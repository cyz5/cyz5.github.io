

> 本课聚焦 **LPTIM（Low-Power Timer）** 在 Sleep/Stop/Standby 邻近场景中的工作原理、时钟选择、周期唤醒、外部脉冲计数、输入捕获、超时保护、RTOS Tickless 协同和测量验证。示例采用 Cortex-M + STM32 风格伪 HAL/寄存器接口，具体寄存器位、时钟保持能力和唤醒行为必须以目标 MCU Reference Manual 与 Datasheet 为准。

## 1. 学习目标

### 理解

- 理解 LPTIM 的定位：**在 CPU 主时钟停止时，使用低速或外部时钟继续计数、比较、捕获和唤醒**。
- 理解 LPTIM 与通用定时器、RTC、SysTick 的时钟域、精度、功耗和功能差异。
- 理解异步时钟、同步器、预分频器、ARR/ compare、Update/Match 事件和唤醒链路。
- 理解 LPTIM 的核心限制：计数位宽、时钟误差、同步延迟、重装载时序和 Stop 模式保持能力。

### 掌握

- 配置 LPTIM 周期唤醒、单次超时、外部脉冲计数和输入捕获。
- 正确处理启动、停止、ARR 写入、标志清除、EXTI/NVIC/PWR 唤醒链路。
- 在 RTOS Tickless Idle 中使用 LPTIM 代替 SysTick，并完成 Tick 补偿。
- 设计 LPTIM 超时、溢出、时钟失效和唤醒配置失败的降级路径。

### 精通

- 分析 LPTIM 跨时钟域同步、预加载寄存器和事件传播的底层时序。
- 量化定时误差、唤醒延迟、计数分辨率、功耗和溢出周期。
- 处理外部脉冲频率变化、毛刺、计数溢出、Stop 唤醒恢复和并发访问。
- 设计多源唤醒下 LPTIM 与 RTC、GPIO、看门狗的协同策略。

### 能够设计

- 面向工业设备的 LPTIM 驱动与 HAL 接口；
- 支持周期唤醒、绝对截止时间、外部计数和捕获测量的统一时基服务；
- RTOS Tickless + LPTIM + Stop 的低功耗时间管理框架；
- 可测量、可回归、可故障降级的 LPTIM 工业级方案。

## 2. 前置要求

### 知识要求

- Cortex-M 中断、NVIC、`WFI/WFE`、Stop 和唤醒源配置；
- RCC 时钟树、LSE/LSI、外部时钟输入和时钟门控；
- GPIO 复用、EXTI、RTC、SysTick、DMA 和看门狗；
- RTOS Tickless Idle、时间补偿、临界区和中断安全；
- 定时器计数、输入捕获、边沿检测和数字滤波。

### 技能要求

- 能阅读目标 MCU 的 LPTIM、RCC、PWR、GPIO 章节；
- 能使用示波器、逻辑分析仪和功耗分析仪验证波形；
- 能编写中断安全的计时器驱动和超时服务；
- 能定位 LPTIM 不计数、周期偏差、唤醒风暴和计数溢出问题。

## 3. 技术概述

### 3.1 LPTIM 的系统定位

典型低功耗计时链路：

```
LSE/LSI/外部脉冲
        ↓
LPTIM 预分频器与同步器
        ↓
计数器 CNT
        ↓
ARR/比较寄存器/捕获寄存器
        ↓
事件标志与中断/EXTI
        ↓
PWR 唤醒逻辑
        ↓
CPU 唤醒、ISR 或任务调度
```

LPTIM 常见功能：

1. **周期唤醒**：ARR Match 或 Update 事件。
2. **单次超时**：启动后计数到目标值自动产生事件。
3. **外部脉冲计数**：在 CPU 停止期间累计脉冲。
4. **输入捕获**：测量外部周期、脉宽或事件间隔。
5. **低功耗 PWM/输出比较**：部分 MCU 支持在 Stop 附近继续输出。
6. **编码器/触发计数**：具体能力取决于芯片型号。

### 3.2 与其他时基的区别

- **SysTick**：依赖 CPU 主时钟，适合 Run/Sleep，不适合深度 Stop。
- **通用定时器**：功能丰富、分辨率高，但通常需要高速时钟，功耗较高。
- **RTC**：适合绝对时间、日历和超长周期，分辨率与配置灵活性有限。
- **LPTIM**：适合 Stop 中的相对定时、外部低频计数和较低功耗时基。

## 4. 核心特性横向对比

典型量级如下，实际能力必须以目标 MCU 数据手册为准。

|维度|SysTick|通用 TIM|RTC|LPTIM|
|---|---|---|---|---|
|Stop 中继续运行|通常否|通常否/有限|是|通常是|
|典型时钟|HCLK|APB/外部高速时钟|LSE/LSI|LSE/LSI/外部时钟|
|分辨率|高|很高|1 Hz~子秒|由时钟源决定|
|长周期能力|软件扩展|软件扩展|很强|受计数位宽限制|
|外部脉冲计数|否|是|通常否|常见支持|
|功耗|较高|中~高|极低|低|
|配置复杂度|低|中|中~高|中~高|
|典型用途|RTOS Tick|PWM/捕获/精密控制|日历/绝对时间|Stop 唤醒/低频计数|

以 32.768 kHz 时钟、16 位计数器为例：

Ttick=132768=30.5176 μsTtick​=327681​=30.5176 μs

无预分频最大计数周期近似为：

Tmax=6553632768=2 sTmax​=3276865536​=2 s

若预分频为 8，最大周期约为 **16 s**，但分辨率也从 30.5 μs 降至 244.1 μs。

## 5. 底层原理与功能特性深度解析

### 5.1 时钟源与跨时钟域同步

LPTIM 可能运行于：

- LSE：32.768 kHz，精度高、温漂较小；
- LSI：低成本但频率误差和温漂通常较大；
- 外部低频时钟：适合外部传感器或编码器；
- 内部低功耗时钟：具体误差需查规格；
- 外部脉冲：用于事件计数，但需满足输入频率和脉宽约束。

当 CPU 使用 HCLK，而 LPTIM 使用 LSE 时，寄存器访问和计数器运行跨越两个时钟域。硬件通常提供同步机制，但软件仍需：

1. 等待配置写入同步完成；
2. 检查计数器启动状态；
3. 不在刚写 ARR 后立即假定新值已经生效；
4. 对 Stop 唤醒后的第一拍计数误差进行实测。

### 5.2 周期唤醒配置

以下为通用伪接口：

```
typedef enum {
    LPTIM_OK = 0,
    LPTIM_ERR_ARG,
    LPTIM_ERR_CLOCK,
    LPTIM_ERR_RANGE,
    LPTIM_ERR_SYNC,
    LPTIM_ERR_BUSY,
} lptim_status_t;

typedef struct {
    uint32_t source_hz;
    uint32_t prescaler;
    uint32_t period_ticks;
    bool one_shot;
    bool wakeup_enable;
} lptim_config_t;

lptim_status_t lptim_periodic_arm(const lptim_config_t *cfg)
{
    if (cfg == NULL || cfg->source_hz == 0U ||
        cfg->period_ticks == 0U || cfg->period_ticks > 0xFFFFU) {
        return LPTIM_ERR_ARG;
    }

    if (!lptim_clock_is_retained_in_stop()) {
        return LPTIM_ERR_CLOCK;
    }

    lptim_disable();
    lptim_clear_all_flags();
    exti_clear_pending(LPTIM_WAKE_LINE);
    nvic_clear_pending(LPTIM_IRQn);

    lptim_set_prescaler(cfg->prescaler);
    lptim_set_autoreload(cfg->period_ticks - 1U);

    if (!lptim_wait_register_sync(100U)) {
        return LPTIM_ERR_SYNC;
    }

    if (cfg->one_shot) {
        lptim_enable_one_shot();
    } else {
        lptim_enable_periodic_mode();
    }

    lptim_enable_arr_match_interrupt();

    if (cfg->wakeup_enable) {
        pwr_enable_lptim_wakeup();
    }

    lptim_enable();
    lptim_start_counter();
    return LPTIM_OK;
}
```

### 5.3 计数值计算

设输入时钟为 fsrcfsrc​，预分频系数为 DD，目标周期为 TT，则：

N=T×fsrcDN=DT×fsrc​​

若硬件按 `ARR + 1` 计数：

ARR=N−1ARR=N−1

代码中必须避免 32 位整数乘法溢出，并明确舍入策略：

```
bool lptim_calc_ticks(uint32_t source_hz,
                      uint32_t divider,
                      uint32_t period_us,
                      uint32_t *arr)
{
    if (source_hz == 0U || divider == 0U ||
        period_us == 0U || arr == NULL) {
        return false;
    }

    uint64_t numerator = (uint64_t)source_hz * period_us;
    uint64_t ticks = (numerator +
                      ((uint64_t)divider * 1000000ULL) / 2ULL) /
                     ((uint64_t)divider * 1000000ULL);

    if (ticks == 0ULL || ticks > 65536ULL) {
        return false;
    }

    *arr = (uint32_t)(ticks - 1ULL);
    return true;
}
```

工程上还应返回实际周期：

Tactual=(ARR+1)DfsrcTactual​=fsrc​(ARR+1)D​

并将量化误差纳入 RTOS 时间补偿和产品时序预算。

### 5.4 外部脉冲计数

外部计数模式适合在 Stop 中累计流量脉冲、转速脉冲或低频事件：

```
bool lptim_external_counter_start(uint32_t max_count)
{
    if (max_count == 0U || max_count > 0xFFFFU) {
        return false;
    }

    lptim_disable();
    lptim_clear_all_flags();
    gpio_config_alternate_lptim_input();
    lptim_select_external_input_clock();
    lptim_set_autoreload(max_count);
    lptim_enable_arr_match_interrupt();
    lptim_enable();
    lptim_start_counter();
    return true;
}

uint32_t lptim_read_count(void)
{
    /* 某些器件读取 CNT 需要同步或双读校验 */
    uint32_t first = lptim_read_counter();
    uint32_t second = lptim_read_counter();
    return (first == second) ? first : lptim_read_counter();
}
```

注意事项：

- 输入脉冲必须满足最小高/低电平时间；
- 外部信号需有施密特输入、滤波或硬件整形；
- ARR 溢出必须被记录，否则会丢失累计量；
- Stop 唤醒后要明确计数器是否停止、复位或继续运行；
- 计数值读取与外部脉冲到达之间存在并发，需要使用快照或硬件锁存。

### 5.5 输入捕获与周期测量

若两次捕获值为 `c1`、`c2`，计数器模数为 `M`：

ΔC=(c2−c1+M)  MΔC=(c2−c1+M)modMfsignal=ftimerD×ΔCfsignal​=D×ΔCftimer​​

```
bool lptim_capture_period(uint32_t c1,
                          uint32_t c2,
                          uint32_t modulus,
                          uint32_t timer_hz,
                          uint32_t divider,
                          uint32_t *freq_hz)
{
    if (modulus == 0U || timer_hz == 0U ||
        divider == 0U || freq_hz == NULL) {
        return false;
    }

    uint32_t delta = (c2 >= c1) ? (c2 - c1)
                                : (modulus - c1 + c2);
    if (delta == 0U) {
        return false;
    }

    *freq_hz = timer_hz / (divider * delta);
    return true;
}
```

对于极低频输入，单周期捕获等待时间过长，可采用多周期平均：

f=KftimerD(CK−C0)f=D(CK​−C0​)Kftimer​​

这样可以降低量化误差，但会增加响应延迟。

### 5.6 LPTIM 中断服务函数

ISR 应只完成硬件确认和事件投递：

```
void LPTIM_IRQHandler(void)
{
    uint32_t status = lptim_get_status();

    if ((status & LPTIM_FLAG_ARRM) != 0U) {
        lptim_clear_flag(LPTIM_FLAG_ARRM);
        wake_event_post_isr(WAKE_SRC_LPTIM,
                            lptim_read_count(),
                            low_power_timestamp());
    }

    if ((status & LPTIM_FLAG_CMPM) != 0U) {
        lptim_clear_flag(LPTIM_FLAG_CMPM);
        wake_event_post_isr(WAKE_SRC_LPTIM_COMPARE,
                            lptim_read_compare(),
                            low_power_timestamp());
    }

    if ((status & LPTIM_FLAG_UE) != 0U) {
        lptim_clear_flag(LPTIM_FLAG_UE);
        lptim_overflow_record_isr();
    }
}
```

禁止在 ISR 中执行：

- 阻塞等待寄存器同步；
- `printf`；
- 长时间去抖；
- 启动复杂传感器或通信协议；
- 调用非 ISR-safe 的 RTOS API。

### 5.7 LPTIM 与 Stop 的进入/恢复

典型时序：

```
停止或挂起正在使用主时钟的外设
    ↓
清除 LPTIM/EXTI/NVIC/PWR 相关标志
    ↓
配置保持的低功耗时钟
    ↓
配置 ARR/比较值并等待同步
    ↓
使能 LPTIM 唤醒链路
    ↓
DSB + WFI
    ↓
唤醒后读取原因和计数值
    ↓
恢复系统时钟与外设
    ↓
重新装载下一次低功耗定时
```

Stop 后是否需要重新启动 LPTIM，必须查芯片手册。常见行为包括：

- LPTIM 在 Stop 中连续运行；
- LPTIM 保持计数但中断线路被重新初始化；
- LPTIM 唤醒后计数器复位；
- 只有特定 Stop 子模式支持 LPTIM。

## 6. 性能量化分析

### 6.1 示例测试平台

- MCU：Cortex-M4，80 MHz；
- LPTIM 时钟：32.768 kHz LSE；
- 计数器：16 位；
- Stop：SRAM 保持；
- 温度：25 ℃；
- 仪器：200 MHz 示波器、1 MSa/s 功耗分析仪。

|项目|示例值|
|---|---|
|LPTIM 时钟周期|30.5176 μs|
|5 秒唤醒配置误差|±30.5 μs 量化误差以内，未含晶振误差|
|LPTIM 事件到 ISR 入口|6.8 μs|
|Stop 唤醒到系统时钟恢复|78 μs|
|LPTIM 配置时间|12~35 μs|
|LPTIM 保持运行附加电流|约 0.8~2.5 μA|
|16 位无预分频最大周期|2 s|
|16 位 /8 最大周期|16 s|

上述数据仅用于说明测试方法，不是通用规格。

### 6.2 周期误差

总误差可近似拆分为：

ΔTtotal=ΔTquantization+ΔTclock+ΔTsync+ΔTwakeΔTtotal​=ΔTquantization​+ΔTclock​+ΔTsync​+ΔTwake​

晶振误差为 `ppm` 时：

ΔTclock=T×ppm×10−6ΔTclock​=T×ppm×10−6

例如 20 ppm 的 LSE 运行 10 分钟：

ΔT=600×20×10−6=12msΔT=600×20×10−6=12ms

因此周期性采样可以接受相对误差，但精密控制应采用校准后的 RTC/LPTIM 时钟或外部参考源。

### 6.3 分辨率与预分频权衡

分辨率：

R=DfsrcR=fsrc​D​

最大周期：

Tmax=2NDfsrcTmax​=fsrc​2ND​

增加预分频 `D`：

- 优点：扩大最大周期、降低计数溢出频率；
- 缺点：分辨率降低、短周期误差增大。

选择原则：

```
先满足最大周期约束
    ↓
再满足响应和分辨率约束
    ↓
最后评估 LPTIM 功耗与同步开销
```

### 6.4 唤醒能量交叉点

设 LPTIM Stop 比 Sleep 每秒节省功率 `ΔP`，进入和恢复额外能量为 `E_wake`：

tbreak−even=EwakeΔPtbreak−even​=ΔPEwake​​

例如：

- 额外唤醒能量：3 μJ；
- Sleep 与 Stop 功率差：4 mW。

tbreak−even=3μJ4mW=0.75mstbreak−even​=4mW3μJ​=0.75ms

若预计空闲时间短于交叉点，直接使用 Sleep 可能更省能量。

### 6.5 主要瓶颈与优化

|瓶颈|表现|优化手段|
|---|---|---|
|计数器溢出|周期错误、累计脉冲丢失|溢出 ISR、软件扩展位宽|
|LSI 漂移|长时间定时误差大|使用 LSE、校准或 RTC 对时|
|同步等待|配置耗时增加|批量配置、减少频繁重装载|
|低采样率|外部脉冲漏计|确认最大输入频率和滤波参数|
|标志未清|立即重复唤醒|外设、EXTI、NVIC、PWR 全链路清理|
|Tickless 补偿错误|RTOS 时间漂移|使用实际捕获计数进行补偿|

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否要求 CPU 停止时仍计时/计数？
├─ 否 → SysTick 或通用 TIM
└─ 是
   ├─ 需要日历和绝对时间？
   │  ├─ 是 → RTC Alarm
   │  └─ 否
   ├─ 需要外部脉冲计数？
   │  ├─ 是 → LPTIM 外部计数模式
   │  └─ 否
   ├─ 周期是否小于 LPTIM 单次最大周期？
   │  ├─ 是 → LPTIM ARR/Compare 唤醒
   │  └─ 否 → 预分频、软件扩展或 RTC
   ├─ 是否要求高精度微秒级？
   │  ├─ 是 → 通用 TIM/高频时钟
   │  └─ 否 → LPTIM + LSE/低功耗时钟
   └─ 是否需要 RTOS 时间基？
      ├─ 是 → Tickless + LPTIM
      └─ 否 → 裸机低功耗定时服务
```

### 7.2 典型场景

|场景|推荐方案|理由|
|---|---|---|
|每 5 秒采样|LPTIM + LSE + Stop|低功耗、周期明确|
|低功耗水表脉冲计数|LPTIM 外部计数|CPU 停止时仍可累计脉冲|
|RTOS Tickless Idle|LPTIM 单次比较|仅在最近截止时间唤醒|
|每天固定时间上报|RTC Alarm|适合绝对时间和日历事件|
|10 μs PWM 控制|通用 TIM|LPTIM 分辨率和时钟能力可能不足|
|低功耗转速测量|LPTIM 捕获/外部计数|降低 CPU 轮询开销|
|超长运输待机|RTC + Standby|LPTIM 未必在复位型模式保持|
|看门狗保护|IWDG|LPTIM 不能替代安全监控链路|

## 8. 工程最佳实践

### 8.1 设计原则

1. **先确认 LPTIM 时钟在目标低功耗模式中是否保持。**
2. 周期定时优先使用绝对截止时间或基于实际计数计算下一次事件。
3. 所有计数器、ARR、比较值都进行范围检查和溢出保护。
4. 统一处理 LPTIM、EXTI、NVIC、PWR 多层标志。
5. ISR 只确认硬件、读取快照和投递事件。
6. 外部输入必须考虑最小脉宽、毛刺、滤波和电平兼容。
7. RTOS Tickless 必须使用硬件实际计数进行时间补偿。
8. LPTIM 配置失败时回退到 Sleep 或 RTC，并记录错误。

### 8.2 选型决策矩阵

|指标|LPTIM|RTC|通用 TIM|SysTick|
|---|---|---|---|---|
|Stop 保持能力|5|5|2|1|
|低功耗|4~5|5|2~3|1|
|外部计数|4~5|1|5|1|
|时间精度|3~4|4~5|5|4|
|长周期|3|5|3|2|
|配置复杂度|3|4|4|2|
|适合 RTOS Tickless|5|4|2|1|

### 8.3 工业级驱动接口

```
typedef struct {
    bool (*init)(const lptim_config_t *cfg);
    bool (*arm_timeout_us)(uint64_t timeout_us);
    bool (*arm_deadline)(uint64_t deadline_ticks);
    bool (*start_external_counter)(void);
    uint32_t (*read_counter)(void);
    uint32_t (*read_capture)(void);
    void (*stop)(void);
    uint32_t (*get_flags)(void);
    void (*clear_flags)(uint32_t flags);
    bool (*is_clock_valid)(void);
} lptim_ops_t;
```

每次低功耗定时事件至少记录：

- 时钟源和实测频率；
- 预分频和 ARR；
- 计划周期与实际周期；
- 配置时间、唤醒延迟；
- 唤醒原因、溢出次数和错误码。

## 9. 常见错误与避坑指南

### 9.1 错误一：LPTIM 使用了 Stop 中不存在的时钟

**错误代码：**

```
rcc_lptim_select_clock(APB1_CLOCK);
lptim_start_counter();
enter_stop();
```

**根因：** APB 时钟在 Stop 中关闭，LPTIM 进入后不再计数。

**正确实现：**

```
rcc_lptim_select_clock(LSE_CLOCK);
if (!rcc_clock_is_kept_in_stop(LSE_CLOCK)) {
    enter_sleep_fallback();
    return;
}
lptim_start_counter();
enter_stop();
```

**风险影响：** 永不唤醒、任务超时和看门狗复位。

### 9.2 错误二：ARR 计算使用 32 位乘法溢出

**错误代码：**

```
uint32_t ticks = source_hz * timeout_us / 1000000U;
```

**根因：** 高频时钟与微秒数相乘超过 32 位范围。

**正确实现：** 使用 `uint64_t` 计算，并检查最终计数是否落在硬件范围内。

**风险影响：** 唤醒周期严重错误，且可能只在长周期参数下出现。

### 9.3 错误三：写 ARR 后立即启动，不等待同步

**错误代码：**

```
lptim_set_autoreload(arr);
lptim_enable();
lptim_start_counter();
```

**根因：** ARR 写入可能跨时钟域，尚未转移到活动寄存器。

**正确实现：** 检查 ARROK/同步状态，超时则停止并回退。

```
lptim_set_autoreload(arr);
if (!lptim_wait_arr_write_ok(100U)) {
    lptim_disable();
    return false;
}
lptim_enable();
lptim_start_counter();
```

**风险影响：** 第一个周期错误、偶发立即唤醒或计数不启动。

### 9.4 错误四：只清 LPTIM 标志，不清 EXTI/NVIC

**错误代码：**

```
lptim_clear_flag(LPTIM_FLAG_ARRM);
enter_stop();
```

**根因：** EXTI Pending 或 NVIC Pending 仍然置位。

**正确实现：**

```
lptim_disable();
lptim_clear_all_flags();
exti_clear_pending(LPTIM_WAKE_LINE);
nvic_clear_pending(LPTIM_IRQn);
pwr_clear_lptim_wakeup_flag();
lptim_arm_next_event();
```

**风险影响：** 进入后立即唤醒、唤醒风暴和平均功耗升高。

### 9.5 错误五：外部脉冲没有滤波，直接作为计数时钟

**错误代码：**

```
gpio_config_input(PULSE_PIN);
lptim_select_external_input(PULSE_PIN);
```

**根因：** EMI、机械触点或长线反射造成多次边沿。

**正确实现：** 使用施密特输入、RC、LPTIM 数字滤波或外部比较器，并验证最小脉宽。

**风险影响：** 流量、转速或事件计数偏大，导致错误控制和错误计费。

### 9.6 错误六：忽略计数器溢出

**错误代码：**

```
uint32_t count = lptim_read_counter();
flow_total += count;
```

**根因：** 16 位计数器在读取前已回卷，软件不知道发生过溢出。

**正确实现：** 开启溢出中断并扩展软件高位：

```
static volatile uint32_t s_overflow_hi;

void LPTIM_IRQHandler(void)
{
    uint32_t status = lptim_get_status();

    if ((status & LPTIM_FLAG_ARRM) != 0U) {
        lptim_clear_flag(LPTIM_FLAG_ARRM);
        s_overflow_hi++;
    }
}

uint32_t lptim_extended_count(void)
{
    uint32_t hi1, low, hi2;
    do {
        hi1 = s_overflow_hi;
        low = lptim_read_counter();
        hi2 = s_overflow_hi;
    } while (hi1 != hi2);

    return (hi1 << 16) | (low & 0xFFFFU);
}
```

**风险影响：** 长时间累计量回退、数据跳变和维护统计错误。

## 10. 多机制组合使用方案

### 10.1 LPTIM 低功耗时间管理架构

```
Low-Power Time Manager
├── Clock Source Manager
│   ├── LSE
│   ├── LSI
│   └── External Clock
├── LPTIM Driver
│   ├── One-Shot Timeout
│   ├── Periodic Wakeup
│   ├── Capture
│   └── External Counter
├── RTC Absolute Time
├── RTOS Tickless Adapter
├── Wakeup Reason Manager
├── Overflow Extension
└── Measurement/Fault Logger
```

### 10.2 LPTIM + Tickless + Stop 框架

```
typedef struct {
    uint64_t now_ticks;
    uint64_t next_deadline;
    uint32_t min_sleep_ticks;
    uint32_t max_sleep_ticks;
} lp_time_window_t;

bool tickless_sleep(const lp_time_window_t *window)
{
    if (window == NULL || window->next_deadline <= window->now_ticks) {
        return false;
    }

    uint64_t delta = window->next_deadline - window->now_ticks;

    if (delta < window->min_sleep_ticks) {
        platform_enter_sleep();
        return true;
    }

    if (delta > window->max_sleep_ticks) {
        delta = window->max_sleep_ticks;
    }

    lptim_stop();
    lptim_clear_all_flags();
    exti_clear_pending(LPTIM_WAKE_LINE);
    nvic_clear_pending(LPTIM_IRQn);

    if (!lptim_arm_deadline(delta)) {
        platform_enter_sleep();
        return false;
    }

    __disable_irq();
    if (rtos_has_pending_work()) {
        __enable_irq();
        lptim_stop();
        return false;
    }

    __DSB();
    __WFI();
    __ISB();
    __enable_irq();

    uint32_t elapsed = lptim_elapsed_ticks();
    rtos_tick_compensate(elapsed);
    lptim_stop();
    return true;
}
```

实际 RTOS 端应接入内核的 tickless 端口，不能在普通任务中直接修改调度器内部时间变量。

### 10.3 LPTIM + RTC + GPIO 多源唤醒

```
LPTIM：短周期相对超时
RTC：绝对时间和长周期事件
GPIO：外部状态变化
IWDG：故障自恢复
        ↓
统一唤醒管理器
        ↓
读取全部标志并形成位图
        ↓
安全告警 > 通信 > 周期任务 > 后台维护
```

底层保留所有原因，业务层再按优先级处理，禁止使用 `else if` 丢弃并发事件。

## 11. 工业级实际案例分析

### 11.1 案例一：电池环境传感器

**需求：** 每 5 秒采样，CPU 活动时间小于 20 ms，要求电池寿命超过一年。

**方案：**

- LSE 驱动 LPTIM；
- LPTIM 每 5 秒唤醒 Stop；
- 唤醒后打开传感器电源、采样、计算 CRC；
- 传感器关闭后重新装载下一次 ARR；
- 每 60 分钟由 RTC 对齐绝对时间，修正 LPTIM 周期误差。

**设计要点：**

- 使用绝对截止时间避免“每次唤醒延迟都累加”；
- 传感器稳定时间不由 LPTIM 计时结果替代硬件 Ready；
- 统计 LPTIM 唤醒次数和异常未唤醒次数；
- LSE 失效时回退到 RTC/LSI，并降低采样频率进入告警状态。

### 11.2 案例二：低功耗水表脉冲计数

**需求：** CPU 大部分时间 Stop，外部霍尔传感器每转输出一个脉冲，累计流量不能因 CPU 睡眠而丢失。

**架构：**

```
霍尔传感器 → 施密特输入/滤波 → LPTIM 外部计数
                                      ↓
                         ARR 溢出唤醒或定期读取
                                      ↓
                           软件扩展计数 + FRAM 保存
```

**设计要点：**

- 先根据最大流量计算最大脉冲频率；
- 验证 LPTIM 输入最大频率和最小脉宽；
- 溢出中断只递增高位，不做 Flash 写入；
- 定期将扩展计数保存至 FRAM 或磨损均衡存储；
- 断电时使用双槽位、序号和 CRC 保证累计量一致性。

### 11.3 案例三：工业 RS-485 从站超时

**需求：** 总线空闲时进入 Stop；收到帧后必须在 2 ms 内处理；帧接收超时必须自动丢弃半帧。

**方案：**

- UART 起始位负责唤醒；
- LPTIM 在 UART 首字节到达后启动帧间超时；
- DMA 接收数据，LPTIM Compare 监测帧间静默时间；
- 超时事件触发协议栈清空 DMA 缓冲并重新同步；
- RTC 不参与短帧超时，避免分辨率和唤醒延迟不足。

**设计要点：**

- 动态调频期间锁定 UART 时钟；
- LPTIM 只负责时间边界，协议合法性由 CRC 和长度字段判断；
- 处理中断与 DMA 并发时使用快照和内存屏障；
- 超时恢复失败时进入安全通信状态，不无限重试。

## 12. 高频问题深度答疑

### 问题一：LPTIM 能完全替代 RTC 吗？

不能。LPTIM 擅长相对周期、低功耗计数和捕获，RTC 擅长绝对时间、日历、长周期和掉电保持。产品通常同时使用二者：LPTIM 负责短期调度，RTC 负责长期校准与绝对时间。

### 问题二：为什么 LPTIM 已启动却不唤醒？

常见原因包括：时钟源未在 Stop 中保持、LPTIM 未连接 PWR 唤醒通道、ARR 写入未同步、外设或 EXTI 标志配置错误、NVIC 未使能以及低功耗模式不支持该 LPTIM 实例。应按“时钟—计数—事件—EXTI—PWR—CPU”逐层验证。

### 问题三：ARR 应设置为 N 还是 N-1？

取决于硬件计数语义。有的定时器在计数到 ARR 时产生 Match，有的按 ARR+1 个时钟产生 Update。必须通过参考手册和示波器验证，不能跨芯片套用 `N-1` 经验。

### 问题四：LPTIM 的周期为什么比计算值长一个或几个时钟？

可能来自 ARR 预加载、写入同步、启动同步、输入时钟同步器和事件传播延迟。对长周期而言误差通常很小；对短周期则必须使用实测校准或选择更高频时钟。

### 问题五：外部脉冲计数能否在任意 Stop 模式中工作？

不能。必须同时满足 GPIO 输入缓冲、LPTIM 时钟域、计数器电源域和目标 Stop 子模式的保持条件。还要确认外部引脚是否支持异步输入以及最大输入频率。

### 问题六：LPTIM Tickless 会不会导致 RTOS 时间漂移？

会，如果只按计划睡眠时间补偿，而没有考虑计数分辨率、晶振误差、提前唤醒和配置失败。应读取实际经过的计数值，按实际时钟换算 Tick，并周期性使用 RTC 或外部参考进行校准。

### 问题七：为什么 LPTIM 周期唤醒后功耗仍很高？

LPTIM 本身可能只消耗微安，但频繁唤醒会引发 PLL、传感器、通信模块和 RTOS 任务活动。应计算完整周期能量：

Ecycle=Ewake+Eactive+Eperipheral+EsleepEcycle​=Ewake​+Eactive​+Eperipheral​+Esleep​

有时合并多个事件、降低唤醒次数比继续优化 LPTIM 静态电流更有效。

## 13. 课程核心总结

### 核心要点

1. **LPTIM 是跨越 Run/Stop 边界的低功耗时基与计数外设。**
2. 首要确认时钟源、电源域和目标低功耗模式之间的兼容关系。
3. ARR、预分频和计数器位宽决定分辨率与最大周期。
4. LPTIM 配置必须处理跨时钟域同步和寄存器写入完成状态。
5. 周期唤醒、外部计数和输入捕获要分别设计溢出、毛刺和并发保护。
6. 唤醒标志必须覆盖 LPTIM、EXTI、NVIC 和 PWR 多层状态。
7. RTOS Tickless 必须基于实际经过计数进行时间补偿。
8. LPTIM 的系统收益最终由整机周期能量、唤醒次数和外部负载决定。

### 性能排序

典型低功耗时基功耗从低到高：

```
RTC 唤醒逻辑 ≤ LPTIM + LSE < LPTIM + UART/外部高速时钟 < 通用 TIM < SysTick 持续运行
```

典型时间分辨率从高到低：

```
通用 TIM > LPTIM 高速时钟 > LPTIM/LSE > RTC 1 Hz
```

典型 Stop 适配能力：

```
RTC ≈ LPTIM > 通用 TIM > SysTick
```

### 通用选型结论

- **Stop 中相对周期唤醒：LPTIM**；
- **外部低频脉冲计数：LPTIM**；
- **外部周期/脉宽测量：LPTIM 捕获或通用 TIM**；
- **绝对时间和超长周期：RTC**；
- **RTOS Tickless：LPTIM + 独立低功耗时钟**；
- **微秒级精密控制：通用高频定时器**。

## 14. 快速参考速查表

### 14.1 场景选型表

|需求|首选方案|关键检查|
|---|---|---|
|Stop 每秒唤醒|LPTIM + LSE|ARR 范围、同步、PWR 唤醒|
|长周期绝对时间|RTC Alarm|LSE 精度、日历和溢出|
|外部脉冲累计|LPTIM 外部计数|最大频率、滤波、溢出|
|测量外部周期|LPTIM 捕获|捕获同步和多周期平均|
|RTOS Tickless|LPTIM One-Shot|实际计数、Tick 补偿|
|高精度 PWM|通用 TIM|时钟分辨率和抖动|

### 14.2 配置检查表

|项目|必须确认|
|---|---|
|时钟源|Stop 中保持且频率已测量|
|预分频|分辨率和最大周期满足需求|
|ARR/比较|计数语义和边界已验证|
|同步|写入完成标志和超时路径|
|触发输入|电平、边沿、最大频率、最小脉宽|
|标志|LPTIM、EXTI、NVIC、PWR 全链路|
|溢出|中断、软件扩展和持久化策略|
|恢复|Stop 后计数器和时钟恢复行为|
|RTOS|Tickless、截止时间和时间补偿|
|测试|功耗、周期误差、唤醒延迟和异常注入|

### 14.3 进入低功耗前检查清单

```
[ ] LPTIM 时钟源在目标模式中保持
[ ] 时钟频率和 ppm 误差已记录
[ ] 预分频与 ARR 范围合法
[ ] ARR/比较寄存器写入已同步
[ ] LPTIM 原始标志已清除
[ ] EXTI/NVIC/PWR 标志已按手册处理
[ ] GPIO 输入滤波和电平已确认
[ ] 外部计数最大频率满足规格
[ ] 溢出扩展已启用
[ ] RTOS Tickless 使用实际计数补偿
[ ] 看门狗最大睡眠时间兼容
[ ] Stop 唤醒后计数器行为已验证
[ ] 配置失败有 Sleep/RTC 回退
[ ] 唤醒原因、周期误差和异常次数可记录
```

## 15. 学习效果自检

- [ ]  能画出 LPTIM 时钟到 CPU 唤醒的完整链路。
- [ ]  能解释 LPTIM 与 RTC、通用 TIM、SysTick 的边界。
- [ ]  能计算给定时钟、预分频和周期对应的 ARR。
- [ ]  能判断目标 LPTIM 时钟是否在 Stop 中保持。
- [ ]  能解释 ARR 写入同步和跨时钟域的影响。
- [ ]  能设计外部脉冲计数的滤波、溢出和软件扩展方案。
- [ ]  能用 LPTIM 捕获计算外部信号频率。
- [ ]  能处理 LPTIM、EXTI、NVIC、PWR 多层标志。
- [ ]  能将 LPTIM 接入 RTOS Tickless 并完成时间补偿。
- [ ]  能计算量化误差、晶振误差和唤醒延迟。
- [ ]  能定位“定时器运行但不唤醒”的分层故障。
- [ ]  能证明 LPTIM 低功耗方案没有造成事件丢失、误计数或实时性退化。

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：LPTIM 周期唤醒

- 使用 LSE 配置 1 s、5 s、30 s 三种周期；
- 进入 Stop，GPIO 标记唤醒入口和 ISR；
- 测量周期误差、唤醒延迟和平均电流。

验收：周期误差可解释，所有标志可追踪，连续运行 24 小时无异常唤醒。

#### 任务二：LPTIM 外部脉冲计数

- 使用信号发生器产生不同频率和脉宽的脉冲；
- 验证输入滤波、最大计数频率和溢出扩展；
- 对比软件轮询、通用 TIM 和 LPTIM 的功耗。

验收：在规格范围内计数误差为零或处于明确容差内。

#### 任务三：输入捕获测频

- 测量 1 Hz~10 kHz 外部信号；
- 比较单周期和多周期平均；
- 在不同温度和电压下统计误差。

验收：输出频率、响应时间和 P95 误差报告。

#### 任务四：RTOS Tickless + LPTIM

- 实现最近截止时间计算；
- 小于交叉点使用 Sleep，大于交叉点使用 Stop；
- 用实际 CNT 值补偿系统 Tick；
- 注入 GPIO 提前唤醒和 LPTIM 配置失败。

验收：无周期性 SysTick 唤醒，任务延时误差满足系统阈值。

#### 任务五：多源唤醒和故障回归

- 同时配置 RTC、LPTIM、GPIO 和 IWDG；
- 注入旧标志、并发事件、时钟失效和计数溢出；
- 生成唤醒原因位图和故障统计。

验收：事件不丢失、原因不覆盖、故障可降级，长时间伪唤醒率满足目标。

### 16.2 性能测试方法

|测试项|方法|
|---|---|
|周期精度|用参考时钟与 GPIO 唤醒标记比较|
|唤醒延迟|外部触发到 ISR/任务 GPIO 翻转的时间差|
|低功耗电流|Stop 稳态窗口平均值和长时间积分|
|配置同步时间|记录写 ARR 到 ARROK 的时间|
|外部计数准确性|已知频率源与 LPTIM 读数比对|
|溢出正确性|让计数器跨越多次回卷并核对扩展值|
|Tickless 误差|与高精度 RTC 或逻辑分析仪比较|
|伪唤醒率|长时间统计并按标志位分类|
|故障恢复|注入时钟、标志、GPIO、看门狗异常|

周期实际值：

Tactual=(ARR+1)DfsrcTactual​=fsrc​(ARR+1)D​

周期误差：

ϵT=Tactual−TtargetTtargetϵT​=Ttarget​Tactual​−Ttarget​​

计数频率：

fsignal=KftimerD(CK−C0)fsignal​=D(CK​−C0​)Kftimer​​

单次唤醒能量：

E=∫t0t1V(t)I(t)dtE=∫t0​t1​​V(t)I(t)dt

### 16.3 进阶学习方向

1. LPTIM 跨时钟域同步、预加载和异步输入采样；
2. FreeRTOS Tickless、Zephyr PM 和 Linux hrtimer/cpuidle 协同；
3. RTC 校准、LSE 温度补偿和长期时间同步；
4. LPTIM 外部计数与流量、转速、编码器和能量计量；
5. 低功耗 PWM、One-Pulse、触发链和 DMA；
6. TrustZone 下安全唤醒源和低功耗时基隔离；
7. 多源唤醒风暴检测、自动化波形分类和低功耗 CI 回归；
8. 从单芯片 LPTIM 扩展到 PMIC、传感器、电池和整机能量模型。

**最终工程结论：LPTIM 不是“低功耗版普通定时器”，而是连接低速时钟域、外部事件、计数器、唤醒逻辑和 RTOS 时间管理的系统组件。只有做到“时钟可保持、计数不丢失、同步可验证、标志可清理、误差可量化、故障可降级”，LPTIM 才能在工业级低功耗系统中稳定承担时间与事件管理职责。**