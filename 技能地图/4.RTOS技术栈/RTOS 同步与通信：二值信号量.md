
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解二值信号量的状态模型：**可用 / 不可用**。
- 区分二值信号量与：
    - 互斥锁；
    - 计数信号量；
    - 事件标志组；
    - 任务通知；
    - 消息队列。
- 理解二值信号量在任务间、ISR 与任务间同步中的典型语义。
- 理解二值信号量**不具备优先级继承能力**这一关键限制。

### 1.2 掌握

能够：

- 使用 FreeRTOS 创建、释放、获取二值信号量。
- 正确处理 `FromISR` API、中断优先级与任务唤醒。
- 设计中断采集、DMA 完成通知、生产者-消费者同步方案。
- 设置超时、处理超时故障和资源回收。
- 使用 Trace、运行时间统计和 GPIO 翻转测量信号量延迟。

### 1.3 精通

能够：

- 从内核源码层面分析二值信号量的阻塞、唤醒和调度路径。
- 判断一个同步问题是否适合使用二值信号量。
- 分析优先级反转、丢事件、重复释放、ISR 延迟等问题。
- 评估二值信号量相对于任务通知、事件标志组、消息队列的性能和内存代价。
- 设计具有超时、故障恢复、可观测性的工业级同步组件。

### 1.4 能够设计

能够设计：

- UART 接收中断到协议解析任务的同步架构。
- ADC/DMA 采样完成到算法任务的同步架构。
- 多任务协同的设备状态机。
- 带错误恢复和性能监测的二值信号量封装层。
- 满足实时性约束的同步机制选型矩阵。

---

## 2. 前置要求

### 2.1 知识要求

- C 语言：
    - 指针、结构体、函数指针；
    - `volatile`；
    - 临界区和中断基本概念；
    - 内存可见性和编译器优化。
- MCU 基础：
    - NVIC 中断优先级；
    - SysTick；
    - PendSV；
    - 临界区；
    - DMA 和外设中断。
- RTOS 基础：
    - 任务状态；
    - 就绪态、阻塞态、挂起态；
    - 优先级调度；
    - 时间片；
    - Tick 和超时。
- FreeRTOS 基础：
    - `TaskHandle_t`；
    - `TickType_t`；
    - `configMAX_PRIORITIES`；
    - `configASSERT()`；
    - `INCLUDE_xTaskAbortDelay` 等配置项。

### 2.2 技能要求

- 能够独立编译和下载 FreeRTOS 工程。
- 能够查看 map 文件和任务运行时统计。
- 能够使用逻辑分析仪或示波器测量 GPIO 脉宽。
- 能够阅读 FreeRTOS `queue.c`、`tasks.c` 的核心路径。
- 能够调试 HardFault、断言和任务栈溢出。

---

## 3. 技术概述

## 3.1 二值信号量的定义

二值信号量本质上是一个只有两个逻辑状态的同步对象：

```
0：不可用，获取操作会阻塞或立即失败
1：可用，获取操作成功，并通常消耗该信号
```

典型工作方式：

```
任务 A 或 ISR：
    give() -> 将信号置为可用，并唤醒等待者

任务 B：
    take() -> 等待信号
             成功后继续运行
```

它表达的是：

> **某个事件已经发生，或者某个执行条件已经满足。**

它通常不表达数据本身，而是表达“可以去检查数据了”。

例如：

```
DMA 完成中断 -> give(binary_semaphore)
采集任务     -> take(binary_semaphore)
采集任务     -> 检查 DMA 缓冲区并处理数据
```

二值信号量并不负责保存采样数据，数据应存放在 DMA 缓冲区、环形缓冲区或消息队列中。

---

## 3.2 二值信号量的核心语义

二值信号量可以抽象为：

```
typedef struct
{
    bool available;
} binary_semaphore_t;
```

基本操作：

```
take():
    if available == true:
        available = false;
        return SUCCESS;

    if timeout == 0:
        return TIMEOUT;

    block_current_task();
    return when_signal_available;

give():
    available = true;
    wake_one_waiting_task();
```

但是在真正的 RTOS 中还需要处理：

- 等待队列；
- 优先级排序；
- 超时唤醒；
- 中断上下文；
- 临界区；
- 调度器锁；
- 任务状态转移；
- 高优先级任务抢占；
- 多核下的内存同步。

---

## 3.3 主流实现分支

|实现方式|典型接口|特点|适用场景|
|---|---|---|---|
|RTOS 通用二值信号量|`xSemaphoreCreateBinary()`|语义清晰，通用性强|任务与任务、ISR 与任务|
|静态二值信号量|`xSemaphoreCreateBinaryStatic()`|无运行时动态分配|工业产品、功能安全|
|任务通知模拟二值信号量|`xTaskNotifyGive()` / `ulTaskNotifyTake()`|性能高、内存小|单一任务接收事件|
|事件标志组|`xEventGroupSetBits()`|多种事件组合|多事件等待、状态组合|
|CMSIS-RTOS 信号量|`osSemaphoreNew(1, 0, ...)`|API 统一|CMSIS-RTOS 兼容项目|
|Zephyr semaphore|`k_sem_init()`|原生内核对象|Zephyr 系统|
|Linux completion|`complete()`|一次性完成事件|Linux 内核线程同步|

---

## 3.4 二值信号量不是互斥锁

这是工程中最容易出现的概念错误之一。

|对比项|二值信号量|互斥锁|
|---|---|---|
|主要目的|事件同步|保护共享资源|
|所有权|通常无所有权|有所有权|
|谁可以释放|通常任意任务或 ISR|通常只能持有者释放|
|优先级继承|**通常没有**|**通常支持**|
|递归获取|通常不支持|可选递归互斥锁|
|典型场景|中断通知任务|保护 SPI 总线|
|典型风险|丢事件、错误释放|死锁、锁顺序错误|
|ISR 是否可释放|通常支持|通常不允许|

核心结论：

> **同步事件使用二值信号量，资源所有权使用互斥锁。**

---

## 4. 核心特性横向对比

### 4.1 FreeRTOS 同步机制对比

|机制|内存开销|典型延迟|可由 ISR 释放|保存数据|优先级继承|最佳用途|
|---|---|---|---|---|---|---|
|二值信号量|中|中|是|否|否|事件同步|
|计数信号量|中|中|是|否|否|资源计数、事件累计|
|互斥锁|中|中|否|否|是|共享资源保护|
|递归互斥锁|中|中|否|否|是|同一任务嵌套加锁|
|事件标志组|中|中|是|位集合|否|多事件组合|
|消息队列|高|高|是|是|否|数据传输|
|直接任务通知|极低|**低**|是|可选|否|单任务事件通知|

### 4.2 二值信号量与任务通知对比

|维度|二值信号量|直接任务通知|
|---|---|---|
|接收者|多个任务理论上可等待|固定绑定一个任务|
|对象独立性|独立内核对象|存储在任务控制块中|
|RAM 占用|较高|极低|
|运行速度|较快|**通常最快**|
|可读性|高|依赖通知配置|
|可扩展性|更好|单接收者限制明显|
|ISR 通知|支持|支持|
|多个生产者|容易实现|需要额外设计|
|适合公共组件|好|适合封闭模块|

### 4.3 二值信号量的关键行为

|行为|说明|
|---|---|
|初始状态|FreeRTOS 动态创建的二值信号量通常初始为“不可用”|
|获取成功|信号从可用变为不可用|
|重复释放|二值语义下不会累积多个信号|
|多次 ISR 触发|如果接收任务未及时获取，多个事件可能合并为一个|
|等待超时|不会自动产生信号，仅返回超时|
|删除对象|必须确保没有任务或 ISR 继续访问|
|任务唤醒|可能触发立即抢占|

---

## 5. 底层原理与功能特性深度解析

以下以 **FreeRTOS** 为主要实现进行分析。

## 5.1 FreeRTOS 中二值信号量的实现本质

FreeRTOS 的信号量不是独立的数据结构，而是基于队列机制实现的。

典型实现逻辑是：

```
#define xSemaphoreCreateBinary() \
    xQueueGenericCreate(1, semSEMAPHORE_QUEUE_ITEM_LENGTH, queueQUEUE_TYPE_BINARY_SEMAPHORE)
```

关键参数：

```
队列长度 = 1
队列单元大小 = 0
队列类型 = binary semaphore
```

因此可以理解为：

```
二值信号量 = 长度为 1、没有用户数据载荷的特殊队列
```

FreeRTOS 内部会使用类似以下的队列结构：

```
typedef struct QueueDefinition
{
    int8_t * pcHead;
    int8_t * pcWriteTo;

    union
    {
        QueuePointers_t xQueue;
        SemaphoreData_t xSemaphore;
    } u;

    List_t xTasksWaitingToSend;
    List_t xTasksWaitingToReceive;

    volatile UBaseType_t uxMessagesWaiting;
    UBaseType_t uxLength;
    UBaseType_t uxItemSize;

    uint8_t ucQueueType;
} Queue_t;
```

二值信号量主要依赖：

```
uxMessagesWaiting
```

其逻辑值通常为：

```
0：无信号
1：有信号
```

---

## 5.2 获取信号量的内核路径

任务调用：

```
xSemaphoreTake(sem, timeout);
```

最终通常进入：

```
xQueueSemaphoreTake()
```

逻辑可以简化为：

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

        /* 被唤醒后重新检查条件，防止竞态 */
    }
}
```

实际源码还包含：

- 互斥锁优先级继承处理；
- 任务超时列表操作；
- 调度器挂起；
- 中断安全；
- 时间溢出处理；
- 删除队列保护。

核心思想是：

> **任务阻塞前必须再次检查条件，并且“检查条件 + 加入等待队列”必须具备原子性。**

否则可能产生经典竞态：

```
任务检查：信号不存在
ISR 释放信号
任务加入等待队列
任务永久等待
```

RTOS 通过临界区和内核调度器保护避免这一问题。

---

## 5.3 释放信号量的内核路径

任务上下文释放：

```
xSemaphoreGive(sem);
```

ISR 上下文释放：

```
xSemaphoreGiveFromISR(sem, &higher_priority_task_woken);
```

简化后的任务上下文逻辑：

```
BaseType_t xQueueGenericSend(
    QueueHandle_t xQueue,
    const void * pvItemToQueue,
    TickType_t xTicksToWait,
    BaseType_t xCopyPosition)
{
    taskENTER_CRITICAL();

    if (xQueue->uxMessagesWaiting < xQueue->uxLength)
    {
        /* 对二值信号量来说，仅代表置为可用 */
        xQueue->uxMessagesWaiting++;

        if (listLIST_IS_EMPTY(
                &xQueue->xTasksWaitingToReceive) == pdFALSE)
        {
            /* 从等待列表移除一个任务 */
            if (xTaskRemoveFromUnorderedEventList(
                    &xQueue->xTasksWaitingToReceive,
                    queueSEND_TO_BACK) != pdFALSE)
            {
                /* 需要切换到更高优先级任务 */
            }
        }

        taskEXIT_CRITICAL();
        return pdPASS;
    }

    taskEXIT_CRITICAL();
    return errQUEUE_FULL;
}
```

### 关键点

对于二值信号量：

```
uxMessagesWaiting 最大只能为 1
```

因此连续两次 `give` 不会变成计数值 2。

如果两个中断事件分别代表两个必须处理的事件，二值信号量可能不适合，因为它会发生事件合并。

---

## 5.4 ISR 释放信号量的完整实现

```
static SemaphoreHandle_t g_adc_done_sem;

void DMA2_Stream0_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    if (DMA_GetFlagStatus(DMA2_Stream0, DMA_FLAG_TCIF0) != RESET)
    {
        DMA_ClearFlag(DMA2_Stream0, DMA_FLAG_TCIF0);

        /*
         * ISR 中只能使用 FromISR 版本。
         * 该调用不会直接进行完整调度，
         * 而是通过 higher_priority_task_woken 请求退出中断后切换。
         */
        xSemaphoreGiveFromISR(
            g_adc_done_sem,
            &higher_priority_task_woken);

        portYIELD_FROM_ISR(higher_priority_task_woken);
    }
}
```

对应任务：

```
static void AdcProcessTask(void *argument)
{
    for (;;)
    {
        BaseType_t ret;

        ret = xSemaphoreTake(
            g_adc_done_sem,
            pdMS_TO_TICKS(100));

        if (ret == pdPASS)
        {
            adc_process_one_block();
        }
        else
        {
            /*
             * 超时不是普通业务分支，
             * 通常应记录诊断信息并执行故障恢复。
             */
            adc_handle_timeout();
        }
    }
}
```

### 调度行为

假设：

```
当前运行任务：低优先级任务 L
等待任务：高优先级任务 H
ISR：释放信号量
```

如果 H 被唤醒：

```
ISR -> Give -> H 从阻塞态转为就绪态
ISR 退出 -> PendSV
调度器选择 H
```

若没有调用：

```
portYIELD_FROM_ISR(higher_priority_task_woken);
```

则 H 可能要等到：

- 当前任务主动让出 CPU；
- 下一个 Tick；
- 其他调度点。

这会直接增加事件响应延迟。

---

## 5.5 创建方式：动态与静态

### 动态创建

```
SemaphoreHandle_t sem = xSemaphoreCreateBinary();

if (sem == NULL)
{
    /*
     * 堆内存不足。
     * 生产系统不得忽略该错误。
     */
    system_fatal_error(SYSTEM_ERR_RTOS_OBJECT_CREATE);
}
```

风险：

- 依赖 FreeRTOS heap；
- 创建时可能碎片化；
- 创建失败时间不确定；
- 生命周期管理复杂。

### 静态创建

```
static StaticSemaphore_t s_adc_done_sem_buffer;
static SemaphoreHandle_t s_adc_done_sem;

void adc_sync_init(void)
{
    s_adc_done_sem = xSemaphoreCreateBinaryStatic(
        &s_adc_done_sem_buffer);

    configASSERT(s_adc_done_sem != NULL);
}
```

优点：

- 无动态内存；
- 地址固定；
- 生命周期明确；
- 更适合高可靠产品。

注意：

```
StaticSemaphore_t
```

的实际大小由端口和配置决定，不应自行假设结构体大小。

---

## 5.6 初始化状态问题

FreeRTOS 的二值信号量通常创建后为“空”状态：

```
创建 -> 不可获取
```

如果希望创建后立即可用，必须显式释放：

```
SemaphoreHandle_t sem = xSemaphoreCreateBinary();

configASSERT(sem != NULL);

if (xSemaphoreGive(sem) != pdPASS)
{
    system_fatal_error(SYSTEM_ERR_SEMAPHORE_INIT);
}
```

更推荐根据语义命名：

```
/* 用于“事件通知”：创建后保持不可用 */
adc_done_sem = xSemaphoreCreateBinary();

/* 用于“初始资源可用”：创建后显式 Give */
device_ready_sem = xSemaphoreCreateBinary();
xSemaphoreGive(device_ready_sem);
```

---

## 5.7 二值信号量的事件合并特性

假设 ISR 触发两次：

```
时刻 T1：give
时刻 T2：give
任务尚未 take
```

二值信号量状态：

```
T1 后：1
T2 后：仍为 1
```

任务只会成功获取一次。

因此：

|需求|是否适合二值信号量|
|---|---|
|“至少有一个事件发生，处理一次即可”|适合|
|“每个事件都必须被处理”|不适合|
|“DMA 完成后处理当前缓冲区”|通常适合|
|“每个 UART 字节都通知一次”|不适合|
|“设备从未准备好变为准备好”|适合|
|“累计多个生产请求”|使用计数信号量或队列|

---

## 5.8 内存可见性与数据一致性

在单核 Cortex-M 上，RTOS 临界区和中断同步通常能够保证合理的执行顺序，但二值信号量并不是数据缓存同步协议。

推荐模式：

```
static uint8_t s_rx_buffer[256];
static volatile size_t s_rx_length;
static SemaphoreHandle_t s_rx_ready_sem;

void USART1_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    size_t length = uart_hw_read_frame(
        s_rx_buffer,
        sizeof(s_rx_buffer));

    s_rx_length = length;

    /*
     * 数据写入完成后再发送同步信号。
     */
    xSemaphoreGiveFromISR(s_rx_ready_sem, &woken);

    portYIELD_FROM_ISR(woken);
}

static void UartParserTask(void *argument)
{
    for (;;)
    {
        if (xSemaphoreTake(
                s_rx_ready_sem,
                pdMS_TO_TICKS(50)) == pdPASS)
        {
            size_t length = s_rx_length;

            if (length <= sizeof(s_rx_buffer))
            {
                protocol_parse(s_rx_buffer, length);
            }
        }
    }
}
```

工程注意：

- DMA 缓冲区需要考虑 Cache 一致性；
- Cortex-M7 上需要进行 D-Cache clean/invalidate；
- 缓冲区所有权必须明确；
- 中断和任务不能同时修改同一段数据；
- 二值信号量只表示同步，不负责保护数据并发访问。

---

## 6. 性能量化分析

以下数据以一个典型测试平台为例：

```
MCU：STM32F407
CPU：Cortex-M4F，168 MHz
编译器：arm-none-eabi-gcc 12.x
优化：-O2
RTOS：FreeRTOS 10.x
Tick：1 kHz
端口：Cortex-M4 GCC
cache：无 D-Cache
测量方式：GPIO 翻转 + DWT CYCCNT
```

以下为**典型参考值**，实际结果取决于端口、编译器、临界区实现和配置。

## 6.1 内存开销

### 动态二值信号量

FreeRTOS 二值信号量底层通常复用队列控制块，但数据区长度为 0。

典型占用：

```
Queue_t 控制块：约 76~100 字节
堆管理额外开销：约 8~16 字节
总计：约 84~116 字节
```

### 静态二值信号量

```
StaticSemaphore_t：通常约 80~100 字节
不包含堆管理额外开销
```

实际值应以编译器：

```
sizeof(StaticSemaphore_t)
```

为准。

### 任务通知

任务通知使用任务控制块中的已有字段，通常不新增独立对象：

```
额外 RAM：接近 0 字节
```

因此在大量“一对一事件通知”场景中，任务通知比二值信号量更节省内存。

---

## 6.2 典型时间开销

参考测量结果：

|操作|典型 CPU 周期|168 MHz 下时间|
|---|---|---|
|`xSemaphoreGive()`，无等待任务|300~550 cycles|1.8~3.3 μs|
|`xSemaphoreGiveFromISR()`，无任务切换|250~500 cycles|1.5~3.0 μs|
|`xSemaphoreTake()`，信号已可用|250~450 cycles|1.5~2.7 μs|
|ISR 释放并唤醒高优先级任务|700~1500 cycles|4.2~8.9 μs|
|直接任务通知 Give/Take|150~350 cycles|0.9~2.1 μs|

换算公式：

```
时间 = CPU 周期数 / CPU 频率
```

例如：

```
1000 cycles / 168 MHz
= 5.95 μs
```

---

## 6.3 事件响应延迟

事件响应时间可以近似表示为：

```
Tresponse =
    Tinterrupt_entry
  + Tisr_give
  + Tscheduler
  + Tcontext_switch
  + Twakeup_task
```

典型组成：

```
中断进入：       0.3~1.0 μs
ISR Give：        1.5~3.0 μs
调度与切换：      2.0~5.0 μs
总响应：          4~10 μs
```

如果忘记调用：

```
portYIELD_FROM_ISR(higher_priority_task_woken);
```

则还要额外等待：

```
下一个调度点
```

在 1 kHz Tick 配置下，最坏情况下可能增加接近 **1 ms**，对高实时性链路是不可接受的。

---

## 6.4 超时精度

FreeRTOS 延时和信号量超时受 Tick 限制。

若：

```
configTICK_RATE_HZ = 1000
```

则 Tick 周期：

```
Ttick = 1 / 1000 = 1 ms
```

调用：

```
xSemaphoreTake(sem, pdMS_TO_TICKS(10));
```

实际超时时间通常存在 Tick 边界量化误差，可能约为：

```
9~11 ms
```

不要将软件 Tick 超时直接当成高精度定时器。

如果要求：

```
亚微秒或微秒级精确定时
```

应使用：

- 硬件定时器；
- 输入捕获；
- DMA；
- DWT；
- GPT/高精度系统定时器。

---

## 6.5 性能瓶颈分析

二值信号量本身通常不是系统主要瓶颈，常见瓶颈来源是：

1. **唤醒后的任务处理耗时过长**
    
    - 信号量只是触发入口；
    - 真正耗时可能在协议解析、滤波或日志输出。
2. **高频事件使用二值信号量**
    
    - 事件合并导致数据丢失；
    - 任务无法跟上生产速率。
3. **过多任务竞争同一个信号量**
    
    - 唤醒顺序不符合业务公平性；
    - 高优先级任务长期抢占。
4. **ISR 中执行过多逻辑**
    
    - ISR 释放信号量本身很快；
    - 但如果 ISR 还做数据搬运或协议解析，会导致系统抖动。
5. **错误的中断优先级**
    
    - FreeRTOS API 可调用的中断优先级受到 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 限制；
    - 配置错误可能直接触发断言或破坏内核状态。

---

## 6.6 优化手段与收益

|优化手段|预期收益|
|---|---|
|一对一通知改用任务通知|降低 RAM，减少约 20%~50% 同步路径开销|
|ISR 只采集状态并 Give|降低中断占用，改善抖动|
|合并高频事件|减少上下文切换次数|
|用 DMA 替代逐字节中断|显著降低 CPU 占用|
|任务通知与环形缓冲区组合|低开销传输数据|
|静态创建|消除堆碎片和运行时创建失败|
|批量处理 DMA 缓冲|提高缓存局部性和吞吐量|
|合理设置任务优先级|降低唤醒后的排队延迟|

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
需要同步或通信？
|
+-- 是否需要传递数据？
|   |
|   +-- 是
|   |   |
|   |   +-- 数据是否固定大小且生产/消费解耦？
|   |       |
|   |       +-- 是 -> 消息队列
|   |       +-- 否 -> 环形缓冲区 + 二值信号量/任务通知
|   |
|   +-- 否
|       |
|       +-- 是否保护共享资源？
|       |   |
|       |   +-- 是 -> 互斥锁
|       |
|       +-- 否，是否只需表达一个事件？
|           |
|           +-- 是
|           |   |
|           |   +-- 是否可能连续发生多个事件且不能丢失？
|           |       |
|           |       +-- 是 -> 计数信号量/队列
|           |       +-- 否
|           |           |
|           |           +-- 接收者是否固定为一个任务？
|           |               |
|           |               +-- 是 -> 任务通知
|           |               +-- 否 -> 二值信号量
|           |
|           +-- 否，是否有多个条件组合？
|               |
|               +-- 是 -> 事件标志组
```

## 7.2 典型场景选型

|场景需求|推荐方案|选择理由|
|---|---|---|
|DMA 一次完成，唤醒一个处理任务|二值信号量或任务通知|无需传递数据本体|
|UART 字节流接收|环形缓冲区 + 任务通知|每字节信号不可扩展|
|SPI 总线互斥访问|互斥锁|需要所有权和优先级继承|
|多个 DMA 块累计处理|计数信号量|不能合并事件|
|多任务等待设备初始化完成|二值信号量/事件组|需要广播时优先使用事件组|
|等待“网络已连接且时间已同步”|事件标志组|需要多个条件组合|
|单任务等待中断完成|直接任务通知|性能和 RAM 更优|
|中断携带一帧消息|队列或环形缓冲区|二值信号量不能传递数据|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：先定义事件语义，再选择对象

不要因为“中断唤醒任务”就机械使用二值信号量。

先回答：

```
事件是否允许合并？
事件是否需要累计？
是否需要传递数据？
是否有资源所有权？
是否需要多个任务同时感知？
```

### 原则二：二值信号量只负责同步，不负责数据保护

错误设计：

```
xSemaphoreTake(data_sem, ...);
shared_buffer_modify();
xSemaphoreGive(data_sem);
```

如果目的是保护共享缓冲区，应使用互斥锁或临界区。

### 原则三：ISR 只做最小工作

ISR 推荐做：

```
清中断标志
读取硬件状态
保存少量元数据
写入缓冲区
释放同步对象
请求调度
```

不推荐做：

```
复杂协议解析
大块 memcpy
浮点运算
printf
动态内存分配
阻塞等待
```

### 原则四：所有等待必须有超时

生产代码不应大量使用：

```
portMAX_DELAY
```

除非已经明确证明：

- 对象生命周期永久有效；
- 任务永远不需要退出；
- 系统不需要检测故障；
- 所有硬件异常都能被其他路径处理。

### 原则五：信号量命名体现方向和语义

推荐：

```
adc_dma_done_sem
uart_rx_frame_ready_sem
sensor_conversion_complete_sem
```

不推荐：

```
sem1
sync
event
flag
```

---

## 8.2 选型决策矩阵

评分范围：

```
1：不适合
3：可用
5：最佳
```

|需求|二值信号量|任务通知|计数信号量|事件组|互斥锁|消息队列|
|---|---|---|---|---|---|---|
|单任务事件通知|4|5|3|3|1|2|
|多任务共享事件|4|1|3|5|1|2|
|事件累计|1|3|5|1|1|4|
|资源保护|1|1|1|1|5|2|
|传递数据|1|3|1|1|1|5|
|ISR 低延迟|4|5|3|3|1|3|
|内存占用|3|5|3|3|2|1|
|优先级继承|1|1|1|1|5|1|

---

## 8.3 工业级编码规范

### 初始化检查

```
#define SEMAPHORE_ASSERT_VALID(sem) \
    configASSERT((sem) != NULL)
```

### 超时检查

```
BaseType_t ret = xSemaphoreTake(
    sem,
    pdMS_TO_TICKS(100));

if (ret != pdPASS)
{
    diagnostic_counter_increment(DIAG_SEM_TIMEOUT);
    fault_manager_report(FAULT_SENSOR_TIMEOUT);
}
```

### ISR API 检查

```
configASSERT(__get_IPSR() != 0U);
```

实际项目中不建议在所有路径中手动判断 ISR 上下文，而应通过接口设计确保：

```
任务接口：module_event_wait()
ISR 接口：module_event_signal_from_isr()
```

### 生命周期规范

对象销毁前必须满足：

```
停止生产者
关闭中断
等待使用者退出
确认没有挂起任务
删除信号量
```

---

## 9. 常见错误与避坑指南

## 9.1 错误一：在 ISR 中调用普通 API

### 错误代码

```
void EXTI0_IRQHandler(void)
{
    xSemaphoreGive(g_button_sem);  /* 错误 */
}
```

### 根因分析

普通 API 可能：

- 操作任务等待链表；
- 触发调度；
- 使用不允许在 ISR 中访问的临界区；
- 修改当前任务状态；
- 执行不适合中断上下文的代码。

### 正确实现

```
void EXTI0_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    EXTI_ClearITPendingBit(EXTI_Line0);

    xSemaphoreGiveFromISR(g_button_sem, &woken);

    portYIELD_FROM_ISR(woken);
}
```

### 风险影响

- HardFault；
- 内核链表破坏；
- 随机死锁；
- 任务状态异常；
- 偶现系统崩溃。

---

## 9.2 错误二：忘记 `portYIELD_FROM_ISR`

### 错误代码

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    xSemaphoreGiveFromISR(g_dma_sem, &woken);

    /* 忘记请求切换 */
}
```

### 根因分析

释放信号量只会使等待任务进入就绪态。若不触发调度，高优先级任务不会立即运行。

### 正确实现

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    DMA_ClearFlag();

    xSemaphoreGiveFromISR(g_dma_sem, &woken);

    portYIELD_FROM_ISR(woken);
}
```

### 风险影响

- 增加事件响应延迟；
- 实时性不稳定；
- 任务实际延迟到下一个 Tick；
- 造成 DMA 缓冲区覆盖。

---

## 9.3 错误三：用二值信号量累计事件

### 错误代码

```
void Sensor_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    xSemaphoreGiveFromISR(g_sensor_event_sem, &woken);
    xSemaphoreGiveFromISR(g_sensor_event_sem, &woken);

    portYIELD_FROM_ISR(woken);
}
```

### 根因分析

二值信号量最多保存一个“可用状态”，第二次释放不会累加为 2。

### 正确实现

使用计数信号量：

```
static SemaphoreHandle_t g_sensor_count_sem;

void Sensor_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    xSemaphoreGiveFromISR(g_sensor_count_sem, &woken);

    portYIELD_FROM_ISR(woken);
}

static void SensorTask(void *argument)
{
    for (;;)
    {
        if (xSemaphoreTake(
                g_sensor_count_sem,
                portMAX_DELAY) == pdPASS)
        {
            sensor_process_one_event();
        }
    }
}
```

或者使用队列记录事件时间戳、类型和序号。

### 风险影响

- 丢失采样事件；
- 数据帧不完整；
- 采样计数与实际硬件不一致；
- 触发协议超时。

---

## 9.4 错误四：用二值信号量保护共享资源

### 错误代码

```
/* 任务 A */
xSemaphoreTake(g_spi_sem, portMAX_DELAY);
spi_transfer();
xSemaphoreGive(g_spi_sem);

/* 任务 B 甚至 ISR 也可能直接 Give */
xSemaphoreGive(g_spi_sem);
```

### 根因分析

二值信号量没有可靠的所有权语义：

- 非持有者也可能释放；
- 不保证递归行为；
- 没有优先级继承；
- 不能正确表达资源占用者。

### 正确实现

```
static SemaphoreHandle_t g_spi_mutex;

void spi_init(void)
{
    g_spi_mutex = xSemaphoreCreateMutex();
    configASSERT(g_spi_mutex != NULL);
}

bool spi_transfer_guarded(
    const uint8_t *tx,
    uint8_t *rx,
    size_t length,
    TickType_t timeout)
{
    if (xSemaphoreTake(g_spi_mutex, timeout) != pdPASS)
    {
        return false;
    }

    bool ok = spi_transfer(tx, rx, length);

    xSemaphoreGive(g_spi_mutex);

    return ok;
}
```

### 风险影响

- 总线数据交错；
- 优先级反转；
- 设备片选时序破坏；
- 随机通信错误。

---

## 9.5 错误五：忽略中断优先级限制

### 错误代码

```
/* 在高优先级中断中调用 FreeRTOS FromISR API */
void HighPriority_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(g_sem, &woken);
}
```

### 根因分析

FreeRTOS 只允许满足配置约束的中断调用内核 API。

在 Cortex-M 上：

```
数值越小，硬件中断优先级越高
```

如果中断优先级高于：

```
configMAX_SYSCALL_INTERRUPT_PRIORITY
```

则不允许调用 FreeRTOS API。

### 正确实现

- 调整该中断优先级；
- 或者在 ISR 中只写硬件标志；
- 由允许调用 RTOS API 的中断或任务处理。

### 风险影响

- `configASSERT()` 触发；
- 临界区保护失效；
- 内核链表损坏；
- 极难复现的系统死机。

---

## 9.6 错误六：等待永不超时

### 错误代码

```
for (;;)
{
    xSemaphoreTake(g_device_ready_sem, portMAX_DELAY);

    device_run();
}
```

### 根因分析

设备可能因为以下原因永远不释放：

- 外设掉电；
- 中断未使能；
- DMA 错误；
- 信号量被错误删除；
- 硬件线路异常；
- ISR 优先级错误。

### 正确实现

```
for (;;)
{
    if (xSemaphoreTake(
            g_device_ready_sem,
            pdMS_TO_TICKS(1000)) == pdPASS)
    {
        device_run();
    }
    else
    {
        device_recover();
        fault_manager_report(FAULT_DEVICE_READY_TIMEOUT);
    }
}
```

### 风险影响

- 任务永久阻塞；
- 看门狗复位；
- 系统失去故障自愈能力；
- 无法区分正常等待和硬件失效。

---

## 10. 多机制组合使用方案

## 10.1 DMA + 环形缓冲区 + 二值信号量

适用于：

```
DMA 完成一次批量接收
任务被唤醒
任务处理缓冲区数据
```

架构：

```
UART/DMA ISR
    |
    +-- 写入环形缓冲区
    +-- 更新写指针
    +-- Give 二值信号量
                |
                v
          UART Parser Task
                |
                +-- Take
                +-- 读取环形缓冲区
                +-- 协议解析
```

### 代码框架

```
#include "FreeRTOS.h"
#include "semphr.h"
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define UART_RX_RING_SIZE 1024U

typedef struct
{
    uint8_t buffer[UART_RX_RING_SIZE];

    volatile uint32_t write_index;
    volatile uint32_t read_index;

    SemaphoreHandle_t data_ready_sem;
} uart_rx_context_t;

static uart_rx_context_t g_uart_rx;
static StaticSemaphore_t g_uart_rx_sem_storage;

static uint32_t ring_next(uint32_t index)
{
    return (index + 1U) % UART_RX_RING_SIZE;
}

static bool ring_push_byte(
    uart_rx_context_t *ctx,
    uint8_t byte)
{
    uint32_t next = ring_next(ctx->write_index);

    if (next == ctx->read_index)
    {
        /* 缓冲区满：丢弃、覆盖或进入故障处理 */
        return false;
    }

    ctx->buffer[ctx->write_index] = byte;
    ctx->write_index = next;

    return true;
}

static bool ring_pop_byte(
    uart_rx_context_t *ctx,
    uint8_t *byte)
{
    if (ctx->read_index == ctx->write_index)
    {
        return false;
    }

    *byte = ctx->buffer[ctx->read_index];
    ctx->read_index = ring_next(ctx->read_index);

    return true;
}

void uart_rx_init(void)
{
    memset(&g_uart_rx, 0, sizeof(g_uart_rx));

    g_uart_rx.data_ready_sem =
        xSemaphoreCreateBinaryStatic(
            &g_uart_rx_sem_storage);

    configASSERT(g_uart_rx.data_ready_sem != NULL);
}

void USART1_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    if (USART_GetITStatus(
            USART1,
            USART_IT_RXNE) != RESET)
    {
        uint8_t byte =
            (uint8_t)USART_ReceiveData(USART1);

        (void)ring_push_byte(&g_uart_rx, byte);

        /*
         * 二值信号量只表示“有数据可处理”，
         * 不表示具体有多少字节。
         */
        xSemaphoreGiveFromISR(
            g_uart_rx.data_ready_sem,
            &woken);

        portYIELD_FROM_ISR(woken);
    }
}

static void UartParserTask(void *argument)
{
    uint8_t byte;

    (void)argument;

    for (;;)
    {
        if (xSemaphoreTake(
                g_uart_rx.data_ready_sem,
                pdMS_TO_TICKS(100)) == pdPASS)
        {
            while (ring_pop_byte(&g_uart_rx, &byte))
            {
                protocol_parser_input(byte);
            }
        }
        else
        {
            protocol_parser_timeout();
        }
    }
}
```

### 设计要点

- 二值信号量只表示“缓冲区可能有数据”；
- 环形缓冲区保存实际数据；
- 生产者与消费者必须明确索引所有权；
- 高速数据链路应使用 DMA，不应逐字节触发高频任务切换；
- 缓冲区满时必须有明确策略：
    - 丢新数据；
    - 覆盖旧数据；
    - 记录溢出；
    - 复位协议状态机。

---

## 10.2 二值信号量 + 互斥锁

典型场景：

```
DMA 中断通知任务
任务获得信号后访问共享设备
多个任务访问设备时再使用互斥锁
```

禁止将两者语义混淆：

```
信号量：DMA 完成了吗？
互斥锁：谁可以访问共享 SPI 控制器？
```

---

## 10.3 二值信号量 + 事件标志组

适用于设备初始化：

```
任务 A：等待硬件 ready
任务 B：等待网络 ready
任务 C：等待校准完成
系统状态任务：等待多个条件
```

示例：

```
#define EVENT_HW_READY      (1UL << 0)
#define EVENT_NET_READY     (1UL << 1)
#define EVENT_CALIBRATED    (1UL << 2)

static EventGroupHandle_t g_system_events;

void device_init_done(void)
{
    xEventGroupSetBits(g_system_events, EVENT_HW_READY);
}

void calibration_done(void)
{
    xEventGroupSetBits(g_system_events, EVENT_CALIBRATED);
}

static void ApplicationTask(void *argument)
{
    EventBits_t bits;

    bits = xEventGroupWaitBits(
        g_system_events,
        EVENT_HW_READY |
        EVENT_NET_READY |
        EVENT_CALIBRATED,
        pdFALSE,
        pdTRUE,
        pdMS_TO_TICKS(5000));

    if ((bits & (
            EVENT_HW_READY |
            EVENT_NET_READY |
            EVENT_CALIBRATED)) ==
        (EVENT_HW_READY |
         EVENT_NET_READY |
         EVENT_CALIBRATED))
    {
        application_start();
    }
    else
    {
        application_start_degraded_mode();
    }
}
```

---

## 11. 工业级实际案例分析

## 11.1 案例一：ADC DMA 双缓冲采样

### 需求

- ADC 采样率：100 kHz；
- 每块缓冲区：256 个样本；
- DMA 半传输和全传输事件；
- 算法任务处理每块数据；
- 不能在 ISR 中执行 FFT。

### 架构

```
ADC -> DMA 双缓冲
          |
          +-- Half Complete ISR -> 设置 half 标志
          +-- Complete ISR      -> 设置 full 标志
                                      |
                                      v
                           ADC Processing Task
```

若只使用二值信号量：

```
半传输和全传输事件可能合并
```

因此更适合：

- 事件标志组；
- 任务通知位；
- 长度为 2 的消息队列；
- 两个二值信号量分别表示 half/full。

### 推荐代码：任务通知位

```
#define ADC_EVENT_HALF  (1UL << 0)
#define ADC_EVENT_FULL  (1UL << 1)

static TaskHandle_t g_adc_task_handle;

void DMA2_Stream0_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    uint32_t events = 0U;

    if (DMA_GetFlagStatus(
            DMA2_Stream0,
            DMA_FLAG_HTIF0) != RESET)
    {
        DMA_ClearFlag(DMA2_Stream0, DMA_FLAG_HTIF0);
        events |= ADC_EVENT_HALF;
    }

    if (DMA_GetFlagStatus(
            DMA2_Stream0,
            DMA_FLAG_TCIF0) != RESET)
    {
        DMA_ClearFlag(DMA2_Stream0, DMA_FLAG_TCIF0);
        events |= ADC_EVENT_FULL;
    }

    if (events != 0U)
    {
        xTaskNotifyFromISR(
            g_adc_task_handle,
            events,
            eSetBits,
            &woken);
    }

    portYIELD_FROM_ISR(woken);
}

static void AdcProcessTask(void *argument)
{
    uint32_t events;

    (void)argument;

    for (;;)
    {
        if (xTaskNotifyWait(
                0U,
                UINT32_MAX,
                &events,
                pdMS_TO_TICKS(100)) != pdPASS)
        {
            adc_report_timeout();
            continue;
        }

        if ((events & ADC_EVENT_HALF) != 0U)
        {
            adc_process_half_buffer(0U);
        }

        if ((events & ADC_EVENT_FULL) != 0U)
        {
            adc_process_half_buffer(1U);
        }
    }
}
```

### 设计要点

- 这里需要区分半块和整块，因此单纯二值信号量信息不足；
- 任务通知位可以携带事件类型；
- 如果处理速度低于采样速度，应增加缓冲深度；
- 必须计算：

```
处理时间 < 每半块数据到达周期
```

若采样率为 100 kHz，每半块 256 样本：

```
Tblock = 256 / 100000 = 2.56 ms
```

算法处理时间必须明显小于 2.56 ms，并预留中断和系统调度裕量。

---

## 11.2 案例二：温度传感器转换完成通知

### 需求

- 启动一次温度转换；
- 传感器转换完成后产生 GPIO 中断；
- 任务读取 I2C 数据；
- 转换超时后重新初始化传感器。

### 架构

```
Temperature Task
    |
    +-- I2C start conversion
    +-- Take conversion_done_sem
    |
GPIO ISR
    |
    +-- clear interrupt
    +-- Give conversion_done_sem
    |
Temperature Task
    |
    +-- read temperature
    +-- validate CRC
    +-- error recovery
```

### 核心代码

```
static SemaphoreHandle_t g_temp_conversion_done;
static StaticSemaphore_t g_temp_sem_storage;

static bool temperature_wait_conversion(
    TickType_t timeout)
{
    return xSemaphoreTake(
               g_temp_conversion_done,
               timeout) == pdPASS;
}

void TEMP_ALERT_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    temp_gpio_clear_irq();

    xSemaphoreGiveFromISR(
        g_temp_conversion_done,
        &woken);

    portYIELD_FROM_ISR(woken);
}

static void TemperatureTask(void *argument)
{
    (void)argument;

    for (;;)
    {
        if (!temperature_start_conversion())
        {
            temperature_recover();
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        if (!temperature_wait_conversion(
                pdMS_TO_TICKS(200)))
        {
            temperature_report_timeout();
            temperature_recover();
            continue;
        }

        float temperature;

        if (!temperature_read_value(&temperature))
        {
            temperature_report_crc_error();
            continue;
        }

        temperature_publish(temperature);

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void temperature_init(void)
{
    g_temp_conversion_done =
        xSemaphoreCreateBinaryStatic(
            &g_temp_sem_storage);

    configASSERT(g_temp_conversion_done != NULL);

    temp_gpio_irq_enable();
}
```

### 设计要点

- 转换开始前必须清理旧的中断状态；
- 必须避免上一次残留信号导致本次等待立即成功；
- 超时后应关闭中断、复位外设、重新初始化；
- 读取数据时应验证 CRC 和状态寄存器；
- 二值信号量适合表达“转换完成”，但不携带温度数据。

---

## 11.3 案例三：设备初始化完成广播

### 需求

多个任务都依赖设备初始化完成：

```
传感器任务
网络任务
日志任务
控制任务
```

### 错误方案

所有任务共享一个二值信号量：

```
初始化任务 Give 一次
只有一个等待任务成功获取
其他任务继续阻塞
```

### 正确方案

使用事件标志组，或者每个任务一个二值信号量。

如果要求广播：

```
static EventGroupHandle_t g_init_events;
#define INIT_SENSOR_READY  (1UL << 0)

void sensor_init_task(void *argument)
{
    if (sensor_init() == true)
    {
        xEventGroupSetBits(
            g_init_events,
            INIT_SENSOR_READY);
    }
}
```

多个任务可以分别等待同一个事件位，且事件位可以配置为等待后不清除。

### 设计结论

|需求|推荐|
|---|---|
|只有一个任务等待初始化完成|二值信号量|
|多个任务都必须感知初始化完成|事件标志组|
|每个任务需要独立确认|每个任务独立二值信号量|
|初始化结果需要携带错误码|全局状态 + 事件标志组|

---

## 12. 高频问题深度答疑

## 问题一：二值信号量和互斥锁到底如何区分？

判断标准不是“是否只有 0 和 1”，而是：

```
是否存在资源所有权？
```

如果任务 A 获取后，只有任务 A 才能释放，则是资源保护语义，应使用互斥锁。

如果 ISR 或任务 B 可以释放，用于通知任务 C，则是事件同步语义，应使用二值信号量。

---

## 问题二：二值信号量是否会丢事件？

会。

只要出现：

```
多个 Give 发生在同一个 Take 之前
```

则多个事件可能合并成一个。

因此要区分：

```
事件发生过至少一次
```

和：

```
事件发生了 N 次，每一次都必须处理
```

前者使用二值信号量，后者使用：

- 计数信号量；
- 队列；
- 事件序列号；
- 环形缓冲区；
- 任务通知计数模式。

---

## 问题三：为什么不用全局 `volatile bool`？

简单场景下：

```
volatile bool event_flag;
```

可以表达状态，但存在问题：

- 任务无法高效阻塞等待；
- 需要主动轮询；
- 浪费 CPU；
- 可能有竞态；
- 无法直接挂入 RTOS 等待队列；
- 无法自然处理超时；
- 不具备任务唤醒和调度语义。

推荐：

```
状态：volatile 变量
同步：RTOS 信号量/通知
数据：缓冲区或队列
```

三者职责分离。

---

## 问题四：二值信号量能否从多个 ISR 释放？

可以，但必须确认事件语义允许合并。

例如：

```
多个 GPIO 都表示“设备异常”
```

可以使用一个二值信号量。

但是：

```
多个 ADC 通道分别产生采样完成事件
```

若需要知道具体通道，应使用：

- 事件标志组；
- 任务通知位；
- 队列；
- 多个二值信号量。

---

## 问题五：为什么任务拿到信号量后仍然读不到有效数据？

常见原因：

1. ISR 先 Give，后写数据；
2. DMA 尚未真正完成；
3. Cache 未失效；
4. 缓冲区被下一次 DMA 覆盖；
5. 多个生产者竞争同一缓冲区；
6. 任务读取时未保存写指针快照；
7. 信号量只通知状态，没有传递数据长度。

正确顺序应是：

```
停止/确认 DMA
写入或确认数据完成
更新长度和指针
清除硬件状态
Give 信号量
```

---

## 问题六：二值信号量是否能够解决优先级反转？

不能。

二值信号量通常没有优先级继承。

如果用于保护共享资源，可能出现：

```
低优先级任务 L 持有资源
高优先级任务 H 等待资源
中优先级任务 M 抢占 L
H 长时间无法运行
```

应改用支持优先级继承的互斥锁，或者重新设计资源访问架构。

---

## 13. 课程核心总结

## 13.1 核心要点

1. **二值信号量用于事件同步，不用于资源所有权保护。**
2. 它只有“可用 / 不可用”两个状态。
3. 多次释放不会累积事件，存在事件合并风险。
4. ISR 中必须使用 `FromISR` API。
5. ISR 释放后必须根据返回值调用 `portYIELD_FROM_ISR()`。
6. 二值信号量通常不支持优先级继承。
7. 二值信号量本身不携带数据，应与缓冲区、环形队列或状态变量配合使用。
8. 每个等待路径都应有超时和故障恢复策略。
9. 单任务、一对一、低开销场景优先考虑直接任务通知。
10. 多任务广播和多条件组合优先考虑事件标志组。

## 13.2 性能排序

在典型 FreeRTOS Cortex-M 系统中：

```
直接任务通知
    >
二值信号量 / 计数信号量
    >
事件标志组
    >
消息队列
```

这里的“>”表示典型同步路径性能更高，并不是所有平台的绝对结论。

## 13.3 通用选型结论

```
一个事件，接收者固定为一个任务：
    优先任务通知

一个事件，接收者可能由模块解耦：
    二值信号量

多个事件不能丢失：
    计数信号量或队列

需要传递数据：
    消息队列或环形缓冲区

保护共享资源：
    互斥锁

多个条件组合：
    事件标志组
```

---

## 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐机制|备注|
|---|---|---|
|ISR 通知任务一次事件|二值信号量|可被合并|
|DMA 完成通知|二值信号量/任务通知|需要区分半满/全满时使用事件位|
|UART 数据接收|环形缓冲区 + 通知|不要逐字节使用二值信号量|
|多次事件累计|计数信号量|每次事件对应一次 Take|
|保护 SPI/I2C|互斥锁|需要优先级继承|
|多任务等待系统状态|事件标志组|支持广播|
|单任务快速通知|任务通知|RAM 和延迟最优|
|传递固定大小消息|消息队列|自带数据复制|
|传递大块数据|指针队列 + 内存池|避免大块复制|

## 14.2 API 速查表

|需求|API|
|---|---|
|动态创建|`xSemaphoreCreateBinary()`|
|静态创建|`xSemaphoreCreateBinaryStatic()`|
|任务获取|`xSemaphoreTake()`|
|任务释放|`xSemaphoreGive()`|
|ISR 获取|通常不允许|
|ISR 释放|`xSemaphoreGiveFromISR()`|
|删除|`vSemaphoreDelete()`|
|检查是否有效|`configASSERT(sem != NULL)`|
|ISR 请求切换|`portYIELD_FROM_ISR(woken)`|

## 14.3 关键约束表

|项目|约束|
|---|---|
|ISR API|只能使用 `FromISR` 版本|
|中断优先级|必须满足 FreeRTOS API 调用限制|
|事件累计|二值信号量不支持|
|优先级继承|二值信号量通常不支持|
|数据传输|二值信号量不携带用户数据|
|超时|推荐所有等待都设置合理超时|
|对象删除|必须先停止所有访问者|
|Cache|Cortex-M7 等平台需考虑 DMA Cache 一致性|

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

### 基础能力

- [ ]  能解释二值信号量的两个状态。
- [ ]  能区分二值信号量和互斥锁。
- [ ]  能解释为什么二值信号量会合并多个事件。
- [ ]  能说明二值信号量为何不能传递数据。

### API 能力

- [ ]  能正确使用 `xSemaphoreCreateBinaryStatic()`。
- [ ]  能正确使用 `xSemaphoreTake()` 并处理超时。
- [ ]  能正确使用 `xSemaphoreGiveFromISR()`。
- [ ]  能正确调用 `portYIELD_FROM_ISR()`。
- [ ]  能检查创建失败和释放失败。

### 内核理解

- [ ]  能说明二值信号量在 FreeRTOS 中基于队列实现。
- [ ]  能说明任务如何进入信号量等待链表。
- [ ]  能说明 ISR 释放后任务如何从阻塞态进入就绪态。
- [ ]  能解释检查条件与加入等待队列为什么必须原子化。

### 工程设计能力

- [ ]  能设计 DMA 完成通知任务的方案。
- [ ]  能设计环形缓冲区加二值信号量的 UART 接收方案。
- [ ]  能识别二值信号量可能造成的事件丢失。
- [ ]  能选择任务通知、计数信号量、事件组和消息队列。
- [ ]  能为等待超时设计恢复机制。
- [ ]  能分析优先级反转风险。

### 性能验证能力

- [ ]  能使用 DWT CYCCNT 测量信号量路径。
- [ ]  能使用 GPIO 翻转测量 ISR 到任务的响应延迟。
- [ ]  能根据采样率计算任务处理时间预算。
- [ ]  能识别上下文切换次数过多造成的实时性问题。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：基础二值信号量

实现：

```
按键中断 -> 二值信号量 -> 按键处理任务
```

要求：

- 消除按键抖动；
- 任务等待超时；
- 统计按键事件数量；
- 不允许在 ISR 中执行打印。

### 任务二：DMA 完成同步

实现：

```
ADC DMA -> 中断 -> 二值信号量 -> 采样处理任务
```

要求：

- 采集 256 点；
- 计算平均值、最大值和最小值；
- 记录 DMA 超时次数；
- 使用 GPIO 测量从 DMA 中断到任务开始执行的延迟。

### 任务三：UART 环形缓冲区

实现：

```
UART RX ISR -> 环形缓冲区 -> 二值信号量 -> 协议解析任务
```

要求：

- 支持帧头、长度、校验和；
- 处理环形缓冲区满；
- 统计丢包和溢出；
- 处理半帧超时；
- 禁止逐字节创建任务或发送消息队列。

### 任务四：机制替换对比

分别使用以下机制实现同一个 DMA 通知功能：

```
二值信号量
直接任务通知
事件标志组
消息队列
```

测量：

- RAM 占用；
- Give/Take CPU 周期；
- ISR 到任务响应时间；
- 高负载下的延迟抖动；
- 代码可维护性。

### 任务五：故障注入

注入以下故障：

```
屏蔽 DMA 中断
错误设置 NVIC 优先级
删除仍在使用的信号量
连续产生高频事件
任务处理时间超过事件周期
```

要求：

- 系统检测超时；
- 记录故障原因；
- 进入降级模式；
- 能够恢复外设；
- 看门狗不会被无意义地喂狗掩盖问题。

---

## 16.2 性能测试方法

### 方法一：DWT 周期计数

```
static inline void dwt_start(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static inline uint32_t dwt_get_cycles(void)
{
    return DWT->CYCCNT;
}
```

测量：

```
uint32_t start = dwt_get_cycles();

xSemaphoreGive(g_sem);

uint32_t cycles = dwt_get_cycles() - start;
```

### 方法二：GPIO 逻辑分析

```
void DMA_IRQHandler(void)
{
    gpio_set(DEBUG_PIN);

    BaseType_t woken = pdFALSE;

    xSemaphoreGiveFromISR(g_sem, &woken);
    portYIELD_FROM_ISR(woken);

    gpio_clear(DEBUG_PIN);
}
```

在任务入口处翻转另一个 GPIO：

```
static void ProcessTask(void *argument)
{
    for (;;)
    {
        xSemaphoreTake(g_sem, portMAX_DELAY);

        gpio_set(PROCESS_PIN);
        process_data();
        gpio_clear(PROCESS_PIN);
    }
}
```

测量：

```
ISR GPIO 上升沿 -> 任务 GPIO 上升沿
```

即为端到端唤醒延迟。

### 方法三：高负载测试

测试条件应覆盖：

- CPU 占用率 30%；
- CPU 占用率 70%；
- CPU 占用率 90%；
- 同优先级任务竞争；
- 高优先级周期任务抢占；
- 禁止和允许时间片；
- 多个中断同时发生。

重点统计：

```
平均延迟
最大延迟
99.9 分位延迟
丢事件数量
信号量超时数量
任务栈峰值
CPU 占用率
```

---

## 16.3 进阶学习方向

1. FreeRTOS 源码：
    - `queue.c`
    - `tasks.c`
    - `list.c`
    - `port.c`
2. 优先级反转与优先级继承。
3. 事件标志组与多条件同步。
4. 任务通知的：
    - 计数模式；
    - 位模式；
    - 覆盖模式；
    - 索引通知模式。
5. DMA 与 Cache 一致性。
6. 多核 RTOS 中的自旋锁、内存屏障和跨核通知。
7. Tracealyzer、Percepio、SEGGER SystemView。
8. 时间确定性分析：
    - WCET；
    - 中断响应时间；
    - 调度延迟；
    - 抖动预算。
9. 功能安全中的同步对象生命周期和故障诊断。
10. 基于形式化状态机验证同步协议和错误恢复路径。