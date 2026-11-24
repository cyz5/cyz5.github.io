
> 本课以**典型 Cortex-M MCU 的时钟树、MCO（Microcontroller Clock Output）以及基于外部参考源的时钟校准**为主线。寄存器示例采用 STM32 风格命名，但不同系列的 MCO 分频编码、输出复用引脚、可选择时钟源和 RCC 寄存器位置可能不同，量产前必须以具体芯片参考手册为准。

---

# 1. 学习目标

## 1.1 理解

完成本课后，应能够：

- 理解 MCU 时钟树的组成：
    - 外部高速时钟 HSE；
    - 内部高速时钟 HSI；
    - 低速时钟 LSE/LSI；
    - PLL、分频器、倍频器；
    - 系统时钟 SYSCLK；
    - AHB、APB 总线时钟；
    - 外设内核时钟；
    - MCO 输出路径。
- 理解 MCO 的本质：

fMCO=fsourceNMCOfMCO​=NMCO​fsource​​

- 理解“时钟配置成功”与“时钟频率准确”是两个不同问题。
- 理解以下概念的工程区别：
    - 频率误差；
    - 周期抖动；
    - 短期稳定度；
    - 长期漂移；
    - 占空比；
    - 启动稳定时间；
    - 旁路模式；
    - 晶振驱动能力。

## 1.2 掌握

能够：

- 根据芯片参考手册配置 MCO 输出；
- 通过示波器、频率计、逻辑分析仪确认时钟实际输出；
- 使用 MCO 对系统时钟树进行分层验证；
- 计算 HSE、HSI、LSE、PLL 输出的实际频率误差；
- 使用外部 PPS、GNSS、TCXO、标准频率源对 MCU 时钟进行测量；
- 设计基于定时器捕获的频率校准流程；
- 识别时钟配置中常见的失效模式：
    - MCO 引脚未配置为复用输出；
    - GPIO 速度等级过低；
    - 时钟源未就绪；
    - PLL 参数错误；
    - MCO 分频编码理解错误；
    - 测量仪器输入负载造成波形失真；
    - 修改系统时钟后 SysTick、波特率、定时器周期未同步更新。

## 1.3 精通

能够深入分析：

- MCO 输出路径的寄存器级行为；
- 时钟切换过程中各级就绪标志和时序约束；
- HSE 晶振、旁路时钟、外部时钟输入的差异；
- PLL 输入频率、VCO 范围、输出分频和电压范围之间的约束；
- APB 定时器时钟倍频导致的实际定时器频率问题；
- MCO 对 EMI、功耗、抖动和系统实时性的影响；
- 频率校准中的测量窗口、量化误差和温漂补偿；
- 如何区分：
    - 时钟频率错误；
    - 计数器配置错误；
    - 测量设备误差；
    - 电气波形问题；
    - 软件时间基准问题。

## 1.4 能够设计

能够设计：

- 工业产品级的时钟初始化模块；
- 带失败回退机制的时钟启动流程；
- 可测试、可诊断的 MCO 输出调试接口；
- 基于外部参考源的 MCU 时钟偏差测量方案；
- 基于生产校准系数的频率补偿方案；
- 支持温度、老化、供电变化的时钟校准架构；
- 面向量产测试的时钟自检、频率窗口判定与故障记录机制。

---

# 2. 前置要求

## 2.1 知识要求

必须具备：

- C 语言：
    - 位操作；
    - `volatile`；
    - 内存映射寄存器；
    - 中断和 DMA；
    - 定点数；
    - 函数指针和模块化设计。
- MCU 硬件基础：
    - GPIO 复用；
    - 推挽输出；
    - 输入输出电平；
    - 时钟门控；
    - 复位与上电时序。
- Cortex-M 基础：
    - SysTick；
    - NVIC；
    - DWT CYCCNT；
    - 定时器捕获。
- RTOS 基础：
    - 系统节拍；
    - 软件定时器；
    - 临界区；
    - 中断延迟。
- 基本测量技术：
    - 示波器；
    - 频率计；
    - 逻辑分析仪；
    - 外部触发；
    - 探头负载；
    - 交流耦合与直流耦合。

## 2.2 技能要求

建议具备：

- 能够阅读 MCU 参考手册中的 RCC、GPIO、FLASH、PWR、TIM 章节；
- 能够使用寄存器级方式定位启动失败；
- 能够编写定时器输入捕获代码；
- 能够使用脚本处理采样数据；
- 能够阅读芯片时钟树图；
- 能够根据目标频率反推 PLL 参数；
- 能够搭建一个最小硬件测试板或使用开发板完成测量。

---

# 3. 技术概述

## 3.1 什么是 MCU 时钟系统

MCU 时钟系统负责为以下模块提供时间基准：

- CPU 内核；
- 总线矩阵；
- SRAM；
- Flash 接口；
- 定时器；
- UART、SPI、I2C、CAN、USB、ADC 等外设；
- RTC；
- 看门狗；
- 调试模块；
- MCO 输出。

典型时钟树可以抽象为：

```
┌──────────────┐
HSE ───────────────▶│              │
                    │     PLL      │──────▶ SYSCLK
HSI ───────────────▶│              │
                    └──────────────┘
                           │
                           ├────▶ AHB / HCLK
                           │
                           ├────▶ APB1 / PCLK1
                           │
                           ├────▶ APB2 / PCLK2
                           │
                           └────▶ MCO

LSE ───────────────────────────────────────▶ RTC
LSI ───────────────────────────────────────▶ IWDG / RTC
```

现代 MCU 往往还包括：

- 多个 PLL；
- 独立外设时钟；
- 时钟安全系统 CSS；
- 时钟恢复机制；
- 内核电压范围控制；
- Flash 等待周期；
- 动态电压频率调整 DVFS；
- 时钟监测器；
- 外部时钟输入检测；
- 低功耗时钟域。

## 3.2 MCO 的定义

MCO 是 MCU Clock Output 的缩写，用于将芯片内部某个时钟源输出到 GPIO 引脚。

常见可输出源包括：

- HSI；
- HSE；
- LSI；
- LSE；
- SYSCLK；
- PLL；
- HCLK；
- 某些外设内核时钟。

典型结构：

```
┌────────────┐
HSE ───────────▶│            │
HSI ───────────▶│ MCO选择器  │──▶ MCO分频器 ──▶ GPIO复用输出
PLL ───────────▶│            │
SYSCLK ────────▶│            │
                └────────────┘
```

输出频率为：

fMCO=fselectedDfMCO​=Dfselected​​

其中：

- fselectedfselected​：MCO 选择的时钟源频率；
- DD：MCO 分频系数；
- fMCOfMCO​：实际引脚输出频率。

## 3.3 MCO 的技术价值

MCO 不是简单的“输出一个方波”，它是一个非常重要的系统级调试和验证接口。

主要用途：

1. **验证时钟源是否正常**
    
    - HSE 是否起振；
    - HSI 是否存在；
    - LSE 是否工作；
    - PLL 是否锁定。
2. **验证 PLL 配置**
    
    - PLL 输出频率是否符合预期；
    - 分频和倍频参数是否正确；
    - 时钟切换后系统频率是否正确。
3. **校准内部振荡器**
    
    - 通过频率计量内部 HSI；
    - 与外部参考频率比较；
    - 计算校准偏差。
4. **量产测试**
    
    - 自动判断主频是否超出容差；
    - 判断晶振是否装配正确；
    - 判断焊接、负载电容、晶体型号是否匹配。
5. **系统级联调**
    
    - 为外部 FPGA、ADC、PHY 或测试设备提供参考时钟；
    - 观察频率是否存在漂移；
    - 分析低功耗唤醒后的时钟恢复状态。

## 3.4 时钟源分类

|时钟源|类型|典型精度|启动速度|温漂|典型用途|
|---|---|---|---|---|---|
|HSI|内部 RC|±0.5%～±3%|快，通常微秒级|较大|启动、低成本系统|
|HSE 晶振|外部晶体|±10～100 ppm|慢，毫秒级|较小|高精度主时钟|
|HSE 旁路|外部有源时钟|取决于外部源|较快|取决于外部源|时钟树、同步系统|
|LSI|内部低速 RC|±5%～±30%|快|大|独立看门狗|
|LSE|32.768 kHz 晶体|±10～100 ppm|慢|较小|RTC|
|TCXO|温补晶振|±0.5～10 ppm|毫秒级|很小|通信、测量、同步|
|外部 PPS|脉冲参考|取决于来源|取决于系统|很小|长期校准|
|USB SOF|总线参考|取决于 USB 主机|动态|中等|在线时基校准|

---

# 4. 核心特性横向对比

## 4.1 时钟源方案对比

|维度|HSI|HSE 晶振|HSE 旁路|TCXO|外部 PPS|
|---|---|---|---|---|---|
|硬件成本|低|中|中|较高|需要外部系统|
|初始精度|中低|高|高|极高|极高|
|短期稳定性|较差|好|好|极好|很好|
|长期稳定性|差|中|中高|高|极高|
|温漂|大|中|取决于外部|小|取决于参考源|
|启动速度|快|慢|中|中|不适合直接启动|
|低功耗适应性|好|一般|一般|一般|差|
|频率校准需求|常见|通常较少|取决于源|通常较少|适合做参考|
|对 PCB 敏感性|低|高|中|中|中|
|适合量产主时钟|成本型产品|通用工业产品|系统同步产品|高精度产品|校准、同步系统|

## 4.2 MCO 分频方案对比

|分频方式|频率关系|优点|缺点|适用场景|
|---|---|---|---|---|
|不分频|fout=fsrcfout​=fsrc​|频率最高，观察链路最短|GPIO 速度和 EMI 压力最大|高速时钟验证|
|2 分频|fout=fsrc/2fout​=fsrc​/2|易于测量，波形通常更好|无法直接验证原始源全部特性|通用调试|
|4/5/8 分频|fout=fsrc/Dfout​=fsrc​/D|频率低，仪器压力小|不能直接观察高频时钟细节|量产测试、低带宽测量|
|PLL 输出分频|取决于芯片|可验证 PLL 级联|可能受专用输出限制|PLL 调试|
|HSE 直接输出|fout=fHSE/Dfout​=fHSE​/D|验证晶振和负载|无法验证系统主频|HSE 硬件诊断|
|SYSCLK 输出|fout=fSYSCLK/Dfout​=fSYSCLK​/D|直接验证系统主频|可能受芯片 MCO 上限限制|系统时钟确认|

## 4.3 测量手段对比

|测量方法|分辨率|实时性|对被测系统影响|适合用途|
|---|---|---|---|---|
|示波器周期测量|中高|高|探头有负载|波形、启动、抖动|
|频率计|极高|中|极低|精确频率|
|逻辑分析仪|中|高|低|数字时序、频率粗测|
|定时器输入捕获|高|高|软件和引脚资源|在线校准|
|DWT CYCCNT|高|高|无引脚开销|CPU 周期测量|
|外部标准频率比较|极高|低～中|需要硬件连接|生产校准|
|GNSS PPS|长期高|低|需 GNSS|长期频率校准|

---

# 5. 底层原理与功能特性深度解析

## 5.1 时钟初始化的正确顺序

典型高速主频切换流程如下：

```
1. 复位 RCC 配置
2. 启动 HSE 或 HSI
3. 等待时钟源就绪
4. 配置电源电压范围
5. 配置 Flash 等待周期
6. 配置 PLL 输入、倍频、输出分频
7. 启动 PLL
8. 等待 PLL 锁定
9. 配置 AHB/APB 分频器
10. 切换 SYSCLK 到 PLL
11. 等待系统时钟切换完成
12. 更新 SystemCoreClock
13. 重配置 SysTick、RTOS Tick 和外设波特率
14. 可选：配置 MCO 输出
```

其中最容易被忽略的是：

- **必须先配置 Flash 等待周期，再提升 CPU 频率**；
- **必须先配置电源电压范围，再使用高频率**；
- **PLL 锁定不代表系统切换完成**；
- **系统时钟切换完成不代表所有外设时钟已正确更新**。

## 5.2 典型 PLL 频率计算

不同 MCU 的 PLL 公式不同，常见形式如下：

fPLL_VCO=fPLL_INM×NfPLL_VCO​=MfPLL_IN​​×NfSYSCLK=fPLL_VCOPfSYSCLK​=PfPLL_VCO​​fUSB=fPLL_VCOQfUSB​=QfPLL_VCO​​

例如：

- HSE = 8 MHz；
- M=8M=8；
- N=336N=336；
- P=2P=2；
- Q=7Q=7。

则：

fPLL_VCO=88×336=336 MHzfPLL_VCO​=88​×336=336 MHzfSYSCLK=3362=168 MHzfSYSCLK​=2336​=168 MHzfUSB=3367=48 MHzfUSB​=7336​=48 MHz

这说明一个 PLL 配置必须同时满足：

- PLL 输入范围；
- VCO 范围；
- SYSCLK 最大值；
- USB 等外设的精确频率要求；
- APB 最大频率；
- Flash 等待周期；
- 电源电压范围。

## 5.3 MCO 寄存器级配置模型

以 STM32F4 风格为例，MCO 通常由以下字段控制：

```
RCC_CFGR.MCO1[1:0]   MCO1 时钟源选择
RCC_CFGR.MCO1PRE     MCO1 分频
RCC_CFGR.MCO2[1:0]   MCO2 时钟源选择
RCC_CFGR.MCO2PRE     MCO2 分频
GPIOx.MODER          GPIO 模式
GPIOx.OSPEEDR        GPIO 输出速度
GPIOx.AFR[]          GPIO 复用选择
```

示例：

```
#include <stdint.h>
#include <stdbool.h>

#define RCC_BASE        0x40023800UL
#define GPIOA_BASE      0x40020000UL

#define RCC_AHB1ENR     (*(volatile uint32_t *)(RCC_BASE + 0x30U))
#define RCC_CFGR        (*(volatile uint32_t *)(RCC_BASE + 0x08U))

#define GPIOA_MODER     (*(volatile uint32_t *)(GPIOA_BASE + 0x00U))
#define GPIOA_OSPEEDR   (*(volatile uint32_t *)(GPIOA_BASE + 0x08U))
#define GPIOA_AFRH      (*(volatile uint32_t *)(GPIOA_BASE + 0x24U))

#define RCC_AHB1ENR_GPIOAEN    (1UL << 0)

/*
 * 以下位定义仅适用于特定 STM32 系列风格。
 * 量产代码必须替换为目标芯片头文件中的官方定义。
 */
#define RCC_CFGR_MCO2_Pos      30U
#define RCC_CFGR_MCO2_Msk      (3UL << RCC_CFGR_MCO2_Pos)

#define RCC_CFGR_MCO2PRE_Pos   27U
#define RCC_CFGR_MCO2PRE_Msk   (7UL << RCC_CFGR_MCO2PRE_Pos)

#define GPIO_PIN_9             9U
#define GPIO_AF0               0U

static void mco2_gpio_init(void)
{
    /* 1. 打开 GPIOA 时钟 */
    RCC_AHB1ENR |= RCC_AHB1ENR_GPIOAEN;

    /*
     * 2. PA9 配置为复用模式
     * MODER[19:18] = 10b
     */
    GPIOA_MODER &= ~(3UL << (GPIO_PIN_9 * 2U));
    GPIOA_MODER |=  (2UL << (GPIO_PIN_9 * 2U));

    /*
     * 3. 设置高速输出，避免高频 MCO 下边沿过慢
     * 11b = very high speed，具体编码随 MCU 系列变化
     */
    GPIOA_OSPEEDR &= ~(3UL << (GPIO_PIN_9 * 2U));
    GPIOA_OSPEEDR |=  (3UL << (GPIO_PIN_9 * 2U));

    /*
     * 4. PA9 选择对应 AF
     * PA9 属于 AFRH 的第 1 个字段
     */
    GPIOA_AFRH &= ~(0xFUL << 4U);
    GPIOA_AFRH |=  ((uint32_t)GPIO_AF0 << 4U);
}

static bool mco2_config(uint32_t source_bits,
                        uint32_t prescaler_bits)
{
    /*
     * 对 RCC 配置寄存器的读改写必须保证字段互斥。
     * 如果系统中存在多个执行上下文修改 RCC，需要加锁或在启动阶段完成。
     */
    uint32_t reg = RCC_CFGR;

    reg &= ~(RCC_CFGR_MCO2_Msk | RCC_CFGR_MCO2PRE_Msk);
    reg |= ((source_bits << RCC_CFGR_MCO2_Pos) & RCC_CFGR_MCO2_Msk);
    reg |= ((prescaler_bits << RCC_CFGR_MCO2PRE_Pos) &
            RCC_CFGR_MCO2PRE_Msk);

    RCC_CFGR = reg;

    return true;
}
```

### 工程注意事项

1. **MCO GPIO 的 AF 编号不是固定的**；
2. 某些芯片的 MCO 引脚可能是：
    - PA8；
    - PC9；
    - PB0；
    - 某个专用时钟输出引脚；
3. GPIO 输出速度等级影响：
    - 边沿时间；
    - 高频损耗；
    - EMI；
    - 输出短路电流；
4. MCO 频率过高时，示波器探头的地线长度会显著影响波形；
5. 不应将 MCO 长距离引出而不进行阻抗控制。

## 5.4 时钟源就绪标志

典型 RCC 状态位：

```
HSIRDY：HSI 就绪
HSERDY：HSE 就绪
PLLRDY：PLL 锁定
LSERDY：LSE 就绪
LSIRDY：LSI 就绪
SWS：当前 SYSCLK 来源
```

正确的启动代码必须：

- 设置启动请求位；
- 使用超时等待；
- 检查就绪状态；
- 失败后回退到安全时钟；
- 记录故障原因。

```
typedef enum
{
    CLOCK_OK = 0,
    CLOCK_ERR_HSE_TIMEOUT,
    CLOCK_ERR_PLL_TIMEOUT,
    CLOCK_ERR_SWITCH_TIMEOUT,
    CLOCK_ERR_INVALID_CONFIG
} clock_status_t;

static clock_status_t wait_flag_set(volatile uint32_t *reg,
                                    uint32_t mask,
                                    uint32_t timeout)
{
    while (timeout > 0U)
    {
        if ((*reg & mask) != 0U)
        {
            return CLOCK_OK;
        }

        timeout--;
    }

    return CLOCK_ERR_HSE_TIMEOUT;
}
```

生产级实现中，建议使用：

- DWT 周期计数器作为超时基准；
- 独立低速时钟作为超时参考；
- 早期启动阶段使用固定循环但必须按最坏情况设计；
- 在故障记录中保存：
    - RCC 当前值；
    - 电源状态；
    - 复位原因；
    - 温度；
    - 供电电压；
    - 启动阶段编号。

## 5.5 HSE 晶振与旁路模式

### 晶振模式

MCU 内部振荡器驱动外部晶体：

```
OSC_IN ── 晶体 ── OSC_OUT
   │                 │
  CL1               CL2
   │                 │
  GND               GND
```

晶体负载电容近似关系：

CL=CL1×CL2CL1+CL2+CstrayCL​=CL1​+CL2​CL1​×CL2​​+Cstray​

对称电容时：

CL1=CL2=CCL1​=CL2​=C

则：

C≈2(CL−Cstray)C≈2(CL​−Cstray​)

例如：

- 晶体标称 CL=12.5 pFCL​=12.5 pF；
- PCB 和引脚寄生 Cstray=3 pFCstray​=3 pF。

则：

C≈2(12.5−3)=19 pFC≈2(12.5−3)=19 pF

但实际还需要考虑：

- MCU 内部输入电容；
- 走线寄生；
- 探头电容；
- 晶体驱动等级；
- ESR；
- 启动裕量；
- 温度和供电变化。

### 旁路模式

旁路模式由外部有源时钟直接驱动 OSC_IN：

```
TCXO / FPGA / 外部时钟源 ──▶ OSC_IN
OSC_OUT 不使用
```

此时：

- 不能再把它当作普通晶体；
- 外部源的电平幅度、占空比、输入门限必须满足数据手册；
- 某些 MCU 要求 OSC_OUT 保持悬空；
- 外部时钟源应有明确的上电顺序；
- MCO 输出可以用于验证旁路时钟是否进入 MCU。

## 5.6 MCO 输出波形不是理想方波

频率正确并不代表 MCO 可直接作为高质量时钟源。

需要关注：

- 上升时间；
- 下降时间；
- 占空比；
- 过冲；
- 下冲；
- 振铃；
- 负载电容；
- 输出驱动强度；
- PCB 走线阻抗；
- 电源噪声；
- 相位噪声；
- 周期抖动。

典型判定：

```
频率正确 + 波形边沿过慢      → GPIO速度/负载/走线问题
频率错误 + 波形稳定          → 时钟树或分频配置问题
频率随温度漂移               → RC源、晶振、供电或温度影响
波形偶发停止                 → 时钟源失锁、供电扰动或复位
占空比严重偏离 50%           → 输出路径、负载或测量方法问题
```

## 5.7 基于 MCO 的时钟频率测量

假设 MCO 输出频率为：

fmeas=fnom+Δffmeas​=fnom​+Δf

频率相对误差：

ϵ=fmeas−fnomfnomϵ=fnom​fmeas​−fnom​​

ppm 表示：

errorppm=fmeas−fnomfnom×106errorppm​=fnom​fmeas​−fnom​​×106

例如：

- 目标频率：8 MHz；
- 测得频率：8,000,240 Hz。

则：

errorppm=2408,000,000×106=30 ppmerrorppm​=8,000,000240​×106=30 ppm

## 5.8 基于外部参考脉冲的定时器捕获

如果外部参考频率为 freffref​，在固定参考时间窗口 TT 内统计 MCU 时钟计数值 NN，则：

fmcu=NTfmcu​=TN​

例如使用 1 PPS：

- 参考窗口 T=1 sT=1 s；
- MCU 定时器时钟计数 N=79,998,400N=79,998,400。

则实际频率：

fmcu=79,998,400 Hzfmcu​=79,998,400 Hz

相对于 80 MHz：

errorppm=−20 ppmerrorppm​=−20 ppm

### 输入捕获测量模型

```
PPS ──▶ TIMx 输入捕获
           │
           └──▶ 每个秒脉冲捕获一次
                 读取自由运行计数器差值
```

```
typedef struct
{
    uint32_t previous_capture;
    uint32_t current_capture;
    uint32_t ticks_per_second;
    int32_t  error_ppm;
    bool     valid;
} clock_measurement_t;

static uint32_t u32_delta(uint32_t current, uint32_t previous)
{
    /*
     * 无符号减法天然支持单次溢出回绕：
     * current - previous 在 uint32_t 下仍得到正确差值。
     */
    return current - previous;
}

static void clock_measurement_update(clock_measurement_t *m,
                                     uint32_t capture)
{
    if (m == NULL)
    {
        return;
    }

    if (!m->valid)
    {
        m->previous_capture = capture;
        m->valid = true;
        return;
    }

    m->current_capture = capture;
    m->ticks_per_second =
        u32_delta(m->current_capture, m->previous_capture);

    m->previous_capture = m->current_capture;

    /*
     * 目标频率假设为 80 MHz。
     * 这里使用 64 位中间结果避免乘法溢出。
     */
    const uint32_t nominal_hz = 80000000UL;

    m->error_ppm = (int32_t)(
        ((int64_t)m->ticks_per_second -
         (int64_t)nominal_hz) * 1000000LL /
        (int64_t)nominal_hz
    );
}
```

### 重要限制

如果定时器计数器频率为 80 MHz，使用 32 位计数器：

Toverflow=23280×106≈53.7 sToverflow​=80×106232​≈53.7 s

因此 1 秒 PPS 测量不会溢出问题。但如果：

- 测量窗口为 60 秒；
- 计数器频率超过 100 MHz；
- 使用低位宽计数器；

则必须使用：

- 定时器溢出扩展；
- 级联定时器；
- DMA 记录多个捕获值；
- 64 位软件计数器。

## 5.9 HSI 校准模型

内部 RC 频率通常受以下因素影响：

fHSI=f0+ΔfT+ΔfV+ΔfA+ΔfprocessfHSI​=f0​+ΔfT​+ΔfV​+ΔfA​+Δfprocess​

其中：

- ΔfTΔfT​：温度引起的偏差；
- ΔfVΔfV​：供电引起的偏差；
- ΔfAΔfA​：老化引起的偏差；
- ΔfprocessΔfprocess​：芯片制造工艺离散。

如果 MCU 提供 HSITRIM 寄存器，可采用线性近似：

fHSI(code)=fbase+Ktrim(code−code0)fHSI​(code)=fbase​+Ktrim​(code−code0​)

根据外部参考测得误差后更新校准码：

```
typedef struct
{
    int16_t trim_code;
    int32_t measured_error_ppm;
    int32_t target_error_ppm;
    bool    saturated;
} hsi_trim_result_t;

static int16_t hsi_trim_calculate(int16_t current_trim,
                                   int32_t measured_error_ppm,
                                   int32_t ppm_per_step,
                                   int16_t trim_min,
                                   int16_t trim_max)
{
    if (ppm_per_step <= 0)
    {
        return current_trim;
    }

    /*
     * 如果当前频率偏高，需要降低 trim；
     * 如果当前频率偏低，需要提高 trim。
     */
    int32_t correction = -measured_error_ppm / ppm_per_step;
    int32_t next = (int32_t)current_trim + correction;

    if (next < trim_min)
    {
        next = trim_min;
    }
    else if (next > trim_max)
    {
        next = trim_max;
    }

    return (int16_t)next;
}
```

实际产品中不能假设 `ppm_per_step` 永远固定，建议：

1. 在生产校准阶段对每颗芯片建立：
    - trim code；
    - 频率；
    - 温度；
    - 电压；
2. 计算分段线性模型；
3. 运行时查表插值；
4. 设置最大调整步长；
5. 对校准过程增加迟滞，避免 trim 抖动。

---

# 6. 性能量化分析

## 6.1 测试平台假设

以下数据基于一个典型测试平台：

- MCU：Cortex-M4F；
- 主频：168 MHz；
- HSE：8 MHz 晶体；
- HSI：16 MHz 内部 RC；
- MCO 输出：4 MHz～84 MHz；
- 编译器：GCC 12.x；
- 优化级别：`-O2`；
- 测量设备：
    - 500 MHz 示波器；
    - 1 GHz 频率计；
    - 10 MHz 外部 PPS；
- 电源：3.3 V；
- 环境温度：25 ℃；
- PCB：四层板，MCO 走线长度 35 mm。

实际数据会因芯片系列、封装、温度和 PCB 而变化，以下用于建立工程量级概念。

## 6.2 时钟启动时间

典型启动时间：

|阶段|典型时间|
|---|---|
|HSI 启动|1～10 μs|
|HSE 晶振启动|0.5～10 ms|
|PLL 锁定|10～200 μs|
|Flash 配置|<10 μs|
|时钟切换|数个 HCLK 周期|
|LSE 启动|0.2～2 s|

启动总时间近似：

Tstartup=Tsource+TPLL+Tswitch+TsoftwareTstartup​=Tsource​+TPLL​+Tswitch​+Tsoftware​

如果使用 HSE + PLL：

Tstartup≈2.5 msTstartup​≈2.5 ms

如果是低功耗系统，则必须评估：

- 每次唤醒是否重新启动 HSE；
- 是否保留 PLL；
- 是否使用 MSI、HSI 或低速源先运行；
- 启动期间看门狗是否会超时；
- RTOS Tick 是否提前启动。

## 6.3 MCO 输出开销

MCO 硬件输出本身不消耗 CPU 周期，主要开销来自：

- GPIO 电流；
- 输出翻转功耗；
- 时钟树动态功耗；
- EMI 处理成本；
- 额外 PCB 布线。

动态功耗近似为：

Pdynamic=αCLV2fPdynamic​=αCL​V2f

例如：

- α=1α=1；
- CL=10 pFCL​=10 pF；
- V=3.3 VV=3.3 V；
- f=50 MHzf=50 MHz。

则：

P=1×10 pF×3.32×50 MHz≈5.45 mWP=1×10 pF×3.32×50 MHz≈5.45 mW

若 GPIO 驱动和内部缓冲共同计入，实际增加功耗可能达到 **5～20 mW**。

## 6.4 频率测量量化误差

在固定时间窗口 TT 内计数，计数误差至少为 ±1 个计数：

δf=1Tδf=T1​

相对误差：

δrelative=1fTδrelative​=fT1​

对于 80 MHz 时钟：

|测量窗口|最小量化误差|
|---|---|
|1 ms|12.5 ppm|
|10 ms|1.25 ppm|
|100 ms|0.125 ppm|
|1 s|0.0125 ppm|

但实际误差还包括：

- 外部参考源误差；
- 输入同步器误差；
- 定时器时钟抖动；
- 捕获延迟；
- 中断处理不确定性；
- 温度变化；
- 供电噪声。

因此，**增加测量窗口可以降低量化误差，但不能消除系统性误差**。

## 6.5 PLL 频率误差传递

若 PLL 输出为：

fout=fin×Kfout​=fin​×K

则输入源相对误差基本等比例传递：

Δfoutfout≈Δfinfinfout​Δfout​​≈fin​Δfin​​

例如 HSE 有 +30 ppm 误差，则：

- SYSCLK 通常也约为 +30 ppm；
- UART 波特率也会出现相同量级误差；
- 定时器时间基准也会出现相同量级误差。

PLL 的倍频不会把相对误差放大成倍数，但会把**绝对频率误差**放大：

Δfout=KΔfinΔfout​=KΔfin​

## 6.6 UART 波特率误差

UART 接收可靠性与发送端、接收端的总时钟误差相关。

简化估算：

errortotal≈errorTX+errorRXerrortotal​≈errorTX​+errorRX​

如果：

- TX 误差：+1.2%；
- RX 误差：-1.0%。

则总相对误差约为：

0.2%0.2%

对于普通 UART，通常需要保持总误差在若干百分比以内，但具体容限取决于：

- 数据帧长度；
- 采样点；
- 过采样倍数；
- 起始位检测策略；
- 接收器容差。

**MCO 测量到的频率误差应与 UART 实际波特率误差联动分析。**

## 6.7 定时器时钟常见计算错误

在很多 STM32 风格 MCU 中，如果 APB 预分频器不为 1，定时器时钟可能为：

fTIM=2fPCLKfTIM​=2fPCLK​

例如：

- SYSCLK = 168 MHz；
- APB1 分频 = 4；
- PCLK1=42 MHzPCLK1=42 MHz；
- APB1 定时器时钟 = 84 MHz。

如果错误地按 42 MHz 配置定时器，实际周期会缩短一半。

这是 MCO 调试中经常遇到的现象：

```
MCO 显示 SYSCLK 正确
UART 波特率正确
但 TIM 定时周期错误
```

根因不是 SYSCLK，而是 **APB 定时器倍频规则理解错误**。

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
需要验证或校准时钟？
├── 仅确认系统是否运行在目标主频
│   ├── 有示波器/频率计
│   │   └── MCO 输出 SYSCLK 或 PLL
│   └── 无外部仪器
│       └── 使用定时器与已知外设时基交叉验证
│
├── 需要确认外部晶振硬件是否正常
│   ├── 直接测 OSC_IN/OSC_OUT？
│   │   └── 不建议作为首选，可能影响晶振负载
│   └── 使用 MCO 输出 HSE
│
├── 需要校准内部 HSI
│   ├── 有 PPS/GNSS
│   │   └── 定时器输入捕获 + 频率误差计算
│   ├── 有 USB 主机
│   │   └── 使用 USB SOF 作为参考
│   └── 只有外部串口
│       └── 精度有限，不建议作为生产校准依据
│
├── 需要高精度通信时钟
│   ├── 精度要求 > ±100 ppm
│   │   └── 优先 HSE/TCXO，不依赖未经校准的 HSI
│   ├── 精度要求 > ±10 ppm
│   │   └── TCXO/高精度晶振/外部同步源
│   └── 需要长期同步
│       └── PPS/PTP/SyncE 等系统级同步方案
│
└── 需要量产自动测试
    ├── 测试速度优先
    │   └── MCO 分频输出 + 频率窗口判定
    ├── 测试精度优先
    │   └── 频率计/标准源 + 固定测量窗口
    └── 需要在线运行
        └── 定时器捕获 + 滑动平均 + 故障阈值
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|板卡无法启动|MCO 输出 HSI/HSE|快速区分 CPU、晶振和 PLL 问题|
|判断 PLL 配置是否正确|MCO 输出 PLL 或 SYSCLK|验证完整主时钟链路|
|工厂校准 HSI|MCO + 频率计|测量路径简单，自动化程度高|
|在线校准定时器时基|PPS + TIM 输入捕获|直接得到 MCU 计数频率|
|高精度 CAN 通信|HSE 或 TCXO|RC 频率漂移过大|
|低功耗数据记录器|LSE + RTC|低功耗和长期计时优先|
|USB FS|HSE/PLL 精确生成 48 MHz|USB 对时钟误差要求高|
|ADC 采样同步|独立定时器时钟 + 外部触发|降低软件调度抖动|
|外设时钟输出给 FPGA|MCO 或专用时钟输出|需核对电气质量和抖动指标|
|量产判定晶振焊接|MCO 输出 HSE|不直接接触晶振节点，风险更低|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：时钟初始化必须可失败

禁止无超时等待：

```
while ((RCC->CR & RCC_CR_HSERDY) == 0U)
{
}
```

应改为：

```
uint32_t timeout = CLOCK_HSE_TIMEOUT;

while (((RCC->CR & RCC_CR_HSERDY) == 0U) &&
       (timeout > 0U))
{
    timeout--;
}

if ((RCC->CR & RCC_CR_HSERDY) == 0U)
{
    return CLOCK_ERR_HSE_TIMEOUT;
}
```

### 原则二：先安全配置，再提升频率

顺序必须满足：

```
电源范围 → Flash等待周期 → 总线分频 → PLL → SYSCLK切换
```

### 原则三：把“配置频率”和“验证频率”分离

配置代码负责：

- 选择源；
- 设置 PLL；
- 设置分频；
- 切换系统时钟。

验证代码负责：

- MCO 输出；
- 定时器测量；
- 频率窗口判断；
- 故障记录。

两者不要强耦合。

### 原则四：MCO 默认应可关闭

建议支持：

```
typedef enum
{
    MCO_OFF = 0,
    MCO_SOURCE_HSI,
    MCO_SOURCE_HSE,
    MCO_SOURCE_PLL,
    MCO_SOURCE_SYSCLK
} mco_source_t;
```

运行时关闭 MCO 的原因：

- 降低功耗；
- 降低 EMI；
- 避免输出时钟干扰邻近模拟电路；
- 避免对外部设备产生错误时钟。

## 8.2 选型决策矩阵

|指标|HSI|HSE|TCXO|PPS校准|
|---|---|---|---|---|
|成本|5|4|2|1|
|初始精度|2|4|5|5|
|启动速度|5|3|3|1|
|温度稳定性|1|3|5|4|
|量产一致性|2|4|5|4|
|低功耗|5|3|2|1|
|校准复杂度|3|4|5|2|
|通信适用性|2|4|5|5|

评分越高越优。

## 8.3 工业级编码规范

建议：

- 所有时钟超时值有统一宏定义；
- 所有 RCC 修改集中在一个模块；
- 不允许业务代码直接修改 RCC 寄存器；
- 时钟配置结构体包含：
    - 输入源；
    - PLL 参数；
    - SYSCLK；
    - AHB/APB 分频；
    - Flash 等待周期；
    - 电压范围；
    - 目标误差。
- 时钟切换前后执行断言；
- 记录实际时钟树配置；
- 使用 `uint64_t` 进行频率误差计算；
- 禁止浮点参与启动阶段时钟计算；
- MCO 测试功能通过编译选项或运行时诊断开关控制；
- 时钟故障必须区分：
    - HSE 启动失败；
    - PLL 锁定失败；
    - 系统切换失败；
    - 频率超差；
    - 运行中丢失。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：只配置 RCC，忘记配置 GPIO 复用

### 错误代码

```
RCC->CFGR |= RCC_CFGR_MCO1_HSE;
```

### 根因

MCO 内部选择器已经配置，但 GPIO 仍处于：

- 模拟模式；
- 普通输入；
- 普通输出；
- 错误的 AF 复用功能。

### 正确实现

```
/* GPIO 时钟 */
RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;

/* PA8 复用模式 */
GPIOA->MODER &= ~(3UL << (8U * 2U));
GPIOA->MODER |=  (2UL << (8U * 2U));

/* 设置高输出速度 */
GPIOA->OSPEEDR |= (3UL << (8U * 2U));

/* 配置正确 AF */
GPIOA->AFR[1] &= ~(0xFUL << 0U);
GPIOA->AFR[1] |=  (0UL << 0U);
```

### 风险影响

- 示波器无输出；
- 误判 HSE 或 PLL 失效；
- 调试时间延长；
- 可能把 GPIO 配置问题误认为硬件故障。

---

## 9.2 错误二：MCO 分频字段编码理解错误

### 错误代码

```
RCC->CFGR |= (3U << RCC_CFGR_MCO1PRE_Pos);  /* 以为是4分频 */
```

### 根因

许多 RCC 分频字段不是直接写入除数，而是编码值：

```
编码值 000 → 不分频
编码值 100 → 2分频
编码值 101 → 3分频
编码值 110 → 4分频
编码值 111 → 5分频
```

或者某些系列使用完全不同的编码。

### 正确实现

```
typedef enum
{
    MCO_DIV_1 = 0U,
    MCO_DIV_2 = 4U,
    MCO_DIV_3 = 5U,
    MCO_DIV_4 = 6U,
    MCO_DIV_5 = 7U
} mco_div_code_t;

static void mco1_set_div4(void)
{
    RCC->CFGR &= ~RCC_CFGR_MCO1PRE_Msk;
    RCC->CFGR |= ((uint32_t)MCO_DIV_4 << RCC_CFGR_MCO1PRE_Pos);
}
```

### 风险影响

- 测得频率与计算值不一致；
- 误判 PLL 倍频参数；
- 量产测试误判合格品；
- 外部设备接收到错误时钟。

---

## 9.3 错误三：HSE 未就绪就启动 PLL

### 错误代码

```
RCC->CR |= RCC_CR_HSEON;
RCC->PLLCFGR = pll_config;
RCC->CR |= RCC_CR_PLLON;
```

### 根因

没有等待 HSE Ready 标志，PLL 可能使用无效或不稳定的输入。

### 正确实现

```
RCC->CR |= RCC_CR_HSEON;

uint32_t timeout = HSE_START_TIMEOUT;

while (((RCC->CR & RCC_CR_HSERDY) == 0U) &&
       (timeout > 0U))
{
    timeout--;
}

if ((RCC->CR & RCC_CR_HSERDY) == 0U)
{
    /* 回退到 HSI，并记录错误 */
    RCC->CR |= RCC_CR_HSION;
    return CLOCK_ERR_HSE_TIMEOUT;
}

RCC->PLLCFGR = pll_config;
RCC->CR |= RCC_CR_PLLON;

timeout = PLL_LOCK_TIMEOUT;

while (((RCC->CR & RCC_CR_PLLRDY) == 0U) &&
       (timeout > 0U))
{
    timeout--;
}

if ((RCC->CR & RCC_CR_PLLRDY) == 0U)
{
    return CLOCK_ERR_PLL_TIMEOUT;
}
```

### 风险影响

- 系统偶发 HardFault；
- 外设波特率随机错误；
- 温度变化后启动失败；
- 量产中出现低概率启动问题。

---

## 9.4 错误四：提升 SYSCLK 前未配置 Flash 等待周期

### 错误代码

```
RCC->CFGR |= RCC_CFGR_SW_PLL;
/* 之后才设置 Flash Latency */
FLASH->ACR |= FLASH_ACR_LATENCY_5WS;
```

### 根因

CPU 已经开始以高频访问 Flash，但 Flash 访问等待周期仍为低频配置。

### 正确实现

```
/*
 * 在提高系统时钟之前设置足够的 Flash 等待周期。
 * 具体等待周期取决于电源电压和芯片系列。
 */
FLASH->ACR = FLASH_ACR_ICEN |
             FLASH_ACR_DCEN |
             FLASH_ACR_LATENCY_5WS;

/* 再切换 SYSCLK */
RCC->CFGR &= ~RCC_CFGR_SW_Msk;
RCC->CFGR |= RCC_CFGR_SW_PLL;
```

### 风险影响

- 随机取指错误；
- HardFault；
- 仅在高温、低压或特定代码布局下出现；
- 调试器单步运行正常，但全速运行崩溃。

---

## 9.5 错误五：修改系统时钟后没有更新 SysTick 和 RTOS

### 错误代码

```
SystemClock_Config();

/* 直接启动 RTOS */
osKernelStart();
```

### 根因

系统时钟改变后：

- `SystemCoreClock` 可能仍为旧值；
- SysTick 重装值仍按旧频率；
- RTOS Tick 频率发生偏差；
- 软件延时不再准确；
- UART、PWM、ADC 采样频率同步失效。

### 正确实现

```
SystemCoreClockUpdate();

SysTick_Config(SystemCoreClock / OS_TICK_HZ);

/*
 * 如果使用 HAL/RTOS/自定义时间基准，
 * 还需要同步更新：
 * - UART 波特率寄存器
 * - 定时器 ARR/PSC
 * - PWM 周期
 * - ADC 触发频率
 * - USB 时钟
 */
```

### 风险影响

- 1 ms 延时变成 1.1 ms 或 0.9 ms；
- RTOS 调度周期错误；
- 通信超时判断错误；
- 控制算法采样周期偏移。

---

# 10. 多机制组合使用方案

## 10.1 推荐组合架构

```
┌────────────────────┐
                  │ Clock Configuration │
                  │ RCC / PLL / GPIO    │
                  └──────────┬─────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │ Clock Measurement  │
                  │ MCO / TIM Capture  │
                  └──────────┬─────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │ Clock Calibration  │
                  │ Trim / LUT / Filter │
                  └──────────┬─────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │ Clock Diagnostics  │
                  │ Fault / Log / DTC  │
                  └────────────────────┘
```

## 10.2 组合设计目标

该架构同时解决：

- 上电时钟启动；
- 运行时频率测量；
- 内部 RC 校准；
- 温度补偿；
- 频率异常检测；
- 量产测试；
- 现场故障诊断。

## 10.3 完整代码框架
```
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* =========================
 * 1. 基础配置
 * ========================= */

#define CLOCK_TARGET_SYSCLK_HZ       80000000UL
#define CLOCK_REFERENCE_HZ           1000000UL
#define CLOCK_ALLOWED_ERROR_PPM      100U

#define CLOCK_FILTER_DEPTH           8U
#define CLOCK_MEASURE_TIMEOUT_MS     1500U
#define CLOCK_CALIBRATION_PERIOD_MS  1000U

#define CLOCK_TRIM_MIN               0
#define CLOCK_TRIM_MAX               127

/* =========================
 * 2. 时钟状态定义
 * ========================= */

typedef enum
{
    CLOCK_STATE_UNINIT = 0,
    CLOCK_STATE_INIT,
    CLOCK_STATE_RUNNING,
    CLOCK_STATE_DEGRADED,
    CLOCK_STATE_FAULT
} clock_state_t;

typedef enum
{
    CLOCK_FAULT_NONE = 0,
    CLOCK_FAULT_HSE_TIMEOUT,
    CLOCK_FAULT_PLL_TIMEOUT,
    CLOCK_FAULT_SWITCH_TIMEOUT,
    CLOCK_FAULT_FREQ_OUT_OF_RANGE,
    CLOCK_FAULT_REFERENCE_LOST,
    CLOCK_FAULT_TRIM_SATURATED
} clock_fault_t;

typedef struct
{
    uint32_t sysclk_hz;
    uint32_t hclk_hz;
    uint32_t pclk1_hz;
    uint32_t pclk2_hz;
    uint32_t tim_apb1_hz;
    uint32_t tim_apb2_hz;

    bool hse_ready;
    bool pll_ready;
    bool clock_switch_done;
} clock_tree_info_t;

typedef struct
{
    uint32_t reference_hz;
    uint32_t measured_hz;
    int32_t  error_ppm;
    uint32_t sample_count;
    bool     valid;
} clock_measurement_t;

typedef struct
{
    int16_t trim_code;
    int16_t trim_min;
    int16_t trim_max;

    /*
     * 每个 trim step 对应的频率变化量。
     * 实际工程建议通过产测标定得到，而非盲目固定。
     */
    int32_t ppm_per_step;

    bool saturated;
} clock_trim_info_t;

typedef struct
{
    clock_state_t state;
    clock_fault_t fault;

    clock_tree_info_t tree;
    clock_measurement_t measurement;
    clock_trim_info_t trim;

    uint32_t last_update_ms;
    uint32_t consecutive_bad_samples;
    uint32_t consecutive_good_samples;
} clock_manager_t;

static clock_manager_t g_clock_mgr;

/* =========================
 * 3. BSP 抽象接口
 * ========================= */

/*
 * 以下接口必须由具体 MCU 工程实现。
 * 不要在业务层直接访问 RCC、TIM、GPIO 寄存器。
 */

extern bool bsp_clock_hw_init(void);
extern bool bsp_clock_start_hse(uint32_t timeout_ms);
extern bool bsp_clock_start_pll(uint32_t timeout_ms);
extern bool bsp_clock_switch_to_pll(uint32_t timeout_ms);

extern void bsp_clock_get_tree(clock_tree_info_t *tree);

extern bool bsp_mco_enable(uint32_t source, uint32_t divider);
extern void bsp_mco_disable(void);

extern bool bsp_reference_capture_start(void);
extern bool bsp_reference_capture_get(uint32_t *captured_ticks);

extern uint32_t bsp_get_reference_timer_clock_hz(void);
extern uint32_t bsp_get_tick_ms(void);

extern int16_t bsp_hsi_trim_get(void);
extern void bsp_hsi_trim_set(int16_t trim_code);

extern void bsp_clock_fault_record(clock_fault_t fault,
                                   const clock_manager_t *manager);

extern void bsp_clock_reset_to_safe_source(void);

/* =========================
 * 4. 工具函数
 * ========================= */

static uint32_t abs_u32_diff(uint32_t a, uint32_t b)
{
    return (a >= b) ? (a - b) : (b - a);
}

static int32_t calculate_error_ppm(uint32_t measured_hz,
                                   uint32_t nominal_hz)
{
    if (nominal_hz == 0U)
    {
        return 0;
    }

    return (int32_t)(
        ((int64_t)measured_hz - (int64_t)nominal_hz) *
        1000000LL /
        (int64_t)nominal_hz
    );
}

static bool frequency_is_valid(uint32_t measured_hz,
                               uint32_t nominal_hz,
                               uint32_t tolerance_ppm)
{
    uint32_t delta_hz = abs_u32_diff(measured_hz, nominal_hz);

    /*
     * 使用 64 位中间结果防止：
     * delta_hz * 1,000,000 溢出 32 位整数。
     */
    return ((uint64_t)delta_hz * 1000000ULL) <=
           ((uint64_t)nominal_hz * tolerance_ppm);
}

/* =========================
 * 5. 时钟初始化
 * ========================= */

bool clock_manager_init(void)
{
    g_clock_mgr.state = CLOCK_STATE_INIT;
    g_clock_mgr.fault = CLOCK_FAULT_NONE;

    g_clock_mgr.trim.trim_min = CLOCK_TRIM_MIN;
    g_clock_mgr.trim.trim_max = CLOCK_TRIM_MAX;
    g_clock_mgr.trim.ppm_per_step = 80;
    g_clock_mgr.trim.trim_code = bsp_hsi_trim_get();

    if (!bsp_clock_hw_init())
    {
        g_clock_mgr.state = CLOCK_STATE_FAULT;
        g_clock_mgr.fault = CLOCK_FAULT_SWITCH_TIMEOUT;
        bsp_clock_fault_record(g_clock_mgr.fault, &g_clock_mgr);
        return false;
    }

    if (!bsp_clock_start_hse(10U))
    {
        /*
         * HSE 启动失败，切换到安全时钟。
         * 安全模式下通常只能提供降级功能。
         */
        bsp_clock_reset_to_safe_source();

        g_clock_mgr.state = CLOCK_STATE_DEGRADED;
        g_clock_mgr.fault = CLOCK_FAULT_HSE_TIMEOUT;
        bsp_clock_fault_record(g_clock_mgr.fault, &g_clock_mgr);
        return false;
    }

    if (!bsp_clock_start_pll(1U))
    {
        bsp_clock_reset_to_safe_source();

        g_clock_mgr.state = CLOCK_STATE_DEGRADED;
        g_clock_mgr.fault = CLOCK_FAULT_PLL_TIMEOUT;
        bsp_clock_fault_record(g_clock_mgr.fault, &g_clock_mgr);
        return false;
    }

    if (!bsp_clock_switch_to_pll(1U))
    {
        bsp_clock_reset_to_safe_source();

        g_clock_mgr.state = CLOCK_STATE_FAULT;
        g_clock_mgr.fault = CLOCK_FAULT_SWITCH_TIMEOUT;
        bsp_clock_fault_record(g_clock_mgr.fault, &g_clock_mgr);
        return false;
    }

    bsp_clock_get_tree(&g_clock_mgr.tree);

    if (g_clock_mgr.tree.sysclk_hz != CLOCK_TARGET_SYSCLK_HZ)
    {
        g_clock_mgr.state = CLOCK_STATE_FAULT;
        g_clock_mgr.fault = CLOCK_FAULT_FREQ_OUT_OF_RANGE;
        bsp_clock_fault_record(g_clock_mgr.fault, &g_clock_mgr);
        return false;
    }

    g_clock_mgr.state = CLOCK_STATE_RUNNING;

    return true;
}

/* =========================
 * 6. MCO 调试输出控制
 * ========================= */

bool clock_debug_mco_enable(uint32_t source,
                            uint32_t divider)
{
    /*
     * source 和 divider 必须经过芯片相关层转换。
     * 禁止业务层直接把“除数”写入寄存器编码字段。
     */
    return bsp_mco_enable(source, divider);
}

void clock_debug_mco_disable(void)
{
    bsp_mco_disable();
}

/* =========================
 * 7. 外部参考测量
 * ========================= */

bool clock_measure_once(uint32_t *measured_hz)
{
    uint32_t captured_ticks;

    if (measured_hz == NULL)
    {
        return false;
    }

    if (!bsp_reference_capture_get(&captured_ticks))
    {
        return false;
    }

    /*
     * 假定外部参考窗口为 1 秒。
     * 如果参考周期不是 1 秒，应改为：
     *
     * measured_hz = captured_ticks / reference_period_s
     *
     * 实际工程中建议全部使用整数分数计算。
     */
    *measured_hz = captured_ticks;

    return true;
}

bool clock_measure_update(void)
{
    uint32_t measured_hz;

    if (!clock_measure_once(&measured_hz))
    {
        g_clock_mgr.fault = CLOCK_FAULT_REFERENCE_LOST;
        g_clock_mgr.measurement.valid = false;
        return false;
    }

    g_clock_mgr.measurement.reference_hz =
        CLOCK_TARGET_SYSCLK_HZ;

    g_clock_mgr.measurement.measured_hz = measured_hz;

    g_clock_mgr.measurement.error_ppm =
        calculate_error_ppm(measured_hz,
                            CLOCK_TARGET_SYSCLK_HZ);

    g_clock_mgr.measurement.sample_count++;
    g_clock_mgr.measurement.valid = true;

    if (!frequency_is_valid(measured_hz,
                            CLOCK_TARGET_SYSCLK_HZ,
                            CLOCK_ALLOWED_ERROR_PPM))
    {
        g_clock_mgr.consecutive_bad_samples++;
        g_clock_mgr.consecutive_good_samples = 0U;

        if (g_clock_mgr.consecutive_bad_samples >= 3U)
        {
            g_clock_mgr.fault = CLOCK_FAULT_FREQ_OUT_OF_RANGE;
            g_clock_mgr.state = CLOCK_STATE_DEGRADED;
            bsp_clock_fault_record(g_clock_mgr.fault,
                                   &g_clock_mgr);
        }

        return false;
    }

    g_clock_mgr.consecutive_good_samples++;
    g_clock_mgr.consecutive_bad_samples = 0U;

    if (g_clock_mgr.consecutive_good_samples >= 3U &&
        g_clock_mgr.state == CLOCK_STATE_DEGRADED)
    {
        g_clock_mgr.state = CLOCK_STATE_RUNNING;
        g_clock_mgr.fault = CLOCK_FAULT_NONE;
    }

    return true;
}

/* =========================
 * 8. HSI Trim 计算
 * ========================= */

static int16_t clock_calculate_next_trim(
    int16_t current_trim,
    int32_t error_ppm,
    int32_t ppm_per_step,
    int16_t trim_min,
    int16_t trim_max)
{
    int32_t correction;
    int32_t next_trim;

    if (ppm_per_step <= 0)
    {
        return current_trim;
    }

    /*
     * 当前频率偏高，error_ppm > 0：
     * 应降低 trim。
     *
     * 当前频率偏低，error_ppm < 0：
     * 应提高 trim。
     */
    correction = -error_ppm / ppm_per_step;
    next_trim = (int32_t)current_trim + correction;

    if (next_trim < trim_min)
    {
        next_trim = trim_min;
    }

    if (next_trim > trim_max)
    {
        next_trim = trim_max;
    }

    return (int16_t)next_trim;
}

bool clock_hsi_calibrate_once(void)
{
    int16_t current_trim;
    int16_t next_trim;

    if (!g_clock_mgr.measurement.valid)
    {
        return false;
    }

    current_trim = g_clock_mgr.trim.trim_code;

    next_trim = clock_calculate_next_trim(
        current_trim,
        g_clock_mgr.measurement.error_ppm,
        g_clock_mgr.trim.ppm_per_step,
        g_clock_mgr.trim.trim_min,
        g_clock_mgr.trim.trim_max
    );

    if (next_trim == g_clock_mgr.trim.trim_min ||
        next_trim == g_clock_mgr.trim.trim_max)
    {
        if (next_trim != current_trim)
        {
            g_clock_mgr.trim.saturated = true;
            g_clock_mgr.fault = CLOCK_FAULT_TRIM_SATURATED;
        }
    }

    if (next_trim != current_trim)
    {
        bsp_hsi_trim_set(next_trim);
        g_clock_mgr.trim.trim_code = next_trim;
    }

    return true;
}

/* =========================
 * 9. 周期任务
 * ========================= */

void clock_manager_process(void)
{
    uint32_t now_ms;

    now_ms = bsp_get_tick_ms();

    if ((now_ms - g_clock_mgr.last_update_ms) <
        CLOCK_CALIBRATION_PERIOD_MS)
    {
        return;
    }

    g_clock_mgr.last_update_ms = now_ms;

    /*
     * 生产系统中应区分：
     * - 仅监测 HSE/PLL；
     * - 校准 HSI；
     * - 在线校准；
     * - 量产校准。
     */
    if (!clock_measure_update())
    {
        return;
    }

    /*
     * 只有明确使用 HSI 作为被校准对象时，
     * 才能执行 HSI trim。
     */
    if (g_clock_mgr.tree.sysclk_hz != 0U)
    {
        (void)clock_hsi_calibrate_once();
    }
}
```

## 10.4 校准算法改进

上面的“一次误差直接修正”适合演示，不适合所有工业场景。实际使用时需要解决三个问题：

### 问题一：测量噪声导致 Trim 来回跳变

例如测量结果：

```
第1次：+42 ppm
第2次：-31 ppm
第3次：+28 ppm
第4次：-36 ppm
```

如果每次都更新校准码，可能出现：

```
trim +1 → trim -1 → trim +1 → trim -1
```

建议采用滑动平均：

eˉn=1N∑i=0N−1en−ieˉn​=N1​i=0∑N−1​en−i​

```
typedef struct
{
    int32_t samples[CLOCK_FILTER_DEPTH];
    uint32_t index;
    uint32_t count;
} ppm_filter_t;

static ppm_filter_t g_ppm_filter;

static int32_t ppm_filter_update(ppm_filter_t *filter,
                                  int32_t new_value)
{
    int64_t sum = 0;

    if (filter == NULL)
    {
        return new_value;
    }

    filter->samples[filter->index] = new_value;
    filter->index++;

    if (filter->index >= CLOCK_FILTER_DEPTH)
    {
        filter->index = 0U;
    }

    if (filter->count < CLOCK_FILTER_DEPTH)
    {
        filter->count++;
    }

    for (uint32_t i = 0U; i < filter->count; i++)
    {
        sum += filter->samples[i];
    }

    return (int32_t)(sum / (int64_t)filter->count);
}
```

### 问题二：接近目标值时不应继续调整

增加死区：

```
#define CLOCK_CALIBRATION_DEADBAND_PPM  20
```

```
static bool calibration_needed(int32_t error_ppm)
{
    return (error_ppm > CLOCK_CALIBRATION_DEADBAND_PPM) ||
           (error_ppm < -CLOCK_CALIBRATION_DEADBAND_PPM);
}
```

### 问题三：单步修正过大造成过冲

推荐限制单次最大调整量：

```
#define CLOCK_MAX_TRIM_STEP  2
```

```
static int16_t limit_trim_step(int16_t current,
                               int16_t target)
{
    int32_t delta = (int32_t)target - current;

    if (delta > CLOCK_MAX_TRIM_STEP)
    {
        delta = CLOCK_MAX_TRIM_STEP;
    }
    else if (delta < -CLOCK_MAX_TRIM_STEP)
    {
        delta = -CLOCK_MAX_TRIM_STEP;
    }

    return (int16_t)((int32_t)current + delta);
}
```

推荐的工业算法：

```
采集 8～32 个样本
        │
        ▼
去除最大值和最小值
        │
        ▼
滑动平均或中值滤波
        │
        ▼
判断是否进入死区
        │
        ▼
限制最大 trim 步长
        │
        ▼
等待时钟稳定
        │
        ▼
重新测量并确认
```

---

# 11. 工业级实际案例分析

## 11.1 案例一：量产测试 HSE 晶振焊接和 PLL 配置

### 需求

某工业控制器采用：

- 8 MHz 外部晶体；
- PLL 生成 120 MHz 系统时钟；
- 要求生产测试快速判断：
    - 晶体是否焊接；
    - 晶体频率是否正确；
    - PLL 配置是否正确；
    - MCO 输出是否满足目标窗口。

### 架构

```
HSE 8 MHz
   │
   ├──▶ MCO1 / 1分频 ──▶ 频率计通道1
   │
   └──▶ PLL ──▶ SYSCLK 120 MHz
                    │
                    └──▶ MCO2 / 8分频 = 15 MHz
                                      │
                                      └──▶ 频率计通道2
```

### 测试项目

|测试项|目标|判定窗口|
|---|---|---|
|HSE MCO|8 MHz|±100 ppm|
|SYSCLK MCO|15 MHz|±100 ppm|
|启动时间|<10 ms|超时失败|
|波形幅度|0～3.3 V|逻辑高低电平合格|
|占空比|50%附近|40%～60%|

### 核心代码

```
bool production_clock_test(void)
{
    uint32_t hse_freq;
    uint32_t sysclk_div_freq;

    /*
     * 先输出 HSE，验证晶体和 HSE 输入链路。
     */
    if (!bsp_mco_enable(BSP_MCO_SOURCE_HSE,
                        BSP_MCO_DIV_1))
    {
        return false;
    }

    if (!bsp_frequency_counter_measure(
            BSP_FREQ_CHANNEL_HSE,
            10U,
            &hse_freq))
    {
        return false;
    }

    if (!frequency_is_valid(hse_freq, 8000000UL, 100U))
    {
        bsp_mco_disable();
        return false;
    }

    /*
     * 再输出 SYSCLK / 8，避免高频直接进入测试设备。
     */
    if (!bsp_mco_enable(BSP_MCO_SOURCE_SYSCLK,
                        BSP_MCO_DIV_8))
    {
        return false;
    }

    if (!bsp_frequency_counter_measure(
            BSP_FREQ_CHANNEL_SYSCLK,
            10U,
            &sysclk_div_freq))
    {
        return false;
    }

    if (!frequency_is_valid(sysclk_div_freq,
                            15000000UL,
                            100U))
    {
        bsp_mco_disable();
        return false;
    }

    bsp_mco_disable();

    return true;
}
```

### 设计要点

- HSE 和 SYSCLK 分开验证，便于定位；
- 先测 HSE，再测 PLL；
- 采用分频输出降低 GPIO 和仪器压力；
- 测试失败时记录失败阶段；
- 不建议直接探测晶体两端作为量产测试手段；
- 量产治具必须固定探头负载和信号地参考。

---

## 11.2 案例二：使用 GNSS PPS 在线校准内部 HSI

### 需求

一款低成本数据采集设备没有外部高精度晶振，使用 HSI 作为主时钟，但要求：

- 设备短期时间误差小于 ±100 ppm；
- 设备长期运行过程中进行在线校准；
- GNSS 有效时使用 PPS；
- GNSS 丢失时保持最近一次校准结果；
- 不允许校准过程影响采样任务。

### 架构

```
GNSS PPS
   │
   ▼
TIM 输入捕获
   │
   ▼
DMA 保存捕获值
   │
   ▼
后台任务计算频率误差
   │
   ▼
滤波 + 死区 + 限幅
   │
   ▼
HSITRIM 更新
```

### 工程要求

- PPS ISR 中只做：
    - 读取捕获状态；
    - 清除标志；
    - 通知后台任务。
- 不能在 PPS ISR 中执行：
    - 浮点计算；
    - Flash 写入；
    - 长时间滤波；
    - 多次寄存器配置。
- Trim 更新后应等待至少一个测量周期再确认。
- 校准参数写 Flash 不能高频执行，建议：
    - 仅在生产时写入；
    - 或达到稳定阈值后写一次；
    - 或按小时/天级别写入。

### 校准误差预算

假设：

|误差来源|误差|
|---|---|
|PPS 参考|±20 ns|
|定时器量化|±1 tick|
|测量窗口|1 s|
|HSI 短期抖动|±15 ppm|
|温度变化|±50 ppm|

整体目标必须满足：

Etotal≤Ereference+Equantization+Eclock+EtemperatureEtotal​≤Ereference​+Equantization​+Eclock​+Etemperature​

如果设备温度快速变化，仅靠固定 trim 不能满足要求，应引入温度补偿：

trim(T)=a0+a1T+a2T2trim(T)=a0​+a1​T+a2​T2

---

## 11.3 案例三：MCO 输出干扰模拟采样系统

### 现象

设备开启 MCO 调试输出后：

- ADC 噪声上升；
- 模拟传感器频谱出现固定尖峰；
- CAN 通信偶发错误；
- 关闭 MCO 后问题消失。

### 根因

MCO 高频翻转产生：

- GPIO 地弹噪声；
- 电源纹波；
- 走线串扰；
- 谐波辐射；
- 外部测试线缆天线效应。

### 解决方案

```
开发模式：
    MCO 可配置输出
    允许外部测量

量产模式：
    默认关闭 MCO
    仅在诊断命令下临时开启
    限定开启时长
    限制输出频率和引脚
```

### 受控开启代码

```
#define MCO_DEBUG_MAX_DURATION_MS  5000U

typedef struct
{
    bool enabled;
    uint32_t start_ms;
} mco_debug_context_t;

static mco_debug_context_t g_mco_debug;

bool mco_debug_start(uint32_t source,
                     uint32_t divider)
{
    if (g_mco_debug.enabled)
    {
        return false;
    }

    if (!bsp_mco_enable(source, divider))
    {
        return false;
    }

    g_mco_debug.enabled = true;
    g_mco_debug.start_ms = bsp_get_tick_ms();

    return true;
}

void mco_debug_process(void)
{
    if (!g_mco_debug.enabled)
    {
        return;
    }

    if ((bsp_get_tick_ms() - g_mco_debug.start_ms) >=
        MCO_DEBUG_MAX_DURATION_MS)
    {
        bsp_mco_disable();
        g_mco_debug.enabled = false;
    }
}
```

### 设计要点

- MCO 不是无害的调试信号；
- 高速 MCO 不应靠近：
    - ADC 输入；
    - 运放反馈；
    - 晶振；
    - CAN、RS-485 差分线；
    - 射频区域；
- 必要时增加：
    - 串联阻尼电阻；
    - 低速 GPIO 配置；
    - 专用测试焊盘；
    - 可选 0 Ω 电阻；
    - 屏蔽和合理回流路径。

---

# 12. 高频问题深度答疑

## 12.1 为什么 MCO 测得频率正确，但 UART 仍然通信失败？

可能原因不在 SYSCLK：

1. UART 使用独立内核时钟；
2. APB 时钟计算错误；
3. UART 分频公式使用了错误的过采样参数；
4. 时钟切换后没有重新配置 UART；
5. 实际波特率误差来自另一端设备；
6. GPIO 复用或电气参数错误；
7. MCO 测量的是 SYSCLK，但 UART 使用 PCLK 或独立 PLL。

应建立完整链路：

```
时钟源
  ↓
PLL
  ↓
SYSCLK
  ↓
AHB/APB
  ↓
UART内核时钟
  ↓
BRR寄存器
  ↓
实际波特率
```

不能只验证某一个节点。

## 12.2 为什么 HSE 已经显示 Ready，但 MCO 没有稳定波形？

`HSERDY` 通常只代表：

- 输入振荡器检测到满足条件的振荡；
- 并不代表波形质量满足系统级要求；
- 也不代表外部负载下仍然稳定。

需要继续检查：

- 晶体负载电容；
- 晶体 ESR；
- PCB 走线；
- 电源噪声；
- 芯片振荡器驱动等级；
- MCO 输出负载；
- 测量探头是否造成影响。

## 12.3 为什么 MCO 波形占空比不是 50%？

MCO 输出经过：

- 时钟选择器；
- 分频器；
- 时钟门控；
- GPIO 输出缓冲；
- 外部负载。

占空比可能受到：

- 奇数分频；
- 时钟源本身占空比；
- 输出路径延迟；
- GPIO 上下拉能力；
- 负载电容；
- 测量阈值。

如果只关注频率，不必强求精确 50%。但如果 MCO 作为外部时钟源，则必须按芯片数据手册检查：

- 最小高电平时间；
- 最小低电平时间；
- 占空比范围；
- 最大负载；
- 最大输出频率。

## 12.4 为什么改变 MCO 分频后，系统运行会异常？

正常情况下，MCO 分频只影响输出支路，不应影响 SYSCLK。但异常可能来自：

- RCC 寄存器读改写覆盖了其他字段；
- 使用了错误的寄存器掩码；
- MCO 配置写入时清除了 SW、HPRE、PPRE 等字段；
- RCC 配置被并发代码修改；
- MCO 输出引脚和其他关键外设复用冲突；
- MCO 引脚电气负载导致电源噪声。

推荐使用完整掩码：

```
uint32_t reg = RCC->CFGR;

reg &= ~(RCC_CFGR_MCO1_Msk |
         RCC_CFGR_MCO1PRE_Msk);

reg |= mco_source_code;
reg |= mco_prescaler_code;

RCC->CFGR = reg;
```

禁止使用无掩码的随意或操作：

```
RCC->CFGR |= 0x12345678U;  /* 高风险 */
```

## 12.5 HSI 校准后为什么重启又恢复原来的频率？

常见原因：

- trim 寄存器是易失性的；
- 只修改了运行时寄存器，没有写入 Flash；
- 上电启动代码覆盖了校准值；
- 校准参数 CRC 校验失败后使用默认值；
- 不同工作电压、温度下需要不同 trim；
- 保存的是错误的芯片或板卡配置。

建议使用：

```
Flash参数区
├── magic
├── version
├── trim_code
├── calibration_temperature
├── calibration_voltage
├── error_ppm
├── sequence
└── CRC32
```

启动时：

```
读取参数
  ↓
检查 magic/version
  ↓
检查范围
  ↓
校验 CRC
  ↓
应用 trim
  ↓
验证频率
  ↓
失败则使用默认值
```

## 12.6 在线校准会不会破坏实时性？

会，尤其是在错误设计下。

风险来源：

- 在中断中修改时钟；
- 校准时切换 PLL；
- 使用阻塞式等待；
- 频繁写 Flash；
- 频率变化影响定时器周期；
- 校准瞬间导致 UART、PWM、ADC 时序异常。

推荐策略：

```
高实时任务使用稳定外部时钟
        │
        ├── 校准模块运行在低优先级任务
        │
        ├── 只调整独立 HSI Trim
        │
        ├── 不在线切换 SYSCLK
        │
        └── 通过版本化参数缓慢更新
```

如果必须在线切换主频，应：

- 暂停相关外设；
- 屏蔽或协调关键中断；
- 重新配置 SysTick；
- 重新计算 UART/TIM/ADC 参数；
- 进行切换后完整性验证。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **MCO 是观察 MCU 内部时钟树的外部窗口**。
2. MCO 调试必须同时配置：
    - RCC 时钟源；
    - MCO 选择和分频；
    - GPIO 复用；
    - GPIO 速度；
    - 测量设备。
3. 时钟初始化顺序必须遵循：

```
电源范围
→ Flash等待周期
→ 时钟源启动
→ PLL锁定
→ 总线分频
→ SYSCLK切换
→ 软件时间基准更新
```

4. `HSERDY`、`PLLRDY` 只能说明硬件状态满足基本条件，不能完全证明时钟质量。
5. 频率误差计算：

errorppm=fmeas−fnomfnom×106errorppm​=fnom​fmeas​−fnom​​×106

6. 频率测量窗口越长，量化误差越低：

δrelative=1fTδrelative​=fT1​

7. HSI 校准应使用：

```
测量
→ 滤波
→ 死区
→ 限幅
→ Trim更新
→ 等待稳定
→ 再次测量
```

8. **MCO 输出会增加功耗和 EMI，量产产品不应默认长期打开**。
9. 任何时钟切换都必须同步检查：
    - SysTick；
    - RTOS Tick；
    - UART；
    - 定时器；
    - PWM；
    - ADC 触发；
    - USB；
    - 通信协议时序。

## 13.2 性能排序

### 时钟精度

```
PPS/高精度同步源
    >
TCXO
    >
高品质 HSE 晶振
    >
普通 HSE 晶振
    >
HSI
    >
LSI
```

### 启动速度

```
HSI / LSI
    >
外部有源时钟
    >
PLL锁定
    >
HSE晶振
    >
LSE晶振
```

### 低功耗适应性

```
LSI/LSE
    >
HSI
    >
HSE
    >
TCXO/外部同步系统
```

## 13.3 通用选型结论

|需求|推荐|
|---|---|
|成本优先|HSI|
|通用工业通信|HSE|
|高精度通信|TCXO 或高品质 HSE|
|长期时间同步|PPS/GNSS/PTP|
|低功耗 RTC|LSE|
|看门狗独立时基|LSI，但必须评估误差|
|调试系统时钟|MCO 输出 SYSCLK|
|调试外部晶振|MCO 输出 HSE|
|校准内部 RC|TIM 捕获外部参考|
|量产测试|MCO + 自动频率计|

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|MCO源|分频建议|测量方式|
|---|---|---|---|
|验证 HSI|HSI|1/2|频率计|
|验证 HSE|HSE|1|示波器或频率计|
|验证 PLL|PLL/SYSCLK|2/4/8|频率计|
|验证 APB 影响|不建议只看 MCO|-|配合 TIM 捕获|
|校准 HSI|HSI 或定时器时钟|适中|PPS + 输入捕获|
|量产测试|HSE、SYSCLK|4/8|自动频率计|
|检查 EMI|SYSCLK|2/4|频谱仪/示波器|
|检查启动|HSE/PLL|适中|示波器单次触发|

## 14.2 MCO 调试检查表

```
[ ] 芯片型号和 RCC 寄存器版本确认
[ ] MCO 引脚确认
[ ] GPIO 时钟已打开
[ ] GPIO 模式为复用
[ ] GPIO AF 编号正确
[ ] GPIO 速度等级正确
[ ] MCO 时钟源已启动
[ ] HSE/PLL Ready 标志有效
[ ] MCO 分频编码正确
[ ] 示波器探头接地正确
[ ] 测量设备带宽足够
[ ] 输出负载未超限
[ ] MCO 没有与其他功能冲突
[ ] 关闭 MCO 后系统仍正常
```

## 14.3 时钟故障定位表

|现象|优先检查|
|---|---|
|MCO 无波形|GPIO 复用、引脚、MCO 源、时钟门控|
|MCO 频率为 0|源未启动、选择编码错误、引脚错误|
|MCO 频率为预期一半|MCO 分频、测量阈值、源频率|
|MCO 频率是预期整数倍|PLL、HSE 输入、分频配置|
|波形边沿慢|GPIO 速度、负载、探头、走线|
|启动偶发失败|HSE 裕量、超时、电源、Flash 等待周期|
|RTOS Tick 错误|`SystemCoreClock`、SysTick 重装值|
|TIM 周期错误|APB 定时器倍频规则|
|UART 波特率错误|UART 内核时钟、PCLK、BRR|
|温度变化后超差|HSI/HSE 温漂、补偿模型|
|开 MCO 后 ADC 变差|EMI、电源噪声、地回路、走线串扰|

---

# 15. 学习效果自检

完成本课后，应能回答并实际完成以下任务。

## 15.1 原理检查

- [ ]  能画出目标 MCU 的完整时钟树；
- [ ]  能说明 HSI、HSE、PLL、SYSCLK、HCLK、PCLK 的关系；
- [ ]  能解释 MCO 在时钟树中的位置；
- [ ]  能写出 PLL 输出频率计算公式；
- [ ]  能说明 HSE 晶振模式与旁路模式的区别；
- [ ]  能解释 `HSERDY` 和 `PLLRDY` 的含义及局限。

## 15.2 配置检查

- [ ]  能正确配置 MCO GPIO 复用；
- [ ]  能确认 MCO 分频编码；
- [ ]  能实现带超时的 HSE 启动；
- [ ]  能实现带超时的 PLL 启动；
- [ ]  能在提升主频前配置 Flash 等待周期；
- [ ]  能在切换主频后更新 SysTick、RTOS 和外设时钟。

## 15.3 测量检查

- [ ]  能用示波器测量 MCO 频率；
- [ ]  能使用频率计计算 ppm 误差；
- [ ]  能使用定时器输入捕获测量外部 PPS；
- [ ]  能处理 32 位定时器计数器溢出；
- [ ]  能区分频率误差和波形质量问题；
- [ ]  能估算测量窗口引入的量化误差。

## 15.4 架构检查

- [ ]  RCC 配置和业务代码已解耦；
- [ ]  时钟故障能够记录；
- [ ]  HSE/PLL 启动失败具有回退机制；
- [ ]  MCO 支持受控开启和自动关闭；
- [ ]  校准过程不阻塞高优先级任务；
- [ ]  校准参数具有 CRC 和版本管理；
- [ ]  校准算法包含滤波、死区和步长限制。

## 15.5 实战考核

建议至少完成以下实验：

1. MCO 输出 HSI，测量实际频率；
2. MCO 输出 HSE，验证晶体频率；
3. MCO 输出 SYSCLK，验证 PLL 配置；
4. 修改 APB 分频，验证定时器时钟倍频；
5. 使用 PPS 测量 MCU 计数频率；
6. 修改 HSI Trim，观察频率变化；
7. 对不同温度下的 HSI 建立校准表；
8. 开启和关闭 MCO，比较 ADC 噪声和电源纹波。

---

# 16. 实践与进阶路径

## 16.1 第一阶段：MCO 基础验证

### 任务

- 输出 HSI；
- 输出 HSE；
- 输出 SYSCLK；
- 输出不同分频频率；
- 使用示波器检查：
    - 频率；
    - 占空比；
    - 上升下降时间；
    - 波形振铃。

### 交付物

- 时钟树图；
- 寄存器配置表；
- 实测波形截图；
- 频率误差表；
- MCO 故障排查记录。

## 16.2 第二阶段：时钟启动故障注入

人为制造以下故障：

- 断开晶体；
- 修改错误的 HSE 频率；
- 配置非法 PLL 参数；
- 缩短启动超时；
- 设置错误 Flash 等待周期；
- 配置错误 GPIO AF；
- 修改错误 MCO 分频编码。

验证系统是否能够：

- 正确检测失败；
- 回退到安全时钟；
- 记录故障原因；
- 避免进入不可恢复死循环。

## 16.3 第三阶段：PPS 频率测量

### 实验步骤

1. 使用 GNSS 或函数发生器产生 1 PPS；
2. 连接到 TIM 输入捕获引脚；
3. 使用定时器自由运行计数；
4. 每秒读取一次捕获差值；
5. 计算实际 MCU 时钟；
6. 输出 ppm 误差；
7. 改变供电和温度，观察漂移。

### 需要记录

```
时间戳
温度
供电电压
捕获计数
计算频率
误差 ppm
Trim code
```

## 16.4 第四阶段：HSI 闭环校准

实现如下闭环：

```
外部参考
   ↓
定时器捕获
   ↓
误差计算
   ↓
滑动平均
   ↓
死区判断
   ↓
Trim调整
   ↓
等待稳定
   ↓
误差确认
```

要求：

- 不允许单次样本直接写 Trim；
- 单次 Trim 调整不得超过 1～2 step；
- 连续 3 次超差才进入故障状态；
- 连续 3 次合格才恢复正常；
- 校准失败不能影响主业务运行。

## 16.5 第五阶段：温度补偿模型

在温箱中采集：

```
-40 ℃、-20 ℃、0 ℃、25 ℃、50 ℃、85 ℃
```

每个温度点记录：

- HSI 频率；
- 默认 Trim；
- 最佳 Trim；
- 供电电压；
- 测量时间；
- 芯片批次。

建立模型：

### 分段线性模型

trim(T)={a1T+b1,T<T1a2T+b2,T1≤T<T2a3T+b3,T≥T2trim(T)=⎩⎨⎧​a1​T+b1​,a2​T+b2​,a3​T+b3​,​T<T1​T1​≤T<T2​T≥T2​​

### 二次模型

trim(T)=aT2+bT+ctrim(T)=aT2+bT+c

嵌入式实现建议优先使用：

- 查表；
- 定点线性插值；
- 限幅；
- CRC 校验；

不建议在高频实时路径中使用浮点多项式计算。

## 16.6 第六阶段：工业级量产自动化

最终应形成：

```
治具连接
   ↓
烧录测试固件
   ↓
配置 MCO
   ↓
频率计自动采样
   ↓
计算误差 ppm
   ↓
写入校准参数
   ↓
复位验证
   ↓
生成序列号测试报告
```

量产测试报告建议至少包含：

- MCU 型号；
- 芯片唯一 ID；
- 板卡序列号；
- HSE 实测频率；
- SYSCLK 实测频率；
- 温度；
- 供电电压；
- 校准前误差；
- 校准后误差；
- Trim 值；
- 测试时间；
- 测试固件版本；
- 判定结果；
- CRC 或签名。

## 16.7 进阶学习方向

后续可以继续深入：

1. **时钟安全系统 CSS**
    
    - HSE 失效检测；
    - 自动切换 HSI；
    - NMI 处理；
    - 故障恢复策略。
2. **低功耗时钟架构**
    
    - Stop/Standby 模式；
    - 唤醒时钟恢复；
    - LSE/LSI 选择；
    - RTC 校准。
3. **高精度同步**
    
    - GNSS PPS；
    - IEEE 1588 PTP；
    - SyncE；
    - 外部同步输入；
    - 时间戳硬件捕获。
4. **时钟抖动和相位噪声**
    
    - PLL 环路带宽；
    - 周期抖动；
    - 随机抖动；
    - 确定性抖动；
    - 通信眼图影响。
5. **EMC/EMI 优化**
    
    - Spread Spectrum；
    - GPIO slew rate；
    - 时钟走线；
    - 回流路径；
    - MCO 输出阻尼。
6. **多时钟域设计**
    
    - CDC；
    - 异步 FIFO；
    - 握手同步；
    - 脉冲同步；
    - 时钟域复位释放。
7. **RTOS 时间基准架构**
    
    - SysTick 与硬件定时器解耦；
    - Tickless；
    - 高精度单调时钟；
    - 时间漂移补偿；
    - 软件定时器长期误差控制。

## 本课最终结论

**MCO 是时钟系统的可观测性接口，时钟校准是测量、建模和反馈控制问题。**

工业级实现不能停留在：

```
配置寄存器 → 示波器看到波形
```

而应完整覆盖：

```
时钟源选择
→ 时钟树配置
→ 安全启动
→ MCO观测
→ 外部参考测量
→ 误差计算
→ 滤波与校准
→ 温度补偿
→ 故障诊断
→ 量产验证
→ 长期维护
```

其中最重要的工程原则是：

> **先保证时钟系统可启动，再保证频率正确，最后保证频率在温度、供电、老化和异常条件下仍然可诊断、可恢复、可验证。**