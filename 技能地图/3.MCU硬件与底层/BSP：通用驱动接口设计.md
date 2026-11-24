
## 1. 学习目标

### 理解

- 理解 BSP 在硬件抽象层、驱动层、服务层和应用层之间的职责边界。
- 理解“板级差异”和“芯片级差异”的来源，以及为什么不能把所有代码都塞进 BSP。
- 理解通用驱动接口设计中的对象模型、状态机、能力描述、错误模型和并发模型。
- 理解轮询、中断、DMA、异步回调和零拷贝接口之间的关系。

### 掌握

- 掌握 BSP 分层结构和目录组织方法。
- 掌握基于函数表、设备对象和能力描述的通用驱动接口设计。
- 掌握 GPIO、UART、SPI、I2C 等常见外设接口的抽象方法。
- 掌握驱动生命周期：注册、初始化、打开、配置、读写、停止、释放。
- 掌握超时、并发访问、错误恢复、资源回滚和低功耗处理。

### 精通

- 能设计跨 MCU、跨芯片厂商的稳定驱动接口。
- 能区分硬件抽象、协议驱动、设备驱动和业务适配层。
- 能处理 DMA 缓冲区一致性、缓存对齐、ISR 上下文限制、优先级反转等问题。
- 能用统一接口支持同步、异步、阻塞、非阻塞和 DMA 模式。
- 能建立 BSP 的版本、测试、配置生成和持续集成机制。

### 能够设计

- 设计一个可移植的 BSP 架构。
- 设计支持多实例、能力查询、错误码、异步回调和电源管理的通用驱动框架。
- 设计驱动接口的兼容性策略和硬件差异隔离方案。
- 为量产产品建立可测试、可诊断、可扩展的板级支持包。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、结构体、函数指针、`const`、`volatile`、链接属性。
- 熟悉 MCU 启动流程、链接脚本、内存映射和中断向量表。
- 熟悉 GPIO、UART、SPI、I2C、定时器、DMA 的基本工作原理。
- 了解 RTOS 任务、互斥锁、信号量、队列和临界区。
- 了解编译、链接、弱符号、静态库和条件编译。
- 了解 Cache、一致性、内存屏障和 DMA 访问约束。

### 技能要求

- 能阅读芯片参考手册和厂商 HAL/LL 源码。
- 能配置时钟、引脚复用、中断和 DMA。
- 能使用逻辑分析仪、示波器和调试器定位驱动问题。
- 能编写基本的单元测试、接口测试和故障注入测试。
- 能分析 map 文件、反汇编和实时性能数据。

---

## 3. 技术概述

### 3.1 BSP 的定义

BSP，Board Support Package，板级支持包，是一组使操作系统或应用软件能够运行在特定硬件板卡上的软件集合。

典型 BSP 包含：

- 启动文件和异常向量表。
- 时钟、复位和电源初始化。
- PinMux、GPIO 和外设实例配置。
- 芯片底层驱动适配。
- 板级设备描述。
- 调试串口、日志、看门狗、存储器初始化。
- RTOS 适配代码。
- 板级测试和诊断代码。

BSP 的核心目标不是“封装所有硬件代码”，而是：

> **将板卡差异、芯片差异和外设连接关系隔离在稳定的软件边界内。**

### 3.2 BSP、HAL、驱动和业务的边界

```
应用层
  |
协议栈 / 中间件 / 设备服务
  |
通用设备驱动接口
  |
具体设备驱动，例如 W25Q、BME280、IMU
  |
芯片 HAL / LL / 寄存器驱动
  |
BSP 板级配置，例如引脚、DMA、时钟、IRQ、设备实例
  |
MCU / SoC 硬件
```

推荐职责划分：

|层级|主要职责|不应承担的职责|
|---|---|---|
|BSP|板卡连接关系、资源分配、启动初始化|业务协议、复杂设备协议|
|MCU HAL|芯片寄存器和外设控制|板级设备拓扑|
|总线驱动|UART/SPI/I2C 控制器|具体传感器寄存器协议|
|设备驱动|设备识别、寄存器访问、状态管理|直接操作应用业务|
|设备服务|把设备转换为系统服务|芯片寄存器细节|
|应用层|业务逻辑和产品行为|直接访问寄存器|

### 3.3 通用驱动接口的核心模型

通用驱动接口通常由以下部分组成：

```
设备对象
  ├── 设备类型
  ├── 实例编号
  ├── 状态
  ├── 能力集合
  ├── 私有上下文
  ├── 操作函数表
  ├── 锁与同步对象
  └── 电源管理状态
```

驱动接口需要明确四个问题：

1. 谁拥有资源？
2. 函数是否可重入？
3. 函数能否在 ISR 中调用？
4. 失败后资源和设备状态是什么？

---

## 4. 核心特性横向对比

### 4.1 驱动接口抽象方式对比

|方案|实现方式|优点|缺点|适用场景|
|---|---|---|---|---|
|直接调用 HAL|应用直接调用厂商 HAL|开发快、代码少|强耦合、难迁移、难测试|原型、一次性项目|
|宏封装|通过宏映射不同平台|编译期无开销|类型检查弱、调试困难|简单 GPIO、板级配置|
|函数封装|统一 C 函数接口|易理解、可测试|多实例扩展不自然|小型项目|
|函数表|对象加 `ops` 函数表|可替换实现、支持多实例|有间接调用开销|工业产品、跨平台|
|C++ 虚函数|抽象基类和多态|类型系统完整、扩展性强|可能有 ROM/RAM/ABI 成本|C++ 固件|
|设备注册表|驱动动态注册和查找|支持模块化、多设备|生命周期复杂|Linux 风格系统、复杂 RTOS|

### 4.2 访问模式对比

|模式|调用特征|延迟|CPU 占用|实时性|适用场景|
|---|---|---|---|---|---|
|阻塞轮询|一直等待完成|可预测但较长|高|中|低速、初始化|
|中断同步|启动后等待事件|中等|低|高|普通收发|
|非阻塞中断|提交后立即返回|提交延迟低|低|高|RTOS 主循环|
|DMA|外设直接访问内存|吞吐高|很低|高|大块数据|
|DMA + 回调|DMA 完成通知上层|高吞吐|很低|高|UART/SPI 音视频|
|DMA + 队列|完成事件投递任务|可扩展|低|取决于任务调度|大型系统|

### 4.3 接口抽象粒度对比

|粒度|示例|优点|风险|
|---|---|---|---|
|寄存器级|`write_reg(addr, value)`|灵活|上层严重依赖设备细节|
|总线级|`spi_transfer()`|能复用多个设备|设备协议仍需重复实现|
|设备级|`imu_read_sample()`|符合应用语义|设备类型差异较大|
|服务级|`motion_get_orientation()`|对应用友好|需要稳定的服务层和数据模型|

推荐采用：

> **BSP 提供资源和总线，设备驱动提供设备语义，服务层提供业务语义。**

---

## 5. 底层原理与功能特性深度解析

## 5.1 设备对象与函数表

核心定义：

```
#ifndef BSP_DEVICE_H
#define BSP_DEVICE_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef enum {
    BSP_OK          = 0,
    BSP_EINVAL      = -1,
    BSP_ENODEV      = -2,
    BSP_EBUSY       = -3,
    BSP_ETIMEOUT    = -4,
    BSP_EIO         = -5,
    BSP_ENOTSUP     = -6,
    BSP_ESTATE      = -7,
    BSP_ENOMEM      = -8,
} bsp_status_t;

typedef enum {
    BSP_DEV_UNINIT = 0,
    BSP_DEV_READY,
    BSP_DEV_OPEN,
    BSP_DEV_ERROR,
} bsp_dev_state_t;

typedef struct bsp_device bsp_device_t;

typedef struct {
    int (*init)(bsp_device_t *dev);
    int (*deinit)(bsp_device_t *dev);
    int (*open)(bsp_device_t *dev);
    int (*close)(bsp_device_t *dev);
    int (*ioctl)(bsp_device_t *dev, uint32_t cmd, void *arg);
    int (*read)(bsp_device_t *dev, void *buf, size_t len, uint32_t timeout_ms);
    int (*write)(bsp_device_t *dev,
                 const void *buf,
                 size_t len,
                 uint32_t timeout_ms);
} bsp_device_ops_t;

struct bsp_device {
    const char *name;
    uint16_t id;
    uint16_t type;
    bsp_dev_state_t state;
    const bsp_device_ops_t *ops;
    void *priv;
    uint32_t capabilities;
};

#define BSP_CAP_READ       (1u << 0)
#define BSP_CAP_WRITE      (1u << 1)
#define BSP_CAP_ASYNC      (1u << 2)
#define BSP_CAP_DMA        (1u << 3)
#define BSP_CAP_POWER      (1u << 4)
#define BSP_CAP_CONFIG     (1u << 5)

#endif
```

该设计的关键点：

- `ops` 是行为抽象。
- `priv` 保存具体驱动上下文，不暴露给上层。
- `capabilities` 用于运行时能力查询。
- `state` 防止未初始化、重复打开和非法关闭。
- `timeout_ms` 显式定义阻塞边界，避免无限等待。

函数表位于只读存储区时，通常不会占用 RAM：

```
static const bsp_device_ops_t uart_ops = {
    .init = uart_init,
    .deinit = uart_deinit,
    .open = uart_open,
    .close = uart_close,
    .ioctl = uart_ioctl,
    .read = uart_read,
    .write = uart_write,
};
```

## 5.2 生命周期状态机

推荐状态：

```
UNINIT
  | init 成功
READY
  | open 成功
OPEN
  | close 成功
READY

任意状态 --严重硬件错误--> ERROR
ERROR --deinit/recovery--> UNINIT
```

状态转换必须由驱动内部维护，不能完全交给调用者。

```
static int dev_open(bsp_device_t *dev)
{
    if (dev == NULL || dev->ops == NULL || dev->ops->open == NULL) {
        return BSP_EINVAL;
    }

    if (dev->state != BSP_DEV_READY) {
        return BSP_ESTATE;
    }

    int rc = dev->ops->open(dev);
    if (rc == BSP_OK) {
        dev->state = BSP_DEV_OPEN;
    }

    return rc;
}
```

## 5.3 GPIO 通用接口

GPIO 的抽象应关注行为，而不是把端口寄存器暴露给应用。

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
    uint8_t port;
    uint8_t pin;
    bsp_gpio_mode_t mode;
    bool pull_up;
    bool pull_down;
} bsp_gpio_config_t;

int bsp_gpio_configure(const bsp_gpio_config_t *cfg);
int bsp_gpio_write(uint8_t port, uint8_t pin, bsp_gpio_level_t level);
int bsp_gpio_read(uint8_t port, uint8_t pin, bsp_gpio_level_t *level);
```

不推荐：

```
#define LED_PORT GPIOA
#define LED_PIN  (1u << 5)

GPIOA->ODR |= LED_PIN;
```

问题：

- 应用依赖具体 MCU 寄存器。
- `|=` 可能产生读改写竞争。
- 不支持 GPIO 扩展芯片。
- 无法统一模拟 GPIO、外部 GPIO 和测试桩。

推荐：

```
int board_led_set(bool on)
{
    return bsp_gpio_write(
        BOARD_LED_GPIO_PORT,
        BOARD_LED_GPIO_PIN,
        on ? BSP_GPIO_HIGH : BSP_GPIO_LOW);
}
```

## 5.4 UART 通用接口

UART 接口通常需要同时支持：

- 阻塞发送。
- 非阻塞发送。
- DMA 发送。
- 接收环形缓冲区。
- 空闲线检测。
- 错误统计。
- 流控配置。

```
typedef enum {
    BSP_UART_PARITY_NONE = 0,
    BSP_UART_PARITY_EVEN,
    BSP_UART_PARITY_ODD,
} bsp_uart_parity_t;

typedef struct {
    uint32_t baudrate;
    uint8_t data_bits;
    uint8_t stop_bits;
    bsp_uart_parity_t parity;
    bool hw_flow_control;
} bsp_uart_config_t;

typedef struct {
    uint32_t rx_overrun;
    uint32_t framing_error;
    uint32_t parity_error;
    uint32_t dma_error;
} bsp_uart_stats_t;

int bsp_uart_configure(bsp_device_t *dev,
                       const bsp_uart_config_t *cfg);

int bsp_uart_send(bsp_device_t *dev,
                  const void *data,
                  size_t len,
                  uint32_t timeout_ms);

int bsp_uart_receive(bsp_device_t *dev,
                     void *data,
                     size_t len,
                     uint32_t timeout_ms);

int bsp_uart_get_stats(bsp_device_t *dev,
                       bsp_uart_stats_t *stats);
```

UART 接收环形缓冲区必须处理两个并发访问者：

```
ISR/DMA 写入 head
任务读取 tail
```

单生产者、单消费者情况下，可以使用无锁环形缓冲区，但必须满足：

- `head` 和 `tail` 使用合适的整数宽度。
- 生产者先写数据，再提交 `head`。
- 消费者先读取 `head`，再读取数据。
- 多核系统需要内存屏障。
- Cache 系统需要处理 DMA 一致性。

示意代码：

```
typedef struct {
    uint8_t *buf;
    size_t capacity;
    volatile size_t head;
    volatile size_t tail;
} bsp_ringbuf_t;

static size_t ringbuf_used(const bsp_ringbuf_t *rb)
{
    size_t head = rb->head;
    size_t tail = rb->tail;

    if (head >= tail) {
        return head - tail;
    }
    return rb->capacity - tail + head;
}

static bool ringbuf_push_isr(bsp_ringbuf_t *rb, uint8_t byte)
{
    size_t next = rb->head + 1u;
    if (next == rb->capacity) {
        next = 0;
    }

    if (next == rb->tail) {
        return false;
    }

    rb->buf[rb->head] = byte;

    /*
     * 在多核或弱内存序平台上，此处需要 release barrier，
     * 确保数据写入先于 head 提交。
     */
    rb->head = next;
    return true;
}
```

注意：`volatile` 只保证编译器不会优化掉访问，**不等价于原子性，也不等价于内存屏障**。

## 5.5 SPI 通用接口

SPI 的通用接口必须描述片选、模式、频率和数据宽度：

```
typedef struct {
    uint32_t frequency_hz;
    uint8_t mode;          /* 0~3 */
    uint8_t data_bits;     /* 常见为 8 或 16 */
    bool lsb_first;
    uint8_t cs_index;
} bsp_spi_config_t;

typedef struct {
    const void *tx;
    void *rx;
    size_t len;
    uint32_t timeout_ms;
} bsp_spi_transfer_t;

int bsp_spi_transfer(bsp_device_t *dev,
                     const bsp_spi_transfer_t *transfer);
```

SPI 设备驱动不应自己直接控制控制器寄存器，而应通过总线接口：

```
static int flash_read_id(flash_ctx_t *ctx, uint32_t *jedec_id)
{
    uint8_t command = 0x9F;
    uint8_t response[3];

    bsp_spi_transfer_t transfer = {
        .tx = &command,
        .rx = response,
        .len = sizeof(response),
        .timeout_ms = 20,
    };

    int rc = bsp_spi_transfer(ctx->spi, &transfer);
    if (rc != BSP_OK) {
        return rc;
    }

    *jedec_id = ((uint32_t)response[0] << 16) |
                ((uint32_t)response[1] << 8) |
                response[2];

    return BSP_OK;
}
```

SPI 总线共享时需要处理：

- 不同设备模式切换。
- 片选时序。
- 总线锁。
- DMA 缓冲区。
- 传输失败后的片选释放。
- 设备切换后的恢复配置。

## 5.6 I2C 错误恢复

I2C 的典型现场问题是从设备在传输中复位或异常，导致 SDA 被拉低，控制器持续等待 BUSY 清除。

通用恢复流程：

```
停止当前控制器
配置 SCL 为 GPIO 开漏
最多输出 9 个时钟脉冲
检查 SDA 是否释放
产生 STOP 条件
重新初始化 I2C 外设
返回错误给上层
```

不要简单地无限等待：

```
while (I2C1->SR2 & I2C_SR2_BUSY) {
}
```

应使用超时：

```
static int wait_bus_idle(uint32_t timeout_ms)
{
    uint32_t start = bsp_time_ms();

    while (i2c_bus_busy()) {
        if ((bsp_time_ms() - start) >= timeout_ms) {
            return BSP_ETIMEOUT;
        }
    }

    return BSP_OK;
}
```

---

## 6. 性能量化分析

以下数据为 Cortex-M4F、主频 168 MHz、零等待 SRAM、编译器 `-O2` 下的**典型测量范围**，实际结果必须使用目标芯片和目标编译选项实测。

### 6.1 抽象调用开销

|调用方式|典型额外 CPU 周期|
|---|---|
|直接寄存器访问|2~8|
|静态内联封装|2~10|
|普通 C 函数|8~20|
|函数表间接调用|15~35|
|RTOS 互斥锁保护|80~500|
|中断提交一次 DMA|100~800|
|任务切换|1~10 us|

函数表调用开销可以近似为：

Tindirect=Tload_object+Tload_ops+TbranchTindirect​=Tload_object​+Tload_ops​+Tbranch​

在 168 MHz 下，35 个周期约为：

35/168MHz≈208ns35/168MHz≈208ns

对于 UART、SPI、I2C 等微秒级外设传输，这个成本通常可以接受。对于 10 MHz 以上 GPIO 翻转或 bit-bang 协议，则可能不可接受。

### 6.2 UART 吞吐

UART 8N1 每个字节通常消耗 10 bit 时间：

Tbyte=10baudrateTbyte​=baudrate10​

115200 baud 下：

Tbyte=10115200≈86.8usTbyte​=11520010​≈86.8us

有效吞吐：

Throughput=11520010=11520Byte/sThroughput=10115200​=11520Byte/s

因此，即使抽象层多增加 1 us，单字节传输影响也只有约 1.15%。但如果每个字节都获取 RTOS 锁并唤醒任务，调度开销会成为主要瓶颈。

### 6.3 DMA 与中断的比较

假设 UART 接收 1024 字节：

|方式|中断次数|CPU 介入|典型 CPU 时间|
|---|---|---|---|
|每字节中断|1024|每字节|50~200 us|
|FIFO 阈值中断|32~128|分批|10~50 us|
|DMA + 空闲线|1~数次|块级|2~15 us|

DMA 的瓶颈通常不在 CPU，而在：

- Cache 一致性。
- 内存带宽。
- DMA 描述符配置。
- 缓冲区生命周期。
- 数据包边界检测。

### 6.4 RAM 成本

每个设备对象的典型成本：

```
基础对象：约 24~48 字节
驱动私有上下文：约 32~256 字节
环形缓冲区：由吞吐和最大延迟决定
互斥锁/信号量：约 40~100 字节，取决于 RTOS
```

环形缓冲区最小容量可以按下式估算：

C≥R×Tblock+MC≥R×Tblock​+M

其中：

- CC：缓冲区字节数。
- RR：输入速率，Byte/s。
- TblockTblock​：任务最大阻塞时间。
- MM：安全余量。

例如 UART 115200、任务最大阻塞 20 ms、安全余量 25%：

C≥11520×0.02×1.25=288ByteC≥11520×0.02×1.25=288Byte

应选择不小于 512 字节的环形缓冲区。

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否只有一块板卡且生命周期短？
├── 是
│   ├── 是否需要快速验证？
│   │   ├── 是 -> 直接使用 HAL + 薄封装
│   │   └── 否 -> 使用统一 C 接口
│   └── 是否预计未来换 MCU？
│       ├── 是 -> 使用设备对象 + 函数表
│       └── 否 -> 使用静态接口封装
└── 否
    ├── 是否存在多个硬件实例？
    │   ├── 是 -> 设备对象 + 私有上下文
    │   └── 否 -> 统一接口 + 板级配置
    ├── 是否需要异步和 DMA？
    │   ├── 是 -> 能力位 + 事件回调 + DMA 缓冲管理
    │   └── 否 -> 同步接口 + 明确超时
    ├── 是否运行 RTOS？
    │   ├── 是 -> 驱动锁、事件、任务上下文约束
    │   └── 否 -> 中断状态机、无阻塞接口
    └── 是否需要跨芯片平台复用？
        ├── 是 -> BSP / HAL / Driver 分层
        └── 否 -> 保持接口简单，避免过度抽象
```

### 7.2 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|产品调试串口|稳定、低复杂度|固定 UART 实例 + 日志接口|无需完整设备注册系统|
|多路传感器|多实例、I2C/SPI 共享|总线驱动 + 设备驱动对象|隔离总线和设备协议|
|高速数据采集|吞吐、低 CPU 占用|DMA + 双缓冲 + 事件队列|避免逐字节中断|
|多型号产品|引脚和外设差异|编译期 board config|保持业务代码不变|
|热插拔模块|动态识别和故障恢复|设备注册表 + 状态机|支持插拔和重连|
|安全启动设备|资源约束、可信执行|静态注册 + 只读配置|减少动态行为和攻击面|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **接口稳定，具体实现可替换。**
2. **BSP 描述资源，不承载业务协议。**
3. **所有可能阻塞的函数都显式带超时。**
4. **ISR 只做最小工作，复杂处理放到任务上下文。**
5. **设备状态和错误状态必须可观测。**
6. **资源初始化采用可回滚设计。**
7. **能力不足必须返回 `BSP_ENOTSUP`，不能静默降级。**
8. **DMA 缓冲区的所有权必须明确。**
9. **避免在公共接口中暴露厂商 HAL 类型。**
10. **接口定义优先于实现，先固定调用契约。**

### 8.2 推荐目录结构

```
bsp/
├── include/
│   ├── bsp_device.h
│   ├── bsp_gpio.h
│   ├── bsp_uart.h
│   ├── bsp_spi.h
│   └── bsp_i2c.h
├── core/
│   ├── bsp_device.c
│   └── bsp_registry.c
├── chip/
│   └── stm32h7/
│       ├── bsp_uart_stm32.c
│       ├── bsp_spi_stm32.c
│       └── bsp_clock_stm32.c
├── board/
│   ├── board_alpha/
│   │   ├── board_config.h
│   │   └── board_devices.c
│   └── board_beta/
│       ├── board_config.h
│       └── board_devices.c
├── drivers/
│   ├── w25qxx.c
│   ├── bme280.c
│   └── ina226.c
└── tests/
    ├── test_bsp_uart.c
    └── test_bsp_registry.c
```

### 8.3 选型决策矩阵

评分范围为 1~5：

|维度|直接 HAL|统一 C 接口|函数表对象|动态注册|
|---|---|---|---|---|
|开发速度|5|4|3|2|
|可移植性|1|3|5|5|
|ROM 成本|5|4|4|3|
|调试难度|5|4|3|2|
|多实例支持|2|3|5|5|
|动态扩展|1|2|4|5|
|认证可控性|4|5|5|3|

### 8.4 工业编码规范

- 公共接口使用固定宽度整数类型。
- 对外返回统一错误码，不直接暴露厂商错误码。
- 输入指针为空时返回 `BSP_EINVAL`。
- 长度参数使用 `size_t`。
- 只读参数使用 `const`。
- 中断共享变量使用合适的原子访问或临界区。
- 禁止驱动内部无限循环。
- 禁止在 ISR 中调用可能阻塞的 API。
- 驱动日志必须包含设备名、实例号和错误码。
- 错误路径需要释放已经获取的锁、DMA、片选和时钟资源。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：应用直接访问寄存器

错误代码：

```
void sensor_power_on(void)
{
    GPIOB->BSRR = GPIO_PIN_3;
    HAL_Delay(10);
}
```

根因：

- 应用依赖具体端口。
- 无法迁移到其他板卡。
- 延时接口和 GPIO 实现不可替换。

正确实现：

```
int sensor_power_on(void)
{
    int rc = bsp_gpio_write(BSP_SENSOR_EN_PORT,
                            BSP_SENSOR_EN_PIN,
                            BSP_GPIO_HIGH);
    if (rc != BSP_OK) {
        return rc;
    }

    return bsp_delay_ms(10);
}
```

风险影响：

- 更换 PCB 或 MCU 时需要修改大量业务代码。
- 无法对应用做主机单元测试。

### 9.2 错误二：无限等待硬件状态

错误代码：

```
while ((SPI1->SR & SPI_SR_TXE) == 0) {
}
```

根因：

- 外设时钟错误、总线锁死或硬件损坏时，任务永久阻塞。
- 看门狗只能被动复位，无法定位故障原因。

正确实现：

```
static int wait_flag(uint32_t timeout_ms)
{
    uint32_t start = bsp_time_ms();

    while (!spi_tx_ready()) {
        if ((bsp_time_ms() - start) >= timeout_ms) {
            spi_reset_peripheral();
            return BSP_ETIMEOUT;
        }
    }

    return BSP_OK;
}
```

风险影响：

- 任务卡死。
- 系统无法进入降级模式。
- 可能导致控制回路失控。

### 9.3 错误三：在 ISR 中调用阻塞接口

错误代码：

```
void USART1_IRQHandler(void)
{
    uint8_t ch = uart_read_byte();
    queue_send(rx_queue, &ch, WAIT_FOREVER);
}
```

根因：

- ISR 中没有任务切换和等待语义。
- 队列满时可能死锁或破坏实时性。

正确实现：

```
void USART1_IRQHandler(void)
{
    uint8_t ch;

    while (uart_hw_rx_ready()) {
        ch = uart_hw_read_byte();

        if (!ringbuf_push_isr(&rx_ring, ch)) {
            uart_stats.rx_overrun++;
        }
    }

    rtos_event_set_from_isr(RX_EVENT_AVAILABLE);
}
```

风险影响：

- 中断延迟扩大。
- 高优先级中断被阻塞。
- 系统出现不可重现的时序故障。

### 9.4 错误四：忽略 DMA Cache 一致性

错误代码：

```
void uart_start_dma(uint8_t *buf, size_t len)
{
    dma_start(buf, len);
}
```

根因：

- CPU Cache 中的数据和 RAM 中的数据不一致。
- DMA 读取旧数据，或 CPU 读取 DMA 尚未写回的数据。

正确实现：

```
int uart_start_dma_tx(const void *buf, size_t len)
{
    if (buf == NULL || len == 0) {
        return BSP_EINVAL;
    }

    uintptr_t addr = (uintptr_t)buf;

    if ((addr % BSP_CACHE_LINE_SIZE) != 0 ||
        (len % BSP_CACHE_LINE_SIZE) != 0) {
        return BSP_EINVAL;
    }

    bsp_cache_clean((void *)buf, len);
    return dma_start(buf, len);
}
```

实际项目也可以使用：

- 非 Cache 区域。
- 对齐的 DMA 专用内存池。
- 发送前 clean，接收后 invalidate。
- 链路层双缓冲。

风险影响：

- 数据偶发错误。
- 仅在高优化、特定负载或特定芯片上出现。
- 现场难以复现。

### 9.5 错误五：用 `volatile` 代替同步机制

错误代码：

```
volatile bool transfer_done;

void isr(void)
{
    transfer_done = true;
}

void task(void)
{
    while (!transfer_done) {
    }
}
```

根因：

- `volatile` 不保证原子性和内存序。
- 忙等待占用 CPU。
- 没有明确的事件清除和超时处理。

正确实现：

```
void isr(void)
{
    rtos_event_set_from_isr(TRANSFER_DONE_EVENT);
}

int wait_transfer(uint32_t timeout_ms)
{
    uint32_t events = 0;

    int rc = rtos_event_wait(TRANSFER_DONE_EVENT,
                             &events,
                             timeout_ms);
    if (rc != RTOS_OK) {
        return BSP_ETIMEOUT;
    }

    return BSP_OK;
}
```

### 9.6 错误六：初始化失败后不回滚

错误代码：

```
int sensor_init(void)
{
    clock_enable();
    gpio_configure();
    i2c_init();

    if (sensor_probe() != BSP_OK) {
        return BSP_EIO;
    }

    return BSP_OK;
}
```

问题：

- `sensor_probe()` 失败后时钟、GPIO、I2C 资源仍保持启用。
- 重试初始化时可能遇到脏状态。

正确实现：

```
int sensor_init(void)
{
    int rc;

    rc = clock_enable();
    if (rc != BSP_OK) {
        return rc;
    }

    rc = gpio_configure();
    if (rc != BSP_OK) {
        goto fail_clock;
    }

    rc = i2c_init();
    if (rc != BSP_OK) {
        goto fail_gpio;
    }

    rc = sensor_probe();
    if (rc != BSP_OK) {
        goto fail_i2c;
    }

    return BSP_OK;

fail_i2c:
    i2c_deinit();
fail_gpio:
    gpio_deconfigure();
fail_clock:
    clock_disable();
    return rc;
}
```

---

## 10. 多机制组合使用方案

## 10.1 推荐架构

```
应用任务
  |
设备服务接口
  |
通用设备对象
  |                 \
同步 API             异步 API
  |                   |
总线驱动             事件队列
  |                   |
芯片 HAL             ISR / DMA
  |
硬件外设
```

### 10.2 异步传输接口

```
typedef void (*bsp_transfer_cb_t)(bsp_device_t *dev,
                                  int result,
                                  size_t transferred,
                                  void *user);

typedef struct {
    const void *tx;
    void *rx;
    size_t len;
    uint32_t timeout_ms;
    bsp_transfer_cb_t callback;
    void *user;
} bsp_async_transfer_t;

int bsp_spi_transfer_async(bsp_device_t *dev,
                           const bsp_async_transfer_t *transfer);
```

异步状态机：

```
IDLE
  | submit
BUSY
  | DMA complete
COMPLETING
  | callback/event posted
IDLE

BUSY --error--> ERROR_RECOVERY
ERROR_RECOVERY --reset success--> IDLE
```

回调约束必须明确：

- 回调运行在 ISR 还是任务上下文。
- 回调是否允许再次提交传输。
- 回调参数指向的缓冲区何时失效。
- 回调是否可能并发执行。
- 失败时 `transferred` 的定义。

### 10.3 DMA 双缓冲框架

```
typedef struct {
    uint8_t *buffer[2];
    size_t buffer_size;
    uint8_t active;
    volatile bool ready[2];
} dma_double_buffer_t;

static void dma_rx_half_complete_isr(void)
{
    uint8_t completed = dma_ctx.active;

    bsp_cache_invalidate(dma_ctx.buffer[completed],
                         dma_ctx.buffer_size);

    dma_ctx.ready[completed] = true;
    dma_ctx.active ^= 1u;

    rtos_event_set_from_isr(DMA_BUFFER_READY_EVENT);
}
```

任务上下文：

```
static void acquisition_task(void *arg)
{
    uint32_t events;

    for (;;) {
        if (rtos_event_wait(DMA_BUFFER_READY_EVENT,
                            &events,
                            1000) != RTOS_OK) {
            acquisition_report_timeout();
            continue;
        }

        for (size_t i = 0; i < 2; ++i) {
            if (dma_ctx.ready[i]) {
                dma_ctx.ready[i] = false;
                process_samples(dma_ctx.buffer[i],
                                dma_ctx.buffer_size);
            }
        }
    }
}
```

组合机制的收益：

- DMA 负责吞吐。
- 双缓冲避免处理时停止采集。
- ISR 只发送事件。
- 任务负责复杂解析。
- Cache 管理集中在 DMA 层。

---

## 11. 工业级实际案例分析

## 11.1 案例一：多型号控制器共用一套应用代码

### 需求

- 产品有 Alpha、Beta 两种 PCB。
- MCU 相同，但 UART、LED、传感器片选和中断引脚不同。
- 应用代码必须保持一致。

### 架构设计

```
application/
  -> device_service/
      -> bsp_uart
      -> bsp_gpio
      -> bsp_spi
board_alpha/
  -> board_config.h
  -> board_devices.c
board_beta/
  -> board_config.h
  -> board_devices.c
chip/
  -> stm32_uart.c
  -> stm32_spi.c
```

配置示例：

```
/* board_config.h */
#define BOARD_DEBUG_UART_ID      2u
#define BOARD_SENSOR_SPI_ID      1u
#define BOARD_SENSOR_CS_PORT     4u
#define BOARD_SENSOR_CS_PIN      7u
```

应用代码：

```
int system_log_write(const char *data, size_t len)
{
    return bsp_uart_send(board_debug_uart(),
                         data,
                         len,
                         100);
}
```

设计要点：

- 板卡差异只存在于 `board/`。
- 应用不包含芯片 HAL 头文件。
- 通过构建参数选择 `BOARD_NAME`。
- CI 分别构建两种板卡配置。

## 11.2 案例二：工业传感器采集节点

### 需求

- 4 路 SPI 传感器。
- 采样率 20 kHz。
- 每次采样 16 字节。
- CPU 需要运行滤波、通信和故障诊断。
- 传感器断线后必须自动恢复。

### 架构

```
定时器触发
  -> SPI DMA
  -> DMA 完成 ISR
  -> 采样事件队列
  -> 采集任务
  -> 滤波任务
  -> 通信任务
```

吞吐需求：

4×20,000×16=1,280,000Byte/s4×20,000×16=1,280,000Byte/s

SPI 时钟至少需要：

1,280,000×8=10.24MHz1,280,000×8=10.24MHz

考虑命令、间隔和协议开销，工程上应选择不低于 16 MHz 的 SPI 时钟。

设计要点：

- 每个传感器拥有独立设备上下文。
- SPI 总线锁保护共享控制器。
- DMA 使用双缓冲。
- 采样时间戳由硬件定时器提供。
- SPI 超时触发总线复位。
- 连续错误达到阈值后进入传感器离线状态。
- 故障恢复流程不能阻塞其他传感器。

## 11.3 案例三：低功耗电池设备

### 需求

- 平时进入 Stop/睡眠模式。
- RTC 或 GPIO 唤醒。
- UART、I2C 外设需要在唤醒后恢复。
- 设备状态不能依赖未保持的寄存器。

### 电源状态机

```
ACTIVE
  | prepare_sleep
SLEEP_PREPARED
  | enter_low_power
SLEEPING
  | wakeup
WAKEUP_RESTORE
  | restore success
ACTIVE
```

接口示例：

```
typedef struct {
    int (*prepare_sleep)(void);
    int (*enter_sleep)(void);
    int (*restore_after_wakeup)(void);
} bsp_power_ops_t;
```

设计要点：

- 睡眠前停止 DMA 和清理未完成事务。
- 保存必要的总线配置。
- 唤醒后重新配置时钟、PinMux 和外设。
- 设备驱动状态不能简单认为仍为 `OPEN`。
- 电源域切换时需要重新探测设备。
- 低功耗测试应测量每个状态的电流和进入/退出延迟。

---

## 12. 高频问题深度答疑

### 问题一：BSP 是否应该封装所有 HAL API？

不应该。

BSP 应该只暴露产品和系统真正需要的稳定接口。完整转发厂商 HAL 会形成“第二套 HAL”，带来：

- 接口数量膨胀。
- 厂商类型泄漏。
- 迁移成本未降低。
- 测试面扩大。
- 调用者仍然依赖底层细节。

建议采用“最小稳定接口”：

```
应用需要什么能力 -> 暴露什么接口
芯片支持什么寄存器 -> 留在芯片驱动内部
```

### 问题二：函数表间接调用会不会损害实时性？

会增加少量调用开销，但通常不是主要瓶颈。

如果调用频率低于几十万次每秒，几十个 CPU 周期的开销通常可以接受。真正需要谨慎的是：

- 高频 GPIO bit-bang。
- 高频音视频采样路径。
- 需要严格 WCET 的控制回路。
- 中断内层循环。

可采用：

- 关键路径使用静态内联接口。
- 控制路径使用函数表。
- 数据路径使用批量 DMA。
- 通过编译期绑定消除间接调用。

### 问题三：通用接口是否应该支持 `ioctl`？

可以支持，但不能让 `ioctl` 变成无类型的垃圾抽屉。

推荐：

```
#define BSP_UART_CMD_SET_CONFIG  0x1001u
#define BSP_UART_CMD_GET_STATS   0x1002u
#define BSP_UART_CMD_FLUSH_RX    0x1003u
```

要求：

- 命令编号有命名空间。
- 参数结构体版本化。
- 明确调用上下文。
- 不同设备类型不能复用语义相同但布局不同的结构体。
- 对不支持的命令返回 `BSP_ENOTSUP`。

### 问题四：BSP 是否应该动态注册设备？

取决于系统。

静态注册适合：

- MCU 裸机。
- 资源固定。
- 功能安全或安全认证产品。
- 强调可预测性。

动态注册适合：

- Linux/复杂 RTOS。
- 热插拔。
- 模块化驱动。
- 设备数量运行时变化。

在资源受限 MCU 中，推荐“编译期静态设备表”，避免堆分配和不可预测的注册失败。

### 问题五：如何处理驱动的并发访问？

先定义并发模型：

|模型|说明|
|---|---|
|单任务独占|驱动只由一个任务访问，最简单|
|多任务互斥|每个设备对象有互斥锁|
|总线锁|共享 SPI/I2C 控制器统一加锁|
|ISR + 任务|ISR 更新硬件状态，任务完成事务|
|多核并发|需要原子操作、内存屏障和 Cache 管理|

不要只在接口外层加一把全局锁，因为这会：

- 降低并发性。
- 放大临界区。
- 增加优先级反转风险。
- 让不同总线之间互相阻塞。

### 问题六：错误码应该统一还是保留芯片错误码？

对外统一，对内保留映射。

推荐：

```
芯片 HAL 错误
  -> 芯片适配层记录原始错误
  -> 映射为 BSP_EIO / BSP_ETIMEOUT / BSP_EBUSY
  -> 设备服务根据 BSP 错误决定重试、降级或告警
```

调试日志中可保留原始错误：

```
LOG_ERROR("spi1 transfer failed: bsp=%d hal=0x%08lx",
          bsp_rc,
          (unsigned long)hal_error);
```

这样可以保证上层可移植，同时保留底层诊断信息。

---

## 13. 课程核心总结

### 核心要点

- BSP 的本质是隔离板卡和芯片差异。
- 通用驱动接口应围绕设备对象、函数表、能力描述和生命周期设计。
- 总线驱动与设备驱动必须分离。
- 所有阻塞操作都必须有明确超时。
- ISR 只做硬件确认、数据搬运和事件通知。
- DMA 设计必须包含缓冲区所有权和 Cache 一致性。
- 错误路径、重试、恢复和降级与正常路径同等重要。
- 多型号产品应通过板级配置复用应用代码。

### 性能排序

在单次调用开销上，通常为：

```
直接寄存器访问
  < 内联封装
  < 普通 C 函数
  < 函数表调用
  < RTOS 锁保护
  < 任务切换
```

在数据吞吐效率上，通常为：

```
逐字节轮询
  < 逐字节中断
  < FIFO 中断
  < DMA
  < DMA + 双缓冲 + 批量处理
```

### 通用选型结论

- 小型、固定硬件：统一 C 接口。
- 多实例、多板卡：设备对象 + 函数表。
- 高吞吐：DMA + 异步事件。
- 低功耗：电源状态机 + 驱动恢复接口。
- 认证项目：静态设备表、显式状态机、无隐式动态分配。
- 可移植产品：BSP、芯片驱动、设备驱动和应用服务严格分层。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|需求|推荐设计|
|---|---|
|单板快速验证|HAL 薄封装|
|多板卡复用|board config + 通用接口|
|多实例设备|设备对象 + 私有上下文|
|高吞吐数据|DMA + 双缓冲|
|异步处理|回调或事件队列|
|多任务共享设备|设备级锁或总线级锁|
|设备热插拔|注册表 + 状态机|
|低功耗|prepare/sleep/restore|
|故障恢复|超时 + 复位 + 重探测|
|主机单元测试|函数表注入 Mock|

### 14.2 特性对比表

|特性|直接 HAL|统一接口|函数表|
|---|---|---|---|
|迁移性|低|中|高|
|调用效率|高|高|中高|
|多实例|弱|中|强|
|可测试性|弱|强|强|
|运行时替换|无|弱|强|
|实现复杂度|低|中|中高|
|适合量产|有限|较好|好|

### 14.3 关键错误码

|错误码|含义|常见处理|
|---|---|---|
|`BSP_EINVAL`|参数非法|修正调用者|
|`BSP_ENODEV`|设备不存在|重探测或下线|
|`BSP_EBUSY`|资源忙|等待、排队或重试|
|`BSP_ETIMEOUT`|操作超时|复位、恢复、告警|
|`BSP_EIO`|硬件 I/O 错误|重试或降级|
|`BSP_ENOTSUP`|能力不支持|选择替代路径|
|`BSP_ESTATE`|状态非法|检查生命周期|
|`BSP_ENOMEM`|内存不足|降级或拒绝请求|

---

## 15. 学习效果自检

完成本课后，应能够回答并实际完成以下任务：

- 能否画出 BSP、HAL、总线驱动、设备驱动和应用服务的边界？
- 能否为一个 UART 设计同步、异步和 DMA 三种接口？
- 能否解释为什么 `volatile` 不能代替同步机制？
- 能否计算给定 UART 速率和任务阻塞时间下的环形缓冲区大小？
- 能否设计 I2C SDA 被拉低时的总线恢复流程？
- 能否为驱动设计完整生命周期状态机？
- 能否设计初始化失败后的资源回滚路径？
- 能否说明 SPI 总线锁和 SPI 设备锁的差异？
- 能否解释 DMA 与 Cache 不一致的根因和解决方案？
- 能否把两块引脚不同的板卡接入同一套应用代码？
- 能否定义 ISR 回调的上下文、时序和缓冲区所有权？
- 能否为驱动增加错误统计、超时统计和恢复次数统计？
- 能否编写一个不依赖真实硬件的 UART Mock 驱动？
- 能否使用逻辑分析仪验证接口时序和超时行为？

---

## 16. 实践与进阶路径

### 阶段一：基础接口实现

实现以下模块：

```
GPIO 通用接口
UART 阻塞发送接口
SPI 同步传输接口
I2C 超时检测接口
设备状态机
统一错误码
```

要求：

- 所有参数检查完整。
- 所有等待操作带超时。
- 所有失败路径可恢复。
- 不能在应用层包含芯片 HAL 头文件。

### 阶段二：多实例与板卡复用

实现两块虚拟板卡：

```
Board A:
  UART1 -> 调试串口
  SPI1  -> Flash
  GPIOA5 -> LED

Board B:
  UART3 -> 调试串口
  SPI2  -> Flash
  GPIOC13 -> LED
```

要求应用层完全不修改，仅切换构建目标。

### 阶段三：异步 DMA 框架

实现：

- UART DMA 接收。
- 空闲线检测。
- 双缓冲。
- 事件队列。
- Cache clean/invalidate。
- 超时和 DMA 错误恢复。

测试指标：

- CPU 占用率。
- 丢包率。
- 最大连续吞吐。
- 中断延迟。
- 任务唤醒延迟。
- DMA 重新提交时间。

### 阶段四：驱动故障注入

注入以下故障：

- SPI 超时。
- I2C SDA 被拉低。
- UART overrun。
- DMA 传输错误。
- 设备探测失败。
- 重复初始化。
- 任务并发访问。
- 缓冲区满和空。
- 唤醒后外设寄存器丢失。

验证：

```
是否能够检测
是否能够记录
是否能够恢复
是否会阻塞其他设备
是否会进入可控降级状态
```

### 阶段五：性能测试方法

使用 GPIO 打点、DWT CYCCNT、逻辑分析仪和 RTOS trace 测量：

```
接口调用延迟
中断响应延迟
DMA 提交时间
DMA 完成到任务处理的延迟
锁竞争时间
最大临界区长度
CPU 占用率
缓冲区峰值使用量
```

DWT 周期测量示例：

```
static inline uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}

uint32_t start = dwt_cycles();

bsp_spi_transfer(&transfer);

uint32_t elapsed = dwt_cycles() - start;
```

换算时间：

Tus=cyclesCPU_Hz×106Tus​=CPU_Hzcycles​×106

测量时必须固定：

- 编译优化等级。
- CPU 主频。
- Cache 状态。
- 中断负载。
- RTOS 调度状态。
- 测试数据长度。
- DMA 和非 DMA 模式。

### 进阶学习方向

- AUTOSAR MCAL 与 ECU Abstraction。
- Zephyr Device Tree 和设备模型。
- Linux platform driver、regmap、device model。
- FreeRTOS/ThreadX 驱动同步与中断机制。
- ARM Cortex-M MPU、TrustZone-M 和安全 BSP。
- Cache 一致性和多核 SoC 驱动架构。
- 功能安全 ISO 26262 下的硬件抽象设计。
- MISRA C、CERT C 和静态分析。
- 设备树生成、配置管理和 BSP CI。
- 基于 QEMU、Renode 或主机 Mock 的驱动自动化测试。