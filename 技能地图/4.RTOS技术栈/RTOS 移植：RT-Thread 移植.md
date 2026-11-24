
> 本课以 **RT-Thread 4.x、Cortex-M3/M4/M7、GCC 工具链**为主线，兼顾 RT-Thread Nano 与完整版本。RT-Thread 的目录结构、函数名和启动流程会随版本、架构端口及 BSP 模板变化，以下代码应作为**工程设计与验证模板**，最终以当前仓库中的 `libcpu`、BSP 和官方示例为准。

---

## 1. 学习目标

### 理解

- 理解 RT-Thread 的内核层、CPU 架构层、BSP 层、设备框架和组件层之间的职责边界。
- 理解 Cortex-M 上下文切换、异常入口、`MSP/PSP`、`PendSV`、系统 Tick 与线程调度之间的关系。
- 理解 RT-Thread 中线程、调度器、IPC、内存管理、设备驱动和自动初始化机制的协作方式。
- 理解 RT-Thread 与 FreeRTOS 在移植边界、对象模型、设备框架和工程组织方式上的差异。

### 掌握

- 能选择并裁剪适合目标芯片的 RT-Thread BSP。
- 能完成时钟、串口、Tick、异常向量、堆内存和线程调度的基本移植。
- 能正确实现 `rt_hw_context_switch_to()`、`rt_hw_context_switch()` 和 `rt_hw_context_switch_interrupt()` 所属端口机制。
- 能配置 RT-Thread 的静态内存、动态内存、组件初始化和设备注册。
- 能使用 FinSH、日志、断言、线程栈监测和故障转储验证移植质量。

### 精通

- 能通过反汇编、寄存器、栈帧和异常返回值定位启动失败、PendSV 异常、栈损坏和优先级配置错误。
- 能分析 Tick 延迟、调度延迟、临界区长度、线程栈水位和内存碎片。
- 能设计中断、DMA、设备驱动、线程和 IPC 的协同架构。
- 能针对高可靠、低功耗、高吞吐和多设备系统进行 RT-Thread 内核裁剪。

### 能够设计

- 能从零建立可维护的 RT-Thread BSP。
- 能制定 RT-Thread 移植验收标准和性能基线。
- 能设计适合产品生命周期的内存策略、驱动分层、初始化顺序和故障恢复机制。
- 能将 RT-Thread 适配到具有特殊异常模型、Cache、MPU、TrustZone 或多核特性的芯片平台。

---

## 2. 前置要求

### 知识要求

- C 语言：指针、结构体、函数指针、宏、链接属性、`volatile`、内存对齐。
- Cortex-M 异常模型：
    - 向量表。
    - `MSP` 与 `PSP`。
    - 异常自动压栈。
    - `EXC_RETURN`。
    - `PendSV`。
    - `SysTick`。
    - NVIC 优先级。
- 启动流程：
    - `Reset_Handler`。
    - `.data` 搬运。
    - `.bss` 清零。
    - 时钟初始化。
    - C 运行库初始化。
- 链接脚本：
    - RAM、Flash 区域。
    - 堆、栈和段布局。
    - 对齐与保留区域。
- RTOS 基础：
    - 线程状态。
    - 优先级调度。
    - 阻塞与唤醒。
    - 信号量、消息队列、事件。
    - 临界区和中断安全 API。

### 技能要求

- 能阅读 RT-Thread 源码中的 `src/`、`libcpu/`、`components/` 和 BSP 目录。
- 能使用 `nm`、`objdump`、map 文件和 GDB。
- 能查看 Cortex-M 的 `SCB`、`NVIC`、`SysTick`、`DWT` 和 fault 寄存器。
- 能使用示波器或逻辑分析仪测量 GPIO 时序。
- 能构建、下载并调试一个最小 BSP。

---

## 3. 技术概述

### 3.1 RT-Thread 的系统分层

RT-Thread 通常可以分为以下层次：

```
应用层
  ├── 应用线程
  ├── 业务状态机
  └── 设备访问、IPC、文件系统、网络协议

组件层
  ├── FinSH / MSH
  ├── 网络协议栈
  ├── 文件系统
  ├── USB
  ├── OTA
  ├── 设备框架
  └── 软件包生态

内核层
  ├── 线程调度
  ├── 时钟与 Tick
  ├── 信号量、互斥量、事件、邮箱、消息队列
  ├── 内存管理
  └── 定时器

CPU 架构层
  ├── 上下文切换
  ├── 中断进入与退出
  ├── 栈初始化
  ├── CPU 原子操作
  └── 架构相关临界区

BSP / 芯片支持层
  ├── 启动文件
  ├── 时钟
  ├── GPIO/UART/DMA/Timer
  ├── 中断控制器
  ├── 链接脚本
  └── board.c / drv_xxx.c
```

### 3.2 RT-Thread 的移植边界

RT-Thread 的移植通常包含四个边界：

|边界|主要内容|典型文件|
|---|---|---|
|CPU 架构端口|上下文切换、栈初始化、临界区|`libcpu/arm/cortex-m*/`|
|芯片 BSP|时钟、GPIO、UART、Tick、中断|`bsp/<vendor>/<board>/`|
|内核配置|线程数、Tick、IPC、堆、组件|`rtconfig.h`|
|构建系统|源码、宏、链接脚本、启动文件|`SConscript`、CMake、Makefile|

### 3.3 RT-Thread Nano 与完整版本

|维度|RT-Thread Nano|完整 RT-Thread|
|---|---|---|
|内核功能|基础线程、时钟、IPC、内存|内核 + 设备框架 + 组件|
|代码规模|小|较大|
|资源消耗|低|可按组件裁剪|
|适用场景|小型控制器、资源敏感产品|工业控制、网关、设备平台|
|驱动框架|通常由用户自行组织|提供统一设备模型|
|FinSH/MSH|通常不默认包含|可选|
|文件系统/网络|通常不包含|可选组件|
|移植难度|低至中|中至高|
|工程扩展性|需要自行搭建|较强|

### 3.4 RT-Thread 的核心对象模型

RT-Thread 内核对象通常包含：

- `rt_thread`：线程。
- `rt_timer`：定时器。
- `rt_semaphore`：信号量。
- `rt_mutex`：互斥量。
- `rt_event`：事件集。
- `rt_mailbox`：邮箱。
- `rt_messagequeue`：消息队列。
- `rt_memory`：内存管理对象。
- `rt_device`：设备对象。

这些对象通常通过统一的对象管理机制组织，内核能够通过对象类型和链表维护生命周期及调试信息。

---

## 4. 核心特性横向对比

### 4.1 RT-Thread 不同移植方式对比

|方案|适用范围|优点|风险|
|---|---|---|---|
|复用官方 BSP|芯片和开发板已有支持|启动、驱动、构建较完整|可能带有过多板级代码|
|基于同系列 BSP 修改|芯片型号相近、外设兼容|开发速度快|需核对时钟、中断和寄存器差异|
|基于 Nano 手动移植|资源小、需求简单|代码少、控制力强|设备框架和组件需自行补充|
|从架构端口开始移植|新芯片或新架构|灵活|上下文、异常和调度验证成本高|
|基于 CubeMX/SDK 生成 BSP|有厂商配置工具|外设初始化快|自动生成代码与 RT-Thread 初始化顺序可能冲突|

### 4.2 不同内存策略对比

|方案|分配速度|碎片风险|支持释放|多内存区域|适用场景|
|---|---|---|---|---|---|
|静态对象|编译期|无|不适用|可手工安排|安全关键、固定对象|
|Small Memory / first-fit 类|中|中|是|依实现而定|通用动态对象|
|内存池|快且可预测|低|是|可分池|固定大小消息和块|
|Slab|快|低|是|可分级|高频固定对象|
|Heap + 外部管理器|取决于实现|取决于实现|是|较灵活|复杂产品|
|外部 SRAM/PSRAM 区域|取决于总线和 Cache|取决于管理器|是|是|大缓存、帧缓冲|

### 4.3 RT-Thread 与 FreeRTOS 移植侧重点

|维度|RT-Thread|FreeRTOS|
|---|---|---|
|端口目录|`libcpu`|`portable`|
|BSP 组织|BSP 和设备框架较突出|通常由厂商工程组织|
|设备模型|原生 `rt_device` 框架|通常由应用或第三方框架提供|
|初始化机制|自动初始化宏较常见|通常显式初始化|
|Shell|FinSH/MSH|通常需外部集成|
|内核对象|统一对象体系|各对象类型独立但接口清晰|
|内存策略|静态、动态、内存池等|多种 heap 实现与静态 API|
|学习重点|BSP、设备框架、组件裁剪|port、config 和内核 API|
|主要移植风险|启动顺序、BSP 适配、设备注册|异常入口、优先级、heap 与 port|

---

## 5. 底层原理与功能特性深度解析

## 5.1 RT-Thread 启动流程

典型启动路径可以抽象为：

```
Reset_Handler
  |
  |-- 初始化栈、.data、.bss
  |
  |-- SystemInit()
  |
  |-- rtthread_startup()
        |
        |-- rt_hw_board_init()
        |     |-- 时钟
        |     |-- 堆
        |     |-- Tick 定时器
        |     |-- 控制台设备
        |
        |-- rt_application_init()
        |     |-- 应用初始化
        |
        |-- rt_system_timer_thread_init()
        |-- rt_system_scheduler_start()
              |
              |-- 选择最高优先级就绪线程
              |-- rt_hw_context_switch_to()
              |-- 不再返回
```

在不同 BSP 中，`rtthread_startup()` 可能由模板代码、启动文件或 `board.c` 间接调用。必须以当前工程实际调用链为准。

常见板级初始化结构：

```
#include <rtthread.h>
#include <board.h>

void rt_hw_board_init(void)
{
    SystemClock_Config();

    /* 初始化 Tick 所使用的硬件定时器或 SysTick。 */
    rt_hw_tick_init();

#if defined(RT_USING_HEAP)
    rt_system_heap_init((void *)HEAP_BEGIN, (void *)HEAP_END);
#endif

#ifdef RT_USING_CONSOLE
    rt_console_set_device(RT_CONSOLE_DEVICE_NAME);
#endif

    /* 初始化 GPIO、UART、DMA 等基础硬件。 */
    rt_hw_pin_init();
    rt_hw_usart_init();
}
```

这段代码的具体函数名会因 BSP 版本不同而变化。重要的是初始化顺序：

```
时钟
  -> 中断控制器
  -> Tick
  -> 堆
  -> 控制台
  -> 设备驱动
  -> 应用初始化
  -> 启动调度器
```

### 5.1.1 初始化顺序的工程约束

- 在堆初始化前，不要创建依赖动态内存的线程或设备对象。
- 在 Tick 初始化前，不要调用依赖时间阻塞的 API。
- 在串口设备注册前，不要使用依赖控制台的日志和 Shell。
- 在调度器启动前，可以创建线程，但不能假设线程已经运行。
- 中断向量和优先级必须在启用对应设备中断前完成配置。

---

## 5.2 Cortex-M 上下文切换

RT-Thread 在 Cortex-M 上通常采用以下机制：

- 当前线程使用 `PSP`。
- 异常处理使用 `MSP`。
- `PendSV` 执行延迟上下文切换。
- `SysTick` 负责推进系统 Tick。
- 中断中发生高优先级线程就绪时，设置 PendSV。
- 退出中断后，由 PendSV 完成线程切换。

### 5.2.1 线程初始栈

新线程第一次运行前，必须构造一个看起来像“异常返回现场”的栈帧。典型栈帧包括：

```
高地址
  xPSR
  PC：线程入口地址
  LR：线程退出处理函数
  R12
  R3
  R2
  R1
  R0：线程参数
  R4-R11：软件保存寄存器
低地址
```

其中：

- `xPSR` 通常设置 Thumb 位。
- `PC` 指向线程入口。
- `LR` 指向线程退出处理函数。
- `R0` 传递线程参数。
- `R4-R11` 初始为已知值，便于调试和检测。

示意代码如下：

```
static rt_uint32_t *
rt_hw_stack_init(void (*entry)(void *parameter),
                 void *parameter,
                 rt_uint8_t *stack_addr,
                 void (*texit)(void))
{
    rt_uint32_t *stk;

    /* 按 Cortex-M 要求进行 8 字节对齐。 */
    stk = (rt_uint32_t *)((rt_uint32_t)stack_addr & ~0x07UL);

    /* 预留并填写异常自动保存的栈帧。 */
    *(--stk) = 0x01000000UL;              /* xPSR，Thumb 状态 */
    *(--stk) = (rt_uint32_t)entry;        /* PC */
    *(--stk) = (rt_uint32_t)texit;        /* LR */
    *(--stk) = 0x12121212UL;              /* R12 */
    *(--stk) = 0x03030303UL;              /* R3 */
    *(--stk) = 0x02020202UL;              /* R2 */
    *(--stk) = 0x01010101UL;              /* R1 */
    *(--stk) = (rt_uint32_t)parameter;    /* R0 */

    /* 预留软件保存的 R4-R11。 */
    *(--stk) = 0x11111111UL;              /* R11 */
    *(--stk) = 0x10101010UL;              /* R10 */
    *(--stk) = 0x09090909UL;              /* R9 */
    *(--stk) = 0x08080808UL;              /* R8 */
    *(--stk) = 0x07070707UL;              /* R7 */
    *(--stk) = 0x06060606UL;              /* R6 */
    *(--stk) = 0x05050505UL;              /* R5 */
    *(--stk) = 0x04040404UL;              /* R4 */

    return stk;
}
```

这段代码是原理示例。官方 RT-Thread 端口可能使用不同的入栈顺序、宏封装或 FPU 处理。**必须与上下文恢复汇编严格匹配。**

### 5.2.2 上下文切换接口

RT-Thread 端口通常需要提供以下类型的能力：

```
void rt_hw_context_switch_to(rt_ubase_t to);
void rt_hw_context_switch(rt_ubase_t from, rt_ubase_t to);
void rt_hw_context_switch_interrupt(rt_ubase_t from, rt_ubase_t to);
```

不同版本的函数声明、参数类型和实现位置可能存在差异，但职责基本相同：

- `switch_to`：调度器第一次启动时切换到第一个线程。
- `switch`：线程上下文中主动发生调度时使用。
- `switch_interrupt`：在中断退出前请求切换。

常见实现思路：

```
static volatile rt_uint32_t rt_interrupt_from_thread;
static volatile rt_uint32_t rt_interrupt_to_thread;
static volatile rt_uint32_t rt_thread_switch_interrupt_flag;

void rt_hw_context_switch_interrupt(rt_ubase_t from,
                                     rt_ubase_t to)
{
    rt_interrupt_from_thread = from;
    rt_interrupt_to_thread = to;

    rt_thread_switch_interrupt_flag = 1U;

    /* 设置 PendSV，真正的寄存器保存和恢复在异常入口完成。 */
    SCB->ICSR = SCB_ICSR_PENDSVSET_Msk;
    __DSB();
    __ISB();
}
```

PendSV 伪代码：

```
PendSV_Handler:
    ; 读取 PSP
    ; 保存当前线程的 R4-R11
    ; 保存更新后的 PSP 到 from 线程控制块

    ; 调用或读取调度结果
    ; 从 to 线程控制块恢复 PSP
    ; 恢复 R4-R11
    ; 写回 PSP
    ; 异常返回，恢复硬件自动保存的寄存器
```

真实实现通常必须处理：

- Handler 模式和 Thread 模式差异。
- 是否已进入中断嵌套。
- `BASEPRI`/`PRIMASK` 保存与恢复。
- FPU 的惰性压栈。
- 栈 8 字节对齐。
- 编译器汇编语法。
- 指令屏障和数据屏障。
- TrustZone 的安全/非安全状态。

### 5.2.3 第一次启动和普通切换的区别

第一次启动没有“当前线程”可保存，因此通常直接加载目标线程的栈指针：

```
rt_system_scheduler_start()
  -> 选择最高优先级就绪线程
  -> rt_hw_context_switch_to()
  -> 设置 PSP
  -> 异常返回或汇编跳转
  -> 进入线程入口
```

普通线程切换则需要：

```
当前线程
  -> 保存上下文
  -> 更新当前线程栈指针
  -> 调度器选择目标线程
  -> 恢复目标线程栈指针
  -> 恢复上下文
  -> 返回目标线程
```

---

## 5.3 Tick 与调度机制

### 5.3.1 Tick 的职责

RT-Thread 的系统 Tick 主要负责：

- 推进全局时间计数。
- 处理延时线程。
- 处理软件定时器。
- 触发时间片轮转。
- 唤醒超时线程。
- 在必要时触发调度。

典型 Tick 中断结构：

```
void SysTick_Handler(void)
{
    rt_interrupt_enter();

    /* 具体 API 以当前 RT-Thread 版本为准。 */
    rt_tick_increase();

    rt_interrupt_leave();
}
```

某些 BSP 会通过 `rt_hw_timer_isr()`、`rt_tick_increase()` 或定制的 Tick 处理函数完成相同工作。不要在不同版本间直接复制函数名。

### 5.3.2 Tick 频率选择

设：

```
f_tick = RT_TICK_PER_SECOND
T_tick = 1 / f_tick
```

常见取值：

|Tick 频率|Tick 周期|适用情况|
|---|---|---|
|100 Hz|10 ms|低速采集、非严格实时|
|250 Hz|4 ms|通用控制|
|500 Hz|2 ms|较高响应要求|
|1000 Hz|1 ms|常规工业控制|
|2000 Hz 以上|小于 0.5 ms|必须有测量依据|

Tick 越高，时间分辨率越高，但固定中断开销也越大。高频控制回路不应简单依赖提高 RTOS Tick，而应使用硬件定时器、DMA 或专用控制中断。

### 5.3.3 Tickless 低功耗

RT-Thread 的低功耗组件通常会根据下一个超时事件计算预计睡眠时间：

```
当前 Tick
  -> 查找最近的超时事件
  -> 关闭或降低系统 Tick 唤醒频率
  -> 进入低功耗模式
  -> 外部中断/低功耗定时器唤醒
  -> 计算实际睡眠时间
  -> 补偿 Tick
  -> 恢复调度
```

低功耗 Tick 的关键风险：

- 低功耗时钟频率误差。
- 睡眠前后的定时器重配置误差。
- 唤醒延迟。
- 长时间 Tick 计数溢出。
- 外部中断在睡眠前后产生的竞态。
- Cache、DMA 和电源域恢复顺序错误。

---

## 5.4 中断嵌套与 RT-Thread API 约束

RT-Thread 通常通过：

```
rt_interrupt_enter();
...
rt_interrupt_leave();
```

维护中断嵌套计数或中断上下文信息。具体是否必须在所有 ISR 中显式使用，取决于 BSP 模板和端口实现。

一般原则：

- ISR 中只做快速、确定、必要的工作。
- 使用中断安全 API。
- 不在 ISR 中执行阻塞操作。
- 不在 ISR 中进行复杂日志格式化。
- 不在 ISR 中访问可能睡眠的设备接口。
- 不在高优先级中断中直接触发不安全的内核操作。
- 使用 DMA、环形缓冲区和线程通知降低 ISR 工作量。

示例：串口接收中断将数据写入环形缓冲区，线程异步处理：

```
#define RX_RING_SIZE 256U

struct uart_ring
{
    rt_uint8_t buffer[RX_RING_SIZE];
    volatile rt_uint16_t head;
    volatile rt_uint16_t tail;
};

static struct uart_ring rx_ring;
static struct rt_semaphore rx_sem;

static void uart_rx_isr(rt_uint8_t data)
{
    rt_uint16_t next;
    rt_base_t level;

    level = rt_hw_interrupt_disable();

    next = (rt_uint16_t)((rx_ring.head + 1U) % RX_RING_SIZE);
    if (next != rx_ring.tail) {
        rx_ring.buffer[rx_ring.head] = data;
        rx_ring.head = next;
    } else {
        /* 缓冲区满：记录溢出，不覆盖未消费数据。 */
        uart_rx_overflow_count++;
    }

    rt_hw_interrupt_enable(level);

    /* 释放信号量的接口必须使用当前版本认可的 ISR 安全形式。 */
    rt_sem_release(&rx_sem);
}
```

对于高频数据流，更推荐：

```
DMA 半传输/完成中断
  -> 更新缓冲区所有权
  -> 记录写指针
  -> 唤醒数据处理线程
  -> 线程批量解析
```

---

## 5.5 临界区与原子性

RT-Thread 常见临界区接口包括：

```
rt_base_t level;

level = rt_hw_interrupt_disable();
/* 临界区 */
rt_hw_interrupt_enable(level);
```

使用原则：

1. 临界区内不调用可能阻塞的 API。
2. 临界区内不访问慢速外设。
3. 临界区必须有明确的最坏执行时间。
4. 嵌套临界区必须保存并恢复原始中断状态。
5. 不要用 `volatile` 代替原子性。
6. 多核或 DMA 场景还需考虑 Cache 和内存屏障。

错误示例：

```
level = rt_hw_interrupt_disable();

rt_thread_mdelay(10);      /* 错误：临界区中阻塞 */
rt_device_write(dev, 0, p, len); /* 高风险：可能执行慢速路径 */

rt_hw_interrupt_enable(level);
```

正确结构：

```
level = rt_hw_interrupt_disable();

update_shared_ring_metadata();
notify_needed = should_notify_consumer();

rt_hw_interrupt_enable(level);

if (notify_needed) {
    rt_sem_release(&data_sem);
}
```

---

## 5.6 RT-Thread 内存管理

### 5.6.1 静态内存

适合：

- 线程固定。
- 驱动对象固定。
- 安全关键路径。
- 启动阶段不能依赖堆。
- 需要确定性 RAM 预算。

示例：

```
static struct rt_thread sensor_thread;
static rt_uint8_t sensor_stack[1024] __attribute__((aligned(8)));

static void sensor_entry(void *parameter)
{
    (void)parameter;

    for (;;) {
        sensor_sample_once();
        rt_thread_mdelay(10);
    }
}

static int sensor_thread_init(void)
{
    rt_err_t result;

    result = rt_thread_init(&sensor_thread,
                            "sensor",
                            sensor_entry,
                            RT_NULL,
                            sensor_stack,
                            sizeof(sensor_stack),
                            10,
                            10);
    if (result != RT_EOK) {
        return -1;
    }

    rt_thread_startup(&sensor_thread);
    return 0;
}
```

静态线程的优势是对象和栈的生命周期明确，但需要确保栈大小、对齐和对象初始化顺序正确。

### 5.6.2 动态内存

动态内存适合：

- 设备数量运行期变化。
- 协议缓冲区大小变化。
- 文件系统和网络组件。
- 插件或模块化系统。

动态内存必须验证：

- 最大分配块。
- 分配失败恢复。
- 长时间运行碎片。
- 多线程并发分配。
- 中断上下文禁用分配。
- 外部内存和 Cache 属性。

示例：

```
void *buffer = rt_malloc(buffer_size);
if (buffer == RT_NULL) {
    LOG_E("allocate %u bytes failed", buffer_size);
    return -RT_ENOMEM;
}

result = protocol_process(buffer, buffer_size);

rt_free(buffer);
buffer = RT_NULL;

return result;
```

### 5.6.3 内存池

固定块内存池适合消息、网络包、DMA 描述符等固定大小对象：

```
static struct rt_mempool packet_pool;
static rt_uint8_t packet_pool_mem[16U * 128U];

static int packet_pool_init(void)
{
    return rt_mp_init(&packet_pool,
                      "pkt",
                      packet_pool_mem,
                      sizeof(packet_pool_mem),
                      128U);
}
```

具体 `rt_mp_init()` 参数和返回类型应以当前版本头文件为准。内存池设计重点是：

- 块大小覆盖最大对象。
- 块数量覆盖峰值并发。
- 不同生命周期对象不要共用同一池。
- 记录空闲块最小值。
- 处理池耗尽，不能无限等待于不可恢复路径。

---

## 5.7 设备框架与驱动移植

RT-Thread 设备驱动通常分为：

```
应用
  -> rt_device_open/read/write/control
  -> rt_device_ops
  -> 芯片寄存器 / DMA / 中断
```

一个简化设备对象：

```
static rt_err_t my_uart_init(rt_device_t dev)
{
    (void)dev;

    clock_enable_uart();
    uart_config_baudrate(115200U);
    uart_enable_rx_interrupt();

    return RT_EOK;
}

static rt_size_t my_uart_read(rt_device_t dev,
                              rt_off_t position,
                              void *buffer,
                              rt_size_t size)
{
    (void)dev;
    (void)position;

    return uart_ring_read(buffer, size);
}

static rt_err_t my_uart_control(rt_device_t dev,
                                int cmd,
                                void *args)
{
    (void)dev;

    switch (cmd) {
    case RT_DEVICE_CTRL_CONFIG:
        return uart_apply_config(args);

    default:
        return -RT_ENOSYS;
    }
}

static const struct rt_device_ops my_uart_ops =
{
    .init    = my_uart_init,
    .open    = RT_NULL,
    .close   = RT_NULL,
    .read    = my_uart_read,
    .write   = RT_NULL,
    .control = my_uart_control,
};
```

驱动注册：

```
static struct rt_device my_uart_device;

static int my_uart_register(void)
{
    rt_err_t result;

    my_uart_device.type = RT_Device_Class_Char;
    my_uart_device.ops = &my_uart_ops;
    my_uart_device.user_data = RT_NULL;

    result = rt_device_register(&my_uart_device,
                                "uart_custom",
                                RT_DEVICE_FLAG_RDWR |
                                RT_DEVICE_FLAG_INT_RX);

    return result == RT_EOK ? 0 : -1;
}
```

生产级驱动必须进一步处理：

- 重复注册。
- 设备打开计数。
- 并发读写。
- DMA 缓冲区所有权。
- 中断与线程之间的同步。
- 超时与取消。
- 错误恢复。
- 设备复位。
- 电源管理。
- Cache 一致性。
- `control()` 参数校验。

---

## 5.8 自动初始化机制

RT-Thread 常用自动初始化宏，例如：

```
static int board_device_init(void)
{
    return my_uart_register();
}
INIT_DEVICE_EXPORT(board_device_init);
```

常见初始化阶段大致包括：

```
INIT_BOARD_EXPORT
INIT_PREV_EXPORT
INIT_DEVICE_EXPORT
INIT_COMPONENT_EXPORT
INIT_ENV_EXPORT
INIT_APP_EXPORT
```

不同阶段的精确含义和执行顺序以当前 RT-Thread 版本为准。

自动初始化的工程风险：

- 初始化顺序隐含在宏段排序中。
- 依赖关系不明显。
- 某些初始化失败仅打印日志，没有阻止系统启动。
- 组件初始化可能消耗大量堆。
- 早期初始化阶段使用了尚未可用的设备。

工程建议：

- 对关键初始化返回值进行检查。
- 初始化失败必须有明确策略：降级、重试、复位或阻止启动。
- 复杂依赖不要完全依赖自动初始化，必要时显式编排。
- 将板级硬件初始化、设备注册、组件初始化和业务启动分开。

---

## 6. 性能量化分析

## 6.1 测试平台定义

性能数据必须包含：

```
MCU：Cortex-M4F，120 MHz
编译器：GCC 12.x
优化：-O2
FPU：单精度硬浮点
RT-Thread：固定 commit
RT_TICK_PER_SECOND：1000
测量工具：DWT CYCCNT + GPIO
Cache：关闭或明确配置
测试负载：两个就绪线程、一个 Tick、一个 UART ISR
```

以下数值均为**示例估算方法，不是通用实测结论**。

## 6.2 计算公式

### Tick CPU 占用

```
U_tick = C_tick × f_tick / f_cpu
```

例如：

```
C_tick = 1,200 cycles
f_tick = 1,000 Hz
f_cpu  = 120 MHz

U_tick = 1,200 × 1,000 / 120,000,000
       = 1.0%
```

### 上下文切换 CPU 占用

```
U_switch = C_switch × f_switch / f_cpu
```

假设：

```
C_switch = 550 cycles
f_switch = 2,000 switches/s
f_cpu = 120 MHz

U_switch = 550 × 2,000 / 120,000,000
         ≈ 0.92%
```

### 线程栈 RAM

```
RAM_stack = Σ(stack_size_i)
```

如果 RT-Thread 栈大小按字节传入，则：

```
3 个线程：
1024 + 1536 + 2048 = 4608 bytes
```

如果某个架构模板使用 `rt_uint8_t` 栈数组，数组大小通常直接以字节计算；如果使用 `rt_ubase_t` 数组，则要按元素大小换算。必须看当前 BSP 的线程创建接口和栈类型定义。

### 最坏响应时间

简化模型：

```
T_response_max =
    T_ISR
  + T_higher_priority_block
  + T_scheduler
  + T_context_switch
  + T_task_start_latency
```

完整分析还应加入：

- 中断嵌套。
- Cache miss。
- 总线争用。
- DMA 访问。
- 临界区屏蔽。
- 日志和调试输出。
- 其他高优先级线程执行时间。

## 6.3 测量代码

```
static void dwt_cycle_counter_enable(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static rt_uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}

static void measure_scheduler_path(void)
{
    rt_uint32_t start;
    rt_uint32_t end;

    start = dwt_cycles();

    /* 触发一个已知的调度路径。 */
    rt_thread_yield();

    end = dwt_cycles();

    LOG_I("scheduler path: %u cycles", end - start);
}
```

注意：

- 测量代码本身有开销。
- 编译器可能内联或重排代码，必要时使用内存屏障。
- `rt_thread_yield()` 的测量不等于完整的中断上下文切换。
- 应分别测量线程态切换和 ISR 退出切换。
- 应统计最大值，而不是只记录平均值。

## 6.4 线程栈高水位

RT-Thread 的线程控制块通常包含栈起始地址和栈大小信息，部分 BSP 或工具提供栈剩余查询。也可以通过栈填充模式测量：

```
static rt_size_t stack_unused_bytes(const rt_uint8_t *stack,
                                    rt_size_t size)
{
    rt_size_t unused = 0U;

    while (unused < size && stack[unused] == 0xCCU) {
        unused++;
    }

    return unused;
}
```

该方法只有在：

- 线程创建前将整个栈填充为 `0xCC`。
- 栈增长方向已确认。
- 不存在初始化过程覆盖检测区域。
- 统计时间足够长。

的条件下才有意义。

工程建议：

```
实测峰值栈使用量
+ 中断嵌套栈空间
+ 调用深度变化余量
+ 编译优化变化余量
+ 故障路径余量
= 最终配置栈大小
```

## 6.5 性能瓶颈和优化手段

|瓶颈|表现|优化方式|
|---|---|---|
|Tick 过高|固定 CPU 占用增加|降低 Tick 或使用硬件定时器|
|线程过多|切换频繁、RAM 增长|合并同类事件，使用事件驱动|
|日志阻塞|高优先级线程延迟|异步日志、环形缓冲区|
|过长临界区|ISR 延迟增加|缩短锁范围、批量处理|
|动态内存碎片|运行一段时间后分配失败|内存池、静态分配、分区堆|
|设备层复制过多|吞吐降低、延迟增加|DMA、零拷贝、缓冲区所有权|
|Cache 不一致|数据错误、偶发崩溃|Cache 维护、非缓存区、内存屏障|

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
开始
 |
 |-- 是否有匹配芯片和工具链的官方 BSP？
 |       |-- 是：复用官方 BSP，先锁定版本和 commit
 |       |-- 否：选择同系列 BSP 或从 Nano 模板开始
 |
 |-- 系统是否需要统一设备框架？
 |       |-- 是：使用完整 RT-Thread + rt_device
 |       |-- 否：使用 Nano 或最小内核
 |
 |-- 是否需要网络、文件系统、USB、Shell？
 |       |-- 是：启用对应组件并制定内存预算
 |       |-- 否：关闭组件，减少启动和 RAM 开销
 |
 |-- 线程和内核对象是否固定？
 |       |-- 是：优先静态对象和内存池
 |       |-- 否：启用动态内存，执行碎片和失败测试
 |
 |-- 是否有低功耗要求？
 |       |-- 是：评估 tickless、低功耗定时器和唤醒路径
 |       |-- 否：使用常规 Tick，优先保证时间基准稳定
 |
 |-- 是否有高吞吐 DMA 设备？
         |-- 是：设计 DMA 缓冲区所有权、Cache 和批处理
         |-- 否：使用普通设备读写模型并验证阻塞行为
```

## 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|小型 MCU，只有少量线程|RT-Thread Nano|资源占用低，移植边界清晰|
|多串口、SPI、I2C、传感器|完整 RT-Thread + 设备框架|统一设备访问和驱动抽象|
|工业网关|完整 RT-Thread + 网络/文件系统|组件集成能力强|
|固定控制任务|静态线程 + 内存池|RAM 可预测，长期运行稳定|
|动态设备数量|动态对象 + 分区内存|支持生命周期变化|
|电池供电节点|低功耗框架 + tickless|减少周期唤醒|
|大量日志与远程诊断|异步日志 + Shell + 网络|避免业务线程被输出阻塞|
|高速 ADC/DMA|DMA + 环形缓冲 + 数据线程|降低中断负载，提升吞吐|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：先锁定版本

至少固定：

- RT-Thread 版本或 commit。
- BSP 版本。
- 编译器版本。
- 芯片 SDK 版本。
- 链接脚本版本。
- 配置文件版本。

RT-Thread 的自动初始化、设备接口和端口细节可能随版本变化。不要将“同一芯片”的旧 BSP 直接复制到新内核。

### 原则二：架构端口和 BSP 分离

推荐目录：

```
project/
  rt-thread/
    src/
    include/
    components/
  bsp/
    board/
      board.c
      drv_uart.c
      drv_gpio.c
      SConscript
      rtconfig.h
    startup/
    linker/
  applications/
    main.c
    app_xxx.c
  packages/
```

架构通用代码放在 `libcpu` 或内核端口，芯片寄存器操作放在 BSP，业务逻辑放在 `applications`。

### 原则三：默认启用诊断能力

开发和测试阶段至少启用：

```
#define RT_USING_ASSERT
#define RT_USING_OVERFLOW_CHECK
#define RT_USING_HEAP
#define RT_USING_FINSH
```

具体宏名称依配置模板变化。产品版本可以裁剪，但必须保留等效的：

- 断言。
- 栈边界检查。
- 内存失败监控。
- HardFault 信息。
- 关键设备错误统计。
- 看门狗和复位原因记录。

### 原则四：初始化失败不能被忽略

错误示例：

```
rt_device_open(dev, RT_DEVICE_FLAG_RDWR);
```

正确实现：

```
rt_err_t result;

result = rt_device_open(dev, RT_DEVICE_FLAG_RDWR);
if (result != RT_EOK) {
    LOG_E("open %s failed: %d", dev->parent.name, result);
    enter_degraded_mode();
    return result;
}
```

### 原则五：设备 API 不等于实时 API

`rt_device_read()`、`rt_device_write()` 和 `rt_device_control()` 可能触发：

- 锁竞争。
- 阻塞等待。
- DMA 配置。
- 缓冲区复制。
- 驱动状态机。
- 日志输出。

实时路径应明确每个设备 API 的最坏执行时间和阻塞行为。

## 8.2 选型决策矩阵

|约束|推荐决策|
|---|---|
|RAM 小于几十 KB|Nano、静态对象、内存池、关闭不必要组件|
|需要多种外设统一访问|完整设备框架|
|有安全关键控制回路|控制路径静态分配，避免动态 Shell 和日志|
|需要运行期模块|动态内存 + 分区管理 + 失败恢复|
|需要远程升级|文件系统、Flash 抽象、校验、回滚状态机|
|需要大量网络缓冲|外部 RAM 或专用内存池，处理 Cache|
|需要低功耗|低功耗时钟、Tickless、唤醒源统一管理|
|需要精确周期控制|硬件定时器/DMA，不依赖普通 Tick|

## 8.3 工业级编码规范

- 所有驱动接口检查参数和设备状态。
- 所有动态分配检查返回值。
- 所有阻塞 API 明确最大等待时间。
- 不在中断中调用阻塞 API。
- ISR 与线程共享变量使用明确的原子性策略。
- DMA 缓冲区明确 Cache 属性和所有权。
- 设备名称统一规范，避免运行期字符串冲突。
- 初始化函数返回值必须被检查。
- 线程入口不应直接返回；如果必须退出，应显式清理资源。
- 关键数据结构增加版本、长度和状态字段。
- 不用 `printf` 替代实时日志系统。
- 线程优先级根据响应时间和阻塞关系设计，不能按模块重要性随意分配。
- 任务栈大小依据高水位和最坏调用路径确定，不以经验数字直接复制。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：启动器和 RT-Thread 初始化重复

错误示例：

```
int main(void)
{
    SystemClock_Config();
    rt_hw_board_init();

    rt_system_scheduler_start();

    /* 下面再次初始化同一时钟和设备。 */
    SystemClock_Config();
    uart_init();

    return 0;
}
```

### 根因

BSP 模板已经在 `rtthread_startup()` 中完成了板级初始化，应用层又重复执行，导致：

- 时钟重新切换。
- UART 状态机被重置。
- 中断重复配置。
- DMA 描述符失效。
- 外设状态不一致。

### 正确实现

将板级初始化集中在 BSP，将业务初始化放在应用初始化阶段：

```
static int application_init(void)
{
    rt_err_t result;

    result = app_devices_open();
    if (result != RT_EOK) {
        return result;
    }

    app_threads_start();
    return RT_EOK;
}
INIT_APP_EXPORT(application_init);
```

### 风险

系统可能可以启动，但在特定中断、低功耗或设备重连场景下随机失败。

---

## 9.2 错误二：PendSV 或 SysTick 向量没有连接到 RT-Thread

错误示例：

```
void PendSV_Handler(void)
{
    while (1) {
        /* 启动文件中的默认死循环 */
    }
}
```

### 根因

- 启动文件定义了强符号。
- RT-Thread 端口的异常处理函数没有覆盖它。
- 使用了错误架构目录下的 `libcpu`。
- 链接脚本使用了错误的向量表。
- `VTOR` 指向了另一个向量表。

### 正确实现

检查最终 ELF：

```
nm firmware.elf | grep -E "PendSV|SysTick|SVC"
objdump -t firmware.elf
```

确认：

```
向量表[PendSV] -> RT-Thread port PendSV handler
向量表[SysTick] -> RT-Thread tick handler
向量表[SVC] -> RT-Thread startup/context handler（如端口需要）
```

### 风险

- `rt_system_scheduler_start()` 后立即 HardFault。
- 第一次 Tick 后进入默认死循环。
- 线程只能运行一个，无法切换。
- 延时线程永远不被唤醒。

---

## 9.3 错误三：上下文栈帧与恢复汇编不匹配

错误示例：

```
/* 初始化时只压入了硬件自动保存的 8 个寄存器，
 * 但 PendSV 恢复代码还会弹出 R4-R11。 */
```

### 根因

线程初始栈布局与 PendSV 汇编约定不一致。常见错误包括：

- `R4-R11` 顺序错误。
- `xPSR` Thumb 位错误。
- 栈增长方向理解错误。
- 返回地址不是有效线程退出函数。
- FPU 上下文预留不一致。
- 栈未按 8 字节对齐。

### 正确实现

必须将以下三者作为一个整体审查：

```
线程栈初始化函数
+ PendSV 保存代码
+ PendSV 恢复代码
```

调试时在首次切换前检查：

```
PSP
栈顶地址
xPSR
PC
LR
R0
R4-R11
EXC_RETURN
```

### 风险

- 线程第一次运行即 HardFault。
- 返回后跳转到奇怪地址。
- 线程运行数秒后随机崩溃。
- 只有开启优化或启用 FPU 时才失败。

---

## 9.4 错误四：中断上下文中执行阻塞操作

错误示例：

```
void UART_IRQHandler(void)
{
    rt_sem_take(&rx_sem, RT_WAITING_FOREVER);
    rt_thread_mdelay(1);
}
```

### 根因

ISR 没有线程上下文，不能睡眠，也不能等待会导致线程切换的对象。

### 正确实现

```
void UART_IRQHandler(void)
{
    rt_interrupt_enter();

    uart_receive_to_ring_buffer();
    rt_sem_release(&rx_sem);

    rt_interrupt_leave();
}
```

线程中执行阻塞等待：

```
static void uart_worker(void *parameter)
{
    (void)parameter;

    for (;;) {
        if (rt_sem_take(&rx_sem, RT_WAITING_FOREVER) == RT_EOK) {
            uart_parse_ring_buffer();
        }
    }
}
```

### 风险

- 系统死锁。
- 中断永不返回。
- 调度器状态破坏。
- 线程控制块链表损坏。
- 看门狗复位。

---

## 9.5 错误五：DMA 缓冲区忽略 Cache 一致性

错误示例：

```
static rt_uint8_t rx_buffer[2048];

start_dma_receive(rx_buffer, sizeof(rx_buffer));
```

### 根因

在 Cortex-M7 等带 D-Cache 的平台上：

- CPU 可能从 Cache 读取旧数据。
- DMA 直接写入 RAM，不会自动更新 CPU Cache。
- CPU 写入的发送数据可能仍停留在 Cache，DMA 读取到旧数据。

### 正确实现

接收前或接收完成后根据平台执行：

```
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buffer,
                              sizeof(rx_buffer));

dma_start_rx(rx_buffer, sizeof(rx_buffer));
```

发送前：

```
SCB_CleanDCache_by_Addr((uint32_t *)tx_buffer,
                        sizeof(tx_buffer));

dma_start_tx(tx_buffer, tx_length);
```

同时确保：

- 地址满足 Cache line 对齐。
- 长度按 Cache line 对齐处理。
- 缓冲区不与其他数据共享同一 Cache line，或采取更严格的对齐与隔离。
- 或将 DMA 缓冲区放在非缓存区域。

### 风险

- 偶发协议校验失败。
- 数据包内容随机旧化。
- 高温、高负载或开启优化后故障频率升高。
- 难以通过普通单步调试复现。

---

## 9.6 错误六：线程栈大小和监测方式错误

错误示例：

```
static rt_uint8_t stack[256];

rt_thread_init(&thread,
               "worker",
               worker_entry,
               RT_NULL,
               stack,
               sizeof(stack),
               10,
               10);
```

### 根因

线程内调用了：

- 大数组。
- 浮点库。
- 日志格式化。
- 深层协议解析。
- 文件系统或网络栈。
- 多层回调。

256 字节很可能不足。

### 正确实现

先按调用路径估算，再通过高水位和压力测试验证：

```
#define WORKER_STACK_SIZE  2048U

static rt_uint8_t worker_stack[WORKER_STACK_SIZE]
    __attribute__((aligned(8)));
```

测试必须覆盖：

- 最大报文。
- 最深错误路径。
- 最大日志输出。
- 中断嵌套。
- 不同优化等级。
- 开启/关闭 FPU。
- 低功耗恢复路径。

### 风险

- 覆盖相邻线程控制块。
- 破坏返回地址。
- 线程随机退出。
- 设备运行较长时间后崩溃。

---

## 9.7 错误七：初始化阶段调用尚未准备好的设备

错误示例：

```
static int app_init(void)
{
    rt_device_t dev;

    dev = rt_device_find("uart2");
    rt_device_open(dev, RT_DEVICE_FLAG_RDWR);

    return 0;
}
INIT_PREV_EXPORT(app_init);
```

### 根因

`uart2` 可能还没有在 `INIT_DEVICE_EXPORT` 阶段注册。

### 正确实现

- 将应用初始化放到合适的初始化阶段。
- 或在应用线程启动后查找设备。
- 对 `rt_device_find()` 和 `rt_device_open()` 返回值进行检查。

```
static int app_init(void)
{
    rt_device_t dev;

    dev = rt_device_find("uart2");
    if (dev == RT_NULL) {
        LOG_E("uart2 not found");
        return -RT_ENOSYS;
    }

    return rt_device_open(dev, RT_DEVICE_FLAG_RDWR);
}
INIT_APP_EXPORT(app_init);
```

### 风险

- 启动阶段空指针访问。
- 设备打开失败但业务继续运行。
- 初始化顺序随链接器或构建系统变化而不稳定。

---

## 10. 多机制组合使用方案

## 10.1 DMA + 设备框架 + 消息队列 + 数据处理线程

典型架构：

```
外设 DMA
  |
  | 半传输/全传输中断
  v
ISR
  |-- 清除中断
  |-- 更新 DMA 缓冲区所有权
  |-- 写入消息描述符
  |-- 唤醒数据处理线程
  v
数据处理线程
  |-- 校验帧
  |-- 批量解析
  |-- 生成业务事件
  v
业务线程
```

示例：

```
#define DMA_BLOCK_SIZE  256U
#define DMA_BLOCK_COUNT 4U

struct dma_block
{
    rt_uint8_t *address;
    rt_uint16_t length;
    rt_uint8_t index;
};

static rt_uint8_t dma_buffer[DMA_BLOCK_SIZE * DMA_BLOCK_COUNT]
    __attribute__((aligned(32)));

static struct rt_messagequeue dma_mq;
static rt_uint8_t dma_mq_pool[sizeof(struct dma_block) * 8U];

static void dma_rx_isr(void)
{
    struct dma_block block;
    rt_base_t level;

    dma_clear_interrupt();

    block.index = dma_get_completed_block();
    block.address = &dma_buffer[block.index * DMA_BLOCK_SIZE];
    block.length = dma_get_block_length();

    /*
     * 这里应根据 MCU 的 Cache 结构执行 invalidate，
     * 并保证地址和长度满足平台要求。
     */
    dma_cache_invalidate(block.address, block.length);

    level = rt_hw_interrupt_disable();
    dma_update_ownership(block.index);
    rt_hw_interrupt_enable(level);

    rt_mq_send(&dma_mq,
               &block,
               sizeof(block));
}
```

线程处理：

```
static void dma_worker(void *parameter)
{
    struct dma_block block;

    (void)parameter;

    for (;;) {
        if (rt_mq_recv(&dma_mq,
                       &block,
                       sizeof(block),
                       RT_WAITING_FOREVER) != RT_EOK) {
            continue;
        }

        if (!frame_check(block.address, block.length)) {
            frame_error_count++;
            dma_release_block(block.index);
            continue;
        }

        process_frame(block.address, block.length);
        dma_release_block(block.index);
    }
}
```

### 10.2 组合设计要点

- 消息队列传递的是描述符，不是大块数据，减少复制。
- DMA 缓冲区由 DMA、ISR、处理线程定义明确所有权。
- 队列满时必须有策略：
    - 丢弃最新数据。
    - 丢弃最旧数据。
    - 停止 DMA。
    - 增加背压。
    - 进入降级模式。
- `rt_mq_send()` 是否允许在 ISR 中调用要以当前版本和 API 定义为准；如果不支持，应使用 ISR 安全接口或中断事件标志。
- 对高速数据流，消息队列容量应根据突发长度和最坏线程调度延迟计算。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业传感器采集节点

### 需求

- 采样频率 10 kHz。
- 传感器通过 SPI + DMA 采集。
- 采样数据需要滤波、阈值判断和通信上传。
- 需要支持串口调试和远程参数配置。
- 采样路径不能被日志阻塞。

### 架构

```
定时器触发
  -> SPI DMA
  -> DMA 完成 ISR
  -> 环形缓冲区
  -> 采样处理线程
  -> 滤波/阈值判断
  -> 通信消息队列
  -> 通信线程
```

### 设计要点

- 采样触发使用硬件定时器，不使用普通 RTOS Tick。
- DMA ISR 只更新读写指针并唤醒处理线程。
- 采样线程优先级高于通信线程，但低于硬件安全中断。
- 原始采样数据使用固定大小内存池。
- 日志采用异步输出，禁止在采样线程中同步打印大量数据。
- 记录丢样计数、DMA 错误计数、队列峰值和处理最大耗时。

核心代码结构：

```
static struct rt_messagequeue sample_mq;
static rt_uint8_t sample_mq_pool[16U * sizeof(struct sample_block)];

static void sample_dma_complete_isr(void)
{
    struct sample_block block;

    block.address = sample_dma_completed_address();
    block.count = sample_dma_completed_count();

    sample_cache_invalidate(block.address,
                            block.count * sizeof(sample_t));

    if (rt_mq_send(&sample_mq,
                   &block,
                   sizeof(block)) != RT_EOK) {
        sample_drop_count++;
    }
}

static void sample_worker(void *parameter)
{
    struct sample_block block;

    (void)parameter;

    for (;;) {
        if (rt_mq_recv(&sample_mq,
                       &block,
                       sizeof(block),
                       RT_WAITING_FOREVER) != RT_EOK) {
            continue;
        }

        filter_samples(block.address, block.count);
        evaluate_thresholds(block.address, block.count);
        sample_release_block(&block);
    }
}
```

### 性能预算

假设：

```
采样周期：100 us
DMA 完成块：32 个样本
处理线程每块处理时间：不超过 40 us
最大高优先级中断阻塞：不超过 10 us
```

则单块处理仍有约：

```
80 us - 40 us - 10 us = 30 us
```

的调度与突发余量。实际还需加入 Cache、总线和其他中断开销。

---

## 11.2 案例二：工业以太网网关

### 需求

- 多串口、CAN、以太网并发。
- 网络突发流量高。
- 支持配置文件、日志和远程升级。
- 系统长期运行，不能依赖频繁重启清理堆碎片。

### 架构

```
网卡 DMA
  -> 网络 ISR
  -> RX 描述符回收线程
  -> 网络协议栈
  -> 业务消息队列
  -> 协议适配线程
  -> CAN/串口发送队列

文件系统
  -> 配置线程
  -> OTA 状态机
  -> Flash 写入线程
```

### 设计要点

- 网络包使用专用内存池，避免通用堆碎片。
- Flash 写入单独线程串行化，避免多个业务线程同时擦写。
- 配置读取与业务运行解耦，更新采用双区或日志结构。
- 以太网 RX 处理采用批量回收，减少每包一次调度。
- 开启 MPU/Cache 的平台需要区分：
    - 网络描述符区域。
    - DMA 数据区域。
    - CPU 处理区域。
- 远程升级必须具有：
    - 镜像完整性校验。
    - 版本回退。
    - 下载断点恢复。
    - 上电中断保护。
    - 启动确认标志。

### 典型资源预算

```
网络包池：64 个 × 1536 字节
CAN 消息池：32 个 × 固定消息结构
日志环形缓冲区：8 KB
Flash 写入队列：16 个描述符
网络线程栈：按协议栈调用路径实测配置
```

不能仅因为系统剩余 RAM 较多，就将所有缓冲区交给通用堆。网络突发和长时间运行对内存碎片非常敏感。

---

## 11.3 案例三：电池管理控制器

### 需求

- 正常状态低功耗。
- 周期采集电压、电流和温度。
- 过压、欠压、过流必须快速响应。
- 支持调试 Shell，但量产版本默认关闭。

### 架构

```
安全比较器/硬件保护
  -> 高优先级安全 ISR
  -> 立即关闭功率路径

低功耗定时器
  -> 唤醒系统
  -> Tick 补偿

采集线程
  -> ADC DMA
  -> 滤波
  -> 状态估计

通信线程
  -> CAN/UART
  -> 参数与诊断
```

### 设计要点

- 硬件保护路径不能依赖普通线程调度。
- 低功耗唤醒后先恢复时钟和电源域，再恢复外设。
- RTC/LPTIM 的时间基准不能直接假设与主频 Tick 等价。
- Shell 只能修改受控参数，不能直接写功率控制寄存器。
- 量产固件应保留故障记录和最小诊断接口，即使关闭完整 FinSH。

---

## 12. 高频问题深度答疑

### Q1：RT-Thread 移植和 FreeRTOS 移植最大的差异是什么？

底层都必须完成上下文切换、Tick 和临界区，但 RT-Thread 的工程移植通常还包括：

- BSP 目录组织。
- `rt_device` 设备框架。
- 自动初始化阶段。
- FinSH/MSH。
- 组件和软件包裁剪。
- Board 层时钟、控制台、堆和 Tick 的统一启动流程。

因此 RT-Thread 移植成功的标准不只是“调度器启动”，还应包括设备注册、组件初始化、Shell/日志和驱动访问链路稳定。

### Q2：为什么 `rt_system_scheduler_start()` 之后不返回？

这是正常设计。调度器启动后会切换到第一个就绪线程，正常情况下不会返回。如果真的返回或进入异常，重点排查：

- 没有就绪线程。
- 线程初始栈帧错误。
- `rt_hw_context_switch_to()` 未实现或实现错误。
- PSP 设置错误。
- PendSV/SVC 向量错误。
- 栈未对齐。
- 链接到错误的架构端口。

### Q3：RT-Thread 的 Tick 中断必须使用 SysTick 吗？

不必须。可以使用：

- Cortex-M SysTick。
- 通用定时器。
- 低功耗定时器。
- RTC 子秒计数器。
- 芯片专用系统定时器。

选择标准是：

- 频率稳定。
- 中断延迟可控。
- 低功耗下是否继续工作。
- 是否与其他功能争用。
- 是否支持 Tickless。
- 是否有足够的计数宽度。

### Q4：RT-Thread 的 `rt_interrupt_enter()` 和 `rt_interrupt_leave()` 能否省略？

不能一概而论。某些 BSP 模板在统一异常包装层中已经调用，驱动 ISR 不应重复；另一些 BSP 需要每个 ISR 显式调用。重复调用可能导致嵌套计数错误，省略则可能导致调度器错误判断当前上下文。

应检查：

- 启动文件。
- BSP 中断包装函数。
- 当前架构端口。
- 同一 BSP 的官方驱动示例。

### Q5：为什么设备已经注册，但 `rt_device_find()` 仍然返回空？

常见原因：

- 设备注册函数没有执行。
- 自动初始化宏阶段不对。
- 设备名拼写不一致。
- 注册失败但返回值被忽略。
- 链接脚本没有保留初始化段。
- C++ 编译导致符号或段属性异常。
- 驱动文件未加入构建系统。
- 使用了不同的 `rt_device` 实例。

排查顺序：

```
确认驱动目标文件已编译
  -> 确认注册函数被执行
  -> 检查 rt_device_register 返回值
  -> 检查设备名称
  -> 检查初始化段和链接脚本
  -> 检查运行时对象列表
```

### Q6：线程优先级应该如何分配？

不应按“模块重要程度”直接分配，而应按：

1. 响应截止时间。
2. 是否可以阻塞。
3. 是否持有共享资源。
4. 是否有周期性计算。
5. 是否会产生大量后续工作。
6. 是否可能被高优先级线程长期抢占。

一个常见优先级关系：

```
硬件安全 ISR
  >
实时控制线程
  >
DMA/协议收包线程
  >
设备驱动服务线程
  >
业务线程
  >
日志、Shell、统计线程
```

但高优先级线程不能无限运行，否则低优先级线程会饥饿。必须限制单次处理批量和最长运行时间。

### Q7：RT-Thread 动态内存是否适合长期运行产品？

可以，但不能只看接口是否可用。必须验证：

- 分配大小分布。
- 分配和释放频率。
- 最大同时占用。
- 碎片率。
- 多线程竞争。
- 失败恢复。
- 内存泄漏。
- 异常路径释放。

对于固定尺寸、高频对象，优先使用内存池。对于生命周期固定的线程和设备，优先静态分配。

---

## 13. 课程核心总结

### 核心要点

1. RT-Thread 移植包含 **CPU 架构端口、BSP、内核配置、设备框架和构建系统** 五个主要部分。
2. Cortex-M 移植的核心是：
    - 正确构造线程初始栈。
    - 正确保存和恢复上下文。
    - 正确连接 PendSV、SysTick 和 SVC。
    - 正确处理 PSP、MSP 和异常返回。
3. RT-Thread 的 BSP 不只是启动代码，还承担：
    - 时钟。
    - Tick。
    - 堆。
    - 控制台。
    - 外设驱动。
    - 设备注册。
4. 自动初始化提高开发效率，但会引入隐含依赖，关键系统应显式验证初始化顺序。
5. 设备框架、DMA、IPC 和线程必须共同设计，不能只完成寄存器驱动。
6. 高可靠系统应优先静态对象、内存池和固定缓冲区。
7. 高吞吐系统必须重点处理 DMA 缓存一致性、缓冲区所有权和批量调度。
8. 低功耗系统必须验证 Tick 补偿、唤醒时序和时钟误差。

### 性能经验排序

从通常的资源消耗角度：

```
静态线程/静态 IPC
  < 内存池对象
  < 普通动态内存对象
  < 网络/文件系统等复杂组件
```

从移植复杂度角度：

```
复用官方 BSP
  < 修改同系列 BSP
  < Nano 手工移植
  < 新架构完整移植
```

从实时性确定性角度：

```
硬件触发 + DMA
  > ISR 采集 + 线程处理
  > 普通线程轮询
  > 高优先级线程周期轮询外设
```

---

## 14. 快速参考速查表

### 14.1 移植模块清单

|模块|必须验证的内容|
|---|---|
|启动文件|向量表、Reset、MSP、VTOR|
|时钟|主频、总线、Tick 时钟源|
|架构端口|初始栈、上下文保存/恢复|
|PendSV|异常优先级、触发和返回|
|SysTick/定时器|Tick 增加、超时唤醒|
|临界区|中断屏蔽、嵌套恢复|
|堆|起止地址、对齐、失败策略|
|线程|栈大小、优先级、生命周期|
|设备|注册、打开、读写、控制|
|构建|源码、宏、链接段、初始化段|
|诊断|断言、栈溢出、HardFault、日志|

### 14.2 API 使用边界

|场景|推荐行为|
|---|---|
|线程中等待信号量|可以使用阻塞等待|
|ISR 中等待信号量|禁止|
|ISR 通知线程|使用 ISR 安全接口或事件机制|
|线程中动态分配|可以，但必须检查失败|
|ISR 中动态分配|禁止|
|高实时路径打印日志|使用异步日志|
|DMA 接收|处理 Cache 和所有权|
|设备打开|检查设备指针和返回值|
|线程退出|显式释放资源，避免直接返回|
|临界区|短、确定、不可阻塞|

### 14.3 移植验收指标

|指标|建议验收内容|
|---|---|
|启动|首线程稳定运行，无 HardFault|
|切换|多线程切换百万次无异常|
|Tick|周期误差、长期漂移可接受|
|中断|ISR 延迟和嵌套符合预算|
|栈|最大业务负载下保留安全余量|
|堆|长时间分配/释放无不可接受碎片|
|设备|注册、打开、读写、关闭、恢复完整|
|DMA|收发数据一致，Cache 场景通过|
|低功耗|睡眠、唤醒、Tick 补偿正确|
|故障|HardFault、断言、看门狗可定位|

---

## 15. 学习效果自检

完成本课后，应能回答以下问题：

- RT-Thread 的 `libcpu` 与 BSP 分别负责什么？
- 一个线程第一次运行时，初始栈中必须包含哪些关键字段？
- 为什么 PendSV 通常用于上下文切换？
- `MSP` 和 `PSP` 在 RT-Thread Cortex-M 端口中的职责是什么？
- `rt_system_scheduler_start()` 为什么通常不返回？
- Tick 中断需要完成哪些内核工作？
- `rt_interrupt_enter()`/`leave()` 的作用是什么？
- 如何确认向量表最终指向了正确的 PendSV 和 SysTick？
- 自动初始化段可能引入哪些初始化顺序问题？
- 哪些对象适合静态分配，哪些对象适合内存池？
- DMA 缓冲区为什么必须考虑 Cache？
- 如何通过 map 文件检查堆和栈的位置？
- 如何测量线程切换、Tick 和 ISR 延迟？
- 如何设计一个不在 ISR 中阻塞的设备驱动？
- 如何定义队列满、内存池耗尽和设备初始化失败时的恢复策略？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：最小 Nano 移植

目标：

- 启动一个线程。
- 实现 Tick。
- 实现 `rt_hw_context_switch_to()`。
- 验证线程入口能够运行。

验收：

```
线程正常启动
  -> 延时准确
  -> 空闲线程运行
  -> 不进入默认异常处理
```

### 任务二：多线程上下文切换

创建三个不同优先级线程：

```
高优先级：周期采样
中优先级：通信处理
低优先级：日志统计
```

验证：

- 优先级抢占。
- 时间片轮转。
- 阻塞和唤醒。
- 线程栈高水位。
- 长时间运行稳定性。

### 任务三：UART 设备驱动

实现：

- UART 初始化。
- 中断接收。
- 环形缓冲区。
- `rt_device_register()`。
- `rt_device_open()`。
- `rt_device_read()`。
- `rt_device_control()`。

验证：

- 设备注册。
- 串口收发。
- 溢出统计。
- 超时行为。
- 关闭和重新打开。

### 任务四：DMA + 消息队列

实现：

```
DMA 完成中断
  -> 描述符入队
  -> 数据线程处理
  -> 缓冲区归还 DMA
```

验证：

- 高速连续数据。
- 队列满。
- 缓冲区耗尽。
- DMA 错误恢复。
- Cache 开启和关闭两种配置。

### 任务五：内存可靠性测试

测试：

- 反复创建和删除线程。
- 反复申请和释放不同大小内存。
- 内存池耗尽。
- 动态内存失败注入。
- 运行 24 小时以上。
- 记录最小剩余堆和最大碎片情况。

### 任务六：低功耗移植

实现：

- 空闲线程进入低功耗。
- 低功耗定时器唤醒。
- Tick 补偿。
- GPIO 外部唤醒。
- 时钟恢复。

测量：

```
正常运行电流
空闲电流
睡眠电流
唤醒延迟
Tick 时间误差
长时间睡眠漂移
```

## 16.2 性能测试方法

### 调度测试

- 记录线程切换前后的 DWT 周期。
- 分别测试：
    - 主动让出 CPU。
    - 阻塞唤醒。
    - Tick 抢占。
    - ISR 退出切换。
- 统计最小值、平均值、最大值和高分位值。

### 中断测试

```
外部触发信号
  -> GPIO ISR 翻转
  -> 线程被唤醒
  -> 线程 GPIO 翻转
```

使用逻辑分析仪测量：

- 中断入口延迟。
- ISR 执行时间。
- 线程响应延迟。
- 高优先级线程抢占影响。

### 内存测试

- 记录堆总量。
- 记录当前使用量。
- 记录历史峰值。
- 记录最大连续空闲块。
- 记录分配失败次数。
- 记录内存池最小剩余块数。

### 故障注入

至少注入：

- 线程栈溢出。
- 空设备访问。
- DMA 超时。
- 队列满。
- 内存分配失败。
- UART 线路断开。
- Flash 写入中断。
- 时钟切换失败。
- 看门狗复位。

## 16.3 进阶学习方向

- 阅读 RT-Thread `src/scheduler.c`、`thread.c`、`timer.c`、`ipc.c` 和内存管理源码。
- 阅读目标架构 `libcpu` 中的上下文切换汇编。
- 研究 RT-Thread 设备模型、驱动框架和自动初始化实现。
- 深入 FinSH/MSH、日志组件、文件系统和网络协议栈。
- 研究 Cortex-M7 Cache、MPU、DMA、内存屏障和非缓存区域。
- 研究 TrustZone-M 下安全世界与非安全世界的线程上下文切换。
- 研究 SMP 架构下调度器、锁、IPI 和每 CPU 数据。
- 将移植验收纳入持续集成：
    - 自动检查向量符号。
    - 自动检查配置宏。
    - 自动检查 RAM/Flash 预算。
    - 自动运行线程切换压力测试。
    - 自动执行设备驱动回归测试。
    - 自动生成栈和堆使用报告。