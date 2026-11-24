
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 Cortex-M SysTick 在内核异常系统中的定位；
- 掌握 SysTick 24 位递减计数器、重装载寄存器、当前值寄存器和控制状态寄存器的关系；
- 理解 `COUNTFLAG`、`TICKINT`、`CLKSOURCE` 对系统行为的影响；
- 理解 SysTick 中断与 PendSV、SVC、普通外部中断之间的调度关系；
- 理解 SysTick 周期抖动、异常延迟和时基漂移的来源。

### 1.2 掌握

能够：

- 基于 CMSIS 直接配置 SysTick；
- 设计毫秒级系统时基；
- 正确处理 24 位重装载值限制；
- 编写不依赖中断的 SysTick 轮询延时；
- 处理 `COUNTFLAG` 的读清零语义；
- 使用无符号差值进行 32 位时间戳回绕安全判断；
- 正确选择 SysTick 时钟源。

### 1.3 精通

能够：

- 分析 SysTick 在 RTOS 中的 tick 驱动模型；
- 设计 tickless idle、动态 tick 和低功耗唤醒方案；
- 评估 SysTick 中断对 CPU 利用率和实时性的影响；
- 处理高优先级中断长期占用 CPU 导致的 SysTick 延迟；
- 识别 SysTick 与 DWT、通用定时器之间的精度和适用场景差异；
- 设计多时基并存的系统时钟架构。

### 1.4 能够设计

能够设计：

- 工业控制器的 1 ms 系统时基；
- 无 RTOS 和 RTOS 共存的定时架构；
- 低功耗设备的 tickless 定时体系；
- 含安全分区、双核或多时钟域系统中的内核时基方案；
- 可验证、可测试、可追踪的 SysTick 驱动模块。

---

# 2. 前置要求

## 2.1 知识要求

- C 语言：
    - `volatile`
    - 位操作
    - 无符号整数溢出
    - 中断函数与临界区
- Cortex-M 基础：
    - 异常向量表
    - NVIC 优先级
    - 异常进入与返回
    - MSP、PSP
    - PendSV、SVC
- MCU 时钟树：
    - HCLK
    - AHB 分频
    - PLL
    - 时钟切换
- 基本 RTOS 概念：
    - 系统 tick
    - 时间片
    - 延时阻塞
    - tickless idle
- 基本低功耗知识：
    - Sleep
    - DeepSleep
    - WFI
    - 时钟门控

## 2.2 技能要求

- 能够阅读 CMSIS 设备头文件；
- 能够使用调试器查看内核寄存器；
- 能够使用逻辑分析仪或示波器测量 GPIO 翻转周期；
- 能够通过 DWT、ITM、串口或 ETM 进行时间观测；
- 能够分析中断优先级和中断响应延迟；
- 能够编写基础的单元测试和硬件测试代码。

---

# 3. 技术概述

## 3.1 SysTick 的定义

SysTick 是 Cortex-M 内核内置的**24 位递减定时器**，主要用于：

- RTOS 系统 tick；
- 操作系统时间片；
- 周期性软件调度；
- 基本延时；
- 系统时间基准；
- 低功耗唤醒辅助。

SysTick 不属于具体 MCU 厂商的外设，而属于 Cortex-M 内核架构的一部分，因此其寄存器结构在不同厂商之间具有较强一致性。

典型寄存器定义如下：

```
typedef struct
{
    volatile uint32_t CTRL;   /* 0x00: 控制与状态寄存器 */
    volatile uint32_t LOAD;   /* 0x04: 重装载值寄存器 */
    volatile uint32_t VAL;    /* 0x08: 当前计数值寄存器 */
    volatile const uint32_t CALIB; /* 0x0C: 校准值寄存器 */
} SysTick_Type;
```

## 3.2 SysTick 的主要功能链路

```
CPU 时钟源
    │
    ├── HCLK / Core Clock
    │
    └── HCLK / 8（部分架构默认选项）
             │
             ▼
       SysTick 递减计数器
             │
       计数到 0
             │
       自动加载 LOAD
             │
       COUNTFLAG 置位
             │
       TICKINT=1 时产生 SysTick 异常
```

## 3.3 SysTick 寄存器

|寄存器|位宽|主要作用|
|---|---|---|
|`CTRL`|32 位|启停、时钟源、中断使能、COUNTFLAG|
|`LOAD`|24 位|计数器重装载值|
|`VAL`|24 位|当前计数值，写入任意值通常清零|
|`CALIB`|32 位|校准信息，是否存在、TENMS 值等|

### `CTRL` 关键位

|位|名称|作用|
|---|---|---|
|0|`ENABLE`|使能计数器|
|1|`TICKINT`|计数归零时产生 SysTick 异常|
|2|`CLKSOURCE`|选择处理器时钟或外部参考时钟|
|16|`COUNTFLAG`|自上次读取后是否发生过归零|

不同 CMSIS 版本中的宏名称通常为：

```
SysTick_CTRL_ENABLE_Msk
SysTick_CTRL_TICKINT_Msk
SysTick_CTRL_CLKSOURCE_Msk
SysTick_CTRL_COUNTFLAG_Msk
```

---

# 4. 核心特性横向对比

## 4.1 SysTick 与其他定时机制对比

|维度|SysTick|通用定时器|RTC/LPTIM|DWT CYCCNT|
|---|---|---|---|---|
|所属模块|Cortex-M 内核|MCU 外设|低功耗外设|Cortex-M 调试/跟踪模块|
|计数位宽|24 位|常见 16/32 位|常见 16/32 位|32 位|
|是否产生异常/中断|是|是|是|通常不直接产生中断|
|时钟源|Core Clock 或外部源|外设时钟|低速时钟|Core Clock|
|低功耗保持能力|通常有限|取决于时钟域|通常较好|通常停止|
|典型用途|系统 tick|精确外设定时|RTC、低功耗唤醒|高精度性能测量|
|配置复杂度|低|中|中高|低|
|适合微秒级测量|不推荐|推荐|不推荐|推荐|
|适合 RTOS tick|推荐|可选|不推荐|不适合|
|最大周期|受 24 位限制|通常更长|通常更长|约 2³² 周期|
|对内核异常影响|有|无或较小|无|无|

## 4.2 SysTick 时钟源对比

|时钟源|频率|优点|缺点|
|---|---|---|---|
|`HCLK`|`f_cpu`|配置简单、分辨率高|时钟改变后需重新配置|
|`HCLK/8`|`f_cpu/8`|可扩大最大定时周期|分辨率降低，平台依赖性强|
|外部参考时钟|芯片相关|可获得稳定参考|不是所有 Cortex-M 实现都支持|

## 4.3 中断 tick 与轮询 tick

|方案|优点|缺点|典型用途|
|---|---|---|---|
|`TICKINT=1`|自动产生异常，适合 RTOS|占用 CPU，受异常延迟影响|系统 tick|
|`TICKINT=0` + 轮询|无周期中断开销|必须主动读取状态|简单裸机、短延时|
|外部定时器中断|灵活、低功耗能力强|配置复杂|复杂产品、长期定时|
|RTC/LPTIM|低功耗保持能力强|精度和分辨率有限|Stop/Standby 唤醒|

---

# 5. 底层原理与功能特性深度解析

## 5.1 SysTick 递减过程

设：

- `f_systick`：SysTick 输入时钟频率；
- `R`：`LOAD` 写入值；
- `N = R + 1`：一个完整计数周期的时钟数。

则周期为：

Ttick=R+1fsystickTtick​=fsystick​R+1​

频率为：

ftick=fsystickR+1ftick​=R+1fsystick​​

注意：**SysTick 的周期不是 `LOAD / f`，而是 `(LOAD + 1) / f`。**

例如：

```
CPU 时钟 = 168 MHz
目标周期 = 1 ms
```

如果使用 HCLK：

R=168000000×0.001−1=167999R=168000000×0.001−1=167999

因此：

```
SysTick->LOAD = 167999U;
```

## 5.2 `LOAD` 的 24 位限制

SysTick 最大重装载值为：

```
0x00FFFFFF = 16,777,215
```

最大周期：

Tmax=16,777,216fsystickTmax​=fsystick​16,777,216​

例如：

|CPU 时钟|最大周期，HCLK 源|
|---|---|
|16 MHz|1.048576 s|
|48 MHz|349.525 ms|
|80 MHz|209.715 ms|
|168 MHz|99.864 ms|
|480 MHz|34.953 ms|

因此，**在高频 MCU 上直接用 SysTick 实现 1 秒定时通常是不成立的**。

## 5.3 初始化时序

推荐顺序：

```
1. 关闭 SysTick
2. 关闭 SysTick 异常
3. 清零当前值 VAL
4. 检查 reload 范围
5. 写入 LOAD
6. 设置异常优先级
7. 设置时钟源
8. 开启中断
9. 开启计数器
```

生产级初始化代码：

```
#include "stm32xxxx.h"
#include <stdint.h>
#include <stdbool.h>

#define SYSTICK_MAX_RELOAD    (0x00FFFFFFUL)

typedef enum
{
    SYSTICK_OK = 0,
    SYSTICK_ERR_INVALID_FREQ,
    SYSTICK_ERR_INVALID_HZ,
    SYSTICK_ERR_RELOAD_OVERFLOW,
    SYSTICK_ERR_RELOAD_ZERO
} systick_status_t;

static uint32_t g_systick_hz;

systick_status_t systick_init(uint32_t core_clock_hz,
                              uint32_t tick_hz,
                              uint32_t irq_priority)
{
    uint64_t reload;

    if ((core_clock_hz == 0U) || (tick_hz == 0U))
    {
        return SYSTICK_ERR_INVALID_FREQ;
    }

    /*
     * 使用 64 位计算，避免 core_clock_hz * 1 发生溢出。
     * reload = ceil(f / tick_hz) - 1
     *
     * 对于整数时钟配置，通常要求 f 能被 tick_hz 整除，
     * 否则系统 tick 会产生周期量化误差。
     */
    reload = ((uint64_t)core_clock_hz + tick_hz - 1U) / tick_hz;

    if (reload == 0U)
    {
        return SYSTICK_ERR_RELOAD_ZERO;
    }

    reload -= 1U;

    if (reload > SYSTICK_MAX_RELOAD)
    {
        return SYSTICK_ERR_RELOAD_OVERFLOW;
    }

    SysTick->CTRL = 0U;
    SysTick->LOAD = (uint32_t)reload;
    SysTick->VAL  = 0U;

    /*
     * 优先级数值越小，逻辑优先级越高。
     * 实际有效位数由实现决定，CMSIS 会进行适配。
     */
    NVIC_SetPriority(SysTick_IRQn, irq_priority);

    SysTick->CTRL =
        SysTick_CTRL_CLKSOURCE_Msk |
        SysTick_CTRL_TICKINT_Msk   |
        SysTick_CTRL_ENABLE_Msk;

    g_systick_hz = tick_hz;

    return SYSTICK_OK;
}
```

## 5.4 为什么清零 `VAL`

写入 `VAL` 的作用通常是：

- 清除当前计数值；
- 清除计数器内部状态；
- 防止使用旧的剩余计数值；
- 让首次周期从完整周期开始。

推荐：

```
SysTick->VAL = 0U;
```

而不是只修改 `LOAD` 后立即打开计数器。

## 5.5 `COUNTFLAG` 的读清零语义

`COUNTFLAG` 不是一个普通软件状态位。

其典型行为：

- 计数器归零时，`COUNTFLAG` 置位；
- 读取 `CTRL` 后，`COUNTFLAG` 被清除；
- 在两次读取之间，如果发生过至少一次归零，则读到 1；
- 多次归零不会累计次数，不能用它统计遗漏了多少个 tick。

轮询代码：

```
bool systick_has_elapsed(void)
{
    return (SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk) != 0U;
}
```

错误示例：

```
uint32_t ctrl = SysTick->CTRL;

if ((ctrl & SysTick_CTRL_COUNTFLAG_Msk) != 0U)
{
    /* 认为只发生了一个 tick */
}
```

问题在于：如果 CPU 长时间没有读取 `CTRL`，期间发生 5 次归零，最终只能观察到“至少发生过一次”。

## 5.6 `TICKINT` 与异常生成

当：

```
SysTick->CTRL & SysTick_CTRL_TICKINT_Msk
```

有效时，计数器归零会产生 SysTick 异常。

异常处理函数：

```
volatile uint32_t g_system_ticks;

void SysTick_Handler(void)
{
    g_system_ticks++;

    /*
     * 只做确定性、短路径操作：
     * - 更新时间基准
     * - 推进软件定时器
     * - 通知 RTOS
     *
     * 不应在此执行：
     * - 阻塞等待
     * - printf
     * - 动态内存分配
     * - 长时间轮询
     */
}
```

## 5.7 SysTick 异常延迟

SysTick 到期并不意味着处理函数立即执行。实际延迟包括：

Tlatency=Tcurrent_ISR_remaining+Thigher_priority_ISR+Tstacking+Tbus_contentionTlatency​=Tcurrent_ISR_remaining​+Thigher_priority_ISR​+Tstacking​+Tbus_contention​

典型异常进入开销：

- Cortex-M3/M4/M7 基本自动压栈：约 8 个寄存器；
- 以 32 位寄存器计算，基础栈帧约：

8×4=32 bytes8×4=32 bytes

- 某些实现包含额外对齐字；
- 使用 FPU 时可能发生浮点上下文延迟保存，栈开销和进入时间增加；
- Cortex-M7 还可能受 I-Cache、D-Cache、TCM、总线竞争影响。

因此：

```
SysTick 周期 = 1 ms
```

不代表：

```
SysTick_Handler 每隔精确 1 ms 开始执行
```

## 5.8 SysTick 时间戳与回绕安全

错误写法：

```
if (now > deadline)
{
    timeout = true;
}
```

该写法不能正确处理 `uint32_t` 回绕。

正确写法：

```
static inline bool time_after_eq(uint32_t now, uint32_t deadline)
{
    return (int32_t)(now - deadline) >= 0;
}
```

典型使用：

```
uint32_t start = g_system_ticks;
uint32_t timeout = 100U;

while ((uint32_t)(g_system_ticks - start) < timeout)
{
    /* 非阻塞处理 */
}
```

该方法要求单次时间跨度小于 `2^31` 个 tick。

## 5.9 时钟切换后的重新配置

当系统时钟从 80 MHz 切换到 160 MHz 时，如果 SysTick 使用 HCLK，原有 `LOAD` 不变，则 tick 周期会减半。

因此时钟切换后必须：

```
void systick_reconfigure(uint32_t new_core_clock_hz,
                         uint32_t tick_hz)
{
    SysTick->CTRL &= ~SysTick_CTRL_ENABLE_Msk;

    (void)systick_init(new_core_clock_hz,
                       tick_hz,
                       NVIC_GetPriority(SysTick_IRQn));
}
```

更好的做法是：

```
系统时钟切换
    │
    ├── 更新 SystemCoreClock
    ├── 重新计算外设分频
    ├── 重新配置 SysTick
    ├── 更新 DWT/性能测量参数
    └── 通知依赖频率的驱动模块
```

---

# 6. 性能量化分析

以下数据以 Cortex-M4F、168 MHz、零等待 SRAM、编译器 `-O2` 为参考模型。不同内核、编译器、Flash 等待周期和 FPU 状态会改变结果，实际产品应使用示波器和 DWT 实测。

## 6.1 计数周期计算

目标：

```
CPU = 168 MHz
SysTick = 1 kHz
```

计算：

R=1680000001000−1=167999R=1000168000000​−1=167999

完整周期：

R+1=168000R+1=168000

理论周期：

T=168000168000000=1msT=168000000168000​=1ms

## 6.2 SysTick 中断 CPU 开销

假设：

- 基础异常进入与退出：约 40～80 cycles；
- `SysTick_Handler`：约 40～120 cycles；
- RTOS tick 处理：约 200～1,000 cycles；
- tick 频率：1 kHz。

### 裸机简单 tick

假设每次 100 cycles：

CPU utilization=100×1000168000000≈0.0595%CPU utilization=168000000100×1000​≈0.0595%

### RTOS tick

假设每次 800 cycles：

800×1000168000000≈0.476%168000000800×1000​≈0.476%

如果系统使用 10 kHz tick：

800×10000168000000≈4.76%168000000800×10000​≈4.76%

因此，**高 tick 频率会显著增加 CPU 开销**。

## 6.3 时间误差

如果 `f_core / tick_hz` 不是整数，则必须进行舍入。

例如：

```
CPU = 80 MHz
tick = 1024 Hz
```

理想计数值：

N=800000001024=78125N=102480000000​=78125

该值是整数，无量化误差。

另一个例子：

```
CPU = 72 MHz
tick = 1000 Hz
```

此时：

N=72000N=72000

仍然无误差。

如果：

```
CPU = 48 MHz
tick = 1000 Hz
```

依然为整数。

但如果：

```
CPU = 64 MHz
tick = 1024 Hz
```

则：

N=62500N=62500

也为整数。

对于非整数情况，例如：

```
CPU = 80 MHz
tick = 1000 Hz
```

仍然是整数；若是 81 MHz：

N=81000N=81000

仍为整数。实际工程中多数主频是 MHz 级整数，但低速或复杂 PLL 配置可能出现量化误差。

单周期误差：

ϵ=Nactual−Nidealfsystickϵ=fsystick​Nactual​−Nideal​​

长期误差：

Elong−term=ϵ×number_of_ticksElong−term​=ϵ×number_of_ticks

## 6.4 SysTick 与 DWT 精度对比

假设 CPU 为 168 MHz：

|机制|分辨率|典型用途|
|---|---|---|
|1 kHz SysTick|1 ms|操作系统时间基准|
|10 kHz SysTick|100 μs|较细粒度调度，但中断负担更高|
|DWT CYCCNT|5.95 ns/cycle|性能测量、短代码段计时|
|1 MHz 通用定时器|1 μs|微秒级外设时序|
|RTC 32.768 kHz|30.5 μs|低功耗长期计时|

## 6.5 优化手段

|优化手段|预期收益|
|---|---|
|降低 tick 频率|降低中断开销|
|在 tick ISR 中只做计数和唤醒|降低最坏执行时间|
|软件定时器使用 delta list 或最小堆|减少每 tick 扫描开销|
|tickless idle|空闲期间几乎消除周期 tick|
|使用通用定时器替代高频 SysTick|降低内核异常干扰|
|将微秒级工作转移至硬件定时器|降低抖动|
|避免在 SysTick 中访问慢速总线外设|缩短 ISR|
|使用 DWT 进行性能测量|获得 cycle 级数据|

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
需要定时功能
   │
   ├── 需要作为 RTOS 内核 tick？
   │      │
   │      ├── 是 → 优先使用 SysTick 或 RTOS 推荐 tick 源
   │      └── 否
   │
   ├── 需要微秒级精度？
   │      │
   │      ├── 是 → 通用定时器 / DWT CYCCNT
   │      └── 否
   │
   ├── 需要 Stop/Standby 低功耗下继续计时？
   │      │
   │      ├── 是 → RTC / LPTIM / 低功耗定时器
   │      └── 否
   │
   ├── 需要超长周期且主频较高？
   │      │
   │      ├── 是 → 通用 32 位定时器 / RTC
   │      └── 否 → SysTick
   │
   └── 需要高精度外部触发或 PWM？
          │
          └── 使用通用定时器，避免 SysTick
```

## 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|RTOS 1 ms tick|SysTick|内核集成、配置简单|
|裸机 1 ms 时间基准|SysTick|低开发成本|
|10 μs PWM 控制|TIM/PWM|硬件输出，抖动低|
|电机换相|高级定时器|支持互补输出、死区、触发|
|Stop 模式唤醒|RTC/LPTIM|低功耗时钟域可保持|
|测量函数耗时|DWT CYCCNT|cycle 级分辨率|
|5 秒软件超时|软件时间戳 + SysTick|不要求高精度|
|高精度协议 bit-bang|通用定时器/DMA|SysTick 抖动不可控|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：SysTick 只承担系统时间基准

不要把 SysTick 当作万能定时器。它适合：

- 系统 tick；
- 软件超时；
- 软件定时器；
- 任务调度。

不适合：

- 高精度 PWM；
- 精确脉宽采样；
- 严格微秒级协议时序；
- 外部事件捕获；
- 长时间低功耗保持。

### 原则二：中断处理函数必须短小确定

推荐：

```
void SysTick_Handler(void)
{
    g_system_ticks++;
    rtos_tick_increment();
}
```

不推荐：

```
void SysTick_Handler(void)
{
    uart_printf("tick\r\n");
    sensor_read_blocking();
    malloc(128);
}
```

### 原则三：所有时间差使用无符号差值

```
if ((uint32_t)(now - start) >= timeout)
{
    /* timeout */
}
```

### 原则四：时钟变化必须同步更新 SysTick

不要只更新：

```
SystemCoreClock = new_clock;
```

还必须重新计算并写入 `LOAD`。

### 原则五：对重装载值做范围校验

```
if (reload == 0U || reload > 0x00FFFFFFUL)
{
    return ERROR;
}
```

### 原则六：使用统一的时间接口

上层不应直接读取 `SysTick->VAL`：

```
uint32_t platform_time_ms(void)
{
    return g_system_ticks;
}
```

这样未来可以替换为：

- 通用定时器；
- RTC；
- RTOS tick；
- 多核共享时钟；
- 低功耗补偿时钟。

## 8.2 选型决策矩阵

|指标|SysTick|TIM|RTC/LPTIM|DWT|
|---|---|---|---|---|
|系统集成成本|5|3|2|4|
|微秒精度|2|5|2|5|
|低功耗能力|2|3|5|1|
|RTOS 适配|5|4|2|1|
|长周期能力|2|5|5|3|
|对系统异常影响|2|4|4|5|
|跨厂商一致性|5|2|2|3|

评分说明：5 表示强，1 表示弱。

## 8.3 工业级编码规范

- 所有硬件寄存器访问使用正确的 `volatile` 定义；
- 采用 CMSIS 宏，不直接硬编码位号；
- 初始化函数必须返回错误码；
- 不在 SysTick ISR 中使用阻塞 API；
- 时间戳类型统一为 `uint32_t` 或 `uint64_t`；
- 所有时间接口明确单位；
- 对低功耗和时钟切换提供独立处理路径；
- 在启动阶段验证 `LOAD` 是否满足架构限制；
- 记录系统 tick 最大延迟和最大执行时间；
- 对 SysTick_Handler 建立静态检查规则。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：忽略 24 位限制

### 错误代码

```
SysTick->LOAD = SystemCoreClock - 1U; /* 希望实现 1 秒 */
```

### 根因

`SystemCoreClock` 可能大于 `0x00FFFFFF`，高位被截断。

### 正确实现

```
uint32_t systick_config_seconds(uint32_t core_clock_hz)
{
    if (core_clock_hz == 0U ||
        core_clock_hz > SYSTICK_MAX_RELOAD + 1U)
    {
        return 1U;
    }

    SysTick->LOAD = core_clock_hz - 1U;
    SysTick->VAL = 0U;
    SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk |
                    SysTick_CTRL_TICKINT_Msk |
                    SysTick_CTRL_ENABLE_Msk;
    return 0U;
}
```

### 风险影响

- 系统 tick 频率错误；
- 软件超时提前或延后；
- RTOS 调度节拍完全失真；
- 故障可能只在高主频版本出现。

## 9.2 错误二：误认为 `LOAD` 就是计数周期

### 错误代码

```
SysTick->LOAD = core_clock_hz / tick_hz;
```

### 根因

递减计数器从 `LOAD` 开始，经过 `LOAD + 1` 个时钟才完成一个周期。

### 正确实现

```
uint32_t reload = (core_clock_hz / tick_hz) - 1U;
SysTick->LOAD = reload;
```

若需要处理非整数频率，应使用明确的舍入策略并评估长期误差。

### 风险影响

- 产生一个计数周期的误差；
- 高频系统或高精度系统中表现为稳定频偏。

## 9.3 错误三：使用大小比较判断时间到期

### 错误代码

```
if (g_system_ticks > deadline)
{
    task_timeout = true;
}
```

### 根因

时间戳回绕后，大小关系不再反映时间先后。

### 正确实现

```
if ((uint32_t)(g_system_ticks - start_tick) >= timeout_ticks)
{
    task_timeout = true;
}
```

### 风险影响

- 系统运行约 49.7 天后，32 位毫秒 tick 可能出现周期性超时错误；
- 现场设备可能重启后才恢复，难以复现。

## 9.4 错误四：在 SysTick 中执行阻塞操作

### 错误代码

```
void SysTick_Handler(void)
{
    while (!uart_tx_ready())
    {
        /* 阻塞 */
    }
}
```

### 根因

异常上下文中执行了不可预测时长的工作。

### 正确实现

```
volatile bool g_tick_event;

void SysTick_Handler(void)
{
    g_system_ticks++;
    g_tick_event = true;
}

void main_loop(void)
{
    if (g_tick_event)
    {
        g_tick_event = false;
        uart_service();
    }
}
```

### 风险影响

- 其他中断延迟；
- RTOS tick 丢失；
- 优先级反转；
- 看门狗超时；
- 产生级联实时性故障。

## 9.5 错误五：时钟切换后不重新配置

### 错误代码

```
SystemCoreClock = 160000000U;
/* 忘记更新 SysTick->LOAD */
```

### 根因

SysTick 的计数周期依赖时钟频率。

### 正确实现

```
SystemCoreClockUpdate();

(void)systick_init(SystemCoreClock,
                   1000U,
                   15U);
```

### 风险影响

- 所有基于 tick 的超时比例错误；
- RTOS 时间管理异常；
- 通信协议超时失效。

## 9.6 错误六：错误使用 `COUNTFLAG`

### 错误代码

```
while ((SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk) == 0U)
{
    /* 忙等 */
}
```

### 根因

读取 `CTRL` 会清除 `COUNTFLAG`，且该标志不累计多次溢出。

### 正确实现

```
void systick_poll_wait_one_period(void)
{
    while ((SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk) == 0U)
    {
        __NOP();
    }
}
```

该方法只适用于等待“至少一个周期”，不适用于统计多个周期。

### 风险影响

- 延时周期不可预测；
- 轮询系统可能遗漏多个 tick；
- 调度逻辑与实际时间不一致。

---

# 10. 多机制组合使用方案

## 10.1 推荐的时间架构

```
┌────────────────────┐
                 │  硬件时钟树/PLL     │
                 └─────────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
      SysTick           TIM/LPTIM          RTC
          │                │                │
          ▼                ▼                ▼
     系统毫秒 tick     微秒级事件       低功耗时间
          │                │                │
          └────────────┬───┴────────────────┘
                       ▼
               平台统一时间服务
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
    软件超时       周期任务        低功耗补偿
```

## 10.2 组合设计模式

### 模式 A：SysTick + 时间戳

适合：

- 裸机；
- 低频控制；
- 通信协议超时。

```
static volatile uint32_t g_tick_ms;

void SysTick_Handler(void)
{
    g_tick_ms++;
}

uint32_t platform_get_time_ms(void)
{
    return g_tick_ms;
}

bool platform_timeout(uint32_t start_ms, uint32_t timeout_ms)
{
    uint32_t now = platform_get_time_ms();

    return (uint32_t)(now - start_ms) >= timeout_ms;
}
```

### 模式 B：SysTick + 软件定时器最小堆

适合：

- 多个超时任务；
- 避免每 tick 扫描所有定时器；
- RTOS 或复杂裸机系统。

核心思想：

```
每个软件定时器只保存绝对到期时间
最小堆顶部是最近到期定时器
每次 tick 只处理顶部已到期项目
```

伪代码：

```
typedef struct
{
    uint32_t deadline;
    void (*callback)(void *arg);
    void *arg;
    bool periodic;
    uint32_t period;
} soft_timer_t;
```

### 模式 C：SysTick + DWT

用途：

- SysTick 提供毫秒级业务时间；
- DWT 提供代码段周期测量。

```
static inline uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}

uint32_t measure_cycles(void (*fn)(void))
{
    uint32_t start = dwt_cycles();

    fn();

    return dwt_cycles() - start;
}
```

### 模式 D：SysTick + 低功耗定时器

进入低功耗前：

```
1. 读取当前 SysTick 时间
2. 计算最近软件事件剩余时间
3. 停止或暂停 SysTick
4. 配置 LPTIM/RTC
5. 进入 WFI/低功耗模式
6. 唤醒后读取低功耗定时器
7. 补偿系统 tick
8. 恢复 SysTick
```

---

# 11. 工业级实际案例分析

## 11.1 案例一：电机控制器 1 ms 控制周期

### 需求

- 主频：168 MHz；
- 1 ms 控制任务；
- 10 μs PWM 更新；
- 500 μs 通信状态机；
- 低延迟故障响应。

### 架构

```
SysTick 1 kHz
    └── 推进控制任务软件调度

高级定时器
    └── PWM 硬件输出、ADC 触发

外部中断
    └── 过流、过压快速保护

DMA
    └── ADC 数据搬运
```

### 核心代码

```
static volatile uint32_t g_control_tick;
static volatile bool g_control_due;

void SysTick_Handler(void)
{
    g_control_tick++;
    g_control_due = true;
}

void control_scheduler(void)
{
    if (g_control_due)
    {
        g_control_due = false;
        motor_control_1ms();
    }
}
```

### 设计要点

- PWM 不使用 SysTick；
- ADC 采样由定时器触发，不依赖 ISR 软件延迟；
- 过流保护优先级高于 SysTick；
- `motor_control_1ms()` 必须有执行时间上限；
- 必须测量最坏执行时间，而不是平均执行时间。

## 11.2 案例二：工业网关多协议超时管理

### 需求

- Modbus RTU；
- CANopen；
- TCP/IP；
- 多个会话超时；
- 不能为每个协议分配独立硬件定时器。

### 架构

```
SysTick 1 ms
    │
    ▼
统一时间服务
    │
    ├── Modbus 帧间隔判断
    ├── CANopen 节点监控
    ├── TCP keepalive 超时
    └── 看门狗喂狗窗口
```

### 核心代码

```
typedef uint32_t time_ms_t;

static volatile time_ms_t g_now_ms;

time_ms_t time_now_ms(void)
{
    return g_now_ms;
}

bool time_expired(time_ms_t start, uint32_t timeout)
{
    return (uint32_t)(time_now_ms() - start) >= timeout;
}

void protocol_task(void)
{
    static time_ms_t modbus_start;
    static bool modbus_active;

    if (modbus_active && time_expired(modbus_start, 100U))
    {
        modbus_active = false;
        modbus_frame_timeout();
    }
}
```

### 设计要点

- 协议模块只依赖抽象时间接口；
- 不允许协议模块直接访问 `SysTick->VAL`；
- 所有超时单位明确为 ms；
- 长期运行测试必须覆盖时间戳回绕；
- TCP/IP 的高精度定时由网络栈或硬件定时器配合实现。

## 11.3 案例三：电池供电传感器的 tickless 低功耗设计

### 需求

- 正常工作时 1 ms tick；
- 低功耗时数秒唤醒一次；
- SysTick 在深度睡眠中停止；
- 唤醒后系统时间不能明显跳变。

### 架构

```
活跃态：
    SysTick 1 kHz
    └── 精细任务调度

空闲态：
    计算下一事件
    └── RTC/LPTIM 负责唤醒

唤醒态：
    读取睡眠时间
    └── 对系统时间进行补偿
```

### 设计要点

- 不能假设 SysTick 在所有低功耗模式下继续运行；
- 进入低功耗前必须保存逻辑时间；
- 唤醒后使用低功耗时钟测量经过时间；
- RTC 晶振误差需纳入长期校准；
- 中断唤醒来源必须区分“目标唤醒”和“外部异步唤醒”。

---

# 12. 高频问题深度答疑

## 问题一：SysTick 是否适合实现精确 1 ms？

在时钟频率稳定且可整除的情况下，SysTick 可以提供非常稳定的**名义 1 ms 周期**。但是“计数周期精确”与“ISR 精确每 1 ms 执行”是两回事。

影响因素：

- 时钟源误差；
- PLL 抖动；
- 异常响应延迟；
- 高优先级中断占用；
- Flash 等待；
- FPU 上下文保存；
- 低功耗模式暂停。

因此：

- 作为系统时间基准：适合；
- 作为精确外部时序：不适合；
- 作为硬实时控制触发：优先使用通用定时器。

## 问题二：SysTick 优先级应该设置多高？

没有统一答案，应基于系统实时性设计。

通常：

```
紧急故障中断 > 高速采样 > 通信接收 > SysTick > 普通后台任务
```

SysTick 过高的风险：

- 抢占关键外设中断；
- 增加系统中断嵌套；
- 干扰高速控制。

SysTick 过低的风险：

- tick 延迟增大；
- RTOS 任务唤醒不准；
- 时间片边界抖动增加。

对于 RTOS，应遵循内核端口的优先级约束，不能仅凭经验设置。

## 问题三：SysTick 能否在中断中安全读取？

可以，但要注意：

```
uint32_t tick = g_system_ticks;
```

如果 `g_system_ticks` 是 ISR 更新的共享变量，必须定义为：

```
static volatile uint32_t g_system_ticks;
```

32 位 Cortex-M 对自然对齐的 32 位读写通常是原子的，但这不等于复合操作是原子的。

错误：

```
if (g_system_ticks - start >= timeout)
{
    ...
}
```

如果需要一致地读取多个时间相关变量，应使用临界区或快照机制。

## 问题四：为什么不直接用 `VAL` 获得更高精度时间？

可以在特定条件下组合：

```
毫秒 tick + 当前 SysTick 剩余计数
```

但存在复杂问题：

- 读取 `VAL` 和读取全局 tick 之间可能发生归零；
- 需要处理读值竞态；
- 时钟切换会影响换算；
- 低功耗时可能停止；
- `VAL` 只有 24 位；
- 不同内核实现和调试访问行为需要谨慎验证。

如果需要高精度时间戳，优先使用：

- DWT CYCCNT；
- 32 位通用定时器；
- 硬件输入捕获；
- 具备同步读取机制的定时器。

## 问题五：SysTick 的 `COUNTFLAG` 能否统计丢失的 tick？

不能。

`COUNTFLAG` 表示“自上次读取相关状态以来，是否至少发生过一次归零”。它不是事件计数器。

如果需要知道实际发生了多少次周期事件，应使用：

- SysTick 中断次数计数；
- 通用定时器捕获；
- RTOS tick 累加；
- 硬件计数器。

## 问题六：RTOS 是否必须使用 SysTick？

不必须。

RTOS 可以使用：

- SysTick；
- 通用定时器；
- 低功耗定时器；
- 外部时钟源。

选择 SysTick 的主要原因是：

- Cortex-M 原生支持；
- CMSIS 和多数 RTOS 端口默认适配；
- 配置简单；
- 与 PendSV、SVC 调度机制配合自然。

但低功耗、超高 tick 频率或复杂多核系统可能更适合使用外部定时器。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **SysTick 是 Cortex-M 内核内置的 24 位递减定时器。**
2. 一个完整周期对应 `LOAD + 1` 个输入时钟。
3. `LOAD` 的有效范围是 `1～0x00FFFFFF`，具体边界应以实现手册为准。
4. `COUNTFLAG` 只表示至少发生过一次归零，不累计事件。
5. SysTick 周期稳定不等于 ISR 执行时刻无抖动。
6. `SysTick_Handler` 必须短小、无阻塞、可预测。
7. 时间判断必须使用无符号差值，处理 32 位回绕。
8. 时钟切换后必须重新配置 SysTick。
9. 微秒级和硬实时外设时序优先使用通用定时器或 DWT。
10. 低功耗系统应使用 RTC/LPTIM 配合 tickless 设计。

## 13.2 性能排序

从高实时性、高精度到低实时性、较高软件开销：

```
硬件定时器输出/捕获
    >
DMA + 定时器触发
    >
DWT CYCCNT 性能测量
    >
SysTick 低频系统 tick
    >
高频 SysTick 软件调度
    >
软件轮询延时
```

## 13.3 通用选型结论

- **系统 tick：SysTick**
- **微秒级事件：通用定时器**
- **性能测量：DWT CYCCNT**
- **低功耗唤醒：RTC/LPTIM**
- **PWM/输入捕获：通用或高级定时器**
- **复杂软件超时：SysTick + 统一时间服务**
- **低功耗 RTOS：tickless + 低功耗定时器**

---

# 14. 快速参考速查表

## 14.1 场景选型表

|需求|首选方案|
|---|---|
|1 ms 系统 tick|SysTick|
|RTOS 调度节拍|SysTick 或 RTOS 指定定时器|
|微秒级代码测量|DWT CYCCNT|
|PWM|TIM|
|输入捕获|TIM|
|ADC 周期触发|TIM TRGO|
|Stop 模式唤醒|RTC/LPTIM|
|长时间超时|RTC、32 位 TIM 或软件扩展|
|多协议超时|SysTick + 统一时间服务|
|严格硬实时保护|外部中断 + 硬件定时器|

## 14.2 特性对比表

|项目|结论|
|---|---|
|计数方向|递减|
|计数宽度|24 位|
|最大值|`0x00FFFFFF`|
|周期公式|`(LOAD + 1) / f_systick`|
|计数到零后|自动重载|
|中断控制|`TICKINT`|
|计数器使能|`ENABLE`|
|时钟选择|`CLKSOURCE`|
|溢出标志|`COUNTFLAG`|
|当前值清零|写 `VAL`|
|是否适合微秒级硬实时|否|
|是否适合 RTOS tick|是|
|是否必须处理回绕|是|
|时钟变化是否需重配|是|

## 14.3 关键公式

```
reload = f_systick / tick_hz - 1

tick_period = (reload + 1) / f_systick

max_period = 0x01000000 / f_systick

timeout:
(uint32_t)(now - start) >= duration
```

---

# 15. 学习效果自检

完成本课后，应能够回答并实践以下问题：

- [ ]  能否解释为什么 SysTick 是 24 位而不是 32 位？
- [ ]  能否计算 120 MHz 下 1 ms tick 的 `LOAD`？
- [ ]  能否判断某个 `LOAD` 是否超过硬件限制？
- [ ]  能否解释 `LOAD + 1` 而不是 `LOAD` 的原因？
- [ ]  能否解释读取 `CTRL` 对 `COUNTFLAG` 的影响？
- [ ]  能否写出回绕安全的超时判断？
- [ ]  能否说明 SysTick ISR 延迟的来源？
- [ ]  能否设计时钟切换后的 SysTick 重新配置流程？
- [ ]  能否判断某个微秒级任务是否应该使用 SysTick？
- [ ]  能否解释 RTOS 为什么通常使用 SysTick + PendSV？
- [ ]  能否设计 SysTick 与 RTC/LPTIM 配合的 tickless 方案？
- [ ]  能否通过 GPIO 翻转测量 SysTick 实际抖动？
- [ ]  能否使用 DWT CYCCNT 测量 SysTick_Handler 的执行周期？
- [ ]  能否识别 SysTick 中断优先级设置不合理导致的实时性问题？

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：裸机 1 ms 系统时基

要求：

- 配置 SysTick；
- 实现 `platform_get_time_ms()`；
- 实现 100 ms 周期任务；
- 使用 GPIO 翻转验证周期。

验收指标：

- 平均周期误差小于时钟源允许误差；
- 任务周期抖动可测量；
- 代码不使用阻塞延时。

### 任务二：时间戳回绕测试

要求：

- 将系统 tick 初始化到接近 `UINT32_MAX`；
- 模拟时间回绕；
- 验证超时判断仍然正确。

示例：

```
uint32_t start = 0xFFFFFFF0UL;
uint32_t now   = 0x00000020UL;

bool expired = ((uint32_t)(now - start) >= 0x30UL);
```

### 任务三：SysTick 与通用定时器精度对比

要求：

- SysTick 产生 1 ms tick；
- TIM 产生 10 μs 事件；
- 分别测量 GPIO 翻转抖动；
- 对比高优先级中断占用时的延迟变化。

### 任务四：设计软件定时器框架

要求：

- 支持单次定时器；
- 支持周期定时器；
- 支持取消；
- 支持回调；
- 不允许在 ISR 中执行复杂回调；
- 支持回绕安全。

推荐结构：

```
SysTick ISR
    └── 只更新时间计数和置位事件

Timer Service Task
    └── 处理到期的软件定时器回调
```

### 任务五：实现 tickless idle

要求：

- 计算下一软件事件；
- 配置 LPTIM 或 RTC；
- 进入 WFI；
- 唤醒后补偿经过时间；
- 对外部中断提前唤醒进行正确处理。

## 16.2 性能测试方法

### 方法一：GPIO 翻转

```
void SysTick_Handler(void)
{
    GPIO_SET(DEBUG_PIN);

    g_system_ticks++;

    GPIO_CLEAR(DEBUG_PIN);
}
```

使用逻辑分析仪观察：

- 周期；
- 脉宽；
- 最大延迟；
- ISR 执行时间；
- 高优先级中断干扰下的抖动。

### 方法二：DWT 测量

```
uint32_t start = DWT->CYCCNT;

SysTick_Handler();

uint32_t cycles = DWT->CYCCNT - start;
```

需要注意：

- `CYCCNT` 可能回绕；
- 调试模块可能被关闭；
- 低功耗模式下可能停止；
- 开启 Cache、FPU、不同编译优化等级后应分别测量。

### 方法三：统计最坏情况

至少记录：

```
平均 ISR 周期
最大 ISR 执行时间
最大 SysTick 响应延迟
连续丢失/延迟 tick 次数
高优先级中断占用比例
系统空闲比例
```

不能只记录平均值。工业级实时系统关注的是：

WCET和Worst Case LatencyWCET和Worst Case Latency

## 16.3 进阶学习方向

### 内核异常与调度

- SysTick、PendSV、SVC 的协同；
- 异常优先级分组；
- BASEPRI 临界区；
- RTOS tick 中断实现；
- 时间片轮转的底层机制。

### 低功耗与时间补偿

- FreeRTOS tickless idle；
- RTC 校准；
- LPTIM 异步时钟；
- Stop 模式下的时间恢复；
- 睡眠期间时钟漂移补偿。

### 高精度性能工程

- DWT CYCCNT；
- ITM/ETM；
- Tracealyzer、Percepio、SystemView；
- 中断延迟统计；
- WCET 分析；
- Cache 和总线竞争对实时性的影响。

### 高级架构

- 多时基统一抽象；
- SysTick 与硬件定时器分层；
- 多核 Cortex-M 系统时间同步；
- TrustZone 下安全世界与非安全世界的时间基准；
- 异构 MCU 中的跨核时间戳同步；
- 基于硬件时间戳的协议栈设计。