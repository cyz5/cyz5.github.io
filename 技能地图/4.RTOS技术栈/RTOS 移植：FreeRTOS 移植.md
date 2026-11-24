
> 本课以 **FreeRTOS-Kernel V10/V11 风格、Cortex-M4F、GCC、单核 MCU** 为主线。具体移植必须以目标内核版本、芯片手册、编译器 ABI 和官方 `portable` 实现为准。代码示例用于说明移植边界；**异常入口、上下文帧和 FPU 处理不能脱离目标内核版本直接复制到产品中**。

## 1. 学习目标

- **理解**：说清 FreeRTOS 内核与硬件端口层的职责边界；理解上下文切换、异常优先级、Tick、中断屏蔽、堆实现之间的关系。
- **掌握**：能从目标芯片、编译器和内核版本中选择匹配的 port；能配置时钟、异常入口、优先级位数、堆和断言；能构建最小任务并验证切换。
- **精通**：能通过反汇编、寄存器快照和 GPIO 时序定位启动失败、异常返回错误、FPU 上下文损坏、优先级配置错误及 Tick 抖动。
- **能够设计**：能定义可复现的移植验收标准，设计中断与临界区策略，并评估实时性、栈水位和 RAM 预算。

## 2. 前置要求

### 知识要求

- Cortex-M 异常模型：向量表、MSP/PSP、异常入栈、异常返回值 `EXC_RETURN`、NVIC 优先级。
- C 运行时启动流程：向量表、`Reset_Handler`、`.data/.bss` 初始化、C 运行库入口。
- 编译器与 ABI：函数调用约定、栈对齐、FPU ABI、链接脚本。
- RTOS 基础：任务状态、调度器、时间片、临界区、中断安全 API。

### 技能要求

- 能查看 ELF 符号、map 文件和反汇编。
- 能读芯片参考手册并确认时钟树、NVIC 优先级位数和向量表布局。
- 能使用硬件断点、数据观察点、GPIO 示波或逻辑分析仪。
- 能检查实际编译参数，尤其是优化等级、FPU 选项和 ABI。

## 3. 技术概述

FreeRTOS 移植不是“把内核编译过”就算完成。移植的核心是为目标处理器与编译器提供一组契约，使内核能够：

1. 初始化第一个任务的栈帧。
2. 启动调度器并切换到任务上下文。
3. 保存和恢复任务上下文。
4. 产生系统 Tick 并触发调度。
5. 从中断安全地请求调度。
6. 正确屏蔽和恢复中断，满足内核临界区语义。

典型内核结构：

```
应用层
  ├── 任务、队列、信号量、软件定时器
  └── FreeRTOS API
内核通用层
  ├── tasks.c、queue.c、list.c、timers.c
  └── 调度与对象管理
硬件端口层 portable/<compiler>/<architecture>
  ├── port.c
  ├── portmacro.h
  └── portASM.S（部分端口）
芯片支持层
  ├── 启动文件、时钟、NVIC、外设驱动
  └── FreeRTOSConfig.h、链接脚本、堆策略
```

一个可验证的移植结果至少应证明：调度器能启动、任务能持续切换、临界区符合预期、中断 API 使用规则正确、栈与堆边界有监测、故障可诊断。

## 4. 核心特性横向对比

|维度|Cortex-M 非 FPU port|Cortex-M4F/M7 FPU port|RISC-V port|自定义新架构 port|
|---|---|---|---|---|
|上下文切换入口|通常由 PendSV 完成|PendSV，并处理浮点上下文策略|依赖 trap/软件中断实现|需自行定义异常入口|
|任务栈初始帧|软件约定 + 硬件异常帧|还需考虑 FP 状态|依 ABI 保存寄存器|全部需实现|
|调度触发|PendSV|PendSV|软件中断或 trap|自定义|
|临界区实现|常见为 `BASEPRI` 或 `PRIMASK`|同左，需核对优先级语义|常见为中断使能位|自定义|
|中断优先级约束|由 port 与 NVIC 编码共同决定|同左|由平台中断控制器决定|自定义|
|移植风险|中|中至高|中至高|高|
|建议|使用内核随附官方 port|官方 port + FPU ABI 一致性核验|选择内核版本对应的正式 port|仅在无可用 port 且有验证资源时采用|

**优先选择官方 `portable` 目录中与架构、编译器、FPU 配置匹配的端口。** 不要仅凭 MCU 型号相同就复用端口；编译器 ABI、内核版本、浮点选项都会改变上下文契约。

## 5. 底层原理与功能特性深度解析

### 5.1 Cortex-M 上下文切换

以 Cortex-M 为例，任务运行在线程模式，常用 PSP；异常处理通常运行在 Handler 模式并使用 MSP。发生 PendSV 时：

1. 硬件自动将部分通用寄存器、返回地址、状态寄存器等压入当前任务栈。
2. PendSV 汇编入口保存其余软件上下文，例如 `R4-R11`。
3. 调用内核调度逻辑选择下一个任务。
4. 恢复新任务上下文，设置 PSP。
5. 通过异常返回恢复线程模式和任务执行位置。

上下文中的准确寄存器集合由架构、端口实现、编译器 ABI 和 FPU 策略决定。**应阅读所用版本的 `port.c`/汇编实现，而不是根据通用描述自行拼出异常入口。**

可从官方端口定位实现：

```
FreeRTOS-Kernel/
  portable/
    GCC/
      ARM_CM4F/
        port.c
        portmacro.h
```

需要核对的内容：

- 初始任务栈帧构造函数，如 `pxPortInitialiseStack()`。
- 首任务启动入口，如 `vPortSVCHandler()`。
- 上下文切换入口，如 `xPortPendSVHandler()`。
- Tick 处理入口，如 `xPortSysTickHandler()`。
- 临界区实现，如 `vPortEnterCritical()`、`vPortExitCritical()`。
- 编译器约束、栈对齐以及 FPU 状态保存路径。

### 5.2 系统异常向量连接

很多 Cortex-M 工程已经在启动文件中定义 `SVC_Handler`、`PendSV_Handler`、`SysTick_Handler`。若 FreeRTOS port 使用这些名字，应确保向量表最终指向 port 实现。常见方式是启动文件使用弱符号，port 提供强符号覆盖；也可能需要通过 `FreeRTOSConfig.h` 重命名。

```
/* 示例：仅当所用 port 支持这些重命名宏时使用。 */
#define vPortSVCHandler    SVC_Handler
#define xPortPendSVHandler PendSV_Handler
#define xPortSysTickHandler SysTick_Handler
```

**不要同时保留两个强定义，也不要假设弱符号一定按预期覆盖。** 使用 `nm`/map 文件确认向量表解析到的最终符号地址。

### 5.3 启动调度器与时钟配置

SysTick 时钟必须来自已确认的时钟源。常见设置是内核 Tick 频率为 1 kHz，但实际应根据响应时间、Tick 开销和系统时钟设计。

```
#define configCPU_CLOCK_HZ       SystemCoreClock
#define configTICK_RATE_HZ       ((TickType_t)1000)
```

部分 port 在启动时根据 `configCPU_CLOCK_HZ` 配置 SysTick。若系统运行期间改变主频，不能只更新 `SystemCoreClock` 就认为 Tick 自动正确；要确认该 port 是否重配置计数器，以及是否存在 Tick 丢失或周期突变。

### 5.4 NVIC 优先级与临界区

对使用 `BASEPRI` 屏蔽中断的 Cortex-M port，存在一个关键边界：**优先级高于内核可屏蔽阈值的中断通常仍可执行，但不能调用 FreeRTOS API。** 可调用 `FromISR` API 的中断必须处于允许的优先级范围内。

Cortex-M 的 NVIC 优先级数值通常是“数值越小，优先级越高”，且只有部分高位有效。CMSIS 的优先级参数通常使用逻辑优先级值，FreeRTOS 配置宏则可能需要未移位或移位后的编码，须按内核版本和 port 注释核对。

```
#define configLIBRARY_LOWEST_INTERRUPT_PRIORITY        15
#define configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY    5

#define configKERNEL_INTERRUPT_PRIORITY \
    (configLIBRARY_LOWEST_INTERRUPT_PRIORITY << (8 - configPRIO_BITS))

#define configMAX_SYSCALL_INTERRUPT_PRIORITY \
    (configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY << (8 - configPRIO_BITS))
```

这是常见 Cortex-M 配置形态，不是所有芯片的通用配置。先确认 `configPRIO_BITS` 与芯片实际实现一致，并启用相应断言检查。

### 5.5 堆与任务栈

FreeRTOS 提供多种 heap 实现，支持能力不同。选择时关注：

- 是否允许释放内存。
- 是否可合并相邻空闲块。
- 是否支持多个非连续内存区域。
- 分配时间是否有界。
- 是否可能产生碎片。

产品可以采用静态对象分配，以便在构建期固定内存预算。启用静态分配后需正确实现 `vApplicationGetIdleTaskMemory()`，以及启用软件定时器时的定时器任务内存回调。动态分配则必须为分配失败定义策略。

```
#define configSUPPORT_STATIC_ALLOCATION  1
#define configSUPPORT_DYNAMIC_ALLOCATION 1
#define configCHECK_FOR_STACK_OVERFLOW   2
#define configUSE_MALLOC_FAILED_HOOK     1
```

同时启用静态和动态分配是允许的，但团队需明确哪些对象可动态创建，以及运行期是否允许释放。

### 5.6 移植配置骨架

```
/* FreeRTOSConfig.h：数值需按目标芯片、时钟和应用约束确认。 */
#define configUSE_PREEMPTION                     1
#define configUSE_TIME_SLICING                   1
#define configUSE_16_BIT_TICKS                   0
#define configTICK_RATE_HZ                       ((TickType_t)1000)

#define configCPU_CLOCK_HZ                       SystemCoreClock
#define configMAX_PRIORITIES                     8
#define configMINIMAL_STACK_SIZE                 128
#define configTOTAL_HEAP_SIZE                    (24U * 1024U)

#define configUSE_MUTEXES                        1
#define configUSE_COUNTING_SEMAPHORES             1
#define configUSE_TIMERS                         1
#define configTIMER_TASK_PRIORITY                3
#define configTIMER_QUEUE_LENGTH                 10
#define configTIMER_TASK_STACK_DEPTH             256

#define configCHECK_FOR_STACK_OVERFLOW            2
#define configUSE_MALLOC_FAILED_HOOK              1
#define configASSERT(x) do { if (!(x)) { taskDISABLE_INTERRUPTS(); for (;;) {} } } while (0)
```

该配置骨架仍需补齐目标端口要求的 NVIC 配置、静态分配回调、运行时统计、可选 API 包含项等。`configMINIMAL_STACK_SIZE` 的单位通常是 `StackType_t` 个数，不是字节；具体以目标版本文档为准。

## 6. 性能量化分析

### 6.1 量化方法

移植性能不能仅根据内核版本推断。必须在目标板上测量，并报告 MCU 型号、主频、编译器版本、优化选项、FPU ABI、Tick 频率、参与切换的任务数和测量方法。

建议分别测量：

- 空闲循环时间。
- 任务间上下文切换时间。
- Tick ISR 执行时间。
- 临界区最大屏蔽时间。
- 中断到任务恢复时间。
- 任务栈高水位和最坏堆使用量。

用 GPIO 或 DWT 周期计数器测量时，需区分测量代码本身的开销，并用空测量做校正。

```
/* Cortex-M DWT 周期计数示例。芯片需支持并启用 DWT CYCCNT。 */
static void dwt_enable_cycle_counter(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t measure_once(void (*fn)(void))
{
    uint32_t start = DWT->CYCCNT;
    fn();
    return DWT->CYCCNT - start;
}
```

### 6.2 计算公式

- **Tick 周期**：`T_tick = 1 / configTICK_RATE_HZ`
- **Tick 频率造成的基础 CPU 占用近似值**：`U_tick ≈ C_tick × f_tick / f_cpu`
    - `C_tick` 是一次 Tick 处理消耗的周期数。
- **周期性上下文切换开销**：`U_switch ≈ C_switch × f_switch / f_cpu`
- **任务栈 RAM**：`RAM_stack = Σ(stack_depth_i × sizeof(StackType_t))`
- **Tick 量化等待误差**：延时精度受 Tick 粒度影响；`vTaskDelay()` 的实际时长还取决于调用发生在 Tick 周期中的相位。

### 6.3 数据解释与示例估算

以下数字是**演示估算，不是某个实测平台的结果**。假设 Cortex-M4F 运行在 120 MHz，编译器优化开启，Tick 为 1 kHz；若测得 Tick 处理为 1,000 周期，则单纯 Tick 处理占用约：

```
1,000 cycles × 1,000 ticks/s ÷ 120,000,000 cycles/s
= 0.83%
```

若一次切换为 500 周期、平均每秒发生 2,000 次，则：

```
500 × 2,000 ÷ 120,000,000
= 0.83%
```

真实数值受任务是否使用 FPU、是否发生就绪队列操作、编译配置和编译器版本影响。**必须把“估算”和“实测”分开报告。**

### 6.4 瓶颈与优化

|瓶颈|影响|优化方向|
|---|---|---|
|Tick 过高|增加周期性中断负载|评估较低 Tick 频率或 tickless idle|
|高频切换|增加上下文切换负载、降低缓存局部性|合并过细任务，使用事件驱动|
|长时间关中断|增加高优先级中断延迟|缩短临界区，改用原子操作或锁|
|动态分配碎片|长期运行后分配失败|静态分配、内存池、限制动态创建|
|任务栈配置过大|RAM 浪费|测试高水位并增加明确安全余量|

## 7. 应用场景选型指南

### 决策流程图

```
开始
 |
 |-- 是否存在目标架构 + 编译器的官方 FreeRTOS port？
 |       |-- 是：使用与内核版本匹配的官方 port
 |       |-- 否：评估维护能力、芯片异常模型与测试资源
 |
 |-- 是否启用 FPU / DSP / TrustZone 等扩展上下文？
 |       |-- 是：选择对应端口与 ABI，并验证上下文保存
 |       |-- 否：选择基础端口
 |
 |-- 是否要求任务对象运行期创建/销毁？
 |       |-- 否：优先静态分配，固定 RAM 预算
 |       |-- 是：选择合适 heap 或自定义分配器，覆盖失败路径
 |
 |-- 是否要求低功耗待机与低功耗 Tick？
         |-- 是：评估 tickless idle 与 RTC/LPTIM 唤醒误差
         |-- 否：使用常规周期 Tick 并测量 CPU 占用
```

### 典型场景

|需求|方案|理由|
|---|---|---|
|Cortex-M 裸机产品首次引入 RTOS|官方 GCC/ARMCC 端口，固定版本|降低上下文切换实现风险|
|RAM 预算严格、系统对象固定|静态对象分配|便于构建期核算、避免堆碎片|
|运行期插件或动态任务|经验证的动态分配策略|满足动态生命周期，但需设计失败恢复|
|极低功耗传感节点|tickless idle + RTC/LPTIM|减少周期唤醒，需核对长睡眠时间精度|
|高优先级采样中断|中断内只采样/入缓冲，任务处理|保持 ISR 短，并避免高优先级 ISR 调用 RTOS API|

## 8. 工程最佳实践

### 设计原则

1. **版本固定**：记录 FreeRTOS-Kernel tag/commit、编译器版本和端口目录；不要无审查替换 `portable` 文件。
2. **端口完整性**：源码、汇编、配置、启动向量和链接脚本作为同一移植单元审查。
3. **中断有界**：ISR 只做必要工作，耗时任务通过队列、通知或 DMA 完成事件交给任务。
4. **静态优先**：高可靠、固定对象的系统优先静态分配；动态分配必须定义可观测失败策略。
5. **可诊断**：启用 `configASSERT`、栈溢出检测、malloc 失败钩子，并记录故障上下文。
6. **可复现测量**：性能报告记录板卡、主频、编译选项、负载和测量代码。

### 选型决策矩阵

|条件|推荐决策|
|---|---|
|官方端口可用且版本匹配|采用官方端口，不自行重写切换代码|
|需要 FPU|使用匹配的 FPU 端口；所有相关目标文件采用一致 ABI|
|任务集合固定|静态任务、静态队列和静态同步对象|
|需要动态对象|选定 heap 策略并执行压力、碎片和失败注入测试|
|高优先级 ISR 不能被内核临界区屏蔽|使用符合优先级约束的高优先级 ISR；禁止调用 RTOS API|
|需要长时间低功耗|单独验证 tickless idle 的时钟误差、溢出和唤醒路径|

### 编码与构建规范

- 移植目录独立纳入版本控制，并在升级时与官方端口逐项 diff。
- `FreeRTOSConfig.h` 的关键时钟、优先级、堆和断言配置纳入代码审查。
- 对 SVC/PendSV/SysTick 的最终链接地址做自动化检查。
- map 文件中确认内核、port、堆实现、向量表都只出现预期定义。
- 不在中断中调用非 `FromISR` API；不在不允许的优先级调用任何 FreeRTOS API。
- 任务栈深度按 `StackType_t` 数量配置，报告换算后的字节数。

## 9. 常见错误与避坑指南

### 错误一：优先级配置编码错位

错误示例：

```
/* 错误风险：把逻辑优先级值误当成已左移的寄存器编码。 */
NVIC_SetPriority(USART1_IRQn, configMAX_SYSCALL_INTERRUPT_PRIORITY);
```

根因：CMSIS 接口通常接收逻辑优先级，而 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 常为寄存器编码值。

正确实现：

```
NVIC_SetPriority(USART1_IRQn,
                 configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY);
```

风险：中断可能被配置到错误优先级，导致断言触发、内核状态损坏或实时性异常。

### 错误二：在高优先级 ISR 调用 RTOS API

错误示例：

```
void ADC_IRQHandler(void)
{
    xQueueSendFromISR(adc_queue, &sample, NULL);
}
```

如果 ADC 中断优先级高于 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 所允许的范围，这仍是错误用法。

正确实现：将中断配置在允许调用内核 API 的优先级范围内；或让高优先级 ISR 只写入无锁/硬件缓冲区，再由低优先级中断或任务转交数据。具体同步方案需针对平台验证。

风险：中断屏蔽语义失效，可能破坏内核链表或就绪队列。

### 错误三：`configCPU_CLOCK_HZ` 与实际时钟不一致

错误示例：

```
#define configCPU_CLOCK_HZ 16000000U /* 实际系统已运行在 120 MHz */
```

正确实现：在时钟初始化后确保内核使用的频率与 SysTick 配置一致；若运行期间改频，执行经验证的 Tick 重配置流程。

风险：Tick 周期错误、超时不准、延时误差随时钟切换变化。

### 错误四：任务栈深度按字节理解

错误示例：

```
xTaskCreate(worker, "worker", 512U, NULL, 2U, NULL); /* 误认为 512 字节 */
```

在常见配置下，栈深度参数表示 `StackType_t` 元素数。若 `StackType_t` 为 32 位，此值可能对应 2,048 字节。

正确实现：

```
#define WORKER_STACK_WORDS  256U
_Static_assert(sizeof(StackType_t) == 4U,
               "Update stack budget for this architecture");
```

风险：RAM 预算偏差、栈溢出检测触发或内存浪费。

### 错误五：向量表仍指向芯片默认异常处理器

根因：启动文件的强符号定义覆盖了 FreeRTOS port，或重命名宏没有生效。

正确实现：检查 map/ELF 符号；确保最终向量表的 SVC、PendSV、SysTick 指向预期处理函数。

风险：调度器无法启动，或首次 Tick 后进入默认死循环。

### 错误六：FPU ABI 或浮点上下文处理不匹配

根因：部分文件启用了硬浮点 ABI，部分文件使用软浮点；或选择了不匹配的 FPU port。

正确实现：统一 CPU/FPU 编译参数，核对官方端口的 FP 上下文策略，并用多个使用浮点的任务做上下文切换压力测试。

风险：任务切换后浮点寄存器互相污染，故障可能只在特定负载下出现。

## 10. 多机制组合使用方案

典型组合：**DMA + ISR 通知 + 高优先级数据处理任务 + 低优先级业务任务**。ISR 不执行解析或日志输出，只确认 DMA 状态并唤醒任务。

```
#include "FreeRTOS.h"
#include "task.h"

static TaskHandle_t telemetry_task_handle;

static void telemetry_task(void *argument)
{
    (void)argument;

    for (;;) {
        uint32_t notification_count;

        notification_count = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (notification_count == 0U) {
            continue;
        }

        /* 读取已完成的 DMA 缓冲区；所有权切换由 DMA 驱动明确管理。 */
        process_dma_buffers();
    }
}

void DMA_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    dma_acknowledge_irq();
    vTaskNotifyGiveFromISR(telemetry_task_handle,
                           &higher_priority_task_woken);
    portYIELD_FROM_ISR(higher_priority_task_woken);
}

int app_start_tasks(void)
{
    BaseType_t result;

    result = xTaskCreate(telemetry_task,
                         "telemetry",
                         512U,
                         NULL,
                         4U,
                         &telemetry_task_handle);
    if (result != pdPASS) {
        return -1;
    }

    return 0;
}
```

工程注意点：

- DMA 缓存一致性必须按芯片架构处理；有 D-cache 时需要 cache clean/invalidate 或使用非缓存区域。
- 通知适合单接收者事件；多消费者、背压和数据容量管理应使用队列或环形缓冲区。
- ISR 必须处于允许调用 `FromISR` API 的优先级范围。
- 任务栈深度、任务优先级和 DMA 缓冲区所有权都要通过压力测试验证。
- `portYIELD_FROM_ISR()` 的具体形式随端口实现变化，按对应端口示例使用。

## 11. 工业级实际案例分析

以下为典型工业设计模式，不代表特定厂商产品实现。

### 案例一：电机控制器的周期采样

- **需求**：ADC/PWM 同步采样，控制回路有严格周期约束，通信和诊断不能阻塞控制。
- **架构**：定时器触发 ADC；高优先级中断完成必要采样与安全保护；控制计算在受控上下文执行；通信任务低优先级运行。
- **设计要点**：控制回路最坏执行时间必须小于周期预算；高优先级 ISR 不调用 FreeRTOS API；任务栈和中断栈均需单独核算。
- **核心代码示意**：

```
void ADC_IRQHandler(void)
{
    sample_t sample = adc_read_result();
    adc_clear_irq();

    if (safety_limit_exceeded(&sample)) {
        motor_force_safe_state();
    }

    control_mailbox_write_isr(&sample);
    pend_control_processing();
}
```

这里的 `control_mailbox_write_isr()` 必须是经过平台验证的中断安全实现；不能在高优先级 ISR 内直接调用不允许的 RTOS API。

### 案例二：工业网关的以太网收包

- **需求**：收包频率不均匀，突发流量下不能在 ISR 内解析协议。
- **架构**：MAC DMA 描述符环形队列；网卡 ISR 确认中断并通知网络任务；网络任务回收描述符、执行协议处理；业务任务读取解析结果。
- **设计要点**：描述符缓冲区生命周期、DMA cache 一致性、接收环背压和任务优先级是关键；用队列长度和丢包计数监测过载。
- **代码路径**：ISR 只通知任务；网络任务批量处理可用描述符，避免每包触发一次昂贵切换。

### 案例三：电池管理系统的低功耗状态采集

- **需求**：大部分时间休眠，定时采样并响应告警。
- **架构**：使用 tickless idle；RTC/LPTIM 负责长睡眠计时；告警中断唤醒系统；采样和滤波由任务处理。
- **设计要点**：验证睡眠时钟精度、唤醒延迟、睡眠期间 Tick 补偿和计数溢出；安全告警路径不能依赖普通任务调度延迟。

## 12. 高频问题深度答疑

### Q1：只要编译通过，就算移植成功了吗？

不是。编译通过只能证明语法和符号依赖满足。至少还需验证首任务启动、稳定切换、Tick 精度、临界区语义、中断优先级规则、栈溢出检测、malloc 失败路径和故障可观测性。

### Q2：为什么 `vTaskStartScheduler()` 后不再返回？

正常情况下调度器成功启动后不返回。若返回，常见原因包括创建 Idle task 失败、内存不足、动态分配未提供、端口启动失败或配置不完整。应检查返回路径和 `vApplicationMallocFailedHook()`，不要把它简单视为死机。

### Q3：PendSV 为什么常配置为最低优先级？

PendSV 用于延后执行上下文切换。将它设为低优先级，能让正在处理的高优先级中断先完成，减少中断嵌套中的上下文切换复杂度。实际配置仍以目标 port 的初始化代码为准。

### Q4：`BASEPRI` 临界区是否屏蔽所有中断？

不是。它只能屏蔽优先级数值达到阈值及更低紧急程度的可配置中断；更高紧急程度的中断仍可能抢占。因此这类 ISR 不能访问未受保护的内核对象，也不能调用不允许的 RTOS API。

### Q5：任务栈检测通过，是否可以认为栈配置充足？

不能完全这样认为。高水位检测依赖栈填充值模式，并且只能说明已观察负载下的使用情况。递归、深调用、异常嵌套、浮点上下文和不同优化等级都可能增加峰值。需要压力场景、静态调用深度分析和安全余量共同验证。

### Q6：Tickless idle 会不会影响超时准确性？

可能。误差取决于低功耗计时源频率、唤醒延迟、计数舍入和时钟切换策略。应选用持续运行的低功耗定时器，测量长睡眠和边界时间，并验证“提前唤醒/延后唤醒”的应用容忍度。

## 13. 课程核心总结

- FreeRTOS 移植的核心是**处理器上下文、异常向量、Tick、中断屏蔽和内存配置的契约正确**。
- 优先复用与内核版本、编译器和目标架构匹配的官方端口。
- Cortex-M 重点检查 SVC、PendSV、SysTick 的向量解析，以及 NVIC 优先级编码。
- FPU、TrustZone、运行时改频和 tickless idle 都会扩大验证范围。
- 性能数字必须在目标板、明确编译选项和负载下测量；估算值不能当成实测结果。
- 工业验收要覆盖功能、实时性、内存边界、异常恢复和可诊断性，而不只是任务能够运行。

**常见实现成本的经验排序**：官方端口复用通常最低；官方端口加芯片时钟/向量适配其次；自行修改上下文切换代码最高。这个排序描述的是移植与维护成本，不等同于运行性能排序。

## 14. 快速参考速查表

### 场景选型表

|场景|建议|
|---|---|
|有匹配官方 port|直接复用并锁定版本|
|固定对象、高可靠性|静态分配优先|
|运行期动态创建|明确 heap 策略、失败回调和碎片测试|
|高优先级 ISR|不调用 RTOS API，缩短 ISR|
|低功耗产品|验证 tickless 与低功耗时钟误差|
|启用 FPU|统一 ABI，使用匹配的 FPU port|

### 移植验收表

|检查项|验证手段|
|---|---|
|向量映射正确|ELF/map 文件检查|
|Tick 正确|GPIO 或计数器测量 Tick 周期|
|上下文切换正确|多任务压力测试，检查寄存器与浮点数据|
|中断规则正确|`configASSERT`、优先级审查、异常注入|
|栈与堆边界|高水位、溢出 hook、分配失败测试|
|性能满足预算|DWT/GPIO 测量并记录方法|
|故障可诊断|故障快照、断言和复位原因记录|

## 15. 学习效果自检

- 能从目标工程找到并解释上下文切换汇编与初始栈帧构造。
- 能说明线程模式与 Handler 模式使用 MSP/PSP 的关系。
- 能解释 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 的实际约束。
- 能从 map 文件确认 FreeRTOS 异常入口没有被启动文件覆盖。
- 能将任务栈深度换算为字节，并核查所有静态 RAM 预算。
- 能测量 Tick、任务切换和临界区时间，并区分测量开销。
- 能设计不在 ISR 内执行复杂工作的数据通路。
- 能写出移植验收测试，包括启动、负载、故障和低功耗路径。

## 16. 实践与进阶路径

### 梯度实战任务

1. **最小启动**：使用官方端口创建两个任务，验证调度器启动、任务切换和 Tick。
2. **中断集成**：接入一个定时器或 DMA 中断，验证 `FromISR` API 和优先级约束。
3. **内存验证**：启用栈溢出检测、malloc 失败钩子和高水位统计；制造分配失败并检查处理结果。
4. **性能基线**：使用 DWT 或 GPIO 测量 Tick、任务切换、ISR 延迟和临界区时长。
5. **扩展功能**：分别验证 FPU、动态改频或 tickless idle；每次只引入一项，记录误差和资源变化。

### 性能测试方法

- 使用 DWT `CYCCNT` 获取周期数；先测量并扣除测量框架开销。
- 用 GPIO 脉冲配合示波器/逻辑分析仪观察外部时序。
- 对响应延迟统计平均值、最大值和高分位值，不能只报告平均数。
- 在通信突发、最大任务负载、中断嵌套和低功耗唤醒场景下重复测试。
- 记录代码版本、编译器参数、主频、温度/电压条件和测量工具。

### 进阶方向

- 阅读当前 FreeRTOS-Kernel 版本的 `tasks.c`、端口上下文切换实现和堆实现源码。
- 研究 Cortex-M 异常入口、`EXC_RETURN`、栈对齐与浮点惰性压栈机制。
- 分析中断优先级反转、长临界区和任务优先级反转的不同成因。
- 深入 tickless idle、静态内存分配、运行时统计和 trace 工具集成。
- 将移植验收自动化：符号检查、配置检查、栈预算、启动压力测试和性能回归测试。