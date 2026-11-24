
本文以 **Microchip ATM90E32AS 三相电能计量芯片**为主要参考器件，覆盖 SPI 寄存器访问、计量参数配置、校准参数管理、电压/电流/功率/电能读取、符号与字节序处理、波形采样、中断、掉电保存、故障诊断以及 RTOS 服务架构。

> 芯片版本、寄存器地址、校准流程和常数可能因 ATM90E32/ATM90E36、ADE7953/ADE9000 等型号而异。量产实现必须以目标器件最新数据手册、勘误表和参考设计为准，不能仅替换寄存器宏完成移植。

---

## 1. 学习目标

### 理解

- 理解 **BSP、计量芯片驱动、计量服务、校准模块、费率结算和保护控制**之间的边界。
- 理解电压、电流、有功功率、无功功率、视在功率、功率因数、频率和电能的测量链路。
- 理解计量芯片 ADC、数字滤波、相位补偿、功率计算和电能累加的底层机制。
- 理解 CT、分流器、电压采样网络、隔离、电磁兼容和 PCB 布局对整机精度的影响。
- 理解寄存器快照一致性、电能累计回绕、掉电保存和断电结算风险。

### 掌握

- 掌握生产级 SPI 寄存器读写、CRC/回读校验、超时和总线互斥。
- 掌握有符号功率寄存器、无符号 RMS 寄存器和多字节电能寄存器的解析。
- 掌握比例系数、增益、相位和零点校准参数的管理方法。
- 掌握周期采样、阈值告警、过零、中断和掉电事件处理。
- 掌握固定点单位体系以及避免整数溢出的计算方法。

### 精通

- 精通三相数据的一致性快照设计。
- 精通脉冲常数、寄存器累加单位和物理电能之间的量化关系。
- 精通小电流、低功率因数、谐波和双向能流条件下的误差分析。
- 精通 SPI 干扰、寄存器配置丢失、计量溢出和掉电丢账问题的定位。
- 精通计量参数的版本控制、双副本存储、CRC 校验和安全更新。

### 能够设计

- 能够设计多型号、多实例、单相/三相可扩展的电能计量 BSP。
- 能够构建“芯片驱动 + 计量服务 + 电能账本 + 告警 + 通信发布”架构。
- 能够完成从实验室标定到量产校准、现场诊断的完整工程链路。
- 能够根据精度、隔离、成本、实时性和认证目标完成器件与采样前端选型。

---

## 2. 前置要求

### 知识要求

- SPI CPOL/CPHA、片选、全双工传输、DMA 和总线互斥。
- 二补码、定点数、整数提升、符号扩展和溢出规则。
- 交流电 RMS、相位、功率因数及有功/无功/视在功率定义。
- 三相三线、三相四线、星形和三角形系统。
- Cortex-M 中断、定时器、RTC、Backup SRAM 和看门狗。
- FreeRTOS 任务、队列、互斥锁、任务通知和优先级继承。
- Flash 擦写粒度、掉电一致性、CRC 和磨损均衡。

### 技能要求

- 能阅读计量芯片数据手册、应用笔记和寄存器表。
- 能使用示波器、逻辑分析仪、标准功率源和参考电能表。
- 能完成高压采样电路的安全评审和误差预算。
- 能编写无动态内存、有超时边界且可进行故障注入的 C 驱动。
- 能使用脚本完成多点标定、回归拟合和误差曲线分析。

---

## 3. 技术概述

### 3.1 系统分层

```
业务与通信
  |-- Modbus/DL-T645/MQTT
  |-- 费率结算、需量、事件记录
  |
计量服务
  |-- 周期快照、质量状态、阈值告警
  |-- 电能账本、掉电保存、时间戳
  |
校准与配置
  |-- 增益、相位、偏置、启动阈值
  |-- 参数版本、CRC、双副本存储
  |
计量芯片驱动
  |-- 寄存器协议、复位、配置、数据解析
  |-- 中断状态、配置校验、芯片错误语义
  |
BSP
  |-- SPI、GPIO、IRQ、复位、时间、互斥
  |
计量芯片 + 模拟前端 + CT/分流器 + 电压网络
```

职责边界：

- **SPI 传输和 GPIO 控制属于 BSP。**
- **寄存器地址、芯片命令和原始值解析属于设备驱动。**
- **校准参数的加载、验证和应用属于校准模块。**
- **累计电能持久化、费率和账单属于计量服务或业务层。**
- **硬件快速保护不得依赖低速业务轮询。**

### 3.2 核心电气量

离散采样下，有效值为：

VRMS=1N∑n=0N−1v[n]2VRMS​=N1​n=0∑N−1​v[n]2​IRMS=1N∑n=0N−1i[n]2IRMS​=N1​n=0∑N−1​i[n]2​

有功功率：

P=1N∑n=0N−1v[n]i[n]P=N1​n=0∑N−1​v[n]i[n]

视在功率：

S=VRMSIRMSS=VRMS​IRMS​

功率因数：

PF=PSPF=SP​

电能：

E=∫P(t)dtE=∫P(t)dt

计量芯片通常在内部完成 ADC、滤波、乘法、积分和累加，MCU 主要负责读取结果、管理校准、时间和持久化。

### 3.3 主流方案分类

- **专用计量芯片**：精度、抗混叠和能量累加能力强，认证路径成熟。
- **MCU ADC 软件计量**：灵活，但实时性、同步采样、动态范围和认证压力更高。
- **数字隔离计量模块**：系统集成快，成本与尺寸较高。
- **智能电表 SoC**：计量核与 MCU 集成，成本低但平台绑定较强。
- **外置电能表/变送器**：通过 RS-485 或脉冲输出接入，适合工业控制柜。

---

## 4. 核心特性横向对比

### 4.1 实现方案对比

|方案|典型器件|相数|接口|波形能力|校准复杂度|适用场景|
|---|---|---|---|---|---|---|
|三相专用计量芯片|ATM90E32AS|3|SPI|中|中|三相电表、配电监测|
|高性能计量 AFE|ADE9000|3|SPI|强|高|电能质量、谐波分析|
|单相计量芯片|ADE7953|1|SPI/I²C|中|中|智能插座、单相电表|
|MCU 软件计量|高精度 ADC + MCU|可扩展|ADC/DMA|强|很高|特殊算法、定制仪器|
|隔离变送器|工业模块|1/3|RS-485|弱|低|PLC、长距离现场|
|脉冲计量接口|电表 CF 输出|1/3|Timer|无|低|仅累计电能|

### 4.2 电流采样方案对比

|方案|隔离|损耗|直流测量|相位误差|成本|典型用途|
|---|---|---|---|---|---|---|
|电流互感器 CT|是|低|否|需补偿|中|交流电表|
|分流器|否|较高|是|低|低|单相低成本设备|
|Rogowski 线圈|是|极低|否|需积分|高|大电流、宽带测量|
|霍尔传感器|是|低|是|中|高|双向 AC/DC 测量|
|隔离放大器 + 分流器|是|中|是|低|高|高精度功率变换器|

### 4.3 采集模型对比

|模型|CPU 占用|数据一致性|实时性|复杂度|推荐场景|
|---|---|---|---|---|---|
|业务直接轮询寄存器|中|差|差|低|仅调试|
|周期任务顺序读取|低|中|中|中|普通监控|
|锁存快照后批量读取|低|**高**|高|中|计费与三相分析|
|IRQ + 周期快照|低|高|**高**|高|工业计量|
|波形 FIFO + DMA|中|高|高|很高|电能质量分析|

---

## 5. 底层原理与功能特性深度解析

### 5.1 模拟前端与误差链

电压通道通常由高阻分压网络衰减：

VADC=VLINERLOWRHIGH+RLOWVADC​=VLINE​RHIGH​+RLOW​RLOW​​

若 `230 V RMS` 需要衰减至 `200 mV RMS`，目标比例约为：

KV=0.2230≈8.696×10−4KV​=2300.2​≈8.696×10−4

电流互感器次级与负载电阻产生采样电压：

VBURDEN=IPNPNSRBVBURDEN​=IP​NS​NP​​RB​

必须同时检查：

- 最大电压、电流时 ADC 不饱和。
- 电阻耐压、脉冲功率和爬电距离。
- CT 不进入磁饱和。
- RC 抗混叠网络的幅频和相频误差。
- 各相器件容差和温漂。
- 保护器件漏电与寄生电容。

**软件校准无法修复已经削顶、饱和或严重混叠的波形。**

### 5.2 BSP 总线抽象

```
#ifndef BSP_METER_BUS_H
#define BSP_METER_BUS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    METER_BUS_OK = 0,
    METER_BUS_E_ARG,
    METER_BUS_E_BUSY,
    METER_BUS_E_TIMEOUT,
    METER_BUS_E_IO
} meter_bus_status_t;

typedef struct {
    meter_bus_status_t (*transfer)(void *ctx,
                                   const uint8_t *tx,
                                   uint8_t *rx,
                                   size_t length,
                                   uint32_t timeout_us);
    bool (*lock)(void *ctx, uint32_t timeout_ms);
    void (*unlock)(void *ctx);
    void (*cs_assert)(void *ctx);
    void (*cs_deassert)(void *ctx);
    void (*reset_write)(void *ctx, bool asserted);
    uint64_t (*time_us)(void *ctx);
    void (*delay_us)(void *ctx, uint32_t delay_us);
    void *ctx;
} meter_bus_t;

#endif
```

驱动实例必须包含独立的总线、CS、校准参数和运行状态，禁止用全局地址支持多设备。

### 5.3 SPI 寄存器访问

计量芯片常采用 16 位寄存器。协议中的读写位、地址位宽、字节序必须严格依据目标器件定义。

以下示例使用抽象帧格式说明驱动结构，`meter_build_command()` 应按具体芯片实现：

```
typedef enum {
    METER_OK = 0,
    METER_E_ARG,
    METER_E_BUS,
    METER_E_ID,
    METER_E_TIMEOUT,
    METER_E_VERIFY,
    METER_E_RANGE,
    METER_E_STATE,
    METER_E_DATA
} meter_status_t;

static uint16_t be_u16(const uint8_t *data)
{
    return (uint16_t)(((uint16_t)data[0] << 8U) |
                      (uint16_t)data[1]);
}

static void u16_to_be(uint16_t value, uint8_t *data)
{
    data[0] = (uint8_t)(value >> 8U);
    data[1] = (uint8_t)value;
}

static uint16_t meter_build_command(uint16_t reg, bool read)
{
    const uint16_t rw = read ? 0x8000U : 0x0000U;
    return (uint16_t)(rw | (reg & 0x7FFFU));
}
```

#### 16 位读取

```
static meter_status_t meter_read_u16(const meter_bus_t *bus,
                                     uint16_t reg,
                                     uint16_t *value)
{
    uint8_t tx[4] = { 0U };
    uint8_t rx[4] = { 0U };

    if ((bus == NULL) || (value == NULL) ||
        (bus->transfer == NULL) ||
        (bus->lock == NULL) ||
        (bus->unlock == NULL) ||
        (bus->cs_assert == NULL) ||
        (bus->cs_deassert == NULL)) {
        return METER_E_ARG;
    }

    const uint16_t command = meter_build_command(reg, true);
    u16_to_be(command, &tx[0]);

    if (!bus->lock(bus->ctx, 5U)) {
        return METER_E_TIMEOUT;
    }

    bus->cs_assert(bus->ctx);
    meter_bus_status_t bus_status =
        bus->transfer(bus->ctx, tx, rx, sizeof(tx), 1000U);
    bus->cs_deassert(bus->ctx);

    bus->unlock(bus->ctx);

    if (bus_status != METER_BUS_OK) {
        return METER_E_BUS;
    }

    *value = be_u16(&rx[2]);
    return METER_OK;
}
```

#### 配置寄存器写入并回读

```
static meter_status_t meter_write_u16(const meter_bus_t *bus,
                                      uint16_t reg,
                                      uint16_t value)
{
    uint8_t tx[4];
    uint8_t rx[4] = { 0U };

    if (bus == NULL) {
        return METER_E_ARG;
    }

    u16_to_be(meter_build_command(reg, false), &tx[0]);
    u16_to_be(value, &tx[2]);

    if (!bus->lock(bus->ctx, 5U)) {
        return METER_E_TIMEOUT;
    }

    bus->cs_assert(bus->ctx);
    meter_bus_status_t status =
        bus->transfer(bus->ctx, tx, rx, sizeof(tx), 1000U);
    bus->cs_deassert(bus->ctx);

    bus->unlock(bus->ctx);

    return (status == METER_BUS_OK)
        ? METER_OK : METER_E_BUS;
}

static meter_status_t meter_write_verify(const meter_bus_t *bus,
                                         uint16_t reg,
                                         uint16_t value,
                                         uint16_t writable_mask)
{
    meter_status_t status = meter_write_u16(bus, reg, value);
    if (status != METER_OK) {
        return status;
    }

    uint16_t readback = 0U;
    status = meter_read_u16(bus, reg, &readback);

    if (status != METER_OK) {
        return status;
    }

    return (((readback ^ value) & writable_mask) == 0U)
        ? METER_OK : METER_E_VERIFY;
}
```

不能对包含自清零位、只读状态位或写一清零位的寄存器做简单全字回读比较，必须使用可写掩码。

### 5.4 有符号寄存器解析

有功功率和无功功率通常允许正反向，因此原始寄存器可能采用二补码：

```
static int16_t raw_to_i16(uint16_t raw)
{
    /*
     * uint16_t 到 int16_t 的超范围转换在 C 中属于
     * implementation-defined。通过显式二补码展开避免依赖实现。
     */
    if ((raw & 0x8000U) == 0U) {
        return (int16_t)raw;
    }

    return (int16_t)(-1 - (int32_t)(~raw & 0xFFFFU));
}
```

读取后按数据手册给出的 LSB 权重换算：

```
static int32_t scale_signed(int16_t raw,
                            int32_t numerator,
                            int32_t denominator)
{
    if (denominator <= 0) {
        return 0;
    }

    int64_t value = (int64_t)raw * numerator;

    if (value >= 0) {
        value += denominator / 2;
    } else {
        value -= denominator / 2;
    }

    return (int32_t)(value / denominator);
}
```

建议统一单位：

- 电压：`mV`
- 电流：`mA`
- 有功功率：`mW`
- 无功功率：`mvar`
- 视在功率：`mVA`
- 频率：`mHz`
- 功率因数：`ppm`，范围 `-1000000～1000000`
- 电能：`mWh` 或 `uWh`

### 5.5 驱动上下文与配置

```
typedef enum {
    METER_PHASE_A = 0,
    METER_PHASE_B,
    METER_PHASE_C,
    METER_PHASE_COUNT
} meter_phase_t;

typedef struct {
    uint32_t voltage_num;
    uint32_t voltage_den;
    uint32_t current_num;
    uint32_t current_den;
    uint32_t active_power_num;
    uint32_t active_power_den;
    uint32_t reactive_power_num;
    uint32_t reactive_power_den;
} meter_scale_t;

typedef struct {
    uint16_t voltage_gain[METER_PHASE_COUNT];
    uint16_t current_gain[METER_PHASE_COUNT];
    int16_t phase_comp[METER_PHASE_COUNT];
    uint32_t version;
    uint32_t crc32;
} meter_calibration_t;

typedef struct {
    meter_bus_t bus;
    meter_scale_t scale;
    meter_calibration_t calibration;
    uint32_t io_errors;
    uint32_t verify_errors;
    uint32_t irq_errors;
    uint32_t reset_count;
    bool initialized;
} meter_device_t;
```

### 5.6 初始化状态机

推荐启动顺序：

```
硬件复位
  -> 等待晶振与模拟前端稳定
  -> 读取芯片 ID/版本
  -> 解锁配置区
  -> 写入基础配置
  -> 写入增益、相位和阈值
  -> 写校验寄存器或配置 CRC
  -> 锁定配置区
  -> 回读关键配置
  -> 清状态和累计寄存器
  -> 启用计量与中断
  -> 读取首个有效快照
```

```
meter_status_t meter_initialize(meter_device_t *dev)
{
    if ((dev == NULL) ||
        (dev->bus.reset_write == NULL) ||
        (dev->bus.delay_us == NULL)) {
        return METER_E_ARG;
    }

    dev->initialized = false;

    dev->bus.reset_write(dev->bus.ctx, true);
    dev->bus.delay_us(dev->bus.ctx, 20U);
    dev->bus.reset_write(dev->bus.ctx, false);
    dev->bus.delay_us(dev->bus.ctx, 10000U);

    uint16_t chip_id = 0U;
    meter_status_t status =
        meter_read_u16(&dev->bus, REG_CHIP_ID, &chip_id);

    if (status != METER_OK) {
        return status;
    }
    if (chip_id != EXPECTED_CHIP_ID) {
        return METER_E_ID;
    }

    status = meter_apply_configuration(dev);
    if (status != METER_OK) {
        return status;
    }

    status = meter_verify_configuration(dev);
    if (status != METER_OK) {
        ++dev->verify_errors;
        return status;
    }

    status = meter_clear_status(dev);
    if (status != METER_OK) {
        return status;
    }

    dev->initialized = true;
    ++dev->reset_count;
    return METER_OK;
}
```

初始化失败后不得发布看似有效的零值。上层必须收到明确的 `OFFLINE` 或 `CONFIG_INVALID` 状态。

### 5.7 三相一致性快照

顺序读取多个寄存器时，A 相电压和 C 相功率可能来自不同 DSP 更新周期。解决方式按优先级排列：

1. 使用芯片的**数据锁存/快照功能**。
2. 使用数据就绪中断后在规定窗口内批量读取。
3. 使用连续读命令。
4. 无锁存能力时执行前后序列寄存器校验。
5. 无法保证一致性时明确标记为非原子快照。

```
typedef struct {
    int32_t voltage_mV[METER_PHASE_COUNT];
    int32_t current_mA[METER_PHASE_COUNT];
    int32_t active_power_mW[METER_PHASE_COUNT];
    int32_t reactive_power_mvar[METER_PHASE_COUNT];
    int32_t apparent_power_mVA[METER_PHASE_COUNT];
    int32_t power_factor_ppm[METER_PHASE_COUNT];
    uint32_t frequency_mHz;
    uint64_t timestamp_us;
    uint32_t sequence;
    uint32_t status_flags;
} meter_snapshot_t;

meter_status_t meter_read_snapshot(meter_device_t *dev,
                                   meter_snapshot_t *output)
{
    meter_snapshot_t temporary = { 0 };

    if ((dev == NULL) || (output == NULL)) {
        return METER_E_ARG;
    }
    if (!dev->initialized) {
        return METER_E_STATE;
    }

    meter_status_t status = meter_latch_measurements(dev);
    if (status != METER_OK) {
        return status;
    }

    for (size_t phase = 0U;
         phase < METER_PHASE_COUNT;
         ++phase) {
        status = meter_read_phase(dev,
                                  (meter_phase_t)phase,
                                  &temporary);
        if (status != METER_OK) {
            return status;
        }
    }

    status = meter_read_frequency(dev, &temporary.frequency_mHz);
    if (status != METER_OK) {
        return status;
    }

    temporary.timestamp_us =
        dev->bus.time_us(dev->bus.ctx);
    temporary.sequence = output->sequence + 1U;

    /*
     * 只有整个快照成功后才更新调用方对象，
     * 防止三相数据部分更新。
     */
    *output = temporary;
    return METER_OK;
}
```

### 5.8 电能累计与回绕扩展

若芯片提供 16 位或 32 位单调递增电能寄存器，MCU 可扩展为 64 位：

```
typedef struct {
    uint32_t previous_raw;
    uint64_t extended_pulses;
    bool initialized;
} energy_counter_t;

static void energy_counter_update(energy_counter_t *counter,
                                  uint32_t current_raw)
{
    if (!counter->initialized) {
        counter->previous_raw = current_raw;
        counter->initialized = true;
        return;
    }

    const uint32_t delta = current_raw - counter->previous_raw;
    counter->extended_pulses += delta;
    counter->previous_raw = current_raw;
}
```

此方法成立的前提是两次读取之间最多发生一次模数回绕。最大安全读取间隔：

Tmax<2NRpulse,maxTmax​<Rpulse,max​2N​

其中 NN 为计数器宽度，Rpulse,maxRpulse,max​ 为最大脉冲速率。

若电能常数为 `3200 imp/kWh`：

EuWh=pulse×1093200=312500×pulseEuWh​=3200pulse×109​=312500×pulse

实际芯片的寄存器单位未必等于 CF 引脚脉冲，必须区分：

- 内部电能寄存器 LSB。
- CF 输出脉冲常数。
- MCU 定时器采集的外部脉冲。
- 校准后业务电能单位。

### 5.9 中断处理

计量芯片中断可能包含：

- 电压过零。
- 失压、欠压、过压。
- 过流。
- 相序错误。
- 电能累计阈值。
- 校验错误。
- 波形缓冲就绪。
- 芯片复位或掉电。

ISR 只通知任务：

```
static TaskHandle_t meter_task_handle;
static volatile uint64_t meter_irq_timestamp_us;

void METER_IRQ_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;

    bsp_gpio_clear_irq(METER_IRQ_PIN);
    meter_irq_timestamp_us = bsp_time_us();

    vTaskNotifyGiveFromISR(
        meter_task_handle, &higher_priority_woken);

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

状态寄存器通常具有读清除或写一清零语义。驱动必须先保存完整状态，再按数据手册规定清除；错误顺序可能永久丢失事件。

### 5.10 校准参数安全存储

```
#define METER_CAL_MAGIC 0x4D43414CU

typedef struct {
    uint32_t magic;
    uint16_t schema_version;
    uint16_t payload_size;
    uint32_t generation;
    meter_calibration_t calibration;
    uint32_t crc32;
} meter_cal_record_t;

static bool calibration_record_valid(
    const meter_cal_record_t *record)
{
    if ((record == NULL) ||
        (record->magic != METER_CAL_MAGIC) ||
        (record->schema_version != 1U) ||
        (record->payload_size != sizeof(record->calibration))) {
        return false;
    }

    return crc32_compute(
        record,
        offsetof(meter_cal_record_t, crc32)) == record->crc32;
}
```

生产系统使用 A/B 双槽：

```
读取槽 A 和 B
  -> 分别校验 magic、版本、长度、CRC
  -> 选择 generation 较新的有效记录
  -> 若都无效：禁止计费或进入未校准状态
```

更新时先写非活动槽，校验成功后再切换活动代数。禁止原地覆盖唯一有效副本。

---

## 6. 性能量化分析

### 6.1 参考平台

参考测试配置：

- MCU：STM32G474，Cortex-M4F，170 MHz。
- 编译器：GCC 12.3，`-O2`。
- SPI：2 MHz，Mode 3。
- RTOS：FreeRTOS 10.5。
- 快照周期：100 ms。
- 每次快照：约 24 个 16 位寄存器。
- 测量方式：DWT 周期计数器与逻辑分析仪。
- 日志关闭，Flash 和 Cache 状态固定。

以下是该配置下的参考量，不代表所有计量芯片的保证值：

|操作|平均时间|P99|
|---|---|---|
|单个 16 位寄存器读|25 µs|31 µs|
|单个写后回读校验|53 µs|67 µs|
|24 寄存器快照|0.72 ms|0.89 ms|
|快照定点换算|8.4 µs|10.6 µs|
|IRQ ISR|0.9 µs|1.3 µs|
|CRC32 校准记录 128 B|5.1 µs|6.2 µs|
|SPI 故障超时|1.0 ms|1.1 ms|

### 6.2 SPI 线时间

假设一次寄存器访问发送 32 bit：

twire=322MHz=16μstwire​=2MHz32​=16μs

读取 24 个寄存器的理论线时间：

24×16μs=384μs24×16μs=384μs

实测高于理论值，差异来自：

- CS 建立与保持时间。
- 每次事务间隔。
- HAL 状态检查。
- RTOS 临界区和总线仲裁。
- 寄存器命令阶段与芯片内部响应要求。

若芯片支持连续读，批量读取可显著降低事务间隙。

### 6.3 CPU 和总线占用率

10 Hz 快照，每次 SPI 占用 0.72 ms：

USPI=0.72ms×10=0.72%USPI​=0.72ms×10=0.72%

每次 CPU 活跃 150 µs：

UCPU=150μs×10=0.15%UCPU​=150μs×10=0.15%

计量监控通常不是 CPU 瓶颈。主要风险是**超时、持久化、跨寄存器一致性和异常事件处理延迟**。

### 6.4 精度误差预算

整机相对误差可用 RSS 近似：

etotal≈echip2+esensor2+eresistor2+ephase2+etemp2+ecal2etotal​≈echip2​+esensor2​+eresistor2​+ephase2​+etemp2​+ecal2​​

例如：

|误差源|典型值|
|---|---|
|计量芯片|0.10%|
|CT 比差|0.20%|
|采样电阻网络|0.10%|
|相位误差折算|0.15%|
|温漂|0.10%|
|校准不确定度|0.05%|

etotal≈0.102+0.202+0.102+0.152+0.102+0.052≈0.31%etotal​≈0.102+0.202+0.102+0.152+0.102+0.052​≈0.31%

简单线性相加得到 0.70%，可作为保守最坏边界；是否可使用 RSS 取决于误差项是否独立。

### 6.5 相位误差对低功率因数的影响

真实相位差为 ϕϕ，测量链附加相位误差为 δδ：

Pmeas=VIcos⁡(ϕ+δ)Pmeas​=VIcos(ϕ+δ)

相对误差：

eP=cos⁡(ϕ+δ)−cos⁡ϕcos⁡ϕeP​=cosϕcos(ϕ+δ)−cosϕ​

当功率因数较低时，微小相位误差会导致显著有功功率误差。因此校准不能只在 `PF=1` 的阻性负载点完成，还必须覆盖感性/容性负载。

### 6.6 内存开销

|对象|典型大小|
|---|---|
|设备上下文|128～256 B|
|三相快照|128～192 B|
|校准记录|64～256 B|
|电能账本|128～512 B|
|32 项事件环形缓冲|1～4 KiB|
|计量任务栈|768～1536 B|
|波形 DMA 双缓冲|1～16 KiB|

### 6.7 优化手段与收益

|优化|参考收益|代价|
|---|---|---|
|单寄存器改连续读取|SPI 时间降低 30～60%|帧解析复杂|
|阻塞读取改 DMA|CPU 占用降低 50～90%|状态机复杂|
|1 Hz 业务读取改 10 Hz 集中快照|数据一致性提高|增加少量总线流量|
|每脉冲写 Flash 改 RAM 累计批量提交|擦写次数降低数千倍|需掉电保护|
|浮点协议值改定点整数|无 FPU MCU 快 2～10 倍|单位管理要求高|
|配置全量校验改分组 CRC|启动校验更快|依赖芯片支持|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否用于法制计量或收费结算？
├─ 是
│  ├─ 是否需要三相计量？
│  │  ├─ 是：三相专用计量芯片 + 独立校准 + 防篡改设计
│  │  └─ 否：单相计量芯片或计量 SoC
│  └─ 必须满足目标地区标准、认证和可追溯校准要求
└─ 否
   ├─ 是否需要谐波、波形或电能质量分析？
   │  ├─ 是：高性能计量 AFE + 波形 FIFO + DMA
   │  └─ 否：RMS/功率/电能型计量芯片
   ├─ 是否需要 AC/DC 双向测量？
   │  ├─ 是：分流器/霍尔 + 支持双向能量的器件
   │  └─ 否：CT 方案通常更容易隔离
   ├─ MCU 是否与市电域隔离？
   │  ├─ 是：数字隔离器 + 隔离电源
   │  └─ 否：整机接口必须按非隔离高压域处理
   └─ 是否需要高速硬件保护？
      ├─ 是：比较器/保护 IC/芯片告警引脚直接进入保护链
      └─ 否：周期计量服务可承担慢速告警
```

### 7.2 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|三相智能电表|计费、双向电能|三相计量芯片 + 独立账本|精度和认证能力强|
|智能插座|单相、小体积|单相计量芯片 + 分流器|成本低|
|工业配电监测|三相、Modbus|ATM90E32 类 + 隔离 RS-485|易于系统集成|
|光伏逆变器|双向功率、宽动态|高性能 AFE + 分流器/CT|方向与谐波要求高|
|电能质量分析|谐波、骤升骤降|ADE9000 类 + 波形 DMA|波形和事件能力强|
|充电设备|计费、漏电和安全|认证计量方案 + 独立保护|计量与安全保护分离|
|低成本家电|功率监控|计量 SoC 或单相芯片|集成度高|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **计量路径与保护路径分离**：过流短路保护不能等待 RTOS 任务。
2. **驱动不负责费率结算**：驱动只输出带时间戳和质量码的数据。
3. **所有配置必须可回读验证**。
4. **计量结果必须采用明确单位和方向约定**。
5. **三相数据应通过锁存或序列校验形成一致快照**。
6. **电能寄存器读取与清零必须形成不可分割事务**。
7. **累计电能使用至少 64 位表示**。
8. **校准参数使用版本、长度、CRC 和双副本管理**。
9. **Flash 保存必须考虑擦写寿命和掉电原子性**。
10. **设备复位后必须重新装载并校验配置**。
11. **小电流、防潜动和启动阈值应在认证要求下设定**。
12. **生产校准设备和标准源必须可追溯**。

### 8.2 选型决策矩阵

评分范围 1～5，5 为最优。

|指标|权重|专用计量芯片|MCU 软件计量|外部变送器|计量 SoC|
|---|---|---|---|---|---|
|计量精度|25%|5|3|4|4|
|认证成熟度|20%|5|2|4|4|
|算法灵活性|15%|3|5|1|3|
|开发成本|15%|4|1|5|4|
|系统集成|10%|4|3|4|5|
|波形能力|10%|3|5|1|3|
|可维护性|5%|4|2|4|3|
|综合得分|100%|**4.35**|2.85|3.45|3.85|

### 8.3 工业级编码规范

- 禁止使用无单位变量名 `voltage`、`energy`，应使用 `voltage_mV`、`energy_uWh`。
- 配置寄存器使用命名字段和掩码，不散落魔法值。
- 有符号寄存器显式执行二补码转换。
- 乘法前提升到 `int64_t` 或 `uint64_t`。
- 所有除数在配置加载时验证非零。
- CRC 未通过的校准数据不得写入芯片。
- 读取失败时不得发布部分更新快照。
- 中断状态必须先保存再清除。
- Flash 写入不得在计量高优先级路径中同步执行。
- 日志中区分原始寄存器值、物理值和校准后值。
- 错误计数应采用饱和递增或明确接受自然回绕。
- 对计费累计的任何校正必须记录审计事件。

---

## 9. 常见错误与避坑指南

### 9.1 有符号功率被当作无符号数

错误代码：

```
uint16_t raw = read_register(REG_ACTIVE_POWER_A);
uint32_t power_mW = raw * POWER_LSB_MW;
```

根因：反向功率使用二补码表示，负值被解释为大正数。

正确实现：

```
uint16_t raw = 0U;
meter_status_t status =
    meter_read_u16(&dev->bus, REG_ACTIVE_POWER_A, &raw);

if (status != METER_OK) {
    return status;
}

int16_t signed_raw = raw_to_i16(raw);
int32_t power_mW =
    scale_signed(signed_raw, POWER_NUM, POWER_DEN);
```

风险影响：光伏回馈被计为大额正向用电，累计账本严重错误。

### 9.2 多寄存器读取产生撕裂快照

错误代码：

```
read_voltage_a();
vTaskDelay(1U);
read_current_a();
read_power_a();
```

根因：各寄存器可能在不同 DSP 更新周期读取。

正确实现：

```
meter_latch_measurements(dev);
meter_read_all_measurements(dev, &temporary);
output = temporary;
```

风险影响：`P` 与 `V × I × PF` 不一致，三相不平衡分析误报。

### 9.3 每增加一个电能脉冲就写 Flash

错误代码：

```
energy_uWh += pulse_energy_uWh;
flash_write(ENERGY_ADDR, &energy_uWh, sizeof(energy_uWh));
```

根因：忽略 Flash 擦写寿命。若每秒写一次，10 万次寿命约 27.8 小时即耗尽。

正确实现：

```
energy_uWh += pulse_energy_uWh;
energy_dirty = true;

if (checkpoint_due() || power_fail_detected()) {
    energy_journal_append(&energy_uWh);
    energy_dirty = false;
}
```

风险影响：Flash 提前失效、账本损坏、设备无法升级或启动。

### 9.4 读清零电能寄存器时重试

错误代码：

```
value = read_energy_and_clear();
if (spi_error()) {
    value = read_energy_and_clear();
}
```

根因：第一次事务可能已触发清零，但响应在 SPI 侧损坏；第二次读取返回零，产生不可判定的数据丢失。

正确实现：

```
/*
 * 优先选择非破坏性累计寄存器，使用模差值。
 * 若器件只有读清零语义，应通过 CF 脉冲或备份通道兜底，
 * 并将不确定事务记录为计量完整性事件。
 */
status = read_monotonic_energy_register(&raw);
if (status == METER_OK) {
    energy_counter_update(&counter, raw);
}
```

风险影响：静默少计电能，重试无法保证幂等。

### 9.5 使用 32 位中间值导致溢出

错误代码：

```
uint32_t energy_uWh =
    pulse_count * 1000000000U / impulses_per_kWh;
```

根因：乘法在除法前溢出。

正确实现：

```
uint64_t energy_uWh =
    ((uint64_t)pulse_count * 1000000000ULL) /
    impulses_per_kWh;
```

风险影响：大累计值周期性突变或归零。

### 9.6 将软件告警当作硬件保护

错误代码：

```
if (snapshot.current_mA[0] > OVERCURRENT_MA) {
    contactor_open();
}
```

根因：周期任务、SPI 超时和 RTOS 调度不能保证短路保护所需响应时间。

正确实现：

```
void HARD_OVERCURRENT_IRQHandler(void)
{
    bsp_pwm_force_off();
    bsp_contactor_trip_request();
    protection_latch_fault_from_isr();
}
```

软件快照只用于慢速过载、记录和策略控制。快速保护应由比较器、驱动器保护输入或专用保护电路完成。

风险影响：保护延迟导致功率器件、电缆或负载损坏。

### 9.7 忽略配置寄存器异常复位

错误代码：

```
meter_initialize_once();
for (;;) {
    meter_read_snapshot();
}
```

根因：电磁干扰、欠压或看门狗可能使计量芯片复位，而 MCU 仍在运行。

正确实现：

```
if ((status_flags & METER_STATUS_RESET) != 0U ||
    !meter_configuration_signature_valid(dev)) {
    meter_mark_offline();
    (void)meter_initialize(dev);
}
```

风险影响：芯片回到默认增益和量程，读数仍变化但比例完全错误。

---

## 10. 多机制组合使用方案

### 10.1 技术协同架构

```
计量芯片 IRQ ──> ISR：时间戳 + 任务通知
                         |
100 ms 周期 ─────────────┤
                         v
                   计量服务任务
                   |-- 读取/清除 IRQ 状态
                   |-- 锁存并读取三相快照
                   |-- 单位换算与合理性校验
                   |-- 扩展电能计数器
                   |-- 更新质量状态
                   |-- 发布不可变快照
                   |
                   +--> 电能账本任务
                   |    |-- RAM 累计
                   |    |-- 周期 checkpoint
                   |    +-- 掉电紧急提交
                   |
                   +--> 告警服务
                   +--> Modbus/DL-T645
                   +--> 诊断与事件日志
```

### 10.2 服务状态和质量码

```
typedef enum {
    METER_QUALITY_VALID = 0,
    METER_QUALITY_STALE,
    METER_QUALITY_BUS_ERROR,
    METER_QUALITY_CONFIG_INVALID,
    METER_QUALITY_CALIBRATION_INVALID,
    METER_QUALITY_OUT_OF_RANGE,
    METER_QUALITY_ENERGY_UNCERTAIN,
    METER_QUALITY_OFFLINE
} meter_quality_t;

typedef struct {
    meter_snapshot_t snapshot;
    uint64_t import_energy_uWh;
    uint64_t export_energy_uWh;
    meter_quality_t quality;
    uint32_t consecutive_errors;
    uint32_t reset_count;
    uint32_t config_generation;
} meter_message_t;
```

### 10.3 RTOS 服务框架

```
typedef enum {
    METER_SERVICE_INIT = 0,
    METER_SERVICE_RUNNING,
    METER_SERVICE_RECOVERY,
    METER_SERVICE_BACKOFF
} meter_service_state_t;

typedef struct {
    meter_device_t *device;
    QueueHandle_t output_queue;
    meter_snapshot_t latest;
    energy_counter_t import_counter;
    energy_counter_t export_counter;
    meter_service_state_t state;
    TickType_t next_sample;
    TickType_t retry_deadline;
    uint32_t sequence;
    uint32_t consecutive_errors;
} meter_service_t;

static bool tick_reached(TickType_t now, TickType_t deadline)
{
    return (BaseType_t)(now - deadline) >= 0;
}

static void meter_publish(meter_service_t *service,
                          meter_quality_t quality)
{
    meter_message_t message = {
        .snapshot = service->latest,
        .import_energy_uWh =
            pulses_to_uWh(service->import_counter.extended_pulses),
        .export_energy_uWh =
            pulses_to_uWh(service->export_counter.extended_pulses),
        .quality = quality,
        .consecutive_errors = service->consecutive_errors,
        .reset_count = service->device->reset_count,
        .config_generation =
            service->device->calibration.version
    };

    (void)xQueueOverwrite(service->output_queue, &message);
}

static void meter_service_task(void *argument)
{
    meter_service_t *service = (meter_service_t *)argument;
    service->state = METER_SERVICE_INIT;

    for (;;) {
        TickType_t now = xTaskGetTickCount();

        switch (service->state) {
        case METER_SERVICE_INIT:
            if (meter_initialize(service->device) == METER_OK) {
                service->consecutive_errors = 0U;
                service->next_sample = now;
                service->state = METER_SERVICE_RUNNING;
            } else {
                service->retry_deadline =
                    now + pdMS_TO_TICKS(1000U);
                service->state = METER_SERVICE_BACKOFF;
                meter_publish(service, METER_QUALITY_OFFLINE);
            }
            break;

        case METER_SERVICE_RUNNING:
            if (!tick_reached(now, service->next_sample)) {
                vTaskDelay(service->next_sample - now);
                break;
            }

            if (meter_read_snapshot(service->device,
                                    &service->latest) == METER_OK) {
                service->consecutive_errors = 0U;
                meter_update_energy(service);
                meter_publish(service, METER_QUALITY_VALID);
                service->next_sample += pdMS_TO_TICKS(100U);
            } else {
                ++service->consecutive_errors;
                meter_publish(service, METER_QUALITY_BUS_ERROR);

                if (service->consecutive_errors >= 3U) {
                    service->state = METER_SERVICE_RECOVERY;
                } else {
                    service->next_sample =
                        now + pdMS_TO_TICKS(100U);
                }
            }
            break;

        case METER_SERVICE_RECOVERY:
            service->device->initialized = false;
            service->state = METER_SERVICE_INIT;
            break;

        case METER_SERVICE_BACKOFF:
            if (tick_reached(now, service->retry_deadline)) {
                service->state = METER_SERVICE_INIT;
            } else {
                vTaskDelay(service->retry_deadline - now);
            }
            break;

        default:
            service->state = METER_SERVICE_INIT;
            break;
        }
    }
}
```

该框架仍需结合项目补充：

- 中断事件队列。
- 可取消的 SPI DMA。
- 指数退避。
- 配置命令队列。
- 掉电通知。
- 电能账本事务。
- 时钟同步与费率边界处理。

---

## 11. 工业级实际案例分析

### 11.1 三相工业配电监测终端

#### 需求

- 三相四线 `230/400 V`。
- 额定电流 `100 A`。
- 每 100 ms 更新瞬时量。
- 每秒更新累计电能。
- 通过隔离 RS-485 发布 Modbus 数据。
- 配置异常时禁止上报有效计量值。

#### 架构设计

```
三相电压网络 + 3×CT
          |
     ATM90E32AS
          |
       SPI + IRQ
          |
     计量服务任务
      |        |
  快照缓存   电能账本
      |        |
    Modbus   FRAM/Flash
```

#### 核心代码：一致快照发布

```
typedef struct {
    meter_message_t slots[2];
    _Atomic uint32_t active;
} meter_snapshot_store_t;

static meter_snapshot_store_t meter_store;

void meter_store_publish(const meter_message_t *source)
{
    uint32_t current =
        atomic_load_explicit(&meter_store.active,
                             memory_order_relaxed);
    uint32_t next = (current ^ 1U) & 1U;

    meter_store.slots[next] = *source;

    atomic_store_explicit(&meter_store.active,
                          next,
                          memory_order_release);
}

meter_message_t meter_store_read(void)
{
    meter_message_t copy;
    uint32_t before;
    uint32_t after;

    do {
        before = atomic_load_explicit(
            &meter_store.active, memory_order_acquire);
        copy = meter_store.slots[before & 1U];
        after = atomic_load_explicit(
            &meter_store.active, memory_order_acquire);
    } while (before != after);

    return copy;
}
```

#### 设计要点

- Modbus 读取不得直接触发 SPI。
- 多寄存器响应来自同一快照，避免主机读到一半更新。
- 三相功率和总功率必须使用同一时间基准。
- CT 相序、极性和安装方向必须在生产测试中验证。
- 失相、反向接线和电压不平衡应形成独立事件。

### 11.2 光伏双向能量管理设备

#### 需求

- 支持正向购电与反向上网。
- 功率因数可能为正或负。
- 掉电时最多允许损失 `1 Wh` 尚未持久化数据。
- 需要分时费率边界准确切换。

#### 电能账本

```
typedef struct {
    uint64_t import_uWh;
    uint64_t export_uWh;
    uint64_t tariff_uWh[4];
    uint32_t generation;
    uint64_t timestamp_s;
    uint32_t crc32;
} energy_ledger_t;

void ledger_apply_delta(energy_ledger_t *ledger,
                        int64_t active_energy_delta_uWh,
                        uint8_t tariff)
{
    if ((ledger == NULL) || (tariff >= 4U)) {
        return;
    }

    if (active_energy_delta_uWh >= 0) {
        uint64_t delta =
            (uint64_t)active_energy_delta_uWh;
        ledger->import_uWh += delta;
        ledger->tariff_uWh[tariff] += delta;
    } else {
        uint64_t delta =
            (uint64_t)(-(active_energy_delta_uWh + 1LL)) + 1ULL;
        ledger->export_uWh += delta;
    }
}
```

#### 设计要点

- 正反向能量使用独立单调累计量。
- 费率切换时先结算旧费率区间，再切换活动费率。
- RTC 回拨不得导致电能重复结算。
- 掉电检测中断只设置紧急保存请求；持久化必须在储能保持时间内完成。
- 账本使用 journal 或 FRAM，避免反复擦写单一 Flash 页。

### 11.3 智能断路器

#### 需求

- RMS 和电能用于监控。
- 短路保护响应小于 `100 µs`。
- 过载保护按热模型执行。
- 计量芯片故障不得阻止硬件脱扣。

#### 架构

```
电流采样
  |----------------> 高速比较器 -> 锁存器 -> 栅极/脱扣保护
  |
  +----------------> 计量芯片 -> MCU -> RMS/电能/热模型
```

#### 热模型示意

θk+1=θk+Δt(KIRMS2−θkτ)θk+1​=θk​+Δt(KIRMS2​−τθk​​)

```
void thermal_model_update(thermal_model_t *model,
                          uint32_t current_mA,
                          uint32_t dt_ms)
{
    uint64_t current_sq =
        (uint64_t)current_mA * current_mA;

    int64_t heating =
        (int64_t)((current_sq * model->heating_gain_q24) >> 24U);

    int64_t cooling =
        model->temperature_state / model->cooling_tau_ms;

    model->temperature_state +=
        (heating - cooling) * (int64_t)dt_ms;
}
```

#### 设计要点

- 快速短路保护完全硬件化。
- MCU 热模型只承担过载保护和诊断。
- 计量数据过期时进入保守保护策略。
- 脱扣事件保存原始电流、RMS、时间戳、质量码和硬件状态。

---

## 12. 高频问题深度答疑

### 12.1 为什么不能只读取电压、电流后由 MCU 计算功率？

`Vrms × Irms` 得到的是视在功率，不是有功功率：

S=VRMSIRMSS=VRMS​IRMS​P=1T∫0Tv(t)i(t)dtP=T1​∫0T​v(t)i(t)dt

在感性、容性或非线性负载下两者差异显著。正确有功功率需要同步瞬时采样并积分，或直接读取计量芯片的有功功率结果。

### 12.2 为什么 PF=1 校准通过，低 PF 仍可能超差？

阻性负载下电压与电流几乎同相，采样链的微小相位误差影响有限。低 PF 时真实相位接近 90°，相位偏差会引起很大的相对有功功率误差，因此必须增加感性和容性校准点。

### 12.3 电能应该读取累计寄存器还是统计 CF 脉冲？

优先级取决于器件特性：

- 累计寄存器读取方便，但要处理回绕、读清零和通信不确定性。
- CF 脉冲可独立校验计量链，但 MCU 复位和脉冲丢失需要处理。
- 高可靠系统可同时使用寄存器和 CF 脉冲进行交叉诊断。

两者不应在未确认比例关系时混合累计。

### 12.4 为什么计量值正确，长期电能仍偏差？

瞬时功率误差会随时间积分；另外还有：

- 定时读取时漏算增量。
- 寄存器回绕未处理。
- 读清零事务失败。
- MCU 复位后基准丢失。
- Flash checkpoint 间隔过长。
- 费率边界处理重复或遗漏。
- 整数截断造成小增量持续丢失。

电能换算应保存余数，避免每次整数除法截断：

```
accumulator_numerator += pulse_delta * ENERGY_NUMERATOR;
energy_uWh += accumulator_numerator / ENERGY_DENOMINATOR;
accumulator_numerator %= ENERGY_DENOMINATOR;
```

### 12.5 SPI CRC 是否能够解决所有计量完整性问题？

不能。CRC 可检测传输错误，但不能检测：

- 配置比例错误。
- CT 反接。
- 模拟输入饱和。
- 校准数据错误但 CRC 正确。
- 芯片内部算法状态异常。
- 多寄存器快照撕裂。

还需要配置回读、范围检查、功率一致性检查、状态位和参考通道。

### 12.6 掉电时应该立即写 Flash 吗？

只有在电源保持时间、Flash 最坏编程时间和中断优先级均经过量化后才可行。更可靠的方案包括：

- FRAM/MRAM。
- 周期 journal，限制最大未提交增量。
- Backup SRAM + 超级电容。
- 芯片内部非易失累计能力。
- 掉电检测提前触发并禁止启动新的高耗能操作。

### 12.7 如何判断计量芯片发生静默复位？

不能只依赖一个复位状态位。工业现场可能出现：

- 芯片复位状态位被读清。
- MCU 与计量芯片不同步启动。
- SPI 某次事务失败但芯片仍正常工作。
- 芯片配置寄存器恢复默认值。
- DSP 计量状态重新开始累加。
- 电源瞬态导致模拟部分或数字部分局部复位。

推荐采用多证据联合诊断：

```
周期读取状态寄存器
        |
        +--> 复位标志置位？
        |
        +--> 配置签名异常？
        |
        +--> 关键寄存器回读异常？
        |
        +--> 电能计数器序列异常？
        |
        +--> IRQ行为和数据更新异常？
        |
        v
累计诊断证据
        |
        +--> 单项异常：配置重读或快速确认
        |
        +--> 多项异常：判定芯片复位/失配
        |
        +--> 确认后：停止发布有效计量值
                       |
                       v
                 重新初始化和校准验证
```

#### 配置签名

```
typedef struct {
    uint16_t register_address;
    uint16_t expected_value;
    uint16_t writable_mask;
} meter_config_signature_item_t;

static const meter_config_signature_item_t config_signature[] = {
    { REG_CONFIG_A, EXPECTED_CONFIG_A, CONFIG_A_MASK },
    { REG_CONFIG_B, EXPECTED_CONFIG_B, CONFIG_B_MASK },
    { REG_CONFIG_C, EXPECTED_CONFIG_C, CONFIG_C_MASK }
};

static meter_status_t meter_check_configuration(
    meter_device_t *dev, bool *valid)
{
    if ((dev == NULL) || (valid == NULL)) {
        return METER_E_ARG;
    }

    *valid = true;

    for (size_t i = 0U;
         i < sizeof(config_signature) /
             sizeof(config_signature[0]);
         ++i) {
        uint16_t actual = 0U;

        meter_status_t status = meter_read_u16(
            &dev->bus,
            config_signature[i].register_address,
            &actual);

        if (status != METER_OK) {
            return status;
        }

        const uint16_t mask =
            config_signature[i].writable_mask;

        if ((actual & mask) !=
            (config_signature[i].expected_value & mask)) {
            *valid = false;
            return METER_OK;
        }
    }

    return METER_OK;
}
```

#### 诊断状态机

```
typedef enum {
    METER_DIAG_NORMAL = 0,
    METER_DIAG_SUSPECTED_RESET,
    METER_DIAG_REINITIALIZING,
    METER_DIAG_OFFLINE
} meter_diag_state_t;

typedef struct {
    meter_diag_state_t state;
    uint8_t abnormal_checks;
    uint32_t reset_events;
    uint32_t config_mismatches;
    uint32_t status_read_errors;
} meter_diagnostic_t;

static bool meter_reset_evidence(
    meter_device_t *dev,
    meter_diagnostic_t *diag)
{
    uint16_t status = 0U;
    bool config_valid = false;
    bool abnormal = false;

    if (meter_read_u16(&dev->bus,
                       REG_STATUS,
                       &status) != METER_OK) {
        ++diag->status_read_errors;
        return true;
    }

    if ((status & STATUS_RESET_FLAG) != 0U) {
        ++diag->reset_events;
        abnormal = true;
    }

    if (meter_check_configuration(dev,
                                   &config_valid) != METER_OK) {
        return true;
    }

    if (!config_valid) {
        ++diag->config_mismatches;
        abnormal = true;
    }

    return abnormal;
}
```

工程上应避免“发现一次异常就立即清账”。正确做法是：

1. 暂停对外发布有效计量数据。
2. 保存异常前后的状态、配置和时间戳。
3. 尝试重新初始化。
4. 回读配置并进行有效测量验证。
5. 明确记录恢复期间的电能完整性状态。
6. 恢复成功后再重新进入 `VALID` 状态。

**关键结论：配置签名 + 复位标志 + 数据连续性 + 状态寄存器**联合判断，比单独读取复位位可靠得多。

---

### 12.8 计量芯片读数与外部参考表不一致，应该先查什么？

应按“方向性、比例性、工况相关性”分层排查。

```
误差是否在所有电流点近似固定比例？
├─ 是：检查增益、CT变比、电阻比例和单位换算
└─ 否
   ├─ 小电流误差明显？
   │  ├─ 是：检查零点、启动阈值、噪声和抗混叠
   │  └─ 否
   ├─ 低功率因数误差明显？
   │  ├─ 是：检查相位补偿和通道延迟
   │  └─ 否
   ├─ 大电流误差明显？
   │  ├─ 是：检查 CT 饱和、ADC 削顶和前端线性
   │  └─ 否
   ├─ 温度变化时误差变化？
   │  ├─ 是：检查电阻、CT、芯片和校准参数温漂
   │  └─ 否
   └─ 仅某一相异常？
      ├─ 是：检查相序、极性、通道配置和焊接
      └─ 否：检查系统参考源、时钟和统一配置
```

必须同时记录：

- 线电压和线电流。
- 功率因数及超前/滞后方向。
- 有功、无功、视在功率。
- 芯片原始寄存器值。
- 校准后值。
- 参考表值。
- 温度。
- 当前增益和相位配置。

不能只比较最终的 `kWh`，因为累计误差无法定位具体原因。

---

### 12.9 为什么电能计量需要区分进口和出口？

对于储能、光伏逆变器和双向变流器，瞬时有功功率可能正负变化：

P>0⇒进口或负载消耗P>0⇒进口或负载消耗P<0⇒出口或回馈P<0⇒出口或回馈

直接累加带符号功率会导致净电能，而不是分别统计的进口、出口电能。

```
typedef struct {
    uint64_t import_uWh;
    uint64_t export_uWh;
    uint64_t remainder;
} bidirectional_energy_t;

void energy_integrate(bidirectional_energy_t *energy,
                      int32_t power_mW,
                      uint32_t interval_ms)
{
    if (energy == NULL) {
        return;
    }

    const int64_t numerator =
        (int64_t)power_mW * interval_ms;

    if (numerator >= 0) {
        energy->import_uWh +=
            (uint64_t)numerator / 3600LL;
    } else {
        energy->export_uWh +=
            (uint64_t)(-numerator) / 3600LL;
    }
}
```

生产实现必须保存除法余数，否则低功率下每次截断都会造成系统性少计。更准确的实现是以统一分子单位保存余数：

```
typedef struct {
    uint64_t import_numerator;
    uint64_t export_numerator;
    uint64_t import_uWh;
    uint64_t export_uWh;
} energy_integrator_t;

void energy_integrate_precise(energy_integrator_t *energy,
                              int32_t power_mW,
                              uint32_t interval_ms)
{
    if ((energy == NULL) || (interval_ms == 0U)) {
        return;
    }

    const uint64_t magnitude =
        (power_mW >= 0)
        ? (uint64_t)power_mW
        : (uint64_t)(-(int64_t)power_mW);

    const uint64_t increment =
        magnitude * interval_ms;

    if (power_mW >= 0) {
        energy->import_numerator += increment;
        energy->import_uWh +=
            energy->import_numerator / 3600ULL;
        energy->import_numerator %= 3600ULL;
    } else {
        energy->export_numerator += increment;
        energy->export_uWh +=
            energy->export_numerator / 3600ULL;
        energy->export_numerator %= 3600ULL;
    }
}
```

这里：

mW×ms=μWh×3.6mW×ms=μWh×3.6

如果采用 `mW × ms / 3600`，应确认单位换算定义。工程中必须将单位换算写入测试，不能凭变量名猜测。

---

### 12.10 计量芯片是否应该直接输出浮点值？

驱动层通常不建议直接输出 `float`，原因包括：

- 无 FPU 的 MCU 上计算代价较高。
- 不同编译器的浮点 ABI 可能影响接口。
- 通信协议中浮点表示不利于兼容和审计。
- 计费累计需要可重复、可追溯的整数计算。
- 浮点 NaN、无穷大和舍入行为容易污染业务逻辑。

推荐输出带单位的定点整数：

```
typedef struct {
    int32_t voltage_mV;
    int32_t current_mA;
    int32_t active_power_mW;
    int32_t reactive_power_mvar;
    uint32_t frequency_mHz;
    int32_t power_factor_ppm;
} meter_physical_values_t;
```

浮点只适合：

- 上位机显示。
- 离线分析。
- 校准拟合。
- 不参与关键累计和保护决策的算法。

---

### 12.11 如何处理无功功率和功率因数符号？

必须在系统级文档中定义：

- 正功率方向。
- 正无功方向。
- 感性负载和容性负载对应的符号。
- 相电压和相电流的参考方向。
- CT 极性和电压通道极性。

不同芯片和电能表对符号约定可能不同，不能直接将寄存器符号映射成业务语义。

```
typedef enum {
    POWER_DIRECTION_IMPORT = 0,
    POWER_DIRECTION_EXPORT
} power_direction_t;

typedef enum {
    REACTIVE_DIRECTION_INDUCTIVE = 0,
    REACTIVE_DIRECTION_CAPACITIVE
} reactive_direction_t;

typedef struct {
    int32_t active_power_mW;
    int32_t reactive_power_mvar;
    power_direction_t active_direction;
    reactive_direction_t reactive_direction;
} signed_power_result_t;
```

生产校准至少应使用：

- 阻性负载：验证有功正方向。
- 感性负载：验证无功符号。
- 容性负载：验证相反无功符号。
- 反接 CT：验证反向有功。
- 三相负载：验证相序和各相符号。

---

### 12.12 如何确定计量服务的采样周期？

采样周期应由业务带宽和控制响应时间决定，而不是越快越好。

|业务|推荐周期|原因|
|---|---|---|
|电能累计|100 ms～1 s|重点是积分连续性|
|面板显示|500 ms～2 s|人眼不需要高频更新|
|过载监控|10～100 ms|需较快发现趋势|
|功率质量分析|依据窗口|通常按整周波或固定窗|
|硬件短路保护|微秒级|不应依赖计量服务|
|Modbus 轮询|按主站周期|使用最新一致快照|

应使用绝对时间调度：

```
TickType_t next_deadline = xTaskGetTickCount();
const TickType_t period = pdMS_TO_TICKS(100U);

for (;;) {
    next_deadline += period;

    meter_read_and_publish();

    vTaskDelayUntil(&next_deadline, period);
}
```

若读取耗时偶尔超过周期，应检测超时并上报，而不是悄悄产生周期漂移。

---

## 13. 课程核心总结

### 核心要点

- 电能计量 BSP 不只是 SPI 读写，还包括**模拟前端约束、配置验证、快照一致性、电能累计和掉电完整性**。
- 有功功率必须基于同步电压电流乘积或计量芯片内部 DSP 结果，不能用 `Vrms × Irms` 替代。
- 正负功率方向、无功符号和 CT 极性必须在系统文档与校准流程中明确。
- 配置寄存器必须回读验证，计量芯片复位必须通过多证据联合判断。
- 电能累计要处理回绕、读清零不幂等、整数截断和掉电保存。
- 硬件快速保护必须与计量软件解耦。
- 法制计量项目必须建立可追溯的标准源、校准参数和审计记录。

### 性能排序

- 访问效率：**连续批量读取 > DMA 单事务 > 阻塞单寄存器读取**。
- 数据一致性：**硬件锁存快照 > 中断窗口批量读取 > 顺序读取**。
- 电能累计可靠性：**非破坏性单调寄存器 > CF 脉冲与寄存器交叉校验 > 读清零寄存器单独使用**。
- 掉电可靠性：**FRAM/MRAM > journal Flash > 单槽 Flash 原地更新**。
- 保护响应：**硬件比较器/保护链 > 专用保护 IC > MCU 中断 > RTOS 周期任务**。

### 通用选型结论

- 三相普通监测：专用三相计量芯片 + SPI + 一致快照。
- 高精度电能质量：高性能 AFE + 波形 FIFO + DMA。
- 单相低成本产品：单相计量芯片或集成计量 SoC。
- 双向能量系统：支持正负功率与进口/出口独立累计的器件和账本。
- 法制计量：优先选择已有参考设计、校准工具链和认证资料的方案。
- 快速保护：独立硬件实现，计量芯片只提供监测和记录。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐方案|关键机制|
|---|---|---|
|单相功率监控|单相计量芯片 + SPI/I²C|RMS、功率、频率、CRC|
|三相配电监测|三相计量芯片 + SPI|锁存快照、相序和失相诊断|
|法制电能计量|专用计量芯片 + 标准校准源|可追溯校准、参数审计、掉电账本|
|光伏/储能|双向计量芯片 + 进口/出口账本|正负功率、能量方向、回馈统计|
|电能质量分析|高性能 AFE + 波形 FIFO|谐波、波形、事件捕获|
|低成本家电|计量 SoC 或单相芯片|低 BOM、有限诊断|
|工业长线监测|RS-485/Modbus 变送器|隔离、CRC、抗干扰|
|智能断路器|计量芯片 + 独立硬件保护|监测与保护分离|

### 14.2 接口与采集方式对比

|方式|典型速率|CPU 占用|一致性|推荐用途|
|---|---|---|---|---|
|I²C 单寄存器轮询|100～400 kHz|中|低|低速调试|
|SPI 单寄存器读取|1～10 MHz|中|中|普通监控|
|SPI 连续读取|1～10 MHz|低|高|周期快照|
|SPI + DMA|2～20 MHz|低|高|RTOS 计量服务|
|IRQ + 锁存快照|依芯片|低|**最高**|三相计量|
|波形 FIFO + DMA|依芯片|中|高|电能质量分析|

### 14.3 核心数据单位

|数据|推荐单位|常见符号|
|---|---|---|
|电压|`mV`|`int32_t`|
|电流|`mA`|`int32_t`|
|有功功率|`mW`|`int32_t`|
|无功功率|`mvar`|`int32_t`|
|视在功率|`mVA`|`uint32_t`|
|频率|`mHz`|`uint32_t`|
|功率因数|`ppm`|`int32_t`|
|电能|`uWh` 或 `mWh`|`uint64_t`|
|时间戳|`us`|`uint64_t`|

### 14.4 初始化检查表

```
[ ] 高压和隔离设计已通过硬件评审
[ ] 电压、电流采样前端未饱和
[ ] CT 极性和变比已确认
[ ] 芯片复位具备超时
[ ] 晶振/模拟前端稳定时间已满足
[ ] WHO_AM_I 或芯片版本已验证
[ ] SPI 模式和时钟已通过波形验证
[ ] 关键配置寄存器已写入
[ ] 配置寄存器已回读
[ ] 校准参数版本和 CRC 已验证
[ ] 状态寄存器已清理
[ ] 电能寄存器初始值已建立基线
[ ] 首个快照已通过范围检查
[ ] 计量芯片中断已正确配置
[ ] 复位后能够重新装载配置
```

### 14.5 快照有效性检查

```
[ ] SPI 事务成功
[ ] 三相数据来自同一锁存窗口
[ ] 电压未超出有效范围
[ ] 电流未饱和
[ ] 有功功率符号符合约定
[ ] 视在功率不小于有功功率绝对值
[ ] PF 位于 [-1, 1] 对应范围
[ ] 频率位于设定电网范围
[ ] 数据时间戳新鲜
[ ] 序列号无异常跳变
[ ] 芯片状态无复位或配置异常
[ ] 校准参数有效
```

### 14.6 电能累计检查

|检查项|推荐实现|
|---|---|
|计数宽度|64 位扩展|
|回绕处理|无符号模差值|
|整数截断|保存除法余数|
|正反向能量|分开累计|
|读清零寄存器|避免重试造成丢账|
|Flash 保存|周期 journal 或 FRAM|
|掉电保护|提前检测 + 储能预算|
|恢复校验|账本 CRC + generation|
|费率切换|先结算旧费率区间|
|时间回拨|禁止重复结算|

### 14.7 故障处理表

|故障|诊断依据|推荐动作|
|---|---|---|
|SPI NACK/错误|总线返回码|释放总线、有限重试|
|WHO_AM_I 错误|芯片 ID 不匹配|停止配置，检查硬件|
|配置被修改|回读签名不一致|停止发布，重新初始化|
|芯片静默复位|复位位、签名、数据连续性|重新装载配置并验证|
|三相数据撕裂|快照序列不一致|使用锁存或重读|
|CT 饱和|波形削顶、RMS异常|标记失真，不进行普通校准|
|电能寄存器回绕|原始值下降但未复位|使用模差扩展|
|电能读清零失败|事务结果不确定|标记 `ENERGY_UNCERTAIN`|
|Flash 参数无效|magic/版本/CRC错误|使用安全默认值并禁止计费|
|过流|硬件比较器/保护链|立即脱扣，软件记录|
|频率异常|过零/频率寄存器越界|标记电网异常|
|低功率因数超差|PF 工况下误差增大|重新进行相位校准|

---

## 15. 学习效果自检

- 能否清楚区分 BSP、计量芯片驱动、校准层和电能账本的职责？
- 能否解释为什么 `Vrms × Irms` 不是有功功率？
- 能否正确解析有功功率的正负方向？
- 能否说明 CT 极性对功率符号的影响？
- 能否设计三相一致性快照？
- 能否根据 SPI 时钟和寄存器数量计算总线占用率？
- 能否避免在读清零寄存器失败后盲目重试？
- 能否使用 64 位处理长期电能累计？
- 能否处理电能计数器回绕？
- 能否解释低功率因数下相位误差为何被放大？
- 能否设计校准参数 A/B 双副本和 CRC 验证？
- 能否联合多个证据识别计量芯片静默复位？
- 能否说明为什么软件计量告警不能替代硬件短路保护？
- 能否区分瞬时量有效、累计量可信和计费数据完整？
- 能否通过故障注入验证 NACK、配置丢失、掉电和读清零异常？
- 能否建立覆盖电流、功率因数、温度和频率的校准测试矩阵？

---

## 16. 实践与进阶路径

### 16.1 基础实战：完成单相计量芯片驱动

实现：

1. SPI/I²C 总线适配层。
2. 芯片复位和 ID 检测。
3. 配置寄存器写入与回读。
4. 电压、电流、功率和频率读取。
5. 有符号功率解析。
6. 原始值到物理值的定点换算。
7. 芯片状态寄存器读取。
8. 统一错误码和故障计数。

验收指标：

- 连续运行 24 h 无死锁。
- 配置修改后回读一致。
- 功率方向与 CT 极性符合文档约定。
- 读取错误时不发布半更新数据。
- 所有事务具备超时边界。

### 16.2 中级实战：构建 RTOS 计量服务

实现：

1. 由单一计量任务执行周期采样。
2. 使用硬件 IRQ 或定时任务触发数据锁存。
3. 构建三相一致快照。
4. 通过队列发布不可变计量消息。
5. 增加样本时间戳、序列号和质量码。
6. 实现电能进口/出口分离累计。
7. 实现配置异常检测和自动恢复。
8. 通过静态对象创建任务、队列和事件组。

验收指标：

- 计量任务不阻塞保护任务。
- 三相数据来自同一采样窗口。
- 低优先级通信任务不会拖延计量快照。
- 连续 72 h 无账本回绕和内存增长。
- 传感器离线时进入退避，不形成忙循环。

### 16.3 高级实战：完成多点计量校准系统

建立至少以下测试点：

|测试维度|建议点位|
|---|---|
|电流|额定值的 1%、5%、20%、50%、100%、120%|
|电压|额定值的 80%、100%、120%|
|功率因数|1.0、0.5 感性、0.5 容性|
|方向|正向、反向|
|频率|45、50、60、65 Hz|
|温度|低温、常温、高温|
|相数|单相、三相平衡、三相不平衡|
|负载|阻性、感性、容性、非线性|

校准流程：

```
标准源输出稳定
  -> 读取芯片原始值
  -> 计算增益误差和相位误差
  -> 拟合校准参数
  -> 写入芯片/参数存储
  -> 回读并校验
  -> 多点复测
  -> 生成校准报告
  -> 固化参数版本和审计信息
```

### 16.4 故障注入实战

至少注入：

- SPI 时钟错误。
- SPI 事务超时。
- 芯片复位。
- 配置寄存器被篡改。
- 电能寄存器回绕。
- 读清零事务响应丢失。
- 电压通道削顶。
- CT 极性反接。
- 单相失压。
- 三相不平衡。
- Flash 校准参数损坏。
- 掉电发生在账本提交中间。

验收要求：

- 无效数据不得进入计费链路。
- 计量芯片恢复后必须重新验证配置。
- 掉电恢复后账本不重复、不回退。
- 所有不确定状态都必须通过质量码或事件记录暴露。

### 16.5 性能测试方法

必须测量：

- 单寄存器读取时间。
- 全量快照时间。
- 三相快照最坏延迟。
- SPI 总线占用率。
- IRQ 到任务唤醒延迟。
- 配置回读时间。
- 芯片复位恢复时间。
- 电能累计误差。
- Flash/FRAM 提交时间。
- 掉电检测到账本提交完成时间。
- 计量任务对保护和通信任务的调度影响。

建议使用：

- DWT `CYCCNT`。
- SPI 片选、IRQ 和 GPIO 调试脉冲。
- 逻辑分析仪。
- 标准功率源。
- 高精度参考电能表。
- 温湿度箱或温度循环箱。
- 可编程交流源和电子负载。
- 功率因数可调负载。
- 断电注入和继电器切换装置。

### 16.6 进阶学习方向

- 深入学习 IEC 62052、IEC 62053、IEC 61557 等相关标准的适用边界。
- 研究 ADE、ATM90E、STPM 和其他计量芯片的寄存器模型差异。
- 研究低功率因数、谐波、非正弦电流下的计量误差。
- 建立电压、电流、相位和温度的多维校准模型。
- 研究电能质量指标：THD、骤升、骤降、闪变和频率偏差。
- 研究计量数据防篡改、参数签名和安全启动协同。
- 将 SPI 同步驱动升级为异步 DMA 事务管理器。
- 设计带审计日志的费率和电能账本系统。
- 使用 HIL 平台验证芯片复位、掉电、过流和电网异常。
- 对法制计量产品建立从原理图、PCB、固件、校准到生产测试的完整可追溯链路。