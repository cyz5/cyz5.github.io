
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 DMA 控制器在总线、外设、内存之间的数据搬运机制。
    
- 理解 **DMA 循环模式（Circular Mode）** 的工作状态机、地址重装载机制和传输计数器行为。
    
- 区分：
    
    - 普通模式；
    - 循环模式；
    - 双缓冲模式；
    - 外设流控模式；
    - 环形软件队列模式。
- 理解 DMA 循环接收中的：
    
    - 半传输事件；
    - 传输完成事件；
    - DMA 写指针；
    - CPU 读指针；
    - 数据覆盖；
    - 缓存一致性。

### 1.2 掌握

能够：

- 配置 UART、SPI、ADC、I2S 等外设的 DMA 循环接收。
- 正确处理 `HT`、`TC`、空闲线、接收超时等事件。
- 设计无锁或低锁竞争的 DMA 环形缓冲区。
- 计算 DMA 缓冲区容量、最坏处理时间和覆盖风险。
- 正确处理 Cortex-M7、Cortex-A 等带 D-Cache 平台上的 DMA 一致性问题。
- 识别 DMA 中断风暴、重复处理、漏数据、数据覆盖等典型故障。

### 1.3 精通

能够：

- 从 DMA 硬件状态机和总线事务角度分析循环模式。
- 设计适合高吞吐、低延迟、可观测的 DMA 接收架构。
- 结合 `HT/TC/IDLE/Timeout` 多事件构建 UART 不定长接收方案。
- 设计 ADC 连续采样、音频采集、SPI 传感器采集等实时数据通道。
- 定量分析 CPU 占用、总线带宽、缓存维护开销和数据延迟。

### 1.4 能够设计

能够独立设计以下工业级系统：

- UART 高速不定长协议 DMA 接收框架。
- ADC 连续采样 + 双半缓冲处理架构。
- SPI 传感器连续采样 + 时间戳对齐 + 数据队列系统。
- 带 Cache 的 MPU 平台上的 DMA 非一致性解决方案。
- 可监控 DMA 丢包、溢出、延迟和处理超时的生产级组件。

---

## 2. 前置要求

### 2.1 知识要求

必须具备：

- C 语言指针、数组、结构体、`volatile`、内存对齐。
    
- MCU 地址空间、寄存器、总线矩阵和中断机制。
    
- UART、SPI、ADC 等常用外设工作原理。
    
- 中断上下文与任务上下文的区别。
    
- RTOS 任务调度、信号量、队列和临界区。
    
- 基本缓存知识：
    
    - Cache line；
    - write-back；
    - write-through；
    - invalidate；
    - clean。

### 2.2 技能要求

应能够：

- 阅读 MCU Reference Manual 中的 DMA 章节。
- 配置 DMA 通道、请求源、传输宽度和地址递增模式。
- 使用示波器或逻辑分析仪测量数据到达时刻。
- 使用 DWT、ETM、Tracealyzer 或 GPIO 翻转测量运行时间。
- 分析 map 文件、链接脚本和内存区域属性。
- 编写中断安全的数据结构。

---

## 3. 技术概述

### 3.1 DMA 的核心定义

DMA，Direct Memory Access，直接存储器访问，是一种由专用硬件控制器代替 CPU 执行数据搬运的机制。

典型数据路径为：

```
外设寄存器  <---->  DMA 控制器  <---->  SRAM / SDRAM / Flash
```

以 UART 接收为例：

```
UART_RX_DATA_REG
        |
        | DMA request
        v
DMA Channel/Stream
        |
        | memory write
        v
rx_buffer[]
```

CPU 不再对每个字节执行：

```
data = UART->RDR;
buffer[index++] = data;
```

而是仅在：

- 半缓冲；
- 满缓冲；
- 空闲线；
- 超时；
- 错误；

等事件发生时参与处理。

### 3.2 DMA 循环模式定义

DMA 循环模式的核心行为是：

1. DMA 从初始配置中获得传输计数 `NDTR`。
    
2. 每完成一次数据传输，`NDTR` 减一。
    
3. 当 `NDTR == 0` 时触发传输完成事件。
    
4. DMA 自动将：
    
    - 外设地址；
    - 内存地址；
    - 传输计数器；
    
    恢复到初始状态，继续下一轮传输。
    

逻辑模型：

```
初始状态:
memory = rx_buffer[0]
NDTR   = BUFFER_LEN

传输:
memory++
NDTR--

NDTR == 0:
memory = rx_buffer[0]
NDTR   = BUFFER_LEN
继续传输
```

注意：不同 MCU 的实现细节不同。有些 DMA 控制器只重装载传输计数和地址，有些控制器使用 descriptor 链表或 ring descriptor。

### 3.3 循环模式的技术价值

DMA 循环模式主要解决：

- 连续数据流接收；
- 固定采样率采集；
- 周期性数据搬运；
- CPU 不希望介入每个数据单元的场景；
- 低延迟批处理；
- 不定长 UART 数据的持续监听。

其核心价值是：

> **把“持续数据流”转化为“固定大小的数据块事件”。**

### 3.4 主流实现分支

|实现方式|典型平台|核心特点|
|---|---|---|
|单缓冲循环 DMA|STM32 DMA、NXP EDMA 部分模式|单个缓冲区自动回绕|
|半传输/传输完成|STM32、GD32、NXP|将缓冲区拆成前后两半|
|双缓冲 DMA|STM32 DMA Double Buffer|DMA 在两个完整 buffer 之间切换|
|Scatter-Gather|高端 MCU、SoC|descriptor 链式执行|
|Ring Descriptor|Ethernet、USB、PCIe|descriptor 本身形成环|
|DMA + 外设 FIFO|高端 MCU、MPU|降低总线访问频率|
|DMA + Cache 管理|Cortex-M7、Cortex-A|需要显式维护缓存一致性|
|DMA + 软件读写指针|UART/SPI/ADC|解决任意长度消费和数据流管理|

---

## 4. 核心特性横向对比

### 4.1 普通 DMA、循环 DMA、双缓冲 DMA 对比

|维度|普通模式|循环模式|双缓冲模式|
|---|---|---|---|
|传输完成后|停止|自动重新开始|切换到另一个 Buffer|
|适合连续流|否|是|是|
|缓冲区数量|1|1|2|
|是否容易覆盖未处理数据|较低|高|较低|
|实时处理复杂度|低|中|中|
|适合固定块处理|一般|很好|很好|
|适合不定长 UART|一般|很好|好|
|内存占用|最低|低|较高|
|处理延迟|取决于触发|半缓冲大小|单个 Buffer 大小|
|防止 DMA/CPU 并发冲突|不涉及|需要设计|通过 Buffer 切换降低风险|
|对 Cache 的要求|有|有|有|
|典型风险|传输停止|数据覆盖|切换时序错误|

### 4.2 事件机制对比

|事件|触发位置|适合用途|优点|风险|
|---|---|---|---|---|
|HT，Half Transfer|传输到缓冲区中点|低延迟流式处理|延迟低|中断频率增加|
|TC，Transfer Complete|传输到缓冲区末尾|块处理|逻辑简单|处理延迟较大|
|UART IDLE|总线空闲|不定长帧|不依赖固定帧长|需处理边界竞争|
|定时器超时|一段时间无数据|防止 IDLE 不适用|可控|额外定时器开销|
|外设阈值事件|FIFO 达到水位|高吞吐|降低中断数|依赖 FIFO 能力|
|软件轮询 NDTR|任意时间|高灵活性|不依赖 DMA 中断|增加 CPU 轮询开销|

### 4.3 UART DMA 接收方案对比

|方案|适用场景|数据处理粒度|复杂度|典型问题|
|---|---|---|---|---|
|普通 DMA + IDLE|一帧一帧接收|帧|低|连续帧边界处理|
|循环 DMA + HT/TC|连续字节流|半缓冲|中|覆盖风险|
|循环 DMA + IDLE|不定长连续流|任意长度|中高|读指针同步|
|双缓冲 + IDLE|高吞吐协议|Buffer|高|Buffer 切换|
|DMA + FIFO + 软件 Ring|高速、突发流|任意长度|高|多级缓存延迟|

---

## 5. 底层原理与功能特性深度解析

## 5.1 DMA 的基本传输状态机

一个 DMA 传输通常包含以下状态：

```
IDLE
  |
  | 外设请求到达
  v
REQUEST_ACCEPT
  |
  | 读取源地址
  v
READ
  |
  | 总线传输完成
  v
WRITE
  |
  | 更新地址与计数器
  v
UPDATE
  |
  +---- NDTR != 0 ----> WAIT_REQUEST
  |
  +---- NDTR == 0 ----> RELOAD 或 STOP
```

每一个数据单元可能是：

- 8 bit；
- 16 bit；
- 32 bit；
- 某些 DMA 支持更宽的 burst。

传输单元大小必须和外设寄存器访问宽度、内存数据类型一致。

例如 ADC 为 16 位数据：

```
uint16_t adc_buffer[1024];
```

正确配置通常为：

```
Peripheral Width = Half Word
Memory Width     = Half Word
Memory Increment = Enable
Peripheral Increment = Disable
```

如果错误配置为 8 位，可能出现：

- 数据截断；
- 地址步长不符合预期；
- 半字拆分；
- 端序相关错误；
- DMA 计数单位与业务样本数不一致。

---

## 5.2 循环模式中的关键寄存器

不同 MCU 名称不同，但通常存在以下逻辑字段：

|逻辑字段|作用|
|---|---|
|Peripheral Address|外设数据寄存器地址|
|Memory Address|内存缓冲区地址|
|Transfer Count|剩余传输单元数|
|Direction|外设到内存、内存到外设、内存到内存|
|Peripheral Increment|外设地址是否递增|
|Memory Increment|内存地址是否递增|
|Data Width|传输宽度|
|Circular Enable|是否自动回绕|
|Half Transfer Interrupt|半传输中断|
|Transfer Complete Interrupt|传输完成中断|
|Error Interrupt|传输错误中断|
|Priority|DMA 仲裁优先级|
|FIFO/Burst|FIFO 与突发传输配置|

### 5.2.1 `NDTR` 的语义

假设：

```
#define DMA_BUF_LEN 1024
```

DMA 正在写入 `rx_buffer`。

通常可以使用：

```
remaining = DMA_GetRemainingCount();
write_pos = DMA_BUF_LEN - remaining;
```

但需要注意：

1. `NDTR` 可能在总线事务完成后更新。
2. `NDTR` 读取与 DMA 写内存不是一个原子事务。
3. 在 `NDTR` 读取瞬间，DMA 可能继续接收。
4. 不同厂商对 `NDTR` 在循环重装载瞬间的可观察行为不同。
5. `NDTR == 0` 是否可读到，取决于硬件实现。

因此，生产代码不能假设：

```
read_ndtr();
read_buffer();
```

天然是一个一致快照。

---

## 5.3 DMA 循环缓冲区的核心算法

设：

```
#define DMA_BUF_LEN 1024

static uint8_t dma_buffer[DMA_BUF_LEN];
static uint32_t consumer_pos;
```

DMA 写位置为：

```
write_pos = DMA_BUF_LEN - dma_remaining;
```

为了处理回绕：

```
static uint32_t dma_get_write_pos(void)
{
    uint32_t remaining = DMA_GetRemainingCount();

    if (remaining > DMA_BUF_LEN) {
        /* DMA 状态异常 */
        return 0;
    }

    return DMA_BUF_LEN - remaining;
}
```

消费算法：

```
static uint32_t ring_distance(uint32_t write_pos,
                              uint32_t read_pos,
                              uint32_t size)
{
    if (write_pos >= read_pos) {
        return write_pos - read_pos;
    }

    return size - read_pos + write_pos;
}
```

核心处理：

```
void dma_rx_poll(void)
{
    uint32_t write_pos = dma_get_write_pos();
    uint32_t available = ring_distance(write_pos,
                                       consumer_pos,
                                       DMA_BUF_LEN);

    while (available > 0U) {
        uint32_t contiguous;

        if (write_pos >= consumer_pos) {
            contiguous = write_pos - consumer_pos;
        } else {
            contiguous = DMA_BUF_LEN - consumer_pos;
        }

        if (contiguous > available) {
            contiguous = available;
        }

        process_bytes(&dma_buffer[consumer_pos], contiguous);

        consumer_pos += contiguous;
        if (consumer_pos == DMA_BUF_LEN) {
            consumer_pos = 0;
        }

        available -= contiguous;
    }
}
```

该算法的基本假设是：

> DMA 写入速度必须不能让写指针追上并覆盖尚未消费的数据。

---

## 5.4 半传输和传输完成机制

假设缓冲区为：

```
uint16_t adc_buffer[1024];
```

DMA 循环传输：

```
0                         512                       1024
|--------------------------|--------------------------|
       Half Buffer 0                 Half Buffer 1
```

事件顺序：

```
写满 [0, 511]   -> HT
写满 [512,1023] -> TC
写满 [0, 511]   -> HT
写满 [512,1023] -> TC
```

典型处理方式：

```
void DMA_IRQHandler(void)
{
    if (DMA_GetHalfTransferFlag()) {
        DMA_ClearHalfTransferFlag();

        /*
         * DMA 此时应已开始写后半区，
         * 前半区在正常硬件行为下可供 CPU 处理。
         */
        adc_process_block(&adc_buffer[0], 512);
    }

    if (DMA_GetTransferCompleteFlag()) {
        DMA_ClearTransferCompleteFlag();

        /*
         * DMA 已经回绕并开始写前半区，
         * 后半区可供 CPU 处理。
         */
        adc_process_block(&adc_buffer[512], 512);
    }
}
```

### 重要边界

HT/TC 方案不是自动安全的。必须满足：

```
CPU 处理一个半缓冲区的最长时间
<
DMA 写满另一个半缓冲区的时间
```

如果不满足，CPU 可能尚未处理完前半区，DMA 已经下一轮写回前半区，导致数据覆盖。

---

## 5.5 UART 循环 DMA + IDLE 机制

UART 数据通常具有以下特征：

- 帧长度不固定；
- 字节之间可能有间隔；
- 数据流持续时间不确定；
- 不能仅依靠固定半缓冲事件确定帧边界。

因此常用架构是：

```
UART RX
  |
  v
DMA Circular Buffer
  |
  +--> HT
  +--> TC
  +--> IDLE
  +--> Timeout
  |
  v
根据 DMA 当前写位置计算新增数据
  |
  v
软件 Ring / 协议解析器
```

核心数据结构：

```
typedef struct {
    uint8_t  *buffer;
    uint32_t size;

    volatile uint32_t read_pos;
    volatile uint32_t last_dma_pos;

    uint32_t overflow_count;
    uint32_t error_count;
} dma_ring_t;
```

数据提取函数：

```
static uint32_t dma_current_pos(const dma_ring_t *ring)
{
    uint32_t remaining = DMA_GetRemainingCount();

    if (remaining > ring->size) {
        return 0U;
    }

    return ring->size - remaining;
}
```

事件处理：

```
void uart_dma_event_handler(dma_ring_t *ring)
{
    uint32_t current_pos;
    uint32_t start_pos;
    uint32_t length;

    current_pos = dma_current_pos(ring);
    start_pos = ring->last_dma_pos;

    if (current_pos >= start_pos) {
        length = current_pos - start_pos;

        if (length > 0U) {
            protocol_input(&ring->buffer[start_pos], length);
        }
    } else {
        length = ring->size - start_pos;

        if (length > 0U) {
            protocol_input(&ring->buffer[start_pos], length);
        }

        if (current_pos > 0U) {
            protocol_input(&ring->buffer[0], current_pos);
        }
    }

    ring->last_dma_pos = current_pos;
}
```

该实现需要进一步解决两个问题：

1. `protocol_input()` 是否允许在中断中执行。
2. CPU 处理期间 DMA 是否可能继续回绕并覆盖数据。

工业实现通常为：

```
DMA ISR:
    读取当前 DMA 位置
    复制新增数据到软件 FIFO
    发送事件给协议任务

协议任务:
    从软件 FIFO 取数据
    执行帧解析、校验和、路由
```

而不是在 DMA ISR 内直接执行完整协议解析。

---

## 5.6 `volatile` 的正确使用

DMA 缓冲区是否必须声明为 `volatile`，取决于平台和访问方式。

### DMA 缓冲区

```
static uint8_t dma_buffer[1024];
```

很多编译器不会因为 DMA 硬件修改内存而自动知道数据变化。在 CPU 通过普通指针轮询 DMA 缓冲区时，通常有两种方案：

#### 方案 A：声明为 volatile

```
static volatile uint8_t dma_buffer[1024];
```

优点：

- 防止编译器缓存 CPU 读取结果；
- 语义直观。

缺点：

- CPU 每次访问可能都变成实际内存访问；
- 影响优化；
- 不能解决 Cache 一致性；
- 不能保证多字节快照原子性。

#### 方案 B：使用显式内存屏障和 Cache 管理

在带 Cache 的系统中，更重要的是：

```
SCB_InvalidateDCache_by_Addr(...);
__DMB();
```

`volatile` 和 Cache 维护解决的是不同问题：

|问题|解决方式|
|---|---|
|编译器是否优化掉访问|`volatile`|
|CPU 与 DMA 是否看到同一份数据|Cache Clean/Invalidate 或非缓存区|
|多变量访问顺序|`DMB`|
|多核同步|原子操作、锁、内存屏障|

---

## 5.7 带 D-Cache 平台的 DMA 一致性

对于 Cortex-M7、Cortex-A 等带数据 Cache 的平台，DMA 不经过 CPU Cache。

### DMA 接收场景

DMA 写入 SRAM：

```
DMA ---> SRAM
CPU ---> Cache 中的旧数据
```

CPU 可能一直读取 Cache 中的旧副本。

接收完成后，应执行：

```
SCB_InvalidateDCache_by_Addr((uint32_t *)buffer, length);
```

### DMA 发送场景

CPU 修改 Buffer：

```
CPU ---> Cache
DMA ---> SRAM 中的旧数据
```

DMA 可能读取 SRAM 中未更新的数据。

发送前执行：

```
SCB_CleanDCache_by_Addr((uint32_t *)buffer, length);
```

### Cache line 对齐

假设 Cache line 为 32 字节，直接对非对齐地址执行维护可能影响相邻对象。因此应保证：

```
#define CACHE_LINE_SIZE 32U

__attribute__((aligned(CACHE_LINE_SIZE)))
static uint8_t dma_buffer[1024];
```

Cache 维护区间通常也要按 Cache line 向下、向上对齐：

```
static uintptr_t align_down(uintptr_t value, uintptr_t alignment)
{
    return value & ~(alignment - 1U);
}

static uintptr_t align_up(uintptr_t value, uintptr_t alignment)
{
    return (value + alignment - 1U) & ~(alignment - 1U);
}
```

工程建议：

1. DMA Buffer 独占 Cache line。
2. DMA Buffer 末尾预留到 Cache line 边界。
3. 或将 DMA Buffer 放入 MPU 配置的 non-cacheable SRAM 区域。
4. 不要让普通变量与 DMA Buffer 共用 Cache line。

---

## 5.8 DMA 循环模式的数据覆盖模型

设：

- DMA 输入速率为 `R`，单位 bytes/s；
- DMA Buffer 容量为 `B`，单位 bytes；
- CPU 最大调度延迟为 `T_sched`；
- CPU 最大处理时间为 `T_process`；
- 其他阻塞时间为 `T_block`。

为避免覆盖，至少满足：

```
B > R × (T_sched + T_process + T_block)
```

若使用半缓冲处理，每半缓冲大小为 `H`，则必须满足：

```
H / R > T_process_max
```

更保守的设计为：

```
H / R > T_process_max + T_irq_block + T_cache + T_jitter
```

例如 UART：

- 波特率：921600 bit/s；
- 8N1，每字节约 10 bit；
- 字节速率：

```
R = 921600 / 10 = 92160 bytes/s
```

如果系统最大调度和处理延迟为 3 ms：

```
B > 92160 × 0.003 = 276.48 bytes
```

实际建议使用：

```
B = 512 bytes 或 1024 bytes
```

如果采用 512 字节 Buffer 的半传输处理：

```
H = 256 bytes
H / R = 256 / 92160 ≈ 2.78 ms
```

则整个半缓冲处理必须稳定小于约 2.78 ms，并且还要留出抖动裕量。

---

## 6. 性能量化分析

以下数据为典型 Cortex-M4、Cortex-M7 类 MCU 的工程参考值，实际结果依赖：

- 主频；
- 总线架构；
- DMA 仲裁；
- SRAM 类型；
- Cache；
- 编译器；
- 数据处理算法；
- 中断优先级。

### 6.1 CPU 搬运与 DMA 搬运对比

测试假设：

- MCU：Cortex-M4，168 MHz；
- SRAM；
- UART：921600 bit/s；
- 每字节接收一次中断；
- DMA：循环接收，512 字节 Buffer；
- 编译器：GCC `-O2`。

|方案|中断频率|典型 CPU 开销|数据搬运 CPU 开销|
|---|---|---|---|
|UART 每字节中断|约 92.16 kHz|约 6%～18%|较高|
|普通 DMA + IDLE|取决于帧数|约 0.5%～2%|低|
|循环 DMA + HT/TC|约 360 Hz|约 0.2%～1%|极低|
|DMA + HT/TC + 软件 FIFO|约 360 Hz|约 0.5%～2%|低|

UART 每字节中断频率计算：

```
F_irq = Baudrate / bits_per_byte
      = 921600 / 10
      = 92160 IRQ/s
```

如果每次中断消耗 100 个 CPU cycle：

```
CPU_cycles = 92160 × 100 = 9,216,000 cycles/s
```

在 168 MHz 下：

```
CPU_usage = 9,216,000 / 168,000,000
          ≈ 5.49%
```

如果中断路径实际消耗 250～300 cycles，CPU 占用可能达到 14%～16%。

### 6.2 DMA 循环 Buffer 大小与延迟

采样率：

```
48 kHz × 2 bytes/sample = 96 kB/s
```

不同半缓冲大小：

|Half Buffer 大小|DMA 产生事件周期|理论最小批处理延迟|
|---|---|---|
|32 samples，64 B|0.667 ms|0.667 ms|
|64 samples，128 B|1.333 ms|1.333 ms|
|128 samples，256 B|2.667 ms|2.667 ms|
|256 samples，512 B|5.333 ms|5.333 ms|

结论：

- Buffer 越小，延迟越低；
- Buffer 越小，中断频率越高；
- Buffer 越大，抗调度抖动能力越强；
- Buffer 过大可能导致实时处理延迟增加。

### 6.3 中断频率公式

设：

- 数据速率 `R`，单位 bytes/s；
- 半缓冲大小 `H`，单位 bytes。

则半传输事件频率：

```
F_HT = R / H
```

同时启用 HT 和 TC 时：

```
F_event = 2R / B
```

其中 `B = 2H`。

例如：

```
R = 96,000 bytes/s
B = 512 bytes
```

则：

```
F_event = 2 × 96,000 / 512
        = 375 events/s
```

### 6.4 数据复制开销

如果 DMA Buffer 中的数据还要复制到软件 FIFO：

```
memcpy_cost = N × cycles_per_byte
```

典型 Cortex-M4 SRAM 内存复制可能约为：

```
1.5～4 cycles/byte
```

以 100 kB/s 数据流计算：

```
CPU_cycles/s = 100,000 × 2
             = 200,000 cycles/s
```

在 168 MHz 下：

```
CPU_usage ≈ 0.119%
```

因此，对于中低速 UART/SPI，复制一次数据通常不是瓶颈；真正的瓶颈往往是：

- 协议解析；
- Cache 维护；
- 锁竞争；
- 中断过于频繁；
- 数据包级别动态内存分配。

### 6.5 性能瓶颈与优化收益

|瓶颈|典型表现|优化措施|预期收益|
|---|---|---|---|
|中断过于频繁|CPU 使用率高|增大半缓冲|中断次数降低|
|数据复制过多|总线流量高|零拷贝解析|降低内存带宽|
|Cache 维护频繁|ISR 时间增加|非缓存区或批量维护|降低维护次数|
|DMA 优先级不合理|丢样、外设溢出|调整 DMA 仲裁|降低传输延迟|
|Buffer 过小|数据覆盖|增大 Buffer|提高抗抖动能力|
|Buffer 过大|延迟增加|分离 DMA Buffer 和业务队列|平衡延迟与吞吐|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否为持续数据流？
├── 否
│   └── 使用普通 DMA，传输完成后停止
│
└── 是
    ├── 数据是否固定块、固定采样率？
    │   ├── 是
    │   │   ├── CPU 处理必须严格按块进行？
    │   │   │   ├── 是：优先双缓冲或 HT/TC
    │   │   │   └── 否：循环 DMA + 定期轮询
    │   │
    │   └── 否
    │       ├── 是否存在明显帧间空闲？
    │       │   ├── 是：循环 DMA + IDLE
    │       │   └── 否：循环 DMA + 软件读写指针
    │       │
    │       └── 数据吞吐是否很高？
    │           ├── 是：DMA + FIFO + 软件 Ring + 零拷贝
    │           └── 否：DMA 循环 Buffer + 软件 FIFO
    │
    └── 平台是否启用 D-Cache？
        ├── 是：非缓存 DMA 区或显式 Clean/Invalidate
        └── 否：仍需考虑内存屏障和并发访问
```

### 7.2 典型场景选型

|场景|推荐方案|理由|
|---|---|---|
|UART 不定长协议|循环 DMA + IDLE + 软件 Ring|接收持续且帧长不固定|
|UART 高速连续字节流|循环 DMA + HT/TC + 软件 FIFO|可控批处理，降低中断数|
|ADC 连续采样|循环 DMA + HT/TC|固定采样率和固定块大小|
|音频采集|双缓冲 DMA|处理一块时 DMA 填另一块|
|SPI 连续传感器采集|循环 DMA 或链式 DMA|降低 CPU 介入|
|PWM 波形输出|普通 DMA 或循环 DMA|取决于波形是否重复|
|Ethernet RX|Descriptor Ring|不是单一线性 Buffer|
|SD 卡批量读写|普通 DMA + 多 Buffer|通常以块为单位，不宜无限循环|
|USB 音频|双缓冲/队列 DMA|需要稳定周期和流控|

---

## 8. 工程最佳实践

### 8.1 设计原则

#### 原则一：DMA Buffer 不等于业务队列

DMA Buffer 只负责：

```
硬件数据接收
```

软件 FIFO 或消息队列负责：

```
业务数据缓存和解耦
```

不要直接把 DMA Buffer 当作无限容量的业务队列。

#### 原则二：中断只做“快路径”

DMA 中断中建议只执行：

- 清除 DMA 标志；
- 读取状态；
- 计算新增数据范围；
- 记录统计信息；
- 投递事件；
- 必要的数据搬运。

不建议执行：

- 复杂协议解析；
- CRC 长计算；
- 动态内存分配；
- 阻塞式日志输出；
- 获取可能阻塞的互斥锁。

#### 原则三：明确所有权

典型所有权模型：

```
DMA 正在写入的区域：DMA 所有
DMA 已经写完且未处理的区域：待处理所有
CPU 正在处理的区域：CPU 所有
CPU 处理完成的区域：可重新使用
```

#### 原则四：优先使用单生产者、单消费者模型

DMA 是生产者，协议任务是消费者：

```
DMA Producer ---> Ring Buffer ---> Protocol Consumer
```

在单生产者、单消费者场景下，可避免重量级锁。

#### 原则五：缓存一致性必须显式设计

必须在架构阶段决定：

- DMA Buffer 是否放在 non-cacheable 区域；
- 是否使用 Cache Clean/Invalidate；
- 是否按 Cache line 对齐；
- 是否需要内存屏障；
- 业务层是否允许零拷贝。

### 8.2 选型决策矩阵

|需求|小 Buffer|大 Buffer|双缓冲|软件 Ring|
|---|---|---|---|---|
|低延迟|优|差|中|优|
|抗调度抖动|差|优|优|优|
|固定块处理|优|中|优|中|
|不定长流|中|中|中|优|
|内存占用|优|差|差|中|
|实现复杂度|低|低|中|高|
|数据覆盖防护|差|中|优|优|

### 8.3 工业级编码规范

- 所有 DMA Buffer 明确声明大小、对齐和内存段。
- 所有 DMA Buffer 初始化时清零或设置已知模式。
- 配置 DMA 前先停止旧传输并清除残留标志。
- 启动 DMA 的顺序应为：

```
停止 DMA
清除 DMA 标志
清除外设残留状态
设置外设地址
设置内存地址
设置传输长度
配置优先级和方向
使能 DMA
使能外设 DMA 请求
启动外设
```

- DMA 中断中检查所有错误标志：
    
    - Transfer Error；
    - FIFO Error；
    - Direct Mode Error；
    - Overrun；
    - Underrun；
    - Bus Error。
- 所有计数变量使用无符号定宽类型。
    
- 不在 DMA Buffer 内保存业务元数据。
    
- 使用统计计数器监控：
    

```
uint32_t dma_ht_count;
uint32_t dma_tc_count;
uint32_t dma_idle_count;
uint32_t dma_overrun_count;
uint32_t dma_error_count;
uint32_t max_processing_time;
```

---

## 9. 常见错误与避坑指南

## 9.1 错误一：循环 DMA Buffer 太小导致数据覆盖

### 错误代码

```
#define RX_BUF_SIZE 32

static uint8_t rx_buf[RX_BUF_SIZE];

void uart_dma_init(void)
{
    dma_start_circular(rx_buf, RX_BUF_SIZE);
}
```

### 根因

系统在最坏情况下 10 ms 不运行协议任务，而 921600 baud 的数据速率约为 92160 bytes/s：

```
10 ms × 92160 bytes/s = 921.6 bytes
```

32 字节 Buffer 会在约：

```
32 / 92160 ≈ 0.347 ms
```

内被覆盖。

### 正确实现

```
#define UART_RX_BUF_SIZE 1024U

_Static_assert((UART_RX_BUF_SIZE & (UART_RX_BUF_SIZE - 1U)) == 0U,
               "Buffer size should be power of two");

static uint8_t uart_rx_buf[UART_RX_BUF_SIZE];
```

### 风险影响

- 丢失协议帧；
- CRC 错误；
- 偶发解析失败；
- 现场难以复现。

---

## 9.2 错误二：在 DMA 中断中直接解析完整协议

### 错误代码

```
void DMA_IRQHandler(void)
{
    if (DMA_GetTransferCompleteFlag()) {
        DMA_ClearTransferCompleteFlag();

        protocol_parse(rx_buf, sizeof(rx_buf));
        crc32_calculate(rx_buf, sizeof(rx_buf));
        log_printf("rx complete\r\n");
    }
}
```

### 根因

中断上下文执行时间不可控，可能导致：

- 高优先级中断响应延迟；
- DMA 下一轮覆盖 Buffer；
- RTOS 临界任务被阻塞；
- 日志函数死锁或阻塞。

### 正确实现

```
void DMA_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    if (DMA_GetTransferCompleteFlag()) {
        DMA_ClearTransferCompleteFlag();

        dma_event_count++;

        xTaskNotifyFromISR(protocol_task,
                           DMA_EVENT_RX_BLOCK,
                           eSetBits,
                           &higher_priority_task_woken);
    }

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

协议任务中处理：

```
void protocol_task_entry(void *argument)
{
    uint32_t event;

    for (;;) {
        xTaskNotifyWait(0U, UINT32_MAX, &event, portMAX_DELAY);

        if ((event & DMA_EVENT_RX_BLOCK) != 0U) {
            protocol_parse_available_data();
        }
    }
}
```

### 风险影响

- 实时性下降；
- 中断嵌套异常；
- 看门狗复位；
- 高负载下数据丢失。

---

## 9.3 错误三：忽略 D-Cache 一致性

### 错误代码

```
static uint8_t rx_buf[1024];

void uart_rx_task(void)
{
    uart_dma_start(rx_buf, sizeof(rx_buf));

    /*
     * Cortex-M7 上可能一直读取 Cache 中的旧数据
     */
    parse(rx_buf, sizeof(rx_buf));
}
```

### 根因

DMA 直接写 SRAM，CPU 可能从 Cache 读取旧副本。

### 正确实现

```
#define CACHE_LINE_SIZE 32U

__attribute__((aligned(CACHE_LINE_SIZE)))
static uint8_t rx_buf[1024];

void uart_rx_prepare_for_cpu(uint8_t *buffer, size_t length)
{
    uintptr_t start;
    uintptr_t end;

    start = align_down((uintptr_t)buffer, CACHE_LINE_SIZE);
    end = align_up((uintptr_t)buffer + length, CACHE_LINE_SIZE);

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                  (int32_t)(end - start));

    __DMB();
}
```

### 风险影响

- 读取旧数据；
- 偶发首包错误；
- 开启优化或 Cache 后故障；
- Debug 版本正常、Release 版本异常。

---

## 9.4 错误四：错误使用 `volatile`，误以为能解决并发问题

### 错误代码

```
volatile uint32_t write_pos;
volatile uint32_t read_pos;

if (write_pos != read_pos) {
    data = buffer[read_pos];
    read_pos++;
}
```

### 根因

`volatile` 不能保证：

- 复合操作原子性；
- DMA 写入和 CPU 读取之间的数据快照一致；
- Cache 一致性；
- 多变量更新顺序；
- 多核同步。

### 正确实现

单生产者、单消费者模型中：

```
typedef struct {
    uint32_t read_pos;
    uint32_t write_pos;
} spsc_ring_t;
```

生产者发布写指针：

```
void ring_publish_write(spsc_ring_t *ring, uint32_t new_pos)
{
    __DMB();
    ring->write_pos = new_pos;
}
```

消费者读取写指针：

```
uint32_t ring_load_write(const spsc_ring_t *ring)
{
    uint32_t pos = ring->write_pos;

    __DMB();
    return pos;
}
```

在 RTOS 或多核环境下，应根据平台使用：

- 原子变量；
- C11 atomic；
- 临界区；
- 自旋锁；
- 内存屏障。

### 风险影响

- 数据顺序错误；
- 偶发重复处理；
- 漏读；
- 高优化级别下行为改变。

---

## 9.5 错误五：没有清除残留 DMA 标志

### 错误代码

```
void dma_restart(void)
{
    DMA_Enable(false);
    DMA_Enable(true);
}
```

### 根因

旧的 HT、TC、TE 标志可能在重新使能后立即触发中断。

### 正确实现

```
void dma_restart(void)
{
    DMA_Enable(false);

    while (DMA_IsEnabled()) {
        /* 等待硬件真正停止 */
    }

    DMA_ClearFlags(DMA_FLAG_HT |
                   DMA_FLAG_TC |
                   DMA_FLAG_TE |
                   DMA_FLAG_FE |
                   DMA_FLAG_DME);

    DMA_SetMemoryAddress(rx_buf);
    DMA_SetTransferCount(sizeof(rx_buf));

    DMA_Enable(true);
}
```

### 风险影响

- 启动后立即误触发；
- 首次数据位置错乱；
- 事件计数与实际接收不一致。

---

## 10. 多机制组合使用方案

## 10.1 推荐架构

```
                 +----------------------+
UART RX -------->| UART 外设            |
                 +----------+-----------+
                            |
                            | DMA Request
                            v
                 +----------------------+
                 | DMA Circular Buffer |
                 | HT / TC / IDLE      |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | DMA Position Tracker|
                 | read_pos/write_pos  |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Software SPSC Ring  |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Protocol Task       |
                 | framing/check/route |
                 +----------------------+
```

### 10.2 组合机制

推荐组合：

```
DMA Circular
    +
HT/TC
    +
UART IDLE
    +
Software SPSC Ring
    +
RTOS Task Notification
    +
Overflow Statistics
    +
Cache Maintenance
```

### 10.3 完整代码框架

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define DMA_RX_SIZE       1024U
#define SW_RING_SIZE      4096U
#define CACHE_LINE_SIZE   32U

typedef struct {
    uint8_t  *buffer;
    uint32_t size;

    volatile uint32_t read_pos;
    volatile uint32_t write_pos;

    uint32_t overflow_count;
    uint32_t error_count;
} spsc_byte_ring_t;

__attribute__((aligned(CACHE_LINE_SIZE)))
static uint8_t dma_rx_buffer[DMA_RX_SIZE];

static uint8_t software_ring_buffer[SW_RING_SIZE];

static spsc_byte_ring_t software_ring = {
    .buffer = software_ring_buffer,
    .size = SW_RING_SIZE,
    .read_pos = 0U,
    .write_pos = 0U,
};

static uint32_t dma_last_pos;

static uint32_t ring_next(uint32_t pos, uint32_t size)
{
    pos++;

    if (pos == size) {
        pos = 0U;
    }

    return pos;
}

static bool ring_push_byte(spsc_byte_ring_t *ring, uint8_t value)
{
    uint32_t write_pos = ring->write_pos;
    uint32_t next_pos = ring_next(write_pos, ring->size);

    if (next_pos == ring->read_pos) {
        ring->overflow_count++;
        return false;
    }

    ring->buffer[write_pos] = value;

    /*
     * 保证数据内容先于 write_pos 发布。
     */
    __DMB();
    ring->write_pos = next_pos;

    return true;
}

static uint32_t dma_get_current_pos(void)
{
    uint32_t remaining = DMA_GetRemainingCount();

    if (remaining > DMA_RX_SIZE) {
        return 0U;
    }

    return DMA_RX_SIZE - remaining;
}

static void dma_copy_new_data_to_ring(void)
{
    uint32_t current_pos = dma_get_current_pos();
    uint32_t pos = dma_last_pos;

    if (current_pos == pos) {
        return;
    }

    while (pos != current_pos) {
        /*
         * Cortex-M7/D-Cache 平台：
         * 此处应根据 DMA 写入区域进行 Invalidate。
         */
        (void)ring_push_byte(&software_ring,
                             dma_rx_buffer[pos]);

        pos = ring_next(pos, DMA_RX_SIZE);
    }

    dma_last_pos = current_pos;
}

void UART_DMA_IRQHandler(void)
{
    bool notify_protocol_task = false;

    if (DMA_GetHalfTransferFlag()) {
        DMA_ClearHalfTransferFlag();
        dma_copy_new_data_to_ring();
        notify_protocol_task = true;
    }

    if (DMA_GetTransferCompleteFlag()) {
        DMA_ClearTransferCompleteFlag();
        dma_copy_new_data_to_ring();
        notify_protocol_task = true;
    }

    if (UART_GetIdleFlag()) {
        UART_ClearIdleFlag();
        dma_copy_new_data_to_ring();
        notify_protocol_task = true;
    }

    if (DMA_GetTransferErrorFlag()) {
        DMA_ClearTransferErrorFlag();
        software_ring.error_count++;
    }

    if (notify_protocol_task) {
        rtos_notify_from_isr(PROTOCOL_TASK_EVENT_RX);
    }
}

void protocol_task(void *argument)
{
    uint8_t data;

    (void)argument;

    for (;;) {
        rtos_wait_event(PROTOCOL_TASK_EVENT_RX);

        while (ring_pop_byte(&software_ring, &data)) {
            protocol_parser_input(data);
        }
    }
}
```

该框架的优点：

- DMA Buffer 与业务 Ring 解耦；
- 支持 HT、TC、IDLE 多事件；
- 协议解析不在 ISR 内执行；
- 支持溢出统计；
- 可扩展为零拷贝；
- 可以加入 Cache 维护；
- 适合 RTOS 系统。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业控制器 UART 高速协议接收

### 需求

- UART：921600 baud；
- 数据帧长度：8～512 bytes；
- 帧之间可能没有明显空闲；
- 不能因协议任务短时阻塞造成丢帧；
- 需要统计丢包和异常。

### 架构设计

```
UART
  |
  v
DMA Circular 1024 B
  |
  +-- HT
  +-- TC
  +-- IDLE
  |
  v
软件 SPSC Ring 4096 B
  |
  v
协议解析任务
```

### 关键参数

字节速率：

```
R = 921600 / 10 = 92160 B/s
```

DMA Buffer 可容忍时间：

```
T_dma = 1024 / 92160 ≈ 11.11 ms
```

软件 Ring 可容忍时间：

```
T_ring = 4096 / 92160 ≈ 44.44 ms
```

因此：

- DMA ISR 至少应在 11 ms 内处理一次新增数据；
- 协议任务即使短时阻塞，也能依靠软件 Ring 额外吸收约 44 ms 数据。

### 设计要点

- DMA Buffer 不直接进行复杂解析；
- `IDLE` 只作为“尽快处理”的提示，不作为唯一可靠机制；
- 必须处理 DMA Buffer 回绕；
- 软件 Ring 满时记录 overflow；
- 协议帧必须具备长度、校验和、重同步机制。

### 协议解析建议

```
WAIT_HEADER
    |
    v
READ_LENGTH
    |
    v
READ_PAYLOAD
    |
    v
CHECK_CRC
    |
    +-- OK  ---> DISPATCH
    |
    +-- ERROR -> SEARCH_NEXT_HEADER
```

不能假设一次 IDLE 事件就是一帧完整数据。

---

## 11.2 案例二：ADC 连续采样与数字滤波

### 需求

- ADC 采样率：48 kHz；
- 每个采样点：16 bit；
- 使用 DMA 连续采样；
- 每 128 个采样点执行一次 FIR 滤波；
- 最大算法处理时间小于采样窗口。

### 架构

```
ADC 48 kHz
    |
    v
DMA Circular Buffer 256 samples
    |
    +-- HT: 处理前 128 samples
    +-- TC: 处理后 128 samples
```

### 时间预算

每个半缓冲区：

```
T_half = 128 / 48000
       ≈ 2.667 ms
```

如果 FIR 处理实测耗时：

```
T_fir = 1.2 ms
```

裕量：

```
Margin = 2.667 - 1.2
       = 1.467 ms
```

该配置相对安全。

如果 FIR 耗时增加到 3.1 ms，则必然存在覆盖风险。

### 关键代码

```
#define ADC_BLOCK_SAMPLES 128U
#define ADC_DMA_SAMPLES   (ADC_BLOCK_SAMPLES * 2U)

__attribute__((aligned(32)))
static uint16_t adc_dma_buffer[ADC_DMA_SAMPLES];

void ADC_DMA_IRQHandler(void)
{
    if (DMA_GetHalfTransferFlag()) {
        DMA_ClearHalfTransferFlag();

        /*
         * 前半区已完成，DMA 正在写后半区。
         */
        adc_submit_block(&adc_dma_buffer[0],
                         ADC_BLOCK_SAMPLES);
    }

    if (DMA_GetTransferCompleteFlag()) {
        DMA_ClearTransferCompleteFlag();

        /*
         * 后半区已完成，DMA 已开始回写前半区。
         */
        adc_submit_block(&adc_dma_buffer[ADC_BLOCK_SAMPLES],
                         ADC_BLOCK_SAMPLES);
    }
}
```

### 设计要点

- FIR、FFT 等处理放在高优先级实时任务中；
- DMA ISR 只投递 Buffer 地址；
- 处理时间必须通过 DWT 实测；
- 如果算法偶发超时，应增加 DMA Buffer 或采用双缓冲；
- 禁止在处理期间修改 DMA 正在写入的区域。

---

## 11.3 案例三：Cortex-M7 SPI 传感器连续采集

### 需求

- Cortex-M7，主频 400 MHz；
- D-Cache 开启；
- SPI 速率 20 MHz；
- 每次采集 32 bytes；
- 采样周期 1 ms；
- 需要将数据送入算法任务。

### 设计方案

```
SPI DMA RX
    |
    v
Non-cacheable DMA Buffer
    |
    v
Cacheable Algorithm Buffer
    |
    v
Sensor Fusion Task
```

也可以采用：

```
Cacheable DMA Buffer
    +
Invalidate D-Cache before CPU read
```

### 数据率

```
32 bytes × 1000 samples/s = 32 kB/s
```

数据吞吐本身很低，Cache 维护开销不大。但为了降低一致性故障概率，推荐：

- DMA Buffer 放在专用 non-cacheable SRAM；
- 算法 Buffer 放在 cacheable SRAM；
- DMA 完成后复制一次数据。

### 设计要点

不要因为 M7 主频高就忽略 DMA 一致性。高性能 CPU 往往更容易暴露：

- Cache 旧数据；
- Store Buffer 延迟；
- 总线乱序观察；
- 中断和 DMA 的时序竞争。

---

## 12. 高频问题深度答疑

## 12.1 为什么循环 DMA 仍然会丢数据？

循环模式只负责：

```
自动回绕继续写
```

它不负责：

```
保证 CPU 已经处理数据
```

当 DMA 写指针追上 CPU 读指针时，硬件默认不会判断“这个区域是否仍在使用”，而是直接覆盖。

因此循环 DMA 必须配合：

- 足够大的 Buffer；
- 正确的读写指针；
- 溢出检测；
- 合理的任务调度；
- 处理时间预算。

---

## 12.2 HT/TC 事件和 IDLE 事件能否同时使用？

可以，而且通常推荐同时使用。

- `HT/TC`：保证持续数据流下不会长时间不处理。
- `IDLE`：数据短帧结束时立即触发，降低延迟。

但事件处理函数必须幂等，即多次事件不能重复消费同一段数据。

核心原则：

```
所有事件最终都只调用一次：
process_from(last_pos, current_pos)
```

而不是每类事件分别复制一套数据处理逻辑。

---

## 12.3 是否应该关闭 HT 中断，只使用 TC？

取决于实时性和处理耗时。

适合只使用 TC：

- 数据处理允许更高延迟；
- CPU 负载敏感；
- Buffer 足够大；
- 单次处理时间可控。

适合 HT + TC：

- 连续流；
- 低延迟；
- CPU 需要尽快释放半缓冲区；
- 每块数据处理时间较短。

如果只使用 TC，DMA Buffer 被全部填满后才通知 CPU，处理窗口和覆盖边界更紧张。

---

## 12.4 DMA Buffer 应该多大？

不能凭经验拍一个数，必须计算。

基本公式：

```
Buffer_Size > Data_Rate × Worst_Case_Service_Latency
```

进一步增加安全系数：

```
Buffer_Size >= Data_Rate × Worst_Case_Latency × Safety_Factor
```

通常安全系数可取：

```
1.5～3.0
```

还需要满足：

- 内存预算；
- Cache line 对齐；
- 协议最大帧长度；
- RTOS 最坏调度延迟；
- DMA 总线抢占；
- 处理任务优先级。

---

## 12.5 DMA Buffer 能否直接被协议解析器使用？

可以，但必须满足以下条件：

1. 解析器支持分段输入；
2. 解析器不要求数据物理连续；
3. DMA 不会覆盖解析器正在读取的区域；
4. 已处理数据不会被重复使用；
5. 已解决 Cache 一致性。

如果协议帧可能跨越 DMA Buffer 尾部，解析器必须支持：

```
segment 1: buffer[read_pos ... end]
segment 2: buffer[0 ... write_pos)
```

否则更稳妥的方式是复制到软件 Ring 或线性帧 Buffer。

---

## 12.6 为什么 DMA 传输完成后 CPU 仍读不到最新数据？

最常见原因是 D-Cache。

DMA 写的是 SRAM：

```
DMA -> SRAM
```

CPU 读取的是 Cache：

```
CPU -> Cache
```

如果 Cache line 中存在旧数据，CPU 不会自动感知 SRAM 已被 DMA 修改。

接收场景必须：

```
DMA 完成
    |
    v
Invalidate Cache
    |
    v
DMB
    |
    v
CPU 读取
```

发送场景则是：

```
CPU 修改 Buffer
    |
    v
Clean Cache
    |
    v
DMB
    |
    v
DMA 读取
```

---

## 13. 课程核心总结

### 13.1 核心要点

1. **DMA 循环模式适合连续数据流。**
2. 循环模式本质是：

```
传输计数耗尽后自动重装地址和计数，继续搬运
```

3. HT/TC 将一个连续 Buffer 切分为两个处理窗口。
4. UART 不定长接收推荐：

```
循环 DMA + HT/TC + IDLE + 软件 Ring
```

5. ADC、音频等固定采样流推荐：

```
循环 DMA + HT/TC
```

6. 双缓冲比单缓冲循环模式更容易建立明确的 Buffer 所有权。
7. DMA Buffer 容量必须依据最坏数据速率和最坏服务延迟计算。
8. `volatile` 不能解决 Cache 一致性，也不能替代同步机制。
9. 带 D-Cache 的平台必须使用：

```
Non-cacheable 区域
或
Clean/Invalidate Cache
```

10. DMA ISR 只做轻量事件处理，复杂解析应放到任务上下文。

### 13.2 性能排序

在典型连续接收场景中，CPU 开销大致排序：

```
每字节中断
    >
DMA + 每帧中断
    >
DMA + HT/TC
    >
DMA + HT/TC + 软件 Ring
    >
DMA + 零拷贝 + 批量处理
```

但延迟大致相反：

```
每字节中断
    <
IDLE/超时
    <
小半缓冲 HT/TC
    <
大半缓冲 HT/TC
```

### 13.3 通用选型结论

|需求|首选方案|
|---|---|
|连续固定采样|循环 DMA + HT/TC|
|低延迟音频|双缓冲 DMA|
|UART 不定长帧|循环 DMA + IDLE|
|高速连续 UART|循环 DMA + 软件 Ring|
|带 Cache MCU|Non-cacheable DMA Buffer 或显式 Cache 维护|
|极高吞吐|Descriptor Ring / Scatter-Gather|
|业务复杂且处理可能阻塞|DMA Buffer + 软件 FIFO + 任务处理|

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|DMA 模式|事件|软件结构|
|---|---|---|---|
|ADC 连续采样|Circular|HT/TC|双半缓冲|
|UART 不定长|Circular|IDLE + HT/TC|SPSC Ring|
|SPI 连续采集|Circular/双缓冲|HT/TC|数据块队列|
|音频|双缓冲|Buffer 完成|实时音频任务|
|PWM 重复波形|Circular|周期事件|波形表|
|Ethernet|Descriptor Ring|RX Done|Descriptor Queue|
|SD 批量传输|Normal/链式|TC|Block Queue|

### 14.2 特性对比表

|特性|普通模式|循环模式|双缓冲模式|
|---|---|---|---|
|自动重复|否|是|是|
|内存占用|低|低|中高|
|连续流支持|弱|强|强|
|数据覆盖风险|中|高|低|
|实时性|中|高|高|
|软件复杂度|低|中|中高|
|典型用途|一次性传输|连续采样/接收|块级实时处理|

### 14.3 关键公式

```
UART Byte Rate = Baudrate / Bits_Per_Byte

Buffer Time = Buffer_Size / Data_Rate

Event Frequency = Data_Rate / Event_Block_Size

No-Overflow Condition:
Buffer_Size > Data_Rate × Worst_Case_Service_Latency

Half-Buffer Condition:
Half_Buffer_Size / Data_Rate > Max_Block_Processing_Time
```

### 14.4 DMA 接收检查清单

```
[ ] 外设 DMA 请求已使能
[ ] DMA 方向正确
[ ] 外设地址固定
[ ] 内存地址递增
[ ] 数据宽度匹配
[ ] Buffer 长度与 NDTR 单位一致
[ ] Circular 已使能
[ ] HT/TC/IDLE 标志正确清除
[ ] DMA 错误标志已处理
[ ] 读写指针逻辑正确
[ ] 已考虑 Buffer 回绕
[ ] 已计算最坏覆盖时间
[ ] 已处理 D-Cache
[ ] DMA ISR 无阻塞操作
[ ] 有溢出和错误统计
[ ] 具备故障恢复机制
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实现：

### 原理检查

- [ ]  解释 DMA 循环模式如何重装载地址和计数器。
- [ ]  解释 `NDTR` 在循环模式中的含义。
- [ ]  说明 HT 和 TC 的触发时机。
- [ ]  说明为什么循环 DMA 仍然可能覆盖未处理数据。
- [ ]  区分 DMA Buffer 和软件 Ring Buffer 的职责。

### 工程检查

- [ ]  能够配置 UART 循环 DMA 接收。
- [ ]  能够处理 DMA Buffer 回绕。
- [ ]  能够处理 IDLE 与 HT/TC 重复事件。
- [ ]  能够设计无锁 SPSC 数据队列。
- [ ]  能够实现 DMA 错误恢复和统计。

### 性能检查

- [ ]  能够根据波特率计算字节速率。
- [ ]  能够根据最大服务延迟计算 Buffer 大小。
- [ ]  能够计算 HT/TC 事件频率。
- [ ]  能够通过 DWT 测量半缓冲处理时间。
- [ ]  能够判断当前 DMA 配置是否存在覆盖风险。

### Cache 检查

- [ ]  能够解释 DMA 与 CPU Cache 的不一致原因。
- [ ]  能够区分接收场景的 Invalidate 和发送场景的 Clean。
- [ ]  能够设计 Cache line 对齐的 DMA Buffer。
- [ ]  能够选择 non-cacheable 区域或显式 Cache 管理方案。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：UART 普通 DMA 接收

要求：

- 使用普通 DMA 接收固定长度数据；
- 接收完成后触发中断；
- 校验数据完整性；
- 测量 CPU 占用。

目标：

```
理解 DMA 地址和计数器基本机制
```

#### 任务二：UART 循环 DMA + HT/TC

要求：

- 配置 256 字节循环 Buffer；
- HT 处理前 128 字节；
- TC 处理后 128 字节；
- 使用 GPIO 测量处理时间；
- 人为增加处理延迟，观察数据覆盖。

目标：

```
掌握半缓冲处理窗口和覆盖边界
```

#### 任务三：UART 循环 DMA + IDLE + 软件 Ring

要求：

- 支持 8～512 字节不定长数据；
- 处理 Buffer 回绕；
- 任务中执行协议解析；
- 统计溢出、IDLE、HT、TC 次数。

目标：

```
构建生产级 UART DMA 接收框架
```

#### 任务四：ADC 连续采样 + FIR

要求：

- 48 kHz 采样；
- 256 samples DMA Buffer；
- HT/TC 触发 FIR；
- 使用 DWT 测量 FIR 最长时间；
- 计算实时处理裕量。

目标：

```
掌握固定采样流的实时性分析
```

#### 任务五：Cortex-M7 Cache 一致性实验

要求：

1. DMA Buffer 放在 Cacheable SRAM；
2. 不做 Invalidate，观察旧数据；
3. 加入 Invalidate，验证修复；
4. 改为 Non-cacheable 区域；
5. 对比两种方案性能。

目标：

```
掌握 DMA Cache 一致性的底层本质
```

### 16.2 性能测试方法

建议测量以下指标：

|指标|测量方法|
|---|---|
|DMA 中断频率|统计 HT/TC 次数|
|ISR 时间|GPIO 翻转或 DWT|
|任务处理时间|DWT、Tracealyzer|
|最大调度延迟|RTOS trace|
|Buffer 峰值占用|记录读写指针距离|
|溢出次数|软件计数器|
|Cache 维护时间|DWT 周期计数|
|数据丢失率|序列号检测|
|端到端延迟|外部触发 + GPIO/逻辑分析仪|

推荐在测试中加入压力条件：

```
提高其他中断负载
降低协议任务优先级
增加临界区阻塞
启用 D-Cache
增加总线访问竞争
随机插入突发数据
```

### 16.3 进阶学习方向

完成 DMA 循环模式后，建议继续学习：

1. **DMA 双缓冲模式**
2. **DMA FIFO 与 Burst 传输**
3. **链式 DMA 和 Scatter-Gather**
4. **DMAMUX 请求路由与同步**
5. **外设 FIFO 与 DMA 水位控制**
6. **Cortex-M7 MPU 和 Non-cacheable 内存设计**
7. **Ethernet Descriptor Ring**
8. **USB Endpoint DMA**
9. **零拷贝协议栈**
10. **RTOS 中断到任务的低延迟通知**
11. **DMA 与总线矩阵仲裁**
12. **高可靠数据流的序列号、回压和丢包恢复**
13. **Linux DMA API、DMA coherent memory 和 IOMMU**
14. **嵌入式系统 DMA 安全隔离与权限控制**

最终应形成以下架构能力：

```
外设数据流建模
      +
DMA 搬运机制设计
      +
缓存一致性设计
      +
实时性量化
      +
数据所有权管理
      +
错误恢复和可观测性
      =
工业级 DMA 数据通道
```