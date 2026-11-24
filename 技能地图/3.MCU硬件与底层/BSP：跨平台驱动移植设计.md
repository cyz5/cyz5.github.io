
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 BSP、HAL、LL、驱动框架、设备树、应用接口之间的边界。
- 理解板级差异、芯片差异、操作系统差异和业务差异在驱动移植中的不同表现。
- 理解跨平台驱动设计中**硬件抽象、能力抽象和策略抽象**的分层关系。
- 理解 GPIO、I2C、SPI、UART、DMA、中断、电源和时钟等资源在 BSP 中的生命周期。

### 掌握

应能够：

- 设计一个可移植的 BSP 目录结构。
- 使用统一总线接口封装不同 MCU、不同 RTOS 或 Linux 平台。
- 处理 GPIO 复用、外部中断、DMA、缓存一致性、设备探测和错误恢复。
- 设计同步、超时、并发访问和资源释放机制。
- 将一个已有 MCU 驱动从平台强相关代码中剥离出来。

### 精通

应能够：

- 识别驱动代码中的隐式平台依赖。
- 评估不同移植方案对实时性、代码体积、启动时间和维护成本的影响。
- 设计可测试、可替换、可追踪的 BSP 适配层。
- 处理多实例设备、不同总线控制器、热插拔、低功耗和故障恢复。
- 建立 BSP 的版本管理、配置管理和硬件变体管理机制。

### 能够设计

应能够设计：

- 面向多个 MCU、多个硬件版本和多个操作系统的 BSP 架构。
- 可扩展的传感器、显示屏、存储器或通信模组驱动框架。
- 支持单元测试、仿真测试、板级测试和性能回归测试的驱动工程。
- 具备可观测性、故障诊断和现场升级能力的工业级 BSP。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、结构体、函数指针、编译链接和内存模型。
- 理解 MCU 启动流程、向量表、中断控制器和时钟树。
- 熟悉 GPIO、UART、I2C、SPI、ADC、PWM、DMA 等常见外设。
- 至少使用过一种 RTOS，例如 FreeRTOS、RT-Thread、Zephyr。
- 了解基本的 Make、CMake、Kconfig 或设备树。
- 理解阻塞、非阻塞、中断上下文和线程上下文的区别。

### 技能要求

- 能够阅读芯片参考手册和原厂 SDK。
- 能够使用逻辑分析仪、示波器和 JTAG/SWD 调试器。
- 能够分析 map 文件、反汇编和链接脚本。
- 能够独立构建、烧录和调试至少一种 MCU 工程。
- 能够编写基本的单元测试和接口 Mock。

---

## 3. 技术概述

### 3.1 BSP 的定义

BSP 是运行在特定硬件板卡上的软件支持集合，负责把：

- 芯片启动和时钟；
- 引脚复用；
- 外设控制器；
- 板载器件；
- 电源和复位；
- 中断和 DMA；
- 存储布局；
- 操作系统启动；

封装成上层系统可以使用的接口。

BSP 不等于“所有底层代码”。更准确地说：

```
应用层
  |
设备功能层：传感器、显示、存储、通信模组
  |
通用驱动层：统一设备操作接口
  |
BSP 适配层：GPIO/I2C/SPI/UART/时间/锁/中断
  |
芯片 HAL/LL：厂商 SDK、寄存器访问
  |
MCU/SoC 硬件
```

### 3.2 BSP 的技术价值

高质量 BSP 需要同时解决四个问题：

1. **硬件差异隔离**  
    同一个温度传感器驱动可以运行在不同 MCU、不同 I2C 控制器上。
    
2. **资源配置集中管理**  
    GPIO、总线、IRQ、DMA 通道和电源依赖不应散落在业务代码中。
    
3. **生命周期管理**  
    驱动需要明确初始化、启动、停止、挂起、恢复和释放行为。
    
4. **工程可验证性**  
    上层驱动应能在没有真实硬件的情况下使用 Mock 进行测试。
    

### 3.3 主流 BSP 实现分支

|方案|典型平台|主要特点|
|---|---|---|
|厂商 SDK 直接封装|STM32 HAL、NXP MCUXpresso|开发效率高，供应商绑定明显|
|自研 MCU BSP|工业控制、汽车电子|可控性高，初期成本大|
|RTOS BSP|RT-Thread、Zephyr、FreeRTOS|提供设备模型、线程、同步和配置系统|
|Linux BSP|Linux kernel、U-Boot、Device Tree|设备模型完整，代码复杂度高|
|多平台 HAL|CMSIS、Mbed HAL、统一公司 HAL|便于跨芯片，但常需牺牲底层能力|
|自动生成 BSP|STM32CubeMX、MCUXpresso Config Tools|配置效率高，需控制生成代码边界|

---

## 4. 核心特性横向对比

### 4.1 驱动抽象层次对比

|方案|抽象粒度|可移植性|性能|代码复杂度|适用场景|
|---|---|---|---|---|---|
|直接寄存器|芯片寄存器|低|最高|高|极限实时、芯片专用|
|厂商 HAL|外设控制器|中|中高|低|单芯片系列产品|
|自研平台 HAL|总线和设备能力|高|高|中高|多 MCU 产品线|
|RTOS 设备框架|设备对象和标准 API|高|中|中|大规模设备管理|
|Linux 子系统|内核设备模型|高|中|高|Linux SoC、复杂系统|
|应用直接控制|无抽象|极低|不稳定|初期低、长期极高|仅适合原型验证|

### 4.2 跨平台接口设计对比

|接口方式|示例|优点|风险|
|---|---|---|---|
|固定函数接口|`bsp_i2c_read()`|简单、可读性高|难支持复杂硬件能力|
|函数表|`struct bus_ops`|可替换、便于 Mock|生命周期和空指针风险|
|面向对象设备句柄|`device->ops->read()`|多实例和扩展性好|C 代码复杂度增加|
|消息队列异步接口|`device_submit()`|适合 DMA 和高并发|延迟模型复杂|
|IOCTL/命令接口|`device_control()`|适合可选能力扩展|类型安全较弱|
|编译期静态绑定|宏和配置表|零运行时开销|编译配置复杂|

---

## 5. 底层原理与功能特性深度解析

## 5.1 BSP 分层设计

推荐将代码划分为四层：

```
bsp/
├── common/
│   ├── bsp_status.h
│   ├── bsp_time.h
│   └── bsp_assert.h
├── soc/
│   ├── stm32h7/
│   └── imxrt1060/
├── board/
│   ├── board_alpha/
│   └── board_beta/
├── osal/
│   ├── freertos/
│   ├── rtos_x/
│   └── baremetal/
└── drivers/
    ├── bus/
    ├── sensor/
    ├── display/
    └── storage/
```

推荐依赖关系：

```
drivers  --> bsp/common + bsp/hal + bsp/osal
board    --> bsp/soc + board configuration
soc      --> vendor SDK or registers
application --> drivers public API
```

禁止出现：

```
通用传感器驱动 --> stm32_hal_gpio.h
通用传感器驱动 --> FreeRTOS.h
业务代码 --> GPIO 端口号、I2C 控制器地址
```

### 5.1.1 统一错误码

```
#ifndef BSP_STATUS_H
#define BSP_STATUS_H

#include <stdint.h>

typedef enum {
    BSP_OK = 0,
    BSP_EINVAL = -1,
    BSP_ENODEV = -2,
    BSP_EBUSY = -3,
    BSP_ETIMEOUT = -4,
    BSP_EIO = -5,
    BSP_ENOMEM = -6,
    BSP_ENOTSUP = -7,
    BSP_ESTATE = -8,
} bsp_status_t;

#endif
```

错误码应满足：

- 能区分参数错误、设备不存在、总线忙、超时和硬件错误。
- 不直接透传某个厂商 HAL 的错误枚举。
- 需要记录原始错误时，在诊断结构中保存 `vendor_error`。
- 中断上下文和线程上下文使用同一语义，但允许不同执行路径。

---

## 5.2 硬件资源抽象

### 5.2.1 GPIO 抽象

```
typedef enum {
    BSP_GPIO_INPUT = 0,
    BSP_GPIO_OUTPUT_PP,
    BSP_GPIO_OUTPUT_OD,
    BSP_GPIO_IT_RISING,
    BSP_GPIO_IT_FALLING,
    BSP_GPIO_IT_BOTH,
} bsp_gpio_mode_t;

typedef enum {
    BSP_GPIO_LOW = 0,
    BSP_GPIO_HIGH = 1,
} bsp_gpio_level_t;

typedef struct {
    uint32_t port;
    uint16_t pin;
    bsp_gpio_mode_t mode;
    bool active_high;
} bsp_gpio_desc_t;

bsp_status_t bsp_gpio_init(const bsp_gpio_desc_t *desc);
bsp_status_t bsp_gpio_write(const bsp_gpio_desc_t *desc,
                            bsp_gpio_level_t logical_level);
bsp_status_t bsp_gpio_read(const bsp_gpio_desc_t *desc,
                           bsp_gpio_level_t *logical_level);
```

逻辑电平与物理电平必须分离：

```
static bsp_gpio_level_t to_physical_level(const bsp_gpio_desc_t *desc,
                                          bsp_gpio_level_t logical)
{
    if (desc->active_high) {
        return logical;
    }

    return logical == BSP_GPIO_HIGH ? BSP_GPIO_LOW : BSP_GPIO_HIGH;
}
```

这样可以避免业务代码中出现：

```
gpio_write(RESET_PIN, 0); /* 0 到底代表释放还是复位？ */
```

而改为：

```
bsp_gpio_write(&sensor_reset, BSP_GPIO_LOW);
```

### 5.2.2 I2C 抽象

I2C 驱动应至少表达：

- 控制器实例；
- 从设备地址；
- 速率；
- 超时时间；
- 重试次数；
- 是否允许 STOP；
- 是否需要 DMA；
- 总线恢复能力。

```
typedef struct {
    uint8_t address;
    uint32_t speed_hz;
    uint32_t timeout_ms;
    uint8_t retries;
} bsp_i2c_cfg_t;

typedef struct {
    void *controller;
    bsp_i2c_cfg_t cfg;
} bsp_i2c_bus_t;

bsp_status_t bsp_i2c_write(const bsp_i2c_bus_t *bus,
                           const uint8_t *data,
                           size_t length);

bsp_status_t bsp_i2c_read(const bsp_i2c_bus_t *bus,
                          uint8_t *data,
                          size_t length);

bsp_status_t bsp_i2c_write_read(const bsp_i2c_bus_t *bus,
                                const uint8_t *write_data,
                                size_t write_length,
                                uint8_t *read_data,
                                size_t read_length);
```

### 5.2.3 I2C 总线时间计算

标准 I2C 一次字节传输通常包含：

- 8 个数据位；
- 1 个 ACK 位；
- 即每字节约 9 个 SCL 周期；
- 加上起始、地址、停止和寄存器地址开销。

近似时间：

```
T ≈ (N_bits / f_scl) + T_start_stop
N_bits ≈ 9 × (字节数 + 地址字节 + 寄存器字节)
```

例如，400 kHz I2C 读取 16 字节：

```
数据阶段字节数 = 1 地址 + 1 寄存器 + 16 数据 = 18
N_bits ≈ 18 × 9 = 162
T_data ≈ 162 / 400000 = 405 us
```

考虑设备拉伸、总线仲裁、RTOS 调度和驱动重试，实际耗时通常为 **430~600 us**。

### 5.2.4 SPI 抽象

SPI 不能只抽象为“读写字节”，因为不同设备需要：

- CS 时序；
- Mode 0~3；
- 8/16 位数据宽度；
- 半双工或全双工；
- DMA；
- CS 保持；
- 命令和数据阶段切换。

```
typedef struct {
    void *controller;
    uint32_t frequency_hz;
    uint8_t mode;
    uint8_t bits_per_word;
    bool keep_cs;
} bsp_spi_cfg_t;

typedef struct {
    const uint8_t *tx;
    uint8_t *rx;
    size_t length;
} bsp_spi_transfer_t;

bsp_status_t bsp_spi_transfer(const bsp_spi_cfg_t *cfg,
                              const bsp_spi_transfer_t *transfer);
```

### 5.2.5 总线锁与设备锁

总线锁用于保护控制器：

```
I2C1 总线锁
  ├── 温度传感器
  ├── EEPROM
  └── 电源监控芯片
```

设备锁用于保护设备内部状态：

```
传感器对象锁
  ├── 配置寄存器缓存
  ├── 校准参数
  └── 数据读取状态
```

不要用设备锁替代总线锁。两个设备仍可能同时访问同一个 I2C 控制器。

---

## 5.3 驱动对象与操作表

一个可移植设备驱动通常包含：

```
typedef struct sensor sensor_t;

typedef struct {
    bsp_status_t (*init)(sensor_t *dev);
    bsp_status_t (*deinit)(sensor_t *dev);
    bsp_status_t (*read)(sensor_t *dev, void *data);
    bsp_status_t (*control)(sensor_t *dev, uint32_t cmd, void *arg);
} sensor_ops_t;

struct sensor {
    const sensor_ops_t *ops;
    const bsp_i2c_bus_t *bus;
    const bsp_gpio_desc_t *reset_gpio;
    void *private_data;
    uint32_t flags;
};
```

设备驱动不得直接访问平台资源：

```
/* 错误：平台耦合 */
HAL_I2C_Master_Transmit(&hi2c1, address, data, len, 100);
HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
```

应该只依赖抽象接口：

```
static bsp_status_t sensor_write_reg(sensor_t *dev,
                                      uint8_t reg,
                                      uint8_t value)
{
    uint8_t buffer[2] = { reg, value };

    if (dev == NULL || dev->bus == NULL) {
        return BSP_EINVAL;
    }

    return bsp_i2c_write(dev->bus, buffer, sizeof(buffer));
}
```

### 5.3.1 私有数据与多实例

```
typedef struct {
    uint8_t address;
    uint16_t who_am_i;
    bool initialized;
} sensor_priv_t;

static sensor_priv_t sensor_priv_pool[4];
```

不要使用单一全局变量：

```
/* 错误：无法支持两个相同传感器 */
static uint8_t g_sensor_address;
static bool g_initialized;
```

多实例驱动应将状态放入设备对象或实例私有区。

---

## 5.4 中断、线程和 DMA 上下文

### 5.4.1 中断服务函数原则

ISR 中应只完成：

1. 读取并清除硬件状态；
2. 保存最小事件信息；
3. 通知线程或释放信号量；
4. 尽快退出。

```
void sensor_irq_handler(void *arg)
{
    sensor_t *dev = (sensor_t *)arg;

    if (dev == NULL) {
        return;
    }

    sensor_hw_clear_irq(dev);

    osal_event_set_from_isr(dev->event, SENSOR_EVENT_DATA_READY);
}
```

禁止在 ISR 中：

- 进行 I2C/SPI 阻塞访问；
- 打印大量日志；
- 动态内存分配；
- 调用不支持 ISR 的 RTOS API；
- 执行复杂校准算法。

### 5.4.2 DMA 缓存一致性

在带 D-Cache 的 Cortex-M7、Cortex-A 或异构 SoC 中，DMA 和 CPU 可能看到不同的数据。

DMA 接收前：

```
cache_invalidate(rx_buffer, rx_length);
start_dma_rx(rx_buffer, rx_length);
```

DMA 接收完成后：

```
cache_invalidate(rx_buffer, rx_length);
process_packet(rx_buffer, rx_length);
```

DMA 发送前：

```
cache_clean(tx_buffer, tx_length);
start_dma_tx(tx_buffer, tx_length);
```

缓存行对齐示例：

```
#define CACHE_LINE_SIZE 32U

static size_t align_down(size_t value, size_t alignment)
{
    return value & ~(alignment - 1U);
}

static size_t align_up(size_t value, size_t alignment)
{
    return (value + alignment - 1U) & ~(alignment - 1U);
}
```

实际清理范围必须覆盖完整缓存行，否则相邻数据可能被错误回写。

---

## 5.5 设备初始化状态机

初始化不应被实现为不可恢复的长函数。推荐显式状态机：

```
typedef enum {
    DEV_STATE_RESET = 0,
    DEV_STATE_POWERED,
    DEV_STATE_CONFIGURED,
    DEV_STATE_RUNNING,
    DEV_STATE_ERROR,
} dev_state_t;
```

典型流程：

```
RESET
  |
  v
上电
  |
  v
硬件复位
  |
  v
等待启动时间
  |
  v
读取 ID
  |
  v
配置寄存器
  |
  v
校验配置
  |
  v
RUNNING
```

失败处理必须反向释放：

```
配置失败
  -> 关闭中断
  -> 停止 DMA
  -> 释放总线锁
  -> 关闭电源
  -> 进入 ERROR
```

---

## 5.6 设备树和板级配置

对于多硬件变体，推荐将资源描述与驱动逻辑分离。

```
typedef struct {
    const char *name;
    bsp_i2c_bus_t i2c;
    bsp_gpio_desc_t reset;
    bsp_gpio_desc_t irq;
    uint32_t power_on_delay_ms;
} sensor_board_cfg_t;
```

配置实例：

```
static const sensor_board_cfg_t board_sensor_cfg = {
    .name = "imu0",
    .i2c = {
        .controller = I2C1,
        .cfg = {
            .address = 0x68,
            .speed_hz = 400000U,
            .timeout_ms = 20U,
            .retries = 2U,
        },
    },
    .reset = {
        .port = GPIOA,
        .pin = 3U,
        .mode = BSP_GPIO_OUTPUT_PP,
        .active_high = false,
    },
    .irq = {
        .port = GPIOB,
        .pin = 5U,
        .mode = BSP_GPIO_IT_RISING,
        .active_high = true,
    },
    .power_on_delay_ms = 5U,
};
```

板级配置应包含资源，不应包含业务策略。例如：

- 可以包含 I2C 地址；
- 可以包含 GPIO 极性；
- 可以包含最大总线速率；
- 不应包含“低于 10 摄氏度则报警”。

---

## 6. 性能量化分析

以下数据为典型工程基准，平台为：

```
MCU：Cortex-M7，400 MHz
RTOS：FreeRTOS
编译器：Arm GCC -O2
总线：I2C 400 kHz，SPI 20 MHz
测试方式：GPIO 翻转 + 示波器，DWT CYCCNT，10000 次统计
```

不同编译器、缓存、驱动配置和芯片外设实现会造成差异，量产前应在目标板上复测。

### 6.1 调用路径开销

|路径|典型额外延迟|RAM 开销|说明|
|---|---|---|---|
|直接寄存器|0.05~0.15 us|0 B|无函数间接调用|
|厂商 HAL|0.3~1.2 us|0~64 B|状态机和参数检查|
|自研函数表 HAL|0.2~0.8 us|8~32 B|函数指针间接调用|
|RTOS 设备框架|1~5 us|64~256 B|对象、锁和事件管理|
|DMA 启动|1~4 us|描述符相关|适合长数据传输|

对于 I2C 传感器一次 500 us 的传输而言，增加 1 us 的抽象开销只占 **0.2%** 。因此除非处于极短周期控制环，否则不应为了几十个 CPU 周期破坏层次设计。

### 6.2 栈和堆开销

典型驱动实例：

```
设备对象：32~64 B
配置对象：32~96 B
互斥锁：24~80 B，依赖 RTOS
事件对象：24~64 B
DMA 描述符：32~128 B
驱动线程栈：512~2048 B
```

推荐优先采用：

- 静态设备对象；
- 静态 DMA 缓冲区；
- 编译期实例数量；
- 明确的最大传输长度。

避免在驱动 API 中频繁调用 `malloc()`：

```
/* 不推荐 */
uint8_t *buffer = malloc(length);
```

原因包括：

- 内存碎片；
- 失败路径复杂；
- 实时性不确定；
- 释放责任不清晰。

### 6.3 吞吐量估算

SPI 20 MHz、8 位数据时：

```
理论吞吐量 = 20 Mbit/s / 8 = 2.5 MB/s
```

考虑命令、地址、CS 间隔和 DMA 启停，实际有效吞吐量通常为：

```
2.0~2.35 MB/s
```

I2C 400 kHz 理论吞吐量：

```
400 kbit/s / 9 ≈ 44.4 kB/s
```

实际有效吞吐量常为：

```
30~38 kB/s
```

### 6.4 瓶颈分析

常见瓶颈：

1. **总线本身**  
    I2C 通常是最先到达吞吐上限的部分。
    
2. **同步锁竞争**  
    多设备共享总线时，低优先级线程可能阻塞高优先级线程。
    
3. **中断频率过高**  
    FIFO 未启用时，按字节中断会显著增加 CPU 负载。
    
4. **DMA 缓存维护**  
    小于缓存行的数据使用 DMA 可能得不偿失。
    
5. **日志输出**  
    UART 阻塞日志可以比实际驱动耗时高一个数量级。
    

### 6.5 优化手段与收益

|优化手段|典型收益|
|---|---|
|I2C 100 kHz 升至 400 kHz|传输时间降低约 75%|
|SPI 中断改 DMA|CPU 占用下降 50%~95%|
|传感器启用 FIFO|中断次数下降 10~100 倍|
|合并寄存器访问|总线事务数下降 20%~60%|
|静态内存替代动态分配|消除运行时分配抖动|
|批量日志替代逐次打印|CPU 和串口占用明显下降|
|设备状态缓存|减少重复探测和寄存器读取|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否需要支持多个 MCU 或多个板卡？
├── 否
│   ├── 是否极端关注纳秒级延迟？
│   │   ├── 是 -> 寄存器或 LL 层，但保留边界封装
│   │   └── 否 -> 厂商 HAL + 轻量 BSP
│   |
│   └── 是否存在多个硬件版本？
│       ├── 是 -> 板级配置表 + 统一驱动
│       └── 否 -> 静态板级定义
|
└── 是
    ├── 是否跨越不同芯片厂商？
    │   ├── 是 -> 自研平台 HAL + 驱动操作表
    │   └── 否 -> 芯片系列 HAL 封装
    |
    ├── 是否运行 Linux？
    │   ├── 是 -> Device Tree + Linux 设备模型
    │   └── 否 -> OSAL + 静态资源描述
    |
    └── 是否有高吞吐数据流？
        ├── 是 -> DMA/FIFO/异步提交接口
        └── 否 -> 同步接口即可
```

### 7.2 典型场景选型

|场景需求|推荐方案|主要理由|
|---|---|---|
|同一产品使用 STM32F4/F7/H7|自研 MCU HAL + 板级配置|保留系列共性，隔离寄存器差异|
|同一传感器运行在 STM32 和 NXP|设备驱动 + 总线函数表|传感器寄存器逻辑可复用|
|量产产品有 5 个板卡变体|Device Resource Table|防止 GPIO 和地址散落在代码中|
|低功耗电池设备|电源域接口 + suspend/resume|需要管理唤醒源和状态恢复|
|高速显示屏|SPI DMA + 双缓冲|减少 CPU 阻塞和撕裂|
|工业网关 Linux 平台|Device Tree + kernel driver|设备发现和电源管理更完整|
|安全关键控制器|静态分配 + 明确时限|降低运行时不确定性|
|原型验证|厂商 HAL 直接调用|先验证功能，后续再抽象|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：依赖方向单向

```
应用 -> 设备驱动 -> BSP 抽象 -> SoC/OS 实现
```

禁止底层反向依赖业务模块。

### 原则二：能力抽象优先于硬件抽象

不应暴露：

```
stm32_i2c_handle_t
```

更推荐暴露：

```
bsp_i2c_bus_t
```

上层只依赖“可以完成什么”，不依赖“硬件内部如何完成”。

### 原则三：配置与逻辑分离

- 资源、地址、极性、速率：配置层。
- 初始化顺序、寄存器配置、数据解析：驱动层。
- 报警阈值、业务状态：应用层。

### 原则四：所有阻塞操作必须有上限

禁止：

```
while (!device_ready()) {
}
```

应使用超时：

```
uint32_t deadline = bsp_time_now_ms() + timeout_ms;

while (!device_ready()) {
    if (bsp_time_after_eq(bsp_time_now_ms(), deadline)) {
        return BSP_ETIMEOUT;
    }
}
```

### 原则五：初始化和反初始化对称

```
init:
  时钟 -> GPIO -> DMA -> IRQ -> 设备配置

deinit:
  IRQ -> DMA -> GPIO -> 时钟
```

### 原则六：错误处理必须可恢复

驱动需要明确：

- 是否支持重试；
- 是否支持总线恢复；
- 是否需要重新上电；
- 是否可以重新初始化；
- 是否需要通知上层设备永久失效。

## 8.2 选型决策矩阵

|维度|轻量封装|完整设备框架|Linux 设备模型|
|---|---|---|---|
|开发成本|低|中|高|
|可移植性|中|高|高|
|实时性|高|中高|依系统而定|
|多实例|需自行实现|好|好|
|电源管理|需自行实现|中|完善|
|动态设备发现|弱|中|强|
|代码体积|小|中|大|
|适合 MCU|好|好|不适用|
|适合复杂 SoC|弱|中|好|

## 8.3 工业级编码规范

- 公开 API 使用统一前缀，例如 `bsp_`、`sensor_`。
- 不在公共头文件中暴露厂商类型。
- 不在驱动中使用魔法数字。
- 所有长度参数使用 `size_t` 或明确宽度类型。
- 对输入指针、长度、状态和资源句柄进行检查。
- 不在 ISR 中调用不确定时延函数。
- 所有线程锁需要规定锁顺序。
- 日志包含设备名、实例号、错误码和关键状态。
- 不使用无限重试。
- 任何硬件超时都应能被诊断和统计。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：通用驱动直接依赖芯片 HAL

### 错误代码

```
#include "stm32f4xx_hal.h"

void sensor_reset(void)
{
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
}
```

### 根因

驱动将板级资源和芯片 HAL 混在一起，导致：

- 无法移植到其他 MCU；
- 无法使用 Mock 测试；
- 同一驱动出现多个复制版本。

### 正确实现

```
void sensor_reset(const bsp_gpio_desc_t *reset)
{
    (void)bsp_gpio_write(reset, BSP_GPIO_LOW);
}
```

### 风险影响

后续迁移通常需要修改大量业务和设备逻辑，回归范围不可控。

---

## 9.2 错误二：没有处理 GPIO 有效电平

### 错误代码

```
gpio_write(RESET_PIN, 0);
```

### 根因

代码把物理低电平和逻辑“关闭”混为一谈。

### 正确实现

```
typedef enum {
    SENSOR_RESET_ASSERTED,
    SENSOR_RESET_RELEASED,
} sensor_reset_state_t;

static void sensor_set_reset(const sensor_t *dev,
                             sensor_reset_state_t state)
{
    bsp_gpio_level_t level;

    if (state == SENSOR_RESET_ASSERTED) {
        level = BSP_GPIO_LOW;
    } else {
        level = BSP_GPIO_HIGH;
    }

    (void)bsp_gpio_write(dev->reset_gpio, level);
}
```

实际项目应由 `active_high` 配置控制逻辑映射。

### 风险影响

硬件变更后可能出现设备始终复位、上电失败或电源异常。

---

## 9.3 错误三：I2C 失败后无限重试

### 错误代码

```
do {
    status = i2c_read(...);
} while (status != BSP_OK);
```

### 根因

将暂时性错误和永久性错误混为一类，且没有时间上限。

### 正确实现

```
for (uint8_t attempt = 0U;
     attempt <= bus->cfg.retries;
     ++attempt) {
    bsp_status_t status = bsp_i2c_read_once(bus, data, length);

    if (status == BSP_OK) {
        return BSP_OK;
    }

    if (status == BSP_ENODEV || status == BSP_EINVAL) {
        return status;
    }

    if (attempt < bus->cfg.retries) {
        bsp_delay_ms(1U << attempt);
    }
}

return BSP_ETIMEOUT;
```

### 风险影响

线程永久阻塞，看门狗复位，系统无法完成故障降级。

---

## 9.4 错误四：DMA 缓存未同步

### 错误代码

```
start_dma_rx(rx_buffer, sizeof(rx_buffer));
wait_dma_done();
parse_packet(rx_buffer);
```

### 根因

CPU 读取了 Cache 中的旧数据，而 DMA 已经更新了 SRAM。

### 正确实现

```
cache_clean_invalidate(rx_buffer, sizeof(rx_buffer));

start_dma_rx(rx_buffer, sizeof(rx_buffer));
wait_dma_done();

cache_invalidate(rx_buffer, sizeof(rx_buffer));
parse_packet(rx_buffer);
```

### 风险影响

出现偶现数据错误、CRC 错误和不可复现的协议异常。

---

## 9.5 错误五：在中断中执行阻塞总线访问

### 错误代码

```
void gpio_irq_handler(void)
{
    uint8_t status;

    bsp_i2c_read(&sensor_bus, &status, 1U);
    process_sensor_status(status);
}
```

### 根因

把“中断通知”和“设备数据读取”放在同一执行上下文。

### 正确实现

```
void gpio_irq_handler(void *arg)
{
    sensor_t *dev = arg;

    sensor_irq_clear(dev);
    osal_event_set_from_isr(dev->event, SENSOR_EVENT_IRQ);
}

static void sensor_task(void *arg)
{
    sensor_t *dev = arg;
    uint32_t events;

    for (;;) {
        if (osal_event_wait(dev->event,
                            SENSOR_EVENT_IRQ,
                            &events,
                            OSAL_WAIT_FOREVER) != BSP_OK) {
            continue;
        }

        if ((events & SENSOR_EVENT_IRQ) != 0U) {
            sensor_process_irq(dev);
        }
    }
}
```

### 风险影响

中断延迟不可控，可能触发优先级反转或系统实时性失效。

---

## 10. 多机制组合使用方案

推荐组合：

```
设备资源描述
  +
统一总线 HAL
  +
OSAL
  +
设备操作表
  +
状态机
  +
DMA/FIFO
  +
故障统计
```

### 10.1 完整代码框架

```
typedef struct {
    const bsp_i2c_bus_t *bus;
    const bsp_gpio_desc_t *reset;
    const bsp_gpio_desc_t *irq;
    osal_mutex_t lock;
    osal_event_t event;
    dev_state_t state;
    uint8_t rx_buffer[64];
} imu_device_t;

static bsp_status_t imu_hw_reset(imu_device_t *dev)
{
    bsp_status_t status;

    status = bsp_gpio_write(dev->reset, BSP_GPIO_LOW);
    if (status != BSP_OK) {
        return status;
    }

    bsp_delay_ms(2U);

    status = bsp_gpio_write(dev->reset, BSP_GPIO_HIGH);
    if (status != BSP_OK) {
        return status;
    }

    bsp_delay_ms(10U);
    return BSP_OK;
}

static bsp_status_t imu_probe(imu_device_t *dev)
{
    uint8_t who_am_i = 0U;
    bsp_status_t status;

    status = imu_read_reg(dev, 0x0FU, &who_am_i, 1U);
    if (status != BSP_OK) {
        return status;
    }

    if (who_am_i != 0x68U) {
        return BSP_ENODEV;
    }

    return BSP_OK;
}

bsp_status_t imu_init(imu_device_t *dev)
{
    bsp_status_t status;

    if (dev == NULL || dev->bus == NULL ||
        dev->reset == NULL || dev->irq == NULL) {
        return BSP_EINVAL;
    }

    dev->state = DEV_STATE_RESET;

    status = osal_mutex_init(&dev->lock);
    if (status != BSP_OK) {
        return status;
    }

    status = osal_event_init(&dev->event);
    if (status != BSP_OK) {
        osal_mutex_deinit(&dev->lock);
        return status;
    }

    status = bsp_gpio_init(dev->reset);
    if (status != BSP_OK) {
        goto fail_event;
    }

    status = bsp_gpio_init(dev->irq);
    if (status != BSP_OK) {
        goto fail_event;
    }

    status = imu_hw_reset(dev);
    if (status != BSP_OK) {
        goto fail_event;
    }

    dev->state = DEV_STATE_POWERED;

    status = imu_probe(dev);
    if (status != BSP_OK) {
        goto fail_event;
    }

    status = imu_configure(dev);
    if (status != BSP_OK) {
        goto fail_event;
    }

    dev->state = DEV_STATE_RUNNING;
    return BSP_OK;

fail_event:
    dev->state = DEV_STATE_ERROR;
    osal_event_deinit(&dev->event);
    osal_mutex_deinit(&dev->lock);
    return status;
}
```

该框架体现了：

- 参数校验；
- 显式状态；
- 初始化顺序；
- 失败回滚；
- 总线抽象；
- 线程同步；
- 中断事件化；
- 多实例支持。

### 10.2 同步与异步接口组合

同步接口适合：

```
低频配置
单次寄存器读写
启动阶段设备探测
```

异步接口适合：

```
高速采样
显示刷新
网络收发
大块 Flash 读写
```

推荐同时提供：

```
bsp_status_t device_read(device_t *dev, void *data, size_t len);

bsp_status_t device_submit(device_t *dev,
                           const void *tx,
                           void *rx,
                           size_t len,
                           device_callback_t callback,
                           void *callback_arg);
```

同步接口可以基于异步接口实现，但异步接口不应强行套在所有简单操作上，否则会增加状态管理复杂度。

---

## 11. 工业级实际案例分析

## 11.1 案例一：同一 IMU 驱动移植到 STM32 与 NXP MCU

### 需求

- 两个平台都使用 I2C；
- 一个使用 FreeRTOS，另一个使用 Zephyr；
- IMU 寄存器协议完全一致；
- 支持 1 kHz 采样和 FIFO；
- 驱动代码复用率目标超过 80%。

### 架构

```
imu_core.c
  |
bsp_i2c.h / bsp_gpio.h / bsp_time.h
  |
stm32_i2c_adapter.c       nxp_i2c_adapter.c
freertos_osal.c           zephyr_osal.c
```

### 设计要点

- IMU 核心层只使用统一接口；
- 平台层处理 I2C 控制器状态和 DMA；
- OSAL 层处理锁、事件和线程；
- FIFO 水位中断只产生事件；
- 采样线程批量读取 FIFO。

### 结果

假设每次读取 12 个样本：

```
逐样本读取：12 次 I2C 事务
FIFO 批量读取：1 次 I2C 事务
```

总线事务开销可减少约 **70%~90%** ，中断次数从每秒 1000 次降至约 83 次。

---

## 11.2 案例二：工业控制器的多板卡变体

### 需求

- 主板、精简板和扩展板共享一套业务软件；
- 传感器地址、GPIO、外部中断和电源控制不同；
- 不希望通过大量 `#ifdef` 管理硬件差异。

### 方案

采用板级资源表：

```
typedef struct {
    bool has_pressure_sensor;
    const sensor_board_cfg_t *pressure;
    const sensor_board_cfg_t *temperature;
    uint32_t board_revision;
} board_manifest_t;
```

启动时：

```
读取硬件版本
  -> 加载对应 manifest
  -> 校验资源完整性
  -> 注册设备
  -> 启动业务
```

### 设计要点

- 板级变体差异集中于 manifest；
- 驱动不感知板卡名称；
- 缺失设备返回 `BSP_ENODEV`，而不是让系统启动失败；
- 必须存在的设备由启动策略单独校验；
- 资源表加入版本号和 CRC，避免配置错配。

---

## 11.3 案例三：低功耗无线终端的电源与驱动协同

### 需求

- 传感器平时断电；
- 定时唤醒后完成采集；
- 设备异常时可重新上电；
- 待机功耗目标低于 10 uA。

### 电源状态

```
OFF
  |
POWER_ON
  |
RESET_RELEASE
  |
ACTIVE
  |
SUSPEND
  |
OFF
```

### 核心接口

```
typedef struct {
    bsp_status_t (*power_on)(void);
    bsp_status_t (*power_off)(void);
    bsp_status_t (*enter_sleep)(void);
    bsp_status_t (*exit_sleep)(void);
} power_domain_ops_t;
```

### 设计要点

- 驱动不能假设设备一直上电；
- `resume()` 必须重新检查芯片 ID 和关键寄存器；
- 关电前必须停止 DMA 和中断；
- GPIO 在关电后设置为高阻，避免反向供电；
- 需要区分“软复位恢复”和“电源重启恢复”。

---

## 12. 高频问题深度答疑

## 问题一：BSP 和 HAL 的边界在哪里？

HAL 通常描述芯片外设控制能力，例如：

```
启动 SPI 控制器
配置波特率
启动 DMA
读取状态寄存器
```

BSP 还要描述板级事实，例如：

```
某个传感器连接到 SPI2
CS 使用哪个 GPIO
复位脚是否有效低
设备是否需要电源使能
```

因此：

```
HAL = 芯片能力抽象
BSP = 芯片能力 + 板卡资源 + 系统启动支持
```

驱动应依赖 BSP 提供的稳定接口，而不是依赖具体 HAL。

---

## 问题二：为什么不直接使用厂商 HAL？

厂商 HAL 并非不能使用，问题在于边界。

适合直接使用厂商 HAL 的场景：

- 单一 MCU 产品；
- 产品生命周期短；
- 平台不需要迁移；
- 供应商 SDK 已经成熟稳定。

需要进一步封装的场景：

- 多芯片平台；
- 多 RTOS；
- 多个板级变体；
- 需要单元测试；
- 需要长期维护；
- 需要严格控制错误码和时序。

推荐：

```
驱动 -> 公司统一 BSP API -> 厂商 HAL
```

而不是：

```
驱动 -> 厂商 HAL
```

---

## 问题三：函数指针抽象会不会严重影响性能？

函数指针通常只增加一次间接调用，典型开销约为 **数个到十几个 CPU 周期**。如果外层操作包含 I2C、SPI、DMA 或 RTOS 调度，该开销通常远小于硬件传输时间。

真正需要避免函数指针的场景：

- 纳秒级或单周期级控制；
- 极高频率 GPIO 翻转；
- 编译期常量优化非常关键；
- 中断路径极短且可静态绑定。

一般驱动应优先保证可测试性和可替换性。

---

## 问题四：BSP 中应该使用动态设备注册还是静态注册？

### 静态注册

优点：

- 启动行为确定；
- 无堆内存依赖；
- 易于做安全认证；
- 适合 MCU 和控制类产品。

缺点：

- 灵活性较低；
- 设备实例数量需要编译期确定。

### 动态注册

优点：

- 支持设备发现；
- 适合 Linux、模块化系统；
- 可插拔性更好。

缺点：

- 生命周期复杂；
- 堆内存和锁竞争增加；
- 启动和故障行为更难预测。

MCU 工业控制产品通常优先静态注册，Linux 网关通常使用设备模型和动态管理。

---

## 问题五：驱动是否应该直接负责重试和总线恢复？

应该负责，但必须区分层次。

### 设备驱动负责

- 设备寄存器访问重试；
- 设备复位；
- 设备 ID 检查；
- 配置重新下发。

### 总线 BSP 负责

- 总线忙检测；
- I2C SCL 脉冲恢复；
- 控制器错误清除；
- DMA 超时和中止；
- 总线重新初始化。

不要让设备驱动直接操作 SCL/SDA GPIO，因为这会破坏总线控制器的统一所有权。

---

## 问题六：如何判断一个驱动是否真正可移植？

可以检查以下依赖：

```
是否包含具体芯片头文件？
是否直接使用厂商句柄？
是否硬编码 GPIO、IRQ、DMA 通道？
是否依赖某个 RTOS API？
是否使用未定义宽度的 int/long？
是否假设字节序？
是否假设 Cache 已关闭？
是否假设地址对齐？
是否假设时钟频率固定？
是否假设中断一定来自同一线程？
```

如果这些依赖无法集中在适配层，驱动通常只是“复制可用”，不是“设计可移植”。

---

## 13. 课程核心总结

### 核心要点

1. **BSP 的核心职责是隔离板级和芯片级差异。**
2. 驱动应依赖能力接口，不应依赖具体芯片类型。
3. GPIO、I2C、SPI、DMA、IRQ、电源和时间必须有清晰抽象。
4. 板级配置与驱动逻辑必须分离。
5. 中断负责通知，线程负责复杂处理。
6. 多设备共享总线时，必须显式管理总线锁。
7. DMA 系统必须处理 Cache 一致性和内存对齐。
8. 初始化流程应具备状态管理、超时和反向回滚。
9. 多平台移植的主要成本不是寄存器差异，而是隐藏的上下文、时序和资源假设。
10. 高质量 BSP 的评价标准是：**可移植、可测试、可诊断、可恢复、可维护**。

### 性能排序

通常情况下：

```
直接寄存器 > LL > 厂商 HAL > 自研函数表 HAL > RTOS 设备框架
```

但在完整总线事务中，抽象层开销通常远小于：

```
I2C/SPI 传输时间
RTOS 调度时间
DMA 启停时间
设备内部转换时间
日志输出时间
```

### 通用选型结论

- 单芯片、低复杂度：厂商 HAL + 轻量 BSP。
- 多芯片、同一产品线：统一平台 HAL + 设备操作表。
- 多硬件变体：资源描述表或设备树。
- 高吞吐数据流：DMA、FIFO、异步接口。
- 强实时和安全关键系统：静态资源、明确超时、无动态分配。
- Linux SoC：设备树 + 内核设备模型 + 标准子系统。
- 长期维护项目：优先建立接口边界和测试替身。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐结构|
|---|---|
|单板单芯片|`driver -> vendor HAL`，外加少量 BSP|
|多板同芯片|`driver -> BSP -> board config`|
|多芯片同设备|`driver -> common HAL -> SoC adapter`|
|多 RTOS|`driver -> OSAL -> RTOS adapter`|
|大块数据传输|异步 API + DMA + FIFO|
|低功耗设备|电源域 + suspend/resume|
|安全关键产品|静态注册 + 静态内存 + 明确时限|
|Linux 平台|Device Tree + 内核驱动模型|

### 14.2 特性对比表

|特性|直接寄存器|厂商 HAL|统一 BSP|设备框架|
|---|---|---|---|---|
|性能|最高|高|高|中|
|可移植性|低|中|高|高|
|测试性|低|中|高|高|
|多实例|低|中|高|高|
|代码体积|最小|小|中|大|
|故障恢复|需自行实现|中|高|高|
|适合复杂系统|低|中|高|高|

### 14.3 驱动接口最小集合

```
init()
deinit()
read()
write()
control()
suspend()
resume()
get_status()
```

不是每个设备都必须提供全部接口，但生命周期接口和错误语义应保持一致。

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  BSP、HAL 和设备驱动的职责边界是什么？
- [ ]  为什么通用驱动不能直接包含厂商 HAL 头文件？
- [ ]  如何处理 GPIO 的有效高、有效低差异？
- [ ]  I2C 总线锁和设备锁分别保护什么？
- [ ]  如何估算一次 I2C 事务的理论耗时？
- [ ]  DMA 接收和发送分别需要什么 Cache 操作？
- [ ]  中断处理函数为什么不能执行阻塞 I2C 访问？
- [ ]  多实例设备如何保存独立状态？
- [ ]  初始化失败时资源应如何回滚？
- [ ]  哪些配置应该放入板级资源表？
- [ ]  什么情况下应采用同步 API，什么情况下应采用异步 API？
- [ ]  如何定位驱动中的隐式平台依赖？
- [ ]  多板卡变体如何避免大量 `#ifdef`？
- [ ]  如何为驱动设计 Mock 总线？
- [ ]  如何验证移植后实时性没有退化？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：GPIO BSP 封装

实现：

```
bsp_gpio_init()
bsp_gpio_write()
bsp_gpio_read()
bsp_gpio_toggle()
```

要求：

- 支持有效电平；
- 支持输入、输出和中断模式；
- 不允许上层访问芯片 GPIO 宏；
- 为每个错误路径增加测试。

### 任务二：I2C 设备驱动移植

选择一个真实 I2C 设备，例如：

- EEPROM；
- 温度传感器；
- IMU；
- 电源监控芯片。

实现：

- 芯片无关寄存器驱动；
- STM32 总线适配；
- Mock 总线；
- 设备 ID 探测；
- 超时、重试和恢复；
- 多实例支持。

### 任务三：STM32 与 NXP 双平台移植

要求：

```
同一份 device_core.c
不同的 i2c_adapter.c
不同的 osal_adapter.c
```

统计：

- 核心驱动代码复用率；
- 平台适配代码行数；
- 初始化时间；
- 单次读写延迟；
- 代码体积；
- RAM 使用量。

### 任务四：DMA/FIFO 高吞吐驱动

实现一个 SPI DMA 设备驱动：

- 支持同步和异步接口；
- 支持双缓冲；
- 处理 Cache 清理和失效；
- 统计吞吐量和 CPU 占用；
- 模拟 DMA 超时和传输中止。

### 任务五：低功耗与故障恢复

增加：

```
device_suspend()
device_resume()
device_recover()
device_get_health()
```

测试：

- 运行中掉电；
- I2C 从设备被拉死；
- DMA 未完成；
- IRQ 丢失；
- 设备复位后寄存器恢复；
- 多次恢复后的资源泄漏。

## 16.2 性能测试方法

### 16.2.1 时间测量

在 Cortex-M 系统中，优先使用 DWT CYCCNT 进行周期级测量。

```
#include <stdint.h>
#include <stdbool.h>

static void dwt_cycle_counter_init(void)
{
    /* 使能 DWT 和 CYCCNT */
    *((volatile uint32_t *)0xE000EDFCU) |= (1UL << 24);
    *((volatile uint32_t *)0xE0001000U) |= 1UL;
    *((volatile uint32_t *)0xE0001004U) = 0U;
}

static uint32_t dwt_get_cycles(void)
{
    return *((volatile uint32_t *)0xE0001004U);
}

static uint32_t cycles_to_us(uint32_t cycles, uint32_t cpu_hz)
{
    return (uint32_t)(((uint64_t)cycles * 1000000ULL) / cpu_hz);
}
```

测量驱动接口：

```
bsp_status_t measured_i2c_read(const bsp_i2c_bus_t *bus,
                               uint8_t *data,
                               size_t length,
                               uint32_t *elapsed_us)
{
    uint32_t start;
    uint32_t end;
    bsp_status_t status;

    if (bus == NULL || data == NULL || length == 0U ||
        elapsed_us == NULL) {
        return BSP_EINVAL;
    }

    start = dwt_get_cycles();

    status = bsp_i2c_read(bus, data, length);

    end = dwt_get_cycles();
    *elapsed_us = cycles_to_us(end - start, SystemCoreClock);

    return status;
}
```

测量时必须区分：

```
API 调用开销
总线传输时间
设备内部处理时间
RTOS 调度时间
锁等待时间
重试和恢复时间
```

不要只记录平均值。工业驱动应至少记录：

- 最小值；
- 平均值；
- 最大值；
- P95；
- P99；
- P999；
- 超时次数；
- 重试次数；
- 总线恢复次数。

### 16.2.2 统计代码示例

```
typedef struct {
    uint32_t count;
    uint32_t min_us;
    uint32_t max_us;
    uint64_t total_us;
    uint32_t timeout_count;
    uint32_t retry_count;
} bsp_perf_stats_t;

static void bsp_perf_update(bsp_perf_stats_t *stats,
                            uint32_t elapsed_us,
                            bool timeout,
                            uint32_t retries)
{
    if (stats == NULL) {
        return;
    }

    if (stats->count == 0U || elapsed_us < stats->min_us) {
        stats->min_us = elapsed_us;
    }

    if (elapsed_us > stats->max_us) {
        stats->max_us = elapsed_us;
    }

    stats->count++;
    stats->total_us += elapsed_us;
    stats->retry_count += retries;

    if (timeout) {
        stats->timeout_count++;
    }
}

static uint32_t bsp_perf_average_us(const bsp_perf_stats_t *stats)
{
    if (stats == NULL || stats->count == 0U) {
        return 0U;
    }

    return (uint32_t)(stats->total_us / stats->count);
}
```

对于需要计算 P99 的场景，不能只保存最大值和平均值，需要保存样本、直方图或分桶统计。

资源受限 MCU 可使用固定分桶：

```
typedef struct {
    uint32_t bucket_0_10_us;
    uint32_t bucket_10_50_us;
    uint32_t bucket_50_100_us;
    uint32_t bucket_100_500_us;
    uint32_t bucket_over_500_us;
} latency_histogram_t;

static void latency_histogram_update(latency_histogram_t *hist,
                                     uint32_t elapsed_us)
{
    if (hist == NULL) {
        return;
    }

    if (elapsed_us < 10U) {
        hist->bucket_0_10_us++;
    } else if (elapsed_us < 50U) {
        hist->bucket_10_50_us++;
    } else if (elapsed_us < 100U) {
        hist->bucket_50_100_us++;
    } else if (elapsed_us < 500U) {
        hist->bucket_100_500_us++;
    } else {
        hist->bucket_over_500_us++;
    }
}
```

### 16.2.3 总线测量

使用逻辑分析仪同时观察：

- I2C 的 SCL、SDA；
- SPI 的 SCK、MOSI、MISO、CS；
- UART 的 TX、RX；
- DMA 开始和完成 GPIO；
- 驱动 API 入口和出口 GPIO；
- IRQ 信号。

测试 GPIO 示例：

```
#define PERF_GPIO_SET()    bsp_gpio_write(&perf_gpio, BSP_GPIO_HIGH)
#define PERF_GPIO_CLEAR()  bsp_gpio_write(&perf_gpio, BSP_GPIO_LOW)

bsp_status_t sensor_read_data(sensor_t *dev,
                              uint8_t *data,
                              size_t length)
{
    bsp_status_t status;

    PERF_GPIO_SET();

    status = bsp_i2c_write_read(dev->bus,
                                &dev->data_reg,
                                1U,
                                data,
                                length);

    PERF_GPIO_CLEAR();

    return status;
}
```

需要区分：

```
GPIO 高电平宽度 = 驱动 API 总耗时
总线波形宽度 = 实际硬件传输耗时
二者差值 = 锁等待、调度、软件处理和收尾开销
```

### 16.2.4 总线带宽测试

理论吞吐量：

```
吞吐量 = 有效数据字节数 / 总事务时间
```

SPI 理论吞吐量：

```
T_theoretical = f_spi × bits_per_word / 8
```

例如：

```
SPI 时钟 = 20 MHz
数据宽度 = 8 bit

理论吞吐量 = 20,000,000 / 8
           = 2.5 MB/s
```

如果一次事务发送：

```
命令：1 字节
地址：3 字节
有效数据：1024 字节
总线事务时间：420 us
```

则有效吞吐量为：

```
Throughput = 1024 / 420 us
           ≈ 2.44 MB/s
```

若加入命令和地址后的总线有效率：

```
Efficiency = 1024 / (1024 + 1 + 3)
           ≈ 99.61%
```

对于小包事务，固定开销占比更高：

```
Efficiency = payload / (command + address + payload)
```

因此，小包设备不应只看总线理论频率，还需要测量：

- CS 拉低到拉高的时间；
- DMA 启动延迟；
- 每个事务之间的空闲时间；
- RTOS 锁等待时间；
- 多线程竞争下的最坏延迟。

### 16.2.5 CPU 占用率测试

RTOS 系统可以使用空闲任务统计 CPU 占用。

```
static volatile uint32_t idle_counter;

void idle_hook(void)
{
    idle_counter++;
}
```

在固定窗口内采样：

```
typedef struct {
    uint32_t idle_before;
    uint32_t idle_after;
    uint32_t window_ms;
} cpu_load_sample_t;
```

基本计算：

```
CPU 利用率 = 1 - 空闲时间 / 测试窗口时间
```

在 FreeRTOS 中，推荐使用运行时间统计接口或任务统计接口，分别观察：

- 总体 CPU 占用；
- 驱动线程占用；
- ISR 执行时间；
- 总线服务线程占用；
- 日志线程占用。

对 DMA 驱动与中断驱动进行对比：

|指标|中断逐字节|DMA|
|---|---|---|
|CPU 中断次数|高|低|
|小包延迟|低|可能略高|
|大包 CPU 占用|高|低|
|实现复杂度|低|中高|
|Cache 一致性要求|低|高|
|适合大数据传输|差|好|
|适合极短控制事务|好|未必|

### 16.2.6 内存测量

需要分别统计：

```
静态 Flash：
  .text
  .rodata

静态 RAM：
  .data
  .bss

运行时 RAM：
  设备对象
  总线对象
  锁和事件
  DMA 缓冲区
  线程栈
  堆内存
```

通过链接器 map 文件确认：

```
.text      驱动代码和常量函数
.rodata    配置表、寄存器表、字符串
.data      有初始值的可写变量
.bss       无初始值的静态变量
```

线程栈水位测试：

```
size_t osal_thread_stack_watermark(void *thread)
{
    /*
     * 返回线程栈的最小剩余空间。
     * 实际实现依赖具体 RTOS。
     */
    return rtos_get_stack_high_water_mark(thread);
}
```

测试要求：

- 在最复杂业务路径下运行；
- 打开所有日志；
- 触发所有错误恢复路径；
- 触发最大并发线程数；
- 至少保留 20%~30% 栈余量；
- 对中断栈、任务栈和 DMA 缓冲区分别检查。

### 16.2.7 最坏执行时间测试

平均值不能证明实时性。必须构造最坏条件：

```
多个线程同时访问同一总线
最高优先级线程周期性抢占
总线设备插入等待
设备产生 NACK
DMA 传输接近超时
日志输出同时发生
Cache 未命中
系统处于高负载
```

测试目标应定义为：

```
驱动单次读写最大延迟 <= 500 us
IRQ 到线程开始处理 <= 100 us
总线恢复完成 <= 5 ms
设备恢复完成 <= 50 ms
```

示例测试断言：

```
#define SENSOR_READ_MAX_US 500U

static bool sensor_read_meets_deadline(sensor_t *dev,
                                       uint8_t *data,
                                       size_t length)
{
    uint32_t elapsed_us = 0U;
    bsp_status_t status;

    status = measured_sensor_read(dev, data, length, &elapsed_us);

    return status == BSP_OK && elapsed_us <= SENSOR_READ_MAX_US;
}
```

测试报告必须说明：

- 测试平台；
- CPU 主频；
- 编译选项；
- Cache 状态；
- RTOS 配置；
- 总线频率；
- 温度和电压条件；
- 测试数据量；
- 最小、平均、最大和百分位延迟。

---

## 16.3 驱动单元测试

### 16.3.1 Mock 总线设计

驱动单元测试不应依赖真实 I2C 控制器。应提供可注入的总线操作。

```
typedef struct {
    bsp_status_t (*write)(void *ctx,
                          uint8_t address,
                          const uint8_t *data,
                          size_t length);

    bsp_status_t (*read)(void *ctx,
                         uint8_t address,
                         uint8_t *data,
                         size_t length);

    void *ctx;
} mock_bus_ops_t;
```

Mock 设备：

```
typedef struct {
    uint8_t registers[256];
    uint32_t read_count;
    uint32_t write_count;
    bsp_status_t forced_status;
} mock_sensor_bus_t;
```

Mock 读取：

```
static bsp_status_t mock_bus_read(void *ctx,
                                  uint8_t address,
                                  uint8_t *data,
                                  size_t length)
{
    mock_sensor_bus_t *mock = ctx;

    if (mock == NULL || data == NULL || length == 0U) {
        return BSP_EINVAL;
    }

    mock->read_count++;

    if (mock->forced_status != BSP_OK) {
        return mock->forced_status;
    }

    if (address != 0x68U) {
        return BSP_ENODEV;
    }

    for (size_t i = 0U; i < length; ++i) {
        data[i] = mock->registers[i];
    }

    return BSP_OK;
}
```

### 16.3.2 单元测试重点

至少覆盖：

- 参数为空；
- 长度为零；
- 设备 ID 正确；
- 设备 ID 错误；
- I2C NACK；
- 超时；
- 重试成功；
- 重试耗尽；
- 初始化中途失败；
- 反初始化后重复调用；
- 多实例之间状态隔离；
- 设备状态非法；
- 传输长度超限；
- 总线锁获取失败。

示例：

```
static void test_probe_rejects_invalid_id(void)
{
    mock_sensor_bus_t mock = {0};
    sensor_t sensor = {0};

    mock.registers[0] = 0x00U;
    sensor.bus = create_mock_bus(&mock);

    bsp_status_t status = sensor_probe(&sensor);

    TEST_ASSERT_EQUAL(BSP_ENODEV, status);
}
```

---

## 16.4 集成测试与板级验证

### 16.4.1 集成测试分层

```
驱动单元测试
  |
总线适配层测试
  |
真实硬件接口测试
  |
多设备并发测试
  |
低功耗和恢复测试
  |
系统长期稳定性测试
```

### 16.4.2 板级测试项目

|测试项目|测试目的|
|---|---|
|上电探测|验证时序、电源和复位|
|连续读写|验证基本通信稳定性|
|最大频率|验证总线时序裕量|
|多设备竞争|验证锁和调度|
|热插拔或掉电|验证恢复能力|
|长时间运行|发现泄漏、计数器溢出和状态积累|
|温度范围测试|验证时钟和设备时序|
|低电压测试|验证电源边界和通信错误处理|
|EMI/噪声环境|验证错误检测和恢复|
|固件升级后恢复|验证初始化和配置持久性|

### 16.4.3 总线故障注入

I2C 常见故障：

- SDA 被拉低；
- 从设备不应答；
- SCL 被拉低；
- 传输中途掉电；
- 设备返回错误寄存器值。

SPI 常见故障：

- MISO 常高；
- MISO 常低；
- CS 时序错误；
- DMA 提前结束；
- 数据长度配置错误。

故障注入后应验证：

```
是否在规定时间内返回
是否产生明确错误码
是否释放总线锁
是否停止 DMA
是否关闭或清除 IRQ
是否支持重新初始化
是否记录诊断信息
是否影响其他设备
```

### 16.4.4 I2C 总线恢复

当 SDA 被设备拉低时，可以使用 GPIO 模式输出若干 SCL 脉冲，尝试推动从设备完成未结束的字节传输。

```
static bsp_status_t i2c_bus_recover(void)
{
    bsp_gpio_config_as_open_drain(&scl_gpio);
    bsp_gpio_config_as_input(&sda_gpio);

    for (uint32_t i = 0U; i < 9U; ++i) {
        bsp_gpio_write(&scl_gpio, BSP_GPIO_LOW);
        bsp_delay_us(5U);

        bsp_gpio_write(&scl_gpio, BSP_GPIO_HIGH);
        bsp_delay_us(5U);

        if (bsp_gpio_read_level(&sda_gpio) == BSP_GPIO_HIGH) {
            break;
        }
    }

    /* 生成 STOP：SDA 由低到高，且 SCL 保持高 */
    bsp_gpio_write(&sda_gpio, BSP_GPIO_LOW);
    bsp_gpio_write(&scl_gpio, BSP_GPIO_HIGH);
    bsp_gpio_write(&sda_gpio, BSP_GPIO_HIGH);

    return i2c_controller_reinit();
}
```

注意事项：

- 恢复期间必须持有总线所有权；
- 不能与其他线程并行访问总线；
- 需要限制恢复次数；
- 恢复失败后应进入设备故障状态；
- 某些芯片不允许在控制器仍启用时切换 GPIO 复用。

---

## 16.5 BSP 代码审查清单

### 架构边界

- [ ]  通用驱动不包含具体芯片头文件。
- [ ]  通用驱动不依赖具体 RTOS API。
- [ ]  板级资源集中定义。
- [ ]  芯片适配代码与设备逻辑分离。
- [ ]  依赖方向单向且可追踪。

### 接口设计

- [ ]  所有公共接口检查输入参数。
- [ ]  所有阻塞操作具有超时。
- [ ]  错误码不直接暴露厂商枚举。
- [ ]  支持多设备实例。
- [ ]  接口明确线程上下文和 ISR 上下文限制。

### 并发与实时性

- [ ]  共享总线有统一锁。
- [ ]  锁顺序已经定义。
- [ ]  没有在 ISR 中阻塞。
- [ ]  高优先级线程不会长期等待低优先级线程。
- [ ]  已测试最大延迟，而不仅是平均延迟。

### DMA 和内存

- [ ]  DMA 缓冲区满足对齐要求。
- [ ]  正确执行 Cache clean/invalidate。
- [ ]  DMA 完成前不会修改发送缓冲区。
- [ ]  DMA 超时后能够中止并清理状态。
- [ ]  没有隐藏的栈上大数组。

### 生命周期

- [ ]  初始化顺序明确。
- [ ]  初始化失败可以回滚。
- [ ]  反初始化不会泄漏资源。
- [ ]  suspend/resume 行为已定义。
- [ ]  重复初始化和重复释放行为明确。

### 可诊断性

- [ ]  记录设备实例和总线编号。
- [ ]  记录原始硬件错误。
- [ ]  统计超时、重试和恢复次数。
- [ ]  故障状态不会被静默吞掉。
- [ ]  关键状态可通过诊断接口读取。

---

## 16.6 进阶学习方向

### 方向一：统一设备模型

深入学习：

- Linux device model；
- Linux kernel driver；
- Device Tree；
- platform device；
- regmap；
- Linux 电源管理；
- IIO、SPI、I2C、TTY 等子系统。

目标是理解复杂系统如何通过标准设备模型完成：

```
设备发现
资源绑定
驱动匹配
电源管理
设备注销
热插拔
```

### 方向二：Zephyr 设备树和驱动模型

重点掌握：

- `DEVICE_DT_DEFINE`；
- `DT_INST_FOREACH_STATUS_OKAY`；
- device binding；
- devicetree overlay；
- device power management；
- Zephyr 的 GPIO、I2C、SPI API。

这适合构建跨 MCU、跨板卡的现代 RTOS BSP。

### 方向三：汽车电子 MCAL 与 AUTOSAR

重点关注：

- MCU Abstraction Layer；
- ECU Abstraction；
- Complex Device Driver；
- Port、Dio、Spi、I2c、Can；
- BSW Module；
- 配置生成；
- 运行时保护；
- 功能安全和诊断。

其核心思想与工业级 BSP 类似：**资源配置、硬件抽象、标准接口、可追踪性和生命周期管理**。

### 方向四：功能安全

进一步学习：

- ISO 26262；
- IEC 61508；
- MISRA C；
- 防御式编程；
- 运行时检查；
- 看门狗；
- 内存保护；
- 错误传播；
- 安全机制独立性。

BSP 层通常是安全链路的重要基础，因为时钟、复位、中断、看门狗和存储保护都属于底层可信根的一部分。

### 方向五：形式化接口验证

对关键驱动接口建立不变量：

```
设备未初始化时不能读写
DMA 运行中不能释放缓冲区
持有总线锁时不能递归获取同一非递归锁
超时退出后必须释放资源
恢复失败后设备必须进入明确错误状态
```

可以使用：

- CMocka；
- Unity；
- Ceedling；
- CBMC；
- Frama-C；
- clang static analyzer；
- Coverity；
- ThreadSanitizer；
- AddressSanitizer。

---

## 16.7 最终实战项目

建议完成一个“跨平台环境采集 BSP”项目：

### 平台

```
平台 A：STM32 + FreeRTOS
平台 B：NXP + Zephyr
```

### 设备

```
温度传感器：I2C
IMU：SPI + FIFO + DMA
外部 Flash：SPI + DMA
状态输入：GPIO + 外部中断
```

### 功能要求

- 同一份设备核心驱动；
- 两套 SoC 总线适配；
- 两套 OSAL；
- 板级资源表；
- 多实例设备；
- 同步和异步接口；
- DMA Cache 维护；
- I2C 总线恢复；
- 设备掉电恢复；
- 统一错误码；
- 性能统计；
- Mock 单元测试；
- 板级长稳测试。

### 验收指标

|指标|目标|
|---|---|
|核心驱动代码复用率|≥ 80%|
|驱动 API 最大阻塞时间|有明确上限|
|I2C 故障恢复时间|≤ 10 ms|
|SPI DMA CPU 占用|≤ 5%|
|设备初始化失败回滚|100% 覆盖|
|单元测试覆盖率|核心逻辑 ≥ 90%|
|连续运行时间|≥ 168 h|
|多实例状态串扰|0 次|
|未处理错误路径|0 个|
|静态分析高等级问题|0 个|

### 最终工程输出

```
bsp/
├── common/
├── hal/
│   ├── stm32/
│   └── nxp/
├── osal/
│   ├── freertos/
│   └── zephyr/
├── board/
│   ├── board_stm32/
│   └── board_nxp/
├── drivers/
│   ├── temperature/
│   ├── imu/
│   └── flash/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fault_injection/
└── docs/
    ├── architecture.md
    ├── timing_report.md
    └── porting_guide.md
```

完成该项目后，应能够独立承担：

- 多 MCU BSP 建设；
- 传感器和外设驱动跨平台移植；
- RTOS 适配层设计；
- 板级资源管理；
- DMA 和缓存一致性问题定位；
- 总线故障恢复；
- 驱动性能测试；
- 工业产品 BSP 的长期维护。