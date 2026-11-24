
## 1. 学习目标

### 理解

- 理解看门狗的**故障模型、复位机制、超时判定逻辑**。
- 理解独立看门狗、窗口看门狗、外部看门狗、任务级软件看门狗的边界。
- 理解看门狗与 **Brownout、HardFault、死循环、总线阻塞、RTOS 调度异常**之间的关系。
- 理解看门狗不能替代故障恢复、错误隔离和系统健康监控。

### 掌握

- 掌握独立看门狗 IWDG 的时钟、预分频、重载值和超时计算。
- 掌握窗口看门狗 WWDG 的早刷新和晚刷新违规机制。
- 掌握看门狗初始化、刷新、复位原因读取和启动阶段配置。
- 掌握 RTOS 多任务系统中的**集中式喂狗机制**。
- 掌握看门狗调试、故障注入和复位原因持久化。

### 精通

- 能够分析看门狗配置对实时性、功耗、启动时间和故障恢复时间的影响。
- 能够处理多任务系统中的**优先级反转、任务假死、刷新路径阻塞、错误状态误喂狗**。
- 能够设计面向产品量产的看门狗管理器、故障记录和自动恢复策略。
- 能够量化 watchdog timeout、误复位概率和最坏恢复时间。

### 能够设计

- 能够为裸机、RTOS、低功耗和安全关键系统设计完整的看门狗架构。
- 能够组合使用硬件看门狗、任务心跳、软件超时、通信链路恢复和故障日志。
- 能够设计满足 IEC 61508、ISO 26262 或企业级可靠性要求的故障恢复方案。
- 能够建立看门狗驱动的单元测试、集成测试和故障注入测试体系。

---

## 2. 前置要求

### 知识要求

- C 语言：位操作、`volatile`、指针、内存映射寄存器。
- MCU 基础：时钟树、复位控制、NVIC、中断和低功耗模式。
- RTOS 基础：任务、优先级、阻塞、互斥锁、定时器。
- 基础硬件知识：RC 振荡器、复位芯片、电源跌落和外部监控器。
- 基本可靠性概念：故障、失效、恢复时间、故障覆盖率。

### 技能要求

- 能够根据芯片参考手册配置定时器和时钟。
- 能够使用逻辑分析仪、示波器或调试器测量复位信号。
- 能够读取并保留 MCU 的复位原因寄存器。
- 能够编写硬件抽象层和可测试的驱动接口。
- 能够构造任务阻塞、死循环、栈溢出和中断风暴等故障场景。

---

## 3. 技术概述

### 3.1 看门狗的核心定义

看门狗是一种**在系统未按预期时间窗口执行维护动作时，主动触发复位或故障信号的监控机制**。

最常见的逻辑为：

```
启动计数器
    |
    v
计数器持续递增或递减
    |
    +-- 在有效时间内刷新 --> 计数器重装，继续运行
    |
    +-- 未刷新或刷新时机非法 --> 触发复位
```

看门狗解决的不是“程序是否正确”，而是下面这类问题：

- CPU 执行流进入死循环。
- 任务永久阻塞或调度器停止运行。
- 中断优先级配置错误，导致普通任务无法获得运行机会。
- 外设驱动等待硬件状态时无限阻塞。
- 栈破坏导致程序跳转到异常地址。
- Flash、RAM、总线或电源瞬态故障造成的软件失控。

### 3.2 主流技术分支

|类型|监控对象|时钟来源|是否可被软件关闭|典型用途|
|---|---|---|---|---|
|独立看门狗 IWDG|CPU 是否周期性刷新|独立低速时钟|通常不可关闭|通用系统最终故障恢复|
|窗口看门狗 WWDG|刷新是否落在合法窗口|APB 总线时钟|通常可配置|检测过早刷新和异常高速执行|
|外部看门狗|MCU 是否持续输出服务信号|外部晶振或内部时钟|MCU 无法直接关闭|高可靠、安全关键系统|
|任务级软件看门狗|单个任务是否按时运行|SysTick/RTOS tick|软件可绕过|多任务健康监控|
|通信看门狗|通信链路是否保持有效|定时器或协议时基|软件实现|CAN、Ethernet、Modbus 链路恢复|
|硬件窗口看门狗|服务信号频率和时间窗|外部硬件|MCU 无法绕过|防止程序异常快速循环喂狗|

### 3.3 看门狗的正确定位

看门狗通常位于系统故障恢复链路的最后一层：

```
应用错误处理
    |
    v
模块重启 / 链路重连 / 外设复位
    |
    v
任务级健康监控
    |
    v
系统级硬件看门狗
    |
    v
外部看门狗或电源重启
```

**看门狗不是正常流程控制器，也不是错误日志系统。**

---

## 4. 核心特性横向对比

### 4.1 不同看门狗方案对比

|维度|IWDG|WWDG|外部看门狗|任务级软件看门狗|
|---|---|---|---|---|
|故障覆盖范围|CPU/软件整体失控|软件执行时序异常|MCU 整体失控|指定任务或模块|
|独立性|高|中|最高|低|
|能否检测过早刷新|否|是|取决于器件|可实现|
|能否检测单任务假死|间接|间接|否|是|
|对时钟故障敏感性|对主时钟不敏感|对 APB 时钟敏感|通常独立|对系统 tick 敏感|
|典型精度|低到中|中|高|取决于系统 tick|
|配置复杂度|低|中|中到高|中|
|误复位风险|配置不当时较高|窗口设置不当时较高|外部时序设计不当|状态管理错误时较高|
|对安全性的贡献|中|中|高|中|
|推荐定位|最终复位手段|时序完整性监控|高可靠最终防线|故障定位和提前恢复|

### 4.2 常见 MCU 内部看门狗差异

|特性|IWDG|WWDG|
|---|---|---|
|计数方向|通常递减|通常递减|
|复位条件|计数器到 0|计数器到 0 或过早刷新|
|刷新要求|超时前刷新|必须位于上限和下限之间刷新|
|时钟|LSI/LIRC 等独立时钟|PCLK 分频|
|主时钟停止后|通常仍可运行|可能停止|
|低功耗适配|需要检查芯片行为|通常受总线时钟影响|
|工程用途|系统最终恢复|检测执行时序异常|

---

## 5. 底层原理与功能特性深度解析

## 5.1 独立看门狗的计时原理

以常见 MCU 的 IWDG 为例：

```
LSI/LIRC --> 预分频器 --> 递减计数器 --> 0 时触发复位
                              ^
                              |
                         写入重载值
```

超时时间通常近似为：

Twdt=(R+1)×PfLSITwdt​=fLSI​(R+1)×P​

其中：

- `R`：重载值。
- `P`：预分频系数。
- `f_LSI`：低速内部振荡器频率。
- `T_wdt`：看门狗超时时间。

以 `f_LSI = 32 kHz`、预分频 `P = 32`、重载值 `R = 999` 为例：

Twdt=1000×3232000=1.0sTwdt​=320001000×32​=1.0s

但实际 LSI 可能存在 ±5% 到 ±20% 的误差，因此设计时必须使用最坏情况：

Tactual,max=(R+1)×PfLSI,minTactual,max​=fLSI,min​(R+1)×P​Tactual,min=(R+1)×PfLSI,maxTactual,min​=fLSI,max​(R+1)×P​

不能把标称值直接当作精确时间基准。

### 通用 IWDG 驱动接口

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    WDT_OK = 0,
    WDT_EINVAL = -1,
    WDT_EBUSY = -2,
    WDT_EHW = -3
} wdt_status_t;

typedef struct {
    uint32_t lsi_hz;
    uint32_t prescaler;
    uint32_t reload;
    uint32_t timeout_ms;
} wdt_config_t;

typedef struct {
    volatile uint32_t key;
    volatile uint32_t prescaler;
    volatile uint32_t reload;
    volatile uint32_t status;
} iwdg_regs_t;

#define IWDG_KEY_ENABLE       0xCCCCu
#define IWDG_KEY_RELOAD       0xAAAAu
#define IWDG_KEY_WRITE_ACCESS 0x5555u
#define IWDG_MAX_RELOAD       0x0FFFu

static iwdg_regs_t *const IWDG = (iwdg_regs_t *)0x40003000u;

static uint32_t wdt_calculate_reload(const wdt_config_t *cfg)
{
    uint64_t ticks;

    if (cfg == NULL || cfg->lsi_hz == 0u || cfg->prescaler == 0u) {
        return 0u;
    }

    ticks = ((uint64_t)cfg->timeout_ms * cfg->lsi_hz) /
            (1000u * cfg->prescaler);

    if (ticks == 0u) {
        return 0u;
    }

    ticks -= 1u;

    if (ticks > IWDG_MAX_RELOAD) {
        return IWDG_MAX_RELOAD;
    }

    return (uint32_t)ticks;
}

wdt_status_t iwdg_init(const wdt_config_t *cfg)
{
    uint32_t reload;

    if (cfg == NULL) {
        return WDT_EINVAL;
    }

    reload = wdt_calculate_reload(cfg);
    if (reload == 0u) {
        return WDT_EINVAL;
    }

    /*
     * 实际项目中必须根据芯片手册等待 PVU/RVU 等更新标志，
     * 不能假定寄存器写入立即生效。
     */
    IWDG->key = IWDG_KEY_WRITE_ACCESS;
    IWDG->prescaler = cfg->prescaler;
    IWDG->reload = reload;

    IWDG->key = IWDG_KEY_RELOAD;
    IWDG->key = IWDG_KEY_ENABLE;

    return WDT_OK;
}

void iwdg_feed(void)
{
    /*
     * 喂狗操作应保持短小、无锁、无阻塞。
     */
    IWDG->key = IWDG_KEY_RELOAD;
}
```

工程上还需要补充：

- 启用 LSI 后等待就绪。
- 等待预分频器和重载寄存器更新。
- 检查写保护状态。
- 记录实际配置结果。
- 在启动早期读取复位来源。
- 对无法配置的超时值返回错误，而不是静默饱和。

---

## 5.2 窗口看门狗原理

窗口看门狗通常要求刷新动作满足：

CNTmin<CNTrefresh≤CNTwindowCNTmin​<CNTrefresh​≤CNTwindow​

存在两个违规方向：

1. **刷新太晚**：计数器已经减到 0。
2. **刷新太早**：计数器仍高于允许窗口上限。

刷新太早通常意味着：

- 主循环异常高速运行。
- 延时逻辑失效。
- 任务调度异常。
- 程序跳过了预期工作。
- 定时器时基损坏。

WWDG 示例：

```
#define WWDG_COUNTER_MIN     0x40u
#define WWDG_COUNTER_START   0x7Fu
#define WWDG_WINDOW_MAX      0x70u

static volatile uint32_t *const WWDG_CR =
    (volatile uint32_t *)0x40002C00u;

static volatile uint32_t *const WWDG_CFR =
    (volatile uint32_t *)0x40002C04u;

static void wwdg_init(void)
{
    /*
     * 真实芯片需要根据参考手册配置：
     * 1. APB 时钟
     * 2. 分频系数
     * 3. 窗口值
     * 4. 中断/复位模式
     */
    *WWDG_CFR = WWDG_WINDOW_MAX;
    *WWDG_CR = WWDG_COUNTER_START;
}

static bool wwdg_refresh(void)
{
    uint32_t counter = *WWDG_CR & 0x7Fu;

    if (counter > WWDG_WINDOW_MAX || counter <= WWDG_COUNTER_MIN) {
        return false;
    }

    *WWDG_CR = counter;
    return true;
}
```

**WWDG 不适合直接在多个任务中分别刷新**，否则无法证明系统整体状态。通常应由一个固定节拍的监控任务集中刷新。

---

## 5.3 看门狗复位原因读取

复位后必须尽早读取复位标志，因为某些芯片会在再次复位或写入复位控制寄存器后清除标志。

```
typedef enum {
    RESET_UNKNOWN = 0,
    RESET_POWER_ON,
    RESET_EXTERNAL_PIN,
    RESET_SOFTWARE,
    RESET_IWDG,
    RESET_WWDG,
    RESET_BROWNOUT,
    RESET_HARDFAULT
} reset_reason_t;

typedef struct {
    uint32_t raw_flags;
    reset_reason_t reason;
    uint32_t boot_count;
    uint32_t crash_signature;
} reset_record_t;

static reset_record_t g_reset_record
    __attribute__((section(".noinit")));

static uint32_t reset_flags_read(void)
{
    volatile uint32_t *const RCC_CSR =
        (volatile uint32_t *)0x40021024u;

    return *RCC_CSR;
}

static reset_reason_t reset_reason_decode(uint32_t flags)
{
    if ((flags & (1u << 29)) != 0u) {
        return RESET_IWDG;
    }

    if ((flags & (1u << 30)) != 0u) {
        return RESET_WWDG;
    }

    if ((flags & (1u << 26)) != 0u) {
        return RESET_BROWNOUT;
    }

    if ((flags & (1u << 27)) != 0u) {
        return RESET_SOFTWARE;
    }

    return RESET_UNKNOWN;
}

void reset_reason_capture(void)
{
    uint32_t flags = reset_flags_read();

    g_reset_record.raw_flags = flags;
    g_reset_record.reason = reset_reason_decode(flags);
    g_reset_record.boot_count++;

    /*
     * 必须在这里保存最小诊断信息，然后再清除硬件标志。
     */
}
```

`__attribute__((section(".noinit")))` 只是示例。量产项目还必须确认：

- 该区域不会被 C 启动代码清零。
- 该 RAM 在目标复位类型下确实保留。
- 上电复位时数据可能无效。
- 数据需要 magic、版本号、长度和 CRC。
- 连续看门狗复位需要防止启动循环。

---

## 5.4 RTOS 中的集中式喂狗

错误模型：

```
void task_a(void *arg)
{
    for (;;) {
        do_task_a();
        iwdg_feed();
        os_delay(10);
    }
}

void task_b(void *arg)
{
    for (;;) {
        do_task_b();
        iwdg_feed();
        os_delay(10);
    }
}
```

这个设计的问题是：`task_a` 可能已经假死，但 `task_b` 仍然持续喂狗，系统不会复位。

正确模型是：

```
各任务独立提交心跳
        |
        v
监控任务检查所有任务是否正常
        |
        +-- 全部正常 --> 刷新硬件看门狗
        |
        +-- 任一异常 --> 记录故障，停止喂狗
```

### 任务心跳监控框架

```
#include <stdint.h>
#include <stdbool.h>

#define HEALTH_TASK_COUNT 4u
#define HEALTH_PERIOD_MS  100u

typedef enum {
    HEALTH_OK = 0,
    HEALTH_TIMEOUT,
    HEALTH_NOT_REGISTERED
} health_state_t;

typedef struct {
    const char *name;
    uint32_t period_ms;
    uint32_t last_kick_ms;
    uint32_t kick_count;
    bool registered;
    bool required;
} health_slot_t;

static health_slot_t g_health[HEALTH_TASK_COUNT];

static uint32_t system_time_ms(void);
static void fault_log_health_failure(uint32_t index);
static void disable_watchdog_service(void);
static void iwdg_feed(void);

bool health_register(uint32_t index,
                     const char *name,
                     uint32_t period_ms,
                     bool required)
{
    if (index >= HEALTH_TASK_COUNT ||
        name == NULL ||
        period_ms == 0u) {
        return false;
    }

    g_health[index].name = name;
    g_health[index].period_ms = period_ms;
    g_health[index].last_kick_ms = system_time_ms();
    g_health[index].kick_count = 0u;
    g_health[index].registered = true;
    g_health[index].required = required;

    return true;
}

bool health_kick(uint32_t index)
{
    if (index >= HEALTH_TASK_COUNT ||
        !g_health[index].registered) {
        return false;
    }

    g_health[index].last_kick_ms = system_time_ms();
    g_health[index].kick_count++;
    return true;
}

static bool health_all_ok(void)
{
    uint32_t now = system_time_ms();

    for (uint32_t i = 0u; i < HEALTH_TASK_COUNT; ++i) {
        if (!g_health[i].registered || !g_health[i].required) {
            continue;
        }

        if ((uint32_t)(now - g_health[i].last_kick_ms) >
            g_health[i].period_ms) {
            fault_log_health_failure(i);
            return false;
        }
    }

    return true;
}

void watchdog_monitor_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (health_all_ok()) {
            iwdg_feed();
        } else {
            /*
             * 故障状态下禁止继续刷新硬件看门狗，
             * 让硬件在确定时间内完成复位。
             */
            disable_watchdog_service();
        }

        os_delay(HEALTH_PERIOD_MS);
    }
}
```

这里使用无符号时间差：

```
(uint32_t)(now - last)
```

可以正确处理 32 位 tick 回绕，只要单次判断间隔小于计数器周期的一半。

### 任务心跳不能只验证“任务被调度”

更高质量的健康检查应验证：

- 任务是否按周期执行。
- 任务是否完成关键事务。
- 外设状态机是否推进。
- 队列是否持续消费。
- DMA 是否完成。
- 链路是否在合理时间内收到有效帧。
- 任务是否处于允许的阻塞状态。
- 关键数据是否通过一致性校验。

仅仅在任务循环末尾调用 `health_kick()`，只能证明代码执行到了该位置，不能证明业务功能正确。

---

## 6. 性能量化分析

以下数据以典型 Cortex-M4、80 MHz、FreeRTOS tick 1 kHz、内部 LSI 32 kHz 为参考，实际结果必须在目标芯片上测量。

### 6.1 内存开销

|组件|典型 RAM 开销|
|---|---|
|IWDG 硬件寄存器|0 Byte|
|单个任务健康槽位|20～32 Byte|
|8 个任务健康表|160～256 Byte|
|复位记录|32～128 Byte|
|监控任务栈|256～1024 Byte|
|监控任务 TCB|80～200 Byte|
|合计|约 0.6～1.6 KB|

### 6.2 时间开销

硬件喂狗通常是一次寄存器写：

- Cortex-M4：约 **几十到几百 ns**。
- 总线等待、写缓冲和外设同步后：通常低于 **1 µs**。
- 软件健康检查：复杂度为 `O(N)`。
- `N = 8` 个任务、每 100 ms 检查一次时，CPU 占用通常低于 **0.01%** 。

健康监控 CPU 占用估算：

CPU Load=Tcheck×fcheckfCPUCPU Load=fCPU​Tcheck​×fcheck​​

例如：

- 检查时间：`8 µs`
- 检查频率：`10 Hz`
- CPU 频率：`80 MHz`

CPULoad=8×10/80,000,000=0.001%CPULoad=8×10/80,000,000=0.001%

### 6.3 超时选择公式

设：

- 监控周期为 `T_monitor`。
- 最大任务正常执行时间为 `T_task_max`。
- 调度抖动为 `J_sched`。
- 中断阻塞时间为 `T_irq_block`。
- 系统启动阶段最长初始化时间为 `T_boot_max`。
- 安全裕量为 `M`。

任务健康超时时间至少满足：

Thealth≥Ttask,max+Jsched+Tirq,block+MThealth​≥Ttask,max​+Jsched​+Tirq,block​+M

硬件看门狗超时至少满足：

Twdt≥Tmonitor+Thealth+Jsystem+MTwdt​≥Tmonitor​+Thealth​+Jsystem​+M

但不能无限增大，因为系统故障恢复时间为：

Trecovery≈Twdt+Treset+Tboot+TserviceTrecovery​≈Twdt​+Treset​+Tboot​+Tservice​

### 6.4 典型参数示例

假设：

- 监控任务周期：`100 ms`
- 任务最长正常运行时间：`60 ms`
- 调度抖动：`10 ms`
- 中断最长阻塞：`5 ms`
- 安全裕量：`25 ms`

则：

Thealth≥60+10+5+25=100msThealth​≥60+10+5+25=100ms

硬件看门狗可设置为：

```
IWDG timeout = 500 ms
监控周期 = 100 ms
健康超时 = 150 ms
启动容忍窗口 = 300 ms
```

系统最大故障恢复时间约为：

```
500 ms + 80 ms reset + 900 ms boot = 1.48 s
```

### 6.5 瓶颈与优化

常见瓶颈：

- LSI 频率误差导致超时偏差。
- 监控任务优先级过低。
- 关键区关闭中断时间过长。
- 任务健康状态更新存在锁竞争。
- 看门狗超时小于合法的最坏执行时间。
- 启动阶段初始化阻塞，但看门狗已提前启动。

优化方法：

1. 使用独立定时器测量 LSI 实际频率。
2. 监控任务设置为高于普通业务任务、低于硬实时中断的优先级。
3. 健康槽位更新使用原子变量或短临界区。
4. 将启动阶段划分为 boot watchdog window 和 runtime watchdog window。
5. 对外设访问使用有限超时，禁止无限等待。
6. 对关键路径测量 WCET，而不是使用平均执行时间。

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否需要 MCU 失控后自动复位？
|
+-- 否 --> 只需要软件超时或任务健康监控
|
+-- 是
    |
    +-- 是否要求主时钟停止后仍能复位？
    |       |
    |       +-- 是 --> 使用 IWDG 或外部看门狗
    |       |
    |       +-- 否
    |           |
    |           +-- 是否需要检测过早刷新？
    |                   |
    |                   +-- 是 --> 使用 WWDG 或外部窗口看门狗
    |                   |
    |                   +-- 否 --> 使用 IWDG
    |
    +-- 是否属于安全关键/高可靠系统？
            |
            +-- 是 --> IWDG + 任务健康监控 + 外部看门狗
            |
            +-- 否 --> IWDG + 任务健康监控
```

### 7.2 典型场景选型

|场景|需求|方案|理由|
|---|---|---|---|
|电池供电传感器|低功耗、主时钟可能关闭|IWDG 或低功耗唤醒看门狗|独立时钟，适合时钟切换|
|电机控制器|需要检测控制循环异常|WWDG + 硬件故障输入|可检测过晚和过早服务|
|网关设备|多任务、通信链路复杂|IWDG + 任务健康表|检查任务、队列和链路|
|工业 PLC|高可靠、现场无人值守|IWDG + 外部看门狗|提高 MCU 失控时的独立恢复能力|
|汽车 ECU|需要故障记录和诊断|外部窗口看门狗 + 安全监控|防止软件伪造正常服务|
|简单裸机设备|代码路径简单|IWDG + 主循环心跳|实现成本低，覆盖基本死循环|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **硬件看门狗只允许一个服务者。**
2. **业务任务不直接喂硬件看门狗。**
3. **故障状态下禁止喂狗。**
4. 看门狗服务路径必须无阻塞、无动态内存、无复杂日志输出。
5. 所有外设轮询都必须具备有限超时。
6. 启动阶段、正常运行阶段、升级阶段应使用不同策略。
7. 看门狗复位后必须记录最小故障上下文。
8. 复位循环必须具备降级模式或安全状态。
9. 看门狗超时时间根据最坏执行时间确定，不根据平均值确定。
10. 关闭看门狗只能在调试配置中允许，量产版本禁止关闭。

### 8.2 选型决策矩阵

评分范围：1 分低，5 分高。

|指标|IWDG|WWDG|外部看门狗|软件看门狗|
|---|---|---|---|---|
|MCU 失控恢复能力|4|3|5|1|
|时序异常检测|2|5|4|3|
|硬件独立性|4|2|5|1|
|成本|5|5|2|5|
|低功耗适配|4|2|4|2|
|多任务诊断能力|2|2|2|5|
|认证适配能力|3|3|5|2|

### 8.3 工业级编码规范

推荐接口：

```
typedef struct {
    uint32_t timeout_ms;
    uint32_t service_period_ms;
    bool start_early;
    bool enable_task_monitor;
} watchdog_policy_t;

typedef enum {
    WD_STATE_INIT = 0,
    WD_STATE_RUNNING,
    WD_STATE_DEGRADED,
    WD_STATE_RESET_PENDING
} watchdog_state_t;

bool watchdog_init(const watchdog_policy_t *policy);
bool watchdog_register_task(uint32_t id,
                            const char *name,
                            uint32_t deadline_ms);
bool watchdog_task_checkpoint(uint32_t id);
void watchdog_monitor_step(void);
watchdog_state_t watchdog_get_state(void);
```

禁止以下设计：

```
#define FEED_WATCHDOG() IWDG->KR = 0xAAAA
```

原因：

- 所有模块都能调用。
- 无法追踪调用者。
- 无法阻止错误状态喂狗。
- 无法测试任务级健康状态。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：所有任务直接喂狗

### 错误代码

```
void communication_task(void *arg)
{
    for (;;) {
        receive_packet();
        iwdg_feed();
    }
}
```

### 根因

只要通信任务仍然运行，即使控制任务已经死锁，硬件看门狗仍会被刷新。

### 正确实现

```
void communication_task(void *arg)
{
    for (;;) {
        if (receive_packet_with_timeout(100u)) {
            process_packet();
        }

        health_kick(COMM_TASK_ID);
    }
}
```

由监控任务统一刷新硬件看门狗。

### 风险影响

- 单任务假死无法被发现。
- 设备表现为“部分功能失效但不复位”。
- 现场问题长期积累，最终造成不可预测状态。

---

## 9.2 错误二：在阻塞操作后才刷新

### 错误代码

```
void sensor_task(void *arg)
{
    for (;;) {
        sensor_wait_data();  /* 可能永久阻塞 */
        sensor_process();
        iwdg_feed();
    }
}
```

### 根因

驱动等待外设状态没有超时，喂狗位于不可达路径之后。

### 正确实现

```
bool sensor_wait_data(uint32_t timeout_ms);

void sensor_task(void *arg)
{
    for (;;) {
        if (!sensor_wait_data(50u)) {
            sensor_recover();
            health_report_fault(SENSOR_WAIT_TIMEOUT);
            break;
        }

        sensor_process();
        health_kick(SENSOR_TASK_ID);
    }
}
```

### 风险影响

- 外设线缆断开时系统永久阻塞。
- 设备必须依赖硬件看门狗，但故障上下文可能未记录。
- 造成无法区分软件故障和外设故障。

---

## 9.3 错误三：看门狗超时设置过短

### 错误代码

```
/* 正常 Flash 擦除耗时最高 800 ms */
iwdg_init(100u);
flash_erase_sector();
```

### 根因

超时时间按照典型耗时或主观经验设置，没有考虑最坏执行时间。

### 正确实现

```
#define FLASH_ERASE_WCET_MS    800u
#define SYSTEM_JITTER_MS       50u
#define SAFETY_MARGIN_MS       150u

#define WDT_TIMEOUT_MS \
    (FLASH_ERASE_WCET_MS + SYSTEM_JITTER_MS + SAFETY_MARGIN_MS)
```

更优方案是：

- 将 Flash 擦除放入专用状态机。
- 使用中断或 DMA。
- 在硬件允许的情况下，在合法的原子阶段刷新。
- 将长操作纳入任务健康模型。

### 风险影响

- 正常业务触发误复位。
- 数据写入过程被打断。
- 文件系统或参数区损坏。

---

## 9.4 错误四：忽略 LSI 频率误差

### 错误代码

```
/* 假设 LSI 永远等于 32 kHz */
timeout_ms = reload * prescaler * 1000u / 32000u;
```

### 根因

内部低速振荡器受电压、温度和工艺影响，标称频率不是精密时钟。

### 正确实现

```
static uint32_t watchdog_timeout_worst_case_ms(uint32_t reload,
                                                 uint32_t prescaler,
                                                 uint32_t lsi_min_hz)
{
    uint64_t ticks = (uint64_t)(reload + 1u) * prescaler;

    if (lsi_min_hz == 0u) {
        return 0u;
    }

    return (uint32_t)((ticks * 1000u) / lsi_min_hz);
}
```

### 风险影响

- 实际超时时间比预期短，产生误复位。
- 不同温度下行为不一致。
- 现场问题难以复现。

---

## 9.5 错误五：启动后不读取复位原因

### 错误代码

```
int main(void)
{
    system_init();
    clear_reset_flags();
    application_start();
}
```

### 根因

在读取看门狗复位原因之前就清除了硬件状态。

### 正确实现

```
int main(void)
{
    reset_reason_capture();
    clear_reset_flags();

    system_init();
    application_start();
}
```

### 风险影响

- 无法统计看门狗复位次数。
- 无法发现设备进入复位循环。
- 现场日志缺少关键故障证据。

---

## 10. 多机制组合使用方案

### 10.1 推荐架构

```
+----------------------+
                |   业务任务健康检查    |
                |  周期/状态/事务完成    |
                +----------+-----------+
                           |
                           v
+-------------+     +------+-------+     +----------------+
| 通信超时检测 | --> | Watchdog Mgr | --> | 硬件 IWDG     |
+-------------+     +------+-------+     +----------------+
                           |
                           +----------> 故障日志/复位原因
                           |
                           +----------> 外设复位/降级模式
                           |
                           +----------> 外部看门狗服务
```

### 10.2 状态机

```
INIT
 |
 +-- 所有必要任务注册成功 --> RUNNING
 |
 +-- 注册超时 --> DEGRADED
                       |
                       +-- 尝试恢复模块
                       |
                       +-- 恢复成功 --> RUNNING
                       |
                       +-- 恢复失败 --> RESET_PENDING
RUNNING
 |
 +-- 健康检查失败 --> DEGRADED
                         |
                         +-- 可恢复 --> RUNNING
                         |
                         +-- 不可恢复 --> 停止喂狗
```

### 10.3 组合框架

```
typedef struct {
    watchdog_state_t state;
    uint32_t fault_bitmap;
    uint32_t last_check_ms;
    uint32_t consecutive_failures;
} watchdog_manager_t;

static watchdog_manager_t g_wdm;

static bool watchdog_policy_check(void)
{
    if (!health_all_ok()) {
        g_wdm.fault_bitmap |= (1u << 0);
        return false;
    }

    if (!communication_link_is_alive()) {
        g_wdm.fault_bitmap |= (1u << 1);
        return false;
    }

    if (!critical_peripheral_is_valid()) {
        g_wdm.fault_bitmap |= (1u << 2);
        return false;
    }

    return true;
}

void watchdog_manager_step(void)
{
    bool healthy = watchdog_policy_check();

    if (healthy) {
        g_wdm.state = WD_STATE_RUNNING;
        g_wdm.consecutive_failures = 0u;
        iwdg_feed();
        external_watchdog_service();
        return;
    }

    g_wdm.consecutive_failures++;

    if (recoverable_fault(g_wdm.fault_bitmap)) {
        g_wdm.state = WD_STATE_DEGRADED;
        recover_failed_modules(g_wdm.fault_bitmap);
        return;
    }

    g_wdm.state = WD_STATE_RESET_PENDING;
    persist_fault_record(&g_wdm);

    /*
     * 不再刷新硬件看门狗，让系统在确定时间内复位。
     */
}
```

关键原则：

- **软件监控负责判断问题。**
- **硬件看门狗负责最终执行复位。**
- **外部看门狗负责防止 MCU 自己伪造健康状态。**
- **模块恢复优先于系统复位，但恢复必须有明确上限。**

---

## 11. 工业级实际案例分析

## 11.1 工业数据采集网关

### 需求

- 4 个 RS-485 通道。
- Ethernet 上报。
- 采集周期 100 ms。
- 任一通信任务异常时，系统应在 1 s 内恢复。
- 复位后保留最后一次故障原因。

### 架构设计

```
RS485 Task x4
    |
    v
采集状态机
    |
    v
数据队列 --> Ethernet Task --> 云端
    |
    v
Watchdog Monitor Task --> IWDG
```

### 设计要点

- 每个 RS-485 任务独立心跳。
- 接收等待必须有超时。
- Ethernet 断链先执行链路重连。
- 连续 3 次重连失败后进入降级模式。
- 任务健康失败时先记录任务名、队列深度、最近错误码。
- 监控任务每 100 ms 执行一次，IWDG 设置 1 s。

### 核心代码

```
void rs485_task(void *arg)
{
    uint32_t channel = (uint32_t)arg;

    for (;;) {
        if (!rs485_receive(channel, 80u)) {
            rs485_reset(channel);
            health_report_fault(channel, RS485_TIMEOUT);
        }

        health_kick(RS485_TASK_BASE_ID + channel);
        os_delay(20u);
    }
}
```

---

## 11.2 电机控制器

### 需求

- 控制周期 1 ms。
- 过流、过压必须快速关闭 PWM。
- 控制循环异常时不能持续输出危险占空比。
- MCU 主频可能因时钟故障降级。

### 架构设计

```
PWM 定时器更新中断
        |
        v
控制算法执行
        |
        +--> 硬件比较器 --> PWM 紧急关闭
        |
        +--> WWDG 服务窗口
        |
        +--> 故障状态机
```

### 设计要点

- 不依赖软件看门狗处理过流，过流必须由硬件比较器直接关闭 PWM。
- WWDG 用于检测控制循环过早或过晚执行。
- 设置硬件故障输入，使 WWDG 复位前进入安全输出状态。
- 看门狗复位后默认关闭 PWM，不能直接恢复输出。
- 启动时必须经过校准、母线电压检查和驱动器握手。

### 核心策略

```
void motor_control_isr(void)
{
    if (comparator_over_current()) {
        pwm_emergency_off();
        fault_latch(MOTOR_OVERCURRENT);
        return;
    }

    if (!control_loop_execute()) {
        pwm_emergency_off();
        fault_latch(MOTOR_CONTROL_ERROR);
        return;
    }

    /*
     * 实际项目中应由固定定时点服务 WWDG，
     * 不能由任意业务代码调用。
     */
    wwdg_service_in_valid_window();
}
```

---

## 11.3 高可靠远程终端

### 需求

- 长期无人值守运行。
- 现场可能存在 EMI、电源波动和 MCU 锁死。
- 需要区分软件、供电、外部复位和看门狗复位。
- 连续异常时进入安全降级模式。

### 架构设计

```
MCU IWDG
    |
    v
外部窗口看门狗
    |
    v
电源监控/复位芯片
    |
    v
安全输出与故障保持电路
```

### 设计要点

- IWDG 处理大多数软件故障。
- 外部看门狗处理 MCU 完全停止、时钟异常和错误服务信号。
- 外部看门狗服务信号不能直接由普通任务产生。
- 复位记录存入保留 RAM，同时周期性写入磨损均衡 Flash 区域。
- 5 分钟内连续 3 次看门狗复位后进入降级模式。
- 降级模式关闭非关键通信，只保留维护链路。

---

## 12. 高频问题深度答疑

### 问题一：看门狗应该设置多长？

没有通用固定值，应基于最坏执行时间和恢复目标。

基本约束：

Twdt>Tmonitor+Thealth+J+MTwdt​>Tmonitor​+Thealth​+J+M

同时：

Trecovery≤Tsystem_requirementTrecovery​≤Tsystem_requirement​

如果系统要求 2 秒内恢复，而启动时间需要 800 ms，则看门狗通常不应设置为 2 秒，必须为复位和启动保留足够预算。

### 问题二：为什么不能在中断里喂狗？

中断可能仍然持续触发，即使任务调度器已经失效。若在周期中断里喂狗，以下故障可能无法检测：

- 任务全部阻塞。
- RTOS 调度器停止。
- 业务状态机死锁。
- 通信任务不再处理数据。

只有当中断本身就是被监控的关键控制循环，并且其执行结果经过完整验证时，才可以让中断参与服务窗口。

### 问题三：任务心跳和软件看门狗有什么区别？

任务心跳是状态证据，软件看门狗是超时执行逻辑。

```
任务心跳：我完成了一个关键周期
软件看门狗：超过截止时间仍未收到证据
硬件看门狗：超过最终期限仍未被允许服务
```

三者职责不同，通常应组合使用。

### 问题四：看门狗复位后是否应该自动重新启动业务？

不应无条件自动恢复。

如果存在连续复位，应执行：

```
第一次复位 --> 正常启动
第二次复位 --> 记录并减少非关键模块
第三次复位 --> 降级模式
持续复位 --> 等待人工维护或外部电源周期
```

否则系统可能进入永久重启循环，无法提供诊断能力。

### 问题五：低功耗模式下看门狗会不会继续运行？

取决于具体 MCU：

- IWDG 常由独立低速时钟驱动，可能继续运行。
- WWDG 通常依赖 APB 时钟，进入停止模式后可能暂停。
- 某些 MCU 支持在低功耗模式下选择保持或停止 IWDG。
- 唤醒时间必须纳入超时预算。

必须查看参考手册中的：

- Clock source。
- Sleep/Stop/Standby 行为。
- Reset domain。
- Debug freeze 配置。

### 问题六：调试时为什么看门狗不断复位？

调试器暂停 CPU 时，任务不会运行，软件也无法刷新看门狗。

解决方案：

- 调试环境配置 DBG freeze。
- 或将 watchdog timeout 临时增大。
- 或使用调试编译选项跳过硬件启动。
- 量产构建必须恢复真实看门狗配置。
- 验证调试配置不会被带入生产固件。

---

## 13. 课程核心总结

### 核心要点

1. **硬件看门狗是最终复位机制，不是任务调度机制。**
2. **任务不能直接喂硬件看门狗，必须通过集中式健康监控。**
3. **健康检查应验证关键业务进展，而不是只验证函数被调用。**
4. IWDG 适合提供独立于主时钟的最终恢复。
5. WWDG 适合检测过早刷新和执行时序异常。
6. 外部看门狗适合安全关键和高可靠系统。
7. 所有硬件等待、通信等待和资源等待必须有超时。
8. 复位原因记录是量产系统诊断闭环的一部分。
9. 超时时间必须基于 WCET、调度抖动和时钟误差计算。
10. 故障状态下继续喂狗，会把真实故障隐藏为“系统仍在运行”。

### 性能排序

按服务操作的 CPU 开销从低到高：

```
硬件寄存器刷新
    <
单变量任务心跳更新
    <
固定数组健康检查
    <
复杂状态一致性检查
    <
跨模块恢复与故障日志持久化
```

按故障独立性从低到高：

```
软件看门狗
    <
MCU 内部 WWDG
    <
MCU 内部 IWDG
    <
外部独立看门狗
```

### 通用选型结论

- 普通裸机：**IWDG + 主循环健康检查**。
- RTOS 多任务：**IWDG + 集中式任务监控**。
- 严格时序控制：**WWDG + 硬件安全输出**。
- 高可靠设备：**IWDG + 外部看门狗 + 故障日志**。
- 安全关键系统：**外部窗口看门狗 + 独立故障通道 + 降级策略**。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选方案|
|---|---|
|裸机主循环卡死|IWDG|
|RTOS 某任务假死|任务心跳 + IWDG|
|控制周期过早/过晚|WWDG|
|MCU 时钟或 CPU 完全失控|外部看门狗|
|通信超时恢复|协议超时 + 链路重连|
|高安全等级产品|IWDG + 外部窗口看门狗|
|低功耗周期唤醒|独立低速时钟看门狗|
|复杂启动流程|启动阶段看门狗策略 + 分阶段健康检查|

### 14.2 特性对比表

|特性|IWDG|WWDG|外部看门狗|软件健康监控|
|---|---|---|---|---|
|自动复位|是|是|是|否，通常请求复位|
|检测任务假死|弱|弱|弱|强|
|检测过早执行|否|是|可选|可实现|
|时钟独立|通常是|通常否|是|否|
|运行时可诊断|低|低|低|高|
|对系统架构价值|最终防线|时序约束|独立防线|健康模型|

### 14.3 超时时间速查

```
健康检查周期:
    T_monitor = 10%～25% 的最短关键任务周期

任务健康超时:
    T_health >= WCET + 调度抖动 + 中断阻塞 + 安全裕量

硬件看门狗:
    T_wdt >= 监控周期 + 健康超时 + 系统抖动 + 安全裕量

恢复时间:
    T_recovery = 看门狗超时 + 复位时间 + 启动时间 + 服务恢复时间
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

- [ ]  能够写出 IWDG 超时时间计算公式。
- [ ]  能够解释 LSI 频率误差如何影响实际超时。
- [ ]  能够区分 IWDG 和 WWDG 的故障覆盖范围。
- [ ]  能够说明为什么多个任务不能直接喂硬件看门狗。
- [ ]  能够设计至少 4 个任务的健康监控表。
- [ ]  能够处理 tick 回绕问题。
- [ ]  能够为外设等待逻辑增加有限超时。
- [ ]  能够在启动早期读取并保存复位原因。
- [ ]  能够设计连续看门狗复位后的降级策略。
- [ ]  能够计算系统最大故障恢复时间。
- [ ]  能够说明低功耗模式下看门狗的时钟行为。
- [ ]  能够使用故障注入验证看门狗是否真正生效。
- [ ]  能够解释为什么过短和过长的超时都存在风险。
- [ ]  能够设计 IWDG、任务健康监控和外部看门狗的组合架构。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：裸机 IWDG 驱动

要求：

- 配置独立低速时钟。
- 设置 100 ms、500 ms、1 s 三组超时。
- 测量实际超时时间。
- 主循环正常喂狗。
- 通过死循环验证自动复位。

验收指标：

- 实际超时误差在芯片手册规定范围内。
- 能够正确读取 IWDG 复位标志。
- 死循环后能够自动重启。

#### 任务二：RTOS 多任务健康监控

要求：

- 创建采集、通信、存储、诊断 4 个任务。
- 只有监控任务能够刷新硬件看门狗。
- 每个任务提交心跳。
- 模拟任意任务永久阻塞。
- 记录失败任务 ID 和最近一次心跳时间。

验收指标：

- 单任务假死能够被识别。
- 监控任务自身停止运行时，硬件看门狗仍能复位系统。
- 正常运行不产生误复位。

#### 任务三：窗口看门狗时序验证

要求：

- 配置 WWDG 有效窗口。
- 测试窗口内刷新。
- 测试过早刷新。
- 测试过晚刷新。
- 通过 GPIO 翻转测量刷新时间点。

验收指标：

- 两类违规都能触发预期故障。
- 能够区分 WWDG 复位和软件复位。
- 能够记录违规前的运行状态。

#### 任务四：工业级故障恢复框架

要求：

- 加入通信超时、外设复位、任务健康、IWDG 和复位记录。
- 实现第一次故障模块恢复。
- 实现连续故障降级。
- 实现连续复位保护。
- 增加故障注入命令。

验收指标：

- 可恢复故障不触发系统复位。
- 不可恢复故障在目标时间内复位。
- 连续复位后能够进入降级模式。
- 日志能够重建故障时间线。

### 16.2 性能测试方法

1. 使用 GPIO 在监控任务进入和退出时翻转。
2. 用逻辑分析仪测量：
    - 监控周期。
    - 最大调度抖动。
    - 最长中断阻塞时间。
    - 看门狗刷新间隔。
3. 改变温度和供电电压，测量 LSI 实际频率。
4. 注入以下故障：
    - 任务死循环。
    - 任务永久阻塞。
    - 中断风暴。
    - 互斥锁死锁。
    - DMA 永不完成。
    - Flash 操作超时。
    - 堆耗尽。
    - 栈溢出。
5. 测量：
    - 故障发生到健康监控发现的时间。
    - 监控发现到系统复位的时间。
    - 复位到系统重新可服务的时间。
6. 检查看门狗复位前是否成功保存故障上下文。

### 16.3 进阶学习方向

- MCU 复位域与电源域分析。
- 外部窗口看门狗芯片选型与服务协议。
- IEC 61508、ISO 26262 看门狗诊断覆盖率。
- AUTOSAR Watchdog Manager 与 Watchdog Interface。
- FreeRTOS 任务运行时间统计和运行时栈检查。
- HardFault、MemManage Fault、BusFault 统一故障框架。
- 启动阶段 Boot Watchdog 与安全启动。
- 双镜像升级、回滚和看门狗协同。
- 锁步 MCU、独立监控核和安全岛架构。
- 看门狗故障注入自动化与硬件在环测试。
- 基于窗口看门狗的执行流完整性验证。
- 使用独立外部电源监控实现 MCU 之外的系统级复位链路。