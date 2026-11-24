
> 本课以 **STM32F1/F4 系列 FSMC/FMC 的异步存储器控制器**为主线，重点覆盖 NOR/SRAM、异步 NAND、PC Card、8080/6800 LCD 接口。不同 STM32 子系列对寄存器名称、Bank 数量、FMC 扩展功能存在差异，实际开发必须以目标芯片参考手册为准。

## 1. 学习目标

### 理解

- 理解 FSMC 在 MCU 总线系统中的位置、地址映射方式和异步时序模型。
- 理解 `NE`、`NOE`、`NWE`、`NWAIT`、地址线、数据线之间的协作关系。
- 理解 NOR/SRAM、NAND、LCD 8080 接口在硬件时序和软件访问模型上的差异。
- 理解 FSMC 地址线复用和 LCD 寄存器/数据窗口映射机制。

### 掌握

- 掌握 FSMC 异步 SRAM/NOR Bank 的时序配置。
- 掌握 8080 LCD 的命令寄存器和数据寄存器地址设计。
- 掌握数据宽度、地址偏移、字节访问、大小端和总线对齐问题。
- 掌握 FSMC 初始化、GPIO 复用、MPU/Cache 配置和基本故障定位方法。

### 精通

- 能够根据外部器件数据手册反推 `ADDSET`、`DATAST`、`BUSTURN` 等参数。
- 能够分析读写波形，定位建立时间、保持时间、地址线错位、数据采样错误等问题。
- 能够设计 LCD、SRAM、NOR Flash、NAND Flash 共用 FSMC/FMC 的总线架构。
- 能够量化吞吐率、CPU 占用、等待周期和 DMA 传输收益。

### 能够设计

- 能够设计满足工业温度、EMI、启动时序和异常恢复要求的 FSMC 外部存储系统。
- 能够为显示、数据缓存、启动介质和大容量存储分别完成方案选型。
- 能够建立可测试、可移植、可验证的 FSMC BSP 和驱动抽象层。

---

## 2. 前置要求

### 知识要求

- ARM Cortex-M 异常模型、AHB/APB 总线和内存映射模型。
- GPIO 复用、推挽输出、输入采样和外部硬件时序。
- SRAM、NOR Flash、NAND Flash 基本工作原理。
- C 语言指针、`volatile`、结构体映射和编译器优化规则。
- 基本信号完整性知识：上升沿、串扰、反射、负载、电平兼容。

### 技能要求

- 能够阅读 MCU 参考手册和外部器件数据手册。
- 能够使用示波器或逻辑分析仪观察总线信号。
- 能够进行寄存器级初始化和启动阶段调试。
- 能够使用 Map 文件、DWT Cycle Counter 或定时器完成性能测量。

---

## 3. 技术概述

### 3.1 FSMC 的定义

FSMC，即 Flexible Static Memory Controller，是 STM32 中用于连接异步外部存储器和并行外设的控制器。

它将外部设备映射到 Cortex-M 的统一地址空间中，使软件可以通过普通指针访问外部硬件：

```
*(volatile uint16_t *)0x68000000U = value;
```

CPU 发起一次内存访问后，FSMC 自动完成：

1. 地址译码；
2. 片选信号生成；
3. 地址线和数据线驱动；
4. 读写控制信号时序生成；
5. 数据采样或输出；
6. 总线释放和等待状态处理。

### 3.2 典型支持设备

|设备类型|典型用途|软件访问模型|是否适合直接执行代码|
|---|---|---|---|
|异步 SRAM|外部缓存、帧缓存|线性读写|部分 MCU 支持|
|NOR Flash|启动介质、代码存储|命令序列 + 地址访问|支持 XIP 的型号可用|
|异步 NAND|大容量数据存储|命令、地址、数据阶段|通常不直接 XIP|
|8080 LCD|显示控制器|命令寄存器 + 数据寄存器|不适用|
|6800 LCD|显示控制器|类似 8080，时序信号不同|不适用|
|PC Card|特定存储卡|分区地址空间|取决于型号|

### 3.3 FSMC 与 FMC

- **FSMC**：常见于 STM32F1、部分 STM32F2/F4。
- **FMC**：后续型号中更名或扩展，通常增加 SDRAM、SDRAM 管理能力。
- 异步 NOR/SRAM/LCD 的核心思想相同，但寄存器字段和时钟配置可能不同。

---

## 4. 核心特性横向对比

### 4.1 外部设备方案对比

|维度|SRAM|NOR Flash|NAND Flash|LCD 8080|
|---|---|---|---|---|
|随机读延迟|低|中|高，需页操作|由 LCD 控制器决定|
|随机写能力|高|低，需擦除/编程|低，需页编程||
|是否需要命令协议|否|是|是|是|
|地址线数量|较多|较多|少，通常复用|少，常复用|
|典型总线宽度|8/16 bit|8/16 bit|8/16 bit|8/16 bit|
|适合帧缓存|**非常适合**|不适合|不适合|设备内部通常有显存|
|是否支持 DMA|视 MCU/外设而定|视 MCU/外设而定|可配合 DMA|通常适合 DMA 刷屏|
|代码执行|某些 MCU 可执行|可 XIP|不适合|不适合|
|软件复杂度|低|中|高|中|
|成本与容量|中、小容量|中容量|**大容量、低成本**|取决于面板|

### 4.2 FSMC 与其他接口对比

|维度|FSMC/FMC|SPI|Quad-SPI/OSPI|SDIO/SDMMC|SDRAM 控制器|
|---|---|---|---|---|---|
|并行位宽|8/16/32 bit，取决于型号|1 bit|4/8 bit|专用|16/32 bit|
|单次访问延迟|低|高|中|高|低|
|引脚数量|多|少|中|中|多|
|随机访问性能|高|低|中|低|高|
|典型用途|SRAM、LCD、NOR|低速外设|外部 Flash|文件系统|大型帧缓存|
|PCB 布线难度|高|低|中|中|高|
|软件访问透明性|高|低|高或中|块设备|高|
|实时确定性|高|中|中|低|中|

---

## 5. 底层原理与功能特性深度解析

## 5.1 总线访问到 FSMC 波形

以异步 SRAM 写周期为例：

```
地址线:  ----<------ 有效地址 ------>----
NE    :  ______\__________________/______
NWE   :  __________\__________/__________
数据线:  --------<--- 有效数据 --->------
```

典型流程：

1. CPU 发起对 FSMC 映射区的写访问。
2. FSMC 输出目标地址。
3. `NE` 拉低，选中 Bank。
4. 等待地址建立时间。
5. 输出数据。
6. `NWE` 拉低，产生写脉冲。
7. `NWE` 拉高并保持数据。
8. `NE` 释放，总线周期完成。

一次异步访问的总时间可以近似表示为：

```
Tcycle =
    Taddress
  + Tdata
  + Tbus_turnaround
  + Tadditional
```

对于同步系统，寄存器值通常以 FSMC 时钟周期为单位：

```
Tperiod = 1 / HCLK
Taddress = (ADDSET + 1) × Tperiod
Tdata    = (DATAST + 1) × Tperiod
```

注意：不同芯片参考手册可能对寄存器值到实际周期的换算定义不同，必须以对应 RM 的时序图为准。

---

## 5.2 地址映射与 Bank 选择

以常见 STM32F1 FSMC NOR/SRAM 区域为例：

|Bank|典型地址范围|
|---|---|
|Bank1 NOR/SRAM 1|`0x60000000` 起始|
|Bank1 NOR/SRAM 2|`0x64000000` 起始|
|Bank1 NOR/SRAM 3|`0x68000000` 起始|
|Bank1 NOR/SRAM 4|`0x6C000000` 起始|
|NAND Bank2|`0x70000000` 起始|
|NAND Bank3|`0x80000000` 起始|

实际地址取决于芯片型号和 Bank 配置。

### 地址线复用的关键问题

对于 16 位数据总线：

```
CPU 地址 A0 不一定直接连接到外部地址线 A0。
```

由于每次访问一个 `uint16_t`，外部器件的最低地址位通常对应 CPU 的 `A1`。因此 LCD 命令/数据地址经常使用：

```
#define LCD_BASE       0x68000000UL
#define LCD_REG_OFFSET 0x00000000UL
#define LCD_RAM_OFFSET 0x00000002UL
```

或者使用更高地址位：

```
#define LCD_REG_ADDR   ((volatile uint16_t *)0x60000000UL)
#define LCD_DATA_ADDR  ((volatile uint16_t *)0x60000002UL)
```

具体偏移由：

- 数据总线宽度；
- `A0` 到外部器件地址线的连接方式；
- `RS/DC` 连接到哪根 FSMC 地址线；
- 原理图和芯片手册的地址映射规则

共同决定，不能直接套用其他开发板代码。

### 生产级地址定义

```
#include <stdint.h>

#define LCD_FSMC_BASE       (0x60000000UL)
#define LCD_RS_A0_OFFSET    (0x00000002UL)

#define LCD_REG_ADDR        ((volatile uint16_t *)(LCD_FSMC_BASE))
#define LCD_DATA_ADDR       ((volatile uint16_t *)(LCD_FSMC_BASE + LCD_RS_A0_OFFSET))

static inline void lcd_write_cmd(uint16_t cmd)
{
    *LCD_REG_ADDR = cmd;
}

static inline void lcd_write_data(uint16_t data)
{
    *LCD_DATA_ADDR = data;
}

static inline uint16_t lcd_read_data(void)
{
    return *LCD_DATA_ADDR;
}
```

`volatile` 是必须的，否则编译器可能合并、删除或重排对硬件寄存器窗口的访问。

---

## 5.3 异步 SRAM/NOR 配置

典型 HAL 风格初始化如下。具体 GPIO 和 RCC 名称根据芯片系列调整。

```
#include "stm32f4xx_hal.h"

static SRAM_HandleTypeDef hsram1;

HAL_StatusTypeDef fsmc_sram_init(void)
{
    FSMC_NORSRAM_TimingTypeDef timing = {
        .AddressSetupTime       = 2U,
        .AddressHoldTime        = 1U,
        .DataSetupTime          = 5U,
        .BusTurnAroundDuration  = 1U,
        .CLKDivision            = 2U,
        .DataLatency            = 2U,
        .AccessMode             = FSMC_ACCESS_MODE_A
    };

    hsram1.Instance  = FSMC_NORSRAM_DEVICE;
    hsram1.Extended  = FSMC_NORSRAM_EXTENDED_DEVICE;

    hsram1.Init.NSBank             = FSMC_NORSRAM_BANK1;
    hsram1.Init.DataAddressMux     = FSMC_DATA_ADDRESS_MUX_DISABLE;
    hsram1.Init.MemoryType         = FSMC_MEMORY_TYPE_SRAM;
    hsram1.Init.MemoryDataWidth   = FSMC_NORSRAM_MEM_BUS_WIDTH_16;
    hsram1.Init.BurstAccessMode    = FSMC_BURST_ACCESS_MODE_DISABLE;
    hsram1.Init.WaitSignalPolarity = FSMC_WAIT_SIGNAL_POLARITY_LOW;
    hsram1.Init.WrapMode           = FSMC_WRAP_MODE_DISABLE;
    hsram1.Init.WaitSignalActive   = FSMC_WAIT_TIMING_BEFORE_WS;
    hsram1.Init.WriteOperation     = FSMC_WRITE_OPERATION_ENABLE;
    hsram1.Init.WaitSignal         = FSMC_WAIT_SIGNAL_DISABLE;
    hsram1.Init.ExtendedMode       = FSMC_EXTENDED_MODE_DISABLE;
    hsram1.Init.AsynchronousWait   = FSMC_ASYNCHRONOUS_WAIT_DISABLE;
    hsram1.Init.WriteBurst         = FSMC_WRITE_BURST_DISABLE;

    if (HAL_SRAM_Init(&hsram1, &timing, &timing) != HAL_OK) {
        return HAL_ERROR;
    }

    return HAL_OK;
}
```

### 时序参数计算

假设：

- FSMC 时钟 `HCLK = 168 MHz`
- 外部 SRAM 地址建立时间要求 `tAS >= 10 ns`
- 数据建立时间要求 `tDW >= 45 ns`
- 时钟周期 `T = 5.95 ns`

则：

```
ADDSET + 1 >= ceil(10 / 5.95) = 2
DATAST + 1 >= ceil(45 / 5.95) = 8
```

初始配置应至少满足：

```
AddressSetupTime = 1;
DataSetupTime    = 7;
```

工程上还需加入：

- PCB 走线延迟；
- 芯片温度和电压变化；
- 外部器件参数离散性；
- 示波器测量误差；
- 控制器实际时序限制。

因此首版通常保留 1 至 2 个时钟周期余量，再通过波形和压力测试优化。

---

## 5.4 LCD 8080 接口

LCD 控制器通常将两个地址映射为：

```
写命令: FSMC 地址 = LCD_BASE + REG_OFFSET
写数据: FSMC 地址 = LCD_BASE + DATA_OFFSET
```

核心接口：

```
typedef struct {
    volatile uint16_t reg;
    volatile uint16_t data;
} lcd_fsmc_t;

#define LCD ((lcd_fsmc_t *)0x60000000UL)

static inline void lcd_cmd(uint16_t command)
{
    LCD->reg = command;
}

static inline void lcd_data(uint16_t data)
{
    LCD->data = data;
}

static void lcd_write_reg(uint16_t command, uint16_t value)
{
    lcd_cmd(command);
    lcd_data(value);
}

static void lcd_write_pixels(const uint16_t *pixels, uint32_t count)
{
    if ((pixels == NULL) || (count == 0U)) {
        return;
    }

    lcd_cmd(0x2CU); /* Memory Write */

    for (uint32_t i = 0U; i < count; ++i) {
        LCD->data = pixels[i];
    }
}
```

### DMA 刷屏

CPU 循环写入存在两个问题：

1. CPU 被长时间占用；
2. 编译器生成的循环不一定能达到总线极限。

DMA 方案应确保：

- DMA 外设地址固定为 LCD 数据窗口；
- 内存地址递增；
- 数据宽度与 LCD/FSMC 宽度一致；
- 传输完成后再释放帧缓冲；
- DMA 访问前后处理 Cache 一致性。

示意代码：

```
HAL_StatusTypeDef lcd_dma_write(const uint16_t *pixels, uint32_t count)
{
    if ((pixels == NULL) || (count == 0U) || (count > 0xFFFFU)) {
        return HAL_ERROR;
    }

    lcd_cmd(0x2CU);

    return HAL_DMA_Start(
        &hdma_memtomem,
        (uint32_t)pixels,
        (uint32_t)&LCD->data,
        count
    );
}
```

某些 STM32 的 DMA 控制器要求外设地址配置在 DMA 外设端口，而不是普通内存到内存模式。实际实现必须检查 DMA 请求映射和 HAL 接口语义。

---

## 5.5 NAND 接口的命令、地址、数据阶段

NAND 通常至少需要：

- `CLE`：命令锁存使能；
- `ALE`：地址锁存使能；
- `CE#`：芯片使能；
- `RE#`：读使能；
- `WE#`：写使能；
- `R/B#`：忙/就绪；
- 数据总线 `D[7:0]` 或 `D[15:0]`。

FSMC NAND 通过不同地址窗口区分：

```
NAND_CMD_AREA
NAND_ADDR_AREA
NAND_DATA_AREA
```

示意代码：

```
#define NAND_CMD_AREA   ((volatile uint8_t *)0x70000000UL)
#define NAND_ADDR_AREA  ((volatile uint8_t *)0x70010000UL)
#define NAND_DATA_AREA  ((volatile uint8_t *)0x70020000UL)

static void nand_write_command(uint8_t command)
{
    *NAND_CMD_AREA = command;
}

static void nand_write_address(uint8_t address)
{
    *NAND_ADDR_AREA = address;
}

static uint8_t nand_read_data(void)
{
    return *NAND_DATA_AREA;
}

static bool nand_wait_ready(uint32_t timeout_ms)
{
    uint32_t start = board_time_ms();

    while (nand_ready_pin_is_low()) {
        if ((board_time_ms() - start) >= timeout_ms) {
            return false;
        }
    }

    return true;
}
```

NAND 驱动不能把物理页直接暴露给上层。生产系统至少要考虑：

- 坏块管理；
- ECC；
- 擦除块管理；
- 掉电保护；
- 写放大；
- 磨损均衡；
- OOB 区域布局。

---

## 5.6 读写时序和扩展模式

FSMC 常见配置项：

|参数|作用|
|---|---|
|`AddressSetupTime`|地址建立时间|
|`AddressHoldTime`|地址保持时间|
|`DataSetupTime`|数据建立/保持阶段|
|`BusTurnAroundDuration`|读写方向切换间隔|
|`AccessMode`|异步访问模式 A/B/C/D|
|`ExtendedMode`|读写时序是否独立配置|
|`WriteBurst`|是否使用写突发|
|`WaitSignal`|是否使用外部等待信号|
|`AsynchronousWait`|异步等待控制|

读和写参数不一定相同。例如：

- LCD 写周期较快，读 ID 需要更长数据建立时间；
- NOR Flash 读周期较长，写命令对时序要求不同；
- SRAM 读写时间可能对称，也可能不同。

因此对于存在明显差异的设备，应启用扩展模式：

```
hsram1.Init.ExtendedMode = FSMC_EXTENDED_MODE_ENABLE;
```

然后分别配置读写时序。

---

## 5.7 GPIO 和电气约束

FSMC 不是只打开外设时钟即可使用，必须同时完成：

- FSMC 外设时钟；
- GPIO 端口时钟；
- 所有地址线、数据线和控制线复用；
- GPIO 速度等级；
- 上拉/下拉策略；
- 外部器件复位和电源时序；
- 必要时的总线串联电阻。

示意：

```
static void fsmc_gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOE_CLK_ENABLE();
    __HAL_RCC_FSMC_CLK_ENABLE();

    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF12_FSMC;

    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_8 |
               GPIO_PIN_9 | GPIO_PIN_10 | GPIO_PIN_14 |
               GPIO_PIN_15;
    HAL_GPIO_Init(GPIOD, &gpio);

    gpio.Pin = GPIO_PIN_7 | GPIO_PIN_8 | GPIO_PIN_9 |
               GPIO_PIN_10 | GPIO_PIN_11 | GPIO_PIN_12 |
               GPIO_PIN_13 | GPIO_PIN_14 | GPIO_PIN_15;
    HAL_GPIO_Init(GPIOE, &gpio);
}
```

实际引脚必须根据芯片 Alternate Function 表和原理图确认。

---

## 6. 性能量化分析

## 6.1 吞吐率估算

假设：

- HCLK = 168 MHz；
- 16 位总线；
- 地址阶段 2 个周期；
- 数据阶段 8 个周期；
- 额外周期 1 个。

则单次访问周期：

```
Ncycle = 2 + 8 + 1 = 11 cycles
Taccess = 11 / 168 MHz = 65.5 ns
```

理论峰值：

```
Throughput = 2 bytes / 65.5 ns
           ≈ 30.5 MB/s
```

这是总线理论值，实际吞吐率还会受以下因素影响：

- CPU 指令执行和循环开销；
- DMA 仲裁；
- Cache Miss；
- LCD 内部写入速度；
- 外部器件 `tACC`；
- 总线翻转和等待周期；
- RTOS 中断抢占。

### 典型实测参考

以下数据为常见 Cortex-M4、168 MHz、16 位 FSMC、无额外等待状态条件下的工程参考值，不代表所有芯片：

|访问方式|理论/实测吞吐率|CPU 占用|
|---|---|---|
|C 语言逐元素写 SRAM|18~25 MB/s|35%~55%|
|优化后的连续 `uint16_t` 写入|24~30 MB/s|25%~40%|
|DMA 连续写入 SRAM|28~31 MB/s|小于 5%|
|DMA 刷 LCD|受 LCD 内部写周期限制，约 8~25 MB/s|小于 10%|
|8 位总线写入|约为 16 位总线的 40%~60%|较高|

测量方式：

```
uint32_t start = DWT->CYCCNT;

for (uint32_t i = 0U; i < count; ++i) {
    external_sram[i] = pattern;
}

uint32_t cycles = DWT->CYCCNT - start;
```

换算公式：

```
time = cycles / CPU_frequency
throughput = bytes / time
```

---

## 6.2 内存开销

FSMC 控制器本身通常只消耗少量寄存器资源：

- 外设寄存器：由芯片固定分配；
- HAL 句柄：通常约 100~300 字节；
- DMA 句柄：通常几十到数百字节；
- 驱动状态结构体：视实现约 100~1000 字节；
- LCD 帧缓存：`width × height × 2` 字节。

例如 800×480 RGB565：

```
800 × 480 × 2 = 768000 bytes ≈ 750 KiB
```

这通常已经超过多数 MCU 内部 SRAM，因此需要：

- 外部 SRAM/SDRAM；
- 分块刷新；
- 双缓冲；
- 行缓冲；
- 图形库的局部刷新机制。

---

## 6.3 瓶颈与优化

### 瓶颈一：时序配置过于保守

表现：

- 波形稳定但吞吐率低；
- LCD 刷新率不足；
- CPU 长时间等待。

优化：

1. 根据器件数据手册计算最小参数；
2. 使用示波器验证实际脉宽；
3. 逐步减少 `DATAST`；
4. 在高低温、电压边界下进行压力测试。

### 瓶颈二：CPU 循环刷新

优化：

- 使用 DMA；
- 使用连续内存和正确对齐；
- 避免每个像素调用函数；
- 通过行缓冲减少 Cache 抖动；
- 将命令设置与数据传输分离。

### 瓶颈三：Cache 不一致

Cortex-M7 或带 D-Cache 的 Cortex-M33 上，DMA 读取 CPU 写入的帧缓存前必须清理 Cache：

```
SCB_CleanDCache_by_Addr((uint32_t *)buffer, byte_count);
```

DMA 写入后 CPU 读取则需要失效 Cache：

```
SCB_InvalidateDCache_by_Addr((uint32_t *)buffer, byte_count);
```

地址和长度通常需要按 Cache Line 对齐，实际实现应封装对齐计算。

### 瓶颈四：总线竞争

当 FSMC、DMA、以太网、LCD、SDRAM 同时访问外部总线时，会产生仲裁延迟。

优化方向：

- 将高带宽设备放在独立控制器；
- 控制 DMA 传输块大小；
- 降低低优先级刷新任务频率；
- 避免中断中执行大块外部内存访问；
- 对实时任务使用内部 SRAM。

---

## 7. 应用场景选型指南

## 7.1 决策流程图

```
需要连接外部并行设备？
|
+-- 否 --> 使用 SPI/QSPI/SDMMC 等串行或专用接口
|
+-- 是
    |
    +-- 需要大容量、页编程、坏块管理？
    |      |
    |      +-- 是 --> NAND + ECC + FTL/文件系统
    |      |
    |      +-- 否
    |
    +-- 需要连续高速随机读写？
    |      |
    |      +-- 是 --> SRAM 或 SDRAM
    |      |
    |      +-- 否
    |
    +-- 需要连接 8080/6800 LCD？
    |      |
    |      +-- 是 --> FSMC/FMC 异步 Bank + DMA 刷屏
    |      |
    |      +-- 否
    |
    +-- 需要 XIP 或直接存放固件？
           |
           +-- 是 --> NOR/QSPI/OSPI，确认启动和执行支持
           |
           +-- 否 --> 根据容量、成本和访问模式选 SRAM/NOR/NAND
```

## 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|480×272 LCD 刷新|FSMC 8080 + DMA|低 CPU 占用，时序可控|
|工业采集缓存|外部 SRAM|随机读写延迟低，软件简单|
|4 MB 配置与日志|NOR Flash|坏块问题少，可靠性较好|
|数百 MB 原始数据|NAND|容量大、成本低，但需 ECC/磨损均衡|
|800×480 双帧缓冲|SDRAM/FMC|SRAM 容量和成本通常不合适|
|实时控制参数|内部 SRAM/Flash|避免外部总线竞争和不确定延迟|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **先看原理图，再写地址宏**。
2. **先根据时序计算，再用仪器验证**。
3. **所有硬件窗口访问都使用 `volatile`** 。
4. **外部总线数据宽度必须与器件和 PCB 连接一致**。
5. **将 Bank、地址偏移、时序参数集中管理**。
6. **将 LCD 控制器协议和 FSMC 总线访问分层**。
7. **DMA 传输必须定义缓存所有权和完成通知机制**。
8. **外部内存不能默认等价于内部 SRAM**，其访问存在等待周期和总线竞争。
9. **启动早期访问外部设备前，必须确认供电、复位和 GPIO 初始化完成**。
10. **必须具备硬件探测和故障降级能力**。

## 8.2 选型决策矩阵

|指标|SRAM|NOR|NAND|SDRAM|
|---|---|---|---|---|
|随机访问|5|3|1|4|
|容量|2|3|5|5|
|软件复杂度|5|3|1|2|
|可靠性|5|4|2|3|
|成本/容量|2|3|5|4|
|实时确定性|5|3|1|3|

评分越高越适合。

## 8.3 编码规范

```
#define FSMC_BANK_BASE       (0x60000000UL)
#define FSMC_DEVICE_ADDR     ((volatile uint16_t *)FSMC_BANK_BASE)

static bool fsmc_sram_probe(void)
{
    volatile uint16_t *mem = FSMC_DEVICE_ADDR;
    const uint16_t old_value = mem[0];
    const uint16_t patterns[] = { 0x0000U, 0xFFFFU, 0x55AAU, 0xAA55U };

    for (uint32_t i = 0U; i < 4U; ++i) {
        mem[0] = patterns[i];

        if (mem[0] != patterns[i]) {
            mem[0] = old_value;
            return false;
        }
    }

    mem[0] = old_value;
    return true;
}
```

探测代码应注意：

- 不破坏有效数据；
- 不在系统运行期随意覆盖共享区域；
- 不把简单数据回读当作完整内存测试；
- 对生产设备使用分区和保护策略。

---

## 9. 常见错误与避坑指南

## 9.1 地址偏移错误

### 错误代码

```
#define LCD_REG  ((volatile uint16_t *)0x60000000U)
#define LCD_DATA ((volatile uint16_t *)0x60000001U)
```

### 根因

16 位总线下，外部地址偏移通常按字节地址和地址线连接规则排列，`+1` 可能导致非对齐访问或错误的 RS 线选择。

### 正确实现

```
#define LCD_REG  ((volatile uint16_t *)0x60000000U)
#define LCD_DATA ((volatile uint16_t *)0x60000002U)
```

具体值必须由原理图确认。

### 风险影响

- LCD 命令被识别为数据；
- 数据写入无效；
- 奇偶字节错位；
- 产生 HardFault 或总线错误。

---

## 9.2 忽略 `volatile`

### 错误代码

```
uint16_t *lcd_data = (uint16_t *)0x60000002U;

for (uint32_t i = 0U; i < count; ++i) {
    *lcd_data = buffer[i];
}
```

### 根因

普通指针访问可能被编译器优化，硬件窗口不是普通内存。

### 正确实现

```
volatile uint16_t *lcd_data =
    (volatile uint16_t *)0x60000002U;
```

### 风险影响

- 写操作被合并或删除；
- 实际总线周期数量与源代码不一致；
- 外部设备协议时序被破坏。

---

## 9.3 时序过快

### 错误代码

```
timing.DataSetupTime = 1U;
```

### 根因

仅按 CPU 主频配置，没有比较外部器件的 `tACC`、`tDW`、`tWP`、`tDS`。

### 正确实现

```
static uint32_t cycles_from_ns(uint32_t ns, uint32_t hclk_hz)
{
    const uint64_t numerator = (uint64_t)ns * hclk_hz;
    return (uint32_t)((numerator + 999999999ULL) / 1000000000ULL);
}
```

然后根据芯片寄存器定义换算为具体字段值，并加入裕量。

### 风险影响

- 高温或低压下随机读写错误；
- 大批量生产后出现低比例现场故障；
- 逻辑分析仪低速测试正常，高速运行失败。

---

## 9.4 DMA 与 Cache 不一致

### 错误代码

```
draw_frame(buffer);
HAL_DMA_Start(&hdma, (uint32_t)buffer,
              (uint32_t)&LCD->data, count);
```

### 根因

CPU 对 `buffer` 的修改仍停留在 D-Cache 中，DMA 从 RAM 读取到旧数据。

### 正确实现

```
SCB_CleanDCache_by_Addr((uint32_t *)buffer, byte_count);
HAL_DMA_Start(&hdma, (uint32_t)buffer,
              (uint32_t)&LCD->data, count);
```

### 风险影响

- LCD 偶发显示旧帧；
- 图像撕裂或局部脏数据；
- 问题随优化级别和中断时序变化。

---

## 9.5 读写方向切换没有留时间

### 错误代码

```
lcd_cmd(LCD_READ_ID);
uint16_t id = lcd_read_data();
lcd_write_pixels(buffer, count);
```

### 根因

外部总线从读切换到写时，FSMC、LCD 和数据线三方可能存在瞬态驱动冲突。

### 正确实现

- 配置足够的 `BusTurnAroundDuration`；
- 按 LCD 数据手册插入必要等待；
- 确认读周期结束后再切换；
- 用示波器确认数据线没有明显争用。

### 风险影响

- 数据总线过流；
- 读写偶发错误；
- 电磁干扰增大；
- 外部器件寿命下降。

---

## 9.6 忽略非对齐访问

### 错误代码

```
uint8_t *p = (uint8_t *)0x60000000U;
uint16_t value = *(uint16_t *)(p + 1);
```

### 根因

外部并行总线按 16 位访问，而软件执行了非对齐半字访问。

### 正确实现

使用与硬件宽度一致的对齐类型：

```
volatile uint16_t *p16 = (volatile uint16_t *)0x60000000U;
uint16_t value = p16[index];
```

### 风险影响

- 总线拆分访问；
- 地址线和字节使能关系异常；
- 某些 Cortex-M 配置下触发 UsageFault。

---

## 10. 多机制组合使用方案

## 10.1 FSMC + DMA + 双缓冲架构

适用于 LCD 连续刷新：

```
图形任务
   |
   v
FrameBuffer A/B
   |
   +-- Cache Clean
   |
   v
DMA
   |
   v
FSMC LCD 数据窗口
   |
   v
LCD 控制器
```

核心状态：

```
typedef enum {
    LCD_DMA_IDLE = 0,
    LCD_DMA_BUSY,
    LCD_DMA_ERROR
} lcd_dma_state_t;

typedef struct {
    const uint16_t *buffer;
    uint32_t pixels;
    volatile lcd_dma_state_t state;
} lcd_dma_transfer_t;

static lcd_dma_transfer_t g_lcd_dma;

bool lcd_start_transfer(const uint16_t *buffer, uint32_t pixels)
{
    if ((buffer == NULL) || (pixels == 0U)) {
        return false;
    }

    if (g_lcd_dma.state == LCD_DMA_BUSY) {
        return false;
    }

    g_lcd_dma.buffer = buffer;
    g_lcd_dma.pixels = pixels;
    g_lcd_dma.state  = LCD_DMA_BUSY;

#if defined(SCB_CleanDCache_by_Addr)
    SCB_CleanDCache_by_Addr(
        (uint32_t *)buffer,
        (int32_t)(pixels * sizeof(uint16_t))
    );
#endif

    lcd_cmd(0x2CU);

    if (HAL_DMA_Start_IT(&hdma_memtomem,
                         (uint32_t)buffer,
                         (uint32_t)&LCD->data,
                         pixels) != HAL_OK) {
        g_lcd_dma.state = LCD_DMA_ERROR;
        return false;
    }

    return true;
}

void HAL_DMA_XferCpltCallback(DMA_HandleTypeDef *hdma)
{
    if (hdma == &hdma_memtomem) {
        g_lcd_dma.state = LCD_DMA_IDLE;
    }
}
```

工程上还应加入：

- DMA 传输超时；
- 取消传输；
- 缓冲区生命周期管理；
- RTOS 信号量或事件通知；
- 传输区域边界检查。

---

## 10.2 FSMC + MPU 属性配置

外部 SRAM 如果用于数据缓存，建议将其配置为：

- Normal Memory；
- Write-back 或 Write-through，视 DMA 一致性策略决定；
- 可缓存但必须处理 DMA；
- 或直接配置为 Non-cacheable，牺牲性能换取一致性简单。

典型策略：

|使用方式|MPU 建议|
|---|---|
|CPU 独占访问|Cacheable|
|CPU 与 DMA 共享|Non-cacheable 或显式 Cache Maintenance|
|LCD 帧缓存|Cacheable + DMA 前 Clean|
|外部寄存器窗口|Device/Strongly Ordered，禁止 Cache|
|外部 NOR XIP|Normal Memory，按执行需求配置|

不能把 LCD 寄存器窗口配置成普通可缓存内存，否则 Cache 可能吞掉实际硬件访问。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业触摸屏 LCD 刷新

### 需求

- 480×272，RGB565；
- 60 Hz 局部刷新；
- MCU 主频 168 MHz；
- 触摸采集、通信和显示任务并发运行；
- CPU 占用需要低于 50%。

### 架构

```
GUI 绘制任务
    |
    v
外部 SRAM 行缓冲
    |
    v
Cache Clean
    |
    v
DMA
    |
    v
FSMC 16-bit 8080 LCD
```

单帧大小：

```
480 × 272 × 2 = 261120 bytes
```

若全屏 60 Hz：

```
261120 × 60 ≈ 15.67 MB/s
```

这对 16 位 FSMC 理论带宽可行，但还要考虑 LCD 内部写周期和其他总线访问。因此工业项目通常使用：

- 脏矩形刷新；
- 行缓冲；
- DMA 链式传输；
- 限制全屏刷新频率；
- 触摸和通信任务使用内部 SRAM。

### 设计要点

- LCD 命令窗口和数据窗口分离；
- 刷新任务不能在中断中执行；
- DMA 完成后再复用帧缓冲；
- 显示控制器支持时，使用窗口设置减少命令开销；
- 对背光 PWM、TE 信号和 DMA 完成事件进行同步。

---

## 11.2 案例二：实时采集系统外部 SRAM 缓存

### 需求

- ADC 持续采样；
- 内部 SRAM 不足以保存多个采样块；
- 采样中断延迟必须小于 10 us；
- 外部 SRAM 作为环形缓存。

### 架构

```
ADC DMA
  |
  v
内部 SRAM Ping-Pong Buffer
  |
  v
搬运任务
  |
  v
FSMC 外部 SRAM Ring Buffer
  |
  +-- 网络发送
  +-- 本地存储
```

设计上不建议 ADC DMA 直接高频写 FSMC 外部 SRAM，因为：

- 外部访问延迟更高；
- 总线可能被 LCD 或其他 DMA 占用；
- Cache 和 MPU 管理更复杂；
- 实时性更难证明。

### 环形缓存示意

```
#define SAMPLE_BLOCK_WORDS  (1024U)
#define SAMPLE_RING_BLOCKS  (16U)

static volatile uint16_t *const sample_ring =
    (volatile uint16_t *)0x68000000UL;

static uint32_t wr_block;
static uint32_t rd_block;

bool sample_ring_push(const uint16_t *src)
{
    if (src == NULL) {
        return false;
    }

    uint32_t next = (wr_block + 1U) % SAMPLE_RING_BLOCKS;

    if (next == rd_block) {
        return false; /* overflow: discard or raise alarm */
    }

    for (uint32_t i = 0U; i < SAMPLE_BLOCK_WORDS; ++i) {
        sample_ring[wr_block * SAMPLE_BLOCK_WORDS + i] = src[i];
    }

    __DMB();
    wr_block = next;

    return true;
}
```

真实产品应使用 DMA 搬运并明确生产者/消费者同步协议，必要时使用原子变量或临界区。

---

## 11.3 案例三：NAND 日志存储

### 需求

- 每天写入数百 MB 采样日志；
- 断电时不能破坏已有日志；
- NAND 存在坏块；
- 需要多年运行寿命。

### 架构

```
应用日志
   |
   v
块设备抽象层
   |
   v
FTL / 磨损均衡 / 坏块表
   |
   v
ECC
   |
   v
FSMC NAND 控制器
```

核心设计要点：

- 不能直接 `memcpy` 到 NAND；
- 每页写入前检查可用状态；
- 每个物理块建立擦写计数；
- ECC 纠错失败时标记介质故障；
- 元数据使用双副本和 CRC；
- 日志采用追加写，避免频繁原地更新；
- 掉电恢复通过提交标志和序列号完成。

NAND 控制器只是物理访问层，**不能替代文件系统、FTL 和可靠性策略**。

---

## 12. 高频问题深度答疑

### 问题一：FSMC 地址为什么经常不是连续的 `+1`？

因为软件地址以字节为单位，而外部总线可能以 16 位或更宽数据为单位。除此之外，LCD 的 `RS/DC` 信号通常连接到某根地址线，地址偏移由总线宽度和地址线布线共同决定。必须从原理图追踪 `FSMC_Ax -> RS` 的连接关系。

### 问题二：时序参数越大是否越稳定？

不完全是。更大的时序通常提高器件容错，但会降低吞吐率，并可能增加总线占用和实时任务延迟。正确方法是：

1. 按最坏器件参数计算；
2. 预留有限裕量；
3. 通过高低温、电压、频率和压力测试验证；
4. 找到稳定性与性能的平衡点。

### 问题三：为什么 SRAM 读写正常，LCD 却无法显示？

LCD 不只是存储器，它还具有命令协议。常见原因：

- 命令和数据地址偏移错误；
- LCD 复位时序错误；
- 颜色格式配置错误；
- 读写时序不满足 LCD 控制器要求；
- `RS/DC` 连接到不同地址线；
- LCD 数据宽度配置错误；
- 窗口坐标或扫描方向设置错误。

### 问题四：FSMC 是否可以直接连接任意并口设备？

不能。FSMC 只提供有限的标准异步时序模式。需要确认设备是否支持：

- 独立地址/数据总线；
- 8080/6800 类控制方式；
- 异步 SRAM/NOR 时序；
- 设备所需的等待信号；
- 所需电平和时钟频率。

如果设备时序包含复杂命令握手、源同步时钟或特殊边沿协议，通常需要 FPGA、SPI、专用并口控制器或 GPIO 时序引擎。

### 问题五：外部 SRAM 能否替代内部 SRAM 用于中断实时数据？

可以使用，但不能无条件替代。外部 SRAM 访问延迟受：

- FSMC 等待周期；
- 总线仲裁；
- Cache 状态；
- DMA 活动；
- 中断嵌套

影响。硬实时数据结构、栈、ISR 高频访问变量应优先放在内部 SRAM。外部 SRAM 更适合大块缓存和非关键路径数据。

### 问题六：为什么 DMA 刷 LCD 后显示内容偶发错误？

常见根因包括：

- D-Cache 未清理；
- DMA 源缓冲区被提前复用；
- LCD 数据窗口地址配置错误；
- DMA 数据宽度与 FSMC 总线宽度不一致；
- DMA 传输完成事件处理错误；
- LCD 内部忙状态未考虑；
- 多任务同时写 LCD。

需要建立明确的资源所有权：

```
GUI 任务拥有缓冲区
    -> 提交 DMA 后转移所有权
DMA 完成中断
    -> 释放缓冲区
GUI 才能再次绘制
```

---

## 13. 课程核心总结

### 核心要点

1. **FSMC 的本质是将外部异步总线协议转换为 MCU 内存访问周期**。
2. **地址映射必须结合总线宽度、地址线复用和原理图确定**。
3. **时序配置必须由外部器件数据手册反推，而不是照抄示例工程**。
4. **LCD 访问本质上是命令窗口和数据窗口的地址映射**。
5. **NAND 需要 ECC、坏块管理、磨损均衡和掉电恢复，FSMC 只负责物理访问**。
6. **DMA 可显著降低 CPU 占用，但会引入 Cache 一致性和缓冲区所有权问题**。
7. **实时控制数据优先放内部 SRAM，外部 SRAM 主要承担容量扩展和大块缓存**。
8. **生产级验证必须包含波形验证、压力测试、极限温度和电压测试**。

### 性能排序

在常见 MCU 系统中，单次随机访问延迟大致为：

```
内部 SRAM
    > 外部 SRAM
    > NOR Flash
    > QSPI/OSPI Flash 随机访问
    > NAND 页访问
    > SD/eMMC 文件系统访问
```

这里的 `>` 表示性能更高，实际结果依赖具体器件和配置。

### 通用选型结论

- 要随机读写：**SRAM**。
- 要低成本大容量：**NAND + 完整 FTL**。
- 要保存固件或配置：**NOR/QSPI NOR**。
- 要并行刷 LCD：**FSMC/FMC + DMA**。
- 要大型帧缓存：**SDRAM/FMC**。
- 要强实时确定性：**内部 SRAM 优先**。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选方案|关键注意事项|
|---|---|---|
|LCD 8080 刷屏|FSMC 16 bit + DMA|地址偏移、DMA、Cache|
|外部随机缓存|异步 SRAM|时序、数据宽度、总线竞争|
|固件 XIP|NOR/QSPI NOR|启动映射、读延迟、Cache|
|大容量日志|NAND|ECC、坏块、磨损均衡|
|大型图形界面|SDRAM/FMC|初始化序列、刷新、MPU|
|低引脚数量|SPI/QSPI|吞吐率和随机访问延迟|

### 14.2 特性对比表

|特性|FSMC 异步模式|FSMC NAND|FSMC LCD|
|---|---|---|---|
|基本访问|线性内存访问|命令/地址/数据窗口|命令/数据寄存器|
|主要信号|NE、NOE、NWE|CLE、ALE、CE、RE、WE、R/B|RS、RD、WR、CS|
|典型数据宽度|8/16 bit|8/16 bit|8/16 bit|
|关键配置|ADDSET、DATAST|NAND 时序、ECC|读写时序、地址偏移|
|常见故障|读写错误|ECC/坏块问题|命令数据错位|
|DMA 价值|中|中|高|

### 14.3 常用检查清单

```
[ ] 确认 MCU 型号和 FSMC/FMC 版本
[ ] 确认 GPIO 复用功能
[ ] 确认外部器件电压兼容
[ ] 确认数据总线宽度
[ ] 确认 RS/DC 与地址线连接
[ ] 确认 Bank 基地址
[ ] 根据数据手册计算时序
[ ] 配置 GPIO、RCC 和 FSMC
[ ] 使用 volatile 访问硬件窗口
[ ] 验证最小读写测试
[ ] 用示波器确认 NE/NWE/NOE 波形
[ ] 验证 Cache/DMA 一致性
[ ] 执行长时间、温度和电压压力测试
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实践以下内容：

- 能否从原理图确定 LCD 命令地址和数据地址？
- 能否解释 8 位、16 位 FSMC 数据宽度对地址映射的影响？
- 能否根据 `tAS`、`tACC`、`tWP` 计算最小时序参数？
- 能否解释 `ADDSET` 和 `DATAST` 对总线波形的影响？
- 能否区分 SRAM、NOR、NAND 和 LCD 的软件访问模型？
- 能否配置异步 SRAM Bank 并完成读写探测？
- 能否使用 DMA 完成 LCD 连续刷屏？
- 能否处理 Cortex-M7 D-Cache 与 DMA 的一致性？
- 能否定位 LCD 命令/数据错位问题？
- 能否解释外部 SRAM 不适合直接承载所有硬实时数据的原因？
- 能否设计 NAND 的 ECC、坏块和磨损均衡分层？
- 能否使用逻辑分析仪验证读写周期是否满足器件手册要求？
- 能否为 FSMC 驱动增加超时、错误码和故障降级路径？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：寄存器级驱动 SRAM

要求：

- 不使用 HAL；
- 配置一个 16 位异步 SRAM Bank；
- 实现单元读写、连续读写和数据线测试；
- 输出实际读写周期时间。

验证：

```
0x0000
0xFFFF
0x55AA
0xAA55
Walking 1
Walking 0
```

### 任务二：LCD 命令/数据映射

要求：

- 完成 LCD 复位和初始化；
- 读取 LCD ID；
- 设置显示窗口；
- 使用 RGB565 填充纯色；
- 测量全屏刷新时间。

### 任务三：DMA 局部刷新

要求：

- 将刷新区域抽象为矩形；
- 使用 DMA 发送行缓冲；
- 支持 DMA 完成回调；
- 支持超时和取消；
- 在带 D-Cache 的 MCU 上完成一致性处理。

### 任务四：总线异常注入

要求：

- 人为减少 `DATAST`；
- 改变 HCLK；
- 施加高温或低压条件；
- 记录错误率与时序裕量；
- 建立参数和可靠性的关系曲线。

### 任务五：NAND 可靠性层

要求：

- 实现页读写；
- 实现块擦除；
- 实现坏块扫描；
- 集成 ECC；
- 增加掉电恢复和简单磨损均衡；
- 设计物理层、FTL、块设备层和文件系统层接口。

## 16.2 性能测试方法

至少测量以下指标：

```
1. 单次随机读延迟
2. 单次随机写延迟
3. 连续读吞吐率
4. 连续写吞吐率
5. DMA 与 CPU 方式的差异
6. 中断延迟增加量
7. 不同 DATAST 下的误码率
8. Cache 开启/关闭下的吞吐率
9. 多 DMA 竞争时的最坏延迟
10. 高低温和电压边界下的稳定性
```

测试工具：

- DWT `CYCCNT`；
- 逻辑分析仪；
- 示波器；
- DMA 传输计数器；
- RTOS trace；
- 内存压力测试；
- 长时间循环读写测试。

## 16.3 进阶学习方向

- STM32 FMC SDRAM 初始化与刷新机制；
- Cortex-M7 MPU、Cache 和 DMA 一致性；
- LCD TE 同步与撕裂控制；
- LTDC 与 FMC/SDRAM 协同架构；
- NOR Flash XIP、启动映射和代码重定位；
- NAND ONFI 时序、ECC 和坏块管理；
- FTL、磨损均衡和掉电保护；
- 高速并行总线 PCB 布线与信号完整性；
- 外部总线安全：地址空间隔离、执行保护和故障注入；
- 基于示波器自动采集和回归验证 FSMC 时序。