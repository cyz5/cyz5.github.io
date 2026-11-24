
## 1. 学习目标

### 理解

- 理解数字音频采样、量化、时钟树和帧结构之间的关系。
- 理解 I2S、SAI、PDM、TDM 四类接口的物理层、时序和数据组织方式。
- 理解音频接口中 `MCLK`、`BCLK/SCK`、`LRCLK/FS`、`SD`、`CLK`、`WS` 等信号的职责。
- 理解 DMA、FIFO、Cache、一致性和实时性对音频连续性的影响。

### 掌握

- 掌握 I2S 主从模式、左右声道时序、数据位宽与槽位宽配置。
- 掌握 SAI 的双子块、异步时钟、同步模式、TDM 槽位和协议配置。
- 掌握 PDM 麦克风的时钟驱动、PDM 到 PCM 的抽取和滤波。
- 掌握 DMA 双缓冲、环形缓冲、半传输回调和欠载/溢出处理。
- 掌握音频接口驱动的启动、停止、错误恢复和资源释放流程。

### 精通

- 能定位以下工业现场问题：
    - 左右声道交换；
    - 采样率偏差；
    - 声道错位；
    - 16 位数据被当成 24 位发送；
    - DMA 运行但没有音频输出；
    - Cache 导致播放数据不更新；
    - PDM 抽取后音频频谱异常；
    - TDM 槽位映射错误；
    - DMA 欠载导致噪声或爆音。
- 能根据 codec、功放、麦克风阵列和 MCU 外设能力选择接口方案。
- 能建立音频接口的时钟、数据、DMA 和缓冲区完整验证链路。

### 能够设计

- 设计支持播放、录音、全双工和多声道的音频驱动架构。
- 设计 8 kHz、16 kHz、44.1 kHz、48 kHz、96 kHz 等多种采样率配置。
- 设计面向 RTOS 的音频流服务，包括任务、消息队列、DMA 回调和错误恢复。
- 设计 2/4/8/16 声道 TDM 音频系统和多麦克风 PDM 采集系统。

---

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、位操作、内存模型和 `volatile`。
- MCU 时钟树、复用功能、GPIO、电源和复位控制。
- DMA 基本工作方式：外设到内存、内存到外设、循环模式、双缓冲。
- RTOS 任务、队列、信号量、中断优先级和临界区。
- 数字信号处理基础：
    - 采样定理；
    - PCM；
    - 量化位宽；
    - FIR/IIR；
    - 抽取和插值；
    - 通带、阻带和混叠。
- Cache、内存屏障和 DMA 一致性。

### 技能要求

- 能阅读 MCU Reference Manual 中的音频外设章节。
- 能使用逻辑分析仪或示波器观察 `BCLK`、`FS`、`SD`。
- 能用 Python、MATLAB、Audacity 或 Sigrok 分析 WAV 和原始 PCM。
- 能编写 DMA 驱动、中断服务函数和硬件抽象层。
- 能通过寄存器读回确认外设实际工作状态。

---

## 3. 技术概述

数字音频接口解决的是三个问题：

1. **什么时候采样或发送一个数据位**；
2. **一个采样帧从哪里开始、在哪里结束**；
3. **每个声道的数据位于哪个槽位**。

典型 PCM 音频链路如下：

```
麦克风/线路输入
    │
    ├── PDM 麦克风：1-bit 高速脉冲流
    │       │
    │       └── PDM 解调/抽取 ── PCM
    │
    └── 模拟 Codec ── ADC ── PCM
                            │
                            ├── I2S
                            ├── SAI
                            └── TDM
                                    │
                                  DMA
                                    │
                              应用/算法/存储
```

### 3.1 I2S

I2S 是最常见的串行 PCM 音频接口，通常包含：

- `SCK/BCLK`：位时钟；
- `WS/LRCLK`：字选择或左右声道帧同步；
- `SD`：串行数据；
- `MCLK`：可选主时钟，常用于 Codec 内部 PLL 或过采样系统。

经典 I2S 模式中，`WS` 翻转后，数据通常延迟一个 `BCLK` 周期输出。这一点与左对齐格式不同。

### 3.2 SAI

SAI，即 Serial Audio Interface，通常是 MCU 对 I2S 的增强实现，常见能力包括：

- 独立配置多个子块；
- 主/从时钟；
- 异步或同步子块；
- I2S、左对齐、右对齐、PCM、AC’97 等协议；
- TDM 多槽位；
- FIFO 阈值；
- 多种数据位宽和槽位宽；
- 全双工或独立收发通道。

SAI 不是一种单一协议，而是一个可配置的音频串行外设。

### 3.3 PDM

PDM，Pulse Density Modulation，是单比特高速脉冲密度编码：

- `1` 的密度表示模拟信号幅度较高；
- `0` 的密度表示模拟信号幅度较低；
- 典型 PDM 时钟为 1 MHz 到 4 MHz；
- 经过低通滤波和抽取后得到 PCM。

例如：

```
PDM clock = 3.072 MHz
decimation = 64
PCM sample rate = 3.072 MHz / 64 = 48 kHz
```

PDM 不能直接当作 PCM 读取。必须进行滤波和抽取。

### 3.4 TDM

TDM，Time Division Multiplexing，在一个音频帧内划分多个时隙：

```
Frame:
| Slot 0 | Slot 1 | Slot 2 | Slot 3 | ... |
```

TDM 常用于：

- 多通道 ADC；
- 多麦克风阵列；
- 多通道功放；
- 汽车音频；
- 专业音频设备；
- 多个 Codec 共享一条串行数据线。

---

## 4. 核心特性横向对比

|维度|I2S|SAI|PDM|TDM|
|---|---|---|---|---|
|主要数据形式|多位 PCM|多位 PCM|1-bit 密度流|多槽位 PCM|
|常见声道数|2|2 或多通道|通常 1/2 路复用|4/8/16/32|
|典型时钟|BCLK、WS、MCLK|多时钟可配置|PDM CLK|BCLK、FS、MCLK|
|单帧结构|左右声道|可自定义|无 PCM 帧概念|多个 Slot|
|硬件复杂度|低|中高|中，依赖抽取器|中高|
|典型采样率|8~192 kHz|8~384 kHz，取决于 MCU|16~48 kHz 常见|8~192 kHz|
|DMA 需求|高|高|高|高|
|带宽计算|`Fs × 2 × slot_width`|`Fs × slots × slot_width`|`PDM_CLK`|`Fs × slot_count × slot_width`|
|主要风险|WS 偏移、位宽错误|配置复杂、同步错误|抽取滤波、时钟比|槽位映射、帧长|
|适用场景|普通立体声|高性能音频子系统|数字麦克风|多通道音频|
|CPU 压力|DMA 后较低|DMA 后较低|软件抽取时较高|DMA 后较低|
|硬件 BOM|低|低|可取消模拟 Codec|低于多路独立 I2S|

### 4.1 时钟带宽公式

对于 PCM 串行接口：

```
BCLK = Fs × SlotCount × SlotWidth
```

例如：

```
Fs         = 48 kHz
SlotCount  = 2
SlotWidth  = 32 bit

BCLK = 48000 × 2 × 32
     = 3.072 MHz
```

如果是 8 槽位 TDM：

```
BCLK = 48000 × 8 × 32
     = 12.288 MHz
```

PDM 的关系通常为：

```
Fs_PCM = FCLK_PDM / Decimation
```

---

## 5. 底层原理与功能特性深度解析

### 5.1 PCM 样本、槽位和内存布局

以 24 位有效数据、32 位槽位为例，通常有两种内存布局：

```
方式 A：每个样本占 32 bit
L0, R0, L1, R1, ...
```

或者：

```
方式 B：3 字节紧凑布局
L0[23:16], L0[15:8], L0[7:0], ...
```

实际 MCU 音频外设通常更适合方式 A，因为：

- DMA 对齐简单；
- FIFO 数据宽度固定；
- CPU 处理方便；
- Cache line 对齐容易；
- 不需要在每个样本上进行字节拼接。

### 5.2 I2S 关键时序

经典 I2S 的核心时序：

```
WS:  ___----____----____
        L       R

SD:      [L sample] [R sample]
         ^
         WS 翻转后延迟一个 BCLK
```

常见错误是将 I2S 配置为左对齐：

```
左对齐：WS 翻转后立即发送 MSB
I2S：   WS 翻转后延迟一个 BCLK 再发送 MSB
```

两种协议在示波器上波形相近，但数据会整体错一位或产生严重失真。

### 5.3 SAI 双子块和同步关系

许多 MCU 的 SAI 包含 Block A 和 Block B：

```
SAI Block A: 主块，可产生或接收时钟
SAI Block B: 从块，可同步 Block A
```

典型全双工结构：

```
Block A TX ── 播放
Block B RX ── 录音
```

或者：

```
Block A 产生 BCLK/FS
Block B 使用 Block A 的同步时钟
```

同步模式下，必须明确：

- 谁产生 `BCLK`；
- 谁产生 `FS`；
- 同步块是否允许独立启动；
- 两个 DMA 的启动顺序；
- 首帧是否会丢失。

### 5.4 DMA 环形缓冲模型

音频 DMA 不应只使用一个小缓冲区并在每次完成后重新启动。推荐采用双半缓冲：

```
+-------------------+-------------------+
| Half 0            | Half 1            |
| DMA 正在处理      | CPU/算法正在处理  |
+-------------------+-------------------+
          ↑
      半传输中断
```

通用抽象：

```
typedef struct {
    uint32_t *buffer;
    size_t frame_count;
    size_t channels;
    size_t half_frames;
    volatile uint32_t overrun_count;
    volatile uint32_t underrun_count;
} audio_stream_t;
```

DMA 回调只做两件事：

1. 记录哪个半区完成；
2. 向音频任务发送事件。

不要在中断中执行：

- 编解码；
- 文件系统写入；
- 浮点 FFT；
- 大规模内存复制；
- 阻塞等待。

```
typedef enum {
    AUDIO_DMA_HALF = 0,
    AUDIO_DMA_FULL,
    AUDIO_DMA_ERROR
} audio_dma_event_t;

static void audio_dma_callback(audio_dma_event_t event)
{
    BaseType_t higher_priority_woken = pdFALSE;

    if (event == AUDIO_DMA_HALF) {
        xQueueSendFromISR(g_audio_queue,
                          &(audio_dma_event_t){ AUDIO_DMA_HALF },
                          &higher_priority_woken);
    } else if (event == AUDIO_DMA_FULL) {
        xQueueSendFromISR(g_audio_queue,
                          &(audio_dma_event_t){ AUDIO_DMA_FULL },
                          &higher_priority_woken);
    } else {
        g_audio_error = true;
    }

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

### 5.5 Cache 一致性

DMA 写内存、CPU 读内存时，CPU 可能读取旧 Cache 数据。

DMA 接收完成后：

```
void audio_rx_half_complete(void)
{
    uintptr_t addr = (uintptr_t)&g_rx_buffer[0];

    addr = addr & ~(CACHE_LINE_SIZE - 1U);

    SCB_InvalidateDCache_by_Addr(
        (uint32_t *)addr,
        CACHE_ALIGN(sizeof(g_rx_buffer) / 2U)
    );
}
```

DMA 发送前，CPU 写完数据后：

```
void audio_tx_prepare(const void *buffer, size_t size)
{
    SCB_CleanDCache_by_Addr(
        (uint32_t *)CACHE_ALIGN_DOWN((uintptr_t)buffer),
        CACHE_ALIGN(size)
    );
}
```

工程上更推荐：

- 音频 DMA 缓冲区放在 Non-cacheable SRAM；
- 或严格使用 Cache Clean/Invalidate；
- 缓冲区起始地址和长度按 Cache line 对齐；
- 禁止 DMA 缓冲区与普通业务数据共享 Cache line。

### 5.6 PDM 到 PCM

PDM 解码包含：

```
PDM bitstream
    │
    ├── 低通 FIR/CIC
    ├── 抽取 Decimation
    ├── 增益补偿
    └── PCM 输出
```

理想情况下：

```
PDM_CLK = Fs × OSR
```

其中 `OSR` 是过采样率。

简单的 CIC 抽取器结构：

```
typedef struct {
    int64_t integrator[3];
    int64_t comb_delay[3];
    uint32_t decimation;
    uint32_t phase;
} cic3_decimator_t;

static int32_t cic3_process_bit(cic3_decimator_t *s, uint8_t bit)
{
    int32_t x = bit ? 1 : -1;
    int64_t y;

    s->integrator[0] += x;
    s->integrator[1] += s->integrator[0];
    s->integrator[2] += s->integrator[1];

    s->phase++;
    if (s->phase < s->decimation) {
        return 0;
    }

    s->phase = 0;

    y = s->integrator[2];

    for (size_t i = 0; i < 3; ++i) {
        int64_t diff = y - s->comb_delay[i];
        s->comb_delay[i] = y;
        y = diff;
    }

    return (int32_t)y;
}
```

生产系统中通常使用：

- MCU 硬件 PDM2PCM；
- CMSIS-DSP；
- 厂商提供的 PDM Filter；
- 专门的数字麦克风驱动库。

上述 CIC 代码用于说明结构，实际使用时必须增加：

- 位打包输入；
- 增益归一化；
- 溢出边界分析；
- 通带补偿 FIR；
- 低频 DC 阻塞；
- 多麦克风左右边沿选择。

### 5.7 TDM 槽位配置

假设 8 槽位、32 位槽宽、24 位有效数据：

```
Slot 0: Mic 0
Slot 1: Mic 1
Slot 2: Mic 2
Slot 3: Mic 3
Slot 4: Reserved
Slot 5: Reserved
Slot 6: Playback L
Slot 7: Playback R
```

配置时必须区分：

- 有效数据宽度：24 bit；
- 槽位宽度：32 bit；
- 每帧槽位数量：8；
- 活跃槽位掩码；
- FS 脉冲宽度；
- FS 极性；
- MSB/LSB first；
- 数据在槽位中的偏移。

DMA 内存中一般为：

```
slot0, slot1, slot2, slot3, slot4, slot5, slot6, slot7,
slot0, slot1, ...
```

不能直接假设“声道连续”。TDM 的通道抽取应显式实现：

```
static void tdm_extract_channel(const int32_t *tdm,
                                int32_t *pcm,
                                size_t frames,
                                size_t slots,
                                size_t channel_slot)
{
    for (size_t frame = 0; frame < frames; ++frame) {
        pcm[frame] = tdm[frame * slots + channel_slot];
    }
}
```

---

## 6. 性能量化分析

以下数据为典型 Cortex-M7 @ 480 MHz、D-Cache 开启、DMA 搬运、编译器 `-O2` 条件下的工程参考值。实际数据必须在目标板上重新测量。

### 6.1 带宽计算

立体声 48 kHz、32 位槽位：

```
48,000 × 2 × 32 = 3.072 Mbit/s
```

8 通道 TDM：

```
48,000 × 8 × 32 = 12.288 Mbit/s
```

16 通道 TDM：

```
48,000 × 16 × 32 = 24.576 Mbit/s
```

DMA 内存带宽以 32 位元素计算：

```
48,000 × 8 × 4 = 1.536 MB/s
```

全双工同时收发约为：

```
1.536 × 2 = 3.072 MB/s
```

### 6.2 缓冲区延迟

对于双半缓冲：

```
Latency ≈ HalfFrames / Fs
```

例如每半区 128 帧，采样率 48 kHz：

```
Latency = 128 / 48000
        ≈ 2.67 ms
```

常见配置：

|每半区帧数|48 kHz 回调周期|适用场景|
|---|---|---|
|32|0.67 ms|低延迟监听，CPU/DMA 压力高|
|64|1.33 ms|实时交互|
|128|2.67 ms|通用音频|
|256|5.33 ms|播放、存储|
|1024|21.33 ms|非实时批处理|

### 6.3 典型 CPU 开销

|操作|典型 CPU 占用|
|---|---|
|I2S/SAI DMA 搬运|小于 1%|
|TDM 8 槽位通道重排|1%~3%|
|PDM 硬件解码|小于 2%|
|软件 CIC + FIR PDM 解码|5%~20%|
|48 kHz、128 点 FFT|1%~5%|
|Cache 维护|取决于缓冲区大小，通常小于 2%|

### 6.4 主要瓶颈

- PDM 解码滤波器计算量；
- 过小 DMA 缓冲导致中断频率过高；
- Cache 维护造成额外内存流量；
- TDM 大量通道重排；
- 音频任务优先级不足；
- 文件系统写入阻塞；
- 锁竞争导致 DMA 半区未及时消费。

### 6.5 优化收益

- DMA 双缓冲替代逐样本中断：CPU 占用通常可从 20% 以上降至 1% 以下。
- PDM 使用硬件解码器：CPU 占用通常可降低 5~15 个百分点。
- 使用 Non-cacheable SRAM：避免每半区 Cache 维护，但可能降低 CPU 顺序访问速度。
- 将 TDM 通道抽取改为 DMA 链表或硬件路由：可减少 1%~3% CPU 占用。
- 增大缓冲区可降低中断频率，但会增加端到端延迟，不能无限增大。

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
需要连接数字麦克风？
├── 是
│   ├── 麦克风输出 PDM？
│   │   ├── 是 ──> 使用 PDM 接口 + 硬件/软件 PDM2PCM
│   │   └── 否 ──> 使用 I2S/TDM 数字麦克风接口
│   └── 需要多麦克风？
│       ├── 是 ──> PDM 多路或 TDM
│       └── 否 ──> 单路 PDM/I2S
│
└── 否，需要连接 Codec/功放？
    ├── 立体声、低复杂度
    │   └── I2S
    ├── 多声道
    │   └── TDM
    ├── 需要多协议、双子块、全双工
    │   └── SAI
    └── 芯片只提供增强型串行音频外设
        └── 优先使用 SAI 或厂商等价外设
```

### 7.2 典型场景

|场景|推荐方案|理由|
|---|---|---|
|MCU 连接立体声 Codec|I2S|配置简单、生态成熟|
|MCU 同时播放和录音|SAI 双子块|便于全双工和时钟同步|
|智能音箱 4 麦阵列|PDM|数字麦克风成本低、抗模拟干扰|
|8 路 ADC 采集|TDM|单条数据线传输多通道|
|汽车功放多通道输入|SAI/TDM|支持多槽位、同步帧和高带宽|
|音频算法前端|PDM + DMA + DSP|适合连续采集和批处理|
|低延迟耳机回放|I2S/SAI + 小 DMA 半区|可以控制端到端延迟|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **时钟优先于数据调试**。先确认 `Fs`、`BCLK`、`MCLK`，再检查数据。
2. **显式区分有效位宽和槽位宽**。
3. **DMA 缓冲区必须满足对齐和 Cache 要求**。
4. **DMA ISR 只做事件通知，不执行重计算**。
5. **启动顺序固定化**：
    - 配置 GPIO；
    - 配置时钟；
    - 清 FIFO；
    - 配置 DMA；
    - 配置外设；
    - 清状态；
    - 启动接收；
    - 启动发送；
    - 开启音频流。
6. **停止顺序固定化**：
    - 禁止新数据提交；
    - 等待或丢弃当前 DMA；
    - 关闭外设；
    - 关闭 DMA；
    - 清状态；
    - 释放时钟和 GPIO。
7. 任何音频流都应有明确的状态机：

```
RESET
  ↓
CONFIGURED
  ↓
PRIMED
  ↓
RUNNING
  ↓
STOPPING
  ↓
ERROR_RECOVERY
```

### 8.2 选型决策矩阵

|需求|I2S|SAI|PDM|TDM|
|---|---|---|---|---|
|立体声|高|高|低|中|
|多声道|低|高|中|高|
|数字麦克风|低|中|高|中|
|配置简单|高|中|中|低|
|低 CPU|高|高|取决于硬件|高|
|灵活协议|低|高|低|高|
|低成本|高|高|高|高|

### 8.3 工业级编码规范

- 所有采样率、位宽、槽位数使用枚举或配置结构，不使用散落魔数。
- DMA 缓冲区长度使用帧数计算，不直接写字节数。
- 所有寄存器写入后检查 `BUSY`、`FIFO_LEVEL`、错误状态。
- 统计并暴露：
    - DMA 欠载数；
    - DMA 溢出数；
    - FIFO 错误数；
    - 缓冲区高水位；
    - 实际采样率；
    - 时钟错误。
- 音频时间基准不能依赖任务调度时间，必须以 DMA 帧计数为准。
- 录音数据写文件时，使用独立存储任务，避免阻塞音频采集任务。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：有效位宽和槽位宽混淆

错误代码：

```
audio_config.data_width = 32;
audio_config.slot_width = 24;
```

根因：

- 24 位数据被放进 32 位槽位时，槽位通常不能小于有效数据宽度。
- 某些外设会直接拒绝配置，另一些会产生错位数据。

正确实现：

```
audio_config.data_width = AUDIO_DATA_WIDTH_24;
audio_config.slot_width = AUDIO_SLOT_WIDTH_32;
```

风险：

- 左右声道失真；
- 数据符号位错误；
- 高 8 位或低 8 位丢失。

### 9.2 错误二：I2S 和左对齐协议配置错误

错误代码：

```
config.protocol = AUDIO_PROTOCOL_LEFT_JUSTIFIED;
```

但 Codec 实际要求 I2S。

根因：

- 两者的 MSB 相对于 WS 有一个 BCLK 周期偏移。

正确实现：

```
config.protocol = AUDIO_PROTOCOL_I2S;
config.fs_polarity = AUDIO_FS_ACTIVE_LOW;
config.first_bit = AUDIO_MSB_FIRST;
```

风险：

- 正弦波变成严重噪声；
- 音频幅度异常；
- 逻辑分析仪看似有数据，但数据内容不正确。

### 9.3 错误三：DMA 缓冲区存在 Cache 不一致

错误代码：

```
void dma_rx_complete(void)
{
    process_audio(rx_buffer);
}
```

根因：

- DMA 已经写入 SRAM，但 CPU 仍读取旧 Cache line。

正确实现：

```
void dma_rx_complete(void)
{
    cache_invalidate_aligned(rx_buffer, RX_HALF_BYTES);
    notify_audio_task(AUDIO_RX_HALF_READY);
}
```

风险：

- 重复处理旧数据；
- 音频卡顿；
- 间歇性噪声；
- 只在开启优化或开启 Cache 时出现。

### 9.4 错误四：在 DMA 中断中执行复杂算法

错误代码：

```
void dma_half_irq(void)
{
    fir_process(rx_buffer, output_buffer, 1024);
    wav_write(output_buffer, 1024);
}
```

根因：

- ISR 执行时间超过半缓冲可用时间；
- 文件系统或锁操作不可预测。

正确实现：

```
void dma_half_irq(void)
{
    cache_invalidate_aligned(rx_buffer, RX_HALF_BYTES);
    audio_event_post_from_isr(AUDIO_RX_HALF_READY);
}
```

风险：

- 丢失后续 DMA 事件；
- FIFO 溢出；
- RTOS 高优先级任务被长期阻塞；
- 系统出现不可复现的爆音。

### 9.5 错误五：TDM 槽位映射假设错误

错误代码：

```
mic0 = tdm_buffer[frame * 4 + 0];
mic1 = tdm_buffer[frame * 4 + 1];
```

但硬件实际将麦克风接在 Slot 2 和 Slot 3。

正确实现：

```
enum {
    MIC0_SLOT = 2,
    MIC1_SLOT = 3,
};

mic0 = tdm_buffer[frame * TDM_SLOTS + MIC0_SLOT];
mic1 = tdm_buffer[frame * TDM_SLOTS + MIC1_SLOT];
```

风险：

- 采集到静音；
- 通道顺序错误；
- 波束成形算法失效；
- 多设备间通道对应关系错乱。

### 9.6 错误六：PDM 抽取率和时钟不匹配

错误配置：

```
PDM_CLK = 3.072 MHz
Decimation = 48
目标 PCM = 48 kHz
```

实际结果：

```
Fs = 3.072 MHz / 48 = 64 kHz
```

正确配置：

```
PDM_CLK = 3.072 MHz
Decimation = 64
PCM = 48 kHz
```

风险：

- 音频播放速度错误；
- 频谱位置偏移；
- 后续算法采样率假设失效。

---

## 10. 多机制组合使用方案

### 10.1 推荐架构

```
                 ┌──────────────────┐
                 │ Audio Controller │
                 └────────┬─────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   Clock Manager     Stream Manager      Error Manager
        │                 │                 │
   I2S/SAI/PDM HAL   DMA Ring Buffer   Recovery Policy
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                    Audio Processing
                          │
                 Codec / DSP / Storage
```

### 10.2 统一音频流配置

```
typedef enum {
    AUDIO_IF_I2S,
    AUDIO_IF_SAI,
    AUDIO_IF_PDM,
    AUDIO_IF_TDM
} audio_if_type_t;

typedef struct {
    audio_if_type_t interface_type;
    uint32_t sample_rate;
    uint32_t channels;
    uint32_t valid_bits;
    uint32_t slot_bits;
    uint32_t tdm_slots;
    uint32_t dma_half_frames;
    bool master_mode;
    bool full_duplex;
} audio_config_t;

typedef struct {
    int (*configure)(const audio_config_t *cfg);
    int (*start_rx)(void);
    int (*start_tx)(void);
    int (*stop)(void);
    int (*recover)(void);
} audio_if_ops_t;
```

### 10.3 音频任务框架

```
static void audio_task(void *argument)
{
    audio_dma_event_t event;

    for (;;) {
        if (xQueueReceive(g_audio_queue, &event, portMAX_DELAY) != pdPASS) {
            continue;
        }

        switch (event) {
        case AUDIO_DMA_HALF:
            audio_cache_prepare_half(0);
            audio_process_half(0);
            break;

        case AUDIO_DMA_FULL:
            audio_cache_prepare_half(1);
            audio_process_half(1);
            break;

        case AUDIO_DMA_ERROR:
            audio_stop_hw();
            audio_clear_status();
            audio_reconfigure();
            audio_restart_stream();
            break;

        default:
            break;
        }
    }
}
```

### 10.4 播放和录音同步

全双工系统需要使用同一音频时钟源，否则录音和播放的实际采样率会有偏差。

例如：

```
播放时钟：48,000.0 Hz
录音时钟：48,003.2 Hz
```

每秒会产生约 3.2 个采样的相对偏差。长时间运行后必须：

- 使用同一 PLL；
- 让一个方向作为主时钟；
- 或使用异步采样率转换 ASRC；
- 或周期性丢弃/插入样本，但这种方式会引入可听伪影。

---

## 11. 工业级实际案例分析

### 11.1 案例一：工业语音终端的双麦 PDM 采集

#### 需求

- 2 路数字 PDM 麦克风；
- 16 kHz PCM 输出；
- 连续录音；
- 运行回声消除和语音唤醒；
- 允许单次 DMA 延迟小于 4 ms。

#### 架构

```
PDM CLK 2.048 MHz
    ↓
双麦数据线，左右边沿复用
    ↓
PDM 硬件解码
    ↓
16 kHz PCM 双通道
    ↓
DMA 双缓冲
    ↓
AEC / VAD / Wake Word
```

参数：

```
PDM_CLK = 2.048 MHz
Decimation = 128
Fs = 16 kHz
HalfFrames = 64
Latency = 64 / 16000 = 4 ms
```

#### 设计要点

- PDM 麦克风左右通道选择必须核对数据手册；
- 对输入做 DC blocker；
- 麦克风时钟使用低抖动时钟源；
- DMA 缓冲区放入 Non-cacheable SRAM；
- AEC 任务优先级低于 DMA 服务任务；
- 通过统计丢帧计数确认连续采集。

### 11.2 案例二：四通道工业振动采集

#### 需求

- 4 路同步 ADC；
- 采样率 48 kHz；
- 24 位有效精度；
- 需要保证通道间采样相位一致；
- 数据写入 SD 卡。

#### 架构

```
多通道 ADC
    ↓
TDM 8 Slot，实际启用 Slot 0~3
    ↓
SAI RX
    ↓
DMA 环形缓冲
    ↓
通道分离与标定
    ↓
SD 卡写入任务
```

配置：

```
Fs        = 48 kHz
SlotCount = 8
SlotWidth = 32 bit
BCLK      = 12.288 MHz
```

#### 设计要点

- 使用 TDM 的统一帧同步保证通道时间对齐；
- Slot 4~7 即使未使用，也要确认是否发送填充数据；
- 不能在 DMA 中断中直接写 SD 卡；
- 采集时间戳以帧计数生成；
- SD 卡写入使用较大的块，例如 4 KB 或 8 KB；
- 缓冲区至少覆盖 SD 卡最坏擦除延迟。

### 11.3 案例三：立体声 Codec 播放和录音

#### 需求

- 48 kHz、24 位、立体声；
- 播放与录音全双工；
- 连接外部 Codec；
- 低延迟监听；
- 支持运行时静音和音量调整。

#### 架构

```
MCU SAI Block A TX ── Codec DAC
MCU SAI Block B RX ── Codec ADC
          │
       同一 PLL
          │
       DMA 双缓冲
```

#### 核心配置

```
audio_config_t cfg = {
    .interface_type = AUDIO_IF_SAI,
    .sample_rate = 48000U,
    .channels = 2U,
    .valid_bits = 24U,
    .slot_bits = 32U,
    .tdm_slots = 2U,
    .dma_half_frames = 128U,
    .master_mode = true,
    .full_duplex = true,
};
```

#### 设计要点

- Codec 的 `MCLK/LRCLK/BCLK` 比例必须同时满足；
- 先启动 RX，再启动 TX，避免录音首帧丢失；
- 静音应优先使用 Codec 硬件 mute；
- 音量寄存器更新应避免在 I2C/SPI 总线阻塞音频任务；
- 发生 FIFO 错误时先关闭 DMA，再清除外设错误状态。

---

## 12. 高频问题深度答疑

### 问题一：为什么逻辑分析仪看到 BCLK 和 WS 正常，但播放仍是噪声？

通常不是“时钟正常就说明接口正常”。还需检查：

- I2S 与左对齐模式；
- WS 极性；
- MSB 相对 WS 的偏移；
- 有效数据宽度；
- 槽位宽度；
- 数据端的上升沿/下降沿采样配置；
- Codec 是否处于正确的数字音频格式。

建议发送固定测试模式：

```
左声道：0x7FFFFF
右声道：0x800000
```

通过示波器或逻辑分析仪确认符号位和声道边界。

### 问题二：为什么 24 位音频通常放在 32 位槽位？

原因包括：

- 硬件 FIFO 常以 8、16、32 位访问；
- DMA 对齐更简单；
- 32 位槽位可以保证每个采样边界固定；
- CPU DSP 通常使用 32 位整数；
- 避免 3 字节数据在内存中的非对齐访问。

代价是带宽增加：

```
24 bit slot: 24 bit × channels × Fs
32 bit slot: 32 bit × channels × Fs
```

如果外设和 Codec 支持，24 位槽位节省约 25% 串行带宽，但配置复杂度和兼容性更差。

### 问题三：I2S 主模式和从模式如何选择？

- MCU 连接普通 Codec，且系统以 MCU 为时钟中心：通常 MCU 做主机。
- MCU 需要跟随外部专业音频时钟：MCU 做从机。
- 多设备系统：只能有一个明确的 `BCLK/FS` 主时钟源。
- 录音和播放共用系统时钟：优先统一 PLL，避免采样率漂移。

### 问题四：DMA 半缓冲多大最合适？

没有固定值，需要平衡：

```
更小缓冲：
    更低延迟
    更高 DMA 中断频率
    更高调度压力

更大缓冲：
    更低中断频率
    更强抗阻塞能力
    更高处理延迟
```

经验上：

- 实时监听：32~64 帧；
- 普通语音：64~128 帧；
- 音乐播放：128~512 帧；
- SD 卡采集：256~2048 帧，并配合更深层 FIFO。

### 问题五：PDM 为什么不能简单统计 1 的数量得到 PCM？

简单计数只能得到窗口平均值，不能满足音频带宽和抗混叠要求：

- 没有合适的低通滤波；
- 高频噪声折叠到基带；
- 频响严重依赖窗口；
- 量化噪声和频谱形状无法控制。

PDM 解码必须包含低通滤波和抽取，生产实现应使用经过验证的 PDM Filter。

### 问题六：TDM 的 FS 是一个脉冲还是占空比 50% 的方波？

两者都有实现，取决于协议和外设：

- 长帧同步：FS 持续一个或多个槽位周期；
- 短帧同步：FS 只持续一个 BCLK 周期；
- 某些 Codec 要求 50% 占空比；
- 某些 ADC 只接受短脉冲帧同步。

必须以对端数据手册为准，不能仅依据“I2S 标准”推断 TDM 行为。

---

## 13. 课程核心总结

### 核心要点

- **I2S 重点是时序偏移和左右声道边界**。
- **SAI 重点是多子块、时钟同步和协议灵活性**。
- **PDM 重点是高速单比特流与 PCM 抽取之间的转换**。
- **TDM 重点是槽位数量、槽位宽度和通道映射**。
- 音频驱动的稳定性主要由以下因素共同决定：

```
稳定音频流 =
正确时钟
+ 正确帧格式
+ 正确 DMA
+ 正确 Cache 处理
+ 足够缓冲
+ 可恢复错误处理
```

### 性能排序

以 CPU 负载为主要指标，通常为：

```
硬件 I2S/SAI DMA
    < TDM DMA + 通道重排
    < 硬件 PDM2PCM
    < 软件 PDM 解码
```

以协议灵活性为主要指标，通常为：

```
SAI > TDM > I2S > PDM
```

以实现复杂度为主要指标，通常为：

```
I2S < PDM < TDM < SAI
```

### 通用选型结论

- **普通立体声 Codec：选 I2S**。
- **复杂全双工或多协议系统：选 SAI**。
- **数字麦克风：选 PDM**。
- **多通道同步采集或播放：选 TDM**。
- 无论选择哪种接口，都应优先确认对端的时钟主从关系和帧格式。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|接口|典型配置|
|---|---|---|
|立体声播放|I2S TX|48 kHz、16/24 bit、2 Slot|
|立体声录音|I2S RX|48 kHz、16/24 bit、2 Slot|
|播放录音全双工|SAI|Block A TX + Block B RX|
|单数字麦克风|PDM|1~3 MHz PDM CLK|
|双数字麦克风|PDM|左右边沿复用|
|四路以上麦克风|TDM/PDM|多槽位或多 PDM 数据线|
|多通道 ADC|TDM|4/8/16 Slot|
|多通道功放|TDM|固定槽位映射|

### 14.2 特性对比表

|参数|I2S|SAI|PDM|TDM|
|---|---|---|---|---|
|PCM 采样|支持|支持|需转换|支持|
|原生多声道|弱|强|取决于硬件|强|
|是否需要抽取|否|否|是|否|
|是否依赖 DMA|强烈建议|强烈建议|强烈建议|强烈建议|
|关键验证点|MSB 偏移|子块同步|PDM CLK/OSR|Slot 映射|
|典型故障|爆音、声道错|不启动、不同步|频响异常|通道错位|

---

## 15. 学习效果自检

完成本课后，应能够回答并实操以下问题：

- [ ]  能从 `Fs`、声道数和槽位宽度计算 `BCLK`。
- [ ]  能解释 I2S 与左对齐协议的 MSB 时序差异。
- [ ]  能说明有效位宽和槽位宽度为何可以不同。
- [ ]  能配置 48 kHz、立体声、24 位、32 位槽位的音频流。
- [ ]  能设计 DMA 双半缓冲并处理半传输和全传输事件。
- [ ]  能解释 D-Cache 对 DMA 音频数据的影响。
- [ ]  能计算 PDM 时钟、抽取率和 PCM 采样率之间的关系。
- [ ]  能从 TDM 缓冲区中正确抽取指定槽位。
- [ ]  能设计音频 DMA 欠载、溢出和 FIFO 错误恢复流程。
- [ ]  能使用逻辑分析仪判断 I2S 的 MSB 偏移是否正确。
- [ ]  能区分“没有时钟”“没有 DMA”“没有有效数据”“Codec 未启动”四类故障。
- [ ]  能解释为什么播放和录音应尽量使用同一时钟源。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：裸机 I2S 播放

实现：

- 48 kHz；
- 16 位；
- 立体声；
- 正弦波 DMA 循环播放；
- 输出固定频率测试音。

验证：

```
输出频率误差 < 0.1%
左右声道幅度一致
无 DMA 欠载
```

#### 任务二：SAI 全双工回环

实现：

```
SAI RX → DMA → 缓冲 → SAI TX
```

要求：

- 128 帧半缓冲；
- 录音和播放共享 PLL；
- 统计输入到输出延迟；
- 注入 FIFO 错误并验证恢复。

#### 任务三：PDM 双麦采集

实现：

- 2 路 PDM 麦克风；
- 输出 16 kHz PCM；
- 使用硬件 PDM Filter；
- 保存 WAV 文件；
- 分析噪声底和频率响应。

测试指标：

- 采样率误差；
- 通道间幅度差；
- 通道间相位差；
- 1 kHz 输入信号 THD+N；
- 连续运行 24 小时丢帧数。

#### 任务四：8 槽位 TDM 通道重排

实现：

- 8 Slot；
- 32 位槽位；
- 仅使用 Slot 0、2、5、7；
- 每个槽位输入不同频率的测试正弦波；
- 验证通道映射和帧边界。

#### 任务五：RTOS 音频服务

实现以下任务：

```
Audio DMA Service
Audio Processing Task
Storage Task
Control Task
```

要求：

- DMA 服务任务最高；
- 处理任务次高；
- 存储任务不能阻塞采集；
- 支持启动、停止、静音、恢复；
- 提供运行时统计接口。

### 16.2 性能测试方法

建议建立以下测试矩阵：

|测试项|方法|
|---|---|
|采样率准确度|定时器捕获 WS 周期|
|BCLK 准确度|逻辑分析仪测量频率|
|抖动|示波器统计周期偏差|
|DMA 延迟|GPIO 翻转与 DMA 中断时间戳对比|
|CPU 占用|DWT 周期计数器|
|缓冲区余量|记录高水位|
|丢帧|帧序号或 DMA 计数器校验|
|音频质量|FFT、THD+N、SNR、频响|
|长稳性|24/72 小时连续运行|

DWT 周期测量示例：

```
static inline uint32_t cycle_get(void)
{
    return DWT->CYCCNT;
}

uint32_t start = cycle_get();
audio_process_half(0);
uint32_t elapsed = cycle_get() - start;

uint32_t budget =
    (SystemCoreClock / sample_rate) * half_frames;

if (elapsed >= budget) {
    g_audio_processing_overrun++;
}
```

### 16.3 进阶学习方向

- ASRC 异步采样率转换；
- 音频 PLL 与低抖动时钟设计；
- USB Audio Class 1.0/2.0；
- Linux ALSA ASoC、DAI 和 DMA Engine；
- I2S/TDM Codec 驱动与 Device Tree；
- FIR、IIR、CIC、半带滤波器设计；
- 回声消除、波束成形和噪声抑制；
- 多通道音频时间同步；
- 音频数据完整性和安全启动链；
- ISO 26262、IEC 61508 音频控制系统设计；
- ARM Helium、DSP 指令和定点音频优化；
- 音频流的零拷贝、Scatter-Gather DMA 和内存带宽建模。