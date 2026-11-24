
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 MCU 低功耗的本质：**时钟门控、功耗域关闭、电源保持、唤醒源管理**。
- 区分 Sleep、Stop、Standby 三类模式在以下方面的差异：
    - CPU 状态是否保持；
    - SRAM、寄存器、外设状态是否保持；
    - 时钟树是否关闭；
    - 唤醒延迟；
    - 唤醒后软件执行路径；
    - 功耗与数据保持能力。
- 理解动态功耗、静态功耗、漏电流和唤醒能量之间的关系。

### 掌握

能够：

- 正确配置 SysTick、RTC、低功耗定时器、GPIO、外部中断等唤醒源。
- 正确处理进入低功耗前的：
    - 中断竞态；
    - 外设停机；
    - Cache、DMA、串口发送；
    - GPIO 浮空输入；
    - 电源域状态保存。
- 使用 `WFI`、`WFE`、Stop、Standby 等机制构建低功耗状态机。
- 使用示波器、电流分析仪测量睡眠电流、唤醒延迟和能量消耗。

### 精通

能够深入分析：

- `WFI` 执行后的 ARM Cortex-M 内核行为。
- `SLEEPDEEP`、`SLEEPONEXIT`、事件寄存器、中断挂起状态与低功耗行为的关系。
- Stop 模式下 RAM 保持、时钟重启和 PLL 重配置问题。
- Standby 模式下复位型唤醒、备份域和唤醒原因判断。
- 低功耗设计中的竞态、伪唤醒、优先级反转、时基异常和唤醒风暴。

### 能够设计

能够设计：

- 低功耗系统状态机；
- 多级睡眠策略；
- 带 RTC 定时唤醒和 GPIO 唤醒的工业设备低功耗框架；
- 低功耗通信终端的睡眠窗口调度方案；
- 可量化验证的功耗预算和能量模型。

---

## 2. 前置要求

### 知识要求

- ARM Cortex-M 异常、中断、NVIC 和异常返回机制。
- MCU 时钟树：HSI、HSE、PLL、系统时钟、总线时钟和外设时钟。
- SRAM、Flash、备份寄存器、RTC 和电源域。
- RTOS 调度器、Tick、中断安全和临界区。
- GPIO、UART、SPI、I²C、DMA、RTC、低功耗定时器。
- 基本电源管理知识，包括 LDO、DCDC、负载开关和漏电流。

### 技能要求

- 能够阅读 MCU Reference Manual 的 Power Control、RCC、RTC、PWR 章节。
- 能够使用示波器或功耗分析仪进行电流测量。
- 能够编写启动文件、链接脚本和寄存器级初始化代码。
- 能够定位 HardFault、唤醒源错误和时钟恢复错误。
- 能够编写硬件抽象层与 RTOS BSP。

---

## 3. 技术概述

## 3.1 低功耗的本质

MCU 总功耗可近似表示为：

Ptotal=Pdynamic+Pstatic+Pperipheral+PexternalPtotal​=Pdynamic​+Pstatic​+Pperipheral​+Pexternal​

其中动态功耗近似为：

Pdynamic=αCV2fPdynamic​=αCV2f

- αα：翻转活动因子；
- CC：等效负载电容；
- VV：电压；
- ff：工作频率。

低功耗模式的核心手段有四类：

1. **降低频率**
2. **降低电压**
3. **关闭时钟**
4. **关闭或隔离电源域**

Sleep 主要使用第 3 类；Stop 通常同时使用第 3、4 类；Standby 则进一步关闭更多电源域，只保留最小唤醒逻辑。

---

## 3.2 三类睡眠模式

### Sleep

典型特征：

- CPU 时钟停止；
- 外设时钟通常仍可运行；
- SRAM、寄存器和系统上下文保持；
- 中断唤醒后直接从 `WFI` 后继续执行；
- 唤醒延迟通常为微秒级；
- 功耗通常为几十微安至数毫安，取决于外设状态。

适合：

- RTOS 空闲任务；
- 高频率、短时间休眠；
- UART、DMA、定时器仍需运行的场景；
- 要求快速响应的控制系统。

### Stop

典型特征：

- CPU 时钟停止；
- 高速时钟源和 PLL 通常关闭；
- 部分低速时钟仍可运行；
- SRAM 通常保持；
- 外设是否保持取决于 MCU 型号和 Stop 子模式；
- 唤醒后通常需要重新配置系统时钟；
- 功耗通常为几微安至数十微安；
- 唤醒延迟通常为几十微秒至数毫秒。

适合：

- 电池设备的空闲窗口；
- 需要保留 RAM 上下文；
- RTC、LPTIM、GPIO、低功耗串口唤醒；
- 低功耗但仍需较快恢复的场景。

### Standby

典型特征：

- 主电源域大部分关闭；
- CPU、绝大多数 SRAM 和外设寄存器状态丢失；
- 只保留备份域、RTC、唤醒逻辑或少量 SRAM；
- 唤醒通常表现为复位或类似复位流程；
- 功耗可低至亚微安至数微安；
- 唤醒延迟通常高于 Stop；
- 必须通过备份寄存器、Retention RAM 或唤醒标志判断唤醒原因。

适合：

- 长时间无操作设备；
- 运输、仓储、电子标签；
- 电池寿命以月或年为目标的场景；
- 可以接受完整系统重启的设备。

---

## 4. 核心特性横向对比

以下数据以典型 3.3 V、Cortex-M4/M33、25 ℃、无外部负载为参考，**实际数值必须以具体 MCU 数据手册为准**。

|维度|Run|Sleep|Stop|Standby|
|---|---|---|---|---|
|CPU 状态|运行|停止|停止|丢失|
|SRAM|保持|保持|通常保持|通常丢失|
|高速时钟|运行|可选运行|关闭|关闭|
|PLL|运行|可选|通常关闭|关闭|
|RTC|可运行|可运行|可运行|可运行|
|GPIO 状态|保持|保持|通常保持|需按芯片定义|
|外设寄存器|保持|保持|部分保持|通常丢失|
|唤醒方式|中断/事件|中断/事件|中断/事件|复位/唤醒事件|
|典型电流|2~30 mA|0.5~5 mA|2~30 μA|0.2~5 μA|
|唤醒延迟|0|1~10 μs|10~500 μs|0.5~10 ms|
|上下文恢复|无|继续执行|时钟恢复|系统重新初始化|
|设计复杂度|低|中|高|高|
|适合持续睡眠时间|任意|μs~ms|ms~分钟|秒~数月|

---

## 5. 底层原理与功能特性深度解析

## 5.1 Cortex-M 的 `WFI` 原理

典型代码：

```
__attribute__((always_inline))
static inline void cpu_wfi(void)
{
    __asm volatile (
        "dsb 0xF\n"
        "wfi\n"
        "isb 0xF\n"
        ::: "memory"
    );
}
```

### `WFI` 的作用

`WFI` 是 Wait For Interrupt：

- 当前线程执行到 `WFI`；
- 如果没有满足唤醒条件，处理器进入睡眠；
- 发生可响应中断后，处理器退出睡眠；
- 中断处理完成后，返回 `WFI` 后面的指令。

`WFI` 不会自动关闭所有外设时钟，也不会自动保存应用上下文。它只是向 Cortex-M 内核声明：**当前没有必要继续执行指令**。

### 为什么使用 `DSB`

在进入睡眠前，可能存在尚未完成的 Store 操作，例如：

```
PWR->CR1 |= PWR_CR1_LPMS_STOP0;
SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;
__DSB();
__WFI();
```

`DSB` 确保此前的内存访问完成，避免电源控制寄存器写入尚未生效时就执行 `WFI`。

### 为什么使用 `ISB`

恢复后，`ISB` 使处理器刷新指令流水线，确保后续指令基于最新系统状态执行。

---

## 5.2 `SLEEPDEEP` 决定 Sleep 还是深度睡眠

Cortex-M 使用 `SCB->SCR.SLEEPDEEP` 选择睡眠深度：

```
#define SCB_SCR_SLEEPDEEP_Msk (1UL << 2)

static void cortexm_set_deep_sleep(bool enable)
{
    if (enable) {
        SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;
    } else {
        SCB->SCR &= ~SCB_SCR_SLEEPDEEP_Msk;
    }
}
```

- `SLEEPDEEP = 0`：普通 Sleep；
- `SLEEPDEEP = 1`：由 MCU 的 PWR 控制器选择 Stop 或 Standby 等深度模式。

**关键结论：**

> `WFI` 本身不是 Stop 或 Standby；`WFI + SLEEPDEEP + PWR 配置` 才构成深度睡眠。

---

## 5.3 Sleep 模式设计

Sleep 模式最适合 RTOS Idle Hook。

```
void platform_idle(void)
{
    /*
     * 进入临界区只用于检查调度器状态，
     * 不应长时间关闭中断。
     */
    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    if (rtos_has_pending_work() == false) {
        __DSB();
        __WFI();
        __ISB();
    }

    if (primask == 0U) {
        __enable_irq();
    }
}
```

### 中断竞态问题

错误逻辑：

```
if (!has_pending_work()) {
    __enable_irq();
    __WFI();
}
```

竞态过程：

1. CPU 检查没有任务；
2. 恰好在 `enable_irq` 和 `WFI` 之间发生中断；
3. 中断服务完成；
4. CPU 执行 `WFI`；
5. 由于中断已处理，CPU 可能再次睡眠；
6. 新任务可能无人处理，造成异常延迟。

正确方案：

- 在关闭中断状态下检查条件；
- 直接执行 `WFI`；
- 中断到来时唤醒；
- `WFI` 返回后再恢复中断。

在 RTOS 中还应使用内核提供的 `portSUPPRESS_TICKS_AND_SLEEP()` 或等价接口，而不是自行修改调度器状态。

---

## 5.4 `WFE` 与事件机制

`WFE` 是 Wait For Event，唤醒条件不仅包括中断，还包括事件寄存器。

常见安全写法：

```
static void cpu_wfe(void)
{
    __SEV();
    __WFE();  /* 清除可能残留的事件 */
    __WFE();  /* 真正等待事件 */
}
```

适用场景：

- 多核或协处理器通知；
- 轻量级事件同步；
- 不希望进入完整中断处理路径的场景。

但在典型 MCU RTOS 空闲任务中，**优先使用内核封装的等待机制**，不要直接混用 `WFE` 和事件寄存器，否则可能引入难以复现的伪唤醒。

---

## 5.5 Stop 模式的进入与恢复

以下示例采用 STM32 风格伪寄存器接口，具体寄存器名称需按芯片修改。

```
typedef enum {
    LOW_POWER_OK = 0,
    LOW_POWER_ERR_ARG,
    LOW_POWER_ERR_CLOCK,
    LOW_POWER_ERR_PERIPHERAL,
} low_power_status_t;

static uint32_t g_saved_sysclk_hz;

static low_power_status_t low_power_prepare(void)
{
    /*
     * 1. 停止周期性 Tick，避免每 1 ms 唤醒一次。
     * 2. 等待 DMA/UART 发送完成。
     * 3. 关闭不需要保持的外设时钟。
     * 4. 配置 GPIO 为确定状态，避免浮空和上下拉分压。
     */
    if (!uart_tx_idle()) {
        return LOW_POWER_ERR_PERIPHERAL;
    }

    if (!dma_all_idle()) {
        return LOW_POWER_ERR_PERIPHERAL;
    }

    g_saved_sysclk_hz = clock_get_sysclk_hz();

    rtc_prepare_wakeup();
    gpio_enter_low_power_state();
    peripheral_suspend_for_stop();

    return LOW_POWER_OK;
}

static low_power_status_t low_power_restore(void)
{
    if (!clock_restore_system()) {
        return LOW_POWER_ERR_CLOCK;
    }

    peripheral_resume_after_stop();
    gpio_restore_run_state();
    rtc_clear_wakeup_flags();

    return LOW_POWER_OK;
}

low_power_status_t mcu_enter_stop(void)
{
    low_power_status_t ret;

    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    ret = low_power_prepare();
    if (ret != LOW_POWER_OK) {
        if (primask == 0U) {
            __enable_irq();
        }
        return ret;
    }

    /*
     * 防止在准备结束后到 WFI 前丢失唤醒事件。
     */
    SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;
    pwr_select_stop_mode();
    pwr_clear_wakeup_flags();

    __DSB();
    __WFI();
    __ISB();

    SCB->SCR &= ~SCB_SCR_SLEEPDEEP_Msk;

    ret = low_power_restore();

    if (primask == 0U) {
        __enable_irq();
    }

    return ret;
}
```

### Stop 唤醒后的核心问题

Stop 唤醒后，很多 MCU 的系统时钟默认回到：

- MSI；
- HSI；
- 内部低速时钟；
- 复位后默认时钟源。

因此必须重新：

1. 启用 HSE；
2. 等待 HSE Ready；
3. 配置 PLL；
4. 切换 SYSCLK；
5. 更新 Flash 等待周期；
6. 更新 `SystemCoreClock`；
7. 恢复 UART 波特率、SPI 分频、定时器配置。

错误地假设系统时钟仍为 80 MHz，可能导致：

- UART 波特率错误；
- 定时器周期错误；
- 软件超时失效；
- RTOS 时间基异常。

---

## 5.6 Standby 模式与复位型唤醒

Standby 的设计重点不是“唤醒后继续执行”，而是：

> **记录进入睡眠前的必要状态，唤醒后重新初始化并恢复状态。**

### 进入前保存状态

```
typedef struct {
    uint32_t magic;
    uint32_t wake_generation;
    uint32_t application_state;
    uint32_t crc;
} standby_context_t;

#define STANDBY_MAGIC 0x53544259UL

static bool standby_save_context(uint32_t app_state)
{
    standby_context_t ctx = {
        .magic = STANDBY_MAGIC,
        .wake_generation = backup_read(BKP_REG_GENERATION),
        .application_state = app_state,
        .crc = 0U,
    };

    ctx.crc = crc32(&ctx, sizeof(ctx) - sizeof(ctx.crc));

    if (!backup_write_context(&ctx)) {
        return false;
    }

    backup_write(BKP_REG_VALID, 1U);
    return true;
}
```

### 唤醒后判断

```
typedef enum {
    WAKE_COLD_BOOT = 0,
    WAKE_RTC,
    WAKE_GPIO,
    WAKE_UNKNOWN,
} wake_reason_t;

static wake_reason_t detect_wakeup_reason(void)
{
    uint32_t flags = pwr_get_wakeup_flags();

    if (flags & PWR_WAKEUP_RTC) {
        return WAKE_RTC;
    }

    if (flags & PWR_WAKEUP_PIN) {
        return WAKE_GPIO;
    }

    return WAKE_COLD_BOOT;
}

void application_boot(void)
{
    wake_reason_t reason = detect_wakeup_reason();

    if (reason != WAKE_COLD_BOOT &&
        backup_context_valid()) {
        standby_context_t ctx;

        if (backup_read_context(&ctx) &&
            ctx.magic == STANDBY_MAGIC &&
            ctx.crc == crc32(&ctx, sizeof(ctx) - sizeof(ctx.crc))) {
            application_resume(ctx.application_state, reason);
        } else {
            application_start_safe_mode();
        }
    } else {
        application_cold_start();
    }

    pwr_clear_wakeup_flags();
}
```

### Standby 的数据保持策略

|数据类型|推荐保存位置|
|---|---|
|唤醒原因|PWR 唤醒标志|
|少量状态字|备份寄存器|
|RTC 相关上下文|Backup SRAM|
|几 KB 状态|Retention SRAM|
|大量数据|外部 FRAM、NOR Flash、文件系统|
|高频写入状态|不建议使用 Flash，需磨损均衡|

---

## 5.7 GPIO 低功耗配置

GPIO 是低功耗系统中最常见的漏电来源之一。

### 原因

- 输入悬空导致电平翻转；
- 外部器件通过 GPIO 反向供电；
- 上拉和下拉同时形成直流通路；
- 两个器件输出电平冲突；
- ADC、比较器或模拟输入未关闭；
- 未使用引脚处于高频模拟切换状态。

### 通用配置原则

|引脚类型|低功耗配置|
|---|---|
|未使用 GPIO|模拟输入或确定电平|
|外部中断输入|保留唤醒电平和正确上下拉|
|外设输出|根据外部电路设置静态安全电平|
|连接传感器|关闭传感器电源或配置负载开关|
|SPI/UART|确保总线无冲突，必要时关闭收发器|
|ADC 输入|按芯片要求配置模拟模式|

```
static void gpio_enter_low_power_state(void)
{
    /*
     * 不能简单地把所有 GPIO 配置为模拟输入。
     * 唤醒脚、外部电源控制脚和安全输出脚必须单独处理。
     */
    gpio_config_analog(GPIO_PORT_A, GPIO_PIN_MASK_UNUSED);
    gpio_set_level(GPIO_SENSOR_EN, 0);
    gpio_config_output(GPIO_SENSOR_EN);

    gpio_config_input_pull(GPIO_WAKE_PIN, GPIO_PULL_UP);

    transceiver_set_shutdown(true);
}
```

---

## 5.8 RTC 与低功耗定时器唤醒

低功耗定时器通常使用 LSE、LSI 或内部低功耗时钟。

若使用 32.768 kHz 的 LSE：

Ttick=132768≈30.5176 μsTtick​=327681​≈30.5176 μs

对于计数值 NN：

Twake=N+132768Twake​=32768N+1​

例如希望 10 秒后唤醒：

N≈10×32768−1=327679N≈10×32768−1=327679

工程注意事项：

- 清除旧的唤醒标志；
- 处理 RTC 写保护；
- 等待同步标志；
- 处理唤醒定时器重装载；
- 考虑 LSE ppm 误差；
- 长时间睡眠必须处理 RTC 溢出；
- 不要使用普通 SysTick 作为 Stop/Standby 唤醒源。

---

## 6. 性能量化分析

## 6.1 测试平台与假设

以下数据为工程测量示例：

- MCU：Cortex-M4，3.3 V；
- Run：80 MHz，DCDC；
- Stop：SRAM 保持，RTC LSE 运行；
- Standby：RTC 和唤醒逻辑保持；
- 温度：25 ℃；
- 板级：移除 USB、调试器和外部传感器负载；
- 仪器：Power Profiler，采样率 100 kSa/s。

|模式|实测电流|唤醒延迟|恢复 CPU 时钟|
|---|---|---|---|
|Run|8.6 mA|—|—|
|Sleep|1.42 mA|2.1 μs|不需要|
|Stop|7.8 μA|96 μs|需要|
|Standby|0.83 μA|2.4 ms|重新启动|

上述数据**不是芯片通用规格**，只能用于说明测量和计算方法。

---

## 6.2 平均电流计算

假设一个周期为：

- Run 处理：20 ms，8.6 mA；
- Stop 睡眠：980 ms，7.8 μA。

Iavg=8.6×20+0.0078×9801000Iavg​=10008.6×20+0.0078×980​Iavg≈0.1796 mAIavg​≈0.1796 mA

若使用 Standby：

- Run：20 ms，8.6 mA；
- Standby：9.98 s，0.00083 mA。

Iavg=8.6×20+0.00083×998010000≈0.0180 mAIavg​=100008.6×20+0.00083×9980​≈0.0180 mA

理论上平均电流约降低 **90%** 。

---

## 6.3 唤醒能量与模式选择

深度模式并不总是更优。必须考虑进入、唤醒和重新初始化能量。

假设：

- Sleep 静态电流：1.42 mA；
- Stop 静态电流：7.8 μA；
- Stop 进入/恢复额外耗时：100 μs；
- 恢复过程平均电流：8.6 mA。

额外唤醒能量近似：

Ewake=V×I×tEwake​=V×I×tEwake=3.3×8.6mA×100μs≈2.84 μJEwake​=3.3×8.6mA×100μs≈2.84 μJ

Sleep 与 Stop 的静态功耗差：

ΔP=3.3×(1.42mA−7.8μA)≈4.66mWΔP=3.3×(1.42mA−7.8μA)≈4.66mW

理论交叉时间：

tbreak−even=EwakeΔP≈0.61mstbreak−even​=ΔPEwake​​≈0.61ms

因此在该假设下，睡眠时间超过约 **1 ms**，Stop 在能量上就可能优于 Sleep。

实际工程还要加上：

- 外设关闭/重启能量；
- PLL 锁定时间；
- 传感器启动时间；
- Flash 访问能量；
- 总线重新配置时间；
- RTOS Tick 补偿成本。

---

## 6.4 瓶颈分析

常见瓶颈：

1. **SysTick 每 1 ms 唤醒**
    
    - Stop 失去意义；
    - 解决：使用 RTC/LPTIM，并在睡眠前抑制 OS Tick。
2. **调试器保持连接**
    
    - Debug freeze 机制可能显著增加功耗；
    - 解决：脱离调试器测量，关闭 DBGMCU 低功耗保持。
3. **GPIO 外部漏电**
    
    - 单个 GPIO 的分压电流可能达到数百微安；
    - 解决：检查电平兼容、电源反灌和上下拉。
4. **LDO 静态电流**
    
    - MCU 进入亚微安，但 LDO 自身消耗数十微安；
    - 解决：选用低 IQ 电源器件。
5. **传感器未断电**
    
    - MCU 低功耗并不等于整机低功耗；
    - 解决：使用负载开关或传感器硬件 Shutdown。

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
开始
 |
 |-- 是否允许系统重新初始化？
 |       |
 |       |-- 否 --> 是否需要外设继续运行？
 |       |              |
 |       |              |-- 是 --> Sleep
 |       |              |
 |       |              |-- 否 --> Stop
 |       |
 |       |-- 是 --> 睡眠时间是否短于 Stop/Standby 唤醒能量交叉点？
 |                      |
 |                      |-- 是 --> Sleep
 |                      |
 |                      |-- 否 --> 是否需要保留 RAM 上下文？
 |                                     |
 |                                     |-- 是 --> Stop
 |                                     |
 |                                     |-- 否 --> Standby
```

## 7.2 场景选型

|需求|推荐模式|理由|
|---|---|---|
|RTOS 空闲几十微秒|Sleep|唤醒快，软件简单|
|UART DMA 接收期间 CPU 空闲|Sleep|外设继续工作|
|传感器每秒采样一次|Stop|RTC/LPTIM 唤醒，RAM 保持|
|无操作 10 分钟|Standby|极低静态功耗|
|需要保持协议栈连接上下文|Stop|RAM 和部分外设状态可保持|
|电子价签运输模式|Standby|允许复位恢复|
|高实时电机控制|Sleep|Stop 的时钟恢复延迟不可接受|
|NB-IoT 周期上报|Stop/Standby|取决于网络上下文保持策略|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **先做功耗预算，再选择模式。**
2. **先关闭外部负载，再优化 MCU。**
3. **所有低功耗入口必须可回滚。**
4. **睡眠前必须定义唤醒源、最大睡眠时间和超时行为。**
5. **Stop 唤醒后必须显式恢复时钟和外设。**
6. **Standby 唤醒必须按冷启动路径设计。**
7. **所有唤醒原因必须可观测和可记录。**
8. **禁止依赖未定义的寄存器保持行为。**

## 8.2 选型决策矩阵

评分范围 1~5，分数越高越优。

|指标|Sleep|Stop|Standby|
|---|---|---|---|
|最低功耗|2|4|5|
|唤醒速度|5|4|2|
|RAM 保持|5|5|1|
|外设保持|5|2|1|
|软件复杂度|5|3|2|
|长时间续航|2|4|5|

## 8.3 工业级编码规范

- 低功耗入口使用独立模块，不允许业务代码直接写 PWR 寄存器。
- 使用状态机管理：
    - `PREPARE`
    - `ENTER`
    - `WAKE`
    - `RESTORE`
    - `FAILSAFE`
- 所有外设实现统一接口：

```
typedef struct {
    bool (*prepare_sleep)(void);
    void (*resume_from_sleep)(void);
    void (*force_shutdown)(void);
} low_power_device_ops_t;
```

- 进入深睡眠前记录：
    - 当前模式；
    - 唤醒原因预期；
    - RTC 时间；
    - 软件版本；
    - 关键故障码。
- 所有唤醒路径进行超时和异常保护。
- 生产版本关闭无必要的调试低功耗保持功能。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：未关闭 SysTick

### 错误代码

```
void enter_stop(void)
{
    __WFI();
}
```

### 根因

SysTick 仍按 1 ms 产生中断，MCU 每毫秒被唤醒。

### 正确实现

```
void stop_prepare_tick(void)
{
    systick_stop();
    rtc_program_wakeup(compute_next_deadline());
}

void stop_restore_tick(void)
{
    uint32_t elapsed = rtc_get_elapsed_ticks();
    rtos_tick_compensate(elapsed);
    systick_start();
}
```

### 风险影响

- 平均电流从微安级升至毫安级；
- 睡眠时间被切碎；
- RTC 和 OS 时间漂移。

---

## 9.2 错误二：Stop 唤醒后不恢复 PLL

### 错误代码

```
void after_stop_wakeup(void)
{
    uart_init(115200);
    application_run();
}
```

### 根因

UART 初始化计算分频时仍使用旧的 `SystemCoreClock`，但实际时钟已回到 HSI/MSI。

### 正确实现

```
void after_stop_wakeup(void)
{
    if (!system_clock_restore_pll()) {
        system_enter_safe_clock();
        fault_report(FAULT_CLOCK_RESTORE);
    }

    SystemCoreClockUpdate();
    uart_reconfigure();
    timer_reconfigure();
}
```

### 风险影响

- 通信乱码；
- 定时器周期错误；
- 看门狗超时；
- 系统偶发死锁。

---

## 9.3 错误三：睡眠前没有等待 UART/DMA 完成

### 错误代码

```
uart_send_async(data, len);
enter_stop();
```

### 根因

Stop 模式关闭了 UART 或 DMA 时钟，发送数据尚未完成。

### 正确实现

```
bool uart_flush_before_sleep(uint32_t timeout_ms)
{
    uint32_t deadline = os_time_ms() + timeout_ms;

    while (!uart_tx_complete()) {
        if (time_after(os_time_ms(), deadline)) {
            uart_abort_tx();
            return false;
        }
        os_thread_sleep(1);
    }

    return true;
}
```

### 风险影响

- 数据截断；
- 总线协议帧损坏；
- 外部设备状态机卡死。

---

## 9.4 错误四：GPIO 浮空或电平冲突

### 错误代码

```
for (uint32_t pin = 0; pin < 16; ++pin) {
    gpio_set_input(GPIOA, pin);
}
```

### 根因

所有引脚被设置为普通输入，造成浮空、反灌或外部输出冲突。

### 正确实现

```
void gpio_low_power_config(void)
{
    gpio_config_analog(GPIOA, GPIOA_UNUSED_MASK);

    gpio_set_level(SENSOR_EN, 0);
    gpio_config_output(SENSOR_EN);

    gpio_config_input_pull(WAKE_PIN, GPIO_PULL_UP);

    gpio_config_input(GPIO_UART_RX);
    gpio_set_external_transceiver_shutdown(true);
}
```

### 风险影响

- 功耗增加几十至数百微安；
- 外部芯片损坏；
- 唤醒脚抖动导致唤醒风暴。

---

## 9.5 错误五：未清除旧唤醒标志

### 错误代码

```
pwr_enable_wakeup_pin();
__WFI();
```

### 根因

上一次唤醒标志仍保持有效，MCU 一进入 Standby 就立即再次唤醒。

### 正确实现

```
pwr_disable_wakeup_sources();
pwr_clear_all_wakeup_flags();
pwr_configure_wakeup_sources();
pwr_enable_wakeup_sources();

__DSB();
__WFI();
```

### 风险影响

- Standby 进入失败；
- 电流波形呈现周期性唤醒；
- 设备无法进入运输模式。

---

## 10. 多机制组合使用方案

## 10.1 架构目标

构建以下策略：

- 睡眠时间短：Sleep；
- 空闲时间中等：Stop；
- 长时间无任务：Standby；
- RTC 定时唤醒；
- GPIO 事件唤醒；
- RTOS Tick 补偿；
- 统一设备挂起和恢复；
- 支持故障降级。

## 10.2 状态机

```
RUN
 |
 |-- 无任务，预计空闲 < T1 --> SLEEP
 |
 |-- 无任务，T1 <= 空闲 < T2 --> STOP
 |
 |-- 无任务，空闲 >= T2 --> STANDBY
 |
 SLEEP/STOP 唤醒
 |
 |-- 恢复失败 --> SAFE_CLOCK / FAULT
 |
 |-- 恢复成功 --> RUN
 |
 STANDBY 唤醒
 |
 |-- 复位启动 --> BOOT --> RESTORE_CONTEXT --> RUN
```

## 10.3 统一框架

```
typedef enum {
    LP_MODE_SLEEP,
    LP_MODE_STOP,
    LP_MODE_STANDBY,
} lp_mode_t;

typedef struct {
    uint32_t expected_idle_ms;
    bool wake_by_rtc;
    bool wake_by_gpio;
    bool retain_ram;
    bool peripherals_must_run;
} lp_request_t;

static lp_mode_t lp_select_mode(const lp_request_t *req)
{
    if (req == NULL) {
        return LP_MODE_SLEEP;
    }

    if (req->peripherals_must_run || req->expected_idle_ms < 2U) {
        return LP_MODE_SLEEP;
    }

    if (req->retain_ram && req->expected_idle_ms < 1000U) {
        return LP_MODE_STOP;
    }

    if (req->retain_ram) {
        return LP_MODE_STOP;
    }

    return LP_MODE_STANDBY;
}

void low_power_service(const lp_request_t *req)
{
    lp_mode_t mode = lp_select_mode(req);

    switch (mode) {
    case LP_MODE_SLEEP:
        platform_enter_sleep();
        break;

    case LP_MODE_STOP:
        if (platform_enter_stop() != LOW_POWER_OK) {
            platform_enter_sleep();
        }
        break;

    case LP_MODE_STANDBY:
        if (!standby_save_context(application_get_state())) {
            platform_enter_stop();
        } else {
            platform_enter_standby();
        }
        break;

    default:
        platform_enter_sleep();
        break;
    }
}
```

---

## 11. 工业级实际案例分析

## 11.1 案例一：无线环境传感器

### 需求

- 每 60 秒采集温湿度；
- 每 10 分钟无线发送一次；
- 电池容量 2400 mAh；
- 目标寿命超过 1 年。

### 架构

```
RTC
 |
 |-- 每 60 秒唤醒
 |      |
 |      |-- 传感器上电
 |      |-- 采样
 |      |-- 关闭传感器
 |
 |-- 每 10 分钟唤醒
        |
        |-- 启动无线模块
        |-- 发送数据
        |-- 等待确认
        |-- 关闭无线模块
        |-- Standby
```

### 设计要点

- 采样阶段使用 Run；
- 等待阶段使用 Standby；
- 无线模块使用硬件电源开关；
- 关键状态写入 FRAM；
- RTC 使用 LSE；
- 无线失败采用指数退避，避免反复唤醒。

### 能耗估算

假设：

- 每分钟采样 50 ms，8 mA；
- 每 10 分钟通信 2 s，120 mA；
- 其余时间 Standby，1 μA。

平均通信电流：

Iradio=120mA×2s600s=0.4mAIradio​=600s120mA×2s​=0.4mA

采样平均电流：

Isensor=8mA×0.05s60s=6.67μAIsensor​=60s8mA×0.05s​=6.67μA

总平均电流约：

Iavg≈0.41mAIavg​≈0.41mA

2400 mAh 理论寿命：

Life=24000.41≈5853h≈244天Life=0.412400​≈5853h≈244天

未达到一年，必须进一步优化：

- 降低无线发射时间；
- 增大发送周期；
- 使用更低功耗无线协议；
- 降低通信峰值持续时间；
- 降低传感器采样频率；
- 采用更大容量电池。

**结论：不能只看 Standby 电流，通信能耗通常是主导项。**

---

## 11.2 案例二：工业电机控制器

### 需求

- 电机运行时要求周期控制；
- 控制周期 100 μs；
- 进入停止状态后 50 ms 内必须响应启动信号；
- 保留故障上下文。

### 方案

- 运行期间：Run；
- 电机停止但仍需快速响应：Sleep；
- 超过 1 s 无启动请求：Stop；
- 不进入 Standby，避免时钟恢复和外设重新初始化影响启动时间。

### 设计要点

- PWM、比较器、故障输入保持工作；
- 使用硬件 Break 输入实现硬件关断；
- CPU 通过 Sleep 等待中断；
- 不能将关键故障唤醒仅依赖软件轮询。

### 结论

**最低功耗不是唯一目标，故障响应和控制确定性优先。**

---

## 11.3 案例三：资产追踪终端

### 需求

- 设备长期运输；
- 每 6 小时定位一次；
- 振动或开箱立即唤醒；
- 不要求保持应用 RAM；
- 目标待机电流小于 3 μA。

### 方案

- 长时间使用 Standby；
- RTC 负责周期唤醒；
- 加速度传感器使用自身低功耗运动检测；
- 开箱信号连接唤醒引脚；
- 唤醒后完整启动系统；
- 通过备份寄存器记录唤醒源和任务原因。

### 设计要点

- 传感器必须有硬件低功耗模式；
- 关断蜂窝模块电源；
- 检查 PCB 上的 ESD、调试器、LED 漏电；
- 使用低 IQ DCDC/LDO；
- 唤醒后优先读取唤醒源，再初始化高功耗模块。

---

## 12. 高频问题深度答疑

### 问题一：Sleep 和 WFI 是同一个概念吗？

不是。

- `WFI` 是 CPU 指令；
- Sleep 是 MCU 电源/时钟控制器定义的模式；
- `WFI` 只是触发进入等待状态；
- 是否进入 Stop 或 Standby，还取决于 `SLEEPDEEP` 和 PWR 寄存器配置。

---

### 问题二：Stop 唤醒后为什么必须重新配置时钟？

因为 Stop 通常关闭 PLL、高速外部时钟和部分时钟树。唤醒后：

- CPU 可以先使用默认内部时钟运行；
- 原来的 PLL 可能未锁定；
- 外设时钟频率可能变化；
- `SystemCoreClock` 软件变量可能过期。

所以必须完成时钟恢复和外设重配置后，才能恢复正常业务。

---

### 问题三：为什么进入 Standby 后唤醒像复位？

Standby 关闭了 CPU 和主电源域。唤醒后：

- CPU 上下文不存在；
- 堆栈寄存器、通用寄存器、普通 SRAM 可能丢失；
- 启动代码重新执行；
- 应用必须通过备份域保存的状态恢复。

这不是异常，而是 Standby 的设计目标。

---

### 问题四：RTOS 中能否直接在 Idle 任务里执行 Stop？

不能简单直接执行。

必须协调：

- 下一次定时器到期时间；
- Tick 抑制；
- 中断竞态；
- 任务唤醒；
- 时间补偿；
- 锁和临界区；
- 外设挂起与恢复。

应优先使用 RTOS 提供的 tickless idle 机制，再在其底层接入 MCU Stop。

---

### 问题五：为什么数据手册写的 Stop 电流很低，实测却高很多？

常见原因：

- 调试器连接；
- GPIO 外部电平冲突；
- LDO 静态电流；
- RTC、BOR、温度传感器仍启用；
- SRAM 保持区配置过大；
- USB、CAN、RS485 收发器未关闭；
- PCB 上 LED、电阻、传感器形成耗电路径；
- 测量仪器接线或电流量程不正确。

功耗测量必须区分：

Itotal=IMCU+Iregulator+Iperipheral+IboardItotal​=IMCU​+Iregulator​+Iperipheral​+Iboard​

---

### 问题六：深睡眠模式一定优于浅睡眠模式吗？

不一定。

若睡眠时间很短，Stop/Standby 的进入和恢复能量可能超过节省的静态功耗。应基于：

Etotal=Eenter+Esleep+Ewake+EreinitEtotal​=Eenter​+Esleep​+Ewake​+Ereinit​

进行模式选择，而不是只比较静态电流。

---

## 13. 课程核心总结

### 核心要点

1. **Sleep 的主要收益来自停止 CPU 时钟。**
2. **Stop 的主要收益来自关闭高速时钟和部分电源域，同时保留 RAM。**
3. **Standby 的主要收益来自关闭主电源域，但唤醒通常是复位型。**
4. `WFI` 不是完整低功耗方案，必须配合 PWR、时钟、外设和唤醒源配置。
5. Stop 唤醒后必须恢复系统时钟和外设配置。
6. Standby 必须设计上下文保存、唤醒源识别和安全恢复。
7. SysTick、GPIO、外部器件和电源芯片经常比 MCU 内核本身更耗电。
8. 低功耗设计必须同时优化：
    - 静态电流；
    - 唤醒次数；
    - 单次唤醒能量；
    - 外部负载；
    - 软件恢复时间。

### 性能排序

按静态功耗从高到低：

```
Run > Sleep > Stop > Standby
```

按唤醒速度从快到慢：

```
Sleep > Stop > Standby
```

按软件恢复复杂度从低到高：

```
Sleep < Stop < Standby
```

### 通用选型结论

- **短时间空闲、需要快速响应：Sleep**
- **中长时间空闲、需要保留 RAM：Stop**
- **长时间无任务、允许系统重启：Standby**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|模式|
|---|---|
|CPU 等待 UART/SPI 中断|Sleep|
|RTOS Tickless Idle，空闲几毫秒|Sleep 或 Stop|
|RTC 周期采样|Stop|
|保持 RAM 中协议状态|Stop|
|运输存储|Standby|
|长时间无操作|Standby|
|电机实时控制空闲|Sleep|
|无线模块彻底关断|Stop 或 Standby|

### 14.2 特性对比表

|项目|Sleep|Stop|Standby|
|---|---|---|---|
|CPU 上下文|保持|保持|丢失|
|RAM|保持|通常保持|通常丢失|
|PLL|可运行|关闭|关闭|
|RTC|可运行|可运行|可运行|
|唤醒后路径|继续执行|恢复时钟后继续|重新启动|
|典型电流|mA 级|μA 级|亚 μA~μA 级|
|典型用途|高频空闲|周期任务|超长待机|

### 14.3 进入低功耗检查清单

```
[ ] 无高优先级任务待处理
[ ] UART/DMA 已完成或已安全暂停
[ ] SysTick 已抑制
[ ] RTC/LPTIM 唤醒已配置
[ ] GPIO 已设置为确定状态
[ ] 外部传感器/收发器已关断
[ ] 唤醒标志已清除
[ ] 关键上下文已保存
[ ] 看门狗策略已确认
[ ] 调试低功耗配置已关闭
[ ] 已执行 DSB
[ ] 唤醒后时钟恢复路径已验证
```

---

## 15. 学习效果自检

应能够回答以下问题：

- [ ]  `WFI` 与 `SLEEPDEEP` 的关系是什么？
- [ ]  Sleep、Stop、Standby 哪些状态会丢失 SRAM？
- [ ]  Stop 唤醒后为何需要重新配置 PLL？
- [ ]  如何避免进入 `WFI` 前的中断竞态？
- [ ]  如何处理 RTOS Tickless Idle 与 RTC 的时间补偿？
- [ ]  如何判断 Standby 唤醒还是冷启动？
- [ ]  如何设计备份寄存器数据的 Magic、版本和 CRC？
- [ ]  如何计算某种低功耗模式的能量交叉点？
- [ ]  为什么 GPIO 浮空会导致功耗升高？
- [ ]  为什么使用调试器测得的低功耗数据通常不可信？
- [ ]  如何设计 Sleep → Stop → Standby 多级策略？
- [ ]  如何证明低功耗模式没有引入通信丢包和时序错误？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：裸机 Sleep

要求：

- 使用定时器中断每 100 ms 唤醒；
- CPU 通过 `WFI` 等待；
- 示波器观察电流和唤醒波形；
- 测量睡眠电流和唤醒延迟。

验收指标：

- 无忙等待；
- 唤醒抖动小于 2 个 CPU 周期；
- 中断处理完成后继续执行。

### 任务二：Stop + RTC

要求：

- RTC 每 5 秒唤醒；
- 进入 Stop 前关闭 UART 和 ADC；
- 唤醒后恢复 PLL；
- 验证 UART 波特率和定时器周期。

验收指标：

- Stop 电流达到芯片数据手册典型值的 1.5 倍以内；
- 时钟恢复失败有降级路径；
- RTC 时间误差可量化。

### 任务三：RTOS Tickless Idle

要求：

- 实现空闲时间预测；
- 小于 2 ms 使用 Sleep；
- 2 ms~1 s 使用 Stop；
- 超过 1 s 使用更深模式；
- 处理 Tick 补偿。

验收指标：

- 无周期性 1 ms 唤醒；
- 任务延时误差小于设定阈值；
- 高优先级任务响应不被低功耗流程阻塞。

### 任务四：Standby 状态恢复

要求：

- 保存应用状态、版本号、CRC；
- 配置 RTC 和 GPIO 双唤醒；
- 记录唤醒原因；
- 模拟备份数据损坏并进入安全模式。

验收指标：

- 冷启动、RTC 唤醒、GPIO 唤醒可区分；
- 状态损坏时不使用无效数据；
- 设备能恢复到安全运行状态。

### 任务五：整机功耗优化

要求：

- 分别测量 MCU、传感器、通信模块和电源芯片电流；
- 建立功耗预算；
- 计算全年电池消耗；
- 优化前后对比平均功耗。

输出内容：

- 电流波形；
- 各模式持续时间；
- 平均电流公式；
- 单次唤醒能量；
- 电池寿命估算；
- 优化收益报告。

---

## 16.2 性能测试方法

### 测量项目

|项目|测量方法|
|---|---|
|睡眠电流|电流分析仪稳态采样|
|唤醒延迟|GPIO 翻转与唤醒事件之间的时间差|
|时钟恢复时间|唤醒到 PLL Lock 的时间|
|单次唤醒能量|对电流波形积分|
|伪唤醒率|长时间统计唤醒次数|
|RTC 精度|与高精度参考时钟比较|
|外部漏电|分模块断电或串联电流计|

单次能量：

E=∫t0t1V(t)I(t)dtE=∫t0​t1​​V(t)I(t)dt

若电压恒定：

E=V∫t0t1I(t)dtE=V∫t0​t1​​I(t)dt

### 必须覆盖的测试条件

- 最高和最低工作温度；
- 最低、典型、最高电源电压；
- 电池新旧状态；
- 外部 GPIO 不同电平；
- RTC、LSE、LSI 不同配置；
- 调试器连接和断开；
- 传感器与通信模块真实连接；
- 看门狗开启；
- Flash 擦写后；
- 异常复位和唤醒源同时发生。

---

## 16.3 进阶学习方向

1. **ARM Cortex-M 低功耗架构**
    
    - `WFI/WFE`
    - Event Register
    - NVIC Pending
    - Sleep-on-Exit
    - TrustZone 下的低功耗切换
2. **RTOS Tickless 和动态时钟**
    
    - FreeRTOS tickless idle；
    - Zephyr PM 子系统；
    - 时间补偿和低功耗定时器；
    - 多任务唤醒截止时间合并。
3. **电源架构协同设计**
    
    - DCDC 与 LDO 的 IQ；
    - 负载开关；
    - 电源域隔离；
    - 传感器和无线芯片的硬件关断。
4. **低功耗通信协议**
    
    - BLE Advertising；
    - Zigbee Sleepy End Device；
    - LoRaWAN Class A；
    - NB-IoT/eDRX/PSM；
    - Wi-Fi DTIM 与唤醒窗口。
5. **工业级功耗验证**
    
    - 自动化功耗测试；
    - 低功耗回归测试；
    - 电流波形异常检测；
    - 长时间唤醒统计；
    - 产线功耗校准与分档。

**最终工程结论：低功耗不是调用一个 `Sleep()` API，而是从时钟树、电源域、外设、GPIO、RTOS 时间基、唤醒源、状态保存到整机电源架构的系统工程。**