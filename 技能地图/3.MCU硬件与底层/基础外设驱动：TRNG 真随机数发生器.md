
> 本课以**典型 MCU 硬件 TRNG/RNG 外设**为主线，参考 STM32 RNG、NXP RNGA、Nordic RNG、Microchip TRNG 等常见实现。不同芯片的寄存器名称、熵源结构和健康检测机制存在差异，工程落地时必须以具体芯片参考手册、勘误表和安全手册为准。  
> 本课中的示例代码采用**硬件抽象层 + 驱动状态机 + 健康检测 + 上层随机源接口**的工业级组织方式。

---

# 1. 学习目标

## 1.1 理解

完成本课后，应能够：

- 理解 **TRNG、PRNG、CSPRNG、DRBG** 的概念和安全边界。
- 理解硬件随机数发生器的基本熵源：
    - 振荡器抖动；
    - 热噪声；
    - 亚稳态采样；
    - 时钟相位噪声；
    - 模拟噪声放大链路。
- 理解 TRNG 数据路径：

```
物理熵源
  ↓
模拟前端 / 振荡器
  ↓
采样器
  ↓
去偏 / 后处理
  ↓
熵池或数据寄存器
  ↓
状态检测 / 错误标志
  ↓
软件驱动
```

- 理解 TRNG 与系统启动、安全启动、密钥生成、协议 nonce、设备身份等模块之间的关系。
- 理解**随机数可用性、随机性质量和密码学安全性并不等价**。

## 1.2 掌握

能够：

- 编写基本 TRNG 初始化、读取、超时和错误处理代码。
- 正确处理：
    - 数据未就绪；
    - 时钟未开启；
    - 熵源故障；
    - 时钟错误；
    - 健康测试失败；
    - 读取超时；
    - 中断竞争；
    - 低功耗恢复。
- 设计阻塞式和非阻塞式 TRNG 接口。
- 建立 TRNG 驱动的错误分层和恢复策略。
- 通过测试验证：
    - 输出吞吐率；
    - 等待延迟；
    - 错误率；
    - 连续输出异常；
    - 低功耗唤醒后的可用性。

## 1.3 精通

能够深入分析：

- TRNG 的熵率与输出比特率之间的关系。
- 为什么“通过 NIST 随机性测试”不能直接证明“适合生成密钥”。
- 为什么硬件 RNG 需要结合：
    - 健康检测；
    - 熵池；
    - CSPRNG/DRBG；
    - 启动阶段故障闭锁；
    - 运行时监控。
- TRNG 在 RTOS 中的并发访问、优先级、超时和故障传播问题。
- TRNG 读数为什么可能受到：
    - 主频；
    - RNG 时钟；
    - 温度；
    - 电源；
    - EMI；
    - 低功耗模式；
    - 芯片批次和工艺差异影响。

## 1.4 能够设计

能够设计：

- 面向裸机、RTOS 和嵌入式 Linux 的统一随机源架构。
- 基于 TRNG 初始化 DRBG/CSPRNG 的系统。
- 支持故障降级、故障闭锁和审计日志的安全随机数服务。
- 面向 TLS、OTA、密钥生成、安全启动和设备配网的随机数解决方案。
- 符合产品安全要求的 TRNG 验证、测试和现场诊断方案。

---

# 2. 前置要求

## 2.1 知识要求

|知识域|要求|
|---|---|
|C 语言|指针、结构体、枚举、位操作、`volatile`、内存可见性|
|MCU 架构|时钟树、外设复位、寄存器访问、中断控制|
|RTOS|任务、互斥锁、信号量、事件、临界区|
|密码学基础|哈希、MAC、密钥、nonce、IV、DRBG 基本概念|
|软件架构|驱动层、服务层、错误码、状态机|
|测试工程|延迟、吞吐量、故障注入、统计测试|

## 2.2 技能要求

应具备以下能力：

- 根据参考手册配置外设寄存器。
- 阅读芯片勘误表，识别 RNG 相关限制。
- 使用逻辑分析仪、示波器、Trace、DWT 或高精度定时器进行性能测量。
- 能够编写寄存器级或 HAL 级外设驱动。
- 能够搭建连续数据采集和离线统计分析工具。
- 能够处理 RTOS 中的并发访问和错误恢复。

---

# 3. 技术概述

## 3.1 TRNG 的定义

TRNG，即 True Random Number Generator，是真随机数发生器。

它从物理世界中的不可预测过程提取熵，例如：

- 热噪声；
- 振荡器频率抖动；
- 雪崩噪声；
- 电路亚稳态；
- ADC 低位噪声；
- 时钟相位噪声。

与普通伪随机数发生器相比，TRNG 的核心区别是：

> **输出不可由有限状态和已知种子完全预测。**

但需要注意，TRNG 芯片输出通常已经经过数字后处理，并不一定是原始物理噪声。

## 3.2 TRNG、PRNG、CSPRNG、DRBG 对比

|类型|熵来源|可预测性|典型用途|是否适合生成密钥|
|---|---|---|---|---|
|普通 PRNG|软件种子|可预测|仿真、游戏、测试|否|
|CSPRNG|安全种子 + 密码算法|计算上不可预测|协议随机数、令牌、nonce|依赖种子质量|
|DRBG|熵输入 + 标准算法|计算上不可预测|大量随机数据生成|是|
|TRNG|物理随机过程|理论上不可预测|熵采集、密钥种子|是，但需健康检测|
|TRNG + DRBG|物理熵 + 密码学扩展|最佳工程组合|安全产品|推荐|

### 工程结论

**TRNG 不应该简单等价于“每次业务调用都直接读硬件寄存器”。**

更合理的架构通常是：

```
TRNG
  ↓ 提供高质量熵
熵池 / DRBG 初始化
  ↓
CSPRNG / DRBG
  ↓
协议 nonce、临时密钥、随机挑战、令牌
```

原因：

1. TRNG 吞吐率可能较低。
2. 直接暴露硬件输出会增加并发和错误处理复杂度。
3. DRBG 可以提供确定性的高吞吐扩展。
4. TRNG 故障可以通过熵池健康检测和系统策略统一处理。

## 3.3 常见 TRNG 实现分支

### 3.3.1 振荡器抖动型

两个频率不同的振荡器进行异步采样，利用相位差随时间变化产生随机比特。

```
高速振荡器 ─────┐
                ├─ 异步采样 ─ 去偏 / 后处理 ─ 输出
低速振荡器 ─────┘
```

优点：

- MCU 内部集成方便；
- 无需外部器件；
- 功耗和面积较低。

风险：

- 对电源、温度、时钟配置较敏感；
- EMI 或时钟异常可能降低熵质量；
- 不同芯片实现差异很大。

### 3.3.2 模拟噪声型

通过模拟噪声源、放大器、比较器和采样器产生随机比特。

优点：

- 物理熵来源较直接；
- 某些高安全等级芯片中常见。

风险：

- 模拟设计复杂；
- 对电源和版图要求高；
- 可能需要启动校准和健康检测。

### 3.3.3 ADC 噪声型

读取 ADC 低位噪声或专用噪声通道。

优点：

- 某些低成本 MCU 可用；
- 硬件复用度高。

缺点：

- 通常需要软件提取和去偏；
- 受外部环境和电路设计影响大；
- **不应直接将普通 ADC 低位当作密码学随机源**。

### 3.3.4 外部安全器件型

使用外部安全芯片或专用随机数芯片。

优点：

- 可具备认证、密钥存储和安全随机源；
- 安全边界更清晰。

缺点：

- 增加 BOM、成本和通信延迟；
- 需要处理 I²C/SPI 线路攻击和故障注入；
- 需要评估外部器件是否真正提供合规随机源。

---

# 4. 核心特性横向对比

## 4.1 不同随机源方案对比

|维度|`rand()`|软件 PRNG|MCU TRNG|TRNG + DRBG|外部安全芯片|
|---|---|---|---|---|---|
|物理熵|无|依赖种子|有|有|有|
|可预测性|高|取决于种子|低，依赖实现|低|低|
|吞吐率|高|高|中低|高|中|
|启动复杂度|低|中|中|高|高|
|认证能力|无|无|取决于芯片|取决于系统|通常较强|
|故障检测|无|无|通常有|可扩展|通常有|
|适合密钥生成|否|通常否|是，需验证|推荐|推荐|
|对时钟依赖|低|低|高|中|低到中|
|对电源敏感性|低|低|中到高|中|中|
|维护成本|低|低|中|高|高|

## 4.2 阻塞式、非阻塞式、中断式、DMA 式对比

|方案|API 特征|优点|缺点|适用场景|
|---|---|---|---|---|
|阻塞轮询|`get_u32(timeout)`|简单、确定性强|占用 CPU，可能阻塞|启动阶段、低频调用|
|非阻塞轮询|`try_get_u32()`|不阻塞任务|调用方需要重试|主循环、实时任务|
|中断式|数据就绪中断|CPU 利用率高|并发和状态机复杂|RTOS、持续采样|
|DMA 式|自动搬运数据|批量吞吐高|配置复杂，安全审查困难|大量熵采集|
|DRBG 扩展|`random_bytes()`|高吞吐，低延迟|依赖可靠熵种子|TLS、协议、密钥派生|

## 4.3 数据宽度和接口形式对比

|接口|优点|风险|
|---|---|---|
|32 位读取|与多数 RNG 寄存器一致|上层容易误认为每次都是独立 32 bit 熵|
|字节流读取|适合协议和密码库|需要处理剩余字节缓存|
|熵块读取|适合 DRBG reseed|需要明确熵量和健康检测|
|直接寄存器访问|延迟低|绕过错误处理和锁|
|统一服务接口|架构清晰|需要设计生命周期和错误传播|

---

# 5. 底层原理与功能特性深度解析

## 5.1 典型 RNG 硬件模块结构

以常见 MCU RNG 为例，逻辑结构通常如下：

```
[熵源振荡器]
      │
      ▼
[异步采样器]
      │
      ▼
[去偏 / 后处理]
      │
      ▼
[32-bit 数据寄存器]
      │
      ├── DRDY：数据就绪
      ├── SEIS：种子错误
      ├── CEIS：时钟错误
      └── IE：中断使能
```

软件通常不能直接控制熵源内部细节，只能：

1. 配置 RNG 外设时钟；
2. 解除复位；
3. 开启 RNG；
4. 等待数据就绪；
5. 读取数据寄存器；
6. 检查错误标志；
7. 必要时执行复位或重新初始化。

## 5.2 时钟配置是 TRNG 正确性的前提

很多 MCU 的 RNG 对输入时钟有约束：

- 必须来自专用 PLL；
- 频率必须处于规定范围；
- 不能在某些低功耗模式下运行；
- 时钟频率不能过低；
- 时钟占空比、抖动或来源可能影响熵质量。

错误示例：

```
/* 错误：仅打开 RNG 外设时钟，没有检查 RNG 时钟源 */
RCC->AHB2ENR |= RCC_AHB2ENR_RNGEN;
RNG->CR |= RNG_CR_RNGEN;
```

问题：

- RNG 的专用时钟可能没有配置；
- RNG 可能一直不产生数据；
- 可能持续产生时钟错误；
- 部分芯片上会触发错误中断风暴。

工程化初始化应明确时钟配置状态：

```
typedef enum {
    TRNG_OK = 0,
    TRNG_E_PARAM,
    TRNG_E_CLOCK,
    TRNG_E_TIMEOUT,
    TRNG_E_SEED,
    TRNG_E_CLOCK_FAULT,
    TRNG_E_NOT_READY,
    TRNG_E_STATE,
} trng_status_t;

typedef struct {
    bool clock_configured;
    bool enabled;
    bool faulted;
    uint32_t timeout_cycles;
} trng_state_t;

static trng_state_t g_trng_state;

static trng_status_t trng_clock_init(void)
{
    /*
     * 实际项目中应根据芯片参考手册配置：
     * 1. RNG 外设总线时钟；
     * 2. RNG 专用时钟源；
     * 3. RNG 时钟分频；
     * 4. 时钟频率范围校验。
     */
    if (!platform_rng_clock_configured()) {
        return TRNG_E_CLOCK;
    }

    g_trng_state.clock_configured = true;
    return TRNG_OK;
}
```

## 5.3 数据就绪和错误标志的处理顺序

推荐顺序：

```
读取状态寄存器
  ↓
先处理错误标志
  ↓
再判断数据是否就绪
  ↓
读取数据寄存器
```

不要先读数据、后检查错误。

错误示例：

```
uint32_t trng_get_bad(void)
{
    while ((RNG->SR & RNG_SR_DRDY) == 0U) {
    }

    uint32_t value = RNG->DR;

    if ((RNG->SR & RNG_SR_SEIS) != 0U) {
        return 0U;  /* 错误：返回看似有效的 0 */
    }

    return value;
}
```

风险：

- 上层无法区分合法随机值 `0` 和错误值；
- 错误数据可能已经进入密钥生成流程；
- 无法统计硬件故障次数；
- 错误状态可能未清除，导致后续读取全部失败。

推荐实现：

```
static trng_status_t trng_read_word_raw(uint32_t *out_value,
                                         uint32_t timeout_cycles)
{
    if (out_value == NULL) {
        return TRNG_E_PARAM;
    }

    for (uint32_t i = 0U; i < timeout_cycles; ++i) {
        uint32_t status = platform_trng_status();

        if ((status & PLATFORM_TRNG_STATUS_SEED_ERROR) != 0U) {
            platform_trng_clear_flags();
            return TRNG_E_SEED;
        }

        if ((status & PLATFORM_TRNG_STATUS_CLOCK_ERROR) != 0U) {
            platform_trng_clear_flags();
            return TRNG_E_CLOCK_FAULT;
        }

        if ((status & PLATFORM_TRNG_STATUS_DATA_READY) != 0U) {
            *out_value = platform_trng_read_data();
            return TRNG_OK;
        }

        platform_cpu_relax();
    }

    return TRNG_E_TIMEOUT;
}
```

## 5.4 超时机制不能使用无限等待

错误示例：

```
uint32_t trng_get_u32(void)
{
    while (!RNG_DATA_READY()) {
        /* 无限等待 */
    }

    return RNG_READ_DATA();
}
```

这种写法可能导致：

- 启动流程卡死；
- TLS 握手任务永久阻塞；
- 看门狗复位；
- 安全服务任务无法响应；
- 故障现场无法导出诊断信息。

### 推荐的超时模型

使用硬件计数器或单调递增时间源：

```
typedef uint32_t (*trng_tick_fn_t)(void);

typedef struct {
    trng_tick_fn_t tick_now;
    uint32_t tick_hz;
    uint32_t timeout_us;
} trng_wait_cfg_t;

static bool trng_timeout_expired(uint32_t start,
                                 uint32_t now,
                                 uint32_t timeout_ticks)
{
    /*
     * 无符号减法可正确处理 32 位 tick 回绕。
     */
    return (uint32_t)(now - start) >= timeout_ticks;
}
```

如果系统使用 DWT 周期计数器：

```
static trng_status_t trng_read_word_timeout(uint32_t *value,
                                             uint32_t timeout_us)
{
    if (value == NULL) {
        return TRNG_E_PARAM;
    }

    uint32_t start = platform_cycle_counter();
    uint32_t budget = platform_us_to_cycles(timeout_us);

    for (;;) {
        uint32_t status = platform_trng_status();

        if (status & PLATFORM_TRNG_STATUS_SEED_ERROR) {
            platform_trng_clear_flags();
            return TRNG_E_SEED;
        }

        if (status & PLATFORM_TRNG_STATUS_CLOCK_ERROR) {
            platform_trng_clear_flags();
            return TRNG_E_CLOCK_FAULT;
        }

        if (status & PLATFORM_TRNG_STATUS_DATA_READY) {
            *value = platform_trng_read_data();
            return TRNG_OK;
        }

        if ((uint32_t)(platform_cycle_counter() - start) >= budget) {
            return TRNG_E_TIMEOUT;
        }

        platform_cpu_relax();
    }
}
```

## 5.5 TRNG 健康检测

### 5.5.1 启动健康检测

启动时至少应检查：

- 外设时钟是否正确；
- RNG 是否成功使能；
- 是否产生数据；
- 是否存在种子错误；
- 是否存在时钟错误；
- 是否连续读取多个样本；
- 是否出现异常重复模式。

示例：

```
static bool trng_startup_health_check(void)
{
    uint32_t previous = 0U;
    uint32_t current = 0U;

    for (uint32_t i = 0U; i < 8U; ++i) {
        if (trng_read_word_timeout(&current, 1000U) != TRNG_OK) {
            return false;
        }

        if (i > 0U && current == previous) {
            /*
             * 注意：单次相等并不必然说明故障。
             * 这里仅作为非常粗粒度的启动异常检测。
             */
        }

        previous = current;
    }

    return true;
}
```

### 5.5.2 运行时健康检测

可检测：

- 连续重复值；
- 长时间无数据；
- 错误标志频率；
- 每单位时间输出量；
- 字节分布异常；
- 硬件状态反复恢复失败。

不应简单使用如下逻辑：

```
if (current == previous) {
    fault = true;
}
```

原因：

- 真随机数据允许连续相等；
- 32 位值连续相同的概率是 `1 / 2^32`，但短样本判断仍需结合统计窗口；
- 单点判断容易误报。

更合理的是使用连续重复计数：

```
typedef struct {
    uint32_t last_word;
    uint32_t repeat_count;
    uint32_t total_samples;
} trng_health_t;

#define TRNG_MAX_CONSECUTIVE_REPEAT 3U

static bool trng_health_update(trng_health_t *health,
                               uint32_t value)
{
    if (health == NULL) {
        return false;
    }

    health->total_samples++;

    if (health->total_samples > 1U && value == health->last_word) {
        health->repeat_count++;
    } else {
        health->repeat_count = 0U;
    }

    health->last_word = value;

    return health->repeat_count < TRNG_MAX_CONSECUTIVE_REPEAT;
}
```

> **重要：软件健康检测只能发现明显异常，不能替代芯片内部符合安全标准的连续测试、重复计数测试和熵源监控。**

## 5.6 熵率与输出比特率

设：

- 原始采样速率为 `R_raw`；
- 单个原始样本熵为 `H_raw`；
- 后处理压缩效率为 `η`；
- 输出接口宽度为 `W`；
- 实际输出速率为 `R_out`。

则有效熵率可近似表示为：

```
R_entropy = R_raw × H_raw × η
```

如果硬件每次输出 32 bit，但有效熵只有 0.7 bit/bit，则每个 32-bit 输出的有效熵约为：

```
H_word = 32 × 0.7 = 22.4 bit
```

因此不能仅根据寄存器宽度声称“每次获取 32 bit 熵”。

对于 TRNG + DRBG 架构，更重要的是：

- 初始种子包含多少有效熵；
- reseed 周期是否满足安全要求；
- DRBG 状态是否被保护；
- 熵源故障时是否停止输出。

---

# 6. 性能量化分析

## 6.1 测试平台假设

以下数据为典型 Cortex-M4/M33 MCU 的工程测量参考值，不代表所有芯片的固定性能。

|项目|典型配置|
|---|---|
|CPU|Cortex-M4F，168 MHz|
|RNG 时钟|48 MHz|
|输出宽度|32 bit|
|读取方式|状态轮询|
|编译器|GCC `-O2`|
|测量工具|DWT CYCCNT|
|RTOS|FreeRTOS，tick 1 kHz|

## 6.2 典型性能数据

|指标|典型测量值|
|---|---|
|单次寄存器读取 CPU 消耗|0.2～0.8 μs|
|单次硬件生成等待时间|1～20 μs|
|32 bit 输出吞吐率|50～1000 kbit/s|
|初始化时间|50～500 μs|
|健康检测时间|100 μs～数 ms|
|互斥锁附加开销|0.5～5 μs|
|DRBG 扩展吞吐率|1～50 Mbit/s，取决于算法和硬件加速|

真实工程中必须通过实测替换这些参考值。

## 6.3 轮询 CPU 占用估算

假设：

- CPU 主频 `F_cpu = 168 MHz`；
- 每次 TRNG 读取等待平均 `T_wait = 5 μs`；
- 每次调用需要读取 32 bit；
- 每秒调用 `N = 1000` 次。

则 CPU 等待时间约为：

```
T_cpu = N × T_wait
      = 1000 × 5 μs
      = 5 ms/s
```

CPU 占用率：

```
U_cpu = T_cpu / 1 s × 100%
      = 0.5%
```

如果每秒调用 100000 次：

```
T_cpu = 100000 × 5 μs = 500 ms/s
U_cpu = 50%
```

此时直接轮询已经不可接受，应采用：

- TRNG + 缓存；
- 中断填充；
- DMA；
- DRBG 扩展。

## 6.4 缓存和 DRBG 的收益

假设：

- TRNG 有效吞吐率为 256 kbit/s；
- 上层需要 4 Mbit/s；
- 每次 TRNG 读取平均等待 10 μs；
- DRBG 在 MCU 上吞吐率为 20 Mbit/s。

直接使用 TRNG：

```
需求速率 / TRNG 速率 = 4 Mbit/s / 0.256 Mbit/s ≈ 15.6
```

TRNG 无法满足需求。

采用：

```
TRNG → 256 bit 初始熵 → DRBG → 4 Mbit/s 输出
```

可以将硬件 TRNG 从高频业务路径中隔离，仅在：

- 启动；
- 定期 reseed；
- 安全事件；
- 熵池低水位

时访问。

## 6.5 内存开销

典型裸机直接读取：

```
驱动状态：约 16～64 byte
代码：约 1～4 KB
```

带 RTOS、缓存和 DRBG：

|模块|典型 RAM|
|---|---|
|驱动状态|64～256 B|
|互斥锁|40～100 B|
|环形缓冲区|64～4096 B|
|HMAC-DRBG|1～3 KB|
|CTR-DRBG|1～4 KB|
|诊断统计|64～512 B|

## 6.6 瓶颈分析与优化

### 瓶颈一：硬件输出速度低

优化：

- 用后台任务预取；
- 用环形缓冲区；
- 使用 DRBG 扩展；
- 降低上层对 TRNG 直接调用频率。

### 瓶颈二：任务阻塞

优化：

- 非阻塞接口；
- 中断通知；
- 超时返回；
- 使用独立随机源服务任务。

### 瓶颈三：锁竞争

优化：

- 单一 RNG 服务任务串行化访问；
- 批量获取随机数据；
- 避免高优先级任务频繁抢锁；
- 把 TRNG 访问和 DRBG 输出分离。

### 瓶颈四：低功耗唤醒后首次读取较慢

优化：

- 唤醒阶段单独执行 RNG 重启；
- 不在唤醒早期立即假设 RNG 可用；
- 配置随机源状态为 `RESTARTING`；
- 由安全服务等待 `READY` 事件。

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否用于安全相关功能？
├─ 否
│  ├─ 仅用于仿真、随机延时、测试
│  │  └─ 软件 PRNG 即可
│  └─ 需要较高不可预测性但无密钥用途
│     └─ MCU TRNG 或系统熵源
│
└─ 是
   ├─ 是否生成长期密钥、设备根密钥或安全启动材料？
   │  ├─ 是
   │  │  ├─ 芯片 TRNG 是否有安全认证、健康测试和勘误说明？
   │  │  │  ├─ 是
   │  │  │  │  └─ TRNG + 密码学库密钥生成
   │  │  │  └─ 否
   │  │  │     └─ 外部安全芯片或经过认证的安全模块
   │  │  └─ 是否允许密钥离开安全边界？
   │  │     ├─ 否：使用安全芯片内部生成
   │  │     └─ 是：使用 TRNG 产生种子后在受控内存中生成
   │  │
   │  └─ 否
   │     ├─ 是否需要高吞吐随机字节？
   │     │  ├─ 是：TRNG 初始化 DRBG
   │     │  └─ 否：直接使用 TRNG 服务接口
   │     └─ 是否运行在 RTOS？
   │        ├─ 是：服务任务 / 互斥锁 / 缓冲区
   │        └─ 否：阻塞或非阻塞读取
```

## 7.2 典型场景选型

|场景|需求|推荐方案|理由|
|---|---|---|---|
|TLS 握手|临时密钥、nonce、大量随机字节|TRNG 初始化 DRBG|低延迟、高吞吐|
|OTA 签名验证|随机数需求较少|TRNG 直接提供随机 nonce|简单、可审计|
|设备密钥生成|高安全要求|安全芯片内部 TRNG 或认证 TRNG|保护密钥边界|
|配网随机挑战|中等吞吐|TRNG 服务|防止可预测挑战|
|随机退避|非安全用途|软件 PRNG|不必占用硬件熵源|
|生产测试|统计和故障检测|原始数据采集 + 离线分析|便于发现批量问题|
|低功耗传感器|唤醒后少量随机数|直接 TRNG + 超时|节省 RAM 和代码|
|高吞吐加密网关|大量随机字节|TRNG + 硬件 DRBG/密码加速|降低 CPU 和外设压力|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：随机数接口必须返回状态

错误：

```
uint32_t random_u32(void);
```

推荐：

```
trng_status_t trng_get_u32(uint32_t *value,
                           uint32_t timeout_us);
```

原因：

- `0` 是合法随机值；
- 调用方必须知道 RNG 是否故障；
- 超时和健康检测失败不能静默吞掉。

### 原则二：区分“随机服务不可用”和“随机值为零”

```
uint32_t value = 0U;
trng_status_t status = trng_get_u32(&value, 1000U);

if (status != TRNG_OK) {
    security_fault_report(status);
    return SECURITY_E_RANDOM_SOURCE;
}
```

### 原则三：安全用途不允许静默降级

错误：

```
if (trng_get_u32(&value, 1000U) != TRNG_OK) {
    value = software_prng();
}
```

风险：

- 硬件熵源失效后系统继续生成“看似随机”的密钥；
- 攻击者可以通过故障注入迫使系统降级；
- 安全边界被绕开。

正确策略：

```
if (trng_get_u32(&value, 1000U) != TRNG_OK) {
    security_enter_random_fault_lockdown();
    return SECURITY_E_RANDOM_SOURCE;
}
```

### 原则四：软件混合不是自动增加熵

错误：

```
mixed = trng_value ^ timer_value ^ adc_value ^ stack_address;
```

如果 TRNG 已经正常工作，混合低质量源通常不能显著提升安全性；如果 TRNG 已经故障，简单异或也不能保证安全。

软件混合的正确价值主要是：

- 降低单一熵源依赖；
- 提供多源故障检测；
- 作为熵收集架构的一部分；
- 配合哈希压缩和熵估计。

### 原则五：保护 DRBG 状态

DRBG 内部状态属于敏感数据，应注意：

- 不允许普通业务直接读取；
- 使用后擦除临时状态；
- 避免打印日志；
- 任务切换时保证内存访问权限；
- 使用 MPU/TrustZone 时放置在安全域；
- 发生安全故障时清除状态。

## 8.2 选型决策矩阵

评分范围：1～5 分，越高越优。

|方案|安全性|吞吐率|实现复杂度|可诊断性|低功耗适应性|
|---|---|---|---|---|---|
|软件 PRNG|1|5|5|3|5|
|直接 TRNG|4|2|4|4|3|
|TRNG + 环形缓冲|4|4|3|4|3|
|TRNG + DRBG|5|5|2|4|4|
|外部安全芯片|5|3|2|5|3|

## 8.3 工业级编码规范

- 所有硬件寄存器使用 `volatile`。
- 所有 API 参数执行空指针检查。
- 所有等待循环必须有超时。
- 所有硬件错误必须映射为明确错误码。
- 不在驱动层使用 `printf` 输出敏感随机数据。
- 不返回未初始化变量。
- 不使用静态全局裸状态绕过并发保护。
- 不在安全场景使用默认软件 PRNG 兜底。
- 在初始化阶段执行硬件健康检查。
- 为错误次数、超时次数、恢复次数建立统计计数器。
- 对低功耗进入和唤醒路径单独设计。
- 明确中断上下文中是否允许调用接口。
- 随机字节缓冲区使用后执行安全擦除。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：无限轮询导致系统死锁

### 错误代码

```
uint32_t trng_read(void)
{
    while ((RNG->SR & RNG_SR_DRDY) == 0U) {
    }

    return RNG->DR;
}
```

### 根因

- RNG 时钟未配置；
- RNG 被硬件错误锁死；
- 低功耗模式下外设停止；
- 芯片进入异常状态；
- 软件忽略了错误标志。

### 正确实现

```
trng_status_t trng_read(uint32_t *value, uint32_t timeout_us)
{
    uint32_t start = platform_time_us();

    if (value == NULL) {
        return TRNG_E_PARAM;
    }

    while ((uint32_t)(platform_time_us() - start) < timeout_us) {
        uint32_t status = platform_trng_status();

        if ((status & PLATFORM_TRNG_STATUS_SEED_ERROR) != 0U) {
            platform_trng_clear_flags();
            return TRNG_E_SEED;
        }

        if ((status & PLATFORM_TRNG_STATUS_CLOCK_ERROR) != 0U) {
            platform_trng_clear_flags();
            return TRNG_E_CLOCK_FAULT;
        }

        if ((status & PLATFORM_TRNG_STATUS_DATA_READY) != 0U) {
            *value = platform_trng_read_data();
            return TRNG_OK;
        }
    }

    return TRNG_E_TIMEOUT;
}
```

### 风险影响

- 系统任务永久阻塞；
- 看门狗复位；
- 安全服务不可用；
- 现场问题难以复现。

## 9.2 错误二：忽略 RNG 错误标志

### 错误代码

```
if (RNG->SR & RNG_SR_DRDY) {
    return RNG->DR;
}
```

### 根因

将 `DRDY` 当成唯一有效性判断，忽略：

- 种子错误；
- 时钟错误；
- 溢出；
- 数据失效状态。

### 正确实现

```
static trng_status_t trng_validate_status(uint32_t status)
{
    if ((status & PLATFORM_TRNG_STATUS_SEED_ERROR) != 0U) {
        return TRNG_E_SEED;
    }

    if ((status & PLATFORM_TRNG_STATUS_CLOCK_ERROR) != 0U) {
        return TRNG_E_CLOCK_FAULT;
    }

    if ((status & PLATFORM_TRNG_STATUS_DATA_READY) == 0U) {
        return TRNG_E_NOT_READY;
    }

    return TRNG_OK;
}
```

### 风险影响

- 将故障数据当作熵使用；
- 生成弱密钥；
- 造成安全漏洞且难以通过功能测试发现。

## 9.3 错误三：将普通 ADC 低位直接当作 TRNG

### 错误代码

```
uint8_t weak_random_byte(void)
{
    return (uint8_t)(ADC1->DR & 0xFFU);
}
```

### 根因

- ADC 低位可能由量化误差、固定噪声和电源纹波主导；
- 噪声可能具有强相关性；
- 外部环境可以影响输入；
- 没有熵估计和去偏处理。

### 正确实现

如果确实需要使用 ADC 噪声，应至少包含：

```
ADC 采样
  ↓
去除直流分量
  ↓
差分 / 高通处理
  ↓
去偏
  ↓
哈希压缩
  ↓
健康测试
  ↓
与独立熵源混合
```

但对于密码学用途，优先级应是：

```
认证硬件 TRNG > 外部安全芯片 > 经验证的专用噪声源 > ADC 噪声
```

### 风险影响

- 输出可能高度可预测；
- 温度、电压或传感器状态变化会改变统计特性；
- 无法满足安全产品要求。

## 9.4 错误四：TRNG 失败后自动使用固定种子软件 PRNG

### 错误代码

```
uint32_t secure_random(void)
{
    uint32_t value;

    if (trng_read(&value, 1000U) != TRNG_OK) {
        srand(1U);
        return (uint32_t)rand();
    }

    return value;
}
```

### 根因

把“程序继续运行”错误地放在“安全性质保持”之前。

### 正确实现

```
trng_status_t secure_random(uint32_t *value)
{
    trng_status_t status;

    if (value == NULL) {
        return TRNG_E_PARAM;
    }

    status = trng_read(value, 1000U);
    if (status != TRNG_OK) {
        security_event_log(SECURITY_EVENT_TRNG_FAILURE, status);
        security_enter_random_fault_lockdown();
        return status;
    }

    return TRNG_OK;
}
```

### 风险影响

- 密钥重复；
- nonce 重复；
- TLS、AEAD、签名等协议遭受严重攻击；
- 故障注入可主动触发降级路径。

## 9.5 错误五：多线程直接访问 RNG 寄存器

### 错误代码

```
void task_a(void)
{
    uint32_t value = RNG->DR;
}

void task_b(void)
{
    uint32_t value = RNG->DR;
}
```

### 根因

- 数据寄存器可能是读清除；
- 两个任务之间存在竞争；
- 一个任务可能读取另一个任务期望的数据；
- 错误标志处理顺序被破坏。

### 正确实现

```
static SemaphoreHandle_t g_trng_lock;

trng_status_t trng_get_u32(uint32_t *value,
                           uint32_t timeout_ms)
{
    if (value == NULL) {
        return TRNG_E_PARAM;
    }

    if (xSemaphoreTake(g_trng_lock,
                       pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
        return TRNG_E_TIMEOUT;
    }

    trng_status_t status = trng_read_word_timeout(value, 1000U);

    xSemaphoreGive(g_trng_lock);
    return status;
}
```

### 风险影响

- 数据丢失；
- 任务间状态污染；
- 随机服务偶发失败；
- 高优先级任务出现不可预测延迟。

## 9.6 错误六：把随机数打印到日志

### 错误代码

```
LOG_INFO("TRNG value = 0x%08lx", value);
```

### 根因

调试日志没有安全分级，导致随机数、种子或密钥材料进入：

- UART；
- RTT；
- Flash 日志；
- 云端诊断；
- 崩溃转储。

### 正确实现

```
LOG_DEBUG("TRNG sample acquired, total=%lu",
          trng_get_total_samples());
```

### 风险影响

- 暴露密钥种子；
- 破坏协议不可预测性；
- 形成长期存储泄露。

---

# 10. 多机制组合使用方案

## 10.1 推荐总体架构

```
┌─────────────────────────────────────┐
│        应用 / TLS / OTA / 安全服务   │
└─────────────────┬───────────────────┘
                  │ random_bytes()
┌─────────────────▼───────────────────┐
│       CSPRNG / DRBG 服务层           │
│  状态保护、reseed、并发控制、审计     │
└─────────────────┬───────────────────┘
                  │ entropy_read()
┌─────────────────▼───────────────────┐
│       熵池 / TRNG 缓冲服务            │
│  环形缓冲、健康检测、低水位管理        │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│       MCU TRNG 驱动                   │
│  时钟、寄存器、超时、错误恢复          │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│       物理熵源硬件                    │
└─────────────────────────────────────┘
```

## 10.2 环形缓冲区设计

```
#define TRNG_POOL_SIZE 256U

typedef struct {
    uint8_t buffer[TRNG_POOL_SIZE];
    size_t head;
    size_t tail;
    size_t count;
    bool faulted;
    uint32_t low_watermark;
} trng_pool_t;

static trng_pool_t g_pool;

static size_t pool_free_size(const trng_pool_t *pool)
{
    return TRNG_POOL_SIZE - pool->count;
}

static bool pool_push(trng_pool_t *pool,
                      const uint8_t *data,
                      size_t len)
{
    if (pool == NULL || data == NULL || len > pool_free_size(pool)) {
        return false;
    }

    for (size_t i = 0U; i < len; ++i) {
        pool->buffer[pool->head] = data[i];
        pool->head = (pool->head + 1U) % TRNG_POOL_SIZE;
        pool->count++;
    }

    return true;
}

static bool pool_pop(trng_pool_t *pool,
                     uint8_t *data,
                     size_t len)
{
    if (pool == NULL || data == NULL || len > pool->count) {
        return false;
    }

    for (size_t i = 0U; i < len; ++i) {
        data[i] = pool->buffer[pool->tail];
        pool->tail = (pool->tail + 1U) % TRNG_POOL_SIZE;
        pool->count--;
    }

    return true;
}
```

工程注意：

- 多任务环境需要互斥锁或单生产者/单消费者模型；
- 不能使用 `memcpy()` 直接处理回绕区域；
- 随机缓冲区不应被普通诊断接口导出；
- 读取失败后不能返回部分数据并伪装为成功。

## 10.3 DRBG 初始化框架

以下示例为抽象接口：

```
typedef enum {
    DRBG_OK = 0,
    DRBG_E_PARAM,
    DRBG_E_ENTROPY,
    DRBG_E_NOT_READY,
    DRBG_E_RESEED_REQUIRED,
} drbg_status_t;

typedef struct {
    bool initialized;
    uint64_t generated_bytes;
    uint32_t reseed_counter;
} drbg_context_t;

static drbg_context_t g_drbg;

drbg_status_t drbg_init(void)
{
    uint8_t entropy[48];
    uint8_t nonce[16];

    if (trng_get_bytes(entropy, sizeof(entropy), 100U) != TRNG_OK) {
        secure_memzero(entropy, sizeof(entropy));
        secure_memzero(nonce, sizeof(nonce));
        return DRBG_E_ENTROPY;
    }

    if (trng_get_bytes(nonce, sizeof(nonce), 100U) != TRNG_OK) {
        secure_memzero(entropy, sizeof(entropy));
        secure_memzero(nonce, sizeof(nonce));
        return DRBG_E_ENTROPY;
    }

    if (!platform_drbg_instantiate(entropy,
                                   sizeof(entropy),
                                   nonce,
                                   sizeof(nonce))) {
        secure_memzero(entropy, sizeof(entropy));
        secure_memzero(nonce, sizeof(nonce));
        return DRBG_E_ENTROPY;
    }

    secure_memzero(entropy, sizeof(entropy));
    secure_memzero(nonce, sizeof(nonce));

    g_drbg.initialized = true;
    g_drbg.generated_bytes = 0U;
    g_drbg.reseed_counter = 0U;

    return DRBG_OK;
}
```

## 10.4 DRBG reseed 策略

可按以下条件触发：

```
启动时必须 reseed
累计输出超过阈值时 reseed
经过固定时间间隔时 reseed
检测到安全事件时 reseed
设备从深度低功耗唤醒时重新验证或 reseed
TRNG 健康状态变化时停止输出
```

示例：

```
#define DRBG_RESEED_BYTES_LIMIT (1024U * 1024U)
#define DRBG_RESEED_INTERVAL_MS 3600000U

bool drbg_need_reseed(uint32_t now_ms)
{
    if (!g_drbg.initialized) {
        return true;
    }

    if (g_drbg.generated_bytes >= DRBG_RESEED_BYTES_LIMIT) {
        return true;
    }

    if ((uint32_t)(now_ms - platform_drbg_last_reseed_ms())
        >= DRBG_RESEED_INTERVAL_MS) {
        return true;
    }

    return false;
}
```

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业网关 TLS 双向认证

### 需求

- 支持 TLS 1.2/1.3；
- 每个连接生成临时密钥和 nonce；
- 设备同时维护 20 个 TCP/TLS 连接；
- 不能因硬件 RNG 短时等待阻塞网络线程；
- RNG 故障必须触发安全告警。

### 架构设计

```
TLS 线程
   ↓
CSPRNG API
   ↓
DRBG 服务任务
   ↓
TRNG 熵池
   ↓
MCU TRNG
```

设计要点：

1. TLS 不直接访问 RNG 寄存器。
2. DRBG 初始化需要成功获取足够熵。
3. DRBG 输出采用互斥保护。
4. TRNG 故障时：
    - 停止新 TLS 会话；
    - 记录安全事件；
    - 允许已有会话按策略关闭；
    - 不使用软件 PRNG 兜底。
5. 熵池由低优先级后台任务维护。

核心代码框架：

```
int tls_random_callback(uint8_t *out, size_t len)
{
    if (out == NULL || len == 0U) {
        return -1;
    }

    if (!g_drbg.initialized) {
        return -1;
    }

    if (drbg_need_reseed(platform_time_ms())) {
        if (drbg_reseed_from_trng() != DRBG_OK) {
            security_event_log(SECURITY_EVENT_DRBG_RESEED_FAILED, 0);
            return -1;
        }
    }

    if (!platform_drbg_generate(out, len)) {
        security_event_log(SECURITY_EVENT_DRBG_GENERATE_FAILED, 0);
        return -1;
    }

    g_drbg.generated_bytes += len;
    return 0;
}
```

### 量化效果

假设 TLS 每秒产生 50 KB 随机需求：

- 直接 TRNG：若吞吐率 32 KB/s，不满足需求；
- TRNG + DRBG：
    - 启动阶段读取 64～128 byte 熵；
    - DRBG 输出达到数 MB/s；
    - TLS 线程平均随机调用延迟从几十微秒下降到数微秒以内。

## 11.2 案例二：工业控制器安全启动和设备身份初始化

### 需求

- 首次启动生成设备密钥对；
- 私钥不能使用固定种子；
- RNG 故障时设备必须进入安全停机；
- 设备重启后不能重复生成相同身份密钥；
- 生产测试需要记录 RNG 健康状态，但不能记录随机数据。

### 架构设计

```
Boot ROM / Bootloader
   ↓
TRNG 初始化
   ↓
启动健康检测
   ↓
安全密钥服务
   ↓
生成设备密钥对
   ↓
密钥写入安全存储
```

核心流程：

```
security_status_t device_identity_provision(void)
{
    if (trng_init() != TRNG_OK) {
        security_enter_safe_state();
        return SECURITY_E_TRNG;
    }

    if (!trng_startup_health_check()) {
        security_enter_safe_state();
        return SECURITY_E_TRNG_HEALTH;
    }

    if (secure_storage_has_device_key()) {
        return SECURITY_OK;
    }

    if (secure_key_generate_and_store(KEY_TYPE_DEVICE_ID) != 0) {
        security_enter_safe_state();
        return SECURITY_E_KEY_GENERATION;
    }

    return SECURITY_OK;
}
```

### 设计要点

- 设备密钥只生成一次，并通过安全存储状态标志保证幂等性。
- 不能使用普通 Flash 写入私钥后再依赖软件权限保护。
- RNG 失败后不允许生成“备用身份密钥”。
- 生产日志只记录：
    - 初始化成功/失败；
    - 错误类型；
    - 重启次数；
    - 健康检测结果摘要。

## 11.3 案例三：低功耗无线传感器随机退避与安全配网

### 需求

- 节点大部分时间处于 Stop/Standby；
- 唤醒后需要生成随机退避时间；
- 配网阶段需要随机挑战值；
- 无线协议每分钟只需要几十字节随机数据；
- 不能因随机源异常使设备无限等待。

### 架构设计

```
唤醒
  ↓
恢复 RNG 时钟
  ↓
RNG 状态验证
  ↓
获取 32 bit 随机值
  ↓
映射到退避窗口
  ↓
关闭或暂停 RNG
```

退避计算：

```
uint32_t random_backoff_ms(uint32_t window_ms)
{
    uint32_t value = 0U;

    if (window_ms == 0U) {
        return 0U;
    }

    if (trng_get_u32(&value, 2000U) != TRNG_OK) {
        /*
         * 如果只是非安全退避，可使用协议明确规定的保守固定值。
         * 这里不能将该路径用于密钥或 nonce。
         */
        return window_ms / 2U;
    }

    /*
     * 简单取模存在轻微 modulo bias。
     * 对非安全退避通常可接受；安全挑战不可这样处理。
     */
    return value % window_ms;
}
```

如果退避结果属于安全协议的一部分，应使用拒绝采样：

```
bool uniform_below(uint32_t upper,
                   uint32_t *result)
{
    uint32_t x;
    uint32_t limit;

    if (upper == 0U || result == NULL) {
        return false;
    }

    limit = UINT32_MAX - (UINT32_MAX % upper);

    do {
        if (trng_get_u32(&x, 2000U) != TRNG_OK) {
            return false;
        }
    } while (x >= limit);

    *result = x % upper;
    return true;
}
```

---

# 12. 高频问题深度答疑

## 问题一：TRNG 输出通过随机性测试后，就可以用于生成密钥吗？

不一定。

随机性测试通常验证的是：

- 比特频率；
- 游程分布；
- 块频率；
- 近似熵；
- 自相关；
- 不可压缩性。

这些测试主要说明样本在统计意义上不像明显的非随机序列。

但密钥安全还依赖：

- 熵源是否具有真实物理不可预测性；
- 攻击者是否能控制外部环境；
- 启动阶段是否存在固定状态；
- 故障情况下是否继续输出；
- 健康检测是否完整；
- 后处理是否正确；
- 芯片实现是否存在勘误问题。

因此应结合：

```
芯片安全手册
+ 原厂认证资料
+ 健康测试机制
+ 工程故障注入
+ 随机性统计测试
+ 系统安全架构
```

## 问题二：为什么不用时间戳、ADC 值和内存地址混合生成随机数？

因为这些值通常不是可靠熵源：

- 时间戳可被预测；
- ADC 值可能被环境控制；
- 内存地址通常固定；
- 堆栈内容可能重复；
- 编译器优化可能改变状态；
- 异或不会自动增加熵。

如果 TRNG 正常，混合它们可能作为防御纵深；但如果 TRNG 故障，不能假设混合后仍具备密码学安全性。

## 问题三：TRNG 需要加锁吗？

如果硬件寄存器被多个上下文访问，通常需要。

以下情况必须考虑同步：

- 多任务读取；
- 中断和任务同时读取；
- DMA 和 CPU 同时读取；
- 错误清除和数据读取存在顺序依赖；
- 数据寄存器为读清除寄存器。

推荐优先级：

```
单一随机服务任务
  > 互斥锁保护的统一驱动接口
  > 禁止中断期间读取
  > 直接多上下文操作寄存器
```

## 问题四：TRNG 出错时，是否可以继续使用之前缓存的随机数？

要区分用途。

### 非安全用途

例如随机延时、负载分散，可以在明确风险的前提下使用已有缓存。

### 安全用途

需要考虑缓存数据的：

- 来源是否经过健康检测；
- 缓存是否可能被重复使用；
- 缓存是否跨重启保存；
- 缓存是否已经暴露；
- 缓存剩余熵量。

通常策略是：

```
TRNG 故障
  ↓
停止新增安全随机输出
  ↓
标记 DRBG 需要 reseed
  ↓
已有会话按安全策略继续或终止
  ↓
恢复成功后重新建立安全状态
```

## 问题五：直接使用 TRNG 与 TRNG + DRBG 哪个更安全？

工程上通常推荐 **TRNG + DRBG**，但前提是：

- TRNG 提供高质量初始熵；
- DRBG 实现正确；
- reseed 策略明确；
- DRBG 状态被保护；
- 输出计数和故障状态被跟踪；
- 不超过标准规定的最大生成量；
- TRNG 故障不会被静默忽略。

直接使用 TRNG 的优点是架构简单，但吞吐率、延迟和并发性通常较差。

## 问题六：低功耗模式下 TRNG 是否仍然有效？

不能假设有效。

需要查阅：

- RNG 外设在 Stop/Standby/Sleep 中是否继续工作；
- RNG 时钟是否保持；
- PLL 是否关闭；
- 唤醒后外设是否需要重新初始化；
- 熵源是否需要重新启动；
- 错误标志是否在低功耗切换后保留；
- 芯片是否规定唤醒后丢弃前若干个样本。

推荐设计状态机：

```
typedef enum {
    TRNG_STATE_OFF,
    TRNG_STATE_STARTING,
    TRNG_STATE_READY,
    TRNG_STATE_FAULT,
    TRNG_STATE_SUSPENDED,
} trng_state_t;
```

唤醒后必须经过：

```
恢复时钟
  ↓
清除旧错误标志
  ↓
重新使能
  ↓
等待就绪
  ↓
健康检查
  ↓
READY
```

---

# 13. 课程核心总结

## 13.1 核心要点

1. **TRNG 是物理熵源，不等于普通随机 API。**
2. **TRNG 驱动必须处理时钟、数据就绪、错误标志和超时。**
3. **安全随机 API 必须返回状态，不能只返回一个整数。**
4. **RNG 故障不能静默降级到固定种子软件 PRNG。**
5. **硬件 TRNG 更适合做熵源，DRBG 更适合做高吞吐随机输出。**
6. **随机性统计测试不能替代熵源安全分析。**
7. **RTOS 环境下应统一访问入口，避免多个任务直接操作寄存器。**
8. **低功耗唤醒后必须重新验证 RNG 状态。**
9. **随机数据、种子和 DRBG 状态不能进入日志或普通崩溃转储。**
10. **安全用途应建立故障闭锁，而不是追求“系统继续运行”。**

## 13.2 性能排序

### 吞吐率

```
硬件加速 DRBG
  > 软件优化 DRBG
  > TRNG + 缓冲
  > 直接 TRNG
  > 外部低速 I²C RNG
```

### 实现简单度

```
直接轮询 TRNG
  > 非阻塞 TRNG
  > 中断 TRNG
  > 缓冲 TRNG
  > TRNG + DRBG + 安全服务
```

### 安全架构推荐度

```
固定种子 PRNG
  < 普通软件 PRNG
  < 直接 MCU TRNG
  < TRNG + 健康检测
  < TRNG + DRBG + 故障闭锁
  < 安全芯片内部 TRNG/密钥生成
```

## 13.3 通用选型结论

|需求|结论|
|---|---|
|非安全随机延时|软件 PRNG 足够|
|少量安全随机数|直接 TRNG 服务|
|大量安全随机字节|TRNG 初始化 DRBG|
|设备根密钥|优先安全芯片内部生成|
|高可靠工业控制|TRNG + 健康检测 + 故障闭锁|
|低功耗设备|唤醒重启 RNG，严格超时|
|多任务系统|随机服务任务或统一互斥接口|
|合规安全产品|依据认证资料和安全手册进行验证|

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐方案|禁止做法|
|---|---|---|
|TLS 随机数|TRNG + DRBG|直接使用 `rand()`|
|密钥生成|认证 TRNG / 安全芯片|时间戳作为种子|
|随机退避|软件 PRNG 或 TRNG|在无超时循环等待|
|配网挑战|TRNG 直接读取|使用固定挑战值|
|高吞吐协议|DRBG 缓存|每字节访问 TRNG|
|低功耗唤醒|RNG 恢复 + 健康检测|假设 RNG 自动恢复|
|故障处理|安全闭锁 / 明确降级|静默切换固定种子|
|日志诊断|记录状态和计数|打印随机值和种子|

## 14.2 特性对比表

|特性|直接 TRNG|TRNG + 缓存|TRNG + DRBG|
|---|---|---|---|
|安全性|高|高|高|
|延迟|中高|中|低|
|吞吐率|低中|中高|高|
|RAM|低|中|中高|
|代码复杂度|低|中|高|
|故障处理|分散|中央化|中央化|
|适合 TLS|一般|较好|最佳|
|适合密钥生成|可以|可以|推荐|
|容易审计|较好|较好|需要完整设计|

## 14.3 推荐 API

```
trng_status_t trng_init(void);

trng_status_t trng_suspend(void);

trng_status_t trng_resume(void);

trng_status_t trng_get_u32(uint32_t *value,
                           uint32_t timeout_us);

trng_status_t trng_get_bytes(uint8_t *buffer,
                             size_t length,
                             uint32_t timeout_ms);

bool trng_is_healthy(void);

trng_status_t trng_get_statistics(trng_statistics_t *stats);
```

---

# 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

## 15.1 原理检查

- [ ]  能解释 TRNG 与 PRNG 的根本区别。
- [ ]  能说明振荡器抖动如何形成随机比特。
- [ ]  能解释为什么寄存器宽度不等于有效熵量。
- [ ]  能区分 TRNG、CSPRNG 和 DRBG 的职责。
- [ ]  能说明随机性测试的局限性。

## 15.2 驱动实现检查

- [ ]  能完成 RNG 时钟配置。
- [ ]  能实现带超时的随机数读取。
- [ ]  能检查并清除种子错误和时钟错误。
- [ ]  能正确处理 `0` 等合法随机值。
- [ ]  能设计初始化健康检查。
- [ ]  能处理中断、任务和 DMA 之间的访问竞争。

## 15.3 系统架构检查

- [ ]  能设计 TRNG + 熵池 + DRBG 架构。
- [ ]  能定义 DRBG reseed 条件。
- [ ]  能设计 RNG 故障闭锁策略。
- [ ]  能说明低功耗唤醒后的恢复流程。
- [ ]  能避免随机数据进入日志和崩溃转储。
- [ ]  能根据吞吐率、延迟和安全要求做方案选型。

## 15.4 工程验证检查

- [ ]  能使用 DWT 或定时器测量随机读取延迟。
- [ ]  能统计 TRNG 吞吐率和错误率。
- [ ]  能注入时钟错误和超时故障。
- [ ]  能验证低功耗切换后的 RNG 可用性。
- [ ]  能执行连续输出、重复计数和分布测试。
- [ ]  能生成可审计的随机源验证报告。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：裸机寄存器级 TRNG 驱动

要求：

- 实现时钟初始化；
- 实现 RNG 使能；
- 实现数据读取；
- 实现超时；
- 实现错误标志检查；
- 输出统计信息，但禁止输出原始随机值。

验收指标：

```
连续读取 10000 个 32 bit 样本
无死循环
错误状态可恢复
超时路径可验证
```

### 任务二：RTOS 随机服务

要求：

- 创建 RNG 服务任务；
- 建立环形缓冲区；
- 提供阻塞式 `get_bytes()`；
- 使用事件或信号量通知数据可用；
- 支持多个业务任务并发请求；
- 记录吞吐率、超时次数和错误次数。

验收指标：

```
10 个任务并发读取
无数据竞争
无缓冲区越界
任务优先级可控
超时行为确定
```

### 任务三：TRNG + DRBG

要求：

- 使用 TRNG 提供初始化熵；
- 集成 HMAC-DRBG、CTR-DRBG 或芯片硬件 DRBG；
- 实现 reseed 计数；
- 限制单次和累计生成量；
- 处理 reseed 失败；
- 安全擦除临时熵数据。

验收指标：

```
DRBG 输出吞吐率至少达到直接 TRNG 的 10 倍
TRNG 故障后不允许继续生成安全随机数
reseed 条件可配置且可观测
```

### 任务四：低功耗恢复测试

要求：

- 在 Sleep、Stop、Standby 等模式下测试 RNG；
- 记录唤醒后首次可用时间；
- 检测旧错误标志；
- 验证恢复流程的幂等性；
- 验证连续进入/退出低功耗 10000 次。

### 任务五：故障注入与安全审计

注入以下故障：

- RNG 时钟关闭；
- RNG 时钟频率超限；
- RNG 数据就绪永不置位；
- 种子错误；
- 时钟错误；
- 中断丢失；
- 外设复位；
- 电源波动；
- 任务竞争；
- 缓冲区满或空。

要求输出：

```
故障触发方式
检测时间
错误码
恢复动作
是否允许继续输出
系统最终状态
```

## 16.2 性能测试方法

### 测量单次读取延迟

```
uint32_t start = DWT->CYCCNT;
uint32_t value = 0U;

trng_status_t status = trng_get_u32(&value, 1000U);

uint32_t cycles = DWT->CYCCNT - start;

if (status == TRNG_OK) {
    test_record_cycles(cycles);
}
```

转换公式：

```
Latency_us = cycles / CPU_Frequency_MHz
```

例如：

```
1680 cycles / 168 MHz = 10 μs
```

### 测量吞吐率

```
uint32_t start_ms = platform_time_ms();
size_t total = 0U;

while ((platform_time_ms() - start_ms) < 1000U) {
    uint32_t value;

    if (trng_get_u32(&value, 1000U) == TRNG_OK) {
        total += sizeof(value);
    }
}

printf("throughput = %lu bytes/s\n",
       (unsigned long)total);
```

生产级测试中应避免在测试代码中输出原始随机数据，只记录：

- 样本数量；
- 错误数量；
- 读取耗时；
- 统计摘要；
- 哈希摘要。

## 16.3 进阶学习方向

### 方向一：标准与认证

继续学习：

- NIST SP 800-90A：DRBG；
- NIST SP 800-90B：熵源；
- NIST SP 800-90C：组合随机数生成器；
- FIPS 140-3；
- Common Criteria；
- PSA Certified；
- ISO/IEC 15408；
- 芯片厂商 RNG 安全手册和勘误说明。

### 方向二：熵源验证

深入掌握：

- 最小熵估计；
- min-entropy；
- IID/non-IID 假设；
- 重复计数测试；
- 自适应比例测试；
- 启动健康测试；
- 连续健康测试；
- 环境应力测试。

### 方向三：密码学工程

学习：

- HMAC-DRBG；
- CTR-DRBG；
- Hash-DRBG；
- HKDF；
- nonce 唯一性；
- AEAD 随机 nonce 设计；
- 密钥生成和擦除；
- 硬件安全模块；
- TrustZone-M 和 MPU 隔离。

### 方向四：安全故障分析

研究：

- 时钟故障注入；
- 电压毛刺；
- 电磁注入；
- 低功耗切换攻击；
- RNG 输出冻结；
- 随机源降级攻击；
- 故障状态清除攻击；
- 重启计数和熵重复问题。

> **最终工程结论：**  
> 对于工业级嵌入式系统，TRNG 的正确定位不是一个“读取随机数寄存器的简单驱动”，而是一个包含**硬件时钟管理、熵源健康检测、并发控制、故障闭锁、低功耗恢复、熵池管理和 DRBG 扩展**的安全基础服务。