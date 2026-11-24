
## 1. 学习目标

### 理解

- 理解 I2C 总线的电气结构、时序规则和地址机制。
- 理解开漏输出、上拉电阻、总线仲裁、时钟拉伸和 ACK/NACK 的底层行为。
- 理解 I2C 主机、从机、多主机和多从机之间的协同方式。
- 理解 7 位地址、10 位地址、读写位和实际线上地址字节的区别。

### 掌握

- 掌握 I2C 标准模式、快速模式和快速模式 Plus 的关键时序参数。
- 掌握寄存器型传感器的写寄存器、读寄存器、连续读写和组合事务。
- 掌握总线异常检测、SDA 卡死恢复、超时处理和设备探测。
- 掌握硬件 I2C 外设与 GPIO 模拟 I2C 的适用边界。

### 精通

- 能从波形、寄存器状态和驱动日志定位 NACK、BUS ERROR、ARBITRATION LOST、TIMEOUT 等问题。
- 能分析上拉电阻、总线电容、线长、速率和边沿时间之间的约束。
- 能设计带超时、恢复、并发保护和错误统计的工业级 I2C 驱动。
- 能处理 RTOS 环境中的互斥、优先级反转和设备访问调度问题。

### 能够设计

- 能够设计一个可移植的 I2C 总线抽象层。
- 能够设计多个传感器、EEPROM、显示器共享同一 I2C 总线的设备管理方案。
- 能够根据实时性、可靠性、功耗和硬件限制完成 I2C 方案选型。
- 能够建立 I2C 驱动的测试、波形验证、故障注入和性能评估体系。

---

## 2. 前置要求

### 知识要求

- 掌握 C 语言指针、结构体、枚举、位操作和错误码设计。
- 理解 MCU GPIO、定时器、中断和 DMA 基本工作机制。
- 理解电压、电流、电阻、RC 电路和 CMOS 输入输出。
- 了解 RTOS 任务、互斥锁、信号量和临界区。
- 了解常见数字通信接口，例如 UART、SPI 和 GPIO 中断。

### 技能要求

- 能够阅读 MCU Reference Manual 中的 I2C 外设章节。
- 能够使用逻辑分析仪或示波器观察 SDA/SCL 波形。
- 能够根据芯片数据手册设计寄存器读写时序。
- 能够使用编译器 map 文件分析 RAM、Flash 和栈使用量。
- 能够编写基本的单元测试、硬件测试和故障日志。

---

## 3. 技术概述

### 3.1 I2C 的核心定义

I2C，即 Inter-Integrated Circuit，是一种由 NXP 提出的**同步、半双工、两线式串行总线协议**。

总线包含：

- `SCL`：串行时钟线，由主机产生。
- `SDA`：串行数据线，双向传输数据。

I2C 的两个核心电气特征是：

1. **SDA 和 SCL 通常均为开漏或开集电极输出。**
2. **总线需要外部上拉电阻恢复高电平。**

设备输出低电平时主动拉低总线；设备需要输出高电平时释放总线，由上拉电阻将线路拉高。

### 3.2 技术价值

I2C 适合连接：

- 温度、压力、加速度、陀螺仪等低速传感器。
- EEPROM、RTC、触摸控制器、ADC、DAC。
- PMIC、IO 扩展器、显示控制器。
- 板级管理控制器和配置存储器。

主要优势：

- 只需要两根信号线。
- 支持多个主机和多个从机。
- 从设备通常不需要独立片选线。
- 适合 PCB 内短距离、低引脚数量连接。
- 支持设备地址化和组合事务。

主要局限：

- 速率低于 SPI。
- 总线电容限制明显。
- 半双工通信，吞吐量有限。
- 错误恢复和时序兼容性比 UART 更复杂。
- 不适合长距离和强实时大数据传输。

### 3.3 主流速率模式

|模式|最高速率|典型应用|
|---|---|---|
|Standard-mode|100 kbit/s|低速传感器、EEPROM|
|Fast-mode|400 kbit/s|常规传感器、显示器、RTC|
|Fast-mode Plus|1 Mbit/s|高速寄存器访问|
|High-speed mode|3.4 Mbit/s|特定高速设备，应用较少|
|Ultra Fast-mode|5 Mbit/s|单向传输，不是通用 I2C 场景|

需要注意：**总线速率不是主机单方面决定的，所有设备必须满足对应模式的时序要求。**

---

## 4. 核心特性横向对比

### 4.1 I2C、SPI、UART 对比

|维度|I2C|SPI|UART|
|---|---|---|---|
|信号线|2 根|通常 4 根及以上|2 根|
|通信方向|半双工|全双工|全双工|
|设备选择|地址|CS 片选|通常点对点|
|典型速率|100 kbit/s～1 Mbit/s|数 Mbit/s～数十 Mbit/s|数 kbit/s～数 Mbit/s|
|电气输出|开漏加上拉|推挽|推挽|
|总线共享|方便|需要多个 CS|不适合多设备共享|
|线长能力|板级短距离|板级短距离|可通过收发器扩展|
|实时性|中等|较高|中等|
|软件复杂度|中等偏高|中等|低|
|典型设备|传感器、EEPROM|Flash、LCD、ADC|调试、模块通信|

### 4.2 I2C 实现方式对比

|方案|优点|缺点|推荐用途|
|---|---|---|---|
|MCU 硬件 I2C|CPU 占用低，时序稳定|外设状态机复杂，部分芯片存在兼容性问题|量产产品首选|
|GPIO 模拟 I2C|灵活，便于兼容特殊设备|CPU 占用高，实时性和边沿不稳定|低速、调试、特殊时序|
|硬件 I2C + 中断|CPU 占用低，响应及时|状态机设计复杂|RTOS 产品|
|硬件 I2C + DMA|CPU 占用最低，适合批量传输|短事务收益有限，调试复杂|长寄存器块、显示数据|
|I2C 外部桥接芯片|可解决电平、隔离、长线问题|增加 BOM 和延迟|多电压域、隔离和长距离|

### 4.3 地址模式对比

|类型|地址范围|适用场景|注意事项|
|---|---|---|---|
|7 位地址|`0x00`～`0x7F`|绝大多数器件|驱动接口建议统一使用 7 位地址|
|10 位地址|更大地址空间|地址冲突严重的复杂系统|硬件和驱动支持度较低|
|地址引脚配置|由 ADDR/SA0 等引脚决定|多个同型号器件|必须确认地址引脚上拉/下拉状态|
|地址复用器|使用通道隔离地址|同地址设备数量过多|增加切换管理和故障点|

**关键结论：** 数据手册写的 `0x68` 通常是 7 位地址；线上第一个字节是：

```
写地址字节 = (7-bit address << 1) | 0
读地址字节 = (7-bit address << 1) | 1
```

---

## 5. 底层原理与功能特性深度解析

## 5.1 总线电气结构

典型连接如下：

```
VDD
 |
Rp
 +-------- SDA --------+-------- SDA
 |                     |
主机开漏输出          从机开漏输出

VDD
 |
Rp
 +-------- SCL --------+-------- SCL
 |                     |
主机开漏输出          从机开漏输出
```

设备只能主动拉低总线，不能主动强推高电平。因此总线逻辑采用“线与”结构：

```
任意设备拉低 -> 总线为低
所有设备释放 -> 总线为高
```

这带来两个关键能力：

- **多主机仲裁**：多个主机同时发送时，输出低电平的主机占据总线。
- **时钟同步/拉伸**：从机可以拉低 SCL，迫使主机等待。

### 工程判断

初始化 I2C 前必须确认：

```
static bool i2c_bus_is_idle(bool sda_level, bool scl_level)
{
    return sda_level && scl_level;
}
```

当 `SDA = 1` 且 `SCL = 1` 时，通常认为总线空闲。

如果上电后 `SCL` 或 `SDA` 为低，应先执行总线恢复，不能直接发送 START。

---

## 5.2 上拉电阻与 RC 上升时间

I2C 高电平由上拉电阻和总线电容共同形成 RC 上升过程：

```
V(t) = VDD × (1 - e^(-t / (Rp × Cb)))
```

常用 30% 到 70% 电压阈值之间的上升时间近似为：

```
tr ≈ 0.8473 × Rp × Cb
```

其中：

- `tr`：上升时间。
- `Rp`：上拉电阻。
- `Cb`：总线总电容，包括 PCB、器件引脚、连接器和探头。

典型规范要求：

|模式|最大上升时间|
|---|---|
|Standard-mode|1000 ns|
|Fast-mode|300 ns|
|Fast-mode Plus|120 ns|

### 计算示例

假设：

```
Cb = 200 pF
目标模式 = Fast-mode
tr <= 300 ns
```

则：

```
Rp <= tr / (0.8473 × Cb)
   <= 300 ns / (0.8473 × 200 pF)
   <= 1.77 kΩ
```

因此可选择 `1.8 kΩ` 或 `2.2 kΩ`，并进一步检查低电平灌电流。

低电平时上拉电阻产生的电流：

```
IOL ≈ (VDD - VOL) / Rp
```

假设：

```
VDD = 3.3 V
VOL = 0.4 V
Rp = 1.8 kΩ
```

则：

```
IOL ≈ (3.3 - 0.4) / 1800
    ≈ 1.61 mA
```

该电流必须小于主机和从机的 `IOL` 能力。

### 工程结论

- 上拉过大：上升时间过慢，高速模式下可能采样失败。
- 上拉过小：低电平灌电流过大，增加功耗并可能超过器件能力。
- 不能只按照“常见 4.7 kΩ”固定设计。
- 设计完成后必须用示波器测量实际 `tr`、`tf`、`VOL` 和过冲。

---

## 5.3 I2C 基本时序

### START 条件

当 SCL 为高电平时，SDA 从高变低：

```
SCL: ─────────────
SDA: ────────╲___
             START
```

### STOP 条件

当 SCL 为高电平时，SDA 从低变高：

```
SCL: ─────────────
SDA: ___╱────────
       STOP
```

### 数据有效条件

正常数据传输期间：

```
SCL 为高时，SDA 必须保持稳定
SDA 只能在 SCL 为低时改变
```

例外是 START 和 STOP。

### 字节和 ACK

每传输 8 位数据，第 9 个时钟周期用于 ACK/NACK：

```
| bit7 | bit6 | ... | bit0 | ACK |
```

- 接收方拉低 SDA：ACK。
- 接收方释放 SDA：NACK。
- 写事务中，主机通常等待从机 ACK。
- 读事务中，主机读取最后一个字节后发送 NACK，通知从机结束。

---

## 5.4 标准寄存器读事务

典型传感器寄存器读取时序：

```
START
从机地址 + Write
ACK
寄存器地址
ACK
REPEATED START
从机地址 + Read
ACK
数据字节 0
ACK
数据字节 1
ACK
...
数据字节 N
NACK
STOP
```

关键点是：

- 写入寄存器地址后不发送 STOP。
- 通过 Repeated START 切换到读方向。
- 读取最后一个字节后发送 NACK。
- 如果中间发送 STOP，某些设备会重置内部寄存器指针或进入新的状态。

### 可移植驱动接口

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef enum {
    I2C_OK = 0,
    I2C_ERR_PARAM = -1,
    I2C_ERR_TIMEOUT = -2,
    I2C_ERR_NACK = -3,
    I2C_ERR_BUS = -4,
    I2C_ERR_ARBITRATION = -5,
    I2C_ERR_BUSY = -6,
    I2C_ERR_RECOVERY = -7
} i2c_status_t;

typedef struct {
    i2c_status_t (*write_read)(uint8_t addr7,
                               const uint8_t *tx,
                               size_t tx_len,
                               uint8_t *rx,
                               size_t rx_len,
                               uint32_t timeout_ms);

    i2c_status_t (*write)(uint8_t addr7,
                          const uint8_t *data,
                          size_t len,
                          uint32_t timeout_ms);

    i2c_status_t (*recover)(void);
} i2c_bus_ops_t;
```

### 寄存器读写封装

```
static i2c_status_t sensor_read_reg(const i2c_bus_ops_t *bus,
                                     uint8_t addr7,
                                     uint8_t reg,
                                     uint8_t *data,
                                     size_t len,
                                     uint32_t timeout_ms)
{
    if (bus == NULL || bus->write_read == NULL ||
        data == NULL || len == 0U ||
        addr7 > 0x7FU) {
        return I2C_ERR_PARAM;
    }

    return bus->write_read(addr7,
                           &reg,
                           1U,
                           data,
                           len,
                           timeout_ms);
}

static i2c_status_t sensor_write_reg(const i2c_bus_ops_t *bus,
                                      uint8_t addr7,
                                      uint8_t reg,
                                      const uint8_t *data,
                                      size_t len,
                                      uint32_t timeout_ms)
{
    uint8_t frame[32];

    if (bus == NULL || bus->write == NULL ||
        (data == NULL && len != 0U) ||
        len > sizeof(frame) - 1U ||
        addr7 > 0x7FU) {
        return I2C_ERR_PARAM;
    }

    frame[0] = reg;

    for (size_t i = 0U; i < len; ++i) {
        frame[i + 1U] = data[i];
    }

    return bus->write(addr7, frame, len + 1U, timeout_ms);
}
```

生产代码中不应默认使用无限等待：

```
while (!(I2C_STATUS & TX_READY)) {
    /* 错误：没有超时，SCL 被拉低时可能永久阻塞 */
}
```

应使用单调递增的时间基准：

```
static bool timeout_expired(uint32_t start,
                            uint32_t now,
                            uint32_t timeout_ms)
{
    return (uint32_t)(now - start) >= timeout_ms;
}
```

使用无符号减法可以正确处理 32 位系统 tick 回绕。

---

## 5.5 7 位地址与地址字节

错误写法：

```
#define SENSOR_ADDR 0xD0U

i2c_write(SENSOR_ADDR, data, len);
```

如果驱动接口要求 7 位地址，`0xD0` 是错误的，因为它已经包含了读写位。

正确写法：

```
#define SENSOR_ADDR_7BIT 0x68U

i2c_write(SENSOR_ADDR_7BIT, data, len);
i2c_read(SENSOR_ADDR_7BIT, data, len);
```

底层发送时才拼接：

```
static uint8_t i2c_address_byte(uint8_t addr7, bool read)
{
    return (uint8_t)((addr7 << 1U) | (read ? 1U : 0U));
}
```

---

## 5.6 总线仲裁

多个主机同时发送时，每个主机在 SCL 高电平期间读取 SDA：

```
主机 A 发送：1
主机 B 发送：0
总线实际：  0
```

发送 `1` 的主机发现总线为 `0`，说明自己失去仲裁。

由于低电平优先，仲裁不会破坏发送低电平的主机事务。

硬件控制器通常会产生：

- Arbitration Lost。
- Bus Error。
- Unexpected STOP。
- Address NACK。

多主机系统不能简单地将“发送失败”统一重试，否则可能导致：

- 多个主机同时重试。
- 总线拥塞。
- 高优先级事务延迟不可控。

应结合随机退避或系统级总线所有权管理。

---

## 5.7 时钟拉伸

从机可以在 SCL 高电平阶段继续拉低 SCL，表示自己还没有准备好。

主机必须区分：

```
主机释放 SCL，但实际 SCL 仍为低
```

与：

```
主机自身没有正确释放 SCL
```

硬件 I2C 控制器通常会自动等待 SCL 真正为高，但驱动仍必须配置超时。

禁止写成：

```
while (read_scl() == 0U) {
    /* 无限等待 */
}
```

正确逻辑：

```
static i2c_status_t wait_scl_high(uint32_t timeout_ms,
                                   uint32_t (*tick_ms)(void),
                                   bool (*read_scl)(void))
{
    uint32_t start = tick_ms();

    while (!read_scl()) {
        if (timeout_expired(start, tick_ms(), timeout_ms)) {
            return I2C_ERR_TIMEOUT;
        }
    }

    return I2C_OK;
}
```

---

## 5.8 硬件 I2C 状态机

不同 MCU 的寄存器名称不同，但硬件状态机通常包含以下阶段：

```
IDLE
  |
  v
START_SENT
  |
  v
ADDRESS_SENT
  |
  +-- NACK --------> ERROR
  |
  v
TX_DATA / RX_DATA
  |
  +-- ACK/NACK ----> NEXT_BYTE
  |
  v
STOP
  |
  v
IDLE
```

驱动应将硬件事件和错误事件分开管理：

```
typedef enum {
    I2C_EVT_NONE = 0,
    I2C_EVT_START,
    I2C_EVT_ADDR_ACK,
    I2C_EVT_ADDR_NACK,
    I2C_EVT_TX_READY,
    I2C_EVT_RX_READY,
    I2C_EVT_STOP,
    I2C_EVT_BUS_ERROR,
    I2C_EVT_ARBITRATION_LOST,
    I2C_EVT_TIMEOUT
} i2c_event_t;
```

不要只判断“发送完成”：

```
if (i2c_transfer_done()) {
    return I2C_OK;
}
```

必须确认：

- 地址阶段是否 ACK。
- 每个数据字节是否完成。
- 最后一个接收字节是否正确发送 NACK。
- STOP 是否已经生成。
- 错误标志是否已经清除。
- 外设是否真正回到空闲状态。

---

## 5.9 GPIO 模拟 I2C 的核心框架

软件模拟 I2C 适合低速设备和硬件调试，但必须保证时序和超时。

```
typedef struct {
    void (*sda_release)(void);
    void (*sda_low)(void);
    bool (*sda_read)(void);

    void (*scl_release)(void);
    void (*scl_low)(void);
    bool (*scl_read)(void);

    void (*delay_us)(uint32_t us);
    uint32_t (*tick_ms)(void);
} soft_i2c_gpio_t;

static i2c_status_t soft_i2c_start(soft_i2c_gpio_t *io)
{
    if (io == NULL) {
        return I2C_ERR_PARAM;
    }

    io->sda_release();
    io->scl_release();
    io->delay_us(2U);

    if (!io->sda_read() || !io->scl_read()) {
        return I2C_ERR_BUSY;
    }

    io->sda_low();
    io->delay_us(2U);
    io->scl_low();

    return I2C_OK;
}

static void soft_i2c_stop(soft_i2c_gpio_t *io)
{
    io->sda_low();
    io->delay_us(2U);
    io->scl_release();
    io->delay_us(2U);
    io->sda_release();
    io->delay_us(2U);
}
```

GPIO 模拟模式还需要处理 SCL 被从机拉低的情况：

```
static i2c_status_t soft_i2c_clock_high(soft_i2c_gpio_t *io,
                                        uint32_t timeout_us)
{
    uint32_t elapsed = 0U;

    io->scl_release();

    while (!io->scl_read()) {
        io->delay_us(1U);

        if (++elapsed >= timeout_us) {
            return I2C_ERR_TIMEOUT;
        }
    }

    io->delay_us(1U);
    return I2C_OK;
}
```

---

## 5.10 SDA 卡死恢复

典型故障：

```
SCL = 高
SDA = 低
```

常见原因：

- 从机在一个字节中途复位。
- 主机复位时没有发送 STOP。
- 电源时序导致从机状态机停留在接收状态。
- 噪声导致从机误判时钟数量。
- 驱动异常退出，没有释放总线。

常见恢复方法：

1. 确认主机不再占用硬件 I2C。
2. 将 SDA 配置为输入/释放。
3. 手动产生最多 9 个 SCL 脉冲。
4. 等待从机释放 SDA。
5. 生成一个 STOP。
6. 重新初始化 I2C 外设。
7. 重新探测设备。

```
i2c_status_t i2c_recover_bus(soft_i2c_gpio_t *io)
{
    if (io == NULL) {
        return I2C_ERR_PARAM;
    }

    io->sda_release();
    io->scl_release();

    for (uint32_t i = 0U; i < 9U; ++i) {
        if (io->sda_read()) {
            break;
        }

        io->scl_low();
        io->delay_us(5U);

        io->scl_release();

        for (uint32_t wait = 0U; wait < 100U; ++wait) {
            if (io->scl_read()) {
                break;
            }
            io->delay_us(1U);
        }

        io->delay_us(5U);
    }

    /* 无论从机是否释放 SDA，都尝试生成 STOP */
    io->sda_low();
    io->delay_us(5U);
    io->scl_release();
    io->delay_us(5U);
    io->sda_release();
    io->delay_us(5U);

    if (!io->sda_read() || !io->scl_read()) {
        return I2C_ERR_RECOVERY;
    }

    return I2C_OK;
}
```

需要注意：**9 个时钟脉冲不是万能修复机制。** 如果是硬件短路、器件掉电异常或某个从机永久拉低线路，只能通过复位从机、电源隔离或硬件开关解决。

---

## 6. 性能量化分析

## 6.1 单字节理论传输时间

一个完整的 I2C 字节通常需要：

- 8 个数据位。
- 1 个 ACK/NACK 位。

因此理论传输时间约为：

```
Tbyte = 9 / Fscl
```

在不同速率下：

|SCL 速率|单字节理论时间|
|---|---|
|100 kHz|90 us|
|400 kHz|22.5 us|
|1 MHz|9 us|

如果是寄存器读取，通常包含：

```
START
地址写 + ACK
寄存器地址 + ACK
Repeated START
地址读 + ACK
数据 N + ACK/NACK
STOP
```

理论时钟数约为：

```
Nbit = 9 × (2 + 1 + N)
```

其中：

- `2`：写地址和读地址。
- `1`：寄存器地址。
- `N`：读取的数据字节数。

例如读取 6 字节：

```
Nbit = 9 × (2 + 1 + 6)
     = 81 bit
```

理论耗时：

```
100 kHz: 810 us
400 kHz: 202.5 us
1 MHz:   81 us
```

实际耗时还要加上：

- START/STOP 建立时间。
- 从机处理延迟。
- 时钟拉伸。
- 中断响应延迟。
- RTOS 调度等待。
- 总线互斥锁等待。
- DMA 启停成本。

### 工程结论

当传感器要求 1 kHz 采样时，100 kHz I2C 读取 6 字节已经占用接近一个毫秒周期，不适合在同一总线上叠加多个设备。

---

## 6.2 CPU 占用

假设：

```
MCU 主频：168 MHz
I2C：400 kHz
事务长度：10 字节
```

轮询模式下，CPU 可能在约 `250 us` 内持续执行状态检查。

如果每次轮询和寄存器访问约消耗 80 个 CPU 周期：

```
CPU 轮询次数 ≈ 10 字节 × 9 位 × 若干状态检查
CPU 占用取决于控制器状态机和轮询间隔
```

工程上常见结果：

|实现方式|单次 10 字节事务 CPU 时间|CPU 占用特点|
|---|---|---|
|轮询|约 100～300 us|事务期间持续占用|
|中断|约 5～30 us|分散在中断处理|
|DMA|约 2～15 us|主要消耗在启动和完成中断|

以上数据是典型 Cortex-M4/M7 工程范围，不是协议规范值，必须在目标平台实测。

### 短事务不要盲目使用 DMA

DMA 启动包括：

- 配置源地址。
- 配置目标地址。
- 设置传输长度。
- 清除状态。
- 启动通道。
- 等待完成中断。

如果只读取 1～2 个字节，DMA 节省的 CPU 时间可能小于启动开销和调试复杂度。

---

## 6.3 内存开销

推荐采用单总线事务上下文：

```
typedef struct {
    uint8_t addr7;
    const uint8_t *tx_buf;
    uint8_t *rx_buf;
    size_t tx_len;
    size_t rx_len;
    size_t tx_pos;
    size_t rx_pos;
    uint32_t deadline;
    i2c_status_t result;
    bool active;
} i2c_transaction_t;
```

典型开销：

|项目|典型 RAM|
|---|---|
|总线控制对象|32～80 字节|
|事务上下文|32～64 字节|
|中断状态机|100～300 字节|
|DMA 描述符|32～128 字节|
|软件临时缓冲区|按最大事务长度变化|

工业级设计中应避免驱动内部固定分配过大的临时数组：

```
uint8_t buffer[1024];
```

对于 I2C 传感器驱动，通常将缓冲区交给上层，或将最大事务限制在数据手册允许范围内。

---

## 6.4 瓶颈与优化手段

### 瓶颈 1：总线电容过大

表现：

- 上升时间超限。
- 高速模式下偶发 NACK。
- 示波器看到高电平斜坡明显。
- 低温或不同批次器件表现不一致。

优化：

- 降低上拉电阻。
- 缩短走线。
- 减少挂载设备。
- 降低 SCL 频率。
- 使用总线缓冲器或分段器件。

### 瓶颈 2：事务数量过多

错误模式：

```
读寄存器 0
STOP
读寄存器 1
STOP
读寄存器 2
STOP
```

优化为：

```
设置寄存器地址
Repeated START
连续读取多个寄存器
```

### 瓶颈 3：RTOS 任务频繁竞争

优化方式：

- 由总线管理任务统一调度事务。
- 对同一设备合并连续寄存器访问。
- 使用优先级队列。
- 对实时设备预留时间窗口。
- 缩短总线锁持有时间。

### 瓶颈 4：过长的时钟拉伸

必须将设备等待时间和总线通信超时分开：

```
设备转换时间：例如 10 ms
I2C 总线事务超时：例如 2 ms
```

不应通过无限延长 I2C 超时来掩盖设备状态机设计问题。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
需要连接多个低速板级设备？
|
+-- 否
|   |
|   +-- 需要高吞吐或全双工？
|       |
|       +-- 是 -> 优先 SPI
|       +-- 否 -> UART / GPIO / 其他接口
|
+-- 是
    |
    +-- 设备能否使用统一电压和短距离 PCB 连接？
    |   |
    |   +-- 否 -> 电平转换器、隔离器或其他物理层
    |   +-- 是
    |
    +-- 总设备地址是否冲突？
    |   |
    |   +-- 否 -> I2C
    |   +-- 是
    |       |
    |       +-- 地址引脚可配置？ -> 配置不同地址
    |       +-- 否
    |           |
    |           +-- 可分配独立 CS？ -> SPI
    |           +-- 否 -> I2C Multiplexer / 总线开关
    |
    +-- 是否要求严格确定性实时响应？
        |
        +-- 是 -> 评估 SPI、专用接口或本地缓存
        +-- 否 -> I2C
```

## 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|MCU 连接温度和压力传感器|400 kHz 硬件 I2C|数据量小，多设备共享|
|连接 24Cxx EEPROM|硬件 I2C|支持页写，协议成熟|
|连接高速显示控制器|I2C 配置 + SPI/并口数据|I2C 不适合大量像素数据|
|多个相同型号传感器|地址配置或 I2C MUX|解决固定地址冲突|
|线长超过几十厘米|不建议直接 I2C|电容和抗干扰风险高|
|需要安全隔离|隔离 I2C 或改用 CAN/RS-485|适合跨地电位和工业现场|
|采集频率超过 1 kHz|优先 SPI|I2C 带宽和延迟可能不足|
|低功耗周期唤醒设备|低速 I2C + 电源门控|降低通信和待机功耗|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **驱动接口统一使用 7 位地址。**
2. **所有事务必须有超时。**
3. **错误路径必须释放总线锁。**
4. **总线恢复必须可独立调用。**
5. **设备驱动不直接操作 MCU 寄存器。**
6. **底层总线层负责时序，设备层负责寄存器语义。**
7. **对于共享总线，使用总线级互斥，而不是每个设备单独加锁。**
8. **对 NACK、TIMEOUT、BUS ERROR、ARBITRATION LOST 分别统计。**
9. **启动阶段探测设备不应阻塞系统主任务。**
10. **禁止在中断上下文执行可能阻塞的 I2C 事务。**

## 8.2 选型决策矩阵

|指标|低速硬件 I2C|高速硬件 I2C|GPIO 模拟 I2C|SPI|
|---|---|---|---|---|
|引脚数量|5|5|4|3～更多|
|吞吐量|低|中|低|高|
|多设备扩展|高|高|高|中|
|时序稳定性|高|中高|低|高|
|CPU 占用|低|低|高|中低|
|调试难度|中|高|中|中|
|适合量产|高|高|低中|高|

## 8.3 工业级编码规范

建议错误码至少区分：

```
typedef enum {
    DEV_OK = 0,
    DEV_ERR_PARAM,
    DEV_ERR_NOT_FOUND,
    DEV_ERR_BUS_TIMEOUT,
    DEV_ERR_NACK,
    DEV_ERR_DATA_INVALID,
    DEV_ERR_CRC,
    DEV_ERR_NOT_READY
} dev_status_t;
```

建议为每条总线维护统计信息：

```
typedef struct {
    uint32_t transaction_count;
    uint32_t nack_count;
    uint32_t timeout_count;
    uint32_t bus_error_count;
    uint32_t arbitration_lost_count;
    uint32_t recovery_count;
    uint32_t recovery_failed_count;
} i2c_statistics_t;
```

---

## 9. 常见错误与避坑指南

## 9.1 错误一：把 8 位地址当成 7 位地址

### 错误代码

```
#define EEPROM_ADDR 0xA0U

i2c_mem_read(EEPROM_ADDR, 0x00U, buffer, 16U);
```

### 根因

`0xA0` 是包含读写位的地址字节，不是 7 位设备地址。

### 正确实现

```
#define EEPROM_ADDR_7BIT 0x50U

i2c_mem_read(EEPROM_ADDR_7BIT, 0x00U, buffer, 16U);
```

### 风险影响

- 设备始终 NACK。
- 误以为硬件损坏。
- 设备扫描结果与数据手册不一致。

---

## 9.2 错误二：事务无超时

### 错误代码

```
while ((I2C_STATUS & I2C_STATUS_DONE) == 0U) {
}
```

### 根因

从机掉电、SDA 卡死、SCL 被拉低或硬件状态机异常时，完成标志永远不会置位。

### 正确实现

```
uint32_t start = tick_ms();

while ((I2C_STATUS & I2C_STATUS_DONE) == 0U) {
    if ((uint32_t)(tick_ms() - start) >= 10U) {
        i2c_abort();
        i2c_recover_bus();
        return I2C_ERR_TIMEOUT;
    }
}
```

### 风险影响

- 任务永久阻塞。
- 看门狗复位。
- 故障扩散到整个控制系统。

---

## 9.3 错误三：最后一个读字节发送 ACK

### 错误代码

```
for (size_t i = 0U; i < len; ++i) {
    buffer[i] = i2c_read_byte(true);  /* 每个字节都 ACK */
}
```

### 根因

最后一个字节之后主机应发送 NACK，表示读取结束。

### 正确实现

```
for (size_t i = 0U; i < len; ++i) {
    bool ack = (i + 1U < len);
    buffer[i] = i2c_read_byte(ack);
}
```

### 风险影响

- 从机继续等待下一个字节。
- STOP 时序异常。
- 部分 MCU 硬件状态机卡在接收状态。

---

## 9.4 错误四：缺少总线互斥保护

### 错误代码

```
/* 任务 A */
i2c_write(addr_a, &reg_a, 1U);

/* 任务 B 可能在此处抢占 */
i2c_read(addr_a, data_a, 2U);
```

### 根因

寄存器地址写入和数据读取是一个不可拆分的组合事务，不能被其他任务插入。

### 正确实现

```
mutex_lock(&i2c_bus_mutex);

status = i2c_write_read(addr7,
                        &reg,
                        1U,
                        data,
                        data_len,
                        5U);

mutex_unlock(&i2c_bus_mutex);
```

### 风险影响

- 设备内部寄存器指针被其他事务覆盖。
- 数据来源错误。
- 出现低概率、难复现的数据异常。

---

## 9.5 错误五：忽略总线电容和上升时间

### 错误代码

```
所有 I2C 设计统一使用 10 kΩ 上拉
```

### 根因

上拉电阻没有根据总线电容和目标速率计算。

### 正确实现

```
1. 估算或测量 Cb
2. 根据 tr <= 0.8473 × Rp × Cb 计算 Rp
3. 检查 IOL 和功耗
4. 用示波器确认实际上升时间
```

### 风险影响

- 低温、长线或批量生产后才出现通信失败。
- 高速模式下数据采样边界不足。
- 上拉过小导致器件低电平能力超限。

---

## 9.6 错误六：NACK 后无条件无限重试

### 错误代码

```
while (i2c_write(addr, data, len) != I2C_OK) {
    /* 一直重试 */
}
```

### 根因

NACK 可能代表：

- 地址错误。
- 设备未上电。
- 设备忙。
- 总线故障。
- 设备永久损坏。

### 正确实现

```
for (uint32_t retry = 0U; retry < 3U; ++retry) {
    status = i2c_write(addr, data, len, 2U);

    if (status == I2C_OK) {
        break;
    }

    if (status == I2C_ERR_BUS || status == I2C_ERR_TIMEOUT) {
        i2c_recover();
    }

    delay_ms(1U << retry);
}

if (status != I2C_OK) {
    device_mark_offline();
}
```

### 风险影响

- 任务占满 CPU。
- 总线长期被占用。
- 系统无法识别设备永久失效。

---

## 10. 多机制组合使用方案

## 10.1 硬件 I2C + 中断 + DMA + RTOS 互斥

推荐分层：

```
应用任务
   |
设备驱动层
   |
I2C 设备管理层
   |
I2C 总线抽象层
   |
MCU 硬件 I2C + 中断/DMA
   |
SDA/SCL + 上拉电阻
```

### 设计职责

|层级|职责|
|---|---|
|应用层|业务采样、控制和错误降级|
|设备层|寄存器定义、数据转换、设备状态|
|总线管理层|互斥、队列、优先级、超时|
|硬件适配层|寄存器、中断、DMA、复位和恢复|
|板级配置层|GPIO、时钟、上拉、电平转换|

### 事务请求框架

```
typedef void (*i2c_done_cb_t)(i2c_status_t status, void *context);

typedef struct {
    uint8_t addr7;
    const uint8_t *tx;
    size_t tx_len;
    uint8_t *rx;
    size_t rx_len;
    uint32_t timeout_ms;
    uint8_t priority;
    i2c_done_cb_t callback;
    void *context;
} i2c_request_t;

typedef struct {
    os_mutex_t mutex;
    os_queue_t queue;
    i2c_statistics_t stats;
    bool online;
} i2c_manager_t;
```

提交事务时：

```
i2c_status_t i2c_submit(i2c_manager_t *manager,
                        const i2c_request_t *request)
{
    if (manager == NULL || request == NULL ||
        request->addr7 > 0x7FU ||
        request->tx_len == 0U && request->rx_len == 0U ||
        request->timeout_ms == 0U) {
        return I2C_ERR_PARAM;
    }

    if (!os_queue_send(&manager->queue, request, 0U)) {
        return I2C_ERR_BUSY;
    }

    return I2C_OK;
}
```

### 组合机制的关键点

- 短事务使用中断，长事务使用 DMA。
- 总线管理任务串行化所有事务。
- 设备驱动不直接等待硬件寄存器。
- 超时后先停止当前事务，再进行恢复。
- 恢复失败后将设备标记为离线，并通知上层。
- 低优先级设备不能长期占用总线。
- 高优先级采样事务需要限制最大事务长度。

---

## 11. 工业级实际案例分析

## 11.1 案例一：电机控制器中的温度和电流监测

### 需求

- MCU 连接温度传感器和电流监测芯片。
- 采样周期 10 ms。
- 两个设备共享一条 I2C 总线。
- 单次采样数据不超过 8 字节。
- 传感器异常时不能阻塞电机控制任务。

### 架构设计

```
电机控制任务：高优先级，禁止直接访问 I2C
        |
采样任务：中高优先级，周期性提交事务
        |
I2C 管理任务：串行调度
        |
硬件 I2C 中断模式：400 kHz
```

### 设计要点

- 电机 PWM 控制使用定时器和 ADC，不依赖 I2C。
- I2C 只负责低实时性监测。
- 连续读取温度和电流寄存器，减少 START/STOP 次数。
- 每次事务超时设置为 2 ms。
- 连续 3 次失败后设备离线。
- 设备离线时使用上一次有效值并设置故障标志。

### 采样状态结构

```
typedef struct {
    int16_t temperature;
    int32_t current_ma;
    uint32_t timestamp_ms;
    uint8_t valid;
    uint8_t error_count;
} monitor_sample_t;

static void monitor_update_error(monitor_sample_t *sample,
                                 i2c_status_t status)
{
    if (status == I2C_OK) {
        sample->error_count = 0U;
        sample->valid = 1U;
        return;
    }

    if (sample->error_count < UINT8_MAX) {
        ++sample->error_count;
    }

    if (sample->error_count >= 3U) {
        sample->valid = 0U;
    }
}
```

---

## 11.2 案例二：工业网关中的多路相同传感器

### 需求

- 8 个相同型号的环境传感器。
- 所有设备默认地址相同。
- 采样速率 10 Hz。
- 设备可能被现场热插拔。
- 需要识别单个通道离线。

### 架构设计

```
MCU
 |
I2C 400 kHz
 |
I2C 多路复用器
 |-- 通道 0 -- 传感器
 |-- 通道 1 -- 传感器
 |-- ...
 |-- 通道 7 -- 传感器
```

### 设计要点

- 选择通道后必须完成当前事务，再切换到其他通道。
- 通道切换本身也是 I2C 事务，需要受总线互斥保护。
- 对每个通道维护独立状态：
    - 在线。
    - 连续错误次数。
    - 最近一次成功时间。
    - 最近一次错误类型。
- 设备探测失败不能影响其他通道采样。
- 多路复用器增加额外事务开销，应批量完成同一通道的访问。

### 通道访问框架

```
static i2c_status_t mux_select_channel(const i2c_bus_ops_t *bus,
                                       uint8_t mux_addr,
                                       uint8_t channel)
{
    uint8_t mask;

    if (bus == NULL || channel >= 8U) {
        return I2C_ERR_PARAM;
    }

    mask = (uint8_t)(1U << channel);

    return bus->write(mux_addr, &mask, 1U, 2U);
}

static i2c_status_t sensor_read_on_channel(const i2c_bus_ops_t *bus,
                                           uint8_t mux_addr,
                                           uint8_t channel,
                                           uint8_t sensor_addr,
                                           uint8_t reg,
                                           uint8_t *data,
                                           size_t len)
{
    i2c_status_t status;

    status = mux_select_channel(bus, mux_addr, channel);
    if (status != I2C_OK) {
        return status;
    }

    return sensor_read_reg(bus, sensor_addr, reg, data, len, 2U);
}
```

实际工程中，`mux_select_channel()` 和传感器读取必须在同一总线锁范围内执行。

---

## 11.3 案例三：带 EEPROM 参数存储的控制器

### 需求

- 使用 I2C EEPROM 保存设备参数。
- 每页最大写入 16 字节。
- EEPROM 写入后需要等待内部编程完成。
- 参数掉电保存，必须避免半写入状态。

### 设计要点

- 写入不能跨页，否则可能回绕覆盖页首数据。
- 写入完成后通过 ACK Polling 等待设备重新响应。
- 参数保存采用双备份或版本号。
- 数据末尾增加 CRC。
- 不在高频控制任务中执行 EEPROM 写入。

### 页边界计算

```
static size_t eeprom_page_chunk(uint16_t address,
                                size_t remaining,
                                size_t page_size)
{
    size_t offset = address % page_size;
    size_t available = page_size - offset;

    return remaining < available ? remaining : available;
}
```

### ACK Polling

```
static i2c_status_t eeprom_wait_ready(const i2c_bus_ops_t *bus,
                                       uint8_t addr7,
                                       uint32_t timeout_ms,
                                       uint32_t (*tick_ms)(void))
{
    uint32_t start;

    if (bus == NULL || bus->write == NULL || tick_ms == NULL) {
        return I2C_ERR_PARAM;
    }

    start = tick_ms();

    while (!timeout_expired(start, tick_ms(), timeout_ms)) {
        i2c_status_t status = bus->write(addr7, NULL, 0U, 1U);

        if (status == I2C_OK) {
            return I2C_OK;
        }

        if (status != I2C_ERR_NACK) {
            return status;
        }
    }

    return I2C_ERR_TIMEOUT;
}
```

注意：是否允许 `len = 0` 的地址探测事务取决于底层接口和 EEPROM 型号。某些驱动应提供独立的 `probe()` 接口。

---

## 12. 高频问题深度答疑

## 问题一：为什么 I2C 必须使用开漏输出？

开漏输出使多个设备可以安全地连接到同一条线上。任何设备都可以拉低线路，而不会与其他设备的高电平推挽输出发生强电平冲突。

如果多个设备使用推挽输出：

```
设备 A 输出高
设备 B 输出低
```

将产生较大的短路电流，可能损坏器件或造成严重 EMI。

开漏结构的代价是高电平由电阻上拉形成，导致上升沿受 RC 限制。

---

## 问题二：为什么 I2C 读寄存器必须使用 Repeated START？

很多从机内部存在寄存器地址指针：

1. 主机先写入寄存器地址。
2. 从机更新内部地址指针。
3. 主机重新发起读事务。
4. 从机从该地址输出数据。

Repeated START 可以在不释放总线的情况下切换方向，防止其他主机插入事务，也符合许多器件的数据手册要求。

但是，部分设备支持：

```
START + 写寄存器地址 + STOP
START + 读数据
```

是否可以分成两个事务，必须以设备数据手册为准。

---

## 问题三：NACK 一定表示设备损坏吗？

不一定。NACK 的含义取决于发生阶段：

|发生阶段|可能原因|
|---|---|
|地址阶段|地址错误、设备掉电、设备忙、通道未选|
|寄存器地址阶段|设备不支持该操作、协议错误|
|数据发送阶段|EEPROM 正在编程、写保护、数据长度不合法|
|数据接收结束|主机主动 NACK，可能是正常结束|

因此错误日志至少应该记录：

```
设备地址
事务方向
事务阶段
寄存器地址
错误状态寄存器
超时时间
恢复次数
```

---

## 问题四：I2C 总线被拉死后，为什么要发送 9 个时钟？

I2C 一个字节由 8 个数据位和 1 个 ACK 位组成。如果从机因为主机异常复位停留在接收状态，额外时钟可以帮助它完成当前字节并释放 SDA。

但这只是针对部分协议状态机卡死问题。以下情况无法依靠 9 个脉冲解决：

- 从机硬件损坏。
- SDA 线路短路。
- 从机电源异常。
- 设备内部固件持续拉低线路。
- 多个设备同时故障。

恢复失败后应执行从机复位或电源重启。

---

## 问题五：硬件 I2C 和 GPIO 模拟 I2C 如何选择？

硬件 I2C 通常是量产产品的默认选择，因为它：

- 时序更稳定。
- CPU 占用更低。
- 更容易支持中断和 DMA。
- 在高负载 RTOS 中更可靠。

GPIO 模拟 I2C 适合：

- 早期硬件调试。
- MCU 硬件 I2C 外设被其他功能占用。
- 设备需要非标准延时。
- 低速、低频、事务非常少的场景。

如果使用 GPIO 模拟 I2C，必须自己处理：

- SCL 拉伸。
- 总线恢复。
- 超时。
- 中断抢占导致的时序抖动。
- GPIO 模式切换。
- 关键段保护。

---

## 问题六：I2C 是否适合工业长距离通信？

通常不适合直接使用。原因包括：

- 总线电容随着线长增加。
- 上升时间变慢。
- 外部噪声和地电位差影响增大。
- 开漏上拉结构抗干扰能力有限。
- 设备数量增加后电容进一步增大。

如果必须扩展距离，应考虑：

- I2C 总线缓冲器。
- 差分 I2C 收发器。
- 电气隔离器。
- 分段总线。
- 将 I2C 转换为 CAN、RS-485 或其他工业总线。

对于现场设备之间的通信，优先使用具备错误检测、仲裁和长线能力的物理层和协议。

---

## 13. 课程核心总结

### 核心要点

1. **I2C 是开漏、上拉、同步、半双工的两线总线。**
2. **7 位地址与线上 8 位地址字节必须严格区分。**
3. **SDA 只能在 SCL 低电平期间改变，START/STOP 是例外。**
4. **每 8 个数据位后都有一个 ACK/NACK 位。**
5. **寄存器读取通常采用写寄存器地址加 Repeated START 的组合事务。**
6. **所有硬件等待都必须有超时。**
7. **SDA 卡死时可以尝试 9 个 SCL 脉冲加 STOP 恢复。**
8. **上拉电阻必须结合总线电容、速率、VOL 和 IOL 计算。**
9. **RTOS 下必须保护完整事务，而不只是保护单个 API 调用。**
10. **I2C 适合板级低速控制和配置，不适合长距离、高吞吐实时传输。**

### 性能排序

在相同 MCU 和事务长度下，通常为：

```
SPI 吞吐量 > 高速 I2C > 标准 I2C > GPIO 模拟 I2C
```

CPU 占用通常为：

```
DMA I2C < 中断 I2C < 轮询 I2C < GPIO 模拟 I2C
```

实现简单度通常为：

```
UART > SPI > 硬件 I2C > GPIO 模拟 I2C
```

### 通用选型结论

- 多个低速器件、引脚紧张：**I2C**。
- 高吞吐、低延迟、独立片选可用：**SPI**。
- 点对点、调试和模块通信：**UART**。
- I2C 设备地址冲突：优先调整地址，其次使用 MUX。
- I2C 长距离：不要直接拉长，应使用专用收发器或更合适的工业总线。
- 量产驱动：硬件 I2C + 中断，必要时结合 DMA、超时和总线恢复。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐方案|
|---|---|
|单个温度传感器|硬件 I2C，100/400 kHz|
|多个低速传感器|硬件 I2C，统一总线调度|
|相同地址设备|地址配置或 I2C MUX|
|EEPROM 页写|分页写入 + ACK Polling|
|传感器组合读取|`write_read`，Repeated START|
|事务长度较大|中断或 DMA|
|总线卡死|9 脉冲 + STOP + 外设重初始化|
|长距离工业连接|CAN、RS-485 或差分 I2C|
|严格实时采样|SPI、ADC 或专用接口|

### 14.2 特性对比表

|特性|关键规则|
|---|---|
|空闲状态|SDA=1，SCL=1|
|START|SCL 高时 SDA 高到低|
|STOP|SCL 高时 SDA 低到高|
|数据改变|只能在 SCL 低时改变|
|数据采样|通常在 SCL 高时采样|
|地址接口|驱动层使用 7 位地址|
|写地址字节|`addr7 << 1`|
|读地址字节|`(addr7 << 1)|
|字节长度|8 位数据 + 1 位 ACK/NACK|
|读事务结束|最后一个字节发送 NACK|
|总线恢复|通常最多 9 个 SCL 脉冲|
|超时处理|必须存在，禁止无限等待|
|上拉设计|结合 `tr`、`Cb`、`IOL` 计算|

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

- [ ]  能解释为什么 I2C 使用开漏输出和外部上拉。
- [ ]  能根据 `VDD`、`VOL`、`IOL` 和 `Cb` 计算上拉电阻范围。
- [ ]  能正确区分 7 位地址和 8 位地址字节。
- [ ]  能画出标准寄存器读事务的完整时序。
- [ ]  能解释最后一个接收字节为什么必须发送 NACK。
- [ ]  能区分地址 NACK、数据 NACK、BUS ERROR 和 TIMEOUT。
- [ ]  能实现带超时的硬件 I2C 事务。
- [ ]  能实现 GPIO 模拟 I2C 的 START、STOP 和 SCL 拉伸处理。
- [ ]  能实现 SDA 卡死后的总线恢复流程。
- [ ]  能在 RTOS 中正确保护跨 Repeated START 的完整事务。
- [ ]  能判断一个 I2C 设备是否适合使用 DMA。
- [ ]  能使用逻辑分析仪验证地址、寄存器地址、数据和 ACK。
- [ ]  能设计设备掉线、重试和故障降级策略。
- [ ]  能说明 I2C 与 SPI、UART、CAN、RS-485 的适用边界。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：GPIO 模拟 I2C 基础

实现：

- GPIO 开漏模拟。
- START、STOP。
- 发送 8 位数据。
- 接收 ACK。
- 单字节读写。

验收标准：

- 逻辑分析仪能看到正确 START/STOP。
- 地址和数据位序正确。
- ACK 采样点正确。
- SCL 频率误差小于 5%。

### 任务二：EEPROM 驱动

实现：

- 单字节读写。
- 连续读写。
- 页边界处理。
- ACK Polling。
- 写超时和重试。
- 掉电数据 CRC。

验收标准：

- 随机地址、随机长度读写通过。
- 跨页写不会破坏相邻数据。
- 强制复位后能恢复总线。
- 10 万次写入测试无逻辑错误。

### 任务三：硬件 I2C 中断驱动

实现：

- 写地址阶段。
- Repeated START。
- 连续发送和接收。
- ACK/NACK。
- 错误中断。
- 超时退出。
- 事务完成回调。

验收标准：

- CPU 不在事务期间忙等。
- 设备拔出后任务仍能继续运行。
- 错误状态可以被分类统计。

### 任务四：RTOS I2C 总线管理器

实现：

- 总线互斥。
- 事务队列。
- 优先级调度。
- 同步和异步 API。
- 设备在线状态管理。
- 总线恢复。
- 故障事件通知。

验收标准：

- 多任务并发访问无事务交叉。
- 高优先级任务最大等待时间可计算。
- 设备异常不会阻塞其他系统任务。

### 任务五：波形和压力测试

测试项目：

- 100 kHz、400 kHz、1 MHz 三档速率。
- 不同上拉电阻。
- 不同总线负载电容。
- 设备热插拔。
- 主机中途复位。
- 从机强制拉低 SDA。
- SCL 拉伸。
- 随机 NACK。
- RTOS 高负载调度。

记录指标：

```
事务成功率
平均延迟
P99 延迟
最大延迟
NACK 率
TIMEOUT 率
总线恢复成功率
CPU 占用
RAM 使用量
上升时间 tr
低电平 VOL
```

## 16.2 性能测试方法

建议使用逻辑分析仪同时采集：

- SDA。
- SCL。
- MCU GPIO 标记脚。
- 中断进入/退出标记。
- 事务提交和完成时间戳。

通过 GPIO 标记测量：

```
事务端到端延迟
驱动实际 CPU 占用
总线锁等待时间
中断服务时间
恢复操作耗时
```

不要只测量 SCL 频率。工业系统真正关心的是：

```
从业务请求产生，到有效数据可用的完整延迟
```

## 16.3 进阶学习方向

- I2C 电气规范中的完整时序参数和噪声容限。
- STM32、NXP、TI、Renesas 等不同 MCU I2C 外设状态机差异。
- I2C 中断状态机与 DMA 的组合设计。
- Linux `i2c-core`、`i2c-adapter`、`i2c-client` 和设备树。
- Linux `i2c-dev` 与 SMBus 接口。
- SMBus 超时、PEC、Alert Response 和 Host Notify。
- I2C 总线复用器、隔离器、缓冲器和差分扩展。
- RTOS 总线服务化架构与优先级调度。
- 故障注入、形式化验证和长时间压力测试。
- 多主机仲裁、系统级资源所有权和安全访问控制。