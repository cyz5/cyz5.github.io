
## 1. 学习目标

### 理解

- 理解 CRC 的数学模型：生成多项式、初始值、输入反射、输出反射、最终异或值。
- 理解硬件 CRC 外设的移位寄存器、异或反馈、数据输入路径和状态寄存器。
- 理解软件 CRC、查表 CRC、硬件 CRC 在实时性、内存、可移植性方面的差异。
- 理解 DMA、总线宽度、字节序和硬件 CRC 数据打包之间的关系。

### 掌握

- 掌握 CRC-8、CRC-16、CRC-32 参数配置方法。
- 掌握硬件 CRC 外设初始化、复位、计算和结果读取。
- 掌握硬件 CRC 与协议帧校验、Flash 镜像校验、启动自检的集成方法。
- 掌握 CRC 结果与参考实现不一致时的定位流程。

### 精通

- 能够从任意 CRC 参数生成等价的软件模型和硬件配置。
- 能够分析不同 MCU CRC 外设对输入数据反射、输出反射、输入逆序和多项式宽度的支持限制。
- 能够处理硬件 CRC 与 DMA、Cache、非对齐地址、大小端转换的组合问题。
- 能够用测试向量、差分测试和边界测试验证驱动正确性。

### 能够设计

- 能够设计可移植的 CRC 抽象层，屏蔽不同 MCU 厂商硬件差异。
- 能够设计支持连续分段计算、协议校验、镜像完整性校验的工业级 CRC 服务。
- 能够设计硬件 CRC 失败回退到软件 CRC 的容错架构。
- 能够设计 CRC 性能基准测试和生产测试方案。

---

## 2. 前置要求

### 知识要求

- C 语言指针、数组、位运算、结构体和 `volatile`。
- MCU 时钟树、AHB/APB 总线和外设复位机制。
- 中断、DMA、Cache 和内存一致性基础。
- 二进制、十六进制、大小端和对齐概念。
- 基本通信协议帧结构，例如：

```
[地址][命令][长度][Payload][CRC]
```

### 技能要求

- 能够阅读 MCU Reference Manual 中的 CRC 章节。
- 能够配置 GPIO、时钟和基础外设。
- 能够使用逻辑分析仪、调试器和串口日志定位问题。
- 能够编译并运行裸机或 RTOS C 工程。
- 能够编写简单的软件 CRC 参考实现。

---

## 3. 技术概述

### 3.1 CRC 的定义

CRC，Cyclic Redundancy Check，循环冗余校验，本质上是对数据比特流进行有限域 GF(2) 多项式除法。

发送端将数据多项式 `M(x)` 左移 `n` 位后，除以生成多项式 `G(x)`，得到余数：

```
R(x) = [M(x) * x^n] mod G(x)
```

最终发送数据通常为：

```
Codeword(x) = M(x) * x^n XOR R(x)
```

接收端对完整码字重新计算，若余数为预期值，则认为数据通过校验。

CRC **可以发现随机传输错误，但不能证明数据绝对正确**。它不具备密码学完整性保护能力，攻击者可以主动构造匹配 CRC 的数据。

### 3.2 CRC 参数模型

一个 CRC 算法通常由以下参数定义：

|参数|含义|
|---|---|
|`Width`|CRC 宽度，例如 8、16、32|
|`Poly`|生成多项式，通常省略最高位 `x^Width`|
|`Init`|初始寄存器值|
|`RefIn`|每个输入字节是否按位反射|
|`RefOut`|输出是否按位反射|
|`XorOut`|最终异或值|
|`Check`|对字符串 `"123456789"` 的标准结果|
|`Residue`|完整码字校验后的标准余数|

典型 CRC-32/IEEE 参数：

```
Width  = 32
Poly   = 0x04C11DB7
Init   = 0xFFFFFFFF
RefIn  = true
RefOut = true
XorOut = 0xFFFFFFFF
Check  = 0xCBF43926
```

### 3.3 主流实现分类

|实现方式|核心机制|典型用途|
|---|---|---|
|按位软件 CRC|每个比特执行移位和异或|资源极小、低速场景|
|查表 CRC|以字节或半字节为索引查表|通用 MCU、高吞吐|
|硬件 CRC|外设内部 LFSR/多项式逻辑|高吞吐、低 CPU 占用|
|DMA + CRC|DMA 搬运数据，CRC 外设计算|大块内存、后台校验|
|SIMD/专用指令|CPU 指令或协处理器加速|高性能处理器、Linux|

---

## 4. 核心特性横向对比

以下数据以 **STM32F4，Cortex-M4，168 MHz，-O2** 为参考，实际数值取决于 Flash 等待周期、总线和编译器。

|维度|按位软件 CRC|256 字节查表|硬件 CRC|DMA + 硬件 CRC|
|---|---|---|---|---|
|CPU 周期/字节|80~150|15~30|2~8|CPU 主要承担配置|
|256 B CPU 周期|20k~38k|3.8k~7.7k|512~2k|约数百|
|代码空间|100~300 B|100~500 B|300~1.5 KB|1~3 KB|
|RAM 表空间|0|256×4 B 或 512 B|0|0|
|参数灵活性|高|高|取决于外设|取决于外设|
|是否占用 CPU|高|中|中低|极低|
|小数据延迟|低配置成本|低|有启停成本|高|
|大块吞吐|低|高|很高|很高|
|可移植性|高|高|低|低|
|适合实时短帧|可用|推荐|推荐|通常不推荐|
|适合 Flash 镜像|较慢|可用|推荐|推荐|
|与 Cache 交互|简单|简单|简单|需要维护一致性|

对于一个 1 MiB 镜像，假设硬件 CRC 实际吞吐为 20 MB/s：

```
T = Size / Throughput
  = 1 MiB / 20 MiB/s
  ≈ 50 ms
```

软件按位实现若只有 0.8 MB/s：

```
T ≈ 1 MiB / 0.8 MiB/s
  ≈ 1.25 s
```

---

## 5. 底层原理与功能特性深度解析

## 5.1 CRC 的 LFSR 实现

以宽度为 8 的非反射 CRC 为例：

```
#include <stdint.h>
#include <stddef.h>

uint8_t crc8_bitwise(const uint8_t *data,
                     size_t len,
                     uint8_t init,
                     uint8_t poly)
{
    uint8_t crc = init;

    if ((data == NULL) && (len != 0U)) {
        return 0U;
    }

    for (size_t i = 0U; i < len; ++i) {
        crc ^= data[i];

        for (uint32_t bit = 0U; bit < 8U; ++bit) {
            if ((crc & 0x80U) != 0U) {
                crc = (uint8_t)((crc << 1U) ^ poly);
            } else {
                crc <<= 1U;
            }
        }
    }

    return crc;
}
```

每次迭代本质上执行：

```
if (MSB == 1)
    CRC = (CRC << 1) XOR Poly
else
    CRC = CRC << 1
```

这里的 `Poly` 不包含最高次项。例如 CRC-8/ATM：

```
G(x) = x^8 + x^2 + x + 1
Poly = 0x07
```

### 关键点

- 非反射模型检查最高位。
- 反射模型检查最低位。
- `Width < 8` 时，必须限制寄存器有效位。
- C 语言左移前应使用足够宽的无符号类型，避免有符号溢出和未定义行为。

---

## 5.2 反射 CRC 的实现

CRC-32/IEEE 使用反射多项式：

```
0x04C11DB7 的反射形式为 0xEDB88320
```

反射版本：

```
uint32_t crc32_reflected(const uint8_t *data,
                         size_t len,
                         uint32_t init,
                         uint32_t poly,
                         uint32_t xor_out)
{
    uint32_t crc = init;

    if ((data == NULL) && (len != 0U)) {
        return 0U;
    }

    for (size_t i = 0U; i < len; ++i) {
        crc ^= data[i];

        for (uint32_t bit = 0U; bit < 8U; ++bit) {
            if ((crc & 1U) != 0U) {
                crc = (crc >> 1U) ^ poly;
            } else {
                crc >>= 1U;
            }
        }
    }

    return crc ^ xor_out;
}
```

CRC-32/IEEE 的验证：

```
#include <assert.h>
#include <string.h>

static void crc32_self_test(void)
{
    static const char text[] = "123456789";

    uint32_t result = crc32_reflected(
        (const uint8_t *)text,
        strlen(text),
        0xFFFFFFFFU,
        0xEDB88320U,
        0xFFFFFFFFU
    );

    assert(result == 0xCBF43926U);
}
```

**必须使用标准 Check 值进行验证**，不要仅通过少量业务数据验证。

---

## 5.3 查表 CRC

查表法将 8 次比特运算折叠为一次数组访问。

```
static uint32_t crc32_table[256];

static uint32_t reflect32(uint32_t value)
{
    uint32_t result = 0U;

    for (uint32_t i = 0U; i < 32U; ++i) {
        result <<= 1U;
        result |= value & 1U;
        value >>= 1U;
    }

    return result;
}

void crc32_table_init(uint32_t poly)
{
    for (uint32_t i = 0U; i < 256U; ++i) {
        uint32_t crc = i;

        for (uint32_t bit = 0U; bit < 8U; ++bit) {
            if ((crc & 1U) != 0U) {
                crc = (crc >> 1U) ^ poly;
            } else {
                crc >>= 1U;
            }
        }

        crc32_table[i] = crc;
    }
}

uint32_t crc32_table_update(uint32_t crc,
                            const uint8_t *data,
                            size_t len)
{
    if ((data == NULL) && (len != 0U)) {
        return crc;
    }

    for (size_t i = 0U; i < len; ++i) {
        uint8_t index = (uint8_t)(crc ^ data[i]);
        crc = (crc >> 8U) ^ crc32_table[index];
    }

    return crc;
}
```

工程中通常不建议运行时生成表，原因是：

- 增加启动时间。
- 可能存在并发初始化问题。
- 失去编译期常量特性。
- 表内容难以通过只读存储保护。

对于安全启动或可靠性要求高的系统，应将表定义为：

```
static const uint32_t crc32_table[256] = {
    /* 由离线工具生成 */
};
```

---

## 5.4 硬件 CRC 外设结构

典型 MCU CRC 外设包含：

```
+-------------------+
Input data --->| 输入数据寄存器     |
                +---------+---------+
                          |
                    数据重排/反射
                          |
                +---------v---------+
                | CRC 移位寄存器   |
                +---------+---------+
                          |
                     XOR feedback
                          |
                +---------v---------+
                | 多项式比较逻辑   |
                +---------+---------+
                          |
                +---------v---------+
                | CRC 结果寄存器   |
                +-------------------+
```

典型寄存器包括：

|寄存器|作用|
|---|---|
|`CR`|外设复位、启停控制|
|`DR`|输入数据和结果寄存器|
|`IDR`|独立 8 位寄存器，某些型号提供|
|`INIT`|初始 CRC 值|
|`POL`|可编程多项式|
|`POLYSIZE`|多项式宽度|
|`REV_IN`|输入数据反转|
|`REV_OUT`|输出反转|

不同 MCU 的寄存器命名和能力差异很大，必须以具体芯片 Reference Manual 为准。

---

## 5.5 硬件 CRC 驱动抽象

以下代码使用通用寄存器抽象，展示驱动边界。实际项目中应替换为厂商 HAL、LL 或 CMSIS 头文件定义。

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef struct {
    volatile uint32_t CR;
    volatile uint32_t DR;
    volatile uint32_t IDR;
    volatile uint32_t INIT;
    volatile uint32_t POL;
} crc_regs_t;

typedef struct {
    crc_regs_t *regs;
    uint32_t poly;
    uint32_t init;
    uint32_t xor_out;
    uint32_t width;
    bool ref_in;
    bool ref_out;
} crc_hw_t;

enum {
    CRC_OK = 0,
    CRC_EINVAL = -1,
    CRC_ESTATE = -2,
    CRC_EUNSUPPORTED = -3
};

static uint32_t width_mask(uint32_t width)
{
    if (width >= 32U) {
        return UINT32_MAX;
    }

    return (1UL << width) - 1UL;
}

int crc_hw_init(crc_hw_t *ctx)
{
    if ((ctx == NULL) || (ctx->regs == NULL)) {
        return CRC_EINVAL;
    }

    if ((ctx->width != 8U) &&
        (ctx->width != 16U) &&
        (ctx->width != 32U)) {
        return CRC_EUNSUPPORTED;
    }

    ctx->regs->POL = ctx->poly;
    ctx->regs->INIT = ctx->init;

    /*
     * 实际工程中还需配置：
     * - 多项式宽度
     * - 输入反转
     * - 输出反转
     * - CRC 外设时钟
     * - 外设复位
     */

    return CRC_OK;
}

int crc_hw_reset(crc_hw_t *ctx)
{
    if ((ctx == NULL) || (ctx->regs == NULL)) {
        return CRC_EINVAL;
    }

    /* 假设 bit 0 为 RESET，具体位定义以芯片手册为准。 */
    ctx->regs->CR |= 1UL;

    return CRC_OK;
}

int crc_hw_update_bytes(crc_hw_t *ctx,
                        const uint8_t *data,
                        size_t len,
                        uint32_t *result)
{
    if ((ctx == NULL) || (ctx->regs == NULL) ||
        (result == NULL) || ((data == NULL) && (len != 0U))) {
        return CRC_EINVAL;
    }

    for (size_t i = 0U; i < len; ++i) {
        /*
         * byte 写入是否有效，取决于 MCU 外设总线接口。
         * 某些 CRC 外设必须按 32 位写入，不能直接使用此方式。
         */
        *((volatile uint8_t *)&ctx->regs->DR) = data[i];
    }

    *result = ctx->regs->DR & width_mask(ctx->width);
    *result ^= ctx->xor_out;
    *result &= width_mask(ctx->width);

    return CRC_OK;
}
```

### 重要限制

不能假设以下行为在所有 MCU 上成立：

```
CRC->DR = byte;
CRC->DR = half_word;
CRC->DR = word;
```

某些硬件规定：

- 只能以 32 位访问 `DR`。
- 8 位写入会被硬件扩展为一个数据单元。
- 32 位写入时，字节顺序由 `REV_IN` 决定。
- 输入数据会按照总线写入宽度进行重排。
- 读取 `DR` 后结果才会锁存。

---

## 5.6 字节序和输入重排

假设内存中的数据为：

```
data[0] = 0x11
data[1] = 0x22
data[2] = 0x33
data[3] = 0x44
```

CPU 以小端方式读取 32 位整数：

```
uint32_t word = 0x44332211;
```

如果将该 `word` 写入 CRC 数据寄存器，硬件可能按照：

```
0x44, 0x33, 0x22, 0x11
```

处理，也可能通过 `REV_IN` 调整为另一种顺序。

因此，下面这种代码存在潜在问题：

```
uint32_t word = *(const uint32_t *)data;
CRC->DR = word;
```

风险包括：

- `data` 未对齐。
- 严格别名规则违反。
- CPU 大小端变化。
- CRC 外设的输入重排与 CPU 读取顺序不匹配。
- 尾部不足 4 字节的处理错误。

更稳妥的方式是使用 `memcpy` 读取，并显式定义数据顺序：

```
#include <string.h>

static uint32_t load_le32(const uint8_t *p)
{
    uint32_t value;

    memcpy(&value, p, sizeof(value));

#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    value = ((value & 0x000000FFUL) << 24U) |
            ((value & 0x0000FF00UL) << 8U)  |
            ((value & 0x00FF0000UL) >> 8U)  |
            ((value & 0xFF000000UL) >> 24U);
#endif

    return value;
}
```

但最终仍要结合具体 CRC 外设的 `REV_IN` 定义验证。

---

## 5.7 连续分段计算

CRC 具有可组合性：

```
CRC(A || B) = update(update(INIT, A), B)
```

因此可以分块计算：

```
uint32_t crc = crc32_start();

crc = crc32_update(crc, image, 4096U);
crc = crc32_update(crc, image + 4096U, image_size - 4096U);

crc = crc32_finish(crc);
```

不能在每个分块之间复位硬件 CRC：

```
/* 错误 */
for (...) {
    CRC_Reset();
    CRC_Feed(block);
}
```

这样得到的是每个块独立 CRC 的最后结果，而不是整个数据流的 CRC。

正确模式：

```
CRC_Reset();
for (...) {
    CRC_Feed(block);
}
result = CRC_Read();
```

---

## 5.8 DMA 与 CRC

对于大量数据，DMA 可以将内存内容持续写入 CRC 外设。

```
Flash/RAM
   |
   | DMA
   v
CRC->DR
   |
   v
CRC result
```

DMA 设计必须解决：

- 源地址是否可被 DMA 访问。
- 数据宽度是 byte、half-word 还是 word。
- 地址是否递增。
- CRC 外设是否支持 DMA 请求。
- DMA 完成中断与 CRC 结果读取的先后关系。
- D-Cache 是否需要清理或失效。
- 多任务环境下 CRC 外设是否被其他线程抢占。

伪代码框架：

```
int crc_dma_calculate(const void *buffer,
                      size_t length,
                      uint32_t *crc)
{
    if ((buffer == NULL) || (crc == NULL) || (length == 0U)) {
        return CRC_EINVAL;
    }

    crc_hw_reset_global();

    dma_disable();
    dma_config_source(buffer);
    dma_config_destination((void *)&CRC->DR);
    dma_config_length(length);
    dma_config_width(DMA_WIDTH_BYTE);
    dma_enable_interrupt();
    dma_enable();

    if (!dma_wait_complete(100U)) {
        dma_abort();
        return CRC_ESTATE;
    }

    *crc = CRC->DR;

    return CRC_OK;
}
```

真实产品中不应在任务中无限期阻塞等待，应使用：

- 中断 + 事件通知。
- RTOS 信号量。
- 超时和 DMA abort。
- 错误状态清理。
- 外设锁保护。

---

## 6. 性能量化分析

## 6.1 计算模型

单字节按位 CRC 通常执行 8 次循环：

```
T_bitwise ≈ N × 8 × (T_shift + T_test + T_xor)
```

查表 CRC：

```
T_table ≈ N × (T_load + T_index + T_load_table + T_shift + T_xor)
```

硬件 CRC：

```
T_hw ≈ T_enable + T_reset + N × T_bus_write + T_read
```

DMA + CRC：

```
T_dma ≈ T_config + N / BusThroughput + T_irq
```

### 参考测试数据

平台：

```
MCU: STM32F407VG
CPU: Cortex-M4 @ 168 MHz
Compiler: arm-none-eabi-gcc -O2
Memory: SRAM source, zero wait-state assumed
Data: 4096 bytes
```

|方案|典型耗时|CPU 占用|
|---|---|---|
|按位 CRC-32|1.9~3.7 ms|100%|
|256 项查表|0.35~0.70 ms|100%|
|硬件逐字节写入|0.10~0.35 ms|100%|
|硬件 32 位写入|0.03~0.10 ms|100%|
|DMA + 硬件 CRC|0.03~0.08 ms|配置和中断时间|

这些数据是工程估算范围，不应替代目标芯片上的实测结果。

## 6.2 实测方法

使用 DWT 周期计数器：

```
static void dwt_enable(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t measure_crc_cycles(const uint8_t *data, size_t len)
{
    uint32_t start;
    uint32_t end;
    uint32_t crc;

    DWT->CYCCNT = 0U;
    start = DWT->CYCCNT;

    crc = crc32_hw_calculate(data, len);

    end = DWT->CYCCNT;

    (void)crc;
    return end - start;
}
```

吞吐率：

```
Throughput = DataSizeBytes × CPUFrequencyHz / CycleCount
```

例如：

```
DataSize = 4096 B
CPU      = 168 MHz
Cycles   = 12000

Throughput = 4096 × 168000000 / 12000
           ≈ 57.3 MB/s
```

## 6.3 瓶颈分析

### 硬件 CRC 仍然很慢的原因

- 每个字节通过 HAL 函数调用，函数调用开销超过 CRC 运算本身。
- 使用错误的数据宽度。
- CRC 外设挂在低速 APB 总线。
- Flash 等待周期导致取数受限。
- DMA 配置为 byte 宽度，无法充分利用总线。
- 频繁复位 CRC 外设。
- Cache 未命中。
- RTOS 锁竞争或中断频繁打断。

### 优化收益

|优化措施|预期收益|
|---|---|
|HAL 循环改为直接寄存器访问|1.5~4 倍|
|byte 写入改为 word 写入|2~4 倍|
|分块复位改为一次复位|可减少大量固定开销|
|DMA 搬运|降低 CPU 占用 80% 以上|
|查表放入高速 SRAM|5%~30%|
|批量处理替代单包调用|降低函数和锁开销|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
开始
 |
 |-- 数据长度是否小于 16 字节？
 |       |
 |       +-- 是 --> 是否要求极高可移植性？
 |       |             |
 |       |             +-- 是 --> 软件 CRC
 |       |             +-- 否 --> 硬件 CRC 或查表 CRC
 |       |
 |       +-- 否
 |
 |-- 是否需要极低 CPU 占用？
 |       |
 |       +-- 是 --> 数据是否达到 DMA 适用阈值？
 |       |             |
 |       |             +-- 是 --> DMA + 硬件 CRC
 |       |             +-- 否 --> 硬件 CRC
 |       |
 |       +-- 否
 |
 |-- 是否要求跨平台结果完全一致？
 |       |
 |       +-- 是 --> 软件参考 CRC + 硬件差分验证
 |       +-- 否 --> 硬件 CRC
 |
 |-- 硬件 CRC 是否支持目标参数？
         |
         +-- 是 --> 硬件 CRC
         +-- 否 --> 查表 CRC 或按位 CRC
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|UART 16 字节控制帧|硬件 CRC 或查表 CRC|延迟低、调用频繁|
|CAN FD 数据帧|协议自带 CRC，不重复添加|总线协议已完成物理层校验|
|Modbus RTU|CRC-16/IBM，查表或硬件|参数固定、帧长中等|
|固件镜像校验|DMA + 硬件 CRC|数据量大、降低 CPU 占用|
|EEPROM 参数区|硬件 CRC|启动时快速检测|
|安全启动完整性|CRC 只能作为错误检测|必须叠加数字签名或 MAC|
|无硬件 CRC 的低端 MCU|查表 CRC|速度和空间平衡|
|极小 ROM 系统|按位 CRC|无额外表空间|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **把 CRC 参数作为协议的一部分固化**，不能只写“使用 CRC-16”。
2. **保存标准 Check 值**，启动测试或单元测试必须验证。
3. **硬件实现必须有软件黄金模型对照**。
4. **区分原始 CRC、最终 CRC 和传输字节序**。
5. **连续数据流只初始化一次**。
6. **硬件外设访问必须有并发保护**。
7. **大块数据优先使用 DMA，但小块数据不应盲目 DMA**。
8. **CRC 不等于安全认证**。

## 8.2 选型决策矩阵

|条件|按位|查表|硬件|DMA+硬件|
|---|---|---|---|---|
|ROM 极端受限|高|低|中|低|
|RAM 极端受限|高|中|高|高|
|参数灵活|高|高|中|中|
|CPU 占用低|低|低|中|高|
|调用数据很小|高|高|高|低|
|大块数据|低|中|高|高|
|可移植性|高|高|低|低|
|工程吞吐|低|中高|高|最高|

## 8.3 工业级编码规范

- 使用 `uint8_t`、`uint16_t`、`uint32_t`，避免 `unsigned long` 表示协议字段。
- 长度使用 `size_t` 或明确宽度的协议类型。
- 对 `(pointer == NULL && length != 0)` 做参数检查。
- 不能对非对齐指针直接强制转换为 `uint32_t *`。
- CRC 外设寄存器必须通过 `volatile` 访问。
- 驱动接口应返回错误码，不使用静默失败。
- 中断上下文中不得调用阻塞式 CRC 服务。
- 记录 CRC 参数、输入范围和结果字节序。

---

## 9. 常见错误与避坑指南

## 9.1 多项式方向错误

### 错误代码

```
crc = (crc << 1U) ^ 0xEDB88320U;
```

### 根因

`0xEDB88320` 是 CRC-32/IEEE 的反射多项式，应配合右移算法使用。

### 正确实现

```
if ((crc & 1U) != 0U) {
    crc = (crc >> 1U) ^ 0xEDB88320U;
} else {
    crc >>= 1U;
}
```

### 风险影响

所有 CRC 结果错误，且错误结果可能在简单测试中未被发现。

---

## 9.2 忽略 `RefIn` 和 `RefOut`

### 错误代码

```
uint32_t crc = crc32_non_reflected(data, len);
```

### 根因

协议使用 CRC-32/IEEE，但实现采用了非反射模型。

### 正确实现

```
uint32_t crc = crc32_reflected(
    data,
    len,
    0xFFFFFFFFU,
    0xEDB88320U,
    0xFFFFFFFFU
);
```

### 风险影响

设备之间互操作失败，通常表现为“发送端和接收端都认为自己正确”。

---

## 9.3 直接非对齐读取

### 错误代码

```
uint32_t word = *(const uint32_t *)(data + 1U);
```

### 根因

`data + 1` 可能没有满足 4 字节对齐要求；部分 Cortex-M 会触发异常，部分系统会产生额外总线访问。

### 正确实现

```
uint32_t word;
memcpy(&word, data + 1U, sizeof(word));
```

### 风险影响

HardFault、性能下降或不同编译器下行为不一致。

---

## 9.4 每个数据块都复位 CRC

### 错误代码

```
for (size_t offset = 0U; offset < length; offset += 256U) {
    CRC_Reset();
    CRC_Feed(data + offset, 256U);
}
```

### 根因

破坏了 CRC 的连续状态。

### 正确实现

```
CRC_Reset();

for (size_t offset = 0U; offset < length; offset += 256U) {
    size_t block = length - offset;

    if (block > 256U) {
        block = 256U;
    }

    CRC_Feed(data + offset, block);
}

uint32_t result = CRC_Read();
```

### 风险影响

镜像校验和流式协议校验结果错误。

---

## 9.5 将 CRC 当成安全机制

### 错误代码

```
if (crc32(image, size) == stored_crc) {
    jump_to_image();
}
```

### 根因

CRC 只能检测偶然错误，不能抵抗恶意篡改。

### 正确实现

```
if (!verify_signature(image, size, signature, public_key)) {
    return BOOT_AUTH_FAILED;
}

if (crc32(image, size) != stored_crc) {
    return BOOT_DATA_CORRUPTED;
}

jump_to_image();
```

### 风险影响

攻击者修改镜像后重新计算 CRC，即可绕过完整性检查。

---

## 10. 多机制组合使用方案

## 10.1 分层架构

```
+--------------------------------------------------+
| 业务层：协议帧 / 固件镜像 / 参数区               |
+--------------------------------------------------+
| CRC 服务层：CRC-16 / CRC-32 / 流式接口           |
+--------------------------------------------------+
| 硬件抽象层：硬件 CRC、DMA、软件回退              |
+--------------------------------------------------+
| MCU 适配层：寄存器、时钟、Cache、RTOS 锁         |
+--------------------------------------------------+
| 芯片硬件：CRC 外设、DMA、SRAM、Flash             |
+--------------------------------------------------+
```

## 10.2 统一接口

```
typedef enum {
    CRC_ALG_CRC16_MODBUS,
    CRC_ALG_CRC32_IEEE
} crc_algorithm_t;

typedef struct crc_service crc_service_t;

int crc_service_open(crc_service_t *service,
                     crc_algorithm_t algorithm);

int crc_service_start(crc_service_t *service);

int crc_service_update(crc_service_t *service,
                       const void *data,
                       size_t length);

int crc_service_finish(crc_service_t *service,
                       uint32_t *result);

void crc_service_close(crc_service_t *service);
```

## 10.3 硬件优先、软件回退

```
int crc_service_update(crc_service_t *service,
                       const void *data,
                       size_t length)
{
    if ((service == NULL) ||
        ((data == NULL) && (length != 0U))) {
        return CRC_EINVAL;
    }

    if (service->backend == CRC_BACKEND_HW) {
        int ret = crc_hw_update(
            &service->hw,
            (const uint8_t *)data,
            length
        );

        if (ret == CRC_OK) {
            return CRC_OK;
        }

        /*
         * 硬件异常时，不能直接切换并继续使用未定义状态。
         * 必须使用当前已确认的流状态重新初始化软件后端。
         */
        service->backend = CRC_BACKEND_SW;
        service->sw_crc = service->processed_crc;
    }

    service->sw_crc = crc_sw_update(
        service->sw_crc,
        (const uint8_t *)data,
        length
    );

    service->processed_crc = service->sw_crc;
    return CRC_OK;
}
```

需要注意：如果硬件已经处理了部分数据但发生异常，软件回退必须知道**最后一个已成功处理的边界**。不能简单从未知硬件状态继续。

---

## 11. 工业级实际案例分析

## 11.1 案例一：Modbus RTU 从站帧校验

### 需求

- UART 接收 8~256 字节帧。
- CRC-16/MODBUS。
- 115200 bps。
- 不阻塞接收任务。
- 错误帧必须丢弃，不得进入命令解析器。

### CRC 参数

```
Width  = 16
Poly   = 0x8005
RefIn  = true
RefOut = true
Init   = 0xFFFF
XorOut = 0x0000
```

反射计算使用：

```
Poly = 0xA001
```

### 核心代码

```
static uint16_t modbus_crc16_update(uint16_t crc,
                                    const uint8_t *data,
                                    size_t len)
{
    for (size_t i = 0U; i < len; ++i) {
        crc ^= data[i];

        for (uint32_t bit = 0U; bit < 8U; ++bit) {
            if ((crc & 1U) != 0U) {
                crc = (uint16_t)((crc >> 1U) ^ 0xA001U);
            } else {
                crc >>= 1U;
            }
        }
    }

    return crc;
}

bool modbus_frame_valid(const uint8_t *frame, size_t frame_len)
{
    if ((frame == NULL) || (frame_len < 4U)) {
        return false;
    }

    uint16_t calculated = modbus_crc16_update(
        0xFFFFU,
        frame,
        frame_len - 2U
    );

    uint16_t received =
        (uint16_t)frame[frame_len - 2U] |
        ((uint16_t)frame[frame_len - 1U] << 8U);

    return calculated == received;
}
```

### 设计要点

- Modbus CRC 低字节先传输。
- CRC 校验范围不包括 CRC 字段自身。
- 接收状态机应先判断地址、功能码、长度，再校验 CRC。
- UART 空闲中断可用于判断帧结束。
- 对于短帧，DMA 配置成本可能高于直接软件或硬件逐字节计算。

---

## 11.2 案例二：固件镜像启动校验

### 需求

- 镜像位于外部 QSPI Flash。
- 镜像大小最大 4 MiB。
- 启动时间预算 300 ms。
- 需要检测存储介质位翻转和升级中断。
- 另有数字签名用于防篡改。

### 镜像头

```
typedef struct {
    uint32_t magic;
    uint32_t image_size;
    uint32_t image_version;
    uint32_t image_crc32;
    uint8_t  signature[64];
} image_header_t;
```

### 核心流程

```
读取镜像头
 |
 |-- magic 正确？
 |       +-- 否 --> 拒绝启动
 |
 |-- image_size 在合法范围？
 |       +-- 否 --> 拒绝启动
 |
 |-- 验证数字签名
 |       +-- 失败 --> 拒绝启动
 |
 |-- DMA + 硬件 CRC 计算镜像
 |       +-- 超时/总线错误 --> 拒绝启动
 |
 |-- CRC 与头部一致？
         +-- 否 --> 回滚或进入升级模式
         +-- 是 --> 设置向量表并跳转
```

### 设计要点

- 计算范围必须明确：是否包含镜像头、签名区和填充区。
- 外部 Flash DMA 访问能力需确认，某些 QSPI 控制器的 memory-mapped 区域不支持 DMA。
- Cortex-M7 使用 D-Cache 时，外设写入后的数据读取需要执行 Cache 维护。
- 镜像 CRC 用于传输和存储错误检测，签名用于身份认证。
- 启动代码必须检查向量表地址和初始栈指针范围。

---

## 11.3 案例三：工业控制器参数区冗余校验

### 需求

- 参数区双备份。
- 每份参数 2 KB。
- 掉电写入不能产生不可恢复状态。
- 启动时选择最新且 CRC 正确的版本。

### 参数结构

```
typedef struct {
    uint32_t magic;
    uint32_t generation;
    uint32_t payload_size;
    uint32_t payload_crc;
    uint8_t  payload[2048];
} parameter_slot_t;
```

### 选择策略

```
Slot A CRC 正确？ Slot B CRC 正确？
        |
        +-- 都正确 --> 选择 generation 较大的
        |
        +-- 仅 A 正确 --> 选择 A
        |
        +-- 仅 B 正确 --> 选择 B
        |
        +-- 都错误 --> 使用编译期默认参数
```

### 设计要点

- `generation` 溢出比较不能直接使用普通大小比较。
- Flash 擦写过程中掉电时，旧备份必须保持有效。
- 参数校验应覆盖版本、长度和 Payload。
- 不能只校验 Payload 而不校验元数据。
- 写入顺序应为：擦除备用区、写 Payload、写 CRC、最后写 Commit 标志。

---

## 12. 高频问题深度答疑

### 问题一：为什么同一个 CRC 多项式有多个结果？

因为 CRC 不仅由 `Poly` 决定，还受以下参数影响：

- `Init`
- `RefIn`
- `RefOut`
- `XorOut`
- 数据处理范围
- CRC 字段传输顺序

因此“CRC-16”不是完整算法名称。工程文档必须写完整参数集合。

### 问题二：硬件 CRC 结果为什么和在线工具不同？

优先检查：

1. 在线工具使用的具体算法名称。
2. 输入是否包含换行符。
3. `Init` 是否正确。
4. 输入和输出反射是否一致。
5. 最终异或值是否一致。
6. 硬件是否按 byte、half-word、word 重新排列输入。
7. 结果是否需要按字节交换。
8. 是否误将 CRC 字段本身纳入计算。

### 问题三：CRC 是否适合防止固件被篡改？

不适合。CRC 是线性校验，攻击者可以修改数据并重新计算 CRC。固件安全启动应使用：

```
Hash + 数字签名
```

或：

```
消息认证码 MAC
```

CRC 可以作为额外的快速存储错误检测层。

### 问题四：小数据是否应该使用 DMA？

通常不应该。DMA 有固定开销：

```
T_dma = T_config + T_transfer + T_irq
```

当数据量较小时：

```
T_config + T_irq > CPU_direct
```

对于 8~32 字节协议帧，直接硬件写入或查表通常更合适。应通过实测确定阈值，而不是凭经验固定。

### 问题五：多个任务能否共享 CRC 外设？

可以，但必须保证一次连续计算期间的状态不被破坏。

方案包括：

- 全局互斥锁。
- CRC 服务任务串行化请求。
- 每个请求保存软件状态。
- 禁止在中断中直接使用共享 CRC 外设。
- 大块 DMA 计算期间避免其他任务抢占同一外设。

若系统高频使用 CRC，推荐建立专用 CRC 服务任务。

### 问题六：硬件 CRC 能否通过多次调用完成同一次计算？

可以，前提是：

- 第一次调用前复位并加载 `Init`。
- 后续调用不复位。
- 所有分段使用同一参数。
- 中途不被其他任务修改外设状态。
- 最后一次调用后再读取和执行 `XorOut`。

---

## 13. 课程核心总结

### 核心要点

- **CRC 是参数化算法，不是单独的多项式。**
- **硬件 CRC 的主要风险不是计算逻辑，而是数据宽度、字节序和反射配置。**
- **连续分段计算必须保持 CRC 内部状态。**
- **DMA 主要降低 CPU 占用，不一定降低小数据延迟。**
- **CRC 用于错误检测，不用于安全认证。**
- **硬件实现必须使用软件黄金模型和标准 Check 值验证。**

### 性能排序

在大块数据场景中，通常为：

```
DMA + 硬件 CRC > 硬件 CRC > 查表 CRC > 按位 CRC
```

在小数据低延迟场景中，通常为：

```
查表 CRC ≈ 硬件直接访问 > 按位 CRC > DMA + 硬件 CRC
```

### 通用选型结论

- **短帧、高频调用**：硬件直接访问或查表。
- **大块内存校验**：DMA + 硬件 CRC。
- **无硬件外设**：查表 CRC。
- **极端 ROM 约束**：按位 CRC。
- **需要安全防篡改**：CRC 叠加 Hash、MAC 或数字签名。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选|
|---|---|
|8~32 字节短帧|硬件直接访问|
|32~512 字节普通协议帧|硬件 CRC 或查表|
|4 KB 以上镜像|DMA + 硬件 CRC|
|硬件参数不支持|查表 CRC|
|无额外 RAM|硬件 CRC 或按位 CRC|
|安全启动|签名验证 + CRC 辅助|
|跨平台参考实现|软件黄金模型|

### 14.2 特性对比表

|项目|非反射|反射|
|---|---|---|
|移位方向|左移|右移|
|判断位|MSB|LSB|
|多项式示例|`0x04C11DB7`|`0xEDB88320`|
|常见算法|CRC-32/MPEG-2|CRC-32/IEEE|
|硬件配置重点|`REV_IN=NONE`|输入/输出反射配置|
|常见错误|使用反射多项式|使用非反射多项式|

### 14.3 验证清单

```
[ ] 算法完整名称已明确
[ ] Width 已确认
[ ] Poly 已确认
[ ] Init 已确认
[ ] RefIn 已确认
[ ] RefOut 已确认
[ ] XorOut 已确认
[ ] "123456789" Check 值通过
[ ] 空数据行为已定义
[ ] 单字节、非对齐、非 4 字节长度已测试
[ ] 硬件与软件结果一致
[ ] DMA 和 Cache 一致性已验证
[ ] 并发访问已保护
```

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  为什么 CRC-32/IEEE 使用 `0xEDB88320` 进行右移计算？
- [ ]  `Poly`、`Init`、`RefIn`、`RefOut`、`XorOut` 各自如何影响结果？
- [ ]  如何验证一个硬件 CRC 外设的配置是正确的？
- [ ]  为什么直接将 `uint8_t *` 转换为 `uint32_t *` 存在风险？
- [ ]  为什么分段 CRC 计算不能每段都复位？
- [ ]  DMA + CRC 的固定开销由哪些部分组成？
- [ ]  Cortex-M7 的 D-Cache 会如何影响 DMA CRC？
- [ ]  Modbus CRC 的传输字节顺序是什么？
- [ ]  CRC 为什么不能替代数字签名？
- [ ]  如何设计硬件失败后的软件回退？
- [ ]  如何保护 RTOS 多任务环境下的 CRC 外设？
- [ ]  如何确定直接计算与 DMA 计算的切换阈值？

---

## 16. 实践与进阶路径

### 阶段一：基础实现

1. 实现 CRC-8/ATM 按位算法。
2. 实现 CRC-16/MODBUS 反射算法。
3. 实现 CRC-32/IEEE 查表算法。
4. 使用 `"123456789"` 验证标准 Check 值。
5. 增加空指针、零长度、超长输入测试。

### 阶段二：硬件驱动

1. 阅读目标 MCU CRC Reference Manual。
2. 确认：
    - 多项式宽度
    - 可编程多项式
    - 初始值
    - 输入反转
    - 输出反转
    - 数据寄存器访问宽度
3. 实现硬件 CRC 单次计算。
4. 实现连续分段计算。
5. 使用软件黄金模型进行逐字节差分测试。

### 阶段三：协议集成

1. 实现 Modbus RTU 帧 CRC 校验。
2. 将 CRC 集成到 UART DMA 接收状态机。
3. 测试：
    - 缺字节
    - 多字节
    - 中间字节翻转
    - CRC 字段翻转
    - 超时截断
4. 统计错误帧率和校验耗时。

### 阶段四：DMA 和性能测试

1. 对 16 B、64 B、256 B、4 KB、64 KB 数据分别测试。
2. 比较：
    - 按位 CRC
    - 查表 CRC
    - 硬件逐字节
    - 硬件字访问
    - DMA + 硬件
3. 使用 DWT 记录周期数。
4. 测量中断延迟、CPU 占用和总线带宽。
5. 找出 DMA 切换阈值。

### 阶段五：工业级扩展

1. 实现统一 CRC 服务层。
2. 增加 RTOS 互斥和超时。
3. 增加硬件 CRC 异常恢复。
4. 增加软件后端回退。
5. 实现 Flash 参数区双备份。
6. 实现固件镜像 CRC 校验。
7. 叠加 SHA-256 和数字签名，形成完整安全启动链路。

### 进阶方向

- CRC 参数自动生成工具。
- CRC 多项式的错误检测能力分析。
- Hamming Distance 与最大检错长度。
- CRC 与 Reed-Solomon、FEC 的组合。
- STM32、NXP、TI、Renesas CRC 外设差异适配。
- Cortex-M7 Cache、MPU 与 DMA 一致性设计。
- 多核 MCU 中 CRC 外设资源仲裁。
- 硬件安全模块中的 CRC、Hash 和 MAC 协同。