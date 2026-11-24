
## 1. 学习目标

### 理解

- 理解 GPIO 从端口复用、模式选择、输出驱动到输入采样的完整硬件链路。
- 理解推挽、开漏、上拉、下拉、模拟输入、高阻输入的电气含义。
- 理解 GPIO 外部中断的触发路径：引脚输入缓冲器 → 边沿检测器 → EXTI/中断控制器 → NVIC → ISR。
- 理解中断延迟、抖动、脉宽、触发丢失和中断风暴之间的关系。

### 掌握

- 掌握 GPIO 时钟、复用、模式、速度、上下拉、输出数据寄存器的配置方法。
- 掌握中断触发边沿、挂起标志、优先级和中断服务函数的正确处理流程。
- 掌握按键、编码器、脉冲输入、故障输入等典型 GPIO 中断应用。
- 掌握中断与任务、环形缓冲区、定时器、事件标志的协同方式。

### 精通

- 能够分析 GPIO 配置错误造成的浮空、漏电、总线冲突、误触发和 EMI 问题。
- 能够分析 GPIO 中断丢失、重复触发、优先级反转、ISR 阻塞和中断风暴。
- 能够使用寄存器、逻辑分析仪、示波器和 DWT/定时器完成时延与抖动量化。
- 能够设计具备去抖、限流、故障恢复和可观测性的工业级 GPIO 驱动。

### 能够设计

- 能够设计统一的 GPIO 抽象层和外部中断管理框架。
- 能够针对不同电气接口选择推挽、开漏、上拉、下拉和外部电阻方案。
- 能够设计高可靠的按键、霍尔、编码器、报警输入和安全输入电路及软件架构。
- 能够建立 GPIO 配置检查、初始化验证和异常诊断机制。

---

## 2. 前置要求

### 知识要求

- C 语言：位运算、`volatile`、结构体映射寄存器、函数指针。
- MCU 启动流程：复位、时钟树、向量表、启动文件。
- 基本数字电路：高低电平、输入阈值、推挽、开漏、三态。
- 中断机制：中断向量、优先级、屏蔽、挂起、嵌套。
- RTOS 基础：任务、队列、信号量、事件组和临界区。
- 基本电气参数：GPIO 最大灌电流、拉电阻、上升时间、输入漏电流。

### 技能要求

- 能够阅读 MCU 参考手册和数据手册。
- 能够使用示波器、逻辑分析仪和万用表。
- 能够定位 HardFault、总线冲突和中断异常。
- 能够编译、链接并调试裸机或 RTOS 工程。
- 能够通过寄存器窗口验证外设配置结果。

---

## 3. 技术概述

## 3.1 GPIO 的本质

GPIO 是 MCU 与外部数字世界交互的最基础外设。一个 GPIO 引脚通常包含：

```
外部引脚
   │
   ├── 输入保护结构：ESD 二极管、过压/欠压保护
   │
   ├── 输入缓冲器：施密特触发器、输入阈值检测
   │
   ├── 上拉/下拉电阻
   │
   ├── 输出驱动器：推挽 PMOS/NMOS 或开漏 NMOS
   │
   ├── 复用器：GPIO、UART、SPI、TIM、ADC 等
   │
   └── 中断/事件检测逻辑
```

GPIO 配置并不是简单地“设为输入或输出”，而是同时决定：

- 电气驱动能力；
- 输入采样特性；
- 是否接入内部上下拉；
- 是否连接到某个复用外设；
- 是否允许进入中断检测路径；
- 电平变化对功耗和 EMC 的影响。

## 3.2 主流 GPIO 模式

|模式|输出能力|输入能力|典型应用|主要风险|
|---|---|---|---|---|
|推挽输出|高、低均主动驱动|通常可读回|LED、片选、控制信号|多设备同时驱动造成短路|
|开漏输出|只能主动拉低|可读|I²C、线与、共享报警线|上升时间依赖上拉电阻|
|浮空输入|高阻|支持|外部已有明确电平源|悬空导致随机抖动|
|上拉输入|高阻/内部上拉|支持|按键、开漏总线|内部电阻精度较差|
|下拉输入|高阻/内部下拉|支持|默认低电平检测|芯片不一定支持所有引脚|
|模拟模式|关闭数字输入缓冲|连接模拟通道|ADC、低功耗模拟输入|误配置可能增加功耗|
|复用功能|由外设控制|由外设控制|UART、SPI、PWM|复用冲突、配置顺序错误|

## 3.3 GPIO 中断分类

常见中断触发方式：

1. **上升沿触发**：低到高。
2. **下降沿触发**：高到低。
3. **双边沿触发**：任意电平变化。
4. **低电平触发**：电平持续有效时可能反复进入中断。
5. **高电平触发**：同上，适合部分电平型故障输入。
6. **事件触发**：不一定进入 CPU 中断，可连接 DMA、唤醒或其他硬件事件。

---

## 4. 核心特性横向对比

### 4.1 输出模式对比

|维度|推挽输出|开漏输出|复用推挽|复用开漏|
|---|---|---|---|---|
|输出高电平|主动驱动|依赖上拉|外设主动驱动|依赖上拉|
|输出低电平|主动驱动|主动拉低|外设主动驱动|外设主动拉低|
|上升沿速度|快|受 RC 限制|快|受 RC 限制|
|多设备共享|不允许直接共享|支持|通常不支持|支持|
|典型应用|LED、控制脚|I²C、报警线|UART、SPI|I²C、单线协议|
|设计风险|总线冲突|上升时间过慢|复用配置错误|上拉过强导致电流过大|

### 4.2 输入上下拉对比

|类型|默认状态|外部信号断开时|适合场景|注意事项|
|---|---|---|---|---|
|浮空|不确定|随机|外部强驱动|不得用于悬空输入|
|内部上拉|高|高|按键接地、开漏输出|阻值通常为几十 kΩ，离散性大|
|内部下拉|低|低|按键接电源|部分 MCU 不支持|
|外部上拉|由阻值决定|稳定|高速、长线、严格时序|需校核功耗和上升时间|
|外部下拉|由阻值决定|稳定|工业输入、抗干扰|需考虑输入源驱动能力|

### 4.3 GPIO 中断触发方式对比

|触发方式|优点|缺点|典型应用|
|---|---|---|---|
|上升沿|事件明确、不会持续触发|下降沿信息丢失|脉冲计数、设备上线|
|下降沿|适合低有效信号|上升沿信息丢失|按键按下、故障有效|
|双边沿|信息完整|中断频率翻倍|编码器、脉宽测量|
|高/低电平|能处理持续有效状态|易产生中断风暴|特定电平型唤醒|
|定时采样|抗抖稳定、行为可控|产生固定采样开销|按键、慢速开关|
|外部中断 + 定时确认|响应快且抗抖|架构复杂|工业按键、报警输入|

---

## 5. 底层原理与功能特性深度解析

以下示例以常见 Cortex-M MCU 为抽象模型。不同厂商寄存器命名可能不同，实际实现必须以参考手册为准。

## 5.1 GPIO 时钟与寄存器访问

GPIO 外设通常挂载于 AHB/APB 总线。关闭时钟时访问 GPIO 寄存器可能无效，部分芯片甚至会触发总线错误。

```
#include <stdint.h>

#define BIT(n)                 (1UL << (n))

typedef struct {
    volatile uint32_t MODER;
    volatile uint32_t OTYPER;
    volatile uint32_t OSPEEDR;
    volatile uint32_t PUPDR;
    volatile uint32_t IDR;
    volatile uint32_t ODR;
    volatile uint32_t BSRR;
    volatile uint32_t LCKR;
    volatile uint32_t AFR[2];
} gpio_regs_t;

#define GPIOA_BASE             (0x48000000UL)
#define GPIOA                  ((gpio_regs_t *)GPIOA_BASE)

#define RCC_BASE               (0x40021000UL)
#define RCC_AHBENR             (*(volatile uint32_t *)(RCC_BASE + 0x14U))
#define RCC_AHBENR_GPIOAEN     BIT(17)

static void gpioa_clock_enable(void)
{
    RCC_AHBENR |= RCC_AHBENR_GPIOAEN;

    /*
     * 某些 MCU 需要读回寄存器，确保时钟写入已经到达外设总线。
     */
    (void)RCC_AHBENR;
}
```

### 设计要点

- **寄存器必须声明为 `volatile`** ，避免编译器删除或合并硬件访问。
- 使能时钟后应读回或执行适当的同步操作。
- 不要通过 `ODR |= mask` 修改单个位，除非确认不存在并发访问。
- 多任务或 ISR 同时操作同一 GPIO 时，应使用原子寄存器或锁保护。

## 5.2 输出模式配置

以 PA5 为例，配置为推挽高速输出、无上下拉。

```
#define GPIO_MODE_OUTPUT      1U
#define GPIO_OTYPE_PP         0U
#define GPIO_SPEED_HIGH       3U
#define GPIO_PUPD_NONE        0U

static void gpio_pin_set_output(gpio_regs_t *gpio, uint8_t pin)
{
    uint32_t shift = (uint32_t)pin * 2U;
    uint32_t mask  = 0x3UL << shift;

    gpio->MODER &= ~mask;
    gpio->MODER |= (GPIO_MODE_OUTPUT << shift);

    gpio->OTYPER &= ~BIT(pin);

    gpio->OSPEEDR &= ~mask;
    gpio->OSPEEDR |= (GPIO_SPEED_HIGH << shift);

    gpio->PUPDR &= ~mask;
}
```

### 为什么推荐 BSRR 而不是 ODR？

```
#define GPIO_BSRR_SET(pin)    BIT(pin)
#define GPIO_BSRR_RESET(pin)  BIT((pin) + 16U)

static inline void gpio_write(gpio_regs_t *gpio,
                              uint8_t pin,
                              bool level)
{
    if (level) {
        gpio->BSRR = GPIO_BSRR_SET(pin);
    } else {
        gpio->BSRR = GPIO_BSRR_RESET(pin);
    }
}
```

`BSRR` 通常支持单周期原子置位/复位：

```
BSRR[0..15]   = 1：置位对应 GPIO
BSRR[16..31]  = 1：复位对应 GPIO
```

而下面的代码是典型的读-改-写操作：

```
gpio->ODR |= BIT(pin);
```

如果 ISR 在读和写之间修改了其他位，可能覆盖 ISR 的修改结果。

## 5.3 输入模式与采样

```
#define GPIO_MODE_INPUT       0U
#define GPIO_PUPD_PULLUP      1U
#define GPIO_PUPD_PULLDOWN    2U

static void gpio_pin_set_input_pullup(gpio_regs_t *gpio, uint8_t pin)
{
    uint32_t shift = (uint32_t)pin * 2U;
    uint32_t mask  = 0x3UL << shift;

    gpio->MODER &= ~mask;

    gpio->PUPDR &= ~mask;
    gpio->PUPDR |= GPIO_PUPD_PULLUP << shift;
}

static bool gpio_read(gpio_regs_t *gpio, uint8_t pin)
{
    return (gpio->IDR & BIT(pin)) != 0U;
}
```

输入采样通常经过同步器，外部信号到达 `IDR` 并非零延迟。若输入信号变化速度接近 MCU 内部采样时钟，还可能发生：

- 亚稳态；
- 脉冲被漏采；
- 边沿检测结果不确定；
- 双边沿中断间隔抖动。

对于异步外部输入，应满足数据手册规定的最小高/低脉宽。若需要统计高速脉冲，应优先使用定时器输入捕获，而不是软件 GPIO 中断。

## 5.4 外部中断配置流程

通用配置路径如下：

```
GPIO 输入配置
    ↓
GPIO 端口映射到 EXTI 线路
    ↓
选择上升沿/下降沿
    ↓
清除历史挂起标志
    ↓
使能 EXTI 中断屏蔽
    ↓
配置 NVIC 优先级
    ↓
使能 NVIC
```

抽象代码：

```
typedef enum {
    GPIO_INT_RISING,
    GPIO_INT_FALLING,
    GPIO_INT_BOTH
} gpio_irq_edge_t;

typedef void (*gpio_irq_callback_t)(uint8_t pin, void *arg);

typedef struct {
    uint8_t              pin;
    gpio_irq_edge_t      edge;
    gpio_irq_callback_t  callback;
    void                *arg;
} gpio_irq_config_t;

static int gpio_irq_init(const gpio_irq_config_t *cfg)
{
    if (cfg == NULL || cfg->callback == NULL || cfg->pin >= 16U) {
        return -1;
    }

    /*
     * 1. 配置 GPIO 为输入
     * 2. 配置端口到 EXTI 映射
     * 3. 配置触发边沿
     * 4. 清除 pending
     * 5. 使能 mask
     * 6. 配置并使能 NVIC
     */

    return 0;
}
```

## 5.5 中断服务函数的正确结构

```
#define EXTI_LINE5                BIT(5)

static volatile uint32_t g_button_irq_count;

void EXTI9_5_IRQHandler(void)
{
    uint32_t pending = EXTI->PR1 & EXTI_LINE5;

    if ((pending & EXTI_LINE5) != 0U) {
        /*
         * 必须先清除挂起标志，避免退出 ISR 后立即重复进入。
         * 某些 MCU 的 pending 寄存器采用写 1 清除。
         */
        EXTI->PR1 = EXTI_LINE5;

        g_button_irq_count++;

        /*
         * ISR 中只做确定性、短路径操作：
         * - 记录时间戳
         * - 写入环形缓冲区
         * - 发送 RTOS ISR 安全事件
         *
         * 不应在这里执行延时、打印、动态内存分配或复杂协议解析。
         */
    }
}
```

### 为什么必须先清除挂起标志？

如果先执行复杂逻辑，再清除 pending：

```
ISR 进入
  ↓
执行耗时逻辑
  ↓
新的边沿到达，pending 保持有效
  ↓
清除 pending
  ↓
退出 ISR
```

新事件可能被清掉，从而造成丢中断。更稳妥的方式是：

1. 读取 pending；
2. 立即清除已确认的 pending；
3. 记录事件；
4. 退出 ISR；
5. 在下层进行业务处理。

但对于“清除后仍可能有新边沿”的硬件，需要结合数据手册确认 pending 的行为，并设计二次检查或硬件锁存。

## 5.6 去抖架构

机械按键抖动常见持续时间为 **1~20 ms**，不同开关、温度、老化状态差异较大。不能简单假设固定 10 ms 一定可靠。

推荐架构：

```
GPIO 边沿中断
    ↓
屏蔽该 GPIO 中断
    ↓
启动一次性定时器，周期 T_debounce
    ↓
定时器到期后重新采样 GPIO
    ↓
连续两次/多次一致后确认状态
    ↓
清除状态并重新使能 GPIO 中断
```

示例：

```
typedef struct {
    volatile bool irq_pending;
    volatile bool stable_level;
    uint32_t       debounce_ms;
} button_t;

static button_t g_button;

void BUTTON_EXTI_IRQHandler(void)
{
    if (exti_pending(BUTTON_PIN)) {
        exti_clear_pending(BUTTON_PIN);
        exti_disable_line(BUTTON_PIN);

        g_button.irq_pending = true;
        timer_start_oneshot(g_button.debounce_ms);
    }
}

void button_debounce_timer_callback(void)
{
    bool level = gpio_read(BUTTON_GPIO, BUTTON_PIN);

    if (g_button.irq_pending) {
        g_button.stable_level = level;
        g_button.irq_pending = false;

        /*
         * 通过队列/事件通知任务，而不是在定时器回调中执行业务。
         */
        button_event_post(level);
        exti_enable_line(BUTTON_PIN);
    }
}
```

对于高可靠输入，可使用连续采样状态机：

```
typedef struct {
    uint8_t history;
    bool    stable;
} debounce_filter_t;

static bool debounce_update(debounce_filter_t *filter, bool sample)
{
    filter->history = (uint8_t)((filter->history << 1U) | (sample ? 1U : 0U));

    if (filter->history == 0xFFU) {
        filter->stable = true;
    } else if (filter->history == 0x00U) {
        filter->stable = false;
    } else {
        return false;
    }

    return true;
}
```

---

## 6. 性能量化分析

以下数据为典型 **Cortex-M4，80 MHz，零等待 SRAM，编译器 `-O2`** 条件下的工程估算值。实际结果必须通过目标芯片实测。

## 6.1 GPIO 操作时间

|操作方式|典型指令路径|典型耗时|
|---|---|---|
|`BSRR` 置位|1 次寄存器写|25~80 ns|
|`ODR` 读改写|读 + 修改 + 写|75~180 ns|
|HAL 层 GPIO 写|函数调用 + 参数检查 + 寄存器写|150~500 ns|
|ISR 进入到用户代码|硬件压栈 + 向量跳转|0.2~1.0 μs|
|简单 ISR 完成|清 pending + 记录事件|0.5~2.0 μs|

时延可近似表示为：

Tlatency=Tsync+TNVIC+Tstack+TISR−entryTlatency​=Tsync​+TNVIC​+Tstack​+TISR−entry​

其中：

- TsyncTsync​：输入同步和边沿检测时间；
- TNVICTNVIC​：中断仲裁时间；
- TstackTstack​：硬件压栈时间；
- TISR−entryTISR−entry​：软件入口代码时间。

## 6.2 上拉电阻与上升时间

开漏信号上升时间近似为：

tr≈2.2RpCLtr​≈2.2Rp​CL​

其中：

- RpRp​：上拉电阻；
- CLCL​：总线、电容、输入引脚及 PCB 寄生电容。

例如：

```
R_p = 4.7 kΩ
C_L = 200 pF
```

则：

tr≈2.2×4700×200pF≈2.07μstr​≈2.2×4700×200pF≈2.07μs

如果通信速率要求上升时间不超过 1 μs，需要：

Rp≤1μs2.2×200pF≈2.27kΩRp​≤2.2×200pF1μs​≈2.27kΩ

但电阻过小会增加低电平灌电流：

ILOW=VDD−VOLRpILOW​=Rp​VDD​−VOL​​

以 VDD=3.3VVDD​=3.3V、VOL=0.4VVOL​=0.4V、Rp=2.2kΩRp​=2.2kΩ 计算：

ILOW≈1.32mAILOW​≈1.32mA

必须同时满足 GPIO 灌电流上限和功耗指标。

## 6.3 中断 CPU 占用率

若外部中断频率为 firqfirq​，单次 ISR 执行时间为 TisrTisr​，则 CPU 占用率近似为：

U=firq×TisrU=firq​×Tisr​

例如：

```
中断频率：20 kHz
ISR 时间：2 μs
```

U=20000×2μs=4%U=20000×2μs=4%

当中断频率达到 100 kHz、ISR 时间达到 3 μs 时：

U=100000×3μs=30%U=100000×3μs=30%

此时还未计入更高优先级中断、缓存失效、RTOS 调度和任务切换成本，系统实时裕量已经明显下降。

## 6.4 RAM 与 Flash 开销

典型 GPIO 抽象层开销：

|项目|典型开销|
|---|---|
|单个 GPIO 配置结构体|12~24 B|
|16 路中断回调表|128~256 B|
|环形缓冲区 64 项，每项 8 B|512 B|
|去抖状态结构|8~32 B|
|简单驱动代码 Flash|1~4 KB|
|HAL 层完整 GPIO 模块|2~10 KB|

### 优化手段

- ISR 只记录事件，不执行业务，通常可将 ISR 从 5~~20 μs 降至 0.5~~2 μs。
- 高频脉冲使用定时器输入捕获，CPU 占用率可从数十个百分点降至 1% 以下。
- 使用 BSRR 替代 ODR 读改写，减少竞态并降低执行周期。
- 多个 GPIO 事件通过批量读取端口寄存器，减少重复总线访问。
- 对固定配置使用静态常量表，避免运行时复杂初始化。

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
是否需要输出信号？
├── 否
│   ├── 输入是否高速、脉宽小于数个 CPU 周期？
│   │   ├── 是：使用定时器输入捕获/计数器，不使用 GPIO ISR
│   │   └── 否
│   │       ├── 是否需要立即响应？
│   │       │   ├── 是：GPIO 外部中断
│   │       │   └── 否：定时采样
│   │       └── 是否存在机械抖动？
│   │           ├── 是：中断唤醒 + 定时确认
│   │           └── 否：直接边沿中断
│   └── 外部是否已有稳定上拉/下拉？
│       ├── 是：浮空输入
│       └── 否：内部上下拉或外部精密电阻
└── 是
    ├── 是否需要多设备共享线路？
    │   ├── 是：开漏 + 外部上拉
    │   └── 否：推挽
    ├── 是否要求低 EMI？
    │   ├── 是：降低 GPIO slew rate
    │   └── 否：根据时序选择速度
    └── 是否需要复用外设？
        ├── 是：配置复用功能并校验引脚复用冲突
        └── 否：普通 GPIO 输出
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|板载 LED|推挽输出，低速|简单、无共享、降低 EMI|
|按键|上拉输入 + 下降沿 + 定时去抖|默认状态明确，响应快|
|I²C|开漏 + 外部上拉|支持线与和多主机仲裁|
|电机故障输入|外部下拉/上拉 + 下降沿中断 + 硬件锁存|防止断线导致误判|
|编码器|定时器正交编码器接口|避免高频 GPIO ISR|
|外部脉冲计数|定时器外部时钟/输入捕获|精度高、CPU 开销低|
|低功耗唤醒|唤醒 GPIO + 低功耗上下拉|支持 STOP/Standby 唤醒|
|多板卡共享报警线|开漏输出 + 线与|任意设备可拉低报警|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **先确定电气状态，再确定软件模式**。
2. 任何输入都必须具有确定的默认电平。
3. 任何共享线路都禁止多个推挽输出直接连接。
4. 高频输入优先使用定时器、DMA、捕获比较等硬件资源。
5. ISR 只做事件采集，不做业务处理。
6. 所有 GPIO 初始化必须显式配置模式、上下拉、速度和初始输出状态。
7. 输出 GPIO 应先设置安全电平，再切换为输出模式，避免启动瞬间毛刺。
8. 对关键安全输入必须同时考虑断线、短路、反接和电平异常。
9. 对中断 pending 的清除语义必须以芯片手册为准，不能凭经验假设。
10. 对中断输入增加统计计数、时间戳和异常频率监测。

## 8.2 选型决策矩阵

|指标|推挽|开漏|GPIO 中断|定时器捕获|定时采样|
|---|---|---|---|---|---|
|输出速度|5|3|-|-|-|
|多设备共享|1|5|-|-|-|
|实时响应|-|-|5|5|2|
|高频处理能力|-|-|2|5|1|
|抗抖能力|-|-|2|2|5|
|软件复杂度|4|3|3|3|4|
|CPU 占用|-|-|2|5|3|

评分：1 为弱，5 为强。

## 8.3 工业级编码规范

- GPIO 号、有效电平和默认状态使用具名宏或枚举。
- 不使用魔数直接操作引脚。
- 不在 ISR 中调用非 ISR-safe API。
- 不在 ISR 中使用 `printf`、`malloc`、阻塞队列、延时函数。
- 所有共享变量使用 `volatile` 仅解决编译器优化问题；原子性仍需额外保证。
- 多位状态数据在 ISR 与任务间传递时使用临界区、原子操作或队列。
- 初始化函数返回错误码，禁止静默失败。
- 对配置后的关键寄存器进行读回验证。
- 中断回调必须支持空指针检查和注销。
- 生产代码应支持 GPIO 自检和异常计数。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：输入引脚浮空

### 错误代码

```
gpio_mode_input(GPIOA, 3);
bool value = gpio_read(GPIOA, 3);
```

### 根因

输入缓冲器为高阻态，外部没有稳定电平，环境噪声会被放大为随机逻辑变化。

### 正确实现

```
gpio_mode_input(GPIOA, 3);
gpio_pullup_enable(GPIOA, 3);
```

或使用外部上下拉电阻。

### 风险影响

- 随机中断；
- 功耗增加；
- 状态机误动作；
- 设备上电行为不确定。

## 9.2 错误二：使用 ODR 读改写造成并发覆盖

### 错误代码

```
GPIOA->ODR |= (1U << 5);
```

### 根因

该操作通常包含读、修改、写三个步骤。ISR 或其他任务可能在中间修改同一端口的其他位。

### 正确实现

```
GPIOA->BSRR = (1U << 5);
```

### 风险影响

- 其他 GPIO 状态被意外覆盖；
- 时序控制出现偶发错误；
- 并发问题难以复现。

## 9.3 错误三：ISR 中延时去抖

### 错误代码

```
void EXTI0_IRQHandler(void)
{
    exti_clear_pending(0);

    delay_ms(20);       /* 错误 */
    if (!gpio_read(GPIOA, 0)) {
        button_pressed();
    }
}
```

### 根因

ISR 阻塞 CPU，期间可能屏蔽其他中断、延迟 RTOS 调度并积压实时任务。

### 正确实现

```
void EXTI0_IRQHandler(void)
{
    exti_clear_pending(0);
    exti_disable_line(0);
    timer_start_oneshot(20);
}
```

### 风险影响

- 高优先级中断响应超时；
- 丢失串口、定时器和采样事件；
- 系统出现不可预测的实时性退化。

## 9.4 错误四：没有清除中断挂起标志

### 错误代码

```
void EXTI1_IRQHandler(void)
{
    button_event_post();
    /* 忘记清除 pending */
}
```

### 根因

NVIC/EXTI 仍认为中断源有效，退出 ISR 后可能立即再次进入。

### 正确实现

```
void EXTI1_IRQHandler(void)
{
    if (exti_is_pending(1)) {
        exti_clear_pending(1);
        button_event_post_from_isr();
    }
}
```

### 风险影响

- 中断风暴；
- CPU 占用率接近 100%；
- 看门狗复位；
- 其他任务无法运行。

## 9.5 错误五：多个推挽输出直接并联

### 错误代码

```
设备 A：推挽输出高
设备 B：推挽输出低
两者直接连接
```

### 根因

一个器件主动向电源供电，另一个器件主动接地，形成近似短路。

### 正确实现

- 使用开漏输出；
- 配置外部上拉；
- 或使用总线收发器/仲裁器件。

### 风险影响

- GPIO 过流；
- 电平异常；
- 芯片永久损伤；
- 通信不稳定。

---

## 10. 多机制组合使用方案

## 10.1 GPIO 中断 + 环形缓冲区 + RTOS 任务

适合：

- 脉冲事件；
- 旋钮/编码器低速输入；
- 多路报警输入；
- 需要保留事件时间顺序的应用。

### 架构

```
GPIO ISR
  ├── 清除 pending
  ├── 读取引脚
  ├── 读取时间戳
  └── 写入无锁/单生产者环形缓冲区
             ↓
        RTOS 消费任务
             ↓
      去抖、协议解析、业务处理
```

### 代码框架

```
#include <stdbool.h>
#include <stdint.h>

#define GPIO_EVENT_QUEUE_SIZE  64U

typedef struct {
    uint8_t  pin;
    bool     level;
    uint32_t timestamp;
} gpio_event_t;

typedef struct {
    gpio_event_t buffer[GPIO_EVENT_QUEUE_SIZE];
    volatile uint32_t write_idx;
    volatile uint32_t read_idx;
    volatile uint32_t overflow_count;
} gpio_event_queue_t;

static gpio_event_queue_t g_event_queue;

static bool gpio_event_push_isr(uint8_t pin,
                                bool level,
                                uint32_t timestamp)
{
    uint32_t write = g_event_queue.write_idx;
    uint32_t next  = (write + 1U) % GPIO_EVENT_QUEUE_SIZE;

    if (next == g_event_queue.read_idx) {
        g_event_queue.overflow_count++;
        return false;
    }

    g_event_queue.buffer[write] = (gpio_event_t) {
        .pin       = pin,
        .level     = level,
        .timestamp = timestamp
    };

    /*
     * 单生产者场景下，最后发布 write_idx。
     * 若存在多生产者，必须使用临界区或原子 CAS。
     */
    g_event_queue.write_idx = next;
    return true;
}

static bool gpio_event_pop(gpio_event_t *event)
{
    if (event == NULL) {
        return false;
    }

    uint32_t read = g_event_queue.read_idx;

    if (read == g_event_queue.write_idx) {
        return false;
    }

    *event = g_event_queue.buffer[read];
    g_event_queue.read_idx =
        (read + 1U) % GPIO_EVENT_QUEUE_SIZE;

    return true;
}
```

### 关键设计点

- `write_idx` 只能由 ISR 生产者修改。
- `read_idx` 只能由任务消费者修改。
- 队列满时必须记录溢出，不允许静默覆盖。
- 事件必须带时间戳，否则无法分析丢失和抖动。
- 队列大小应按最坏突发事件率设计：

N≥(Rproducer−Rconsumer)×Tblocking+marginN≥(Rproducer​−Rconsumer​)×Tblocking​+margin

## 10.2 GPIO 中断 + 定时器去抖 + 状态机

适合机械按键、继电器反馈、限位开关。

```
边沿中断
  ↓
锁定输入
  ↓
定时器采样
  ↓
连续 N 次一致？
  ├── 否：继续采样
  └── 是：确认状态变化并通知业务
```

## 10.3 GPIO + DMA/定时器

对于高速并行输入，可使用：

```
定时器触发采样
    ↓
GPIO 端口 IDR
    ↓
DMA 搬运到内存
    ↓
任务批量解析
```

这样可以避免每一个边沿都进入 CPU，适合：

- 逻辑分析采样；
- 并行数据采集；
- 高速脉冲序列；
- 低抖动时序测量。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业控制器急停输入

### 需求

- 急停信号低有效；
- 正常状态为高；
- 断线时必须判定为故障；
- 响应时间小于 1 ms；
- 不能依赖 RTOS 任务调度完成第一阶段处理。

### 架构

```
急停触点
  ↓
外部上拉 + 保护电路
  ↓
GPIO 下降沿中断
  ↓
ISR 关闭功率输出
  ↓
记录故障时间戳
  ↓
通知安全任务完成状态机和日志
```

### 核心代码

```
static volatile bool g_emergency_stop;
static volatile uint32_t g_estop_timestamp;

void ESTOP_IRQHandler(void)
{
    if (exti_is_pending(ESTOP_PIN)) {
        exti_clear_pending(ESTOP_PIN);

        /*
         * 第一阶段动作必须是确定性硬件动作。
         * 例如关闭 PWM、置位硬件使能禁止信号。
         */
        pwm_output_disable();
        safety_gate_disable();

        g_estop_timestamp = timer_get_counter();
        g_emergency_stop = true;

        safety_event_notify_from_isr();
    }
}
```

### 设计要点

- 急停不能只依赖软件轮询。
- 不能在 ISR 中写 Flash、打印日志或等待任务。
- 关键关断最好由硬件链路直接完成，GPIO 中断作为诊断和状态同步路径。
- 输入电路需要考虑断线检测和触点抖动。
- 需要通过示波器验证“外部边沿到功率关断”的总延迟。

## 11.2 案例二：电机霍尔脉冲采集

### 需求

- 霍尔频率最高 50 kHz；
- 需要计算转速和换相位置；
- 不能因中断负载影响 PWM 实时性。

### 错误方案

每个霍尔边沿进入 GPIO ISR，并在 ISR 中执行转速计算和状态切换。

### 推荐方案

```
霍尔输入
  ↓
定时器输入捕获/正交接口
  ↓
DMA 或捕获寄存器
  ↓
低频任务计算转速
```

### 转速计算

若相邻边沿捕获计数差为 ΔCΔC，定时器频率为 ftimerftimer​，每转脉冲数为 PPRPPR：

RPM=60ftimerΔC×PPRRPM=ΔC×PPR60ftimer​​

### 设计要点

- GPIO 只负责复用为定时器输入。
- 使用输入滤波器抑制窄脉冲和 EMI。
- 低速时使用周期测量，高速时使用门控计数，避免分辨率失衡。
- 发生捕获溢出时必须进行扩展计数处理。

## 11.3 案例三：多设备共享故障报警线

### 需求

- 8 个模块共享一根报警线；
- 任意模块发生故障都可以拉低；
- 主控需要检测报警并读取故障源。

### 硬件与软件方案

```
每个模块：开漏输出
共享线路：单个外部上拉
主控：GPIO 输入 + 下降沿中断
故障源：通过 SPI/CAN/寄存器进一步查询
```

### 设计要点

- 所有模块只能主动拉低，不能主动拉高。
- 上拉电阻根据总线电容和响应时间计算。
- 主控检测到报警后，不应直接假设故障源唯一。
- 故障线应具备超时、断线和粘连诊断机制。
- 报警恢复应由故障源显式释放，不能由主控强制清除。

---

## 12. 高频问题深度答疑

### 问题一：为什么内部上拉不能替代外部上拉？

内部上拉通常阻值范围较宽，且随工艺、电压、温度变化明显。例如标称 40 kΩ 的内部上拉，实际可能在较大范围内变化。它适合按键和低速控制输入，但不适合：

- 高速总线；
- 长线；
- 严格上升时间要求；
- 强 EMI 环境；
- 需要精确功耗预算的场景。

高速或工业线路应使用外部精密电阻，并结合电容、线长和阈值计算。

### 问题二：GPIO 中断为什么会丢边沿？

常见原因包括：

- 输入边沿间隔小于 ISR 处理能力；
- 多个边沿在同一个 pending 位上合并；
- ISR 清除 pending 的时机不正确；
- 中断被高优先级任务或临界区长期屏蔽；
- 外部脉冲宽度小于 GPIO 输入同步器要求；
- 使用电平触发但未及时释放信号。

如果事件不能丢失，应使用定时器捕获、硬件 FIFO、DMA 或外部锁存器。

### 问题三：`volatile` 能否保证 ISR 与任务之间的数据安全？

不能。`volatile` 只保证编译器每次都执行访问，不保证：

- 多字节数据原子性；
- 读写顺序；
- 多核一致性；
- 复合操作的不可分割性；
- 生产者和消费者之间的内存序。

单 bit 或天然字长数据通常可原子读写，但仍需根据架构确认。复杂数据应使用队列、临界区、原子操作或内存屏障。

### 问题四：双边沿中断适合测量脉宽吗？

低速、低抖动且对精度要求不高时可以。但工业级脉宽测量更推荐定时器输入捕获：

- GPIO ISR 受中断屏蔽和任务负载影响；
- ISR 时间戳存在软件路径抖动；
- 双边沿中断频率翻倍；
- 定时器捕获由硬件锁存边沿时刻，精度和确定性更高。

### 问题五：为什么 GPIO 输出初始化会产生毛刺？

常见初始化顺序如下：

```
复位默认输入/浮空
  ↓
配置为输出
  ↓
再写期望电平
```

在配置为输出的瞬间，输出锁存器可能仍为默认值，从而产生短暂错误电平。

推荐：

```
static void gpio_safe_output_init(gpio_regs_t *gpio,
                                  uint8_t pin,
                                  bool safe_level)
{
    /*
     * 先设置输出锁存器，再切换输出模式。
     */
    if (safe_level) {
        gpio->BSRR = BIT(pin);
    } else {
        gpio->BSRR = BIT(pin + 16U);
    }

    gpio_pin_set_output(gpio, pin);
}
```

还需要确认 MCU 数据手册对输出锁存器和模式切换的具体行为。

### 问题六：按键是否应该完全使用定时采样，而不用中断？

取决于系统目标：

- 低功耗唤醒：中断更合适；
- 普通人机界面：10~20 ms 定时采样通常足够；
- 高可靠机械输入：中断触发 + 定时确认；
- 输入数量多：统一定时扫描更容易维护；
- 需要立即响应：边沿中断用于唤醒，再由任务确认。

没有绝对方案，应以功耗、响应时间、抖动、软件复杂度综合决策。

---

## 13. 课程核心总结

### 核心要点

1. **GPIO 配置同时涉及逻辑功能、电气特性和时序性能**。
2. 推挽适合独占输出，开漏适合共享线路。
3. 输入不得悬空，内部上下拉只适合低速和非精密场景。
4. 输出初始化应先设置安全电平，再切换输出模式。
5. GPIO ISR 必须快速、确定、不可阻塞。
6. 中断事件应通过队列、环形缓冲区或事件组交给任务处理。
7. 高频脉冲优先使用定时器输入捕获、计数器和 DMA。
8. 机械输入采用中断唤醒、定时确认或连续采样去抖。
9. 使用 `BSRR` 等原子寄存器避免 GPIO 端口并发覆盖。
10. 关键输入和急停链路必须结合硬件安全机制，不能只依赖软件 ISR。

### 性能排序

在常见 MCU 上，处理效率通常为：

```
硬件定时器/DMA
    >
定时器输入捕获
    >
GPIO 中断 + 极简 ISR
    >
GPIO 中断 + RTOS 通知
    >
定时采样任务
    >
ISR 中复杂业务处理
```

### 通用选型结论

- **独占数字输出：推挽。**
- **共享数字线路：开漏 + 外部上拉。**
- **低速离散输入：上下拉 + 定时采样或中断。**
- **机械输入：中断唤醒 + 定时去抖。**
- **高速脉冲：定时器输入捕获/计数器。**
- **安全输入：硬件关断 + GPIO 中断诊断。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|GPIO 模式|触发/采集方式|关键注意事项|
|---|---|---|---|
|LED|推挽输出|普通写|限流电阻、默认关闭|
|按键|上拉输入|下降沿 + 定时去抖|机械抖动、有效电平|
|I²C|开漏复用|外设硬件|上升时间、总线电容|
|UART|复用推挽|UART 外设|复用冲突、电平匹配|
|霍尔|复用输入捕获|定时器|输入滤波、溢出|
|急停|上拉输入|下降沿中断|硬件关断、断线诊断|
|报警共享线|开漏输出|下降沿中断|不能推挽拉高|
|低功耗唤醒|低功耗输入|唤醒中断|漏电、默认电平|

### 14.2 特性对比表

|项目|推荐|
|---|---|
|原子置位|`BSRR` 或厂商原子 GPIO 寄存器|
|单 GPIO 读取|`IDR`|
|多 GPIO 快速采样|端口寄存器整体读取|
|中断清除|按手册写 1 清除/读后清除|
|高频事件|定时器捕获、DMA|
|ISR 通信|ISR-safe 队列、事件、环形缓冲区|
|去抖|定时确认或连续采样|
|共享数据|原子变量、临界区、队列|
|生产诊断|中断计数、溢出计数、时间戳|

---

## 15. 学习效果自检

完成本课后，应能够回答并实现：

- [ ]  能说明推挽与开漏的电气差异。
- [ ]  能根据输入默认电平选择上拉或下拉。
- [ ]  能计算开漏总线的上升时间和低电平灌电流。
- [ ]  能解释为什么输入浮空会导致误触发。
- [ ]  能使用原子 GPIO 寄存器实现并发安全的置位和复位。
- [ ]  能正确配置 GPIO 复用和外部中断映射。
- [ ]  能正确清除中断挂起标志。
- [ ]  能设计不在 ISR 中阻塞的按键去抖方案。
- [ ]  能计算给定中断频率和 ISR 时长下的 CPU 占用率。
- [ ]  能判断何时必须使用定时器输入捕获而不是 GPIO 中断。
- [ ]  能设计 GPIO ISR 与 RTOS 任务之间的事件传递链路。
- [ ]  能为急停、故障输入和共享报警线设计故障安全机制。
- [ ]  能使用逻辑分析仪测量输入到 ISR 翻转输出的延迟。
- [ ]  能定位中断风暴、重复中断和 GPIO 状态被覆盖问题。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：基础 GPIO 驱动

实现一个不依赖 HAL 的 GPIO 驱动，要求：

- 支持输入、推挽输出、开漏输出；
- 支持上下拉和输出速度；
- 使用原子置位/复位；
- 初始化失败返回错误码；
- 支持寄存器配置回读验证。

### 任务二：按键中断与去抖

实现：

```
下降沿中断
  ↓
禁用中断
  ↓
20 ms 定时器
  ↓
采样确认
  ↓
事件发送到任务
```

测试内容：

- 单击；
- 长按；
- 快速连续点击；
- 按键抖动；
- 按键卡死；
- 中断队列溢出。

### 任务三：GPIO 事件环形缓冲区

要求：

- 支持至少 4 路 GPIO；
- 每个事件保存 pin、level、时间戳；
- ISR 作为单生产者；
- 任务作为单消费者；
- 记录队列溢出次数；
- 对比环形缓冲区与 RTOS 队列的 CPU 和 RAM 开销。

### 任务四：高速脉冲方案对比

使用信号发生器产生 1 kHz、10 kHz、50 kHz、100 kHz 输入，分别测试：

1. GPIO 中断；
2. 定时器输入捕获；
3. 定时器外部计数；
4. DMA 批量采样。

记录：

- 丢脉冲数；
- CPU 占用率；
- 最大中断延迟；
- 时间戳抖动；
- RAM 使用量。

## 16.2 性能测试方法

### 测量 ISR 延迟

```
void EXTI_IRQHandler(void)
{
    test_gpio_set();          /* ISR 第一条可观测动作 */

    exti_clear_pending(PIN);
    gpio_event_push_isr(PIN, gpio_read(GPIOA, PIN), dwt_get_cycle());

    test_gpio_reset();
}
```

使用示波器测量：

```
外部信号边沿
    到
测试 GPIO 翻转
```

得到：

- 平均延迟；
- 最大延迟；
- 最小延迟；
- 延迟抖动；
- 高优先级中断影响。

### 测量 CPU 占用

通过 DWT、系统定时器或 RTOS runtime statistics 统计：

UISR=∑TISRTmeasurementUISR​=Tmeasurement​∑TISR​​

同时测试以下工况：

- 无其他中断；
- UART 高负载；
- DMA 高负载；
- RTOS 临界区；
- Flash 擦写；
- 低功耗唤醒。

## 16.3 进阶学习方向

- Cortex-M NVIC 优先级分组、尾链、迟到中断和中断嵌套。
- GPIO 与 EXTI 的厂商差异及跨平台抽象。
- 定时器输入捕获、PWM 输入、编码器接口。
- DMA 触发链路和 GPIO 采样。
- 低功耗 GPIO 保持、唤醒源和漏电优化。
- EMC/ESD 对 GPIO 输入的影响及硬件滤波。
- 安全输入冗余、反相采样、断线检测和 ISO 13849 思路。
- RTOS 中断延迟分析、优先级反转和 ISR-safe API。
- 使用形式化状态机验证输入故障恢复逻辑。
- 建立 GPIO 配置静态检查工具，自动检测复用冲突、浮空输入和危险默认状态。