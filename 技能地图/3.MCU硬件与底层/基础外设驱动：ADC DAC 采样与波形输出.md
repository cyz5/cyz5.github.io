
## 1. 学习目标

### 理解

- 理解 **SAR ADC、Sigma-Delta ADC、R-2R DAC、电阻串 DAC** 的转换原理。
- 理解 ADC 的采样保持、量化、参考电压、采样时间、源阻抗和输入带宽之间的关系。
- 理解 DAC 的零阶保持、建立时间、输出缓冲能力、毛刺能量和负载稳定性。
- 理解 **分辨率不等于有效精度**，能够区分 LSB、DNL、INL、ENOB、SNR、SINAD、THD。

### 掌握

- 掌握 ADC/DAC 的寄存器配置顺序、校准流程和异常恢复。
- 掌握定时器触发、DMA 环形缓冲、双缓冲和半满/满传输事件。
- 掌握多通道扫描中的通道排序、串扰、采样时间和数据对齐。
- 掌握偏置、增益和参考电压误差的软件校准。

### 精通

- 精通高阻信号源的采样时间计算。
- 精通 DMA、Cache、总线竞争造成的数据一致性与实时性问题。
- 精通过采样、抽取、数字滤波和抗混叠滤波的联合设计。
- 精通动态指标的 FFT 测试及 ENOB 计算。

### 能够设计

- 能够设计 **定时器同步 ADC/DAC 数据链路**。
- 能够设计无丢样、可观测、可恢复的工业采集模块。
- 能够基于精度、吞吐率、延迟、CPU 占用和模拟前端条件完成选型。
- 能够设计 ADC/DAC 自检、校准、诊断和安全降级机制。

---

## 2. 前置要求

### 知识要求

- Cortex-M 中断、NVIC、DMA、定时器和总线矩阵。
- `volatile`、内存屏障、原子操作和生产者-消费者模型。
- RC 电路、运算放大器、奈奎斯特采样定理和基础频谱分析。
- RTOS 任务调度、中断优先级和 ISR 到任务的通知机制。
- MCU 时钟树、外设复位和引脚复用。

### 技能要求

- 能阅读 MCU Reference Manual、Datasheet 和 Errata。
- 能通过示波器观察触发、转换和 DMA 处理时序。
- 能使用逻辑分析仪、信号源和高精度万用表。
- 能进行链接脚本、MPU、D-Cache 和 DMA 内存区域配置。
- 能编写无动态内存分配的嵌入式 C 模块。

---

## 3. 技术概述

### 3.1 ADC 核心定义

ADC 将连续电压映射为离散数字码。理想单极性 ADC：

Code=clip⁡(⌊VinVref(2N−1)+0.5⌋,0,2N−1)Code=clip(⌊Vref​Vin​​(2N−1)+0.5⌋,0,2N−1)

反算输入电压：

Vin≈Code2N−1VrefVin​≈2N−1Code​Vref​

工程中还必须考虑：

Codereal=f(Vin,Vref,Offset,Gain,INL,DNL,Noise,Temperature)Codereal​=f(Vin​,Vref​,Offset,Gain,INL,DNL,Noise,Temperature)

### 3.2 DAC 核心定义

理想单极性 DAC：

Vout≈Code2N−1VrefVout​≈2N−1Code​Vref​

实际输出受输出缓冲器压摆率、输出阻抗、负载电容、零点/满量程裕量和建立时间限制。

### 3.3 技术价值

ADC/DAC 是数字控制系统与模拟物理世界之间的边界，直接决定：

- 传感器测量精度。
- 闭环控制延迟和稳定裕量。
- 波形生成质量。
- 故障诊断可信度。
- 模拟量接口的 EMC 和功能安全能力。

### 3.4 主流技术分支

|类型|典型分辨率|典型速率|核心特点|
|---|---|---|---|
|SAR ADC|10~18 bit|100 kSPS~几十 MSPS|低延迟、易于多路复用|
|Sigma-Delta ADC|16~32 bit|10 SPS~数 MSPS|高分辨率，存在数字滤波延迟|
|Flash ADC|6~10 bit|数百 MSPS~GSPS|极高吞吐率，功耗和面积大|
|Pipeline ADC|10~16 bit|数十 MSPS~GSPS|高速，固定流水线延迟|
|电阻串 DAC|8~12 bit|中低速|单调性好，面积较大|
|R-2R DAC|8~18 bit|中高速|结构通用，存在切换毛刺|
|电流舵 DAC|8~16 bit|数百 MSPS~GSPS|高速，匹配和动态误差关键|
|PWM + RC|取决于时钟与滤波|低速|成本低，纹波和响应时间矛盾|

---

## 4. 核心特性横向对比

### 4.1 ADC 采集模式

|方案|触发抖动|CPU 占用|连续吞吐|延迟可控性|适用场景|
|---|---|---|---|---|---|
|软件启动 + 轮询|高|高|低|差|上电自检、低速测量|
|软件启动 + 中断|高|中|中|一般|非周期事件采样|
|定时器触发 + 中断|低|中高|中|好|低通道数闭环控制|
|定时器触发 + DMA|低|低|高|好|连续数据采集|
|定时器 + DMA 双缓冲|低|低|很高|很好|DSP、音频、振动分析|
|多 ADC 同步交错|低|低|极高|复杂|高速采样|
|Sigma-Delta + DRDY/DMA|取决于 ADC|低|中|滤波延迟较大|高精度测量|

### 4.2 模拟输出方案

|方案|静态精度|响应速度|纹波|CPU 占用|典型用途|
|---|---|---|---|---|---|
|MCU 内置 DAC|中|μs 级|低|低|偏置、控制电压|
|DAC + DMA + 定时器|中|稳定周期输出|低|极低|任意波形|
|SPI 外置 DAC|高|取决于 SPI|低|低|工业模拟量输出|
|PWM + RC|低到中|慢|较高|极低|成本敏感的慢速输出|
|PWM + 有源滤波|中|中低速|中低|极低|电源设定、背光控制|

### 4.3 关键指标

|指标|含义|常见误区|
|---|---|---|
|Resolution|数字码宽度|12 bit 不代表有 12 bit 精度|
|ENOB|包含噪声和失真的有效位数|不能只用静态标准差代替|
|DNL|相邻码宽偏差|DNL < -1 LSB 可能丢码|
|INL|传输曲线相对理想直线偏差|软件两点校准不能消除全部 INL|
|SNR|信号功率与噪声功率比|不包含谐波|
|SINAD|信号与噪声失真综合比|用于计算动态 ENOB|
|Settling time|进入指定误差带的时间|不等于转换时间|
|Throughput|每秒完成的有效样本数|不等于 ADC 内核时钟|

---

## 5. 底层原理与功能特性深度解析

以下示例以 **STM32H743、Cortex-M7、ADC3、TIM6、DMA** 为参考。寄存器位定义应以目标芯片 Reference Manual 为准。

### 5.1 SAR ADC 转换链路

SAR ADC 一次转换包括：

1. 输入开关接通。
2. 采样电容向输入电压充电。
3. 输入开关断开，电容保持电压。
4. 电容 DAC 与比较器执行二分逼近。
5. 数字结果写入数据寄存器。
6. 触发 EOC/EOS，并可产生 DMA 请求。

N 位 SAR 理论上需要约 N 次比较，但 MCU 通常使用内部流水线，外部可见时间由数据手册给出：

Tconv=Csample+CconvertfADCTconv​=fADC​Csample​+Cconvert​​

若 12 bit 转换阶段为 12.5 cycles，采样时间为 47.5 cycles，ADC 时钟为 40 MHz：

Tconv=47.5+12.540MHz=1.5 μsTconv​=40MHz47.5+12.5​=1.5 μs

理论单 ADC 上限约为 **666.7 kSPS**，尚未扣除通道切换、触发和总线约束。

### 5.2 采样保持与源阻抗

采样电容需要在采样窗口内稳定到允许误差。近似模型：

Verror=Vstepe−Ts(Rs+Ron)CshVerror​=Vstep​e−(Rs​+Ron​)Csh​Ts​​

若要求误差小于 0.5 LSB：

Ts≥(Rs+Ron)Cshln⁡(2N+1)Ts​≥(Rs​+Ron​)Csh​ln(2N+1)

12 bit ADC、`Csh=5 pF`、`Ron=1 kΩ`、信号源阻抗 `Rs=100 kΩ`：

Ts≥101kΩ×5pF×ln⁡(8192)≈4.55 μsTs​≥101kΩ×5pF×ln(8192)≈4.55 μs

40 MHz ADC 时钟下至少需要 **182 cycles**。使用 2.5 或 8.5 cycles 会产生与输入码、前一通道电压相关的系统性误差。

可复用采样周期估算：

```
#include <math.h>
#include <stdint.h>

uint32_t adc_required_sample_cycles(uint32_t resolution_bits,
                                    float source_ohm,
                                    float switch_ohm,
                                    float sample_cap_f,
                                    float adc_clock_hz)
{
    if ((resolution_bits == 0U) || (adc_clock_hz <= 0.0f) ||
        (sample_cap_f <= 0.0f)) {
        return 0U;
    }

    const float tau = (source_ohm + switch_ohm) * sample_cap_f;
    const float settling = logf(ldexpf(1.0f, (int)resolution_bits + 1));
    return (uint32_t)ceilf(tau * settling * adc_clock_hz);
}
```

生产固件中通常离线计算并静态配置，避免引入浮点和 `libm`。

### 5.3 定时器硬件触发

周期采样不应通过任务延时或 ISR 重启 ADC。正确链路：

```
PLL/晶振
  └─ TIMx 计数器
      └─ TRGO 更新事件
          └─ ADC 外部触发
              └─ ADC 转换完成
                  └─ DMA 写入内存
```

采样频率：

fs=fTIM(PSC+1)(ARR+1)fs​=(PSC+1)(ARR+1)fTIM​​

定时器初始化核心代码：

```
#include "stm32h7xx.h"
#include <stdbool.h>
#include <stdint.h>

static bool tim6_init_trgo(uint32_t timer_clk_hz, uint32_t sample_rate_hz)
{
    if ((timer_clk_hz == 0U) || (sample_rate_hz == 0U) ||
        (sample_rate_hz > timer_clk_hz)) {
        return false;
    }

    const uint32_t ticks = timer_clk_hz / sample_rate_hz;
    if ((ticks == 0U) || (ticks > 65536U) ||
        ((timer_clk_hz % sample_rate_hz) != 0U)) {
        return false;
    }

    RCC->APB1LENR |= RCC_APB1LENR_TIM6EN;
    (void)RCC->APB1LENR;

    TIM6->CR1 = 0U;
    TIM6->PSC = 0U;
    TIM6->ARR = ticks - 1U;
    TIM6->CR2 = TIM_CR2_MMS_1;       /* Update event as TRGO */
    TIM6->EGR = TIM_EGR_UG;
    TIM6->SR = 0U;

    return true;
}
```

应先启动 DMA 和 ADC，再启动定时器，防止首个触发发生时接收端未就绪。

### 5.4 ADC 校准和启动状态机

ADC 稳压器、校准和就绪状态必须满足时序：

```
typedef enum {
    ADC_DRV_OK = 0,
    ADC_DRV_BAD_ARG,
    ADC_DRV_TIMEOUT,
    ADC_DRV_HW_ERROR
} adc_drv_status_t;

static bool wait_bits(volatile uint32_t *reg,
                      uint32_t mask,
                      uint32_t expected,
                      uint32_t timeout)
{
    while (timeout-- > 0U) {
        if ((*reg & mask) == expected) {
            return true;
        }
    }
    return false;
}

static adc_drv_status_t adc3_calibrate_and_enable(void)
{
    if ((ADC3->CR & ADC_CR_ADEN) != 0U) {
        ADC3->CR |= ADC_CR_ADDIS;
        if (!wait_bits(&ADC3->CR, ADC_CR_ADEN, 0U, 100000U)) {
            return ADC_DRV_TIMEOUT;
        }
    }

    ADC3->CR &= ~ADC_CR_DEEPPWD;
    ADC3->CR |= ADC_CR_ADVREGEN;

    /* Replace with a timer-based delay satisfying the datasheet tADCVREG_STUP. */
    for (volatile uint32_t i = 0U; i < 1000U; ++i) {
        __NOP();
    }

    ADC3->CR &= ~ADC_CR_ADCALDIF;    /* Single-ended calibration */
    ADC3->CR |= ADC_CR_ADCAL;

    if (!wait_bits(&ADC3->CR, ADC_CR_ADCAL, 0U, 1000000U)) {
        return ADC_DRV_TIMEOUT;
    }

    ADC3->ISR = ADC_ISR_ADRDY;
    ADC3->CR |= ADC_CR_ADEN;

    if (!wait_bits(&ADC3->ISR, ADC_ISR_ADRDY, ADC_ISR_ADRDY, 100000U)) {
        return ADC_DRV_TIMEOUT;
    }

    return ADC_DRV_OK;
}
```

注意：循环超时依赖 CPU 频率，工业实现应使用单调硬件计时器。芯片复位、低功耗退出及温漂超限后是否重新校准，需要依据数据手册确定。

### 5.5 多通道扫描

多通道扫描的内存排列通常为：

```
CH0, CH1, CH2, CH0, CH1, CH2, ...
```

总触发周期必须覆盖整个序列：

Ttrigger≥∑i=1MTconv,iTtrigger​≥i=1∑M​Tconv,i​

高阻通道紧跟大幅度低阻通道时，采样电容残余电荷会造成串扰。解决顺序：

1. 增加高阻通道采样周期。
2. 使用运放缓冲。
3. 插入重复采样并丢弃第一次结果。
4. 优化通道排序，降低相邻通道电压阶跃。
5. 对关键通道使用独立 ADC。

通道解复用：

```
#define ADC_CHANNEL_COUNT 3U

typedef struct {
    uint16_t current;
    uint16_t voltage;
    uint16_t temperature;
} adc_frame_t;

static bool adc_decode_interleaved(const uint16_t *src,
                                   size_t sample_count,
                                   adc_frame_t *dst,
                                   size_t frame_capacity,
                                   size_t *frames_written)
{
    if ((src == NULL) || (dst == NULL) || (frames_written == NULL) ||
        ((sample_count % ADC_CHANNEL_COUNT) != 0U)) {
        return false;
    }

    const size_t frames = sample_count / ADC_CHANNEL_COUNT;
    if (frames > frame_capacity) {
        return false;
    }

    for (size_t i = 0U; i < frames; ++i) {
        dst[i].current     = src[i * 3U + 0U];
        dst[i].voltage     = src[i * 3U + 1U];
        dst[i].temperature = src[i * 3U + 2U];
    }

    *frames_written = frames;
    return true;
}
```

### 5.6 DMA 环形缓冲与双缓冲

DMA 半传输和全传输事件形成两个固定数据块：

```
DMA 正在写后半区 -> CPU 处理前半区
DMA 正在写前半区 -> CPU 处理后半区
```

```
#include <stdatomic.h>

#define ADC_DMA_SAMPLES 1024U

#if defined(__GNUC__)
__attribute__((section(".dma_buffer"), aligned(32)))
#endif
static uint16_t g_adc_dma[ADC_DMA_SAMPLES];

typedef struct {
    atomic_uint_fast32_t ready_mask;
    atomic_uint_fast32_t overrun_count;
} adc_dma_state_t;

static adc_dma_state_t g_adc_state;

static void adc_publish_block(uint32_t mask)
{
    const uint32_t previous =
        (uint32_t)atomic_fetch_or_explicit(&g_adc_state.ready_mask,
                                           mask,
                                           memory_order_release);
    if ((previous & mask) != 0U) {
        atomic_fetch_add_explicit(&g_adc_state.overrun_count,
                                  1U,
                                  memory_order_relaxed);
    }
}

void DMA1_Stream0_IRQHandler(void)
{
    const uint32_t status = DMA1->LISR;

    if ((status & DMA_LISR_TEIF0) != 0U) {
        DMA1->LIFCR = DMA_LIFCR_CTEIF0;
        /* Record fault and stop the acquisition chain. */
    }

    if ((status & DMA_LISR_HTIF0) != 0U) {
        DMA1->LIFCR = DMA_LIFCR_CHTIF0;
        adc_publish_block(1U);
    }

    if ((status & DMA_LISR_TCIF0) != 0U) {
        DMA1->LIFCR = DMA_LIFCR_CTCIF0;
        adc_publish_block(2U);
    }
}
```

若 Cortex-M7 开启 D-Cache，必须满足以下之一：

- DMA 缓冲区放入不可缓存的 SRAM 区域。
- 通过 MPU 将该区设为 non-cacheable。
- 每次 CPU 读取前按 Cache Line 对齐执行 invalidate。

仅使用 `volatile` **不能解决 Cache 一致性问题**。

### 5.7 过采样与抽取

对白噪声主导的系统，额外获得 B 位有效分辨率通常需要：

OSR=4BOSR=4B

- 增加 1 bit：4 倍采样。
- 增加 2 bit：16 倍采样。
- 增加 3 bit：64 倍采样。

```
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool adc_average_u16(const uint16_t *samples,
                            size_t count,
                            uint16_t *result)
{
    if ((samples == NULL) || (result == NULL) ||
        (count == 0U) || (count > 65536U)) {
        return false;
    }

    uint64_t sum = 0U;
    for (size_t i = 0U; i < count; ++i) {
        sum += samples[i];
    }

    *result = (uint16_t)((sum + count / 2U) / count);
    return true;
}
```

简单平均具有 sinc 频响，会引入窗口长度对应的延迟，并不能替代模拟抗混叠滤波。如果输入噪声不足以跨越量化阈值，重复采样不会产生额外有效位，需要受控抖动或更高分辨率 ADC。

### 5.8 参考电压补偿

ADC 测量的是 `Vin/Vref`。若 VDDA 波动，固定常数换算会产生比例误差。可利用内部校准参考通道估算 VDDA：

VDDA=VCALCodeVREFINT,CALCodeVREFINTVDDA​=VCAL​CodeVREFINT​CodeVREFINT,CAL​​

```
static bool adc_calculate_vdda_mv(uint16_t vref_code,
                                  uint16_t factory_cal_code,
                                  uint32_t factory_cal_mv,
                                  uint32_t *vdda_mv)
{
    if ((vref_code == 0U) || (factory_cal_code == 0U) ||
        (vdda_mv == NULL)) {
        return false;
    }

    *vdda_mv =
        (factory_cal_mv * (uint32_t)factory_cal_code + vref_code / 2U) /
        vref_code;
    return true;
}
```

工厂校准数据的地址、标称电压和适用温度必须使用目标芯片数据手册定义，不能跨型号复制。

### 5.9 两点校准

线性校准模型：

ycal=Gx+Oycal​=Gx+OG=y2−y1x2−x1,O=y1−Gx1G=x2​−x1​y2​−y1​​,O=y1​−Gx1​

定点实现避免运行时浮点：

```
typedef struct {
    int32_t gain_q20;
    int32_t offset_q20;
} linear_cal_t;

static bool linear_cal_build(int32_t raw1,
                             int32_t eng1,
                             int32_t raw2,
                             int32_t eng2,
                             linear_cal_t *cal)
{
    if ((cal == NULL) || (raw1 == raw2)) {
        return false;
    }

    cal->gain_q20 =
        (int32_t)(((int64_t)(eng2 - eng1) << 20) / (raw2 - raw1));
    cal->offset_q20 =
        (int32_t)(((int64_t)eng1 << 20) -
                  (int64_t)cal->gain_q20 * raw1);
    return true;
}

static int32_t linear_cal_apply(const linear_cal_t *cal, int32_t raw)
{
    const int64_t value_q20 =
        (int64_t)cal->gain_q20 * raw + cal->offset_q20;
    return (int32_t)((value_q20 + (1LL << 19)) >> 20);
}
```

两点校准只能补偿主要的增益与偏置误差，不能消除 INL、温漂、噪声和前端非线性。

### 5.10 DAC 定时器触发与 DMA 输出

DAC 输出周期波形：

```
查找表 -> DMA -> DAC 数据保持寄存器
                    ↑
                 TIM TRGO
```

N 点波形的基频：

fout=fupdateNfout​=Nfupdate​​

```
#define DAC_TABLE_SIZE 256U
#define DAC_MAX_CODE   4095U

static uint16_t g_dac_table[DAC_TABLE_SIZE];

static void dac_generate_triangle(uint16_t amplitude, uint16_t offset)
{
    if (amplitude > DAC_MAX_CODE) {
        amplitude = DAC_MAX_CODE;
    }

    for (uint32_t i = 0U; i < DAC_TABLE_SIZE; ++i) {
        const uint32_t phase =
            (i < DAC_TABLE_SIZE / 2U) ? i : (DAC_TABLE_SIZE - 1U - i);
        uint32_t code =
            offset + (2U * (uint32_t)amplitude * phase) / DAC_TABLE_SIZE;

        if (code > DAC_MAX_CODE) {
            code = DAC_MAX_CODE;
        }
        g_dac_table[i] = (uint16_t)code;
    }
}
```

DMA 必须在定时器启动前配置完成。若运行中切换波形，使用双缓冲并只在块边界交换，避免半张表来自旧波形、半张表来自新波形。

---

## 6. 性能量化分析

### 6.1 测试平台与口径

参考平台：

- MCU：STM32H743，Cortex-M7 400 MHz。
- ADC：12 bit 模式，ADC kernel clock 40 MHz。
- DMA：16 bit 外设到内存。
- 缓冲：1024 samples，32-byte 对齐。
- 编译器：GCC `-O2`。
- 输入：低失真正弦源，经低噪声运放缓冲。
- 测试口径：以下时序含计算值和工程代表值；最终设计必须在实际 PCB 上复测。

### 6.2 转换时间

|采样周期|总周期，假设转换 12.5 cycles|单次时间|理论上限|
|---|---|---|---|
|2.5|15|0.375 μs|2.67 MSPS|
|16.5|29|0.725 μs|1.38 MSPS|
|47.5|60|1.500 μs|666.7 kSPS|
|247.5|260|6.500 μs|153.8 kSPS|
|810.5|823|20.575 μs|48.6 kSPS|

表中是公式结果，不代表芯片在所有分辨率、boost 模式、电压和温度条件下均允许该速率。

### 6.3 内存带宽

12 bit 结果通常以 16 bit 存储：

BW=fs×Channels×2 bytesBW=fs​×Channels×2 bytes

4 通道、每通道 100 kSPS：

BW=100k×4×2=800 kB/sBW=100k×4×2=800 kB/s

1024 个 `uint16_t` 双半区 DMA 缓冲占 **2048 bytes**。每半区填充时间：

Thalf=512400k=1.28 msThalf​=400k512​=1.28 ms

处理任务必须在 1.28 ms 内消费该块，否则需要更深队列或降低采样率。

### 6.4 CPU 开销

以 400 MHz M7 的代表性测量为例：

|处理方式|400 kSPS 时 CPU 占用|特征|
|---|---|---|
|每样本中断，约 180 cycles/sample|18.0%|中断频繁、抖动明显|
|512 样本 DMA 块通知，约 1200 cycles/block|0.23%|仅含调度与块管理|
|整块整数均值，约 7 cycles/sample|0.7%|Cache 命中情况下|
|64 tap FIR，优化 CMSIS-DSP|约 6%~15%|取决于数据类型和内存位置|

每样本中断占用估算：

CPU%=CyclesISR×fsfCPU×100%CPU%=fCPU​CyclesISR​×fs​​×100%

### 6.5 Cache 维护开销

32-byte Cache Line 下，1024-byte 半缓冲包含 32 条 Cache Line。代表性 invalidate 时间约为数百到一千 CPU cycles，取决于实现和总线状态。相比逐样本中断通常仍然很低，但错误的地址/长度对齐会使相邻变量失效。

推荐：

- 将 DMA 缓冲独占到 Cache Line。
- 长期高速流数据放入 MPU non-cacheable 区。
- 算法工作缓冲保持 cacheable，通过显式复制隔离所有权。

### 6.6 ENOB 与动态性能

由 SINAD 计算：

ENOB=SINAD−1.766.02ENOB=6.02SINAD−1.76​

若实测 SINAD 为 65 dB：

ENOB≈10.50 bitsENOB≈10.50 bits

理论 12 bit ADC 的理想量化 SNR：

SNRideal=6.02N+1.76=74.0 dBSNRideal​=6.02N+1.76=74.0 dB

工业板上受到参考源、地弹、时钟抖动、输入驱动和电源噪声影响，12 bit ADC 得到约 9.5~11.2 ENOB 是常见工程区间，不应直接宣称固定值。

### 6.7 时钟抖动限制

正弦输入下，时钟抖动导致的 SNR 上限：

SNRjitter=−20log⁡10(2πfinσt)SNRjitter​=−20log10​(2πfin​σt​)

`fin=100 kHz`、RMS 抖动 `σt=10 ps`：

SNRjitter≈104 dBSNRjitter​≈104 dB

对 12 bit ADC 通常不是首要瓶颈；对 MHz 级高分辨率采样则会迅速成为限制。

### 6.8 优化收益

|优化|典型收益|代价|
|---|---|---|
|轮询改 DMA 块处理|CPU 占用降低 10~100 倍|增加缓冲和状态管理|
|运放缓冲高阻源|降低建立误差和通道串扰|BOM、功耗、稳定性设计|
|16 倍过采样|理想条件约增加 2 bit|带宽降为 1/16，延迟增加|
|独立低噪声参考源|改善增益稳定性和噪声|成本与启动时间增加|
|同步硬件触发|显著降低采样周期抖动|占用定时器资源|
|DMA 区设为 non-cacheable|消除 Cache 维护错误|CPU 访问该区速度降低|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
需要采集还是输出？
├─ 采集
│  ├─ 有效分辨率是否超过 MCU ADC 能力？
│  │  ├─ 是：外置 SAR 或 Sigma-Delta ADC
│  │  └─ 否：内置 ADC
│  ├─ 是否要求确定周期与低抖动？
│  │  ├─ 是：定时器硬件触发
│  │  └─ 否：软件触发可接受
│  ├─ 总采样率是否超过约 10 kSPS？
│  │  ├─ 是：DMA 环形/双缓冲
│  │  └─ 否：中断或低频轮询
│  ├─ 输入源阻抗是否较高？
│  │  ├─ 是：计算采样时间；必要时运放缓冲
│  │  └─ 否：按吞吐率选择采样周期
│  └─ 是否涉及交流频谱？
│     ├─ 是：模拟抗混叠 + 相干采样/窗函数 + FFT
│     └─ 否：校准 + 低通/平均
└─ 输出
   ├─ 是否只需开关或慢速平均电压？
   │  ├─ 是：PWM + RC
   │  └─ 否：DAC
   ├─ 精度是否超过内置 DAC？
   │  ├─ 是：外置高精度 DAC + 独立参考
   │  └─ 否：内置 DAC
   └─ 是否输出周期波形？
      ├─ 是：定时器 + DMA + 查找表
      └─ 否：软件更新并校验范围
```

### 7.2 典型场景

|需求|方案|理由|
|---|---|---|
|电池电压，10 Hz|ADC 软件触发或低速定时器触发|带宽低，重视分压静态功耗与建立时间|
|三相电流，20 kHz 控制|PWM 中点触发 ADC + DMA/注入组|避开开关噪声并与控制周期同步|
|24 bit 称重|外置 Sigma-Delta ADC|低带宽、高分辨率、斩波与数字滤波|
|100 kHz 振动分析|SAR ADC + 定时器 + DMA 双缓冲|低延迟、高吞吐、便于 FFT|
|0~10 V 控制输出|外置 DAC + 运放放大 + 保护|MCU DAC 电压范围和驱动能力不足|
|音频/任意波形|DAC + 定时器 + DMA + 重构滤波|周期稳定，CPU 开销低|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **先设计模拟信号链，再配置 ADC**：量程、偏置、保护、带宽和源阻抗决定可实现精度。
2. **使用同一硬件时基同步采样和控制**：避免软件调度抖动。
3. **采样吞吐留至少 20% 裕量**：序列转换总时长不得逼近触发周期。
4. **DMA 缓冲建立明确所有权**：DMA 写入时 CPU 不得读取同一区块。
5. **ISR 只确认事件和交接缓冲**：滤波、校准、FFT 在任务或主循环执行。
6. **校准参数带版本和 CRC**：禁止无校验加载 Flash 参数。
7. **模拟地不是“零阻抗节点”** ：参考回流、数字开关电流和 ADC 驱动回路必须规划。
8. **保护器件必须纳入误差预算**：串联电阻、TVS 漏电和钳位二极管电容都会影响精度。
9. **DAC 输出必须验证负载稳定性**：大电容负载可能使片内缓冲器振荡。
10. **运行时监测溢出、超时和参考异常**：静默丢样不可接受。

### 8.2 选型决策矩阵

评分：1 差，5 优。

|方案|精度|吞吐|延迟|CPU 效率|成本|集成难度|
|---|---|---|---|---|---|---|
|MCU ADC 轮询|3|1|2|1|5|5|
|MCU ADC + DMA|3|4|4|5|5|4|
|外置 SAR ADC|4|5|5|4|3|3|
|外置 Sigma-Delta|5|2|2|4|3|3|
|MCU DAC|3|3|4|5|5|5|
|外置精密 DAC|5|3|3|4|2|3|
|PWM + RC|2|1|1|5|5|4|

### 8.3 工业级编码规范

- 驱动接口返回明确错误码，不使用静默失败。
- 所有等待硬件状态的循环必须有超时。
- DMA 缓冲使用固定宽度类型并满足对齐要求。
- 配置寄存器前关闭外设，按文档顺序清状态位。
- ISR 与任务共享状态使用原子操作或临界区。
- 对 ADC 原始码、校准值和工程量使用不同类型或命名后缀。
- 所有乘法在提升到足够宽度后执行，避免中间结果溢出。
- 在编译期验证缓冲大小、通道数和对齐条件。

```
_Static_assert((ADC_DMA_SAMPLES % 2U) == 0U,
               "DMA buffer must have two equal halves");
_Static_assert((sizeof(g_adc_dma) % 32U) == 0U,
               "DMA buffer size must be cache-line aligned");
```

---

## 9. 常见错误与避坑指南

### 9.1 使用任务延时控制采样周期

错误代码：

```
for (;;) {
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 10U);
    samples[index++] = HAL_ADC_GetValue(&hadc1);
    osDelay(1U);
}
```

根因：

- `osDelay()` 只保证任务至少延迟指定 tick。
- 调度、临界区和中断造成周期抖动。
- ADC 启动延迟也进入采样周期。

正确实现：

```
/* TIM TRGO drives ADC; DMA writes the complete stream. */
if (!tim6_init_trgo(timer_clock_hz, sample_rate_hz)) {
    system_enter_safe_state();
}

if (adc_dma_start(g_adc_dma, ADC_DMA_SAMPLES) != ADC_DRV_OK) {
    system_enter_safe_state();
}

TIM6->CR1 |= TIM_CR1_CEN;
```

风险影响：频谱泄漏、控制环路相位抖动、难以复现实验结果。

### 9.2 高阻输入使用最短采样时间

#### 错误代码

```
/* CH0 configured with the shortest sampling time. */
ADC3->SMPR1 &= ~ADC_SMPR1_SMP0;
```

#### 根因分析

ADC 输入端不是理想的无限输入阻抗节点。转换开始前，外部信号源必须通过模拟开关导通电阻 `Ron` 给内部采样电容 `Csh` 充电。

建立误差近似为：

Verror=Vstepe−Ts(Rs+Ron)CshVerror​=Vstep​e−(Rs​+Ron​)Csh​Ts​​

若要求 N 位 ADC 的建立误差小于 0.5 LSB：

Ts≥(Rs+Ron)Cshln⁡(2N+1)Ts​≥(Rs​+Ron​)Csh​ln(2N+1)

以 12 bit ADC 为例：

- `Rs = 100 kΩ`
- `Ron = 1 kΩ`
- `Csh = 5 pF`
- `fADC = 40 MHz`

计算得到：

Ts≥4.55 μsTs​≥4.55 μs

对应采样周期至少为：

Cycless≥4.55 μs×40MHz=182 cyclesCycless​≥4.55 μs×40MHz=182 cycles

如果配置为 2.5 cycles，实际采样窗口只有 62.5 ns，远低于要求。

#### 正确实现

首先根据数据手册列出的离散采样周期表选择**不小于计算值**的配置：

```
typedef struct {
    uint32_t smpr_bits;
    uint16_t cycles_x10;
} adc_sample_time_t;

static const adc_sample_time_t g_adc_sample_times[] = {
    { ADC_SMPR_SMP_1CYCLE_5,   15U   },
    { ADC_SMPR_SMP_2CYCLES_5,  25U   },
    { ADC_SMPR_SMP_8CYCLES_5,  85U   },
    { ADC_SMPR_SMP_16CYCLES_5, 165U  },
    { ADC_SMPR_SMP_32CYCLES_5, 325U  },
    { ADC_SMPR_SMP_64CYCLES_5, 645U  },
    { ADC_SMPR_SMP_387CYCLES_5, 3875U },
    { ADC_SMPR_SMP_810CYCLES_5, 8105U }
};

static bool adc_select_sample_time(uint32_t required_cycles_x10,
                                   uint32_t *smpr_bits)
{
    if (smpr_bits == NULL) {
        return false;
    }

    for (size_t i = 0U;
         i < sizeof(g_adc_sample_times) / sizeof(g_adc_sample_times[0]);
         ++i) {
        if (g_adc_sample_times[i].cycles_x10 >= required_cycles_x10) {
            *smpr_bits = g_adc_sample_times[i].smpr_bits;
            return true;
        }
    }

    return false;
}
```

若最长采样周期仍不能满足要求，应改变模拟前端，而不是继续修改数字滤波：

```
高阻传感器
    │
    ├─ RC 限带与保护
    │
    └─ 低偏置电流、轨到轨运放缓冲
            │
            └─ ADC 输入
```

运放还必须满足：

- 输出能够稳定驱动 ADC 的开关电容负载。
- 建立时间小于采样窗口。
- 输入偏置电流不会在高阻源上形成明显误差。
- GBW、压摆率和输出摆幅满足输入频带与量程。
- 必要时在运放输出与 ADC 引脚之间加入隔离电阻。

#### 风险影响

- 采样结果随前一个通道电压变化。
- 满量程附近误差增大。
- 多通道扫描产生串扰。
- 低速直流测试可能正常，高速连续采样时失效。
- 软件校准无法彻底补偿动态建立误差。

---

### 9.3 将 `volatile` 当作 DMA Cache 一致性解决方案

#### 错误代码

```
static volatile uint16_t adc_dma_buffer[1024];

void process_adc_data(void)
{
    for (size_t i = 0U; i < 1024U; ++i) {
        consume_sample(adc_dma_buffer[i]);
    }
}
```

#### 根因分析

`volatile` 只约束编译器：

- 每次访问都生成实际加载或存储指令。
- 不合并或删除可观察访问。

它不能完成：

- D-Cache 回写。
- D-Cache 失效。
- DMA 与 CPU 的硬件一致性维护。
- DMA/CPU 缓冲区所有权同步。
- 内存访问顺序的跨主设备协调。

在 Cortex-M7 上，如果 DMA 将新数据写入 SRAM，而 CPU Cache 中仍保留对应地址的旧 Cache Line，CPU 可能持续读到旧数据。

更严重的情况是：Cache Line 中同时包含 DMA 缓冲区和普通变量。执行 invalidate 时，可能丢弃普通变量尚未回写的数据。

#### 正确实现一：MPU 非缓存区

将 DMA 缓冲区放入独立且满足 MPU 粒度要求的区域：

```
#define ADC_DMA_SAMPLE_COUNT 1024U
#define CACHE_LINE_SIZE      32U

__attribute__((section(".dma_buffer"), aligned(CACHE_LINE_SIZE)))
static uint16_t g_adc_dma_buffer[ADC_DMA_SAMPLE_COUNT];

_Static_assert((sizeof(g_adc_dma_buffer) % CACHE_LINE_SIZE) == 0U,
               "DMA buffer size must be cache-line aligned");
```

链接脚本示意：

```
.dma_buffer (NOLOAD) :
{
    . = ALIGN(32);
    __dma_buffer_start__ = .;
    *(.dma_buffer)
    . = ALIGN(32);
    __dma_buffer_end__ = .;
} >RAM_D2
```

通过 MPU 将该区域配置为 non-cacheable。区域大小、对齐和属性必须遵守目标 Cortex-M 的 MPU 规则。

#### 正确实现二：显式 Cache 维护

DMA 从外设写内存后，CPU 读取前执行 invalidate：

```
#include <stdint.h>
#include <stddef.h>

#define CACHE_LINE_SIZE 32U

static void dcache_invalidate_region(void *address, size_t length)
{
    if ((address == NULL) || (length == 0U)) {
        return;
    }

    const uintptr_t start =
        (uintptr_t)address & ~((uintptr_t)CACHE_LINE_SIZE - 1U);
    const uintptr_t end =
        ((uintptr_t)address + length + CACHE_LINE_SIZE - 1U) &
        ~((uintptr_t)CACHE_LINE_SIZE - 1U);

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                (int32_t)(end - start));
    __DSB();
    __ISB();
}
```

半缓冲处理：

```
#define ADC_HALF_SAMPLES (ADC_DMA_SAMPLE_COUNT / 2U)

static void process_adc_half(uint32_t half_index)
{
    if (half_index > 1U) {
        return;
    }

    uint16_t *block =
        &g_adc_dma_buffer[half_index * ADC_HALF_SAMPLES];

    dcache_invalidate_region(block,
                             ADC_HALF_SAMPLES * sizeof(block[0]));

    adc_consume_block(block, ADC_HALF_SAMPLES);
}
```

对于**内存到外设**的 DAC DMA，CPU 写完波形表后应执行 clean，而不是 invalidate：

```
SCB_CleanDCache_by_Addr((uint32_t *)aligned_start, aligned_length);
__DSB();
```

#### 风险影响

- 处理到旧样本或混合新旧数据。
- 问题受代码布局、优化等级和运行时序影响，难以复现。
- DAC 输出旧波形。
- Cache 维护覆盖相邻对象，导致无关状态被破坏。
- 现场表现为偶发跳变、重复数据或控制失稳。

---

### 9.4 DMA 缓冲区被覆盖但软件没有检测

#### 错误代码

```
static bool block_ready;

void DMA_IRQHandler(void)
{
    block_ready = true;
}

void acquisition_task(void)
{
    if (block_ready) {
        block_ready = false;
        process_entire_buffer();
    }
}
```

#### 根因分析

单个布尔标志无法表达以下状态：

- 前半区已就绪。
- 后半区已就绪。
- 同一半区在处理前再次完成。
- 已发生一个或多个数据块丢失。
- DMA 传输错误。

如果处理时间大于半缓冲填充时间，后续事件只会重复写入 `true`，软件无法知道丢失了多少块。

硬实时约束为：

Tprocess,worst<ThalfTprocess,worst​<Thalf​

其中：

Thalf=Nhalffs×NchannelThalf​=fs​×Nchannel​Nhalf​​

还应留出中断、任务唤醒和高优先级抢占的预算。

#### 正确实现

使用位图表达半区所有权，并显式统计覆盖：

```
#include <stdatomic.h>
#include <stdint.h>

enum {
    ADC_BLOCK_FIRST  = 1U << 0,
    ADC_BLOCK_SECOND = 1U << 1
};

typedef struct {
    atomic_uint_fast32_t ready_mask;
    atomic_uint_fast32_t overrun_count;
    atomic_uint_fast32_t dma_error_count;
} adc_stream_state_t;

static adc_stream_state_t g_stream;

static void adc_publish_block(uint32_t block_mask)
{
    const uint32_t old_mask =
        (uint32_t)atomic_fetch_or_explicit(&g_stream.ready_mask,
                                           block_mask,
                                           memory_order_release);

    if ((old_mask & block_mask) != 0U) {
        atomic_fetch_add_explicit(&g_stream.overrun_count,
                                  1U,
                                  memory_order_relaxed);
    }
}

static bool adc_take_block(uint32_t block_mask)
{
    const uint32_t old_mask =
        (uint32_t)atomic_fetch_and_explicit(&g_stream.ready_mask,
                                            ~block_mask,
                                            memory_order_acquire);

    return (old_mask & block_mask) != 0U;
}
```

任务处理：

```
static void acquisition_service(void)
{
    if (adc_take_block(ADC_BLOCK_FIRST)) {
        process_adc_half(0U);
    }

    if (adc_take_block(ADC_BLOCK_SECOND)) {
        process_adc_half(1U);
    }

    const uint32_t overruns =
        (uint32_t)atomic_load_explicit(&g_stream.overrun_count,
                                       memory_order_relaxed);

    if (overruns != 0U) {
        diagnostics_report_adc_overrun(overruns);
    }
}
```

若每个数据块都必须保留，应使用描述符队列或多缓冲池。队列深度至少满足：

Depth≥⌈Tblocking,maxTblock⌉+MarginDepth≥⌈Tblock​Tblocking,max​​⌉+Margin

但增加队列只能吸收突发延迟，不能解决平均处理能力低于数据产生速率的问题。

#### 风险影响

- 无告警丢样。
- FFT 时序不连续。
- 能量积分结果偏低。
- 控制算法使用不完整数据。
- 故障录波缺少事故关键片段。

---

### 9.5 ADC 数据对齐、分辨率与 DMA 宽度不一致

#### 错误代码

```
static uint32_t adc_buffer[256];

/* ADC result is 16-bit, but DMA transfers bytes. */
DMA1_Stream0->PSIZE = DMA_PDATAALIGN_BYTE;
DMA1_Stream0->MSIZE = DMA_MDATAALIGN_BYTE;
```

#### 根因分析

ADC 数据寄存器、DMA 外设宽度、DMA 内存宽度和目标数组元素宽度必须一致。错误组合会导致：

- 高位丢失。
- 每个数组元素只有部分字节被更新。
- 数据间出现未初始化填充。
- 多通道序列发生错位。
- 左对齐结果被按右对齐解释。

对于 12 bit 右对齐 ADC，通常使用：

- 外设宽度：16 bit。
- 内存宽度：16 bit。
- 缓冲元素：`uint16_t`。
- 数据掩码：通常不必额外处理，但可在接口边界验证。

#### 正确实现

```
#define ADC_RESOLUTION_BITS 12U
#define ADC_CODE_MAX        ((1U << ADC_RESOLUTION_BITS) - 1U)

static uint16_t g_adc_buffer[256];

static bool adc_validate_block(const uint16_t *samples, size_t count)
{
    if ((samples == NULL) || (count == 0U)) {
        return false;
    }

    for (size_t i = 0U; i < count; ++i) {
        if (samples[i] > ADC_CODE_MAX) {
            return false;
        }
    }

    return true;
}

static void adc_configure_dma_width(void)
{
    /* Symbolic register fields are platform-specific. */
    DMA1_Stream0->CR &=
        ~(DMA_SxCR_PSIZE_Msk | DMA_SxCR_MSIZE_Msk);

    DMA1_Stream0->CR |=
        DMA_SxCR_PSIZE_0 |    /* Peripheral half-word */
        DMA_SxCR_MSIZE_0;     /* Memory half-word */
}
```

若使用 8 bit 模式或双 ADC 打包模式，必须根据数据寄存器格式重新定义传输宽度和解包逻辑。

#### 风险影响

- 采样码值缩小或周期性异常。
- 通道映射错乱。
- 缓冲区边界计算错误。
- 标定参数失效。
- 可能出现未对齐访问和总线 Fault。

---

### 9.6 未进行抗混叠设计，只依赖数字滤波

#### 错误代码

```
/* Sampling at 10 kSPS, then averaging in software. */
for (size_t i = 0U; i < count; ++i) {
    sum += samples[i];
}
result = sum / count;
```

#### 根因分析

高于奈奎斯特频率的模拟信号在 ADC 采样时已经折叠到基带：

falias=∣fin−kfs∣falias​=∣fin​−kfs​∣

例如：

- `fs = 10 kSPS`
- 干扰 `fin = 9 kHz`
- 取 `k = 1`

则：

falias=∣9k−10k∣=1kHzfalias​=∣9k−10k∣=1kHz

采样之后，数字域无法区分这个 1 kHz 分量来自真实 1 kHz 信号还是 9 kHz 混叠。数字滤波不能恢复已经丢失的信息。

#### 正确实现

模拟抗混叠滤波器必须在 ADC 之前：

```
传感器
  └─ 保护与限流
      └─ 模拟低通滤波器
          └─ 缓冲/增益级
              └─ ADC
                  └─ 数字滤波与抽取
```

一阶 RC 截止频率：

fc=12πRCfc​=2πRC1​

但单极点滤波器在截止频率之后仅有 **20 dB/decade** 衰减。若阻带要求较高，应使用二阶或更高阶有源滤波器，并结合过采样降低模拟滤波器陡峭度要求。

示例设计：

- 有效信号带宽：1 kHz。
- ADC 原始采样率：32 kSPS。
- 数字输出率：4 kSPS。
- 模拟低通截止频率：约 2 kHz。
- 数字 FIR：抑制 2~16 kHz 后执行 8 倍抽取。

#### 风险影响

- 高频开关噪声折叠到控制带宽。
- FFT 出现不存在的低频分量。
- 数字平均后仍有稳定偏差或拍频。
- 电机 PWM、DC/DC 开关频率形成伪信号。

---

### 9.7 DAC 直接驱动超出能力的负载

#### 错误代码

```
/* Directly drive a low-resistance or large-capacitance load. */
DAC1->DHR12R1 = requested_code;
```

#### 根因分析

片内 DAC 输出缓冲器通常存在：

- 最小负载电阻。
- 最大容性负载。
- 输出电流限制。
- 靠近电源轨时的摆幅限制。
- 建立时间和压摆率限制。

例如 DAC 输出 3 V，负载为 1 kΩ：

Iload=3V1kΩ=3mAIload​=1kΩ3V​=3mA

该电流可能超过片内缓冲器保证精度的能力。大电容还可能造成振荡或长时间建立。

#### 正确实现

```
MCU DAC
   │
   ├─ 小阻值隔离电阻
   │
   └─ 轨到轨运放缓冲
          ├─ 输出 RC 滤波
          ├─ 过压/ESD 保护
          └─ 负载
```

软件侧执行范围检查和斜率限制：

```
typedef struct {
    uint16_t current_code;
    uint16_t minimum_code;
    uint16_t maximum_code;
    uint16_t maximum_step;
} dac_slew_limiter_t;

static bool dac_set_limited(dac_slew_limiter_t *state,
                            uint16_t requested_code)
{
    if (state == NULL) {
        return false;
    }

    uint16_t target = requested_code;

    if (target < state->minimum_code) {
        target = state->minimum_code;
    } else if (target > state->maximum_code) {
        target = state->maximum_code;
    }

    if (target > state->current_code) {
        const uint32_t upper =
            (uint32_t)state->current_code + state->maximum_step;
        if ((uint32_t)target > upper) {
            target = (uint16_t)upper;
        }
    } else {
        const uint16_t delta = state->current_code - target;
        if (delta > state->maximum_step) {
            target = state->current_code - state->maximum_step;
        }
    }

    DAC1->DHR12R1 = target;
    state->current_code = target;
    return true;
}
```

#### 风险影响

- DAC 输出幅度偏低。
- 波形边沿失真。
- 运放或片内缓冲器振荡。
- 瞬态电流导致模拟电源扰动，反向污染 ADC。
- 外部执行器产生突变。

---

### 9.8 运行时直接修改 DAC DMA 查找表

#### 错误代码

```
for (size_t i = 0U; i < DAC_TABLE_SIZE; ++i) {
    g_dac_table[i] = generate_new_sample(i);
}
```

#### 根因分析

DMA 可能正在读取同一张表。CPU 更新期间，输出波形将同时包含：

- 尚未修改的旧数据。
- 已修改的新数据。
- Cache 中尚未写回的数据。

结果是非原子波形切换和不可预测的瞬态毛刺。

#### 正确实现

使用双缓冲，并只在确定的边界切换：

```
#define DAC_BUFFER_COUNT 2U
#define DAC_TABLE_SIZE   256U

__attribute__((aligned(32)))
static uint16_t g_dac_tables[DAC_BUFFER_COUNT][DAC_TABLE_SIZE];

typedef struct {
    uint8_t active;
    uint8_t pending;
    bool switch_requested;
} dac_buffer_state_t;

static dac_buffer_state_t g_dac_state;

static bool dac_prepare_waveform(const uint16_t *source, size_t count)
{
    if ((source == NULL) || (count != DAC_TABLE_SIZE) ||
        g_dac_state.switch_requested) {
        return false;
    }

    const uint8_t inactive = g_dac_state.active ^ 1U;

    for (size_t i = 0U; i < count; ++i) {
        g_dac_tables[inactive][i] =
            (source[i] <= 4095U) ? source[i] : 4095U;
    }

    dcache_clean_region(g_dac_tables[inactive],
                        sizeof(g_dac_tables[inactive]));

    g_dac_state.pending = inactive;
    g_dac_state.switch_requested = true;
    return true;
}

void dac_dma_transfer_complete_isr(void)
{
    if (g_dac_state.switch_requested) {
        dac_dma_select_memory(g_dac_state.pending);
        g_dac_state.active = g_dac_state.pending;
        g_dac_state.switch_requested = false;
    }
}
```

硬件支持 DMA 双缓冲模式时，应使用当前目标位判断 CPU 可以更新哪一块内存。

#### 风险影响

- 输出瞬态毛刺。
- 频谱产生宽带杂散。
- 功率驱动级受到异常阶跃冲击。
- 波形切换行为随 Cache 和 DMA 时序变化。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

典型工业数据链路：

```
统一硬件时基
├─ PWM 定时器比较事件
│   └─ ADC 精确相位触发
│       └─ ADC 多通道序列
│           └─ DMA Ping-Pong 缓冲
│               └─ Cache 一致性处理
│                   └─ 采集任务
│                       ├─ 原始数据合法性检查
│                       ├─ 偏置/增益校准
│                       ├─ 数字滤波与抽取
│                       ├─ 故障诊断
│                       └─ 控制算法
│                           └─ DAC/PWM 输出命令
│
└─ DAC 更新定时器
    └─ DMA 双缓冲
        └─ 模拟重构滤波器
```

该架构组合了：

- **定时器**：提供低抖动采样与输出时基。
- **ADC/DAC**：完成模拟域与数字域转换。
- **DMA**：降低 CPU 搬运开销。
- **双缓冲**：隔离生产者和消费者。
- **Cache/MPU**：保证数据一致性。
- **RTOS 通知**：完成 ISR 到任务的低开销调度。
- **校准与诊断**：保证工程量可信度。
- **模拟滤波器**：控制带外能量与 DAC 镜像频谱。

### 10.2 组合设计模式

推荐采用以下分层：

```
Application
  └─ Control / Measurement Service
      └─ Signal Processing
          └─ ADC/DAC Stream Manager
              └─ MCU HAL/LL/Register Driver
                  └─ ADC + DAC + DMA + Timer Hardware
```

职责边界：

|层级|负责内容|不应负责|
|---|---|---|
|硬件驱动|寄存器、校准、启动、停止、错误恢复|工程量换算|
|Stream Manager|缓冲所有权、序号、时间戳、丢块统计|业务判断|
|Signal Processing|校准、滤波、抽取、FFT|外设寄存器|
|Service|状态机、故障策略、参数管理|ISR 细节|
|Application|控制和业务逻辑|DMA Cache 维护|

### 10.3 完整代码框架

```
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>

#define ADC_CHANNEL_COUNT       3U
#define ADC_FRAMES_PER_BLOCK    128U
#define ADC_SAMPLES_PER_BLOCK   \
    (ADC_CHANNEL_COUNT * ADC_FRAMES_PER_BLOCK)
#define ADC_BUFFER_SAMPLES      (2U * ADC_SAMPLES_PER_BLOCK)

typedef enum {
    ANALOG_OK = 0,
    ANALOG_BAD_ARGUMENT,
    ANALOG_NOT_INITIALIZED,
    ANALOG_TIMEOUT,
    ANALOG_DMA_ERROR,
    ANALOG_OVERRUN,
    ANALOG_REFERENCE_ERROR
} analog_status_t;

typedef struct {
    int32_t current_ma;
    int32_t bus_mv;
    int32_t temperature_mc;
    uint32_t sequence;
    uint32_t timestamp_ticks;
} measurement_block_t;

typedef struct {
    atomic_uint_fast32_t ready_mask;
    atomic_uint_fast32_t dma_errors;
    atomic_uint_fast32_t overruns;
    atomic_bool running;
    uint32_t sequence;
} analog_stream_t;

__attribute__((section(".dma_buffer"), aligned(32)))
static uint16_t g_adc_dma_buffer[ADC_BUFFER_SAMPLES];

static analog_stream_t g_analog_stream;

static analog_status_t analog_hw_start(void)
{
    if (atomic_load_explicit(&g_analog_stream.running,
                             memory_order_acquire)) {
        return ANALOG_OK;
    }

    analog_status_t status = adc_hardware_calibrate();
    if (status != ANALOG_OK) {
        return status;
    }

    status = adc_dma_configure(g_adc_dma_buffer,
                               ADC_BUFFER_SAMPLES);
    if (status != ANALOG_OK) {
        return status;
    }

    status = adc_enable_external_trigger();
    if (status != ANALOG_OK) {
        adc_dma_stop();
        return status;
    }

    atomic_store_explicit(&g_analog_stream.ready_mask,
                          0U,
                          memory_order_relaxed);
    atomic_store_explicit(&g_analog_stream.running,
                          true,
                          memory_order_release);

    sampling_timer_start();
    return ANALOG_OK;
}

static void analog_hw_stop(void)
{
    sampling_timer_stop();
    adc_disable_trigger();
    adc_dma_stop();

    atomic_store_explicit(&g_analog_stream.running,
                          false,
                          memory_order_release);
}

static void analog_isr_publish(uint32_t mask)
{
    const uint32_t previous =
        (uint32_t)atomic_fetch_or_explicit(
            &g_analog_stream.ready_mask,
            mask,
            memory_order_release);

    if ((previous & mask) != 0U) {
        atomic_fetch_add_explicit(&g_analog_stream.overruns,
                                  1U,
                                  memory_order_relaxed);
    }

    acquisition_task_notify_from_isr();
}

void adc_dma_irq_handler(void)
{
    const uint32_t flags = adc_dma_get_flags();

    if ((flags & ADC_DMA_FLAG_ERROR) != 0U) {
        adc_dma_clear_flags(ADC_DMA_FLAG_ERROR);
        atomic_fetch_add_explicit(&g_analog_stream.dma_errors,
                                  1U,
                                  memory_order_relaxed);
        sampling_timer_stop_from_isr();
        acquisition_task_notify_from_isr();
    }

    if ((flags & ADC_DMA_FLAG_HALF) != 0U) {
        adc_dma_clear_flags(ADC_DMA_FLAG_HALF);
        analog_isr_publish(1U << 0);
    }

    if ((flags & ADC_DMA_FLAG_COMPLETE) != 0U) {
        adc_dma_clear_flags(ADC_DMA_FLAG_COMPLETE);
        analog_isr_publish(1U << 1);
    }
}

static analog_status_t analog_process_block(
    uint32_t half,
    measurement_block_t *output)
{
    if ((half > 1U) || (output == NULL)) {
        return ANALOG_BAD_ARGUMENT;
    }

    uint16_t *samples =
        &g_adc_dma_buffer[half * ADC_SAMPLES_PER_BLOCK];

    dcache_invalidate_region(
        samples,
        ADC_SAMPLES_PER_BLOCK * sizeof(samples[0]));

    int64_t current_sum = 0;
    int64_t voltage_sum = 0;
    int64_t temperature_sum = 0;

    for (size_t frame = 0U;
         frame < ADC_FRAMES_PER_BLOCK;
         ++frame) {
        const size_t base = frame * ADC_CHANNEL_COUNT;

        const uint16_t current_raw = samples[base + 0U];
        const uint16_t voltage_raw = samples[base + 1U];
        const uint16_t temp_raw    = samples[base + 2U];

        if ((current_raw > 4095U) ||
            (voltage_raw > 4095U) ||
            (temp_raw > 4095U)) {
            return ANALOG_DMA_ERROR;
        }

        current_sum += current_calibrate_ma(current_raw);
        voltage_sum += voltage_calibrate_mv(voltage_raw);
        temperature_sum += temperature_calibrate_mc(temp_raw);
    }

    output->current_ma =
        (int32_t)(current_sum / ADC_FRAMES_PER_BLOCK);
    output->bus_mv =
        (int32_t)(voltage_sum / ADC_FRAMES_PER_BLOCK);
    output->temperature_mc =
        (int32_t)(temperature_sum / ADC_FRAMES_PER_BLOCK);
    output->sequence = g_analog_stream.sequence++;
    output->timestamp_ticks = hardware_timestamp_get();

    return ANALOG_OK;
}

void acquisition_task(void *argument)
{
    (void)argument;

    measurement_block_t block;

    for (;;) {
        acquisition_task_wait_notification();

        if (atomic_load_explicit(&g_analog_stream.dma_errors,
                                 memory_order_relaxed) != 0U) {
            analog_hw_stop();
            diagnostics_report_adc_failure();

            if (analog_hw_start() != ANALOG_OK) {
                system_enter_degraded_mode();
            }
            continue;
        }

        const uint32_t ready =
            (uint32_t)atomic_exchange_explicit(
                &g_analog_stream.ready_mask,
                0U,
                memory_order_acquire);

        if ((ready & (1U << 0)) != 0U) {
            if (analog_process_block(0U, &block) == ANALOG_OK) {
                measurement_publish(&block);
            }
        }

        if ((ready & (1U << 1)) != 0U) {
            if (analog_process_block(1U, &block) == ANALOG_OK) {
                measurement_publish(&block);
            }
        }
    }
}
```

生产项目还应补充：

- DMA 错误后的外设复位序列。
- VREFINT 与温度监测。
- 参数 CRC 和版本检查。
- 缓冲块时间戳。
- 看门狗监督。
- 模拟输入开路、短路和越界诊断。
- 采样序列号连续性检查。

---

## 11. 工业级实际案例分析

### 11.1 电机控制中的相电流同步采样

#### 需求

- PWM：20 kHz。
- 双电阻或三电阻相电流采样。
- ADC 采样必须避开 MOSFET 开关边沿。
- 采样到控制输出总延迟小于一个 PWM 周期。
- 过流故障必须具有硬件快速关断路径。

#### 架构设计

```
中心对齐 PWM 定时器
├─ PWM 输出 -> 功率桥
├─ 比较事件 -> ADC 注入组触发
│              └─ 相电流采样
│                  └─ ADC JEOC ISR
│                      └─ Clarke/Park/PI/SVPWM
└─ 硬件 Break 输入 <- 比较器过流信号
```

采样点通常位于 PWM 有效矢量稳定区，而不是简单固定在周期中点。低占空比时可能没有足够的电流采样窗口，需要：

- 改变采样点。
- 使用双采样重构。
- 限制最小脉宽。
- 使用相电流传感器替代低侧分流方案。

#### 核心代码

```
void ADC_Injected_IRQHandler(void)
{
    const uint32_t isr = ADC1->ISR;

    if ((isr & ADC_ISR_JEOS) != 0U) {
        ADC1->ISR = ADC_ISR_JEOS;

        const int32_t ia =
            current_from_adc((uint16_t)ADC1->JDR1,
                             g_current_offset_a);
        const int32_t ib =
            current_from_adc((uint16_t)ADC1->JDR2,
                             g_current_offset_b);

        if ((abs_i32(ia) > CURRENT_TRIP_MA) ||
            (abs_i32(ib) > CURRENT_TRIP_MA)) {
            pwm_disable_outputs_immediately();
            fault_latch(FAULT_SOFTWARE_OVERCURRENT);
            return;
        }

        current_control_step(ia, ib);
    }

    if ((isr & ADC_ISR_JOVR) != 0U) {
        ADC1->ISR = ADC_ISR_JOVR;
        pwm_disable_outputs_immediately();
        fault_latch(FAULT_ADC_OVERRUN);
    }
}
```

#### 设计要点

- 硬件比较器与定时器 Break 负责最快过流保护，软件保护作为冗余。
- ADC 触发相位必须依据死区时间、放大器建立时间和开关振铃确定。
- ISR 最坏执行时间必须小于控制周期预算。
- 电流零偏应在无电流条件下统计，并监测温漂。
- 不在控制 ISR 内执行日志输出或 Flash 操作。

---

### 11.2 振动状态监测

#### 需求

- 4 通道同步或准同步采样。
- 每通道 25.6 kSPS。
- 有效频带 10 Hz~10 kHz。
- 每秒计算 RMS、峰值、峭度和频谱。
- 长时间运行不允许静默丢块。

#### 架构设计

```
IEPE/加速度传感器
  └─ 恒流源与模拟调理
      └─ 10 kHz 抗混叠低通
          └─ 同步 ADC
              └─ DMA 多缓冲
                  └─ 采集任务
                      ├─ 去直流
                      ├─ 窗函数
                      ├─ FFT
                      ├─ 特征提取
                      └─ 告警与存储
```

总数据率：

25.6k×4×2=204.8 kB/s25.6k×4×2=204.8 kB/s

若每块 4096 个交织样本：

Tblock=409625.6k×4=40msTblock​=25.6k×44096​=40ms

算法必须在平均 40 ms 内完成一个块的处理。

#### 核心代码

```
typedef struct {
    uint32_t sequence;
    uint32_t sample_rate_hz;
    uint16_t channel_count;
    uint16_t sample_count;
    const int16_t *samples;
} vibration_block_t;

static bool vibration_validate_sequence(uint32_t sequence)
{
    static uint32_t expected;
    static bool initialized;

    if (!initialized) {
        expected = sequence;
        initialized = true;
    }

    const bool valid = (sequence == expected);
    expected = sequence + 1U;
    return valid;
}

static void vibration_process(const vibration_block_t *block)
{
    if ((block == NULL) ||
        (block->samples == NULL) ||
        (block->channel_count != 4U) ||
        (block->sample_rate_hz != 25600U)) {
        diagnostics_report_configuration_error();
        return;
    }

    if (!vibration_validate_sequence(block->sequence)) {
        diagnostics_report_sample_gap(block->sequence);
        fft_state_reset();
    }

    signal_remove_dc(block);
    signal_apply_window(block);
    signal_fft_execute(block);
    signal_extract_features(block);
}
```

#### 设计要点

- 多通道相位分析要求同步采样 ADC；多路复用 ADC 会引入通道间时间偏差。
- FFT 测试应采用相干采样，不能满足时使用合适窗函数。
- 数据块必须携带序列号和硬件时间戳。
- 丢块后不得把不连续数据拼接为连续 FFT 窗口。
- 抗混叠滤波器的相位一致性也影响跨通道相位测量。

---

### 11.3 0~10 V 工业模拟量输出与回读诊断

#### 需求

- 输出范围：0~10 V。
- 控制分辨率：至少 12 bit。
- 负载：不低于 10 kΩ。
- 上电和通信丢失时进入安全输出值。
- 需要检测开路、短路和输出偏差。

#### 架构设计

```
MCU DAC / 外置 DAC
  └─ 低通滤波
      └─ 非反相运放，增益约 3.03
          ├─ 输出保护
          └─ 0~10 V 输出
                │
                └─ 分压回读 -> ADC -> 诊断比较
```

若 DAC 满量程为 3.3 V：

Gain=103.3≈3.03Gain=3.310​≈3.03

输出回读允许误差应包含：

- DAC 误差。
- 运放偏置与增益误差。
- 电阻网络误差。
- ADC 误差。
- 参考源误差。
- 温漂。
- 动态建立时间。

#### 核心代码

```
typedef enum {
    AO_DIAG_OK = 0,
    AO_DIAG_TRACKING_ERROR,
    AO_DIAG_SHORT_CIRCUIT,
    AO_DIAG_FEEDBACK_INVALID
} ao_diag_t;

static ao_diag_t analog_output_diagnose(int32_t command_mv,
                                        int32_t feedback_mv,
                                        uint32_t settling_elapsed_ms)
{
    if ((feedback_mv < -100) || (feedback_mv > 11000)) {
        return AO_DIAG_FEEDBACK_INVALID;
    }

    if (settling_elapsed_ms < AO_SETTLING_TIME_MS) {
        return AO_DIAG_OK;
    }

    const int32_t error_mv = abs_i32(command_mv - feedback_mv);
    const int32_t tolerance_mv =
        AO_FIXED_TOLERANCE_MV +
        (command_mv * AO_GAIN_TOLERANCE_PPM) / 1000000;

    if ((command_mv > 1000) &&
        (feedback_mv < AO_SHORT_THRESHOLD_MV)) {
        return AO_DIAG_SHORT_CIRCUIT;
    }

    if (error_mv > tolerance_mv) {
        return AO_DIAG_TRACKING_ERROR;
    }

    return AO_DIAG_OK;
}
```

#### 设计要点

- 命令变化后必须等待模拟链路建立，再执行跟踪诊断。
- 回读链路应尽可能独立，否则共同参考源故障可能无法检测。
- 安全输出不应只依赖任务调度，必要时使用外部硬件使能。
- 输出斜率限制应根据执行器安全要求设计。
- 短路保护需要硬件限流和热设计，软件检测不能替代硬件保护。

---

## 12. 高频问题深度答疑

### 12.1 12 bit ADC 为什么只能得到约 10 bit ENOB？

12 bit 只表示数字输出具有 4096 个码。ENOB 还受到以下因素影响：

- 量化噪声。
- ADC 比较器与采样网络噪声。
- 参考电压噪声。
- 时钟抖动。
- 电源与地噪声。
- 输入驱动失真。
- INL 和谐波失真。
- PCB 串扰。

动态 ENOB 应通过正弦输入的 SINAD 计算：

ENOB=SINAD−1.766.02ENOB=6.02SINAD−1.76​

直流输入的标准差只能描述短期噪声，不能覆盖谐波失真和 INL，因此不能替代动态 ENOB。

### 12.2 增加采样时间一定能提高精度吗？

不一定。

增加采样时间主要改善：

- 高源阻抗导致的建立误差。
- 多通道切换后的残余电荷问题。

它不能直接解决：

- 参考源噪声。
- ADC INL。
- 电源耦合。
- 时钟抖动。
- 模拟前端失真。
- PCB 布局问题。

采样时间过长还会降低吞吐率。应先计算最小建立时间，再保留适当裕量。

### 12.3 过采样能否把 12 bit ADC 变成 16 bit ADC？

理论上增加 4 bit 需要：

OSR=44=256OSR=44=256

但必须满足：

- 噪声能够覆盖多个量化阈值。
- 噪声近似不相关。
- 输入在累积窗口内足够稳定。
- ADC 的 INL 不成为限制。
- 参考源和模拟前端具有更高精度。
- 带宽和延迟允许 256 倍采样。

因此，过采样可以增加有效分辨率，但不能把低线性度 ADC 变成真正的高精度 16 bit ADC。

### 12.4 ADC 多通道扫描是否等于同步采样？

不等于。

多路复用 ADC 按顺序采样，各通道时间偏移约为：

Δt≈TconvΔt≈Tconv​

对频率为 `fin` 的正弦信号，时间偏差对应相位差：

Δϕ=360∘finΔtΔϕ=360∘fin​Δt

若 `fin=10 kHz`、通道间隔 `1 μs`：

Δϕ=3.6∘Δϕ=3.6∘

功率计算、三相电流、阵列传感器和振动相位分析可能无法接受。此时应选择同步采样 ADC、多个 ADC 同步触发或片内并行 ADC。

### 12.5 ADC DMA 是否一定不会丢数据？

不是。

DMA 只降低了 CPU 搬运压力，仍可能因以下原因丢数据：

- ADC overrun。
- DMA 总线仲裁延迟过大。
- DMA FIFO 或请求配置错误。
- 软件未及时释放缓冲区。
- Cache 一致性错误。
- 中断被长期屏蔽。
- 外设错误后 DMA 停止但软件未检测。

必须监测 ADC OVR、DMA TE/FE/DME、块序号和软件缓冲覆盖计数。

### 12.6 DAC 输出正弦波为什么频谱中存在镜像和毛刺？

DAC 查找表输出是离散时间序列经过零阶保持后的结果，其频谱会在采样频率整数倍附近产生镜像。幅频包络近似具有 sinc 特性。

此外，毛刺来自：

- 多位同时翻转时开关不同步。
- DMA 更新时序。
- 参考与电源耦合。
- 运放建立不足。
- 查找表量化。
- 相位累加器截断。

解决措施：

- 提高 DAC 更新率。
- 增大查找表或使用相位累加 DDS。
- 使用低毛刺 DAC。
- 添加模拟重构滤波器。
- 使用 DMA 保持均匀更新时间。
- 优化参考源和布局。

---

## 13. 课程核心总结

### 13.1 核心要点

1. ADC 精度由**完整模拟链路**决定，而不是只由标称位数决定。
2. 高阻输入必须依据 `Rs`、`Ron`、`Csh` 和目标分辨率计算采样时间。
3. 周期采样应使用**定时器硬件触发**，持续数据流应使用 DMA。
4. DMA 双缓冲必须建立明确的块所有权、覆盖检测和错误恢复。
5. Cortex-M7 等带 Cache 平台必须显式解决 DMA Cache 一致性。
6. 模拟抗混叠必须发生在采样之前，数字滤波不能消除已经发生的混叠。
7. 过采样只能在噪声、线性度、带宽和延迟条件成立时提高 ENOB。
8. DAC 输出需要考虑负载、建立时间、毛刺、重构滤波和安全状态。
9. 工业驱动必须提供超时、错误计数、时间戳、序列号和降级策略。
10. 控制系统中 ADC 触发、算法执行和 DAC/PWM 更新应基于统一硬件时基。

### 13.2 性能排序

#### CPU 效率

```
定时器 + DMA 块处理
    > 定时器 + 每序列中断
        > 每样本中断
            > 软件轮询
```

#### 采样时序确定性

```
硬件定时器触发
    > 外部同步信号触发
        > ISR 软件触发
            > RTOS 任务延时触发
```

#### 低频测量精度潜力

```
外置高精度 Sigma-Delta ADC
    > 外置精密 SAR ADC
        > MCU 内置 ADC + 优质模拟前端
            > 未校准 MCU ADC
```

#### DAC 输出精度潜力

```
外置精密 DAC + 独立参考 + 精密缓冲
    > MCU DAC + 缓冲与校准
        > PWM + 有源滤波
            > PWM + 简单 RC
```

### 13.3 通用选型结论

- **低速监控量**：定时器低频触发 ADC，DMA 或中断均可。
- **连续高吞吐采集**：定时器 + ADC + DMA 双缓冲。
- **闭环控制**：PWM 定时器相位触发 ADC，固定延迟执行算法。
- **高精度低带宽**：外置 Sigma-Delta ADC。
- **高带宽低延迟**：SAR ADC。
- **精密模拟输出**：外置 DAC、独立参考和输出回读。
- **成本敏感慢速输出**：PWM + RC，但必须量化纹波与建立时间。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐触发|搬运方式|关键约束|
|---|---|---|---|
|电池电压监控|低频定时器|中断或 DMA|分压阻抗、建立时间|
|温度采集|定时器|DMA|低通滤波、校准|
|电机相电流|PWM 比较事件|注入组 ISR/DMA|采样窗口、固定延迟|
|振动分析|定时器|DMA 双缓冲|抗混叠、连续性、FFT|
|多通道相位测量|同步触发|并行 ADC/DMA|通道间时差|
|24 bit 称重|DRDY|SPI DMA|数字滤波延迟、漂移|
|周期波形输出|定时器|DAC DMA|更新率、重构滤波|
|0~10 V 输出|定时器或软件命令|DAC/SPI|缓冲、保护、回读|
|慢速设定电压|PWM 定时器|硬件 PWM|纹波、响应时间|

### 14.2 特性对比表

|机制|优势|主要风险|必要措施|
|---|---|---|---|
|软件轮询|简单|CPU 占用高、抖动大|仅用于低速诊断|
|ADC 中断|响应快|高频中断负载|限制采样率|
|DMA 环形缓冲|吞吐高|覆盖与 Cache 问题|所有权和错误计数|
|双缓冲|处理与采集并行|块处理超时|WCET 分析|
|多通道扫描|节省 ADC|通道串扰、非同步|采样时间与排序|
|过采样|改善噪声分辨率|带宽与延迟下降|验证噪声和 INL|
|内部参考补偿|减少 VDDA 影响|校准常数使用错误|按芯片手册换算|
|DAC DMA|低 CPU 波形输出|表更新竞争|双缓冲与 Cache clean|
|PWM + RC|成本低|纹波与慢响应|量化 RC 和负载|
|外置 ADC/DAC|性能高|成本、接口和布局复杂|完整误差预算|

### 14.3 常用公式

|项目|公式|
|---|---|
|ADC 理想码|Code≈Vin(2N−1)/VrefCode≈Vin​(2N−1)/Vref​|
|ADC LSB|LSB=Vref/2NLSB=Vref​/2N|
|建立时间|Ts≥(Rs+Ron)Cshln⁡(2N+1)Ts​≥(Rs​+Ron​)Csh​ln(2N+1)|
|转换时间|Tconv=(Csample+Cconvert)/fADCTconv​=(Csample​+Cconvert​)/fADC​|
|定时器采样率|fs=fTIM/((PSC+1)(ARR+1))fs​=fTIM​/((PSC+1)(ARR+1))|
|数据带宽|BW=fs×Channels×BytesBW=fs​×Channels×Bytes|
|过采样率|OSR=4BOSR=4B|
|动态 ENOB|ENOB=(SINAD−1.76)/6.02ENOB=(SINAD−1.76)/6.02|
|抖动 SNR|SNR=−20log⁡10(2πfinσt)SNR=−20log10​(2πfin​σt​)|
|RC 截止频率|fc=1/(2πRC)fc​=1/(2πRC)|
|DAC 波形频率|fout=fupdate/Ntablefout​=fupdate​/Ntable​|

---

## 15. 学习效果自检

完成本课后，应能够独立确认以下能力：

- [ ]  能从 Datasheet 中找到 ADC 采样电容、输入开关电阻和允许源阻抗。
- [ ]  能计算指定分辨率下的最小采样时间。
- [ ]  能计算多通道序列的最大触发频率。
- [ ]  能配置定时器 TRGO 触发 ADC。
- [ ]  能实现 DMA 半满/满双缓冲处理。
- [ ]  能解释 `volatile` 为什么不能解决 Cache 一致性。
- [ ]  能正确区分 DMA 接收时的 invalidate 与发送时的 clean。
- [ ]  能通过覆盖计数检测软件处理不及时。
- [ ]  能设计模拟抗混叠和数字抽取的联合方案。
- [ ]  能区分分辨率、精度、SNR、SINAD 和 ENOB。
- [ ]  能使用 FFT 测量 ADC 的 SINAD、THD 和 ENOB。
- [ ]  能实现参考电压补偿和两点线性校准。
- [ ]  能判断多通道扫描是否满足同步采样要求。
- [ ]  能设计 DAC DMA 双缓冲波形更新。
- [ ]  能评估 DAC 输出负载和建立时间。
- [ ]  能为采集链路加入超时、错误计数、序列号和恢复状态机。
- [ ]  能对 ADC/DAC 链路建立完整的静态与动态误差预算。
- [ ]  能使用示波器验证采样触发相位和处理最坏执行时间。

---

## 16. 实践与进阶路径

### 16.1 第一阶段：基础寄存器驱动

#### 任务

1. 不依赖 HAL 实现单通道 ADC 轮询采样。
2. 完成 ADC 稳压器启动、校准、使能和超时处理。
3. 读取内部参考通道并估算 VDDA。
4. 将原始码转换为毫伏。
5. 故意缩短采样时间，观察高阻源的误差变化。

#### 验收指标

- 连续运行 24 小时无死循环。
- 所有硬件等待都有超时。
- 参考电压换算与高精度万用表偏差在既定误差预算内。
- 能解释实测偏差的主要来源。

### 16.2 第二阶段：定时器与 DMA 流式采集

#### 任务

1. 配置 4 通道、每通道 25 kSPS。
2. 使用定时器 TRGO 触发 ADC。
3. 使用 1024-sample DMA 环形缓冲。
4. 实现半满/满事件和覆盖计数。
5. 为每个处理块记录序列号和时间戳。
6. 在高 CPU 负载下验证是否丢块。

#### 验收指标

- 采样周期抖动由示波器或硬件事件引脚验证。
- 运行 1 小时无未报告的数据丢失。
- CPU 占用和最大处理时长有量化记录。
- DMA 错误注入后能够停止、复位并恢复。

### 16.3 第三阶段：信号质量与 ENOB 测试

#### 任务

1. 输入低失真正弦波。
2. 采集不少于 8192 点。
3. 实现去直流、窗函数和 FFT。
4. 计算 SNR、THD、SINAD 和 ENOB。
5. 对比不同采样时间、ADC 时钟和参考源。
6. 对比 PCB 上数字负载开启前后的频谱。

#### 测试要求

尽量使用相干采样：

finfs=MNfs​fin​​=NM​

其中 `M` 与 `N` 互质，N 为采样点数。不能相干采样时，应使用 Hann、Blackman-Harris 等窗函数，并修正窗函数的相干增益和等效噪声带宽。

#### 验收指标

- 结果中明确排除直流和基波 Bin。
- 谐波折叠位置计算正确。
- ENOB 由 SINAD 推导，而不是由标准差替代。
- 测试报告记录信号源、幅度、频率、采样率、参考源和供电条件。

### 16.4 第四阶段：ADC/DAC 闭环系统

#### 任务

1. DAC 通过 DMA 输出 1 kHz 正弦波。
2. 经模拟回路连接到 ADC。
3. ADC 与 DAC 使用关联硬件时基。
4. 在线估计幅值、直流偏置和相位延迟。
5. 运行中无毛刺切换波形频率和幅值。
6. 注入 DAC 负载异常并通过 ADC 回读检测。

#### 验收指标

- 波形切换仅发生在缓冲边界。
- 输出频率误差符合定时器时钟精度。
- 回读诊断考虑模拟建立时间。
- 输出越界、短路和 DMA 错误均进入定义明确的安全状态。

### 16.5 性能测试方法

#### GPIO 时序测量

在关键路径翻转 GPIO：

```
static inline void trace_processing_begin(void)
{
    TRACE_GPIO->BSRR = TRACE_PIN;
}

static inline void trace_processing_end(void)
{
    TRACE_GPIO->BSRR = (uint32_t)TRACE_PIN << 16U;
}
```

通过示波器测量：

- ADC 触发到 DMA 完成的延迟。
- 任务唤醒延迟。
- 数据块处理时间。
- 最坏执行时间。
- DAC 更新到模拟输出稳定的时间。

#### DWT 周期计数

```
static void cycle_counter_enable(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t measure_processing_cycles(void)
{
    const uint32_t start = DWT->CYCCNT;
    process_adc_data();
    return DWT->CYCCNT - start;
}
```

测量时应覆盖：

- Cache 命中与未命中。
- 最大通道数。
- 最复杂滤波路径。
- 高优先级中断干扰。
- RTOS 调度与临界区。
- Flash 与 SRAM 中执行代码的差异。

### 16.6 进阶学习方向

1. **精密模拟前端**：仪表放大器、低噪声设计、Kelvin 连接、参考源缓冲。
2. **高速数据转换**：差分 ADC 驱动、LVDS、JESD204、时钟树和孔径抖动。
3. **Sigma-Delta ADC**：调制器、噪声整形、sinc 滤波器和群延迟。
4. **同步采样系统**：多 ADC 时钟同步、相位校准和确定性延迟。
5. **数字信号处理**：FIR/IIR、抽取、插值、FFT、定点量化分析。
6. **电机控制采样**：单/双/三电阻电流重构、PWM 中点采样和死区补偿。
7. **功能安全**：ADC 冗余、合理性检查、潜伏故障检测和安全输出路径。
8. **EMC 与 PCB**：参考回流、模拟数字分区、滤波器布局和开关节点隔离。
9. **自动化测试**：信号源控制、频谱指标计算、温箱校准和产线参数烧录。
10. **驱动架构**：异步 Stream API、零拷贝缓冲池、错误恢复和可观测性设计。
