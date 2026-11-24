
## 1. 学习目标

### 理解

- 理解 NAND Flash 的阵列组织：Die、Plane、Block、Page、目标页。
- 理解 NAND 的基本约束：**只能按页编程、按块擦除、位状态只能由 1 变 0**。
- 理解 Raw NAND、Managed NAND、SPI NAND、eMMC、UFS 的边界与适用场景。
- 理解 ECC、坏块管理、磨损均衡、垃圾回收和掉电保护之间的关系。

### 掌握

- 掌握 NAND Flash 的读、编程、擦除命令流程。
- 掌握 ONFI 参数页、设备 ID、状态寄存器、时序参数的解析。
- 掌握页缓存、随机读、连续读、Program/Erase 等典型操作。
- 掌握工厂坏块和运行时坏块的识别与管理。

### 精通

- 能分析 ECC 强度、R/B# 信号、NAND 时序和并行度对性能的影响。
- 能定位写放大、ECC 失败、坏块增长、掉电破坏和数据不一致问题。
- 能设计适用于 MCU、RTOS、Bootloader 和嵌入式 Linux 的 NAND 存储层。

### 能够设计

- 能设计 Raw NAND 的底层驱动、FTL 或日志型文件系统适配层。
- 能根据容量、延迟、可靠性、成本和功耗选择 NAND 方案。
- 能设计包含 ECC、坏块管理、掉电恢复和寿命监控的工业级存储架构。

---

## 2. 前置要求

### 知识要求

- C 语言指针、位操作、结构体、内存映射 I/O。
- MCU DMA、中断、定时器和 GPIO 基本原理。
- SPI、并行总线、异步时序。
- RTOS 任务、互斥锁、信号量、队列和临界区。
- CRC、ECC、日志、文件系统和基本存储抽象。
- Linux MTD、UBI、UBIFS 基本概念。

### 技能要求

- 能阅读芯片数据手册和时序图。
- 能使用逻辑分析仪观察 NAND 命令、地址、数据和 R/B#。
- 能编写 HAL 驱动并处理超时、错误码和 DMA 缓冲区。
- 能进行掉电测试、坏块注入、写放大和寿命测试。
- 能使用 JTAG、Trace、串口日志和示波器定位底层问题。

---

## 3. 技术概述

NAND Flash 是一种非易失性存储器。其存储单元通过浮栅或电荷俘获层保存电子数量，利用阈值电压区间表示逻辑状态。

NAND 的典型层次为：

```
NAND Device
└── Die
    └── Plane
        └── Block
            └── Page
                ├── Main Data Area
                └── Spare/OOB Area
```

常见粒度：

- **Page**：读取和编程的基本单位，常见 2 KiB、4 KiB、8 KiB、16 KiB。
- **Block**：擦除的基本单位，常见每块 64、128、256 页。
- **OOB/Spare**：每页附加区域，用于 ECC、坏块标记、逻辑地址和元数据。
- **Die**：独立的 NAND 芯片阵列，可以通过多 Die 并发提升吞吐。

### 技术分支

|分类维度|方案|
|---|---|
|存储单元|SLC、MLC、TLC、QLC|
|接口|ONFI 并行 NAND、Toggle NAND、SPI NAND|
|管理方式|Raw NAND、Managed NAND|
|可靠性机制|主控 ECC、芯片内部 ECC、LDPC|
|典型封装|TSOP、BGA、MCP|
|使用层|Bootloader、MTD、UBI、文件系统、数据库|

---

## 4. 核心特性横向对比

|维度|SLC|MLC|TLC|QLC|
|---|---|---|---|---|
|每单元位数|1|2|3|4|
|每单元状态数|2|4|8|16|
|P/E 寿命|约 50,000~100,000 次|约 3,000~10,000 次|约 1,000~3,000 次|约 100~1,000 次|
|读取延迟|低|中|中高|高|
|编程延迟|低|中|高|更高|
|ECC 要求|较低|较高|高|很高，通常 LDPC|
|单位容量成本|高|中|低|最低|
|工业可靠性|高|中高|中|低于 SLC|
|典型用途|Boot、日志、参数|工业存储|SSD、eMMC|大容量消费级存储|

|方案|主控责任|优点|风险/限制|典型场景|
|---|---|---|---|---|
|Raw NAND|ECC、坏块、磨损均衡、映射|成本低、可控性强|软件复杂度高|Linux 工业设备、定制存储|
|SPI NAND|命令协议简单，通常带内部 ECC|MCU 易接入、引脚少|内部管理能力依器件而异|MCU 外部扩展存储|
|eMMC|内部 FTL、ECC、坏块管理|软件接近块设备|内部行为不可控，寿命透明度低|Linux、Android、网关|
|UFS|高速串行、多队列|高性能、低 CPU 占用|协议和硬件复杂|高端嵌入式设备|
|NOR Flash|可随机读取、XIP|读取延迟低，可靠|容量和成本不利|Boot、代码、参数|

---

## 5. 底层原理与功能特性深度解析

### 5.1 NAND 单元状态

浮栅 NAND 通过控制栅极施加电压，使电子隧穿进入或离开浮栅。电子数量改变后，晶体管阈值电压发生变化。

以 SLC 为例：

```
擦除后：逻辑 1，阈值电压低
编程后：逻辑 0，阈值电压高
```

NAND 编程通常通过 ISPP：

```
Incremental Step Pulse Programming
└── 施加编程脉冲
    └── 验证阈值电压
        ├── 未达到目标：增加脉冲电压
        └── 达到目标：停止该页编程
```

MLC/TLC/QLC 需要区分更多阈值电压窗口，因此：

- 编程时间增加。
- 读取参考电压更复杂。
- 邻近单元干扰更明显。
- 数据保持时间和 P/E 寿命下降。
- ECC 纠错能力要求提高。

---

### 5.2 Page Read 流程

典型 ONFI NAND 读取流程：

```
1. CLE = 1，发送 READ PAGE 命令 0x00
2. CLE = 0，发送列地址
3. 发送行地址
4. 发送 READ START 命令 0x30
5. 等待 R/B# 从 Busy 变为 Ready
6. 读取数据和 OOB
```

伪代码：

```
typedef enum {
    NAND_OK = 0,
    NAND_E_TIMEOUT = -1,
    NAND_E_STATUS = -2,
    NAND_E_ECC = -3,
} nand_status_t;

int nand_read_page(uint32_t row, uint8_t *main, uint8_t *oob,
                   uint32_t timeout_us)
{
    if (main == NULL || oob == NULL) {
        return NAND_E_STATUS;
    }

    nand_cle(1);
    nand_write_cmd(0x00);
    nand_cle(0);

    nand_write_col_addr(0);
    nand_write_row_addr(row);

    nand_cle(1);
    nand_write_cmd(0x30);
    nand_cle(0);

    if (!nand_wait_ready(timeout_us)) {
        return NAND_E_TIMEOUT;
    }

    nand_read_data(main, NAND_PAGE_SIZE);
    nand_read_data(oob, NAND_OOB_SIZE);

    uint8_t status = nand_read_status();

    if (status & NAND_STATUS_FAIL) {
        return NAND_E_STATUS;
    }

    if (status & NAND_STATUS_ECC_UNCORRECTABLE) {
        return NAND_E_ECC;
    }

    return NAND_OK;
}
```

工程注意事项：

- `row` 是页地址，不是字节地址。
- 并行 NAND 的列地址可能需要 1~2 个周期。
- 不同器件的地址周期和 READ 命令可能不同。
- `R/B#` 只能说明内部操作完成，不能替代状态寄存器检查。
- DMA 读取时必须确认总线宽度、Cache 一致性和缓冲区对齐。

---

### 5.3 Page Program 流程

典型编程流程：

```
1. 检查目标块是否为坏块
2. 检查页是否已经被编程
3. 发送 0x80
4. 发送列地址和行地址
5. 写入 Main + OOB
6. 发送 0x10
7. 等待 R/B#
8. 读取状态寄存器
9. 判断 Program Fail
```

```
int nand_program_page(uint32_t row,
                       const uint8_t *main,
                       const uint8_t *oob,
                       uint32_t timeout_us)
{
    if (main == NULL || oob == NULL) {
        return NAND_E_STATUS;
    }

    if (nand_is_bad_block(row / NAND_PAGES_PER_BLOCK)) {
        return NAND_E_STATUS;
    }

    nand_cle(1);
    nand_write_cmd(0x80);
    nand_cle(0);

    nand_write_col_addr(0);
    nand_write_row_addr(row);

    nand_write_data(main, NAND_PAGE_SIZE);
    nand_write_data(oob, NAND_OOB_SIZE);

    nand_cle(1);
    nand_write_cmd(0x10);
    nand_cle(0);

    if (!nand_wait_ready(timeout_us)) {
        return NAND_E_TIMEOUT;
    }

    uint8_t status = nand_read_status();
    return (status & NAND_STATUS_FAIL) ? NAND_E_STATUS : NAND_OK;
}
```

**重要约束：**

- 同一页不应反复部分编程，除非数据手册明确允许。
- 同一块中页的编程顺序通常必须遵守由低到高的规则。
- 不能把已编程的 0 直接改回 1，必须先擦除整个块。
- 编程前必须确保 OOB 中 ECC 区域不会被业务数据覆盖。

---

### 5.4 Block Erase 流程

擦除是以块为单位执行：

```
1. 检查坏块
2. 发送 ERASE SETUP
3. 发送块地址
4. 发送 ERASE CONFIRM
5. 等待 R/B#
6. 检查 Erase Fail
```

```
int nand_erase_block(uint32_t block, uint32_t timeout_us)
{
    if (block >= NAND_BLOCK_COUNT) {
        return NAND_E_STATUS;
    }

    if (nand_is_bad_block(block)) {
        return NAND_E_STATUS;
    }

    nand_cle(1);
    nand_write_cmd(0x60);
    nand_cle(0);

    nand_write_row_addr(block * NAND_PAGES_PER_BLOCK);

    nand_cle(1);
    nand_write_cmd(0xD0);
    nand_cle(0);

    if (!nand_wait_ready(timeout_us)) {
        return NAND_E_TIMEOUT;
    }

    return (nand_read_status() & NAND_STATUS_FAIL)
               ? NAND_E_STATUS : NAND_OK;
}
```

擦除过程中会将单元恢复为擦除态。擦除是 NAND 中最耗时、对寿命影响最大的操作之一。

---

### 5.5 OOB、ECC 与数据布局

以 2 KiB Page 为例，可能有 64~128 字节 OOB：

```
Main Area: 2048 bytes
OOB Area:
    ├── Bad Block Marker
    ├── ECC bytes
    ├── Logical Page Number
    ├── Sequence Number
    └── 文件系统/FTL 元数据
```

不要假设 OOB 的具体偏移，必须读取：

- 芯片数据手册。
- 控制器 ECC 布局。
- Linux NAND 控制器驱动的 `ecc.layout`。
- ONFI 参数页的 ECC 建议能力。

一个抽象的 ECC 读接口：

```
typedef struct {
    uint32_t corrected_bits;
    bool uncorrectable;
} nand_ecc_result_t;

int nand_read_page_ecc(uint32_t row,
                       uint8_t *data,
                       nand_ecc_result_t *result)
{
    int rc = nand_read_page_raw(row, data, nand_oob_buffer);

    if (rc != NAND_OK) {
        return rc;
    }

    result->corrected_bits = ecc_decode(
        data,
        NAND_PAGE_SIZE,
        nand_oob_buffer,
        NAND_OOB_SIZE
    );

    result->uncorrectable =
        result->corrected_bits == ECC_UNCORRECTABLE;

    if (result->uncorrectable) {
        return NAND_E_ECC;
    }

    return NAND_OK;
}
```

#### BCH 与 LDPC

|特性|BCH|LDPC|
|---|---|---|
|适用介质|SLC、较老 MLC|TLC、QLC、高密度 NAND|
|解码复杂度|中|高|
|软判决能力|弱或无|强|
|功耗|较低|较高|
|控制器要求|较低|较高|
|纠错性能|稳定|高，但依赖迭代和软信息|

ECC 设计应关注：

- 每 512 字节或每 1 KiB 的纠错能力。
- 最大可纠正 bit 数。
- 纠错计数的预警阈值。
- Uncorrectable Error 的处理策略。
- 是否需要 read-retry 或重新迁移数据。

---

### 5.6 坏块管理

NAND 坏块分为：

1. **工厂坏块**：出厂时已存在。
2. **运行时坏块**：擦除或编程失败后产生。
3. **潜在弱块**：操作成功，但 ECC 纠错位数持续升高。

典型策略：

```
bool nand_is_bad_block(uint32_t block)
{
    uint32_t marker_page = block * NAND_PAGES_PER_BLOCK;
    uint8_t oob[NAND_OOB_SIZE];

    if (nand_read_oob(marker_page, oob) != NAND_OK) {
        return true;
    }

    return oob[NAND_BAD_BLOCK_MARKER_OFFSET] != 0xFF;
}
```

运行时出现 Program Fail 或 Erase Fail：

```
int nand_mark_runtime_bad(uint32_t block)
{
    uint8_t oob[NAND_OOB_SIZE];

    memset(oob, 0xFF, sizeof(oob));
    oob[NAND_BAD_BLOCK_MARKER_OFFSET] = 0x00;

    /*
     * 实际项目必须确认器件允许的坏块标记写入方式，
     * 某些器件不允许直接破坏首个页的 OOB。
     */
    return nand_program_oob_marker(
        block * NAND_PAGES_PER_BLOCK,
        oob
    );
}
```

工业系统中通常还需要一张逻辑坏块表：

```
物理块 100 -> 无法使用
物理块 101 -> 逻辑块 56
物理块 102 -> 逻辑块 57
```

坏块表本身必须：

- 多副本保存。
- 带版本号或序列号。
- 带 CRC。
- 支持掉电恢复。
- 防止坏块表更新失败后丢失整盘映射。

---

### 5.7 Raw NAND 与 FTL

Raw NAND 不能直接当普通块设备使用，因为：

```
逻辑扇区地址 != 物理页地址
```

FTL 一般包含：

```
Host LBA
  ↓
逻辑页映射
  ↓
物理页
  ↓
ECC + OOB
  ↓
NAND
```

常见映射方式：

|映射方式|RAM 占用|随机写性能|适用场景|
|---|---|---|---|
|页级映射|高|高|高性能、高 RAM|
|块级映射|低|低|简单设备|
|混合映射|中|中高|工业产品常用|
|日志结构|低到中|高|追加型数据、文件系统|

对于 Linux，常见分层是：

```
Raw NAND
  ↓
NAND Controller ECC
  ↓
MTD
  ↓
UBI
  ↓
UBIFS
  ↓
应用
```

**UBI 不是文件系统，UBIFS 也不是简单块文件系统。**

- MTD 面向擦除块设备。
- UBI 负责逻辑擦除块、坏块和磨损均衡。
- UBIFS 面向 NAND 特性组织日志和索引。

---

## 6. 性能量化分析

以下数据以一个典型平台为估算基准：

```
器件：2 KiB Page、128 KiB Block、SLC Raw NAND
接口：8-bit ONFI、50 MHz
ECC：BCH 8~24 bit / 1 KiB
CPU：Cortex-M7 400 MHz 或 Cortex-A53 1.4 GHz
```

实际数值必须以具体器件数据手册和实测结果为准。

### 典型时间

|操作|典型时间|
|---|---|
|页数据传输 2 KiB，50 MHz，8 bit|约 41 us|
|Page Read 内部 tR|约 25~100 us|
|Page Program tPROG|约 200~1,200 us|
|Block Erase tBERS|约 1~10 ms|
|ECC 软件解码 2 KiB|约 5~100 us|
|SPI NAND 读取一页|约 50~300 us|

传输时间：

```
T_transfer = DataBits / BusFrequency
```

对于 2 KiB、8 bit、50 MHz：

```
T_transfer = 2048 × 8 / 50 MHz
           ≈ 327.7 us
```

如果是 8-bit 并行总线，单个数据周期传 1 Byte，则：

```
T_transfer = 2048 / 50 MHz
           ≈ 41 us
```

吞吐量的理论上限：

```
Throughput = BusWidth × BusFrequency / 8
```

8-bit、50 MHz：

```
Throughput = 8 × 50 MHz / 8
           = 50 MB/s
```

但真实吞吐量还要扣除：

- 命令和地址周期。
- R/B# 等待时间。
- ECC 处理时间。
- DMA 启停。
- 坏块跳过。
- FTL 映射和垃圾回收。
- 文件系统元数据写入。

### 写放大

```
WAF = NAND 实际写入量 / 主机有效写入量
```

例如主机写入 4 KiB，但文件系统触发：

- 4 KiB 数据写入。
- 8 KiB 元数据。
- 128 KiB 垃圾回收搬移。

则：

```
NAND 实际写入量 = 4 + 8 + 128 = 140 KiB
WAF = 140 / 4 = 35
```

这是严重的写放大。

优化方法：

- 采用日志结构写入。
- 聚合小写入为整页写入。
- 降低频繁元数据更新。
- 预留 over-provisioning 空间。
- 使用顺序写入。
- 让垃圾回收在空闲时间执行。
- 对热点数据与冷数据分区。

### 寿命估算

简单估算：

```
LifeWrites = UsableCapacity × P/E_Cycles / WAF
```

例：

```
可用容量 = 1 GiB
SLC P/E = 50,000
WAF = 5

LifeWrites = 1 GiB × 50,000 / 5
           = 10,000 GiB
```

这不是完整寿命模型，还必须考虑：

- 数据保持时间。
- 温度。
- 读干扰。
- 坏块增长。
- 不同块的磨损分布。
- 电压和电源质量。
- ECC 余量。

---

## 7. 应用场景选型指南

### 决策流程图

```
需要存储代码并支持直接执行？
├── 是：优先选择 NOR Flash
└── 否
    └── 需要大容量？
        ├── 否：SPI NOR / SPI NAND
        └── 是
            └── 是否希望主控看到标准块设备？
                ├── 是：eMMC / UFS
                └── 否：Raw NAND + MTD/UBI/自研 FTL
                    └── 是否强实时、长寿命？
                        ├── 是：SLC NAND 或工业级 MLC
                        └── 否：TLC/QLC managed NAND
```

### 场景选型

|需求|方案|理由|
|---|---|---|
|MCU 保存数百 MB 日志|SPI NAND|引脚少、容量大|
|Linux 根文件系统|Raw NAND + UBI + UBIFS|与 NAND 擦除特性匹配|
|高可靠 Boot 镜像|NOR + 冗余镜像|支持稳定随机读和 XIP|
|摄像头本地存储|eMMC/UFS|内部 FTL，吞吐较高|
|高频参数更新|NOR EEPROM 仿真或 FRAM|避免 NAND 小写放大|
|工业控制器长期日志|SLC NAND + 日志结构|P/E 寿命和可预测性更好|

---

## 8. 工程最佳实践

### 设计原则

1. **任何 NAND 访问都必须经过 ECC。**
2. **任何物理块使用前都必须检查坏块。**
3. **所有 Program/Erase 都必须有超时。**
4. **状态寄存器必须在操作完成后检查。**
5. **不能假设 NAND 上电后内容一定为全 1。**
6. **不能直接在 NAND 上实现传统原地更新。**
7. **逻辑地址与物理地址必须隔离。**
8. **关键元数据必须具备 CRC、版本和冗余。**
9. **对 ECC 纠错计数进行统计和预警。**
10. **存储驱动必须支持掉电中断后的恢复。**

### 选型决策矩阵

|指标|权重|SLC Raw NAND|eMMC|SPI NAND|NOR|
|---|---|---|---|---|---|
|容量|20%|5|5|4|2|
|寿命|20%|5|3|3|4|
|软件复杂度|15%|2|5|4|4|
|随机读取|15%|3|4|3|5|
|低引脚数|10%|2|4|5|5|
|供应稳定性|10%|4|3|3|4|
|成本|10%|4|4|4|2|

### 工业级编码规范

- 所有容量、页大小、块大小使用 `uint32_t` 或 `uint64_t`。
- 不使用魔数，命令和状态位统一宏定义。
- 驱动层禁止直接调用业务层回调。
- 读写缓冲区明确 Cache、DMA 和对齐要求。
- 统一返回值：超时、ECC、坏块、总线错误、参数错误。
- 记录每块的擦除次数和 ECC 纠错统计。
- 对关键路径增加 Trace 点：
    - 命令开始。
    - R/B# 变化。
    - 状态结果。
    - ECC 纠错量。
    - 坏块标记。
- 生产测试必须覆盖全盘擦除、随机写、顺序写、掉电和高温。

---

## 9. 常见错误与避坑指南

### 错误一：把 NAND 当 NOR 使用

错误代码：

```
*(volatile uint8_t *)(NAND_BASE + offset) = value;
```

根因：

- NAND 不支持任意字节原地改写。
- 必须经过命令、地址、页缓存和 Program 流程。

正确实现：

```
uint8_t page[NAND_PAGE_SIZE];

nand_read_page(row, page, oob);
memcpy(&page[offset], &value, sizeof(value));
nand_erase_block(block, timeout_us);
nand_program_page(row, page, oob, timeout_us);
```

实际工程中应改为日志结构更新，避免整块擦除。

风险：

- 数据未写入。
- 页状态损坏。
- 触发 Program Fail。
- 快速消耗 P/E 寿命。

---

### 错误二：覆盖 OOB 中的 ECC 或坏块标记

错误代码：

```
nand_program_page(row, data, user_oob, timeout_us);
```

根因：

- `user_oob` 未按控制器布局保留 ECC 区域。
- 可能破坏坏块标志。

正确实现：

```
void build_oob(uint8_t *oob, const uint8_t *metadata)
{
    memset(oob, 0xFF, NAND_OOB_SIZE);

    memcpy(&oob[USER_METADATA_OFFSET],
           metadata,
           USER_METADATA_SIZE);

    ecc_encode_oob(oob);
}
```

风险：

- 后续读取无法纠错。
- 工厂坏块被误识别为好块。
- 文件系统元数据损坏。

---

### 错误三：只检查 R/B#，不检查状态寄存器

错误代码：

```
nand_wait_ready(10000);
return 0;
```

根因：

- R/B# 只表示内部操作结束，不代表操作成功。

正确实现：

```
if (!nand_wait_ready(timeout_us)) {
    return NAND_E_TIMEOUT;
}

uint8_t status = nand_read_status();

if (status & NAND_STATUS_FAIL) {
    nand_mark_runtime_bad(block);
    return NAND_E_STATUS;
}
```

风险：

- 将失败页当作有效数据。
- 运行时坏块未进入管理表。
- 后续错误扩散。

---

### 错误四：忽略 NAND 编程顺序限制

错误代码：

```
for (int page = 0; page < PAGES_PER_BLOCK; page += 2) {
    nand_program_page(block * PAGES_PER_BLOCK + page,
                      data[page], oob[page], timeout_us);
}
```

根因：

- 某些 NAND 要求页按物理顺序编程。
- 交错编程或跨区域编程可能违反数据手册限制。

正确实现：

```
for (uint32_t page = 0; page < PAGES_PER_BLOCK; page++) {
    if (nand_program_page(block * PAGES_PER_BLOCK + page,
                          data[page],
                          oob[page],
                          timeout_us) != NAND_OK) {
        return NAND_E_STATUS;
    }
}
```

风险：

- 页间干扰。
- 数据保持能力下降。
- 读取 ECC 错误。

---

### 错误五：没有掉电一致性设计

错误代码：

```
write_mapping_table(new_table);
write_data(new_data);
```

根因：

- 两次写之间掉电后，映射表和数据状态不一致。

正确实现：

```
typedef struct {
    uint32_t magic;
    uint32_t generation;
    uint32_t logical_block;
    uint32_t physical_block;
    uint32_t crc32;
} mapping_record_t;

int commit_mapping(const mapping_record_t *record)
{
    mapping_record_t copy = *record;
    copy.crc32 = crc32(&copy, offsetof(mapping_record_t, crc32));

    int rc = append_log_record(&copy);
    if (rc != 0) {
        return rc;
    }

    return flush_nand_program_queue();
}
```

启动时扫描多个记录，选择：

- Magic 正确。
- CRC 正确。
- Generation 最大。
- 映射关系自洽。

风险：

- 文件系统无法挂载。
- 数据回退到旧版本。
- 坏块表丢失。
- 设备进入反复重启。

---

## 10. 多机制组合使用方案

一个工业级 Raw NAND 存储层通常采用以下架构：

```
应用数据层
    ↓
日志/对象存储层
    ↓
逻辑块管理
    ↓
FTL 或 UBI
    ↓
坏块管理 + 磨损均衡
    ↓
ECC 编解码
    ↓
NAND Controller HAL
    ↓
DMA / GPIO / 时序控制器
    ↓
NAND Flash
```

### 组合设计模式

- **日志结构写入**：避免随机原地更新。
- **双副本提交**：关键元数据 A/B 保存。
- **Copy-on-Write**：新数据写新位置，提交后切换指针。
- **后台垃圾回收**：在空闲任务中迁移有效页。
- **磨损均衡**：冷热数据分离，并将高擦除块迁移到低擦除块。
- **ECC 预警**：达到纠错阈值时主动搬移数据。

### 统一抽象接口

```
typedef struct {
    uint32_t page_size;
    uint32_t oob_size;
    uint32_t pages_per_block;
    uint32_t block_count;
    uint32_t ecc_strength;
} nand_geometry_t;

typedef struct {
    int (*read_page)(uint32_t row, uint8_t *data, uint8_t *oob);
    int (*program_page)(uint32_t row,
                        const uint8_t *data,
                        const uint8_t *oob);
    int (*erase_block)(uint32_t block);
    int (*is_bad)(uint32_t block);
    int (*mark_bad)(uint32_t block);
} nand_ops_t;

typedef struct {
    nand_geometry_t geometry;
    nand_ops_t ops;
    uint32_t *erase_count;
    uint8_t *bad_block_bitmap;
} nand_device_t;
```

### 后台垃圾回收框架

```
int nand_gc_once(nand_device_t *dev)
{
    uint32_t victim = select_victim_block(dev);

    if (dev->ops.is_bad(victim)) {
        return 0;
    }

    for (uint32_t page = 0;
         page < dev->geometry.pages_per_block;
         page++) {
        if (!page_is_valid(victim, page)) {
            continue;
        }

        uint8_t data[NAND_PAGE_SIZE];
        uint8_t oob[NAND_OOB_SIZE];

        int rc = dev->ops.read_page(
            victim * dev->geometry.pages_per_block + page,
            data,
            oob
        );

        if (rc != NAND_OK) {
            dev->ops.mark_bad(victim);
            return -1;
        }

        uint32_t target = allocate_free_page();

        rc = dev->ops.program_page(target, data, oob);
        if (rc != NAND_OK) {
            dev->ops.mark_bad(target / dev->geometry.pages_per_block);
            return -1;
        }

        update_mapping(page_to_lba(victim, page), target);
    }

    if (dev->ops.erase_block(victim) != NAND_OK) {
        dev->ops.mark_bad(victim);
        return -1;
    }

    dev->erase_count[victim]++;
    return 0;
}
```

---

## 11. 工业级实际案例分析

### 案例一：工业网关本地日志

#### 需求

- 每秒写入 2 KiB。
- 保存 30 天。
- 支持异常掉电后恢复。
- 不能因单个坏块导致设备停止工作。

#### 架构

```
采集任务
  ↓ Queue
日志聚合任务
  ↓ 16 KiB 顺序写
环形日志区
  ↓
SPI NAND + 内部 ECC
```

#### 核心设计

- 以 16 KiB 为聚合写入单位。
- 每条日志包含时间戳、序列号、长度和 CRC。
- 每个擦除块头部保存块序列号。
- 启动时扫描块头和记录 CRC，定位最后一个完整记录。
- 使用环形策略回收最旧数据。

#### 设计要点

- 2 KiB/s × 30 天约为 4.94 GiB 原始数据，容量必须留有余量。
- 如果 WAF 为 2，实际 NAND 写入约 9.88 GiB。
- 不能只按标称容量选型，应考虑预留块、坏块和文件系统开销。

---

### 案例二：工业控制器双镜像升级

#### 需求

- 固件升级过程中掉电不能变砖。
- 新固件校验失败时自动回退。
- 固件容量 8 MiB。
- 支持升级状态追踪。

#### 存储布局

```
Block 0~63     Bootloader
Block 64~511   Firmware A
Block 512~959  Firmware B
Block 960~1023 Metadata / Recovery
```

每个镜像包含：

```
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t image_size;
    uint32_t image_crc;
    uint32_t commit_state;
    uint32_t header_crc;
} image_header_t;
```

升级流程：

```
1. 运行 A，下载新镜像到 B
2. 写入镜像数据
3. 读取回校验 CRC
4. 写入 B 的 valid 标志
5. 更新启动选择元数据
6. 重启
7. B 启动成功后写入 confirmed
8. 启动失败则回退 A
```

设计要点：

- `valid` 和 `confirmed` 不能只保存一份。
- 状态更新采用追加日志而不是覆盖。
- 每次更新必须执行读回校验。
- Bootloader 必须能识别坏块并跳过物理地址空洞。
- 固件镜像不能假设连续物理块一定可用。

---

### 案例三：高温振动环境的数据采集设备

#### 需求

- 温度范围：-40°C 至 85°C。
- 传感器数据周期写入。
- 长期运行超过 10 年。
- 对数据保持和 ECC 余量有严格要求。

#### 架构

```
SLC NAND
+ BCH/LDPC ECC
+ 数据 CRC
+ 三副本关键索引
+ 冷热数据分离
+ 周期性数据刷新
+ ECC 纠错阈值监控
```

#### 设计要点

- 高温会降低数据保持时间。
- 不能只使用一次写入后的数据，不做 refresh。
- 当纠错位数持续超过阈值时，应立即迁移数据。
- 采用 SLC 而非 TLC，牺牲容量换取寿命和可靠性。
- 通过 `擦除次数 + ECC 纠错数 + 温度历史` 建立寿命模型。

---

## 12. 高频问题深度答疑

### 问题一：为什么 NAND 不能像 RAM 一样随机写？

因为 NAND 单元只能通过编程使状态朝一个方向变化，无法直接把 0 恢复为 1。恢复为 1 需要对整个 Block 施加擦除操作。因此 NAND 的最小写粒度是 Page，最小擦除粒度是 Block。

---

### 问题二：ECC 已经纠错，为什么还需要 CRC？

ECC 主要针对随机 bit error。CRC 用于检测：

- 元数据错位。
- 控制器逻辑错误。
- 地址映射错误。
- 错误数据被写入正确物理位置。
- 超出 ECC 能力但未被正确识别的异常。

工程上通常采用：

```
NAND 原始数据
+ ECC：纠正介质 bit error
+ CRC：验证记录整体完整性
```

两者职责不同，不能互相替代。

---

### 问题三：ECC 纠错位数越高越好吗？

不是。更强 ECC 通常意味着：

- 更多 OOB 空间。
- 更高解码延迟。
- 更大功耗。
- 更复杂的控制器。
- 更高的软信息读取成本。

应根据 NAND 厂商规定的 `ECC requirement` 设计，并保留实际纠错余量。若 NAND 要求 8 bit/1 KiB，设计 8 bit 只是最低门槛，工业产品通常需要结合寿命和温度进行验证。

---

### 问题四：为什么 eMMC 仍然会突然变只读或掉盘？

eMMC 内部包含 FTL、ECC、坏块管理和缓存。主控看不到其内部映射和磨损状态。当预留块耗尽、映射元数据损坏、内部 NAND 达到寿命或供电异常时，设备可能：

- 进入只读模式。
- 返回超时。
- 报告不可恢复错误。
- 重新枚举失败。

因此 eMMC 不是“无需管理寿命”，而是把管理责任转移到了器件内部。工业设计仍应保留：

- 写入量统计。
- 健康状态监控。
- 文件系统冗余。
- 可恢复升级策略。
- 关键数据外部备份。

---

### 问题五：为什么顺序写比随机写更重要？

随机小写会导致：

```
小写入
  ↓
页合并
  ↓
有效页搬移
  ↓
整块擦除
  ↓
重新编程
```

这会提高 WAF 和尾延迟。顺序写可以减少：

- 页合并。
- 映射更新。
- 垃圾回收频率。
- 峰值擦除延迟。

实时系统中还要关注 P99/P999 延迟，而不是只看平均吞吐量。

---

### 问题六：NAND 掉电时最危险的是什么？

最危险的不是单个数据页写失败，而是：

- 映射表只更新了一半。
- 坏块表更新一半。
- 文件系统日志提交状态不一致。
- 电源下降过程中 NAND 内部编程脉冲异常。
- 控制器 Cache 中的数据尚未落盘。

解决方式：

- 电源监测和提前中止写入。
- 足够的保持时间或超级电容。
- 双副本元数据。
- Generation + CRC。
- 写前日志和写后提交。
- 启动恢复扫描。
- 对关键区域实施只追加更新。

---

## 13. 课程核心总结

### 核心要点

- **NAND 的基本单位是 Page 读写、Block 擦除。**
- **NAND 不能直接覆盖写，必须使用日志、FTL 或文件系统完成更新。**
- **ECC、坏块管理、磨损均衡和掉电恢复是一个整体。**
- **Raw NAND 软件复杂度高，但可控性和成本优势明显。**
- **eMMC/UFS 降低软件复杂度，但内部 FTL 行为不可完全观察。**
- **TLC/QLC 容量和成本优势突出，但对 ECC、温度和寿命更敏感。**

### 性能排序

一般情况下：

```
顺序读 > 随机读
顺序写 > 随机写
SLC > MLC > TLC > QLC
并行多 Die > 单 Die
DMA > CPU PIO
整页写 > 小块写
```

### 通用选型结论

```
代码执行：NOR
高可靠小容量：SLC NAND / NOR
MCU 大容量：SPI NAND
Linux 原始 NAND：Raw NAND + MTD + UBI + UBIFS
标准块设备：eMMC / UFS
高容量低成本：TLC/QLC managed NAND
```

---

## 14. 快速参考速查表

### 场景选型表

|场景|推荐方案|
|---|---|
|Bootloader|NOR 或 SLC NAND|
|MCU 日志|SPI NAND + 日志结构|
|Linux 根文件系统|UBI + UBIFS|
|高速多媒体|eMMC / UFS|
|高频小参数更新|FRAM、EEPROM、NOR 日志区|
|长寿命工业设备|SLC NAND + 强 ECC + refresh|
|低成本大容量|TLC eMMC 或 UFS|

### 特性对比表

|特性|Raw NAND|SPI NAND|eMMC|UFS|
|---|---|---|---|---|
|ECC|主控负责|通常内部提供|内部负责|内部负责|
|坏块管理|主控/软件负责|依器件|内部负责|内部负责|
|接口复杂度|高|低|中|高|
|容量|高|中|高|高|
|可控性|最高|中高|较低|较低|
|适合 MCU|条件适合|适合|通常不适合|不适合|
|适合 Linux|适合|可用|适合|适合|

### 关键公式

```
T_transfer = DataBits / BusFrequency

Throughput = BusWidth × BusFrequency / 8

WAF = NAND 实际写入量 / 主机有效写入量

LifeWrites = UsableCapacity × P/E_Cycles / WAF
```

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  为什么 NAND 的读写和擦除粒度不同？
- [ ]  为什么 NAND 需要 OOB？
- [ ]  如何区分工厂坏块和运行时坏块？
- [ ]  如何设计一个不会因掉电损坏的映射表？
- [ ]  为什么不能仅通过 R/B# 判断操作成功？
- [ ]  什么情况下应该使用 Raw NAND？
- [ ]  什么情况下应选择 eMMC 或 UFS？
- [ ]  如何计算 WAF？
- [ ]  如何根据 ECC 纠错计数判断数据是否需要迁移？
- [ ]  如何降低随机小写造成的写放大？
- [ ]  如何设计双镜像升级和自动回退？
- [ ]  如何对 NAND 执行寿命和高温数据保持测试？

建议实战验证：

- 使用逻辑分析仪抓取一次完整 Page Read。
- 注入一个 ECC 可纠正错误并观察纠错计数。
- 让一次 Program 或 Erase 失败，验证坏块迁移逻辑。
- 在元数据提交的每个阶段断电，验证启动恢复结果。
- 对顺序写和随机写分别统计平均延迟、P99 延迟和 WAF。

---

## 16. 实践与进阶路径

### 阶段一：驱动基础

实现以下功能：

1. 读取设备 ID。
2. 读取 ONFI 参数页。
3. 读取状态寄存器。
4. 实现 Page Read。
5. 实现 Page Program。
6. 实现 Block Erase。
7. 实现 R/B# 超时处理。
8. 实现工厂坏块扫描。

验收指标：

- 连续读写 10,000 页无协议错误。
- 所有操作具备超时。
- 任意操作失败都返回明确错误码。
- 能打印页地址、块地址、状态和 ECC 结果。

### 阶段二：可靠性层

实现：

- ECC 编解码。
- OOB 元数据布局。
- 运行时坏块管理。
- 坏块表多副本。
- 每块擦除计数。
- 记录 CRC 和序列号。
- 双副本元数据提交。

验收指标：

- 随机断电 10,000 次后数据可恢复。
- 模拟 1% 坏块后逻辑地址仍可用。
- ECC 纠错错误不会静默传播。

### 阶段三：日志和 FTL

实现：

- 页级或块级映射。
- 空闲块管理。
- 垃圾回收。
- 冷热数据分离。
- 后台磨损均衡。
- WAF 统计。
- P99/P999 延迟统计。

测试数据集：

```
4 KiB 顺序写
4 KiB 随机写
64 KiB 顺序写
混合读写
突发写入
低剩余空间写入
高温下持续写入
```

重点指标：

```
平均吞吐量
P99 写延迟
P999 写延迟
WAF
ECC 平均纠错位数
坏块增长率
有效容量比例
掉电恢复时间
```

### 阶段四：Linux 工业化

深入学习：

- Linux MTD。
- NAND 控制器驱动。
- BCH/LDPC 硬件加速。
- UBI 擦除块管理。
- UBIFS 日志和索引。
- Device Tree NAND 描述。
- `nandtest`、`mtd_debug`、`ubiattach`、`ubiformat`。
- 内核启动阶段的 NAND 时序与 ECC 配置。

### 阶段五：架构进阶

进一步研究：

- Read Disturb 与数据刷新。
- Retention Loss 与温度模型。
- Program Disturb、Cell-to-Cell Interference。
- TLC/QLC 的软判决和 Read Retry。
- NAND 健康度预测。
- 存储故障注入框架。
- 面向 OTA 的 A/B 分区与回滚。
- 面向工业设备的可观测存储系统。
- 通过统计 ECC 纠错量预测剩余寿命。

最终应形成一套完整能力：

```
芯片识别
  → 时序驱动
  → ECC
  → 坏块管理
  → 磨损均衡
  → 日志/FTL
  → 掉电恢复
  → 寿命监控
  → 工业测试与量产验证
```