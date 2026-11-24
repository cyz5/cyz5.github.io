
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解互斥量的**资源所有权语义**。
- 理解优先级反转的形成条件、调度过程和实时性危害。
- 理解优先级继承协议的工作机制。
- 区分互斥量、二值信号量和计数信号量。
- 理解互斥量的关键约束：
    - 必须由持有者释放；
    - 通常不能在 ISR 中使用；
    - 只能用于任务间资源保护；
    - 可能引入阻塞和优先级变化。

### 1.2 掌握

能够：

- 使用 FreeRTOS 静态、动态创建互斥量。
- 正确使用 `xSemaphoreTake()` 和 `xSemaphoreGive()`。
- 分析互斥量获取超时和资源释放路径。
- 处理临界区、嵌套加锁和锁顺序。
- 使用优先级继承降低优先级反转影响。
- 测量锁竞争延迟、最长持锁时间和优先级继承响应时间。

### 1.3 精通

能够：

- 从 FreeRTOS 内核源码分析互斥量与队列的差异。
- 解释 `uxMutexesHeld`、`uxBasePriority`、`uxPriority` 等字段的作用。
- 分析嵌套锁、多个互斥量和优先级恢复问题。
- 识别死锁、活锁、锁饥饿、优先级反转和中断阻塞。
- 根据实时性要求设计锁顺序、锁粒度和资源访问架构。

### 1.4 能够设计

能够设计：

- 支持优先级继承的设备总线访问层。
- 多任务共享 SPI、I2C、UART 等外设的互斥保护方案。
- 带锁顺序约束、超时、故障诊断和恢复机制的锁封装层。
- 适用于高实时任务的锁粒度和资源代理架构。
- 在互斥量、临界区、调度器锁和无锁数据结构之间进行工程选型。

---

## 2. 前置要求

### 2.1 知识要求

- C 语言：
    - 函数、指针、结构体；
    - `volatile`；
    - 资源生命周期；
    - 错误处理和统一清理路径。
- MCU 基础：
    - 中断优先级；
    - 临界区；
    - SysTick/PendSV；
    - 外设总线时序。
- RTOS 基础：
    - 任务优先级；
    - 阻塞态和就绪态；
    - 抢占式调度；
    - Tick 超时；
    - 任务控制块。
- FreeRTOS 基础：
    - 队列和信号量；
    - `FromISR` API；
    - 静态对象；
    - `configASSERT()`；
    - `configUSE_MUTEXES`。

### 2.2 技能要求

- 能够阅读 `queue.c` 和 `tasks.c` 中的同步代码。
- 能够使用逻辑分析仪观察任务切换和外设访问。
- 能够分析 map 文件、任务栈余量和运行时统计。
- 能够定位死锁、任务阻塞和优先级反转。
- 能够实现基本的锁顺序检查和资源访问封装。

---

## 3. 技术概述

## 3.1 互斥量的定义

互斥量（Mutex，Mutual Exclusion）用于保护一个具有排他访问要求的共享资源。

典型资源：

- SPI 控制器；
- I2C 控制器；
- 共享 UART；
- 显示控制器；
- Flash 擦写接口；
- 文件系统；
- 共享内存结构；
- DMA 通道配置；
- 非线程安全驱动。

互斥量的基本状态：

```
未持有：资源可被某个任务获取
已持有：资源被某个任务独占
```

典型使用方式：

```
if (xSemaphoreTake(mutex, timeout) == pdPASS)
{
    shared_resource_access();

    xSemaphoreGive(mutex);
}
```

互斥量与普通二值信号量最大的区别是：

> **互斥量具有所有权语义，并且通常支持优先级继承。**

---

## 3.2 互斥量的所有权

假设任务 A 成功获取互斥量：

```
任务 A -> Take -> 持有互斥量
```

此时：

- 任务 A 可以访问受保护资源；
- 任务 B、C 获取失败后阻塞；
- 任务 A 必须释放互斥量；
- 任务 B 或 C 不能代替 A 释放；
- 任务 A 释放时可能恢复原始优先级。

抽象模型：

```
typedef struct
{
    TaskHandle_t owner;
    uint32_t recursion_count;
    uint32_t waiting_task_count;
} mutex_t;
```

实际 FreeRTOS 内部结构更复杂，但核心就是：

```
mutex -> owner
```

---

## 3.3 优先级反转

优先级反转是指：

> **高优先级任务因为等待低优先级任务持有的资源，反而被中优先级任务间接阻塞。**

典型任务：

```
H：高优先级任务
M：中优先级任务
L：低优先级任务
```

执行过程：

```
1. L 获取互斥量
2. H 被唤醒，尝试获取互斥量
3. H 因资源被 L 持有而阻塞
4. M 抢占 L
5. L 无法运行，也无法释放互斥量
6. H 持续等待
```

调度关系：

```
H 等待 L
M 抢占 L
H 实际被 M 间接阻塞
```

这破坏了优先级调度应有的实时性。

---

## 3.4 优先级继承

优先级继承协议的核心规则：

```
高优先级任务 H 等待低优先级任务 L 持有的互斥量
        |
        v
L 临时继承 H 的优先级
        |
        v
L 抢占 M，尽快运行并释放互斥量
        |
        v
H 获取互斥量并运行
        |
        v
L 恢复原始优先级
```

注意：

- 优先级继承是**临时的**；
- 只在存在高优先级等待者时发生；
- 持有多个互斥量时，优先级恢复需要考虑其他等待者；
- 优先级继承不能消除锁竞争，只能缩短部分优先级反转窗口；
- 优先级继承不能解决死锁。

---

## 3.5 主流互斥协议

|协议|核心机制|优点|缺点|
|---|---|---|---|
|优先级继承（PIP）|持有者临时提升到最高等待者优先级|通用、实现相对简单|多锁嵌套时恢复复杂|
|优先级上限（PCP）|获取资源时提升到资源预设上限|可降低阻塞链，理论确定性好|需要提前配置资源上限|
|即时优先级上限（ICPP）|任务持有资源期间使用系统上限规则|更强的实时性分析能力|实现复杂、管理成本高|
|无协议|只有排他访问|简单|存在严重优先级反转|

FreeRTOS 原生互斥量主要使用：

```
优先级继承协议
```

通常不提供完整的优先级上限协议。

---

## 3.6 互斥量与其他机制对比

|机制|所有权|优先级继承|ISR 使用|典型用途|
|---|---|---|---|---|
|互斥量|有|是|通常不允许|保护共享资源|
|二值信号量|无|否|可释放|事件同步|
|计数信号量|无|否|可释放|资源数量、事件累计|
|临界区|隐式|不适用|可有限使用|极短原子操作|
|调度器锁|无|不适用|否|防止任务切换|
|自旋锁|无或显式|通常无|多核场景|极短跨核保护|
|消息队列|无|否|支持发送|数据传输|

---

## 4. 核心特性横向对比

## 4.1 二值信号量与互斥量

|维度|互斥量|二值信号量|
|---|---|---|
|主要语义|资源保护|事件同步|
|所有者|有|无|
|释放者|持有者|任意合法上下文|
|优先级继承|**支持**|不支持|
|ISR 释放|通常不允许|支持|
|递归获取|递归互斥量支持|通常不支持|
|典型场景|共享 SPI 总线|DMA 完成通知|
|主要风险|死锁、持锁过久|丢事件、错误释放|

## 4.2 不同资源保护方式对比

|方案|进入/退出开销|可阻塞|优先级继承|适合保护时间|适用场景|
|---|---|---|---|---|---|
|互斥量|中|是|是|中短|任务间共享资源|
|临界区|低|否|不适用|极短|原子变量、寄存器|
|调度器锁|低~中|否|不适用|短|防止任务切换|
|自旋锁|低~中|忙等|通常否|极短|多核 RTOS|
|任务代理|通信开销|是|不需要|任意|高实时性设备访问|
|无锁结构|低|否|不需要|受限|单生产者/消费者|

核心原则：

> **任务可能等待共享资源时使用互斥量；只需保护几条指令时优先考虑临界区或原子操作。**

---

## 4.3 优先级继承的收益与代价

|项目|无优先级继承|有优先级继承|
|---|---|---|
|优先级反转|可能严重|显著降低|
|代码复杂度|低|中|
|内核开销|低|较高|
|任务优先级稳定性|高|运行时暂时变化|
|死锁风险|存在|仍然存在|
|最坏阻塞可分析性|差|较好，但需分析锁嵌套|
|适合高实时性|较差|更适合|

---

## 5. 底层原理与功能特性深度解析

以下以 FreeRTOS 为主要实现。

## 5.1 FreeRTOS 互斥量的创建

动态创建：

```
SemaphoreHandle_t mutex;

mutex = xSemaphoreCreateMutex();

configASSERT(mutex != NULL);
```

静态创建：

```
static StaticSemaphore_t g_spi_mutex_storage;
static SemaphoreHandle_t g_spi_mutex;

void spi_mutex_init(void)
{
    g_spi_mutex =
        xSemaphoreCreateMutexStatic(
            &g_spi_mutex_storage);

    configASSERT(g_spi_mutex != NULL);
}
```

FreeRTOS 互斥量本质上仍基于队列控制块，但对象类型不同：

```
queueQUEUE_TYPE_MUTEX
```

与普通二值信号量相比，互斥量会额外维护：

- 持有者；
- 递归持有计数；
- 持有互斥量数量；
- 任务原始优先级；
- 优先级继承相关状态。

---

## 5.2 互斥量的核心内部状态

FreeRTOS 任务控制块中通常包含类似字段：

```
typedef struct tskTaskControlBlock
{
    UBaseType_t uxPriority;
    UBaseType_t uxBasePriority;

    UBaseType_t uxMutexesHeld;

    ListItem_t xStateListItem;
    ListItem_t xEventListItem;

    /* 其他字段 */
} TCB_t;
```

含义：

|字段|含义|
|---|---|
|`uxPriority`|当前有效优先级|
|`uxBasePriority`|任务原始优先级|
|`uxMutexesHeld`|当前持有的互斥量数量|
|`pxMutexHolder`|互斥量当前持有者|

在没有优先级继承时：

```
uxPriority == uxBasePriority
```

发生优先级继承后：

```
uxPriority > uxBasePriority
```

---

## 5.3 互斥量获取路径

任务调用：

```
xSemaphoreTake(mutex, timeout);
```

最终进入队列获取路径，并区别处理互斥量。

可以抽象为：

```
BaseType_t xQueueSemaphoreTake(
    QueueHandle_t mutex,
    TickType_t timeout)
{
    TaskHandle_t current = xTaskGetCurrentTaskHandle();

    taskENTER_CRITICAL();

    if (mutex->count > 0U)
    {
        mutex->count = 0U;
        mutex->owner = current;

        current->uxMutexesHeld++;

        taskEXIT_CRITICAL();
        return pdPASS;
    }

    if (mutex->owner == current &&
        mutex->is_recursive == true)
    {
        mutex->recursive_count++;

        taskEXIT_CRITICAL();
        return pdPASS;
    }

    if (timeout == 0U)
    {
        taskEXIT_CRITICAL();
        return errQUEUE_EMPTY;
    }

    /*
     * 当前任务将要阻塞。
     * 如果当前任务优先级高于持有者，
     * 执行优先级继承。
     */
    if (current->priority >
        mutex->owner->priority)
    {
        inherit_priority(
            mutex->owner,
            current->priority);
    }

    place_task_on_mutex_wait_list(
        current,
        mutex);

    taskEXIT_CRITICAL();

    portYIELD_WITHIN_API();

    return when_woken;
}
```

实际实现还包括：

- 超时列表；
- 任务事件列表；
- 锁持有者删除处理；
- 调度器挂起；
- 继承优先级传播；
- 多锁状态处理；
- 任务优先级重新排序。

---

## 5.4 优先级继承的内核过程

假设：

```
任务 L：原始优先级 2，持有 mutex
任务 M：优先级 5，就绪
任务 H：优先级 10，等待 mutex
```

当 H 调用：

```
xSemaphoreTake(mutex, timeout);
```

内核执行逻辑：

```
1. 发现 mutex 被 L 持有
2. H 的优先级为 10，高于 L 的当前优先级 2
3. 将 L 的有效优先级提升到 10
4. 将 L 在原优先级就绪列表中移除
5. 将 L 放入优先级 10 的就绪列表
6. H 进入 mutex 等待列表
7. 调度器选择 L 继续执行
8. L 尽快完成临界资源访问
9. L 释放 mutex
10. H 被唤醒并获取 mutex
11. L 恢复原始优先级 2
```

调度过程：

```
没有优先级继承：

H 阻塞
M 运行
L 无法运行
H 长时间等待

有优先级继承：

H 阻塞
L 临时提升为 10
L 抢占 M
L 释放锁
H 运行
```

---

## 5.5 优先级继承不是优先级提升的永久修改

错误理解：

```
任务 L 的优先级被永久改为 H 的优先级
```

正确理解：

```
L 的有效优先级临时提升
L 的基础优先级保持不变
```

状态变化：

```
基础优先级：2
继承后有效优先级：10
释放相关互斥量后：
有效优先级恢复为 2
```

对应概念：

```
base priority：设计配置的优先级
effective priority：当前调度使用的优先级
```

---

## 5.6 多个互斥量与优先级恢复

这是工程中容易忽略的复杂场景。

任务 L：

```
L 获取 mutex_A
L 获取 mutex_B
```

随后：

```
任务 H 等待 mutex_A
任务 M 等待 mutex_B
```

L 的有效优先级至少需要覆盖仍然等待的最高优先级任务。

如果 L 只释放 `mutex_A`，但仍持有 `mutex_B`：

```
不能简单地立即恢复到基础优先级
```

否则 L 可能仍需要继续处理 `mutex_B`，而 M 仍在等待。

FreeRTOS 的优先级继承实现通常使用：

```
持有互斥量数量
```

辅助判断何时进行优先级恢复。

工程结论：

> **不要依赖复杂嵌套锁下的隐式优先级恢复来保证严格实时性。**

更好的做法：

- 缩短锁持有时间；
- 避免一个任务同时持有多个互斥量；
- 按全局顺序获取多个锁；
- 将共享资源合并到单一访问层；
- 对高实时任务使用资源代理。

---

## 5.7 互斥量释放路径

任务调用：

```
xSemaphoreGive(mutex);
```

简化逻辑：

```
BaseType_t xQueueGiveMutexRecursive(
    QueueHandle_t mutex)
{
    TaskHandle_t current =
        xTaskGetCurrentTaskHandle();

    configASSERT(mutex->owner == current);

    if (mutex->recursive_count > 0U)
    {
        mutex->recursive_count--;
        return pdPASS;
    }

    mutex->owner = NULL;
    mutex->count = 1U;

    current->uxMutexesHeld--;

    if (current->uxMutexesHeld == 0U)
    {
        current->uxPriority =
            current->uxBasePriority;
    }

    wake_highest_priority_waiter(mutex);

    return pdPASS;
}
```

实际 FreeRTOS 对普通互斥量和递归互斥量路径有所区别。

释放时需要完成：

1. 验证当前任务是持有者；
2. 清除所有权；
3. 更新持有计数；
4. 恢复或重新计算任务有效优先级；
5. 唤醒等待任务；
6. 必要时触发调度。

---

## 5.8 递归互斥量

普通互斥量不允许同一任务重复获取：

```
xSemaphoreTake(mutex, ...);
xSemaphoreTake(mutex, ...);  /* 可能死锁 */
```

递归互斥量允许：

```
xSemaphoreTakeRecursive(mutex, timeout);
xSemaphoreTakeRecursive(mutex, timeout);

xSemaphoreGiveRecursive(mutex);
xSemaphoreGiveRecursive(mutex);
```

规则：

```
获取次数 = 释放次数
```

示例：

```
static SemaphoreHandle_t g_driver_recursive_mutex;

bool driver_lock(TickType_t timeout)
{
    return xSemaphoreTakeRecursive(
               g_driver_recursive_mutex,
               timeout) == pdPASS;
}

void driver_unlock(void)
{
    BaseType_t ret =
        xSemaphoreGiveRecursive(
            g_driver_recursive_mutex);

    configASSERT(ret == pdPASS);
}
```

递归互斥量适合：

- 分层驱动 API；
- 公共函数可能被已加锁函数调用；
- 同一任务内部存在合法嵌套访问。

但它可能掩盖设计问题：

- 锁边界不清；
- 调用层次过深；
- 锁持有时间不可控；
- 释放次数不匹配。

---

## 5.9 互斥量不能在 ISR 中使用

错误：

```
void SPI_IRQHandler(void)
{
    xSemaphoreTake(g_spi_mutex, 0);
}
```

原因：

- ISR 不能阻塞；
- 互斥量存在所有权；
- 优先级继承依赖任务上下文；
- ISR 没有可恢复的持锁生命周期；
- 中断嵌套下的所有权模型不成立。

正确架构：

```
ISR：
    清中断
    保存状态
    通知任务

任务：
    获取互斥量
    访问共享外设
    释放互斥量
```

如果 ISR 必须快速访问硬件寄存器：

- 使用硬件设计保证寄存器访问不会与任务冲突；
- 使用极短临界区；
- 重新分配外设所有权；
- 通过任务代理访问设备。

---

## 5.10 内存可见性与互斥量

互斥量不仅提供排他访问，也通常形成同步顺序：

```
任务 A：
    修改共享数据
    Give mutex

任务 B：
    Take mutex
    读取共享数据
```

但工程上不能将 `volatile` 当作互斥量替代品。

错误：

```
volatile bool locked;
```

原因：

- 检查和设置不是原子操作；
- 两个任务可能同时看到 `false`；
- 没有等待队列；
- 没有优先级继承；
- 没有所有权；
- 没有超时阻塞语义。

应使用：

```
xSemaphoreTake();
访问共享数据
xSemaphoreGive();
```

---

## 6. 性能量化分析

以下为典型测试参考：

```
MCU：STM32F407
CPU：Cortex-M4F，168 MHz
FreeRTOS：10.x
编译：GCC -O2
Tick：1 kHz
测量：DWT CYCCNT + GPIO
```

实际结果取决于端口、配置和临界区实现。

## 6.1 典型内存开销

|对象|典型 RAM|
|---|---|
|动态互斥量控制块|约 80~110 字节|
|堆管理额外开销|约 8~16 字节|
|静态互斥量|约 80~110 字节|
|递归互斥量|通常与普通互斥量同量级|

准确值应使用：

```
sizeof(StaticSemaphore_t)
```

进行确认。

---

## 6.2 典型操作开销

|操作|典型周期|168 MHz 时间|
|---|---|---|
|无竞争 Take|300~550 cycles|1.8~3.3 μs|
|无竞争 Give|300~550 cycles|1.8~3.3 μs|
|竞争后阻塞|500~1000 cycles + 阻塞时间|3.0~6.0 μs + 等待|
|优先级继承处理|100~400 cycles 额外|0.6~2.4 μs|
|唤醒高优先级任务并切换|700~1500 cycles|4.2~8.9 μs|
|临界区保护极短变量|50~150 cycles|0.3~0.9 μs|

计算公式：

```
T = cycles / CPU_frequency
```

例如：

```
1500 / 168 MHz ≈ 8.93 μs
```

---

## 6.3 互斥量总等待时间

任务获取共享资源的总等待时间可近似为：

```
Twait =
    Tcritical_resource
  + Tqueue_wait
  + Tpreemption
  + Tinterrupt_block
  + Tscheduling
```

其中：

- `Tcritical_resource`：持有者访问资源的时间；
- `Tqueue_wait`：等待前方任务释放；
- `Tpreemption`：持有者被抢占时间；
- `Tinterrupt_block`：中断或临界区造成的延迟；
- `Tscheduling`：调度和上下文切换开销。

优先级继承主要降低：

```
Tpreemption
```

不能直接减少：

```
Tcritical_resource
```

因此：

> **优先级继承不是缩短临界区的替代方案。**

---

## 6.4 优先级反转示例量化

假设：

```
低优先级任务 L 持锁时间：100 μs
中优先级任务 M 每次运行：500 μs
高优先级任务 H 等待锁
```

无优先级继承时：

```
L 获取锁
H 阻塞
M 抢占 L 运行 500 μs
L 继续运行并释放锁
H 最坏等待 ≈ 600 μs + 调度开销
```

有优先级继承时：

```
H 阻塞
L 继承 H 的优先级
L 立即抢占 M
L 再运行 100 μs
释放锁
H 被唤醒
```

H 的等待时间接近：

```
100 μs + 上下文切换开销
```

收益约为：

```
600 μs -> 100 μs
```

但如果 L 在临界区中执行：

```
I2C 设备等待 2 ms
```

优先级继承不能消除这 2 ms 的物理等待。

---

## 6.5 持锁时间预算

定义：

```
Tlock_max
```

为一次持有互斥量的最坏时间。

对于高优先级任务，应满足：

```
Tlock_max < 允许阻塞预算
```

例如高优先级控制任务周期：

```
Tperiod = 1 ms
```

允许同步阻塞预算：

```
Bmutex <= 50 μs
```

那么共享资源访问必须满足：

```
Tlock_max + 调度和中断开销 <= 50 μs
```

如果 SPI 传输需要 300 μs，则不应让控制任务直接竞争该 SPI 锁，应考虑：

- DMA；
- 预取数据；
- 设备代理任务；
- 双缓冲；
- 将控制路径与低速通信路径分离。

---

## 6.6 优先级继承的限制

优先级继承不能解决：

1. **死锁**
    
    - A 等 B；
    - B 等 A。
2. **持锁任务自身阻塞**
    
    - 持锁后等待另一个事件；
    - 等待 DMA 完成；
    - 等待消息队列。
3. **中断造成的延迟**
    
    - 高优先级 ISR 长时间运行；
    - 临界区关闭中断过久。
4. **锁粒度过大**
    
    - 保护范围包含日志、I/O 和复杂计算。
5. **锁顺序错误**
    
    - 多锁反向获取。
6. **任务优先级设计错误**
    
    - 资源访问任务基础优先级过低；
    - 后台任务占用 CPU。

---

## 6.7 性能优化与收益

|优化措施|典型收益|
|---|---|
|缩短持锁范围|直接降低最高优先级任务阻塞时间|
|锁内禁止日志和动态分配|降低不可预测延迟|
|任务代理访问外设|将锁竞争转换为消息排队|
|DMA 替代同步轮询|缩短 CPU 持锁时间|
|细化锁粒度|提高并发度，但增加死锁复杂度|
|静态创建互斥量|消除运行时堆分配失败|
|使用递归锁前先审查调用层次|避免掩盖锁设计错误|
|建立全局锁顺序|降低死锁概率|
|记录锁等待时间|可发现实时性退化|

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
是否存在共享资源？
|
+-- 否
|   |
|   +-- 是事件同步？
|       |
|       +-- 是 -> 二值信号量/任务通知/计数信号量
|       +-- 否 -> 重新定义通信模型
|
+-- 是
    |
    +-- 资源是否允许多个任务同时访问？
    |   |
    |   +-- 是 -> 不需要互斥量，使用并发安全接口
    |   +-- 否
    |
    +-- 访问者是否全部在任务上下文？
    |   |
    |   +-- 否，包含 ISR
    |   |   |
    |   |   +-- ISR 是否只需极短原子访问？
    |   |       |
    |   |       +-- 是 -> 临界区/原子操作/硬件机制
    |   |       +-- 否 -> ISR 通知任务，由任务持锁访问
    |   |
    |   +-- 是
    |       |
    |       +-- 是否可能出现优先级竞争？
    |           |
    |           +-- 是 -> 支持优先级继承的互斥量
    |           +-- 否 -> 仍优先使用互斥量表达所有权
    |
    +-- 是否需要同一任务嵌套获取？
        |
        +-- 是 -> 递归互斥量，但先审查锁设计
        +-- 否 -> 普通互斥量
```

## 7.2 典型场景

|场景|推荐方案|理由|
|---|---|---|
|多任务共享 SPI 总线|互斥量|资源具备明确所有权|
|多任务访问 I2C|互斥量|防止事务交错|
|ISR 通知任务 DMA 完成|二值信号量/任务通知|这是事件，不是资源保护|
|保护两个寄存器的原子更新|临界区/原子操作|锁开销过大|
|多任务共享文件系统|互斥量或文件系统内部锁|需要排他访问|
|高优先级控制任务访问低速设备|任务代理|避免高优先级任务长时间持锁|
|固定内存池|计数信号量 + 互斥量|一个管理数量，一个保护链表|
|多条件设备状态|事件标志组|不属于排他访问|
|多核共享短变量|自旋锁/原子操作|不能直接套用单核互斥量|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：所有共享资源都应有明确的所有权模型

应明确：

```
谁可以获取？
谁负责释放？
是否允许递归？
持有期间能否阻塞？
最大持锁时间是多少？
```

### 原则二：只保护必要代码

错误：

```
Take(mutex);
read_sensor();
printf("sensor=%d\n", value);
calculate_filter();
write_flash();
Give(mutex);
```

正确：

```
Take(mutex);
read_shared_registers();
copy_data_to_local_buffer();
Give(mutex);

calculate_filter();
log_value();
write_flash();
```

原则：

> **锁内只保留共享资源访问，计算和日志尽量移到锁外。**

### 原则三：持锁后不得无界阻塞

高风险操作：

- `vTaskDelay()`；
- `xQueueReceive(..., portMAX_DELAY)`；
- 等待 DMA；
- 等待网络；
- 等待用户输入；
- 文件系统慢速 I/O；
- 动态内存分配。

如必须等待，应重新设计资源所有权。

### 原则四：所有任务使用统一锁顺序

例如定义：

```
Lock A：系统状态锁
Lock B：SPI 总线锁
Lock C：设备对象锁
```

任何任务必须按：

```
A -> B -> C
```

获取，释放时反向：

```
C -> B -> A
```

禁止：

```
任务 1：A -> B
任务 2：B -> A
```

### 原则五：优先级继承不是性能优化

它解决的是：

```
优先级反转造成的间接阻塞
```

它不解决：

```
锁内执行时间过长
锁竞争过于频繁
死锁
设备本身响应慢
```

---

## 8.2 选型决策矩阵

评分范围：

```
1：不适合
3：可用
5：最佳
```

|需求|互斥量|二值信号量|临界区|任务代理|原子操作|
|---|---|---|---|---|---|
|共享外设保护|5|1|2|4|1|
|优先级反转防护|5|1|不适用|5|不适用|
|ISR 使用|1|5|4|4|5|
|极短临界操作|3|1|5|2|5|
|可阻塞等待|5|4|1|5|1|
|明确所有权|5|1|1|4|1|
|低延迟|3|4|5|3|5|
|复杂设备事务|3|1|1|5|1|
|代码简单性|4|4|4|2|3|

---

## 8.3 工业级编码规范

### 互斥量命名

推荐：

```
spi_bus_mutex
i2c_controller_mutex
flash_driver_mutex
filesystem_mutex
```

不推荐：

```
sem1
lock
sync
```

### 统一获取包装

```
typedef enum
{
    LOCK_OK = 0,
    LOCK_TIMEOUT,
    LOCK_INVALID
} lock_result_t;

static lock_result_t driver_lock(
    SemaphoreHandle_t mutex,
    TickType_t timeout)
{
    if (mutex == NULL)
    {
        return LOCK_INVALID;
    }

    if (xSemaphoreTake(
            mutex,
            timeout) != pdPASS)
    {
        return LOCK_TIMEOUT;
    }

    return LOCK_OK;
}
```

### 统一释放检查

```
static void driver_unlock(
    SemaphoreHandle_t mutex)
{
    BaseType_t ret =
        xSemaphoreGive(mutex);

    configASSERT(ret == pdPASS);
}
```

### 持锁时间统计

```
typedef struct
{
    uint32_t take_count;
    uint32_t timeout_count;
    uint32_t max_wait_cycles;
    uint32_t max_hold_cycles;
} mutex_stats_t;
```

### 禁止规则

在锁内禁止执行：

```
printf
malloc/free
无限等待
vTaskDelay
不可控 I/O
复杂算法
回调外部代码
调用可能再次获取其他锁的未知函数
```

---

## 9. 常见错误与避坑指南

## 9.1 错误一：使用二值信号量保护共享资源

### 错误代码

```
static SemaphoreHandle_t g_spi_sem;

void spi_transfer_guarded(
    const uint8_t *tx,
    uint8_t *rx,
    size_t length)
{
    xSemaphoreTake(
        g_spi_sem,
        portMAX_DELAY);

    spi_transfer(tx, rx, length);

    xSemaphoreGive(g_spi_sem);
}
```

### 根因分析

如果 `g_spi_sem` 是二值信号量：

- 不具备可靠所有权；
- 非持有者可能错误释放；
- 不支持优先级继承；
- 不能正确表达资源保护语义。

### 正确实现

```
static SemaphoreHandle_t g_spi_mutex;

bool spi_transfer_guarded(
    const uint8_t *tx,
    uint8_t *rx,
    size_t length,
    TickType_t timeout)
{
    if (xSemaphoreTake(
            g_spi_mutex,
            timeout) != pdPASS)
    {
        return false;
    }

    bool ok = spi_transfer(tx, rx, length);

    if (xSemaphoreGive(g_spi_mutex) != pdPASS)
    {
        fault_manager_report(
            FAULT_SPI_MUTEX_RELEASE);
        ok = false;
    }

    return ok;
}
```

### 风险影响

- 优先级反转；
- 总线事务交错；
- 设备寄存器配置损坏；
- 低概率通信错误。

---

## 9.2 错误二：非持有者释放互斥量

### 错误代码

```
/* 任务 A */
xSemaphoreTake(g_mutex, portMAX_DELAY);
start_dma();

/* DMA ISR */
void DMA_IRQHandler(void)
{
    xSemaphoreGive(g_mutex); /* 错误 */
}
```

### 根因分析

ISR 不是互斥量持有者，且 ISR 不应操作互斥量。

正确的语义应是：

```
任务 A 持有互斥量
ISR 通知任务 A DMA 完成
任务 A 处理完成并释放互斥量
```

### 正确实现

```
static SemaphoreHandle_t g_dma_done_sem;

static bool spi_dma_transfer(
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

    bool ok = spi_dma_start(tx, rx, length);

    if (ok)
    {
        ok = xSemaphoreTake(
                 g_dma_done_sem,
                 pdMS_TO_TICKS(100)) == pdPASS;
    }

    spi_dma_stop_if_needed();

    xSemaphoreGive(g_spi_mutex);

    return ok;
}

void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    dma_clear_flags();

    xSemaphoreGiveFromISR(
        g_dma_done_sem,
        &woken);

    portYIELD_FROM_ISR(woken);
}
```

更进一步，若 DMA 等待期间不应占用总线锁，应将资源所有权拆分，避免长时间持锁。

### 风险影响

- 互斥量所有权破坏；
- 任务误以为自己持锁；
- 其他任务在硬件事务未完成时进入；
- 内核断言或数据损坏。

---

## 9.3 错误三：锁内执行无限等待

### 错误代码

```
xSemaphoreTake(g_device_mutex, portMAX_DELAY);

xQueueReceive(
    g_response_queue,
    &response,
    portMAX_DELAY);

xSemaphoreGive(g_device_mutex);
```

### 根因分析

任务持有设备锁时等待外部响应：

- 其他任务无法访问设备；
- 响应可能恰好需要其他任务触发；
- 形成锁与消息等待的环；
- 高优先级任务可能长期阻塞。

### 正确实现

```
bool device_request(
    const request_t *request,
    response_t *response)
{
    bool ok = false;

    if (xSemaphoreTake(
            g_device_mutex,
            pdMS_TO_TICKS(20)) != pdPASS)
    {
        return false;
    }

    ok = device_send_request(request);

    xSemaphoreGive(g_device_mutex);

    if (!ok)
    {
        return false;
    }

    /*
     * 锁外等待响应。
     */
    return xQueueReceive(
               g_response_queue,
               response,
               pdMS_TO_TICKS(100)) == pdPASS;
}
```

### 风险影响

- 死锁；
- 资源长期占用；
- 其他任务级联超时；
- 看门狗复位。

---

## 9.4 错误四：多锁反向获取导致死锁

### 错误代码

```
/* 任务 A */
xSemaphoreTake(g_spi_mutex, portMAX_DELAY);
xSemaphoreTake(g_device_mutex, portMAX_DELAY);

/* 任务 B */
xSemaphoreTake(g_device_mutex, portMAX_DELAY);
xSemaphoreTake(g_spi_mutex, portMAX_DELAY);
```

### 根因分析

执行过程：

```
A 持有 SPI，等待 Device
B 持有 Device，等待 SPI
```

两个任务都无法继续。

优先级继承不能解决锁顺序死锁。

### 正确实现

统一顺序：

```
static bool acquire_device_path(TickType_t timeout)
{
    if (xSemaphoreTake(
            g_spi_mutex,
            timeout) != pdPASS)
    {
        return false;
    }

    if (xSemaphoreTake(
            g_device_mutex,
            timeout) != pdPASS)
    {
        xSemaphoreGive(g_spi_mutex);
        return false;
    }

    return true;
}

static void release_device_path(void)
{
    xSemaphoreGive(g_device_mutex);
    xSemaphoreGive(g_spi_mutex);
}
```

所有调用者统一：

```
SPI -> Device
```

### 风险影响

- 系统永久死锁；
- 任务无法恢复；
- 看门狗复位；
- 故障复现依赖时序，难以调试。

---

## 9.5 错误五：持锁执行复杂计算和日志

### 错误代码

```
xSemaphoreTake(g_state_mutex, portMAX_DELAY);

update_shared_state();
run_large_filter();
printf("state=%d\n", state);
save_to_flash();

xSemaphoreGive(g_state_mutex);
```

### 根因分析

锁保护范围远大于共享数据访问，导致：

- 锁持有时间不可预测；
- 高优先级任务等待时间增加；
- 日志和 Flash 操作导致毫秒级阻塞；
- 优先级继承扩大高优先级任务影响范围。

### 正确实现

```
state_snapshot_t snapshot;

xSemaphoreTake(
    g_state_mutex,
    pdMS_TO_TICKS(10));

snapshot = g_shared_state;

xSemaphoreGive(g_state_mutex);

run_large_filter(&snapshot);
printf("state=%d\n", snapshot.state);
save_to_flash(&snapshot);
```

### 风险影响

- 实时性恶化；
- 高优先级任务周期抖动；
- 低优先级任务长期处于继承优先级；
- 锁竞争放大。

---

## 9.6 错误六：不检查互斥量获取结果

### 错误代码

```
xSemaphoreTake(
    g_mutex,
    pdMS_TO_TICKS(10));

shared_data_update();

xSemaphoreGive(g_mutex);
```

### 根因分析

获取可能超时。如果忽略返回值，任务会在未持锁的情况下访问共享资源，并且还可能错误执行释放。

### 正确实现

```
if (xSemaphoreTake(
        g_mutex,
        pdMS_TO_TICKS(10)) != pdPASS)
{
    mutex_timeout_record();
    return false;
}

bool ok = shared_data_update();

BaseType_t give_ret =
    xSemaphoreGive(g_mutex);

configASSERT(give_ret == pdPASS);

return ok;
```

### 风险影响

- 数据竞争；
- 内存破坏；
- 互斥量状态损坏；
- 随机死锁。

---

## 9.7 错误七：把递归互斥量当作普通互斥量使用

### 错误代码

```
xSemaphoreTakeRecursive(g_mutex, timeout);

/* 某异常路径 */
xSemaphoreGive(g_mutex); /* API 不匹配 */
```

### 根因分析

递归互斥量必须使用配套 API，且获取和释放次数必须严格匹配。

### 正确实现

```
if (xSemaphoreTakeRecursive(
        g_recursive_mutex,
        timeout) != pdPASS)
{
    return false;
}

bool ok = nested_driver_operation();

BaseType_t ret =
    xSemaphoreGiveRecursive(
        g_recursive_mutex);

configASSERT(ret == pdPASS);

return ok;
```

### 风险影响

- 锁计数不一致；
- 资源永久不释放；
- 后续任务永久阻塞；
- 断言或不可预测行为。

---

## 10. 多机制组合使用方案

## 10.1 互斥量 + 二值信号量：DMA 外设事务

典型需求：

```
多个任务共享 SPI
SPI 使用 DMA
DMA 完成通过 ISR 通知当前任务
```

角色分工：

```
spi_mutex：
    保护 SPI 控制器配置和总线所有权

dma_done_sem：
    表示当前 DMA 事务完成

DMA ISR：
    只 Give dma_done_sem

调用任务：
    Take spi_mutex
    启动 DMA
    等待 dma_done_sem
    释放 spi_mutex
```

注意：

如果 DMA 等待时间较长，任务持有总线互斥量期间，其他任务无法使用 SPI。这是正确性和并发度之间的权衡。

如果 DMA 期间硬件总线可以安全交给其他事务，则应进一步拆分：

```
配置锁
事务队列
DMA 完成状态
设备片选所有权
```

---

## 10.2 互斥量 + 计数信号量：固定资源池

```
free_count：
    计数信号量，表示空闲对象数量

free_list_mutex：
    保护空闲链表

free_list：
    保存实际资源对象
```

操作顺序：

```
Take free_count
Take free_list_mutex
从链表获取对象
Give free_list_mutex
```

归还顺序：

```
Take free_list_mutex
对象放回链表
Give free_list_mutex
Give free_count
```

必须处理异常：

```
Take count 成功但链表为空
    -> 恢复 count
```

---

## 10.3 互斥量 + 事件标志组：设备状态与资源访问

例如网络设备：

```
net_state_event：
    NET_READY
    NET_LINK_DOWN
    NET_ERROR

net_config_mutex：
    保护配置结构和驱动寄存器
```

任务流程：

```
if (xEventGroupWaitBits(
        g_net_events,
        NET_READY,
        pdFALSE,
        pdTRUE,
        pdMS_TO_TICKS(1000)) == 0U)
{
    return false;
}

if (xSemaphoreTake(
        g_net_config_mutex,
        pdMS_TO_TICKS(20)) != pdPASS)
{
    return false;
}

net_update_configuration();

xSemaphoreGive(g_net_config_mutex);
```

事件组表达：

```
当前状态是否满足条件
```

互斥量表达：

```
谁可以修改配置
```

---

## 10.4 互斥量 + 任务代理

对于高实时任务访问慢速设备，推荐任务代理模式：

```
高优先级控制任务
    |
    +-- 发送设备请求
    +-- 不直接持有慢速设备锁
    |
    v
设备代理任务
    |
    +-- 独占设备
    +-- 处理请求
    +-- 返回结果
```

收益：

- 设备锁只由代理任务持有；
- 高优先级控制任务不被低速 I/O 长时间阻塞；
- 设备访问顺序天然串行；
- 可以集中处理超时、重试和错误恢复。

代价：

- 增加消息传输和调度延迟；
- 需要设计请求超时和取消机制；
- 适合事务型设备，不适合极短寄存器访问。

---

## 10.5 完整设备锁封装框架

```
typedef enum
{
    DRIVER_OK = 0,
    DRIVER_INVALID_ARG,
    DRIVER_LOCK_TIMEOUT,
    DRIVER_IO_ERROR
} driver_status_t;

typedef struct
{
    SemaphoreHandle_t mutex;
    SemaphoreHandle_t done_sem;

    volatile uint32_t lock_timeout_count;
    volatile uint32_t io_error_count;
    volatile uint32_t max_hold_cycles;
} spi_driver_t;

static spi_driver_t g_spi;

driver_status_t spi_driver_transfer(
    const uint8_t *tx,
    uint8_t *rx,
    size_t length,
    TickType_t lock_timeout,
    TickType_t io_timeout)
{
    uint32_t start_cycles;
    driver_status_t status =
        DRIVER_IO_ERROR;

    if ((tx == NULL && length != 0U) ||
        (rx == NULL && length != 0U) ||
        length == 0U)
    {
        return DRIVER_INVALID_ARG;
    }

    if (xSemaphoreTake(
            g_spi.mutex,
            lock_timeout) != pdPASS)
    {
        g_spi.lock_timeout_count++;
        return DRIVER_LOCK_TIMEOUT;
    }

    start_cycles = DWT->CYCCNT;

    /*
     * 清理旧完成状态，防止上一次事务的残留通知
     * 使本次传输误判为完成。
     */
    while (xSemaphoreTake(
               g_spi.done_sem,
               0U) == pdPASS)
    {
        /* drain stale completion */
    }

    if (!spi_hw_start_dma(tx, rx, length))
    {
        goto unlock;
    }

    if (xSemaphoreTake(
            g_spi.done_sem,
            io_timeout) != pdPASS)
    {
        spi_hw_abort();
        g_spi.io_error_count++;
        goto unlock;
    }

    status = spi_hw_check_result()
                 ? DRIVER_OK
                 : DRIVER_IO_ERROR;

unlock:
    {
        uint32_t hold_cycles =
            DWT->CYCCNT - start_cycles;

        if (hold_cycles > g_spi.max_hold_cycles)
        {
            g_spi.max_hold_cycles = hold_cycles;
        }
    }

    configASSERT(
        xSemaphoreGive(g_spi.mutex) == pdPASS);

    return status;
}

void SPI_DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;

    if (spi_hw_dma_complete())
    {
        spi_hw_clear_irq();

        xSemaphoreGiveFromISR(
            g_spi.done_sem,
            &woken);
    }

    portYIELD_FROM_ISR(woken);
}
```

设计要点：

- 事务前清空残留完成信号；
- 普通互斥量保护共享 SPI；
- ISR 只发送 DMA 完成事件；
- 所有阻塞都有超时；
- 记录最大持锁时间；
- 出错时执行硬件终止；
- 释放互斥量必须位于统一出口。

---

## 11. 工业级实际案例分析

## 11.1 案例一：多任务共享 SPI 传感器总线

### 需求

- 4 个任务访问同一 SPI 控制器；
- 任务优先级分别为 2、4、6、8；
- 每次事务包含：
    - 选择片选；
    - 配置 SPI；
    - DMA 传输；
    - 校验；
    - 释放片选。
- 最高优先级任务周期要求小于 1 ms。

### 错误架构

```
每个任务直接访问 SPI
不加锁
```

风险：

- SPI 配置被覆盖；
- 片选交错；
- DMA 源地址被覆盖；
- 事务边界破坏。

### 基础正确架构

```
spi_mutex：
    保护整个 SPI 事务

dma_done_sem：
    通知 DMA 完成
```

### 优先级反转分析

如果低优先级任务正在执行 SPI 事务，高优先级任务到达：

```
H 等待 spi_mutex
L 持有 spi_mutex
```

启用优先级继承后：

```
L 临时继承 H 的优先级
L 尽快完成事务
H 获得 spi_mutex
```

### 设计要点

- 不在锁内执行日志；
- 不在锁内执行复杂数据解析；
- SPI DMA 超时必须终止硬件；
- 片选必须由同一个锁保护；
- 记录锁等待和持锁时间；
- 如果某事务超过高优先级任务阻塞预算，改用 SPI 代理任务。

---

## 11.2 案例二：I2C 总线与设备驱动分层

### 需求

- 多个设备共享 I2C 总线；
- 设备驱动 API 可以相互调用；
- 某些公共 API 可能嵌套调用底层传输；
- 需要防止重复获取同一把锁。

### 方案一：递归互斥量

```
设备上层 API
    -> TakeRecursive
       -> 底层 I2C API
          -> TakeRecursive
             -> 传输
          -> GiveRecursive
    -> GiveRecursive
```

适用于：

- 已确认调用层次；
- 获取/释放配对明确；
- 锁内没有无限等待；
- 递归深度有限。

### 方案二：重构接口，避免递归锁

更推荐：

```
public API：
    负责加锁

private API：
    假设调用者已持锁，不再次加锁
```

示例：

```
static bool i2c_transfer_locked(
    uint8_t address,
    const uint8_t *tx,
    size_t tx_len,
    uint8_t *rx,
    size_t rx_len)
{
    return i2c_hw_transfer(
        address,
        tx,
        tx_len,
        rx,
        rx_len);
}

bool sensor_read_id(uint8_t *id)
{
    bool ok;

    if (xSemaphoreTake(
            g_i2c_mutex,
            pdMS_TO_TICKS(20)) != pdPASS)
    {
        return false;
    }

    ok = i2c_transfer_locked(
        SENSOR_ADDRESS,
        SENSOR_ID_REG,
        1U,
        id,
        1U);

    xSemaphoreGive(g_i2c_mutex);

    return ok;
}
```

### 设计结论

> **递归互斥量是解决合法嵌套的工具，不是掩盖锁边界混乱的手段。**

---

## 11.3 案例三：高实时控制任务访问低速 Flash

### 需求

- 控制任务周期：1 ms；
- Flash 写入时间：2~10 ms；
- 日志任务低优先级；
- 控制任务偶尔需要读取校准参数；
- 不允许控制任务被 Flash 写入阻塞数毫秒。

### 直接互斥量方案

```
Flash mutex
控制任务 Take
日志任务可能持锁写 Flash
控制任务阻塞 2~10 ms
```

即使有优先级继承，日志任务继承控制任务优先级后，仍可能在 Flash 操作期间持续占用资源。

### 推荐方案：Flash 代理任务

```
控制任务
    |
    +-- 发送读取请求
    +-- 等待响应
    |
Flash Agent Task
    |
    +-- 独占 Flash
    +-- 处理读写
    +-- 返回结果
```

对于控制任务读取：

- 将校准参数预加载到 RAM；
- 运行时从 RAM 读取；
- Flash 写入由代理任务异步处理；
- 采用双备份和版本号提交。

### 设计结论

优先级继承不能使慢速 Flash 变快。遇到高实时性和长时间 I/O 冲突，应改变架构，而不是单纯增加锁优先级。

---

## 12. 高频问题深度答疑

## 问题一：为什么二值信号量不能替代互斥量？

因为二值信号量缺少三个关键属性：

1. **所有权**
    - 谁获取，谁释放；
2. **优先级继承**
    - 高优先级等待时提升持有者；
3. **递归和持有状态管理**
    - 可选递归锁能够管理嵌套获取。

二值信号量的语义是：

```
某个事件可用
```

互斥量的语义是：

```
某个资源当前归某个任务独占
```

---

## 问题二：优先级继承能否完全消除优先级反转？

不能。

它主要解决：

```
中优先级任务无界抢占低优先级持有者
```

但以下阻塞仍然存在：

- 持锁任务本身执行时间；
- 持锁任务等待硬件；
- 更高优先级 ISR；
- 更高优先级任务；
- 其他资源锁；
- 锁嵌套；
- 调度器关闭时间。

因此，必须同时控制：

```
锁持有时间
锁等待时间
锁嵌套深度
锁顺序
中断阻塞时间
```

---

## 问题三：优先级继承和优先级上限有什么区别？

### 优先级继承

```
只有发生高优先级等待时，持有者才提升
```

优点：

- 动态；
- 通用；
- 不需要为每个锁配置上限。

缺点：

- 多锁场景复杂；
- 运行时状态变化；
- 实时性分析难度较高。

### 优先级上限

```
任务获取某资源后，立即提升到该资源预设上限
```

优点：

- 能提前避免部分优先级反转；
- 理论分析更明确。

缺点：

- 需要提前知道资源访问者优先级；
- 配置复杂；
- 可能产生不必要的优先级提升。

---

## 问题四：一个任务持有多个互斥量时，为什么不能简单恢复优先级？

例如：

```
L 持有 A 和 B
H 等待 A
M 等待 B
```

如果 L 释放 A 后立即恢复到基础优先级，而 M 仍等待 B，那么 L 可能被其他任务抢占，导致 B 长时间不释放。

因此优先级恢复必须考虑：

```
L 是否仍持有其他互斥量
其他互斥量上是否还有等待者
最高等待者优先级是多少
```

工程实践中应尽量避免：

```
一个任务同时持有多把锁
```

如果无法避免，必须建立：

- 全局锁顺序；
- 最大嵌套深度；
- 持锁时间预算；
- 锁依赖图；
- 死锁检测策略。

---

## 问题五：互斥量是否可以在中断和任务之间共用？

通常不可以。

正确模型应是：

```
ISR：
    记录状态
    发送任务通知/二值信号量

任务：
    获取互斥量
    操作共享资源
    释放互斥量
```

如果 ISR 和任务同时访问共享寄存器：

- 使用硬件规定的访问顺序；
- 使用极短临界区；
- 关闭相关中断；
- 使用原子位操作；
- 重新设计为单一任务拥有外设。

不能简单地让 ISR“抢互斥量”。

---

## 问题六：什么时候应使用任务代理替代互斥量？

满足以下条件时，任务代理通常更合适：

- 资源操作时间较长；
- 资源访问需要等待硬件；
- 高优先级任务不允许长时间阻塞；
- 访问顺序需要统一管理；
- 资源错误恢复复杂；
- 多个任务共享一个复杂设备；
- 设备访问需要异步排队。

任务代理的代价：

- 增加消息传递延迟；
- 需要请求和响应对象；
- 需要处理请求超时、取消和队列满。

---

## 13. 课程核心总结

## 13.1 核心要点

1. **互斥量用于保护共享资源，具备所有权语义。**
2. 只有持有者才能释放互斥量。
3. FreeRTOS 互斥量通常支持优先级继承。
4. 优先级继承通过临时提升低优先级持有者，减少中优先级任务造成的间接阻塞。
5. 优先级继承不能解决死锁、长时间持锁和慢速硬件等待。
6. 互斥量通常不能在 ISR 中使用。
7. 所有锁等待都应设置超时或具备明确的永久等待证明。
8. 锁内应只保留必要的共享资源访问。
9. 多锁场景必须建立全局锁顺序。
10. 高实时任务访问慢速资源时，优先考虑任务代理、DMA、缓存和异步架构。

## 13.2 典型性能排序

针对极短共享变量保护：

```
原子操作
    >
临界区
    >
互斥量
```

针对可阻塞的任务间共享资源：

```
互斥量
    >
二值信号量
    >
临界区
```

这里的排序不是绝对性能排序，而是针对不同语义的适用性排序。

## 13.3 通用选型结论

```
任务之间排他访问共享资源：
    互斥量

共享资源竞争可能产生优先级反转：
    支持优先级继承的互斥量

极短、不可阻塞的原子更新：
    临界区或原子操作

ISR 通知任务：
    二值信号量或任务通知

慢速共享设备：
    任务代理

多个资源嵌套访问：
    全局锁顺序 + 尽量减少嵌套

高实时任务不能长时间等待：
    避免直接持锁访问慢速 I/O
```

---

## 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐机制|注意事项|
|---|---|---|
|多任务共享 SPI|互斥量|锁内只保留事务必要操作|
|多任务共享 I2C|互斥量|事务超时必须释放锁|
|DMA 完成通知|二值信号量/任务通知|不要用互斥量|
|保护单个计数器|原子操作/临界区|不必创建互斥量|
|高优先级任务访问慢速 Flash|任务代理/缓存|避免长时间持锁|
|固定资源池|计数信号量 + 互斥量|数量和对象必须一致|
|递归驱动调用|递归互斥量或接口重构|必须匹配获取/释放次数|
|多把锁同时获取|互斥量 + 全局锁顺序|释放按反向顺序|
|ISR 与任务共享外设|ISR 通知任务|不要让 ISR 获取互斥量|
|设备状态广播|事件标志组|不属于所有权保护|

## 14.2 API 速查表

|需求|FreeRTOS API|
|---|---|
|动态普通互斥量|`xSemaphoreCreateMutex()`|
|静态普通互斥量|`xSemaphoreCreateMutexStatic()`|
|动态递归互斥量|`xSemaphoreCreateRecursiveMutex()`|
|静态递归互斥量|`xSemaphoreCreateRecursiveMutexStatic()`|
|获取普通互斥量|`xSemaphoreTake()`|
|释放普通互斥量|`xSemaphoreGive()`|
|获取递归互斥量|`xSemaphoreTakeRecursive()`|
|释放递归互斥量|`xSemaphoreGiveRecursive()`|
|删除互斥量|`vSemaphoreDelete()`|
|ISR 释放互斥量|通常不允许|
|调度器断言|`configASSERT()`|

## 14.3 关键约束表

|项目|约束|
|---|---|
|所有权|必须由持有者释放|
|ISR|通常不能使用互斥量|
|优先级继承|只降低部分优先级反转影响|
|锁内阻塞|原则上禁止无限等待|
|锁顺序|多锁必须有全局顺序|
|锁粒度|越小越好，但不能破坏事务原子性|
|递归锁|获取和释放次数必须匹配|
|超时|必须处理获取失败|
|资源恢复|异常路径必须释放锁|
|锁内代码|禁止日志、动态分配和复杂计算|

---

## 15. 学习效果自检

### 基础理解

- [ ]  能解释互斥量和二值信号量的语义差异。
- [ ]  能解释什么是优先级反转。
- [ ]  能画出 L、M、H 三任务的优先级反转过程。
- [ ]  能解释优先级继承的提升和恢复过程。
- [ ]  能说明互斥量为什么不能在 ISR 中使用。

### API 能力

- [ ]  能使用 `xSemaphoreCreateMutexStatic()`。
- [ ]  能正确检查 `xSemaphoreTake()` 返回值。
- [ ]  能保证获取和释放路径配对。
- [ ]  能区分普通互斥量和递归互斥量 API。
- [ ]  能处理锁超时和设备恢复。

### 内核理解

- [ ]  能解释 `uxPriority` 和 `uxBasePriority` 的区别。
- [ ]  能说明 `uxMutexesHeld` 的用途。
- [ ]  能描述高优先级任务等待时的优先级继承路径。
- [ ]  能分析多互斥量持有时的优先级恢复问题。
- [ ]  能说明优先级继承为什么不能解决死锁。

### 工程设计能力

- [ ]  能为 SPI/I2C 设计互斥保护。
- [ ]  能建立多锁全局顺序。
- [ ]  能识别锁内不应执行的操作。
- [ ]  能设计 DMA + 互斥量 + 完成通知方案。
- [ ]  能判断何时使用任务代理替代互斥量。
- [ ]  能设计锁等待和持锁时间统计。

### 性能验证能力

- [ ]  能测量无竞争 Take/Give 延迟。
- [ ]  能测量锁竞争等待时间。
- [ ]  能测量优先级继承带来的调度变化。
- [ ]  能统计最大持锁时间和最大等待时间。
- [ ]  能验证高优先级任务周期是否满足阻塞预算。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：三任务优先级反转实验

创建三个任务：

```
L：优先级 2
M：优先级 5
H：优先级 10
```

实验过程：

```
L 获取互斥量并延迟
H 尝试获取互斥量
M 持续运行
```

分别测试：

```
普通二值信号量
互斥量
```

观察：

- H 的实际等待时间；
- L 是否被 M 长时间抢占；
- 启用优先级继承前后的 GPIO 波形；
- L 的有效优先级变化。

---

### 任务二：SPI 共享总线

实现：

```
三个任务共享 SPI
每个任务使用不同片选
SPI 使用 DMA
DMA 中断通知任务
SPI 互斥量保护总线
```

要求：

- 事务不能交错；
- 片选必须连续有效；
- DMA 超时能够终止；
- 所有错误路径释放互斥量；
- 统计最大锁等待和持锁时间。

---

### 任务三：多锁死锁注入

构造：

```
任务 A：Lock A -> Lock B
任务 B：Lock B -> Lock A
```

要求：

- 复现死锁；
- 使用统一锁顺序修复；
- 增加锁等待超时；
- 输出锁依赖和任务状态快照；
- 触发故障恢复而不是永久阻塞。

---

### 任务四：锁粒度优化

实现两种版本：

```
版本一：
    锁内执行数据拷贝、算法和日志

版本二：
    锁内只做共享数据快照
    算法和日志放在锁外
```

对比：

- 最大持锁时间；
- 高优先级任务最大等待时间；
- 系统抖动；
- CPU 利用率；
- 代码复杂度。

---

### 任务五：互斥量与任务代理对比

使用慢速 Flash 或 I2C 设备，分别实现：

```
直接互斥访问
任务代理访问
```

测量：

- 高优先级任务响应延迟；
- 请求平均延迟；
- 请求最坏延迟；
- 设备吞吐量；
- 任务栈和 RAM 占用；
- 异常恢复复杂度。

---

## 16.2 性能测试方法

### 方法一：测量无竞争锁路径

```
uint32_t start = DWT->CYCCNT;

BaseType_t ret =
    xSemaphoreTake(
        g_mutex,
        0U);

uint32_t take_cycles =
    DWT->CYCCNT - start;

configASSERT(ret == pdPASS);

start = DWT->CYCCNT;

ret = xSemaphoreGive(g_mutex);

uint32_t give_cycles =
    DWT->CYCCNT - start;

configASSERT(ret == pdPASS);
```

应记录：

```
平均值
最大值
最小值
99.9 分位值
```

---

### 方法二：测量优先级反转

在不同代码位置翻转 GPIO：

```
/* 低优先级任务获取锁 */
gpio_set(LOW_LOCK_ENTER_PIN);
xSemaphoreTake(g_mutex, portMAX_DELAY);
gpio_clear(LOW_LOCK_ENTER_PIN);

/* 高优先级任务开始等待 */
gpio_set(HIGH_WAIT_PIN);
xSemaphoreTake(g_mutex, portMAX_DELAY);
gpio_clear(HIGH_WAIT_PIN);

/* 高优先级任务获得锁 */
gpio_set(HIGH_LOCK_ACQUIRED_PIN);
```

测量：

```
高优先级任务开始等待
    ->
高优先级任务获得锁
```

分别在：

```
二值信号量
互斥量
互斥量 + 不同中优先级负载
```

下测试。

---

### 方法三：持锁时间监控

```
typedef struct
{
    uint32_t enter_cycles;
    uint32_t max_hold_cycles;
    uint32_t max_wait_cycles;
    uint32_t timeout_count;
} lock_monitor_t;

static lock_monitor_t g_spi_lock_monitor;

static bool spi_lock_take(
    TickType_t timeout)
{
    uint32_t start = DWT->CYCCNT;

    if (xSemaphoreTake(
            g_spi_mutex,
            timeout) != pdPASS)
    {
        g_spi_lock_monitor.timeout_count++;
        return false;
    }

    g_spi_lock_monitor.enter_cycles =
        DWT->CYCCNT;

    uint32_t wait_cycles =
        g_spi_lock_monitor.enter_cycles - start;

    if (wait_cycles >
        g_spi_lock_monitor.max_wait_cycles)
    {
        g_spi_lock_monitor.max_wait_cycles =
            wait_cycles;
    }

    return true;
}

static void spi_lock_give(void)
{
    uint32_t hold_cycles =
        DWT->CYCCNT -
        g_spi_lock_monitor.enter_cycles;

    if (hold_cycles >
        g_spi_lock_monitor.max_hold_cycles)
    {
        g_spi_lock_monitor.max_hold_cycles =
            hold_cycles;
    }

    configASSERT(
        xSemaphoreGive(g_spi_mutex) == pdPASS);
}
```

---

### 方法四：死锁和锁顺序检查

为每把锁分配静态等级：

```
typedef enum
{
    LOCK_LEVEL_STATE = 10,
    LOCK_LEVEL_BUS = 20,
    LOCK_LEVEL_DEVICE = 30
} lock_level_t;
```

任务持锁时记录最高等级：

```
当前已持有锁等级 = 20
禁止获取等级 <= 20 的新锁
```

在诊断版本中可以实现：

```
configASSERT(new_lock_level > current_lock_level);
```

该方法不能证明没有所有死锁，但可以快速发现大量反向锁顺序问题。

---

## 16.3 进阶学习方向

1. FreeRTOS：
    - `queue.c` 中的互斥量路径；
    - `tasks.c` 中的优先级继承；
    - 任务优先级恢复；
    - 任务删除时的锁处理。
2. 优先级继承协议的形式化分析。
3. 优先级上限协议和实时调度理论。
4. 死锁检测：
    - 资源分配图；
    - 锁依赖图；
    - 等待图；
    - 周期检测。
5. 锁粒度、锁顺序和资源分层。
6. 任务代理和异步设备驱动。
7. 多核 RTOS：
    - 自旋锁；
    - 内存屏障；
    - 跨核中断；
    - Cache 一致性。
8. 无锁算法：
    - CAS；
    - 单生产者单消费者队列；
    - 原子环形缓冲区。
9. 实时性分析：
    - 最坏阻塞时间；
    - WCET；
    - 资源访问协议；
    - 任务响应时间分析。
10. 工业级可观测性：
    - 锁等待直方图；
    - 最大持锁时间；
    - 锁竞争次数；
    - 任务阻塞快照；
    - 运行时死锁诊断；
    - 故障自动降级。