

> 本课聚焦 **RTC 唤醒源**，包括 RTC Wakeup Timer、Alarm、周期唤醒、绝对时间唤醒、Stop/Standby 协同、LSE/LSI 时钟、校准、唤醒标志、备份域、时间补偿和故障恢复。示例采用 Cortex-M + STM32 风格伪 HAL/寄存器接口，具体寄存器位、计数器宽度、唤醒行为和低功耗模式能力必须以目标 MCU Reference Manual、Datasheet 和 Errata 为准。

## 1. 学习目标

### 理解

- 理解 RTC 的硬件组成：时钟源、预分频器、日历计数器、Alarm、Wakeup Timer、Tamper、备份域和唤醒逻辑。
- 理解 RTC 唤醒链路：

```
LSE/LSI/外部低速时钟
        ↓
RTC 预分频器/日历/唤醒计数器
        ↓
Alarm/Wakeup Timer 标志
        ↓
EXTI RTC 唤醒线路
        ↓
PWR 唤醒逻辑
        ↓
CPU 唤醒或系统复位
```

- 区分 **相对时间唤醒** 与 **绝对时间唤醒**。
- 理解 RTC Alarm、RTC Wakeup Timer、LPTIM 和 SysTick 的边界。
- 理解 RTC 时钟误差、温漂、写保护、同步延迟和唤醒标志残留。

### 掌握

- 配置 RTC 低功耗时钟源和预分频器。
- 配置周期唤醒、一次性 Alarm 和固定时刻唤醒。
- 正确执行 RTC、EXTI、PWR、NVIC 多层标志处理。
- 实现 Stop/Standby 下的 RTC 唤醒。
- 使用 RTC 时间完成超时、周期调度、掉电恢复和日志时间戳。

### 精通

- 分析 RTC 异步/同步预分频器、日历进位、Alarm 掩码和 Wakeup Timer 计数行为。
- 量化 LSE/LSI 误差、唤醒延迟、周期累计漂移和校准收益。
- 设计基于绝对时间的周期任务，避免相对延时累积漂移。
- 处理 RTC 写入期间的并发、备份域复位、低功耗唤醒复位和时间回拨。

### 能够设计

- 工业级 RTC 驱动和时间服务；
- 支持周期、绝对时间、多个 Alarm 和多源唤醒的调度器；
- RTC + Stop/Standby + 备份上下文的低功耗架构；
- 具有校准、故障检测、时间可信度和自动回退能力的 RTC 子系统。

## 2. 前置要求

### 知识要求

- Cortex-M 异常、NVIC、`WFI/WFE`、Stop、Standby 和复位流程；
- RCC 时钟树、LSE、LSI、备份域和电源域；
- RTC、EXTI、PWR、LPTIM 和看门狗；
- 时间戳、周期调度、Tickless 和时间补偿；
- 晶振误差、ppm、温漂和基础校准方法；
- FRAM、Backup SRAM、Flash 和 CRC。

### 技能要求

- 能阅读 MCU RTC、PWR、RCC、EXTI 章节；
- 能使用示波器和功耗分析仪验证 RTC 唤醒；
- 能处理 RTC 写保护、同步标志和 Alarm 标志；
- 能实现时间转换、闹钟计算和掉电恢复；
- 能定位 RTC 不唤醒、周期偏移和立即重复唤醒。

## 3. 技术概述

## 3.1 RTC 的系统定位

RTC 主要解决三类问题：

1. **长期绝对时间保持**：年月日时分秒；
2. **低功耗周期调度**：每秒、每分钟、每小时唤醒；
3. **固定时间事件**：每天 08:00、每周一、某个时间戳触发。

RTC 通常位于备份域：

```
VDD 主电源关闭
    ↓
VBAT/备份电源继续供电
    ↓
LSE + RTC + Backup Register 继续运行
```

因此，RTC 可以在 MCU 主系统断电或 Standby 复位后继续保持时间。

## 3.2 RTC 唤醒机制分类

### RTC Wakeup Timer

适合：

- 相对时间延时；
- 周期性采样；
- Stop 模式定时唤醒；
- 不需要日历匹配的任务。

### RTC Alarm

适合：

- 固定时刻唤醒；
- 基于年月日时分秒的绝对时间；
- 每天固定时间执行任务；
- 多种 Alarm 掩码匹配。

### RTC Tamper

适合：

- 检测备份电池、外壳和线路篡改；
- 触发安全记录或系统唤醒；
- 不能替代普通定时唤醒。

## 3.3 RTC、LPTIM 与 SysTick 对比

|特性|RTC|LPTIM|SysTick|
|---|---|---|---|
|Stop 中运行|通常支持|通常支持|通常不支持|
|Standby 中保持|通常支持|依芯片而定|不支持|
|绝对时间|强|弱|弱|
|周期定时|强|强|强|
|外部计数|通常弱|强|不支持|
|分辨率|1 Hz~子秒|由时钟源决定|高|
|长周期|强|受计数器宽度限制|软件扩展|
|低功耗|极低|低|较高|
|时间校准|支持|通常较弱|不适合长期保持|

## 4. 核心特性横向对比

### 4.1 RTC 时钟源

|时钟源|典型频率|精度|温漂|功耗|推荐场景|
|---|---|---|---|---|---|
|LSE 晶振|32.768 kHz|高|低~中|极低|工业产品、长期计时|
|LSI|约 32~100 kHz|低|高|低|成本敏感、精度要求低|
|外部 1 Hz|1 Hz|取决于源|取决于源|低~中|高精度同步系统|
|外部低频时钟|依系统|取决于源|取决于源|依系统|专用时基和同步系统|

### 4.2 RTC 唤醒机制对比

|机制|典型用途|精度|长周期能力|配置复杂度|主要风险|
|---|---|---|---|---|---|
|Wakeup Timer|相对周期|中~高|中|中|计数范围、溢出|
|Alarm A/B|绝对时间|高|高|高|掩码错误、标志残留|
|秒中断|1 秒节拍|高|软件扩展|低|唤醒次数过多|
|日历匹配|固定时间|高|高|高|闰年、月份和时间回拨|
|Tamper|安全事件|不适用|不适用|中|误触发和数据清除|

### 4.3 RTC 唤醒与低功耗模式

|模式|RTC 保持|CPU 上下文|唤醒后流程|典型功耗|
|---|---|---|---|---|
|Sleep|是|保持|ISR/任务继续|高|
|Stop|是|通常保持|恢复系统时钟|中~低|
|Standby|是|丢失|复位启动流程|极低|
|Shutdown|依芯片而定|丢失|接近冷启动|最低|

## 5. 底层原理与功能特性深度解析

## 5.1 RTC 预分频器

RTC 通常使用两级预分频器：

```
RTCCLK
   ↓
异步预分频器 PREDIV_A
   ↓
同步预分频器 PREDIV_S
   ↓
1 Hz 日历时基
```

常见关系：

fck_apre=fRTCCLKPREDIVA+1fck_apre​=PREDIVA​+1fRTCCLK​​fck_spre=fck_aprePREDIVS+1fck_spre​=PREDIVS​+1fck_apre​​

若使用 32.768 kHz LSE，目标为 1 Hz，可以配置为：

32768=(127+1)×(255+1)32768=(127+1)×(255+1)

即：

```
PREDIV_A = 127
PREDIV_S = 255
```

具体 RTC Wakeup Timer 可能直接使用：

- 1 Hz；
- 1/2 Hz；
- 1/4 Hz；
- 1/8 Hz；
- ck_spre；
- ck_apre；
- 其他专用分频路径。

必须根据手册确认 Wakeup Timer 输入时钟，而不能假设始终为 1 Hz。

## 5.2 RTC 初始化

```
typedef enum {
    RTC_CLOCK_LSE,
    RTC_CLOCK_LSI,
    RTC_CLOCK_EXTERNAL,
} rtc_clock_source_t;

typedef struct {
    rtc_clock_source_t source;
    uint32_t source_hz;
    uint32_t async_prescaler;
    uint32_t sync_prescaler;
    bool enable_backup_domain;
} rtc_init_config_t;

bool rtc_init(const rtc_init_config_t *cfg)
{
    if (cfg == NULL || cfg->source_hz == 0U) {
        return false;
    }

    if (!rcc_enable_rtc_clock_source(cfg->source)) {
        return false;
    }

    if (!rcc_wait_rtc_clock_ready(500U)) {
        return false;
    }

    if (cfg->enable_backup_domain &&
        !pwr_enable_backup_domain_write()) {
        return false;
    }

    if (!rcc_select_rtc_clock(cfg->source)) {
        return false;
    }

    rtc_disable_write_protection();
    rtc_enter_init_mode();

    if (!rtc_wait_init_ready(100U)) {
        rtc_exit_init_mode();
        rtc_enable_write_protection();
        return false;
    }

    rtc_set_async_prescaler(cfg->async_prescaler);
    rtc_set_sync_prescaler(cfg->sync_prescaler);
    rtc_exit_init_mode();
    rtc_enable_write_protection();

    return rtc_clock_is_valid();
}
```

### 初始化关键点

- 备份域写保护必须正确处理；
- 切换 RTC 时钟源可能复位 RTC 配置；
- 重新配置 RTC 前必须确认是否需要备份数据迁移；
- LSE/LSI Ready 不能只等待固定延时，应检查硬件状态；
- 初始化后应写入 Magic 标志，避免每次启动都重置时间。

## 5.3 RTC Wakeup Timer 配置

```
typedef struct {
    uint32_t timeout_s;
    bool periodic;
    bool enable_interrupt;
    bool enable_pwr_wakeup;
} rtc_wakeup_config_t;

bool rtc_wakeup_arm(const rtc_wakeup_config_t *cfg)
{
    if (cfg == NULL || cfg->timeout_s == 0U) {
        return false;
    }

    rtc_disable_wakeup_timer();
    rtc_clear_wakeup_timer_flag();
    exti_clear_pending(RTC_WAKE_LINE);
    nvic_clear_pending(RTC_IRQn);
    pwr_clear_rtc_wakeup_flag();

    if (!rtc_wakeup_counter_supports(cfg->timeout_s)) {
        return false;
    }

    /*
     * 是否配置 timeout_s - 1，必须依据硬件计数语义。
     */
    if (!rtc_set_wakeup_counter(
            rtc_seconds_to_wakeup_counter(cfg->timeout_s))) {
        return false;
    }

    if (!rtc_wait_wakeup_write_sync(100U)) {
        return false;
    }

    rtc_set_wakeup_mode(cfg->periodic
                            ? RTC_WAKEUP_PERIODIC
                            : RTC_WAKEUP_ONE_SHOT);

    if (cfg->enable_interrupt) {
        rtc_enable_wakeup_interrupt();
        nvic_enable_irq(RTC_IRQn);
    }

    if (cfg->enable_pwr_wakeup) {
        pwr_enable_rtc_wakeup();
    }

    rtc_clear_wakeup_timer_flag();
    exti_clear_pending(RTC_WAKE_LINE);
    rtc_enable_wakeup_timer();

    return true;
}
```

## 5.4 RTC Alarm 配置

RTC Alarm 通常将当前日历值与 Alarm 寄存器进行比较，并通过掩码决定匹配字段。

```
typedef struct {
    uint16_t year;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
    uint32_t mask;
} rtc_alarm_time_t;

bool rtc_alarm_arm(const rtc_alarm_time_t *alarm)
{
    if (alarm == NULL ||
        alarm->month < 1U || alarm->month > 12U ||
        alarm->day < 1U || alarm->day > 31U ||
        alarm->hour > 23U ||
        alarm->minute > 59U ||
        alarm->second > 59U) {
        return false;
    }

    rtc_disable_alarm();
    rtc_clear_alarm_flag();
    exti_clear_pending(RTC_ALARM_LINE);
    nvic_clear_pending(RTC_IRQn);

    if (!rtc_alarm_set_time(alarm)) {
        return false;
    }

    rtc_alarm_set_mask(alarm->mask);
    rtc_enable_alarm_interrupt();
    pwr_enable_rtc_alarm_wakeup();

    rtc_clear_alarm_flag();
    exti_clear_pending(RTC_ALARM_LINE);
    rtc_enable_alarm();

    return true;
}
```

### Alarm 掩码风险

例如：

```
仅匹配小时和分钟 → 每天同一时间触发
匹配分钟和秒 → 每小时重复触发
仅匹配秒 → 每分钟触发
```

不同 MCU 的掩码定义可能是“屏蔽字段”或“参与匹配字段”，必须严格核对手册。

## 5.5 绝对时间调度

周期任务不应简单执行：

```
next_alarm = current_time + period;
```

然后用实际唤醒后的当前时间继续累加，因为每次处理耗时会累积漂移。

推荐使用绝对时间：

```
typedef struct {
    uint64_t next_deadline_s;
    uint32_t period_s;
} rtc_schedule_t;

bool rtc_schedule_next(rtc_schedule_t *schedule,
                       uint64_t now_s)
{
    if (schedule == NULL || schedule->period_s == 0U) {
        return false;
    }

    if (schedule->next_deadline_s <= now_s) {
        uint64_t missed =
            (now_s - schedule->next_deadline_s) /
            schedule->period_s + 1ULL;

        schedule->next_deadline_s +=
            missed * schedule->period_s;
    } else {
        schedule->next_deadline_s += schedule->period_s;
    }

    return true;
}
```

这可以避免：

```
计划时间：10, 20, 30, 40 s
实际处理：10.2, 20.4, 30.6, 40.8 s
```

变成：

```
计划时间：10, 20, 30, 40 s
实际处理延迟不再累加到下一次调度基准
```

## 5.6 RTC 中断处理

```
void RTC_IRQHandler(void)
{
    uint32_t status = rtc_get_status();

    if ((status & RTC_FLAG_WAKEUP) != 0U) {
        rtc_clear_wakeup_timer_flag();
        wake_event_post_isr(WAKE_SRC_RTC_WAKEUP,
                            0U,
                            rtc_get_timestamp());
    }

    if ((status & RTC_FLAG_ALARM_A) != 0U) {
        rtc_clear_alarm_flag();
        wake_event_post_isr(WAKE_SRC_RTC_ALARM_A,
                            0U,
                            rtc_get_timestamp());
    }

    if ((status & RTC_FLAG_ALARM_B) != 0U) {
        rtc_clear_alarm_b_flag();
        wake_event_post_isr(WAKE_SRC_RTC_ALARM_B,
                            0U,
                            rtc_get_timestamp());
    }

    if ((status & RTC_FLAG_TAMPER) != 0U) {
        rtc_clear_tamper_flag();
        security_event_post_isr(SECURITY_EVENT_RTC_TAMPER);
    }
}
```

注意：

- 某些芯片要求通过写 0 清标志，不能使用普通读改写；
- 清除 RTC 原始标志后还要清 EXTI Pending；
- Alarm A/B 可能共享同一个 IRQ，需要分别判断；
- Standby 唤醒可能不进入 RTC ISR，而是走 Reset_Handler。

## 5.7 Standby 唤醒与复位原因

Standby 后 CPU 上下文丢失，启动代码必须先读取唤醒原因：

```
typedef enum {
    BOOT_COLD_RESET,
    BOOT_RTC_WAKEUP,
    BOOT_GPIO_WAKEUP,
    BOOT_WATCHDOG_RESET,
    BOOT_BROWNOUT_RESET,
    BOOT_UNKNOWN,
} boot_reason_t;

boot_reason_t boot_reason_detect(void)
{
    uint32_t reset_flags = rcc_get_reset_flags();
    uint32_t pwr_flags = pwr_get_wakeup_flags();
    uint32_t rtc_flags = rtc_get_wakeup_flags();

    boot_reason_t reason = BOOT_UNKNOWN;

    if ((reset_flags & RESET_FLAG_IWDG) != 0U) {
        reason = BOOT_WATCHDOG_RESET;
    } else if ((pwr_flags & PWR_FLAG_RTC_WAKEUP) != 0U ||
               (rtc_flags & RTC_FLAG_ALARM_A) != 0U ||
               (rtc_flags & RTC_FLAG_WAKEUP) != 0U) {
        reason = BOOT_RTC_WAKEUP;
    } else if ((pwr_flags & PWR_FLAG_GPIO_WAKEUP) != 0U) {
        reason = BOOT_GPIO_WAKEUP;
    } else if ((reset_flags & RESET_FLAG_BOR) != 0U) {
        reason = BOOT_BROWNOUT_RESET;
    } else {
        reason = BOOT_COLD_RESET;
    }

    return reason;
}
```

**必须先读取再清除。** 否则启动早期清除标志会导致无法判断真实唤醒原因。

## 5.8 RTC 校准

晶振误差为 ppmppm 时，时间误差近似为：

Δt=t×ppm×10−6Δt=t×ppm×10−6

若晶振误差为 20 ppm，运行 24 小时：

Δt=86400×20×10−6=1.728sΔt=86400×20×10−6=1.728s

常见校准方式：

1. 生产测试时写入校准值；
2. 与 GPS、网络时间或高精度外部时钟比较；
3. RTC 数字校准；
4. 周期性校准；
5. 运行时根据温度补偿。

```
typedef struct {
    int32_t correction_ppm;
    int32_t temperature_c;
    uint32_t sequence;
    uint32_t crc;
} rtc_calibration_t;

bool rtc_apply_calibration(
    const rtc_calibration_t *cal)
{
    if (cal == NULL ||
        cal->correction_ppm < -500 ||
        cal->correction_ppm > 500) {
        return false;
    }

    if (cal->crc != crc32(cal,
                           offsetof(rtc_calibration_t, crc))) {
        return false;
    }

    return rtc_set_digital_calibration(
        cal->correction_ppm);
}
```

具体数字校准单位、正负号含义和最大修正范围必须以芯片手册为准。

## 6. 性能量化分析

## 6.1 示例测试平台

- MCU：Cortex-M4；
- RTC 时钟：32.768 kHz LSE；
- RTC 日历：1 Hz；
- 低功耗模式：Stop/Standby；
- 温度：25 ℃；
- 仪器：200 MHz 示波器、功耗分析仪和参考频率计。

|项目|示例值|
|---|---|
|LSE 周期|30.5176 μs|
|RTC 1 Hz 日历误差|由晶振 ppm 主导|
|Stop RTC 唤醒到 ISR|10~80 μs|
|Standby 唤醒到 Reset_Handler|0.5~5 ms|
|RTC Alarm 配置时间|20~100 μs|
|RTC Wakeup Timer 配置时间|15~60 μs|
|RTC 备份域附加电流|约 0.5~2 μA|
|20 ppm 晶振一天误差|1.728 s|

上述数据仅为测试示例，不代表通用器件规格。

## 6.2 RTC 唤醒误差模型

总唤醒时间误差可表示为：

ΔTtotal=ΔTclock+ΔTquantization+ΔTsync+ΔTwake+ΔTsoftwareΔTtotal​=ΔTclock​+ΔTquantization​+ΔTsync​+ΔTwake​+ΔTsoftware​

其中：

- ΔTclockΔTclock​：LSE/LSI 频率误差；
- ΔTquantizationΔTquantization​：计数分辨率造成的量化误差；
- ΔTsyncΔTsync​：寄存器跨时钟域同步；
- ΔTwakeΔTwake​：电源和时钟恢复时间；
- ΔTsoftwareΔTsoftware​：ISR、任务调度和业务处理延迟。

## 6.3 周期唤醒漂移

错误方式：

```
每次唤醒后，使用“当前时间 + 周期”配置下一次 Alarm
```

若每次业务处理耗时 TprocessTprocess​，经过 NN 次后累计漂移近似为：

ΔTdrift=N×TprocessΔTdrift​=N×Tprocess​

绝对时间方式只会产生当前事件处理延迟，不会把处理延迟累加到下一次计划时间。

## 6.4 RTC 唤醒功耗

单次周期能量：

Ecycle=Ertc+Ewake+Eactive+EexternalEcycle​=Ertc​+Ewake​+Eactive​+Eexternal​

平均功率：

Pavg=EcycleTperiodPavg​=Tperiod​Ecycle​​

假设：

- RTC 备份域电流：1 μA；
- Stop 电流：8 μA；
- 活动电流：8 mA，持续 20 ms；
- 周期：10 s。

则：

Iavg≈8μA×9.9810+8mA×0.0210Iavg​≈8μA×109.98​+8mA×100.02​Iavg≈23.9μAIavg​≈23.9μA

如果外部传感器启动需要 5 mA、持续 100 ms，则：

Isensor=5mA×0.110=50μAIsensor​=5mA×100.1​=50μA

此时传感器活动能耗已经大于 MCU Stop 电流，优化重点应转向外部电源域。

## 6.5 主要瓶颈与优化

|瓶颈|表现|优化手段|
|---|---|---|
|LSI 漂移|周期和时间误差大|LSE、校准、网络对时|
|RTC 频繁唤醒|平均功耗高|批量任务、减少唤醒次数|
|Alarm 配置错误|不触发或连续触发|明确掩码和标志清理|
|备份域漏电|Standby 电流异常|检查 VBAT、GPIO、外部器件|
|时间回拨|周期任务重复或跳过|版本化时间策略|
|唤醒后恢复慢|任务截止时间不满足|Stop 替代 Standby或提前启动时钟|
|计数范围不足|长周期配置失败|软件扩展、Alarm 或分段唤醒|

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否需要绝对时间？
├─ 是
│  ├─ 固定时刻事件 → RTC Alarm
│  ├─ 日历/星期/月度事件 → RTC Alarm + 日历计算
│  └─ 长期时间保持 → RTC + VBAT/备份域
└─ 否
   ├─ 相对周期小于 Wakeup Timer 范围？
   │  ├─ 是 → RTC Wakeup Timer
   │  └─ 否 → 分段唤醒、Alarm 或 RTC 软件扩展
   ├─ 需要 CPU 保持上下文？
   │  ├─ 是 → Stop + RTC
   │  └─ 否 → Standby + RTC
   ├─ 需要更高分辨率？
   │  ├─ 是 → LPTIM/通用 TIM
   │  └─ 否 → RTC
   └─ 需要外部脉冲计数？
      ├─ 是 → LPTIM
      └─ 否 → RTC
```

### 7.2 典型场景

|需求|推荐方案|理由|
|---|---|---|
|每 10 秒采样|RTC Wakeup Timer|相对周期、低功耗|
|每天 08:00 上报|RTC Alarm|绝对时间匹配|
|每周维护任务|RTC Alarm + 日历|支持星期和日期|
|运输状态保持数月|RTC + Standby|备份域继续运行|
|每毫秒超时|LPTIM/通用 TIM|RTC 分辨率不足|
|低功耗 RTOS Tickless|LPTIM + RTC 校准|LPTIM 做短周期、RTC 做长期基准|
|掉电后记录时间|RTC + VBAT|备份域保持日历|
|防拆检测|RTC Tamper|事件记录和安全处理|

## 8. 工程最佳实践

## 8.1 设计原则

1. **优先使用 LSE 作为工业级 RTC 时钟源。**
2. 初始化时检查 RTC Magic，避免每次启动重置日历。
3. 相对周期任务使用 Wakeup Timer，绝对时间任务使用 Alarm。
4. 周期调度使用绝对时间，避免处理耗时累计漂移。
5. 清除 RTC、EXTI、NVIC、PWR 标志必须符合目标芯片顺序。
6. Standby 唤醒必须在启动早期读取复位和唤醒原因。
7. 任何 RTC 时间修改都必须定义回拨、跳跃和任务重排策略。
8. RTC 写入期间禁止无保护的并发访问。
9. RTC 校准必须记录版本、序号、温度和校准来源。
10. 低功耗失败应回退到 Stop 或 Sleep，并记录故障。

## 8.2 选型决策矩阵

|指标|RTC Wakeup Timer|RTC Alarm|LPTIM|SysTick|
|---|---|---|---|---|
|绝对时间能力|2|5|1|1|
|相对周期能力|5|4|5|4|
|超长周期|3|5|2~3|2|
|Stop 保持|5|5|5|1|
|Standby 保持|4~5|4~5|依芯片|1|
|分辨率|3|3|4~5|5|
|配置复杂度|3|4~5|3~4|2|
|长期精度|4|4|3~4|2|

## 8.3 工业级接口

```
typedef struct {
    bool (*init)(const rtc_init_config_t *cfg);
    bool (*get_datetime)(rtc_datetime_t *dt);
    bool (*set_datetime)(const rtc_datetime_t *dt);
    bool (*arm_wakeup)(uint64_t timeout_s);
    bool (*arm_alarm)(const rtc_alarm_time_t *alarm);
    bool (*cancel_alarm)(void);
    uint32_t (*get_flags)(void);
    void (*clear_flags)(uint32_t flags);
    bool (*apply_calibration)(const rtc_calibration_t *cal);
    bool (*is_time_valid)(void);
} rtc_ops_t;
```

时间服务应提供：

- 当前 Unix 时间；
- 单调时间；
- 日历时间；
- 时间可信度；
- 最近一次校准时间；
- RTC 复位次数；
- 时间回拨计数；
- Alarm/Wakeup 配置状态。

## 9. 常见错误与避坑指南

### 9.1 错误一：每次启动都重新初始化 RTC 时间

**错误代码：**

```
void rtc_init(void)
{
    rtc_enable();
    rtc_set_datetime(&default_time);
}
```

**根因：** 未检查备份域中是否已有有效 RTC 配置。

**正确实现：**

```
if (backup_read_magic() != RTC_VALID_MAGIC ||
    !rtc_calendar_valid()) {
    rtc_set_datetime(&factory_default_time);
    backup_write_magic(RTC_VALID_MAGIC);
}
```

**风险影响：**

- 掉电后时间被重置；
- 周期任务错过；
- 日志时间戳不可信；
- 设备无法进行长期数据对齐。

### 9.2 错误二：只清 RTC Alarm 标志

**错误代码：**

```
rtc_clear_alarm_flag();
enter_stop();
```

**根因：** EXTI Pending 或 PWR Wakeup Flag 仍然有效。

**正确实现：**

```
rtc_disable_alarm();
rtc_clear_alarm_flag();
exti_clear_pending(RTC_ALARM_LINE);
nvic_clear_pending(RTC_IRQn);
pwr_clear_rtc_wakeup_flag();
rtc_program_next_alarm();
rtc_enable_alarm();
```

**风险影响：**

- 进入低功耗后立即唤醒；
- 唤醒风暴；
- 平均功耗远高于预期。

### 9.3 错误三：Alarm 掩码配置错误

**错误代码：**

```
alarm.mask = RTC_MASK_DAY | RTC_MASK_HOUR;
rtc_alarm_arm(&alarm);
```

**根因：** 对掩码语义理解错误，实际匹配条件与预期不同。

**正确实现：**

- 明确“屏蔽字段”还是“参与比较字段”；
- 对每天、每小时、每周事件分别做实测；
- 用时间仿真覆盖闰年、月底、跨日和跨年。

**风险影响：**

- Alarm 不触发；
- 每分钟或每小时重复触发；
- 固定时间任务错时执行。

### 9.4 错误四：使用 LSI 却按 LSE 精度设计

**错误代码：**

```
rtc_select_clock(LSI);
schedule_daily_job(08, 00, 00);
```

**根因：** LSI 频率误差和温漂可能远大于 LSE，长期时间会显著漂移。

**正确实现：**

- 使用 LSE；
- 或测量 LSI 实际频率；
- 或定期使用外部参考校准；
- 在需求中明确允许的时间误差。

**风险影响：**

- 数天后固定时间任务产生明显偏移；
- 多设备时间逐渐失步；
- 计量和日志关联错误。

### 9.5 错误五：用相对时间不断重装载造成累计漂移

**错误代码：**

```
void periodic_task(void)
{
    do_work();
    rtc_wakeup_arm(PERIOD_S);
}
```

**根因：** `do_work()` 的执行时间被加入下一周期。

**正确实现：**

```
static uint64_t next_deadline_s;

void periodic_task(void)
{
    uint64_t now = rtc_get_unix_seconds();

    do_work();

    while (next_deadline_s <= now) {
        next_deadline_s += PERIOD_S;
    }

    rtc_alarm_arm_unix(next_deadline_s);
}
```

**风险影响：**

- 任务时间逐渐漂移；
- 多设备周期无法长期对齐；
- 通信窗口和采样窗口错位。

### 9.6 错误六：Standby 唤醒后过早清除标志

**错误代码：**

```
int main(void)
{
    pwr_clear_wakeup_flags();
    rcc_clear_reset_flags();

    boot_reason_t reason = boot_reason_detect();
}
```

**根因：** 在读取原因之前清除了关键寄存器。

**正确实现：**

```
boot_snapshot_t snapshot = boot_snapshot_read_all();

pwr_clear_wakeup_flags();
rcc_clear_reset_flags();
rtc_clear_wakeup_flags();

boot_reason_t reason = boot_reason_decode(&snapshot);
```

**风险影响：**

- 无法区分冷启动、RTC 唤醒、看门狗和欠压复位；
- 错误恢复策略失效；
- 低功耗故障无法诊断。

## 10. 多机制组合使用方案

## 10.1 RTC 时间服务架构

```
RTC Time Service
├── Clock Source Manager
│   ├── LSE
│   ├── LSI
│   └── External Reference
├── Calendar Manager
├── Alarm Scheduler
├── Wakeup Timer
├── Calibration Manager
├── Backup Domain Manager
├── Power/Wakeup Manager
├── Monotonic Time Layer
└── Diagnostics
    ├── Time Validity
    ├── Drift
    ├── Reset Cause
    └── Wakeup Statistics
```

## 10.2 RTC + Stop 周期唤醒框架

```
bool rtc_stop_until(uint64_t deadline_s)
{
    uint64_t now_s = rtc_get_unix_seconds();

    if (deadline_s <= now_s) {
        return false;
    }

    uint64_t delta_s = deadline_s - now_s;

    if (delta_s < LOW_POWER_CROSSOVER_S) {
        platform_enter_sleep();
        return true;
    }

    rtc_disable_wakeup_timer();
    rtc_clear_all_wakeup_flags();
    exti_clear_pending(RTC_WAKE_LINE);
    nvic_clear_pending(RTC_IRQn);

    if (!rtc_wakeup_arm_seconds(delta_s)) {
        platform_enter_sleep();
        return false;
    }

    __disable_irq();

    if (scheduler_has_pending_work()) {
        __enable_irq();
        rtc_wakeup_cancel();
        return false;
    }

    __DSB();
    __WFI();
    __ISB();

    __enable_irq();
    return true;
}
```

进入低功耗前的“检查空闲—配置 RTC—执行 WFI”必须在受保护的临界区内完成，避免事件竞态。

## 10.3 RTC + LPTIM 协同

```
RTC：长期绝对时间、日历、每天/每周任务
LPTIM：短周期超时、Stop 中高分辨率调度
GPIO：外部事件唤醒
IWDG：故障复位
        ↓
统一唤醒管理器
        ↓
读取所有来源
        ↓
生成唤醒原因位图
        ↓
按优先级执行任务
```

典型策略：

```
小于 10 ms 的超时 → LPTIM/通用 TIM
10 ms~数秒周期 → LPTIM
数秒以上且需要低功耗 → RTC Wakeup Timer
固定时间事件 → RTC Alarm
长期绝对时间 → RTC Calendar
```

## 10.4 备份上下文与 RTC

```
typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t length;
    uint64_t next_deadline_s;
    uint32_t sequence;
    uint32_t crc;
} backup_context_t;

bool backup_context_save(const backup_context_t *ctx)
{
    if (ctx == NULL ||
        ctx->length != sizeof(*ctx)) {
        return false;
    }

    backup_context_t copy = *ctx;
    copy.crc = crc32(&copy,
                     offsetof(backup_context_t, crc));

    return backup_write_dual_slot(&copy);
}

bool backup_context_load(backup_context_t *ctx)
{
    if (ctx == NULL) {
        return false;
    }

    if (!backup_read_latest_valid(ctx)) {
        return false;
    }

    return ctx->magic == BACKUP_CONTEXT_MAGIC &&
           ctx->version == BACKUP_CONTEXT_VERSION &&
           ctx->crc == crc32(ctx,
                             offsetof(backup_context_t, crc));
}
```

关键任务的下一次 Alarm 时间、周期序号和任务状态应保存到可靠备份介质，防止 Standby 唤醒后调度状态丢失。

## 11. 工业级实际案例分析

## 11.1 案例一：电池环境传感器

### 需求

- 每 5 分钟采样；
- 每小时汇总并上传；
- 设备大部分时间处于 Stop；
- 电池寿命超过一年；
- 采样时间戳误差小于每日 2 秒。

### 架构

```
RTC LSE
    ↓
RTC Wakeup Timer/Alarm
    ↓
Stop 唤醒
    ↓
打开传感器电源
    ↓
采样、校验、保存
    ↓
每小时启动通信模块
    ↓
上传数据
    ↓
重新计算绝对下一次截止时间
    ↓
Stop
```

### 设计要点

- LSE 20 ppm 时，理论一天误差约 1.728 秒，满足需求；
- 使用绝对 Unix 时间调度，不能使用“唤醒结束时间 + 300 秒”；
- 传感器 Ready 信号优先于固定延时；
- 上传失败使用有限重试和退避；
- 采样和上传分开测量单次能量；
- RTC 每天与网络时间校准一次。

## 11.2 案例二：工业控制器每天定时维护

### 需求

- 每天 02:00 进入维护窗口；
- 正常情况下 MCU 处于 Standby；
- 外部开门信号也能唤醒；
- RTC 时间被修改后不能重复执行维护任务。

### 架构

```
RTC Alarm 02:00 ─┐
开门 GPIO ───────┼→ Standby 唤醒
IWDG 复位 ───────┘
                    ↓
             启动早期读取原因
                    ↓
             判断维护窗口是否已执行
                    ↓
             执行维护/开门处理
                    ↓
             保存执行序号和时间
```

### 设计要点

- 使用日期 + 维护序号避免同一天重复执行；
- RTC 回拨时不直接重新触发已经完成的维护任务；
- 看门狗复位不得被误判为 RTC 唤醒；
- 启动阶段先捕获原始标志，再清除硬件状态；
- 维护任务执行结果保存到双槽位备份存储。

## 11.3 案例三：低功耗资产追踪器

### 需求

- 每 6 小时定位一次；
- 每天固定时间上传汇总；
- 振动或开箱立即唤醒；
- 电池电压过低时降低上传频率。

### 架构

```
RTC Alarm：6 小时定位
RTC Alarm：每天上传
GPIO：振动/开箱
ADC：电池欠压监测
IWDG：故障恢复
        ↓
统一唤醒原因收集
        ↓
按优先级处理安全事件、定位、上传
        ↓
根据电池状态选择下一次 Alarm
```

### 设计要点

- RTC 只保持时间和调度，不直接决定业务安全策略；
- 欠压时修改下一次计划，但保留绝对日期基准；
- 开箱事件优先于普通定位任务；
- 多个 Alarm 同时到达时保存完整位图；
- 记录 RTC 时间有效性和最近校准来源。

## 12. 高频问题深度答疑

### 问题一：RTC Wakeup Timer 和 RTC Alarm 如何选择？

需要相对周期时使用 Wakeup Timer；需要固定日期、时间或星期时使用 Alarm。若一个周期任务必须长期保持相位，应采用绝对 Alarm 或基于 RTC 绝对时间重算 Wakeup Timer。

### 问题二：为什么 RTC 唤醒后时间会偏几秒？

主要原因是晶振 ppm 误差。20 ppm 晶振每天约产生 1.728 秒误差。除此之外还有温度漂移、同步延迟、唤醒恢复延迟和校准误差。应测量长期偏差并使用校准或网络对时。

### 问题三：为什么 RTC Alarm 一配置就立即唤醒？

常见原因：

- Alarm 时间已经过去；
- Alarm 标志未清；
- EXTI Pending 未清；
- PWR Wakeup Flag 未清；
- 掩码配置导致当前时间已经匹配；
- 设置日期/时间过程中产生了匹配事件。

应采用禁用、清标志、配置、再次清标志、使能的完整时序。

### 问题四：RTC 时间修改后，如何处理已安排的任务？

必须定义策略。推荐：

1. 保存修改前后的时间；
2. 取消全部旧 Alarm；
3. 根据新时间重新计算下一次绝对截止时间；
4. 对已经执行的任务使用序号去重；
5. 对时间回拨设置事件标志，避免重复执行不可重复业务。

### 问题五：Standby 中 RTC 运行，为什么唤醒后没有进入 RTC ISR？

Standby 唤醒常表现为系统复位，CPU 从启动代码开始执行，而不是从睡眠前指令继续执行。需要在 `Reset_Handler` 或 `main()` 早期读取 PWR、RTC 和 RCC 复位标志。

### 问题六：为什么 RTC 备份域功耗比数据手册高？

可能原因：

- VBAT 电压不在指定范围；
- LSE 负载电容配置不匹配；
- 备份寄存器或 Tamper 电路开启；
- GPIO 通过外部器件反向供电；
- 纽扣电池、超级电容或 PCB 漏电；
- 调试器或测量设备影响备份域。

应单独测量 VBAT 电流，并断开外部备份域负载进行对比。

### 问题七：是否可以每秒使用 RTC Alarm 唤醒一次？

可以，但通常不推荐。频繁唤醒会增加 CPU、时钟恢复和任务调度能耗。若只需要短周期计时，优先使用 LPTIM；若需要低功耗日历基准，可让 RTC 保持运行，由 LPTIM 承担短周期事件。

### 问题八：RTC 能否替代系统单调时钟？

不建议直接替代。RTC 可能被用户校准、网络同步或手动回拨，不保证单调递增。系统应同时维护：

- **Wall Clock**：可调整的日历时间；
- **Monotonic Clock**：只递增的超时和调度时间。

## 13. 课程核心总结

### 核心要点

1. **RTC 是低功耗系统的长期绝对时间基准。**
2. RTC Wakeup Timer 适合相对周期，Alarm 适合绝对时间。
3. LSE 是工业产品的优先时钟源，LSI 必须评估误差和温漂。
4. 周期调度必须基于绝对时间，避免业务处理时间累积漂移。
5. RTC 唤醒涉及 RTC、EXTI、PWR、NVIC 多层标志。
6. Standby 唤醒通常经过复位流程，必须在启动早期判断原因。
7. RTC 时间修改必须处理任务重排、时间回拨和重复执行。
8. RTC 低功耗收益不能脱离 VBAT、LSE、备份域和外部器件单独评价。
9. RTC、LPTIM、GPIO、IWDG 应由统一唤醒管理器协同。
10. **工业级 RTC 设计的核心是时间可信、唤醒可靠、误差可量化、恢复可诊断。**

### 性能排序

低功耗时基的典型功耗从低到高：

```
RTC + LSE + 备份域
    ≤ RTC + LSI
    < LPTIM + 低功耗时钟
    < 通用 TIM
    < SysTick 持续运行
```

长期时间能力：

```
RTC Alarm/Calendar > RTC Wakeup Timer > LPTIM > SysTick
```

短周期分辨率：

```
通用 TIM > LPTIM > RTC 子秒/1 Hz > RTC 秒级 Alarm
```

### 通用选型结论

- **绝对时间和长期保持：RTC Calendar + Alarm**；
- **低功耗相对周期：RTC Wakeup Timer**；
- **短周期和更高分辨率：LPTIM**；
- **微秒级控制：通用 TIM**；
- **Standby/Shutdown 唤醒：RTC + PWR 唤醒逻辑**；
- **长期精度要求高：LSE + 校准 + 外部时间同步**。

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选方案|关键检查|
|---|---|---|
|每秒/每分钟周期唤醒|RTC Wakeup Timer|计数范围、唤醒标志|
|每天固定时间执行|RTC Alarm|掩码、跨日和时间有效性|
|每周任务|RTC Alarm + 日历计算|星期、日期和回拨|
|Standby 长期待机|RTC + VBAT|备份域功耗、唤醒复位|
|Stop 周期采样|RTC/LPTIM|CPU 上下文和恢复时间|
|高频超时|LPTIM|分辨率、时钟保持|
|时间戳记录|RTC Calendar|校准、有效标志|
|防拆唤醒|RTC Tamper|滤波、误触发和安全日志|

### 14.2 标志处理表

|层级|示例|处理要求|
|---|---|---|
|RTC 原始标志|Alarm、Wakeup、Tamper|读取并清除|
|EXTI Pending|RTC Alarm/Wakeup Line|必须清除|
|NVIC Pending|RTC IRQ|按场景清除|
|PWR Wake Flag|Stop/Standby 唤醒|深睡眠必须检查|
|RCC Reset Flag|POR/BOR/IWDG|启动早期读取|
|Backup Magic|RTC 初始化有效性|防止重复初始化|

### 14.3 RTC 配置检查清单

```
[ ] LSE/LSI 时钟源已确认
[ ] 时钟频率和 ppm 误差已测量或定义
[ ] 备份域写保护已正确处理
[ ] RTC 未被无条件重新初始化
[ ] 预分频器计算正确
[ ] Wakeup Timer 计数语义已确认
[ ] Alarm 掩码语义已确认
[ ] RTC 原始标志已清除
[ ] EXTI/NVIC/PWR 标志已清除
[ ] Stop/Standby 保持能力已验证
[ ] Standby 唤醒原因在启动早期读取
[ ] 周期任务使用绝对时间
[ ] 时间回拨和校准策略已定义
[ ] RTC 失效有 LSI/外部参考回退
[ ] VBAT 和备份域电流已单独测量
[ ] 闰年、月底、跨日、跨年已测试
[ ] 唤醒、漂移和重复唤醒可统计
```

## 15. 学习效果自检

- [ ]  能解释 RTC 时钟、预分频器、日历和唤醒逻辑之间的关系。
- [ ]  能区分 RTC Wakeup Timer 与 RTC Alarm 的适用场景。
- [ ]  能根据 LSE 频率计算 RTC 预分频器。
- [ ]  能计算给定 ppm 晶振的日误差和月误差。
- [ ]  能设计周期任务的绝对时间调度。
- [ ]  能正确处理 RTC、EXTI、PWR、NVIC 和 RCC 标志。
- [ ]  能解释 Standby 唤醒为什么通常走复位路径。
- [ ]  能处理 RTC 时间回拨、网络对时和任务重排。
- [ ]  能设计 RTC Alarm 的每日、每周和跨日任务。
- [ ]  能定位 RTC 立即重复唤醒的原因。
- [ ]  能测量 VBAT、LSE 和备份域的实际功耗。
- [ ]  能设计 RTC 时间有效性、校准和故障回退机制。
- [ ]  能将 RTC 与 LPTIM、GPIO、IWDG 组合成统一唤醒架构。
- [ ]  能验证闰年、月底、跨年和掉电恢复行为。

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：RTC 基础初始化

- 配置 LSE；
- 设置 RTC 日历；
- 写入 Backup Magic；
- 重启后验证时间不会被重复初始化。

验收：冷启动、软件复位和掉电恢复三种场景行为不同且可解释。

#### 任务二：RTC Wakeup Timer 周期唤醒

- 配置 1 秒、5 秒、60 秒周期；
- 进入 Stop；
- 记录 RTC、EXTI、PWR 和 NVIC 标志；
- 测量周期误差和唤醒延迟。

验收：连续运行 24 小时无唤醒风暴，误差可归因到时钟和同步项。

#### 任务三：RTC Alarm 固定时间唤醒

- 配置每天固定时间；
- 覆盖跨日、月底、闰年和跨年；
- 验证 Alarm 掩码；
- 模拟时间回拨。

验收：任务不重复执行、不漏执行，时间修改后能正确重排。

#### 任务四：RTC + Standby

- 保存任务序号和下一次截止时间；
- 进入 Standby；
- 通过 RTC、GPIO 和看门狗分别唤醒；
- 在启动早期识别唤醒原因。

验收：不同唤醒源不会被错误合并，恢复上下文带 CRC 校验。

#### 任务五：RTC 校准

- 使用参考时钟测量 LSE/LSI 误差；
- 在不同温度下采集偏差；
- 实现数字校准或软件补偿；
- 对比校准前后的 24 小时误差。

验收：输出校准参数、温度条件、残余误差和有效期。

#### 任务六：整机 RTC 低功耗回归

覆盖：

- LSE/LSI 切换；
- Stop/Standby/Shutdown；
- RTC Alarm/Wakeup；
- GPIO 并发唤醒；
- 看门狗复位；
- VBAT 掉电；
- 时间回拨；
- 备份域复位；
- 高低温和电池电压边界；
- 旧标志残留和重复进入低功耗。

### 16.2 性能测试方法

|测试项|方法|
|---|---|
|RTC 频率精度|与参考频率源比较长期周期|
|Alarm 时间精度|计划时间与 GPIO 唤醒时间比较|
|Wakeup Timer 周期|连续记录多次唤醒间隔|
|唤醒延迟|RTC 事件到 ISR/Reset_Handler 打点|
|备份域功耗|单独测量 VBAT 电流|
|低功耗电流|Stop/Standby 稳态窗口平均值|
|重复唤醒|长时间统计相邻唤醒间隔|
|掩码正确性|模拟每天、每小时、每分钟匹配|
|时间回拨|修改 RTC 前后验证任务重排|
|掉电恢复|断开 VDD、保持/断开 VBAT 分别测试|
|标志正确性|同时注入 RTC、GPIO、IWDG 事件|
|温漂|温箱中比较不同温度的时间误差|

周期误差：

ϵT=Tactual−TtargetTtargetϵT​=Ttarget​Tactual​−Ttarget​​

晶振误差：

Δt=t×ppm×10−6Δt=t×ppm×10−6

平均功耗：

Pavg=∑iEiTobservationPavg​=Tobservation​∑i​Ei​​

单次唤醒能量：

Ewake=∫V(t)I(t)dtEwake​=∫V(t)I(t)dt

时间调度约束：

Twake+Trestore+Ttask≤TdeadlineTwake​+Trestore​+Ttask​≤Tdeadline​

### 16.3 进阶学习方向

1. RTC 异步/同步预分频器和跨时钟域同步；
2. RTC Alarm 掩码、子秒 Alarm 和日历边界处理；
3. LSE 晶振选型、负载电容、启动时间和温漂；
4. RTC 数字校准、温度补偿和网络对时；
5. Backup SRAM、FRAM、EEPROM 和掉电一致性；
6. RTOS 时间服务、单调时钟和墙上时钟分离；
7. RTC + LPTIM + Tickless 的多级低功耗调度；
8. Standby/Shutdown 启动路径、复位原因和安全恢复；
9. RTC Tamper、防拆、可信时间和安全日志；
10. 多设备时间同步、PTP/NTP/GNSS 时间源和工业事件时序分析。

**最终工程结论：RTC 唤醒不是“设置一个闹钟后进入低功耗”，而是对低速时钟精度、备份域保持、日历计算、Alarm/Wakeup 计数、标志生命周期、复位恢复、时间校准和任务调度进行系统级设计。只有做到“时间可信、唤醒可靠、误差可量化、掉电可恢复、回拨可处理、故障可诊断”，RTC 才能成为工业级低功耗系统的稳定时间基准。**