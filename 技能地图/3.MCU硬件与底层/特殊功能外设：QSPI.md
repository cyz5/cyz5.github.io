
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 QSPI/OSPI 与传统 SPI 的硬件结构差异。
- 理解单线、双线、四线、八线数据传输在时序和吞吐率上的本质区别。
- 理解 NOR Flash 的命令周期、地址周期、Dummy Cycle、数据周期和状态机。
- 理解 QSPI 控制器的间接模式、自动轮询模式、内存映射模式的工作机制。
- 理解 XIP、Cache、预取、总线仲裁对执行性能和实时性的影响。

### 掌握

应能够：

- 配置 QSPI 外设完成 NOR Flash 识别、读写、擦除和状态轮询。
- 设计可靠的 Flash 驱动层，包括初始化、超时、异常恢复和掉电保护。
- 处理不同厂商 Flash 的 JEDEC ID、状态寄存器、QE 位和 Dummy Cycle 差异。
- 使用 Memory-Mapped Mode 访问外部 Flash。
- 设计 4 KB 扇区擦除、64 KB 块擦除、页编程等基础存储操作。
- 通过逻辑分析仪和性能计数器定位 QSPI 时序错误和吞吐率瓶颈。

### 精通

应能够：

- 分析 QSPI 控制器寄存器级配置和 Flash 内部状态机。
- 评估 XIP 架构下的 Cache Miss、Cache Line Fill 和随机访问开销。
- 处理 DMA、Cache 一致性、RTOS 任务并发访问和中断实时性问题。
- 设计支持多型号 NOR Flash 的可移植驱动架构。
- 设计在 OTA、文件系统、参数存储和图形资源加载场景下的 QSPI 访问策略。
- 量化 QSPI 的带宽、延迟、擦写寿命、功耗和实时性。

### 能够设计

应能够独立设计：

- 面向工业控制器的外部代码存储和 XIP 系统。
- 面向 OTA 的双分区 Flash 布局与升级回滚机制。
- 面向 LVGL/GUI 的资源型 QSPI Flash 架构。
- 面向 RTOS 的线程安全 QSPI 服务层。
- 支持故障注入、数据校验、掉电恢复和现场诊断的工业级 QSPI 模块。

---

## 2. 前置要求

### 知识要求

- MCU 总线架构：AHB、AXI、APB、内存映射。
- GPIO 复用、时钟树和中断控制器。
- SPI 基础协议：CPOL、CPHA、CS、SCK、MOSI、MISO。
- NOR Flash 基本结构：Page、Sector、Block、状态寄存器。
- C 语言指针、位操作、结构体和模块化设计。
- RTOS 任务、互斥锁、临界区和 DMA 基础。
- Cache、MPU、内存屏障和 DMA 一致性。

### 技能要求

- 能够阅读 MCU Reference Manual 中的 QSPI 章节。
- 能够使用逻辑分析仪观察 QSPI 总线。
- 能够阅读 NOR Flash Datasheet 中的 AC Characteristics 和 Command Table。
- 能够编写基础 SPI Flash 驱动。
- 能够分析 HardFault、BusFault、总线超时和 Cache 一致性问题。
- 能够使用编译器 Map 文件分析代码布局和外部存储占用。

---

## 3. 技术概述

### 3.1 QSPI 的定义

QSPI，Quad SPI，通常指基于标准 SPI 协议扩展而来的 **四数据线串行外设接口**。

传统 SPI 一般使用：

```
SCK   : 时钟
CS    : 片选
MOSI  : 主机到从机
MISO  : 从机到主机
```

QSPI 则允许 IO0~IO3 四根数据线同时传输数据：

```
SCK   : 时钟
CS    : 片选
IO0   : 数据线 0
IO1   : 数据线 1
IO2   : 数据线 2
IO3   : 数据线 3
```

常见传输模式：

|模式|指令线|地址线|数据线|每周期有效数据|
|---|---|---|---|---|
|SPI|1|1|1|1 bit|
|Dual SPI|1|2|2|2 bit|
|Quad Output|1|1/4|4|4 bit|
|Quad I/O|1/4|4|4|4 bit|
|Octal SPI|8|8|8|8 bit|
|DDR/OPI|8|8|8|上下沿均传输|

需要注意：**“QSPI 外设”不一定代表整个命令周期全部使用四线传输。** 很多 Flash 的命令仍然通过单线传输，只有地址和数据阶段进入 Quad 模式。

---

### 3.2 QSPI 的技术价值

QSPI 主要解决以下问题：

1. **扩大外部存储容量**
    
     
    
    MCU 内部 Flash 通常不足以容纳：
    
    - 大型应用代码；
    - 图形资源；
    - 字体、音频、模型；
    - OTA 双镜像；
    - 大型配置数据库。
2. **提高串行 Flash 访问吞吐率**
    
     
    
    理想数据速率近似为：
    
    Tdata=Nlane×fSCK×Eedge8Tdata​=8Nlane​×fSCK​×Eedge​​
    
    其中：
    
    - NlaneNlane​：数据线数量；
    - fSCKfSCK​：时钟频率；
    - EedgeEedge​：每周期有效边沿数，SDR 为 1，DDR 为 2。
    
    例如：
    
    - 4 线；
    - 80 MHz；
    - SDR；
    
    理论吞吐率：
    
    4×80 MHz8=40 MB/s84×80 MHz​=40 MB/s
3. **支持 XIP**
    
     
    
    控制器将外部 Flash 映射到 MCU 地址空间，CPU 可以像访问内存一样执行代码：
    
    ```
    typedef void (*app_entry_t)(void);
    
    app_entry_t entry = (app_entry_t)0x90000001U;
    entry();
    ```
    
4. **减少引脚和 PCB 成本**
    
     
    
    相比并行 NOR/NAND，QSPI 在提高带宽的同时仍保持较少引脚数量。
    

---

### 3.3 主流技术分支

#### 按数据宽度分类

- Standard SPI
- Dual SPI
- Quad SPI
- Octal SPI
- HyperBus
- xSPI/OPI

#### 按访问模式分类

- 间接模式：CPU 通过 FIFO/DMA 发送命令。
- 自动轮询模式：硬件轮询状态寄存器。
- 内存映射模式：Flash 映射到 MCU 地址空间。
- XIP：直接从外部 Flash 执行代码。

#### 按传输时序分类

- SDR：Single Data Rate。
- DDR：Double Data Rate。
- DTR：部分厂商对 DDR 的命名。
- STR：Single Transfer Rate。

#### 按存储介质分类

- SPI NOR Flash：随机读取快，适合代码和资源。
- SPI NAND Flash：容量大、成本低，但需要 ECC 和坏块管理。
- EEPROM/FRAM：适合小数据频繁更新。
- PSRAM：适合运行时数据，不适合长期存储。

---

## 4. 核心特性横向对比

### 4.1 不同接口方案对比

|维度|标准 SPI|QSPI|Octal SPI|并行 NOR|eMMC/SD|
|---|---|---|---|---|---|
|数据线数量|1|4|8|8~32|4/8|
|典型时钟|20~50 MHz|80~133 MHz|100~200 MHz|50~100 MHz|50~200 MHz|
|理论吞吐|2.5~6.25 MB/s|40~66 MB/s|100~200 MB/s|高|高|
|引脚数量|少|中|多|多|中|
|随机读取延迟|中|中|低|低|高|
|XIP 支持|部分|常见|常见|常见|不适合|
|设计复杂度|低|中|高|高|中|
|EMI 风险|低|中|高|高|中|
|适合代码执行|一般|很好|很好|很好|较差|
|容量|1~512 Mbit|8 Mbit~2 Gbit|64 Mbit~2 Gbit|大|大|
|升级便利性|好|好|好|一般|好|

### 4.2 QSPI 三种工作模式对比

|模式|CPU 访问方式|适合场景|优点|缺点|
|---|---|---|---|---|
|间接模式|读写 FIFO/寄存器|擦除、编程、ID 读取|控制清晰、兼容性高|CPU 参与多|
|DMA 间接模式|DMA 搬运 FIFO|大块读写、资源加载|CPU 占用低|Cache/中断复杂|
|Memory-Mapped|直接访问映射地址|XIP、资源随机访问|使用简单、随机访问方便|擦写时通常不能继续访问|

### 4.3 常见 Flash 指令对比

|操作|典型指令|说明|
|---|---|---|
|Read JEDEC ID|`0x9F`|读取厂商、容量、类型|
|Write Enable|`0x06`|置位 WEL|
|Read Status Register|`0x05`|读取 BUSY/WEL 等|
|Write Status Register|`0x01`|写状态寄存器|
|Read Data|`0x03`|普通单线读取|
|Fast Read|`0x0B`|带 Dummy Cycle|
|Quad Output Read|`0x6B`|输出阶段四线|
|Quad I/O Read|`0xEB`|地址和数据阶段四线|
|Page Program|`0x02`|单线页编程|
|Quad Page Program|`0x32`|四线页编程|
|Sector Erase|`0x20`|4 KB 擦除|
|Block Erase|`0xD8`|64 KB 擦除|
|Chip Erase|`0xC7/0x60`|整片擦除|
|Reset Enable|`0x66`|允许复位|
|Reset|`0x99`|Flash 软件复位|

---

## 5. 底层原理与功能特性深度解析

## 5.1 QSPI 命令帧结构

一个典型 Quad I/O Read 命令可能是：

```
CS 拉低
┌────────┬────────────┬────────┬──────────────┐
│ 指令   │ 地址       │ 模式   │ Dummy Cycle  │ 数据
│ 8 bit  │ 24/32 bit  │ 8 bit  │ 4~20 cycles  │ N bytes
└────────┴────────────┴────────┴──────────────┘
CS 拉高
```

例如 `0xEB`：

```
Instruction : 0xEB，1-1-4 或 1-4-4，取决于 Flash
Address     : 24 bit / 32 bit
Mode        : 可选
Dummy       : 6~20 个时钟周期
Data        : 4 线输出
```

**最容易出错的地方是协议模式匹配。** MCU 配置的 Instruction Mode、Address Mode、Data Mode 必须与 Flash Datasheet 中定义一致。

---

## 5.2 NOR Flash 内部状态机

NOR Flash 通常包含以下关键状态：

```
IDLE
  │
  ├── Write Enable ──> WEL=1
  │                         │
  │                         ├── Page Program ──> BUSY=1
  │                         └── Erase ────────> BUSY=1
  │
  └── Reset ───────────────> IDLE
```

状态寄存器常见位：

```
Bit 0: WIP/BUSY
Bit 1: WEL
Bit 2~5: Block Protect
Bit 6: QE，部分厂商放在 SR2
Bit 7: Status Register Protect
```

### 工程要求

- 所有 Program/Erase 操作前都必须执行 `Write Enable`。
- 执行后必须轮询 `BUSY`。
- `Write Enable` 不能跨越过长时间，否则 WEL 可能被硬件清除。
- 擦除和编程期间，不应从同一颗 Flash 的 Memory-Mapped 区域取指。
- 轮询必须带超时，禁止无限等待。

---

## 5.3 基础数据结构

下面使用通用抽象，不绑定某个 MCU 厂商 HAL：

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef enum {
    QSPI_OK = 0,
    QSPI_ERR_PARAM,
    QSPI_ERR_TIMEOUT,
    QSPI_ERR_BUSY,
    QSPI_ERR_IO,
    QSPI_ERR_ID,
    QSPI_ERR_UNSUPPORTED,
    QSPI_ERR_VERIFY
} qspi_status_t;

typedef struct {
    uint8_t manufacturer_id;
    uint8_t memory_type;
    uint8_t capacity_id;

    uint32_t total_size;
    uint32_t page_size;
    uint32_t sector_size;
    uint32_t block_size;

    uint32_t max_read_hz;
    uint32_t max_program_hz;
    uint8_t address_bytes;
    uint8_t qe_required;
} qspi_flash_info_t;

typedef struct {
    qspi_status_t (*command)(const uint8_t *cmd,
                             size_t cmd_len,
                             void *rx,
                             size_t rx_len,
                             uint32_t timeout_ms);

    qspi_status_t (*write)(const uint8_t *cmd,
                           size_t cmd_len,
                           const void *tx,
                           size_t tx_len,
                           uint32_t timeout_ms);

    qspi_status_t (*read)(const uint8_t *cmd,
                          size_t cmd_len,
                          void *rx,
                          size_t rx_len,
                          uint32_t timeout_ms);

    void (*delay_ms)(uint32_t ms);
    uint32_t (*get_tick_ms)(void);
} qspi_bus_ops_t;

typedef struct {
    qspi_bus_ops_t bus;
    qspi_flash_info_t info;
    void *lock;
    bool initialized;
} qspi_flash_t;
```

该架构把以下内容隔离：

- MCU QSPI 控制器；
- Flash 命令协议；
- RTOS 互斥锁；
- 具体厂商 Flash 参数；
- 上层 OTA、文件系统和资源管理器。

---

## 5.4 JEDEC ID 读取

```
#define CMD_READ_JEDEC_ID  0x9FU

static qspi_status_t qspi_flash_read_id(qspi_flash_t *flash)
{
    if (flash == NULL) {
        return QSPI_ERR_PARAM;
    }

    uint8_t cmd = CMD_READ_JEDEC_ID;
    uint8_t id[3] = {0};

    qspi_status_t ret = flash->bus.read(
        &cmd,
        1U,
        id,
        sizeof(id),
        100U
    );

    if (ret != QSPI_OK) {
        return ret;
    }

    flash->info.manufacturer_id = id[0];
    flash->info.memory_type     = id[1];
    flash->info.capacity_id    = id[2];

    /*
     * 生产环境不能只判断 manufacturer_id。
     * 同一厂商不同系列的擦除、QE、Dummy Cycle 可能不同。
     */
    if (id[0] == 0xEFU && id[1] == 0x40U) {
        flash->info.total_size = 1UL << id[2];
        flash->info.page_size = 256U;
        flash->info.sector_size = 4096U;
        flash->info.block_size = 65536U;
        flash->info.address_bytes = 3U;
        flash->info.qe_required = 1U;
    } else {
        return QSPI_ERR_UNSUPPORTED;
    }

    return QSPI_OK;
}
```

### 工程注意事项

- JEDEC ID 的第三个字节通常是容量编码，但不能简单对所有厂商使用 `1 << id[2]`。
- 部分 Flash 使用 SFDP 提供参数。
- 部分大容量 Flash 需要 4-byte Address Mode。
- 读取 ID 失败时，应尝试：
    1. 检查 CS 是否被拉高；
    2. 降低 QSPI 时钟；
    3. 执行 Flash Reset；
    4. 检查 IO2/IO3 是否被复用为 WP/HOLD；
    5. 检查供电和复位时序。

---

## 5.5 Write Enable 与状态轮询

```
#define CMD_WRITE_ENABLE       0x06U
#define CMD_READ_STATUS_REG1   0x05U

#define SR1_BUSY_MASK           0x01U
#define SR1_WEL_MASK            0x02U

static qspi_status_t qspi_flash_write_enable(qspi_flash_t *flash)
{
    uint8_t cmd = CMD_WRITE_ENABLE;

    qspi_status_t ret = flash->bus.command(
        &cmd,
        1U,
        NULL,
        0U,
        100U
    );

    if (ret != QSPI_OK) {
        return ret;
    }

    uint8_t status = 0U;
    uint32_t start = flash->bus.get_tick_ms();

    while (1) {
        uint8_t sr_cmd = CMD_READ_STATUS_REG1;

        ret = flash->bus.read(
            &sr_cmd,
            1U,
            &status,
            1U,
            100U
        );

        if (ret != QSPI_OK) {
            return ret;
        }

        if ((status & SR1_BUSY_MASK) == 0U &&
            (status & SR1_WEL_MASK) != 0U) {
            return QSPI_OK;
        }

        if ((flash->bus.get_tick_ms() - start) > 100U) {
            return QSPI_ERR_TIMEOUT;
        }
    }
}

static qspi_status_t qspi_flash_wait_ready(qspi_flash_t *flash,
                                            uint32_t timeout_ms)
{
    uint32_t start = flash->bus.get_tick_ms();

    while (1) {
        uint8_t cmd = CMD_READ_STATUS_REG1;
        uint8_t status = 0U;

        qspi_status_t ret = flash->bus.read(
            &cmd,
            1U,
            &status,
            1U,
            100U
        );

        if (ret != QSPI_OK) {
            return ret;
        }

        if ((status & SR1_BUSY_MASK) == 0U) {
            return QSPI_OK;
        }

        if ((flash->bus.get_tick_ms() - start) >= timeout_ms) {
            /*
             * 超时后不能直接继续发新命令。
             * 应进入错误恢复流程，例如复位 Flash、重新初始化 QSPI。
             */
            return QSPI_ERR_TIMEOUT;
        }
    }
}
```

### 为什么不能只延时固定时间？

固定延时的问题：

```
HAL_Delay(3);
```

原因：

- 不同温度下擦除时间不同；
- 不同容量和工艺的 Flash 时间不同；
- 电源波动会导致内部操作变慢；
- 任务调度会增加延迟；
- 固定时间过短导致读写冲突；
- 固定时间过长降低系统吞吐率。

正确方法是：

```
发起操作
  ↓
读取 BUSY
  ↓
BUSY=1：继续轮询
  ↓
BUSY=0：操作完成
  ↓
超过最大规格时间：错误恢复
```

---

## 5.6 页编程边界处理

NOR Flash 的 Page Program 通常有两个关键限制：

1. 一次编程不能超过一个 Page。
2. 数据跨越 Page 边界时，很多 Flash 会发生地址回卷。

例如 Page Size 为 256 字节：

```
起始地址：0x01F0
长度：32 字节
```

实际跨越：

```
0x01F0 ~ 0x01FF：16 字节
0x0100 ~ 0x010F：可能回卷覆盖
```

因此必须自动拆包。

```
#define CMD_PAGE_PROGRAM 0x02U

static qspi_status_t qspi_flash_program_page(qspi_flash_t *flash,
                                              uint32_t address,
                                              const uint8_t *data,
                                              size_t length)
{
    if (flash == NULL || data == NULL || length == 0U) {
        return QSPI_ERR_PARAM;
    }

    if (length > flash->info.page_size) {
        return QSPI_ERR_PARAM;
    }

    qspi_status_t ret = qspi_flash_write_enable(flash);
    if (ret != QSPI_OK) {
        return ret;
    }

    uint8_t cmd[5];
    size_t cmd_len = 1U + flash->info.address_bytes;

    cmd[0] = CMD_PAGE_PROGRAM;

    if (flash->info.address_bytes == 3U) {
        cmd[1] = (uint8_t)(address >> 16);
        cmd[2] = (uint8_t)(address >> 8);
        cmd[3] = (uint8_t)(address);
    } else {
        cmd[1] = (uint8_t)(address >> 24);
        cmd[2] = (uint8_t)(address >> 16);
        cmd[3] = (uint8_t)(address >> 8);
        cmd[4] = (uint8_t)(address);
    }

    ret = flash->bus.write(
        cmd,
        cmd_len,
        data,
        length,
        100U
    );

    if (ret != QSPI_OK) {
        return ret;
    }

    return qspi_flash_wait_ready(flash, 100U);
}

qspi_status_t qspi_flash_program(qspi_flash_t *flash,
                                 uint32_t address,
                                 const void *buffer,
                                 size_t length)
{
    if (flash == NULL || buffer == NULL || length == 0U) {
        return QSPI_ERR_PARAM;
    }

    if (address >= flash->info.total_size ||
        length > flash->info.total_size - address) {
        return QSPI_ERR_PARAM;
    }

    const uint8_t *src = (const uint8_t *)buffer;

    while (length > 0U) {
        size_t page_offset = address % flash->info.page_size;
        size_t remain_in_page = flash->info.page_size - page_offset;
        size_t chunk = length < remain_in_page ? length : remain_in_page;

        qspi_status_t ret = qspi_flash_program_page(
            flash,
            address,
            src,
            chunk
        );

        if (ret != QSPI_OK) {
            return ret;
        }

        address += (uint32_t)chunk;
        src += chunk;
        length -= chunk;
    }

    return QSPI_OK;
}
```

---

## 5.7 擦除操作

擦除前必须满足：

```
目标地址对齐
目标范围合法
Flash 不处于 BUSY
发送 Write Enable
发送 Erase 指令
等待 BUSY 清零
```

```
#define CMD_SECTOR_ERASE 0x20U

static qspi_status_t qspi_flash_erase_sector(qspi_flash_t *flash,
                                             uint32_t address)
{
    if (flash == NULL) {
        return QSPI_ERR_PARAM;
    }

    if ((address % flash->info.sector_size) != 0U) {
        return QSPI_ERR_PARAM;
    }

    qspi_status_t ret = qspi_flash_write_enable(flash);
    if (ret != QSPI_OK) {
        return ret;
    }

    uint8_t cmd[4];
    cmd[0] = CMD_SECTOR_ERASE;
    cmd[1] = (uint8_t)(address >> 16);
    cmd[2] = (uint8_t)(address >> 8);
    cmd[3] = (uint8_t)address;

    ret = flash->bus.command(
        cmd,
        sizeof(cmd),
        NULL,
        0U,
        100U
    );

    if (ret != QSPI_OK) {
        return ret;
    }

    /*
     * 4 KB Sector Erase 典型耗时：
     * 20~400 ms，具体取决于器件和温度。
     */
    return qspi_flash_wait_ready(flash, 1000U);
}
```

### 擦除粒度选择

|擦除方式|典型容量|典型时间|适用场景|
|---|---|---|---|
|4 KB Sector|4 KB|20~100 ms|参数、日志、小范围更新|
|32 KB Block|32 KB|100~500 ms|中等大小资源|
|64 KB Block|64 KB|100~1000 ms|OTA 镜像、大文件|
|Chip Erase|整片|数十秒|产线、量产初始化|

---

## 5.8 QE 位与 IO2/IO3 复用

四线模式通常需要设置 QE，Quad Enable。

但不同厂商可能存在以下差异：

|厂商/系列|QE 位置|写入方式|
|---|---|---|
|某些 Winbond|SR2 Bit1|写 SR1/SR2|
|某些 Macronix|SR1 Bit6|写状态寄存器|
|某些 GigaDevice|SR2 Bit1|特定写寄存器命令|
|某些 Cypress/Infineon|配置寄存器|可能使用不同命令|
|某些新器件|默认启用|无需修改|

**不能仅凭 Flash 厂商名称推断 QE 配置方式。必须读取对应 Datasheet。**

示意代码：

```
#define CMD_READ_STATUS_REG2 0x35U
#define CMD_WRITE_STATUS     0x01U
#define QE_MASK              0x02U

static qspi_status_t qspi_flash_enable_quad(qspi_flash_t *flash)
{
    uint8_t cmd = CMD_READ_STATUS_REG2;
    uint8_t sr2 = 0U;

    qspi_status_t ret = flash->bus.read(
        &cmd,
        1U,
        &sr2,
        1U,
        100U
    );

    if (ret != QSPI_OK) {
        return ret;
    }

    if ((sr2 & QE_MASK) != 0U) {
        return QSPI_OK;
    }

    ret = qspi_flash_write_enable(flash);
    if (ret != QSPI_OK) {
        return ret;
    }

    uint8_t sr1_cmd = 0x05U;
    uint8_t sr1 = 0U;

    ret = flash->bus.read(&sr1_cmd, 1U, &sr1, 1U, 100U);
    if (ret != QSPI_OK) {
        return ret;
    }

    uint8_t write_cmd[3];
    write_cmd[0] = CMD_WRITE_STATUS;
    write_cmd[1] = sr1;
    write_cmd[2] = (uint8_t)(sr2 | QE_MASK);

    ret = flash->bus.command(
        write_cmd,
        sizeof(write_cmd),
        NULL,
        0U,
        100U
    );

    if (ret != QSPI_OK) {
        return ret;
    }

    return qspi_flash_wait_ready(flash, 100U);
}
```

---

## 5.9 Memory-Mapped Mode 与 XIP

### 内存映射原理

QSPI 控制器将一个外部地址区间映射为：

```
CPU 地址 0x90000000
        ↓
QSPI 控制器
        ↓
Flash 地址 0x00000000
```

CPU 执行：

```
uint32_t value = *(volatile uint32_t *)0x90010000U;
```

控制器内部自动生成：

```
Read Command
Address = 0x00010000
Dummy Cycle
Receive Data
```

### XIP 的优势

- 不占用内部 Flash 空间；
- 可以运行大型应用；
- 支持大型资源和插件式代码；
- 降低内部存储成本。

### XIP 的风险

1. **随机访问延迟显著高于内部 Flash**
    
     
    
    内部 Flash 可能只需几个 CPU 周期，而 QSPI 每次 Cache Line Miss 都需要完整总线事务。
    
2. **擦除/编程期间无法从同一 Flash 取指**
    
     
    
    如果正在执行外部 Flash 中的代码，又对该 Flash 擦除，会导致：
    
    - BusFault；
    - CPU 卡死；
    - QSPI 控制器返回无效数据；
    - 看门狗复位。
3. **Cache 一致性问题**
    
     
    
    Memory-Mapped 数据被 DMA 修改后，CPU Cache 中仍可能保留旧数据。
    
4. **电源和时钟依赖**
    
     
    
    XIP 代码运行期间，不能随意关闭 QSPI 时钟或切换引脚复用。
    

### XIP 安全执行框架

```
__attribute__((section(".itcm_text")))
static void flash_program_critical_code(void)
{
    /*
     * 此函数必须放到内部 Flash 或 ITCM/RAM。
     * 不能从正在擦写的外部 Flash 执行。
     */
}

__attribute__((section(".ram_data")))
static uint8_t qspi_cmd_buffer[256];
```

链接脚本示意：

```
.itcm_text :
{
    *(.itcm_text)
} > ITCM

.ram_data :
{
    *(.ram_data)
} > RAM
```

---

## 5.10 Cache 与 DMA 一致性

假设 QSPI 映射区为 Normal Memory，CPU 读取了某个 Cache Line：

```
外部 Flash：新数据
CPU Cache ：旧数据
```

此时外部 Flash 被重新编程或 DMA 更新，CPU 仍然可能读取旧 Cache 内容。

### 读取前失效

```
void qspi_cache_invalidate(void *addr, size_t len)
{
    uintptr_t start = (uintptr_t)addr;
    uintptr_t end = start + len;

    start &= ~(uintptr_t)31U;
    end = (end + 31U) & ~(uintptr_t)31U;

    SCB_InvalidateDCache_by_Addr(
        (uint32_t *)start,
        (int32_t)(end - start)
    );

    __DSB();
    __ISB();
}
```

### DMA 发送前清理

```
void qspi_dma_tx_prepare(const void *addr, size_t len)
{
    uintptr_t start = (uintptr_t)addr;
    uintptr_t end = start + len;

    start &= ~(uintptr_t)31U;
    end = (end + 31U) & ~(uintptr_t)31U;

    SCB_CleanDCache_by_Addr(
        (uint32_t *)start,
        (int32_t)(end - start)
    );

    __DSB();
}
```

### 工程建议

- QSPI Memory-Mapped 区可配置为 Cacheable。
- DMA 描述符和 DMA 缓冲区最好放到 Non-Cacheable 区。
- 如果 MPU 配置复杂，优先使用明确的 Cache Maintenance API。
- `volatile` 不能解决 Cache 一致性问题。`volatile` 只约束编译器，不会刷新 CPU Cache。

---

## 6. 性能量化分析

## 6.1 理论吞吐率

### SDR 四线模式

Bideal=4×fSCK8Bideal​=84×fSCK​​

80 MHz 时：

Bideal=40 MB/sBideal​=40 MB/s

### 加入命令、地址和 Dummy 开销

一次读取总周期：

Ctotal=Ccmd+Caddr+Cmode+Cdummy+CdataCtotal​=Ccmd​+Caddr​+Cmode​+Cdummy​+Cdata​

有效效率：

η=CdataCtotalη=Ctotal​Cdata​​

假设：

- 指令：8 bit 单线，8 周期；
- 地址：24 bit 四线，6 周期；
- Dummy：8 周期；
- 数据：256 Byte，512 周期；

则：

Ctotal=8+6+8+512=534Ctotal​=8+6+8+512=534η=512534=95.9%η=534512​=95.9%

大块顺序读取时效率很高；但读取 4 Byte 时：

Cdata=8 cyclesCdata​=8 cyclesη=88+6+8+8=26.7%η=8+6+8+88​=26.7%

因此：

> **QSPI 擅长大块顺序读取，不擅长大量细粒度随机访问。**

---

## 6.2 典型实测数据

以下数据以常见 Cortex-M7、QSPI NOR Flash、80 MHz SDR、四线读取为参考，实际数值依赖 MCU、Flash、Cache 和 PCB。

|操作|典型数据|
|---|---|
|JEDEC ID 读取|5~20 μs|
|4 KB Sector Erase|20~150 ms|
|64 KB Block Erase|100~1000 ms|
|Page Program 256 B|0.3~3 ms|
|间接模式读取|10~25 MB/s|
|DMA 读取|25~38 MB/s|
|Memory-Mapped 顺序读取|30~42 MB/s|
|Cache 命中随机读取|约 1~10 ns 等效|
|Cache Miss 随机读取|0.2~2 μs|
|片内 Flash 读取|约 1~3 CPU 周期/字|

### 重要结论

- **Memory-Mapped 顺序读取不等于 CPU 实际执行吞吐率。**
- XIP 的性能通常受 Cache Line Fill 和指令分支影响。
- 代码执行比数据连续读取更容易出现 Cache Miss。
- 擦除时间通常远高于编程时间，是 OTA 和日志系统的主要瓶颈。

---

## 6.3 时间模型

对于一次 QSPI 读操作：

Tread=Tsetup+CprotocolfSCK+8NLfSCKTread​=Tsetup​+fSCK​Cprotocol​​+LfSCK​8N​

其中：

- TsetupTsetup​：控制器配置和 CS 建立时间；
- CprotocolCprotocol​：命令、地址和 Dummy 周期；
- NN：数据字节数；
- LL：数据线数量。

对于页编程：

Tprogram=Ttransfer+Tinternal-programTprogram​=Ttransfer​+Tinternal-program​

当数据量大于几十字节时，内部编程时间通常占主导。

对于擦除：

Terase≫Tprogram≫TreadTerase​≫Tprogram​≫Tread​

---

## 6.4 瓶颈分析

### 瓶颈一：时钟频率过低

优化：

- 提高 QSPI 时钟；
- 优化 PCB 走线；
- 配置正确采样边沿；
- 使用 Delay Block；
- 增加驱动强度；
- 降低 IO 负载。

### 瓶颈二：Dummy Cycle 配置错误

表现：

- 低速正常，高速错误；
- 连续数据出现固定偏移；
- 首字节错误；
- 地址附近数据正确但后续错误。

优化：

- 按 Flash 当前频率配置 Dummy Cycle；
- 不要直接使用 Datasheet 最大值；
- 对不同频率建立参数表；
- 使用逻辑分析仪确认实际协议。

### 瓶颈三：大量小块访问

错误模式：

```
for (uint32_t i = 0; i < 1024; ++i) {
    value[i] = *(volatile uint8_t *)(QSPI_BASE + offset + i);
}
```

如果每次访问都造成独立总线事务，效率很低。

优化：

- 按 Cache Line 对齐；
- 按 64~256 字节批量读取；
- 使用 DMA；
- 建立 RAM 缓存；
- 使用资源索引避免大量随机读取。

### 瓶颈四：擦除阻塞业务任务

优化：

- 后台擦除；
- 双缓冲；
- 分区轮换；
- 预擦除空闲块；
- 把日志写入 RAM 队列；
- 让高优先级任务不依赖正在擦除的 Flash。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要外部非易失存储？
├── 否
│   └── 使用内部 Flash / EEPROM / FRAM
└── 是
    ├── 是否需要直接执行代码？
    │   ├── 是
    │   │   ├── 代码是否超过内部 Flash 容量？
    │   │   │   ├── 是：QSPI Memory-Mapped + XIP
    │   │   │   └── 否：内部 Flash 优先，QSPI 存资源
    │   │   └── 是否要求高随机执行性能？
    │   │       ├── 是：QSPI + Cache / OPI / PSRAM
    │   │       └── 否：QSPI XIP
    │   └── 否
    │       ├── 是否以大块顺序读为主？
    │       │   ├── 是：QSPI + DMA
    │       │   └── 否
    │       │       ├── 是否频繁小数据更新？
    │       │       │   ├── 是：FRAM / EEPROM / 内部 Flash 参数区
    │       │       │   └── 否：QSPI NOR
    │       │
    │       └── 容量是否超过 256 MB？
    │           ├── 是：4-byte Address / OPI / SPI NAND
    │           └── 否：普通 QSPI NOR
```

## 7.2 典型场景

|场景|需求|方案|理由|
|---|---|---|---|
|MCU 外部代码|容量大、可 XIP|QSPI Memory-Mapped|可直接执行|
|OTA 双镜像|大容量、顺序读写|QSPI + DMA + CRC/SHA|容量和成本平衡|
|GUI 图片/字体|高频读取、随机访问|QSPI + Cache + 资源索引|资源加载方便|
|设备日志|追加写入、掉电恢复|QSPI NOR + 环形日志|成本低、容量大|
|高频参数更新|小数据、频繁写入|FRAM/EEPROM|避免 NOR 擦写寿命|
|音频播放|连续流读取|QSPI + DMA 双缓冲|满足持续带宽|
|大型 AI 模型|大容量顺序加载|Octal SPI / SPI NAND|QSPI 容量和带宽可能不足|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：硬件协议层与 Flash 器件层分离

```
QSPI Controller Driver
        ↓
Flash Transport Layer
        ↓
Flash Command Layer
        ↓
Partition Manager
        ↓
OTA / File System / Resource Manager
```

### 原则二：任何 BUSY 轮询必须有超时

禁止：

```
while (read_status() & BUSY) {
}
```

必须：

```
while (read_status() & BUSY) {
    if (timeout_expired()) {
        recover_flash();
        return QSPI_ERR_TIMEOUT;
    }
}
```

### 原则三：读写擦除接口必须进行边界检查

必须检查：

```
address < total_size
length <= total_size - address
erase_address % erase_size == 0
```

避免：

```
if (address + length > total_size)
```

因为 `address + length` 可能发生整数溢出。

### 原则四：擦除、编程期间禁止从同一 Flash 取指

应确保：

- QSPI 驱动位于内部 Flash 或 RAM；
- 中断向量和高优先级中断不位于外部 Flash；
- RTOS 调度代码不依赖外部 Flash；
- 关键异常处理代码位于内部存储。

### 原则五：不要把 QSPI NOR 当作 EEPROM 使用

NOR Flash 具有：

- 页编程限制；
- 扇区擦除限制；
- 有限擦写寿命；
- 擦除前必须全 1；
- 写入只能将 bit 从 1 变为 0。

---

## 8.2 选型决策矩阵

|指标|权重|低需求方案|高需求方案|
|---|---|---|---|
|顺序读带宽|25%|QSPI SDR|OPI DDR|
|随机读延迟|20%|QSPI + Cache|内部 RAM/PSRAM|
|容量|20%|64 Mbit NOR|SPI NAND/eMMC|
|擦写寿命|15%|NOR + Wear Leveling|FRAM|
|实时性|10%|间接模式|内部 Flash/RAM|
|成本|10%|低速 SPI NOR|高速 OPI/并行存储|

---

## 8.3 工业级编码规范

- 所有 QSPI API 返回明确错误码。
- 所有超时采用单调递增 Tick。
- 不在驱动内部调用无限阻塞延时。
- 不在中断中执行擦除。
- 不在持有总线锁时执行长时间无关计算。
- 页编程自动处理 Page Boundary。
- 擦除接口要求显式对齐。
- 关键元数据保存版本号、长度、CRC、Magic。
- 对外部 Flash 读取进行范围校验。
- 对 XIP 区域配置 MPU 属性。
- 对 DMA 缓冲区进行 Cache 对齐。
- 使用静态分析工具检查地址溢出和边界问题。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：跨页编程

### 错误代码

```
void flash_write(uint32_t addr, const uint8_t *data, uint32_t len)
{
    write_enable();
    page_program(addr, data, len);
}
```

### 根因

没有处理：

```
页内剩余空间 < len
```

Flash 可能发生地址回卷。

### 正确实现

将数据拆分为：

```
page_remaining = page_size - (addr % page_size);
chunk = MIN(len, page_remaining);
```

### 风险影响

- 数据覆盖；
- 镜像校验失败；
- 配置结构损坏；
- 故障具有随机性，难以复现。

---

## 9.2 错误二：未设置 QE 位

### 错误代码

```
qspi_configure_quad_mode();
read_quad_data();
```

### 根因

MCU 已进入四线模式，但 Flash IO2/IO3 仍然是 WP/HOLD 或未启用 Quad。

### 正确实现

```
读取器件 ID
  ↓
读取 QE 当前状态
  ↓
如未设置：Write Enable
  ↓
按厂商协议写 QE
  ↓
等待 BUSY 清零
  ↓
重新初始化 QSPI Quad 模式
```

### 风险影响

- 读取全 `0xFF`；
- 读取全 `0x00`；
- 数据错位；
- 低速单线正常、高速四线异常。

---

## 9.3 错误三：忽略擦除操作

### 错误代码

```
flash_program(addr, data, len);
```

### 根因

NOR Flash 只能将 bit 从 1 写为 0，不能直接将 0 写回 1。

### 正确实现

```
flash_erase_sector(align_down(addr, 4096U));
flash_program(addr, data, len);
```

更工业化的实现应先判断目标区域是否已经是擦除态：

```
if (need_erase(old_data, new_data)) {
    erase_sector();
}
program_pages();
```

### 风险影响

- 写入结果不等于目标数据；
- 校验偶发失败；
- 参数更新后旧 bit 无法恢复。

---

## 9.4 错误四：擦写期间继续 XIP

### 错误代码

```
void ota_write_image(void)
{
    flash_erase_sector(image_addr);
    flash_program(image_addr, buffer, size);
}
```

同时当前程序本身位于 QSPI XIP 区域。

### 根因

CPU 在执行 QSPI 擦除或编程期间仍然需要从同一 Flash 读取指令。

### 正确实现

- 将 QSPI 驱动放入内部 Flash/RAM；
- 将中断服务函数放入内部存储；
- 擦写期间禁止访问外部 Flash 代码；
- 必要时切换到 Bootloader 或内部安全执行区。

### 风险影响

- HardFault；
- 总线死锁；
- 看门狗超时；
- 系统无法恢复。

---

## 9.5 错误五：DMA 与 Cache 不一致

### 错误代码

```
memcpy(qspi_buffer, src, size);
qspi_dma_start(qspi_buffer, size);
```

### 根因

CPU 修改的数据仍停留在 D-Cache，DMA 从 RAM 读取到旧数据。

### 正确实现

```
memcpy(qspi_buffer, src, size);
qspi_dma_tx_prepare(qspi_buffer, size);
qspi_dma_start(qspi_buffer, size);
```

### 风险影响

- OTA 镜像 CRC 错误；
- 数据偶发错误；
- 仅在开启 Cache 和 DMA 时出现。

---

## 9.6 错误六：固定 Dummy Cycle

### 错误代码

```
qspi_set_dummy_cycles(8);
qspi_set_clock(133000000U);
```

### 根因

Dummy Cycle 与：

- Flash 型号；
- QSPI 时钟；
- 读命令；
- 电压；
- 温度；
- 采样延迟；

有关，不能固定照搬。

### 正确实现

```
dummy = flash_profile_get_dummy_cycles(
    jedec_id,
    read_mode,
    qspi_clock
);
qspi_set_dummy_cycles(dummy);
```

### 风险影响

- 高温/低温下异常；
- 某些板卡正常、某些板卡失败；
- 量产后现场偶发数据错误。

---

## 10. 多机制组合使用方案

## 10.1 QSPI + DMA + Cache + RTOS 组合架构

```
应用任务
  ↓
QSPI Service Layer
  ↓
Mutex + Request Queue
  ↓
Flash Command Layer
  ↓
QSPI Controller + DMA
  ↓
External NOR Flash
```

### 设计目标

- 同一时刻只有一个事务访问 QSPI。
- 大块读取使用 DMA。
- 小块状态命令使用 CPU PIO。
- 读写擦除请求统一排队。
- DMA 完成通过中断通知任务。
- Cache 操作由驱动封装，不暴露给业务层。

### 请求结构

```
typedef enum {
    QSPI_REQ_READ,
    QSPI_REQ_PROGRAM,
    QSPI_REQ_ERASE
} qspi_req_type_t;

typedef struct {
    qspi_req_type_t type;
    uint32_t address;
    void *buffer;
    size_t length;
    uint32_t timeout_ms;
    qspi_status_t result;
    void *completion;
} qspi_request_t;
```

### 服务任务框架

```
static void qspi_service_task(void *argument)
{
    qspi_request_t req;

    for (;;) {
        if (queue_receive(&req, portMAX_DELAY) != true) {
            continue;
        }

        mutex_lock(qspi_mutex, portMAX_DELAY);

        switch (req.type) {
        case QSPI_REQ_READ:
            /*
             * 大于阈值时使用 DMA。
             * 小于阈值时使用 PIO，减少 DMA 配置开销。
             */
            if (req.length >= 64U) {
                qspi_cache_invalidate(req.buffer, req.length);
                req.result = qspi_read_dma(
                    req.address,
                    req.buffer,
                    req.length,
                    req.timeout_ms
                );
            } else {
                req.result = qspi_read_pio(
                    req.address,
                    req.buffer,
                    req.length,
                    req.timeout_ms
                );
            }
            break;

        case QSPI_REQ_PROGRAM:
            qspi_cache_clean(req.buffer, req.length);
            req.result = qspi_flash_program(
                &g_flash,
                req.address,
                req.buffer,
                req.length
            );
            break;

        case QSPI_REQ_ERASE:
            req.result = qspi_erase_range(
                req.address,
                req.length,
                req.timeout_ms
            );
            break;

        default:
            req.result = QSPI_ERR_PARAM;
            break;
        }

        mutex_unlock(qspi_mutex);
        event_signal(req.completion);
    }
}
```

### 组合设计模式

|机制|解决问题|
|---|---|
|Mutex|解决多个任务并发访问|
|Queue|解耦业务请求与硬件访问|
|DMA|降低 CPU 搬运开销|
|Cache Maintenance|解决数据一致性|
|Memory-Mapped|简化随机读取|
|Background Erase|降低业务阻塞|
|CRC/SHA|验证数据完整性|
|Watchdog|防止硬件永久卡死|
|Telemetry|统计超时和错误率|

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业控制器 XIP 应用代码

### 需求

- MCU 内部 Flash 只有 1 MB；
- 应用代码 2.5 MB；
- 外部 QSPI NOR 为 8 MB；
- 上电后直接运行主应用；
- 需要保留安全启动和回滚能力。

### 架构

```
内部 Flash
├── Bootloader
├── 公钥与安全配置
└── Recovery Code

外部 QSPI Flash
├── App Slot A
├── App Slot B
├── 镜像元数据
└── 资源区
```

### 关键设计

- Bootloader 位于内部 Flash；
- App A/B 支持 XIP；
- 升级时写入非活动分区；
- 写入完成后计算 SHA-256；
- 校验签名；
- 设置启动标志；
- 新版本启动失败则回滚。

### 启动元数据

```
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t image_addr;
    uint32_t image_size;
    uint32_t image_crc32;
    uint32_t state;
    uint8_t signature[64];
} boot_record_t;
```

### 设计要点

- 元数据不能只保存一份，应使用双副本。
- 状态更新必须采用单调状态机：

```
EMPTY
  ↓
DOWNLOADING
  ↓
VERIFIED
  ↓
PENDING_BOOT
  ↓
CONFIRMED
```

- 外部 Flash 掉电时，Bootloader 必须能够识别半写状态。
- XIP 代码不能在运行期间擦写自身所在分区。

---

## 11.2 案例二：工业 HMI 图形资源加载

### 需求

- 480×272 LCD；
- 图片、字体资源约 6 MB；
- 资源随机读取频繁；
- UI 刷新周期 16.7 ms；
- 不希望资源加载阻塞控制任务。

### 架构

```
QSPI NOR
├── Resource Header
├── Image Index
├── Compressed Images
├── Font Tables
└── CRC Metadata

RAM
├── 资源索引缓存
├── 图片解压缓冲区 A
└── 图片解压缓冲区 B
```

### 设计策略

- 资源索引常驻 RAM；
- 图像按 4~32 KB 分块；
- QSPI 使用 DMA；
- 双缓冲异步加载；
- CPU 在处理 Buffer A 时，DMA 读取 Buffer B；
- 图片数据使用 CRC 校验；
- 高频资源预加载到 SRAM/PSRAM。

### 性能计算

假设：

- 一帧图像压缩数据 64 KB；
- QSPI 有效读取速率 30 MB/s；

读取时间：

T=64 KB30 MB/s≈2.13 msT=30 MB/s64 KB​≈2.13 ms

如果解压需要 4 ms，则双缓冲可以把总耗时接近：

Tframe≈max⁡(2.13,4)=4 msTframe​≈max(2.13,4)=4 ms

而不是：

2.13+4=6.13 ms2.13+4=6.13 ms

---

## 11.3 案例三：设备日志环形存储

### 需求

- 每秒产生 2 KB 日志；
- 保留最近 30 天；
- 不能每条日志都擦除；
- 支持异常掉电恢复；
- 需要限制擦写集中在少数扇区。

### 容量估算

每天数据量：

2 KB/s×86400=172.8 MB/day2 KB/s×86400=172.8 MB/day

30 天：

172.8×30=5184 MB172.8×30=5184 MB

此时普通 64 MB QSPI NOR 明显不够，需要：

- 降低日志频率；
- 压缩日志；
- 使用更大容量 NOR；
- 使用 SPI NAND/eMMC；
- 只保存事件日志而非全量采样。

### NOR 适用的优化方式

- RAM 聚合 4 KB 或 16 KB 后批量写入；
- 使用日志块头；
- 块内追加写；
- 每块包含序号、首条时间戳、CRC；
- 采用块轮换和磨损均衡。

```
typedef struct {
    uint32_t magic;
    uint32_t sequence;
    uint32_t valid_bytes;
    uint32_t crc32;
} log_block_header_t;
```

---

## 12. 高频问题深度答疑

## 问题一：QSPI 和 SPI 的本质区别是什么？

不是简单地“多了三根线”。

真正区别包括：

- Flash 命令协议阶段的线宽变化；
- 控制器对 Instruction/Address/Alternate/Data/Dummy 的独立配置；
- 硬件地址映射能力；
- FIFO、自动轮询、DMA 和 XIP 支持；
- 更高频率下的采样延迟和信号完整性要求。

---

## 问题二：QSPI Memory-Mapped 模式为什么会出现随机访问慢？

因为 CPU 的一次随机访问可能触发：

1. Cache Miss；
2. Cache Line Fill；
3. QSPI 命令发送；
4. 地址发送；
5. Dummy Cycle；
6. 数据接收；
7. Cache Line 写入；
8. CPU 恢复执行。

如果 Cache Line 为 32 字节，即使 CPU 只读取 4 字节，也可能触发一次完整的 32 字节外部事务。

因此：

- 顺序读取：效率高；
- 代码线性执行：较好；
- 大量分支和随机跳转：性能下降明显；
- 高频小数据随机访问：应复制到 RAM。

---

## 问题三：为什么 Quad I/O 读命令可能比 Quad Output 更快？

Quad Output 通常是：

```
Instruction：单线
Address：单线
Data：四线
```

Quad I/O 通常是：

```
Instruction：单线或四线
Address：四线
Data：四线
```

对于小数据读取，地址阶段占比不可忽略，因此 Quad I/O 可以减少地址传输周期，提高有效效率。但它对 Flash、控制器和 Dummy Cycle 配置要求更高，兼容性也更复杂。

---

## 问题四：QSPI 擦除期间是否一定不能读？

要区分不同设备和访问方式。

对于同一颗传统 SPI NOR：

- 正在擦除的区域不能正常读取；
- 很多器件在 BUSY 期间其他读取也不可用；
- QSPI 控制器可能阻塞；
- XIP 通常不可用。

部分高级 Flash 支持：

- Suspend/Resume；
- Read While Write；
- Dual Bank；
- 部分区域并行操作。

但不能默认支持，必须查看 Datasheet 的 RWW 说明。

---

## 问题五：为什么低速运行正常，高速运行异常？

常见原因：

- Dummy Cycle 不正确；
- 采样边沿不匹配；
- QSPI 时钟超过 Flash 最大频率；
- PCB 走线过长；
- IO 驱动能力不合适；
- 电源去耦不足；
- CS 高电平时间不足；
- 引脚复用冲突；
- 控制器 Delay Block 未校准；
- 温度导致时序裕量下降。

排查顺序建议：

```
降频
  ↓
确认单线模式
  ↓
确认 ID
  ↓
确认 Fast Read
  ↓
确认 QE
  ↓
确认 Quad Read
  ↓
逐步提高频率
  ↓
做温度和电压边界测试
```

---

## 问题六：为什么要使用 SFDP？

SFDP，Serial Flash Discoverable Parameters，允许 MCU 从 Flash 中读取标准化参数，包括：

- Flash 容量；
- Page Size；
- 支持的读命令；
- Dummy Cycle；
- 擦除粒度；
- 4-byte Address 支持；
- 电源和时序参数。

使用 SFDP 可以减少对固定型号表的依赖，但仍需注意：

- 部分老旧 Flash 的 SFDP 不完整；
- 厂商私有配置仍无法完全标准化；
- QE 位位置可能仍需厂商专用处理；
- Bootloader 必须保留最小兼容路径。

---

## 13. 课程核心总结

### 核心要点

1. **QSPI 是协议线宽、控制器架构和存储访问模型的组合，而不仅是四根数据线。**
2. **NOR Flash 的 Page Program、Sector Erase、BUSY、WEL 和 QE 是驱动设计的核心。**
3. **所有编程都必须处理 Page Boundary。**
4. **所有擦除和编程都必须使用超时轮询。**
5. **Memory-Mapped 适合 XIP 和随机读取，但不能掩盖 Cache Miss 和外部总线延迟。**
6. **DMA 必须配合 Cache Maintenance。**
7. **擦写 QSPI Flash 时，不能从同一 Flash 执行代码。**
8. **Dummy Cycle、QE、地址宽度和命令线宽必须按具体 Flash 型号适配。**
9. **QSPI 擅长大块顺序读取，不适合高频小数据更新。**
10. **高可靠系统应具备错误恢复、CRC/SHA、掉电保护和擦写均衡。**

### 性能排序

在典型 MCU 系统中：

```
内部 SRAM
  >
内部 Flash
  >
QSPI Cache 命中
  >
QSPI Memory-Mapped 顺序读取
  >
QSPI Cache Miss 随机读取
  >
QSPI Page Program
  >
QSPI Sector Erase
```

### 通用选型结论

- **代码执行：** 内部 Flash 优先，容量不足时使用 QSPI XIP。
- **大块资源读取：** QSPI + DMA。
- **小块频繁更新：** FRAM/EEPROM 或 RAM 聚合后批量写入。
- **大型模型或超大容量：** 考虑 Octal SPI、SPI NAND、eMMC。
- **工业级 OTA：** 双分区、CRC/SHA、签名校验、状态机和回滚机制缺一不可。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|应用场景|主要需求|推荐方案|关键注意事项|
|---|---|---|---|
|读取 JEDEC ID|初始化识别、低数据量|间接模式 + PIO|上电延时、复位时序、CS 时序|
|读取状态寄存器|查询 BUSY/WEL/QE|间接模式 + PIO|轮询必须带超时|
|小块读取|1~32 字节控制数据|PIO 间接模式|避免为小事务配置 DMA|
|大块连续读取|OTA、音频、图片|QSPI + DMA|处理 Cache 一致性|
|随机读取资源|字体、图片索引、配置|Memory-Mapped + Cache|控制 Cache Miss 和访问粒度|
|外部代码执行|应用代码容量不足|Memory-Mapped + XIP|擦写期间不能从同一 Flash 取指|
|OTA 镜像写入|大容量、可靠升级|DMA + 分区管理 + CRC/SHA|双分区、断电恢复、回滚|
|小容量参数存储|参数更新频率低|QSPI NOR|擦除粒度和写入寿命|
|高频小数据更新|计数器、运行时间、标定值|FRAM/EEPROM|避免 NOR 频繁擦除|
|环形日志|追加写、掉电恢复|QSPI NOR + 日志块管理|磨损均衡、块序号、CRC|
|连续音频播放|稳定流式带宽|QSPI + DMA 双缓冲|缓冲区深度、欠载保护|
|大型 AI 模型|大容量、顺序读取|Octal SPI / SPI NAND / eMMC|ECC、坏块管理、启动时间|
|高性能 XIP|高指令带宽|OPI DDR + Cache|信号完整性、采样延迟、温度裕量|

---

### 14.2 QSPI 工作模式速查

|模式|指令|地址|数据|CPU 访问方式|典型用途|
|---|---|---|---|---|---|
|1-1-1|1 线|1 线|1 线|PIO/DMA|兼容性初始化|
|1-1-4|1 线|1 线|4 线|PIO/DMA|Quad Output Read|
|1-4-4|1 线|4 线|4 线|PIO/DMA/映射|Quad I/O Read|
|4-4-4|4 线|4 线|4 线|映射/XIP|高性能 Quad 协议|
|8-8-8 SDR|8 线|8 线|8 线|映射/DMA|Octal SPI|
|8-8-8 DDR|8 线|8 线|8 线|映射/XIP|高性能 OPI|

> 实际使用时，应以 Flash Datasheet 中的协议名称为准。MCU 手册中的 `Instruction Mode`、`Address Mode`、`Data Mode` 必须与 Flash 命令表严格匹配。

---

### 14.3 常用命令表

|操作|指令|是否需要 WREN|是否需要等待 BUSY|典型超时|
|---|---|---|---|---|
|Read JEDEC ID|`0x9F`|否|否|100 μs|
|Reset Enable|`0x66`|否|否|100 μs|
|Reset|`0x99`|否|通常需要|100 ms|
|Write Enable|`0x06`|否|检查 WEL|100 μs|
|Read Status Register 1|`0x05`|否|否|100 μs|
|Read Status Register 2|`0x35`|否|否|100 μs|
|Read Data|`0x03`|否|否|依数据量|
|Fast Read|`0x0B`|否|否|依数据量|
|Quad Output Read|`0x6B`|否|否|依数据量|
|Quad I/O Read|`0xEB`|否|否|依数据量|
|Page Program|`0x02`|是|是|3~10 ms|
|Quad Page Program|`0x32`|是|是|3~10 ms|
|Sector Erase|`0x20`|是|是|1 s|
|32 KB Block Erase|`0x52`|是|是|2 s|
|64 KB Block Erase|`0xD8`|是|是|3 s|
|Chip Erase|`0xC7`|是|是|60 s 以上|

---

### 14.4 核心参数公式

#### 理论吞吐率

Bideal=Nlane×fSCK×E8Bideal​=8Nlane​×fSCK​×E​

其中：

- NlaneNlane​：数据线数量；
- fSCKfSCK​：QSPI 时钟频率；
- EE：每个时钟周期的数据边沿数，SDR 为 1，DDR 为 2。

#### 有效吞吐率

Bactual=Bideal×ηprotocol×ηcontroller×ηsystemBactual​=Bideal​×ηprotocol​×ηcontroller​×ηsystem​

其中：

- ηprotocolηprotocol​：命令、地址、Dummy 等协议开销；
- ηcontrollerηcontroller​：FIFO、DMA、事务切换损耗；
- ηsystemηsystem​：Cache、总线仲裁、任务调度等损耗。

#### 单次读取时间

Tread=Tsetup+Ccmd+Caddr+CdummyfSCK+8NLfSCKTread​=Tsetup​+fSCK​Ccmd​+Caddr​+Cdummy​​+LfSCK​8N​

#### 页编程时间

Tprogram=Ttransfer+Tinternal-programTprogram​=Ttransfer​+Tinternal-program​

#### NOR Flash 擦写寿命

如果某个扇区最大擦除寿命为 NeraseNerase​，每天平均擦除次数为 RdayRday​，理论寿命为：

Dlife=NeraseRdayDlife​=Rday​Nerase​​

实际系统还需要考虑：

- 温度降额；
- 擦除分布不均；
- 掉电导致的重复写入；
- 磨损均衡效率；
- 坏块或失效概率。

---

### 14.5 QSPI 驱动检查清单

#### 初始化阶段

- [ ]  使能 QSPI 外设时钟。
- [ ]  配置 GPIO 复用和驱动能力。
- [ ]  检查 Flash 电源和复位时序。
- [ ]  将 QSPI 降到保守频率。
- [ ]  读取 JEDEC ID。
- [ ]  读取或配置地址宽度。
- [ ]  读取 QE 位。
- [ ]  必要时设置 QE。
- [ ]  配置 Dummy Cycle。
- [ ]  配置采样延迟或 Delay Block。
- [ ]  运行低速读写自检。
- [ ]  再切换到目标频率。

#### 读操作

- [ ]  检查地址和长度边界。
- [ ]  匹配正确的读命令。
- [ ]  配置正确的指令线宽、地址线宽和数据线宽。
- [ ]  配置正确 Dummy Cycle。
- [ ]  大块数据使用 DMA。
- [ ]  DMA 操作前后处理 Cache。
- [ ]  检查超时和总线错误。

#### 编程操作

- [ ]  检查地址范围。
- [ ]  拆分 Page Boundary。
- [ ]  执行 Write Enable。
- [ ]  检查 WEL。
- [ ]  发起 Page Program。
- [ ]  等待 BUSY 清零。
- [ ]  必要时回读校验。
- [ ]  统计编程失败次数。

#### 擦除操作

- [ ]  检查擦除地址对齐。
- [ ]  根据范围选择最优擦除粒度。
- [ ]  执行 Write Enable。
- [ ]  等待 BUSY 清零。
- [ ]  使用最大规格时间作为超时上限。
- [ ]  擦除失败后执行恢复流程。
- [ ]  避免在高优先级任务中同步擦除。

#### XIP 操作

- [ ]  确认链接脚本放置位置。
- [ ]  驱动代码位于内部 Flash 或 RAM。
- [ ]  中断向量和关键 ISR 不在正在擦写的 Flash。
- [ ]  正确配置 MPU。
- [ ]  正确处理 I-Cache 和 D-Cache。
- [ ]  避免执行期间关闭 QSPI 时钟。
- [ ]  设计 XIP 失败后的恢复路径。

---

### 14.6 常用状态位

|状态位|常见名称|含义|处理要求|
|---|---|---|---|
|SR1 Bit0|BUSY/WIP|内部编程或擦除进行中|必须等待清零|
|SR1 Bit1|WEL|写使能锁存|编程/擦除前必须为 1|
|SR1 Bit2~5|BP|写保护区域配置|防止误写|
|SR1 Bit7|SRWD|状态寄存器写保护|量产配置时确认|
|SR2 Bit1|QE|Quad Enable|Quad 模式通常必须设置|
|SR2 其他位|厂商相关|驱动强度、锁定、协议模式|查 Datasheet|

---

## 15. 学习效果自检

### 15.1 原理理解检查

能够解释：

- [ ]  为什么 QSPI 的理论带宽不等于实际带宽。
- [ ]  为什么小块随机访问时 Quad 模式收益有限。
- [ ]  为什么 QSPI 读命令通常需要 Dummy Cycle。
- [ ]  为什么 NOR Flash 编程前通常需要擦除。
- [ ]  为什么擦写期间不能从同一颗 Flash XIP。
- [ ]  为什么 `volatile` 不能解决 DMA 与 Cache 一致性。
- [ ]  为什么 QE 位的位置不能通过厂商名称简单推断。
- [ ]  为什么 Page Program 必须处理页边界。
- [ ]  为什么擦除操作的延迟远高于读取操作。

### 15.2 驱动实现检查

能够独立实现：

- [ ]  JEDEC ID 读取。
- [ ]  Flash Reset。
- [ ]  Write Enable。
- [ ]  状态寄存器读取。
- [ ]  BUSY 状态轮询。
- [ ]  4 KB 扇区擦除。
- [ ]  跨页编程。
- [ ]  连续数据读取。
- [ ]  数据回读校验。
- [ ]  超时错误处理。
- [ ]  多型号 Flash 参数匹配。
- [ ]  4-byte Address 模式切换。
- [ ]  QE 配置。
- [ ]  Memory-Mapped 模式切换。

### 15.3 调试能力检查

遇到问题时，能够区分：

- [ ]  GPIO 复用错误。
- [ ]  QSPI 时钟没有开启。
- [ ]  CS 时序错误。
- [ ]  CPOL/CPHA 或采样边沿错误。
- [ ]  Flash 未退出复位状态。
- [ ]  QE 未设置。
- [ ]  Dummy Cycle 错误。
- [ ]  4-byte 地址未启用。
- [ ]  DMA 源缓冲区 Cache 未清理。
- [ ]  外部 Flash 正处于 BUSY。
- [ ]  Memory-Mapped 地址配置错误。
- [ ]  XIP 代码与擦写操作发生冲突。

### 15.4 工业级设计检查

能够设计：

- [ ]  支持 CRC 或 SHA 校验的 Flash 数据层。
- [ ]  支持掉电恢复的 OTA 状态机。
- [ ]  双分区固件存储方案。
- [ ]  带磨损均衡的日志存储方案。
- [ ]  基于 RTOS 请求队列的 QSPI 服务层。
- [ ]  QSPI 故障恢复和重新初始化流程。
- [ ]  运行时性能统计和故障计数机制。
- [ ]  产线烧录和现场升级兼容的 Flash 布局。

---

## 16. 实践与进阶路径

## 16.1 第一阶段：基础驱动验证

### 实战任务

使用一颗常见 QSPI NOR Flash，实现：

```
上电初始化
  ↓
读取 JEDEC ID
  ↓
读取状态寄存器
  ↓
设置 QE
  ↓
读取一段数据
  ↓
擦除一个扇区
  ↓
写入测试数据
  ↓
回读并比较
```

### 验收标准

- JEDEC ID 连续读取 1000 次无错误。
- 4 KB 扇区擦除后回读全部为 `0xFF`。
- 1~256 字节随机长度写入正确。
- 起始地址覆盖页首、页尾和非对齐地址。
- 读写超时能正确返回错误码。
- Flash 复位后可以重新初始化。

---

## 16.2 第二阶段：跨页、跨扇区和异常处理

### 实战任务

实现以下接口：

```
qspi_status_t qspi_read(uint32_t address,
                        void *buffer,
                        size_t length);

qspi_status_t qspi_program(uint32_t address,
                           const void *buffer,
                           size_t length);

qspi_status_t qspi_erase(uint32_t address,
                         size_t length);

qspi_status_t qspi_verify(uint32_t address,
                          const void *buffer,
                          size_t length);
```

覆盖测试：

- 从页中间开始写入；
- 连续写入跨越多个 Page；
- 连续擦除多个 Sector；
- 地址接近 Flash 尾部；
- `length == 0`；
- 地址溢出；
- 写入超过容量；
- Flash 忙时发起新事务；
- 人为拉低供电模拟中断；
- 超时后执行 Flash Reset。

---

## 16.3 第三阶段：DMA 与 RTOS 服务层

### 实战任务

实现一个 QSPI 服务任务：

```
应用任务
  ↓
消息队列
  ↓
QSPI Service Task
  ↓
互斥锁
  ↓
PIO/DMA 自动选择
  ↓
完成事件通知
```

建议增加：

- 请求优先级；
- 读取请求合并；
- 擦除任务后台执行；
- DMA 超时；
- 请求取消；
- 统计平均延迟和最大延迟；
- 总线错误恢复；
- 任务堆栈监控。

### 验收指标

|指标|目标|
|---|---|
|小于 32 B 读取|PIO 处理|
|大于等于 64 B 读取|DMA 处理|
|DMA 缓冲区 Cache 对齐|32 B 或按平台要求|
|高优先级控制任务阻塞|小于设计上限|
|QSPI 超时恢复|100% 可恢复|
|并发访问数据损坏|0 次|
|1 MB 连续读取 CRC 错误|0 次|

---

## 16.4 第四阶段：Memory-Mapped 与 XIP

### 实战任务

- 将外部 Flash 配置为 Memory-Mapped。
- 读取并比较 PIO、DMA、Memory-Mapped 三种模式的性能。
- 将部分只读代码放入外部 Flash。
- 将高频函数复制到内部 RAM。
- 对比 Cache 开启和关闭时的执行时间。
- 测量顺序执行、循环执行和随机跳转的差异。

### 测试函数示例

```
static uint32_t benchmark_linear_read(const uint32_t *base,
                                       size_t words)
{
    uint32_t sum = 0U;

    for (size_t i = 0U; i < words; ++i) {
        sum += base[i];
    }

    return sum;
}

static uint32_t benchmark_random_read(const uint32_t *base,
                                      const uint32_t *index,
                                      size_t count)
{
    uint32_t sum = 0U;

    for (size_t i = 0U; i < count; ++i) {
        sum += base[index[i]];
    }

    return sum;
}
```

需要记录：

- 总执行周期；
- Cache Miss 次数；
- 读取长度；
- QSPI 时钟；
- Dummy Cycle；
- DMA/PIO 模式；
- CPU 主频；
- 总线竞争情况。

---

## 16.5 第五阶段：OTA 与掉电恢复

### 实战任务

设计双分区升级：

```
Bootloader
├── 固件 Slot A
├── 固件 Slot B
├── 下载状态
├── 镜像摘要
├── 签名信息
└── 版本与回滚记录
```

实现以下状态：

```
EMPTY
DOWNLOADING
DOWNLOAD_COMPLETE
HASH_VERIFIED
SIGNATURE_VERIFIED
PENDING_BOOT
BOOT_TESTING
CONFIRMED
ROLLBACK
```

必须测试：

- 下载过程中断电；
- 擦除过程中断电；
- 页编程过程中断电；
- 镜像 CRC 错误；
- 镜像签名错误；
- 新固件启动异常；
- 启动确认超时；
- 版本回退攻击；
- 元数据副本损坏。

---

## 16.6 第六阶段：性能与可靠性测试方法

### 带宽测试

分别测试：

- 4 字节读取；
- 32 字节读取；
- 256 字节读取；
- 4 KB 读取；
- 64 KB 读取；
- 1 MB 连续读取。

计算：

Bactual=数据字节数总耗时Bactual​=总耗时数据字节数​

测试结果至少记录：

```
QSPI 时钟
传输模式
Dummy Cycle
CPU 主频
Cache 状态
DMA 状态
数据长度
实际吞吐率
CPU 占用率
```

### 实时性测试

观察：

- QSPI DMA 中断延迟；
- QSPI 互斥锁最长持有时间；
- 擦除期间高优先级任务响应时间；
- Cache Maintenance 耗时；
- 总线竞争下的最坏执行时间；
- XIP Cache Miss 对控制回路的影响。

推荐使用：

- DWT Cycle Counter；
- GPIO 翻转；
- ETM/Trace；
- RTOS Runtime Statistics；
- 逻辑分析仪；
- 示波器；
- 总线性能计数器。

### 信号完整性测试

需要验证：

- 最大工作频率；
- 高低温；
- 最低和最高供电电压；
- 不同 PCB 批次；
- 不同 Flash 批次；
- CS 建立和保持时间；
- SCK 上升下降沿；
- IO 过冲和振铃；
- 采样窗口和时序裕量。

### 擦写寿命测试

建议执行：

```
写入测试数据
  ↓
回读校验
  ↓
擦除
  ↓
回读 0xFF
  ↓
记录耗时和失败次数
  ↓
重复至目标次数
```

关注：

- 擦除时间是否逐渐增加；
- 编程失败率；
- 位翻转错误；
- 温度对寿命的影响；
- 磨损均衡效果；
- 掉电恢复成功率。

---

## 16.7 进阶学习方向

### 方向一：SFDP 自动探测

实现基于 SFDP 的参数解析：

- JEDEC Basic Flash Parameter Table；
- 读命令支持；
- 擦除类型；
- Page Size；
- 4-byte Address；
- Dummy Cycle；
- 频率限制。

目标是减少硬编码型号表，提高驱动可移植性。

### 方向二：高性能 OPI/DDR

继续学习：

- DQS；
- DDR 采样；
- Read Strobe；
- Delay Block；
- 窗口扫描；
- OPI 命令格式；
- 高速 PCB 走线；
- SI/PI 联合仿真。

### 方向三：SPI NAND

重点掌握：

- 坏块表；
- ECC 状态；
- Page Read；
- Cache Read；
- Block Erase；
- NAND 地址映射；
- FTL；
- 磨损均衡；
- 断电保护。

### 方向四：可靠存储系统

继续设计：

- Copy-on-Write；
- 日志结构存储；
- 双副本元数据；
- 原子提交；
- 版本回滚；
- CRC32/SHA-256；
- 数据完整性和一致性恢复。

### 方向五：安全启动与安全升级

重点学习：

- Secure Boot；
- 固件签名；
- 哈希链；
- Anti-Rollback；
- 密钥存储；
- TrustZone-M；
- 固件加密；
- 调试口生命周期管理；
- OTA 故障恢复。

### 方向六：系统级架构优化

进一步研究：

- QSPI、PSRAM、SDRAM 的分层存储；
- MPU 区域划分；
- Cache 优化；
- DMA 调度；
- 实时任务与存储任务隔离；
- 多核 MCU 下的共享总线访问；
- 存储带宽预算和最坏时延分析。

### 最终能力目标

完成上述实践后，应能够在真实项目中完成以下工作：

```
根据容量、带宽、实时性、寿命和成本需求选择存储器
  ↓
设计 QSPI 控制器和 Flash 抽象层
  ↓
实现 PIO、DMA、Memory-Mapped 和 XIP
  ↓
处理 Cache、RTOS 并发和擦写冲突
  ↓
完成 OTA、日志、资源和参数存储架构
  ↓
通过性能、温度、电压、寿命和掉电测试
  ↓
形成可量产、可维护、可诊断的工业级方案
```