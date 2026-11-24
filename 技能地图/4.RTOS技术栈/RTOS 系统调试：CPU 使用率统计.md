
## 1. 学习目标

### 理解

- 理解 CPU 使用率、任务运行时间、调度延迟、ISR 占用率和系统空闲率的区别。
- 理解基于空闲任务、运行时间统计、Trace 事件和硬件采样的 CPU 使用率计算原理。
- 理解 CPU 使用率统计对时间基准、任务切换、溢出、低功耗和多核系统的依赖。

### 掌握

- 掌握 FreeRTOS `vTaskGetRunTimeStats()`、`uxTaskGetSystemState()` 和空闲任务统计的使用方式。
- 掌握任务级、ISR 级和系统级 CPU 使用率的计算方法。
- 掌握统计周期、时间基准、临界区和计数器溢出的工程处理方法。

### 精通

- 能区分平均 CPU 使用率、瞬时 CPU 使用率、峰值 CPU 使用率和窗口内 P99 使用率。
- 能定位 CPU 高占用、任务饥饿、忙等、ISR 风暴、优先级配置错误和低功耗统计失真。
- 能量化 CPU 统计机制自身带来的时间、RAM 和调度开销。

### 能够设计

- 能为单核 MCU、带中断系统和低功耗系统设计生产级 CPU 使用率统计模块。
- 能建立任务级、ISR 级、系统级的性能指标体系和阈值告警策略。
- 能将 CPU 使用率与 Tracealyzer、SystemView、看门狗、性能计数器和现场诊断结合。

## 2. 前置要求

### 知识要求

- 熟悉 RTOS 任务状态：Running、Ready、Blocked、Suspended。
- 理解抢占式调度、时间片、优先级、空闲任务和中断上下文。
- 了解 MCU 定时器、DWT 周期计数器或其他自由运行计数器。
- 理解 `tick`、系统时钟、主频和时间单位之间的换算关系。
- 了解任务栈、堆、临界区、关中断和低功耗机制。

### 技能要求

- 能配置 FreeRTOS 的 `FreeRTOSConfig.h`。
- 能读取任务状态、任务优先级、任务栈余量和运行时间统计。
- 能阅读 linker map 文件，计算统计缓冲区和任务控制块的资源占用。
- 能使用逻辑分析仪、DWT、示波器或 SystemView 验证 CPU 统计结果。
- 能构造稳定、可重复的压力测试场景。

## 3. 技术概述

CPU 使用率表示在一个统计时间窗口内，处理器用于执行非空闲工作的时间比例。

单核系统中：

```
系统 CPU 使用率 = 1 - 空闲时间 / 统计窗口时间
```

如果统计窗口为 `T`，空闲任务运行时间为 `T_idle`：

```
CPU 使用率 = (T - T_idle) / T × 100%
```

也可以由任务运行时间求和：

```
CPU 使用率 = Σ(各任务运行时间) / 统计窗口时间 × 100%
```

但该公式必须明确是否包含：

- ISR 执行时间；
- 空闲任务时间；
- 调度器和临界区开销；
- 统计代码自身开销；
- 睡眠或停止时钟期间。

常见实现方式：

1. **空闲任务计数法**  
    通过空闲任务钩子或空闲任务运行计数估算空闲比例。
    
2. **任务运行时间统计法**  
    RTOS 在任务切换时读取高分辨率计数器，累加每个任务的运行时间。
    
3. **Trace 事件法**  
    通过 Tracealyzer、SystemView 等工具从任务切换和 ISR 事件重建 CPU 时间分布。
    
4. **硬件采样法**  
    使用周期采样中断、PC 采样、ETM 或性能监控单元估算执行热点。
    
5. **低功耗状态统计法**  
    将 Running、Idle、Sleep、Stop 等处理器状态分别计时，适用于低功耗产品。
    

CPU 使用率不是单独的性能结论。一个系统 CPU 使用率为 30%，并不意味着它一定满足实时性要求。高优先级任务可能只执行 5%，但某次响应延迟仍可能超过截止时间。

## 4. 核心特性横向对比

|统计方案|时间分辨率|任务级分解|ISR 统计|运行开销|适用场景|
|---|---|---|---|---|---|
|空闲任务钩子|通常为采样窗口级|弱|通常不直接支持|低|快速判断系统负载|
|空闲任务运行时间|取决于计数器|弱|通常并入非空闲时间|低|长期产品监控|
|RTOS 任务运行时间|高，可达周期计数器级|强|取决于端口实现|中|任务负载定位|
|Tracealyzer/SystemView|高|强|强，取决于适配层|中到高|调度、阻塞和时序分析|
|周期采样|采样周期级|近似|可配置|低到中|热点趋势和长期观测|
|ETM/硬件追踪|指令或周期级|强|强|通常低|高精度性能剖析|
|`printf` 统计输出|输出周期级|取决于实现|弱|高且不稳定|不推荐用于实时统计|

### 关键差异

- **空闲统计适合回答“系统是否接近满载”** 。
- **任务运行时间适合回答“哪个任务消耗了 CPU”** 。
- **Trace 工具适合回答“为什么这个任务消耗 CPU、什么时候被延迟”** 。
- **硬件跟踪适合回答“具体代码路径和指令在哪里耗时”** 。

## 5. 底层原理与功能特性深度解析

### 5.1 空闲任务统计原理

FreeRTOS 的空闲任务在没有其他 Ready 任务时运行。若能记录空闲任务占用的时间，就可以计算系统非空闲占用。

最简单的方式是在空闲任务钩子中增加计数：

```
static volatile uint32_t g_idle_loop_count;

void vApplicationIdleHook(void)
{
    ++g_idle_loop_count;
}
```

然后由统计任务每隔一段时间读取并清零：

```
static uint32_t g_last_idle_count;

static uint32_t cpu_usage_from_idle_count(uint32_t current_idle_count,
                                          uint32_t window_ticks)
{
    const uint32_t delta = current_idle_count - g_last_idle_count;

    g_last_idle_count = current_idle_count;

    /*
     * idle_count 不是时间单位，必须先通过基准测试得到：
     * 满空闲状态下每个统计窗口可执行多少次 idle loop。
     */
    return idle_count_to_cpu_percent(delta, window_ticks);
}
```

这种方法存在一个根本问题：`idle loop` 的执行次数不是固定时间单位。它会受以下因素影响：

- 编译器优化等级；
- Flash 等待周期；
- cache 状态；
- 中断频率；
- 调试器状态；
- 空闲钩子代码本身；
- 低功耗切换。

因此，单纯计数空闲循环次数只能作为粗略负载指标。生产级系统应优先使用硬件时间基准统计空闲任务运行时间。

### 5.2 FreeRTOS 运行时间统计

FreeRTOS 提供 `configGENERATE_RUN_TIME_STATS` 配置选项。启用后，内核在任务切换相关路径中获取运行时间计数，并维护每个任务的运行时间累计值。

典型配置：

```
#define configGENERATE_RUN_TIME_STATS    1
#define configUSE_TRACE_FACILITY         1
#define configUSE_STATS_FORMATTING_FUNCTIONS 1

#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS() \
    platform_runtime_counter_init()

#define portGET_RUN_TIME_COUNTER_VALUE() \
    platform_runtime_counter_get()
```

不同 FreeRTOS 版本和端口对宏的要求可能略有差异，应以当前版本 `portable` 目录和示例配置为准。

推荐使用一个高分辨率自由运行计数器：

```
#include <stdint.h>

#define RUNTIME_COUNTER_HZ 1000000UL

static volatile uint32_t g_runtime_counter;

void platform_runtime_counter_init(void)
{
    /*
     * 配置一个 1 MHz 或更高频率的自由运行计数器。
     * 计数器必须持续运行，不应依赖 RTOS tick 中断。
     */
    timer_config_free_running(RUNTIME_COUNTER_HZ);
}

uint32_t platform_runtime_counter_get(void)
{
    return timer_read_counter();
}
```

### 5.3 任务 CPU 使用率计算

通过 `uxTaskGetSystemState()` 获取任务状态：

```
#include "FreeRTOS.h"
#include "task.h"

#define MAX_TASKS 32U

static TaskStatus_t g_task_status[MAX_TASKS];

void cpu_report_tasks(void)
{
    UBaseType_t total_tasks = 0U;
    uint32_t total_runtime = 0U;

    total_tasks = uxTaskGetSystemState(
        g_task_status,
        MAX_TASKS,
        &total_runtime);

    if (total_tasks == 0U || total_runtime == 0U) {
        return;
    }

    for (UBaseType_t i = 0U; i < total_tasks; ++i) {
        const uint32_t task_runtime = g_task_status[i].ulRunTimeCounter;
        const uint32_t usage =
            (uint32_t)(((uint64_t)task_runtime * 10000ULL) /
                       (uint64_t)total_runtime);

        /*
         * usage 采用百分之一百分比：
         * 1234 表示 12.34%。
         */
        cpu_store_task_usage(g_task_status[i].pcTaskName, usage);
    }
}
```

使用 `uint64_t` 进行中间计算很重要。若直接执行：

```
uint32_t usage = task_runtime * 100U / total_runtime;
```

当 `task_runtime` 较大时，乘法可能先溢出，最终得到错误结果。

### 5.4 统计时间窗口与增量计算

累计运行时间适合查看总分布，但诊断实时负载时更需要窗口内变化量：

```
typedef struct {
    TaskHandle_t handle;
    uint32_t previous_runtime;
} task_runtime_snapshot_t;

typedef struct {
    uint32_t total_delta;
    uint32_t task_delta;
    uint32_t usage_x100;
} task_usage_result_t;

static task_usage_result_t calc_window_usage(
    uint32_t current_total,
    uint32_t current_task,
    task_runtime_snapshot_t *snapshot)
{
    task_usage_result_t result = {0};

    if (snapshot == NULL) {
        return result;
    }

    const uint32_t task_delta =
        current_task - snapshot->previous_runtime;

    snapshot->previous_runtime = current_task;
    result.task_delta = task_delta;
    result.total_delta = current_total;
    if (current_total != 0U) {
        result.usage_x100 =
            (uint32_t)(((uint64_t)task_delta * 10000ULL) /
                       (uint64_t)current_total);
    }

    return result;
}
```

这里的减法依赖无符号整数的模回绕特性。只要两个采样点之间的时间间隔小于计数器完整回绕周期，增量计算仍然有效。

### 5.5 ISR CPU 占用率

很多 RTOS 任务运行时间统计只统计任务上下文，或者把 ISR 时间归入被打断任务。这会导致任务级统计出现偏差。

一种工程化做法是在 ISR 入口和出口读取计数器：

```
typedef struct {
    volatile uint32_t total_cycles;
    volatile uint32_t count;
    volatile uint32_t max_cycles;
} isr_metric_t;

static isr_metric_t g_dma_isr_metric;

void DMA_IRQHandler(void)
{
    const uint32_t start = platform_cycle_count();

    dma_clear_interrupt_flags();
    dma_process_events();

    const uint32_t elapsed = platform_cycle_count() - start;

    g_dma_isr_metric.total_cycles += elapsed;
    g_dma_isr_metric.count++;

    if (elapsed > g_dma_isr_metric.max_cycles) {
        g_dma_isr_metric.max_cycles = elapsed;
    }
}
```

这个示例在严格并发场景下还需要考虑：

- 是否存在嵌套中断；
- `total_cycles` 是否可能被其他上下文读取；
- 计数器是否会回绕；
- ISR 中增加的统计代码是否改变了 ISR 延迟；
- 编译器是否重排了关键读写。

在带嵌套中断的系统中，ISR 统计应采用栈式嵌套模型，而不是简单的全局 `start` 和 `end`：

```
typedef struct {
    uint32_t enter_cycle;
    uint32_t accumulated_cycle;
} irq_trace_frame_t;

static irq_trace_frame_t g_irq_frame[IRQ_NESTING_MAX];
static uint32_t g_irq_depth;

void irq_trace_enter(void)
{
    if (g_irq_depth < IRQ_NESTING_MAX) {
        g_irq_frame[g_irq_depth].enter_cycle =
            platform_cycle_count();
        g_irq_frame[g_irq_depth].accumulated_cycle = 0U;
        ++g_irq_depth;
    }
}

void irq_trace_exit(void)
{
    if (g_irq_depth == 0U) {
        return;
    }

    --g_irq_depth;

    const uint32_t elapsed =
        platform_cycle_count() - g_irq_frame[g_irq_depth].enter_cycle;

    irq_record_duration(elapsed);
}
```

实际项目应避免在所有 ISR 中无条件调用重型统计函数，优先对关键 ISR 或通过编译选项选择性启用。

### 5.6 瞬时、平均和峰值 CPU 使用率

设窗口长度为 `T`：

- **平均使用率**：窗口内总运行时间除以 `T`。
- **瞬时使用率**：较短窗口内的使用率，响应快但波动大。
- **峰值使用率**：多个窗口中的最大值。
- **P99 使用率**：99% 的窗口不超过的使用率，适合容量评估。

例如：

```
采样周期：100 ms
窗口使用率：72%、75%、91%、68%、84%
平均值：78%
峰值：91%
P99：取决于更长时间窗口和样本数量
```

仅报告平均值会掩盖短时 CPU 峰值。对实时系统，应至少保存：

- 平均使用率；
- 最大使用率；
- 超阈值次数；
- 连续超阈值窗口数；
- 任务级最大占用；
- ISR 最大执行时间。

## 6. 性能量化分析

### 6.1 测量平台与数据说明

以下数据为**典型 Cortex-M4F、120 MHz、FreeRTOS、1 MHz 运行时间计数器、O2 优化下的示例测量格式**，用于说明测量方法，不应作为所有平台的固定值。实际数据必须在产品目标板上重新测量。

|项目|示例数据|
|---|---|
|CPU 主频|120 MHz|
|运行时间计数器|1 MHz|
|统计窗口|100 ms|
|任务数量|12|
|运行时间统计额外 RAM|约 16~32 字节/任务，取决于 TCB 配置|
|单次任务统计读取|约 1~5 微秒|
|`uxTaskGetSystemState()` 读取 12 个任务|约 10~30 微秒|
|每 100 ms 统计一次的平均 CPU 占用|通常远低于 0.1%，需实测|
|DWT 读取一次|通常为若干 CPU 周期量级，取决于封装和编译|

这些数字受以下因素显著影响：

- Cortex-M 内核型号；
- Flash 等待周期和 cache；
- FreeRTOS 版本；
- 任务数量；
- 是否启用浮点；
- 统计输出格式化方式；
- 是否通过串口输出；
- 编译器和优化等级。

### 6.2 运行时间统计精度

若运行时间计数器频率为 `f_counter`，计数周期为：

```
Δt = 1 / f_counter
```

当 `f_counter = 1 MHz` 时：

```
1 个计数 = 1 微秒
```

如果使用 RTOS tick 统计，`configTICK_RATE_HZ = 1000` 时，时间分辨率只有 1 ms。对于 100 微秒级任务，tick 统计无法提供足够精度。

### 6.3 计数器回绕

对于 32 位、1 MHz 计数器：

```
回绕时间 = 2^32 / 1,000,000
         ≈ 4294.97 秒
         ≈ 71.6 分钟
```

如果使用 120 MHz 的 32 位 DWT 周期计数器：

```
回绕时间 = 2^32 / 120,000,000
         ≈ 35.8 秒
```

因此，DWT 周期计数器适合短窗口精确测量，但不适合直接作为长时间累计计数器，除非周期性扩展为 64 位时间基准。

### 6.4 CPU 统计的内存开销

任务运行时间统计的内存开销主要包括：

```
额外 RAM ≈ 每任务统计字段 + 任务快照数组
         + 统计任务栈
         + 输出缓冲区
         + ISR 统计结构
```

如果：

- 任务数为 20；
- 每任务运行时间字段 4 字节；
- 快照结构每任务 40 字节；
- 输出缓冲区为 512 字节；

则粗略 RAM 增量约为：

```
20 × 4 + 20 × 40 + 512
= 1392 字节
```

实际还需计入结构体对齐、任务名存储和工具链实现差异。

### 6.5 瓶颈与优化

常见瓶颈：

1. **统计频率过高**：每 1 ms 统计一次会增加管理和输出开销。
2. **使用 `sprintf` 格式化**：可能引入较大的代码、栈和执行时间。
3. **在高优先级任务中输出**：串口输出可能阻塞或造成调度扰动。
4. **统计所有 ISR**：中断入口和出口开销叠加。
5. **使用过高频率计数器却不处理回绕**：长期运行后得到错误数据。

优化方式：

- 统计采样和输出分离，采样任务只保存二进制结果。
- 采用 100 ms、500 ms 或 1 s 窗口，按应用实时性选择。
- 通过 DMA、RTT 或后台任务异步输出。
- 只对关键任务和关键 ISR 做高精度统计。
- 采用定点整数输出，避免实时路径浮点格式化。
- 仅在超阈值时保存详细任务列表。

## 7. 应用场景选型指南

### 纯文本决策流程图

```
需要回答什么问题？
├─ 只想知道系统是否接近满载
│  └─ 空闲任务运行时间统计
├─ 需要知道哪个任务消耗 CPU
│  └─ RTOS 任务运行时间统计
├─ 需要知道 ISR 是否占用过多 CPU
│  └─ ISR 入口/出口计时 + 任务运行时间统计
├─ 需要知道为什么任务被延迟或抢占
│  └─ SystemView/Tracealyzer 事件时间线
├─ 需要知道具体代码函数的热点
│  └─ 采样分析、硬件性能计数器或 ETM
├─ 系统存在低功耗睡眠
│  └─ 分别统计 Running、Idle、Sleep、Stop 状态
└─ 多核系统
   └─ 每核独立统计，再计算全局和每核利用率
```

### 典型场景

|需求|推荐方案|理由|
|---|---|---|
|判断是否需要提高 MCU 主频|空闲时间 + 任务运行时间|可以快速估算负载余量|
|定位 CPU 最高任务|`uxTaskGetSystemState()`|直接获得任务级运行时间|
|控制周期超时|任务运行时间 + 调度延迟测量|总 CPU 利用率无法说明单次超时原因|
|高频 ISR 导致任务饥饿|ISR 计时 + SystemView|区分 ISR 占用和任务竞争|
|现场性能退化|周期统计 + 峰值/超阈值计数|低成本长期监控|
|低功耗产品|状态机时间统计|普通 CPU 使用率可能把睡眠误判为空闲|
|多核 SMP|每核独立统计|全局平均值可能掩盖单核过载|

## 8. 工程最佳实践

### 设计原则

1. **CPU 使用率必须带统计窗口和时间基准。**
2. **平均值不能替代峰值和最坏情况分析。**
3. **任务运行时间和 ISR 运行时间要分开统计。**
4. **统计模块不能改变关键实时路径。**
5. **所有统计结果必须标注是否包含 ISR、空闲任务和睡眠时间。**
6. **生产环境优先保存计数和直方图，避免持续输出详细文本。**
7. **CPU 使用率必须与响应时间、截止时间、栈水位和队列深度一起分析。**

### 选型决策矩阵

|约束|空闲统计|任务运行时间|Trace 工具|硬件采样|
|---|---|---|---|---|
|资源开销低|高|中|低到中|中|
|任务级归因|低|高|高|中|
|ISR 分析|低|取决于端口|高|高|
|长期量产运行|高|高|低|中|
|调度根因定位|低|中|高|中|
|代码热点定位|低|低|中|高|
|对时间精度要求高|低|高|高|高|

### 工业级编码规范

- 所有统计变量使用明确的单位后缀，如 `_cycles`、`_ticks`、`_us`、`_x100`。
- 访问跨上下文共享的 64 位变量时，必须保证原子性或使用临界区。
- 统计函数不得隐式执行阻塞 I/O。
- 计时器读取接口应统一封装，禁止应用层直接依赖具体寄存器。
- 统计失败、缓冲区不足和计数器异常必须有显式状态。
- 采样窗口、阈值和事件数量使用配置项，不要散落在业务代码中。
- 任务名、任务句柄和统计项之间建立稳定映射，避免仅依赖数组顺序。

## 9. 常见错误与避坑指南

### 错误一：用空闲循环次数直接当作时间

```
static volatile uint32_t idle_count;

void vApplicationIdleHook(void)
{
    ++idle_count;
}

/* 错误：认为 100000 次循环就等于固定时间 */
uint32_t idle_percent = idle_count / 1000U;
```

**根因**：空闲循环次数受编译器、Flash、cache、中断和统计代码影响，不是稳定时间单位。

**正确实现**：

- 使用硬件自由运行计数器统计空闲任务实际运行时间；或
- 先在固定硬件和固定构建下校准，并明确只能作为相对指标。

**风险影响**：换优化等级、主频或编译器后，CPU 使用率会发生无意义变化。

---

### 错误二：直接使用 32 位乘法计算百分比

```
uint32_t percent =
    task_runtime * 10000U / total_runtime;
```

**根因**：`task_runtime * 10000U` 可能在除法之前溢出。

**正确实现**：

```
uint32_t usage_x100 = 0U;

if (total_runtime != 0U) {
    usage_x100 = (uint32_t)(
        ((uint64_t)task_runtime * 10000ULL) /
        (uint64_t)total_runtime);
}
```

**风险影响**：高运行时间任务可能被报告为低占用，导致错误优化方向。

---

### 错误三：把 RTOS tick 当作高精度运行时间

```
uint32_t start = xTaskGetTickCount();

do_work();

uint32_t elapsed_us =
    (xTaskGetTickCount() - start) * 1000U;
```

**根因**：tick 分辨率受 `configTICK_RATE_HZ` 限制，且短于一个 tick 的执行时间会被量化为 0。

**正确实现**：

```
uint32_t start = platform_cycle_count();

do_work();

uint32_t cycles = platform_cycle_count() - start;
uint32_t elapsed_us =
    cycles_to_microseconds(cycles);
```

**风险影响**：短任务执行时间和周期抖动被严重低估。

---

### 错误四：在统计任务中直接打印完整报告

```
void cpu_stat_task(void *arg)
{
    for (;;) {
        vTaskGetRunTimeStats(text_buffer);
        printf("%s", text_buffer);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
```

**根因**：

- `vTaskGetRunTimeStats()` 的格式化可能使用大量 CPU 和栈；
- `printf` 可能阻塞；
- 输出任务优先级和串口驱动可能改变系统调度。

**正确实现**：

- 先通过 `uxTaskGetSystemState()` 获取结构化数据；
- 只保存二进制统计结果；
- 由低优先级后台任务异步输出；
- 生产环境仅在请求或超阈值时输出。

**风险影响**：统计行为掩盖原始负载问题，甚至制造新的实时性故障。

---

### 错误五：忽略中断时间

```
所有任务 CPU 使用率之和为 75%
因此系统总 CPU 使用率为 75%
```

**根因**：某些任务运行时间统计将 ISR 时间归入被打断任务，另一些端口可能单独记录 ISR，不能直接相加。

**正确实现**：

- 查明 RTOS 端口的统计语义；
- 明确 ISR 是否单独计时；
- 对关键 ISR 增加入口/出口测量；
- 用 SystemView 或硬件测量交叉验证。

**风险影响**：错误估计系统余量，无法解释高优先级任务突然延迟。

---

### 错误六：低功耗后继续用停止的计数器计算 CPU 使用率

```
enter_stop_mode();
/* 计数器停止 */
exit_stop_mode();

uint32_t elapsed = counter_read() - start;
```

**根因**：计数器在 Stop/Sleep 模式停止或切换时钟源，导致统计时间不连续。

**正确实现**：

- 使用始终运行的低功耗定时器；
- 在进入和退出睡眠时记录状态并补偿时间；
- 将 `Run`、`Idle`、`Sleep`、`Stop` 分开统计。

**风险影响**：系统可能被报告为“CPU 长时间空闲”，但实际是进入了低功耗状态，导致功耗和性能结论错误。

## 10. 多机制组合使用方案

推荐的工业级组合：

```
低成本长期统计
    ├─ 空闲/睡眠时间
    ├─ 任务运行时间
    ├─ 关键 ISR 时间
    └─ 最大值、P99、超阈值次数

问题定位模式
    ├─ SystemView/Tracealyzer
    ├─ 任务切换事件
    ├─ 同步对象事件
    └─ 用户业务阶段事件

代码热点模式
    ├─ DWT/硬件性能计数器
    ├─ 周期采样
    └─ ETM 或离线 profiler
```

### 组合代码框架

```
#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t usage_x100;
    uint32_t max_usage_x100;
    uint32_t over_limit_count;
    uint32_t consecutive_over_limit;
} cpu_window_metric_t;

static cpu_window_metric_t g_cpu_metric;
static uint32_t g_prev_total_runtime;
static uint32_t g_prev_idle_runtime;

#define CPU_USAGE_LIMIT_X100 8500U

static void cpu_update_window(uint32_t total_runtime,
                              uint32_t idle_runtime)
{
    const uint32_t total_delta =
        total_runtime - g_prev_total_runtime;
    const uint32_t idle_delta =
        idle_runtime - g_prev_idle_runtime;

    g_prev_total_runtime = total_runtime;
    g_prev_idle_runtime = idle_runtime;

    if (total_delta == 0U || idle_delta > total_delta) {
        return;
    }

    const uint32_t busy_delta = total_delta - idle_delta;
    const uint32_t usage_x100 = (uint32_t)(
        ((uint64_t)busy_delta * 10000ULL) /
        (uint64_t)total_delta);

    g_cpu_metric.usage_x100 = usage_x100;

    if (usage_x100 > g_cpu_metric.max_usage_x100) {
        g_cpu_metric.max_usage_x100 = usage_x100;
    }

    if (usage_x100 > CPU_USAGE_LIMIT_X100) {
        ++g_cpu_metric.over_limit_count;
        ++g_cpu_metric.consecutive_over_limit;
    } else {
        g_cpu_metric.consecutive_over_limit = 0U;
    }

    if (g_cpu_metric.consecutive_over_limit >= 3U) {
        diagnostic_raise(DIAG_CPU_SATURATION);
    }
}
```

该框架需要补充：

- `total_runtime` 的定义；
- 空闲时间是否包括睡眠；
- 多核情况下是否按核统计；
- 计数器回绕；
- 并发读取；
- 指标上报周期；
- 阈值告警去抖。

### 统计任务示例

```
void cpu_monitor_task(void *arg)
{
    (void)arg;

    TickType_t wake_time = xTaskGetTickCount();

    for (;;) {
        vTaskDelayUntil(&wake_time,
                        pdMS_TO_TICKS(CPU_MONITOR_PERIOD_MS));

        uint32_t total_runtime = 0U;
        uint32_t idle_runtime = cpu_read_idle_runtime();

        cpu_read_total_runtime(&total_runtime);

        cpu_update_window(total_runtime, idle_runtime);

        if (g_cpu_metric.consecutive_over_limit >= 3U) {
            cpu_capture_task_snapshot();
            trace_mark_cpu_saturation(g_cpu_metric.usage_x100);
        }
    }
}
```

监控任务本身也会消耗 CPU。其优先级应根据诊断目的配置，通常不应高于实时控制任务。

## 11. 工业级实际案例分析

### 案例一：电机控制任务偶发周期超时

#### 需求

控制任务周期为 1 ms，正常执行时间约 180 微秒，但在通信突发期间偶发超时。

#### 初步错误判断

系统平均 CPU 使用率只有 62%，因此认为 CPU 资源充足。

#### 架构设计

- 任务运行时间统计；
- 控制任务周期开始和结束时间；
- DMA、通信 ISR 入口和出口计时；
- SystemView 记录任务切换和中断事件；
- 保存控制任务最大执行时间和最大调度等待时间。

#### 分析结果模式

```
平均 CPU 使用率：62%
控制任务平均执行时间：180 us
控制任务最大执行时间：220 us
控制任务最大调度等待：680 us
通信 ISR 突发累计占用：420 us
```

根因不是平均 CPU 过高，而是通信 ISR 突发导致控制任务无法及时获得 CPU。

#### 设计要点

- 不能只调整控制任务优先级；
- 需要限制 ISR 单次处理量；
- 将复杂协议解析从 ISR 转移到任务；
- 评估中断优先级和 DMA 批量策略；
- 以最坏响应时间而不是平均 CPU 使用率作为验收指标。

---

### 案例二：网关设备任务级 CPU 泄漏

#### 需求

设备运行数小时后 CPU 使用率逐渐从 35% 上升到 80%。

#### 架构设计

- 每 1 秒采集任务增量运行时间；
- 保存每个任务的 60 个窗口样本；
- 统计任务最大值、平均值和 P99；
- 记录队列深度、连接数、定时器数量和内存余量。

#### 分析方法

若系统总 CPU 增长主要来自网络任务，应进一步对比：

```
连接数 -> 网络任务 CPU
消息数 -> 网络任务 CPU
定时器数量 -> 定时器服务任务 CPU
堆余量 -> CPU 使用率
```

典型根因可能包括：

- 断开连接后仍残留定时器；
- 重试任务进入短周期忙等；
- 队列空轮询没有阻塞；
- 定时器回调执行时间随对象数量线性增长；
- 错误路径持续产生高频日志。

#### 设计要点

必须保存窗口增量，而不是只看累计运行时间。累计值只能说明历史总量，无法定位负载是何时增长的。

---

### 案例三：低功耗传感器节点的 CPU 使用率误判

#### 需求

设备每 10 秒唤醒一次采样，其他时间进入 Stop 模式。传统统计显示 CPU 使用率低于 1%。

#### 问题

低 CPU 使用率并不能说明系统功耗模型正确。CPU 可能处于：

- RTOS Idle；
- WFI Sleep；
- Stop 模式；
- 外部低功耗控制器接管状态。

#### 架构设计

分别累计：

```
ACTIVE_TIME
RTOS_IDLE_TIME
WFI_SLEEP_TIME
STOP_MODE_TIME
WAKEUP_LATENCY
```

#### 设计要点

- 使用始终运行的低功耗计时器；
- 记录进入和退出低功耗模式；
- 分开报告 CPU active ratio 和系统唤醒占比；
- 将唤醒延迟、采样执行时间和功耗作为同一组指标分析。

对于低功耗系统，单一 CPU 使用率指标不应作为系统效率的主要指标。

## 12. 高频问题深度答疑

### Q1：CPU 使用率达到多少才算危险？

没有跨产品通用阈值。通常需要结合实时性裕量、负载波动和系统功能。

例如：

- 周期控制系统可能要求长期平均低于 60%，并保留较大峰值裕量；
- 通信网关可能允许平均 80%，但必须保证高优先级任务截止时间；
- 非实时 UI 或后台设备可能允许更高利用率。

工程上应同时设定：

```
平均使用率阈值
峰值使用率阈值
连续超阈值窗口数
关键任务最大执行时间
关键任务最大调度等待
```

### Q2：任务 CPU 使用率之和为什么不是 100%？

常见原因包括：

1. ISR 时间没有统计到任务；
2. 统计窗口和累计窗口混用；
3. 空闲任务未计入；
4. 任务创建或删除过程中快照不一致；
5. 统计计数器回绕；
6. 多核系统按单核数据和全局数据混算；
7. 统计代码自身未纳入任何任务。

必须先定义统计分母和分类边界，再解释百分比。

### Q3：任务运行时间统计会不会改变调度结果？

会有可能。每次任务切换增加计数器读取、数据更新和临界区操作。影响大小取决于：

- 上下文切换频率；
- 时间戳读取成本；
- 计数器宽度；
- 编译器优化；
- CPU 主频；
- 是否发生缓存或总线竞争。

应测量：

```
无统计：上下文切换耗时
启用统计：上下文切换耗时
差值：统计扰动
```

如果关键周期很短，应采用硬件跟踪或选择性统计。

### Q4：应该使用 RTOS tick 还是 DWT 作为统计时基？

一般判断：

- 只需要低精度长期趋势：RTOS tick 可以使用；
- 需要区分百微秒级任务：使用高分辨率硬件计数器；
- 需要短路径精确分析：DWT 或硬件定时器；
- 需要跨低功耗模式连续计时：使用始终运行的低功耗计数器。

注意：高分辨率不等于高准确性。必须确认时钟频率、回绕、时钟切换和调试状态。

### Q5：空闲任务 CPU 使用率和任务运行时间统计哪个更可靠？

在正确配置下，两者都可以可靠，但适用目的不同。

- 空闲时间统计适合系统级负载；
- 任务运行时间统计适合负载归因；
- 如果 ISR 时间被并入任务，任务级数据需要特别解释；
- 低功耗系统还需要独立统计睡眠状态。

推荐组合使用，而不是二选一。

### Q6：CPU 使用率低，但系统仍然响应慢，为什么？

CPU 使用率是总量指标，不是延迟指标。可能原因包括：

- 高优先级任务被长时间关中断；
- 任务等待互斥锁；
- ISR 优先级配置错误；
- 任务优先级过低；
- 外设响应慢；
- 队列或信号量超时；
- 内存分配或锁竞争；
- 系统进入低功耗后唤醒延迟较大。

应增加：

- 端到端响应时间；
- 调度等待时间；
- 互斥锁等待时间；
- ISR 最大执行时间；
- 关中断最长时间；
- 队列等待时间。

## 13. 课程核心总结

### 核心要点

- CPU 使用率本质上是**时间占比**，必须明确统计窗口和时间基准。
- 空闲统计适合判断总体负载，任务运行时间统计适合定位负载来源。
- ISR 时间、睡眠时间和统计代码开销必须明确归属。
- 平均 CPU 使用率不能替代最坏响应时间、峰值占用和截止时间分析。
- 高精度统计应使用独立硬件计数器，并处理回绕、并发和低功耗时钟问题。

### 性能排序

在一般工程场景下：

```
开销从低到高：
空闲计数器
< 空闲运行时间
< 任务运行时间统计
< 选择性 ISR 统计
< 全量事件跟踪
< 硬件指令级追踪
```

该排序只是常见趋势，具体结果必须通过目标板测量确认。

### 通用选型结论

- **只需要系统负载**：空闲任务运行时间统计。
- **需要任务排名**：RTOS 任务运行时间统计。
- **需要 ISR 分析**：任务统计加 ISR 计时。
- **需要调度根因**：SystemView 或 Tracealyzer。
- **需要函数热点**：硬件采样或性能分析器。
- **需要低功耗评估**：活动、空闲、睡眠和 Stop 状态分开统计。

## 14. 快速参考速查表

### 场景选型表

|场景|首选方法|必须补充|
|---|---|---|
|系统是否接近满载|空闲运行时间|峰值和连续超阈值次数|
|哪个任务占用最高|`uxTaskGetSystemState()`|窗口增量统计|
|控制任务超期|任务运行时间|调度等待、ISR 和截止时间|
|ISR 风暴|ISR 入口/出口计时|中断次数、优先级、最大时长|
|现场性能退化|周期任务统计|队列、连接数和资源指标|
|低功耗系统|状态机时间统计|唤醒延迟和功耗|
|多核系统|每核独立统计|核间迁移和全局负载|

### 特性对比表

|指标|含义|不能单独说明|
|---|---|---|
|平均 CPU 使用率|窗口平均工作时间|是否存在偶发超时|
|峰值 CPU 使用率|观察窗口内最大负载|峰值出现的根因|
|任务运行时间|任务获得 CPU 的时间|任务等待了多久|
|调度等待时间|Ready 到实际运行的延迟|代码本身执行时间|
|ISR 执行时间|中断处理占用|任务级业务负载|
|空闲时间|未执行普通任务的时间|是否处于低功耗|
|P99 使用率|大多数窗口的负载水平|极少数最坏事件|

## 15. 学习效果自检

- 能给出单核 CPU 使用率的时间占比定义。
- 能说明空闲任务统计和任务运行时间统计的差异。
- 能配置 FreeRTOS 运行时间统计，并读取任务运行时间。
- 能正确处理 32 位计数器回绕和 64 位中间乘法。
- 能计算统计计数器频率、分辨率和回绕周期。
- 能区分任务 CPU 时间、ISR 时间、调度等待时间和端到端延迟。
- 能发现 `printf`、忙等、过高统计频率和低功耗计时器停止等问题。
- 能设计平均值、峰值、P99、超阈值次数和连续超阈值窗口指标。
- 能使用 SystemView、GPIO 或硬件计数器验证 CPU 统计结果。
- 能为量产固件设计低开销、可关闭、可追溯的 CPU 监控机制。

## 16. 实践与进阶路径

### 梯度实战任务

1. **任务级统计**  
    在 FreeRTOS 工程中启用 `configGENERATE_RUN_TIME_STATS`，使用 1 MHz 自由运行计数器，输出任务运行时间排名。
    
2. **窗口统计**  
    每 100 ms 保存一次任务运行时间快照，计算窗口 CPU 使用率、峰值和连续超阈值次数。
    
3. **ISR 统计**  
    为 DMA、UART 或定时器 ISR 增加入口/出口计时，记录调用次数、平均执行时间和最大执行时间。
    
4. **忙等问题定位**  
    构造一个错误的轮询任务和一个正确阻塞等待的任务，比较两者对 CPU 使用率和响应时间的影响。
    
5. **实时性联合分析**  
    使用 SystemView 或 Tracealyzer 分析任务 CPU 使用率、调度等待和同步对象阻塞，验证总 CPU 使用率低但任务仍超时的场景。
    
6. **低功耗统计**  
    增加 Active、Idle、Sleep、Stop 四类状态计时，比较普通 CPU 使用率与真实功耗状态的差异。
    

### 性能测试方法

测试时至少记录：

```
CPU 平均使用率
CPU 峰值使用率
P99 使用率
任务运行时间
ISR 总时间
ISR 最大执行时间
最大调度等待
最长关中断时间
统计模块自身开销
任务栈余量
```

采用以下对照组：

```
A：关闭统计
B：只启用空闲统计
C：启用任务运行时间统计
D：启用任务与 ISR 统计
E：启用完整 Trace
```

比较每组的：

- 上下文切换时间；
- 关键任务响应时间；
- 中断延迟；
- CPU 使用率；
- RAM 和 Flash 增量；
- 事件或统计数据完整性。

### 进阶学习方向

- FreeRTOS `tasks.c` 中任务切换和运行时间累计逻辑。
- Cortex-M DWT、SysTick、通用定时器和低功耗定时器。
- SystemView、Tracealyzer 的时间线与任务运行统计。
- 多核 RTOS 中每核利用率、任务迁移和锁竞争。
- CPU 使用率直方图、P99/P999 和最坏执行时间分析。
- ETM、ITM、性能监控单元和硬件采样。
- 面向量产的性能回归、异常触发快照和现场指标压缩。