

## 1. 学习目标

### 理解

- 理解 BSP 在硬件层、驱动层、应用层之间的边界与职责。
- 理解传感器抽象层解决的核心问题：**硬件差异隔离、驱动可替换、采样时序统一、错误语义统一**。
- 理解传感器驱动中的总线访问、设备探测、量程配置、数据转换和校准之间的依赖关系。
- 理解静态多态、函数表、设备句柄、能力位和事件回调在嵌入式抽象设计中的作用。

### 掌握

- 掌握 BSP 的目录组织、初始化顺序和资源归属模型。
- 掌握基于 C 语言函数表的传感器抽象接口设计。
- 掌握 I2C、SPI、GPIO、定时器等底层资源的统一封装方式。
- 掌握阻塞式、异步式、轮询式和 FIFO 式传感器接口的适用边界。
- 掌握错误码、超时、重试、设备状态和数据时间戳的统一处理方法。

### 精通

- 能够设计支持多型号传感器、多种总线和不同采样模式的传感器框架。
- 能够分析驱动抽象引入的时间、内存和代码尺寸开销。
- 能够处理总线竞争、设备热插拔、传感器复位、数据一致性和时间戳漂移问题。
- 能够建立 BSP、HAL、设备驱动、传感器服务和业务模块之间的依赖约束。

### 能够设计

- 能够设计适用于量产产品的 BSP 架构和传感器抽象层。
- 能够设计可测试、可移植、可配置和可诊断的传感器软件组件。
- 能够针对环境监测、运动检测、工业控制等场景完成传感器方案选型和系统集成。
- 能够输出包含接口契约、资源表、错误模型、性能预算和测试策略的完整设计方案。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、结构体、函数指针、枚举、位操作和编译链接模型。
- 熟悉 MCU 启动流程、时钟树、中断、DMA、GPIO、I2C、SPI 和 UART。
- 熟悉 RTOS 任务、互斥锁、信号量、队列、软件定时器和中断上下文限制。
- 理解寄存器映射、字节序、补码、定点数和浮点数转换。
- 了解基本的传感器参数：ODR、FS、灵敏度、噪声、FIFO、DRDY 和校准。

### 技能要求

- 能够阅读 MCU 参考手册和传感器数据手册。
- 能够使用逻辑分析仪验证 I2C/SPI 时序。
- 能够通过示波器或 GPIO 打点测量驱动延迟。
- 能够编写单元测试、硬件在环测试和故障注入测试。
- 能够使用 map 文件、栈分析工具和 RTOS 运行时统计工具定位问题。

---

## 3. 技术概述

### 3.1 BSP 的定义

BSP（Board Support Package，板级支持包）是针对一块具体硬件板卡提供的**启动、时钟、引脚、外设资源和板级设备支持集合**。

BSP 通常位于：

```
应用层
    ↓
传感器服务 / 设备管理层
    ↓
传感器抽象层
    ↓
具体传感器驱动
    ↓
BSP / HAL
    ↓
MCU 外设寄存器
```

BSP 主要解决：

- MCU 启动与系统时钟配置。
- GPIO 复用和电气属性配置。
- I2C、SPI、UART、ADC、PWM 等外设实例初始化。
- 板载 LED、按键、电源控制、复位脚和中断脚管理。
- 板级传感器、Flash、显示屏等设备资源描述。
- 不同硬件版本之间的资源差异隔离。

BSP 不应承担：

- 业务算法。
- 传感器数据融合。
- 产品协议。
- 过多的传感器型号判断。
- 具体业务状态机。

### 3.2 传感器抽象层的定义

传感器抽象层通过统一的设备接口，隐藏具体传感器型号、总线实现和寄存器细节，为上层提供稳定的数据和控制能力。

例如上层只关心：

```
sensor_read(&dev, &sample);
```

而不需要知道底层设备是：

- MPU6050 还是 BMI270；
- I2C 还是 SPI；
- 数据是 16 位原始值还是 FIFO 批量读取；
- 是否需要温度补偿；
- 芯片是否经过了硬件复位。

### 3.3 主流技术分支

|分类维度|方案|
|---|---|
|抽象实现|函数表、宏生成、C++ 虚函数、组件接口|
|数据获取|轮询、DRDY 中断、FIFO、DMA、异步回调|
|总线模型|直接访问、总线服务、设备管理器|
|配置方式|编译期静态配置、设备树、运行时注册|
|并发模型|单线程驱动、总线锁、驱动任务、异步事务|
|数据格式|原始码、物理量、定点数、浮点数|
|错误处理|errno、统一枚举错误码、状态机、事件上报|
|校准方式|固件常量、运行时校准、在线估计、外部校准表|

---

## 4. 核心特性横向对比

### 4.1 BSP 组织方式对比

|方案|特点|优点|缺点|适用场景|
|---|---|---|---|---|
|所有代码集中在 `bsp.c`|简单直接|初期开发快|耦合严重、难测试|原型、小型项目|
|按外设拆分|`bsp_i2c.c`、`bsp_gpio.c`|边界清晰|资源关系仍可能分散|中型 MCU 项目|
|BSP + HAL + Board Config|板级资源与芯片外设分离|可移植、可复用|初期设计成本较高|多板卡产品|
|BSP + 设备树|配置和驱动解耦|支持多硬件变体|构建系统复杂|Linux、复杂 RTOS|
|BSP 组件化|每个设备独立组件|易复用、易测试|依赖管理要求高|平台型产品|

### 4.2 传感器接口实现对比

|方案|RAM|ROM|调用开销|可替换性|调试难度|
|---|---|---|---|---|---|
|直接调用具体驱动|低|低|最低|差|中|
|函数表抽象|一个句柄加函数表|中|通常 2~10 个 CPU 周期|好|低|
|宏静态绑定|最低|低|接近零|中|中|
|C++ 虚函数|一个对象指针和虚表|中|通常高于 C 函数表|好|中|
|统一设备管理器|设备表、锁和状态|较高|依赖实现|很好|较高|

### 4.3 数据获取机制对比

|机制|实时性|CPU 占用|功耗|数据完整性|适用场景|
|---|---|---|---|---|---|
|周期轮询|中|高|高|可能丢样|低速环境传感器|
|DRDY 中断|高|低|低|较好|IMU、ADC|
|FIFO|高|很低|低|最好|高频 IMU、音频|
|DMA|高|很低|低|好|连续批量数据|
|异步总线事务|高|低|低|依赖队列|多设备共享总线|

---

## 5. 底层原理与功能特性深度解析

## 5.1 推荐分层模型

```
sensor_service
    ├── 数据采集调度
    ├── 校准与单位转换
    ├── 时间戳管理
    └── 故障监控

sensor_abstraction
    ├── 统一初始化
    ├── 统一配置
    ├── 统一读取
    ├── 统一自检
    └── 统一能力查询

sensor_driver
    ├── 寄存器访问
    ├── 芯片 ID 检测
    ├── 芯片配置
    ├── 原始数据解析
    └── 芯片状态恢复

bsp
    ├── I2C/SPI
    ├── GPIO/EXTI
    ├── 延时与时间戳
    ├── 电源控制
    └── 板级设备实例
```

依赖方向必须单向：

```
业务层 → 服务层 → 抽象层 → 具体驱动 → BSP
```

禁止：

```
BSP → 业务层
具体驱动 → 某个业务任务
抽象层 → 某个具体型号驱动的私有符号
```

---

## 5.2 BSP 资源接口设计

BSP 应提供能力，而不是暴露寄存器。

### 错误设计

```
/* 具体 MCU 寄存器泄漏到传感器驱动 */
I2C1->CR1 |= I2C_CR1_START;
I2C1->DR = reg_addr;
```

这种设计会导致：

- 驱动只能运行在某个 MCU 上。
- 无法模拟 I2C 进行单元测试。
- DMA、中断和阻塞模式无法替换。
- 业务代码可能直接修改底层外设状态。

### 推荐接口

```
typedef enum {
    BSP_OK = 0,
    BSP_ERR_PARAM,
    BSP_ERR_TIMEOUT,
    BSP_ERR_IO,
    BSP_ERR_BUSY,
    BSP_ERR_UNSUPPORTED,
} bsp_status_t;

typedef struct {
    bsp_status_t (*write)(void *ctx,
                          uint8_t addr,
                          const uint8_t *data,
                          size_t len,
                          uint32_t timeout_ms);

    bsp_status_t (*read)(void *ctx,
                         uint8_t addr,
                         uint8_t *data,
                         size_t len,
                         uint32_t timeout_ms);

    bsp_status_t (*write_read)(void *ctx,
                               uint8_t addr,
                               const uint8_t *tx,
                               size_t tx_len,
                               uint8_t *rx,
                               size_t rx_len,
                               uint32_t timeout_ms);

    void *ctx;
} bsp_i2c_bus_t;
```

这里的关键点：

- `ctx` 保存硬件实例，避免全局变量。
- `write_read()` 对 I2C 寄存器读取非常重要，可以保证 repeated-start 时序。
- 所有阻塞接口必须明确超时时间。
- 返回值必须能区分参数错误、忙、超时和总线错误。
- 传感器驱动不应假定底层使用中断还是 DMA。

---

## 5.3 传感器统一数据模型

原始数据不能直接作为抽象层输出。抽象层应统一单位、时间戳和质量状态。

```
typedef enum {
    SENSOR_TYPE_ACCEL = 0,
    SENSOR_TYPE_GYRO,
    SENSOR_TYPE_TEMP,
    SENSOR_TYPE_PRESSURE,
    SENSOR_TYPE_HUMIDITY,
} sensor_type_t;

typedef enum {
    SENSOR_SAMPLE_VALID       = 1u << 0,
    SENSOR_SAMPLE_CALIBRATED  = 1u << 1,
    SENSOR_SAMPLE_OVERRUN     = 1u << 2,
    SENSOR_SAMPLE_SATURATED   = 1u << 3,
    SENSOR_SAMPLE_TIMESTAMPED = 1u << 4,
} sensor_sample_flags_t;

typedef struct {
    int32_t x;
    int32_t y;
    int32_t z;
} sensor_vec3_q16_t;

typedef struct {
    sensor_type_t type;
    uint64_t timestamp_us;
    uint32_t sequence;
    uint32_t flags;
    union {
        sensor_vec3_q16_t vec3;
        int32_t scalar_q16;
    } value;
} sensor_sample_t;
```

采用 Q16 定点格式时：

```
物理值 = raw_q16 / 65536
```

相比 `float`：

- 在无 FPU 的 Cortex-M0/M3 上，避免较重的软件浮点运算。
- 数据结构大小固定，便于 DMA、队列和日志传输。
- 代价是动态范围和运算溢出必须严格管理。

---

## 5.4 函数表式传感器抽象

```
typedef enum {
    SENSOR_OK = 0,
    SENSOR_ERR_PARAM,
    SENSOR_ERR_NOT_FOUND,
    SENSOR_ERR_ID,
    SENSOR_ERR_IO,
    SENSOR_ERR_TIMEOUT,
    SENSOR_ERR_STATE,
    SENSOR_ERR_UNSUPPORTED,
    SENSOR_ERR_DATA,
} sensor_status_t;

typedef struct {
    uint32_t odr_hz;
    uint32_t range;
    uint32_t watermark;
    bool enable_fifo;
    bool enable_interrupt;
} sensor_config_t;

typedef struct sensor_device sensor_device_t;

typedef struct {
    sensor_status_t (*init)(sensor_device_t *dev);
    sensor_status_t (*deinit)(sensor_device_t *dev);
    sensor_status_t (*configure)(sensor_device_t *dev,
                                 const sensor_config_t *cfg);
    sensor_status_t (*read)(sensor_device_t *dev,
                            sensor_sample_t *sample);
    sensor_status_t (*self_test)(sensor_device_t *dev);
    sensor_status_t (*recover)(sensor_device_t *dev);
    uint32_t (*get_caps)(sensor_device_t *dev);
} sensor_ops_t;

struct sensor_device {
    const char *name;
    sensor_type_t type;
    const sensor_ops_t *ops;
    void *priv;
    uint32_t state;
    uint32_t error_count;
};
```

公共接口负责参数检查和状态保护：

```
sensor_status_t sensor_read(sensor_device_t *dev,
                            sensor_sample_t *sample)
{
    if ((dev == NULL) || (sample == NULL) ||
        (dev->ops == NULL) || (dev->ops->read == NULL)) {
        return SENSOR_ERR_PARAM;
    }

    if ((dev->state & SENSOR_STATE_INITIALIZED) == 0u) {
        return SENSOR_ERR_STATE;
    }

    sensor_status_t ret = dev->ops->read(dev, sample);
    if (ret != SENSOR_OK) {
        dev->error_count++;
    }

    return ret;
}
```

公共层不应将所有驱动细节抽象成大量通用接口。接口应围绕上层实际需要设计，避免形成“万能设备接口”。

---

## 5.5 芯片驱动的寄存器访问

下面以典型 I2C 传感器为例：

```
typedef struct {
    bsp_i2c_bus_t *bus;
    uint8_t address;
    uint8_t who_am_i_expected;
    uint32_t sample_period_us;
} sensor_i2c_priv_t;

static sensor_status_t sensor_reg_read(sensor_i2c_priv_t *priv,
                                       uint8_t reg,
                                       uint8_t *data,
                                       size_t len)
{
    if ((priv == NULL) || (data == NULL) || (len == 0u)) {
        return SENSOR_ERR_PARAM;
    }

    bsp_status_t ret = priv->bus->write_read(
        priv->bus->ctx,
        priv->address,
        &reg,
        1u,
        data,
        len,
        10u
    );

    if (ret == BSP_ERR_TIMEOUT) {
        return SENSOR_ERR_TIMEOUT;
    }

    return (ret == BSP_OK) ? SENSOR_OK : SENSOR_ERR_IO;
}
```

16 位寄存器解析必须明确字节序和符号扩展：

```
static int16_t be16_to_i16(const uint8_t *p)
{
    uint16_t value = ((uint16_t)p[0] << 8) | p[1];
    return (int16_t)value;
}
```

加速度转换示例：

```
/* sensitivity_lsb_per_g 由量程配置决定 */
static int32_t accel_raw_to_q16(int16_t raw,
                                int32_t sensitivity_lsb_per_g)
{
    /* g = raw / sensitivity; Q16 = g * 65536 */
    int64_t result = (int64_t)raw * 65536LL;
    result /= sensitivity_lsb_per_g;

    if (result > INT32_MAX) {
        return INT32_MAX;
    }

    if (result < INT32_MIN) {
        return INT32_MIN;
    }

    return (int32_t)result;
}
```

生产代码需要特别注意：

- 读取长度必须与数据手册一致。
- 连续寄存器地址是否自动递增不能想当然。
- 读写寄存器是否需要最高位设置为读标志，取决于芯片协议。
- 复位后必须等待芯片完成启动。
- 写配置寄存器后应读取回读确认，至少在关键配置阶段进行。
- 避免用未对齐指针直接强转解析多字节数据。

---

## 5.6 设备探测与初始化状态机

复杂设备初始化不应写成无条件连续寄存器写入。

```
typedef enum {
    DEV_STATE_RESET = 0,
    DEV_STATE_POWERED,
    DEV_STATE_ID_CHECKED,
    DEV_STATE_CONFIGURED,
    DEV_STATE_RUNNING,
    DEV_STATE_FAULT,
} dev_state_t;
```

推荐流程：

```
RESET
  ↓
电源开启
  ↓
硬件复位
  ↓
等待启动完成
  ↓
读取 WHO_AM_I
  ↓
配置总线和量程
  ↓
回读关键寄存器
  ↓
清除中断/FIFO
  ↓
RUNNING
```

示例：

```
static sensor_status_t imu_init(sensor_device_t *dev)
{
    sensor_i2c_priv_t *priv = dev->priv;
    uint8_t id = 0u;

    if (sensor_reg_read(priv, REG_WHO_AM_I, &id, 1u) != SENSOR_OK) {
        dev->state = SENSOR_STATE_FAULT;
        return SENSOR_ERR_IO;
    }

    if (id != priv->who_am_i_expected) {
        dev->state = SENSOR_STATE_FAULT;
        return SENSOR_ERR_ID;
    }

    if (sensor_reg_write(priv, REG_RESET, RESET_COMMAND) != SENSOR_OK) {
        dev->state = SENSOR_STATE_FAULT;
        return SENSOR_ERR_IO;
    }

    bsp_delay_ms(5u);

    if (imu_configure_default(dev) != SENSOR_OK) {
        dev->state = SENSOR_STATE_FAULT;
        return SENSOR_ERR_IO;
    }

    dev->state = SENSOR_STATE_INITIALIZED;
    return SENSOR_OK;
}
```

注意：`bsp_delay_ms()` 只能用于初始化阶段。运行期高频采样不能依靠长时间阻塞延时维持时序。

---

## 5.7 中断、FIFO 和时间戳

传感器中断服务程序中不应执行完整 I2C/SPI 读取：

```
void EXTI_SENSOR_IRQHandler(void)
{
    sensor_irq_clear();

    /* 只记录事件和时间，唤醒采集任务 */
    sensor_irq_timestamp = bsp_time_us();
    os_semaphore_give_from_isr(sensor_data_sem);
}
```

采集任务中再读取数据：

```
void sensor_task(void *arg)
{
    sensor_device_t *dev = arg;
    sensor_sample_t sample;

    for (;;) {
        if (os_semaphore_take(sensor_data_sem, OS_WAIT_FOREVER) != OS_OK) {
            continue;
        }

        sensor_status_t ret = sensor_read(dev, &sample);
        if (ret == SENSOR_OK) {
            sensor_pipeline_push(&sample);
        } else {
            sensor_fault_report(dev, ret);
        }
    }
}
```

FIFO 的关键约束：

```
FIFO 数据量 = ODR × 采样周期 × 每个样本字节数
```

例如：

- ODR = 1 kHz；
- 三轴加速度；
- 每轴 16 bit；
- FIFO 水位为 20 ms。

则：

```
容量 = 1000 × 0.02 × 6 = 120 字节
```

实际还需增加：

- 时间戳或时间戳重建空间；
- FIFO 状态寄存器；
- 水位误差；
- 总线事务和任务调度延迟裕量。

---

## 5.8 传感器资源注册

板级配置可以采用静态实例：

```
static bsp_i2c_bus_t g_i2c1;

static sensor_i2c_priv_t g_imu_priv = {
    .bus = &g_i2c1,
    .address = 0x68u,
    .who_am_i_expected = 0x42u,
    .sample_period_us = 1000u,
};

static const sensor_ops_t g_imu_ops = {
    .init = imu_init,
    .deinit = imu_deinit,
    .configure = imu_configure,
    .read = imu_read,
    .self_test = imu_self_test,
    .recover = imu_recover,
    .get_caps = imu_get_caps,
};

sensor_device_t g_imu_device = {
    .name = "imu0",
    .type = SENSOR_TYPE_ACCEL,
    .ops = &g_imu_ops,
    .priv = &g_imu_priv,
};
```

静态实例的优势：

- 无动态内存碎片。
- 启动依赖明确。
- 编译器可以检查初始化字段。
- 适合安全等级较高的产品。

---

## 6. 性能量化分析

以下数据以 **Cortex-M4F，168 MHz，I2C 400 kHz，FreeRTOS，编译器 GCC `-O2`** 为参考。实际数据必须通过目标板实测确认。

### 6.1 调用开销

|操作|典型耗时|
|---|---|
|直接函数调用|约 10~20 ns|
|函数表间接调用|约 15~35 ns|
|I2C 读 1 字节寄存器|约 100~180 us|
|I2C 连续读 14 字节|约 450~650 us|
|SPI 读 14 字节，8 MHz|约 20~40 us|
|GPIO 中断到任务开始运行|约 5~30 us|
|读取并解析 6 轴 16 位数据|约 1~5 us|

相比总线事务，函数表调用开销通常可忽略。真正的瓶颈一般是：

- 低速 I2C；
- 总线锁竞争；
- 任务唤醒延迟；
- 频繁单寄存器读取；
- 中断优先级配置不当；
- FIFO 未启用导致事务次数过多。

### 6.2 I2C 传输时间估算

标准 I2C 一次事务包括地址、寄存器地址、数据和 ACK 位。

粗略估算：

```
T ≈ N_bits / f_bus + T_start_stop + T_clock_stretch
```

例如读取 14 字节：

```
写地址 + 寄存器地址 + 读地址 + 14 字节
≈ (1 + 1 + 1 + 14) × 9 bit
= 153 bit
```

在 400 kHz 下：

```
T ≈ 153 / 400000
  ≈ 382.5 us
```

再加上启动、停止、驱动调度和设备内部延迟，实际可能达到 450~650 us。

### 6.3 轮询与 FIFO 的 CPU 占用

假设每秒读取 1000 次，每次 I2C 事务占用 CPU 20 us：

```
CPU 占用率 = 1000 × 20 us / 1 s
          = 2%
```

如果实际是阻塞等待 I2C 完成，CPU 在等待期间无法执行其他任务，则系统调度影响远高于 2% 的计算结果。

改为 FIFO，每 20 个样本批量读取一次：

```
事务次数：1000 次/s → 50 次/s
事务管理开销降低约 95%
```

代价是：

- 数据处理延迟增加，最大约 20 ms；
- FIFO 溢出风险需要监控；
- 时间戳需要重建；
- 故障发现可能延迟。

### 6.4 内存开销

典型静态设计：

|对象|典型大小|
|---|---|
|`sensor_device_t`|24~40 字节|
|具体驱动私有结构|32~128 字节|
|函数表|28~40 字节 Flash|
|单样本结构|32~48 字节|
|32 个样本环形缓冲区|1~2 KB|
|任务栈|1~4 KB，依赖实现|

传感器抽象本身的开销通常很小，主要内存消耗来自：

- FIFO 软件缓存；
- 消息队列；
- 日志缓冲区；
- DMA 双缓冲；
- 多设备实例。

### 6.5 优化手段和收益

|优化手段|典型收益|代价|
|---|---|---|
|SPI 替代 400 kHz I2C|单次读取延迟降低 10~20 倍|占用片选和 GPIO|
|FIFO 批量读取|总线事务次数降低 80%~95%|采样延迟增加|
|DMA|CPU 搬运开销降低 50%~90%|状态管理更复杂|
|静态配置|减少 RAM 和碎片风险|灵活性下降|
|Q16 定点运算|无 FPU 平台计算速度提高|溢出风险增加|
|配置回读缓存|减少重复寄存器读取|缓存可能失效|
|总线事务合并|降低起始停止开销|驱动设计复杂|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
需要采集传感器数据
    |
    +-- 采样频率 <= 10 Hz，实时性要求低？
    |       |
    |       +-- 是 --> 轮询 + 阻塞式总线接口
    |       |
    |       +-- 否
    |
    +-- 是否要求每个样本不能丢失？
    |       |
    |       +-- 是 --> DRDY + FIFO + DMA/批量读取
    |       |
    |       +-- 否 --> DRDY + 单次读取
    |
    +-- 是否存在多个任务访问同一总线？
    |       |
    |       +-- 是 --> 总线服务或总线互斥锁
    |       |
    |       +-- 否 --> 驱动私有总线访问
    |
    +-- 是否有多个硬件版本或传感器替代料？
    |       |
    |       +-- 是 --> 函数表抽象 + 能力查询 + 探测机制
    |       |
    |       +-- 否 --> 静态绑定接口也可接受
    |
    +-- 是否涉及功能安全或安全认证？
            |
            +-- 是 --> 静态分配 + 明确错误模型 + 可追踪状态机
            |
            +-- 否 --> 可按产品成本选择动态注册或组件化方案
```

### 7.2 典型场景

|场景需求|方案|理由|
|---|---|---|
|室内温湿度每 1 秒采集一次|I2C + 轮询 + 抽象层|数据频率低，系统简单，功耗低|
|电机振动 3.2 kHz 采样|SPI + DRDY + FIFO + DMA|I2C 带宽和调度延迟不足|
|多个传感器共享 I2C|总线锁或总线服务|避免事务交叉和总线状态破坏|
|同一产品支持两种 IMU|统一加速度/陀螺仪接口|上层算法不感知具体型号|
|传感器可断电恢复|电源控制 + `recover()`|支持运行期故障恢复|
|高可靠工业控制|静态设备表 + 状态机 + 诊断计数|可验证性和可追踪性更好|
|Linux 与 MCU 共用驱动模型|设备能力、采样格式、错误码统一|上层软件迁移成本低|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 单一职责

- BSP 管理板级资源。
- HAL 管理 MCU 外设抽象。
- 芯片驱动管理寄存器和芯片状态。
- 抽象层管理统一接口。
- 服务层管理调度、校准、缓存和诊断。
- 业务层只消费标准化数据。

### 资源显式传递

避免依赖全局 `i2c1`、`gpio_exti` 等隐式资源。设备私有结构中显式保存资源句柄。

### 统一物理单位

接口文档必须明确：

- 加速度：`m/s^2`、`g` 或 Q16；
- 角速度：`rad/s` 或 `deg/s`；
- 温度：摄氏度或 Q16；
- 压力：Pa、kPa 或 Q16；
- 时间戳：单调时钟还是墙上时钟。

### 不在 ISR 中做复杂事务

ISR 只做：

- 清中断；
- 读取硬件时间或记录事件；
- 投递信号；
- 必要时切换任务。

### 错误可恢复

错误模型至少区分：

```
参数错误
设备不存在
设备 ID 错误
总线忙
总线超时
数据无效
FIFO 溢出
设备需要复位
设备永久故障
```

## 8.2 选型决策矩阵

评分范围：1 分较差，5 分较好。

|方案|可移植性|实时性|资源开销|可测试性|适合量产|
|---|---|---|---|---|---|
|直接驱动调用|1|5|5|2|2|
|函数表抽象|4|4|4|5|5|
|C++ 虚函数|4|4|3|4|4|
|设备管理器|5|3|2|4|5|
|设备树 + 驱动框架|5|4|2|4|5|

## 8.3 工业级编码规范

- 所有对外接口检查空指针、长度、状态和范围。
- 不使用无限等待的总线操作。
- 不在驱动中直接调用业务日志接口；通过统一诊断接口上报。
- 不在驱动初始化函数中创建任务、队列等上层资源。
- 所有寄存器字段通过宏定义，避免裸数字。
- 对每次配置写入定义“写后回读”策略。
- 数据结构中使用固定宽度整数类型。
- 明确是否允许并发调用。
- 明确哪些接口可以在 ISR 上下文调用。
- 禁止在采样路径中使用不可控的动态内存分配。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：传感器驱动直接操作 MCU 寄存器

### 错误代码

```
void imu_read(void)
{
    I2C1->CR1 |= I2C_CR1_START;
    I2C1->DR = 0x68u << 1;
}
```

### 根因

驱动层同时承担了：

- MCU 外设控制；
- 总线时序；
- 传感器协议；
- 数据解析。

硬件芯片变化或 MCU 更换时，驱动无法复用。

### 正确实现

```
sensor_status_t imu_read_reg(uint8_t reg,
                             uint8_t *data,
                             size_t len)
{
    return bus_read_register(&imu_bus, IMU_ADDR, reg, data, len);
}
```

### 风险影响

- 无法进行主机单元测试。
- 驱动与 MCU 强耦合。
- 容易破坏其他设备正在使用的总线状态。
- 后续加入 DMA 或异步模式时需要重写驱动。

---

## 9.2 错误二：ISR 中阻塞读取完整传感器数据

### 错误代码

```
void imu_drdy_isr(void)
{
    uint8_t data[14];

    i2c_read(IMU_ADDR, REG_ACCEL_XOUT, data, sizeof(data), 100);
    process_imu_data(data);
}
```

### 根因

ISR 中执行了不可预测时长的总线事务和数据处理。

### 正确实现

```
void imu_drdy_isr(void)
{
    uint64_t timestamp = bsp_time_us();

    imu_irq_timestamp = timestamp;
    os_semaphore_give_from_isr(imu_sem);
}
```

### 风险影响

- 阻塞更高优先级中断。
- 触发中断嵌套和实时性失控。
- 可能造成系统看门狗复位。
- 高频采样时容易丢失后续中断。

---

## 9.3 错误三：不检查芯片 ID

### 错误代码

```
void imu_init(void)
{
    write_reg(REG_CTRL1, 0x57u);
    write_reg(REG_CTRL2, 0x08u);
}
```

### 根因

默认假设器件一定存在且型号正确。

### 正确实现

```
uint8_t id;

if (read_reg(REG_WHO_AM_I, &id, 1u) != SENSOR_OK) {
    return SENSOR_ERR_IO;
}

if (id != EXPECTED_WHO_AM_I) {
    return SENSOR_ERR_ID;
}
```

### 风险影响

- 器件焊接错误无法及时发现。
- I2C 地址配置错误被误判为初始化成功。
- 替代料寄存器布局不同，可能写入危险配置。
- 上层得到全零或随机数据而无法定位原因。

---

## 9.4 错误四：直接使用原始值而忽略量程和灵敏度

### 错误代码

```
float acceleration_g = (float)raw_x;
```

### 根因

没有把原始 ADC 码转换为物理量。

### 正确实现

```
float acceleration_g = (float)raw_x / sensitivity_lsb_per_g;
```

或者使用定点：

```
int32_t acceleration_q16 =
    accel_raw_to_q16(raw_x, sensitivity_lsb_per_g);
```

### 风险影响

- 算法输入比例错误。
- 不同量程配置下结果不一致。
- 姿态解算、阈值检测和控制算法全部失效。
- 问题可能表现为“算法偶发异常”，难以定位。

---

## 9.5 错误五：I2C 总线没有统一并发保护

### 错误代码

```
/* 任务 A */
i2c_start();
i2c_write(addr);
i2c_write(reg);
os_delay_ms(1);

/* 任务 B 可能在此时访问同一 I2C */
i2c_start();
```

### 根因

把一次完整事务拆开后允许其他任务插入。

### 正确实现

```
bus_lock(&i2c1, timeout_ms);

ret = i2c_write_read(addr, &reg, 1u, data, len, timeout_ms);

bus_unlock(&i2c1);
```

### 风险影响

- 设备收到交叉数据。
- 总线进入 BUSY 或错误状态。
- 间歇性故障难以通过普通测试复现。
- 多设备同时工作时故障概率显著增加。

---

## 9.6 错误六：时间戳使用任务读取时刻

### 错误代码

```
sensor_read(dev, &sample);
sample.timestamp_us = bsp_time_us();
```

### 根因

任务调度和总线读取延迟被错误地当作采样时刻。

### 正确实现

```
void sensor_drdy_isr(void)
{
    sample_irq_timestamp = bsp_time_us();
    os_semaphore_give_from_isr(data_sem);
}

sample.timestamp_us = sample_irq_timestamp;
```

### 风险影响

- 多传感器融合出现相位偏差。
- 高速运动时姿态和位置估计误差增加。
- 控制系统可能出现抖动或响应滞后。

---

## 10. 多机制组合使用方案

## 10.1 推荐组合架构

```
传感器硬件
    ↓ DRDY
GPIO/EXTI ISR
    ↓ 信号量 + 硬件时间戳
Sensor Acquisition Task
    ↓ SPI/I2C + DMA/FIFO
传感器抽象层
    ↓ 标准样本
Calibration Filter
    ↓
Ring Buffer / Message Queue
    ↓
算法任务、记录任务、诊断任务
```

组合机制：

- **BSP**：提供总线、GPIO、电源和时间服务。
- **驱动层**：实现寄存器访问和设备状态机。
- **抽象层**：统一设备操作和数据格式。
- **DRDY 中断**：保证采样事件及时通知。
- **FIFO**：吸收任务调度抖动。
- **DMA**：减少 CPU 数据搬运。
- **环形缓冲区**：隔离生产者和消费者速度差。
- **看门狗/诊断**：检测无数据、溢出和总线卡死。

## 10.2 环形缓冲区代码框架

```
#define SAMPLE_RING_SIZE 32u

typedef struct {
    sensor_sample_t items[SAMPLE_RING_SIZE];
    uint32_t write_index;
    uint32_t read_index;
    os_mutex_t lock;
} sample_ring_t;

static bool ring_is_full(const sample_ring_t *ring)
{
    uint32_t next = (ring->write_index + 1u) % SAMPLE_RING_SIZE;
    return next == ring->read_index;
}

sensor_status_t sample_ring_push(sample_ring_t *ring,
                                 const sensor_sample_t *sample)
{
    if ((ring == NULL) || (sample == NULL)) {
        return SENSOR_ERR_PARAM;
    }

    os_mutex_lock(&ring->lock, OS_WAIT_FOREVER);

    if (ring_is_full(ring)) {
        os_mutex_unlock(&ring->lock);
        return SENSOR_ERR_DATA;
    }

    ring->items[ring->write_index] = *sample;
    ring->write_index =
        (ring->write_index + 1u) % SAMPLE_RING_SIZE;

    os_mutex_unlock(&ring->lock);
    return SENSOR_OK;
}
```

生产级实现还应明确满载策略：

```
禁止覆盖旧数据
    → 上报溢出
    → 保证数据完整性

允许覆盖旧数据
    → 保留最新数据
    → 适合实时显示或控制

丢弃最新数据
    → 保持历史连续性
    → 适合离线记录
```

---

## 10.3 总线服务化框架

当多个任务共享多个设备时，可以将总线访问集中到一个任务：

```
typedef struct {
    uint8_t address;
    const uint8_t *tx;
    size_t tx_len;
    uint8_t *rx;
    size_t rx_len;
    uint32_t timeout_ms;
    os_semaphore_t done;
    bsp_status_t result;
} bus_transaction_t;

void i2c_bus_task(void *arg)
{
    bus_transaction_t transaction;

    for (;;) {
        if (queue_receive(&i2c_queue,
                          &transaction,
                          OS_WAIT_FOREVER) != OS_OK) {
            continue;
        }

        transaction.result = bsp_i2c_execute(&transaction);
        os_semaphore_give(&transaction.done);
    }
}
```

优势：

- 总线状态机集中管理。
- 不需要多个任务直接竞争硬件。
- 可以实现事务优先级和超时策略。
- 可以统一处理总线恢复。

缺点：

- 增加任务和队列开销。
- 请求者需要处理异步等待。
- 如果总线任务优先级设计不当，可能形成系统瓶颈。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业电机振动监测

### 需求

- 三轴加速度采样率 3.2 kHz。
- 支持 FFT 和故障特征提取。
- 不允许因任务短时间阻塞导致数据丢失。
- 需要记录采样溢出和传感器异常。

### 架构设计

```
SPI 8 MHz
    ↓
IMU FIFO，水位 32 samples
    ↓ DRDY
ISR 记录时间戳
    ↓
高优先级采集任务
    ↓ DMA 批量读取
    ↓
无锁或单生产者环形缓冲区
    ↓
FFT 处理任务
```

### 设计要点

- 采用 SPI，避免 400 kHz I2C 的吞吐限制。
- FIFO 水位按最坏调度延迟计算。
- 每批数据保存第一个样本时间戳，后续按 ODR 重建。
- 记录 FIFO overflow、SPI CRC 错误和设备复位次数。
- 采集任务不执行 FFT，避免数据采集和算法处理互相阻塞。

### 核心代码

```
static void vibration_collect_task(void *arg)
{
    sensor_device_t *dev = arg;
    uint8_t fifo_data[32u * 6u];
    uint32_t sample_count;

    for (;;) {
        os_semaphore_take(fifo_ready_sem, OS_WAIT_FOREVER);

        if (imu_fifo_count(dev, &sample_count) != SENSOR_OK) {
            sensor_fault_report(dev, SENSOR_ERR_IO);
            continue;
        }

        if (sample_count > 32u) {
            sample_count = 32u;
        }

        if (imu_fifo_read(dev,
                          fifo_data,
                          sample_count * 6u) != SENSOR_OK) {
            sensor_fault_report(dev, SENSOR_ERR_IO);
            continue;
        }

        decode_fifo_samples(fifo_data, sample_count);
    }
}
```

---

## 11.2 案例二：低功耗环境监测节点

### 需求

- 温湿度每 60 秒采样一次。
- 电池供电，目标平均电流小于 100 uA。
- 传感器支持断电。
- 传感器故障后不能阻塞系统唤醒流程。

### 架构设计

```
RTC 唤醒
    ↓
开启传感器电源
    ↓
等待启动
    ↓
I2C 探测
    ↓
读取温湿度
    ↓
校准和范围检查
    ↓
记录/发送
    ↓
关闭传感器电源
    ↓
MCU 进入低功耗
```

### 设计要点

- 传感器电源由 GPIO 或负载开关控制。
- 所有 I2C 操作设置有限超时。
- 每次采样前重新检测设备状态。
- 读取失败不能阻塞到下一次 RTC 唤醒。
- 通过设备电流预算决定是否使用硬件断电。

---

## 11.3 案例三：机器人姿态估计

### 需求

- IMU 采样 1 kHz。
- 需要和编码器、磁力计进行时间同步。
- 姿态控制周期 1 ms。
- 允许传感器运行期恢复，但不能静默输出错误数据。

### 架构设计

```
IMU DRDY ─┐
编码器中断 ├─ 时间戳服务
磁力计定时 ┘
       ↓
采集层
       ↓
统一时间基准
       ↓
校准和坐标转换
       ↓
姿态融合
       ↓
控制器
```

### 设计要点

- 所有设备使用同一个单调时间基准。
- 时间戳不能依赖读取完成时间。
- 传感器样本带有质量标志。
- 恢复期间禁止输出“有效但错误”的零值。
- 通过 `SENSOR_SAMPLE_VALID` 明确数据是否可参与融合。

---

## 12. 高频问题深度答疑

### 问题一：BSP、HAL 和驱动到底如何划分？

建议按“谁知道什么”划分：

- BSP 知道**这块板子如何连接**。
- HAL 知道**MCU 如何控制外设**。
- 芯片驱动知道**传感器寄存器和协议**。
- 抽象层知道**上层需要哪些通用能力**。
- 服务层知道**何时采集、如何缓存和如何校准**。

例如 I2C 引脚属于 BSP，I2C 状态机属于 HAL，`WHO_AM_I` 属于传感器驱动。

### 问题二：是否所有传感器都应该使用同一个 `read()` 接口？

不应该强行统一所有语义。

适合统一的通常是：

- 初始化；
- 配置；
- 单样本读取；
- 自检；
- 恢复；
- 能力查询。

对于差异明显的能力，应通过扩展接口或能力位表达：

```
#define SENSOR_CAP_FIFO       (1u << 0)
#define SENSOR_CAP_BATCH_READ (1u << 1)
#define SENSOR_CAP_SELF_TEST  (1u << 2)
#define SENSOR_CAP_TIMESTAMP  (1u << 3)
```

不能让所有驱动都实现一个语义模糊的“万能控制函数”。

### 问题三：应该输出原始值还是物理量？

分层处理更合理：

- 芯片驱动保留原始值解析能力；
- 抽象层输出统一物理量；
- 服务层完成校准、坐标变换和质量评估；
- 诊断接口保留原始寄存器和原始码。

这样既方便算法使用，也方便现场定位量程、灵敏度和寄存器配置错误。

### 问题四：函数表会不会影响实时性？

在典型 MCU 上，函数表间接调用一般只有几十纳秒级开销，而一次 I2C 事务通常为数百微秒，二者相差几个数量级。

真正需要关注的是：

- 间接调用是否影响编译器内联；
- 是否增加分支预测失败；
- 是否影响安全认证中的可分析性；
- 是否在极高频、极短路径中重复调用。

如果某个热路径每微秒都很关键，可以在驱动内部静态绑定；对普通传感器抽象，函数表的可维护性收益通常更大。

### 问题五：传感器异常时应该返回零值吗？

不应该。零值可能是合法物理数据，会掩盖故障。

推荐：

```
sample.flags &= ~SENSOR_SAMPLE_VALID;
return SENSOR_ERR_IO;
```

同时：

- 保留上一次有效值，但标记过期；
- 记录连续错误次数；
- 触发恢复状态机；
- 超过阈值后上报设备故障；
- 算法层根据质量标志决定是否丢弃数据。

### 问题六：总线锁和总线服务应该选哪个？

小系统、设备数量少、事务短：

```
总线互斥锁 + 同步事务
```

中大型系统、设备多、需要优先级和异步 DMA：

```
总线服务任务 + 事务队列
```

如果需要严格控制最大阻塞时间，总线服务更容易统一实施超时和优先级策略。但它引入了队列延迟，必须将队列等待时间纳入实时性预算。

### 问题七：如何处理传感器运行期复位？

恢复动作应当是状态机，而不是简单重写几个寄存器：

```
检测异常
  ↓
停止上层数据输出
  ↓
清理 FIFO/中断
  ↓
硬件复位或软件复位
  ↓
等待启动
  ↓
读取 ID
  ↓
重新配置
  ↓
自检
  ↓
恢复输出
```

恢复成功前，不能设置 `SENSOR_SAMPLE_VALID`。

---

## 13. 课程核心总结

### 13.1 核心要点

1. **BSP 的核心任务是描述和管理板级资源**，包括时钟、GPIO、总线、电源、复位、外部中断和板载设备连接关系。
2. **HAL 的核心任务是屏蔽 MCU 外设寄存器差异**，向上提供稳定的 I2C、SPI、GPIO、DMA 和时间服务。
3. **具体传感器驱动只负责芯片协议和寄存器语义**，不应直接操作 MCU 寄存器，也不应依赖业务任务。
4. **传感器抽象层统一设备生命周期和数据契约**，至少应覆盖初始化、配置、读取、自检、恢复、能力查询和错误状态。
5. **统一数据接口不能只统一函数名，还必须统一单位、字节序、时间戳、质量标志、错误码和并发约束。**
6. **传感器中断应只完成事件通知和时间戳捕获**，完整总线事务应放在任务或异步总线上下文中执行。
7. **高频采样系统应优先采用 DRDY + FIFO + DMA + 环形缓冲区**，用硬件缓存吸收调度抖动。
8. **所有总线事务必须具备超时和恢复策略**，不能使用无限阻塞。
9. **设备恢复必须经过重新探测、重新配置和自检**，恢复完成前禁止输出有效样本。
10. **抽象层的目标不是隐藏所有差异，而是暴露稳定的共性、显式表达能力差异。**
11. **静态分配、静态设备注册和显式资源依赖**更适合高可靠、低碎片和可认证系统。
12. **性能优化应优先处理总线带宽、事务数量、FIFO 溢出和任务调度延迟**，函数表间接调用通常不是主要瓶颈。

### 13.2 性能排序

在常见 MCU 传感器系统中，性能影响通常按照以下优先级排序：

```
总线速率和总线事务数量
    >
采样方式：单次读取或 FIFO 批量读取
    >
任务调度和优先级配置
    >
DMA/中断数据搬运方式
    >
数据转换和校准算法
    >
函数表间接调用开销
```

对于 1 kHz 以上采样系统，优先检查：

- 传感器是否支持 FIFO；
- 总线是否适合目标吞吐量；
- 读取操作是否可以 DMA；
- 采集任务是否会被低优先级任务阻塞；
- 是否存在 I2C 总线锁竞争；
- FIFO 水位是否覆盖最坏调度延迟。

### 13.3 通用选型结论

|产品特征|推荐架构|
|---|---|
|单板、单传感器、低速采样|BSP + 具体驱动 + 轻量接口|
|多型号传感器替代|函数表抽象 + 能力位 + 设备探测|
|多设备共享总线|统一总线锁或总线服务任务|
|高频、不能丢样|DRDY + FIFO + DMA + 环形缓冲区|
|低功耗周期唤醒|电源控制 + 按需初始化 + 有限超时|
|高可靠工业产品|静态注册 + 状态机 + 故障计数 + 恢复策略|
|功能安全或强约束系统|静态内存、有限状态、明确接口契约、可追踪诊断|
|MCU/Linux 多平台复用|统一设备模型、数据格式和错误语义，底层实现分别适配|

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐方案|关键参数|
|---|---|---|
|温湿度 0.1~1 Hz|I2C 轮询|超时、低功耗、测量等待时间|
|IMU 100~500 Hz|DRDY + 单次读取|中断延迟、总线锁、时间戳|
|IMU 1 kHz 以上|SPI + FIFO + DMA|FIFO 水位、批量大小、溢出处理|
|振动采集|SPI + FIFO + DMA + 环形缓冲|采样完整性、吞吐量、时间同步|
|多设备共享 I2C|总线服务或互斥锁|事务原子性、优先级、超时|
|运行期可断电传感器|电源控制 + `recover()`|上电时序、复位时间、重新探测|
|传感器替代料|抽象接口 + 能力查询|设备 ID、能力位、配置映射|
|认证型产品|静态注册和静态内存|可追踪性、边界检查、故障模式|

### 14.2 传感器抽象接口最小集合

```
typedef struct {
    sensor_status_t (*init)(sensor_device_t *dev);
    sensor_status_t (*deinit)(sensor_device_t *dev);
    sensor_status_t (*configure)(sensor_device_t *dev,
                                 const sensor_config_t *config);
    sensor_status_t (*read)(sensor_device_t *dev,
                            sensor_sample_t *sample);
    sensor_status_t (*self_test)(sensor_device_t *dev);
    sensor_status_t (*recover)(sensor_device_t *dev);
    uint32_t (*get_caps)(sensor_device_t *dev);
} sensor_ops_t;
```

### 14.3 关键状态

```
RESET
  ↓
POWERED
  ↓
ID_CHECKED
  ↓
CONFIGURED
  ↓
RUNNING
  ↓
FAULT
  ↓
RECOVERING
  ↓
SELF_TEST
  ↓
RUNNING
```

### 14.4 关键错误码

|错误码|含义|典型处理|
|---|---|---|
|`SENSOR_ERR_PARAM`|参数非法|立即返回，记录调用位置|
|`SENSOR_ERR_NOT_FOUND`|设备无响应|检查供电、地址和引脚|
|`SENSOR_ERR_ID`|芯片 ID 不匹配|禁止继续配置|
|`SENSOR_ERR_IO`|总线或设备通信失败|重试或总线恢复|
|`SENSOR_ERR_TIMEOUT`|操作超时|复位总线或设备|
|`SENSOR_ERR_STATE`|当前状态不允许操作|检查初始化和恢复状态|
|`SENSOR_ERR_DATA`|数据无效或 FIFO 溢出|丢弃样本并上报诊断|
|`SENSOR_ERR_UNSUPPORTED`|当前设备不支持该能力|查询能力位后调整策略|

### 14.5 性能计算公式

```
总线占用率
= 单次事务时间 × 每秒事务次数 / 1 秒

FIFO 所需容量
= 采样率 × 最坏阻塞时间 × 单样本字节数 × 安全裕量

环形缓冲容量
≥ 生产速率 × 最坏消费者阻塞时间

采样时间误差
= 任务调度延迟 + 总线传输时间 + 数据处理延迟
```

安全裕量通常建议至少取：

```
1.5 ~ 2.0 倍
```

对于任务调度抖动较大的系统，应依据实际运行统计值，而不是仅按平均值设计。

---

## 15. 学习效果自检

### 15.1 架构边界

- [ ]  能解释 BSP、HAL、具体驱动、传感器抽象层和服务层的职责差异。
- [ ]  能指出哪些代码不应出现在 BSP 中。
- [ ]  能绘制从应用层到 MCU 寄存器的单向依赖关系。
- [ ]  能为一块新硬件建立独立的板级资源描述。

### 15.2 接口设计

- [ ]  能设计基于函数表的传感器设备接口。
- [ ]  能定义设备生命周期和状态迁移。
- [ ]  能设计统一错误码并区分超时、忙、设备不存在和数据无效。
- [ ]  能定义传感器数据单位、精度、时间戳和有效标志。
- [ ]  能说明哪些接口允许在 ISR 上下文调用。

### 15.3 总线和并发

- [ ]  能计算一笔 I2C/SPI 事务的理论时间。
- [ ]  能判断目标采样率是否超过总线带宽。
- [ ]  能设计共享总线的互斥或服务化访问方案。
- [ ]  能分析优先级反转和总线锁长时间占用问题。
- [ ]  能设计总线卡死后的恢复流程。

### 15.4 数据采集

- [ ]  能比较轮询、DRDY、FIFO 和 DMA 的适用条件。
- [ ]  能根据采样率和最坏阻塞时间计算 FIFO 容量。
- [ ]  能设计单生产者单消费者环形缓冲区。
- [ ]  能区分采样时间戳和读取完成时间戳。
- [ ]  能处理 FIFO 溢出、数据丢失和序列号断裂。

### 15.5 故障处理

- [ ]  能通过 `WHO_AM_I` 或等效机制确认设备型号。
- [ ]  能设计传感器运行期恢复状态机。
- [ ]  能保证故障期间不输出伪造的有效数据。
- [ ]  能统计连续通信错误、复位次数和数据溢出次数。
- [ ]  能通过日志或诊断接口定位板级连接问题。

### 15.6 工程验证

- [ ]  能使用逻辑分析仪检查总线地址、ACK、重复起始和停止条件。
- [ ]  能用 GPIO 打点测量中断到数据读取完成的延迟。
- [ ]  能使用 map 文件检查驱动和缓冲区内存占用。
- [ ]  能通过故障注入验证超时和恢复路径。
- [ ]  能测试不同 ODR、量程和总线速率下的数据一致性。

---

## 16. 实践与进阶路径

### 16.1 第一阶段：完成最小抽象框架

实现以下模块：

```
bsp_i2c.c / bsp_i2c.h
bsp_gpio.c / bsp_gpio.h
bsp_time.c / bsp_time.h
sensor_core.c / sensor_core.h
sensor_xxx.c / sensor_xxx.h
```

要求：

- 一个传感器设备可以完成初始化、配置和单次读取。
- 所有总线操作具有超时。
- 能读取并验证设备 ID。
- 能输出统一单位的数据。
- 错误路径有明确返回值。

验收指标：

```
设备初始化成功率：100%
非法地址访问：能够返回错误
总线超时：不发生死锁
设备 ID 错误：禁止进入 RUNNING
```

### 16.2 第二阶段：增加多型号驱动替换

实现两个具有相同功能但寄存器不同的传感器驱动：

```
sensor_a_driver
sensor_b_driver
        ↓
统一 sensor_ops_t
        ↓
上层采集任务
```

要求：

- 上层任务不出现具体型号判断。
- 通过设备探测选择具体驱动。
- 两个驱动输出相同单位和相同数据格式。
- 对不支持的能力返回 `SENSOR_ERR_UNSUPPORTED`。
- 通过模拟总线接口完成主机单元测试。

### 16.3 第三阶段：增加 DRDY 和时间戳

实现：

```
GPIO/EXTI
    ↓
ISR 记录时间戳
    ↓
信号量唤醒采集任务
    ↓
总线读取
    ↓
样本入队
```

测试内容：

- 测量 DRDY 到任务开始的延迟。
- 测量 DRDY 到样本入队的延迟。
- 统计延迟最大值、平均值和 P99 值。
- 在高优先级任务持续运行时验证是否丢样。
- 检查时间戳单调性。

推荐记录：

```
typedef struct {
    uint32_t irq_to_task_us;
    uint32_t task_to_read_done_us;
    uint32_t read_done_to_queue_us;
    uint32_t fifo_overflow_count;
    uint32_t bus_timeout_count;
} sensor_perf_stat_t;
```

### 16.4 第四阶段：增加 FIFO、DMA 和环形缓冲区

目标：

- 采样频率提升到 1 kHz 或更高。
- 采集任务不执行复杂算法。
- 使用批量读取降低事务数量。
- 在最坏调度延迟下不发生 FIFO 溢出。

验证公式：

```
FIFO 容量
> 采样率 × 最大任务阻塞时间 × 单样本字节数 × 2
```

例如：

```
采样率：1000 Hz
最大阻塞：20 ms
单样本：6 字节

最小推荐容量
> 1000 × 0.02 × 6 × 2
= 240 字节
```

### 16.5 第五阶段：增加故障恢复和诊断

实现以下故障注入：

```
设备断电
设备地址错误
SDA 被拉低
SCL 被拉低
设备返回错误 ID
传输中途超时
FIFO 溢出
数据饱和
DRDY 丢失
```

每种故障应验证：

- 是否能在规定时间内检测；
- 是否停止输出无效数据；
- 是否触发重试；
- 是否执行总线或设备恢复；
- 是否恢复成功后重新自检；
- 是否留下可追踪诊断信息。

### 16.6 第六阶段：建立硬件无关测试层

将 BSP 总线接口替换为模拟实现：

```
typedef struct {
    uint8_t registers[256];
    bool timeout;
    bool wrong_id;
    uint32_t read_count;
    uint32_t write_count;
} mock_sensor_bus_t;
```

测试项目：

- 寄存器读写顺序；
- 芯片 ID 校验；
- 配置回读；
- 大小端转换；
- 负数原始值解析；
- 量程转换；
- 超时映射；
- 重试次数；
- 恢复状态迁移；
- FIFO 溢出处理。

### 16.7 性能测试方法

#### 总线吞吐测试

测试变量：

```
I2C：100 kHz / 400 kHz / 1 MHz
SPI：1 MHz / 4 MHz / 8 MHz / 16 MHz
读取模式：单寄存器 / 连续寄存器 / FIFO
```

记录指标：

```
单次事务耗时
每秒最大样本数
CPU 占用率
任务阻塞时间
总线错误率
```

#### 调度延迟测试

在中断和任务中使用 GPIO 打点：

```
void sensor_irq_handler(void)
{
    test_pin_set();
    irq_timestamp = bsp_time_us();
    os_semaphore_give_from_isr(sensor_sem);
    test_pin_clear();
}
```

使用逻辑分析仪测量：

```
DRDY 边沿 → ISR 响应
ISR 响应 → 任务开始
任务开始 → 总线开始
总线开始 → 数据完成
数据完成 → 样本入队
```

#### 数据完整性测试

检查：

- 样本序列号是否连续；
- 时间戳是否单调；
- FIFO 是否溢出；
- 采样间隔是否符合 ODR；
- 传感器断电恢复后是否出现脏数据；
- 满载时环形缓冲区策略是否符合设计。

### 16.8 进阶学习方向

1. **总线服务框架**
    
    - 异步事务队列。
    - 事务优先级。
    - DMA 链接传输。
    - 总线故障自动恢复。
2. **统一设备模型**
    
    - 设备注册表。
    - 能力发现。
    - 运行时设备替换。
    - 设备生命周期管理。
3. **高精度时间同步**
    
    - 硬件捕获时间戳。
    - 多传感器时间基准校准。
    - ODR 偏差估计。
    - 时间漂移补偿。
4. **传感器数据质量管理**
    
    - 饱和检测。
    - 断线检测。
    - 静态偏置估计。
    - 温度补偿。
    - 样本置信度评分。
5. **安全与可靠性**
    
    - 看门狗配合驱动状态机。
    - 总线异常隔离。
    - 关键寄存器写后回读。
    - 故障注入和 FMEA。
    - MISRA-C 和静态分析。
6. **Linux 与 RTOS 驱动迁移**
    
    - 设备树资源描述。
    - Linux IIO 模型。
    - 中断线程化。
    - sysfs、字符设备和 ioctl。
    - MCU 侧传感器抽象与 Linux 用户态数据接口统一。

### 本课最终能力标准

完成本课后，应能够独立回答并落地以下问题：

```
这块板子的资源如何描述？
不同 MCU 的 I2C 如何统一？
不同型号传感器如何替换？
高频数据如何避免丢失？
中断和总线访问如何解耦？
故障如何检测和恢复？
数据单位和时间戳如何保证一致？
如何证明系统在最坏情况下仍满足实时性？
```

一个合格的工业级设计，不仅要“读到传感器数据”，还必须能够说明：

```
数据从哪里来
何时采样
如何转换
是否有效
发生错误怎么办
资源由谁管理
最坏延迟是多少
如何验证设计成立
```