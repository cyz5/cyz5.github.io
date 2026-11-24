
## 1. 学习目标

### 理解

- 理解 **TCM（Tightly Coupled Memory）** 是与 Cortex-M 内核紧耦合、可预测低延迟访问的专用存储通路。
- 区分 **ITCM、DTCM、Cache、SRAM、Flash、AXI/AHB 总线存储器** 的硬件定位。

### 掌握

- 能够通过链接脚本将关键代码、栈、控制环变量、DMA 描述符等放入正确的内存区域。
- 能够完成启动阶段 TCM 初始化、代码搬运、Cache 与 DMA 一致性处理。

### 精通

- 能够分析 Cortex-M7/M55 等内核中取指、数据访问、Cache、总线仲裁对实时性的影响。
- 能够量化 TCM 对中断响应、控制周期抖动、算法吞吐量的收益。

### 能够设计

- 能够为电机控制、工业通信、边缘 AI、音频处理等系统设计 **Flash + AXI SRAM + ITCM + DTCM + DMA Buffer** 的分层内存架构。

---

## 2. 前置要求

### 知识要求

- ARM Cortex-M 异常模型、NVIC、MPU、Cache 基础。
- ELF 文件、段（`.text`、`.data`、`.bss`、`NOLOAD`）与链接脚本概念。
- AHB/AXI 总线、DMA、存储器映射基础。
- C 语言对象生命周期、`volatile`、内存屏障。

### 技能要求

- 能够阅读 CMSIS 启动文件和 GCC/ARMCC 链接脚本。
- 能够使用 `objdump`、`nm`、map 文件确认符号地址。
- 能够通过 DWT Cycle Counter 或 GPIO 测量执行时间。
- 能够调试 Cache/DMA 数据不一致问题。

---

## 3. 技术概述

TCM 是直接服务于 CPU 内核的片上存储区域。其核心价值不是“容量大”，而是提供：

- **固定且极低的访问延迟**
- **不依赖共享总线仲裁**
- **通常不经过 D-Cache / I-Cache**
- **更强的时间确定性**
- **指令访问与数据访问可并行**

典型实现：

|类型|服务对象|典型用途|典型特性|
|---|---|---|---|
|ITCM|指令取指通路|中断服务、控制算法、DSP 内核|固定低延迟取指|
|DTCM|数据访问通路|栈、控制状态、热数据|固定低延迟读写|
|Cache|通用存储器访问加速|Flash、AXI SRAM、外部 RAM|命中快，未命中不可预测|
|AXI SRAM|系统共享 SRAM|大数组、帧缓存、DMA 缓冲区|可被 DMA/外设访问，存在仲裁|
|Flash|非易失程序存储|固件主体、常量表|访问受 Wait State/Cache 影响|

> **关键结论：TCM 是 CPU 局部低抖动存储，不是所有主设备都可访问的共享 RAM。**

---

## 4. 核心特性横向对比

以下以常见 Cortex-M7 SoC，例如 STM32H7、NXP i.MX RT 系列的实现特征为参考。实际地址、容量、DMA 可见性必须以芯片参考手册为准。

|维度|ITCM|DTCM|AXI SRAM|Flash + I-Cache|外部 SDRAM/OSPI|
|---|---|---|---|---|---|
|CPU 访问延迟|通常 0~1 Cycle|通常 0~1 Cycle|受总线影响|Cache 命中低，失效高|高且波动大|
|访问确定性|极高|极高|中等|中等|低|
|指令执行|最优|不适合|可执行但不优先|常规方案|通常不建议|
|数据访问|不推荐|最优|良好|只读常量适用|大容量数据|
|是否依赖 Cache|通常否|通常否|通常需要|是|强依赖|
|DMA 可访问性|多数芯片不可见|多数芯片不可见|通常可见|不适用|通常可见|
|适合对象|ISR、控制核心函数|栈、热变量、FPU/DSP 工作区|DMA 缓冲、消息队列、大数组|普通业务代码|图像、模型、文件缓存|
|容量|小|小|中等|大|大|
|主要风险|容量耗尽|DMA 不可见、栈溢出|Cache 一致性|Miss 抖动|带宽与延迟抖动|

---

## 5. 底层原理与功能特性深度解析

### 5.1 TCM 与 Cortex-M 访问通路

在典型 Cortex-M7 实现中，处理器存在独立的取指与数据访问能力：

```
+---------------------------+
                  |       Cortex-M Core       |
                  |                           |
                  |  I-Code / ITCM Interface  +------> ITCM
                  |  D-Code / DTCM Interface  +------> DTCM
                  |  System AXI/AHB Interface +------> AXI SRAM / Flash / SDRAM
                  |                           |
                  |       I-Cache / D-Cache   |
                  +---------------------------+
```

TCM 的核心不是单纯“快”，而是 CPU 不必等待：

```
CPU 发起 DTCM 访问
    |
    +--> 直接命中 DTCM 端口
    |
    +--> 无 AXI 仲裁
    +--> 无 DMA 抢占
    +--> 无 Cache Miss 回填
    |
    +--> 固定时延返回
```

而 AXI SRAM 访问可能经过：

```
CPU -> D-Cache 查询
    |
    +--> Cache Hit: 快
    |
    +--> Cache Miss:
          CPU -> AXI Matrix -> SRAM/Flash/SDRAM
                              ^
                              |
                      DMA / LCD / Ethernet / USB 等主机竞争
```

因此，Cache 的平均性能可能很高，但最坏情况延迟不稳定；TCM 更适合硬实时路径。

---

### 5.2 ITCM：关键代码放置

对于控制循环、中断服务函数、短小高频 DSP 函数，可将代码放入 ITCM。

```
#include <stdint.h>

#if defined(__GNUC__)
#define ITCM_CODE __attribute__((section(".itcm_text"), noinline))
#elif defined(__ICCARM__)
#define ITCM_CODE _Pragma("location=\"ITCM_CODE\"")
#else
#define ITCM_CODE
#endif

static volatile uint32_t g_control_tick;

/* 放入 ITCM，避免 Flash 等待周期和 I-Cache Miss 造成控制周期抖动。 */
ITCM_CODE void MotorControl_FastLoop(void)
{
    g_control_tick++;

    /* 生产工程中应避免在高频路径调用不可预测的库函数。 */
    __asm volatile ("nop");
}
```

GCC 链接脚本示例：

```
MEMORY
{
    FLASH     (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
    ITCMRAM   (xrw) : ORIGIN = 0x00000000, LENGTH = 64K
    DTCMRAM   (xrw) : ORIGIN = 0x20000000, LENGTH = 128K
    AXIRAM    (xrw) : ORIGIN = 0x24000000, LENGTH = 512K
}

.itcm_text :
{
    . = ALIGN(32);
    __itcm_text_start__ = .;
    *(.itcm_text)
    *(.itcm_text*)
    . = ALIGN(32);
    __itcm_text_end__ = .;
} > ITCMRAM AT > FLASH

__itcm_text_load__ = LOADADDR(.itcm_text);
```

启动代码必须将 Flash 中的镜像复制到 ITCM：

```
#include <stddef.h>
#include <stdint.h>

extern uint32_t __itcm_text_load__;
extern uint32_t __itcm_text_start__;
extern uint32_t __itcm_text_end__;

static void CopySection(uint32_t *dst, const uint32_t *src, const uint32_t *end)
{
    while (dst < end) {
        *dst++ = *src++;
    }
}

void RuntimeMemoryInit(void)
{
    CopySection(
        &__itcm_text_start__,
        &__itcm_text_load__,
        &__itcm_text_end__);
}
```

必须保证 `RuntimeMemoryInit()` 在调用任何 `.itcm_text` 函数前执行。

---

### 5.3 DTCM：栈与热数据放置

DTCM 的高价值对象包括：

- 中断栈、主栈、任务栈。
- 控制器状态，例如 PID 积分项、滤波器状态。
- 高频查表算法的工作集。
- FFT、FIR 的短工作缓冲区。
- 高频访问的消息元数据。

```
#include <stdint.h>

#define DTCM_DATA __attribute__((section(".dtcm_data")))
#define DTCM_BSS  __attribute__((section(".dtcm_bss")))

typedef struct {
    float kp;
    float ki;
    float kd;
    float integrator;
    float previous_error;
    float output_min;
    float output_max;
} PidController;

static DTCM_DATA PidController g_current_pid = {
    .kp = 0.15f,
    .ki = 0.02f,
    .kd = 0.001f,
    .output_min = -1.0f,
    .output_max = 1.0f,
};

static DTCM_BSS float g_filter_state[64];

float PidController_Update(PidController *pid, float reference, float feedback, float dt)
{
    float error = reference - feedback;
    float derivative;
    float output;

    if (dt <= 0.0f) {
        return 0.0f;
    }

    pid->integrator += error * dt;
    derivative = (error - pid->previous_error) / dt;

    output = pid->kp * error
           + pid->ki * pid->integrator
           + pid->kd * derivative;

    if (output > pid->output_max) {
        output = pid->output_max;
    } else if (output < pid->output_min) {
        output = pid->output_min;
    }

    pid->previous_error = error;
    return output;
}
```

DTCM 的典型工程边界：**CPU 可访问不代表 DMA 可访问。** 在许多 MCU 中，DMA、以太网 MAC、USB、LCD 控制器只能访问 AXI SRAM、AHB SRAM 或外部 RAM，不能访问 DTCM。

---

### 5.4 TCM 与 Cache 的关系

TCM 常被设计为非 Cacheable，因为它本身已经具备低延迟确定性。将数据放入 DTCM 后：

- 不会发生 D-Cache Miss。
- 不需要因 DMA 而执行 Cache Clean/Invalidate。
- 但 DMA 也可能根本无法访问该内存。
- 若 MPU 配置错误，可能导致访问属性与芯片预期不一致。

Cache 与 DMA 的标准处理流程：

```
#include "core_cm7.h"

void EthTxPrepare(void *buffer, uint32_t length)
{
    uintptr_t start = (uintptr_t)buffer;
    uintptr_t aligned_start = start & ~(uintptr_t)31U;
    uint32_t aligned_length =
        (uint32_t)(((start + length + 31U) & ~(uintptr_t)31U) - aligned_start);

    SCB_CleanDCache_by_Addr((uint32_t *)aligned_start, (int32_t)aligned_length);
    __DSB();
}

void EthRxComplete(void *buffer, uint32_t length)
{
    uintptr_t start = (uintptr_t)buffer;
    uintptr_t aligned_start = start & ~(uintptr_t)31U;
    uint32_t aligned_length =
        (uint32_t)(((start + length + 31U) & ~(uintptr_t)31U) - aligned_start);

    SCB_InvalidateDCache_by_Addr((uint32_t *)aligned_start, (int32_t)aligned_length);
    __DSB();
    __ISB();
}
```

对于 DMA 缓冲区，更优选的结构通常是：

```
DTCM:
├── RTOS 任务栈
├── ISR 私有状态
├── PID/FIR 状态
└── 实时控制变量

AXI SRAM（Non-cacheable MPU Region）:
├── Ethernet Rx/Tx Descriptor
├── Ethernet Frame Buffer
├── USB DMA Buffer
└── ADC DMA Ping-Pong Buffer

ITCM:
├── 高频 ISR
├── 电流环/速度环
├── 快速数学内核
└── 时间敏感协议状态机
```

---

### 5.5 MPU 对 TCM 的保护设计

对于安全或高可靠系统，应通过 MPU 控制 TCM 区域权限。

```
#include "core_cm7.h"

static void MpuConfigureDmaBufferRegion(void)
{
    MPU_Region_InitTypeDef region = {0};

    HAL_MPU_Disable();

    region.Enable = MPU_REGION_ENABLE;
    region.Number = MPU_REGION_NUMBER4;
    region.BaseAddress = 0x24000000U;
    region.Size = MPU_REGION_SIZE_32KB;
    region.SubRegionDisable = 0x00U;
    region.TypeExtField = MPU_TEX_LEVEL1;
    region.AccessPermission = MPU_REGION_FULL_ACCESS;
    region.DisableExec = MPU_INSTRUCTION_ACCESS_DISABLE;
    region.IsShareable = MPU_ACCESS_SHAREABLE;
    region.IsCacheable = MPU_ACCESS_NOT_CACHEABLE;
    region.IsBufferable = MPU_ACCESS_BUFFERABLE;

    HAL_MPU_ConfigRegion(&region);
    HAL_MPU_Enable(MPU_PRIVILEGED_DEFAULT);
}
```

实际 MPU 宏、属性编码依赖厂商 HAL/CMSIS 版本。设计目标是：

- TCM：仅 CPU 访问，高优先级实时对象。
- DMA 区：设备与 CPU 共享，通常标记为 **Non-cacheable**。
- 普通 AXI SRAM：Cacheable，承载一般应用数据。
- 代码区：只读、可执行。
- DMA 描述符区：禁止执行。

---

## 6. 性能量化分析

### 6.1 测试平台与边界

以下数据为典型 Cortex-M7、480 MHz、片内 Flash 启用 ART/I-Cache、D-Cache 使能、AXI 总线存在 DMA 竞争时的**代表性量级**。不同芯片、编译器优化等级、Cache 状态和总线负载下结果会不同，必须在目标硬件上复测。

### 6.2 测量方法

使用 DWT Cycle Counter：

```
#include "core_cm7.h"
#include <stdint.h>

static void CycleCounter_Init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t CycleCounter_Begin(void)
{
    return DWT->CYCCNT;
}

static uint32_t CycleCounter_Elapsed(uint32_t start)
{
    return DWT->CYCCNT - start;
}
```

时间换算公式：

```
执行时间(ns) = 周期数 / CPU频率(Hz) × 10^9

480 MHz 时：
1 Cycle = 1 / 480,000,000 s = 2.083 ns
```

### 6.3 典型性能数据

|操作|ITCM/DTCM|AXI SRAM，Cache Hit|AXI SRAM，Cache Miss|Flash，I-Cache Hit|Flash，I-Cache Miss|
|---|---|---|---|---|---|
|32-bit 单次访问|1~2 Cycle|1~3 Cycle|8~30 Cycle|不适用|不适用|
|64 B 顺序读取|16~32 Cycle|16~40 Cycle|50~120 Cycle|不适用|不适用|
|短 ISR 取指|稳定|稳定性中等|不适用|稳定|首次/冲突有抖动|
|1 KB 数据处理|高确定性|平均高吞吐|取决于回填|代码适用|代码抖动较明显|
|DMA 并发影响|通常无|可能显著|显著|可能影响取指|可能影响取指|

示例：一个 20 kHz 电流环周期为：

```
周期 = 1 / 20,000 = 50 us

480 MHz 可用周期数：
480,000,000 × 50 us = 24,000 Cycle
```

若控制函数在 Flash 中偶发增加 300 Cycle：

```
时间抖动 = 300 / 480 MHz = 625 ns
相对于 50 us 周期 = 1.25%
```

对一般应用可能可接受，但对于高带宽电流环、同步采样窗、精密 PWM 更新，抖动会直接转化为控制误差。将关键路径放到 ITCM 后，通常能将这类由取指 Miss 或总线竞争引入的抖动压缩到极低水平。

### 6.4 优化收益排序

|优化措施|典型收益|适用条件|风险|
|---|---|---|---|
|高频 ISR 放入 ITCM|降低最坏执行时间和抖动|ISR 代码小且高频|ITCM 容量不足|
|任务栈放入 DTCM|降低上下文切换和局部变量访问波动|RTOS 高频切换|DMA 不可访问|
|热状态放入 DTCM|降低控制算法访问延迟|小工作集高复用|过度分配|
|DMA Buffer 放入非缓存 AXI SRAM|消除 Cache 一致性问题|Ethernet/USB/ADC DMA|CPU 访问略慢|
|普通数据保留 Cacheable AXI SRAM|提升平均吞吐|大数据、非硬实时|Cache Miss 抖动|
|代码全部放 ITCM|通常不推荐|极小型实时固件|浪费容量，启动复制时间增加|

---

## 7. 应用场景选型指南

### 决策流程图

```
开始
|
+-- 是否存在硬实时路径，且最坏延迟比平均性能更重要？
|   |
|   +-- 是
|   |   |
|   |   +-- 是高频代码或 ISR？
|   |   |   +-- 是 -> ITCM
|   |   |   +-- 否 -> 继续判断数据特性
|   |   |
|   |   +-- 是 CPU 私有高频状态、栈或小工作集？
|   |       +-- 是 -> DTCM
|   |       +-- 否 -> AXI SRAM，必要时 MPU 非缓存配置
|   |
|   +-- 否
|       |
|       +-- 是否由 DMA/以太网/USB/LCD 访问？
|       |   +-- 是 -> DMA 可达 SRAM，优先 Non-cacheable 区
|       |   +-- 否 -> Cacheable AXI SRAM
|       |
|       +-- 是否是大容量只读模型、图像、文件缓存？
|           +-- 是 -> 外部 RAM / OSPI Flash + Cache
|           +-- 否 -> 普通 SRAM / Flash
```

|场景|推荐方案|理由|
|---|---|---|
|20~100 kHz 电机电流环|ISR 与控制算法放 ITCM；状态放 DTCM|最小化控制抖动|
|FreeRTOS 高频任务切换|ISR 栈、关键任务栈放 DTCM|降低栈访问和上下文切换开销|
|Ethernet TCP/IP|描述符与帧缓冲放非缓存 AXI SRAM|DMA 可访问，避免 Cache 一致性错误|
|ADC 连续采样|Ping-Pong Buffer 放 DMA SRAM；滤波状态放 DTCM|DMA 与 CPU 职责分离|
|摄像头/LCD|帧缓冲放外部 SDRAM 或 AXI SRAM|TCM 容量与可见性不匹配|
|CMSIS-NN 小模型推理|内核代码放 ITCM；激活热点放 DTCM；权重放 Flash/OSPI|提升热点路径确定性|
|工业协议网关|协议 ISR 放 ITCM；DMA Buffer 放共享 SRAM|平衡实时性与外设访问|

---

## 8. 工程最佳实践

### 设计原则

1. **以最坏执行时间（WCET）作为 TCM 分配依据，不以平均耗时作为依据。**
2. **ITCM 只存放短小、频繁、确定性敏感的代码。**
3. **DTCM 只存放 CPU 私有的热数据、栈和状态。**
4. **DMA 访问对象默认不能放 DTCM，除非芯片手册明确说明可达。**
5. **不要将所有变量放入 DTCM。** 这会导致容量失控，且降低共享资源可用性。
6. 通过 map 文件和启动日志验证实际地址，不能只相信段名。
7. 所有 DMA Buffer 按 Cache Line 对齐，Cortex-M7 常见为 **32 Byte**。
8. 对共享数据使用 Cache 维护或 MPU Non-cacheable 区域，两者必须有明确策略，禁止混用而无边界。

### 选型决策矩阵

|对象特征|ITCM|DTCM|Cacheable AXI SRAM|Non-cacheable DMA SRAM|
|---|---|---|---|---|
|高频 ISR 代码|推荐|不适用|可用|不推荐|
|控制器状态|不适用|推荐|可用|不推荐|
|RTOS 任务栈|不适用|推荐|可用|不推荐|
|Ethernet 描述符|不适用|禁止|风险高|推荐|
|Ethernet 帧数据|不适用|禁止|可用但需维护 Cache|推荐|
|ADC DMA Buffer|不适用|禁止|可用但需维护 Cache|推荐|
|大型 FFT 缓冲|不适用|容量允许时可用|推荐|仅 DMA 场景推荐|
|神经网络权重|不适用|不推荐|可用|不推荐|

### 工业级编码规范

```
#define DMA_ALIGNMENT 32U

#define DMA_BUFFER \
    __attribute__((section(".dma_buffer"), aligned(DMA_ALIGNMENT)))

typedef struct {
    uint8_t data[1536];
} EthFrame;

static DMA_BUFFER EthFrame g_rx_frames[8];

/* 编译期检查：DMA 缓冲区必须满足 Cache Line 对齐要求。 */
_Static_assert((sizeof(EthFrame) % DMA_ALIGNMENT) == 0U,
               "DMA frame size must be cache-line aligned");
```

避免将内存布局决策散落在业务代码中。建议统一由 `memory_layout.h` 管理：

```
#ifndef MEMORY_LAYOUT_H
#define MEMORY_LAYOUT_H

#if defined(__GNUC__)
#define MEM_ITCM_CODE      __attribute__((section(".itcm_text"), noinline))
#define MEM_DTCM_DATA      __attribute__((section(".dtcm_data")))
#define MEM_DTCM_BSS       __attribute__((section(".dtcm_bss")))
#define MEM_DMA_BUFFER     __attribute__((section(".dma_buffer"), aligned(32)))
#else
#define MEM_ITCM_CODE
#define MEM_DTCM_DATA
#define MEM_DTCM_BSS
#define MEM_DMA_BUFFER
#endif

#endif
```

---

## 9. 常见错误与避坑指南

### 错误 1：将 DMA 缓冲区放入 DTCM

错误代码：

```
static __attribute__((section(".dtcm_bss")))
uint8_t g_eth_rx_buffer[1536];
```

根因分析：

- DTCM 通常仅连接 CPU 内核端口。
- Ethernet DMA 主机可能无法寻址或访问 DTCM。
- 表现可能是 DMA 不触发、总线错误、接收帧全零或随机丢包。

正确实现：

```
static __attribute__((section(".dma_buffer"), aligned(32)))
uint8_t g_eth_rx_buffer[1536];
```

风险影响：

- 网络通信随机失效。
- DMA 错误中断。
- 工业现场出现低概率、难复现的协议掉线。

---

### 错误 2：ITCM 段未从 Flash 复制

错误代码：

```
.itcm_text :
{
    *(.itcm_text*)
} > ITCMRAM AT > FLASH
```

仅有链接脚本，没有启动拷贝逻辑。

根因分析：

- `AT > FLASH` 只规定镜像加载地址。
- 上电后 ITCM RAM 未必自动包含代码运行内容。
- CPU 跳转到 ITCM 函数时可能执行零值、垃圾数据或触发 HardFault。

正确实现：

```
extern uint32_t __itcm_text_load__;
extern uint32_t __itcm_text_start__;
extern uint32_t __itcm_text_end__;

void CopyItcmText(void)
{
    uint32_t *dst = &__itcm_text_start__;
    const uint32_t *src = &__itcm_text_load__;

    while (dst < &__itcm_text_end__) {
        *dst++ = *src++;
    }

    __DSB();
    __ISB();
}
```

风险影响：

- 早期启动 HardFault。
- 仅在冷启动失败、调试器下载后偶尔正常的“假象”。

---

### 错误 3：DMA 完成后未失效 D-Cache

错误代码：

```
void AdcDmaCompleteCallback(void)
{
    ProcessSamples(g_adc_buffer, 256U);
}
```

根因分析：

- CPU 可能仍读取 D-Cache 中 DMA 开始前的旧数据。
- DMA 直接写 SRAM，不会更新 CPU Cache。

正确实现：

```
void AdcDmaCompleteCallback(void)
{
    SCB_InvalidateDCache_by_Addr(
        (uint32_t *)g_adc_buffer,
        sizeof(g_adc_buffer));
    __DSB();

    ProcessSamples(g_adc_buffer, 256U);
}
```

风险影响：

- ADC 数据周期性重复。
- 音频爆音、控制环使用旧采样值。
- 网络接收包内容错误。

---

### 错误 4：将过大的普通数据放入 DTCM

错误代码：

```
static __attribute__((section(".dtcm_bss")))
uint8_t g_large_frame_buffer[1280U * 720U * 2U];
```

根因分析：

- 图像帧约为 `1,843,200 Byte`。
- DTCM 常见容量只有几十 KB 到数百 KB。
- 链接可能直接失败，或覆盖其他段。

正确实现：

```
static __attribute__((section(".framebuffer"), aligned(32)))
uint8_t g_large_frame_buffer[1280U * 720U * 2U];
```

风险影响：

- 链接失败。
- 栈空间被挤压。
- 系统运行后异常复位。

---

### 错误 5：把所有函数放入 ITCM

错误代码：

```
#define FAST_CODE __attribute__((section(".itcm_text")))

FAST_CODE void AppMainLoop(void);
FAST_CODE void TcpIpStackProcess(void);
FAST_CODE void FileSystemProcess(void);
FAST_CODE void UiRender(void);
```

根因分析：

- ITCM 是稀缺资源。
- 大量低频代码会挤占关键 ISR 的空间。
- 启动复制时间增加，固件维护成本升高。

正确实现：

```
MEM_ITCM_CODE void PwmUpdateIsr(void);
MEM_ITCM_CODE void CurrentLoopStep(void);

void TcpIpStackProcess(void);
void FileSystemProcess(void);
void UiRender(void);
```

风险影响：

- 最关键代码无法部署到 ITCM。
- 实时性问题从“可优化”变成“容量不可满足”。

---

## 10. 多机制组合使用方案

### 技术协同架构

```
+----------------------+
                         |      Flash / OSPI     |
                         | 固件主体、常量、权重 |
                         +----------+-----------+
                                    |
                                    v
+------------------+       +------------------+
|      ITCM        |       |      DTCM        |
| PWM ISR          |       | ISR/Task Stack   |
| 电流环           |       | PID/FIR 状态     |
| 快速协议状态机   |       | 热点工作集       |
+------------------+       +------------------+
                                    |
                                    v
                         +----------------------+
                         | Cacheable AXI SRAM   |
                         | 普通任务数据         |
                         | 大型算法缓存         |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Non-cacheable SRAM  |
                         | ADC/Ethernet/USB DMA |
                         | DMA Descriptor       |
                         +----------------------+
```

### 完整代码框架

```
#include <stdint.h>
#include <stdbool.h>
#include "memory_layout.h"

typedef struct {
    float ia;
    float ib;
    float ic;
} PhaseCurrent;

typedef struct {
    float duty_a;
    float duty_b;
    float duty_c;
} PwmDuty;

static MEM_DTCM_DATA PhaseCurrent g_phase_current;
static MEM_DTCM_DATA PwmDuty g_pwm_duty;

/* DMA 可访问区域，禁止放入 DTCM。 */
static MEM_DMA_BUFFER uint16_t g_adc_dma_buffer[6];

static void AdcSamplesToCurrent(const uint16_t *samples, PhaseCurrent *current)
{
    const float scale = 0.001f;

    current->ia = ((float)samples[0] - 2048.0f) * scale;
    current->ib = ((float)samples[1] - 2048.0f) * scale;
    current->ic = ((float)samples[2] - 2048.0f) * scale;
}

MEM_ITCM_CODE void MotorPwmIsr(void)
{
    /* DMA 缓冲区处于 Non-cacheable SRAM 时无需 Cache Invalidate。 */
    AdcSamplesToCurrent(g_adc_dma_buffer, &g_phase_current);

    g_pwm_duty.duty_a = g_phase_current.ia * 0.1f;
    g_pwm_duty.duty_b = g_phase_current.ib * 0.1f;
    g_pwm_duty.duty_c = g_phase_current.ic * 0.1f;

    /* 此处调用寄存器级 PWM Compare 更新函数。 */
}
```

组合设计模式：

|机制|职责|
|---|---|
|ITCM|承担高频、低抖动指令路径|
|DTCM|承担 CPU 私有热数据和栈|
|DMA SRAM|承担外设与 CPU 共享数据|
|MPU|定义缓存性、执行权限、访问权限|
|D-Cache Maintenance|支持必须位于 Cacheable SRAM 的 DMA 数据|
|DWT|持续测量 WCET、周期抖动和性能回归|

---

## 11. 工业级实际案例分析

### 案例 1：伺服驱动器 40 kHz 电流环

#### 需求

- 控制周期：25 us。
- PWM 更新必须在 ADC 同步采样后限定窗口内完成。
- 最坏执行时间必须小于 12 us。
- 同时运行 CANopen/Ethernet 工业通信。

#### 架构设计

```
ITCM:
- ADC DMA 完成 ISR
- Clarke/Park 变换
- PI 电流环
- SVPWM

DTCM:
- 电流环状态
- 角度状态
- PI 积分项
- ISR 栈

AXI SRAM:
- 通信协议栈数据
- 诊断日志
- 参数管理

DMA SRAM:
- ADC 双缓冲
- Ethernet DMA 描述符
- Ethernet Rx/Tx Buffer
```

核心代码：

```
MEM_ITCM_CODE void AdcInjectedDmaIsr(void)
{
    const uint16_t *adc = g_adc_dma_buffer;
    float ia = ((float)adc[0] - 2048.0f) * 0.01f;
    float ib = ((float)adc[1] - 2048.0f) * 0.01f;

    CurrentLoop_Execute(ia, ib);
    Pwm_CommitShadowRegisters();
}
```

设计要点：

- ISR 的所有直接调用函数必须检查 map 文件，避免部分函数仍留在 Flash。
- 避免 ISR 内日志、动态内存、锁竞争、复杂协议栈调用。
- 将通信任务与控制 ISR 的内存和总线访问隔离。

---

### 案例 2：工业以太网网关

#### 需求

- 支持 Ethernet DMA、TCP/IP、Modbus TCP。
- 数据包接收不能丢帧。
- 控制报文具有较低处理抖动。
- CPU 开启 D-Cache 提升协议吞吐量。

#### 架构设计

```
DTCM:
- FreeRTOS 高优先级协议任务栈
- 协议状态机热变量

Non-cacheable AXI SRAM:
- ETH DMA Descriptor
- Rx Buffer
- Tx Buffer

Cacheable AXI SRAM:
- TCP/IP pbuf 管理结构
- 应用层报文队列
- 日志缓存
```

核心代码：

```
MEM_DMA_BUFFER static uint8_t g_eth_rx_pool[8][1536];

bool NetworkRxAcquire(uint8_t **frame, uint16_t *length)
{
    if ((frame == NULL) || (length == NULL)) {
        return false;
    }

    /* 由 DMA 驱动层返回 Non-cacheable 缓冲区。 */
    return EthDriver_GetRxFrame(frame, length);
}
```

设计要点：

- DMA 描述符必须按 Cache Line 对齐。
- 若 DMA 区采用 MPU Non-cacheable 配置，驱动层无需每包执行 Cache 维护。
- 协议解析的短小热点函数可放 ITCM，但整个 lwIP 协议栈不应无差别搬运。

---

### 案例 3：Cortex-M7 边缘 AI 振动诊断终端

#### 需求

- 三轴加速度计以 20 kHz 采样。
- 每 100 ms 执行特征提取与轻量模型推理。
- 同时通过 USB 或 Ethernet 上传诊断结果。

#### 架构设计

|数据类型|放置区域|原因|
|---|---|---|
|ADC/SPI DMA 原始采样块|Non-cacheable SRAM|DMA 可访问|
|窗函数、FFT 状态|DTCM|高频读写、确定性|
|CMSIS-DSP 热函数|ITCM|降低取指抖动|
|神经网络权重|Flash/OSPI|容量大、主要只读|
|特征向量与推理工作区|DTCM 或 AXI SRAM|按工作集大小选择|
|上传报文|AXI SRAM|网络 DMA 共享|

核心代码：

```
MEM_ITCM_CODE static void FeatureExtract(const float *input,
                                         float *feature,
                                         uint32_t count)
{
    float sum = 0.0f;
    float energy = 0.0f;

    for (uint32_t i = 0U; i < count; ++i) {
        float x = input[i];
        sum += x;
        energy += x * x;
    }

    feature[0] = sum / (float)count;
    feature[1] = energy / (float)count;
}
```

设计要点：

- 原始数据 DMA 写入共享 SRAM。
- CPU 消费前完成 Cache 失效，或直接使用 Non-cacheable 区。
- 不应将完整模型权重迁移到 DTCM，除非模型极小且收益经实测确认。

---

## 12. 高频问题深度答疑

### 1. TCM 是否一定比 Cache 更快？

不一定。对于连续访问的大数组，Cache 命中后的 AXI SRAM 吞吐量可能非常高。TCM 的核心优势是 **最坏访问时间可预测**。硬实时控制优先 TCM；吞吐型大数据任务优先 Cacheable SRAM。

### 2. 为什么 DTCM 中的数据 DMA 访问不到？

因为 DTCM 通常挂接在内核私有 TCM 接口上，而 DMA 是系统总线主设备。二者不一定存在硬件互连。必须检查芯片的 bus matrix、DMA address map 和参考手册。

### 3. 是否需要给 ITCM/DTCM 配置 Cache？

通常不需要。TCM 已经提供低延迟本地访问；很多实现中其访问属性天然不经 Cache。错误地把问题理解为“所有 RAM 都应缓存”会破坏实时性设计重点。

### 4. ITCM 函数中的常量表放在哪里？

函数指令在 ITCM，不代表常量自动在 ITCM。若常量仍在 Flash，函数运行时仍可能访问 Flash。对高频小型常量表，应单独放入 DTCM 或 ITCM 可访问区域；对大型查表数据，应评估 DTCM 容量与访问模式。

```
static const float g_sin_table[16]
__attribute__((section(".dtcm_rodata"))) = {
    0.0f, 0.382683f, 0.707107f, 0.923880f
};
```

### 5. FreeRTOS 的任务栈都应放 DTCM 吗？

不是。高优先级、频繁切换、实时敏感任务适合 DTCM。低频通信、UI、文件系统任务的栈放普通 SRAM 更合理。还必须确认异常栈、MSP、PSP 的配置与启动文件一致。

### 6. 如何证明 TCM 优化确实有效？

不能只看平均执行时间。应至少测量：

- ISR 最小、平均、最大 Cycle。
- 控制周期峰峰值抖动。
- 有 DMA/LCD/Ethernet 高负载时的 WCET。
- Cache 开启、关闭及不同存储区域下的对比。
- map 文件中关键符号实际地址。
- TCM 占用率、栈高水位和链接余量。

---

## 13. 课程核心总结

- **ITCM 用于关键指令路径，DTCM 用于 CPU 私有热数据与栈。**
- TCM 的主要价值是 **低延迟与时间确定性**，不只是平均吞吐量。
- DMA Buffer、Ethernet 描述符、USB 缓冲区通常应位于 DMA 可访问的 SRAM，而不是 DTCM。
- Cacheable SRAM 适合一般数据和高吞吐大工作集；Non-cacheable SRAM 适合共享 DMA 数据。
- 所有内存布局优化必须通过 **map 文件、DWT Cycle、总线负载场景** 验证。
- 最优架构通常不是“全放 TCM”，而是 **按访问主体、实时等级、容量、缓存一致性分层放置**。

性能确定性排序：

```
ITCM / DTCM
    >
非缓存共享 SRAM
    >
Cache 命中后的 AXI SRAM / Flash
    >
Cache Miss 的 AXI SRAM / Flash
    >
外部 SDRAM / OSPI，且存在总线竞争
```

---

## 14. 快速参考速查表

### 场景选型表

|对象|推荐内存|必要措施|
|---|---|---|
|高优先级 ISR|ITCM|确保调用链关键函数也在 ITCM|
|PID/FIR 状态|DTCM|控制总容量|
|RTOS 实时任务栈|DTCM|做栈高水位监控|
|ADC DMA Buffer|Non-cacheable SRAM|双缓冲、对齐|
|Ethernet Descriptor|Non-cacheable SRAM|32 Byte 对齐|
|Ethernet Payload|Non-cacheable SRAM 或 Cacheable SRAM|后者需 Cache 维护|
|大型图像帧|AXI SRAM / SDRAM|评估 DMA 带宽|
|普通业务代码|Flash + I-Cache|保持默认即可|
|高速算法热点|ITCM + DTCM|DWT 验证收益|

### 特性对比表

|特性|ITCM|DTCM|DMA SRAM|Cacheable SRAM|
|---|---|---|---|---|
|CPU 实时性|极高|极高|中等|平均高、最坏较差|
|DMA 可达|通常否|通常否|是|是|
|Cache 维护|通常不需要|通常不需要|通常不需要|需要|
|容量适合性|小代码|小热数据|中小 DMA 数据|中大数据|
|核心用途|ISR/算法代码|栈/状态|外设共享缓冲|通用应用数据|

---

## 15. 学习效果自检

- [ ]  能解释 ITCM、DTCM、Cache、AXI SRAM 的硬件访问路径差异。
- [ ]  能从芯片手册确认 DMA 是否可访问某段 TCM。
- [ ]  能修改链接脚本定义 `.itcm_text`、`.dtcm_data`、`.dma_buffer`。
- [ ]  能在启动代码中正确复制 ITCM 代码和 DTCM 初始化数据。
- [ ]  能通过 map 文件确认 ISR 和关键变量的最终地址。
- [ ]  能使用 DWT 测量函数 WCET 和周期抖动。
- [ ]  能正确处理 Cacheable DMA Buffer 的 Clean/Invalidate。
- [ ]  能设计 MPU Non-cacheable DMA 区。
- [ ]  能根据实时性、共享性和容量完成内存分层设计。
- [ ]  能定位“DMA 无数据”“偶发旧数据”“ISR 抖动”等问题。

---

## 16. 实践与进阶路径

### 任务 1：建立 TCM 基础工程

- 为目标 Cortex-M7 工程添加 ITCM、DTCM、DMA SRAM 段。
- 将一个定时器 ISR 放入 ITCM。
- 将 ISR 局部状态放入 DTCM。
- 使用 map 文件验证地址。

### 任务 2：完成启动搬运链路

- 修改链接脚本，使用 `AT > FLASH` 为 ITCM 段建立加载镜像。
- 修改启动代码复制 `.itcm_text`、`.dtcm_data`。
- 冷启动、软件复位、调试器复位分别验证。

### 任务 3：执行性能基准测试

- 比较 Flash、ITCM、AXI SRAM、DTCM 中相同函数的 Cycle。
- 分别测试 Cache 开启和关闭。
- 在 Ethernet 或 DMA 高负载下采样 ISR 最大执行周期。
- 输出最小值、平均值、P99、最大值，不只输出平均值。

### 任务 4：实现 DMA 一致性策略

- 建立 ADC DMA 双缓冲。
- 方案 A：Cacheable SRAM + Cache Clean/Invalidate。
- 方案 B：MPU Non-cacheable SRAM。
- 对比 CPU 开销、代码复杂度、错误概率和实时性。

### 任务 5：工业级内存架构设计

- 为“电机控制 + EtherCAT/Ethernet + 数据记录”系统分配内存。
- 定义 ITCM、DTCM、Cacheable SRAM、DMA SRAM、外部 RAM 的对象清单。
- 建立 TCM 容量预算、栈预算、DMA Buffer 预算和链接余量告警。

### 进阶学习方向

- Cortex-M7 Cache、MPU、AXI Matrix、TCM 接口的微架构。
- FreeRTOS/Zephyr 的任务栈布局与 MPU 隔离。
- CMSIS-DSP、CMSIS-NN 的内存工作集优化。
- WCET 分析、Trace、ETM/ITM、SWO 性能诊断。
- ISO 26262、IEC 61508 场景下的内存保护与确定性设计。