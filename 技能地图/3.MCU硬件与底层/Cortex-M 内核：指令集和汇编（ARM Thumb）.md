
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 Cortex-M 的异常模型、特权级、堆栈模型和寄存器组织。
- 理解 ARM 状态、Thumb 状态、Thumb-2 指令集之间的关系。
- 理解流水线、条件执行、访存对齐、内存屏障和异常进入/退出机制。
- 理解 C 代码如何映射为汇编、函数调用如何遵循 AAPCS 调用约定。
- 理解 `MSP`、`PSP`、`CONTROL`、`xPSR`、`PRIMASK`、`BASEPRI`、`FAULTMASK` 的工程用途。

### 掌握

- 掌握 Cortex-M 常用寄存器和异常向量表布局。
- 掌握 Thumb 汇编基本语法、寻址方式和条件分支。
- 掌握 `LDR/STR`、`PUSH/POP`、`BL/BX`、`MRS/MSR`、`DMB/DSB/ISB` 等关键指令。
- 掌握 C 与汇编混合编程、裸函数、启动代码和上下文切换框架。
- 掌握 HardFault、MemManage、BusFault、UsageFault 的基本定位方法。

### 精通

- 能分析编译器生成的 Cortex-M 汇编，并识别性能瓶颈。
- 能推导异常现场栈帧、返回码 `EXC_RETURN` 和任务切换上下文。
- 能处理未对齐访问、弱内存序、流水线同步、临界区嵌套等底层问题。
- 能根据实时性、代码尺寸、功耗和安全需求选择指令和架构实现。
- 能使用反汇编、map 文件、DWT、ETM/ITM、Fault 状态寄存器定位现场问题。

### 能够设计

- 设计 Cortex-M 启动文件、异常向量表和异常诊断框架。
- 设计 RTOS 上下文切换、用户态/特权态隔离和安全启动边界。
- 设计高性能寄存器访问、DMA 缓冲区、无锁环形队列和内存屏障策略。
- 设计适用于量产产品的 HardFault 收集、回滚和远程诊断机制。

---

## 2. 前置要求

### 知识要求

1. 熟悉 C 语言：
    - 指针、数组、结构体、函数指针。
    - `volatile`、`const`、`static`、链接属性。
    - 位运算、内存布局、栈和堆。
2. 熟悉 MCU 基本硬件：
    - 地址空间、寄存器、总线、DMA、中断。
    - Flash、SRAM、外设寄存器。
3. 了解 RTOS 基础：
    - 任务、栈、上下文切换、临界区。
4. 了解编译、链接和启动流程：
    - 编译器、汇编器、链接器、启动文件、链接脚本。
5. 熟悉十六进制、二进制和补码表示。

### 技能要求

- 能使用 `arm-none-eabi-gcc` 或 ARM Compiler 工具链。
- 能查看 `.elf`、`.map`、`.lst`、反汇编文件。
- 能使用 GDB、OpenOCD、J-Link 或厂商 IDE 调试。
- 能读取和修改启动文件、链接脚本及异常处理代码。
- 能使用逻辑分析仪、示波器或 DWT 周期计数器完成性能测量。

---

## 3. 技术概述

## 3.1 Cortex-M 的定位

Cortex-M 是 ARM 面向微控制器和实时嵌入式系统设计的处理器内核系列，核心特点是：

- **低中断延迟**。
- **统一的异常模型**。
- **硬件自动保存部分上下文**。
- **Thumb/Thumb-2 高代码密度指令集**。
- **可选 MPU、FPU、DSP、TrustZone-M、Cache 等扩展**。
- **与 CMSIS、RTOS 和主流 MCU 生态高度兼容**。

常见内核：

|内核|典型能力|典型应用|
|---|---|---|
|Cortex-M0/M0+|ARMv6-M，基础 Thumb|低成本、低功耗控制|
|Cortex-M3|ARMv7-M，Thumb-2，DSP 基础|通用工业控制|
|Cortex-M4|ARMv7E-M，DSP，单精度 FPU 可选|电机控制、音频、传感器|
|Cortex-M7|高性能流水线、Cache、TCM、FPU|高性能控制、图形、边缘处理|
|Cortex-M23|ARMv8-M Baseline，TrustZone-M 可选|安全低功耗设备|
|Cortex-M33|ARMv8-M Mainline，DSP/FPU/TrustZone-M|安全 IoT、工业控制|
|Cortex-M55|Helium/MVE，可选 AI 加速|边缘 AI、信号处理|
|Cortex-M85|更高性能、Helium|高端边缘计算|

---

## 3.2 ARM、Thumb 和 Thumb-2 的关系

历史上 ARM 架构存在两种主要指令状态：

- **ARM 状态**：大多数指令为 32 位。
- **Thumb 状态**：早期主要为 16 位指令。
- **Thumb-2**：混合使用 16 位和 32 位 Thumb 指令。

关键结论：

> **Cortex-M 系列只执行 Thumb 指令集，不支持传统 ARM 状态。**

因此：

- Cortex-M 的 `xPSR.T` 位必须保持为 1。
- 函数地址最低位通常置 1，用于表示 Thumb 状态。
- 通过 `BX` 或异常返回切换时，目标地址最低位必须符合 Thumb 状态要求。
- 在 Cortex-M 上不能像 Cortex-A 那样通过切换 CPSR 进入传统 ARM 状态。

例如：

```
typedef void (*entry_fn_t)(void);

void jump_to_image(uint32_t image_base)
{
    uint32_t reset_handler = *(volatile uint32_t *)(image_base + 4U);

    /*
     * Cortex-M 函数地址最低位必须为 1，
     * 表示 Thumb 状态。
     */
    reset_handler |= 1U;

    ((entry_fn_t)reset_handler)();
}
```

---

## 3.3 技术分支分类

### 按指令编码分类

|类型|长度|特点|
|---|---|---|
|Thumb-1|16 位|代码密度高，寄存器和寻址能力有限|
|Thumb-2|16/32 位混合|兼顾代码密度和表达能力|
|ARM 指令|32 位|Cortex-M 不支持|

### 按内核执行能力分类

|能力|相关寄存器/机制|典型用途|
|---|---|---|
|基础整数运算|`ADD/SUB/MUL`|控制逻辑|
|位操作|`BIC/ORR/EOR/LSL/ROR`|寄存器和协议字段|
|条件执行|`IT`、条件分支|减少分支|
|原子访问|`LDREX/STREX`、位带|无锁同步|
|DSP|`SMLAD`, `SSAT`, `QADD`|FIR、电机控制|
|浮点|`VMOV`, `VADD`, `VMUL`|控制算法、滤波|
|内存顺序|`DMB/DSB/ISB`|DMA、外设、异常控制|
|调试追踪|DWT、ITM、ETM|性能分析和故障诊断|

---

## 4. 核心特性横向对比

## 4.1 Cortex-M 内核能力对比

|维度|M0/M0+|M3|M4|M7|M33|
|---|---|---|---|---|---|
|架构|ARMv6-M|ARMv7-M|ARMv7E-M|ARMv7E-M|ARMv8-M Mainline|
|Thumb-2|部分/有限|支持|支持|支持|支持|
|DSP 指令|否|否|是|是|是|
|FPU|否|否|可选|可选|可选|
|MPU|通常无/简化|可选|可选|可选|支持|
|TrustZone-M|否|否|否|否|可选|
|Cache|通常无|无|无|常见|取决于实现|
|TCM|无|无|无|常见|取决于实现|
|典型主频|16–64 MHz|72–120 MHz|80–200 MHz|200–600 MHz|100–250 MHz|
|适合场景|低成本控制|通用 MCU|DSP/电机|高性能系统|安全 IoT|

## 4.2 常用实现方案对比

|方案|优点|缺点|适用场景|
|---|---|---|---|
|C 代码|可维护性高、移植性好|关键路径性能不完全可控|普通业务逻辑|
|CMSIS 内联函数|可读性和可控性平衡|依赖 CMSIS|特殊寄存器、屏障|
|内联汇编|可嵌入 C、接口方便|编译器约束复杂|原子操作、特殊指令|
|独立汇编文件|完全控制寄存器和栈|可维护性较低|启动文件、上下文切换|
|编译器内置函数|优化好、语义清晰|编译器相关|DSP、位操作、屏障|
|位带|语义直观|并非所有内核支持，地址映射成本|小型状态位|
|LDREX/STREX|通用、适合多核/中断并发|编程复杂，可能重试|原子计数器、锁|

## 4.3 特权和堆栈机制对比

|模式|堆栈|特权级|典型用途|
|---|---|---|---|
|Handler 模式|通常 MSP|特权|异常、ISR、系统服务|
|Thread 模式|MSP 或 PSP|特权/非特权|主程序或 RTOS 任务|
|Thread + MSP|MSP|特权|裸机主循环|
|Thread + PSP|PSP|可特权或非特权|RTOS 任务、用户态任务|
|非特权 Thread|PSP/MSP|非特权|安全隔离、应用代码|

---

# 5. 底层原理与功能特性深度解析

## 5.1 Cortex-M 通用寄存器组织

Cortex-M 基本寄存器：

|寄存器|用途|
|---|---|
|`R0-R12`|通用寄存器|
|`R13/SP`|栈指针|
|`R14/LR`|链接寄存器|
|`R15/PC`|程序计数器|
|`xPSR`|程序状态寄存器|
|`MSP`|主堆栈指针|
|`PSP`|进程堆栈指针|
|`CONTROL`|当前堆栈和特权控制|
|`PRIMASK`|全局可屏蔽中断控制|
|`BASEPRI`|按优先级屏蔽中断|
|`FAULTMASK`|屏蔽除 NMI 外的异常|

### 关键寄存器读取

```
#include <stdint.h>

static inline uint32_t read_msp(void)
{
    uint32_t value;

    __asm volatile (
        "mrs %0, msp"
        : "=r"(value)
        :
        : "memory"
    );

    return value;
}

static inline uint32_t read_psp(void)
{
    uint32_t value;

    __asm volatile (
        "mrs %0, psp"
        :
        : 
        : "memory"
    );

    return value;
}
```

更推荐使用 CMSIS：

```
uint32_t msp = __get_MSP();
uint32_t psp = __get_PSP();
uint32_t control = __get_CONTROL();
uint32_t xpsr = __get_xPSR();
```

---

## 5.2 启动流程和向量表

复位后，Cortex-M 硬件执行：

1. 从地址 `VTOR + 0x00` 读取初始 MSP。
2. 从地址 `VTOR + 0x04` 读取复位处理函数地址。
3. 将 PC 设置为复位处理函数。
4. 开始执行启动代码。

典型向量表：

```
typedef void (*isr_handler_t)(void);

extern unsigned long _estack;
void Reset_Handler(void);
void Default_Handler(void);

__attribute__((section(".isr_vector")))
const isr_handler_t vector_table[] = {
    (isr_handler_t)&_estack,
    Reset_Handler,
    Default_Handler,        /* NMI */
    HardFault_Handler,
    MemManage_Handler,
    BusFault_Handler,
    UsageFault_Handler,
};
```

在实际工程中，向量表通常还要满足：

- 按内核要求对齐。
- 位于可执行内存或系统要求的存储区域。
- Bootloader 跳转时重新设置 `VTOR`。
- 启用中断前完成向量表和外设状态初始化。

```
#define SCB_VTOR (*(volatile uint32_t *)0xE000ED08UL)

void relocate_vector_table(uint32_t vector_base)
{
    /*
     * 对齐要求必须符合具体内核和向量表大小。
     * 这里不应盲目使用固定掩码。
     */
    SCB_VTOR = vector_base;
    __asm volatile ("dsb" ::: "memory");
    __asm volatile ("isb" ::: "memory");
}
```

---

## 5.3 Thumb 指令编码与程序计数器

Cortex-M 使用 Thumb 指令：

- 常见指令长度为 **16 位或 32 位**。
- PC 读取值通常具有架构相关的预取偏移。
- `PC` 作为操作数时，低位通常被忽略或按对齐规则处理。
- 分支目标地址最低位用于表示 Thumb 状态。

常见问题：

```
void (*fn)(void) = (void *)0x08010100U;  /* 错误风险 */
fn();
```

如果该地址实际代表 Thumb 函数入口，应写成：

```
void (*fn)(void) = (void *)(0x08010100U | 1U);
fn();
```

但需要注意：

> **函数地址低位为 1 只是状态标识，不代表实际取指地址从奇数地址开始。**

---

## 5.4 数据处理指令

### 加减法

```
adds    r0, r0, r1      ; r0 = r0 + r1，并更新 APSR 标志
adds    r0, #1
subs    r0, r1, r2
```

C 对应：

```
uint32_t add_u32(uint32_t a, uint32_t b)
{
    return a + b;
}
```

典型生成结果可能是：

```
add     r0, r0, r1
bx      lr
```

### 位操作

```
orrs    r0, r1          ; r0 |= r1
ands    r0, r1          ; r0 &= r1
eors    r0, r1          ; r0 ^= r1
bics    r0, r1          ; r0 &= ~r1
mvns    r0, r0          ; r0 = ~r0
```

寄存器字段修改：

```
static inline void reg_set_bits(volatile uint32_t *reg,
                                 uint32_t mask)
{
    *reg |= mask;
}

static inline void reg_clear_bits(volatile uint32_t *reg,
                                   uint32_t mask)
{
    *reg &= ~mask;
}
```

注意：对于中断或多线程并发访问的寄存器，上述读改写不是原子的，可能需要：

- 外设提供 `SET/CLR` 寄存器。
- 关闭中断。
- 使用原子指令。
- 使用临界区或锁。

---

## 5.5 移位和旋转

常用指令：

```
lsls    r0, r1, #3      ; r0 = r1 << 3
lsrs    r0, r1, #4
asrs    r0, r1, #4      ; 算术右移
rors    r0, r1          ; 循环右移，部分内核支持形式不同
```

编译器内置函数：

```
static inline uint32_t ror32(uint32_t value, unsigned int shift)
{
    shift &= 31U;

    if (shift == 0U) {
        return value;
    }

    return (value >> shift) | (value << (32U - shift));
}
```

如果目标内核和编译器支持，通常可以使用：

```
uint32_t result = __ROR(value, shift);
```

工程注意：

- 移位量等于或大于类型宽度时，C 语言行为存在风险。
- 必须显式约束移位量。
- 对协议 CRC、哈希、加密算法应验证编译器生成指令。

---

## 5.6 条件执行和分支

Cortex-M 的条件判断通常依赖 APSR 标志：

- `N`：负数标志。
- `Z`：零标志。
- `C`：进位/无借位标志。
- `V`：有符号溢出标志。

常用条件：

|后缀|含义|
|---|---|
|`EQ`|`Z == 1`|
|`NE`|`Z == 0`|
|`CS/HS`|`C == 1`|
|`CC/LO`|`C == 0`|
|`MI`|`N == 1`|
|`PL`|`N == 0`|
|`VS`|`V == 1`|
|`VC`|`V == 0`|
|`GT`|有符号大于|
|`LT`|有符号小于|
|`GE`|有符号大于等于|
|`LE`|有符号小于等于|

汇编示例：

```
cmp     r0, #0
beq     value_is_zero

movs    r1, #1
bx      lr

value_is_zero:
movs    r1, #0
bx      lr
```

Thumb-2 可使用条件执行块，但现代编译器通常谨慎使用 `IT`：

```
cmp     r0, #0
ite     eq
moveq   r1, #1
movne   r1, #0
```

工程建议：

- 短小无副作用逻辑可用条件执行。
- 分支概率明显不均衡时，应将常见路径放在顺序路径上。
- 对 Cortex-M7 等带预测机制的实现，应结合实际测量，不要凭经验判断。

---

## 5.7 加载和存储指令

基本指令：

```
ldr     r0, [r1]           ; 32 位加载
str     r0, [r1]           ; 32 位存储
ldrb    r0, [r1]           ; 8 位加载
strb    r0, [r1]           ; 8 位存储
ldrh    r0, [r1]           ; 16 位加载
strh    r0, [r1]           ; 16 位存储
```

带偏移：

```
ldr     r0, [r1, #4]
str     r0, [r1, #8]
ldr     r0, [r1, r2]
```

前后变址：

```
ldr     r0, [r1, #4]!
ldr     r0, [r1], #4
```

多寄存器访问：

```
ldmia   r0!, {r4-r7}
stmia   r0!, {r4-r7}
push    {r4-r7, lr}
pop     {r4-r7, pc}
```

### 结构体映射

```
typedef struct {
    volatile uint32_t CTRL;
    volatile uint32_t STATUS;
    volatile uint32_t DATA;
} device_regs_t;

#define DEVICE ((device_regs_t *)0x40010000UL)

void device_enable(void)
{
    DEVICE->CTRL |= (1UL << 0);
}
```

编译器可能生成：

```
ldr     r1, [pc, #offset]  ; 获取 DEVICE 地址
ldr     r2, [r1, #0]       ; 读取 CTRL
orrs    r2, r2, #1
str     r2, [r1, #0]
bx      lr
```

---

## 5.8 `volatile` 的真实边界

`volatile` 保证：

- 编译器不会删除对该对象的访问。
- 编译器不会随意合并或缓存访问。
- 每次抽象机要求的访问都应产生实际内存访问。

`volatile` 不保证：

- 原子性。
- 多核内存一致性。
- 中断和主线程之间的复合操作安全。
- DMA 与 CPU 之间的 Cache 一致性。
- 访问顺序满足外设或总线要求。

错误示例：

```
volatile uint32_t counter;

void increment(void)
{
    counter++;  /* 不是原子操作，实际是 load + add + store */
}
```

可能被中断打断：

```
主线程读取 counter = 10
中断读取 counter = 10
主线程写回 11
中断写回 11
结果丢失一次累加
```

正确方案之一：

```
uint32_t increment_atomic(volatile uint32_t *value)
{
    uint32_t old_value;
    uint32_t new_value;
    uint32_t status;

    do {
        __asm volatile ("ldrex %0, [%3]"
                       : "=&r"(old_value)
                       : "0"(old_value), "r"(value), "r"(value)
                       : "memory");

        new_value = old_value + 1U;

        __asm volatile ("strex %0, %2, [%1]"
                       : "=&r"(status)
                       : "r"(value), "r"(new_value)
                       : "memory");
    } while (status != 0U);

    __asm volatile ("clrex" ::: "memory");
    return new_value;
}
```

实际生产代码应优先使用 CMSIS 原子封装或经过验证的架构库。

---

## 5.9 栈、调用约定和函数现场

Cortex-M 通常遵循 AAPCS：

- `R0-R3`：参数和返回值，调用者保存。
- `R4-R11`：被调用者保存。
- `R12`：临时寄存器。
- `R13`：SP。
- `R14`：LR。
- `R15`：PC。
- 栈通常 **8 字节对齐**。

函数示例：

```
uint32_t sum4(uint32_t a,
              uint32_t b,
              uint32_t c,
              uint32_t d)
{
    return a + b + c + d;
}
```

可能生成：

```
sum4:
    add     r0, r0, r1
    add     r0, r0, r2
    add     r0, r0, r3
    bx      lr
```

带局部变量时：

```
push    {r4, lr}
sub     sp, #16
...
add     sp, #16
pop     {r4, pc}
```

### 裸函数注意事项

```
__attribute__((naked))
void naked_handler(void)
{
    __asm volatile (
        "mrs r0, psp\n"
        "b   naked_handler_body\n"
    );
}
```

裸函数中：

- 编译器不会生成标准函数序言和尾声。
- 不能直接写普通 C 代码。
- 必须手工保证栈对齐和寄存器保存。
- 不应让编译器自动分配局部变量。
- 适用于上下文切换、异常入口等少数场景。

---

## 5.10 异常进入和自动压栈

异常进入时，硬件通常自动压入：

```
低地址
R0
R1
R2
R3
R12
LR
PC
xPSR
高地址
```

在 Cortex-M4F/M7F 等带 FPU 的系统中，可能还涉及扩展浮点上下文：

```
S0-S15
FPSCR
保留字
```

是否保存 FPU 上下文通常受：

- `FPCCR.LSPEN`
- `FPCCR.ASPEN`
- 当前任务是否执行过浮点指令

影响。

异常现场结构：

```
typedef struct {
    uint32_t r0;
    uint32_t r1;
    uint32_t r2;
    uint32_t r3;
    uint32_t r12;
    uint32_t lr;
    uint32_t pc;
    uint32_t xpsr;
} exception_stack_frame_t;
```

---

## 5.11 HardFault 现场捕获

典型实现：

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
} fault_frame_t;

volatile fault_frame_t g_fault_frame;
volatile uint32_t g_fault_lr;
volatile uint32_t g_hfsr;
volatile uint32_t g_cfsr;
volatile uint32_t g_hardfault_status;

__attribute__((naked))
void HardFault_Handler(void)
{
    __asm volatile (
        "tst lr, #4                 \n"
        "ite eq                      \n"
        "mrseq r0, msp               \n"
        "mrsne r0, psp               \n"
        "mov r1, lr                  \n"
        "b hardfault_capture         \n"
    );
}

void hardfault_capture(fault_frame_t *frame,
                       uint32_t exc_return)
{
    g_fault_frame = *frame;
    g_fault_lr = exc_return;

    /*
     * 具体地址应使用 CMSIS 的 SCB 寄存器定义。
     */
    g_hfsr = SCB->HFSR;
    g_cfsr = SCB->CFSR;
    g_hardfault_status = SCB->HFSR;

    /*
     * 生产系统中应：
     * 1. 写入保留 RAM 或 Flash；
     * 2. 添加 CRC；
     * 3. 记录启动计数和软件版本；
     * 4. 复位或进入安全降级状态。
     */
    NVIC_SystemReset();
}
```

需要重点检查：

- `frame->pc`：故障指令地址。
- `frame->lr`：调用者返回地址。
- `g_fault_lr`：`EXC_RETURN`，判断使用 MSP 还是 PSP。
- `SCB->CFSR`：具体故障类型。
- `SCB->HFSR`：是否由其他 Fault 升级。
- `SCB->BFAR/MMFAR`：故障访问地址。

---

## 5.12 `EXC_RETURN` 机制

异常处理函数中的 `LR` 并不是普通函数返回地址，而是特殊编码：

常见含义：

|位|含义|
|---|---|
|Bit 31:28|通常为 `0xF`|
|Bit 4|是否包含浮点扩展栈帧|
|Bit 3|返回 Handler 还是 Thread|
|Bit 2|返回时使用 MSP 还是 PSP|

常见值：

- `0xFFFFFFF1`：返回 Handler，使用 MSP。
- `0xFFFFFFF9`：返回 Thread，使用 MSP。
- `0xFFFFFFFD`：返回 Thread，使用 PSP。

RTOS PendSV 上下文切换经常利用这一机制：

```
mrs     r0, psp
stmdb   r0!, {r4-r11}
str     r0, [r2]

ldr     r1, [r3]
ldr     r0, [r1]
ldmia   r0!, {r4-r11}
msr     psp, r0

bx      lr
```

---

## 5.13 MSP 与 PSP

推荐架构：

```
异常/ISR             -> MSP
RTOS 任务            -> PSP
系统启动和内核       -> MSP
用户应用             -> PSP + 非特权
```

切换到 PSP：

```
void switch_to_psp(uint32_t psp)
{
    __set_PSP(psp);

    /*
     * CONTROL.SPSEL = 1：Thread 模式使用 PSP。
     */
    __set_CONTROL(__get_CONTROL() | (1U << 1));

    /*
     * 确保 CONTROL 更新立即生效。
     */
    __ISB();
}
```

注意：

- Handler 模式始终使用 MSP。
- 不能在 Handler 模式中通过 `CONTROL.SPSEL` 选择 PSP。
- PSP 必须满足对齐要求。
- 任务栈边界必须配置栈溢出检测。

---

## 5.14 中断屏蔽寄存器

### PRIMASK

```
uint32_t primask = __get_PRIMASK();
__disable_irq();

/* 临界区 */

__set_PRIMASK(primask);
```

特点：

- 屏蔽所有可屏蔽异常。
- 不屏蔽 NMI 和 HardFault。
- 适合极短、强一致性临界区。
- 会影响系统实时性。

### BASEPRI

```
uint32_t old_basepri = __get_BASEPRI();
__set_BASEPRI(irq_priority_threshold);

/* 只屏蔽低优先级中断 */

__set_BASEPRI(old_basepri);
```

特点：

- 只屏蔽优先级数值大于等于阈值的中断。
- 适合 RTOS 临界区。
- 优先级编码必须注意“数值越小优先级越高”的规则。
- 不适用于 Cortex-M0 的全部场景，因为 M0 对 BASEPRI 支持有限或不支持。

### FAULTMASK

```
uint32_t old_faultmask = __get_FAULTMASK();
__set_FAULTMASK(1U);

/* 极特殊的故障恢复代码 */

__set_FAULTMASK(old_faultmask);
```

通常不建议业务代码使用。

---

## 5.15 内存屏障：DMB、DSB、ISB

### DMB：Data Memory Barrier

保证屏障前的内存访问在屏障后的内存访问之前完成观察。

典型用途：

```
shared_data = 123U;
__DMB();
event_flag = 1U;
```

另一侧：

```
while (event_flag == 0U) {
    /* wait */
}

__DMB();
uint32_t value = shared_data;
```

### DSB：Data Synchronization Barrier

保证前面的显式内存访问完成后，处理器才继续执行。

典型用途：

```
SCB->VTOR = vector_base;
__DSB();
__ISB();
```

### ISB：Instruction Synchronization Barrier

刷新指令流水线，使后续指令使用最新的系统状态。

典型场景：

- 修改 `CONTROL`。
- 修改 MPU 配置。
- 修改向量表。
- 修改缓存或系统控制寄存器。

```
__set_CONTROL(control);
__ISB();
```

关键结论：

> `volatile` 解决编译器优化问题；`DMB/DSB/ISB` 解决处理器执行和内存顺序问题；二者不是替代关系。

---

## 5.16 访存对齐与未对齐

Cortex-M 对未对齐访问的支持取决于：

- 指令类型。
- 内核实现。
- `CCR.UNALIGN_TRP` 配置。
- 总线和外设限制。

错误示例：

```
uint32_t parse_u32(const uint8_t *buf)
{
    return *(const uint32_t *)buf;
}
```

风险：

- `buf` 未对齐时产生 UsageFault。
- 某些情况下硬件自动拆分访问，性能下降。
- 严格别名和 C 语言未定义行为风险。
- 外设寄存器通常不允许这种访问方式。

正确实现：

```
#include <stdint.h>
#include <string.h>

uint32_t parse_u32_le(const uint8_t *buf)
{
    uint32_t value;

    memcpy(&value, buf, sizeof(value));
    return value;
}
```

在明确小端环境下，也可显式拼接：

```
uint32_t parse_u32_le_explicit(const uint8_t *buf)
{
    return ((uint32_t)buf[0])       |
           ((uint32_t)buf[1] << 8U) |
           ((uint32_t)buf[2] << 16U) |
           ((uint32_t)buf[3] << 24U);
}
```

---

## 5.17 DSP 指令和饱和运算

Cortex-M4/M7/M33 等部分内核支持饱和运算：

```
#include <stdint.h>
#include "arm_math.h"

int32_t saturate_q31(int64_t value)
{
    if (value > INT32_MAX) {
        return INT32_MAX;
    }

    if (value < INT32_MIN) {
        return INT32_MIN;
    }

    return (int32_t)value;
}
```

使用 CMSIS-DSP：

```
arm_status status;
q31_t input[128];
q31_t output[128];
q31_t coeffs[32];

arm_fir_instance_q31_t fir;

status = arm_fir_init_q31(&fir,
                          32U,
                          coeffs,
                          output,
                          128U);

if (status == ARM_MATH_SUCCESS) {
    arm_fir_q31(&fir, input, output, 128U);
}
```

工程重点：

- Q 格式必须明确。
- 乘法结果位宽必须设计。
- 饱和策略影响控制稳定性。
- 不要仅因使用 DSP 指令就忽略内存带宽和 Cache 行为。

---

## 5.18 浮点上下文和 Lazy Stacking

带 FPU 的 Cortex-M 进入异常时，浮点上下文可能延迟保存。优点：

- 不使用 FPU 的 ISR 不需要保存全部浮点寄存器。
- 降低普通中断延迟。

风险：

- 某个 ISR 首次使用 FPU 时触发额外上下文保存。
- RTOS 任务使用 FPU 后，任务切换栈消耗明显增大。
- 浮点上下文大小会影响最坏情况栈深度。

工程建议：

- 对高实时性 ISR 禁止使用浮点。
- 将浮点算法放在任务上下文。
- 对所有任务执行栈水位检测。
- 测量“首次使用 FPU”的异常延迟，而不是只测稳态延迟。

---

# 6. 性能量化分析

以下数据以 **Cortex-M4F，168 MHz，Flash 访问带 3 个等待周期，SRAM 0 等待周期，Arm GCC 12，`-O2`** 为示例。不同芯片的 Flash 加速器、总线结构和编译器会显著影响结果，必须在目标平台实测。

## 6.1 指令级典型周期

|操作|典型周期|备注|
|---|---|---|
|`ADD` 寄存器运算|1|单周期执行条件|
|`MUL`|1–3|依内核实现|
|SRAM 单次 `LDR/STR`|1–2|不含等待|
|Flash 顺序取指|1–若干|受等待周期和预取影响|
|`PUSH/POP`|1 + 每字传输成本|总线访问决定|
|taken branch|约 2–3|流水线刷新|
|未对齐访问|2–若干|依硬件和总线|
|`DMB`|通常低成本|保证顺序，不一定等待外设完成|
|`DSB`|可明显变慢|必须等待显式访问完成|
|异常进入|约 12 周期起|受等待、FPU、总线影响|
|异常退出|约 10–12 周期起|受栈恢复影响|

## 6.2 时间换算

处理器周期：

Tcycle=1fCPUTcycle​=fCPU​1​

168 MHz 时：

Tcycle≈5.95nsTcycle​≈5.95ns

如果代码路径执行 120 个周期：

Tpath=120×5.95ns≈714nsTpath​=120×5.95ns≈714ns

如果需要 10 μs 周期控制回路，则最大周期预算为：

Nbudget=10μs×168MHz=1680 cyclesNbudget​=10μs×168MHz=1680 cycles

工程上不能将预算全部用于平均执行时间，应按最坏情况设计：

```
控制算法：900 cycles
传感器读取：250 cycles
异常裕量：200 cycles
Cache/Flash/中断扰动：200 cycles
总计：1550 cycles
剩余：130 cycles
```

---

## 6.3 代码尺寸对比

典型简单函数：

```
uint32_t get_status(void)
{
    return DEVICE->STATUS;
}
```

可能结果：

|实现|代码大小|
|---|---|
|Thumb-1 简单形式|4–8 字节|
|Thumb-2|6–10 字节|
|复杂地址常量加载|8–16 字节|
|额外边界检查和错误处理|20–60 字节|

代码尺寸受以下因素影响：

- 常量是否可通过 PC-relative 访问。
- 是否需要 `MOVW/MOVT`。
- 是否启用 LTO。
- 函数是否内联。
- 分支距离是否超出短跳范围。
- 是否使用 FPU 或 64 位操作。

---

## 6.4 栈开销

典型异常自动栈帧：

```
R0-R3       16 bytes
R12          4 bytes
LR           4 bytes
PC           4 bytes
xPSR         4 bytes
---------------------
基础帧      32 bytes
```

若扩展浮点栈帧被压入：

```
S0-S15      64 bytes
FPSCR        4 bytes
保留字       4 bytes
---------------------
额外        72 bytes
```

一个 RTOS 任务的典型上下文切换栈开销：

```
自动异常帧：32 bytes
软件保存 R4-R11：32 bytes
对齐/扩展：0–8 bytes
-----------------------
约 64–72 bytes
```

使用 FPU 时必须额外考虑：

```
浮点扩展帧约 72 bytes
```

因此 1 KB 任务栈并不等价于“可用 1 KB 业务局部变量”。需要减去：

- 异常帧。
- RTOS 保存寄存器。
- 嵌套中断。
- 编译器局部变量。
- 深层函数调用。
- 浮点上下文。
- 库函数临时栈。

---

## 6.5 分支和内存访问优化

### 优化前

```
uint32_t checksum(const uint8_t *data, size_t len)
{
    uint32_t sum = 0U;

    for (size_t i = 0U; i < len; ++i) {
        sum += data[i];
    }

    return sum;
}
```

### 优化方向

1. 确保数据位于高效存储区。
2. 对大块数据采用批量加载。
3. 使用 `restrict` 明确别名约束。
4. 使用 CMSIS-DSP 或编译器向量化能力。
5. 避免在最内层循环调用函数。
6. 通过 DWT 实测，而不是根据源码行数估算。

```
uint32_t checksum_u32(const uint32_t *restrict data,
                      size_t words)
{
    uint32_t sum = 0U;

    while (words >= 4U) {
        sum += data[0];
        sum += data[1];
        sum += data[2];
        sum += data[3];

        data += 4;
        words -= 4U;
    }

    while (words > 0U) {
        sum += *data++;
        --words;
    }

    return sum;
}
```

风险：

- 数据地址必须满足对齐要求。
- 字节序必须符合算法定义。
- 过度展开可能增加代码尺寸并降低 I-Cache 命中率。
- `restrict` 使用错误会引入未定义行为。

---

## 6.6 DWT 周期测量

部分 Cortex-M 支持 DWT `CYCCNT`：

```
static void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

uint32_t measure_cycles(void (*fn)(void))
{
    uint32_t start;
    uint32_t end;

    start = DWT->CYCCNT;
    fn();
    end = DWT->CYCCNT;

    return end - start;
}
```

测量要求：

- 关闭或记录中断干扰。
- 分别测冷 Cache、热 Cache。
- 测平均值、最大值和 99.9 分位值。
- 测量不同 Flash/SRAM/TCM 放置位置。
- 对 ISR 测量进入、正文、退出三个阶段。

---

# 7. 应用场景选型指南

## 7.1 决策流程图

```
需要直接访问特殊寄存器或异常机制？
├─ 是
│  ├─ CMSIS 已提供接口？
│  │  ├─ 是 -> 优先使用 CMSIS intrinsic
│  │  └─ 否 -> 使用最小化内联汇编，并封装成 C API
│  └─ 涉及启动/上下文切换？
│     ├─ 是 -> 独立汇编文件或 naked 汇编入口
│     └─ 否 -> 内联汇编
└─ 否
   ├─ 是否是性能关键循环？
   │  ├─ 否 -> 使用 C，并检查生成汇编
   │  └─ 是
   │     ├─ 是否支持 CMSIS-DSP/DSP 指令？
   │     │  ├─ 是 -> 优先使用 CMSIS-DSP/编译器 intrinsic
   │     │  └─ 否 -> C 优化后再考虑汇编
   │     └─ 是否存在并发访问？
   │        ├─ 是 -> 原子指令/临界区/硬件 SET-CLR
   │        └─ 否 -> 普通加载存储
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|读取 MSP/PSP|CMSIS intrinsic|可移植、编译器适配成熟|
|HardFault 取栈帧|naked 汇编入口 + C 解析|入口必须控制现场|
|RTOS PendSV 切换|独立汇编|精确管理寄存器和栈|
|外设寄存器访问|`volatile` C 结构体|可读性好|
|高速 FIR|CMSIS-DSP|已验证、性能稳定|
|计数器原子加|LDREX/STREX 或临界区|保障复合操作一致性|
|修改 MPU|CMSIS + DSB/ISB|确保属性立即生效|
|大块 DMA 缓冲|Cache 维护 + 屏障|解决 CPU/DMA 一致性|
|低功耗切换|系统寄存器 + DSB/WFI|保证写入完成后休眠|
|Bootloader 跳转|设置 MSP、VTOR、Thumb 地址|避免异常和栈错乱|

---

# 8. 工程最佳实践

## 8.1 设计原则

1. **汇编最小化原则**
    - 只有在 C、CMSIS 或 intrinsic 无法满足需求时使用汇编。
2. **边界封装原则**
    - 汇编代码只暴露稳定的 C 接口。
3. **现场可恢复原则**
    - 所有异常入口必须能保存 PC、LR、SP、xPSR 和 Fault 状态。
4. **最坏情况优先原则**
    - 以 WCET、最大栈深度和最坏中断延迟为依据。
5. **架构约束显式化**
    - 在代码中明确小端、对齐、Thumb 地址、寄存器宽度等假设。
6. **屏障语义精确化**
    - 不要把 `volatile` 当作内存屏障。
7. **ABI 一致性**
    - C、C++、汇编之间统一 AAPCS、栈对齐和符号命名。
8. **可诊断性优先**
    - 优化不能破坏故障回溯和版本定位能力。

## 8.2 选型决策矩阵

|需求|C|CMSIS|内联汇编|独立汇编|
|---|---|---|---|---|
|可维护性|高|高|中|低|
|可移植性|高|中高|低|低|
|精确控制|低|中高|高|极高|
|调试难度|低|中|高|高|
|启动代码|不适合|部分适合|不适合|最适合|
|异常入口|不适合|部分适合|适合|最适合|
|DSP 循环|中|高|高|高|
|团队协作|高|高|中|中低|

## 8.3 工业级编码规范

### 汇编规范

- 所有汇编入口写明：
    - 输入寄存器。
    - 输出寄存器。
    - 被调用者保存寄存器。
    - 是否修改条件标志。
    - 栈对齐要求。
    - 是否允许中断。
- 避免魔数，使用宏定义或注释说明寄存器地址。
- 每个 `push` 必须有明确对应的 `pop`。
- 所有异常路径检查 SP 是否有效。
- 不在普通业务函数中直接修改 `PRIMASK`。

### C 规范

- 外设寄存器必须使用正确宽度的 `volatile` 类型。
- 共享变量使用 `volatile` 只是第一步。
- 位移前检查移位量范围。
- 禁止将未对齐网络数据直接转换为宽类型指针。
- 对函数指针跳转检查地址范围和 Thumb 位。
- 所有栈使用量纳入静态和动态分析。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：函数地址未设置 Thumb 位

### 错误代码

```
void boot_jump(uint32_t address)
{
    void (*entry)(void) = (void (*)(void))address;
    entry();
}
```

### 根因

Cortex-M 只支持 Thumb 状态，异常或分支目标地址必须满足 Thumb 标识要求。

### 正确实现

```
void boot_jump(uint32_t address)
{
    void (*entry)(void);

    entry = (void (*)(void))(address | 1U);
    entry();
}
```

实际 Bootloader 还必须先：

- 关闭中断。
- 停止 SysTick。
- 清除 NVIC pending。
- 设置 MSP。
- 设置 `VTOR`。
- 清理外设状态。

### 风险影响

- 触发 UsageFault 或 HardFault。
- 跳转到错误地址。
- 系统表现为“偶发无法升级”。

---

## 9.2 错误二：把 `volatile` 当作原子操作

### 错误代码

```
volatile uint32_t event_count;

void event_inc(void)
{
    event_count++;
}
```

### 根因

`event_count++` 至少包含：

```
load -> add -> store
```

中断或其他执行流可以在中间插入。

### 正确实现

单核中断场景：

```
void event_inc(void)
{
    uint32_t state = __get_PRIMASK();

    __disable_irq();
    ++event_count;
    __set_PRIMASK(state);
}
```

更高并发要求使用：

- `LDREX/STREX`。
- RTOS 原子 API。
- 硬件计数器。
- 外设事件寄存器。

### 风险影响

- 丢事件。
- 计数器回退。
- 状态机进入不可恢复状态。

---

## 9.3 错误三：修改系统控制寄存器后不执行 ISB

### 错误代码

```
__set_CONTROL(__get_CONTROL() | 0x02U);
/* 立即假设后续代码已经使用 PSP */
```

### 根因

控制寄存器更新与指令流水线执行存在时序关系。

### 正确实现

```
uint32_t control = __get_CONTROL();
control |= 0x02U;

__set_CONTROL(control);
__ISB();
```

### 风险影响

- 栈切换行为不符合预期。
- 任务启动时使用错误堆栈。
- 产生难以复现的异常。

---

## 9.4 错误四：未对齐数据直接强制转换

### 错误代码

```
uint32_t value = *(const uint32_t *)&packet[1];
```

### 根因

`packet + 1` 很可能不是 4 字节对齐地址。

### 正确实现

```
uint32_t value;

memcpy(&value, &packet[1], sizeof(value));
```

或显式按字节拼装。

### 风险影响

- UsageFault。
- 总线访问次数增加。
- 不同编译器和优化级别下行为不一致。

---

## 9.5 错误五：异常中使用错误的堆栈指针

### 错误代码

```
void HardFault_Handler(void)
{
    uint32_t *frame = (uint32_t *)__get_MSP();
    /* 假设所有异常都使用 MSP */
}
```

### 根因

Thread 模式可能使用 PSP，异常进入后 Handler 使用 MSP，但硬件自动压栈的现场可能位于 PSP。

### 正确实现

检查异常 LR：

```
tst  lr, #4
ite  eq
mrseq r0, msp
mrsne r0, psp
```

### 风险影响

- 读取错误内存。
- Fault Handler 二次崩溃。
- 无法恢复故障 PC。

---

## 9.6 错误六：修改 VTOR 后没有同步屏障

### 错误代码

```
SCB->VTOR = new_vector;
__enable_irq();
```

### 根因

向量表更新、取指和中断响应之间可能存在流水线或系统总线时序问题。

### 正确实现

```
SCB->VTOR = new_vector;
__DSB();
__ISB();
__enable_irq();
```

### 风险影响

- 第一个中断进入旧向量表。
- Bootloader/Application 边界偶发中断错跳。
- 现场难以重现。

---

# 10. 多机制组合使用方案

## 10.1 “异常现场 + MPU + RTOS + 看门狗”架构

推荐架构：

```
应用任务
  │
  ├─ PSP + 非特权模式
  ├─ MPU 限制代码、数据和外设访问
  └─ 通过 SVC 请求内核服务
       │
       ▼
RTOS 内核
  │
  ├─ MSP
  ├─ BASEPRI 临界区
  ├─ PendSV 上下文切换
  ├─ SysTick/定时器
  └─ 资源和权限管理
       │
       ▼
Fault 框架
  │
  ├─ HardFault/MemManage/BusFault/UsageFault
  ├─ 保存异常栈帧
  ├─ 保存 CFSR/HFSR/BFAR/MMFAR
  ├─ CRC 校验
  └─ 看门狗复位或安全降级
```

## 10.2 上下文切换代码框架

以下为简化框架，真实 RTOS 还需要处理 FPU、临界区和调度器状态。

```
typedef struct task_control_block {
    uint32_t *sp;
} task_control_block_t;

extern task_control_block_t *current_task;
extern task_control_block_t *next_task;

__attribute__((naked))
void PendSV_Handler(void)
{
    __asm volatile (
        "mrs     r0, psp                         \n"
        "isb                                     \n"

        "stmdb   r0!, {r4-r11}                  \n"

        "ldr     r1, =current_task              \n"
        "ldr     r2, [r1]                        \n"
        "str     r0, [r2]                        \n"

        "ldr     r2, =next_task                 \n"
        "ldr     r2, [r2]                        \n"
        "ldr     r0, [r2]                        \n"

        "ldmia   r0!, {r4-r11}                  \n"
        "msr     psp, r0                         \n"
        "isb                                     \n"

        "ldr     r1, =current_task              \n"
        "str     r2, [r1]                        \n"

        "bx      lr                             \n"
    );
}
```

设计要点：

- `r4-r11` 是被调用者保存寄存器。
- 异常硬件已经保存了 `r0-r3/r12/lr/pc/xpsr`。
- `PSP` 指向任务栈。
- 任务控制块中的 `sp` 必须始终指向有效栈帧。
- `PendSV` 应设置为最低可抢占优先级。
- 临界区不能破坏上下文切换时序。

---

# 11. 工业级实际案例分析

## 11.1 案例一：Bootloader 安全跳转到应用

### 需求

- Bootloader 位于 `0x08000000`。
- 应用位于 `0x08020000`。
- 跳转前检查镜像 CRC、版本和签名。
- 应用拥有独立向量表。

### 架构设计

```
上电
 │
 ▼
Bootloader
 ├─ 校验镜像签名
 ├─ 校验镜像 CRC
 ├─ 停止 SysTick
 ├─ 关闭并清除 NVIC 中断
 ├─ 设置 VTOR
 ├─ 设置 MSP
 └─ 跳转 Reset_Handler
```

### 核心代码

```
typedef void (*application_entry_t)(void);

static void disable_all_irqs(void)
{
    __disable_irq();

    SysTick->CTRL = 0U;
    SysTick->LOAD = 0U;
    SysTick->VAL = 0U;

    for (uint32_t i = 0U;
         i < (sizeof(NVIC->ICER) / sizeof(NVIC->ICER[0]));
         ++i) {
        NVIC->ICER[i] = 0xFFFFFFFFUL;
        NVIC->ICPR[i] = 0xFFFFFFFFUL;
    }
}

void jump_to_application(uint32_t app_base)
{
    uint32_t app_msp;
    uint32_t app_reset;
    application_entry_t entry;

    app_msp = *(volatile uint32_t *)(app_base + 0U);
    app_reset = *(volatile uint32_t *)(app_base + 4U);

    if ((app_msp & 0x2FFF0000UL) != 0x20000000UL) {
        return;
    }

    if ((app_reset & 1U) == 0U) {
        return;
    }

    disable_all_irqs();

    SCB->VTOR = app_base;
    __DSB();
    __ISB();

    __set_MSP(app_msp);
    __DSB();
    __ISB();

    entry = (application_entry_t)app_reset;
    entry();

    while (1) {
        /* 不应返回 */
    }
}
```

### 设计要点

- MSP 地址范围检查必须匹配实际 SRAM 布局。
- 不能仅检查地址低位就认为镜像可信。
- 跳转前需关闭 DMA、定时器、通信外设。
- 若启用 TrustZone-M，还需处理安全状态跳转。
- 生产系统必须增加签名验证和防回滚策略。

---

## 11.2 案例二：电机控制中的定时 ISR

### 需求

- PWM 频率 20 kHz。
- 控制周期 50 μs。
- 处理 ADC 采样、电流环、SVPWM 更新。
- 最大控制路径不得超过 25 μs。
- 目标 Cortex-M4F，168 MHz。

### 周期预算

25μs×168MHz=4200 cycles25μs×168MHz=4200 cycles

设计预算：

|模块|周期预算|
|---|---|
|ISR 进入/退出|300 cycles|
|ADC 数据整理|500 cycles|
|Clarke/Park 变换|1000 cycles|
|PI 控制器|900 cycles|
|SVPWM|800 cycles|
|保护检查|300 cycles|
|合计|3800 cycles|
|裕量|400 cycles|

### 代码框架

```
void PWM_IRQHandler(void)
{
    uint32_t adc_current_a;
    uint32_t adc_current_b;
    int32_t ia;
    int32_t ib;

    adc_current_a = ADC1->DR_A;
    adc_current_b = ADC1->DR_B;

    ia = adc_to_q31(adc_current_a);
    ib = adc_to_q31(adc_current_b);

    if (over_current(ia, ib)) {
        PWM1->TRIP = PWM_TRIP_DISABLE;
        fault_latch_set();
        return;
    }

    current_transform(ia, ib);
    pi_current_control();
    svm_update();

    PWM1->IRQ_CLEAR = PWM_IRQ_UPDATE;
}
```

### 设计要点

- ISR 中禁止动态内存分配。
- 避免调用不可控延迟的库函数。
- 浮点使用需确认 FPU 上下文成本。
- ADC/DMA 缓冲区和控制变量放入低延迟 SRAM。
- 用 DWT 测量最坏路径，而不是平均路径。
- 保护路径必须短于正常控制路径。
- 对 PWM 关闭寄存器使用硬件紧急关断机制，不能依赖软件 ISR 单一路径。

---

## 11.3 案例三：工业设备异常诊断

### 需求

- 现场出现偶发 HardFault。
- 设备必须保存故障上下文并在重启后上传。
- 需要定位到具体版本、任务和指令地址。

### 保存信息

```
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t reset_count;

    fault_frame_t frame;
    uint32_t exc_return;

    uint32_t hfsr;
    uint32_t cfsr;
    uint32_t mmfar;
    uint32_t bfar;
    uint32_t control;
    uint32_t msp;
    uint32_t psp;

    uint32_t crc;
} fault_record_t;
```

### 设计要点

- 保存在备份 SRAM、外部 FRAM 或专用 Flash 页。
- 写入顺序应保证掉电不产生“伪有效记录”。
- 增加 magic、长度、版本和 CRC。
- 记录应用版本、编译时间、Git commit、任务 ID。
- 解析 PC 时使用 `.elf` 和 map 文件符号化。
- 对不可恢复故障执行安全复位，而不是在 Fault Handler 中无限循环占用看门狗。

---

# 12. 高频问题深度答疑

## 问题 1：为什么 Cortex-M 不支持 ARM 指令集？

Cortex-M 的设计目标是低成本、低功耗和实时控制。Thumb-2 能够以 16/32 位混合编码提供接近 ARM 指令集的表达能力，同时降低代码存储需求和取指带宽。

因此 Cortex-M 从架构层面规定只支持 Thumb 状态。代码中看到的：

```
.word 0x...
.thumb
.thumb_func
```

并不表示 CPU 支持传统 ARM 状态，而是汇编器在生成 Thumb 指令和符号属性。

---

## 问题 2：函数地址为什么经常是奇数？

最低位为 1 是 Thumb 状态标识，不是实际内存访问地址。处理器在取指时会按指令对齐规则处理地址。

例如：

```
实际代码地址：0x08001200
函数指针值：  0x08001201
```

如果最低位为 0，`BX`、异常返回或函数指针调用可能触发状态错误。

---

## 问题 3：`DMB`、`DSB`、`ISB` 到底怎么选？

简化判断：

```
只需要保证数据访问顺序？
-> DMB

需要等待写入真正完成后再继续？
-> DSB

修改了处理器执行环境、MPU、CONTROL、VTOR？
-> ISB，通常配合 DSB
```

例如：

- 发布共享数据：`DMB`。
- 写外设后立即进入低功耗：`DSB`。
- 修改 `CONTROL` 或 MPU：`ISB`。
- 修改 VTOR：通常 `DSB + ISB`。

---

## 问题 4：为什么异常进入延迟不是固定的？

架构给出的是基础行为，不是所有实现的绝对周期。延迟受到以下因素影响：

- 当前指令是否可中断。
- Flash 等待周期。
- 总线是否被 DMA 占用。
- 是否需要浮点扩展压栈。
- 是否有更高优先级异常。
- Cache、TCM 和内存系统实现。
- 堆栈所在区域的访问速度。

实时系统必须测量：

```
最短中断延迟
平均中断延迟
最大中断延迟
嵌套情况下最大延迟
FPU 首次使用情况下最大延迟
```

---

## 问题 5：`PRIMASK` 和 `BASEPRI` 如何选择？

- `PRIMASK`：简单粗暴，屏蔽所有可屏蔽中断，适合极短关键硬件操作。
- `BASEPRI`：只屏蔽低优先级中断，允许高优先级实时中断继续运行，适合 RTOS 内核。

如果临界区中操作时间不可严格控制，不应使用 `PRIMASK`。否则可能导致：

- 丢失高频采样中断。
- 通信 FIFO 溢出。
- 看门狗喂狗延迟。
- 系统抖动扩大。

---

## 问题 6：HardFault 中为什么不能直接打印日志？

因为 Fault 发生时系统可能处于：

- 栈损坏。
- 堆损坏。
- 中断嵌套。
- 时钟异常。
- 外设状态未知。
- RTOS 锁死。
- 串口驱动不可用。

直接调用复杂日志函数可能再次触发异常。正确策略：

1. 使用最小汇编入口取现场。
2. 复制固定长度数据。
3. 写入保留存储区。
4. 尽量不调用动态内存和复杂驱动。
5. 复位后再上传和解析。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **Cortex-M 只执行 Thumb/Thumb-2，不支持传统 ARM 状态。**
2. **函数地址最低位为 1 表示 Thumb 状态。**
3. `R0-R3` 用于参数，`R4-R11` 通常由被调用者保存。
4. 异常进入时硬件自动保存基础栈帧。
5. `EXC_RETURN` 决定异常返回模式、使用 MSP/PSP 以及浮点栈帧。
6. `volatile` 不等于原子性，也不等于内存屏障。
7. `DMB/DSB/ISB` 分别解决顺序、完成和流水线同步问题。
8. `MSP` 通常用于异常和内核，`PSP` 通常用于任务。
9. 汇编应集中在启动、异常入口、上下文切换和极少数性能关键路径。
10. 任何性能结论必须在目标芯片上通过 DWT、示波器或 ETM 实测。

## 13.2 性能排序

在一般 Cortex-M 系统中，典型访问性能从高到低大致为：

```
寄存器运算
> TCM/零等待 SRAM
> 高命中 Cache 的 SRAM/Flash
> 顺序 Flash 访问
> 带等待周期的随机 Flash 访问
> 外部存储器
> 外设总线访问
> 未对齐或竞争严重的总线访问
```

注意：具体排序受芯片实现影响，特别是 Cortex-M7、外部 RAM 和 Cache 系统。

## 13.3 通用选型结论

|目标|推荐|
|---|---|
|可维护业务逻辑|C|
|系统寄存器访问|CMSIS|
|屏障、特殊寄存器|CMSIS intrinsic|
|异常入口|少量汇编 + C|
|RTOS 切换|独立汇编|
|DSP/滤波|CMSIS-DSP|
|原子操作|架构原子指令或 RTOS 封装|
|极限性能|C 优化 + 反汇编验证 + 必要时汇编|
|故障定位|汇编取现场 + C 保存诊断记录|

---

# 14. 快速参考速查表

## 14.1 常用指令速查

|指令|作用|
|---|---|
|`MOV`|寄存器或立即数传送|
|`MVN`|按位取反后传送|
|`ADD/SUB`|加减法|
|`MUL`|乘法|
|`CMP`|比较并更新标志|
|`TST`|按位与并更新标志|
|`AND/ORR/EOR/BIC`|位操作|
|`LSL/LSR/ASR/ROR`|移位和旋转|
|`LDR/STR`|32 位加载/存储|
|`LDRB/STRB`|8 位加载/存储|
|`LDRH/STRH`|16 位加载/存储|
|`PUSH/POP`|栈操作|
|`B`|无条件跳转|
|`BL`|带链接调用|
|`BX`|按地址状态跳转|
|`CBZ/CBNZ`|零比较跳转|
|`MRS/MSR`|特殊寄存器读写|
|`SVC`|触发系统服务异常|
|`WFI/WFE`|等待中断/事件|
|`DMB`|数据内存屏障|
|`DSB`|数据同步屏障|
|`ISB`|指令同步屏障|
|`LDREX/STREX`|独占访问原子操作|

## 14.2 特殊寄存器速查

|寄存器|作用|
|---|---|
|`MSP`|主堆栈指针|
|`PSP`|进程堆栈指针|
|`CONTROL`|堆栈选择和特权控制|
|`xPSR`|状态、异常号和条件标志|
|`PRIMASK`|全局中断屏蔽|
|`BASEPRI`|按优先级屏蔽|
|`FAULTMASK`|Fault 屏蔽|
|`VTOR`|向量表基地址|
|`CFSR`|可配置 Fault 状态|
|`HFSR`|HardFault 状态|
|`MMFAR`|MemManage 故障地址|
|`BFAR`|BusFault 故障地址|
|`ICSR`|中断控制与状态|
|`SHCSR`|系统处理器控制与状态|

## 14.3 场景选型表

|场景|首选机制|
|---|---|
|任务栈切换|PSP + PendSV|
|内核临界区|BASEPRI|
|极短硬件原子操作|PRIMASK|
|用户权限隔离|MPU/TrustZone-M|
|异常回溯|自动栈帧 + CFSR|
|外设写后休眠|DSB|
|发布共享数据|DMB|
|修改 MPU/CONTROL|ISB|
|高频控制 ISR|定点/DSP + SRAM/TCM|
|Bootloader 跳转|MSP + VTOR + Thumb 地址|
|DMA 与 Cache|Cache 维护 + 屏障|

---

# 15. 学习效果自检

完成本课后，应能够回答并实操以下任务：

- [ ]  解释 Cortex-M 为什么只支持 Thumb。
- [ ]  解释函数指针地址最低位为什么通常为 1。
- [ ]  写出 Cortex-M 异常自动保存的 8 个寄存器。
- [ ]  根据 `EXC_RETURN` 判断现场位于 MSP 还是 PSP。
- [ ]  解释 `R0-R3` 和 `R4-R11` 在 AAPCS 中的职责。
- [ ]  写出读取 MSP、PSP、CONTROL 的代码。
- [ ]  写出一个可靠的 HardFault 现场捕获入口。
- [ ]  区分 `volatile`、原子操作和内存屏障。
- [ ]  说明 `DMB/DSB/ISB` 的典型使用场景。
- [ ]  解释为什么未对齐指针转换存在风险。
- [ ]  分析一个 C 函数对应的 Thumb 汇编。
- [ ]  估算一个 ISR 的周期预算。
- [ ]  通过 DWT 测量函数周期数。
- [ ]  设计 MSP/PSP 分离的 RTOS 栈布局。
- [ ]  设计 Bootloader 到 Application 的安全跳转流程。
- [ ]  根据 CFSR、HFSR、BFAR 和异常 PC 定位 HardFault。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：寄存器和汇编基础

实现：

- 读取 MSP、PSP、CONTROL、xPSR。
- 使用内联汇编实现：
    - 位设置。
    - 位清除。
    - 32 位循环右移。
    - 饱和加法。
- 对比 C、CMSIS intrinsic 和汇编生成结果。

验收标准：

- 能正确解释每条指令。
- 栈对齐不被破坏。
- 通过 `objdump -d` 验证实际编码。

### 任务二：启动文件和向量表

实现：

- 自定义向量表。
- 编写 `Reset_Handler`。
- 初始化 `.data` 和 `.bss`。
- 设置 VTOR。
- 加入默认异常处理器。

验收标准：

- 能从复位进入 `main`。
- 能触发并确认 SysTick、UART、HardFault 向量。
- 能通过 map 文件确认各段地址。

### 任务三：HardFault 诊断框架

实现：

- 保存自动栈帧。
- 保存 MSP、PSP、CONTROL、CFSR、HFSR、BFAR、MMFAR。
- 写入保留 RAM。
- 重启后输出符号化信息。

人为制造故障：

```
void trigger_fault(void)
{
    volatile uint32_t *invalid =
        (volatile uint32_t *)0xFFFFFFF0UL;

    *invalid = 0x12345678UL;
}
```

验收标准：

- 能定位故障 PC。
- 能区分非法访问、未定义指令、除零和栈错误。
- Fault Handler 不发生二次崩溃。

### 任务四：最小 RTOS 上下文切换

实现：

- MSP 承担异常和内核。
- PSP 承担任务。
- PendSV 保存和恢复 `R4-R11`。
- 使用 SysTick 触发调度。
- 增加栈水位检测。

验收标准：

- 两个任务正常切换。
- 任务栈 8 字节对齐。
- 可检测栈溢出。
- 可测量上下文切换周期。

### 任务五：DMA、Cache 和内存屏障

在 Cortex-M7 或带 Cache 的 Cortex-M33 平台上实现：

- DMA 接收缓冲。
- CPU 读取前 Cache invalidate。
- CPU 写入后 DMA 发送前 Cache clean。
- 在关键点加入 DMB/DSB。

验收标准：

- 长时间运行无数据不一致。
- 测量 Cache 维护的周期成本。
- 说明为什么只加 `volatile` 无法解决问题。

---

## 16.2 性能测试方法

### 测试维度

1. 指令路径周期数。
2. ISR 进入和退出延迟。
3. 异常嵌套延迟。
4. Flash 与 SRAM 执行差异。
5. 对齐与未对齐访问差异。
6. FPU 首次使用开销。
7. Cache 冷启动和热启动差异。
8. PendSV 上下文切换成本。
9. 临界区最大关闭中断时间。
10. 栈最大深度和高水位。

### 测试工具

- DWT `CYCCNT`。
- ITM/SWO。
- ETM trace。
- GPIO 翻转 + 示波器。
- J-Link RTT。
- GDB Python 脚本。
- `arm-none-eabi-objdump`。
- `arm-none-eabi-size`。
- `arm-none-eabi-nm`。
- map 文件和 ELF 符号化工具。

### 性能报告至少包含

```
芯片型号：
内核型号：
主频：
编译器版本：
优化选项：
Flash 等待周期：
代码位置：
数据位置：
是否启用 FPU：
是否启用 Cache：
中断背景：
平均周期：
最大周期：
99.9% 周期：
栈峰值：
结论和风险：
```

---

## 16.3 进阶学习方向

### 内核和异常方向

- ARMv7-M、ARMv7E-M、ARMv8-M 架构手册。
- NVIC、SCB、MPU、SCS 寄存器。
- SVC、PendSV、SysTick 的 RTOS 实现。
- Fault escalation 和异常优先级。

### 编译器和 ABI 方向

- AAPCS 调用约定。
- Thumb-2 编码。
- GCC extended asm 约束。
- 链接器重定位。
- LTO、函数节、链接脚本。
- 编译器生成代码与手写汇编的对比。

### 性能方向

- Cortex-M7 Cache 和 TCM。
- CMSIS-DSP。
- DWT/ITM/ETM。
- WCET 分析。
- Flash 加速器和总线矩阵。
- 指令级功耗测量。

### 安全方向

- MPU 内存隔离。
- TrustZone-M。
- Secure/Non-secure 函数调用。
- PSA Firmware Framework。
- 栈保护、CFI、不可执行区域。
- 安全启动和故障注入防护。

### 最终工程目标

应能够独立完成以下系统级任务：

```
启动代码
  + 向量表
  + Bootloader 跳转
  + RTOS 上下文切换
  + MPU/TrustZone 隔离
  + DMA/Cache 一致性
  + HardFault 诊断
  + WCET 和栈深度验证
  + 量产版本回滚与远程故障分析
```

这套能力才构成 Cortex-M 指令集和汇编知识在工业级嵌入式系统中的完整闭环。