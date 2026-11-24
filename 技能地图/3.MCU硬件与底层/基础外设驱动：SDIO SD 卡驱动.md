​
## 1. 学习目标

### 理解

- 理解 SD 卡物理层、命令层、数据传输层与文件系统层的分层关系。
- 理解 SD、SDHC、SDXC、SPI 模式、SDIO/SDMMC 模式之间的差异。
- 理解 SD 卡初始化状态机、OCR、CID、CSD、RCA、SCR、总线宽度和传输状态。
- 理解 SDIO/SDMMC 控制器、DMA、Cache、一致性和中断之间的关系。
- 理解块设备驱动与 FatFs 等文件系统之间的接口边界。

### 掌握

- 掌握 SD 卡上电初始化、卡识别、容量计算和总线配置流程。
- 掌握单块、多块读写命令：`CMD17`、`CMD18`、`CMD24`、`CMD25`。
- 掌握 SDIO/SDMMC + DMA 的驱动框架。
- 掌握超时、CRC 错误、数据超限、卡移除和写保护处理。
- 掌握 4-bit SDIO、1-bit SDIO 与 SPI 模式的选型方法。
- 掌握 FatFs `diskio.c` 与底层块设备驱动的适配。

### 精通

- 能够分析 SD 卡协议交互、控制器状态机和 DMA 描述符。
- 能够定位 Cache 不一致、DMA 卡死、总线错误、写入异常和随机性能下降。
- 能够设计带超时恢复、并发保护、掉电保护和故障统计的工业级 SD 卡驱动。
- 能够基于实际吞吐、延迟、写放大和任务调度约束进行架构优化。

### 能够设计

- 能够设计完整的 `Block Device -> SD Driver -> SDIO/SDMMC HAL -> DMA` 分层架构。
- 能够设计日志、升级包、参数存储和数据采集等场景下的 SD 卡存储方案。
- 能够设计 SD 卡热插拔、文件系统一致性和异常掉电恢复机制。
- 能够建立 SD 卡性能测试、可靠性测试和现场故障诊断体系。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、数组、结构体、枚举、位操作和错误码设计。
- 熟悉 MCU 时钟树、GPIO 复用、DMA、中断和 Cache 基本机制。
- 熟悉 RTOS 任务、互斥锁、信号量、事件和超时机制。
- 了解 SPI、CRC、块设备和 FAT 文件系统基本概念。
- 了解 ARM Cortex-M 的 D-Cache、MPU、内存屏障和非缓存区域。

### 技能要求

- 能够阅读 MCU Reference Manual 中 SDIO/SDMMC 章节。
- 能够使用逻辑分析仪或示波器观察 CLK、CMD、D0-D3。
- 能够配置 DMA、处理中断并定位总线错误。
- 能够编译和调试 FatFs。
- 能够编写至少一个稳定的裸机或 RTOS 外设驱动。

---

## 3. 技术概述

### 3.1 SD 卡驱动的分层结构

SD 卡驱动不等于文件系统驱动。工业实现通常划分为五层：

```
应用层
  |
文件系统层：FatFs / littlefs（通常不直接用于标准 SD 卡）
  |
块设备适配层：disk_read / disk_write / disk_ioctl
  |
SD 卡协议驱动：初始化、命令、数据、状态、错误恢复
  |
控制器驱动：SDIO / SDMMC / SPI / DMA / 中断
  |
硬件层：GPIO、时钟、电源、卡检测、写保护
```

核心接口应保持为块设备语义：

```
typedef struct
{
    int (*init)(void *ctx);
    int (*read_blocks)(void *ctx,
                       uint8_t *buf,
                       uint32_t lba,
                       uint32_t count);
    int (*write_blocks)(void *ctx,
                        const uint8_t *buf,
                        uint32_t lba,
                        uint32_t count);
    int (*ioctl)(void *ctx, uint32_t cmd, void *arg);
    int (*is_present)(void *ctx);
} block_device_t;
```

文件系统只关心：

- 逻辑块地址 `LBA`
- 块数量
- 读写是否成功
- 扇区大小
- 卡容量
- 同步操作

它不应该感知 `CMD17`、`CMD24` 或 SDIO 寄存器。

---

### 3.2 主要工作模式

#### SPI 模式

使用普通 SPI 外设访问 SD 卡：

```
MCU SPI_SCK  -> SD CLK
MCU SPI_MOSI -> SD CMD
MCU SPI_MISO -> SD DAT0
CS           -> SD CS
```

特点：

- 只使用一条数据线。
- 协议简单，适合低端 MCU 和调试。
- 吞吐通常低于 SDIO 4-bit。
- 命令和数据通过 SPI 帧传输。
- 无法使用原生 SDIO 多线数据通道。

#### SDIO 1-bit

使用 SD 原生协议，一条数据线：

```
CLK + CMD + DAT0
```

特点：

- 比 SPI 更高效。
- 仍保持较少 GPIO。
- 吞吐低于 4-bit。
- 调试和布线相对简单。

#### SDIO/SDMMC 4-bit

使用：

```
CLK + CMD + DAT0 + DAT1 + DAT2 + DAT3
```

特点：

- 常见工业方案。
- 支持多块读写和 DMA。
- 吞吐高，CPU 占用低。
- 对信号完整性、时序和 Cache 一致性要求更高。

---

### 3.3 常用命令

|命令|名称|作用|
|---|---|---|
|`CMD0`|GO_IDLE_STATE|卡复位，进入 Idle|
|`CMD8`|SEND_IF_COND|检测 SD 版本和电压范围|
|`CMD55`|APP_CMD|下一条命令为 ACMD|
|`ACMD41`|SD_SEND_OP_COND|初始化卡并等待 Ready|
|`CMD2`|ALL_SEND_CID|获取卡 CID|
|`CMD3`|SEND_RELATIVE_ADDR|获取 RCA|
|`CMD7`|SELECT/DESELECT_CARD|选中卡|
|`ACMD6`|SET_BUS_WIDTH|配置 1-bit/4-bit|
|`ACMD51`|SEND_SCR|读取卡的功能配置|
|`CMD9`|SEND_CSD|读取 CSD|
|`CMD13`|SEND_STATUS|读取卡状态|
|`CMD16`|SET_BLOCKLEN|设置块长度|
|`CMD17`|READ_SINGLE_BLOCK|读单块|
|`CMD18`|READ_MULTIPLE_BLOCK|读多块|
|`CMD12`|STOP_TRANSMISSION|停止多块传输|
|`CMD24`|WRITE_BLOCK|写单块|
|`CMD25`|WRITE_MULTIPLE_BLOCK|写多块|
|`CMD23`|SET_BLOCK_COUNT|设置预擦除块数量|

---

## 4. 核心特性横向对比

### 4.1 访问模式对比

|维度|SPI|SDIO 1-bit|SDIO 4-bit|SDMMC 4-bit + DMA|
|---|---|---|---|---|
|数据线数量|1|1|4|4|
|协议复杂度|低|中|中|中高|
|峰值总线速率|`f_spi`|`f_clk`|`4 × f_clk`|`4 × f_clk`|
|CPU 占用|高|中高|中|低|
|DMA 支持|取决于 SPI|支持|支持|完整支持|
|多块传输|可实现|支持|支持|适合|
|初始化难度|低|中|中|中高|
|信号完整性要求|低|中|中高|中高|
|适用场景|低速、低成本、调试|GPIO 受限|常规产品|高吞吐、采集、日志|
|推荐速度|1~25 MHz|12~25 MHz|12~50 MHz|24~50 MHz，视平台而定|

> 实际吞吐不是理论总线速率。命令、响应、等待忙、卡内部擦写、DMA 配置和文件系统元数据都会降低有效吞吐。

---

### 4.2 SD 卡类型对比

|类型|容量范围|地址单位|`OCR CCS`|`CMD16`|典型注意事项|
|---|---|---|---|---|---|
|SDSC|小于等于 2 GB|字节地址|0|必须设置 512 字节|地址计算需要 `LBA × 512`|
|SDHC|2 GB 到 32 GB|块地址|1|通常固定 512 字节|地址直接使用 LBA|
|SDXC|大于 32 GB|块地址|1|通常固定 512 字节|文件系统、容量、许可与格式化策略需确认|
|SDUC|更大容量|块地址|视规范|平台支持有限|MCU 控制器和文件系统可能不支持|

地址转换：

```
static uint32_t sd_lba_to_arg(bool block_addressing, uint32_t lba)
{
    return block_addressing ? lba : lba * 512U;
}
```

---

### 4.3 数据传输方式对比

|方式|CPU 参与度|实时性|适合数据量|典型问题|
|---|---|---|---|---|
|轮询|高|可控但阻塞|小块|占用 CPU，容易超时|
|中断|中|较好|中等|中断复杂，吞吐有限|
|DMA|低|好|大块|Cache、地址对齐、边界处理|
|DMA + 多块命令|低|最佳|大量连续数据|停止命令、卡忙、错误恢复|

---

## 5. 底层原理与功能特性深度解析

## 5.1 SD 卡上电初始化状态机

典型初始化过程：

```
上电稳定
  |
配置 GPIO 为默认输入/上拉
  |
SDCLK <= 400 kHz
  |
发送 CMD0
  |
发送 CMD8
  |
循环发送 CMD55 + ACMD41
  |
读取 OCR，确认卡 Ready
  |
CMD2 获取 CID
  |
CMD3 获取 RCA
  |
CMD9 获取 CSD
  |
CMD7 选卡
  |
ACMD6 切换 4-bit
  |
提高时钟频率
  |
进入 Transfer 状态
```

### 5.1.1 初始化约束

初始化阶段通常要求：

- 时钟不超过约 `400 kHz`。
- 上电后发送至少 74 个时钟周期。
- CMD、DAT 线处于合适上拉状态。
- 等待卡内部电源和振荡器稳定。
- `ACMD41` 必须设置 `HCS`，以支持 SDHC/SDXC。
- 必须检查 OCR 中的电压窗口和 Busy 位。

### 5.1.2 初始化伪代码

```
#define SD_INIT_CLOCK_HZ       400000U
#define SD_ACMD41_TIMEOUT_MS   1000U

static int sd_card_init(sd_card_t *card)
{
    uint32_t response;
    uint32_t ocr;
    uint32_t start;

    if (card == NULL)
    {
        return SD_ERR_INVALID_ARG;
    }

    sd_hw_set_clock(SD_INIT_CLOCK_HZ);
    sd_hw_set_bus_width(SD_BUS_WIDTH_1);
    sd_hw_send_dummy_clocks(80U);

    if (sd_send_command(CMD0, 0U, SD_RESP_NONE, NULL) != SD_OK)
    {
        return SD_ERR_CMD;
    }

    /*
     * CMD8 不被旧卡支持。
     * SDHC/SDXC 卡通常应正确响应 CMD8。
     */
    card->version2 = false;
    if (sd_send_command(CMD8, 0x1AAU, SD_RESP_R7, &response) == SD_OK)
    {
        if ((response & 0xFFFU) != 0x1AAU)
        {
            return SD_ERR_VOLTAGE;
        }

        card->version2 = true;
    }

    start = sd_get_tick_ms();

    do
    {
        if (sd_send_command(CMD55, 0U, SD_RESP_R1, &response) != SD_OK)
        {
            return SD_ERR_CMD;
        }

        /*
         * HCS=1：告诉卡主机支持高容量块寻址。
         */
        uint32_t arg = card->version2 ? 0x40000000UL : 0UL;

        if (sd_send_command(ACMD41, arg, SD_RESP_R3, &ocr) != SD_OK)
        {
            return SD_ERR_CMD;
        }

        if ((ocr & 0x80000000UL) != 0U)
        {
            break;
        }
    } while ((sd_get_tick_ms() - start) < SD_ACMD41_TIMEOUT_MS);

    if ((ocr & 0x80000000UL) == 0U)
    {
        return SD_ERR_TIMEOUT;
    }

    card->block_addressing = ((ocr & 0x40000000UL) != 0U);

    if (sd_send_command(CMD2, 0U, SD_RESP_R2, card->cid) != SD_OK)
    {
        return SD_ERR_CMD;
    }

    if (sd_send_command(CMD3, 0U, SD_RESP_R6, &card->rca) != SD_OK)
    {
        return SD_ERR_CMD;
    }

    card->rca = card->rca & 0xFFFF0000UL;

    if (sd_read_csd(card, card->csd) != SD_OK)
    {
        return SD_ERR_CSD;
    }

    if (sd_send_command(CMD7,
                        card->rca,
                        SD_RESP_R1B,
                        &response) != SD_OK)
    {
        return SD_ERR_CMD;
    }

    if (sd_set_bus_width(card, SD_BUS_WIDTH_4) != SD_OK)
    {
        /*
         * 部分卡或部分硬件可退回 1-bit 工作。
         */
        sd_hw_set_bus_width(SD_BUS_WIDTH_1);
        card->bus_width = SD_BUS_WIDTH_1;
    }
    else
    {
        card->bus_width = SD_BUS_WIDTH_4;
    }

    sd_hw_set_clock(card->target_clock_hz);

    return SD_OK;
}
```

---

## 5.2 响应类型与错误判断

SD 卡响应不仅是一个返回值。

|响应|长度|用途|
|---|---|---|
|R1|48 bit|普通命令状态|
|R1b|48 bit + Busy|可能持续拉低 DAT0|
|R2|136 bit|CID/CSD|
|R3|48 bit|OCR|
|R6|48 bit|RCA|
|R7|48 bit|CMD8|

R1 中的关键错误位：

```
#define SD_R1_OUT_OF_RANGE       (1UL << 31)
#define SD_R1_ADDRESS_ERROR      (1UL << 30)
#define SD_R1_BLOCK_LEN_ERROR    (1UL << 29)
#define SD_R1_ERASE_SEQ_ERROR    (1UL << 28)
#define SD_R1_ERASE_PARAM        (1UL << 27)
#define SD_R1_WP_VIOLATION       (1UL << 26)
#define SD_R1_CARD_IS_LOCKED     (1UL << 25)
#define SD_R1_LOCK_UNLOCK_FAILED  (1UL << 24)
#define SD_R1_COM_CRC_ERROR      (1UL << 23)
#define SD_R1_ILLEGAL_COMMAND    (1UL << 22)
#define SD_R1_CARD_ECC_FAILED    (1UL << 21)
#define SD_R1_CC_ERROR           (1UL << 20)
#define SD_R1_ERROR               (1UL << 19)
#define SD_R1_CSD_OVERWRITE       (1UL << 16)
#define SD_R1_WP_ERASE_SKIP       (1UL << 15)
#define SD_R1_CARD_ECC_DISABLED   (1UL << 14)
#define SD_R1_ERASE_RESET         (1UL << 13)
#define SD_R1_READY_FOR_DATA      (1UL << 8)
#define SD_R1_APP_CMD             (1UL << 5)
#define SD_R1_CURRENT_STATE_MASK  (0xFUL << 9)
```

不要只判断“命令有没有响应”，还要检查：

```
static int sd_check_r1(uint32_t r1)
{
    const uint32_t fatal =
        SD_R1_OUT_OF_RANGE |
        SD_R1_ADDRESS_ERROR |
        SD_R1_BLOCK_LEN_ERROR |
        SD_R1_WP_VIOLATION |
        SD_R1_COM_CRC_ERROR |
        SD_R1_ILLEGAL_COMMAND |
        SD_R1_CARD_ECC_FAILED |
        SD_R1_CC_ERROR |
        SD_R1_ERROR;

    if ((r1 & fatal) != 0U)
    {
        return SD_ERR_CARD_STATUS;
    }

    return SD_OK;
}
```

---

## 5.3 CSD 与容量计算

### 5.3.1 SDHC/SDXC 容量

对于高容量卡，CSD Version 2：

```
容量 = (C_SIZE + 1) × 512 KiB
```

代码：

```
static uint64_t sd_capacity_from_csd_v2(const uint8_t csd[16])
{
    uint32_t c_size;

    /*
     * CSD 中 C_SIZE 位于 [69:48]。
     * 这里假定 csd[0] 为最高位字节。
     */
    c_size =
        (((uint32_t)(csd[7] & 0x3FU)) << 16) |
        ((uint32_t)csd[8] << 8) |
        (uint32_t)csd[9];

    return ((uint64_t)c_size + 1ULL) * 512ULL * 1024ULL;
}
```

### 5.3.2 SDSC 容量

CSD Version 1 需要组合：

```
容量 =
  (C_SIZE + 1)
  × 2^(C_SIZE_MULT + 2)
  × READ_BL_LEN
```

此外，还需要考虑：

- `READ_BL_PARTIAL`
- `WRITE_BL_LEN`
- `C_SIZE_MULT`
- 是否固定 512 字节块操作

生产代码建议通过位域提取函数或经过验证的 CSD 解析模块完成，不要直接在业务代码中散落魔数。

---

## 5.4 单块与多块读写

### 5.4.1 读操作

单块读：

```
CMD17
  |
等待数据令牌
  |
接收 512 字节
  |
接收 CRC16
```

多块读：

```
CMD18
  |
Block 0
Block 1
Block 2
...
CMD12
```

多块读通常比循环调用 `CMD17` 更高效，因为：

- 命令开销更低。
- 卡内部可以连续预取。
- DMA 可以持续搬运。
- 总线空闲时间更少。

### 5.4.2 写操作

单块写：

```
CMD24
  |
发送数据令牌
  |
发送 512 字节
  |
发送 CRC16
  |
等待卡内部编程
```

多块写：

```
CMD25
  |
发送多个数据块
  |
发送停止传输令牌
  |
等待卡完成内部编程
```

写操作返回数据响应令牌后，卡可能仍处于 Busy：

```
DAT0 = 0  -> 卡忙
DAT0 = 1  -> 卡完成
```

因此“数据响应正确”不等于“写入已经完成”。

---

## 5.5 DMA 与 Cache 一致性

这是 Cortex-M7、Cortex-M33 高性能平台上最常见的问题之一。

### 5.5.1 读路径

DMA 从 SDIO 外设写入内存：

```
SD 卡 -> SDIO FIFO -> DMA -> RAM
```

如果 CPU Cache 中已经有目标地址对应的旧数据，CPU 可能继续读取旧 Cache 行，而不是 DMA 写入的新数据。

正确流程：

```
SCB_InvalidateDCache_by_Addr(buffer, length);
memory_barrier();
start_dma_read();
wait_dma_complete();
memory_barrier();
SCB_InvalidateDCache_by_Addr(buffer, length);
```

### 5.5.2 写路径

CPU 修改了 Buffer，但数据仍在 D-Cache 中，RAM 还没有更新。DMA 读取 RAM 时会获取旧数据。

正确流程：

```
SCB_CleanDCache_by_Addr(buffer, length);
memory_barrier();
start_dma_write();
wait_dma_complete();
```

### 5.5.3 地址和长度对齐

Cortex-M Cache 行常见为 32 字节，但应以具体内核和芯片手册为准：

```
#define CACHE_LINE_SIZE 32U

static void cache_align_range(const void *addr,
                              size_t len,
                              uintptr_t *start,
                              size_t *aligned_len)
{
    uintptr_t begin = (uintptr_t)addr;
    uintptr_t end = begin + len;

    *start = begin & ~(CACHE_LINE_SIZE - 1U);
    end = (end + CACHE_LINE_SIZE - 1U) &
          ~(CACHE_LINE_SIZE - 1U);

    *aligned_len = end - *start;
}
```

通用封装：

```
static void sd_dma_prepare_rx(void *buffer, size_t length)
{
    uintptr_t start;
    size_t aligned_len;

    cache_align_range(buffer, length, &start, &aligned_len);

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                  (int32_t)aligned_len);
    __DSB();
    __ISB();
}

static void sd_dma_prepare_tx(const void *buffer, size_t length)
{
    uintptr_t start;
    size_t aligned_len;

    cache_align_range(buffer, length, &start, &aligned_len);

    SCB_CleanDCache_by_Addr((uint32_t *)start,
                            (int32_t)aligned_len);
    __DSB();
    __ISB();
}
```

### 5.5.4 更稳妥的设计

可选方案：

1. 将 DMA Buffer 放入非缓存 SRAM。
2. 使用专用 32 字节对齐的 DMA 缓冲区。
3. 每次 DMA 前后执行 Cache 维护。
4. 通过 MPU 将固定 DMA 区域配置为 Non-cacheable。
5. 禁止业务层直接修改正在 DMA 的 Buffer。

推荐：

```
文件系统 Buffer
      |
对齐检查
      |
DMA Bounce Buffer
      |
SDIO DMA
```

对于大规模连续传输，Bounce Buffer 会增加一次内存拷贝；对于小块非对齐访问，则通常能显著降低 Cache 风险。

---

## 5.6 RTOS 并发控制

SD 卡控制器通常是单资源，多个任务不能并发发命令。

```
typedef struct
{
    sd_hw_t hw;
    os_mutex_t lock;
    os_event_t event;
    volatile uint32_t irq_status;
    uint32_t block_size;
    uint32_t block_count;
    bool initialized;
    bool block_addressing;
} sd_card_t;
```

读写接口：

```
int sd_read_blocks(sd_card_t *card,
                   void *buffer,
                   uint32_t lba,
                   uint32_t count)
{
    int rc;

    if ((card == NULL) ||
        (buffer == NULL) ||
        (count == 0U) ||
        (count > SD_MAX_TRANSFER_BLOCKS))
    {
        return SD_ERR_INVALID_ARG;
    }

    if (!card->initialized)
    {
        return SD_ERR_NOT_INITIALIZED;
    }

    if (!sd_card_present(card))
    {
        return SD_ERR_NO_CARD;
    }

    if (os_mutex_lock(&card->lock, SD_LOCK_TIMEOUT_MS) != OS_OK)
    {
        return SD_ERR_BUSY;
    }

    rc = sd_validate_range(card, lba, count);
    if (rc != SD_OK)
    {
        goto exit;
    }

    rc = sd_controller_read_dma(card,
                                buffer,
                                sd_lba_to_arg(card->block_addressing, lba),
                                count);

exit:
    os_mutex_unlock(&card->lock);
    return rc;
}
```

关键原则：

- **锁住整个命令和数据事务**，不要只锁命令阶段。
- 中断服务函数不能获取普通互斥锁。
- ISR 只记录状态并释放事件。
- 写操作的锁持有时间可能远大于读操作。
- 长事务应有明确超时，不能无限等待。

---

## 5.7 卡状态与传输状态

典型状态：

```
Idle
  |
Ready
  |
Identification
  |
Stand-by
  |
Transfer
  |
Sending-data / Receive-data
  |
Programming
  |
Disconnect
```

正常读写前卡应处于 `Transfer` 状态。

使用 `CMD13` 检查：

```
static int sd_wait_transfer_state(sd_card_t *card,
                                  uint32_t timeout_ms)
{
    uint32_t start = sd_get_tick_ms();
    uint32_t status;

    do
    {
        if (sd_send_command(CMD13,
                            card->rca,
                            SD_RESP_R1,
                            &status) != SD_OK)
        {
            return SD_ERR_CMD;
        }

        if ((status & SD_R1_ERROR_MASK) != 0U)
        {
            return SD_ERR_CARD_STATUS;
        }

        uint32_t state =
            (status & SD_R1_CURRENT_STATE_MASK) >> 9;

        if ((state == SD_STATE_TRANSFER) &&
            ((status & SD_R1_READY_FOR_DATA) != 0U))
        {
            return SD_OK;
        }
    } while ((sd_get_tick_ms() - start) < timeout_ms);

    return SD_ERR_TIMEOUT;
}
```

---

## 6. 性能量化分析

以下数据是典型工程测试参考值，测试平台假设：

```
MCU：Cortex-M7，主频 400 MHz
SD 控制器：原生 SDMMC
DMA：FIFO DMA
总线：4-bit
SD 时钟：48 MHz
块大小：512 bytes
Cache：D-Cache 开启
文件系统：FatFs
```

不同 MCU、卡型号、温度、文件系统状态和测试方法会导致较大差异，量产前必须在目标硬件上复测。

### 6.1 理论带宽

4-bit 总线理论比特率：

```
48 MHz × 4 bit = 192 Mbit/s
```

换算为字节：

```
192 / 8 = 24 MB/s
```

考虑协议和时序开销：

```
有效吞吐 ≈ 24 MB/s × 0.75 ~ 0.90
          ≈ 18 ~ 21.6 MB/s
```

实际卡内部能力通常更低。

### 6.2 典型实测范围

|操作|访问方式|典型吞吐|CPU 占用|
|---|---|---|---|
|512 B 单块读|DMA + CMD17|0.5~2 MB/s|5%~15%|
|32 KB 连续读|DMA + CMD18|12~20 MB/s|1%~5%|
|512 B 单块写|DMA + CMD24|0.2~2 MB/s|5%~15%|
|32 KB 连续写|DMA + CMD25|5~18 MB/s|1%~8%|
|4 KB 随机写|文件系统层|0.05~3 MB/s|依卡而定|
|1 MB 顺序写|文件系统层|4~15 MB/s|2%~10%|

### 6.3 影响吞吐的因素

#### 命令开销

单块读每次都要发送命令：

```
有效吞吐 = 数据量 / (命令时间 + 数据时间 + 卡等待时间)
```

当单次数据只有 512 字节时，命令和等待时间占比很高。

#### 卡内部擦写

NAND Flash 的写入不是简单覆盖，通常涉及：

```
逻辑块映射
  |
准备空闲物理块
  |
擦除
  |
编程
  |
映射表更新
```

因此连续写可能突然出现几十毫秒甚至数百毫秒的尾延迟。

#### 文件系统元数据

一个小文件写入可能触发：

- FAT 表更新
- 目录项更新
- 文件长度更新
- 时间戳更新
- FSInfo 更新
- 数据区写入

因此应用层一次 `f_write()` 不一定对应一次块设备写。

### 6.4 内存开销

典型 DMA 驱动内存：

|项目|大小|
|---|---|
|单块 DMA Buffer|512 B|
|8 块 DMA Buffer|4 KB|
|32 块 DMA Buffer|16 KB|
|控制器状态对象|100~300 B|
|RTOS 互斥锁和事件|视系统实现|
|FatFs 工作区|通常数百字节到数 KB|
|文件对象|通常几十到数百字节|

推荐缓冲区大小：

- 低内存产品：`1~4 KB`
- 采集和日志：`8~32 KB`
- 高吞吐数据记录：双缓冲或环形缓冲区

### 6.5 性能优化收益

|优化方式|典型收益|
|---|---|
|单块改为多块传输|2~10 倍|
|轮询改为 DMA|CPU 占用下降 50%~95%|
|4-bit 替代 1-bit|总线带宽理论提升 4 倍|
|预分配连续文件|随机写延迟下降 20%~80%|
|双缓冲采集|降低实时任务阻塞概率|
|Cache 正确维护|消除偶发数据错误|
|批量 `f_write()`|小块写吞吐提升 2~20 倍|
|延迟 `f_sync()`|降低同步开销，但掉电风险增大|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否要求高吞吐？
├─ 否
│  ├─ GPIO 很少？
│  │  └─ 是 -> SPI 模式
│  └─ 有原生 SDIO？
│     └─ 是 -> SDIO 1-bit 或 4-bit
└─ 是
   ├─ MCU 有 SDIO/SDMMC？
   │  ├─ 否 -> SPI + DMA，降低吞吐目标
   │  └─ 是
   │     ├─ PCB 信号质量是否满足高速？
   │     │  ├─ 否 -> 低频 SDIO 4-bit
   │     │  └─ 是 -> SDMMC 4-bit + DMA
   │     └─ 是否有实时采集？
   │        ├─ 是 -> DMA + 双缓冲 + 后台写任务
   │        └─ 否 -> DMA + 普通块设备接口
```

```
是否要求掉电后数据一致？
├─ 否 -> 批量缓存写入，降低同步频率
└─ 是
   ├─ 数据是否允许丢失一个批次？
   │  ├─ 是 -> 周期性 f_sync + 日志校验
   │  └─ 否 -> 每条事务同步或使用事务日志
   └─ 是否允许文件系统损坏？
      ├─ 否 -> 掉电检测 + 卸载 + 日志恢复
      └─ 是 -> 仅依赖正常关机流程风险较高
```

### 7.2 场景选型

|场景|需求|方案|理由|
|---|---|---|---|
|参数导入导出|低吞吐、可维护|SPI 或 SDIO 1-bit + FatFs|成本低，访问量小|
|黑盒日志|连续写、不能阻塞采集|SDMMC 4-bit + DMA + 双缓冲|吞吐高，降低实时任务阻塞|
|OTA 固件包|大文件顺序读|SDMMC 4-bit + DMA + CRC|读取吞吐高，适合镜像校验|
|图片或音频播放|连续读、低抖动|多块读 + 大缓存|减少命令开销和卡延迟影响|
|高可靠配置存储|小数据、强一致性|不建议直接依赖 SD 卡|优先 FRAM、EEPROM 或 NOR|
|工业数据归档|文件系统、掉电恢复|FatFs + 预分配 + 日志索引|兼顾容量和恢复能力|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：分离协议层、控制器层和文件系统层

推荐目录：

```
drivers/sd/
├── sd_card.c
├── sd_card.h
├── sd_protocol.c
├── sd_protocol.h
├── sdmmc_port.c
├── sdmmc_port.h
├── sd_dma.c
└── sd_error.c
```

不要把以下内容混在一个函数中：

- GPIO 配置
- CMD17 发送
- DMA 配置
- FatFs 文件操作
- 日志打印
- 错误恢复

### 原则二：所有等待都必须有超时

错误实现：

```
while ((SDMMC->STA & SDMMC_STA_RXDAVL) == 0U)
{
}
```

正确实现：

```
static int sd_wait_flag(uint32_t mask,
                        uint32_t timeout_ms)
{
    uint32_t start = sd_get_tick_ms();

    while ((SDMMC->STA & mask) == 0U)
    {
        if ((sd_get_tick_ms() - start) >= timeout_ms)
        {
            return SD_ERR_TIMEOUT;
        }
    }

    return SD_OK;
}
```

### 原则三：传输长度和地址都要做边界校验

```
static int sd_validate_range(const sd_card_t *card,
                             uint32_t lba,
                             uint32_t count)
{
    if (count == 0U)
    {
        return SD_ERR_INVALID_ARG;
    }

    if ((uint64_t)lba + count > card->block_count)
    {
        return SD_ERR_OUT_OF_RANGE;
    }

    return SD_OK;
}
```

### 原则四：写入完成必须等待卡退出 Busy

```
static int sd_wait_not_busy(sd_card_t *card,
                            uint32_t timeout_ms)
{
    uint32_t start = sd_get_tick_ms();

    while (sd_hw_dat0_is_low(card))
    {
        if ((sd_get_tick_ms() - start) >= timeout_ms)
        {
            return SD_ERR_WRITE_TIMEOUT;
        }
    }

    return SD_OK;
}
```

### 原则五：热插拔必须有明确状态机

```
CARD_REMOVED
  |
检测到插卡
  |
DEBOUNCE
  |
上电
  |
初始化
  |
READY
  |
检测拔卡
  |
停止 DMA
  |
复位控制器
  |
卸载文件系统
  |
CARD_REMOVED
```

### 8.2 选型决策矩阵

|需求|SPI|SDIO 1-bit|SDIO 4-bit|SDMMC + DMA|
|---|---|---|---|---|
|低成本|5|4|3|3|
|高吞吐|2|3|4|5|
|软件简单|5|3|3|2|
|CPU 占用低|2|3|4|5|
|低风险量产|4|4|4|4|
|实时采集|2|3|4|5|

### 8.3 工业级编码规范

- 所有接口使用显式宽度类型：`uint32_t`、`uint64_t`。
- 不直接依赖 `int` 的位宽。
- LBA 转物理地址时使用 `uint64_t` 中间结果。
- 不在 ISR 中做文件系统操作。
- 不在持锁状态下打印大量日志。
- 错误码必须区分：参数错误、无卡、命令错误、数据错误、超时、写保护。
- 记录累计错误次数和最近一次错误上下文。
- DMA Buffer 必须明确其 Cache 属性、对齐要求和所有权。
- 对用户输入的 LBA、块数、文件大小做整数溢出检查。
- 对生产设备禁用无限重试。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：SDSC 地址计算错误

### 错误代码

```
uint32_t address = lba;
sd_send_command(CMD17, address, SD_RESP_R1, &response);
```

### 根因

SDSC 使用字节地址，SDHC/SDXC 使用块地址。

### 正确实现

```
uint32_t address = card->block_addressing
                 ? lba
                 : lba * 512U;
```

### 风险影响

- 读取错误扇区。
- 小容量卡表现正常，高容量卡表现正常，导致问题难以发现。
- 可能出现文件系统静默损坏。

---

## 9.2 错误二：DMA 与 D-Cache 不一致

### 错误代码

```
memset(rx_buffer, 0, 512);
start_sd_dma_rx(rx_buffer, 512);
wait_dma_done();

process_data(rx_buffer);
```

### 根因

CPU 可能从 Cache 读取旧数据。DMA 写入 RAM 后，Cache 未失效。

### 正确实现

```
sd_dma_prepare_rx(rx_buffer, 512);
start_sd_dma_rx(rx_buffer, 512);
wait_dma_done();
sd_dma_complete_rx(rx_buffer, 512);
process_data(rx_buffer);
```

### 风险影响

- 数据偶发错误。
- 低负载时正常，高负载或 Cache 开启后异常。
- 错误具有随机性，很难通过简单功能测试发现。

---

## 9.3 错误三：只等待数据响应，不等待卡写完成

### 错误代码

```
send_write_data(block);
check_data_response();
return SD_OK;
```

### 根因

数据响应只代表卡接受了该数据块，卡可能仍在内部编程。

### 正确实现

```
send_write_data(block);

if (sd_wait_not_busy(card, SD_WRITE_TIMEOUT_MS) != SD_OK)
{
    return SD_ERR_WRITE_TIMEOUT;
}

return SD_OK;
```

### 风险影响

- 连续写时下一条命令被拒绝。
- 文件系统认为写入成功，但数据尚未稳定。
- 掉电时更容易出现 FAT 或目录损坏。

---

## 9.4 错误四：无限等待硬件标志

### 错误代码

```
while ((SDMMC->STA & SDMMC_STA_DATAEND) == 0U)
{
}
```

### 根因

以下情况都可能导致标志永远不出现：

- 卡被拔出。
- CMD/DAT 线短路。
- DMA 地址非法。
- 时钟配置错误。
- 控制器状态机卡死。
- 中断标志未清除。

### 正确实现

```
uint32_t start = sd_get_tick_ms();

while ((SDMMC->STA & SDMMC_STA_DATAEND) == 0U)
{
    uint32_t status = SDMMC->STA;

    if ((status & SDMMC_ERROR_MASK) != 0U)
    {
        sd_controller_abort();
        return SD_ERR_DATA;
    }

    if ((sd_get_tick_ms() - start) > SD_DATA_TIMEOUT_MS)
    {
        sd_controller_abort();
        return SD_ERR_TIMEOUT;
    }
}
```

### 风险影响

- 阻塞系统任务。
- 看门狗复位。
- 驱动锁死后无法恢复。
- 影响其他实时任务。

---

## 9.5 错误五：以为 `f_write()` 后数据已经落盘

### 错误代码

```
f_write(&file, data, length, &written);
/* 直接认为掉电后数据可靠 */
```

### 根因

FatFs 和 SD 卡内部可能仍有缓存、FAT 更新或 Flash 编程操作。

### 正确实现

```
if (f_write(&file, data, length, &written) != FR_OK)
{
    return APP_ERR_FS_WRITE;
}

if (written != length)
{
    return APP_ERR_SHORT_WRITE;
}

if (f_sync(&file) != FR_OK)
{
    return APP_ERR_FS_SYNC;
}
```

### 风险影响

- 突然掉电后丢失最近数据。
- 文件长度和数据区不一致。
- FAT 链损坏。

---

## 9.6 错误六：多个任务直接访问 FatFs 或 SD 控制器

### 错误代码

```
void logger_task(void *arg)
{
    f_write(&log_file, data, size, &written);
}

void update_task(void *arg)
{
    f_open(&fw_file, "fw.bin", FA_READ);
}
```

### 根因

- FatFs 配置可能未启用重入保护。
- 底层 SD 控制器通常只支持一个活动事务。
- 文件系统和底层设备锁的层级不清晰。

### 正确实现

```
多个业务任务
      |
存储服务任务
      |
FatFs
      |
SD 块设备互斥锁
      |
SDMMC DMA
```

### 风险影响

- 文件系统内部数据结构被破坏。
- DMA Buffer 被覆盖。
- 任务之间发生优先级反转或长时间阻塞。

---

## 10. 多机制组合使用方案

## 10.1 推荐架构：采集任务 + 环形缓冲 + 存储任务

```
高速采集任务
      |
固定大小记录
      |
无锁/单生产者环形缓冲
      |
存储任务
      |
批量拼接为 8~32 KB
      |
FatFs f_write
      |
f_sync 周期同步
      |
SDMMC 4-bit + DMA
```

### 10.1.1 环形缓冲框架

```
#define LOG_QUEUE_DEPTH  16U
#define LOG_BLOCK_SIZE   4096U

typedef struct
{
    uint8_t data[LOG_BLOCK_SIZE];
    uint32_t length;
} log_block_t;

typedef struct
{
    log_block_t queue[LOG_QUEUE_DEPTH];
    uint32_t write_index;
    uint32_t read_index;
    os_mutex_t lock;
    os_semaphore_t items;
    os_semaphore_t spaces;
} log_queue_t;
```

生产者：

```
int log_queue_put(log_queue_t *queue,
                  const void *data,
                  uint32_t length,
                  uint32_t timeout_ms)
{
    if ((queue == NULL) ||
        (data == NULL) ||
        (length == 0U) ||
        (length > LOG_BLOCK_SIZE))
    {
        return LOG_ERR_INVALID_ARG;
    }

    if (os_sem_take(&queue->spaces, timeout_ms) != OS_OK)
    {
        return LOG_ERR_FULL;
    }

    if (os_mutex_lock(&queue->lock, timeout_ms) != OS_OK)
    {
        os_sem_give(&queue->spaces);
        return LOG_ERR_LOCK;
    }

    log_block_t *block =
        &queue->queue[queue->write_index];

    memcpy(block->data, data, length);
    block->length = length;

    queue->write_index =
        (queue->write_index + 1U) % LOG_QUEUE_DEPTH;

    os_mutex_unlock(&queue->lock);
    os_sem_give(&queue->items);

    return LOG_OK;
}
```

消费者：

```
int log_queue_get(log_queue_t *queue,
                  log_block_t *block,
                  uint32_t timeout_ms)
{
    if ((queue == NULL) || (block == NULL))
    {
        return LOG_ERR_INVALID_ARG;
    }

    if (os_sem_take(&queue->items, timeout_ms) != OS_OK)
    {
        return LOG_ERR_EMPTY;
    }

    if (os_mutex_lock(&queue->lock, timeout_ms) != OS_OK)
    {
        os_sem_give(&queue->items);
        return LOG_ERR_LOCK;
    }

    *block = queue->queue[queue->read_index];

    queue->read_index =
        (queue->read_index + 1U) % LOG_QUEUE_DEPTH;

    os_mutex_unlock(&queue->lock);
    os_sem_give(&queue->spaces);

    return LOG_OK;
}
```

### 10.1.2 组合机制的价值

|机制|解决的问题|
|---|---|
|DMA|降低 CPU 搬运开销|
|多块传输|提升连续吞吐|
|环形缓冲|解耦采集实时性和卡延迟|
|存储服务任务|统一文件系统访问|
|周期性 `f_sync`|平衡一致性和性能|
|CRC/序号|检测记录缺失和损坏|
|看门狗/超时|防止永久阻塞|
|错误统计|支持现场诊断|

---

## 11. 工业级实际案例分析

## 11.1 案例一：电机控制器黑盒数据记录

### 需求

- 采样频率：10 kHz。
- 每条记录：64 字节。
- 原始数据率：

```
10,000 × 64 = 640 KB/s
```

- 不能因为 SD 卡偶发 100 ms 写延迟而阻塞控制环。
- 掉电允许丢失不超过 1 秒数据。

### 架构设计

```
ADC/DMA
  |
采集 ISR
  |
双缓冲
  |
环形队列：至少 1 秒容量
  |
存储任务
  |
每次写 32 KB
  |
预分配文件
  |
每 500 ms f_sync
```

所需最小缓存：

```
640 KB/s × 1 s = 640 KB
```

工程上建议配置：

```
1~2 MB RAM 或外部 SRAM/SDRAM
```

核心代码：

```
#define RECORD_SIZE             64U
#define SAMPLE_RATE             10000U
#define STORAGE_RATE            (RECORD_SIZE * SAMPLE_RATE)
#define LOG_BUFFER_BYTES        (1024U * 1024U)

static uint8_t log_buffer[LOG_BUFFER_BYTES]
    __attribute__((aligned(32), section(".noncacheable")));

static volatile uint32_t log_head;
static volatile uint32_t log_tail;

void adc_dma_half_complete_isr(void)
{
    const uint8_t *record = adc_dma_get_half_buffer();

    /*
     * ISR 只复制或提交固定长度记录，
     * 不执行文件系统和 SD 卡访问。
     */
    ring_push_isr(record, RECORD_SIZE);
}

void storage_task(void *argument)
{
    uint8_t write_buffer[32U * 1024U]
        __attribute__((aligned(32)));

    uint32_t last_sync = os_tick();

    for (;;)
    {
        uint32_t length = ring_pop_batch(write_buffer,
                                         sizeof(write_buffer),
                                         100U);

        if (length != 0U)
        {
            UINT written;

            if (f_write(&log_file,
                        write_buffer,
                        length,
                        &written) != FR_OK ||
                written != length)
            {
                storage_record_error(STORAGE_ERR_WRITE);
            }
        }

        if ((os_tick() - last_sync) >= 500U)
        {
            if (f_sync(&log_file) != FR_OK)
            {
                storage_record_error(STORAGE_ERR_SYNC);
            }

            last_sync = os_tick();
        }
    }
}
```

### 设计要点

- 采集 ISR 不直接写 SD。
- 文件必须提前扩容或预分配。
- 每条记录包含序号和 CRC。
- 环形缓冲区必须能容纳最坏写延迟，而不是平均写延迟。
- 记录文件应采用追加写，减少随机定位。

---

## 11.2 案例二：现场设备 OTA 升级

### 需求

- 固件镜像存放在 SD 卡。
- 镜像大小约 8 MB。
- 需要完整性校验。
- 升级失败时设备不能变砖。

### 架构

```
SD 卡
  |
FatFs 顺序读取
  |
分块 SHA-256
  |
镜像签名校验
  |
写入备用 Flash 分区
  |
Flash 完整性校验
  |
更新 Boot 标志
  |
重启
```

核心代码框架：

```
#define OTA_READ_SIZE  (32U * 1024U)

int ota_program_from_sd(const char *path,
                        const uint8_t expected_hash[32])
{
    FIL file;
    uint8_t buffer[OTA_READ_SIZE]
        __attribute__((aligned(32)));
    UINT read_size;
    sha256_ctx_t hash;
    uint32_t flash_offset = 0U;
    int rc = OTA_OK;

    if (f_open(&file, path, FA_READ) != FR_OK)
    {
        return OTA_ERR_OPEN;
    }

    sha256_init(&hash);

    while (true)
    {
        if (f_read(&file,
                   buffer,
                   sizeof(buffer),
                   &read_size) != FR_OK)
        {
            rc = OTA_ERR_READ;
            break;
        }

        if (read_size == 0U)
        {
            break;
        }

        sha256_update(&hash, buffer, read_size);

        if (flash_program_staging(flash_offset,
                                  buffer,
                                  read_size) != 0)
        {
            rc = OTA_ERR_FLASH;
            break;
        }

        flash_offset += read_size;
    }

    if (rc == OTA_OK)
    {
        uint8_t actual_hash[32];

        sha256_final(&hash, actual_hash);

        if (memcmp(actual_hash, expected_hash, 32U) != 0)
        {
            rc = OTA_ERR_HASH;
        }
    }

    f_close(&file);
    return rc;
}
```

### 设计要点

- SD 卡文件名、大小和内容都不能直接信任。
- 不能只校验 CRC32；固件升级应使用 SHA-256 和数字签名。
- 写入主 Flash 前，镜像必须完成完整校验。
- Bootloader 应使用 A/B 分区或回滚标志。
- SD 卡拔出时必须终止 DMA 并关闭文件。
- 升级过程中应禁止进入低功耗或复位路径。

---

## 11.3 案例三：工业网关离线数据归档

### 需求

- 网络中断时缓存数据。
- 网络恢复后上传历史文件。
- 多任务同时产生不同数据。
- 需要限制单文件大小，避免超大目录和长时间恢复。

### 方案

```
多个采集模块
  |
统一消息队列
  |
归档服务任务
  |
按时间生成文件：
  /log/2025/03/08/120000.bin
  |
每个文件 16~64 MB
  |
文件头 + 记录序号 + CRC
  |
周期同步
```

文件头示例：

```
typedef struct
{
    uint32_t magic;
    uint16_t version;
    uint16_t header_size;
    uint32_t sequence;
    uint64_t start_timestamp;
    uint32_t record_size;
    uint32_t reserved;
    uint32_t header_crc;
} archive_header_t;
```

设计要点：

- 文件按时间切分，降低恢复和上传粒度。
- 记录使用定长结构，便于断点恢复。
- 维护最后确认上传位置。
- 删除策略必须避免删除未上传数据。
- 目录层级和文件数量需要限制。

---

## 12. 高频问题深度答疑

### 问题一：SDIO 和 SDMMC 是不是同一个东西？

从协议角度看，它们都可以实现 SD 原生总线访问；从控制器命名看，芯片厂商可能区分：

- `SDIO`：较早的 SD/SDIO 控制器命名。
- `SDMMC`：更完整的 SD/MMC 控制器命名。
- 某些 MCU 的 SDMMC 支持更好的 DMA、FIFO、时钟控制和多媒体卡协议。

实际选型应以芯片 Reference Manual 为准，重点查看：

- 是否支持 4-bit。
- 是否支持 SDHC/SDXC。
- 是否支持 DMA。
- 是否有 FIFO。
- 是否支持硬件数据超时。
- 是否支持 IDMA/链式描述符。
- 是否能在 Cache 开启时稳定工作。

---

### 问题二：为什么 4-bit 理论速度很高，实际只有几 MB/s？

主要原因包括：

1. 卡内部写入速度有限。
2. 单块命令开销高。
3. 文件系统产生大量元数据更新。
4. `f_sync()` 频繁调用。
5. 数据未按大块连续写入。
6. 卡内部垃圾回收造成尾延迟。
7. DMA 配置和 Cache 维护带来额外开销。
8. 总线时钟、采样边沿或信号质量限制了实际频率。

首先应区分：

```
裸块设备吞吐
文件系统顺序吞吐
文件系统随机吞吐
应用端到端吞吐
```

不能用 `f_write()` 的结果直接判断 SDMMC 总线性能。

---

### 问题三：是否应该始终使用 `CMD18/CMD25`？

不应绝对化。

适合多块传输的情况：

- 连续读写。
- 数据量至少几个 KB。
- DMA 已经配置完成。
- 应用能够准备连续 Buffer。

单块传输更合适的情况：

- 少量随机访问。
- 发生错误后需要最小化重试范围。
- 访问地址不连续。
- 驱动实现处于早期调试阶段。

工业实现通常是：

```
小于阈值 -> 单块
大于等于阈值 -> 多块
```

阈值可通过实测确定，常见为 `4~16` 个块。

---

### 问题四：SD 卡能否作为实时控制系统的主存储？

不适合作为严格实时路径中的同步存储介质。

原因：

- 写延迟非确定。
- 卡内部垃圾回收不可控。
- 不同卡的尾延迟差异很大。
- 掉电时写入一致性难以保证。
- 热插拔和接触不良会引起瞬态错误。

更合理的架构是：

```
实时控制路径
  |
RAM / FRAM / NOR
  |
后台异步写入 SD 卡
```

SD 卡适合作为大容量归档介质，而不是硬实时数据结构的唯一副本。

---

### 问题五：为什么文件系统偶发损坏，但裸块读写测试正常？

常见原因：

- 未调用 `f_sync()` 或正常卸载。
- 写操作过程中掉电。
- 多任务并发访问 FatFs。
- DMA Buffer Cache 不一致。
- 文件系统工作区被栈溢出覆盖。
- 设备移除时仍有活动 DMA。
- SD 卡供电跌落。
- 卡忙超时后驱动错误恢复不完整。
- 未检查 `f_write()` 返回的实际写入字节数。

应建立分层测试：

```
SD 电气测试
  |
裸命令测试
  |
块设备顺序读写
  |
块设备随机读写
  |
FatFs 文件测试
  |
异常掉电测试
  |
热插拔测试
  |
长期压力测试
```

---

### 问题六：写超时应该重试还是立即失败？

取决于错误类别。

适合重试：

- CRC 错误。
- 瞬时总线错误。
- 检测到卡仍在 Busy，但未超过总超时。
- 低概率传输错误。

不适合盲目重试：

- 地址越界。
- 写保护。
- 非法命令。
- 卡被拔出。
- 控制器状态机已损坏。
- 电源不稳定。

推荐策略：

```
首次失败
  |
读取卡状态和控制器状态
  |
清除错误并停止 DMA
  |
重新初始化控制器
  |
最多重试 1~3 次
  |
仍失败 -> 标记介质故障并通知上层
```

---

## 13. 课程核心总结

### 13.1 核心要点

1. **SD 卡驱动应当是块设备驱动，不应和文件系统耦合。**
2. **初始化必须区分 SDSC 与 SDHC/SDXC 的地址模式。**
3. **SDIO/SDMMC 4-bit + DMA 是大多数高吞吐 MCU 产品的首选方案。**
4. **DMA + D-Cache 一致性是 Cortex-M7 等平台的关键风险点。**
5. **写数据响应成功不等于卡已经完成内部编程。**
6. **所有硬件等待都必须有超时和错误退出路径。**
7. **实时采集必须使用缓存、双缓冲或环形队列隔离 SD 卡长尾延迟。**
8. **文件系统掉电一致性需要同步策略、日志设计和恢复机制共同保障。**
9. **SD 卡不适合承担严格硬实时任务的同步存储职责。**
10. **必须分别测试裸块设备、文件系统和端到端应用性能。**

### 13.2 性能排序

在相同卡和时钟条件下，通常为：

```
SDMMC 4-bit + DMA + 多块传输
    >
SDIO 4-bit + DMA
    >
SDIO 1-bit + DMA
    >
SPI + DMA
    >
SPI 轮询
```

对于小块随机访问，文件系统和卡内部延迟可能让上述排序不再明显。

### 13.3 通用选型结论

- **低速、低成本、GPIO 紧张**：SPI。
- **中等吞吐、实现复杂度可控**：SDIO 1-bit 或 4-bit。
- **高吞吐、日志和升级**：SDMMC 4-bit + DMA。
- **严格实时采集**：RAM/FRAM/NOR 做实时缓存，SD 卡后台归档。
- **强一致性参数**：不要把 SD 卡作为唯一参数存储介质。
- **高可靠升级**：SD 卡读取 + Hash + 签名校验 + A/B Flash。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐方案|关键配置|
|---|---|---|
|参数导入导出|SPI + FatFs|低频、简单重试|
|固件升级|SDMMC 4-bit + DMA|32 KB 读取、SHA-256|
|黑盒日志|SDMMC 4-bit + DMA|双缓冲、预分配、周期同步|
|音频播放|SDMMC 4-bit|大块多块读、预读缓存|
|低功耗设备|SPI 或 SDIO 1-bit|降频、断电控制|
|高可靠数据归档|SDMMC + 服务任务|文件切分、CRC、恢复索引|

### 14.2 命令速查表

|操作|典型命令序列|
|---|---|
|初始化|`CMD0 -> CMD8 -> CMD55 + ACMD41`|
|获取卡身份|`CMD2 -> CMD3 -> CMD9`|
|选卡|`CMD7`|
|配置 4-bit|`CMD55 -> ACMD6`|
|单块读取|`CMD17`|
|多块读取|`CMD18 -> CMD12`|
|单块写入|`CMD24`|
|多块写入|`CMD25 -> STOP token`|
|读取卡状态|`CMD13`|

### 14.3 错误码建议

```
typedef enum
{
    SD_OK = 0,
    SD_ERR_INVALID_ARG,
    SD_ERR_NO_CARD,
    SD_ERR_NOT_INITIALIZED,
    SD_ERR_TIMEOUT,
    SD_ERR_CMD,
    SD_ERR_DATA,
    SD_ERR_CRC,
    SD_ERR_BUSY,
    SD_ERR_WRITE_PROTECTED,
    SD_ERR_OUT_OF_RANGE,
    SD_ERR_CARD_STATUS,
    SD_ERR_DMA,
    SD_ERR_CONTROLLER,
    SD_ERR_UNSUPPORTED
} sd_status_t;
```

### 14.4 超时建议

|操作|建议超时|
|---|---|
|命令响应|10~100 ms|
|单块读|100~500 ms|
|多块读|按数据量计算，至少 1 s|
|单块写|250~1000 ms|
|多块写|1~5 s|
|初始化|1~2 s|
|卡 Busy 等待|依据卡规格，至少覆盖最坏擦写延迟|

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

- 能否画出 SD 卡从上电到 Transfer 状态的初始化状态机？
- 能否解释 `CMD8`、`ACMD41`、`CMD3` 和 `CMD7` 的作用？
- 能否正确区分 SDSC 与 SDHC 的地址传递方式？
- 能否从 CSD 解析卡容量？
- 能否实现单块和多块读写？
- 能否解释 `CMD18` 结束时为什么需要 `CMD12`？
- 能否说明写数据响应和卡 Busy 的区别？
- 能否为 DMA 读写设计正确的 Cache 维护流程？
- 能否处理 DMA 超时、CRC 错误、卡移除和写保护？
- 能否设计多个 RTOS 任务访问同一 SD 卡的同步方案？
- 能否解释为什么 SD 卡不能直接放入硬实时控制路径？
- 能否设计带环形缓冲、批量写入和周期同步的日志系统？
- 能否通过裸块设备测试区分总线问题和文件系统问题？
- 能否设计异常掉电后的文件恢复策略？
- 能否为 OTA 场景增加 Hash、签名和回滚机制？

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：SPI 模式识别卡

要求：

- 实现 `CMD0`、`CMD8`、`CMD55`、`ACMD41`。
- 读取 OCR、CID、CSD。
- 解析容量和卡类型。
- 使用逻辑分析仪确认命令帧。

验收指标：

- 能识别至少一张 SDSC 和一张 SDHC 卡。
- 初始化失败必须返回明确错误码。
- 所有等待都有超时。

#### 任务二：SDIO 1-bit 单块读写

要求：

- 实现 `CMD17` 和 `CMD24`。
- 完成 512 字节模式读写。
- 增加 CRC、地址越界和写保护检测。

验收指标：

- 连续读写 10 万个块无数据错误。
- 读回数据与写入数据逐字节一致。
- 模拟卡移除后 500 ms 内返回错误。

#### 任务三：SDMMC 4-bit + DMA

要求：

- 配置 DMA。
- 实现 `CMD18` 和 `CMD25`。
- 支持 4 KB、32 KB、128 KB 连续读写。
- 统计吞吐和 CPU 占用。

验收指标：

- 连续读取吞吐达到目标平台理论值的 60% 以上。
- CPU 占用显著低于轮询版本。
- DMA 错误能够恢复到可用状态。

#### 任务四：FatFs 块设备适配

要求：

- 完成 `disk_initialize()`。
- 完成 `disk_read()`、`disk_write()`。
- 完成 `disk_ioctl()`。
- 支持挂载、创建文件、追加写和同步。

验收指标：

- 能通过 PC 读取卡内生成文件。
- 反复创建、删除、追加文件无文件系统错误。
- `f_write()` 返回值和实际写入长度均被检查。

#### 任务五：工业日志系统

要求：

- 实现采集任务、环形缓冲和存储任务。
- 记录序号、时间戳和 CRC。
- 支持文件预分配。
- 模拟 100 ms、500 ms 和 1 s 的卡写延迟。

验收指标：

- 实时采集任务不直接阻塞在 SD 写入上。
- 可检测丢记录。
- 缓冲区溢出有明确统计。
- 异常掉电后能够定位最后一条有效记录。

#### 任务六：异常恢复与可靠性测试

测试项目：

```
连续满盘写入
随机块读写
随机文件创建删除
高低温测试
低电压测试
写入过程中掉电
写入过程中拔卡
DMA 中断丢失
CMD/DAT 线干扰
看门狗复位
文件系统重新挂载
```

### 16.2 性能测试方法

应分别测试以下指标：

#### 裸块设备顺序读

```
读取 64 MB
块大小：32 KB
记录总耗时
吞吐 = 总字节数 / 总耗时
```

#### 裸块设备随机写

```
随机选择 4 KB 对齐 LBA
重复 10,000 次
统计平均值、P95、P99、最大延迟
```

#### 文件系统写入

分别测试：

- 512 B 写入。
- 4 KB 写入。
- 32 KB 写入。
- 1 MB 顺序写。
- 开启和关闭 `f_sync()`。
- 预分配与非预分配。

重点指标：

```
平均吞吐
P95 延迟
P99 延迟
最大写延迟
CPU 占用
峰值 RAM
掉电后恢复时间
```

不能只看平均吞吐，工业实时系统更应关注：

```
最大阻塞时间
P99 写延迟
缓冲区峰值占用
错误恢复耗时
```

### 16.3 进阶学习方向

- SD Physical Layer Specification。
- SDIO/SDMMC 控制器寄存器和 DMA 章节。
- FatFs 源码：`diskio.c`、FAT 链管理、目录项更新和同步机制。
- Cortex-M Cache、MPU 和 DMA 一致性。
- NAND Flash FTL、垃圾回收和写放大。
- 文件系统日志、掉电保护和事务一致性。
- 高可靠存储：A/B 数据区、双备份、CRC、版本号和回滚。
- Secure Boot、固件签名和 OTA 安全链路。
- SD 卡信号完整性、阻抗控制、电源完整性和 ESD/EMC 设计。
- 使用 Tracealyzer、逻辑分析仪和性能计数器构建端到端性能画像。