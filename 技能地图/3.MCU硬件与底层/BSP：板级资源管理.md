
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 BSP 在应用层、驱动框架、HAL、启动代码和硬件原理图之间的定位。
- 理解“板级资源”不仅包括 GPIO、UART、SPI、I2C、定时器，也包括时钟、DMA、中断、PinMux、电源域、复位域和启动介质。
- 理解 MCU BSP 与嵌入式 Linux Board Support Package 在职责边界上的差异。
- 理解静态资源分配、动态资源注册、设备树描述和编译期配置的适用场景。

### 掌握

- 掌握 BSP 分层目录设计和依赖方向。
- 掌握 GPIO、UART、SPI、I2C、DMA、Timer 等资源的统一描述方法。
- 掌握资源申请、释放、冲突检测和生命周期管理。
- 掌握 PinMux、时钟门控、NVIC、中断向量和 DMA 通道的配置关系。
- 掌握板级初始化顺序和错误回滚策略。

### 精通

- 能够定位资源冲突、初始化时序错误、引脚复用错误、时钟配置错误和中断异常等现场问题。
- 能够设计适用于多硬件版本、多板卡和产品量产的 BSP 架构。
- 能够建立可测试、可追踪、可配置的板级资源管理框架。
- 能够量化 BSP 初始化时间、静态内存、运行时开销和中断延迟。

### 能够设计

- 能够设计一套工业级 MCU BSP。
- 能够设计板级资源清单、资源冲突检测机制和初始化拓扑。
- 能够设计统一的板级设备注册接口。
- 能够设计支持多个硬件版本、编译期裁剪和运行时探测的 BSP 方案。
- 能够将 BSP 与 RTOS、驱动框架、Bootloader、生产测试和远程升级体系协同起来。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、结构体、枚举、位操作和 `const`、`volatile`。
- 熟悉 MCU 存储器映射、寄存器访问和中断机制。
- 理解 GPIO、UART、SPI、I2C、ADC、PWM、DMA 的基本工作原理。
- 了解 Cortex-M 启动流程、向量表、SysTick、NVIC 和异常模型。
- 了解 RTOS 任务、队列、互斥锁和临界区。
- 了解基本的硬件原理图、芯片数据手册和勘误文档。

### 技能要求

- 能够使用逻辑分析仪、示波器和 JTAG/SWD 调试器。
- 能够阅读芯片参考手册和板卡原理图。
- 能够编写基本的底层驱动。
- 能够使用 Git、CMake/Make、编译器 map 文件和静态分析工具。
- 能够通过寄存器、波形和日志定位硬件初始化问题。

---

## 3. 技术概述

### 3.1 BSP 的定义

BSP，即 Board Support Package，板级支持包，是连接**具体硬件板卡**与**上层软件系统**的软件适配层。

典型依赖方向如下：

```
应用层
  ↓
业务服务 / Middleware
  ↓
设备抽象接口
  ↓
芯片驱动 / HAL
  ↓
BSP 板级配置与资源管理
  ↓
MCU 外设寄存器 / SoC 硬件
```

BSP 的核心任务不是简单“初始化外设”，而是完成：

1. **硬件资源描述**
2. **引脚复用配置**
3. **时钟和电源域配置**
4. **中断和 DMA 资源绑定**
5. **板级设备初始化**
6. **板卡差异隔离**
7. **资源冲突检测**
8. **启动阶段故障处理**
9. **硬件版本兼容**
10. **生产测试和诊断支持**

### 3.2 BSP、HAL、驱动和设备树的边界

|层次|主要职责|典型内容|是否依赖具体板卡|
|---|---|---|---|
|应用层|业务逻辑|电机控制、数据采集|尽量不依赖|
|设备服务层|设备抽象|`sensor_read()`、`storage_write()`|少量依赖|
|驱动层|控制某类设备|UART 驱动、SPI NOR 驱动|依赖 MCU/SoC|
|HAL|屏蔽寄存器细节|RCC、GPIO、DMA API|依赖芯片系列|
|BSP|描述具体板卡|LED、按键、引脚、设备连接|强依赖板卡|
|启动代码|建立执行环境|向量表、堆栈、时钟入口|依赖芯片和链接脚本|
|设备树/配置层|描述硬件拓扑|DTS、Kconfig、Board Config|面向板卡|

**核心边界：**

- HAL 关注“芯片有这个外设”。
- BSP 关注“这块板上哪个外设连接了什么器件”。
- 驱动关注“如何控制某类设备”。
- 应用关注“如何使用设备完成业务”。

### 3.3 BSP 的主流实现分支

#### 分支一：静态宏配置型

```
#define BOARD_LED_PORT       GPIOB
#define BOARD_LED_PIN        5U
#define BOARD_UART_INSTANCE  USART1
```

特点：

- 运行时开销最低。
- 代码路径简单。
- 适合资源固定、产品单一的 MCU。
- 可维护性依赖配置规范。

#### 分支二：结构化资源表型

```
static const board_gpio_t g_led = {
    .port = GPIOB,
    .pin = 5U,
    .active_level = 0U,
};
```

特点：

- 描述清晰。
- 易于统一管理。
- 支持多个硬件版本。
- 需要注意结构体和间接访问带来的代码体积。

#### 分支三：注册表型

```
board_device_register(&g_uart1_device);
board_device_register(&g_flash_device);
```

特点：

- 适合 RTOS 和通用设备框架。
- 支持设备枚举和统一生命周期。
- 需要处理名称冲突、注册顺序和资源释放。

#### 分支四：设备树/声明式配置型

```
&usart1 {
    pinctrl-0 = <&usart1_pins>;
    status = "okay";
};
```

特点：

- 板级描述与驱动代码分离。
- 适合复杂 SoC、Linux、支持多板卡平台。
- 对 MCU 小型项目可能显得过重。

---

## 4. 核心特性横向对比

### 4.1 板级资源管理方案对比

|维度|宏配置|静态资源表|运行时注册表|设备树|
|---|---|---|---|---|
|运行时开销|最低|低|中|中|
|RAM 占用|几乎无|低|中|由解析方式决定|
|类型安全|较低|高|高|依赖绑定层|
|多板卡支持|一般|较好|好|最好|
|资源冲突检测|编译期有限|可增强|运行时可检测|编译/启动阶段|
|调试复杂度|低|低|中|高|
|适合 MCU 小项目|很适合|很适合|适合|视规模而定|
|适合 SoC/Linux|一般|一般|适合|最适合|
|动态设备支持|弱|弱|强|中|
|启动确定性|最好|好|中|中|

### 4.2 资源生命周期管理对比

|模式|资源申请|资源释放|适用场景|风险|
|---|---|---|---|---|
|全部静态占用|编译期|无|固定板卡、裸机|资源利用率低|
|初始化时独占|启动时|关机或卸载时|RTOS 设备|初始化顺序依赖|
|引用计数|首次使用|最后释放|可共享时钟、GPIO|引用计数错误|
|所有权转移|注册时|所有者负责|DMA、中断、外设|所有权不清晰|
|资源租约|运行时申请|超时或主动释放|可热插拔、共享总线|实时性和复杂度较高|

### 4.3 初始化方式对比

|方式|初始化时机|优点|缺点|
|---|---|---|---|
|启动前全部初始化|`main()` 前后|系统状态确定|启动时间长，故障影响全局|
|分阶段初始化|时钟、基础、设备、服务|故障隔离较好|依赖关系需明确|
|按需初始化|第一次访问时|节省启动时间和功耗|首次访问延迟、并发复杂|
|设备注册后初始化|统一框架调度|扩展性好|需要依赖排序|
|运行时探测|读取 ID、EEPROM、GPIO|支持硬件变体|启动路径复杂、异常更多|

---

## 5. 底层原理与功能特性深度解析

## 5.1 BSP 的初始化分层

推荐将 BSP 初始化拆分为以下阶段：

```
Reset_Handler
  ↓
低级启动初始化
  - 设置 MSP
  - 初始化 .data/.bss
  - 设置向量表
  ↓
时钟与电源基础初始化
  - 电源电压等级
  - Flash Wait State
  - HSE/HSI/PLL
  - 总线分频
  ↓
基础硬件初始化
  - GPIO 默认安全态
  - PinMux
  - SysTick/定时器
  - MPU/Cache（如适用）
  ↓
资源管理器初始化
  - 资源表加载
  - 冲突检查
  - 设备所有权建立
  ↓
外设驱动初始化
  - UART/SPI/I2C/DMA
  - 存储器
  - 传感器
  ↓
RTOS 与服务启动
```

### 5.1.1 为什么初始化顺序重要

例如系统时钟切换到高频 PLL：

1. 必须先设置 Flash 等待周期。
2. 再启动 PLL。
3. 等待 PLL Lock。
4. 切换系统时钟源。
5. 更新 `SystemCoreClock`。
6. 最后初始化依赖时钟的 UART、Timer 和 RTOS Tick。

错误顺序可能导致：

- Flash 取指异常。
- UART 波特率错误。
- RTOS Tick 频率错误。
- 延时函数失效。
- 外设时序完全偏移。

### 5.2 统一资源描述

下面给出一个适用于 MCU BSP 的资源描述框架。

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    BSP_RES_GPIO = 0,
    BSP_RES_UART,
    BSP_RES_SPI,
    BSP_RES_I2C,
    BSP_RES_DMA,
    BSP_RES_TIMER,
    BSP_RES_COUNT
} bsp_resource_type_t;

typedef enum {
    BSP_RES_FREE = 0,
    BSP_RES_RESERVED,
    BSP_RES_INITIALIZED,
    BSP_RES_ERROR
} bsp_resource_state_t;

typedef struct {
    bsp_resource_type_t type;
    uint16_t id;
    uint16_t owner;
    bsp_resource_state_t state;
    uint32_t flags;
} bsp_resource_t;

typedef enum {
    BSP_OK = 0,
    BSP_ERR_INVALID_ARG = -1,
    BSP_ERR_BUSY = -2,
    BSP_ERR_NOT_FOUND = -3,
    BSP_ERR_CONFLICT = -4,
    BSP_ERR_HW = -5,
} bsp_status_t;
```

这里的 `owner` 不建议使用字符串。工业系统中应优先使用：

- 编译期生成的数字 ID；
- 设备枚举值；
- 唯一资源句柄。

原因是字符串比较会增加代码体积、启动时间和 RAM 占用，同时容易出现拼写错误。

### 5.3 资源申请与所有权

```
#define BSP_OWNER_UART1       1U
#define BSP_OWNER_CONSOLE     2U
#define BSP_OWNER_SENSOR      3U

static bsp_resource_t g_resources[] = {
    {
        .type = BSP_RES_UART,
        .id = 1U,
        .owner = 0U,
        .state = BSP_RES_FREE,
        .flags = 0U,
    },
    {
        .type = BSP_RES_SPI,
        .id = 1U,
        .owner = 0U,
        .state = BSP_RES_FREE,
        .flags = 0U,
    },
};

static bsp_resource_t *resource_find(bsp_resource_type_t type,
                                     uint16_t id)
{
    for (uint32_t i = 0U;
         i < sizeof(g_resources) / sizeof(g_resources[0]);
         ++i) {
        if ((g_resources[i].type == type) &&
            (g_resources[i].id == id)) {
            return &g_resources[i];
        }
    }

    return NULL;
}

bsp_status_t bsp_resource_acquire(bsp_resource_type_t type,
                                  uint16_t id,
                                  uint16_t owner)
{
    if (owner == 0U) {
        return BSP_ERR_INVALID_ARG;
    }

    bsp_resource_t *res = resource_find(type, id);
    if (res == NULL) {
        return BSP_ERR_NOT_FOUND;
    }

    if ((res->state != BSP_RES_FREE) &&
        (res->owner != owner)) {
        return BSP_ERR_CONFLICT;
    }

    res->owner = owner;
    res->state = BSP_RES_RESERVED;
    return BSP_OK;
}

bsp_status_t bsp_resource_release(bsp_resource_type_t type,
                                  uint16_t id,
                                  uint16_t owner)
{
    bsp_resource_t *res = resource_find(type, id);
    if (res == NULL) {
        return BSP_ERR_NOT_FOUND;
    }

    if ((res->owner != owner) ||
        (res->state == BSP_RES_FREE)) {
        return BSP_ERR_CONFLICT;
    }

    res->owner = 0U;
    res->state = BSP_RES_FREE;
    return BSP_OK;
}
```

### 工程注意事项

该示例为单线程版本。若资源管理器被多个 RTOS 任务调用，必须增加：

- 互斥锁；
- 中断上下文限制；
- 申请超时；
- 所有权转移规则；
- 失败回滚；
- 资源状态审计日志。

不要在中断上下文中执行可能阻塞的资源申请操作。

---

## 5.4 GPIO 与 PinMux 的底层关系

GPIO 配置通常至少包含：

1. GPIO 时钟门控。
2. 引脚模式配置。
3. 上拉/下拉配置。
4. 输出速度配置。
5. 输出类型配置。
6. 复用功能选择。
7. 初始输出电平。

对于一个复用为 UART TX 的引脚，常见配置顺序为：

```
开启 GPIO 时钟
  ↓
设置安全输出电平
  ↓
设置复用模式
  ↓
设置输出类型、速度、上下拉
  ↓
设置 Alternate Function
  ↓
开启 UART 外设
```

### GPIO 资源描述

```
typedef enum {
    BSP_GPIO_INPUT = 0,
    BSP_GPIO_OUTPUT_PP,
    BSP_GPIO_OUTPUT_OD,
    BSP_GPIO_AF_PP,
    BSP_GPIO_ANALOG
} bsp_gpio_mode_t;

typedef struct {
    void *port;
    uint16_t pin;
    bsp_gpio_mode_t mode;
    uint8_t pull;
    uint8_t speed;
    uint8_t alternate;
    uint8_t initial_level;
    uint8_t active_level;
} bsp_gpio_cfg_t;
```

### 安全初始化示例

```
bsp_status_t bsp_gpio_init(const bsp_gpio_cfg_t *cfg)
{
    if ((cfg == NULL) || (cfg->port == NULL) || (cfg->pin == 0U)) {
        return BSP_ERR_INVALID_ARG;
    }

    /*
     * 1. 开启 GPIO 时钟
     * 2. 先设置安全电平，避免继电器、MOS、制动器误动作
     */
    gpio_clock_enable(cfg->port);

    if (cfg->mode == BSP_GPIO_OUTPUT_PP ||
        cfg->mode == BSP_GPIO_OUTPUT_OD) {
        gpio_write(cfg->port, cfg->pin, cfg->initial_level);
    }

    gpio_configure(cfg->port,
                   cfg->pin,
                   cfg->mode,
                   cfg->pull,
                   cfg->speed,
                   cfg->alternate);

    return BSP_OK;
}
```

**工业级关键点：**

- 功率控制、继电器、制动器、点火等输出必须先进入安全态，再切换复用功能。
- 不能假设复位默认态满足系统安全要求。
- 多功能引脚切换时，必须避免短暂错误电平。
- 模拟输入应关闭数字输入缓冲，以降低漏电和噪声。
- 高速信号不应盲目配置最高 GPIO 速度，否则会增加 EMI。

---

## 5.5 时钟资源管理

时钟是典型的共享资源。多个外设可能依赖同一个总线时钟：

```
APB1 Clock
 ├── USART2
 ├── I2C1
 └── TIM3
```

如果某个设备关闭总线时钟，可能破坏其他设备。

### 引用计数式时钟管理

```
typedef struct {
    uint32_t ref_count;
    bool enabled;
} bsp_clock_gate_t;

static bsp_clock_gate_t g_apb1_clock;

bsp_status_t bsp_clock_acquire_apb1(void)
{
    uint32_t irq_state = irq_save();

    if (g_apb1_clock.ref_count == 0U) {
        rcc_apb1_clock_enable();
        g_apb1_clock.enabled = true;
    }

    if (g_apb1_clock.ref_count == UINT32_MAX) {
        irq_restore(irq_state);
        return BSP_ERR_HW;
    }

    g_apb1_clock.ref_count++;
    irq_restore(irq_state);
    return BSP_OK;
}

bsp_status_t bsp_clock_release_apb1(void)
{
    uint32_t irq_state = irq_save();

    if (g_apb1_clock.ref_count == 0U) {
        irq_restore(irq_state);
        return BSP_ERR_CONFLICT;
    }

    g_apb1_clock.ref_count--;

    if (g_apb1_clock.ref_count == 0U) {
        rcc_apb1_clock_disable();
        g_apb1_clock.enabled = false;
    }

    irq_restore(irq_state);
    return BSP_OK;
}
```

### 重要限制

引用计数只能解决“多个使用者共享时钟”的问题，不能替代：

- 外设访问互斥；
- DMA 通道所有权；
- 中断向量绑定；
- 外设状态机管理。

---

## 5.6 DMA 与中断资源绑定

DMA 资源通常包含：

- DMA 控制器；
- Stream/Channel；
- 请求源；
- 中断线；
- 优先级；
- 缓存一致性属性；
- 内存地址对齐和缓冲区生命周期。

推荐将 DMA 资源作为完整对象管理，而不是仅传递一个通道号。

```
typedef struct {
    uint8_t controller;
    uint8_t stream;
    uint8_t channel;
    uint8_t irq;
    uint8_t priority;
    uint32_t direction;
    bool cache_coherent;
} bsp_dma_resource_t;

typedef struct {
    uint32_t *buffer;
    uint32_t length;
    bsp_dma_resource_t dma;
} bsp_dma_transfer_t;
```

### DMA 启动前检查

```
bsp_status_t bsp_dma_start(const bsp_dma_transfer_t *transfer)
{
    if ((transfer == NULL) ||
        (transfer->buffer == NULL) ||
        (transfer->length == 0U)) {
        return BSP_ERR_INVALID_ARG;
    }

    if ((transfer->length % 4U) != 0U) {
        return BSP_ERR_INVALID_ARG;
    }

    if (transfer->dma.cache_coherent) {
        dcache_clean_by_addr(transfer->buffer,
                             transfer->length * sizeof(uint32_t));
    }

    dma_clear_all_flags(transfer->dma.controller,
                        transfer->dma.stream);

    dma_configure(&transfer->dma,
                  transfer->buffer,
                  transfer->length);

    dma_enable_irq(transfer->dma.controller,
                   transfer->dma.stream);

    dma_start(transfer->dma.controller,
              transfer->dma.stream);

    return BSP_OK;
}
```

在带 D-Cache 的 Cortex-M7、Cortex-A 等平台，DMA 缓冲区必须处理：

- Cache Clean：内存到外设前。
- Cache Invalidate：外设到内存后。
- 地址对齐。
- 缓冲区不能在 DMA 完成前被释放或复用。

---

## 5.7 设备注册与初始化拓扑

建议将设备初始化从“源文件排列顺序”升级为“显式依赖图”。

```
typedef struct {
    const char *name;
    int (*init)(void);
    int (*deinit)(void);
    const char * const *dependencies;
    uint8_t dependency_count;
    bool initialized;
} bsp_device_t;
```

例如：

```
clock
  ↓
gpio
  ↓
dma
  ↓
uart1
  ↓
console
  ↓
shell
```

### 初始化框架示例

```
static int device_dependency_ready(const bsp_device_t *dev)
{
    for (uint32_t i = 0U; i < dev->dependency_count; ++i) {
        const bsp_device_t *dep =
            bsp_find_device(dev->dependencies[i]);

        if ((dep == NULL) || !dep->initialized) {
            return 0;
        }
    }

    return 1;
}

int bsp_devices_init(void)
{
    uint32_t initialized_count = 0U;
    const uint32_t total = bsp_device_count();

    while (initialized_count < total) {
        bool progress = false;

        for (uint32_t i = 0U; i < total; ++i) {
            bsp_device_t *dev = bsp_device_at(i);

            if (dev->initialized) {
                continue;
            }

            if (!device_dependency_ready(dev)) {
                continue;
            }

            int ret = dev->init();
            if (ret != 0) {
                bsp_log_error("init %s failed: %d", dev->name, ret);
                return ret;
            }

            dev->initialized = true;
            initialized_count++;
            progress = true;
        }

        if (!progress) {
            /*
             * 没有设备可以继续初始化，通常意味着存在循环依赖
             * 或缺失依赖。
             */
            return -100;
        }
    }

    return 0;
}
```

该方法适合中大型工程。对资源受限 MCU，可以在编译期生成拓扑，避免运行时字符串和遍历开销。

---

## 6. 性能量化分析

以下数据以**STM32H743，480 MHz Cortex-M7，GCC -O2，TCM 关闭，L1 D-Cache 开启**为示例。实际结果会受到编译器、链接位置、总线状态和调试配置影响，工程中应通过 DWT、GPIO 翻转和 map 文件复测。

### 6.1 初始化时间示例

|操作|典型耗时|
|---|---|
|GPIO 单组配置|0.8~1.5 μs|
|UART 外设初始化|3~8 μs|
|SPI 初始化|2~5 μs|
|I2C 初始化|2~5 μs|
|DMA 配置|1~3 μs|
|PLL 启动与锁定|100~800 μs|
|外部 NOR Flash 初始化|1~10 ms|
|I2C 传感器上电和 ID 检查|2~50 ms|

**结论：**

- BSP 软件配置本身通常不是启动瓶颈。
- 外部器件上电、复位、校准和总线探测通常占据主要时间。
- 应区分“硬件配置耗时”和“设备自检耗时”。

### 6.2 资源表内存开销

假设资源描述结构体：

```
typedef struct {
    uint8_t type;
    uint8_t id;
    uint16_t owner;
    uint8_t state;
    uint8_t reserved[3];
    uint32_t flags;
} resource_entry_t;
```

按 12 字节计算：

```
总 RAM = 资源数量 × 单项大小
       = 64 × 12
       = 768 Bytes
```

若改为纯静态宏配置，运行时资源状态表可降为 0~几十字节，但失去：

- 运行时冲突检测；
- 资源状态查询；
- 统一调试能力；
- 动态设备支持。

### 6.3 资源查找复杂度

线性查找：

```
T_linear = O(N)
```

当资源数量为 32，单次比较约 10~30 ns，完整查找可能为：

```
32 × 20 ns ≈ 640 ns
```

如果在 100 kHz 高频路径中反复查找：

```
100000 × 640 ns = 64 ms/s
```

相当于占用约 6.4% 的单核时间。

因此：

- 初始化阶段可以接受线性查找；
- 实时数据路径应缓存资源指针或使用数组索引；
- 大型系统可使用哈希表或编译期 ID 映射；
- 中断路径禁止做复杂资源查询。

### 6.4 中断延迟影响

资源管理器若在临界区中执行 N 项线性遍历：

```
临界区时间 ≈ N × 单项访问时间 + 锁操作时间
```

假设：

- N = 64；
- 单项访问 20 ns；
- 锁和状态更新 500 ns；

则：

```
临界区 ≈ 64 × 20 ns + 500 ns
       ≈ 1.78 μs
```

在 10 μs 硬实时截止时间中，这已经达到约 17.8% 的预算。

**优化方式：**

- 资源表按类型分组；
- 使用编译期资源 ID 直接索引；
- 禁止中断上下文申请资源；
- 缩短锁保护范围；
- 使用原子状态字替代大临界区；
- 将设备初始化迁移到启动阶段。

### 6.5 启动时间预算

建议建立启动时间预算：

```
T_boot =
T_reset
+ T_clock
+ T_gpio
+ T_dma
+ T_driver
+ T_device_probe
+ T_rtos
+ T_application_ready
```

例如：

|项目|预算|
|---|---|
|复位到 C 环境|1 ms|
|时钟初始化|0.5 ms|
|GPIO/PinMux|0.1 ms|
|基础外设|1 ms|
|外部 Flash|5 ms|
|传感器探测|20 ms|
|RTOS 启动|1 ms|
|总计|28.6 ms|

如果产品要求 10 ms 内进入安全控制状态，应将传感器探测、文件系统和网络初始化延迟到后台任务，并优先完成：

```
复位 → 安全 GPIO → 看门狗 → 控制定时器 → 安全状态
```

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否只有一块固定硬件板？
├─ 是
│  ├─ 项目规模小于 50 个设备/资源？
│  │  ├─ 是 → 编译期宏配置 + 静态初始化
│  │  └─ 否 → 静态资源表 + 冲突检查
│  └─ 是否需要运行时切换硬件版本？
│     ├─ 是 → 结构化资源表 + 版本探测
│     └─ 否 → 编译期 Board Config
│
└─ 否
   ├─ 是否基于 Linux/复杂 SoC？
   │  ├─ 是 → 设备树 + 驱动模型 + Board Config
   │  └─ 否 → 多 Board BSP + 统一设备接口
   └─ 是否需要设备热插拔或动态加载？
      ├─ 是 → 注册表 + 引用计数 + 生命周期管理
      └─ 否 → 静态设备注册 + 初始化拓扑
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|单一工业控制板|静态资源表|确定性高，调试简单|
|同一产品 A/B 两个 PCB 版本|多 Board Config|隔离引脚和设备差异|
|MCU + RTOS 通用平台|设备注册表|便于任务、驱动和服务集成|
|Linux 计算平台|设备树|硬件描述与驱动解耦|
|低功耗传感器节点|按需初始化 + 时钟引用计数|减少功耗|
|多外设共享 SPI|总线对象 + 片选资源表|统一互斥和时序|
|多 DMA 外设|DMA 资源矩阵 + 编译期检查|避免 DMA 冲突|
|安全控制输出|安全默认态 + 分阶段初始化|防止上电误动作|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：板级差异集中管理

不要把引脚号散落在业务代码中。

错误：

```
gpio_write(GPIOB, 5, 0);
```

推荐：

```
board_led_set(false);
```

或者：

```
gpio_write(board_led.port,
           board_led.pin,
           board_led.active_level);
```

### 原则二：单向依赖

推荐依赖方向：

```
board_config → bsp_resource → driver → service → application
```

禁止：

```
BSP → application
driver → 某个具体业务任务
HAL → BSP
```

### 原则三：资源必须有唯一所有者

每个以下资源都应明确所有者：

- DMA 通道；
- UART 中断；
- Timer 通道；
- GPIO 输出；
- SPI 片选；
- I2C 总线恢复控制权；
- 电源控制 GPIO。

### 原则四：初始化必须可失败

初始化函数不能默认成功：

```
int board_uart_init(void);
int board_sensor_init(void);
int board_storage_init(void);
```

必须检查：

- 时钟是否有效；
- 引脚是否成功配置；
- 外设 ID 是否匹配；
- DMA 是否可用；
- 中断是否绑定；
- 外部设备是否响应。

### 原则五：安全态优先

在板级初始化中，优先处理：

1. 急停；
2. 电机使能；
3. 制动器；
4. 功率 MOS；
5. 继电器；
6. 看门狗；
7. 故障指示灯。

### 8.2 选型决策矩阵

评分范围为 1~5，分数越高越适合。

|方案|确定性|可扩展性|多板卡|运行时管理|代码体积|
|---|---|---|---|---|---|
|宏配置|5|2|2|1|5|
|静态资源表|5|4|4|3|4|
|注册表|3|5|5|5|3|
|设备树|3|5|5|4|2|

### 8.3 工业级编码规范

- 所有资源 ID 使用枚举或生成的常量，禁止魔数。
- 所有硬件寄存器访问使用 `volatile`。
- 所有初始化接口必须返回错误码。
- 不在 BSP 中使用无限阻塞等待，必须具备超时。
- 不在中断中调用可能阻塞的设备接口。
- 不通过全局变量隐式传递资源所有权。
- 对 DMA 缓冲区明确缓存属性和生命周期。
- 设备初始化失败时必须记录资源、阶段和错误码。
- 板级配置与驱动实现分离。
- 在 CI 中执行资源冲突静态检查。
- 通过链接脚本或 MPU 将关键寄存器和启动区域设置为受保护区域。
- 对安全输出采用“默认关闭、显式使能”的设计。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：PinMux 冲突

### 错误代码

```
uart1_init(GPIOA, 9, GPIOA, 10);
spi1_init(GPIOA, 5, GPIOA, 6, GPIOA, 7);
```

表面上没有问题，但如果另一个设备又将 `PA9` 配置成定时器输出，后初始化的设备会覆盖前者。

### 根因

- 引脚配置分散在多个驱动中；
- 没有统一资源登记；
- 初始化顺序掩盖了资源冲突。

### 正确实现

```
static const board_pin_t g_board_pins[] = {
    { .port = GPIOA, .pin = 9,  .func = PIN_FUNC_UART1_TX },
    { .port = GPIOA, .pin = 10, .func = PIN_FUNC_UART1_RX },
    { .port = GPIOA, .pin = 5,  .func = PIN_FUNC_SPI1_SCK },
    { .port = GPIOA, .pin = 6,  .func = PIN_FUNC_SPI1_MISO },
    { .port = GPIOA, .pin = 7,  .func = PIN_FUNC_SPI1_MOSI },
};
```

启动阶段统一检查同一物理引脚是否被重复声明。

### 风险影响

- UART 无输出；
- SPI 数据异常；
- 设备间歇性失效；
- 现场表现为随机故障。

---

## 9.2 错误二：GPIO 初始电平错误导致执行器误动作

### 错误代码

```
gpio_config_output(RELAY_PORT, RELAY_PIN);
gpio_write(RELAY_PORT, RELAY_PIN, 1);
```

如果继电器低电平有效，则上电瞬间可能已经动作。

### 根因

- 未定义 active-low/active-high；
- 配置模式切换前没有设置安全电平；
- 依赖芯片复位默认态。

### 正确实现

```
#define RELAY_SAFE_LEVEL  1U
#define RELAY_ACTIVE_LEVEL 0U

gpio_write(RELAY_PORT, RELAY_PIN, RELAY_SAFE_LEVEL);
gpio_config_output(RELAY_PORT, RELAY_PIN);
```

### 风险影响

- 电机启动；
- 继电器误吸合；
- 高压模块误使能；
- 人身和设备安全风险。

---

## 9.3 错误三：时钟切换后波特率和 Tick 未更新

### 错误代码

```
system_clock_set_480mhz();
uart_init(115200);
rtos_start();
```

但 UART 和 Tick 仍使用旧的 `SystemCoreClock`。

### 根因

- 时钟切换只修改寄存器；
- 软件时钟变量未同步；
- 外设初始化依赖隐式全局状态。

### 正确实现

```
system_clock_set_480mhz();

SystemCoreClockUpdate();

if (uart_init(115200U) != BSP_OK) {
    system_fault_enter(FAULT_UART_INIT);
}

rtos_tick_config(SystemCoreClock, 1000U);
```

### 风险影响

- 串口乱码；
- 延时偏差；
- RTOS 调度周期错误；
- 通信超时和协议异常。

---

## 9.4 错误四：DMA 缓冲区缓存不一致

### 错误代码

```
static uint8_t rx_buffer[256];

dma_start_rx(rx_buffer, sizeof(rx_buffer));

/* DMA 完成后直接读取 */
process_packet(rx_buffer);
```

### 根因

CPU Cache 中仍保留旧数据，DMA 写入的内存内容未反映到 CPU 读取路径。

### 正确实现

```
dma_wait_complete();

dcache_invalidate_by_addr(rx_buffer, sizeof(rx_buffer));

process_packet(rx_buffer);
```

发送方向则通常需要：

```
dcache_clean_by_addr(tx_buffer, tx_length);
dma_start_tx(tx_buffer, tx_length);
```

### 风险影响

- 收到旧数据；
- 协议包校验随机失败；
- 高负载下问题加重；
- 难以通过低优化级别复现。

---

## 9.5 错误五：初始化失败后继续运行

### 错误代码

```
board_flash_init();
board_sensor_init();
app_start();
```

### 根因

- 忽略返回值；
- 没有定义降级策略；
- BSP 与应用没有故障状态接口。

### 正确实现

```
if (board_flash_init() != BSP_OK) {
    fault_report(FAULT_FLASH);
    system_enter_degraded_mode();
}

if (board_sensor_init() != BSP_OK) {
    fault_report(FAULT_SENSOR);
    sensor_mark_unavailable();
}

app_start();
```

### 风险影响

- 运行时空指针；
- 数据写入错误介质；
- 传感器数据被当作有效值；
- 故障延迟暴露。

---

## 9.6 错误六：资源释放不完整

### 错误代码

```
spi_init();
dma_init();
gpio_init();
```

设备卸载时只执行：

```
spi_deinit();
```

### 根因

- 没有生命周期模型；
- DMA、中断、GPIO、时钟和设备状态之间缺少回滚关系。

### 正确实现

```
int sensor_deinit(void)
{
    dma_stop(SENSOR_DMA);
    dma_irq_disable(SENSOR_DMA);
    spi_irq_disable(SENSOR_SPI);
    spi_deinit(SENSOR_SPI);
    gpio_set_safe_state(SENSOR_CS_PORT, SENSOR_CS_PIN);
    bsp_clock_release_apb1();
    return 0;
}
```

### 风险影响

- 下次初始化失败；
- 中断打到已释放对象；
- 功耗异常；
- 资源泄漏。

---

## 10. 多机制组合使用方案

## 10.1 推荐架构

```
Board Config
  ├── Pin 定义
  ├── Clock 定义
  ├── DMA 定义
  ├── IRQ 定义
  └── Device 定义
        ↓
Resource Manager
  ├── 冲突检查
  ├── 所有权管理
  ├── 生命周期
  └── 诊断信息
        ↓
BSP Device Registry
  ├── uart_console
  ├── spi_flash
  ├── i2c_sensor
  └── pwm_motor
        ↓
Driver Framework
        ↓
RTOS Services / Application
```

## 10.2 组合设计模式

推荐使用：

- **静态资源描述 + 运行时状态管理**
- **设备注册表 + 显式依赖**
- **资源所有权 + 引用计数**
- **初始化事务 + 失败回滚**
- **编译期配置 + 运行时硬件探测**
- **统一错误码 + 分层日志**
- **安全默认态 + 状态机使能**

### 完整代码框架

```
typedef struct {
    int (*clock_init)(void);
    int (*gpio_init)(void);
    int (*dma_init)(void);
    int (*device_init)(void);
    int (*device_deinit)(void);
} board_ops_t;

typedef struct {
    bool clock_ready;
    bool gpio_ready;
    bool dma_ready;
    bool device_ready;
} board_state_t;

static board_state_t g_board_state;

int board_init(const board_ops_t *ops)
{
    int ret;

    if (ops == NULL) {
        return BSP_ERR_INVALID_ARG;
    }

    ret = ops->clock_init();
    if (ret != BSP_OK) {
        goto fail;
    }
    g_board_state.clock_ready = true;

    ret = ops->gpio_init();
    if (ret != BSP_OK) {
        goto fail;
    }
    g_board_state.gpio_ready = true;

    ret = ops->dma_init();
    if (ret != BSP_OK) {
        goto fail;
    }
    g_board_state.dma_ready = true;

    ret = ops->device_init();
    if (ret != BSP_OK) {
        goto fail;
    }
    g_board_state.device_ready = true;

    return BSP_OK;

fail:
    /*
     * 反向回滚，避免系统处于未知的半初始化状态
     */
    if (g_board_state.device_ready && ops->device_deinit != NULL) {
        (void)ops->device_deinit();
        g_board_state.device_ready = false;
    }

    if (g_board_state.dma_ready) {
        dma_global_deinit();
        g_board_state.dma_ready = false;
    }

    if (g_board_state.gpio_ready) {
        gpio_global_safe_state();
        g_board_state.gpio_ready = false;
    }

    if (g_board_state.clock_ready) {
        clock_enter_safe_source();
        g_board_state.clock_ready = false;
    }

    return ret;
}
```

---

## 11. 工业级实际案例分析

## 11.1 案例一：电机控制器 BSP

### 需求

- 3 相 PWM 输出；
- 编码器输入；
- 电流 ADC 采样；
- 急停输入；
- 母线过压和过流保护；
- 控制环周期 20 kHz；
- 上电不得误使能功率级。

### 架构

```
Reset
  ↓
安全 GPIO 配置
  ↓
急停输入启用
  ↓
PWM 输出保持关闭
  ↓
ADC + DMA 初始化
  ↓
定时器触发 ADC
  ↓
控制任务启动
  ↓
经过自检后允许功率使能
```

### 关键代码

```
int motor_board_init(void)
{
    if (gpio_init_output(MOTOR_EN_PORT,
                          MOTOR_EN_PIN,
                          MOTOR_EN_SAFE_LEVEL) != 0) {
        return -1;
    }

    if (gpio_init_input(ESTOP_PORT,
                        ESTOP_PIN,
                        GPIO_PULLUP) != 0) {
        return -2;
    }

    if (pwm_init_disabled(PWM_TIMER) != 0) {
        return -3;
    }

    if (adc_dma_init(&g_adc_dma_cfg) != 0) {
        return -4;
    }

    if (!gpio_read(ESTOP_PORT, ESTOP_PIN)) {
        motor_fault_set(MOTOR_FAULT_ESTOP);
        return -5;
    }

    return 0;
}

int motor_power_enable(void)
{
    if (motor_fault_active()) {
        return -1;
    }

    if (!adc_values_valid()) {
        return -2;
    }

    pwm_enable_outputs(PWM_TIMER);
    gpio_write(MOTOR_EN_PORT, MOTOR_EN_PIN, MOTOR_EN_ACTIVE_LEVEL);
    return 0;
}
```

### 设计要点

- PWM 定时器初始化后必须保持输出关闭。
- ADC 触发源、PWM 定时器和 DMA 通道必须形成固定资源绑定。
- 急停输入不能仅由应用任务轮询，应连接硬件刹车输入或高优先级中断。
- 功率使能应由状态机控制，而不是普通 GPIO API 直接控制。
- 20 kHz 控制周期为 50 μs，BSP 不能在控制环路径中执行资源查找、日志打印或动态内存申请。

---

## 11.2 案例二：工业数据采集网关

### 需求

- 4 路 RS-485；
- 2 路以太网；
- SD 卡；
- RTC；
- 看门狗；
- 支持两种 PCB 版本；
- 支持现场诊断和生产测试。

### 架构

```
Board Variant Detect
  ↓
加载 Board A / Board B 配置
  ↓
资源冲突检查
  ↓
时钟与电源
  ↓
网络 PHY 复位和 MDIO
  ↓
UART + RS-485 DE GPIO
  ↓
SDMMC + DMA
  ↓
诊断 Shell
```

### 多硬件版本描述

```
typedef enum {
    BOARD_REV_A = 0,
    BOARD_REV_B
} board_revision_t;

typedef struct {
    void *rs485_uart[4];
    void *rs485_de_port[4];
    uint16_t rs485_de_pin[4];
    void *eth_phy_reset_port;
    uint16_t eth_phy_reset_pin;
} board_variant_cfg_t;

static board_variant_cfg_t g_board_cfg;

int board_detect_revision(board_revision_t *revision)
{
    if (revision == NULL) {
        return -1;
    }

    uint32_t id = eeprom_read_board_id();

    switch (id) {
    case 0xA001U:
        *revision = BOARD_REV_A;
        return 0;
    case 0xB001U:
        *revision = BOARD_REV_B;
        return 0;
    default:
        return -2;
    }
}
```

### 设计要点

- 板卡版本探测必须有默认安全策略。
- 不能让驱动直接判断 PCB 版本。
- 版本差异应收敛到 `board_variant_cfg_t`。
- 生产测试接口应能够输出：
    - 板卡版本；
    - 资源占用表；
    - 时钟频率；
    - PHY ID；
    - UART 回环结果；
    - SD 卡识别结果；
    - 看门狗状态。

---

## 11.3 案例三：低功耗无线传感器节点

### 需求

- 电池供电；
- 睡眠电流小于 10 μA；
- SPI Flash；
- I2C 传感器；
- RTC 唤醒；
- 传感器按需上电；
- 采样完成后自动进入 Stop/Standby。

### 资源策略

```
启动
  ↓
仅初始化 RTC、唤醒 GPIO、看门狗
  ↓
RTC 到期
  ↓
开启传感器电源
  ↓
初始化 I2C
  ↓
采样
  ↓
写入 Flash
  ↓
关闭 I2C 时钟、传感器电源、SPI
  ↓
进入低功耗模式
```

### 设计要点

- 外设时钟采用引用计数或按阶段开启。
- GPIO 在睡眠前切换到模拟态或高阻态。
- SPI Flash 的 CS 必须保持明确电平，避免误进入命令状态。
- 进入低功耗前，必须等待 DMA、Flash 编程和总线事务完成。
- 不要仅关闭 MCU 外设时钟，外部器件电源和上拉电阻也可能造成漏电。

---

## 12. 高频问题深度答疑

### 问题一：BSP 是否应该包含所有驱动？

不应该。

BSP 应包含：

- 板卡资源描述；
- 板级初始化；
- 板级设备连接关系；
- 板级电源、复位和 PinMux；
- 板级差异适配。

通用设备驱动应独立于具体板卡。例如 SPI NOR 驱动不应直接写死：

```
#define FLASH_CS_PORT GPIOB
#define FLASH_CS_PIN  12
```

而应由 BSP 提供：

```
flash_bus_t bus = {
    .spi = board_flash_spi(),
    .cs = board_flash_cs(),
};
```

这样同一驱动可以复用于不同板卡。

---

### 问题二：BSP 应该使用 HAL 还是直接操作寄存器？

取决于性能、可移植性和控制要求。

|场景|推荐|
|---|---|
|普通 GPIO、UART、I2C 初始化|HAL/LL|
|高频控制环|LL 或寄存器|
|关键时序、启动代码|寄存器或芯片底层库|
|多芯片平台|HAL 接口|
|需要规避 HAL 隐式行为|LL/寄存器|
|安全关键路径|明确、可审计的底层实现|

关键不是“是否直接寄存器”，而是：

- 是否可验证；
- 是否可维护；
- 是否清楚读改写副作用；
- 是否处理时钟、缓存、屏障和中断并发。

---

### 问题三：资源管理器是否值得引入？

当系统出现以下任一情况时，通常值得引入：

- 多个驱动共享总线；
- 多个板卡版本；
- DMA 通道较多；
- PinMux 冲突频繁；
- 需要运行时诊断；
- 设备支持按需启停；
- 需要热插拔或低功耗管理。

对于只有 3 个 GPIO、1 个 UART 的小型项目，完整注册表可能是过度设计。可以采用：

```
静态资源配置 + 编译期断言 + 统一初始化顺序
```

---

### 问题四：板级资源应该放在全局变量还是常量表中？

硬件静态配置优先放在 `const` 表中：

```
static const board_uart_cfg_t g_uart_cfg = {
    .instance = USART1,
    .baudrate = 115200U,
};
```

运行时状态单独放在 RAM：

```
static board_uart_state_t g_uart_state;
```

不要把“配置”和“状态”混在同一个可写全局结构中，否则容易出现：

- 运行时修改静态硬件定义；
- 多任务并发破坏配置；
- 调试时无法区分期望值和实际状态。

---

### 问题五：初始化失败后应该停止系统还是降级运行？

取决于设备关键等级。

|设备|失败策略|
|---|---|
|急停、看门狗、安全监控|停止并进入安全态|
|主控制定时器|禁止启动业务|
|主存储器|进入只读或降级模式|
|调试串口|可继续运行，但记录故障|
|非关键传感器|标记不可用，业务降级|
|可选网络接口|允许离线运行|

必须建立设备关键等级，而不是所有初始化失败都统一死循环。

---

### 问题六：为什么很多 BSP 最终会变成“巨型 board.c”？

常见原因：

- 所有外设初始化集中在一个文件；
- 没有资源描述层；
- 驱动和板级连接关系混合；
- 没有设备生命周期；
- 没有初始化依赖图；
- 通过复制粘贴支持硬件版本。

改进方式：

```
board_config/
  ├── board_pins.c
  ├── board_clocks.c
  ├── board_dma.c
  ├── board_devices.c
  └── board_variant.c

bsp/
  ├── bsp_resource.c
  ├── bsp_power.c
  ├── bsp_reset.c
  └── bsp_diagnostic.c
```

---

## 13. 课程核心总结

### 核心要点

1. **BSP 的本质是板卡硬件拓扑和资源的组织层，不是简单的初始化代码集合。**
2. **HAL 解决芯片抽象，BSP 解决板卡差异，驱动解决设备控制。**
3. **PinMux、GPIO、时钟、DMA、中断和电源必须统一纳入资源管理。**
4. **每个硬件资源都必须有清晰的所有权、生命周期和错误处理策略。**
5. **安全输出必须先进入安全态，再完成复用和外设使能。**
6. **初始化顺序应由显式依赖关系决定，而不是依赖源文件排列。**
7. **DMA 系统必须处理缓存一致性、对齐和缓冲区生命周期。**
8. **多板卡产品应将版本差异集中在 Board Config 层。**
9. **实时路径禁止执行资源查找、动态分配和阻塞式 BSP 操作。**
10. **BSP 必须支持生产测试、现场诊断和故障追踪。**

### 性能排序

在运行时开销方面通常为：

```
编译期宏配置
  >
静态资源索引
  >
静态结构体表
  >
数组线性查找
  >
运行时注册表
  >
字符串查找 / 动态反射式框架
```

在可扩展性方面通常为：

```
设备树 / 声明式配置
  >
注册表 + 依赖图
  >
结构化资源表
  >
宏配置
```

### 通用选型结论

- **固定 MCU、固定板卡、强实时：静态资源表 + 编译期检查。**
- **多硬件版本：Board Variant + 统一设备接口。**
- **RTOS 通用设备框架：注册表 + 生命周期管理。**
- **Linux/复杂 SoC：设备树 + 驱动模型。**
- **安全控制：安全默认态 + 分阶段初始化 + 故障锁定。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐实现|
|---|---|
|单板固定资源|静态配置|
|多 PCB 版本|Board Variant|
|多任务共享外设|所有权 + 互斥|
|多设备共享时钟|引用计数|
|DMA 外设|DMA 资源对象|
|低功耗系统|按需初始化 + 资源关闭|
|高频控制路径|编译期绑定 + 缓存句柄|
|Linux SoC|设备树|
|安全输出|安全态初始化|
|生产诊断|资源状态表 + 自检接口|

### 14.2 资源管理检查表

|检查项|是否必须|
|---|---|
|GPIO 是否定义初始安全电平|是|
|PinMux 是否全局无冲突|是|
|DMA 是否有唯一所有者|是|
|中断优先级是否经过预算|是|
|时钟切换后是否更新软件变量|是|
|DMA Cache 是否处理|视平台，但必须明确|
|初始化是否检查返回值|是|
|失败是否回滚|中大型项目必须|
|设备是否有生命周期状态|推荐|
|是否能输出资源诊断信息|工业项目推荐|

---

## 15. 学习效果自检

完成本课后，应能够回答以下问题：

### 架构能力

- 能否画出应用、驱动、HAL、BSP 和硬件之间的依赖关系？
- 能否明确哪些代码属于 BSP，哪些代码属于设备驱动？
- 能否为两个 PCB 版本设计统一资源接口？

### 资源管理能力

- 能否建立 GPIO、DMA、IRQ、Timer 和 Clock 资源表？
- 能否检测两个设备使用同一个引脚或 DMA 通道？
- 能否设计资源所有权和释放机制？
- 能否区分共享资源和独占资源？

### 初始化能力

- 能否设计具有显式依赖的初始化顺序？
- 能否为每一个初始化阶段定义失败策略？
- 能否实现失败回滚？
- 能否保证功率输出上电不误动作？

### 性能能力

- 能否计算资源查找的时间复杂度？
- 能否使用 DWT 或 GPIO 翻转测量 BSP 初始化耗时？
- 能否分析临界区对实时性的影响？
- 能否判断某个资源管理操作是否允许出现在中断路径？

### 调试能力

- 能否通过波形判断 PinMux 或波特率配置错误？
- 能否通过寄存器检查时钟是否真正开启？
- 能否定位 DMA 缓存一致性问题？
- 能否通过资源状态表定位设备冲突？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：静态板级配置

实现以下内容：

- LED；
- 按键；
- UART；
- SPI；
- I2C；
- 独立 Board Config 文件。

要求：

- 应用层不得出现具体端口号；
- 所有初始化接口返回错误码；
- 增加 GPIO 安全态配置。

### 任务二：资源冲突检测器

实现编译期或启动期检查：

- GPIO 重复使用；
- DMA 通道重复使用；
- IRQ 重复绑定；
- Timer 通道冲突；
- 外设时钟依赖缺失。

输出示例：

```
BSP RESOURCE ERROR:
  type: GPIO
  resource: PA9
  owner_a: UART1_TX
  owner_b: TIMER1_CH2
```

### 任务三：设备注册与依赖管理

实现：

- 设备注册；
- 设备查找；
- 依赖排序；
- 初始化；
- 反向销毁；
- 循环依赖检测；
- 初始化耗时统计。

### 任务四：多板卡 BSP

支持：

```
BOARD_REV_A
BOARD_REV_B
BOARD_REV_C
```

要求：

- 驱动代码不感知 PCB 版本；
- 仅 Board Config 不同；
- 通过 EEPROM、GPIO Strap 或 OTP 识别版本；
- 未知版本进入安全模式。

### 任务五：DMA 与 Cache 验证

设计 DMA 收发测试：

- 无 Cache；
- 开启 Cache 但不维护；
- Clean/Invalidate；
- 非对齐地址；
- 不同缓冲区长度；
- 高负载并发访问。

记录：

- 数据错误率；
- 传输耗时；
- CPU 占用；
- Cache 维护耗时。

### 任务六：工业级 BSP 诊断框架

提供 Shell 命令：

```
bsp info
bsp clock
bsp resource
bsp gpio
bsp dma
bsp selftest
bsp fault
```

要求能够输出：

- 板卡版本；
- CPU 和总线频率；
- 已占用资源；
- DMA 状态；
- 外设初始化状态；
- 最近一次故障码；
- 启动阶段耗时。

## 16.2 性能测试方法

### 中断延迟

通过外部信号触发中断，并在 ISR 入口翻转 GPIO：

```
void EXTI0_IRQHandler(void)
{
    /*
     * 尽量将测试 GPIO 翻转放在 ISR 的第一条可控指令处。
     * 测试版本可直接操作 BSRR，避免 HAL 调用引入额外开销。
     */
    DEBUG_GPIO->BSRR = DEBUG_PIN;

    if ((EXTI->PR1 & EXTI_PR1_PIF0) != 0U) {
        EXTI->PR1 = EXTI_PR1_PIF0;
    }

    DEBUG_GPIO->BSRR = (uint32_t)DEBUG_PIN << 16U;
}
```

测试连接：

```
信号发生器
   ├── 通道 1：连接 MCU 外部中断输入
   └── 示波器 CH1：监测中断输入

MCU 调试 GPIO
   └── 示波器 CH2：监测 ISR 入口翻转
```

定义：

```
T_irq_latency =
T_isr_gpio_edge - T_external_trigger_edge
```

测量结果包含：

```
外部输入同步延迟
+ EXTI 边沿检测延迟
+ NVIC 仲裁延迟
+ 当前指令完成时间
+ Cortex-M 异常入栈时间
+ Flash/Cache/总线等待时间
+ ISR 入口指令执行时间
+ GPIO 写入传播时间
```

以 Cortex-M4 为例，在零等待、无更高优先级中断、无总线竞争的理想条件下，异常响应的核心开销通常约为 **12 个时钟周期**。实际工业系统中还需要考虑：

- Flash Wait State；
- 指令 Cache 命中率；
- FPU 上下文保存；
- 中断嵌套；
- RTOS 临界区；
- `BASEPRI` 或 `PRIMASK` 屏蔽；
- DMA 与 CPU 总线竞争；
- 尾链优化；
- ISR 包装函数额外开销。

禁止只测量一次。至少应统计：

- 最小值；
- 最大值；
- 平均值；
- P99；
- P99.9；
- 超出截止时间的次数。

例如：

|指标|测量结果|
|---|---|
|最小中断延迟|0.19 μs|
|平均中断延迟|0.31 μs|
|P99|0.68 μs|
|最大中断延迟|2.74 μs|
|测试样本|1,000,000|
|超过 3 μs|0 次|

**实时系统重点关注最大值和尾部延迟，而不是平均值。**

### DWT 周期计数器初始化

Cortex-M3/M4/M7 常可使用 DWT 周期计数器：

```
#include <stdint.h>
#include "core_cm7.h"

static int cycle_counter_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

#if defined(DWT_LAR)
    DWT->LAR = 0xC5ACCE55UL;
#endif

    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    return ((DWT->CTRL & DWT_CTRL_CYCCNTENA_Msk) != 0U) ? 0 : -1;
}

static inline uint32_t cycle_counter_get(void)
{
    return DWT->CYCCNT;
}

static uint32_t cycles_to_ns(uint32_t cycles, uint32_t core_hz)
{
    if (core_hz == 0U) {
        return UINT32_MAX;
    }

    /*
     * 先除后乘会损失精度，使用 64 位中间值避免溢出。
     */
    return (uint32_t)(((uint64_t)cycles * 1000000000ULL) /
                      (uint64_t)core_hz);
}
```

测量 BSP 接口：

```
typedef struct {
    uint32_t min_cycles;
    uint32_t max_cycles;
    uint64_t total_cycles;
    uint32_t samples;
} benchmark_result_t;

static void benchmark_update(benchmark_result_t *result,
                             uint32_t elapsed_cycles)
{
    if ((result == NULL) || (elapsed_cycles == 0U)) {
        return;
    }

    if ((result->samples == 0U) ||
        (elapsed_cycles < result->min_cycles)) {
        result->min_cycles = elapsed_cycles;
    }

    if (elapsed_cycles > result->max_cycles) {
        result->max_cycles = elapsed_cycles;
    }

    result->total_cycles += elapsed_cycles;
    result->samples++;
}
```

```
benchmark_result_t result = {0};

for (uint32_t i = 0U; i < 100000U; ++i) {
    uint32_t start = cycle_counter_get();

    board_gpio_set(BOARD_GPIO_STATUS_LED, true);
    board_gpio_set(BOARD_GPIO_STATUS_LED, false);

    uint32_t elapsed = cycle_counter_get() - start;
    benchmark_update(&result, elapsed);
}
```

平均周期数：

```
C_avg = total_cycles / samples
```

执行时间：

```
T_ns = C_avg × 10^9 / F_core
```

DWT 的 32 位计数器会溢出，但无符号减法在单次测量跨度小于一个完整计数周期时仍然有效：

```
elapsed = end - start;
```

在 480 MHz 下，一个完整周期约为：

```
2^32 / 480,000,000 ≈ 8.95 s
```

因此单段测量必须短于约 8.95 秒，或者使用软件扩展为 64 位计数器。

### GPIO 操作延迟

对比不同抽象层的执行开销：

```
/* 方案一：直接寄存器 */
GPIOB->BSRR = GPIO_PIN_5;

/* 方案二：LL */
LL_GPIO_SetOutputPin(GPIOB, LL_GPIO_PIN_5);

/* 方案三：HAL */
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);

/* 方案四：BSP 资源查询 */
board_gpio_set(BOARD_GPIO_STATUS_LED, true);
```

示例平台：STM32H743，480 MHz，GCC 12，`-O2`，代码和数据命中 Cache。示例结果如下：

|调用方式|典型周期|典型时间|
|---|---|---|
|直接写 `BSRR`|2~6 cycles|4~13 ns|
|LL 内联接口|2~8 cycles|4~17 ns|
|HAL 接口|15~40 cycles|31~83 ns|
|BSP 数组索引|20~55 cycles|42~115 ns|
|BSP 字符串查找|100~500+ cycles|0.21~1.04+ μs|

这些数值不能直接当作目标芯片的结论，必须在目标构建配置下重新测量。测量时应固定：

- 编译器版本；
- 优化等级；
- LTO 设置；
- Flash Wait State；
- I-Cache/D-Cache 状态；
- 代码所在存储区；
- 中断屏蔽策略；
- GPIO 所在总线频率。

若 `board_gpio_set()` 被用于 MHz 级软件翻转，抽象开销可能不可接受。推荐提供初始化时解析、运行时直达寄存器的快速句柄：

```
typedef struct {
    volatile uint32_t *set_reg;
    volatile uint32_t *clear_reg;
    uint32_t mask;
} bsp_gpio_fast_handle_t;

static inline void bsp_gpio_fast_set(
    const bsp_gpio_fast_handle_t *handle)
{
    *handle->set_reg = handle->mask;
}

static inline void bsp_gpio_fast_clear(
    const bsp_gpio_fast_handle_t *handle)
{
    *handle->clear_reg = handle->mask;
}
```

该设计保留 BSP 的板级解耦，同时避免在实时路径中重复查表。

### 初始化阶段耗时追踪

为每个 BSP 初始化阶段建立固定编号，避免依赖字符串日志：

```
typedef enum {
    BSP_STAGE_CLOCK = 0,
    BSP_STAGE_SAFE_GPIO,
    BSP_STAGE_PINMUX,
    BSP_STAGE_DMA,
    BSP_STAGE_CONSOLE,
    BSP_STAGE_STORAGE,
    BSP_STAGE_SENSORS,
    BSP_STAGE_NETWORK,
    BSP_STAGE_COUNT
} bsp_init_stage_t;

typedef struct {
    uint32_t start_cycles;
    uint32_t elapsed_cycles;
    int32_t result;
} bsp_stage_profile_t;

static bsp_stage_profile_t g_stage_profile[BSP_STAGE_COUNT];

static void bsp_profile_begin(bsp_init_stage_t stage)
{
    if (stage < BSP_STAGE_COUNT) {
        g_stage_profile[stage].start_cycles = DWT->CYCCNT;
    }
}

static void bsp_profile_end(bsp_init_stage_t stage, int32_t result)
{
    if (stage < BSP_STAGE_COUNT) {
        g_stage_profile[stage].elapsed_cycles =
            DWT->CYCCNT - g_stage_profile[stage].start_cycles;
        g_stage_profile[stage].result = result;
    }
}
```

使用示例：

```
int board_devices_init(void)
{
    int ret;

    bsp_profile_begin(BSP_STAGE_STORAGE);
    ret = board_storage_init();
    bsp_profile_end(BSP_STAGE_STORAGE, ret);

    if (ret != BSP_OK) {
        return ret;
    }

    bsp_profile_begin(BSP_STAGE_SENSORS);
    ret = board_sensors_init();
    bsp_profile_end(BSP_STAGE_SENSORS, ret);

    return ret;
}
```

注意事项：

- 初始化阶段不要同步打印每条测量结果，否则串口日志会改变被测时序。
- 先将结果写入 RAM，初始化完成后统一输出。
- 若启动阶段可能复位，应将关键结果保存到备份 SRAM 或保留 RAM。
- 测量外部器件启动时间时，应同时使用示波器验证，避免周期计数器尚未启动或时钟频率中途变化。

### DMA 吞吐率

DMA 有效吞吐率计算公式：

```
Throughput = Payload Bytes / Transfer Time
```

总线利用率：

```
Bus Utilization =
Measured Throughput / Theoretical Bus Bandwidth × 100%
```

SPI 理论有效载荷上限：

```
SPI_theoretical = F_spi / 8
```

例如 SPI 时钟为 40 MHz：

```
40,000,000 / 8 = 5,000,000 Byte/s
               ≈ 4.77 MiB/s
```

若实测传输 4096 字节耗时 930 μs：

```
Throughput =
4096 / 930 μs
≈ 4.40 MB/s

Utilization =
4.40 / 5.00 × 100%
≈ 88%
```

测试代码：

```
typedef struct {
    uint32_t transfer_cycles;
    uint32_t bytes;
    int status;
} dma_benchmark_t;

int benchmark_spi_dma(const uint8_t *buffer,
                      uint32_t length,
                      dma_benchmark_t *result)
{
    if ((buffer == NULL) || (length == 0U) || (result == NULL)) {
        return BSP_ERR_INVALID_ARG;
    }

    dcache_clean_by_addr((void *)buffer, length);

    uint32_t start = DWT->CYCCNT;

    int ret = spi_dma_transmit(buffer, length, 100U);
    if (ret != BSP_OK) {
        result->status = ret;
        return ret;
    }

    result->transfer_cycles = DWT->CYCCNT - start;
    result->bytes = length;
    result->status = BSP_OK;

    return BSP_OK;
}
```

必须区分：

- DMA 配置时间；
- 首字节启动延迟；
- 总线传输时间；
- DMA 完成中断延迟；
- Cache 维护时间；
- 驱动同步等待时间。

推荐分别测量：

```
T_total =
T_cache
+ T_dma_config
+ T_peripheral_transfer
+ T_completion_irq
+ T_wakeup
```

### CPU 占用率

对周期性 BSP 服务，可通过 DWT 统计任务执行时间：

```
CPU Usage =
Σ Task Execution Time / Observation Window × 100%
```

例如传感器服务每 1 ms 执行一次，每次占用 12 μs：

```
CPU Usage =
12 μs / 1000 μs × 100%
= 1.2%
```

对 DMA 方案，应同时比较轮询方案：

|方案|CPU 占用|传输延迟|实现复杂度|
|---|---|---|---|
|字节轮询|高|低到中|低|
|中断收发|中|中|中|
|DMA + 阻塞等待|中|中|中|
|DMA + 事件通知|低|中|较高|
|DMA 双缓冲|最低|最低且稳定|高|

注意：DMA 并不保证 CPU 占用一定最低。小数据包可能因配置 DMA、Cache 维护和任务切换产生更大开销。因此应测量 DMA 盈亏平衡点。

设：

```
T_poll(N) = N × C_byte
T_dma(N)  = C_setup + N × C_bus + C_complete
```

当：

```
T_dma(N) < T_poll(N)
```

DMA 才在 CPU 时间上有收益。

例如：

```
C_setup + C_complete = 3 μs
轮询每字节 CPU 开销 = 0.15 μs
```

忽略共同总线时间，则盈亏平衡长度约为：

```
N_break_even = 3 / 0.15 = 20 Bytes
```

小于约 20 字节时，轮询可能更有效；大于该长度时，DMA 通常更有优势。实际阈值必须在目标平台实测。

### 临界区最大持续时间

使用 GPIO 或 DWT 测量关中断时间：

```
uint32_t irq_state = irq_save();
uint32_t start = DWT->CYCCNT;

resource_table_update();

uint32_t elapsed = DWT->CYCCNT - start;
irq_restore(irq_state);

critical_time_record(elapsed);
```

这里存在一个重要测量陷阱：如果在恢复中断之后才记录结束时间，待处理中断可能先执行，使结果混入 ISR 时间；如果在恢复中断之前结束计时，则测得的是纯临界区长度。两种指标都可以测，但含义必须明确。

约束关系：

```
T_critical_max
≤ T_interrupt_deadline - T_hardware_latency - T_ISR_execution
```

例如：

```
中断截止时间             10 μs
硬件和异常入口延迟        1 μs
ISR 最坏执行时间           3 μs
允许的最大屏蔽时间         6 μs
```

则所有会屏蔽该中断的临界区最坏持续时间必须小于 **6 μs**，并保留工程裕量。建议目标控制在 3~4 μs，而不是刚好 6 μs。

### 栈使用量

BSP 初始化可能包含深层函数调用、大型局部变量和厂商 HAL 栈帧，应测量启动栈和设备任务栈的高水位。

填充法：

```
#define STACK_PATTERN 0xA5U

void stack_fill(uint8_t *stack_start, uint32_t stack_size)
{
    if ((stack_start == NULL) || (stack_size == 0U)) {
        return;
    }

    for (uint32_t i = 0U; i < stack_size; ++i) {
        stack_start[i] = STACK_PATTERN;
    }
}

uint32_t stack_unused_bytes(const uint8_t *stack_start,
                            uint32_t stack_size)
{
    uint32_t unused = 0U;

    if (stack_start == NULL) {
        return 0U;
    }

    while ((unused < stack_size) &&
           (stack_start[unused] == STACK_PATTERN)) {
        ++unused;
    }

    return unused;
}
```

栈利用率：

```
Stack Used = Stack Size - Minimum Unused Bytes

Stack Utilization =
Stack Used / Stack Size × 100%
```

建议：

- 常规任务保留至少 **25%~30%** 裕量；
- 中断嵌套复杂或启用 FPU 时保留更高裕量；
- 测试必须覆盖最深错误处理和日志路径；
- 不要只测正常启动路径；
- 开启编译器栈使用报告，如 GCC 的 `-fstack-usage`；
- 静态分析结果与运行时高水位测量结合使用。

### Flash 与 RAM 占用

通过链接器 map 文件量化 BSP：

```
BSP Flash =
.text.bsp
+ .rodata.bsp
+ 初始化表
+ 板级配置表

BSP RAM =
.data.bsp
+ .bss.bsp
+ 设备状态
+ 资源状态表
+ DMA 缓冲区
+ BSP 任务栈
```

GCC 工具链可使用：

```
arm-none-eabi-size firmware.elf
arm-none-eabi-nm --print-size --size-sort firmware.elf
arm-none-eabi-objdump -h firmware.elf
```

对比不同配置时必须确保：

- 编译器和版本相同；
- 编译参数相同；
- LTO 设置相同；
- 调试日志等级相同；
- 链接脚本相同；
- 未使用的设备驱动已通过 Section GC 移除。

推荐编译参数：

```
-ffunction-sections
-fdata-sections
-Wl,--gc-sections
```

建立 CI 预算：

|指标|基准值|最大允许增长|
|---|---|---|
|BSP Flash|48 KiB|+2 KiB|
|BSP 静态 RAM|6 KiB|+512 B|
|启动时间|25 ms|+2 ms|
|最大关中断时间|3 μs|不允许增加|
|最大 ISR 延迟|5 μs|+0.5 μs|

超过预算时，CI 应产生告警或阻止合入。

### 功耗测量

低功耗 BSP 必须测量：

- Reset 后功耗；
- 初始化阶段峰值；
- Idle；
- Sleep；
- Stop；
- Standby；
- 外设工作态；
- 唤醒瞬态；
- 外部器件断电后的漏电。

平均电流：

```
I_avg =
Σ(I_state × T_state) / T_observation
```

例如：

```
采样工作：8 mA × 20 ms
无线发送：25 mA × 10 ms
睡眠：8 μA × 970 ms
周期：1000 ms
```

计算：

```
I_avg =
(8 mA × 20 ms
+ 25 mA × 10 ms
+ 0.008 mA × 970 ms) / 1000 ms

≈ 0.418 mA
```

理论电池寿命：

```
Battery Life =
Usable Capacity / Average Current
```

若可用容量为 2000 mAh：

```
2000 mAh / 0.418 mA ≈ 4785 h ≈ 199 天
```

实际设计还必须考虑：

- 电池自放电；
- 温度；
- 峰值电流能力；
- DC/DC 效率；
- 电池有效容量折减；
- 无线重传；
- 器件老化；
- 低电压截止阈值。

---

## 16.3 建议的性能测试矩阵

不要只测试“默认配置”。工业 BSP 至少应覆盖以下组合：

|测试维度|测试组合|
|---|---|
|编译优化|`-O0`、`-Og`、`-O2`、LTO|
|Cache|I-Cache/D-Cache 开启与关闭|
|存储位置|Flash、ITCM、SRAM|
|系统负载|空闲、DMA 高负载、中断风暴|
|RTOS 状态|调度器关闭、正常负载、最高负载|
|电源模式|Run、Sleep、Stop 唤醒|
|外设状态|单设备、共享总线、多设备并发|
|错误注入|超时、NACK、DMA 错误、时钟失锁|
|PCB 版本|所有受支持硬件版本|
|温度与电压|常温、低温、高温、最低/最高电压|

建议的测试轮次：

```
基准测试
  ↓
单资源压力测试
  ↓
资源并发测试
  ↓
最坏中断负载测试
  ↓
错误注入测试
  ↓
低电压与温度边界测试
  ↓
24~72 小时稳定性测试
```

---

## 16.4 自动化验收指标

可在 CI、HIL 或生产测试系统中建立以下硬门限：

```
[启动]
复位到安全输出建立：       ≤ 500 μs
复位到控制任务就绪：       ≤ 10 ms
全部非关键设备完成初始化： ≤ 100 ms

[实时性]
最高优先级中断最大延迟：   ≤ 3 μs
最大关中断时间：           ≤ 2 μs
20 kHz 控制任务最大抖动：  ≤ 1 μs

[资源]
PinMux 冲突：              0
DMA 通道冲突：             0
未释放资源：               0
未知所有者资源：           0

[内存]
主栈最小剩余：             ≥ 30%
任务栈最小剩余：           ≥ 25%
BSP 静态 RAM：             ≤ 目标预算
动态内存泄漏：             0

[可靠性]
设备超时可恢复率：         100%
重复初始化/反初始化：      10,000 次无失败
睡眠/唤醒循环：            100,000 次无失败
看门狗复位后安全态：       100%
```

测试阈值必须来自系统需求和最坏情况分析，不能直接照搬上述示例。

---

## 16.5 进阶学习方向

### 方向一：编译期资源生成

使用 YAML、JSON、Kconfig 或设备树作为硬件描述源，在构建阶段生成：

- PinMux 配置；
- DMA 分配表；
- 中断配置；
- 时钟树；
- 设备实例；
- 资源冲突报告；
- 板级文档。

推荐流程：

```
board.yaml
   ↓ Schema 校验
资源分配与冲突检测
   ↓
生成 board_config.c/.h
   ↓
编译期 static_assert
   ↓
固件构建
```

核心要求是使用结构化解析器和 Schema 校验，不应通过不可靠的文本替换脚本处理硬件描述。

### 方向二：静态断言与链接期校验

通过 `_Static_assert` 验证：

```
_Static_assert(BOARD_UART_COUNT <= MCU_UART_COUNT,
               "UART resource count exceeds hardware limit");

_Static_assert((DMA_BUFFER_SIZE % CACHE_LINE_SIZE) == 0U,
               "DMA buffer size must align to cache line");
```

对于跨源文件唯一性，可通过生成器或链接符号制造重复定义，使资源冲突在链接阶段直接失败。

### 方向三：设备生命周期状态机

建立严格状态模型：

```
UNREGISTERED
    ↓ register
REGISTERED
    ↓ acquire resources
RESERVED
    ↓ initialize hardware
INITIALIZED
    ↓ start
RUNNING
    ↓ stop
INITIALIZED
    ↓ deinitialize
REGISTERED
    ↓ unregister
UNREGISTERED

任意状态
    ↓ hardware failure
ERROR
```

每个状态只允许有限操作，避免半初始化设备被上层访问。

### 方向四：故障注入

建议注入：

- 外部晶振不起振；
- PLL 锁定超时；
- I2C 永久 Busy；
- SPI 设备无响应；
- DMA 传输错误；
- EEPROM 板卡 ID 损坏；
- 传感器 ID 不匹配；
- Cache 维护遗漏；
- 中断永远不触发；
- 外设初始化中途复位。

目标不是验证“正常情况下能工作”，而是验证系统能否：

1. 检测故障；
2. 限定影响范围；
3. 释放或回滚资源；
4. 进入安全状态；
5. 保留可诊断信息；
6. 在策略允许时自动恢复。

### 方向五：安全与功能安全 BSP

进一步学习：

- 启动阶段 RAM、Flash、CPU 自检；
- 时钟监控和时钟失效切换；
- 双通道输入一致性；
- 寄存器配置回读；
- 外设访问保护；
- MPU 区域划分；
- 看门狗窗口设计；
- 安全输出回读；
- ISO 26262、IEC 61508、IEC 60730 对底层软件的要求；
- 故障反应时间与诊断覆盖率分析。

### 方向六：Linux BSP

从 MCU BSP 进一步扩展到：

- Boot ROM、SPL、U-Boot；
- Linux Device Tree；
- PinCtrl、Clock、Reset、Regulator 子系统；
- Platform Driver；
- DMA Engine；
- Runtime PM；
- IOMMU 与缓存一致性；
- RootFS 和 A/B 升级；
- Kernel 配置与补丁维护；
- 驱动上游化和长期版本管理。

---

## 16.6 本课最终实践交付物

完成 BSP 与板级资源管理实践后，建议形成以下工程资产：

```
bsp/
├── include/
│   ├── bsp_board.h
│   ├── bsp_resource.h
│   ├── bsp_device.h
│   ├── bsp_clock.h
│   ├── bsp_power.h
│   └── bsp_diagnostic.h
├── board/
│   ├── board_config.c
│   ├── board_pins.c
│   ├── board_clocks.c
│   ├── board_dma.c
│   ├── board_devices.c
│   └── board_variant.c
├── core/
│   ├── bsp_resource.c
│   ├── bsp_device.c
│   ├── bsp_init.c
│   ├── bsp_fault.c
│   └── bsp_profile.c
├── generated/
│   ├── board_resource_ids.h
│   ├── board_resource_table.c
│   └── board_conflict_report.txt
└── tests/
    ├── test_resource_conflict.c
    ├── test_init_rollback.c
    ├── test_device_lifecycle.c
    ├── test_board_variant.c
    └── test_bsp_performance.c
```

验收时至少提交：

- 板级资源清单；
- PinMux 冲突报告；
- DMA 和中断分配表；
- 初始化依赖图；
- 启动时序报告；
- Flash/RAM 占用报告；
- 最大中断延迟和最大临界区报告；
- 低功耗状态电流报告；
- 错误注入结果；
- 多硬件版本兼容性测试结果；
- 生产自检接口说明；
- BSP 维护和版本升级规范。

**最终能力标准不是“能够把板子点亮”，而是能够建立一套资源无冲突、初始化有顺序、失败可回滚、性能可量化、故障可诊断、硬件版本可扩展的工业级 BSP。**