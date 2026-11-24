
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 DMA 控制器在 CPU、外设、总线矩阵、内存之间的角色定位。
- 理解 DMA 单缓冲、循环缓冲、Ping-Pong 双缓冲、链式描述符的工作机制。
- 理解 DMA 传输请求、仲裁、突发、FIFO、地址递增、数据宽度、缓存一致性之间的关系。
- 理解 DMA 双缓冲中“半传输 / 全传输 / 缓冲区切换”的时序。
- 理解 DMA 与实时性、总线带宽、Cache、一致性、内存屏障之间的关联。

### 1.2 掌握

能够：

- 配置内存到外设、外设到内存、内存到内存三类 DMA 传输。
- 设计基于 Ping-Pong 缓冲的连续采集架构。
- 正确处理 DMA 完成中断、半传输中断、错误中断。
- 计算 DMA 缓冲区大小、CPU 处理预算和总线带宽。
- 编写具备边界检查、溢出检测和错误恢复能力的 DMA 驱动框架。

### 1.3 精通

能够：

- 分析 DMA 与 CPU、Cache、RTOS 调度之间的竞态问题。
- 处理 Cortex-M7、Cortex-A 等带数据 Cache 平台上的 DMA 一致性问题。
- 根据外设速率、处理时延、总线负载选择单缓冲、双缓冲或环形队列。
- 解决 DMA 中断风暴、优先级反转、数据覆盖、错帧、丢样本等现场问题。
- 设计 DMA 超时、异常复位、故障隔离和数据完整性校验机制。

### 1.4 能够设计

能够完成以下工业级设计：

- 高速 ADC 连续采集 + 双缓冲信号处理系统。
- UART/SPI/CAN-FD 等通信接口的 DMA 接收架构。
- 音频 I2S/SAI 双缓冲采集与播放系统。
- RTOS 环境下 ISR、工作线程、处理线程之间的 DMA 数据流水线。
- 带 Cache 管理、内存分区、性能监测和故障恢复的 DMA 子系统。

---

# 2. 前置要求

## 2.1 知识要求

- C 语言指针、数组、结构体、`volatile`、内存对齐。
- MCU 中断、NVIC、优先级、临界区。
- 片上总线基础：AHB、AXI、APB、总线矩阵。
- MCU 存储器映射、SRAM、Flash、外设寄存器。
- RTOS 任务、队列、信号量、事件组。
- 基本 Cache、MPU、内存屏障概念。
- 定时器、ADC、UART、SPI 等外设触发机制。

## 2.2 技能要求

- 能阅读芯片参考手册中的 DMA 章节。
- 能使用逻辑分析仪或示波器观测外设时序。
- 能通过寄存器、调试器和日志定位 DMA 状态异常。
- 能编写中断安全的环形队列和生产者/消费者模型。
- 能使用 DWT、ETM、Trace、GPIO 翻转等方法测量实时性。

---

# 3. 技术概述

## 3.1 DMA 的核心定义

DMA，即 Direct Memory Access，直接存储器访问，是一种允许外设或内存控制器在不经过 CPU 逐字节参与的情况下完成数据搬运的硬件机制。

典型数据路径为：

```
外设寄存器
    │
    │ 外设请求/DMA Request
    ▼
DMA 控制器
    │
    │ 总线读写
    ▼
SRAM / 外部内存
```

CPU 主要负责：

1. 初始化 DMA 描述符或寄存器；
2. 启动 DMA；
3. 响应半传输、全传输、错误中断；
4. 处理已完成的数据块；
5. 监控 DMA 运行状态。

DMA 的关键价值是：

- 降低 CPU 搬运数据的指令开销；
- 提高持续数据流的吞吐能力；
- 缩短中断处理路径；
- 让 CPU 与外设传输并行执行；
- 构建采集、处理、发送流水线。

---

## 3.2 DMA 的主要分类

### 按传输方向分类

|类型|数据方向|典型场景|
|---|---|---|
|Peripheral-to-Memory|外设到内存|ADC、UART、SPI、I2S 接收|
|Memory-to-Peripheral|内存到外设|UART、SPI、DAC、I2S 发送|
|Memory-to-Memory|内存到内存|大块搬运、图像复制、数据重排|

### 按缓冲方式分类

|方案|描述|
|---|---|
|单次传输|传输完成后停止|
|循环模式|到达末尾后自动回到起始地址|
|半传输模式|缓冲区前半段完成时触发事件|
|双缓冲模式|两块内存交替作为当前 DMA 目标|
|链式描述符|DMA 自动切换多个描述符或缓冲区|

### 按地址模式分类

|地址模式|说明|
|---|---|
|固定外设地址|外设寄存器地址不变|
|内存地址递增|连续填充数组|
|外设地址递增|多寄存器或多通道访问|
|双地址递增|内存到内存搬运|
|环形地址|地址达到边界后回绕|

---

## 3.3 DMA 双缓冲的定义

DMA 双缓冲通常称为：

- Ping-Pong Buffer；
- Double Buffer；
- Multi-buffer；
- Circular Double Buffer。

其基本结构为：

```
Buffer A：DMA 正在写入/读取
Buffer B：CPU 正在处理

时间 T0：
DMA -> Buffer A
CPU -> Buffer B

时间 T1：
DMA -> Buffer B
CPU -> Buffer A

时间 T2：
DMA -> Buffer A
CPU -> Buffer B
```

其核心目标是实现：

> **DMA 传输与 CPU 数据处理并行执行，避免 CPU 处理期间阻塞外设数据流。**

---

# 4. 核心特性横向对比

## 4.1 单缓冲、半传输、双缓冲、环形队列对比

|维度|单缓冲|半传输|硬件双缓冲|软件环形队列|
|---|---|---|---|---|
|实现复杂度|低|中|中|中高|
|连续传输能力|弱|较强|强|强|
|CPU 处理粒度|整块|半块|整块|可变|
|缓冲切换开销|高|低|很低|中|
|对实时性的要求|高|中|中|低到中|
|适合固定帧长|是|是|是|不一定|
|适合不定长数据|弱|弱|中|强|
|数据覆盖风险|高|中|低|可控|
|RAM 占用|1×|1×|2×|N×|
|DMA 自动切换|否|部分|是|取决于硬件|
|典型场景|一次性搬运|连续采样|ADC、音频、SPI|UART 流数据|

## 4.2 双缓冲实现方式对比

|方案|切换机制|优点|缺点|推荐场景|
|---|---|---|---|---|
|DMA 硬件双地址|DMA 自动在 M0/M1 间切换|延迟低、CPU 开销小|受芯片 DMA 功能限制|高速连续流|
|半传输中断|一个大数组前后半区交替使用|兼容性好、配置简单|CPU 依赖中断及时处理|ADC、I2S|
|软件指针交换|DMA 每次完成后重设地址|灵活|存在停顿和重启窗口|低速采集|
|链式描述符|描述符指向多个缓冲区|适合复杂流水线|配置和调试复杂|Ethernet、SDIO、图像|
|DMA + 环形队列|DMA 连续写，软件追踪读写指针|适合不定长数据|边界处理复杂|UART、网络接收|

---

# 5. 底层原理与功能特性深度解析

## 5.1 DMA 一次传输的底层过程

一次 DMA 传输可抽象为：

```
1. 外设产生请求
2. DMA 控制器获得总线访问权
3. DMA 从源地址读取数据
4. DMA 将数据写入目标地址
5. 源/目标地址按配置递增或保持
6. 剩余传输计数器递减
7. 计数器归零后产生 TC 事件
```

对于外设到内存传输：

```
源地址 = 外设数据寄存器
目标地址 = SRAM 当前写入位置
源地址 = 固定
目标地址 = 递增
```

对于内存到外设传输：

```
源地址 = SRAM 当前读取位置
目标地址 = 外设数据寄存器
源地址 = 递增
目标地址 = 固定
```

---

## 5.2 DMA 配置核心参数

典型 DMA 配置包含：

```
typedef enum {
    DMA_DIR_PERIPH_TO_MEM,
    DMA_DIR_MEM_TO_PERIPH,
    DMA_DIR_MEM_TO_MEM
} dma_direction_t;

typedef enum {
    DMA_DATA_8BIT  = 1,
    DMA_DATA_16BIT = 2,
    DMA_DATA_32BIT = 4
} dma_data_width_t;

typedef struct {
    dma_direction_t   direction;
    uintptr_t         periph_addr;
    uintptr_t         mem0_addr;
    uintptr_t         mem1_addr;
    size_t            transfer_count;
    dma_data_width_t  periph_width;
    dma_data_width_t  mem_width;
    bool              periph_inc;
    bool              mem_inc;
    bool              circular;
    bool              double_buffer;
    uint8_t           priority;
} dma_config_t;
```

### 关键约束

必须检查：

```
1. 地址是否位于 DMA 可访问内存区域；
2. 地址是否满足数据宽度对齐要求；
3. 传输长度是否为合法范围；
4. 外设数据宽度与 DMA 数据宽度是否匹配；
5. 双缓冲的两个地址是否不重叠；
6. Cache 是否需要清理或失效；
7. DMA 是否支持该外设请求线；
8. DMA 通道是否与其他高优先级设备冲突。
```

---

## 5.3 DMA 双缓冲硬件切换机制

硬件双缓冲通常内部维护：

```
当前目标 = M0 或 M1
下一目标 = 另一个地址
```

当当前缓冲区传输完成时：

```
1. DMA 将当前目标切换为另一个内存地址；
2. 更新当前目标标志；
3. 产生传输完成中断；
4. CPU 根据当前目标标志判断哪个缓冲区已经完成；
5. CPU 处理已经完成的缓冲区。
```

伪代码如下：

```
void dma_irq_handler(void)
{
    uint32_t status = dma_get_status();

    if (status & DMA_FLAG_TRANSFER_COMPLETE) {
        bool current_is_m1 = dma_get_current_target() == DMA_TARGET_M1;

        /*
         * DMA 已经切换到新的目标缓冲区，
         * 因此刚刚完成的是另一个缓冲区。
         */
        uint8_t completed_index = current_is_m1 ? 0U : 1U;

        dma_clear_flag(DMA_FLAG_TRANSFER_COMPLETE);

        dma_buffer_ready(completed_index);
    }

    if (status & DMA_FLAG_TRANSFER_ERROR) {
        dma_clear_flag(DMA_FLAG_TRANSFER_ERROR);
        dma_error_recovery();
    }
}
```

### 关键点

不要简单地根据“中断次数奇偶”判断完成缓冲区。更可靠的方法是：

- 读取硬件当前目标寄存器；
- 根据硬件规定的切换时序判断；
- 或读取 DMA 状态寄存器中的 CT/Target 位。

因为：

- 中断可能被延迟；
- 某些平台同时存在半传输与全传输事件；
- 错误恢复后中断序列可能不再保持简单奇偶关系。

---

## 5.4 半传输双缓冲机制

某些 DMA 没有硬件 M0/M1 双缓冲，但支持半传输中断。

假设缓冲区为：

```
#define DMA_BLOCK_SAMPLES 256U

static uint16_t adc_dma_buffer[DMA_BLOCK_SAMPLES];
```

逻辑上分成：

```
[0 ... 127]       前半缓冲
[128 ... 255]     后半缓冲
```

传输过程：

```
DMA 写前半段 -> HT 中断 -> CPU 处理前半段
DMA 写后半段 -> TC 中断 -> CPU 处理后半段
DMA 再次写前半段 -> HT 中断
...
```

示例：

```
#define DMA_HALF_SAMPLES 128U

static uint16_t adc_dma_buffer[DMA_HALF_SAMPLES * 2U];

void adc_dma_irq_handler(void)
{
    uint32_t flags = dma_get_status();

    if ((flags & DMA_FLAG_HALF_TRANSFER) != 0U) {
        dma_clear_flag(DMA_FLAG_HALF_TRANSFER);

        /*
         * 前半区已经写满，DMA 正在写后半区。
         */
        adc_block_ready(&adc_dma_buffer[0],
                        DMA_HALF_SAMPLES);
    }

    if ((flags & DMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        dma_clear_flag(DMA_FLAG_TRANSFER_COMPLETE);

        /*
         * 后半区已经写满，DMA 即将回到前半区。
         */
        adc_block_ready(&adc_dma_buffer[DMA_HALF_SAMPLES],
                        DMA_HALF_SAMPLES);
    }
}
```

### 重要时序约束

处理前半区必须在 DMA 再次写入前半区之前完成：

```
T_process < T_half_period
```

其中：

```
T_half_period = DMA_HALF_SAMPLES / sample_rate
```

例如：

```
采样率 = 48 kHz
半缓冲样本数 = 128

T_half_period = 128 / 48000
              = 2.667 ms
```

如果 CPU 处理一半缓冲区需要 3 ms，则一定存在覆盖风险。

---

## 5.5 双缓冲与 `volatile`

DMA 修改的内存区域不应简单理解为“所有数据都必须加 `volatile`”。

例如：

```
static uint16_t dma_buffer[256];
```

DMA 硬件会修改该数组，但 C 编译器并不知道 DMA 的存在。对于通过中断通知的设计，可以使用事件同步保证可见性：

```
static volatile bool buffer_ready[2];
```

数据本体不一定必须是 `volatile`，但状态变量通常需要：

```
static uint16_t buffer[2][128];
static volatile uint8_t ready_mask;

void dma_isr(void)
{
    ready_mask |= 0x01U;
}

void processing_task(void)
{
    uint8_t mask = ready_mask;

    if ((mask & 0x01U) != 0U) {
        ready_mask &= (uint8_t)~0x01U;
        process_block(buffer[0], 128);
    }
}
```

然而仅使用 `volatile` 不能解决：

- Cache 一致性；
- 多字节状态的原子性；
- ISR 与任务之间的竞态；
- 内存访问顺序；
- 缓冲区被 DMA 同时修改的问题。

工业级设计应采用：

- 原子变量；
- 临界区；
- RTOS 队列；
- 内存屏障；
- Cache 维护操作；
- 明确的缓冲区所有权。

---

## 5.6 DMA 缓冲区所有权模型

建议采用明确的 Ownership 状态：

```
typedef enum {
    BUF_FREE = 0,
    BUF_DMA_WRITING,
    BUF_READY,
    BUF_PROCESSING
} buffer_state_t;
```

状态转换：

```
FREE
 │
 ▼
DMA_WRITING
 │ DMA 完成
 ▼
READY
 │ CPU 获取
 ▼
PROCESSING
 │ CPU 处理完成
 ▼
FREE
```

示例：

```
typedef struct {
    uint16_t *data;
    size_t length;
    volatile buffer_state_t state;
} dma_buffer_slot_t;

static dma_buffer_slot_t slots[2];

static bool buffer_acquire_for_processing(dma_buffer_slot_t **slot)
{
    for (size_t i = 0U; i < 2U; ++i) {
        if (slots[i].state == BUF_READY) {
            slots[i].state = BUF_PROCESSING;
            *slot = &slots[i];
            return true;
        }
    }

    return false;
}

static void buffer_release_after_processing(dma_buffer_slot_t *slot)
{
    if (slot == NULL) {
        return;
    }

    slot->state = BUF_FREE;
}
```

在纯硬件双缓冲模式下，`BUF_FREE` 与 `BUF_DMA_WRITING` 通常由 DMA 当前目标隐式维护，软件主要管理 `READY` 和 `PROCESSING`。

---

# 6. 性能量化分析

## 6.1 CPU 搬运与 DMA 搬运的开销模型

假设每个样本需要 CPU 执行：

- 读取外设寄存器：CrCr​ 个周期；
- 写入内存：CwCw​ 个周期；
- 地址更新：CaCa​ 个周期；
- 循环判断：ClCl​ 个周期。

则 CPU 搬运总周期约为：

CCPU=N(Cr+Cw+Ca+Cl)CCPU​=N(Cr​+Cw​+Ca​+Cl​)

DMA 模式下，CPU 主要承担初始化和中断处理：

CDMA=Cinit+K×CirqCDMA​=Cinit​+K×Cirq​

其中：

- NN：数据项数量；
- KK：中断次数；
- CirqCirq​：单次中断处理开销。

当：

N(Cr+Cw+Ca+Cl)≫Cinit+KCirqN(Cr​+Cw​+Ca​+Cl​)≫Cinit​+KCirq​

DMA 才具有明显收益。

---

## 6.2 示例平台测算

测试假设：

- MCU：Cortex-M7，主频 400 MHz；
- 数据宽度：16 bit；
- ADC 采样率：200 ksample/s；
- DMA 半缓冲：256 samples；
- 每秒半缓冲事件：

fevent=200000256=781.25 次/sfevent​=256200000​=781.25 次/s

假设：

- 一次 DMA ISR：0.8 μs；
- CPU 搬运单个样本：约 12 cycles；
- CPU 处理一次样本：不计入搬运对比。

DMA 中断 CPU 占用：

781.25×0.8μs=625μs/s781.25×0.8μs=625μs/s

CPU 占用率：

0.0625%0.0625%

如果 CPU 逐样本搬运：

200000×12=2.4Mcycles/s200000×12=2.4Mcycles/s

在 400 MHz 下：

2.4M400M=0.6%400M2.4M​=0.6%

实际系统中如果还包括寄存器访问等待、循环分支、总线竞争，则 CPU 占用通常会进一步增加。

---

## 6.3 双缓冲处理预算

双缓冲的关键约束：

Tprocess,max<TbufferTprocess,max​<Tbuffer​

其中：

Tbuffer=NbufferfsampleTbuffer​=fsample​Nbuffer​​

例如：

- 采样率：96 kHz；
- 每个缓冲区：256 samples。

则：

Tbuffer=25696000≈2.667msTbuffer​=96000256​≈2.667ms

CPU 对每个缓冲区的处理时间必须小于 2.667 ms。

考虑系统抖动、Cache Miss、RTOS 调度和高优先级中断，建议保留 20%～40% 裕量：

Tprocess,target≤0.6∼0.8×TbufferTprocess,target​≤0.6∼0.8×Tbuffer​

即：

```
推荐处理预算：1.6～2.1 ms
```

---

## 6.4 缓冲区大小的权衡

缓冲区越小：

- 中断频率越高；
- 延迟越低；
- 单次处理粒度越小；
- CPU 调度压力越大。

缓冲区越大：

- 中断频率越低；
- 吞吐更稳定；
- 端到端延迟增加；
- RAM 占用增大；
- 突发处理时间增加。

中断频率：

firq=fdataNblockfirq​=Nblock​fdata​​

例如数据速率为 1 MB/s：

|缓冲区大小|中断频率|
|---|---|
|64 B|15625 Hz|
|256 B|3906 Hz|
|1024 B|976.6 Hz|
|4096 B|244.1 Hz|

---

## 6.5 总线带宽计算

假设 ADC：

- 采样率：2 Msps；
- 每个样本：16 bit；
- DMA 写入带宽：

B=2M×2B=4MB/sB=2M×2B=4MB/s

若使用 32-bit 总线并采用单次 32-bit 访问，实际总线占用还要考虑：

- 总线事务粒度；
- 地址相位；
- 仲裁间隙；
- FIFO；
- 读写等待；
- 其他主设备占用。

工程上通常按：

Bbus≈Bpayload×(1.2∼2.0)Bbus​≈Bpayload​×(1.2∼2.0)

估算。

对于带 Cache 的 Cortex-A 系统，还需考虑 Cache 回写和失效引起的额外内存流量。

---

## 6.6 性能瓶颈与优化

### 瓶颈 1：中断频率过高

优化方法：

- 增大半缓冲长度；
- 使用 DMA FIFO；
- 使用链式描述符；
- 合并多个数据块后再通知 CPU；
- 降低非必要中断优先级。

### 瓶颈 2：CPU 处理超时

优化方法：

- 使用定点算法；
- 使用 SIMD/DSP 指令；
- 将处理拆分为快速路径和后台路径；
- 增加缓冲区深度；
- 将高耗时处理迁移到协处理器或硬件加速器。

### 瓶颈 3：Cache 抖动

优化方法：

- DMA 缓冲区放入 Non-cacheable SRAM；
- 使用 Cache Line 对齐；
- DMA 前执行 Clean；
- DMA 后执行 Invalidate；
- 避免 DMA 缓冲区与高频 CPU 数据混在同一 Cache Line。

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要连续数据流？
├── 否
│   └── 使用单次 DMA
│
└── 是
    ├── 数据长度固定？
    │   ├── 是
    │   │   ├── CPU 处理时间 < 半缓冲周期？
    │   │   │   ├── 是
    │   │   │   │   ├── 芯片支持硬件双缓冲？
    │   │   │   │   │   ├── 是：使用硬件双缓冲
    │   │   │   │   │   └── 否：使用半传输双缓冲
    │   │   │   │
    │   │   │   └── 否
    │   │   │       ├── 增大缓冲区
    │   │   │       ├── 优化处理算法
    │   │   │       └── 使用多缓冲/队列
    │   │   │
    │   │   └── 否：优先使用环形队列或链式描述符
    │   │
    │   └── 数据不定长
    │       ├── UART：DMA 环形接收 + IDLE/超时检测
    │       ├── Ethernet：描述符环
    │       └── 文件/网络流：多缓冲队列
```

## 7.2 典型场景选型

|场景|需求|推荐方案|理由|
|---|---|---|---|
|ADC 连续采样|固定采样率、固定块长|半传输或硬件双缓冲|时序稳定|
|I2S 音频|连续收发、低延迟|硬件双缓冲|需要严格避免断流|
|UART 接收|不定长数据|环形 DMA + IDLE|不依赖固定帧长|
|SPI 屏幕刷新|大块固定发送|单次 DMA + 双发送缓冲|计算与发送并行|
|Ethernet RX|多帧、异步、高吞吐|描述符环|每个描述符对应独立缓冲|
|SDIO|块设备、大吞吐|多缓冲 + DMA|抵抗介质访问抖动|
|摄像头 DCMI|连续图像流|DMA 双缓冲/链式|帧或行级处理|
|电机控制 ADC|严格周期采样|定时器触发 ADC + DMA|降低采样抖动|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：DMA 只负责搬运，不负责业务协议

DMA 驱动层不应解析：

- 帧头；
- 长度；
- CRC；
- 应用命令；
- 上层协议状态。

DMA 层只负责：

```
配置、启动、停止、状态、错误、缓冲区交付
```

### 原则二：明确缓冲区所有权

任何时刻必须明确：

```
DMA 正在使用？
CPU 正在处理？
缓冲区是否已交付？
是否允许释放？
```

### 原则三：ISR 最小化

ISR 中只做：

1. 读取并清除状态；
2. 识别完成缓冲区；
3. 执行必要的 Cache 维护；
4. 投递事件；
5. 记录错误。

不要在 ISR 中执行：

- FFT；
- 大量数据复制；
- 动态内存分配；
- 阻塞等待；
- 复杂协议解析。

### 原则四：所有 DMA 都必须有错误恢复路径

至少处理：

- 传输错误；
- FIFO 错误；
- 总线错误；
- 地址错误；
- 外设请求丢失；
- 缓冲区溢出；
- 超时无进展。

---

## 8.2 选型决策矩阵

|指标|单缓冲|半传输|硬件双缓冲|环形队列|描述符链|
|---|---|---|---|---|---|
|低延迟|2|4|5|4|4|
|高吞吐|2|4|5|4|5|
|不定长数据|1|1|2|5|5|
|低 RAM|5|4|3|2|1|
|调试难度|5|4|3|3|1|
|硬件依赖|5|4|2|4|1|

评分越高越适合。

---

## 8.3 工业级编码规范

- DMA 缓冲区长度使用无符号类型，并进行乘法溢出检查。
- 地址使用 `uintptr_t` 或芯片推荐的地址类型。
- DMA 中断标志必须先读取、后清除，并验证清除结果。
- 所有 DMA 状态机必须支持 `START、RUNNING、STOPPING、ERROR、RECOVERING`。
- 缓冲区必须进行对齐声明。
- 不在 DMA ISR 中调用不可重入函数。
- 不在 DMA ISR 中调用可能阻塞的 RTOS API。
- 对双缓冲索引、事件位使用原子操作或临界区保护。
- 生产代码必须有 DMA 错误计数器和超时监测。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：CPU 与 DMA 同时访问同一缓冲区

### 错误代码

```
static uint16_t adc_buffer[256];

void process_task(void)
{
    /*
     * DMA 可能仍在写 adc_buffer，
     * CPU 此时直接处理整个数组。
     */
    filter_samples(adc_buffer, 256);
}
```

### 根因

没有建立缓冲区所有权协议，CPU 不知道 DMA 当前写入位置。

### 正确实现

```
void dma_half_complete_callback(void)
{
    processing_queue_push(&adc_buffer[0], 128);
}

void dma_complete_callback(void)
{
    processing_queue_push(&adc_buffer[128], 128);
}
```

CPU 只处理已完成区域。

### 风险影响

- 数据撕裂；
- 样本前后半段属于不同采样周期；
- FFT、控制算法产生随机异常；
- 问题难以复现。

---

## 9.2 错误二：忽略 D-Cache 一致性

### 错误代码

```
static uint8_t rx_buffer[1024];

/* DMA 完成后直接读取 */
void rx_done_callback(void)
{
    parse_packet(rx_buffer, sizeof(rx_buffer));
}
```

### 根因

CPU 可能从 Cache 读取旧数据，而 DMA 已经更新了 SRAM。

### 正确实现

```
#define CACHE_LINE_SIZE 32U

static uint8_t rx_buffer[1024]
    __attribute__((aligned(CACHE_LINE_SIZE)));

void rx_done_callback(void)
{
    cache_invalidate_by_addr(rx_buffer, sizeof(rx_buffer));
    __DSB();

    parse_packet(rx_buffer, sizeof(rx_buffer));
}
```

对于内存到外设发送：

```
void tx_start(const uint8_t *data, size_t len)
{
    cache_clean_by_addr(data, len);
    __DSB();

    dma_start_mem_to_periph(data, len);
}
```

### 风险影响

- 偶发读取旧数据；
- 低负载时正常，高负载时异常；
- 不同编译优化等级表现不同；
- 仅在开启 Cache 的芯片上出现。

---

## 9.3 错误三：DMA 数据宽度和外设宽度不匹配

### 错误代码

```
/*
 * ADC 数据寄存器为 16 bit，
 * DMA 却按 8 bit 访问。
 */
dma_set_peripheral_width(DMA_DATA_8BIT);
dma_set_memory_width(DMA_DATA_16BIT);
```

### 根因

没有根据外设寄存器定义和数据对齐方式配置 DMA。

### 正确实现

```
dma_set_peripheral_width(DMA_DATA_16BIT);
dma_set_memory_width(DMA_DATA_16BIT);
```

如果硬件明确要求 32-bit 访问，则内存端也应根据手册配置，并处理高低位布局。

### 风险影响

- 数据截断；
- 样本错位；
- DMA 计数与实际字节数不一致；
- 总线访问异常。

---

## 9.4 错误四：处理时间超过缓冲周期

### 错误代码

```
void process_block(uint16_t *buf)
{
    expensive_algorithm(buf, 1024);  /* 耗时 8 ms */
}
```

假设 DMA 每 4 ms 覆盖一次同一缓冲区，则必然发生数据覆盖。

### 根因

没有进行最坏执行时间分析，只测量了平均耗时。

### 正确实现

```
#define BUFFER_SAMPLES 1024U
#define SAMPLE_RATE    250000U

/*
 * 缓冲周期：
 * 1024 / 250000 = 4.096 ms
 *
 * 设计要求：
 * WCET <= 0.7 * 4.096 ms = 2.867 ms
 */
```

解决办法：

- 增加缓冲区；
- 分块处理；
- 优化算法；
- 使用多缓冲；
- 降低采样率；
- 将处理迁移到硬件加速器。

### 风险影响

- 缓冲区覆盖；
- 丢样本；
- 输出波形断裂；
- 控制系统出现不稳定。

---

## 9.5 错误五：错误清除顺序不正确

### 错误代码

```
void dma_irq_handler(void)
{
    dma_clear_all_flags();

    if (dma_get_status() & DMA_FLAG_TRANSFER_ERROR) {
        handle_error();
    }
}
```

### 根因

先清除状态，再读取状态，导致错误信息被抹掉。

### 正确实现

```
void dma_irq_handler(void)
{
    uint32_t status = dma_get_status();

    dma_clear_flags(status);

    if ((status & DMA_FLAG_TRANSFER_ERROR) != 0U) {
        dma_error_count++;
        dma_enter_recovery();
    }

    if ((status & DMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        dma_complete_event();
    }
}
```

### 风险影响

- 错误无法统计；
- 故障恢复路径不执行；
- DMA 进入静默停止状态。

---

# 10. 多机制组合使用方案

## 10.1 DMA 双缓冲 + RTOS 队列

推荐架构：

```
ADC/外设
   │
   ▼
DMA 双缓冲
   │ ISR
   ▼
缓冲区事件队列
   │
   ▼
处理任务
   │
   ├── 算法处理
   ├── 数据校验
   └── 下游队列
```

### 数据结构

```
typedef struct {
    uint16_t *data;
    size_t length;
    uint8_t index;
    uint32_t sequence;
} dma_block_event_t;

static QueueHandle_t dma_event_queue;
```

### DMA 回调

```
static uint32_t block_sequence;

void dma_buffer_complete_isr(uint8_t index)
{
    BaseType_t higher_priority_woken = pdFALSE;

    dma_block_event_t event = {
        .data = adc_buffers[index],
        .length = ADC_BLOCK_SAMPLES,
        .index = index,
        .sequence = block_sequence++
    };

    /*
     * ISR 中只投递事件，不执行算法。
     */
    xQueueSendFromISR(dma_event_queue,
                      &event,
                      &higher_priority_woken);

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

### 处理任务

```
static void adc_processing_task(void *argument)
{
    dma_block_event_t event;

    for (;;) {
        if (xQueueReceive(dma_event_queue,
                          &event,
                          portMAX_DELAY) == pdPASS) {
            cache_invalidate_by_addr(event.data,
                                     event.length * sizeof(uint16_t));
            __DSB();

            adc_algorithm_process(event.data,
                                  event.length);
        }
    }
}
```

### 工程注意事项

- 队列长度至少覆盖最大调度抖动；
- 事件中携带序号，便于检测丢块；
- 不建议在队列中复制整个数据块，只传递指针；
- 指针指向的缓冲区在处理完成前不得重新交给 DMA；
- 若只有两个缓冲区，处理任务必须严格满足时限。

---

## 10.2 DMA 双缓冲 + 环形队列

当处理任务可能短时间阻塞时，两个缓冲区可能不够。可以设计：

```
DMA -> Buffer[0] -> Queue -> Processing
    -> Buffer[1] -> Queue -> Processing
    -> Buffer[2] -> Queue -> Processing
    -> Buffer[3] -> Queue -> Processing
```

这属于多缓冲池：

```
#define BUFFER_COUNT 4U

typedef struct {
    uint8_t *addr;
    size_t capacity;
    size_t length;
    bool in_use;
} buffer_node_t;
```

相比双缓冲，多缓冲可以提高抗抖动能力，但不能无限解决处理能力不足的问题：

长期平均处理速率≥数据产生速率长期平均处理速率≥数据产生速率

否则缓冲区最终仍会耗尽。

---

## 10.3 DMA + Cache + 内存屏障组合

### 外设接收路径

```
DMA 写 SRAM
    │
    ▼
DMA 完成
    │
    ▼
Invalidate D-Cache
    │
    ▼
DSB
    │
    ▼
CPU 读取数据
```

### 外设发送路径

```
CPU 写 Cache
    │
    ▼
Clean D-Cache
    │
    ▼
DSB
    │
    ▼
DMA 读取 SRAM
```

关键规则：

```
DMA 写内存 -> CPU 读内存：Invalidate
CPU 写内存 -> DMA 读内存：Clean
```

---

# 11. 工业级实际案例分析

## 11.1 案例一：ADC 电机电流采样

### 需求

- PWM 同步触发 ADC；
- 采样率：100 kHz；
- 每 128 个样本进行一次电流环计算；
- 采样不可丢失；
- 控制计算必须在下一个采样块到来前完成。

### 架构

```
PWM 定时器
    │ TRGO
    ▼
ADC
    │ DMA Request
    ▼
DMA 双缓冲
    │
    ├── Buffer 0
    └── Buffer 1
         │
         ▼
电流环处理任务
```

### 核心代码

```
#define CURRENT_BLOCK_SIZE 128U
#define CURRENT_SAMPLE_HZ  100000U

static int16_t current_buffer[2][CURRENT_BLOCK_SIZE]
    __attribute__((aligned(32)));

static volatile uint32_t current_block_seq;

void current_dma_init(void)
{
    dma_config_t config = {
        .direction       = DMA_DIR_PERIPH_TO_MEM,
        .periph_addr     = ADC_DATA_REGISTER,
        .mem0_addr       = (uintptr_t)&current_buffer[0][0],
        .mem1_addr       = (uintptr_t)&current_buffer[1][0],
        .transfer_count  = CURRENT_BLOCK_SIZE,
        .periph_width    = DMA_DATA_16BIT,
        .mem_width       = DMA_DATA_16BIT,
        .periph_inc      = false,
        .mem_inc         = true,
        .circular        = true,
        .double_buffer   = true,
        .priority        = 7U
    };

    dma_init(&config);
    dma_enable_interrupt(DMA_INT_TRANSFER_COMPLETE |
                         DMA_INT_TRANSFER_ERROR);
    dma_start();
}

void current_dma_complete_isr(void)
{
    uint8_t completed = dma_get_current_target() == DMA_TARGET_M1
                      ? 0U
                      : 1U;

    cache_invalidate_by_addr(current_buffer[completed],
                             sizeof(current_buffer[completed]));
    __DSB();

    current_control_submit(current_buffer[completed],
                            CURRENT_BLOCK_SIZE,
                            current_block_seq++);
}
```

### 设计要点

- 采样由硬件定时器触发，避免软件触发抖动；
- DMA 只填充缓冲区，不在 ISR 中执行控制算法；
- 采用序号检测丢块；
- 电流控制任务优先级高于普通通信任务；
- 对 DMA 错误执行停止 ADC、复位 DMA、清空状态、重新启动。

---

## 11.2 案例二：I2S 音频双缓冲

### 需求

- 48 kHz；
- 双声道；
- 24-bit 音频；
- 每块 128 帧；
- 需要实时执行 EQ、限幅和音量控制；
- 不能出现音频断流。

### 缓冲区大小

每帧：

```
2 个声道 × 4 字节存储 = 8 字节
```

每个缓冲区：

128×8=1024Bytes128×8=1024Bytes

缓冲周期：

128/48000=2.667ms128/48000=2.667ms

设计要求：

```
音频处理 WCET < 1.8 ms
```

### 处理框架

```
#define AUDIO_FRAMES_PER_BLOCK 128U
#define AUDIO_CHANNELS         2U
#define AUDIO_WORD_BYTES       4U

static int32_t audio_buf[2][AUDIO_FRAMES_PER_BLOCK]
                         [AUDIO_CHANNELS]
    __attribute__((aligned(32)));

void audio_process_block(uint8_t index)
{
    int32_t (*block)[AUDIO_CHANNELS] = audio_buf[index];

    audio_eq_process(block, AUDIO_FRAMES_PER_BLOCK);
    audio_limiter_process(block, AUDIO_FRAMES_PER_BLOCK);
    audio_gain_process(block, AUDIO_FRAMES_PER_BLOCK);
}
```

### 设计要点

- 音频处理采用固定执行时间路径；
- 禁止在实时音频任务中动态分配内存；
- 双缓冲切换必须基于 DMA 当前目标状态；
- 输出 DMA 和输入 DMA 可以使用独立双缓冲；
- 处理超时需统计 XRUN 次数；
- 必须提供静音或旧数据重播的降级策略。

---

## 11.3 案例三：UART DMA 环形接收 + IDLE 检测

### 需求

- UART 波特率：3 Mbps；
- 帧长度不固定；
- 需要降低逐字节中断；
- 支持连续帧接收。

### 架构

```
UART RX
   │
   ▼
DMA Circular Buffer
   │
   ├── 半传输事件
   ├── 全传输事件
   └── IDLE 事件
         │
         ▼
软件读取指针
         │
         ▼
协议解析器
```

### 关键逻辑

```
#define UART_RX_DMA_SIZE 1024U

static uint8_t uart_rx_dma[UART_RX_DMA_SIZE]
    __attribute__((aligned(32)));

static size_t uart_read_pos;

static size_t uart_dma_get_write_pos(void)
{
    size_t remaining = dma_get_remaining_count();

    return (UART_RX_DMA_SIZE - remaining) %
           UART_RX_DMA_SIZE;
}

void uart_rx_poll(void)
{
    size_t write_pos = uart_dma_get_write_pos();

    while (uart_read_pos != write_pos) {
        uint8_t byte = uart_rx_dma[uart_read_pos];

        protocol_input_byte(byte);

        uart_read_pos++;
        if (uart_read_pos >= UART_RX_DMA_SIZE) {
            uart_read_pos = 0U;
        }
    }
}
```

### 设计要点

- DMA 保持循环运行；
- CPU 通过当前剩余计数计算写指针；
- IDLE 中断只表示一段时间没有新字节，不代表完整协议帧；
- 软件必须处理写指针追上读指针的溢出情况；
- 高吞吐场景下需要记录 overrun 次数。

---

# 12. 高频问题深度答疑

## 12.1 DMA 双缓冲是否一定比环形缓冲更好？

不一定。

双缓冲适合：

- 固定块长；
- 稳定采样率；
- CPU 以块为单位处理；
- 严格低延迟场景。

环形缓冲适合：

- 不定长数据；
- UART、网络等异步输入；
- 数据到达速度有抖动；
- 上层消费粒度不固定。

如果数据块固定且处理时间可预测，双缓冲通常更简单、更高效。

---

## 12.2 为什么 DMA 已完成，但 CPU 仍读到旧数据？

最常见原因是 D-Cache。

DMA 直接写 SRAM，CPU 可能仍然读取 Cache 中旧 Cache Line。必须在 DMA 完成后对对应地址执行 Cache Invalidate。

反方向同理：

```
CPU 写 Cache，但 DMA 读取 SRAM
```

此时必须先 Clean Cache，否则 DMA 看到的可能是旧内存内容。

---

## 12.3 `volatile` 能否解决 DMA 数据一致性？

不能。

`volatile` 只约束编译器：

- 不要删除访问；
- 不要随意合并访问；
- 每次都从抽象内存读取或写入。

它不能保证：

- Cache 一致性；
- 总线完成顺序；
- 多线程原子性；
- DMA 与 CPU 的所有权；
- 缓冲区不会被覆盖。

因此 `volatile` 不是 DMA 同步机制的替代品。

---

## 12.4 为什么双缓冲仍然会丢数据？

双缓冲只能提供一个缓冲周期的处理窗口。

如果：

Tprocess>TbufferTprocess​>Tbuffer​

则 CPU 处理尚未完成时，DMA 已经需要重新使用该缓冲区。

此外还有以下原因：

- DMA 中断优先级过低；
- RTOS 任务被高优先级任务长期抢占；
- Cache 维护耗时；
- 总线被 LCD、GPU、Ethernet 等主设备占用；
- DMA 请求频率超过控制器能力；
- 处理任务发生阻塞。

---

## 12.5 DMA 中断应该放在什么优先级？

原则不是“越高越好”。

应综合考虑：

```
DMA 数据丢失风险
外设实时性
ISR 执行时间
系统最高优先级中断
RTOS 临界区限制
```

通常：

- 电机控制采样 DMA：高优先级；
- 音频流 DMA：中高优先级；
- UART 大块接收 DMA：中优先级；
- 内存复制 DMA：低优先级。

ISR 本身必须足够短，否则高优先级 DMA 反而会破坏整个系统实时性。

---

## 12.6 双缓冲是否需要互斥锁？

在 ISR 与单个处理任务之间，通常不推荐使用普通互斥锁。

更适合的方式：

- ISR 安全队列；
- 事件组；
- 原子状态；
- 临界区；
- 缓冲区所有权转移。

互斥锁可能带来：

- 优先级反转；
- ISR 不可调用；
- 不确定阻塞时间；
- 死锁风险。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **DMA 的本质是将数据搬运从 CPU 指令路径转移到硬件总线路径。**
2. **双缓冲的本质是 DMA 与 CPU 同时工作在不同缓冲区上。**
3. **任何双缓冲设计都必须满足：CPU 处理时间小于缓冲周期。**
4. **Cache 一致性是带 Cache MCU/Linux SoC 上 DMA 的第一类问题。**
5. **DMA ISR 应只完成状态确认、缓冲区交付和事件通知。**
6. **双缓冲不是无限吞吐方案，长期平均处理速率必须不低于数据产生速率。**
7. **固定块长优先使用双缓冲，不定长流数据优先使用环形 DMA。**
8. **所有工业级 DMA 都必须具备超时、错误统计和恢复机制。**

## 13.2 性能排序

在固定长度连续数据场景中，通常性能从高到低为：

```
硬件双缓冲
    >
DMA 半传输
    >
DMA 环形缓冲
    >
软件重启 DMA
    >
CPU 逐项搬运
```

但如果考虑灵活性：

```
链式描述符
    >
软件环形队列
    >
硬件双缓冲
    >
半传输缓冲
    >
单缓冲
```

## 13.3 通用选型结论

|需求|推荐方案|
|---|---|
|一次性大块搬运|单次 DMA|
|连续固定采样|硬件双缓冲|
|芯片无双缓冲但支持 HT|半传输双缓冲|
|UART 不定长接收|环形 DMA + IDLE|
|高吞吐网络|描述符环|
|处理时间抖动较大|多缓冲队列|
|强 Cache 系统|Non-cacheable DMA 区或严格 Cache 维护|

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|DMA 模式|关键注意点|
|---|---|---|
|ADC 连续采样|双缓冲/半传输|采样周期、处理 WCET|
|I2S 音频|双缓冲|低延迟、XRUN|
|UART 接收|环形 DMA|写指针、IDLE、溢出|
|SPI 接收|双缓冲|CS 时序、帧边界|
|SPI 发送|单次/双发送缓冲|发送缓存不能提前修改|
|Ethernet|描述符环|Cache、所有权位|
|LCD 刷屏|内存到外设 DMA|Cache Clean、总线竞争|
|摄像头|多缓冲/链式 DMA|帧同步、带宽|

## 14.2 特性对比表

|特性|单缓冲|半传输|双缓冲|环形队列|
|---|---|---|---|---|
|连续性|低|高|高|高|
|延迟|高|中低|中低|可调|
|固定块适应性|高|高|高|中|
|不定长适应性|低|低|中|高|
|RAM 占用|低|低|中|高|
|调试难度|低|中|中|高|
|适合工业连续流|一般|好|最好|好|

---

# 15. 学习效果自检

完成本课后，应能够回答并实践以下问题：

## DMA 基础

- [ ]  能解释外设请求如何触发 DMA 传输。
- [ ]  能区分外设地址固定和内存地址递增。
- [ ]  能说明传输宽度与实际字节数的关系。
- [ ]  能解释 DMA 传输完成和半传输事件。

## 双缓冲设计

- [ ]  能画出 Ping-Pong 缓冲时序图。
- [ ]  能根据 DMA 当前目标判断已经完成的缓冲区。
- [ ]  能计算缓冲周期和 CPU 最大处理时间。
- [ ]  能设计缓冲区所有权状态机。
- [ ]  能处理双缓冲溢出和丢块检测。

## Cache 与一致性

- [ ]  能判断何时需要 Cache Clean。
- [ ]  能判断何时需要 Cache Invalidate。
- [ ]  能解释为什么 `volatile` 不能解决 Cache 问题。
- [ ]  能处理 Cache Line 对齐和地址范围问题。

## 工业级能力

- [ ]  能设计 DMA 错误恢复流程。
- [ ]  能实现 DMA 超时检测。
- [ ]  能统计 DMA 丢块、覆盖、FIFO 错误次数。
- [ ]  能用示波器或 DWT 测量 DMA 处理预算。
- [ ]  能在 RTOS 中实现 ISR 到处理任务的无拷贝数据交付。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：单次 DMA 内存复制

要求：

- 实现内存到内存 DMA；
- 校验源和目标数据；
- 测量 CPU memcpy 与 DMA memcpy 的速度；
- 统计不同数据长度下的收益拐点。

### 任务二：ADC 半传输采集

要求：

- 使用定时器触发 ADC；
- DMA 循环接收；
- 半传输和全传输分别处理；
- 使用 GPIO 翻转测量 ISR 延迟；
- 人为增加处理延迟，验证数据覆盖条件。

### 任务三：硬件双缓冲采集

要求：

- 配置 M0/M1 双缓冲；
- 读取当前目标位；
- 记录完成缓冲区序号；
- 检测是否存在丢块；
- 增加 DMA 错误恢复。

### 任务四：带 Cache 的双缓冲

要求：

- 将缓冲区放入 Cacheable SRAM；
- 故意去掉 Cache Invalidate，观察旧数据；
- 恢复 Cache 维护逻辑；
- 比较 Cacheable 和 Non-cacheable 区域性能。

### 任务五：DMA + RTOS 流水线

要求：

```
DMA ISR
  -> 事件队列
  -> 处理任务
  -> 输出任务
```

验证：

- 处理任务被抢占时的缓冲稳定性；
- 队列长度对丢块率的影响；
- 高低优先级任务对实时性的影响；
- 处理 WCET 超限后的故障表现。

---

## 16.2 性能测试方法

### 方法一：GPIO 时间测量

```
void process_block_wrapper(uint16_t *data, size_t count)
{
    GPIO_SET(PROCESS_MARKER);

    process_block(data, count);

    GPIO_CLEAR(PROCESS_MARKER);
}
```

使用示波器测量：

```
高电平宽度 = 实际处理时间
相邻脉冲间隔 = 缓冲周期
```

### 方法二：DWT 周期计数

```
uint32_t start = DWT->CYCCNT;

process_block(data, count);

uint32_t cycles = DWT->CYCCNT - start;
```

处理时间：

T=cyclesfcpuT=fcpu​cycles​

### 方法三：统计最坏执行时间

不要只统计平均值，应记录：

- 最小值；
- 平均值；
- 99% 分位；
- 99.9% 分位；
- 最大值；
- 中断嵌套情况下的最大值。

### 方法四：故障注入

主动注入：

- 增大处理耗时；
- 禁止 Cache 维护；
- 降低 DMA 中断优先级；
- 提高其他总线主设备负载；
- 暂停处理任务；
- 修改 DMA 地址为非法区域。

验证系统是否能够：

- 检测故障；
- 记录故障；
- 停止异常 DMA；
- 重新初始化；
- 恢复正常数据流。

---

## 16.3 进阶学习方向

### 方向一：DMA 描述符与 Scatter-Gather

适合：

- Ethernet；
- SDIO；
- 摄像头；
- PCIe；
- 高吞吐存储。

重点学习：

- 描述符所有权；
- 环形描述符；
- 链接描述符；
- 中断合并；
- Cache 一致性；
- 零拷贝。

### 方向二：总线矩阵与 QoS

重点分析：

- AXI/AHB 仲裁；
- DMA 与 CPU 的竞争；
- 突发长度；
- FIFO 深度；
- QoS 优先级；
- 实时数据流的带宽预留。

### 方向三：Cache、MPU 与 DMA 内存规划

学习：

- Non-cacheable 区；
- Write-through / Write-back；
- Cache Line 对齐；
- MPU 属性；
- 内存屏障；
- DMA Buffer 专用内存池。

### 方向四：实时系统数据流架构

进一步构建：

```
采集 DMA
   ▼
多缓冲池
   ▼
无拷贝消息队列
   ▼
实时算法
   ▼
输出 DMA
```

最终目标是实现：

- **零拷贝**；
- **有界延迟**；
- **可测量 WCET**；
- **可恢复错误状态**；
- **可追踪数据序号**；
- **可量化系统吞吐能力**。