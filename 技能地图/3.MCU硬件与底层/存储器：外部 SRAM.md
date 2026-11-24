
## 1. 学习目标

### 理解

- 理解外部 SRAM 在 MCU 存储体系中的定位，以及它与片内 SRAM、SDRAM、PSRAM、NOR Flash 的本质差异。
- 理解异步 SRAM 的地址、数据、片选、读写使能及字节选通信号时序。
- 理解 MCU 外部存储控制器将 CPU 总线事务转换为 SRAM 引脚时序的过程。
- 理解存储器映射、总线矩阵、Cache、MPU、DMA 与外部 SRAM 的协同关系。

### 掌握

- 掌握外部 SRAM 容量、数据宽度、地址线数量及地址映射的计算方法。
- 掌握 FMC/FSMC 类控制器的地址建立、数据建立、总线周转等参数配置。
- 掌握外部 SRAM 的基础读写、数据总线、地址总线和全容量测试方法。
- 掌握链接脚本、静态内存池和 DMA 缓冲区在外部 SRAM 中的放置方法。

### 精通

- 精通异步 SRAM 读写时序闭合、访问延迟计算及带宽瓶颈定位。
- 精通 Cache 属性、MPU 内存类型、DMA 一致性和内存屏障的工程处理。
- 精通板级信号完整性、时序裕量、温压漂移及量产测试设计。
- 精通外部 SRAM 故障模式诊断，包括地址混叠、数据位故障、邻位耦合和随机瞬态错误。

### 能够设计

- 能够完成从 SRAM 选型、原理图连接、PCB 约束到驱动和测试的完整设计。
- 能够根据实时性、容量、吞吐量、待机功耗和成本选择并行 SRAM、PSRAM 或 SDRAM。
- 能够设计内部 SRAM 与外部 SRAM 分层使用的内存架构。
- 能够设计支持 MPU、Cache、DMA、静态分配和故障降级的工业级外部内存子系统。

---

## 2. 前置要求

### 知识要求

- ARM Cortex-M 地址空间、AHB/AXI 总线和总线矩阵。
- MCU 启动流程、链接脚本、ELF 段和 C 运行时初始化。
- 建立时间、保持时间、传播延迟和时钟周期等数字时序概念。
- `volatile`、内存屏障、Cache line 和 DMA 一致性。
- GPIO 复用、PCB 走线负载及基本信号完整性知识。

### 技能要求

- 能阅读 MCU 外部存储控制器和 SRAM 数据手册。
- 能使用示波器或逻辑分析仪测量 `/CS`、`/OE`、`/WE` 和数据线时序。
- 能修改链接脚本并通过 map 文件确认变量位置。
- 能编写无动态分配、具备边界检查和错误返回的底层 C 驱动。
- 能通过 DWT、硬件定时器或逻辑分析仪进行周期级性能测量。

---

## 3. 技术概述

### 3.1 核心定义

SRAM 使用双稳态存储单元保存数据，只要供电持续且器件未进入数据丢失模式，数据就能保持。它不需要 SDRAM 那样周期性刷新。

**外部 SRAM** 是通过 MCU 的并行外部总线或串行存储接口接入的易失性随机访问存储器。工程上主要分为：

1. **异步并行 SRAM**：无时钟，以 `/CS`、`/OE`、`/WE` 控制读写。
2. **同步突发 SRAM**：有时钟，支持流水线和突发访问，多用于 FPGA、高速网络设备。
3. **异步 PSRAM**：内部通常采用 DRAM 单元，但对外模拟 SRAM 接口。
4. **串行 PSRAM**：使用 SPI、QSPI 或 Octal SPI，节省引脚但延迟较高。
5. **双口 SRAM**：两个独立访问端口，适合处理器间高速共享。
6. **非易失 SRAM**：SRAM 与电池、超级电容或非易失介质组合，掉电保留。

本课以 **MCU FMC/FSMC 接口的异步并行 SRAM** 为主，同时给出与 PSRAM、SDRAM的选型边界。

### 3.2 技术价值

外部 SRAM 主要解决以下问题：

- 片内 SRAM 容量不足。
- 大尺寸帧缓冲、采样窗口、协议缓存无法容纳。
- 需要确定性随机访问，而 SDRAM 刷新和行切换抖动不可接受。
- 需要 DMA 可直接访问的大容量缓冲区。
- 希望将实时关键对象保留在片内 SRAM，将非关键大对象迁移到外部。

外部 SRAM 的核心代价是：**引脚多、PCB 面积大、访问延迟增加、功耗提高，并引入 Cache/DMA 一致性和板级时序问题。**

---

## 4. 核心特性横向对比

|维度|异步并行 SRAM|同步 SRAM|并行 PSRAM|QSPI/OSPI PSRAM|SDRAM|
|---|---|---|---|---|---|
|典型容量|128 KiB~8 MiB|512 KiB~72 MiB|1~32 MiB|2~64 MiB|8~256 MiB|
|接口宽度|8/16/32 bit|18/36/72 bit|8/16 bit|1/4/8 bit|8/16/32 bit|
|随机访问延迟|**低且确定**|低|中等|高|与行命中相关|
|刷新|无|无|内部完成|内部完成|控制器显式管理|
|持续带宽|中|高|中|中|**高**|
|引脚数量|高|很高|高|**低**|高|
|控制复杂度|低|中|低|中|高|
|时序抖动|**小**|小|中|中|较大|
|单位容量成本|高|很高|中|中|**低**|
|XIP 适用性|可映射，不适合代码主存|可|视控制器而定|控制器支持时可用|通常不建议|
|典型用途|实时缓存、FPGA 共享|网络、FPGA、高吞吐|大缓存|GUI、IoT|显示、音视频、大数据|

### SRAM 与 NOR Flash 的本质差异

|项目|SRAM|NOR Flash|
|---|---|---|
|易失性|易失|非易失|
|写入粒度|字节或字|页编程|
|擦除要求|无|写前按扇区擦除|
|写入寿命|不受擦写次数限制|通常 `10^4~10^5` 次擦除|
|写延迟|ns 级总线访问|us~ms 级编程/擦除|
|主要用途|运行时工作内存|固件、资源和持久数据|

---

## 5. 底层原理与功能特性深度解析

### 5.1 SRAM 单元与读写机制

经典 SRAM 单元由六个晶体管构成：

- 四个晶体管形成交叉耦合反相器，保存一个 bit。
- 两个访问晶体管由字线控制。
- 位线 `BL/BLB` 用于差分读写。

读操作流程：

1. 位线预充电。
2. 地址译码器选中字线。
3. 存储单元使位线产生微小差分。
4. 灵敏放大器将差分放大为逻辑电平。
5. 输出缓冲器在 `/CS` 与 `/OE` 有效时驱动数据总线。

写操作流程：

1. 外部控制器驱动数据线。
2. `/CS` 和 `/WE` 有效。
3. 写驱动器覆盖单元原状态。
4. `/WE` 撤销后新状态稳定保存。

**并行 SRAM 没有刷新，但掉电后数据丢失。**

### 5.2 地址与容量计算

以 `512K × 16 bit` SRAM 为例：

```
存储字数量 = 512 Ki = 2^19
地址线数量 = 19，A0~A18
每个存储字 = 16 bit = 2 byte
总容量     = 2^19 × 2 byte = 1 MiB
```

对于 16 位外部总线，MCU 的字节地址 `A0` 通常不直接接 SRAM 的 `A0`：

```
MCU byte address bit 0 -> 字节选通信号 NBL0/NBL1 的选择语义
MCU address bit 1      -> SRAM A0
MCU address bit 2      -> SRAM A1
...
MCU address bit 19     -> SRAM A18
```

是否由控制器内部自动右移地址，必须依据 MCU 参考手册确认。**不能仅按原理图信号名推断。**

### 5.3 关键控制信号

|信号|含义|典型有效电平|
|---|---|---|
|`CS/NE`|芯片选择|低|
|`OE/NOE`|输出使能|低|
|`WE/NWE`|写使能|低|
|`LB/NBL0`|低字节使能|低|
|`UB/NBL1`|高字节使能|低|
|`A[n:0]`|字地址|双态|
|`D[n:0]`|双向数据总线|三态|

16 位总线上的单字节写入依赖字节选通信号：

```
#define EXTSRAM_BASE 0x60000000UL

static inline void sram_write_u8(uint32_t offset, uint8_t value)
{
    *(volatile uint8_t *)(EXTSRAM_BASE + offset) = value;
}

static inline void sram_write_u16(uint32_t offset, uint16_t value)
{
    /* offset 必须是 2 字节对齐地址。 */
    *(volatile uint16_t *)(EXTSRAM_BASE + offset) = value;
}
```

如果 `NBL0/NBL1` 未连接或配置错误，字节写可能破坏同一半字中的另一个字节。

### 5.4 异步读时序

一次读操作需满足：

```
地址稳定 ─────────────────────────────
/CS      ───────\________________/─────
/OE      ─────────\____________/───────
数据     ZZZZZZZZZZ<--有效数据-->ZZZZZZ
                    ^
                    CPU 采样
```

主要器件参数：

- `tAA`：地址有效到数据有效。
- `tACS`：片选有效到数据有效。
- `tOE`：输出使能到数据有效。
- `tOH`：地址变化后的数据保持。
- `tHZ`：控制信号撤销到输出高阻。

控制器读数据采样时间必须满足：

Tsample≥max⁡(tAA,tACS,tOE)+tpcb+tmarginTsample​≥max(tAA​,tACS​,tOE​)+tpcb​+tmargin​

### 5.5 异步写时序

主要约束包括：

- `tWP`：写脉冲宽度。
- `tDW`：数据建立时间。
- `tDH`：数据保持时间。
- `tAW`：地址建立时间。
- `tWC`：完整写周期。

Twrite≥max⁡(tWC,tAW+tWP,tDW+tWP)+tmarginTwrite​≥max(tWC​,tAW​+tWP​,tDW​+tWP​)+tmargin​

### 5.6 FMC 时序参数计算

假设：

- FMC 内核时钟：`100 MHz`
- `T_HCLK = 10 ns`
- SRAM `tAA = 55 ns`
- PCB 与温压裕量：`10 ns`
- 控制器数据阶段定义为 `(DATAST + 1) × T_HCLK`

则：

DATAST≥⌈55+1010⌉−1=6DATAST≥⌈1055+10​⌉−1=6

工程配置应先采用保守参数完成验证，再逐步压缩：

```
typedef struct {
    uint32_t address_setup_cycles;
    uint32_t data_setup_cycles;
    uint32_t bus_turnaround_cycles;
} sram_timing_t;

static const sram_timing_t g_sram_timing = {
    .address_setup_cycles = 2U,
    .data_setup_cycles = 7U,
    .bus_turnaround_cycles = 1U
};
```

具体寄存器字段是否采用 `N` 或 `N+1` 编码，必须以芯片参考手册为准。

### 5.7 基础访问驱动

```
#include <stddef.h>
#include <stdint.h>

#define EXTSRAM_BASE_ADDR  0x60000000UL
#define EXTSRAM_SIZE_BYTES (1UL * 1024UL * 1024UL)

typedef enum {
    SRAM_OK = 0,
    SRAM_EINVAL,
    SRAM_ERANGE,
    SRAM_EIO
} sram_status_t;

static sram_status_t sram_check_range(uint32_t offset, size_t length)
{
    if (length == 0U) {
        return SRAM_EINVAL;
    }

    if ((offset >= EXTSRAM_SIZE_BYTES) ||
        (length > EXTSRAM_SIZE_BYTES - offset)) {
        return SRAM_ERANGE;
    }

    return SRAM_OK;
}

sram_status_t sram_write(uint32_t offset, const void *src, size_t length)
{
    const uint8_t *source = (const uint8_t *)src;
    volatile uint8_t *destination;
    size_t i;

    if ((src == NULL) || (sram_check_range(offset, length) != SRAM_OK)) {
        return SRAM_EINVAL;
    }

    destination = (volatile uint8_t *)(EXTSRAM_BASE_ADDR + offset);

    for (i = 0U; i < length; ++i) {
        destination[i] = source[i];
    }

    __DSB();
    return SRAM_OK;
}

sram_status_t sram_read(uint32_t offset, void *dst, size_t length)
{
    uint8_t *destination = (uint8_t *)dst;
    const volatile uint8_t *source;
    size_t i;

    if ((dst == NULL) || (sram_check_range(offset, length) != SRAM_OK)) {
        return SRAM_EINVAL;
    }

    source = (const volatile uint8_t *)(EXTSRAM_BASE_ADDR + offset);

    for (i = 0U; i < length; ++i) {
        destination[i] = source[i];
    }

    __DSB();
    return SRAM_OK;
}
```

`volatile` 适用于寄存器级自检和强制总线访问，但不应无条件用于普通业务对象，否则会阻止编译器执行必要优化。正常映射的外部 RAM 应通过 MPU 属性和 Cache 管理保证语义。

### 5.8 Cache、MPU 与内存属性

对于 Cortex-M7，外部存储区必须明确配置为：

- **Normal memory**：允许正常加载、存储和突发访问。
- **Cacheable**：CPU 高频访问区可启用。
- **Shareable/Non-shareable**：根据 DMA 和多主设备关系确定。
- **Execute Never**：纯数据区禁止执行。
- **读写权限**：按任务和特权级限制。

DMA 访问可缓存 SRAM 时：

- DMA 读取 CPU 生成的数据前，CPU 必须 Clean D-Cache。
- CPU 读取 DMA 写入的数据前，CPU 必须 Invalidate D-Cache。
- 清理和失效范围必须按 Cache line 向外对齐。

```
#define DCACHE_LINE_SIZE 32U

static uintptr_t align_down(uintptr_t value)
{
    return value & ~((uintptr_t)DCACHE_LINE_SIZE - 1U);
}

static uintptr_t align_up(uintptr_t value)
{
    return (value + DCACHE_LINE_SIZE - 1U) &
           ~((uintptr_t)DCACHE_LINE_SIZE - 1U);
}

void dma_prepare_tx(const void *buffer, size_t length)
{
    uintptr_t start = align_down((uintptr_t)buffer);
    uintptr_t end = align_up((uintptr_t)buffer + length);

    SCB_CleanDCache_by_Addr((uint32_t *)start, (int32_t)(end - start));
    __DSB();
}

void dma_complete_rx(void *buffer, size_t length)
{
    uintptr_t start = align_down((uintptr_t)buffer);
    uintptr_t end = align_up((uintptr_t)buffer + length);

    __DSB();
    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                (int32_t)(end - start));
    __DSB();
}
```

**DMA 接收前还需避免目标 Cache line 中存在其他有效对象。** 否则失效整个 Cache line 时可能丢弃邻接对象的脏数据。工程上应让 DMA 缓冲区按 Cache line 对齐并独占完整 Cache line。

---

## 6. 性能量化分析

### 6.1 测试平台与边界

以下数据为工程基准示例，不是跨平台固定结论：

- MCU：STM32H743，Cortex-M7，CPU `400 MHz`
- FMC 内核时钟：`100 MHz`
- SRAM：`512K × 16 bit`，异步访问 `55 ns`
- 总线宽度：16 bit
- 编译器：GCC `12.x`，`-O2`
- 测试长度：256 KiB
- 测量方法：DWT 周期计数器
- 顺序访问，数据区 32 字节对齐
- FMC 配置：地址建立 2 周期、数据建立 7 周期

实际项目必须基于目标芯片、PCB 和编译选项复测。

### 6.2 理论访问时间

若一次 16 位访问占用：

Ncycle=Naddress+Ndata+NturnaroundNcycle​=Naddress​+Ndata​+Nturnaround​

取 `2 + 7 + 1 = 10` 个 FMC 周期：

Taccess=10×10ns=100nsTaccess​=10×10ns=100ns

单次 16 位事务理论带宽：

BW=2Byte100ns=20MB/sBW=100ns2Byte​=20MB/s

由于 CPU 指令、总线仲裁、桥接和循环控制，软件实测通常低于该值。

### 6.3 示例实测结果

|访问方式|Cache|示例吞吐量|400 MHz CPU 周期/字节|特点|
|---|---|---|---|---|
|`volatile uint8_t` 顺序写|关闭|7.2 MB/s|55.6|字节选通信号开销高|
|`volatile uint16_t` 顺序写|关闭|16.8 MB/s|23.8|接近总线有效带宽|
|`uint32_t` 顺序写|关闭|18.1 MB/s|22.1|被拆分为两个 16 位事务|
|DMA 内部 SRAM→外部 SRAM|关闭|18.9 MB/s|CPU 异步|接近 FMC 上限|
|CPU `memcpy` 顺序写|Write-back|43 MB/s*|9.3|初期写入 Cache|
|Cache clean 后端到端写|Write-back|18.4 MB/s|21.7|最终受 FMC 限制|
|随机 32 位读|关闭|8.5 MB/s|47.1|无突发、等待多|
|顺序重复读热点|开启|600+ MB/s*|<1|命中 L1 D-Cache|

带 `*` 的结果描述 CPU 观察到的 Cache 行为，**不代表 SRAM 引脚上的物理带宽**。

### 6.4 带宽计算

DWT 测量公式：

T=CyclesFCPUT=FCPU​Cycles​BW=Bytes×FCPUCyclesBW=CyclesBytes×FCPU​​

```
typedef struct {
    uint32_t cycles;
    uint32_t bytes;
} benchmark_result_t;

benchmark_result_t sram_benchmark_write32(volatile uint32_t *base,
                                          size_t word_count)
{
    uint32_t start;
    uint32_t end;
    size_t i;

    __DSB();
    start = DWT->CYCCNT;

    for (i = 0U; i < word_count; ++i) {
        base[i] = (uint32_t)i ^ 0xA5A55A5AU;
    }

    __DSB();
    end = DWT->CYCCNT;

    return (benchmark_result_t) {
        .cycles = end - start,
        .bytes = (uint32_t)(word_count * sizeof(uint32_t))
    };
}
```

DWT 初始化：

```
void cycle_counter_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}
```

### 6.5 容量与元数据开销

一个固定块内存池的总开销可表示为：

Mtotal=N×align(B,A)+Mbitmap+McontrolMtotal​=N×align(B,A)+Mbitmap​+Mcontrol​

例如：

- 块大小：1024 Byte
- 块数量：512
- 位图：512 bit = 64 Byte
- 控制结构：约 32 Byte

Mtotal=512KiB+64B+32BMtotal​=512KiB+64B+32B

相比通用堆分配器，固定块池不存在每块 8~16 Byte 的块头开销，并具备确定性分配时间。

### 6.6 主要瓶颈与优化收益

|瓶颈|现象|优化|典型收益|
|---|---|---|---|
|时序参数过保守|带宽低但稳定|逐级降低 `DATAST` 并做温压测试|10%~35%|
|8 位访问|总线利用率低|使用自然对齐的 16/32 位访问|1.5~2.2 倍|
|Cache miss|随机访问慢|数据局部化、块处理|2~10 倍|
|总线争用|DMA 与 CPU 同时变慢|时隙调度、双缓冲|抖动降低 30%~80%|
|频繁 Cache 维护|小包性能差|合并批次、非缓存 DMA 区|20%~60%|
|通用堆碎片|分配时间增长|固定块池或区域分配器|延迟趋于常数|
|PCB 过冲振铃|高频随机错位|降低 GPIO 速率、串联阻尼|显著降低误码|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
需要扩展易失性内存？
├─ 否 -> 使用片内 SRAM
└─ 是
   ├─ 容量是否超过 8~16 MiB？
   │  ├─ 是 -> 优先 SDRAM
   │  └─ 否
   ├─ 是否要求随机访问延迟高度确定？
   │  ├─ 是 -> 异步 SRAM / 同步 SRAM
   │  └─ 否
   ├─ MCU 引脚是否紧张？
   │  ├─ 是 -> QSPI/OSPI PSRAM
   │  └─ 否
   ├─ 是否要求持续高带宽帧缓冲？
   │  ├─ 是 -> SDRAM；小容量高确定性场景选同步 SRAM
   │  └─ 否 -> 异步 SRAM
   ├─ 是否由 DMA 与 CPU 共同访问？
   │  ├─ 是 -> 划分 Cacheable CPU 区和 Non-cacheable DMA 区
   │  └─ 否 -> 可按访问局部性启用 Cache
   └─ 是否保存硬实时控制状态？
      ├─ 是 -> 保留片内 SRAM，仅将大缓存放入外部 SRAM
      └─ 否 -> 可迁移到外部 SRAM
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|1 MiB ADC 采样窗口，延迟确定|并行异步 SRAM|无刷新，随机延迟稳定|
|800×480 RGB565 双帧缓冲|SDRAM|约 1.46 MiB，连续带宽和容量更重要|
|引脚受限的 GUI 缓冲|OSPI PSRAM|引脚少，容量较大|
|FPGA 与 MCU 共享状态表|双口 SRAM|避免软件仲裁和总线竞争|
|电机控制参数、ISR 状态|片内 SRAM|最低延迟，不应放外部存储|
|网络大包缓存|外部 SRAM固定块池|容量可控、分配确定、无碎片|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **硬实时数据留在片内 SRAM**：中断栈、控制环状态和高频锁对象不应迁移到外部 SRAM。
2. **外部存储必须显式分区**：至少划分普通缓存区、DMA 区、诊断区和保留区。
3. **时序参数从器件最坏值推导**：使用工作温度和最低电压下的最慢速度等级。
4. **Cache 策略按数据所有权设计**：不能靠零散的 Clean/Invalidate 调用补救架构缺陷。
5. **禁止将外部 SRAM 无限制加入通用堆**：容易掩盖容量、实时性和碎片问题。
6. **启动阶段执行破坏性测试，运行阶段执行非破坏性巡检**。
7. **量产硬件必须测试地址线和数据线，不仅测试固定首地址。**
8. **关键缓冲区使用头尾哨兵、长度校验和所有权状态机。**

### 8.2 选型决策矩阵

评分范围为 1~5，5 为最佳。

|方案|确定性|容量|带宽|引脚成本|控制复杂度|综合适用性|
|---|---|---|---|---|---|---|
|异步 SRAM|5|2|3|1|5|实时缓存|
|同步 SRAM|5|2|5|1|3|高速低延迟|
|并行 PSRAM|3|4|3|2|4|成本敏感大缓存|
|OSPI PSRAM|2|4|3|5|3|引脚受限|
|SDRAM|2|5|5|2|2|图形与大数据|

### 8.3 工业级编码规范

- 地址、容量和分区使用 `uintptr_t`、`size_t` 和编译期断言。
- 所有范围判断使用防溢出形式：`length <= size - offset`。
- DMA 缓冲区按 Cache line 对齐，并保证不与普通对象共享 Cache line。
- 不允许业务代码直接散布硬编码地址。
- SRAM 初始化函数必须返回明确错误码。
- 测试失败时记录地址、期望值、实际值和测试阶段。
- 中断与任务共享区使用原子操作、临界区或所有权协议。
- 外部 SRAM 初始化前，禁止 C 运行时访问放在该区域中的静态变量。
- 正常业务数据访问不滥用 `volatile`。
- MPU 默认配置为 XN，除非明确需要从外部 SRAM 执行代码。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：忽略 16 位总线地址偏移

错误代码：

```
#define SRAM_REG(index) \
    (*(volatile uint16_t *)(EXTSRAM_BASE_ADDR + (index)))
```

根因：`index` 被当作字节偏移，连续索引产生未对齐访问，并且不能正确表示连续半字。

正确实现：

```
#define SRAM_REG(index) \
    (*(volatile uint16_t *)(EXTSRAM_BASE_ADDR + \
                            ((uintptr_t)(index) * sizeof(uint16_t))))
```

风险影响：

- HardFault 或 BusFault。
- 数据写入错误位置。
- 编译器拆分访问，时序和性能不可控。

### 9.2 错误二：DMA 与 D-Cache 不一致

错误代码：

```
dma_start_rx(ext_buffer, length);
wait_dma_done();
process(ext_buffer); /* CPU 可能继续读取旧 Cache line。 */
```

根因：DMA 绕过 CPU D-Cache 直接写外部 SRAM，CPU Cache 中仍保留旧副本。

正确实现：

```
dma_start_rx(ext_buffer, length);
wait_dma_done();
dma_complete_rx(ext_buffer, length);
process(ext_buffer);
```

更优方案是将 DMA 缓冲区放到 MPU 配置为 Non-cacheable 的独立区域。

风险影响：

- 偶发旧数据。
- 调试模式正常、优化模式失败。
- 数据包 CRC 随机错误。
- 问题与数据长度和地址对齐相关，极难复现。

### 9.3 错误三：仅用固定模式测试 SRAM

错误代码：

```
for (i = 0U; i < SRAM_WORDS; ++i) {
    sram[i] = 0xAAAAAAAAU;
}
```

根因：单一模式不能识别地址线短路、地址混叠、数据位耦合和保持故障。

正确实现：

```
for (i = 0U; i < SRAM_WORDS; ++i) {
    sram[i] = (uint32_t)i ^ 0xA5A55A5AU;
}
__DSB();

for (i = 0U; i < SRAM_WORDS; ++i) {
    uint32_t expected = (uint32_t)i ^ 0xA5A55A5AU;
    if (sram[i] != expected) {
        return SRAM_EIO;
    }
}
```

完整测试还应包含 walking-one、walking-zero、地址唯一值和 March 算法。

风险影响：

- 量产板通过测试，但在特定地址或数据模式下失效。
- 地址线断路导致多个地址映射到同一单元。

### 9.4 错误四：时序仅在室温单板验证

错误配置：

```
timing.data_setup_cycles = 4U; /* 仅按典型 35 ns 计算。 */
```

根因：使用典型值而非最坏值，未计入低压、高温、PCB 延迟和控制器采样裕量。

正确实现：

```
timing.data_setup_cycles = 7U; /* 按 55 ns 最坏值加 10 ns 裕量。 */
```

随后在温箱、最低工作电压和高总线负载下逐级验证。

风险影响：

- 高温或低电压随机位翻转。
- 不同批次 SRAM 表现不一致。
- DMA 高负载时故障率升高。

### 9.5 错误五：过早访问外部 SRAM 静态段

错误代码：

```
__attribute__((section(".extsram_bss")))
static uint8_t frame_buffer[256 * 1024];

void SystemInit(void)
{
    frame_buffer[0] = 0U; /* FMC 尚未初始化。 */
}
```

根因：启动代码可能在 `main()` 前清零 `.bss`，但此时 FMC 和 GPIO 尚未配置。

正确实现：

- 将外部 SRAM 初始化提前到对应段清零之前。
- 或将该段标记为 `NOLOAD`，在 FMC 初始化后由应用显式初始化。

```
.extsram_noinit (NOLOAD) :
{
    . = ALIGN(32);
    *(.extsram_noinit*)
    . = ALIGN(32);
} > EXTSRAM
```

风险影响：启动阶段 BusFault、看门狗复位或静默启动失败。

### 9.6 错误六：使用 `volatile` 代替并发同步

错误代码：

```
volatile bool ready;
uint8_t buffer[1024];

void producer(void)
{
    fill(buffer);
    ready = true;
}
```

根因：`volatile` 不提供原子性、跨核同步或完整内存排序保证。

正确实现：

```
void producer(void)
{
    fill(buffer);
    __DMB();
    __atomic_store_n(&ready, true, __ATOMIC_RELEASE);
}

bool consumer_ready(void)
{
    return __atomic_load_n(&ready, __ATOMIC_ACQUIRE);
}
```

风险影响：消费者看到 `ready == true`，但缓冲区数据仍未按预期可见。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

```
应用任务
├─ 实时控制对象
│  └─ 片内 DTCM/紧耦合 SRAM
├─ 协议与采集服务
│  ├─ 外部 SRAM固定块池
│  └─ 所有权队列
├─ DMA 数据通道
│  ├─ Non-cacheable 外部 SRAM 分区
│  └─ 双缓冲/Ping-Pong
├─ CPU 大数据处理
│  └─ Cacheable 外部 SRAM 分区
└─ 健康监控
   ├─ 启动 March 测试
   ├─ 运行时哨兵检查
   └─ 错误计数与降级策略
```

### 10.2 链接分区

```
MEMORY
{
    FLASH      (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
    RAM        (xrw) : ORIGIN = 0x24000000, LENGTH = 512K
    EXTSRAM_C  (xrw) : ORIGIN = 0x60000000, LENGTH = 768K
    EXTSRAM_DMA(xrw) : ORIGIN = 0x600C0000, LENGTH = 256K
}

.extsram_cacheable (NOLOAD) :
{
    . = ALIGN(32);
    *(.extsram_cacheable*)
    . = ALIGN(32);
} > EXTSRAM_C

.extsram_dma (NOLOAD) :
{
    . = ALIGN(32);
    *(.extsram_dma*)
    . = ALIGN(32);
} > EXTSRAM_DMA
```

### 10.3 双缓冲完整框架

```
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>

#define SAMPLE_COUNT 4096U
#define CACHE_LINE   32U

typedef enum {
    BUFFER_FREE = 0,
    BUFFER_DMA_OWNED,
    BUFFER_CPU_OWNED
} buffer_state_t;

typedef struct {
    _Alignas(CACHE_LINE) uint16_t samples[SAMPLE_COUNT];
    atomic_uint state;
    uint32_t sequence;
    uint32_t valid_samples;
} sample_buffer_t;

__attribute__((section(".extsram_dma"), aligned(CACHE_LINE)))
static sample_buffer_t g_buffers[2];

static sample_buffer_t *buffer_acquire_for_dma(void)
{
    size_t i;

    for (i = 0U; i < 2U; ++i) {
        unsigned expected = BUFFER_FREE;

        if (atomic_compare_exchange_strong_explicit(
                &g_buffers[i].state,
                &expected,
                BUFFER_DMA_OWNED,
                memory_order_acq_rel,
                memory_order_acquire)) {
            return &g_buffers[i];
        }
    }

    return NULL;
}

void adc_dma_complete_isr(sample_buffer_t *buffer, uint32_t count)
{
    if ((buffer == NULL) || (count > SAMPLE_COUNT)) {
        return;
    }

    buffer->valid_samples = count;
    buffer->sequence++;
    atomic_store_explicit(&buffer->state,
                          BUFFER_CPU_OWNED,
                          memory_order_release);
}

sample_buffer_t *buffer_acquire_for_cpu(void)
{
    size_t i;

    for (i = 0U; i < 2U; ++i) {
        if (atomic_load_explicit(&g_buffers[i].state,
                                 memory_order_acquire) ==
            BUFFER_CPU_OWNED) {
            return &g_buffers[i];
        }
    }

    return NULL;
}

void buffer_release_from_cpu(sample_buffer_t *buffer)
{
    if (buffer != NULL) {
        atomic_store_explicit(&buffer->state,
                              BUFFER_FREE,
                              memory_order_release);
    }
}
```

设计要点：

- DMA 区由 MPU 配置为 Non-cacheable。
- DMA 和 CPU 通过状态机转移所有权。
- ISR 只发布完成状态，不执行长时间处理。
- 缓冲区按 Cache line 对齐，未来调整 MPU 策略时仍保持安全。
- 如果生产速率高于消费速率，必须定义丢弃、覆盖或背压策略。

---

## 11. 工业级实际案例分析

### 11.1 工业振动采集设备

#### 需求

- 8 通道 ADC，单通道 `50 kSPS`。
- 每样本 16 bit。
- 保存 1 秒原始窗口。
- DMA 连续采集，不允许控制任务被阻塞。

原始吞吐量：

8×50000×2=800000Byte/s8×50000×2=800000Byte/s

1 秒窗口至少需要约 `781.25 KiB`，考虑双缓冲、元数据和对齐，选择 **2 MiB 异步 SRAM**。

#### 架构设计

```
ADC -> DMA -> 外部 SRAM Ping Buffer
                |
                +-> 数据处理任务 -> FFT/特征提取
ADC -> DMA -> 外部 SRAM Pong Buffer
片内 SRAM -> 控制任务、队列控制块、任务栈
```

#### 核心代码

```
#define CHANNELS          8U
#define SAMPLES_PER_BLOCK 1024U
#define BLOCK_WORDS       (CHANNELS * SAMPLES_PER_BLOCK)

typedef struct {
    uint32_t sequence;
    uint32_t timestamp;
    uint16_t data[BLOCK_WORDS];
} acquisition_block_t;

_Static_assert(sizeof(acquisition_block_t) < 20U * 1024U,
               "Acquisition block unexpectedly large");

__attribute__((section(".extsram_dma"), aligned(32)))
static acquisition_block_t g_acq_blocks[2];
```

#### 设计要点

- 外部 SRAM 带宽必须大于 ADC 输入带宽、CPU读取带宽和其他总线主设备需求之和。
- 采集缓冲采用固定块，不使用堆。
- 当处理任务落后时记录 overrun，不允许静默覆盖。
- 控制闭环数据仍放片内 SRAM，避免外部总线争用影响实时性。

### 11.2 工业以太网报文池

#### 需求

- 突发接收 256 个以太网帧。
- 每帧最大 1536 Byte。
- 分配和释放时间必须有上界。
- DMA 与协议栈共享报文。

容量：

256×1536=393216Byte256×1536=393216Byte

加上描述符和对齐，预留约 `416 KiB`。

#### 架构设计

- 外部 SRAM 存放固定大小 payload。
- 片内 SRAM 存放描述符、空闲队列和高频控制字段。
- DMA 区为 Non-cacheable，避免逐包 Cache 维护。
- 描述符通过 SPSC 环形队列在 ISR 和网络任务间传递。

#### 核心代码

```
#define PACKET_COUNT 256U
#define PACKET_SIZE  1536U

typedef struct {
    uint16_t length;
    uint16_t flags;
    uint32_t timestamp;
    uint16_t buffer_index;
} packet_desc_t;

__attribute__((section(".extsram_dma"), aligned(32)))
static uint8_t g_packet_storage[PACKET_COUNT][PACKET_SIZE];

static packet_desc_t g_descriptors[PACKET_COUNT];
```

#### 设计要点

- 高频修改的描述符留在片内 SRAM，减少外部总线小粒度随机访问。
- payload 放外部 SRAM，以连续块方式由 DMA 搬运。
- 固定块池提供 O(1) 分配和释放。
- 接收拥塞时必须有明确的尾丢弃或优先级丢弃策略。

### 11.3 HMI 帧缓冲与控制业务共存

#### 需求

- 分辨率 `480 × 272`，RGB565。
- 双缓冲。
- 显示刷新不允许干扰 1 kHz 控制任务。

内存需求：

480×272×2×2=522240Byte480×272×2×2=522240Byte

约 `510 KiB`，选择 1 MiB SRAM 可容纳双帧缓冲，但刷新带宽需额外核算。若刷新率 60 Hz：

480×272×2×60≈15.67MB/s480×272×2×60≈15.67MB/s

这已接近典型 16 位异步 SRAM 的持续带宽上限，CPU 绘图将进一步争用总线。

#### 结论

- 低刷新率、局部更新可使用异步 SRAM。
- 全帧 60 Hz 刷新应优先 SDRAM或更高速存储接口。
- 控制算法、ISR 栈和关键参数必须位于片内 SRAM。
- 通过总线 QoS、DMA 时隙或降低刷新率控制最坏阻塞时间。

---

## 12. 高频问题深度答疑

### 12.1 外部 SRAM 能否直接作为系统堆？

可以，但不应把整个外部 SRAM 无条件并入通用堆。外部 SRAM 延迟更高，且通用堆存在碎片和不可预测分配时间。

推荐策略：

- 片内堆：小对象、控制对象、低延迟对象。
- 外部固定块池：报文、图像块、采样块。
- 区域分配器：生命周期一致的批量数据。
- 禁止 ISR 调用通用动态内存分配。

### 12.2 为什么读写测试正常，DMA 仍然出现错误？

常见原因不是 SRAM 本体，而是：

- D-Cache 未 Clean/Invalidate。
- DMA 不具备访问该 FMC 地址区的总线路径。
- DMA 数据宽度与外部总线宽度不匹配。
- 缓冲区未对齐。
- DMA 与显示控制器争用总线导致超时。
- DMA 完成中断只表示传输结束，但外设 FIFO 或总线写缓冲尚未完全排空。

需要同时检查 MCU 总线矩阵、DMA 可达性和内存属性。

### 12.3 外部 SRAM 是否适合执行代码？

技术上可以，只要地址区可执行且控制器支持存储器映射。但通常不推荐：

- 访问延迟明显高于片内 Flash/ITCM。
- 指令取值与数据访问竞争外部总线。
- SRAM 易失，代码需要启动时搬运。
- Cache miss 会造成较大执行时间抖动。
- 安全攻击面增加。

适合迁移到 SRAM 的通常是少量性能关键函数，并优先放入片内 ITCM。

### 12.4 为什么开启 Cache 后测试速度极高，却不能证明 SRAM 时序正确？

因为 CPU 可能反复访问已缓存的数据，后续读操作根本没有到达外部 SRAM。写回 Cache 下，写操作也可能只修改 Cache line。

进行硬件时序和存储测试时应：

- 将区域设为 Non-cacheable。
- 或每轮显式 Clean/Invalidate。
- 使用大于 Cache 容量的数据集。
- 通过 `/CS`、`/OE`、`/WE` 波形确认真实总线事务。

### 12.5 SRAM 测试应选择 March C- 还是简单模式测试？

简单模式适合快速开机检查；March C- 更适合量产和深度诊断。March C- 能覆盖多类 stuck-at、transition、address decoder 和 coupling fault，但复杂度约为 `10N` 次操作。

建议：

- 研发与量产：全容量 March C-/March X。
- 冷启动：根据启动时间预算执行全测或分区全测。
- 运行期：分片执行非破坏性透明测试，避开业务占用区。
- 安全系统：按 IEC 61508、ISO 26262 或行业标准定义诊断覆盖率。

### 12.6 如何确定 FMC 最优时序，而不是一直使用最大等待周期？

采用“计算下限 + 实测收敛”的方法：

1. 根据 SRAM 最坏时序和 FMC 字段定义计算理论下限。
2. 加入 PCB、温度、电压和器件批次裕量。
3. 从保守参数开始执行全容量 March 测试。
4. 逐级减少等待周期并重复压力测试。
5. 在高温、低压和多主总线负载下验证。
6. 找到失效边界后至少回退一个或两个控制器周期。
7. 将参数与器件料号和 PCB 版本绑定，禁止跨平台复制。

---

## 13. 课程核心总结

### 13.1 核心要点

- **外部异步 SRAM 的核心优势是低且确定的随机访问延迟，不是容量密度。**
- 容量由“字数量 × 数据宽度”决定，16 位总线地址连接存在字节地址偏移问题。
- FMC 参数必须从 `tAA`、`tACS`、`tOE`、`tWP` 等最坏时序推导。
- Cache 提高 CPU 局部访问性能，但不会提高 SRAM 引脚物理带宽。
- DMA 与 Cache 一致性是外部存储最常见的软件故障源。
- 实时关键对象应留在片内 SRAM，大缓存和大块 payload 才迁移到外部。
- 全容量测试必须覆盖地址线、数据线、耦合故障和时序裕量。
- 生产系统应使用分区、固定块池、所有权状态机和运行时健康监控。

### 13.2 性能排序

随机访问确定性：

```
片内 TCM > 片内 SRAM > 同步 SRAM > 异步 SRAM
          > 并行 PSRAM > SDRAM > 串行 PSRAM
```

容量成本优势：

```
SDRAM > 串行/并行 PSRAM > 异步 SRAM > 同步 SRAM
```

引脚效率：

```
串行 PSRAM > 片内 SRAM > 并行 SRAM ≈ SDRAM
```

### 13.3 通用选型结论

- **小于数 MiB、要求确定性：异步 SRAM。**
- **大容量、高连续带宽：SDRAM。**
- **引脚紧张、允许较高延迟：OSPI PSRAM。**
- **硬实时控制状态：片内 SRAM/TCM。**
- **CPU 与 DMA 共享：优先独立 Non-cacheable DMA 分区。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|需求|首选|
|---|---|
|确定性随机访问|异步 SRAM|
|大容量图像缓存|SDRAM|
|少引脚大容量缓存|OSPI PSRAM|
|高速 FPGA 共享|同步 SRAM或双口 SRAM|
|ISR、控制环、任务栈|片内 SRAM/TCM|
|网络和采集报文池|外部 SRAM固定块池|
|DMA 高频写、CPU 后处理|Non-cacheable 外部 SRAM|

### 14.2 特性与处理方式

|问题|处理方式|
|---|---|
|地址映射异常|检查总线宽度导致的地址位偏移|
|字节写破坏邻字节|检查 `NBL0/NBL1`|
|高温随机错误|增大数据建立时间，检查信号完整性|
|DMA 读到旧数据|DMA 前 Clean D-Cache|
|CPU 读到 DMA 旧数据|DMA 后 Invalidate D-Cache|
|启动前 BusFault|调整初始化顺序或使用 `NOLOAD`|
|性能低|对齐访问、扩大访问粒度、使用 DMA|
|Cache 测试虚高|禁用 Cache 或强制维护并测引脚波形|
|地址混叠|执行地址唯一值和 walking-address 测试|
|实时抖动|关键数据留片内，安排 DMA 时隙|

### 14.3 常用计算公式

Capacity=WordCount×DataWidth/8Capacity=WordCount×DataWidth/8Tclock=1/FbusTclock​=1/Fbus​Nsetup≥⌈Trequired/Tclock⌉Nsetup​≥⌈Trequired​/Tclock​⌉Bandwidth=Bytes×FCPU/CyclesBandwidth=Bytes×FCPU​/CyclesFrameBuffer=Width×Height×BytesPerPixel×BufferCountFrameBuffer=Width×Height×BytesPerPixel×BufferCount

---

## 15. 学习效果自检

完成本课后，应能够独立回答并完成以下事项：

- 能从 `512K × 16` 推导容量和地址线数量。
- 能解释 16 位总线下 MCU 地址位与 SRAM 地址位的对应关系。
- 能根据 SRAM 数据手册计算 FMC 地址建立和数据建立周期。
- 能解释 `/CS`、`/OE`、`/WE`、`NBL0/NBL1` 的作用。
- 能区分 CPU Cache 命中带宽与 SRAM 物理总线带宽。
- 能设计 Cacheable 区和 Non-cacheable DMA 区。
- 能正确实现 DMA 前后的 Cache 维护。
- 能修改链接脚本，将对象放入外部 SRAM。
- 能避免在 FMC 初始化前清零外部 SRAM 段。
- 能实现地址线、数据线和全容量存储测试。
- 能使用 DWT 测量访问周期和吞吐量。
- 能根据实时性、容量和引脚约束选择 SRAM、PSRAM 或 SDRAM。
- 能说明为什么任务栈和控制环状态通常不应放在外部 SRAM。
- 能在示波器上判断读数据采样裕量是否充分。
- 能定义存储器故障后的告警、隔离和降级策略。

---

## 16. 实践与进阶路径

### 16.1 第一阶段：基础驱动与地址验证

任务：

1. 完成 FMC GPIO 和异步 SRAM 控制器初始化。
2. 实现 8、16、32 位读写接口。
3. 验证首地址、尾地址和边界检查。
4. 使用逻辑分析仪观察 `/CS`、`/OE`、`/WE` 波形。
5. 确认字节写对应的 `NBL0/NBL1` 行为。

验收标准：

- 全地址范围可访问。
- 无 BusFault。
- 8/16/32 位模式均无邻接数据破坏。
- 读写波形满足器件最坏时序。

### 16.2 第二阶段：存储故障测试

任务：

- walking-one 数据总线测试。
- walking-zero 数据总线测试。
- 地址唯一值测试。
- 地址线 walking-one 测试。
- 全容量反码测试。
- March C- 测试。

测试结果至少记录：

```
typedef struct {
    uintptr_t address;
    uint32_t expected;
    uint32_t actual;
    uint32_t phase;
} sram_failure_t;
```

验收标准：

- 能识别人为短接的一根数据线。
- 能识别人为短接的两根地址线。
- 能输出首个错误地址、期望值和实际值。
- 测试代码运行时关闭 Cache 或正确执行 Cache 维护。

### 16.3 第三阶段：性能与时序边界

任务：

1. 测量 8/16/32 位顺序读写吞吐量。
2. 比较 CPU 循环、`memcpy` 和 DMA。
3. 比较 Cache 开启与关闭。
4. 逐级缩短 FMC 数据建立周期。
5. 在总线并发压力下测量最坏延迟。

性能测试必须同时报告：

- CPU 和总线频率。
- SRAM 型号及速度等级。
- FMC 全部时序字段。
- Cache 和 MPU 属性。
- 数据长度与对齐方式。
- 编译器版本及优化级别。
- 平均值、最大值、最小值和 P99 延迟。

### 16.4 第四阶段：工业级内存架构

实现以下完整系统：

```
片内 SRAM
├─ RTOS 内核对象
├─ ISR 栈和任务栈
├─ 高频描述符
└─ 控制算法状态

外部 SRAM
├─ Cacheable 业务缓存
├─ Non-cacheable DMA 双缓冲
├─ 固定块报文池
└─ 启动/运行期诊断区
```

验收标准：

- DMA 与 CPU 并发运行 24 小时无一致性错误。
- 固定块池分配和释放具有常数时间上界。
- 缓冲耗尽时有明确背压或丢弃策略。
- 外部 SRAM 故障后系统进入可定义的安全状态。
- MPU 禁止从纯数据区执行代码。

### 16.5 进阶学习方向

- Cortex-M7 AXI/AHB 总线矩阵与仲裁策略。
- MPU Normal/Device/Strongly-ordered 属性差异。
- Write-through、Write-back、Write-allocate 的总线行为。
- SDRAM 行命中、Bank 交错、刷新和时序优化。
- HyperRAM、OSPI PSRAM 和内存映射接口。
- March C-、March SS 与透明 RAM 测试算法。
- IEC 61508、ISO 26262 下的 RAM 诊断覆盖率。
- PCB 地址/数据总线串扰、源端终端和眼图分析。
- 多核 MCU 的 Cache coherent 与 non-coherent 共享内存设计。
- ECC SRAM、奇偶校验和软件冗余存储架构。