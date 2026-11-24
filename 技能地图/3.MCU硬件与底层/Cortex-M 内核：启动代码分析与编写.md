

## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 Cortex-M 上电后的硬件启动序列：
    - 读取向量表第 0 项初始化 MSP
    - 读取向量表第 1 项进入 `Reset_Handler`
    - 执行时钟、内存、C/C++ 运行时初始化
- 理解 Cortex-M 异常模型、向量表布局和异常入口机制。
- 理解 `Reset_Handler`、`SystemInit`、`.data`、`.bss`、`__libc_init_array` 之间的调用关系。
- 理解启动代码与链接脚本、启动汇编、CMSIS、编译器运行库之间的边界。

### 掌握

能够：

- 分析 GCC、ArmClang、IAR 等工具链生成的启动代码。
- 编写符合 Cortex-M 异常模型的向量表。
- 编写 `.data` 拷贝、`.bss` 清零、堆栈边界初始化代码。
- 正确配置 `SCB->VTOR`，实现向量表重定位。
- 编写弱符号默认中断处理函数。
- 区分 Cortex-M0/M0+ 与 Cortex-M3/M4/M7/M33 在启动代码上的差异。

### 精通

能够：

- 分析启动阶段 HardFault、BusFault、UsageFault、MemManage Fault 的根因。
- 设计 Bootloader → Application 的跳转协议。
- 设计支持 RAM 启动、XIP、双 Bank、OTA 回滚的启动框架。
- 量化启动时间、`.data` 拷贝时间、`.bss` 清零时间和向量表重定位开销。
- 诊断启动阶段栈溢出、时钟未就绪、FPU 未启用、Cache/MPU 配置顺序错误等问题。

### 能够设计

能够设计一套工业级 Cortex-M 启动框架，满足：

- 明确的硬件复位、Bootloader、应用启动分层。
- 可验证的内存初始化流程。
- 可诊断的异常处理框架。
- 支持多镜像、向量表重定位和安全启动扩展。
- 启动时延、内存占用和故障行为可量化、可测试。

---

## 2. 前置要求

### 知识要求

|类别|必备知识|
|---|---|
|C 语言|指针、数组、函数指针、链接属性、`volatile`、位操作|
|汇编|ARM Thumb 指令、`MSR`、`MRS`、`LDR`、`BX`、栈操作|
|MCU|Flash、SRAM、时钟树、复位源、NVIC|
|编译原理|编译、汇编、链接、重定位、符号解析|
|链接脚本|`section`、`LOADADDR`、`AT`、`KEEP`、符号导出|
|Cortex-M|异常、特权级、MSP/PSP、向量表、SCB|

### 技能要求

- 能使用 `arm-none-eabi-gcc`、`objdump`、`readelf`。
- 能阅读 `.map` 文件。
- 能通过 JTAG/SWD 单步执行 `Reset_Handler`。
- 能查看寄存器：
    - `SCB->VTOR`
    - `SCB->CFSR`
    - `SCB->HFSR`
    - `SCB->BFAR`
    - `SCB->MMFAR`
    - `SCB->ICSR`
- 能修改并重新链接一个 MCU 工程。

---

## 3. 技术概述

## 3.1 启动代码的定义

Cortex-M 启动代码是处理器复位后，进入 C 语言运行环境前执行的一段底层代码，主要负责：

1. 提供异常向量表。
2. 设置主堆栈指针 MSP。
3. 设置异常处理入口。
4. 初始化时钟和芯片级硬件。
5. 初始化 `.data` 段。
6. 清零 `.bss` 段。
7. 初始化 C/C++ 运行时。
8. 调用 `main()`。
9. 在 `main()` 返回时进入安全停机状态。

典型调用链如下：

```
硬件复位
    │
    ├── CPU 从地址 0x00000000 读取初始 MSP
    │
    ├── CPU 从地址 0x00000004 读取 Reset_Handler
    │
    └── Reset_Handler
            │
            ├── 芯片底层初始化 SystemInit()
            ├── 拷贝 .data
            ├── 清零 .bss
            ├── 初始化 C/C++ 运行库
            ├── 调用 main()
            └── main 返回后的安全停机
```

## 3.2 Cortex-M 异常向量表结构

典型向量表：

|偏移|向量|说明|
|---|---|---|
|`0x00`|Initial MSP|初始主堆栈指针|
|`0x04`|Reset|复位处理函数|
|`0x08`|NMI|不可屏蔽中断|
|`0x0C`|HardFault|硬错误|
|`0x10`|MemManage|内存管理错误，部分内核支持|
|`0x14`|BusFault|总线错误，部分内核支持|
|`0x18`|UsageFault|用法错误，部分内核支持|
|`0x1C`|Reserved|保留|
|`0x20`|Reserved|保留|
|`0x24`|Reserved|保留|
|`0x28`|Reserved|保留|
|`0x2C`|SVCall|SVC 系统调用|
|`0x30`|DebugMon|调试监控|
|`0x34`|Reserved|保留|
|`0x38`|PendSV|可挂起系统服务|
|`0x3C`|SysTick|系统滴答|
|`0x40`|IRQ0|外部中断 0|
|...|...|芯片外部中断|

向量表中保存的是：

- 第 0 项：一个栈地址。
- 后续项目：异常处理函数地址。

处理函数地址通常必须带有 **Thumb 状态位**，因此最低位为 `1`。例如：

```
Reset_Handler 地址 = 0x08000101
实际指令地址     = 0x08000100
```

Cortex-M 仅执行 Thumb 指令，向量表中的函数地址最低位用于标识 Thumb 状态。

## 3.3 主流启动代码实现分支

|实现方案|特点|适用场景|
|---|---|---|
|厂商汇编启动文件|硬件厂商提供，兼容性好|传统裸机工程|
|CMSIS 启动文件|标准化、可移植|多芯片族工程|
|纯 C 启动代码|易读、可调试|Cortex-M3 及以上、定制平台|
|C + 少量汇编|工程实践最常用|生产项目|
|Bootloader 二级启动|支持 OTA、校验、回滚|产品级设备|
|安全启动框架|增加签名验证、隔离和密钥保护|安全产品|

---

## 4. 核心特性横向对比

## 4.1 Cortex-M 内核启动差异

|项目|Cortex-M0/M0+|Cortex-M3|Cortex-M4|Cortex-M7|Cortex-M33|
|---|---|---|---|---|---|
|Thumb 指令集|Thumb-1 子集|Thumb-2|Thumb-2|Thumb-2|Thumb-2|
|`VTOR`|M0 通常无，M0+ 取决于实现|支持|支持|支持|支持|
|MemManage Fault|不支持|支持|支持|支持|支持|
|BusFault|不支持或有限|支持|支持|支持|支持|
|UsageFault|不支持|支持|支持|支持|支持|
|FPU|无|无|可选|可选|可选|
|Cache|无|无|通常无|I/D Cache 常见|实现相关|
|MPU|可选|可选|可选|可选|常见|
|TrustZone|不支持|不支持|不支持|不支持|可选|
|启动复杂度|低|中|中|高|很高|

## 4.2 启动代码方案对比

|方案|可读性|可移植性|启动性能|维护成本|主要风险|
|---|---|---|---|---|---|
|全汇编|低|低|高|高|不易审计|
|全 C|高|高|中|低|早期 ABI 假设|
|C + 汇编入口|高|高|高|中|接口边界错误|
|厂商模板|中|低|中|中|隐含初始化|
|CMSIS 模板|高|中|中|低|依赖厂商实现|
|Bootloader + App|中|中|中|高|跳转状态不完整|
|安全启动|中|中|低至中|很高|验证链配置错误|

## 4.3 运行时初始化对比

|初始化项|是否必须|典型实现|失败后果|
|---|---|---|---|
|MSP 初始化|必须|硬件自动加载|立即异常|
|`.data` 拷贝|必须|`LMA → VMA`|全局变量初值错误|
|`.bss` 清零|必须|RAM 清零|静态变量非零|
|时钟初始化|通常必须|`SystemInit()`|系统频率错误|
|FPU 初始化|使用浮点时必须|CPACR 设置|浮点指令 UsageFault|
|C++ 构造函数|C++ 必须|`__libc_init_array()`|全局对象未构造|
|Cache 初始化|M7 等平台常见|SCB Cache API|性能或一致性问题|
|MPU 配置|使用 MPU 时必须|区域配置|访问异常|
|VTOR 配置|向量重定位时必须|`SCB->VTOR`|中断进入错误地址|

---

# 5. 底层原理与功能特性深度解析

## 5.1 硬件复位后的第一条“指令”

Cortex-M 复位后，并不是从某个固定的 `Reset_Handler` 地址开始执行，而是执行以下硬件动作：

```
MSP ← Mem[VTOR + 0x00]
PC  ← Mem[VTOR + 0x04]
xPSR.T ← 1
```

复位时，`VTOR` 通常具有默认值：

```
VTOR = 0x00000000
```

但 `0x00000000` 是否对应 Flash，需要由芯片的存储器映射决定。

例如：

```
0x00000000 ── Boot ROM / Flash Alias
0x08000000 ── Main Flash
0x20000000 ── SRAM
```

如果 Bootloader 或芯片启动模式改变了地址映射，向量表的实际位置也会改变。

## 5.2 启动汇编入口

一个典型的 GNU 汇编启动入口：

```
.syntax unified
.cpu cortex-m4
.thumb

.global Reset_Handler
.type Reset_Handler, %function

.extern SystemInit
.extern __libc_init_array
.extern main

.section .text.Reset_Handler
Reset_Handler:
    /* 复位后硬件已经装载 MSP。
     * 这里再次设置，便于 Bootloader 或调试场景统一处理。
     */
    ldr     r0, =_estack
    mov     sp, r0

    /* 可选：关闭中断，防止时钟和运行时初始化过程中进入 ISR */
    cpsid   i

    /* 芯片级初始化：时钟、FPU、Cache、外设复位等 */
    bl      SystemInit

    /* 初始化 C 运行时 */
    bl      __libc_init_array

    /* 进入应用 */
    bl      main

    /* main 不应返回 */
.L_main_return:
    b       .L_main_return

.size Reset_Handler, . - Reset_Handler
```

这里需要注意：

- `SystemInit()` 与 `.data/.bss` 初始化的先后顺序不是绝对固定。
- 某些厂商在 `SystemInit()` 内部依赖已初始化的全局变量，这种设计应避免。
- `__libc_init_array()` 需要在 C++ 或使用构造函数的运行时环境中调用。
- `main()` 返回后不能直接 `bx lr`，否则可能跳转到无效返回地址。

## 5.3 `.data` 和 `.bss` 的本质

假设源码：

```
uint32_t g_counter = 100;
uint8_t  g_buffer[1024];
const char g_name[] = "device";
```

最终可能被放入：

```
.data:
    g_counter = 100
    运行地址：SRAM
    加载地址：Flash

.bss:
    g_buffer[1024]
    只需要分配 SRAM，不占用 Flash 镜像空间

.rodata:
    g_name[]
    运行地址：Flash
```

`.data` 具有两个地址：

- **LMA，Load Memory Address**：镜像存储地址，通常在 Flash。
- **VMA，Virtual Memory Address**：运行地址，通常在 SRAM。

启动时执行：

```
Flash[LMA] → SRAM[VMA]
```

链接脚本示例：

```
.data : ALIGN(4)
{
    __data_start__ = .;
    *(.data)
    *(.data.*)
    __data_end__ = .;
} > RAM AT > FLASH

__data_load__ = LOADADDR(.data);

.bss (NOLOAD) : ALIGN(4)
{
    __bss_start__ = .;
    *(.bss)
    *(.bss.*)
    *(COMMON)
    __bss_end__ = .;
} > RAM
```

对应 C 代码：

```
#include <stdint.h>
#include <stddef.h>

extern uint32_t __data_load__;
extern uint32_t __data_start__;
extern uint32_t __data_end__;

extern uint32_t __bss_start__;
extern uint32_t __bss_end__;

static void runtime_init_data_bss(void)
{
    uint32_t *src  = &__data_load__;
    uint32_t *dst  = &__data_start__;
    uint32_t *end  = &__data_end__;

    while (dst < end) {
        *dst++ = *src++;
    }

    dst = &__bss_start__;
    end = &__bss_end__;

    while (dst < end) {
        *dst++ = 0U;
    }
}
```

生产实现需要保证：

- 起始地址按 4 字节对齐。
- `.data`、`.bss` 长度是 4 的整数倍，或者使用字节级处理。
- 链接脚本符号类型与 C 声明一致。
- 不能对 `const` 链接符号本身取值，而应取其地址。

## 5.4 更稳健的内存初始化实现

```
#include <stdint.h>

extern uint8_t __data_load__;
extern uint8_t __data_start__;
extern uint8_t __data_end__;

extern uint8_t __bss_start__;
extern uint8_t __bss_end__;

static void copy_data_section(void)
{
    uint8_t *src = &__data_load__;
    uint8_t *dst = &__data_start__;
    uint8_t *end = &__data_end__;

    while (dst < end) {
        *dst++ = *src++;
    }
}

static void zero_bss_section(void)
{
    uint8_t *dst = &__bss_start__;
    uint8_t *end = &__bss_end__;

    while (dst < end) {
        *dst++ = 0U;
    }
}

static void runtime_memory_init(void)
{
    copy_data_section();
    zero_bss_section();
}
```

对于高性能平台，可以使用字复制：

```
static void zero_bss_wordwise(void)
{
    uintptr_t start = (uintptr_t)&__bss_start__;
    uintptr_t end   = (uintptr_t)&__bss_end__;

    while ((start < end) && (start % sizeof(uint32_t) != 0U)) {
        *(uint8_t *)start = 0U;
        start++;
    }

    uint32_t *p = (uint32_t *)start;
    uint32_t *e = (uint32_t *)(end & ~(sizeof(uint32_t) - 1U));

    while (p < e) {
        *p++ = 0U;
    }

    while ((uintptr_t)p < end) {
        *(uint8_t *)p = 0U;
        p = (uint32_t *)((uintptr_t)p + 1U);
    }
}
```

实际工程中，通常优先使用编译器优化后的简单循环，避免手工优化引入未对齐访问和别名问题。

## 5.5 向量表定义

C 语言向量表：

```
#include <stdint.h>

typedef void (*isr_handler_t)(void);

extern uint32_t _estack;
void Reset_Handler(void);
void Default_Handler(void);

void NMI_Handler(void)       __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void MemManage_Handler(void) __attribute__((weak, alias("Default_Handler")));
void BusFault_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void UsageFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SVC_Handler(void)       __attribute__((weak, alias("Default_Handler")));
void DebugMon_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void PendSV_Handler(void)    __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void)   __attribute__((weak, alias("Default_Handler")));

__attribute__((section(".isr_vector"), used, aligned(256)))
const uintptr_t vector_table[] = {
    (uintptr_t)&_estack,
    (uintptr_t)Reset_Handler,
    (uintptr_t)NMI_Handler,
    (uintptr_t)HardFault_Handler,
    (uintptr_t)MemManage_Handler,
    (uintptr_t)BusFault_Handler,
    (uintptr_t)UsageFault_Handler,
    0U,
    0U,
    0U,
    0U,
    (uintptr_t)SVC_Handler,
    (uintptr_t)DebugMon_Handler,
    0U,
    (uintptr_t)PendSV_Handler,
    (uintptr_t)SysTick_Handler,
};
```

注意事项：

1. `section(".isr_vector")` 必须在链接脚本中置于镜像首部。
2. `used` 防止链接器垃圾回收。
3. 需要使用 `KEEP(*(.isr_vector))`。
4. 对齐要求取决于向量表长度和芯片实现，不能简单认为永远是 128 字节。
5. 中断向量数量较多时，应按照芯片头文件完整声明。

## 5.6 默认中断处理函数

最简单的默认处理函数：

```
__attribute__((noreturn))
void Default_Handler(void)
{
    while (1) {
        __asm volatile ("bkpt 0");
    }
}
```

生产级实现应保存故障现场：

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
} exception_stack_frame_t;

volatile exception_stack_frame_t *g_fault_frame;
volatile uint32_t g_fault_exc_return;

__attribute__((naked))
void HardFault_Handler(void)
{
    __asm volatile (
        "tst lr, #4                         \n"
        "ite eq                              \n"
        "mrseq r0, msp                       \n"
        "mrsne r0, psp                       \n"
        "mov r1, lr                          \n"
        "b hardfault_c                       \n"
    );
}

__attribute__((noreturn))
void hardfault_c(exception_stack_frame_t *frame,
                 uint32_t exc_return)
{
    g_fault_frame = frame;
    g_fault_exc_return = exc_return;

    /*
     * 此处可记录：
     * - PC/LR
     * - CFSR/HFSR/DFSR/AFSR
     * - BFAR/MMFAR
     * - 当前任务或线程信息
     */

    while (1) {
        __asm volatile ("bkpt 0");
    }
}
```

异常发生时，硬件自动压栈：

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

如果使用 FPU，可能还会压入扩展浮点上下文，需结合 `EXC_RETURN` 判断。

## 5.7 FPU 初始化

对于 Cortex-M4F/M7 等带 FPU 的内核，需要启用 CP10 和 CP11：

```
#define SCB_CPACR (*(volatile uint32_t *)0xE000ED88UL)

static void fpu_enable(void)
{
    SCB_CPACR |= (3UL << 20U) | (3UL << 22U);

    __asm volatile ("dsb");
    __asm volatile ("isb");
}
```

CMSIS 形式：

```
SCB->CPACR |= (3UL << 20U) | (3UL << 22U);
__DSB();
__ISB();
```

如果在 FPU 未启用时执行浮点指令，可能触发：

- `NOCP` UsageFault。
- 若 UsageFault 未启用，则升级为 HardFault。

## 5.8 VTOR 向量表重定位

当应用不在 Flash 首地址时，需要配置：

```
SCB->VTOR = application_vector_address;
__DSB();
__ISB();
```

完整实现：

```
#include <stdint.h>

#define SCB_VTOR (*(volatile uint32_t *)0xE000ED08UL)

static int vector_table_is_valid(uint32_t address,
                                 uint32_t ram_start,
                                 uint32_t ram_end,
                                 uint32_t flash_start,
                                 uint32_t flash_end)
{
    uint32_t initial_sp = *(volatile uint32_t *)(address + 0U);
    uint32_t reset_pc   = *(volatile uint32_t *)(address + 4U);

    int sp_valid =
        (initial_sp >= ram_start) &&
        (initial_sp <  ram_end);

    int pc_valid =
        ((reset_pc & 1U) != 0U) &&
        ((reset_pc & ~1UL) >= flash_start) &&
        ((reset_pc & ~1UL) <  flash_end);

    return sp_valid && pc_valid;
}

static void set_vector_table(uint32_t address)
{
    /*
     * address 必须满足芯片要求的对齐约束。
     * M3/M4 常见要求为 128 字节或更高，具体以实现手册为准。
     */
    SCB_VTOR = address;
    __asm volatile ("dsb");
    __asm volatile ("isb");
}
```

必须注意：

- 不能只检查 `Reset_Handler` 地址。
- 需要校验初始 MSP 是否落在合法 SRAM 范围。
- 地址最低位必须为 `1`。
- 需要校验镜像长度、CRC/签名和版本号。
- 修改 `VTOR` 后必须执行 `DSB + ISB`。

## 5.9 时钟初始化顺序

典型 `SystemInit()`：

```
void SystemInit(void)
{
    /*
     * 1. 复位时钟控制器到已知状态
     * 2. 配置电源与电压范围
     * 3. 配置 Flash 等待周期
     * 4. 启动外部晶振或内部高速时钟
     * 5. 配置 PLL
     * 6. 切换系统时钟源
     * 7. 更新 SystemCoreClock
     * 8. 配置 FPU/MPU/Cache
     */
}
```

关键工程约束：

### Flash 等待周期必须先于升频

错误顺序：

```
切换到 168 MHz
    ↓
再设置 Flash 等待周期
```

正确顺序：

```
设置电压范围
    ↓
设置 Flash Latency
    ↓
配置 PLL
    ↓
等待锁定
    ↓
切换系统时钟
```

否则可能在切换瞬间发生取指错误。

### M7 Cache/MPU 顺序

常见顺序：

```
关闭 Cache
    ↓
配置 MPU
    ↓
清理/失效 Cache
    ↓
开启 Cache
    ↓
开启 MMU/MPU 相关策略
```

实际顺序必须遵循具体芯片参考手册，尤其是外部 SDRAM、DMA 缓冲区和非缓存区配置。

---

# 6. 性能量化分析

以下数据以一个典型平台为例：

- MCU：Cortex-M4F
- 主频：168 MHz
- Flash：零等待或少量等待
- SRAM：片上 SRAM
- 编译器：GCC `-O2`
- 不使用 DMA
- 使用 DWT CYCCNT 测量

## 6.1 `.bss` 清零时间

假设：

```
系统频率 F_CPU = 168 MHz
.bss 大小       = 32 KB
按 32 位写入
```

写入次数：

```
N = 32 × 1024 / 4 = 8192 次
```

如果每次循环平均 2～4 个周期：

```
Cycles ≈ 8192 × 3 = 24576 cycles
Time ≈ 24576 / 168 MHz
     ≈ 146 μs
```

实际测量通常约为：

```
120～250 μs
```

取决于：

- 编译器优化。
- SRAM 等待状态。
- 是否使用 `memset`。
- 是否有总线竞争。
- 是否启用 Cache。
- 是否清零多个不连续区域。

## 6.2 `.data` 拷贝时间

假设：

```
.data 大小 = 8 KB
Flash 读取平均 2～4 周期
SRAM 写入 1 周期
```

拷贝次数：

```
N = 8 × 1024 / 4 = 2048 次
```

估计：

```
Cycles ≈ 2048 × 5 = 10240 cycles
Time ≈ 61 μs
```

实测可能处于：

```
50～150 μs
```

## 6.3 向量表重定位开销

配置 VTOR 的本身开销非常小：

```
SCB->VTOR = address;
__DSB();
__ISB();
```

典型开销：

```
写寄存器：约 1～2 个总线周期
DSB：等待存储操作完成
ISB：刷新流水线，通常约数个周期
总计：约 10～30 个 CPU 周期
```

在 168 MHz 下大约：

```
60～180 ns
```

但是，真正的启动开销通常来自：

- 向量表复制。
- 时钟 PLL 锁定。
- 外部晶振启动。
- Flash 配置。
- Cache/MPU 初始化。

## 6.4 PLL 启动时间

典型范围：

|操作|典型耗时|
|---|---|
|内部 RC 启动|1～10 μs|
|外部晶振启动|0.5～10 ms|
|PLL 锁定|10～500 μs|
|外部 SDRAM 初始化|1～10 ms|
|OTA 镜像校验|1～100 ms|

因此：

> 对大多数工业产品，启动时间瓶颈不是 `.bss` 清零，而是晶振、PLL、外部存储器和镜像校验。

## 6.5 内存占用分析

启动代码主要消耗：

|项目|典型大小|
|---|---|
|向量表|`4 × (16 + IRQ 数量)` 字节|
|Reset_Handler|50～300 字节|
|`.data` 镜像|与 `.data` 运行大小相同，占 Flash|
|`.bss`|只占 SRAM|
|Fault Handler|100～1000 字节|
|C++ 运行时初始化|视构造函数数量而定|

例如芯片有 82 个外部中断：

```
向量项 = 16 + 82 = 98
向量表大小 = 98 × 4 = 392 字节
```

为了满足对齐，可能需要放置到：

```
512 字节边界
```

## 6.6 启动优化手段

|优化手段|收益|风险|
|---|---|---|
|减少全局初始化变量|降低 `.data` 拷贝时间|代码可读性下降|
|将大缓冲区放入 `.bss`|节省 Flash 镜像|启动清零时间增加|
|让硬件 DMA 清零|降低 CPU 占用|DMA 早期初始化复杂|
|延迟初始化非关键外设|缩短首帧启动时间|初始化依赖管理复杂|
|使用内部 RC 首启动|减少启动等待|频率精度较低|
|并行执行镜像校验与硬件初始化|缩短总启动时间|状态机复杂|
|仅在需要时初始化 C++ 构造|缩短启动时间|破坏语言运行时预期|

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否存在 Bootloader？
├── 否
│   ├── 应用位于 Flash 首地址？
│   │   ├── 是：使用单级启动代码
│   │   └── 否：配置 VTOR + 镜像合法性检查
│   │
│   └── 是否使用 C++？
│       ├── 否：可不调用 __libc_init_array
│       └── 是：必须调用 __libc_init_array
│
└── 是
    ├── 是否需要 OTA？
    │   ├── 否：Bootloader 校验后直接跳转
    │   └── 是：增加镜像版本、CRC/签名、回滚状态
    │
    ├── 是否启用 TrustZone？
    │   ├── 否：普通 MSP/VTOR 跳转
    │   └── 是：配置安全/非安全向量表与栈
    │
    └── 是否使用 Cache/DMA/外部 RAM？
        ├── 否：普通启动流程
        └── 是：增加 MPU、Cache、内存屏障和一致性处理
```

## 7.2 典型场景选型

|场景|需求|方案|理由|
|---|---|---|---|
|简单裸机控制器|快速启动、代码少|CMSIS 启动文件|结构简单、稳定|
|RTOS 应用|中断、PendSV、SysTick 正常工作|标准向量表 + RTOS 异常入口|需要精确控制异常|
|Bootloader + App|应用不在首地址|App 自定义向量表 + VTOR|防止中断进入 Bootloader|
|OTA 设备|签名、回滚、双镜像|一级 Boot + 二级 App|方便故障恢复|
|Cortex-M7 高性能系统|Cache、MPU、SDRAM|分阶段启动|避免早期内存一致性错误|
|Cortex-M33 安全设备|安全世界/非安全世界|双启动框架|需要安全边界|
|低功耗设备|极短唤醒时间|RAM 保留、延迟初始化|降低每次唤醒成本|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：启动阶段必须建立“已知状态”

启动代码不能假设：

- 时钟已经正确。
- SRAM 已经清零。
- 中断已经关闭。
- FPU 已经开启。
- Cache 已经失效。
- Bootloader 已经恢复所有寄存器。

应显式设置关键状态。

### 原则二：启动代码必须可审计

建议明确划分：

```
startup_asm.S       汇编入口和最早期 CPU 状态
startup.c           向量表、运行时初始化
system_xxx.c        芯片级时钟和电源初始化
memory.ld           内存布局
fault.c             异常诊断
boot_jump.c         Bootloader 跳转
```

### 原则三：不要在早期启动阶段依赖复杂全局状态

错误示例：

```
static ClockConfig g_config = load_config_from_flash();
```

因为此时：

- `.data` 可能还未初始化。
- Flash 控制器可能未配置。
- C++ 构造函数可能还未执行。

### 原则四：默认中断不能静默丢失

默认 Handler 至少应该：

- 停机。
- 记录异常号。
- 记录堆栈帧。
- 触发看门狗复位或进入故障模式。
- 保留调试入口。

## 8.2 启动选型决策矩阵

|需求|推荐方案|
|---|---|
|最小代码尺寸|汇编入口 + C 运行时|
|最大可维护性|C 向量表 + 少量汇编 Fault 入口|
|支持 C++|`__libc_init_array()`|
|支持多应用|每个镜像独立向量表|
|支持 OTA|Bootloader 验证 + VTOR 重定位|
|需要故障追踪|汇编捕获栈帧 + C 解析|
|需要安全隔离|MPU/TrustZone 启动阶段配置|
|需要极短启动|延迟外设初始化 + 分阶段启动|

## 8.3 工业级编码规范

- 所有内存映射寄存器使用 `volatile`。
- 所有启动状态寄存器修改后，根据手册插入 `DSB/ISB`。
- 不使用未定义的魔数，统一定义寄存器位。
- 不在启动阶段调用依赖堆、锁或复杂初始化的函数。
- 入口函数使用明确的 `noreturn` 语义。
- 对链接脚本导出的符号使用 `extern uint8_t symbol;`。
- 对向量表使用 `used` 和 `KEEP`。
- 对应用镜像跳转执行完整状态清理。
- 对启动失败路径设置明确的故障码。
- 启动代码必须纳入静态检查和单元测试之外的板级测试。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：`.data` 没有拷贝

### 错误代码

```
int g_mode = 3;

int main(void)
{
    if (g_mode == 3) {
        start();
    }
}
```

启动代码未执行 `.data` 初始化。

### 根因

`g_mode` 的初始值在 Flash 中，但运行地址在 SRAM。CPU 直接访问 SRAM 时，得到复位后的未知值。

### 正确实现

```
runtime_memory_init();
SystemInit();
main();
```

或根据平台要求：

```
SystemInit();
runtime_memory_init();
main();
```

关键是必须明确所有函数的依赖关系。

### 风险影响

- 全局配置错误。
- 状态机进入错误分支。
- 故障具有随机性。
- Debug 版本正常，Release 版本异常。

---

## 9.2 错误二：`.bss` 未清零

### 错误代码

```
static uint8_t tx_busy;

void tx_start(void)
{
    if (tx_busy != 0U) {
        return;
    }

    tx_busy = 1U;
}
```

### 根因

C 语言要求静态存储期对象默认初始化为零，但裸机启动代码未兑现这一运行时契约。

### 正确实现

```
static void zero_bss_section(void)
{
    uint32_t *p = &__bss_start__;
    uint32_t *e = &__bss_end__;

    while (p < e) {
        *p++ = 0U;
    }
}
```

### 风险影响

- 全局状态机状态错误。
- RTOS 控制块损坏。
- 互斥锁初始状态异常。
- 故障表现与上电 SRAM 残留数据有关。

---

## 9.3 错误三：Bootloader 跳转前未关闭中断

### 错误代码

```
SCB->VTOR = app_base;
jump_to_app();
```

### 根因

Bootloader 中可能存在：

- Pending 中断。
- SysTick。
- DMA 中断。
- 外设中断使能位。
- NVIC 优先级状态。

跳转到应用后，旧中断可能立即进入错误 ISR。

### 正确实现

```
static void disable_all_interrupts(void)
{
    __disable_irq();

    SysTick->CTRL = 0U;
    SysTick->LOAD = 0U;
    SysTick->VAL  = 0U;

    for (uint32_t i = 0U; i < 8U; i++) {
        NVIC->ICER[i] = 0xFFFFFFFFUL;
        NVIC->ICPR[i] = 0xFFFFFFFFUL;
    }

    __DSB();
    __ISB();
}
```

### 风险影响

- 应用刚启动就进入异常。
- 中断处理函数使用错误的设备状态。
- 偶现死机，难以复现。

---

## 9.4 错误四：VTOR 未对齐

### 错误代码

```
SCB->VTOR = 0x08008100U;
```

### 根因

向量表必须满足实现规定的对齐要求。对齐粒度与向量表大小相关，具体以 ARM 内核实现和芯片手册为准。

### 正确实现

链接脚本中约束：

```
.isr_vector ALIGN(512) :
{
    KEEP(*(.isr_vector))
} > FLASH
```

代码中检查：

```
#define VECTOR_ALIGNMENT 512U

if ((app_base % VECTOR_ALIGNMENT) != 0U) {
    fault_stop();
}
```

### 风险影响

- 中断进入错误地址。
- HardFault。
- 仅在某些中断触发时失败。

---

## 9.5 错误五：没有调用 `__libc_init_array`

### 错误代码

```
int main(void)
{
    return app_main();
}
```

启动代码直接调用 `main()`，未初始化 C++ 运行时。

### 根因

全局 C++ 对象构造函数通常位于 `.init_array`，需要运行库显式调用。

### 正确实现

```
bl __libc_init_array
bl main
```

### 风险影响

- 全局对象构造函数未执行。
- `std::array`、静态锁、驱动对象状态异常。
- C++ 工程可能启动后立即崩溃。

---

## 9.6 错误六：高频时钟切换前未配置 Flash Latency

### 错误代码

```
switch_to_168mhz();
flash_set_wait_states(5);
```

### 根因

CPU 已经以高频访问 Flash，但 Flash 控制器仍处于低频等待周期配置。

### 正确实现

```
flash_set_wait_states(5);
power_set_voltage_scale_high();
pll_configure();
pll_wait_lock();
switch_to_168mhz();
```

### 风险影响

- 取指错误。
- 随机 HardFault。
- 仅在高温、低压或特定芯片批次下出现。

---

# 10. 多机制组合使用方案

## 10.1 启动分层架构

推荐架构：

```
Level 0：硬件复位
    ├── 硬件加载 MSP/PC
    └── 进入 Reset_Handler

Level 1：CPU 早期初始化
    ├── 关闭中断
    ├── 初始化栈
    ├── 设置 FPU
    └── 建立异常捕获能力

Level 2：平台初始化
    ├── 电源
    ├── Flash 等待周期
    ├── 时钟
    ├── Cache/MPU
    └── 芯片外设复位

Level 3：C/C++ 运行时
    ├── .data
    ├── .bss
    ├── 构造函数
    └── 运行库初始化

Level 4：系统软件
    ├── 日志
    ├── 看门狗
    ├── RTOS
    └── 驱动框架

Level 5：业务应用
```

## 10.2 完整启动框架

```
#include <stdint.h>

extern void SystemInit(void);
extern void __libc_init_array(void);
extern int main(void);

static void runtime_memory_init(void);
static int platform_validate(void);
static void fault_stop(void);

void Reset_Handler(void)
{
    __disable_irq();

    runtime_memory_init();

    if (platform_validate() != 0) {
        fault_stop();
    }

    SystemInit();

    /*
     * C++ 工程必须保留。
     * 纯 C 工程是否调用取决于工具链和运行库配置。
     */
    __libc_init_array();

    (void)main();

    fault_stop();
}

static int platform_validate(void)
{
    /*
     * 可检查：
     * - 栈边界
     * - Flash 设备 ID
     * - 时钟源状态
     * - Boot 原因
     * - 镜像完整性
     */
    return 0;
}

static void fault_stop(void)
{
    __disable_irq();

    while (1) {
        __asm volatile ("wfi");
    }
}
```

## 10.3 启动状态机

复杂产品不建议把全部逻辑写成线性阻塞代码，可以使用状态机：

```
typedef enum {
    BOOT_STAGE_CPU = 0,
    BOOT_STAGE_MEMORY,
    BOOT_STAGE_CLOCK,
    BOOT_STAGE_SECURITY,
    BOOT_STAGE_APPLICATION,
    BOOT_STAGE_FAILED
} boot_stage_t;

static boot_stage_t g_boot_stage;

int boot_sequence(void)
{
    g_boot_stage = BOOT_STAGE_CPU;

    g_boot_stage = BOOT_STAGE_MEMORY;
    runtime_memory_init();

    g_boot_stage = BOOT_STAGE_CLOCK;
    if (clock_init() != 0) {
        g_boot_stage = BOOT_STAGE_FAILED;
        return -1;
    }

    g_boot_stage = BOOT_STAGE_SECURITY;
    if (image_verify() != 0) {
        g_boot_stage = BOOT_STAGE_FAILED;
        return -2;
    }

    g_boot_stage = BOOT_STAGE_APPLICATION;
    return 0;
}
```

这种设计便于：

- 记录启动失败阶段。
- 在看门狗复位后分析原因。
- 支持低功耗唤醒。
- 支持分阶段、非阻塞初始化。

---

# 11. 工业级实际案例分析

## 11.1 案例一：Bootloader 跳转到应用

### 需求

- Bootloader 位于 `0x08000000`。
- 应用位于 `0x08020000`。
- 应用拥有独立向量表。
- 跳转前关闭 Bootloader 中断和 SysTick。

### 架构

```
0x08000000 ── Bootloader
0x08020000 ── Application Vector Table
0x08020400 ── Application Code
```

### 核心代码

```
#include <stdint.h>

typedef void (*app_entry_t)(void);

#define APP_BASE       0x08020000UL
#define SRAM_START     0x20000000UL
#define SRAM_END       0x20040000UL
#define FLASH_START    0x08000000UL
#define FLASH_END      0x08100000UL

static int app_is_valid(uint32_t base)
{
    uint32_t sp = *(volatile uint32_t *)(base + 0U);
    uint32_t pc = *(volatile uint32_t *)(base + 4U);

    if ((sp < SRAM_START) || (sp >= SRAM_END)) {
        return 0;
    }

    if ((pc & 1U) == 0U) {
        return 0;
    }

    if (((pc & ~1UL) < FLASH_START) ||
        ((pc & ~1UL) >= FLASH_END)) {
        return 0;
    }

    return 1;
}

static void jump_to_application(uint32_t base)
{
    uint32_t app_sp;
    uint32_t app_pc;
    app_entry_t app_entry;

    if (!app_is_valid(base)) {
        return;
    }

    __disable_irq();

    SysTick->CTRL = 0U;
    SysTick->LOAD = 0U;
    SysTick->VAL  = 0U;

    for (uint32_t i = 0U; i < 8U; i++) {
        NVIC->ICER[i] = 0xFFFFFFFFUL;
        NVIC->ICPR[i] = 0xFFFFFFFFUL;
    }

    app_sp = *(volatile uint32_t *)(base + 0U);
    app_pc = *(volatile uint32_t *)(base + 4U);

    SCB->VTOR = base;
    __DSB();
    __ISB();

    __set_MSP(app_sp);
    __DSB();
    __ISB();

    app_entry = (app_entry_t)app_pc;
    app_entry();

    while (1) {
    }
}
```

### 设计要点

- 必须验证 MSP。
- 必须验证 Reset 向量的 Thumb 位。
- 必须清理 NVIC Pending 位。
- 必须停止 SysTick。
- 对使用 Cache 的 M7，还要处理 Cache 和分支预测器。
- 如果 Bootloader 和应用使用不同的时钟状态，最好在跳转前恢复为应用约定状态，或者让应用显式重新配置。

---

## 11.2 案例二：Cortex-M7 + 外部 SDRAM + DMA

### 需求

- M7 使用 I-Cache/D-Cache。
- 图像缓冲区位于外部 SDRAM。
- DMA 与 CPU 共享帧缓冲。
- 启动阶段初始化 MPU 和 Cache。

### 启动顺序

```
复位
 ↓
初始化时钟和 Flash
 ↓
初始化 FMC/外部 SDRAM
 ↓
配置 MPU
 ↓
清理并失效 Cache
 ↓
开启 I-Cache/D-Cache
 ↓
初始化 .data/.bss
 ↓
启动应用
```

### DMA 缓冲区布局

```
__attribute__((section(".dma_buffer"), aligned(32)))
uint8_t camera_frame[320U * 240U * 2U];
```

链接脚本：

```
.dma_buffer (NOLOAD) : ALIGN(32)
{
    . = ALIGN(32);
    *(.dma_buffer)
    . = ALIGN(32);
} > SDRAM
```

### Cache 一致性代码

```
void dma_prepare_rx(void *buffer, uint32_t size)
{
    uintptr_t start = (uintptr_t)buffer & ~31UL;
    uintptr_t end   = ((uintptr_t)buffer + size + 31UL) & ~31UL;

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                  (int32_t)(end - start));
}

void dma_prepare_tx(void *buffer, uint32_t size)
{
    uintptr_t start = (uintptr_t)buffer & ~31UL;
    uintptr_t end   = ((uintptr_t)buffer + size + 31UL) & ~31UL;

    SCB_CleanDCache_by_Addr((uint32_t *)start,
                            (int32_t)(end - start));
}
```

### 设计要点

- M7 D-Cache 常见 Cache Line 为 32 字节，但必须以芯片实现为准。
- DMA 缓冲区必须按 Cache Line 对齐。
- RX DMA 前需要失效 Cache。
- TX DMA 前需要清理 Cache。
- 外部 SDRAM 初始化之前，不能访问位于 SDRAM 的 `.data` 或 `.bss`。
- 如果链接脚本把普通全局变量放到了外部 RAM，启动顺序必须重新设计。

---

## 11.3 案例三：带看门狗和故障记录的量产设备

### 需求

- 启动失败后自动重启。
- 保留上次 HardFault 的 PC/LR。
- 在 Bootloader 中读取故障信息并上报。
- 不能依赖文件系统。

### 故障记录结构

```
#include <stdint.h>

#define FAULT_MAGIC 0x4641554CUL

typedef struct {
    uint32_t magic;
    uint32_t reset_reason;
    uint32_t pc;
    uint32_t lr;
    uint32_t cfsr;
    uint32_t hfsr;
    uint32_t bfar;
    uint32_t mmfar;
    uint32_t checksum;
} fault_record_t;

__attribute__((section(".noinit")))
volatile fault_record_t g_fault_record;
```

链接脚本：

```
.noinit (NOLOAD) :
{
    . = ALIGN(4);
    *(.noinit)
    . = ALIGN(4);
} > RAM
```

### 记录代码

```
static uint32_t fault_checksum(const fault_record_t *record)
{
    const uint32_t *p = (const uint32_t *)record;
    uint32_t sum = 0U;

    for (uint32_t i = 0U;
         i < (sizeof(fault_record_t) / sizeof(uint32_t)) - 1U;
         i++) {
        sum ^= p[i];
    }

    return sum;
}

__attribute__((noreturn))
void record_hardfault(exception_stack_frame_t *frame)
{
    g_fault_record.magic = FAULT_MAGIC;
    g_fault_record.pc    = frame->pc;
    g_fault_record.lr    = frame->lr;
    g_fault_record.cfsr  = SCB->CFSR;
    g_fault_record.hfsr  = SCB->HFSR;
    g_fault_record.bfar  = SCB->BFAR;
    g_fault_record.mmfar = SCB->MMFAR;

    g_fault_record.checksum = fault_checksum(&g_fault_record);

    system_reset();

    while (1) {
    }
}
```

### 设计要点

- `.noinit` 不应被启动代码清零。
- 必须使用 Magic + Checksum 判断记录是否有效。
- 看门狗复位后要区分：
    - 正常软件复位。
    - 看门狗复位。
    - Brown-out。
    - 外部复位。
    - HardFault 后软件触发复位。
- 记录 PC 后，需要使用 ELF、`.map` 或 `addr2line` 解析源码位置。

---

# 12. 高频问题深度答疑

## 问题一：为什么向量表第一个地址不是函数地址？

因为 Cortex-M 复位时需要先建立主堆栈。硬件直接把第一个表项加载到 MSP：

```
MSP = vector_table[0]
PC  = vector_table[1]
```

如果第一个表项不是有效 SRAM 地址，CPU 可能在异常压栈时立即失败。

---

## 问题二：为什么函数地址必须是奇数？

Cortex-M 执行 Thumb 指令，函数指针最低位用于表示 Thumb 状态。向量表中的地址必须满足：

```
(reset_handler_address & 1U) == 1U
```

实际取指地址会自动忽略最低位，但该位不能被清零。

---

## 问题三：为什么 `main()` 返回后不能直接返回？

`Reset_Handler` 是由硬件进入的，不存在正常的 C 调用者。其 LR 不具有可返回的合法地址。

错误做法：

```
bl main
bx lr
```

正确做法：

```
bl main
b .
```

或者触发系统复位。

---

## 问题四：`.data` 和 `.bss` 为什么处理方式不同？

`.data` 需要保留非零初始值，因此：

```
Flash 保存初始镜像
SRAM 保存运行副本
启动时执行复制
```

`.bss` 的语言语义是零初始化，不需要把一大片零数据存入 Flash，因此：

```
只分配 SRAM
启动时清零
```

这可以显著节省 Flash 镜像空间。

---

## 问题五：`SystemInit()` 应该在 `.data/.bss` 初始化前还是后？

没有适用于所有平台的唯一顺序，取决于 `SystemInit()` 的实现。

推荐原则：

- `SystemInit()` 不应依赖全局变量。
- 早期时钟、Flash、电源初始化可以在运行时内存初始化之前完成。
- 如果时钟初始化代码依赖 `.data` 中的配置，则必须先初始化 `.data`。
- 量产项目应通过代码约束消除这种隐式依赖。

一种通用顺序：

```
关闭中断
 ↓
设置 MSP
 ↓
基础 CPU 状态
 ↓
SystemInit
 ↓
.data/.bss
 ↓
C/C++ 运行时
 ↓
main
```

另一种适合纯软件平台的顺序：

```
关闭中断
 ↓
设置 MSP
 ↓
.data/.bss
 ↓
SystemInit
 ↓
C/C++ 运行时
 ↓
main
```

关键不是机械遵循模板，而是建立依赖关系。

---

## 问题六：Bootloader 跳转到应用时，为什么还要重新设置 MSP？

硬件复位时会自动加载 MSP，但 Bootloader 跳转不是硬件复位。此时 MSP 仍然可能指向 Bootloader 的栈。

因此必须执行：

```
__set_MSP(*(uint32_t *)app_base);
```

否则应用函数调用和异常压栈会使用错误的栈区域。

---

## 问题七：是否可以完全使用 C 编写启动代码？

在 Cortex-M3 及以上，通常可以使用 C 编写大部分启动代码，但仍需注意：

- 进入 C 代码前，栈必须有效。
- 编译器生成的函数可能依赖栈。
- 入口函数可能需要 `naked` 或汇编包装。
- 编译器运行库自身可能访问 `.data`/`.bss`。
- Cortex-M0 某些实现缺少 `VTOR`，不能直接复制 M3 方案。

工程上推荐：

```
少量汇编负责最早期入口和异常栈帧捕获
C 负责向量表、内存初始化、平台初始化和故障逻辑
```

---

# 13. 课程核心总结

## 13.1 核心要点

1. Cortex-M 复位启动本质是：

```
向量表 → MSP → PC → Reset_Handler
```

2. 启动代码必须建立完整的 C 运行环境：

```
.data 拷贝
.bss 清零
C/C++ 运行库初始化
```

3. 向量表必须满足：

- 正确位置。
- 正确对齐。
- 正确 Thumb 地址。
- 正确异常顺序。
- 链接器不能回收。

4. Bootloader 跳转必须处理：

- 中断关闭。
- SysTick 停止。
- NVIC Pending 清除。
- `VTOR` 重定位。
- MSP 重设。
- Cache/MPU 状态。
- 镜像合法性验证。

5. Cortex-M7/M33 启动复杂度主要来自：

- Cache。
- MPU。
- 外部存储器。
- DMA 一致性。
- 安全域切换。
- 多镜像启动。

## 13.2 性能排序

以启动总时间为目标：

```
镜像校验/签名验证
    >
外部晶振和 PLL 启动
    >
外部 SDRAM 初始化
    >
大块 .bss 清零
    >
大块 .data 拷贝
    >
Cache/MPU 配置
    >
VTOR 写入和内存屏障
```

## 13.3 通用选型结论

|项目|推荐|
|---|---|
|普通 MCU 裸机|CMSIS + 厂商启动模板|
|中大型裸机工程|C 向量表 + 少量汇编|
|RTOS|标准异常向量 + PendSV/SysTick 明确分层|
|Bootloader|独立向量表 + 严格跳转清理|
|M7|显式设计 Cache、MPU、外部 RAM 顺序|
|M33|将安全启动和非安全启动分离|
|C++|必须检查 `__libc_init_array()`|
|量产设备|故障现场保存 + 看门狗 + 启动阶段码|

---

# 14. 快速参考速查表

## 14.1 启动流程速查

```
硬件复位
 → 读取初始 MSP
 → 读取 Reset_Handler
 → 关闭中断
 → 初始化 CPU 状态
 → 配置 FPU/MPU/Cache
 → 配置时钟
 → 拷贝 .data
 → 清零 .bss
 → __libc_init_array()
 → main()
 → 不返回
```

## 14.2 关键寄存器

|寄存器|作用|
|---|---|
|`MSP`|主堆栈指针|
|`PSP`|进程堆栈指针|
|`SCB->VTOR`|向量表基地址|
|`SCB->CPACR`|FPU 访问权限|
|`SCB->CFSR`|可配置故障状态|
|`SCB->HFSR`|HardFault 状态|
|`SCB->BFAR`|总线错误地址|
|`SCB->MMFAR`|内存管理错误地址|
|`SCB->ICSR`|中断控制与状态|
|`SysTick->CTRL`|SysTick 控制状态|

## 14.3 启动代码检查表

|检查项|结果|
|---|---|
|向量表是否位于镜像首部|□|
|向量表是否使用 `KEEP`|□|
|初始 MSP 是否在有效 SRAM|□|
|Reset Handler 是否为 Thumb 地址|□|
|`.data` 是否拷贝|□|
|`.bss` 是否清零|□|
|C++ 是否调用 `__libc_init_array`|□|
|FPU 是否在使用前启用|□|
|Flash Latency 是否先于升频设置|□|
|VTOR 是否满足对齐要求|□|
|默认中断是否可诊断|□|
|Bootloader 是否清除 Pending 中断|□|
|`main()` 返回后是否安全停机|□|

---

# 15. 学习效果自检

完成本课后，应能够独立回答：

- [ ]  Cortex-M 复位时硬件从向量表读取了哪些内容？
- [ ]  为什么向量表第 0 项是栈地址？
- [ ]  为什么函数地址最低位必须是 `1`？
- [ ]  `.data` 的 LMA 和 VMA 分别是什么？
- [ ]  `.bss` 为什么不需要占用 Flash 镜像空间？
- [ ]  启动代码为什么需要调用 `__libc_init_array()`？
- [ ]  `VTOR` 重定位后为什么需要 `DSB/ISB`？
- [ ]  Bootloader 跳转前为什么必须清除 NVIC Pending 位？
- [ ]  M7 启动时 Cache、MPU、外部 SDRAM 的顺序如何确定？
- [ ]  如何从 HardFault 的自动压栈内容中恢复故障 PC？
- [ ]  如何判断应用向量表中的 MSP 和 Reset Handler 是否合法？
- [ ]  为什么启动阶段不应依赖复杂的全局对象和动态内存？

进阶能力检查：

- [ ]  能从 `.map` 文件定位 `.data/.bss/.isr_vector`。
- [ ]  能使用 `objdump -h` 检查段布局。
- [ ]  能使用 `readelf -s` 查看链接脚本导出的符号。
- [ ]  能使用 DWT 测量 `.bss` 清零时间。
- [ ]  能构造一次非法访问并解析 `CFSR/HFSR/PC/LR`。
- [ ]  能独立编写 Bootloader 到 Application 的安全跳转函数。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：分析现有启动文件

目标：

- 找出向量表。
- 找出 `Reset_Handler`。
- 找出 `.data/.bss` 初始化位置。
- 找出 `SystemInit()` 调用位置。
- 找出 C++ 运行时初始化位置。

工具：

```
arm-none-eabi-objdump -h firmware.elf
arm-none-eabi-objdump -d firmware.elf
arm-none-eabi-readelf -s firmware.elf
```

### 任务二：手写最小启动代码

要求：

- 自定义向量表。
- 实现 `Reset_Handler`。
- 实现 `.data` 拷贝。
- 实现 `.bss` 清零。
- 调用 `main()`。
- 默认中断进入死循环。

### 任务三：增加 HardFault 诊断

要求记录：

```
R0-R3
R12
LR
PC
xPSR
CFSR
HFSR
BFAR
MMFAR
```

并通过串口输出。

### 任务四：实现 Bootloader 跳转

要求：

- 校验 MSP。
- 校验 Reset Handler。
- 停止 SysTick。
- 清空 NVIC Enable/Pending。
- 设置 VTOR。
- 重设 MSP。
- 跳转应用。

### 任务五：实现启动性能统计

使用 DWT：

```
static void dwt_enable(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t dwt_get_cycles(void)
{
    return DWT->CYCCNT;
}
```

测量：

```
uint32_t start;
uint32_t end;

dwt_enable();

start = dwt_get_cycles();
runtime_memory_init();
end = dwt_get_cycles();

printf("runtime init cycles = %lu\n",
       (unsigned long)(end - start));
```

换算公式：

```
时间 = 周期数 / CPU 频率
```

### 任务六：设计 M7 Cache/DMA 启动方案

要求：

- 配置 DMA 缓冲区段。
- 设置 32 字节或芯片要求的对齐。
- 配置 MPU 属性。
- 实现 DMA 前后的 Cache Clean/Invalidate。
- 验证图像数据一致性。

## 16.2 性能测试方法

建议建立以下测试矩阵：

|测试项|测试方法|
|---|---|
|启动总时间|GPIO 翻转 + 示波器|
|`.data` 拷贝时间|DWT CYCCNT|
|`.bss` 清零时间|DWT CYCCNT|
|PLL 锁定时间|GPIO 时间戳|
|Bootloader 校验时间|分阶段记录|
|异常响应时间|触发非法访问后测量|
|看门狗恢复时间|记录复位原因和 GPIO|
|Cache 一致性|DMA 数据校验|

## 16.3 进阶学习方向

### 方向一：Cortex-M 异常与调度

- 异常优先级。
- Tail-chaining。
- Late arrival。
- `EXC_RETURN`。
- PendSV 上下文切换。
- SVC 系统调用。

### 方向二：RTOS 启动集成

- SysTick/PendSV 接口。
- 启动第一个任务。
- MSP/PSP 切换。
- 中断优先级分组。
- FPU 上下文保存。

### 方向三：可靠启动

- 镜像 CRC。
- 数字签名。
- 版本回滚保护。
- 双 Bank。
- 看门狗窗口。
- 启动状态机。

### 方向四：Cortex-M7 高性能启动

- I-Cache/D-Cache。
- MPU 内存属性。
- TCM。
- 外部 SDRAM。
- DMA 一致性。
- 双核同步。

### 方向五：Cortex-M33 安全启动

- TrustZone。
- Secure/Non-secure VTOR。
- SAU/IDAU。
- 安全栈和非安全栈。
- CMSE。
- 安全异常入口。

## 本课最终工程结论

**启动代码不是模板文件，而是整个嵌入式系统运行时契约的建立过程。**

一个工业级 Cortex-M 启动实现至少必须保证：

```
CPU 状态可控
内存状态确定
时钟状态正确
异常入口有效
运行库初始化完整
Bootloader 跳转可验证
故障现场可追踪
启动性能可量化
```

只要其中任意一项依赖隐式默认状态，系统就可能出现“偶现启动失败、随机 HardFault、只在量产环境出现”的高成本问题。