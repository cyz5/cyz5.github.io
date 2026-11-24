
本课以 **FreeRTOS 软件定时器**为主线，重点讲解：定时器由谁调度、定时器命令为何是异步的、回调为什么不能阻塞，以及软件定时器在实时性方面的边界。

> **软件定时器适合低成本的超时、周期性维护和延迟通知，不适合代替硬件定时器生成高精度波形，也不适合在回调中执行长时间工作。**

## 1. 学习目标

|层级|能力产出|
|---|---|
|**理解**|理解一次性与自动重载定时器；理解定时器服务任务、命令队列和回调之间的关系|
|**掌握**|正确创建、启动、停止、复位和删除定时器；处理命令队列满、超时和 ISR 调用|
|**精通**|分析回调延迟、队列积压、Tick 量化和定时器服务任务优先级对实时性的影响|
|**能够设计**|设计有界、可观测、可恢复的超时和周期任务架构，并明确软件定时器与硬件定时器的职责边界|

## 2. 前置要求

### 知识要求

- 理解 RTOS 任务调度、阻塞、优先级和 Tick。
- 熟悉任务通知、队列、信号量和 ISR 上下文 API。
- 理解超时与截止时间不是同一概念。
- 理解任务上下文回调和 ISR 回调的区别。

### 技能要求

- 能阅读 `timers.c`、`timers.h` 和 `tasks.c`。
- 能检查 `FreeRTOSConfig.h` 中的定时器配置。
- 能使用 DWT、GPIO 或 Trace 工具测量回调延迟。
- 能排查命令队列满、定时器回调阻塞和周期抖动问题。

## 3. 技术概述

### 3.1 软件定时器定义

软件定时器是由 RTOS 内核维护到期时间，并在到期后通知或调用应用代码的对象。

FreeRTOS 软件定时器通常由以下部分组成：

```
定时器对象
  ├── 周期和自动重载属性
  ├── 定时器 ID
  └── 回调函数

定时器服务任务（Timer daemon task）
  ├── 接收定时器命令
  ├── 维护活动定时器列表
  ├── 处理到期定时器
  └── 执行回调

定时器命令队列
  ├── Start
  ├── Stop
  ├── Reset
  ├── ChangePeriod
  └── PendFunctionCall
```

### 3.2 定时器类型

|类型|行为|典型用途|
|---|---|---|
|一次性定时器|到期一次后停止|超时、延迟动作、重试截止|
|自动重载定时器|到期后周期性重新装载|低频状态轮询、维护任务|
|硬件定时器|由硬件计数器和比较寄存器触发|PWM、精确采样、高速捕获|
|周期任务|任务按周期运行，例如 `vTaskDelayUntil()`|有明确计算流程的周期控制任务|

### 3.3 FreeRTOS 定时器配置

常用配置项：

```
#define configUSE_TIMERS                 1
#define configTIMER_TASK_PRIORITY        3
#define configTIMER_QUEUE_LENGTH         16
#define configTIMER_TASK_STACK_DEPTH     256
```

具体配置含义：

- `configUSE_TIMERS`：启用软件定时器。
- `configTIMER_TASK_PRIORITY`：定时器服务任务优先级。
- `configTIMER_QUEUE_LENGTH`：定时器命令队列长度。
- `configTIMER_TASK_STACK_DEPTH`：定时器服务任务栈深度，通常以 `StackType_t` 单位计，而不是字节。

配置名称和细节应以项目使用的 FreeRTOS 版本为准。

### 3.4 软件定时器不是独立执行上下文

多个软件定时器通常由**同一个定时器服务任务**管理，所有回调都在该任务上下文中执行：

```
Timer A 到期 -> 回调 A
Timer B 到期 -> 回调 B
Timer C 到期 -> 回调 C
```

一个回调长时间运行，会延迟同一服务任务处理其他定时器和命令。

## 4. 核心特性横向对比

|方案|触发来源|时间精度|回调/执行上下文|适合用途|主要限制|
|---|---|---|---|---|---|
|FreeRTOS 软件定时器|RTOS Tick|Tick 级|定时器服务任务|超时、低频周期维护|回调共享同一服务任务|
|`vTaskDelayUntil()` 周期任务|RTOS Tick|Tick 级|独立任务|周期性计算和控制逻辑|占用任务栈和任务对象|
|硬件比较定时器|硬件计数器|通常高于 Tick|ISR 或 DMA|精确波形、采样、捕获|MCU 资源有限|
|定时器回调中通知任务|软件定时器到期|Tick 级加调度延迟|回调后由任务处理|将回调保持短小|增加一次任务调度|
|一个共享高精度定时器服务|自定义时间轮/堆|取决于实现|通常任务|大量定时任务或特定需求|实现、验证成本高|

### 4.1 软件定时器与周期任务

|维度|软件定时器|`vTaskDelayUntil()` 任务|
|---|---|---|
|是否有独立任务栈|所有定时器共享服务任务栈|每个周期任务有独立栈|
|回调是否可阻塞|不应阻塞|任务可按设计阻塞|
|到期时并发执行|回调串行|不同任务可独立调度|
|适合短小动作|是|可以，但资源开销较高|
|适合长处理|否|通常更合适|
|到期抖动|受 daemon 调度和其他回调影响|受任务调度、优先级和执行时间影响|

## 5. 底层原理与功能特性深度解析

### 5.1 FreeRTOS 软件定时器的执行链

典型控制流程：

```
应用调用 xTimerStart()
    -> 命令进入 timer command queue
    -> Timer daemon task 取出命令
    -> 将定时器插入活动列表
    -> Tick 到达定时器到期时间
    -> Timer daemon task 处理到期定时器
    -> 执行回调函数
```

内核源码通常包含类似职责的函数和对象：

- `xTimerGenericCommand()`：向定时器命令队列提交命令。
- 定时器服务任务入口：处理命令和到期定时器。
- 当前定时器列表与 Tick 溢出定时器列表：管理不同 Tick 区间的到期时间。
- 到期处理函数：取出定时器并调用回调。

确切函数名和路径可能随 FreeRTOS 版本变化，应阅读项目实际内核源码。

### 5.2 定时器命令是异步的

调用：

```
BaseType_t result = xTimerStart(timer, wait_ticks);
```

通常表示：

> 启动命令已成功提交到定时器命令队列。

它**不表示**：

- 定时器服务任务已经处理了命令；
- 定时器已完成列表插入；
- 回调已经执行；
- 回调一定会在某个墙钟精确时刻开始。

如果命令队列已满，任务 API 可以在给定时间内等待队列空间；等待结束仍无空间则命令提交失败。ISR API 不能阻塞，必须处理失败返回值。

### 5.3 FreeRTOS 定时器命令

常用任务 API：

|API|作用|
|---|---|
|`xTimerStart()`|启动定时器|
|`xTimerStop()`|停止定时器|
|`xTimerReset()`|复位定时器到期时间|
|`xTimerChangePeriod()`|修改周期并重置计时|
|`xTimerDelete()`|请求删除定时器|
|`xTimerIsTimerActive()`|查询内核当前认知的活动状态|
|`xTimerGetTimerID()`|读取应用关联的 Timer ID|

重要 API 语义：

- `xTimerReset()` 常用于“重新开始超时窗口”。
- `xTimerChangePeriod()` 用于修改周期；在常见实现中也会使定时器开始运行。具体行为应核对当前版本 API 文档。
- `xTimerDelete()` 通常也是通过命令队列异步处理。
- 查询 API 反映的是内核当前状态，不一定包含尚在命令队列中的未处理命令。

### 5.4 定时器服务任务与命令队列

定时器命令队列是共享资源，可能同时接收来自多个任务和 ISR 的命令：

```
应用任务 Start/Stop/Reset
ISR Start/Stop/Reset
回调中提交的新命令
PendFunctionCall
        |
        v
Timer Command Queue
        |
        v
Timer daemon task
```

因此：

- 命令队列长度不是定时器数量；
- 队列满可能使启动、停止或复位请求失败；
- 长回调会让定时器服务任务无法及时排空命令队列；
- `xTimerPendFunctionCall()` 也会占用这条服务路径。

### 5.5 Tick 精度、Tick 转换与周期量化

软件定时器基于 Tick。Tick 频率为：

```
fTick = configTICK_RATE_HZ
```

Tick 周期：

```
Ttick = 1 / fTick
```

例如：

|Tick 频率|Tick 分辨率|
|---|---|
|100 Hz|10 ms|
|500 Hz|2 ms|
|1000 Hz|1 ms|

`pdMS_TO_TICKS()` 在许多配置中会按整数运算向下截断。小于一个 Tick 的正数可能被转换为 0。因此，要求“不早于指定毫秒数”时，可使用向上取整，并验证结果不溢出：

```
#include <stdbool.h>
#include <stdint.h>
#include "FreeRTOS.h"

static bool ms_to_ticks_ceil(
    uint64_t milliseconds,
    TickType_t *ticks_out)
{
    const uint64_t hz = (uint64_t)configTICK_RATE_HZ;
    const uint64_t max_ticks =
        (uint64_t)((TickType_t)~(TickType_t)0);

    uint64_t whole_seconds;
    uint64_t remaining_ms;
    uint64_t ticks;
    uint64_t fractional_ticks;

    if ((ticks_out == NULL) ||
        (milliseconds == 0U) ||
        (hz == 0U))
    {
        return false;
    }

    whole_seconds = milliseconds / 1000U;
    remaining_ms = milliseconds % 1000U;

    if (whole_seconds > (max_ticks / hz))
    {
        return false;
    }

    ticks = whole_seconds * hz;
    fractional_ticks =
        ((remaining_ms * hz) + 999U) / 1000U;

    if (fractional_ticks > (max_ticks - ticks))
    {
        return false;
    }

    ticks += fractional_ticks;

    if (ticks == 0U)
    {
        ticks = 1U;
    }

    *ticks_out = (TickType_t)ticks;
    return true;
}
```

注意：

- 该函数以 `TickType_t` 最大值作为上限，不代表这么长的定时器在业务上合理。
- 长时间定时器还应考虑 Tick 回绕、系统休眠和设备生命周期。
- Tick 量化只是精度的一部分，回调实际延迟还受调度和服务任务负载影响。

### 5.6 到期时间与回调实际运行时间

应区分：

```
逻辑到期时间
回调开始时间
回调完成时间
```

回调开始时间可抽象为：

```
Tcallback_start =
    Tlogical_expiry
  + Jtick
  + Jdaemon_schedule
  + Wprior_callbacks
  + I高优先级任务/中断
```

其中：

- `Jtick`：Tick 量化与时间戳误差；
- `Jdaemon_schedule`：定时器服务任务获得 CPU 的延迟；
- `Wprior_callbacks`：前面尚未完成的回调或命令处理；
- `I`：更高优先级任务和中断的干扰。

**定时器期限到达不等于回调立即运行。**

自动重载定时器的到期时间管理细节可能受内核版本和实现影响。无论其名义周期如何管理，回调实际启动时间都会受调度和回调负载影响。若应用需要精确相位、补偿漏周期或定义跳过策略，应使用任务时间戳或硬件定时器明确实现。

### 5.7 自动重载定时器的工程含义

创建自动重载定时器：

```
xTimerCreate(
    "Periodic",
    period_ticks,
    pdTRUE,
    timer_id,
    callback);
```

自动重载意味着定时器到期后会再次进入后续周期，不意味着：

```
每次回调都按绝对精确周期执行
回调执行耗时不会影响其他定时器
错过周期后一定按业务期望补齐
```

如果周期逻辑需要：

```
每 10 ms 采一次样，漏掉时跳过旧样本
```

就应明确使用时间戳和序号实现跳过策略，而不是依赖软件定时器回调的调度时刻。

### 5.8 回调执行上下文与阻塞限制

定时器回调运行在 **Timer daemon task** 中，不在 ISR 中。

回调内不应：

- 调用 `vTaskDelay()`；
- 使用可能阻塞的队列、信号量或互斥量 API；
- 执行长时间计算；
- 等待 DMA、外设或其他任务；
- 使用非零阻塞时间发送定时器命令。

如果回调阻塞，后果可能包括：

```
其他定时器到期处理被推迟
Stop/Reset/Start 命令积压
定时器命令队列填满
所有依赖定时器服务的模块延迟上升
```

回调推荐只做：

```
记录轻量状态
发送任务通知
非阻塞提交短消息
更新受控标志
```

### 5.9 回调中再提交定时器命令

在回调中调用：

```
xTimerStop(timer, 0U);
```

通常会把停止命令放入同一命令队列，之后由定时器服务任务处理。使用 `0` 使队列满时立即失败，避免在服务任务内部等待自身处理队列。

回调中若调用：

```
xTimerStop(timer, portMAX_DELAY);
```

存在严重风险：服务任务可能在等待命令队列空间，而队列只有它自己能够排空，形成自阻塞。

### 5.10 ISR 中调用软件定时器 API

常见 ISR API 包括：

```
xTimerStartFromISR()
xTimerStopFromISR()
xTimerResetFromISR()
xTimerChangePeriodFromISR()
```

示例：

```
void GPIO_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    gpio_clear_interrupt_flags();

    BaseType_t result = xTimerResetFromISR(
        g_debounce_timer,
        &higher_priority_task_woken);

    if (result != pdPASS)
    {
        g_timer_isr_command_failures++;
    }

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

工程限制：

- ISR API 只能提交命令，不能阻塞等待处理；
- 命令队列满时会失败；
- 必须遵守 FreeRTOS 的中断优先级约束；
- 不同版本可用的 ISR API 应查阅当前 `timers.h`；
- 不应假设 ISR 中提交的命令已经立即生效。

### 5.11 静态创建与内存生命周期

动态创建：

```
TimerHandle_t timer = xTimerCreate(
    "Retry",
    period_ticks,
    pdFALSE,
    timer_id,
    callback);
```

静态创建：

```
static StaticTimer_t s_timer_storage;

TimerHandle_t timer = xTimerCreateStatic(
    "Retry",
    period_ticks,
    pdFALSE,
    timer_id,
    callback,
    &s_timer_storage);
```

需要特别注意：

> **静态创建一个 Timer 对象，并不自动证明整个软件定时器子系统完全没有动态分配。**

还要检查当前 FreeRTOS 版本中：

- Timer daemon task 的创建方式；
- Timer command queue 的分配方式；
- `configSUPPORT_STATIC_ALLOCATION` 的相关钩子；
- 其他 timer service 资源的生命周期。

动态删除命令是异步处理的。提交删除后不要继续使用该句柄；若使用静态对象，必须确认对象不再被内核访问后，才能复用其存储。

---

## 6. 性能量化分析

### 6.1 测试平台与证据边界

建议基准平台固定为：

```
MCU：Cortex-M4F，168 MHz
FreeRTOS：记录确切 tag 和提交号
编译器：记录版本及优化参数
Tick：1 kHz
测量：DWT CYCCNT + GPIO/Trace
```

本课未在该平台实际运行，因此不提供未经验证的 API 周期“实测值”。以下给出可复算公式和测量方法。

### 6.2 时间换算

```
T = cycles / fCPU
```

在 168 MHz 下：

|周期数|时间|
|---|---|
|168 cycles|1 μs|
|840 cycles|5 μs|
|1680 cycles|10 μs|

这是周期与时间的换算，不是定时器 API 的实测周期。

### 6.3 Timer command queue 内存与容量

定时器命令队列存储大致由以下部分组成：

```
Rqueue ≈ QueueControlBlock
       + configTIMER_QUEUE_LENGTH × sizeof(DaemonCommand)
       + 对齐和分配器开销
```

`DaemonCommand` 等内部类型通常是内核私有实现，不应在应用代码中硬编码大小。应通过 map 文件和所用版本源码核算。

队列容量可以根据突发和服务延迟初步估算：

```
Qrequired >= BurstCommands
           + CommandRate × MaxDaemonUnserviceTime
           + Margin
```

其中 `MaxDaemonUnserviceTime` 至少要考虑最长回调执行时间和更高优先级负载造成的抢占。

### 6.4 定时器服务任务负载

设第 i 个周期回调频率为 `λi`，平均执行时间为 `Ci`：

```
Utimer_callbacks ≈ Σ(λi × Ci)
```

这只是回调 CPU 负载的简化估算，还未包含：

- 命令处理；
- 定时器列表操作；
- 任务切换；
- Trace 和统计；
- 其他 timer daemon 工作。

如果回调一次执行 2 ms，而多个定时器在相近时刻到期，队列等待和回调串行执行可能显著增加其他定时器的延迟。

### 6.5 回调延迟上界模型

```
Lcallback <=
    Ltick
  + Lcommand_queue
  + Ldaemon_ready
  + Σ(前序回调执行时间)
  + I高优先级任务/中断
```

如果无法为回调执行时间、命令队列等待时间和高优先级干扰给出上界，就不能给出可靠的回调最坏延迟保证。

### 6.6 优化手段与收益来源

|优化|主要收益|注意事项|
|---|---|---|
|回调只发任务通知|缩短 daemon 占用时间|业务处理移至任务后仍需分析响应|
|增大命令队列|降低突发命令立即失败概率|不会解决 daemon 长期处理不过来|
|提高 timer daemon 优先级|降低被其他任务抢占的延迟|可能增加对低优先级任务的干扰|
|将复杂周期逻辑移到独立任务|隔离回调耗时和栈需求|增加任务控制块和栈|
|用硬件定时器处理精确时序|降低 Tick 和任务调度误差|需要处理 ISR 与硬件资源分配|
|减少高频定时器数量|降低命令和到期处理压力|合并后需设计统一调度逻辑|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
时间约束是什么？
|
+-- 亚 Tick 精度、稳定边沿或硬实时输出
|   +-- 使用硬件定时器、PWM、比较通道或 DMA
|
+-- 需要周期执行完整计算流程
|   +-- 使用周期任务，如 vTaskDelayUntil()
|
+-- 低频超时、延迟动作或短小周期回调
    |
    +-- 回调能保持短小且不阻塞？
        |
        +-- 是 -> 软件定时器
        |
        +-- 否 -> 定时器回调只通知任务，工作由任务完成
```

### 7.2 典型场景

|需求|推荐方案|原因|
|---|---|---|
|按键消抖|一次性软件定时器|延迟检查状态，逻辑短|
|通信超时|软件定时器 + 通知/状态机|超时事件与数据处理分离|
|周期性低频健康检查|自动重载软件定时器|维护回调短小|
|电机 PWM 边沿|硬件 PWM|不应依赖任务调度|
|高频 ADC 采样|硬件定时器触发 DMA|定时精度和吞吐更可靠|
|周期算法处理|周期任务|有独立栈和执行上下文|
|长时间重试流程|软件定时器唤醒状态机|避免任务长期阻塞或回调执行重工作|
|一次性延迟开关|软件定时器|适合低频延迟控制|

---

## 8. 工程最佳实践

### 8.1 回调保持短小、非阻塞

推荐：

```
回调：
    设置轻量状态
    通知工作任务

工作任务：
    执行业务处理
    处理错误和恢复
```

不推荐：

```
回调：
    等待外设
    睡眠
    等锁
    做大规模计算
```

### 8.2 将定时器命令视为异步消息

`xTimerStart()` 返回 `pdPASS` 的含义是命令提交成功，不是“定时器已完成启动”。

如果系统必须确认命令已执行，应设计确认通道，例如：

```
发送控制命令
    -> timer service task 处理
    -> 到期回调或管理任务发确认
```

不要只调用 `xTimerIsTimerActive()` 并将其当作命令队列已清空的证明。

### 8.3 定时器所有权和句柄规则

每个定时器应有明确的所有者：

```
谁创建
谁启动和复位
谁停止
谁删除
谁负责处理命令队列满
```

多个模块同时控制同一个定时器，容易发生：

```
任务 A 请求 Reset
任务 B 请求 Stop
命令按入队顺序处理，但业务期望不清晰
```

复杂系统建议由单一管理任务拥有定时器，其他模块发送定时器控制消息。

### 8.4 选择 daemon task 优先级

- 优先级过低：回调和命令会被高优先级任务长时间压制。
- 优先级过高：会增加对普通任务的抢占影响。
- 回调如果已保证短小，通常较容易建立稳定预算。
- 优先级应通过系统响应时间分析确定，而不是默认设置成最高。

### 8.5 计算周期时避免静默截断

```
TickType_t ticks;

if (!ms_to_ticks_ceil(requested_ms, &ticks))
{
    return TIMER_PERIOD_OUT_OF_RANGE;
}
```

然后检查：

- 周期是否大于 0；
- 周期是否符合业务允许范围；
- Tick 频率是否足以满足最小精度；
- 最大 Tick 范围和回绕语义是否可接受。

### 8.6 记录关键诊断数据

至少监控：

```
Start/Stop/Reset 命令失败数
定时器服务任务栈余量
timer command queue 高水位
回调最大执行时间
回调迟到时间
定时器到期次数
丢弃或跳过周期次数
```

### 8.7 关键实时动作使用硬件资源

如果动作与时间误差直接影响设备安全或控制性能，应考虑：

- 硬件比较寄存器；
- PWM 外设；
- 输入捕获；
- DMA 定时触发；
- 独立高精度定时器中断。

软件定时器的回调受任务调度、命令队列和其他回调影响，**不能承诺硬件级时序精度**。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：把 `xTimerStart()` 成功当作回调已安排完成

错误假设：

```
if (xTimerStart(timer, 0U) == pdPASS)
{
    /* 错：假设定时器已在 daemon task 中生效 */
    begin_operation_requiring_timer_active_state();
}
```

**根因：** `pdPASS` 通常表示启动命令已进入命令队列，不表示 daemon 已处理。

正确做法：

- 把启动命令视为异步请求；
- 若必须知道处理完成，设计确认机制；
- 不依赖立即查询状态推断命令队列状态。

**风险影响：** 状态机提前进入下一阶段，导致超时保护未生效。

### 9.2 错误二：在回调中阻塞

错误代码：

```
static void timer_callback(TimerHandle_t timer)
{
    xQueueSend(
        g_queue,
        &message,
        portMAX_DELAY);
}
```

**根因：** 回调运行于共享 timer daemon task；队列满时，所有定时器处理都会被阻塞。

正确实现：

```
static void timer_callback(TimerHandle_t timer)
{
    if (xQueueSend(
            g_queue,
            &message,
            0U) != pdPASS)
    {
        g_queue_overflow_count++;
    }

    /* 或使用 xTaskNotify() 通知专用工作任务。 */
}
```

**风险影响：** 其他定时器迟到、命令队列满、系统超时路径整体失效。

### 9.3 错误三：回调中带非零等待时间提交定时器命令

错误代码：

```
static void timer_callback(TimerHandle_t timer)
{
    xTimerReset(timer, portMAX_DELAY);
}
```

**根因：** 回调本身就在消费 timer command queue 的 daemon task 中。命令队列满时，daemon 可能等待自身排空队列。

正确实现：

```
static void timer_callback(TimerHandle_t timer)
{
    if (xTimerReset(timer, 0U) != pdPASS)
    {
        timer_command_failure_count++;
    }
}
```

更好的设计通常是用自动重载定时器或由独立任务控制复位。

**风险影响：** daemon task 自阻塞，造成定时器服务停摆。

### 9.4 错误四：命令队列满时忽略失败

错误代码：

```
(void)xTimerReset(timer, 0U);
```

**根因：** 定时器命令提交可能失败，但代码不记录，也不重试或降级。

正确实现：

```
if (xTimerReset(timer, pdMS_TO_TICKS(5)) != pdPASS)
{
    timer_reset_failures++;
    report_timer_control_failure();
}
```

ISR 中不可阻塞，应检查 FromISR 返回值并设计失败路径。

**风险影响：** 超时窗口未复位、看门狗策略错误、系统进入不可诊断状态。

### 9.5 错误五：用 `pdMS_TO_TICKS()` 转换很短周期而得到 0

错误代码：

```
TickType_t period = pdMS_TO_TICKS(1U);

if (xTimerChangePeriod(timer, period, 0U) != pdPASS)
{
    /* period 可能为 0，或不满足定时器要求 */
}
```

**根因：** 转换宏可能向下截断；当 Tick 周期大于请求时间时，结果可能是 0。

正确做法：

- 对正数毫秒周期按向上取整；
- 检查转换结果；
- 若要求精度高于 Tick，使用硬件定时器。

**风险影响：** 断言失败、周期错误或出现不可预测行为。

### 9.6 错误六：把软件定时器当精确周期源

错误假设：

```
/* 假设每次回调恰好间隔 1 ms。 */
static void fast_callback(TimerHandle_t timer)
{
    update_control_loop();
}
```

**根因：** Tick 量化、daemon 调度、前序回调和高优先级干扰都会造成延迟；软件回调不是硬件比较事件。

正确方案：

- 使用硬件定时器触发采样或波形；
- 用周期任务运行需要独立上下文的算法；
- 为低频维护任务接受 Tick 和调度抖动。

**风险影响：** 采样抖动、控制环不稳定、通信边沿不符合协议时序。

### 9.7 错误七：删除定时器后继续访问句柄或复用静态存储

错误模式：

```
xTimerDelete(timer, 0U);
reuse_static_timer_buffer();
```

**根因：** 删除命令通常异步处理，服务任务可能尚未完成删除。

正确做法：

- 删除前停止相关生产者；
- 提交删除后不再使用句柄；
- 对静态存储建立完成确认或由单一生命周期管理者控制；
- 不在无法确认安全时立即复用对象存储。

**风险影响：** Use-after-free、控制块破坏、随机 HardFault。

---

## 10. 多机制组合使用方案

### 10.1 软件定时器 + 任务通知

推荐结构：

```
Timer daemon task：
    到期回调只发通知

Worker task：
    接收通知
    执行业务
    处理错误和恢复
```

这样可以把回调时间缩短，并隔离业务栈需求。

### 10.2 软件定时器 + 消息队列

适合需要携带超时上下文的系统：

```
回调：
    非阻塞发送 {timer_id, generation, timeout_type}

状态机任务：
    收到后检查 generation
    确认超时是否仍属于当前事务
```

使用代际编号可以避免：

```
旧事务定时器命令迟到
新事务已经开始
旧超时误终止新事务
```

### 10.3 软超时 + 硬件截止时间

```
硬件定时器：
    生成精确的采样、PWM 或总线时序

软件定时器：
    检测设备是否长时间无响应
    触发恢复状态机
```

两者职责不同：硬件定时器保证边沿或采样时刻，软件定时器管理较粗粒度的系统超时。

### 10.4 完整代码框架：超时定时器通知工作任务

以下框架采用静态 Timer 对象。回调只向工作任务发通知，不执行耗时操作。

```
#include <stdbool.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "task.h"
#include "timers.h"

#define NOTIFY_RETRY_TIMEOUT    (1UL << 0)

typedef struct
{
    TaskHandle_t worker_task;
    volatile uint32_t callback_notify_failures;
} retry_timer_context_t;

static retry_timer_context_t s_retry_context;
static StaticTimer_t s_retry_timer_storage;
static TimerHandle_t s_retry_timer;

static void retry_timer_callback(TimerHandle_t timer)
{
    retry_timer_context_t *context =
        (retry_timer_context_t *)pvTimerGetTimerID(timer);

    if ((context == NULL) ||
        (context->worker_task == NULL))
    {
        return;
    }

    /*
     * 回调在 Timer daemon task 上下文运行。
     * xTaskNotify() 不需要 FromISR API，也不能使用阻塞等待。
     */
    if (xTaskNotify(
            context->worker_task,
            NOTIFY_RETRY_TIMEOUT,
            eSetBits) != pdPASS)
    {
        context->callback_notify_failures++;
    }
}

bool retry_timer_init(
    TaskHandle_t worker_task,
    TickType_t period_ticks)
{
    if ((worker_task == NULL) ||
        (period_ticks == 0U))
    {
        return false;
    }

    s_retry_context.worker_task = worker_task;
    s_retry_context.callback_notify_failures = 0U;

    s_retry_timer = xTimerCreateStatic(
        "RetryTimeout",
        period_ticks,
        pdFALSE,                 /* 一次性定时器 */
        &s_retry_context,        /* Timer ID */
        retry_timer_callback,
        &s_retry_timer_storage);

    return s_retry_timer != NULL;
}

bool retry_timer_start(TickType_t command_wait_ticks)
{
    if (s_retry_timer == NULL)
    {
        return false;
    }

    /*
     * pdPASS 表示 Start 命令提交成功，
     * 不表示回调已经执行或定时器已立即生效。
     */
    return xTimerStart(
               s_retry_timer,
               command_wait_ticks) == pdPASS;
}

bool retry_timer_reset(TickType_t command_wait_ticks)
{
    if (s_retry_timer == NULL)
    {
        return false;
    }

    return xTimerReset(
               s_retry_timer,
               command_wait_ticks) == pdPASS;
}

bool retry_timer_stop(TickType_t command_wait_ticks)
{
    if (s_retry_timer == NULL)
    {
        return false;
    }

    return xTimerStop(
               s_retry_timer,
               command_wait_ticks) == pdPASS;
}

static void RetryWorkerTask(void *argument)
{
    (void)argument;

    for (;;)
    {
        uint32_t notification_value = 0U;

        if (xTaskNotifyWait(
                0U,
                NOTIFY_RETRY_TIMEOUT,
                &notification_value,
                portMAX_DELAY) == pdTRUE)
        {
            if ((notification_value &
                 NOTIFY_RETRY_TIMEOUT) != 0U)
            {
                retry_timeout_state_machine_step();
            }
        }
    }
}
```

设计注意：

- `RetryWorkerTask` 应先创建，并在开启定时器控制流程前保存有效句柄。
- `retry_timer_start()` 返回成功只表示命令入队。
- 如果超时可能属于不同事务，应增加事务编号或代际编号。
- 统计计数仅由 timer daemon task 修改；读取时应通过安全快照、临界区或诊断消息转交，不能默认跨任务访问天然安全。
- 静态 Timer 对象不代表 Timer command queue 和 daemon task 一定完全静态分配。

---

## 11. 工业级实际案例分析

### 11.1 案例一：按键消抖

**需求：**

- GPIO 边沿触发后，等待稳定时间再读取电平；
- 后续边沿需要重新开始消抖窗口；
- ISR 中不执行延时。

**架构：**

```
GPIO ISR
    -> xTimerResetFromISR()
    -> timer daemon 处理复位命令

定时器回调
    -> 通知按键任务

按键任务
    -> 读取 GPIO 状态
    -> 状态确认和事件上报
```

**设计要点：**

- ISR 中不能调用普通 `xTimerReset()`。
- 命令队列满时必须有恢复策略。
- 如果抖动边沿频率很高，需确认命令队列有足够余量。
- 若要严格控制采样窗口，使用硬件捕获或周期采样任务。
- 回调中只通知按键任务，不执行复杂状态机。

### 11.2 案例二：通信请求超时

**需求：**

- 发送请求后启动响应超时；
- 收到匹配响应时取消或复位计时器；
- 超时后重试有限次数；
- 迟到响应不能误完成下一笔请求。

**架构：**

```
协议任务：
    创建事务编号
    启动一次性定时器

响应到达：
    校验事务编号
    提交 Stop 命令

定时器回调：
    发送 {transaction_id, timeout_event} 给协议任务

协议任务：
    再次核验 transaction_id
    决定重试、失败或忽略迟到事件
```

**设计要点：**

- 回调只发送轻量通知或消息。
- 事务编号用于防止旧超时误作用于新事务。
- Stop 命令是异步的，收到响应与超时回调可能竞争；最终裁决由单一协议任务完成。
- 超时参数应按实际链路延迟和重试策略设计，而非只按名义传输时间设置。

### 11.3 案例三：设备低频健康检查

**需求：**

- 每秒检查一次传感器和总线状态；
- 检查可能包含多个寄存器访问；
- 出错后进入恢复状态机。

**架构：**

```
自动重载软件定时器
    -> 通知健康检查任务
    -> 任务执行有界状态检查
    -> 更新设备状态和故障事件
```

**设计要点：**

- 不在 timer callback 中执行总线读写或等待。
- 健康检查任务有独立栈和可测量 WCET。
- 任务运行频率必须低于其可持续服务能力。
- 若检查过程可能因总线锁阻塞，应分析优先级反转和超时。
- 严重故障另发故障记录，不只依赖一个定时器位。

---

## 12. 高频问题深度答疑

### 问题一：`xTimerStart()` 返回 `pdPASS` 后，定时器什么时候开始计时？

它通常表示命令已进入 Timer command queue。命令由 daemon task 后续处理。

常见 FreeRTOS 实现会在命令中记录调用时的 Tick 时间，用于计算逻辑到期时间；但服务任务处理延迟仍可能导致回调启动时间晚于预期。**应以项目对应版本的 API 文档和源码为准，不要假设命令处理即时完成。**

### 问题二：定时器回调能调用 FreeRTOS API 吗？

可以调用适用于任务上下文的非阻塞 API，例如：

- `xTaskNotify()`；
- `xQueueSend(..., 0)`；
- `xEventGroupSetBits()`。

但不得调用可能阻塞的 API。回调共享 Timer daemon task，阻塞会影响其他定时器服务。

### 问题三：自动重载定时器会不会补发所有错过的周期？

不能在不了解当前版本实现和应用语义的情况下作此假设。

更重要的是，回调实际执行时间会受到调度和其他回调影响。若业务要求：

- 每次周期都处理；
- 漏周期后补算；
- 漏周期后跳过；
- 保持绝对相位；

应显式维护周期编号和时间戳，并定义补偿策略。

### 问题四：`xTimerChangePeriod()` 可以用于启动停用的定时器吗？

在常见 FreeRTOS 实现中，修改周期命令会重置并启动计时器。但 API 细节和版本可能有差异。工程代码应以本项目版本的 `timers.h` 文档和源码为准，并编写相应测试，不要仅凭函数名推断。

### 问题五：能不能在回调中调用 `vTaskDelay()`？

不能。回调运行在 Timer daemon task 中，阻塞该任务会暂停其他软件定时器回调和命令处理。

正确方式是：回调通知工作任务，工作任务完成延时等待或耗时操作。

### 问题六：`xTimerIsTimerActive()` 能不能确认刚发送的 Start 已经生效？

不能可靠地确认尚在命令队列中的请求已被处理。它反映的是内核当前识别的活动状态，不是通用命令确认协议。若需要确认，应设计专用确认事件或管理任务。

### 问题七：软件定时器能用于硬实时控制吗？

一般不应把它作为硬件时序输出的直接来源。它受到：

- Tick 分辨率；
- daemon task 优先级；
- 其他回调耗时；
- 命令队列负载；
- 更高优先级任务和中断；

影响。硬实时边沿和采样应由硬件定时器、PWM、DMA 或硬件触发链完成。

---

## 13. 课程核心总结

### 核心要点

1. **FreeRTOS 软件定时器由 Timer daemon task 管理。**
2. 定时器 Start、Stop、Reset 等命令通常通过命令队列异步处理。
3. `pdPASS` 表示命令提交成功，不代表操作已完成。
4. 所有软件定时器回调共享 daemon task，必须短小、非阻塞。
5. 回调阻塞会同时影响其他定时器和命令处理。
6. ISR 使用 FromISR API，命令队列满时必须处理失败。
7. Tick 决定时间量化，任务调度和回调串行又增加实际延迟。
8. 自动重载不等于回调精确周期运行。
9. 静态 Timer 对象不等于整个 Timer 子系统完全不使用堆。
10. 精确波形和硬实时采样应交给硬件定时器。

### 通用选型结论

```
低频超时、延迟动作、短小回调：
    软件定时器

周期性且有完整计算流程：
    周期任务

精确边沿、PWM、采样触发：
    硬件定时器 / DMA

长时间超时后的复杂处理：
    软件定时器唤醒任务，任务执行恢复逻辑
```

---

## 14. 快速参考速查表

### 14.1 主要 API

|需求|API|
|---|---|
|动态创建|`xTimerCreate()`|
|静态创建|`xTimerCreateStatic()`|
|启动|`xTimerStart()`|
|停止|`xTimerStop()`|
|复位|`xTimerReset()`|
|修改周期|`xTimerChangePeriod()`|
|删除|`xTimerDelete()`|
|查询活动状态|`xTimerIsTimerActive()`|
|读取 Timer ID|`pvTimerGetTimerID()`|
|ISR 启动|`xTimerStartFromISR()`|
|ISR 停止|`xTimerStopFromISR()`|
|ISR 复位|`xTimerResetFromISR()`|
|ISR 修改周期|`xTimerChangePeriodFromISR()`|
|在 daemon task 中延迟执行函数|`xTimerPendFunctionCall()`|

### 14.2 配置速查

|配置项|用途|
|---|---|
|`configUSE_TIMERS`|启用软件定时器|
|`configTIMER_TASK_PRIORITY`|Timer daemon task 优先级|
|`configTIMER_QUEUE_LENGTH`|定时器命令队列容量|
|`configTIMER_TASK_STACK_DEPTH`|Timer daemon task 栈深度|

### 14.3 关键约束

|项目|约束|
|---|---|
|回调上下文|Timer daemon task|
|回调阻塞|禁止|
|Timer command queue|多定时器和 PendFunctionCall 共用|
|API 返回 `pdPASS`|通常只表示命令入队|
|ISR|使用 FromISR API|
|命令队列满|必须处理失败|
|精度|受 Tick 与调度延迟影响|
|硬实时输出|用硬件定时器|
|静态 Timer|不保证整个子系统完全静态分配|
|删除操作|可能异步完成，句柄不可继续使用|

---

## 15. 学习效果自检

- [ ]  能画出应用命令、Timer command queue、daemon task 和回调的执行链。
- [ ]  能解释 `xTimerStart()` 返回成功不等于回调已执行。
- [ ]  能说明回调阻塞为什么会影响所有软件定时器。
- [ ]  能区分 Timer period 和命令队列等待时间。
- [ ]  能正确计算 Tick 周期和毫秒转换结果。
- [ ]  能处理 `pdMS_TO_TICKS()` 产生 0 或溢出的情况。
- [ ]  能正确使用 ISR 定时器 API。
- [ ]  能设计命令队列满时的错误路径。
- [ ]  能解释自动重载与回调实际周期之间的区别。
- [ ]  能判断什么时候应改用周期任务或硬件定时器。
- [ ]  能在回调中只发送通知，把耗时工作转交给任务。
- [ ]  能处理动态删除和静态存储复用的生命周期问题。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

|阶段|任务|验收标准|
|---|---|---|
|1|创建一次性定时器并通知工作任务|回调不执行阻塞操作|
|2|创建自动重载定时器|记录实际周期和回调最大耗时|
|3|多任务同时 Start/Stop/Reset|统计命令失败和队列高水位|
|4|ISR 复位消抖定时器|检查中断优先级、返回值和抖动情况|
|5|注入慢回调|观察其他定时器延迟和命令积压|
|6|注入命令队列满|验证系统有诊断和恢复路径|
|7|对比软件定时器与硬件定时器|测量周期精度、抖动和 CPU 占用|

### 16.2 性能测试方法

#### DWT 测量回调执行时间

```
static volatile uint32_t s_callback_max_cycles;

static void measured_callback(TimerHandle_t timer)
{
    uint32_t start = DWT->CYCCNT;

    timer_callback_short_work(timer);

    uint32_t elapsed = DWT->CYCCNT - start;

    if (elapsed > s_callback_max_cycles)
    {
        s_callback_max_cycles = elapsed;
    }
}
```

此例适用于低风险诊断环境。对跨任务共享统计量，应使用临界区、原子操作或由单一任务读取，避免数据竞争。

#### GPIO 测量回调迟到

在设定的逻辑到期附近由回调拉高 GPIO，用逻辑分析仪观察：

```
预期到期时刻
    ->
回调开始时刻
```

再通过 DWT 或 Trace 记录：

```
回调开始到回调结束的时间
```

应分别统计：

- 最小值；
- 平均值；
- P99 和 P99.9；
- 最大观察值；
- timer command queue 高水位；
- Start/Reset 失败数；
- daemon task 栈余量；
- 前序回调执行时间。

最大观察值不是严格的 WCET，需要结合任务优先级、最长回调、最长临界区和中断干扰建立上界。

### 16.3 进阶学习方向

- 阅读 `timers.c` 中的命令处理、到期列表和回调执行路径。
- 分析 FreeRTOS 定时器命令队列的长度、对象大小和入队超时。
- 研究 Tick 溢出列表、Tickless Idle 和低功耗唤醒对定时器的影响。
- 对比 `vTaskDelayUntil()`、软件定时器与硬件比较定时器。
- 建立回调执行预算和 Timer daemon task 响应时间模型。
- 为超时状态机加入事务编号、重复启动保护和迟到事件处理。
- 对高精度需求使用硬件定时器触发 DMA，软件定时器只承担系统级监督。