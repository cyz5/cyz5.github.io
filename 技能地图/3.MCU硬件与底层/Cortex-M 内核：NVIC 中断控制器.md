
## 1. 学习目标

### 理解

- 理解 Cortex-M 异常模型、中断号、向量表和 NVIC 的层级关系。
- 理解中断优先级、抢占优先级、响应优先级和优先级分组的真实含义。
- 理解中断进入、嵌套、退出、尾链、晚到达和异常返回的底层流程。
- 理解 `PRIMASK`、`BASEPRI`、`FAULTMASK` 与 NVIC 屏蔽机制的边界。

### 掌握

- 掌握 NVIC 的使能、禁用、挂起、清除挂起和软件触发机制。
- 掌握 Cortex-M3/M4/M7/M33 常用中断控制寄存器。
- 掌握中断优先级配置、优先级分组和 CMSIS 接口。
- 掌握中断共享、事件通知、延迟处理和 ISR 最小化设计。

### 精通

- 能分析中断延迟、优先级反转、伪共享、清中断时序和中断风暴。
- 能处理多源中断、DMA 中断、RTOS 临界区与 NVIC 的协同。
- 能通过 DWT、GPIO、逻辑分析仪和统计计数器量化 ISR 延迟与执行时间。
- 能定位 HardFault、BusFault、MemManage Fault 与非法异常返回等问题。

### 能够设计

- 能为工业控制、通信、采集和电机控制系统设计完整的 NVIC 优先级架构。
- 能设计可审计、可测试、可扩展的中断分层模型。
- 能建立中断预算、最大关闭中断时间和最坏响应时间模型。
- 能设计满足实时性要求的 Cortex-M 异常处理与故障恢复方案。

---

## 2. 前置要求

### 知识要求

- C 语言指针、函数指针、`volatile`、位操作和内存模型。
- ARM Cortex-M 基本寄存器结构、异常模型和特权级。
- MCU 时钟树、GPIO、定时器、DMA、UART/SPI 等外设基础。
- RTOS 任务调度、临界区、信号量和队列。
- 基本的实时系统分析方法。

### 技能要求

- 能阅读芯片参考手册和 Cortex-M Technical Reference Manual。
- 能使用 CMSIS、调试器、逻辑分析仪和示波器。
- 能查看 map 文件、反汇编、栈回溯和 fault 状态寄存器。
- 能独立实现一个带超时、错误处理和边界保护的外设驱动。
- 能使用 DWT、定时器或 GPIO 测量代码执行时间。

---

## 3. 技术概述

### 3.1 NVIC 的定义

NVIC，Nested Vectored Interrupt Controller，嵌套向量中断控制器，是 Cortex-M 内核的一部分，负责：

- 管理外部中断请求。
- 根据优先级决定异常响应顺序。
- 支持中断嵌套。
- 维护 Pending、Active、Enabled 等状态。
- 从向量表中获取异常入口地址。
- 支持尾链和晚到达等低延迟机制。
- 向处理器提供系统异常和外部 IRQ 的统一异常入口。

NVIC 不是 MCU 厂商外设。它属于 Cortex-M 内核架构，但实际支持的中断数量、实现的优先级位数和部分寄存器细节由具体芯片决定。

### 3.2 异常类型

Cortex-M 的异常可以分为两大类：

|类型|来源|是否由 NVIC 管理|示例|
|---|---|---|---|
|系统异常|内核内部|部分由 NVIC 管理|NMI、HardFault、SysTick、PendSV|
|外部中断|MCU 外设|是|UART、DMA、ADC、定时器|
|Reset|复位逻辑|否|上电复位、看门狗复位|
|SVC|软件指令|否，属于系统异常路径|RTOS 系统调用|
|UsageFault|执行错误|否，属于 Fault 异常路径|未定义指令、除零|
|BusFault|总线错误|否，属于 Fault 异常路径|非法访问、总线响应错误|
|MemManage|MPU 权限错误|否，属于 Fault 异常路径|执行或访问权限违规|

常用异常编号：

```
异常编号:
  -15 Reset
  -14 NMI
  -13 HardFault
  -12 MemManage
  -11 BusFault
  -10 UsageFault
   -5 SVCall
   -2 PendSV
   -1 SysTick

外部中断:
    0 IRQ0
    1 IRQ1
    ...
```

CMSIS 使用的是统一的 `IRQn_Type`，外部中断通常从 `0` 开始，系统异常为负数。

### 3.3 向量表与 NVIC 的关系

向量表保存异常入口地址：

```
向量表基地址 + 异常编号 × 4
```

对于 Cortex-M，向量表通常包含：

```
[0] 初始主堆栈指针 MSP
[1] Reset_Handler
[2] NMI_Handler
[3] HardFault_Handler
...
[N] 外部中断入口地址
```

向量表基地址由 `SCB->VTOR` 指定：

```
SCB->VTOR = vector_table_address;
__DSB();
__ISB();
```

重要约束：

- 向量表必须满足芯片规定的对齐要求。
- 重新定位向量表后必须执行 `DSB` 和 `ISB`。
- 向量表位于 Flash 时，启动阶段一般无需修改。
- Bootloader 跳转到 App 时，必须同时处理 `VTOR`、MSP、外设中断状态和 Pending 状态。

---

## 4. 核心特性横向对比

### 4.1 中断屏蔽机制对比

|机制|屏蔽范围|是否屏蔽 NMI|是否屏蔽 HardFault|典型用途|
|---|---|---|---|---|
|`PRIMASK`|屏蔽所有可屏蔽异常|否|否|极短全局临界区|
|`BASEPRI`|屏蔽优先级数值大于等于阈值的异常|否|否|RTOS 临界区、保护共享资源|
|`FAULTMASK`|屏蔽除 NMI 外所有异常|否|是|Fault 处理、极少使用|
|NVIC `ICER`|禁止指定 IRQ|不适用|不适用|动态关闭外设中断|
|外设中断屏蔽位|禁止外设产生某类源中断|不适用|不适用|精确关闭某一中断源|

注意：Cortex-M 的优先级数值越小，逻辑优先级越高。

```
优先级 0  > 优先级 1 > 优先级 2 > ... > 优先级 15
高优先级                         低优先级
```

### 4.2 不同 Cortex-M 内核对比

|特性|Cortex-M0/M0+|Cortex-M3/M4|Cortex-M7|Cortex-M33|
|---|---|---|---|---|
|NVIC|支持|支持|支持|支持|
|最大外部 IRQ|取决于实现|取决于实现|取决于实现|取决于实现|
|可编程优先级位|通常较少|通常 3~4 位|通常 4 位|通常 3~4 位|
|`BASEPRI`|通常不支持|支持|支持|支持|
|`FAULTMASK`|部分支持|支持|支持|支持|
|`VTOR`|取决于具体内核版本|支持|支持|支持|
|FPU Lazy Stacking|不适用|M4F 支持|支持|取决于实现|
|TrustZone|不支持|不支持|不支持|支持|
|Cache 影响|无|通常无|I/D-Cache 可能存在|取决于实现|
|中断延迟稳定性|较好|较好|受 Cache、TCM、总线影响|受安全域和实现影响|

### 4.3 优先级机制对比

|方案|抢占能力|配置复杂度|适用场景|
|---|---|---|---|
|所有中断同优先级|无嵌套|低|简单产品、非严格实时系统|
|分层优先级|有嵌套|中|通用工业控制|
|优先级分组|抢占与响应可分离|高|多层实时系统|
|`BASEPRI` 分区|支持受控临界区|高|RTOS、多任务系统|
|完全依靠外设屏蔽|只屏蔽指定源|中|对实时中断保护要求高的系统|

---

## 5. 底层原理与功能特性深度解析

## 5.1 NVIC 的核心状态机

对于每个外部 IRQ，NVIC 至少维护以下状态：

```
Enable:
  IRQ 是否允许被响应

Pending:
  IRQ 是否已经产生请求但尚未执行

Active:
  IRQ 当前是否正在执行，或者存在嵌套活动状态

Priority:
  IRQ 的抢占优先级与响应优先级
```

典型状态转换：

```
外设产生请求
    |
    v
Pending = 1
    |
    | Enable=1 且优先级允许响应
    v
进入 ISR
    |
    v
Active = 1, Pending 通常清除
    |
    v
异常返回
    |
    v
Active = 0
```

如果 ISR 执行过程中外设再次产生中断：

- 某些外设会保持 Pending。
- 某些外设需要软件重新清除状态位。
- 如果硬件状态位一直为 1，退出 ISR 后可能立即再次进入。

因此，**清 Pending 不等于清除外设中断源**。

---

## 5.2 NVIC 常用寄存器

以下寄存器属于 NVIC：

|寄存器|作用|
|---|---|
|`ISER`|Interrupt Set-Enable Register，使能 IRQ|
|`ICER`|Interrupt Clear-Enable Register，禁止 IRQ|
|`ISPR`|Interrupt Set-Pending Register，设置 Pending|
|`ICPR`|Interrupt Clear-Pending Register，清除 Pending|
|`IABR`|Interrupt Active Bit Register，读取 Active|
|`IPR`|Interrupt Priority Register，配置 IRQ 优先级|
|`STIR`|Software Trigger Interrupt Register，软件触发 IRQ|

CMSIS 推荐使用封装接口：

```
NVIC_EnableIRQ(UARTx_IRQn);
NVIC_DisableIRQ(UARTx_IRQn);
NVIC_SetPendingIRQ(UARTx_IRQn);
NVIC_ClearPendingIRQ(UARTx_IRQn);
NVIC_GetPendingIRQ(UARTx_IRQn);
NVIC_GetActive(UARTx_IRQn);
NVIC_SetPriority(UARTx_IRQn, priority);
```

不要直接假设所有芯片的 `NVIC->IPR` 布局、优先级位数和 IRQ 数量完全相同。

---

## 5.3 中断优先级的编码方式

Cortex-M 通常只实现优先级字段的高若干位。

例如 `__NVIC_PRIO_BITS = 4` 时，逻辑优先级范围为：

```
0 ~ 15
```

寄存器中实际存储为左对齐形式：

```
逻辑优先级 3
寄存器值 = 3 << (8 - 4)
         = 0x30
```

CMSIS 的 `NVIC_SetPriority()` 通常接收未左移的逻辑优先级：

```
NVIC_SetPriority(UARTx_IRQn, 5);
```

错误方式：

```
/* 错误：已经手动左移后又交给 CMSIS，可能导致优先级错误 */
NVIC_SetPriority(UARTx_IRQn, 5U << 4);
```

不同芯片的 `__NVIC_PRIO_BITS` 可能不同，必须读取设备头文件或参考手册。

---

## 5.4 优先级分组

Cortex-M 可以将实现的优先级位划分为：

- 抢占优先级：决定能否打断当前 ISR。
- 子优先级：当多个 IRQ 同时 Pending 时，决定先响应谁。

抽象表示：

```
优先级字段 = [抢占优先级位][子优先级位]
```

例如有 4 个有效优先级位：

|分组|抢占位|子优先级位|
|---|---|---|
|Group 0|0|4|
|Group 1|1|3|
|Group 2|2|2|
|Group 3|3|1|
|Group 4|4|0|

工程建议：

- 多数实时系统使用 `Group 4`，即所有有效优先级位用于抢占优先级。
- 只有确实需要“同一抢占层内排序”时，才使用子优先级。
- 不要把“响应优先级”误认为可以打断当前 ISR。**只有抢占优先级决定是否发生嵌套。**

CMSIS 示例：

```
NVIC_SetPriorityGrouping(0U);

/*
 * 具体分组编码由 CMSIS 和芯片实现定义。
 * 实际项目应使用芯片 SDK 推荐的宏或配置接口。
 */
```

在 STM32 等平台上，常见的是：

```
HAL_NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4);
```

但不能将某一家厂商 HAL 的分组宏直接移植到其他芯片。

---

## 5.5 中断响应流程

以外部 IRQ 为例，简化流程如下：

```
1. 外设置位中断状态
2. NVIC 将 IRQ 标记为 Pending
3. 处理器完成当前可继续执行的指令
4. 判断该 IRQ 是否高于当前活动异常
5. 自动保存部分寄存器
6. 根据向量表读取 ISR 地址
7. 设置异常状态并跳转到 ISR
8. ISR 执行
9. 执行异常返回
10. 恢复寄存器并继续原上下文
```

硬件自动压栈通常包括：

```
R0
R1
R2
R3
R12
LR
PC
xPSR
```

基础栈帧大小：

```
8 × 4 bytes = 32 bytes
```

如果使用 FPU，并且触发浮点上下文保存，额外栈空间可能达到约：

```
18 × 4 bytes = 72 bytes
```

因此，在存在 ISR 嵌套和 FPU 的系统中，栈预算不能只按普通函数调用深度估算。

---

## 5.6 Tail-chaining：尾链

如果一个 ISR 退出时，另一个同级或更高优先级异常已经 Pending，处理器可以直接切换到下一个 ISR，而不必完整执行：

```
出栈 -> 线程态 -> 再入栈
```

这称为尾链。

收益：

- 减少异常切换的栈操作。
- 降低连续中断的响应开销。
- 适合 SysTick、DMA、通信中断等高频场景。

工程影响：

- 多个高频中断可能连续执行，造成任务长期得不到运行。
- ISR 总执行时间仍然受所有 Pending 中断累计影响。
- 不能因为尾链降低了切换开销，就放任 ISR 中做复杂处理。

---

## 5.7 Late Arrival：晚到达

当处理器正在准备进入低优先级 ISR 时，如果更高优先级 IRQ 到达，处理器可以转而响应高优先级 IRQ。

这避免了：

```
进入低优先级 ISR
低优先级 ISR 刚开始
高优先级 ISR 抢占
```

而是尽可能直接进入高优先级 ISR。

但需要注意：

- 晚到达只能改善异常入口阶段的响应。
- 如果低优先级 ISR 已经开始执行，仍然需要正常抢占。
- 如果全局关闭中断，晚到达机制也无法绕过屏蔽规则。

---

## 5.8 `PRIMASK`、`BASEPRI` 的工程用法

### `PRIMASK`

```
uint32_t primask = __get_PRIMASK();

__disable_irq();
/* 极短、不可阻塞的临界区 */
__enable_irq();

__set_PRIMASK(primask);
```

恢复原状态比无条件 `__enable_irq()` 更安全：

```
static inline uint32_t irq_lock(void)
{
    uint32_t state = __get_PRIMASK();
    __disable_irq();
    __DSB();
    __ISB();
    return state;
}

static inline void irq_unlock(uint32_t state)
{
    __set_PRIMASK(state);
    __DSB();
    __ISB();
}
```

### `BASEPRI`

`BASEPRI` 可以屏蔽低优先级中断，同时保留高优先级实时中断。

例如：

```
#define BASEPRI_THRESHOLD  (5U)

static inline uint32_t basepri_lock(void)
{
    uint32_t old = __get_BASEPRI();
    __set_BASEPRI(BASEPRI_THRESHOLD << (8U - __NVIC_PRIO_BITS));
    __DSB();
    __ISB();
    return old;
}

static inline void basepri_unlock(uint32_t old)
{
    __set_BASEPRI(old);
    __DSB();
    __ISB();
}
```

实际代码应使用 RTOS 或 CMSIS 提供的优先级编码宏，避免手动移位与芯片实现不一致。

---

## 5.9 中断处理中的内存屏障

中断和 DMA 共享数据时，必须区分：

- 编译器重排。
- CPU 指令执行顺序。
- Cache 一致性。
- 外设总线可见性。

常见屏障：

|指令|作用|
|---|---|
|`DMB`|保证显式内存访问顺序|
|`DSB`|等待此前内存访问完成|
|`ISB`|清空流水线并重新取指|

共享标志示例：

```
static volatile bool adc_ready;
static uint16_t adc_buffer[128];

void ADC_IRQHandler(void)
{
    if (ADC_GetStatus() & ADC_STATUS_EOC) {
        ADC_ClearStatus(ADC_STATUS_EOC);

        adc_buffer[0] = ADC_ReadData();

        /*
         * 保证数据写入先于标志发布。
         */
        __DMB();
        adc_ready = true;
    }
}

bool adc_try_consume(uint16_t *value)
{
    if (value == NULL) {
        return false;
    }

    if (!adc_ready) {
        return false;
    }

    /*
     * 保证先观察到 adc_ready，再读取相关数据。
     */
    __DMB();
    *value = adc_buffer[0];
    adc_ready = false;

    return true;
}
```

对于 Cortex-M7 等具有 Cache 的内核，DMA 缓冲区还需要处理 Cache clean/invalidate；`DMB` 本身不能解决 Cache 一致性问题。

---

## 5.10 中断向量表重定位

典型启动代码：

```
#include "cmsis_gcc.h"
#include "core_cm4.h"

#define APP_VECTOR_TABLE_ADDR  (0x08020000UL)

static bool is_valid_vector_table(uint32_t address)
{
    uint32_t initial_msp = *(const uint32_t *)address;
    uint32_t reset_pc = *(const uint32_t *)(address + 4U);

    /*
     * 实际项目应根据 SRAM、Flash 地址范围进一步检查。
     */
    bool msp_aligned = ((initial_msp & 0x7U) == 0U);
    bool pc_thumb = ((reset_pc & 0x1U) != 0U);

    return msp_aligned && pc_thumb;
}

void app_prepare_vector_table(void)
{
    if (!is_valid_vector_table(APP_VECTOR_TABLE_ADDR)) {
        return;
    }

    __disable_irq();

    for (IRQn_Type irq = (IRQn_Type)0;
         irq < (IRQn_Type)NUMBER_OF_INT_VECTORS;
         ++irq) {
        NVIC_DisableIRQ(irq);
        NVIC_ClearPendingIRQ(irq);
    }

    SCB->VTOR = APP_VECTOR_TABLE_ADDR;
    __DSB();
    __ISB();

    __enable_irq();
}
```

生产系统还需要：

- 清除外设本身的中断状态。
- 清空 DMA、UART 等外设残留状态。
- 重新设置 MSP。
- 关闭 SysTick。
- 清理 RTOS 和 Bootloader 的 PendSV/SVC 状态。
- 校验 App 镜像完整性。
- 检查向量表地址是否位于合法 Flash 区域。

---

## 6. 性能量化分析

以下数据为典型参考值，不代表所有 MCU 的实测结果。实际结果必须以目标芯片、编译器、Flash 等待周期、Cache、FPU 和总线负载为准。

### 6.1 异常入口理论开销

设 CPU 主频为：

```
F_CPU = 168 MHz
T_cycle = 1 / 168 MHz ≈ 5.95 ns
```

对于 Cortex-M4，典型异常响应可近似：

```
入口基础开销 ≈ 12 cycles
出口基础开销 ≈ 10~12 cycles
```

仅按 24 cycles 计算：

```
T_entry_exit = 24 / 168 MHz
             ≈ 143 ns
```

如果考虑 Flash 等待、总线仲裁、FPU 上下文、调试器影响，实际可能达到：

```
约 150 ns ~ 500 ns
```

### 6.2 典型 ISR 时间预算

假设：

- 控制周期：100 μs
- 最高允许 ISR 占用率：20%
- ISR 总预算：

```
T_ISR_budget = 100 μs × 20%
             = 20 μs
```

若有三个中断：

|ISR|周期|单次执行时间|CPU 占用|
|---|---|---|---|
|电流采样|100 μs|3 μs|3%|
|通信 DMA|1 ms|8 μs|0.8%|
|系统 Tick|1 ms|5 μs|0.5%|

总中断占用：

```
3% + 0.8% + 0.5% = 4.3%
```

但不能只看平均占用率，还要看最坏连续占用：

```
最大连续不可抢占时间
= 当前 ISR 执行时间
+ 更高优先级 ISR 执行时间
+ 异常入口/出口开销
```

### 6.3 中断延迟模型

可用以下模型估算：

```
L_response =
    L_current_instruction
  + L_mask
  + L_exception_entry
  + L_higher_priority_ISR
  + L_bus
  + L_cache
```

其中：

- `L_current_instruction`：当前指令完成时间。
- `L_mask`：中断屏蔽造成的额外等待。
- `L_exception_entry`：硬件异常进入开销。
- `L_higher_priority_ISR`：已存在的更高优先级 ISR 影响。
- `L_bus`：总线拥塞、Flash、DMA 仲裁。
- `L_cache`：Cache miss 或 Cache 维护开销。

### 6.4 中断风暴分析

若某中断源频率为 `f_irq`，ISR 平均执行时间为 `t_isr`：

```
CPU_Utilization = f_irq × t_isr
```

例如：

```
f_irq = 50 kHz
t_isr = 4 μs

CPU_Utilization = 50,000 × 4 μs
                = 0.20
                = 20%
```

如果 ISR 中每个字节触发一次，而串口速率为 4 Mbps：

```
字节速率 = 4 Mbps / 10
         ≈ 400 kB/s
```

如果每字节产生一次中断，则：

```
IRQ 频率 ≈ 400 kHz
```

这类设计通常应改为：

- DMA。
- FIFO 阈值中断。
- 环形缓冲区。
- 批量接收。
- 空闲线检测。

### 6.5 栈空间估算

若最大嵌套深度为 4：

```
基础异常栈空间 = 4 × 32 bytes = 128 bytes
```

如果每层还存在 64 bytes 编译器保存寄存器：

```
总估算 = 4 × (32 + 64)
       = 384 bytes
```

如果 ISR 使用 FPU，需要进一步增加浮点上下文空间。

生产项目建议：

- 使用栈填充模式检测高水位。
- 使用 MPU 或栈哨兵检测越界。
- 分别估算 MSP 和 PSP。
- 对 HardFault、NMI、DMA ISR 设计独立栈预算。

### 6.6 优化手段与收益

|优化措施|典型收益|
|---|---|
|字节中断改 DMA|中断次数降低 10~1000 倍|
|ISR 中只入队列|ISR 时间降低 30%~90%|
|消除 ISR 中浮点运算|避免 50~100 bytes 级上下文压力|
|将关键 ISR 放入 ITCM/RAM|代码执行抖动降低，常见可减少数十个周期|
|减少全局关中断|最坏延迟显著下降|
|使用 `BASEPRI` 分层保护|保留关键实时中断响应|
|合并低优先级中断源|降低异常入口/出口开销|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否需要微秒级确定性响应？
├─ 是
│  ├─ 是否存在周期性高速数据？
│  │  ├─ 是 -> DMA + 高优先级完成中断 + 延迟处理
│  │  └─ 否
│  ├─ 是否允许打断其他 ISR？
│  │  ├─ 是 -> 配置独立抢占优先级
│  │  └─ 否 -> 同一抢占层，使用子优先级或软件排序
│  └─ 是否运行 RTOS？
│     ├─ 是 -> ISR 优先级必须遵守 RTOS 可调用边界
│     └─ 否 -> 使用 BASEPRI/PRIMASK 管理临界区
└─ 否
   ├─ 数据量较大？
   │  ├─ 是 -> DMA/FIFO/批量中断
   │  └─ 否 -> 普通外设中断
   └─ 是否有多个来源共享 IRQ？
      ├─ 是 -> ISR 内按状态位逐项确认和清除
      └─ 否 -> 单一外设 ISR
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|电机电流采样，响应要求 1 μs 级|定时器触发 ADC + ADC/DMA 高优先级 ISR|时序确定、减少软件触发抖动|
|高速 UART/CAN 接收|DMA + 环形缓冲区 + 批量通知|避免每字节中断|
|GPIO 紧急故障输入|高抢占优先级 GPIO ISR|快速关断或进入安全态|
|RTOS 系统 Tick|SysTick 或硬件定时器|驱动调度时基|
|RTOS 上下文切换|PendSV 最低优先级|避免打断业务 ISR|
|系统调用|SVC|线程态进入特权内核|
|低功耗唤醒|EXTI/NVIC + 唤醒源配置|处理睡眠状态下的异常恢复|
|Bootloader 跳转 App|清理 IRQ + 设置 VTOR + 设置 MSP|防止异常入口和上下文污染|

---

## 8. 工程最佳实践

## 8.1 中断设计原则

1. **ISR 只做必须立即完成的事情。**
2. **ISR 不执行阻塞操作。**
3. **ISR 不调用不可重入函数。**
4. **ISR 不进行动态内存分配。**
5. **ISR 不打印日志。**
6. **先读取并确认状态，再清除中断源。**
7. **尽量使用 DMA 和硬件 FIFO 降低中断频率。**
8. **所有共享数据明确所有权、访问方向和同步协议。**
9. **每个 ISR 都应有最大执行时间预算。**
10. **每个中断优先级都应记录到系统架构文档。**

### 8.2 推荐优先级架构

```
优先级 0: NMI / 极端安全故障
优先级 1: 电机保护、过流、硬件急停
优先级 2: 高速控制环、精确采样
优先级 3: 高速通信 DMA 完成
优先级 4: 普通外设实时事件
优先级 5~8: RTOS 可调用 ISR
优先级 15: SysTick/PendSV 等低优先级异常
```

实际值取决于：

- 芯片实现的优先级位数。
- RTOS 的 `configMAX_SYSCALL_INTERRUPT_PRIORITY`。
- 控制周期与响应指标。
- 是否使用 TrustZone。
- 是否有安全认证要求。

### 8.3 选型决策矩阵

|需求|PRIMASK|BASEPRI|外设屏蔽|DMA|
|---|---|---|---|---|
|保护极短原子操作|高|中|低|低|
|保留关键实时中断|低|高|高|高|
|降低 CPU 占用|低|低|中|高|
|简单实现|高|中|中|低|
|RTOS 兼容性|低|高|高|高|
|适合大块数据|低|低|中|高|

### 8.4 工业级编码规范

- IRQ 处理函数命名统一。
- 使用 `static` 封装驱动状态。
- 中断状态寄存器只在必要位置读取。
- 所有计数器考虑溢出。
- 环形缓冲区使用无锁单生产者/单消费者模型时，明确读写端。
- 共享变量使用 `volatile`，但不要误认为 `volatile` 提供原子性。
- 对 32 位自然对齐读写进行原子性假设时，要在目标内核上验证。
- 对多字节结构使用序列号、临界区或双缓冲。
- 中断优先级配置集中管理，避免散落在业务代码中。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：只清 NVIC Pending，不清外设状态

### 错误代码

```
void UART_IRQHandler(void)
{
    NVIC_ClearPendingIRQ(UART_IRQn);
}
```

### 根因

UART 外设的接收状态位仍然为 1，NVIC Pending 清除后，外设会再次请求中断。

### 正确实现

```
void UART_IRQHandler(void)
{
    uint32_t status = UART_GetStatus();

    if ((status & UART_STATUS_RX_READY) != 0U) {
        uint8_t byte = UART_ReadData();
        ring_buffer_push_from_isr(&rx_ring, byte);
    }

    if ((status & UART_STATUS_OVERRUN) != 0U) {
        UART_ClearStatus(UART_STATUS_OVERRUN);
        rx_overrun_count++;
    }
}
```

### 风险影响

- 中断立即重入。
- CPU 被中断风暴占满。
- 任务无法调度。
- 看门狗复位。

---

## 9.2 错误二：错误理解优先级数值

### 错误代码

```
NVIC_SetPriority(EMERGENCY_IRQn, 15);
NVIC_SetPriority(LOGGING_IRQn, 0);
```

### 根因

将数值大的优先级误认为优先级高。

### 正确实现

```
NVIC_SetPriority(EMERGENCY_IRQn, 0);
NVIC_SetPriority(LOGGING_IRQn, 15);
```

### 风险影响

- 紧急故障不能及时抢占。
- 日志、低速通信阻塞控制环。
- 出现难以复现的实时性异常。

---

## 9.3 错误三：手动左移优先级后交给 CMSIS

### 错误代码

```
NVIC_SetPriority(TIM_IRQn, 3U << 4);
```

### 根因

CMSIS 接口通常期望未编码的逻辑优先级，接口内部会根据 `__NVIC_PRIO_BITS` 进行编码。

### 正确实现

```
NVIC_SetPriority(TIM_IRQn, 3U);
```

### 风险影响

- 低优先级被错误配置为高优先级。
- RTOS ISR 优先级边界被破坏。
- 不同芯片移植后行为不一致。

---

## 9.4 错误四：ISR 中调用阻塞 API

### 错误代码

```
void SPI_IRQHandler(void)
{
    xSemaphoreTake(spi_mutex, portMAX_DELAY);
    process_spi_frame();
    xSemaphoreGive(spi_mutex);
}
```

### 根因

ISR 没有任务阻塞语义，不能等待互斥锁，也不应调用普通任务 API。

### 正确实现

```
void SPI_IRQHandler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    uint32_t status = SPI_GetStatus();

    if ((status & SPI_STATUS_RX_DONE) != 0U) {
        SPI_ClearStatus(SPI_STATUS_RX_DONE);

        xTaskNotifyFromISR(
            spi_task_handle,
            SPI_EVENT_RX_DONE,
            eSetBits,
            &higher_priority_task_woken);
    }

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

### 风险影响

- 系统死锁。
- 调度器状态破坏。
- 优先级反转。
- 中断上下文访问任务对象导致内核异常。

---

## 9.5 错误五：修改 VTOR 后没有屏障

### 错误代码

```
SCB->VTOR = app_vector_address;
jump_to_application();
```

### 根因

流水线和内存访问可能仍使用旧的向量表视图。

### 正确实现

```
SCB->VTOR = app_vector_address;
__DSB();
__ISB();

jump_to_application();
```

### 风险影响

- 跳转后首次中断进入旧 ISR。
- 只在高优化级别或特定时序下出现问题。
- Bootloader/App 交界问题难以复现。

---

## 9.6 错误六：共享数据只加 `volatile`

### 错误代码

```
volatile uint64_t timestamp;

void TIMER_IRQHandler(void)
{
    timestamp++;
}

uint64_t get_timestamp(void)
{
    return timestamp;
}
```

### 根因

在 32 位 Cortex-M 上，64 位读写通常不是单条指令，可能被 ISR 或其他上下文打断。

### 正确实现：短临界区

```
uint64_t get_timestamp(void)
{
    uint32_t state = __get_PRIMASK();
    __disable_irq();

    uint64_t value = timestamp;

    __set_PRIMASK(state);
    return value;
}
```

### 风险影响

- 读取到撕裂数据。
- 时间戳偶发回退。
- 协议超时和状态机出现随机错误。

---

## 10. 多机制组合使用方案

## 10.1 DMA + NVIC + 环形缓冲区 + RTOS 通知

推荐架构：

```
外设接收
   |
   v
DMA 写入环形缓冲区
   |
   +--> 半传输/全传输/空闲线中断
              |
              v
       NVIC 进入 ISR
              |
              v
       记录 DMA 写指针
              |
              v
       RTOS 通知通信任务
              |
              v
       任务解析协议帧
```

### 代码框架

```
#include <stdint.h>
#include <stdbool.h>
#include "cmsis_gcc.h"

#define RX_DMA_SIZE  256U

static uint8_t rx_dma_buffer[RX_DMA_SIZE];
static volatile uint32_t rx_dma_write_index;
static volatile uint32_t rx_error_count;

static void uart_rx_record_dma_position(void)
{
    uint32_t remaining = UART_DMA_GetRemainingCount();

    if (remaining > RX_DMA_SIZE) {
        rx_error_count++;
        return;
    }

    rx_dma_write_index = RX_DMA_SIZE - remaining;
}

void UART_DMA_IRQHandler(void)
{
    uint32_t status = UART_DMA_GetStatus();

    if ((status & UART_DMA_STATUS_HALF) != 0U) {
        UART_DMA_ClearStatus(UART_DMA_STATUS_HALF);
        uart_rx_record_dma_position();
        rtos_notify_from_isr(RX_EVENT_DATA);
    }

    if ((status & UART_DMA_STATUS_FULL) != 0U) {
        UART_DMA_ClearStatus(UART_DMA_STATUS_FULL);
        uart_rx_record_dma_position();
        rtos_notify_from_isr(RX_EVENT_DATA);
    }

    if ((status & UART_DMA_STATUS_ERROR) != 0U) {
        UART_DMA_ClearStatus(UART_DMA_STATUS_ERROR);
        rx_error_count++;
        rtos_notify_from_isr(RX_EVENT_ERROR);
    }
}
```

设计要点：

- DMA 缓冲区大小必须覆盖最大任务调度抖动。
- 写指针读取需要考虑 DMA 和 CPU 的可见性。
- Cortex-M7 上要处理 Cache。
- DMA 错误必须与数据接收事件区分。
- 任务解析数据，不在 ISR 中执行协议栈。

## 10.2 高优先级安全 ISR + 低优先级控制任务

```
过流比较器
   |
   v
高优先级 IRQ
   |
   +--> 立即关闭 PWM
   +--> 锁存故障寄存器
   +--> 通知安全任务
   |
   v
安全任务记录故障并决定恢复策略
```

高优先级 ISR 只做硬件安全动作：

```
void OVER_CURRENT_IRQHandler(void)
{
    uint32_t status = POWER_GetFaultStatus();

    POWER_DisablePwmOutputs();
    POWER_LatchFault(status);
    POWER_ClearFaultInterrupt();

    fault_event_set_from_isr(FAULT_OVERCURRENT);
}
```

不能在该 ISR 中：

- 写 Flash。
- 打印日志。
- 等待通信发送完成。
- 获取互斥锁。
- 执行复杂故障恢复。

---

## 11. 工业级实际案例分析

## 11.1 案例一：三相电机控制

### 需求

- PWM 频率：20 kHz。
- 控制周期：50 μs。
- ADC 采样必须与 PWM 中点同步。
- 过流保护响应小于 2 μs。
- 控制算法不能被普通通信中断打断。

### 架构

```
PWM 定时器
   |
   +--> ADC 触发
   |
   +--> ADC DMA
             |
             v
       DMA 完成 IRQ
             |
             v
       读取采样结果
             |
             v
       执行快速控制计算

硬件比较器
   |
   v
过流 IRQ，最高业务优先级
   |
   v
关闭 PWM
```

### 优先级建议

```
过流保护 IRQ: 0
ADC/DMA 控制 IRQ: 1
高速通信 IRQ: 3
普通通信 IRQ: 6
RTOS Tick: 14
PendSV: 15
```

### 设计要点

- 过流保护最好由硬件链路直接关断 PWM，NVIC 只负责记录和软件处理。
- ADC 采样由定时器硬件触发，避免软件启动造成采样抖动。
- 控制 ISR 中避免访问慢速外设。
- 若使用 M7，应将关键控制代码与数据放入 TCM 或可控内存区域。
- 控制 ISR 的最坏执行时间必须小于 50 μs，通常还要保留至少 30% 裕量。

---

## 11.2 案例二：工业 Ethernet 或高速串口网关

### 需求

- 接收速率高。
- 帧长不固定。
- CPU 不能被每字节中断占满。
- 协议解析可以延迟到任务上下文。
- 不能丢帧。

### 架构

```
UART/Ethernet MAC
       |
       v
      DMA
       |
       v
环形缓冲区
       |
       +--> 水位中断
       +--> 空闲线/帧结束中断
       |
       v
NVIC ISR
       |
       v
记录读写指针 + 任务通知
       |
       v
协议任务
       |
       v
CRC、组帧、超时、业务处理
```

### 关键计算

假设：

```
接收速率 = 2 MB/s
任务最长调度延迟 = 500 μs
```

最小缓冲需求：

```
Buffer_min = 2 MB/s × 500 μs
           = 1000 bytes
```

考虑突发流量和安全裕量，实际可选择：

```
Buffer_size >= 2048 bytes
```

### 设计要点

- 缓冲区不能只按平均吞吐率设计。
- 需要根据最大不可调度时间计算容量。
- 读写指针必须使用无符号溢出安全比较或明确取模。
- 协议任务应检查帧长度、CRC、序号、超时和重复帧。

---

## 11.3 案例三：Bootloader 与应用程序切换

### 需求

- Bootloader 完成升级后跳转应用。
- App 使用独立向量表。
- 不允许残留中断影响 App 启动。
- 支持升级失败回滚。

### 跳转框架

```
typedef void (*app_entry_t)(void);

static void jump_to_app(uint32_t vector_address)
{
    uint32_t app_msp = *(const uint32_t *)vector_address;
    uint32_t app_reset = *(const uint32_t *)(vector_address + 4U);

    if ((app_msp & 0x7U) != 0U) {
        return;
    }

    if ((app_reset & 0x1U) == 0U) {
        return;
    }

    __disable_irq();

    SysTick->CTRL = 0U;
    SysTick->LOAD = 0U;
    SysTick->VAL = 0U;

    for (IRQn_Type irq = (IRQn_Type)0;
         irq < (IRQn_Type)NUMBER_OF_INT_VECTORS;
         ++irq) {
        NVIC_DisableIRQ(irq);
        NVIC_ClearPendingIRQ(irq);
    }

    SCB->VTOR = vector_address;
    __DSB();
    __ISB();

    __set_MSP(app_msp);
    ((app_entry_t)app_reset)();
}
```

### 设计要点

- 还需要关闭和复位已使用的外设。
- 清除外设自己的中断状态。
- 清除系统异常 Pending 状态。
- 进行镜像签名和完整性校验。
- 处理看门狗、时钟和安全启动状态。
- 不应假设 App 启动代码会自动修复 Bootloader 的所有状态。

---

## 12. 高频问题深度答疑

### 问题一：为什么 NVIC Pending 清了，中断还会马上进来？

因为 Pending 只是 NVIC 的请求状态，真正的中断源通常位于外设内部。例如 UART 的接收非空状态、DMA 的传输完成状态仍然有效，外设会再次向 NVIC 发出请求。

正确顺序通常是：

```
读取外设状态
处理数据
清除外设状态
必要时清除 NVIC Pending
```

但具体顺序必须以芯片参考手册为准。有些外设要求先读状态再读数据，有些要求写特定值清除。

---

### 问题二：为什么关闭中断后仍然能进入某些异常？

`PRIMASK` 只屏蔽可屏蔽异常，不能屏蔽：

- NMI。
- HardFault。

`FAULTMASK` 可以进一步屏蔽 HardFault，但仍不能屏蔽 NMI。安全相关系统通常不应随意使用 `FAULTMASK`，否则可能隐藏真正的故障来源。

---

### 问题三：`volatile` 能否保证中断共享变量安全？

不能。

`volatile` 主要保证编译器不会删除或合并对变量的访问，但不能保证：

- 多字节访问原子性。
- 读改写操作原子性。
- 多个变量之间的顺序一致性。
- DMA 与 Cache 的一致性。
- 任务与 ISR 之间的同步协议。

需要根据数据特征选择：

- 原子类型。
- 短临界区。
- 单生产者单消费者环形队列。
- 双缓冲。
- 序列锁。
- RTOS 通知或事件。

---

### 问题四：为什么 PendSV 通常配置为最低优先级？

PendSV 用于延迟处理和 RTOS 上下文切换。配置为最低优先级可以保证：

- 不打断真正的实时 ISR。
- 等待所有更高优先级中断完成。
- 在系统相对空闲时执行上下文切换。
- 降低调度逻辑对硬实时路径的影响。

SysTick 也不一定必须最低，但不能让它破坏关键控制中断的响应时间。

---

### 问题五：中断优先级分组为什么经常导致 RTOS 问题？

因为工程人员常把：

- NVIC 逻辑优先级。
- 硬件编码后的优先级。
- RTOS 可调用边界。
- 抢占优先级与子优先级。

混为一谈。

RTOS 通常要求：

```
允许调用 FromISR API 的 IRQ
必须处于指定的低优先级范围
```

如果某个 ISR 优先级高于 RTOS 允许范围，却调用了 RTOS API，可能出现：

- 断言失败。
- 调度器临界区被绕过。
- 链表损坏。
- 随机崩溃。

必须统一配置：

```
__NVIC_PRIO_BITS
NVIC_SetPriorityGrouping()
RTOS 优先级宏
各 IRQ 优先级表
```

---

### 问题六：如何测量真正的中断延迟？

推荐使用硬件观测和 DWT 双重验证。

#### GPIO 测量

```
void TIM_IRQHandler(void)
{
    DEBUG_GPIO_SET();

    TIM_ClearInterrupt();
    control_step();

    DEBUG_GPIO_CLEAR();
}
```

逻辑分析仪可以测量：

- IRQ 到 GPIO 翻转的延迟。
- ISR 执行时间。
- 周期抖动。
- 嵌套关系。

#### DWT 测量

```
static uint32_t isr_start_cycle;
static uint32_t isr_max_cycle;

void TIM_IRQHandler(void)
{
    uint32_t start = DWT->CYCCNT;

    TIM_ClearInterrupt();
    control_step();

    uint32_t elapsed = DWT->CYCCNT - start;

    if (elapsed > isr_max_cycle) {
        isr_max_cycle = elapsed;
    }

    isr_start_cycle = start;
}
```

注意：

- `DWT->CYCCNT` 需要先使能。
- 测试应覆盖 Cache miss、DMA 竞争、最高中断负载和 RTOS 调度场景。
- 不能只测平均值，必须记录最大值和分布。

---

## 13. 课程核心总结

### 核心要点

1. **NVIC 管理的是异常响应，不等于外设中断源本身。**
2. **清除 NVIC Pending 不代表清除了外设状态。**
3. **优先级数值越小，逻辑优先级越高。**
4. **只有抢占优先级决定是否可以打断当前 ISR。**
5. **`PRIMASK` 是全局屏蔽，`BASEPRI` 是分层屏蔽。**
6. **ISR 应短小、确定、不可阻塞。**
7. **高吞吐数据优先选择 DMA、FIFO 和批量中断。**
8. **中断实时性必须按最坏情况分析，而不是平均 CPU 占用分析。**
9. **向量表切换必须同步处理 VTOR、MSP、Pending 和外设状态。**
10. **RTOS 中断优先级必须与内核临界区规则统一。**

### 性能排序

按通常的响应确定性和软件开销排序：

```
硬件直连保护逻辑
    >
高优先级普通 IRQ
    >
DMA 完成 IRQ
    >
普通外设 IRQ
    >
RTOS 延迟任务处理
    >
轮询
```

按 CPU 占用从低到高，通常为：

```
DMA 批量传输
    <
FIFO 阈值中断
    <
帧级中断
    <
字节级中断
    <
高频轮询
```

### 通用选型结论

- **硬实时安全动作：硬件保护链路 + 高优先级 IRQ。**
- **高速数据搬运：DMA + 环形缓冲区。**
- **复杂协议解析：ISR 通知任务，任务完成处理。**
- **RTOS 临界区：优先使用 `BASEPRI`，避免无差别关闭所有可屏蔽中断。**
- **单片机简单项目：集中配置优先级，避免过度复杂的优先级分组。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐机制|
|---|---|
|单个 GPIO 紧急输入|GPIO IRQ + 快速状态确认|
|高速 UART 接收|DMA + 空闲线/水位中断|
|ADC 周期采样|定时器触发 + ADC DMA|
|电机过流|硬件关断 + 高优先级 IRQ|
|RTOS 上下文切换|PendSV 最低优先级|
|RTOS 系统调用|SVC|
|保护共享短数据|原子访问或短临界区|
|保护复杂共享结构|`BASEPRI` + 明确同步协议|
|Bootloader 跳 App|清 IRQ + 清外设 + VTOR + MSP|

### 14.2 特性对比表

|机制|作用|关键注意事项|
|---|---|---|
|`NVIC_EnableIRQ`|开启 IRQ|不代表外设已配置正确|
|`NVIC_DisableIRQ`|禁止 IRQ|外设状态可能继续积累|
|`NVIC_SetPendingIRQ`|软件设置 Pending|可用于事件注入和测试|
|`NVIC_ClearPendingIRQ`|清 NVIC Pending|不一定清外设中断源|
|`NVIC_SetPriority`|设置逻辑优先级|数值越小优先级越高|
|`PRIMASK`|全局屏蔽可屏蔽异常|临界区必须极短|
|`BASEPRI`|屏蔽低优先级 IRQ|适合 RTOS 和分层保护|
|`DMB`|保证内存访问顺序|不解决 Cache 一致性|
|`DSB`|等待内存访问完成|用于关键寄存器和异常切换|
|`ISB`|刷新流水线|修改 VTOR、控制寄存器后常用|
|`PendSV`|延迟处理/上下文切换|通常最低优先级|
|`SysTick`|系统节拍|不应阻塞高实时路径|

---

## 15. 学习效果自检

完成本课后，应能够回答并实践以下问题：

- [ ]  能解释外设状态、NVIC Pending 和 Active 三者的区别。
- [ ]  能根据 `__NVIC_PRIO_BITS` 正确配置优先级。
- [ ]  能解释为什么优先级 `0` 高于优先级 `15`。
- [ ]  能区分抢占优先级和子优先级。
- [ ]  能选择 `PRIMASK`、`BASEPRI` 或外设屏蔽位。
- [ ]  能设计一个无锁单生产者单消费者环形缓冲区。
- [ ]  能识别 ISR 中阻塞、打印、动态分配和复杂计算的问题。
- [ ]  能计算中断 CPU 占用率和最小 DMA 缓冲区容量。
- [ ]  能使用 GPIO 和 DWT 测量 ISR 延迟及执行时间。
- [ ]  能分析中断风暴和连续尾链导致的任务饥饿。
- [ ]  能完成 Bootloader 到 App 的向量表切换。
- [ ]  能解释 RTOS 中断优先级边界及 FromISR API 使用限制。
- [ ]  能从 CFSR、HFSR、BFAR、MMFAR 和栈帧定位 Fault。
- [ ]  能为一个真实产品编制完整的 IRQ 优先级表。

---

## 16. 实践与进阶路径

### 阶梯实战任务

#### 任务一：基础 NVIC 状态实验

实现一个定时器 IRQ：

- 配置 IRQ 优先级。
- 动态 Enable/Disable。
- 软件设置 Pending。
- 读取 Pending 和 Active 状态。
- 记录 IRQ 进入次数。

验证内容：

```
IRQ 禁止时是否保持 Pending
IRQ 重新使能后是否立即响应
ISR 执行期间 Active 状态如何变化
```

#### 任务二：中断嵌套实验

配置两个定时器：

```
Timer A: 优先级 2，执行 20 μs
Timer B: 优先级 1，周期性触发
```

测量：

- Timer B 是否抢占 Timer A。
- 抢占延迟。
- 嵌套栈空间。
- 关闭中断后行为变化。

#### 任务三：DMA 环形接收

实现：

- UART DMA 环形缓冲区。
- 半传输、全传输和空闲线中断。
- 任务级协议解析。
- 溢出检测。
- 丢帧统计。

要求记录：

```
最大接收速率
最大任务调度延迟
缓冲区最大占用率
丢帧次数
ISR 最大执行周期
```

#### 任务四：RTOS 优先级边界实验

验证：

- 高优先级 ISR 不调用 RTOS API。
- 低优先级 ISR 使用 FromISR API。
- 错误优先级配置下的断言或故障行为。
- `BASEPRI` 临界区对高优先级 ISR 的影响。

#### 任务五：Fault 现场分析

主动制造以下故障：

- 未对齐访问。
- 非法地址访问。
- 除零。
- 执行非法指令。
- 栈溢出。
- 错误异常返回。

实现 HardFault 捕获框架，输出：

```
R0-R3
R12
LR
PC
xPSR
MSP/PSP
CFSR
HFSR
BFAR
MMFAR
```

### 性能测试方法

至少完成以下测试矩阵：

|测试维度|测量指标|
|---|---|
|空载中断|基础入口/出口周期|
|Flash 执行|ISR 最大周期|
|RAM/TCM 执行|抖动和平均周期|
|DMA 竞争|最坏响应延迟|
|多 IRQ 同时到达|优先级决策和尾链|
|RTOS 运行|任务最大阻塞时间|
|FPU 使用|额外栈空间和上下文开销|
|Cache 开启|Cache miss 对延迟的影响|
|全局关中断|最大不可响应窗口|
|高频突发流量|Pending 堆积和数据丢失率|

### 进阶学习方向

- Cortex-M 异常进入与异常返回指令编码。
- ARMv7-M 与 ARMv8-M 异常模型差异。
- TrustZone-M 的 Secure/Non-secure NVIC。
- MPU 与 MemManage Fault。
- Cortex-M7 Cache、TCM 和 DMA 一致性。
- RTOS `BASEPRI` 临界区实现。
- 实时调度理论中的中断干扰分析。
- WCET，Worst-Case Execution Time，最坏执行时间分析。
- 安全启动、向量表校验和故障注入防护。
- CMSIS-Core、芯片启动文件和链接脚本的异常链路。
- 通过 ETM/ITM/Tracealyzer/SystemView 进行系统级中断时序分析。