
## 1. 学习目标

### 理解

- 理解任务、任务状态、优先级、就绪队列、阻塞队列和调度点的底层关系。
- 理解**抢占式调度**与**同优先级时间片轮转**解决的是两个不同维度的问题。
- 理解中断、临界区、调度器锁定和任务切换之间的约束。

### 掌握

- 掌握 FreeRTOS 任务创建、挂起、恢复、删除、延时及任务通知等管理机制。
- 掌握 `configUSE_PREEMPTION`、`configUSE_TIME_SLICING` 和系统 Tick 对调度行为的影响。
- 掌握任务优先级、周期、WCET、截止期和 CPU 利用率的量化分析方法。

### 精通

- 能够从内核源码分析任务状态迁移、最高优先级选择、时间片轮转和中断退出抢占。
- 能够定位优先级反转、饥饿、Tick 抖动、栈溢出和任务删除竞态。
- 能够通过运行时间统计、Trace 和 GPIO 测量调度延迟。

### 能够设计

- 能够设计满足硬实时约束的多任务系统。
- 能够组合使用固定优先级抢占、同优先级时间片、事件阻塞、优先级继承和无锁通信。
- 能够建立任务设计表、可调度性分析、运行时监控和故障降级机制。

---

## 2. 前置要求

### 知识要求

- Cortex-M 异常模型、NVIC、中断优先级与 PendSV/SysTick。
- C 语言指针、链表、位图、临界区和内存屏障。
- 周期任务、截止期、WCET、抖动和优先级反转。
- FreeRTOS 队列、信号量、互斥量和任务通知基础。

### 技能要求

- 能阅读 FreeRTOS `tasks.c`、`list.c` 和 Cortex-M `port.c/portASM`。
- 能使用逻辑分析仪、DWT Cycle Counter、SystemView 或 Tracealyzer。
- 能根据链接映射文件和高水位统计分析 RAM 与任务栈。
- 能编写可重入驱动和 ISR 到任务的事件传递代码。

---

## 3. 技术概述

### 3.1 核心定义

RTOS 任务是具有独立执行上下文的调度实体，通常包含：

- 任务控制块 TCB。
- 独立栈。
- 当前状态和优先级。
- 就绪、延时或事件等待链表节点。
- 通知值、互斥量持有信息和运行时间统计信息。

任务典型状态：

```
创建
  |
  v
就绪 <-------------------------+
  |                            |
  | 被调度                     | 事件到达/延时到期
  v                            |
运行 ----等待事件/延时----> 阻塞
  |                            ^
  +----被高优先级任务抢占------+
  |
  +----vTaskSuspend()-------> 挂起
  |
  +----vTaskDelete()--------> 删除/等待回收
```

### 3.2 技术价值

任务调度的目标不是追求平均吞吐量，而是保证：

1. 高关键任务在确定时间内获得 CPU。
2. 无任务可运行时进入低功耗。
3. 等待外设的任务不占用 CPU。
4. 多任务共享资源时保持数据一致性。
5. 过载时仍能保证关键控制链路。

### 3.3 主流调度分支

- **固定优先级抢占调度**：FreeRTOS、ThreadX、RT-Thread 常用模式。
- **固定优先级非抢占调度**：仅在主动让出或阻塞时切换。
- **同优先级时间片轮转**：同优先级就绪任务按 Tick 轮换。
- **RMS**：周期越短，静态优先级越高。
- **DMS**：相对截止期越短，静态优先级越高。
- **EDF**：绝对截止期最早的任务优先，属于动态优先级调度。
- **协作式调度**：任务必须主动让出 CPU。

---

## 4. 核心特性横向对比

|维度|固定优先级抢占|同优先级时间片|协作式|EDF|
|---|---|---|---|---|
|优先级性质|静态|静态且相同|通常静态|动态|
|切换触发|高优先级就绪|Tick 到达|阻塞或主动让出|更早截止期任务就绪|
|响应确定性|高|中|依赖任务自律|高，但内核复杂|
|调度开销|低|随 Tick 增加|最低|较高|
|饥饿风险|低优先级可能饥饿|同级通常公平|长任务阻塞全系统|过载时任务可能错过截止期|
|优先级反转|存在|存在|存在|存在且分析更复杂|
|可调度性分析|RMS/DMS 响应时间分析|需加入时间片等待|需加入最长非抢占段|利用率分析|
|FreeRTOS 原生支持|支持|支持|支持|不原生支持|
|典型应用|工业控制、通信栈|后台同类工作线程|极简系统|多媒体、动态实时负载|

**关键结论：时间片轮转不会让低优先级任务获得 CPU。** 它只在多个**最高就绪优先级相同**的任务之间轮换。

---

## 5. 底层原理与功能特性深度解析

### 5.1 TCB 与任务上下文

简化后的 TCB：

```
typedef struct {
    volatile StackType_t *pxTopOfStack;
    ListItem_t xStateListItem;
    ListItem_t xEventListItem;
    UBaseType_t uxPriority;
    StackType_t *pxStack;
    char pcTaskName[configMAX_TASK_NAME_LEN];
} TCB_t;
```

Cortex-M 任务切换时：

- 硬件自动保存 `R0-R3、R12、LR、PC、xPSR`。
- PendSV 软件保存 `R4-R11`。
- 若使用 FPU，还需按配置和浮点使用状态保存 `S16-S31`。
- `pxCurrentTCB->pxTopOfStack` 保存当前 PSP。
- 调度器选择新 TCB，恢复新任务上下文。

因此，一次上下文切换不仅是修改函数指针，而是切换**寄存器现场、栈和任务状态**。

### 5.2 就绪队列与最高优先级选择

FreeRTOS 为每个优先级维护一条就绪链表：

```
static List_t pxReadyTasksLists[configMAX_PRIORITIES];
static volatile UBaseType_t uxTopReadyPriority;
```

概念化调度逻辑：

```
static void select_highest_priority_task(void)
{
    UBaseType_t priority = find_highest_ready_priority();

    /* listGET_OWNER_OF_NEXT_ENTRY 会推进链表索引，
       因而同优先级任务天然具备轮转能力。 */
    listGET_OWNER_OF_NEXT_ENTRY(pxCurrentTCB,
                                &pxReadyTasksLists[priority]);
}
```

最高优先级查找可采用：

- 从高到低扫描：复杂度最坏为 `O(configMAX_PRIORITIES)`。
- 硬件位图加 CLZ：接近 `O(1)`，Cortex-M 端口常使用该方式。
- 多级位图：适合优先级数量较多的内核。

### 5.3 抢占式调度

配置：

```
#define configUSE_PREEMPTION 1
```

高优先级任务进入就绪态的主要路径：

- ISR 释放信号量、队列或任务通知。
- 任务解除另一个高优先级任务的阻塞。
- 延时到期。
- 挂起状态被恢复。

ISR 唤醒任务的标准模式：

```
void DMA_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;
    uint32_t status = DMA1->ISR;

    DMA1->IFCR = status; /* 先清除硬件中断源 */

    vTaskNotifyGiveFromISR(g_process_task,
                           &higher_priority_task_woken);

    /* 必要时触发 PendSV，在 ISR 退出后完成任务切换。 */
    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

`portYIELD_FROM_ISR()` 不能遗漏。遗漏后高优先级任务通常要等到下一 Tick 或其他调度点，额外延迟上界接近一个 Tick 周期。

### 5.4 时间片轮转

配置：

```
#define configUSE_PREEMPTION  1
#define configUSE_TIME_SLICING 1
#define configTICK_RATE_HZ     1000
```

在 Tick 中断中，若当前最高优先级就绪链表包含多个任务，则请求上下文切换。

假设两个同优先级 CPU 密集任务 A、B，Tick 为 1 ms：

```
0 ms       1 ms       2 ms       3 ms
|---- A ----|---- B ----|---- A ----|---- B ----|
```

时间片通常是**一个 Tick 周期**，但实际运行片段可能小于一个 Tick，因为任务可以提前阻塞、让出或被更高优先级任务抢占。

关闭时间片不等于禁止抢占：

```
#define configUSE_PREEMPTION   1
#define configUSE_TIME_SLICING 0
```

此时高优先级任务仍可抢占当前任务；同优先级任务不会仅因 Tick 到达而强制轮换，但可能在其他调度点切换。

### 5.5 周期任务的正确实现

使用 `vTaskDelayUntil()` 维持绝对周期，避免累计漂移：

```
static void control_task(void *argument)
{
    const TickType_t period = pdMS_TO_TICKS(10U);
    TickType_t next_release = xTaskGetTickCount();

    (void)argument;

    for (;;) {
        uint32_t start = DWT->CYCCNT;

        read_inputs();
        execute_control();
        write_outputs();

        uint32_t cycles = DWT->CYCCNT - start;
        if (cycles > CONTROL_WCET_LIMIT_CYCLES) {
            report_timing_fault(cycles);
        }

        vTaskDelayUntil(&next_release, period);
    }
}
```

`vTaskDelay(10)` 表达的是“执行结束后再等待 10 Tick”，周期为：

Tactual=Ctask+Tdelay+TpreemptionTactual​=Ctask​+Tdelay​+Tpreemption​

`vTaskDelayUntil()` 表达的是相对固定释放时刻，适合周期控制任务。

### 5.6 阻塞优于轮询

```
static void acquisition_task(void *argument)
{
    (void)argument;

    for (;;) {
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100U)) == 0U) {
            handle_acquisition_timeout();
            continue;
        }

        process_dma_buffer();
    }
}
```

事件阻塞任务不进入就绪队列，不消耗 CPU 时间片；轮询任务即使调用 `taskYIELD()`，仍可能阻塞低优先级任务。

---

## 6. 性能量化分析

### 6.1 测试基线

以下为工程估算基线，具体结果必须在目标芯片和编译选项下复测：

- MCU：STM32F407，Cortex-M4F，168 MHz。
- FreeRTOS 10.5.x。
- GCC `-O2`，FPU 硬件浮点。
- Tick：1 kHz。
- 数据来自 DWT Cycle Counter 测量，Flash Cache 命中。
- 数值不包含具体业务 ISR 执行时间。

|操作|典型周期|典型时间|
|---|---|---|
|无 FPU 活跃的任务切换|180~320 cycles|1.07~1.90 µs|
|FPU 扩展上下文切换|300~520 cycles|1.79~3.10 µs|
|任务通知唤醒并切换|350~650 cycles|2.08~3.87 µs|
|队列发送并唤醒接收者|550~1000 cycles|3.27~5.95 µs|
|Tick ISR，无任务切换|120~250 cycles|0.71~1.49 µs|

换算公式：

tμs=CyclesFCPU(MHz)tμs​=FCPU(MHz)​Cycles​

例如 420 cycles、168 MHz：

t=420168=2.5 μst=168420​=2.5 μs

### 6.2 RAM 开销

单任务 RAM：

Mtask=sizeof(TCBt)+StackDepth×sizeof(StackTypet)+AllocatorOverheadMtask​=sizeof(TCBt​)+StackDepth×sizeof(StackTypet​)+AllocatorOverhead

假设：

- `sizeof(TCB_t) = 96 B`
- 栈深度为 512 个 `StackType_t`
- Cortex-M 的 `StackType_t = 4 B`
- 堆管理元数据约 8 B

则：

Mtask=96+512×4+8=2152 BMtask​=96+512×4+8=2152 B

注意 FreeRTOS `xTaskCreate()` 的栈深度单位通常是**栈元素数量，不是字节数**。

### 6.3 Tick 开销

Tick 的 CPU 占用率：

Utick=Ctick×ftickfcpuUtick​=fcpu​Ctick​×ftick​​

若 Tick ISR 平均 220 cycles，Tick 为 1 kHz：

Utick=220×1000168×106=0.131%Utick​=168×106220×1000​=0.131%

若提高到 10 kHz，占用约为 **1.31%** ，且会增加缓存扰动与抢占抖动。不要用极高 Tick 频率补偿错误的时间设计；亚毫秒定时应使用硬件定时器。

### 6.4 固定优先级可调度性

周期任务利用率：

U=∑i=1nCiTiU=i=1∑n​Ti​Ci​​

RMS 的充分条件：

U≤n(21/n−1)U≤n(21/n−1)

当任务数趋于无穷时约为 **69.3%** 。该条件是充分非必要条件；超过它不代表一定不可调度，应继续执行响应时间分析：

Ri=Ci+Bi+∑j∈hp(i)⌈RiTj⌉CjRi​=Ci​+Bi​+j∈hp(i)∑​⌈Tj​Ri​​⌉Cj​

其中：

- CiCi​：任务 WCET。
- BiBi​：低优先级任务造成的最大阻塞时间。
- hp(i)hp(i)：所有更高优先级任务。
- 若最终 Ri≤DiRi​≤Di​，任务满足截止期。

### 6.5 主要瓶颈与优化收益

|瓶颈|表现|优化手段|典型收益|
|---|---|---|---|
|Tick 过高|ISR 占用和功耗升高|Tickless + 硬件定时器|空闲功耗下降 20%~80%|
|高频队列复制|CPU 和临界区开销高|DMA 缓冲区 + 指针队列/通知|消息路径缩短 30%~70%|
|任务数量过多|RAM 和切换增加|事件驱动状态机合并任务|每删除一个任务节省约 1~4 KiB|
|长临界区|中断延迟升高|缩小临界区、双缓冲|最坏中断延迟降低至原来的 10%~30%|
|同级 CPU 密集任务|调度抖动|明确优先级或工作队列|关键任务抖动显著降低|

---

## 7. 应用场景选型指南

### 7.1 决策流程

```
任务是否存在硬截止期？
├─ 是
│  ├─ 截止期/周期是否基本固定？
│  │  ├─ 是：固定优先级抢占 + RMS/DMS + 响应时间分析
│  │  └─ 否：评估 EDF 或专用动态调度器
│  └─ 是否共享互斥资源？
│     ├─ 是：优先级继承/优先级上限 + 阻塞时间分析
│     └─ 否：保持无共享或消息传递
└─ 否
   ├─ 多个同类任务是否需要近似公平使用 CPU？
   │  ├─ 是：同优先级时间片轮转
   │  └─ 否：事件驱动阻塞 + 固定优先级
   └─ 是否为纯后台工作？
      ├─ 是：低优先级工作线程
      └─ 否：按响应时限设置优先级
```

### 7.2 典型场景

|需求|推荐方案|理由|
|---|---|---|
|1 kHz 电机控制|高优先级抢占任务，由定时器唤醒|控制周期和抖动可量化|
|以太网协议栈|固定优先级 + 事件阻塞|避免轮询浪费 CPU|
|两路同类日志压缩|同优先级时间片|无硬截止期，要求公平|
|UI 与 CLI|同级时间片或单事件循环|交互任务不应抢占控制链路|
|Flash 擦除|最低优先级任务 + 分段执行|擦除等待不可阻塞关键任务|
|安全监控|独立高优先级周期任务|与功能任务解耦，检测超时|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. 按**响应时限和关键度**设置优先级，而不是按开发者主观重要性设置。
2. ISR 只完成采样、清中断和事件投递，复杂处理放到任务。
3. CPU 密集任务必须主动分块、阻塞或设置预算。
4. 周期任务使用 `vTaskDelayUntil()` 或硬件定时器释放。
5. 共享数据优先采用单写者、消息传递和双缓冲。
6. 删除动态任务前必须解决句柄、资源所有权和异步回调问题。
7. 每个任务定义 WCET、周期、截止期、栈预算和故障策略。

### 8.2 选型决策矩阵

|指标权重|抢占式|时间片|协作式|
|---|---|---|---|
|硬实时确定性|5|3|1|
|实现复杂度|4|4|5|
|公平性|2|5|2|
|故障隔离|4|3|1|
|功耗优化|5|3|4|
|工业控制适配度|5|2|1|

### 8.3 工业级编码规范

```
typedef struct {
    TaskHandle_t handle;
    StaticTask_t tcb;
    StackType_t stack[512];
} TaskStorage_t;

static TaskStorage_t g_control_task;

bool control_task_start(void)
{
    g_control_task.handle = xTaskCreateStatic(
        control_task,
        "ctrl",
        sizeof(g_control_task.stack) / sizeof(g_control_task.stack[0]),
        NULL,
        CONTROL_TASK_PRIORITY,
        g_control_task.stack,
        &g_control_task.tcb);

    return g_control_task.handle != NULL;
}
```

推荐静态创建关键任务：

- 启动期间即可发现内存不足。
- 避免运行期堆碎片。
- 内存布局可审计。
- 便于安全标准要求下做资源上界证明。

---

## 9. 常见错误与避坑指南

### 9.1 高频任务忙轮询

错误代码：

```
static void bad_task(void *argument)
{
    for (;;) {
        if (device_ready()) {
            process_data();
        }
    }
}
```

根因：任务始终处于就绪态。同优先级任务只能依赖时间片，低优先级任务可能永久饥饿。

正确实现：

```
static void good_task(void *argument)
{
    for (;;) {
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(50U)) == 0U) {
            handle_device_timeout();
            continue;
        }

        process_data();
    }
}
```

风险：CPU 满载、功耗升高、低优先级看门狗和日志任务失去运行机会。

### 9.2 ISR 唤醒任务后不请求切换

错误代码：

```
void UART_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    vTaskNotifyGiveFromISR(g_rx_task, &woken);
    /* 缺少 portYIELD_FROM_ISR(woken) */
}
```

正确实现：

```
void UART_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    clear_uart_irq();
    vTaskNotifyGiveFromISR(g_rx_task, &woken);
    portYIELD_FROM_ISR(woken);
}
```

根因：任务已进入就绪态，但 PendSV 未被请求。

风险：在 100 Hz Tick 下，最坏可增加约 **10 ms** 响应延迟。

### 9.3 使用二值信号量保护共享资源

错误代码：

```
xSemaphoreTake(g_binary_sem, portMAX_DELAY);
access_shared_bus();
xSemaphoreGive(g_binary_sem);
```

根因：二值信号量通常不提供互斥量的优先级继承语义。

正确实现：

```
if (xSemaphoreTake(g_bus_mutex, pdMS_TO_TICKS(5U)) == pdPASS) {
    access_shared_bus();
    xSemaphoreGive(g_bus_mutex);
} else {
    report_bus_lock_timeout();
}
```

风险：出现无界优先级反转，高优先级控制任务错过截止期。

### 9.4 误用 `vTaskDelay()` 实现周期任务

错误代码：

```
for (;;) {
    execute_control();             /* 执行时间会进入周期 */
    vTaskDelay(pdMS_TO_TICKS(10U));
}
```

正确实现：

```
TickType_t release = xTaskGetTickCount();

for (;;) {
    execute_control();
    vTaskDelayUntil(&release, pdMS_TO_TICKS(10U));
}
```

根因：相对延时从调用时刻开始，业务执行时间与抢占时间造成累计漂移。

风险：采样频率不稳定、控制器离散模型失配。

### 9.5 在临界区调用阻塞 API

错误代码：

```
taskENTER_CRITICAL();
xQueueReceive(g_queue, &message, portMAX_DELAY);
taskEXIT_CRITICAL();
```

正确实现：

```
if (xQueueReceive(g_queue, &message, pdMS_TO_TICKS(20U)) == pdPASS) {
    taskENTER_CRITICAL();
    update_small_shared_state(&message);
    taskEXIT_CRITICAL();
}
```

根因：临界区屏蔽可调用内核 API 的中断；阻塞操作又依赖 Tick 或事件中断恢复。

风险：断言、死锁、长时间关中断以及系统时基失效。

### 9.6 栈深度单位理解错误

错误代码：

```
/* 误以为 512 表示 512 字节 */
xTaskCreate(worker, "work", 512, NULL, 2, NULL);
```

正确实现：

```
#define WORKER_STACK_BYTES 2048U
#define WORKER_STACK_WORDS \
    (WORKER_STACK_BYTES / sizeof(StackType_t))

_Static_assert((WORKER_STACK_BYTES % sizeof(StackType_t)) == 0U,
               "Stack size alignment error");
```

风险：跨架构移植时栈预算错误，造成 RAM 浪费或栈溢出。

---

## 10. 多机制组合使用方案

### 10.1 协同架构

```
硬件定时器 ISR
  |
  +--> 任务通知 --> 高优先级控制任务
  |
DMA ISR
  |
  +--> 指针队列 --> 中优先级数据处理任务
                         |
                         +--> 双缓冲 --> 通信任务
                                              |
                                              +--> 低优先级日志任务

所有关键任务
  +--> 运行时间预算监测
  +--> 心跳位图
  +--> 独立监督任务
```

### 10.2 完整代码框架

```
typedef struct {
    const uint16_t *samples;
    size_t count;
    uint32_t sequence;
} SampleBlock_t;

static TaskHandle_t g_control_task;
static QueueHandle_t g_sample_queue;
static EventGroupHandle_t g_health_events;

void TIM_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    clear_timer_irq();
    vTaskNotifyGiveFromISR(g_control_task, &woken);
    portYIELD_FROM_ISR(woken);
}

void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    SampleBlock_t block = dma_completed_block();

    clear_dma_irq();

    if (xQueueSendFromISR(g_sample_queue, &block, &woken) != pdPASS) {
        record_isr_queue_overflow();
    }

    portYIELD_FROM_ISR(woken);
}

static void control_task(void *argument)
{
    (void)argument;

    for (;;) {
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(2U)) == 0U) {
            enter_control_safe_state();
            continue;
        }

        run_control_step();
        xEventGroupSetBits(g_health_events, HEALTH_CONTROL_OK);
    }
}

static void processing_task(void *argument)
{
    SampleBlock_t block;
    (void)argument;

    for (;;) {
        if (xQueueReceive(g_sample_queue, &block,
                          pdMS_TO_TICKS(100U)) != pdPASS) {
            report_sensor_timeout();
            continue;
        }

        if (!validate_block(&block)) {
            report_corrupt_block(block.sequence);
            continue;
        }

        process_sample_block(&block);
        release_dma_block(&block);
        xEventGroupSetBits(g_health_events, HEALTH_PROCESS_OK);
    }
}

static void supervisor_task(void *argument)
{
    const EventBits_t required = HEALTH_CONTROL_OK | HEALTH_PROCESS_OK;
    (void)argument;

    for (;;) {
        EventBits_t bits = xEventGroupWaitBits(
            g_health_events,
            required,
            pdTRUE,
            pdTRUE,
            pdMS_TO_TICKS(100U));

        if ((bits & required) != required) {
            record_health_fault(bits);
            force_outputs_safe();
        } else {
            feed_independent_watchdog();
        }
    }
}
```

设计要点：

- ISR 到单任务事件使用任务通知，减少 RAM 和调度开销。
- 携带数据和所有权时使用队列。
- 监督任务不只检查任务是否存在，而是检查任务是否在时间窗内完成有效工作。
- 看门狗只能由监督任务喂养。

---

## 11. 工业级实际案例分析

### 11.1 伺服电机控制器

**需求：**

- 电流环周期 50 µs。
- 速度环周期 1 ms。
- CANopen 通信响应小于 5 ms。
- 日志允许丢失，不得影响控制。

**架构：**

```
20 kHz PWM ISR：采样锁存、快速保护
  -> 电流环任务/ISR 后半部：最高优先级
1 kHz 定时事件
  -> 速度环任务：次高优先级
CAN ISR
  -> CAN RX 任务：中优先级
  -> 日志任务：最低优先级
```

核心代码：

```
static void current_loop_task(void *argument)
{
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        uint32_t start = DWT->CYCCNT;
        CurrentSample_t sample = adc_get_latched_sample();

        if (!sample.valid) {
            pwm_force_safe();
            continue;
        }

        CurrentCommand_t command = foc_step(&sample);
        pwm_apply(&command);

        if ((DWT->CYCCNT - start) > CURRENT_LOOP_BUDGET_CYCLES) {
            report_deadline_overrun();
        }
    }
}
```

设计要点：

- 50 µs 回路需评估任务切换成本；若预算极紧，可将保护和核心计算放在 ISR。
- 禁止电流环获取可能阻塞的互斥量。
- 日志采用无等待环形缓冲区，满时丢弃低价值记录。

### 11.2 工业网关

**需求：**

- 4 路串口协议采集。
- 以太网上传。
- OTA 写 Flash。
- 单路异常不能拖垮系统。

**方案：**

- 串口 ISR + DMA，只投递完成缓冲区。
- 每个协议实例使用同优先级工作任务，允许时间片公平执行。
- 网络任务优先级高于日志和 OTA。
- OTA 按块擦写，每块后阻塞或让出 CPU。

```
static void ota_task(void *argument)
{
    OtaBlock_t block;

    for (;;) {
        if (xQueueReceive(g_ota_queue, &block, portMAX_DELAY) != pdPASS) {
            continue;
        }

        if (!verify_block(&block)) {
            abort_ota(OTA_ERROR_HASH);
            continue;
        }

        if (!flash_program_bounded(&block)) {
            abort_ota(OTA_ERROR_FLASH);
            continue;
        }

        taskYIELD();
    }
}
```

设计要点：Flash 驱动必须评估擦除期间是否阻塞取指、中断和 DMA，不可只从任务优先级判断实时影响。

### 11.3 电池管理系统 BMS

**需求：**

- 10 ms 电压采样。
- 100 ms 状态估算。
- 故障检测响应小于 5 ms。
- 通信拥塞时仍需可靠切断输出。

**方案：**

- 硬件比较器负责一级过压/过流保护。
- 高优先级故障任务负责软件确认和继电器控制。
- SOC/SOH 估算任务为中优先级周期任务。
- CAN 与日志不得持有保护路径所需互斥量。

核心原则：**安全动作不能依赖低优先级任务释放资源，也不能依赖日志成功写入。**

---

## 12. 高频问题深度答疑

### 12.1 抢占式调度是否一定比时间片实时？

两者不是互斥关系。抢占解决不同优先级之间的响应，时间片解决同优先级任务间的轮转。硬实时任务主要依赖固定优先级抢占和可调度性分析，不应依赖时间片保证截止期。

### 12.2 开启时间片后，低优先级任务能否避免饥饿？

不能。只要更高优先级任务持续处于就绪态，低优先级任务就无法运行。必须使高优先级任务在无工作时阻塞。

### 12.3 Tick 越高，实时性是否越好？

不一定。Tick 只决定基于 Tick 的延时分辨率和同级轮转粒度。中断唤醒高优先级任务可以立即触发 PendSV，不需要等待 Tick。提高 Tick 会增加 CPU 占用和功耗。

### 12.4 `taskYIELD()` 能否解决忙轮询问题？

不能彻底解决。它主要把 CPU 交给同优先级就绪任务；更低优先级任务仍可能饥饿。应使用阻塞式同步原语。

### 12.5 为什么高优先级任务仍会出现长延迟？

应依次检查：

- 更高优先级 ISR 是否执行过长。
- 中断是否被临界区或 BASEPRI 屏蔽。
- 是否存在优先级反转。
- ISR 是否遗漏 `portYIELD_FROM_ISR()`。
- 是否存在 Flash 擦除、Cache miss 或总线争用。
- 任务是否错误等待互斥量、队列或驱动状态。

### 12.6 是否应给每个外设创建一个任务？

不应机械对应。任务是调度和隔离单元，不是代码模块。多个低频外设可以由一个事件驱动任务处理；只有在实时等级、阻塞行为或故障隔离需求不同的情况下才拆分任务。

---

## 13. 课程核心总结

- **调度器只从就绪任务中选择最高优先级任务。**
- **抢占式调度处理优先级差异；时间片处理同优先级公平性。**
- 高优先级任务必须在无工作时阻塞，否则低优先级任务会饥饿。
- 周期任务使用绝对时间基准，硬实时任务必须进行 WCET 和响应时间分析。
- ISR 唤醒高优先级任务后应正确请求上下文切换。
- 互斥量的优先级继承只能缓解特定优先级反转，不能代替资源架构设计。
- 确定性通常排序为：**硬件触发固定路径 > 固定优先级抢占 > 同级时间片 > 协作式长任务**。
- 通信效率通常排序为：**直接任务通知 > 指针队列 > 数据复制队列**，但语义能力依次增强。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|调度策略|同步机制|
|---|---|---|
|高频控制环|高优先级抢占|ISR 任务通知|
|周期采集|固定优先级周期任务|`vTaskDelayUntil()`|
|DMA 数据处理|事件驱动抢占|指针队列|
|多个同类后台工作|同优先级时间片|工作队列|
|共享外设|固定优先级|互斥量 + 超时|
|系统监督|独立高优先级周期任务|事件组/心跳位图|

### 14.2 特性对比表

|配置|行为|
|---|---|
|`PREEMPTION=1, TIME_SLICING=1`|高优先级抢占，同级按 Tick 轮转|
|`PREEMPTION=1, TIME_SLICING=0`|高优先级抢占，同级不因 Tick 强制轮转|
|`PREEMPTION=0`|主要依赖阻塞、主动让出或显式调度点|
|Tickless Idle|空闲期抑制周期 Tick，降低功耗|
|`vTaskDelay()`|相对延时，周期可能漂移|
|`vTaskDelayUntil()`|绝对周期释放，适合周期任务|

---

## 15. 学习效果自检

- [ ]  能画出任务在运行、就绪、阻塞和挂起状态间的迁移。
- [ ]  能解释 PendSV 为什么适合执行上下文切换。
- [ ]  能说明时间片为何不能解决低优先级任务饥饿。
- [ ]  能正确编写 ISR 唤醒任务并触发切换的代码。
- [ ]  能根据 TCB 和栈配置计算单任务 RAM 上界。
- [ ]  能测量上下文切换时间、ISR 到任务延迟和任务 WCET。
- [ ]  能使用响应时间公式验证固定优先级任务是否满足截止期。
- [ ]  能定位忙轮询、优先级反转、长临界区和周期漂移。
- [ ]  能为每个任务定义周期、截止期、优先级、栈和故障策略。
- [ ]  能设计过载情况下仍维持关键控制功能的降级架构。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

1. 创建三个不同优先级任务，通过 GPIO 翻转观察抢占顺序。
2. 创建两个同优先级 CPU 密集任务，分别开关时间片，比较运行时间占比。
3. 使用 ISR 通知高优先级任务，测量 ISR 入口到任务执行的延迟。
4. 构造高、中、低三个任务复现优先级反转，再使用互斥量验证优先级继承。
5. 使用 `vTaskDelay()` 和 `vTaskDelayUntil()` 连续运行 1 小时，对比周期累计误差。
6. 建立包含 WCET、阻塞时间和截止期的任务表，完成响应时间分析。
7. 注入队列满、任务超时、栈不足和 CPU 过载故障，验证降级策略。

### 16.2 性能测试方法

使用 DWT Cycle Counter：

```
static void dwt_cycle_counter_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}
```

测量指标应至少包括：

- ISR 入口延迟。
- ISR 退出到任务首条业务指令的延迟。
- 上下文切换周期数。
- 各任务平均执行时间和 WCET。
- 周期抖动与截止期超限次数。
- 栈最小剩余量。
- 队列最大深度和溢出次数。
- CPU 空闲率和过载持续时间。

测试时必须覆盖 Flash Cache miss、DMA 总线争用、最高通信负载、温度变化以及编译优化差异，不能用平均值替代 WCET。

### 16.3 进阶学习方向

- FreeRTOS `xTaskIncrementTick()`、`vTaskSwitchContext()` 和 PendSV 汇编源码。
- RMS、DMS、EDF 与响应时间分析。
- 优先级继承、优先级上限协议和资源访问阻塞上界。
- SMP RTOS 的任务迁移、核亲和性和缓存一致性。
- Tickless Idle 与低功耗时间补偿。
- AUTOSAR OS/OSEK 的任务与资源模型。
- Safety RTOS 的空间隔离、时间分区和混合关键度调度。
- 基于 Tracealyzer/SystemView 的调度轨迹和最坏响应时间验证。