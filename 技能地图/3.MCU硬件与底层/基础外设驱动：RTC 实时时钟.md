
## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 RTC 与普通定时器、系统 Tick、低功耗唤醒定时器之间的职责边界。
- 理解 RTC 的时钟源、分频链、计数器、日历寄存器、闹钟、唤醒定时器和时间戳机制。
- 理解 RTC 在掉电保持、低功耗运行、时间基准、事件调度中的系统级定位。
- 理解 **UTC、Unix 时间戳、本地时间、夏令时、闰年、闰秒** 等时间概念的工程含义。
- 理解 RTC 误差来源：晶振误差、温漂、老化、负载电容偏差、PCB 噪声和供电切换。

### 1.2 掌握

能够：

- 完成 RTC 的时钟源、预分频、计数器、日历和备份域初始化。
- 设计 Unix 时间戳与日历时间之间的转换模块。
- 实现 RTC 当前时间读取、设置、闹钟、周期唤醒和时间戳捕获。
- 正确处理 RTC 备份电源、首次上电、软件复位、掉电恢复和时间有效性校验。
- 使用单调时基和 RTC 墙上时间协同完成超时、日志、定时任务调度。

### 1.3 精通

能够：

- 从寄存器级分析 RTC 初始化、同步、写保护和备份域复位流程。
- 量化不同时钟源下的时间精度、功耗、启动时间和可靠性。
- 处理 **RTC 时钟源失效、非法时间、跨世纪、溢出、备份域异常和时间回拨**。
- 设计可审计的时间服务，包括时间有效标记、校时策略、时间质量等级和漂移补偿。
- 识别并解决 RTC 读写中的竞态、寄存器锁存、异步同步延迟和中断重复触发问题。

### 1.4 能够设计

能够设计：

- 适用于工业控制器、数据记录器、低功耗传感器和网关设备的完整 RTC 服务。
- 支持掉电保持、网络校时、外部 PPS 校时、闹钟唤醒和事件日志的时间管理架构。
- 支持多时间域：**单调时间、UTC 时间、本地显示时间、设备运行时间**。
- 支持时间回拨保护、日志排序、时间质量追踪和异常恢复的工业级时间系统。

---

## 2. 前置要求

### 2.1 知识要求

- MCU 时钟树、复位控制、备份域和低功耗电源域。
- GPIO、外部中断、定时器、DMA 和中断优先级。
- C 语言位操作、结构体、枚举、函数指针和模块封装。
- 基本日期算法：闰年、月份天数、Unix Epoch。
- RTOS 基本概念：Tick、任务、软件定时器、互斥锁和临界区。
- 串口、I²C、SPI 等基础通信机制。
- 低功耗模式：Sleep、Stop、Standby、Hibernate。

### 2.2 技能要求

- 能够阅读 MCU Reference Manual 的 RCC/PWR/RTC 章节。
- 能够使用逻辑分析仪、示波器、频率计或高精度时间源进行时钟测量。
- 能够编写寄存器级初始化代码和 HAL/LL/BSP 封装。
- 能够使用调试器观察备份寄存器、复位原因和低功耗唤醒原因。
- 能够编写单元测试、边界测试和长时间漂移测试。
- 能够分析系统启动、掉电、复位、唤醒和时间同步日志。

---

## 3. 技术概述

## 3.1 RTC 的核心定义

RTC，即 Real-Time Clock，实时时钟，是运行在独立低速时钟域中的时间保持模块，通常具备：

- 秒级或亚秒级时间计数；
- 日历时间维护；
- 低功耗运行；
- 备份电源供电；
- 闹钟唤醒；
- 周期唤醒；
- 时间戳捕获；
- 备份寄存器；
- 低速时钟失效检测。

RTC 的本质通常不是“保存年月日的寄存器”，而是：

> **在独立时钟域中持续维护一个时间计数器，并通过软件或硬件将其解释为日历时间。**

常见实现有两类：

1. **纯计数器型 RTC**
    
    - 内部维护秒计数器；
    - 软件负责 Unix 时间戳与年月日转换；
    - 结构简单、可移植性高。
2. **硬件日历型 RTC**
    
    - 硬件直接维护年、月、日、时、分、秒；
    - 支持 BCD 编码、日期进位和闹钟匹配；
    - 软件使用方便，但寄存器访问和初始化流程更复杂。

---

## 3.2 RTC 的系统定位

RTC 与其他时间机制的关系如下：

|时间机制|主要用途|是否掉电保持|精度|是否单调|典型实现|
|---|---|---|---|---|---|
|RTC|绝对时间、日志时间、预约唤醒|是，配合备份电源|ppm 级|不一定|LSE/LFXO、外部 RTC|
|SysTick|RTOS 调度、短周期超时|否|通常 ms 级|通常是|内核定时器|
|通用定时器|PWM、捕获、精确周期事件|否|us/ns 级|通常是|APB Timer|
|DWT/Cycle Counter|性能测量、短时间间隔|否|CPU 周期级|是|CPU 调试单元|
|低功耗唤醒定时器|Stop/Standby 唤醒|部分|ms/s 级|通常是|LPTIM/WUT|
|网络时间|UTC 校准|取决于本地保存|依赖网络|不保证|NTP/PTP|
|GNSS/PPS|高精度绝对时间|否|ns~us 级|可校准|GPS/GNSS|

**核心结论：**

- **RTC 适合绝对时间，不适合高精度短延时。**
- **系统 Tick 适合任务调度，不适合掉电保持。**
- **单调时钟适合超时和时间间隔，不应直接替代墙上时间。**
- **日志系统必须区分墙上时间和单调时间。**

---

## 3.3 RTC 时钟源分类

### 3.3.1 外部低速晶振 LSE/LFXO

典型频率：

fLSE=32.768 kHzfLSE​=32.768 kHz

因为：

32768=21532768=215

所以经过 15 级二分频后可得到 1 Hz：

fRTC=32768215=1 HzfRTC​=21532768​=1 Hz

特点：

- 精度通常为 **±10 ppm 到 ±100 ppm**；
- 低功耗；
- 适合作为工业设备 RTC 主时钟；
- 受晶振负载电容、布局、温度和老化影响；
- 启动时间通常高于内部 RC。

### 3.3.2 内部低速 RC 时钟 LSI/IRC

典型频率：

- 32 kHz；
- 37 kHz；
- 40 kHz；
- 可能随芯片、温度和电压变化。

特点：

- 无需外部晶振，成本低；
- 启动快；
- 频率精度通常仅为 **±1% 到 ±10%** ；
- 适合看门狗、低精度唤醒；
- 不适合作为长期时间基准，除非有校准机制。

### 3.3.3 外部 RTC 芯片

典型器件：

- DS3231：带温度补偿；
- RV-3028：超低功耗；
- PCF8563：成本较低；
- RX8010、BM8563 等。

特点：

- 独立于 MCU；
- 可具备更好的精度和掉电保持；
- 通过 I²C/SPI 通信；
- 需要处理总线故障、通信延迟和上电时序；
- 适用于 MCU RTC 性能不足或需要高精度保持的场景。

### 3.3.4 网络或卫星时间源

包括：

- NTP；
- SNTP；
- PTP；
- GNSS；
- 外部 PPS；
- 工业现场时钟同步协议。

它们通常用于：

- 初始校时；
- 周期校时；
- 多设备时间一致性；
- 高精度时间同步。

---

## 4. 核心特性横向对比

## 4.1 时钟源对比

|维度|外部 32.768 kHz 晶振|内部 LSI/IRC|外部 RTC 芯片|GNSS/PPS|NTP|
|---|---|---|---|---|---|
|典型精度|±10~100 ppm|±1%~10%|±2~32 ppm|ns~us 级|ms~100 ms|
|静态功耗|0.3~2 µA|0.5~5 µA|0.1~3 µA|20~100 mA|依赖网络|
|启动时间|0.5~2 s|10~100 ms|100~1000 ms|秒级到分钟|秒级|
|硬件成本|低|最低|中|高|低至中|
|失效模式|晶振停振、负载错误|温漂大、频率漂移|总线故障、供电故障|天线遮挡、无卫星|网络不可用|
|低功耗适配|好|好|好|差|不适用|
|长期保持能力|中高|差|高|非本地保持源|依赖周期同步|
|适用场景|通用工业 MCU|低成本、低精度|高可靠、长时间保持|高精度校时|联网设备|

---

## 4.2 RTC 计时实现对比

|方案|时间表示|优点|缺点|适用场景|
|---|---|---|---|---|
|硬件日历寄存器|年/月/日/时/分/秒|使用方便，支持硬件闹钟|BCD 转换复杂，访问同步要求高|MCU 内置 RTC|
|Unix 秒计数器|自 Epoch 起的秒数|算法统一，易存储、易比较|需要日历转换|多平台时间服务|
|Unix 秒 + 亚秒|秒 + subsecond|支持高精度日志|溢出、校准更复杂|测量、工业日志|
|纯软件时间|RAM 中递增|无需 RTC|复位或掉电丢失|临时运行时间|
|外部 RTC + MCU 软件|芯片计数器|可获得更高精度|总线通信开销|高可靠产品|

---

## 4.3 RTC 闹钟机制对比

|机制|精度|低功耗唤醒|资源占用|典型用途|
|---|---|---|---|---|
|秒级 Alarm|1 s|是|低|定时唤醒、日程任务|
|日历匹配 Alarm|1 s|是|低|每天某时刻触发|
|Wake-up Timer|低至 ms 级，取决于分频|是|低|周期唤醒|
|普通定时器|us 级|视芯片而定|中|高频周期任务|
|软件定时器|Tick 级|通常否|RAM/任务|RTOS 内部调度|
|外部引脚时间戳|输入边沿精度|可选|中|PPS、事件记录|

---

# 5. 底层原理与功能特性深度解析

## 5.1 RTC 硬件结构

典型 RTC 模块包含：

```
+--------------------+
LSE/LSI ------->| 时钟选择与分频链     |
                 +---------+----------+
                           |
                           v
                 +--------------------+
                 | 1 Hz 或亚秒时基     |
                 +---------+----------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
     +---------------+           +---------------+
     | 日历/秒计数器  |           | 唤醒定时器     |
     +-------+-------+           +-------+-------+
             |                           |
             v                           v
     +---------------+           +---------------+
     | Alarm 匹配器   |           | 中断/唤醒输出   |
     +---------------+           +---------------+

备份域：
- RTC 核心寄存器
- 备份寄存器
- RTC 时钟源选择
- 低速晶振使能
- 电源切换逻辑
```

RTC 往往位于独立电源域，具有以下特点：

1. **主电源关闭时仍可能运行**；
2. MCU 主域复位不一定清除 RTC；
3. 备份域复位可能导致时间、时钟源配置、备份寄存器全部丢失；
4. 访问 RTC 寄存器时可能跨越异步时钟域；
5. RTC 写入通常有专门的解锁和同步流程。

---

## 5.2 32.768 kHz 分频原理

假设输入时钟为 32.768 kHz，需要得到 1 Hz：

fRTC=fLSE(PREDIVA+1)(PREDIVS+1)fRTC​=(PREDIVA​+1)(PREDIVS​+1)fLSE​​

一种常见配置：

PREDIVA=127,PREDIVS=255PREDIVA​=127,PREDIVS​=255

则：

(127+1)(255+1)=128×256=32768(127+1)(255+1)=128×256=32768

因此：

fRTC=3276832768=1 HzfRTC​=3276832768​=1 Hz

这里通常存在两个分频器：

- **异步预分频器**：降低功耗，减少后级翻转频率；
- **同步预分频器**：生成亚秒分辨率或 1 Hz 计数。

如果只需要秒级时间，选择合理的同步预分频即可。如果需要亚秒时间戳，则必须保留足够的同步计数分辨率。

---

## 5.3 RTC 误差量化

RTC 的频率误差通常用 ppm 表示：

1 ppm=10−61 ppm=10−6

时间误差：

Δt=t×ϵΔt=t×ϵ

其中：

- tt：运行时间；
- ϵϵ：相对频率误差。

例如 20 ppm 晶振运行一年：

Δt=365×24×3600×20×10−6Δt=365×24×3600×20×10−6Δt≈630.72 sΔt≈630.72 s

即约 **10.5 分钟/年**。

不同误差水平的年误差：

|频率误差|每天误差|每月误差|每年误差|
|---|---|---|---|
|1 ppm|86.4 ms|2.59 s|31.54 s|
|10 ppm|864 ms|25.92 s|5.26 min|
|20 ppm|1.728 s|51.84 s|10.51 min|
|50 ppm|4.32 s|129.6 s|26.28 min|
|100 ppm|8.64 s|259.2 s|52.56 min|
|1%|864 s|7.2 h|3.65 d|

**工程结论：**

- “RTC 能走”不等于“时间准确”；
- 10 ppm 并不代表一年只误差 10 秒；
- 产品需求必须明确时间误差预算；
- 如果要求每天误差小于 1 秒，频率误差至少要控制在：

ϵ<186400≈11.57 ppmϵ<864001​≈11.57 ppm

---

## 5.4 晶振负载电容与频率偏差

外部 32.768 kHz 晶振需要匹配负载电容。常见估算：

CL=C1C2C1+C2+CstrayCL​=C1​+C2​C1​C2​​+Cstray​

当 C1=C2=CC1​=C2​=C 时：

CL≈C2+CstrayCL​≈2C​+Cstray​

若晶振标称负载为 12.5 pF，PCB 寄生电容估计为 2.5 pF，则：

C≈2(CL−Cstray)=2(12.5−2.5)=20 pFC≈2(CL​−Cstray​)=2(12.5−2.5)=20 pF

但实际不能简单套公式，还需要参考：

- MCU 内部负载电容；
- 晶振数据手册；
- PCB 走线寄生；
- MCU 推荐应用电路；
- ESR 限制；
- 启动裕量。

负载电容错误可能造成：

- 晶振不起振；
- RTC 启动时间变长；
- 频率偏移；
- 温度变化时稳定性恶化；
- 偶发停振。

---

## 5.5 备份电源与供电切换

常见供电结构：

```
主电源 VDD --------+
                   |---- 电源切换 ---- RTC Core
备份电源 VBAT -----+

主电源存在：RTC 由 VDD 供电
主电源掉电：RTC 切换到 VBAT
```

必须区分：

- **备份域是否有电**；
- **RTC 时钟是否运行**；
- **RTC 配置是否保留**；
- **备份寄存器是否保留**；
- **低速晶振是否继续运行**。

典型问题：

1. VBAT 有电，但 RTC 域被软件复位；
2. MCU 复位后重新配置 RTC，误清空时间；
3. 首次上电标志存储在普通 RAM 中，复位后丢失；
4. 纽扣电池反向充电；
5. 备份域电源切换时产生毛刺；
6. 使用超级电容时，掉电保持时间不足；
7. 外部 RTC 的 I²C 上拉仍由主电源供电，主电源断电后总线反向供电。

---

## 5.6 生产级 RTC 数据结构

建议统一使用 Unix 时间作为系统内部标准，并用结构体表示日历时间：

```
#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint16_t year;        /* 2000~2099，具体范围由产品定义 */
    uint8_t  month;       /* 1~12 */
    uint8_t  day;         /* 1~31 */
    uint8_t  hour;        /* 0~23 */
    uint8_t  minute;      /* 0~59 */
    uint8_t  second;      /* 0~59 */
    uint16_t millisecond; /* 0~999 */
} rtc_datetime_t;

typedef struct {
    uint64_t unix_sec;
    uint32_t subsec_us;
    bool     valid;
} rtc_timestamp_t;

typedef enum {
    RTC_TIME_QUALITY_INVALID = 0,
    RTC_TIME_QUALITY_BACKUP,
    RTC_TIME_QUALITY_NETWORK,
    RTC_TIME_QUALITY_GNSS,
    RTC_TIME_QUALITY_FACTORY
} rtc_time_quality_t;
```

**建议：**

- 日志和协议内部使用 UTC；
- UI 显示时才转换成本地时区；
- 时间戳使用无符号 64 位；
- 时间有效性不能仅由时间值判断；
- 时间质量必须独立保存。

---

## 5.7 日历合法性校验

```
#include <stdbool.h>
#include <stdint.h>

static bool rtc_is_leap_year(uint16_t year)
{
    return ((year % 4U == 0U) &&
            ((year % 100U != 0U) || (year % 400U == 0U)));
}

static uint8_t rtc_days_in_month(uint16_t year, uint8_t month)
{
    static const uint8_t days_table[12] = {
        31U, 28U, 31U, 30U, 31U, 30U,
        31U, 31U, 30U, 31U, 30U, 31U
    };

    if ((month == 0U) || (month > 12U)) {
        return 0U;
    }

    if ((month == 2U) && rtc_is_leap_year(year)) {
        return 29U;
    }

    return days_table[month - 1U];
}

bool rtc_datetime_is_valid(const rtc_datetime_t *dt)
{
    uint8_t max_day;

    if (dt == NULL) {
        return false;
    }

    if ((dt->year < 2000U) || (dt->year > 2099U)) {
        return false;
    }

    if (dt->month < 1U || dt->month > 12U) {
        return false;
    }

    max_day = rtc_days_in_month(dt->year, dt->month);

    if (dt->day < 1U || dt->day > max_day) {
        return false;
    }

    if (dt->hour > 23U ||
        dt->minute > 59U ||
        dt->second > 59U ||
        dt->millisecond > 999U) {
        return false;
    }

    return true;
}
```

需要特别处理：

- 2000 年是闰年；
- 1900 年不是闰年；
- 2100 年不是闰年；
- 不同 MCU 对闰秒的支持不同；
- 多数嵌入式 RTC 直接忽略闰秒，采用连续 POSIX 时间。

---

## 5.8 Unix 时间戳转换

下面代码使用 2000-01-01 作为内部 Epoch，避免 32 位 Unix 时间戳在 2038 年溢出问题。

```
#include <stdint.h>
#include <stdbool.h>

#define RTC_EPOCH_YEAR 2000U

static uint32_t rtc_days_before_year(uint16_t year)
{
    uint32_t days = 0U;

    for (uint16_t y = RTC_EPOCH_YEAR; y < year; ++y) {
        days += rtc_is_leap_year(y) ? 366U : 365U;
    }

    return days;
}

static uint32_t rtc_days_before_month(uint16_t year, uint8_t month)
{
    uint32_t days = 0U;

    for (uint8_t m = 1U; m < month; ++m) {
        days += rtc_days_in_month(year, m);
    }

    return days;
}

bool rtc_datetime_to_epoch2000(const rtc_datetime_t *dt, uint64_t *epoch_sec)
{
    uint64_t days;

    if ((dt == NULL) || (epoch_sec == NULL)) {
        return false;
    }

    if (!rtc_datetime_is_valid(dt)) {
        return false;
    }

    days = rtc_days_before_year(dt->year);
    days += rtc_days_before_month(dt->year, dt->month);
    days += (uint32_t)(dt->day - 1U);

    *epoch_sec = days * 86400ULL
              + (uint64_t)dt->hour * 3600ULL
              + (uint64_t)dt->minute * 60ULL
              + dt->second;

    return true;
}

bool rtc_epoch2000_to_datetime(uint64_t epoch_sec, rtc_datetime_t *dt)
{
    uint64_t days;
    uint32_t seconds_of_day;
    uint16_t year = RTC_EPOCH_YEAR;
    uint8_t month = 1U;

    if (dt == NULL) {
        return false;
    }

    days = epoch_sec / 86400ULL;
    seconds_of_day = (uint32_t)(epoch_sec % 86400ULL);

    while (true) {
        uint32_t days_in_year =
            rtc_is_leap_year(year) ? 366U : 365U;

        if (days < days_in_year) {
            break;
        }

        days -= days_in_year;
        ++year;

        /* 防止异常时间戳导致年份无限增长 */
        if (year == UINT16_MAX) {
            return false;
        }
    }

    while (true) {
        uint8_t dim = rtc_days_in_month(year, month);

        if (days < dim) {
            break;
        }

        days -= dim;
        ++month;

        if (month > 12U) {
            return false;
        }
    }

    dt->year = year;
    dt->month = month;
    dt->day = (uint8_t)days + 1U;
    dt->hour = (uint8_t)(seconds_of_day / 3600U);
    seconds_of_day %= 3600U;
    dt->minute = (uint8_t)(seconds_of_day / 60U);
    dt->second = (uint8_t)(seconds_of_day % 60U);
    dt->millisecond = 0U;

    return true;
}
```

生产项目中，如果时间转换频繁调用，不建议每次使用循环遍历年份和月份。可以：

- 预计算月份累计天数；
- 使用 Howard Hinnant 等常数时间算法；
- 将时间转换放到日志任务中；
- 避免在高优先级中断中进行日历转换。

---

## 5.9 RTC BCD 编码处理

许多 RTC 硬件寄存器采用 BCD：

```
static uint8_t rtc_bin_to_bcd(uint8_t value)
{
    return (uint8_t)(((value / 10U) << 4U) | (value % 10U));
}

static uint8_t rtc_bcd_to_bin(uint8_t value)
{
    return (uint8_t)(((value >> 4U) * 10U) + (value & 0x0FU));
}
```

必须校验 BCD 合法性：

```
static bool rtc_is_valid_bcd(uint8_t bcd, uint8_t max_value)
{
    uint8_t high = (uint8_t)(bcd >> 4U);
    uint8_t low  = (uint8_t)(bcd & 0x0FU);

    if (low > 9U || high > 9U) {
        return false;
    }

    return rtc_bcd_to_bin(bcd) <= max_value;
}
```

错误示例：

```
/* 错误：直接把 BCD 当作二进制 */
uint8_t hour = rtc_reg_hour; /* 0x23 被解释成十进制 35 */
```

正确实现：

```
uint8_t hour = rtc_bcd_to_bin(rtc_reg_hour);
```

---

## 5.10 RTC 寄存器访问同步

RTC 通常运行在低速异步时钟域，CPU 运行在高速主时钟域。二者之间存在 CDC，即 Clock Domain Crossing。

常见硬件机制：

- 影子寄存器；
- 双级同步器；
- 读锁存；
- 写同步等待；
- RSF 寄存器同步标志；
- 进入/退出初始化模式。

典型读取流程：

```
1. 等待 RTC 寄存器同步完成
2. 读取时间寄存器
3. 读取日期寄存器
4. 必要时重复读取，确保跨秒边界一致
```

某些 MCU 要求：

> 必须先读时间，再读日期。

原因可能是：

- 读时间操作锁存当前日历值；
- 读日期清除锁存；
- 直接先读日期可能得到不一致组合。

生产级抽象接口：

```
typedef enum {
    RTC_OK = 0,
    RTC_ERR_PARAM,
    RTC_ERR_TIMEOUT,
    RTC_ERR_INVALID_TIME,
    RTC_ERR_CLOCK_SOURCE,
    RTC_ERR_NOT_INITIALIZED,
    RTC_ERR_HW
} rtc_status_t;

rtc_status_t rtc_hw_wait_sync(uint32_t timeout_ms);
rtc_status_t rtc_hw_read_datetime(rtc_datetime_t *dt);
rtc_status_t rtc_hw_write_datetime(const rtc_datetime_t *dt);
```

带超时的同步等待：

```
rtc_status_t rtc_hw_wait_sync(uint32_t timeout_ms)
{
    uint32_t start = platform_get_tick_ms();

    while (!RTC_STATUS_REG_SYNC_READY) {
        if ((platform_get_tick_ms() - start) >= timeout_ms) {
            return RTC_ERR_TIMEOUT;
        }
    }

    return RTC_OK;
}
```

注意 Tick 回绕时不能直接使用：

```
/* 不推荐：存在 Tick 回绕问题 */
if (platform_get_tick_ms() > start + timeout_ms) {
}
```

应使用无符号差值：

```
if ((uint32_t)(platform_get_tick_ms() - start) >= timeout_ms) {
}
```

---

## 5.11 RTC 初始化的生产级流程

典型流程：

```
系统启动
  |
  v
读取复位原因、备份域状态、RTC 时钟源状态
  |
  v
检查 RTC 是否已配置
  |
  +-- 已配置且时钟有效 --> 保留时间，仅同步软件状态
  |
  +-- 未配置 -----------> 解锁备份域
                            |
                            v
                      选择 LSE/LSI/外部 RTC
                            |
                            v
                      等待时钟稳定
                            |
                            v
                      配置预分频器
                            |
                            v
                      设置初始时间
                            |
                            v
                      写入魔术字、版本号、CRC
                            |
                            v
                      锁定备份域
```

不要简单地在每次启动时执行：

```
RTC_Init();
RTC_SetTime(2024, 1, 1, 0, 0, 0);
```

这会导致：

- 软件复位后时间被重置；
- 看门狗复位后时间被重置；
- 升级重启后时间被重置；
- 设备无法保留掉电时间。

---

## 5.12 备份域有效性标记

建议不要只使用一个固定魔术数：

```
typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    uint64_t epoch2000;
    uint32_t generation;
    uint32_t crc32;
} rtc_backup_record_t;

#define RTC_BACKUP_MAGIC   0x52544331UL
#define RTC_BACKUP_VERSION 1U
```

启动时检查：

1. 魔术数；
2. 版本；
3. 记录字段范围；
4. CRC；
5. RTC 硬件状态；
6. 低速时钟源是否有效；
7. 掉电或篡改标志。

注意：备份记录中的时间只是“最后一次确认状态”，真正当前时间仍应从 RTC 硬件读取。

---

## 5.13 闹钟与周期唤醒

### 闹钟逻辑

闹钟匹配器通常支持：

- 秒匹配；
- 分匹配；
- 时匹配；
- 星期匹配；
- 日期匹配；
- 掩码匹配。

例如每天 08:30:00：

```
typedef struct {
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
    bool    every_day;
} rtc_alarm_t;

rtc_status_t rtc_set_daily_alarm(const rtc_alarm_t *alarm)
{
    if (alarm == NULL) {
        return RTC_ERR_PARAM;
    }

    if (alarm->hour > 23U ||
        alarm->minute > 59U ||
        alarm->second > 59U) {
        return RTC_ERR_INVALID_TIME;
    }

    /*
     * 1. 禁止 Alarm 中断
     * 2. 清除 Alarm 标志
     * 3. 写入 BCD 格式时分秒
     * 4. 配置日期掩码为每周/每天匹配
     * 5. 清除挂起标志
     * 6. 使能 Alarm
     * 7. 使能 EXTI/NVIC/唤醒路径
     */

    return RTC_OK;
}
```

### 周期唤醒定时器

周期唤醒适合：

- 每 10 秒采样；
- 每 5 分钟上报；
- 低功耗设备周期检查；
- 传感器轮询。

如果 RTC 时钟为 1 Hz，周期唤醒计数值 NN 对应：

T=N sT=N s

如果唤醒时钟为 2 kHz：

T=N2000 sT=2000N​ s

实际周期还要考虑：

- 唤醒同步延迟；
- 电源稳定时间；
- 启动代码执行时间；
- 任务调度延迟；
- 时钟源漂移。

---

## 5.14 RTC 时间戳捕获

时间戳功能用于记录外部事件发生时刻，例如：

- GPIO 上升沿；
- PPS；
- 传感器告警；
- 电源掉电；
- 工业总线事件；
- 外部脉冲计数。

推荐结构：

```
typedef struct {
    uint64_t epoch_sec;
    uint32_t subsec;
    uint32_t flags;
} rtc_event_timestamp_t;

volatile rtc_event_timestamp_t g_last_timestamp;
volatile bool g_timestamp_pending;

void RTC_Timestamp_IRQHandler(void)
{
    uint32_t status = rtc_hw_get_status();

    if ((status & RTC_STATUS_TIMESTAMP) != 0U) {
        rtc_event_timestamp_t ts;

        ts.epoch_sec = rtc_hw_read_timestamp_seconds();
        ts.subsec = rtc_hw_read_timestamp_subseconds();
        ts.flags = status;

        g_last_timestamp = ts;
        g_timestamp_pending = true;

        rtc_hw_clear_status(RTC_STATUS_TIMESTAMP);
    }
}
```

中断中不要执行：

- 日历格式化；
- Flash 写入；
- 网络发送；
- 大量日志打印；
- 复杂时间转换。

---

## 5.15 时间服务中的双时钟设计

工业系统通常需要同时维护：

```
墙上时间 Wall Clock：
- UTC 时间
- 可能被校时
- 可能跳变
- 用于日志、显示、协议

单调时间 Monotonic Clock：
- 只递增
- 不受校时回拨影响
- 用于超时、重试、延时和状态机
```

抽象接口：

```
typedef struct {
    uint64_t utc_sec;
    uint32_t utc_us;
    uint64_t mono_us;
    rtc_time_quality_t quality;
} system_time_t;

bool system_time_get(system_time_t *time);

uint64_t system_mono_us(void);
bool system_utc_get(uint64_t *sec, uint32_t *us);
rtc_status_t system_utc_set(uint64_t sec,
                            uint32_t us,
                            rtc_time_quality_t quality);
```

错误做法：

```
uint64_t deadline = rtc_get_epoch() + 10U;

while (rtc_get_epoch() < deadline) {
    /*
     * 如果 NTP 校时将时间回拨，循环可能无限等待；
     */
}
```

正确做法：

```
uint64_t deadline = system_mono_us() + 10ULL * 1000000ULL;

while ((int64_t)(system_mono_us() - deadline) < 0) {
    /*
     * 超时基于单调时钟，不受 RTC 校时影响
     */
}
```

---

## 5.16 时间校准策略

### 直接跳变

适用于：

- 首次上电；
- 时间无效；
- 用户明确设置；
- 设备尚未开始记录关键日志。

```
当前时间无效 --> 直接设置 RTC
当前时间有效且偏差很大 --> 根据策略跳变或平滑
```

### 立即校正

如果偏差小于阈值，例如 ±2 秒，可直接修改时间。

### 平滑校正

设当前时间偏差为：

Δt=tref−tlocalΔt=tref​−tlocal​

可以通过调整软件时间映射：

tcorrected=tlocal+αΔttcorrected​=tlocal​+αΔt

其中 0<α<10<α<1。

也可以通过临时修正 RTC 频率：

fadjusted=frtc(1+δ)fadjusted​=frtc​(1+δ)

适用于：

- 日志顺序不能回拨；
- 工业控制事件时间必须连续；
- 网络校时频繁发生。

### 频率校准

长期测量 RTC 偏差：

ppm=ΔtT×106ppm=TΔt​×106

例如设备运行 7 天，比标准时间慢 3.024 秒：

ppm=3.024604800×106=5 ppmppm=6048003.024​×106=5 ppm

校准方法：

- RTC 校准寄存器；
- 插入/删除脉冲；
- 软件时间补偿；
- 温度补偿表；
- 外部高精度 RTC 替换。

---

# 6. 性能量化分析

## 6.1 参考测试平台

以下数据采用典型工业 MCU 作为参考模型：

- Cortex-M4F，主频 80 MHz；
- 512 KB Flash；
- 128 KB SRAM；
- 外部 32.768 kHz LSE；
- RTC 1 Hz 日历模式；
- 3.0 V 供电；
- -20 ℃ 至 +70 ℃；
- GCC `-O2`；
- 无 RTOS 中断竞争条件。

不同芯片的寄存器访问时间、功耗和同步延迟会有明显差异，实际项目必须复测。

---

## 6.2 内存开销

|模块|Flash|RAM|说明|
|---|---|---|---|
|基础 RTC 驱动|1.5~4 KB|100~300 B|取决于 HAL/LL|
|日历转换|1~3 KB|32~128 B|常数时间算法更大|
|时间服务|2~6 KB|200~800 B|含质量、校时状态|
|闹钟管理|0.5~2 KB|64~256 B|取决于闹钟数量|
|CRC/备份记录|0.5~2 KB|32~128 B|取决于算法|
|格式化输出|1~8 KB|128~1024 B|`printf` 可能显著增加体积|

**工程建议：**

- 驱动层不要依赖 `printf`；
- 时间转换和格式化分层；
- 使用静态缓冲，避免运行时动态内存；
- 不要在中断中使用复杂格式化库。

---

## 6.3 时间开销

参考测量值：

|操作|典型时间|
|---|---|
|读取硬件秒计数器|0.5~2 µs|
|读取日历寄存器|1~10 µs|
|BCD 转换|0.1~0.5 µs|
|Epoch 转日历，循环算法|1~8 µs|
|Epoch 转日历，常数时间算法|0.5~2 µs|
|校验备份记录 CRC32|2~20 µs|
|设置 RTC 时间|100 µs~数 ms|
|等待同步标志|0~数 ms|
|外部 I²C RTC 读取|0.3~2 ms|
|NTP 校时|10 ms~数秒|

主要因素：

- RTC 异步同步时间；
- 总线频率；
- HAL 层抽象；
- 是否等待影子寄存器同步；
- 是否包含锁与临界区；
- 是否启用 RTOS。

---

## 6.4 功耗分析

典型值：

|RTC 方案|RTC 域电流|
|---|---|
|LSE + MCU RTC|0.5~2 µA|
|LSI + MCU RTC|0.5~5 µA|
|低功耗外部 RTC|0.1~1 µA|
|温补型外部 RTC|1~3 µA|
|MCU Stop + RTC|2~20 µA，取决于 MCU|
|MCU Standby + RTC|0.5~5 µA，取决于芯片|

备份电池寿命估算：

Thour=CbatteryIRTC+IleakThour​=IRTC​+Ileak​Cbattery​​

例如：

- 电池容量：220 mAh；
- RTC 电流：1.0 µA；
- 板级漏电：0.5 µA。

T=220000μAh1.5μA≈146667h≈16.7 年T=1.5μA220000μAh​≈146667h≈16.7 年

但实际寿命还受：

- 自放电；
- 温度；
- 电池有效容量；
- 电源切换；
- 外部漏电；
- 电池内阻；
- 主电源断续工作。

---

## 6.5 时间误差预算

可以建立误差预算：

Etotal=Ecrystal+Etemperature+Eaging+Eload+Esoftware+EsyncEtotal​=Ecrystal​+Etemperature​+Eaging​+Eload​+Esoftware​+Esync​

例如：

|误差源|预算|
|---|---|
|晶振初始误差|±20 ppm|
|温度漂移|±10 ppm|
|老化|±3 ppm|
|负载电容|±5 ppm|
|软件校时残差|±2 ppm|
|总体保守预算|±40 ppm 左右|

不能简单做平方和，除非各误差近似独立且统计特征明确。工业设计通常采用：

- 最坏情况线性叠加；
- 统计场景下使用 RSS；
- 对关键指标保留 20%~50% 余量。

---

## 6.6 性能瓶颈与优化手段

### 瓶颈一：外部 RTC 总线访问过慢

优化：

- 周期性读取后缓存；
- 只在秒边界或任务调度时访问；
- 使用单调时间在两次 RTC 读取之间推算；
- 采用中断或时间戳锁存；
- 降低不必要的 I²C 事务。

### 瓶颈二：日历转换频繁占用 CPU

优化：

- 内部统一保存 epoch；
- 使用常数时间转换算法；
- 只在日志输出和 UI 显示时转换；
- 对相同秒值做缓存。

### 瓶颈三：频繁写 RTC 或备份寄存器

优化：

- 只有时间变化超过阈值才写入；
- 不要每秒写 Flash；
- 备份寄存器只保存启动恢复信息；
- 使用磨损均衡和事务记录。

### 瓶颈四：时间校时导致系统事件异常

优化：

- 业务超时使用单调时钟；
- 校时采用平滑调整；
- 日志记录校时事件；
- 为时间增加质量和来源字段。

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要掉电后保持时间？
|
+-- 否 --> 是否需要高精度短周期定时？
|           |
|           +-- 是 --> 使用通用定时器/LPTIM
|           |
|           +-- 否 --> 使用 RTOS Tick/软件定时器
|
+-- 是 --> 目标长期误差是否小于 ±100 ppm？
            |
            +-- 否 --> 可选 LSI/IRC RTC
            |
            +-- 是 --> 是否有外部 32.768 kHz 晶振空间？
                        |
                        +-- 是 --> 使用 MCU RTC + LSE
                        |
                        +-- 否 --> 是否允许外部 RTC 芯片？
                                    |
                                    +-- 是 --> 使用外部 RTC
                                    |
                                    +-- 否 --> 通过网络/GNSS 周期校时

是否需要低功耗唤醒？
|
+-- 是 --> MCU RTC Alarm/Wakeup Timer 或外部 RTC INT
|
+-- 否 --> RTC 只用于绝对时间和日志

是否要求多设备严格同步？
|
+-- 是 --> NTP/PTP/GNSS/PPS + 本地 RTC
|
+-- 否 --> 本地 RTC + 周期网络校时

时间是否可能被回拨？
|
+-- 是 --> 所有业务超时使用单调时钟
|
+-- 否 --> 可使用 UTC 作为日志时间，但仍建议保留单调时间
```

---

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|普通 MCU 产品，断电保持，误差每天数秒可接受|LSE + MCU RTC|成本、功耗和精度平衡|
|低成本玩具或简单家电|LSI + MCU RTC|无外部晶振，成本最低|
|工业数据记录器|LSE + RTC + 网络校时|本地保持与周期修正兼顾|
|超低功耗无线传感器|低功耗外部 RTC 或 LSE RTC|低静态功耗，支持周期唤醒|
|需要温度补偿|DS3231 等 TCXO RTC|频率稳定性高|
|需要微秒级事件对时|GNSS/PPS + RTC 时间戳|PPS 提供高精度边沿|
|多控制器协同|PTP/NTP + 本地 RTC|支持系统级时间一致性|
|电表、燃气表|RTC + 备份电源 + 防篡改|需要长期稳定和掉电记录|
|低功耗门锁|RTC Alarm + 外部唤醒|支持预约唤醒和低功耗|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：内部统一使用 UTC 或 Epoch

不要在业务层到处传递：

```
year, month, day, hour, minute, second
```

建议业务层使用：

```
uint64_t epoch_sec;
uint32_t subsec_us;
```

日历结构仅用于：

- 人机界面；
- 协议编码；
- 配置输入；
- 日志格式化。

### 原则二：绝对时间与单调时间分离

- 绝对时间：可能跳变；
- 单调时间：不允许回拨；
- 业务超时：只使用单调时间；
- 日志记录：同时写入两者。

### 原则三：RTC 初始化必须幂等

多次调用初始化函数不应破坏有效时间。

### 原则四：所有硬件等待必须有超时

包括：

- 晶振启动；
- 寄存器同步；
- 初始化模式进入；
- 外部 RTC 总线通信；
- Alarm 配置；
- 低功耗唤醒确认。

### 原则五：时间有效性必须显式表达

不能用：

```
if (year != 0) {
    valid = true;
}
```

应使用：

- 备份魔术数；
- CRC；
- 时间范围；
- 时钟源状态；
- 复位原因；
- 校时来源。

### 原则六：校时必须可追踪

每次校时应记录：

- 校时前时间；
- 校时后时间；
- 偏差；
- 时间源；
- 校时模式；
- 操作原因；
- 时间质量。

---

## 8.2 选型决策矩阵

评分：1 分最差，5 分最好。

|方案|精度|功耗|成本|软件复杂度|低功耗唤醒|抗主 MCU 复位|
|---|---|---|---|---|---|---|
|LSI + MCU RTC|1|4|5|4|4|4|
|LSE + MCU RTC|4|4|4|4|5|4|
|普通外部 RTC|4|3|3|3|4|5|
|温补 RTC|5|3|2|3|4|5|
|GNSS + RTC|5|1|1|2|1|4|
|NTP + RTC|3|2|3|2|2|4|

---

## 8.3 工业级编码规范

- 所有 RTC 接口返回明确错误码；
- 不在驱动中直接调用业务日志模块；
- 不在 RTC ISR 中调用阻塞 API；
- 不使用未限定范围的 `int` 保存时间戳；
- 不将硬件 BCD 值直接暴露给上层；
- 不依赖结构体默认对齐保存备份寄存器；
- 备份数据必须定义版本和 CRC；
- 时间转换函数必须覆盖边界日期；
- 对 RTC 回绕、Unix 时间溢出进行设计；
- 所有超时使用无符号差值或带符号差值安全处理；
- 时间校正策略必须可配置；
- 低功耗进入前清理闹钟挂起标志；
- 唤醒后必须读取并记录唤醒原因。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：每次启动都重置 RTC

### 错误代码

```
void app_init(void)
{
    rtc_init();
    rtc_set_datetime(&(rtc_datetime_t) {
        .year = 2024,
        .month = 1,
        .day = 1,
        .hour = 0,
        .minute = 0,
        .second = 0
    });
}
```

### 根因分析

没有区分：

- 首次上电；
- 软件复位；
- 看门狗复位；
- 低功耗唤醒；
- 备份域丢失。

### 正确实现

```
void app_rtc_init(void)
{
    rtc_status_t status;

    status = rtc_hw_init_if_needed();

    if (status != RTC_OK) {
        system_set_fault(SYSTEM_FAULT_RTC);
        return;
    }

    if (!rtc_backup_is_valid()) {
        rtc_datetime_t factory_time = {
            .year = 2024U,
            .month = 1U,
            .day = 1U,
            .hour = 0U,
            .minute = 0U,
            .second = 0U,
            .millisecond = 0U
        };

        (void)rtc_hw_write_datetime(&factory_time);
        rtc_backup_mark_valid();
    }
}
```

### 风险影响

- 所有历史日志时间失效；
- 预约任务重复执行；
- 证书、密钥有效期判断错误；
- 设备升级后时间回到出厂时间。

---

## 9.2 错误二：直接读取 RTC 寄存器导致日期和时间不一致

### 错误代码

```
uint8_t hour = RTC_HOUR_REG;
uint8_t minute = RTC_MINUTE_REG;
uint8_t second = RTC_SECOND_REG;
uint8_t day = RTC_DAY_REG;
```

### 根因分析

读取过程中可能发生秒进位：

```
23:59:59
读取 hour/minute
RTC 进位
00:00:00
读取 second/day
```

最终得到非法组合：

```
23:59:00
```

或：

```
23:59:00 + 次日日期
```

### 正确实现

```
rtc_status_t rtc_hw_read_datetime(rtc_datetime_t *dt)
{
    rtc_datetime_t first;
    rtc_datetime_t second;

    if (dt == NULL) {
        return RTC_ERR_PARAM;
    }

    for (uint8_t retry = 0U; retry < 3U; ++retry) {
        if (rtc_hw_read_once(&first) != RTC_OK) {
            return RTC_ERR_HW;
        }

        if (rtc_hw_read_once(&second) != RTC_OK) {
            return RTC_ERR_HW;
        }

        if ((first.year == second.year) &&
            (first.month == second.month) &&
            (first.day == second.day) &&
            (first.hour == second.hour) &&
            (first.minute == second.minute) &&
            (first.second == second.second)) {
            *dt = second;
            return RTC_OK;
        }
    }

    return RTC_ERR_TIMEOUT;
}
```

### 风险影响

- 日志出现跨天错误；
- 计费记录异常；
- 闹钟计算错误；
- 数据库排序混乱。

---

## 9.3 错误三：使用 RTC 作为超时基准

### 错误代码

```
uint64_t deadline = rtc_get_epoch() + 30U;

while (rtc_get_epoch() < deadline) {
    feed_watchdog();
}
```

### 根因分析

RTC 是墙上时间，可能被：

- 用户手动设置；
- NTP 校时；
- GNSS 校时；
- 夏令时转换；
- 外部 RTC 恢复；
- 故障修复逻辑回拨。

### 正确实现

```
bool wait_timeout_ms(uint32_t timeout_ms)
{
    uint32_t start = platform_get_tick_ms();

    while ((uint32_t)(platform_get_tick_ms() - start) < timeout_ms) {
        platform_feed_watchdog();
        platform_idle();
    }

    return true;
}
```

### 风险影响

- 超时循环无限等待；
- 重试间隔异常；
- 状态机卡死；
- 看门狗复位；
- 网络连接流程异常。

---

## 9.4 错误四：忽略 BCD 编码

### 错误代码

```
RTC_HOUR_REG = 23; /* 错误：硬件期望 BCD 0x23 */
```

### 根因分析

RTC 寄存器常使用 BCD 表示：

```
十进制 23 -> BCD 0x23
十进制 19 -> BCD 0x19
```

十进制整数 23 的十六进制表示为 0x17，并不是 BCD 0x23。

### 正确实现

```
RTC_HOUR_REG = rtc_bin_to_bcd(23U);
```

### 风险影响

- 时间显示错误；
- 小于 10 的时间可能正常，大于 15 后出现异常；
- 闹钟匹配失败；
- 非法 BCD 导致硬件行为不确定。

---

## 9.5 错误五：RTC 同步等待无超时

### 错误代码

```
while ((RTC_STATUS_REG & RTC_SYNC_READY) == 0U) {
    /* 永久等待 */
}
```

### 根因分析

如果：

- LSE 未起振；
- RTC 时钟源被关闭；
- 备份域配置错误；
- 低功耗唤醒后同步逻辑异常；
- 时钟源切换失败；

该循环可能永久阻塞。

### 正确实现

```
rtc_status_t rtc_wait_sync(uint32_t timeout_ms)
{
    uint32_t start = platform_get_tick_ms();

    while ((RTC_STATUS_REG & RTC_SYNC_READY) == 0U) {
        if ((uint32_t)(platform_get_tick_ms() - start) >= timeout_ms) {
            return RTC_ERR_TIMEOUT;
        }
    }

    return RTC_OK;
}
```

### 风险影响

- 系统无法启动；
- 看门狗不断复位；
- 现场表现为“偶发死机”；
- 故障无法自动降级。

---

## 9.6 错误六：将本地时间直接存入 RTC

### 错误代码

```
/* 将北京时间直接写入 RTC */
rtc_set_datetime(2024, 6, 1, 8, 0, 0);
```

### 根因分析

本地时间涉及：

- 时区；
- 夏令时；
- 跨地区配置；
- 日志传输；
- 设备迁移。

### 正确实现

```
RTC 内部：保存 UTC
设备配置：保存时区偏移或时区规则
显示层：UTC + 时区转换
日志：UTC + 单调时间
```

### 风险影响

- 跨时区设备迁移后时间错乱；
- 夏令时重复或缺失一个小时；
- 服务器日志难以对齐；
- 多设备数据无法统一排序。

---

# 10. 多机制组合使用方案

## 10.1 推荐时间服务架构

```
+------------------------------------------------------+
|                   应用层                             |
| 日志 / 计费 / 预约任务 / UI / 通信协议                |
+----------------------------+-------------------------+
                             |
                             v
+------------------------------------------------------+
|                   时间服务层                         |
| UTC 时间 / 单调时间 / 时区转换 / 时间质量 / 校时策略  |
+--------------+-------------------+-------------------+
               |                   |
               v                   v
+----------------------+   +--------------------------+
| 本地 RTC 驱动         |   | 单调时钟驱动              |
| LSE/LSI/外部 RTC      |   | SysTick/LPTIM/DWT         |
+----------+-----------+   +--------------------------+
           |
           v
+------------------------------------------------------+
| 校时源                                                |
| NTP/SNTP / GNSS/PPS / 用户设置 / 工厂时间             |
+------------------------------------------------------+
```

---

## 10.2 时间服务核心框架

```
#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint64_t utc_sec;
    uint32_t utc_us;
    uint64_t mono_us;
    rtc_time_quality_t quality;
    bool valid;
} system_time_t;

typedef struct {
    uint64_t base_utc_us;
    uint64_t base_mono_us;
    int64_t  slew_offset_us;
    rtc_time_quality_t quality;
    bool initialized;
} time_service_ctx_t;

static time_service_ctx_t g_time_service;

void time_service_init(void)
{
    rtc_timestamp_t rtc_ts;

    g_time_service.initialized = false;
    g_time_service.slew_offset_us = 0;

    if (rtc_get_timestamp(&rtc_ts) == RTC_OK && rtc_ts.valid) {
        g_time_service.base_utc_us =
            rtc_ts.unix_sec * 1000000ULL + rtc_ts.subsec_us;
        g_time_service.base_mono_us = platform_get_monotonic_us();
        g_time_service.quality = RTC_TIME_QUALITY_BACKUP;
        g_time_service.initialized = true;
    }
}

bool time_service_get(system_time_t *out)
{
    uint64_t mono_us;
    uint64_t elapsed_us;
    int64_t utc_us;

    if ((out == NULL) || !g_time_service.initialized) {
        return false;
    }

    mono_us = platform_get_monotonic_us();
    elapsed_us = mono_us - g_time_service.base_mono_us;

    utc_us = (int64_t)(g_time_service.base_utc_us + elapsed_us);
    utc_us += g_time_service.slew_offset_us;

    if (utc_us < 0) {
        return false;
    }

    out->utc_sec = (uint64_t)utc_us / 1000000ULL;
    out->utc_us = (uint32_t)((uint64_t)utc_us % 1000000ULL);
    out->mono_us = mono_us;
    out->quality = g_time_service.quality;
    out->valid = true;

    return true;
}
```

这个框架的特点：

- RTC 不需要每次业务读取；
- 业务读取使用单调时间推算；
- 校时可以更新基准；
- 支持平滑修正；
- 避免外部 RTC 总线频繁访问；
- 统一向上层提供时间质量。

---

## 10.3 校时平滑调整

```
#define TIME_SLEW_STEP_US 1000LL

void time_service_apply_offset(int64_t offset_us,
                               rtc_time_quality_t quality)
{
    if (!g_time_service.initialized) {
        return;
    }

    /*
     * 偏差较大时，直接重置基准；
     * 偏差较小时采用逐步修正，避免业务时间跳变。
     */
    if ((offset_us > 5000000LL) || (offset_us < -5000000LL)) {
        system_time_t now;
        uint64_t current_mono;

        if (!time_service_get(&now)) {
            return;
        }

        current_mono = now.mono_us;

        g_time_service.base_utc_us =
            now.utc_sec * 1000000ULL + now.utc_us
            + offset_us;
        g_time_service.base_mono_us = current_mono;
        g_time_service.slew_offset_us = 0;
    } else {
        g_time_service.slew_offset_us += offset_us;
    }

    g_time_service.quality = quality;
}
```

实际产品中应进一步处理：

- 重复校时；
- 平滑修正速度；
- 系统重启后的校时状态；
- 校时失败退避；
- RTC 硬件同步；
- 负偏差和日志排序关系。

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业数据记录器

### 需求

- 断电后保持时间；
- 记录传感器事件；
- 每 10 秒采样；
- 每天 02:00 自动导出；
- 网络恢复后 NTP 校时；
- 日志不能因为校时回拨而破坏顺序；
- 时间误差要求小于 ±2 秒/天。

### 架构设计

```
LSE 32.768 kHz
      |
      v
MCU RTC
      |
      +-- 每天 02:00 Alarm
      +-- 备份域保持
      +-- UTC 秒计数
      |
      v
时间服务
      |
      +-- UTC 时间
      +-- 单调时间
      +-- NTP 校时
      +-- 时间质量
      |
      v
日志服务
      |
      +-- UTC 时间戳
      +-- 单调序号
      +-- 校时事件
```

### 日志结构

```
typedef struct {
    uint64_t utc_sec;
    uint32_t utc_us;
    uint64_t mono_us;
    uint32_t sequence;
    uint16_t event_id;
    int32_t  value;
    uint8_t  time_quality;
    uint8_t  reserved[3];
    uint32_t crc32;
} log_record_t;
```

### 设计要点

- 每条日志同时写 UTC 和单调时间；
- `sequence` 用于处理 UTC 回拨；
- 网络不可用时继续使用本地 RTC；
- NTP 偏差小于阈值时进行平滑校正；
- 每次校时生成特殊日志事件；
- 日志存储采用追加写入，避免时间作为唯一排序键。

---

## 11.2 案例二：超低功耗无线传感器

### 需求

- 设备 99% 时间处于 Stop/Standby；
- 每 5 分钟唤醒采样；
- 每小时无线发送；
- RTC 域功耗小于 2 µA；
- 无网络时连续运行 6 个月；
- 支持外部磁簧事件时间戳。

### 架构设计

```
纽扣电池/主电池
      |
      v
低功耗 RTC 域
      |
      +-- RTC Wakeup Timer：5 分钟
      +-- GPIO Timestamp：外部事件
      |
      v
MCU 唤醒
      |
      +-- 读取 RTC
      +-- 读取传感器
      +-- 记录事件
      +-- 必要时发送
      +-- 重新配置唤醒
      |
      v
进入低功耗模式
```

### 低功耗注意事项

- 进入低功耗前关闭不必要的 RTC 中断；
- 清除 Alarm/Wakeup 挂起标志；
- 确认唤醒源只保留必要通道；
- 记录睡眠前后的 RTC 值；
- 计算实际唤醒间隔，不假设绝对精确；
- 检查主电源与 VBAT 的隔离；
- 评估 RTC 唤醒误差是否会累积。

### 周期漂移

若 RTC 误差为 20 ppm，5 分钟周期误差约为：

300×20×10−6=6 ms300×20×10−6=6 ms

一天约 288 次周期，若完全不校正，理论累计误差：

86400×20×10−6=1.728 s86400×20×10−6=1.728 s

对于低功耗采样通常可接受；对于严格定时上报，则需要网络或 GNSS 周期校准。

---

## 11.3 案例三：电能计量设备

### 需求

- 计费时间必须可审计；
- 断电时记录掉电时刻；
- 需要防止用户回拨时间；
- 支持远程校时；
- 支持夏令时配置；
- 时间误差要求小于 1 分钟/月。

### 架构设计

```
高可靠 RTC/温补 RTC
      |
      +-- 独立 VBAT
      +-- 备份寄存器
      +-- 掉电时间戳
      |
      v
安全时间服务
      |
      +-- UTC 内部时间
      +-- 本地时区显示
      +-- 校时权限校验
      +-- 时间回拨检测
      +-- 校时审计记录
      |
      v
计量日志/计费模块
```

### 防回拨策略

维护历史最大可信时间：

```
typedef struct {
    uint64_t last_trusted_utc;
    uint64_t max_seen_utc;
    uint32_t crc32;
} anti_rollback_record_t;
```

启动或校时后：

```
bool time_is_rollback(uint64_t candidate_utc,
                      uint64_t max_seen_utc)
{
    /*
     * 允许极小范围的硬件读取抖动，
     * 但禁止显著回拨。
     */
    return candidate_utc + 2ULL < max_seen_utc;
}
```

实际安全产品还需要：

- 安全存储；
- 签名校时命令；
- 权限分级；
- 校时次数和来源限制；
- 可信时间源；
- 防止备份电池拔除绕过检测。

---

# 12. 高频问题深度答疑

## 12.1 为什么 RTC 不能替代通用定时器？

RTC 通常以 1 Hz 或低频时钟工作，分辨率和中断响应有限。通用定时器可以运行在几十 MHz 甚至更高频率下，适合：

- PWM；
- 输入捕获；
- 微秒级超时；
- 电机控制；
- 高速协议时序。

RTC 适合保存时间和低功耗唤醒，不适合高频控制。

---

## 12.2 RTC 使用 LSI 会有什么问题？

LSI 的问题不是“不能工作”，而是精度和稳定性通常不足。

假设 LSI 误差为 1%，一天误差：

86400×0.01=864 s86400×0.01=864 s

即 **14.4 分钟/天**。

如果产品只要求：

- 看门狗；
- 大约每小时唤醒；
- 时间仅用于粗粒度状态；

LSI 可以接受。

如果用于：

- 计费；
- 数据记录；
- 证书有效期；
- 工业日志；
- 多设备时间对齐；

应选择 LSE 或外部 RTC，并配合校时。

---

## 12.3 为什么 RTC 读时间时经常要求“先读时间再读日期”？

因为 RTC 日历寄存器跨越异步时钟域。芯片通常通过影子寄存器将当前时间锁存给 CPU。读取时间可能触发锁存，读取日期可能解除锁存或确认该组数据。

如果顺序错误，可能得到：

- 时间来自上一秒；
- 日期来自下一天；
- 日期寄存器尚未同步；
- 亚秒和秒字段不对应。

必须遵守芯片 Reference Manual 的寄存器访问顺序，而不是依据寄存器名称猜测。

---

## 12.4 RTC 校时应该直接跳变还是平滑调整？

取决于业务。

直接跳变适用于：

- 首次上电；
- 时间无效；
- 用户主动修改；
- 设备尚未产生关键日志。

平滑调整适用于：

- 在线 NTP 校时；
- 持续运行的工业设备；
- 不能接受日志时间回退；
- 需要维持事件顺序。

如果偏差很大，强行平滑可能需要很长时间。通常采用：

```
偏差 > 5 秒：直接跳变或进入特殊校时态
偏差 10 ms~5 秒：平滑调整
偏差 < 10 ms：忽略或微调
```

阈值应根据业务定义，而不是固定照搬。

---

## 12.5 夏令时应该写入 RTC 吗？

一般不建议。

推荐：

```
RTC：UTC
应用配置：时区规则
显示层：UTC -> Local Time
日志：UTC
```

夏令时是显示和规则解释问题，不是底层硬件计时问题。

如果直接把夏令时本地时间写入 RTC：

- 时间会跳变；
- 一小时可能重复；
- 一小时可能不存在；
- 跨地区部署复杂；
- 多设备日志难以对齐。

---

## 12.6 RTC 能否保证设备重启后时间一定正确？

不能。

RTC 只能保证在以下条件满足时继续计时：

- 备份电源正常；
- RTC 时钟源正常；
- 备份域未被复位；
- 晶振未停振；
- 配置未损坏；
- 设备没有被恶意改时；
- 长期漂移在可接受范围内。

所以工业系统应设计：

- 时间有效标记；
- 时钟源故障检测；
- 备份域 CRC；
- 网络/GNSS 校时；
- 时间质量等级；
- 异常日志；
- 故障降级策略。

---

## 12.7 32 位 Unix 时间戳是否足够？

如果使用传统 Unix 时间戳：

```
uint32_t timestamp;
```

有符号 32 位 Unix 时间在 2038 年存在溢出风险。即使使用无符号 32 位，也将在 2106 年附近溢出。

建议：

- 内部使用 `uint64_t`；
- 协议层根据兼容性使用 32 位；
- 明确 Epoch；
- 对外部时间戳做范围检查；
- 对差值计算使用安全的有符号判断。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **RTC 是绝对时间源，不是通用高精度定时器。**
2. **LSE 是 MCU RTC 的通用工业级选择，LSI 适合低成本和低精度场景。**
3. **RTC 通常处于独立备份域，主 MCU 复位不应重置有效时间。**
4. **跨异步时钟域读写必须遵守同步、锁存和寄存器访问顺序。**
5. **RTC 日历寄存器可能使用 BCD，不能直接当作普通二进制。**
6. **时间服务必须分离 UTC 墙上时间和单调时间。**
7. **业务超时、重试、状态机必须使用单调时钟。**
8. **校时策略必须区分直接跳变、立即校正和平滑校正。**
9. **RTC 误差必须使用 ppm 和时间误差公式进行量化。**
10. **时间有效性、时间来源和时间质量必须显式建模。**
11. **备份电源寿命必须同时考虑 RTC 电流和板级漏电。**
12. **日志系统不应只使用 UTC 作为唯一排序依据，应同时保存单调时间或序列号。**

## 13.2 性能排序

### 时间精度排序

```
GNSS/PPS > 温补 RTC > 高品质 LSE > 普通 LSE > LSI
```

### 功耗排序

```
低功耗外部 RTC ≈ LSE RTC < 普通外部 RTC < 温补 RTC < GNSS
```

### 成本排序

```
LSI < LSE + MCU RTC < 普通外部 RTC < 温补 RTC < GNSS/PPS
```

### 软件复杂度排序

```
MCU RTC HAL < MCU RTC + 时间服务 < 外部 RTC < 多源校时系统
```

## 13.3 通用选型结论

- **通用工业 MCU：LSE + 内置 RTC + VBAT + 周期校时。**
- **低成本低精度产品：LSI + 内置 RTC。**
- **超低功耗产品：低功耗外部 RTC 或低功耗 MCU RTC。**
- **高精度产品：温补 RTC，必要时增加 GNSS/PPS。**
- **联网产品：本地 RTC 用于离线保持，NTP 用于周期校准。**
- **严格实时控制：RTC 不参与控制闭环，使用通用定时器或硬件时间戳。**

---

# 14. 快速参考速查表

## 14.1 场景选型表

|需求|推荐|
|---|---|
|只需要系统调度|SysTick/RTOS Tick|
|需要微秒级周期控制|通用定时器|
|断电保持日历时间|RTC + VBAT|
|每天固定时间唤醒|RTC Alarm|
|周期性低功耗唤醒|RTC Wakeup Timer|
|普通工业时间保持|LSE + MCU RTC|
|长期高精度保持|温补外部 RTC|
|多设备统一时间|NTP/PTP/GNSS|
|严禁时间回拨影响超时|单调时钟|
|需要可审计日志|UTC + 单调时间 + 序列号|

## 14.2 特性对比表

|项目|RTC|通用定时器|RTOS Tick|外部 RTC|
|---|---|---|---|---|
|掉电保持|是|否|否|是|
|绝对日期时间|是|否|否|是|
|微秒级精度|通常否|是|否|通常否|
|低功耗运行|是|视芯片|通常否|是|
|低功耗唤醒|是|视芯片|通常否|是|
|受校时影响|是|否|否|是|
|适合业务超时|否|是|是|否|
|适合日志时间|是|否|否|是|
|硬件复杂度|低|中|低|中|
|推荐内部表示|Epoch/UTC|Tick/Cycle|Tick|Epoch/UTC|

## 14.3 关键公式

### RTC 输出频率

fRTC=fsource(PREDIVA+1)(PREDIVS+1)fRTC​=(PREDIVA​+1)(PREDIVS​+1)fsource​​

### 时间误差

Δt=t×ppm×10−6Δt=t×ppm×10−6

### ppm 估算

ppm=ΔtT×106ppm=TΔt​×106

### 备份电池寿命

Thour=CbatteryIRTC+IleakThour​=IRTC​+Ileak​Cbattery​​

### 32.768 kHz 生成 1 Hz

32768=21532768=215

---

# 15. 学习效果自检

## 15.1 原理检查

- [ ]  能解释为什么 32.768 kHz 适合 RTC。
- [ ]  能推导 RTC 预分频参数。
- [ ]  能解释 LSE 与 LSI 的误差差异。
- [ ]  能说明 RTC 为什么需要备份电源。
- [ ]  能解释 RTC 与主时钟域之间的同步问题。
- [ ]  能说明为什么部分 MCU 要求先读时间再读日期。

## 15.2 驱动实现检查

- [ ]  能够实现 RTC 初始化且不破坏已有时间。
- [ ]  能够实现 RTC 时间读写接口。
- [ ]  能够处理 BCD 编码。
- [ ]  能够实现日期合法性校验。
- [ ]  能够实现闰年判断。
- [ ]  能够配置 Alarm 和 Wakeup Timer。
- [ ]  能够实现 RTC 时间戳捕获。
- [ ]  所有硬件等待均有超时和错误返回。

## 15.3 系统架构检查

- [ ]  能区分 UTC、本地时间和单调时间。
- [ ]  业务超时不会依赖 RTC。
- [ ]  校时不会破坏日志顺序。
- [ ]  时间质量和来源可追踪。
- [ ]  备份域状态可验证。
- [ ]  掉电、复位、唤醒和时钟故障均有处理策略。

## 15.4 性能与可靠性检查

- [ ]  能根据 ppm 计算每天、每月和每年的误差。
- [ ]  能测量 RTC 真实频率误差。
- [ ]  能评估 PCB 漏电对电池寿命的影响。
- [ ]  能验证晶振在全温范围内正常起振。
- [ ]  能进行长时间漂移测试。
- [ ]  能验证跨秒、跨分、跨天、跨月、跨年边界。
- [ ]  能验证网络校时前后业务超时行为。
- [ ]  能验证备份域复位和电池拔除故障。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：寄存器级 RTC 初始化

要求：

- 配置 LSE；
- 配置 RTC 时钟源；
- 配置异步和同步预分频；
- 等待同步完成；
- 设置初始时间；
- 读取并打印时间；
- 所有等待带超时。

验收指标：

- 首次上电时间初始化成功；
- 软件复位后时间不被重置；
- LSE 起振失败时系统能够报错并降级。

---

### 任务二：日历和 Epoch 转换

要求：

- 实现 `datetime -> epoch`；
- 实现 `epoch -> datetime`；
- 覆盖 2000~2099；
- 验证闰年；
- 验证跨月、跨年和跨世纪边界。

测试用例：

```
2000-02-29 23:59:59
2000-03-01 00:00:00
2024-02-29 12:00:00
2100-02-28 23:59:59
2100-03-01 00:00:00
```

---

### 任务三：RTC Alarm 低功耗唤醒

要求：

- 配置每天固定时间唤醒；
- 进入 Stop/Standby；
- 唤醒后读取复位和唤醒原因；
- 清除挂起标志；
- 防止重复进入中断；
- 统计实际唤醒时间误差。

验收指标：

- 连续运行 7 天；
- Alarm 不重复触发；
- 唤醒误差在目标范围内；
- 低功耗电流满足设计要求。

---

### 任务四：RTC + 单调时钟时间服务

要求：

- 提供 UTC 接口；
- 提供单调微秒接口；
- 支持时间质量；
- 支持 NTP 模拟校时；
- 设计大偏差跳变和小偏差平滑策略；
- 日志同时记录 UTC、单调时间和序列号。

验收指标：

- 校时不会导致任务超时异常；
- UTC 允许跳变；
- 单调时间严格递增；
- 日志顺序在时间回拨后仍然可恢复。

---

### 任务五：RTC 长期精度校准

要求：

- 使用高精度频率源或 GNSS PPS；
- 运行至少 7 天；
- 测量 RTC 频率偏差；
- 计算 ppm；
- 使用校准寄存器或软件补偿；
- 比较校准前后误差。

测试公式：

ppm=Trtc−TrefTref×106ppm=Tref​Trtc​−Tref​​×106

验收指标：

- 得到设备实测 ppm；
- 温度变化下记录 ppm 曲线；
- 校准前后误差有明确量化收益。

---

## 16.2 性能测试方法

### 测试一：频率精度测试

设备输出：

- RTC 1 Hz；
- 或每秒 GPIO 翻转。

使用频率计或逻辑分析仪测量：

```
实际周期 = 1.000xxx s
频率误差 = (实际频率 - 1 Hz) / 1 Hz × 10^6 ppm
```

### 测试二：温漂测试

温度点：

```
-40 ℃、-20 ℃、0 ℃、25 ℃、50 ℃、70 ℃、85 ℃
```

每个温度点稳定后测量至少 30 分钟，建立：

```
温度 -> ppm
```

### 测试三：掉电保持测试

测试步骤：

1. 设置准确时间；
2. 关闭主电源；
3. 保持 24 小时、7 天、30 天；
4. 恢复主电源；
5. 读取 RTC；
6. 与参考时钟比较；
7. 检查备份域和时间有效标志。

### 测试四：边界一致性测试

重点测试：

- 23:59:59 -> 00:00:00；
- 月末 -> 月初；
- 2 月 28 日 -> 2 月 29 日；
- 12 月 31 日 -> 1 月 1 日；
- 软件复位；
- 看门狗复位；
- Stop 唤醒；
- RTC 时钟源故障；
- 备份域复位。

### 测试五：校时鲁棒性测试

注入以下情况：

- 前拨 1 秒；
- 回拨 1 秒；
- 前拨 1 小时；
- 回拨 1 天；
- 重复校时；
- 校时过程中进入低功耗；
- 校时源突然丢失。

验证：

- 业务超时；
- 日志排序；
- 闹钟任务；
- 证书有效期；
- 数据库同步；
- 故障恢复。

---

## 16.3 进阶学习方向

### 方向一：高精度时间同步

- NTP/SNTP；
- PTP/IEEE 1588；
- GNSS/PPS；
- 硬件时间戳；
- 时钟伺服算法；
- PI 控制器校频；
- SyncE。

### 方向二：高可靠 RTC 设计

- 温补晶振；
- TCXO/OCXO；
- 外部 RTC 冗余；
- 时钟源故障切换；
- 备份电源监控；
- 时间完整性校验；
- 安全时间源。

### 方向三：低功耗 RTC 架构

- Stop/Standby 唤醒；
- RTC Alarm 与外部中断协同；
- LPTIM；
- 超低功耗外部 RTC；
- 电池寿命建模；
- PCB 漏电排查；
- VBAT 防反充设计。

### 方向四：时间安全

- 安全启动中的可信时间；
- 证书有效期判断；
- 防时间回拨；
- 安全日志时间戳；
- 时间源认证；
- Secure Element 时间计数；
- 防篡改备份域。

### 方向五：Linux 与分布式系统时间

- `CLOCK_REALTIME` 与 `CLOCK_MONOTONIC`；
- Linux RTC class；
- `/dev/rtcX`；
- `hwclock`；
- `chrony`；
- PTP Hardware Clock；
- 多设备日志对齐；
- 边缘网关时间同步架构。

**本课最终应形成的工程能力是：不仅能够“把 RTC 配起来”，还能够设计一个在掉电、复位、低功耗、网络校时、时间回拨和长期漂移条件下仍然可预测、可验证、可审计的工业级时间系统。**