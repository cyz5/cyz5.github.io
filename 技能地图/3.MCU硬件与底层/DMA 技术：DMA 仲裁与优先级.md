
> DMA 仲裁与优先级决定了多个 DMA 通道、CPU、显示控制器、以太网、USB、SDMMC、外部存储器控制器同时访问系统总线时，谁先获得访问权、一次获得多少访问时间，以及低优先级数据流是否会被饿死。  
> 本课以常见 MCU 的 DMA Channel Priority、DMA Controller Arbitration、FIFO / Burst、AXI Bus Matrix 和 QoS 机制为参考，适用于普通 DMA、BDMA、MDMA、GPDMA 以及具备独立总线主设备能力的外设 DMA。

---

## 1. 学习目标

### 理解

- 理解 DMA 仲裁、通道优先级、总线优先级和外设请求优先级之间的区别。
- 理解 DMA 控制器内部仲裁与系统级 Bus Matrix 仲裁的不同。
- 理解以下机制的底层作用：
    - 固定优先级；
    - 轮询仲裁；
    - 加权轮询；
    - 抢占；
    - Burst；
    - FIFO；
    - QoS；
    - 带宽限制；
    - 饥饿防止。
- 理解 DMA 优先级并不等于端到端实时优先级。
- 理解高优先级 DMA 可能对 CPU、Cache、LCD、Ethernet 和其他 DMA 造成的影响。

### 掌握

- 掌握 DMA 通道优先级配置方法。
- 掌握多个外设共享 DMA 控制器时的资源分配方法。
- 掌握实时流、吞吐流、后台流的分级设计。
- 掌握 FIFO、Burst Length、传输宽度与总线占用时间之间的关系。
- 掌握 DMA 优先级与 RTOS 任务优先级的协同方法。
- 掌握 DMA 优先级验证和最坏情况延迟测试方法。

### 精通

- 能分析 DMA 仲裁造成的：
    - FIFO 溢出；
    - 外设欠载；
    - UART 丢字节；
    - 网络接收丢包；
    - 音频 underrun；
    - 控制任务抖动；
    - 低优先级传输饥饿。
- 能区分平均吞吐量问题与最坏延迟问题。
- 能建立 DMA 带宽预算和总线利用率模型。
- 能设计支持优先级、配额和公平性的 DMA 调度策略。
- 能定位 DMA 控制器内部优先级与系统总线仲裁冲突。

### 能够设计

- 能为电机控制、音频、Ethernet、LCD、SDMMC 等数据流建立 DMA 优先级矩阵。
- 能设计多 DMA 通道共享总线时的带宽隔离方案。
- 能设计低优先级后台搬运不影响高优先级实时数据的架构。
- 能设计 DMA 超时、饥饿检测、错误恢复和运行时统计机制。
- 能完成 DMA 仲裁策略的性能验证、压力测试和最坏情况评估。

---

## 2. 前置要求

### 知识要求

- DMA 基本结构和传输模式。
- AHB、AXI、APB、Bus Matrix 和 SRAM Bank。
- CPU、DMA、LTDC、Ethernet、USB、SDMMC 等总线主设备。
- 中断优先级、RTOS 任务优先级和优先级反转。
- FIFO、Burst、Cache、MPU 和内存屏障。
- 实时系统中的：
    - 周期；
    - 截止时间；
    - 最坏执行时间；
    - 抖动；
    - 背压；
    - 缓冲区容量。

### 技能要求

- 能阅读芯片参考手册中的 DMA 仲裁和总线章节。
- 能查看 DMA 通道优先级寄存器。
- 能使用 DWT、定时器或 trace 工具测量延迟。
- 能通过逻辑分析仪检测外设 FIFO 是否及时服务。
- 能使用 map 文件和链接脚本进行内存区域分配。
- 能统计 DMA 传输时间、等待时间、错误次数和带宽占用。

---

## 3. 技术概述

## 3.1 DMA 仲裁的定义

DMA 仲裁是指当多个 DMA 请求或多个总线主设备同时请求访问共享资源时，硬件决定：

1. 哪个请求先执行；
2. 哪个请求可以连续执行多个 Beat；
3. 哪个请求何时被挂起；
4. 低优先级请求如何获得服务；
5. 是否允许高优先级请求抢占当前传输；
6. 如何防止某个请求永久占用总线。

典型资源竞争如下：

```
UART DMA RX ----+
SPI DMA RX -----+
ADC DMA --------+--> DMA Controller --> Bus Matrix --> SRAM
Ethernet DMA ---+
MDMA -----------+
CPU ------------+
LCD Controller -+
```

DMA 仲裁至少存在两个层级。

---

## 3.2 DMA 控制器内部仲裁

多个 DMA Channel 共享同一个 DMA 控制器时，需要在控制器内部仲裁：

```
DMA Channel 0 ──┐
DMA Channel 1 ──┤
DMA Channel 2 ──┼──> DMA Controller Arbiter
DMA Channel 3 ──┤
DMA Channel 4 ──┘
```

常见仲裁策略：

- 固定优先级；
- 轮询；
- 优先级加轮询；
- 分组优先级；
- 通道号优先级；
- 外设请求级优先级。

---

## 3.3 系统总线级仲裁

即使 DMA 控制器已经决定 Channel 0 优先，DMA 仍需要与其他总线主设备竞争：

```
CPU
DMA1
DMA2
MDMA
Ethernet MAC
USB
LTDC
JPEG
SDMMC
  |
  v
AXI / AHB Bus Matrix
  |
  v
SRAM / SDRAM / Flash
```

因此：

```
DMA Channel Priority
不等于
System Bus Priority
```

如果某芯片只提供 DMA 通道优先级，而没有可配置的 Bus Matrix QoS，那么通道优先级无法完全决定最终总线访问顺序。

---

## 3.4 DMA 优先级的典型等级

常见抽象：

```
typedef enum {
    DMA_PRIORITY_LOW = 0,
    DMA_PRIORITY_MEDIUM = 1,
    DMA_PRIORITY_HIGH = 2,
    DMA_PRIORITY_VERY_HIGH = 3,
} dma_priority_t;
```

但必须注意：

- 某些芯片的数值越小优先级越高。
- 某些芯片的数值越大优先级越高。
- 某些 DMA 控制器只支持低、中、高三档。
- 某些控制器还叠加通道编号作为次级优先级。
- 优先级只在同一 DMA 控制器内部生效。
- 不同 DMA 控制器之间通常还要经过系统总线仲裁。

---

## 3.5 DMA 优先级与实时性的关系

实时性关心的是：

WorstCaseLatency≤DeadlineWorstCaseLatency≤Deadline

而不是平均传输速度。

例如：

```
ADC FIFO 可容忍延迟：2 μs
LCD 刷新 DMA 平均带宽很高
```

即使 LCD DMA 平均吞吐量优秀，只要它导致 ADC 访问延迟超过 2 μs，系统仍会发生采样丢失。

因此 DMA 优先级设计必须同时考虑：

- 请求周期；
- FIFO 深度；
- 单次可容忍延迟；
- 数据块大小；
- Burst 长度；
- 处理周期；
- 最坏总线竞争。

---

## 4. 核心特性横向对比

## 4.1 DMA 仲裁策略对比

|仲裁策略|机制|优点|缺点|适用场景|
|---|---|---|---|---|
|固定优先级|高优先级始终优先|延迟可预测|低优先级可能饥饿|严格实时流|
|纯轮询|请求依次轮转|公平|高优先级延迟不稳定|负载相近的通道|
|优先级 + 轮询|高优先级优先，同级轮询|兼顾实时性和公平性|实现复杂|工业混合负载|
|加权轮询|按权重分配服务次数|可配置带宽比例|参数调优复杂|多流带宽隔离|
|FIFO 优先|优先服务 FIFO 接近满的通道|可避免溢出|优先级动态变化|具有 FIFO 的外设|
|截止时间优先|距离 Deadline 最近者优先|实时性强|硬件通常不支持|软件调度层|

## 4.2 固定优先级与轮询对比

|维度|固定优先级|轮询|
|---|---|---|
|高优先级最坏延迟|低|中|
|低优先级公平性|差|好|
|配置简单度|高|高|
|饥饿风险|高|低|
|吞吐量|相近|相近|
|适合控制数据|好|一般|
|适合后台数据|差|好|
|实时性分析|简单但需考虑饥饿|需分析轮转周期|

## 4.3 DMA 数据流分类

|数据流类型|特征|推荐优先级|典型应用|
|---|---|---|---|
|硬实时流|有严格服务截止时间|Very High|电机 ADC、音频|
|高可靠实时流|不能轻易丢失|High|Ethernet RX、UART 控制|
|周期业务流|有周期要求但有一定缓冲|Medium|SPI 传感器|
|吞吐型流|追求带宽，不强调单次延迟|Medium|SDMMC|
|后台流|可延迟、可暂停|Low|日志、资源加载|
|调试流|可丢失或重试|Low|Trace、诊断|

## 4.4 Burst 长度对比

|Burst 长度|总线效率|单次占用时间|高优先级插入延迟|适用场景|
|---|---|---|---|---|
|Single|低|很短|低|强实时、小数据|
|4 Beat|中|短|低～中|混合负载|
|8 Beat|高|中|中|普通数据流|
|16 Beat|很高|长|高|大块吞吐|
|32 Beat 以上|最高|很长|很高|独占或后台搬运|

**Burst 越长，不代表系统实时性越好。**

---

## 5. 底层原理与功能特性深度解析

## 5.1 DMA 仲裁的基本时序

假设 DMA Channel 0、1、2 同时产生请求：

```
T0: Channel 0 Request
T1: Channel 1 Request
T2: Channel 2 Request
T3: 仲裁器读取优先级
T4: 选中 Channel 0
T5: Channel 0 传输一个或多个 Beat
T6: 再次仲裁
T7: 选中 Channel 1
T8: Channel 1 传输
```

如果采用固定优先级：

```
Priority 0 > Priority 1 > Priority 2
```

则可能出现：

```
Channel 0 持续产生请求
Channel 1 只能间歇获得服务
Channel 2 长时间无法获得服务
```

如果 Channel 0 的请求永不停止，Channel 2 可能产生饥饿。

---

## 5.2 单次传输与仲裁粒度

仲裁器不一定在每个字节后重新选择通道。

可能的仲裁粒度包括：

- 每个 Beat；
- 每个 Burst；
- 每个 FIFO 阈值；
- 每个块；
- 每次外设请求；
- 当前事务完成后。

例如：

```
Burst Length = 8 Beat
```

即使高优先级请求在当前 Burst 的第 2 个 Beat 到达，也可能要等剩余 6 个 Beat 完成后才能获得服务。

因此高优先级请求的等待延迟至少受到以下因素影响：

Twait≥Tcurrent_burst_remaining+Tbus_arbitrationTwait​≥Tcurrent_burst_remaining​+Tbus_arbitration​

---

## 5.3 优先级的三个层级

工程上应区分以下三种优先级。

### 层级一：外设请求优先级

外设可能有：

- FIFO 水位；
- 请求阈值；
- 请求紧急程度；
- 请求保持机制。

例如：

```
SPI RX FIFO 达到 4 字节
ADC FIFO 达到 8 个采样
```

### 层级二：DMA 通道优先级

DMA 控制器决定：

```
Channel 0 vs Channel 1 vs Channel 2
```

### 层级三：系统总线主设备优先级

Bus Matrix 决定：

```
CPU vs DMA vs MDMA vs LCD vs Ethernet
```

最终延迟为：

Te2e=Tperipheral_request+Tdma_queue+Tdma_arbitration+Tbus_arbitration+Tmemory_accessTe2e​=Tperipheral_request​+Tdma_queue​+Tdma_arbitration​+Tbus_arbitration​+Tmemory_access​

只调高 DMA 通道优先级，不一定能解决总线层面的延迟。

---

## 5.4 固定优先级仲裁

固定优先级的典型策略：

```
高优先级请求 > 中优先级请求 > 低优先级请求
```

伪代码：

```
static int select_fixed_priority_channel(
    const dma_channel_state_t *channels,
    size_t count)
{
    int selected = -1;
    uint8_t best_priority = 0U;

    for (size_t i = 0U; i < count; ++i) {
        if (!channels[i].request_pending) {
            continue;
        }

        if (selected < 0 ||
            channels[i].priority > best_priority) {
            selected = (int)i;
            best_priority = channels[i].priority;
        }
    }

    return selected;
}
```

### 优点

- 高优先级延迟容易分析。
- 对硬实时数据流有利。
- 配置和实现简单。
- 适合有明确截止时间的通道。

### 缺点

- 低优先级可能无限等待。
- 高优先级流持续满载时，后台传输可能完全停止。
- 容易出现“高优先级配置过多”导致优先级失去意义。

---

## 5.5 轮询仲裁

轮询策略记录上次服务位置：

```
static size_t round_robin_select(
    const dma_channel_state_t *channels,
    size_t count,
    size_t last_index)
{
    for (size_t offset = 1U; offset <= count; ++offset) {
        size_t index =
            (last_index + offset) % count;

        if (channels[index].request_pending) {
            return index;
        }
    }

    return count;
}
```

### 优点

- 通道之间具有公平性。
- 不容易产生永久饥饿。
- 适合负载和实时性相近的数据流。

### 缺点

- 高优先级请求可能等待其他通道。
- 最坏延迟取决于同时竞争的通道数量。
- 如果某通道 Burst 很长，轮询并不一定真正公平。

---

## 5.6 优先级 + 同级轮询

工业系统常用组合：

```
第一层：优先级分组
第二层：同级通道轮询
```

例如：

```
Very High：
    ADC1
    Audio RX

High：
    Ethernet RX
    UART Control

Medium：
    SPI Sensor
    USB

Low：
    Logger
    Resource Loader
```

仲裁过程：

```
1. 先选择最高非空优先级组。
2. 在组内使用 Round-Robin。
3. 每次服务一个 Beat 或一个有限 Burst。
4. 记录服务指针。
5. 对长期未服务通道进行饥饿监测。
```

这种方式兼顾：

- 高优先级实时性；
- 同级通道公平性；
- 低优先级通道的最低服务机会。

---

## 5.7 DMA 优先级配置示例

以下为抽象接口：

```
typedef struct {
    uint8_t channel;
    uint32_t request;
    dma_priority_t priority;
    uint8_t burst_length;
    uint8_t fifo_threshold;
    const char *name;
} dma_channel_config_t;

static const dma_channel_config_t g_dma_config[] = {
    {
        .channel = 0U,
        .request = DMA_REQ_ADC1,
        .priority = DMA_PRIORITY_VERY_HIGH,
        .burst_length = 1U,
        .fifo_threshold = 1U,
        .name = "adc_control",
    },
    {
        .channel = 1U,
        .request = DMA_REQ_ETH_RX,
        .priority = DMA_PRIORITY_HIGH,
        .burst_length = 4U,
        .fifo_threshold = 4U,
        .name = "ethernet_rx",
    },
    {
        .channel = 2U,
        .request = DMA_REQ_SPI1_RX,
        .priority = DMA_PRIORITY_MEDIUM,
        .burst_length = 4U,
        .fifo_threshold = 2U,
        .name = "spi_sensor",
    },
    {
        .channel = 3U,
        .request = DMA_REQ_UART_LOG_TX,
        .priority = DMA_PRIORITY_LOW,
        .burst_length = 8U,
        .fifo_threshold = 4U,
        .name = "log_tx",
    },
};
```

初始化：

```
int dma_configure_channel(
    const dma_channel_config_t *cfg)
{
    if (cfg == NULL) {
        return -1;
    }

    if (cfg->channel >= DMA_CHANNEL_COUNT) {
        return -2;
    }

    if (!dma_request_supported(cfg->channel,
                                cfg->request)) {
        return -3;
    }

    dma_disable(cfg->channel);
    dma_clear_flags(cfg->channel);

    dma_set_request(cfg->channel,
                    cfg->request);

    dma_set_priority(cfg->channel,
                     cfg->priority);

    dma_set_burst_length(cfg->channel,
                         cfg->burst_length);

    dma_set_fifo_threshold(cfg->channel,
                           cfg->fifo_threshold);

    dma_enable_error_irq(cfg->channel);
    dma_enable_complete_irq(cfg->channel);

    return 0;
}
```

---

## 5.8 DMA 优先级与 Burst 的耦合

假设：

- 总线频率：200 MHz；
- 一次 Beat：4 Byte；
- Burst：16 Beat；
- 当前 DMA 正在执行完整 Burst。

当前 Burst 数据量：

Dburst=16×4=64ByteDburst​=16×4=64Byte

理想总线时间：

Tburst=16200MHz=80nsTburst​=200MHz16​=80ns

但实际还包括：

- SRAM 等待；
- 仲裁间隙；
- 地址阶段；
- 外部 SDRAM 延迟；
- 总线转换；
- FIFO 状态。

如果实际 Burst 时间为 250 ns，那么高优先级请求可能至少等待 250 ns。

对于 ADC FIFO 仅能容忍 100 ns 的场景，Burst=16 就可能导致溢出，即使 ADC DMA 被设置为最高优先级。

### 结论

高实时通道通常应组合：

```
高通道优先级
+
较短 Burst
+
较短服务粒度
+
独立 SRAM Bank
+
适当 FIFO 阈值
```

---

## 5.9 FIFO 阈值与仲裁

FIFO 使 DMA 可以先积累一部分数据，再以 Burst 方式访问总线。

### FIFO 阈值较低

```
FIFO 稍有数据就发起总线访问
```

优点：

- 延迟低；
- 减少外设 FIFO 溢出风险。

缺点：

- Burst 不完整；
- 总线效率较低；
- 仲裁次数增加。

### FIFO 阈值较高

```
FIFO 积累较多数据后再发起访问
```

优点：

- 总线效率高；
- Burst 更完整；
- 减少仲裁次数。

缺点：

- 等待时间长；
- 外设 FIFO 可能先溢出；
- 不适合极短截止时间的数据流。

因此：

```
实时性优先：低 FIFO 阈值
吞吐量优先：高 FIFO 阈值
```

---

## 5.10 高优先级 DMA 的饥饿问题

固定优先级下，低优先级通道可能长期得不到总线服务。

定义低优先级请求等待时间：

Tstarvation=Thigh_traffic+Tbus_contentionTstarvation​=Thigh_traffic​+Tbus_contention​

如果高优先级流持续占用 100% 可用带宽：

Tstarvation→∞Tstarvation​→∞

这就是 DMA 饥饿。

### 饥饿检测

```
typedef struct {
    uint64_t submit_time;
    uint64_t service_time;
    uint32_t max_wait_cycles;
    uint32_t starvation_count;
} dma_wait_stat_t;

static dma_wait_stat_t g_dma_stats[DMA_CHANNEL_COUNT];

void dma_record_service(uint32_t channel,
                        uint32_t wait_cycles)
{
    dma_wait_stat_t *stat =
        &g_dma_stats[channel];

    if (wait_cycles > stat->max_wait_cycles) {
        stat->max_wait_cycles = wait_cycles;
    }

    if (wait_cycles > DMA_STARVATION_THRESHOLD) {
        stat->starvation_count++;
    }
}
```

### 防止饥饿的策略

1. 同级轮询。
2. 最大连续服务 Burst 限制。
3. 最低带宽保证。
4. 老化机制：
    - 等待时间越长，动态优先级越高。
5. 后台任务在系统空闲窗口运行。
6. 将高优先级流拆分成短块。
7. 将非实时流迁移到独立 DMA 控制器或独立 SRAM。

---

## 5.11 DMA 带宽预算

任何复杂系统都应提前计算 DMA 带宽。

### 单个数据流带宽

Bi=SampleRatei×BytesPerSampleiBi​=SampleRatei​×BytesPerSamplei​

例如：

```
ADC：2 MSPS × 2 Byte = 4 MB/s
SPI：20 MHz × 1 Byte/8 = 2.5 MB/s
Ethernet：约 12 MB/s
LCD：60 MB/s
```

系统总需求：

Btotal=∑iBiBtotal​=i∑​Bi​

考虑协议、地址、空闲和仲裁开销：

Brequired=BtotalEfficiencyBrequired​=EfficiencyBtotal​​

如果总数据带宽为 100 MB/s，预计总线效率为 75%：

Brequired=1000.75≈133.3MB/sBrequired​=0.75100​≈133.3MB/s

### 带宽余量

建议：

Bavailable≥1.3×BrequiredBavailable​≥1.3×Brequired​

对于硬实时系统，建议保留：

- 30%～50% 的平均带宽余量；
- 额外的最坏延迟分析；
- 外部内存和刷新峰值分析。

---

## 5.12 DMA 优先级与 RTOS 优先级

DMA 优先级和 RTOS 任务优先级不是同一个系统。

示例：

```
ADC DMA：硬件优先级 Very High
ADC ISR：NVIC 高优先级
ADC Process Task：RTOS 高优先级

Logger DMA：硬件优先级 Low
Logger ISR：NVIC 低优先级
Logger Task：RTOS 低优先级
```

合理关系：

```
硬件实时性越高
    -> DMA 通道优先级越高
    -> ISR 延迟要求越低
    -> 对应处理任务通常也应更高
```

但不应简单认为：

```
RTOS 任务优先级高 = DMA 一定优先
```

DMA 正在访问总线时，RTOS 任务无法直接抢占 DMA 当前总线事务。

---

## 5.13 DMA 中断优先级的独立问题

DMA 通道优先级决定：

```
谁获得数据搬运机会
```

NVIC 中断优先级决定：

```
谁的 ISR 先被 CPU 执行
```

两者不同。

错误配置：

```
ADC DMA：通道 Very High
ADC DMA IRQ：NVIC 低优先级

Logger DMA：通道 Low
Logger DMA IRQ：NVIC 高优先级
```

结果可能是：

- ADC 数据已经搬到内存；
- 但 ADC 完成 ISR 长时间不执行；
- Logger ISR 抢占 CPU；
- ADC 后处理延迟增加；
- 产生缓冲区覆盖。

因此应同时配置：

```
DMA Channel Priority
NVIC IRQ Priority
RTOS Task Priority
```

---

## 6. 性能量化分析

以下为示例平台：

- Cortex-M7，480 MHz；
- AXI 总线：240 MHz；
- SRAM 访问宽度：64 bit；
- 普通 DMA 与 MDMA 并行；
- UART：921600 baud；
- ADC：2 MSPS；
- Ethernet：100 Mbps；
- LCD RGB 数据流并行。

实际数值需通过目标平台测量。

## 6.1 UART FIFO 溢出约束

假设 UART 接收：

```
波特率：921600
数据格式：10 bit / Byte
```

字节速率：

R=92160010=92160Byte/sR=10921600​=92160Byte/s

字节间隔：

Tbyte≈10.85μsTbyte​≈10.85μs

如果 UART 没有 FIFO，DMA 需要在约 10.85 μs 内完成一次服务。

如果 UART FIFO 深度为 16 Byte，则理论容忍时间：

Tfifo=16×10.85≈173.6μsTfifo​=16×10.85≈173.6μs

但是工程上不能使用全部 FIFO 深度，应预留：

- 总线仲裁延迟；
- 中断关闭时间；
- Cache Miss；
- 外设时钟抖动；
- 任务调度延迟。

建议最坏服务延迟控制在：

Tservice,max<0.5×TfifoTservice,max​<0.5×Tfifo​

即约：

Tservice,max<86.8μsTservice,max​<86.8μs

## 6.2 ADC FIFO 约束

假设：

```
ADC 采样率：2 MSPS
每个采样：2 Byte
ADC FIFO：8 个样本
```

每个采样间隔：

Tsample=0.5μsTsample​=0.5μs

FIFO 可容忍时间：

Tfifo=8×0.5=4μsTfifo​=8×0.5=4μs

这意味着 ADC DMA 的最坏等待时间必须小于 4 μs，最好小于 2 μs。

如果某个 LCD DMA 使用 16 Beat Burst，且每个 Beat 需要 100 ns：

Tburst=16×100ns=1.6μsTburst​=16×100ns=1.6μs

在多层总线竞争下，ADC 仍可能接近危险边界。

优化方式：

- 将 ADC DMA 设置更高优先级。
- 缩短 LCD Burst。
- 将 ADC Buffer 放在独立 SRAM。
- 降低 LCD 刷新峰值。
- 使用专用 ADC FIFO。
- 调整触发和服务窗口。

## 6.3 多流带宽预算示例

假设系统存在以下数据流：

|数据流|数据速率|
|---|---|
|ADC|4 MB/s|
|UART RX|0.092 MB/s|
|SPI RX|5 MB/s|
|Ethernet RX|12.5 MB/s|
|LCD|60 MB/s|
|SDMMC|25 MB/s|

总理论数据量：

Bdata=4+0.092+5+12.5+60+25=106.592MB/sBdata​=4+0.092+5+12.5+60+25=106.592MB/s

假设总线实际效率为 70%：

Brequired=106.5920.7≈152.27MB/sBrequired​=0.7106.592​≈152.27MB/s

若总线可用带宽为 180 MB/s，平均余量：

Margin=180−152.27≈27.73MB/sMargin=180−152.27≈27.73MB/s

余量比例：

27.73180×100%≈15.4%18027.73​×100%≈15.4%

这对于包含外部 SDRAM、Cache Miss 和瞬时 Burst 的系统偏紧，应进行优化。

## 6.4 优先级对最坏延迟的影响

设：

- 当前低优先级 DMA Burst 剩余时间：1.2 μs；
- 总线重新仲裁：0.2 μs；
- 高优先级 DMA 访问内存：0.5 μs；
- 外部内存等待：0.8 μs。

高优先级请求的最坏响应：

Tresponse=1.2+0.2+0.5+0.8=2.7μsTresponse​=1.2+0.2+0.5+0.8=2.7μs

如果 ADC FIFO 只能容忍 2 μs，则必须减少：

- 当前 Burst 长度；
- 外部内存访问；
- 共享总线竞争；
- 访问路径层级。

## 6.5 CPU 负载与 DMA 优先级

假设 UART 每字节 ISR 耗时 1.5 μs：

CPUuart=92160×1.5μs=138.24ms/s≈13.8%CPUuart​=92160×1.5μs=138.24ms/s≈13.8%

采用 64 Byte DMA 块：

ISRrate=9216064=1440/sISRrate​=6492160​=1440/s

每次 DMA ISR 加任务通知耗时 4 μs：

CPUdma=1440×4μs=5.76ms/s≈0.58%CPUdma​=1440×4μs=5.76ms/s≈0.58%

提高 DMA 优先级主要改善：

- 丢包风险；
- 外设 FIFO 服务延迟；
- DMA 完成时刻稳定性。

但它并不会直接减少 DMA ISR 执行时间。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否有多个 DMA / 总线主设备同时访问同一资源？
|
+-- 否 --> 使用默认优先级，重点验证传输正确性
|
+-- 是 --> 数据流是否有严格截止时间？
           |
           +-- 是 --> 是否存在 FIFO 溢出或 underrun 风险？
           |          |
           |          +-- 是 --> 设为高优先级
           |          |          缩短 Burst
           |          |          分配独立内存
           |          |
           |          +-- 否 --> 高优先级或中优先级均可
           |
           +-- 否 --> 是否追求高吞吐量？
                      |
                      +-- 是 --> 中优先级 + 较长 Burst
                      |
                      +-- 否 --> 低优先级 + 可抢占 / 可暂停
```

## 7.2 按数据流选型

|场景|推荐优先级|Burst 建议|内存建议|
|---|---|---|---|
|电机控制 ADC|Very High|Single / Short|独立 SRAM|
|音频采集|Very High|Short / Medium|双缓冲 SRAM|
|Ethernet RX|High|Medium|专用 RX Descriptor / SRAM|
|UART 控制通道|High|Short|内部 SRAM|
|SPI 传感器|Medium|Short / Medium|内部 SRAM|
|SDMMC 文件读写|Medium|Medium / Long|外部或专用 SRAM|
|LCD 刷新|Medium|根据实时性调整|Framebuffer 独立区域|
|日志输出|Low|Medium / Long|后台 Buffer|
|Flash 资源加载|Low|Long，但限时|后台执行|
|调试 Trace|Low|Short|可丢弃 Buffer|

## 7.3 典型场景说明

### 电机控制

需求：

- 采样与 PWM 同步；
- FIFO 深度小；
- 丢一个采样可能影响控制稳定性。

方案：

```
ADC DMA：Very High
Burst：Single 或极短 Burst
Buffer：独立 SRAM Bank
NVIC：高优先级
控制任务：高优先级
```

理由：

- 首要目标是确定性和最坏延迟；
- 不追求大 Burst 的峰值带宽。

### LCD + Ethernet 并发

需求：

- LCD 追求持续吞吐；
- Ethernet RX 不能丢包；
- 两者都可能访问外部 SDRAM。

方案：

```
Ethernet RX：High
LCD：Medium
SDMMC：Medium / Low
日志：Low
```

理由：

- Ethernet RX 具有 FIFO 溢出风险；
- LCD 可通过帧缓冲和刷新调度吸收延迟；
- LCD Burst 不宜长期独占总线。

### 日志后台传输

需求：

- 允许延迟；
- 允许暂停；
- 不得影响控制和通信。

方案：

```
日志 DMA：Low
限制最大 Burst
设置提交队列长度
在系统空闲窗口启动
必要时主动暂停
```

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：按截止时间分配优先级，而不是按模块名称分配

错误方式：

```
“网络模块很重要，所以网络 DMA 最高”
```

正确方式：

```
哪个数据流最先达到不可恢复错误条件？
哪个数据流的 FIFO 最浅？
哪个数据流的 Deadline 最短？
哪个数据流丢失代价最高？
```

优先级依据应为：

Priority∝Criticality×DeadlineUrgency×OverflowRiskPriority∝Criticality×DeadlineUrgency×OverflowRisk

### 原则二：优先级必须和 FIFO、Burst 一起设计

不能只配置：

```
dma_set_priority(channel,
                 DMA_PRIORITY_VERY_HIGH);
```

还需要评估：

```
dma_set_burst_length(channel, ...);
dma_set_fifo_threshold(channel, ...);
dma_set_memory_region(channel, ...);
```

### 原则三：高优先级不应过多

如果所有通道都设置为 Very High：

```
优先级失去区分度
```

推荐保留层级：

```
Very High：不超过总实时流的 10%～20%
High：关键通信和可靠性流
Medium：普通业务流
Low：后台可延迟流
```

### 原则四：避免高优先级大块 DMA 长时间独占总线

高优先级不代表 Burst 可以无限长。

推荐：

```
高优先级 + 短 Burst
低优先级 + 长 Burst
```

或者：

```
高优先级：
    短请求、强实时

低优先级：
    大块吞吐、可延迟
```

### 原则五：使用内存分区减少仲裁

例如：

```
D2 SRAM：
    ADC Buffer、UART Buffer

AXI SRAM：
    Ethernet Buffer

外部 SDRAM：
    Framebuffer、日志、资源

DTCM：
    CPU 实时算法数据
```

如果不同 DMA 访问不同 SRAM Bank，可以减少：

- 总线冲突；
- SRAM 端口冲突；
- Cache 影响；
- 最坏延迟。

### 原则六：低优先级传输必须有进度保证

必须能够回答：

```
低优先级 DMA 最长多久没有获得服务？
是否可能永久饥饿？
是否需要动态提升优先级？
是否可以被取消？
```

## 8.2 优先级决策矩阵

评分范围为 1～5。

|数据流|截止时间紧迫性|丢失代价|FIFO 溢出风险|推荐优先级|
|---|---|---|---|---|
|电机 ADC|5|5|5|Very High|
|音频 RX|5|4|5|Very High|
|Ethernet RX|4|4|4|High|
|UART 控制|4|5|3|High|
|SPI 传感器|3|3|3|Medium|
|LCD 刷新|2～4|2|2～4|Medium|
|SDMMC|2|3|2|Medium|
|日志|1|1|1|Low|

## 8.3 工业级编码规范

- DMA 优先级统一使用枚举，不直接写魔法数。
- 在系统配置表中记录：
    - 通道；
    - 请求源；
    - 优先级；
    - Burst；
    - FIFO；
    - 内存区域；
    - 业务所有者。
- 启动时打印 DMA 资源配置。
- 为每个通道统计：
    - 请求次数；
    - 完成次数；
    - 错误次数；
    - 最大等待时间；
    - 平均服务时间；
    - 最大连续占用时间。
- 禁止所有通道默认设置为最高优先级。
- 高优先级通道使用短 Burst 并限制单次占用。
- 低优先级通道设计老化或最低服务策略。
- 不仅测试空载性能，还要测试全负载并发。
- 重点测试：
    - CPU Cache Miss；
    - LCD 刷新；
    - Ethernet 高流量；
    - SDMMC 连续读写；
    - 外部 SDRAM 访问；
    - 中断密集场景。
- DMA Channel Priority、NVIC Priority 和 RTOS Task Priority 必须分别记录和评审。
- 任何优先级调整都必须重新测试最坏延迟。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：所有 DMA 通道都设置为最高优先级

### 错误代码

```
for (uint32_t ch = 0U;
     ch < DMA_CHANNEL_COUNT;
     ++ch) {
    dma_set_priority(ch,
                     DMA_PRIORITY_VERY_HIGH);
}
```

### 根因

优先级没有区分，所有通道竞争时只能依赖默认通道号、FIFO 状态或系统总线仲裁。

### 正确实现

```
dma_set_priority(DMA_ADC_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

dma_set_priority(DMA_ETH_RX_CHANNEL,
                 DMA_PRIORITY_HIGH);

dma_set_priority(DMA_SPI_CHANNEL,
                 DMA_PRIORITY_MEDIUM);

dma_set_priority(DMA_LOG_CHANNEL,
                 DMA_PRIORITY_LOW);
```

### 风险影响

- 高实时通道得不到预期优势。
- 后台大块传输可能长时间占用总线。
- 系统在高负载下出现抖动。
- 优先级配置失去可维护性。

---

## 9.2 错误二：提高优先级但保持过长 Burst

### 错误代码

```
dma_set_priority(DMA_ADC_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

/* ADC FIFO 很浅，却使用超长 Burst */
dma_set_burst_length(DMA_ADC_CHANNEL,
                     DMA_BURST_16_BEAT);
```

### 根因

ADC 虽然拥有高优先级，但其他通道当前正在执行长 Burst，或者 ADC 自己一次占用总线过久。

### 正确实现

```
dma_set_priority(DMA_ADC_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

dma_set_burst_length(DMA_ADC_CHANNEL,
                     DMA_BURST_SINGLE);

dma_set_fifo_threshold(DMA_ADC_CHANNEL,
                       DMA_FIFO_LOW);
```

### 风险影响

- ADC FIFO 溢出。
- 采样序列丢失。
- 电机控制周期抖动。
- 提高优先级后问题仍然存在。

---

## 9.3 错误三：只配置 DMA 优先级，不考虑系统总线仲裁

### 错误代码

```
dma_set_priority(DMA_ETH_RX_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

/* LCD、MDMA、SDMMC 同时访问同一个 SDRAM */
start_lcd_refresh();
start_mdma_copy();
start_sdmmc_transfer();
```

### 根因

DMA 通道优先级只在 DMA 控制器内部生效，最终访问 SDRAM 时还需要经过系统 Bus Matrix。

### 正确实现

```
Ethernet RX：
    高优先级
    专用内部 SRAM / RX Descriptor

LCD：
    中优先级
    限制 Burst
    分区刷新

SDMMC：
    中低优先级
    空闲窗口执行

MDMA：
    低优先级
    可暂停、可分块
```

并建立总线带宽预算：

Btotal=Beth+Blcd+Bsdmmc+Bmdma+BcpuBtotal​=Beth​+Blcd​+Bsdmmc​+Bmdma​+Bcpu​

### 风险影响

- Ethernet DMA 仍然丢包。
- SDRAM 访问延迟不可预测。
- CPU 任务发生长尾延迟。
- 单独测试每个模块正常，并发时失败。

---

## 9.4 错误四：误将 NVIC 优先级当作 DMA 通道优先级

### 错误代码

```
NVIC_SetPriority(DMA_ADC_IRQn, 1);

/*
 * 未配置 DMA Channel Priority，
 * 或者 DMA Channel 仍为 Low。
 */
```

### 根因

NVIC 优先级只控制 CPU 执行哪个 ISR，不控制 DMA 硬件先搬运哪个数据流。

### 正确实现

```
dma_set_priority(DMA_ADC_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

NVIC_SetPriority(DMA_ADC_IRQn,
                 ADC_DMA_IRQ_PRIORITY);

NVIC_EnableIRQ(DMA_ADC_IRQn);
```

同时配置：

```
DMA Channel Priority
NVIC IRQ Priority
RTOS Task Priority
```

### 风险影响

- DMA 数据已经延迟甚至丢失，ISR 才开始执行。
- 高优先级 ISR 无法弥补低优先级 DMA 服务。
- 系统调试时出现“中断优先级很高但仍丢数据”。

---

## 9.5 错误五：低优先级 DMA 被长期饿死

### 错误代码

```
dma_set_priority(DMA_ADC_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

dma_set_priority(DMA_AUDIO_CHANNEL,
                 DMA_PRIORITY_VERY_HIGH);

dma_set_priority(DMA_LOG_CHANNEL,
                 DMA_PRIORITY_LOW);

/* ADC 和 Audio 长期满载运行 */
```

### 根因

固定优先级仲裁下，高优先级请求始终存在，低优先级通道没有获得服务的机会。

### 正确实现

```
if (dma_wait_cycles(DMA_LOG_CHANNEL) >
    DMA_LOG_MAX_WAIT_CYCLES) {
    dma_temporarily_boost_priority(
        DMA_LOG_CHANNEL,
        DMA_PRIORITY_MEDIUM);
}
```

或者：

```
高优先级通道使用有限 Burst
同级通道采用轮询
低优先级通道获得最低带宽保证
后台日志可在空闲窗口执行
```

### 风险影响

- 日志 Buffer 持续堆积。
- 后台传输最终溢出。
- 系统无法追溯早期故障。
- 低优先级任务出现永久饥饿。

---

## 9.6 错误六：只按平均带宽，不分析最坏延迟

### 错误代码

```
/*
 * 平均带宽只有总线能力的 40%，
 * 因此认为系统一定安全。
 */
configure_all_dma_channels();
```

### 根因

平均带宽不足以证明实时性。FIFO 溢出通常由瞬时拥塞和最坏等待时间造成。

### 正确实现

评估：

```
平均带宽
峰值带宽
最大 Burst
最坏总线等待
FIFO 深度
外设请求间隔
中断关闭时间
Cache Miss 延迟
```

核心约束：

Tworst_service<Tfifo_toleranceTworst_service​<Tfifo_tolerance​

### 风险影响

- 平均性能报告正常。
- 高负载或特定相位关系下突然溢出。
- 问题难以通过普通功能测试复现。

---

## 10. 多机制组合使用方案

## 10.1 DMA 优先级 + FIFO + Burst + 内存分区

### 推荐架构

```
硬实时流：
    高优先级
    短 Burst
    低 FIFO 阈值
    独立 SRAM

可靠性流：
    高优先级
    中 Burst
    专用 Descriptor

吞吐流：
    中优先级
    长 Burst
    外部 SDRAM

后台流：
    低优先级
    可暂停
    空闲窗口执行
```

### 配置框架

```
typedef struct {
    uint32_t channel;
    const char *name;
    dma_priority_t priority;
    uint32_t burst;
    uint32_t fifo_threshold;
    uint32_t memory_region;
    uint32_t max_wait_cycles;
    uint32_t max_burst_cycles;
} dma_policy_t;

static const dma_policy_t g_dma_policy[] = {
    {
        .channel = DMA_ADC_CHANNEL,
        .name = "adc_control",
        .priority = DMA_PRIORITY_VERY_HIGH,
        .burst = DMA_BURST_SINGLE,
        .fifo_threshold = DMA_FIFO_LOW,
        .memory_region = SRAM_D2,
        .max_wait_cycles = 1000U,
        .max_burst_cycles = 100U,
    },
    {
        .channel = DMA_ETH_RX_CHANNEL,
        .name = "ethernet_rx",
        .priority = DMA_PRIORITY_HIGH,
        .burst = DMA_BURST_4,
        .fifo_threshold = DMA_FIFO_MEDIUM,
        .memory_region = SRAM_D2,
        .max_wait_cycles = 3000U,
        .max_burst_cycles = 500U,
    },
    {
        .channel = DMA_LCD_CHANNEL,
        .name = "lcd_refresh",
        .priority = DMA_PRIORITY_MEDIUM,
        .burst = DMA_BURST_8,
        .fifo_threshold = DMA_FIFO_HIGH,
        .memory_region = SDRAM,
        .max_wait_cycles = 20000U,
        .max_burst_cycles = 3000U,
    },
    {
        .channel = DMA_LOG_CHANNEL,
        .name = "logger",
        .priority = DMA_PRIORITY_LOW,
        .burst = DMA_BURST_4,
        .fifo_threshold = DMA_FIFO_MEDIUM,
        .memory_region = AXI_SRAM,
        .max_wait_cycles = 100000U,
        .max_burst_cycles = 1000U,
    },
};
```

---

## 10.2 DMA + RTOS 任务 + 事件通知

推荐数据流：

```
DMA 完成
    |
    v
ISR 快速处理状态
    |
    v
Task Notification / Event
    |
    v
高优先级任务处理实时数据
    |
    v
低优先级任务处理后台数据
```

### ISR 示例

```
void DMA_ADC_IRQHandler(void)
{
    uint32_t flags =
        dma_get_flags(DMA_ADC_CHANNEL);

    if ((flags & DMA_FLAG_TRANSFER_ERROR) != 0U) {
        dma_clear_flags(DMA_ADC_CHANNEL,
                        DMA_FLAG_TRANSFER_ERROR);

        adc_dma_error_count++;
        adc_error_notify_from_isr();
        return;
    }

    if ((flags & DMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        dma_clear_flags(DMA_ADC_CHANNEL,
                        DMA_FLAG_TRANSFER_COMPLETE);

        adc_dma_complete_count++;
        adc_data_ready_notify_from_isr();
    }
}
```

### 任务优先级分配

```
ADC Control Task：最高业务优先级
Ethernet RX Task：高业务优先级
SPI Sensor Task：中业务优先级
Logger Task：低业务优先级
```

### 关键原则

- ISR 优先级不能违反 RTOS 对可调用 API 的限制。
- 任务优先级不能替代 DMA 通道优先级。
- 高优先级任务不能长期占用 CPU，导致低优先级 DMA 相关任务无法运行。
- 对后台流设置最大延迟和丢弃策略。

---

## 10.3 DMA + 双缓冲 + 优先级分层

适用于 ADC、音频和网络流。

```
DMA Buffer A：
    DMA 写入

DMA Buffer B：
    CPU / DSP 处理

完成后交换：
    DMA 写入 B
    CPU 处理 A
```

优先级设计：

```
采集 DMA：Very High
采集 ISR：高
处理任务：高

记录 DMA：Low
记录 ISR：低
记录任务：低
```

时序约束：

Tprocess,max<Tbuffer_fillTprocess,max​<Tbuffer_fill​

如果处理任务未及时完成：

```
1. 记录 overrun
2. 丢弃最旧或最新块
3. 保持采集 DMA 连续运行
4. 不允许低优先级处理阻塞硬实时采集
```

---

## 10.4 DMA + 总线带宽整形

如果芯片支持 QoS、优先级或带宽限制，可以设计：

```
ADC：
    保证低延迟，不限制最低带宽

Ethernet：
    保证最低服务带宽

LCD：
    限制峰值 Burst

日志：
    限制最大带宽和最长连续占用
```

抽象接口：

```
typedef struct {
    uint32_t master_id;
    uint32_t min_bandwidth;
    uint32_t max_bandwidth;
    uint32_t max_burst;
} bus_qos_policy_t;

int bus_qos_configure(
    const bus_qos_policy_t *policy)
{
    if (policy == NULL) {
        return -1;
    }

    if (policy->min_bandwidth >
        policy->max_bandwidth) {
        return -2;
    }

    bus_set_min_bandwidth(policy->master_id,
                          policy->min_bandwidth);

    bus_set_max_bandwidth(policy->master_id,
                          policy->max_bandwidth);

    bus_set_max_burst(policy->master_id,
                      policy->max_burst);

    return 0;
}
```

---

## 11. 工业级实际案例分析

## 11.1 案例一：FOC 电机控制中的 ADC DMA 仲裁

### 需求

- PWM 频率：20 kHz。
- ADC 采样与 PWM 中点同步。
- 每个控制周期采集：
    - 三相电流；
    - 母线电压；
    - 温度或辅助通道。
- 系统同时运行：
    - Ethernet；
    - LCD；
    - 日志；
    - 参数存储。
- 采样不能因总线竞争丢失。
- 控制任务必须在下一个 PWM 周期前完成。

### 数据量

假设每个采样周期有 6 个 `uint16_t` 数据：

Datasample=6×2=12ByteDatasample​=6×2=12Byte

PWM 频率为 20 kHz：

BADC=12×20000=240000Byte/s=0.24MB/sBADC​=12×20000=240000Byte/s=0.24MB/s

ADC 数据带宽并不高，但其**截止时间极短、FIFO 深度有限、丢样代价高**，因此应设置为 Very High 优先级。

### 推荐架构

```
PWM Timer
    |
    +--> ADC Trigger
    |       |
    |       v
    |     ADC
    |       |
    |       v
    |    ADC DMA
    |       |
    |       v
    |  D2 SRAM Buffer
    |       |
    |       v
    |  ADC DMA ISR
    |       |
    |       v
    |  FOC Control Task
```

同时存在：

```
Ethernet DMA --> Ethernet SRAM
LCD DMA       --> External SDRAM
Logger DMA    --> AXI SRAM
```

### DMA 优先级配置

```
static void motor_dma_config(void)
{
    dma_disable(DMA_ADC_CHANNEL);
    dma_clear_flags(DMA_ADC_CHANNEL);

    dma_set_request(DMA_ADC_CHANNEL,
                    DMA_REQ_ADC1);

    dma_set_priority(DMA_ADC_CHANNEL,
                     DMA_PRIORITY_VERY_HIGH);

    /*
     * ADC FIFO 较浅，使用短 Burst，
     * 避免其他主设备长时间占用总线。
     */
    dma_set_burst_length(DMA_ADC_CHANNEL,
                         DMA_BURST_SINGLE);

    dma_set_fifo_threshold(DMA_ADC_CHANNEL,
                           DMA_FIFO_LOW);

    dma_set_memory_region(DMA_ADC_CHANNEL,
                          DMA_MEMORY_D2_SRAM);

    dma_enable_irq(DMA_ADC_CHANNEL,
                   DMA_IRQ_TRANSFER_COMPLETE |
                   DMA_IRQ_TRANSFER_ERROR);
}
```

### Buffer 配置

```
#define ADC_SAMPLE_COUNT 6U

static uint16_t adc_sample_buffer[ADC_SAMPLE_COUNT]
    __attribute__((section(".dma_d2_sram"),
                   aligned(32)));
```

### DMA 完成 ISR

```
void DMA_ADC_IRQHandler(void)
{
    uint32_t flags =
        dma_get_flags(DMA_ADC_CHANNEL);

    if ((flags & DMA_FLAG_TRANSFER_ERROR) != 0U) {
        dma_clear_flags(DMA_ADC_CHANNEL,
                        DMA_FLAG_TRANSFER_ERROR);

        motor_adc_error_count++;
        motor_control_fault_notify_from_isr();
        return;
    }

    if ((flags & DMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        dma_clear_flags(DMA_ADC_CHANNEL,
                        DMA_FLAG_TRANSFER_COMPLETE);

        /*
         * 如果 Buffer 位于 Cacheable 区域，
         * CPU 读取前需要 Invalidate。
         */
        dma_cache_invalidate(adc_sample_buffer,
                             sizeof(adc_sample_buffer));
        cpu_dmb();

        motor_adc_sample_timestamp =
            timer_get_capture_value();

        motor_control_notify_from_isr();
    }
}
```

### 设计要点

1. ADC 采样 DMA 使用 **Very High + 短 Burst**。
2. ADC Buffer 放在内部 SRAM，避免与 LCD 共用外部 SDRAM。
3. 不允许 LCD 或 MDMA 使用同一 SRAM Bank 长时间 Burst。
4. ADC ISR 只记录状态和发送通知。
5. FOC 任务不能等待低优先级日志任务。
6. 对 ADC 采样超时、DMA 错误和采样序列错误立即进入安全策略。
7. 测量从 ADC 触发到控制任务开始运行的端到端延迟。

### 关键实时约束

PWM 周期：

TPWM=120000=50μsTPWM​=200001​=50μs

如果控制算法最晚必须在周期末完成，则应满足：

TADC_DMA+TISR+TTaskWakeup+TFOC<50μsTADC_DMA​+TISR​+TTaskWakeup​+TFOC​<50μs

工程上不应将 50 μs 全部用满，建议保留至少 20%～30% 裕量。

---

## 11.2 案例二：Ethernet RX 与 LCD 刷新的总线竞争

### 需求

- MCU 集成 Ethernet MAC。
- LCD 使用 LTDC 连续刷新。
- Framebuffer 位于外部 SDRAM。
- Ethernet RX 不能因 LCD 刷新丢包。
- LCD 可以容忍少量延迟，但不能出现严重撕裂。

### 典型冲突

```
Ethernet MAC DMA ----+
                     |
LTDC DMA ------------+--> AXI Bus Matrix --> SDRAM
                     |
MDMA Frame Copy -----+
```

LCD 产生持续读取：

```
LTDC -> SDRAM Framebuffer -> LCD
```

Ethernet RX 则需要及时写入：

```
Ethernet MAC -> RX Descriptor / RX Buffer
```

如果 Ethernet RX Buffer 和 Framebuffer 都位于同一个 SDRAM Bank，可能出现：

- Ethernet RX 描述符更新延迟；
- RX FIFO 溢出；
- 网络丢包；
- LCD 刷新抖动；
- SDRAM 仲裁等待增加。

### 推荐内存分区

```
D2 SRAM：
    Ethernet RX Descriptor
    Ethernet RX Buffer

AXI SRAM：
    Ethernet TX Buffer
    协议栈控制结构

外部 SDRAM：
    LCD Framebuffer
    UI 资源
```

### 推荐优先级

```
Ethernet RX DMA：High
Ethernet TX DMA：Medium
LTDC：Medium
MDMA 图像复制：Low / Medium
日志 DMA：Low
```

### Ethernet DMA 配置框架

```
static void ethernet_dma_config(void)
{
    dma_set_priority(DMA_ETH_RX_CHANNEL,
                     DMA_PRIORITY_HIGH);

    /*
     * RX 需要及时服务，但不应设置过长 Burst，
     * 避免长时间阻塞 ADC 等硬实时通道。
     */
    dma_set_burst_length(DMA_ETH_RX_CHANNEL,
                         DMA_BURST_4);

    dma_set_fifo_threshold(DMA_ETH_RX_CHANNEL,
                           DMA_FIFO_MEDIUM);

    dma_set_memory_region(DMA_ETH_RX_CHANNEL,
                          DMA_MEMORY_D2_SRAM);

    dma_enable_irq(DMA_ETH_RX_CHANNEL,
                   DMA_IRQ_TRANSFER_COMPLETE |
                   DMA_IRQ_TRANSFER_ERROR);
}
```

### Ethernet RX 任务策略

```
void ethernet_rx_task(void *arg)
{
    for (;;) {
        uint32_t packet_count;

        if (!ethernet_wait_rx_event(&packet_count,
                                    portMAX_DELAY)) {
            continue;
        }

        /*
         * RX 任务优先处理描述符回收和 Buffer 释放，
         * 避免 Ethernet DMA 因描述符不足停止。
         */
        ethernet_reclaim_rx_descriptors();

        for (uint32_t i = 0U;
             i < packet_count;
             ++i) {
            ethernet_process_one_packet();
        }

        ethernet_refill_rx_descriptors();
    }
}
```

### LCD 刷新优化

不要在整个 Framebuffer 上频繁进行 MDMA 大块复制：

```
/* 不推荐：每次 UI 更新都复制整个 Framebuffer */
mdma_memcpy(framebuffer,
            render_buffer,
            FRAMEBUFFER_SIZE);
```

推荐使用 Dirty Rectangle：

```
typedef struct {
    uint32_t x;
    uint32_t y;
    uint32_t width;
    uint32_t height;
} dirty_rect_t;

int lcd_update_rect(const dirty_rect_t *rect)
{
    if (rect == NULL ||
        rect->width == 0U ||
        rect->height == 0U) {
        return -1;
    }

    return mdma_copy_2d(
        render_buffer_address(rect),
        framebuffer_address(rect),
        rect->width * LCD_PIXEL_SIZE,
        rect->height,
        render_buffer_stride(),
        framebuffer_stride());
}
```

### 设计要点

1. Ethernet RX Descriptor 优先放内部 SRAM。
2. LCD Framebuffer 放外部 SDRAM，但 LCD Burst 要受控。
3. MDMA 图像复制使用 Dirty Rectangle。
4. UI 更新避免与 Ethernet 高峰同时启动大块搬运。
5. Ethernet RX Buffer 释放速度必须大于网络包到达速度。
6. 需要测试：
    - 网络满负载；
    - LCD 满屏刷新；
    - MDMA UI 更新；
    - CPU Cache Miss；
    - SDRAM 高负载。

---

## 11.3 案例三：音频采集、SDMMC 写盘和后台日志并发

### 需求

- 音频采样率：48 kHz。
- 双声道、24 bit 数据。
- 音频不能出现 underrun 或 overrun。
- SDMMC 将数据写入 SD 卡。
- 系统同时写入诊断日志。
- SD 卡存在不可预测的写入延迟。

### 音频数据带宽

每个采样帧：

2×3=6Byte2×3=6Byte

采样率为 48 kHz：

Baudio=6×48000=288000Byte/s≈0.288MB/sBaudio​=6×48000=288000Byte/s≈0.288MB/s

音频带宽不高，但实时性要求高，因为音频 Buffer 有固定的播放 / 采集窗口。

### 推荐架构

```
SAI / I2S
    |
    v
Audio DMA
    |
    v
Ping-Pong Audio Buffer
    |
    +--> Audio Task
    |
    +--> Ring Buffer
             |
             v
        SDMMC DMA
             |
             v
          SD Card
```

日志数据不应直接与音频 DMA 竞争同一高优先级路径：

```
Logger Buffer
      |
      v
Low Priority DMA
```

### DMA 优先级配置

```
Audio RX DMA：Very High
Audio TX DMA：Very High
SDMMC DMA：Medium
Logger DMA：Low
```

### 双缓冲状态机

```
typedef enum {
    AUDIO_BUF_FREE = 0,
    AUDIO_BUF_DMA_WRITING,
    AUDIO_BUF_READY,
    AUDIO_BUF_PROCESSING,
    AUDIO_BUF_ERROR,
} audio_buffer_state_t;

typedef struct {
    uint8_t *address;
    size_t size;
    volatile audio_buffer_state_t state;
    uint32_t sequence;
} audio_buffer_t;

static audio_buffer_t g_audio_buffer[2];
```

### 音频 DMA 完成处理

```
void DMA_AUDIO_IRQHandler(void)
{
    uint32_t flags =
        dma_get_flags(DMA_AUDIO_CHANNEL);

    if ((flags & DMA_FLAG_TRANSFER_ERROR) != 0U) {
        dma_clear_flags(DMA_AUDIO_CHANNEL,
                        DMA_FLAG_TRANSFER_ERROR);

        audio_dma_error_count++;
        audio_fault_notify_from_isr();
        return;
    }

    if ((flags & DMA_FLAG_HALF_TRANSFER) != 0U) {
        dma_clear_flags(DMA_AUDIO_CHANNEL,
                        DMA_FLAG_HALF_TRANSFER);

        if (!audio_mark_buffer_ready(0U)) {
            audio_overrun_count++;
        }

        audio_task_notify_from_isr(0U);
    }

    if ((flags & DMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        dma_clear_flags(DMA_AUDIO_CHANNEL,
                        DMA_FLAG_TRANSFER_COMPLETE);

        if (!audio_mark_buffer_ready(1U)) {
            audio_overrun_count++;
        }

        audio_task_notify_from_isr(1U);
    }
}
```

### SDMMC 写盘策略

SD 卡内部擦写会产生毫秒级甚至更长延迟，因此不能让音频处理任务同步等待 SDMMC：

```
void audio_task(void *arg)
{
    for (;;) {
        uint32_t buffer_id;

        if (!audio_wait_buffer(&buffer_id,
                               portMAX_DELAY)) {
            continue;
        }

        audio_buffer_t *buffer =
            &g_audio_buffer[buffer_id];

        if (buffer->state != AUDIO_BUF_READY) {
            continue;
        }

        buffer->state = AUDIO_BUF_PROCESSING;

        audio_process(buffer->address,
                      buffer->size);

        if (!audio_queue_to_sdmmc(buffer)) {
            audio_sd_queue_overflow_count++;
        }

        buffer->state = AUDIO_BUF_FREE;
    }
}
```

### 设计要点

1. 音频 DMA 采用 Very High 优先级。
2. SDMMC 使用独立的缓存队列。
3. SD 卡写入延迟不能反向阻塞音频采集。
4. 日志 DMA 只能使用低优先级。
5. 音频 Buffer 容量应覆盖 SD 卡最坏写入延迟：

BufferSize≥DataRate×Tstorage_worstBufferSize≥DataRate×Tstorage_worst​

例如音频数据率约 0.288 MB/s，SD 卡最坏延迟 100 ms：

BufferSize≥0.288×0.1=0.0288MB≈28.8KBBufferSize≥0.288×0.1=0.0288MB≈28.8KB

实际还需加入：

- 文件系统开销；
- 扇区对齐；
- Cache；
- RTOS 调度抖动；
- 多个写入请求排队；
- 安全裕量。

---

## 12. 高频问题深度答疑

## 问题一：DMA 通道优先级越高，系统性能就越好吗？

不是。

提高优先级只能提高该 DMA 获得仲裁机会的可能性，不能消除：

- 总线带宽不足；
- 外部 SDRAM 延迟；
- Burst 过长；
- 内存 Bank 冲突；
- Cache 一致性开销；
- CPU 或其他主设备竞争。

高优先级 DMA 还可能导致：

- 低优先级数据流饥饿；
- CPU 访问抖动；
- LCD 刷新不稳定；
- 其他 DMA FIFO 溢出。

正确目标不是“尽可能高优先级”，而是：

```
在满足最坏实时约束的前提下，
使用足够高但不过度的优先级。
```

---

## 问题二：DMA Channel Priority 和 NVIC Priority 哪个更重要？

两者作用不同，不能互相替代。

### DMA Channel Priority

决定：

```
多个 DMA 请求竞争时，哪个请求先获得 DMA 控制器服务。
```

### NVIC Priority

决定：

```
多个中断同时挂起时，CPU 先执行哪个 ISR。
```

例如：

```
ADC DMA 通道是 Low：
    即使 ADC ISR 是最高优先级，
    ADC 仍可能在硬件搬运阶段得不到服务。

ADC DMA 通道是 Very High：
    但 ADC ISR 是低优先级，
    数据虽已搬运完成，CPU 仍可能不能及时处理。
```

因此必须分别设计：

```
DMA Channel Priority
NVIC IRQ Priority
RTOS Task Priority
```

---

## 问题三：为什么固定优先级会导致低优先级 DMA 饥饿？

设高优先级流持续产生请求：

```
High Request -> High Request -> High Request -> ...
```

固定优先级仲裁始终优先服务高优先级请求：

```
if (high_pending) {
    service(high);
} else if (low_pending) {
    service(low);
}
```

如果 `high_pending` 永远为真，则：

```
low_service_count = 0
```

低优先级 DMA 的等待时间趋于无限。

解决方案：

- 高优先级通道限制 Burst。
- 使用优先级 + 同级轮询。
- 引入老化机制。
- 为低优先级设置最低服务配额。
- 将后台任务安排到高优先级流的空闲窗口。
- 让后台 DMA 可暂停、可取消、可恢复。

---

## 问题四：为什么平均带宽足够，仍然会发生 DMA 溢出？

平均带宽描述的是长时间平均值，DMA 溢出通常取决于短时间最坏延迟。

例如：

```
总线平均利用率：40%
ADC FIFO 可容忍时间：2 μs
某次外部 SDRAM Burst 阻塞：3 μs
```

即使平均带宽非常充足，ADC 仍会因为一次 3 μs 的阻塞而溢出。

必须同时分析：

Tworst_service<Tfifo_toleranceTworst_service​<Tfifo_tolerance​

平均带宽只是必要条件，不是充分条件。

---

## 问题五：Burst 越长，DMA 吞吐量一定越高吗？

单个数据流在理想连续传输中，较长 Burst 通常能降低地址和仲裁开销，提高总线效率。

但系统整体不一定更快，因为长 Burst 会：

- 增加其他高优先级请求等待时间；
- 放大外部内存访问峰值；
- 增加总线阻塞时间；
- 降低系统响应性；
- 造成实时 FIFO 溢出。

所以 Burst 选择应遵循：

```
高实时流：短 Burst
大块吞吐流：中长 Burst
后台流：可使用长 Burst，但必须限流
```

---

## 问题六：如何判断一个 DMA 流应该设置为高优先级？

不要按“模块重要程度”判断，应依据以下指标：

1. Deadline 是否短。
2. FIFO 是否浅。
3. 数据丢失是否不可恢复。
4. 是否存在硬件实时约束。
5. 是否有足够的缓冲空间吸收延迟。
6. 传输是否可以重试。
7. 是否会影响安全功能。
8. 是否可以拆分为更短请求。
9. 是否会长期占用总线。
10. 是否会导致其他关键流饥饿。

可以定义一个简单评分：

Score=2D+2F+2L+S−RScore=2D+2F+2L+S−R

其中：

- `D`：Deadline 紧迫程度；
- `F`：FIFO 溢出风险；
- `L`：数据丢失代价；
- `S`：安全关键等级；
- `R`：可重试能力。

分数高的流优先级更高。

---

## 问题七：DMA 优先级是否可以运行时动态修改？

可以，但需要非常谨慎。

风险包括：

- 正在运行的通道状态不一致；
- 仲裁器状态切换不可预测；
- 产生优先级抖动；
- 低优先级流频繁提升，破坏整体调度；
- RTOS 和中断上下文同时修改配置。

推荐策略：

```
1. 只在传输边界修改优先级。
2. 禁止在通道正在执行关键 Burst 时修改。
3. 使用统一 DMA Manager 管理。
4. 修改前后记录配置和时间戳。
5. 设置优先级提升持续时间上限。
6. 使用老化机制而不是频繁人工改优先级。
```

---

## 13. 课程核心总结

### 13.1 核心要点

- **DMA 仲裁决定多个 DMA 请求如何共享 DMA 控制器和系统总线。**
- DMA 优先级至少存在三个层次：
    1. 外设请求层；
    2. DMA 通道层；
    3. 系统总线主设备层。
- **DMA Channel Priority 不等于 System Bus Priority，也不等于 NVIC Priority。**
- 固定优先级适合硬实时流，但存在低优先级饥饿风险。
- 轮询适合公平共享，但高优先级最坏延迟较大。
- 工业系统通常使用：
    - 优先级分组；
    - 同级轮询；
    - 有限 Burst；
    - FIFO 阈值；
    - 内存分区；
    - 带宽预算；
    - 饥饿监测。
- **优先级必须与 Burst、FIFO、Buffer 深度和内存布局联合设计。**
- 高优先级并不能解决：
    - 总线带宽不足；
    - 外部内存延迟；
    - SRAM Bank 冲突；
    - Cache Miss；
    - 过长 Burst。
- 实时性必须满足：

Tworst_service<Tfifo_toleranceTworst_service​<Tfifo_tolerance​

- 平均带宽只是必要条件，**最坏延迟才是实时系统的核心约束**。
- 高实时流应优先考虑：
    - 更高 DMA 优先级；
    - 更短 Burst；
    - 更低 FIFO 阈值；
    - 独立 SRAM；
    - 更高 NVIC 优先级；
    - 高优先级处理任务。
- 低优先级流必须具备最低服务保障，不能允许永久饥饿。
- DMA 优先级配置必须配合运行时统计：
    - 最大等待时间；
    - 最大连续占用；
    - FIFO 峰值；
    - 错误次数；
    - 溢出次数；
    - 带宽使用率。

### 13.2 通用选型结论

|需求|推荐策略|
|---|---|
|严格实时、FIFO 很浅|Very High + Short Burst + 独立 SRAM|
|高可靠通信|High + Medium Burst + Descriptor 独立存储|
|普通业务流|Medium + FIFO / Burst 平衡|
|大块吞吐流|Medium + Long Burst，但限制最大占用|
|后台日志和资源加载|Low + 可暂停 + 空闲窗口运行|
|多个同级实时流|同级轮询|
|高优先级长期满载|增加老化、最低带宽或限流|
|多主设备访问外部 SDRAM|做 Bus Matrix、Burst 和内存 Bank 规划|
|发现 DMA 溢出|先看最坏延迟，再看平均带宽|
|发现 CPU 抖动|检查 DMA Burst、总线竞争和 Cache 行为|

---

## 14. 快速参考速查表

## 14.1 DMA 优先级速查表

|数据流|推荐优先级|Burst|FIFO|内存|
|---|---|---|---|---|
|电机 ADC|Very High|Single / Short|Low|内部 SRAM|
|音频采集|Very High|Short|Low / Medium|双缓冲 SRAM|
|Ethernet RX|High|4 Beat|Medium|专用 RX SRAM|
|UART 控制|High|Short|Low|内部 SRAM|
|SPI 传感器|Medium|Short / Medium|Medium|内部 SRAM|
|LCD|Medium|Medium|Medium / High|SDRAM|
|SDMMC|Medium|Medium / Long|High|专用 Buffer|
|日志|Low|Short / Medium|Medium|后台 SRAM|
|资源加载|Low|Long，但限时|High|外部内存|

## 14.2 仲裁策略速查表

|条件|推荐策略|
|---|---|
|严格实时、数据流少|固定优先级|
|多个同级数据流|Round-Robin|
|混合实时与后台流|优先级分组 + 同级轮询|
|高优先级长期占用|有限 Burst + 老化机制|
|多主设备共享 AXI|QoS + 内存分区 + 带宽预算|
|需要最低服务保证|加权轮询或软件配额|
|低优先级可延迟|低优先级 + 空闲窗口调度|

## 14.3 最坏延迟检查公式

### FIFO 可容忍时间

Tfifo=FIFODepthRequestRateTfifo​=RequestRateFIFODepth​

### 高优先级请求响应时间

Tresponse=Tcurrent_burst_remaining+Tarbitration+Tmemory+TqueueTresponse​=Tcurrent_burst_remaining​+Tarbitration​+Tmemory​+Tqueue​

### 实时性约束

Tresponse,max<TfifoTresponse,max​<Tfifo​

### 总线带宽需求

Brequired=∑BiEfficiencyBrequired​=Efficiency∑Bi​​

### 带宽余量

Margin=Bavailable−BrequiredMargin=Bavailable​−Brequired​

---

## 15. 学习效果自检

### 15.1 仲裁机制

- [ ]  能解释 DMA 控制器内部仲裁。
- [ ]  能解释系统 Bus Matrix 仲裁。
- [ ]  能区分固定优先级、轮询和加权轮询。
- [ ]  能说明仲裁粒度可能是 Beat、Burst 或块。
- [ ]  能分析长 Burst 对高优先级请求的影响。
- [ ]  能解释 DMA Channel Priority 与 NVIC Priority 的区别。

### 15.2 实时性分析

- [ ]  能根据 FIFO 深度和数据速率计算可容忍延迟。
- [ ]  能计算单个数据流的带宽。
- [ ]  能进行多 DMA 流带宽预算。
- [ ]  能分析平均带宽与最坏延迟的差异。
- [ ]  能判断某个数据流是否存在饥饿风险。
- [ ]  能设置最大服务等待时间。

### 15.3 配置能力

- [ ]  能为不同数据流分配 DMA 优先级。
- [ ]  能根据实时性选择 Burst 长度。
- [ ]  能根据 FIFO 深度选择 FIFO 阈值。
- [ ]  能将关键 Buffer 放到独立 SRAM。
- [ ]  能配置 DMA、NVIC 和 RTOS 三层优先级。
- [ ]  能避免所有通道都设置为最高优先级。

### 15.4 故障定位

- [ ]  能定位 ADC FIFO 溢出。
- [ ]  能定位 Ethernet RX 丢包。
- [ ]  能定位 LCD 与 MDMA 的总线竞争。
- [ ]  能识别低优先级 DMA 饥饿。
- [ ]  能通过逻辑分析仪和 DWT 测量服务延迟。
- [ ]  能通过压力测试复现瞬时总线拥塞。

### 15.5 工程设计

- [ ]  能建立 DMA 优先级矩阵。
- [ ]  能为每个 DMA 流定义最大等待时间。
- [ ]  能建立 DMA 带宽预算表。
- [ ]  能设计后台 DMA 的限流和暂停策略。
- [ ]  能设计 DMA 运行时统计模块。
- [ ]  能设计 DMA 仲裁故障的降级策略。

---

## 16. 实践与进阶路径

## 16.1 第一阶段：单 DMA 通道优先级基线测试

### 实践任务

建立一个 DMA 内存到内存或外设到内存测试工程，测量：

- 不同优先级下的传输时间；
- 不同 Burst 下的传输时间；
- 不同 FIFO 阈值下的延迟；
- CPU 同时访问 SRAM 时的 DMA 性能。

### 测试矩阵

|DMA 优先级|Burst|FIFO|传输长度|平均时间|最大时间|
|---|---|---|---|---|---|
|Low|Single|Low|4 KB|测量|测量|
|Medium|4 Beat|Medium|4 KB|测量|测量|
|High|8 Beat|High|4 KB|测量|测量|
|Very High|16 Beat|High|4 KB|测量|测量|

---

## 16.2 第二阶段：双 DMA 通道竞争测试

### 实践任务

同时启动：

```
DMA Channel 0：ADC 模拟数据流
DMA Channel 1：大块内存复制
```

逐步改变：

- Channel 0 优先级；
- Channel 1 优先级；
- Burst 长度；
- Buffer 所在 SRAM；
- CPU 访问压力。

### 需要测量

```
高优先级通道最大等待时间
低优先级通道最大等待时间
传输完成抖动
FIFO 溢出次数
总线占用率
CPU 访问延迟
```

---

## 16.3 第三阶段：模拟 FIFO 溢出

### 实践任务

使用定时器或高速外设模拟固定请求速率，逐步增加总线压力：

```
ADC DMA
    +
LCD DMA
    +
MDMA 大块搬运
    +
CPU Cache Miss
```

测试目标：

1. 找到 FIFO 开始溢出的临界点。
2. 改变 DMA 优先级，观察临界点变化。
3. 改变 Burst 长度，观察最坏延迟变化。
4. 将 Buffer 迁移到不同 SRAM Bank。
5. 对比独立内存与共享内存的结果。

---

## 16.4 第四阶段：低优先级饥饿测试

### 实践任务

配置：

```
高优先级 DMA：持续满载
低优先级 DMA：周期性提交请求
```

记录：

```
低优先级请求提交时间
低优先级首次获得服务时间
低优先级最大等待时间
低优先级超时次数
```

然后逐步增加：

- 同级轮询；
- 最大 Burst 限制；
- 动态老化；
- 最低带宽保证。

比较各策略的：

- 高优先级最坏延迟；
- 低优先级平均等待；
- 低优先级最大等待；
- 总体吞吐量。

---

## 16.5 第五阶段：FOC / 音频 / Ethernet 混合压力测试

### 实践任务

构建三类数据流：

```
1. 硬实时 ADC 或音频流
2. 高可靠 Ethernet RX
3. 低优先级日志和存储流
```

设置目标：

```
硬实时流零溢出
Ethernet 零描述符耗尽
日志允许延迟但不能无限堆积
```

### 统计指标

- DMA 最大等待周期；
- 外设 FIFO 最大占用；
- 缓冲区峰值使用量；
- 传输完成抖动；
- CPU 最坏响应时间；
- 任务调度延迟；
- 总线平均利用率；
- 总线峰值利用率；
- 丢包和溢出次数。

---

## 16.6 第六阶段：运行时 DMA 监控

建议实现统一监控结构：

```
typedef struct {
    uint64_t request_count;
    uint64_t complete_count;
    uint64_t error_count;
    uint64_t total_wait_cycles;
    uint32_t max_wait_cycles;
    uint32_t max_service_cycles;
    uint32_t starvation_count;
    uint32_t overflow_count;
} dma_runtime_stats_t;

static dma_runtime_stats_t
    g_dma_runtime_stats[DMA_CHANNEL_COUNT];
```

监控逻辑：

```
void dma_record_wait(uint32_t channel,
                     uint32_t wait_cycles)
{
    dma_runtime_stats_t *stats =
        &g_dma_runtime_stats[channel];

    stats->request_count++;
    stats->total_wait_cycles += wait_cycles;

    if (wait_cycles > stats->max_wait_cycles) {
        stats->max_wait_cycles = wait_cycles;
    }

    if (wait_cycles >
        dma_channel_max_wait(channel)) {
        stats->starvation_count++;
    }
}
```

运行时应能够输出：

```
DMA ADC:
    max_wait = 0.8 μs
    max_service = 1.2 μs
    overflow = 0

DMA Ethernet:
    max_wait = 4.5 μs
    descriptor_exhaust = 0

DMA Logger:
    max_wait = 2.8 ms
    starvation = 3
```

---

## 16.7 第七阶段：工业级 DMA 仲裁策略评审

最终应形成一份 DMA 仲裁配置文档，至少包含：

```
1. DMA 控制器和通道分配
2. 请求源映射
3. DMA Channel Priority
4. NVIC IRQ Priority
5. RTOS Task Priority
6. Burst Length
7. FIFO Threshold
8. Buffer 内存区域
9. 数据流平均带宽
10. 数据流峰值带宽
11. FIFO 深度
12. 最坏服务延迟
13. 最大等待时间
14. 饥饿防止策略
15. 错误恢复策略
16. 压力测试结果
17. 低功耗和 Cache 约束
```

推荐模块划分：

```
dma_arbiter_policy.c
    - 优先级策略
    - Burst 策略
    - FIFO 策略

dma_runtime_monitor.c
    - 等待时间统计
    - 服务时间统计
    - 饥饿检测
    - 溢出检测

dma_bandwidth_monitor.c
    - 通道带宽
    - 总线利用率
    - 峰值带宽

dma_fault_manager.c
    - DMA 错误
    - FIFO 溢出
    - 超时
    - 降级处理
```

### 进阶学习方向

1. **AXI QoS 与 Bus Matrix**
    - AWQOS；
    - ARQOS；
    - Read / Write 仲裁；
    - Outstanding Transaction。
2. **DMA 带宽整形**
    - Token Bucket；
    - 加权轮询；
    - 最低带宽保证；
    - 峰值限制。
3. **实时调度理论**
    - Response Time Analysis；
    - Worst-Case Execution Time；
    - Deadline Monotonic；
    - Rate Monotonic。
4. **存储器系统优化**
    - SRAM Bank 分配；
    - SDRAM 行命中；
    - Cache Line；
    - Burst 对齐。
5. **高性能数据流**
    - Ethernet Zero-Copy；
    - Audio Ping-Pong；
    - 摄像头采集；
    - SDMMC 多 Buffer。
6. **系统级性能工具**
    - ETM / ITM；
    - DWT；
    - SystemView；
    - Tracealyzer；
    - 总线性能监控器。
7. **安全与隔离**
    - DMA 越界；
    - MPU；
    - TrustZone；
    - 外设主设备隔离；
    - DMA 请求源权限控制。

### 本课最终能力要求

面对一个包含 ADC、Ethernet、LCD、SDMMC 和日志的复杂系统时，应能够输出类似以下的设计结论：

```
ADC 和音频属于硬实时流，使用 Very High 优先级和短 Burst，
Buffer 放置于独立内部 SRAM；

Ethernet RX 属于高可靠通信流，使用 High 优先级，
Descriptor 和 RX Buffer 放置于内部 SRAM，避免与 Framebuffer 争用 SDRAM；

LCD 属于持续吞吐流，使用 Medium 优先级，
使用 Dirty Rectangle 和受控 Burst，降低瞬时总线占用；

SDMMC 属于可缓存吞吐流，使用 Medium 或 Low 优先级，
通过大 Buffer 吸收存储介质的长尾延迟；

日志属于后台流，使用 Low 优先级，
允许暂停和延迟，并通过最大等待时间和溢出统计进行监控；

最终通过最坏服务延迟、FIFO 深度、总线峰值带宽和长时间压力测试，
证明所有硬实时流满足 Deadline，低优先级流不存在永久饥饿。
```

**DMA 仲裁的核心不是简单地把某个通道设置为最高优先级，而是在实时性、公平性、吞吐量、功耗和系统可预测性之间建立可验证的服务策略。**