
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 Cortex-M DSP 扩展在 **ARMv7E-M** 与 **ARMv8-M Mainline** 中的架构定位。
- 区分普通 ARM 指令、DSP 扩展指令与 Helium/MVE 向量扩展。
- 理解以下核心硬件能力：
    - 16 位双路 SIMD 算术；
    - 8 位四路 SIMD 算术；
    - 饱和加减；
    - 双 16 位乘加；
    - 32 位乘法高位提取；
    - `CLZ` 前导零统计；
    - 打包、解包、符号扩展与算术移位。
- 理解 DSP 指令对 **定点信号处理、控制环、音频、通信和传感器算法** 的价值。

### 掌握

能够：

- 识别目标 Cortex-M 内核是否支持 DSP 扩展。
- 使用 CMSIS-Core intrinsic 正确映射 DSP 指令。
- 设计 Q15、Q31 定点数据路径。
- 正确处理：
    - 有符号溢出；
    - 饱和；
    - 舍入；
    - 高低半字顺序；
    - 对齐；
    - 编译器优化；
    - 异常和未定义行为。
- 对比标量 C、DSP intrinsic、CMSIS-DSP 三种实现方式。

### 精通

能够：

- 从反汇编确认 C 代码是否真正生成 DSP 指令。
- 量化 DSP 指令对吞吐率、代码尺寸和功耗的影响。
- 根据内核型号、采样率、数据格式和实时约束进行指令级选型。
- 分析内核流水线、访存带宽和 Flash 等待周期对 DSP 性能的限制。
- 设计不依赖未定义 C 行为的生产级定点算法。

### 能够设计

能够完成：

- 基于 Cortex-M4/M7/M33 DSP 扩展的 FIR、IIR、矢量点积和 Clarke/Park 变换。
- 具有饱和保护、边界处理、可测试性和回退实现的定点 DSP 组件。
- 面向电机控制、音频采集和无线通信的 DSP 加速架构。
- DSP 指令与 DMA、定时器、Cache、RTOS 任务及硬件加速器的协同设计。

---

## 2. 前置要求

### 知识要求

- ARM Cortex-M 异常模型与寄存器：
    - `R0-R15`；
    - `xPSR`；
    - `CONTROL`；
    - `PRIMASK`；
    - `BASEPRI`。
- C 语言：
    - 整数提升规则；
    - 有符号整数表示；
    - 定点数；
    - 指针和数组；
    - `volatile`；
    - `restrict`；
    - 未定义行为。
- 基本数字信号处理：
    - 卷积；
    - FIR；
    - IIR；
    - 点积；
    - Q15/Q31；
    - 饱和与量化。
- 编译器和链接基础：
    - GCC/Clang；
    - `-mcpu`；
    - `-mthumb`；
    - `-mfpu`；
    - `-mfloat-abi`；
    - 反汇编工具。

### 技能要求

- 能够搭建 Cortex-M 工程并查看反汇编。
- 能够使用 DWT Cycle Counter 进行周期测量。
- 能够阅读 ARM 编译器生成的 Thumb-2 汇编。
- 能够运行单元测试和边界测试。
- 能够区分：
    - 编译器内建函数；
    - CMSIS-Core intrinsic；
    - CMSIS-DSP 算法库；
    - 硬件浮点 FPU；
    - DSP 扩展指令。

---

## 3. 技术概述

### 3.1 DSP 扩展的定义

Cortex-M DSP 扩展是一组面向定点信号处理和数据并行计算的 Thumb 指令扩展。它不等同于传统意义上的完整 SIMD 向量处理器，而是利用一个 32 位通用寄存器同时容纳多个较窄数据元素：

```
32 位寄存器：

31                         16 15                          0
+----------------------------+----------------------------+
|       16-bit lane 1        |       16-bit lane 0        |
+----------------------------+

或：

31 23 22 15 14 7 6 0
+------+-------+------+------+
| byte3| byte2 | byte1| byte0|
+------+-------+------+------+
```

典型能力包括：

- 一个寄存器中并行处理两个 16 位元素；
- 一个寄存器中并行处理四个 8 位元素；
- 一条指令完成两个 16 位乘法并累加；
- 对两个 16 位或四个 8 位元素同时加减；
- 发生溢出时进行饱和；
- 对 32 位结果进行高位提取；
- 快速计算前导零，用于归一化和动态缩放。

### 3.2 支持情况

|内核|DSP 扩展情况|典型能力|
|---|---|---|
|Cortex-M0/M0+|不支持传统 DSP 扩展|基本 Thumb 指令|
|Cortex-M3|通常不支持 DSP 扩展|基本 Thumb-2|
|Cortex-M4|支持 ARMv7E-M DSP|16 位 SIMD、双 MAC、饱和运算|
|Cortex-M7|支持 ARMv7E-M DSP|更深流水线、更高主频、通常配合 Cache|
|Cortex-M23|不支持传统 DSP 扩展|ARMv8-M Baseline|
|Cortex-M33|支持 ARMv8-M Mainline DSP|DSP 扩展，可选 FPU|
|Cortex-M55|支持 DSP，并可支持 Helium/MVE|标量 DSP + 向量扩展|
|Cortex-M85|支持 DSP，并可支持 Helium/MVE|更强标量与向量计算能力|

**关键结论：**

> Cortex-M4/M7/M33 的 DSP 扩展是“打包数据并行指令”；Helium/MVE 是更完整的向量扩展，两者不能混为一谈。

### 3.3 DSP 扩展与 FPU 的区别

|项目|DSP 扩展|FPU|
|---|---|---|
|数据类型|主要是整数、定点数|IEEE-754 单精度/双精度，取决于实现|
|精度|Q7/Q15/Q31|浮点|
|资源|使用整数寄存器与整数 ALU|使用浮点寄存器和浮点流水线|
|典型用途|FIR、IIR、控制、通信、音频定点|浮点控制、算法原型、动态范围较大算法|
|溢出处理|可使用饱和指令|依赖 IEEE 浮点语义|
|数据转换成本|低|定点到浮点转换可能产生额外成本|
|功耗|通常较低|取决于 FPU 实现和使用频率|
|实时确定性|较好|需关注 Lazy Stacking、异常上下文保存|

---

## 4. 核心特性横向对比

### 4.1 三种实现路径对比

|维度|纯 C 标量|DSP intrinsic|CMSIS-DSP|
|---|---|---|---|
|可移植性|高|中|中高|
|性能上限|低到中|高|高|
|代码可读性|高|中|高|
|对编译器依赖|中|高|中|
|指令级可控性|低|高|中|
|边界处理|需自行实现|需自行实现|库中已有大量实现|
|适合算法|简单、非热点|热点内核|完整 DSP 模块|
|对内核型号依赖|低|高|通过宏适配|
|调试难度|低|中高|中|
|生产推荐|作为基线|热点路径|标准 DSP 算法优先|

### 4.2 典型指令类别

|指令类别|示例|典型用途|
|---|---|---|
|双 16 位加减|`SADD16`、`SSUB16`|两路并行定点运算|
|四路 8 位加减|`SADD8`、`SSUB8`|颜色、音频、字节级处理|
|双 16 位乘加|`SMLAD`、`SMLADX`|FIR、点积、复数乘法|
|双 16 位乘减|`SMLSD`、`SMLSDX`|复数运算、差分运算|
|乘法高位|`SMMLA`、`SMMUL`|Q31 缩放、矩阵运算|
|饱和|`QADD`、`QSUB`、`QASX`|防止控制算法溢出|
|打包/解包|`PKHBT`、`PKHTB`、`UXTB16`|数据重排|
|算术移位|`SSAT`、`USAT`|位宽压缩、限幅|
|前导零|`CLZ`|归一化、动态缩放|

### 4.3 不同数据格式的适配

|数据格式|元素宽度|适合指令|典型应用|
|---|---|---|---|
|Q7|8 bit|`SADD8`、`SSUB8`|音频压缩、低精度传感器|
|Q15|16 bit|`SMLAD`、`SADD16`|FIR、IIR、电机控制|
|Q31|32 bit|`SMMLA`、普通 32 位乘法|高动态范围控制、滤波|
|混合 Q15/Q31|16/32 bit|双 MAC + 64 位累加|高精度滤波、矩阵|

---

## 5. 底层原理与功能特性深度解析

## 5.1 双 16 位打包数据模型

假设两个 Q15 样本：

```
a0 = 0x1000
a1 = 0x2000
```

可以打包为：

```
a = (a1 << 16) | (a0 & 0xFFFF)
```

其逻辑布局为：

```
a[31:16] = a1
a[15:0]  = a0
```

生产级打包函数：

```
#include <stdint.h>

static inline uint32_t pack_s16x2(int16_t low, int16_t high)
{
    return ((uint32_t)(uint16_t)low) |
           ((uint32_t)(uint16_t)high << 16);
}

static inline int16_t unpack_low_s16(uint32_t value)
{
    return (int16_t)(value & 0xFFFFu);
}

static inline int16_t unpack_high_s16(uint32_t value)
{
    return (int16_t)(value >> 16);
}
```

注意：

- 必须显式转换为 `uint16_t`，避免移位过程中发生意外的有符号扩展。
- 不要依赖 C 语言结构体位域布局实现打包。
- 不要假设内存字节序与寄存器 lane 顺序完全相同。

---

## 5.2 `SADD16`：双路 16 位饱和加法

逻辑形式：

```
dst.low  = sat16(a.low  + b.low)
dst.high = sat16(a.high + b.high)
```

普通 C 实现：

```
static inline int16_t sat16_from_i32(int32_t x)
{
    if (x > INT16_MAX) {
        return INT16_MAX;
    }

    if (x < INT16_MIN) {
        return INT16_MIN;
    }

    return (int16_t)x;
}

static inline uint32_t sadd16_c(uint32_t a, uint32_t b)
{
    int16_t a0 = unpack_low_s16(a);
    int16_t a1 = unpack_high_s16(a);
    int16_t b0 = unpack_low_s16(b);
    int16_t b1 = unpack_high_s16(b);

    int16_t r0 = sat16_from_i32((int32_t)a0 + b0);
    int16_t r1 = sat16_from_i32((int32_t)a1 + b1);

    return pack_s16x2(r0, r1);
}
```

使用 CMSIS-Core intrinsic：

```
#include "arm_math.h"

static inline uint32_t sadd16_intrinsic(uint32_t a, uint32_t b)
{
    return __SADD16(a, b);
}
```

工程意义：

- 对 Q15 信号进行加法时，避免环绕溢出。
- 对音频混音、电流矢量叠加、控制误差计算尤其重要。
- 饱和不是“免费正确性”，它会改变线性系统特性。连续饱和可能造成波形削顶、控制环非线性和谐波增加。

---

## 5.3 `SMLAD`：双 16 位乘法并累加

`SMLAD` 的逻辑定义：

```
dst = accumulator + signed(a.low)  * signed(b.low)
                    + signed(a.high) * signed(b.high)
```

即：

```
dst = acc + a0*b0 + a1*b1
```

其中：

- 两个乘法输入均为有符号 16 位；
- 每个乘法产生有符号 32 位结果；
- 两个结果与累加器相加；
- 最终结果为 32 位。

CMSIS-Core 用法：

```
#include "arm_math.h"

static inline int32_t dot_q15x2(
    uint32_t packed_a,
    uint32_t packed_b,
    int32_t accumulator)
{
    return __SMLAD(packed_a, packed_b, accumulator);
}
```

### Q15 缩放分析

如果：

```
a0, a1, b0, b1 ∈ Q15
```

则：

```
a0 * b0 ∈ Q30
a1 * b1 ∈ Q30
```

因此 `SMLAD` 输出本质上是 Q30 累加值，而不是 Q15。

将其转换回 Q15，通常需要：

```
static inline int16_t q30_to_q15_round_sat(int32_t x)
{
    int32_t rounded = x + (1 << 14);
    int32_t shifted = rounded >> 15;

    return sat16_from_i32(shifted);
}
```

但需要注意：

- `x + (1 << 14)` 可能发生 32 位溢出；
- 如果输入规模足够大，应先使用 64 位中间值；
- 对滤波器累加，应根据 tap 数量评估最坏情况下的累加范围。

更稳妥的实现：

```
static inline int16_t q30_to_q15_round_sat_safe(int32_t x)
{
    int64_t value = (int64_t)x + (1LL << 14);
    value >>= 15;

    if (value > INT16_MAX) {
        return INT16_MAX;
    }

    if (value < INT16_MIN) {
        return INT16_MIN;
    }

    return (int16_t)value;
}
```

---

## 5.4 `SMLADX`：交换半字后的双乘加

`SMLADX` 对第二个操作数的高低半字进行交叉配对：

```
dst = acc + a0*b1 + a1*b0
```

示意：

```
a = [a1 | a0]
b = [b1 | b0]

SMLAD:
    a0*b0 + a1*b1

SMLADX:
    a0*b1 + a1*b0
```

这对复数乘法非常有用。

设复数：

```
A = ar + j*ai
B = br + j*bi
```

实部：

```
Re(A*B) = ar*br - ai*bi
```

虚部：

```
Im(A*B) = ar*bi + ai*br
```

对应实现：

```
typedef struct {
    int32_t real;
    int32_t imag;
} complex_q15_acc_t;

static inline complex_q15_acc_t complex_mul_q15_acc(
    int16_t ar,
    int16_t ai,
    int16_t br,
    int16_t bi)
{
    uint32_t a = pack_s16x2(ar, ai);
    uint32_t b = pack_s16x2(br, bi);

    complex_q15_acc_t result;

    /*
     * 实部：ar * br - ai * bi
     *
     * SMLSD:
     * acc + a.low*b.low - a.high*b.high
     */
    result.real = __SMLSD(a, b, 0);

    /*
     * 虚部：ar * bi + ai * br
     *
     * SMLADX:
     * acc + a.low*b.high + a.high*b.low
     */
    result.imag = __SMLADX(a, b, 0);

    return result;
}
```

该实现输出 Q30，需要后续右移 15 位并进行饱和。

---

## 5.5 `SMLSD`：差分乘加

`SMLSD` 的逻辑：

```
dst = acc + a0*b0 - a1*b1
```

适用于：

- 复数乘法实部；
- 差分滤波；
- 正负权重对称结构；
- Clarke/Park 变换中的乘减组合。

注意：

```
INT32_MIN - 1
```

等情况可能导致 32 位有符号溢出。DSP 指令本身的溢出语义必须结合具体指令定义确认，不能简单假设所有 DSP 算术都自动饱和。

---

## 5.6 `QADD`、`QSUB`：32 位饱和加减

普通 32 位加法溢出时会环绕：

```
int32_t error = reference - feedback;
```

如果结果超出范围，C 语言有符号溢出是未定义行为。

使用 CMSIS intrinsic：

```
static inline int32_t sat_add_i32(int32_t a, int32_t b)
{
    return __QADD(a, b);
}

static inline int32_t sat_sub_i32(int32_t a, int32_t b)
{
    return __QSUB(a, b);
}
```

可用于：

- 误差积分；
- 位置累加；
- 音频混音；
- 速度环输出限幅；
- 定点 PI/PID 中的中间结果。

但是，饱和加法不能替代系统级限幅。以 PI 控制器为例，至少需要区分：

1. 运算中间值是否溢出；
2. 积分器是否发生 windup；
3. PWM 输出是否达到物理上限；
4. 传感器异常时是否需要立即禁用输出。

---

## 5.7 `SSAT` 与 `USAT`

`SSAT` 将有符号值限制到指定位宽：

```
SSAT(x, n) = clamp(x, -2^(n-1), 2^(n-1)-1)
```

`USAT` 将值限制到无符号范围：

```
USAT(x, n) = clamp(x, 0, 2^n-1)
```

CMSIS-Core 示例：

```
static inline int32_t limit_q31(int32_t value, uint32_t bits)
{
    /*
     * bits 必须满足架构允许范围。
     * 实际工程应在调用层保证参数合法，避免运行时非法用法。
     */
    return __SSAT(value, bits);
}

static inline uint32_t limit_u16(uint32_t value)
{
    return __USAT(value, 16U);
}
```

典型用途：

```
static inline int16_t clamp_pwm_command(int32_t command)
{
    int32_t limited = __SSAT(command, 15U);
    return (int16_t)limited;
}
```

如果 PWM 命令范围是 `[-32768, 32767]`，则使用 16 位有符号范围时应注意 CMSIS 参数含义和目标指令的实际编码限制，不能仅凭函数名推断边界。

---

## 5.8 `CLZ`：前导零统计

`CLZ` 返回 32 位操作数最高位开始的连续零数量：

```
CLZ(0x80000000) = 0
CLZ(0x40000000) = 1
CLZ(0x00000001) = 31
CLZ(0x00000000) = 32
```

CMSIS 用法：

```
static inline uint32_t clz_u32(uint32_t value)
{
    return __CLZ(value);
}
```

用于：

- Q31 动态归一化；
- 自动检测数据有效位宽；
- 快速确定缩放因子；
- 软件浮点格式处理；
- 音频增益控制中的峰值分析。

归一化示例：

```
static inline int32_t normalize_q31(int32_t value)
{
    uint32_t magnitude;
    uint32_t shift;

    if (value == 0) {
        return 0;
    }

    /*
     * 对 INT32_MIN 做特殊处理：
     * -INT32_MIN 在 int32_t 中不可表示。
     */
    if (value == INT32_MIN) {
        magnitude = 0x80000000U;
    } else {
        magnitude = (value < 0)
                  ? (uint32_t)(-value)
                  : (uint32_t)value;
    }

    shift = __CLZ(magnitude) - 1U;

    if (shift >= 31U) {
        return value;
    }

    return value << shift;
}
```

---

## 5.9 乘法高位提取：Q31 乘法

对于两个 Q31 数：

```
a, b ∈ [-1, 1)
```

乘法结果是约 Q62，需要提取高位形成 Q31。

某些 DSP 指令可以直接计算乘积高位，减少：

- 64 位乘法显式拼接；
- 高低寄存器管理；
- 右移和符号处理；
- 中间数据搬运。

但不同编译器和内核对 intrinsic 的暴露方式可能不同，工程中应优先：

1. 使用 CMSIS-Core 提供的架构 intrinsic；
2. 使用 CMSIS-DSP 已验证实现；
3. 用反汇编确认生成的指令；
4. 对边界值执行定点误差测试。

---

## 5.10 `GE` 标志与并行比较

部分 DSP 指令会更新 APSR 中的 GE（Greater than or Equal）标志，用于后续选择或字节级比较。

工程中不建议直接大量依赖隐式 APSR 状态，因为：

- 可读性较差；
- 容易被普通算术指令破坏；
- 内联汇编约束复杂；
- 调试和静态分析困难。

如果使用，应封装在极小函数中，并明确注明：

```
/*
 * 仅允许在本函数内部使用 GE 标志。
 * 禁止在调用者中假设 APSR 仍保持原值。
 */
```

---

## 6. 性能量化分析

## 6.1 测试平台

以下数据采用一个典型平台作为工程估算：

- MCU：Cortex-M4F
- 主频：168 MHz
- 编译器：GCC 12.x
- 编译选项：

```
-mcpu=cortex-m4
-mthumb
-O3
-ffunction-sections
-fdata-sections
```

- 数据：Q15
- 测试内容：长度 128 的 FIR
- 数据位于 SRAM
- 关闭中断干扰
- 使用 DWT `CYCCNT`
- 不计函数调用初始化成本

**说明：以下为典型实测量级，不应替代具体芯片上的基准测试。** Flash 等待周期、Cache、TCM、编译器版本和内存布局都会影响结果。

## 6.2 FIR 性能估算

标量实现：

```
int32_t acc = 0;

for (uint32_t i = 0; i < num_taps; ++i) {
    acc += (int32_t)state[i] * coeff[i];
}
```

双 MAC 实现：

```
uint32_t packed_state;
uint32_t packed_coeff;
int32_t acc = 0;

for (uint32_t i = 0; i < num_taps; i += 2U) {
    packed_state = pack_s16x2(state[i], state[i + 1U]);
    packed_coeff = pack_s16x2(coeff[i], coeff[i + 1U]);
    acc = __SMLAD(packed_state, packed_coeff, acc);
}
```

典型结果：

|实现|指令级乘法吞吐|128 tap 周期|相对性能|
|---|---|---|---|
|低优化标量 C|1 MAC 约 3～5 周期|450～650|1.0x|
|`-O3` 标量 C|1 MAC 约 2～3 周期|280～400|1.5～1.8x|
|DSP `SMLAD`|2 MAC/条指令|150～230|2.5～3.0x|
|CMSIS-DSP 优化 FIR|受访存与循环展开影响|120～210|2.8～3.5x|

### 理论周期模型

设：

- `N`：tap 数；
- `C_mac`：每个双 MAC 的计算周期；
- `C_load`：加载两个样本和两个系数的周期；
- `C_pack`：打包成本；
- `C_loop`：循环控制成本；
- `M = ceil(N/2)`。

则：

```
C_total ≈ M × (C_mac + C_load + C_pack + C_loop) + C_tail
```

在理想寄存器已打包情况下：

```
C_pack ≈ 0
```

在数据已经按合适布局存储时，DSP 扩展收益最大。

---

## 6.3 数据布局对性能的影响

### 布局一：普通 `int16_t` 数组

```
state[0], state[1], state[2], state[3], ...
```

每轮需要：

1. 加载两个 16 位元素；
2. 合并为 32 位；
3. 加载两个系数；
4. 合并为 32 位；
5. 执行 `SMLAD`。

### 布局二：预打包数组

```
uint32_t packed_state[N / 2];
uint32_t packed_coeff[N / 2];
```

每轮只需：

1. 加载一个 32 位状态；
2. 加载一个 32 位系数；
3. 执行 `SMLAD`。

典型代价：

|项目|普通布局|预打包布局|
|---|---|---|
|RAM 存储|原始数据大小|原始数据大小|
|额外打包成本|每轮存在|初始化或 DMA 阶段完成|
|代码复杂度|低|中|
|FIR 热点性能|中|高|
|数据更新灵活性|高|中|
|适合固定系数滤波|一般|很适合|

**工程结论：**

> 如果数据流长期稳定且处理频繁，应优先在接口层设计成适合双半字访问的布局，而不是在最内层循环中反复打包。

---

## 6.4 内存开销

以 128 tap Q15 FIR 为例：

### 普通数组

```
系数：128 × 2 = 256 B
状态：128 × 2 = 256 B
```

### 预打包为 32 位

```
系数：64 × 4 = 256 B
状态：64 × 4 = 256 B
```

存储空间通常不增加，但需要注意：

- 32 位对齐；
- DMA 访问粒度；
- Cache line；
- 外设数据写入格式；
- 大小端和符号扩展。

对齐声明：

```
typedef struct {
    uint32_t packed;
} packed_s16_pair_t;

static packed_s16_pair_t coeff_pairs[64] __attribute__((aligned(4)));
```

跨编译器建议使用项目统一宏：

```
#define DSP_ALIGN4 __attribute__((aligned(4)))
```

或使用 CMSIS/编译器适配层。

---

## 6.5 代码尺寸收益

一条 `SMLAD` 可以替代：

- 两次 16 位符号扩展；
- 两次 32 位乘法；
- 一次或两次加法；
- 若干寄存器搬运。

典型情况下：

|实现|代码尺寸|
|---|---|
|标量 C 循环|40～80 B|
|intrinsic 循环|24～56 B|
|手工汇编展开|可能低至 16～40 B|

但手工汇编可能降低：

- 可维护性；
- 编译器跨版本稳定性；
- 调试可观测性；
- 可移植性。

在 Flash 紧张的产品中，应优先让编译器通过 intrinsic 生成指令，再考虑手工汇编。

---

## 6.6 功耗收益

粗略模型：

```
E_total ≈ C_total × E_per_cycle
```

若 DSP 指令使计算周期从 400 降至 180：

```
能耗计算部分约下降：
1 - 180 / 400 = 55%
```

但系统级收益不一定等于 55%，原因包括：

- MCU 可能无法在计算后立即休眠；
- SRAM 和 Flash 访问占主要功耗；
- DMA、Cache、外设时钟仍然运行；
- 高频运行会提高动态功耗；
- 更短的活跃时间可能允许更长的睡眠时间。

---

## 6.7 主要瓶颈

DSP 指令并不总能提升性能。常见瓶颈：

1. **访存带宽不足**
    
    - 每条 `SMLAD` 需要两个 32 位操作数；
    - Flash 等待周期过高；
    - SRAM 总线冲突。
2. **数据打包开销**
    
    - 计算量小而打包成本高；
    - 每次函数调用都重新排列数据。
3. **循环尾部处理**
    
    - 奇数长度需要额外标量路径；
    - 短向量中尾部比例较大。
4. **非对齐访问**
    
    - 某些 MCU 上非对齐 32 位访问会拆分；
    - 某些总线或外设区域禁止非对齐访问。
5. **Cache/TCM 配置不合理**
    
    - Cortex-M7 代码在 Flash 执行时可能受等待周期影响；
    - 数据 Cache 未命中会抵消 ALU 加速。
6. **数据格式转换**
    
    - Q15 与 Q31 来回转换；
    - 饱和、舍入和重排占据主要周期。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
开始
 |
 |-- 数据是否为整数/定点格式？
 |       |
 |       |-- 否 --> 算法动态范围很大？
 |       |             |
 |       |             |-- 是 --> 使用 FPU 或软件浮点
 |       |             |
 |       |             |-- 否 --> 评估是否值得定点化
 |       |
 |       |-- 是
 |
 |-- 目标内核是否支持 DSP 扩展？
 |       |
 |       |-- 否 --> 使用标量 C + 编译器优化 + CMSIS-DSP 回退
 |       |
 |       |-- 是
 |
 |-- 是否为标准 FIR/IIR/FFT/矩阵等算法？
 |       |
 |       |-- 是 --> 优先 CMSIS-DSP
 |       |
 |       |-- 否
 |
 |-- 是否存在大量 16 位/8 位并行运算？
 |       |
 |       |-- 是 --> 使用 DSP intrinsic
 |       |
 |       |-- 否 --> 先使用标量 C，基准测试后决定
 |
 |-- 是否需要高精度和强动态范围？
 |       |
 |       |-- 是 --> Q31/64 位累加/FPU
 |       |
 |       |-- 否 --> Q15 + SMLAD
 |
 |-- 是否为极端性能热点？
         |
         |-- 是 --> intrinsic + 数据预打包 + 反汇编验证
         |
         |-- 否 --> CMSIS-DSP 或可读性优先实现
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|128 tap 音频 FIR|Q15 + `SMLAD` 或 CMSIS-DSP|双 MAC 高效，内存占用低|
|电机电流 PI 控制|Q31 + `QADD/QSUB/SSAT`|需要确定性和显式限幅|
|复数 IQ 解调|Q15 + `SMLSD/SMLADX`|直接映射复数乘法|
|低速温度滤波|标量 C|算力需求低，避免不必要复杂度|
|8 位图像通道处理|`SADD8/USAD8` 等|四路字节级并行|
|大规模向量运算|CMSIS-DSP 或 MVE|标量 DSP 扩展并行度有限|
|动态范围极大算法|FPU 或 Q31/64 位|避免频繁饱和造成精度损失|
|安全关键控制|intrinsic 封装 + 形式化边界测试|可追踪、可验证|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：先定义数值格式，再选择指令

不能先看到 `SMLAD`，再强行把算法转换成 Q15。应先确定：

- 输入范围；
- 系数量化范围；
- 最大累加长度；
- 可接受误差；
- 饱和策略；
- 舍入策略；
- 失真容忍度。

### 原则二：热点路径使用 intrinsic，算法框架保持 C

推荐分层：

```
算法层：C 语言，描述滤波/控制逻辑
数据路径层：Q15/Q31 类型和缩放管理
加速层：CMSIS intrinsic
平台层：内核检测、回退实现、编译器适配
测试层：参考模型、边界测试、周期测试
```

### 原则三：禁止默认假设编译器自动向量化

必须检查反汇编：

```
arm-none-eabi-objdump -d firmware.elf > firmware.S
grep -E "smlad|smladx|smlsd|qadd|ssat|usat" firmware.S
```

### 原则四：饱和必须有系统级策略

单条 `QADD` 只能防止某次运算溢出，不能解决：

- 积分 windup；
- 反馈异常；
- ADC 断线；
- 输出超限；
- 长期削顶；
- 失控状态。

### 原则五：使用 64 位累加器处理长 FIR

对于 N 个 Q15 乘积：

```
最大单项约为 2^30
最大累加约为 N × 2^30
```

若 N = 1024：

```
1024 × 2^30 = 2^40
```

32 位累加器必然不足，必须使用：

- 64 位累加器；
- 分块缩放；
- 系数归一化；
- 或限制输入和系数幅值。

## 8.2 选型决策矩阵

|条件|标量 C|intrinsic|CMSIS-DSP|手工汇编|
|---|---|---|---|---|
|维护性|5|4|4|2|
|性能|2|5|5|5|
|可移植性|5|3|4|1|
|可验证性|5|4|4|2|
|开发速度|5|3|5|1|
|编译器稳定性|4|4|4|2|
|推荐等级|基线|热点|默认首选|极限场景|

## 8.3 工业级编码规范

- 所有定点类型使用明确宽度：
    - `int16_t`；
    - `int32_t`；
    - `int64_t`。
- 禁止直接依赖 `short`、`long` 宽度。
- 禁止有符号整数溢出。
- 对所有右移明确区分：
    - 算术右移；
    - 逻辑右移。
- 对 Q 格式在接口和变量名中体现：
    - `sample_q15`；
    - `acc_q30`；
    - `gain_q31`。
- intrinsic 统一封装在平台加速层。
- 每个加速函数提供标量参考实现。
- 所有长度参数进行合法性检查。
- 明确规定内存对齐。
- 运行时性能测试使用 DWT 或硬件定时器，不使用 RTOS tick。
- 对 `INT16_MIN`、`INT32_MIN` 单独测试。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：把两个 Q15 乘积直接当 Q15 使用

### 错误代码

```
int16_t result = (int16_t)__SMLAD(a, b, 0);
```

### 根因

`SMLAD` 结果是两个 Q15 乘积的累加，通常属于 Q30 或更宽累加域，不能直接截断为 Q15。

### 正确实现

```
int32_t acc_q30 = __SMLAD(a, b, 0);
int16_t result_q15 = q30_to_q15_round_sat_safe(acc_q30);
```

### 风险影响

- 增益错误；
- 结果严重失真；
- 高位被直接丢弃；
- 可能出现控制环增益异常。

---

## 9.2 错误二：使用有符号溢出进行“快速饱和”

### 错误代码

```
int32_t sum = a + b;

if (sum < a) {
    sum = INT32_MAX;
}
```

### 根因

`a + b` 发生有符号溢出时，C 语言行为未定义。编译器可能基于“不会溢出”假设重排代码。

### 正确实现

```
static inline int32_t sat_add_i32_safe(int32_t a, int32_t b)
{
#if defined(__ARM_FEATURE_DSP)
    return __QADD(a, b);
#else
    int64_t sum = (int64_t)a + b;

    if (sum > INT32_MAX) {
        return INT32_MAX;
    }

    if (sum < INT32_MIN) {
        return INT32_MIN;
    }

    return (int32_t)sum;
#endif
}
```

### 风险影响

- 高优化等级下行为变化；
- 安全边界判断失效；
- 电机控制输出瞬时跳变；
- 认证测试无法复现。

---

## 9.3 错误三：忽略半字顺序

### 错误代码

```
uint32_t a = ((uint32_t)sample_a << 16) | sample_b;
uint32_t b = ((uint32_t)coeff_a << 16) | coeff_b;

int32_t result = __SMLAD(a, b, 0);
```

### 根因

调用者以为低半字是 `sample_a`，实际低半字是 `sample_b`。如果只做对称点积，问题可能不明显；在交叉乘法或复数算法中会导致结果错误。

### 正确实现

```
uint32_t a = pack_s16x2(sample_a, sample_b);
/* pack_s16x2 的第一个参数放低半字 */

uint32_t b = pack_s16x2(coeff_a, coeff_b);

int32_t result = __SMLAD(a, b, 0);
```

### 风险影响

- 复数实部/虚部错误；
- I/Q 通道互换；
- 相位偏移；
- 某些输入下测试通过、实际信号下失败。

---

## 9.4 错误四：奇数长度数组越界

### 错误代码

```
for (uint32_t i = 0; i < num_samples; i += 2U) {
    uint32_t x = pack_s16x2(samples[i], samples[i + 1U]);
    /* ... */
}
```

### 根因

当 `num_samples` 为奇数时，最后一次访问 `samples[num_samples]`，越过数组边界。

### 正确实现

```
static int32_t dot_q15_safe(
    const int16_t *samples,
    const int16_t *coeff,
    uint32_t length)
{
    if ((samples == NULL) || (coeff == NULL)) {
        return 0;
    }

    int32_t acc = 0;
    uint32_t i = 0;

    for (; (i + 1U) < length; i += 2U) {
        uint32_t x = pack_s16x2(samples[i], samples[i + 1U]);
        uint32_t c = pack_s16x2(coeff[i], coeff[i + 1U]);

        acc = __SMLAD(x, c, acc);
    }

    if (i < length) {
        acc += (int32_t)samples[i] * coeff[i];
    }

    return acc;
}
```

### 风险影响

- HardFault；
- 读取相邻对象；
- 结果非确定；
- 仅在特定数组布局下暴露。

---

## 9.5 错误五：没有检查目标内核是否支持 DSP

### 错误代码

```
#include "arm_math.h"

int32_t fast_dot(uint32_t a, uint32_t b)
{
    return __SMLAD(a, b, 0);
}
```

### 根因

编译配置可能把代码构建为 Cortex-M0/M3，但源代码直接使用 DSP intrinsic。

### 正确实现

```
static inline int32_t dot_pair(
    uint32_t a,
    uint32_t b,
    int32_t acc)
{
#if defined(__ARM_FEATURE_DSP)
    return __SMLAD(a, b, acc);
#else
    int16_t a0 = unpack_low_s16(a);
    int16_t a1 = unpack_high_s16(a);
    int16_t b0 = unpack_low_s16(b);
    int16_t b1 = unpack_high_s16(b);

    return acc + (int32_t)a0 * b0 + (int32_t)a1 * b1;
#endif
}
```

### 风险影响

- 编译失败；
- 错误生成非法指令；
- 固件在错误型号上运行触发 UsageFault；
- 多产品平台无法共用代码。

---

## 9.6 错误六：未定义的非对齐访问

### 错误代码

```
uint32_t value = *(const uint32_t *)&samples[i];
```

### 根因

- `samples` 可能只有 2 字节对齐；
- 类型别名规则可能被违反；
- 某些内核/总线对非对齐访问处理不同。

### 正确实现

```
static inline uint32_t load_s16x2_unaligned_safe(
    const int16_t *samples)
{
    return pack_s16x2(samples[0], samples[1]);
}
```

如果确定地址满足 4 字节对齐，可使用平台明确支持的加载方式，但必须通过接口契约保证：

```
typedef struct {
    uint32_t value;
} aligned_u32_t;
```

### 风险影响

- 总线错误；
- 性能下降；
- 编译器优化后行为不一致；
- DMA 与 CPU 看到的数据边界不一致。

---

## 10. 多机制组合使用方案

## 10.1 技术协同架构

一个工业级定点 DSP 模块通常由以下机制组合：

```
ADC/DMA
  |
  v
双缓冲采样区
  |
  v
Q15 数据预处理
  |
  +--> DC 去除：SADD16/QADD
  |
  +--> FIR：SMLAD
  |
  +--> 增益缩放：SMMLA/移位/舍入
  |
  +--> 限幅：SSAT/QADD
  |
  v
控制或通信输出
```

## 10.2 完整 FIR 框架

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "arm_math.h"

typedef struct {
    const int16_t *coeff;
    int16_t *state;

    uint32_t num_taps;
    uint32_t state_length;

    bool initialized;
} fir_q15_ctx_t;

static inline int16_t sat_q15_from_q30(int32_t value)
{
    int64_t rounded = (int64_t)value + (1LL << 14);
    int64_t result = rounded >> 15;

    if (result > INT16_MAX) {
        return INT16_MAX;
    }

    if (result < INT16_MIN) {
        return INT16_MIN;
    }

    return (int16_t)result;
}

bool fir_q15_init(
    fir_q15_ctx_t *ctx,
    const int16_t *coeff,
    int16_t *state,
    uint32_t num_taps)
{
    if ((ctx == NULL) ||
        (coeff == NULL) ||
        (state == NULL) ||
        (num_taps == 0U)) {
        return false;
    }

    ctx->coeff = coeff;
    ctx->state = state;
    ctx->num_taps = num_taps;
    ctx->state_length = num_taps;
    ctx->initialized = true;

    for (uint32_t i = 0; i < num_taps; ++i) {
        state[i] = 0;
    }

    return true;
}

bool fir_q15_process_one(
    fir_q15_ctx_t *ctx,
    int16_t input,
    int16_t *output)
{
    if ((ctx == NULL) ||
        (output == NULL) ||
        !ctx->initialized) {
        return false;
    }

    /*
     * 状态右移。
     * 对高吞吐场景，应改成环形缓冲区，避免 O(N) 搬移。
     */
    for (uint32_t i = ctx->num_taps - 1U; i > 0U; --i) {
        ctx->state[i] = ctx->state[i - 1U];
    }

    ctx->state[0] = input;

    int32_t acc_q30 = 0;
    uint32_t i = 0;

#if defined(__ARM_FEATURE_DSP)
    for (; (i + 1U) < ctx->num_taps; i += 2U) {
        uint32_t x = pack_s16x2(ctx->state[i], ctx->state[i + 1U]);
        uint32_t c = pack_s16x2(ctx->coeff[i], ctx->coeff[i + 1U]);

        acc_q30 = __SMLAD(x, c, acc_q30);
    }
#else
    for (; (i + 1U) < ctx->num_taps; i += 2U) {
        acc_q30 += (int32_t)ctx->state[i] * ctx->coeff[i];
        acc_q30 += (int32_t)ctx->state[i + 1U] * ctx->coeff[i + 1U];
    }
#endif

    if (i < ctx->num_taps) {
        acc_q30 += (int32_t)ctx->state[i] * ctx->coeff[i];
    }

    *output = sat_q15_from_q30(acc_q30);
    return true;
}
```

### 工程改进点

上述框架便于说明，但生产环境还应改进：

- 用环形缓冲区消除状态搬移；
- 批量处理多个样本；
- 将系数按 32 位预打包；
- 通过 DMA 双缓冲减少 CPU 等待；
- 对 Cortex-M7 处理 Cache 一致性；
- 对 Q30 累加范围进行静态证明；
- 对偶数 tap 和奇数 tap 提供不同专用路径。

---

## 10.3 RTOS + DMA 协同模式

```
DMA 半缓冲完成中断
       |
       v
ISR 仅做：
- 清中断
- 记录缓冲索引
- 发送事件/信号量
       |
       v
DSP 任务：
- 读取已完成缓冲
- 执行 Q15 FIR / FFT
- 检测饱和计数
- 输出结果
```

ISR 不应直接执行长 FIR，原因：

- 阻塞更高优先级中断；
- 增大系统中断延迟；
- 破坏实时调度；
- 难以处理 Cache 和缓冲区所有权。

---

## 11. 工业级实际案例分析

## 11.1 案例一：电机控制中的 Q15 电流环

### 需求

- PWM 频率：20 kHz；
- 电流采样同步于 PWM；
- 每个控制周期预算：50 μs；
- 需要执行：
    - ADC 偏置去除；
    - Clarke/Park 变换；
    - PI 控制；
    - 输出限幅；
- 不能出现整数环绕。

### 架构

```
PWM 触发 ADC
    |
    v
DMA 写入 ADC 缓冲
    |
    v
控制 ISR/高优先级任务
    |
    +--> Q15 偏置校正
    +--> Q15 乘加
    +--> QADD/QSUB
    +--> SSAT 输出限幅
    |
    v
更新 PWM 比较寄存器
```

### 核心代码

```
typedef struct {
    int32_t integrator_q31;
    int32_t kp_q15;
    int32_t ki_q15;
    int32_t output_limit_q15;
} pi_q15_t;

static int16_t pi_q15_step(
    pi_q15_t *pi,
    int16_t reference_q15,
    int16_t feedback_q15)
{
    if (pi == NULL) {
        return 0;
    }

    int32_t error_q15 =
        (int32_t)reference_q15 - (int32_t)feedback_q15;

    error_q15 = __SSAT(error_q15, 16U);

    /*
     * 比例项：
     * kp_q15 * error_q15 -> Q30
     */
    int32_t proportional_q30 =
        pi->kp_q15 * error_q15;

    /*
     * 积分项：
     * 根据具体缩放策略将结果转换到 Q31。
     * 此处使用 64 位避免中间溢出。
     */
    int64_t integral_delta =
        (int64_t)pi->ki_q15 * error_q15;

    integral_delta >>= 15;

    int64_t integrator_next =
        (int64_t)pi->integrator_q31 + integral_delta;

    if (integrator_next > INT32_MAX) {
        integrator_next = INT32_MAX;
    } else if (integrator_next < INT32_MIN) {
        integrator_next = INT32_MIN;
    }

    pi->integrator_q31 = (int32_t)integrator_next;

    int64_t output_q30 =
        (int64_t)proportional_q30 +
        ((int64_t)pi->integrator_q31 << 15);

    output_q30 >>= 15;

    if (output_q30 > pi->output_limit_q15) {
        output_q30 = pi->output_limit_q15;
    } else if (output_q30 < -pi->output_limit_q15) {
        output_q30 = -pi->output_limit_q15;
    }

    return (int16_t)output_q30;
}
```

### 设计要点

- 控制环不能只依赖 `QADD`，还要有积分抗饱和。
- 对 ADC 原始值先做范围校验。
- ISR 中禁止使用不可预测的动态内存。
- 必须测量：
    - ISR 最坏执行周期；
    - 中断抖动；
    - PWM 更新截止时间；
    - 饱和事件次数；
    - ADC 异常事件。

---

## 11.2 案例二：音频前端 FIR 降噪

### 需求

- 采样率：48 kHz；
- 单声道；
- 128 tap FIR；
- 处理块：64 samples；
- 目标：低于 10% CPU 占用；
- Q15 音频样本。

### 架构

```
I2S/SAI
  |
  v
DMA 双缓冲
  |
  v
音频任务
  |
  +--> 去直流
  +--> FIR
  +--> 软限幅
  +--> 输出 DMA
```

### 性能估算

每个输出样本需要约 128 次乘法：

```
总乘法次数 = 48,000 × 128 = 6,144,000 次/秒
```

若使用 `SMLAD`，理论双乘法次数：

```
6,144,000 / 2 = 3,072,000 条双 MAC/秒
```

在 168 MHz 下，纯 MAC 理论占比：

```
3,072,000 / 168,000,000 ≈ 1.83%
```

实际还要加上：

- 状态管理；
- 访存；
- DMA；
- Q 格式转换；
- Cache；
- RTOS 调度；
- 音频输出。

实际 CPU 占用可能为 **4%～12%** ，具体取决于实现和内存位置。

### 设计要点

- 系数放在只读区，尽量放入高速存储区域；
- 使用环形状态缓冲；
- 批量处理，减少函数调用；
- 对输入和输出采用 4 字节对齐；
- 监测削顶计数，避免静默音质退化；
- 音频场景下舍入策略比单纯截断更重要。

---

## 11.3 案例三：无线通信中的复数基带乘法

### 需求

- I/Q 数据为 Q15；
- 进行本振旋转、载波补偿或复数相关；
- 需要减少每个复数乘法的指令数；
- 关注相位误差和饱和失真。

### 核心代码

```
static inline void complex_mul_q15(
    int16_t ar,
    int16_t ai,
    int16_t br,
    int16_t bi,
    int16_t *out_r,
    int16_t *out_i)
{
    if ((out_r == NULL) || (out_i == NULL)) {
        return;
    }

    uint32_t a = pack_s16x2(ar, ai);
    uint32_t b = pack_s16x2(br, bi);

#if defined(__ARM_FEATURE_DSP)
    int32_t real_q30 = __SMLSD(a, b, 0);
    int32_t imag_q30 = __SMLADX(a, b, 0);
#else
    int32_t real_q30 =
        (int32_t)ar * br - (int32_t)ai * bi;

    int32_t imag_q30 =
        (int32_t)ar * bi + (int32_t)ai * br;
#endif

    *out_r = sat_q15_from_q30(real_q30);
    *out_i = sat_q15_from_q30(imag_q30);
}
```

### 设计要点

- `SMLSD` 和 `SMLADX` 的 lane 顺序必须通过测试向量验证。
- 测试至少包含：
    - `(1, 0) × (1, 0)`；
    - `(0, 1) × (1, 0)`；
    - 最大正数；
    - 最大负数；
    - 交叉符号组合；
    - 正负饱和边界。
- 如果输入接近满幅，复数乘法结果可能超出 Q15 范围，应在系统级考虑增益预留，例如保留 1～2 bit headroom。

---

## 12. 高频问题深度答疑

### 问题一：Cortex-M4 的 DSP 扩展是不是向量处理器？

不是传统意义上的完整向量处理器。

Cortex-M4 DSP 扩展的核心方式是：

```
一个 32 位寄存器
    |
    +--> 两个 16 位 lane
    |
    +--> 四个 8 位 lane
```

它没有通用向量寄存器文件，也没有 MVE 那样的向量谓词、向量长度和复杂向量访存机制。因此：

- 适合短整数并行；
- 适合低开销控制和信号处理；
- 不适合大规模矩阵和高维向量吞吐；
- 数据布局和打包方式对性能影响明显。

---

### 问题二：为什么使用 `SMLAD` 后速度没有提升两倍？

常见原因：

1. 数据没有预打包；
2. 打包成本抵消了双乘法收益；
3. 访存是瓶颈；
4. Flash 等待周期过高；
5. 循环没有展开；
6. 编译器生成了额外符号扩展；
7. 奇数长度尾部较长；
8. 函数调用和边界检查占比过大；
9. Cache 未命中；
10. 数据依赖导致流水线停顿。

双 MAC 的“两个乘法”只是 ALU 层面的理论能力，系统性能还取决于：

```
性能 = min(计算吞吐、访存吞吐、数据准备吞吐、调度吞吐)
```

---

### 问题三：Q15 和 Q31 应该如何选择？

|条件|推荐|
|---|---|
|输入动态范围中等，追求高吞吐|Q15|
|FIR tap 较多，需要更大累加空间|Q15 输入 + 64 位累加|
|控制算法需要较高分辨率|Q31|
|乘法结果需要高精度|Q31 或 64 位中间值|
|数据来自 12/16 位 ADC|通常可映射到 Q15|
|算法包含大量归一化和缩放|Q31 更灵活，但成本更高|
|有 FPU 且算法天然浮点|可评估单精度浮点|

选择不能只看精度，还要看：

- 指令支持；
- 累加宽度；
- 饱和频率；
- 内存带宽；
- 功耗预算；
- 测试和标定复杂度。

---

### 问题四：DSP 指令是否天然保证饱和？

不是。

必须区分：

- 普通加法：可能环绕；
- `SADD16`：半字级饱和；
- `QADD`：32 位饱和；
- `SMLAD`：乘加本身通常不是饱和乘加；
- `SSAT`：显式位宽限幅。

因此，不能因为某个路径使用了 DSP 指令，就认为整个算法没有溢出风险。需要建立完整的数值范围分析。

---

### 问题五：DSP intrinsic 和 CMSIS-DSP 应该怎么选？

推荐原则：

- **标准算法**：优先 CMSIS-DSP。
- **自定义热点**：使用 CMSIS-Core intrinsic。
- **平台无关基线**：保留纯 C 实现。
- **极端热点**：在 intrinsic 已不足时再考虑手工汇编。
- **需要迁移到 MVE 或其他架构**：优先算法级抽象，不要让业务层充斥 intrinsic。

CMSIS-DSP 的优势是：

- 已经处理了大量定点缩放；
- 提供经过验证的算法；
- 便于替换底层实现；
- 可统一做基准测试。

---

### 问题六：为什么不能直接通过指针强转加载两个 `int16_t`？

例如：

```
uint32_t x = *(uint32_t *)&samples[i];
```

风险包括：

- 对齐不满足；
- C 严格别名规则违反；
- 不同编译器行为不同；
- 端序导致 lane 解释不同；
- 某些内核的非对齐访问性能差或触发异常。

更可靠的方式是：

```
uint32_t x = pack_s16x2(samples[i], samples[i + 1U]);
```

如果性能测试证明打包成为瓶颈，应从数据结构和 DMA 布局层解决，而不是直接引入未定义行为。

---

## 13. 课程核心总结

### 核心要点

1. **Cortex-M DSP 扩展不是完整向量处理器，而是基于通用寄存器的窄位宽并行计算扩展。**
2. **`SMLAD` 是 Q15 FIR、点积和双路乘加的核心指令。**
3. **`SMLSD` 和 `SMLADX` 非常适合复数基带计算。**
4. **DSP 指令不会自动解决数值溢出，缩放、舍入和饱和必须由算法设计明确规定。**
5. **数据布局、对齐和访存路径通常决定最终性能。**
6. **CMSIS-DSP 适合标准算法，intrinsic 适合自定义热点，纯 C 实现应作为回退和参考模型。**
7. **必须通过反汇编确认编译器生成了目标 DSP 指令。**
8. **MVE/Helium 与传统 Cortex-M DSP 扩展属于不同层级的能力。**

### 性能排序

在典型定点热点场景下：

```
手工优化汇编 ≈ 高质量 intrinsic
    >
CMSIS-DSP 优化实现
    >
-O3 标量 C
    >
低优化标量 C
```

但从工程综合成本看：

```
CMSIS-DSP
    >
intrinsic 封装
    >
标量 C
    >
手工汇编
```

### 通用选型结论

- **低计算量**：标量 C。
- **标准 DSP 算法**：CMSIS-DSP。
- **双路 Q15 乘加热点**：`SMLAD`。
- **复数乘法**：`SMLSD` + `SMLADX`。
- **需要可靠限幅**：`QADD/QSUB/SSAT/USAT`。
- **需要动态归一化**：`CLZ`。
- **性能极限**：数据预打包 + 对齐 + 高速 SRAM/TCM + intrinsic + 反汇编验证。
- **大规模向量**：考虑 MVE/Helium，而不是仅依赖传统 DSP 扩展。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|数据格式|推荐指令/库|注意事项|
|---|---|---|---|
|双路 Q15 点积|Q15|`SMLAD`|输出为 Q30|
|复数实部|Q15|`SMLSD`|`ar*br - ai*bi`|
|复数虚部|Q15|`SMLADX`|`ar*bi + ai*br`|
|双路 Q15 加法|Q15|`SADD16`|半字级饱和|
|双路 Q15 减法|Q15|`SSUB16`|注意负溢出|
|32 位控制量加法|Q31|`QADD`|防止环绕|
|输出限幅|Q15/Q31|`SSAT/USAT`|明确位宽|
|动态归一化|Q31|`CLZ`|单独处理 0 和最小负数|
|FIR/FFT|Q15/Q31|CMSIS-DSP|优先使用成熟实现|
|MVE 可用平台|多种|Helium/MVE|不等同于 DSP 扩展|

### 14.2 特性对比表

|Intrinsic|功能|并行度|是否饱和|典型用途|
|---|---|---|---|---|
|`__SMLAD`|两个 16 位乘加|2|否|点积、FIR|
|`__SMLADX`|交叉双乘加|2|否|复数虚部|
|`__SMLSD`|双乘差分|2|否|复数实部|
|`__SADD16`|双 16 位加法|2|是|Q15 加法|
|`__SSUB16`|双 16 位减法|2|是|Q15 差分|
|`__QADD`|32 位饱和加法|1|是|控制积分|
|`__QSUB`|32 位饱和减法|1|是|误差计算|
|`__SSAT`|有符号限幅|1|是|输出限制|
|`__USAT`|无符号限幅|1|是|PWM/ADC|
|`__CLZ`|前导零统计|1|不适用|归一化|

---

## 15. 学习效果自检

### 架构理解

- [ ]  能解释 Cortex-M DSP 扩展与 MVE/Helium 的区别。
- [ ]  能判断某个内核是否支持 DSP 扩展。
- [ ]  能说明一个 32 位寄存器如何存放两个 Q15 元素。
- [ ]  能解释 `SMLAD` 的两个乘法如何映射到寄存器半字。

### 数值正确性

- [ ]  能计算 Q15 × Q15 的输出格式。
- [ ]  能判断 32 位累加器是否足够。
- [ ]  能正确处理 `INT16_MIN` 和 `INT32_MIN`。
- [ ]  能实现带舍入和饱和的 Q30 到 Q15 转换。
- [ ]  能区分截断、舍入、饱和和环绕。

### 指令使用

- [ ]  能使用 `SMLAD` 完成双路点积。
- [ ]  能使用 `SMLSD/SMLADX` 完成复数乘法。
- [ ]  能使用 `QADD/QSUB` 保护 32 位控制运算。
- [ ]  能使用 `SSAT/USAT` 做明确位宽限幅。
- [ ]  能使用 `CLZ` 实现 Q31 归一化。

### 工程实现

- [ ]  能处理奇数长度尾部。
- [ ]  能保证数据对齐。
- [ ]  能为 DSP 路径提供纯 C 回退实现。
- [ ]  能通过反汇编确认实际生成 DSP 指令。
- [ ]  能使用 DWT 测量周期。
- [ ]  能定位访存瓶颈而不是盲目增加 intrinsic。

### 架构设计

- [ ]  能设计 DMA 双缓冲与 DSP 任务协同。
- [ ]  能判断是否应该使用预打包数据。
- [ ]  能评估 DSP 扩展、FPU 和 CMSIS-DSP 的综合成本。
- [ ]  能建立饱和次数、最大周期和数据溢出的运行时监控。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：实现双路 Q15 点积

要求：

- 实现纯 C 版本；
- 实现 `SMLAD` 版本；
- 支持奇数长度；
- 对比输出结果；
- 测量周期；
- 测试随机数据和边界数据。

验收指标：

```
输出误差 = 0
或误差满足明确的定点量化误差界限
```

---

### 任务二：实现复数 Q15 乘法

要求：

- 使用 `SMLSD` 计算实部；
- 使用 `SMLADX` 计算虚部；
- 实现 Q30 到 Q15 的舍入与饱和；
- 与 Python/双精度浮点参考模型对比。

测试向量至少包括：

```
(1 + j0) × (1 + j0)
(j1) × (1 + j0)
(0 + j1) × (0 + j1)
最大正数和最大负数组合
```

---

### 任务三：实现双缓冲 FIR

要求：

- ADC/DMA 模拟输入；
- 半缓冲或整缓冲事件；
- DSP 任务处理；
- 不在 DMA 正在写入的缓冲区上计算；
- 统计每块处理最大周期；
- 检测超时和丢块。

---

### 任务四：实现 Q15 PI 控制器

要求：

- 比例项；
- 积分项；
- 输出限幅；
- 积分抗饱和；
- 异常输入保护；
- 饱和事件统计；
- 最坏执行周期测试。

---

### 任务五：对比 Cortex-M3、M4、M7、M33

要求记录：

|项目|M3|M4|M7|M33|
|---|---|---|---|---|
|是否支持 DSP|||||
|128 tap FIR 周期|||||
|代码大小|||||
|SRAM 数据路径|||||
|Flash 数据路径|||||
|最大中断延迟|||||

注意：

- 不能只比较主频；
- 应比较每周期完成量、存储系统和实际数据路径；
- M7 需要分别测试 Cache 开启、关闭、TCM 放置等条件。

## 16.2 性能测试方法

### DWT 周期计数

```
#include "core_cm4.h"

static void dwt_cycle_counter_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t dwt_measure_begin(void)
{
    return DWT->CYCCNT;
}

static uint32_t dwt_measure_end(uint32_t begin)
{
    return DWT->CYCCNT - begin;
}
```

测量时应：

- 关闭或屏蔽无关中断；
- 测试多次；
- 记录平均值、最大值和最小值；
- 分别测试 Cache 命中和未命中；
- 避免编译器删除测试代码；
- 对输入输出使用 `volatile` 或校验结果。

### 性能指标

建议至少记录：

```
cycles/sample
cycles/block
MAC/s
CPU utilization
code size
RAM usage
maximum saturation count
maximum numerical error
worst-case latency
```

## 16.3 进阶学习方向

1. **CMSIS-DSP 内核源码**
    
    - FIR；
    - Biquad；
    - Matrix；
    - FFT；
    - PID；
    - 基准测试框架。
2. **Cortex-M7 微架构**
    
    - 六级流水线；
    - 指令 Cache；
    - 数据 Cache；
    - TCM；
    - AXI/AHB 访问；
    - 分支预测和流水线停顿。
3. **ARMv8-M Mainline**
    
    - Cortex-M33；
    - TrustZone；
    - DSP 与安全域协同；
    - 浮点上下文保存。
4. **Helium/MVE**
    
    - 向量寄存器；
    - 谓词执行；
    - 向量加载/存储；
    - 向量化 FIR/FFT；
    - 与传统 DSP intrinsic 的迁移。
5. **定点数值分析**
    
    - 区间分析；
    - 位增长分析；
    - 块浮点；
    - 自动量化；
    - 定点误差传播。
6. **工业级验证**
    
    - 属性测试；
    - 静态分析；
    - MISRA C；
    - 故障注入；
    - WCET 分析；
    - ISO 26262/IEC 61508 软件组件验证。

**本课最终应形成的工程能力是：不仅会调用 `SMLAD`，而且能够证明它在目标 Cortex-M 内核上被正确生成、数值范围可控、性能收益可测量，并且可以安全地嵌入 RTOS、DMA 和工业控制系统中。**