
本课以 **FreeRTOS 任务通知**为主线。任务通知是一种“直接发给指定任务”的轻量同步机制，适合唤醒任务、累计事件次数或传递有限的状态位。它不是通用消息队列，也不提供多订阅者广播。

## 1. 学习目标

### 理解

- 理解任务通知由目标任务的通知状态和通知值构成。
- 理解任务通知是**定向到某个任务**的，而不是独立的 RTOS 对象。
- 区分通知计数、通知位、通知值覆盖和“只唤醒任务”四种语义。
- 理解任务通知与队列、信号量、事件组的能力边界。

### 掌握

- 正确使用 `xTaskNotify()`、`xTaskNotifyGive()`、`xTaskNotifyWait()` 和 `ulTaskNotifyTake()`。
- 正确使用 `FromISR` API，并处理高优先级任务唤醒请求。
- 使用通知位合并多个状态条件，或使用通知计数累计事件。
- 为每个通知索引定义唯一的语义和使用方。
- 处理超时、计数清除、通知覆盖和任务生命周期。

### 精通

- 从 FreeRTOS 内核角度理解通知状态、通知值和等待状态的区别。
- 分析多个生产者共用同一通知槽时的覆盖、合并和计数风险。
- 根据实时性、数据量、消费者数量选择任务通知、队列或信号量。
- 使用任务通知作为“门铃”，与 DMA 环形缓冲区、队列或共享状态协同工作。
- 评估通知数组对 TCB RAM 的影响和通知路径的调度延迟。

### 能够设计

- 高实时 ISR 到单任务的通知链路。
- DMA 完成、UART 数据到达和定时采样唤醒架构。
- 带通知位和超时的任务状态机。
- 多通知源共用一个任务时的位分配和索引管理方案。
- 通知与实际数据队列分离的工业级“数据 + 门铃”架构。

---

## 2. 前置要求

### 知识要求

- 理解任务调度、阻塞、就绪和优先级抢占。
- 理解队列、二值信号量、计数信号量和事件组。
- 理解 ISR 与任务上下文 API 的区别。
- 理解 `volatile` 不能替代同步机制。
- 理解 DMA 缓冲区所有权、内存生命周期和缓存一致性。

### 技能要求

- 能够使用 FreeRTOS 任务和队列 API。
- 能够配置 NVIC 中断优先级和 `configMAX_SYSCALL_INTERRUPT_PRIORITY`。
- 能够阅读 `tasks.c` 和 `task.h` 中的通知相关实现。
- 能够使用 DWT、GPIO 或 Trace 工具测量通知延迟。
- 能够编写队列积压、事件丢失和任务超时的诊断统计。

---

## 3. 技术概述

### 3.1 任务通知是什么

FreeRTOS 任务通知是一种附属于目标任务的同步状态。任务 TCB 中通常为每个通知索引维护：

```
通知值：32 位整数
通知状态：未等待、等待中、已收到等状态
```

发送者直接指定目标任务：

```
xTaskNotify(
    target_task,
    value,
    action);
```

通知可以用于：

- 唤醒一个指定任务；
- 累计事件次数；
- 传递事件位；
- 覆盖保存一个最新整数值；
- 以“通知待处理”状态传递一个不携带数据的信号。

### 3.2 任务通知与独立同步对象的区别

队列和信号量通常是独立内核对象：

```
生产者 -> Queue/Semaphore -> 一个或多个等待者
```

任务通知则是目标任务内部的状态：

```
生产者 -> 目标任务 TCB 中的通知槽
```

因此它天然适合：

```
多个发送者 -> 一个已知目标任务
```

不适合直接表达：

```
一个消息 -> 多个任务各自收到一份
```

### 3.3 通知状态与通知值是两个概念

|内容|表示什么|
|---|---|
|通知状态|目标任务是否收到尚未处理的通知|
|通知值|计数、位集合或一个 32 位数值|

不要只看通知值判断是否有通知。例如使用 `eNoAction` 时，通知状态可以变为“已收到”，但通知值不一定变化。

### 3.4 任务通知的四种主要用途

|用途|典型 API|语义|
|---|---|---|
|计数信号量|`xTaskNotifyGive()` + `ulTaskNotifyTake()`|每次通知累加计数|
|二值门铃|`xTaskNotifyGive()` + `ulTaskNotifyTake(pdTRUE, ...)`|多次通知可合并为“至少一次”|
|事件位|`xTaskNotify(..., eSetBits)` + `xTaskNotifyWait()`|多个位可合并|
|单值邮箱|`xTaskNotify(..., eSetValueWithOverwrite)`|最新值覆盖旧值|

### 3.5 适用边界

任务通知的值通常是 **32 位**，不是任意长度消息：

- 不能直接传递结构体；
- 不能可靠传递 64 位时间戳或任意指针；
- 不保存多条有序消息；
- 不提供独立的生产者阻塞队列；
- 一个通知槽的状态和操作语义必须由参与者共同约定。

---

## 4. 核心特性横向对比

### 4.1 任务通知与其他机制

|维度|任务通知|二值信号量|计数信号量|消息队列|事件组|
|---|---|---|---|---|---|
|目标|指定任务|对象等待者|对象等待者|队列消费者|多个条件等待者|
|是否独立对象|否，附属于任务|是|是|是|是|
|保存数据|32 位通知值|否|计数|固定大小消息|位集合|
|累计次数|可通过计数语义|否|是|是|否|
|保存消息顺序|否|否|否|是|否|
|多接收者|不适合广播|可竞争消费|可竞争消费|可竞争消费|多任务等待条件|
|ISR 支持|支持 FromISR API|支持|支持|支持|支持，但需考虑实现路径|
|内存开销|通常较低|独立对象|独立对象|随容量增长|独立对象|
|典型场景|单任务唤醒|事件同步|数量累计|数据传输|多状态组合|

### 4.2 通知动作对比

|Action|行为|适合用途|主要风险|
|---|---|---|---|
|`eNoAction`|不改变通知值，只设置通知状态|纯唤醒|多次通知合并|
|`eSetBits`|对通知值执行按位 OR|事件位|同一位重复置位不计数|
|`eIncrement`|通知值加一|事件计数|计数溢出|
|`eSetValueWithOverwrite`|覆盖为新值|最新值邮箱|旧值丢失|
|`eSetValueWithoutOverwrite`|仅在没有待处理通知时写入|不允许覆盖的单值通信|写入失败必须处理|

### 4.3 按业务语义选型

|业务需求|建议|
|---|---|
|只需唤醒一个任务，让它检查状态|`eNoAction` 或任务通知门铃|
|每次硬件事件都要累计|`eIncrement` + `ulTaskNotifyTake(pdFALSE, ...)`|
|只需“至少有一个事件发生”|门铃式通知，可合并事件|
|多种原因可同时触发同一任务|`eSetBits` + `xTaskNotifyWait()`|
|每条事件携带数据并要求保序|消息队列|
|一个状态要被多个任务广播观察|事件组或订阅架构|
|共享资源排他访问|互斥量|

---

## 5. 底层原理与功能特性深度解析

### 5.1 通知槽与通知数组

FreeRTOS 任务控制块通常保存类似信息：

```
/* 示意：真实内核结构以项目版本为准。 */
typedef struct
{
    uint32_t notification_value[NOTIFICATION_COUNT];
    uint8_t notification_state[NOTIFICATION_COUNT];
} task_notification_storage_t;
```

默认配置通常只有一个通知索引。支持通知数组的版本可配置：

```
#define configTASK_NOTIFICATION_ARRAY_ENTRIES  3
```

每个索引有独立的：

```
通知值
通知状态
```

设计时要注意：

- 不同索引可以隔离不同通信用途；
- 所有发送者和接收者必须使用一致索引；
- 传统未带 `Indexed` 的 API 通常使用索引 0；
- 使用通知数组的 API 必须核对当前 FreeRTOS 版本和配置；
- 不能假设索引 0 的状态可以和索引 1 的状态互相独立访问。

### 5.2 `xTaskNotify()` 的动作语义

发送：

```
BaseType_t result = xTaskNotify(
    task_handle,
    value,
    eSetBits);
```

常见动作：

```
eNoAction
eSetBits
eIncrement
eSetValueWithOverwrite
eSetValueWithoutOverwrite
```

可抽象为：

```
BaseType_t notify_model(
    notification_slot_t *slot,
    uint32_t value,
    eNotifyAction action)
{
    switch (action)
    {
        case eNoAction:
            /* 只标记通知已到达。 */
            break;

        case eSetBits:
            slot->value |= value;
            break;

        case eIncrement:
            slot->value++;
            break;

        case eSetValueWithOverwrite:
            slot->value = value;
            break;

        case eSetValueWithoutOverwrite:
            if (slot->state == taskNOTIFICATION_RECEIVED)
            {
                return pdFAIL;
            }
            slot->value = value;
            break;

        default:
            return pdFAIL;
    }

    slot->state = taskNOTIFICATION_RECEIVED;
    return pdPASS;
}
```

这只是逻辑模型，真实内核实现还会处理：

- 调度器状态；
- 目标任务是否阻塞在通知等待；
- 任务优先级和就绪列表；
- ISR 与任务的同步保护；
- Trace 和调试检查。

### 5.3 通知到达时目标任务的状态变化

```
目标任务正在等待通知：
    收到通知 -> 从阻塞态转为就绪态
    是否立即切换由优先级和当前调度上下文决定

目标任务没有等待：
    通知状态和值保留
    任务稍后等待时可以观察到通知

目标任务已经有未消费通知：
    根据 Action 合并、累加、覆盖或拒绝
```

任务通知不会因为接收者尚未执行等待函数就自动丢弃。具体保留方式取决于使用的 Action。

### 5.4 `xTaskNotifyWait()`：位与数值通知接收

典型调用：

```
uint32_t value = 0U;

BaseType_t notified = xTaskNotifyWait(
    0U,                /* 进入等待前不清除位 */
    NOTIFY_EVENT_MASK, /* 返回时清除指定位 */
    &value,
    pdMS_TO_TICKS(100));
```

参数：

|参数|含义|
|---|---|
|`ulBitsToClearOnEntry`|进入等待时先清除通知值中的指定位|
|`ulBitsToClearOnExit`|通知到达并退出时清除指定位|
|`pulNotificationValue`|返回观察到的通知值|
|`xTicksToWait`|最大等待时间|

返回：

```
pdTRUE  ：收到通知
pdFALSE ：超时
```

当通知值用于位集合时，建议：

```
#define NOTIFY_RX_READY   (1UL << 0)
#define NOTIFY_FAULT      (1UL << 1)
#define NOTIFY_TIMEOUT    (1UL << 2)
```

接收后按掩码判断：

```
if ((value & NOTIFY_FAULT) != 0U)
{
    handle_fault();
}
```

不要使用：

```
if (value != 0U)
```

来判断某个特定事件，因为值可能包含其他位或遗留信息。

### 5.5 `xTaskNotifyGive()` 与 `ulTaskNotifyTake()`：计数语义

发送一次：

```
BaseType_t result = xTaskNotifyGive(task_handle);
```

其核心语义类似：

```
目标任务通知值加一
通知状态置为收到
```

接收任务：

```
uint32_t count = ulTaskNotifyTake(
    pdTRUE,
    pdMS_TO_TICKS(100));
```

`ulTaskNotifyTake()` 常用作计数信号量：

- `pdFALSE`：成功时计数减一，逐次消费；
- `pdTRUE`：成功时将计数清零，一次取走当前累积量；
- 返回值是清除或递减前观察到的计数；
- 超时且没有通知时返回 0。

逐个处理：

```
while (ulTaskNotifyTake(pdFALSE, timeout) > 0U)
{
    process_one_event();
}
```

批量处理：

```
uint32_t pending = ulTaskNotifyTake(
    pdTRUE,
    timeout);

if (pending > 0U)
{
    process_pending_events(pending);
}
```

使用计数语义时应考虑 `uint32_t` 溢出。高频生产者若长期快于消费者，计数可能回绕，必须保证消费者服务能力足够，或使用更适合的数据队列。

### 5.6 二值门铃与计数信号量的区别

`xTaskNotifyGive()` 会递增通知值，因此它天然提供计数。

若接收方这样等待：

```
ulTaskNotifyTake(pdTRUE, timeout);
```

则一次唤醒会清掉当前累计值，可用于“有工作了，快去处理”的门铃。

这种方式可能合并多次事件。适用于：

```
通知只负责唤醒
真正待处理数量由环形缓冲区或硬件状态查询
```

如果每次事件都必须独立处理，应逐次递减，或传递队列消息。

### 5.7 通知位与 `eSetBits`

生产者：

```
xTaskNotify(
    task_handle,
    NOTIFY_RX_READY | NOTIFY_LINK_CHANGED,
    eSetBits);
```

消费者：

```
uint32_t value;

if (xTaskNotifyWait(
        0U,
        NOTIFY_RX_READY | NOTIFY_LINK_CHANGED,
        &value,
        portMAX_DELAY) == pdTRUE)
{
    if ((value & NOTIFY_RX_READY) != 0U)
    {
        process_rx_data();
    }

    if ((value & NOTIFY_LINK_CHANGED) != 0U)
    {
        refresh_link_state();
    }
}
```

多个发送者可以通过 `eSetBits` 合并不同原因，但：

- 相同位重复设置仍只保留一个位；
- 位值不保存顺序；
- 位值不携带额外参数；
- 每个位的清除责任要明确；
- 若通知值同时用于计数，不能混用不同语义。

### 5.8 `eSetValueWithOverwrite` 与 `eSetValueWithoutOverwrite`

覆盖模式：

```
xTaskNotify(
    task_handle,
    latest_value,
    eSetValueWithOverwrite);
```

效果：

```
新值替换旧值
```

适用于只关心最新值的简单状态，但不适合完整消息序列。

不覆盖模式：

```
BaseType_t result = xTaskNotify(
    task_handle,
    value,
    eSetValueWithoutOverwrite);
```

若目标任务已有未处理通知，可能返回 `pdFAIL`。调用者必须处理失败，不能假设值已经送达。

注意：

- 这两种模式都只能保存一个 32 位值；
- 结构体不能直接放入通知值；
- 不要把指针强制转成 32 位数用于跨平台代码；
- 大于 32 位的地址或值可能截断。

### 5.9 通知 API 的配对纪律

同一个通知索引的生产者和消费者应遵循一套语义。例如：

```
索引 0：事件位，使用 xTaskNotify(eSetBits) + xTaskNotifyWait
索引 1：计数通知，使用 xTaskNotifyGiveIndexed + ulTaskNotifyTakeIndexed
```

不推荐在同一个索引上混用：

```
eIncrement
eSetBits
eSetValueWithOverwrite
ulTaskNotifyTake
xTaskNotifyWait
```

因为这些操作共享通知值和状态，语义会相互破坏。**只有在通过状态机严格定义时，才可混用。**

### 5.10 通知数组与旧 API

支持通知数组的 FreeRTOS 版本提供带索引 API，例如：

```
xTaskNotifyIndexed()
xTaskNotifyWaitIndexed()
ulTaskNotifyTakeIndexed()
xTaskNotifyGiveIndexed()
```

配置项：

```
#define configTASK_NOTIFICATION_ARRAY_ENTRIES  2
```

使用前检查：

- 项目内核版本是否包含这些 API；
- 该配置是否大于使用的索引；
- 传统 API 是否仍默认使用索引 0；
- 模块是否统一封装索引，避免不同任务误用同一个槽。

### 5.11 ISR 中使用任务通知

ISR 通知目标任务：

```
void DMA_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    dma_clear_interrupt_flags();

    vTaskNotifyGiveFromISR(
        g_dma_task_handle,
        &higher_priority_task_woken);

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

或设置位：

```
void GPIO_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;
    BaseType_t result;

    result = xTaskNotifyFromISR(
        g_event_task_handle,
        NOTIFY_GPIO_CHANGED,
        eSetBits,
        &higher_priority_task_woken);

    if (result != pdPASS)
    {
        g_notify_failure_count++;
    }

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

要求：

- 使用 FromISR 版本；
- ISR 优先级必须满足 FreeRTOS 调用规则；
- 需要切换时调用对应端口的 yield 宏；
- 目标任务句柄在 ISR 运行前已有效；
- 不在 ISR 中执行可能阻塞的 API。

### 5.12 任务生命周期与句柄安全

通知以任务句柄定位目标，因此要保证：

- 发送前目标任务已经创建；
- 目标任务删除前已停止所有生产者；
- 不能保留已删除任务的句柄并继续发送；
- 任务重建后更新所有生产者使用的句柄；
- 对动态创建和删除任务的系统，应设计句柄发布和撤销同步。

---

## 6. 性能量化分析

### 6.1 测试基准与数据边界

建议记录以下测试条件：

```
MCU 和主频
FreeRTOS 版本及提交号
编译器版本和优化等级
Tick 频率
任务优先级
中断优先级
Trace 和断言配置
通知索引配置
```

本课未在具体目标板上实际运行，因此不把估算数字称为实测值。性能部分给出内存公式、周期换算和可复现测试方法，具体数值应由项目测量获得。

### 6.2 内存开销

每个任务通知索引通常增加：

```
一个 32 位通知值
一个通知状态字段
可能的结构体对齐填充
```

可以用近似式估算：

```
额外 TCB RAM ≈ N × (sizeof(uint32_t) + sizeof(state))
```

在常见 32 位平台上，单索引的字段负载约为 5 字节，但由于结构体对齐，实际增加量必须看 TCB 布局和配置。

项目中可比较：

```
configTASK_NOTIFICATION_ARRAY_ENTRIES = 1
```

和更多索引时的：

- `sizeof(TCB_t)`；
- 静态任务控制块大小；
- map 文件；
- 创建一定数量任务后的 RAM 总量。

`TCB_t` 常为内核私有类型，不应在应用代码中依赖其布局。

### 6.3 周期换算

CPU 时间计算：

```
T = cycles / fCPU
```

例如在 168 MHz 下：

|周期数|时间|
|---|---|
|168 cycles|1 μs|
|840 cycles|5 μs|
|1680 cycles|10 μs|

这只是换算公式，不是任务通知实测数据。

### 6.4 吞吐和积压

若事件生产速率为 `λp`，任务处理速率为 `λc`：

```
λp < λc：长期稳定
λp = λc：无裕量，抖动容易积压
λp > λc：积压持续增加
```

对计数通知，累计值可能反映积压次数，但不保存事件内容；对门铃通知，多个事件可能合并，数据积压应从队列或环形缓冲区读取。

### 6.5 通知与队列的成本对比

通知通常不需要独立队列对象，也不需要复制任意长度消息，因此：

- 小型唤醒通常比完整消息队列更轻量；
- `eSetBits` 和 `eIncrement` 仍然要执行内核同步和调度相关工作；
- 真正的延迟还包括任务变为就绪、被调度和开始运行；
- ISR 通知延迟依赖目标任务优先级、中断优先级和临界区。

不要只测 API 函数的局部周期，而忽略端到端调度延迟。

### 6.6 实时性瓶颈

任务通知性能容易受以下因素支配：

- 接收任务低于其他就绪任务的优先级；
- 高优先级 ISR 执行时间过长；
- 中断优先级不符合内核约束；
- 任务在通知后仍等待其他锁或队列；
- 通知值承载数据，但处理数据的时间很长；
- 多个发送者频繁抢占同一个任务。

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
通信目标是什么？
|
+-- 唤醒一个明确任务？
|   |
|   +-- 是 -> 任务通知
|
+-- 每次事件都要保存数据和顺序？
|   |
|   +-- 是 -> 消息队列 / 缓冲区
|
+-- 只需等待多个布尔条件？
|   |
|   +-- 是 -> 事件组
|
+-- 要累计“可用资源数量”？
|   |
|   +-- 是 -> 计数信号量
|
+-- 要保护共享资源？
|   |
|   +-- 是 -> 互斥量
|
+-- 一个通知需要广播到多个任务？
    |
    +-- 是 -> 事件组、多个通知或发布订阅设计
```

### 7.2 场景选型

|场景|推荐机制|理由|
|---|---|---|
|DMA 完成后唤醒处理任务|任务通知|单一明确接收者、开销低|
|UART 有数据待处理|门铃通知 + 环形缓冲区|通知只负责唤醒，数据保存在缓冲区|
|每个脉冲都要计数|计数通知或计数信号量|需要累计次数|
|多种 ISR 原因唤醒同一任务|`eSetBits`|多个原因可合并|
|每个 CAN 帧都要按顺序处理|消息队列|通知不保存帧内容和顺序|
|多任务等待系统就绪状态|事件组|通知绑定单一任务|
|单任务等待资源到达|任务通知或信号量|明确目标任务时通知合适|
|单任务最新设定值|`eSetValueWithOverwrite` 或邮箱|允许旧值被新值替代|
|共享 SPI 总线|互斥量|需要资源所有权|

---

## 8. 工程最佳实践

### 8.1 每个通知索引只定义一种主语义

推荐：

```
index 0：事件位
index 1：DMA 完成计数
index 2：任务控制命令值
```

不要让同一个索引在不同代码路径中有时表示位、有时表示计数。

### 8.2 用通知做门铃，数据放在数据结构里

推荐架构：

```
ISR 写 DMA 状态或推进环形缓冲区索引
    -> 任务通知唤醒消费者
    -> 消费者读取实际数据
```

通知不是数据存储区。

### 8.3 选择计数还是合并

- **逐个计数**：`ulTaskNotifyTake(pdFALSE, ...)`。
- **批量读取当前计数**：`ulTaskNotifyTake(pdTRUE, ...)`。
- **合并多个原因**：`eSetBits`。
- **只需知道“有事情”** ：门铃式通知。
- **需要每条消息**：队列。

### 8.4 通知值的清除必须明确

`xTaskNotifyWait()` 的两个清除掩码有不同时间点：

```
clearOnEntry：开始等待之前清除
clearOnExit：成功收到通知并退出时清除
```

清除过多可能丢失尚未处理的位；清除不足可能重复处理旧位。应为每个位指定清除责任。

### 8.5 ISR 和任务 API 不可混用

ISR 使用：

```
xTaskNotifyFromISR()
vTaskNotifyGiveFromISR()
```

任务使用：

```
xTaskNotify()
xTaskNotifyGive()
```

同时检查：

- ISR 优先级；
- 返回值；
- `pxHigherPriorityTaskWoken`；
- `portYIELD_FROM_ISR()`。

### 8.6 生命周期规范

- 接收任务先创建并发布句柄，再允许生产者发送；
- 删除任务前停止所有发送端；
- 任务重启后重新发布新句柄；
- 不能仅凭 `TaskHandle_t != NULL` 证明任务仍有效。

### 8.7 工业级编码规范

- 对通知位使用集中宏定义。
- 使用超时并设计超时恢复。
- 统计通知失败、超时、累积数量和处理耗时。
- 对计数通知做上限或溢出分析。
- 不把指针强转成 `uint32_t` 作为通用消息传输方式。
- 关键路径应在同一位置封装通知的发送和接收语义。
- 通知值必须能解释，不能作为无文档的模块间共享整数。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：认为任务通知可以保存多条消息

错误代码：

```
xTaskNotify(
    worker,
    command_a,
    eSetValueWithOverwrite);

xTaskNotify(
    worker,
    command_b,
    eSetValueWithOverwrite);
```

**根因：** `eSetValueWithOverwrite` 只保留最新的 32 位值，`command_a` 可能被覆盖。

正确方案：

```
if (xQueueSend(
        command_queue,
        &command_a,
        timeout) != pdPASS)
{
    handle_queue_full();
}
```

若只关心最新命令，再使用覆盖邮箱语义，并明确允许覆盖。

**风险影响：** 动作命令、配置更新或安全请求丢失。

### 9.2 错误二：计数通知用清零语义却要求逐个处理

错误代码：

```
uint32_t count =
    ulTaskNotifyTake(pdTRUE, timeout);

/* 错误：只处理一次，但 count 可能大于 1。 */
process_one_event();
```

**根因：** `pdTRUE` 会一次清除当前累计计数。

正确方案一，批量处理：

```
uint32_t count =
    ulTaskNotifyTake(pdTRUE, timeout);

while (count-- > 0U)
{
    process_one_event();
}
```

正确方案二，逐个消费：

```
if (ulTaskNotifyTake(pdFALSE, timeout) > 0U)
{
    process_one_event();
}
```

**风险影响：** 事件计数减少、采样或脉冲丢失。

### 9.3 错误三：把同一通知索引同时用作位和计数

错误代码：

```
xTaskNotify(
    task,
    EVT_DMA_DONE,
    eSetBits);

xTaskNotifyGive(task); /* 同一默认索引上又加计数 */
```

**根因：** 两种操作共同修改同一个 32 位通知值，位模式和计数值可能互相破坏。

正确方案：

- 使用不同通知索引；或
- 使用独立消息队列/信号量；或
- 明确证明复合编码不会冲突。

**风险影响：** 事件位被错误解释为计数，或计数被清位操作消除。

### 9.4 错误四：忽略 `eSetValueWithoutOverwrite` 的失败

错误代码：

```
xTaskNotify(
    worker,
    value,
    eSetValueWithoutOverwrite);
```

**根因：** 目标任务已有未处理通知时，写入可能失败。

正确实现：

```
BaseType_t result = xTaskNotify(
    worker,
    value,
    eSetValueWithoutOverwrite);

if (result != pdPASS)
{
    notify_busy_count++;
    retry_or_reject(value);
}
```

**风险影响：** 发送者以为命令已送达，接收者实际没有新值。

### 9.5 错误五：在 ISR 中调用任务上下文 API

错误代码：

```
void UART_IRQHandler(void)
{
    xTaskNotify(
        g_uart_task,
        EVT_RX,
        eSetBits);
}
```

**根因：** 普通 API 不是 ISR API。

正确实现：

```
void UART_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    xTaskNotifyFromISR(
        g_uart_task,
        EVT_RX,
        eSetBits,
        &woken);

    portYIELD_FROM_ISR(woken);
}
```

同时确认 ISR 优先级符合 FreeRTOS 端口要求。

**风险影响：** 内核列表损坏、断言触发、不可预测的上下文切换。

### 9.6 错误六：把通知用于广播

错误假设：

```
一个任务通知发出后，多个任务都能各自接收。
```

**根因：** 通知状态附属于一个目标任务，不是广播对象。

正确方案：

- 每个接收任务单独发送通知；
- 使用事件组表示共享状态；
- 使用发布/订阅或消息分发任务；
- 对需要的接收者各自维护队列或通知索引。

**风险影响：** 部分任务永久错过状态变化。

### 9.7 错误七：重复通知溢出或错误合并

错误代码：

```
for (;;)
{
    xTaskNotifyGive(task);
    /* 消费者可能长期运行不过来 */
}
```

**根因：** 计数持续累加且没有流量控制。无符号计数最终会回绕；实际到达率高于处理率时，系统会积压。

正确方案：

- 评估生产速率和消费能力；
- 只需门铃时使用可合并通知；
- 需要保留数据时使用有容量和溢出策略的缓冲区；
- 记录最大积压和丢弃情况。

**风险影响：** 事件数量失真、任务长期追赶积压、故障被隐藏。

---

## 10. 多机制组合使用方案

### 10.1 任务通知 + 环形缓冲区

典型 UART 接收：

```
ISR/DMA：
    写入环形缓冲区
    通知接收任务

接收任务：
    被通知后读取当前读写索引
    尽可能排空缓冲区
```

通知可以合并，但数据仍保存在环形缓冲区。接收任务不能把“一次通知”误认为“只有一个字节”或“一帧数据”。

### 10.2 任务通知 + 队列

当消息需要保序时：

```
队列保存消息内容
任务通知用于额外的轻量门铃或任务控制
```

一般队列本身已经能阻塞并唤醒消费者，额外通知往往重复。只有在有明确多通道或调度设计时才加通知，避免产生两份不同步的状态。

### 10.3 任务通知 + 互斥量

通知负责唤醒，互斥量保护共享资源：

```
收到通知
    -> 获取互斥量
    -> 读取或修改共享状态
    -> 释放互斥量
```

通知不提供资源所有权，不能替代互斥量。

### 10.4 完整框架：DMA 门铃 + 环形缓冲区

下例使用任务通知只表示“有数据需要处理”，数据由环形缓冲区保存。平台相关的 DMA 索引和缓存维护函数必须由 BSP 实现。

```
#include <stdint.h>
#include <stdbool.h>
#include "FreeRTOS.h"
#include "task.h"

#define DMA_NOTIFY_INDEX       0U
#define DMA_NOTIFY_DATA_READY  (1UL << 0)

static TaskHandle_t s_rx_task_handle;
static volatile uint32_t s_notify_failures;
static volatile uint32_t s_rx_overruns;

/* BSP 接口：返回 DMA 已写入位置，范围为 [0, RX_RING_SIZE)。 */
extern uint32_t dma_rx_get_write_index(void);
extern bool rx_ring_consume_to(uint32_t write_index);
extern void dma_rx_clear_irq(void);
extern void dma_rx_cache_maintenance(void);
extern void rx_error_recovery(void);

#define RX_RING_SIZE 1024U

static void RxTask(void *argument)
{
    uint32_t last_read_index = 0U;

    (void)argument;

    for (;;)
    {
        uint32_t notify_value = 0U;

        /*
         * 通知是门铃。清除目标位后，读取当前 DMA 写入位置，
         * 并排空当前已有数据。
         */
        BaseType_t notified = xTaskNotifyWaitIndexed(
            DMA_NOTIFY_INDEX,
            0U,
            DMA_NOTIFY_DATA_READY,
            &notify_value,
            pdMS_TO_TICKS(100));

        if (notified == pdFALSE)
        {
            check_rx_timeout_and_dma_health();
            continue;
        }

        dma_rx_cache_maintenance();

        uint32_t write_index = dma_rx_get_write_index();

        /*
         * 平台实现需要识别环形缓冲区是否已覆盖未读数据。
         * 仅靠两个索引无法在所有生产速率下检测满圈；
         * 高可靠系统还需要 DMA 计数、块序号或溢出标志。
         */
        if (!rx_ring_consume_to(write_index))
        {
            s_rx_overruns++;
            rx_error_recovery();
            continue;
        }

        last_read_index = write_index;
        (void)last_read_index;

        /*
         * 处理期间若再次收到通知，下一轮会读到新的写入位置。
         * 若数据吞吐很高，可在任务中循环排空，直到读写追平。
         */
    }
}

void DMA_RX_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    dma_rx_clear_irq();

    BaseType_t result = xTaskNotifyIndexedFromISR(
        s_rx_task_handle,
        DMA_NOTIFY_INDEX,
        DMA_NOTIFY_DATA_READY,
        eSetBits,
        &higher_priority_task_woken);

    if (result != pdPASS)
    {
        s_notify_failures++;
    }

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

设计要点：

- `s_rx_task_handle` 必须在启用 DMA 中断前初始化。
- 通知值只表示“数据可能有变化”，不是字节数量。
- 高频中断可合并通知，不影响环形缓冲区中尚未覆盖的数据。
- DMA 环形缓冲区若可能绕满，仅凭读写索引不足以检测覆盖。
- 若系统启用 D-Cache，需要执行符合芯片要求的 Cache 维护。
- 若每个 DMA 块都必须单独处理，应使用块描述符队列，而不是单个门铃位。

---

## 11. 工业级实际案例分析

以下是常见工业架构模式，不代表某一具体客户项目的实测结果。

### 11.1 案例一：UART DMA 接收处理

**需求：**

- UART 持续接收字节流；
- ISR 不能执行协议解析；
- 接收任务需要及时处理新增数据；
- 数据不能因重复通知被误认为只发生一次。

**架构：**

```
UART DMA 写环形缓冲区
    -> ISR 发任务通知
    -> RX 任务读取 DMA 写入索引
    -> 解析并推进读索引
```

**设计要点：**

- 通知是门铃，不保存数据；
- 任务每次被唤醒后应排空当前积压；
- 通过 DMA 计数器或块序号检测覆盖；
- 通知失败必须计数并设计恢复策略；
- 高优先级数据处理任务应避免被长时间低优先级任务阻塞。

### 11.2 案例二：ADC 采样完成计数

**需求：**

- ADC 每完成一个采样块触发中断；
- 算法任务需要知道待处理块数；
- 每个块都有独立数据缓冲区。

**架构：**

```
DMA 块完成 ISR
    -> 发布块描述符到 Queue
    -> 可选地通知算法任务

算法任务
    -> 接收块描述符
    -> 处理数据
    -> 归还缓冲区
```

若只发送通知计数而没有块描述符，任务知道“完成了几次”，但不知道：

- 每次对应哪块缓冲区；
- 缓冲区是否被覆盖；
- 每块的时间戳；
- 哪些块需要归还。

因此数据块必须由队列或固定缓冲池描述符承载。通知只作为唤醒提示。

### 11.3 案例三：单一故障管理任务

**需求：**

- 多个模块检测故障；
- 由一个故障任务统一处理；
- 同类故障只需合并为“至少有故障待处理”；
- 故障码和时间戳必须记录。

**架构：**

```
故障检测模块
    -> 将 fault record 写入有界队列
    -> 通知故障管理任务

故障管理任务
    -> 被通知后排空 fault queue
    -> 记录日志、执行安全策略
```

**设计要点：**

- 队列保存故障记录；
- 任务通知负责快速唤醒；
- 若队列本身已用于阻塞接收，额外通知可能不必要；
- 若要合并同类故障，合并规则必须按故障码和级别定义；
- 队列满时，最高等级故障应有保留策略，不能与普通诊断信息竞争同一容量。

---

## 12. 高频问题深度答疑

### 问题一：任务通知比信号量快吗？

常见 FreeRTOS 单任务唤醒路径中，任务通知通常更轻量，因为不需要独立信号量对象，也能直接更新目标任务 TCB 中的状态。但实际效果受：

- FreeRTOS 版本；
- 端口临界区实现；
- Trace 配置；
- 任务优先级；
- ISR 优先级；
- 调度器负载；

影响。工程上应在目标板测量，不应把“通常较轻量”理解为固定倍数。

### 问题二：任务通知可以当队列用吗？

不能替代通用队列。通知值只有有限位宽，没有多条消息存储、消息长度和 FIFO 历史。

它可以在严格定义下承载：

- 32 位状态值；
- 位集合；
- 事件计数；
- 单槽最新值。

必须逐条处理且每条带数据时，用队列或缓冲区。

### 问题三：为什么通知值为零时任务仍可能收到通知？

因为通知状态和通知值是分开的。例如使用 `eNoAction` 可以设置“通知已到达”状态而不改变通知值。

因此判断收到通知应看 API 返回值，而不是只看通知值是否非零。

### 问题四：多个发送者能否通知同一个任务？

可以，但必须共同约定：

- 使用哪个通知索引；
- 使用哪种 Action；
- 哪些位分别表示什么；
- 是否允许覆盖；
- 谁负责清除；
- 多个来源是否会冲突。

若发送者传递需要保序的数据，应使用队列。

### 问题五：目标任务尚未等待时，通知会丢吗？

通常不会因为任务当时未等待就自动丢失；通知状态和值会保留，任务稍后等待时可观察到。但不同 Action 的合并、覆盖、计数和拒绝行为不同，必须根据语义选择。

### 问题六：任务通知可以在多个任务之间广播吗？

不能。一次通知针对一个目标任务句柄。如果多个任务都需要知道状态，应：

- 对每个任务分别通知；
- 使用事件组；
- 使用发布/订阅；
- 使用共享状态加版本号；
- 将消息复制到多个订阅者的队列。

---

## 13. 课程核心总结

### 核心要点

1. **任务通知是直接发送给指定任务的同步状态。**
2. 通知由“通知状态”和“通知值”组成，二者不能混为一谈。
3. `xTaskNotifyGive()` 和 `ulTaskNotifyTake()` 适合计数或门铃语义。
4. `eSetBits` 适合合并多个事件原因，但重复相同位不会累计次数。
5. `eSetValueWithOverwrite` 是单槽覆盖，不是消息队列。
6. `FromISR` API 必须配合 ISR 优先级约束和必要的上下文切换请求。
7. 通知值有限，不能替代大数据消息传输。
8. 任务通知不是广播机制。
9. 通知可作为数据缓冲区的门铃，实际数据应保存在队列或环形缓冲区。
10. 同一个通知索引必须有清晰、统一的语义。

### 性能排序

针对“唤醒一个明确任务”的场景，常见实现中通常是：

```
任务通知
    >
专用二值同步对象
    >
完整队列消息
```

这是**典型开销趋势**，不是固定周期或跨平台性能承诺。若传输数据、保留历史或需要多接收者，语义正确性优先于微小的 API 开销差异。

### 通用选型结论

```
唤醒一个指定任务：
    任务通知

每次事件都要计数：
    计数通知 / 计数信号量

多个事件原因合并：
    eSetBits

每条消息都要保留：
    Queue / MessageBuffer

多个任务等待共享状态：
    Event Group

共享资源保护：
    Mutex

DMA/UART 高频数据：
    环形缓冲区或描述符队列 + 任务通知门铃
```

---

## 14. 快速参考速查表

### 14.1 场景与 API

|需求|常用 API|
|---|---|
|任务发送通知|`xTaskNotify()`|
|任务发送计数通知|`xTaskNotifyGive()`|
|等待通知并读值|`xTaskNotifyWait()`|
|计数方式等待|`ulTaskNotifyTake()`|
|ISR 发送通知值|`xTaskNotifyFromISR()`|
|ISR 发送计数通知|`vTaskNotifyGiveFromISR()`|
|等待指定索引|`xTaskNotifyWaitIndexed()`|
|指定索引计数接收|`ulTaskNotifyTakeIndexed()`|

### 14.2 Action 速查

|Action|结果|
|---|---|
|`eNoAction`|设置通知状态，不修改值|
|`eSetBits`|`value|
|`eIncrement`|`value++`|
|`eSetValueWithOverwrite`|`value = input`|
|`eSetValueWithoutOverwrite`|只有无待处理通知时才写入|

### 14.3 常见接收模式

|模式|发送|接收|
|---|---|---|
|纯唤醒|`xTaskNotify(..., eNoAction)`|`xTaskNotifyWait()`|
|事件位|`xTaskNotify(..., eSetBits)`|`xTaskNotifyWait()`|
|计数逐个消费|`xTaskNotifyGive()`|`ulTaskNotifyTake(pdFALSE, ...)`|
|批量取当前计数|`xTaskNotifyGive()`|`ulTaskNotifyTake(pdTRUE, ...)`|
|最新值覆盖|`xTaskNotify(..., eSetValueWithOverwrite)`|`xTaskNotifyWait()`|

### 14.4 关键约束表

|项目|约束|
|---|---|
|接收者|指定任务|
|单索引载荷|32 位通知值|
|通知历史|不保存任意多条有序消息|
|重复位|合并，不计数|
|多接收者|不自动广播|
|ISR|使用 `FromISR` API|
|数据结构|使用队列或缓冲区|
|计数|分析溢出和生产消费速率|
|索引|发送和接收双方必须一致|
|任务删除|删除前停止所有发送端|

---

## 15. 学习效果自检

- [ ]  能区分通知状态与通知值。
- [ ]  能解释任务通知为什么不是独立内核对象。
- [ ]  能使用通知实现任务唤醒。
- [ ]  能区分门铃、计数、位集合和单值覆盖。
- [ ]  能正确使用 `ulTaskNotifyTake(pdTRUE)` 与 `pdFALSE`。
- [ ]  能说明重复设置同一通知位不会累计次数。
- [ ]  能说明通知不能广播，也不能保存任意长度消息。
- [ ]  能正确使用 ISR 版本 API。
- [ ]  能解释 `eSetValueWithoutOverwrite` 失败后的处理方式。
- [ ]  能为通知数组设计索引分配表。
- [ ]  能设计 DMA 数据环形缓冲区加任务通知的方案。
- [ ]  能处理任务句柄的初始化、更新和销毁。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：任务通知二值门铃

- 生产者调用 `xTaskNotifyGive()`；
- 消费者调用 `ulTaskNotifyTake(pdTRUE, timeout)`；
- 让生产者快于消费者；
- 观察批量清除后的合并行为；
- 验证这是否符合业务语义。

#### 任务二：计数通知

- ISR 或任务每发生一次事件就计数；
- 消费者使用 `ulTaskNotifyTake(pdFALSE, ...)`；
- 统计最大待处理数和处理耗时；
- 注入消费者长期阻塞；
- 评估计数溢出和系统稳定性。

#### 任务三：多事件位

- 为 UART、DMA、故障和配置更新分配不同位；
- 使用 `eSetBits`；
- 消费者通过 `xTaskNotifyWait()` 读取；
- 验证不同生产者同时设置不同位时是否正确合并；
- 验证清除掩码不会误清其他待处理状态。

#### 任务四：通知数组隔离语义

- 索引 0 用于事件位；
- 索引 1 用于计数通知；
- 使用对应 indexed API；
- 测量任务 TCB RAM 增量；
- 检查传统 API 默认索引，避免误用索引 0。

#### 任务五：通知门铃与 DMA 环形缓冲区

- DMA 写入环形缓冲区；
- ISR 只发送门铃；
- 任务收到后排空数据；
- 注入任务调度延迟和 DMA 覆盖；
- 验证通知合并时数据仍可完整恢复。

### 16.2 性能测试方法

可使用 DWT 测量局部 API 执行周期：

```
uint32_t start = DWT->CYCCNT;

BaseType_t result =
    xTaskNotifyGive(g_worker_task);

uint32_t cycles =
    DWT->CYCCNT - start;

if (result != pdPASS)
{
    notify_send_failure();
}

record_cycle_sample(cycles);
```

这只能反映调用路径的一部分。端到端延迟应通过 GPIO 或 Trace 测量：

```
发送方拉高 GPIO
    -> 发送任务通知
    -> 接收任务开始运行时拉高另一个 GPIO
```

分别测试：

- 目标任务阻塞等待；
- 目标任务未等待；
- 目标任务低于其他就绪任务；
- ISR 发送并触发切换；
- 单次通知；
- 高频计数通知；
- 单位通知值大小和 Action；
- 不同 Trace、断言和优化配置。

记录：

```
最小、平均、P99、P99.9 和最大观察值
发送到任务开始运行的延迟
通知失败数
任务处理积压数
计数高水位
超时次数
中断和临界区干扰
```

在 CPU 频率 `fCPU` 下，周期换算为：

```
T = cycles / fCPU
```

应同时区分：

```
API 执行时间
任务唤醒延迟
端到端处理延迟
```

三者不是同一个指标。

### 16.3 进阶学习方向

- 阅读 FreeRTOS `tasks.c` 中的通知发送、等待和计数消费路径。
- 研究通知状态与通知值的生命周期。
- 评估不同 FreeRTOS 版本的通知数组支持和 API 差异。
- 分析 `configTASK_NOTIFICATION_ARRAY_ENTRIES` 对 TCB RAM 的影响。
- 研究 ISR 优先级约束、内核临界区和直接任务唤醒。
- 设计 DMA 描述符队列与任务通知的组合。
- 研究事件合并、背压、计数上限和故障恢复。
- 将“任务通知是门铃，队列或缓冲区是数据载体”落实为模块接口规范。