
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 **BSP、HAL、MCAL、设备驱动、设备服务、应用适配层**之间的职责边界。
- 理解 MCU 启动链路、时钟初始化、内存初始化、中断向量表、PinMux、外设实例化之间的依赖关系。
- 理解“板级差异”和“芯片差异”为什么必须隔离。
- 理解静态绑定、设备树、设备表、驱动模型等常见架构方案。

### 掌握

能够：

- 设计适用于裸机、FreeRTOS、Zephyr 或嵌入式 Linux 的 BSP 目录结构。
- 编写具有错误处理、并发保护、超时控制和资源释放能力的驱动框架。
- 将 MCU 厂商 SDK、寄存器代码与业务代码隔离。
- 建立 GPIO、UART、I2C、SPI、ADC、PWM、Flash 等设备的统一接口。
- 实现 Board Variant、Feature Configuration 和硬件版本兼容机制。

### 精通

能够：

- 分析驱动分层中的依赖反转、接口污染、初始化顺序、锁竞争和实时性问题。
- 设计同步驱动、异步驱动、DMA 驱动和中断驱动的统一抽象。
- 处理多实例设备、设备探测、热插拔、故障恢复和电源管理。
- 对驱动进行时间、内存、栈、锁竞争和中断延迟量化。

### 能够设计

能够独立设计：

- 面向量产产品的 BSP 架构。
- 支持多块硬件变体的可配置 BSP。
- 适配多种 MCU 或 SoC 的可移植驱动层。
- 支持单元测试、仿真测试、板级测试和持续集成的工程化 BSP。
- 具备版本管理、故障诊断和现场升级能力的工业级驱动系统。

---

## 2. 前置要求

### 知识要求

1. 熟悉 C 语言：
    - 指针、函数指针、结构体、位操作。
    - `volatile`、内存屏障、链接脚本基础。
    - 编译单元、弱符号、静态库和链接过程。
2. 熟悉 MCU 基础：
    - 中断控制器、时钟树、GPIO、DMA、定时器。
    - Flash、SRAM、Boot 流程。
3. 熟悉 RTOS 基础：
    - 任务、队列、信号量、互斥锁、事件组。
    - 中断上下文和任务上下文的边界。
4. 理解常见通信总线：
    - UART、I2C、SPI、CAN、USB、Ethernet。
5. 具备基本软件工程能力：
    - Git、Make/CMake、编译警告、静态分析、单元测试。

### 技能要求

- 能阅读 MCU Reference Manual 和 Datasheet。
- 能使用逻辑分析仪、示波器、JTAG/SWD 调试器。
- 能查看 `.map` 文件和反汇编结果。
- 能定位 HardFault、BusFault、UsageFault。
- 能基于寄存器和 SDK 实现一个基础外设驱动。

---

## 3. 技术概述

### 3.1 BSP 的定义

BSP，即 Board Support Package，板级支持包，是连接：

- **芯片硬件**
- **具体开发板或产品硬件**
- **操作系统/运行时**
- **上层设备服务和应用**

之间的软件适配层。

BSP 不等同于“启动代码集合”，也不等同于“厂商 HAL 的简单封装”。

一个工业级 BSP 通常包含：

```
启动与复位
├── 启动文件
├── 向量表
├── 异常处理
├── 堆栈和内存初始化
├── 时钟树初始化
└── 系统 Tick 初始化

板级配置
├── PinMux
├── GPIO 默认状态
├── 电源轨
├── 板载 LED / 按键
├── 外部晶振
├── 外部 Flash
├── 传感器连接关系
└── 硬件版本检测

芯片驱动
├── UART
├── SPI
├── I2C
├── ADC
├── PWM
├── DMA
├── Timer
└── Watchdog

设备驱动
├── Flash 芯片
├── 温度传感器
├── IMU
├── 显示屏
├── 电机驱动器
└── 电源管理芯片

操作系统适配
├── Tick
├── 临界区
├── 中断注册
├── Cache 管理
├── DMA 内存属性
└── 线程/锁/事件适配
```

### 3.2 BSP、HAL、驱动、设备服务的边界

推荐分层：

```
应用层
    ↓
业务服务层
    ↓
设备服务层
    ↓
通用设备驱动层
    ↓
总线驱动层
    ↓
芯片 HAL / MCAL
    ↓
寄存器 / CMSIS / SoC 硬件
```

具体职责：

|层级|主要职责|不应承担的职责|
|---|---|---|
|应用层|业务流程、状态机|直接操作寄存器|
|设备服务层|传感器校准、数据聚合、设备策略|直接配置 MCU PinMux|
|设备驱动层|面向具体芯片或设备的数据读写|处理业务状态|
|总线层|UART/I2C/SPI/CAN 传输|解释具体传感器协议|
|HAL/MCAL|屏蔽 MCU 寄存器差异|保存业务状态|
|BSP Board 层|板级连接、PinMux、供电、实例绑定|实现通用总线算法|
|寄存器层|控制硬件寄存器|暴露给应用直接调用|

### 3.3 主流架构分支

#### 方案一：直接静态调用

```
Application → BSP_xxx → Vendor HAL → Register
```

优点：

- 简单。
- 代码体积小。
- 调试链路短。

缺点：

- 可测试性差。
- 业务容易污染 BSP。
- 多硬件变体维护困难。

适合：小型单板、一次性产品、资源极其有限的项目。

#### 方案二：接口抽象 + 实例绑定

```
Application
    ↓
Generic Device API
    ↓
Driver Interface
    ↓
Board Instance
    ↓
Bus Driver
    ↓
MCU HAL
```

优点：

- 支持多硬件版本。
- 方便单元测试和 Mock。
- 适合中大型产品。

缺点：

- 函数指针和对象管理带来少量开销。
- 需要严格定义接口边界。

适合：量产产品和多平台产品。

#### 方案三：设备模型 / Device Tree

```
Device Tree / Board Description
            ↓
Device Model
            ↓
Driver Probe
            ↓
Bus Controller
```

优点：

- 硬件描述与驱动代码分离。
- 适合多 SoC、多板型和复杂设备树。
- Linux、Zephyr 等系统普遍使用。

缺点：

- 追踪调用链复杂。
- 配置错误可能在运行时暴露。
- 小型 MCU 项目可能过度设计。

适合：复杂 SoC、嵌入式 Linux、设备数量多且变化频繁的系统。

---

## 4. 核心特性横向对比

### 4.1 不同驱动组织方式对比

|维度|直接调用 HAL|静态接口封装|面向对象驱动模型|Device Tree/设备模型|
|---|---|---|---|---|
|实现复杂度|低|中|中高|高|
|运行时开销|最低|低|低到中|中|
|多硬件适配|差|好|好|优秀|
|单元测试|差|好|优秀|好|
|调试直观性|优秀|好|中|中低|
|代码体积|最小|小|中|中高|
|初始化复杂度|低|中|高|高|
|适合小 MCU|优秀|优秀|可选|谨慎使用|
|适合多产品线|差|好|优秀|优秀|
|运行时设备探测|差|中|好|优秀|

### 4.2 同步、异步和 DMA 驱动对比

|方案|CPU 占用|实时性|实现复杂度|适用数据量|
|---|---|---|---|---|
|轮询|高|可预测|低|小|
|中断|中低|好|中|中等|
|DMA|很低|好|高|大|
|RTOS 阻塞接口|中|依赖调度|中|非严格实时|
|异步事件接口|低|优秀|高|连续流数据|

### 4.3 BSP 配置方式对比

|配置方式|典型形式|优点|缺点|
|---|---|---|---|
|预处理宏|`#define BOARD_REV_A`|简单、无运行时开销|条件编译污染|
|C 配置表|`const board_cfg_t`|类型安全、结构清晰|需要实例管理|
|链接脚本分区|不同硬件放不同镜像|资源隔离|构建复杂|
|Device Tree|`.dts`|描述与实现分离|工具链复杂|
|EEPROM/OTP 探测|运行时检测|支持同一镜像多板型|启动复杂、失败风险高|

---

## 5. 底层原理与功能特性深度解析

## 5.1 启动链路设计

典型 Cortex-M 启动链路：

```
复位
 ↓
取向量表第 0 项作为 MSP
 ↓
取向量表第 1 项作为 Reset_Handler
 ↓
SystemInit()
 ↓
_data 从 Flash 拷贝到 SRAM
 ↓
_bss 清零
 ↓
时钟初始化
 ↓
C 运行时初始化
 ↓
main()
 ↓
BSP_Init()
 ↓
OS 启动或进入主循环
```

启动文件通常包含：

```
extern int main(void);
extern unsigned long _estack;

__attribute__((section(".isr_vector")))
const void *vector_table[] = {
    &_estack,
    Reset_Handler,
    NMI_Handler,
    HardFault_Handler,
};

void Reset_Handler(void)
{
    extern unsigned long _sidata;
    extern unsigned long _sdata;
    extern unsigned long _edata;
    extern unsigned long _sbss;
    extern unsigned long _ebss;

    unsigned long *src = &_sidata;
    unsigned long *dst = &_sdata;

    while (dst < &_edata) {
        *dst++ = *src++;
    }

    for (dst = &_sbss; dst < &_ebss; ++dst) {
        *dst = 0;
    }

    SystemInit();
    __libc_init_array();

    (void)main();

    for (;;) {
        /* main 返回属于异常情况 */
    }
}
```

### 工程注意事项

1. 向量表必须位于正确地址。
2. 启动阶段不能依赖尚未初始化的全局状态。
3. `SystemInit()` 的执行顺序必须与 Cache、FPU、时钟、内存属性相匹配。
4. 使用外部晶振时必须有超时和降级策略。
5. 不能在启动阶段无限等待外设 ready。

---

## 5.2 BSP 初始化分层

不建议设计为：

```
void bsp_init(void)
{
    clock_init();
    gpio_init();
    uart_init();
    sensor_init();
    display_init();
    application_init();
}
```

因为它混合了：

- 芯片级初始化。
- 板级初始化。
- 设备驱动初始化。
- 业务设备初始化。

推荐拆分：

```
typedef enum {
    BSP_STAGE_EARLY = 0,
    BSP_STAGE_CLOCK,
    BSP_STAGE_PINMUX,
    BSP_STAGE_DRIVER,
    BSP_STAGE_DEVICE,
    BSP_STAGE_SERVICE,
} bsp_stage_t;

typedef int (*bsp_init_fn_t)(void);

typedef struct {
    const char    *name;
    bsp_stage_t    stage;
    bsp_init_fn_t  init;
    uint32_t       timeout_ms;
    bool           mandatory;
} bsp_init_item_t;

int bsp_init_all(const bsp_init_item_t *items, size_t count)
{
    if (items == NULL) {
        return -EINVAL;
    }

    for (bsp_stage_t stage = BSP_STAGE_EARLY;
         stage <= BSP_STAGE_SERVICE;
         ++stage) {

        for (size_t i = 0; i < count; ++i) {
            if (items[i].stage != stage) {
                continue;
            }

            int rc = items[i].init();
            if (rc != 0) {
                log_error("BSP init failed: %s, rc=%d",
                          items[i].name, rc);

                if (items[i].mandatory) {
                    return rc;
                }
            }
        }
    }

    return 0;
}
```

优点：

- 初始化顺序显式化。
- 强制设备和可选设备可以区分。
- 方便启动诊断。
- 可增加启动耗时统计。

---

## 5.3 总线层与设备层分离

以 I2C 为例，不建议在传感器驱动中直接调用厂商 HAL：

```
/* 错误：设备驱动与 MCU HAL 强耦合 */
HAL_I2C_Mem_Read(&hi2c1,
                 SENSOR_ADDR << 1,
                 REG_TEMP,
                 I2C_MEMADD_SIZE_8BIT,
                 buf,
                 2,
                 100);
```

推荐定义总线接口：

```
typedef struct {
    int (*write_read)(void *ctx,
                      uint16_t addr,
                      const uint8_t *tx,
                      size_t tx_len,
                      uint8_t *rx,
                      size_t rx_len,
                      uint32_t timeout_ms);
    int (*lock)(void *ctx, uint32_t timeout_ms);
    int (*unlock)(void *ctx);
    void *ctx;
} i2c_bus_t;
```

设备驱动只依赖总线接口：

```
typedef struct {
    i2c_bus_t *bus;
    uint16_t   address;
    uint16_t   who_am_i_reg;
    uint8_t    expected_id;
} sensor_t;

int sensor_read_reg(sensor_t *dev,
                    uint8_t reg,
                    uint8_t *data,
                    size_t len)
{
    if (dev == NULL || dev->bus == NULL ||
        dev->bus->write_read == NULL ||
        data == NULL || len == 0) {
        return -EINVAL;
    }

    uint8_t tx = reg;

    int rc = dev->bus->lock(dev->bus->ctx, 20);
    if (rc != 0) {
        return rc;
    }

    rc = dev->bus->write_read(dev->bus->ctx,
                              dev->address,
                              &tx,
                              1,
                              data,
                              len);

    int unlock_rc = dev->bus->unlock(dev->bus->ctx);

    return rc != 0 ? rc : unlock_rc;
}
```

这样可以：

- 用真实 I2C 控制器运行。
- 用 Mock 总线做单元测试。
- 复用同一传感器驱动到 SPI 或虚拟总线。
- 将锁、超时和总线恢复集中在总线层。

---

## 5.4 驱动对象与实例化

推荐使用“接口 + 私有数据”的形式：

```
typedef struct device device_t;

typedef struct {
    int  (*init)(device_t *dev);
    int  (*read)(device_t *dev, void *buf, size_t len);
    int  (*write)(device_t *dev, const void *buf, size_t len);
    int  (*ioctl)(device_t *dev, uint32_t cmd, void *arg);
    int  (*deinit)(device_t *dev);
} device_ops_t;

struct device {
    const char       *name;
    const device_ops_t *ops;
    void             *priv;
    uint32_t          flags;
};
```

驱动实例：

```
typedef struct {
    i2c_bus_t *bus;
    uint16_t address;
    uint8_t initialized;
} eeprom_priv_t;

static int eeprom_init(device_t *dev)
{
    if (dev == NULL || dev->priv == NULL) {
        return -EINVAL;
    }

    eeprom_priv_t *priv = dev->priv;

    if (priv->bus == NULL || priv->address == 0) {
        return -EINVAL;
    }

    /* 可执行芯片 ID 检测、写保护状态检测 */
    priv->initialized = 1;
    return 0;
}

static int eeprom_read(device_t *dev, void *buf, size_t len)
{
    if (dev == NULL || dev->priv == NULL ||
        buf == NULL || len == 0) {
        return -EINVAL;
    }

    eeprom_priv_t *priv = dev->priv;

    if (!priv->initialized) {
        return -EPIPE;
    }

    /* 实际实现中应包含页边界、地址范围和超时处理 */
    return 0;
}

static const device_ops_t eeprom_ops = {
    .init   = eeprom_init,
    .read   = eeprom_read,
    .write  = NULL,
    .ioctl  = NULL,
    .deinit = NULL,
};
```

### 接口设计原则

- 不要把具体芯片寄存器暴露给上层。
- 不要把 `HAL_HandleTypeDef` 直接作为公共接口类型。
- 不要让公共接口返回模糊的 `-1`。
- 每个接口都应定义：
    - 参数有效性。
    - 并发语义。
    - 超时语义。
    - 中断上下文限制。
    - 缓冲区所有权。
    - 错误码范围。

---

## 5.5 中断、DMA 与缓存一致性

在带 D-Cache 的 Cortex-M7 或 Cortex-A 系统中，DMA 缓冲区必须考虑 Cache 一致性。

典型问题：

```
CPU 写入 buffer
 ↓
数据停留在 Cache
 ↓
DMA 从 SRAM 读取旧数据
```

或：

```
DMA 写入 SRAM
 ↓
CPU Cache 中仍有旧副本
 ↓
CPU 读取到旧数据
```

推荐方式：

```
#define CACHE_LINE_SIZE 32U

static size_t align_down(size_t value, size_t align)
{
    return value & ~(align - 1U);
}

static size_t align_up(size_t value, size_t align)
{
    return (value + align - 1U) & ~(align - 1U);
}

void dma_prepare_tx(void *buf, size_t len)
{
    uintptr_t start = (uintptr_t)buf;
    uintptr_t aligned_start = align_down(start, CACHE_LINE_SIZE);
    size_t offset = start - aligned_start;
    size_t aligned_len = align_up(len + offset, CACHE_LINE_SIZE);

    SCB_CleanDCache_by_Addr((uint32_t *)aligned_start,
                            (int32_t)aligned_len);
    __DSB();
}

void dma_prepare_rx(void *buf, size_t len)
{
    uintptr_t start = (uintptr_t)buf;
    uintptr_t aligned_start = align_down(start, CACHE_LINE_SIZE);
    size_t offset = start - aligned_start;
    size_t aligned_len = align_up(len + offset, CACHE_LINE_SIZE);

    SCB_InvalidateDCache_by_Addr((uint32_t *)aligned_start,
                                 (int32_t)aligned_len);
    __DSB();
    __ISB();
}
```

工程中还应考虑：

- DMA 缓冲区按 Cache Line 对齐。
- 不在 DMA 期间修改缓冲区。
- 多核 SoC 需要内存屏障和共享内存属性。
- Linux 中应使用 DMA API，不应直接操作 Cache。
- 中断处理程序只做状态确认和事件投递，复杂处理放在线程上下文。

---

## 5.6 驱动状态机

高可靠驱动不应仅使用一个 `initialized` 标志，推荐状态机：

```
typedef enum {
    DEV_STATE_RESET = 0,
    DEV_STATE_CONFIGURED,
    DEV_STATE_READY,
    DEV_STATE_BUSY,
    DEV_STATE_ERROR,
    DEV_STATE_SUSPENDED,
} dev_state_t;
```

典型状态转换：

```
RESET
  ↓ init 成功
CONFIGURED
  ↓ 自检成功
READY
  ↓ 启动传输
BUSY
  ↓ 完成
READY

任意状态
  ↓ 超时/总线错误
ERROR
  ↓ recover 成功
READY
  ↓ suspend
SUSPENDED
```

状态机可以避免：

- 未初始化访问设备。
- 设备忙时重复启动。
- 错误状态下继续提交事务。
- 睡眠期间访问已关闭时钟的外设。

---

## 6. 性能量化分析

以下数据以 **STM32H743，480 MHz，Cortex-M7，GCC -O2，FreeRTOS，I2C 400 kHz** 为示例测试参考。不同芯片、编译器和驱动实现会有差异，实际项目应使用 DWT、逻辑分析仪和 Trace 工具复测。

### 6.1 调用开销

|调用方式|典型额外 CPU 周期|480 MHz 下时间|
|---|---|---|
|直接寄存器访问|5～20 cycles|10～42 ns|
|厂商 HAL 调用|100～400 cycles|0.21～0.83 μs|
|一层函数指针|8～20 cycles|17～42 ns|
|两层函数指针|15～35 cycles|31～73 ns|
|RTOS Mutex 获取|150～800 cycles|0.31～1.67 μs|
|任务切换|500～2000 cycles|1.04～4.17 μs|

**结论：**

- 对 UART、I2C、SPI 这类总线设备，通信本身通常是主要耗时，函数指针抽象成本可以接受。
- 对 GPIO 翻转、位带操作、纳秒级控制路径，不应使用过深抽象。
- 高频实时路径可提供 `static inline` 快速接口。

### 6.2 I2C 传输时间

I2C 每个字节通常包含：

- 8 位数据。
- 1 位 ACK/NACK。

因此：

```
传输时间 ≈ (起始/地址/寄存器/数据/停止等总位数) / 总线频率
```

例如读取一个寄存器：

```
START + 地址写 + ACK + 寄存器 + ACK
+ RESTART + 地址读 + ACK + 数据 + NACK + STOP
≈ 27～36 bit
```

在 400 kHz 下：

```
T ≈ 36 / 400000
  ≈ 90 μs
```

如果驱动增加：

- RTOS 锁：0.5～2 μs。
- 中断唤醒：2～10 μs。
- 总线恢复：可能达到数十到数百微秒。

因此，单纯优化 C 函数指针通常不能显著降低 I2C 事务总时间，真正的瓶颈是总线速率、事务数量和设备内部转换时间。

### 6.3 内存开销

典型驱动实例：

```
typedef struct {
    i2c_bus_t *bus;       /* 4/8 bytes */
    uint16_t address;     /* 2 bytes */
    uint8_t initialized;  /* 1 byte */
    uint8_t state;        /* 1 byte */
    uint32_t timeout_ms;  /* 4 bytes */
} sensor_priv_t;
```

在 32 位 MCU 上通常为 **16～24 字节**，加上：

- 设备对象：约 16～32 字节。
- RTOS Mutex：约 40～80 字节。
- DMA 缓冲区：根据协议决定。
- 事务队列：每项约 24～64 字节。

### 6.4 阻塞接口与异步接口

假设 SPI 发送 4096 字节，SPI 速率 20 MHz：

```
传输时间 = 4096 × 8 / 20 MHz
         ≈ 1.638 ms
```

#### 阻塞轮询

若 CPU 全程轮询：

```
CPU 占用 ≈ 1.638 ms
```

#### 中断模式

假设每 8 字节产生一次中断，每次 ISR 消耗 1.2 μs：

```
中断次数 = 4096 / 8 = 512
ISR 总耗时 = 512 × 1.2 μs = 614.4 μs
```

#### DMA 模式

假设 DMA 配置和完成中断总耗时 8 μs：

```
CPU 占用 ≈ 8 μs
CPU 节省 ≈ 1.638 ms - 8 μs
       ≈ 1.630 ms
```

**结论：**

- 小于几十字节的低频事务，轮询可能更简单。
- 中等频率事务适合中断。
- 连续数据流、显示刷屏、音频采样、网络帧传输应优先 DMA。
- DMA 的代价是缓存一致性、生命周期和错误恢复复杂度。

### 6.5 启动时间分析

推荐记录每个 BSP 初始化节点：

```
uint32_t start = bsp_time_us();
int rc = item->init();
uint32_t elapsed = bsp_time_us() - start;

log_info("init %-16s rc=%d time=%lu us",
         item->name, rc, (unsigned long)elapsed);
```

常见启动时间组成：

```
总启动时间 =
时钟稳定时间
+ 外部 Flash 初始化
+ 传感器上电稳定时间
+ 总线设备探测时间
+ 文件系统挂载时间
+ RTOS 启动前初始化
```

优化方式：

- 把非关键设备延迟初始化。
- 多个独立设备并行初始化。
- 缩短设备探测重试次数。
- 保存硬件配置缓存，减少重复探测。
- 对必需设备和可选设备分别处理。

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否只有一块固定硬件？
├── 是
│   ├── 资源极少、功能简单？
│   │   ├── 是 → 直接 BSP + 轻量 HAL 封装
│   │   └── 否 → 静态接口 + 设备实例表
│
└── 否
    ├── 是否存在多个 MCU/SoC 平台？
    │   ├── 是
    │   │   ├── 外设数量少？
    │   │   │   ├── 是 → 跨平台接口 + 平台适配层
    │   │   │   └── 否 → 设备模型 + 设备描述配置
    │   │
    │   └── 否
    │       ├── 是否存在多个板卡版本？
    │       │   ├── 是 → Board Variant + 配置表
    │       │   └── 否 → 静态绑定
    │
    └── 是否需要运行时探测/热插拔？
        ├── 是 → 设备注册表 + Probe/Remove
        └── 否 → 编译期实例化
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|低成本传感器节点|轻量 BSP + 静态设备表|代码小，启动快|
|工业控制器多硬件版本|Board Variant + 抽象总线层|降低硬件变更影响|
|Linux 网关|Device Tree + 设备模型|设备数量多，平台复杂|
|电机控制实时环|分层但保留快速路径|控制回路不能承受过度抽象|
|车载 ECU|MCAL + RTE 风格接口|规范化、可验证、可移植|
|显示与音频设备|DMA + 异步驱动 + 缓冲队列|降低 CPU 占用|
|量产产品|配置表 + 诊断 + 版本检测|支持现场维护和硬件兼容|

---

## 8. 工程最佳实践

## 8.1 推荐目录结构

```
bsp/
├── common/
│   ├── bsp_init.c
│   ├── bsp_error.c
│   ├── bsp_time.c
│   └── bsp_log.c
├── startup/
│   ├── startup_xxx.s
│   ├── system_xxx.c
│   └── vectors.c
├── chip/
│   └── stm32h7/
│       ├── clock.c
│       ├── dma.c
│       ├── irq.c
│       └── cache.c
├── board/
│   ├── board_common.c
│   ├── board_rev_a.c
│   ├── board_rev_b.c
│   ├── board_config.h
│   └── pinmux.c
├── drivers/
│   ├── bus/
│   │   ├── i2c/
│   │   ├── spi/
│   │   └── uart/
│   ├── device/
│   │   ├── sensor/
│   │   ├── eeprom/
│   │   └── display/
│   └── storage/
├── osal/
│   ├── osal_mutex.c
│   ├── osal_event.c
│   └── osal_time.c
└── tests/
    ├── mock_i2c.c
    └── test_sensor.c
```

## 8.2 依赖方向

推荐：

```
app
 ↓
service
 ↓
device_driver
 ↓
bus_interface
 ↓
bsp/chip_hal
```

禁止：

```
bsp → app
driver → business_service
HAL → sensor_driver
common → concrete_board
```

如果底层需要通知上层，应使用：

- 回调。
- 事件队列。
- 观察者接口。
- 注册表。
- OS 消息机制。

不要直接调用上层业务函数。

## 8.3 选型决策矩阵

|条件|静态封装|设备对象|设备模型|
|---|---|---|---|
|单板固定|5|3|1|
|多板型|3|5|5|
|运行时探测|1|4|5|
|资源极小|5|4|2|
|单元测试|2|5|4|
|复杂依赖管理|2|4|5|
|快速量产|5|4|3|

评分越高越适合。

## 8.4 工业级编码规范

- 所有公共驱动接口必须检查参数。
- 使用明确错误码：
    - `-EINVAL`
    - `-ETIMEDOUT`
    - `-EIO`
    - `-EBUSY`
    - `-ENODEV`
    - `-EAGAIN`
- 所有等待必须有超时。
- 所有锁必须定义上下文限制。
- ISR 中禁止：
    - 阻塞锁。
    - 动态内存分配。
    - 长时间轮询。
    - 复杂日志输出。
- 驱动不能隐式修改用户缓冲区内容。
- DMA 缓冲区必须明确：
    - 对齐要求。
    - 所有权。
    - 生命周期。
    - Cache 操作。
- 驱动初始化和反初始化必须成对设计。
- 不要滥用弱符号覆盖关键功能。
- 不要在公共头文件中暴露厂商 HAL 类型。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：应用层直接调用 HAL

### 错误代码

```
void application_read_temperature(void)
{
    uint8_t data[2];

    HAL_I2C_Mem_Read(&hi2c1,
                     0x48 << 1,
                     0x00,
                     I2C_MEMADD_SIZE_8BIT,
                     data,
                     2,
                     100);
}
```

### 根因

- 应用层知道了 MCU 句柄。
- 应用层知道了传感器寄存器协议。
- 更换 MCU 或 I2C 实例会修改业务代码。
- 无法对应用进行脱离硬件测试。

### 正确实现

```
int temperature_service_get(float *value)
{
    if (value == NULL) {
        return -EINVAL;
    }

    return temperature_device_read(&g_temperature, value);
}
```

### 风险影响

- 平台迁移成本高。
- 业务代码不可复用。
- 硬件变更导致大范围回归。

---

## 9.2 错误二：无限等待设备状态

### 错误代码

```
while ((I2C1->ISR & I2C_ISR_STOPF) == 0) {
    /* 无限等待 */
}
```

### 根因

- 外设时钟异常。
- 总线被拉低。
- 从设备掉电。
- 中断标志未清除。
- 代码永远卡死。

### 正确实现

```
int i2c_wait_stop(uint32_t timeout_us)
{
    uint32_t start = bsp_time_us();

    while ((I2C1->ISR & I2C_ISR_STOPF) == 0U) {
        if ((bsp_time_us() - start) >= timeout_us) {
            I2C1->ICR = I2C_ICR_STOPCF;
            i2c_bus_recover();
            return -ETIMEDOUT;
        }
    }

    I2C1->ICR = I2C_ICR_STOPCF;
    return 0;
}
```

### 风险影响

- 任务永久阻塞。
- 看门狗复位。
- 控制系统失去响应。
- 现场表现为“偶发死机”。

---

## 9.3 错误三：I2C 总线锁粒度错误

### 错误代码

```
mutex_lock(&i2c_mutex);

i2c_write_register(addr, reg, value);

/* 在持锁期间执行较长设备延时 */
delay_ms(20);

i2c_read_register(addr, reg, &value);

mutex_unlock(&i2c_mutex);
```

### 根因

- 将设备内部转换延迟也放在总线锁内。
- 其他设备无法使用总线。
- 高优先级任务可能被低优先级任务长期阻塞。

### 正确实现

```
int sensor_start_conversion(sensor_t *dev)
{
    int rc;

    rc = bus_lock(dev->bus, 10);
    if (rc != 0) {
        return rc;
    }

    rc = sensor_write_command(dev, SENSOR_CMD_START);
    (void)bus_unlock(dev->bus);

    return rc;
}

int sensor_read_conversion(sensor_t *dev, uint16_t *value)
{
    if (!sensor_conversion_ready(dev)) {
        return -EAGAIN;
    }

    int rc = bus_lock(dev->bus, 10);
    if (rc != 0) {
        return rc;
    }

    rc = sensor_read_result(dev, value);
    int unlock_rc = bus_unlock(dev->bus);

    return rc != 0 ? rc : unlock_rc;
}
```

### 风险影响

- 总线吞吐降低。
- 优先级反转。
- 任务响应延迟不可预测。

---

## 9.4 错误四：DMA 缓冲区缓存不一致

### 错误代码

```
static uint8_t rx_buffer[1024];

start_dma_receive(rx_buffer, sizeof(rx_buffer));

/* DMA 完成后直接读取 */
parse_packet(rx_buffer);
```

### 根因

- CPU Cache 中保留旧数据。
- DMA 更新了 SRAM，但 CPU 读取了 Cache。
- 缓冲区未按 Cache Line 对齐。

### 正确实现

```
__attribute__((aligned(32)))
static uint8_t rx_buffer[1024];

void dma_rx_complete(void)
{
    dma_prepare_rx(rx_buffer, sizeof(rx_buffer));
    parse_packet(rx_buffer);
}
```

### 风险影响

- 数据包偶发解析错误。
- 错误难以复现。
- 高温、高负载或开启 Cache 后才出现。

---

## 9.5 错误五：驱动初始化顺序隐式依赖

### 错误代码

```
int sensor_init(void)
{
    /* 假设 I2C 已经初始化 */
    return i2c_transfer(...);
}
```

### 根因

- 依赖关系只存在于调用者脑中。
- 改变链接顺序或启动流程后产生隐藏故障。

### 正确实现

```
int sensor_init(void)
{
    if (!device_is_ready(&g_i2c1)) {
        return -ENODEV;
    }

    if (!gpio_is_ready(&g_sensor_power)) {
        return -ENODEV;
    }

    return sensor_probe(&g_sensor);
}
```

### 风险影响

- 启动偶发失败。
- 不同构建配置表现不一致。
- 现场升级后初始化异常。

---

## 10. 多机制组合使用方案

## 10.1 推荐协同架构

```
┌──────────────────┐
                │ Application       │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Device Service    │
                │ 校准/状态/策略     │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Generic Driver   │
                │ 统一设备接口       │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Bus Adapter      │
                │ 锁/超时/DMA/恢复  │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Chip HAL/MCAL    │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Hardware         │
                └──────────────────┘
```

组合机制：

1. **接口抽象**：隔离上层和底层。
2. **设备对象**：支持多实例。
3. **配置表**：支持多板型。
4. **状态机**：管理设备生命周期。
5. **事件队列**：实现异步处理。
6. **DMA**：降低 CPU 占用。
7. **看门狗与错误恢复**：提高现场可靠性。
8. **诊断接口**：支持运行时状态查询。

## 10.2 完整代码框架

```
typedef enum {
    SENSOR_EVT_DATA_READY = 1,
    SENSOR_EVT_ERROR,
    SENSOR_EVT_TIMEOUT,
} sensor_event_t;

typedef struct {
    i2c_bus_t *bus;
    uint16_t address;
    dev_state_t state;
    void (*event_cb)(sensor_event_t event, void *arg);
    void *cb_arg;
} sensor_device_t;

static int sensor_recover(sensor_device_t *dev)
{
    if (dev == NULL || dev->bus == NULL) {
        return -EINVAL;
    }

    dev->state = DEV_STATE_ERROR;

    int rc = bus_reset(dev->bus);
    if (rc == 0) {
        rc = sensor_hw_init(dev);
    }

    dev->state = (rc == 0) ? DEV_STATE_READY : DEV_STATE_ERROR;
    return rc;
}

static int sensor_start(sensor_device_t *dev)
{
    if (dev == NULL) {
        return -EINVAL;
    }

    if (dev->state != DEV_STATE_READY) {
        return -EBUSY;
    }

    int rc = sensor_command_start(dev);
    if (rc != 0) {
        (void)sensor_recover(dev);
        return rc;
    }

    dev->state = DEV_STATE_BUSY;
    return 0;
}

void sensor_irq_handler(sensor_device_t *dev)
{
    if (dev == NULL) {
        return;
    }

    uint32_t status = sensor_read_irq_status(dev);

    if ((status & SENSOR_DATA_READY) != 0U) {
        dev->state = DEV_STATE_READY;

        if (dev->event_cb != NULL) {
            dev->event_cb(SENSOR_EVT_DATA_READY, dev->cb_arg);
        }
    }

    if ((status & SENSOR_ERROR) != 0U) {
        dev->state = DEV_STATE_ERROR;

        if (dev->event_cb != NULL) {
            dev->event_cb(SENSOR_EVT_ERROR, dev->cb_arg);
        }
    }
}
```

关键点：

- ISR 不执行完整数据读取。
- ISR 只确认硬件状态并投递事件。
- 设备驱动拥有状态机。
- 总线层管理锁、超时和恢复。
- 设备服务层负责重试、校准和业务策略。

---

## 11. 工业级实际案例分析

## 11.1 案例一：多版本工业控制器 BSP

### 需求

同一产品存在：

- Board Rev A：温度传感器连接 I2C1。
- Board Rev B：温度传感器连接 I2C3。
- Rev B 增加电源使能 GPIO。
- 需要同一软件镜像支持两种板卡。

### 架构设计

```
启动
 ↓
读取 EEPROM 板卡 ID
 ↓
选择 board_config
 ↓
配置 PinMux 和电源
 ↓
绑定 I2C 实例
 ↓
初始化温度传感器
```

### 核心代码

```
typedef struct {
    uint32_t board_id;
    i2c_bus_t *sensor_bus;
    gpio_t sensor_power;
    uint16_t sensor_addr;
} board_config_t;

static const board_config_t board_rev_a = {
    .board_id = 0xA001,
    .sensor_bus = &g_i2c1,
    .sensor_power = GPIO_INVALID,
    .sensor_addr = 0x48,
};

static const board_config_t board_rev_b = {
    .board_id = 0xB001,
    .sensor_bus = &g_i2c3,
    .sensor_power = {
        .port = GPIO_PORT_C,
        .pin = 5,
    },
    .sensor_addr = 0x48,
};

const board_config_t *board_detect(void)
{
    uint32_t id = board_read_id();

    switch (id) {
    case 0xA001:
        return &board_rev_a;
    case 0xB001:
        return &board_rev_b;
    default:
        return NULL;
    }
}
```

### 设计要点

- 设备驱动不感知 Rev A/Rev B。
- Board 层只负责实例选择和 GPIO/电源配置。
- 板卡检测失败时必须进入安全模式，而不是随机选择默认配置。
- 应记录板卡 ID、软件版本和 BSP 版本。

---

## 11.2 案例二：高吞吐 SPI 显示驱动

### 需求

- SPI 速率 40 MHz。
- 屏幕刷新区域最多 320×240×16 bit。
- 使用 FreeRTOS。
- CPU 还承担控制算法和通信任务。
- 要求刷新时 CPU 占用低于 10%。

### 架构

```
显示服务
 ↓
Frame Buffer 管理
 ↓
异步 LCD 驱动
 ↓
SPI DMA
 ↓
DMA 完成事件
```

### 关键设计

```
typedef struct {
    const uint8_t *buf;
    size_t len;
    void (*done)(int status, void *arg);
    void *arg;
} spi_async_req_t;

int lcd_flush_async(const void *frame,
                    size_t bytes,
                    void (*done)(int, void *),
                    void *arg)
{
    if (frame == NULL || bytes == 0 || done == NULL) {
        return -EINVAL;
    }

    if (lcd_state != LCD_READY) {
        return -EBUSY;
    }

    lcd_state = LCD_BUSY;

    dma_prepare_tx((void *)frame, bytes);

    int rc = spi_dma_start(frame, bytes, lcd_dma_complete);
    if (rc != 0) {
        lcd_state = LCD_ERROR;
        return rc;
    }

    g_lcd_done = done;
    g_lcd_done_arg = arg;
    return 0;
}

static void lcd_dma_complete(int status)
{
    lcd_state = (status == 0) ? LCD_READY : LCD_ERROR;

    if (g_lcd_done != NULL) {
        g_lcd_done(status, g_lcd_done_arg);
    }
}
```

### 设计要点

- 不能复制整个 Frame Buffer，避免额外内存和时间开销。
- DMA 期间禁止修改发送缓冲区。
- 使用双缓冲或区域刷新减少数据量。
- 传输完成事件通过任务通知或事件组传递。
- 错误后应重新初始化 SPI 和 LCD 控制器。

---

## 11.3 案例三：工业传感器总线故障恢复

### 需求

- 多个传感器共享 I2C。
- 现场可能出现 SDA 被拉低。
- 单次事务不得阻塞超过 10 ms。
- 设备故障后可以自动恢复。

### 恢复策略

```
事务失败
 ↓
检查 BUSY
 ↓
尝试发送 STOP
 ↓
禁用 I2C 外设
 ↓
GPIO 模式接管 SCL/SDA
 ↓
输出 9 个 SCL 脉冲
 ↓
产生 STOP 条件
 ↓
恢复 I2C 外设
 ↓
重新 Probe 设备
 ↓
成功：恢复 READY
失败：上报故障
```

### 核心代码

```
int i2c_bus_recover(void)
{
    i2c_disable();

    gpio_set_mode(I2C_SCL, GPIO_OUTPUT_OD);
    gpio_set_mode(I2C_SDA, GPIO_OUTPUT_OD);

    gpio_write(I2C_SDA, 1);

    for (int i = 0; i < 9; ++i) {
        gpio_write(I2C_SCL, 0);
        delay_us(5);
        gpio_write(I2C_SCL, 1);
        delay_us(5);

        if (gpio_read(I2C_SDA) != 0) {
            break;
        }
    }

    /* 产生 STOP：SDA 从低到高，同时 SCL 为高 */
    gpio_write(I2C_SDA, 0);
    delay_us(5);
    gpio_write(I2C_SCL, 1);
    delay_us(5);
    gpio_write(I2C_SDA, 1);

    i2c_restore_pins();
    i2c_enable();

    return i2c_bus_is_idle() ? 0 : -EIO;
}
```

### 设计要点

- 恢复流程必须有总超时。
- 恢复过程中禁止其他任务访问总线。
- 恢复成功不等于设备状态正常，还应重新 Probe。
- 连续失败应进入降级状态，避免无限重试占用 CPU。

---

## 12. 高频问题深度答疑

## 问题一：BSP 和 HAL 到底有什么区别？

**HAL 主要屏蔽芯片寄存器差异，BSP 主要描述具体板卡如何使用芯片。**

例如：

- HAL：提供 `uart_send()`。
- BSP：决定调试串口使用 USART3、波特率为 115200、连接哪些 GPIO。
- 设备驱动：决定如何通过 UART 访问具体设备协议。
- 应用：只调用日志或设备服务接口。

可以理解为：

```
HAL = 芯片能力抽象
BSP = 板卡资源绑定
Driver = 设备行为实现
Service = 业务设备策略
```

---

## 问题二：驱动抽象是否一定会降低性能？

不一定。

主要需要区分：

1. **调用开销**
    - 函数指针通常只有几十个周期。
2. **设备事务开销**
    - I2C、SPI、UART 的传输时间通常远大于函数调用。
3. **实时闭环开销**
    - GPIO 翻转、电机控制 PWM 更新可能对纳秒级延迟敏感。

原则：

- 总线型设备适合抽象。
- 高频硬实时路径保留专用快速接口。
- 可用 `static inline`、编译期绑定和 LTO 降低开销。
- 不要为了理论性能消除所有抽象，而牺牲可维护性。

---

## 问题三：驱动接口应该返回 errno，还是自定义错误码？

小型项目可以使用统一自定义错误码，大型项目推荐采用类似 POSIX 的错误语义：

```
-EINVAL     参数错误
-ENODEV     设备不存在
-ETIMEDOUT  超时
-EIO        硬件 I/O 错误
-EBUSY      设备忙
-EAGAIN     稍后重试
-EPERM      权限或上下文错误
```

重要的是：

- 全项目统一。
- 能区分参数错误、瞬态错误和永久错误。
- 支持错误恢复策略。
- 不要只返回 `-1`。

---

## 问题四：驱动是否应负责自动重试？

应根据错误类型区分：

|错误类型|是否重试|
|---|---|
|仲裁丢失|可以短次数重试|
|总线忙|延迟后重试|
|NACK|根据设备状态决定|
|参数错误|不应重试|
|设备不存在|启动阶段有限重试|
|DMA 错误|恢复后有限重试|
|硬件永久故障|不应无限重试|

推荐：

```
单次事务重试：1～3 次
连续故障：执行总线恢复
恢复失败：进入 ERROR
由上层决定降级或复位
```

不要让底层驱动无限重试。

---

## 问题五：BSP 是否应该包含业务设备驱动？

应区分“设备驱动”和“业务服务”。

例如：

- `bsp/drivers/bme280.c`：属于设备驱动。
- `services/environment.c`：负责温度校准、报警和采样周期，属于服务层。
- `application/thermal_control.c`：负责控制策略，属于应用层。

BSP 可以包含设备驱动实现，但不应包含业务策略。

---

## 问题六：硬件变体应该编译多个固件，还是一个固件运行时识别？

### 编译多个固件

优点：

- 代码路径简单。
- 无运行时探测风险。
- 可做更激进的编译优化。

缺点：

- 发布包复杂。
- 现场刷错版本风险高。

### 一个固件运行时识别

优点：

- 现场部署方便。
- 同一软件支持多个硬件版本。

缺点：

- 启动流程复杂。
- 必须处理探测失败。
- 代码体积和测试组合增加。

推荐：

- 硬件差异大：多个镜像。
- 仅引脚、总线实例、电源控制不同：一个镜像 + Board Config。
- 现场无法确认硬件版本：优先运行时识别，但必须有安全默认策略。

---

## 13. 课程核心总结

### 13.1 核心要点

1. **BSP 不是简单的启动代码，也不是厂商 HAL 的重命名。**
2. BSP 的核心职责是：
    - 启动。
    - 时钟。
    - PinMux。
    - 板级资源绑定。
    - 芯片和设备实例化。
    - OS 与硬件适配。
3. 推荐依赖方向：

```
应用 → 服务 → 设备驱动 → 总线 → HAL/MCAL → 寄存器
```

4. 设备驱动不应直接依赖具体 MCU HAL。
5. 总线层必须集中处理：
    - 锁。
    - 超时。
    - DMA。
    - Cache。
    - 总线恢复。
6. 初始化应显式管理阶段、依赖和失败策略。
7. 多硬件版本优先使用：
    - Board Config。
    - 设备实例表。
    - 编译期特性开关。
8. 异步驱动适合高吞吐设备，DMA 适合大数据量传输。
9. ISR 只处理硬件确认和事件投递，不承担完整业务。
10. 所有等待都必须有上限，所有错误都必须有恢复或降级路径。

### 13.2 性能排序

对于 CPU 开销，通常从低到高：

```
直接寄存器
< 静态 inline 封装
< 普通函数调用
< 函数指针调用
< HAL 轮询
< 中断驱动
< RTOS 阻塞接口
< 复杂设备模型运行时探测
```

但对于总线设备，实际总时间往往是：

```
总线传输时间
≫ HAL 调用开销
≫ 函数指针抽象开销
```

### 13.3 通用选型结论

|项目类型|推荐架构|
|---|---|
|小型固定单板|轻量 BSP + 静态封装|
|中型量产 MCU 产品|接口抽象 + 设备实例 + Board Config|
|多板型产品|Board Variant + 配置表 + 统一驱动|
|多 SoC/复杂设备系统|设备模型 + Device Tree|
|高实时控制|分层架构 + 专用快速路径|
|大数据流设备|异步接口 + DMA + 双缓冲|
|工业现场系统|超时 + 恢复 + 诊断 + 降级|

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐实现|
|---|---|
|单个 GPIO LED|BSP Board API|
|多实例 UART|UART Controller + Device Instance|
|多设备共享 I2C|Bus Object + Mutex + Timeout|
|SPI 屏幕|Async + DMA + Frame Buffer|
|ADC 连续采样|Timer Trigger + DMA + Ring Buffer|
|外部 Flash|SPI/QSPI Bus + Flash Driver|
|多硬件版本|Board Config + Runtime Detection|
|Linux SoC 外设|Device Tree + Driver Probe|
|高实时 PWM|静态绑定 + Inline Fast Path|
|现场总线故障|Recovery State Machine|

### 14.2 驱动层级表

|层级|关键对象|典型接口|
|---|---|---|
|Board|Pin、Clock、Power、Instance|`board_init()`|
|HAL/MCAL|Register、Peripheral Handle|`hal_uart_tx()`|
|Bus|Transaction、Lock、DMA|`bus_transfer()`|
|Device Driver|Device State、Register Map|`sensor_read()`|
|Service|Calibration、Policy|`temperature_get()`|
|Application|Workflow、State Machine|`control_loop()`|

### 14.3 必须检查的工程属性

```
[ ] 是否所有等待都有超时？
[ ] 是否明确 ISR/线程上下文限制？
[ ] 是否处理 DMA Cache 一致性？
[ ] 是否有总线恢复机制？
[ ] 是否支持多实例？
[ ] 是否暴露了厂商 HAL 类型？
[ ] 是否有设备初始化状态机？
[ ] 是否有失败降级策略？
[ ] 是否有启动耗时统计？
[ ] 是否能使用 Mock 做单元测试？
[ ] 是否能从 .map 文件确认内存占用？
[ ] 是否记录硬件版本和 BSP 版本？
```

---

## 15. 学习效果自检

完成本课后，应能够回答：

### 架构能力

- 能否画出应用、服务、设备驱动、总线、HAL 和寄存器之间的依赖关系？
- 能否解释 BSP 与 HAL 的边界？
- 能否设计支持两个板卡版本的配置机制？
- 能否判断何时使用静态绑定，何时使用设备模型？

### 驱动实现能力

- 能否为一个 I2C 传感器设计可测试的驱动接口？
- 能否实现同步和异步两种 API？
- 能否设计驱动状态机？
- 能否处理设备不存在、NACK、超时和总线卡死？

### 实时性能力

- 能否估算一次 SPI/I2C 事务的理论时间？
- 能否计算 DMA 相对于轮询的 CPU 节省？
- 能否分析 Mutex 引入的延迟？
- 能否识别锁粒度过大导致的优先级反转？

### 工程化能力

- 能否组织一个可维护的 BSP 目录？
- 能否使用 Mock 总线测试设备驱动？
- 能否在启动阶段记录每个模块耗时？
- 能否从错误日志定位初始化失败阶段？

### 高阶设计能力

- 能否设计 I2C 总线自动恢复机制？
- 能否解释 DMA 与 D-Cache 的一致性问题？
- 能否将设备驱动迁移到不同 MCU？
- 能否区分驱动逻辑、板级配置和业务策略？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：构建基础 BSP

实现：

- 启动文件。
- 时钟初始化。
- SysTick 或硬件定时器。
- GPIO LED。
- UART 日志。

要求：

- 记录启动阶段。
- 对时钟配置失败进行错误处理。
- UART 发送必须有超时。

### 任务二：实现统一 GPIO 接口

实现：

```
int gpio_configure(const gpio_t *gpio,
                   gpio_mode_t mode,
                   gpio_pull_t pull);

int gpio_write(const gpio_t *gpio, bool level);
int gpio_read(const gpio_t *gpio, bool *level);
```

要求：

- 不暴露芯片寄存器。
- 支持不同 Board Variant。
- 支持无效 GPIO 检查。

### 任务三：实现 I2C 总线抽象

要求：

- 支持锁。
- 支持超时。
- 支持同步事务。
- 支持总线恢复。
- 使用 Mock I2C 完成单元测试。

### 任务四：实现传感器设备驱动

要求：

- Probe 和 ID 检测。
- 初始化状态机。
- 寄存器读写。
- 设备超时。
- 错误恢复。
- 与 I2C HAL 解耦。

### 任务五：实现 SPI DMA 异步驱动

要求：

- DMA 发送。
- 完成回调。
- 传输状态机。
- Cache 维护。
- 双缓冲。
- 错误后重新初始化。

### 任务六：支持多板卡单镜像

要求：

- 通过 EEPROM/ADC 电阻编码识别硬件版本。
- 选择不同的 PinMux、I2C 实例和电源控制。
- 同一设备驱动不修改代码。
- 探测失败进入安全模式。

---

## 16.2 性能测试方法

### CPU 周期测量

使用 Cortex-M DWT：

```
static void dwt_enable(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

uint32_t measure_cycles(void (*fn)(void))
{
    uint32_t start = DWT->CYCCNT;
    fn();
    return DWT->CYCCNT - start;
}
```

### 中断延迟测量

- 使用 GPIO 在 ISR 入口翻转。
- 使用示波器测量外部事件到 GPIO 翻转的时间。
- 分别测量：
    - 无 RTOS。
    - RTOS 空闲。
    - 高优先级任务运行。
    - Cache 开启。
    - DMA 正在运行。

### 总线性能测量

- 逻辑分析仪测量 START 到 STOP。
- 统计：
    - 单次事务时间。
    - 总线空闲比例。
    - 重试比例。
    - NACK 比例。
    - 总线恢复次数。

### 内存测试

- 查看 `.map` 文件。
- 统计：
    - `.text`
    - `.rodata`
    - `.data`
    - `.bss`
    - 堆
    - 各任务栈
    - DMA 缓冲区
- 使用栈水位检测峰值使用量。

---

## 16.3 进阶学习方向

1. **AUTOSAR Classic**
    - MCAL。
    - ECU Abstraction。
    - RTE。
    - BSW 分层。
2. **Zephyr Device Model**
    - Device Tree。
    - `DEVICE_DT_DEFINE`。
    - Driver API。
    - Init Level。
3. **嵌入式 Linux 驱动**
    - Platform Driver。
    - Device Tree。
    - Regmap。
    - Runtime PM。
    - DMA API。
4. **高可靠驱动设计**
    - 故障注入。
    - 看门狗。
    - Brown-out。
    - ECC。
    - 安全状态。
5. **多核与异构 SoC**
    - 共享内存。
    - Mailbox。
    - Cache Coherency。
    - AMP/SMP。
6. **驱动自动化测试**
    - Host Mock。
    - HIL。
    - SIL。
    - 故障注入。
    - 覆盖率和静态分析。
7. **性能与实时性**
    - Worst-Case Execution Time。
    - Tracealyzer。
    - ETM/ITM。
    - 中断延迟预算。
    - 优先级反转分析。
8. **安全启动和可信 BSP**
    - Secure Boot。
    - 固件签名。
    - 关键外设访问控制。
    - 安全升级和回滚。

**最终目标不是“把驱动写出来”，而是建立一个具备清晰边界、可测试、可迁移、可诊断、可恢复并能量化性能的板级软件体系。**