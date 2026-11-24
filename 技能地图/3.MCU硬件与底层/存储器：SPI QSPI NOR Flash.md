
## 1. 学习目标

### 理解

- 理解 NOR Flash 的阵列组织、页编程、扇区擦除、块擦除和整片擦除机制。
- 理解 SPI、Dual SPI、Quad SPI、QPI、Memory-Mapped 模式的协议差异。
- 理解 NOR Flash 的有限擦写寿命、擦除粒度、写入粒度和数据一致性约束。
- 理解 JEDEC ID、SFDP、状态寄存器、保护寄存器、QE 位的作用。

### 掌握

- 掌握 SPI/QSPI NOR Flash 初始化、读写、擦除、状态轮询和超时处理。
- 掌握页边界处理、写保护处理、忙状态处理和掉电场景下的数据保护。
- 掌握基于 SFDP 参数动态识别 Flash 容量、页大小、擦除类型和时序参数。
- 掌握 QSPI 控制器间接模式和 Memory-Mapped 模式的使用方法。

### 精通

- 能够定位 QSPI 读数据错误、QE 位未配置、Dummy Cycle 不匹配、Cache 一致性等问题。
- 能够设计具备磨损均衡、掉电恢复、CRC 校验和版本管理能力的参数存储层。
- 能够从总线时序、控制器状态机和 Flash 内部操作三个层面分析实时性瓶颈。
- 能够建立可测试的 Flash 抽象驱动和板级适配层。

### 能够设计

- 能够设计工业级 SPI/QSPI NOR Flash 驱动框架。
- 能够针对代码执行、参数存储、日志存储、OTA 镜像等场景完成器件选型。
- 能够设计多任务环境下的并发访问、互斥、异步擦除和故障恢复机制。
- 能够量化容量、带宽、延迟、擦写寿命和系统启动时间。

---

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、位操作、内存映射和 `volatile`。
- MCU SPI、DMA、中断、Cache 和 MPU 基础。
- 基本的时序图阅读能力。
- RTOS 互斥锁、信号量、任务调度和优先级反转知识。
- CRC、双备份、日志追加写等数据完整性机制。

### 技能要求

- 能够使用逻辑分析仪抓取 SPI 信号。
- 能够阅读 Flash 数据手册和 MCU QSPI 控制器参考手册。
- 能够编写寄存器级或 HAL 级 SPI 外设驱动。
- 能够进行擦写寿命、掉电恢复和异常时序测试。

---

## 3. 技术概述

SPI NOR Flash 是一种基于 NOR 阵列的非易失性存储器，典型特点是：

- **随机读取速度高**。
- 支持按地址读取代码和常量。
- 编程前必须保证对应位已经处于 `1`。
- 编程只能将位从 `1` 写成 `0`。
- 擦除负责将位恢复为 `1`。
- 擦除粒度通常大于编程粒度。
- 擦写寿命通常为 **10 万次/扇区级别**，具体以器件数据手册为准。

### 主要技术分支

|类型|数据线|典型命令|典型应用|
|---|---|---|---|
|Standard SPI|1 条 MOSI + 1 条 MISO|`03h`、`0Bh`|低速参数、兼容性优先|
|Dual SPI|2 条数据线|`3Bh`、`BBh`|提高读取带宽|
|Quad SPI|4 条数据线|`6Bh`、`EBh`|高速代码执行、资源读取|
|QPI|4 条数据线，命令也走 4 线|`38h` 等|高速连续访问|
|Memory-Mapped QSPI|控制器映射为地址空间|控制器自动发命令|XIP、资源直接读取|

### 基本操作粒度

- 读取：通常按字节、半字或任意长度读取。
- 页编程：典型页大小为 **256 Bytes**。
- 扇区擦除：典型大小为 **4 KiB**。
- 块擦除：常见为 **32 KiB 或 64 KiB**。
- 芯片擦除：整个器件擦除，耗时可能达到几十秒甚至数分钟。

---

## 4. 核心特性横向对比

|维度|Standard SPI|Dual SPI|Quad SPI|QPI|Memory-Mapped QSPI|
|---|---|---|---|---|---|
|数据线数量|1|2|4|4|4|
|命令线|1|1|1|4|控制器自动处理|
|初始化复杂度|低|中|中|高|高|
|读取吞吐|低|中|高|高|高|
|软件控制难度|低|中|中|高|中|
|调试难度|低|中|中高|高|高|
|是否依赖 QE 位|否|通常否|通常是|通常是|通常是|
|适合 XIP|一般|一般|较好|较好|最佳|
|适合参数读写|好|好|好|一般|不推荐直接写|
|总线兼容性|最好|较好|依赖硬件|较差|依赖 MCU 控制器|
|典型瓶颈|时钟频率|Dummy Cycle|时序和 Cache|状态切换|Cache、映射窗口|

### 不同读取命令

|命令|含义|地址线|数据线|典型用途|
|---|---|---|---|---|
|`03h`|Normal Read|1|1|最稳定、无需 Dummy|
|`0Bh`|Fast Read|1|1|高速单线读取|
|`3Bh`|Dual Output Read|1|2|双线数据读取|
|`6Bh`|Quad Output Read|1|4|四线数据读取|
|`EBh`|Quad I/O Read|4|4|高速连续读取|
|`38h`|Quad Page Program|4|4|高速页编程，器件相关|

---

## 5. 底层原理与功能特性深度解析

### 5.1 NOR Flash 位编程原理

NOR Flash 内部通过浮栅晶体管保存电荷：

- 擦除操作移除浮栅中的电子，使单元回到逻辑 `1`。
- 编程操作注入电子，使单元变为逻辑 `0`。
- 因此，未经擦除时不能把 `0` 直接改成 `1`。
- 写入同一地址前，必须确认目标区域已经擦除，或者写入数据只发生 `1 -> 0`。

例如：

```
原数据：1111_0000
写入值：1100_0011
结果：  1100_0000
```

写入值中的 `1` 无法把原来的 `0` 恢复为 `1`。

---

### 5.2 典型命令时序

#### 写使能

```
CS Low
  06h
CS High
```

Flash 的写入、擦除、状态寄存器修改等操作通常都要求先发送 `Write Enable`。

#### 读取 JEDEC ID

```
CS Low
  9Fh
  Dummy
  Manufacturer ID
  Memory Type
  Capacity
CS High
```

#### 读取状态寄存器

```
CS Low
  05h
  Status Register 1
CS High
```

典型状态位：

|位|名称|含义|
|---|---|---|
|Bit0|WIP|`1` 表示内部编程或擦除忙|
|Bit1|WEL|`1` 表示写使能锁存有效|
|Bit2|BP0|块保护配置|
|Bit3|BP1|块保护配置|
|Bit4|BP2|块保护配置|
|Bit5|TB|保护区域方向|
|Bit6|SEC|保护粒度|
|Bit7|SRP|状态寄存器保护|

具体位定义必须以器件数据手册为准，不应假设所有厂商完全一致。

---

### 5.3 基础驱动数据结构

```
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef enum {
    FLASH_OK = 0,
    FLASH_EINVAL,
    FLASH_ETIMEOUT,
    FLASH_EIO,
    FLASH_EBUSY,
    FLASH_EPROTECT,
    FLASH_ENOTSUP
} flash_status_t;

typedef struct {
    uint32_t capacity_bytes;
    uint32_t page_size;
    uint32_t sector_size;
    uint32_t block_size;
    uint32_t max_clock_hz;
    bool     quad_enabled;
} flash_geometry_t;

typedef struct {
    int (*select)(void *ctx);
    int (*deselect)(void *ctx);
    int (*txrx)(void *ctx,
                const uint8_t *tx,
                uint8_t *rx,
                size_t len);
    uint32_t (*time_ms)(void *ctx);
    void (*delay_ms)(void *ctx, uint32_t ms);
    void *ctx;
} flash_bus_t;

typedef struct {
    flash_bus_t bus;
    flash_geometry_t geometry;
    uint8_t address_bytes;
} nor_flash_t;
```

驱动层只依赖 `flash_bus_t`，不直接依赖具体 MCU HAL，可以在单元测试、裸机和 RTOS 工程中复用。

---

### 5.4 读状态寄存器与等待内部操作结束

```
#define CMD_READ_SR1       0x05u
#define SR1_WIP            (1u << 0)
#define SR1_WEL            (1u << 1)

static flash_status_t flash_read_sr1(nor_flash_t *dev, uint8_t *sr)
{
    uint8_t tx[2] = { CMD_READ_SR1, 0 };
    uint8_t rx[2] = { 0 };

    if (dev == NULL || sr == NULL) {
        return FLASH_EINVAL;
    }

    if (dev->bus.select(dev->bus.ctx) != 0) {
        return FLASH_EIO;
    }

    int ret = dev->bus.txrx(dev->bus.ctx, tx, rx, sizeof(tx));
    (void)dev->bus.deselect(dev->bus.ctx);

    if (ret != 0) {
        return FLASH_EIO;
    }

    *sr = rx[1];
    return FLASH_OK;
}

static flash_status_t flash_wait_ready(nor_flash_t *dev,
                                       uint32_t timeout_ms)
{
    uint32_t start;
    uint8_t sr;

    if (dev == NULL || dev->bus.time_ms == NULL) {
        return FLASH_EINVAL;
    }

    start = dev->bus.time_ms(dev->bus.ctx);

    for (;;) {
        flash_status_t ret = flash_read_sr1(dev, &sr);
        if (ret != FLASH_OK) {
            return ret;
        }

        if ((sr & SR1_WIP) == 0u) {
            return FLASH_OK;
        }

        if ((uint32_t)(dev->bus.time_ms(dev->bus.ctx) - start)
            >= timeout_ms) {
            return FLASH_ETIMEOUT;
        }

        if (dev->bus.delay_ms != NULL) {
            dev->bus.delay_ms(dev->bus.ctx, 1u);
        }
    }
}
```

工程要求：

- 不能无限等待 `WIP` 清零。
- 超时后必须记录操作类型、地址、命令和状态寄存器。
- RTOS 中不能使用忙等替代调度等待。
- `WIP` 清零只表示内部操作结束，不表示数据一定符合业务协议，应进一步校验。

---

### 5.5 页编程与页边界处理

典型 `Page Program` 命令：

```
06h                  Write Enable
02h + Address + Data Page Program
等待 WIP 清零
```

**关键约束：一次 Page Program 不能跨越页边界。**

```
#define CMD_WRITE_ENABLE  0x06u
#define CMD_PAGE_PROGRAM  0x02u
#define FLASH_PAGE_SIZE   256u

static flash_status_t flash_write_enable(nor_flash_t *dev)
{
    uint8_t cmd = CMD_WRITE_ENABLE;

    if (dev == NULL) {
        return FLASH_EINVAL;
    }

    if (dev->bus.select(dev->bus.ctx) != 0) {
        return FLASH_EIO;
    }

    int ret = dev->bus.txrx(dev->bus.ctx, &cmd, NULL, 1u);
    (void)dev->bus.deselect(dev->bus.ctx);

    return (ret == 0) ? FLASH_OK : FLASH_EIO;
}

static flash_status_t flash_page_program(nor_flash_t *dev,
                                         uint32_t addr,
                                         const uint8_t *data,
                                         size_t len)
{
    uint8_t frame[4 + FLASH_PAGE_SIZE];
    size_t i;
    flash_status_t ret;

    if (dev == NULL || data == NULL || len == 0u ||
        len > FLASH_PAGE_SIZE) {
        return FLASH_EINVAL;
    }

    if ((addr / FLASH_PAGE_SIZE) !=
        ((addr + len - 1u) / FLASH_PAGE_SIZE)) {
        return FLASH_EINVAL;
    }

    ret = flash_write_enable(dev);
    if (ret != FLASH_OK) {
        return ret;
    }

    frame[0] = CMD_PAGE_PROGRAM;
    frame[1] = (uint8_t)(addr >> 16);
    frame[2] = (uint8_t)(addr >> 8);
    frame[3] = (uint8_t)addr;

    for (i = 0; i < len; ++i) {
        frame[4u + i] = data[i];
    }

    if (dev->bus.select(dev->bus.ctx) != 0) {
        return FLASH_EIO;
    }

    int bus_ret = dev->bus.txrx(dev->bus.ctx, frame, NULL, 4u + len);
    (void)dev->bus.deselect(dev->bus.ctx);

    if (bus_ret != 0) {
        return FLASH_EIO;
    }

    ret = flash_wait_ready(dev, 100u);
    if (ret != FLASH_OK) {
        return ret;
    }

    return FLASH_OK;
}
```

生产级封装还应增加：

- 地址范围检查。
- 写前数据检查。
- 写后回读校验。
- 只允许 `1 -> 0` 时跳过擦除的策略。
- DMA 发送缓存的非 Cache 区域约束。
- 互斥锁保护整条“写使能 + 编程 + 等待”事务。

---

### 5.6 扇区擦除

典型 `Sector Erase`：

```
06h
20h + 24-bit Address
等待 WIP 清零
```

地址通常只需要落在目标扇区内，不要求地址必须为扇区首地址，但工程中建议统一传入对齐地址。

```
#define CMD_SECTOR_ERASE  0x20u
#define FLASH_SECTOR_SIZE 4096u

static flash_status_t flash_sector_erase(nor_flash_t *dev,
                                         uint32_t addr)
{
    uint8_t frame[4];
    flash_status_t ret;

    if (dev == NULL ||
        addr >= dev->geometry.capacity_bytes ||
        (addr % dev->geometry.sector_size) != 0u) {
        return FLASH_EINVAL;
    }

    ret = flash_write_enable(dev);
    if (ret != FLASH_OK) {
        return ret;
    }

    frame[0] = CMD_SECTOR_ERASE;
    frame[1] = (uint8_t)(addr >> 16);
    frame[2] = (uint8_t)(addr >> 8);
    frame[3] = (uint8_t)addr;

    if (dev->bus.select(dev->bus.ctx) != 0) {
        return FLASH_EIO;
    }

    int bus_ret = dev->bus.txrx(dev->bus.ctx, frame, NULL, sizeof(frame));
    (void)dev->bus.deselect(dev->bus.ctx);

    if (bus_ret != 0) {
        return FLASH_EIO;
    }

    return flash_wait_ready(dev, 1000u);
}
```

不同器件的典型最大时间可能不同：

|操作|典型时间|最大时间示例|
|---|---|---|
|Page Program|0.3~1 ms|3 ms|
|4 KiB Sector Erase|30~100 ms|400 ms|
|64 KiB Block Erase|100~500 ms|2 s|
|Chip Erase|数十秒|200 s 以上|

实际超时必须从数据手册的 `tPP(max)`、`tSE(max)`、`tBE(max)` 获取，并留出系统误差余量。

---

### 5.7 QSPI 与 QE 位

Quad 模式通常需要：

1. 读取状态寄存器。
2. 判断 QE 位。
3. 写使能。
4. 写状态寄存器或配置寄存器。
5. 等待 `WIP` 清零。
6. 重新读取确认。
7. 重新初始化 QSPI 控制器。

不同厂商的 QE 位位置并不统一：

- 某些器件位于 Status Register 2。
- 某些器件位于 Status Register 1。
- 某些器件通过写状态寄存器 1/2 的组合命令配置。
- 某些器件上电默认 QE 为 `0`。
- 某些器件的 QE 为 OTP 或不可修改位。

因此不能写成通用的：

```
status2 |= (1u << 1);  /* 错误：假设所有 Flash QE 都是 bit1 */
```

应使用器件描述表：

```
typedef struct {
    uint8_t manufacturer_id;
    uint8_t memory_type;
    uint8_t capacity_id;

    uint8_t qe_register;
    uint8_t qe_mask;

    uint8_t read_quad_opcode;
    uint8_t page_program_quad_opcode;
    uint8_t dummy_cycles;
} flash_part_desc_t;
```

---

### 5.8 SFDP 动态参数识别

SFDP 使用 `5Ah` 命令读取标准参数表，可以发现：

- Flash 容量。
- 支持的擦除命令及粒度。
- 页大小。
- 地址模式。
- 读取模式和 Dummy Cycle。
- 部分器件的时序能力。

典型流程：

```
读取 JEDEC ID
读取 SFDP Header
读取 Basic Flash Parameter Table
解析密度、页大小、擦除类型
根据厂商扩展表解析 QE 位置
```

SFDP 不能完全替代厂商手册，尤其是：

- QE 配置。
- 深度掉电模式。
- 复位流程。
- 特殊地址模式。
- 非标准状态寄存器布局。

工业产品通常采用：

```
SFDP 基础参数 + 厂商器件白名单 + 启动时自检
```

---

## 6. 性能量化分析

以下数据为典型实测参考，平台假设：

- MCU：STM32H7，QSPI 运行在 100 MHz。
- Flash：128 Mbit，256 Byte Page，4 KiB Sector。
- SPI 模式：Standard SPI 使用 50 MHz，Quad Read 使用 100 MHz。
- DMA 开启，数据 Cache 已正确维护。

### 6.1 理论读取带宽

Standard SPI：

```
理论有效带宽 = 50 MHz × 1 bit / 8
              = 6.25 MB/s
```

Quad SPI：

```
理论有效带宽 = 100 MHz × 4 bit / 8
              = 50 MB/s
```

对于 `EBh` Quad I/O Read，还需要扣除：

- 命令周期。
- 地址周期。
- Mode 周期。
- Dummy Cycle。
- CS 拉低和控制器启动延迟。

因此连续读取时实际可能为：

|模式|理论值|典型实测值|
|---|---|---|
|50 MHz Standard SPI|6.25 MB/s|4.5~5.8 MB/s|
|100 MHz Quad Read|50 MB/s|28~42 MB/s|
|Memory-Mapped Quad Read|50 MB/s|25~45 MB/s|

### 6.2 小块读取延迟

假设读取 16 Bytes：

```
总 bit 数 = 命令 8 + 地址 24 + Dummy 8 + 数据 128
         = 168 bit

50 MHz SPI 传输时间 = 168 / 50 MHz
                    ≈ 3.36 us
```

实际端到端延迟还包括：

- CS 建立时间。
- 控制器配置时间。
- DMA 启动时间。
- Cache Miss。
- RTOS 调度延迟。

因此小块读取中，**总线频率提升不一定线性降低延迟**，批量读取和减少事务次数更加重要。

### 6.3 页编程耗时

256 Bytes Page Program：

```
传输时间 = (8 + 24 + 256 × 8) / 50 MHz
         ≈ 41.6 us
```

但 Flash 内部编程时间通常为：

```
tPP = 0.3~3 ms
```

所以页编程的主要瓶颈是 **Flash 内部编程时间**，而不是 SPI 传输时间。

### 6.4 内存和 CPU 开销

|项目|典型开销|
|---|---|
|驱动静态状态|64~256 Bytes|
|单次事务栈缓存|260~520 Bytes|
|DMA 描述符|32~128 Bytes|
|4 KiB 擦除缓存|4 KiB|
|CRC-32 软件计算|约 8~30 cycles/Byte|
|Quad Cache 维护|与 Cache Line 数量相关|

以 256 Bytes Page Program 为例：

```
DMA 缓存维护字节数 =
向下对齐起始地址 + 向上对齐结束地址后的范围
```

若 D-Cache Line 为 32 Bytes，非对齐缓冲区可能需要清理超过 256 Bytes 的 Cache 区域。

### 6.5 主要瓶颈与优化

|瓶颈|优化方法|典型收益|
|---|---|---|
|单线读取吞吐低|Quad Read|4~7 倍|
|频繁小块事务|批量读取、预取|20%~200%|
|页编程内部耗时|合并写入、异步队列|降低任务阻塞|
|扇区擦除耗时|空闲时预擦除|缩短关键路径|
|Cache 不一致|正确 Clean/Invalidate|消除随机数据错误|
|频繁擦除|日志追加、磨损均衡|延长寿命|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
需要存储代码并直接执行？
├─ 是
│  ├─ MCU 支持 QSPI Memory-Mapped？
│  │  ├─ 是 -> Quad QSPI + XIP
│  │  └─ 否 -> 启动时分块加载到内部 Flash/RAM
│  └─ 代码访问是否要求高带宽？
│     ├─ 是 -> Quad I/O 或 Quad Output
│     └─ 否 -> Standard SPI
└─ 否，需要存储数据？
   ├─ 数据量小于几十 KB？
   │  ├─ 是 -> 内部 Flash 或 SPI NOR
   │  └─ 否 -> SPI/QSPI NOR
   ├─ 需要频繁随机更新？
   │  ├─ 是 -> 日志结构 + 磨损均衡
   │  └─ 否 -> 固定分区 + 双备份
   └─ 需要高容量文件系统？
      ├─ 是 -> NOR 上的 LittleFS/自研对象存储
      └─ 否 -> 定制参数区/日志区
```

### 7.2 典型场景

|场景|推荐方案|理由|
|---|---|---|
|设备校准参数|Standard SPI + 双备份|简单、可靠、调试容易|
|图标、字体、音频|Quad Read + 连续读取|重点是读取吞吐|
|OTA 固件镜像|QSPI + 分区管理 + CRC/签名|容量和读取速度要求高|
|高频事件日志|环形日志 + 磨损均衡|避免固定扇区过快损坏|
|XIP 执行代码|Memory-Mapped QSPI|减少内部 Flash 压力|
|断电敏感配置|双槽位 + 序列号 + CRC|保障原子提交和恢复|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **驱动层与 MCU HAL 解耦**。
2. **所有操作必须有超时**。
3. **地址、长度、页边界和容量必须检查**。
4. **擦除、编程期间必须串行化**。
5. **使用 SFDP，但保留器件兼容表**。
6. **参数区不能直接覆盖写**。
7. **关键数据必须具备 CRC、版本号和提交标志**。
8. **写保护状态必须显式管理**。
9. **Memory-Mapped 区域禁止直接执行擦除或编程所在区域的代码**。
10. **将 Flash 错误计数、超时和擦除次数纳入诊断系统**。

### 8.2 选型决策矩阵

|需求|权重|关注指标|
|---|---|---|
|读取带宽|高|QSPI 频率、Dummy Cycle、连续读取能力|
|参数可靠性|高|擦写寿命、掉电行为、状态寄存器保护|
|启动兼容性|高|JEDEC ID、SFDP、复位时序|
|成本|中|容量、封装、工作温度|
|EMI|中|时钟边沿、走线长度、驱动强度|
|软件复杂度|中|QE 配置、QPI 状态恢复、控制器能力|

### 8.3 编码规范

- 所有外设寄存器使用明确宽度类型。
- 位域操作使用掩码，不依赖编译器位域布局。
- 地址计算使用 `uint32_t` 或 `uint64_t`，避免 16 位溢出。
- 异步接口必须有明确的状态机和取消策略。
- 中断中不执行擦除轮询和长时间 CRC。
- 日志记录至少包含：命令、地址、长度、状态寄存器、错误码、时间戳。

---

## 9. 常见错误与避坑指南

### 错误一：跨页写入

错误代码：

```
flash_page_program(addr, buffer, length);
```

其中 `addr = 0x1F0`，`length = 64`。

根因：

- 目标数据跨越了 `0x200` 页边界。
- 部分器件会在页内回绕覆盖数据，而不是自动进入下一页。

正确实现：

```
size_t page_remain = 256u - (addr % 256u);
size_t chunk = (length < page_remain) ? length : page_remain;

flash_page_program(addr, buffer, chunk);
addr += chunk;
buffer += chunk;
length -= chunk;
```

风险：

- 配置数据损坏。
- 错误只在特定地址出现，难以复现。

---

### 错误二：未擦除直接覆盖写

错误代码：

```
uint8_t value = 0xFF;
flash_write(0x1000, &value, 1);
```

根因：

- 写操作不能将 `0` 恢复为 `1`。

正确策略：

```
写入前比较旧值和新值
├─ 新值只产生 1 -> 0
│  └─ 可直接 Page Program
└─ 存在 0 -> 1
   └─ 读取整个扇区 -> 修改 RAM 副本 -> 擦除 -> 重写
```

风险：

- 数据看似写成功，但回读值错误。
- 直接擦除又可能破坏同一扇区中的其他数据。

---

### 错误三：只发送 Page Program，不等待 WIP

错误代码：

```
flash_write_enable(dev);
send_page_program(dev, addr, data, len);
send_page_program(dev, addr + len, next, next_len);
```

根因：

- Flash 仍处于内部编程状态。
- 后续命令可能被忽略，或者写使能锁存已经失效。

正确实现：

```
flash_write_enable(dev);
send_page_program(dev, addr, data, len);
flash_wait_ready(dev, PAGE_PROGRAM_TIMEOUT_MS);
```

风险：

- 偶发丢写。
- 温度升高或电压下降时错误概率增加。

---

### 错误四：QE 位、Dummy Cycle 或线序配置错误

错误代码：

```
qspi_read_quad(addr, data, len); /* 未确认 QE 和 Dummy Cycle */
```

根因：

- IO2/IO3 未切换到 Quad 功能。
- Flash QE 位未打开。
- MCU 控制器配置的 Dummy Cycle 与 Flash 当前模式不一致。
- DQS、采样边沿或驱动强度配置错误。

正确实现：

```
读取 JEDEC ID
读取并配置 QE
读取配置寄存器确认 QE
配置 Quad Read opcode
配置 Dummy Cycle
读取固定测试模式
与 Standard SPI 结果逐字节比较
```

风险：

- 全部数据错误。
- 仅高速或仅某些温度下错误。
- 代码 XIP 直接 HardFault。

---

### 错误五：DMA 与 D-Cache 不一致

错误代码：

```
cacheable_buffer[0] = 0x55;
qspi_dma_tx(cacheable_buffer, 1);
```

根因：

- CPU 修改的数据还在 D-Cache 中，DMA 从 RAM 读取到旧数据。
- DMA 写入后的数据仍被 Cache 中的旧副本覆盖。

正确处理：

```
DMA 发送前：Clean D-Cache
DMA 接收后：Invalidate D-Cache
缓冲区地址：按 Cache Line 对齐
缓冲区长度：按 Cache Line 向上取整
```

风险：

- 数据随机错误。
- 低频复现，调试器单步时可能消失。

---

### 错误六：RTOS 下没有保护复合事务

错误代码：

```
TaskA: Write Enable -> Page Program
TaskB: Write Enable -> Sector Erase
```

根因：

- 两个任务交叉访问同一 Flash。
- `Write Enable` 与后续命令不是原子事务。

正确实现：

```
lock_flash();

ret = flash_write_enable(dev);
if (ret == FLASH_OK) {
    ret = flash_page_program_locked(dev, addr, data, len);
}

unlock_flash();
```

风险：

- 写使能状态被覆盖。
- 任务之间产生不可预测的时序冲突。

---

## 10. 多机制组合使用方案

推荐将 Flash 访问分为四层：

```
应用层
  |
对象存储层：参数、日志、镜像对象
  |
Flash 管理层：分区、互斥、磨损均衡、掉电恢复
  |
NOR 驱动层：读、页编程、擦除、状态轮询
  |
总线适配层：SPI/QSPI HAL、DMA、Cache、GPIO
```

### 10.1 双槽位参数提交框架

每个槽位包含：

```
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t length;
    uint32_t crc32;
    uint32_t commit;
    uint8_t  payload[PARAM_MAX_SIZE];
} param_record_t;
```

提交流程：

```
1. 读取当前有效槽位
2. version + 1
3. 计算 payload CRC
4. 擦除备用槽位
5. 写入 header 和 payload
6. 回读并校验 CRC
7. 最后写 commit 标志
8. 启动时选择 version 最大且 CRC 正确的槽位
```

`commit` 必须最后写入，避免掉电时半成品被识别为有效数据。

### 10.2 环形日志方案

```
分区划分为 N 个扇区
每个扇区包含：
  sector_header
  record[0...M]
  sector_state

写入策略：
  当前扇区有空闲记录 -> 追加写
  当前扇区已满 -> 擦除最旧扇区并切换
  启动扫描 -> 依据序列号恢复写指针
```

该方案将擦除从“每条记录一次”降低为“每个扇区多条记录一次”。

---

## 11. 工业级实际案例分析

### 案例一：电机控制器校准参数

#### 需求

- 参数容量：8 KiB。
- 上电读取时间：小于 10 ms。
- 现场可能断电。
- 参数修改频率：每天 1~10 次。
- 必须检测数据损坏。

#### 架构

```
4 KiB Slot A
4 KiB Slot B
每个槽位：
Magic + Version + Length + CRC + Payload + Commit
```

#### 设计要点

- 使用 Standard SPI，调试和兼容性优先。
- 每次更新写备用槽位。
- CRC 使用 CRC-32C。
- 启动时选择版本号最大的有效槽位。
- 两个槽位都无效时加载编译期默认参数并上报故障。
- 不在中断中写 Flash。

---

### 案例二：带屏设备资源存储

#### 需求

- 字库、图片和音频共 8 MiB。
- UI 刷新要求连续读取带宽大于 20 MB/s。
- MCU 支持 QSPI Memory-Mapped。
- 资源只读，升级时整体替换。

#### 架构

```
QSPI Memory-Mapped
  0x000000 ~ 0x0001FF : 资源表
  0x000200 ~ 资源区   : 字库、图片、音频
```

#### 设计要点

- 使用 Quad I/O Read。
- 资源表包含偏移、长度、CRC、压缩类型和版本。
- 启动时验证资源表 CRC。
- 资源读取采用连续访问，避免大量小事务。
- QSPI XIP 区域禁止在资源更新期间执行。
- 更新流程先下载到备用分区，校验通过后切换活动分区。

---

### 案例三：工业网关 OTA 镜像

#### 需求

- 固件镜像容量：16 MiB。
- 支持断点续传。
- 需要 CRC 和数字签名校验。
- 断电后可恢复升级状态。

#### 分区

```
Bootloader     0x000000 ~ 0x01FFFF
Metadata       0x020000 ~ 0x02FFFF
Active Image   0x100000 ~ 0x8FFFFF
Download Image 0x900000 ~ 0xFFFFFF
```

#### 核心代码框架

```
typedef struct {
    uint32_t image_version;
    uint32_t image_size;
    uint32_t received_size;
    uint32_t image_crc;
    uint8_t  signature[64];
    uint32_t state;
} ota_metadata_t;

bool ota_is_complete(const ota_metadata_t *m)
{
    return m != NULL &&
           m->received_size == m->image_size &&
           m->state == OTA_STATE_DOWNLOADED;
}
```

#### 设计要点

- 下载数据按 4 KiB 或更大块写入。
- 每个块带序号和 CRC。
- Metadata 至少双备份。
- 下载完成后先校验整镜像，再校验签名。
- Bootloader 只切换状态，不直接信任应用层写入结果。
- 升级失败时保留旧镜像，保证回滚能力。

---

## 12. 高频问题深度答疑

### 1. 为什么 Quad SPI 速度不一定是 Standard SPI 的四倍？

因为实际吞吐还受以下因素影响：

- 命令、地址和 Dummy 周期仍然消耗总线时间。
- 控制器可能只能以较小事务启动 DMA。
- Flash 内部阵列读取速度存在上限。
- Cache Miss 和 CPU 访问模式可能成为瓶颈。
- PCB 信号完整性限制最高时钟频率。

连续大块读取时更接近理论四倍，小块随机读取时收益明显降低。

### 2. SPI NOR 和 NAND Flash 如何选择？

SPI NOR 适合：

- 代码执行。
- 小容量随机读取。
- 参数和资源保存。
- 对坏块管理要求较低的系统。

SPI NAND 适合：

- 大容量数据。
- 文件、视频、日志等顺序存储。
- 能够接受 ECC、坏块管理和更复杂控制器。

NOR 的软件复杂度低，但单位容量成本通常更高。

### 3. 擦除期间能否读取 Flash？

大多数器件在擦除或编程期间会拉高 `WIP`，普通读取可能返回无效数据，或者被器件忽略。是否支持读取其他区域取决于器件是否支持：

- Suspend/Resume。
- Read While Write。
- 多 Bank 并行操作。

没有明确数据手册支持时，应认为 **擦除/编程期间不能可靠读取同一器件**。

### 4. 是否应该在 Flash 上直接使用文件系统？

取决于需求：

- 固定参数：不建议引入完整文件系统，双槽位更简单。
- 高频日志：可使用 LittleFS 或定制日志结构。
- 大量文件和目录：文件系统能降低应用复杂度。
- 强实时路径：文件系统的写放大和垃圾回收可能不可接受。

选择时重点评估写放大、擦除延迟、掉电恢复和 RAM 占用。

### 5. 为什么擦除后仍然读不到 `0xFF`？

可能原因：

- 擦除命令未执行，写使能无效。
- 地址不在预期扇区。
- Flash 仍处于 `WIP`。
- 状态寄存器写保护。
- QSPI 读配置错误。
- Cache 未失效，读取到旧数据。
- 供电、电压或时序不满足要求。

排查顺序应为：

```
JEDEC ID -> 状态寄存器 -> WEL -> WIP -> Standard SPI 回读
-> QSPI 配置 -> Cache -> 电气波形
```

### 6. 为什么 QSPI XIP 偶发 HardFault？

常见原因：

- Flash 进入 QPI 后，异常处理流程仍使用 Standard SPI 命令。
- QSPI Memory-Mapped 区域配置错误。
- Dummy Cycle 与 Flash 配置不一致。
- 擦除/编程时 CPU 仍从同一 Flash 执行代码。
- Cache 或 MPU 属性不匹配。
- 读时钟超过器件在当前电压温度下的能力。

工业实现应将 Flash 操作代码、异常向量和关键数据放在内部 Flash 或 SRAM 中。

---

## 13. 课程核心总结

### 核心要点

- **Page Program 不能跨页**。
- **写入前必须处理擦除约束**。
- **写使能、编程/擦除、WIP 轮询必须作为受保护事务**。
- **QE 位、Dummy Cycle 和 IO 线序是 QSPI 调试重点**。
- **Cache 一致性是 DMA/QSPI 系统中的高频隐患**。
- **关键参数必须使用 CRC、版本号、双备份和提交标志**。
- **高频写入必须采用日志结构或磨损均衡**。
- **XIP 系统必须解决擦除期间代码执行和异常处理问题**。

### 性能排序

```
Memory-Mapped Quad Read
    >
Quad I/O Read
    >
Quad Output Read
    >
Dual SPI
    >
Fast Standard SPI
    >
Normal Standard SPI
```

### 通用选型结论

- 可靠性和兼容性优先：**Standard SPI**。
- 连续读取带宽优先：**Quad SPI**。
- 代码和资源直接访问：**Memory-Mapped QSPI**。
- 高频参数更新：**日志结构 + 磨损均衡**。
- OTA：**双分区 + 元数据双备份 + CRC + 签名 + 回滚**。

---

## 14. 快速参考速查表

### 场景选型表

|场景|总线模式|数据组织|关键机制|
|---|---|---|---|
|小量配置|Standard SPI|双槽位|CRC、版本、Commit|
|字库图片|Quad Read|连续对象|资源表、CRC|
|XIP|Memory-Mapped QSPI|地址映射|Cache、MPU、异常安全|
|高频日志|SPI/QSPI|环形追加|磨损均衡、序列号|
|OTA|QSPI|双镜像分区|签名、回滚、断点续传|

### 命令速查

|操作|常见命令|
|---|---|
|Write Enable|`06h`|
|Read Status Register 1|`05h`|
|Read JEDEC ID|`9Fh`|
|Read SFDP|`5Ah`|
|Normal Read|`03h`|
|Fast Read|`0Bh`|
|Quad Output Read|`6Bh`|
|Quad I/O Read|`EBh`|
|Page Program|`02h`|
|Quad Page Program|`32h` 或器件相关|
|4 KiB Sector Erase|`20h`|
|64 KiB Block Erase|`D8h`|
|Chip Erase|`C7h` 或 `60h`|
|Reset Enable|`66h`|
|Reset|`99h`|

### 驱动接口速查

```
flash_status_t flash_init(nor_flash_t *dev);
flash_status_t flash_read(nor_flash_t *dev,
                          uint32_t addr,
                          void *buf,
                          size_t len);
flash_status_t flash_write(nor_flash_t *dev,
                           uint32_t addr,
                           const void *buf,
                           size_t len);
flash_status_t flash_erase_sector(nor_flash_t *dev,
                                  uint32_t addr);
flash_status_t flash_erase_block(nor_flash_t *dev,
                                 uint32_t addr);
flash_status_t flash_get_geometry(nor_flash_t *dev,
                                  flash_geometry_t *geometry);
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实现：

- [ ]  解释为什么 NOR Flash 不能直接把 `0` 写回 `1`。
- [ ]  正确处理跨页写入。
- [ ]  计算任意地址和长度需要擦除的扇区范围。
- [ ]  设计带超时的 `WIP` 轮询机制。
- [ ]  根据 JEDEC ID 判断器件容量。
- [ ]  解释 SFDP 的作用和局限。
- [ ]  识别 QE 位配置错误。
- [ ]  解释 Dummy Cycle 与读取采样的关系。
- [ ]  处理 QSPI DMA 的 Cache 一致性。
- [ ]  设计双备份掉电安全参数区。
- [ ]  设计环形日志和基本磨损均衡策略。
- [ ]  说明为什么不能在同一 QSPI Flash 擦除期间执行 XIP 代码。
- [ ]  量化 Standard SPI 与 Quad SPI 的理论吞吐。
- [ ]  为 Page Program、Sector Erase 设置合理超时。
- [ ]  使用逻辑分析仪验证命令、地址、数据和 CS 时序。

---

## 16. 实践与进阶路径

### 阶段一：基础驱动实现

实现以下接口：

```
flash_init
flash_read_id
flash_read_status
flash_write_enable
flash_read
flash_page_program
flash_sector_erase
flash_wait_ready
```

验证内容：

- JEDEC ID 正确。
- 擦除后数据为 `0xFF`。
- 单页写入回读一致。
- 地址头尾、页边界和容量边界均测试。

### 阶段二：完善工程能力

增加：

- 自动分页写入。
- 多种擦除粒度选择。
- SFDP 参数解析。
- 器件白名单。
- RTOS 互斥保护。
- DMA 传输。
- Cache 维护。
- 错误日志和统计计数。

### 阶段三：可靠性实战

实现：

- 双槽位参数存储。
- CRC-32 校验。
- 掉电恢复。
- 环形日志。
- 擦除次数统计。
- 断点续传。
- OTA 双镜像和回滚。

### 阶段四：性能测试方法

建立以下测试矩阵：

|测试项|测试方法|
|---|---|
|连续读取带宽|读取 1 MiB，统计总耗时|
|随机读取延迟|随机地址读取 4/16/64 Bytes|
|页编程时间|重复写入 256 Bytes，统计 P50/P99|
|扇区擦除时间|记录最小、平均、最大耗时|
|温度影响|低温、常温、高温重复测试|
|电压影响|在规格上下限内测试|
|掉电恢复|编程和擦除阶段随机断电|
|写入寿命|循环擦写直到数据错误|
|信号质量|检查频率、占空比、采样边沿和过冲|

### 阶段五：进阶方向

- JEDEC SFDP 完整解析。
- QSPI 调谐、采样点自动校准。
- DDR Quad SPI 和 DQS。
- NOR Flash 的 Suspend/Resume。
- LittleFS 与定制对象存储比较。
- 面向 OTA 的安全启动和镜像认证。
- 多 Flash Bank 并行设计。
- 形式化验证关键状态机。
- 基于故障注入的 Flash 驱动测试。
- 使用 FPGA 或高速逻辑分析仪验证边界时序。