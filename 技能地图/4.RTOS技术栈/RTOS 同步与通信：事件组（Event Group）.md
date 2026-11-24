## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解事件组是一个由多个状态位组成的同步对象。
- 区分事件组、二值信号量、计数信号量、消息队列和任务通知。
- 理解等待条件中的“任意位满足”与“所有位满足”。
- 理解自动清除位与不清除位的区别，以及多任务等待时的行为。
- 认识事件组表示的是**状态条件**，不是带顺序、计数和数据的事件队列。

### 掌握

能够：

- 创建静态和动态 FreeRTOS 事件组。
- 使用 `xEventGroupSetBits()`、`xEventGroupClearBits()` 和 `xEventGroupWaitBits()`。
- 在 ISR 中通过 `xEventGroupSetBitsFromISR()` 提交事件组更新。
- 为多个状态定义稳定、无重叠的位掩码。
- 设计启动同步、设备状态和多条件等待流程。
- 处理等待超时、事件位清除和 ISR 延迟处理。

### 精通

能够：

- 从 FreeRTOS 内核实现分析事件位操作与任务阻塞过程。
- 判断事件组是否会丢失“发生次数”或“发生顺序”。
- 分析自动清除与多个等待者之间的竞争。
- 根据任务数量和事件频率选择事件组、任务通知或消息队列。
- 量化事件组的位预算、唤醒延迟、CPU 开销和事件积压风险。

### 能够设计

能够设计：

- 多外设启动屏障；
- 多条件设备就绪门控；
- 可组合的系统状态位协议；
- ISR 到任务的事件通知结构；
- 事件组与消息队列、任务通知或互斥量协作的同步架构；
- 带超时、诊断统计和恢复路径的工业级事件协议。

---

## 2. 前置要求

### 知识要求

- C 语言位运算、整数类型和掩码定义。
- RTOS 任务状态、调度器和阻塞超时。
- 中断与任务上下文区别。
- FreeRTOS 队列、信号量和任务通知基础。
- 明白 `volatile` 不提供复合操作的原子性，也不能替代同步对象。

### 技能要求

- 能阅读 FreeRTOS `event_groups.c` 和 `event_groups.h`。
- 能检查工程中的 `configUSE_16_BIT_TICKS`、`configTICK_RATE_HZ` 和事件组配置。
- 能在 ISR 中使用对应的 FromISR API。
- 能用逻辑分析仪或 Trace 工具测量任务唤醒延迟。
- 能为事件位设计生命周期、清除责任和超时恢复策略。

---

## 3. 技术概述

### 3.1 事件组定义

事件组是一组可独立置位或清除的标志位：

```
bit 0：网络已连接
bit 1：时间同步完成
bit 2：传感器就绪
bit 3：配置加载完成
```

任务可以等待：

```
任意一个指定条件满足
```

或者：

```
所有指定条件都满足
```

抽象状态：

```
typedef uint32_t event_bits_t;
```

常见操作：

```
Set bits：某个条件变为真
Clear bits：某个条件变为假或事件被消费
Wait bits：等待一个或多个条件成立
```

FreeRTOS 的事件组通常使用 `EventBits_t` 类型。可用位数由该类型宽度和内核保留位决定，必须以当前版本头文件为准，不能假定所有平台都可使用完整 32 位。

### 3.2 事件状态与瞬时事件

事件组位可以有两种常见用法。

#### 持续状态

```
NETWORK_READY = 1：网络当前可用
NETWORK_READY = 0：网络当前不可用
```

只有状态变化时置位或清除。

#### 一次性事件

```
CALIBRATION_DONE = 1：校准已完成
```

等待者观察到后可清除该位。

工程上必须为每个位定义语义：

|语义|置位含义|清除含义|常见场景|
|---|---|---|---|
|状态位|条件成立|条件不再成立|连接状态、设备有效|
|完成位|操作完成|新操作开始或被消费|启动完成、校准完成|
|粘滞故障位|故障曾经发生|故障已确认并恢复|安全故障、诊断|
|门控位|允许进入下一阶段|暂停或撤销许可|系统启动屏障|

### 3.3 `Any` 与 `All` 等待

设等待掩码：

```
#define READY_MASK (NETWORK_READY | SENSOR_READY)
```

等待任意位：

```
NETWORK_READY 或 SENSOR_READY 至少一个置位
```

等待所有位：

```
NETWORK_READY 和 SENSOR_READY 都置位
```

注意：

```
waitForAll = pdFALSE -> 任意位满足
waitForAll = pdTRUE  -> 所有位满足
```

### 3.4 事件组不是消息队列

事件组只保存位状态，不保存：

- 每个位发生了多少次；
- 事件发生顺序；
- 事件参数；
- 时间戳；
- 每个消费者各自的消息副本。

重复置位同一位：

```
Set(DATA_READY)
Set(DATA_READY)
```

最终仍只是：

```
DATA_READY = 1
```

两次置位会合并成一个状态，不会得到“有两个数据块”。

---

## 4. 核心特性横向对比

### 4.1 RTOS 同步机制对比

|机制|表达内容|是否累计次数|是否带数据|多任务等待|ISR 使用|
|---|---|---|---|---|---|
|事件组|多个状态位|否|否|支持不同条件组合|支持特定 FromISR API|
|二值信号量|一个待消费信号|否|否|多任务竞争消费|支持|
|计数信号量|数量|是|否|多任务竞争消费|支持|
|消息队列|有序消息|是|是|多消费者竞争消费|支持|
|任务通知|单任务状态、位或计数|依模式|有限|通常绑定一个任务|支持|
|互斥量|资源所有权|否|否|一个持有者|通常不能在 ISR 使用|

### 4.2 事件组与消息队列

|维度|事件组|消息队列|
|---|---|---|
|状态表示|位集合|消息序列|
|保存历史|否|是，直到队列满|
|重复事件|合并|分别排队|
|条件组合|方便，支持任意位/全部位|需要接收后自行判断|
|数据载荷|无|有|
|顺序|不保证事件顺序|FIFO 或显式优先级|
|多任务等待|可让多个任务等待不同位条件|消息被一个消费者取走|
|适合启动门控|是|通常不如事件组直接|
|适合逐条处理|否|是|

### 4.3 状态位与事件位的设计选择

|问题|状态位|一次性事件位|
|---|---|---|
|条件撤销后是否清除|应清除|通常由消费者或新事务清除|
|是否允许多个任务观察|可以，但清除语义要谨慎|需要避免一个任务替其他任务消费|
|是否需要历史次数|否|若需要次数，应换计数机制|
|是否需要状态查询|很适合|只能表示“曾发生/待处理”|

---

## 5. 底层原理与功能特性深度解析

### 5.1 FreeRTOS 事件组对象

事件组通常由以下概念组成：

```
当前事件位值
等待任务列表
对象控制块
```

内核需要支持：

- `SetBits` 后检查哪些任务的等待条件满足；
- 解除满足条件任务的阻塞；
- 按等待任务要求清除指定位；
- 必要时触发调度；
- 处理超时任务。

事件组与队列、信号量一样，需要同步保护其内部状态。应用不应直接修改 EventGroup 对象内存。

### 5.2 位掩码

推荐集中定义事件位：

```
#define EVT_NETWORK_READY    (1UL << 0)
#define EVT_SENSOR_READY     (1UL << 1)
#define EVT_CONFIG_READY     (1UL << 2)
#define EVT_SYSTEM_FAULT     (1UL << 3)
```

组合：

```
#define EVT_STARTUP_READY \
    (EVT_NETWORK_READY | EVT_SENSOR_READY | EVT_CONFIG_READY)
```

定义时应遵守：

- 每个位只有一个稳定含义；
- 不重叠；
- 不复用内核保留位；
- 只传入合法用户位；
- 命名中区分状态、完成和故障语义。

位图类型转换应避免有符号左移和宽度不匹配。例如：

```
#define EVT_SENSOR_READY ((EventBits_t)1U << 2U)
```

具体类型和允许位数应以项目 FreeRTOS 头文件为准。

### 5.3 设置事件位

任务上下文：

```
EventBits_t result =
    xEventGroupSetBits(
        g_system_events,
        EVT_SENSOR_READY);
```

设置某个位表示状态变化或事件发生。若多个任务等待条件被满足，内核可能解除多个任务的阻塞。

**设置事件位不是“把消息交给某一个等待任务”。**

### 5.4 等待事件位

典型调用：

```
EventBits_t observed = xEventGroupWaitBits(
    g_system_events,
    EVT_STARTUP_READY,
    pdFALSE,                 /* 返回时不清除 */
    pdTRUE,                  /* 等待掩码中的所有位 */
    pdMS_TO_TICKS(5000));
```

参数语义：

|参数|含义|
|---|---|
|事件组句柄|要等待的对象|
|`uxBitsToWaitFor`|等待位掩码|
|`xClearOnExit`|条件满足退出时是否清除等待位|
|`xWaitForAllBits`|等全部位还是任意位|
|`xTicksToWait`|最大等待时间|

返回值是**退出等待时观察到的事件位快照**，可能因为：

- 等待条件满足；
- 超时；
- 被允许清除的位被清除；

而不同于任务最初等待时的状态。

正确判断方式：

```
EventBits_t observed = xEventGroupWaitBits(
    g_system_events,
    EVT_STARTUP_READY,
    pdFALSE,
    pdTRUE,
    pdMS_TO_TICKS(5000));

if ((observed & EVT_STARTUP_READY) == EVT_STARTUP_READY)
{
    system_start_services();
}
else
{
    system_handle_startup_timeout(observed);
}
```

### 5.5 等待任意位或全部位

任意位：

```
EventBits_t observed = xEventGroupWaitBits(
    g_system_events,
    EVT_NETWORK_READY | EVT_SYSTEM_FAULT,
    pdFALSE,
    pdFALSE,
    timeout);

if ((observed & EVT_SYSTEM_FAULT) != 0U)
{
    handle_fault();
}
else if ((observed & EVT_NETWORK_READY) != 0U)
{
    start_network_service();
}
```

全部位：

```
const EventBits_t required =
    EVT_NETWORK_READY |
    EVT_SENSOR_READY |
    EVT_CONFIG_READY;

EventBits_t observed = xEventGroupWaitBits(
    g_system_events,
    required,
    pdFALSE,
    pdTRUE,
    timeout);

if ((observed & required) == required)
{
    system_ready();
}
```

调用者必须使用掩码判断，不应简单判断：

```
if (observed != 0U)
```

因为返回值可能包含无关事件位。

### 5.6 自动清除位的语义

调用：

```
xEventGroupWaitBits(
    group,
    mask,
    pdTRUE,
    pdTRUE,
    timeout);
```

表示条件满足并退出等待时，清除等待掩码中的相关位。

自动清除适合：

```
一次性完成事件
单消费者消费的通知
```

不适合未经分析地用于：

```
多个任务都要观察的持续状态
```

如果任务 A 清除了 `NETWORK_READY`，任务 B 可能看不到该状态。

### 5.7 多个等待任务与事件位清除

假设任务 A 和 B 都等待同一个位，且都设置自动清除：

```
A 等待 EVT_DONE，clearOnExit = true
B 等待 EVT_DONE，clearOnExit = true
生产者设置 EVT_DONE
```

FreeRTOS 会在事件组处理过程中检查等待条件，并对满足条件的任务进行解除阻塞和清除处理。具体行为涉及内核的等待列表和清除顺序，**不能把事件组抽象成“每个等待者各有一份独立事件副本”** 。

工程规则：

- 若多个任务都要观察持续状态，使用 `clearOnExit = pdFALSE`；
- 若事件必须被唯一消费者消费，最好用队列或任务专属通知表达；
- 若要广播一次性事件，采用明确的广播协议，例如每个消费者有独立位或独立通知；
- 多任务共享自动清除位之前，应查阅项目对应 FreeRTOS 版本的源码和测试。

### 5.8 超时语义

事件组等待使用 Tick 超时：

```
pdMS_TO_TICKS(100)
```

超时精度受 Tick 频率和调度影响。`configTICK_RATE_HZ = 1000` 时，Tick 量化单位为 1 ms，但任务重新获得 CPU 的实际时间可能晚于名义超时。

超时不表示：

- 事件一定未发生；
- 相关硬件已停止；
- 等待过程没有状态变化；
- 事件位自动清零。

超时路径应查询返回位、当前设备状态或硬件状态，再决定恢复策略。

### 5.9 ISR 设置事件位：FreeRTOS 的延迟处理

FreeRTOS 中 `xEventGroupSetBitsFromISR()` 通常通过 **deferred function call** 机制将事件位设置请求提交给 RTOS daemon/timer service task，而不是在 ISR 中执行全部等待列表处理。

示例：

```
void DMA_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    dma_clear_flags();

    BaseType_t result =
        xEventGroupSetBitsFromISR(
            g_events,
            EVT_DMA_COMPLETE,
            &higher_priority_task_woken);

    if (result != pdPASS)
    {
        g_isr_event_set_failed++;
    }

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

因此需要：

- 启用并正确配置 FreeRTOS Timer Service Task；
- 配置足够的 timer command queue 长度；
- 配置合理的 timer task 优先级；
- 处理 FromISR 请求失败；
- 认识到 ISR 到等待任务之间多了一段 daemon task 调度延迟。

如果必须在 ISR 返回前直接完成高确定性的同步动作，可评估：

- 任务通知 FromISR；
- 二值信号量 FromISR；
- 原子标志加任务通知；
- 硬件中断后由高优先级任务处理。

### 5.10 清除事件位

任务上下文：

```
EventBits_t previous =
    xEventGroupClearBits(
        g_events,
        EVT_SENSOR_READY);
```

清位通常用于状态撤销或开始新一轮事务。

清位前要确定：

```
这个位是谁负责清除？
是否有其他任务也依赖它？
是否存在新一轮事件与旧一轮清除竞争？
```

典型竞态：

```
任务准备开始新事务并清位
ISR 恰好设置新事务完成位
```

若操作顺序和事务编号不受控，可能清掉刚到的新事件。需要通过：

- 在启动硬件前清位；
- 事务序号；
- 单一所有者；
- 临界区或设备状态机；

来消除歧义。

### 5.11 事件组不保存计数和顺序

连续两次设置同一位：

```
xEventGroupSetBits(g_events, EVT_RX_READY);
xEventGroupSetBits(g_events, EVT_RX_READY);
```

事件组最终仍只表示：

```
EVT_RX_READY == 1
```

它不表示发生了两次。

如果每次都要处理：

```
使用计数信号量、消息队列或环形缓冲区
```

如果只表示“有数据需要检查”，可以使用事件位，但消费者需要从数据源中读取实际积压内容。

---

## 6. 性能量化分析

### 6.1 测量平台与数据边界

建议固定并记录：

```
MCU 型号
CPU 主频
FreeRTOS 版本与提交号
编译器版本与优化等级
configTICK_RATE_HZ
事件组配置
timer task 优先级
timer command queue 长度
Trace 和断言配置
```

本课没有在具体目标板上运行基准测试，因此不提供未经验证的“API 实测周期”。以下给出内存公式、延迟模型和可复现测量方法。

### 6.2 位容量与对象 RAM

事件组 RAM 主要由以下部分构成：

```
事件位类型
对象控制块
等待任务列表节点
堆管理开销（动态分配时）
```

增加事件位通常不会按位增加独立对象存储，因为位通常打包在一个整数中；但位数受内核类型宽度限制。

应从目标工程检查：

```
sizeof(EventGroupHandle_t)
sizeof(StaticEventGroup_t)
sizeof(EventBits_t)
```

以实际头文件和 ABI 为准。

### 6.3 等待位预算

若某版本的事件组可用位数为 `B`，则：

```
可独立编码状态数量 <= B
```

但应预留结构空间：

```
Btotal = Bstatus + Bevent + Bfault + Breserved
```

不要将同一位在多个模块中复用且没有生命周期约定。

事件位不足时，优先拆分事件组或采用其他对象；不要将事件组扩展成跨模块的无约束全局位域。

### 6.4 延迟模型

任务上下文置位后，等待任务的响应时间近似为：

```
Tresponse =
    Tset
  + Tscheduler
  + Tready_queue
  + Tinterrupt_block
```

ISR 调用 FromISR API 时，常见 FreeRTOS 路径通过 timer service task 延迟处理，响应时间还包括：

```
Ttimer_queue
+ Ttimer_task_schedule
+ Tprocess_event
```

因此 ISR 到任务的延迟受 timer task 负载和命令队列影响。它不能简单等同于 `xSemaphoreGiveFromISR()` 的直接唤醒延迟。

### 6.5 高负载和等待任务数量

设置事件位时，内核需要检查等待条件并处理满足条件的任务。实际开销与以下因素相关：

- 当前等待该事件组的任务数量；
- 等待掩码复杂度；
- 满足条件的任务数量；
- 是否需要调度；
- Trace 和断言配置。

高频 ISR 不应无节制地用事件组反复置位，尤其是 ISR API 还要经由 daemon task 的场景。

### 6.6 选择事件组的性能依据

事件组的优势不是“永远最快”，而是：

- 多条件组合简洁；
- 一个状态变化可解除多个任务的等待；
- 多个条件可由一个位图表达；
- 避免为每个布尔状态创建单独同步对象。

如果只是单任务接收一个高频通知，任务通知通常更轻量。如果要逐条传消息，队列的语义更正确，即使复制成本更高。

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
同步对象需要表达什么？
|
+-- 多个布尔状态组合
|   |
|   +-- 等待任意/全部条件 -> 事件组
|
+-- 一次事件发生，单任务处理
|   |
|   +-- 任务通知或二值信号量
|
+-- 事件发生次数必须保留
|   |
|   +-- 计数信号量或队列
|
+-- 事件携带数据或必须保序
|   |
|   +-- 消息队列 / MessageBuffer
|
+-- 保护共享资源
    |
    +-- 互斥量
```

### 7.2 典型场景

|场景|推荐机制|理由|
|---|---|---|
|多外设全部初始化后启动服务|事件组，等待全部位|条件组合明确|
|网络连接或断开状态|事件组状态位|表示持续状态|
|多个任务等待系统就绪|事件组，不自动清状态位|多任务观察同一条件|
|UART 每帧接收|队列/缓冲区|每帧有数据和边界|
|DMA 完成次数必须保留|计数信号量或队列|事件组会合并重复位|
|设备寄存器互斥访问|互斥量|事件组不提供所有权|
|单任务高频唤醒|任务通知|通常开销更低|
|故障历史必须审计|故障队列/日志 + 状态位|状态位不保存历史|

---

## 8. 工程最佳实践

### 8.1 每个位必须有唯一契约

位定义应说明：

```
位名
置位者
清除者
状态还是一次性事件
是否允许被多个任务观察
超时后的处理方式
```

例如：

|位|置位者|清除者|语义|
|---|---|---|---|
|`EVT_NETWORK_READY`|网络管理任务|网络管理任务|持续状态|
|`EVT_SENSOR_READY`|传感器任务|传感器任务|持续状态|
|`EVT_CALIBRATION_DONE`|校准任务|启动下一轮校准时|完成状态|
|`EVT_SYSTEM_FAULT`|故障管理器|故障确认流程|粘滞故障|

### 8.2 状态位和事件通知分离

网络连接状态：

```
NETWORK_READY 位表示当前是否连接
```

每次连接变化的历史：

```
网络事件队列保存 CONNECTED/DISCONNECTED 记录
```

两者可以同时存在：

```
事件组：当前状态查询和门控
队列：历史事件和逐条处理
```

### 8.3 默认不自动清除共享状态位

若多个任务都可能等待 `SYSTEM_READY`：

```
xEventGroupWaitBits(
    events,
    EVT_SYSTEM_READY,
    pdFALSE,
    pdTRUE,
    timeout);
```

自动清除会让等待任务之间互相影响。只有明确是单消费者的一次性事件时，才考虑清除。

### 8.4 ISR 事件组操作必须纳入 daemon task 预算

使用 FromISR API 时，应检查：

- Timer Service Task 是否创建；
- `configTIMER_QUEUE_LENGTH` 是否足够；
- `configTIMER_TASK_PRIORITY` 是否满足延迟目标；
- 命令队列满时的错误路径；
- ISR 优先级是否符合 FreeRTOS 限制。

### 8.5 超时与恢复不能只看返回值

等待超时后应检查：

- 哪些位已经满足；
- 设备实际硬件状态；
- 相关任务是否运行；
- 是否应重试、降级或复位模块；
- 是否有部分初始化成功的资源需要释放。

### 8.6 工业级编码规范

- 位掩码集中定义，不在业务代码中随意写 `1U << n`。
- 使用 `EventBits_t` 兼容的类型和合法位范围。
- 对所有等待设置合理超时，只有有证明的永久等待才用 `portMAX_DELAY`。
- 对 `xEventGroupSetBitsFromISR()` 检查返回值。
- 不用事件组保存事件次数和数据。
- 清位操作必须有单一责任方或明确协议。
- 删除事件组前停止所有设置者和等待者。
- 关键状态增加序号、时间戳或硬件状态校验。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：把事件组位当事件计数器

错误代码：

```
/* 每个 DMA 块完成都设置同一位。 */
xEventGroupSetBits(g_events, EVT_DMA_DONE);
```

任务随后只等待一次：

```
xEventGroupWaitBits(
    g_events,
    EVT_DMA_DONE,
    pdTRUE,
    pdFALSE,
    portMAX_DELAY);
```

**根因：** 重复置位同一个 bit 会合并，不会累计完成块数量。

正确方案：

```
若所有完成块都要处理：
    DMA 描述符队列 + 通知/信号量

若只需知道“至少有数据待处理”：
    事件组可以作为门控，但数据数量从环形缓冲区读取
```

**风险影响：** 漏处理 DMA 块、缓冲区覆盖、数据序列断裂。

### 9.2 错误二：等待所有位时使用了任意位模式

错误代码：

```
xEventGroupWaitBits(
    g_events,
    EVT_NET | EVT_SENSOR | EVT_CONFIG,
    pdFALSE,
    pdFALSE, /* 错：任意一位满足即可返回 */
    timeout);
```

正确实现：

```
EventBits_t required =
    EVT_NET | EVT_SENSOR | EVT_CONFIG;

EventBits_t observed = xEventGroupWaitBits(
    g_events,
    required,
    pdFALSE,
    pdTRUE,
    timeout);

if ((observed & required) != required)
{
    handle_startup_timeout(observed);
}
```

**根因：** `pdFALSE` 表示等待任意指定位，不是“全部等待”。

**风险影响：** 服务在依赖外设尚未就绪时启动。

### 9.3 错误三：共享状态位使用自动清除

错误代码：

```
xEventGroupWaitBits(
    g_events,
    EVT_NETWORK_READY,
    pdTRUE,  /* 清除 */
    pdTRUE,
    portMAX_DELAY);
```

**根因：** 第一个观察到条件的任务可能清掉状态位，其他任务看不到共享状态。

正确方案：

```
xEventGroupWaitBits(
    g_events,
    EVT_NETWORK_READY,
    pdFALSE,
    pdTRUE,
    timeout);
```

由网络状态拥有者在断开时清位。

**风险影响：** 不同任务观察到互相矛盾的网络状态，启动或恢复流程卡住。

### 9.4 错误四：忽略 ISR 设置失败

错误代码：

```
void DMA_IRQHandler(void)
{
    xEventGroupSetBitsFromISR(
        g_events,
        EVT_DMA_DONE,
        NULL);
}
```

**根因：**

- 未检查返回值；
- `pxHigherPriorityTaskWoken` 可能不可省略或不符合当前版本 API；
- deferred command queue 可能满；
- 未按要求请求 ISR 退出时切换。

正确模式：

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    BaseType_t result;

    dma_clear_flags();

    result = xEventGroupSetBitsFromISR(
        g_events,
        EVT_DMA_DONE,
        &woken);

    if (result != pdPASS)
    {
        g_event_command_failures++;
    }

    portYIELD_FROM_ISR(woken);
}
```

还必须验证 daemon task 配置和中断优先级。

**风险影响：** 偶发丢通知、处理延迟不稳定、队列满时静默失效。

### 9.5 错误五：把事件组当成广播队列

错误假设：

```
多个任务等待 EVT_DATA_READY，所以每个任务都会各自收到一份数据。
```

**根因：** 事件组只提供位状态，没有数据副本和每任务消息队列。自动清除和各任务等待条件还会改变可观察行为。

正确方案：

- 若所有任务只需知道状态，使用不清除的共享状态位；
- 若每个任务都要处理同一份数据，使用广播架构或每任务独立消息；
- 若消息由单个任务消费，使用队列。

**风险影响：** 漏消费者、重复消费或状态不同步。

### 9.6 错误六：先清位再开始操作，竞态覆盖新事件

错误模式：

```
xEventGroupClearBits(g_events, EVT_DONE);

/* 期间旧事务或新事务可能完成并置位 */
start_new_operation();
```

**根因：** 清位和事务启动没有明确顺序，旧事件与新事件无法区分。

正确方案：

```
1. 确认前一事务已停止或完成
2. 清除旧完成状态
3. 建立新事务编号
4. 启动硬件
5. 等待与该事务对应的完成通知
```

对可能迟到的中断，应使用事务序号或硬件状态确认。

**风险影响：** 新完成被清除，或旧完成被误认作新事务完成。

---

## 10. 多机制组合使用方案

### 10.1 事件组 + 消息队列

用途分工：

```
事件组：
    设备是否就绪、是否发生故障、是否允许启动

消息队列：
    每次数据、命令、状态变化记录
```

例如：

```
EVT_SENSOR_READY：
    传感器当前可用

sensor_queue：
    每条传感器采样和时间戳
```

不要重复使用一个事件位去替代队列中的每条采样。

### 10.2 事件组 + 互斥量

用途分工：

```
事件组：
    等待“配置已完成”或“设备已连接”

互斥量：
    保护设备配置结构和寄存器访问
```

事件组不能保护共享资源；互斥量也不适合表达多个布尔条件。

### 10.3 ISR 更新标志后唤醒任务

若事件组 FromISR 的 deferred 路径不满足延迟目标，可使用：

```
ISR：
    原子记录硬件事件或使用 FromISR 通知

高优先级任务：
    读取硬件状态，更新事件组状态
```

示例结构：

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    dma_clear_flags();

    vTaskNotifyGiveFromISR(
        g_dma_task,
        &woken);

    portYIELD_FROM_ISR(woken);
}

static void DmaServiceTask(void *argument)
{
    for (;;)
    {
        ulTaskNotifyTake(
            pdTRUE,
            portMAX_DELAY);

        if (dma_completion_pending())
        {
            xEventGroupSetBits(
                g_system_events,
                EVT_DMA_SERVICE_READY);
        }
    }
}
```

这个模式将：

```
快速 ISR 唤醒
```

与：

```
系统状态位维护
```

分开。若同一事件可能多次发生且每次都需要处理，任务通知计数或队列要保留次数/数据。

### 10.4 启动屏障：完整代码框架

```
#include "FreeRTOS.h"
#include "event_groups.h"
#include "task.h"

#define EVT_NETWORK_READY   ((EventBits_t)1U << 0U)
#define EVT_SENSOR_READY    ((EventBits_t)1U << 1U)
#define EVT_CONFIG_READY    ((EventBits_t)1U << 2U)
#define EVT_STARTUP_FAULT   ((EventBits_t)1U << 3U)

#define EVT_STARTUP_REQUIRED \
    (EVT_NETWORK_READY | EVT_SENSOR_READY | EVT_CONFIG_READY)

static StaticEventGroup_t s_event_storage;
static EventGroupHandle_t s_system_events;

bool system_events_init(void)
{
    s_system_events = xEventGroupCreateStatic(
        &s_event_storage);

    return s_system_events != NULL;
}

void network_set_ready(bool ready)
{
    if (ready)
    {
        xEventGroupSetBits(
            s_system_events,
            EVT_NETWORK_READY);
    }
    else
    {
        xEventGroupClearBits(
            s_system_events,
            EVT_NETWORK_READY);
    }
}

static void StartupTask(void *argument)
{
    const TickType_t timeout =
        pdMS_TO_TICKS(10000U);

    (void)argument;

    EventBits_t observed = xEventGroupWaitBits(
        s_system_events,
        EVT_STARTUP_REQUIRED | EVT_STARTUP_FAULT,
        pdFALSE,
        pdFALSE, /* 任一故障或全部就绪后，仍需在代码中判定 */
        timeout);

    if ((observed & EVT_STARTUP_FAULT) != 0U)
    {
        startup_enter_safe_mode(observed);
        vTaskDelete(NULL);
    }

    if ((observed & EVT_STARTUP_REQUIRED) !=
        EVT_STARTUP_REQUIRED)
    {
        startup_timeout_recovery(observed);
        vTaskDelete(NULL);
    }

    start_application_services();
    vTaskDelete(NULL);
}
```

这个示例等待条件需特别注意：使用“任意位”时，任一就绪位也会使等待返回。因此如果目标是“全部就绪或任一故障”，应采用分阶段等待或更适合的协议，不能把上面的掩码逻辑误解为自动表达逻辑：

```
(全部 READY) OR (任一 FAULT)
```

可用循环明确表达该条件：

```
static bool wait_startup_condition(TickType_t total_timeout)
{
    TickType_t start = xTaskGetTickCount();

    for (;;)
    {
        EventBits_t bits = xEventGroupGetBits(s_system_events);

        if ((bits & EVT_STARTUP_FAULT) != 0U)
        {
            return false;
        }

        if ((bits & EVT_STARTUP_REQUIRED) ==
            EVT_STARTUP_REQUIRED)
        {
            return true;
        }

        TickType_t elapsed = xTaskGetTickCount() - start;

        if (elapsed >= total_timeout)
        {
            return false;
        }

        TickType_t remaining = total_timeout - elapsed;

        /*
         * 等待任一相关位变化以减少轮询。
         * 返回后循环重新评估复合条件。
         */
        (void)xEventGroupWaitBits(
            s_system_events,
            EVT_STARTUP_REQUIRED | EVT_STARTUP_FAULT,
            pdFALSE,
            pdFALSE,
            remaining);
    }
}
```

这说明事件组支持“任意位”或“所有指定位”，但不能在一个 `WaitBits` 调用中直接表达任意布尔公式。

---

## 11. 工业级实际案例分析

### 11.1 案例一：多外设启动同步

**需求：**

- 网络、传感器和配置存储由不同任务初始化；
- 主应用必须等三者全部就绪；
- 任一初始化失败则进入安全模式；
- 启动等待最多 10 秒。

**架构：**

```
Network Task  -> NETWORK_READY
Sensor Task   -> SENSOR_READY
Config Task   -> CONFIG_READY

Failure Path  -> STARTUP_FAULT

Startup Task：
    检查故障位
    检查全部就绪位
    检查截止时间
```

**设计要点：**

- 初始化成功位由对应模块拥有；
- 初始化失败后设置错误状态并置位故障；
- 就绪状态通常不自动清除；
- 每个模块应支持启动超时或失败回报；
- 系统进入安全模式后，不能只清故障位假装恢复。

### 11.2 案例二：网络状态门控与连接历史

**需求：**

- 多任务需要判断网络是否可用；
- 连接变化需要逐条记录；
- 网络断开后上传任务必须停止发送；
- 重新连接后上传任务恢复。

**架构：**

```
事件组 NETWORK_READY：
    当前连接状态

网络事件队列：
    CONNECTED/DISCONNECTED/ERROR + 时间戳
```

**设计要点：**

- 事件组服务于快速门控；
- 事件队列保留连接历史；
- 连接任务是状态位的唯一拥有者；
- 断开时清 `NETWORK_READY`，并发送一条断开事件；
- 上传任务等待就绪位，但实际发送仍需处理链路错误。

### 11.3 案例三：故障状态与恢复策略

**需求：**

- 多个任务检测不同故障；
- 控制任务要快速进入安全状态；
- 故障码、时间戳和恢复次数必须保留；
- 某些故障清除前需要人工确认。

**架构：**

```
事件组：
    FAULT_PRESENT
    SENSOR_INVALID
    OVER_TEMPERATURE

故障队列：
    fault_code
    timestamp
    source
    measured_value

控制任务：
    等待任一严重故障位
    进入安全控制状态
```

**设计要点：**

- 位用于快速门控；
- 队列用于完整故障记录；
- 需要粘滞的故障位由故障管理器清除；
- 不能让普通消费者自动清除安全故障位；
- 故障事件队列满时应有专门的故障计数和持久化策略。

---

## 12. 高频问题深度答疑

### 问题一：事件组的多个位能否同时等待？

可以。通过掩码指定多个位，并选择等待任意位或全部位。

但不能直接表达复杂布尔公式，例如：

```
(A AND B) OR C
```

可以等待相关位变化后，在任务中重新检查完整表达式，或将状态结构化为更直接的状态机。

### 问题二：两个任务等待同一个事件位，能否都被唤醒？

事件组允许多个任务等待条件。具体哪些任务解除阻塞取决于各自等待掩码、等待全部/任意条件和清除选项。

但要记住：

> **被唤醒不等于每个任务拥有一份独立消息副本。**

共享状态通常不自动清除；唯一消费事件通常应使用队列或任务专属通知。

### 问题三：事件组位被清除后，等待任务返回值是什么？

FreeRTOS 等待函数返回事件位快照，具体清除和解除阻塞流程应以所用内核版本源码为准。应用不应仅凭“返回值非零”判定目标条件满足，而应使用目标掩码检查：

```
(bits & required_mask) == required_mask
```

### 问题四：为什么不能在 ISR 中直接调用普通 `xEventGroupSetBits()`？

普通 API 运行在任务上下文语义中，可能涉及任务列表处理和调度行为。ISR 应使用 `xEventGroupSetBitsFromISR()`。

此外 FreeRTOS 常将事件组 FromISR 操作延迟到 timer service task 处理，因此要考虑 daemon task 和命令队列资源。

### 问题五：事件组适合每 100 μs 设置一次吗？

通常需要先测量和评估。高频反复设置同一位会合并事件，却仍带来同步开销；FromISR 路径还可能向 daemon queue 提交命令。

若事件频率高：

- 需要累计次数：计数信号量或任务通知计数；
- 需要保存数据：队列或环形缓冲区；
- 只是提示缓冲区已有数据：使用低频合并通知，并批量处理积压。

### 问题六：事件组能否代替锁保护共享数据？

不能。事件位只表示状态，不提供共享数据所有权。

若任务要读取共享结构：

- 用互斥量保护；
- 使用不可变快照；
- 或设计无锁快照协议。

事件组可以用于通知“数据已更新”，但不能保证通知与多字段数据更新形成一个应用级事务，除非整体协议明确处理。

---

## 13. 课程核心总结

### 核心要点

1. **事件组是一组状态位，不是消息队列。**
2. `waitForAllBits` 选择等待全部位还是任意位。
3. 自动清除可能影响其他等待者，必须先明确消费者模型。
4. 重复设置同一位会合并，不会计数。
5. 事件组不保存载荷、顺序、时间戳或历史。
6. FreeRTOS ISR 设置事件组可能经由 timer service task 延迟处理。
7. 多消费者共享持续状态时通常不自动清除。
8. 需要逐条处理的数据应用消息队列或缓冲区。
9. 需要保护共享资源使用互斥量。
10. 每个位都要定义置位者、清除者和语义生命周期。

### 性能与表达能力排序

针对**多条件布尔状态组合**：

```
事件组
    >
多个独立二值对象
```

针对**单任务快速通知**：

```
任务通知通常更轻量
```

针对**逐条消息和数据载荷**：

```
消息队列 / MessageBuffer
```

没有单一机制能同时提供：

```
任意条件组合、事件计数、消息顺序、载荷传输和资源所有权
```

### 通用选型结论

```
等待多个状态条件：
    事件组

单任务接收一次通知：
    任务通知或二值信号量

事件次数不能丢：
    计数信号量或队列

每次事件带数据：
    消息队列或缓冲区

共享资源保护：
    互斥量

多个任务都要看到状态：
    不清除的状态位，或独立订阅机制
```

---

## 14. 快速参考速查表

### 14.1 FreeRTOS API 速查

|需求|API|
|---|---|
|动态创建|`xEventGroupCreate()`|
|静态创建|`xEventGroupCreateStatic()`|
|设置位|`xEventGroupSetBits()`|
|清除位|`xEventGroupClearBits()`|
|等待位|`xEventGroupWaitBits()`|
|查询位|`xEventGroupGetBits()`|
|ISR 设置位|`xEventGroupSetBitsFromISR()`|
|删除对象|`vEventGroupDelete()`|

### 14.2 等待参数速查

|参数|取值|语义|
|---|---|---|
|`xClearOnExit`|`pdTRUE`|满足等待条件退出时清除等待位|
|`xClearOnExit`|`pdFALSE`|不自动清除|
|`xWaitForAllBits`|`pdTRUE`|等待掩码中的所有位|
|`xWaitForAllBits`|`pdFALSE`|等待掩码中任意位|
|timeout|`0`|不阻塞|
|timeout|有限 Tick|最多等待指定时间|

### 14.3 场景速查表

|需求|机制|
|---|---|
|多外设全部就绪|事件组，等待全部位|
|网络当前可用|事件组状态位|
|每次网络变化都要记录|事件队列|
|多次 DMA 完成逐个处理|队列/计数同步|
|UART 帧和数据|消息队列/缓冲区|
|共享 SPI 访问|互斥量|
|单任务高频通知|任务通知|
|多任务共享状态观察|非自动清除状态位或订阅架构|

---

## 15. 学习效果自检

### 理解能力

- [ ]  能解释事件组位表示状态而非次数。
- [ ]  能说明 `pdTRUE` / `pdFALSE` 对 `waitForAllBits` 的含义。
- [ ]  能说明自动清除位的多任务影响。
- [ ]  能区分状态位和一次性完成事件。
- [ ]  能解释事件组为什么不能替代消息队列。

### API 能力

- [ ]  能创建静态事件组。
- [ ]  能正确判断 `xEventGroupWaitBits()` 返回掩码。
- [ ]  能正确处理有限超时。
- [ ]  能在 ISR 中使用对应 FromISR API。
- [ ]  能检查 ISR 延迟处理和 timer service task 配置。
- [ ]  能在模块失效时清除持续状态位。

### 架构能力

- [ ]  能设计多模块启动屏障。
- [ ]  能将当前状态位与历史事件队列分离。
- [ ]  能为每个位定义置位者和清除者。
- [ ]  能判断共享状态位是否允许自动清除。
- [ ]  能设计“全部就绪或发生故障”的等待与判定逻辑。
- [ ]  能处理事件组与共享数据之间的一致性问题。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

1. **多外设启动屏障**
    
    - 网络、传感器、配置任务分别置位；
    - 主任务等待全部就绪；
    - 一个模块超时后设置故障位；
    - 进入安全模式并记录未就绪模块。
2. **网络状态与事件历史分离**
    
    - 事件组表示当前连接状态；
    - 消息队列记录每次连接变化；
    - 验证多个任务读取状态不会互相清位。
3. **自动清除竞争实验**
    
    - 两个任务等待相同位；
    - 分别测试自动清除和不清除；
    - 用 Trace 观察任务唤醒和后续状态；
    - 对照当前 FreeRTOS 版本的 `event_groups.c`。
4. **ISR 设置事件位**
    
    - 从 DMA ISR 设置事件；
    - 测量 ISR 到等待任务执行的延迟；
    - 增加 timer service task 负载；
    - 注入 timer command queue 满；
    - 记录请求失败和延迟变化。
5. **事件位与事件队列组合**
    
    - 事件组只表示“有数据待处理”；
    - 队列保存每条数据；
    - 消费任务批量排空队列；
    - 验证重复置位不会导致数据数量错误。

### 16.2 性能测试方法

使用 GPIO 测量任务上下文置位到等待任务开始运行：

```
/* 生产者任务 */
gpio_set(EVENT_SET_PIN);
xEventGroupSetBits(g_events, EVT_TEST);
gpio_clear(EVENT_SET_PIN);

/* 等待任务 */
(void)xEventGroupWaitBits(
    g_events,
    EVT_TEST,
    pdTRUE,
    pdTRUE,
    portMAX_DELAY);

gpio_set(EVENT_WAKE_PIN);
```

测量：

```
EVENT_SET 上升沿
    ->
EVENT_WAKE 上升沿
```

分别测试：

- 一个等待任务；
- 多个等待任务；
- 满足任意位；
- 满足全部位；
- 自动清除和不清除；
- 任务上下文设置；
- ISR FromISR 设置；
- daemon task 不同负载；
- 不同优先级和中断负载。

记录：

```
最小、平均、P99、P99.9、最大观察值
等待任务数
timer task 队列使用情况
ISR 请求失败数
任务唤醒延迟
事件位被清除的次数
```

DWT 用于测量 CPU 周期；GPIO 或 Trace 用于测量包含调度和中断的端到端响应时间。最大观察值不是严格 WCET，需要结合优先级、最长临界区、ISR 干扰和 timer task 行为建立上界。

### 16.3 进阶学习方向

- 阅读 `event_groups.c` 中的：
    - `xEventGroupSetBits()`；
    - `xEventGroupSetBitsFromISR()`；
    - `xEventGroupWaitBits()`；
    - 等待列表处理和事件位清除逻辑。
- 研究 timer service task 的命令队列与优先级。
- 建立事件位状态机和清除责任表。
- 研究多任务广播与发布/订阅模式。
- 评估任务通知、事件组和消息队列的延迟与 RAM 成本。
- 学习事件驱动架构中的：
    - 状态快照；
    - 事件历史；
    - 故障粘滞位；
    - 事件序号；
    - 超时恢复；
    - 故障安全状态。