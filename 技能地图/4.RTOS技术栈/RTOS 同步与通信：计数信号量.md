
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解计数信号量的**计数模型、资源模型和事件模型**。
- 区分计数信号量与：
    - 二值信号量；
    - 互斥锁；
    - 任务通知；
    - 消息队列；
    - 事件标志组。
- 理解计数信号量的两个核心参数：
    - 最大计数值；
    - 当前计数值。
- 理解计数信号量**不携带用户数据，也不具备所有权和优先级继承能力**。
- 理解计数信号量在“资源池”和“事件累计”两类场景中的不同语义。

### 1.2 掌握

能够：

- 使用 FreeRTOS 创建、释放、获取计数信号量。
- 在 ISR 中使用 `xSemaphoreGiveFromISR()`。
- 正确设置最大计数值和初始计数值。
- 处理计数溢出、获取超时、资源耗尽和事件丢失。
- 设计 DMA 缓冲块、连接资源池、空闲对象池等同步方案。
- 使用 `uxQueueMessagesWaiting()` 和 `uxQueueSpacesAvailable()` 进行运行时观测。

### 1.3 精通

能够：

- 从 FreeRTOS 队列内核实现角度分析计数信号量。
- 判断“计数信号量”应表达资源还是事件。
- 分析生产速率、消费速率、最大积压量和资源池容量之间的关系。
- 识别错误释放、计数溢出、事件合并、资源泄漏和优先级反转问题。
- 根据实时性、RAM、吞吐量和可靠性约束选择计数信号量、队列或任务通知。

### 1.4 能够设计

能够设计：

- ISR 事件累计到任务批量消费的架构。
- DMA 多缓冲块处理架构。
- 固定块内存池和资源计数管理方案。
- 受限连接池、文件描述符池、事务槽位管理方案。
- 带计数守恒、超时恢复、诊断统计的工业级同步组件。

---

## 2. 前置要求

### 2.1 知识要求

- C 语言：
    - 无符号整数；
    - 原子性与竞态条件；
    - `volatile`；
    - 结构体和指针；
    - 整数溢出。
- MCU 基础：
    - 中断上下文；
    - NVIC 优先级；
    - DMA；
    - 临界区；
    - Cache 一致性。
- RTOS 基础：
    - 任务状态；
    - 阻塞与唤醒；
    - 优先级调度；
    - Tick 超时；
    - ISR 与任务上下文区别。
- FreeRTOS 基础：
    - 队列；
    - 二值信号量；
    - `FromISR` API；
    - `configASSERT()`；
    - 静态和动态内核对象。

### 2.2 技能要求

- 能阅读 `queue.c` 中队列和信号量相关代码。
- 能使用示波器或逻辑分析仪测量任务唤醒延迟。
- 能查看任务运行时统计和堆使用情况。
- 能定位任务永久阻塞、计数失衡和 ISR API 使用错误。
- 能够实现环形缓冲区、固定块内存池或 DMA 多缓冲机制。

---

## 3. 技术概述

## 3.1 计数信号量的定义

计数信号量维护一个范围受限的整数：

```
0 <= current_count <= max_count
```

其中：

- `max_count`：最大计数值；
- `current_count`：当前可用信号或资源数量。

两个基本操作：

```
Give：
    current_count = current_count + 1

Take：
    如果 current_count > 0：
        current_count = current_count - 1
    否则：
        阻塞或立即失败
```

计数信号量能够表达：

> **当前有多少个可消费事件，或者有多少个可用资源。**

---

## 3.2 两种核心语义

### 3.2.1 事件计数语义

生产者每产生一次事件，就执行一次 `Give`：

```
ISR 产生事件
    -> Give
ISR 再产生事件
    -> Give
任务 Take
    -> 消费一个事件
任务再 Take
    -> 消费另一个事件
```

典型用途：

- DMA 缓冲块完成次数；
- UART 接收帧数量；
- 传感器采样完成次数；
- 定时器周期到期次数；
- 外部脉冲累计。

### 3.2.2 资源计数语义

信号量计数值代表可用资源数量：

```
初始化时 Give N 次
任务获取资源：
    Take 一次
任务释放资源：
    Give 一次
```

典型用途：

- 固定大小内存块池；
- 网络连接槽位；
- DMA 通道数量；
- 文件描述符；
- 数据库事务槽位；
- 硬件缓冲区数量。

---

## 3.3 计数信号量的抽象模型

```
typedef struct
{
    uint32_t max_count;
    uint32_t current_count;
} counting_semaphore_t;
```

基本不变量：

```
0 <= current_count <= max_count
```

事件模式：

```
生产者：Give
消费者：Take
```

资源模式：

```
初始化：Give N 次
资源获取：Take
资源归还：Give
```

在资源模式下，计数值表示资源状态；在事件模式下，计数值表示待处理事件积压量。

---

## 3.4 计数信号量不是其他机制的替代品

|机制|主要语义|
|---|---|
|计数信号量|多个同质资源或累计事件|
|二值信号量|一个“发生过”的事件|
|互斥锁|共享资源所有权|
|消息队列|数据传输和排队|
|事件标志组|多个状态位的组合|
|任务通知|单个任务的高性能通知|
|内存池|实际保存固定大小资源|

核心结论：

> **计数信号量只记录“数量”，不记录“对象是谁、数据是什么、顺序是什么”。**

如果每个事件还需要携带：

```
事件类型
时间戳
数据长度
缓冲区地址
错误码
```

则应使用消息队列或环形缓冲区。

---

## 4. 核心特性横向对比

## 4.1 同步机制对比

|维度|计数信号量|二值信号量|互斥锁|消息队列|任务通知|
|---|---|---|---|---|---|
|最大计数|大于 1|1|1|队列长度|依赖通知模式|
|是否累计事件|是|否|否|是|可选|
|是否传递数据|否|否|否|是|可传递整数/位|
|是否有所有权|否|否|是|否|否|
|优先级继承|否|否|是|否|否|
|ISR 释放|支持|支持|通常不支持|支持|支持|
|多个消费者|支持|支持但语义有限|不适用|支持|固定绑定任务|
|RAM 开销|中|中|中|高|极低|
|适合资源池|**好**|差|差|可用|一般|
|适合事件累计|**好**|差|不适用|好|好|
|保存事件顺序|否|否|不适用|**是**|通常否|

---

## 4.2 事件计数与资源计数对比

|项目|事件计数模式|资源计数模式|
|---|---|---|
|初始化计数|通常为 0|通常为资源总数|
|Give 含义|新事件产生|资源归还|
|Take 含义|消费一个事件|获得一个资源|
|计数溢出风险|生产过快|错误释放或重复归还|
|典型问题|事件积压、处理不及时|资源泄漏、计数失真|
|是否允许丢失|取决于业务|通常不允许|
|配套对象|环形缓冲区、事件元数据|内存池、对象池|

---

## 4.3 不同实现方式对比

|实现|优点|缺点|典型场景|
|---|---|---|---|
|FreeRTOS 计数信号量|通用、可阻塞、支持 ISR|内存和路径开销高于通知|通用 RTOS 应用|
|任务通知计数模式|快、RAM 极低|只能绑定一个任务|单生产者/单消费者|
|队列长度为 N|可传数据、保序|RAM 开销高|事件带参数|
|原子计数器 + 任务通知|性能高、结构灵活|需要自行处理竞态|高性能驱动|
|Linux semaphore|内核通用|调度开销较大|内核线程、设备驱动|
|Zephyr `k_sem`|API 直接|依赖 Zephyr|Zephyr 项目|

---

## 5. 底层原理与功能特性深度解析

以下以 FreeRTOS 为主。

## 5.1 FreeRTOS 中计数信号量的实现

FreeRTOS 的计数信号量同样基于队列机制实现。

典型创建接口：

```
SemaphoreHandle_t xSemaphoreCreateCounting(
    UBaseType_t uxMaxCount,
    UBaseType_t uxInitialCount);
```

内部可以抽象为：

```
xQueueGenericCreate(
    uxMaxCount,
    semSEMAPHORE_QUEUE_ITEM_LENGTH,
    queueQUEUE_TYPE_COUNTING_SEMAPHORE);
```

关键参数：

```
队列长度 = uxMaxCount
队列单元大小 = 0
队列类型 = counting semaphore
当前消息数 = uxInitialCount
```

计数信号量的“消息”并不是真正的用户数据，而是通过：

```
uxMessagesWaiting
```

表示当前计数。

可抽象为：

```
typedef struct QueueDefinition
{
    volatile UBaseType_t uxMessagesWaiting;
    UBaseType_t uxLength;
    UBaseType_t uxItemSize;

    List_t xTasksWaitingToSend;
    List_t xTasksWaitingToReceive;

    /* 其他队列控制字段 */
} Queue_t;
```

核心映射关系：

```
current_count = uxMessagesWaiting
max_count     = uxLength
```

---

## 5.2 创建计数信号量

### 动态创建

```
SemaphoreHandle_t xSemaphoreCreateCounting(
    UBaseType_t uxMaxCount,
    UBaseType_t uxInitialCount);
```

示例：

```
static SemaphoreHandle_t g_dma_block_sem;

void dma_sync_init(void)
{
    g_dma_block_sem = xSemaphoreCreateCounting(
        8U,  /* 最大积压 8 个 DMA 块 */
        0U); /* 初始没有完成块 */

    configASSERT(g_dma_block_sem != NULL);
}
```

参数约束：

```
uxMaxCount > 0
uxInitialCount <= uxMaxCount
```

### 静态创建

```
static StaticSemaphore_t g_sem_storage;
static SemaphoreHandle_t g_sem;

void event_counter_init(void)
{
    g_sem = xSemaphoreCreateCountingStatic(
        16U,
        0U,
        &g_sem_storage);

    configASSERT(g_sem != NULL);
}
```

注意：不同 FreeRTOS 版本的静态创建函数声明可能略有差异，必须以当前工程头文件为准。常见形式为：

```
xSemaphoreCreateCountingStatic(
    uxMaxCount,
    uxInitialCount,
    pxStaticSemaphore);
```

生产系统建议在编译阶段确认接口原型，不要凭经验复制不同版本的 API。

---

## 5.3 获取计数信号量

任务调用：

```
xSemaphoreTake(
    g_event_count,
    timeout);
```

简化逻辑：

```
BaseType_t xQueueSemaphoreTake(
    QueueHandle_t xQueue,
    TickType_t xTicksToWait)
{
    for (;;)
    {
        taskENTER_CRITICAL();

        if (xQueue->uxMessagesWaiting > 0U)
        {
            xQueue->uxMessagesWaiting--;

            taskEXIT_CRITICAL();

            return pdPASS;
        }

        if (xTicksToWait == 0U)
        {
            taskEXIT_CRITICAL();

            return errQUEUE_EMPTY;
        }

        vTaskPlaceOnUnorderedEventList(
            &xQueue->xTasksWaitingToReceive,
            xTicksToWait);

        taskEXIT_CRITICAL();

        portYIELD_WITHIN_API();
    }
}
```

真正源码还需要处理：

- 任务超时；
- 调度器状态；
- 互斥锁优先级继承分支；
- 时间溢出；
- 阻塞列表；
- 中断并发；
- 删除对象保护。

关键逻辑是：

```
计数 > 0：
    立即递减并成功返回

计数 == 0：
    timeout == 0：立即失败
    timeout > 0：进入阻塞态
```

---

## 5.4 释放计数信号量

任务上下文：

```
xSemaphoreGive(g_event_count);
```

ISR 上下文：

```
BaseType_t woken = pdFALSE;

xSemaphoreGiveFromISR(
    g_event_count,
    &woken);

portYIELD_FROM_ISR(woken);
```

简化后的释放逻辑：

```
BaseType_t xQueueGenericSend(
    QueueHandle_t xQueue,
    const void *pvItemToQueue,
    TickType_t xTicksToWait,
    BaseType_t xCopyPosition)
{
    taskENTER_CRITICAL();

    if (xQueue->uxMessagesWaiting < xQueue->uxLength)
    {
        xQueue->uxMessagesWaiting++;

        if (listLIST_IS_EMPTY(
                &xQueue->xTasksWaitingToReceive) == pdFALSE)
        {
            /*
             * 唤醒一个等待任务。
             * 实际唤醒哪个任务由等待列表排序和调度策略决定。
             */
            xTaskRemoveFromUnorderedEventList(
                &xQueue->xTasksWaitingToReceive,
                queueSEND_TO_BACK);
        }

        taskEXIT_CRITICAL();

        return pdPASS;
    }

    taskEXIT_CRITICAL();

    return errQUEUE_FULL;
}
```

对于计数信号量：

```
Give 成功：count + 1
Give 失败：count 已经达到 max_count
```

这与二值信号量的主要区别是：

```
二值信号量最大计数固定为 1
计数信号量最大计数由创建参数决定
```

---

## 5.5 计数上限与释放失败

计数信号量不是无限计数器。

```
SemaphoreHandle_t sem =
    xSemaphoreCreateCounting(3U, 0U);
```

连续释放：

```
第 1 次 Give：成功，count = 1
第 2 次 Give：成功，count = 2
第 3 次 Give：成功，count = 3
第 4 次 Give：失败，count 仍为 3
```

必须检查返回值：

```
if (xSemaphoreGive(g_sem) != pdPASS)
{
    diagnostic_counter_increment(
        DIAG_COUNTING_SEM_OVERFLOW);

    fault_manager_report(
        FAULT_COUNTING_SEM_OVERFLOW);
}
```

在 ISR 中：

```
BaseType_t woken = pdFALSE;

if (xSemaphoreGiveFromISR(g_sem, &woken) != pdPASS)
{
    /*
     * ISR 中不要执行复杂故障处理。
     * 记录最小状态，交给任务处理。
     */
    g_isr_overflow_flag = true;
}

portYIELD_FROM_ISR(woken);
```

注意：

> **计数溢出通常不是“正常状态”，而是生产速率超过系统设计能力、最大容量配置错误或消费者失效的信号。**

---

## 5.6 计数信号量与事件积压

设：

```
P(t)：截至时刻 t 产生的事件总数
C(t)：截至时刻 t 消费的事件总数
Q(t)：当前信号量计数
```

理想情况下：

```
Q(t) = P(t) - C(t)
```

并且必须满足：

```
0 <= Q(t) <= Qmax
```

如果平均生产速率为：

```
λp = 事件产生速率
```

平均消费速率为：

```
λc = 事件消费速率
```

则：

```
λp < λc
```

是长期稳定运行的必要条件。

如果：

```
λp > λc
```

则积压量持续增加，最终出现：

```
Q(t) = Qmax
```

之后新的事件无法计数，发生溢出或丢事件。

---

## 5.7 计数信号量与资源守恒

对于资源池，设资源总数为 `N`：

```
available_count + allocated_count = N
```

其中：

```
available_count = 计数信号量当前计数
allocated_count = 当前被任务持有的资源数
```

每次获取资源：

```
available_count--
allocated_count++
```

每次归还资源：

```
available_count++
allocated_count--
```

任何情况下都必须满足：

```
0 <= available_count <= N
0 <= allocated_count <= N
```

如果出现：

```
available_count > N
```

说明存在：

- 重复释放；
- 同一个资源被多个路径归还；
- 初始化重复；
- 异常路径释放次数错误。

如果出现：

```
available_count < 0
```

则通常意味着信号量和资源实际状态已经失配，或者代码存在未受保护的独立计数器错误。

---

## 5.8 ISR 使用规则

ISR 中可以释放计数信号量：

```
void EXTI_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    exti_clear_pending();

    if (xSemaphoreGiveFromISR(
            g_event_count,
            &higher_priority_task_woken) != pdPASS)
    {
        /*
         * 计数达到上限。
         * 记录溢出，不在 ISR 中执行复杂处理。
         */
        g_event_overflow_count++;
    }

    portYIELD_FROM_ISR(
        higher_priority_task_woken);
}
```

ISR 中通常不能获取计数信号量：

```
/* 不推荐或不允许 */
xSemaphoreTakeFromISR(...);
```

原因：

- ISR 不能阻塞；
- 计数为 0 时无法等待；
- FreeRTOS 通常不提供通用的信号量 ISR Take 语义；
- ISR 资源获取应使用无阻塞硬件或原子结构。

如果 ISR 需要尝试获取某种资源，应设计为：

```
任务提前分配资源
ISR 只提交状态
任务完成资源管理
```

---

## 5.9 计数信号量不保证 FIFO 业务顺序

计数信号量只保留数量：

```
count = 3
```

它不知道三个事件的：

- 产生时间；
- 来源；
- 类型；
- 数据内容；
- 优先级。

如果业务要求严格顺序，应使用：

- 消息队列；
- 时间戳环形队列；
- 描述符队列；
- 带序号的事件结构。

例如：

```
typedef struct
{
    uint32_t sequence;
    uint32_t timestamp;
    uint16_t type;
    uint16_t length;
} event_record_t;
```

此类数据应进入队列，而不是只增加信号量计数。

---

## 5.10 多生产者和多消费者

### 多生产者

多个 ISR 或任务可以对同一个计数信号量执行 `Give`：

```
ISR A -> Give
ISR B -> Give
Task C -> Take
```

适合表达：

```
多个来源都产生同一种待处理工作
```

但如果需要区分来源，则还需要：

- 原子事件位；
- 来源队列；
- 事件记录；
- 独立计数器。

### 多消费者

多个任务可以等待同一个计数信号量：

```
count = 5
Task A Take -> count = 4
Task B Take -> count = 3
```

这种方式适合：

```
多个同质工作者竞争消费工作令牌
```

但不适合要求：

```
指定事件必须由指定任务处理
```

因为计数信号量不携带任务路由信息。

---

## 6. 性能量化分析

以下数据以典型平台为参考：

```
MCU：STM32F407
CPU：Cortex-M4F，168 MHz
编译器：arm-none-eabi-gcc 12.x
优化：-O2
RTOS：FreeRTOS 10.x
Tick：1 kHz
测量方式：DWT CYCCNT + GPIO
Cache：无 D-Cache
```

实际结果会受到：

- FreeRTOS 配置；
- 编译器版本；
- 临界区实现；
- 端口；
- 任务优先级；
- 中断嵌套；
- 链接位置；

等因素影响。

## 6.1 内存开销

计数信号量底层是长度为 `max_count`、单元大小为 0 的队列。

因此主要内存开销来自队列控制块，而不是每一个计数项的数据存储。

典型值：

|对象|典型 RAM|
|---|---|
|动态计数信号量控制块|约 76~100 字节|
|堆管理额外开销|约 8~16 字节|
|静态计数信号量|约 80~100 字节|
|单个计数项数据区|通常为 0 字节|

重要结论：

> 将最大计数从 8 增加到 1024，通常不会像消息队列那样线性增加用户数据区，但会受到计数类型和实现限制。真正需要保存每个事件信息时，队列或环形缓冲区仍需要按事件数量分配存储。

---

## 6.2 典型 CPU 开销

参考测量值：

|操作|典型周期|168 MHz 下时间|
|---|---|---|
|`xSemaphoreGive()`，无等待任务|300~550 cycles|1.8~3.3 μs|
|`xSemaphoreTake()`，计数大于 0|250~450 cycles|1.5~2.7 μs|
|`xSemaphoreGiveFromISR()`，无切换|250~500 cycles|1.5~3.0 μs|
|Give 并唤醒高优先级任务|700~1500 cycles|4.2~8.9 μs|
|直接任务通知计数模式|150~350 cycles|0.9~2.1 μs|

换算公式：

```
T = cycles / fCPU
```

例如：

```
1200 cycles / 168 MHz
≈ 7.14 μs
```

---

## 6.3 吞吐量估算

如果一次事件的处理路径平均消耗：

```
Ttake = 2.5 μs
Tprocess = 20 μs
```

则理论单任务处理上限约为：

```
Rmax = 1 / (Ttake + Tprocess)
     = 1 / 22.5 μs
     ≈ 44.4 k events/s
```

但工程设计不应按理论极限运行，应预留：

- 其他任务；
- 中断；
- cache miss；
- 日志；
- 临界区；
- 峰值抖动；
- 故障处理；

建议长期平均负载控制在理论能力的：

```
50%~70%
```

对于硬实时任务，还要根据最坏执行时间而不是平均执行时间计算。

---

## 6.4 最大积压量计算

设：

```
生产速率：λp
消费速率：λc
突发持续时间：Tb
```

当：

```
λp > λc
```

突发期间需要的最小计数容量近似为：

```
Qburst >= (λp - λc) × Tb
```

例如：

```
生产速率：1000 events/s
消费速率：600 events/s
突发持续：200 ms
```

则积压量：

```
Qburst >= (1000 - 600) × 0.2
        = 80
```

还需要加上：

- 调度抖动裕量；
- 中断禁用时间；
- 任务启动延迟；
- 突发峰值误差；
- 故障恢复期间的积压。

工程上可选择：

```
max_count = 128 或更高
```

而不是刚好配置为 80。

---

## 6.5 计数溢出概率和故障窗口

假设消费者短时停止 `Tstop`，生产速率为 `λp`：

```
积压量 = λp × Tstop
```

例如：

```
生产速率：5 k events/s
消费者最长停止：10 ms
```

则最少需要：

```
Qmin = 5000 × 0.01 = 50
```

如果 `max_count < 50`，消费者停止期间就可能溢出。

---

## 6.6 Tick 超时精度

若：

```
configTICK_RATE_HZ = 1000
```

则：

```
Tick 周期 = 1 ms
```

调用：

```
xSemaphoreTake(
    g_sem,
    pdMS_TO_TICKS(10));
```

实际超时会受到 Tick 边界量化影响，典型约为：

```
9~11 ms
```

如果事件处理要求微秒级超时，计数信号量不应承担定时器功能，应使用：

- 硬件定时器；
- 高精度时间戳；
- DWT；
- GPT；
- 硬件超时机制。

---

## 6.7 性能瓶颈分析

常见瓶颈不是 `Give` 和 `Take` 本身，而是：

1. **消费者处理能力不足**
    
    - `λc < λp`；
    - 计数持续增加；
    - 最终达到最大值。
2. **事件过于频繁地触发上下文切换**
    
    - 每个事件都立即唤醒任务；
    - 任务频繁抢占；
    - 实际有效处理时间下降。
3. **使用计数信号量却需要事件数据**
    
    - 计数只能告诉“有几个”；
    - 无法恢复事件来源和参数。
4. **多个消费者竞争导致缓存和调度抖动**
    
    - 工作窃取不均衡；
    - 任务优先级配置不合理；
    - 低优先级消费者长期得不到执行。
5. **错误的最大计数**
    
    - 太小导致突发期间丢事件；
    - 太大掩盖消费者性能不足。

---

## 6.8 优化手段与收益

|优化手段|预期效果|
|---|---|
|使用任务通知计数模式|降低对象 RAM 和同步路径开销|
|批量 Take 后处理|减少上下文切换和调度次数|
|DMA 替代逐字节中断|降低事件产生频率|
|多缓冲或环形缓冲|吸收短时突发|
|增加消费者任务优先级|降低积压增长速度|
|处理事件时批量读取数据|提高缓存和总线效率|
|计数与事件描述符队列组合|同时保留数量和数据|
|统计高水位|及时发现容量不足|
|在溢出时记录故障|防止静默丢事件|

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
需要同步或通信？
|
+-- 是否需要传递事件数据？
|   |
|   +-- 是
|   |   |
|   |   +-- 是否要求事件保序？
|   |       |
|   |       +-- 是 -> 消息队列/环形缓冲区
|   |       +-- 否 -> 指针队列或任务通知 + 数据区
|   |
|   +-- 否
|       |
|       +-- 是否需要累计多个事件？
|       |   |
|       |   +-- 是
|       |       |
|       |       +-- 接收任务是否固定为一个？
|       |           |
|       |           +-- 是 -> 任务通知计数模式
|       |           +-- 否 -> 计数信号量
|       |
|       +-- 否
|           |
|           +-- 是否只需要表达“事件发生过”？
|               |
|               +-- 是 -> 二值信号量
|               +-- 否
|                   |
|                   +-- 是否管理同质资源数量？
|                       |
|                       +-- 是 -> 计数信号量 + 资源池
|                       +-- 否 -> 重新定义同步语义
```

## 7.2 典型场景选型

|需求|推荐方案|理由|
|---|---|---|
|多次 DMA 块完成，块块都要处理|计数信号量或通知计数|保留完成数量|
|UART 每帧到达，帧内容需要解析|队列/环形缓冲区 + 计数信号量|信号量只统计帧数，缓冲区保存数据|
|固定内存块池|计数信号量 + 内存池|计数代表空闲块数量|
|多个连接槽位|计数信号量|计数代表可用槽位|
|单任务累计事件|任务通知计数模式|性能和内存更优|
|多任务竞争相同工作项|计数信号量|多个消费者可以竞争 Take|
|多个条件组合|事件标志组|需要按位表达状态|
|SPI 总线访问|互斥锁|需要所有权和优先级继承|
|事件必须携带时间戳|消息队列|计数信号量无法保存参数|

---

## 8. 工程最佳实践

## 8.1 明确计数语义

每个计数信号量必须明确其用途：

```
typedef enum
{
    COUNTING_SEM_EVENT,
    COUNTING_SEM_RESOURCE
} counting_sem_semantics_t;
```

命名中体现语义：

```
adc_completed_block_count
free_dma_buffer_count
available_connection_count
pending_rx_frame_count
```

避免：

```
sem_count
counter_sem
event_sem
```

---

## 8.2 建立计数守恒关系

事件模式：

```
产生事件总数 - 消费事件总数 = 当前积压量 + 丢失事件数
```

资源模式：

```
空闲资源数 + 已分配资源数 = 资源总数
```

建议记录：

```
typedef struct
{
    uint32_t give_count;
    uint32_t take_count;
    uint32_t overflow_count;
    uint32_t timeout_count;
    uint32_t high_watermark;
} counting_sem_stats_t;
```

---

## 8.3 配置最大计数时使用容量预算

不要凭经验设置：

```
xSemaphoreCreateCounting(10, 0);
```

应根据以下数据计算：

- 平均生产速率；
- 峰值生产速率；
- 最大突发时间；
- 消费者最坏执行时间；
- 任务最长阻塞时间；
- 中断禁用窗口；
- 系统启动和恢复时间；
- 可接受丢失量。

建议：

```
max_count >= 计算积压量 + 调度裕量 + 故障裕量
```

---

## 8.4 释放操作必须检查返回值

### 任务上下文

```
BaseType_t ret = xSemaphoreGive(g_sem);

if (ret != pdPASS)
{
    stats_overflow_increment();
    fault_manager_report(
        FAULT_SEMAPHORE_OVERFLOW);
}
```

### ISR 上下文

```
BaseType_t woken = pdFALSE;
BaseType_t ret;

ret = xSemaphoreGiveFromISR(
    g_sem,
    &woken);

if (ret != pdPASS)
{
    /*
     * ISR 中只做最小记录。
     */
    g_sem_overflow_count++;
}

portYIELD_FROM_ISR(woken);
```

---

## 8.5 计数信号量与数据存储分离

推荐架构：

```
数据存储：
    环形缓冲区 / 描述符队列 / 内存池

事件计数：
    计数信号量

任务处理：
    Take 一次 -> 取出一个数据单元
```

例如：

```
DMA 完成
    -> 将缓冲区描述符放入队列
    -> Give 计数信号量

任务
    -> Take
    -> 从队列取出描述符
    -> 处理对应缓冲区
```

如果已经使用消息队列传递描述符，通常不再需要额外计数信号量，因为队列本身已经提供：

- 数据保存；
- 排队；
- 阻塞等待；
- 事件计数。

---

## 8.6 批量消费降低调度开销

当一次唤醒后可能有多个事件，可以批量处理：

```
static void EventConsumerTask(void *argument)
{
    for (;;)
    {
        if (xSemaphoreTake(
                g_event_count,
                pdMS_TO_TICKS(100)) == pdPASS)
        {
            process_one_event();

            /*
             * 继续非阻塞消费当前已积压事件。
             */
            while (xSemaphoreTake(
                       g_event_count,
                       0U) == pdPASS)
            {
                process_one_event();
            }
        }
        else
        {
            event_consumer_timeout();
        }
    }
}
```

收益：

- 减少阻塞/唤醒次数；
- 减少上下文切换；
- 提高数据局部性；
- 降低调度抖动。

但应设置单次批处理上限，防止低优先级任务长期占用 CPU：

```
#define EVENT_BATCH_LIMIT 32U
```

---

## 8.7 资源模式必须绑定实际资源

错误：

```
xSemaphoreCreateCounting(8, 8);
```

但实际系统只有 4 个资源对象。

这样计数信号量无法真实表达资源状态。

正确做法：

```
#define DMA_BUFFER_COUNT 4U

static dma_buffer_t g_dma_buffers[DMA_BUFFER_COUNT];

g_free_buffer_sem =
    xSemaphoreCreateCounting(
        DMA_BUFFER_COUNT,
        DMA_BUFFER_COUNT);
```

计数值必须与实际对象池容量一致。

---

## 8.8 工业级编码规范

推荐提供封装接口：

```
typedef struct
{
    SemaphoreHandle_t handle;
    UBaseType_t max_count;
    volatile uint32_t give_count;
    volatile uint32_t take_count;
    volatile uint32_t overflow_count;
    volatile uint32_t timeout_count;
} counted_event_t;
```

禁止业务层直接任意 `Give`：

```
/* 不推荐 */
xSemaphoreGive(g_global_sem);
```

推荐：

```
counted_event_signal_from_isr(
    &g_rx_event,
    &woken);

counted_event_wait(
    &g_rx_event,
    timeout);
```

这样可以统一：

- 统计；
- 超时；
- 溢出；
- 生命周期；
- 诊断；
- 单元测试。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：将计数信号量当作无限计数器

### 错误代码

```
for (;;)
{
    xSemaphoreGive(g_event_sem);
}
```

### 根因分析

计数信号量存在最大值：

```
current_count <= max_count
```

当计数达到最大值后，后续 `Give` 失败。

### 正确实现

```
BaseType_t ret = xSemaphoreGive(g_event_sem);

if (ret != pdPASS)
{
    event_overflow_handle();
}
```

如果业务确实要求无限累加，应使用：

- 64 位原子计数器；
- 软件饱和计数器；
- 队列；
- 环形日志；
- 丢失事件统计。

### 风险影响

- 静默丢事件；
- 任务处理数量小于实际产生数量；
- 数据统计失真；
- 控制系统响应异常。

---

## 9.2 错误二：把资源池计数和资源对象脱离

### 错误代码

```
static Buffer_t g_buffers[4];

static SemaphoreHandle_t g_free_buffer_sem;

void init(void)
{
    g_free_buffer_sem =
        xSemaphoreCreateCounting(8U, 8U);
}
```

### 根因分析

实际只有 4 个资源，却初始化出 8 个可用资源。

任务可能成功获取第 5~8 个“资源令牌”，但没有对应对象。

### 正确实现

```
#define BUFFER_COUNT 4U

static Buffer_t g_buffers[BUFFER_COUNT];

void init(void)
{
    g_free_buffer_sem =
        xSemaphoreCreateCounting(
            BUFFER_COUNT,
            BUFFER_COUNT);

    configASSERT(g_free_buffer_sem != NULL);
}
```

### 风险影响

- 缓冲区越界；
- 空指针；
- 多任务使用同一资源；
- 内存破坏；
- 偶发 HardFault。

---

## 9.3 错误三：资源使用异常路径未归还

### 错误代码

```
if (xSemaphoreTake(
        g_resource_sem,
        pdMS_TO_TICKS(100)) == pdPASS)
{
    if (!resource_operation())
    {
        return;  /* 错误：没有 Give */
    }

    xSemaphoreGive(g_resource_sem);
}
```

### 根因分析

异常返回路径泄漏了一个资源令牌。

经过多次故障后：

```
available_count 持续下降
```

最终所有任务永久阻塞。

### 正确实现

```
bool resource_execute(void)
{
    bool ok = false;

    if (xSemaphoreTake(
            g_resource_sem,
            pdMS_TO_TICKS(100)) != pdPASS)
    {
        return false;
    }

    ok = resource_operation();

    /*
     * 无论成功还是失败，只要已获取资源，
     * 就必须归还。
     */
    if (xSemaphoreGive(g_resource_sem) != pdPASS)
    {
        fault_manager_report(
            FAULT_RESOURCE_RETURN_FAILED);
        ok = false;
    }

    return ok;
}
```

更复杂的 C 项目可使用统一清理出口：

```
bool resource_execute(void)
{
    bool acquired = false;
    bool result = false;

    if (xSemaphoreTake(
            g_resource_sem,
            pdMS_TO_TICKS(100)) != pdPASS)
    {
        goto exit;
    }

    acquired = true;

    result = resource_operation();

exit:
    if (acquired)
    {
        if (xSemaphoreGive(g_resource_sem) != pdPASS)
        {
            result = false;
        }
    }

    return result;
}
```

### 风险影响

- 资源逐步耗尽；
- 系统长时间运行后死锁；
- 故障难以复现；
- 看门狗复位。

---

## 9.4 错误四：用计数信号量传递需要区分的数据事件

### 错误代码

```
void SensorA_IRQHandler(void)
{
    xSemaphoreGiveFromISR(g_sensor_event_sem, NULL);
}

void SensorB_IRQHandler(void)
{
    xSemaphoreGiveFromISR(g_sensor_event_sem, NULL);
}

static void SensorTask(void *argument)
{
    while (1)
    {
        xSemaphoreTake(g_sensor_event_sem, portMAX_DELAY);

        /*
         * 不知道是 Sensor A 还是 Sensor B 触发
         */
        process_sensor_event();
    }
}
```

### 根因分析

计数信号量只保留：

```
事件数量
```

不保存：

```
事件来源和数据
```

### 正确实现

使用事件位：

```
#define SENSOR_A_EVENT (1UL << 0)
#define SENSOR_B_EVENT (1UL << 1)
```

或使用消息队列：

```
typedef struct
{
    uint8_t source;
    uint32_t timestamp;
} sensor_event_t;
```

### 风险影响

- 读取错误设备；
- 事件与数据错配；
- 无法按来源进行故障统计；
- 业务状态机错误跳转。

---

## 9.5 错误五：在 ISR 中使用普通 API

### 错误代码

```
void DMA_IRQHandler(void)
{
    xSemaphoreGive(g_dma_count_sem);
}
```

### 根因分析

普通 API 可能：

- 操作任务阻塞列表；
- 执行不适用于 ISR 的临界区；
- 触发调度；
- 访问当前任务上下文。

### 正确实现

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    dma_clear_flags();

    if (xSemaphoreGiveFromISR(
            g_dma_count_sem,
            &woken) != pdPASS)
    {
        g_dma_overflow_count++;
    }

    portYIELD_FROM_ISR(woken);
}
```

### 风险影响

- HardFault；
- 内核链表损坏；
- 随机死锁；
- 中断返回异常。

---

## 9.6 错误六：忽略 `portYIELD_FROM_ISR`

### 错误代码

```
void Timer_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    xSemaphoreGiveFromISR(
        g_period_count_sem,
        &woken);

    /* 忘记调度 */
}
```

### 根因分析

计数增加只会让等待任务进入就绪态，不能保证立即切换到高优先级任务。

### 正确实现

```
void Timer_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    timer_clear_irq();

    xSemaphoreGiveFromISR(
        g_period_count_sem,
        &woken);

    portYIELD_FROM_ISR(woken);
}
```

### 风险影响

- 消费延迟增加；
- 计数积压；
- DMA 缓冲区覆盖；
- 实时性抖动增加。

---

## 9.7 错误七：用计数信号量保护共享资源

### 错误代码

```
xSemaphoreTake(g_bus_count_sem, portMAX_DELAY);
spi_transfer();
xSemaphoreGive(g_bus_count_sem);
```

### 根因分析

计数信号量不具备：

- 所有权；
- 优先级继承；
- 持有者检查；
- 递归加锁语义。

### 正确实现

```
static SemaphoreHandle_t g_spi_mutex;

bool spi_transfer_guarded(
    const uint8_t *tx,
    uint8_t *rx,
    size_t length)
{
    if (xSemaphoreTake(
            g_spi_mutex,
            pdMS_TO_TICKS(20)) != pdPASS)
    {
        return false;
    }

    bool result = spi_transfer(tx, rx, length);

    xSemaphoreGive(g_spi_mutex);

    return result;
}
```

### 风险影响

- 优先级反转；
- 总线访问冲突；
- 数据帧交错；
- 片选时序错误。

---

## 10. 多机制组合使用方案

## 10.1 计数信号量 + 环形缓冲区

适合：

```
事件数量需要累计
事件数据保存在环形缓冲区
```

架构：

```
ISR/生产者
    |
    +-- 写入环形缓冲区
    +-- Give counting semaphore
                |
                v
          消费任务
                |
                +-- Take
                +-- 从环形缓冲区读取一个事件
```

### 代码框架

```
#include "FreeRTOS.h"
#include "semphr.h"
#include <stdint.h>
#include <stdbool.h>

#define EVENT_RING_SIZE 128U

typedef struct
{
    uint32_t timestamp;
    uint16_t type;
    uint16_t value;
} event_record_t;

typedef struct
{
    event_record_t buffer[EVENT_RING_SIZE];

    volatile uint32_t write_index;
    volatile uint32_t read_index;

    SemaphoreHandle_t event_count;
} event_ring_t;

static event_ring_t g_event_ring;
static StaticSemaphore_t g_event_sem_storage;

static uint32_t ring_next(uint32_t index)
{
    return (index + 1U) % EVENT_RING_SIZE;
}

static bool event_ring_push(
    event_ring_t *ring,
    const event_record_t *event)
{
    uint32_t next = ring_next(ring->write_index);

    if (next == ring->read_index)
    {
        return false;
    }

    ring->buffer[ring->write_index] = *event;
    ring->write_index = next;

    return true;
}

static bool event_ring_pop(
    event_ring_t *ring,
    event_record_t *event)
{
    if (ring->read_index == ring->write_index)
    {
        return false;
    }

    *event = ring->buffer[ring->read_index];
    ring->read_index = ring_next(ring->read_index);

    return true;
}

void event_ring_init(void)
{
    g_event_ring.event_count =
        xSemaphoreCreateCountingStatic(
            EVENT_RING_SIZE - 1U,
            0U,
            &g_event_sem_storage);

    configASSERT(
        g_event_ring.event_count != NULL);
}

void EXTI0_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    event_record_t event = {
        .timestamp = timer_get_timestamp(),
        .type = 1U,
        .value = sensor_read_latched_value()
    };

    exti_clear_pending();

    if (event_ring_push(&g_event_ring, &event))
    {
        if (xSemaphoreGiveFromISR(
                g_event_ring.event_count,
                &woken) != pdPASS)
        {
            /*
             * 环形缓冲区和计数信号量已经出现不一致。
             * 生产系统必须记录该故障。
             */
            g_event_counter_error = true;
        }
    }
    else
    {
        g_event_ring_overflow = true;
    }

    portYIELD_FROM_ISR(woken);
}

static void EventConsumerTask(void *argument)
{
    event_record_t event;

    (void)argument;

    for (;;)
    {
        if (xSemaphoreTake(
                g_event_ring.event_count,
                pdMS_TO_TICKS(100)) != pdPASS)
        {
            event_consumer_timeout();
            continue;
        }

        if (!event_ring_pop(
                &g_event_ring,
                &event))
        {
            /*
             * 计数信号量说有数据，但环形缓冲区为空，
             * 说明同步计数和数据队列已经失配。
             */
            event_ring_consistency_fault();
            continue;
        }

        process_event(&event);
    }
}
```

### 设计要点

- 环形缓冲区容量和计数信号量最大值必须一致；
- 计数信号量只表示元素数量；
- 缓冲区满时必须明确丢弃策略；
- 生产者和消费者索引要有清晰所有权；
- 多生产者时，不能直接套用单生产者无锁环形队列。

---

## 10.2 计数信号量 + 固定块内存池

适合：

```
多个任务动态申请固定大小对象
资源数量有限
不希望使用堆
```

架构：

```
空闲块池：
    [Block 0] [Block 1] [Block 2] [Block 3]

free_count = 4

任务获取：
    Take -> 从空闲链表取一个块

任务归还：
    放回空闲链表
    Give
```

### 代码框架

```
#define BLOCK_COUNT 8U
#define BLOCK_SIZE 256U

typedef struct memory_block
{
    uint8_t data[BLOCK_SIZE];
    struct memory_block *next;
} memory_block_t;

typedef struct
{
    memory_block_t blocks[BLOCK_COUNT];

    memory_block_t *free_list;
    SemaphoreHandle_t count_sem;
    SemaphoreHandle_t list_mutex;
} fixed_pool_t;

static fixed_pool_t g_pool;
static StaticSemaphore_t g_count_storage;
static StaticSemaphore_t g_mutex_storage;

void fixed_pool_init(void)
{
    g_pool.free_list = NULL;

    for (uint32_t i = 0U; i < BLOCK_COUNT; ++i)
    {
        g_pool.blocks[i].next = g_pool.free_list;
        g_pool.free_list = &g_pool.blocks[i];
    }

    g_pool.count_sem =
        xSemaphoreCreateCountingStatic(
            BLOCK_COUNT,
            BLOCK_COUNT,
            &g_count_storage);

    g_pool.list_mutex =
        xSemaphoreCreateMutexStatic(
            &g_mutex_storage);

    configASSERT(g_pool.count_sem != NULL);
    configASSERT(g_pool.list_mutex != NULL);
}

memory_block_t *fixed_pool_acquire(
    TickType_t timeout)
{
    memory_block_t *block = NULL;

    if (xSemaphoreTake(
            g_pool.count_sem,
            timeout) != pdPASS)
    {
        return NULL;
    }

    if (xSemaphoreTake(
            g_pool.list_mutex,
            pdMS_TO_TICKS(10)) != pdPASS)
    {
        /*
         * 已经消耗了一个资源令牌，但没有取出对象。
         * 必须恢复计数，否则造成资源泄漏。
         */
        xSemaphoreGive(g_pool.count_sem);
        return NULL;
    }

    block = g_pool.free_list;

    if (block != NULL)
    {
        g_pool.free_list = block->next;
        block->next = NULL;
    }

    xSemaphoreGive(g_pool.list_mutex);

    if (block == NULL)
    {
        /*
         * 计数和链表不一致。
         */
        xSemaphoreGive(g_pool.count_sem);
    }

    return block;
}

bool fixed_pool_release(memory_block_t *block)
{
    if (block == NULL)
    {
        return false;
    }

    if (xSemaphoreTake(
            g_pool.list_mutex,
            pdMS_TO_TICKS(10)) != pdPASS)
    {
        return false;
    }

    block->next = g_pool.free_list;
    g_pool.free_list = block;

    xSemaphoreGive(g_pool.list_mutex);

    if (xSemaphoreGive(g_pool.count_sem) != pdPASS)
    {
        /*
         * 可能是重复释放或资源池状态损坏。
         */
        pool_report_double_release(block);
        return false;
    }

    return true;
}
```

### 设计要点

- 计数信号量只表示空闲块数量；
- 空闲链表负责保存实际对象；
- 链表操作需要互斥保护；
- 获取信号量成功但对象获取失败时必须恢复计数；
- 归还对象前必须检查地址是否属于该池；
- 生产系统应检测重复释放和越界指针。

---

## 10.3 计数信号量 + 消息队列

这种组合有两种情况。

### 情况一：通常不需要组合

消息队列已经同时提供：

- 数据存储；
- 消息计数；
- 阻塞等待；
- FIFO 顺序。

此时额外计数信号量会造成状态重复，增加失配风险。

### 情况二：数据和工作令牌分离

例如：

```
DMA 缓冲区由硬件管理
任务只需要知道有多少个缓冲块完成
缓冲块编号由固定索引获取
```

此时计数信号量可以表示：

```
完成块数量
```

而队列保存：

```
块编号或块指针
```

但如果队列本身已经保证“一条消息对应一个块”，则计数信号量通常可以删除。

---

## 10.4 计数信号量 + 事件标志组

适合复杂设备状态：

```
事件计数：
    采样完成次数

事件状态：
    设备已连接
    校准已完成
    传感器有效
```

典型架构：

```
计数信号量：
    处理每个采样事件

事件标志组：
    判断系统是否满足运行条件
```

不要用计数信号量替代状态位，也不要用事件位替代需要累计的事件。

---

## 11. 工业级实际案例分析

## 11.1 案例一：多缓冲 DMA 采集

### 需求

- ADC 采样率：200 kHz；
- 每个 DMA 缓冲块：128 个样本；
- 环形 DMA 描述符数量：8；
- 每个完成块必须处理；
- 处理任务允许短时滞后，但不能长期丢块。

### 时间预算

每个块到达周期：

```
Tblock = 128 / 200000
       = 640 μs
```

如果任务处理一个块最坏需要：

```
Tprocess = 400 μs
```

则理论上有：

```
640 - 400 = 240 μs
```

调度和系统抖动裕量。

### 架构

```
ADC DMA
    |
    +-- 完成中断
    +-- Give counting semaphore
    |
    v
ADC Processing Task
    |
    +-- Take
    +-- 获取下一个 DMA 缓冲块
    +-- 执行滤波/FFT前处理
```

### 关键代码

```
#define ADC_DMA_BLOCK_COUNT 8U

static SemaphoreHandle_t g_adc_block_count;
static StaticSemaphore_t g_adc_count_storage;

static volatile uint32_t g_adc_overflow_count;
static volatile uint32_t g_adc_high_watermark;

void adc_dma_sync_init(void)
{
    g_adc_block_count =
        xSemaphoreCreateCountingStatic(
            ADC_DMA_BLOCK_COUNT,
            0U,
            &g_adc_count_storage);

    configASSERT(g_adc_block_count != NULL);
}

void DMA2_Stream0_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    if (dma_block_complete())
    {
        dma_clear_complete_flag();

        if (xSemaphoreGiveFromISR(
                g_adc_block_count,
                &woken) != pdPASS)
        {
            /*
             * 说明任务处理落后，或 DMA 描述符管理出错。
             */
            g_adc_overflow_count++;
        }
    }

    portYIELD_FROM_ISR(woken);
}

static void AdcProcessTask(void *argument)
{
    const TickType_t timeout =
        pdMS_TO_TICKS(10U);

    (void)argument;

    for (;;)
    {
        if (xSemaphoreTake(
                g_adc_block_count,
                timeout) != pdPASS)
        {
            adc_processing_timeout();
            continue;
        }

        dma_block_t *block =
            dma_get_completed_block();

        if (block == NULL)
        {
            adc_dma_state_fault();
            continue;
        }

        adc_process_block(block);
        dma_release_block(block);
    }
}
```

### 设计要点

- `max_count` 不应超过实际 DMA 描述符数量；
- 如果计数增加但没有对应完成块，说明 DMA 管理和同步状态失配；
- 需要监控计数高水位；
- 处理任务的最坏执行时间必须小于缓冲块到达周期；
- 如果长期接近满水位，应优化算法、增加 DMA 缓冲或降低采样率。

---

## 11.2 案例二：固定大小网络缓冲池

### 需求

- 网络协议栈需要申请固定大小报文缓冲区；
- 缓冲池共 32 个块；
- 多个任务可能同时申请；
- 不允许使用不受控的动态内存；
- 申请超时后需要丢包或进入背压。

### 架构

```
固定块内存池
    |
    +-- free_buffer_count：计数信号量
    +-- free_list_mutex：互斥锁
    +-- free_list：空闲块链表
```

### 关键设计

```
初始：
    count = 32

申请：
    Take -> count = 31
    从 free_list 取一个块

释放：
    放回 free_list
    Give -> count = 32
```

### 需求约束

```
free_count + allocated_count = 32
```

必须记录：

```
最小空闲块数量
申请超时次数
重复释放次数
非法地址释放次数
```

### 设计要点

- 计数信号量不替代空闲链表；
- 互斥锁保护链表；
- 任何失败路径都要恢复计数；
- 缓冲池耗尽时不要无限阻塞；
- 网络任务可根据资源不足进入背压或丢弃低优先级报文。

---

## 11.3 案例三：多通道传感器采样任务

### 需求

- 12 个传感器通道；
- 多个中断源产生采样完成事件；
- 一个采样任务统一消费；
- 每个事件需要知道通道号；
- 同一时刻可能出现多个完成事件。

### 错误设计

```
所有通道 ISR -> Give 一个计数信号量
```

问题：

```
任务只知道有 N 个事件，
不知道具体是哪几个通道完成。
```

### 正确架构

```
每个通道：
    事件记录进入环形队列
    Give 计数信号量

采样任务：
    Take
    Pop 一个事件记录
    按 channel_id 处理
```

事件记录：

```
typedef struct
{
    uint8_t channel_id;
    uint8_t status;
    uint16_t sample;
    uint32_t timestamp;
} sensor_event_t;
```

### 设计要点

- 计数信号量解决“有多少条记录待处理”；
- 环形队列解决“每条记录的具体内容”；
- 多 ISR 生产者时，队列写入必须具备并发保护；
- 若中断频率很高，应考虑 DMA 汇聚和批量采样。

---

## 12. 高频问题深度答疑

## 问题一：计数信号量和二值信号量的本质区别是什么？

核心区别不是 API 名称，而是是否允许多个未消费信号同时存在。

二值信号量：

```
最大状态为 1
多个 Give 会合并
```

计数信号量：

```
最大状态为 N
多个 Give 可以累计
```

如果业务要求：

```
事件发生 5 次，任务必须执行 5 次
```

使用计数信号量或队列。

如果业务只要求：

```
事件至少发生过一次，任务处理一次即可
```

使用二值信号量。

---

## 问题二：为什么计数信号量不能替代消息队列？

因为计数信号量只保存一个数字：

```
count = 3
```

它无法回答：

```
这 3 个事件分别是什么？
谁产生的？
什么时候产生的？
携带什么数据？
是否需要按顺序处理？
```

消息队列保存完整消息，并提供 FIFO 排队。

因此：

```
计数信号量 = 数量同步
消息队列 = 数据通信
```

---

## 问题三：计数信号量达到最大值后，应该如何处理？

这取决于业务，但不能无条件忽略。

常见策略：

### 丢弃新事件

适合：

```
只关心最新状态，旧事件可合并
```

### 覆盖旧事件

通常需要环形缓冲区配合。

### 进入故障

适合：

```
每个事件都必须处理，不能丢失
```

### 反向施加背压

适合：

```
生产者可以暂停或降低速率
```

工业系统至少应：

```
记录溢出次数
记录最高水位
记录最近一次溢出时间
```

---

## 问题四：计数信号量能否用于限制并发任务数量？

可以。

例如限制最多 4 个并发事务：

```
g_transaction_slots =
    xSemaphoreCreateCounting(4U, 4U);
```

每个事务开始：

```
xSemaphoreTake(g_transaction_slots, timeout);
```

事务完成：

```
xSemaphoreGive(g_transaction_slots);
```

但注意：

- 计数信号量不记录哪个任务占用了哪个槽位；
- 若任务异常退出，必须保证释放；
- 如果资源有明确身份，应结合对象池或槽位表；
- 不要将它误认为互斥锁。

---

## 问题五：计数信号量是否支持优先级继承？

通常不支持。

因为计数信号量没有明确的所有权：

```
任意生产者可以 Give
任意消费者可以 Take
```

RTOS 无法判断谁是资源持有者，也无法建立优先级继承关系。

如果问题是：

```
保护共享外设
```

使用互斥锁。

如果问题是：

```
多个同质资源的数量限制
```

使用计数信号量。

---

## 问题六：为什么计数信号量计数和实际缓冲区数量可能不一致？

常见原因：

1. 写入缓冲区成功，但 `Give` 失败；
2. `Give` 成功，但缓冲区写入失败；
3. 任务 `Take` 成功，但读取缓冲区失败；
4. 异常路径忘记归还；
5. 重复归还资源；
6. 多生产者访问无锁环形缓冲区；
7. DMA 状态与软件状态不同步；
8. 对象被删除或复位后计数未重建。

建议采用以下顺序：

```
写数据成功
    -> 更新写索引
    -> Give 计数信号量
```

消费侧：

```
Take 成功
    -> 读取数据
    -> 处理或归还数据资源
```

并增加一致性断言：

```
configASSERT(buffer_available() >= 0);
configASSERT(buffer_pending() ==
             semaphore_count());
```

生产系统中不应频繁调用高成本断言，但可以在诊断版本中启用。

---

## 13. 课程核心总结

## 13.1 核心要点

1. **计数信号量表示可用资源数量或待处理事件数量。**
2. 计数范围满足：

```
0 <= count <= max_count
```

3. 它能够累计多个事件，而二值信号量不能。
4. 它不保存事件数据、来源、顺序和时间戳。
5. 计数信号量没有所有权，也通常没有优先级继承。
6. ISR 中必须使用 `xSemaphoreGiveFromISR()`。
7. 释放时必须检查是否达到最大计数。
8. 资源池场景必须保持：

```
空闲资源数 + 已分配资源数 = 总资源数
```

9. 事件场景必须关注：

```
生产速率、消费速率、最大积压和溢出
```

10. 需要传递数据时，应与消息队列、环形缓冲区或内存池组合。

## 13.2 性能排序

典型 FreeRTOS Cortex-M 系统中：

```
任务通知计数模式
    >
计数信号量
    >
事件标志组
    >
消息队列
```

这只是典型同步路径排序，不代表所有平台和所有负载下的绝对结果。

## 13.3 通用选型结论

```
一个事件，接收者固定为一个任务：
    任务通知计数模式

多个事件，只需要累计数量：
    计数信号量

多个事件，需要保存具体数据：
    消息队列或环形缓冲区

多个同质资源数量受限：
    计数信号量 + 资源池

保护单一共享资源：
    互斥锁

只需要表达是否发生：
    二值信号量

多个条件组合：
    事件标志组
```

---

## 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐机制|关键注意事项|
|---|---|---|
|DMA 完成块累计|计数信号量|最大计数不能小于缓冲块容量|
|多个中断事件累计|计数信号量|检查溢出|
|单任务累计事件|任务通知计数|性能和 RAM 更优|
|UART 帧接收|队列/环形缓冲区 + 计数|信号量不保存帧内容|
|固定内存块池|计数信号量 + 空闲链表|必须防止重复释放|
|并发连接数限制|计数信号量|异常退出必须归还|
|SPI 总线互斥|互斥锁|需要优先级继承|
|多通道事件区分|事件记录队列|计数信号量不能表示来源|
|事件广播|事件标志组|计数信号量是竞争消费，不是广播|
|传递大块数据|指针队列 + 内存池|避免大块复制|

## 14.2 FreeRTOS API 速查

|需求|API|
|---|---|
|动态创建|`xSemaphoreCreateCounting()`|
|静态创建|`xSemaphoreCreateCountingStatic()`|
|任务获取|`xSemaphoreTake()`|
|任务释放|`xSemaphoreGive()`|
|ISR 释放|`xSemaphoreGiveFromISR()`|
|删除|`vSemaphoreDelete()`|
|查询计数|`uxSemaphoreGetCount()`|
|查询等待数量|`uxQueueMessagesWaiting()`|
|查询剩余空间|`uxQueueSpacesAvailable()`|
|ISR 请求切换|`portYIELD_FROM_ISR()`|

## 14.3 关键约束表

|项目|约束|
|---|---|
|初始计数|必须小于或等于最大计数|
|最大计数|必须匹配事件积压或资源池容量|
|ISR API|必须使用 `FromISR` 版本|
|资源释放|每次成功获取必须有对应归还|
|事件数据|计数信号量不保存|
|优先级继承|通常不支持|
|计数溢出|必须检测并诊断|
|生命周期|删除前必须停止所有生产者和消费者|
|多生产者|缓冲区必须具备并发保护|
|多消费者|只保证消费数量，不保证业务路由|

---

## 15. 学习效果自检

### 基础理解

- [ ]  能写出计数信号量的不变量：

```
0 <= count <= max_count
```

- [ ]  能解释事件计数模式和资源计数模式。
- [ ]  能解释计数信号量与二值信号量的区别。
- [ ]  能说明为什么计数信号量不能传递事件数据。
- [ ]  能说明为什么计数信号量不具备优先级继承。

### API 能力

- [ ]  能正确创建动态计数信号量。
- [ ]  能正确创建静态计数信号量。
- [ ]  能在任务中使用超时获取。
- [ ]  能在 ISR 中使用 `xSemaphoreGiveFromISR()`。
- [ ]  能检查 `Give` 失败和计数溢出。
- [ ]  能使用 `uxSemaphoreGetCount()` 进行诊断。

### 内核理解

- [ ]  能说明计数信号量如何基于 FreeRTOS 队列实现。
- [ ]  能说明 `uxMessagesWaiting` 如何表示当前计数。
- [ ]  能解释计数为 0 时任务如何阻塞。
- [ ]  能解释达到最大计数时 `Give` 为什么失败。
- [ ]  能说明 ISR 唤醒高优先级任务的调度路径。

### 工程设计能力

- [ ]  能根据生产速率和消费速率计算最大积压。
- [ ]  能设计计数信号量和环形缓冲区的组合方案。
- [ ]  能设计固定块内存池。
- [ ]  能识别资源泄漏和重复释放。
- [ ]  能识别计数信号量无法表达事件来源的问题。
- [ ]  能为计数溢出和超时设计恢复策略。

### 性能验证能力

- [ ]  能使用 DWT 测量 Give/Take 周期。
- [ ]  能使用 GPIO 测量 ISR 到任务的响应延迟。
- [ ]  能统计计数高水位。
- [ ]  能计算事件积压容量。
- [ ]  能比较计数信号量和任务通知的 CPU/RAM 开销。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：事件累计

实现：

```
定时器 ISR -> 计数信号量 -> 任务
```

要求：

- 定时器每 1 ms 产生一次事件；
- 任务每次处理耗时 2 ms；
- 观察计数是否增长；
- 记录最大计数高水位；
- 当计数达到上限时触发告警。

需要回答：

```
为什么平均消费能力不足时计数会持续增加？
```

---

### 任务二：DMA 多块处理

实现：

```
ADC DMA 8 块缓冲
DMA 完成 ISR
计数信号量
采样处理任务
```

要求：

- 计算每个块的到达周期；
- 测量处理任务最坏执行时间；
- 统计溢出次数；
- 统计计数高水位；
- 注入任务延迟，观察系统行为。

---

### 任务三：固定块内存池

实现：

```
16 个固定大小缓冲块
计数信号量管理空闲数量
互斥锁保护空闲链表
```

要求：

- 支持多个任务并发申请；
- 支持超时；
- 检测重复释放；
- 检测非法地址释放；
- 验证资源守恒关系：

```
free_count + allocated_count = 16
```

---

### 任务四：计数信号量与消息队列对比

使用以下三种方式实现事件处理：

```
计数信号量 + 环形缓冲区
消息队列
任务通知计数 + 环形缓冲区
```

测量：

- RAM 占用；
- Give/Take 周期；
- 事件吞吐量；
- 最大可承受突发；
- 事件丢失数量；
- 代码复杂度；
- 故障诊断能力。

---

### 任务五：故障注入

注入以下故障：

```
消费者任务暂停 100 ms
生产速率超过消费速率
Give 重复调用
资源重复归还
任务获取后异常退出
DMA 完成计数与缓冲区状态不一致
中断优先级配置错误
```

要求：

- 系统检测计数溢出；
- 记录最高水位；
- 检测资源泄漏；
- 进行计数重建或模块复位；
- 不允许用无限等待掩盖故障。

---

## 16.2 性能测试方法

### 方法一：DWT 测量 Give/Take

```
static inline void dwt_counter_init(void)
{
    CoreDebug->DEMCR |=
        CoreDebug_DEMCR_TRCENA_Msk;

    DWT->CYCCNT = 0U;

    DWT->CTRL |=
        DWT_CTRL_CYCCNTENA_Msk;
}

static inline uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}
```

任务上下文测量：

```
uint32_t start = dwt_cycles();

BaseType_t ret = xSemaphoreTake(
    g_count_sem,
    0U);

uint32_t elapsed =
    dwt_cycles() - start;
```

应分别测量：

```
count > 0 时成功 Take
count == 0 时立即失败
阻塞后唤醒
Give 无等待任务
Give 唤醒高优先级任务
```

---

### 方法二：测量积压高水位

```
static void update_count_high_watermark(
    SemaphoreHandle_t sem)
{
    UBaseType_t count =
        uxSemaphoreGetCount(sem);

    if (count > g_high_watermark)
    {
        g_high_watermark = count;
    }
}
```

在每次 `Give` 或周期诊断任务中采样：

```
当前计数
最大计数
溢出次数
超时次数
Give 总数
Take 总数
```

---

### 方法三：GPIO 测量端到端延迟

ISR：

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    gpio_set(DEBUG_ISR_PIN);

    dma_clear_flags();

    xSemaphoreGiveFromISR(
        g_count_sem,
        &woken);

    portYIELD_FROM_ISR(woken);

    gpio_clear(DEBUG_ISR_PIN);
}
```

任务：

```
static void ProcessTask(void *argument)
{
    for (;;)
    {
        xSemaphoreTake(
            g_count_sem,
            portMAX_DELAY);

        gpio_set(DEBUG_TASK_PIN);

        process_one_block();

        gpio_clear(DEBUG_TASK_PIN);
    }
}
```

测量：

```
ISR 标记上升沿
    ->
任务标记上升沿
```

得到：

```
信号产生到任务开始执行的响应延迟
```

---

### 方法四：稳定性测试

至少覆盖：

|测试条件|目标|
|---|---|
|生产速率低于消费速率|确认计数稳定|
|生产速率等于消费速率|确认长期不漂移|
|生产速率高于消费速率|确认高水位和溢出诊断|
|消费者短时阻塞|验证突发容量|
|消费者长期停止|验证故障恢复|
|多生产者并发|验证计数和数据一致性|
|多消费者竞争|验证任务公平性和吞吐量|
|任务异常退出|验证资源归还|

---

## 16.3 进阶学习方向

1. FreeRTOS：
    - `queue.c`；
    - `tasks.c`；
    - 队列发送和接收列表；
    - 超时列表；
    - 任务通知实现。
2. 任务通知的计数模式、位模式和覆盖模式。
3. 无锁环形缓冲区：
    - 单生产者单消费者；
    - 多生产者；
    - 内存屏障；
    - Cache 一致性。
4. 固定块内存池和对象池。
5. DMA 描述符环和多缓冲架构。
6. 生产者-消费者排队模型。
7. Little 定律：

```
平均在途数量 = 平均到达率 × 平均停留时间
```

8. 实时性分析：
    - WCET；
    - 最坏积压；
    - 队列容量；
    - 调度抖动；
    - 阻塞时间。
9. 高可靠系统中的：
    - 计数守恒；
    - 资源泄漏检测；
    - 运行时一致性校验；
    - 诊断快照；
    - 故障降级。
10. 多核 RTOS 中的：

- 原子计数；
- 跨核事件通知；
- 自旋锁；
- 内存排序；
- NUMA/Cache 影响。