

> 本课以 **STM32 Cortex-M 系列 EXTI** 为主线，重点讨论 GPIO 外部中断从电气输入、边沿检测、挂起标志、NVIC 分发到 ISR/事件处理的完整链路。  
> STM32F1、F4、G0、G4、H7、U5 等系列在 EXTI 寄存器组织和路由方式上存在差异，本文使用“共性原理 + 系列差异提示”的方式展开。实际开发时必须以目标芯片参考手册和启动文件为准。

---

## 1. 学习目标

### 1.1 理解

完成本课后，应能够理解：

- EXTI、GPIO、SYSCFG/AFIO、NVIC、CPU 异常入口之间的关系。
- 外部中断从输入电平变化到执行 ISR 的完整硬件路径。
- **边沿触发、中断屏蔽、事件屏蔽、挂起标志、软件触发**的含义。
- 为什么机械按键会产生抖动，以及为什么“进入一次 ISR”不等于“按键动作一次”。
- 为什么 EXTI 的 pending flag 处理不当会导致中断风暴、丢中断或误触发。

### 1.2 掌握

能够独立完成：

- GPIO 输入和 EXTI 线路映射配置。
- 上升沿、下降沿、双边沿触发配置。
- NVIC 优先级和 IRQ 通道配置。
- 中断服务函数中的 pending flag 判断与清除。
- 按键、脉冲输入、故障输入、唤醒输入的基础驱动。
- 基于 EXTI 的 ISR 快速确认、时间戳记录、事件投递架构。

### 1.3 精通

能够深入分析：

- EXTI 线路复用冲突与端口映射限制。
- 中断延迟、ISR 执行时间、响应抖动和高频输入吞吐能力。
- EXTI 与 DMA、定时器输入捕获、低功耗唤醒、RTOS 任务通知的协同。
- 中断嵌套、优先级反转、共享 IRQ、竞态条件和清 pending 时序问题。
- 不同 STM32 系列 EXTI 结构差异及其对驱动架构的影响。

### 1.4 能够设计

能够设计工业级 EXTI 驱动，满足：

- **中断处理路径短、确定性强、可测试、可追踪**。
- 支持去抖、事件丢弃策略、队列溢出检测和故障诊断。
- 支持多路输入统一抽象。
- 支持裸机、FreeRTOS、低功耗和安全故障输入场景。
- 能够明确判定 EXTI 是否适合某一类信号，并在不适合时切换到定时器捕获、DMA 或专用外设。

---

# 2. 前置要求

## 2.1 知识要求

|类别|必备知识|
|---|---|
|C 语言|指针、位操作、结构体、`volatile`、内存映射寄存器|
|MCU 架构|Cortex-M 异常模型、向量表、MSP/PSP、优先级|
|GPIO|输入模式、上拉/下拉、推挽/开漏、电平兼容性|
|中断|IRQ、ISR、NVIC、优先级、抢占与响应延迟|
|时钟|总线时钟、外设时钟使能、寄存器访问时序|
|RTOS|任务、ISR 安全 API、队列、信号量、任务通知|
|硬件基础|开关抖动、信号完整性、上拉电阻、EMI、过压保护|

## 2.2 技能要求

- 能够阅读目标芯片参考手册中的 EXTI、GPIO、SYSCFG/AFIO 和 NVIC 章节。
- 能够使用调试器查看寄存器、挂起标志和当前执行上下文。
- 能够使用逻辑分析仪或示波器观测输入波形。
- 能够修改启动文件和中断向量表。
- 能够编译、烧录并定位 HardFault、IRQ 未进入、IRQ 反复进入等问题。
- 能够编写不依赖 HAL 的寄存器级初始化代码。

---

# 3. 技术概述

## 3.1 EXTI 的定义

EXTI，即 **External Interrupt/Event Controller，外部中断/事件控制器**，用于将以下信号转换为 MCU 内部中断或事件：

1. GPIO 外部引脚输入；
2. 内部外设事件；
3. RTC、PVD、比较器、低功耗唤醒等系统信号；
4. 软件触发源。

EXTI 本身通常不直接决定 GPIO 来自哪个端口，而是完成：

- 边沿检测；
- 中断屏蔽；
- 事件屏蔽；
- 挂起状态记录；
- 软件触发；
- 部分系列中的上升沿/下降沿独立屏蔽；
- 部分系列中的数字滤波、锁存或扩展路由。

## 3.2 典型信号路径

```
外部电气信号
    │
    ▼
GPIO 输入采样器
    │
    ▼
SYSCFG/AFIO 端口映射
    │
    ▼
EXTI Line 0~N
    │
    ├── 上升沿检测
    ├── 下降沿检测
    ├── 软件触发
    │
    ├── Pending Register
    │
    ├── Interrupt Mask ─────► NVIC ─────► Cortex-M ISR
    │
    └── Event Mask ──────────► Event Fabric / WFE
```

## 3.3 中断与事件的区别

|机制|进入 ISR|适用场景|
|---|---|---|
|EXTI 中断|是|需要执行软件处理逻辑|
|EXTI 事件|否|唤醒 `WFE`、触发内部事件链路|
|软件触发|可以|自测、软件注入、统一事件路径|
|低功耗唤醒|通常通过 EXTI 路径|按键唤醒、RTC 唤醒、系统唤醒|

**关键结论：**

- 需要读取状态、记录时间、投递任务时使用中断。
- 只需要唤醒 CPU 或配合事件机制时，事件可能比中断更低开销。
- 事件不等于中断，不能在事件模式下期待自动执行 ISR。

## 3.4 主流实现分支

### 按触发源分类

1. GPIO 外部线路；
2. 内部外设线路；
3. 软件触发线路；
4. 低功耗唤醒线路。

### 按触发方式分类

1. 上升沿；
2. 下降沿；
3. 双边沿；
4. 电平触发——传统 STM32 EXTI 通常不是持续电平触发，而是边沿锁存。

### 按软件架构分类

1. 直接 ISR 处理；
2. ISR + 环形缓冲区；
3. ISR + RTOS 任务通知；
4. EXTI + 定时器延迟确认；
5. EXTI + 硬件定时器捕获/DMA。

---

# 4. 核心特性横向对比

## 4.1 GPIO 外部中断与其他采集方式

|维度|EXTI 中断|定时器输入捕获|定时器外部时钟/计数|DMA 采样 GPIO|轮询|
|---|---|---|---|---|---|
|触发粒度|边沿事件|边沿+时间戳|边沿计数|周期采样|软件周期|
|CPU 占用|低到中|低|极低|极低|中到高|
|响应延迟|低|低|不适合即时处理|与 DMA 周期相关|至少一个轮询周期|
|高频信号能力|有限|很强|很强|很强|弱|
|时间测量能力|需软件读取时间|硬件时间戳|计数为主|可离线计算|较差|
|抖动|受中断延迟影响|硬件捕获，较低|极低|采样量化误差|较大|
|适合按键|是，需去抖|通常过度设计|否|一般不必要|可行但功耗较高|
|适合编码器|低速可用|推荐|可辅助|特定场景|不推荐|
|适合故障输入|推荐|视需求|不适合|不适合快速故障||
|适合窄脉冲|可能丢失|推荐|推荐|视采样率|容易丢失|

## 4.2 触发方式对比

|触发方式|优点|缺点|典型场景|
|---|---|---|---|
|上升沿|语义清晰，误触发少|不能直接响应下降沿|脉冲有效开始|
|下降沿|常用于低有效信号|不能响应释放或恢复|故障拉低、按键按下|
|双边沿|同时获取变化和恢复|事件量翻倍，软件复杂度高|编码器、状态边沿监测|
|软件触发|便于测试和注入|不代表真实引脚变化|自测、模拟故障路径|

## 4.3 ISR 处理模式对比

|模式|ISR 工作量|实时性|可扩展性|风险|
|---|---|---|---|---|
|ISR 直接执行业务|高|初期较好|差|阻塞、重入、优先级问题|
|ISR 只记录标志|极低|高|中|多事件可能覆盖|
|ISR 写环形队列|低|高|高|队列溢出需处理|
|ISR 发送任务通知|极低|高|高|事件计数和数据传输能力有限|
|ISR 发送消息队列|中|高|高|队列操作有固定开销|
|ISR + 定时器去抖|低|高|高|需要管理定时器生命周期|

**生产级推荐：**

- 单一状态事件：ISR 设置标志或任务通知。
- 高频脉冲：ISR 记录时间戳或使用输入捕获。
- 多路事件：ISR 写入带溢出统计的环形队列。
- 按键：EXTI 只启动去抖流程，不在 ISR 中执行完整按键逻辑。

---

# 5. 底层原理与功能特性深度解析

## 5.1 GPIO 输入与 EXTI 线路映射

在多数 STM32 中，EXTI 线路编号通常与 GPIO pin 编号对应：

```
PA0、PB0、PC0 ... → EXTI0
PA1、PB1、PC1 ... → EXTI1
...
PA15、PB15、PC15 → EXTI15
```

但同一条 EXTI line 在同一时刻通常只能映射到一个端口。例如：

```
PA3 ─┐
PB3 ─┼── EXTI3
PC3 ─┘
```

不能同时将 PA3 和 PB3 都作为传统 EXTI3 的独立 GPIO 中断源。

### STM32F1 常见配置方式

STM32F1 通常通过 AFIO 的 EXTICR 进行端口映射：

```
AFIO->EXTICR[0] &= ~(0x0FU << 12);
AFIO->EXTICR[0] |=  (0x00U << 12);  /* EXTI3 -> PA3 */
```

### STM32F4/G4/H7 常见配置方式

通常通过 SYSCFG_EXTICR：

```
SYSCFG->EXTICR[0] &= ~(0x0FU << 12);
SYSCFG->EXTICR[0] |=  (0x00U << 12);  /* EXTI3 -> PA3 */
```

### 工程注意事项

- 必须先打开 GPIO 时钟。
- 必须先打开 AFIO/SYSCFG 时钟。
- 修改 EXTICR 前应确认目标线路没有被其他模块使用。
- 映射关系应在板级资源表中统一管理，不应散落在多个驱动文件中。

---

## 5.2 边沿检测逻辑

典型 EXTI 逻辑可以抽象为：

```
edge_event =
    (rising_enabled  && previous == 0 && current == 1)
 || (falling_enabled && previous == 1 && current == 0);

if (edge_event) {
    pending = 1;
}

if (pending && interrupt_mask) {
    request_irq_to_nvic = 1;
}
```

注意：实际硬件内部可能存在同步器、采样时钟和系列特定滤波逻辑，因此不能将 GPIO 输入变化到 ISR 的时间简单等同于一个固定时钟周期。

### 边沿配置

```
EXTI->RTSR |=  (1U << line);  /* 上升沿 */
EXTI->FTSR |=  (1U << line);  /* 下降沿 */
```

部分新系列寄存器名称可能变为：

```
EXTI->RTSR1
EXTI->FTSR1
EXTI->RPR1
EXTI->FPR1
```

必须以目标芯片头文件为准。

---

## 5.3 Pending 标志与中断屏蔽

EXTI 中存在两个容易混淆的状态：

1. **Pending：硬件已经检测到事件**
2. **Interrupt Mask：是否允许该事件向 NVIC 输出中断请求**

因此：

```
输入边沿发生
    ↓
Pending 置位
    ↓
若 IMR 允许
    ↓
NVIC 收到 IRQ 请求
```

如果 IMR 被关闭，事件仍可能在 pending 中等待；重新打开 IMR 后可能立即进入中断。

### 典型清除方式

传统 STM32 常使用“写 1 清除”：

```
EXTI->PR = (1U << line);
```

新系列可能使用：

```
EXTI->RPR1 = (1U << line);  /* 清除上升沿 pending */
EXTI->FPR1 = (1U << line);  /* 清除下降沿 pending */
```

**不要用读-改-写方式清除写 1 清零寄存器：**

```
/* 错误示例 */
EXTI->PR |= (1U << line);
```

原因是：

- 该寄存器通常是 W1C；
- 读出的其他 pending 位可能为 1；
- 再写回时可能把其他线路的 pending 一并清除。

正确方式：

```
EXTI->PR = (1U << line);
```

或者使用芯片提供的专用清除寄存器。

---

## 5.4 NVIC 分组与共享 IRQ

EXTI 线路不一定一条线路对应一个 IRQ：

```
EXTI0      → EXTI0_IRQn
EXTI1      → EXTI1_IRQn
EXTI2      → EXTI2_IRQn
EXTI3      → EXTI3_IRQn
EXTI4      → EXTI4_IRQn
EXTI5~9    → EXTI9_5_IRQn
EXTI10~15  → EXTI15_10_IRQn
```

因此共享 IRQ 中必须逐位判断：

```
void EXTI9_5_IRQHandler(void)
{
    uint32_t pending = EXTI->PR;

    if ((pending & (1U << 5)) != 0U) {
        EXTI->PR = (1U << 5);
        exti_line5_isr();
    }

    if ((pending & (1U << 7)) != 0U) {
        EXTI->PR = (1U << 7);
        exti_line7_isr();
    }
}
```

### 共享 IRQ 的处理原则

- 先读取一次 pending 快照。
- 只处理当前快照中确实置位的线路。
- 每条线路独立清除。
- 不要假设一次 IRQ 只对应一条线路。
- 对高优先级线路应避免被低优先级线路的长处理阻塞。

---

## 5.5 裸机寄存器级初始化示例

以下代码以 STM32F4 风格寄存器为示例，将 **PA0 配置为下降沿 EXTI0**。

```
#include "stm32f4xx.h"
#include <stdint.h>
#include <stdbool.h>

#define EXTI_LINE0_MASK    (1UL << 0)

static void exti0_gpio_init(void)
{
    /* 1. 打开 GPIOA 和 SYSCFG 时钟 */
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;

    /*
     * 2. PA0 配置为输入
     * MODER = 00: input
     */
    GPIOA->MODER &= ~(3UL << (0U * 2U));

    /*
     * 3. 上拉输入
     * 根据外部电路选择上拉、下拉或无上下拉
     */
    GPIOA->PUPDR &= ~(3UL << (0U * 2U));
    GPIOA->PUPDR |=  (1UL << (0U * 2U)); /* 01: pull-up */

    /*
     * 4. EXTI0 映射到 PA0
     * EXTICR[0] 的低 4 位控制 EXTI0
     * 0000 通常表示 GPIOA
     */
    SYSCFG->EXTICR[0] &= ~(0x0FUL << 0U);

    /*
     * 5. 先屏蔽线路，避免配置中间状态产生伪中断
     */
    EXTI->IMR &= ~EXTI_LINE0_MASK;

    /*
     * 6. 配置下降沿，关闭上升沿
     */
    EXTI->RTSR &= ~EXTI_LINE0_MASK;
    EXTI->FTSR |=  EXTI_LINE0_MASK;

    /*
     * 7. 清除历史 pending
     * 采用写 1 清除
     */
    EXTI->PR = EXTI_LINE0_MASK;

    /*
     * 8. 配置 NVIC
     * 优先级数值越小，抢占优先级越高。
     * 具体优先级位数由 SCB->AIRCR 和芯片实现决定。
     */
    NVIC_SetPriority(EXTI0_IRQn, 6U);
    NVIC_ClearPendingIRQ(EXTI0_IRQn);
    NVIC_EnableIRQ(EXTI0_IRQn);

    /*
     * 9. 最后打开 EXTI 中断屏蔽
     */
    EXTI->IMR |= EXTI_LINE0_MASK;
}
```

对应 ISR：

```
volatile uint32_t g_exti0_event_count;
volatile uint32_t g_exti0_last_tick;

void EXTI0_IRQHandler(void)
{
    /*
     * 仅处理 EXTI0 的 pending。
     * 不要无条件进入业务逻辑。
     */
    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        /*
         * 先清 pending，再执行后续逻辑。
         * 对于允许快速重复触发的线路，先清除可降低重复进入风险。
         */
        EXTI->PR = EXTI_LINE0_MASK;

        g_exti0_event_count++;
        g_exti0_last_tick = SysTick->VAL;

        /*
         * ISR 内不执行：
         * - printf
         * - malloc/free
         * - 阻塞式 I/O
         * - 长时间循环
         * - 复杂协议解析
         */
    }
}
```

---

## 5.6 ISR 中的时间戳记录

如果系统时钟为：

```
f_cpu = 168 MHz
```

则一个 CPU 周期约为：

```
T_cpu = 1 / 168 MHz ≈ 5.95 ns
```

可以使用通用定时器自由运行计数器记录边沿时间：

```
static inline uint32_t timer_timestamp(void)
{
    return TIM2->CNT;
}

volatile uint32_t g_edge_timestamp;

void EXTI0_IRQHandler(void)
{
    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        uint32_t timestamp = timer_timestamp();

        EXTI->PR = EXTI_LINE0_MASK;

        g_edge_timestamp = timestamp;
    }
}
```

但需要注意：

- 时间戳记录的是 ISR 读取时刻，存在中断延迟；
- 若要求精确测量边沿时刻，应使用 **TIM 输入捕获**；
- EXTI 更适合“发生了事件”，不适合作为高精度时间测量外设。

---

## 5.7 中断安全事件队列

对于多次事件不能覆盖的场景，可以在 ISR 中写入无锁单生产者环形缓冲区。

```
#include <stdint.h>
#include <stdbool.h>

#define EXTI_EVENT_QUEUE_SIZE  32U

typedef struct {
    uint8_t  line;
    uint8_t  level;
    uint16_t reserved;
    uint32_t timestamp;
} exti_event_t;

typedef struct {
    volatile uint32_t write_index;
    volatile uint32_t read_index;
    exti_event_t buffer[EXTI_EVENT_QUEUE_SIZE];
    volatile uint32_t overflow_count;
} exti_event_queue_t;

static exti_event_queue_t g_exti_queue;

static bool exti_queue_push_from_isr(uint8_t line,
                                     uint8_t level,
                                     uint32_t timestamp)
{
    uint32_t write_index = g_exti_queue.write_index;
    uint32_t next_index =
        (write_index + 1U) % EXTI_EVENT_QUEUE_SIZE;

    /*
     * 单生产者/单消费者模型下：
     * ISR 只修改 write_index，任务只修改 read_index。
     */
    if (next_index == g_exti_queue.read_index) {
        g_exti_queue.overflow_count++;
        return false;
    }

    g_exti_queue.buffer[write_index].line = line;
    g_exti_queue.buffer[write_index].level = level;
    g_exti_queue.buffer[write_index].timestamp = timestamp;

    /*
     * 数据写入后再发布 write_index。
     * 编译器屏障避免编译器重排。
     */
    __DMB();
    g_exti_queue.write_index = next_index;

    return true;
}

static bool exti_queue_pop(exti_event_t *event)
{
    uint32_t read_index;
    uint32_t write_index;

    if (event == NULL) {
        return false;
    }

    read_index = g_exti_queue.read_index;
    write_index = g_exti_queue.write_index;

    if (read_index == write_index) {
        return false;
    }

    *event = g_exti_queue.buffer[read_index];

    __DMB();
    g_exti_queue.read_index =
        (read_index + 1U) % EXTI_EVENT_QUEUE_SIZE;

    return true;
}
```

对于 Cortex-M：

- 单核、天然对齐的 32 位读写通常具有原子性；
- 但“数据写入后更新索引”的发布顺序仍需考虑编译器和内存访问顺序；
- 若 ISR 和任务共享复杂结构，必须使用合适的内存屏障或临界区；
- `volatile` 只保证访问不被优化掉，不等于线程安全。

---

## 5.8 RTOS 下使用任务通知

以 FreeRTOS 为例，EXTI ISR 不直接执行业务，而是通知任务。

```
#include "FreeRTOS.h"
#include "task.h"

static TaskHandle_t g_key_task_handle = NULL;

void EXTI0_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        EXTI->PR = EXTI_LINE0_MASK;

        vTaskNotifyGiveFromISR(
            g_key_task_handle,
            &higher_priority_task_woken
        );

        portYIELD_FROM_ISR(higher_priority_task_woken);
    }
}
```

任务侧：

```
static void key_task(void *argument)
{
    (void)argument;

    for (;;) {
        /*
         * 阻塞等待事件，不占用 CPU
         */
        uint32_t count = ulTaskNotifyTake(
            pdTRUE,              /* 退出时清零通知计数 */
            portMAX_DELAY
        );

        if (count > 0U) {
            /*
             * 这里执行按键状态确认、业务分发等复杂逻辑
             */
        }
    }
}
```

### 任务通知适用条件

- 只关心“发生了事件”或“事件计数”；
- 不需要携带大量事件数据；
- ISR 只对应一个任务；
- 希望获得比队列更低的开销。

---

## 5.9 按键去抖：EXTI 不等于去抖

机械按键在一次按压过程中可能产生如下信号：

```
理想信号：  ─────┐
                 └────────

实际信号：  ─────┐_┌_┐__┌──
                 └────────
```

抖动持续时间可能为：

- 普通按键：**1~20 ms**
- 老化、污染、低质量按键：可能超过 **30 ms**

如果直接使用下降沿 EXTI，可能在一次按压中进入多次 ISR。

### 推荐方案：EXTI 触发 + 定时器延迟确认

```
typedef enum {
    KEY_STATE_IDLE = 0,
    KEY_STATE_DEBOUNCE
} key_state_t;

static volatile key_state_t g_key_state;
static volatile uint32_t g_key_event_pending;

void EXTI0_IRQHandler(void)
{
    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        EXTI->PR = EXTI_LINE0_MASK;

        if (g_key_state == KEY_STATE_IDLE) {
            g_key_state = KEY_STATE_DEBOUNCE;
            g_key_event_pending = 1U;

            /*
             * 启动一次性定时器，例如 10 ms 后触发确认。
             * 禁止在 ISR 中忙等 10 ms。
             */
            key_debounce_timer_start(10U);
        }
    }
}

void key_debounce_timer_callback(void)
{
    bool active = ((GPIOA->IDR & (1U << 0U)) == 0U);

    if (g_key_state == KEY_STATE_DEBOUNCE) {
        if (active) {
            key_event_post(KEY_EVENT_PRESSED);
        } else {
            key_event_post(KEY_EVENT_RELEASED);
        }

        g_key_state = KEY_STATE_IDLE;
        g_key_event_pending = 0U;
    }
}
```

### 更稳健的状态机方案

对需要识别按下、释放、长按、连击的按键，应使用：

```
IDLE
  │ 检测到下降沿
  ▼
DEBOUNCE_PRESS
  │ 10 ms 后采样有效
  ├── 无效 → IDLE
  └── 有效 → PRESSED
                  │
                  ├── 持续时间达到长按阈值 → LONG_PRESS
                  └── 检测到释放 → DEBOUNCE_RELEASE
```

---

## 5.10 软件触发与自测

部分 STM32 支持通过软件触发寄存器产生 EXTI 事件：

```
EXTI->SWIER |= EXTI_LINE0_MASK;
```

软件触发可以用于：

- 验证 NVIC 和向量表配置；
- 验证事件队列；
- 对故障处理路径进行注入测试；
- 启动统一的异步处理流程。

但软件触发不一定会改变 GPIO 的实际电平，因此不能用它替代真实输入电气测试。

---

## 5.11 低功耗唤醒

EXTI 通常参与以下低功耗流程：

```
配置 GPIO/EXTI
    ↓
清除历史 pending
    ↓
配置唤醒源
    ↓
进入 STOP/STANDBY
    ↓
外部边沿到来
    ↓
EXTI 置 pending
    ↓
唤醒系统
    ↓
重新配置系统时钟
    ↓
处理唤醒原因
```

必须区分：

- **唤醒成功**
- **唤醒原因正确**

进入低功耗前如果没有清除历史 pending，系统可能在刚进入低功耗后立即被“旧事件”唤醒。

---

# 6. 性能量化分析

## 6.1 中断响应时间构成

EXTI 从边沿发生到 ISR 执行，延迟通常包含：

```
T_response =
    T_gpio_sync
  + T_exti_detect
  + T_nvic_arbitration
  + T_context_entry
  + T_higher_priority_block
```

Cortex-M 异常进入时间在理想条件下大约为：

- Cortex-M3/M4：约 **12 个 CPU 周期**
- Cortex-M7：取决于缓存、总线和异常配置
- 存在高优先级 ISR、关闭中断、Flash 等待周期时会明显增加

以 STM32F407、168 MHz 为例：

```
12 cycles / 168 MHz ≈ 71.4 ns
```

但这是理想异常入口开销，不包含：

- GPIO 输入同步；
- Flash 访问等待；
- 当前高优先级 ISR；
- 总线竞争；
- ISR 首次取指；
- RTOS 临界区。

工程中更有价值的是实测：

```
T_irq = GPIO_edge_time_to_ISR_toggle_time
```

可以使用：

```
void EXTI0_IRQHandler(void)
{
    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        TEST_GPIO->BSRR = TEST_PIN; /* ISR 入口附近拉高 */
        EXTI->PR = EXTI_LINE0_MASK;
        TEST_GPIO->BSRR = ((uint32_t)TEST_PIN << 16U);
    }
}
```

用示波器测量外部信号到测试 GPIO 翻转之间的时间。

## 6.2 ISR 时间预算

假设输入事件最大频率为：

```
f_event = 2 kHz
```

每个事件允许的 CPU 时间占比为：

```
U_isr = f_event × T_isr
```

若 ISR 执行时间为 2 μs：

```
U_isr = 2000 × 2 μs = 0.004 = 0.4%
```

若错误地在 ISR 中执行 200 μs 的日志、协议解析：

```
U_isr = 2000 × 200 μs = 0.4 = 40%
```

这还没有计算其他中断和任务调度开销。

### 推荐预算

|场景|建议 ISR 时长|
|---|---|
|普通按键|小于 5 μs|
|电源故障输入|小于 2 μs|
|高频脉冲|小于 1~3 μs|
|RTOS 任务通知|通常小于 5 μs|
|复杂业务处理|不应放在 ISR|

具体数值应通过目标平台示波器和 DWT 周期计数器测得，而不是仅依赖理论值。

## 6.3 内存开销

### 直接标志方式

```
volatile uint32_t event_flag;
```

静态内存：

```
4 bytes
```

但多个事件可能相互覆盖。

### 事件队列方式

如果：

```
事件大小 = 8 bytes
队列长度 = 32
索引和统计 = 16 bytes
```

则：

```
RAM ≈ 8 × 32 + 16 = 272 bytes
```

### RTOS 队列方式

FreeRTOS 队列的实际开销包含：

```
队列控制块 + 队列存储区 + 对齐填充
```

具体值依赖端口和配置，不能只按消息大小估算。对于简单二值事件，任务通知通常比队列更省 RAM 和 CPU。

## 6.4 高频输入吞吐能力

若每个边沿触发一次 ISR，最大理论处理能力近似为：

```
f_max ≈ 1 / T_isr
```

例如：

```
T_isr = 3 μs
f_max ≈ 333 k events/s
```

但这只是单独占用 CPU 的理论上限。若系统允许 EXTI 占用不超过 10% CPU：

```
f_practical ≈ 0.1 / 3 μs ≈ 33.3 k events/s
```

对于编码器双边沿：

```
f_edge = 4 × f_mechanical
```

如果机械转速为 2000 转/分钟，编码器每转 1024 线，四倍频：

```
f_edge = 2000 / 60 × 1024 × 4
       ≈ 136.5 kHz
```

此时不应使用普通 EXTI 做完整软件解码，应优先使用：

- 定时器编码器接口；
- 定时器输入捕获；
- 硬件滤波；
- DMA。

## 6.5 优化手段及收益

|优化手段|原始问题|优化收益|
|---|---|---|
|ISR 先清 pending|重复进入、嵌套风险|降低中断风暴|
|ISR 只写事件|ISR 过长|降低响应抖动|
|使用任务通知|队列开销过大|降低 RAM 和调度开销|
|使用定时器捕获|EXTI 时间戳误差大|提高边沿测量精度|
|硬件上拉/施密特输入|噪声和慢边沿|减少误触发|
|硬件 RC + 软件去抖|机械抖动|提高按键稳定性|
|合并共享 IRQ 读取快照|多次访问寄存器|降低总线访问次数|
|DWT/示波器测量|只凭经验优化|形成可验证数据|

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
输入信号是否需要检测边沿？
├── 否
│   └── 是否需要持续读取电平？
│       ├── 是 → GPIO 轮询/定时采样
│       └── 否 → 重新评估接口需求
│
└── 是
    └── 边沿频率是否低于约 1 kHz？
        ├── 否
        │   └── 是否需要精确时间戳？
        │       ├── 是 → 定时器输入捕获/DMA
        │       └── 否 → 定时器计数/DMA 采样
        │
        └── 是
            └── 是否为机械按键？
                ├── 是 → EXTI + 软件/硬件去抖
                └── 否
                    └── 是否需要进入任务处理？
                        ├── 是 → EXTI ISR + 任务通知/事件队列
                        └── 否 → EXTI ISR 直接执行短处理
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|用户按键|EXTI + 定时器去抖|响应快，软件可扩展|
|电源故障输入|EXTI 下降沿 + 立即锁存|故障响应优先级高|
|门磁/限位开关|EXTI + 状态确认|低频，强调可靠性|
|低功耗唤醒|EXTI 事件/中断|硬件支持唤醒|
|霍尔转速低速检测|EXTI + 时间戳|低频且需要周期计算|
|高速编码器|定时器编码器模式|EXTI 中断量过大|
|PWM 脉宽测量|定时器输入捕获|硬件记录边沿时间|
|窄脉冲捕获|输入捕获/DMA|避免 CPU 响应不及时丢失|
|外部中断线数量超过限制|GPIO 扩展器/专用中断控制器|EXTI 线路有限|
|强噪声工业输入|隔离 + 硬件滤波 + EXTI|单靠软件不能解决电气问题|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：中断只做“确认、记录、投递”

ISR 内只做以下事情：

- 判断 pending；
- 清除 pending；
- 读取必要的硬件状态；
- 记录时间戳；
- 投递事件；
- 设置极少量状态。

不应在 ISR 中做：

- `printf`；
- 动态内存分配；
- 阻塞等待；
- Flash 擦写；
- 复杂协议解析；
- 长循环；
- 访问非 ISR 安全 API。

### 原则二：初始化时先屏蔽，完成配置后再打开

推荐顺序：

```
打开时钟
  ↓
配置 GPIO
  ↓
配置线路映射
  ↓
关闭 EXTI 中断
  ↓
配置触发边沿
  ↓
清 pending
  ↓
配置 NVIC
  ↓
打开 EXTI 中断
```

### 原则三：明确事件语义

不要只定义：

```
EVENT_EXTI0
```

应该定义：

```
KEY_POWER_PRESSED
DOOR_OPENED
MOTOR_FAULT_ASSERTED
ENCODER_EDGE
```

底层 EXTI 事件应转换为具有业务语义的事件。

### 原则四：必须统计异常

建议统计：

```
typedef struct {
    uint32_t irq_count;
    uint32_t queue_overflow;
    uint32_t debounce_reject;
    uint32_t unexpected_pending;
    uint32_t maximum_latency_cycles;
} exti_diag_t;
```

工业现场出现偶发故障时，没有计数器往往无法还原问题。

## 8.2 选型决策矩阵

|指标|EXTI|定时器捕获|DMA 采样|轮询|
|---|---|---|---|---|
|响应速度|5|5|3|1|
|高频能力|2|5|5|1|
|时间精度|2|5|4|1|
|软件复杂度|3|3|4|2|
|低功耗适配|5|3|1|1|
|按键适配|5|2|1|3|
|资源占用|4|3|2|4|

评分越高越适合。

## 8.3 工业级编码规范

推荐：

```
#define EXTI_LINE_MASK(line)       (1UL << (line))
#define EXTI_PENDING_IS_SET(mask)  ((EXTI->PR & (mask)) != 0U)
```

避免：

```
if (EXTI->PR & 1 << line) {
    ...
}
```

原因：

- 运算符优先级不够直观；
- 线路范围和类型不明确；
- 不利于静态检查。

建议：

- 所有线路号使用 `uint8_t` 或枚举；
- 所有寄存器位掩码使用无符号常量；
- ISR 函数命名与启动文件保持一致；
- 不在驱动层直接暴露业务变量；
- 把芯片系列差异封装在 `bsp_exti_stm32xxx.c` 中；
- 用单元测试验证事件队列、去抖状态机和溢出处理。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：忘记打开 SYSCFG/AFIO 时钟

### 错误代码

```
RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;

/* 直接访问 SYSCFG->EXTICR */
SYSCFG->EXTICR[0] = 0;
```

### 根因

SYSCFG 外设时钟未打开，EXTICR 写入可能无效。

### 正确实现

```
RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;

(void)RCC->APB2ENR; /* 必要时插入读回，确保时钟写入完成 */

SYSCFG->EXTICR[0] &= ~(0x0FUL << 0U);
```

### 风险影响

- GPIO 正常，但 EXTI 永远不进；
- 问题容易被误判为 NVIC 配置错误。

---

## 9.2 错误二：使用读-改-写清除 W1C pending

### 错误代码

```
EXTI->PR |= (1U << 3);
```

### 根因

W1C 寄存器写入 1 表示清除。读出的其他 pending 位为 1，再写回会误清其他事件。

### 正确实现

```
EXTI->PR = (1U << 3);
```

### 风险影响

- 丢失其他 EXTI 线路事件；
- 共享 IRQ 下出现偶发数据丢失。

---

## 9.3 错误三：ISR 中不判断 pending

### 错误代码

```
void EXTI9_5_IRQHandler(void)
{
    EXTI->PR = (1U << 5);
    key_event_process();
}
```

### 根因

EXTI9_5 是共享中断，IRQ 进入不代表一定是 EXTI5 触发。

### 正确实现

```
void EXTI9_5_IRQHandler(void)
{
    uint32_t pending = EXTI->PR;

    if ((pending & (1U << 5)) != 0U) {
        EXTI->PR = (1U << 5);
        key_event_post_from_isr();
    }
}
```

### 风险影响

- 错误执行业务逻辑；
- 可能误报按键、故障或通信事件。

---

## 9.4 错误四：按键 ISR 中直接执行完整业务逻辑

### 错误代码

```
void EXTI0_IRQHandler(void)
{
    if ((EXTI->PR & 1U) != 0U) {
        EXTI->PR = 1U;

        printf("key pressed\r\n");
        motor_stop();
        flash_save_config();
        protocol_send_status();
    }
}
```

### 根因

将异步硬件事件和复杂业务处理耦合在 ISR 中。

### 正确实现

```
void EXTI0_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        EXTI->PR = EXTI_LINE0_MASK;

        xTaskNotifyFromISR(
            g_key_task_handle,
            KEY_EVENT_EDGE,
            eSetBits,
            &higher_priority_task_woken
        );

        portYIELD_FROM_ISR(higher_priority_task_woken);
    }
}
```

### 风险影响

- 阻塞其他中断；
- 增大系统实时性抖动；
- 可能触发看门狗；
- Flash 操作期间引入不可预测延迟。

---

## 9.5 错误五：没有清除历史 pending

### 错误代码

```
void exti_init(void)
{
    EXTI->IMR |= EXTI_LINE0_MASK;
    NVIC_EnableIRQ(EXTI0_IRQn);
}
```

### 根因

配置过程中已经产生了 pending，打开 NVIC 后立即进入 ISR。

### 正确实现

```
void exti_init(void)
{
    EXTI->IMR &= ~EXTI_LINE0_MASK;

    /* 配置 GPIO、映射、边沿 */

    EXTI->PR = EXTI_LINE0_MASK;
    NVIC_ClearPendingIRQ(EXTI0_IRQn);

    NVIC_EnableIRQ(EXTI0_IRQn);
    EXTI->IMR |= EXTI_LINE0_MASK;
}
```

### 风险影响

- 上电误报；
- 低功耗进入后立即唤醒；
- 状态机初始状态被破坏。

---

## 9.6 错误六：用 EXTI 处理过高频率输入

### 错误代码

```
void EXTI0_IRQHandler(void)
{
    if ((EXTI->PR & EXTI_LINE0_MASK) != 0U) {
        EXTI->PR = EXTI_LINE0_MASK;
        encoder_position++;
    }
}
```

### 根因

将高频编码器输入当成低频异步事件处理。

### 正确实现

- 使用定时器编码器接口；
- 或使用输入捕获记录边沿；
- 或使用 DMA 采样并批量解析。

### 风险影响

- 丢脉冲；
- CPU 占用过高；
- 位置累计错误；
- 电机控制周期被打断。

---

# 10. 多机制组合使用方案

## 10.1 EXTI + 定时器去抖 + RTOS 任务通知

### 架构

```
GPIO 按键
   │
   ▼
EXTI ISR
   │
   ├── 清 pending
   ├── 记录边沿
   └── 启动一次性定时器
          │
          ▼
    定时器回调/软件定时器
          │
          ├── 重新采样 GPIO
          ├── 判断稳定状态
          └── 通知 KeyTask
                         │
                         ▼
                    业务状态机
```

### 框架代码

```
typedef enum {
    KEY_EVENT_PRESSED = 1,
    KEY_EVENT_RELEASED,
    KEY_EVENT_LONG_PRESS
} key_event_t;

typedef struct {
    uint8_t stable_level;
    uint8_t last_level;
    uint8_t reserved[2];
    uint32_t press_tick;
} key_context_t;

static key_context_t g_key_ctx;

void key_exti_isr(void)
{
    uint32_t now = system_tick_get();

    /*
     * 清除 pending 后只记录最小信息。
     */
    EXTI->PR = EXTI_LINE0_MASK;

    g_key_ctx.last_level =
        ((GPIOA->IDR & (1U << 0U)) != 0U) ? 1U : 0U;

    key_debounce_timer_start(now + 10U);
}

void key_debounce_expired(void)
{
    uint8_t level =
        ((GPIOA->IDR & (1U << 0U)) != 0U) ? 1U : 0U;

    if (level == g_key_ctx.last_level) {
        if (level != g_key_ctx.stable_level) {
            g_key_ctx.stable_level = level;

            if (level == 0U) {
                key_event_post(KEY_EVENT_PRESSED);
                g_key_ctx.press_tick = system_tick_get();
            } else {
                key_event_post(KEY_EVENT_RELEASED);
            }
        }
    }
}
```

## 10.2 EXTI + 环形队列 + 时间戳

适用于：

- 多路低频脉冲；
- 故障边沿记录；
- 需要保留事件顺序；
- 需要离线计算周期或响应时间。

```
typedef struct {
    uint8_t  source;
    uint8_t  edge;
    uint16_t flags;
    uint32_t timestamp;
} input_edge_event_t;

static void input_edge_isr(uint8_t source, uint8_t edge)
{
    input_edge_event_t event;

    event.source = source;
    event.edge = edge;
    event.flags = 0U;
    event.timestamp = TIM2->CNT;

    if (!edge_queue_push_from_isr(&event)) {
        system_fault_set(FAULT_EDGE_QUEUE_OVERFLOW);
    }
}
```

## 10.3 EXTI + 定时器输入捕获

适用于：

- 低频事件需要高精度时间；
- 需要测量脉宽、周期、占空比；
- 外部输入既需要快速通知，又需要硬件时间戳。

架构：

```
输入信号
  ├── 定时器通道 → 硬件捕获 CNT
  └── EXTI       → 软件事件通知
```

不过应确认同一个引脚是否允许同时连接到对应定时器复用功能和 EXTI 路径，以及两者配置是否冲突。

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业控制柜急停输入

### 需求

- 急停信号低有效；
- 正常工作时实时监测；
- 下降沿后立即关闭 PWM 输出；
- 业务任务异步记录故障；
- 必须统计误触发和恢复次数。

### 架构设计

```
急停输入
  ↓
GPIO 硬件滤波/施密特输入
  ↓
EXTI 下降沿
  ↓
高优先级 ISR
  ├── 清 pending
  ├── 关闭 PWM 输出
  ├── 锁存故障寄存器
  └── 通知安全任务
```

### 核心代码

```
void ESTOP_EXTI_IRQHandler(void)
{
    uint32_t pending = EXTI->PR;

    if ((pending & ESTOP_EXTI_MASK) != 0U) {
        /*
         * 先锁存硬件故障状态。
         */
        EXTI->PR = ESTOP_EXTI_MASK;

        /*
         * 对安全相关输出，优先使用硬件刹车输入或定时器 Break。
         * EXTI ISR 关闭 PWM 仅作为软件辅助路径。
         */
        TIM1->BDTR |= TIM_BDTR_MOE; /* 示例：实际安全动作需按芯片设计 */

        safety_fault_latch(SAFETY_FAULT_ESTOP);
        safety_event_notify_from_isr(SAFETY_FAULT_ESTOP);
    }
}
```

### 设计要点

- 对急停、过流、驱动故障，**不能只依赖 EXTI 软件中断**。
- 最佳方案通常是：

```
故障输入 → 定时器 Break/硬件关断 → EXTI 软件记录
```

- 软件 ISR 延迟受中断屏蔽和高优先级任务影响，不满足最高等级安全关断要求。
- 必须考虑输入断线检测、反相逻辑和安全继电器诊断。

---

## 11.2 案例二：门磁和限位开关监测

### 需求

- 8 路低频输入；
- 信号变化后 20 ms 稳定确认；
- 需要识别打开、关闭和异常抖动；
- 不能因为一路输入导致其他路事件丢失。

### 架构设计

```
8 路 GPIO
  ↓
EXTI5~9_5 / EXTI15_10 共享 IRQ
  ↓
读取 pending 快照
  ↓
每路清 pending + 投递线路号
  ↓
事件队列
  ↓
状态机任务
  ↓
20 ms 稳定确认
```

### 核心 ISR

```
void EXTI9_5_IRQHandler(void)
{
    uint32_t pending = EXTI->PR;
    uint32_t active = pending & EXTI->IMR;

    for (uint8_t line = 5U; line <= 9U; line++) {
        uint32_t mask = 1UL << line;

        if ((active & mask) != 0U) {
            uint8_t level;

            EXTI->PR = mask;

            level = ((GPIOB->IDR & mask) != 0U) ? 1U : 0U;

            if (!door_event_queue_push_from_isr(line, level)) {
                g_door_diag.queue_overflow++;
            }
        }
    }
}
```

### 设计要点

- 共享 IRQ 必须扫描所有可能线路。
- 每路应有独立去抖状态机。
- 不要用全局单一 `door_changed` 标志，否则多路同时变化时会覆盖。
- 队列满时必须有明确策略：
    - 丢弃最新事件；
    - 丢弃最旧事件；
    - 锁存故障；
    - 重新读取所有输入状态进行恢复。

---

## 11.3 案例三：低功耗无线传感器按键唤醒

### 需求

- MCU 大部分时间处于 STOP 模式；
- 按键唤醒系统；
- 唤醒后判断按键是否真实按下；
- 需要避免历史 pending 导致假唤醒。

### 架构

```
STOP 模式
  ↓
按键边沿
  ↓
EXTI 唤醒
  ↓
系统时钟恢复
  ↓
清除唤醒标志和 EXTI pending
  ↓
延迟 10 ms 采样
  ↓
确认按键状态
  ↓
执行通信发送
```

### 设计要点

- 进入 STOP 前清除 pending。
- 从 STOP 返回后重新配置系统时钟。
- 不要假设唤醒后系统时钟仍处于运行前状态。
- 需要区分 EXTI 唤醒、RTC 唤醒、低电压复位等原因。
- 若使用 STANDBY，部分系列会经历复位流程，唤醒路径不能按 STOP 处理。

---

# 12. 高频问题深度答疑

## 问题一：为什么 GPIO 输入已经变化，但 EXTI 不进中断？

需要按以下顺序排查：

```
GPIO 时钟是否打开？
  ↓
GPIO 是否配置为输入？
  ↓
输入电平是否真的达到 VIH/VIL？
  ↓
EXTI 线路是否映射到正确端口？
  ↓
RTSR/FTSR 是否正确？
  ↓
IMR 是否打开？
  ↓
pending 是否置位？
  ↓
NVIC 是否使能？
  ↓
IRQHandler 名称是否与启动文件一致？
  ↓
是否被全局关中断或更高优先级 ISR 阻塞？
```

最有效的调试方法不是先看业务代码，而是直接观察：

```
GPIOx->IDR
SYSCFG->EXTICR[n]
EXTI->IMR
EXTI->RTSR / FTSR
EXTI->PR
NVIC->ISER
NVIC->ISPR
```

如果 pending 置位但 ISR 不进，问题集中在 NVIC、向量表、全局中断或异常屏蔽。如果 pending 不置位，问题集中在 GPIO、映射、电气输入和边沿配置。

---

## 问题二：为什么中断会无限进入？

常见根因：

1. pending 没有清除；
2. 使用错误寄存器清除；
3. 清除的线路位不正确；
4. 输入信号持续振荡；
5. ISR 退出前又产生了新边沿；
6. 共享 IRQ 中其他线路 pending 未处理；
7. 触发源存在电气噪声。

应使用示波器确认真实输入波形，并在 ISR 中统计：

```
g_irq_count++;
g_pending_snapshot = EXTI->PR;
```

不要简单地在 ISR 中永久关闭中断掩盖问题，因为这可能把真实故障变成静默丢失。

---

## 问题三：应该先清 pending 还是后清 pending？

通用推荐：

```
读取 pending
  ↓
确认是目标线路
  ↓
尽早清除 pending
  ↓
读取必要状态
  ↓
投递事件
```

先清的优点：

- 缩短 pending 保持时间；
- 减少同一事件重复进入；
- 降低 ISR 长路径中再次触发的影响。

但如果输入信号可能在 ISR 内快速产生连续事件，先清 pending 可能允许新的事件在后续再次置位，这通常是合理行为。若软件必须区分每一个边沿，应使用硬件捕获或队列，不应依赖 pending 位保存多个事件。

---

## 问题四：`volatile` 能否解决 ISR 与任务之间的数据一致性？

不能完全解决。

`volatile` 主要解决：

- 编译器不能删除访问；
- 编译器不能把变量长期缓存到寄存器。

它不能保证：

- 多变量更新的整体原子性；
- 复杂结构体的一致快照；
- 生产者和消费者的发布顺序；
- 多上下文之间的同步。

例如：

```
volatile uint32_t event_count;
volatile uint32_t event_timestamp;
```

任务读取时可能看到新计数和旧时间戳。生产级实现应使用：

- 临界区；
- 原子变量；
- 单生产者单消费者队列；
- 内存屏障；
- RTOS 同步原语。

---

## 问题五：为什么按键必须去抖？硬件 RC 不够吗？

硬件 RC 可以降低高频噪声和抖动，但通常不能完全替代软件去抖：

- 元件容差会改变时间常数；
- 输入阈值存在变化；
- 温度和老化影响开关波形；
- 长线和 EMI 可能重新引入干扰；
- 按键动作语义通常还包含长按、连击和释放。

最佳实践通常是：

```
硬件：限制尖峰、改善边沿、电气保护
软件：确认稳定状态、实现按键语义
```

---

## 问题六：EXTI 可以用于测量外部脉冲频率吗？

可以，但要看频率和精度要求。

### 适合 EXTI 的情况

- 频率较低；
- 只需要粗略统计；
- 不要求每个边沿精确时间；
- 系统 CPU 负载较低。

### 不适合 EXTI 的情况

- 高频连续脉冲；
- 脉宽测量；
- 需要纳秒/微秒级稳定时间戳；
- 不能容忍丢边沿；
- 输入可能产生脉冲密集突发。

此时应改用：

- 定时器输入捕获；
- 定时器外部时钟；
- DMA；
- 专用高速采集外设。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **EXTI 负责边沿检测和事件锁存，GPIO 负责输入采样，NVIC 负责中断分发。**
2. 同一编号 EXTI line 通常只能映射一个 GPIO 端口。
3. ISR 必须判断对应 pending，尤其是共享 IRQ。
4. W1C 寄存器必须使用直接写 1 清除，禁止随意使用 `|=`。
5. 初始化时应先屏蔽中断，配置完成、清除 pending 后再打开。
6. ISR 应遵循“确认、清除、记录、投递”原则。
7. 机械按键必须做去抖，EXTI 本身不提供业务级去抖。
8. 高速输入不应盲目使用 EXTI，应优先考虑定时器捕获、编码器接口或 DMA。
9. 安全关断不能只依赖软件 EXTI，必须优先使用硬件保护路径。
10. `volatile` 不是完整同步机制，事件队列和跨上下文数据需要正确的内存顺序设计。

## 13.2 性能排序

从高性能到低性能，典型排序如下：

```
硬件捕获/DMA
    >
定时器输入捕获
    >
EXTI + 极短 ISR
    >
EXTI + RTOS 事件投递
    >
GPIO 周期轮询
```

但从低功耗和实现简单性看：

```
EXTI 事件/唤醒
    >
EXTI 中断
    >
定时器周期采样
    >
持续轮询
```

## 13.3 通用选型结论

|输入类型|通用推荐|
|---|---|
|按键|EXTI + 10~20 ms 去抖|
|低速状态变化|EXTI + 事件队列|
|故障输入|硬件关断 + EXTI 记录|
|低功耗唤醒|EXTI/事件唤醒|
|低速频率测量|EXTI + 定时器时间戳|
|高频频率测量|定时器输入捕获|
|编码器|定时器编码器模式|
|多路同时事件|EXTI + 环形队列 + 溢出统计|
|窄脉冲|捕获/DMA，不使用普通 EXTI|

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|触发方式|ISR 策略|后续处理|
|---|---|---|---|
|按键按下|下降沿|清 pending、启动去抖|任务状态机|
|按键按下/释放|双边沿|读取输入、投递事件|任务状态机|
|故障拉低|下降沿|立即锁存、通知任务|安全处理|
|故障恢复|上升沿|记录恢复时间|状态机确认|
|低功耗唤醒|按芯片要求|唤醒后识别原因|时钟恢复|
|低速脉冲|上升沿|记录计数/时间戳|频率计算|
|高速脉冲|不推荐 EXTI|硬件捕获|DMA/任务处理|

## 14.2 配置顺序表

|步骤|操作|
|---|---|
|1|打开 GPIO 时钟|
|2|打开 SYSCFG/AFIO 时钟|
|3|配置 GPIO 输入模式|
|4|配置上下拉和电气属性|
|5|配置 EXTI 端口映射|
|6|屏蔽 EXTI 中断|
|7|配置上升沿/下降沿|
|8|清除 pending|
|9|配置 NVIC 优先级|
|10|清除 NVIC pending|
|11|使能 NVIC|
|12|打开 EXTI 中断屏蔽|

## 14.3 ISR 模板

```
void EXTIx_IRQHandler(void)
{
    uint32_t pending = EXTI->PR;

    if ((pending & EXTI_LINE_MASK) != 0U) {
        /*
         * W1C：直接写目标位
         */
        EXTI->PR = EXTI_LINE_MASK;

        /*
         * 读取必要硬件状态
         */
        uint32_t level = GPIOx->IDR & GPIO_PIN_MASK;

        /*
         * 记录或投递事件
         */
        exti_event_post_from_isr(level);
    }
}
```

---

# 15. 学习效果自检

完成本课后，应逐项确认：

## 15.1 配置能力

- [ ]  能解释 GPIO、SYSCFG/AFIO、EXTI、NVIC 的连接关系。
- [ ]  能将指定 GPIO 端口映射到正确 EXTI line。
- [ ]  能配置上升沿、下降沿和双边沿。
- [ ]  能正确处理共享 IRQ。
- [ ]  能识别目标芯片的 pending 清除寄存器。

## 15.2 原理能力

- [ ]  能解释 pending 和 interrupt mask 的区别。
- [ ]  能解释为什么历史 pending 会导致刚开启中断就进入 ISR。
- [ ]  能解释 W1C 寄存器不能使用普通读-改-写。
- [ ]  能说明 EXTI 为什么无法保存多个连续事件。
- [ ]  能解释软件触发和真实 GPIO 边沿的区别。

## 15.3 工程能力

- [ ]  能设计 ISR + 任务通知架构。
- [ ]  能实现带溢出检测的事件环形队列。
- [ ]  能实现按键去抖状态机。
- [ ]  能使用示波器测量外部边沿到 ISR 的延迟。
- [ ]  能判断某个高速输入是否应改用定时器捕获。
- [ ]  能为 EXTI 驱动增加事件计数、溢出计数和异常诊断。

## 15.4 故障定位能力

- [ ]  GPIO 电平正常但 ISR 不进入时，能按链路定位。
- [ ]  能定位中断风暴的根因。
- [ ]  能区分硬件噪声、机械抖动和软件清 pending 错误。
- [ ]  能识别向量表函数名错误导致的默认异常处理。
- [ ]  能判断是 EXTI 丢事件还是下游队列溢出。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：单路按键 EXTI

要求：

- PA0 配置为下降沿 EXTI；
- ISR 中翻转测试 GPIO；
- 使用示波器测量输入到 ISR 的响应延迟；
- 记录最小、最大和平均延迟。

输出指标：

```
min_latency
max_latency
average_latency
jitter = max_latency - min_latency
```

### 任务二：按键去抖

要求：

- EXTI 只负责启动去抖；
- 10 ms 后重新采样；
- 实现按下、释放、长按；
- 统计一次按键动作产生的原始边沿数和有效事件数。

### 任务三：共享 IRQ 多路输入

要求：

- 配置 EXTI5、EXTI6、EXTI7；
- 使用共享 IRQ；
- 同时模拟多路边沿；
- 验证不会误处理和丢失线路事件；
- 添加队列溢出告警。

### 任务四：EXTI 与 FreeRTOS

要求：

- ISR 使用任务通知；
- 任务完成状态确认；
- 禁止在 ISR 中调用非 ISR 安全 API；
- 测量通知到任务开始执行的调度延迟。

### 任务五：与定时器捕获对比

要求：

- 同一路脉冲分别接入 EXTI 和 TIM 输入捕获；
- 比较：
    - 响应延迟；
    - 时间戳误差；
    - CPU 占用；
    - 高频丢边沿情况。

## 16.2 性能测试方法

### ISR 延迟测量

```
信号源输出边沿
    ↓
GPIO/EXTI
    ↓
ISR 中翻转测试 GPIO
    ↓
示波器测量两边沿时间差
```

### ISR 执行周期测量

使用 DWT：

```
static inline void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static inline uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}
```

在 ISR 入口和出口记录：

```
uint32_t start = dwt_cycles();

/* ISR core logic */

uint32_t elapsed = dwt_cycles() - start;
```

注意：

- DWT 在部分低功耗模式下可能停止；
- Debug 配置和芯片实现会影响 DWT；
- 高优化等级下应配合汇编或 GPIO 波形验证。

### 压力测试

逐步增加：

```
100 Hz
1 kHz
10 kHz
50 kHz
100 kHz
```

统计：

- IRQ 次数；
- 事件队列入队次数；
- 队列溢出次数；
- 丢边沿数；
- CPU 利用率；
- 其他高优先级中断最大延迟。

## 16.3 进阶学习方向

1. **Cortex-M 异常机制**
    
    - 异常入栈；
    - Tail-chaining；
    - Late-arrival；
    - BASEPRI、PRIMASK、FAULTMASK。
2. **高级中断架构**
    
    - 中断延迟预算；
    - ISR 分层；
    - 中断亲和性；
    - 实时性分析。
3. **定时器输入捕获**
    
    - 硬件时间戳；
    - 数字滤波；
    - 脉宽和周期测量；
    - 捕获溢出处理。
4. **低功耗唤醒**
    
    - STOP/STANDBY；
    - 唤醒源管理；
    - 唤醒标志清除；
    - 时钟恢复。
5. **工业信号完整性**
    
    - RC 滤波；
    - 施密特触发；
    - TVS；
    - 光耦和数字隔离；
    - 接地和屏蔽。
6. **安全相关输入设计**
    
    - 硬件关断；
    - 双通道输入；
    - 断线检测；
    - 故障锁存；
    - IEC 61508/ISO 13849 相关设计方法。

**最终工程结论：EXTI 是低频异步事件的高性价比入口，但它不是通用高速采集器，也不是按键去抖器，更不是安全关断的唯一保障。工业级设计应将 EXTI 定位为“快速事件通知与状态锁存通道”，把复杂业务、去抖、协议解析和高精度时间测量交给更合适的机制。**