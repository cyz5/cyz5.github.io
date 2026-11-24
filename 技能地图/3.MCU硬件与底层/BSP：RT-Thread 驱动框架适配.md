

## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 **BSP、芯片 HAL、RT-Thread 设备驱动框架、应用层**之间的分层关系。
- 理解 RT-Thread 设备模型中以下核心对象的职责：
    - `rt_device`
    - `rt_device_ops`
    - `rt_device_ops_pin`
    - `rt_device_ops_uart`
    - `rt_device_ops_i2c_bus`
    - `rt_device_ops_spi`
- 理解 RT-Thread 自动初始化机制、设备注册机制和设备查找机制。
- 理解字符设备、总线设备、设备驱动与设备实例之间的关系。
- 理解中断上下文、线程上下文、DMA 上下文在驱动中的边界。

### 1.2 掌握

能够：

- 创建一个可编译、可启动、可维护的 RT-Thread BSP。
- 完成 UART、GPIO、I2C、SPI、ADC、PWM 等基础外设的框架适配。
- 使用 `rt_device_register()` 注册自定义设备。
- 正确实现设备的：
    - `init`
    - `open`
    - `close`
    - `read`
    - `write`
    - `control`
- 使用 `rt_device_find()`、`rt_device_open()`、`rt_device_control()` 访问设备。
- 正确处理中断回调、事件通知、DMA 收发和缓存一致性。

### 1.3 精通

能够分析和解决：

- UART 丢包、DMA 环形缓冲区溢出。
- I2C 总线死锁、SDA 被拉低、总线恢复。
- SPI 片选时序错误、DMA 完成时序错误。
- GPIO 中断抖动、回调执行时间过长。
- 设备重复注册、初始化顺序错误、设备名冲突。
- 驱动阻塞导致系统实时性下降。
- 多线程并发访问同一设备导致数据竞争。
- 不同芯片 HAL API 差异导致 BSP 可移植性下降。

### 1.4 能够设计

能够设计：

- 分层清晰的 RT-Thread BSP 目录结构。
- 支持轮询、中断、DMA 三种工作模式的 UART 驱动。
- 可复用的 I2C 传感器设备适配层。
- 基于设备框架的 SPI Flash、传感器、显示屏驱动。
- 支持 Kconfig、SCons、自动初始化和组件裁剪的工业级 BSP。
- 具备故障恢复、超时、统计、日志、测试接口的生产级驱动。

---

# 2. 前置要求

## 2.1 知识要求

必须掌握：

- C 语言：
    - 结构体和函数指针
    - `volatile`
    - 指针与内存映射
    - 位操作
    - 链表和环形缓冲区
- MCU 基础：
    - 中断控制器
    - GPIO 复用
    - UART、I2C、SPI、DMA 工作原理
    - 时钟树和复位控制
- RTOS 基础：
    - 线程、信号量、互斥锁、事件
    - 中断与线程上下文
    - 临界区和调度
- RT-Thread 基础：
    - `rt_thread`
    - `rt_sem`
    - `rt_mutex`
    - `rt_event`
    - `rt_device`

## 2.2 技能要求

建议具备：

- 能够使用芯片厂商 IDE 或 CMake/SCons 编译工程。
- 能够阅读芯片参考手册和 HAL 源码。
- 能够使用逻辑分析仪、示波器、J-Link/SWD 调试器。
- 能够查看 map 文件、反汇编和启动日志。
- 能够独立定位 HardFault、总线异常、DMA 传输错误。
- 能够编写简单的 Python、Shell 或串口测试脚本。

---

# 3. 技术概述

## 3.1 BSP 的定义

BSP，即 Board Support Package，板级支持包，是将一块具体硬件板卡适配到操作系统所需的底层软件集合。

典型 BSP 包含：

```
BSP
├── 启动文件
├── 链接脚本
├── 系统时钟初始化
├── 中断向量表
├── GPIO 配置
├── UART 适配
├── I2C/SPI/ADC/PWM 适配
├── 板级引脚定义
├── RT-Thread 配置
├── Kconfig
├── SConscript
└── 板级初始化代码
```

BSP 的边界不是“把 HAL 调起来”这么简单，而是要提供一个稳定的硬件抽象契约：

```
应用层
  ↓
组件/设备驱动层
  ↓
RT-Thread 设备框架
  ↓
BSP 驱动适配层
  ↓
芯片 HAL/LL/寄存器
  ↓
MCU 外设与板级硬件
```

## 3.2 RT-Thread 驱动框架的核心定位

RT-Thread 设备框架解决的主要问题是：

1. **设备统一命名**
2. **设备生命周期管理**
3. **设备访问接口统一**
4. **驱动与应用解耦**
5. **轮询、中断、DMA 访问模式抽象**
6. **设备控制命令统一**
7. **组件复用**

例如，应用不应该直接调用：

```
HAL_UART_Transmit(&huart1, data, len, timeout);
```

而应使用：

```
rt_device_write(serial, 0, data, len);
```

这样应用不依赖具体 MCU 厂商 HAL。

## 3.3 主流适配方式分类

|适配方式|特点|适用场景|风险|
|---|---|---|---|
|直接使用 RT-Thread 官方 BSP|开发快，生态成熟|常见开发板|板级定制不足|
|基于同系列 BSP 修改|复用启动代码和驱动|同系列 MCU 新板|隐含旧板配置|
|从厂商 HAL 重建 BSP|控制力强，结构清晰|工业产品、自研芯片|初期工作量大|
|直接寄存器驱动|性能和控制力最好|高实时、特殊硬件|维护成本高|
|HAL 封装适配|开发效率高|大多数量产项目|HAL 黑盒、时延不确定|
|LL/寄存器混合|性能与可维护性平衡|UART/SPI 高吞吐|需要严格边界管理|

## 3.4 RT-Thread 设备模型

典型设备访问流程：

```
设备注册
    ↓
rt_device_register()
    ↓
设备加入全局设备链表
    ↓
rt_device_find("uart1")
    ↓
rt_device_open()
    ↓
rt_device_read()/write()/control()
    ↓
底层驱动 ops
```

基础设备结构通常包含：

```
struct rt_device
{
    struct rt_object parent;       /* 内核对象基类 */
    rt_uint16_t      type;         /* 设备类型 */
    rt_uint16_t      flag;         /* 设备标志 */
    rt_uint8_t       open_flag;    /* 打开状态 */
    rt_uint8_t       ref_count;    /* 引用计数 */
    rt_size_t        rx_indicate;  /* 接收回调，具体版本可能为函数指针 */
    rt_size_t        tx_complete;  /* 发送完成回调 */
    void            *user_data;
    const struct rt_device_ops *ops;
};
```

不同 RT-Thread 版本在字段类型和结构细节上可能存在差异，实际开发必须以当前版本头文件为准。

---

# 4. 核心特性横向对比

## 4.1 BSP 分层方案对比

|方案|可移植性|性能|开发效率|调试难度|推荐场景|
|---|---|---|---|---|---|
|应用直接调用 HAL|低|高|高|中|原型验证|
|BSP 封装 HAL|高|中高|中高|中|通用产品|
|RT-Thread 设备框架|很高|中高|高|低中|多设备、多组件系统|
|直接寄存器驱动|中|最高|低|高|强实时、特殊时序|
|外设组件直接访问寄存器|极低|最高|低|很高|不建议量产|

## 4.2 UART 访问模式对比

|模式|CPU 占用|时延|吞吐能力|实现复杂度|适用场景|
|---|---|---|---|---|---|
|轮询|高|可预测|低|低|低速控制、启动阶段|
|中断|中|低|中|中|命令行、普通串口|
|DMA 普通模式|低|低|高|中高|大块数据|
|DMA 环形模式|很低|低|很高|高|连续数据流|
|双缓冲 DMA|很低|极低|很高|高|高速连续采集|

## 4.3 I2C 设备访问模式对比

|方式|是否阻塞|错误处理能力|兼容性|适用场景|
|---|---|---|---|---|
|HAL 阻塞式|是|中|高|低速传感器|
|RT-Thread 总线设备|可选|高|高|多设备共享总线|
|自定义异步队列|否|高|中|高并发系统|
|直接寄存器状态机|否|最高|低|严格实时系统|

## 4.4 设备层和总线层对比

|层次|典型对象|主要职责|
|---|---|---|
|控制器层|`i2c_bus_device`、SPI 控制器|管理硬件总线和传输|
|从设备层|温度传感器、Flash、LCD|管理设备协议和寄存器|
|组件层|sensor、fal、finsh|向上提供统一组件接口|
|应用层|业务线程|不关心硬件寄存器|

---

# 5. 底层原理与功能特性深度解析

## 5.1 BSP 启动过程

典型启动路径如下：

```
复位
 ↓
Reset_Handler
 ↓
SystemInit()
 ↓
初始化 .data/.bss
 ↓
rtthread_startup()
 ↓
board_init()
 ↓
rt_hw_board_init()
 ↓
rt_components_board_init()
 ↓
rt_components_init()
 ↓
main()
```

不同 RT-Thread 版本、配置项和 BSP 模板可能导致函数名略有差异，但核心思想一致：

1. 完成 CPU 和时钟初始化。
2. 初始化堆和系统定时器。
3. 初始化串口等基础设备。
4. 初始化设备框架。
5. 初始化组件。
6. 创建主线程并进入调度。

## 5.2 自动初始化机制

RT-Thread 常见初始化宏：

```
INIT_BOARD_EXPORT(board_init);
INIT_DEVICE_EXPORT(sensor_init);
INIT_COMPONENT_EXPORT(component_init);
INIT_APP_EXPORT(application_init);
```

宏的本质通常是将函数指针放入特定链接段：

```
typedef int (*init_fn_t)(void);

#define INIT_EXPORT(fn, level)                  \
    RT_USED const init_fn_t __rt_init_##fn      \
    RT_SECTION(".rti_fn." level) = fn
```

启动阶段通过遍历链接段执行：

```
for (fn = init_fn_begin; fn < init_fn_end; fn++)
{
    (*fn)();
}
```

### 初始化顺序设计原则

```
board
  ↓
device
  ↓
component
  ↓
env
  ↓
app
```

例如：

- GPIO 和时钟必须先于 UART。
- I2C 控制器必须先于传感器驱动。
- Flash 驱动必须先于 FAL。
- FAL 必须先于文件系统。
- 文件系统必须先于依赖文件系统的应用线程。

## 5.3 自定义字符设备注册

下面实现一个虚拟 ADC 设备，展示生产级设备框架结构。

```
#include <rtthread.h>
#include <rtdevice.h>

#define VADC_CTRL_SET_CHANNEL   0x01
#define VADC_CTRL_GET_STATUS    0x02

struct vadc_device
{
    struct rt_device parent;

    rt_uint8_t channel;
    rt_bool_t initialized;
    rt_mutex_t lock;

    rt_uint32_t sample_count;
    rt_uint32_t error_count;
};

static rt_err_t vadc_init(rt_device_t dev)
{
    struct vadc_device *vadc = (struct vadc_device *)dev->user_data;

    if (vadc == RT_NULL)
        return -RT_EINVAL;

    /* 配置时钟、GPIO、ADC 寄存器 */
    vadc->channel = 0;
    vadc->sample_count = 0;
    vadc->error_count = 0;
    vadc->initialized = RT_TRUE;

    return RT_EOK;
}

static rt_err_t vadc_open(rt_device_t dev, rt_uint16_t oflag)
{
    RT_UNUSED(oflag);

    if (dev == RT_NULL)
        return -RT_EINVAL;

    return RT_EOK;
}

static rt_err_t vadc_close(rt_device_t dev)
{
    if (dev == RT_NULL)
        return -RT_EINVAL;

    return RT_EOK;
}

static rt_size_t vadc_read(
    rt_device_t dev,
    rt_off_t pos,
    void *buffer,
    rt_size_t size)
{
    struct vadc_device *vadc;
    rt_uint16_t *samples;
    rt_size_t i;

    RT_UNUSED(pos);

    if ((dev == RT_NULL) || (buffer == RT_NULL) || (size == 0))
        return 0;

    vadc = (struct vadc_device *)dev->user_data;
    samples = (rt_uint16_t *)buffer;

    if (rt_mutex_take(vadc->lock, rt_tick_from_millisecond(20)) != RT_EOK)
        return 0;

    for (i = 0; i < size; i++)
    {
        /*
         * 实际项目中这里应执行：
         * 1. 启动 ADC
         * 2. 等待转换完成
         * 3. 检查溢出和错误
         * 4. 读取 ADC 数据寄存器
         */
        samples[i] = 2048;
        vadc->sample_count++;
    }

    rt_mutex_release(vadc->lock);

    return size;
}

static rt_size_t vadc_write(
    rt_device_t dev,
    rt_off_t pos,
    const void *buffer,
    rt_size_t size)
{
    RT_UNUSED(dev);
    RT_UNUSED(pos);
    RT_UNUSED(buffer);
    RT_UNUSED(size);

    /* ADC 通常不支持 write */
    return 0;
}

static rt_err_t vadc_control(
    rt_device_t dev,
    int cmd,
    void *args)
{
    struct vadc_device *vadc;

    if ((dev == RT_NULL) || (dev->user_data == RT_NULL))
        return -RT_EINVAL;

    vadc = (struct vadc_device *)dev->user_data;

    switch (cmd)
    {
    case VADC_CTRL_SET_CHANNEL:
        if (args == RT_NULL || *(rt_uint8_t *)args >= 16)
            return -RT_EINVAL;

        vadc->channel = *(rt_uint8_t *)args;
        return RT_EOK;

    case VADC_CTRL_GET_STATUS:
        if (args == RT_NULL)
            return -RT_EINVAL;

        *(rt_uint32_t *)args = vadc->error_count;
        return RT_EOK;

    default:
        return -RT_ENOSYS;
    }
}

static const struct rt_device_ops vadc_ops =
{
    .init = vadc_init,
    .open = vadc_open,
    .close = vadc_close,
    .read = vadc_read,
    .write = vadc_write,
    .control = vadc_control,
};

static struct vadc_device vadc0;

static int vadc_register(void)
{
    vadc0.parent.type = RT_Device_Class_Char;
    vadc0.parent.ops = &vadc_ops;
    vadc0.parent.user_data = &vadc0;
    vadc0.lock = rt_mutex_create("vadc", RT_IPC_FLAG_PRIO);

    if (vadc0.lock == RT_NULL)
        return -RT_ENOMEM;

    return rt_device_register(
        &vadc0.parent,
        "adc0",
        RT_DEVICE_FLAG_RDWR);
}
INIT_DEVICE_EXPORT(vadc_register);
```

### 关键设计点

- `user_data` 不应指向临时栈变量。
- `read()` 返回实际读取的元素数，而不是字节数时，要在接口文档中明确。
- `control()` 必须校验 `args`。
- 多线程访问硬件寄存器时必须加锁。
- 不支持的操作返回 `-RT_ENOSYS`，不要静默成功。

## 5.4 UART 驱动适配的核心

UART 驱动通常涉及三类上下文：

```
线程上下文：
    rt_device_read/write
    允许阻塞、获取互斥锁

中断上下文：
    ISR、DMA 完成回调
    禁止阻塞、禁止大规模日志输出

后台线程：
    处理协议帧、超时和业务逻辑
```

UART 中断接收的典型逻辑：

```
static void uart_rx_isr(struct uart_device *uart)
{
    rt_uint8_t ch;

    while (UART_RX_READY(uart))
    {
        ch = UART_READ_DATA(uart);

        if (ringbuf_put(&uart->rx_rb, ch) != 0)
        {
            uart->rx_overflow++;
        }
    }

    /*
     * 只做轻量通知，不在 ISR 中解析完整协议帧
     */
    if (uart->rx_sem != RT_NULL)
    {
        rt_sem_release(uart->rx_sem);
    }
}
```

协议解析线程：

```
static void protocol_thread_entry(void *parameter)
{
    struct protocol_ctx *ctx = parameter;
    rt_uint8_t temp[64];

    while (1)
    {
        if (rt_sem_take(ctx->rx_sem, rt_tick_from_millisecond(100))
            != RT_EOK)
        {
            protocol_check_timeout(ctx);
            continue;
        }

        while (ringbuf_available(&ctx->rx_rb) > 0)
        {
            rt_size_t n = ringbuf_read(
                &ctx->rx_rb,
                temp,
                sizeof(temp));

            protocol_feed(ctx, temp, n);
        }
    }
}
```

## 5.5 I2C 总线设备适配

I2C 的设备层不应直接控制 GPIO 或寄存器，而应通过总线接口完成传输。

```
struct rt_i2c_msg msgs[2];
rt_uint8_t reg = 0x0F;
rt_uint8_t value = 0;

msgs[0].addr  = 0x1D;
msgs[0].flags = RT_I2C_WR;
msgs[0].buf   = &reg;
msgs[0].len   = 1;

msgs[1].addr  = 0x1D;
msgs[1].flags = RT_I2C_RD;
msgs[1].buf   = &value;
msgs[1].len   = 1;

if (rt_i2c_transfer(i2c_bus, msgs, 2) != 2)
{
    /* 传输失败：记录错误并执行恢复策略 */
}
```

设备驱动应处理：

- 设备地址有效性。
- 寄存器读写端序。
- ACK/NACK。
- 超时。
- 总线恢复。
- 重试次数。
- 设备掉线。
- 上电稳定时间。

## 5.6 I2C 总线恢复

典型 I2C 卡死原因：

- 从设备在传输过程中复位。
- 主机复位但从设备保持在数据阶段。
- SDA 被从设备拉低。
- SCL 被从设备拉低。
- 中断状态未清除。
- DMA 传输被提前终止。

恢复流程：

```
禁用 I2C 外设
    ↓
GPIO 开漏模式
    ↓
读取 SDA/SCL
    ↓
若 SCL 为高且 SDA 为低：
    输出 9 个 SCL 脉冲
    ↓
输出 STOP：SDA 低 → SCL 高 → SDA 高
    ↓
重新初始化 I2C
    ↓
探测设备并恢复业务
```

示例：

```
static rt_err_t i2c_bus_recover(void)
{
    int i;

    i2c_hw_disable();

    gpio_set_scl_output_open_drain();
    gpio_set_sda_output_open_drain();

    gpio_write_sda(1);
    gpio_write_scl(1);

    for (i = 0; i < 9 && gpio_read_sda() == 0; i++)
    {
        gpio_write_scl(0);
        delay_us(5);
        gpio_write_scl(1);
        delay_us(5);
    }

    /* 生成 STOP */
    gpio_write_sda(0);
    delay_us(2);
    gpio_write_scl(1);
    delay_us(2);
    gpio_write_sda(1);

    i2c_hw_enable();

    return (gpio_read_sda() && gpio_read_scl())
           ? RT_EOK
           : -RT_ERROR;
}
```

实际项目中应根据芯片 GPIO 复用和开漏配置要求修改。

## 5.7 SPI 设备适配

SPI 设备通常包含：

```
SPI 控制器
 ├── CS0 ── SPI Flash
 ├── CS1 ── LCD
 └── CS2 ── 传感器
```

访问时必须保证：

- CS 在整个事务期间保持有效。
- SPI 模式正确：
    - CPOL
    - CPHA
- 数据位宽正确。
- 高速设备满足建立时间和保持时间。
- DMA 缓冲区满足对齐要求。
- 事务完成前不得释放 CS。

```
struct rt_spi_device *spi_dev;

spi_dev = (struct rt_spi_device *)rt_device_find("spi10");
if (spi_dev == RT_NULL)
{
    return -RT_ENODEV;
}

struct rt_spi_configuration cfg =
{
    .mode = RT_SPI_MASTER | RT_SPI_MODE_0 | RT_SPI_MSB,
    .data_width = 8,
    .max_hz = 20 * 1000 * 1000,
};

rt_spi_configure(spi_dev, &cfg);

rt_uint8_t tx[2] = {0x9F, 0x00};
rt_uint8_t rx[2] = {0};

if (rt_spi_send_then_recv(spi_dev, tx, 1, rx, 1) != 1)
{
    return -RT_ERROR;
}
```

---

# 6. 性能量化分析

以下数据为典型 Cortex-M4、120 MHz、RT-Thread、无缓存或低缓存配置下的工程测量参考值。实际数据必须在目标板上重新测量。

## 6.1 设备访问开销

|操作|典型耗时|主要开销|
|---|---|---|
|`rt_device_find()`|2~10 μs|设备链表遍历|
|`rt_device_open()`|1~5 μs|标志检查和回调|
|`rt_device_control()`|0.5~3 μs|函数指针调用|
|中断唤醒线程|3~15 μs|ISR、调度、上下文切换|
|信号量获取|0.5~4 μs|内核对象操作|
|互斥锁获取|0.5~5 μs|优先级继承及调度判断|

若设备数量为 `N`，设备名平均比较长度为 `L`，则：

```
T_find ≈ N × (链表遍历开销 + L × 字符比较开销)
```

因此不要在高频实时路径中反复调用：

```
rt_device_find("uart1");
```

推荐在初始化阶段缓存设备句柄：

```
static rt_device_t uart1_dev;

uart1_dev = rt_device_find("uart1");
```

## 6.2 UART 吞吐量

串口有效字节率：

```
有效字节率 = 波特率 / 每帧位数
```

典型 8N1：

```
每帧位数 = 1 起始位 + 8 数据位 + 1 停止位 = 10
```

115200 波特率下：

```
有效字节率 = 115200 / 10 = 11520 Byte/s
```

若接收环形缓冲区为 256 字节：

```
理论缓存覆盖时间 = 256 / 11520 ≈ 22.2 ms
```

如果协议线程最长阻塞时间超过 22 ms，就存在溢出风险。

## 6.3 DMA 与中断 CPU 占用

假设：

- UART 速率：921600 bit/s
- 8N1
- 中断每字节触发
- 单次中断处理耗时：2.5 μs

有效字节率：

```
921600 / 10 = 92160 Byte/s
```

CPU 时间占用：

```
92160 × 2.5 μs = 230.4 ms/s ≈ 23.0%
```

若 DMA 每 64 字节触发一次：

```
中断频率 = 92160 / 64 = 1440 次/s
CPU 占用 = 1440 × 2.5 μs = 3.6 ms/s ≈ 0.36%
```

**DMA 的收益主要来自减少中断频率，而不只是减少数据搬运。**

## 6.4 环形缓冲区容量计算

设：

- 输入峰值速率：`R` Byte/s
- 线程最大不可运行时间：`T` s
- 安全系数：`K = 1.5~2.0`

则：

```
RingBufferSize ≥ R × T × K
```

例如：

```
R = 92160 Byte/s
T = 10 ms
K = 2

Size ≥ 92160 × 0.01 × 2 = 1843.2 Byte
```

应选择 2048 字节，而不是 1024 字节。

## 6.5 I2C 传输时间

I2C 一次事务大致包括：

```
T ≈ 起始 + 地址 + 寄存器 + 数据 + ACK + 停止
```

以 400 kHz、写 1 字节寄存器地址、读 2 字节为例：

```
约 1 地址字节
+ 1 寄存器字节
+ 2 数据字节
+ ACK/NACK
≈ 40~50 bit
```

理论时间约：

```
50 / 400000 = 125 μs
```

考虑软件调度、HAL 状态机和总线空闲时间后，实际常见为 **150~300 μs**。

## 6.6 内存开销

典型驱动内存：

|模块|典型 RAM|
|---|---|
|设备对象|64~160 Byte|
|UART 环形缓冲区|256~4096 Byte|
|DMA 描述信息|32~128 Byte|
|I2C 消息数组|每条 16~32 Byte|
|SPI 设备对象|64~128 Byte|
|设备互斥锁/信号量|40~100 Byte|
|驱动线程栈|512~4096 Byte|

原则：

- 大缓冲区优先静态分配。
- 不在高频路径中动态申请。
- 线程栈根据栈水位测量，而不是凭经验扩大。
- DMA 缓冲区放到 DMA 可访问内存区域。
- 带 D-Cache 的 MCU 必须处理缓存一致性。

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要接入 RT-Thread 组件或应用？
├── 否
│   ├── 仅启动阶段使用？
│   │   └── 可直接使用 HAL/LL
│   └── 强实时特殊控制？
│       └── BSP 内部使用寄存器或 LL，并封装边界
└── 是
    ├── 是否属于标准外设？
    │   ├── 是
    │   │   ├── 低吞吐、简单访问？
    │   │   │   └── 轮询或中断模式
    │   │   └── 连续高速数据？
    │   │       └── DMA/环形 DMA
    │   └── 否
    │       └── 自定义 rt_device 设备
    ├── 是否多设备共享总线？
    │   ├── 是 → 使用 I2C/SPI 总线框架
    │   └── 否 → 可采用专用设备驱动
    └── 是否需要量产级恢复能力？
        ├── 是 → 加入超时、重试、复位、总线恢复、统计
        └── 否 → 原型版本可简化
```

## 7.2 典型场景

|需求|推荐方案|理由|
|---|---|---|
|CLI 串口|UART 中断接收 + 环形缓冲|低延迟、实现简单|
|921600 bps 升级|UART DMA + 环形缓冲|降低 CPU 占用|
|温度传感器|I2C 总线 + 设备层驱动|多设备复用、便于替换|
|SPI NOR Flash|SPI 设备 + FAL|可接入文件系统|
|高速 ADC|DMA + 双缓冲 + 事件通知|连续采样不丢数据|
|LCD|SPI 设备 + 专用显示驱动|事务边界清晰|
|电机 PWM|PWM 框架 + 定时器底层驱动|统一频率和占空比接口|
|按键|GPIO 中断 + 消抖线程|ISR 轻量、逻辑可扩展|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：硬件相关代码只能停留在 BSP 层

不推荐：

```
/* 应用层直接访问芯片寄存器 */
USART1->DR = ch;
```

推荐：

```
rt_device_write(serial, 0, &ch, 1);
```

### 原则二：驱动接口必须明确阻塞语义

每个接口都应说明：

- 是否阻塞。
- 最大阻塞时间。
- 是否允许在中断中调用。
- 超时时返回什么。
- 失败后设备是否仍然可用。

### 原则三：驱动必须具备故障闭环

至少包括：

```
检测错误
  ↓
记录错误码和计数
  ↓
执行局部恢复
  ↓
恢复失败则复位设备
  ↓
通知上层
```

### 原则四：ISR 只做最少工作

ISR 中禁止：

- `rt_thread_mdelay()`
- 文件系统操作
- 长时间循环
- 大量日志输出
- 动态内存分配
- 复杂协议解析

### 原则五：所有硬件等待必须有超时

错误：

```
while (!UART_TXE());
```

正确：

```
rt_tick_t start = rt_tick_get();

while (!UART_TXE())
{
    if ((rt_tick_get() - start) > timeout_ticks)
        return -RT_ETIMEOUT;
}
```

## 8.2 选型决策矩阵

|指标|轮询|中断|DMA|自定义状态机|
|---|---|---|---|---|
|开发复杂度|低|中|高|很高|
|CPU 占用|高|中|低|低|
|实时确定性|高|中高|中|高|
|连续流能力|低|中|高|高|
|故障恢复复杂度|低|中|高|很高|
|推荐等级|原型/低速|通用默认|高吞吐|特殊系统|

## 8.3 工业级编码规范

- 所有硬件寄存器定义使用明确宽度类型。
- ISR 与主线程共享变量使用 `volatile`，但不能把 `volatile` 当作同步机制。
- 驱动状态必须有明确状态机。
- 所有错误路径必须释放锁、恢复 CS、停止 DMA。
- 设备名统一命名：
    - `uart1`
    - `i2c1`
    - `spi10`
    - `adc0`
    - `pwm1`
- 所有 `rt_device_find()` 结果必须判空。
- 所有缓冲区操作必须检查长度。
- 设备初始化失败时必须返回错误，不允许假启动。
- 日志输出必须包含设备名、错误码和上下文。
- 量产版本关闭不必要的高频 debug 日志。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：设备注册后未设置 `ops`

### 错误代码

```
static struct rt_device dev;

rt_device_register(&dev, "mydev", RT_DEVICE_FLAG_RDWR);
```

### 根因

设备对象没有操作函数表，调用 `rt_device_open()` 或 `read()` 时可能触发空指针。

### 正确实现

```
static const struct rt_device_ops ops =
{
    .init = my_init,
    .open = my_open,
    .close = my_close,
    .read = my_read,
    .write = my_write,
    .control = my_control,
};

dev.ops = &ops;
dev.type = RT_Device_Class_Char;
rt_device_register(&dev, "mydev", RT_DEVICE_FLAG_RDWR);
```

### 风险影响

- HardFault。
- 设备初始化成功但运行时崩溃。
- 问题通常只在第一次访问时暴露。

## 9.2 错误二：在 ISR 中调用阻塞 API

### 错误代码

```
void uart_irq_handler(void)
{
    rt_mutex_take(lock, RT_WAITING_FOREVER);
    rt_device_write(dev, 0, data, len);
    rt_mutex_release(lock);
}
```

### 根因

中断上下文没有线程阻塞语义，可能导致死锁或内核断言。

### 正确实现

```
void uart_irq_handler(void)
{
    ringbuf_put_isr(&rx_rb, data);
    rt_sem_release(rx_sem);
}
```

由线程完成后续处理。

### 风险影响

- 系统死锁。
- 中断嵌套异常。
- 高优先级任务永久阻塞。

## 9.3 错误三：DMA 缓冲区位于不可访问区域

### 错误代码

```
static rt_uint8_t rx_buf[1024];
/* 某些带 DTCM 的 MCU 上，DMA 无法访问该区域 */
```

### 根因

部分 DMA 控制器无法访问 DTCM、某些 SRAM 区域或外部存储器。

### 正确实现

```
#if defined(__GNUC__)
__attribute__((section(".dma_buffer"), aligned(32)))
#endif
static rt_uint8_t rx_buf[1024];
```

并在链接脚本中将 `.dma_buffer` 放入 DMA 可访问 SRAM。

### 风险影响

- DMA 完成中断不触发。
- 接收数据全为旧值。
- 问题具有平台相关性。

## 9.4 错误四：未处理 D-Cache 一致性

### 错误代码

```
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, len);
```

### 根因

地址和长度未按 Cache Line 对齐，可能造成相邻数据被错误失效。

### 正确实现

```
#define CACHE_LINE_SIZE 32

static void cache_invalidate_buffer(void *addr, rt_size_t len)
{
    uintptr_t start;
    uintptr_t end;

    start = (uintptr_t)addr & ~(CACHE_LINE_SIZE - 1);
    end = ((uintptr_t)addr + len + CACHE_LINE_SIZE - 1)
          & ~(CACHE_LINE_SIZE - 1);

    SCB_InvalidateDCache_by_Addr(
        (uint32_t *)start,
        (int32_t)(end - start));
}
```

### 风险影响

- DMA 数据与 CPU 读取结果不一致。
- 偶现协议校验失败。
- 高温、高负载时故障概率升高。

## 9.5 错误五：设备名冲突

### 错误代码

```
rt_device_register(&dev1, "i2c1", ...);
rt_device_register(&dev2, "i2c1", ...);
```

### 根因

多个 BSP 模块重复注册相同设备名，后注册设备可能失败或产生查找歧义。

### 正确实现

- 统一设备命名表。
- 注册返回值必须检查。
- 构建阶段禁止重复设备实例。

```
rt_err_t ret;

ret = rt_device_register(&dev1, "i2c1", RT_DEVICE_FLAG_RDWR);
if (ret != RT_EOK)
{
    LOG_E("register i2c1 failed: %d", ret);
    return ret;
}
```

### 风险影响

- 应用访问错误的物理设备。
- 初始化顺序变化后产生非确定性故障。

---

# 10. 多机制组合使用方案

## 10.1 UART DMA 环形接收架构

```
UART 外设
   ↓
DMA 环形缓冲区
   ↓
DMA 半传输/全传输/空闲线中断
   ↓
ISR 更新写指针
   ↓
信号量通知协议线程
   ↓
软件环形缓冲区
   ↓
协议状态机
```

## 10.2 完整代码框架

```
struct uart_stream
{
    struct rt_device *dev;

    rt_uint8_t *dma_buf;
    rt_size_t dma_size;

    volatile rt_size_t dma_last_pos;
    struct ringbuf rb;

    struct rt_sem rx_sem;
    struct rt_mutex tx_lock;

    rt_uint32_t overflow_count;
    rt_uint32_t frame_error_count;
};

static void uart_dma_idle_callback(struct uart_stream *stream)
{
    rt_size_t current;
    rt_size_t length;

    current = uart_dma_get_position(stream->dev);

    if (current >= stream->dma_last_pos)
    {
        length = current - stream->dma_last_pos;
        ringbuf_write(
            &stream->rb,
            &stream->dma_buf[stream->dma_last_pos],
            length);
    }
    else
    {
        length = stream->dma_size - stream->dma_last_pos;

        ringbuf_write(
            &stream->rb,
            &stream->dma_buf[stream->dma_last_pos],
            length);

        ringbuf_write(
            &stream->rb,
            &stream->dma_buf[0],
            current);
    }

    stream->dma_last_pos = current;

    if (rt_sem_get_value(&stream->rx_sem) < 1)
        rt_sem_release(&stream->rx_sem);
}

static rt_ssize_t uart_stream_send(
    struct uart_stream *stream,
    const void *data,
    rt_size_t len,
    rt_int32_t timeout)
{
    rt_ssize_t result;

    if ((stream == RT_NULL) || (data == RT_NULL) || len == 0)
        return -RT_EINVAL;

    if (rt_mutex_take(&stream->tx_lock, timeout) != RT_EOK)
        return -RT_ETIMEOUT;

    result = rt_device_write(stream->dev, 0, data, len);

    rt_mutex_release(&stream->tx_lock);

    return result;
}
```

### 组合中的关键点

- DMA 负责搬运。
- ISR 只更新指针和通知。
- 软件环形缓冲区负责解耦 DMA 与协议线程。
- 发送方向使用互斥锁，防止多个线程交错发送。
- 接收方向使用信号量，不使用轮询。
- 缓冲区满时必须有明确策略：
    - 丢弃新数据
    - 覆盖旧数据
    - 丢弃完整帧
    - 触发流控

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业网关 UART 升级通道

### 需求

- 波特率：921600 bps。
- 固件包大小：1~4 MB。
- 不能因日志线程导致丢包。
- 支持 CRC、超时、断点续传。
- CPU 占用低于 10%。

### 架构

```
UART DMA 环形接收
    ↓
接收线程
    ↓
协议状态机
    ↓
CRC 校验
    ↓
Flash 写入线程
    ↓
FAL/Flash 驱动
```

### 设计要点

- DMA 接收缓冲区至少 2 KB。
- 协议解析和 Flash 擦写分离。
- Flash 擦除期间不能阻塞 UART 接收线程。
- 采用双缓冲或消息队列交接数据。
- 每个数据包包含：
    - magic
    - version
    - sequence
    - payload length
    - payload
    - CRC32

### 关键代码框架

```
struct upgrade_packet
{
    rt_uint32_t magic;
    rt_uint32_t sequence;
    rt_uint16_t length;
    rt_uint8_t payload[1024];
    rt_uint32_t crc32;
};

static void upgrade_thread(void *parameter)
{
    struct upgrade_ctx *ctx = parameter;
    struct upgrade_packet packet;

    while (1)
    {
        if (rt_mq_recv(&ctx->packet_mq,
                       &packet,
                       sizeof(packet),
                       rt_tick_from_millisecond(1000)) != RT_EOK)
        {
            continue;
        }

        if (crc32_check(&packet) != RT_EOK)
        {
            ctx->crc_error++;
            continue;
        }

        if (flash_write_chunk(
                ctx->write_address,
                packet.payload,
                packet.length) != RT_EOK)
        {
            ctx->flash_error++;
            upgrade_abort(ctx);
            continue;
        }

        ctx->write_address += packet.length;
        upgrade_send_ack(packet.sequence);
    }
}
```

## 11.2 案例二：多传感器 I2C 采集板

### 需求

- 一条 400 kHz I2C 总线。
- 连接温度、压力、加速度传感器。
- 某个传感器异常不能拖死整条总线。
- 采集周期 10 ms。
- 设备可能热插拔或掉电。

### 架构

```
I2C 控制器驱动
    ↓
RT-Thread I2C 总线
    ↓
温度设备驱动
压力设备驱动
加速度设备驱动
    ↓
传感器采集线程
    ↓
数据融合线程
```

### 设计要点

- 每个设备访问设置独立超时。
- 失败后最多重试 2~3 次。
- 多次失败触发设备复位或总线恢复。
- 采集线程不能无限等待 I2C。
- 传感器驱动只负责寄存器协议，不负责业务融合。

## 11.3 案例三：SPI NOR Flash 文件系统

### 需求

- SPI 频率 40 MHz。
- 使用 FAL 分区。
- 上层挂载 LittleFS。
- 支持掉电保护和磨损均衡。

### 架构

```
SPI 控制器驱动
    ↓
SPI NOR Flash 驱动
    ↓
FAL
    ↓
LittleFS
    ↓
配置/日志服务
```

### 设计要点

- 读、页编程、块擦除必须分离。
- 编程前检查页边界。
- 擦除时间可能达到数十到数百毫秒。
- 擦除期间不要阻塞高优先级业务线程。
- 写入完成必须轮询 WIP 位并带超时。
- 断电保护需要：
    - 元数据冗余
    - CRC
    - 事务提交标记
    - 版本号或序列号

---

# 12. 高频问题深度答疑

## 问题三：为什么 UART 中断接收仍然会丢数据？

常见原因：

1. 接收缓冲区容量不足。
2. ISR 处理时间过长。
3. 接收线程优先级过低。
4. 系统长时间关闭中断。
5. 环形缓冲区读写指针并发访问不安全。
6. DMA 与 CPU 之间存在 Cache 不一致。
7. DMA 计数器回绕处理错误。
8. 协议线程被 Flash 擦除、日志输出等操作长时间阻塞。

#### 根本分析

UART 接收数据的本质是生产者-消费者模型：

```
UART/DMA/ISR：生产者
协议线程：消费者
```

如果生产速率大于消费速率，缓冲区最终一定溢出。

缓冲区容量至少满足：

```
BufferSize ≥ InputRate × MaxBlockTime × SafetyFactor
```

例如：

```
波特率：921600 bps
8N1 有效字节率：92160 Byte/s
协议线程最大阻塞时间：10 ms
安全系数：2

BufferSize ≥ 92160 × 0.01 × 2
            ≥ 1843 Byte
```

因此应选择 **2048 Byte 或更大**的环形缓冲区。

#### 错误实现

```
void UART_IRQHandler(void)
{
    rt_uint8_t ch;

    ch = UART->RDR;

    /* ISR 中直接做复杂协议解析 */
    protocol_parse_byte(ch);

    /* ISR 中打印日志 */
    rt_kprintf("rx=%02x\n", ch);
}
```

问题包括：

- 单字节中断开销大。
- `protocol_parse_byte()` 的执行时间不可控。
- `rt_kprintf()` 可能阻塞。
- 高速串口下容易造成下一个字节未及时读取。

#### 正确实现

```
void UART_IRQHandler(void)
{
    rt_uint8_t ch;

    while (UART_RX_READY())
    {
        ch = UART_READ_DATA();

        if (ringbuf_put_isr(&uart_ctx.rx_rb, ch) != 0)
        {
            uart_ctx.rx_overflow++;
        }
    }

    rt_sem_release(&uart_ctx.rx_sem);
}
```

协议线程中再解析：

```
static void uart_protocol_thread(void *parameter)
{
    struct uart_context *ctx = parameter;
    rt_uint8_t buf[128];
    rt_size_t len;

    while (1)
    {
        rt_sem_take(&ctx->rx_sem, RT_WAITING_FOREVER);

        while (ringbuf_data_len(&ctx->rx_rb) > 0)
        {
            len = ringbuf_get(&ctx->rx_rb, buf, sizeof(buf));

            if (len > 0)
            {
                protocol_input(ctx, buf, len);
            }
        }
    }
}
```

#### 工业级排查顺序

```
是否产生 UART 硬件错误？
├── 是 → 检查波特率、时钟、线路、电平、FIFO
└── 否
    ├── 是否发生软件缓冲区溢出？
    │   └── 增大缓冲区或提高消费者处理能力
    ├── ISR 是否过长？
    │   └── 统计 ISR 最大执行时间
    ├── 是否长时间关中断？
    │   └── 检查临界区、Flash 操作、日志输出
    ├── DMA 是否存在 Cache 问题？
    │   └── 检查内存区域和 Cache 维护
    └── DMA 回绕位置是否正确？
        └── 对比 DMA 当前计数器和软件读写指针
```

---

## 问题四：为什么 I2C 设备偶尔会把整条总线拖死？

#### 常见现象

- `SCL` 或 `SDA` 长时间为低电平。
- 后续所有设备访问均失败。
- I2C 状态机卡在 BUSY。
- 软件复位 I2C 外设无效。
- 重新上电后恢复。

#### 根因

I2C 是开漏总线，任何设备都可以主动拉低总线。

典型故障流程：

```
主机发送 START
    ↓
从机开始发送数据
    ↓
从机异常复位或主机复位
    ↓
从机仍认为当前事务未完成
    ↓
从机持续拉低 SDA
    ↓
主机无法生成新的 START
```

还有一种情况是从机在时钟延展阶段拉低 SCL，但主机没有正确处理超时。

#### 错误实现

```
while (I2C->SR2 & I2C_BUSY)
{
    /* 无限等待 */
}
```

风险：

- 一个传感器异常会阻塞整个系统。
- 高优先级线程永久占用 CPU。
- 看门狗可能复位系统。
- 总线故障无法自动恢复。

#### 正确策略

必须同时具备：

1. 传输超时。
2. 总线状态检测。
3. I2C 外设复位。
4. GPIO 模式下的 9 脉冲恢复。
5. STOP 条件生成。
6. 设备重新探测。
7. 错误计数和故障上报。

```
static rt_err_t i2c_transfer_with_recovery(
    struct rt_i2c_bus_device *bus,
    struct rt_i2c_msg *msgs,
    rt_uint32_t num)
{
    rt_err_t ret;
    int retry;

    for (retry = 0; retry < 3; retry++)
    {
        ret = rt_i2c_transfer(bus, msgs, num);

        if (ret == (rt_err_t)num)
        {
            return RT_EOK;
        }

        if (i2c_bus_is_stuck())
        {
            i2c_bus_recover();
        }

        i2c_controller_reset();
    }

    return -RT_ETIMEOUT;
}
```

#### 设计权衡

|策略|优点|缺点|
|---|---|---|
|只增加超时|实现简单|不能恢复总线|
|仅复位 I2C 外设|代码简单|从机仍可能拉低 SDA|
|GPIO 9 脉冲恢复|恢复能力强|需要额外 GPIO 控制|
|复位从设备|最彻底|需要硬件复位引脚|
|整板复位|简单粗暴|业务中断严重|

工业产品推荐：

```
超时
 → I2C 外设复位
 → GPIO 总线恢复
 → 从设备复位
 → 设备重新初始化
 → 仍失败则上报不可用
```

---

## 问题五：RT-Thread 设备初始化顺序错误，应该如何定位？

#### 典型现象

- `rt_device_find("i2c1")` 返回空指针。
- 传感器初始化失败，但 I2C 驱动后来又正常。
- 文件系统挂载失败，但 Flash 驱动启动后可用。
- 同一份代码偶尔启动成功、偶尔失败。
- 修改日志打印后故障消失。

#### 根因

RT-Thread 初始化机制依赖初始化等级和链接段顺序。应用层初始化函数可能在底层设备注册之前执行。

错误依赖关系：

```
sensor_init()
    ↓
rt_device_find("i2c1")
```

但实际启动顺序为：

```
sensor_init()
    ↓
i2c_bus_init()
```

于是传感器找不到 I2C 总线。

#### 错误代码

```
INIT_APP_EXPORT(sensor_init);
INIT_DEVICE_EXPORT(i2c_bus_init);
```

应用初始化优先于设备初始化。

#### 正确实现

```
INIT_DEVICE_EXPORT(i2c_bus_init);
INIT_COMPONENT_EXPORT(sensor_init);
```

或者显式拆分：

```
static int sensor_register(void)
{
    sensor_bus = rt_device_find("i2c1");

    if (sensor_bus == RT_NULL)
    {
        LOG_E("i2c1 not found");
        return -RT_ENODEV;
    }

    return sensor_hw_init();
}

INIT_COMPONENT_EXPORT(sensor_register);
```

#### 推荐排查方法

在每个初始化函数中输出：

```
LOG_I("init: %s", __func__);
```

记录实际顺序：

```
init: board_init
init: uart_init
init: i2c_bus_init
init: spi_flash_init
init: sensor_init
init: filesystem_init
init: application_init
```

同时检查：

- 初始化宏等级。
- `Kconfig` 是否打开对应驱动。
- `SConscript` 是否将源文件加入编译。
- 驱动是否被链接器垃圾回收。
- 设备注册返回值。
- 设备名是否拼写一致。
- 是否存在多个同名设备。

#### 工业级建议

不要仅依赖隐式初始化顺序。对于关键设备，应显式检查依赖：

```
static int filesystem_init(void)
{
    rt_device_t flash;

    flash = rt_device_find("norflash0");
    if (flash == RT_NULL)
    {
        LOG_E("norflash0 is unavailable");
        return -RT_ENODEV;
    }

    return fal_init();
}
```

初始化失败必须可观察、可统计、可降级，不能静默跳过。

---

## 问题六：设备驱动是否应该在每次访问时加互斥锁？

答案不是简单的“应该”或“不应该”，要区分设备资源和访问上下文。

#### 需要加锁的场景

- 多线程访问同一个 UART。
- 多个线程共享同一条 I2C 总线。
- 多个线程访问同一个 SPI 设备。
- 设备操作包含多个不可分割步骤。
- 设备有共享状态机或共享缓冲区。
- 设备读写操作会修改寄存器配置。

#### 不一定需要锁的场景

- 设备只由单一线程访问。
- 访问接口本身已由总线框架串行化。
- 仅访问原子状态变量。
- ISR 与线程之间只通过无锁环形缓冲区交互。
- 设备硬件本身支持独立通道。

#### 错误实现

```
rt_mutex_take(&lock, RT_WAITING_FOREVER);

spi_write_command();
spi_write_address();
spi_write_data();

rt_mutex_release(&lock);
```

问题是：

- 可能无限阻塞。
- 设备异常时锁无法及时释放。
- 高优先级线程可能被低优先级线程长期占用。

#### 正确实现

```
if (rt_mutex_take(&lock, rt_tick_from_millisecond(100))
    != RT_EOK)
{
    return -RT_ETIMEOUT;
}

ret = spi_write_command();
if (ret != RT_EOK)
{
    goto exit;
}

ret = spi_write_address();
if (ret != RT_EOK)
{
    goto exit;
}

ret = spi_write_data();

exit:
rt_mutex_release(&lock);
return ret;
```

#### 注意优先级反转

假设：

```
低优先级线程 L 持有 SPI 锁
高优先级线程 H 等待 SPI 锁
中优先级线程 M 持续运行
```

如果没有优先级继承：

```
H 等待 L
L 被 M 抢占
M 持续运行
H 长时间无法运行
```

RT-Thread 互斥锁应优先使用具备优先级继承语义的机制，不要使用普通信号量代替互斥锁保护共享资源。

---

## 问题七：为什么驱动中不能随意使用动态内存？

#### 风险来源

驱动通常具有以下特性：

- 启动阶段调用。
- 中断和线程并发调用。
- 长时间运行。
- 资源释放路径复杂。
- 对实时性敏感。

频繁动态内存分配可能造成：

- 堆碎片。
- 分配时延不确定。
- 内存泄漏。
- 错误路径释放遗漏。
- 低内存下设备部分初始化。

#### 错误实现

```
rt_uint8_t *buf;

buf = rt_malloc(size);
if (buf == RT_NULL)
{
    return -RT_ENOMEM;
}

rt_device_read(dev, 0, buf, size);

/* 某个错误分支忘记释放 */
if (check_data(buf) != RT_EOK)
{
    return -RT_ERROR;
}

rt_free(buf);
```

#### 正确实现一：静态缓冲区

```
#define SENSOR_FRAME_MAX 128

static rt_uint8_t sensor_frame[SENSOR_FRAME_MAX];
static struct rt_mutex sensor_lock;
```

适合：

- 固定大小数据。
- 单实例设备。
- 长期运行的嵌入式系统。

#### 正确实现二：初始化阶段一次性分配

```
ctx->rx_buf = rt_malloc(RX_BUF_SIZE);
if (ctx->rx_buf == RT_NULL)
{
    return -RT_ENOMEM;
}

ret = rt_device_open(dev, flags);
if (ret != RT_EOK)
{
    rt_free(ctx->rx_buf);
    ctx->rx_buf = RT_NULL;
    return ret;
}
```

#### 正确实现三：内存池

对于固定大小、频繁申请释放的消息对象，使用内存池：

```
static struct rt_mempool packet_pool;
static rt_uint8_t packet_pool_mem[16 * 128];

static int packet_pool_init(void)
{
    return rt_mp_init(&packet_pool,
                      "pkt",
                      packet_pool_mem,
                      sizeof(packet_pool_mem),
                      128);
}
```

分配：

```
void *packet = rt_mp_alloc(&packet_pool, rt_tick_from_millisecond(10));
if (packet == RT_NULL)
{
    return -RT_ENOMEM;
}
```

释放：

```
rt_mp_free(packet);
```

#### 选型建议

|场景|推荐|
|---|---|
|固定大小长期缓存|静态数组|
|初始化后不释放|初始化阶段动态分配|
|高频固定块消息|内存池|
|大小变化且低频|动态堆，但必须完整释放|
|ISR|禁止动态分配|
|安全关键路径|静态分配或内存池|

---

## 问题八：BSP 应该直接依赖 HAL，还是直接操作寄存器？

#### HAL 方案

```
HAL_UART_Transmit(&huart1, data, len, timeout);
```

优点：

- 开发快。
- 芯片厂商维护。
- 兼容多个同系列型号。
- 初期验证成本低。

缺点：

- 时延不透明。
- 状态机较重。
- 错误恢复行为可能不符合需求。
- HAL 版本升级可能引入行为变化。

#### 寄存器方案

```
while (!(USART1->ISR & USART_ISR_TXE))
{
    if (timeout_expired())
        return -RT_ETIMEOUT;
}

USART1->TDR = ch;
```

优点：

- 控制精确。
- 性能高。
- 可实现特殊时序。
- 更容易保证确定性。

缺点：

- 芯片强相关。
- 维护成本高。
- 容易遗漏边界条件。
- 对参考手册依赖强。

#### 推荐的混合策略

```
普通外设初始化 → HAL/LL
高频数据路径 → LL/寄存器
复杂错误恢复 → 寄存器直接控制
设备框架接口 → RT-Thread 统一封装
```

例如 UART：

```
初始化：
    HAL/LL 配置 GPIO、时钟、中断、DMA

发送数据：
    RT-Thread 设备接口

DMA 状态读取：
    直接读取 DMA 当前计数器

错误清除：
    根据参考手册直接操作状态寄存器
```

**关键不是 HAL 还是寄存器，而是边界是否清晰。**

推荐架构：

```
RT-Thread 设备接口
        ↓
BSP 适配层
        ↓
硬件抽象层
        ↓
HAL/LL/寄存器
```

不要让同一个函数同时混合：

- 应用协议解析；
- RT-Thread 设备注册；
- HAL 初始化；
- 直接操作业务 GPIO；
- 错误恢复；
- 日志输出。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **BSP 的职责是提供稳定的板级硬件抽象，而不是简单包装 HAL。**
2. **RT-Thread 设备框架通过统一命名、生命周期和访问接口实现驱动与应用解耦。**
3. **中断上下文只能做快速、确定、不可阻塞的工作。**
4. **UART 高吞吐场景应优先采用 DMA、环形缓冲和线程化协议解析。**
5. **I2C 驱动必须包含超时、重试和总线恢复机制。**
6. **SPI 驱动必须保证事务期间 CS、时钟模式和 DMA 缓冲区正确。**
7. **所有硬件等待必须有超时，所有设备注册必须检查返回值。**
8. **设备初始化必须明确依赖关系，不能依赖偶然的链接顺序。**
9. **共享设备资源使用互斥锁，线程通知使用信号量或事件。**
10. **DMA 场景必须验证内存区域、地址对齐和 Cache 一致性。**

## 13.2 性能排序

### CPU 占用

```
轮询 > 单字节中断 > 批量中断 > DMA > DMA 环形/双缓冲
```

### 实现复杂度

```
轮询 < 中断 < 普通 DMA < 环形 DMA < 双缓冲状态机
```

### 实时确定性

```
直接寄存器状态机 > LL > 中断驱动 > HAL 阻塞接口
```

### 通用可移植性

```
应用直连寄存器 < HAL 直连应用 < BSP 封装 HAL < RT-Thread 设备框架
```

## 13.3 通用选型结论

- **低速、低复杂度设备**：轮询或阻塞式 HAL。
- **普通串口和控制设备**：中断 + 环形缓冲。
- **高速连续数据流**：DMA + 环形缓冲或双缓冲。
- **共享 I2C/SPI 总线**：总线设备框架 + 从设备驱动。
- **复杂产品**：RT-Thread 设备框架、组件、Kconfig、自动初始化和故障恢复必须完整结合。
- **强实时路径**：RT-Thread 接口负责上层抽象，底层使用 LL 或寄存器优化。

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐实现|
|---|---|
|调试串口|中断接收 + 环形缓冲|
|高速 UART|DMA 环形接收 + 空闲线中断|
|单个低速传感器|I2C 设备驱动|
|多个 I2C 设备|I2C 总线框架|
|SPI Flash|SPI 设备 + FAL|
|LCD|SPI 设备 + 显示驱动|
|ADC 连续采样|DMA 双缓冲|
|GPIO 按键|GPIO 中断 + 消抖线程|
|PWM 输出|PWM 设备框架|
|关键设备故障恢复|超时 + 重试 + 复位 + 状态上报|

## 14.2 驱动接口检查表

|检查项|要求|
|---|---|
|设备注册|检查返回值|
|设备查找|检查空指针|
|`ops`|所需操作函数完整|
|参数|检查空指针和长度|
|超时|所有等待均有上限|
|锁|明确锁的范围和上下文|
|ISR|不阻塞、不分配、不打印大量日志|
|DMA|检查内存区域、对齐、Cache|
|错误|记录错误码、计数和恢复动作|
|资源释放|所有失败路径释放资源|
|初始化|依赖顺序明确|
|设备命名|全局唯一|

---

# 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  BSP 与 HAL、RT-Thread 设备框架、应用层的边界是什么？
- [ ]  `rt_device_register()` 的主要职责是什么？
- [ ]  `rt_device_ops` 中每个回调的调用时机是什么？
- [ ]  为什么不能在 ISR 中调用阻塞式互斥锁？
- [ ]  UART 环形缓冲区容量如何计算？
- [ ]  DMA 环形接收如何处理回绕？
- [ ]  I2C 总线被 SDA 拉低时如何恢复？
- [ ]  SPI 设备如何保证 CS 在完整事务期间有效？
- [ ]  为什么设备初始化会出现顺序问题？
- [ ]  什么时候使用互斥锁，什么时候使用信号量？
- [ ]  DMA 和 D-Cache 不一致如何解决？
- [ ]  如何设计一个支持超时、重试和复位的驱动？
- [ ]  如何判断驱动应该使用 HAL、LL 还是寄存器？
- [ ]  如何通过 map 文件确认驱动是否被链接进最终镜像？
- [ ]  如何测量 ISR 最大执行时间和线程响应延迟？

建议以以下实战题作为通过标准：

```
1. 编写一个自定义 rt_device 字符设备。
2. 为 UART 增加中断环形接收。
3. 将 UART 改造成 DMA 环形接收。
4. 编写一个 I2C 传感器设备驱动。
5. 实现 I2C 总线卡死恢复。
6. 为 SPI Flash 接入 FAL。
7. 添加设备统计信息和故障恢复机制。
8. 使用逻辑分析仪验证真实时序。
```

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 阶段一：基础设备注册

目标：

- 注册自定义字符设备。
- 实现 `open/read/write/control`。
- 通过 FinSH 访问设备。
- 验证设备名、设备标志和错误码。

验收指标：

```
设备可查找
设备可打开
非法参数可拒绝
不支持的命令返回 -RT_ENOSYS
```

### 阶段二：UART 中断驱动

目标：

- 实现 UART 接收中断。
- 使用环形缓冲区缓存数据。
- 使用信号量通知接收线程。
- 统计溢出次数和硬件错误次数。

验收指标：

```
115200 bps 连续接收 10 分钟无丢包
缓冲区溢出可检测
ISR 平均耗时和最大耗时可测量
```

### 阶段三：UART DMA 环形驱动

目标：

- 实现 DMA 环形接收。
- 支持空闲线检测。
- 处理 DMA 回绕。
- 适配 D-Cache。
- 评估 CPU 占用变化。

验收指标：

```
921600 bps 连续接收无丢包
CPU 占用低于中断逐字节方案
DMA 回绕测试通过
Cache 开启和关闭结果一致
```

### 阶段四：I2C 总线与传感器框架

目标：

- 实现 I2C 总线访问。
- 注册一个温度或加速度传感器。
- 实现寄存器读写。
- 增加重试和超时。
- 注入 SDA 卡低故障并恢复。

验收指标：

```
设备掉线可检测
单次访问有明确超时
总线卡死可自动恢复
设备恢复后可继续采集
```

### 阶段五：SPI Flash + FAL

目标：

- 适配 SPI NOR Flash。
- 实现 JEDEC ID 读取。
- 实现页编程、扇区擦除和状态轮询。
- 接入 FAL。
- 挂载 LittleFS 或其他文件系统。

验收指标：

```
读写校验正确
页边界处理正确
掉电测试后文件系统可恢复
擦除超时不会永久阻塞线程
```

## 16.2 性能测试方法

### ISR 延迟测试

使用 GPIO 翻转：

```
void UART_IRQHandler(void)
{
    TEST_GPIO_SET();

    uart_isr_handler();

    TEST_GPIO_RESET();
}
```

用逻辑分析仪测量：

```
ISR 执行时间 = GPIO 脉冲宽度
```

必须记录：

- 平均值。
- 最大值。
- 最小值。
- 中断嵌套情况下的最大值。

### 线程响应测试

```
rt_tick_t start;
rt_tick_t end;

start = rt_tick_get();
rt_sem_release(&rx_sem);

/* 在接收线程中 */
end = rt_tick_get();

latency = end - start;
```

建议结合硬件 GPIO 记录亚 tick 级延迟。

### DMA 吞吐测试

测试至少包括：

- 低速、小包。
- 高速、大包。
- 缓冲区回绕。
- CPU 高负载。
- Cache 开启。
- Flash 擦写并发。
- 多线程同时访问。

### 故障注入测试

必须主动测试：

```
UART 帧错误
UART 溢出
I2C SDA 拉低
I2C SCL 拉低
SPI Flash 忙状态超时
DMA 传输错误
设备热插拔
设备复位
线程异常退出
内存不足
```

## 16.3 进阶学习方向

### RT-Thread 内核方向

- 设备模型源码。
- 自动初始化链接段。
- 调度器与中断退出调度。
- 互斥锁优先级继承。
- IPC 对象实现。
- 内存堆与内存池。
- SMP 下设备驱动并发安全。

### MCU 底层方向

- DMA 请求映射。
- FIFO 和突发传输。
- D-Cache 一致性。
- MPU 内存属性。
- 中断优先级分组。
- 低功耗唤醒。
- 时钟切换期间的外设时序。

### 工程化方向

- Kconfig 驱动裁剪。
- SCons 多板卡构建。
- CI 自动编译多个 BSP。
- 静态分析和 MISRA-C。
- 单元测试与硬件在环测试。
- 故障注入和长期稳定性测试。
- 驱动 API 版本管理。

最终应达到的工程能力是：

```
能够从一块新硬件板卡出发，
完成启动、时钟、引脚、外设、RT-Thread 设备框架、
DMA、缓存一致性、故障恢复、组件接入和自动化测试，
并交付一个可维护、可量产、可验证的 BSP。
```