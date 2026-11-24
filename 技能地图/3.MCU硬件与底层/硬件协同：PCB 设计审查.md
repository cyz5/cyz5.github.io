

## 1. 学习目标

### 理解

- 理解 **PCB 不是原理图的物理复制品，而是电源完整性、信号完整性、热、EMC 与可制造性的耦合系统**。
- 理解器件封装、叠层、回流路径、寄生参数、结构件和固件时序之间的相互影响。
- 理解原理图审查、布局审查、布线审查、生产资料审查的不同目标。

### 掌握

- 掌握 MCU/SoC 最小系统、电源树、时钟、复位、启动配置和调试接口的审查方法。
- 掌握高速数字、模拟采样、开关电源、通信接口的关键审查规则。
- 掌握 ERC、DRC、网表比对、阻抗约束、回流路径和电流密度检查。
- 掌握基于风险分级的 PCB Review Checklist。

### 精通

- 精通从功能、性能、可靠性、EMC、热设计、DFM、DFT、DFX 多维度发现系统性缺陷。
- 能够量化评估过孔寄生、电源压降、温升、串扰、反射、地弹和采样误差。
- 能够定位“原理图正确但整机不稳定”的跨域问题。

### 能够设计

- 能够建立企业级硬件设计审查流程、门禁条件和缺陷闭环机制。
- 能够设计硬件、固件、结构、测试、生产联合评审体系。
- 能够为新平台建立可复用的叠层模板、布局模板、接口保护模板和自检框架。

---

## 2. 前置要求

### 知识要求

- MCU/SoC 启动流程、GPIO、电源域、时钟树和复位系统。
- LDO、Buck、Boost、MOSFET、运放、ADC、晶振等基础电路。
- 传输线、阻抗、反射、串扰、回流路径和寄生参数基础。
- UART、SPI、I²C、CAN、USB、Ethernet 等接口原理。
- EMC、ESD、EFT、浪涌及共模/差模干扰基础。
- PCB 制造、SMT、回流焊、AOI、ICT 和功能测试基本流程。

### 技能要求

- 能够阅读原理图、PCB、BOM、Gerber、ODB++ 等工程资料。
- 能够使用示波器、电流探头、差分探头、逻辑分析仪和万用表。
- 能够分析 MCU 数据手册中的电气参数、封装和参考设计。
- 能够编写板级自检程序并通过寄存器验证硬件状态。
- 能够区分设计规则、经验规则和产品级约束。

---

## 3. 技术概述

### 3.1 核心定义

**硬件协同**是指硬件、PCB、固件、结构、测试和生产团队围绕统一系统约束进行联合设计，而不是各专业完成后再被动集成。

**PCB 设计审查**是对以下设计对象进行系统验证：

1. 原理图逻辑正确性。
2. 器件选型和参数裕量。
3. PCB 叠层与阻抗规划。
4. 器件布局与电流路径。
5. 高速信号和回流路径。
6. 电源完整性与去耦网络。
7. EMC、ESD 和接口防护。
8. 热设计与结构约束。
9. 可制造性、可测试性和可维护性。
10. 固件可启动、可诊断、可升级和可恢复能力。

### 3.2 技术价值

设计缺陷越晚发现，修复成本越高：

```
原理图阶段发现
└─ 修改成本：1×

PCB 布局阶段发现
└─ 修改成本：约 3×～5×

样机阶段发现
└─ 修改成本：约 10×～30×

认证或试产阶段发现
└─ 修改成本：约 50×～200×

批量交付后发现
└─ 可能触发返工、召回、停线和客户索赔
```

审查的目标不是保证“板子能亮”，而是保证：

- **所有边界条件下可启动**
- **全温、全压、全负载稳定运行**
- **满足 EMC 与可靠性目标**
- **能够批量制造和测试**
- **现场失效可诊断、可恢复**

### 3.3 主流审查分类

|审查类型|主要对象|核心输出|
|---|---|---|
|架构审查|系统框图、电源树、接口分配|架构风险清单|
|原理图审查|网络连接、选型、参数|原理图缺陷闭环|
|布局审查|功能分区、关键器件位置|布局冻结条件|
|布线审查|阻抗、回流、串扰、电流|布线风险报告|
|DFM 审查|板厂、SMT、拼板、钢网|可制造性报告|
|DFT 审查|测试点、边界扫描、自检|测试覆盖率报告|
|EMC 审查|滤波、屏蔽、接口防护|EMC 预测与整改项|
|热审查|热源、铜皮、过孔、风道|热仿真或温升结果|
|发布审查|Gerber、BOM、坐标、版本|Release Checklist|

---

## 4. 核心特性横向对比

### 4.1 审查方式对比

|维度|人工 Checklist|EDA 自动规则|仿真分析|样机实测|
|---|---|---|---|---|
|连接错误发现能力|中|高|低|中|
|回流路径问题|高|低～中|高|高|
|阻抗问题|中|中|高|高|
|电源瞬态问题|中|低|高|高|
|EMC 风险|高度依赖经验|低|中～高|最高|
|热风险|中|低|高|最高|
|成本|低|低|中～高|高|
|设计阶段适用性|全阶段|原理图/PCB|布线前后|样机阶段|
|可重复性|中|高|高|中～高|
|主要局限|依赖专家|只能检查已编码规则|模型存在误差|发现时间较晚|

**结论：工业级审查必须采用“人工规则 + 自动规则 + 仿真 + 实测”的组合方式。**

### 4.2 典型 PCB 层数对比

|方案|典型用途|优点|主要风险|
|---|---|---|---|
|2 层板|低速、低密度、成本敏感|成本低、加工简单|回流路径差、EMC 风险高|
|4 层板|通用 MCU、工业控制|可提供完整地平面|电源平面和信号层资源有限|
|6 层板|高速 MCU、DDR、Ethernet|回流连续、分层灵活|叠层规划复杂|
|8 层及以上|SoC、DDR、高速通信|SI/PI 控制能力强|成本、加工公差和过孔复杂度高|

### 4.3 去耦方案对比

|方案|高频性能|低频储能|成本|适用场景|
|---|---|---|---|---|
|单颗大电容|差|高|低|低频负载|
|多容量并联|中～高|高|中|通用数字系统|
|同容量多颗并联|高|中|中|降低等效阻抗|
|电容阵列 + 平面对|最高|高|高|FPGA、SoC、高速处理器|
|大量不同容值无仿真并联|不确定|高|高|可能形成反谐振，不推荐|

---

## 5. 底层原理与功能特性深度解析

### 5.1 审查 MCU 最小系统

最小系统至少包括：

- 所有电源域及对应去耦。
- 模拟电源、参考电压和地处理。
- 主时钟与低速时钟。
- 上电复位、外部复位和看门狗。
- 启动模式配置。
- SWD/JTAG 调试接口。
- 未使用引脚处理。
- 下载、量产和失效恢复路径。

#### 关键风险

1. 电源引脚遗漏。
2. VDDA 没有单独滤波。
3. VCAP 引脚误接普通电源。
4. BOOT 引脚悬空。
5. NRST 电容过大导致调试器无法复位。
6. SWD 引脚被外围强驱动。
7. 晶振负载电容仅按经验选取。

#### 板级启动诊断代码

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    BOARD_BOOT_OK = 0,
    BOARD_BOOT_ERR_CLOCK,
    BOARD_BOOT_ERR_POWER,
    BOARD_BOOT_ERR_RESET_CAUSE,
    BOARD_BOOT_ERR_CONFIG
} board_boot_status_t;

typedef struct {
    uint32_t reset_flags;
    uint32_t core_clock_hz;
    uint16_t vdda_mv;
    bool external_clock_ready;
} board_boot_diag_t;

static bool board_clock_is_valid(uint32_t actual_hz, uint32_t expected_hz)
{
    const uint32_t tolerance_ppm = 10000U; /* 启动阶段允许 ±1% */
    uint64_t error = (actual_hz > expected_hz)
                   ? (uint64_t)(actual_hz - expected_hz)
                   : (uint64_t)(expected_hz - actual_hz);

    return (error * 1000000ULL) <=
           ((uint64_t)expected_hz * tolerance_ppm);
}

board_boot_status_t board_boot_diagnose(board_boot_diag_t *diag)
{
    if (diag == NULL) {
        return BOARD_BOOT_ERR_CONFIG;
    }

    diag->reset_flags = platform_get_reset_flags();
    diag->core_clock_hz = platform_measure_core_clock();
    diag->vdda_mv = platform_measure_vdda_mv();
    diag->external_clock_ready = platform_external_clock_ready();

    if ((diag->vdda_mv < 3000U) || (diag->vdda_mv > 3600U)) {
        return BOARD_BOOT_ERR_POWER;
    }

    if (!diag->external_clock_ready ||
        !board_clock_is_valid(diag->core_clock_hz, 168000000U)) {
        return BOARD_BOOT_ERR_CLOCK;
    }

    if ((diag->reset_flags & RESET_FLAG_BROWNOUT) != 0U) {
        return BOARD_BOOT_ERR_RESET_CAUSE;
    }

    return BOARD_BOOT_OK;
}
```

**设计要点：**

- 启动第一阶段应保存复位源，避免初始化代码提前清除标志。
- 使用内部时钟启动，再切换外部晶振，可以提高失效可诊断性。
- 电源电压检测必须使用内部基准校准，不能直接假定 ADC 参考电压恒定。

---

### 5.2 电源完整性审查

负载瞬态发生时，电源网络必须同时满足：

ΔV=ΔI×ZPDNΔV=ΔI×ZPDN​

目标阻抗为：

Ztarget=ΔVallowΔIstepZtarget​=ΔIstep​ΔVallow​​

例如，1.2 V 内核电源允许波动 30 mV，负载阶跃 1.5 A：

Ztarget=0.031.5=20mΩZtarget​=1.50.03​=20mΩ

因此，在关注频段内，PDN 阻抗原则上应低于 **20 mΩ**。

#### 去耦电容实际模型

实际电容包含：

- 电容量 CC
- 等效串联电阻 ESR
- 等效串联电感 ESL
- PCB 走线和过孔电感

阻抗近似为：

Z(jω)=ESR+jωESL+1jωCZ(jω)=ESR+jωESL+jωC1​

谐振频率：

fr=12πESL⋅Cfr​=2πESL⋅C​1​

#### 电源监控代码

```
typedef struct {
    uint16_t min_mv;
    uint16_t max_mv;
    uint16_t sample_count;
    uint16_t violation_count;
} rail_monitor_t;

bool rail_monitor_sample(rail_monitor_t *monitor, uint16_t voltage_mv)
{
    if ((monitor == NULL) || (monitor->sample_count == UINT16_MAX)) {
        return false;
    }

    monitor->sample_count++;

    if ((voltage_mv < monitor->min_mv) ||
        (voltage_mv > monitor->max_mv)) {
        monitor->violation_count++;
        return false;
    }

    return true;
}
```

#### 审查重点

- 去耦电容是否靠近对应电源引脚，而不是仅仅“在芯片附近”。
- 电流是否按照“电源平面 → 电容 → 芯片引脚”最短路径流动。
- 电容地端是否通过独立近端地过孔连接完整地平面。
- 开关电源高 di/dt 回路是否最小化。
- 反馈网络是否远离 SW 节点、电感和栅极驱动走线。
- 模拟参考电压是否被数字负载共享。

---

### 5.3 回流路径审查

高速信号电流不会选择几何最短路径，而是选择 **高频阻抗最低路径**。当信号参考完整平面时，回流电流集中在信号正下方。

以下情况会迫使回流绕行：

- 信号跨越地平面分割。
- 信号换层但附近无回流过孔。
- 参考平面从 GND 切换到 Power，缺少跨接电容。
- 接口共模电流无法在连接器附近闭合。

换层时，信号过孔旁应配置参考地缝合过孔。其目标不是降低直流电阻，而是减少回流环路面积和寄生电感。

#### GPIO 边沿控制代码

```
typedef enum {
    GPIO_SLEW_LOW,
    GPIO_SLEW_MEDIUM,
    GPIO_SLEW_HIGH
} gpio_slew_t;

static gpio_slew_t select_slew_rate(uint32_t signal_hz,
                                    uint32_t trace_length_mm)
{
    /*
     * 边沿速度比协议频率更关键。
     * 短距离低速控制信号优先使用低驱动速度，减少 EMI。
     */
    if ((signal_hz <= 1000000U) && (trace_length_mm <= 100U)) {
        return GPIO_SLEW_LOW;
    }

    if (signal_hz <= 25000000U) {
        return GPIO_SLEW_MEDIUM;
    }

    return GPIO_SLEW_HIGH;
}
```

**工程原则：不要默认选择最高 GPIO Speed。**  
更高驱动速度会缩短边沿，但也会增加过冲、地弹、串扰和辐射。

---

### 5.4 信号完整性审查

是否按传输线处理，取决于信号边沿时间，而不只是时钟频率。

经验判断：

Lcritical≈vp⋅tr6Lcritical​≈6vp​⋅tr​​

其中：

- vpvp​：PCB 上信号传播速度，常见约为真空光速的 50%～70%。
- trtr​：信号上升时间。
- LcriticalLcritical​：达到该长度后应重点考虑传输线效应。

假设传播速度为 160 mm/ns，上升时间为 1 ns：

Lcritical≈160×16≈26.7mmLcritical​≈6160×1​≈26.7mm

因此，即使信号频率只有 1 MHz，只要边沿为 1 ns，长度达到数厘米仍可能出现明显反射。

#### 端接方案

|端接类型|位置|优点|局限|
|---|---|---|---|
|源端串联端接|驱动端|功耗低、成本低|点到多点效果有限|
|并联端接|接收端|吸收反射效果好|静态功耗较大|
|Thevenin 端接|接收端|可匹配偏置电平|器件多、功耗较大|
|AC 端接|接收端|降低直流功耗|低频波形可能失真|
|片内端接|芯片内部|布局简单|阻值精度和模式受芯片限制|

#### 自适应 SPI 速率降级框架

```
typedef struct {
    uint32_t frequency_hz;
    uint32_t crc_errors;
    uint32_t timeout_errors;
} spi_link_state_t;

static const uint32_t spi_rate_table[] = {
    50000000U,
    25000000U,
    12000000U,
    6000000U
};

bool spi_link_train(spi_link_state_t *state)
{
    if (state == NULL) {
        return false;
    }

    for (uint32_t i = 0U;
         i < (sizeof(spi_rate_table) / sizeof(spi_rate_table[0]));
         ++i) {
        platform_spi_set_frequency(spi_rate_table[i]);
        state->frequency_hz = spi_rate_table[i];
        state->crc_errors = 0U;
        state->timeout_errors = 0U;

        if (platform_spi_run_integrity_test(1000U,
                                            &state->crc_errors,
                                            &state->timeout_errors) &&
            (state->crc_errors == 0U) &&
            (state->timeout_errors == 0U)) {
            return true;
        }
    }

    return false;
}
```

该机制不能替代正确 PCB 设计，但可用于：

- 样机阶段快速识别信号裕量。
- 量产测试筛查焊接或器件异常。
- 现场降级运行并记录故障。

---

### 5.5 差分信号审查

差分对的关键不是“绝对等长”，而是：

- 差分阻抗满足接口要求。
- 对内时延偏差受控。
- 参考平面连续。
- 两线周围电磁环境基本对称。
- 过孔数量、层切换和连接器引脚路径对称。
- 避免一根线靠近铜皮而另一根线靠近板边。

对内长度偏差产生的时延约为：

Δt=ΔLvpΔt=vp​ΔL​

若传播速度取 160 mm/ns，长度差 8 mm：

Δt=8160=50psΔt=1608​=50ps

是否可接受，应根据接收器抖动预算、眼图裕量和协议要求决定，不能使用统一的“5 mil 等长”规则。

---

### 5.6 模拟与 ADC 审查

ADC 输入并非无限阻抗。采样瞬间，内部采样电容通过开关连接到外部信号源。

采样建立误差近似为：

Verror=Vstep⋅e−tacq/(RsourceCsample)Verror​=Vstep​⋅e−tacq​/(Rsource​Csample​)

要达到 N 位精度，近似要求：

tacq≥(N+1)ln⁡(2)⋅RsourceCsampletacq​≥(N+1)ln(2)⋅Rsource​Csample​

例如：

- 12 位 ADC
- Rsource=10kΩRsource​=10kΩ
- Csample=10pFCsample​=10pF

则：

tacq≥13×0.693×10k×10pF≈0.9μstacq​≥13×0.693×10k×10pF≈0.9μs

如果采样时间只有 100 ns，即使直流电压正确，也会出现明显采样误差。

#### ADC 启动自校准

```
typedef struct {
    uint16_t ground_code;
    uint16_t reference_code;
    uint16_t full_scale_code;
} adc_self_test_t;

bool adc_run_self_test(adc_self_test_t *result)
{
    if (result == NULL) {
        return false;
    }

    platform_adc_calibrate();

    result->ground_code = platform_adc_read_channel(ADC_CH_GND);
    result->reference_code = platform_adc_read_channel(ADC_CH_INTERNAL_REF);
    result->full_scale_code = platform_adc_read_channel(ADC_CH_VDDA);

    if (result->ground_code > 8U) {
        return false;
    }

    if ((result->reference_code < ADC_REF_MIN_CODE) ||
        (result->reference_code > ADC_REF_MAX_CODE)) {
        return false;
    }

    if (result->full_scale_code < 4000U) {
        return false;
    }

    return true;
}
```

---

### 5.7 时钟与晶振审查

晶振负载电容关系近似为：

CL=C1C2C1+C2+CstrayCL​=C1​+C2​C1​C2​​+Cstray​

当 C1=C2=CC1​=C2​=C：

C≈2(CL−Cstray)C≈2(CL​−Cstray​)

不能直接使用“晶振标称负载电容的两倍”，因为：

- MCU 引脚存在输入电容。
- PCB 焊盘和走线存在寄生电容。
- 示波器探头会改变振荡条件。
- 不同晶振的 ESR 和驱动等级不同。

#### 审查重点

- 晶振和负载电容是否紧贴 MCU。
- 晶振回路下方是否避免高速走线。
- 晶振两端是否避免测试点和长支路。
- 驱动等级是否低于晶体最大允许功耗。
- 是否具备外部时钟失效后的降级策略。

---

### 5.8 EMC 与接口防护审查

典型接口保护路径应遵循：

```
外部连接器
├─ ESD/浪涌泄放器件
├─ 共模或差模滤波
├─ 串联阻尼/限流
├─ 收发器
└─ MCU/SoC
```

布局顺序错误会导致保护器件失效。例如 TVS 放在板内深处时，瞬态电流先经过长走线，产生：

V=L⋅didtV=L⋅dtdi​

若走线寄生电感为 10 nH，瞬态电流变化率为 10 A/ns：

V=10nH×10A/ns=100VV=10nH×10A/ns=100V

即使 TVS 的钳位电压较低，芯片端仍可能承受额外寄生电压。

---

## 6. 性能量化分析

以下数据用于建立审查量级感。实际结果必须结合具体叠层、材料、器件、温度和测试带宽验证。

### 6.1 基准平台

```
处理器：Cortex-M7，主频 400 MHz
PCB：6 层，1.6 mm，外层 1 oz 铜
电源：3.3 V / 1.2 V / 5 V
主要接口：RMII Ethernet、USB 2.0 FS、QSPI、CAN FD
测试环境：25°C，12 V 输入，典型业务负载
示波器带宽：500 MHz
差分探头带宽：500 MHz
电流探头带宽：100 MHz
```

### 6.2 典型问题量化

|项目|优化前参考值|优化后参考值|主要措施|
|---|---|---|---|
|1.2 V 电源峰峰值纹波|82 mV|31 mV|缩短去耦回路、增加平面对电容|
|3.3 V 负载瞬态跌落|210 mV|75 mV|降低 PDN 阻抗、优化补偿|
|QSPI CLK 过冲|1.1 V|0.28 V|源端串联 22～33 Ω|
|SPI CRC 错误率|约 10−510−5|未观测到错误|阻尼、完整参考面、降低边沿|
|ADC 空载噪声|14.2 LSB RMS|3.8 LSB RMS|模拟地回流、参考滤波、RC 输入|
|MCU 热点温升|43°C|27°C|底部散热过孔、扩大内层铜|
|CAN 接口 EFT 复位|频繁发生|测试中未复现|接口泄放、共模路径、复位滤波|

这些数值只能作为工程量级参考，不能替代目标板测量。

### 6.3 过孔寄生估算

普通通孔的寄生电感通常处于亚纳亨到数纳亨量级，具体取决于孔径、板厚、焊盘和回流结构。

高频阻抗：

XL=2πfLXL​=2πfL

假设：

- L=1nHL=1nH
- f=500MHzf=500MHz

则：

XL=2π×500MHz×1nH≈3.14ΩXL​=2π×500MHz×1nH≈3.14Ω

这说明在高频下，去耦电容距离电源引脚仅增加一个不合理过孔，也可能显著降低效果。

### 6.4 铜线压降和功耗

直流电阻：

R=ρLWtR=ρWtL​

其中铜电阻率近似为：

ρ≈1.72×10−8Ω⋅mρ≈1.72×10−8Ω⋅m

功耗：

P=I2RP=I2R

审查时不能只判断走线“是否烧毁”，还应检查：

- 压降是否影响负载最低工作电压。
- 温升是否影响附近晶振、基准源和传感器。
- 脉冲电流是否造成局部地电位变化。
- 内层走线散热是否弱于外层。

### 6.5 时间开销

|审查活动|中等复杂度 MCU 板典型投入|
|---|---|
|架构与电源树审查|2～4 人时|
|原理图逐页审查|4～8 人时|
|关键布局审查|3～6 人时|
|完整布线审查|6～16 人时|
|DFM/DFT 审查|2～6 人时|
|Release 资料检查|1～3 人时|

复杂 SoC、DDR、高速 SerDes、隔离电源或高压系统的投入通常显著增加。

### 6.6 主要瓶颈与优化收益

|瓶颈|根因|优化手段|预期收益|
|---|---|---|---|
|Review 依赖个人经验|规则未沉淀|Checklist + EDA 规则化|降低漏检|
|问题发现过晚|布线完成后才审查|分阶段 Gate Review|降低返工|
|仿真与实测不一致|模型和探测方法错误|校准模型与探头连接|提高预测可信度|
|固件无法辅助定位|无板级诊断设计|启动日志、自检、测试模式|缩短定位时间|
|DFM 问题重复出现|板厂反馈未闭环|制造规则库版本化|提高一次投板成功率|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
开始 PCB 审查
├─ 是否包含高速接口或边沿小于 2 ns？
│  ├─ 是
│  │  ├─ 是否已有受控阻抗叠层？
│  │  │  ├─ 否 → 先冻结叠层与阻抗，再开始关键布线
│  │  │  └─ 是 → 检查阻抗、回流、过孔、端接和串扰
│  │  └─ 是否包含多负载或连接器？
│  │     ├─ 是 → 进行拓扑与端接仿真
│  │     └─ 否 → 至少完成点到点反射检查
│  └─ 否
│     └─ 重点检查回流、电源、EMC 和 GPIO 边沿
│
├─ 是否存在大电流、开关电源或电机负载？
│  ├─ 是 → 检查高 di/dt 回路、铜厚、压降、温升和地弹
│  └─ 否 → 执行常规 PDN 和热检查
│
├─ 是否连接外部线缆？
│  ├─ 是 → 必须检查 ESD/EFT/浪涌、共模路径和接口地
│  └─ 否 → 重点控制板内串扰和辐射
│
├─ 是否包含高精度 ADC/DAC/传感器？
│  ├─ 是 → 独立审查参考源、采样建立、地回流和热梯度
│  └─ 否 → 常规模拟审查
│
└─ 是否进入量产发布？
   ├─ 是 → 执行 DFM、DFT、BOM、坐标、Gerber 和版本审查
   └─ 否 → 记录风险并进入下一设计 Gate
```

### 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|低成本低速传感器节点|2～4 层板，完整地铜优先|控制成本，同时避免地平面碎片化|
|工业 MCU 控制器|4～6 层板，独立完整地平面|提升 EMC、回流和电源稳定性|
|高精度数据采集|模数分区但保持连续参考地|避免粗暴分割地导致回流绕行|
|电机控制器|功率与控制分区、Kelvin 采样|降低开关噪声和电流采样误差|
|Ethernet/USB 网关|受控阻抗、连接器端防护|控制信号完整性和线缆共模干扰|
|高可靠安全控制器|双电源监控、独立看门狗、DFT|提高失效检测和恢复能力|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **先定义约束，再开始布局。**
2. **先处理关键电流环路，再处理几何美观。**
3. **优先保证参考平面连续，而不是追求表面等长。**
4. **高速信号按照边沿时间审查，而不是仅按协议频率。**
5. **外部瞬态必须在连接器入口处处理。**
6. **模拟地和数字地的关键是电流路径管理，而非机械切割。**
7. **硬件必须为固件诊断和生产测试提供可观测点。**
8. **所有 Review 缺陷必须有责任人、严重级别和关闭证据。**

### 8.2 选型决策矩阵

评分建议：

- 1：差
- 3：可接受
- 5：优秀

|方案|SI|PI|EMC|成本|热性能|可制造性|
|---|---|---|---|---|---|---|
|2 层低成本板|1|2|1|5|2|5|
|4 层标准板|3|3|3|4|3|5|
|6 层高速板|4|4|4|3|4|4|
|8 层 HDI|5|5|5|1|4|2|

权重应由产品目标决定。例如工业通信设备可使用：

```
SI          20%
PI          20%
EMC         25%
可靠性      15%
成本        10%
可制造性    10%
```

### 8.3 工业级审查规范

每个问题必须记录：

```
问题编号：
设计版本：
页面/坐标：
网络名称：
问题描述：
失效模式：
严重级别：
建议措施：
责任人：
计划关闭时间：
验证证据：
最终状态：
```

缺陷严重度建议：

|等级|定义|处理要求|
|---|---|---|
|Blocker|可能导致安全事故、无法启动或大规模损坏|禁止投板|
|Critical|高概率功能失效、认证失败或批量风险|必须关闭|
|Major|性能、可靠性或可维护性不足|原则上关闭|
|Minor|标识、规范、可读性问题|发布前处理或接受风险|
|Suggestion|优化建议|项目组决策|

---

## 9. 常见错误与避坑指南

### 9.1 错误一：BOOT、复位或中断引脚悬空

#### 错误代码

```
void board_init(void)
{
    /*
     * 错误：假设外部 BOOT 和中断引脚始终具有确定电平。
     * PCB 上如果缺少上下拉，启动模式和中断状态可能随机。
     */
    if (gpio_read(BOOT_MODE_PIN)) {
        enter_bootloader();
    }
}
```

#### 根因分析

- CMOS 输入阻抗高，悬空引脚容易被泄漏电流和外部噪声改变。
- 上电阶段 MCU 内部上下拉可能尚未生效。
- 测试探头、潮湿、污染和邻近开关节点均可能改变电平。

#### 正确实现

硬件上配置确定性上下拉，固件增加去抖和一致性判断：

```
static bool read_strap_pin_stable(uint32_t pin)
{
    uint32_t high_count = 0U;

    for (uint32_t i = 0U; i < 16U; ++i) {
        if (gpio_read(pin)) {
            high_count++;
        }
        platform_delay_us(50U);
    }

    return high_count >= 14U;
}

void board_init(void)
{
    if (read_strap_pin_stable(BOOT_MODE_PIN)) {
        enter_bootloader();
    }
}
```

#### 风险影响

- 偶发进入 Bootloader。
- 上电不启动。
- 中断风暴。
- EMC 测试中随机复位或模式切换。

---

### 9.2 错误二：所有 GPIO 配置为最高速度

#### 错误代码

```
void gpio_init(void)
{
    gpio_config_t config = {
        .mode = GPIO_MODE_OUTPUT,
        .speed = GPIO_SPEED_VERY_HIGH,
        .pull = GPIO_PULL_NONE
    };

    gpio_configure(STATUS_LED_PIN, &config);
    gpio_configure(RELAY_ENABLE_PIN, &config);
    gpio_configure(SPI_CLK_PIN, &config);
}
```

#### 根因分析

GPIO 速度配置通常控制输出驱动强度或边沿速度，不等于协议频率。无差别使用最高速度会增加：

- 过冲和振铃。
- 电源瞬态电流。
- 地弹和同步开关噪声。
- 串扰和辐射发射。

#### 正确实现

```
void gpio_init(void)
{
    gpio_config_output(STATUS_LED_PIN,
                       GPIO_SPEED_LOW,
                       GPIO_PULL_NONE);

    gpio_config_output(RELAY_ENABLE_PIN,
                       GPIO_SPEED_LOW,
                       GPIO_PULL_DOWN);

    gpio_config_alternate(SPI_CLK_PIN,
                          GPIO_AF_SPI,
                          GPIO_SPEED_MEDIUM,
                          GPIO_PULL_NONE);
}
```

#### 风险影响

- EMC 辐射超限。
- SPI、SDIO 等接口偶发数据错误。
- 邻近复位、中断或模拟信号被串扰触发。

---

### 9.3 错误三：ADC 采样时间与源阻抗不匹配

#### 错误代码

```
uint16_t read_temperature(void)
{
    adc_set_sample_cycles(ADC_CH_TEMP, 2U);
    return adc_read(ADC_CH_TEMP);
}
```

#### 根因分析

传感器输出经过高阻分压或 RC 滤波后，无法在极短采样窗口内为 ADC 内部采样电容充电。

#### 正确实现

```
uint16_t read_temperature(void)
{
    uint32_t accumulator = 0U;

    adc_set_sample_cycles(ADC_CH_TEMP, 247U);

    /* 通道切换后的首个结果丢弃，降低残余电荷影响。 */
    (void)adc_read(ADC_CH_TEMP);

    for (uint32_t i = 0U; i < 16U; ++i) {
        accumulator += adc_read(ADC_CH_TEMP);
    }

    return (uint16_t)(accumulator / 16U);
}
```

硬件侧还应：

- 降低源阻抗。
- 在 ADC 引脚附近放置 RC。
- 必要时增加运放缓冲。
- 检查运放驱动容性负载的稳定性。

#### 风险影响

- 温度、压力和电流采样偏差。
- 通道之间串扰。
- 误触发过温、过流保护。

---

### 9.4 错误四：只清软件看门狗，不验证硬件状态

#### 错误代码

```
while (1) {
    watchdog_refresh();
    application_run();
}
```

#### 根因分析

主循环仍然运行不代表系统健康。外设可能已经失效，例如：

- SPI DMA 停止。
- ADC 数据长期不更新。
- 电源故障输入被卡死。
- 通信任务逻辑死锁。
- 外部器件持续复位。

#### 正确实现

```
#define HEALTH_COMM_BIT   (1UL << 0)
#define HEALTH_ADC_BIT    (1UL << 1)
#define HEALTH_POWER_BIT  (1UL << 2)
#define HEALTH_CONTROL_BIT (1UL << 3)

#define HEALTH_REQUIRED_MASK \
    (HEALTH_COMM_BIT | HEALTH_ADC_BIT | \
     HEALTH_POWER_BIT | HEALTH_CONTROL_BIT)

static volatile uint32_t health_bitmap;

void health_report(uint32_t component_bit)
{
    health_bitmap |= component_bit;
}

void health_supervisor_periodic(void)
{
    uint32_t snapshot = health_bitmap;
    health_bitmap = 0U;

    if ((snapshot & HEALTH_REQUIRED_MASK) == HEALTH_REQUIRED_MASK) {
        watchdog_refresh();
    } else {
        fault_log_write(FAULT_HEALTH_CHECK, snapshot);
        /* 不喂狗，由硬件看门狗复位系统。 */
    }
}
```

#### 风险影响

- 板卡处于“CPU 活着但功能失效”的危险状态。
- 工业控制输出无法恢复。
- 现场故障缺少有效日志。

---

### 9.5 错误五：开关电源反馈从错误位置取样

#### 错误实现

```
Buck 输出电容正端 ── 长电源铜皮 ── 负载
       │
       └── 反馈分压从电感或噪声节点附近引出
```

#### 根因分析

- 反馈路径拾取 SW 节点噪声。
- 反馈参考地包含大电流压降。
- 控制器调节的是局部电压，而不是负载端电压。

#### 正确实现

```
电感 → 输出电容 → 负载
          │
          ├── 反馈上端 Kelvin 取样
          └── 反馈地从安静地 Kelvin 返回
```

#### 风险影响

- 输出纹波增大。
- 轻载振荡或动态响应异常。
- 负载端电压偏低。
- EMC 和音频噪声恶化。

---

### 9.6 错误六：为“数模隔离”粗暴切割地平面

#### 错误实现

```
ADC 信号线跨越 AGND/DGND 分割缝
回流电流被迫绕行至单点连接位置
```

#### 根因分析

地分割并不自动实现隔离。信号跨缝会显著扩大高频回流环路，引入：

- 共模辐射。
- 串扰。
- ADC 参考地跳动。
- 数字接口波形恶化。

#### 正确实现

- 优先使用连续完整地平面。
- 通过器件分区和电流路径控制隔离噪声。
- 模拟电路集中布置在 ADC 附近。
- 让数字回流远离模拟输入与参考源。
- 仅在具有明确电流模型时采用地分割。

#### 风险影响

- ADC ENOB 降低。
- EMC 辐射增加。
- 问题对探头位置和线缆状态高度敏感。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

```
系统需求
├─ 功能与接口约束
├─ 安全与可靠性目标
├─ EMC 环境等级
├─ 热与结构边界
└─ 成本与生产目标
        │
        ▼
硬件架构设计
├─ 电源树
├─ 时钟与复位
├─ 接口与隔离
└─ 可诊断性设计
        │
        ▼
PCB 约束设计
├─ 叠层和阻抗
├─ Net Class
├─ 电流和热约束
├─ 差分与等长约束
└─ DFM/DFT 规则
        │
        ▼
固件协同
├─ 上电自检
├─ 电源和时钟监控
├─ 通信完整性测试
├─ 降级与恢复
└─ 生产测试模式
        │
        ▼
样机验证
├─ SI/PI 测试
├─ EMC 预兼容
├─ 热测试
├─ 边界条件测试
└─ HALT/可靠性测试
```

### 10.2 组合设计模式

推荐采用：

- **硬件确定性默认状态**
- **固件二次确认**
- **运行时健康监控**
- **故障日志持久化**
- **外部看门狗兜底**
- **安全输出硬件互锁**

### 10.3 完整板级自检代码框架

```
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

typedef enum {
    TEST_NOT_RUN = 0,
    TEST_PASS,
    TEST_FAIL,
    TEST_DEGRADED
} test_state_t;

typedef struct {
    test_state_t power;
    test_state_t clock;
    test_state_t memory;
    test_state_t adc;
    test_state_t communication;
    test_state_t external_watchdog;
    uint32_t failure_bitmap;
} board_test_report_t;

enum {
    FAIL_POWER        = 1UL << 0,
    FAIL_CLOCK        = 1UL << 1,
    FAIL_MEMORY       = 1UL << 2,
    FAIL_ADC          = 1UL << 3,
    FAIL_COMM         = 1UL << 4,
    FAIL_EXT_WATCHDOG = 1UL << 5
};

static test_state_t test_power_rails(void)
{
    const uint16_t rail_3v3 = platform_measure_rail_mv(RAIL_3V3);
    const uint16_t rail_1v2 = platform_measure_rail_mv(RAIL_1V2);

    if ((rail_3v3 < 3135U) || (rail_3v3 > 3465U)) {
        return TEST_FAIL;
    }

    if ((rail_1v2 < 1140U) || (rail_1v2 > 1260U)) {
        return TEST_FAIL;
    }

    return TEST_PASS;
}

static test_state_t test_clock_tree(void)
{
    if (!platform_main_clock_ready()) {
        return TEST_FAIL;
    }

    uint32_t frequency_hz = platform_measure_reference_clock();

    if ((frequency_hz < 24975000U) ||
        (frequency_hz > 25025000U)) {
        return TEST_DEGRADED;
    }

    return TEST_PASS;
}

static test_state_t test_memory_bus(void)
{
    static const uint32_t patterns[] = {
        0x00000000U,
        0xFFFFFFFFU,
        0xAAAAAAAAU,
        0x55555555U,
        0xA5A5A5A5U
    };

    for (uint32_t i = 0U;
         i < (sizeof(patterns) / sizeof(patterns[0]));
         ++i) {
        if (!platform_external_memory_test(patterns[i])) {
            return TEST_FAIL;
        }
    }

    return TEST_PASS;
}

bool board_power_on_self_test(board_test_report_t *report)
{
    if (report == NULL) {
        return false;
    }

    memset(report, 0, sizeof(*report));

    report->power = test_power_rails();
    if (report->power == TEST_FAIL) {
        report->failure_bitmap |= FAIL_POWER;
        platform_force_outputs_safe();
        return false;
    }

    report->clock = test_clock_tree();
    if (report->clock == TEST_FAIL) {
        report->failure_bitmap |= FAIL_CLOCK;
        platform_switch_to_internal_clock();
    }

    report->memory = test_memory_bus();
    if (report->memory == TEST_FAIL) {
        report->failure_bitmap |= FAIL_MEMORY;
    }

    report->adc = platform_adc_self_test()
                ? TEST_PASS
                : TEST_FAIL;

    if (report->adc == TEST_FAIL) {
        report->failure_bitmap |= FAIL_ADC;
    }

    report->communication = platform_communication_loopback_test()
                          ? TEST_PASS
                          : TEST_FAIL;

    if (report->communication == TEST_FAIL) {
        report->failure_bitmap |= FAIL_COMM;
    }

    report->external_watchdog =
        platform_external_watchdog_test()
        ? TEST_PASS
        : TEST_FAIL;

    if (report->external_watchdog == TEST_FAIL) {
        report->failure_bitmap |= FAIL_EXT_WATCHDOG;
    }

    fault_log_store_post_result(report,
                                sizeof(*report));

    return report->failure_bitmap == 0U;
}
```

---

## 11. 工业级实际案例分析

### 11.1 案例一：工业网关随机复位

#### 需求

- Cortex-M7 工业网关。
- 24 V 输入。
- Ethernet、RS-485、CAN 和 USB。
- 工作温度 -40°C～85°C。
- 外接数米通信线缆。

#### 故障现象

- 实验室稳定运行。
- EFT 测试和现场继电器切换时偶发复位。
- 软件日志显示 Brownout Reset。

#### 架构分析

```
24 V 输入
├─ TVS
├─ Buck 5 V
├─ LDO 3.3 V
└─ MCU
```

实际问题：

1. TVS 回流经过数字地内部区域。
2. 连接器保护器件距离接口较远。
3. 3.3 V LDO 输入电容回路过长。
4. NRST 走线靠近 Ethernet 时钟。
5. 复位源日志记录晚于时钟初始化。

#### 整改架构

```
连接器入口
├─ 瞬态泄放至机壳/接口参考路径
├─ 滤波与共模抑制
└─ 收发器

电源入口
├─ TVS 最短泄放路径
├─ 输入滤波
├─ Buck
├─ 负载点储能
└─ MCU 去耦网络
```

#### 核心代码

```
typedef struct {
    uint32_t reset_cause;
    uint16_t minimum_vdda_mv;
    uint32_t timestamp;
} reset_record_t;

void early_reset_capture(void)
{
    reset_record_t record;

    record.reset_cause = platform_read_reset_cause_raw();
    record.minimum_vdda_mv = platform_read_brownout_capture_mv();
    record.timestamp = platform_backup_timer_read();

    platform_backup_store(&record, sizeof(record));
    platform_clear_reset_flags();
}
```

#### 设计要点

- 复位原因必须在最早启动阶段保存。
- 接口浪涌和电源浪涌应分别规划回流路径。
- EMC 防护器件的位置通常比单纯提高器件规格更重要。
- 不允许复位网络跨越高 dv/dt 区域。

---

### 11.2 案例二：电机控制器电流采样跳变

#### 需求

- 三相 PMSM 控制。
- PWM 20 kHz。
- 母线电压 48 V。
- 相电流峰值 30 A。
- 低侧分流电阻采样。

#### 故障现象

- 小负载正常。
- 大电流时 ADC 采样瞬间出现尖峰。
- 软件过流保护误触发。
- 降低 PWM 边沿速度后问题减轻。

#### 根因

1. 分流电阻不是 Kelvin 连接。
2. 运放地与 MOSFET 功率地共享高电流铜皮。
3. ADC RC 滤波器离 MCU 较远。
4. 采样时刻靠近 MOSFET 切换边沿。
5. 栅极回路和采样回路平行布置。

#### 核心代码

```
#define CURRENT_LIMIT_MA       32000
#define CURRENT_CONFIRM_COUNT  3U

static uint32_t overcurrent_count;

void current_control_isr(void)
{
    int32_t current_ma = adc_get_phase_current_ma();

    if (current_ma > CURRENT_LIMIT_MA) {
        overcurrent_count++;

        if (overcurrent_count >= CURRENT_CONFIRM_COUNT) {
            pwm_force_safe_state();
            fault_log_write(FAULT_OVERCURRENT,
                            (uint32_t)current_ma);
        }
    } else {
        overcurrent_count = 0U;
    }
}
```

对于真正要求快速保护的系统，不能只依赖软件确认，应配置：

- 比较器硬件过流保护。
- PWM Break 输入。
- 栅极驱动器故障关断。
- 软件保护作为诊断和第二道防线。

#### 设计要点

- 分流采样必须使用 Kelvin 连接。
- 模拟前端参考点应避免共享功率回流。
- 采样触发点应位于 PWM 稳定窗口。
- 硬件保护路径必须独立于 CPU 软件执行。

---

### 11.3 案例三：高速 SPI Flash 在高温下启动失败

#### 需求

- QSPI NOR Flash。
- 80～100 MHz 时钟。
- 从外部 Flash 执行代码。
- -40°C～85°C 工作环境。

#### 故障现象

- 室温启动正常。
- 高温或低压条件下偶发读取 ID 错误。
- 降到 25 MHz 后恢复正常。

#### 根因

- CLK 使用最高驱动强度，存在严重过冲。
- CLK 过孔换层后附近无回流过孔。
- Flash 去耦电容通过长支路连接。
- 固件上电后直接切换最高速率。
- 未根据温压条件执行延迟校准。

#### 核心代码

```
bool qspi_initialize_reliably(void)
{
    static const uint32_t startup_rates[] = {
        12000000U,
        25000000U,
        50000000U,
        80000000U
    };

    platform_qspi_reset_memory();

    for (uint32_t i = 0U;
         i < (sizeof(startup_rates) / sizeof(startup_rates[0]));
         ++i) {
        platform_qspi_set_frequency(startup_rates[i]);

        if (!platform_qspi_read_id_valid()) {
            return false;
        }

        if (!platform_qspi_delay_calibrate()) {
            if (i == 0U) {
                return false;
            }

            platform_qspi_set_frequency(startup_rates[i - 1U]);
            break;
        }
    }

    return platform_qspi_crc_check_boot_region();
}
```

#### 设计要点

- 启动阶段先使用低速率建立通信。
- 源端串联阻尼应靠近 MCU 输出端。
- 所有 QSPI 信号换层时都应审查参考转换。
- 高温、低压和器件批次变化会压缩时序裕量。

---

## 12. 高频问题深度答疑

### 12.1 两层板是否一定做不好 EMC？

不一定，但难度明显更高。关键取决于：

- 是否能保持大面积连续地参考。
- 高速信号是否短且不跨地缝。
- 接口瞬态是否在入口处闭合。
- 电源和开关节点回路是否足够小。
- 是否存在长线缆、开关电源和高边沿数字信号。

低速、小尺寸、无线缆系统可能使用两层板达到目标；复杂工业控制器通常更适合四层或更多层。

### 12.2 模拟地和数字地到底要不要分割？

默认不要机械分割。应先分析：

- 数字电流从哪里流出。
- 回流从哪里返回。
- 模拟输入和参考源是否处于安静区域。
- ADC 是否包含内部数模耦合路径。
- 接口和电源是否把噪声注入模拟区。

**功能分区不等于地平面分割。**  
大多数 MCU 混合信号设计优先使用连续地平面，并通过布局和回流约束控制噪声。

### 12.3 去耦电容是不是越多越好？

不是。过多、容值跨度过大的电容并联可能与平面电感形成反谐振峰。正确方法是：

1. 计算目标阻抗。
2. 获取电容带偏压后的有效容量。
3. 建立 ESR、ESL 和安装电感模型。
4. 评估 PDN 阻抗曲线。
5. 结合时域负载瞬态测试验证。

### 12.4 等长是不是越严格越好？

不是。应先定义时序预算：

Tmargin=Tcycle−Tcoarse−Tdevice−Tskew−TjitterTmargin​=Tcycle​−Tcoarse​−Tdevice​−Tskew​−Tjitter​

只有分配给 PCB 的时延偏差预算确定后，才能转换为长度约束：

ΔLmax=vp⋅ΔtbudgetΔLmax​=vp​⋅Δtbudget​

过度蛇形等长可能增加：

- 自耦合。
- 串扰。
- 插入损耗。
- 局部参考不连续。
- 布线密度。

### 12.5 0 Ω 电阻是否应该大量预留？

只在具备明确用途时预留，例如：

- 电源域隔离与电流测量。
- 时钟源选择。
- 接口路由选择。
- EMI 调试。
- 模块旁路或版本兼容。

无目的的大量预留会增加寄生、BOM、焊接风险和调试复杂度。

### 12.6 为什么实验室正常，EMC 测试却失败？

实验室功能测试通常只覆盖正常工作条件，而 EMC 测试会注入快速共模和差模能量。常见原因包括：

- 外部线缆成为天线。
- 保护器件回流路径过长。
- 复位、晶振、中断等高敏感网络暴露。
- 电源瞬态裕量不足。
- 固件没有异常恢复路径。
- 屏蔽层、机壳地和数字地连接策略错误。

EMC 是系统级问题，不能只通过增加一个磁珠解决。

---

## 13. 课程核心总结

### 核心要点

- **PCB 审查的本质是审查电流路径，而不只是审查连线。**
- **信号边沿时间决定传输线风险，协议频率不能单独作为判断依据。**
- **完整回流路径通常比机械等长更重要。**
- **电源完整性必须通过目标阻抗和负载瞬态量化。**
- **模拟设计的核心是参考稳定、采样建立和噪声电流隔离。**
- **EMC 防护器件必须靠近干扰入口，并具有低阻抗泄放路径。**
- **硬件必须支持固件自检、降级、日志和失效恢复。**
- **审查必须分阶段进行，不能等 PCB 完成后一次性检查。**

### 性能影响排序

在通用 MCU 工业板上，常见优先级为：

```
电源和地回流完整性
> 关键电流环路布局
> 接口保护与共模路径
> 高速信号阻抗和端接
> 时钟、复位与启动配置
> 模拟参考和采样网络
> 热设计
> 可制造性与可测试性
> 几何整齐度
```

### 通用选型结论

- 中等复杂度工业 MCU 系统优先采用 **4～6 层板**。
- 高速接口必须在布局前确定叠层和阻抗。
- 外部接口必须联合考虑 SI、EMC、ESD 和地系统。
- 安全相关输出不能只依赖固件，应配置硬件关断路径。
- 投板前必须完成原理图、布局、布线、DFM、DFT 和 Release 六类审查。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|必查项|推荐措施|
|---|---|---|
|MCU 最小系统|电源域、BOOT、NRST、SWD|确定性上下拉、调试隔离|
|开关电源|热回路、反馈、SW 节点|缩小环路、Kelvin 反馈|
|高速单端信号|阻抗、回流、端接|连续参考面、源端阻尼|
|差分接口|差分阻抗、对内偏差|对称布线、减少过孔|
|ADC 输入|源阻抗、建立时间、参考|RC、缓冲、长采样时间|
|晶振|负载、ESR、布局|紧凑回路、避免测试支路|
|外部线缆|ESD、EFT、共模路径|入口保护、低电感泄放|
|大电流负载|铜宽、压降、热、地弹|平面供电、Kelvin 采样|
|安全输出|默认状态、失效关闭|硬件互锁、独立看门狗|
|量产测试|测试点、下载、序列号|ICT/FCT、自检模式|

### 14.2 特性对比表

|特性|低风险设计|高风险设计|
|---|---|---|
|地平面|连续完整|大量分割和狭缝|
|去耦|紧贴引脚、短回路|远离器件、共享长过孔|
|换层|附近有回流过孔|回流被迫绕行|
|接口保护|靠近连接器|放在板内深处|
|开关电源|热回路紧凑|SW 铜皮过大、反馈靠近 SW|
|ADC|低源阻抗、稳定参考|高阻源、采样时间过短|
|GPIO|最低可用边沿速度|全部最高驱动速度|
|调试|保留恢复和日志路径|启动失败后无法连接|
|测试|有测试点和自检|只能依赖人工探测|
|发布|版本和资料交叉验证|Gerber、BOM、坐标版本不一致|

---

## 15. 学习效果自检

完成本课后，应能够独立回答并完成以下任务：

- [ ]  能从系统框图识别电源、时钟、复位和接口关键风险。
- [ ]  能计算负载阶跃对应的 PDN 目标阻抗。
- [ ]  能根据上升时间估算传输线临界长度。
- [ ]  能判断高速信号是否跨越参考平面分割。
- [ ]  能分析信号换层后的高频回流路径。
- [ ]  能识别 Buck 热回路、反馈回路和栅极回路。
- [ ]  能计算 ADC 源阻抗对应的最小采样时间。
- [ ]  能检查差分对阻抗、对内时延和周边环境对称性。
- [ ]  能判断 ESD/TVS 的布局是否具有有效泄放路径。
- [ ]  能审查 MCU BOOT、NRST、SWD 和未使用引脚。
- [ ]  能设计板级上电自检和硬件健康监控框架。
- [ ]  能建立带严重等级和关闭证据的 Review 缺陷清单。
- [ ]  能完成 Gerber、BOM、坐标和原理图版本一致性检查。
- [ ]  能区分“功能正常”和“全边界条件可靠”。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：MCU 最小系统审查

选择一块现有 MCU 控制板，完成：

- 电源引脚和去耦映射。
- BOOT、NRST 和 SWD 审查。
- 晶振网络参数计算。
- 未使用引脚状态审查。
- 输出不少于 20 项的风险清单。

#### 任务二：电源与回流路径审查

对 Buck + MCU 电源链进行：

- 标注高 di/dt 热回路。
- 计算主要供电走线压降。
- 计算关键电源目标阻抗。
- 审查去耦电容安装电感。
- 使用示波器验证负载阶跃响应。

#### 任务三：高速接口审查

选择 SPI、QSPI、RMII、USB 或 Ethernet：

- 获取驱动端边沿时间。
- 估算临界传输线长度。
- 检查阻抗、拓扑、过孔和回流。
- 调整串联阻尼并测量过冲。
- 运行长时间 CRC 或误码测试。

#### 任务四：工业 EMC 整改

构建带继电器、长线缆或电机的干扰环境：

- 记录复位源和最低电源电压。
- 对比接口保护器件不同布局的影响。
- 检查共模电流闭合路径。
- 加入固件自检和故障恢复。
- 输出整改前后波形和复现概率。

#### 任务五：建立企业 Review Gate

建立以下设计门禁：

```
Gate 0：需求和接口冻结
Gate 1：架构与器件选型审查
Gate 2：原理图冻结
Gate 3：关键布局冻结
Gate 4：完整布线冻结
Gate 5：DFM/DFT 审查
Gate 6：生产资料发布
Gate 7：样机验证关闭
```

### 16.2 性能测试方法

|测试对象|测试方法|核心指标|
|---|---|---|
|电源纹波|短地弹簧或同轴探测|峰峰值、频谱、瞬态跌落|
|信号完整性|高带宽探头、近端/远端测量|过冲、下冲、振铃、抖动|
|ADC 性能|短接输入、精密源、FFT|RMS 噪声、ENOB、INL/DNL|
|热性能|热像仪、热电偶|热点温升、稳态时间|
|通信可靠性|CRC、PRBS、长时间压力测试|误码率、超时率|
|启动可靠性|全温全压循环上电|启动成功率、启动时间|
|EMC 鲁棒性|预兼容测试|复位、锁死、数据异常|
|故障恢复|注入掉电、断钟、总线卡死|检测时间、恢复时间|

### 16.3 进阶学习方向

1. **信号完整性**
    
    - IBIS 模型。
    - TDR 与阻抗测量。
    - 眼图、抖动和时序预算。
    - 过孔 Stub 与背钻。
2. **电源完整性**
    
    - PDN 阻抗扫描。
    - 反谐振分析。
    - 平面对电容。
    - VRM 控制环路与负载瞬态。
3. **EMC**
    
    - 共模电流模型。
    - 近场探头定位。
    - 屏蔽、机壳地和连接器 360° 搭接。
    - ESD/EFT/浪涌失效机理。
4. **热与可靠性**
    
    - 热阻网络。
    - 功率循环和焊点疲劳。
    - 器件降额设计。
    - HALT/HASS 和寿命模型。
5. **DFX**
    
    - DFM、DFA、DFT、DFS。
    - ICT、飞针和边界扫描。
    - 自动化生产测试。
    - 可追溯性与失效分析。
6. **硬件—固件协同**
    
    - 上电自检 POST。
    - 硬件抽象与板级配置管理。
    - 故障注入、降级运行与安全状态。
    - 现场日志、Bootloader 恢复和远程诊断。