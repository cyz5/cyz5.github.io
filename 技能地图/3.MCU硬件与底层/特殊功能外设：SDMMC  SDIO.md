

> 本课聚焦 MCU 高速访问 SD/eMMC/SDIO 外设的底层原理、总线时序、DMA/Cache 一致性、可靠性与工程选型。文中示例以 **SDMMC 4-bit 总线、DMA、FreeRTOS/裸机均适用的分层驱动**为主；寄存器名称因 MCU 厂商而异，代码采用可移植 HAL 适配层表达。

## 1. 学习目标

### 理解

- 理解 SD 卡初始化状态机、CMD/RSP/Data 通道、RCA/CID/CSD/SCR/EXT_CSD 等核心寄存器。
- 理解 SD、SDIO、eMMC 在协议、拓扑、性能和可靠性上的差异。
- 理解 1-bit/4-bit/8-bit、Default Speed/High Speed/UHS、DMA 与 CPU 搬运的边界。

### 掌握

- 掌握 SDMMC 主机初始化、卡识别、总线宽度切换、频率切换和块读写流程。
- 掌握 DMA、D-Cache、内存对齐、超时、CRC、总线错误和热插拔处理。
- 掌握块设备、文件系统、日志层和电源管理的分层设计。

### 精通

- 能定位数据损坏、偶发超时、卡降速、优先级反转、DMA Cache 不一致等现场问题。
- 能基于吞吐、延迟、写放大、掉电一致性和生命周期选择 SD 卡、eMMC 或 SDIO 方案。

### 能够设计

- 能设计具备 DMA、异步 IO、故障恢复、磨损管理、掉电保护和可观测性的工业级存储子系统。

## 2. 前置要求

### 知识要求

- C 语言指针、内存屏障、结构体布局、并发与中断。
- MCU 时钟树、GPIO 复用、DMA、Cache、MPU、NVIC。
- FAT/exFAT 或自定义块存储、CRC、RTOS 同步原语。
- SPI、串行总线时序及基本信号完整性知识。

### 技能要求

- 能阅读 MCU Reference Manual 中 SDMMC、DMA、RCC、GPIO 章节。
- 能使用逻辑分析仪、示波器、示波器电流探头和文件系统一致性工具。
- 能编写硬件抽象层、DMA 回调、故障注入测试和压力测试程序。

## 3. 技术概述

### 3.1 SD、SDIO、SDMMC、eMMC 的定位

- **SD**：可插拔非易失存储卡，主机通过 SD 总线或 SPI 模式访问。
- **SDIO**：在 SD 总线上承载 I/O 功能，可连接 Wi-Fi、蓝牙、GNSS 等从设备；通常使用 CMD52/CMD53 访问寄存器或内存窗口。
- **SDMMC**：MCU 中面向 SD/SDIO/eMMC 的专用主控制器，通常支持 1/4/8 位总线、DMA、硬件 CRC 和超时检测。
- **eMMC**：封装了 NAND、控制器和 FTL 的固定式存储器，主机侧协议类似 MMC，硬件焊接、可靠性和启动能力通常优于可插拔 SD 卡。

### 3.2 协议层次

```
应用/数据库/日志
        ↓
文件系统或自定义存储层
        ↓
块设备层：read(lba,n)、write(lba,n)、ioctl
        ↓
SD/MMC 协议层：命令、响应、数据、状态
        ↓
SDMMC 主机控制器：FIFO、DMA、CRC、超时
        ↓
GPIO/RCC/DMA/Cache/电源
        ↓
SD 卡、SDIO 从设备或 eMMC
```

### 3.3 典型命令

|命令|作用|典型阶段|
|---|---|---|
|CMD0|进入空闲状态|复位|
|CMD8|检查电压范围及 SDHC 能力|初始化|
|CMD55 + ACMD41|SD 卡初始化并等待就绪|初始化|
|CMD2|读取 CID|识别|
|CMD3|获取 RCA|识别|
|CMD7|选择/取消选择卡|传输|
|CMD9|读取 CSD|容量/时序|
|CMD17/CMD18|单块/多块读|数据|
|CMD24/CMD25|单块/多块写|数据|
|CMD12|停止多块传输|数据|
|CMD52/CMD53|SDIO 寄存器/扩展数据访问|SDIO|
|CMD6|SD 高速模式切换或功能查询|模式配置|

## 4. 核心特性横向对比

|维度|SPI 模式 SD|SDMMC 1-bit|SDMMC 4-bit|SDMMC 8-bit/eMMC|SDIO CMD52/53|
|---|---|---|---|---|---|
|线数|2 数据线+控制|1|4|8|1/4|
|协议复杂度|低|中|中|高|高|
|理论吞吐|约 2–20 MB/s|约 2–12 MB/s|约 8–50 MB/s|约 20–100+ MB/s|取决于从设备|
|DMA 支持|视 SPI|通常支持|通常支持|通常支持|通常支持|
|CPU 开销|高|低|低|低|中|
|热插拔|容易|需设计|需设计|不适用|通常不适用|
|适用场景|引脚紧张、低速|调试/降级|常规数据记录|高吞吐、固定存储|Wi-Fi/无线模块|
|主要风险|协议效率低|性能不足|SI/Cache/供电|启动配置复杂|功能中断与窗口流控|

> **工程结论**：新设计若 MCU 有 SDMMC，数据记录优先使用 **4-bit + DMA + 多块传输**；固定式高可靠产品优先评估 **eMMC**；SDIO 无线模块必须同时设计中断线、流控和固件版本兼容策略。

## 5. 底层原理与功能特性深度解析

### 5.1 初始化状态机

SD 卡上电后通常进入 Idle。主机应先提供稳定时钟，再发送 CMD0；随后通过 CMD8 判断电压与版本，使用 CMD55/ACMD41 轮询卡完成初始化。卡 ready 后，读取 CID/CSD，分配 RCA，选择卡，读取 SCR 并切换总线宽度。

```
#define SD_TIMEOUT_MS       1000U
#define SD_OCR_READY        (1UL << 31)
#define SD_OCR_CCS         (1UL << 30)

struct sd_card {
    uint32_t rca;
    uint32_t ocr;
    uint64_t capacity_bytes;
    uint32_t block_size;
    bool high_capacity;
    bool high_speed;
};

static int sd_init(struct sd_card *card)
{
    uint32_t r1, ocr;
    uint32_t start = board_tick_ms();

    if (!card || sd_power_on() != 0)
        return -EINVAL;

    sd_set_clock(400000U);                 /* 识别阶段低速时钟 */
    sd_send_74_clocks();                   /* 卡上电稳定 */
    if (sd_cmd(CMD0, 0, SD_RSP_NONE, NULL) != 0)
        return -EIO;

    if (sd_cmd(CMD8, 0x1AA, SD_RSP_R7, &r1) != 0) {
        /* 老卡可按产品策略支持 v1.x；不能盲目当作 SDHC */
        if (!sd_legacy_card_allowed())
            return -EPROTONOSUPPORT;
    }

    do {
        if (sd_cmd(CMD55, 0, SD_RSP_R1, &r1) != 0)
            return -EIO;
        if (sd_cmd(ACMD41, 0x40FF8000UL, SD_RSP_R3, &ocr) != 0)
            return -EIO;
        if (ocr & SD_OCR_READY)
            break;
    } while ((board_tick_ms() - start) < SD_TIMEOUT_MS);

    if (!(ocr & SD_OCR_READY))
        return -ETIMEDOUT;

    card->ocr = ocr;
    card->high_capacity = (ocr & SD_OCR_CCS) != 0;
    if (sd_cmd(CMD2, 0, SD_RSP_R2, NULL) != 0 ||
        sd_cmd(CMD3, 0, SD_RSP_R6, &card->rca) != 0 ||
        sd_cmd(CMD9, card->rca << 16, SD_RSP_R2, NULL) != 0 ||
        sd_cmd(CMD7, card->rca << 16, SD_RSP_R1B, NULL) != 0)
        return -EIO;

    if (sd_read_scr_and_switch_4bit(card) != 0)
        return -EIO;
    if (sd_try_high_speed(card) != 0)
        card->high_speed = false;          /* 可降级，不应直接误判为致命故障 */

    sd_set_clock(card->high_speed ? 50000000U : 25000000U);
    card->block_size = 512U;
    return sd_read_capacity(card);
}
```

### 5.2 块地址与容量

标准容量卡通常使用字节地址，SDHC/SDXC 使用块地址。错误地把块号乘以 512 后再传给高容量卡，会导致访问错误。

```
static uint32_t sd_arg_from_lba(const struct sd_card *c, uint32_t lba)
{
    return c->high_capacity ? lba : lba * c->block_size;
}
```

容量计算必须依据 CSD 版本解析，不能固定套用单一公式；生产代码应保存原始 CSD 并通过 CRC/范围检查验证解析结果。

### 5.3 多块 DMA 读写

```
int sd_read_blocks(struct sd_card *c, uint32_t lba,
                   void *buf, uint32_t count)
{
    if (!c || !buf || count == 0 || count > SD_MAX_DMA_BLOCKS)
        return -EINVAL;
    if (((uintptr_t)buf & (SD_DMA_ALIGN - 1U)) != 0)
        return -EALIGN;
    if (!board_dma_buffer_valid(buf, count * 512U))
        return -EFAULT;

    dcache_invalidate(buf, count * 512U);
    dma_memory_barrier();

    int rc = sdmmc_start_read_dma(sd_arg_from_lba(c, lba), buf, count);
    if (rc != 0)
        return rc;

    rc = sdmmc_wait_completion(SD_TIMEOUT_MS + count * 2U);
    dma_memory_barrier();
    if (rc != 0) {
        sdmmc_abort();
        sd_clear_errors();
        return sd_recover_after_error(rc);
    }
    dcache_invalidate(buf, count * 512U);
    return 0;
}

int sd_write_blocks(struct sd_card *c, uint32_t lba,
                    const void *buf, uint32_t count)
{
    if (!c || !buf || count == 0 || count > SD_MAX_DMA_BLOCKS)
        return -EINVAL;
    if (((uintptr_t)buf & (SD_DMA_ALIGN - 1U)) != 0)
        return -EALIGN;

    dcache_clean(buf, count * 512U);       /* DMA 读取内存前必须回写 Cache */
    dma_memory_barrier();
    int rc = sdmmc_start_write_dma(sd_arg_from_lba(c, lba), buf, count);
    if (rc != 0)
        return rc;
    rc = sdmmc_wait_completion(SD_WRITE_TIMEOUT_MS + count * 5U);
    if (rc != 0) {
        sdmmc_abort();
        sd_clear_errors();
        return sd_recover_after_error(rc);
    }
    return sd_wait_card_not_busy(SD_WRITE_BUSY_TIMEOUT_MS);
}
```

### 5.4 SDIO CMD52/CMD53

- **CMD52**：单字节寄存器读写，适合 CCCR/FBR 配置、状态确认。
- **CMD53**：块模式或字节模式访问功能空间，适合 Wi-Fi 数据窗口。
- SDIO 从设备常通过 DAT1 提供中断；主机必须先清除中断状态，再读取数据长度和窗口。
- 高吞吐 SDIO 设计要避免逐字节 CMD52，控制面与数据面应分离。

```
int sdio_write_reg(uint8_t fn, uint32_t addr, uint8_t value)
{
    if (fn > 7 || addr > 0x1FFFFU)
        return -EINVAL;
    return sd_cmd52_write(fn, addr, value);
}

int sdio_read_block(uint8_t fn, uint32_t addr,
                    void *buf, uint32_t len)
{
    if (!buf || len == 0 || (len % 4U) != 0)
        return -EINVAL;
    return sd_cmd53_read_block(fn, addr, buf, len);
}
```

### 5.5 CRC、超时和错误状态

硬件通常检查命令 CRC、数据 CRC、FIFO overrun/underrun、数据超时和 DMA 传输错误。驱动应保存：命令号、参数、响应、错误寄存器、DMA 状态、卡状态和电源状态，以便现场复盘。

## 6. 性能量化分析

### 6.1 理论吞吐

对 4-bit 总线，理论原始吞吐为：

```
T_raw = f_clk × bus_width / 8
```

当时钟为 50 MHz、总线宽度为 4：

```
T_raw = 50,000,000 × 4 / 8 = 25 MB/s
```

考虑命令、CRC、忙等待、卡内部编程和主机间隙，连续大块读取的有效吞吐常为 **15–23 MB/s**；随机 4 KB 写入可能只有 **0.1–5 MB/s**，并且延迟呈长尾分布。

### 6.2 典型实测基线

以下为 Cortex-M7 400 MHz、SDMMC 4-bit 50 MHz、DMA、Cache 开启、工业级 UHS-I 卡的典型工程基线，实际值必须以目标卡和板级 SI 实测为准：

|项目|典型值|
|---|---|
|初始化耗时|80–500 ms|
|连续读取，1 MiB|15–23 MB/s|
|连续写入，1 MiB|8–20 MB/s|
|4 KiB 随机读|0.5–4 MB/s|
|单次命令 CPU 占用|DMA 下约 2–15 µs|
|DMA 描述符/控制结构|约 64–512 B|
|512 B 缓冲区|512 B + Cache 对齐填充|
|卡内部写忙时间|1–250 ms，差异很大|

### 6.3 优化手段

1. 使用多块 CMD18/CMD25，避免每个 512 B 块重新发命令。
2. DMA 缓冲区按 Cache line（常见 32/64 B）对齐，读前 invalidate、写前 clean。
3. 将日志聚合为 16–128 KiB 顺序写，减少 FTL 写放大。
4. 读写线程与文件系统线程解耦，使用固定大小内存池，避免实时任务动态分配。
5. 通过逻辑分析仪测量 CLK、CMD、DAT 眼图；降频通常比盲目重试更可靠。

## 7. 应用场景选型指南

```
需要存储还是连接外设？
├─ 连接 Wi-Fi/蓝牙/GNSS
│  └─ 选择 SDIO：CMD52 控制面 + CMD53 数据面 + DAT1 中断
└─ 需要非易失存储
   ├─ 是否需要可插拔？
   │  ├─ 是 → SD 卡；要求 4-bit + DMA + 卡检测 + 掉电策略
   │  └─ 否 → 是否需要高可靠/高并发？
   │      ├─ 是 → eMMC，评估 HS200/HS400、RPMB、寿命
   │      └─ 否 → SD 卡或低成本 eMMC
   └─ 引脚极少或兼容旧硬件 → SPI 模式 SD
```

|场景|方案|理由|
|---|---|---|
|数据记录仪|SDMMC 4-bit + DMA + 环形日志|吞吐和容量平衡|
|工业网关|eMMC + 分区 + 双副本配置|固定连接、可控启动|
|相机/音频|4-bit/8-bit + 大块 DMA|连续吞吐优先|
|Wi-Fi 模块|SDIO 4-bit + DAT1|低协议开销、硬件中断|
|引脚受限低速设备|SPI SD|复用简单、调试容易|

## 8. 工程最佳实践

### 8.1 设计原则

- **协议层、控制器层、块设备层和文件系统层分离**。
- 所有 IO 都有明确超时；禁止无限等待卡 ready 或 DMA 完成。
- 读写接口返回结构化错误，不要只返回 `false`。
- 将卡检测、电源控制、总线复位和降速恢复纳入状态机。
- 文件系统不能直接操作寄存器，必须通过块设备接口。
- 生产系统保留卡 CID、CSD、固件版本、错误计数和最近一次命令。

### 8.2 选型决策矩阵

|约束|优先方案|
|---|---|
|最大吞吐|8-bit eMMC 或 4-bit SDMMC 高速模式|
|最低 BOM|SPI SD|
|可维护性|可插拔 SD + 卡检测 + 诊断日志|
|掉电安全|eMMC 高可靠特性/电源保持/日志事务|
|低延迟|eMMC、预分配文件、顺序写|
|无线外设|SDIO 4-bit + 中断和流控|

### 8.3 工业级编码规范

- LBA、长度、字节数使用固定宽度整数并检查乘法溢出。
- DMA 缓冲区禁止位于不可访问或 Cache 属性错误的内存区域。
- 中断只记录状态并唤醒线程，不在 ISR 中执行文件系统操作。
- 挂载前验证分区表/文件系统；卸载前停止写入并等待卡非忙。
- 任何重试都必须有上限，且区分 CRC 瞬态错误与卡永久错误。

## 9. 常见错误与避坑指南

### 错误一：DMA 与 D-Cache 不一致

```
memcpy(tx_buf, data, 512);
sdmmc_start_write_dma(..., tx_buf, 1); /* 错误：未 clean cache */
```

**根因**：DMA 直接访问 RAM，CPU 修改仍停留在 Cache。  
**正确实现**：写 DMA 前 `dcache_clean()`，读 DMA 前 invalidate，配合内存屏障。  
**风险**：偶发旧数据、压力测试才出现的文件系统损坏。

### 错误二：把 SDHC 当字节地址卡

```
cmd_arg = lba * 512; /* 对 SDHC/SDXC 错误 */
```

**根因**：未依据 OCR 的 CCS 位区分地址单位。  
**正确实现**：高容量卡传 LBA，标准容量卡传字节地址。  
**风险**：访问错误块，可能破坏分区元数据。

### 错误三：无限等待卡非忙

```
while (sdmmc_card_is_busy()) { } /* 错误 */
```

**根因**：假设卡永远最终完成。  
**正确实现**：带绝对超时、复位和故障记录。  
**风险**：系统线程永久阻塞，喂狗失败，整机失控。

### 错误四：单块写文件日志

```
for (...) {
    fs_write(file, record, 512); /* 每条记录触发一次小写 */
}
```

**根因**：忽略 NAND page、FTL 和文件系统元数据更新。  
**正确实现**：RAM 聚合、顺序预分配、批量 flush、掉电事务标记。  
**风险**：吞吐低、写放大大、卡寿命缩短。

### 错误五：高速模式未经 SI 验证

**根因**：走线过长、串扰、上下拉不合适、供电噪声或电平不匹配。  
**正确实现**：先低速验证，再逐级升频；检查 CLK/DAT 边沿、眼图和错误计数。  
**风险**：温度、电压或批次变化后出现间歇性 CRC 错误。

### 错误六：热插拔直接拔电

**根因**：文件系统仍有缓存，卡正在编程。  
**正确实现**：停止写入、flush、卸载、确认非忙后断电；异常拔出时使用日志恢复。  
**风险**：目录损坏、FAT 链断裂、卡进入不可识别状态。

## 10. 多机制组合使用方案

### 10.1 推荐架构

```
采集任务
   ↓ 无锁/单生产者队列
日志聚合任务（16~128 KiB）
   ↓ 双缓冲 + CRC + 序号
块设备异步 IO 任务
   ↓ DMA + Cache 维护
SDMMC 驱动
   ↓
SD 卡/eMMC
   ↑
错误恢复、卡检测、电源管理、统计监控
```

### 10.2 双缓冲日志框架

```
struct log_block {
    uint32_t magic;
    uint32_t sequence;
    uint32_t payload_len;
    uint8_t  payload[LOG_PAYLOAD_SIZE];
    uint32_t crc;
} __attribute__((aligned(64)));

static struct log_block g_buf[2];
static atomic_uint g_active;

int log_commit(struct log_block *b, uint32_t lba)
{
    if (!b || b->payload_len > LOG_PAYLOAD_SIZE)
        return -EINVAL;
    b->magic = LOG_MAGIC;
    b->crc = crc32(b, offsetof(struct log_block, crc));
    dcache_clean(b, sizeof(*b));
    int rc = sd_write_blocks(&g_card, lba, b,
                             (sizeof(*b) + 511U) / 512U);
    if (rc != 0)
        telemetry_record_storage_error(rc, lba, b->sequence);
    return rc;
}
```

掉电恢复时扫描魔数、序号和 CRC，选择最后一个连续有效块；不要依赖“文件大小”作为唯一一致性依据。

## 11. 工业级实际案例分析

### 案例一：振动监测数据记录仪

**需求**：8 路传感器，单通道 10 kS/s，16 bit，总数据率约 160 kB/s，断电后最多丢失 1 s。  
**架构**：采集 DMA → SPSC 队列 → 64 KiB 聚合 → SDMMC 4-bit DMA → 环形文件。  
**设计要点**：文件预分配；每个块写入序号、时间戳、长度、CRC；电压跌落中断触发停止采集和最后一次 flush。  
**结果目标**：持续写入只需约 1 MB/s，显著低于卡连续写能力，但通过大块顺序写降低写放大和延迟长尾。

### 案例二：工业网关 eMMC 系统

**需求**：Linux/RTOS 双系统启动、配置不可丢失、现场升级可回滚。  
**架构**：Boot 分区 + A/B 系统分区 + 数据分区 + 配置双副本；关键密钥使用 RPMB（若器件支持）。  
**设计要点**：升级包先写非活动分区，校验完整后原子切换启动标志；配置使用版本号、CRC 和双备份；监控设备寿命和坏块统计。  
**风险控制**：禁止直接覆盖当前启动分区；升级过程中掉电必须能回到旧版本。

### 案例三：SDIO Wi-Fi 数据通道

**需求**：低延迟网络收发，控制寄存器访问与数据流并发。  
**架构**：CMD52 配置 CCCR/FBR，CMD53 访问 TX/RX window，DAT1 中断唤醒驱动任务，另设 host-to-card 流控。  
**设计要点**：中断只读取状态并投递事件；RX buffer 使用 DMA 对齐内存池；根据设备声明的 block size 合并传输；超时后复位功能块而非直接复位整机。

## 12. 高频问题深度答疑

### 1. 为什么标称 50 MB/s，实际只有 15 MB/s？

标称值通常是接口原始或理想连续吞吐；实际还包括命令间隙、CRC、DMA 配置、卡内部 FTL、写忙、文件系统和随机访问。应使用大块裸盘测试区分“总线能力”和“卡介质能力”。

### 2. DMA 已完成但读出的数据仍是旧数据，为什么？

最常见是 D-Cache 未 invalidate，或 invalidate 范围未覆盖 Cache line。还要检查 DMA 是否真的写入了目标 RAM、MPU 是否将区域配置为设备/不可缓存、是否存在缓冲区别名。

### 3. 多块写为什么比单块写快很多？

多块传输摊薄命令和响应开销，卡可以连续规划 NAND page，主机也减少中断次数。对日志系统而言，聚合写通常比提高总线频率更有效。

### 4. CRC 错误应该重试还是降速？

偶发单次错误可有限重试；若错误在固定频率、温度或电压下持续出现，应优先降速、检查 SI、供电和接地。无限重试会掩盖硬件问题并破坏实时性。

### 5. SD 卡适合做数据库吗？

可以，但不能把它当低延迟块盘。应采用 WAL/日志结构、顺序写、预分配、批量提交、掉电恢复和卡寿命监控；高一致性、高并发和固定式产品通常优先 eMMC 或专用工业存储。

### 6. 为什么热插拔后卡偶尔无法重新识别？

可能存在卡电源未完全放电、DAT 仍被拉低、控制器状态机未复位、GPIO 复用残留或插拔抖动。重新插入流程应包含停止 DMA、关闭时钟、控制器复位、GPIO 重新初始化、电源放电延时和完整重新识别。

## 13. 课程核心总结

- **性能排序**：8-bit eMMC > 4-bit SDMMC > 1-bit SDMMC > SPI SD；实际性能还受卡介质和访问模式决定。
- **可靠性核心**：超时、有限重试、错误日志、掉电事务、Cache 一致性和 SI 验证缺一不可。
- **通用选型**：可插拔数据记录选 SDMMC 4-bit；固定式工业设备选 eMMC；无线模块选 SDIO；极简兼容场景选 SPI。
- **最重要的工程原则**：不要只验证“能读写”，必须验证温度、电压、批次、热插拔、掉电、长时间压力和文件系统恢复。

## 14. 快速参考速查表

### 场景选型表

|需求|推荐|
|---|---|
|低成本可插拔|SDMMC 4-bit|
|引脚最少|SPI SD|
|固定高可靠存储|eMMC|
|Wi-Fi/蓝牙扩展|SDIO 4-bit|
|最大连续吞吐|eMMC 8-bit 或 SDMMC 高速模式|
|强掉电恢复|日志结构 + 双副本 + 电源保持|

### 特性对比表

|项目|关键检查|
|---|---|
|初始化|CMD8、ACMD41、CID/CSD、RCA、SCR|
|地址|SDSC 字节地址，SDHC/SDXC 块地址|
|DMA|对齐、可访问性、描述符、超时|
|Cache|读 invalidate，写 clean，内存屏障|
|写入|多块、聚合、预分配、非忙等待|
|错误|CRC、超时、FIFO、DMA、卡状态|
|热插拔|停写、flush、卸载、复位、放电|
|SDIO|CMD52 控制、CMD53 数据、DAT1 中断|

## 15. 学习效果自检

- [ ]  能画出 SD 卡从 CMD0 到传输态的初始化状态机。
- [ ]  能解释 CMD8、ACMD41、CMD3、CMD7、CMD17、CMD18、CMD24、CMD25 的作用。
- [ ]  能正确区分 SDSC 与 SDHC/SDXC 的地址单位。
- [ ]  能解释 DMA 与 D-Cache 不一致的根因并写出正确维护代码。
- [ ]  能计算 4-bit/50 MHz 的理论吞吐并解释有效吞吐差异。
- [ ]  能设计超时、重试、降速、控制器复位和卡重新识别流程。
- [ ]  能为 SDIO 设计 CMD52/CMD53、DAT1 中断和流控架构。
- [ ]  能实现掉电后基于序号和 CRC 的日志恢复。

## 16. 实践与进阶路径

### 梯度实战任务

1. **基础驱动**：完成 1-bit 初始化、CID/CSD 读取和单块读写。
2. **性能版本**：切换 4-bit、DMA、多块读写，测量裸盘吞吐。
3. **可靠性版本**：加入超时、错误寄存器采集、有限重试和降速恢复。
4. **文件系统版本**：实现预分配环形日志、CRC、掉电恢复和卡热插拔。
5. **SDIO 版本**：完成 CMD52 寄存器访问、CMD53 块传输和 DAT1 中断。
6. **工业验证**：进行 0–70 ℃、电压边界、不同卡批次、插拔、掉电和 72 小时压力测试。

### 性能测试方法

- 裸块设备分别测试 512 B、4 KiB、64 KiB、1 MiB 顺序/随机读写。
- 记录平均值、P95、P99 和最大延迟，不只看平均吞吐。
- 同时采集 DMA 中断次数、CPU 占用、卡 busy 时间、CRC 错误和重试次数。
- 使用逻辑分析仪确认命令、数据宽度、频率和停止传输时序。
- 对文件系统测试异常掉电、目录恢复、写满行为和长期写放大。

### 进阶方向

- SD UHS-I、DDR50、eMMC HS200/HS400 与信号完整性。
- Linux MMC core、block layer、DMA mapping、ext4/F2FS 与设备树。
- eMMC 分区、boot partition、RPMB、寿命监控和安全启动。
- 高可靠日志结构、事务存储、数据库 WAL 和端到端 CRC。
- 基于故障注入的存储可靠性验证与 IEC 61508/ISO 26262 工程流程。