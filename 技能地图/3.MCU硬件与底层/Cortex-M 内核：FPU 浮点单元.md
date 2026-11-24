
> 适用对象：具备 5 年以上 MCU/RTOS 开发经验，已熟悉 Cortex-M 异常模型、编译器、链接脚本、RTOS 调度与 DMA 的嵌入式工程师。  
> 课程范围：重点覆盖 **Cortex-M4F、Cortex-M7、Cortex-M33/M35P 可选 FPU**，以 Arm FPv4-SP/FPv5-SP 为主。  
> 说明：多数 Cortex-M FPU 为**单精度浮点 FPU**，不应将其与支持双精度硬件运算的 Cortex-A/R 或桌面处理器混淆。

---

# 1. 学习目标

## 1.1 理解

完成本课后，应能够：

- 理解 Cortex-M FPU 的架构定位、寄存器模型和异常上下文机制。
    
- 理解：
    
    - S0~S31 单精度寄存器；
    - D0~D15 双字视图；
    - FPSCR；
    - CPACR；
    - FPCCR；
    - 浮点上下文保存与恢复；
    - Lazy Stacking 的工作原理。
- 理解 `-mfloat-abi=soft`、`softfp`、`hard` 的 ABI 差异。
    
- 理解 RTOS 任务使用 FPU 时的上下文切换成本。
    
- 理解浮点运算中的 NaN、Inf、非规格化数、舍入误差和异常状态。
    

## 1.2 掌握

能够：

- 正确启用 Cortex-M FPU。
- 使用编译器参数生成匹配目标芯片的浮点指令。
- 在启动文件、RTOS、异常处理器和任务代码之间正确配置 FPU。
- 判断某段 C/C++ 代码是否真的使用了硬件 FPU。
- 测量浮点运算周期、异常延迟和上下文切换开销。
- 正确处理浮点寄存器、栈帧和任务切换。

## 1.3 精通

能够深入分析：

- `VMUL.F32`、`VMLA.F32`、`VDIV.F32`、`VSQRT.F32` 等指令的流水线代价。
- FPU 指令触发 `NOCP`、`UNDEFINSTR` 等 Fault 的根因。
- Lazy Stacking 对中断延迟、栈峰值和实时性的影响。
- 浮点 ABI 不一致导致的链接失败、参数传递错误和性能退化。
- RTOS 中浮点任务与非浮点任务混合调度时的上下文管理策略。
- DMA/ISR/任务共享浮点数据时的数据一致性与实时性问题。

## 1.4 能够设计

能够设计：

- 面向电机控制、传感器融合、音频处理和控制算法的 FPU 使用架构。
- 具有明确 WCET、栈预算和异常处理策略的浮点实时系统。
- 混合定点/浮点计算管线。
- 支持浮点任务隔离、上下文切换和故障诊断的 RTOS 方案。
- 经过性能、精度、资源、安全性验证的工业级浮点模块。

---

# 2. 前置要求

## 2.1 知识要求

- ARMv7-M 或 ARMv8-M 异常模型。
- MSP、PSP、CONTROL、PRIMASK、BASEPRI、FAULTMASK。
- Cortex-M 自动异常入栈格式。
- C 语言指针、结构体、位域和编译器扩展。
- ELF、链接脚本、启动文件和 map 文件。
- RTOS 任务切换、临界区和中断优先级。
- 基本 IEEE-754 单精度浮点知识。
- DMA、Cache、内存屏障和 MPU 基础。

## 2.2 技能要求

- 能使用 GCC/Clang/Arm Compiler 编译 Cortex-M 工程。
- 能查看反汇编：

```
arm-none-eabi-objdump -d firmware.elf
```

- 能使用 DWT CYCCNT、逻辑分析仪或 ETM 进行性能测量。
- 能分析 HardFault/BusFault/UsageFault 堆栈。
- 能阅读 CMSIS-Core 头文件和 Cortex-M 启动代码。
- 能修改链接脚本配置栈、堆和特定内存区域。

---

# 3. 技术概述

## 3.1 Cortex-M FPU 的定义

Cortex-M FPU 是可选的**单精度浮点硬件执行单元**，用于加速：

- 加减乘除；
- 乘加；
- 开方；
- 浮点比较；
- 浮点转换；
- 浮点寄存器搬运；
- 部分浮点数据处理操作。

常见指令包括：

```
VMOV.F32
VADD.F32
VSUB.F32
VMUL.F32
VMLA.F32
VMLS.F32
VDIV.F32
VSQRT.F32
VCMP.F32
VCVT.F32.S32
```

## 3.2 典型 Cortex-M FPU 分类

|内核|FPU|典型特性|常见产品|
|---|---|---|---|
|Cortex-M4|可选 FPv4-SP-D16|单精度，16 个双精度寄存器视图|STM32F4、NXP Kinetis K|
|Cortex-M7|可选 FPv5-SP-D16|单精度，高性能流水线，通常配合 Cache|STM32F7、NXP i.MX RT|
|Cortex-M33|可选 FPv5-SP-D16|ARMv8-M，TrustZone 可选|STM32U5、LPC55Sxx|
|Cortex-M35P|可选 FPv5-SP-D16|增强安全特性|安全 MCU|
|Cortex-M55|可选 FPv5-SP-D16，另有 Helium|更强 DSP/向量能力|新一代边缘 AI MCU|

本课重点是 **D16 单精度 FPU**。D16 表示：

- 物理上有 `S0~S31` 共 32 个 32 位单精度寄存器；
- 也可视为 `D0~D15` 共 16 个 64 位寄存器；
- 并不代表具备完整硬件双精度性能；
- `double` 运算在多数 Cortex-M FPU 上仍需要软件库支持。

## 3.3 FPU 在系统架构中的位置

```
应用算法
   │
   ├── 控制算法 / 滤波 / 姿态解算
   ├── DSP / 音频 / 传感器融合
   └── 数学库 / 浮点格式转换
          │
          ▼
编译器浮点代码生成
   │
   ├── 软浮点库调用
   ├── 硬件 FPU 指令
   └── SIMD/DSP 指令
          │
          ▼
Cortex-M 内核
   ├── 整数流水线
   ├── FPU
   ├── 异常系统
   └── MPU/Cache/内存系统
          │
          ▼
RTOS / 中断 / DMA / 外设
```

---

# 4. 核心特性横向对比

## 4.1 浮点 ABI 对比

|配置|浮点运算实现|浮点参数传递|二进制兼容性|性能|适用场景|
|---|---|---|---|---|---|
|`-mfloat-abi=soft`|软件库|整数寄存器/栈|兼容无 FPU 目标|最低|通用库、无 FPU MCU|
|`-mfloat-abi=softfp`|硬件 FPU 可用|遵循软件 ABI|与 soft ABI 兼容性较好|高|需要兼容已有库|
|`-mfloat-abi=hard`|硬件 FPU|VFP 寄存器|需要全工程 ABI 一致|高|新建 FPU 工程|
|定点 Q 格式|无 FPU|整数 ABI|高|在某些场景更稳定|强实时、固定量程|
|浮点 + CMSIS-DSP|FPU 指令/优化实现|取决于工程 ABI|需统一编译|很高|DSP、滤波、FFT|

重要编译选项示例：

```
-mcpu=cortex-m7
-mthumb
-mfpu=fpv5-sp-d16
-mfloat-abi=hard
```

Cortex-M4 常见配置：

```
-mcpu=cortex-m4
-mfpu=fpv4-sp-d16
-mfloat-abi=hard
```

## 4.2 浮点数据类型对比

|类型|位宽|Cortex-M FPU 硬件支持|典型问题|
|---|---|---|---|
|`float`|32|通常硬件支持|精度约 7 位十进制有效数字|
|`double`|64|多数 Cortex-M FPU 不原生支持|由软件库实现，性能显著下降|
|`long double`|通常 64 或 128|通常无硬件支持|资源消耗更高|
|`q15_t`|16|整数/DSP 指令支持|需要手动缩放和溢出管理|
|`q31_t`|32|整数/DSP 指令支持|动态范围和精度需设计|

## 4.3 浮点上下文策略对比

|策略|机制|中断首进延迟|任务栈占用|适用性|
|---|---|---|---|---|
|禁用 FPU|不使用浮点指令|最低|0|定点系统|
|eager stacking|每次异常都保存 FPU 上下文|稳定但偏高|最高|强确定性系统|
|lazy stacking|首次使用 FPU 时保存扩展帧|通常较低|峰值不可忽略|通用 RTOS|
|RTOS 按任务保存|仅浮点任务保存 FPU|非 FPU 任务开销低|由任务设计决定|混合任务系统|
|全局共享 FPU|任务间不切换 FPU|切换快|低|仅适合单线程或受控场景|

---

# 5. 底层原理与功能特性深度解析

## 5.1 FPU 寄存器组织

### 5.1.1 通用浮点寄存器

```
S0  ~ S31 : 32 个 32 位单精度寄存器
D0  ~ D15 : 16 个 64 位寄存器视图
```

映射关系：

```
D0  = {S1, S0}
D1  = {S3, S2}
...
D15 = {S31, S30}
```

在 D16 配置下，一般不存在 `S32~S63` 或 `D16~D31`。

### 5.1.2 FPSCR

`FPSCR` 保存浮点控制和状态信息，主要包括：

- RMode：舍入模式；
- FZ：Flush-to-Zero；
- DN：Default NaN；
- QC：饱和状态标记；
- N、Z、C、V：比较结果标志；
- 浮点异常累计状态。

注意：很多 Cortex-M 默认不会因为 IEEE-754 异常直接进入 Fault。异常通常通过状态位记录，需要软件读取和处理。

## 5.2 启用 FPU：CPACR

Cortex-M3/M4/M7/M33 等内核通过 `SCB->CPACR` 控制 CP10/CP11 访问权限。

```
#include "cmsis_gcc.h"
#include "core_cm7.h"

static int fpu_enable(void)
{
    /*
     * CP10/CP11 = 0b11：Full Access
     * CP10 位于 20~21
     * CP11 位于 22~23
     */
    SCB->CPACR |= (3UL << 20) | (3UL << 22);

    /*
     * 确保 CPACR 写入在后续 FPU 指令执行前生效。
     */
    __DSB();
    __ISB();

    /*
     * 可选：设置浮点控制策略。
     * FZ=1：将非规格化数刷新为 0，降低极端数据下的执行代价。
     */
    __set_FPSCR(__get_FPSCR() | (1UL << 24));

    return 0;
}
```

更稳健的写法是显式清除后设置：

```
static int fpu_enable_strict(void)
{
    uint32_t cpacr = SCB->CPACR;

    cpacr &= ~((3UL << 20) | (3UL << 22));
    cpacr |=  ((3UL << 20) | (3UL << 22));

    SCB->CPACR = cpacr;

    __DSB();
    __ISB();

    return 0;
}
```

### 设计要点

- 必须在任何 FPU 指令执行前启用。
- 启用动作通常放在 `SystemInit()` 或启动文件中。
- 如果使用 RTOS，应在 RTOS 启动前完成。
- 某些安全 MCU 中，非安全世界访问 FPU 还受到安全状态、SAU/IDAU 或实现定义策略影响。
- 不要只修改 `CPACR` 而忽略 `DSB/ISB`。

## 5.3 FPU 未启用时的 Fault

如果 CPU 执行 FPU 指令，但 CP10/CP11 未授权，通常触发 UsageFault，并设置 `NOCP`。

示例 Fault 解析：

```
#define CFSR_NOCP_Msk       (1UL << 19)
#define CFSR_UNDEFINSTR_Msk (1UL << 16)

static void fault_decode(void)
{
    uint32_t cfsr = SCB->CFSR;

    if (cfsr & CFSR_NOCP_Msk) {
        /* 协处理器访问被禁止，常见于 FPU 未启用 */
    }

    if (cfsr & CFSR_UNDEFINSTR_Msk) {
        /* 指令未定义或目标内核不支持 */
    }
}
```

需要注意：

- `NOCP` 不一定只代表 FPU 未启用，也可能是 CP10/CP11 权限配置错误。
- 编译器生成了 FPU 指令，但芯片实际没有 FPU，也会产生类似问题。
- 启动文件、编译参数和芯片型号必须一致。

## 5.4 异常栈帧与浮点上下文

### 5.4.1 基本异常帧

进入异常时，硬件自动保存：

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

该结构体通常为：

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
} basic_stack_frame_t;
```

共 **8 × 4 = 32 字节**。

### 5.4.2 扩展浮点异常帧

当需要保存浮点上下文时，额外保存：

```
S0 ~ S15
FPSCR
保留字
```

总计：

```
16 × 4 + 4 + 4 = 72 字节
```

因此完整异常栈帧通常为：

```
32 + 72 = 104 字节
```

`S16~S31` 通常属于软件管理的 callee-saved 浮点寄存器，由 RTOS 或任务切换代码负责保存。

## 5.5 EXC_RETURN 与浮点栈帧判断

异常返回值 `EXC_RETURN` 中包含异常返回模式及栈帧信息。常见判断：

```
static inline bool exception_frame_has_fp(uint32_t exc_return)
{
    /*
     * EXC_RETURN bit[4]:
     * 0：扩展浮点栈帧
     * 1：基本栈帧
     */
    return (exc_return & (1UL << 4)) == 0U;
}
```

典型 HardFault 框架：

```
__attribute__((naked))
void HardFault_Handler(void)
{
    __asm volatile (
        "tst lr, #4                         \n"
        "ite eq                             \n"
        "mrseq r0, msp                      \n"
        "mrsne r0, psp                      \n"
        "mov r1, lr                         \n"
        "b hardfault_c                      \n"
    );
}

void hardfault_c(uint32_t *stacked, uint32_t exc_return)
{
    basic_stack_frame_t *frame = (basic_stack_frame_t *)stacked;

    uint32_t pc = frame->pc;
    uint32_t xpsr = frame->xpsr;

    bool has_fp_frame = exception_frame_has_fp(exc_return);

    /*
     * 生产系统应：
     * 1. 保存 PC/LR/xPSR/CFSR/HFSR/BFAR/MMFAR；
     * 2. 保存任务 ID、栈边界、复位原因；
     * 3. 判断 stacked 指针是否落在合法栈区；
     * 4. 禁止继续解引用可能损坏的帧；
     */
    (void)pc;
    (void)xpsr;
    (void)has_fp_frame;
}
```

## 5.6 Lazy Stacking

### 5.6.1 工作机制

Lazy Stacking 允许异常入口先只保存基本栈帧，不立即保存 S0~S15/FPSCR。

只有在异常处理代码实际执行浮点指令时，硬件才补充保存浮点上下文。

这样可以降低：

- 不使用浮点的高频中断入口开销；
- 中断嵌套下的平均栈流量；
- 非浮点异常路径的延迟。

### 5.6.2 FPCCR 关键位

常见字段：

- `ASPEN`：自动状态保存使能；
- `LSPEN`：Lazy State Preservation 使能；
- `LSPACT`：当前存在延迟保存的浮点状态。

示例配置：

```
static void fpu_lazy_stacking_enable(void)
{
    /*
     * ASPEN = 1，LSPEN = 1
     */
    FPU->FPCCR |= FPU_FPCCR_ASPEN_Msk |
                  FPU_FPCCR_LSPEN_Msk;

    __DSB();
    __ISB();
}
```

### 5.6.3 Lazy Stacking 的工程风险

Lazy Stacking 并不等于“没有浮点栈开销”。

风险包括：

1. **中断处理程序偶然使用浮点**
    - 例如日志格式化调用 `printf("%f")`；
    - 监控代码进行比例计算；
    - 编译器内联了浮点表达式。
2. **中断延迟不可预测**
    - 首次执行 FPU 指令时发生延迟保存。
3. **栈峰值估算错误**
    - 只按基本栈帧分配栈空间；
    - 嵌套中断时发生栈溢出。
4. **调试器改变行为**
    - 单步、监视寄存器或调试启动配置可能影响观察结果。

工业建议：

- 强实时 ISR 禁止浮点。
- 浮点计算放到任务或专用低优先级处理线程。
- 如果 ISR 必须使用浮点，应将扩展栈帧纳入最坏情况预算。
- 对高确定性系统，可考虑关闭 Lazy Stacking，采用显式、稳定的上下文策略。

## 5.7 编译器代码生成与 FPU 验证

### 5.7.1 示例代码

```
float vector_dot(const float *a, const float *b, size_t n)
{
    float sum = 0.0f;

    for (size_t i = 0; i < n; ++i) {
        sum += a[i] * b[i];
    }

    return sum;
}
```

### 5.7.2 预期硬件指令

开启优化后，可能看到：

```
vldr    s14, [r0, #...]
vldr    s15, [r1, #...]
vmla.f32 s0, s14, s15
```

或者：

```
vmul.f32 s1, s2, s3
vadd.f32 s0, s0, s1
```

### 5.7.3 验证方法

```
arm-none-eabi-objdump -d app.elf | grep -E "v(add|sub|mul|mla|mls|div|sqrt)"
```

如果没有看到 VFP 指令，常见原因：

- 使用了 `-mfloat-abi=soft`；
- 函数被优化成整数或常量计算；
- 使用了 `double`；
- 编译器调用了库函数；
- 目标架构与 `-mfpu` 不匹配；
- 优化等级过低；
- 浮点代码位于未被链接的目标段。

## 5.8 `float`、`double` 与字面量陷阱

错误示例：

```
float gain = 0.1;       /* 0.1 默认是 double */
float y = x * 2.0;      /* 2.0 默认是 double */
```

正确示例：

```
float gain = 0.1f;
float y = x * 2.0f;
```

错误写法可能导致：

- 触发软件双精度运算；
- 产生 `__aeabi_dmul`、`__aeabi_dadd` 等库调用；
- 性能从数周期退化到数百周期甚至更多；
- 代码体积增加。

## 5.9 FPSCR 配置

```
static void fpu_configure(void)
{
    uint32_t fpscr = __get_FPSCR();

    /*
     * 清除累计异常标志和控制字段。
     */
    fpscr &= ~(0x9FUL);

    /*
     * FZ：Flush-to-Zero
     * 对极小非规格化数直接按 0 处理。
     */
    fpscr |= (1UL << 24);

    /*
     * DN：Default NaN，可按项目规范选择。
     */
    fpscr |= (1UL << 25);

    __set_FPSCR(fpscr);
    __DSB();
    __ISB();
}
```

### 设计取舍

|配置|优点|风险|
|---|---|---|
|FZ=0|IEEE-754 行为更完整|极小数运算可能变慢|
|FZ=1|实时性更稳定|牺牲非规格化数精度|
|DN=0|保留 NaN 传播信息|NaN 行为更复杂|
|DN=1|行为更统一|丢失部分 NaN 载荷信息|

## 5.10 浮点比较与 NaN

错误代码：

```
if (value == NAN) {
    /* 永远不能按预期工作 */
}
```

正确代码：

```
#include <math.h>

if (isnan(value)) {
    /* 处理非法计算结果 */
}

if (isfinite(value) == 0) {
    /* 处理 NaN 或 Inf */
}
```

生产级输入检查：

```
static bool float_valid(float x, float min, float max)
{
    if (!isfinite(x)) {
        return false;
    }

    return (x >= min) && (x <= max);
}
```

---

# 6. 性能量化分析

以下数据为工程估算和典型实测区间，实际结果取决于：

- Cortex-M 型号；
- 主频；
- Flash 等待周期；
- I/D Cache；
- TCM；
- 编译器；
- 优化等级；
- 数据是否对齐；
- 浮点输入是否为正常数、NaN、Inf 或非规格化数。

## 6.1 典型指令周期

以 Cortex-M7、216 MHz、代码位于 ITCM、数据位于 DTCM、开启优化为例：

|操作|典型延迟/吞吐|备注|
|---|---|---|
|`VADD.F32`|约 1~2 周期|受相关性和流水线影响|
|`VSUB.F32`|约 1~2 周期|同上|
|`VMUL.F32`|约 1~2 周期|通常可流水化|
|`VMLA.F32`|约 1~2 周期|适合 MAC|
|`VDIV.F32`|约 10~20 周期|内核实现差异大|
|`VSQRT.F32`|约 10~20 周期|需查看具体 TRM|
|`VCVT`|约 1~4 周期|依目标和数据类型而定|
|软件 `double` 加法|数十周期以上|可能调用库|
|软件 `double` 除法|数百周期级|需重点规避|

不可将“指令延迟”直接等同于“函数总周期”。函数总耗时还包括：

- Load/Store；
- 缓存未命中；
- 循环控制；
- 分支；
- 浮点数据相关；
- 函数调用；
- ABI 参数搬运；
- 中断抢占。

## 6.2 浮点上下文内存开销

### 异常级上下文

基本异常帧：

```
8 个字 × 4 字节 = 32 字节
```

浮点扩展帧：

```
S0~S15：16 × 4 = 64 字节
FPSCR：4 字节
保留字段：4 字节
合计：72 字节
```

完整异常栈：

```
32 + 72 = 104 字节
```

### 任务级上下文

常见 RTOS 需要保存：

- `S16~S31`：16 × 4 = 64 字节；
- 可能还有控制寄存器、对齐填充；
- 加上任务栈中的异常帧。

因此，每个浮点任务至少要额外预算约：

```
64 字节 + 对齐余量
```

如果任务本身可能被浮点 ISR 抢占，任务栈还需要额外覆盖扩展异常帧：

```
至少再增加 72 字节
```

工程预算不应只加 136 字节，而应按以下公式估算：

```
Stack_required =
    Basic_frame
  + FP_extended_frame_if_possible
  + RTOS_saved_context
  + nested_ISR_frames
  + compiler_call_depth
  + safety_margin
```

推荐安全余量：

```
Safety_margin >= 20%
```

对于复杂算法任务，建议通过栈水位和压力测试实测，而不是仅依赖静态估算。

## 6.3 浮点任务切换成本

假设 RTOS 每次切换浮点任务时保存和恢复 `S16~S31`：

```
16 个寄存器 × 4 字节 = 64 字节
```

若使用 32 位 Load/Store：

```
16 次 Store + 16 次 Load = 32 次访存
```

在 TCM 中可能约为几十周期；在普通 Flash/外部 RAM 环境中，考虑等待、总线竞争和 Cache 未命中后，可能达到：

```
约 50~150 周期
```

若调度频率为 1 kHz、每次切换涉及 2 个浮点任务，粗略 CPU 占用：

```
Overhead = 1000 × 100 cycles / CPU_frequency
```

在 200 MHz 下：

```
= 100,000 / 200,000,000
≈ 0.05%
```

但这只是纯寄存器搬运。若每个任务还发生异常扩展栈、Cache miss、MPU 切换和调度器逻辑，实际开销可能达到 **0.1%~1%** 。

## 6.4 浮点与定点性能比较

以 100 阶 FIR 为例：

```
y[n] = Σ x[i] × h[i]
```

理论操作量：

```
100 次乘法 + 100 次加法
```

典型结果：

|实现|典型耗时，216 MHz|备注|
|---|---|---|
|标量 `float`|约 0.8~2.0 μs|取决于加载和优化|
|CMSIS-DSP `arm_fir_f32`|约 0.5~1.5 μs|通常更优|
|Q15/Q31 DSP|约 0.3~1.2 μs|需考虑缩放和饱和|
|软件 `double`|约 10~50 μs|可能更高|

## 6.5 瓶颈与优化收益

### 瓶颈一：隐式 double

```
float result = value * 0.333333333333;
```

优化：

```
float result = value * 0.333333333333f;
```

收益：

- 减少软件库调用；
- 降低代码体积；
- 避免 double 临时变量；
- 典型路径可获得数倍至数十倍收益。

### 瓶颈二：内存系统

即使 FPU 每周期可完成一次 MAC，若数据从慢速 Flash 或外部 RAM 读取，FPU 会等待数据。

优化手段：

- 常量放入 DTCM/紧耦合 RAM；
- 关键代码放入 ITCM；
- 使用 DMA 预取；
- 保证 4 字节对齐；
- 合理使用 D-Cache；
- 避免 DMA 与 Cache 数据不一致。

### 瓶颈三：除法和开方

```
float normalized = value / scale;
float norm = sqrtf(x * x + y * y + z * z);
```

优化策略：

- 预计算倒数：

```
float inv_scale = 1.0f / scale;
float normalized = value * inv_scale;
```

- 使用 `arm_fast_sqrt_f32` 或项目允许的近似算法；
- 对控制算法采用查表、牛顿迭代或定点近似；
- 明确误差预算后再使用快速近似。

### 瓶颈四：浮点依赖链

错误：

```
for (size_t i = 0; i < n; ++i) {
    sum = sum + data[i] * coeff[i];
}
```

该代码的累加存在长依赖链。

优化：

```
float sum0 = 0.0f;
float sum1 = 0.0f;
float sum2 = 0.0f;
float sum3 = 0.0f;

for (size_t i = 0; i + 3U < n; i += 4U) {
    sum0 += data[i]     * coeff[i];
    sum1 += data[i + 1] * coeff[i + 1];
    sum2 += data[i + 2] * coeff[i + 2];
    sum3 += data[i + 3] * coeff[i + 3];
}

float sum = sum0 + sum1 + sum2 + sum3;
```

代价：

- 浮点加法结合顺序改变；
- 结果可能有微小差异；
- 不适合要求严格逐项复现的算法；
- 可以通过误差上限验证后采用。

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要浮点运算？
├── 否
│   └── 优先使用整数或定点，避免启用 FPU
│
└── 是
    ├── 目标 MCU 没有 FPU？
    │   ├── 运算量低、实时性要求低
    │   │   └── 使用 float + 软件库
    │   └── 运算量高或实时性严格
    │       └── 使用 Q15/Q31、DSP 优化或更换 MCU
    │
    └── 目标 MCU 有 FPU
        ├── 是否需要与已有 soft ABI 库兼容？
        │   ├── 是
        │   │   └── softfp
        │   └── 否
        │       └── hard ABI
        │
        ├── 是否存在强实时 ISR？
        │   ├── 是
        │   │   └── ISR 禁止浮点，算法放入任务
        │   └── 否
        │       └── 可采用 lazy stacking
        │
        ├── 数据量大、带宽受限？
        │   ├── 是
        │   │   └── 评估 Q15/Q31、CMSIS-DSP、DMA
        │   └── 否
        │       └── float32 优先
        │
        └── 是否需要 double 精度？
            ├── 是
            │   ├── 是否能接受高计算成本？
            │   │   ├── 是：软件 double
            │   │   └── 否：更换支持双精度的处理器
            └── 否：使用 float
```

## 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|电机 FOC 电流环 10~40 kHz|`float` FPU 或 Q31|浮点开发效率高，Q31 可获得更稳定时延|
|IMU 姿态解算|`float32` + CMSIS-DSP|动态范围大，算法可读性好|
|音频 48 kHz FIR/IIR|FPU + CMSIS-DSP，必要时 Q15|需要大量 MAC 和稳定吞吐|
|安全保护 ISR|定点或整数|避免 FPU 上下文和不可预测延迟|
|云端协议栈|禁止在 ISR 中使用 FPU|协议处理通常不需要高频浮点|
|标定参数计算|`float`|计算频率低，优先精度和可维护性|
|高精度计量|`double` 或外部协处理器|单精度有效数字可能不足|
|电池 SOC/SOH 估计|`float`|算法复杂、动态范围较宽|

---

# 8. 工程最佳实践

## 8.1 设计原则

1. **统一浮点架构配置**
    - `-mcpu`、`-mfpu`、`-mfloat-abi` 必须在全工程一致。
2. **优先使用 `float`**
    - 所有常量显式使用 `f` 后缀。
3. **ISR 禁止浮点**
    - 尤其是高频、低延迟、安全保护类 ISR。
4. **浮点任务显式标识**
    - RTOS 任务创建时标识是否使用 FPU。
5. **对浮点输入做有限性检查**
    - 关键控制链路必须检测 NaN/Inf。
6. **对栈进行峰值测试**
    - 静态估算不能替代运行时栈水位检测。
7. **性能测试必须在真实内存系统下进行**
    - 不要只在 ITCM/DTCM 下测量。
8. **计算精度和实时性共同验收**
    - 浮点不是天然正确，也不是天然实时。

## 8.2 选型决策矩阵

|约束|float32|double|Q31|Q15|
|---|---|---|---|---|
|开发效率|高|中|中|低|
|动态范围|中|高|中|低|
|精度|中|高|中|低~中|
|实时确定性|中|低|高|高|
|代码复杂度|低|低|高|高|
|FPU 依赖|是|通常无法完全利用|否|否|
|适合高频控制|可|不推荐|很适合|适合|
|适合复杂估计|很适合|精度敏感时适合|需谨慎|通常不适合|

## 8.3 工业级编码规范

### 浮点常量

```
#define CTRL_DT_S       (0.0001f)
#define MAX_CURRENT_A   (30.0f)
#define INV_SQRT_3      (0.57735026919f)
```

### 不直接比较浮点相等

```
static bool float_equal(float a, float b, float abs_tol)
{
    return fabsf(a - b) <= abs_tol;
}
```

### 防止除零

```
static bool safe_div_f32(float numerator,
                         float denominator,
                         float denominator_min,
                         float *result)
{
    if ((result == NULL) ||
        !isfinite(numerator) ||
        !isfinite(denominator) ||
        (fabsf(denominator) < denominator_min)) {
        return false;
    }

    *result = numerator / denominator;
    return isfinite(*result);
}
```

### 记录 FPSCR 和 Fault 状态

在安全关键系统中，应把以下信息纳入诊断记录：

- FPSCR；
- CFSR；
- HFSR；
- DFSR；
- MMFAR；
- BFAR；
- 当前任务 ID；
- 当前异常嵌套深度；
- 当前 PSP/MSP。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：FPU 未启用就执行浮点指令

### 错误代码

```
int main(void)
{
    float a = 1.0f;
    float b = a * 2.0f;
    return (int)b;
}
```

### 根因

- 启动代码没有设置 CP10/CP11；
- 启用了编译器 FPU 指令，但芯片初始化未同步；
- `SystemInit()` 被裁剪或未调用。

### 正确实现

```
int main(void)
{
    fpu_enable_strict();
    fpu_configure();

    float a = 1.0f;
    float b = a * 2.0f;

    return (int)b;
}
```

### 风险影响

- 进入 UsageFault；
- 若 UsageFault 未启用，升级为 HardFault；
- 现场表现为启动即死。

---

## 9.2 错误二：工程中混用 hard/softfp ABI

### 错误配置

```
应用：-mfloat-abi=hard
第三方库：-mfloat-abi=softfp
```

### 根因

硬浮点 ABI 使用 VFP 寄存器传递浮点参数，软件 ABI 使用整数寄存器或栈传递。

### 正确实现

使用构建系统统一配置：

```
add_compile_options(
    -mcpu=cortex-m7
    -mthumb
    -mfpu=fpv5-sp-d16
    -mfloat-abi=hard
)

add_link_options(
    -mcpu=cortex-m7
    -mthumb
    -mfpu=fpv5-sp-d16
    -mfloat-abi=hard
)
```

并检查库属性：

```
arm-none-eabi-readelf -A libfoo.a
```

### 风险影响

- 链接器直接报 ABI 不兼容；
- 某些非标准构建链可能静默产生错误参数传递；
- 性能退化为软件浮点。

---

## 9.3 错误三：在高优先级 ISR 中使用浮点

### 错误代码

```
void ADC_IRQHandler(void)
{
    float current = adc_raw_to_current(ADC1->DR);
    control_state.current = current;
}
```

### 根因

- ISR 触发 Lazy Stacking；
- 浮点指令引入额外上下文保存；
- ISR WCET 增加；
- 异常嵌套导致栈峰值不可控。

### 正确实现

```
void ADC_IRQHandler(void)
{
    uint16_t raw = (uint16_t)ADC1->DR;

    /*
     * ISR 只采集原始数据并通知任务。
     */
    adc_sample_queue_push_from_isr(raw);
}
```

任务中执行：

```
void control_task(void *arg)
{
    uint16_t raw;

    for (;;) {
        if (adc_sample_queue_pop(&raw, WAIT_FOREVER)) {
            float current = adc_raw_to_current(raw);
            control_update(current);
        }
    }
}
```

### 风险影响

- 电流环抖动；
- 保护中断响应时间增加；
- 栈溢出；
- 浮点状态被错误保存或破坏。

---

## 9.4 错误四：使用 double 常量导致软件双精度

### 错误代码

```
float temperature = raw * 0.125 + (-40.0);
```

### 根因

C 语言中无后缀小数常量默认为 `double`。

### 正确实现

```
float temperature = raw * 0.125f - 40.0f;
```

### 风险影响

- 引入 `__aeabi_d*` 函数；
- 运算性能大幅下降；
- Flash 代码体积增加；
- 控制任务超时。

---

## 9.5 错误五：只保存 S0~~S15，忽略 S16~~S31

### 错误场景

RTOS 自定义上下文切换代码只保存低位浮点寄存器。

### 根因

按照异常扩展帧模型误认为所有浮点寄存器都由硬件自动保存。

实际通常是：

- 硬件异常帧保存 S0~S15；
- 软件上下文切换负责 S16~S31。

### 正确实现

伪代码：

```
/* 仅示意，实际需结合具体 RTOS ABI 和栈布局 */
vstmdb  r0!, {s16-s31}
...
vldmia  r0!, {s16-s31}
```

### 风险影响

- 任务切换后浮点变量随机变化；
- 算法偶发失稳；
- 难以复现，容易误判为内存踩踏。

---

## 9.6 错误六：未检查 NaN/Inf

### 错误代码

```
float angle = atan2f(y, x);
motor_set_angle(angle);
```

### 根因

- 输入传感器异常；
- 除零或溢出；
- DMA 数据未更新；
- 上游算法已经产生 NaN。

### 正确实现

```
float angle = atan2f(y, x);

if (!isfinite(angle)) {
    fault_record(FAULT_INVALID_ANGLE);
    angle = 0.0f;
}

motor_set_angle(angle);
```

### 风险影响

- NaN 传播到 PID、PWM、通信协议；
- 比较判断全部失效；
- 执行器输出不可预测。

---

# 10. 多机制组合使用方案

## 10.1 推荐架构

```
ADC/DMA
  │
  ├── 原始采样缓冲
  │
  ▼
高优先级 ISR
  ├── 清中断标志
  ├── 记录时间戳
  ├── 推送样本索引
  └── 不执行浮点
  │
  ▼
浮点算法任务
  ├── ADC 标定
  ├── Clarke/Park 变换
  ├── PI/PID
  ├── 观测器
  └── 饱和与 NaN 检查
  │
  ▼
整数/PWM 输出层
  ├── 限幅
  ├── 转换为定时器比较值
  └── 写入 Shadow Register
```

## 10.2 组合设计原则

组合使用：

- **DMA**：降低采样搬运开销；
- **ISR**：只做实时事件确认；
- **RTOS 队列/通知**：传递样本完成事件；
- **FPU 任务**：执行浮点算法；
- **整数输出层**：确保外设写入和保护路径简单；
- **DWT**：记录算法耗时；
- **MPU/栈监控**：防止浮点任务栈溢出。

## 10.3 完整代码框架

```
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

typedef struct {
    uint16_t ia_raw;
    uint16_t ib_raw;
    uint32_t timestamp;
} adc_sample_t;

typedef struct {
    float ia;
    float ib;
    float duty_a;
    float duty_b;
} control_result_t;

static bool convert_sample(const adc_sample_t *sample,
                           float *ia,
                           float *ib)
{
    if ((sample == NULL) || (ia == NULL) || (ib == NULL)) {
        return false;
    }

    /*
     * 所有常量显式使用 float。
     */
    *ia = ((float)sample->ia_raw - 2048.0f) * 0.01f;
    *ib = ((float)sample->ib_raw - 2048.0f) * 0.01f;

    return isfinite(*ia) && isfinite(*ib);
}

static bool control_compute(const adc_sample_t *sample,
                            control_result_t *result)
{
    float ia;
    float ib;

    if ((result == NULL) ||
        !convert_sample(sample, &ia, &ib)) {
        return false;
    }

    /*
     * 示例：简单比例控制。
     * 实际项目可能包括 Clarke/Park、PI、解耦和 SVPWM。
     */
    result->ia = ia;
    result->ib = ib;
    result->duty_a = 0.5f + 0.01f * ia;
    result->duty_b = 0.5f + 0.01f * ib;

    if (!isfinite(result->duty_a) ||
        !isfinite(result->duty_b)) {
        return false;
    }

    if (result->duty_a < 0.0f) {
        result->duty_a = 0.0f;
    } else if (result->duty_a > 1.0f) {
        result->duty_a = 1.0f;
    }

    if (result->duty_b < 0.0f) {
        result->duty_b = 0.0f;
    } else if (result->duty_b > 1.0f) {
        result->duty_b = 1.0f;
    }

    return true;
}

void ADC_IRQHandler(void)
{
    adc_sample_t sample;

    /*
     * 1. 读取 DMA 已完成缓冲；
     * 2. 只做整数数据整理；
     * 3. 投递到任务；
     */
    sample.ia_raw = ADC1->DR;
    sample.ib_raw = ADC2->DR;
    sample.timestamp = DWT->CYCCNT;

    control_queue_push_from_isr(&sample);
}

void control_task(void *arg)
{
    adc_sample_t sample;
    control_result_t result;

    (void)arg;

    for (;;) {
        if (!control_queue_pop(&sample, WAIT_FOREVER)) {
            continue;
        }

        uint32_t start = DWT->CYCCNT;

        if (!control_compute(&sample, &result)) {
            fault_record(FAULT_CONTROL_NUMERIC);
            pwm_disable();
            continue;
        }

        pwm_set_duty_float(result.duty_a, result.duty_b);

        uint32_t elapsed = DWT->CYCCNT - start;
        control_monitor_wcet(elapsed);
    }
}
```

---

# 11. 工业级实际案例分析

## 11.1 案例一：三相 PMSM FOC 控制

### 需求

- 电流环频率：20 kHz；
- 控制周期：50 μs；
- 输入：ADC 同步采样；
- 算法：Clarke、Park、PI、反 Park、SVPWM；
- 最坏执行时间：小于 20 μs；
- 保护 ISR：过流响应小于 2 μs。

### 架构

```
PWM 定时器触发 ADC
        │
        ▼
DMA 双缓冲
        │
        ▼
ADC ISR：仅确认采样完成
        │
        ▼
FOC 浮点任务
        │
        ▼
PWM Shadow Register
```

### 设计要点

- 保护路径不使用 FPU；
- FOC 任务使用 `float32` 或 Q31；
- 查表替代高频 `sinf/cosf`，或者使用 CMSIS-DSP；
- 对电流、电压、母线电压做范围检查；
- FPU 任务栈单独配置；
- DWT 记录 99.9 分位和最大执行时间；
- 通过故障注入测试 NaN、ADC 饱和和 DMA 丢样本。

### 核心代码

```
static bool foc_update(float ia,
                       float ib,
                       float theta,
                       float *duty_a,
                       float *duty_b,
                       float *duty_c)
{
    if ((duty_a == NULL) ||
        (duty_b == NULL) ||
        (duty_c == NULL)) {
        return false;
    }

    if (!isfinite(ia) ||
        !isfinite(ib) ||
        !isfinite(theta)) {
        return false;
    }

    float sin_theta = arm_sin_f32(theta);
    float cos_theta = arm_cos_f32(theta);

    float alpha = ia;
    float beta = (ia + 2.0f * ib) * 0.57735026919f;

    float id = alpha * cos_theta + beta * sin_theta;
    float iq = -alpha * sin_theta + beta * cos_theta;

    /*
     * 此处接入 PI、解耦和 SVPWM。
     */
    (void)id;
    (void)iq;

    *duty_a = 0.5f;
    *duty_b = 0.5f;
    *duty_c = 0.5f;

    return true;
}
```

### 主要风险

- FPU 任务未保存 `S16~S31`；
- 中断中调用浮点日志；
- `double` 三角函数导致执行时间失控；
- Cache/DMA 数据不一致；
- 任务栈不足导致控制环偶发崩溃。

---

## 11.2 案例二：IMU 姿态融合

### 需求

- IMU 采样频率：1 kHz；
- 算法：四元数积分、陀螺仪偏置估计、加速度校正；
- 允许输出延迟：小于 2 ms；
- 角度误差：小于 0.5°；
- 传感器可能出现断线、全零或饱和数据。

### 架构

```
SPI + DMA
   │
   ▼
数据完整性校验
   │
   ▼
浮点姿态任务
   ├── 单位换算
   ├── 四元数更新
   ├── 归一化
   ├── 有限性检查
   └── 输出姿态
```

### 四元数归一化

```
static bool quat_normalize(float q[4])
{
    if (q == NULL) {
        return false;
    }

    float norm_sq = q[0] * q[0] +
                    q[1] * q[1] +
                    q[2] * q[2] +
                    q[3] * q[3];

    if (!isfinite(norm_sq) || (norm_sq < 1.0e-12f)) {
        return false;
    }

    float inv_norm = 1.0f / sqrtf(norm_sq);

    for (size_t i = 0; i < 4U; ++i) {
        q[i] *= inv_norm;
    }

    for (size_t i = 0; i < 4U; ++i) {
        if (!isfinite(q[i])) {
            return false;
        }
    }

    return true;
}
```

### 设计要点

- 传感器原始数据先做整数级 CRC/范围检查；
- 算法内部统一使用 `float32`；
- 归一化前检查范数下限；
- 对 NaN、Inf 进行故障计数；
- 使用固定周期任务，避免不受控的浮点计算积压；
- 必要时使用定点预处理减少总线和内存压力。

---

## 11.3 案例三：工业温控与热模型

### 需求

- 温度采样周期：100 ms；
- 多阶 RC 热模型；
- PID + 前馈；
- 对实时性要求中等；
- 需要在线标定参数；
- 设备使用 Cortex-M33，支持 TrustZone。

### 架构

```
安全域
 ├── 过温比较器
 ├── 硬件紧急关断
 └── 故障状态寄存器

非安全域
 ├── 浮点热模型
 ├── 参数拟合
 ├── 诊断与记录
 └── HMI/通信
```

### 设计要点

- 安全保护由硬件比较器和整数阈值完成；
- 浮点模型不能直接决定最终安全关断；
- 标定参数从安全存储区域读取并做范围校验；
- 浮点任务运行频率低，可接受软件开方或较高运算延迟；
- 使用 MPU/TrustZone 隔离算法区和安全控制区。

---

# 12. 高频问题深度答疑

## 问题一：Cortex-M 的 FPU 能否高效执行 double？

通常不能。

多数 Cortex-M4F、M7、M33 的 FPU 是 **单精度 FPv4-SP/FPv5-SP**。`double` 通常由软件库实现，即使语法上使用 `double`，编译器也可能生成：

```
__aeabi_dadd
__aeabi_dmul
__aeabi_ddiv
```

因此：

- 控制算法优先使用 `float`；
- 只有精度确实需要时才使用 `double`；
- 若 double 是核心负载，应评估支持双精度的处理器或外部协处理器。

## 问题二：`softfp` 和 `hard` 哪个性能更好？

对本地浮点密集计算而言，二者都可以使用硬件 FPU；主要差异在 ABI。

- `softfp`：浮点参数按照软件 ABI 传递；
- `hard`：浮点参数通过 VFP 寄存器传递。

如果函数频繁传递浮点参数，`hard` 通常减少参数搬运。但 hard ABI 要求：

- 应用；
- 静态库；
- 第三方库；
- 启动代码；
- 系统库；

全部保持兼容。

## 问题三：为什么开启 Lazy Stacking 后仍然发生栈溢出？

因为 Lazy Stacking 只是延迟保存，不是取消保存。

在以下条件下，浮点扩展帧仍会被压入栈：

- 中断代码使用 FPU；
- 被中断的上下文涉及浮点状态；
- 异常嵌套；
- RTOS 任务使用浮点；
- 调试或实现策略导致状态保存。

因此栈预算必须包含：

```
基本栈帧 + 浮点扩展栈帧 + 嵌套异常帧 + RTOS 上下文 + 安全余量
```

## 问题四：浮点计算结果为什么在不同编译器或优化等级下不同？

原因包括：

- 加法结合顺序变化；
- FMA 融合与否；
- 舍入点不同；
- 浮点寄存器中间结果精度不同；
- `-ffast-math` 放宽 IEEE-754 语义；
- 是否启用 Flush-to-Zero；
- 是否使用近似数学函数。

例如：

```
(a + b) + c
```

通常不一定等于：

```
a + (b + c)
```

如果项目要求跨平台可复现：

- 禁止不受控的 `fast-math`；
- 固定编译器与版本；
- 明确 FMA 和舍入策略；
- 使用误差范围，而不是逐位比较。

## 问题五：是否可以在 ISR 中使用 `sqrtf()` 或 `atan2f()`？

技术上可以，但工程上通常不推荐。

风险：

- 可能执行大量指令；
- 可能触发 FPU 上下文保存；
- 最坏执行时间较大；
- 某些数学库实现可能存在分支或异常路径；
- 高优先级 ISR 被延迟。

推荐做法：

- ISR 采集数据；
- 任务执行复杂数学；
- 对实时保护路径使用整数比较、查表或简化近似；
- 若必须在 ISR 使用，必须进行 WCET 测量和栈峰值测试。

## 问题六：`volatile float` 能保证浮点数据一致性吗？

不能完全保证。

```
volatile float sensor_value;
```

`volatile` 只约束编译器不要删除或合并访问，并不自动保证：

- 多线程原子性；
- 数据结构一致性；
- 读写顺序；
- DMA Cache 一致性；
- 多变量快照一致性。

如果 ISR 更新多个浮点变量，应使用：

- 临界区；
- 双缓冲；
- 序列号；
- 环形队列；
- 原子指针交换；
- DMA 完成事件同步。

例如序列号快照：

```
typedef struct {
    uint32_t seq;
    float x;
    float y;
    float z;
} imu_shared_t;

static bool imu_read_consistent(const imu_shared_t *src,
                                float *x,
                                float *y,
                                float *z)
{
    uint32_t begin;
    uint32_t end;

    do {
        begin = src->seq;

        if (begin & 1U) {
            continue;
        }

        *x = src->x;
        *y = src->y;
        *z = src->z;

        end = src->seq;
    } while ((begin != end) || (end & 1U));

    return isfinite(*x) && isfinite(*y) && isfinite(*z);
}
```

---

# 13. 课程核心总结

## 13.1 核心要点

1. **Cortex-M FPU 通常是单精度硬件 FPU，不是通用双精度计算单元。**
2. 启用 FPU 的核心步骤是：

```
配置 CPACR
→ DSB
→ ISB
→ 配置 FPSCR/FPCCR
```

3. **浮点 ABI 必须全工程统一**。
4. 异常上下文分为：

```
基本帧：32 字节
浮点扩展帧：72 字节
完整扩展帧：通常 104 字节
```

5. `S0~S15` 通常由硬件异常机制处理，`S16~S31` 通常需要 RTOS/软件保存。
6. **Lazy Stacking 降低平均开销，但不会消除最坏情况栈和延迟。**
7. `double` 在多数 Cortex-M FPU 上会退化为软件实现。
8. 高优先级 ISR 应避免浮点，浮点算法放入任务。
9. `float` 代码必须防范：

```
NaN
Inf
除零
非规格化数
溢出
精度累积误差
```

10. 性能瓶颈不只在 FPU，也可能来自：

```
内存系统
Cache
DMA 一致性
函数调用
软件 double
除法/开方
浮点依赖链
```

## 13.2 性能排序

典型情况下，从高性能到低性能：

```
定点 DSP/Q15/Q31
≈ CMSIS-DSP 优化 float32
> 手写优化 float32
> 普通标量 float32
> softfp + 不合理 ABI 调用
> 软件 double
```

但最终排序必须通过实际平台测量确认。

## 13.3 通用选型结论

- **复杂算法、动态范围较大**：优先 `float32 + FPU`。
- **强实时、高频控制、固定量程**：优先 Q31/Q15。
- **中断保护路径**：优先整数/定点。
- **高精度计量**：评估 double 或更高性能处理器。
- **混合系统**：ISR 使用整数，任务使用浮点，输出层重新转换为整数。

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐配置|
|---|---|
|Cortex-M4F 浮点算法|`-mfpu=fpv4-sp-d16 -mfloat-abi=hard`|
|Cortex-M7 浮点算法|`-mfpu=fpv5-sp-d16 -mfloat-abi=hard`|
|兼容旧 soft ABI 库|`-mfloat-abi=softfp`|
|无 FPU MCU|`-mfloat-abi=soft` 或定点|
|高频 ISR|不使用 FPU|
|复杂数学任务|使用 float32 FPU|
|强确定性控制|评估定点或关闭 Lazy 策略|
|低频标定|float32，必要时 double|
|DMA + Cache|必须处理 Cache clean/invalidate|

## 14.2 特性对比表

|项目|关键结论|
|---|---|
|FPU 类型|多数 Cortex-M 为单精度|
|单精度寄存器|S0~S31|
|双字视图|D0~D15|
|CP10/CP11|控制 FPU 访问权限|
|FPSCR|浮点状态、舍入、FZ、DN|
|FPCCR|自动保存与 Lazy Stacking|
|基本异常帧|32 字节|
|浮点扩展帧|72 字节|
|`float` 常量|使用 `f` 后缀|
|NaN 判断|使用 `isnan()`，不能与 `NAN` 比较|
|有限性判断|使用 `isfinite()`|
|任务切换|关注 S16~S31 保存|
|代码验证|反汇编检查 `v*.f32`|
|性能测量|DWT CYCCNT + 最坏情况测试|

---

# 15. 学习效果自检

完成本课后，应能回答并完成以下任务：

## 15.1 原理检查

- [ ]  能解释 CP10/CP11 与 FPU 访问权限的关系。
- [ ]  能说明 S0~~S31 与 D0~~D15 的映射。
- [ ]  能解释基本异常帧和浮点扩展帧的大小。
- [ ]  能解释 Lazy Stacking 的触发条件。
- [ ]  能说明 S16~S31 为什么通常由 RTOS 保存。
- [ ]  能解释 `soft`、`softfp`、`hard` 的 ABI 差异。

## 15.2 工程检查

- [ ]  能正确配置 `-mcpu`、`-mfpu`、`-mfloat-abi`。
- [ ]  能从 ELF 属性确认实际 ABI。
- [ ]  能从反汇编确认是否生成 FPU 指令。
- [ ]  能定位 `NOCP` Fault。
- [ ]  能解析包含 FPU 上下文的异常栈。
- [ ]  能为浮点任务估算栈空间。
- [ ]  能检测 NaN、Inf、除零和范围异常。
- [ ]  能设计 ISR 与浮点任务解耦架构。

## 15.3 性能检查

- [ ]  能使用 DWT 测量浮点函数周期。
- [ ]  能分别测量 ITCM、Flash、DTCM、SRAM 下的性能。
- [ ]  能识别隐式 double。
- [ ]  能评估除法、开方和三角函数的 WCET。
- [ ]  能量化 RTOS 浮点上下文切换成本。
- [ ]  能进行栈峰值和中断嵌套压力测试。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：FPU 启用与 Fault 定位

目标：

- 在 Cortex-M4F/M7 工程中启用 FPU；
- 故意关闭 CP10/CP11；
- 执行浮点指令；
- 捕获 UsageFault；
- 解析 `CFSR.NOCP`。

验收指标：

- 能输出故障 PC；
- 能输出 CFSR/HFSR；
- 能证明 Fault 由 FPU 权限导致。

### 任务二：验证 float 与 double

实现：

```
float benchmark_float(size_t n);
double benchmark_double(size_t n);
```

测试：

- 周期数；
- Flash 占用；
- RAM 占用；
- 反汇编；
- 函数调用情况。

预期结论：

- `float` 生成 VFP 指令；
- `double` 大概率出现 `__aeabi_d*`；
- 两者执行时间存在数量级差异。

### 任务三：Lazy Stacking 压力测试

设计：

- 高频定时器 ISR；
    
- ISR 分别执行整数代码和浮点代码；
    
- 开启/关闭 Lazy Stacking；
    
- 记录：
    
    - ISR 入口延迟；
    - 最大栈深度；
    - 中断抖动；
    - 嵌套异常行为。

### 任务四：RTOS 浮点任务上下文验证

创建两个任务：

```
Task A：持续写入浮点寄存器模式 A
Task B：持续写入浮点寄存器模式 B
```

频繁切换后检查：

- 浮点寄存器是否被破坏；
- S16~S31 是否正确保存；
- 任务栈是否溢出；
- 调度开销是多少。

### 任务五：FOC 或姿态解算性能闭环

实现一个简化算法链：

```
ADC/IMU 原始数据
→ 标定
→ 浮点算法
→ 范围检查
→ 输出转换
```

测量：

- 平均执行时间；
- 最大执行时间；
- 99.9 分位执行时间；
- 浮点异常计数；
- 栈高水位；
- 中断抖动。

## 16.2 性能测试方法

推荐建立以下测试矩阵：

|维度|测试项|
|---|---|
|编译|O0/O2/O3/Os|
|ABI|softfp/hard|
|数据位置|Flash/SRAM/DTCM|
|Cache|开启/关闭|
|输入数据|正常/极小/NaN/Inf|
|浮点类型|float/double/Q31|
|调度|单任务/多任务/高频抢占|
|异常|无中断/嵌套中断|
|库|标准数学库/CMSIS-DSP/快速近似|

周期测量示例：

```
static uint32_t measure_cycles(void (*fn)(void))
{
    uint32_t start;
    uint32_t end;

    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    start = DWT->CYCCNT;
    fn();
    end = DWT->CYCCNT;

    return end - start;
}
```

生产环境应补充：

- 禁止测量代码被优化掉；
- 对输入和输出使用 `volatile` 或校验和；
- 测量中记录中断状态；
- 重复运行至少数千次；
- 统计最大值、平均值和分位数；
- 区分 Cache 热路径和冷路径。

## 16.3 进阶学习方向

### 方向一：FPU 与 RTOS 内核

- FreeRTOS Cortex-M 浮点上下文处理；
- Zephyr arch 层 FPU lazy save；
- PendSV 中 `S16~S31` 保存；
- 浮点任务标记与调度优化；
- MPU 与浮点任务隔离。

### 方向二：浮点确定性

- WCET 分析；
- FPU 指令延迟建模；
- Lazy Stacking 最坏情况；
- 异常嵌套栈预算；
- 中断抖动与 Cache 交互。

### 方向三：CMSIS-DSP

重点掌握：

- `arm_fir_f32`；
- `arm_biquad_cascade_df1_f32`；
- `arm_matrix_instance_f32`；
- `arm_cfft_f32`；
- `arm_sin_f32` / `arm_cos_f32`；
- Q15/Q31 与 float32 实现差异。

### 方向四：浮点与数值安全

- IEEE-754 异常行为；
- 浮点 NaN 注入；
- 控制算法失稳测试；
- 传感器边界数据；
- 安全关键系统的数值异常降级；
- MISRA C 对浮点使用的约束。

### 方向五：浮点与硬件加速协同

- Cortex-M DSP 扩展；
- SIMD 指令；
- Helium/MVE；
- DMA 双缓冲；
- TCM 与 Cache；
- 外部 DSP/协处理器；
- 边缘 AI 推理中的 float32、float16、int8 混合量化。

**本课最终工程结论：FPU 不是“打开编译选项就结束”的性能开关，而是涉及 ABI、异常栈、RTOS 上下文、实时性、数值稳定性和故障安全的系统级资源。**