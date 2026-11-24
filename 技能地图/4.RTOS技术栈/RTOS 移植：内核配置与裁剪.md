
> 本课针对 **FreeRTOS、RT-Thread、embOS、Zephyr** 四类 RTOS，重点讨论在完成基础移植之后，如何进行**内核配置、功能裁剪、内存预算、性能优化、可验证构建和产品级配置管理**。
> 
> 四者的配置模型不同：
> 
> - **FreeRTOS**：以 `FreeRTOSConfig.h` 为核心，配置集中、显式、简单。
> - **RT-Thread**：以 `rtconfig.h`、Kconfig、组件配置和 BSP 配置共同决定最终功能。
> - **embOS**：配置入口和可裁剪项受具体版本、CPU port、授权包和工程模板约束，不能脱离版本手册假定统一宏名称。
> - **Zephyr**：以 Kconfig、Devicetree、CMake/west 和模块配置共同生成最终工程，配置体系最完整，但依赖链也最复杂。
> 
> **配置与裁剪不是“关闭几个宏”** 。工业级裁剪必须同时考虑功能依赖、代码路径、RAM/Flash、实时性、可诊断性、安全能力、升级维护和测试覆盖。

---

# 1. 学习目标

## 理解

- 理解 RTOS 内核配置、编译裁剪、链接裁剪和运行时资源配置的区别。
- 理解 FreeRTOS、RT-Thread、embOS、Zephyr 四类 RTOS 的配置模型和依赖机制。
- 理解一个配置项如何影响：
    - Flash 代码量。
    - RAM 数据量。
    - 任务栈。
    - 中断延迟。
    - 调度行为。
    - 组件初始化。
    - 调试和故障恢复能力。
- 理解“最小镜像”和“可量产镜像”之间的工程差异。

## 掌握

- 能根据产品需求建立 RTOS 功能配置矩阵。
- 能配置和裁剪以下能力：
    - 抢占调度。
    - 时间片。
    - Tick。
    - 同步对象。
    - 软件定时器。
    - 动态内存。
    - 静态内存。
    - Shell。
    - 日志。
    - 网络。
    - 文件系统。
    - 低功耗。
    - MPU/TrustZone。
- 能使用 map 文件、ELF、Kconfig、预处理结果和构建日志分析裁剪结果。
- 能区分“功能没有启用”和“功能已启用但没有被调用”。
- 能制定开发版、测试版和量产版的差异化配置。

## 精通

- 能定位配置依赖导致的隐式资源增长。
- 能分析一个配置项对实时性、内存和故障诊断的综合影响。
- 能设计可复现、可审计、可回滚的 RTOS 配置体系。
- 能对四类 RTOS 建立统一的 RAM/Flash/实时性预算模型。
- 能通过压力测试验证裁剪没有破坏异常路径和边界功能。

## 能够设计

- 能设计面向产品系列的 RTOS 配置层级。
- 能设计静态内存优先、动态内存受控、组件按需启用的系统架构。
- 能建立配置检查、资源预算、功能回归和性能回归的 CI 流程。
- 能为安全关键、高性能、低功耗和资源受限产品制定不同的裁剪策略。

---

# 2. 前置要求

## 知识要求

### RTOS 基础

- 抢占式与协作式调度。
- 线程/任务状态。
- 优先级、时间片和阻塞。
- Tick、软件定时器和超时。
- 临界区、中断安全 API 和优先级反转。
- 信号量、互斥量、事件、消息队列和内存池。

### C 和构建系统

- 预处理宏、条件编译、弱符号和链接段。
- 静态库、目标文件和链接器垃圾回收。
- CMake、Make、SCons、Ninja。
- map 文件、ELF 符号和反汇编。
- 编译器优化选项和 LTO。

### MCU 和系统资源

- Flash、RAM、TCM、DTCM、AXI SRAM、外部 RAM。
- Cortex-M 异常和中断。
- Cache、MPU、TrustZone-M。
- DMA 缓冲区和内存属性。
- 低功耗和时钟切换。

## 技能要求

- 能查看 RTOS 的最终配置文件。
- 能从 map 文件定位最大的代码段和数据段。
- 能查看编译器预处理后的宏结果。
- 能使用 `size`、`nm`、`objdump`、`readelf`。
- 能在目标板上测量 Tick、任务切换、ISR 延迟和栈高水位。
- 能通过故障注入验证配置失败路径。

---

# 3. 技术概述

## 3.1 内核配置与裁剪的定义

RTOS 配置可以分为五个层次：

```
功能配置
  -> 是否启用信号量、消息队列、软件定时器、网络、文件系统等

资源配置
  -> 任务数量、优先级数量、队列长度、线程栈、堆大小

行为配置
  -> 抢占、时间片、Tick、超时、调度策略、低功耗

硬件配置
  -> 时钟、Tick 定时器、MPU、FPU、Cache、DMA

构建配置
  -> 编译器、优化、LTO、链接脚本、调试符号、镜像布局
```

真正的产品镜像大小和实时性能由这些层次共同决定。

## 3.2 四类 RTOS 的配置模型

|RTOS|主配置机制|配置特点|主要风险|
|---|---|---|---|
|FreeRTOS|`FreeRTOSConfig.h`|集中、显式、宏控制|配置项之间的隐式依赖和端口差异|
|RT-Thread|`rtconfig.h`、Kconfig、BSP 配置|内核、组件、设备框架分层|BSP/组件配置不一致|
|embOS|版本相关工程配置、CPU port、官方模板|商业包内配置和端口耦合|不能脱离版本手册假定配置宏|
|Zephyr|Kconfig、Devicetree、CMake、west|配置表达能力强、自动生成完整|依赖链、模块和生成文件复杂|

## 3.3 裁剪的四个目标

### 目标一：降低资源占用

- 减少 Flash。
- 减少静态 RAM。
- 减少任务栈。
- 减少对象数量。
- 减少初始化数据。

### 目标二：保持实时性

- 降低 Tick 固定开销。
- 缩短临界区。
- 减少不必要的线程切换。
- 关闭同步日志。
- 降低中断和后台任务负载。

### 目标三：保留可诊断能力

- 断言。
- 栈溢出检测。
- 堆分配失败回调。
- 运行时统计。
- 故障日志。
- 看门狗。
- 线程和设备状态查询。

### 目标四：保证可维护性

- 配置可审计。
- 构建可复现。
- 版本可回滚。
- 不依赖手动修改生成文件。
- 开发版和量产版差异明确。

## 3.4 不能简单裁剪的内容

以下功能即使不直接用于业务，也可能被间接依赖：

- 系统 Tick。
- 空闲线程。
- 主线程。
- 中断上下文管理。
- 基础时钟。
- 内存对齐。
- 设备初始化框架。
- 错误处理。
- 异常向量。
- C 运行库。
- 低功耗唤醒源。
- 安全启动依赖。

**裁剪前必须建立依赖图，而不是只看应用代码是否调用某个 API。**

---

# 4. 核心特性横向对比

## 4.1 四类 RTOS 配置体系对比

|维度|FreeRTOS|RT-Thread|embOS|Zephyr|
|---|---|---|---|---|
|主要配置文件|`FreeRTOSConfig.h`|`rtconfig.h`/Kconfig|版本相关工程配置|`prj.conf`、Board/SoC Kconfig|
|硬件描述|BSP 和芯片工程|BSP、驱动和 Kconfig|BSP/工程模板|Devicetree|
|组件裁剪|宏控制|内核宏 + 组件配置|官方包和工程选项|Kconfig|
|依赖解析|相对简单|中等|取决于版本和模板|自动依赖能力强|
|配置可读性|高|中|需看版本手册|高，但文件较多|
|配置生成|通常手工|手工或配置工具|工程模板/配置工具|自动生成|
|适合小 MCU|很适合|Nano/精简版适合|适合|通过 Kconfig 裁剪后适合|
|复杂系统能力|需外部组件|较强|取决于产品包|很强|
|配置误用风险|中|中|高度依赖版本|依赖链复杂|
|构建审计难度|低|中|中|高|
|动态可配置性|中|高|取决于版本|高|

## 4.2 功能配置对比

|功能|FreeRTOS|RT-Thread|embOS|Zephyr|
|---|---|---|---|---|
|抢占调度|`configUSE_PREEMPTION`|配置项/内核策略|版本相关|`CONFIG_PREEMPT_ENABLED` 等|
|时间片|`configUSE_TIME_SLICING`|调度器配置|版本相关|调度配置|
|Tick 频率|`configTICK_RATE_HZ`|`RT_TICK_PER_SECOND`|官方时基配置|`CONFIG_SYS_CLOCK_TICKS_PER_SEC`|
|动态内存|`configSUPPORT_DYNAMIC_ALLOCATION`|heap/内存管理|版本相关|内核 heap/Kconfig|
|静态对象|`configSUPPORT_STATIC_ALLOCATION`|静态对象 API|版本相关|静态对象和链接配置|
|软件定时器|`configUSE_TIMERS`|软件定时器组件|版本相关|`k_timer`|
|Shell|FinSH 可选|原生 FinSH/MSH|通常需配套组件|Shell 子系统|
|日志|Trace/Hook/外部日志|日志组件|版本和工具支持|Logger|
|网络|外部协议栈或扩展|网络组件|取决于产品包|原生网络子系统|
|文件系统|外部组件|文件系统组件|取决于产品包|原生文件系统|
|Device Tree|无|部分 BSP 使用|通常无|核心机制|
|Kconfig|无|可选/常见|通常不是核心机制|核心机制|

## 4.3 内存策略对比

|策略|确定性|碎片风险|适用|
|---|---|---|---|
|全静态|高|无|安全关键、固定对象|
|固定块内存池|高|低|消息、网络包、DMA 描述符|
|通用动态堆|中|中至高|配置、非固定生命周期对象|
|分区堆|高|低|多种固定大小对象|
|外部内存|取决于总线|取决于管理器|大缓存、帧缓冲|
|动态堆 + 失败恢复|中|取决于实现|设备数量和对象数量动态变化|

## 4.4 诊断能力裁剪对比

|能力|开发版|测试版|量产版建议|
|---|---|---|---|
|断言|开启|开启|保留关键断言或故障记录|
|栈溢出检测|开启|开启|保留低成本检测|
|堆失败钩子|开启|开启|必须保留失败计数和降级策略|
|Shell|开启|开启|按安全策略关闭或只读|
|同步日志|可用|尽量关闭|通常关闭|
|延迟日志|开启|开启|保留限速诊断|
|Trace|开启|按需|关闭或保留采样|
|调试符号|完整|完整|可分离保存，不一定烧录|
|线程名称|开启|开启|视 RAM 预算决定|
|运行时统计|开启|开启|保留核心指标|

---

# 5. 底层原理与功能特性深度解析

## 5.1 配置的编译过程

以通用 RTOS 工程为例：

```
配置源
  |
  |-- FreeRTOSConfig.h
  |-- rtconfig.h
  |-- embOS 工程配置
  |-- Zephyr prj.conf/Kconfig
  |
预处理
  |
  |-- 条件编译
  |-- API 宏展开
  |-- 功能代码裁剪
  |
编译
  |
  |-- 生成目标文件
  |-- 生成静态库
  |
链接
  |
  |-- 链接器垃圾回收
  |-- 段布局
  |-- 符号解析
  |
最终镜像
  |
  |-- Flash
  |-- RAM
  |-- 向量表
  |-- 线程栈
  |-- 设备初始化
```

重要结论：

- **宏关闭**通常决定代码是否参与编译。
- **链接器垃圾回收**决定未引用代码是否最终进入镜像。
- **静态对象配置**决定 RAM 是否在链接阶段固定占用。
- **运行时动态创建**决定 RAM 是否在运行期变化。
- **调试和日志**可能同时增加 Flash、RAM、CPU 和栈消耗。

## 5.2 FreeRTOS 配置与裁剪

### 5.2.1 核心配置骨架

```
#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

#define configUSE_PREEMPTION                    1
#define configUSE_TIME_SLICING                  1
#define configCPU_CLOCK_HZ                      SystemCoreClock
#define configTICK_RATE_HZ                      ((TickType_t)1000)
#define configMAX_PRIORITIES                    8

#define configSUPPORT_STATIC_ALLOCATION         1
#define configSUPPORT_DYNAMIC_ALLOCATION        0
#define configTOTAL_HEAP_SIZE                   0

#define configUSE_MUTEXES                       1
#define configUSE_RECURSIVE_MUTEXES             0
#define configUSE_COUNTING_SEMAPHORES            1
#define configUSE_TASK_NOTIFICATIONS             1
#define configUSE_TIMERS                         1

#define configUSE_IDLE_HOOK                     0
#define configUSE_TICK_HOOK                     0
#define configUSE_MALLOC_FAILED_HOOK             0
#define configCHECK_FOR_STACK_OVERFLOW           2

#define INCLUDE_vTaskDelay                      1
#define INCLUDE_vTaskSuspend                    1
#define INCLUDE_xTaskAbortDelay                 0
#define INCLUDE_xTaskGetSchedulerState          1
#define INCLUDE_uxTaskGetStackHighWaterMark     1

#endif
```

这是结构示例。具体配置项受 FreeRTOS 内核版本、端口和应用影响。

### 5.2.2 FreeRTOS 配置影响

|配置|影响|
|---|---|
|`configUSE_PREEMPTION`|抢占调度代码和行为|
|`configUSE_TIME_SLICING`|同优先级任务的 Tick 轮转|
|`configMAX_PRIORITIES`|就绪列表数量、调度相关 RAM/代码|
|`configUSE_MUTEXES`|互斥锁和优先级继承相关代码|
|`configUSE_RECURSIVE_MUTEXES`|递归互斥锁支持|
|`configUSE_COUNTING_SEMAPHORES`|计数信号量代码|
|`configUSE_TASK_NOTIFICATIONS`|任务通知代码，通常成本较低|
|`configUSE_TIMERS`|Timer Service 任务、队列和栈|
|`configUSE_TRACE_FACILITY`|任务统计、调试字段|
|`configGENERATE_RUN_TIME_STATS`|运行时统计采样|
|`configUSE_STATS_FORMATTING_FUNCTIONS`|统计格式化代码和栈|
|`INCLUDE_xxx`|单个 API 的编译包含|
|`configASSERT`|断言代码和故障定位能力|

### 5.2.3 `configMAX_PRIORITIES` 的成本

`configMAX_PRIORITIES` 不是越大越好。它可能影响：

- 就绪列表数量。
- 调度器扫描或查找路径。
- 端口位图大小。
- 任务控制块相关数据。
- 优先级配置的可维护性。

工业产品应根据优先级分层设计，例如：

```
0：空闲
1：后台维护
2：日志/统计
3：普通业务
4：通信处理
5：实时采集
6：控制线程
7：安全事件
```

如果配置 32 个优先级，但系统只使用 6 个，会增加配置复杂度和潜在误用，而不一定带来收益。

### 5.2.4 FreeRTOS 动态和静态分配

静态分配：

```
#define configSUPPORT_STATIC_ALLOCATION   1
#define configSUPPORT_DYNAMIC_ALLOCATION  0
```

动态分配：

```
#define configSUPPORT_STATIC_ALLOCATION   0
#define configSUPPORT_DYNAMIC_ALLOCATION  1
#define configTOTAL_HEAP_SIZE             (24U * 1024U)
```

混合方式：

```
#define configSUPPORT_STATIC_ALLOCATION   1
#define configSUPPORT_DYNAMIC_ALLOCATION  1
```

产品建议：

- 固定任务、队列和信号量优先静态创建。
- 网络包、协议对象优先使用内存池。
- 动态堆只用于确实存在运行期生命周期变化的对象。
- 动态分配失败必须有策略：
    - 拒绝新请求。
    - 释放低优先级缓存。
    - 降级功能。
    - 记录故障。
    - 触发复位或安全状态。

### 5.2.5 FreeRTOS API 裁剪

例如，如果应用没有使用任务挂起 API：

```
#define INCLUDE_vTaskSuspend 0
```

如果应用不需要任务统计：

```
#define configUSE_TRACE_FACILITY 0
#define INCLUDE_uxTaskGetSystemState 0
```

但裁剪前必须执行：

```
源码搜索 API 调用
  -> 检查组件和第三方库
  -> 检查调试脚本
  -> 检查异常恢复路径
  -> 编译和链接
  -> 运行时回归
```

不能只搜索 `src/`，还要搜索：

- 驱动。
- 网络协议栈。
- OTA。
- 测试代码。
- Shell 命令。
- 工具和调试适配层。

## 5.3 RT-Thread 配置与裁剪

### 5.3.1 RT-Thread 配置层级

典型层次：

```
rtconfig.h
  |
  |-- 内核功能
  |-- 线程/IPC/定时器
  |-- 堆和内存池
  |
BSP 配置
  |
  |-- 时钟
  |-- UART
  |-- GPIO
  |-- Tick
  |-- 芯片外设
  |
组件配置
  |
  |-- FinSH/MSH
  |-- 文件系统
  |-- 网络
  |-- USB
  |-- OTA
  |-- 日志
  |
应用配置
  |
  |-- 业务线程
  |-- 设备和协议
```

### 5.3.2 RT-Thread 常见配置示意

```
#ifndef RT_CONFIG_H
#define RT_CONFIG_H

#define RT_USING_PREEMPTION
#define RT_TICK_PER_SECOND 1000

#define RT_THREAD_PRIORITY_MAX 32
#define RT_USING_HOOK

#define RT_USING_SEMAPHORE
#define RT_USING_MUTEX
#define RT_USING_EVENT
#define RT_USING_MAILBOX
#define RT_USING_MESSAGEQUEUE

#define RT_USING_HEAP
#define RT_USING_MEMPOOL

#define RT_USING_DEVICE
#define RT_USING_CONSOLE
#define RT_CONSOLE_DEVICE_NAME "uart1"

#define RT_USING_FINSH
#define FINSH_USING_MSH

#define RT_USING_LOG
#define LOG_LEVEL LOG_LVL_INFO

#endif
```

配置宏会随着 RT-Thread 版本、BSP 和组件变化，不能脱离当前工程直接复制。

### 5.3.3 RT-Thread 裁剪重点

#### 内核级裁剪

- 抢占调度。
- 时间片。
- Tick。
- 线程数。
- 线程优先级数量。
- 信号量。
- 互斥量。
- 事件。
- 邮箱。
- 消息队列。
- 软件定时器。
- Hook。
- Idle Hook。
- 线程统计。

#### 组件级裁剪

- FinSH/MSH。
- 文件系统。
- 网络协议栈。
- USB。
- OTA。
- 日志。
- POSIX 兼容层。
- C++ 支持。
- 软件包。

#### 设备级裁剪

- 设备框架。
- 自动初始化。
- 设备注册。
- DMA。
- 电源管理。
- 设备电源状态。

### 5.3.4 FinSH/MSH 的资源影响

Shell 通常增加：

- 命令表。
- 命令字符串。
- Shell 线程栈。
- Shell 输入缓冲区。
- 输出缓冲区。
- 格式化代码。
- UART 依赖。
- 访问系统对象的调试代码。

开发阶段建议开启：

```
#define RT_USING_FINSH
#define FINSH_USING_MSH
#define FINSH_USING_HISTORY
#define FINSH_USING_SYMTAB
```

量产版应根据安全需求选择：

```
完全关闭
只保留只读诊断命令
使用受认证的维护通道
关闭任意内存读写和复位命令
```

### 5.3.5 RT-Thread 组件裁剪策略

不要直接从工程中删除组件目录。应：

1. 关闭配置宏。
2. 执行全量构建。
3. 检查组件是否仍被其他模块依赖。
4. 查看 map 文件。
5. 运行设备初始化回归。
6. 执行长期压力测试。

尤其注意：

```
开启网络
  -> 可能依赖定时器、线程、内存、网卡设备和日志

开启文件系统
  -> 可能依赖块设备、缓存、信号量和工作线程

开启 FinSH
  -> 可能依赖控制台设备、线程和符号表

开启 OTA
  -> 可能依赖网络、Flash、校验、文件系统和升级状态机
```

## 5.4 embOS 配置与裁剪

### 5.4.1 embOS 配置原则

embOS 的具体配置入口和宏名称会随版本、CPU port、工具链和授权包变化。应从以下资料确认：

- 当前 embOS 用户手册。
- 当前 CPU port 文档。
- 官方示例工程。
- 目标芯片 BSP。
- 工具链工程模板。
- 授权包中的配置文件。

不要使用其他 RTOS 的配置习惯去猜 embOS 的配置接口。

### 5.4.2 embOS 常见裁剪维度

虽然具体名称以版本为准，但通常需要评估：

- 任务调度。
- 系统时钟。
- 任务延时。
- 信号量。
- 事件。
- 邮箱或消息机制。
- 软件定时器。
- 内存管理。
- 任务监控。
- 调试和 Trace。
- 统计信息。
- CPU port 特性。
- FPU、MPU 和低功耗支持。

### 5.4.3 embOS 端口与功能配置的关系

对于 embOS，以下配置不能孤立处理：

```
CPU port
  + 编译器 ABI
  + FPU
  + 中断模型
  + 系统 Tick
  + 任务栈
  + 调试支持
```

例如：

- 切换 FPU 编译选项可能改变任务上下文要求。
- 修改中断优先级策略可能改变系统锁语义。
- 启用 MPU 或安全扩展可能改变栈和异常入口。
- 修改 Tick 源可能影响延时、定时器和低功耗。

### 5.4.4 embOS 裁剪的工程流程

```
确认 embOS 版本和授权包
  -> 确认 CPU port 和工具链
  -> 从官方示例建立基线
  -> 禁用不需要的对象/组件
  -> 编译并检查符号
  -> 测量 RAM/Flash
  -> 执行调度/ISR/超时回归
  -> 记录配置差异
```

### 5.4.5 embOS 调试能力不能过早关闭

开发阶段应尽量保留：

- 断言。
- 任务状态观察。
- 栈检查。
- CPU 寄存器和异常转储。
- Trace 或性能统计。
- 看门狗故障信息。

量产版可以关闭高成本 Trace，但建议保留：

```
任务栈边界检测
内核错误记录
复位原因
看门狗信息
关键线程状态
系统锁超时或异常计数
```

## 5.5 Zephyr 配置与裁剪

### 5.5.1 Zephyr 的最终配置来源

```
应用 prj.conf
  + Board Kconfig
  + SoC Kconfig
  + 架构 Kconfig
  + 模块 Kconfig
  + CMake 参数
  + Devicetree
  + west manifest
  -> build/zephyr/.config
  -> 最终镜像
```

Devicetree 独立生成：

```
Board DTS
  + SoC DTSI
  + Shield DTS
  + app.overlay
  -> build/zephyr/zephyr.dts
  -> devicetree_generated.h
```

### 5.5.2 Zephyr 配置示意

```
CONFIG_GPIO=y
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y

CONFIG_MAIN_STACK_SIZE=2048
CONFIG_IDLE_STACK_SIZE=512
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=1024

CONFIG_HEAP_MEM_POOL_SIZE=4096
CONFIG_HEAP_LISTENER=y

CONFIG_LOG=y
CONFIG_LOG_MODE_DEFERRED=y
CONFIG_LOG_DEFAULT_LEVEL=2

CONFIG_ASSERT=y
CONFIG_THREAD_NAME=y
CONFIG_THREAD_STACK_INFO=y

CONFIG_PM=y
CONFIG_TICKLESS_KERNEL=y
```

这些选项需根据目标 Zephyr 版本和平台确认。

### 5.5.3 Zephyr 的裁剪路径

#### 关闭组件

```
CONFIG_LOG=n
CONFIG_SHELL=n
CONFIG_NET=n
CONFIG_FILE_SYSTEM=n
CONFIG_BT=n
CONFIG_USB_DEVICE_STACK=n
```

#### 降低资源

```
CONFIG_MAIN_STACK_SIZE=1024
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=1024
CONFIG_NET_BUF_RX_COUNT=8
CONFIG_NET_BUF_TX_COUNT=8
```

#### 关闭调试能力

```
CONFIG_THREAD_NAME=n
CONFIG_THREAD_STACK_INFO=n
CONFIG_ASSERT=n
CONFIG_TRACING=n
```

量产版关闭这些选项前，必须确认已经通过开发和测试阶段的覆盖。

### 5.5.4 Zephyr 的隐式依赖

例如打开 Shell：

```
CONFIG_SHELL=y
  -> Shell backend
  -> UART/RTT/USB backend
  -> Shell 线程或工作队列
  -> 命令表和字符串
  -> 线程栈和输入缓冲区
```

打开网络：

```
CONFIG_NETWORKING=y
  -> 网络协议栈
  -> net_buf
  -> 网络线程
  -> 网卡驱动
  -> 事件/定时器
  -> 协议配置
  -> RAM buffer
```

打开蓝牙：

```
CONFIG_BT=y
  -> Host
  -> Controller 或外部 Controller
  -> HCI
  -> buffer
  -> 工作队列/线程
  -> 定时器
```

### 5.5.5 Zephyr 的 Devicetree 裁剪

关闭硬件实例：

```
&spi2 {
    status = "disabled";
};
```

禁用设备树节点不一定会关闭所有驱动代码。要同时关闭对应 Kconfig，否则驱动可能仍然编译，但实例不会生成。

正确的裁剪方式通常是：

```
Kconfig：
  关闭驱动子系统

Devicetree：
  将具体硬件节点设置为 disabled

应用：
  删除对设备的依赖或添加编译条件
```

---

# 6. 性能量化分析

## 6.1 资源预算模型

一个 RTOS 镜像的 RAM 可以近似表示为：

```
RAM_total =
    RAM_kernel
  + RAM_task_stack
  + RAM_task_control_block
  + RAM_ipc
  + RAM_timer
  + RAM_heap
  + RAM_driver
  + RAM_dma
  + RAM_log
  + RAM_network
  + RAM_file_system
  + RAM_alignment
```

Flash 可以近似表示为：

```
Flash_total =
    Flash_kernel
  + Flash_port
  + Flash_driver
  + Flash_component
  + Flash_application
  + Flash_const_data
  + Flash_init_data
  + Flash_exception
```

不能只看 RTOS 内核源代码大小。一个日志、网络或 Shell 配置可能引入大量间接依赖。

## 6.2 典型测量平台

性能报告应记录：

```
MCU：Cortex-M4F，120 MHz
RTOS：具体版本和 commit
编译器：GCC 版本
优化：-O2
LTO：关闭/开启
调试：关闭/开启
Tick：1000 Hz
日志：关闭或延迟模式
网络：关闭
FPU：开启/关闭
Cache：开启/关闭
测量：DWT + GPIO + map 文件
```

## 6.3 Flash 和 RAM 的测量

GNU 工具链常用：

```
arm-none-eabi-size firmware.elf
arm-none-eabi-nm --size-sort -S firmware.elf
arm-none-eabi-objdump -h firmware.elf
```

重点观察：

```
.text      代码
.rodata    常量、字符串、命令表
.data      已初始化 RAM 数据
.bss       未初始化 RAM 数据
.noinit    不初始化数据
.stack     链接脚本保留栈
.heap      链接脚本保留堆
```

Zephyr 还应查看：

```
build/zephyr/zephyr.map
build/zephyr/.config
build/zephyr/zephyr.dts
```

RT-Thread 和 FreeRTOS 应查看：

```
map 文件
内核对象统计
堆剩余量
线程栈高水位
```

embOS 应结合对应版本工具和调试支持分析任务、栈和内核对象占用。

## 6.4 配置项的量化方法

不能直接说“打开日志增加 5 KB”，应采用对照构建：

```
Build A：基础配置
Build B：只打开一个功能
差值：Build B - Build A
```

例如：

|构建|配置|Flash|RAM|
|---|---|---|---|
|A|基础线程和 Tick|32.4 KB|8.1 KB|
|B|A + Shell|39.8 KB|10.6 KB|
|C|A + 日志|37.2 KB|9.4 KB|
|D|A + 文件系统|48.7 KB|14.9 KB|
|E|A + 网络|96.3 KB|35.2 KB|

以上数字仅为**测量格式示例**，不能作为通用 RTOS 数据。实际项目必须在目标平台上建立自己的基线。

## 6.5 Tick CPU 占用

```
U_tick = C_tick × f_tick / f_cpu
```

假设：

```
C_tick = 1200 cycles
f_tick = 1000 Hz
f_cpu = 120 MHz
```

则：

```
U_tick = 1200 × 1000 / 120000000
       = 1.0%
```

降低 Tick 频率可以降低固定开销，但会影响：

- 超时分辨率。
- 调度时间片。
- 低功耗唤醒策略。
- 软件定时器精度。
- 任务响应上界。

## 6.6 配置项对实时性的影响

|配置项|可能影响|
|---|---|
|Tick 频率增加|固定 ISR 开销增加|
|时间片开启|同优先级任务切换增加|
|日志同步输出|ISR/线程延迟增加|
|Trace 开启|Hook 和事件记录增加|
|栈检查|上下文或调度路径增加检查开销|
|网络 buffer 增加|RAM 增加，吞吐提升但缓存压力增大|
|系统工作队列|减少线程数量，但可能造成任务串行阻塞|
|用户态/MPU|系统调用和切换成本增加，但安全性提高|
|tickless|空闲功耗降低，但唤醒和时间补偿复杂度增加|

## 6.7 栈预算公式

```
Stack_required =
    Maximum_call_depth
  + Interrupt_nesting
  + Library_usage
  + FPU_context
  + Logging_path
  + Error_path
  + Safety_margin
```

建议安全余量：

```
Stack_margin =
    max(实际峰值 × 20%,
        固定最小余量)
```

具体比例应通过项目风险等级和测试覆盖确定，不能机械使用。

## 6.8 瓶颈分析

### Flash 瓶颈

常见来源：

- 日志格式化。
- printf 浮点支持。
- Shell 命令表。
- 网络协议栈。
- 文件系统。
- C++ 运行库。
- 异常处理和 RTTI。
- 未启用 LTO。
- 未启用链接垃圾回收。

优化方式：

```
关闭不需要的组件
  -> 关闭不使用的 API
  -> 关闭浮点格式化
  -> 使用 -ffunction-sections/-fdata-sections
  -> 使用 --gc-sections
  -> 评估 LTO
  -> 减少重复字符串
```

### RAM 瓶颈

常见来源：

- 线程栈。
- 网络 buffer。
- 日志缓冲区。
- Shell 输入和历史缓冲区。
- 文件系统缓存。
- DMA 双缓冲。
- 通用堆。
- 大量内核对象。

优化方式：

- 降低线程数量。
- 使用事件驱动。
- 固定块内存池。
- 缩小队列长度。
- 根据实测高水位调整栈。
- 将只读数据放入 Flash。
- 将大缓冲区放入合适的外部 RAM。
- 区分高速实时 RAM 和普通缓存 RAM。

---

# 7. 应用场景选型指南

## 7.1 决策流程图

```
开始
 |
 |-- 产品是否有严格的 RAM/Flash 上限？
 |       |-- 是：先建立资源预算，再选择最小功能集合
 |       |-- 否：仍需建立基线，避免组件无边界增长
 |
 |-- 任务和内核对象是否固定？
 |       |-- 是：静态对象 + 固定内存池优先
 |       |-- 否：受控动态内存 + 失败恢复
 |
 |-- 是否需要网络、文件系统、USB、蓝牙？
 |       |-- 是：启用对应组件，并拆分 buffer/线程/栈预算
 |       |-- 否：关闭相关 Kconfig/组件/驱动
 |
 |-- 是否需要 Shell 和详细日志？
 |       |-- 开发阶段：开启
 |       |-- 测试阶段：开启诊断，关闭高成本同步输出
 |       |-- 量产阶段：按安全需求关闭或只保留只读诊断
 |
 |-- 是否要求严格实时？
 |       |-- 是：降低后台组件、关闭同步日志、限制临界区
 |       |-- 否：允许更丰富的协议、Shell 和日志
 |
 |-- 是否需要低功耗？
 |       |-- 是：评估 tickless、PM、RTC/LPTIM 和唤醒成本
 |       |-- 否：先建立固定 Tick 性能基线
 |
 |-- 是否需要 MPU/TrustZone/用户态？
         |-- 是：预留额外栈、切换和系统调用开销
         |-- 否：优先简化实时路径
```

## 7.2 场景选型

|场景|推荐配置策略|理由|
|---|---|---|
|小型控制器|静态任务、固定 IPC、关闭 Shell/网络|RAM/Flash 可预测|
|工业采集器|DMA、固定内存池、延迟日志|采样实时性和长期稳定性|
|网络网关|网络 buffer、专用线程、异步日志|提升吞吐并降低阻塞|
|OTA 设备|文件系统/Flash/校验/回滚|功能完整但资源预算较大|
|安全设备|MPU/TrustZone、保留断言和故障记录|保护边界和可诊断性|
|低功耗传感器|tickless、RTC、最小线程和组件|降低唤醒次数|
|开发平台|全量诊断、Shell、Trace|提升调试效率|
|量产固件|关闭高成本调试组件、保留关键监控|平衡资源和可维护性|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：先做配置矩阵，再写配置文件

建立如下表格：

|功能|是否需要|依赖|RAM 影响|Flash 影响|实时性影响|验证方式|
|---|---|---|---|---|---|---|
|抢占调度|是|架构端口|低|中|影响调度|抢占测试|
|软件定时器|是|Tick、Timer 线程|中|中|增加后台线程|超时测试|
|Shell|开发需要|UART、线程|中|中|输出可能阻塞|Shell 回归|
|网络|是|网卡、buffer|高|高|增加线程和中断|吞吐测试|
|文件系统|是|Flash/块设备|中|高|可能阻塞|掉电测试|
|Trace|测试需要|Hook/缓冲区|中|中|增加事件开销|性能对比|

### 原则二：配置文件分层

建议：

```
common/
  基础内核配置

board/
  板级硬件配置

product/
  产品功能配置

debug/
  调试配置

test/
  测试配置

release/
  量产配置
```

不要把所有配置都塞进一个不断增长的文件。

### 原则三：开发、测试、量产配置分离

```
开发版：
  Shell、日志、断言、Trace、统计全部开启

测试版：
  保留诊断和故障注入，关闭同步高负载日志

量产版：
  关闭 Shell 写操作、高成本 Trace 和调试输出
  保留断言等效机制、看门狗、栈/堆错误记录
```

### 原则四：不要为了节省几 KB 关闭所有诊断

如果没有：

- 栈溢出检测。
- 动态内存失败处理。
- 设备初始化失败记录。
- HardFault 信息。
- 看门狗复位原因。

系统即使尺寸更小，也可能无法维护。

### 原则五：配置应当可以被机器检查

CI 应检查：

- 禁止配置组合。
- Flash/RAM 上限。
- 必须启用的安全配置。
- 不允许在量产版开启的 Shell 命令。
- Tick 和 CPU 时钟一致性。
- 网络 buffer 和 RAM 预算。
- 所有设备节点状态。
- 线程栈最小值。

## 8.2 四类 RTOS 的配置最佳实践

### FreeRTOS

- `FreeRTOSConfig.h` 与目标端口放在明确路径。
- 用静态分配固定核心对象。
- 只打开实际使用的 `INCLUDE_xxx` API。
- 用 `configASSERT`、栈溢出检测和 malloc 失败 hook。
- 控制 `configMAX_PRIORITIES`。
- 不用 `configUSE_TRACE_FACILITY` 替代完整性能分析。
- Tickless 必须配合目标 port 验证。

### RT-Thread

- 区分内核、BSP、组件和应用配置。
- 使用 RT-Thread 的配置工具生成配置，但审查最终 `rtconfig.h`。
- 关闭不用的 FinSH、文件系统、网络和软件包。
- 对自动初始化函数的失败返回值进行检查。
- 设备框架与底层驱动不要混为一层。
- 固定消息优先使用内存池。

### embOS

- 严格使用当前版本官方配置和 CPU port 文档。
- 不复制其他版本或其他 RTOS 的配置宏。
- 保存官方示例和本地修改的差异。
- 记录授权包和交付范围。
- 不在缺少文档依据时关闭端口相关功能。
- 以实际工具和官方调试能力验证任务栈、Tick 和切换。

### Zephyr

- 只修改源配置，不修改生成的 `.config` 和 `zephyr.dts`。
- Kconfig 负责功能，Devicetree 负责硬件。
- overlay、Board DTS、SoC DTSI 分层。
- 使用 `west build -t pristine` 验证配置变更。
- 以 `build/zephyr/.config` 和 `build/zephyr/zephyr.dts` 为最终证据。
- 为网络、蓝牙、USB、文件系统分别建立 RAM 预算。

## 8.3 工业级编码规范

- 所有配置宏使用统一命名和注释。
- 禁止在业务代码中散落大量 Board 条件编译。
- 配置失败时尽量在构建阶段报错。
- 对互斥配置使用静态断言或 Kconfig 依赖。
- 任务栈、堆、消息队列长度使用命名常量。
- 所有动态资源分配都检查返回值。
- 配置修改必须产生可审计的变更记录。
- 不把构建目录中的生成文件提交为手工维护源文件。
- 量产配置不能通过“删掉调试代码”临时生成，应有正式配置入口。
- 配置和版本必须与固件镜像一起记录。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：只关闭宏，不检查依赖

错误示例：

```
#define configUSE_TIMERS 0
```

但应用仍然调用软件定时器 API，或者某组件依赖 Timer Service。

### 根因

配置项关闭后，依赖代码没有同步修改。

### 正确实现

```
搜索所有定时器 API
  -> 搜索组件依赖
  -> 关闭或替换业务路径
  -> 构建验证
  -> 超时和故障恢复回归
```

### 风险影响

- 编译失败。
- 链接失败。
- 组件启动失败。
- 运行时超时逻辑失效。

## 9.2 错误二：为了节省资源关闭断言和栈检测

错误示例：

```
#define configASSERT(x)
#define configCHECK_FOR_STACK_OVERFLOW 0
```

或在其他 RTOS 中完全关闭等效检查。

### 根因

只统计了检查代码的资源成本，没有评估故障定位和产品维护成本。

### 正确实现

开发和测试阶段开启；量产版可降低检查频率，但保留：

- 栈边界检测。
- 关键断言。
- 故障记录。
- 看门狗复位原因。
- 线程或任务异常计数。

### 风险影响

- 栈溢出变成随机内存破坏。
- 配置错误无法定位。
- 现场问题无法复现。
- 设备长期运行稳定性下降。

## 9.3 错误三：降低 Tick 频率后没有重新验证超时语义

错误示例：

```
#define configTICK_RATE_HZ 1000
/* 改为 100 后未检查所有超时和周期任务。 */
#define configTICK_RATE_HZ 100
```

### 根因

代码中把 Tick 数直接当作毫秒，或者依赖高频 Tick 的时间粒度。

### 正确实现

统一使用时间换算：

```
#define MS_TO_TICKS(ms) \
    ((TickType_t)(((uint64_t)(ms) * configTICK_RATE_HZ) / 1000U))
```

并检查：

- 1 ms 延时是否仍然有意义。
- 周期任务是否允许 10 ms 粒度。
- 软件定时器是否满足精度。
- Tick 计数溢出处理。
- 低功耗唤醒误差。

### 风险影响

- 超时提前或延后。
- 周期任务节拍改变。
- 通信协议超时失效。
- 控制逻辑不稳定。

## 9.4 错误四：把任务栈配置按字节或字为单位误解

错误示例：

```
xTaskCreate(worker, "worker", 512U, NULL, 2U, NULL);
```

调用者误认为 512 表示 512 字节。

或在 Zephyr 中：

```
static uint8_t stack[1024];
```

直接替代 `K_THREAD_STACK_DEFINE()`。

### 根因

不同 RTOS、不同 API 对栈大小单位和栈对象布局的定义不同。

### 正确实现

- FreeRTOS：核对 `StackType_t` 和 API 说明。
- RT-Thread：核对线程栈参数单位和 BSP 模板。
- embOS：核对当前版本 API 和 CPU port。
- Zephyr：使用 `K_THREAD_STACK_DEFINE()` 与 `K_THREAD_STACK_SIZEOF()`。

### 风险影响

- RAM 预算错误。
- 栈溢出。
- MPU/用户态启动失败。
- 随机 HardFault。

## 9.5 错误五：关闭日志后失去所有诊断

错误示例：

```
CONFIG_LOG=n
```

或直接删除所有错误记录。

### 根因

把“关闭同步日志”误解为“删除故障诊断”。

### 正确实现

区分：

```
同步日志输出
异步日志输出
故障计数
故障快照
看门狗记录
复位原因
关键状态持久化
```

量产版可以关闭 UART 输出，但保留 RAM/Flash 故障记录。

### 风险影响

- 现场故障无法定位。
- 设备静默失败。
- OTA 后问题无法归因。
- 看门狗复位只能看到“复位”，不知道原因。

## 9.6 错误六：Zephyr 直接修改生成文件

错误示例：

```
手动修改：
build/zephyr/.config
build/zephyr/zephyr.dts
```

### 根因

误把生成结果当作配置源。

### 正确实现

- Kconfig 改 `prj.conf`、Board defconfig 或 fragment。
- Devicetree 改 `.dts`、`.dtsi` 或 overlay。
- 使用 pristine build。
- 检查生成结果。

### 风险影响

- 本地构建有效，CI 失败。
- 配置不可复现。
- 清理构建后功能消失。

## 9.7 错误七：RT-Thread 关闭组件但保留初始化依赖

错误示例：

```
/* 关闭 FinSH */
#define RT_USING_FINSH 0
```

但仍然：

```
rt_console_set_device("uart1");
finsh_set_device("uart1");
```

### 根因

组件关闭后，BSP 或应用仍执行组件初始化路径。

### 正确实现

使用同一配置条件包围依赖代码：

```
#ifdef RT_USING_FINSH
    finsh_set_device("uart1");
#endif
```

同时检查自动初始化函数和设备注册。

### 风险影响

- 编译失败。
- 空指针调用。
- 启动阶段设备初始化顺序错误。

## 9.8 错误八：embOS 直接使用未经版本确认的配置宏

错误示例：

```
#define OS_USE_TRACE 0
#define OS_USE_HEAP  0
```

### 根因

从其他版本、网络文章或其他 RTOS 推断 embOS 配置接口。

### 正确实现

```
查看当前 embOS 用户手册
  -> 查看 CPU port 文档
  -> 查看官方示例工程
  -> 确认配置项是否存在
  -> 修改后执行官方测试和性能回归
```

### 风险影响

- 配置宏不生效。
- 编译路径与预期不一致。
- 误关闭端口依赖。
- 违反授权包或工程约束。

---

# 10. 多机制组合使用方案

## 10.1 统一的产品配置架构

建议将四类 RTOS 的配置抽象为相同的产品层：

```
产品需求
  |
  |-- RTOS 核心能力
  |-- 设备和驱动能力
  |-- 调试和诊断能力
  |-- 安全能力
  |-- 低功耗能力
  |-- 网络/文件系统能力
  |
配置矩阵
  |
  |-- FreeRTOSConfig.h
  |-- RT-Thread rtconfig.h/Kconfig
  |-- embOS 官方工程配置
  |-- Zephyr prj.conf/overlay
  |
最终镜像
```

## 10.2 统一功能配置矩阵

```
struct rtos_feature_policy
{
    bool preemptive;
    bool time_slicing;
    bool dynamic_memory;
    bool shell;
    bool logging;
    bool tracing;
    bool networking;
    bool filesystem;
    bool low_power;
    bool memory_protection;
};
```

产品可以维护一份逻辑配置：

```
产品配置：
  PREEMPTIVE = 1
  TIME_SLICING = 0
  DYNAMIC_MEMORY = 0
  SHELL = 0
  LOGGING = 1
  TRACE = 0
  NETWORKING = 1
  FILESYSTEM = 1
  LOW_POWER = 0
  MEMORY_PROTECTION = 1
```

然后由不同 RTOS 工程映射到各自的配置系统。

这不会替代各 RTOS 的配置文件，但能够避免四套产品变体策略完全漂移。

## 10.3 统一资源预算框架

```
产品 RAM 上限
  |
  |-- RTOS 内核固定 RAM
  |-- 线程栈
  |-- IPC 对象
  |-- 驱动状态
  |-- DMA 缓冲区
  |-- 网络/文件系统 buffer
  |-- 日志缓冲区
  |-- 安全和故障记录
  |-- 安全余量
```

建议建立机器可读表格：

```
struct rtos_budget
{
    uint32_t flash_limit;
    uint32_t ram_limit;
    uint32_t stack_limit;
    uint32_t heap_limit;
    uint32_t network_buffer_limit;
    uint32_t log_buffer_limit;
};
```

CI 中检查：

```
实际 Flash <= 配置上限
实际 RAM <= 配置上限
每个任务栈高水位 <= 预算阈值
堆最小剩余量 >= 规定阈值
队列峰值 <= 配置长度
```

## 10.4 配置变体管理

推荐配置变体：

```
config/
  common/
    realtime.conf
    memory_static.conf
  development/
    debug.conf
    shell.conf
    trace.conf
  test/
    fault_injection.conf
    stress.conf
  production/
    release.conf
    security.conf
```

映射关系：

|逻辑配置|FreeRTOS|RT-Thread|embOS|Zephyr|
|---|---|---|---|---|
|静态内存|`configSUPPORT_STATIC_ALLOCATION`|静态对象/内存池|按版本配置|固定对象/内存池|
|抢占|`configUSE_PREEMPTION`|抢占配置|官方端口配置|Kconfig|
|Shell|外部组件|FinSH/MSH|配套组件|Shell Kconfig|
|日志|外部日志/Trace|RT-Thread log|工具/组件|Logger|
|低功耗|port/tickless|PM/tickless|版本支持|PM/tickless|
|MPU|Cortex-M port|架构/平台支持|CPU port|用户态/MPU|

---

# 11. 工业级实际案例分析

## 11.1 案例一：资源受限的电机控制器

### 需求

- Cortex-M4F。
- Flash 256 KB。
- RAM 64 KB。
- 3 个实时控制线程。
- 1 个通信线程。
- 1 个诊断线程。
- 不需要文件系统、网络和 Shell。
- 需要保留故障记录和栈检测。

### 配置策略

```
抢占调度：开启
时间片：关闭或仅用于后台线程
Tick：1 kHz
动态堆：关闭
任务：静态创建
消息：固定内存池
日志：异步、限速
Shell：关闭
网络：关闭
文件系统：关闭
Trace：测试版开启，量产版关闭
栈检测：保留
看门狗：保留
```

### 设计重点

- 控制路径不使用通用动态分配。
- ADC/PWM 触发采用硬件定时器。
- ISR 只执行安全判断和数据搬运。
- 诊断线程只能低优先级运行。
- 量产版保留故障码、复位原因和最后一次异常上下文。
- 栈高水位通过最大控制算法、日志和错误路径测试确认。

### 资源预算

```
控制线程栈：3 × 2048 B
通信线程栈：4096 B
诊断线程栈：2048 B
系统/空闲线程栈：预留
DMA 缓冲区：8 KB
故障记录：4 KB
消息池：4 KB
内核对象和驱动状态：预算
安全余量：至少一部分 RAM
```

具体值必须根据编译器、优化等级和调用路径实测。

## 11.2 案例二：工业网关

### 需求

- 以太网、CAN、UART。
- 网络协议栈。
- 文件系统。
- OTA。
- 远程日志。
- 设备运行数月不重启。

### 配置策略

```
动态内存：限制使用
网络 buffer：专用池
文件系统 cache：固定上限
日志：异步
Shell：仅维护版本开放
线程：按协议和优先级拆分
OTA：独立状态机和存储线程
看门狗：保留
运行时统计：保留关键数据
```

### 四类 RTOS 的落地差异

#### FreeRTOS

- 需要选择网络栈。
- 通过 `FreeRTOSConfig.h` 配置内核。
- 网络 buffer 和协议栈由外部组件管理。
- 需要额外建立设备和日志配置体系。

#### RT-Thread

- 可使用设备框架、网络、文件系统、FinSH 和 OTA 组件。
- 需要严格控制组件自动初始化和堆使用。
- 建议网络包和协议对象使用专用内存池。

#### embOS

- 具体网络和文件系统能力取决于产品集成包。
- 需要确认相关组件是否与当前 embOS 版本、工具链和授权范围匹配。
- 不能仅通过关闭某个内核宏推断组件已经裁剪。

#### Zephyr

- 使用 Kconfig 管理网络、文件系统、日志和 OTA 相关功能。
- 使用 Devicetree 描述各总线、PHY、Flash 分区。
- 使用 sysbuild 管理引导程序和主应用镜像。
- 重点检查生成的 `.config`、DTS 和 Flash 分区。

## 11.3 案例三：低功耗传感器节点

### 需求

- 运行时间大部分处于睡眠。
- 每 10 秒唤醒采样。
- 异常 GPIO 可立即唤醒。
- 无网络，仅使用低功耗无线模块。
- 需要记录电池电压和复位原因。

### 配置策略

```
Tickless：开启
RTC/LPTIM：独立低功耗时钟
日志：只保留故障日志
Shell：开发版开启，量产版关闭
线程：减少到采样、通信和故障处理
动态内存：关闭
设备电源管理：开启
唤醒源：统一管理
```

### 风险

- 低功耗唤醒后时钟没有恢复。
- Tick 补偿误差。
- 无线模块恢复耗时超过业务窗口。
- 睡眠前 DMA 或 SPI 传输尚未结束。
- 日志输出阻止进入深睡眠。
- 配置裁剪后故障记录路径消失。

---

# 12. 高频问题深度答疑

## Q1：如何判断一个功能是否应该裁剪？

采用四个问题：

```
是否有业务需求？
是否被其他组件间接依赖？
关闭后是否影响调试和故障恢复？
运行时资源成本是否超过收益？
```

例如 Shell：

- 量产业务可能不需要。
- 但开发和测试阶段非常重要。
- 量产版可以改成只读诊断接口，而不是简单删除所有诊断能力。

## Q2：为什么关闭一个功能后 Flash 几乎没有减少？

常见原因：

- 功能仍被其他组件依赖。
- 使用了强引用。
- 链接器没有启用 `--gc-sections`。
- 该功能只有少量代码，主要占用的是 RAM。
- 日志字符串和错误路径仍然保留。
- LTO 或优化策略不同导致差异被其他代码抵消。
- 生成的镜像包含对齐和固定分区浪费。

应进行 A/B 构建并使用 `nm`、map 文件定位实际差异。

## Q3：为什么关闭日志后 RAM 仍然很高？

日志可能不是主要 RAM 来源。还要检查：

- 线程栈。
- 网络 buffer。
- 文件系统 cache。
- DMA 双缓冲。
- 通用堆。
- Shell 输入缓冲区。
- 工作队列。
- 内核对象。
- 静态大数组。

不要只根据配置名称判断资源消耗。

## Q4：为什么不能把所有功能都编译进来，运行时不用就行？

因为未使用功能也可能带来：

- Flash 占用。
- 静态 RAM。
- 初始化时间。
- 额外线程。
- 额外中断。
- 额外锁竞争。
- 更大的攻击面。
- 更复杂的测试矩阵。
- 更高的升级和维护成本。

工业产品应当按功能边界构建镜像，而不是把所有能力打进一个固件。

## Q5：Tick 频率应该怎么选？

根据以下因素联合决定：

```
最小软件超时时间
  + 时间片需求
  + 软件定时器精度
  + 低功耗策略
  + Tick ISR 成本
  + 调度延迟预算
```

如果控制周期为 50 us，不应简单把 Tick 提高到 20 kHz。更合理的方案通常是硬件定时器或 DMA 产生控制事件，RTOS Tick 只负责线程和超时管理。

## Q6：动态内存是否应该完全禁止？

不是绝对规则。

适合禁止动态内存：

- 任务和对象固定。
- 安全关键系统。
- RAM 必须在构建期完全核算。
- 产品长期运行且不能容忍碎片。

适合受控使用动态内存：

- 设备数量变化。
- 网络包和协议对象生命周期动态。
- 文件系统和协议栈需要运行期分配。
- 有经过验证的内存池或分区堆。

关键不在“是否动态”，而在于：

- 分配是否有界。
- 失败是否可恢复。
- 碎片是否可测量。
- 生命周期是否清晰。
- 中断路径是否禁止分配。

## Q7：为什么开发版和量产版不能只通过 `#ifdef DEBUG` 区分？

因为量产差异通常不仅是一个宏：

- Shell 权限不同。
- 日志输出路径不同。
- 安全功能不同。
- 看门狗策略不同。
- OTA 和调试接口不同。
- 诊断数据保存方式不同。
- 编译优化和 LTO 不同。
- MPU/TrustZone 配置不同。

应建立正式的配置变体，并对每个变体执行构建和测试。

## Q8：如何保证四种 RTOS 的产品配置一致？

建立平台无关的逻辑配置，再映射到各 RTOS：

```
PRODUCT_PREEMPTIVE
PRODUCT_ENABLE_SHELL
PRODUCT_ENABLE_NETWORK
PRODUCT_ENABLE_FILESYSTEM
PRODUCT_ENABLE_DYNAMIC_MEMORY
PRODUCT_ENABLE_LOW_POWER
PRODUCT_ENABLE_TRACE
```

然后分别生成：

```
FreeRTOSConfig.h
RT-Thread rtconfig.h/Kconfig
embOS 工程配置
Zephyr prj.conf/overlay
```

同时用统一资源预算和测试用例验证，而不是要求四种 RTOS 的宏名称相同。

## Q9：embOS 配置为什么不能像 FreeRTOS 一样直接查宏名？

因为 embOS 的具体配置项受版本、工具链、CPU port、工程模板和授权包影响。FreeRTOS 的配置模型公开且集中，embOS 的端口和工程集成边界可能不同。正确做法是：

```
版本手册
  -> CPU port 文档
  -> 官方示例
  -> 工程预处理结果
  -> map 文件
```

不能根据网络文章或其他版本的宏名直接修改。

---

# 13. 课程核心总结

## 核心要点

1. RTOS 配置与裁剪必须同时分析：
    
    - 功能。
    - 依赖。
    - Flash。
    - RAM。
    - 实时性。
    - 诊断。
    - 安全。
    - 维护成本。
2. 四类 RTOS 的核心差异：
    

```
FreeRTOS：
  配置集中，宏控制直接。

RT-Thread：
  内核、BSP、设备框架和组件共同配置。

embOS：
  配置高度依赖版本、CPU port、工具链和授权工程。

Zephyr：
  Kconfig + Devicetree + CMake/west 共同生成系统。
```

3. 关闭功能前必须验证：
    
    - 是否存在间接依赖。
    - 是否影响初始化顺序。
    - 是否影响异常路径。
    - 是否影响调试和故障恢复。
    - 是否真的降低资源占用。
4. 最可靠的裁剪方法是：
    

```
建立基线
  -> 只修改一个配置项
  -> 全量构建
  -> 对比 Flash/RAM/map
  -> 执行功能和性能测试
  -> 记录结果
```

5. 生产系统通常推荐：

```
固定任务静态创建
  + 固定大小对象使用内存池
  + 动态堆受控使用
  + 日志异步化
  + Shell 受权限控制
  + 栈和堆错误检测保留
  + 配置可生成、可审计、可回归
```

## 资源和性能的一般排序

### 资源可预测性

```
全静态
  > 固定内存池
  > 分区堆
  > 通用动态堆
```

### 配置复杂度

```
FreeRTOS
  < RT-Thread
  < embOS 版本/工程依赖
  < Zephyr Kconfig + Devicetree + 模块
```

这个排序描述的是配置复杂度，不是运行性能。

### 适合的产品方向

|RTOS|配置裁剪优势|
|---|---|
|FreeRTOS|小型 MCU、固定功能、内核轻量|
|RT-Thread|设备框架和组件组合|
|embOS|商业支持、端口稳定、产品工程集成|
|Zephyr|多硬件、多组件、统一配置和上游生态|

---

# 14. 快速参考速查表

## 14.1 配置入口速查

|RTOS|首要检查文件|
|---|---|
|FreeRTOS|`FreeRTOSConfig.h`、port、heap 实现|
|RT-Thread|`rtconfig.h`、BSP 配置、组件 Kconfig|
|embOS|当前版本手册、CPU port、官方工程模板|
|Zephyr|`prj.conf`、Board Kconfig、DTS、overlay、`.config`|

## 14.2 裁剪顺序

```
1. 删除不需要的产品功能
2. 关闭对应组件
3. 关闭对应驱动
4. 关闭对应调试接口
5. 缩小线程栈和队列
6. 选择静态对象或内存池
7. 优化日志和字符串
8. 启用链接垃圾回收/LTO
9. 检查 Flash/RAM
10. 执行功能、实时性和故障回归
```

## 14.3 资源检查表

|检查项|验证手段|
|---|---|
|Flash 使用量|`size`、map、段统计|
|RAM 使用量|map、链接脚本、运行时统计|
|线程栈|高水位、栈保护、压力测试|
|堆|当前使用、峰值、最大空闲块|
|消息队列|最大深度、丢包计数|
|网络 buffer|峰值占用、内存池余量|
|日志|缓冲区占用、丢日志计数|
|Tick|DWT/GPIO 测量|
|调度|任务切换周期和最大延迟|
|中断|ISR 延迟和临界区长度|

## 14.4 量产配置建议

|功能|建议|
|---|---|
|抢占调度|根据需求保留|
|时间片|只在确有需求时开启|
|Tick|按实时性和功耗平衡|
|动态堆|受控使用或关闭|
|Shell|默认关闭或只读|
|日志|异步、分级、限速|
|Trace|通常关闭，保留必要统计|
|断言|保留关键断言和故障记录|
|栈检测|尽量保留|
|看门狗|保留并记录复位原因|
|网络|按产品需求开启|
|文件系统|按升级、配置和日志需求开启|
|MPU/TrustZone|按安全边界开启|

---

# 15. 学习效果自检

完成本课后，应能完成以下任务：

- 说明四种 RTOS 的配置模型差异。
- 解释 Kconfig、Devicetree、`FreeRTOSConfig.h`、`rtconfig.h` 的职责。
- 能建立一个内核功能依赖矩阵。
- 能区分 Flash、RAM、CPU 和实时性四类成本。
- 能计算 Tick、任务切换和线程栈的基础预算。
- 能为固定任务系统选择静态对象和内存池方案。
- 能为动态协议对象选择受控动态内存方案。
- 能判断 Shell、日志、Trace 是否应在量产版保留。
- 能通过 map 文件确认裁剪是否真正生效。
- 能从 Zephyr `.config` 和 `zephyr.dts` 定位配置问题。
- 能按照当前版本资料确认 embOS 配置项，而不是猜宏名称。
- 能识别关闭配置后可能残留的间接依赖。
- 能设计开发版、测试版和量产版配置。
- 能为配置建立 CI 检查和资源预算门禁。
- 能设计裁剪后的功能、性能和故障注入测试。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：建立四类 RTOS 的最小基线

分别完成：

```
FreeRTOS：
  一个静态任务 + 一个 Tick

RT-Thread：
  一个线程 + 一个设备初始化

embOS：
  使用官方示例启动两个任务

Zephyr：
  一个 Board + 一个 GPIO + 一个线程
```

记录：

- Flash。
- RAM。
- Tick CPU 占用。
- 任务栈。
- 启动时间。
- 最小依赖集合。

### 任务二：单变量裁剪实验

每次只修改一个配置项：

```
开启/关闭 Shell
开启/关闭日志
开启/关闭软件定时器
开启/关闭消息队列
开启/关闭网络
开启/关闭文件系统
开启/关闭 Trace
开启/关闭动态内存
```

每次记录：

```
Flash 差值
RAM 差值
线程数量变化
初始化时间变化
最大响应延迟变化
功能回归结果
```

### 任务三：建立资源预算表

为每个产品版本建立：

```
Flash 上限
RAM 上限
任务数量
每个任务栈
内核对象数量
DMA 缓冲区
网络 buffer
日志 buffer
堆上限
安全余量
```

并在构建后自动检查。

### 任务四：开发版到量产版迁移

建立三套配置：

```
development
test
production
```

验证：

- 开发版能使用 Shell 和详细日志。
- 测试版能执行故障注入。
- 量产版关闭高风险维护命令。
- 量产版保留故障记录和看门狗。
- 三个版本均能独立构建。
- 三个版本均通过核心功能回归。

### 任务五：裁剪后故障注入

至少测试：

```
任务栈接近边界
动态内存分配失败
内存池耗尽
消息队列满
设备初始化失败
Tick 延迟
日志缓冲区满
DMA buffer overrun
看门狗复位
低功耗唤醒失败
```

### 任务六：配置 CI 门禁

建议自动执行：

```
检查 RTOS 版本
检查配置文件差异
检查禁止配置组合
检查 Flash/RAM 上限
检查栈大小下限
检查最终 Kconfig
检查最终 Devicetree
检查许可证和第三方清单
运行最小启动测试
运行线程切换测试
运行关键设备回归
```

## 16.2 性能测试方法

### A/B 构建

```
Build A：当前基线
Build B：只改变一个配置
比较：
  .text
  .rodata
  .data
  .bss
  堆
  栈
  初始化时间
  Tick 占用
  最大响应延迟
```

### 压力测试

- 最大任务同时就绪。
- 最大中断频率。
- 最大日志流量。
- 最大网络突发。
- 最大文件系统操作。
- 最大 DMA 吞吐。
- 低功耗频繁进出。
- 长时间运行 24 小时、72 小时或更长。

### 实时性测试

测量：

```
ISR 入口延迟
ISR 最大执行时间
线程唤醒延迟
任务切换时间
临界区最大时长
高优先级任务响应时间
Tick 最大抖动
```

### 内存测试

记录：

```
启动后最低剩余 RAM
运行期间堆峰值
最大连续空闲块
线程栈最小余量
消息队列最大深度
内存池最低余量
网络 buffer 峰值
```

## 16.3 进阶学习方向

- 研究链接器垃圾回收、LTO、函数段和数据段拆分。
- 研究 RTOS 内核配置项对调度路径的具体代码影响。
- 研究不同 Tick 频率下的调度抖动和低功耗收益。
- 研究固定块内存池、TLSF、分区堆和碎片分析。
- 研究 MPU、TrustZone-M、用户态和系统调用开销。
- 研究 Zephyr Kconfig 依赖、Devicetree binding 和 sysbuild。
- 研究 RT-Thread 组件自动初始化和设备框架裁剪。
- 研究 FreeRTOS heap 实现、静态对象和 trace facility。
- 研究 embOS 当前版本的官方配置体系、CPU port 和调试工具链。
- 建立完整的 RTOS 配置工程体系：

```
需求矩阵
  -> 配置矩阵
  -> 资源预算
  -> 变体生成
  -> 构建检查
  -> 硬件回归
  -> 性能回归
  -> 故障注入
  -> 量产发布
```