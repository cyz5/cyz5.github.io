

## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 Zephyr BSP、SoC、board、devicetree、Kconfig、驱动模型和应用层之间的关系。
- 理解 Zephyr 的设备模型：
    - `struct device`
    - `DEVICE_DT_DEFINE()`
    - `DEVICE_DT_INST_DEFINE()`
    - `device_is_ready()`
    - `DEVICE_API()`
- 理解 Zephyr 的初始化等级与优先级：
    - `PRE_KERNEL_1`
    - `PRE_KERNEL_2`
    - `POST_KERNEL`
    - `APPLICATION`
- 理解 devicetree 对硬件实例、寄存器资源、中断、时钟、GPIO、DMA 和总线拓扑的描述方式。
- 理解 Zephyr 驱动 API、驱动实现和设备实例之间的关系。
- 理解 Zephyr 的静态设备模型与 RTOS 启动期设备初始化机制。

### 1.2 掌握

能够：

- 创建一个完整的 Zephyr board。
- 编写或修改：
    - `board.yml`
    - `board.cmake`
    - `Kconfig.board`
    - `Kconfig.defconfig`
    - `board.dts`
    - `pinctrl.dtsi`
    - `CMakeLists.txt`
- 使用 devicetree alias、chosen、节点状态和 compatible。
- 适配 GPIO、UART、I2C、SPI、ADC、PWM、传感器和 Flash 设备。
- 编写静态设备驱动并通过 `device_is_ready()` 检查初始化状态。
- 使用 `DEVICE_DT_INST_DEFINE()` 为多个硬件实例生成驱动设备。
- 使用 `west build`、`west flash`、`west debug` 完成构建、下载和调试。

### 1.3 精通

能够定位和解决：

- devicetree 节点存在但驱动没有生成的问题。
- Kconfig 使能但设备未 ready 的问题。
- UART 中断、DMA、FIFO 和异步 API 适配问题。
- I2C 总线锁死、SDA 被拉低和从设备异常恢复问题。
- SPI CS、pinctrl、频率和 DMA 配置错误。
- 驱动初始化顺序错误。
- `CONFIG_*` 配置与 devicetree 属性不一致。
- 多实例驱动的配置结构、数据结构和资源管理问题。
- 驱动在 ISR、线程和系统启动上下文中的调用边界问题。

### 1.4 能够设计

能够设计：

- 可复用的 Zephyr 多板卡 BSP。
- 基于 devicetree 的硬件描述体系。
- 支持多个 SoC、多个板卡和多个硬件版本的驱动适配层。
- 面向量产产品的 UART DMA、I2C 总线、SPI Flash 和传感器驱动。
- 支持 Kconfig 裁剪、日志、错误恢复、设备电源管理和自动化测试的 BSP。
- 符合 Zephyr 驱动模型和上游代码风格的 out-of-tree 驱动。

---

# 2. 前置要求

## 2.1 知识要求

必须掌握：

- C 语言：
    - 结构体和函数指针
    - `const`、`volatile`、内存映射
    - 宏展开和条件编译
    - 链接段和静态对象
    - 环形缓冲区
- MCU 基础：
    - 启动文件和链接脚本
    - 中断控制器
    - 时钟、复位和电源域
    - UART、I2C、SPI、DMA 原理
    - GPIO 复用和电气属性
- RTOS 基础：
    - 线程、信号量、互斥锁、事件
    - 中断上下文限制
    - 优先级和调度
    - 内存保护和栈管理
- Zephyr 基础：
    - `west`
    - CMake
    - Kconfig
    - devicetree
    - Device Driver Model
    - logging 子系统

## 2.2 技能要求

建议具备：

- 能够阅读 SoC reference manual 和 Zephyr SoC 支持代码。
- 能够使用 `west build -t menuconfig` 和 `west build -t guiconfig`。
- 能够使用：

```
west build -b <board> <app>
west flash
west debug
west build -t dt-sources
west build -t dt-doc-validate
```

- 能够查看：

```
build/zephyr/zephyr.dts
build/zephyr/include/generated/zephyr/devicetree_generated.h
build/zephyr/.config
build/zephyr/zephyr.map
```

- 能够使用示波器和逻辑分析仪验证实际外设波形。
- 能够定位 HardFault、BusFault、UsageFault 和 DMA 错误。
- 能够编写基础的 Python 串口、协议和回归测试脚本。

---

# 3. 技术概述

## 3.1 Zephyr BSP 的定义

Zephyr 中的 board 支持包不是传统意义上单独堆积的启动文件和外设代码，而是多个层次协同构成的硬件支持体系：

```
应用层
  ↓
Zephyr subsystem / driver API
  ↓
具体设备驱动
  ↓
devicetree 硬件描述
  ↓
SoC 支持层
  ↓
芯片 HAL / LL / 寄存器
  ↓
MCU 硬件
```

典型 board 目录：

```
boards/<arch>/<board_name>/
├── board.yml
├── board.cmake
├── CMakeLists.txt
├── Kconfig.board
├── Kconfig.defconfig
├── <board_name>.dts
├── <board_name>_defconfig
├── pinctrl.dtsi
├── support/
│   ├── openocd.cfg
│   └── ...
└── doc/
    └── index.rst
```

不同 Zephyr 版本的 board 元数据文件和目录布局可能略有差异，应以目标版本 `boards/` 下的现有板卡为模板。

## 3.2 Zephyr 的核心适配机制

Zephyr 的驱动适配通常由四部分组成：

```
Kconfig
  ↓ 决定驱动是否参与编译

devicetree
  ↓ 描述硬件资源和实例参数

驱动源码
  ↓ 实现 API 和硬件操作

DEVICE_DT_DEFINE()
  ↓ 生成静态设备对象并注册到启动流程
```

一个设备要真正可用，通常必须同时满足：

```
节点 status = "okay"
+ compatible 与驱动匹配
+ 对应 CONFIG_* 已启用
+ 依赖设备已经初始化
+ 驱动初始化成功
+ device_is_ready() 返回 true
```

## 3.3 主流驱动适配方式

|方案|特点|适用场景|风险|
|---|---|---|---|
|使用 Zephyr 原生驱动|生态和维护性最好|标准 UART、I2C、SPI、GPIO|受现有功能限制|
|基于现有驱动扩展|保留框架并增加功能|同类硬件增强|需要理解原驱动内部契约|
|out-of-tree 驱动|不修改 Zephyr 主树|产品私有设备|后续版本迁移成本|
|使用厂商 HAL|开发快，硬件覆盖完整|原型和已有 HAL 资产|时延、风格和资源管理不统一|
|直接寄存器实现|控制精确|特殊硬件和强实时路径|维护和上游合并困难|
|wrapper 驱动|包装已有控制器|协议转换和资源复用|调试路径变长|

## 3.4 Zephyr 设备对象

典型设备对象：

```
struct device
{
    const char *name;
    const void *config;
    const void *api;
    void *const data;
    device_handle_t state;
};
```

具体字段可能随 Zephyr 版本变化，不能依赖内部布局。应用和驱动应使用公开 API，例如：

```
const struct device *dev =
    DEVICE_DT_GET(DT_NODELABEL(uart0));

if (!device_is_ready(dev))
{
    return -ENODEV;
}
```

## 3.5 设备注册的本质

Zephyr 不推荐运行时动态注册普通设备。大多数设备在编译期通过宏生成：

```
DEVICE_DT_DEFINE(
    node_id,
    init_fn,
    pm_device,
    data,
    config,
    POST_KERNEL,
    CONFIG_I2C_INIT_PRIORITY,
    &api);
```

该宏通常会生成：

- 静态设备对象。
- 驱动配置对象。
- 驱动运行时数据对象。
- 初始化函数登记信息。
- devicetree 依赖句柄。

因此 Zephyr 设备模型具有以下特点：

- 启动时静态初始化。
- 运行时无需设备链表查找。
- 设备句柄通常为编译期常量。
- 资源关系可以由 devicetree 静态表达。
- 对 RAM、启动时间和可预测性更友好。

---

# 4. 核心特性横向对比

## 4.1 RT-Thread 与 Zephyr BSP 机制对比

|维度|RT-Thread|Zephyr|
|---|---|---|
|硬件描述|代码、宏、部分 devicetree|devicetree 为核心|
|设备注册|常见为运行时 `rt_device_register()`|常见为编译期 `DEVICE_DT_DEFINE()`|
|设备查找|`rt_device_find("uart1")`|`DEVICE_DT_GET()` 或 `DEVICE_DT_GET_ALIAS()`|
|配置系统|Kconfig + SCons|Kconfig + CMake/west|
|设备状态|设备对象和返回值|`device_is_ready()`|
|初始化控制|自动初始化宏和等级|init level + priority|
|动态设备|支持较自然|普通设备通常静态生成|
|驱动接口|`read/write/control`|子系统专用 API|
|总线模型|设备框架和总线设备|devicetree bus + API|
|资源描述|驱动代码和板级宏|phandle、reg、interrupts、pinctrl|
|可移植性|依赖设备 API 设计|devicetree 和 binding 约束较强|
|构建追踪|SCons/Kconfig|CMake/Kconfig/devicetree|

## 4.2 Zephyr 常见驱动接口对比

|设备类型|典型 API|典型实现方式|
|---|---|---|
|GPIO|`gpio_pin_configure_dt()`|GPIO controller 驱动|
|UART|`uart_poll_in()`、`uart_irq_*()`、UART async API|poll/interrupt/DMA|
|I2C|`i2c_transfer()`、`i2c_write_dt()`|控制器总线驱动|
|SPI|`spi_transceive_dt()`|控制器 + CS 描述|
|ADC|`adc_read()`|通道配置 + 采样序列|
|PWM|`pwm_set_dt()`|周期和脉宽配置|
|Sensor|`sensor_sample_fetch()`|总线设备 + 传感器协议|
|Flash|`flash_read()`、`flash_write()`|NOR/NAND 控制器|
|Counter|`counter_start()`|定时器或计数器硬件|
|Watchdog|`wdt_install_timeout()`|独立看门狗或窗口看门狗|

## 4.3 设备资源描述方式对比

|方式|编译期检查|可移植性|运行时灵活性|推荐度|
|---|---|---|---|---|
|C 宏硬编码寄存器|低|低|中|低|
|board C 文件配置|中|中|中|中|
|devicetree 属性|高|高|低中|高|
|运行时动态探测|低中|中|高|特殊场景|
|devicetree + runtime control|高|高|中高|高|

---

# 5. 底层原理与功能特性深度解析

## 5.1 Zephyr Board、SoC 和驱动的职责边界

### Board 层负责

- 板卡型号。
- 外部晶振。
- 具体引脚连接。
- 板载 LED、按键、传感器、Flash。
- 默认 console。
- 板卡调试和下载配置。
- 板级电源和外部控制脚。

### SoC 层负责

- 芯片内核。
- 中断控制器。
- 外设基地址。
- 芯片时钟和复位。
- DMA 控制器。
- 芯片级 pinctrl 定义。
- SoC 系列通用外设实例。

### 驱动层负责

- 某类控制器的硬件操作。
- 对外提供 Zephyr 标准 API。
- 根据 devicetree 配置初始化实例。
- 处理中断、DMA、错误恢复和并发访问。

错误的边界：

```
板卡驱动中直接实现传感器业务协议
```

正确的边界：

```
board.dts：
    描述传感器挂在哪条 I2C 总线、地址是多少

sensor driver：
    实现传感器寄存器协议

application：
    周期读取并处理传感器数据
```

## 5.2 devicetree 工作机制

示例 `board.dts`：

```
/dts-v1/;

#include <st/stm32/stm32f407Xg.dtsi>
#include "pinctrl.dtsi"

/ {
    model = "Acme Industrial Controller";
    compatible = "acme,industrial-controller";

    chosen {
        zephyr,console = &usart1;
        zephyr,shell-uart = &usart1;
    };

    aliases {
        led0 = &status_led;
        sw0 = &user_button;
        sensor0 = &temp_sensor;
    };

    leds {
        compatible = "gpio-leds";

        status_led: led_0 {
            gpios = <&gpiod 12 GPIO_ACTIVE_HIGH>;
            label = "STATUS_LED";
        };
    };

    buttons {
        compatible = "gpio-keys";

        user_button: button_0 {
            gpios = <&gpioa 0 (GPIO_PULL_UP | GPIO_ACTIVE_LOW)>;
            label = "USER_BUTTON";
        };
    };

    sensors {
        compatible = "acme,sensors";

        temp_sensor: temperature@48 {
            compatible = "ti,tmp102";
            reg = <0x48>;
            status = "okay";
        };
    };
};

&usart1 {
    status = "okay";
    current-speed = <115200>;
    pinctrl-0 = <&usart1_tx_pa9 &usart1_rx_pa10>;
    pinctrl-names = "default";
};

&i2c1 {
    status = "okay";
    clock-frequency = <I2C_BITRATE_FAST>;
};
```

处理链路：

```
board.dts
    ↓
DTC 编译
    ↓
zephyr.dts
    ↓
devicetree_generated.h
    ↓
DT_NODELABEL / DT_ALIAS / DT_INST 宏
    ↓
驱动实例生成
```

### 编译期实例获取

```
#define LED_NODE DT_ALIAS(led0)

static const struct gpio_dt_spec led =
    GPIO_DT_SPEC_GET(LED_NODE, gpios);
```

这段代码会将：

- GPIO 控制器设备；
- GPIO 引脚编号；
- GPIO flags；

全部转换为静态初始化信息。

## 5.3 Kconfig 与 devicetree 的关系

Kconfig 决定代码是否参与编译：

```
config MY_SENSOR
    bool "My sensor driver"
    default y
    depends on I2C
    select SENSOR
```

devicetree 决定硬件实例和参数：

```
my_sensor0: sensor@30 {
    compatible = "acme,my-sensor";
    reg = <0x30>;
    status = "okay";
};
```

两者关系：

```
Kconfig：是否编译这类驱动
devicetree：系统中有哪些实例及其资源
```

错误理解：

```
打开 CONFIG_MY_SENSOR 后，设备就一定存在
```

实际上还必须满足：

```
存在 matching compatible 的 okay 节点
+ 总线设备启用
+ 依赖 Kconfig 打开
```

## 5.4 GPIO 设备适配

### 应用侧使用

```
#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>

#define LED_NODE DT_ALIAS(led0)

#if !DT_NODE_EXISTS(LED_NODE)
#error "led0 alias is required"
#endif

static const struct gpio_dt_spec led =
    GPIO_DT_SPEC_GET(LED_NODE, gpios);

int main(void)
{
    int ret;

    if (!gpio_is_ready_dt(&led))
    {
        return -ENODEV;
    }

    ret = gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE);
    if (ret != 0)
    {
        return ret;
    }

    while (1)
    {
        gpio_pin_toggle_dt(&led);
        k_sleep(K_MSEC(500));
    }

    return 0;
}
```

### GPIO 中断

```
static struct gpio_callback button_cb_data;
static struct k_work button_work;
static const struct gpio_dt_spec button =
    GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);

static void button_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    /*
     * 线程上下文中执行消抖、事件上报等操作。
     * 不在 ISR 中执行阻塞逻辑。
     */
    printk("button event\n");
}

static void button_isr(
    const struct device *port,
    struct gpio_callback *cb,
    uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);

    k_work_submit(&button_work);
}

static int button_init(void)
{
    int ret;

    if (!gpio_is_ready_dt(&button))
    {
        return -ENODEV;
    }

    ret = gpio_pin_configure_dt(
        &button,
        GPIO_INPUT);
    if (ret != 0)
    {
        return ret;
    }

    ret = gpio_pin_interrupt_configure_dt(
        &button,
        GPIO_INT_EDGE_TO_ACTIVE);
    if (ret != 0)
    {
        return ret;
    }

    gpio_init_callback(
        &button_cb_data,
        button_isr,
        BIT(button.pin));

    ret = gpio_add_callback(
        button.port,
        &button_cb_data);
    if (ret != 0)
    {
        return ret;
    }

    k_work_init(&button_work, button_work_handler);

    return 0;
}
```

### 关键问题

- 中断回调只做通知。
- 按键消抖不能简单依赖一次 GPIO 中断。
- `GPIO_ACTIVE_LOW` 必须由 devicetree 描述，应用使用 `gpio_pin_set_dt()` 时会自动处理逻辑极性。
- 不能硬编码 GPIO 控制器和引脚号。

## 5.5 UART 驱动适配

Zephyr UART 常见三种接口：

### Polling API

```
const struct device *uart =
    DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

if (!device_is_ready(uart))
{
    return -ENODEV;
}

uart_poll_out(uart, 'A');
```

特点：

- 简单。
- 阻塞。
- 适合启动日志、低速控制和早期初始化。
- 不适合大吞吐数据。

### Interrupt-driven API

```
static const struct device *uart_dev;

static void uart_isr(const struct device *dev, void *user_data)
{
    uint8_t c;

    ARG_UNUSED(user_data);

    if (!uart_irq_update(dev))
    {
        return;
    }

    if (!uart_irq_rx_ready(dev))
    {
        return;
    }

    while (uart_fifo_read(dev, &c, 1) == 1)
    {
        if (ring_buf_put(&rx_rb, &c, 1) != 1)
        {
            rx_overflow++;
        }
    }

    k_sem_give(&rx_sem);
}
```

初始化：

```
uart_irq_callback_user_data_set(
    uart_dev,
    uart_isr,
    NULL);

uart_irq_rx_enable(uart_dev);
```

### Asynchronous UART API

异步 API 常用于 DMA：

```
static uint8_t rx_buf[2][1024];

static void uart_callback(
    const struct device *dev,
    struct uart_event *evt,
    void *user_data)
{
    switch (evt->type)
    {
    case UART_RX_RDY:
        /*
         * evt->data.rx.buf:
         * evt->data.rx.offset:
         * evt->data.rx.len:
         */
        protocol_input(
            evt->data.rx.buf + evt->data.rx.offset,
            evt->data.rx.len);
        break;

    case UART_RX_BUF_REQUEST:
        uart_rx_buf_rsp(
            dev,
            rx_buf[1],
            sizeof(rx_buf[1]));
        break;

    case UART_RX_BUF_RELEASED:
        break;

    case UART_RX_DISABLED:
        uart_rx_enable(
            dev,
            rx_buf[0],
            sizeof(rx_buf[0]),
            100);
        break;

    case UART_TX_DONE:
        break;

    case UART_TX_ABORTED:
        break;

    default:
        break;
    }
}
```

实际项目中应根据 Zephyr 版本和 UART 控制器驱动支持情况选择 API。不是所有 UART 控制器都完整支持异步 DMA API。

## 5.6 I2C 设备适配

### 应用侧访问

```
#include <zephyr/drivers/i2c.h>

#define SENSOR_NODE DT_ALIAS(sensor0)

static const struct i2c_dt_spec sensor =
    I2C_DT_SPEC_GET(SENSOR_NODE);

static int sensor_read_reg(
    uint8_t reg,
    uint8_t *value)
{
    if (!i2c_is_ready_dt(&sensor))
    {
        return -ENODEV;
    }

    return i2c_reg_read_byte_dt(
        &sensor,
        reg,
        value);
}
```

### 复杂事务

```
static int sensor_read_block(
    uint8_t reg,
    uint8_t *buf,
    size_t len)
{
    uint8_t tx = reg;

    if (buf == NULL || len == 0)
    {
        return -EINVAL;
    }

    return i2c_write_read_dt(
        &sensor,
        &tx,
        sizeof(tx),
        buf,
        len);
}
```

### 总线恢复

Zephyr 是否提供具体 I2C 总线恢复接口，取决于控制器驱动和 SoC 支持。没有统一硬件恢复能力时，可在控制器驱动内部实现：

```
static int i2c_recover_bus(const struct device *dev)
{
    int ret;
    int i;

    i2c_hw_disable(dev);

    gpio_i2c_switch_to_open_drain();

    gpio_i2c_set_sda(1);
    gpio_i2c_set_scl(1);

    for (i = 0; i < 9; i++)
    {
        if (gpio_i2c_get_sda() != 0)
        {
            break;
        }

        gpio_i2c_set_scl(0);
        k_busy_wait(5);
        gpio_i2c_set_scl(1);
        k_busy_wait(5);
    }

    /* 生成 STOP 条件 */
    gpio_i2c_set_sda(0);
    k_busy_wait(2);
    gpio_i2c_set_scl(1);
    k_busy_wait(2);
    gpio_i2c_set_sda(1);

    ret = gpio_i2c_get_sda() && gpio_i2c_get_scl()
          ? 0
          : -EIO;

    i2c_hw_enable(dev);

    return ret;
}
```

注意：

- 不能在任意应用代码中直接切换总线 GPIO。
- 恢复逻辑应由 I2C 控制器驱动或专用 board recovery 层负责。
- 进行 GPIO 恢复前必须确保 I2C 外设已关闭。
- 总线恢复期间必须阻止其他线程访问该总线。

## 5.7 SPI 设备适配

### devicetree

```
&spi1 {
    status = "okay";
    pinctrl-0 = <&spi1_sck_pa5
                 &spi1_miso_pa6
                 &spi1_mosi_pa7>;
    pinctrl-names = "default";

    flash0: flash@0 {
        compatible = "jedec,spi-nor";
        reg = <0>;
        spi-max-frequency = <40000000>;
        status = "okay";
    };
};
```

### SPI 访问

```
static const struct spi_dt_spec spi_flash =
    SPI_DT_SPEC_GET(
        DT_NODELABEL(flash0),
        SPI_WORD_SET(8) | SPI_TRANSFER_MSB,
        0);

static int spi_read_id(uint8_t id[3])
{
    uint8_t command = 0x9F;
    struct spi_buf tx_buf =
    {
        .buf = &command,
        .len = 1,
    };
    struct spi_buf rx_buf =
    {
        .buf = id,
        .len = 3,
    };
    struct spi_buf_set tx =
    {
        .buffers = &tx_buf,
        .count = 1,
    };
    struct spi_buf_set rx =
    {
        .buffers = &rx_buf,
        .count = 1,
    };

    if (!spi_is_ready_dt(&spi_flash))
    {
        return -ENODEV;
    }

    return spi_transceive_dt(
        &spi_flash,
        &tx,
        &rx);
}
```

### 关键时序要求

```
配置 SPI
    ↓
拉低 CS
    ↓
发送命令
    ↓
发送地址/参数
    ↓
收发数据
    ↓
等待事务完成
    ↓
释放 CS
```

如果需要命令和数据之间保持 CS 有效，应使用一个完整的 `spi_transceive()` 事务，而不是分两次调用。

## 5.8 自定义 Zephyr 设备驱动

下面实现一个简单的自定义电压采集驱动框架。

### 公共 API

```
#ifndef ZEPHYR_INCLUDE_DRIVERS_ACME_VADC_H_
#define ZEPHYR_INCLUDE_DRIVERS_ACME_VADC_H_

#include <zephyr/device.h>
#include <stdint.h>

struct vadc_sample
{
    uint16_t raw;
    int32_t millivolts;
};

struct vadc_driver_api
{
    int (*read)(const struct device *dev,
                uint8_t channel,
                struct vadc_sample *sample);

    int (*set_channel)(const struct device *dev,
                       uint8_t channel);
};

static inline int vadc_read(
    const struct device *dev,
    uint8_t channel,
    struct vadc_sample *sample)
{
    const struct vadc_driver_api *api =
        (const struct vadc_driver_api *)dev->api;

    return api->read(dev, channel, sample);
}

#endif
```

### 驱动配置和运行时数据

```
struct vadc_config
{
    uintptr_t base;
    uint8_t channel_count;
};

struct vadc_data
{
    struct k_mutex lock;
    uint8_t current_channel;
    uint32_t sample_count;
    uint32_t error_count;
};
```

### 驱动实现

```
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(acme_vadc, CONFIG_ACME_VADC_LOG_LEVEL);

static int vadc_init(const struct device *dev)
{
    const struct vadc_config *cfg = dev->config;
    struct vadc_data *data = dev->data;

    if (cfg->base == 0 || cfg->channel_count == 0)
    {
        return -EINVAL;
    }

    k_mutex_init(&data->lock);

    /*
     * 实际项目中执行：
     * 1. 打开外设时钟
     * 2. 配置复位
     * 3. 设置采样时间
     * 4. 配置中断或 DMA
     * 5. 清除 pending 状态
     */
    data->current_channel = 0;
    data->sample_count = 0;
    data->error_count = 0;

    return 0;
}

static int vadc_read_impl(
    const struct device *dev,
    uint8_t channel,
    struct vadc_sample *sample)
{
    const struct vadc_config *cfg = dev->config;
    struct vadc_data *data = dev->data;
    int ret;

    if (sample == NULL)
    {
        return -EINVAL;
    }

    if (channel >= cfg->channel_count)
    {
        return -EINVAL;
    }

    ret = k_mutex_lock(&data->lock, K_MSEC(20));
    if (ret != 0)
    {
        return ret;
    }

    ret = vadc_hw_select_channel(cfg->base, channel);
    if (ret != 0)
    {
        data->error_count++;
        goto out;
    }

    ret = vadc_hw_start_conversion(cfg->base);
    if (ret != 0)
    {
        data->error_count++;
        goto out;
    }

    ret = vadc_hw_wait_done(
        cfg->base,
        K_MSEC(5));
    if (ret != 0)
    {
        data->error_count++;
        goto out;
    }

    sample->raw = vadc_hw_read_raw(cfg->base);
    sample->millivolts = vadc_raw_to_mv(sample->raw);
    data->sample_count++;

out:
    k_mutex_unlock(&data->lock);
    return ret;
}

static int vadc_set_channel_impl(
    const struct device *dev,
    uint8_t channel)
{
    const struct vadc_config *cfg = dev->config;
    struct vadc_data *data = dev->data;
    int ret;

    if (channel >= cfg->channel_count)
    {
        return -EINVAL;
    }

    ret = k_mutex_lock(&data->lock, K_MSEC(20));
    if (ret != 0)
    {
        return ret;
    }

    ret = vadc_hw_select_channel(cfg->base, channel);
    if (ret == 0)
    {
        data->current_channel = channel;
    }

    k_mutex_unlock(&data->lock);

    return ret;
}

static const struct vadc_driver_api vadc_api =
{
    .read = vadc_read_impl,
    .set_channel = vadc_set_channel_impl,
};
```

### devicetree binding

```
description: ACME voltage ADC

compatible: "acme,vadc"

include: base.yaml

properties:
  reg:
    required: true

  channel-count:
    type: int
    required: true
```

### 驱动实例生成

```
#define VADC_INIT(inst)                                      \
    static struct vadc_data vadc_data_##inst;               \
                                                            \
    static const struct vadc_config vadc_cfg_##inst =       \
    {                                                       \
        .base = DT_INST_REG_ADDR(inst),                     \
        .channel_count = DT_INST_PROP(inst, channel_count), \
    };                                                      \
                                                            \
    DEVICE_DT_INST_DEFINE(                                  \
        inst,                                                \
        vadc_init,                                           \
        NULL,                                                \
        &vadc_data_##inst,                                   \
        &vadc_cfg_##inst,                                    \
        POST_KERNEL,                                         \
        CONFIG_ACME_VADC_INIT_PRIORITY,                      \
        &vadc_api);

DT_INST_FOREACH_STATUS_OKAY(VADC_INIT)
```

### 对应 devicetree

```
vadc0: vadc@40012000 {
    compatible = "acme,vadc";
    reg = <0x40012000 0x400>;
    channel-count = <8>;
    status = "okay";
};
```

## 5.9 初始化等级和依赖关系

Zephyr 常见初始化顺序：

```
PRE_KERNEL_1
    ↓
PRE_KERNEL_2
    ↓
POST_KERNEL
    ↓
APPLICATION
```

典型依赖：

```
时钟/中断控制器
    ↓
GPIO/I2C/SPI/UART 控制器
    ↓
传感器、Flash、显示设备
    ↓
文件系统、网络协议栈
    ↓
应用线程
```

设备驱动应尽量通过 devicetree 依赖句柄表达依赖，而不是依赖隐式初始化顺序。

例如：

```
struct sensor_config
{
    const struct device *bus;
    uint16_t address;
};
```

初始化时：

```
if (!device_is_ready(cfg->bus))
{
    return -ENODEV;
}
```

---

# 6. 性能量化分析

以下数据为 Cortex-M4/M33，主频 120~160 MHz，Zephyr tick 为 1 kHz，开启优化编译时的典型参考值。实际结果必须在目标硬件和目标配置上测量。

## 6.1 Zephyr 设备访问开销

|操作|典型耗时|说明|
|---|---|---|
|`DEVICE_DT_GET()`|0|编译期生成地址|
|`device_is_ready()`|20~80 ns|通常为状态读取|
|GPIO 直接寄存器写|50~150 ns|取决于总线和缓存|
|`gpio_pin_set_dt()`|0.2~1.0 μs|包含 API 间接调用|
|`i2c_write_read_dt()` 软件开销|1~5 μs|不含总线传输时间|
|`spi_transceive_dt()` 软件开销|1~8 μs|不含 SPI 传输时间|
|信号量唤醒线程|2~15 μs|取决于调度和中断嵌套|
|mutex 获取|0.2~3 μs|不发生阻塞时|

相比运行时按名字查找，Zephyr 的 `DEVICE_DT_GET()` 不需要设备链表搜索：

```
RT-Thread 运行时查找：O(N)
Zephyr 编译期设备句柄：O(1)
```

## 6.2 UART 吞吐量

8N1 UART 每个字节占用 10 bit。

```
有效字节率 = 波特率 / 10
```

115200 bps：

```
115200 / 10 = 11520 Byte/s
```

921600 bps：

```
921600 / 10 = 92160 Byte/s
```

如果线程最大不可运行时间为 8 ms，安全系数为 2：

```
BufferSize ≥ 92160 × 0.008 × 2
            ≥ 1474.56 Byte
```

建议选择：

```
2048 Byte
```

如果使用 DMA，每 128 字节触发一次处理：

```
中断频率 = 92160 / 128 = 720 次/s
```

假设每次中断处理耗时 3 μs：

```
CPU 占用 = 720 × 3 μs
         = 2.16 ms/s
         = 0.216%
```

逐字节中断时：

```
CPU 占用 = 92160 × 3 μs
         = 276.48 ms/s
         = 27.65%
```

## 6.3 I2C 总线传输时间

以 400 kHz Fast-mode 为例，一次“寄存器地址 + 读取 2 字节”的事务大致包含：

```
START
7 位地址 + R/W
寄存器地址
Repeated START
7 位地址 + R/W
2 字节数据
ACK/NACK
STOP
```

实际约 40~60 bit：

```
Tbus ≈ 60 / 400000
     ≈ 150 μs
```

加上：

- 控制器状态机；
- 中断延迟；
- 线程调度；
- 总线仲裁；
- 从设备内部转换时间；

一次访问实际可能达到 **180~500 μs**。

10 ms 采样周期下，如果串行访问 4 个传感器：

```
4 × 500 μs = 2 ms
```

理论上占用采集周期 20%，还未计入数据处理和异常重试。

## 6.4 SPI 传输时间

SPI 传输时间：

```
T = bit_count / spi_frequency
```

例如 40 MHz SPI，发送 1 字节命令、3 字节地址和 256 字节数据：

```
总字节数 = 1 + 3 + 256 = 260 Byte
总 bit 数 = 260 × 8 = 2080 bit

T = 2080 / 40000000
  = 52 μs
```

实际时间还包含：

- CS 建立和释放时间；
- DMA 配置时间；
- Flash busy 轮询；
- 控制器 FIFO 空闲；
- 写入前擦除时间。

因此 NOR Flash 的真实写入时延通常由两部分构成：

```
总时延 = SPI 搬运时间 + Flash 内部编程/擦除时间
```

第二项通常远大于第一项。

## 6.5 RAM 和 Flash 开销

典型估算：

|模块|Flash|RAM|
|---|---|---|
|基础设备对象|100~300 Byte|16~64 Byte|
|GPIO 回调|0.5~2 KB|32~128 Byte|
|UART 中断驱动|2~8 KB|512~4096 Byte|
|UART DMA 驱动|4~12 KB|2~16 KB|
|I2C 控制器|3~10 KB|128~1024 Byte|
|SPI 控制器|4~12 KB|128~2048 Byte|
|日志模块|1~10 KB|256~4096 Byte|
|传感器驱动|2~8 KB|64~512 Byte|

Zephyr 驱动的静态设备对象通常不需要运行时 malloc，但线程、消息队列、DMA 缓冲区仍可能占用较多 RAM。

## 6.6 启动时间

典型启动时间：

```
复位到 kernel ready：1~10 ms
设备初始化：0.1~数十 ms
Flash 检测和擦写恢复：数十~数百 ms
网络栈初始化：数十~数百 ms
```

影响因素：

- 初始化设备数量。
- 外部晶振稳定时间。
- Flash JEDEC ID 检测。
- 传感器上电延时。
- 阻塞式驱动初始化。
- 日志输出速度。
- 文件系统挂载扫描。

启动阶段禁止无超时等待外部设备：

```
while (!device_response())
{
    /* 错误 */
}
```

应改为：

```
for (int i = 0; i < 3; i++)
{
    if (device_response() == 0)
    {
        return 0;
    }

    k_sleep(K_MSEC(2));
}

return -ETIMEDOUT;
```

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否已有 Zephyr 原生驱动？
├── 是
│   ├── 功能是否满足需求？
│   │   ├── 是 → 只配置 devicetree 和 Kconfig
│   │   └── 否 → 扩展现有驱动或增加 wrapper
│   └── 是否需要厂商特殊功能？
│       ├── 是 → 在驱动底层增加 capability/control 接口
│       └── 否 → 使用标准 Zephyr API
└── 否
    ├── 是否属于标准设备类别？
    │   ├── 是 → 实现对应 subsystem API
    │   └── 否 → 设计自定义 driver API
    ├── 是否挂在 I2C/SPI 等总线？
    │   ├── 是 → 使用 bus controller + child device
    │   └── 否 → 使用独立设备驱动
    ├── 数据吞吐是否高？
    │   ├── 是 → DMA/FIFO/异步 API
    │   └── 否 → 轮询或中断 API
    └── 是否要求量产级恢复？
        ├── 是 → 超时、重试、复位、统计、降级
        └── 否 → 原型阶段可使用简化实现
```

## 7.2 典型场景需求与方案

|典型需求|推荐方案|理由|
|---|---|---|
|系统 console|chosen 节点 + UART polling/interrupt|标准化启动和日志|
|CLI 命令行|UART interrupt + ring buffer|低延迟、无需持续 DMA|
|921600 bps 固件升级|UART async/DMA|低 CPU 占用|
|多个 I2C 传感器|I2C controller + sensor drivers|总线复用、组件兼容|
|SPI NOR Flash|`jedec,spi-nor` + flash API|可接入存储和 FCB/FAT/LittleFS|
|板载按键|`gpio-keys` 或 GPIO callback|统一输入描述|
|PWM 风扇控制|PWM API + devicetree|周期/脉宽语义清晰|
|ADC 电池采样|ADC channel spec|支持增益、参考和采样时间|
|高速采集|DMA + double buffer + k_poll|保证连续数据流|
|低功耗设备|PM device + GPIO wakeup|统一电源状态管理|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：硬件资源全部优先放入 devicetree

不推荐：

```
#define SENSOR_I2C_ADDR 0x48
#define SENSOR_INT_PIN  5
```

推荐：

```
sensor@48 {
    compatible = "acme,my-sensor";
    reg = <0x48>;
    int-gpios = <&gpioa 5 GPIO_ACTIVE_LOW>;
};
```

驱动读取：

```
#define SENSOR_NODE DT_INST(0, acme_my_sensor)

static const struct gpio_dt_spec int_gpio =
    GPIO_DT_SPEC_GET(SENSOR_NODE, int_gpios);
```

这样硬件变更时主要修改 board overlay，而不是修改驱动源码。

### 原则二：标准设备优先实现标准 API

例如：

- GPIO 使用 GPIO API。
- I2C 控制器使用 I2C API。
- SPI 控制器使用 SPI API。
- 传感器使用 Sensor API。
- Flash 使用 Flash API。
- 看门狗使用 Watchdog API。

只有标准 API 无法表达厂商能力时，才增加扩展接口。

### 原则三：区分驱动配置和运行时数据

```
struct my_config
{
    uintptr_t base;
    const struct device *bus;
    uint32_t frequency;
};

struct my_data
{
    struct k_mutex lock;
    uint32_t error_count;
    bool initialized;
};
```

原则：

```
config：只读、编译期生成、硬件固定参数
data：运行时状态、锁、计数器、缓存
```

### 原则四：所有设备句柄先检查 ready

```
const struct device *dev =
    DEVICE_DT_GET(DT_NODELABEL(i2c1));

if (!device_is_ready(dev))
{
    LOG_ERR("i2c1 is not ready");
    return -ENODEV;
}
```

不能因为 `DEVICE_DT_GET()` 返回的是非空指针，就认为硬件一定初始化成功。

### 原则五：驱动初始化不能阻塞无限时间

设备初始化遇到外部器件无响应时，应：

- 尝试有限次数。
- 返回明确错误码。
- 支持系统降级启动。
- 记录设备状态。
- 不阻塞整个系统初始化。

### 原则六：保持 ISR 短小

ISR 只负责：

```
读取硬件状态
清除中断
搬运少量数据
更新索引
提交 work
释放 semaphore
```

协议解析、日志、设备恢复和大块数据处理应在线程上下文执行。

## 8.2 Kconfig 最佳实践

示例：

```
config ACME_VADC
    bool "ACME VADC driver"
    default y
    depends on SOC_SERIES_ACME
    help
      Enable the ACME voltage ADC driver.

config ACME_VADC_INIT_PRIORITY
    int "ACME VADC initialization priority"
    default 80
    depends on ACME_VADC

config ACME_VADC_LOG_LEVEL
    int "ACME VADC log level"
    default 3
    depends on ACME_VADC
```

注意：

- 驱动不能无条件参与编译。
- 通过 `depends on` 表达硬件和子系统依赖。
- 不要滥用 `select`，否则可能产生隐藏配置依赖。
- 每个可配置行为都应有明确默认值。
- 产品配置、开发配置和测试配置分离。

## 8.3 devicetree 最佳实践

- 使用 `status = "okay"` 控制设备实例。
- 使用 `aliases` 表达板卡级逻辑角色。
- 使用 `chosen` 表达 console、shell、flash 等系统角色。
- 使用 `pinctrl` 集中描述引脚复用。
- 对自定义驱动提供 binding YAML。
- 使用 `dtc` 和 devicetree 文档验证属性。
- 不在应用中复制 devicetree 参数。

## 8.4 设备命名策略

优先使用节点引用，而不是字符串名称：

```
DEVICE_DT_GET(DT_NODELABEL(sensor0));
```

不推荐：

```
device_get_binding("SENSOR_0");
```

节点引用的优势：

- 编译期检查。
- 不需要字符串比较。
- 设备重命名影响更小。
- 能表达设备依赖关系。

## 8.5 量产级错误处理

驱动错误码应稳定且有语义：

|错误码|含义|
|---|---|
|`-EINVAL`|参数非法|
|`-ENODEV`|设备不存在或未 ready|
|`-EIO`|硬件 I/O 失败|
|`-ETIMEDOUT`|操作超时|
|`-EBUSY`|设备忙|
|`-ENOTSUP`|不支持该功能|
|`-ENOMEM`|内存不足|
|`-EAGAIN`|暂时失败，可重试|

错误日志应包含：

```
设备实例
操作类型
寄存器或事务阶段
错误码
重试次数
恢复动作
```

---

# 9. 常见错误与避坑指南

## 9.1 错误一：devicetree 节点为 `okay`，但驱动没有生成

### 错误配置

```
my_sensor: sensor@48 {
    compatible = "acme,my-sensor";
    reg = <0x48>;
    status = "okay";
};
```

但驱动没有实现或没有声明：

```
compatible = "acme,my-sensor"
```

### 根因

devicetree 节点和驱动的 `DT_DRV_COMPAT` 不匹配。

### 正确实现

驱动源码：

```
#define DT_DRV_COMPAT acme_my_sensor
```

注意 devicetree 的连字符会转换为 C 宏中的下划线：

```
"acme,my-sensor"
    ↓
acme_my_sensor
```

同时需要：

```
CONFIG_ACME_MY_SENSOR=y
```

### 风险影响

- 编译通过但没有设备实例。
- `DT_INST_FOREACH_STATUS_OKAY()` 不生成任何代码。
- 应用只能得到未定义节点或设备不可用。

## 9.2 错误二：未检查 `device_is_ready()`

### 错误代码

```
const struct device *i2c =
    DEVICE_DT_GET(DT_NODELABEL(i2c1));

i2c_write(i2c, data, len, address);
```

### 根因

设备指针存在不代表初始化成功。时钟、GPIO、DMA 或控制器初始化都可能失败。

### 正确实现

```
if (!device_is_ready(i2c))
{
    LOG_ERR("I2C controller is not ready");
    return -ENODEV;
}

return i2c_write(i2c, data, len, address);
```

### 风险影响

- 访问未初始化寄存器。
- 总线状态不确定。
- 触发断言、BusFault 或不可恢复错误。

## 9.3 错误三：把 board 硬件参数写死在驱动里

### 错误代码

```
#define SENSOR_ADDR 0x48
#define SENSOR_SCL_PIN 10
#define SENSOR_SDA_PIN 11
```

### 根因

驱动源码同时承担了板级连接关系，破坏了驱动复用和板卡隔离。

### 正确实现

`board.overlay`：

```
&i2c1 {
    status = "okay";

    sensor@48 {
        compatible = "acme,my-sensor";
        reg = <0x48>;
        status = "okay";
    };
};
```

驱动：

```
#define SENSOR_NODE DT_INST(0, acme_my_sensor)

#define SENSOR_ADDR DT_REG_ADDR(SENSOR_NODE)
```

### 风险影响

- 更换引脚或地址必须修改驱动。
- 多板卡无法复用同一驱动。
- 驱动无法进入上游。
- 运行时和文档中的硬件配置容易不一致。

## 9.4 错误四：在中断回调中执行阻塞操作

### 错误代码

```
static void gpio_isr(
    const struct device *port,
    struct gpio_callback *cb,
    uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);

    k_sleep(K_MSEC(20));
    i2c_write(sensor, data, len, address);
}
```

### 根因

GPIO ISR 在中断上下文运行，不能睡眠，也不应访问可能阻塞的总线。

### 正确实现

```
static struct k_work sensor_work;

static void gpio_isr(
    const struct device *port,
    struct gpio_callback *cb,
    uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);

    k_work_submit(&sensor_work);
}

static void sensor_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    k_sleep(K_MSEC(20));
    sensor_read_data();
}
```

### 风险影响

- 内核断言。
- 中断长期占用。
- 其他高优先级中断延迟增加。
- 系统实时性失效。

## 9.5 错误五：SPI 事务被拆开导致 CS 时序错误

### 错误代码

```
spi_write_dt(&spi, &command);
spi_write_dt(&spi, &address);
spi_read_dt(&spi, data, len);
```

### 根因

每次调用可能独立控制 CS，设备要求的完整事务被拆成多个片段。

### 正确实现

```
struct spi_buf tx_bufs[] =
{
    {
        .buf = &command,
        .len = 1,
    },
    {
        .buf = &address,
        .len = 3,
    },
};

struct spi_buf_set tx =
{
    .buffers = tx_bufs,
    .count = ARRAY_SIZE(tx_bufs),
};

struct spi_buf rx_buf =
{
    .buf = data,
    .len = len,
};

struct spi_buf_set rx =
{
    .buffers = &rx_buf,
    .count = 1,
};

return spi_transceive_dt(&spi, &tx, &rx);
```

### 风险影响

- Flash 返回错误 ID。
- 传感器寄存器读取偏移。
- LCD 命令和数据被设备错误解释。
- 低速测试正常，高速运行失败。

## 9.6 错误六：多实例驱动错误共享运行时数据

### 错误代码

```
static struct my_data data;

#define MY_INIT(inst) \
    DEVICE_DT_INST_DEFINE(inst, my_init, NULL, \
                          &data, NULL, POST_KERNEL, 80, &api);
```

### 根因

所有设备实例共用一个 `data`，导致多个硬件实例共享：

- 锁。
- 中断状态。
- 缓冲区。
- 错误计数。
- 当前配置。

### 正确实现

```
#define MY_INIT(inst)                                      \
    static struct my_data my_data_##inst;                 \
    static const struct my_config my_cfg_##inst =         \
    {                                                      \
        .base = DT_INST_REG_ADDR(inst),                   \
    };                                                     \
                                                           \
    DEVICE_DT_INST_DEFINE(                                \
        inst,                                               \
        my_init,                                            \
        NULL,                                               \
        &my_data_##inst,                                    \
        &my_cfg_##inst,                                     \
        POST_KERNEL,                                        \
        80,                                                 \
        &my_api);
```

### 风险影响

- 两个设备相互覆盖状态。
- 中断回调操作错误实例。
- 故障只在多实例板卡上出现。

---

# 10. 多机制组合使用方案

## 10.1 UART DMA + ring buffer + k_work 架构

```
UART 外设
    ↓
DMA/FIFO
    ↓
UART 中断或异步事件
    ↓
更新环形缓冲区
    ↓
提交 k_work 或释放 semaphore
    ↓
协议线程/工作队列
    ↓
帧解析和业务分发
```

### 数据结构

```
struct uart_stream_ctx
{
    const struct device *dev;

    struct ring_buf rx_rb;
    uint8_t *rx_mem;
    size_t rx_mem_size;

    struct k_sem rx_sem;
    struct k_mutex tx_lock;

    atomic_t rx_overflow;
    atomic_t frame_error;
};
```

### 接收路径框架

```
static void uart_irq_handler(
    const struct device *dev,
    void *user_data)
{
    struct uart_stream_ctx *ctx = user_data;
    uint8_t buf[32];
    int count;

    if (!uart_irq_update(dev))
    {
        return;
    }

    if (!uart_irq_rx_ready(dev))
    {
        return;
    }

    do
    {
        count = uart_fifo_read(
            dev,
            buf,
            sizeof(buf));

        if (count > 0)
        {
            uint32_t written;

            written = ring_buf_put(
                &ctx->rx_rb,
                buf,
                count);

            if (written != (uint32_t)count)
            {
                atomic_inc(&ctx->rx_overflow);
            }
        }
    } while (count > 0);

    k_sem_give(&ctx->rx_sem);
}
```

### 发送路径框架

```
static int uart_stream_send(
    struct uart_stream_ctx *ctx,
    const uint8_t *data,
    size_t len,
    k_timeout_t timeout)
{
    int ret;

    if (ctx == NULL || data == NULL || len == 0)
    {
        return -EINVAL;
    }

    ret = k_mutex_lock(&ctx->tx_lock, timeout);
    if (ret != 0)
    {
        return ret;
    }

    for (size_t i = 0; i < len; i++)
    {
        uart_poll_out(ctx->dev, data[i]);
    }

    k_mutex_unlock(&ctx->tx_lock);

    return 0;
}
```

量产版本中，发送方向应优先使用中断或 DMA，避免 `uart_poll_out()` 在高优先级线程中长时间阻塞。

## 10.2 I2C 总线 + 传感器 + work queue

```
GPIO/INT
    ↓
ISR
    ↓
k_work_submit()
    ↓
传感器工作项
    ↓
I2C 事务
    ↓
错误重试/设备恢复
    ↓
消息队列
    ↓
数据融合线程
```

### 设计原则

- GPIO ISR 不直接执行 I2C。
- 传感器驱动不直接操作业务消息队列。
- 总线锁由 I2C 控制器或上层访问模型统一管理。
- 传感器数据采样和数据融合分线程执行。
- 设备失败不应让工作队列永久阻塞。

## 10.3 SPI Flash + Flash API + FCB/LittleFS

```
SPI controller
    ↓
SPI NOR driver
    ↓
Zephyr flash API
    ↓
FCB / NVS / LittleFS
    ↓
配置、日志、升级数据
```

### 事务边界

```
读 JEDEC ID
读状态寄存器
写使能
页编程
等待 WIP 清零
扇区擦除
等待 WIP 清零
```

每个命令都必须具备：

- 命令超时。
- 状态寄存器轮询上限。
- SPI 事务失败处理。
- 写保护状态检查。
- 页边界检查。
- 掉电恢复策略。

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业网关串口升级通道

### 需求

- UART 波特率：921600 bps。
- 升级包：1~8 MB。
- 支持 CRC32 和序列号。
- Flash 写入期间不能丢串口数据。
- CPU 占用低于 10%。
- 升级失败后可回滚。

### devicetree

```
&usart1 {
    status = "okay";
    current-speed = <921600>;
    dma-names = "rx", "tx";
};
```

### 架构

```
UART DMA
    ↓
双缓冲接收
    ↓
升级协议线程
    ↓
CRC32 校验
    ↓
消息队列
    ↓
Flash 写入线程
    ↓
镜像状态管理
```

### 设计要点

- UART 接收和 Flash 写入不能共用同一个阻塞线程。
- 接收缓冲区容量应覆盖最大 Flash 操作阻塞时间。
- 升级镜像保存：
    - magic；
    - 版本；
    - 长度；
    - CRC；
    - 状态；
    - sequence。
- 使用 A/B 分区或活动镜像加备用镜像。
- 最后一步才写入“镜像有效”标志。

### 核心代码框架

```
struct upgrade_chunk
{
    uint32_t sequence;
    uint16_t length;
    uint8_t payload[1024];
    uint32_t crc32;
};

static int process_chunk(
    const struct upgrade_chunk *chunk)
{
    int ret;

    if (chunk == NULL ||
        chunk->length > sizeof(chunk->payload))
    {
        return -EINVAL;
    }

    if (crc32_check(
            chunk->payload,
            chunk->length,
            chunk->crc32) != 0)
    {
        return -EBADMSG;
    }

    ret = flash_write(
        flash_dev,
        write_offset,
        chunk->payload,
        chunk->length);
    if (ret != 0)
    {
        LOG_ERR("flash write failed: %d", ret);
        return ret;
    }

    write_offset += chunk->length;
    last_sequence = chunk->sequence;

    return 0;
}
```

### 量化指标

```
921600 bps → 92160 Byte/s
2 KB DMA/软件缓存 → 约 22 ms 原始覆盖时间
4 KB 缓存 → 约 44 ms 原始覆盖时间
```

如果 Flash 页编程或擦除可能阻塞 50 ms，则必须：

- 使用更大的缓存；
- 使用独立 DMA；
- 将 Flash 操作拆分；
- 或启用硬件流控。

## 11.2 案例二：多传感器 I2C 采集节点

### 需求

- I2C 频率：400 kHz。
- 连接 4 个传感器。
- 采样周期：10 ms。
- 单个传感器掉线不能阻塞其他传感器。
- SDA 卡低时可自动恢复。

### devicetree

```
&i2c1 {
    status = "okay";
    clock-frequency = <I2C_BITRATE_FAST>;

    temp@48 {
        compatible = "ti,tmp102";
        reg = <0x48>;
        status = "okay";
    };

    accel@1d {
        compatible = "st,lis2dh";
        reg = <0x1d>;
        irq-gpios = <&gpioa 3 GPIO_ACTIVE_HIGH>;
        status = "okay";
    };
};
```

### 架构

```
I2C controller
    ↓
标准 I2C API
    ↓
温度、加速度、压力、光照驱动
    ↓
各自采集 work
    ↓
sensor message queue
    ↓
时间戳对齐和数据融合
```

### 设计要点

- 每个传感器访问必须独立设置超时。
- 失败传感器只标记为 offline，不影响其他设备。
- 连续失败达到阈值后执行总线恢复。
- 对中断型传感器，ISR 只提交 work。
- 采集线程不能持有总线锁执行数据转换。

### 采样调度伪代码

```
static void sensor_poll_work(struct k_work *work)
{
    struct sensor_ctx *ctx =
        CONTAINER_OF(work, struct sensor_ctx, work);
    int ret;

    ret = sensor_sample_fetch(ctx->dev);
    if (ret != 0)
    {
        ctx->error_count++;

        if (ctx->error_count >= 3)
        {
            sensor_recover(ctx);
        }

        return;
    }

    ctx->error_count = 0;
    sensor_publish(ctx);
}
```

## 11.3 案例三：SPI NOR Flash 存储日志

### 需求

- SPI 频率：40 MHz。
- 使用 NOR Flash 保存事件日志。
- 日志写入不能阻塞控制线程。
- 掉电后数据可恢复。
- Flash 擦除和写入具有超时保护。

### 架构

```
控制线程
    ↓
无阻塞日志接口
    ↓
内存消息队列
    ↓
日志写入线程
    ↓
Flash API
    ↓
FCB/NVS/LittleFS
```

### 设计要点

- 控制线程只提交日志，不直接写 Flash。
- 日志项固定大小时使用内存池。
- Flash 擦除必须在低优先级线程完成。
- 每条日志增加 CRC 和序列号。
- 启动时扫描最后一个有效日志项。
- 写入提交顺序：

```
写 payload
    ↓
写 CRC
    ↓
写有效标志
```

不能先写有效标志，否则掉电时可能将不完整数据识别为有效记录。

---

# 12. 高频问题深度答疑

## 问题一：为什么 devicetree 中写了 `status = "okay"`，设备仍然不可用？

`status = "okay"` 只表示该节点在硬件描述中启用，并不保证：

- 驱动已经编译。
- `compatible` 有对应实现。
- 所有依赖 Kconfig 已开启。
- 控制器设备初始化成功。
- 引脚配置正确。
- 时钟和 DMA 资源有效。

排查顺序：

```
检查最终 zephyr.dts
    ↓
检查节点是否为 okay
    ↓
检查 compatible
    ↓
检查 .config 中 CONFIG_*
    ↓
检查设备是否生成
    ↓
检查 device_is_ready()
    ↓
检查驱动 init 返回值
    ↓
检查实际硬件波形
```

推荐检查：

```
const struct device *dev =
    DEVICE_DT_GET(DT_NODELABEL(i2c1));

if (!device_is_ready(dev))
{
    LOG_ERR("device %s is not ready", dev->name);
    return -ENODEV;
}
```

常见原因是 overlay 没有被当前 build 使用。应检查：

```
west build -t dt-sources
```

并查看：

```
build/zephyr/zephyr.dts
```

不要只看源码目录中的 `.dts` 文件。

## 问题二：为什么 Zephyr 使用 `DEVICE_DT_GET()`，还要调用 `device_is_ready()`？

`DEVICE_DT_GET()` 通常只返回编译期生成的设备对象地址：

```
const struct device *dev =
    DEVICE_DT_GET(DT_NODELABEL(uart0));
```

它解决的是：

```
如何拿到设备对象
```

而 `device_is_ready()` 解决的是：

```
设备初始化是否成功
依赖设备是否已经 ready
驱动是否报告了错误
```

因此正确模式是：

```
if (!device_is_ready(dev))
{
    return -ENODEV;
}
```

如果设备节点不存在，编译期宏可能直接报错；如果节点存在但初始化失败，通常只能在运行时通过 `device_is_ready()` 发现。

## 问题三：Zephyr 驱动为什么通常不使用运行时动态注册？

Zephyr 偏向**编译期静态设备模型**，而不是 RT-Thread 常见的运行时设备注册模型。

典型方式：

```
DEVICE_DT_INST_DEFINE(
    inst,
    my_init,
    NULL,
    &my_data_##inst,
    &my_config_##inst,
    POST_KERNEL,
    CONFIG_MY_INIT_PRIORITY,
    &my_api);
```

设备对象、配置对象、运行时数据对象和初始化入口在链接阶段生成。

#### 主要原因

##### 1. 降低运行时不确定性

静态设备对象不需要：

- 动态分配设备对象。
- 插入全局设备链表。
- 按名称搜索设备。
- 在运行时解析硬件资源。

访问路径通常是：

```
const struct device *dev =
    DEVICE_DT_GET(DT_NODELABEL(uart0));
```

设备地址在编译期确定，访问复杂度近似为：

```
O(1)
```

而基于字符串的设备搜索通常是：

```
O(N × 平均名称长度)
```

##### 2. 降低内存碎片风险

驱动对象、配置对象和设备实例通常是静态分配的：

```
Flash/ROM：
    const struct my_config

RAM：
    struct my_data

设备对象：
    静态生成
```

因此不需要在设备创建和销毁时频繁使用堆。

##### 3. 方便链接时裁剪

如果某个 devicetree 节点被关闭：

```
status = "disabled";
```

则：

```
DT_INST_FOREACH_STATUS_OKAY(MY_INIT)
```

不会生成该实例的设备对象。

这有利于减少：

- Flash 占用。
- RAM 占用。
- 初始化时间。
- 不必要的驱动代码。

##### 4. 依赖关系更明确

devicetree 可以表达：

```
传感器
  └── 依赖 I2C 控制器
        └── 依赖时钟和 GPIO
```

驱动可以在初始化时检查依赖：

```
static int sensor_init(const struct device *dev)
{
    const struct sensor_config *cfg = dev->config;

    if (!device_is_ready(cfg->bus))
    {
        return -ENODEV;
    }

    return 0;
}
```

##### 5. 更适合安全和实时系统

静态设备模型有利于：

- 启动路径审计。
- 内存布局审计。
- 资源使用量分析。
- 编译期错误发现。
- 禁止运行时未知设备注入。

#### 什么时候需要动态对象？

以下场景可能存在运行时对象：

- USB 热插拔设备。
- 动态网络接口。
- 虚拟设备。
- 多路协议通道。
- 用户态设备代理。
- 运行时创建的 socket、线程和消息队列。

但通常应该区分：

```
硬件控制器设备：
    编译期静态生成

运行时逻辑对象：
    根据业务动态创建
```

例如 USB 控制器是静态设备，某个枚举出来的 USB HID 设备上下文可以是动态对象。

#### 工程结论

不要试图把所有设备都设计成动态注册。优先采用：

```
devicetree 描述硬件
+ Kconfig 控制功能
+ DEVICE_DT_DEFINE() 生成设备
+ runtime object 管理业务状态
```

---

## 问题四：Zephyr 的 `struct device`、驱动 API、config 和 data 应该如何划分？

推荐采用四层结构：

```
struct device
    ├── config：硬件固定配置
    ├── data：运行时状态
    ├── api：设备操作接口
    └── init：启动期初始化函数
```

#### config：只读硬件配置

```
struct sensor_config
{
    const struct device *bus;
    uint16_t address;
    uint32_t max_frequency;
    struct gpio_dt_spec irq_gpio;
};
```

适合放入：

- 外设基地址。
- 中断号。
- GPIO 描述。
- I2C 地址。
- SPI 配置。
- 时钟频率。
- devicetree 固定属性。

config 通常应声明为：

```
static const struct sensor_config sensor_cfg = {
    ...
};
```

#### data：运行时状态

```
struct sensor_data
{
    struct k_mutex lock;
    uint8_t current_mode;
    uint32_t sample_count;
    uint32_t error_count;
    bool initialized;
};
```

适合放入：

- 锁。
- 信号量。
- 环形缓冲区。
- 当前工作模式。
- 错误计数。
- 运行时校准参数。
- DMA 状态。
- 上一次采样结果。

#### api：驱动操作接口

```
struct sensor_driver_api
{
    int (*sample_fetch)(const struct device *dev);
    int (*channel_get)(
        const struct device *dev,
        enum sensor_channel chan,
        struct sensor_value *val);
};
```

应用通过标准 API 或驱动公开 API 调用：

```
const struct sensor_driver_api *api = dev->api;

return api->sample_fetch(dev);
```

实际项目中不建议应用直接访问 `dev->api`，应使用封装的 inline API：

```
static inline int my_sensor_fetch(
    const struct device *dev)
{
    const struct my_sensor_api *api = dev->api;

    if (api == NULL || api->fetch == NULL)
    {
        return -ENOTSUP;
    }

    return api->fetch(dev);
}
```

#### 常见错误：把运行时状态放入 config

```
struct bad_config
{
    uint32_t error_count;
    bool active;
};
```

问题：

- 多线程修改只读配置。
- 多实例之间容易误共享。
- 破坏 ROM 配置模型。
- 可能导致总线错误。

正确方式：

```
struct good_config
{
    uintptr_t base;
};

struct good_data
{
    uint32_t error_count;
    bool active;
};
```

#### 工程判断标准

```
板卡换一块但驱动源码不变：
    属于 config

设备运行一段时间后会变化：
    属于 data

上层调用的操作集合：
    属于 api
```

---

## 问题五：为什么设备初始化优先级设置错误会导致设备不可用？

Zephyr 初始化不是简单地按照源文件编译顺序执行，而是由初始化等级和优先级共同决定。

典型顺序：

```
PRE_KERNEL_1
    ↓
PRE_KERNEL_2
    ↓
POST_KERNEL
    ↓
APPLICATION
```

同一个初始化等级中，优先级数值通常越小，越早执行。

例如：

```
DEVICE_DT_DEFINE(
    node_id,
    init_fn,
    NULL,
    data,
    config,
    POST_KERNEL,
    50,
    &api);
```

会早于：

```
DEVICE_DT_DEFINE(
    node_id,
    init_fn,
    NULL,
    data,
    config,
    POST_KERNEL,
    90,
    &api);
```

#### 错误示例

```
传感器驱动：POST_KERNEL，优先级 50
I2C 控制器：POST_KERNEL，优先级 90
```

传感器先执行：

```
if (!device_is_ready(i2c_bus))
{
    return -ENODEV;
}
```

结果传感器初始化失败。

#### 正确关系

```
I2C 控制器：POST_KERNEL，优先级 50
传感器：POST_KERNEL，优先级 80
应用：APPLICATION
```

#### 设备 ready 与初始化顺序

驱动初始化函数返回错误后，设备通常不会处于 ready 状态：

```
static int sensor_init(const struct device *dev)
{
    const struct sensor_config *cfg = dev->config;

    if (!device_is_ready(cfg->bus))
    {
        return -ENODEV;
    }

    return sensor_hw_init(dev);
}
```

因此必须分析：

1. 控制器的初始化等级。
2. 从设备的初始化等级。
3. 设备依赖是否已 ready。
4. 时钟和 pinctrl 是否已经配置。
5. 外部器件上电时间是否满足。

#### 不要过度依赖 priority

如果设备之间有复杂依赖，应优先使用：

- devicetree 依赖句柄。
- `device_is_ready()` 检查。
- 明确的 init 错误返回。
- 应用阶段显式延迟初始化。

不要通过不断修改 priority 掩盖真正的依赖问题。

---

## 问题六：Zephyr 中如何处理 UART 的轮询、中断和 DMA 模式？

三种模式应根据吞吐量、时延和资源约束选择。

#### Polling 模式

```
const struct device *uart =
    DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

if (!device_is_ready(uart))
{
    return -ENODEV;
}

uart_poll_out(uart, 'A');
```

特点：

- 实现最简单。
- 发送时可能阻塞。
- CPU 占用高。
- 适合早期启动、低速调试和极少量数据。

#### 中断模式

```
static void uart_isr(
    const struct device *dev,
    void *user_data)
{
    struct uart_ctx *ctx = user_data;
    uint8_t buf[32];
    int len;

    if (!uart_irq_update(dev))
    {
        return;
    }

    if (uart_irq_rx_ready(dev))
    {
        do
        {
            len = uart_fifo_read(
                dev,
                buf,
                sizeof(buf));

            if (len > 0)
            {
                uint32_t n;

                n = ring_buf_put(
                    &ctx->rx_rb,
                    buf,
                    len);

                if (n != (uint32_t)len)
                {
                    ctx->overflow_count++;
                }
            }
        } while (len > 0);

        k_sem_give(&ctx->rx_sem);
    }
}
```

适用：

- CLI。
- 普通控制串口。
- 中低速协议。
- 数据包大小有限的设备。

#### 异步/DMA 模式

异步 UART 事件包括：

```
UART_RX_RDY
UART_RX_BUF_REQUEST
UART_RX_BUF_RELEASED
UART_RX_DISABLED
UART_TX_DONE
UART_TX_ABORTED
```

典型初始化：

```
static int uart_async_start(
    const struct device *dev)
{
    int ret;

    ret = uart_callback_set(
        dev,
        uart_event_handler,
        NULL);
    if (ret != 0)
    {
        return ret;
    }

    return uart_rx_enable(
        dev,
        rx_buf_a,
        sizeof(rx_buf_a),
        100);
}
```

适用：

- 高速固件升级。
- 连续数据流。
- GNSS、Modbus、高速传感器。
- CPU 资源紧张的系统。

#### 选择建议

```
数据量很小？
├── 是 → polling
└── 否
    ├── 需要连续高速流？
    │   ├── 是 → DMA/异步 API
    │   └── 否 → 中断 API
    └── 是否需要严格控制帧边界？
        ├── 是 → 空闲线/异步事件/协议状态机
        └── 否 → 环形缓冲区
```

---

## 问题七：Zephyr 的 devicetree overlay 为什么有时没有生效？

#### 常见原因

1. overlay 文件没有被当前 board 使用。
2. overlay 文件名不符合构建规则。
3. 构建缓存没有清理。
4. 节点 label 或 alias 写错。
5. 后加载 overlay 覆盖了先前配置。
6. `status`、`compatible` 或节点层级错误。
7. 使用了错误的 board 名称。
8. 应用目录和 board overlay 的优先级理解错误。

#### 推荐检查步骤

首先执行干净构建：

```
west build -p always -b <board> <app>
```

查看最终使用的 devicetree 源：

```
west build -t dt-sources
```

查看最终合并结果：

```
build/zephyr/zephyr.dts
```

查看生成宏：

```
build/zephyr/include/generated/zephyr/devicetree_generated.h
```

#### 错误示例

```
&uart1 {
    current-speed = <115200>;
};
```

但实际 SoC 中节点 label 是：

```
usart1: serial@40011000 { ... };
```

`uart1` 和 `usart1` 并不是同一个 label。

#### 正确方法

先查看最终 `zephyr.dts`：

```
usart1: serial@40011000 {
    ...
};
```

然后使用：

```
&usart1 {
    status = "okay";
    current-speed = <115200>;
};
```

#### Alias 问题

应用使用：

```
DEVICE_DT_GET(DT_ALIAS(led0));
```

则 board 必须提供：

```
aliases {
    led0 = &status_led;
};
```

否则会产生编译期错误或未定义节点。

#### 工程结论

不要只检查源码中的 overlay，必须检查：

```
最终 zephyr.dts
最终 .config
最终生成头文件
```

这三个文件分别回答：

```
硬件节点最终是什么？
配置最终是什么？
C 宏最终生成了什么？
```

---

## 问题八：Zephyr 驱动中什么时候使用 `k_mutex`，什么时候使用 `k_sem`？

#### 使用 `k_mutex` 的场景

`k_mutex` 用于保护共享资源，具有所有权语义和优先级继承能力。

适合：

- 多线程共享 I2C/SPI 事务上下文。
- 访问共享设备寄存器。
- 保护驱动状态。
- 保护发送缓冲区。
- 保证一组操作的原子性。

```
k_mutex_lock(&data->lock, K_MSEC(20));

ret = spi_transceive_dt(&cfg->spi, &tx, &rx);

k_mutex_unlock(&data->lock);
```

#### 使用 `k_sem` 的场景

`k_sem` 用于事件通知和资源计数。

适合：

- ISR 通知线程。
- DMA 完成通知。
- UART 接收通知。
- 设备操作完成通知。
- 资源池计数。

```
static void dma_isr(void)
{
    k_sem_give(&dma_done_sem);
}

static int wait_dma_done(void)
{
    return k_sem_take(
        &dma_done_sem,
        K_MSEC(10));
}
```

#### 错误替代

```
/* 用 semaphore 保护共享 SPI 设备 */
k_sem_take(&spi_sem, K_FOREVER);
spi_transaction();
k_sem_give(&spi_sem);
```

问题：

- 没有明确所有权。
- 错误路径容易忘记释放。
- 不具备与 mutex 等价的优先级继承语义。
- 语义表达不清晰。

#### 组合使用

驱动中经常同时使用：

```
mutex：
    保护硬件配置和共享状态

semaphore：
    等待中断/DMA 完成

event：
    表示多个状态位

work：
    将 ISR 事件转移到线程上下文
```

典型流程：

```
线程获取 mutex
    ↓
启动 DMA
    ↓
释放 mutex 或保留事务锁
    ↓
等待 semaphore
    ↓
ISR 释放 semaphore
    ↓
线程检查 DMA 状态
    ↓
释放资源
```

注意：是否在等待 DMA 期间持有 mutex，要根据设备并发模型决定。如果其他线程不能插入同一事务，则需要保持事务级锁；如果锁只保护寄存器配置，则可在启动 DMA 后释放。

---

## 问题九：Zephyr 驱动如何处理 I2C 总线死锁和设备掉线？

I2C 访问不能只依赖：

```
i2c_write_read_dt(...);
```

量产级驱动还需要：

- 超时。
- 有限重试。
- 总线状态检测。
- 控制器复位。
- GPIO 9 脉冲恢复。
- 从设备复位。
- 设备在线状态管理。
- 故障统计。

#### 错误模式

```
while (i2c_is_busy())
{
    /* 无限等待 */
}
```

#### 推荐模式

```
static int i2c_transfer_retry(
    const struct device *bus,
    struct i2c_msg *msgs,
    uint8_t num_msgs,
    uint16_t addr)
{
    int ret;

    for (int retry = 0; retry < 3; retry++)
    {
        ret = i2c_transfer(
            bus,
            msgs,
            num_msgs,
            addr);

        if (ret == 0)
        {
            return 0;
        }

        if (ret == -ETIMEDOUT || ret == -EIO)
        {
            i2c_controller_recover(bus);
            continue;
        }

        return ret;
    }

    return -ETIMEDOUT;
}
```

#### 设备状态机

```
ONLINE
  ↓ 访问失败
RETRYING
  ↓ 恢复成功
ONLINE
  ↓ 连续失败达到阈值
OFFLINE
  ↓ 定时重新探测
PROBING
  ↓ 探测成功
ONLINE
```

不要让应用线程永久阻塞在某个异常设备上。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **Zephyr BSP 不是单一目录，而是 board、SoC、devicetree、Kconfig、pinctrl 和驱动框架的组合。**
2. **devicetree 描述硬件资源，Kconfig 控制代码编译，驱动实现设备行为。**
3. **Zephyr 普遍采用编译期静态设备模型，而不是运行时按名称注册和查找。**
4. **`DEVICE_DT_GET()` 获取设备对象，`device_is_ready()` 判断设备初始化状态。**
5. **驱动应区分 config、data、api 三类信息。**
6. **标准设备应优先实现 Zephyr 标准 API。**
7. **硬件变化优先修改 devicetree，不应修改设备驱动源码。**
8. **所有 ISR 都应短小，阻塞、协议解析和恢复逻辑应转移到线程或 work queue。**
9. **UART 高吞吐场景应采用中断环形缓冲、异步 API 或 DMA。**
10. **I2C、SPI 和 Flash 驱动必须具备超时、错误统计和恢复策略。**
11. **多实例驱动必须为每个实例生成独立的 config 和 data。**
12. **调试 devicetree 问题必须查看最终生成的 `zephyr.dts`，不能只看源文件。**

## 13.2 性能排序

### 设备句柄获取开销

```
DEVICE_DT_GET()
    <
字符串查找
    <
运行时动态创建和注册
```

### UART CPU 占用

```
Polling
    >
逐字节中断
    >
批量中断
    >
DMA/异步 API
```

### 配置可移植性

```
驱动内硬编码
    <
board C 文件宏
    <
devicetree overlay
    <
标准 binding + devicetree
```

### 运行时确定性

```
静态设备对象
    >
固定大小内存池
    >
普通动态堆
```

## 13.3 通用选型结论

|需求|推荐方案|
|---|---|
|早期启动日志|UART polling|
|普通 CLI|UART interrupt + ring buffer|
|高速串口升级|UART async/DMA + 双缓冲|
|标准 I2C 传感器|devicetree + Sensor API|
|标准 SPI Flash|SPI controller + JEDEC NOR driver|
|板级 LED/按键|GPIO devicetree spec|
|高速采集|DMA + work/semaphore + 双缓冲|
|私有硬件控制器|自定义 driver API + binding|
|多板卡复用|board overlay + 通用驱动|
|量产设备|静态设备模型 + 完整错误恢复|

---

# 14. 快速参考速查表

## 14.1 常用设备获取方式

|需求|API|
|---|---|
|节点 label|`DEVICE_DT_GET(DT_NODELABEL(uart0))`|
|alias|`DEVICE_DT_GET(DT_ALIAS(led0))`|
|chosen|`DEVICE_DT_GET(DT_CHOSEN(zephyr_console))`|
|驱动实例|`DEVICE_DT_INST_GET(inst)`|
|子节点总线|`DEVICE_DT_GET(DT_BUS(node_id))`|
|GPIO 描述|`GPIO_DT_SPEC_GET(node, gpios)`|
|I2C 描述|`I2C_DT_SPEC_GET(node)`|
|SPI 描述|`SPI_DT_SPEC_GET(node, operation, delay)`|
|PWM 描述|`PWM_DT_SPEC_GET(node)`|
|ADC 通道|`ADC_DT_SPEC_GET_BY_IDX(node, idx)`|

## 14.2 驱动实例宏

```
#define DT_DRV_COMPAT acme_my_device

#define MY_DEVICE_INIT(inst)                              \
    static struct my_data my_data_##inst;                \
    static const struct my_config my_cfg_##inst =        \
    {                                                     \
        .base = DT_INST_REG_ADDR(inst),                  \
    };                                                    \
                                                          \
    DEVICE_DT_INST_DEFINE(                               \
        inst,                                             \
        my_init,                                          \
        NULL,                                             \
        &my_data_##inst,                                  \
        &my_cfg_##inst,                                   \
        POST_KERNEL,                                      \
        CONFIG_MY_INIT_PRIORITY,                         \
        &my_api);

DT_INST_FOREACH_STATUS_OKAY(MY_DEVICE_INIT)
```

## 14.3 调试文件

|文件|用途|
|---|---|
|`build/zephyr/zephyr.dts`|查看最终 devicetree|
|`build/zephyr/.config`|查看最终 Kconfig|
|`devicetree_generated.h`|查看生成宏|
|`zephyr.map`|查看符号和内存占用|
|`compile_commands.json`|查看实际编译命令|
|日志输出|查看设备 init 错误|

## 14.4 驱动错误处理表

|场景|推荐返回值|
|---|---|
|参数为空|`-EINVAL`|
|节点不存在|编译期错误或 `-ENODEV`|
|设备未 ready|`-ENODEV`|
|总线访问失败|`-EIO`|
|硬件等待超时|`-ETIMEDOUT`|
|不支持功能|`-ENOTSUP`|
|资源忙|`-EBUSY`|
|资源耗尽|`-ENOMEM`|
|暂时不可用|`-EAGAIN`|

---

# 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  Zephyr board、SoC、devicetree 和驱动之间的职责边界是什么？
- [ ]  `DEVICE_DT_DEFINE()` 和 `DEVICE_DT_INST_DEFINE()` 的作用是什么？
- [ ]  `DEVICE_DT_GET()` 与 `device_is_ready()` 的区别是什么？
- [ ]  Kconfig 和 devicetree 分别解决什么问题？
- [ ]  为什么硬件地址和 GPIO 不应硬编码在驱动源码中？
- [ ]  如何区分驱动的 config、data 和 api？
- [ ]  如何实现一个多实例 Zephyr 驱动？
- [ ]  `PRE_KERNEL_1`、`PRE_KERNEL_2`、`POST_KERNEL`、`APPLICATION` 有什么区别？
- [ ]  UART polling、中断和 DMA 的选型依据是什么？
- [ ]  如何处理 UART DMA 的接收缓冲区回绕？
- [ ]  为什么不能在 GPIO ISR 中调用 I2C？
- [ ]  如何定位 devicetree overlay 没有生效？
- [ ]  如何实现 I2C 总线恢复？
- [ ]  SPI 命令和数据为什么有时必须放在一次事务中？
- [ ]  什么时候使用 `k_mutex`，什么时候使用 `k_sem`？
- [ ]  如何设计驱动的超时、重试和故障降级机制？
- [ ]  如何从 `zephyr.map` 判断驱动是否被链接进最终镜像？

建议通过以下实践验收：

```
1. 创建一个自定义 Zephyr board。
2. 添加一个 UART console。
3. 使用 devicetree 配置 LED 和按键。
4. 实现一个 GPIO 中断 + k_work 消抖。
5. 为 I2C 传感器编写 binding 和驱动实例。
6. 创建一个多实例 SPI 设备驱动。
7. 为 UART 增加中断环形接收。
8. 将 UART 改为异步/DMA 接收。
9. 注入 I2C SDA 卡低故障并完成恢复。
10. 使用最终 zephyr.dts、.config 和 map 文件完成问题定位。
```

---

# 16. 实践与进阶路径

## 16.1 阶段一：Board 基础适配

### 任务

- 创建板卡目录。
- 配置启动、时钟和链接脚本。
- 添加 board DTS。
- 配置 console。
- 添加 LED 和按键 alias。
- 完成 `west build` 和 `west flash`。

### 验收指标

```
板卡可启动
串口日志正常
LED 可控制
按键中断可触发
device_is_ready() 检查通过
```

## 16.2 阶段二：标准外设框架适配

### 任务

- 使用 GPIO API 控制 LED。
- 使用 UART interrupt API 接收数据。
- 使用 I2C API 读取传感器。
- 使用 SPI API 读取 Flash JEDEC ID。
- 使用 PWM API 输出波形。
- 使用 ADC API 读取电池电压。

### 验收指标

```
不直接操作应用层寄存器
硬件参数全部通过 devicetree 配置
多个 board overlay 可以复用同一驱动
非法配置在编译期或启动期明确失败
```

## 16.3 阶段三：自定义驱动开发

### 任务

- 编写 binding YAML。
- 定义 `DT_DRV_COMPAT`。
- 实现 config/data/api。
- 使用 `DEVICE_DT_INST_DEFINE()`。
- 支持多个 devicetree 实例。
- 增加日志和错误统计。
- 编写驱动单元测试。

### 验收指标

```
两个硬件实例互不共享运行时状态
驱动可通过 Kconfig 裁剪
设备初始化失败可观察
所有硬件等待有超时
```

## 16.4 阶段四：高吞吐和故障恢复

### 任务

- UART DMA 双缓冲。
- 环形缓冲区溢出统计。
- I2C 总线恢复。
- SPI Flash 编程超时。
- DMA Cache 一致性处理。
- 设备掉线和重连。
- 电源管理和设备 suspend/resume。

### 验收指标

```
921600 bps 连续接收无丢包
I2C SDA 拉低可恢复
SPI Flash 异常 busy 不会死锁
Cache 开启后数据仍正确
设备掉线不阻塞系统其他业务
```

## 16.5 阶段五：工程化和上游质量

### 任务

- 添加 Kconfig 文档。
- 添加 devicetree binding 文档。
- 添加 board README 和硬件文档。
- 通过编译器告警检查。
- 运行静态分析。
- 编写 twister 测试。
- 支持多个 board。
- 控制 patch 边界，避免修改无关子系统。

### 验收指标

```
多板卡自动构建通过
最小配置可以编译
驱动关闭后没有未定义引用
测试覆盖正常路径和错误路径
可从最终构建产物追溯设备配置
```

## 16.6 性能测试方法

### 设备初始化耗时

使用 GPIO 或 cycle counter 记录：

```
uint32_t start = k_cycle_get_32();

ret = my_device_init(dev);

uint32_t end = k_cycle_get_32();

LOG_INF("init cycles=%u", end - start);
```

换算：

```
时间 = cycle_count / CPU_frequency
```

### ISR 执行时间

```
static void uart_isr(...)
{
    uint32_t start = k_cycle_get_32();

    uart_irq_service();

    uint32_t end = k_cycle_get_32();

    if (end - start > max_isr_cycles)
    {
        max_isr_cycles = end - start;
    }
}
```

同时建议使用 GPIO 输出进行示波器验证，因为日志和软件计数本身可能干扰时序。

### UART 丢包测试

测试条件至少包括：

```
115200 / 460800 / 921600 bps
CPU 高负载
日志开启和关闭
Cache 开启和关闭
Flash 擦写并发
不同缓冲区大小
不同线程优先级
```

记录：

- 接收字节数。
- 缓冲区溢出次数。
- UART 硬件错误次数。
- CRC 错误次数。
- 最大接收延迟。
- CPU 占用率。

### I2C 故障注入

主动注入：

```
SDA 拉低
SCL 拉低
从设备中途复位
主机中途复位
设备不响应 ACK
总线频率异常
```

验证：

```
访问是否超时
恢复是否执行
其他设备是否仍可访问
设备是否能回到 ONLINE 状态
系统是否出现死锁
```

## 16.7 进阶学习方向

### Zephyr 内核和设备模型

- `struct device` 和 device handle。
- device init level。
- devicetree dependency ordinal。
- linker section 设备生成机制。
- Kconfig 配置合并。
- CMake target 依赖。
- `SYS_INIT()` 与设备初始化。
- `k_work`、`k_poll`、`k_fifo` 和 `k_msgq`。

### MCU 和硬件底层

- DMA request mux。
- FIFO watermark。
- UART idle-line 检测。
- SPI FIFO 和片选控制。
- I2C clock stretching。
- M33 TrustZone 下的外设访问。
- MPU 内存属性。
- D-Cache 和 DMA 一致性。
- 低功耗下外设保持和唤醒。

### 工程化方向

- Zephyr Twister 自动测试。
- Renode/QEMU 硬件仿真。
- Hardware-in-the-loop。
- CI 中多 board 构建。
- SBOM 和许可证检查。
- MISRA-C/CERT-C。
- 静态分析与代码覆盖率。
- 上游 Zephyr patch 组织。
- 驱动 API 兼容性和版本迁移。

最终应具备以下能力：

```
能够从一块新 MCU 板卡出发，
完成 board、SoC 配置、devicetree、Kconfig、pinctrl、
标准外设驱动、自定义设备驱动、DMA、错误恢复、
低功耗和自动化测试，
并交付一个可复用、可裁剪、可验证、可维护的 Zephyr BSP。
```