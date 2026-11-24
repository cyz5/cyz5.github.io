
## 1. 学习目标

### 理解

- 理解 PWM 的周期、频率、占空比、计数模式、比较匹配和输出极性。
- 理解边沿对齐 PWM、中心对齐 PWM、互补 PWM、死区插入的硬件实现。
- 理解 PWM 分辨率、频率、时钟源、预分频器之间的约束关系。

### 掌握

- 掌握基于定时器寄存器的 PWM 初始化、更新和停止流程。
- 掌握电机、LED、蜂鸣器、加热器等典型负载的 PWM 参数选择。
- 掌握运行时修改占空比时的影子寄存器、更新事件和毛刺规避方法。

### 精通

- 能够分析 PWM 输出抖动、频率误差、占空比误差、更新延迟和优先级影响。
- 能够设计带故障关闭、过流保护、死区控制和同步更新的工业级 PWM 驱动。
- 能够处理定时器资源冲突、DMA 更新、低功耗恢复和多通道同步问题。

### 能够设计

- 能够设计一个支持多通道、动态频率、故障关断和参数校验的 PWM HAL。
- 能够针对直流电机、三相逆变器和 LED 调光等场景完成选型与验证方案。

---

## 2. 前置要求

### 知识要求

- C 语言：位操作、`volatile`、整数溢出、结构体和函数指针。
- MCU 定时器：计数器、预分频器、自动重装载寄存器、比较寄存器。
- 中断、DMA、GPIO 复用和时钟树。
- 基本电气知识：MOSFET、体二极管、栅极驱动、负载惯性和电流续流。

### 技能要求

- 能够阅读 MCU Reference Manual 中的 Timer/PWM 章节。
- 能够使用示波器或逻辑分析仪测量频率、占空比和边沿抖动。
- 能够定位寄存器配置错误、GPIO 复用错误和时钟源错误。
- 能够编写基础驱动测试代码，并建立参数边界测试。

---

## 3. 技术概述

PWM 是一种利用**固定周期数字脉冲的高、低电平持续时间比例**表示模拟控制量的技术。

基本参数：

```
周期 T = 1 / f_pwm
占空比 D = T_high / T
平均电压 V_avg = D * V_high
```

对于理想电阻负载，平均功率近似为：

```
P_avg = D * P_full
```

但对于电机、线圈、加热器等储能负载，实际电流和功率还受电感、电阻、反电动势、续流路径和控制环带宽影响。

主流 PWM 类型：

1. **边沿对齐 PWM**
    
    - 计数器从 0 递增到周期值。
    - 一个边沿固定，另一个边沿随占空比移动。
    - 实现简单，适合 LED、风扇、普通执行器。
2. **中心对齐 PWM**
    
    - 计数器上下计数。
    - 脉冲中心固定，两个边沿对称移动。
    - 适合电机控制和功率变换，可降低谐波和采样时序误差。
3. **互补 PWM**
    
    - 输出高侧和低侧驱动信号。
    - 通常配合死区时间，避免上下管直通。
4. **硬件 PWM**
    
    - 由定时器输出比较单元直接生成。
    - CPU 负载低，边沿抖动小，实时性高。
5. **软件 PWM**
    
    - 通过定时器中断或 GPIO 翻转生成。
    - 资源灵活，但 CPU 负载、抖动和通道数量受限。

---

## 4. 核心特性横向对比

|维度|边沿对齐|中心对齐|软件 PWM|硬件 PWM|
|---|---|---|---|---|
|定时器复杂度|低|中|中|低到中|
|CPU 占用|极低|极低|中到高|极低|
|边沿抖动|取决于硬件|取决于硬件|受中断影响|极低|
|频率精度|高|高|中|高|
|适用负载|LED、风扇、加热器|电机、逆变器|低速指示、资源不足场景|工业控制|
|频谱特性|单边沿变化|边沿对称|受软件调度影响|稳定|
|ADC 同步采样|较复杂|较容易|不可靠|可由触发器完成|
|多通道同步|依赖定时器|依赖定时器|较差|较好|
|故障关闭|依赖外部硬件|可结合刹车输入|软件延迟大|可由硬件完成|
|最大通道数|受定时器限制|受定时器限制|受 CPU 限制|受定时器限制|

---

## 5. 底层原理与功能特性深度解析

### 5.1 边沿对齐 PWM 的计数逻辑

设：

```
timer_clk = 72 MHz
PSC       = 71
ARR       = 999
```

计数频率为：

```
f_cnt = 72 MHz / (PSC + 1)
      = 72 MHz / 72
      = 1 MHz
```

PWM 频率为：

```
f_pwm = f_cnt / (ARR + 1)
      = 1 MHz / 1000
      = 1 kHz
```

如果：

```
CCR = 250
```

则占空比为：

```
D = CCR / (ARR + 1)
  = 250 / 1000
  = 25%
```

典型 PWM 输出比较逻辑：

```
CNT < CCR  -> 输出有效电平
CNT >= CCR -> 输出无效电平
CNT 溢出   -> 开始下一个周期
```

### 5.2 通用硬件抽象代码

下面代码假设定时器具备：

- 预分频寄存器 `PSC`
- 自动重装载寄存器 `ARR`
- 比较寄存器 `CCR`
- 预装载使能
- 更新事件
- 输出使能

```
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef struct {
    volatile uint32_t CR1;
    volatile uint32_t DIER;
    volatile uint32_t SR;
    volatile uint32_t EGR;
    volatile uint32_t CCMR1;
    volatile uint32_t CCER;
    volatile uint32_t PSC;
    volatile uint32_t ARR;
    volatile uint32_t CCR1;
    volatile uint32_t BDTR;
} pwm_timer_regs_t;

typedef struct {
    pwm_timer_regs_t *regs;
    uint32_t timer_clk_hz;
    uint32_t pwm_hz;
    uint32_t period_ticks;
    uint8_t channel;
    bool inverted;
    bool running;
} pwm_device_t;

enum {
    PWM_OK = 0,
    PWM_EINVAL = -1,
    PWM_ERANGE = -2,
    PWM_EBUSY = -3
};

static int pwm_calc_period(uint32_t timer_clk_hz,
                           uint32_t pwm_hz,
                           uint32_t *period_ticks)
{
    if (timer_clk_hz == 0U || pwm_hz == 0U || period_ticks == NULL) {
        return PWM_EINVAL;
    }

    uint32_t ticks = timer_clk_hz / pwm_hz;

    if (ticks < 2U || ticks > 0x10000U) {
        return PWM_ERANGE;
    }

    *period_ticks = ticks;
    return PWM_OK;
}

int pwm_init(pwm_device_t *dev,
             pwm_timer_regs_t *regs,
             uint32_t timer_clk_hz,
             uint32_t pwm_hz,
             uint8_t channel,
             bool inverted)
{
    uint32_t period_ticks;
    int ret;

    if (dev == NULL || regs == NULL || channel != 1U) {
        return PWM_EINVAL;
    }

    ret = pwm_calc_period(timer_clk_hz, pwm_hz, &period_ticks);
    if (ret != PWM_OK) {
        return ret;
    }

    dev->regs = regs;
    dev->timer_clk_hz = timer_clk_hz;
    dev->pwm_hz = pwm_hz;
    dev->period_ticks = period_ticks;
    dev->channel = channel;
    dev->inverted = inverted;
    dev->running = false;

    /* 这里假设预分频已由上层时钟配置为 1。 */
    regs->PSC = 0U;
    regs->ARR = period_ticks - 1U;

    /* PWM mode 1 + CCR 预装载。具体位定义必须以芯片手册为准。 */
    regs->CCMR1 |= (1U << 3);
    regs->CCMR1 |= (6U << 4);

    /* 初始输出关闭，避免初始化期间出现意外脉冲。 */
    regs->CCR1 = 0U;
    regs->CCER &= ~(1U << 0);

    /* 强制产生更新事件，使 ARR/CCR 等配置进入活动寄存器。 */
    regs->EGR = 1U;

    return PWM_OK;
}
```

### 5.3 占空比更新

占空比输入应使用整数千分比或百万分比，避免浮点参与实时路径。

```
int pwm_set_duty_permille(pwm_device_t *dev, uint16_t duty_permille)
{
    uint32_t compare;

    if (dev == NULL || dev->regs == NULL) {
        return PWM_EINVAL;
    }

    if (duty_permille > 1000U) {
        return PWM_ERANGE;
    }

    compare = ((uint64_t)duty_permille * dev->period_ticks) / 1000U;

    if (compare > dev->period_ticks) {
        compare = dev->period_ticks;
    }

    /*
     * CCR 预装载开启时，该值通常在下一个更新事件生效，
     * 可避免周期中途修改造成窄脉冲或毛刺。
     */
    dev->regs->CCR1 = compare;
    return PWM_OK;
}
```

边界行为必须明确：

- `0%`：输出始终无效。
- `100%`：某些 MCU 中 `CCR = ARR + 1` 才能保证始终有效。
- `CCR = ARR` 可能仍然在计数边界产生一个极窄的无效窗口。
- 对功率级而言，`0%` 和 `100%` 不能只依赖比较寄存器语义，应验证实际栅极波形。

### 5.4 启停和故障关闭

```
int pwm_start(pwm_device_t *dev)
{
    if (dev == NULL || dev->regs == NULL) {
        return PWM_EINVAL;
    }

    /* 先装载配置，再打开通道，最后启动计数器。 */
    dev->regs->EGR = 1U;
    dev->regs->CCER |= (1U << 0);
    dev->regs->CR1 |= (1U << 0);
    dev->running = true;

    return PWM_OK;
}

int pwm_stop(pwm_device_t *dev)
{
    if (dev == NULL || dev->regs == NULL) {
        return PWM_EINVAL;
    }

    dev->regs->CCER &= ~(1U << 0);
    dev->regs->CCR1 = 0U;
    dev->regs->CR1 &= ~(1U << 0);
    dev->running = false;

    return PWM_OK;
}

void pwm_emergency_off(pwm_device_t *dev)
{
    if (dev == NULL || dev->regs == NULL) {
        return;
    }

    /*
     * 故障路径不应等待任务调度或普通中断。
     * 实际项目应优先使用定时器硬件 Break 输入。
     */
    dev->regs->BDTR |= (1U << 0); /* 假设为主输出关闭位 */
    dev->regs->CCER &= ~(1U << 0);
    dev->regs->CCR1 = 0U;
}
```

### 5.5 中心对齐 PWM

中心对齐模式下，计数序列为：

```
0 -> ARR -> 0 -> ARR -> ...
```

如果计数器上下计数，PWM 频率通常变为：

```
f_pwm = f_cnt / (2 * ARR)
```

与边沿对齐相比：

- 开关边沿在周期中心对称分布。
- 适合在 PWM 中点进行 ADC 采样。
- 可降低偶次谐波。
- 相同定时器时钟下，最大 PWM 频率约为边沿对齐的一半。
- 更新事件可能在上溢、下溢或两者都产生，必须确认芯片行为。

### 5.6 互补输出与死区

半桥上下管不能同时导通。切换过程中必须插入死区：

```
高侧关闭
等待 t_dead
低侧打开
```

死区时间选择应满足：

```
t_dead > t_turnoff_high + t_driver_delay + t_skew
```

同时不能过大，因为死区期间电流通过体二极管或同步整流路径，导致：

- 二极管反向恢复损耗增加。
- 输出电压误差增加。
- 电流畸变和低速转矩脉动增加。

典型功率级至少需要：

- 互补通道。
- 可配置死区。
- Break/故障输入。
- 软启动。
- 硬件强制关闭状态。
- 上下管输出极性配置。
- 栅极驱动器欠压锁定。

---

## 6. 性能量化分析

### 6.1 频率和分辨率

边沿对齐模式下：

```
f_pwm = f_timer / ((PSC + 1) * (ARR + 1))
```

占空比分辨率近似为：

```
Resolution_bits = log2(ARR + 1)
```

例如：

```
f_timer = 72 MHz
f_pwm   = 20 kHz
PSC     = 0
ARR     = 3599
```

则：

```
f_pwm = 72 MHz / 3600 = 20 kHz
分辨率 = log2(3600) ≈ 11.81 bit
最小占空比步进 = 1 / 3600 ≈ 0.0278%
```

### 6.2 中断软件 PWM 的 CPU 开销

假设：

```
PWM 频率       = 20 kHz
每周期中断次数 = 2
ISR 平均耗时   = 1.2 us
CPU 主频       = 168 MHz
```

CPU 占用率：

```
Load = 20,000 * 2 * 1.2 us
     = 4.8%
```

如果有 8 个软件 PWM 通道，并且每个通道都需要独立边沿处理，实际开销可能超过：

```
8 * 4.8% = 38.4%
```

这还没有计算临界区、Cache、总线竞争和高优先级中断影响。因此：

- 低速 LED 调光可使用软件 PWM。
- 电机和功率转换必须优先使用硬件 PWM。
- 高通道数软件 PWM 应使用时间片调度、排序边沿或 DMA。

### 6.3 抖动量化

如果软件 PWM ISR 的最坏延迟为 `3 us`，而 PWM 周期为 `50 us`：

```
相对边沿误差 = 3 / 50 = 6%
```

对 20 kHz PWM：

```
T = 50 us
```

这可能导致：

- LED 轻微亮度噪声。
- 电机电流纹波增加。
- 电流环采样点偏移。
- 声学噪声增强。

硬件 PWM 的边沿误差通常由定时器时钟周期决定。72 MHz 定时器时钟对应：

```
T_tick = 1 / 72 MHz ≈ 13.89 ns
```

若使用硬件预装载，边沿位置误差通常接近一个或少数几个定时器 tick。

### 6.4 内存开销

典型单通道软件对象：

```
pwm_device_t ≈ 32~48 bytes
```

硬件定时器寄存器不占用 RAM。若使用 DMA 更新：

```
DMA buffer = channel_count * sample_count * sizeof(uint16_t)
```

例如：

```
4 通道 * 256 点 * 2 bytes = 2048 bytes
```

### 6.5 主要瓶颈和优化收益

|瓶颈|典型影响|优化方式|
|---|---|---|
|软件翻转 GPIO|抖动大、CPU 高|改用硬件输出比较|
|频繁修改 ARR/PSC|产生周期跳变|使用影子寄存器和同步更新|
|浮点计算占空比|ISR 延迟|使用定点整数|
|多通道独立中断|中断数量高|DMA 或统一时间片|
|无硬件死区|直通风险|使用高级定时器死区模块|
|总线写寄存器竞争|更新不确定|在更新事件或 DMA 中更新|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
需要 PWM 输出
|
+-- 是否驱动半桥/全桥/三相功率级？
|   |
|   +-- 是 --> 是否需要互补输出、死区、故障刹车？
|              |
|              +-- 是 --> 高级定时器硬件 PWM
|              +-- 否 --> 普通硬件 PWM
|
+-- 是否需要 ADC 与 PWM 精确同步？
|   |
|   +-- 是 --> 中心对齐 + 定时器触发 ADC + DMA
|   +-- 否 --> 边沿对齐即可
|
+-- 通道数是否超过硬件 PWM 通道数？
|   |
|   +-- 是 --> 增加定时器、外部 PWM 芯片或 DMA 软件 PWM
|   +-- 否 --> 硬件 PWM
|
+-- PWM 频率是否低于 1 kHz 且实时性要求低？
    |
    +-- 是 --> 软件 PWM 可接受
    +-- 否 --> 硬件 PWM
```

### 7.2 典型场景

|场景|推荐方案|主要理由|
|---|---|---|
|LED 调光|500 Hz~20 kHz 边沿对齐|成本低、实现简单|
|有刷直流电机|10~25 kHz 硬件 PWM|避开可闻频段，减少 CPU 负担|
|BLDC 六步换相|10~30 kHz 互补 PWM|需要上下桥臂控制和死区|
|PMSM 矢量控制|10~40 kHz 中心对齐|便于 ADC 中点采样|
|蜂鸣器|1~4 kHz PWM|频率直接对应音调|
|加热器|低频时间比例控制|热惯性大，无需高频开关|
|舵机|50 Hz，脉宽 1~2 ms|协议约定脉宽而非平均电压|
|开关电源|高级定时器 + 硬件保护|强实时性和故障安全要求|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **驱动层不直接暴露芯片位定义**，通过 HAL 或 LL 封装。
2. 所有频率、占空比、死区参数都进行范围校验。
3. 初始化时先关闭输出，再配置寄存器，最后启动计数器。
4. 动态更新优先使用 CCR 影子寄存器。
5. 功率级故障关闭使用硬件路径，软件仅作为第二道保护。
6. 占空比使用整数比例，避免实时路径浮点运算。
7. 明确 `0%`、`100%`、极小占空比的硬件语义。
8. 记录定时器时钟来源，禁止假定 APB 总线频率等于定时器频率。

### 8.2 选型决策矩阵

|需求|边沿对齐|中心对齐|软件 PWM|高级定时器|
|---|---|---|---|---|
|低 CPU 占用|高|高|低|高|
|ADC 同步|中|高|低|高|
|故障安全|低|中|低|高|
|配置复杂度|低|中|中|高|
|功率控制|中|高|不推荐|必选|
|低成本简单输出|高|低|中|低|

### 8.3 工业级编码规范

- 单位写入变量名：`pwm_hz`、`deadtime_ns`、`duty_permille`。
- 不允许未经检查的 `ARR + 1`、`CCR + 1` 溢出。
- 不在中断中调用阻塞 API。
- 不在驱动内部隐式修改 GPIO 复用配置，除非接口契约明确。
- 对定时器共享资源建立所有权模型。
- 对更新顺序编写硬件相关注释，并引用芯片手册章节。

---

## 9. 常见错误与避坑指南

### 错误一：频率计算遗漏 `+1`

错误代码：

```
regs->ARR = timer_clk_hz / pwm_hz;
```

根因：

- 计数范围通常为 `0..ARR`，实际周期是 `ARR + 1`。
- 频率将产生一个周期计数误差。

正确实现：

```
uint32_t period = timer_clk_hz / pwm_hz;
regs->ARR = period - 1U;
```

风险：

- 高频下频率误差明显。
- 舵机、通信时序和电机控制可能不满足规范。

### 错误二：运行中直接修改 ARR 和 CCR

错误代码：

```
regs->ARR = new_arr;
regs->CCR1 = new_ccr;
```

根因：

- 可能在当前周期中途改变比较边界。
- 产生窄脉冲、周期突变或短暂 100% 输出。

正确实现：

```
/* 开启 ARR/CCR 预装载，在更新事件统一生效。 */
regs->ARR = new_arr;
regs->CCR1 = new_ccr;
regs->EGR = 1U;
```

具体是否应手动触发 `EGR`，必须根据芯片的影子寄存器机制确认。

### 错误三：把 100% 占空比简单写成 CCR=ARR

错误代码：

```
regs->CCR1 = regs->ARR;
```

根因：

- 比较匹配规则可能在周期边界产生一个低电平 tick。
- 某些定时器对 `CCR > ARR`、`CCR = ARR` 的处理不同。

正确实现：

```
uint32_t period = regs->ARR + 1U;

if (duty_permille == 1000U) {
    regs->CCR1 = period;       /* 仅适用于支持该语义的定时器 */
} else {
    regs->CCR1 = (period * duty_permille) / 1000U;
}
```

风险：

- 电机最大输出不稳定。
- 功率级出现非预期开关边沿。

### 错误四：上下桥臂没有死区

错误代码：

```
high_side = !high_side;
low_side = high_side;
```

根因：

- 高侧关闭和低侧开启不是零延迟。
- GPIO、驱动器和 MOSFET 都存在传播与关断延迟。

正确实现：

```
/* 实际项目应使用高级定时器硬件互补输出和 DTG 寄存器。 */
configure_complementary_output();
configure_deadtime_ns(300U);
configure_break_input();
```

风险：

- 上下管直通。
- MOSFET、驱动器甚至 PCB 铜箔损坏。

### 错误五：错误假定定时器时钟

错误代码：

```
pwm_hz = 72000000U / ((psc + 1U) * (arr + 1U));
```

根因：

- 定时器时钟可能来自不同 APB 域。
- 某些 MCU 在 APB 分频不为 1 时，定时器时钟自动倍频。
- 时钟切换后驱动缓存值过期。

正确实现：

```
uint32_t timer_clk_hz = clock_get_timer_frequency(TIMER1);
pwm_calc_period(timer_clk_hz, requested_pwm_hz, &period_ticks);
```

风险：

- 示波器测得频率与设计值不一致。
- 不同板级配置下行为不同。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

```
定时器 PWM
|
+-- CCR 影子寄存器：无毛刺更新
+-- 更新事件：统一提交参数
+-- ADC 触发：固定采样相位
+-- DMA：周期性更新占空比
+-- Break 输入：硬件故障关闭
+-- RTOS 控制任务：计算目标占空比
+-- 保护任务：监视过流、过温、欠压
```

### 10.2 双缓冲参数提交框架

```
typedef struct {
    uint32_t period_ticks;
    uint32_t duty_ticks;
    uint32_t generation;
} pwm_pending_t;

typedef struct {
    volatile uint32_t *arr;
    volatile uint32_t *ccr;
    pwm_pending_t pending;
    uint32_t active_generation;
} pwm_sync_t;

int pwm_prepare_update(pwm_sync_t *sync,
                       uint32_t period_ticks,
                       uint32_t duty_ticks)
{
    if (sync == NULL || sync->arr == NULL || sync->ccr == NULL) {
        return PWM_EINVAL;
    }

    if (period_ticks < 2U || duty_ticks > period_ticks) {
        return PWM_ERANGE;
    }

    sync->pending.period_ticks = period_ticks;
    sync->pending.duty_ticks = duty_ticks;
    sync->pending.generation++;
    return PWM_OK;
}

void pwm_commit_at_update(pwm_sync_t *sync)
{
    if (sync == NULL) {
        return;
    }

    /*
     * 该函数应在定时器更新事件或 DMA 提交点执行。
     * 多核或中断并发场景需要额外的原子性保护。
     */
    *sync->arr = sync->pending.period_ticks - 1U;
    *sync->ccr = sync->pending.duty_ticks;
    sync->active_generation = sync->pending.generation;
}
```

对于电机控制，推荐组合：

```
中心对齐 PWM
+ 互补输出
+ 硬件死区
+ ADC 触发
+ DMA 采样
+ Break 过流关闭
+ 控制环在固定采样点运行
```

---

## 11. 工业级实际案例分析

### 案例一：24 V 有刷直流电机调速

#### 需求

- PWM 频率：20 kHz。
- 占空比：0~95%。
- 过流后硬件关闭。
- 速度环周期：1 ms。
- 禁止启动时误转。

#### 架构

```
PWM Timer CH1 -> MOSFET Gate Driver -> DC Motor
Current Comparator -> Timer Break
Encoder Timer -> Speed Feedback
RTOS Task 1 ms -> PI Speed Controller -> CCR1
```

#### 核心代码

```
void motor_set_command(int32_t command_permille)
{
    if (command_permille < 0) {
        command_permille = 0;
    }

    /* 预留 5% 保护区，避免极限占空比下续流异常。 */
    if (command_permille > 950) {
        command_permille = 950;
    }

    (void)pwm_set_duty_permille(&motor_pwm,
                                (uint16_t)command_permille);
}
```

#### 设计要点

- 电机启动时采用斜坡增加占空比，限制浪涌电流。
- 过流信号直接进入硬件 Break，不等待 RTOS 任务。
- 速度控制输出必须经过限幅、积分抗饱和和故障状态检查。
- PWM 频率选择在可闻频段以上，但需评估 MOSFET 开关损耗。

### 案例二：三相 PMSM 逆变器

#### 需求

- 20 kHz SVPWM。
- 中心对齐。
- 三相互补输出。
- 死区 300 ns。
- ADC 在 PWM 中点采样。
- 硬件过流在数百纳秒级关闭。

#### 架构

```
高级定时器
|
+-- CH1/CH1N：Phase U
+-- CH2/CH2N：Phase V
+-- CH3/CH3N：Phase W
+-- TRGO：触发 ADC
+-- BKIN：过流硬件关断
+-- DMA：装载下一周期 CCR
```

#### 核心代码框架

```
typedef struct {
    uint16_t u;
    uint16_t v;
    uint16_t w;
} svm_compare_t;

static void inverter_apply_compare(const svm_compare_t *cmp)
{
    if (cmp == NULL) {
        return;
    }

    /*
     * 三相比较值应在同一个更新事件统一生效，
     * 避免 U/V/W 三相跨周期不同步。
     */
    TIM1->CCR1 = cmp->u;
    TIM1->CCR2 = cmp->v;
    TIM1->CCR3 = cmp->w;
}

void inverter_fault_isr(void)
{
    TIM1->BDTR |= TIM_BDTR_MOE_DISABLE;
    inverter_state = INVERTER_FAULT_LATCHED;
}
```

#### 设计要点

- 不能分别在普通任务中更新三个 CCR。
- 采样点必须避开开关瞬间和死区。
- 需要处理低调制度下的最小脉宽限制。
- 过流故障应锁存，重新启动前必须完成故障原因确认和功率级放电。

### 案例三：工业 LED 恒流调光

#### 需求

- PWM 频率 2 kHz。
- 调光范围 0.1%~100%。
- 多通道亮度同步变化。
- 摄像系统下避免明显频闪。

#### 设计方案

- 使用一个定时器的多个通道，保证公共周期。
- 使用 DMA 或更新事件同步加载所有通道 CCR。
- 亮度输入使用 16 位定点值。
- 对低亮度区进行 Gamma 校正，但 Gamma 表不直接等同于电流线性。

```
uint16_t led_gamma_to_duty(uint16_t brightness)
{
    /* gamma_table 应由离线工具生成并经过标定。 */
    if (brightness >= 65535U) {
        return 1000U;
    }

    return gamma_table[brightness >> 8];
}
```

设计重点是区分：

```
PWM 占空比线性
!=
人眼感知亮度线性
!=
摄像机曝光下的图像亮度线性
```

---

## 12. 高频问题深度答疑

### 问题一：PWM 频率越高越好吗？

不是。

提高频率可以：

- 降低电流纹波。
- 减小可闻噪声。
- 提高控制环更新频率。

但会增加：

- MOSFET 开关损耗。
- 栅极驱动损耗。
- EMI。
- 定时器分辨率压力。
- ADC 采样和控制算法的实时性要求。

实际频率应由负载、电感、开关器件、EMI 和控制环带宽共同决定。

### 问题二：LED 和电机是否使用同样的 PWM 频率？

通常不一样。

LED 关注频闪、摄像兼容性和调光分辨率，常见为数百 Hz 到数十 kHz。电机关注电流纹波、声噪声和开关损耗，常见为 10~25 kHz。必须根据负载响应和功率级参数选定。

### 问题三：为什么占空比写 50%，示波器测到不是 50%？

可能原因：

- `ARR` 计算错误。
- 定时器时钟实际频率错误。
- `CCR` 和 `ARR` 的计数边界语义不同。
- 输出极性配置反向。
- 示波器测量阈值不合适。
- 上升沿和下降沿传播延迟不同。
- 死区或驱动器延迟影响了功率节点，而不是 MCU 引脚。

应分别测量：

```
MCU 定时器引脚
驱动器输入
驱动器输出
MOSFET 栅极
功率开关节点
```

### 问题四：为什么开启 CCR 预装载后，占空比更新晚一个周期？

这是正常现象。

预装载寄存器和活动寄存器分离后，CPU 写入的是影子寄存器。只有在更新事件到来时，新值才转移到活动寄存器。这保证了波形完整性，但会引入最多一个 PWM 周期的更新延迟。

如果控制环允许，应优先保留该机制，而不是为了降低一个周期延迟而关闭预装载。

### 问题五：中心对齐为什么频率变成预期的一半？

因为计数器需要完成：

```
0 -> ARR
ARR -> 0
```

一个完整 PWM 周期包含两段计数过程。因此：

```
f_center = f_timer / (2 * (PSC + 1) * ARR)
```

不同 MCU 对 `ARR` 边界和更新事件定义可能存在差异，应以参考手册公式为准。

### 问题六：软件 PWM 什么时候仍然值得使用？

以下场景可以考虑：

- PWM 频率低。
- 通道数量少。
- 输出允许微秒级抖动。
- 没有足够的硬件定时器通道。
- 需要复杂的非标准波形。
- CPU 资源充足且已有统一时间基准。

但软件 PWM 不适合：

- 栅极驱动。
- 高速电机控制。
- 需要严格同步 ADC 的系统。
- 对故障响应时间有硬性要求的功率系统。

---

## 13. 课程核心总结

核心结论：

1. PWM 本质是**定时器计数器与比较寄存器的硬件时序关系**。
2. 频率由定时器时钟、预分频器和周期寄存器共同决定。
3. 占空比分辨率由周期计数值决定，频率越高，通常可用分辨率越低。
4. 动态更新应使用 CCR/ARR 预装载和更新事件。
5. 电机及功率变换应优先使用中心对齐、互补输出、死区和硬件 Break。
6. 软件 PWM 的主要代价是 CPU 占用和边沿抖动。
7. 故障关闭必须优先走硬件路径，不能依赖 RTOS 调度。
8. PWM 参数必须通过示波器、逻辑分析仪和功率级波形共同验证。

性能和可靠性排序：

```
硬件 PWM + 影子寄存器 + DMA + 硬件故障关闭
>
硬件 PWM + 中断更新
>
硬件定时器中断翻转 GPIO
>
普通软件 PWM
```

通用选型结论：

```
普通执行器  -> 边沿对齐硬件 PWM
电机控制    -> 中心对齐硬件 PWM
半桥功率级  -> 互补 PWM + 死区 + Break
同步采样    -> PWM 触发 ADC + DMA
低速简单输出 -> 软件 PWM 可接受
```

---

## 14. 快速参考速查表

### 场景选型表

|场景|频率参考|模式|关键配置|
|---|---|---|---|
|LED 调光|500 Hz~20 kHz|边沿对齐|多通道同步|
|DC 电机|10~25 kHz|边沿或中心对齐|电流保护|
|PMSM|10~40 kHz|中心对齐|互补、死区、ADC 触发|
|蜂鸣器|1~4 kHz|边沿对齐|频率可调|
|舵机|50 Hz|边沿对齐|脉宽 1~2 ms|
|加热器|0.1~10 Hz 时间比例|低频 PWM|继电器寿命和热惯性|

### 特性对比表

|项目|公式或原则|
|---|---|
|周期|`T = 1 / f_pwm`|
|边沿对齐频率|`f = f_timer / ((PSC+1)(ARR+1))`|
|中心对齐频率|`f = f_timer / (2(PSC+1)ARR)`|
|占空比|`D = CCR / period_ticks`|
|分辨率|`log2(period_ticks)`|
|最小步进|`1 / period_ticks`|
|死区下限|大于关断延迟、驱动延迟和通道偏差之和|
|运行时更新|优先写入影子寄存器|
|故障关闭|优先使用硬件 Break|

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  给定定时器时钟和目标频率，计算 `PSC`、`ARR`。
- [ ]  计算指定 `CCR` 对应的实际占空比。
- [ ]  解释边沿对齐和中心对齐 PWM 的计数过程。
- [ ]  解释为什么 CCR 预装载可以避免输出毛刺。
- [ ]  识别 `CCR=ARR` 是否能实现真正的 100% 输出。
- [ ]  分析软件 PWM 的 CPU 占用和最坏抖动。
- [ ]  为半桥选择合理的死区时间。
- [ ]  设计硬件过流关闭和软件故障锁存流程。
- [ ]  说明定时器时钟与 APB 总线时钟可能不相等的原因。
- [ ]  使用示波器验证 MCU 引脚、栅极和功率节点的 PWM 波形。
- [ ]  设计多通道 PWM 的同步更新机制。
- [ ]  说明 PWM 频率、分辨率、开关损耗之间的工程权衡。

---

## 16. 实践与进阶路径

### 阶梯实战任务

1. **基础任务**
    
    - 配置一个 1 kHz PWM。
    - 通过串口修改占空比。
    - 验证 `0%`、`25%`、`50%`、`100%` 波形。
2. **驱动任务**
    
    - 封装 `pwm_init()`、`pwm_start()`、`pwm_stop()`、`pwm_set_duty()`。
    - 增加参数校验、状态机和故障状态。
    - 对频率和占空比变化进行单元测试。
3. **同步任务**
    
    - 使用三个通道同时输出不同占空比。
    - 在更新事件统一加载 CCR。
    - 使用逻辑分析仪验证三相边沿一致性。
4. **控制任务**
    
    - 驱动有刷直流电机。
    - 增加电流采样、速度反馈和 PI 控制。
    - 验证启动、堵转、突加负载和故障恢复。
5. **功率任务**
    
    - 配置互补 PWM、死区和 Break。
    - 使用示波器测量上下管栅极。
    - 注入过流信号，验证硬件关闭时间。

### 性能测试方法

测试项目：

```
1. PWM 频率误差
2. 占空比误差
3. 周期间抖动
4. CCR 更新延迟
5. CPU 占用率
6. DMA 总线占用
7. 故障关断延迟
8. 死区实际时间
9. 最小有效脉宽
10. 温升与开关损耗
```

建议测量方法：

- 用逻辑分析仪测量连续 10,000 个周期，统计平均周期、最大周期和最小周期。
- 用示波器同时测量 PWM 输入、栅极输出和功率节点。
- 使用 GPIO 打点统计 ISR 执行时间。
- 使用 DWT Cycle Counter 或高精度定时器测量更新延迟。
- 在不同系统负载、RTOS 中断压力和 Cache 状态下重复测试。
- 使用电流探头确认死区、反向恢复和开关瞬态。

### 进阶学习方向

- 定时器触发 ADC 和同步采样。
- DMA 环形缓冲与 PWM 波形表输出。
- SVPWM、正弦 PWM 和空间矢量调制。
- 高级定时器 Break、锁存故障和安全状态。
- PWM 与电流环、速度环、位置环协同设计。
- 功率器件开关损耗、EMI 和栅极电阻优化。
- 多定时器同步、相位偏移和交错 PWM。
- RTOS 下 PWM 参数更新的锁和无锁设计。
- 基于示波器数据建立 PWM 驱动自动化回归测试。