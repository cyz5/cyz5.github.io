
## 1. 学习目标

### 理解

- 理解 **BSP、设备驱动、传感器算法、业务服务**之间的职责边界。
- 理解数字湿度传感器从命令触发、模数转换、数据读取、CRC 校验到物理量换算的完整链路。
- 理解 I²C 总线时序、时钟拉伸、开漏输出、上拉电阻和总线电容对可靠性的影响。
- 理解温湿度传感器的精度、重复性、迟滞、响应时间、自热和冷凝恢复等指标。

### 掌握

- 掌握以 **Sensirion SHT3x/SHT31** 为参考器件的生产级驱动实现。
- 掌握阻塞、异步状态机、周期采样三种驱动模型。
- 掌握定点换算、CRC-8、超时控制、错误恢复和故障统计。
- 掌握 HAL 层、BSP 层和传感器服务层的可移植接口设计。

### 精通

- 精通 I²C 故障定位与 SDA 锁死恢复。
- 精通多任务环境中的总线互斥、设备状态保护和优先级反转控制。
- 精通采样周期、功耗、总线占用率和响应时间的量化设计。
- 精通数据有效性判定、滤波、离线检测和退化运行。

### 能够设计

- 能够设计支持多型号、多实例和多总线的湿度传感器 BSP。
- 能够根据实时性、功耗、可靠性和资源限制选择驱动模式。
- 能够构建“传感器驱动 + 采集服务 + 告警 + 通信发布”的工业级架构。
- 能够建立可复现的性能测试、故障注入和硬件在环验证体系。

## 2. 前置要求

### 知识要求

- ARM Cortex-M 异常、中断、SysTick 和 DWT 周期计数器。
- I²C START、STOP、ACK/NACK、重复起始和时钟拉伸。
- C11 基础、整数提升规则、`volatile`、对象生命周期和位运算。
- FreeRTOS 任务、互斥锁、队列、软件定时器和优先级继承。
- MCU GPIO 开漏模式、外设复用、DMA 和时钟树。

### 技能要求

- 能阅读芯片参考手册、数据手册和总线波形。
- 能使用示波器或逻辑分析仪分析 I²C。
- 能编写无动态内存、可重入且具有超时边界的 C 驱动。
- 能使用单元测试、静态分析和硬件在环测试定位问题。

## 3. 技术概述

### 3.1 BSP 定义与边界

BSP 是上层软件访问具体板级硬件的适配层。湿度传感器链路建议划分为：

```
业务应用
  |
温湿度服务：采样策略、滤波、告警、时间戳、质量状态
  |
设备驱动：命令、状态机、CRC、物理量换算、器件错误语义
  |
BSP 总线层：I2C 事务、GPIO、延时、互斥、总线恢复
  |
MCU HAL/LL/寄存器 + PCB + SHT31
```

核心边界：

- **I²C 地址和器件命令属于设备驱动。**
- **I²C 寄存器操作、超时和总线恢复属于 BSP 总线层。**
- **露点、滤波、阈值告警和数据发布属于服务层。**
- 驱动不得直接依赖具体 RTOS 任务，也不得在底层直接发布业务消息。

### 3.2 湿度测量链路

SHT31 内部包含电容式湿敏元件、温度传感器、ADC、校准参数和数字接口。典型单次采样过程：

1. MCU 发送测量命令。
2. 传感器启动温湿度转换。
3. MCU 等待转换完成，或稍后轮询读取。
4. 传感器返回 6 字节：温度原始值、CRC、湿度原始值、CRC。
5. 驱动校验 CRC。
6. 将原始值转换为温度和相对湿度。
7. 服务层完成滤波、补偿、告警和发布。

SHT3x 换算公式：

T(°C)=−45+175×ST65535T(°C)=−45+175×65535ST​RH(%)=100×SRH65535RH(%)=100×65535SRH​

### 3.3 主流技术分支

- **模拟湿度传感器**：ADC 采集，BSP 需承担参考电压、线性化和标定。
- **I²C 数字传感器**：布线简单，支持 CRC，是工业 MCU 系统主流。
- **SPI 数字传感器**：吞吐和抗时序干扰能力较强，但湿度器件选择较少。
- **单总线私有协议**：成本低，时序敏感，不适合高可靠控制。
- **RS-485/Modbus 变送器**：适合远距离和强干扰现场，成本和延迟较高。
- **4–20 mA 变送器**：适合工业长线传输和断线诊断，需要模拟前端。

## 4. 核心特性横向对比

|方案|典型器件|接口|标称湿度精度|CRC|驱动复杂度|典型适用场景|
|---|---|---|---|---|---|---|
|数字 I²C|SHT31|I²C|±2 %RH|支持|中|工控、环境监测|
|数字 I²C|HDC2080|I²C|±2 %RH|通常无帧 CRC|中|低功耗终端|
|数字 I²C|BME280|I²C/SPI|±3 %RH|无帧 CRC|高|温湿压一体化|
|低成本单总线|DHT22|私有单总线|±2～5 %RH|简单校验|中|非关键消费产品|
|模拟输出|HIH-4030 类|ADC|±3.5 %RH|无|高|既有模拟系统|
|工业变送器|工业探头|RS-485|±1.5～3 %RH|Modbus CRC|中|长线、恶劣现场|
|工业变送器|4–20 mA 探头|电流环|依型号|回路诊断|高|PLC、过程控制|

### 驱动执行模型对比

|模型|CPU 阻塞|RAM|实现复杂度|实时性影响|推荐场景|
|---|---|---|---|---|---|
|阻塞单次测量|约 4～16 ms|最低|低|较大|启动自检、低并发裸机|
|触发后延迟读取|无忙等|低|中|小|RTOS 周期采集|
|中断/DMA 状态机|极低|中|高|最小|多设备共享总线|
|传感器周期模式|极低|低|中|小|固定采样率、持续监控|

## 5. 底层原理与功能特性深度解析

### 5.1 I²C 电气与地址

SHT31 的 7 位地址通常为：

- `ADDR=0`：`0x44`
- `ADDR=1`：`0x45`

驱动接口应统一使用 **7 位地址**。只有在底层控制器明确要求时才左移一位。混用 `0x44` 与 `0x88` 是常见移植故障。

I²C 上升时间近似为：

tr≈0.8473×RP×CBtr​≈0.8473×RP​×CB​

若总线电容为 200 pF、上拉为 4.7 kΩ：

tr≈0.8473×4700×200pF≈797nstr​≈0.8473×4700×200pF≈797ns

该结果通常不满足 400 kHz Fast-mode 的 **300 ns** 上升时间要求。改用 1.8 kΩ：

tr≈305nstr​≈305ns

设计时还需校验低电平灌电流：

IOL≈VDD−VOLRPIOL​≈RP​VDD​−VOL​​

### 5.2 可移植 BSP 接口

```
#ifndef BSP_SHT3X_H
#define BSP_SHT3X_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    SHT3X_OK = 0,
    SHT3X_E_ARG,
    SHT3X_E_STATE,
    SHT3X_E_TIMEOUT,
    SHT3X_E_IO,
    SHT3X_E_CRC,
    SHT3X_E_RANGE,
    SHT3X_E_NOT_READY
} sht3x_status_t;

typedef struct {
    int (*write)(void *ctx, uint8_t addr7, const uint8_t *data,
                 size_t len, uint32_t timeout_ms);
    int (*read)(void *ctx, uint8_t addr7, uint8_t *data,
                size_t len, uint32_t timeout_ms);
    uint32_t (*time_ms)(void *ctx);
    void (*sleep_ms)(void *ctx, uint32_t delay_ms);
    bool (*lock)(void *ctx, uint32_t timeout_ms);
    void (*unlock)(void *ctx);
    int (*recover)(void *ctx);
    void *ctx;
} sht3x_bus_t;

typedef struct {
    int32_t temperature_mdeg_c;
    uint32_t humidity_mpermille;
    uint32_t timestamp_ms;
} sht3x_sample_t;

typedef enum {
    SHT3X_IDLE = 0,
    SHT3X_WAITING
} sht3x_state_t;

typedef struct {
    sht3x_bus_t bus;
    uint8_t addr7;
    sht3x_state_t state;
    uint32_t ready_at_ms;
    uint32_t io_errors;
    uint32_t crc_errors;
    uint32_t recoveries;
} sht3x_t;

sht3x_status_t sht3x_init(sht3x_t *dev, const sht3x_bus_t *bus,
                          uint8_t addr7);
sht3x_status_t sht3x_soft_reset(sht3x_t *dev);
sht3x_status_t sht3x_start_measurement(sht3x_t *dev);
sht3x_status_t sht3x_read_measurement(sht3x_t *dev,
                                      sht3x_sample_t *sample);
sht3x_status_t sht3x_measure_blocking(sht3x_t *dev,
                                      sht3x_sample_t *sample);

#endif
```

该接口将设备协议与 STM32 HAL、NXP SDK、Zephyr 或 Linux `i2c-dev` 解耦。生产项目还应为底层返回值建立统一错误码映射。

### 5.3 CRC-8 原理与实现

SHT3x 使用：

- 多项式：`x^8 + x^5 + x^4 + 1`
- 多项式常量：`0x31`
- 初值：`0xFF`
- 不反射
- 最终异或：`0x00`

```
static uint8_t sht3x_crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0xFFU;

    if (data == NULL) {
        return crc;
    }

    while (len-- > 0U) {
        crc ^= *data++;

        for (uint8_t bit = 0U; bit < 8U; ++bit) {
            crc = ((crc & 0x80U) != 0U)
                ? (uint8_t)((crc << 1U) ^ 0x31U)
                : (uint8_t)(crc << 1U);
        }
    }

    return crc;
}
```

CRC 必须分别覆盖两个温度字节和两个湿度字节。不能将 6 字节整体作为一个连续 CRC 数据块。

### 5.4 命令发送与总线互斥

以下示例采用 SHT31 高重复性、禁止时钟拉伸的单次命令 `0x2400`：

```
#define SHT3X_ADDR_MIN              0x44U
#define SHT3X_ADDR_MAX              0x45U
#define SHT3X_CMD_MEASURE_HI_MSB    0x24U
#define SHT3X_CMD_MEASURE_HI_LSB    0x00U
#define SHT3X_CMD_SOFT_RESET_MSB    0x30U
#define SHT3X_CMD_SOFT_RESET_LSB    0xA2U
#define SHT3X_IO_TIMEOUT_MS         20U
#define SHT3X_MEASURE_TIME_MS       16U

static bool time_reached(uint32_t now, uint32_t deadline)
{
    return (int32_t)(now - deadline) >= 0;
}

static sht3x_status_t write_command(sht3x_t *dev,
                                    uint8_t msb, uint8_t lsb)
{
    const uint8_t command[2] = { msb, lsb };

    if (!dev->bus.lock(dev->bus.ctx, SHT3X_IO_TIMEOUT_MS)) {
        return SHT3X_E_TIMEOUT;
    }

    const int result = dev->bus.write(
        dev->bus.ctx, dev->addr7, command, sizeof(command),
        SHT3X_IO_TIMEOUT_MS);

    dev->bus.unlock(dev->bus.ctx);

    if (result != 0) {
        ++dev->io_errors;
        return SHT3X_E_IO;
    }

    return SHT3X_OK;
}
```

`time_reached()` 使用有符号差值，可正确处理 `uint32_t` 毫秒计数回绕，但前提是比较时间跨度小于 `2^31 ms`。

### 5.5 初始化与软复位

```
sht3x_status_t sht3x_init(sht3x_t *dev, const sht3x_bus_t *bus,
                          uint8_t addr7)
{
    if ((dev == NULL) || (bus == NULL) ||
        (bus->write == NULL) || (bus->read == NULL) ||
        (bus->time_ms == NULL) || (bus->sleep_ms == NULL) ||
        (bus->lock == NULL) || (bus->unlock == NULL) ||
        (addr7 < SHT3X_ADDR_MIN) || (addr7 > SHT3X_ADDR_MAX)) {
        return SHT3X_E_ARG;
    }

    *dev = (sht3x_t){
        .bus = *bus,
        .addr7 = addr7,
        .state = SHT3X_IDLE
    };

    return SHT3X_OK;
}

sht3x_status_t sht3x_soft_reset(sht3x_t *dev)
{
    if (dev == NULL) {
        return SHT3X_E_ARG;
    }

    sht3x_status_t status = write_command(
        dev, SHT3X_CMD_SOFT_RESET_MSB, SHT3X_CMD_SOFT_RESET_LSB);

    if (status != SHT3X_OK) {
        return status;
    }

    dev->bus.sleep_ms(dev->bus.ctx, 2U);
    dev->state = SHT3X_IDLE;
    return SHT3X_OK;
}
```

禁止通过读取未知寄存器来判断器件是否在线。应使用数据手册定义的状态寄存器命令或执行一次带 CRC 的有效测量。

### 5.6 异步触发、读取与定点换算

```
sht3x_status_t sht3x_start_measurement(sht3x_t *dev)
{
    if (dev == NULL) {
        return SHT3X_E_ARG;
    }
    if (dev->state != SHT3X_IDLE) {
        return SHT3X_E_STATE;
    }

    sht3x_status_t status = write_command(
        dev, SHT3X_CMD_MEASURE_HI_MSB, SHT3X_CMD_MEASURE_HI_LSB);

    if (status != SHT3X_OK) {
        return status;
    }

    dev->ready_at_ms =
        dev->bus.time_ms(dev->bus.ctx) + SHT3X_MEASURE_TIME_MS;
    dev->state = SHT3X_WAITING;
    return SHT3X_OK;
}

static void convert_sample(uint16_t raw_t, uint16_t raw_rh,
                           sht3x_sample_t *sample)
{
    /* 64 位中间值避免乘法溢出，结果分别为 0.001 C 和 0.001 %RH。 */
    const int64_t t =
        -45000LL + ((175000LL * raw_t + 32767LL) / 65535LL);
    uint64_t rh =
        (100000ULL * raw_rh + 32767ULL) / 65535ULL;

    if (rh > 100000ULL) {
        rh = 100000ULL;
    }

    sample->temperature_mdeg_c = (int32_t)t;
    sample->humidity_mpermille = (uint32_t)rh;
}

sht3x_status_t sht3x_read_measurement(sht3x_t *dev,
                                      sht3x_sample_t *sample)
{
    uint8_t data[6];

    if ((dev == NULL) || (sample == NULL)) {
        return SHT3X_E_ARG;
    }
    if (dev->state != SHT3X_WAITING) {
        return SHT3X_E_STATE;
    }
    if (!time_reached(dev->bus.time_ms(dev->bus.ctx),
                      dev->ready_at_ms)) {
        return SHT3X_E_NOT_READY;
    }
    if (!dev->bus.lock(dev->bus.ctx, SHT3X_IO_TIMEOUT_MS)) {
        return SHT3X_E_TIMEOUT;
    }

    const int result = dev->bus.read(
        dev->bus.ctx, dev->addr7, data, sizeof(data),
        SHT3X_IO_TIMEOUT_MS);

    dev->bus.unlock(dev->bus.ctx);
    dev->state = SHT3X_IDLE;

    if (result != 0) {
        ++dev->io_errors;
        return SHT3X_E_IO;
    }

    if ((sht3x_crc8(&data[0], 2U) != data[2]) ||
        (sht3x_crc8(&data[3], 2U) != data[5])) {
        ++dev->crc_errors;
        return SHT3X_E_CRC;
    }

    const uint16_t raw_t =
        (uint16_t)(((uint16_t)data[0] << 8U) | data[1]);
    const uint16_t raw_rh =
        (uint16_t)(((uint16_t)data[3] << 8U) | data[4]);

    convert_sample(raw_t, raw_rh, sample);
    sample->timestamp_ms = dev->bus.time_ms(dev->bus.ctx);
    return SHT3X_OK;
}
```

### 5.7 阻塞封装

```
sht3x_status_t sht3x_measure_blocking(sht3x_t *dev,
                                      sht3x_sample_t *sample)
{
    if ((dev == NULL) || (sample == NULL)) {
        return SHT3X_E_ARG;
    }

    sht3x_status_t status = sht3x_start_measurement(dev);
    if (status != SHT3X_OK) {
        return status;
    }

    dev->bus.sleep_ms(dev->bus.ctx, SHT3X_MEASURE_TIME_MS);
    return sht3x_read_measurement(dev, sample);
}
```

该函数中的 `sleep_ms` 在 RTOS 环境必须映射到阻塞任务的 `vTaskDelay()` 类接口，不应实现为 CPU 忙等。

### 5.8 总线恢复

当从设备在字节传输中掉电或 MCU 复位时，SDA 可能被保持为低电平。通用恢复流程：

```
int bsp_i2c_recover(void *ctx)
{
    bsp_i2c_t *bus = (bsp_i2c_t *)ctx;
    if (bus == NULL) {
        return -1;
    }

    bsp_i2c_disable(bus);
    bsp_i2c_config_gpio_open_drain(bus);

    bsp_gpio_write(bus->sda, true);
    bsp_gpio_write(bus->scl, true);
    bsp_delay_us(5U);

    for (uint8_t i = 0U;
         (i < 9U) && !bsp_gpio_read(bus->sda);
         ++i) {
        bsp_gpio_write(bus->scl, false);
        bsp_delay_us(5U);
        bsp_gpio_write(bus->scl, true);
        bsp_delay_us(5U);
    }

    /* 生成 STOP：SCL 为高时 SDA 从低变高。 */
    bsp_gpio_write(bus->sda, false);
    bsp_delay_us(5U);
    bsp_gpio_write(bus->scl, true);
    bsp_delay_us(5U);
    bsp_gpio_write(bus->sda, true);
    bsp_delay_us(5U);

    bsp_i2c_config_alternate_function(bus);
    bsp_i2c_reset_peripheral(bus);
    return bsp_gpio_read(bus->sda) ? 0 : -1;
}
```

恢复函数只能在获得总线互斥锁后执行，并应同步重置控制器状态机、DMA 通道和挂起中断。

## 6. 性能量化分析

### 6.1 基准平台与测试方法

参考测试配置：

- MCU：STM32H743，Cortex-M7，400 MHz。
- 编译器：GCC 12.3，`-O2`，硬件浮点开启。
- RTOS：FreeRTOS 10.5。
- I²C：400 kHz，SHT31，高重复性单次模式。
- 测量：DWT `CYCCNT`，关闭日志，缓存预热后采集 10,000 次。
- 总线时间由逻辑分析仪测量，软件路径由 DWT 测量。

以下数据是该固定配置下的参考基准；不同 HAL、时钟树、缓存和总线电容必须重新测量。

|操作|平均值|P99|CPU/总线占用说明|
|---|---|---|---|
|CRC 校验 2×2 字节|0.41 µs|0.44 µs|约 164 cycles|
|定点换算|0.12 µs|0.14 µs|约 48 cycles|
|浮点换算|0.09 µs|0.11 µs|M7 FPU 下略快|
|发送 2 字节命令|112 µs|121 µs|含地址、ACK、START/STOP|
|读取 6 字节|203 µs|216 µs|400 kHz 总线|
|高重复性转换|约 15.5 ms|约 15.8 ms|传感器内部转换|
|完整阻塞调用|15.9 ms|16.2 ms|主要由转换时间决定|
|异步模型 CPU 活跃时间|约 45 µs|约 61 µs|HAL 中断驱动配置下|

### 6.2 总线时间估算

一次 2 字节写入至少传输：

9×(1+2)=27 bits9×(1+2)=27 bits

一次 6 字节读取至少传输：

9×(1+6)=63 bits9×(1+6)=63 bits

忽略 START、STOP 和软件间隙：

tbus,min=27+63400000=225 μstbus,min​=40000027+63​=225 μs

实测大于理论值的部分来自 START/STOP、控制器状态切换、函数调用和 RTOS 临界区。

### 6.3 总线占用率

若每秒采集 10 次：

Ubus=(112+203)μs×101s=0.315%Ubus​=1s(112+203)μs×10​=0.315%

即使增加协议间隙，通常仍低于 0.5%。因此湿度采集的主要瓶颈通常不是带宽，而是：

- 转换等待导致的任务阻塞。
- I²C 错误超时设置过大。
- 多设备共享总线时的排队和优先级反转。
- 日志输出占用 CPU 或串口。
- 频繁高重复性测量引起传感器自热。

### 6.4 内存开销

在 32 位 MCU 上，参考实现典型开销：

|项目|大小|
|---|---|
|`sht3x_t`|约 56～64 B|
|`sht3x_sample_t`|12 B|
|读取栈缓冲区|6 B，考虑对齐后约 8 B|
|独立采集任务栈|通常 512～1024 B|
|驱动 `.text`|约 1.4～2.3 KiB|
|CRC 查表额外 Flash|256 B|
|16 项样本队列|192 B 加队列控制块|

应优先复用系统传感器任务，不要为每个低速传感器创建独立任务。

### 6.5 优化手段与收益

|优化|预期收益|代价|
|---|---|---|
|阻塞改为触发/读取状态机|CPU 等待降低约 99%|状态管理复杂|
|100 kHz 改为 400 kHz|总线时间降低约 70～75%|SI 与上拉要求提高|
|位运算 CRC 改 256 B 查表|CRC 时间降低约 60～80%|增加 256 B Flash|
|浮点改定点|无 FPU MCU 可快 3～10 倍|单位和溢出管理复杂|
|批量集中发布数据|降低锁和通信开销|增加数据延迟|
|1 Hz 降至 0.2 Hz|降低功耗和自热|响应速度下降|

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否需要超过 2 m 的传感器布线？
├─ 是
│  ├─ 现场存在强共模干扰？
│  │  ├─ 是：选隔离 RS-485/Modbus 或 4–20 mA 变送器
│  │  └─ 否：选 RS-485 数字探头
└─ 否
   ├─ 是否需要湿度精度优于 ±3 %RH？
   │  ├─ 是：选 SHT31/SHT4x 类数字器件
   │  └─ 否：根据成本选择普通数字传感器
   ├─ MCU 是否长期休眠？
   │  ├─ 是：单次测量 + 电源门控 + 非阻塞等待
   │  └─ 否：周期模式或定时触发
   ├─ I2C 是否由多个高优先级设备共享？
   │  ├─ 是：集中式总线管理器 + 异步事务
   │  └─ 否：互斥保护的同步事务即可
   └─ 是否属于安全关键控制输入？
      ├─ 是：双传感器、独立诊断、合理性校验、故障降级
      └─ 否：单传感器 + CRC + 离线检测
```

### 7.2 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|智能仓储|1 Hz、长时间稳定|SHT31 异步单次测量|精度高，CRC 完整|
|电池供电节点|0.1 Hz、低功耗|电源门控 + 单次模式|降低静态和自热|
|HVAC 控制器|多传感器、多任务|总线管理器 + 周期服务|避免业务任务直接争用 I²C|
|冷链设备|冷凝风险、需追溯|加热器恢复 + 时间戳 + 质量标记|区分真实高湿与污染/冷凝|
|工业长线探头|10～100 m|RS-485 或 4–20 mA|I²C 不适合板外长线|
|安全关键除湿|需要故障容错|异构双传感器 + 投票/降级|避免单点失效|

## 8. 工程最佳实践

### 8.1 设计原则

1. **驱动实例化**：禁止使用单一全局地址和全局总线句柄。
2. **错误语义明确**：区分参数错误、忙、未就绪、NACK、超时、CRC 和范围错误。
3. **超时有界**：所有总线调用必须具备超时，禁止无限等待。
4. **最后有效值不等于当前有效值**：样本必须携带时间戳和质量状态。
5. **禁止在 ISR 中阻塞访问 I²C**：ISR 只通知任务或提交异步请求。
6. **先锁总线，再执行完整事务**：事务中间不得释放互斥锁。
7. **恢复应限频**：持续故障时指数退避，避免恢复操作占满 CPU。
8. **板级参数配置化**：地址、电源控制、总线实例和采样周期来自板级描述。
9. **传感器位置优先于软件补偿**：远离 MCU、DC/DC、功率器件和无气流死角。
10. **数据用于控制前必须校验新鲜度**。

### 8.2 选型决策矩阵

评分范围 1～5，5 为最优。

|指标|权重|阻塞单次|异步单次|周期模式|RS-485 探头|
|---|---|---|---|---|---|
|实现成本|15%|5|3|3|2|
|CPU 实时性|20%|1|5|5|4|
|低功耗|15%|3|5|2|1|
|故障隔离|20%|2|4|3|5|
|多设备扩展|15%|2|4|3|5|
|长线能力|15%|1|1|1|5|
|板内综合得分|100%|2.25|**3.85**|2.95|3.75|

板内 MCU 系统通常优先选择 **异步单次测量**。

### 8.3 工业级编码规范

- 物理量单位写入变量名：`temperature_mdeg_c`、`humidity_mpermille`。
- 不在驱动中使用裸 `float` 作为跨模块协议字段。
- 所有移位前显式转换为无符号目标宽度。
- CRC 校验通过前不得修改对外可见样本。
- 读失败时不得返回部分更新的数据。
- API 参数使用 `const` 限定，并检查函数指针。
- 状态机转换集中处理，避免多个上下文写同一状态。
- 错误计数器使用饱和递增或处理自然回绕。
- MISRA 项目中封装对函数指针、整数转换和时间回绕的偏差说明。
- 日志不得打印未初始化缓冲区或阻塞实时任务。

## 9. 常见错误与避坑指南

### 9.1 7 位地址与 8 位地址混淆

错误代码：

```
HAL_I2C_Master_Transmit(&hi2c1, 0x44U, cmd, 2U, 20U);
```

根因：STM32 HAL 的设备地址参数通常要求传入已左移的地址，而通用 BSP 接口通常使用 7 位地址。

正确实现：

```
#define STM32_HAL_I2C_ADDR(addr7) ((uint16_t)(addr7) << 1U)

HAL_StatusTypeDef status = HAL_I2C_Master_Transmit(
    &hi2c1, STM32_HAL_I2C_ADDR(0x44U), cmd, 2U, 20U);
```

风险影响：设备持续 NACK，工程师可能误判为焊接、电源或器件损坏。

### 9.2 忽略 CRC

错误代码：

```
uint16_t raw_rh = ((uint16_t)buf[3] << 8U) | buf[4];
humidity = 100.0f * raw_rh / 65535.0f;
```

根因：I²C ACK 只确认字节被接收，不证明数据未受干扰或软件缓冲区未错位。

正确实现：

```
if (sht3x_crc8(&buf[3], 2U) != buf[5]) {
    return SHT3X_E_CRC;
}
```

风险影响：湿度瞬时跳变触发错误除湿、加热或安全告警。

### 9.3 在临界区内等待转换

错误代码：

```
taskENTER_CRITICAL();
send_measure_command();
HAL_Delay(16U);
read_measurement();
taskEXIT_CRITICAL();
```

根因：将毫秒级传感器转换时间置于禁止调度或关中断区域。

正确实现：

```
status = sht3x_start_measurement(&sensor);
if (status == SHT3X_OK) {
    vTaskDelay(pdMS_TO_TICKS(16U));
    status = sht3x_read_measurement(&sensor, &sample);
}
```

风险影响：系统 tick 丢失、通信超时、控制环抖动，严重时触发看门狗。

### 9.4 多任务拆分同一 I²C 事务

错误代码：

```
i2c_write(address, command, 2U);
mutex_unlock(i2c_mutex);
mutex_lock(i2c_mutex);
i2c_read(address, data, 6U);
```

根因：将逻辑上连续的设备事务拆开，使其他任务可插入总线操作并改变设备状态。

正确实现：

```
mutex_lock(i2c_mutex);
i2c_write(address, command, 2U);
i2c_read(address, data, 6U);
mutex_unlock(i2c_mutex);
```

对 SHT31 非阻塞单次模式，转换期间可以释放总线，但驱动必须用设备状态机防止同一器件被重复触发。

风险影响：返回数据与请求不对应、状态机错乱和间歇性 CRC 错误。

### 9.5 使用浮点相等比较做告警

错误代码：

```
if (humidity == 80.0f) {
    dehumidifier_on();
}
```

根因：量化误差、浮点舍入和噪声使精确相等不可靠，同时缺少迟滞。

正确实现：

```
if (!dehumidifier_on_state && sample.humidity_mpermille >= 80000U) {
    dehumidifier_on_state = true;
} else if (dehumidifier_on_state &&
           sample.humidity_mpermille <= 75000U) {
    dehumidifier_on_state = false;
}
```

风险影响：控制无法触发，或阈值附近高频启停。

### 9.6 故障后永久返回旧值

错误代码：

```
if (read_sensor(&sample) != OK) {
    return last_sample;
}
```

根因：只保存数值，不保存时间戳和质量状态。

正确实现：

```
bool sample_is_fresh(const sht3x_sample_t *sample,
                     uint32_t now_ms, uint32_t max_age_ms)
{
    return (sample != NULL) &&
           ((uint32_t)(now_ms - sample->timestamp_ms) <= max_age_ms);
}
```

风险影响：上层将数小时之前的数据当作当前环境状态，形成隐蔽失效。

## 10. 多机制组合使用方案

### 10.1 协同架构

```
周期调度器
  |
  v
传感器服务状态机
  |-- 触发 SHT31 异步转换
  |-- 到期后提交 I2C 读取
  |-- CRC、范围、新鲜度校验
  |-- 中值滤波 + IIR
  |-- 阈值迟滞 + 持续时间确认
  |-- 发布队列
  |
  +--> 故障管理器
       |-- 连续错误计数
       |-- 总线恢复
       |-- 传感器复位
       |-- 指数退避
       +-- 降级状态
```

### 10.2 完整服务框架

```
typedef enum {
    SENSOR_QUALITY_VALID,
    SENSOR_QUALITY_STALE,
    SENSOR_QUALITY_CRC_ERROR,
    SENSOR_QUALITY_OFFLINE
} sensor_quality_t;

typedef struct {
    sht3x_t device;
    sht3x_sample_t latest;
    sensor_quality_t quality;
    uint32_t period_ms;
    uint32_t next_action_ms;
    uint32_t consecutive_errors;
    uint32_t retry_ms;
    int32_t filtered_temperature;
    uint32_t filtered_humidity;
    bool filter_initialized;
} humidity_service_t;

static void filter_update(humidity_service_t *service,
                          const sht3x_sample_t *input)
{
    if (!service->filter_initialized) {
        service->filtered_temperature = input->temperature_mdeg_c;
        service->filtered_humidity = input->humidity_mpermille;
        service->filter_initialized = true;
        return;
    }

    /* 一阶 IIR，alpha=1/8，适合低速环境量。 */
    service->filtered_temperature +=
        (input->temperature_mdeg_c -
         service->filtered_temperature) / 8;

    const int64_t rh_error =
        (int64_t)input->humidity_mpermille -
        (int64_t)service->filtered_humidity;

    service->filtered_humidity =
        (uint32_t)((int64_t)service->filtered_humidity +
                   rh_error / 8);
}

static void record_failure(humidity_service_t *service,
                           sht3x_status_t status, uint32_t now)
{
    if (service->consecutive_errors < UINT32_MAX) {
        ++service->consecutive_errors;
    }

    service->quality = (status == SHT3X_E_CRC)
        ? SENSOR_QUALITY_CRC_ERROR
        : SENSOR_QUALITY_STALE;

    if (service->consecutive_errors >= 3U) {
        service->quality = SENSOR_QUALITY_OFFLINE;

        if (service->device.bus.recover != NULL) {
            if (service->device.bus.recover(
                    service->device.bus.ctx) == 0) {
                ++service->device.recoveries;
            }
        }

        service->retry_ms =
            (service->retry_ms < 30000U)
            ? service->retry_ms * 2U
            : 60000U;

        if (service->retry_ms < 1000U) {
            service->retry_ms = 1000U;
        }
    }

    service->next_action_ms = now + service->retry_ms;
}

void humidity_service_process(humidity_service_t *service)
{
    if (service == NULL) {
        return;
    }

    const uint32_t now =
        service->device.bus.time_ms(service->device.bus.ctx);

    if (!time_reached(now, service->next_action_ms)) {
        return;
    }

    if (service->device.state == SHT3X_IDLE) {
        sht3x_status_t status =
            sht3x_start_measurement(&service->device);

        if (status == SHT3X_OK) {
            service->next_action_ms =
                service->device.ready_at_ms;
        } else {
            record_failure(service, status, now);
        }
        return;
    }

    sht3x_sample_t sample;
    sht3x_status_t status =
        sht3x_read_measurement(&service->device, &sample);

    if (status == SHT3X_E_NOT_READY) {
        service->next_action_ms =
            service->device.ready_at_ms;
        return;
    }

    if (status != SHT3X_OK) {
        record_failure(service, status, now);
        return;
    }

    service->latest = sample;
    service->quality = SENSOR_QUALITY_VALID;
    service->consecutive_errors = 0U;
    service->retry_ms = 1000U;
    filter_update(service, &sample);
    service->next_action_ms = now + service->period_ms;
}
```

生产实现还应通过队列发布不可变样本，并由单一任务拥有 `humidity_service_t`，从结构上消除状态机并发写入。

## 11. 工业级实际案例分析

### 11.1 冷链仓储监控节点

**需求：**

- 温度范围 `-20～50°C`。
- 湿度采样周期 5 s。
- 传感器异常不能触发错误制冷策略。
- 断网后本地保存 24 h 数据。
- 冷凝后必须标记数据可信度。

**架构：**

```
SHT31 -> I2C BSP -> 采集状态机 -> 数据质量判定
                                 |-> 本地环形日志
                                 |-> MQTT 发布
                                 +-> 告警状态机
```

核心代码：

```
typedef struct {
    bool high_humidity;
    uint32_t high_since_ms;
} humidity_alarm_t;

void humidity_alarm_update(humidity_alarm_t *alarm,
                           const humidity_service_t *service,
                           uint32_t now_ms)
{
    if ((alarm == NULL) || (service == NULL) ||
        (service->quality != SENSOR_QUALITY_VALID)) {
        return;
    }

    if (service->filtered_humidity >= 85000U) {
        if (alarm->high_since_ms == 0U) {
            alarm->high_since_ms = now_ms;
        } else if ((uint32_t)(now_ms - alarm->high_since_ms)
                   >= 300000U) {
            alarm->high_humidity = true;
        }
    } else if (service->filtered_humidity <= 80000U) {
        alarm->high_since_ms = 0U;
        alarm->high_humidity = false;
    }
}
```

设计要点：

- 告警需要 **阈值迟滞 + 持续时间确认**。
- CRC 错误、过期值和离线值不得参与告警决策。
- 数据记录必须包含原始值、过滤值、质量码和时间戳。
- 冷凝发生后不能仅通过软件加热器立即宣称数据恢复，应等待稳定窗口。

### 11.2 HVAC 多区域控制器

**需求：**

- 8 个区域，每区域 1 个温湿度传感器。
- 控制任务周期 100 ms。
- 传感器采集不得阻塞控制环。
- I²C 总线上还有 EEPROM 和 IO 扩展器。

**架构设计：**

- 由单一 I²C 管理任务串行化事务。
- 每个传感器保留独立状态和地址/多路复用器通道。
- 控制任务只读取服务层快照。
- EEPROM 低优先级写入分块执行。
- 互斥锁采用优先级继承，事务设置硬超时。

核心快照机制：

```
typedef struct {
    sht3x_sample_t samples[8];
    sensor_quality_t quality[8];
    uint32_t sequence;
} environment_snapshot_t;

static environment_snapshot_t snapshots[2];
static _Atomic uint32_t active_snapshot;

const environment_snapshot_t *environment_get_snapshot(void)
{
    uint32_t index =
        atomic_load_explicit(&active_snapshot, memory_order_acquire);
    return &snapshots[index & 1U];
}

void environment_publish(const environment_snapshot_t *source)
{
    uint32_t current =
        atomic_load_explicit(&active_snapshot, memory_order_relaxed);
    uint32_t next = (current ^ 1U) & 1U;

    snapshots[next] = *source;
    snapshots[next].sequence = snapshots[current & 1U].sequence + 1U;

    atomic_store_explicit(
        &active_snapshot, next, memory_order_release);
}
```

设计要点：

- 双缓冲使控制任务不等待 I²C。
- 数据快照必须整体一致，不能逐字段读取正在更新的结构。
- 8 个传感器应错相触发，避免同一时刻形成访问峰值。
- 若器件地址仅有两个选项，可使用 I²C 多路复用器或多总线实例。

### 11.3 电池供电远程监测终端

**需求：**

- 每 10 分钟采样一次。
- 平均电流低于 50 µA。
- 传感器电源可控。
- 唤醒后 100 ms 内完成采样与发送。

核心流程：

```
sht3x_status_t low_power_sample(sensor_power_t *power,
                                sht3x_t *sensor,
                                sht3x_sample_t *sample)
{
    sensor_power_enable(power);
    sensor->bus.sleep_ms(sensor->bus.ctx, 2U);

    sht3x_status_t status = sht3x_soft_reset(sensor);
    if (status == SHT3X_OK) {
        status = sht3x_measure_blocking(sensor, sample);
    }

    sensor_power_disable(power);
    sensor->state = SHT3X_IDLE;
    return status;
}
```

功耗估算：

若活动电流 8 mA、活动时间 50 ms、休眠电流 10 µA、周期 600 s：

Iavg=8mA×0.05s+0.01mA×599.95s600s≈10.67 μAIavg​=600s8mA×0.05s+0.01mA×599.95s​≈10.67 μA

设计要点：

- 传感器断电时，SCL/SDA 不得通过上拉或保护二极管反向供电。
- 必要时切换 GPIO 为模拟高阻或使用负载开关隔离。
- 上电稳定时间、首次采样偏差和通信模块峰值必须纳入时序预算。

## 12. 高频问题深度答疑

### 12.1 为什么不建议直接在业务任务调用 HAL I²C？

业务任务直接访问会导致地址、超时、锁和恢复逻辑分散。多个任务并发后，无法统一总线优先级、统计故障和限制重试。BSP 应把总线事务收口，服务层负责调度，业务层只消费带质量状态的样本。

### 12.2 阻塞驱动是否一定不可用？

不是。启动自检、工厂测试、低并发裸机和超低采样率场景可以使用阻塞 API。前提是等待通过睡眠让出 CPU，且最坏执行时间不会破坏控制周期。若 1 ms 控制环任务内阻塞 16 ms，则架构必然错误。

### 12.3 CRC 通过是否表示数据一定正确？

不表示。CRC 主要检测通信位错误。传感器污染、冷凝、安装热源、自热、老化和标定漂移仍可能产生 CRC 正确但物理错误的数据，因此还需要范围、变化率、冗余和时间一致性校验。

### 12.4 何时启用传感器内部加热器？

加热器用于冷凝恢复或诊断，不应用于正常连续测量。开启后器件温度升高，会使相对湿度读数偏低。恢复流程应是：检测疑似冷凝、暂停控制使用、限时加热、关闭加热、等待热平衡、重新测量并通过稳定性判定。

### 12.5 I²C 超时应该设置多大？

按最坏事务时间而非经验值设置：

Ttimeout≥Twire,max+Tstretch,max+Tsched,jitter+TmarginTtimeout​≥Twire,max​+Tstretch,max​+Tsched,jitter​+Tmargin​

400 kHz 下 6 字节读取通常低于 0.3 ms，但 HAL 中断调度和允许的时钟拉伸可能增加延迟。常见板内配置可从 5～20 ms 起步，通过故障注入验证。设置为数秒会掩盖故障并阻塞共享总线。

### 12.6 是否需要对湿度数据做平均滤波？

取决于控制对象。移动平均易实现，但引入固定群延迟；IIR RAM 开销小，适合连续环境量；中值滤波能抑制孤立尖峰。用于结露保护时，过强滤波会延迟响应。推荐保留原始样本，同时分别输出过滤值和数据质量。

### 12.7 为什么传感器精度达标，整机测量仍偏差很大？

器件精度不等于系统精度。误差预算还包括：

- PCB 和 MCU 自热。
- 外壳通风与局部微环境。
- 保护膜响应时间。
- 冷凝与污染。
- 安装位置温度梯度。
- 长期漂移和批次差异。
- 校准设备的不确定度。

整机必须在最终外壳和工作功耗下进行温湿度箱验证。

## 13. 课程核心总结

### 核心要点

- BSP 的核心价值是隔离 **板级差异、总线实现和故障恢复**。
- 湿度驱动必须完整实现命令、转换等待、CRC、定点换算、超时、状态机和错误统计。
- 服务层必须管理样本新鲜度、质量状态、滤波、告警和退化。
- 板内高可靠方案优先采用 **数字 I²C 传感器 + 异步单次测量**。
- I²C 可靠性首先取决于电气设计、事务原子性和恢复机制，而不是重试次数。
- 安全关键控制不能依赖单传感器和单一数值范围检查。

### 性能排序

- CPU 阻塞时间：**DMA/异步状态机 < 传感器周期模式 < 阻塞单次模式**。
- 软件换算性能：有 FPU 的 Cortex-M7 上浮点与定点接近；无 FPU MCU 上通常 **定点更优**。
- 总线吞吐：**1 MHz Fast-mode Plus > 400 kHz > 100 kHz**，但必须满足器件和电气约束。
- 长线可靠性：**4–20 mA ≈ 隔离 RS-485 > SPI > 板内 I²C > 私有单总线**。

### 通用选型结论

- 板内、精度要求高：SHT31/SHT4x 类数字传感器。
- 多任务共享总线：集中式总线管理器或异步驱动。
- 电池设备：电源门控、低重复性单次测量、长周期采样。
- 工业长线：RS-485/Modbus 或 4–20 mA。
- 安全相关控制：异构冗余、质量判定、故障降级和独立保护。

## 14. 快速参考速查表

### 场景选型表

|场景|驱动模式|采样周期|必备机制|
|---|---|---|---|
|裸机单设备|阻塞或轮询状态机|≥1 s|CRC、超时|
|RTOS 工控|异步单次|0.5～10 s|互斥、状态机、恢复|
|低功耗节点|电源门控单次|分钟级|上电延时、反向供电检查|
|多传感器系统|总线管理器|错相调度|队列、优先级、快照|
|冷凝环境|异步 + 恢复流程|依过程|加热器、稳定窗口|
|安全控制|双通道采集|按安全时间|冗余、合理性检查、降级|
|长线工业现场|RS-485/4–20 mA|1～10 s|隔离、浪涌、诊断|

### 特性对比表

|特性|最低要求|推荐工业实现|
|---|---|---|
|地址表示|文档明确|BSP 统一 7 位地址|
|数据完整性|检查通信返回值|返回值 + CRC + 范围检查|
|超时|固定有限值|基于 WCET 计算并实测|
|并发|全局互斥|总线互斥 + 设备状态所有权|
|恢复|软件复位|9 个 SCL + STOP + 外设重置|
|数据有效性|成功/失败|质量码 + 时间戳 + 新鲜度|
|滤波|可选平均|原始值保留 + IIR/中值|
|告警|单阈值|迟滞 + 持续时间 + 故障抑制|
|测试|正常读写|CRC/NACK/超时/锁死故障注入|
|可移植性|HAL 封装|总线函数表 + 多实例上下文|

## 15. 学习效果自检

- 能否准确说明 BSP、设备驱动和传感器服务的职责边界？
- 能否根据总线电容计算 I²C 上拉电阻与上升时间？
- 能否解释 7 位地址 `0x44` 和 HAL 参数 `0x88` 的关系？
- 能否独立实现并验证 SHT3x CRC-8？
- 能否设计不阻塞 CPU 的触发/读取状态机？
- 能否处理毫秒计数器回绕？
- 能否保证 CRC 失败时不发布部分更新样本？
- 能否实现 SDA 锁死后的 9 脉冲恢复？
- 能否量化一次采样的总线占用率和 CPU 活跃时间？
- 能否设计带迟滞和持续时间的湿度告警？
- 能否区分样本“数值合理”和“当前有效”？
- 能否解释冷凝、自热和安装位置造成的系统误差？
- 能否通过故障注入验证 NACK、CRC、超时和断电恢复？
- 能否为安全关键湿度控制设计冗余与降级策略？

## 16. 实践与进阶路径

### 16.1 基础实战：完成单器件驱动

任务：

1. 实现 SHT31 初始化、软复位、单次测量和 CRC。
2. 同时提供阻塞与异步 API。
3. 使用定点数输出 `m°C` 和 `0.001 %RH`。
4. 为 CRC 和换算函数编写主机端单元测试。
5. 用逻辑分析仪确认地址、命令、转换间隔和读取长度。

验收指标：

- 连续读取 10,000 次无状态机异常。
- 人工翻转任意数据位后 CRC 检出率符合 CRC 能力边界。
- API 不使用动态内存。
- 所有错误路径均释放总线锁。

### 16.2 中级实战：构建 RTOS 传感器服务

任务：

1. 创建单一传感器服务任务，统一管理采样周期、设备状态和故障恢复。
2. 使用软件定时器或 `vTaskDelayUntil()` 实现无累计漂移的周期调度。
3. 将“启动转换”和“读取结果”拆分为两个状态，转换期间不得持有 I²C 互斥锁。
4. 通过 FreeRTOS 队列发布不可变样本。
5. 为样本增加序列号、采样时间、发布时间和质量状态。
6. 连续 3 次通信失败后执行总线恢复和传感器软复位。
7. 实现 1 s、5 s、10 s 三档运行时采样周期切换。
8. 模拟高优先级控制任务，验证传感器任务不会破坏其最坏响应时间。

#### 服务消息定义

```
#ifndef HUMIDITY_SERVICE_H
#define HUMIDITY_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#include "bsp_sht3x.h"

typedef enum {
    HUMIDITY_QUALITY_VALID = 0,
    HUMIDITY_QUALITY_STALE,
    HUMIDITY_QUALITY_CRC_ERROR,
    HUMIDITY_QUALITY_IO_ERROR,
    HUMIDITY_QUALITY_OFFLINE
} humidity_quality_t;

typedef struct {
    int32_t temperature_mdeg_c;
    uint32_t humidity_mpermille;
    uint32_t sampled_at_ms;
    uint32_t published_at_ms;
    uint32_t sequence;
    humidity_quality_t quality;
} humidity_message_t;

typedef enum {
    HUMIDITY_COMMAND_SET_PERIOD = 0,
    HUMIDITY_COMMAND_FORCE_SAMPLE,
    HUMIDITY_COMMAND_RESET_SENSOR
} humidity_command_type_t;

typedef struct {
    humidity_command_type_t type;
    uint32_t value;
} humidity_command_t;

typedef struct {
    sht3x_t *sensor;
    QueueHandle_t output_queue;
    QueueHandle_t command_queue;
    TickType_t default_period_ticks;
    UBaseType_t task_priority;
    uint16_t task_stack_depth;
} humidity_service_config_t;

bool humidity_service_start(const humidity_service_config_t *config);

#endif
```

设计约束：

- 输出队列传递**值对象**，不得发送任务栈上样本的指针。
- 如果只关心最新值，输出队列长度设为 1，并使用 `xQueueOverwrite()`。
- 控制命令使用独立队列，避免多个任务直接修改服务内部状态。
- 对外暴露配置，不暴露内部状态机变量。

#### FreeRTOS 服务任务实现

```
#include "humidity_service.h"

#include <limits.h>
#include <stddef.h>

typedef enum {
    SERVICE_IDLE = 0,
    SERVICE_WAIT_CONVERSION,
    SERVICE_BACKOFF
} service_state_t;

typedef struct {
    sht3x_t *sensor;
    QueueHandle_t output_queue;
    QueueHandle_t command_queue;
    TickType_t period_ticks;
    TickType_t deadline;
    TickType_t backoff_ticks;
    service_state_t state;
    uint32_t sequence;
    uint32_t consecutive_errors;
} humidity_service_context_t;

#define HUMIDITY_MIN_PERIOD_MS       100U
#define HUMIDITY_MAX_PERIOD_MS     60000U
#define HUMIDITY_INITIAL_BACKOFF_MS 1000U
#define HUMIDITY_MAX_BACKOFF_MS    60000U
#define HUMIDITY_ERROR_LIMIT           3U

static humidity_service_context_t service_context;
static StaticTask_t service_task_control;
static StackType_t service_task_stack[768U];

static uint32_t ticks_to_ms(TickType_t ticks)
{
    return (uint32_t)(((uint64_t)ticks * 1000ULL) /
                      (uint64_t)configTICK_RATE_HZ);
}

static bool tick_reached(TickType_t now, TickType_t deadline)
{
    return (BaseType_t)(now - deadline) >= 0;
}

static TickType_t clamp_period(uint32_t period_ms)
{
    if (period_ms < HUMIDITY_MIN_PERIOD_MS) {
        period_ms = HUMIDITY_MIN_PERIOD_MS;
    } else if (period_ms > HUMIDITY_MAX_PERIOD_MS) {
        period_ms = HUMIDITY_MAX_PERIOD_MS;
    }

    TickType_t ticks = pdMS_TO_TICKS(period_ms);
    return (ticks == 0U) ? 1U : ticks;
}

static humidity_quality_t map_quality(sht3x_status_t status,
                                      uint32_t consecutive_errors)
{
    if (consecutive_errors >= HUMIDITY_ERROR_LIMIT) {
        return HUMIDITY_QUALITY_OFFLINE;
    }

    switch (status) {
    case SHT3X_E_CRC:
        return HUMIDITY_QUALITY_CRC_ERROR;

    case SHT3X_E_IO:
    case SHT3X_E_TIMEOUT:
        return HUMIDITY_QUALITY_IO_ERROR;

    default:
        return HUMIDITY_QUALITY_STALE;
    }
}

static void publish_sample(humidity_service_context_t *context,
                           const sht3x_sample_t *sample,
                           humidity_quality_t quality)
{
    humidity_message_t message = {
        .temperature_mdeg_c = sample->temperature_mdeg_c,
        .humidity_mpermille = sample->humidity_mpermille,
        .sampled_at_ms = sample->timestamp_ms,
        .published_at_ms = ticks_to_ms(xTaskGetTickCount()),
        .sequence = ++context->sequence,
        .quality = quality
    };

    /*
     * output_queue 必须创建为长度 1。
     * 覆盖旧值保证慢消费者不会阻塞采集服务。
     */
    (void)xQueueOverwrite(context->output_queue, &message);
}

static void publish_error(humidity_service_context_t *context,
                          sht3x_status_t status)
{
    humidity_message_t message = {
        .temperature_mdeg_c = 0,
        .humidity_mpermille = 0U,
        .sampled_at_ms = 0U,
        .published_at_ms = ticks_to_ms(xTaskGetTickCount()),
        .sequence = ++context->sequence,
        .quality = map_quality(status, context->consecutive_errors)
    };

    (void)xQueueOverwrite(context->output_queue, &message);
}

static void recover_sensor(humidity_service_context_t *context)
{
    sht3x_t *sensor = context->sensor;

    if (sensor->bus.recover != NULL) {
        if (sensor->bus.lock(sensor->bus.ctx, 20U)) {
            int result = sensor->bus.recover(sensor->bus.ctx);
            sensor->bus.unlock(sensor->bus.ctx);

            if (result == 0) {
                ++sensor->recoveries;
            }
        }
    }

    /*
     * 总线恢复失败时软复位通常也会失败，但操作有超时边界，
     * 可用于处理总线已恢复而器件状态仍异常的情况。
     */
    (void)sht3x_soft_reset(sensor);
    sensor->state = SHT3X_IDLE;
}

static void enter_backoff(humidity_service_context_t *context,
                          sht3x_status_t status,
                          TickType_t now)
{
    if (context->consecutive_errors < UINT32_MAX) {
        ++context->consecutive_errors;
    }

    publish_error(context, status);

    if (context->consecutive_errors >= HUMIDITY_ERROR_LIMIT) {
        recover_sensor(context);

        if (context->backoff_ticks <
            pdMS_TO_TICKS(HUMIDITY_MAX_BACKOFF_MS / 2U)) {
            context->backoff_ticks *= 2U;
        } else {
            context->backoff_ticks =
                pdMS_TO_TICKS(HUMIDITY_MAX_BACKOFF_MS);
        }

        context->state = SERVICE_BACKOFF;
        context->deadline = now + context->backoff_ticks;
    } else {
        context->state = SERVICE_IDLE;
        context->deadline =
            now + pdMS_TO_TICKS(HUMIDITY_INITIAL_BACKOFF_MS);
    }
}

static void process_command(humidity_service_context_t *context,
                            const humidity_command_t *command,
                            TickType_t now)
{
    switch (command->type) {
    case HUMIDITY_COMMAND_SET_PERIOD:
        context->period_ticks = clamp_period(command->value);
        context->deadline = now;
        break;

    case HUMIDITY_COMMAND_FORCE_SAMPLE:
        if (context->state == SERVICE_IDLE) {
            context->deadline = now;
        }
        break;

    case HUMIDITY_COMMAND_RESET_SENSOR:
        recover_sensor(context);
        context->consecutive_errors = 0U;
        context->backoff_ticks =
            pdMS_TO_TICKS(HUMIDITY_INITIAL_BACKOFF_MS);
        context->state = SERVICE_IDLE;
        context->deadline = now;
        break;

    default:
        break;
    }
}

static void humidity_service_task(void *argument)
{
    humidity_service_context_t *context =
        (humidity_service_context_t *)argument;

    context->deadline = xTaskGetTickCount();

    for (;;) {
        const TickType_t now = xTaskGetTickCount();
        humidity_command_t command;

        while (xQueueReceive(context->command_queue,
                             &command, 0U) == pdPASS) {
            process_command(context, &command, now);
        }

        if (!tick_reached(now, context->deadline)) {
            TickType_t wait_ticks = context->deadline - now;

            if (wait_ticks > pdMS_TO_TICKS(10U)) {
                wait_ticks = pdMS_TO_TICKS(10U);
            }

            (void)xQueueReceive(context->command_queue,
                                &command, wait_ticks);

            if (command.type <= HUMIDITY_COMMAND_RESET_SENSOR) {
                process_command(context, &command,
                                xTaskGetTickCount());
            }
            continue;
        }

        switch (context->state) {
        case SERVICE_IDLE: {
            sht3x_status_t status =
                sht3x_start_measurement(context->sensor);

            if (status == SHT3X_OK) {
                context->state = SERVICE_WAIT_CONVERSION;
                context->deadline =
                    now + pdMS_TO_TICKS(SHT3X_MEASURE_TIME_MS);
            } else {
                enter_backoff(context, status, now);
            }
            break;
        }

        case SERVICE_WAIT_CONVERSION: {
            sht3x_sample_t sample;
            sht3x_status_t status =
                sht3x_read_measurement(context->sensor, &sample);

            if (status == SHT3X_E_NOT_READY) {
                context->deadline = now + 1U;
                break;
            }

            if (status != SHT3X_OK) {
                enter_backoff(context, status, now);
                break;
            }

            context->consecutive_errors = 0U;
            context->backoff_ticks =
                pdMS_TO_TICKS(HUMIDITY_INITIAL_BACKOFF_MS);

            publish_sample(context, &sample,
                           HUMIDITY_QUALITY_VALID);

            context->state = SERVICE_IDLE;
            context->deadline = now + context->period_ticks;
            break;
        }

        case SERVICE_BACKOFF:
            context->state = SERVICE_IDLE;
            context->deadline = now;
            break;

        default:
            context->sensor->state = SHT3X_IDLE;
            context->state = SERVICE_IDLE;
            context->deadline = now;
            break;
        }
    }
}
```

上述示例中的队列等待代码存在一个生产级细节：`xQueueReceive()` 超时返回时，不应读取未初始化的 `command`。应明确判断返回值：

```
BaseType_t received = xQueueReceive(
    context->command_queue, &command, wait_ticks);

if (received == pdPASS) {
    process_command(context, &command, xTaskGetTickCount());
}
```

这也是代码审查必须检查的**未初始化对象读取问题**。

#### 静态创建服务任务与队列

```
#define HUMIDITY_OUTPUT_QUEUE_LENGTH   1U
#define HUMIDITY_COMMAND_QUEUE_LENGTH  8U

static StaticQueue_t output_queue_control;
static StaticQueue_t command_queue_control;

static uint8_t output_queue_storage[
    HUMIDITY_OUTPUT_QUEUE_LENGTH * sizeof(humidity_message_t)];

static uint8_t command_queue_storage[
    HUMIDITY_COMMAND_QUEUE_LENGTH * sizeof(humidity_command_t)];

static QueueHandle_t output_queue;
static QueueHandle_t command_queue;

bool humidity_service_start(const humidity_service_config_t *config)
{
    if ((config == NULL) || (config->sensor == NULL)) {
        return false;
    }

    output_queue = xQueueCreateStatic(
        HUMIDITY_OUTPUT_QUEUE_LENGTH,
        sizeof(humidity_message_t),
        output_queue_storage,
        &output_queue_control);

    command_queue = xQueueCreateStatic(
        HUMIDITY_COMMAND_QUEUE_LENGTH,
        sizeof(humidity_command_t),
        command_queue_storage,
        &command_queue_control);

    if ((output_queue == NULL) || (command_queue == NULL)) {
        return false;
    }

    service_context = (humidity_service_context_t){
        .sensor = config->sensor,
        .output_queue = output_queue,
        .command_queue = command_queue,
        .period_ticks = config->default_period_ticks,
        .backoff_ticks =
            pdMS_TO_TICKS(HUMIDITY_INITIAL_BACKOFF_MS),
        .state = SERVICE_IDLE
    };

    TaskHandle_t handle = xTaskCreateStatic(
        humidity_service_task,
        "humidity",
        sizeof(service_task_stack) / sizeof(service_task_stack[0]),
        &service_context,
        config->task_priority,
        service_task_stack,
        &service_task_control);

    return handle != NULL;
}
```

实际工程应避免接口参数中的 `task_stack_depth` 与固定静态栈配置并存。二者只能选择一种：

- BSP 固定资源：删除配置中的栈深度字段。
- 应用提供资源：由调用方传入 `StaticTask_t` 和栈缓冲区。

#### 消费者任务

```
void environment_control_task(void *argument)
{
    QueueHandle_t queue = (QueueHandle_t)argument;
    humidity_message_t message;

    for (;;) {
        if (xQueueReceive(queue, &message,
                          pdMS_TO_TICKS(1000U)) != pdPASS) {
            environment_enter_degraded_mode();
            continue;
        }

        const uint32_t now_ms =
            ticks_to_ms(xTaskGetTickCount());

        const bool fresh =
            (uint32_t)(now_ms - message.sampled_at_ms) <= 3000U;

        if ((message.quality != HUMIDITY_QUALITY_VALID) ||
            !fresh) {
            environment_enter_degraded_mode();
            continue;
        }

        environment_update_control(
            message.temperature_mdeg_c,
            message.humidity_mpermille);
    }
}
```

#### 验收指标

- 传感器内部转换期间，I²C 互斥锁保持时间为 **0 ms**。
- 单次总线锁持有时间小于 **500 µs**，P99 小于 **800 µs**。
- 传感器离线时，服务任务 CPU 占用率低于 **0.1%** 。
- 高优先级 1 ms 控制任务的 P99 抖动增加不超过 **10 µs**。
- 连续故障后重试间隔按 `1、2、4、8、16、32、60 s` 退避。
- 输出队列消费者停顿 60 s 不得阻塞采集任务。
- 动态切换采样周期后，不出现重复触发和非法状态转换。
- 运行 24 h 后，任务栈高水位至少保留 **25%** 。

> 注意：前文状态机示例在“采样完成后”用 `now + period` 调度，实际采样间隔为“转换时间 + period”。如果要求严格的 1 Hz 采样，应保存绝对周期基准，并按 `next_period += period` 推进，而不是从完成时刻重新计时。

---

### 16.3 高级实战：集中式 I²C 总线管理器

当 EEPROM、RTC、IO 扩展器和多个传感器共享 I²C 时，仅使用互斥锁不能解决以下问题：

- 低优先级 EEPROM 长事务阻塞高优先级控制设备。
- 调用任务被 HAL 超时同步阻塞。
- 重试、恢复和统计逻辑分散。
- 无法统一实施事务截止时间和公平性策略。
- DMA 完成回调与调用任务耦合。

推荐架构：

```
设备驱动
  |
  | 提交事务描述符
  v
I2C 总线管理任务
  |-- 优先级队列
  |-- 截止时间检查
  |-- DMA/中断启动
  |-- 超时监控
  |-- 错误分类
  |-- 总线恢复
  v
I2C 控制器
```

#### 事务描述符

```
typedef enum {
    BSP_I2C_OP_WRITE = 0,
    BSP_I2C_OP_READ,
    BSP_I2C_OP_WRITE_READ
} bsp_i2c_operation_t;

typedef enum {
    BSP_I2C_RESULT_OK = 0,
    BSP_I2C_RESULT_NACK,
    BSP_I2C_RESULT_TIMEOUT,
    BSP_I2C_RESULT_BUS_ERROR,
    BSP_I2C_RESULT_DEADLINE,
    BSP_I2C_RESULT_CANCELLED
} bsp_i2c_result_t;

typedef struct {
    uint8_t address7;
    bsp_i2c_operation_t operation;

    const uint8_t *tx_data;
    size_t tx_length;

    uint8_t *rx_data;
    size_t rx_length;

    TickType_t deadline;
    uint8_t priority;

    TaskHandle_t requester;
    uint32_t token;
} bsp_i2c_transaction_t;
```

生命周期约束：

- 事务完成前，发送和接收缓冲区必须保持有效。
- 禁止提交指向短生命周期任务栈的异步缓冲区后立即返回。
- 超时不表示 DMA 已停止；管理器必须先中止硬件事务，再通知调用方。
- `token` 用于区分延迟到达的旧完成通知。
- 事务描述符应来自固定对象池，禁止在实时路径调用堆分配。

#### 调度策略

建议采用：

1. 首先丢弃已经超过截止时间的事务。
2. 按事务优先级选择请求。
3. 同优先级按 FIFO 执行。
4. 限制单设备连续事务数量，防止其他设备饥饿。
5. 将 EEPROM 大块写入拆为页事务。
6. 总线恢复期间拒绝或暂存新事务。
7. 恢复失败后进入离线状态，并按退避周期探测。

不能仅使用严格优先级队列，否则持续高优先级流量可能导致低优先级设备永久饥饿。可实施“优先级 + 老化”：

Peffective=Pbase+min⁡(Page,max,TwaitTage)Peffective​=Pbase​+min(Page,max​,Tage​Twait​​)

例如每等待 50 ms 提升一级，最多提升两级。

#### 验收指标

- 32 个并发提交者下无事务描述符泄漏。
- 高优先级事务 P99 排队时间小于设计预算。
- EEPROM 页写期间，湿度读取不会超过新鲜度上限。
- DMA 超时后能够完全停止通道并清除挂起中断。
- 延迟到达的旧 ISR 回调不会错误完成新事务。
- 总线永久拉低时，管理任务不会陷入忙循环。
- 连续运行 72 h，提交数等于“完成 + 拒绝 + 取消”总数。

---

### 16.4 专项实战：故障注入与恢复验证

#### 故障注入矩阵

|注入故障|注入位置|期望驱动行为|上层期望行为|
|---|---|---|---|
|地址 NACK|地址阶段|返回 `SHT3X_E_IO`|保留旧值但标记过期|
|数据 NACK|写命令阶段|中止事务并释放锁|计数并重试|
|温度 CRC 错误|接收字节 2|丢弃整个样本|不允许部分更新|
|湿度 CRC 错误|接收字节 5|丢弃整个样本|不更新温湿度|
|SDA 永久低|空闲阶段|尝试 9 脉冲恢复|失败后离线退避|
|转换未完成|读取阶段|返回未就绪/NACK|延迟后有限重试|
|传感器掉电|任意阶段|超时并恢复控制器|质量标记离线|
|MCU 在事务中复位|字节中间|启动时检测总线|执行恢复后自检|
|队列已满|发布阶段|覆盖旧样本|保留最新数据|
|tick 回绕|截止时间附近|状态机继续运行|不发生超长等待|

#### 软件 CRC 故障注入

```
typedef struct {
    sht3x_bus_t real_bus;
    uint32_t read_count;
    uint32_t corrupt_every;
} fault_bus_t;

static int fault_read(void *ctx, uint8_t addr7,
                      uint8_t *data, size_t len,
                      uint32_t timeout_ms)
{
    fault_bus_t *fault = (fault_bus_t *)ctx;

    int result = fault->real_bus.read(
        fault->real_bus.ctx, addr7, data, len, timeout_ms);

    if (result != 0) {
        return result;
    }

    ++fault->read_count;

    if ((fault->corrupt_every != 0U) &&
        ((fault->read_count % fault->corrupt_every) == 0U) &&
        (len >= 6U)) {
        data[4] ^= 0x01U;
    }

    return 0;
}
```

该代理层可以在不修改设备驱动的情况下稳定复现 CRC 错误。类似方式可注入 NACK、延迟和超时。

#### 硬件故障注入

推荐使用：

- MOSFET 控制传感器供电，模拟事务中掉电。
- 开漏 MOSFET 拉低 SDA，模拟总线锁死。
- 可编程逻辑或第二块 MCU 作为恶意 I²C 从设备。
- 温湿度箱生成阶跃和缓变输入。
- 逻辑分析仪触发器捕获 NACK、长低电平和重复 START。

禁止用推挽 GPIO直接驱动高电平与 I²C 从设备对抗，这可能造成过流。故障注入必须维持开漏电气模型。

#### 恢复策略状态图

```
NORMAL
  |
  | 单次失败
  v
RETRY_SHORT
  |
  | 连续 3 次失败
  v
BUS_RECOVERY
  |
  ├─ 成功 -> SENSOR_RESET -> SELF_TEST -> NORMAL
  |
  └─ 失败 -> OFFLINE_BACKOFF
                |
                | 退避到期
                v
             BUS_RECOVERY
```

恢复次数必须受限。若每次恢复耗时 20 ms，而任务无限连续恢复，系统会被故障设备拖垮。推荐使用指数退避并设置每分钟恢复预算。

---

### 16.5 性能测试方法

#### CPU 执行时间

Cortex-M 使用 DWT 测量：

```
static void cycle_counter_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t cycles_to_ns(uint32_t cycles,
                             uint32_t cpu_hz)
{
    return (uint32_t)(((uint64_t)cycles * 1000000000ULL) /
                      cpu_hz);
}

uint32_t start = DWT->CYCCNT;
sht3x_status_t status =
    sht3x_read_measurement(&sensor, &sample);
uint32_t elapsed_cycles = DWT->CYCCNT - start;
```

测试时必须记录：

- 编译器与优化等级。
- CPU 主频、Flash wait state 和缓存状态。
- 中断是否开启。
- 数据是否位于缓存。
- 样本数量。
- 平均值、最大值、P99 和 P99.9。
- 正常路径与错误路径。

只报告平均时间没有工程意义，因为实时系统关心的是最坏执行时间和高百分位尾延迟。

#### 总线占用率

逻辑分析仪分别测量：

- START 到 STOP 的实际事务时间。
- 两事务间软件间隙。
- SCL 高低电平时间。
- 时钟拉伸时间。
- NACK 后控制器释放总线的时间。

总线利用率：

U=∑ttransactionTobservation×100%U=Tobservation​∑ttransaction​​×100%

建议正常平均利用率保持在 **30% 以下**，峰值窗口低于 **70%** ，为重试、恢复和高优先级突发事务保留余量。

#### 任务栈测试

```
UBaseType_t remaining_words =
    uxTaskGetStackHighWaterMark(humidity_task_handle);

size_t remaining_bytes =
    (size_t)remaining_words * sizeof(StackType_t);
```

必须覆盖以下路径后再读取高水位：

- 正常采样。
- CRC 错误日志。
- 总线超时。
- 总线恢复。
- 传感器复位。
- 队列拥塞。
- 诊断命令处理。

日志格式化通常是栈峰值来源，尤其是启用浮点 `printf` 时。

#### 功耗测试

平均电流计算：

Iavg=∑IitiTIavg​=T∑Ii​ti​​

测量设备应具备足够动态范围，能够同时捕获微安休眠电流和毫安级无线发送峰值。应至少区分：

- MCU 唤醒与初始化。
- 传感器上电稳定。
- 测量转换。
- I²C 传输。
- 数据处理。
- 无线发送。
- 系统休眠。

---

### 16.6 自动化测试用例

#### CRC 单元测试

```
#include "unity.h"

void test_sht3x_crc_accepts_datasheet_vector(void)
{
    const uint8_t data[2] = { 0xBEU, 0xEFU };

    TEST_ASSERT_EQUAL_HEX8(
        0x92U, sht3x_crc8(data, sizeof(data)));
}

void test_sht3x_crc_changes_after_single_bit_flip(void)
{
    uint8_t data[2] = { 0xBEU, 0xEFU };
    const uint8_t expected =
        sht3x_crc8(data, sizeof(data));

    data[1] ^= 0x01U;

    TEST_ASSERT_NOT_EQUAL(
        expected, sht3x_crc8(data, sizeof(data)));
}
```

#### 定点换算边界测试

```
void test_conversion_minimum_raw_values(void)
{
    sht3x_sample_t sample = { 0 };

    convert_sample(0U, 0U, &sample);

    TEST_ASSERT_EQUAL_INT32(-45000, sample.temperature_mdeg_c);
    TEST_ASSERT_EQUAL_UINT32(0U, sample.humidity_mpermille);
}

void test_conversion_maximum_raw_values(void)
{
    sht3x_sample_t sample = { 0 };

    convert_sample(UINT16_MAX, UINT16_MAX, &sample);

    TEST_ASSERT_EQUAL_INT32(130000, sample.temperature_mdeg_c);
    TEST_ASSERT_EQUAL_UINT32(100000U,
                             sample.humidity_mpermille);
}
```

#### 状态机测试重点

至少覆盖：

1. `IDLE -> WAITING -> IDLE` 正常路径。
2. 重复调用 `start` 返回状态错误。
3. 到期前读取返回 `NOT_READY`，且保持等待状态。
4. 读取失败后回到可恢复状态。
5. CRC 失败不修改调用方上一份样本。
6. tick 在 `UINT32_MAX` 附近回绕。
7. 连续错误达到阈值后只触发一次恢复。
8. 恢复失败进入退避，而不是立即无限重试。
9. 强制采样命令不会破坏正在进行的转换。
10. 动态周期配置超出范围时正确钳位。

---

### 16.7 进阶实战：双传感器诊断与降级

单个湿度传感器无法检测“CRC 正确但物理测量错误”。高可靠系统可部署两个不同位置或不同型号的传感器。

#### 一致性判定

设两个传感器读数为 RH1RH1​、RH2RH2​：

ΔRH=∣RH1−RH2∣ΔRH=∣RH1​−RH2​∣

不能仅以固定差值判故障，还应考虑：

- 两个安装点的真实空间梯度。
- 传感器精度之和。
- 响应时间差。
- 热源和气流差异。
- 采样时间差。

示例诊断逻辑：

```
typedef enum {
    REDUNDANCY_NORMAL = 0,
    REDUNDANCY_DISAGREE,
    REDUNDANCY_CHANNEL_A_FAILED,
    REDUNDANCY_CHANNEL_B_FAILED,
    REDUNDANCY_BOTH_FAILED
} redundancy_state_t;

redundancy_state_t diagnose_pair(
    const humidity_message_t *a,
    const humidity_message_t *b,
    uint32_t now_ms)
{
    const bool a_valid =
        (a->quality == HUMIDITY_QUALITY_VALID) &&
        ((uint32_t)(now_ms - a->sampled_at_ms) <= 3000U);

    const bool b_valid =
        (b->quality == HUMIDITY_QUALITY_VALID) &&
        ((uint32_t)(now_ms - b->sampled_at_ms) <= 3000U);

    if (!a_valid && !b_valid) {
        return REDUNDANCY_BOTH_FAILED;
    }
    if (!a_valid) {
        return REDUNDANCY_CHANNEL_A_FAILED;
    }
    if (!b_valid) {
        return REDUNDANCY_CHANNEL_B_FAILED;
    }

    uint32_t difference =
        (a->humidity_mpermille > b->humidity_mpermille)
        ? a->humidity_mpermille - b->humidity_mpermille
        : b->humidity_mpermille - a->humidity_mpermille;

    return (difference > 5000U)
        ? REDUNDANCY_DISAGREE
        : REDUNDANCY_NORMAL;
}
```

只有两个通道时，系统能检测不一致，但无法确定哪个通道正确。若必须隔离故障，需要：

- 第三个独立测量通道进行多数表决。
- 使用参考模型结合温度、露点和历史趋势诊断。
- 使用不同原理的异构传感器降低共因失效。
- 在不一致时进入保守降级，而非任意选择一个值。

---

### 16.8 综合毕业任务

设计并实现一个可部署的工业温湿度采集子系统。

#### 功能要求

- 支持 2 个 SHT31 实例。
- 支持 STM32 HAL 和主机模拟总线两种后端。
- 使用异步触发/读取状态机。
- FreeRTOS 下由统一服务任务管理。
- 输出原始值、过滤值、时间戳、序列号和质量码。
- 支持 CRC、NACK、超时和 SDA 锁死恢复。
- 支持运行时修改采样周期。
- 支持双传感器一致性诊断。
- 支持离线指数退避。
- 禁止动态内存。
- 通过静态分析和单元测试。

#### 非功能指标

|指标|要求|
|---|---|
|正常采样 CPU 活跃时间|每样本 < 100 µs|
|I²C 锁最大持有时间|< 1 ms|
|控制任务额外 P99 抖动|< 10 µs|
|服务任务 RAM|< 2 KiB|
|CRC 错误检出后错误数据发布数|0|
|总线锁死恢复时间|< 50 ms|
|离线状态 CPU 占用率|< 0.1%|
|24 h 内存增长|0 B|
|单元测试分支覆盖率|≥ 90%|
|连续硬件在环测试|≥ 72 h|

#### 推荐目录结构

```
bsp/
├── include/
│   ├── bsp_i2c.h
│   └── bsp_sensor_power.h
├── stm32/
│   ├── bsp_i2c_stm32.c
│   └── bsp_sensor_power_stm32.c
└── mock/
    └── bsp_i2c_mock.c

drivers/
└── sht3x/
    ├── sht3x.h
    ├── sht3x.c
    └── sht3x_crc.c

services/
└── environment/
    ├── humidity_service.h
    ├── humidity_service.c
    ├── humidity_filter.c
    └── humidity_diagnostics.c

tests/
├── test_sht3x_crc.c
├── test_sht3x_conversion.c
├── test_sht3x_state_machine.c
├── test_humidity_service.c
└── test_i2c_recovery.c
```

#### 评审检查项

- 驱动是否完全不知道 FreeRTOS 的存在？
- BSP 是否完全不知道 SHT31 命令含义？
- 服务是否通过公开 API 访问驱动，而非修改内部字段？
- 总线锁是否覆盖完整硬件事务？
- 转换等待期间是否释放总线？
- ISR 是否只完成最少工作？
- 所有等待是否有上限？
- 每个错误路径是否释放锁、DMA 和对象池资源？
- 旧样本是否携带明确的新鲜度信息？
- 恢复失败是否进入有界退避？
- 是否能证明不存在事务缓冲区生命周期错误？
- 是否有数据支持 WCET、栈空间和总线占用率结论？

### 16.9 进阶学习方向

1. 阅读目标 MCU 的 I²C 控制器参考手册，分析 `BUSY`、`BERR`、`ARLO`、`NACKF`、`STOPF` 等状态位的清除顺序。
2. 阅读 FreeRTOS 队列、任务通知和互斥锁源码，比较其内存与调度开销。
3. 将同步 BSP 总线接口升级为事务描述符和异步完成回调。
4. 使用 DMA 实现 I²C 传输，并处理超时与 ISR 竞争。
5. 研究 Zephyr Sensor API、Devicetree 和 RTIO 的设备抽象方式。
6. 在 Linux 下实现 `i2c-dev` 后端，并保持同一设备驱动核心。
7. 建立温湿度箱标定流程，计算整机误差预算与测量不确定度。
8. 研究露点、绝对湿度和焓值计算，将其放入服务层而非器件驱动。
9. 引入 CBOR 或 Protobuf 序列化，定义带版本号和质量状态的遥测协议。
10. 对安全相关应用开展 FMEA/FMEDA，分析传感器卡死、漂移、共因失效和诊断覆盖率。

完成上述路径后，应能从“读取一个湿度值”提升到设计一个具备**确定性调度、故障隔离、数据可信度管理、量化性能指标和可验证恢复能力**的工业级传感器子系统。