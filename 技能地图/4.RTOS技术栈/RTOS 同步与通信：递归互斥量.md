
本课以 **FreeRTOS 单核抢占式调度**为主要分析对象，重点解决三个工程问题：**同一任务为什么需要重复获取同一把锁、递归计数如何决定资源释放、递归互斥量如何影响优先级继承和最坏阻塞时间**。

源码说明以 FreeRTOS Kernel 10.x/11.x 常见实现为依据；涉及优先级恢复等行为时，应对照项目使用的具体版本。性能部分区分**可直接计算的数据、示例预算和需要上板获得的实测值**，不将估算写成实测结果。

## 1. 学习目标

|层级|本课能力产出|
|---|---|
|**理解**|理解所有者、递归深度、首次获取、最终释放之间的关系；区分递归互斥量与函数递归、可重入性|
|**掌握**|正确使用静态创建和递归 Take/Give API；处理失败路径、嵌套调用和超时|
|**精通**|分析 FreeRTOS 的所有者检查、递归计数、优先级继承及多锁恢复限制|
|**能够设计**|为分层驱动、复合设备操作设计锁边界，并证明最大递归深度、最大持锁时间和无环锁顺序|

完成课程后，应能够回答：

> 一个任务把递归互斥量获取了三次，释放两次之后，高优先级等待任务能否进入？为什么？

正确答案是：**不能。只有第三次释放完成，底层互斥资源才重新可用。**

## 2. 前置要求

### 2.1 知识要求

- 理解普通互斥量的所有权和优先级继承。
- 理解任务阻塞、抢占、就绪列表与 Tick 超时。
- 理解 C 语言调用栈、回调、统一清理出口。
- 理解“单个变量读写原子”与“复合操作线程安全”的区别。
- 理解 DMA 完成通知、设备事务边界和缓冲区生命周期。

### 2.2 技能要求

- 能阅读 `semphr.h`、`queue.c`、`tasks.c`。
- 能构造不同优先级任务的锁竞争实验。
- 能使用 DWT、硬件定时器或 Trace 工具测量锁等待时间。
- 能画出函数调用图和锁依赖图。
- 能为资源操作设计正常、超时和硬件异常三类退出路径。

## 3. 技术概述

### 3.1 核心定义

递归互斥量允许**同一个持有任务重复获取同一把互斥量**，每次获取增加递归计数，每次释放减少计数。

只有计数归零时，资源所有权才结束。

```
初始：owner = NULL，depth = 0

任务 A 首次获取：
    owner = A，depth = 1

任务 A 再次获取：
    owner = A，depth = 2

任务 A 释放一次：
    owner = A，depth = 1
    其他任务仍然不能获取

任务 A 再释放一次：
    owner = NULL，depth = 0
    其他任务才有机会获取
```

两个核心不变量：

```
depth > 0  => 存在唯一持有任务
depth = 0  => 没有持有任务
```

**递归计数表示所有者尚未配对释放的成功获取次数，不表示等待任务数量。**

### 3.2 “递归”不要求函数递归

常见需求来自分层 API：

```
设备复合操作 device_configure()
    获取设备锁
    |
    +-- device_write_register()
    |       再次获取同一设备锁
    |
    +-- device_read_register()
            再次获取同一设备锁
```

这些函数没有递归调用自己，但同一任务重复获取了同一把锁。

### 3.3 递归互斥量不等于函数可重入

递归互斥量允许同一任务再次进入受保护区域，因此：

- 可以防止其他任务并发访问；
- **不能阻止当前任务通过回调再次进入模块**；
- 不能自动保证模块处于可再次调用的状态。

例如模块已经加锁，但状态正处于：

```
已更新长度，尚未更新数据指针
```

此时调用回调，回调再次进入模块，仍可能读取不一致状态。

**排他访问、同任务重入安全、业务事务完整性，是三个不同问题。**

### 3.4 主流方案分类

|方案|实现思路|适用前提|
|---|---|---|
|原生递归互斥量|内核维护所有者和递归计数|RTOS 原生支持|
|普通互斥量 + 内部已持锁函数|只在公开边界加锁|能控制模块调用结构|
|外部事务接口|调用者持锁执行一组操作|需要显式组合事务|
|单任务资源代理|代理任务独占资源|适合异步、慢速设备|
|自行封装递归锁|自行维护所有者与计数|需要额外证明原子性及继承语义，通常不推荐|

## 4. 核心特性横向对比

|维度|普通互斥量|递归互斥量|二值信号量|资源代理任务|
|---|---|---|---|---|
|所有权|有|有|无|由代理集中拥有资源|
|同一任务重复获取|不支持|**支持**|不表达所有权||
|最终释放条件|一次合法释放|**所有成功获取均配对释放**|Give||
|FreeRTOS 优先级继承|支持，存在实现限制|支持，存在同类限制|不支持|不自动传播请求者优先级|
|ISR 使用|不允许|不允许|可使用对应 FromISR API|ISR 可提交受支持的通知|
|主要用途|排他访问|合法的嵌套排他访问|事件同步|统一设备事务|
|主要风险|死锁、长持锁|深度失配、隐蔽长持锁、重入状态错误|事件合并|队列延迟、请求生命周期|
|接口审计难度|中|较高|中|较高|

一个关键选型结论：

> **可控模块通常优先采用“普通互斥量 + 内部已持锁函数”；公共 API 确实需要组合调用时，再使用递归互斥量。**

## 5. 底层原理与功能特性深度解析

### 5.1 FreeRTOS 配置与创建

需要启用对应配置：

```
#define configUSE_MUTEXES                   1
#define configUSE_RECURSIVE_MUTEXES         1
#define configSUPPORT_STATIC_ALLOCATION    1
```

静态创建：

```
#include "FreeRTOS.h"
#include "semphr.h"

static StaticSemaphore_t s_device_lock_storage;
static SemaphoreHandle_t s_device_lock;

bool device_lock_init(void)
{
    s_device_lock = xSemaphoreCreateRecursiveMutexStatic(
        &s_device_lock_storage);

    return s_device_lock != NULL;
}
```

工程要求：

- 初始化必须在任务并发访问前完成；
- 静态控制块必须覆盖对象整个生命周期；
- 不得在仍被使用时重新创建到同一块存储；
- 动态创建失败时返回 `NULL`，必须处理。

动态创建的对应接口为：

```
SemaphoreHandle_t lock = xSemaphoreCreateRecursiveMutex();

if (lock == NULL)
{
    /* 向启动管理层返回失败，禁止继续开放设备接口。 */
    return false;
}
```

### 5.2 内部结构：底层令牌 + 所有者 + 递归计数

FreeRTOS 的互斥量复用队列基础设施。与递归相关的内部数据包含：

```
/* 示意结构，不能作为真实 FreeRTOS 内部类型使用。 */
typedef struct
{
    TaskHandle_t owner;
    UBaseType_t recursive_count;
} recursive_mutex_state_t;
```

常见源码字段包括：

```
u.xSemaphore.xMutexHolder
u.xSemaphore.uxRecursiveCallCount
```

递归获取次数增加时，**底层队列令牌不会每次都被再次取走**：

```
首次获取：消耗底层互斥令牌，建立所有权
重复获取：检查当前任务是否为所有者，增加递归计数
中间释放：只减少递归计数
最终释放：归还底层互斥令牌，结束所有权
```

### 5.3 获取路径

API 映射通常为：

```
xSemaphoreTakeRecursive()
    -> xQueueTakeMutexRecursive()
```

其核心控制逻辑可表示为：

```
/*
 * 以下为控制流示意，不是可直接替换的内核源码。
 * 省略了端口保护、Trace 和内部类型。
 */
BaseType_t recursive_take_model(
    mutex_model_t *mutex,
    TickType_t timeout)
{
    TaskHandle_t current = xTaskGetCurrentTaskHandle();

    if (mutex->owner == current)
    {
        mutex->recursive_count++;
        return pdPASS;
    }

    if (underlying_mutex_take(mutex, timeout) != pdPASS)
    {
        return pdFAIL;
    }

    /* 底层获取已建立所有权。 */
    mutex->recursive_count++;
    return pdPASS;
}
```

重要行为：

- **当前所有者重入时不阻塞**；
- 传入的等待时间仅对需要竞争底层互斥量的路径有意义；
- 同任务重入不需要再次触发优先级继承；
- 竞争失败时不能增加递归计数。

普通互斥量和递归互斥量应使用各自匹配的 API，不能依赖内部实现碰巧兼容。

### 5.4 释放路径

API 映射通常为：

```
xSemaphoreGiveRecursive()
    -> xQueueGiveMutexRecursive()
```

控制逻辑：

```
/* 控制流示意，不是生产实现。 */
BaseType_t recursive_give_model(mutex_model_t *mutex)
{
    if (mutex->owner != xTaskGetCurrentTaskHandle())
    {
        return pdFAIL;
    }

    mutex->recursive_count--;

    if (mutex->recursive_count == 0U)
    {
        return underlying_mutex_give(mutex);
    }

    return pdPASS;
}
```

**释放一次成功，不代表资源已经对其他任务开放。**

生产代码必须执行释放后再检查结果，不能把操作藏在断言参数中：

```
static bool device_unlock(void)
{
    BaseType_t result = xSemaphoreGiveRecursive(s_device_lock);

    configASSERT(result == pdPASS);

    return result == pdPASS;
}
```

错误写法：

```
/* 如果断言宏不求值，释放操作可能完全消失。 */
configASSERT(xSemaphoreGiveRecursive(s_device_lock) == pdPASS);
```

### 5.5 与优先级继承的关系

设：

```
L：基础优先级 2，持锁深度 3
M：优先级 5，就绪
H：优先级 8，阻塞等待该锁
```

调度过程：

```
H 阻塞等待
    -> L 继承优先级 8
    -> L 继续执行
    -> Give：depth 3 -> 2，锁仍归 L
    -> Give：depth 2 -> 1，锁仍归 L
    -> Give：depth 1 -> 0，底层释放
    -> H 被解除该锁的等待
```

要区分：

|指标|含义|
|---|---|
|递归深度|同一把锁尚未配对释放的获取次数|
|`uxMutexesHeld`|任务持有的不同互斥量数量|

**同一递归互斥量获取三次，通常只使 `uxMutexesHeld` 增加一次。**

FreeRTOS 常见实现采用简化的优先级继承：

- 持有多个互斥量时，正常释放其中一个锁，不一定立即降到精确所需优先级；
- 常见正常释放路径会等到持有互斥量数量归零后恢复基础优先级；
- 等待超时后的降优先级处理存在版本和条件限制；
- **不能假设任意多锁等待链都会得到完整、持续的传递式优先级继承。**

### 5.6 超时只限制等待，不限制持有

```
xSemaphoreTakeRecursive(lock, pdMS_TO_TICKS(10));
```

表示：

> 本次获取最多按指定 Tick 等待锁变得可用。

它不表示：

```
10 ms 后锁会自动释放
10 ms 后内核撤销所有权
持锁操作必须在 10 ms 内完成
```

超时到达只影响等待者。持有者可以继续持锁，因此必须独立监控最大持锁时间。

### 5.7 递归计数溢出

递归计数使用有限宽度无符号类型。不能把它理解成无限深度。

工程防护首先依赖调用图：

```
公开事务接口：深度 1
    -> 公开寄存器接口：深度 2
        -> 硬件访问：不再加锁
```

对该设计可以给出：

```
最大合法递归深度 Dmax = 2
```

诊断封装可额外记录深度，但该计数必须在合法所有权保护下维护，且所有访问路径都必须经过封装。不能在加锁前无保护地检查共享 `depth`。

## 6. 性能量化分析

### 6.1 测试平台与证据边界

建议固定以下基准平台：

|项目|配置|
|---|---|
|MCU|STM32F407，Cortex-M4F|
|CPU 时钟|168 MHz|
|内核|固定 FreeRTOS tag，并记录提交号|
|编译器|固定 GCC 版本，`-O2`|
|调度|单核、抢占式|
|Tick|1 kHz|
|测量|DWT CYCCNT + 调度 Trace|

**本课没有在该平台执行测量，因此不提供未经验证的 API 周期“实测值”。** 下列换算和预算可直接复算，具体周期需按第 16 节的方法获得。

### 6.2 内存开销

静态对象占用直接读取：

```
size_t lock_storage_bytes = sizeof(StaticSemaphore_t);
```

在 FreeRTOS 中：

- 普通互斥量和递归互斥量通常复用相同控制块类型；
- **递归深度增加不会为每一层创建一个内核对象**；
- 最大深度为 2 和最大深度为 20，内核锁对象大小通常相同；
- 若嵌套来自更深的函数调用，任务栈占用仍然增加。

例如，假设 map 文件确认：

```
sizeof(StaticSemaphore_t) = 80 字节
锁数量 = 12
```

则静态锁控制块总量：

```
RAMlocks = 12 × 80 = 960 字节
```

这里 **80 字节只是计算示例，不能替代目标工程的 `sizeof` 结果**。

### 6.3 时间开销模型

设一次完整操作的最大递归深度为 `d`：

```
Toperation =
    Tfirst_take
  + (d - 1) × Treenter
  + Tbusiness
  + (d - 1) × Tpartial_give
  + Tfinal_give
```

同任务重入路径通常短于首次竞争获取路径，但实际差值受 Trace、断言和编译优化影响。

在 168 MHz 下：

|周期数|时间|
|---|---|
|168 cycles|1 μs|
|840 cycles|5 μs|
|1680 cycles|10 μs|

公式：

```
Tμs = cycles × 10^6 / fCPU
```

### 6.4 最坏持锁时间取决于最外层

示例预算：

```
最外层开始持锁
    参数与状态更新：10 μs
    寄存器写入：30 μs
    内层计算：80 μs
    寄存器读取：30 μs
最终释放
```

即使单个寄存器 API 只需 30 μs：

```
总持锁时间至少为 10 + 30 + 80 + 30 = 150 μs
```

外部任务等待的是**最外层剩余事务时间**，而不是当前内层 API 的执行时间。

### 6.5 优先级继承收益示例

假设 H 等待时：

```
L 剩余持锁执行时间：120 μs
M 可造成的额外抢占：600 μs
```

忽略其他干扰：

```
无继承：H 等待约 720 μs + 调度开销
有继承：H 等待约 120 μs + 调度开销
```

这是调度模型推导，不是上板测量结果。

若 L 正在等待 2 ms 的硬件完成，继承优先级无法消除硬件等待。

### 6.6 瓶颈与优化收益

|优化|可量化收益|限制|
|---|---|---|
|将 80 μs 的独立计算移到锁外|示例持锁时间从 150 μs 降到约 70 μs|需保证数据快照有效|
|消除一层重复加锁|减少一次重入和一次中间释放成本|需要调整接口|
|将轮询换为 DMA|降低 CPU 占用|若事务仍独占设备，持锁墙钟时间未必缩短|
|拆分长事务|降低单次阻塞上界|不得破坏设备协议原子性|
|使用状态快照|缩短共享数据锁持有时间|存在复制成本和陈旧数据问题|

## 7. 应用场景选型指南

### 7.1 决策流程图

```
需要保护共享资源？
|
+-- 否
|   +-- 使用任务通知、信号量、队列或事件组
|
+-- 是
    |
    +-- 访问发生在 ISR？
    |   +-- 是：重新设计为 ISR 通知任务，或使用适用的短临界保护
    |
    +-- 同一任务会重复进入同一锁域？
        |
        +-- 否：普通互斥量
        |
        +-- 是
            |
            +-- 能明确拆分 public 与 private_locked 接口？
            |   +-- 能：优先普通互斥量 + 内部已持锁函数
            |
            +-- 公共 API 必须支持组合事务？
                |
                +-- 是：递归互斥量
                |       同时证明深度、状态一致性和持锁上界
                |
                +-- 资源操作长期阻塞？
                    +-- 评估资源代理、异步状态机或缓存
```

### 7.2 场景选型

|需求|方案|原因|
|---|---|---|
|复合配置需要调用多个独立线程安全 API|递归互斥量|支持外层事务和内层 API 共享锁|
|模块内部调用结构完全可控|普通锁 + `_locked` 函数|锁边界更明确|
|DMA ISR 通知完成|任务通知或信号量|ISR 不拥有互斥量|
|文件系统公共接口确有嵌套|原生支持的递归保护|必须审查回调及其他锁|
|锁内调用用户回调|优先改为锁外回调|递归锁不能保证状态可重入|
|多个慢速设备请求串行处理|资源代理|便于集中管理事务和恢复|
|两把锁反向获取|统一锁顺序|改为递归锁不能解决|

## 8. 工程最佳实践

### 8.1 五条设计原则

1. **锁域必须对应一个明确的不变量集合。**  
    例如“设备寄存器影子值与设备模式一致”，而不只是“这些函数都属于同一个文件”。
    
2. **先决定事务边界，再决定是否递归。**  
    外层锁住两个 API，意味着其他任务不能观察两个 API 之间的中间状态。
    
3. **成功获取一次，必须恰好释放一次。**  
    获取失败不得释放；异常出口不得漏释放。
    
4. **回调默认放到锁外。**  
    若必须锁内回调，应定义允许调用的接口、最大执行时间和禁止获取的锁。
    
5. **持锁等待可以存在，但必须有界且无等待环。**  
    SPI DMA 期间保持总线所有权可能是必要的；不能为了“缩短持锁”提前释放仍在使用的硬件资源。
    

### 8.2 选型决策矩阵

|条件|普通锁 + `_locked`|递归锁|资源代理|
|---|---|---|---|
|内部调用关系可控|**优先**|可用|通常不必要|
|外部需要组合多个公共 API|需提供事务接口|**适合**|可用|
|同步操作较短|适合|适合|通信成本可能偏高|
|慢速、复杂恢复事务|可用|谨慎|**适合**|
|要求锁依赖容易审计|**较好**|需要额外审计|需审计消息等待关系|
|ISR 直接操作资源|不适合|不适合|ISR 提交事件|

### 8.3 编码规范

- 命名体现类型：`device_recursive_mutex`。
- 普通和递归 API 禁止混用。
- `_locked` 后缀表示**调用者已持锁**，不能理解为“函数内部会加锁”。
- 初始化和删除由生命周期管理层负责。
- 不依赖 `configASSERT()` 执行业务副作用。
- 不能通过 `vTaskDelete()` 自动回收任务持有的锁；FreeRTOS 没有通用的健壮互斥量所有者死亡恢复机制。
- 删除锁前必须停止新访问，并确认没有持有者和等待者。

## 9. 常见错误与避坑指南

### 9.1 错误一：递归获取与普通释放混用

错误代码：

```
xSemaphoreTakeRecursive(lock, timeout);
xSemaphoreGive(lock);
```

**根因：** 绕过递归计数管理，违反对象使用约定。

正确实现：

```
if (xSemaphoreTakeRecursive(lock, timeout) != pdPASS)
{
    return false;
}

bool ok = operation();

BaseType_t released = xSemaphoreGiveRecursive(lock);

configASSERT(released == pdPASS);
return ok && released == pdPASS;
```

**风险：** 提前开放资源、递归计数失配、所有权错误或断言失败。

### 9.2 错误二：某个错误路径漏释放

错误代码：

```
if (xSemaphoreTakeRecursive(lock, timeout) != pdPASS)
{
    return false;
}

if (!validate_device())
{
    return false; /* 漏释放 */
}

xSemaphoreGiveRecursive(lock);
```

**根因：** 错误出口绕过配对清理；嵌套情况下只会残留一层，更难发现。

正确实现：

```
bool execute_checked(TickType_t timeout)
{
    bool ok = false;

    if (xSemaphoreTakeRecursive(lock, timeout) != pdPASS)
    {
        return false;
    }

    if (!validate_device())
    {
        goto unlock;
    }

    ok = operation();

unlock:
    {
        BaseType_t released = xSemaphoreGiveRecursive(lock);
        configASSERT(released == pdPASS);
        return ok && released == pdPASS;
    }
}
```

**风险：** 当前任务看似还能继续重入，其他任务却长期无法获取。

### 9.3 错误三：把递归锁当作跨任务共享持锁权限

错误代码：

```
/* 任务 A */
xSemaphoreTakeRecursive(lock, timeout);
submit_work_to_task_b();

/* 任务 B */
xSemaphoreGiveRecursive(lock);
```

**根因：** 递归权限只属于同一个任务，不能随请求传给另一个任务。

正确实现：

```
/* 任务 B 独立拥有完整事务。 */
if (xSemaphoreTakeRecursive(lock, timeout) == pdPASS)
{
    execute_submitted_work();

    BaseType_t released = xSemaphoreGiveRecursive(lock);
    configASSERT(released == pdPASS);
}
```

任务 A 不应持锁等待需要 B 获取同一把锁才能完成的工作。

**风险：** 释放失败或形成任务间等待环。

### 9.4 错误四：认为递归锁能解决多锁死锁

错误代码：

```
/* 任务 A */
take_recursive(lock_a);
take_recursive(lock_b);

/* 任务 B */
take_recursive(lock_b);
take_recursive(lock_a);
```

**根因：** 递归只允许同任务重入同锁，不消除不同锁之间的循环依赖。

正确实现：

```
/* 所有任务统一 A -> B。 */
if (xSemaphoreTakeRecursive(lock_a, timeout) != pdPASS)
{
    return false;
}

if (xSemaphoreTakeRecursive(lock_b, timeout) != pdPASS)
{
    BaseType_t released = xSemaphoreGiveRecursive(lock_a);
    configASSERT(released == pdPASS);
    return false;
}

/* 访问资源；随后按 B -> A 释放。 */
```

**风险：** 永久死锁、级联超时。两个获取若共享端到端期限，还必须传递**剩余预算**，不能各自重新使用完整超时。

### 9.5 错误五：锁内回调观察到半更新状态

错误代码：

```
take_recursive(lock);

state.length = new_length;
user_callback(); /* 回调可再次进入，读取旧指针和新长度 */
state.data = new_data;

give_recursive(lock);
```

**根因：** 同任务不会被递归锁挡住。

正确设计：

```
take_recursive(lock);

/* 完成全部状态更新，并生成可独立使用的事件快照。 */
state.data = new_data;
state.length = new_length;
event_snapshot_t event = make_snapshot();

give_recursive(lock);

user_callback(&event);
```

快照中的指针还必须具有足够生命周期；浅复制不等于数据独立。

**风险：** 越界访问、状态机重入、资源重复释放。

### 9.6 错误六：获取失败仍访问和释放

错误代码：

```
xSemaphoreTakeRecursive(lock, timeout);
modify_device();
xSemaphoreGiveRecursive(lock);
```

**根因：** 忽略竞争超时，继续执行无所有权访问。

正确实现必须在 `pdPASS` 后才能进入受保护区域。

**风险：** 数据竞争、硬件事务交错、非法释放。

## 10. 多机制组合使用方案

### 10.1 技术协同架构

下面的框架用于表达：

```
递归互斥量：
    保护整个设备配置事务

公共寄存器接口：
    可独立调用，也可被复合配置接口调用

硬件访问层：
    提供有界的同步读写

错误状态：
    配置中途失败则标记设备需要重新初始化
```

若硬件使用 DMA，可在底层增加完成通知：

```
调用任务持有递归互斥量
    -> 启动 DMA
    -> 有界等待完成通知
ISR
    -> 清状态并发送通知
调用任务
    -> 确认完成，或终止并确认硬件静止
    -> 最终释放锁
```

**清空旧通知不足以防止超时后的迟到中断。** 开始新事务前还应确认旧 DMA 已停止、相关挂起状态已清除；必要时使用事务编号和驱动状态机。

### 10.2 完整同步框架

以下模块代码使用静态对象、递归 API 和统一清理出口。硬件适配层需要实现声明的有界接口。

```
#include <stdbool.h>
#include <stdint.h>
#include "FreeRTOS.h"
#include "semphr.h"
#include "task.h"

typedef enum
{
    DEV_OK = 0,
    DEV_BAD_ARG,
    DEV_NOT_READY,
    DEV_LOCK_TIMEOUT,
    DEV_IO_ERROR,
    DEV_LOCK_ERROR
} dev_status_t;

typedef struct
{
    StaticSemaphore_t lock_storage;
    SemaphoreHandle_t lock;
    bool needs_reinit; /* 所有运行期访问均在设备锁内 */
} device_t;

/*
 * 平台契约：
 * 1. 只在任务上下文调用。
 * 2. 每次调用有明确的最坏完成/终止时间。
 * 3. 返回时不再访问调用者缓冲区。
 * 4. 不回调设备公共 API。
 */
extern bool board_reg_write(uint8_t reg, uint8_t value);
extern bool board_reg_read(uint8_t reg, uint8_t *value);

static device_t s_device;

bool device_init(void)
{
    /* 仅在系统启动、并发访问尚未开放时调用一次。 */
    s_device.needs_reinit = false;
    s_device.lock = xSemaphoreCreateRecursiveMutexStatic(
        &s_device.lock_storage);

    return s_device.lock != NULL;
}

static dev_status_t device_enter(TickType_t wait_ticks)
{
    if (s_device.lock == NULL)
    {
        return DEV_NOT_READY;
    }

    if (xSemaphoreTakeRecursive(
            s_device.lock, wait_ticks) != pdPASS)
    {
        return DEV_LOCK_TIMEOUT;
    }

    return DEV_OK;
}

static dev_status_t device_leave(dev_status_t status)
{
    BaseType_t released =
        xSemaphoreGiveRecursive(s_device.lock);

    configASSERT(released == pdPASS);

    return released == pdPASS ? status : DEV_LOCK_ERROR;
}

dev_status_t device_write(
    uint8_t reg,
    uint8_t value,
    TickType_t wait_ticks)
{
    dev_status_t status = device_enter(wait_ticks);

    if (status != DEV_OK)
    {
        return status;
    }

    if (s_device.needs_reinit)
    {
        status = DEV_NOT_READY;
    }
    else if (!board_reg_write(reg, value))
    {
        s_device.needs_reinit = true;
        status = DEV_IO_ERROR;
    }

    return device_leave(status);
}

dev_status_t device_read(
    uint8_t reg,
    uint8_t *value,
    TickType_t wait_ticks)
{
    if (value == NULL)
    {
        return DEV_BAD_ARG;
    }

    dev_status_t status = device_enter(wait_ticks);

    if (status != DEV_OK)
    {
        return status;
    }

    if (s_device.needs_reinit)
    {
        status = DEV_NOT_READY;
    }
    else if (!board_reg_read(reg, value))
    {
        s_device.needs_reinit = true;
        status = DEV_IO_ERROR;
    }

    return device_leave(status);
}

dev_status_t device_configure(
    uint8_t mode,
    uint8_t rate,
    TickType_t lock_wait_ticks)
{
    enum
    {
        REG_MODE = 1,
        REG_RATE = 2
    };

    uint8_t readback = 0U;
    dev_status_t status = device_enter(lock_wait_ticks);

    if (status != DEV_OK)
    {
        return status;
    }

    /*
     * 外层已持锁，内层公共 API 同任务重入。
     * 传 0 不会失去所有权，也不会引入新的竞争等待。
     */
    status = device_write(REG_MODE, mode, 0U);
    if (status != DEV_OK)
    {
        goto out;
    }

    status = device_write(REG_RATE, rate, 0U);
    if (status != DEV_OK)
    {
        goto out;
    }

    status = device_read(REG_RATE, &readback, 0U);
    if (status != DEV_OK)
    {
        goto out;
    }

    if (readback != rate)
    {
        s_device.needs_reinit = true;
        status = DEV_IO_ERROR;
    }

out:
    return device_leave(status);
}
```

这个框架具备以下明确边界：

- 最大递归深度为 **2**；
- 其他任务不能插入复合配置中间；
- `lock_wait_ticks` 只控制外层获取等待；
- 配置失败可能已修改部分硬件，因此标记需要重新初始化；
- 互斥量提供并发原子性，**不提供硬件配置的自动回滚**；
- 设备恢复必须另行实现，并在相同所有权规则下执行。

## 11. 工业级实际案例分析

以下为真实工业设备中常见的场景建模，不代表已在某个具体客户项目中验证的案例。

### 11.1 场景一：工业传感器复合配置

**需求：**

- 多任务共享一颗传感器；
- 对外提供单寄存器读写接口；
- 切换量程必须连续写多个寄存器并校验；
- 其他任务不能在中途读取半配置状态。

**架构：**

```
device_configure()
    外层递归锁
    -> device_write()
    -> device_write()
    -> device_read()
    最终释放
```

核心代码即第 10 节框架。

**设计要点：**

- 最大递归深度为 2；
- 将传感器稳定等待时间计入持锁预算；
- 若转换等待很长，使用“配置中”状态机，定义哪些访问必须拒绝；
- 中途失败不能只解锁后声称设备正常，应标记降级或执行重初始化。

### 11.2 场景二：设备事务锁与共享总线锁分离

**需求：**

- 多颗器件共享 SPI；
- 某器件的配置事务包含“写入—等待—校验”；
- 等待期间其他器件允许使用总线。

**架构：**

```
设备事务锁：保护同一器件完整配置
    |
    +-- 获取总线锁，发送写命令，释放总线锁
    +-- 有界等待器件内部完成
    +-- 获取总线锁，读取校验，释放总线锁
```

核心代码模式：

```
/* 调用者已持有设备事务锁。 */
static bool write_command_locked(void)
{
    if (xSemaphoreTake(bus_mutex, bus_wait) != pdPASS)
    {
        return false;
    }

    bool ok = board_send_command();

    BaseType_t released = xSemaphoreGive(bus_mutex);
    configASSERT(released == pdPASS);

    return ok && released == pdPASS;
}
```

**设计要点：**

- 全局锁顺序固定为：**设备事务锁 → 总线锁**；
- 同一设备的其他任务仍被挡住；
- 其他设备可以在等待窗口使用 SPI；
- 若协议要求片选持续有效或总线必须独占，则不能提前释放总线锁；
- 两把锁会引入更复杂的阻塞链，必须验证 FreeRTOS 简化继承的实际影响。

### 11.3 场景三：图形库组合绘制

**需求：**

- 多任务更新 UI；
- 绘制窗口内部调用绘制文字、图标等公共接口；
- 一个完整 UI 更新不能被其他任务插入。

**架构：**

```
ui_draw_panel()
    递归获取 framebuffer 锁
    -> ui_draw_text()
    -> ui_draw_icon()
    最终释放
```

核心代码：

```
bool ui_draw_panel(TickType_t timeout)
{
    if (xSemaphoreTakeRecursive(ui_mutex, timeout) != pdPASS)
    {
        return false;
    }

    bool ok = ui_draw_text("RUN", 0U);

    if (ok)
    {
        ok = ui_draw_icon(ICON_RUNNING, 0U);
    }

    BaseType_t released = xSemaphoreGiveRecursive(ui_mutex);
    configASSERT(released == pdPASS);

    return ok && released == pdPASS;
}
```

**设计要点：**

- 锁内只修改图形状态或 framebuffer；
- 不在锁内同步等待整屏慢速刷新；
- DMA 正在读取的缓冲区不能继续被修改，需双缓冲或明确所有权转移；
- 字体加载、文件读取尽量在锁外预处理；
- 事件回调在状态一致且锁已释放后调用。

## 12. 高频问题深度答疑

### 12.1 递归互斥量是否比普通互斥量更安全？

不构成普遍结论。

它避免同一任务重复获取普通锁造成的自锁，但也会：

- 隐藏原本应暴露的锁边界问题；
- 允许回调重入中间状态；
- 增加释放次数失配风险；
- 使外层持锁范围更难发现。

安全性来自明确的调用约束和资源不变量。

### 12.2 同一任务重入时传入 0，会获取失败吗？

对于已由当前任务持有、状态有效的递归互斥量，常见 FreeRTOS 实现直接增加递归计数并成功返回，不进入等待路径。

但这依赖**当前调用任务确实是所有者**，不能把 `0` 当作绕过所有权的方式。

### 12.3 递归深度为 5，需要五份互斥量内存吗？

不需要。深度通常保存在控制块的整数计数器中。

但更深调用链需要更多任务栈；若是真正的函数递归，还应证明栈深度上界。

### 12.4 内层释放后，高优先级任务为什么还不能执行？

高优先级任务仍等待锁变为可用。内层释放只把深度从 2 减到 1，外层事务仍拥有资源。

因此诊断不能只统计 Give 成功次数，还要定位**首次获取到最终释放**之间的完整时间窗口。

### 12.5 持锁任务被删除，其他任务能接管吗？

不能依赖这种行为。

FreeRTOS 不提供通用的所有者死亡后自动修复机制。即使强行释放锁，受保护资源也可能处于半更新状态。

正确恢复流程通常是：

```
停止新请求
确认原执行上下文已停止
终止或复位相关硬件
重建资源状态
在无访问者条件下重建同步对象
重新开放服务
```

### 12.6 资源代理能完全消除优先级反转吗？

不能。

如果代理任务优先级低，可能被中优先级任务抢占；如果请求队列 FIFO，紧急请求可能排在长事务后面。

代理架构仍需设计：

- 代理任务优先级；
- 请求优先级或分级队列；
- 最大单事务长度；
- 请求取消与超时；
- 已开始事务是否可抢占。

它提供集中管理能力，不自动提供请求者到代理的优先级继承。

## 13. 课程核心总结

### 13.1 核心要点

1. **递归互斥量允许同一任务重复获取同一把锁。**
2. 成功获取 N 次，必须由同一任务配对释放 N 次。
3. 只有最终释放才结束资源所有权。
4. 递归深度不等于任务持有的不同互斥量数量。
5. 优先级继承沿用底层互斥机制，不能假设完整处理所有复杂锁链。
6. 获取超时不限制持锁时间。
7. 递归锁不能解决多锁死锁，也不能保证回调重入安全。
8. 互斥保护不提供硬件事务回滚。
9. 可控调用结构优先考虑普通锁与 `_locked` 内部函数。
10. 工程验收必须覆盖深度、配对、持锁上界和错误恢复。

### 13.2 性能关系

对常见 FreeRTOS 实现：

```
同任务重入 / 中间释放：
    通常比涉及阻塞和切换的竞争路径短

竞争阻塞 / 最终释放并唤醒：
    包含等待列表、继承、调度等额外工作
```

**普通互斥量与递归互斥量不能给出跨平台固定性能排序。** 应比较相同业务调用图、相同竞争条件和相同仪表配置下的结果。

### 13.3 通用选型结论

```
没有合法嵌套需求：
    普通互斥量

模块内部可控：
    普通互斥量 + private_locked 函数

公共 API 必须组合为排他事务：
    递归互斥量

慢速设备需要异步管理：
    资源代理或状态机

ISR 与任务同步：
    任务通知 / 信号量 / 队列

不同锁之间存在循环依赖：
    修复锁顺序和架构
```

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐|必查项|
|---|---|---|
|外层事务调用多个线程安全公共 API|递归互斥量|深度和最外层持锁时间|
|内部函数重复加锁|普通锁 + `_locked`|所有入口是否正确加锁|
|锁内用户回调|优先改为锁外|快照生命周期|
|设备等待期间允许其他设备用总线|事务锁与总线锁分离|协议允许性、锁顺序|
|DMA 完成|通知或信号量|迟到中断、终止确认|
|高实时任务等待长事务|缓存、异步、代理|截止期和排队策略|
|持锁任务死亡|模块级恢复|状态重建，不能仅解锁|

### 14.2 特性与 API 对照表

|项目|递归互斥量|
|---|---|
|动态创建|`xSemaphoreCreateRecursiveMutex()`|
|静态创建|`xSemaphoreCreateRecursiveMutexStatic()`|
|获取|`xSemaphoreTakeRecursive()`|
|释放|`xSemaphoreGiveRecursive()`|
|所有者查询|`xSemaphoreGetMutexHolder()`，仅用于诊断快照|
|删除|`vSemaphoreDelete()`，必须先满足生命周期条件|
|初始状态|可获取、无所有者|
|ISR 获取 / 释放|不允许|
|同任务重入|支持|
|其他任务获取|等待最终释放|
|获取超时|不撤销所有者、不自动释放|
|递归深度查询|无通用公开 API，应通过受控封装或 Trace 观测|
|优先级继承|支持，受版本和简化实现限制|

所有者查询存在并发变化，**不能采用“先查 owner，再决定无锁访问”的方式替代获取操作**。

## 15. 学习效果自检

- [ ]  能解释 depth 为 3 时释放两次为什么仍不开放资源。
- [ ]  能区分递归锁、函数递归和重入安全。
- [ ]  能解释 `uxMutexesHeld` 为什么不等于递归深度。
- [ ]  能正确匹配递归 Take/Give API。
- [ ]  能保证所有成功获取在错误路径上配对释放。
- [ ]  能避免在断言参数中执行释放。
- [ ]  能说明获取超时与持锁期限的区别。
- [ ]  能计算最外层事务的持锁上界。
- [ ]  能识别锁内回调引起的同任务状态重入问题。
- [ ]  能说明 FreeRTOS 多锁优先级恢复的限制。
- [ ]  能设计 DMA 超时后的硬件静止确认。
- [ ]  能通过调用图证明最大递归深度。
- [ ]  能建立不同锁之间的无环获取顺序。
- [ ]  能判断何时应改用普通锁与 `_locked` 接口。

## 16. 实践与进阶路径

### 16.1 梯度实战任务

|阶段|任务|验收标准|
|---|---|---|
|1|同一任务连续获取三次、分三次释放|另一任务只能在最终释放后成功获取|
|2|复合配置调用两个公共寄存器 API|深度上界为 2，事务中间无其他任务插入|
|3|注入每个硬件访问失败点|所有退出路径释放配对，设备状态可诊断|
|4|构造 L/M/H 优先级反转|Trace 显示继承，比较 H 等待时间|
|5|注入锁内回调重入|发现半更新状态并通过快照或锁外回调修复|
|6|替换为普通锁 + `_locked` 接口|比较 API 成本、调用清晰度和持锁时间|
|7|引入设备锁与总线锁|验证锁顺序、阻塞链和其他设备吞吐量|

优先级反转实验中，L 应在锁内执行**有界 CPU 工作**，而不是用 `vTaskDelay()` 模拟 CPU 计算。后者会让 L 自身阻塞，不能清晰展示中优先级抢占被继承机制抑制的效果。

### 16.2 性能测试方法

分别测量以下路径：

```
首次无竞争获取
同任务重入
中间释放
最终释放，无等待者
最终释放，有高优先级等待者
竞争等待及优先级继承
```

DWT 测量核心代码：

```
/* 前置：DWT CYCCNT 已由平台初始化，且目标支持周期计数。 */
uint32_t start = DWT->CYCCNT;

BaseType_t result =
    xSemaphoreTakeRecursive(lock, 0U);

uint32_t elapsed = DWT->CYCCNT - start;

if (result != pdPASS)
{
    return false;
}

/* 将 elapsed 写入预分配样本缓冲区，测量路径中不打印。 */

BaseType_t released = xSemaphoreGiveRecursive(lock);
configASSERT(released == pdPASS);

return released == pdPASS;
```

实验要求：

- 重入测试前，由同一任务先持有一次；
- 中间释放测试前，确保递归深度至少为 2；
- 测量计数器读取本身的基线开销；
- 周期计数使用无符号减法，并限制区间小于一次计数器回绕；
- 在 168 MHz 下，32 位周期计数器约 **25.57 s** 回绕；
- 若释放导致当前任务被抢占，函数返回后的时间差可能包含其他任务运行时间，不能当作纯 Give 指令成本；
- 超时测试区分 Tick 量化和任务重新获得 CPU 的延迟；
- 记录内核版本、编译选项、Trace 配置、时钟和负载。

建议至少保存：

```
样本数
最小值
平均值
P99 / P99.9
最大观测值
获取超时次数
首次获取到最终释放的最大墙钟时间
```

**最大观测值不是经过证明的 WCET。** 硬实时系统还需要结合调用图、硬件时限和干扰分析建立上界。

### 16.3 进阶学习方向

1. 阅读 `queue.c`：
    
    - `xQueueTakeMutexRecursive()`；
    - `xQueueGiveMutexRecursive()`；
    - `xQueueSemaphoreTake()`；
    - 互斥量归还与等待任务唤醒路径。
2. 阅读 `tasks.c`：
    
    - `xTaskPriorityInherit()`；
    - `xTaskPriorityDisinherit()`；
    - `vTaskPriorityDisinheritAfterTimeout()`；
    - 就绪列表和事件列表的优先级更新。
3. 对比不同资源协议：
    
    - 基本优先级继承；
    - 原始优先级上限协议；
    - 即时优先级上限协议；
    - 各自的获取条件、阻塞上界和适用假设。
4. 建立模块级验证：
    
    - 锁依赖图；
    - 最大递归深度；
    - 首次获取至最终释放的时间预算；
    - 硬件超时后的状态恢复；
    - 同任务回调重入测试；
    - 多任务竞争与长期运行故障注入。