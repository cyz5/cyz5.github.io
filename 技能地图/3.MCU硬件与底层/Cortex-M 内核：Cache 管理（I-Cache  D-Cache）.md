
## 1. 学习目标

### 理解

- 理解 Cortex-M 内核中 **I-Cache、D-Cache、TCM、MPU、Shareability、Memory Attribute** 的关系。
- 理解 Cache line、Tag、Valid、Dirty、Write-back、Write-through 的底层工作机制。
- 理解 DMA 与 D-Cache 并发访问时产生的数据不一致问题。
- 理解 `Clean`、`Invalidate`、`CleanInvalidate` 三类 Cache 维护操作的语义差异。

### 掌握

- 掌握 Cortex-M7/M33/M55 等不同内核的 Cache 能力边界。
- 掌握 CMSIS Cache API 的正确使用时机和内存屏障要求。
- 掌握 DMA 接收、DMA 发送、非 Cache 区域、Buffer 对齐等工程实现方法。
- 掌握 I-Cache 代码更新、Bootloader 跳转、Flash 擦写后的指令一致性维护。

### 精通

- 能够从 MPU 属性、Cache policy、内存屏障和外设总线访问路径分析一致性问题。
- 能够量化 Cache 对执行时间、总线带宽、功耗和实时性的影响。
- 能够诊断 HardFault、DMA 数据污染、偶发协议错误和自修改代码异常。
- 能够根据实时性、吞吐量、内存容量和 DMA 使用情况制定 Cache 管理策略。

### 能够设计

- 能够设计适用于工业控制、网络通信、图像采集和 Bootloader 的 Cache 架构。
- 能够设计统一的 Cache-safe DMA Buffer 管理层。
- 能够定义 Cache 维护接口、内存分区、MPU 属性和代码审查规范。
- 能够建立基于 DWT、GPIO、ETM 或逻辑分析仪的 Cache 性能测试方案。

---

## 2. 前置要求

### 知识要求

- ARMv7-M 或 ARMv8-M 异常模型、特权级、栈和内存映射。
- Cortex-M 总线结构：I-Code、D-Code、System Bus、AHB、AXI。
- C 语言指针、数组、结构体、`volatile`、链接脚本和 section。
- DMA 基本原理，包括源地址、目的地址、突发传输和循环模式。
- MPU region、内存属性和内存屏障指令。
- RTOS 任务切换、中断上下文和共享缓冲区设计。

### 技能要求

- 能够阅读芯片 Reference Manual 和 Cortex-M Technical Reference Manual。
- 能够分析 `.map` 文件和链接脚本。
- 能够使用 DWT、GPIO、逻辑分析仪或示波器测量执行时间。
- 能够编写 DMA 外设驱动和中断回调。
- 能够使用 CMSIS-Core、调试器和反汇编工具定位异常。

---

## 3. 技术概述

### 3.1 Cache 的核心定义

Cache 是位于 CPU 与主存储器之间的小容量高速存储器。它利用程序访问的两个局部性：

- **时间局部性**：近期访问的数据可能再次被访问。
- **空间局部性**：访问某个地址后，附近地址可能很快被访问。

Cache 并不是简单的“高速 RAM”，而是一个由以下信息组成的硬件结构：

```
Cache Line
+---------+---------+----------------------+
| Valid   | Tag     | Data                 |
+---------+---------+----------------------+
```

Cache 对地址进行拆分：

```
地址 = Tag + Set Index + Line Offset
```

其中：

- `Line Offset`：确定 Cache line 内部的字节位置。
- `Set Index`：确定地址映射到哪个 set。
- `Tag`：判断当前 line 是否保存目标地址的数据。
- `Valid`：判断当前 line 是否有效。
- `Dirty`：Write-back Cache 中标识数据是否已经被 CPU 修改。

### 3.2 Cortex-M Cache 的典型分布

|Cortex-M 内核|I-Cache|D-Cache|典型应用|
|---|---|---|---|
|Cortex-M0/M0+|无|无|低成本控制|
|Cortex-M3|通常无|通常无|工业控制、通信|
|Cortex-M4|通常无|通常无|DSP、控制算法|
|Cortex-M7|有|有|高性能 MCU、网络、图形|
|Cortex-M23|通常无|通常无|TrustZone 低功耗设备|
|Cortex-M33|视芯片实现|视芯片实现|安全、无线、控制|
|Cortex-M55|通常有|通常有|AI、DSP、边缘计算|

**Cache 是否存在、容量、关联度和策略由具体芯片实现决定，不能仅根据 Cortex-M 型号推断。**

例如某些 Cortex-M7 MCU 可能具有：

```
I-Cache: 16 KB，4-way，32-byte line
D-Cache: 16 KB，4-way，32-byte line
```

但另一个芯片可能为 32 KB Cache，Cache line 也可能不同。工程代码必须使用芯片手册或 CMSIS 定义确认：

```
#define CACHE_LINE_SIZE 32U
```

不要假设所有 Cortex-M 都是 32 字节 Cache line。

### 3.3 I-Cache 与 D-Cache 的职责

#### I-Cache

I-Cache 缓存 CPU 从代码存储区域取出的指令，主要改善：

- Flash 执行速度。
- 分支密集代码执行效率。
- 复杂控制算法和协议栈执行效率。
- 从外部 QSPI/XIP Flash 执行代码的性能。

#### D-Cache

D-Cache 缓存 CPU 读写的数据，主要改善：

- SRAM 访问性能。
- 外部 SDRAM、PSRAM、OSPI RAM 访问性能。
- 图像、网络、音频数据处理吞吐量。
- CPU 对连续数据的访问效率。

### 3.4 TCM 与 Cache 的关系

TCM，即 Tightly Coupled Memory，通常通过专用路径与 CPU 紧耦合：

```
CPU
├── ITCM -> 指令
├── DTCM -> 数据
└── AXI/AHB -> SRAM、Flash、外设
```

TCM 的特点：

- 通常不经过 Cache。
- 访问延迟可预测。
- 适合硬实时 ISR、控制环和关键数据。
- 容量较小。
- DMA 是否能访问 DTCM 取决于芯片总线结构，很多 DMA 无法访问 DTCM。

因此：

|存储区域|Cache|延迟|DMA 可见性|适用场景|
|---|---|---|---|---|
|ITCM|否|稳定|通常不适用于 DMA|实时关键代码|
|DTCM|否|稳定|可能不可见|控制变量、ISR 数据|
|内部 SRAM|视 MPU/芯片配置|较低|通常可见|普通数据、DMA|
|外部 SDRAM|通常是|高且波动|通常可见|大容量图像缓冲|
|外设寄存器|禁止 Cache|设备定义|外设访问|MMIO|
|Flash/XIP|I-Cache|命中快、未命中慢|通常不用于 DMA|程序代码|

---

## 4. 核心特性横向对比

### 4.1 Cache 策略对比

|维度|Write-through|Write-back|
|---|---|---|
|CPU 写操作|同时写 Cache 和内存|只写 Cache，稍后回写内存|
|写延迟|较高|较低|
|内存带宽|较高|较低|
|数据一致性风险|相对较低|较高|
|是否需要 Clean|通常不需要处理普通 CPU 写|DMA 读取前通常必须 Clean|
|适合场景|共享数据、简单系统|高性能 CPU 数据处理|
|典型代价|每次写都可能访问总线|需要显式维护和更复杂调试|

### 4.2 Cache 维护操作对比

|操作|作用|CPU 继续访问时的数据|内存中的数据|典型场景|
|---|---|---|---|---|
|Clean|将 Dirty line 写回内存，保留 Cache line|保留|更新|DMA 读取前|
|Invalidate|丢弃 Cache line，不写回|重新从内存读取|保留原值|DMA 写入后|
|CleanInvalidate|先写回，再丢弃|后续重新读取|更新|CPU/DMA 双向切换、不确定状态|
|Disable|关闭 Cache|依赖实现|可能仍有 Dirty 数据|初始化或故障恢复|
|Enable|开启 Cache|建立新的缓存状态|不自动解决所有一致性问题|系统启动|

### 4.3 Cache 与内存属性对比

|属性|Cacheable|Bufferable|Shareable|典型用途|
|---|---|---|---|---|
|Normal Cacheable|是|通常是|可配置|SRAM、SDRAM、Flash|
|Normal Non-cacheable|否|可配置|可配置|DMA Buffer|
|Device|否|通常有限制|通常是|外设寄存器|
|Strongly Ordered|否|否|是|老版本架构语义|
|TCM|通常不适用 Cache|由内核路径决定|由实现决定|硬实时数据|

### 4.4 DMA 方向与维护策略

|DMA 方向|CPU 在 DMA 前的动作|DMA 完成后的动作|
|---|---|---|
|Memory -> Peripheral|Clean|通常无需 Invalidate|
|Peripheral -> Memory|通常不需要 Clean，除非目标 line 已被 CPU 缓存|Invalidate|
|Memory <-> Peripheral|Clean|Invalidate|
|CPU 与 DMA 交替读写|根据所有权转换执行 Clean/Invalidate|严格定义 Buffer ownership|

---

## 5. 底层原理与功能特性深度解析

## 5.1 D-Cache 数据不一致的本质

假设内存地址 `0x24001000` 初始值为 `0x00`。

CPU 读取后：

```
Memory:     0x00
D-Cache:    0x00，Valid = 1
```

CPU 修改数据：

```
CPU 写入:    0x55
D-Cache:    0x55，Dirty = 1
Memory:     0x00
```

此时 DMA 读取同一地址：

```
DMA 读取 Memory -> 得到 0x00
CPU 读取地址   -> 得到 0x55
```

这不是 `volatile` 能解决的问题。`volatile` 只约束编译器生成访问，不会清除 CPU Cache，也不会让 DMA 看到 Cache 中的数据。

### 5.2 DMA 发送：Clean

DMA 从内存读取数据发送到外设，CPU 可能已经将最新数据写入 D-Cache，因此必须将缓存数据写回内存。

```
#include "cmsis_gcc.h"
#include <stdint.h>
#include <stddef.h>

#define CACHE_LINE_SIZE 32U

static uintptr_t align_down(uintptr_t address, uintptr_t alignment)
{
    return address & ~(alignment - 1U);
}

static uintptr_t align_up(uintptr_t address, uintptr_t alignment)
{
    return (address + alignment - 1U) & ~(alignment - 1U);
}

static void dcache_clean_range(const void *address, size_t length)
{
    uintptr_t start;
    uintptr_t end;

    if ((address == NULL) || (length == 0U)) {
        return;
    }

    start = align_down((uintptr_t)address, CACHE_LINE_SIZE);
    end = align_up((uintptr_t)address + length, CACHE_LINE_SIZE);

    SCB_CleanDCache_by_Addr((uint32_t *)start, (int32_t)(end - start));
    __DSB();
}
```

发送流程：

```
static uint8_t tx_buffer[256] __attribute__((aligned(CACHE_LINE_SIZE)));

int dma_tx_start(const uint8_t *data, size_t length)
{
    if ((data == NULL) || (length == 0U) || (length > sizeof(tx_buffer))) {
        return -1;
    }

    memcpy(tx_buffer, data, length);

    /*
     * 保证 DMA 从内存读取到 CPU 最新写入的数据。
     */
    dcache_clean_range(tx_buffer, length);

    /*
     * 外设寄存器配置应在 Clean 后执行，避免启动时序问题。
     */
    dma_config_memory_to_peripheral(tx_buffer, length);
    dma_enable();

    return 0;
}
```

### 5.3 DMA 接收：Invalidate

DMA 向内存写数据时，CPU 可能已经缓存了目标地址的旧数据。

如果 DMA 完成后 CPU 直接读取地址，CPU 可能继续读到旧 Cache line。因此 DMA 完成后必须 Invalidate。

```
static void dcache_invalidate_range(void *address, size_t length)
{
    uintptr_t start;
    uintptr_t end;

    if ((address == NULL) || (length == 0U)) {
        return;
    }

    start = align_down((uintptr_t)address, CACHE_LINE_SIZE);
    end = align_up((uintptr_t)address + length, CACHE_LINE_SIZE);

    __DSB();

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                 (int32_t)(end - start));
    __DSB();
}
```

接收流程：

```
static uint8_t rx_buffer[256] __attribute__((aligned(CACHE_LINE_SIZE)));

int dma_rx_start(void)
{
    /*
     * 丢弃 CPU 可能已经缓存的旧数据。
     * 如果该 Cache line 中存在 CPU Dirty 数据，直接 Invalidate
     * 会造成数据丢失，因此接收 Buffer 不应被 CPU 提前修改。
     */
    dcache_invalidate_range(rx_buffer, sizeof(rx_buffer));

    dma_config_peripheral_to_memory(rx_buffer, sizeof(rx_buffer));
    dma_enable();

    return 0;
}

void dma_rx_complete_callback(size_t received_length)
{
    if (received_length > sizeof(rx_buffer)) {
        dma_abort();
        return;
    }

    /*
     * DMA 已经修改内存，必须让 CPU 丢弃旧 Cache line。
     */
    dcache_invalidate_range(rx_buffer, received_length);

    process_rx_data(rx_buffer, received_length);
}
```

### 5.4 为什么必须按 Cache line 对齐

Cache 维护操作通常以 Cache line 为单位。假设 Cache line 是 32 字节：

```
地址范围：0x20000010 ~ 0x2000001F
实际需要维护：0x20000000 ~ 0x2000001F
```

如果只维护未对齐区间，可能出现：

1. 起始 Cache line 没有被完整处理。
2. 结束 Cache line 没有被完整处理。
3. 同一个 Cache line 中相邻对象被意外写回或丢弃。
4. 不同 DMA Buffer 共享 Cache line，导致数据互相污染。

建议：

```
#define CACHE_ALIGNED __attribute__((aligned(CACHE_LINE_SIZE)))

static uint8_t dma_rx_buffer[512] CACHE_ALIGNED;
```

除了首地址对齐，**Buffer 长度也最好按 Cache line 对齐**：

```
static uint8_t dma_rx_buffer[512] CACHE_ALIGNED;
```

如果实际长度不是 Cache line 的整数倍，应通过独立 Buffer 或严格的所有权协议避免与其他变量共享末尾 Cache line。

### 5.5 Clean 和 Invalidate 的顺序

对于双向 DMA 或 CPU/DMA 交替使用的 Buffer，推荐顺序：

```
CPU 写数据
    |
    | Clean
    v
DMA 读取或修改
    |
    | DMA 完成
    | Invalidate
    v
CPU 读取数据
```

若一个 Buffer 同时可能包含：

- CPU 未提交的 Dirty 数据；
- DMA 即将写入的新数据；

直接执行 Invalidate 会丢失 CPU Dirty 数据。因此必须先定义 Buffer 所有权：

```
CPU Owned -> DMA Owned -> CPU Owned
```

在 RTOS 中可通过状态机、信号量或消息队列实现：

```
typedef enum {
    BUFFER_CPU_OWNED,
    BUFFER_DMA_OWNED
} buffer_owner_t;

typedef struct {
    uint8_t *data;
    size_t capacity;
    size_t length;
    buffer_owner_t owner;
} dma_buffer_t;
```

### 5.6 I-Cache 管理

I-Cache 的典型问题出现在：

- Bootloader 跳转到应用程序。
- Flash 擦写后执行新代码。
- 运行时加载代码。
- OTA 更新后切换镜像。
- XIP Flash 映射变化。
- 中断向量表重定位。

如果代码存储区域内容发生变化，必须保证：

1. 数据写入已经完成。
2. 数据 Cache 已清理。
3. 指令 Cache 已失效。
4. CPU 已执行必要的同步屏障。

典型流程：

```
typedef void (*app_entry_t)(void);

__attribute__((noreturn))
static void jump_to_application(uint32_t app_base)
{
    uint32_t app_stack;
    uint32_t app_reset_handler;
    app_entry_t entry;

    app_stack = *(volatile uint32_t *)(app_base + 0U);
    app_reset_handler = *(volatile uint32_t *)(app_base + 4U);

    if ((app_stack & 0x2FFE0000U) != 0x20000000U) {
        system_fault();
    }

    __disable_irq();

    /*
     * 关闭期间先清理旧执行上下文和缓存状态。
     */
    SysTick->CTRL = 0U;
    SysTick->LOAD = 0U;
    SysTick->VAL = 0U;

    SCB_DisableDCache();
    SCB_DisableICache();

    SCB_CleanInvalidateDCache();
    SCB_InvalidateICache();

    __DSB();
    __ISB();

    SCB->VTOR = app_base;
    __DSB();
    __ISB();

    __set_MSP(app_stack);

    entry = (app_entry_t)(app_reset_handler | 1U);
    entry();

    for (;;) {
        __NOP();
    }
}
```

实际工程中还需要：

- 停止 DMA。
- 关闭外设中断。
- 清除 NVIC pending 状态。
- 关闭 MPU 或重新配置 MPU。
- 检查应用入口地址 Thumb 位。
- 检查向量表地址对齐。
- 处理 TrustZone Secure/Non-secure 状态切换。

### 5.7 内存屏障

#### `DMB`

Data Memory Barrier，保证内存访问顺序，对后续访问进行排序，但不一定等待所有访问完成。

#### `DSB`

Data Synchronization Barrier，等待此前显式内存访问完成。

适合：

- Cache maintenance 后。
- 修改系统控制寄存器后。
- 关闭 Cache 前。
- 启动 DMA 前后的关键同步点。

#### `ISB`

Instruction Synchronization Barrier，使处理器丢弃预取指令并重新获取指令流。

适合：

- 修改 `CONTROL`、`VTOR`、MPU、Cache 控制寄存器后。
- 开启或关闭 I-Cache 后。
- 修改执行权限或内存属性后。

典型组合：

```
SCB_CleanDCache_by_Addr(ptr, length);
__DSB();

SCB_InvalidateICache();
__DSB();
__ISB();
```

---

## 6. 性能量化分析

### 6.1 测试平台假设

以下数据采用一类典型 Cortex-M7 MCU 作为参考：

```
CPU 主频：400 MHz
I-Cache：16 KB，32-byte line
D-Cache：16 KB，32-byte line
内部 SRAM：零等待或低等待
外部 SDRAM：约 100~150 MHz
编译器：Arm GCC -O2
测量方式：DWT->CYCCNT
```

数据是工程估算范围，不代表所有芯片的固定结果。最终数据必须在目标芯片上实测。

### 6.2 典型访问延迟

|访问类型|典型周期范围|
|---|---|
|DTCM 命中|1~2 cycles|
|D-Cache 命中|2~5 cycles|
|内部 SRAM 未命中|3~10 cycles|
|Flash + I-Cache 命中|1~5 cycles|
|Flash 未命中|10~50 cycles|
|外部 SDRAM 命中|5~20 cycles|
|外部 SDRAM 未命中|30~150+ cycles|
|Cache line refill|取决于总线、突发长度和存储器等待状态|

400 MHz 下：

```
1 cycle = 1 / 400 MHz = 2.5 ns
100 cycles = 250 ns
1000 cycles = 2.5 us
```

### 6.3 Cache 命中率与平均访问时间

平均访问时间可近似表示为：

```
AMAT = Hit Time + Miss Rate × Miss Penalty
```

例如：

```
Hit Time    = 3 cycles
Miss Rate   = 5%
Miss Penalty = 60 cycles

AMAT = 3 + 0.05 × 60
     = 6 cycles
```

如果 Cache 被关闭：

```
平均访问时间 ≈ 60 cycles
```

理想情况下，Cache 可带来约：

```
60 / 6 = 10 倍
```

但实际程序会受到：

- 分支跳转。
- Cache 冲突。
- Flash wait state。
- 总线仲裁。
- DMA 竞争。
- 数据访问模式。

因此不能只看理论命中率。

### 6.4 Cache 维护开销

以 32-byte Cache line 为例：

```
维护行数 = ceil((address + length) / 32) - floor(address / 32)
```

例如：

```
Buffer 起始地址：0x24001004
Buffer 长度：100 bytes

覆盖 Cache line：
0x24001000
0x24001020
0x24001040
0x24001060
0x24001080

维护行数 = 5
```

假设每个 Cache line 维护平均 20~40 cycles：

```
Clean/Invalidate 开销 ≈ 5 × 30 = 150 cycles
```

在 400 MHz 下约为：

```
150 × 2.5 ns = 375 ns
```

如果每 1 ms 维护一次 4 KB Buffer：

```
Cache line 数 = 4096 / 32 = 128
单次约 128 × 30 = 3840 cycles
CPU 占用 ≈ 3840 / 400000 = 0.96%
```

这还没有计算 DMA 中断、协议解析和总线竞争。

### 6.5 性能瓶颈

#### Cache thrashing

当多个高频访问区域映射到相同 set 时，会反复驱逐 Cache line：

```
A -> Cache set 3
B -> Cache set 3
C -> Cache set 3
D -> Cache set 3
```

即使总数据量没有超过 Cache 容量，也可能出现高 Miss Rate。

#### 大步长访问

```
for (size_t i = 0; i < rows; i++) {
    sum += matrix[i][0];
}
```

如果每次跳过一整行，空间局部性很差。

#### 代码过大

函数分散在多个区域或分支路径过多，会使 I-Cache 命中率下降。

#### DMA 与 CPU 争用总线

Cache 命中时 CPU 不访问主存，但 Cache miss、Clean、Invalidate 和 DMA 都会争抢总线，可能导致实时任务抖动。

### 6.6 优化手段与收益

|优化手段|适用问题|典型收益|
|---|---|---|
|将 ISR 放入 ITCM|ISR 抖动、Flash 等待|延迟下降，抖动减小|
|将控制变量放入 DTCM|高频读取、硬实时|访问延迟稳定|
|DMA Buffer 放入 Non-cacheable SRAM|频繁 Cache 维护|降低 CPU 维护开销|
|Buffer 按 Cache line 对齐|伪共享、无效维护范围|降低数据污染风险|
|增大 DMA Buffer|中断频率过高|降低中断开销|
|使用双 Buffer|CPU/DMA 并发|提高吞吐量|
|改善访问连续性|Cache miss 高|提升空间局部性|
|减少热路径代码体积|I-Cache 冲突|提高指令命中率|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否使用 DMA 访问该 Buffer？
├── 否
│   ├── 是否要求严格、可预测的实时延迟？
│   │   ├── 是 -> 放入 TCM 或配置为 Non-cacheable
│   │   └── 否 -> 使用 Cacheable Normal Memory
│   └── 是否为外设寄存器？
│       ├── 是 -> Device Memory，禁止 Cache
│       └── 否 -> Cacheable Normal Memory
└── 是
    ├── DMA 访问频率高、Buffer 较大？
    │   ├── 是 -> 优先放入 Non-cacheable DMA SRAM
    │   └── 否 -> Cacheable + 明确 Clean/Invalidate
    ├── CPU 与 DMA 是否同时访问同一 Buffer？
    │   ├── 是 -> 使用所有权状态机或双 Buffer
    │   └── 否 -> 单 Buffer + 方向性 Cache 维护
    └── 是否必须硬实时？
        ├── 是 -> 避免运行时 Cache maintenance，使用 TCM/Non-cacheable
        └── 否 -> 可接受显式 Clean/Invalidate
```

### 7.2 典型场景选型

|场景|推荐方案|理由|
|---|---|---|
|Ethernet RX Descriptor|Non-cacheable 或严格 Invalidate|DMA 高频写入，数据一致性优先|
|Ethernet TX Buffer|Cacheable + Clean|CPU 组包后由 DMA 读取|
|ADC DMA 连续采样|Non-cacheable 或半缓冲 Invalidate|长时间连续写入|
|LCD Framebuffer|Cacheable + Clean，或 Non-cacheable|CPU 绘制后显示控制器读取|
|电机控制 ISR|ITCM + DTCM|延迟和抖动可预测|
|QSPI XIP 程序|I-Cache|显著降低 Flash 取指延迟|
|OTA 更新代码区|关闭/失效对应 Cache|防止执行旧指令|
|外设寄存器|Device Memory|防止错误合并、预取和缓存|
|多核共享内存|Shareable + 明确同步|Cortex-M 系列或异构系统协同|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **先按所有权设计，再决定 Cache 维护位置。**
2. **DMA Buffer 与普通变量物理隔离。**
3. **所有 DMA Buffer 按 Cache line 对齐。**
4. **不要通过 `volatile` 代替 Cache 一致性处理。**
5. **外设寄存器必须使用 Device 属性。**
6. **中断路径中避免大范围 Cache maintenance。**
7. **Bootloader、OTA 和 XIP 必须定义 I-Cache 管理流程。**
8. **将实时性要求高的代码和数据放入 TCM。**
9. **Cache API 封装在平台层，业务层不直接散落调用 CMSIS API。**
10. **Cache line size、MPU 属性和内存区域必须由配置统一生成或集中定义。**

### 8.2 选型决策矩阵

|需求|Cacheable|Non-cacheable|TCM|
|---|---|---|---|
|CPU 吞吐量|高|中|高|
|延迟确定性|中|高|最高|
|DMA 兼容性|需维护|高|取决于 DMA|
|CPU 访问大数据|优|一般|不适合容量大|
|实现复杂度|中|低|中|
|内存容量|通常较大|通常较大|小|
|适合硬实时|谨慎|可以|最佳|

### 8.3 工业级编码规范

建议统一提供以下接口：

```
typedef enum {
    CACHE_ACCESS_CPU_TO_DMA,
    CACHE_ACCESS_DMA_TO_CPU,
    CACHE_ACCESS_BIDIRECTIONAL
} cache_dma_direction_t;

int cache_prepare_dma(void *buffer,
                      size_t length,
                      cache_dma_direction_t direction);

int cache_complete_dma(void *buffer,
                       size_t length,
                       cache_dma_direction_t direction);
```

接口内部完成：

- 空指针和长度检查。
- 地址对齐。
- 长度溢出检查。
- Cache line size 适配。
- 必要的 `DMB/DSB/ISB`。
- 调试版本的地址范围断言。
- 对禁止使用的 DTCM 地址进行检查。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：DMA 接收完成后不 Invalidate

错误代码：

```
void dma_done(void)
{
    process_data(rx_buffer, rx_length);
}
```

根因：

- CPU 之前读取过 `rx_buffer`。
- 旧数据仍在 D-Cache 中。
- DMA 只修改了主存，没有更新 CPU Cache。

正确实现：

```
void dma_done(void)
{
    dcache_invalidate_range(rx_buffer, rx_length);
    process_data(rx_buffer, rx_length);
}
```

风险影响：

- 偶发接收旧数据。
- CRC 错误。
- 网络协议解析失败。
- 难以复现的现场故障。

### 9.2 错误二：DMA 发送前只使用 `volatile`

错误代码：

```
volatile uint8_t tx_buffer[256];

memcpy((void *)tx_buffer, data, length);
dma_start((void *)tx_buffer, length);
```

根因：

- `volatile` 只影响编译器。
- CPU 写入可能停留在 Dirty D-Cache。
- DMA 从主存读取旧数据。

正确实现：

```
memcpy(tx_buffer, data, length);
dcache_clean_range(tx_buffer, length);
dma_start(tx_buffer, length);
```

风险影响：

- 发送旧报文。
- 帧头正确、负载错误。
- 只在开启 D-Cache 时出现。

### 9.3 错误三：对未对齐 Buffer 直接维护

错误代码：

```
SCB_CleanDCache_by_Addr((uint32_t *)&buffer[1], 64);
```

根因：

- 地址和长度没有覆盖完整 Cache line。
- 该 Buffer 可能与相邻变量共享 Cache line。

正确实现：

```
dcache_clean_range(&buffer[1], 64);
```

其中 `dcache_clean_range()` 内部完成地址向下对齐、结束地址向上对齐。

风险影响：

- 相邻数据被错误写回。
- Cache line 未完全维护。
- DMA 数据出现边界错误。

### 9.4 错误四：Invalidate 一个包含 CPU Dirty 数据的 Cache line

错误代码：

```
rx_buffer[0] = 0xAA;
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buffer, 32);
```

根因：

- `rx_buffer` 所在 Cache line 已经 Dirty。
- Invalidate 直接丢弃 Dirty line，不写回主存。

正确实现：

```
/*
 * DMA RX Buffer 交给 DMA 前不得包含 CPU 未提交数据。
 */
dcache_clean_invalidate_range(rx_buffer, sizeof(rx_buffer));
dma_start_rx(rx_buffer, sizeof(rx_buffer));
```

更好的方案是：

- CPU 和 DMA 使用独立 Buffer。
- Buffer 交接前禁止另一方访问。
- RX Buffer 放入 Non-cacheable 区域。

风险影响：

- CPU 写入的数据静默丢失。
- 相邻对象数据损坏。
- 状态机异常。

### 9.5 错误五：修改代码后只清 D-Cache，不失效 I-Cache

错误代码：

```
flash_program(app_address, image, image_size);
SCB_CleanDCache();
jump_to_app(app_address);
```

根因：

- I-Cache 仍然可能保存旧指令。
- CPU 执行的是旧 Cache line 中的代码。

正确实现：

```
flash_program(app_address, image, image_size);

SCB_CleanDCache();
__DSB();

SCB_InvalidateICache();
__DSB();
__ISB();
```

风险影响：

- 执行旧版本代码。
- 指令异常。
- 更新后首次启动失败。

### 9.6 错误六：把 DTCM Buffer 交给 DMA

错误代码：

```
__attribute__((section(".dtcm_data")))
static uint8_t dma_buffer[512];

dma_start(dma_buffer, sizeof(dma_buffer));
```

根因：

- 许多 DMA 控制器不在 DTCM 总线可达范围内。
- 这不是 Cache 一致性问题，而是 DMA 地址不可访问问题。

正确实现：

```
__attribute__((section(".dma_sram")))
__attribute__((aligned(CACHE_LINE_SIZE)))
static uint8_t dma_buffer[512];
```

风险影响：

- DMA 无响应。
- 总线错误。
- 外设传输超时。

---

## 10. 多机制组合使用方案

### 10.1 推荐架构

```
应用层
  |
DMA Buffer API
  |
Cache Policy Layer
  |
MPU Configuration
  |
CMSIS Cache API
  |
Cortex-M Cache / TCM / SRAM / External Memory
```

### 10.2 双 Buffer DMA 框架

```
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define RX_BUFFER_COUNT 2U
#define RX_BUFFER_SIZE  512U

typedef enum {
    RX_BUF_FREE,
    RX_BUF_DMA_ACTIVE,
    RX_BUF_READY,
    RX_BUF_PROCESSING
} rx_state_t;

typedef struct {
    uint8_t data[RX_BUFFER_SIZE]
        __attribute__((aligned(CACHE_LINE_SIZE)));
    size_t length;
    rx_state_t state;
} rx_buffer_t;

static rx_buffer_t rx_buffers[RX_BUFFER_COUNT];

static rx_buffer_t *find_free_buffer(void)
{
    for (size_t i = 0U; i < RX_BUFFER_COUNT; ++i) {
        if (rx_buffers[i].state == RX_BUF_FREE) {
            return &rx_buffers[i];
        }
    }

    return NULL;
}

int rx_dma_submit(void)
{
    rx_buffer_t *buffer = find_free_buffer();

    if (buffer == NULL) {
        return -1;
    }

    /*
     * 确保 DMA 不会看到 CPU 旧 Cache line。
     * RX Buffer 不应包含 CPU Dirty 数据。
     */
    dcache_invalidate_range(buffer->data, sizeof(buffer->data));

    buffer->length = 0U;
    buffer->state = RX_BUF_DMA_ACTIVE;

    if (dma_start_rx(buffer->data, sizeof(buffer->data)) != 0) {
        buffer->state = RX_BUF_FREE;
        return -1;
    }

    return 0;
}

void rx_dma_complete(rx_buffer_t *buffer, size_t length)
{
    if ((buffer == NULL) ||
        (buffer->state != RX_BUF_DMA_ACTIVE) ||
        (length > RX_BUFFER_SIZE)) {
        dma_abort();
        return;
    }

    dcache_invalidate_range(buffer->data, length);

    buffer->length = length;
    buffer->state = RX_BUF_READY;

    notify_rx_task(buffer);
}

void rx_task_process(rx_buffer_t *buffer)
{
    if ((buffer == NULL) || (buffer->state != RX_BUF_READY)) {
        return;
    }

    buffer->state = RX_BUF_PROCESSING;
    protocol_parse(buffer->data, buffer->length);
    buffer->state = RX_BUF_FREE;

    /*
     * 重新提交前，Buffer 已经不再被 CPU 使用。
     */
    (void)rx_dma_submit();
}
```

### 10.3 MPU 配置策略

可以将 DMA SRAM 配置为：

```
Normal Memory
Non-cacheable
Shareable
Read/Write
Execute Never
```

普通数据区配置为：

```
Normal Memory
Write-back
Write-allocate
Non-shareable
Read/Write
Execute Never
```

代码区配置为：

```
Normal Memory
Read-only
Cacheable
Executable
```

外设区配置为：

```
Device Memory
Shareable
Read/Write
Execute Never
```

---

## 11. 工业级实际案例分析

### 11.1 案例一：以太网 DMA 收发

#### 需求

- 100 Mbps 或 1 Gbps Ethernet。
- DMA 描述符环形队列。
- CPU 运行 TCP/IP 协议栈。
- 支持零拷贝或低拷贝收发。

#### 架构设计

```
Ethernet DMA
  |
  +-- Descriptor: Non-cacheable
  |
  +-- RX Buffer: Non-cacheable 或 DMA 完成后 Invalidate
  |
  +-- TX Buffer: Cacheable，发送前 Clean
  |
TCP/IP Task
```

#### 设计要点

- Descriptor 建议放入 Non-cacheable SRAM。
- RX Buffer 必须在 CPU 读取前 Invalidate。
- TX Buffer 在 DMA 发送前 Clean。
- Descriptor 状态更新必须配合 `DMB/DSB`。
- 不允许 CPU 与 DMA 同时拥有同一个 Descriptor。

示例：

```
static int eth_tx_submit(uint8_t *buffer, size_t length)
{
    if ((buffer == NULL) || (length == 0U)) {
        return -1;
    }

    dcache_clean_range(buffer, length);
    __DMB();

    eth_dma_desc->buffer = (uintptr_t)buffer;
    eth_dma_desc->length = length;
    eth_dma_desc->status = ETH_DESC_READY;

    __DSB();
    eth_dma_kick();

    return 0;
}
```

### 11.2 案例二：LCD 图像帧缓冲

#### 需求

- CPU 绘制 UI。
- LTDC/DSI 控制器从 SDRAM 读取 Framebuffer。
- 支持双 Buffer。
- 避免撕裂和颜色异常。

#### 架构设计

```
Frame Buffer A: CPU 绘制
Frame Buffer B: LCD DMA 扫描
             |
             +-- VSYNC 时交换
             +-- CPU 完成绘制后 Clean
```

#### 核心代码

```
void framebuffer_present(uint8_t *framebuffer, size_t size)
{
    /*
     * LCD 控制器将从外部内存读取最新图像数据。
     */
    dcache_clean_range(framebuffer, size);

    __DSB();

    lcd_set_pending_framebuffer(framebuffer);
    lcd_wait_vsync();
    lcd_commit_framebuffer();
}
```

#### 设计要点

- Framebuffer 大小可能达到数百 KB，逐帧 Clean 有明显开销。
- 若刷新率 60 Hz，单帧 Cache 维护成本可能成为 CPU 负担。
- 可以考虑：
    - Framebuffer 放到 Non-cacheable SDRAM。
    - 使用局部 Dirty Region，只 Clean 被修改区域。
    - 使用硬件 2D 加速器。
    - 使用双 Buffer 或三 Buffer。
    - 控制 Cache policy，避免大量写分配造成额外回写。

### 11.3 案例三：Bootloader OTA 更新

#### 需求

- Bootloader 接收新镜像。
- 写入内部 Flash 或外部 Flash。
- 校验镜像。
- 跳转到应用程序。
- 保证升级失败可恢复。

#### 关键流程

```
接收镜像
  |
DMA RX 完成 -> Invalidate
  |
镜像校验
  |
Flash 擦除/写入
  |
校验 Flash 内容
  |
Clean D-Cache
  |
Invalidate I-Cache
  |
更新 VTOR / MSP
  |
跳转应用
```

#### 设计要点

- Flash 写入完成不代表 CPU 已经不再执行旧指令。
- 如果应用程序从外部 Flash XIP 执行，还需要：
    - 重新配置外部存储控制器。
    - 重新配置 MPU。
    - 重新配置该区域的 Cache 属性。
    - 必要时失效 I-Cache 和 D-Cache。
- 更新状态应采用 A/B 镜像或双 Bank 机制。
- 不能只依赖 CRC，应考虑镜像签名和回滚保护。

---

## 12. 高频问题深度答疑

### 问题一：为什么 `volatile` 不能解决 DMA 与 Cache 一致性？

`volatile` 只告诉编译器：

```
每次读写都必须生成实际的内存访问
```

但 CPU 执行的访问可能命中 D-Cache：

```
CPU -> D-Cache -> 主存
DMA ------------> 主存
```

DMA 不访问 CPU 的 D-Cache，因此 `volatile` 无法让 DMA 看到 Dirty Cache line。必须使用：

- Clean。
- Invalidate。
- Non-cacheable Memory。
- 硬件 Cache Coherent 机制。

### 问题二：DMA RX 前为什么有时需要 Invalidate？

如果 CPU 在 DMA 开始前已经读取过 RX Buffer，旧数据可能已经进入 D-Cache。DMA 写入主存后，如果 Cache line 仍然有效，CPU 完成后继续读取旧 Cache line。

DMA RX 前 Invalidate 的目的是：

```
确保 DMA 写入后，CPU 不再使用旧 Cache line
```

但是，如果 Cache line 是 Dirty 的，直接 Invalidate 会丢失 CPU 数据。因此 RX Buffer 必须保持 DMA 独占，或者先 CleanInvalidate。

### 问题三：Non-cacheable 是否一定比 Cacheable 更好？

不是。

Non-cacheable 的优点：

- 一致性简单。
- 适合 DMA。
- 延迟更可预测。

缺点：

- CPU 每次访问都经过总线。
- 高频处理大数据时性能下降。
- 外部 SDRAM 访问可能非常慢。
- 增加总线压力。

一般策略：

```
小型、高频、DMA 共享 Buffer -> Non-cacheable
大型、CPU 密集处理 Buffer -> Cacheable + 维护
硬实时数据 -> TCM 或 Non-cacheable
```

### 问题四：Clean 后是否必须 Invalidate？

不一定。

DMA TX 方向：

```
CPU 写 -> Clean -> DMA 读
```

DMA 不会修改内存内容，因此通常不需要 Invalidate。

DMA RX 方向：

```
DMA 写 -> Invalidate -> CPU 读
```

通常不需要先 Clean，前提是 CPU 没有修改目标 Cache line。

双向 Buffer 或所有权不清晰时，应使用：

```
CleanInvalidate
```

但更好的办法是重构 Buffer 所有权，避免不明确的共享访问。

### 问题五：I-Cache 与 D-Cache 为什么要分开管理？

指令和数据的访问特征不同：

- 指令通常只读。
- 数据通常可读写。
- 指令 Cache 不需要 Dirty 状态。
- 数据 Cache 需要处理 Write-back。
- 自修改代码、Flash 更新和 XIP 切换涉及 I/D Cache 的不同维护顺序。

当 CPU 或 DMA 修改了“将来要执行的代码”时，通常需要：

```
D-Cache Clean
DMB/DSB
I-Cache Invalidate
DSB/ISB
```

### 问题六：Cache 维护会不会破坏实时性？

会，尤其是：

- 维护范围很大。
- 在高优先级中断中执行。
- 多个任务频繁维护相同 Buffer。
- 外部 SDRAM 回写耗时高。
- Clean 导致大量总线突发写操作。

优化方法：

- 将 DMA Buffer 迁移到 Non-cacheable SRAM。
- 使用双 Buffer，减少 CPU/DMA 争用。
- 仅维护实际使用的区域。
- 将维护操作放在低优先级任务上下文。
- 通过 TCM 保存实时控制变量。
- 采用批量 DMA，减少维护次数。
- 使用 DWT 测量真实维护耗时。

---

## 13. 课程核心总结

### 核心要点

1. **I-Cache 解决取指性能，D-Cache 解决数据访问性能。**
2. **DMA 不会自动访问 CPU 的 D-Cache。**
3. **DMA TX 前通常 Clean，DMA RX 后通常 Invalidate。**
4. **Cache 维护必须覆盖完整 Cache line。**
5. **DMA Buffer 必须考虑地址对齐、长度对齐和相邻变量污染。**
6. **`volatile` 不能代替 Cache 一致性处理。**
7. **TCM 适合低延迟和硬实时，但 DMA 可能无法访问。**
8. **修改代码或 Flash 内容后，需要处理 D-Cache、I-Cache 和指令屏障。**
9. **Buffer 所有权比单纯调用 Cache API 更重要。**
10. **Non-cacheable、Cacheable 和 TCM 应根据访问者、实时性和吞吐量综合选择。**

### 性能排序

通常可按以下顺序理解：

```
DTCM/ITCM
    > Cache Hit
    > 内部 SRAM
    > Flash Cache Miss
    > 外部 RAM Cache Hit
    > 外部 RAM Cache Miss
```

实际排序受具体芯片总线、存储器控制器、等待状态和 DMA 仲裁影响。

### 通用选型结论

```
硬实时控制代码       -> ITCM
硬实时控制数据       -> DTCM
CPU 高频计算数据     -> Cacheable SRAM
DMA 高频共享数据     -> Non-cacheable SRAM
DMA 低频/大块数据    -> Cacheable + Clean/Invalidate
外设寄存器           -> Device Memory
XIP 程序             -> I-Cache + 正确 MPU 属性
代码动态更新         -> D-Cache Clean + I-Cache Invalidate
```

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|配置建议|维护操作|
|---|---|---|
|CPU 写，DMA 读|Cacheable|DMA 前 Clean|
|DMA 写，CPU 读|Cacheable|DMA 完成后 Invalidate|
|CPU/DMA 双向|Cacheable|交接时 Clean/Invalidate|
|高频 DMA Buffer|Non-cacheable|通常无需维护|
|控制 ISR 代码|ITCM|无|
|控制 ISR 数据|DTCM|无，但确认 DMA 可达性|
|Flash 代码执行|I-Cache|代码更新后 Invalidate|
|外设寄存器|Device|禁止 Cache|
|图像 Framebuffer|Cacheable 或 Non-cacheable|根据更新区域 Clean|

### 14.2 特性对比表

|操作|是否写回内存|是否丢弃 Cache|主要用途|
|---|---|---|---|
|Clean|是|否|提交 CPU 写入|
|Invalidate|否|是|丢弃旧 Cache|
|CleanInvalidate|是|是|状态不确定时完整同步|
|DMB|不保证完成|否|访问排序|
|DSB|等待完成|否|同步外部访问|
|ISB|重新取指|否|同步指令流|

### 14.3 最小代码模板

```
/* CPU -> DMA */
dcache_clean_range(buffer, length);
__DSB();
dma_start_tx(buffer, length);

/* DMA -> CPU */
dma_start_rx(buffer, length);

/* DMA complete */
__DSB();
dcache_invalidate_range(buffer, length);
process_buffer(buffer, length);

/* Code update */
dcache_clean_range(code_address, code_length);
__DSB();
SCB_InvalidateICache();
__DSB();
__ISB();
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

- [ ]  能够解释 `Tag / Index / Offset / Valid / Dirty` 的作用。
- [ ]  能够判断某个 DMA Buffer 是否需要 Clean。
- [ ]  能够判断某个 DMA Buffer 是否需要 Invalidate。
- [ ]  能够解释为什么 DMA RX 完成后 CPU 可能读到旧数据。
- [ ]  能够编写 Cache line 对齐的维护函数。
- [ ]  能够发现未对齐 Buffer 造成的相邻变量污染。
- [ ]  能够区分 TCM、Cacheable SRAM 和 Non-cacheable SRAM。
- [ ]  能够设计 CPU/DMA Buffer 所有权状态机。
- [ ]  能够解释 `DMB`、`DSB`、`ISB` 的差异。
- [ ]  能够设计 Bootloader 跳转前的 Cache 和 MPU 处理流程。
- [ ]  能够使用 DWT 测量 Cache 命中与维护操作耗时。
- [ ]  能够从芯片总线结构判断 DMA 是否可以访问 DTCM。
- [ ]  能够定位“开启 D-Cache 后才出现”的协议和图像异常。
- [ ]  能够说明何时应选择 Non-cacheable 而不是 Cacheable。
- [ ]  能够制定项目级 DMA Buffer 和 Cache 管理规范。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：测量 I-Cache 性能

实现两个函数：

```
uint32_t test_flash_loop(void);
uint32_t test_itcm_loop(void);
```

分别将相同代码放入 Flash 和 ITCM，使用 DWT 测量：

```
循环次数
总周期数
平均每次循环周期数
I-Cache 开启/关闭时的差异
```

#### 任务二：复现 DMA RX 一致性问题

步骤：

1. CPU 先读取 RX Buffer。
2. DMA 写入新数据。
3. DMA 完成后不执行 Invalidate。
4. 观察 CPU 是否读到旧值。
5. 增加 Invalidate。
6. 重复测试并记录结果。

#### 任务三：测试 Buffer 对齐影响

测试以下 Buffer：

```
uint8_t buffer_a[128];
uint8_t buffer_b[128] __attribute__((aligned(32)));
```

比较：

- 起始地址。
- Cache maintenance 覆盖范围。
- Clean/Invalidate 周期数。
- 相邻变量是否被影响。

#### 任务四：构建双 Buffer 网络接收框架

要求：

- 两个 RX Buffer。
- DMA 和协议栈并行运行。
- 明确 Buffer 状态。
- 不允许 CPU 处理 DMA 正在写入的 Buffer。
- 统计丢包率和最大处理延迟。

#### 任务五：构建 Cache 策略测试矩阵

至少测试：

```
Cacheable + Clean/Invalidate
Non-cacheable
DTCM
外部 SDRAM + Cache
```

测量指标：

- CPU 周期数。
- DMA 吞吐量。
- 中断延迟。
- 最大执行抖动。
- 总线利用率。
- 功耗变化。

### 16.2 性能测试方法

使用 DWT Cycle Counter：

```
static void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t measure_cycles(void (*fn)(void))
{
    uint32_t begin;
    uint32_t end;

    begin = DWT->CYCCNT;
    fn();
    end = DWT->CYCCNT;

    return end - begin;
}
```

测试时应控制：

- 编译优化等级。
- 中断是否关闭。
- DMA 是否并发运行。
- Cache 初始状态。
- Buffer 地址和长度。
- Flash wait state。
- 外部存储器时钟和时序。
- 测试数据是否跨越 Cache line。

对于实时系统，不要只记录平均值，还要记录：

```
最小值
最大值
平均值
P99
P99.9
抖动范围
```

### 16.3 进阶学习方向

1. Cortex-M7 总线矩阵、AXI/AHB 访问路径与 Cache refill。
2. MPU Memory Type、Shareable 属性和内存排序。
3. ARMv8-M 中的安全域与 Cache 一致性。
4. Cortex-M55 Helium 向量指令与 Cache 访问模式。
5. Ethernet、USB、SDMMC、GPU、LCD DMA 的一致性设计。
6. 多核 MCU 的共享内存与软件 Cache Coherency。
7. ETM trace、性能计数器和 Cache miss 分析。
8. Zephyr、FreeRTOS、ThreadX 中的 DMA Buffer 抽象。
9. 外部 Octo-SPI、HyperRAM、SDRAM 的 Cache/MPU 联合优化。
10. OTA 场景下的代码完整性、I-Cache 管理和安全启动。