
## 1. 学习目标

### 理解

- 理解 RTOS 任务、线程控制块（TCB）、任务栈、任务状态与调度器之间的关系。
- 理解任务创建、就绪、阻塞、挂起、删除的生命周期。
- 理解静态创建与动态创建在内存、确定性和资源管理方面的差异。

### 掌握

- 掌握 FreeRTOS 任务创建 API、任务参数传递、优先级配置和栈深度配置。
- 掌握任务删除、任务自删除、外部删除和资源回收机制。
- 掌握任务栈水位、任务句柄、任务状态查询和运行时监控。

### 精通

- 能够分析 TCB、任务栈、上下文切换和空闲任务回收机制。
- 能够定位任务创建失败、栈溢出、优先级反转、删除后资源泄漏等问题。
- 能够设计满足实时性、内存确定性和故障恢复要求的任务生命周期管理方案。

### 能够设计

- 能够设计工业级任务启动、运行、停止、重启和资源释放框架。
- 能够根据产品约束选择静态任务、动态任务或混合方案。
- 能够建立任务栈、CPU 占用、创建失败和异常退出的可观测性体系。

## 2. 前置要求

### 知识要求

- C 语言函数指针、结构体、枚举、指针生命周期和内存管理。
- MCU 中断、异常、堆栈和上下文切换基本原理。
- 优先级抢占式调度、临界区和同步原语。
- 至少一种 MCU 架构，例如 Cortex-M。

### 技能要求

- 能够独立编译和下载 FreeRTOS 工程。
- 能够使用调试器查看任务栈、寄存器和异常现场。
- 能够使用逻辑分析仪、示波器或 DWT 周期计数器进行时序测量。
- 能够阅读 RTOS 移植层和内核源码。

## 3. 技术概述

RTOS 任务是一个具有独立执行上下文的调度实体，通常包含：

```
任务入口函数
任务控制块 TCB
任务栈 Stack
优先级 Priority
任务状态 State
任务句柄 Handle
```

任务本质上不是普通函数调用。普通函数由调用者管理调用栈和返回地址，而 RTOS 任务由内核保存：

- 当前栈指针；
- CPU 通用寄存器；
- 程序计数器；
- 状态寄存器；
- 调度优先级；
- 阻塞对象和超时信息；
- 任务名称、运行统计等诊断信息。

主流任务创建方式：

|方案|典型 API|内存来源|确定性|适用场景|
|---|---|---|---|---|
|动态创建|`xTaskCreate()`|RTOS Heap|中|原型、资源动态变化|
|静态创建|`xTaskCreateStatic()`|用户提供数组|高|工业产品、安全关键系统|
|动态分配 TCB 和栈|`heap_4/heap_5`|RTOS 堆|中|一般 MCU 产品|
|静态 TCB，动态栈|需自行封装|混合|中高|特殊内存布局|
|任务池|自定义对象池|固定内存池|高|频繁创建和删除|
|线程封装|CMSIS-RTOS、RT-Thread API|由适配层决定|取决于内核|跨 RTOS 兼容|

## 4. 核心特性横向对比

|对比维度|动态任务|静态任务|任务池|
|---|---|---|---|
|创建灵活性|高|中|中|
|创建时间确定性|较低|高|高|
|堆碎片风险|有|无|无|
|任务栈地址|内核分配|用户指定|池中固定|
|删除后自动释放|依赖配置和空闲任务|不需要释放内存|归还池|
|适合长期任务|可以|推荐|可以|
|适合频繁创建删除|不推荐|可行但管理复杂|推荐|
|调试可预测性|中|高|高|
|RAM 利用率|可能更高|固定占用|固定占用|
|安全认证友好性|较弱|较强|较强|

任务状态：

|状态|含义|是否参与调度|
|---|---|---|
|Running|当前正在运行|是|
|Ready|满足运行条件|是|
|Blocked|等待事件或超时|否|
|Suspended|被显式挂起|否|
|Deleted|从调度列表移除|否|

## 5. 底层原理与功能特性深度解析

### 5.1 任务控制块与任务栈

以 FreeRTOS 为例，任务控制块通常包含以下逻辑字段：

```
typedef struct
{
    StackType_t *pxTopOfStack;
    ListItem_t   xStateListItem;
    ListItem_t   xEventListItem;
    UBaseType_t  uxPriority;
    StackType_t *pxStack;
    char         pcTaskName[configMAX_TASK_NAME_LEN];
} TCB_t;
```

不同 FreeRTOS 版本的字段布局可能不同，不能直接依赖内部结构体。工程代码应通过公开 API 获取信息。

任务栈保存：

```
高地址
+-------------------------+
| 任务局部变量            |
| 保存的寄存器            |
| 异常返回信息            |
| 初始 PC = 任务入口      |
| 初始 LR = 任务退出处理  |
+-------------------------+
低地址
```

Cortex-M 任务切换一般由 PendSV 完成：

```
void vPortPendSVHandler(void)
{
    /*
     * 实际实现通常为汇编：
     * 1. 读取 PSP
     * 2. 保存 r4-r11
     * 3. 写回当前 TCB 的栈指针
     * 4. 调用 vTaskSwitchContext()
     * 5. 从新任务 TCB 恢复栈指针
     * 6. 恢复 r4-r11
     * 7. 异常返回到新任务
     */
}
```

关键结论：

**任务切换的本质是切换栈指针，而不是调用另一个函数。**

### 5.2 动态创建任务

```
#include "FreeRTOS.h"
#include "task.h"

static void SensorTask(void *argument)
{
    const uint32_t period_ms = 10U;

    for (;;)
    {
        sensor_sample();

        /*
         * 使用 vTaskDelayUntil 保证周期基于绝对时间，
         * 避免任务执行时间叠加导致周期漂移。
         */
        vTaskDelay(pdMS_TO_TICKS(period_ms));
    }
}

BaseType_t App_CreateSensorTask(void)
{
    TaskHandle_t handle = NULL;

    BaseType_t result = xTaskCreate(
        SensorTask,
        "sensor",
        384U,              /* 单位通常为 StackType_t，不是字节 */
        NULL,
        5U,
        &handle
    );

    if (result != pdPASS)
    {
        log_error("sensor task create failed");
        return pdFAIL;
    }

    return pdPASS;
}
```

必须注意：`xTaskCreate()` 的栈参数通常是 **栈元素数量**。

例如 Cortex-M 上：

```
StackType_t = uint32_t
384 个栈元素 = 384 × 4 = 1536 字节
```

错误示例：

```
xTaskCreate(SensorTask, "sensor", 1536U, NULL, 5U, NULL);
```

这会实际申请约 6144 字节，而不是 1536 字节。

### 5.3 静态创建任务

```
#define SENSOR_TASK_STACK_WORDS 384U

static StaticTask_t sensor_tcb;
static StackType_t sensor_stack[SENSOR_TASK_STACK_WORDS];
static TaskHandle_t sensor_handle;

BaseType_t App_CreateSensorTaskStatic(void)
{
    sensor_handle = xTaskCreateStatic(
        SensorTask,
        "sensor",
        SENSOR_TASK_STACK_WORDS,
        NULL,
        5U,
        sensor_stack,
        &sensor_tcb
    );

    if (sensor_handle == NULL)
    {
        log_error("static sensor task create failed");
        return pdFAIL;
    }

    return pdPASS;
}
```

静态对象应放入明确的内存区域：

```
__attribute__((section(".rtos_stack")))
static StackType_t sensor_stack[SENSOR_TASK_STACK_WORDS];

__attribute__((section(".rtos_tcb")))
static StaticTask_t sensor_tcb;
```

这样可以通过链接脚本将任务栈放入：

- DTCM；
- SRAM1；
- 低功耗保持 RAM；
- MPU 配置的独立区域；
- 带 ECC 的安全 RAM。

### 5.4 任务参数传递

不建议把局部变量地址传给任务：

```
void App_Start(void)
{
    SensorConfig_t config = {
        .channel = 2U
    };

    xTaskCreate(SensorTask, "sensor", 384U, &config, 5U, NULL);
} /* config 生命周期结束，任务中继续访问将产生悬空指针 */
```

正确方式一：静态全局配置：

```
static const SensorConfig_t sensor_config = {
    .channel = 2U,
    .sample_period_ms = 10U
};

static void SensorTask(void *argument)
{
    const SensorConfig_t *config = argument;

    configASSERT(config != NULL);

    for (;;)
    {
        sensor_sample_channel(config->channel);
        vTaskDelay(pdMS_TO_TICKS(config->sample_period_ms));
    }
}
```

正确方式二：动态分配后由任务接管并释放：

```
static void WorkerTask(void *argument)
{
    WorkerConfig_t *config = argument;

    if (config == NULL)
    {
        vTaskDelete(NULL);
        return;
    }

    worker_init(config);

    vPortFree(config);

    for (;;)
    {
        worker_process();
        vTaskDelay(pdMS_TO_TICKS(10U));
    }
}
```

这种模式必须明确所有权：**创建方分配，任务成功启动后接管，任务完成初始化后释放。**

### 5.5 任务删除机制

任务可以删除自己：

```
static void OneShotTask(void *argument)
{
    (void)argument;

    perform_one_shot_operation();

    /*
     * 删除自身。不会返回。
     */
    vTaskDelete(NULL);

    configASSERT(false);
}
```

也可以由其他任务删除：

```
BaseType_t App_StopTask(TaskHandle_t *handle)
{
    if ((handle == NULL) || (*handle == NULL))
    {
        return pdFAIL;
    }

    vTaskDelete(*handle);

    *handle = NULL;
    return pdPASS;
}
```

但是，`vTaskDelete()` 不会自动释放任务持有的业务资源：

```
不会自动关闭：
- 互斥锁逻辑所有权
- 文件描述符
- DMA 通道
- 外设句柄
- 网络连接
- 用户分配的内存
- 注册到其他模块的回调
```

动态任务的 TCB 和栈通常由 **Idle Task** 延迟释放。因此删除后内存不会立即回收。

### 5.6 推荐的可控停止模型

不要直接从外部强制删除长期运行任务，推荐使用停止请求：

```
typedef struct
{
    TaskHandle_t handle;
    EventGroupHandle_t events;
    StaticEventGroup_t event_storage;
} ServiceControl_t;

#define SERVICE_STOP_BIT    (1UL << 0)

static ServiceControl_t service_ctrl;

static void ServiceTask(void *argument)
{
    ServiceControl_t *ctrl = argument;

    for (;;)
    {
        EventBits_t bits = xEventGroupWaitBits(
            ctrl->events,
            SERVICE_STOP_BIT,
            pdTRUE,
            pdFALSE,
            pdMS_TO_TICKS(100U)
        );

        if ((bits & SERVICE_STOP_BIT) != 0U)
        {
            service_deinit();
            ctrl->handle = NULL;
            vTaskDelete(NULL);
        }

        service_process_once();
    }
}

BaseType_t Service_Stop(TickType_t timeout)
{
    if (service_ctrl.handle == NULL)
    {
        return pdPASS;
    }

    xEventGroupSetBits(service_ctrl.events, SERVICE_STOP_BIT);

    TickType_t start = xTaskGetTickCount();

    while (service_ctrl.handle != NULL)
    {
        if ((xTaskGetTickCount() - start) >= timeout)
        {
            return pdTIMEOUT;
        }

        vTaskDelay(pdMS_TO_TICKS(1U));
    }

    return pdPASS;
}
```

这种方式支持：

- 业务资源释放；
- 外设反初始化；
- DMA 停止；
- 队列清理；
- 有限时间等待；
- 停止超时故障上报。

## 6. 性能量化分析

以下数据为典型 Cortex-M4F、168 MHz、FreeRTOS、GCC `-O2` 环境下的工程测量参考值，实际数据必须在目标平台重新测量。

### 内存开销

假设：

```
TCB：约 100～160 字节
任务栈：N × sizeof(StackType_t)
Cortex-M：sizeof(StackType_t) = 4 字节
```

任务总 RAM 估算：

```
RAM_task ≈ sizeof(TCB)
         + N × sizeof(StackType_t)
         + 堆管理元数据
         + 应用对象
```

例如：

```
TCB                   128 B
栈 384 words          1536 B
堆块管理元数据        8～16 B
任务句柄及控制对象    16～32 B
--------------------------------
约                    1.7 KB
```

### 时间开销

典型参考值：

|操作|典型耗时|
|---|---|
|`xTaskCreate()`|5～30 us|
|`xTaskCreateStatic()`|2～10 us|
|`vTaskDelete()`|1～5 us|
|一次普通上下文切换|1～5 us|
|任务从阻塞转就绪|取决于列表和配置|
|Idle Task 回收删除任务|通常小于数十 us|

测量代码：

```
static uint32_t MeasureCreateCycles(void)
{
    uint32_t start;
    uint32_t end;

    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    start = DWT->CYCCNT;

    BaseType_t result = App_CreateSensorTaskStatic();

    end = DWT->CYCCNT;

    configASSERT(result == pdPASS);

    return end - start;
}
```

耗时换算：

```
time_us = cycle_count / CPU_frequency_MHz
```

例如 168 MHz 下，840 个周期：

```
840 / 168 = 5 us
```

### 栈使用量

```
UBaseType_t words_free = uxTaskGetStackHighWaterMark(sensor_handle);

size_t bytes_free =
    (size_t)words_free * sizeof(StackType_t);
```

栈安全阈值建议：

```
开发阶段：保留 30% 以上余量
量产阶段：保留 20% 以上余量
安全关键任务：基于最坏路径和故障注入验证
```

### 主要瓶颈

- 任务栈配置过大导致 RAM 浪费。
- 任务栈配置过小导致栈溢出。
- 动态创建和删除导致堆碎片。
- 频繁创建任务导致调度和内存管理开销。
- 删除任务后资源未释放。
- 高优先级任务长期不阻塞导致低优先级任务饥饿。

优化手段：

|问题|优化方式|典型收益|
|---|---|---|
|栈过大|依据高水位和最坏调用路径裁剪|RAM 降低 10%～40%|
|频繁创建|使用常驻任务或任务池|创建开销接近 0|
|堆碎片|使用静态对象或 `heap_5` 分区|确定性显著提升|
|周期漂移|使用绝对延时|周期误差降低到 tick 级|
|栈溢出|栈填充、高水位、MPU 保护|提前发现越界|

## 7. 应用场景选型指南

### 决策流程图

```
是否需要运行时动态增加任务？
├─ 否
│  ├─ 是否要求启动和内存完全确定？
│  │  ├─ 是 -> 静态创建
│  │  └─ 否 -> 可使用动态创建，但启动阶段一次性创建
│
└─ 是
   ├─ 是否频繁创建和删除？
   │  ├─ 是
   │  │  ├─ 任务行为是否同质？
   │  │  │  ├─ 是 -> 任务池
   │  │  │  └─ 否 -> 常驻管理任务 + 动态对象
   │  │
   │  └─ 否 -> 动态创建，配合堆碎片监测
```

|场景|推荐方案|理由|
|---|---|---|
|电机控制任务|静态创建|周期和内存必须确定|
|传感器采集任务|静态创建或启动阶段动态创建|长期运行，不需要反复创建|
|OTA 下载任务|常驻任务 + 状态机|避免删除时资源泄漏|
|TCP 会话处理|任务池或事件驱动|连接数量动态变化|
|工厂测试模式|动态创建|测试模块生命周期不固定|
|安全关键任务|静态创建 + MPU|可验证性和隔离性更好|
|大量短任务|不建议独立任务|使用消息队列和工作线程|

## 8. 工程最佳实践

### 设计原则

1. **系统任务在启动阶段一次性创建。**
2. **长期服务优先采用常驻任务，不通过反复删除和重建实现状态切换。**
3. **任务退出前必须释放业务资源。**
4. **禁止任务入口函数自然返回。**
5. **任务参数必须具有明确生命周期和所有权。**
6. **所有任务创建结果必须检查。**
7. **任务栈必须通过高水位和最坏路径验证。**
8. **高优先级任务必须具有明确阻塞点。**
9. **外部停止优先使用消息、事件或通知，不直接删除。**
10. **任务句柄在删除后立即清零或进入无效状态。**

### 选型决策矩阵

|需求|静态创建|动态创建|任务池|
|---|---|---|---|
|内存确定性|5|2|5|
|生命周期灵活性|3|5|4|
|低碎片风险|5|2|5|
|开发简单度|4|5|3|
|高频创建删除|2|1|5|
|安全认证|5|2|4|

### 工业级编码规范

```
#define APP_SENSOR_TASK_PRIORITY    (5U)
#define APP_SENSOR_TASK_STACK_WORDS (384U)

static TaskHandle_t s_sensor_task = NULL;

BaseType_t App_SensorStart(void)
{
    if (s_sensor_task != NULL)
    {
        return pdPASS;
    }

    s_sensor_task = xTaskCreateStatic(
        SensorTask,
        "sensor",
        APP_SENSOR_TASK_STACK_WORDS,
        NULL,
        APP_SENSOR_TASK_PRIORITY,
        s_sensor_stack,
        &s_sensor_tcb
    );

    return (s_sensor_task != NULL) ? pdPASS : pdFAIL;
}
```

## 9. 常见错误与避坑指南

### 错误一：任务函数直接返回

错误代码：

```
static void TaskEntry(void *argument)
{
    init_service();
    return;
}
```

根因：任务入口不是普通函数调用，返回地址通常是内核预设的异常处理函数或不可用地址。

正确实现：

```
static void TaskEntry(void *argument)
{
    init_service();

    for (;;)
    {
        service_run();
        vTaskDelay(pdMS_TO_TICKS(10U));
    }
}
```

或者一次性任务：

```
static void TaskEntry(void *argument)
{
    one_shot_work();
    vTaskDelete(NULL);
}
```

风险影响：HardFault、任务状态异常、系统不可预测。

### 错误二：把字节数当成栈深度

错误代码：

```
xTaskCreate(TaskEntry, "task", 1024U, NULL, 3U, NULL);
```

根因：FreeRTOS 栈深度单位通常是 `StackType_t` 数量。

正确实现：

```
#define TASK_STACK_BYTES 1024U
#define TASK_STACK_WORDS \
    (TASK_STACK_BYTES / sizeof(StackType_t))

xTaskCreate(
    TaskEntry,
    "task",
    TASK_STACK_WORDS,
    NULL,
    3U,
    NULL
);
```

风险影响：实际分配栈空间扩大数倍，造成 RAM 不足。

### 错误三：删除任务但未释放资源

错误代码：

```
vTaskDelete(task_handle);
```

根因：RTOS 只负责回收内核任务对象，不知道应用层资源。

正确实现：

```
service_stop_dma();
service_close_socket();
service_unregister_callback();
service_free_buffers();

vTaskDelete(NULL);
```

风险影响：DMA 通道泄漏、回调访问已释放对象、网络连接残留、内存泄漏。

### 错误四：任务参数指向局部变量

错误代码：

```
void Start(void)
{
    uint32_t channel = 1U;
    xTaskCreate(TaskEntry, "task", 256U, &channel, 3U, NULL);
}
```

根因：`Start()` 返回后，`channel` 生命周期结束。

正确实现：

```
static uint32_t s_channel = 1U;

void Start(void)
{
    xTaskCreate(TaskEntry, "task", 256U,
                &s_channel, 3U, NULL);
}
```

风险影响：任务读取随机数据，可能导致越界访问或错误配置外设。

### 错误五：高优先级任务不阻塞

错误代码：

```
static void HighPriorityTask(void *argument)
{
    for (;;)
    {
        poll_hardware();
    }
}
```

根因：任务始终处于 Running/Ready，不给低优先级任务运行机会。

正确实现：

```
static void HighPriorityTask(void *argument)
{
    for (;;)
    {
        if (hardware_event_ready())
        {
            process_hardware_event();
        }

        ulTaskNotifyTake(
            pdTRUE,
            pdMS_TO_TICKS(100U)
        );
    }
}
```

风险影响：CPU 满载、系统任务饥饿、通信协议栈无法运行。

## 10. 多机制组合使用方案

推荐采用：

```
硬件中断
   |
   v
任务通知 / 队列
   |
   v
常驻服务任务
   |
   +--> 状态机
   +--> DMA
   +--> 超时控制
   +--> 停止请求
   +--> 资源释放
```

完整框架：

```
typedef enum
{
    SERVICE_STATE_INIT = 0,
    SERVICE_STATE_RUNNING,
    SERVICE_STATE_STOPPING,
    SERVICE_STATE_ERROR
} ServiceState_t;

typedef struct
{
    TaskHandle_t task;
    TaskNotification_t notification;
    ServiceState_t state;
    bool initialized;
} ServiceContext_t;

static ServiceContext_t s_service;

static void ServiceTask(void *argument)
{
    ServiceContext_t *ctx = argument;

    if (service_init() != 0)
    {
        ctx->state = SERVICE_STATE_ERROR;
        vTaskDelete(NULL);
    }

    ctx->initialized = true;
    ctx->state = SERVICE_STATE_RUNNING;

    for (;;)
    {
        uint32_t notification;

        xTaskNotifyWait(
            0U,
            UINT32_MAX,
            &notification,
            pdMS_TO_TICKS(100U)
        );

        if ((notification & SERVICE_NOTIFY_STOP) != 0U)
        {
            ctx->state = SERVICE_STATE_STOPPING;

            service_stop_dma();
            service_flush_queue();
            service_deinit();

            ctx->initialized = false;
            ctx->state = SERVICE_STATE_INIT;
            ctx->task = NULL;

            vTaskDelete(NULL);
        }

        if ((notification & SERVICE_NOTIFY_DATA) != 0U)
        {
            service_process_data();
        }

        service_periodic_check();
    }
}
```

设计重点：

- 中断只做清标志和通知任务；
- 业务处理放在任务上下文；
- 停止流程是有序的；
- 任务删除前释放资源；
- 任务句柄由任务在退出前清空；
- 状态字段用于外部监控和故障诊断。

## 11. 工业级实际案例分析

### 案例一：电机控制系统

需求：

- 1 kHz 控制环；
- 控制任务周期误差不超过一个系统 tick；
- 不允许运行时分配内存；
- 过流中断优先于普通控制任务。

架构：

```
PWM/ADC中断
    |
    +--> 更新采样缓冲
    +--> 通知 MotorControlTask
                         |
                         +--> 电流环
                         +--> 速度环
                         +--> 故障状态机
```

核心代码：

```
static void MotorControlTask(void *argument)
{
    TickType_t last_wake = xTaskGetTickCount();

    for (;;)
    {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        motor_read_adc();
        motor_current_loop();
        motor_speed_loop();
        motor_update_pwm();

        /*
         * 控制任务通常由硬件事件唤醒，
         * 不使用长时间阻塞调用。
         */
        vTaskDelayUntil(&last_wake, 1U);
    }
}
```

设计要点：

- 电流保护放在硬件比较器或高优先级中断；
- 任务静态创建；
- 控制任务不能调用不可控延时或动态内存分配；
- 任务栈通过最坏控制路径验证。

### 案例二：OTA 升级任务

需求：

- 下载、校验、写 Flash；
- 支持取消；
- 网络断开后可重试；
- 停止时必须释放 socket、缓存和 Flash 状态。

核心状态机：

```
typedef enum
{
    OTA_IDLE,
    OTA_CONNECT,
    OTA_DOWNLOAD,
    OTA_VERIFY,
    OTA_COMMIT,
    OTA_FAILED
} OtaState_t;

static void OtaTask(void *argument)
{
    OtaState_t state = OTA_CONNECT;

    for (;;)
    {
        if (ota_stop_requested())
        {
            ota_socket_close();
            ota_buffer_release();
            ota_flash_abort();
            vTaskDelete(NULL);
        }

        switch (state)
        {
        case OTA_CONNECT:
            state = ota_connect() ? OTA_DOWNLOAD : OTA_FAILED;
            break;

        case OTA_DOWNLOAD:
            state = ota_download_step() ? OTA_VERIFY : OTA_FAILED;
            break;

        case OTA_VERIFY:
            state = ota_verify() ? OTA_COMMIT : OTA_FAILED;
            break;

        case OTA_COMMIT:
            ota_commit();
            vTaskDelete(NULL);
            break;

        default:
            ota_report_failure();
            vTaskDelete(NULL);
            break;
        }

        vTaskDelay(pdMS_TO_TICKS(10U));
    }
}
```

设计要点：

- OTA 任务通常可以动态创建，但不应无限频繁创建；
- 删除前要关闭网络、终止 Flash 操作并释放缓存；
- 升级过程需要看门狗喂狗策略；
- 不允许在校验过程中被无序删除。

### 案例三：工业网关连接处理

需求：

- 同时支持多个 TCP 连接；
- 连接数量动态变化；
- 每个连接处理协议帧；
- 连接关闭后释放会话资源。

推荐方案：

```
监听任务
   |
   +--> 接收连接
   +--> 从会话池获取 Session
   +--> 投递到工作队列
                    |
                    v
              WorkerTask
```

不推荐为每一个短生命周期事件创建一个任务。连接数量有限且行为相似时，使用：

- 固定大小 Session 池；
- 一个或多个常驻 Worker；
- 消息队列投递任务；
- 连接对象引用计数或明确所有权。

这样可以避免任务 TCB、任务栈和堆碎片随连接波动。

## 12. 高频问题深度答疑

### 问题一：为什么不建议频繁创建和删除任务？

任务创建涉及 TCB、栈初始化、调度链表插入和堆分配；删除还可能依赖 Idle Task 回收。频繁操作会带来：

- 不确定的执行时间；
- 堆碎片；
- 删除对象延迟回收；
- 任务句柄和资源所有权复杂化。

通常应将动态行为建模为**任务状态机**，而不是任务生命周期。

### 问题二：任务删除后内存是否立即释放？

不一定。FreeRTOS 动态删除任务后，删除任务会进入等待回收列表，通常由 Idle Task 调用 `prvCheckTasksWaitingTermination()` 回收。

因此：

- Idle Task 被高优先级任务长期占用时，回收会延迟；
- 短时间反复创建删除可能看到堆空间持续下降；
- 必须保证 Idle Task 能够运行。

### 问题三：任务栈应该如何确定？

不能只凭经验设置。应进行：

1. 编译器栈使用分析；
2. 关键路径静态审查；
3. 栈填充和高水位统计；
4. 中断嵌套和库函数调用测试；
5. 异常路径和日志路径测试；
6. 最坏输入压力测试。

推荐公式：

```
stack_size =
    max(normal_path,
        error_path,
        interrupt_effect,
        library_call)
    × safety_factor
```

安全系数通常取 `1.2～1.5`，安全关键系统应基于验证数据确定。

### 问题四：外部删除任务和任务自删除有什么差异？

任务自删除时，任务可以按业务顺序释放自己的资源，逻辑最清晰。外部删除无法保证任务当前执行到哪一步，可能中断：

- 持有互斥锁；
- 正在操作 DMA；
- 正在写 Flash；
- 正在访问共享缓冲区。

因此外部删除只适用于已知无资源持有、可立即终止的任务，长期服务应采用停止请求。

### 问题五：静态创建一定比动态创建更好吗？

不是绝对的。

静态创建优势：

- 内存来源明确；
- 无堆碎片；
- 创建时间更确定；
- 便于链接脚本和 MPU 管理。

动态创建优势：

- 资源利用灵活；
- 适合连接数或测试任务不固定的系统；
- 可以按运行时需求申请对象。

工业项目常见折中：

```
核心控制任务、通信栈、监控任务 -> 静态创建
非核心会话、测试模块、临时任务 -> 动态创建或任务池
```

### 问题六：任务优先级越高，响应一定越快吗？

不一定。高优先级任务如果：

- 长时间不阻塞；
- 频繁关闭中断；
- 持有互斥锁；
- 执行大量计算；
- 等待低优先级任务释放资源；

仍然可能造成系统实时性恶化。优先级设计应结合：

```
截止期
执行时间
唤醒频率
阻塞时间
资源依赖
故障影响范围
```

## 13. 课程核心总结

### 核心要点

- **任务由 TCB、任务栈和调度链表共同构成。**
- **上下文切换的核心是保存和恢复任务栈指针。**
- **任务栈参数通常以 `StackType_t` 数量为单位。**
- **长期运行任务应在启动阶段创建并持续运行。**
- **停止任务时应优先使用停止请求，而不是外部强制删除。**
- **RTOS 不负责释放应用层资源。**
- **任务入口函数不能自然返回。**
- **任务栈必须通过实际高水位和最坏路径验证。**

### 性能排序

在典型 Cortex-M + FreeRTOS 环境下：

```
静态创建确定性 > 任务池 > 动态创建
静态内存可预测性 > 动态内存灵活性
常驻任务状态机 > 频繁创建删除
```

### 通用选型结论

```
固定数量、长期运行、实时关键 -> 静态任务
数量动态、生命周期不固定     -> 动态任务
大量同质、频繁创建删除       -> 任务池
短时业务处理                 -> 常驻 Worker + 队列
```

## 14. 快速参考速查表

### 场景选型表

|场景|推荐方式|
|---|---|
|控制环|静态任务 + 任务通知|
|周期采集|静态任务 + `vTaskDelayUntil()`|
|一次性初始化|一次性任务，完成后自删除|
|OTA|常驻任务或启动阶段动态创建|
|网络连接池|Worker 任务 + Session 池|
|高安全等级|静态任务 + MPU + 栈监测|
|高频短作业|工作队列，不创建独立任务|

### API 对比表

|API|用途|注意事项|
|---|---|---|
|`xTaskCreate()`|动态创建|检查返回值和堆碎片|
|`xTaskCreateStatic()`|静态创建|TCB 和栈必须长期有效|
|`vTaskDelete(NULL)`|删除自身|退出前释放业务资源|
|`vTaskDelete(handle)`|删除其他任务|可能破坏资源一致性|
|`vTaskDelay()`|相对延时|可能产生周期漂移|
|`vTaskDelayUntil()`|绝对周期|适合固定周期任务|
|`uxTaskGetStackHighWaterMark()`|栈余量查询|单位通常是栈元素|
|`vTaskGetInfo()`|获取任务信息|需启用相关配置|
|`xTaskNotifyWait()`|任务通知等待|轻量、适合点对点唤醒|

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  任务和普通函数调用在执行模型上有什么区别？
- [ ]  TCB 和任务栈分别保存什么信息？
- [ ]  为什么任务切换必须保存栈指针？
- [ ]  `xTaskCreate()` 的栈深度单位是什么？
- [ ]  静态任务的 TCB 和栈能否使用局部变量？
- [ ]  任务删除后哪些资源不会自动释放？
- [ ]  为什么应该优先使用任务停止协议？
- [ ]  如何测量任务创建耗时？
- [ ]  如何通过高水位估算任务栈余量？
- [ ]  如何避免高优先级任务饿死低优先级任务？
- [ ]  什么场景应该使用任务池？
- [ ]  为什么 Idle Task 对动态任务回收很重要？

## 16. 实践与进阶路径

### 梯度实战任务

1. 使用静态方式创建一个 10 ms 周期传感器任务。
2. 增加任务句柄、启动接口、停止接口和状态查询接口。
3. 使用任务通知替代轮询方式唤醒任务。
4. 增加栈高水位统计和任务 CPU 占用统计。
5. 实现任务停止超时检测。
6. 构造任务创建失败场景，验证故障上报。
7. 实现固定大小任务池，测试频繁创建和删除。
8. 使用 MPU 或栈边界保护验证非法栈访问。

### 性能测试方法

- 使用 DWT `CYCCNT` 测量创建、删除和上下文切换周期。
- 使用 GPIO 翻转配合逻辑分析仪测量任务响应延迟。
- 使用 `uxTaskGetStackHighWaterMark()` 记录最小剩余栈。
- 反复创建和删除任务，监测 `xPortGetFreeHeapSize()` 和 `xPortGetMinimumEverFreeHeapSize()`。
- 让高优先级任务持续运行，验证低优先级任务是否获得调度。
- 注入网络断开、DMA 超时、Flash 写入失败等异常，验证任务退出清理路径。
- 通过压力测试确认任务栈、堆和 Idle Task 均有足够余量。

### 进阶学习方向

- FreeRTOS 调度器源码：就绪链表、延时链表和 `vTaskSwitchContext()`。
- Cortex-M PendSV、SysTick、MSP/PSP 和异常返回机制。
- FreeRTOS MPU 任务和特权级切换。
- 任务栈溢出检测方法一、方法二及硬件保护。
- 任务运行时间统计和 Tracealyzer 等可视化工具。
- 面向 AUTOSAR、IEC 61508、ISO 26262 的任务生命周期设计。
- 无堆系统、固定块内存池和确定性资源管理。
- 从任务模型演进到事件驱动、Actor 模型和混合调度架构。