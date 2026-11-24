
## 1. 学习目标

### 理解

- 理解 RTOS 运行时统计信息的范围：任务状态、任务运行时间、栈余量、堆状态、对象数量、任务切换及运行时计数器。
- 区分**快照型信息**与**累计型信息**，理解二者的采集成本和诊断用途。
- 理解统计结果依赖内核版本、移植层、配置项和采集时机，不能把 API 输出直接当作完整的系统真相。

### 掌握

- 掌握 FreeRTOS 常用运行时信息接口：`uxTaskGetSystemState()`、`uxTaskGetNumberOfTasks()`、`uxTaskGetStackHighWaterMark()`、`vPortGetHeapStats()`。
- 能配置任务运行时间统计，并正确计算采样窗口内的任务 CPU 占用。
- 能解释任务状态、优先级、栈高水位、堆统计和任务运行时间字段。

### 精通

- 能识别统计采集引入的临界区、任务暂停、栈使用和输出开销。
- 能分析统计数据不一致、采集时任务创建/删除竞争、计数器回绕及栈水位低估风险。
- 能设计面向现场诊断的运行时快照、低开销周期统计和异常触发机制。

### 能够设计

- 能设计线程安全、可版本化、单位明确的运行时统计模块。
- 能建立任务、堆、栈、CPU 和系统状态的联合诊断指标。
- 能设计统计接口在发布固件中的启停策略、缓冲区预算和数据完整性机制。

## 2. 前置要求

### 知识要求

- 熟悉 RTOS 任务状态、调度器、抢占、优先级和任务切换。
- 理解任务栈、TCB、堆分配及静态/动态创建任务的区别。
- 理解 FreeRTOS 配置头文件和 `portable` 移植层的职责。
- 熟悉计数器频率、单位换算、整数溢出和并发访问。

### 技能要求

- 能修改并验证 `FreeRTOSConfig.h`。
- 能阅读 FreeRTOS API 文档、内核源码和目标移植层。
- 能检查 map 文件、任务栈配置和堆实现。
- 能在调试器、串口、RTT 或文件中采集结构化数据。
- 能通过压力测试验证栈、堆和统计功能。

## 3. 技术概述

**RTOS 运行时统计信息**是系统运行过程中可查询的状态与累计指标，用于回答：

- 当前有哪些任务，各自处于什么状态？
- 任务运行了多久，占用多少 CPU？
- 哪些任务栈余量不足？
- 堆还剩多少空间，最大连续块有多大？
- 任务是否持续阻塞、频繁切换或长期处于 Ready？
- 系统是否发生过内存分配失败、栈溢出或任务创建失败？

常见统计类别：

|类别|代表数据|主要用途|
|---|---|---|
|任务快照|名称、状态、优先级、任务号、栈高水位|现场状态与任务管理|
|运行时间|任务累计运行计数、窗口 CPU 占比|CPU 归因与负载趋势|
|栈统计|栈高水位、配置深度、溢出钩子|栈容量验证|
|堆统计|空闲字节、最小剩余量、最大块、分配失败|内存预算与碎片分析|
|调度统计|任务切换次数、tick、调度器状态|系统活动和异常辅助分析|
|应用统计|队列高水位、超时数、错误计数|业务状态与内核数据关联|

需区分三种时间尺度：

- **瞬时状态**：一次查询时的任务状态和堆剩余量。
- **累计统计**：从启动或复位后累计的任务运行计数、分配失败次数。
- **窗口统计**：两次快照之间的差值，适合性能趋势和负载分析。

## 4. 核心特性横向对比

|机制|数据类型|精度/时效|开销|主要限制|
|---|---|---|---|---|
|`uxTaskGetSystemState()`|多任务快照|查询时点|与任务数相关|需要调用方提供数组；配置要求依版本而定|
|`vTaskList()`|格式化任务文本|查询时点|格式化开销较高|占栈和代码空间，不适合高频实时路径|
|`vTaskGetRunTimeStats()`|格式化累计运行时间|累计值|查询和格式化开销|输出单位及精度依赖运行时间计数器|
|`uxTaskGetStackHighWaterMark()`|单任务栈余量|历史最低余量|较低|是高水位估计，不是静态证明|
|`vPortGetHeapStats()`|FreeRTOS 堆状态|查询时点/历史最小值|堆实现相关|只有支持的 heap 实现才提供对应统计|
|Tracealyzer/SystemView|事件时间线|高时间分辨率|低到高，依配置而定|依赖目标端 Recorder、事件和传输配置|
|应用自建快照|项目定制字段|可控|可控|需自行处理一致性、单位和版本|

**格式化 API 适合人工调试，不适合高频实时采集。** 生产统计通常先采集结构化数据，再由低优先级后台路径异步编码输出。

## 5. 底层原理与功能特性深度解析

### 5.1 任务状态快照

FreeRTOS 中常见任务状态包括：

- `eRunning`：当前正在执行的任务。
- `eReady`：可运行，等待 CPU。
- `eBlocked`：等待延时、队列、信号量或事件。
- `eSuspended`：显式挂起，不参与正常调度。
- `eDeleted`：删除过程中的状态；通常不应把它当作稳定快照状态。

`uxTaskGetSystemState()` 返回一组 `TaskStatus_t` 数据。调用时需要预先提供容量足够的数组，具体配置要求应以目标 FreeRTOS 版本为准。

```
#include "FreeRTOS.h"
#include "task.h"

#define DIAG_MAX_TASKS 32U

static TaskStatus_t g_task_snapshot[DIAG_MAX_TASKS];

static UBaseType_t collect_task_snapshot(uint32_t *total_runtime)
{
    if (total_runtime == NULL) {
        return 0U;
    }

    *total_runtime = 0U;

    return uxTaskGetSystemState(g_task_snapshot,
                                DIAG_MAX_TASKS,
                                total_runtime);
}
```

工程上应处理任务数量超过数组容量的情况。不能假设系统任务数量永远不变，尤其是支持动态创建和删除任务的系统。

推荐先检查任务数量，再确认缓冲区容量：

```
static bool task_snapshot_capacity_ok(void)
{
    const UBaseType_t task_count = uxTaskGetNumberOfTasks();

    return task_count <= DIAG_MAX_TASKS;
}
```

如果任务创建与采集可能并发发生，应由系统约束保证快照容量足够，或采用更大容量和失败计数；不要在高优先级路径中循环扩容或动态分配。

### 5.2 任务运行时间统计

FreeRTOS 可通过运行时间计数器为任务累计运行时间。典型配置包括：

```
#define configGENERATE_RUN_TIME_STATS 1
#define configUSE_TRACE_FACILITY      1

#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS() \
    platform_runtime_timer_init()

#define portGET_RUN_TIME_COUNTER_VALUE() \
    platform_runtime_timer_get()
```

宏定义及相关依赖可能随 FreeRTOS 版本、芯片支持包和移植层而不同。应检查当前版本的 `FreeRTOSConfig.h`、`portmacro.h`、内核源码及官方示例。

运行时间计数器应满足：

- 具有明确频率和单位；
- 分辨率适合目标任务的执行时间；
- 与 RTOS tick 解耦，避免低分辨率；
- 访问速度足够快，不显著增加任务切换开销；
- 回绕周期满足统计采样和累计宽度要求；
- 低功耗时钟行为有明确约定。

### 5.3 任务运行时间快照与窗口占比

累计运行时间反映任务从统计起点开始获得 CPU 的总量。窗口占比应基于两次快照的差值计算。

```
#include <stdint.h>

typedef struct {
    uint32_t previous_task_runtime;
    uint32_t previous_total_runtime;
    bool initialized;
} runtime_window_state_t;

typedef struct {
    uint32_t task_runtime_delta;
    uint32_t total_runtime_delta;
    uint32_t cpu_percent_x100;
} runtime_window_result_t;

static runtime_window_result_t calculate_runtime_window(
    runtime_window_state_t *state,
    uint32_t task_runtime,
    uint32_t total_runtime)
{
    runtime_window_result_t result = {0};

    if (state == NULL) {
        return result;
    }

    if (!state->initialized) {
        state->previous_task_runtime = task_runtime;
        state->previous_total_runtime = total_runtime;
        state->initialized = true;
        return result;
    }

    /*
     * 32 位无符号差值可处理一次回绕；
     * 采样间隔必须短于计数器完整回绕周期。
     */
    result.task_runtime_delta =
        task_runtime - state->previous_task_runtime;
    result.total_runtime_delta =
        total_runtime - state->previous_total_runtime;

    state->previous_task_runtime = task_runtime;
    state->previous_total_runtime = total_runtime;

    if (result.total_runtime_delta != 0U) {
        result.cpu_percent_x100 = (uint32_t)(
            ((uint64_t)result.task_runtime_delta * 10000ULL) /
            result.total_runtime_delta);
    }

    return result;
}
```

该计算示例假设 `total_runtime` 与任务运行时间处于同一计数单位和统计域。若总计数只表示任务运行时间而不包括 ISR，或包含空闲时间，解释方式就不同，需先确认端口实现。

### 5.4 任务栈高水位

FreeRTOS 的 `uxTaskGetStackHighWaterMark()` 返回任务运行以来最少剩余栈空间的估计值。返回单位可能是 `StackType_t` 元素，而不是字节。必须换算：

```
static size_t task_stack_high_water_bytes(TaskHandle_t task)
{
    const UBaseType_t words = uxTaskGetStackHighWaterMark(task);

    return (size_t)words * sizeof(StackType_t);
}
```

注意：

- 这是**历史最低余量**，不是当前 SP 与栈底的精确实时距离。
- 依赖 RTOS 对未使用栈区域进行填充值初始化，并通过扫描估算剩余量。
- 未执行过的最坏路径不会体现在高水位中。
- 递归、异常路径、浮点上下文保存和中断栈使用可能导致低估风险。
- 在 Cortex-M 上，异常处理通常使用 MSP，任务可能使用 PSP；任务栈统计不一定包含 ISR 栈空间。

建议结合静态栈分析、压力测试、栈溢出钩子和安全余量配置。

### 5.5 堆统计

`vPortGetHeapStats()` 等接口的可用性取决于所用 FreeRTOS heap 实现和版本。常见堆指标包括：

- 当前空闲字节数；
- 历史最小空闲字节数；
- 最大空闲块；
- 空闲块数量；
- 最小/最大块大小；
- 分配和释放次数。

**总空闲量不等于可满足最大分配请求的连续空间。** 例如，空闲总量为 20 KB，但最大连续块只有 2 KB，则 4 KB 的分配仍可能失败。

应将下列数据联合观察：

```
free_bytes
minimum_ever_free_bytes
largest_free_block
free_block_count
allocation_failure_count
```

这些字段的具体含义随 `heap_1` 到 `heap_5` 等实现不同而变化。使用前必须阅读目标 `heap_x.c` 的实现，不能假定各实现提供同样的碎片信息。

### 5.6 采集一致性与并发

运行时快照往往跨多个任务、内核对象和堆结构读取。采集期间如果任务正在创建、删除或修改对象，可能出现：

- 任务数量变化；
- 快照中对象状态与关联数据不一致；
- 堆统计反映不同时间点；
- 任务句柄已经失效；
- 对象名称或状态在输出前改变。

工程处理方式：

1. 使用 RTOS 提供的快照 API，避免自行遍历 TCB 或堆结构。
2. 控制采集频率，不在关键路径采集。
3. 采集后立即复制必要字段，避免保存长期有效性未知的内部指针。
4. 对动态任务创建/删除建立诊断锁或事件化记录。
5. 将快照标注时间戳和版本，允许分析端识别非原子采集。

### 5.7 结构化输出与稳定接口

不要直接导出内核内部结构体原始内存。内核结构会随版本、编译器和配置变化。定义稳定的项目级快照：

```
#define DIAG_TASK_NAME_LENGTH 16U

typedef struct {
    char name[DIAG_TASK_NAME_LENGTH];
    uint32_t task_id;
    uint32_t runtime_counter;
    uint32_t stack_high_water_bytes;
    uint8_t priority;
    uint8_t state;
} diag_task_record_t;
```

字段单位、枚举值和结构版本应固定；传输时建议使用显式编码，不要依赖编译器结构体填充。

## 6. 性能量化分析

### 6.1 采集开销来源

- RTOS 查询 API 的内核锁或临界区时间；
- 遍历任务和对象的 CPU 时间；
- 运行时间计数器读取和累计；
- 结构化复制和字符串处理；
- 输出编码、串口或 RTT 传输；
- 统计任务本身的栈和 CPU 占用。

### 6.2 时间复杂度

典型复杂度：

- `uxTaskGetNumberOfTasks()`：实现通常为常量级或轻量读取，仍应以实际版本为准。
- `uxTaskGetSystemState()`：大致随任务数线性增长，约为 `O(N_tasks)`。
- 任务名复制：与任务数乘以名称最大长度相关。
- 堆块遍历统计：依具体 heap 实现而定，可能与空闲块数成正比。
- 文本格式化：通常比结构化复制更昂贵，成本受字段数和格式化库影响。

### 6.3 数据量与缓冲区估算

若每任务记录为 `R` 字节，任务数量为 `N`，快照头部为 `H`：

```
单次快照大小 ≈ H + N × R
```

例如，假设每条任务记录为 **40 字节**，系统有 **24 个任务**，头部为 **32 字节**：

```
快照大小 ≈ 32 + 24 × 40
         = 992 字节
```

这是数据格式估算示例，不是 FreeRTOS 结构体的固定大小。实际大小应通过项目格式和编译器 map 确认。

### 6.4 运行时间计数器分辨率与回绕

若 32 位计数器频率为 `f`：

```
回绕时间 = 2^32 / f
分辨率 = 1 / f
```

示例：

- 1 MHz：分辨率 1 微秒，约 71.6 分钟回绕。
- 10 MHz：分辨率 0.1 微秒，约 7.16 分钟回绕。
- 100 MHz：分辨率 10 纳秒，约 42.9 秒回绕。

高频计数器回绕更快。运行时间统计应使用可靠的增量差值，或扩展为 64 位计数，但 64 位访问在 32 位 MCU 上可能需要临界区或一致性读取。

### 6.5 实测方法与示例指标

以下为**测试方法示例，不是跨平台基准值**：

1. 在目标 MCU 上重复采集 1、8、16、32 个任务的快照。
2. 用 DWT 或定时器测量 API 调用时间。
3. 对照启用/关闭运行时间统计测上下文切换周期。
4. 检查任务栈高水位查询和堆统计的最大执行时间。
5. 在最坏负载和动态任务创建场景下确认结果完整性。

建议报告：

|指标|记录内容|
|---|---|
|任务快照耗时|最小、平均、P99、最大值|
|统计任务 CPU 占比|实测值及采样周期|
|静态 RAM 增量|map 文件差值|
|最大输出带宽|字节/秒及是否丢数据|
|API 临界区时间|最大关中断或调度锁定时间|
|栈余量|高水位、测试覆盖范围、安全余量|
|堆健康度|当前空闲、历史最小、最大连续块|

统计任务若每 `T` 秒运行一次，单次耗时为 `C`，其平均 CPU 占比近似为：

```
U = C / T × 100%
```

例如，实测单次快照 2 ms，采样周期 1 s，则平均占用约 0.2%。但还应检查单次 2 ms 是否造成不允许的调度延迟。

## 7. 应用场景选型指南

### 纯文本决策流程图

```
要诊断什么？
├─ 当前任务状态和优先级
│  └─ 低频 uxTaskGetSystemState() 快照
├─ 哪个任务占用 CPU
│  └─ 运行时间计数器 + 窗口差值
├─ 栈是否不足
│  └─ 高水位统计 + 栈溢出钩子 + 压力测试
├─ 堆是否耗尽或碎片化
│  └─ heap 统计 + 最大连续块 + 分配失败计数
├─ 为什么任务卡住或被延迟
│  └─ SystemView/Tracealyzer + 运行时快照
├─ 现场故障后需要保留证据
│  └─ 固定大小二进制快照 + 故障码 + 版本元信息
└─ 需要自动化性能回归
   └─ 结构化周期样本 + 阈值和趋势分析
```

### 典型场景需求—方案—理由

|场景|推荐方案|理由|
|---|---|---|
|任务创建后状态异常|任务快照|获取优先级、状态和任务数量|
|系统 CPU 占用增长|窗口运行时间增量|能比较不同时间段和任务占用|
|偶发栈溢出|栈高水位 + 溢出钩子 + 现场快照|高水位提供余量，钩子捕捉越界|
|动态分配失败|堆统计 + 分配失败计数|区分总量不足与连续块不足|
|看门狗复位|故障前快照和复位原因|保留最后状态，便于启动后分析|
|任务长期 Ready|快照配合调度 Trace|统计状态说明现象，时间线帮助找原因|
|产品现场低成本监控|限频结构化统计|避免持续格式化输出和高频追踪|

## 8. 工程最佳实践

### 设计原则

- **单位明确**：变量名中标注 `_bytes`、`_words`、`_ticks`、`_cycles`、`_us`。
- **累计与窗口分开**：累计计数保留总量，窗口差值用于实时负载分析。
- **采集与输出分离**：高优先级路径只采集，后台路径编码和发送。
- **数据带上下文**：记录固件版本、内核版本、构建配置、时钟频率和采集时间。
- **避免依赖内部布局**：不输出原始 TCB 或堆内部结构。
- **对失败显式计数**：缓冲区不足、任务数超限、采集失败和传输丢失都要可见。
- **按目标版本验证**：FreeRTOS API、配置依赖和 heap 统计字段可能随版本变化。

### 选型决策矩阵

|目标|推荐机制|采集频率|
|---|---|---|
|现场快速查看任务状态|任务快照 API|手动或异常时|
|CPU 负载排名|运行时间累计值的窗口差分|100 ms 到数秒|
|栈安全性|高水位周期检查|启动验证和低频巡检|
|堆碎片趋势|堆统计和分配失败计数|低频|
|任务调度根因|Trace 工具|问题定位时|
|安全关键现场诊断|固定格式快照、校验和、版本字段|触发式|

### 工业级编码规范

- 统计接口必须有最大任务数和输出缓冲区上限。
- 任务名称需要定长复制并确保终止符。
- API 返回值、任务数量和堆统计结果必须检查。
- 统计任务优先级应低于实时控制任务，且不得持续忙等。
- 数据格式带 schema 版本，枚举值和单位不随意修改。
- 处理任务删除、重建和句柄重用，不能仅凭句柄长期关联历史统计。
- 通过配置控制统计功能，不让发布构建意外引入高开销格式化路径。

## 9. 常见错误与避坑指南

### 错误一：假定任务快照数组永远足够

```
TaskStatus_t status[16];

uxTaskGetSystemState(status, 16U, &total_runtime);
/* 错误：没有检查实际任务数量和返回数量 */
```

**根因**：产品后续可能增加软件定时器任务、诊断任务或动态工作任务。

**正确实现**：

- 检查当前任务数量；
- 对超容量显式返回错误并计数；
- 根据系统最大任务数静态确定容量；
- 不在实时路径动态分配快照数组。

**风险影响**：任务数据不完整，或调用不满足内核 API 的容量要求。

### 错误二：把栈高水位的返回值当成字节

```
uint32_t remaining_bytes =
    uxTaskGetStackHighWaterMark(task); /* 单位可能不是字节 */
```

**根因**：FreeRTOS API 的单位通常是 `StackType_t` 元素，具体声明及单位应核对当前版本。

**正确实现**：

```
size_t remaining_bytes =
    (size_t)uxTaskGetStackHighWaterMark(task) *
    sizeof(StackType_t);
```

**风险影响**：报告错误的栈余量，可能导致栈配置不足或无谓浪费 RAM。

### 错误三：将累计运行时间当作当前 CPU 占用率

```
uint32_t percent =
    task_runtime * 100U / total_runtime;
```

**根因**：两个累计值可能从启动开始增长，不能直接代表最近一个统计窗口；乘法还可能溢出。

**正确实现**：

- 两次采样分别保存任务运行时间和总运行时间；
- 使用差值计算窗口占比；
- 使用 64 位中间乘法；
- 确保分子和分母统计域一致。

**风险影响**：负载趋势判断错误，可能漏掉近期 CPU 饱和。

### 错误四：在高优先级任务中调用文本格式化统计接口

```
void control_task(void *arg)
{
    vTaskGetRunTimeStats(report_buffer);
    uart_send(report_buffer, strlen(report_buffer));
}
```

**根因**：格式化和串口传输可能耗时、阻塞并占用大量栈。

**正确实现**：

- 高优先级任务只更新必要计数；
- 低优先级统计任务采集结构化结果；
- 独立传输任务异步输出；
- 只在请求或异常触发时生成文本报告。

**风险影响**：改变任务调度和控制周期，甚至制造本来不存在的超时。

### 错误五：只看堆空闲总量

```
Free heap = 12 KB，因此 8 KB 分配一定成功。
```

**根因**：堆可能碎片化，最大连续块小于总空闲量。

**正确实现**：

- 同时记录总空闲字节和最大空闲块；
- 检查当前 heap 实现是否支持这些字段；
- 统计分配失败次数和分配尺寸分布；
- 对关键缓冲区优先静态分配或使用内存池。

**风险影响**：现场出现分配失败，却误判为系统堆总量充足。

### 错误六：认为栈高水位证明不会溢出

```
压力测试后还剩 128 字节，因此栈配置安全。
```

**根因**：高水位只反映已执行路径，异常路径、递归、浮点上下文和深层调用可能尚未覆盖。

**正确实现**：

- 覆盖最坏调用路径和故障处理路径；
- 配置栈溢出钩子；
- 采用静态栈分析、压力测试和安全余量；
- 分开评估任务栈与中断栈。

**风险影响**：特定输入或中断嵌套下栈溢出，造成状态破坏或复位。

## 10. 多机制组合使用方案

推荐将运行时信息按成本分层：

```
常驻低开销层
├─ 内存分配失败计数
├─ 关键任务栈低水位
├─ 最大队列深度
└─ 任务运行时间窗口统计

异常快照层
├─ 任务状态和优先级
├─ 堆空闲量与最大连续块
├─ 看门狗/断言/故障码
└─ 时间戳、固件版本和校验和

开发分析层
├─ SystemView/Tracealyzer
├─ 任务切换和 ISR 时间线
├─ 同步对象事件
└─ 用户业务事件
```

### 结构化快照框架

```
#define DIAG_MAX_TASKS 32U
#define DIAG_SCHEMA_VERSION 1U

typedef struct {
    uint32_t schema_version;
    uint32_t timestamp;
    uint32_t firmware_id;
    uint16_t task_count;
    uint16_t flags;
    uint32_t heap_free_bytes;
    uint32_t heap_min_free_bytes;
    diag_task_record_t tasks[DIAG_MAX_TASKS];
} diag_runtime_snapshot_t;

static bool diag_capture_runtime_snapshot(
    diag_runtime_snapshot_t *snapshot)
{
    if (snapshot == NULL) {
        return false;
    }

    snapshot->schema_version = DIAG_SCHEMA_VERSION;
    snapshot->timestamp = platform_monotonic_time();
    snapshot->firmware_id = platform_firmware_id();
    snapshot->task_count = 0U;
    snapshot->flags = 0U;

    if (!task_snapshot_capacity_ok()) {
        snapshot->flags |= DIAG_FLAG_TASK_CAPACITY_EXCEEDED;
        return false;
    }

    uint32_t total_runtime = 0U;
    const UBaseType_t count = uxTaskGetSystemState(
        g_task_snapshot,
        DIAG_MAX_TASKS,
        &total_runtime);

    if (count > DIAG_MAX_TASKS) {
        snapshot->flags |= DIAG_FLAG_TASK_SNAPSHOT_INVALID;
        return false;
    }

    snapshot->task_count = (uint16_t)count;

    for (UBaseType_t i = 0U; i < count; ++i) {
        diag_copy_task_record(&snapshot->tasks[i],
                              &g_task_snapshot[i]);
    }

    diag_read_heap_metrics(&snapshot->heap_free_bytes,
                           &snapshot->heap_min_free_bytes);

    snapshot->flags |= DIAG_FLAG_VALID;
    return true;
}
```

需要根据项目实际实现 `diag_copy_task_record()` 和 `diag_read_heap_metrics()`。快照采集完成后，应复制到固定缓冲区或队列，再由低优先级路径传输。若目标端 RAM 紧张，可只保留异常发生前后的环形快照索引和关键字段。

### 组合设计要点

- **任务快照提供状态，窗口运行时间提供负载，Trace 提供时序因果。**
- **栈高水位是长期安全指标，Trace 栈采样不是替代品。**
- **堆统计是容量视图，分配失败事件是故障证据。**
- **看门狗复位信息应与最后一份有效快照关联。**
- 统计结果必须标记采集成功、部分数据和数据丢失状态。

## 11. 工业级实际案例分析

以下是典型工程案例模式，不对应特定厂商产品。

### 案例一：周期任务偶发超时

**需求**：控制任务偶发错过周期，平均 CPU 使用率正常。

**架构设计**

- 每周期记录控制任务执行时间和调度等待时间。
- 每 500 ms 采集任务运行时间窗口。
- 关键 ISR 记录调用次数和最大执行时间。
- 超时触发时保存任务状态、队列水位和 Trace 标记。

**核心代码思路**

```
const uint32_t release_time = platform_cycle_count();

wait_for_control_release();

const uint32_t start_time = platform_cycle_count();
control_step();
const uint32_t end_time = platform_cycle_count();

record_control_latency(start_time - release_time);
record_control_runtime(end_time - start_time);
```

**设计要点**

- 统计任务运行时间不能说明任务何时变为 Ready；
- 必须区分释放到开始的调度延迟，以及开始到结束的执行时间；
- 对 ISR 风暴和长临界区要用 Trace 或硬件时序交叉验证。

### 案例二：运行数小时后任务数量和堆异常

**需求**：设备长期运行后偶发任务创建失败，堆总空闲量看似尚可。

**架构设计**

- 定时保存当前任务数、堆空闲量、最小空闲量和最大连续块。
- 对任务创建/删除和动态内存分配记录调用来源 ID。
- 任务创建失败时保存异常快照。
- 使用固定大小记录缓冲区，避免诊断路径再次动态分配。

**分析结果模式**

```
堆空闲总量：持续下降
最大连续块：下降更快
分配失败：集中发生在较大缓冲区请求
任务数：周期性增加，未回落
```

**设计要点**

- 总空闲量不能解释连续块不足；
- 应检查任务删除、定时器释放和异步回调生命周期；
- 高频、固定尺寸对象优先使用内存池；
- 记录器本身不能通过同一动态堆分配关键缓冲区。

### 案例三：现场栈溢出后无法复现

**需求**：偶发栈溢出造成看门狗复位，开发环境长期测试未复现。

**架构设计**

- 任务栈高水位低频巡检并保存历史最小值。
- 启用栈溢出检测钩子。
- 故障路径保存任务 ID、当前任务名、异常码和栈指针。
- 任务列表和栈信息使用静态缓冲区，复位后再导出。
- 通过压力测试覆盖异常输入、最大中断嵌套和错误路径。

**设计要点**

- 栈溢出时当前任务上下文可能已损坏，钩子中只能做最小操作；
- 不应在故障钩子中格式化长字符串或发送阻塞串口；
- 高水位不能覆盖未执行路径，必须保留静态分析与余量；
- 还需确认 MCU 的 MSP、PSP 和异常栈使用模型。

## 12. 高频问题深度答疑

### Q1：`vTaskList()` 和 `uxTaskGetSystemState()` 应该选哪个？

需要人工快速查看时，`vTaskList()` 方便，但它输出格式化文本，开销和栈使用较高。自动化采集、低开销和版本化数据应使用结构化接口，例如 `uxTaskGetSystemState()`，再转换为项目定义的格式。

### Q2：任务运行时间统计是否包含 ISR？

没有统一答案，取决于 RTOS 端口和统计实现。有的实现把 ISR 执行时间归入当前被中断任务，有的可以单独统计 ISR。必须查阅移植层实现并用硬件测量验证，不能把任务百分比直接相加后假定等于 100%。

### Q3：为什么任务状态快照的 CPU 总和不等于 100%？

常见原因有：

- ISR 时间没有归入任务或被单独统计；
- 任务和总时间采样窗口不一致；
- 快照期间有任务创建/删除；
- 计数器回绕或单位不一致；
- 当前运行时间统计只包含调度器运行时间；
- 任务快照不包含空闲任务或其他系统上下文。

先确认分母定义和统计边界，再讨论偏差。

### Q4：栈高水位多久采集一次？

高水位是历史最低值，采样太频繁通常不会带来更多信息。可在启动后、长时间压力测试期间低频采集，并在关键事件时记录。周期根据系统变化速率和诊断预算决定；真正的栈安全验证还需要覆盖最坏调用路径和异常路径。

### Q5：FreeRTOS 堆统计能判断内存泄漏吗？

单次堆统计不能。要判断泄漏，应观察长时间趋势，并关联分配/释放数量、对象生命周期和最大连续块变化。`minimum_ever_free_bytes` 只能指出历史最低剩余量，不提供泄漏对象的来源。

### Q6：动态任务创建和删除会影响运行时统计吗？

会影响快照容量、任务句柄稳定性和任务名称生命周期。运行时采集应处理任务数变化，避免长期保存已删除任务的句柄。项目最好统一任务创建/删除入口，并记录稳定任务 ID，而不是只依赖名称或数组下标。

## 13. 课程核心总结

- 运行时统计不仅是 CPU 百分比，还包括任务状态、运行时间、栈余量、堆状态和应用指标。
- **累计值用于历史总量，窗口差值用于当前负载趋势，快照用于故障时状态。**
- 任务快照、运行时间、栈和堆 API 的行为受 FreeRTOS 版本、移植层和堆实现影响。
- 运行时统计必须明确单位、采集窗口、统计边界和失败状态。
- 格式化输出应与实时采集路径分离。
- 任务统计解释“是什么”，Trace 时间线帮助解释“为什么”。
- 堆空闲总量不等于最大连续分配能力；栈高水位不等于最坏情况证明。

## 14. 快速参考速查表

### 场景选型表

|需要的信息|常用机制|注意事项|
|---|---|---|
|当前任务列表|`uxTaskGetSystemState()`|检查任务数组容量|
|人工任务列表|`vTaskList()`|低频使用，格式化开销较高|
|任务 CPU 占比|运行时间统计 + 两次快照差值|分子、分母单位和统计域必须一致|
|栈剩余量|`uxTaskGetStackHighWaterMark()`|换算 `StackType_t` 单位|
|堆剩余量|heap 实现提供的统计接口|检查最大连续块和失败计数|
|任务阻塞根因|SystemView/Tracealyzer|需要正确事件和时间基准|
|故障现场|固定大小运行时快照|需加版本、时间戳和有效标志|

### 特性对比表

|指标|快照/累计性质|适合用途|主要局限|
|---|---|---|---|
|任务状态|瞬时快照|现场状态检查|快照本身不说明状态持续多久|
|任务运行计数|累计值|CPU 归因|需转为窗口差值|
|栈高水位|历史极值|栈余量评估|依赖测试路径覆盖|
|堆当前空闲|瞬时快照|资源余量|不代表最大连续块|
|堆历史最小值|累计极值|最坏资源余量|不提供发生时间|
|Trace 事件|时间序列|调度因果分析|有采集开销和数据完整性要求|

## 15. 学习效果自检

- 能解释瞬时快照、累计值和窗口差值的区别。
- 能说明任务状态、任务运行时间、栈高水位和堆统计的用途。
- 能检查 `uxTaskGetSystemState()` 的容量和返回值。
- 能将栈高水位从 `StackType_t` 单位换算为字节。
- 能用两次运行时间快照计算窗口 CPU 占比，并处理回绕和整数溢出。
- 能解释 ISR 时间是否计入任务运行时间需要查端口实现。
- 能区分堆总空闲量和最大连续空闲块。
- 能把采集、格式化和传输分离。
- 能为运行时快照定义版本、单位、时间戳和错误标志。
- 能通过压力测试验证栈余量、堆趋势和统计模块开销。

## 16. 实践与进阶路径

### 梯度实战任务

1. **任务状态快照**  
    在 FreeRTOS 工程中启用所需配置，获取任务名称、状态、优先级和任务数量，处理缓冲区容量不足。
    
2. **结构化导出**  
    建立项目级任务记录结构，复制字段并输出为定长二进制数据；加入 schema 版本和时间戳。
    
3. **运行时间窗口统计**  
    配置硬件自由运行计数器，每 500 ms 采集任务运行计数，计算窗口占比和最大值。
    
4. **栈余量验证**  
    对所有任务采集高水位，构造最坏输入、错误路径和最大调用深度，统计最低剩余栈空间。
    
5. **堆趋势监控**  
    长时间运行并定期记录空闲量、历史最小值、最大连续块和分配失败次数；测试任务创建/删除和大块分配。
    
6. **故障快照**  
    在看门狗、断言或超时触发时保存固定大小快照，复位后导出并验证校验和、版本和有效标志。
    

### 性能测试方法

- 用 DWT 或硬件定时器测量各统计 API 的最小、平均、P99 和最大执行时间。
- 比较关闭统计、启用运行时间统计、启用任务快照和启用文本输出的 CPU 占用。
- 检查统计任务栈余量，特别是格式化和编码路径。
- 在动态任务创建/删除期间持续采集，检查快照完整性和句柄生命周期。
- 在计数器接近回绕、系统进入低功耗和调度器暂停场景中验证行为。
- 用 SystemView 或 Tracealyzer 检查采集 API 是否产生明显调度延迟或过长临界区。

### 进阶学习方向

- FreeRTOS `tasks.c` 中任务状态快照与运行时间累计逻辑。
- `heap_1` 至 `heap_5` 的分配策略和统计差异。
- Cortex-M MSP、PSP、异常入栈和中断栈预算。
- 统计数据的环形缓存、版本化协议和故障后持久化。
- 多核 RTOS 中每核任务统计、任务迁移和全局快照一致性。
- 运行时统计与 SystemView、Tracealyzer、看门狗和性能回归测试的协同设计。