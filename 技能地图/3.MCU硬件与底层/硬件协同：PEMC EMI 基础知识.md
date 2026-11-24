
## 1. 学习目标

### 理解

- 理解 **EMC（Electromagnetic Compatibility，电磁兼容）** 、**EMI（Electromagnetic Interference，电磁干扰）** 与 **EMS（Electromagnetic Susceptibility，电磁抗扰度）** 之间的关系。
- 理解工程中所称的 **PEMC** 通常不是统一标准术语。本课将其按 **产品级电磁兼容（Product EMC）** 理解，即从 PCB、线缆、机壳、电源、固件、结构与测试角度进行系统级 EMC 设计。
- 理解电磁干扰成立的三个基本条件：
    - 干扰源。
    - 耦合路径。
    - 敏感受害者。
- 理解传导发射、辐射发射、传导抗扰度和辐射抗扰度的底层机理。
- 理解差模电流、共模电流、回流路径、环路面积和阻抗不连续对 EMC 的决定性影响。

### 掌握

- 掌握工业产品常见 EMC 测试项目、测试对象与失效判据。
- 掌握 ESD、EFT、浪涌、射频场、传导射频和工频磁场的基础防护方法。
- 掌握接口入口保护、电源入口滤波、PCB 分区、参考平面和机壳地设计方法。
- 掌握使用示波器、电流探头、近场探头、频谱仪和 LISN 进行预兼容定位的方法。
- 掌握通过 GPIO 边沿控制、负载错峰、通信重试、故障日志和安全状态增强系统抗扰度。

### 精通

- 能够建立“源—路径—受害者”模型，区分差模问题与共模问题。
- 能够判断干扰主要通过传导、容性耦合、感性耦合还是辐射路径进入系统。
- 能够从频谱峰值反推时钟、开关电源、PWM、通信总线和共模电流来源。
- 能够区分真正的 EMC 故障与电源完整性、信号完整性、接地、测量方法或软件恢复问题。
- 能够根据干扰时间尺度设计硬件保护、驱动级关断、复位、固件过滤和恢复策略。

### 能够设计

- 能够设计产品级 EMC 分区、接口保护、线缆屏蔽、机壳地和 PCB 回流架构。
- 能够为工业控制器建立 EMC 需求矩阵、风险清单、预兼容测试和认证关闭流程。
- 能够设计适用于 ESD、EFT 和浪涌环境的硬件—固件联合防护框架。
- 能够建立可复用的 EMC Review Checklist、故障注入程序和整改验证方法。

---

## 2. 前置要求

### 知识要求

- 电场、磁场、电压、电流和阻抗基本概念。
- RC、RL、LC 与 RLC 网络。
- 信号完整性和电源完整性基础。
- PCB 叠层、参考平面、回流路径、过孔与连接器基础。
- Buck、LDO、电机、继电器、MOSFET 和通信收发器工作原理。
- GPIO、时钟、复位、中断、看门狗和 MCU 启动流程。
- CAN、RS-485、Ethernet、USB、SPI、UART 等接口基础。
- 示波器、频谱仪和差分探头基本测量原理。

### 技能要求

- 能够阅读原理图、PCB、结构图和线缆图。
- 能够识别高 dv/dtdv/dt、高 di/dtdi/dt 节点。
- 能够测量电源纹波、数字信号边沿和复位波形。
- 能够读取并保存 MCU 复位原因和外设错误状态。
- 能够编写通信压力测试、错误统计和故障恢复代码。
- 能够从产品标准或客户规范中提取测试等级与性能判据。

---

## 3. 技术概述

### 3.1 基本定义

**EMC** 表示设备在其电磁环境中正常工作，同时不对环境中的其他设备产生不可接受电磁干扰的能力。

EMC 包含两个基本方向：

```
EMC
├─ EMI/Emission：设备向外发出的干扰
│  ├─ 传导发射
│  └─ 辐射发射
│
└─ EMS/Immunity：设备承受外部干扰的能力
   ├─ 静电放电 ESD
   ├─ 电快速瞬变 EFT/Burst
   ├─ 浪涌 Surge
   ├─ 射频辐射抗扰度
   ├─ 射频传导抗扰度
   ├─ 工频磁场
   └─ 电压跌落、短时中断与变化
```

**EMI** 更准确地指电磁干扰现象或发射问题，不应与完整 EMC 概念混用。

### 3.2 干扰三要素

任何 EMC 问题都可以抽象为：

```
干扰源
   │
   ▼
耦合路径
   │
   ▼
敏感受害者
```

#### 干扰源

- MCU、FPGA、DDR 和高速时钟。
- Buck/Boost 的 SW 节点。
- MOSFET 栅极和功率回路。
- PWM、电机、继电器和电磁阀。
- Ethernet PHY、USB、CAN 和无线发射器。
- ESD、EFT、浪涌和外部射频场。

#### 耦合路径

- 共用电源阻抗。
- 共用地阻抗。
- 寄生电容。
- 互感。
- PCB 走线。
- 外部线缆。
- 机壳和屏蔽体。
- 空间辐射。
- 接口保护器件的泄放路径。

#### 敏感受害者

- 复位和启动配置引脚。
- 晶振、PLL 和时钟输入。
- ADC 输入和参考电压。
- 高阻中断、比较器和传感器输入。
- 通信收发器。
- 电源反馈和监控网络。
- MCU 内核、电源域和存储器。

### 3.3 EMC 的系统边界

EMC 不能只在 PCB 范围内解决。完整边界包括：

```
芯片
└─ 封装
   └─ PCB
      └─ 连接器
         └─ 线缆
            └─ 屏蔽层
               └─ 机壳
                  └─ 安装环境
                     └─ 外部电网和设备
```

板级整改如果没有处理线缆共模电流和机壳泄放路径，通常只能暂时改变频谱，无法稳定解决系统问题。

### 3.4 常见标准体系

具体适用标准必须由产品类别、市场、安装环境和客户要求确定。

|标准系列|主要领域|
|---|---|
|IEC 61000-4-x|通用抗扰度试验方法|
|CISPR 11|工业、科学和医疗设备发射|
|CISPR 32|多媒体设备发射|
|CISPR 35|多媒体设备抗扰度|
|IEC 61326|测量、控制和实验室设备|
|IEC 61000-6-x|通用工业/居住环境 EMC|
|ISO 11452|道路车辆零部件辐射抗扰度|
|CISPR 25|车载接收机保护相关发射|
|ISO 7637|车辆供电线瞬态|
|IEC 60601-1-2|医疗电气设备 EMC|
|DO-160|航空设备环境与 EMC 测试|

**测试等级、频率范围、耦合方式和判据必须以产品适用标准的现行版本为准。**

---

## 4. 核心特性横向对比

### 4.1 发射与抗扰度对比

|维度|传导发射|辐射发射|传导抗扰度|辐射抗扰度|
|---|---|---|---|---|
|主要路径|电源线、通信线|PCB、线缆、开口|电源线、接口线|空间电磁场|
|常用工具|LISN、频谱仪|天线、接收机|CDN、耦合钳|功放、天线、暗室|
|主要电流|差模和共模|以共模电流最危险|共模注入为主|场耦合到线缆和 PCB|
|典型根因|开关电源、时钟|线缆共模、回流不连续|接口滤波与泄放不足|高阻节点、长线缆、屏蔽差|
|常见整改|输入滤波、环路优化|共模抑制、连续参考面|滤波、钳位、隔离|屏蔽、滤波、回流控制|

### 4.2 ESD、EFT 与浪涌对比

|维度|ESD|EFT/Burst|Surge|
|---|---|---|---|
|典型来源|人体、带电物体接触|继电器、接触器、电感负载切换|雷击感应、电网大能量切换|
|特征|极快、高电压、能量相对有限|快速脉冲串、重复率高|上升较慢、能量大|
|主要风险|芯片闩锁、接口损伤、复位|累积扰动、通信错误、复位|TVS 过载、器件烧毁、绝缘失效|
|防护重点|低电感泄放、入口钳位|高频滤波、共模路径、恢复能力|能量分级泄放、限流、爬电电气间隙|
|固件作用|状态恢复、日志|去抖、重试、健康监控|仅辅助，不能承担能量防护|

### 4.3 耦合机制对比

|耦合机制|主导参数|风险条件|主要抑制方式|
|---|---|---|---|
|共阻抗耦合|共享阻抗、电流|多模块共用细长回流|降低共享阻抗、分离电流路径|
|容性耦合|寄生电容、dv/dtdv/dt|SW 节点靠近敏感线|增距、屏蔽、减小 SW 面积|
|感性耦合|互感、di/dtdi/dt、环路面积|功率回路靠近信号回路|缩小环路、正交布线、增距|
|辐射耦合|场强、天线效率|长线缆、共模电流|屏蔽、共模滤波、机壳搭接|
|直接传导|路径阻抗|电源或接口共用路径|滤波、隔离、钳位、分区|

### 4.4 常见防护器件对比

|器件|主要作用|优点|局限|
|---|---|---|---|
|TVS|瞬态钳位|响应快、能量能力明确|有寄生电容和动态电阻|
|MOV|大能量过压吸收|能量能力较强|老化、漏电、钳位较高|
|GDT|高能量泄放|寄生低、耐大浪涌|击穿慢、存在续流风险|
|共模扼流圈|抑制共模电流|不明显影响理想差模|饱和、寄生和模式转换|
|差模电感|抑制差模噪声|对电源差模有效|压降、饱和和谐振|
|RC 滤波|限带、阻尼|简单、可预测|影响边沿和时序|
|磁珠|中高频损耗|体积小、成本低|偏置降效、可能谐振|
|Y 电容|提供共模高频路径|共模抑制有效|受漏电流和安全规范限制|
|光耦/数字隔离器|隔离直流和低频共模|打断地环路|隔离电容仍会传递高频共模|

---

## 5. 底层原理与功能特性深度解析

### 5.1 时域边沿与频域能量

数字信号的 EMC 风险主要由边沿决定，而不只由重复频率决定。常用近似：

fknee≈0.35trfknee​≈tr​0.35​

假设 GPIO 的上升时间为 1 ns：

fknee≈350MHzfknee​≈350MHz

即使该 GPIO 每秒只翻转 1000 次，每次边沿仍包含数百 MHz 的高频成分。

#### 固件控制边沿

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    GPIO_SLEW_LOW = 0,
    GPIO_SLEW_MEDIUM,
    GPIO_SLEW_HIGH
} gpio_slew_t;

typedef struct {
    uint32_t pin;
    uint32_t maximum_toggle_hz;
    uint32_t trace_length_mm;
    bool external_cable;
    gpio_slew_t configured_slew;
} emc_signal_config_t;

bool emc_configure_output(const emc_signal_config_t *config)
{
    if ((config == NULL) || !platform_gpio_is_valid(config->pin)) {
        return false;
    }

    gpio_slew_t slew = config->configured_slew;

    /*
     * 外接线缆和低速输出优先限制边沿。
     * 最终配置必须通过时序和 EMC 实测确认。
     */
    if ((config->maximum_toggle_hz <= 1000000U) ||
        config->external_cable) {
        slew = GPIO_SLEW_LOW;
    }

    platform_gpio_set_slew(config->pin, slew);
    return true;
}
```

**工程原则：选择满足功能时序的最低 Slew Rate 和最低驱动强度。**

---

### 5.2 差模与共模电流

#### 差模电流

差模电流沿一根导体流向负载，再沿另一根导体返回：

```
电源/信号 ─────────► 负载
返回/地   ◄─────────
```

差模发射主要与以下因素相关：

- 回路面积。
- 电流幅值。
- 电流变化率。
- 走线阻抗。
- 滤波网络。

#### 共模电流

共模电流在多根导体上同向流动，经寄生电容、机壳、保护地或空间返回：

```
线缆多根导体 ───────►
                     设备
寄生电容/机壳/大地 ◄──┘
```

即使共模电流只有微安至毫安量级，长线缆也可能形成高效天线。

#### 模式转换

以下不对称会将差模能量转换为共模能量：

- 差分对走线不对称。
- 连接器引脚环境不对称。
- 保护电容差异。
- TVS 寄生电容不匹配。
- 一根线换层、另一根线不换。
- 共模扼流圈焊盘不对称。
- 参考平面中断。

---

### 5.3 环路面积与磁场辐射

小电流环路可以近似为磁偶极子。辐射趋势随以下参数增加：

E∝I⋅A⋅f2E∝I⋅A⋅f2

其中：

- II：高频电流幅度。
- AA：环路面积。
- ff：频率。

该比例关系用于判断趋势，不替代完整场计算。

因此：

- 同样的电流，环路面积增大十倍，辐射风险显著上升。
- 同样的 PCB，边沿频谱向高频扩展后，辐射会迅速恶化。
- 缩小 Buck 热回路和信号回流环路通常比“增加屏蔽罩”更优先。

### 5.4 高 dv/dtdv/dt 与容性耦合

寄生电容电流为：

iC=CpdvdtiC​=Cp​dtdv​

假设：

- SW 节点与敏感线之间寄生电容为 0.5 pF。
- SW 电压在 2 ns 内变化 24 V。

则：

dvdt=12V/nsdtdv​=12V/nsiC=0.5pF×12V/ns=6mAiC​=0.5pF×12V/ns=6mA

对高阻复位、ADC 或运放输入，6 mA 瞬态耦合可能造成严重干扰。

#### 抑制方法

- 减小 SW 节点铜面积。
- 增加与敏感网络的距离。
- 避免敏感走线从 SW 节点下方穿过。
- 降低开关边沿速度，但需评估开关损耗。
- 使用地屏蔽和连续参考平面。
- 降低受害节点阻抗。
- 增加输入 RC 过滤和迟滞。

---

### 5.5 高 di/dtdi/dt 与感性耦合

寄生互感导致受害回路电压：

VM=MdidtVM​=Mdtdi​

假设：

- 两个回路互感为 2 nH。
- 功率电流在 20 ns 内变化 5 A。

则：

VM=2nH×5A20ns=0.5VVM​=2nH×20ns5A​=0.5V

0.5 V 已足以触发低电压数字输入或污染模拟采样。

#### 抑制方法

- 缩小干扰源电流环路。
- 缩小受害者回路。
- 增加空间距离。
- 避免长距离平行。
- 必要时让两回路正交。
- 使用差分/Kelvin 采样。
- 减少共享地阻抗。

---

### 5.6 共阻抗耦合

多个电路共享返回阻抗时：

Vnoise=Iaggressor⋅ZsharedVnoise​=Iaggressor​⋅Zshared​

例如继电器驱动电流变化 200 mA，共享地路径在相关频率下阻抗为 1 Ω：

Vnoise=0.2A×1Ω=0.2VVnoise​=0.2A×1Ω=0.2V

该 200 mV 会同时抬升受害电路的本地地参考。即使受害信号对“系统地”看似稳定，对接收器本地地而言也可能跨越门限。

**接地设计的核心不是地网名称，而是电流从哪里流、通过什么阻抗返回。**

---

### 5.7 PCB 回流路径

高频信号的回流集中在信号正下方的参考平面。当信号跨越平面裂缝时：

- 回流路径被迫绕行。
- 环路面积增大。
- 路径电感增加。
- 差模能量转换为共模。
- 线缆和机壳可能成为新的返回路径。

```
正确：
高速信号  ─────────────────►
连续 GND  ═══════════════════
回流电流  ◄─────────────────

错误：
高速信号  ─────────┆────────►
参考平面  ════════  裂缝  ═══
回流电流被迫绕行
```

#### 换层要求

- 信号换层附近放置参考地缝合过孔。
- 差分对两根线同时换层。
- 参考从 GND 切换到另一 GND 层时，通过近端地过孔连接。
- 参考从电源平面切换到地平面时，必须分析高频跨接路径。
- 板边、高速连接器和屏蔽边界处布置地缝合过孔。

---

### 5.8 线缆为什么是 EMC 的重点

线缆长度接近波长的有效比例时，容易形成高效天线。自由空间波长：

λ=cfλ=fc​

在 100 MHz：

λ=3×108100×106=3mλ=100×1063×108​=3m

四分之一波长为：

λ4=0.75m4λ​=0.75m

长度约 0.75 m 的线缆在 100 MHz 附近可能具有较高辐射效率。实际线缆受介质、共模路径和安装方式影响，但该估算可用于判断风险频段。

#### 线缆接口设计原则

```
外部线缆
└─ 连接器
   ├─ 屏蔽层优先短路径连接机壳参考
   ├─ ESD/浪涌器件靠近入口
   ├─ 共模滤波靠近入口
   ├─ 差模滤波按协议带宽设计
   └─ 收发器位于保护区内
```

不能让瞬态先经过长 PCB 走线，再到位于板内深处的 TVS。

---

### 5.9 ESD 底层机理

ESD 具有极快边沿，会通过以下路径进入系统：

- 直接接触接口引脚。
- 放电到金属外壳。
- 空气放电到缝隙。
- 屏蔽层耦合。
- 寄生电容耦合到内部地和电源。
- 通过接口芯片保护结构注入电源轨。

保护路径的寄生电感会产生：

VL=LdidtVL​=Ldtdi​

假设泄放路径电感 10 nH，电流变化率 5 A/ns：

VL=50VVL​=50V

因此，TVS 标称钳位电压不是芯片端承受电压的全部。实际残压还包括：

- TVS 动态钳位。
- 走线和过孔电感电压。
- 地弹。
- 器件结电容形成的耦合。
- 保护器件到接口之间的路径电压。

### 5.10 EFT 底层机理

EFT 是快速脉冲串，其工业现场来源包括：

- 接触器抖动。
- 继电器触点开断。
- 电机换向。
- 感性负载切换。
- 电源网络中的重复瞬态。

EFT 不一定直接损坏器件，更常见的现象是：

- 复位。
- 通信错误。
- 中断风暴。
- ADC 跳变。
- 状态机异常。
- 外设锁死。
- 数据存储损坏。

由于脉冲重复出现，单次过滤不充分时会累积触发软件错误。

---

### 5.11 浪涌底层机理

浪涌能量通常显著高于 ESD 和 EFT。典型保护采用分级协调：

```
接口入口
├─ 一级高能量泄放：GDT/MOV/大功率 TVS
├─ 限流或解耦：电阻、电感、PTC
├─ 二级精确钳位：TVS
├─ 滤波
└─ 被保护器件
```

必须验证：

- 最大钳位电压。
- 峰值脉冲电流。
- 脉冲功率。
- 动态电阻。
- 重复脉冲寿命。
- 温度降额。
- 后级器件绝对最大额定值。
- 泄放路径和爬电电气间隙。

固件无法代替浪涌能量防护。

---

### 5.12 开关电源的 EMI 来源

Buck 的关键高频回路包括：

#### 输入热回路

```
输入电容正端
→ 高侧 MOSFET
→ 低侧 MOSFET/续流路径
→ 输入电容地端
```

#### SW 节点

SW 节点具有高 dv/dtdv/dt，容易产生：

- 容性耦合。
- 辐射发射。
- 对反馈和模拟信号的干扰。
- 通过散热片、屏蔽罩和机壳形成共模电流。

#### 电感输出回路

电感电流纹波形成差模噪声，可能经输入和输出路径传播。

#### 整改优先级

1. 缩小输入热回路。
2. 缩小 SW 节点面积。
3. 优化栅极驱动回路。
4. 修复反馈 Kelvin 路径。
5. 调整边沿、Snubber 和开关频率。
6. 最后再增加输入/输出滤波。

---

### 5.13 RC Snubber 基础

Snubber 用于阻尼寄生 LC 产生的振铃，不能盲目选值。

如果测得振铃频率为 frfr​，可先增加测试电容 CtestCtest​，测量新频率 f2f2​，估算原寄生电容和电感，再选择阻尼参数。简化阻尼电阻可从以下量级开始：

Rsnubber≈LpCsnubberRsnubber​≈Csnubber​Lp​​​

Snubber 功耗近似与开关频率、电容和电压平方相关：

Psnubber≈CsnubberV2fsPsnubber​≈Csnubber​V2fs​

假设：

- C=330pFC=330pF
- V=24VV=24V
- fs=500kHzfs​=500kHz

则：

P≈330pF×242×500kHz≈95mWP≈330pF×242×500kHz≈95mW

实际损耗和波形相关，应通过温升与功率测量验证。

---

### 5.14 屏蔽与机壳地

屏蔽的目标是：

- 限制场穿透。
- 为共模电流提供低阻抗返回路径。
- 防止 PCB 地承受本应流向机壳的瞬态电流。

高频屏蔽连接要求：

- 低电感。
- 大面积。
- 短路径。
- 尽量 360° 搭接。
- 避免细长“猪尾巴”连接。

一根长而细的屏蔽接地线在低频下可能导通良好，但在高频下因电感呈现高阻抗。

机壳地、保护地和数字地的连接方式不能套用固定答案。必须根据以下因素设计：

- 安全规范。
- 系统是否浮地。
- 线缆屏蔽方式。
- 共模电流路径。
- 多设备地电位差。
- 接口隔离要求。
- 目标频段。

---

### 5.15 固件的 EMC 作用边界

固件能够：

- 限制边沿和驱动强度。
- 错峰切换大负载。
- 对输入去抖和数字滤波。
- 检测通信错误并重试。
- 监控外设活性。
- 保存复位原因。
- 执行降级和安全恢复。

固件不能：

- 吸收 ESD 或浪涌能量。
- 修复不连续的 PCB 回流路径。
- 让超过绝对最大额定值的芯片不损坏。
- 替代硬件过流关断。
- 保证已经失控的 CPU 执行安全动作。

#### 输入时间滤波框架

```
typedef struct {
    uint16_t assert_samples;
    uint16_t release_samples;
    uint16_t active_count;
    uint16_t inactive_count;
    bool filtered_state;
} digital_filter_t;

bool digital_filter_update(digital_filter_t *filter, bool raw_state)
{
    if ((filter == NULL) ||
        (filter->assert_samples == 0U) ||
        (filter->release_samples == 0U)) {
        return false;
    }

    if (raw_state) {
        filter->inactive_count = 0U;

        if (filter->active_count < filter->assert_samples) {
            filter->active_count++;
        }

        if (filter->active_count >= filter->assert_samples) {
            filter->filtered_state = true;
        }
    } else {
        filter->active_count = 0U;

        if (filter->inactive_count < filter->release_samples) {
            filter->inactive_count++;
        }

        if (filter->inactive_count >= filter->release_samples) {
            filter->filtered_state = false;
        }
    }

    return filter->filtered_state;
}
```

对于安全急停、硬件过流等信号，不能简单增加长时间软件滤波。应结合：

- 硬件比较器。
- 带迟滞输入。
- 双通道一致性。
- 脉冲宽度判定。
- 安全时间预算。

---

## 6. 性能量化分析

### 6.1 示例验证平台

以下数据为便于说明方法的一组**示例测试条件**，不代表统一产品限值：

```
设备：Cortex-M7 工业通信控制器
输入：24 VDC
PCB：6 层，完整 GND 参考面
接口：Ethernet、CAN FD、RS-485、USB
负载：继电器、电磁阀、外部传感器
主时钟：25 MHz
CPU：400 MHz
Buck：500 kHz
频谱仪：9 kHz～3 GHz
近场探头：H 场与 E 场探头
示波器：1 GHz、5 GSa/s
电流探头：100 MHz
测试距离与带宽：按目标预兼容配置记录
```

### 6.2 边沿速度优化

|指标|高 Slew|中 Slew|低 Slew|
|---|---|---|---|
|GPIO 上升时间|1.1 ns|2.6 ns|7.8 ns|
|主要频谱拐点|318 MHz|135 MHz|45 MHz|
|接收端时序裕量|最大|充分|需确认|
|200～400 MHz 近场峰值|基准|降低约 4～8 dB|降低约 8～15 dB|
|过冲|0.9 V|0.35 V|0.12 V|

这些是特定示例量级。不同 MCU 的 Slew 档位差异很大，必须实测。

### 6.3 环路面积优化

假设 Buck 输入热回路面积由 300 mm² 降至 60 mm²，在其他条件近似不变时：

AnewAold=60300=0.2Aold​Anew​​=30060​=0.2

按磁偶极趋势估计，相关近场耦合可能显著下降。但由于实际还受到电流波形、平面和屏蔽影响，不能直接承诺严格降低 14 dB。

示例实测：

|项目|优化前|优化后|
|---|---|---|
|SW 节点振铃|82 MHz|74 MHz|
|振铃峰峰值|9.5 V|3.1 V|
|70～100 MHz 近场峰值|基准|降低 7～11 dB|
|输入传导峰值|超限 8 dB|留有 3 dB 裕量|

### 6.4 共模电流与辐射趋势

线缆共模电流是辐射发射的重要指标。假设在 150 MHz 附近测得：

|状态|共模电流|
|---|---|
|无共模处理|1.8 mA|
|增加共模扼流圈|0.55 mA|
|同时修复屏蔽搭接|0.16 mA|

相对电流幅度变化：

20log⁡10(0.161.8)≈−21dB20log10​(1.80.16​)≈−21dB

远场结果不会必然下降同样数值，但该测量能用于判断共模路径整改是否有效。

### 6.5 RC 输入滤波

一阶 RC 截止频率：

fc=12πRCfc​=2πRC1​

若：

- R=1kΩR=1kΩ
- C=10nFC=10nF

则：

fc≈15.9kHzfc​≈15.9kHz

对 10 MHz 干扰，理想一阶低通衰减幅度近似：

∣H(f)∣=11+(f/fc)2∣H(f)∣=1+(f/fc​)2​1​20log⁡10∣H(10MHz)∣≈−56dB20log10​∣H(10MHz)∣≈−56dB

实际衰减会受到：

- 电容 ESL。
- PCB 寄生。
- 输入钳位。
- 共模注入。
- 地参考噪声。
- 信号源阻抗。

因此，公式只能用于初选，不能作为最终抗扰度保证。

### 6.6 TVS 寄生路径

假设 TVS 到接口地的总路径电感为 8 nH，ESD 电流变化率为 4 A/ns：

VL=8nH×4A/ns=32VVL​=8nH×4A/ns=32V

若通过布局将路径电感降至 2 nH：

VL=8VVL​=8V

仅通过缩短泄放路径，寄生电感电压即可减少约 24 V。对低压收发器而言，这通常比盲目更换更低标称钳位电压的 TVS 更有效。

### 6.7 滤波器插入损耗

理想 LC 滤波器在特定频率可能具有较高衰减，但实际性能由以下因素限制：

- 源阻抗与负载阻抗。
- 电感寄生电容。
- 电容 ESL。
- 元件偏置特性。
- PCB 耦合绕过滤波器。
- 差模与共模模式转换。
- 阻尼不足导致的谐振峰。

因此，不能直接将 50 Ω 测试条件下的数据手册插入损耗等同于实际系统衰减。

### 6.8 整改优先级与收益

|根因|低效做法|优先整改|示例收益量级|
|---|---|---|---|
|Buck 热回路过大|增加屏蔽罩|重做功率布局|近场峰值降低 5～15 dB|
|线缆共模电流|只加差模电容|修复共模路径|辐射峰值降低 6～20 dB|
|GPIO 边沿过快|降低协议频率|降 Slew/增加阻尼|高频谐波降低 3～15 dB|
|ESD 泄放过长|换更大 TVS|TVS 移近连接器|芯片端残压显著下降|
|复位线高阻|只加软件延迟|上拉、RC、布局和监控|消除误复位|
|地平面裂缝|增加磁珠|修复回流路径|SI、EMI 同时改善|

### 6.9 测试不确定度

EMC 结果受以下因素显著影响：

- 天线距离和高度。
- 线缆摆放。
- 转台角度。
- 接地和辅助设备。
- 检波器类型。
- RBW/VBW。
- 探头方向和压力。
- 环境底噪。
- 设备运行模式。
- 不同样机和线缆批次。

认证前预兼容目标通常应保留合理裕量，不能以“刚好压线”为设计目标。

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
开始 EMC 设计
├─ 产品连接外部电源或长线缆吗？
│  ├─ 是
│  │  ├─ 线缆是否屏蔽？
│  │  │  ├─ 是 → 定义屏蔽层与机壳的高频连接方式
│  │  │  └─ 否 → 重点控制线缆共模电流
│  │  └─ 接口是否暴露于 ESD/EFT/Surge？
│  │     ├─ 是 → 在连接器入口进行分级保护
│  │     └─ 否 → 执行常规接口滤波
│  └─ 否 → 重点审查板内源、回流和结构开口
│
├─ 是否存在高 dv/dt 节点？
│  ├─ 是 → 缩小节点面积、增距、屏蔽、控制边沿
│  └─ 否 → 继续检查高 di/dt 回路
│
├─ 是否存在高 di/dt 回路？
│  ├─ 是 → 缩小回路、降低共享阻抗、优化去耦
│  └─ 否 → 检查时钟和高速数字信号
│
├─ 是否存在高速时钟或外接高速接口？
│  ├─ 是 → 连续参考面、阻抗、端接、共模控制
│  └─ 否 → 低速 GPIO 使用最低可用 Slew
│
├─ 是否存在高阻敏感节点？
│  ├─ 是 → 偏置、迟滞、RC、屏蔽和短走线
│  └─ 否 → 执行常规抗扰度审查
│
├─ 是否有危险输出？
│  ├─ 是 → 硬件互锁、默认安全状态、独立关断
│  └─ 否 → 软件恢复可作为补充
│
└─ 是否进入样机阶段？
   ├─ 是 → 近场扫描、线缆电流、传导和抗扰度预兼容
   └─ 否 → 完成 EMC 约束与 Review 后冻结 PCB
```

### 7.2 典型场景选型

|场景|主要风险|推荐方案|理由|
|---|---|---|---|
|工业 PLC|EFT、浪涌、长线缆|入口分级防护、隔离、机壳地|工业现场瞬态与共模干扰强|
|电机控制器|高 dv/dtdv/dt、高 di/dtdi/dt|功率/控制分区、隔离驱动、硬件关断|功率回路是强干扰源|
|工业网关|多接口、共模线缆|各接口独立共模路径和保护|多根线缆形成复杂天线系统|
|高精度采集|ADC、参考源敏感|连续参考、低噪声电源、接口限带|微小耦合即可影响精度|
|电池无线终端|DC/DC、射频发射|控制谐波、局部储能、天线隔离|射频与数字电源相互耦合|
|车载 ECU|供电瞬态、线束耦合|汽车级保护、线束共模控制|电源和线束环境严苛|
|医疗设备|安全、低噪声、抗扰度|隔离、漏电流控制、风险管理|EMC 故障可能影响基本性能|
|继电器控制板|触点电弧、感性回扫|负载端吸收、线圈续流、输入滤波|干扰应尽量在源端处理|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **优先从干扰源降低能量，而不是在受害端无限增加滤波。**
2. **优先修复回流路径，再增加磁珠和屏蔽罩。**
3. **对外接口必须在连接器入口完成瞬态泄放。**
4. **屏蔽层高频连接必须短、宽、低电感。**
5. **Buck 的输入热回路和 SW 节点应作为最高优先级布局对象。**
6. **高速信号不跨参考平面裂缝。**
7. **外接低速 GPIO 也要按线缆天线和瞬态入口处理。**
8. **复位、晶振、启动和高阻输入属于重点受害网络。**
9. **安全相关输出必须有独立硬件关断路径。**
10. **固件应记录故障，不应掩盖反复发生的硬件问题。**
11. **每次整改只改变少数关键变量，并保留整改前后数据。**
12. **认证不是调试场所，预兼容测试应在设计冻结前完成。**

### 8.2 选型决策矩阵

评分：1 为差，5 为优秀。

|方案|高频抑制|大能量防护|信号影响|成本|调试难度|
|---|---|---|---|---|---|
|RC 滤波|4|1|2～4|5|5|
|LC 滤波|5|1|3～5|4|3|
|磁珠 + 电容|3～5|1|3～5|4|3|
|共模扼流圈|5|1|4|3|3|
|TVS|2|3～5|2～5|4|4|
|MOV/GDT|1～2|5|4|3|3|
|数字隔离|4|3|4|2|3|
|屏蔽罩|3～5|1|5|2|2|
|修复 PCB 回流|5|2|5|设计期 5|返板期 1|

### 8.3 产品级 EMC 需求矩阵

每个测试项目至少明确：

|字段|内容|
|---|---|
|标准与版本|产品适用标准|
|端口|AC、DC、信号、通信、机壳|
|测试项目|发射或抗扰度|
|等级|电压、场强、频率、持续时间|
|工作模式|最大辐射与最敏感模式|
|判据|A、B、C 或产品自定义|
|安全状态|故障期间输出状态|
|恢复方式|自动、人工或禁止恢复|
|日志要求|复位、错误、数据完整性|
|验证证据|波形、频谱、日志和报告|

### 8.4 PCB 编码与布局规范

- 建立 `SW_NODE`、`HIGH_DI_DT`、`CLOCK`、`RESET`、`ANALOG_SENSITIVE` 等网络类别。
- 对高 dv/dtdv/dt 节点设置禁止布线和铜区。
- 对高速信号设置连续参考面规则。
- 接口保护器件设置最大入口距离约束。
- 机壳地和数字地网络必须有明确连接策略。
- 差分保护器件寄生参数应匹配。
- 板边和连接器附近按目标频段规划地缝合。
- 禁止在晶振、ADC、参考源下方布置 SW 和功率回路。

### 8.5 固件规范

- 上电最早阶段保存复位源。
- 通信模块维护 CRC、帧错误、超时和恢复计数。
- 外设必须有超时和重新初始化路径。
- 安全输出默认由硬件保持关闭。
- EMC 故障模式下禁止无限重试。
- 欠压、时钟失效和通信失效应使用不同错误码。
- 故障日志应避免在供电不稳定时直接写 Flash。
- 看门狗应由健康监督器统一喂养。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：用固件滤波代替接口硬件防护

#### 错误代码

```
void external_interrupt_handler(void)
{
    /*
     * 错误：认为延迟 10 ms 就能解决 ESD/EFT。
     * 此时瞬态可能已经超过 MCU 引脚绝对最大值。
     */
    platform_delay_ms(10U);

    if (gpio_read(EXTERNAL_INPUT_PIN)) {
        process_external_event();
    }
}
```

#### 根因分析

软件只能在 CPU 和引脚仍正常工作后处理逻辑状态，无法：

- 限制注入电流。
- 降低芯片端钳位电压。
- 防止闩锁和永久损伤。
- 控制瞬态回流路径。

#### 正确实现

硬件采用入口 TVS、限流、RC 和施密特触发；ISR 只记录事件，过滤在周期任务执行：

```
static volatile bool external_input_pending;

void external_interrupt_handler(void)
{
    external_input_pending = true;
}

void external_input_periodic(void)
{
    static digital_filter_t filter = {
        .assert_samples = 5U,
        .release_samples = 5U
    };

    if (!external_input_pending) {
        return;
    }

    external_input_pending = false;

    bool state = digital_filter_update(
        &filter,
        gpio_read(EXTERNAL_INPUT_PIN));

    if (state) {
        process_external_event();
    }
}
```

#### 风险影响

- MCU 引脚损伤。
- 闩锁。
- 随机复位。
- 中断风暴。
- 安全输入误判。

---

### 9.2 错误二：所有 GPIO 都配置为最高速度

#### 错误代码

```
void board_gpio_init(void)
{
    platform_gpio_set_slew(LED_PIN, GPIO_SLEW_HIGH);
    platform_gpio_set_slew(RELAY_PIN, GPIO_SLEW_HIGH);
    platform_gpio_set_slew(SPI_CLK_PIN, GPIO_SLEW_HIGH);
    platform_gpio_set_slew(STATUS_PIN, GPIO_SLEW_HIGH);
}
```

#### 根因分析

最高 Slew 增加高频谐波、同时开关电流、地弹、串扰和辐射。LED、继电器和低速状态信号通常没有快速边沿需求。

#### 正确实现

```
void board_gpio_init(void)
{
    platform_gpio_set_slew(LED_PIN, GPIO_SLEW_LOW);
    platform_gpio_set_slew(RELAY_PIN, GPIO_SLEW_LOW);
    platform_gpio_set_slew(STATUS_PIN, GPIO_SLEW_LOW);

    /*
     * SPI 使用满足时序的最低档位，
     * 并结合源端串联电阻实测。
     */
    platform_gpio_set_slew(SPI_CLK_PIN, GPIO_SLEW_MEDIUM);
}
```

#### 风险影响

- 辐射发射超限。
- 接口过冲和振铃。
- 邻近复位、ADC 和晶振网络受干扰。
- 功耗和电源噪声增加。

---

### 9.3 错误三：ESD TVS 放在板内深处

#### 错误实现

```
连接器 ── 80 mm PCB 走线 ── TVS ── 收发器
```

#### 根因分析

ESD 电流先流经长走线，走线寄生电感产生较大电压；沿途还会向其他网络发生容性和感性耦合。

#### 正确实现

```
连接器
├─ 最短路径 TVS
├─ 机壳/接口参考泄放
├─ 共模或差模滤波
└─ 收发器
```

并确保：

- TVS 回流不穿过数字核心区域。
- 保护前后走线物理分离。
- TVS 后端不与未保护走线平行耦合。
- 器件寄生电容满足接口带宽。

#### 风险影响

- 收发器损伤。
- MCU 复位。
- 保护器件存在但实际无效。
- ESD 电流污染整板地平面。

---

### 9.4 错误四：通信错误后无限重试

#### 错误代码

```
void communication_task(void)
{
    while (!bus_send_frame()) {
        /*
         * 错误：干扰期间无限重试，
         * 可能提高总线占用和电源噪声。
         */
    }
}
```

#### 根因分析

EFT 或射频干扰期间，无限重试会导致：

- CPU 占用失控。
- 总线持续拥塞。
- 发射器反复翻转，进一步增加 EMI。
- 看门狗无法反映真实健康状态。
- 故障证据丢失。

#### 正确实现

```
#define BUS_RETRY_MAX       3U
#define BUS_BACKOFF_MS      5U

bool communication_send_with_retry(const uint8_t *data,
                                   uint32_t length)
{
    if ((data == NULL) || (length == 0U)) {
        return false;
    }

    for (uint32_t retry = 0U;
         retry < BUS_RETRY_MAX;
         ++retry) {
        if (bus_send_frame(data, length)) {
            return true;
        }

        platform_delay_ms(BUS_BACKOFF_MS * (retry + 1U));
    }

    fault_log_stage_in_ram(FAULT_BUS_RETRY_EXHAUSTED);
    communication_enter_degraded_mode();
    return false;
}
```

#### 风险影响

- 实时任务失调度。
- 故障扩散。
- EMI 加重。
- 系统无法进入受控降级状态。

---

### 9.5 错误五：粗暴分割地平面解决噪声

#### 错误实现

```
数字地 ═══════ 裂缝 ═══════ 模拟地
高速信号和接口线跨越裂缝
```

#### 根因分析

信号跨缝后回流绕行，环路面积增大，将差模电流转化为共模电流。地分割还可能迫使 ESD 电流通过敏感区域。

#### 正确实现

- 优先使用连续参考地平面。
- 通过功能布局控制数字和模拟电流路径。
- 让接口保护电流在入口附近闭合。
- 仅在明确掌握所有返回路径时使用分割。
- 隔离系统应定义隔离屏障和跨屏障寄生电容。

#### 风险影响

- 辐射发射增加。
- ADC 噪声恶化。
- 通信波形振铃。
- EMC 故障随线缆和探头位置变化。

---

### 9.6 错误六：只增加磁珠，不分析噪声模式

#### 错误实现

```
所有电源和接口都串联同一型号磁珠
```

#### 根因分析

磁珠可能：

- 对目标频率阻抗不足。
- 在直流偏置下失效。
- 与 MLCC 形成高 Q 谐振。
- 只抑制差模，而实际问题是共模。
- 引入压降和负载瞬态问题。

#### 正确实现

1. 判断干扰是差模还是共模。
2. 测量目标频率。
3. 检查偏置电流下阻抗。
4. 建立源和负载阻抗模型。
5. 加入阻尼。
6. 验证插入损耗和负载瞬态。

#### 风险影响

- EMC 无改善。
- 电源反谐振。
- 电压跌落。
- 器件温升和饱和。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

```
外部环境
├─ ESD
├─ EFT
├─ Surge
├─ 射频场
└─ 线缆共模电流
       │
       ▼
结构防护层
├─ 金属机壳
├─ 屏蔽搭接
├─ 接缝和开口控制
└─ 保护地
       │
       ▼
接口防护层
├─ TVS/MOV/GDT
├─ 共模滤波
├─ 差模滤波
├─ 限流与隔离
└─ 低电感泄放
       │
       ▼
PCB 防护层
├─ 连续参考平面
├─ 功能分区
├─ 最小热回路
├─ 低阻抗 PDN
├─ 敏感网络隔离
└─ 地缝合
       │
       ▼
硬件监督层
├─ Brownout
├─ 独立复位监控
├─ 外部看门狗
├─ 硬件过流关断
└─ 安全输出互锁
       │
       ▼
固件韧性层
├─ 输入过滤
├─ CRC 与重试
├─ 外设健康检测
├─ 有限次数恢复
├─ 降级运行
└─ 故障日志
```

### 10.2 EMC 健康监督器代码框架

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    EMC_STATE_NORMAL = 0,
    EMC_STATE_DISTURBED,
    EMC_STATE_DEGRADED,
    EMC_STATE_SAFE
} emc_state_t;

typedef struct {
    uint32_t reset_flags;
    uint32_t communication_errors;
    uint32_t peripheral_timeouts;
    uint32_t clock_faults;
    uint32_t brownout_warnings;
    uint32_t unexpected_interrupts;
    emc_state_t state;
} emc_health_t;

#define EMC_COMM_ERROR_LIMIT       10U
#define EMC_TIMEOUT_LIMIT           3U
#define EMC_CLOCK_FAULT_LIMIT       1U
#define EMC_BROWNOUT_LIMIT          1U

static bool emc_health_is_critical(const emc_health_t *health)
{
    if (health == NULL) {
        return true;
    }

    return (health->clock_faults >= EMC_CLOCK_FAULT_LIMIT) ||
           (health->brownout_warnings >= EMC_BROWNOUT_LIMIT);
}

static bool emc_health_is_degraded(const emc_health_t *health)
{
    if (health == NULL) {
        return true;
    }

    return (health->communication_errors >=
            EMC_COMM_ERROR_LIMIT) ||
           (health->peripheral_timeouts >=
            EMC_TIMEOUT_LIMIT);
}

void emc_health_supervise(emc_health_t *health)
{
    if (health == NULL) {
        return;
    }

    if (emc_health_is_critical(health)) {
        platform_force_outputs_safe();
        platform_disable_high_power_loads();
        fault_log_stage_in_backup_ram(
            FAULT_EMC_CRITICAL);

        health->state = EMC_STATE_SAFE;

        /*
         * 不依赖当前 CPU 无限恢复。
         * 最终复位由独立看门狗或电源监控器执行。
         */
        return;
    }

    if (emc_health_is_degraded(health)) {
        platform_reduce_interface_rates();
        platform_disable_optional_peripherals();
        health->state = EMC_STATE_DEGRADED;
        return;
    }

    health->state = EMC_STATE_NORMAL;
}
```

### 10.3 外设有限恢复框架

EMC 干扰可能使外设状态机、DMA、总线控制器或收发器进入异常状态。恢复机制必须遵循：

- **限制恢复次数**，禁止无限重试。
- **先隔离业务流量，再复位外设**。
- **清理 DMA、中断和错误标志**，避免带故障状态重新初始化。
- **记录首次故障和最终恢复结果**。
- **恢复失败后进入降级或安全状态**。
- 对安全相关外设，恢复前必须确认输出已由硬件置于安全状态。

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    RECOVERY_OK = 0,
    RECOVERY_ERR_ARGUMENT,
    RECOVERY_ERR_LIMIT,
    RECOVERY_ERR_QUIESCE,
    RECOVERY_ERR_RESET,
    RECOVERY_ERR_REINIT,
    RECOVERY_ERR_SELF_TEST
} recovery_result_t;

typedef enum {
    PERIPHERAL_STATE_OFFLINE = 0,
    PERIPHERAL_STATE_RECOVERING,
    PERIPHERAL_STATE_ONLINE,
    PERIPHERAL_STATE_DEGRADED,
    PERIPHERAL_STATE_FAILED
} peripheral_state_t;

typedef struct {
    uint32_t recovery_count;
    uint32_t recovery_limit;
    uint32_t last_error;
    uint32_t first_error;
    uint32_t last_recovery_ms;
    peripheral_state_t state;
} peripheral_recovery_t;

typedef struct {
    bool (*quiesce)(void);
    bool (*reset)(void);
    bool (*initialize)(void);
    bool (*self_test)(void);
    void (*force_safe)(void);
} peripheral_recovery_ops_t;

static bool recovery_ops_valid(
    const peripheral_recovery_ops_t *ops)
{
    return (ops != NULL) &&
           (ops->quiesce != NULL) &&
           (ops->reset != NULL) &&
           (ops->initialize != NULL) &&
           (ops->self_test != NULL) &&
           (ops->force_safe != NULL);
}

recovery_result_t peripheral_try_recover(
    peripheral_recovery_t *context,
    const peripheral_recovery_ops_t *ops,
    uint32_t error_code)
{
    if ((context == NULL) || !recovery_ops_valid(ops)) {
        return RECOVERY_ERR_ARGUMENT;
    }

    if (context->recovery_count == 0U) {
        context->first_error = error_code;
    }

    context->last_error = error_code;

    if (context->recovery_count >= context->recovery_limit) {
        ops->force_safe();
        context->state = PERIPHERAL_STATE_FAILED;

        fault_log_stage_in_backup_ram(
            FAULT_PERIPHERAL_RECOVERY_LIMIT);

        return RECOVERY_ERR_LIMIT;
    }

    context->recovery_count++;
    context->state = PERIPHERAL_STATE_RECOVERING;

    /*
     * 必须先阻止业务继续提交请求，并将危险输出置于安全状态。
     */
    ops->force_safe();

    if (!ops->quiesce()) {
        context->state = PERIPHERAL_STATE_DEGRADED;
        return RECOVERY_ERR_QUIESCE;
    }

    /*
     * reset() 应清理外设、DMA、中断挂起位和总线错误状态。
     */
    if (!ops->reset()) {
        context->state = PERIPHERAL_STATE_FAILED;
        return RECOVERY_ERR_RESET;
    }

    if (!ops->initialize()) {
        context->state = PERIPHERAL_STATE_DEGRADED;
        return RECOVERY_ERR_REINIT;
    }

    if (!ops->self_test()) {
        context->state = PERIPHERAL_STATE_DEGRADED;
        return RECOVERY_ERR_SELF_TEST;
    }

    context->last_recovery_ms = platform_get_tick_ms();
    context->state = PERIPHERAL_STATE_ONLINE;

    fault_log_write(FAULT_PERIPHERAL_RECOVERED,
                    context->recovery_count,
                    context->first_error,
                    context->last_error,
                    context->last_recovery_ms);

    return RECOVERY_OK;
}
```

#### CAN 外设恢复实现

```
static bool can_quiesce(void)
{
    can_disable_tx_requests();
    can_disable_rx_interrupts();

    return can_wait_tx_idle(2U);
}

static bool can_reset_controller(void)
{
    can_abort_all_tx();

    dma_disable(CAN_RX_DMA);
    dma_disable(CAN_TX_DMA);

    nvic_disable_irq(CAN_RX_IRQn);
    nvic_disable_irq(CAN_TX_IRQn);
    nvic_clear_pending_irq(CAN_RX_IRQn);
    nvic_clear_pending_irq(CAN_TX_IRQn);

    platform_peripheral_reset_assert(PERIPHERAL_CAN);
    platform_delay_us(10U);
    platform_peripheral_reset_release(PERIPHERAL_CAN);

    return true;
}

static bool can_reinitialize(void)
{
    if (!can_configure_bitrate(CAN_NOMINAL_BITRATE,
                               CAN_DATA_BITRATE)) {
        return false;
    }

    can_clear_error_counters();
    can_clear_interrupt_flags();

    nvic_enable_irq(CAN_RX_IRQn);
    nvic_enable_irq(CAN_TX_IRQn);

    return can_enable();
}

static bool can_self_test(void)
{
    can_status_t status;

    if (!can_get_status(&status)) {
        return false;
    }

    return !status.bus_off &&
           (status.rx_error_count < 128U) &&
           (status.tx_error_count < 128U);
}

static void can_force_safe(void)
{
    can_transceiver_set_standby(true);
}

static const peripheral_recovery_ops_t can_recovery_ops = {
    .quiesce = can_quiesce,
    .reset = can_reset_controller,
    .initialize = can_reinitialize,
    .self_test = can_self_test,
    .force_safe = can_force_safe
};

static peripheral_recovery_t can_recovery = {
    .recovery_limit = 3U,
    .state = PERIPHERAL_STATE_OFFLINE
};

void can_health_periodic(void)
{
    if (!can_is_bus_off() && !can_has_fatal_error()) {
        return;
    }

    recovery_result_t result =
        peripheral_try_recover(&can_recovery,
                               &can_recovery_ops,
                               can_get_last_error());

    if (result == RECOVERY_OK) {
        can_transceiver_set_standby(false);
        return;
    }

    if ((result == RECOVERY_ERR_LIMIT) ||
        (result == RECOVERY_ERR_RESET)) {
        system_enter_degraded_mode(
            DEGRADED_REASON_CAN_FAILURE);
    }
}
```

#### 设计约束

恢复计数不能在任意一次成功后立即清零，否则持续干扰可能形成“失败—恢复—失败”的无限循环。推荐使用时间窗口：

```
恢复成功
├─ 连续稳定运行达到 10 min
│  └─ 恢复预算减少 1 次或重新初始化
└─ 稳定时间不足再次故障
   └─ 累加恢复次数并提高故障等级
```

### 10.4 EMC 故障日志框架

故障日志必须能够回答：

- 哪个模块首先失效。
- 失效前电源、时钟和通信状态如何。
- MCU 是否发生 Brownout、看门狗或外部复位。
- 恢复执行了几次。
- 故障是否与特定业务负载同步。
- 设备最终自动恢复、降级还是进入安全状态。

```
#define EMC_EVENT_BUFFER_SIZE  32U

typedef enum {
    EMC_EVENT_ESD_SUSPECTED = 0,
    EMC_EVENT_BROWNOUT,
    EMC_EVENT_CLOCK_FAILURE,
    EMC_EVENT_COMMUNICATION_ERROR,
    EMC_EVENT_PERIPHERAL_TIMEOUT,
    EMC_EVENT_UNEXPECTED_INTERRUPT,
    EMC_EVENT_RECOVERY_STARTED,
    EMC_EVENT_RECOVERY_FAILED,
    EMC_EVENT_SAFE_STATE
} emc_event_type_t;

typedef struct {
    uint32_t timestamp_ms;
    emc_event_type_t type;
    uint32_t source;
    uint32_t detail;
    uint16_t supply_mv;
    uint16_t reset_flags;
} emc_event_t;

typedef struct {
    emc_event_t events[EMC_EVENT_BUFFER_SIZE];
    uint32_t write_index;
    uint32_t event_count;
} emc_event_log_t;

static emc_event_log_t emc_log;

void emc_event_record(emc_event_type_t type,
                      uint32_t source,
                      uint32_t detail)
{
    uint32_t index =
        emc_log.write_index % EMC_EVENT_BUFFER_SIZE;

    emc_event_t *event = &emc_log.events[index];

    event->timestamp_ms = platform_get_tick_ms();
    event->type = type;
    event->source = source;
    event->detail = detail;
    event->supply_mv = platform_read_supply_mv();
    event->reset_flags =
        (uint16_t)platform_get_cached_reset_flags();

    emc_log.write_index =
        (index + 1U) % EMC_EVENT_BUFFER_SIZE;

    if (emc_log.event_count < EMC_EVENT_BUFFER_SIZE) {
        emc_log.event_count++;
    }
}
```

**生产级实现要求：**

- ISR 中只写固定大小 RAM 环形缓冲区。
- 不在 ESD/EFT 或欠压中直接擦写 Flash。
- 使用 CRC、序号和双副本保护持久化数据。
- 使用单调时钟或备份域时间戳。
- 启动早期保存复位源，之后再清除硬件标志。
- 日志接口不得阻塞实时控制任务。

### 10.5 EMC 故障注入运行模式

```
typedef struct {
    uint32_t loop_count;
    uint32_t crc_errors;
    uint32_t bus_timeouts;
    uint32_t unexpected_resets;
    uint32_t peripheral_recoveries;
    uint32_t safe_state_entries;
} emc_test_statistics_t;

static emc_test_statistics_t emc_test_stats;

void emc_test_cycle(void)
{
    uint8_t tx_data[64];
    uint8_t rx_data[64];

    platform_generate_test_pattern(tx_data,
                                   sizeof(tx_data),
                                   emc_test_stats.loop_count);

    if (!communication_loopback(tx_data,
                                rx_data,
                                sizeof(tx_data),
                                20U)) {
        emc_test_stats.bus_timeouts++;
        emc_event_record(
            EMC_EVENT_COMMUNICATION_ERROR,
            EMC_SOURCE_LOOPBACK,
            emc_test_stats.bus_timeouts);
    } else if (crc32_compute(tx_data, sizeof(tx_data)) !=
               crc32_compute(rx_data, sizeof(rx_data))) {
        emc_test_stats.crc_errors++;
        emc_event_record(
            EMC_EVENT_COMMUNICATION_ERROR,
            EMC_SOURCE_CRC,
            emc_test_stats.crc_errors);
    }

    if (!platform_peripheral_heartbeat_valid()) {
        emc_test_stats.peripheral_recoveries++;
        emc_event_record(
            EMC_EVENT_PERIPHERAL_TIMEOUT,
            EMC_SOURCE_HEARTBEAT,
            emc_test_stats.peripheral_recoveries);
    }

    emc_test_stats.loop_count++;
}
```

测试模式必须持续产生具有代表性的最坏工作负载：

- 最大通信流量。
- Flash、RAM 和 DMA 活动。
- 最大 GPIO 翻转。
- ADC 连续采样。
- PWM 和功率输出。
- 显示、背光或射频工作。
- 看门狗与安全监督。
- 可观测的外部心跳。

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业控制器 EFT 测试随机复位

### 需求

- 24 VDC 输入。
- 8 路数字输入。
- 4 路继电器输出。
- CAN 和 RS-485 通信。
- EFT 通过等级按产品适用标准定义。
- 干扰期间控制输出必须保持安全。

### 故障现象

- EFT 耦合到 24 V 电源线时 MCU 随机复位。
- 对 RS-485 线注入时出现通信超时。
- 日志偶尔记录 Brownout，偶尔无有效记录。
- 增加输入大电解电容后改善有限。

### 源—路径—受害者模型

```
干扰源：
EFT 脉冲串

耦合路径：
24 V 线缆
→ 输入滤波
→ DC/DC 寄生电容
→ 数字地
→ MCU 电源与复位网络

受害者：
MCU VDD、NRST、晶振、RS-485 控制状态
```

### 根因

1. 输入共模高频电流没有低阻抗机壳返回路径。
2. TVS 和输入电容离连接器较远。
3. DC/DC 输入高频回路跨越数字控制区域。
4. NRST 上拉阻值过大，走线靠近继电器驱动。
5. 软件在外设超时后无限重试。
6. 复位日志在初始化完成后才读取。

### 整改架构

```
24 V 连接器
├─ 机壳参考与屏蔽连接
├─ 入口 TVS
├─ 共模滤波
├─ 差模滤波
├─ 输入储能
└─ DC/DC
   ├─ 紧凑输入热回路
   └─ 控制侧低阻抗 PDN
```

### 核心代码

```
typedef struct {
    uint32_t reset_flags;
    uint32_t boot_counter;
    uint32_t previous_uptime_ms;
    uint32_t crc32;
} early_reset_record_t;

void early_boot_capture(void)
{
    early_reset_record_t record;

    record.reset_flags =
        platform_read_reset_flags_raw();

    record.boot_counter =
        backup_register_read(BOOT_COUNTER_INDEX) + 1U;

    record.previous_uptime_ms =
        backup_register_read(UPTIME_INDEX);

    record.crc32 = crc32_compute(
        &record,
        sizeof(record) - sizeof(record.crc32));

    backup_sram_write(&record, sizeof(record));
    backup_register_write(BOOT_COUNTER_INDEX,
                          record.boot_counter);

    platform_clear_reset_flags();
}
```

### 整改结果示例

|指标|整改前|整改后|
|---|---|---|
|EFT 注入期间复位|多次|未观测到|
|RS-485 超时|每分钟数次|偶发且自动恢复|
|NRST 瞬态幅度|约 1.1 V|小于 0.25 V|
|3.3 V 最低值|2.79 V|3.16 V|
|故障日志完整率|不稳定|100% 捕获测试事件|

### 设计要点

- EFT 是重复脉冲串，既要阻断单脉冲，也要避免软件错误累积。
- 输入大电容主要处理较低频能量，不能代替高频共模路径设计。
- 安全输出必须由硬件默认态和驱动级 Enable 共同保护。

---

## 11.2 案例二：Ethernet 产品辐射发射超限

### 需求

- 100BASE-TX Ethernet。
- 塑料机壳。
- 1 m 非屏蔽网线。
- Cortex-M7 + 外部 PHY。
- 需满足目标产品的辐射发射限值。

### 故障现象

- 125 MHz 及其倍频附近存在明显超限。
- 断开网线后辐射峰值下降超过 10 dB。
- 在 PHY 上增加屏蔽罩后仅改善约 2 dB。
- 近场扫描显示 PHY 时钟区域能量较强。

### 判断

断开网线后显著改善，说明**线缆共模电流是主要辐射天线**，PHY 局部场只是激励源之一。

### 根因

1. 变压器中心抽头去耦回路较长。
2. 差分对在连接器附近环境不对称。
3. ESD 器件两线寄生电容不匹配。
4. 数字地与接口屏蔽参考之间缺少受控高频路径。
5. PHY 时钟使用最高驱动强度。
6. 网口下方存在参考平面不连续。

### 整改

- 优化中心抽头去耦和回流。
- 使用匹配的低电容 ESD 阵列。
- 修复差分对过孔与焊盘对称性。
- 对屏蔽连接器建立低电感机壳路径。
- 修复网口区域参考平面。
- 降低 PHY 时钟驱动强度。
- 用共模电流探头验证线缆电流变化。

### 结果示例

|指标|整改前|整改后|
|---|---|---|
|125 MHz 线缆共模电流|1.2 mA|0.19 mA|
|125 MHz 辐射峰值|超限 7 dB|低于限值 4 dB|
|250 MHz 辐射峰值|超限 3 dB|低于限值 5 dB|
|链路误码率|合格|合格|
|ESD 抗扰度|偶发掉链|自动恢复且无复位|

### 核心代码

```
typedef struct {
    uint32_t link_down_count;
    uint32_t crc_error_count;
    uint32_t phy_reset_count;
    uint32_t last_link_down_ms;
} ethernet_emc_diag_t;

static ethernet_emc_diag_t ethernet_diag;

void ethernet_monitor_periodic(void)
{
    if (ethernet_phy_link_is_up()) {
        ethernet_diag.crc_error_count +=
            ethernet_get_and_clear_crc_errors();
        return;
    }

    ethernet_diag.link_down_count++;
    ethernet_diag.last_link_down_ms =
        platform_get_tick_ms();

    if (ethernet_diag.phy_reset_count < 2U) {
        ethernet_diag.phy_reset_count++;

        ethernet_disable_traffic();
        ethernet_phy_reset();
        ethernet_phy_initialize();
        ethernet_enable_traffic();
    } else {
        ethernet_enter_degraded_mode();
    }
}
```

### 设计要点

- 辐射超限时应先判断天线是谁：PCB、线缆、机壳开口还是散热结构。
- 屏蔽罩无法替代线缆共模电流控制。
- 差分接口中的微小不对称可能产生显著共模辐射。

---

## 11.3 案例三：电机控制器 ESD 导致功率级误导通

### 需求

- 48 V PMSM 控制器。
- 三相逆变桥。
- 20 kHz PWM。
- 金属机壳。
- 外接编码器、通信和电机线缆。
- ESD 干扰期间不允许桥臂上下管同时导通。

### 故障现象

- 对编码器连接器附近空气放电时，偶发驱动器 Fault。
- 某些样机出现短时异常 PWM。
- MCU 日志未记录复位。
- 功率级电流探头观察到异常尖峰。

### 根因

1. 栅极驱动器 Enable 为高阻输入，外部下拉过弱。
2. 编码器屏蔽层通过长线连接数字地。
3. 驱动器 Fault 和 PWM 走线靠近接口泄放路径。
4. 软件仅在周期任务中检查驱动器 Fault。
5. PWM 安全关断依赖 CPU 中断响应。

### 整改架构

```
编码器连接器
├─ 屏蔽层 360° 接机壳
├─ ESD 入口泄放
├─ 共模滤波
└─ 差分接收器

功率驱动
├─ Enable 强下拉
├─ 硬件互锁
├─ DESAT/过流检测
├─ MCU Timer Break 输入
└─ 软件诊断与日志
```

### 核心代码

```
void motor_safety_init(void)
{
    /*
     * Timer Break 必须由硬件异步关闭 PWM，
     * 不依赖 CPU ISR 延迟。
     */
    timer_break_config_t config = {
        .active_level = TIMER_BREAK_ACTIVE_LOW,
        .filter_cycles = 2U,
        .automatic_output_enable = false,
        .lock_level = TIMER_LOCK_LEVEL_HIGH
    };

    platform_timer_configure_break(MOTOR_TIMER,
                                   &config);

    platform_gate_driver_enable(false);
    platform_pwm_outputs_enable(false);
}

void motor_fault_isr(void)
{
    uint32_t fault = platform_gate_driver_fault_raw();

    /*
     * PWM 已被硬件 Break 关闭。
     * ISR 仅负责锁存状态和禁止自动恢复。
     */
    platform_pwm_outputs_enable(false);
    platform_gate_driver_enable(false);

    fault_log_stage_in_backup_ram(
        FAULT_GATE_DRIVER_EMC);

    motor_latch_fault(fault);
}
```

### 结果示例

|指标|整改前|整改后|
|---|---|---|
|ESD 时异常 PWM|偶发|未观测到|
|驱动器 Fault|多次|少量受控触发|
|最大关断时间|软件路径约 40 µs|硬件路径小于 1 µs|
|功率级异常电流|明显尖峰|未超过保护阈值|
|自动恢复行为|不确定|故障锁存，人工确认恢复|

### 设计要点

- 对危险功率输出，**固件恢复能力不能替代硬件异步关断**。
- 屏蔽电流应进入机壳，不应穿越控制地。
- 抗扰度测试不仅检查“是否复位”，还要检查输出是否进入危险状态。

---

# 12. 高频问题深度答疑

## 12.1 EMC 与 EMI 有什么区别？

**EMC 是系统能力，EMI 是干扰现象或发射问题。**

```
EMC
├─ Emission：不能过度干扰别人
└─ Immunity：外部干扰下仍满足性能判据
```

只解决辐射发射并不等于产品具备完整 EMC 能力。产品还必须处理 ESD、EFT、浪涌、射频场、电压跌落等抗扰度问题。

## 12.2 为什么频谱仪看到某个时钟频点，就不能直接认定时钟线是天线？

频谱峰值只说明该频率存在能量，不代表辐射结构就是时钟线本身。常见路径是：

```
时钟源
→ PCB 上的差模电流
→ 参考面不连续或接口不对称
→ 转换为共模电流
→ 外部线缆辐射
```

应执行：

1. 关闭或改变时钟频率。
2. 观察频谱峰值是否随之移动。
3. 使用近场探头定位源区。
4. 使用电流探头测量线缆共模电流。
5. 分别处理源、模式转换点和天线。

## 12.3 共模扼流圈是否一定能降低辐射？

不一定。它只有在以下条件下才可能有效：

- 主要问题确实是共模电流。
- 目标频率处共模阻抗足够高。
- 工作电流下未饱和。
- 寄生差模影响可以接受。
- PCB 没有从扼流圈两侧发生高频跨越耦合。
- 接口不对称没有在器件之后重新产生共模。

如果问题是差模回路、地裂缝或 PCB 本身辐射，共模扼流圈可能几乎无效。

## 12.4 TVS 钳位电压低，是否就一定保护得更好？

不是。还必须考虑：

- 测试电流下的动态钳位电压。
- 动态电阻。
- 寄生电容。
- 漏电流。
- 脉冲功率和能量能力。
- 保护路径电感。
- TVS 到接口与参考地的布局。
- 后级芯片钳位电流能力。

芯片端电压近似包括：

Vchip≈VTVS+Lpathdidt+I⋅RpathVchip​≈VTVS​+Lpath​dtdi​+I⋅Rpath​

布局不良时，路径电感产生的电压可能超过不同 TVS 型号之间的钳位差异。

## 12.5 数字地和机壳地应该单点连接还是多点连接？

没有脱离频率和系统结构的固定答案。

- 低频地环路问题常倾向于单点或受控连接。
- 高频共模泄放通常需要短、宽、多点、低电感连接。
- 混合方案可使用电容、RC、火花间隙或专用耦合结构。
- 安全保护地连接必须服从安全规范，不能只按 EMC 优化。

决策依据应包括：

- 线缆屏蔽方式。
- 机壳材料。
- 安全等级。
- 目标频段。
- 是否隔离。
- 外部设备之间的地电位差。
- 共模电流实际返回路径。

## 12.6 软件看门狗是否能解决 EMC 引起的死机？

只能解决一部分“CPU 仍可被复位”的故障，不能解决：

- 电源越过绝对最大值。
- 芯片闩锁。
- 时钟完全失效且看门狗同源。
- 外设持续驱动危险输出。
- Flash 已损坏。
- 看门狗任务仍运行但业务任务失效。

更稳健的方案是：

```
任务健康位
+ 窗口看门狗
+ 独立时钟源
+ 外部复位监控
+ 硬件安全输出
+ 故障日志
```

## 12.7 为什么加屏蔽罩后改善很小？

可能原因：

- 真正天线是外部线缆。
- 屏蔽罩接地连接电感过大。
- 屏蔽罩存在较大开口或接缝。
- 干扰通过电源或地传导出去。
- 屏蔽罩内部场通过接口直接激励线缆。
- 屏蔽罩改变了谐振频率，但没有减少总共模电流。

应先定位源、路径和天线，再决定是否使用屏蔽罩。

---

# 13. 课程核心总结

## 核心要点

- **EMC 问题必须使用“干扰源—耦合路径—敏感受害者”模型分析。**
- **产品级 EMC 的边界包括芯片、PCB、连接器、线缆、机壳和安装环境。**
- **差模电流通常由功能回路产生，共模电流通常决定线缆辐射能力。**
- **高 dv/dtdv/dt 通过寄生电容耦合，高 di/dtdi/dt 通过互感和共享阻抗耦合。**
- **回流路径不连续会扩大环路并造成差模到共模的转换。**
- **ESD 防护的关键是入口钳位和低电感泄放，而不只是 TVS 型号。**
- **EFT 强调重复快速脉冲和系统恢复，浪涌强调能量分级承受能力。**
- **屏蔽必须为高频共模电流提供低阻抗路径。**
- **固件能够增强系统韧性，但不能替代能量防护、PCB 回流和硬件安全关断。**
- **预兼容阶段应同时测量频谱、线缆共模电流、电源、复位和业务错误。**

## 性能排序

通用工业产品的 EMC 整改优先级通常为：

```
识别源、路径和受害者
> 修复接口及机壳共模回流
> 缩小高 dv/dt、高 di/dt 回路
> 保持参考平面连续
> 控制边沿和模式转换
> 优化入口保护与滤波
> 保护复位、时钟和敏感输入
> 增加硬件监督和安全关断
> 增加固件恢复与日志
> 最后考虑局部屏蔽
```

## 通用选型结论

- **外接线缆接口**：入口 TVS、共模控制、低电感机壳路径。
- **开关电源**：优先优化热回路、SW 节点和反馈，再设计滤波。
- **低速外部 GPIO**：按 ESD/EFT 入口和线缆天线处理。
- **差分接口**：同时控制差分阻抗、对称性、共模范围与保护寄生。
- **安全输出**：使用硬件互锁、默认安全态和异步关断。
- **抗扰度恢复**：有限重试、状态重建、降级和故障锁存。
- **认证策略**：设计阶段预兼容，正式认证前保留工程裕量。

---

# 14. 快速参考速查表

## 14.1 关键公式

|项目|公式|
|---|---|
|边沿有效带宽|fknee≈0.35/trfknee​≈0.35/tr​|
|电容耦合电流|iC=Cp⋅dv/dtiC​=Cp​⋅dv/dt|
|感性耦合电压|VM=M⋅di/dtVM​=M⋅di/dt|
|共阻抗噪声|Vn=I⋅ZsharedVn​=I⋅Zshared​|
|寄生电感电压|VL=L⋅di/dtVL​=L⋅di/dt|
|自由空间波长|λ=c/fλ=c/f|
|RC 截止频率|fc=1/(2πRC)fc​=1/(2πRC)|
|一阶低通幅频响应|$|
|Snubber 阻值初估|R≈L/CR≈L/C​|
|Snubber 功耗初估|P≈CV2fP≈CV2f|
|幅度分贝比|20log⁡10(A2/A1)20log10​(A2​/A1​)|

## 14.2 场景选型表

|场景|首要风险|优先措施|
|---|---|---|
|24 V 工业电源|EFT、浪涌、共模|入口保护、共模/差模滤波|
|CAN/RS-485|长线缆、ESD、共模|TVS、终端、短支线、隔离|
|Ethernet|线缆共模辐射|对称差分、中心抽头、屏蔽路径|
|USB|ESD、差分失衡|低电容 TVS、对称布局|
|Buck|SW 节点、热回路|缩环路、Snubber、滤波|
|电机逆变|高 dv/dtdv/dt、di/dtdi/dt|分区、隔离、硬件关断|
|ADC|参考和高阻输入|限带、连续地、低噪声供电|
|复位/启动脚|瞬态误触发|强偏置、RC、短走线、监控|
|金属机壳|屏蔽电流和接缝|360° 搭接、低电感连接|
|塑料机壳|线缆成为主天线|控制接口共模电流|

## 14.3 EMC Review Checklist

|检查项|结果|
|---|---|
|是否明确产品适用标准和版本|□|
|是否定义所有端口的测试项目与等级|□|
|是否定义性能判据和安全状态|□|
|是否识别高 dv/dtdv/dt 节点|□|
|是否识别高 di/dtdi/dt 回路|□|
|是否分析差模和共模路径|□|
|高速信号参考平面是否连续|□|
|接口保护是否靠近连接器|□|
|瞬态泄放是否避开数字核心区|□|
|保护器件寄生是否满足信号要求|□|
|屏蔽层是否低电感连接机壳|□|
|是否检查线缆共模电流路径|□|
|Buck 热回路是否最小|□|
|SW 节点面积是否受控|□|
|复位、晶振和启动脚是否受保护|□|
|外部输入是否有偏置、迟滞和限带|□|
|是否配置最低必要 GPIO Slew|□|
|安全输出是否具备硬件关断|□|
|外设恢复次数是否受限|□|
|是否保存最早复位原因|□|
|是否避免欠压期间写 Flash|□|
|是否进行近场扫描|□|
|是否测量线缆共模电流|□|
|是否完成最坏业务模式预兼容测试|□|
|整改是否有前后量化数据|□|

---

# 15. 学习效果自检

完成本课后，应能够独立完成：

- [ ]  准确定义 EMC、EMI、EMS 和产品级 EMC。
- [ ]  为故障建立源—路径—受害者模型。
- [ ]  区分传导发射、辐射发射和抗扰度问题。
- [ ]  区分差模和共模电流。
- [ ]  计算寄生电容耦合电流。
- [ ]  计算互感和共享阻抗引起的噪声。
- [ ]  根据边沿时间估算主要频谱。
- [ ]  根据线缆长度估算高风险频段。
- [ ]  识别 Buck 的热回路和 SW 节点。
- [ ]  识别高速信号跨越参考平面裂缝的问题。
- [ ]  审查 ESD TVS 的位置、回流和寄生参数。
- [ ]  设计 EFT 输入过滤和有限恢复机制。
- [ ]  解释浪涌为什么需要分级能量防护。
- [ ]  判断共模扼流圈是否适用于当前问题。
- [ ]  设计机壳地、屏蔽层和数字地的高频路径。
- [ ]  为安全输出配置硬件异步关断。
- [ ]  编写外设有限恢复和 EMC 故障日志代码。
- [ ]  使用近场探头定位源区。
- [ ]  使用电流探头识别线缆共模电流。
- [ ]  建立完整的 EMC 预兼容测试矩阵。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：GPIO 边沿与频谱实验

分别配置低、中、高 Slew，记录：

- 10%～90% 上升时间。
- 过冲和振铃。
- 近场频谱。
- 电源电流尖峰。
- 接收端 Setup/Hold 裕量。

输出：

```
Slew 档位
→ 边沿时间
→ 频谱拐点
→ 发射峰值
→ 时序裕量
→ 最终选型
```

### 任务二：Buck 热回路定位

使用 H 场近场探头扫描：

- 输入电容。
- MOSFET。
- SW 节点。
- 电感。
- 输出电容。
- 反馈网络。

对比以下修改：

- 输入电容位置。
- SW 节点面积。
- 栅极电阻。
- RC Snubber。
- 开关频率。

### 任务三：接口 ESD 路径对比

设计两个版本：

```
版本 A：TVS 距连接器 50 mm
版本 B：TVS 紧靠连接器并直接泄放到接口参考
```

记录：

- 芯片端残余电压。
- 数字地抬升。
- 复位次数。
- 通信掉线次数。
- TVS 电流路径。
- 近场瞬态分布。

### 任务四：线缆共模电流实验

分别改变：

- 线缆长度。
- 屏蔽层连接方式。
- 共模扼流圈型号。
- 机壳地连接。
- 差分保护器件。
- 接口参考平面。

记录线缆共模电流与辐射峰值的相关性。

### 任务五：EFT 软件韧性测试

在 EFT 注入期间持续运行：

- CAN/RS-485 通信。
- CRC 数据交换。
- ADC 采样。
- Flash 只读校验。
- 外设心跳。
- 安全输出监督。
- 独立看门狗。

验证：

- 错误是否被记录。
- 是否存在无限重试。
- 恢复次数是否受限。
- 危险输出是否始终安全。
- 干扰停止后是否按判据恢复。

### 任务六：完整 EMC 预兼容计划

建立测试矩阵：

```
测试项目
├─ 传导发射
├─ 辐射发射
├─ ESD
├─ EFT
├─ Surge
├─ 传导射频抗扰度
├─ 辐射射频抗扰度
└─ 电压跌落与短时中断
```

每项定义：

- 端口。
- 等级。
- 工作模式。
- 性能判据。
- 安全状态。
- 监控信号。
- 日志内容。
- 通过条件。
- 整改复测方法。

## 16.2 性能测试方法

|测试对象|推荐工具|核心指标|
|---|---|---|
|PCB 局部辐射源|E/H 近场探头、频谱仪|峰值频率、空间分布|
|线缆共模电流|高频电流探头|共模电流幅值与频谱|
|传导发射|LISN、EMI 接收机|准峰值、平均值|
|辐射发射|天线、转台、接收机|最大场强与裕量|
|ESD 残余电压|高带宽差分探头|芯片端峰值、地弹|
|EFT 抗扰度|EFT 发生器、耦合夹|错误率、复位、恢复|
|浪涌抗扰度|浪涌发生器|钳位、损伤、安全状态|
|射频抗扰度|CDN/天线、功放|功能偏差、通信错误|
|Buck EMI|近场探头、电流探头|SW 振铃、热回路辐射|
|软件韧性|自动化日志和压力程序|错误、恢复、降级次数|

## 16.3 推荐定位流程

```
发现 EMC 超限或抗扰度故障
├─ 固定可重复的测试配置
├─ 记录频率、端口、极性、位置和工作模式
├─ 判断是发射还是抗扰度问题
├─ 建立源—路径—受害者模型
├─ 判断差模还是共模
├─ 使用近场探头定位源区
├─ 使用电流探头检查线缆
├─ 同步测量电源、复位、时钟和错误日志
├─ 单变量实施整改
├─ 量化整改前后结果
└─ 回归 SI、PI、功能、热与安全测试
```

## 16.4 进阶学习方向

1. **EMC 场论**
    
    - 近场与远场。
    - 电偶极子与磁偶极子。
    - 屏蔽效能。
    - 波阻抗与边界条件。
    - 缝隙和开口辐射。
2. **共模建模**
    
    - 差模到共模转换。
    - 线缆天线模型。
    - 共模阻抗。
    - 机壳和保护地网络。
    - 屏蔽层端接。
3. **开关电源 EMI**
    
    - 热回路建模。
    - 栅极驱动优化。
    - Snubber 参数提取。
    - Spread Spectrum。
    - 输入滤波器稳定性。
    - 共模位移电流。
4. **瞬态防护**
    
    - IEC 61000-4-2 ESD。
    - IEC 61000-4-4 EFT。
    - IEC 61000-4-5 Surge。
    - TVS 动态模型。
    - 分级保护与能量协调。
5. **EMC 测量**
    
    - LISN 与人工电源网络。
    - 准峰值、峰值和平均值检波。
    - RBW/VBW。
    - 天线因子。
    - 探头校准。
    - 暗室相关性和测量不确定度。
6. **系统安全与韧性**
    
    - 硬件安全状态。
    - 独立看门狗。
    - 故障锁存。
    - 受限恢复。
    - EMC 故障注入。
    - FMEA、FTA 与安全时间预算。
7. **自动化验证**
    
    - 仪器远程控制。
    - 频谱自动扫描。
    - 故障日志时间关联。
    - 自动改变负载和工作模式。
    - EMC 结果与 PCB/BOM 版本绑定。
    - 将预兼容测试纳入设计发布门禁。