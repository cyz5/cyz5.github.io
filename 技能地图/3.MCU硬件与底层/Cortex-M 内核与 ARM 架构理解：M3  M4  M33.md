
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 **Cortex-M3、Cortex-M4、Cortex-M33** 所对应的 ARM 架构版本：
    - M3：ARMv7-M
    - M4：ARMv7E-M
    - M33：ARMv8-M Mainline
- 理解 Cortex-M 的：
    - 线程模式与处理模式
    - 特权级与非特权级
    - 异常模型与中断入口流程
    - 堆栈帧、异常返回码 EXC_RETURN
    - NVIC、SCB、SysTick、MPU 的职责
- 理解 Thumb-2 指令集、流水线、内存序、屏障指令和独占访问机制。

### 1.2 掌握

能够：

- 从启动文件、向量表和 SCB 寄存器定位系统启动路径。
- 配置 NVIC 中断优先级、优先级分组和异常处理函数。
- 解释中断嵌套、尾链、迟到中断和优先级反转现象。
- 分析函数调用、异常入栈、上下文切换的栈布局。
- 使用 DWT、ITM、SysTick 和 SCB 寄存器进行故障定位。
- 使用 `DMB`、`DSB`、`ISB` 和 LDREX/STREX 实现正确的并发访问。

### 1.3 精通

能够：

- 设计基于 Cortex-M 的异常、启动、故障恢复和低功耗架构。
- 对 M3/M4/M33 的实时性、DSP、FPU、安全隔离能力进行量化选型。
- 分析：
    - HardFault
    - MemManage Fault
    - BusFault
    - UsageFault
    - SecureFault
    - 栈溢出与异常嵌套失败
- 设计带 MPU、TrustZone、Bootloader、Secure/Non-secure 分区的系统。
- 判断某个外设访问是否需要内存屏障，是否存在编译器重排、CPU 重排或总线可见性问题。

### 1.4 能够设计

能够设计以下工业级系统：

- 高实时性电机控制系统的中断架构。
- 带 MPU 任务隔离的安全 RTOS 系统。
- 基于 Cortex-M33 TrustZone 的安全启动和安全服务架构。
- 含 FPU 上下文管理、异常诊断和故障转储的工业控制固件。
- 统一兼容 M3/M4/M33 的底层 BSP 与异常框架。

---

# 2. 前置要求

## 2.1 知识要求

- 熟悉 C 语言：
    - 指针、结构体、位操作
    - `volatile`
    - 函数指针
    - 链接段和启动代码
- 理解 MCU 基本组成：
    - Flash
    - SRAM
    - 总线
    - 中断控制器
    - 定时器
    - DMA
- 了解基本 ARM 汇编：
    - `LDR`
    - `STR`
    - `BL`
    - `BX`
    - `PUSH`
    - `POP`
    - `MRS`
    - `MSR`
- 了解 RTOS 基本概念：
    - 任务
    - 上下文切换
    - 临界区
    - 优先级
    - PendSV
    - SysTick

## 2.2 技能要求

- 能够阅读芯片 Reference Manual 和 Cortex-M Technical Reference Manual。
- 能够使用 Keil、GCC 或 LLVM 编译 Cortex-M 工程。
- 能够使用 J-Link、CMSIS-DAP 或 OpenOCD 调试。
- 能够查看：
    - CPU 寄存器
    - 堆栈
    - 反汇编
    - 异常寄存器
    - MAP 文件
- 至少有一种 Cortex-M3/M4/M33 MCU 的开发经验。

---

# 3. 技术概述

## 3.1 Cortex-M 的定位

Cortex-M 是 ARM 面向微控制器和实时嵌入式系统设计的处理器架构族。其核心设计目标不是最高主频，而是：

- **低中断延迟**
- **低上下文切换成本**
- **低功耗**
- **紧凑代码密度**
- **简单而可预测的异常模型**
- **与 RTOS 天然适配**
- **可选的安全隔离和 DSP/FPU 能力**

Cortex-M 的系统级特征通常包括：

|模块|主要职责|
|---|---|
|NVIC|中断和异常管理|
|SCB|系统控制、故障状态、异常配置|
|SysTick|系统节拍|
|MPU|内存区域访问权限控制|
|DWT|数据观察、性能计数、调试|
|ITM|调试跟踪输出|
|FPB|Flash Patch 和断点|
|FPU|浮点运算，部分内核可选|
|SAU/IDAU|M33 的 TrustZone 安全分区|
|SCS|System Control Space，系统控制空间|

---

## 3.2 三种内核的架构分类

|内核|ARM 架构|指令集|DSP|FPU|MPU|TrustZone|
|---|---|---|---|---|---|---|
|Cortex-M3|ARMv7-M|Thumb-2|基础能力|无|可选|无|
|Cortex-M4|ARMv7E-M|Thumb-2|增强 DSP|可选单精度 FPU|可选|无|
|Cortex-M33|ARMv8-M Mainline|Thumb-2|DSP|可选单/双精度 FPU，取决于实现|可选|可选，通常配合 SAU|

注意：

1. **Cortex-M4 不一定带 FPU**。例如某些芯片命名为 M4，但芯片具体型号可能采用无 FPU 配置。
2. **Cortex-M33 不一定启用 TrustZone**。TrustZone 是架构能力，最终是否暴露取决于芯片实现。
3. MPU、FPU、DSP、TrustZone 都不能仅根据 CPU 名称推断，应通过芯片数据手册、CPUID、特性寄存器和厂商文档确认。

---

## 3.3 ARMv7-M、ARMv7E-M、ARMv8-M 的关系

### ARMv7-M

主要对应 Cortex-M3：

- Thumb-2
- 统一异常模型
- NVIC
- 低延迟中断
- 可选 MPU
- 支持独占访问
- 支持原子同步原语

### ARMv7E-M

主要对应 Cortex-M4：

在 ARMv7-M 基础上增加：

- DSP 指令
- 饱和运算
- SIMD 指令
- 乘加指令
- 可选 FPU

典型 DSP 指令包括：

- `SMLAD`
- `SMLALD`
- `QADD`
- `SSAT`
- `USAT`
- `PKHBT`
- `REV16`

### ARMv8-M Mainline

主要对应 Cortex-M33：

在 ARMv7-M/ARMv7E-M 的基础上增加：

- TrustZone 安全扩展
- Secure/Non-secure 状态
- 安全网关 `SG`
- 更强的异常和安全状态管理
- 可选 MVE 扩展，但 MVE 通常关联 Cortex-M55，而不是 M33
- 更现代化的安全、隔离和软件分区支持

---

# 4. 核心特性横向对比

## 4.1 架构能力对比

|维度|Cortex-M3|Cortex-M4|Cortex-M33|
|---|---|---|---|
|架构|ARMv7-M|ARMv7E-M|ARMv8-M Mainline|
|典型应用|通用控制、通信|电机控制、音频、传感器|安全 MCU、IoT、工业控制|
|Thumb-2|支持|支持|支持|
|DSP|无增强 DSP|强|支持|
|FPU|无|可选单精度|可选，取决于实现|
|TrustZone|不支持|不支持|可选支持|
|MPU|可选|可选|可选|
|安全状态|单一状态|单一状态|Secure / Non-secure|
|原子操作|LDREX/STREX|LDREX/STREX|LDREX/STREX，新增部分原子扩展|
|典型流水线|3 级|3 级|3 级|
|典型主频|50～120 MHz|80～200 MHz|100～250 MHz|
|异常模型|完整|完整|完整并增强安全状态|
|代码迁移难度|基准|较低|需关注安全状态和工具链|

以上主频仅为工程常见范围，不是架构限制。

---

## 4.2 实时性对比

|指标|M3|M4|M33|
|---|---|---|---|
|基本 IRQ 响应|通常 12 个周期左右进入异常|类似|类似|
|尾链|支持|支持|支持|
|迟到中断|支持|支持|支持|
|FPU 上下文开销|无|可能增加|可能增加|
|TrustZone 状态切换|无|无|有额外安全边界成本|
|中断响应主要瓶颈|Flash 等待、屏蔽状态|Flash、FPU、总线竞争|安全状态、Flash、总线和缓存/加速器|

实际中断延迟不能只看 CPU 手册，还必须考虑：

- Flash wait state
- I-Cache/ART/预取
- 总线仲裁
- DMA 抢占
- 临界区
- 中断优先级屏蔽
- FPU lazy stacking
- 安全状态切换
- 外设同步延迟

---

## 4.3 编程模型对比

|内容|M3/M4|M33|
|---|---|---|
|Thread/Handler Mode|支持|支持|
|Privileged/Unprivileged|支持，依赖 CONTROL|支持，Secure 和 Non-secure 各自管理|
|MSP/PSP|支持|Secure/Non-secure 可分别存在|
|PendSV|支持|支持|
|SVC|支持|支持，并增加安全调用语义|
|EXC_RETURN|基本格式|扩展安全状态相关位|
|MPU|可选|可选，Secure/Non-secure 可能分别存在|
|Secure Gateway|不支持|支持|

---

# 5. 底层原理与功能特性深度解析

## 5.1 Cortex-M 寄存器模型

Cortex-M 通用寄存器如下：

|寄存器|用途|
|---|---|
|R0～R3|参数、临时值、返回值|
|R4～R11|被调用者保存寄存器|
|R12|临时寄存器|
|R13|SP，堆栈指针|
|R14|LR，链接寄存器|
|R15|PC，程序计数器|
|xPSR|程序状态寄存器|

xPSR 由三个逻辑部分构成：

- APSR：条件标志
- IPSR：当前异常号
- EPSR：执行状态和 Thumb 状态

### xPSR 关键位

|位|名称|作用|
|---|---|---|
|N|Negative|负数标志|
|Z|Zero|零标志|
|C|Carry|进位标志|
|V|Overflow|溢出标志|
|T|Thumb|Thumb 状态，必须为 1|
|IPSR[8:0]|Exception Number|当前异常号|

Cortex-M 只执行 Thumb 指令。若异常返回或分支导致 T 位非法，通常会触发 UsageFault。

---

## 5.2 栈指针：MSP 与 PSP

Cortex-M 有两个堆栈指针：

- **MSP，Main Stack Pointer**
- **PSP，Process Stack Pointer**

`CONTROL.SPSEL` 决定线程模式下使用哪个栈：

```
static inline uint32_t cm_get_control(void)
{
    uint32_t value;
    __asm volatile ("MRS %0, CONTROL" : "=r"(value) :: "memory");
    return value;
}

static inline void cm_set_psp(uint32_t psp)
{
    __asm volatile ("MSR PSP, %0" : : "r"(psp) : "memory");
}

static inline void cm_use_psp_unprivileged(void)
{
    uint32_t control;

    __asm volatile ("MRS %0, CONTROL" : "=r"(control));
    control |= (1UL << 1); /* SPSEL = 1，线程模式使用 PSP */
    control |= (1UL << 0); /* nPRIV = 1，进入非特权线程 */
    __asm volatile ("MSR CONTROL, %0" : : "r"(control) : "memory");

    /*
     * 修改 CONTROL 后需要 ISB，使后续指令使用新执行上下文。
     */
    __asm volatile ("ISB");
}
```

### 工程建议

- RTOS 任务通常使用 **PSP**。
- 异常处理通常使用 **MSP**。
- 不要让普通任务长期使用 MSP，否则：
    - 任务栈和异常栈混合
    - 栈溢出定位困难
    - 异常嵌套容易破坏任务上下文
- 进入 Handler Mode 后，硬件始终使用 MSP。

---

## 5.3 异常入栈与退出

Cortex-M 发生异常时，硬件通常自动保存以下寄存器：

```
低地址
+----------------+
| R0             |
+----------------+
| R1             |
+----------------+
| R2             |
+----------------+
| R3             |
+----------------+
| R12            |
+----------------+
| LR             |
+----------------+
| PC             |
+----------------+
| xPSR           |
+----------------+
高地址
```

基本异常栈帧大小：

```
8 个寄存器 × 4 字节 = 32 字节
```

如果启用 FPU 且发生浮点上下文保存，可能额外保存：

```
S0～S15、FPSCR、保留字
共 18 个字，共 72 字节
```

因此一次异常可能带来：

```
基本栈帧：32 字节
扩展浮点栈帧：72 字节
总计：104 字节
```

### 异常返回

异常进入时，LR 被设置为特殊的 `EXC_RETURN` 值，而不是普通函数返回地址。

常见值：

|EXC_RETURN|含义|
|---|---|
|`0xFFFFFFF1`|返回 Handler Mode，使用 MSP|
|`0xFFFFFFF9`|返回 Thread Mode，使用 MSP|
|`0xFFFFFFFD`|返回 Thread Mode，使用 PSP|
|bit[4] = 0|返回帧包含浮点上下文|
|bit[4] = 1|返回帧不包含浮点上下文|

异常诊断代码：

```
#include <stdint.h>

typedef struct
{
    uint32_t r0;
    uint32_t r1;
    uint32_t r2;
    uint32_t r3;
    uint32_t r12;
    uint32_t lr;
    uint32_t pc;
    uint32_t xpsr;
} cm_basic_stack_frame_t;

static void fault_decode_frame(const cm_basic_stack_frame_t *frame)
{
    if (frame == NULL) {
        return;
    }

    /*
     * 生产环境中不能使用 printf 作为唯一输出手段。
     * 应写入保留 SRAM、备份寄存器或可靠日志区。
     */
    fault_log_write("R0", frame->r0);
    fault_log_write("R1", frame->r1);
    fault_log_write("R2", frame->r2);
    fault_log_write("R3", frame->r3);
    fault_log_write("R12", frame->r12);
    fault_log_write("LR", frame->lr);
    fault_log_write("PC", frame->pc);
    fault_log_write("xPSR", frame->xpsr);
}

/*
 * 这里的 fault_log_write 由平台提供。
 */
extern void fault_log_write(const char *name, uint32_t value);

__attribute__((naked))
void HardFault_Handler(void)
{
    __asm volatile (
        "tst lr, #4                    \n"
        "ite eq                         \n"
        "mrseq r0, msp                  \n"
        "mrsne r0, psp                  \n"
        "b hardfault_c                 \n"
    );
}

void hardfault_c(const cm_basic_stack_frame_t *frame)
{
    uint32_t hfsr;
    uint32_t cfsr;
    uint32_t mmfar;
    uint32_t bfar;

    fault_decode_frame(frame);

    hfsr  = *((volatile uint32_t *)0xE000ED2CUL);
    cfsr  = *((volatile uint32_t *)0xE000ED28UL);
    mmfar = *((volatile uint32_t *)0xE000ED34UL);
    bfar  = *((volatile uint32_t *)0xE000ED38UL);

    fault_log_write("HFSR", hfsr);
    fault_log_write("CFSR", cfsr);
    fault_log_write("MMFAR", mmfar);
    fault_log_write("BFAR", bfar);

    /*
     * 不建议在 HardFault 中继续复杂业务逻辑。
     * 典型策略：
     * 1. 写入最小故障记录；
     * 2. 关闭看门狗或延长复位窗口；
     * 3. 触发系统复位；
     * 4. 下次启动读取故障记录。
     */
    system_fault_reboot();
}

extern void system_fault_reboot(void);
```

---

## 5.4 异常入口时序

典型中断响应路径：

```
外设产生中断
    ↓
中断请求进入 NVIC
    ↓
NVIC 判断使能、Pending、优先级和屏蔽状态
    ↓
当前指令完成
    ↓
硬件自动压入异常栈帧
    ↓
更新 IPSR
    ↓
从向量表取异常处理函数地址
    ↓
进入 Handler Mode
    ↓
执行 ISR
    ↓
异常返回，自动恢复栈帧
```

### 关键实时性机制

#### 尾链 Tail-Chaining

如果当前 ISR 返回时，另一个更高优先级异常已经 Pending，处理器不需要完整执行：

```
出栈 → 再入栈
```

而是直接切换到下一个 ISR，从而降低异常切换开销。

#### 迟到中断 Late Arrival

在当前异常入栈过程中，如果出现更高优先级异常，处理器可能直接转向优先级更高的异常处理函数，减少不必要的上下文处理。

#### 优先级屏蔽

Cortex-M 主要有以下屏蔽寄存器：

|寄存器|作用|
|---|---|
|PRIMASK|屏蔽除 NMI 和 HardFault 外的可屏蔽异常|
|BASEPRI|屏蔽低于某优先级阈值的中断|
|FAULTMASK|除 NMI 外几乎全部屏蔽|

`BASEPRI` 是 RTOS 中最重要的机制，因为它允许保留高优先级紧急中断。

```
static inline uint32_t irq_save_basepri(uint32_t threshold)
{
    uint32_t old;

    __asm volatile (
        "MRS %0, BASEPRI \n"
        "MSR BASEPRI, %1 \n"
        "DSB              \n"
        "ISB              \n"
        : "=r"(old)
        : "r"(threshold)
        : "memory"
    );

    return old;
}

static inline void irq_restore_basepri(uint32_t old)
{
    __asm volatile (
        "MSR BASEPRI, %0 \n"
        "DSB              \n"
        "ISB              \n"
        :
        : "r"(old)
        : "memory"
    );
}
```

注意：

- `BASEPRI` 的有效优先级编码依赖芯片实现的 `__NVIC_PRIO_BITS`。
- 数字越小通常代表优先级越高。
- 不能直接把逻辑优先级值当成寄存器编码值。

---

## 5.5 NVIC 优先级模型

Cortex-M 的中断优先级通常采用高位有效编码。例如实现 4 个优先级位时：

```
寄存器字节：xxxx0000
             ↑↑↑↑
             有效优先级位
```

逻辑优先级和硬件编码应分离：

```
#include <stdint.h>

#ifndef __NVIC_PRIO_BITS
#define __NVIC_PRIO_BITS 4U
#endif

static uint32_t irq_priority_encode(uint32_t logical_priority)
{
    const uint32_t max_priority = (1UL << __NVIC_PRIO_BITS) - 1UL;

    if (logical_priority > max_priority) {
        logical_priority = max_priority;
    }

    return logical_priority << (8U - __NVIC_PRIO_BITS);
}
```

### 优先级分组

优先级通常分为：

- 抢占优先级
- 子优先级

在 RTOS 系统中，常见原则是：

> **尽量使用统一抢占优先级，不依赖子优先级。**

原因：

- 子优先级不能决定 ISR 是否抢占当前 ISR。
- RTOS 对可调用 API 的中断优先级通常有明确限制。
- 优先级分组配置错误会导致 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 语义失效。

---

## 5.6 SysTick、PendSV、SVC 的职责分工

### SysTick

适合：

- 系统节拍
- 超时基准
- 周期性软件任务
- RTOS tick

不适合：

- 高精度硬实时控制
- 高速数据采样
- 需要极低抖动的 PWM 同步控制

### PendSV

适合：

- 延迟上下文切换
- 将调度动作推迟到所有高优先级 ISR 完成之后
- RTOS 任务切换

### SVC

适合：

- 用户任务调用内核服务
- 非特权代码请求特权服务
- 系统调用边界
- Secure/Non-secure 服务入口的一部分

典型 RTOS 事件流程：

```
SysTick ISR
    ↓
更新时间片和延时队列
    ↓
发现需要调度
    ↓
置位 PendSV
    ↓
高优先级 ISR 执行完毕
    ↓
PendSV 保存当前任务上下文
    ↓
选择下一个任务
    ↓
恢复下一个任务上下文
```

---

## 5.7 Thumb-2 与指令集

Cortex-M 执行 Thumb 指令集，Thumb-2 混合使用：

- 16 位短指令
- 32 位扩展指令

这带来两个工程价值：

- 代码密度高
- 仍可实现复杂寻址和高效控制流

典型编译结果：

```
static inline uint32_t add_and_test(uint32_t a, uint32_t b)
{
    uint32_t result = a + b;
    return result == 0U;
}
```

可能生成类似：

```
add     r0, r0, r1
cmp     r0, #0
ite     eq
moveq   r0, #1
movne   r0, #0
bx      lr
```

工程上不应只看 C 源码判断性能，必须结合：

- `-mcpu=cortex-m3/m4/m33`
- `-mthumb`
- `-mfpu`
- `-mfloat-abi`
- 优化级别
- LTO
- 编译器版本
- 目标芯片 Flash 加速配置

---

## 5.8 M4 的 DSP 指令

M4 相较 M3 的核心优势是 DSP 指令。

### 示例：双 16 位乘加

```
static inline int32_t dot_q15_2(const int16_t *a,
                                const int16_t *b)
{
    uint32_t packed_a;
    uint32_t packed_b;

    packed_a = ((uint32_t)(uint16_t)a[1] << 16) |
               (uint16_t)a[0];

    packed_b = ((uint32_t)(uint16_t)b[1] << 16) |
               (uint16_t)b[0];

    return __SMLAD(packed_a, packed_b, 0);
}
```

`SMLAD` 可以在一次指令中完成两个 16 位乘法并累加：

```
result = a_low × b_low + a_high × b_high + accumulator
```

适合：

- FIR
- IIR
- 电机 Clarke/Park 变换
- 音频采样
- 振动分析
- 传感器融合

### 定点饱和

```
static inline int16_t q15_saturate(int32_t value)
{
    if (value > 32767) {
        return 32767;
    }

    if (value < -32768) {
        return -32768;
    }

    return (int16_t)value;
}
```

使用架构饱和指令时：

```
static inline int32_t signed_saturate_16(int32_t value)
{
    return __SSAT(value, 16);
}
```

定点设计必须明确：

- Q 格式
- 乘法后的扩大位宽
- 舍入方式
- 饱和点
- 溢出行为
- 量化误差上限

---

## 5.9 M4/M33 的 FPU 与 Lazy Stacking

启用 FPU 后，异常上下文可能包含浮点寄存器。为了降低普通 ISR 的开销，Cortex-M 通常支持 **Lazy Stacking**：

- 进入异常时先不立即保存浮点寄存器。
- 如果 ISR 实际执行浮点指令，再补充保存浮点上下文。
- 如果 ISR 不使用 FPU，则不支付完整 FPU 栈帧成本。

### 典型代价

假设：

- CPU：120 MHz
- 基本异常栈帧：32 字节
- 浮点扩展栈帧：72 字节
- SRAM 访问无等待

则：

```
基本栈内存：32 字节
浮点扩展栈内存：72 字节
总计：104 字节
```

在三层异常嵌套情况下，理论额外栈消耗：

```
104 × 3 = 312 字节
```

还没有计算软件保存的 R4～R11 和 RTOS 上下文。

### 工程风险

- 任务栈大小不足。
- 中断中意外调用浮点函数，导致栈消耗突然增加。
- 浮点上下文切换造成抖动。
- RTOS 未正确配置 `FPCA`、FPU 上下文和编译选项。

编译配置必须一致：

```
-mcpu=cortex-m4
-mthumb
-mfpu=fpv4-sp-d16
-mfloat-abi=hard
```

或者：

```
-mfloat-abi=softfp
```

不能混用不同 ABI 的目标文件和库。

---

## 5.10 内存系统与内存属性

Cortex-M 常见内存区域包括：

|区域|典型地址|特征|
|---|---|---|
|Code|`0x00000000` 附近|Flash、ROM、代码执行|
|SRAM|`0x20000000` 附近|可读写、低延迟|
|Peripheral|`0x40000000` 附近|外设寄存器|
|External RAM/Device|视芯片实现|外部存储或设备|
|System|`0xE0000000` 附近|NVIC、SCB、调试组件|

内存属性不仅决定缓存行为，也决定访问是否允许：

- Execute / Execute Never
- Read-only / Read-write
- Shareable
- Device
- Normal memory
- Strongly ordered 等架构语义

对于 Cortex-M，外设寄存器访问必须使用：

```
volatile uint32_t *reg = (volatile uint32_t *)PERIPH_ADDR;
```

但 `volatile` 只能约束编译器，不等价于：

- 原子访问
- CPU 内存屏障
- 总线完成
- 多核同步
- DMA 一致性

---

## 5.11 DMB、DSB、ISB

### DMB：Data Memory Barrier

保证屏障前的数据访问在屏障后的数据访问之前对观察者可见。

适合：

- 生产者先写数据，再设置 ready 标志。
- 外设寄存器访问顺序要求。
- 共享内存同步。

### DSB：Data Synchronization Barrier

等待所有显式内存访问完成后，才继续执行后续指令。

适合：

- 关闭 MPU 后立即执行敏感访问。
- 修改中断控制寄存器后确保生效。
- 进入低功耗前保证外设写入完成。
- 修改系统控制寄存器后执行 `WFI`。

### ISB：Instruction Synchronization Barrier

刷新流水线，使后续指令按照新系统状态重新取指。

适合：

- 修改 `CONTROL`
- 修改 `VTOR`
- 修改 MPU
- 修改权限或执行状态
- 修改系统时钟配置后确保后续执行使用新状态

示例：

```
static inline void enable_mpu_and_sync(void)
{
    SCB->SHCSR |= SCB_SHCSR_MEMFAULTENA_Msk;

    MPU->CTRL = MPU_CTRL_ENABLE_Msk |
                MPU_CTRL_PRIVDEFENA_Msk;

    __DSB();
    __ISB();
}
```

---

## 5.12 LDREX/STREX 与原子操作

独占访问指令通过 exclusive monitor 实现无锁原子更新。

```
static inline int atomic_increment(volatile uint32_t *value)
{
    uint32_t old_value;
    uint32_t new_value;
    uint32_t status;

    do {
        old_value = __LDREXW(value);
        new_value = old_value + 1U;
        status = __STREXW(new_value, value);

        /*
         * STREX 返回 0 表示独占写成功。
         * 返回非 0 表示期间独占状态被破坏，需要重试。
         */
    } while (status != 0U);

    __DMB();

    return 0;
}
```

注意：

- `LDREX/STREX` 不是“禁止中断”。
- 中断、异常、其他总线主设备可能导致独占状态失效。
- 需要限制重试次数，避免极端情况下活锁。
- DMA 与 CPU 的原子语义需要结合芯片总线实现确认。
- 单核 MCU 中，短临界区通常比复杂无锁结构更容易验证。

限制重试版本：

```
static bool atomic_increment_bounded(volatile uint32_t *value,
                                     uint32_t max_retry)
{
    uint32_t i;

    for (i = 0U; i < max_retry; ++i) {
        uint32_t old_value = __LDREXW(value);
        uint32_t status = __STREXW(old_value + 1U, value);

        if (status == 0U) {
            __DMB();
            return true;
        }
    }

    __CLREX();
    return false;
}
```

---

## 5.13 MPU 原理

MPU 将地址空间划分为若干区域，每个区域配置：

- 起始地址
- 大小
- 访问权限
- 执行权限
- 内存类型
- Shareable 属性
- 子区域禁用

典型 RTOS MPU 设计：

```
区域 0：代码区，Privileged/Unprivileged Read-Only，XN = 0
区域 1：任务数据，Read-Write，XN = 1
区域 2：外设窗口，Read-Write，XN = 1
区域 3：任务栈，Read-Write，XN = 1
区域 4：共享缓冲区，按协议开放
区域 5：Guard Region，禁止访问
```

### MPU 配置示例

```
static bool mpu_region_config(uint32_t number,
                              uint32_t base,
                              uint32_t size_rasr)
{
    if ((base & 0x1FU) != 0U) {
        return false;
    }

    MPU->RNR = number;
    MPU->RBAR = base;
    MPU->RASR = size_rasr;

    return true;
}

static void mpu_init(void)
{
    /*
     * 关闭 MPU，避免配置过程中出现不确定访问行为。
     */
    MPU->CTRL = 0U;
    __DSB();
    __ISB();

    /*
     * 示例：配置 32 KB Flash 代码区。
     * 实际 SIZE 编码必须按照 ARM MPU RASR 规范计算。
     * 这里仅展示结构，不应直接复制到任意芯片。
     */
    mpu_region_config(
        0U,
        0x08000000UL,
        MPU_RASR_AP_FULL_ACCESS |
        MPU_RASR_XN_Msk |
        MPU_RASR_ENABLE_Msk
    );

    MPU->CTRL = MPU_CTRL_ENABLE_Msk |
                MPU_CTRL_PRIVDEFENA_Msk;

    __DSB();
    __ISB();
}
```

实际工程必须处理：

- 区域大小必须是 2 的幂。
- 基地址必须按区域大小对齐。
- 区域重叠时，编号更高的区域通常优先级更高。
- 不同芯片 MPU 区域数量不同。
- 需要在故障处理程序中检查 `MMFAR` 和 `CFSR`。

---

## 5.14 M33 TrustZone

Cortex-M33 支持两种安全状态：

```
Secure State
Non-secure State
```

典型系统分层：

```
Secure World
├── 安全启动
├── 密钥管理
├── 加密服务
├── 安全计数器
├── 调试认证
└── Non-secure Callable Gateway

Non-secure World
├── RTOS
├── 应用逻辑
├── 通信协议
├── UI
└── 非关键业务
```

### Secure Gateway

Non-secure 代码不能直接跳转到任意 Secure 地址，必须通过标记为 `cmse_nonsecure_entry` 的安全入口。

```
#include <arm_cmse.h>
#include <stdint.h>

__attribute__((cmse_nonsecure_entry))
int secure_random_get(uint8_t *buffer, uint32_t length)
{
    if (buffer == NULL || length == 0U || length > 64U) {
        return -1;
    }

    /*
     * 必须验证 Non-secure 指针：
     * 1. 地址范围；
     * 2. 可写权限；
     * 3. 长度是否溢出；
     * 4. 是否跨越安全边界。
     */
    if (cmse_check_address_range(buffer,
                                 buffer + length - 1U,
                                 CMSE_MPU_READWRITE) == NULL) {
        return -2;
    }

    return secure_rng_fill(buffer, length);
}

extern int secure_rng_fill(uint8_t *buffer, uint32_t length);
```

### TrustZone 的核心风险

- Secure 函数参数指针未校验。
- Non-secure 回调地址未校验。
- Secure/Non-secure 共享 SRAM 权限配置错误。
- SAU、IDAU、MPU 和芯片厂商安全控制器配置不一致。
- 异常从 Non-secure 跳入 Secure 时，安全状态栈处理错误。
- Secure 中断被错误配置为 Non-secure 可见。

---

# 6. 性能量化分析

以下数据采用典型条件估算，实际结果必须在目标 MCU 上用 DWT 和示波器复测。

## 6.1 基本异常延迟

假设：

- Cortex-M3/M4/M33
- CPU 主频 120 MHz
- Flash 已配置正确等待周期
- 无更高优先级中断
- 无临界区屏蔽
- 向量表位于低延迟存储区域

理论异常响应约为：

```
12 个 CPU 周期 ≈ 12 / 120 MHz = 100 ns
```

如果 Flash 额外引入 3 个等待周期，且向量取指与 ISR 入口受影响：

```
总延迟 ≈ 15 周期
时间 ≈ 15 / 120 MHz = 125 ns
```

实际延迟可能达到数百纳秒甚至数微秒，主要取决于：

- Flash wait state
- 总线竞争
- 中断屏蔽
- 当前指令不可打断窗口
- DMA 和外设同步
- 中断服务程序是否使用 FPU

---

## 6.2 上下文切换成本

以典型 RTOS 为例：

软件保存：

```
R4～R11：8 × 4 = 32 字节
PSP 调整、任务选择和恢复：约 30～100 个周期
```

硬件异常栈帧：

```
R0～R3、R12、LR、PC、xPSR：32 字节
```

典型上下文切换可能为：

```
100～250 个 CPU 周期
```

在 120 MHz 下：

```
100 周期 ≈ 0.83 μs
250 周期 ≈ 2.08 μs
```

如果发生浮点上下文切换，额外栈操作可能带来：

```
约 72 字节栈空间
几十到上百个周期的额外开销
```

---

## 6.3 M3 与 M4 DSP 性能对比

以 64 点 Q15 点积为例。

### M3 标量实现

每个元素大致需要：

```
加载 + 符号扩展 + 乘法 + 累加
```

估算：

```
64 × 4～6 周期 ≈ 256～384 周期
```

### M4 SMLAD 实现

每条 `SMLAD` 处理两个 16 位乘加：

```
64 / 2 = 32 条 SMLAD
```

估算：

```
32～50 周期
```

理论加速比：

```
256 / 50 ≈ 5.1 倍
384 / 50 ≈ 7.7 倍
```

实际加速比会受到：

- 数据对齐
- Flash 取指
- Load/Use 相关
- 循环展开
- 编译器优化
- 内存总线状态

影响。

---

## 6.4 FPU 与软件浮点对比

以单精度乘加为例，典型量级：

|实现|单次操作周期量级|
|---|---|
|M3 软件浮点|数十至数百周期|
|M4 无 FPU软件浮点|数十至数百周期|
|M4 单精度 FPU|通常 1～数周期流水化|
|M33 FPU|取决于具体 FPU 实现和数据路径|

对于 1 kHz 控制循环，每次执行 1000 次浮点运算：

```
软件浮点：1000 × 100 周期 = 100,000 周期
120 MHz 下约 0.833 ms
```

FPU：

```
1000 × 2 周期 = 2,000 周期
120 MHz 下约 16.7 μs
```

但必须把以下因素纳入总预算：

- FPU 上下文保存
- 编译器 ABI
- 浮点函数库
- 中断中使用 FPU
- 浮点异常和 NaN 处理
- 任务切换额外成本

---

## 6.5 DWT 周期测量

```
static void dwt_enable_cycle_counter(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t dwt_measure(void (*func)(void))
{
    uint32_t start;
    uint32_t end;

    if (func == NULL) {
        return 0U;
    }

    DWT->CYCCNT = 0U;
    __DSB();
    start = DWT->CYCCNT;

    func();

    __DSB();
    end = DWT->CYCCNT;

    return end - start;
}
```

工程测量必须明确：

- 是否包含函数调用开销。
- 是否关闭中断。
- 是否清空 Cache 或预取状态。
- 是否包含 Flash wait state。
- 是否发生 DMA 竞争。
- 是否执行多次取最小值、平均值和 P99/P99.9。

---

## 6.6 栈空间量化

任务栈预算可按下式估算：

```
Stack_required =
    Base_task_frame
  + Software_saved_registers
  + Max_ISR_nesting × ISR_frame
  + FPU_frame
  + Library_call_depth
  + Safety_margin
```

示例：

```
基础任务上下文：64 字节
软件保存寄存器：32 字节
最大 ISR 嵌套：3
每级基本异常帧：32 字节
浮点扩展帧：72 字节
调用链余量：256 字节
安全余量：256 字节
```

则：

```
64 + 32 + 3×32 + 72 + 256 + 256
= 776 字节
```

实际配置可向上取整为：

```
1024 字节或 1536 字节
```

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要硬件安全隔离或 Secure/Non-secure 分区？
├── 是
│   └── 选择 Cortex-M33
│       ├── 需要安全启动/密钥/加密服务
│       │   └── 启用 TrustZone + SAU + Secure MPU
│       └── 不需要复杂安全隔离
│           └── 可关闭 TrustZone，作为普通 M33 使用
│
└── 否
    ├── 是否需要 DSP、快速定点运算或浮点？
    │   ├── 是
    │   │   ├── 需要单精度硬件浮点？
    │   │   │   └── 选择带 FPU 的 Cortex-M4
    │   │   └── 仅需要控制和定点运算
    │   │       └── 选择 Cortex-M4，无 FPU 也可
    │   │
    │   └── 否
    │       ├── 资源和成本敏感？
    │       │   └── 选择 Cortex-M3
    │       └── 需要更现代的安全、性能和软件生态？
    │           └── 选择 Cortex-M33
```

---

## 7.2 典型场景选型

|场景|推荐|理由|
|---|---|---|
|工业传感器采集|M3/M4|主要是外设、中断、协议处理|
|三相电机控制|M4|DSP、乘加、饱和运算、FPU|
|音频处理|M4|DSP 和 FPU 更有优势|
|安全网关|M33|TrustZone、安全启动、隔离|
|低成本控制器|M3|成本和功耗优势|
|医疗设备控制|M33/M4|取决于安全隔离和认证要求|
|BLE/Wi-Fi 协处理控制|M4/M33|需要较强协议和安全能力|
|多任务 RTOS 系统|M4/M33|性能和 MPU 能力更适合|
|无线固件升级设备|M33|Secure Boot、密钥隔离|
|简单电机驱动|M3/M4|如果 DSP 计算量较低，M3 也可|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：不要依赖默认异常行为

必须显式配置：

- VTOR
- 优先级分组
- Fault Handler
- FPU
- MPU
- SysTick
- 看门狗
- 栈边界检查

### 原则二：异常处理程序只做最小工作

ISR 推荐执行：

```
读取状态
清除中断源
搬运最小数据
投递事件
退出
```

不推荐：

```
复杂协议解析
动态内存分配
阻塞等待
长时间轮询
printf
浮点密集计算
```

### 原则三：硬实时 ISR 与 RTOS ISR 分层

```
最高优先级：
    电流采样、PWM 同步、过流保护
    不调用 RTOS API

中等优先级：
    DMA 完成、通信接收
    可调用受限 RTOS API

低优先级：
    软件定时、日志、管理任务
```

### 原则四：架构能力必须以芯片实际实现为准

不要仅根据 `Cortex-M4` 或 `Cortex-M33` 判断：

- 是否有 FPU
- 是否有 MPU
- 是否支持 TrustZone
- 是否有 Cache
- 是否有 DWT/ITM
- 是否有足够 NVIC 优先级位

---

## 8.2 选型决策矩阵

评分范围：1～5，分数越高越适合。

|能力|M3|M4|M33|
|---|---|---|---|
|成本敏感|5|4|3|
|基础控制|5|5|5|
|DSP|2|5|4|
|FPU|1|4|4|
|安全隔离|1|1|5|
|RTOS|4|5|5|
|代码兼容性|5|5|4|
|安全启动|2|2|5|
|复杂通信协议|3|4|5|
|认证和隔离|2|2|5|

---

## 8.3 工业级编码规范

- 所有外设寄存器定义必须使用 `volatile`。
- 中断共享变量需要结合：
    - 原子访问
    - 临界区
    - 内存屏障
- 不在 ISR 中调用非 ISR-safe API。
- 不依赖 `int` 的位宽。
- 不假设结构体布局与硬件寄存器完全一致，除非经过静态断言验证。
- 对栈帧解析使用明确结构体和地址合法性检查。
- 对 `SCB->CFSR`、`HFSR` 等故障寄存器进行启动时清理和复位原因记录。
- 不使用未经确认的 CMSIS 位定义。
- 所有优先级配置统一使用逻辑优先级到硬件编码的转换函数。
- 对 TrustZone 的 Non-secure 指针进行边界验证。
- 关键控制代码使用 `-fstack-usage`、静态分析和栈水位监测。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：错误使用 `volatile` 代替原子操作

### 错误代码

```
volatile uint32_t event_flags;

void set_event(uint32_t bit)
{
    event_flags |= bit;
}
```

### 根因

读-改-写不是原子操作：

```
读 event_flags
修改 bit
写回 event_flags
```

如果中断和任务同时修改，可能丢失事件。

### 正确实现

```
static volatile uint32_t event_flags;

void set_event_from_isr(uint32_t bit)
{
    uint32_t primask = __get_PRIMASK();

    __disable_irq();
    event_flags |= bit;
    __set_PRIMASK(primask);
}

uint32_t fetch_events(void)
{
    uint32_t value;
    uint32_t primask = __get_PRIMASK();

    __disable_irq();
    value = event_flags;
    event_flags = 0U;
    __set_PRIMASK(primask);

    return value;
}
```

### 风险影响

- 丢事件
- 状态机卡死
- 偶发数据不一致
- 难以通过普通测试复现

---

## 9.2 错误二：误判 NVIC 优先级数值

### 错误代码

```
NVIC_SetPriority(UART_IRQn, 0x01);
NVIC_SetPriority(TIM_IRQn, 0x02);
```

### 根因

不同抽象层对优先级的定义不同：

- CMSIS 通常接收未左移的逻辑优先级。
- 直接写 NVIC 寄存器时必须左移。
- 数字越小通常优先级越高。

### 正确实现

```
enum
{
    IRQ_PRIO_CRITICAL = 1U,
    IRQ_PRIO_DRIVER   = 5U,
    IRQ_PRIO_LOG      = 12U
};

NVIC_SetPriority(TIM_IRQn, IRQ_PRIO_CRITICAL);
NVIC_SetPriority(UART_IRQn, IRQ_PRIO_DRIVER);
NVIC_SetPriority(DEBUG_IRQn, IRQ_PRIO_LOG);
```

### 风险影响

- 高优先级控制中断被低优先级通信中断延迟。
- RTOS API 调用限制失效。
- 出现难以解释的实时性抖动。

---

## 9.3 错误三：HardFault 中直接使用复杂日志

### 错误代码

```
void HardFault_Handler(void)
{
    printf("HardFault\r\n");
    malloc(128);
    protocol_send_fault_report();
}
```

### 根因

HardFault 发生时，系统可能已经处于：

- 栈损坏
- 时钟异常
- 堆损坏
- 中断嵌套异常
- 外设不可用
- 锁状态未知

### 正确实现

```
void fault_recovery_minimal(uint32_t pc,
                            uint32_t lr,
                            uint32_t cfsr)
{
    fault_record_t record = {
        .magic = FAULT_RECORD_MAGIC,
        .pc = pc,
        .lr = lr,
        .cfsr = cfsr
    };

    backup_sram_write(&record);
    system_fault_reboot();
}
```

### 风险影响

- 二次故障
- 故障现场被覆盖
- 设备无法自动恢复
- 现场出现“死机但没有日志”

---

## 9.4 错误四：启用 FPU 后忽略任务栈空间

### 错误代码

```
static uint8_t task_stack[512];
```

### 根因

实际栈消耗不仅包括任务函数调用，还包括：

- 异常基本栈帧
- 软件保存寄存器
- 浮点上下文
- 中断嵌套
- 库函数调用
- 编译器生成的临时对象

### 正确实现

```
#define TASK_STACK_BYTES \
    (1024U + 2U * 32U + 72U + 256U)

static uint8_t task_stack[TASK_STACK_BYTES]
    __attribute__((aligned(8)));
```

同时启用：

- 栈水位检测
- MPU 栈保护区
- 编译器栈使用报告
- 最大路径测试

### 风险影响

- 任务运行一段时间后崩溃
- 浮点路径触发后才崩溃
- 异常入栈失败，升级为 HardFault 或锁死

---

## 9.5 错误五：修改系统控制寄存器后不执行屏障

### 错误代码

```
SCB->VTOR = vector_table_addr;
__enable_irq();
```

### 根因

修改系统状态寄存器后，流水线和存储系统可能尚未完成同步。

### 正确实现

```
SCB->VTOR = vector_table_addr;
__DSB();
__ISB();
__enable_irq();
```

### 风险影响

- 中断进入错误地址
- 低概率跳转异常
- 仅在高优化或特定 Flash 状态下复现

---

## 9.6 错误六：TrustZone 入口不验证 Non-secure 指针

### 错误代码

```
__attribute__((cmse_nonsecure_entry))
void secure_write(uint8_t *buffer, uint32_t length)
{
    memcpy(secure_storage, buffer, length);
}
```

### 根因

Non-secure 代码可传入：

- 非法地址
- Secure 地址
- 溢出长度
- 只读地址
- 跨越边界的地址

### 正确实现

```
__attribute__((cmse_nonsecure_entry))
int secure_write_checked(const uint8_t *buffer, uint32_t length)
{
    const void *checked;

    if (buffer == NULL || length == 0U || length > 256U) {
        return -1;
    }

    checked = cmse_check_address_range(
        buffer,
        buffer + length - 1U,
        CMSE_MPU_READ
    );

    if (checked == NULL) {
        return -2;
    }

    return secure_storage_write(buffer, length);
}
```

### 风险影响

- Secure 数据泄露
- 任意地址读取
- 安全边界绕过
- 设备被植入持久化恶意代码

---

# 10. 多机制组合使用方案

## 10.1 架构目标

设计一个同时具备以下能力的 Cortex-M 系统：

- RTOS 任务调度
- 中断分层
- MPU 任务隔离
- DWT 性能测量
- HardFault 故障记录
- M33 可选 TrustZone 安全服务

```
+------------------------------------------------+
| Application Tasks                              |
| 传感器任务 / 通信任务 / 控制任务 / 日志任务       |
+-------------------------+----------------------+
                          |
+------------------------------------------------+
| RTOS Kernel             |
| SVC / PendSV / SysTick  |
+------------------------------------------------+
                          |
+-------------------------+----------------------+
| Driver ISR Layer        |
| DMA / UART / Timer      |
+------------------------------------------------+
                          |
+------------------------------------------------+
| Critical ISR Layer      |
| PWM / ADC / Overcurrent |
+------------------------------------------------+
                          |
+------------------------------------------------+
| Cortex-M Core           |
| NVIC / SCB / MPU / DWT  |
| M33: SAU / Secure Gate  |
+------------------------------------------------+
```

---

## 10.2 中断分层框架

```
typedef enum
{
    IRQ_CLASS_CRITICAL = 0,
    IRQ_CLASS_DRIVER,
    IRQ_CLASS_DEFERRED
} irq_class_t;

static volatile uint32_t adc_pending;

void ADC_IRQHandler(void)
{
    uint32_t status = ADC1->ISR;

    if ((status & ADC_ISR_EOC_Msk) != 0U) {
        uint16_t sample = (uint16_t)ADC1->DR;

        /*
         * 关键控制路径：
         * 1. 读取硬件数据；
         * 2. 执行固定上限计算；
         * 3. 不调用阻塞 API；
         * 4. 不访问动态内存。
         */
        motor_control_step(sample);

        ADC1->ISR = ADC_ISR_EOC_Msk;
    }
}

void USART_IRQHandler(void)
{
    uint32_t status = USART1->ISR;

    if ((status & USART_ISR_RXNE_Msk) != 0U) {
        uint8_t data = (uint8_t)USART1->RDR;

        ring_buffer_push_isr(&rx_ring, data);

        /*
         * 仅投递事件，协议解析放到任务中。
         */
        adc_pending |= EVENT_RX_READY;
        __DMB();
    }
}
```

---

## 10.3 RTOS PendSV 上下文切换框架

以下为简化框架，实际需结合具体 RTOS 的任务控制块布局：

```
typedef struct
{
    uint32_t *sp;
    uint32_t priority;
    uint32_t state;
} task_control_block_t;

extern task_control_block_t *current_tcb;
extern task_control_block_t *scheduler_select_next(void);

__attribute__((naked))
void PendSV_Handler(void)
{
    __asm volatile (
        "mrs     r0, psp                    \n"
        "stmdb   r0!, {r4-r11}              \n"

        /*
         * current_tcb->sp = r0
         * 这里不能假设 C 结构体布局，生产代码应通过汇编常量或宏维护偏移。
         */
        "ldr     r3, =current_tcb           \n"
        "ldr     r2, [r3]                   \n"
        "str     r0, [r2]                   \n"

        "push    {r3, lr}                   \n"
        "bl      scheduler_select_next     \n"
        "pop     {r3, lr}                   \n"

        "ldr     r2, [r3]                   \n"
        "ldr     r0, [r2]                   \n"
        "ldmia   r0!, {r4-r11}              \n"
        "msr     psp, r0                    \n"
        "isb                                \n"
        "bx      lr                         \n"
    );
}
```

生产级实现还应考虑：

- `BASEPRI` 临界区状态。
- FPU 上下文。
- 任务栈对齐。
- 首次启动与普通切换的区别。
- TrustZone 下 Secure/Non-secure 任务切换。
- 中断栈和任务栈边界检查。

---

# 11. 工业级实际案例分析

## 11.1 案例一：Cortex-M4 三相电机控制

### 需求

- PWM 频率：20 kHz
- ADC 与 PWM 同步采样
- 控制周期：50 μs
- 控制算法：Clarke、Park、PI、SVPWM
- 允许最大控制 ISR 时间：20 μs
- 通信协议：CAN
- RTOS 负责参数管理和诊断

### 架构

```
PWM Timer Update
    ↓
ADC 采样完成中断
    ↓
读取电流
    ↓
Clarke/Park
    ↓
PI 控制
    ↓
反 Park
    ↓
SVPWM
    ↓
更新 CCR
    ↓
退出 ISR
```

CAN 接收放到低优先级中断，通过队列交给通信任务。

### 核心代码

```
void ADC1_IRQHandler(void)
{
    int16_t ia;
    int16_t ib;
    motor_dq_t dq;
    motor_voltage_t voltage;

    if ((ADC1->ISR & ADC_ISR_EOC_Msk) == 0U) {
        return;
    }

    ia = adc_read_current_a();
    ib = adc_read_current_b();

    dq = motor_clarke_park_q15(ia, ib, motor_get_angle());

    voltage.vd = pi_run_q15(&id_controller, motor_id_ref(), dq.d);
    voltage.vq = pi_run_q15(&iq_controller, motor_iq_ref(), dq.q);

    motor_svpwm_update(voltage);

    ADC1->ISR = ADC_ISR_EOC_Msk;
}
```

### 设计要点

- 使用 M4 DSP 指令优化 Q15 运算。
- 不在控制 ISR 中调用 RTOS API。
- ISR 运行时间必须使用 DWT 统计最大值，而不是平均值。
- 对控制周期做 WCET 分析。
- 对 ADC、PWM、CPU 时钟使用同一时钟树进行同步校验。

### 性能预算

假设 CPU 168 MHz：

```
控制周期：50 μs
总周期：168 MHz × 50 μs = 8400 cycles
```

若控制 ISR 预算为 20%：

```
8400 × 20% = 1680 cycles
```

如果实际最大值为 1200 cycles，则余量：

```
1680 - 1200 = 480 cycles
```

应继续保留：

- Flash 抖动余量
- 最高优先级保护 ISR
- 编译器版本变化余量
- 未来算法升级余量

---

## 11.2 案例二：Cortex-M33 安全 IoT 网关

### 需求

- Secure Boot
- OTA 固件升级
- 设备密钥隔离
- Non-secure 运行 RTOS
- Secure 提供加密、随机数和密钥服务
- 防止普通应用读取密钥

### 架构

```
Secure
├── Boot ROM / Secure Boot
├── Secure Image 验证
├── 密钥存储
├── AES/ECC 服务
├── TRNG 服务
├── Secure Counter
└── Secure Gateway

Non-secure
├── TCP/IP
├── MQTT
├── OTA 下载
├── 应用任务
└── 用户配置
```

### Secure API 设计原则

```
typedef struct
{
    uint32_t opcode;
    uint32_t input_len;
    uint32_t output_len;
    uint8_t *input;
    uint8_t *output;
} secure_request_t;

int secure_service_call(secure_request_t *request)
{
    if (request == NULL) {
        return SECURE_ERR_PARAM;
    }

    if (request->input_len > SECURE_MAX_INPUT ||
        request->output_len > SECURE_MAX_OUTPUT) {
        return SECURE_ERR_LENGTH;
    }

    if (!secure_validate_ns_buffer(request->input,
                                   request->input_len,
                                   false)) {
        return SECURE_ERR_INPUT;
    }

    if (!secure_validate_ns_buffer(request->output,
                                   request->output_len,
                                   true)) {
        return SECURE_ERR_OUTPUT;
    }

    switch (request->opcode) {
    case SECURE_OP_RANDOM:
        return secure_random_get(request->output,
                                 request->output_len);

    case SECURE_OP_SIGN:
        return secure_sign(request->input,
                           request->input_len,
                           request->output,
                           request->output_len);

    default:
        return SECURE_ERR_OPCODE;
    }
}
```

### 设计要点

- Secure API 必须是**显式、有限、可审计**的。
- Secure 不应暴露原始密钥。
- Non-secure 输入输出必须进行地址和长度校验。
- OTA 镜像验证必须在 Secure 环境完成。
- Secure Fault 需要独立记录。
- 调试口必须有生命周期状态控制。

---

## 11.3 案例三：Cortex-M3 工业传感器节点

### 需求

- 低成本
- 低功耗
- 采集温度、压力、振动
- RS-485 通信
- 10 ms 数据处理周期
- 不需要浮点和安全分区

### 架构

```
SysTick / RTC
    ↓
唤醒采集任务
    ↓
ADC/DMA 获取数据
    ↓
定点滤波
    ↓
阈值判断
    ↓
RS-485 通信
    ↓
进入低功耗
```

### 设计要点

- 使用 Q 格式避免软件浮点。
- 使用 DMA 降低 CPU 搬运开销。
- 采样数据使用环形缓冲区。
- 进入低功耗前使用 `DSB`。
- 通过 GPIO 翻转或 DWT 测量唤醒路径耗时。
- 中断只做数据搬运，滤波放到任务或主循环。

---

# 12. 高频问题深度答疑

## 12.1 为什么 Cortex-M 中断延迟低于传统 MCU？

核心原因不是单一因素，而是多个机制协同：

1. 硬件自动保存基本寄存器。
2. 向量表直接给出处理函数地址。
3. NVIC 与 CPU 深度集成。
4. 支持尾链。
5. 支持迟到中断。
6. 异常优先级由硬件比较。
7. 不需要软件模拟复杂中断入口。

但“理论 12 周期”不等于系统总响应时间。必须叠加：

```
总响应时间 =
CPU 异常入口
+ Flash/总线等待
+ 屏蔽时间
+ 外设同步
+ 高优先级 ISR 执行
```

---

## 12.2 为什么 RTOS 选择 PendSV 作为上下文切换入口？

因为 PendSV 可以被设置为最低优先级。

这样可以保证：

```
硬实时 ISR
    ↓
普通设备 ISR
    ↓
PendSV 执行调度
```

如果在 SysTick 中直接做完整上下文切换，可能导致：

- SysTick ISR 过长
- 其他高优先级中断响应受影响
- ISR 嵌套关系复杂
- 调度和时间基准耦合

PendSV 将“请求调度”和“执行调度”分离，架构更清晰。

---

## 12.3 `volatile` 是否保证中断和任务之间的数据一致性？

不保证。

`volatile` 只保证编译器：

- 不删除访问
- 不把访问完全缓存到寄存器
- 按要求生成读写指令

它不保证：

- 读改写原子性
- 多字数据一致性
- CPU 顺序
- DMA 一致性
- 结构体整体更新原子性

对于单生产者单消费者环形缓冲区，需要同时设计：

- head/tail 所有权
- 索引宽度
- 内存屏障
- 缓冲区满/空判定
- 中断和任务并发关系

---

## 12.4 什么时候用 BASEPRI，什么时候用 PRIMASK？

### 使用 BASEPRI

适合：

- RTOS 临界区
- 需要保留最高优先级紧急中断
- 驱动层保护共享数据

### 使用 PRIMASK

适合：

- 极短、绝对不可打断的关键原子操作
- 启动阶段
- 极低层异常恢复
- 没有优先级位或需要屏蔽全部可屏蔽中断的场景

原则：

> **默认优先使用 BASEPRI，避免无条件关闭所有中断。**

---

## 12.5 M4 带 FPU 后一定比 M3 快吗？

不一定。

如果算法主要是：

- GPIO
- UART
- SPI
- 状态机
- 位操作
- 简单整数计算

M4 的 FPU 没有明显收益。

M4 的优势主要出现在：

- 大量乘加
- 定点 DSP
- 单精度浮点
- 音频、滤波、控制算法
- 高频数据处理

如果任务主要受 Flash、外设和通信限制，换 M4 可能无法带来线性收益。

---

## 12.6 M33 的 TrustZone 是否等同于完整安全系统？

不等同。

TrustZone 只提供硬件安全状态隔离能力，完整安全系统还需要：

- Secure Boot
- 密钥生命周期管理
- 安全调试
- 安全升级
- 固件完整性保护
- 随机数质量保证
- 访问控制
- 故障注入防护
- Secure API 审计
- 密钥擦除策略
- 生产烧录和证书管理

如果 Secure API 设计错误，TrustZone 仍可能被错误接口绕过。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **M3 = ARMv7-M，M4 = ARMv7E-M，M33 = ARMv8-M Mainline。**
2. M4 的主要价值是 **DSP 和可选 FPU**。
3. M33 的主要价值是 **TrustZone、安全状态和更现代的安全架构**。
4. Cortex-M 的实时性依赖：
    - NVIC
    - 硬件异常入栈
    - 尾链
    - 迟到中断
    - 合理优先级设计
5. RTOS 的核心异常分工：
    - SysTick：时间基准
    - PendSV：上下文切换
    - SVC：系统调用
6. 异常栈帧是 HardFault 诊断和 RTOS 切换的基础。
7. `volatile` 不等于原子性，也不等于内存屏障。
8. `DMB/DSB/ISB` 必须根据同步语义正确使用。
9. FPU 会带来额外上下文和栈空间成本。
10. MPU 与 TrustZone 是系统级隔离机制，不是简单的寄存器配置。
11. 所有性能结论必须在目标芯片上使用 DWT、GPIO 和示波器复测。
12. Cortex-M 架构能力必须以具体芯片实现为准。

## 13.2 典型性能排序

### DSP/定点运算

```
M4 ≈ M33 > M3
```

### 安全隔离

```
M33 >> M4 ≈ M3
```

### 基础控制性价比

```
M3 ≥ M4 > M33
```

### 复杂 RTOS 与协议处理能力

```
M33 ≥ M4 > M3
```

### 浮点能力

```
带 FPU 的 M4/M33 >> M3
```

---

# 14. 快速参考速查表

## 14.1 场景选型表

|需求|首选|
|---|---|
|低成本基础控制|M3|
|高频定点 DSP|M4|
|单精度控制算法|带 FPU 的 M4|
|安全启动|M33|
|Secure/Non-secure 隔离|M33|
|多任务 RTOS|M4/M33|
|低功耗传感器|M3/M33|
|高安全 IoT|M33|
|高性能音频|M4/M33|
|复杂协议栈|M4/M33|

---

## 14.2 关键异常号

|异常|异常号|说明|
|---|---|---|
|Reset|1|复位|
|NMI|2|不可屏蔽中断|
|HardFault|3|硬错误|
|MemManage|4|MPU 访问错误|
|BusFault|5|总线错误|
|UsageFault|6|指令或执行错误|
|SVCall|11|SVC 系统调用|
|DebugMonitor|12|调试监控|
|PendSV|14|可挂起系统服务|
|SysTick|15|系统节拍|

M33 还涉及：

- SecureFault
- Secure/Non-secure 状态相关异常行为

---

## 14.3 关键控制寄存器

|寄存器|用途|
|---|---|
|`CONTROL`|特权级、线程模式栈选择|
|`PRIMASK`|全局中断屏蔽|
|`BASEPRI`|按优先级阈值屏蔽|
|`FAULTMASK`|故障屏蔽|
|`MSP`|主栈|
|`PSP`|进程栈|
|`xPSR`|程序状态|
|`VTOR`|向量表地址|
|`SHCSR`|系统 Handler 控制|
|`CFSR`|可配置故障状态|
|`HFSR`|HardFault 状态|
|`MMFAR`|MemManage 错误地址|
|`BFAR`|BusFault 错误地址|
|`ICSR`|中断控制和状态|
|`AIRCR`|系统复位、优先级分组|
|`CCR`|配置控制|
|`CPACR`|FPU 协处理器访问权限|

---

## 14.4 屏障指令速查

|指令|核心语义|常见场景|
|---|---|---|
|`DMB`|保证访问顺序|共享数据、外设顺序|
|`DSB`|等待访问完成|低功耗、系统控制|
|`ISB`|刷新取指流水线|CONTROL、MPU、VTOR|

---

# 15. 学习效果自检

## 15.1 架构理解

- [ ]  能说明 M3、M4、M33 的架构版本。
- [ ]  能解释 ARMv7-M、ARMv7E-M、ARMv8-M 的差异。
- [ ]  能判断某型号是否真的带 FPU、MPU 和 TrustZone。
- [ ]  能解释 Thumb-2 的 16/32 位指令特点。

## 15.2 异常与中断

- [ ]  能画出 Cortex-M 异常入栈结构。
- [ ]  能根据 EXC_RETURN 判断返回 MSP 还是 PSP。
- [ ]  能解释尾链和迟到中断。
- [ ]  能正确配置 NVIC 优先级。
- [ ]  能区分 PRIMASK、BASEPRI、FAULTMASK。
- [ ]  能说明 SysTick、PendSV、SVC 的职责。

## 15.3 故障诊断

- [ ]  能从 HardFault 中获取 PC、LR、xPSR。
- [ ]  能读取 CFSR、HFSR、MMFAR、BFAR。
- [ ]  能判断是否发生栈溢出。
- [ ]  能识别非法访问、未对齐访问和非法指令执行。
- [ ]  能设计复位后故障记录恢复机制。

## 15.4 性能分析

- [ ]  能使用 DWT 测量函数周期数。
- [ ]  能计算 ISR 的 WCET。
- [ ]  能估算异常嵌套下的栈消耗。
- [ ]  能量化 M3 与 M4 DSP 实现差异。
- [ ]  能分析 FPU lazy stacking 的成本。

## 15.5 安全设计

- [ ]  能说明 Secure 和 Non-secure 状态。
- [ ]  能配置基本 SAU/MPU 分区。
- [ ]  能设计 Secure Gateway API。
- [ ]  能校验 Non-secure 指针和长度。
- [ ]  能说明 TrustZone 不等于完整安全系统。

---

# 16. 实践与进阶路径

## 16.1 第一阶段：异常和寄存器实验

### 任务

1. 修改向量表地址。
2. 触发除零异常。
3. 触发未对齐访问。
4. 触发非法指令。
5. 在 HardFault 中解析栈帧。
6. 将故障 PC、LR、CFSR 写入保留 SRAM。

### 验收指标

- 能准确定位故障指令地址。
- 能区分 UsageFault、BusFault 和 HardFault。
- 能在复位后输出上次故障信息。

---

## 16.2 第二阶段：NVIC 实时性实验

### 任务

- 配置三个不同优先级中断。
- 测试中断嵌套。
- 测试 `BASEPRI` 屏蔽效果。
- 测试尾链。
- 用 GPIO 和 DWT 统计：
    - 中断入口延迟
    - ISR 执行时间
    - ISR 抖动
    - 最大嵌套深度

### 建议输出数据

```
最小延迟
平均延迟
最大延迟
P99 延迟
P99.9 延迟
最大 ISR 执行周期
最大堆栈深度
```

---

## 16.3 第三阶段：M3/M4 算法对比

### 任务

在 M3 和 M4 上实现并对比：

- 32 点 FIR
- 64 点点积
- Q15 PI 控制器
- 单精度浮点 PI 控制器
- 饱和加法
- 绝对值和最大值搜索

### 测试方法

- 使用相同编译器版本。
- 使用相同优化级别。
- 保证数据位于相同类型存储区域。
- 分别测量：
    - 代码大小
    - RAM 使用
    - 平均周期
    - 最大周期
    - 能耗
- 对比标量实现和 DSP intrinsic 实现。

---

## 16.4 第四阶段：MPU 任务隔离

### 任务

设计三个任务：

```
Task A：只能访问自己的栈和数据区
Task B：只能读共享配置区
Task C：允许访问指定外设
```

测试：

- 任务 A 访问任务 B 数据。
- 任务 B 执行 SRAM 中的代码。
- 任务 C 访问未授权外设。
- 访问栈保护区。
- 触发 MemManage Fault 并记录错误地址。

### 验收指标

- 非法访问能够被拦截。
- Fault Handler 能准确输出违规地址。
- 合法共享缓冲区不影响性能和实时性。

---

## 16.5 第五阶段：M33 TrustZone 安全服务

### 任务

设计一个 Secure 服务：

```
Non-secure：
    请求随机数
    请求签名
    请求密钥派生

Secure：
    验证输入
    执行加密操作
    返回结果
```

必须包含：

- Secure Gateway
- Non-secure 指针验证
- 输入长度检查
- 错误码设计
- Secure 日志
- 访问频率限制
- 密钥不可导出策略

---

## 16.6 第六阶段：工业级综合项目

推荐实现一个小型控制平台：

```
Cortex-M4/M33
├── 启动和向量表重定位
├── HardFault 故障记录
├── SysTick 时间基准
├── PendSV 任务切换
├── MPU 任务隔离
├── DMA 环形缓冲区
├── 高优先级控制 ISR
├── 通信协议栈
├── DWT 性能监控
├── 看门狗恢复
└── M33 可选 TrustZone 服务
```

最终应形成以下工程文档：

- CPU 和芯片能力矩阵
- 中断优先级表
- 任务栈预算表
- 异常处理流程
- WCET 测试报告
- MPU/TrustZone 安全边界图
- 复位和故障恢复策略
- 代码审查清单
- 静态分析和覆盖率报告

---

## 16.7 进阶学习方向

### 架构方向

- ARMv8-M Security Extension
- TrustZone-M 异常模型
- MPU 区域优先级和重叠规则
- 原子操作和独占访问语义
- CMSIS-Core 实现细节

### RTOS 方向

- PendSV 汇编上下文切换
- FPU 任务上下文管理
- MPU-RTOS
- TrustZone-RTOS
- 中断优先级与系统调用边界

### 性能方向

- DWT/ITM/SWO 跟踪
- ETM 指令跟踪
- WCET 分析
- Flash 加速器和总线矩阵分析
- ISR 抖动和 P99.9 延迟分析

### 安全方向

- Secure Boot
- 固件签名和反回滚
- 密钥生命周期
- 安全调试
- PSA Certified 架构
- 安全故障注入和边界测试

### 实战总目标

最终应能够回答并验证以下问题：

> 当一个 Cortex-M 系统出现偶发 HardFault、中断延迟抖动、任务栈溢出、FPU 路径异常或 Non-secure 越权访问时，能否从架构、寄存器、汇编、内存系统、RTOS 和安全边界多个层面快速定位根因，并给出可量化、可验证、可维护的工程解决方案？