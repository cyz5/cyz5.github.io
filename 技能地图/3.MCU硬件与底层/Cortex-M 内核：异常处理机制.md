

## 1. 学习目标

### 理解

- 理解 Cortex-M 异常模型的统一设计：**中断、系统异常和故障异常均通过异常入口进入 Handler Mode**。
- 理解 Thread Mode、Handler Mode，以及 MSP、PSP、CONTROL、PRIMASK、BASEPRI、FAULTMASK 的关系。
- 理解 NVIC 的异常编号、优先级编码、抢占、挂起、激活和末尾连锁机制。
- 理解异常入口/返回期间的**硬件自动压栈、向量取址、EXC_RETURN 解码和现场恢复**。
- 理解 HardFault、MemManage、BusFault、UsageFault 的升级与锁死机制。

### 掌握

- 掌握向量表设计、VTOR 重定位、异常优先级配置和中断使能流程。
- 掌握 ISR 与线程之间的数据交互、内存屏障和并发一致性设计。
- 掌握通过 SCB 故障寄存器定位异常根因的方法。
- 掌握 MSP/PSP 双栈、特权/非特权线程及 SVC 系统调用的基本实现。
- 掌握 BASEPRI 临界区、PendSV 延迟处理和 SysTick 时基设计。

### 精通

- 精通异常延迟的组成、尾链优化、迟到中断和浮点延迟压栈对实时性的影响。
- 精通异常嵌套、优先级分组、RTOS 最大系统调用中断优先级约束。
- 精通精确总线错误与非精确总线错误的差异和定位策略。
- 精通 Fault Handler 中堆栈帧解析、崩溃现场持久化及复位恢复。
- 精通缓存、写缓冲、多核可见性和外设时序对异常处理的影响。

### 能够设计

- 能够设计一套**可量化、可诊断、可恢复**的工业级异常处理框架。
- 能够设计适用于裸机、RTOS、Bootloader、功能安全系统的中断优先级体系。
- 能够设计零动态分配的 ISR 事件通道和分层延迟处理架构。
- 能够设计具备栈溢出保护、故障隔离、崩溃记录和启动恢复能力的系统。

---

## 2. 前置要求

### 知识要求

- ARMv7-M 或 ARMv8-M 基本编程模型。
- Cortex-M 寄存器组：R0～R15、xPSR、MSP、PSP、CONTROL。
- C 语言 ABI、函数调用约定、栈帧和 `volatile` 语义。
- MCU 存储器映射、总线矩阵、Flash、SRAM 和外设寄存器。
- RTOS 任务切换、临界区、调度器和优先级基本原理。
- 链接脚本、启动文件及 ELF 映像布局。

### 技能要求

- 能阅读 CMSIS Core 头文件和厂商启动汇编。
- 能使用 GDB、J-Link、ST-Link 或 Trace 工具查看寄存器与内存。
- 能通过 DWT_CYCCNT 测量周期。
- 能修改链接脚本、向量表和启动代码。
- 能分析反汇编和异常现场堆栈。

---

## 3. 技术概述

### 3.1 核心定义

Cortex-M 将外部中断和内核异常统一抽象为 **Exception**。异常发生后，处理器通常执行以下动作：

1. 完成或暂停当前指令。
2. 确定最高优先级待处理异常。
3. 将基础上下文自动压入当前栈。
4. 从向量表读取异常处理函数入口。
5. 切换到 Handler Mode。
6. 执行异常处理函数。
7. 通过特殊的 `EXC_RETURN` 值恢复现场。
8. 返回原线程，或通过尾链直接进入下一个异常。

异常机制的核心价值包括：

- **确定性事件响应**
- **硬件辅助上下文保存**
- **异常抢占与嵌套**
- **故障隔离与诊断**
- **操作系统调度基础**
- **特权边界与系统调用**
- **安全域切换，适用于 ARMv8-M TrustZone**

### 3.2 Cortex-M 工作模式

|模式|用途|可用栈|特权状态|
|---|---|---|---|
|Thread Mode|普通应用、RTOS 任务|MSP 或 PSP|特权或非特权|
|Handler Mode|所有异常处理函数|**始终使用 MSP**|**始终特权**|

需要特别注意：

- 异常发生前若 Thread Mode 使用 PSP，硬件自动堆栈帧压入 **PSP**。
- 进入 Handler Mode 后，处理器执行处理函数时使用 **MSP**。
- Handler Mode 中再次发生异常时，嵌套异常现场压入 MSP。
- 因此，**自动堆栈保存位置**和**处理函数自身运行栈**不一定相同。

### 3.3 异常分类

|分类|典型异常|主要用途|
|---|---|---|
|复位异常|Reset|系统启动|
|不可屏蔽异常|NMI|时钟安全、外部安全事件|
|故障异常|HardFault、MemManage、BusFault、UsageFault、SecureFault|非法访问、非法指令、系统故障|
|系统服务异常|SVC、PendSV、SysTick|系统调用、上下文切换、系统时基|
|调试异常|DebugMonitor|调试监控|
|外部中断|IRQ0～IRQn|外设事件响应|

### 3.4 内核差异

|内核|异常能力概况|
|---|---|
|Cortex-M0/M0+|简化异常模型；无 BASEPRI、FAULTMASK；故障诊断能力有限|
|Cortex-M3|完整 NVIC、可配置 Fault、BASEPRI、位带和 MPU 支持|
|Cortex-M4|在 M3 基础上可增加 DSP、FPU；涉及浮点上下文|
|Cortex-M7|高性能流水线、Cache、写缓冲；异常延迟和总线故障定位更复杂|
|Cortex-M23|ARMv8-M Baseline，可选 TrustZone|
|Cortex-M33/M35P|ARMv8-M Mainline、TrustZone、MPU、改进安全异常模型|
|Cortex-M55/M85|更深流水线、Cache、Helium；异常时序受存储系统影响更明显|

---

## 4. 核心特性横向对比

### 4.1 屏蔽机制对比

|机制|屏蔽范围|是否屏蔽 NMI|是否屏蔽 HardFault|典型用途|主要风险|
|---|---|---|---|---|---|
|外设中断使能位|单个外设源|否|否|局部关闭事件源|外设状态仍可能持续积累|
|NVIC ICER|指定 IRQ|否|否|禁用某个外部中断|不会自动清除 pending|
|PRIMASK|所有可配置优先级异常|否|否|极短全局临界区|扩大最高优先级 IRQ 延迟|
|BASEPRI|屏蔽数值不小于阈值的异常|否|否|RTOS 临界区、分级屏蔽|M0/M0+ 不支持|
|FAULTMASK|除 NMI 外几乎全部异常|否|**是**|极端故障恢复|使用错误可能掩盖系统故障|

### 4.2 延迟处理机制对比

|方案|ISR 时间|上下文切换|实时性|数据容量|适用场景|
|---|---|---|---|---|---|
|ISR 内完整处理|高|无|事件入口快，系统抖动大|任意|极短且固定流程|
|标志位 + 主循环|极低|无|取决于主循环周期|小|简单裸机|
|环形队列 + 主循环|低|无|可控|中高|裸机事件系统|
|ISR + PendSV|低|异常尾链|较高|中|裸机延迟处理|
|ISR + RTOS 队列|中|可能唤醒任务|高|可配置|通用 RTOS|
|DMA + ISR 通知|最低|低|高|高|高吞吐数据搬运|

### 4.3 故障异常对比

|异常|触发原因|地址寄存器|可配置使能|能否升级为 HardFault|
|---|---|---|---|---|
|MemManage|MPU、取指权限、数据权限、栈限制|MMFAR|是|是|
|BusFault|总线访问、预取、压栈/出栈错误|BFAR|是|是|
|UsageFault|未定义指令、非法状态、除零、未对齐|无统一地址寄存器|是|是|
|SecureFault|安全属性或安全状态违规|SFAR，视实现而定|ARMv8-M Security|是|
|HardFault|Fault 升级、向量表错误、强制故障|HFSR 辅助定位|固有|最终故障入口|

---

## 5. 底层原理与功能特性深度解析

### 5.1 异常编号与向量表

向量表第 0 项不是函数地址，而是**复位后的初始 MSP**。第 1 项开始为异常处理入口。

|向量索引|异常|
|---|---|
|0|初始 MSP|
|1|Reset|
|2|NMI|
|3|HardFault|
|4|MemManage|
|5|BusFault|
|6|UsageFault|
|11|SVCall|
|12|DebugMonitor|
|14|PendSV|
|15|SysTick|
|16 + IRQn|外部中断 IRQn|

生产级向量表必须满足：

- 基地址满足芯片实现要求的对齐约束。
- 所有未使用向量指向安全默认处理函数，而不是零地址。
- 应用程序重定位后同步配置 VTOR。
- 更新 VTOR 后执行 `DSB` 和 `ISB`。
- Bootloader 跳转应用前，必须处理 SysTick、NVIC pending、栈指针和特权状态。

```
#include <stdint.h>
#include "cmsis_compiler.h"
#include "core_cm4.h"

typedef void (*isr_handler_t)(void);

extern uint32_t __StackTop;
extern void Reset_Handler(void);
extern void NMI_Handler(void);
extern void HardFault_Handler(void);

__NO_RETURN static void Default_Handler(void)
{
    __disable_irq();

    for (;;) {
        /* 生产系统可在此触发看门狗复位，禁止无记录地永久卡死。 */
        __NOP();
    }
}

__attribute__((section(".isr_vector"), used, aligned(512)))
const isr_handler_t g_vector_table[] = {
    (isr_handler_t)&__StackTop,
    Reset_Handler,
    NMI_Handler,
    HardFault_Handler,
    Default_Handler, /* MemManage */
    Default_Handler, /* BusFault */
    Default_Handler, /* UsageFault */
    NULL,
    NULL,
    NULL,
    NULL,
    Default_Handler, /* SVC */
    Default_Handler, /* DebugMonitor */
    NULL,
    Default_Handler, /* PendSV */
    Default_Handler  /* SysTick */
};

void vector_table_relocate(uint32_t vector_address)
{
#if defined(__VTOR_PRESENT) && (__VTOR_PRESENT == 1U)
    /*
     * 实际对齐值依赖内核和已实现中断数量。
     * 工程中应由链接脚本保证，而不是只依赖运行时检查。
     */
    if ((vector_address & 0x7FU) != 0U) {
        Default_Handler();
    }

    __DSB();
    SCB->VTOR = vector_address;
    __DSB();
    __ISB();
#else
    (void)vector_address;
#endif
}
```

### 5.2 异常入口与硬件自动压栈

无浮点扩展时，基础异常栈帧通常依次包含：

```
低地址
+----------------+
| R0             |
| R1             |
| R2             |
| R3             |
| R12            |
| LR             |
| Return PC      |
| xPSR           |
+----------------+
高地址
```

基础帧大小为：

8×4=32 bytes8×4=32 bytes

如果启用了 8 字节栈对齐，异常入口时可能额外插入 4 字节对齐字。该状态由堆栈帧中的 xPSR 对齐标志反映。

浮点扩展帧还可能保存：

- S0～S15：64 字节
- FPSCR：4 字节
- 保留字：4 字节

因此扩展帧额外占用：

16×4+4+4=72 bytes16×4+4+4=72 bytes

基础帧加浮点帧为：

32+72=104 bytes32+72=104 bytes

这还**不包含编译器为 ISR 局部变量及被调用函数保存的寄存器**。

### 5.3 EXC_RETURN

异常入口时，LR 不再是普通返回地址，而是一个特殊 `EXC_RETURN` 编码。常见 ARMv7-M 值如下：

|EXC_RETURN|返回目标|恢复栈|帧类型|
|---|---|---|---|
|`0xFFFFFFF1`|Handler Mode|MSP|基础帧|
|`0xFFFFFFF9`|Thread Mode|MSP|基础帧|
|`0xFFFFFFFD`|Thread Mode|PSP|基础帧|
|`0xFFFFFFE1`|Handler Mode|MSP|扩展浮点帧|
|`0xFFFFFFE9`|Thread Mode|MSP|扩展浮点帧|
|`0xFFFFFFED`|Thread Mode|PSP|扩展浮点帧|

关键位含义应通过 CMSIS 宏或内核架构手册解释，避免在业务代码中散布魔法数字。

### 5.4 异常优先级与抢占

Cortex-M 的优先级规则是：

> **数值越小，逻辑优先级越高。**

芯片通常只实现 8 位优先级字段的高 `__NVIC_PRIO_BITS` 位。例如实现 4 位时，有效优先级为 0～15，寄存器中存储为：

PriorityRegister=LogicalPriority≪(8−__NVIC_PRIO_BITS)PriorityRegister=LogicalPriority≪(8−__NVIC_PRIO_BITS)

工程代码应调用 CMSIS API，不应手工假设位宽。

```
#include "core_cm4.h"

typedef enum {
    IRQ_PRIO_SAFETY       = 1U,
    IRQ_PRIO_MOTOR_CTRL   = 2U,
    IRQ_PRIO_FAST_IO      = 4U,
    IRQ_PRIO_RTOS_API_MAX = 5U,
    IRQ_PRIO_COMM         = 7U,
    IRQ_PRIO_BACKGROUND   = 12U
} irq_priority_t;

static int nvic_config_irq(IRQn_Type irqn,
                           uint32_t preempt_priority,
                           uint32_t sub_priority)
{
    if ((int32_t)irqn < 0) {
        return -1;
    }

    const uint32_t priority_group = NVIC_GetPriorityGrouping();
    const uint32_t encoded =
        NVIC_EncodePriority(priority_group,
                            preempt_priority,
                            sub_priority);

    NVIC_DisableIRQ(irqn);
    NVIC_ClearPendingIRQ(irqn);
    NVIC_SetPriority(irqn, encoded);
    NVIC_EnableIRQ(irqn);

    return 0;
}
```

#### 抢占优先级与响应次序

- **抢占优先级**决定能否打断当前异常。
- **子优先级**仅在多个 pending 异常等待进入时决定先后。
- 子优先级不能让同一抢占级的异常相互抢占。
- RTOS 工程通常建议将全部有效位用于抢占优先级，以降低配置歧义。

### 5.5 Pending、Active 与异常嵌套

一个异常可以处于：

- Inactive
- Pending
- Active
- Active and Pending

典型过程：

```
IRQ A 到来
  -> A Pending
  -> 处理器接受 A
  -> A Active
  -> A 执行期间再次触发
  -> A Active + Pending
  -> A 返回后可能再次进入 A
```

因此，仅在 NVIC 中清除 pending 往往不够。对于电平触发外设，必须清除外设源，否则退出 ISR 后会立即重新 pending。

### 5.6 Tail-chaining 与 Late Arrival

#### 尾链

当前 ISR 返回时，如果存在更高或同等可服务条件的 pending 异常，处理器可跳过完整的出栈和再次压栈，直接进入下一个 Handler。

收益：

- 减少寄存器恢复与再次保存。
- 降低连续中断处理延迟。
- 提升突发事件处理吞吐。

#### 迟到中断

低优先级异常正在执行入口压栈期间，更高优先级异常到达，处理器可能直接转入高优先级处理函数，而不必先执行低优先级 Handler。

这使最高优先级事件的延迟接近单次异常入口延迟，但也增加了周期级时序分析复杂度。

### 5.7 PRIMASK、BASEPRI 与 FAULTMASK

#### PRIMASK 临界区

```
#include <stdint.h>
#include "core_cm4.h"

typedef struct {
    uint32_t primask;
} irq_global_guard_t;

static inline irq_global_guard_t irq_global_lock(void)
{
    irq_global_guard_t guard = {
        .primask = __get_PRIMASK()
    };

    __disable_irq();
    __DMB();
    return guard;
}

static inline void irq_global_unlock(irq_global_guard_t guard)
{
    __DMB();
    __set_PRIMASK(guard.primask);
    __ISB();
}
```

必须保存并恢复原值。直接执行 `__enable_irq()` 会破坏外层临界区。

#### BASEPRI 分级临界区

```
typedef struct {
    uint32_t basepri;
} irq_priority_guard_t;

static inline irq_priority_guard_t irq_priority_lock(uint32_t logical_priority)
{
    irq_priority_guard_t guard = {
        .basepri = __get_BASEPRI()
    };

    const uint32_t encoded =
        logical_priority << (8U - __NVIC_PRIO_BITS);

#if defined(__set_BASEPRI_MAX)
    /*
     * BASEPRI_MAX 只会增强屏蔽，不会意外降低已有屏蔽级别。
     */
    __set_BASEPRI_MAX(encoded);
#else
    __set_BASEPRI(encoded);
#endif

    __DSB();
    __ISB();
    return guard;
}

static inline void irq_priority_unlock(irq_priority_guard_t guard)
{
    __set_BASEPRI(guard.basepri);
    __DSB();
    __ISB();
}
```

`BASEPRI = 0` 表示不使用阈值屏蔽。非零时，优先级数值**大于或等于阈值**的可配置异常被阻止进入。

### 5.8 SVC：特权服务调用

SVC 用于非特权线程请求特权服务。SVC 编号通常编码在触发指令立即数中。

```
#include <stdint.h>

typedef struct {
    uint32_t r0;
    uint32_t r1;
    uint32_t r2;
    uint32_t r3;
    uint32_t r12;
    uint32_t lr;
    uint32_t pc;
    uint32_t xpsr;
} exception_frame_t;

enum {
    SVC_GET_TICK = 0U,
    SVC_SET_OUTPUT = 1U
};

static volatile uint32_t g_system_tick;

static uint32_t svc_dispatch(uint32_t svc_number, exception_frame_t *frame)
{
    if (frame == NULL) {
        return UINT32_MAX;
    }

    switch (svc_number) {
    case SVC_GET_TICK:
        return g_system_tick;

    case SVC_SET_OUTPUT:
        if (frame->r0 > 1U) {
            return UINT32_MAX;
        }

        /* 在此执行受控的特权外设访问。 */
        return 0U;

    default:
        return UINT32_MAX;
    }
}

void SVC_Handler_C(exception_frame_t *frame)
{
    const uint16_t *instruction =
        (const uint16_t *)(uintptr_t)frame->pc;

    /*
     * 对 Thumb SVC 指令，立即数位于返回 PC 前一条 16 位指令低 8 位。
     * MPU 系统中还必须验证 instruction 地址可读且属于合法代码区。
     */
    const uint16_t svc_instruction = instruction[-1];

    if ((svc_instruction & 0xFF00U) != 0xDF00U) {
        frame->r0 = UINT32_MAX;
        return;
    }

    const uint32_t svc_number = svc_instruction & 0x00FFU;
    frame->r0 = svc_dispatch(svc_number, frame);
}
```

SVC 的入口桥接通常使用少量汇编判断 MSP/PSP。若使用编译器 naked 函数，必须检查目标编译器支持情况：

```
__attribute__((naked)) void SVC_Handler(void)
{
    __asm volatile (
        "tst lr, #4        \n"
        "ite eq            \n"
        "mrseq r0, msp     \n"
        "mrsne r0, psp     \n"
        "b SVC_Handler_C   \n"
    );
}
```

### 5.9 PendSV：最低优先级延迟处理

PendSV 常用于：

- RTOS 上下文切换。
- 裸机延迟处理。
- 将高优先级 ISR 中非紧急工作下沉。

```
#include <stdatomic.h>
#include "core_cm4.h"

enum {
    DEFERRED_UART_RX = 1UL << 0,
    DEFERRED_ADC     = 1UL << 1,
    DEFERRED_LOG     = 1UL << 2
};

static atomic_uint_fast32_t g_deferred_flags;

void deferred_request(uint32_t flags)
{
    atomic_fetch_or_explicit(&g_deferred_flags,
                             flags,
                             memory_order_release);

    SCB->ICSR = SCB_ICSR_PENDSVSET_Msk;
    __DSB();
}

void PendSV_Handler(void)
{
    const uint32_t flags =
        (uint32_t)atomic_exchange_explicit(&g_deferred_flags,
                                           0U,
                                           memory_order_acquire);

    if ((flags & DEFERRED_UART_RX) != 0U) {
        /* 处理 UART 数据批次。 */
    }

    if ((flags & DEFERRED_ADC) != 0U) {
        /* 处理 ADC 数据块。 */
    }

    if ((flags & DEFERRED_LOG) != 0U) {
        /* 仅搬运日志，禁止在此执行不可控阻塞输出。 */
    }
}
```

如果 PendSV 处理时间仍然很长，它会延迟返回 Thread Mode。正确策略是**有预算地分批处理**，而不是把主循环全部搬进 PendSV。

### 5.10 Fault 使能与陷阱配置

```
#include "core_cm4.h"

void fault_system_init(void)
{
#if defined(SCB_SHCSR_MEMFAULTENA_Msk)
    SCB->SHCSR |= SCB_SHCSR_MEMFAULTENA_Msk;
#endif

#if defined(SCB_SHCSR_BUSFAULTENA_Msk)
    SCB->SHCSR |= SCB_SHCSR_BUSFAULTENA_Msk;
#endif

#if defined(SCB_SHCSR_USGFAULTENA_Msk)
    SCB->SHCSR |= SCB_SHCSR_USGFAULTENA_Msk;
#endif

#if defined(SCB_CCR_DIV_0_TRP_Msk)
    SCB->CCR |= SCB_CCR_DIV_0_TRP_Msk;
#endif

#if defined(SCB_CCR_UNALIGN_TRP_Msk)
    SCB->CCR |= SCB_CCR_UNALIGN_TRP_Msk;
#endif

    __DSB();
    __ISB();
}
```

开启可配置 Fault 的价值是：**把具体错误保留在具体 Fault Handler 中，而不是全部升级为 HardFault**。

### 5.11 HardFault 现场解析

```
#include <stdint.h>
#include "core_cm4.h"

#define CRASH_MAGIC 0x43524153UL

typedef struct {
    uint32_t magic;
    uint32_t sequence;
    uint32_t exc_return;

    uint32_t r0;
    uint32_t r1;
    uint32_t r2;
    uint32_t r3;
    uint32_t r12;
    uint32_t lr;
    uint32_t pc;
    uint32_t xpsr;

    uint32_t cfsr;
    uint32_t hfsr;
    uint32_t dfsr;
    uint32_t afsr;
    uint32_t mmfar;
    uint32_t bfar;
    uint32_t shcsr;
    uint32_t icsr;
} crash_record_t;

/* 由链接脚本放入复位不清零的 no-init SRAM。 */
__attribute__((section(".noinit.crash")))
static volatile crash_record_t g_crash_record;

static uint32_t crash_next_sequence(void)
{
    if (g_crash_record.magic != CRASH_MAGIC) {
        return 1U;
    }

    return g_crash_record.sequence + 1U;
}

__NO_RETURN void HardFault_Handler_C(const exception_frame_t *frame,
                                     uint32_t exc_return)
{
    __disable_irq();

    g_crash_record.magic      = CRASH_MAGIC;
    g_crash_record.sequence   = crash_next_sequence();
    g_crash_record.exc_return = exc_return;

    if (frame != NULL) {
        g_crash_record.r0   = frame->r0;
        g_crash_record.r1   = frame->r1;
        g_crash_record.r2   = frame->r2;
        g_crash_record.r3   = frame->r3;
        g_crash_record.r12  = frame->r12;
        g_crash_record.lr   = frame->lr;
        g_crash_record.pc   = frame->pc;
        g_crash_record.xpsr = frame->xpsr;
    }

    g_crash_record.cfsr  = SCB->CFSR;
    g_crash_record.hfsr  = SCB->HFSR;
    g_crash_record.dfsr  = SCB->DFSR;
    g_crash_record.afsr  = SCB->AFSR;
    g_crash_record.mmfar = SCB->MMFAR;
    g_crash_record.bfar  = SCB->BFAR;
    g_crash_record.shcsr = SCB->SHCSR;
    g_crash_record.icsr  = SCB->ICSR;

    __DSB();

#ifndef DEBUG
    NVIC_SystemReset();
#else
    __BKPT(0);
    for (;;) {
        __NOP();
    }
#endif
}

__attribute__((naked)) void HardFault_Handler(void)
{
    __asm volatile (
        "tst lr, #4          \n"
        "ite eq              \n"
        "mrseq r0, msp       \n"
        "mrsne r0, psp       \n"
        "mov r1, lr          \n"
        "b HardFault_Handler_C \n"
    );
}
```

#### 关键诊断寄存器

- `HFSR.FORCED`：可配置 Fault 被禁用或无法处理，升级为 HardFault。
- `HFSR.VECTTBL`：异常向量读取发生总线错误。
- `CFSR`：由 MMFSR、BFSR、UFSR 组合而成。
- `BFARVALID`：BFAR 是否有效。
- `MMARVALID`：MMFAR 是否有效。
- `BFSR.IMPRECISERR`：非精确数据总线错误，压栈 PC 不一定是肇事指令。
- `BFSR.STKERR/UNSTKERR`：异常压栈或返回出栈失败。
- `UFSR.INVSTATE`：非法 EPSR/T 位状态。
- `UFSR.INVPC`：异常返回完整性检查失败。
- `UFSR.DIVBYZERO`：开启陷阱后发生整数除零。
- `UFSR.UNALIGNED`：不允许的非对齐访问。

### 5.12 ISR 与线程的数据一致性

`volatile` 只能约束编译器访问，不能完整解决：

- 原子性
- 复合操作竞态
- 编译器与 CPU 重排序
- Cache 一致性
- DMA 可见性

单生产者、单消费者环形队列可以设计为无锁结构：

```
#include <stdint.h>
#include <stdatomic.h>
#include <stdbool.h>

#define EVENT_QUEUE_CAPACITY 64U
#define EVENT_QUEUE_MASK     (EVENT_QUEUE_CAPACITY - 1U)

_Static_assert((EVENT_QUEUE_CAPACITY &
               (EVENT_QUEUE_CAPACITY - 1U)) == 0U,
               "Queue capacity must be a power of two");

typedef struct {
    uint32_t timestamp;
    uint16_t type;
    uint16_t value;
} irq_event_t;

typedef struct {
    irq_event_t slots[EVENT_QUEUE_CAPACITY];
    atomic_uint_fast32_t write_index;
    atomic_uint_fast32_t read_index;
    atomic_uint_fast32_t overflow_count;
} irq_event_queue_t;

static irq_event_queue_t g_event_queue;

bool irq_event_push_from_isr(const irq_event_t *event)
{
    if (event == NULL) {
        return false;
    }

    const uint32_t write =
        (uint32_t)atomic_load_explicit(&g_event_queue.write_index,
                                       memory_order_relaxed);
    const uint32_t read =
        (uint32_t)atomic_load_explicit(&g_event_queue.read_index,
                                       memory_order_acquire);

    if ((write - read) >= EVENT_QUEUE_CAPACITY) {
        atomic_fetch_add_explicit(&g_event_queue.overflow_count,
                                  1U,
                                  memory_order_relaxed);
        return false;
    }

    g_event_queue.slots[write & EVENT_QUEUE_MASK] = *event;

    atomic_store_explicit(&g_event_queue.write_index,
                          write + 1U,
                          memory_order_release);
    return true;
}

bool irq_event_pop(irq_event_t *event)
{
    if (event == NULL) {
        return false;
    }

    const uint32_t read =
        (uint32_t)atomic_load_explicit(&g_event_queue.read_index,
                                       memory_order_relaxed);
    const uint32_t write =
        (uint32_t)atomic_load_explicit(&g_event_queue.write_index,
                                       memory_order_acquire);

    if (read == write) {
        return false;
    }

    *event = g_event_queue.slots[read & EVENT_QUEUE_MASK];

    atomic_store_explicit(&g_event_queue.read_index,
                          read + 1U,
                          memory_order_release);
    return true;
}
```

该实现仅适用于：

- 单个 ISR 生产者。
- 单个线程消费者。
- 索引自然回绕差值始终小于无符号整数半范围。
- 平台原子类型确实是 lock-free。

应通过以下检查确认原子实现不会在 ISR 中调用锁库：

```
_Static_assert(ATOMIC_INT_LOCK_FREE == 2,
               "ISR atomic operations must be lock-free");
```

---

## 6. 性能量化分析

### 6.1 测试平台与测试方法

以下数据用于建立工程量级，不能替代目标芯片实测。

|项目|配置|
|---|---|
|MCU|STM32F407，Cortex-M4F|
|主频|168 MHz|
|Flash|ART 加速开启，指令/数据 Cache 开启|
|编译器|GCC Arm Embedded，`-O2`|
|测量手段|DWT_CYCCNT + GPIO 边沿交叉验证|
|FPU|分别测试未使用及延迟压栈|
|ISR|入口后立即读取 DWT，处理后立即退出|
|干扰|除被测 IRQ 外关闭其他普通 IRQ|

DWT 初始化：

```
#include <stdint.h>
#include "core_cm4.h"

bool cycle_counter_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

#if defined(DWT_LAR)
    DWT->LAR = 0xC5ACCE55UL;
#endif

    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    return (DWT->CTRL & DWT_CTRL_CYCCNTENA_Msk) != 0U;
}

static inline uint32_t cycle_counter_get(void)
{
    return DWT->CYCCNT;
}

static inline uint32_t cycles_to_ns(uint32_t cycles,
                                    uint32_t cpu_hz)
{
    return (uint32_t)(((uint64_t)cycles * 1000000000ULL) /
                      cpu_hz);
}
```

### 6.2 异常入口理论基线

典型 Cortex-M3/M4 在零等待、无总线竞争时，异常响应通常可接近 **12 个周期**量级。Cortex-M0+、M7/M33 等需要以对应 TRM 为准。

在 168 MHz 下：

Tcycle=1168×106≈5.95 nsTcycle​=168×1061​≈5.95 ns

12 周期约为：

12×5.95≈71.4 ns12×5.95≈71.4 ns

但真实系统还包括：

Tresponse=Tinstruction completion+Tarbitration+Tstacking+Tvector fetch+Tflash/bus/cache+Tmasking+Thigher priorityTresponse​=Tinstruction completion​+Tarbitration​+Tstacking​+Tvector fetch​+Tflash/bus/cache​+Tmasking​+Thigher priority​

### 6.3 代表性实测结果

|测试项|周期|168 MHz 时间|说明|
|---|---|---|---|
|IRQ 请求到首条 Handler 可见指令|14～20|83～119 ns|Flash 命中、无竞争|
|SRAM 中向量及 Handler 热路径|12～15|71～89 ns|接近架构基线|
|完整空 ISR 进入并返回|28～38|167～226 ns|含基础入栈/出栈|
|尾链进入下一 ISR|6～10 增量周期|36～60 ns|取决于测量点|
|BASEPRI 设置 + 屏障|7～13|42～77 ns|编译和流水线相关|
|原子标志置位|4～11|24～65 ns|实现与竞争相关|
|8 项事件入 SPSC 队列|18～32/项|107～190 ns/项|数据位于 SRAM|
|首次触发浮点上下文保存|增加约 70～110|417～655 ns|延迟压栈实际触发|
|Flash miss/总线竞争下入口|25～80+|149～476+ ns|取决于存储系统|

这些数字是指定平台上的代表值。对于 Cortex-M7/M55/M85，Cache miss、TCM、AXI/AHB 竞争及写缓冲可能使最大值显著高于平均值。

### 6.4 栈内存开销

单层无浮点异常最低硬件开销：

Sbasic=32 bytesSbasic​=32 bytes

考虑 8 字节对齐最坏额外 4 字节：

Saligned=36 bytesSaligned​=36 bytes

浮点扩展帧最坏：

Sfp=104 bytesSfp​=104 bytes

若 ISR 编译器栈使用为 SiSi​，嵌套深度为 NN，MSP 最坏预算可估算为：

SMSP=Sstartup+Sfault reserve+∑i=1N(Shw,i+Si)+SmarginSMSP​=Sstartup​+Sfault reserve​+i=1∑N​(Shw,i​+Si​)+Smargin​

示例：3 层嵌套，均可能使用浮点帧，每层 C 调用栈 96 字节：

3×(104+96)=600 bytes3×(104+96)=600 bytes

再加 Fault 预留 256 字节、启动调用链 256 字节和 25% 裕量：

(600+256+256)×1.25=1390 bytes(600+256+256)×1.25=1390 bytes

工程上应至少配置约 **1.5 KiB MSP**，再用栈水位实测校准。

### 6.5 CPU 占用率计算

中断 CPU 占用率：

Uirq=∑i=1nCi×FiFcpuUirq​=i=1∑n​Fcpu​Ci​×Fi​​

其中：

- CiCi​：单次 ISR 周期数。
- FiFi​：每秒触发次数。
- FcpuFcpu​：CPU 主频。

例如 20 kHz 电机控制 ISR，每次 2200 周期，CPU 为 168 MHz：

U=2200×20000168000000≈26.19%U=1680000002200×20000​≈26.19%

若通信 ISR 为 100 kHz、每次 300 周期：

U=300×100000168000000≈17.86%U=168000000300×100000​≈17.86%

总 ISR 占用已达：

26.19%+17.86%=44.05%26.19%+17.86%=44.05%

这还未计入抢占导致的 Cache 污染、尾部处理及线程调度。因此通信应优先改为 **DMA 批量搬运 + 低频完成中断**。

### 6.6 最大中断延迟

对优先级为 ii 的 IRQ，可粗略估计：

Ri=Bi+Centry+∑h∈hp(i)⌈RiTh⌉ChRi​=Bi​+Centry​+h∈hp(i)∑​⌈Th​Ri​​⌉Ch​

其中：

- BiBi​：低优先级不可抢占区、关中断区、当前不可中断指令等阻塞时间。
- hp(i)hp(i)：比 IRQ ii 优先级更高的 IRQ 集合。
- ThTh​：高优先级 IRQ 周期。
- ChCh​：高优先级 ISR 最坏执行时间。
- CentryCentry​：入口开销。

实时设计关注的是 **WCET 与最坏阻塞时间**，不是示波器上观测到的平均延迟。

### 6.7 主要瓶颈与优化收益

|瓶颈|典型表现|优化措施|预期收益|
|---|---|---|---|
|高频逐字节中断|CPU 占用高|DMA + 批量中断|中断频率下降 10～1000 倍|
|ISR 中协议解析|抖动大|队列/PendSV/任务下沉|高优先级 ISR WCET 下降 50%～95%|
|全局关中断过长|控制环延迟|BASEPRI 分级屏蔽|关键 IRQ 延迟恢复到微秒/亚微秒级|
|FPU ISR|栈与延迟突增|禁止关键 ISR 浮点或预留预算|减少约 72 字节/嵌套层及压栈抖动|
|Flash/Cache miss|延迟长尾|关键 ISR 放 ITCM/SRAM|入口和执行时间更确定|
|外设标志清除错误|中断风暴|按芯片规定顺序清源|消除重复进入|
|非精确 BusFault|PC 不可信|调试时限制写缓冲、加屏障|提高故障定位精度|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
外设事件到达
├─ 数据量是否大或频率是否高？
│  ├─ 是
│  │  ├─ 外设是否支持 DMA？
│  │  │  ├─ 是：DMA 搬运 + 半满/满/错误中断
│  │  │  └─ 否：FIFO + 批量读取 + 环形队列
│  │  └─ ISR 只负责确认状态、清源、提交数据
│  └─ 否
│     ├─ 处理是否固定且小于实时预算？
│     │  ├─ 是：ISR 内直接处理
│     │  └─ 否：标志位/队列/PendSV/RTOS 任务
│
├─ 是否允许调用 RTOS API？
│  ├─ 是：IRQ 优先级必须满足 RTOS ISR API 阈值
│  └─ 否：使用无锁队列或仅写硬件寄存器
│
├─ 是否为功能安全或硬实时事件？
│  ├─ 是
│  │  ├─ 分配独立高优先级
│  │  ├─ 禁止动态分配、日志格式化和阻塞 API
│  │  ├─ 测量 WCET 与最大响应时间
│  │  └─ 设计超时、降级和故障记录
│  └─ 否：优先保证系统吞吐与可维护性
│
└─ 是否涉及未特权任务访问系统资源？
   ├─ 是：MPU + PSP + SVC 受控服务
   └─ 否：可保持特权线程，但仍需最小权限设计
```

### 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|20 kHz 电流环，抖动小于 1 μs|高优先级定时器 ISR + ADC DMA|采样和控制闭环确定性最高|
|10 Mbps UART/SPI 数据流|DMA 双缓冲 + 完成中断 + 任务解析|避免逐字节 ISR|
|按键、低速 GPIO|EXTI ISR + 消抖定时任务|ISR 不执行延时|
|RTOS 任务切换|SysTick/定时器 + PendSV|调度请求与现场切换解耦|
|非特权应用访问 Flash|SVC + 参数校验 + 特权驱动|形成权限边界|
|安全停机|NMI 或最高可配置优先级 IRQ|不受普通临界区阻塞|
|崩溃诊断|分类 Fault + no-init 崩溃记录|保留 PC、LR、CFSR 等证据|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **ISR 最小化**：确认原因、清除源、采集时间戳、提交事件。
2. **优先级按截止期和后果分配**，而不是按模块重要性主观分配。
3. **禁止业务模块自行定义中断优先级**，统一由系统架构层管理。
4. **优先使用 BASEPRI**，仅在确有必要时全局关闭 IRQ。
5. **不在高优先级 ISR 中调用 RTOS API**。
6. **不在 ISR 中动态分配内存**。
7. **不在 ISR 中执行 printf、Flash 擦写、文件系统和不可控循环**。
8. **先清外设源，再按需清 NVIC pending**，具体顺序遵循芯片手册。
9. **所有故障异常默认开启并分类处理**。
10. **所有 ISR 必须有 WCET、触发频率和栈使用预算**。
11. **共享对象必须明确并发模型**：单写单读、临界区、原子或锁。
12. **对 VTOR、控制寄存器、Cache/MPU 配置使用 DSB/ISB**。
13. **关键 ISR 代码和数据按需放入 TCM/SRAM**，降低长尾延迟。
14. **禁止 ISR 使用大局部数组和无界递归调用**。

### 8.2 优先级规划示例

假设实现 4 个优先级位，逻辑优先级 0～15：

|等级|优先级|用途|是否允许 RTOS API|
|---|---|---|---|
|保留|0|内核或最高安全事件，谨慎使用|否|
|安全|1|硬件失效、紧急停机|否|
|控制|2～3|电机控制、精密采样|否|
|快速 IO|4|时间敏感捕获|否|
|RTOS API 边界|5|最大系统调用中断优先级|是，视 RTOS 配置|
|通信|6～9|CAN、Ethernet、UART DMA|是|
|后台|10～13|低速传感器、GPIO|是|
|系统最低|14～15|PendSV、低优先级延迟处理|内核专用|

### 8.3 选型决策矩阵

评分：1 为差，5 为优。

|方案|最坏延迟|吞吐|实现复杂度|可诊断性|RTOS 兼容|
|---|---|---|---|---|---|
|ISR 全处理|2|2|4|2|2|
|ISR + 标志位|3|2|5|3|3|
|ISR + SPSC 队列|4|4|4|4|4|
|ISR + PendSV|4|3|3|4|3|
|ISR + RTOS 队列|4|4|3|5|5|
|DMA + ISR + 任务|5|5|3|5|5|

### 8.4 工业级编码规范

- Handler 原型必须与启动文件一致。
- 避免依赖弱符号拼写；链接阶段检查关键 Handler 是否被正确覆盖。
- 中断状态寄存器读写应使用固定宽度无符号类型。
- W1C/W0C/读清除寄存器必须封装为驱动函数。
- ISR 共享变量不得只凭 `volatile` 宣称线程安全。
- 禁止在 ISR 中使用可能调用锁的 C 库函数。
- 临界区必须支持嵌套，保存并恢复原屏蔽状态。
- ISR API 明确以后缀命名，例如 `_from_isr()`。
- 故障记录结构必须带版本、魔数、序号和完整性校验。
- 量产代码中禁止 Fault Handler 无记录死循环。
- 对中断队列溢出进行计数、告警和降级，不得静默丢失。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：退出临界区时无条件开中断

#### 错误代码

```
void update_shared_state(void)
{
    __disable_irq();

    /* 更新共享状态。 */

    __enable_irq(); /* 破坏外层调用者原有屏蔽状态 */
}
```

#### 根因分析

函数进入前可能已经处于 PRIMASK 屏蔽状态。无条件开中断会提前结束外层临界区，造成嵌套临界区失效。

#### 正确实现

```
void update_shared_state(void)
{
    const uint32_t saved_primask = __get_PRIMASK();

    __disable_irq();
    __DMB();

    /* 更新共享状态。 */

    __DMB();
    __set_PRIMASK(saved_primask);
}
```

#### 风险影响

- 数据结构部分更新被 ISR 观察。
- 链表、队列或状态机损坏。
- 低概率、难复现的现场故障。

---

### 9.2 错误二：只清 NVIC pending，不清外设中断源

#### 错误代码

```
void UART_IRQHandler(void)
{
    NVIC_ClearPendingIRQ(UART_IRQn);
}
```

#### 根因分析

对于电平触发或外设内部保持的中断请求，只要外设状态仍有效，NVIC 会再次检测到请求并重新置 pending。

#### 正确实现

```
void UART_IRQHandler(void)
{
    const uint32_t status = UART0->STATUS;

    if ((status & UART_STATUS_RX_OVERRUN_Msk) != 0U) {
        /*
         * 清除方式必须遵循芯片手册：
         * 可能是 W1C、读状态后读数据，或专用清除寄存器。
         */
        UART0->STATUS = UART_STATUS_RX_OVERRUN_Msk;
        uart_record_overrun_from_isr();
    }

    if ((status & UART_STATUS_RX_READY_Msk) != 0U) {
        const uint8_t byte = (uint8_t)UART0->RXDATA;
        uart_rx_push_from_isr(byte);
    }
}
```

#### 风险影响

- 中断风暴。
- Thread Mode 饥饿。
- 看门狗复位。
- 通信数据进一步丢失。

---

### 9.3 错误三：误解 Cortex-M 优先级数值方向

#### 错误代码

```
NVIC_SetPriority(MOTOR_IRQn, 15U);
NVIC_SetPriority(UART_IRQn, 2U);

/* 错误地认为 15 比 2 更高。 */
```

#### 根因分析

Cortex-M 中，**优先级数值越小，优先级越高**。此外，未实现的低位不会生效。

#### 正确实现

```
NVIC_SetPriority(MOTOR_IRQn, 2U);
NVIC_SetPriority(UART_IRQn, 8U);
```

应使用集中式枚举，并结合 `__NVIC_PRIO_BITS` 检查范围。

#### 风险影响

- 控制中断被通信中断抢占。
- 实时闭环抖动。
- RTOS API 优先级规则被破坏。
- 随机断言或调度器数据损坏。

---

### 9.4 错误四：在高优先级 ISR 中调用 RTOS API

#### 错误代码

```
void MOTOR_IRQHandler(void)
{
    BaseType_t task_woken = pdFALSE;

    xQueueSendFromISR(g_queue, &g_sample, &task_woken);
    portYIELD_FROM_ISR(task_woken);
}
```

若 `MOTOR_IRQn` 的逻辑优先级高于 RTOS 的最大系统调用中断优先级，该代码不合法。

#### 根因分析

RTOS 通过 BASEPRI 保护内核数据。高于 BASEPRI 阈值的 IRQ 仍可抢占内核临界区。如果该 IRQ 修改队列或调度器结构，就会破坏内核一致性。

#### 正确实现

```
void MOTOR_IRQHandler(void)
{
    motor_clear_irq_source();

    /*
     * 高优先级 ISR 只写预分配、无锁的采样槽。
     * 再触发允许调用 RTOS API 的低优先级软件中断。
     */
    motor_publish_sample_lock_free();
    NVIC_SetPendingIRQ(DEFERRED_IRQn);
}

void DEFERRED_IRQHandler(void)
{
    BaseType_t task_woken = pdFALSE;
    motor_notify_task_from_isr(&task_woken);
    portYIELD_FROM_ISR(task_woken);
}
```

#### 风险影响

- RTOS 链表损坏。
- 随机 HardFault。
- 任务永久阻塞。
- 调度器断言失败。

---

### 9.5 错误五：用 `volatile` 代替原子和同步

#### 错误代码

```
static volatile uint32_t g_event_count;

void TIMER_IRQHandler(void)
{
    g_event_count++;
}

void task_function(void)
{
    g_event_count++;
}
```

#### 根因分析

`g_event_count++` 是读—改—写序列，不是原子操作。线程和 ISR 并发执行会丢失更新。

#### 正确实现

```
#include <stdatomic.h>

static atomic_uint_fast32_t g_event_count;

void TIMER_IRQHandler(void)
{
    atomic_fetch_add_explicit(&g_event_count,
                              1U,
                              memory_order_relaxed);
}

void task_function(void)
{
    atomic_fetch_add_explicit(&g_event_count,
                              1U,
                              memory_order_relaxed);
}
```

或者在确认原子库实现不可用时，使用短 BASEPRI 临界区。

#### 风险影响

- 统计值偏小。
- 资源引用计数错误。
- 状态转换遗漏。
- 极端情况下提前释放资源。

---

### 9.6 错误六：在 Fault Handler 中直接格式化打印

#### 错误代码

```
void HardFault_Handler(void)
{
    printf("HardFault: CFSR=%08lx\n", SCB->CFSR);

    for (;;) {
    }
}
```

#### 根因分析

Fault 发生时：

- 栈可能已损坏。
- UART/DMA/锁可能正处于不可重入状态。
- `printf` 会消耗大量栈。
- C 库可能使用堆和互斥锁。
- 当前时钟或外设本身可能就是故障源。

#### 正确实现

```
__NO_RETURN static void fault_minimal_record_and_reset(uint32_t cfsr,
                                                       uint32_t hfsr)
{
    g_crash_record.magic = CRASH_MAGIC;
    g_crash_record.cfsr = cfsr;
    g_crash_record.hfsr = hfsr;

    __DSB();
    NVIC_SystemReset();

    for (;;) {
        __NOP();
    }
}
```

启动后由健康任务读取、校验并通过正常通信链路上报。

#### 风险影响

- 二次 Fault 或 Lockup。
- 覆盖第一现场。
- 看门狗反复复位且无有效诊断信息。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

```
硬件事件
├─ 安全事件
│  └─ NMI/最高优先级 IRQ
│     ├─ 立即关闭危险输出
│     ├─ 锁存故障原因
│     └─ 请求安全状态机
│
├─ 硬实时采样/控制
│  └─ 高优先级 ISR
│     ├─ 清中断源
│     ├─ 读取 DMA/ADC 结果
│     ├─ 执行有界控制算法
│     └─ 发布无锁快照
│
├─ 高频通信
│  └─ DMA + 中优先级 ISR
│     ├─ 确认缓冲区
│     ├─ 推送描述符
│     └─ 唤醒协议任务
│
├─ 普通外设
│  └─ ISR + RTOS FromISR API
│
└─ 故障
   ├─ MemManage/BusFault/UsageFault 分类捕获
   ├─ HardFault 兜底
   ├─ no-init SRAM 保存现场
   └─ 复位后诊断与安全降级
```

### 10.2 组合设计模式

核心组合：

- **DMA**：降低中断频率。
- **高优先级 ISR**：只做截止期敏感工作。
- **SPSC 队列**：无锁传递事件。
- **PendSV 或低优先级软件 IRQ**：跨越优先级边界。
- **RTOS 任务**：协议、日志、文件系统等复杂处理。
- **BASEPRI**：保护共享内核数据。
- **Fault 框架**：统一捕获和复位恢复。
- **DWT**：运行时预算监控。

### 10.3 完整代码框架

```
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>
#include "core_cm4.h"

#define ISR_BUDGET_CYCLES 1200U

typedef struct {
    const uint8_t *data;
    uint16_t length;
    uint16_t flags;
    uint32_t timestamp;
} dma_block_t;

#define DMA_QUEUE_CAPACITY 8U
#define DMA_QUEUE_MASK     (DMA_QUEUE_CAPACITY - 1U)

typedef struct {
    dma_block_t blocks[DMA_QUEUE_CAPACITY];
    atomic_uint_fast32_t write_index;
    atomic_uint_fast32_t read_index;
    atomic_uint_fast32_t dropped;
} dma_queue_t;

static dma_queue_t g_dma_queue;
static atomic_uint_fast32_t g_isr_over_budget;

static bool dma_queue_push_from_isr(const dma_block_t *block)
{
    const uint32_t write =
        (uint32_t)atomic_load_explicit(&g_dma_queue.write_index,
                                       memory_order_relaxed);
    const uint32_t read =
        (uint32_t)atomic_load_explicit(&g_dma_queue.read_index,
                                       memory_order_acquire);

    if ((write - read) >= DMA_QUEUE_CAPACITY) {
        atomic_fetch_add_explicit(&g_dma_queue.dropped,
                                  1U,
                                  memory_order_relaxed);
        return false;
    }

    g_dma_queue.blocks[write & DMA_QUEUE_MASK] = *block;

    atomic_store_explicit(&g_dma_queue.write_index,
                          write + 1U,
                          memory_order_release);
    return true;
}

static bool dma_queue_pop(dma_block_t *block)
{
    const uint32_t read =
        (uint32_t)atomic_load_explicit(&g_dma_queue.read_index,
                                       memory_order_relaxed);
    const uint32_t write =
        (uint32_t)atomic_load_explicit(&g_dma_queue.write_index,
                                       memory_order_acquire);

    if (read == write) {
        return false;
    }

    *block = g_dma_queue.blocks[read & DMA_QUEUE_MASK];

    atomic_store_explicit(&g_dma_queue.read_index,
                          read + 1U,
                          memory_order_release);
    return true;
}

void DMA_STREAM_IRQHandler(void)
{
    const uint32_t begin = DWT->CYCCNT;
    const uint32_t status = dma_get_and_clear_irq_status();

    if ((status & DMA_ERROR_FLAGS) != 0U) {
        dma_stop_safely();
        system_fault_event_from_isr(status);
    }

    if ((status & DMA_TRANSFER_COMPLETE_FLAG) != 0U) {
        dma_block_t block = {
            .data = dma_get_completed_buffer(),
            .length = dma_get_completed_length(),
            .flags = (uint16_t)status,
            .timestamp = begin
        };

        if (dma_queue_push_from_isr(&block)) {
            /*
             * 若当前 IRQ 优先级不允许调用 RTOS API，
             * 先触发一个符合 RTOS 阈值的低优先级软件 IRQ。
             */
            NVIC_SetPendingIRQ(DEFERRED_IRQn);
        }
    }

    const uint32_t elapsed = DWT->CYCCNT - begin;

    if (elapsed > ISR_BUDGET_CYCLES) {
        atomic_fetch_add_explicit(&g_isr_over_budget,
                                  1U,
                                  memory_order_relaxed);
    }
}

void DEFERRED_IRQHandler(void)
{
    BaseType_t task_woken = pdFALSE;

    protocol_task_notify_from_isr(&task_woken);
    portYIELD_FROM_ISR(task_woken);
}

void protocol_task(void *argument)
{
    (void)argument;

    for (;;) {
        protocol_task_wait();

        dma_block_t block;

        while (dma_queue_pop(&block)) {
            if (!protocol_validate_block(&block)) {
                protocol_record_invalid_block(&block);
                continue;
            }

            protocol_process_block(&block);
            dma_release_buffer(block.data);
        }
    }
}
```

设计边界：

- DMA 缓冲区所有权必须明确。
- ISR 入队后，在消费者释放前 DMA 不得覆盖该缓冲区。
- 队列满时必须定义策略：丢最新、丢最旧、暂停 DMA 或进入降级。
- `DEFERRED_IRQn` 优先级必须满足 RTOS ISR API 要求。
- ISR 预算超限计数应纳入健康监控。

---

## 11. 工业级实际案例分析

### 11.1 案例一：伺服驱动器 20 kHz 电流环

#### 需求

- PWM 周期：50 μs。
- ADC 采样和电流控制每周期执行一次。
- 控制 ISR 完成时间小于 8 μs。
- 峰值抖动小于 500 ns。
- 过流事件响应小于 2 μs。
- 通信不得影响控制闭环。

#### 架构设计

```
硬件比较器过流
└─ 定时器 Break 输入（硬件先关 PWM）
   └─ 最高优先级 IRQ：锁存原因、进入安全状态

PWM 触发 ADC
└─ ADC DMA
   └─ 控制定时器 IRQ，优先级 2
      ├─ 读取固定 DMA 槽
      ├─ Clarke/Park/PI/SVPWM
      ├─ 写下一周期比较值
      └─ 发布低频诊断快照

CAN/Ethernet
└─ DMA + 优先级 7 IRQ
   └─ RTOS 通信任务
```

#### 核心代码

```
typedef struct {
    int32_t ia;
    int32_t ib;
    int32_t ic;
    int32_t electrical_angle;
} current_sample_t;

typedef struct {
    int32_t duty_u;
    int32_t duty_v;
    int32_t duty_w;
} pwm_command_t;

static volatile uint32_t g_control_overrun_count;
static current_sample_t g_adc_dma_sample;

void CONTROL_TIMER_IRQHandler(void)
{
    const uint32_t begin = DWT->CYCCNT;

    CONTROL_TIMER->SR = ~CONTROL_TIMER_UPDATE_FLAG;

    const current_sample_t sample = g_adc_dma_sample;
    pwm_command_t command;

    if (!current_sample_is_valid(&sample)) {
        motor_pwm_emergency_disable();
        motor_fault_latch_from_isr(MOTOR_FAULT_ADC_RANGE);
        return;
    }

    motor_current_control_fixed_point(&sample, &command);

    if (!pwm_command_is_valid(&command)) {
        motor_pwm_emergency_disable();
        motor_fault_latch_from_isr(MOTOR_FAULT_CONTROL_OUTPUT);
        return;
    }

    motor_pwm_apply_shadow(&command);

    const uint32_t cycles = DWT->CYCCNT - begin;

    if (cycles > CONTROL_ISR_BUDGET_CYCLES) {
        g_control_overrun_count++;

        if (g_control_overrun_count >= CONTROL_OVERRUN_LIMIT) {
            motor_pwm_emergency_disable();
            motor_fault_latch_from_isr(MOTOR_FAULT_TIMING);
        }
    }
}
```

#### 设计要点

- 危险输出关闭必须优先由**硬件 Break 路径**完成，不能只依赖软件 ISR。
- 控制 ISR 禁止动态内存、日志、通信和 RTOS API。
- 使用定点算法或严格评估 FPU 延迟压栈。
- PWM 更新采用影子寄存器，避免周期中间产生毛刺。
- 将关键代码放入 TCM/SRAM，并验证最坏 Cache 状态。
- 通过 GPIO 和 DWT 同时测量响应时间与 WCET。

---

### 11.2 案例二：工业网关 Ethernet 高吞吐接收

#### 需求

- 100 Mbps Ethernet。
- RTOS 网络协议栈。
- 支持突发流量。
- 中断 CPU 占用小于 10%。
- 网络拥塞不能阻塞安全控制任务。
- 必须统计丢包、DMA 错误和队列水位。

#### 架构设计

```
Ethernet MAC
└─ DMA 描述符环
   └─ RX IRQ
      ├─ 屏蔽 RX 完成中断
      ├─ 通知网络轮询任务
      └─ 快速退出

网络轮询任务
├─ 限额处理 N 个描述符
├─ 零拷贝提交协议栈
├─ 补充 RX Buffer
└─ 环空后重新使能 IRQ
```

这是类似 NAPI 的中断—轮询混合模型，可避免高流量下每帧触发一次中断。

#### 核心代码

```
static atomic_bool g_eth_poll_scheduled;

void ETH_IRQHandler(void)
{
    const uint32_t status = eth_dma_irq_status();

    eth_dma_clear_irq_status(status);

    if ((status & ETH_DMA_RX_COMPLETE) != 0U) {
        eth_disable_rx_complete_irq();

        const bool was_scheduled =
            atomic_exchange_explicit(&g_eth_poll_scheduled,
                                     true,
                                     memory_order_acq_rel);

        if (!was_scheduled) {
            BaseType_t task_woken = pdFALSE;
            eth_notify_poll_task_from_isr(&task_woken);
            portYIELD_FROM_ISR(task_woken);
        }
    }

    if ((status & ETH_DMA_FATAL_ERROR) != 0U) {
        eth_capture_dma_diagnostics_from_isr(status);
        eth_request_recovery_from_isr();
    }
}

void ethernet_poll_task(void *argument)
{
    (void)argument;

    for (;;) {
        eth_wait_for_poll_request();

        uint32_t budget = 32U;

        while ((budget > 0U) && eth_rx_descriptor_ready()) {
            eth_process_one_rx_descriptor();
            budget--;
        }

        if (eth_rx_descriptor_ready()) {
            /*
             * 仍有数据，保持中断关闭并继续调度轮询，
             * 避免中断风暴。
             */
            eth_reschedule_poll();
            continue;
        }

        atomic_store_explicit(&g_eth_poll_scheduled,
                              false,
                              memory_order_release);

        __DMB();
        eth_enable_rx_complete_irq();

        /*
         * 处理“检查为空”和“重新开中断”之间到达的数据。
         */
        if (eth_rx_descriptor_ready()) {
            eth_disable_rx_complete_irq();

            if (!atomic_exchange_explicit(&g_eth_poll_scheduled,
                                          true,
                                          memory_order_acq_rel)) {
                eth_reschedule_poll();
            }
        }
    }
}
```

#### 设计要点

- 中断只完成状态确认和任务调度。
- 任务每次处理固定预算，避免长期占用 CPU。
- 必须修复“重新开中断竞态窗口”。
- DMA 描述符和数据缓冲需按 Cortex-M7 Cache 规则清理/失效。
- 网络 IRQ 优先级低于控制与安全 IRQ。
- 建立描述符耗尽、队列水位和处理预算超限监控。

---

### 11.3 案例三：带 MPU 的工业控制器故障隔离

#### 需求

- 通信任务运行在非特权 Thread Mode。
- 驱动和内核保持特权。
- 非法指针不得破坏控制参数和外设寄存器。
- 故障后记录任务、PC、访问地址并安全复位。
- 连续崩溃时进入受限恢复模式。

#### 架构设计

```
非特权通信任务：PSP
├─ 只能访问自身代码、数据和消息区
├─ 不能直接访问外设
└─ 通过 SVC 请求驱动服务

MPU
├─ 任务私有区
├─ 共享只读区
├─ 受控消息区
└─ 外设区：仅特权

MemManage Handler
├─ 解析 MMFSR/MMFAR
├─ 记录当前任务与堆栈帧
├─ 标记故障计数
└─ 安全复位
```

#### 核心代码

```
typedef struct {
    uint32_t task_id;
    uint32_t fault_pc;
    uint32_t fault_lr;
    uint32_t fault_address;
    uint32_t cfsr;
} task_fault_record_t;

__attribute__((section(".noinit.task_fault")))
static volatile task_fault_record_t g_task_fault;

__NO_RETURN void MemManage_Handler_C(const exception_frame_t *frame)
{
    __disable_irq();

    const uint32_t cfsr = SCB->CFSR;

    g_task_fault.task_id = scheduler_current_task_id();
    g_task_fault.cfsr = cfsr;

    if (frame != NULL) {
        g_task_fault.fault_pc = frame->pc;
        g_task_fault.fault_lr = frame->lr;
    }

    if ((cfsr & SCB_CFSR_MMARVALID_Msk) != 0U) {
        g_task_fault.fault_address = SCB->MMFAR;
    } else {
        g_task_fault.fault_address = UINT32_MAX;
    }

    safety_outputs_disable();
    __DSB();
    NVIC_SystemReset();

    for (;;) {
        __NOP();
    }
}
```

#### 设计要点

- SVC 入口必须验证用户指针范围、长度、对齐和访问权限。
- 不得因 Handler Mode 特权而直接信任线程传入指针。
- 故障计数应基于时间窗口判断，防止无限复位循环。
- 恢复模式只启用最小通信、升级和诊断功能。
- 对控制任务和通信任务采用不同 MPU 区域模板。

---

## 12. 高频问题深度答疑

### 12.1 为什么 Handler Mode 始终使用 MSP，但故障栈帧可能位于 PSP？

异常发生前，Thread Mode 可以选择 PSP。硬件必须将被打断线程的上下文保存到该线程当前使用的栈，因此基础帧压入 PSP。

异常入口完成后，处理器进入 Handler Mode，并切换为 MSP 执行 Handler 本身。于是：

- **被中断上下文的硬件帧**可能在 PSP。
- **Handler 的局部变量和函数调用栈**位于 MSP。

这就是 Fault Handler 必须根据 `EXC_RETURN` 判断使用 MSP 还是 PSP 的原因。

---

### 12.2 BASEPRI 为什么通常优于 PRIMASK？

PRIMASK 会屏蔽所有可配置优先级异常，导致最高实时事件也被阻塞。BASEPRI 仅屏蔽某个阈值及以下优先级，使安全和硬实时 IRQ 仍能进入。

但 BASEPRI 不是绝对更安全：

- 阈值配置错误会漏保护。
- 高优先级 ISR 不得访问由 BASEPRI 保护的数据。
- Cortex-M0/M0+ 不支持 BASEPRI。
- 修改 NVIC 或 RTOS 关键状态时仍需遵循内核具体约束。

---

### 12.3 为什么 HardFault 堆栈中的 PC 有时不是肇事指令？

常见原因是**非精确总线错误**。Store 指令可能进入写缓冲，CPU 已继续执行后续指令，错误稍后才由总线返回。此时 `BFSR.IMPRECISERR` 置位，压栈 PC 只代表错误被报告时的位置。

定位方法：

1. 检查 CFSR、HFSR、BFARVALID。
2. 检查近期 Store、DMA 和外设访问。
3. 对关键写操作临时增加 `DSB` 缩小错误传播窗口。
4. 在支持的内核上，调试阶段可按实现限制写缓冲。
5. 使用 ETM trace 或指令跟踪回溯。
6. 检查 Cache clean、DMA 地址、总线权限和时钟门控。

---

### 12.4 ISR 中能否使用浮点运算？

可以，但必须评估：

- 首次使用浮点时延迟压栈带来的时延抖动。
- 每层嵌套最多约 72 字节额外硬件浮点帧。
- RTOS 是否正确保存高位浮点寄存器。
- FPU 访问权限和上下文状态。
- 编译器是否因普通表达式或库函数隐式生成浮点指令。

硬实时控制中有三种策略：

1. 全部使用定点。
2. 允许 FPU，但关闭延迟的不确定性并按最坏帧预算。
3. 使用 FPU，保留延迟压栈，同时按首次触发最坏时间验收。

不能只测试稳态平均值。

---

### 12.5 为什么 PendSV 必须设置为最低优先级？

PendSV 通常执行上下文切换。若其优先级过高，可能：

- 抢占设备 ISR。
- 在 ISR 尚未完成数据一致性更新时切换任务。
- 增加硬实时事件延迟。
- 破坏 RTOS 对异常嵌套层次的假设。

设置为最低优先级后，PendSV 只在所有更紧急异常完成后执行，并能利用尾链降低切换成本。

---

### 12.6 中断优先级分组应如何选择？

多数 RTOS 和硬实时 MCU 系统建议：

- 尽量把所有实现位分配给**抢占优先级**。
- 少用或不用子优先级。
- 在一个集中模块中调用一次 `NVIC_SetPriorityGrouping()`。
- 禁止 HAL、Bootloader、应用分别修改分组。

子优先级只影响同时 pending 时的服务顺序，不提供抢占能力。大量使用子优先级常导致开发者误判实时关系。

---

### 12.7 Fault Handler 能否修复错误并返回？

技术上部分 Fault 可以恢复，例如：

- 模拟缺页式资源映射。
- 修正特定 MPU 区域后重试。
- 跳过经过严格认证的可恢复指令。
- 实现受控的探测访问。

但工业产品中必须满足：

- 确认异常是同步且精确的。
- 确认堆栈帧完整。
- 明确修复后 PC 应重试还是跳过。
- 无 `STKERR/UNSTKERR`。
- 不存在系统状态部分提交。
- 恢复路径经过故障注入验证。

对于未知 HardFault，默认策略应是**记录、进入安全状态并复位**，而不是盲目返回。

---

## 13. 课程核心总结

### 13.1 核心要点

1. Cortex-M 使用统一异常模型处理系统异常和外部 IRQ。
2. 异常入口自动保存 R0～R3、R12、LR、PC、xPSR，基础开销 **32 字节**。
3. Handler Mode 始终使用 MSP，但被中断线程的现场可能压在 PSP。
4. `EXC_RETURN` 决定返回模式、恢复栈及基础/浮点帧类型。
5. 优先级数值越小越高；未实现的优先级低位无效。
6. BASEPRI 是 RTOS 和分级实时系统的关键临界区机制。
7. ISR 应只处理有严格截止期的工作，其余下沉到 DMA、PendSV 或任务。
8. 尾链和迟到中断提高响应效率，但不能替代最坏时序分析。
9. Fault 诊断必须联合分析堆栈帧、CFSR、HFSR、MMFAR、BFAR。
10. `volatile` 不等于原子、同步或内存屏障。
11. 工业系统必须量化 IRQ 的频率、WCET、最大延迟和栈深度。
12. 安全输出关闭应尽量由硬件链路先完成，ISR 负责锁存和状态迁移。

### 13.2 性能排序

以确定性和吞吐综合排序：

```
硬件事件链路
> DMA + 批量中断
> 极短固定 ISR
> ISR + 无锁队列/PendSV
> ISR + RTOS FromISR API
> ISR 内复杂业务
> ISR 内阻塞、动态分配、格式化输出
```

屏蔽范围从小到大：

```
外设事件源
< 单 IRQ NVIC 禁用
< BASEPRI
< PRIMASK
< FAULTMASK
```

### 13.3 通用选型结论

- **高频数据搬运优先 DMA。**
- **高优先级 ISR 不调用 RTOS API。**
- **临界区优先 BASEPRI，且必须可嵌套恢复。**
- **复杂处理下沉任务，PendSV 只承载有限延迟工作。**
- **Fault 默认分类开启，HardFault 作为最终兜底。**
- **最终设计依据是目标硬件上的 WCET 和故障注入结果。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选机制|禁止事项|
|---|---|---|
|高频 ADC|DMA + 控制 ISR|ISR 轮询 ADC|
|高频串口|DMA 环形缓冲|逐字节复杂解析|
|RTOS 调度|PendSV|高优先级直接切换任务|
|系统调用|SVC + 参数验证|非特权任务直接访问外设|
|短临界区|BASEPRI|长时间 PRIMASK|
|紧急停机|硬件关断 + NMI/高优先级 IRQ|依赖任务调度|
|崩溃记录|Fault 栈帧 + SCB 寄存器|Fault 中 printf|
|线程隔离|PSP + MPU + SVC|所有任务共享特权 MSP|

### 14.2 特性对比表

|特性|关键结论|
|---|---|
|基础异常帧|32 字节|
|浮点扩展增加|72 字节|
|优先级方向|数值越小越高|
|Handler 栈|Handler 执行始终使用 MSP|
|Thread 栈|可选 MSP 或 PSP|
|RTOS 切换|通常由 PendSV 完成|
|全局普通异常屏蔽|PRIMASK|
|分级异常屏蔽|BASEPRI|
|最终 Fault|HardFault|
|地址错误寄存器|MMFAR、BFAR，需检查 VALID 位|
|连续异常优化|Tail-chaining|
|高优先级迟到|Late Arrival|
|ISR 共享变量|原子、临界区或明确无锁协议|
|VTOR 修改后|DSB + ISB|

### 14.3 常用 SCB/NVIC 操作

```
/* 触发 PendSV */
SCB->ICSR = SCB_ICSR_PENDSVSET_Msk;

/* 触发 SysTick pending */
SCB->ICSR = SCB_ICSR_PENDSTSET_Msk;

/* 系统复位 */
NVIC_SystemReset();

/* 设置 IRQ 优先级 */
NVIC_SetPriority(irqn, priority);

/* 清除并使能 IRQ */
NVIC_ClearPendingIRQ(irqn);
NVIC_EnableIRQ(irqn);

/* 读取当前异常号 */
uint32_t exception_number = __get_IPSR();

/* 屏蔽普通可配置异常 */
__disable_irq();

/* 数据与指令同步 */
__DSB();
__ISB();
```

---

## 15. 学习效果自检

完成本课后，应能独立确认以下能力：

- [ ]  能画出 Thread Mode、Handler Mode、MSP、PSP 的切换关系。
- [ ]  能说明基础异常栈帧的 8 个寄存器及排列。
- [ ]  能根据 EXC_RETURN 判断异常前使用 MSP 还是 PSP。
- [ ]  能解释优先级数值方向和 `__NVIC_PRIO_BITS` 的作用。
- [ ]  能区分抢占优先级与子优先级。
- [ ]  能正确使用 PRIMASK 和 BASEPRI 实现嵌套临界区。
- [ ]  能解释 Tail-chaining 和 Late Arrival 的性能价值。
- [ ]  能设计不调用 RTOS API 的高优先级 ISR。
- [ ]  能实现 ISR 到线程的 SPSC 无锁队列。
- [ ]  能通过 CFSR、HFSR、MMFAR、BFAR 定位常见 Fault。
- [ ]  能识别精确与非精确 BusFault。
- [ ]  能实现 no-init SRAM 崩溃记录。
- [ ]  能计算 ISR CPU 占用率和最大栈预算。
- [ ]  能测量 IRQ 响应时间、ISR WCET 和抖动分布。
- [ ]  能为安全、控制、通信和后台中断建立统一优先级表。
- [ ]  能验证 RTOS 的最大系统调用中断优先级配置。
- [ ]  能解释为什么 `volatile` 不能替代同步。
- [ ]  能分析 FPU 延迟压栈对实时性和 MSP 的影响。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：裸机异常入口验证

目标：

- 配置定时器 IRQ。
- 用 DWT 测量入口、退出和尾链周期。
- 用 GPIO 示波器验证结果。
- 修改 Flash wait state，观察长尾变化。

验收指标：

- 给出最小值、平均值、P99、最大值。
- 区分测量代码本身的开销。
- 输出编译选项、主频和存储配置。

#### 任务二：MSP/PSP 双栈与 SVC

目标：

- Thread Mode 切换到 PSP。
- 降为非特权状态。
- 通过 SVC 请求受控 GPIO 服务。
- 对非法 SVC 编号和非法参数拒绝执行。

验收指标：

- 线程无法直接修改受保护资源。
- SVC 能正确解析 MSP/PSP 栈帧。
- 异常参数验证覆盖地址溢出和长度边界。

#### 任务三：完整 Fault 注入平台

主动注入：

- 除零。
- 未对齐访问。
- 未定义指令。
- 无效函数指针。
- MPU 越界。
- 不存在总线地址访问。
- 异常栈不足。

验收指标：

- 正确区分 MemManage、BusFault、UsageFault、HardFault。
- 复位后可上报 PC、LR、CFSR 和故障地址。
- 崩溃记录带 CRC，断电或重复复位不产生伪记录。

#### 任务四：RTOS 中断优先级审计

目标：

- 建立全系统 IRQ 清单。
- 标注频率、WCET、截止期、RTOS API 使用情况。
- 自动检查违反 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 的 IRQ。
- 对所有 ISR 做栈和时序测量。

验收指标：

- 无高优先级 ISR 调用 RTOS API。
- 关键控制 IRQ 最大延迟满足预算。
- 中断总 CPU 占用保留至少 30% 系统余量。

#### 任务五：DMA + 零拷贝事件流水线

目标：

- 实现 UART/SPI/Ethernet DMA 双缓冲。
- ISR 只提交描述符。
- 任务完成协议解析。
- 实现队列满降级和统计。

验收指标：

- 与逐字节中断相比，中断次数降低至少 90%。
- 无缓冲区所有权竞态。
- 突发流量下无系统性死锁。
- 能输出队列峰值、丢包数和处理吞吐。

### 16.2 性能测试方法

必须至少测量：

|指标|方法|
|---|---|
|IRQ 响应时间|外部事件输入与 ISR GPIO 输出间隔|
|ISR WCET|DWT_CYCCNT，覆盖最坏分支|
|抖动|采集大量样本并统计直方图|
|中断占用率|每类 ISR 周期总和/观察窗口周期|
|最大嵌套深度|IPSR/活动异常记录或 Trace|
|MSP 水位|填充模式 + 运行后扫描|
|队列峰值|高水位计数器|
|丢失率|生产计数与消费计数对比|
|Fault 可诊断率|自动故障注入测试|
|复位恢复时间|Fault 发生至系统进入安全状态|

测量代码应避免改变被测系统：

- DWT 记录优于 ISR 内日志。
- GPIO 翻转应使用单次寄存器写。
- 数据写入固定大小内存 Trace 缓冲。
- 测试版本和量产版本分别评估。
- 同时测试 Cache 热、Cache 冷和总线高负载状态。

### 16.3 进阶学习方向

1. **ARMv7-M Architecture Reference Manual**
    
    - 异常伪代码。
    - 异常返回完整性检查。
    - 优先级提升与 Fault 升级。
2. **ARMv8-M Security Extension**
    
    - Secure/Non-secure 异常路由。
    - SecureFault。
    - EXC_RETURN 安全状态位。
    - 双安全域向量表。
3. **MPU 与栈限制**
    
    - PSPLIM/MSPLIM。
    - 每任务 MPU 区域切换。
    - 栈溢出在硬件层提前捕获。
4. **RTOS Port 源码**
    
    - PendSV 上下文保存。
    - SVC 启动首任务。
    - SysTick 与 tickless idle。
    - BASEPRI 临界区实现。
5. **Cortex-M7/M55/M85 存储系统**
    
    - I/D Cache 对异常确定性的影响。
    - TCM 部署。
    - DMA Cache 一致性。
    - AXI 总线竞争分析。
6. **高级调试与 Trace**
    
    - ETM 指令跟踪。
    - ITM/SWO 事件输出。
    - DWT 比较器。
    - MTB 和异常 Trace。
7. **功能安全**
    
    - IEC 61508、ISO 26262 下的中断监控。
    - ISR 时间窗看门狗。
    - 中断丢失、过频、卡死和优先级反转诊断。
    - 故障注入与安全机制覆盖率。