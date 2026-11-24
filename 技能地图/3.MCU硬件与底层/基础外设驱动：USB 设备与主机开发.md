​
## 1. 学习目标

### 理解

- 理解 USB 2.0 总线拓扑、主机调度、设备枚举和端点通信模型。
- 理解 USB 设备控制器、USB 主机控制器、PHY、FIFO、DMA、Endpoint、Transfer 的硬件关系。
- 理解控制传输、批量传输、中断传输、同步传输的协议语义与适用边界。
- 理解设备描述符、配置描述符、接口描述符、端点描述符和字符串描述符之间的层级关系。

### 掌握

- 掌握 USB 设备枚举完整状态机。
- 掌握 USB Device、USB Host、USB OTG 三类控制器的软件架构。
- 掌握 USB CDC、HID、MSC 等常见类设备的驱动开发方式。
- 掌握 Host 侧设备发现、地址分配、配置选择、类驱动绑定和数据传输。
- 掌握端点 FIFO、DMA、双缓冲、NAK、STALL、超时和错误重试机制。

### 精通

- 能够定位枚举失败、数据丢失、偶发 CRC 错误、传输超时、端点卡死等现场问题。
- 能够结合 USB Analyzer、示波器、逻辑分析仪、内核日志和寄存器状态完成问题闭环。
- 能够设计支持低功耗、缓存一致性、并发访问和异常恢复的工业级 USB 驱动。
- 能够分析 USB 协议栈的 CPU、RAM、延迟和吞吐量开销。

### 能够设计

- 能够独立设计 MCU USB Device 固件架构。
- 能够设计带 Hub、类驱动、热插拔和错误恢复能力的 USB Host 软件架构。
- 能够设计 USB 与 RTOS、DMA、缓存、文件系统、网络协议栈协同的完整系统。
- 能够根据带宽、实时性、功耗、复杂度和认证要求完成 USB 方案选型。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、结构体、位操作、内存屏障和中断编程。
- 理解 MCU 时钟树、NVIC、DMA、FIFO、Cache 和内存映射寄存器。
- 熟悉 UART、SPI、I2C 等基础外设驱动开发。
- 理解 TCP/IP 分层模型和客户端/服务端通信模型。
- 熟悉一种 RTOS，至少理解任务、队列、信号量、事件和临界区。
- 了解 USB 2.0 基本术语：Host、Device、Hub、Endpoint、Pipe、Token、Data、Handshake。

### 技能要求

- 能够阅读 MCU Reference Manual 中 USB OTG、USB Device、USB Host 章节。
- 能够使用示波器、逻辑分析仪和 USB 抓包工具。
- 能够配置链接脚本、DMA 缓冲区和 Cache 属性。
- 能够编译、下载并调试中断驱动代码。
- 能够阅读 USB 描述符和十六进制抓包数据。
- 建议拥有一块支持 USB FS 或 HS 的 MCU 开发板，以及一个 USB Protocol Analyzer。

---

## 3. 技术概述

### 3.1 USB 的核心定义

USB 是一种由主机统一调度的串行总线协议。其核心特点是：

1. **总线控制权属于 Host**
2. **Device 不主动发起总线事务**
3. **所有数据传输都以 Endpoint 为逻辑终点**
4. **Host 通过枚举发现和配置 Device**
5. **带宽由 Host Frame/SOF 调度**
6. **数据可靠性主要由协议层 CRC、握手和重试保证**

USB 不是点对点协议。即使是一个设备到主机的数据传输，也必须表现为：

```
Host 发起 IN Token
Device 返回 DATA
Host 返回 ACK
```

设备端只能在 Host 发出 IN Token 后返回数据。

### 3.2 USB 2.0 速率分类

|模式|标称速率|常见 MCU 场景|最大包大小|
|---|---|---|---|
|Low Speed|1.5 Mbps|鼠标、键盘|8 Bytes|
|Full Speed|12 Mbps|CDC、HID、MSC、工业控制|控制端点最大 64 Bytes|
|High Speed|480 Mbps|摄像头、存储、网卡|高速 Bulk 可达 512 Bytes|
|SuperSpeed|5 Gbps 及以上|USB 3.x 设备|不属于传统 USB 2.0 控制器范围|

**USB FS 的 12 Mbps 是线路速率，不是应用层吞吐量。**

典型 USB FS Bulk 实际有效吞吐量通常约为：

- 裸包理论上限：约 1 MB/s
- 设备端实际吞吐：约 700～900 KB/s
- 加入 RTOS、DMA、应用拷贝和协议头后：约 400～800 KB/s

### 3.3 USB 事务与传输层级

```
Transfer
  └── Transaction
        └── Packet
              └── Token / Data / Handshake
```

例如一次 Bulk IN 传输：

```
IN Token -> DATA0/DATA1 -> ACK
```

控制传输通常包含三个阶段：

```
SETUP Stage -> DATA Stage -> STATUS Stage
```

### 3.4 USB 端点模型

Endpoint 由以下因素共同标识：

```
Endpoint Address = Direction + Endpoint Number
```

例如：

```
0x81 = Endpoint 1 IN
0x02 = Endpoint 2 OUT
```

注意：

- Endpoint 0 是所有 USB Device 必须实现的控制端点。
- Endpoint 0 同时支持 IN 和 OUT。
- Endpoint 0 的最大包长在 USB FS 中一般为 8、16、32 或 64 Bytes。
- 非 0 端点必须通过 Configuration Descriptor 声明。

### 3.5 USB 设备类

常见类协议：

|类|典型设备|应用层接口|
|---|---|---|
|CDC ACM|虚拟串口|COM/TTY|
|HID|键盘、鼠标、遥控器|报告描述符|
|MSC|U 盘、读卡器|SCSI over Bulk|
|Audio|声卡、麦克风|等时传输|
|DFU|固件升级|控制传输|
|CDC ECM/NCM|USB 网卡|网络接口|
|Vendor Specific|自定义工业设备|自定义协议|

---

## 4. 核心特性横向对比

### 4.1 四类 USB 传输方式

|维度|Control|Bulk|Interrupt|Isochronous|
|---|---|---|---|---|
|可靠性|高，有握手与重试|高，有握手与重试|高，有握手与重试|不重试|
|实时性|低|不保证|较高|最高|
|带宽保证|否|否|可预留|可预留|
|典型用途|枚举、配置|U 盘、打印机、CDC 数据|HID、状态上报|音频、视频|
|最大包 FS|64 Bytes|64 Bytes|64 Bytes|1023 Bytes|
|错误处理|协议级|自动重试|自动重试|上层处理丢包|
|是否支持数据流|有限|是|有限|是|
|典型延迟|毫秒级|受调度影响|1～数毫秒|固定周期|

### 4.2 Device、Host 和 OTG

|维度|USB Device|USB Host|USB OTG|
|---|---|---|---|
|总线角色|响应 Host|调度总线|可动态切换|
|供电|通常被供电|向外供电|依赖角色|
|主要工作|枚举响应、端点收发|枚举、调度、类驱动|角色检测与切换|
|软件复杂度|中|高|很高|
|RAM 消耗|较低|较高|最高|
|常见应用|MCU 虚拟串口|MCU 读取 U 盘|手机、工业网关|
|关键机制|描述符、端点状态|Pipe、URB、Hub|HNP/SRP、ID/VBUS|

### 4.3 常见 USB 类实现对比

|类|主要端点|设备侧复杂度|主机侧支持|实时性|典型风险|
|---|---|---|---|---|---|
|CDC|Bulk IN/OUT + Interrupt|低|通常成熟|中|粘包、缓存不足|
|HID|Interrupt IN/OUT|低|系统原生支持|高|报告描述符错误|
|MSC|Bulk IN/OUT|中|系统原生支持|低|SCSI、文件系统一致性|
|Audio|Isochronous|高|系统原生支持|高|丢包、时钟漂移|
|DFU|Control|中|工具支持|低|断电恢复、镜像校验|
|Vendor|自定义|低到高|需自研|由设计决定|驱动部署复杂|

---

## 5. 底层原理与功能特性深度解析

## 5.1 USB 设备状态机

USB Device 状态主要包括：

```
Powered
  -> Default
  -> Addressed
  -> Configured
  -> Suspended
```

状态转换：

```
上电                  -> Powered
检测到复位             -> Default
SET_ADDRESS 成功       -> Addressed
SET_CONFIGURATION 成功 -> Configured
总线长时间无活动       -> Suspended
恢复信号               -> 返回原状态
```

关键约束：

- 设备复位后必须使用地址 0。
- Host 通过 `SET_ADDRESS` 分配新地址。
- 设备必须在规定时间内完成控制请求响应。
- 未配置时，非 0 端点通常不能参与正常数据传输。
- Suspend 状态下应降低功耗，但必须保持唤醒能力。

### 生产级状态管理代码

```
typedef enum {
    USB_DEV_DEFAULT = 0,
    USB_DEV_ADDRESSED,
    USB_DEV_CONFIGURED,
    USB_DEV_SUSPENDED,
} usb_dev_state_t;

typedef struct {
    usb_dev_state_t state;
    uint8_t address;
    uint8_t configuration;
    bool remote_wakeup_enabled;
} usb_device_context_t;

static usb_device_context_t g_usb;

void usb_device_reset(void)
{
    usb_hw_disable_non_control_endpoints();
    usb_hw_flush_tx_fifo();
    usb_hw_flush_rx_fifo();

    g_usb.state = USB_DEV_DEFAULT;
    g_usb.address = 0U;
    g_usb.configuration = 0U;
    g_usb.remote_wakeup_enabled = false;

    usb_ep0_init();
}

int usb_device_set_address(uint8_t address)
{
    if (address > 127U) {
        return -EINVAL;
    }

    /*
     * USB 规范要求：SET_ADDRESS 请求完成后才切换地址。
     * 不能在接收 SETUP 包的瞬间立即改地址。
     */
    usb_ep0_status_in();

    usb_hw_set_address(address);

    g_usb.address = address;
    g_usb.state = (address == 0U)
                    ? USB_DEV_DEFAULT
                    : USB_DEV_ADDRESSED;

    return 0;
}
```

## 5.2 控制传输与 SETUP 包

SETUP 包固定为 8 Bytes：

```
typedef struct __attribute__((packed)) {
    uint8_t  bmRequestType;
    uint8_t  bRequest;
    uint16_t wValue;
    uint16_t wIndex;
    uint16_t wLength;
} usb_setup_packet_t;
```

`bmRequestType`：

```
Bit 7     Direction: 0 OUT, 1 IN
Bits 6:5  Type: Standard, Class, Vendor
Bits 4:0  Recipient: Device, Interface, Endpoint, Other
```

典型标准请求：

|请求|作用|
|---|---|
|GET_STATUS|查询状态|
|CLEAR_FEATURE|清除特性|
|SET_FEATURE|设置特性|
|SET_ADDRESS|设置设备地址|
|GET_DESCRIPTOR|获取描述符|
|SET_CONFIGURATION|设置配置|
|GET_INTERFACE|获取接口|
|SET_INTERFACE|设置接口|

### EP0 请求分发

```
static int usb_handle_standard_request(const usb_setup_packet_t *s)
{
    switch (s->bRequest) {
    case USB_REQ_GET_DESCRIPTOR:
        return usb_send_descriptor(s);

    case USB_REQ_SET_ADDRESS:
        if (s->wIndex != 0U || s->wLength != 0U) {
            return -EINVAL;
        }
        return usb_device_set_address((uint8_t)s->wValue);

    case USB_REQ_SET_CONFIGURATION:
        if (s->wIndex != 0U || s->wLength != 0U) {
            return -EINVAL;
        }
        return usb_set_configuration((uint8_t)s->wValue);

    case USB_REQ_GET_CONFIGURATION:
        return usb_ep0_send(&g_usb.configuration, 1U);

    case USB_REQ_GET_STATUS:
        return usb_ep0_send_zero_status();

    default:
        return -ENOTSUP;
    }
}

void usb_ep0_setup_callback(const uint8_t *data, size_t len)
{
    usb_setup_packet_t setup;

    if (data == NULL || len != sizeof(setup)) {
        usb_ep0_stall();
        return;
    }

    memcpy(&setup, data, sizeof(setup));

    int rc;

    if ((setup.bmRequestType & USB_REQ_TYPE_MASK) == USB_REQ_TYPE_STANDARD) {
        rc = usb_handle_standard_request(&setup);
    } else if ((setup.bmRequestType & USB_REQ_TYPE_MASK) == USB_REQ_TYPE_CLASS) {
        rc = usb_handle_class_request(&setup);
    } else if ((setup.bmRequestType & USB_REQ_TYPE_MASK) == USB_REQ_TYPE_VENDOR) {
        rc = usb_handle_vendor_request(&setup);
    } else {
        rc = -ENOTSUP;
    }

    if (rc < 0) {
        usb_ep0_stall();
    }
}
```

### 控制传输中的常见错误

- `wLength` 与实际发送长度不一致。
- Device Descriptor 请求时返回超过 18 Bytes。
- 设备没有在 `SET_ADDRESS` 的 STATUS 阶段后更新地址。
- `SET_CONFIGURATION` 后没有打开非 0 端点。
- 无法识别的请求没有返回 STALL。
- 控制传输过程中错误地复用普通数据端点状态。

## 5.3 描述符层级

USB 描述符通常是：

```
Device Descriptor
  └── Configuration Descriptor
        ├── Interface Descriptor
        │     ├── HID Descriptor
        │     └── Endpoint Descriptor
        └── Interface Descriptor
              └── Endpoint Descriptor
```

### CDC ACM 的典型结构

```
Device
  Configuration
    Interface 0: Communication Control
      CDC Header
      CDC Call Management
      CDC ACM
      CDC Union
      Endpoint 1 IN: Interrupt
    Interface 1: Data
      Endpoint 2 OUT: Bulk
      Endpoint 3 IN: Bulk
```

### 描述符一致性约束

- `wTotalLength` 必须等于整个 Configuration Descriptor 集合长度。
- `bNumInterfaces` 必须等于接口数量。
- `bInterfaceNumber` 必须连续或符合设计。
- Endpoint 地址不能重复。
- `wMaxPacketSize` 必须符合速度与传输类型。
- HID 的 `wDescriptorLength` 必须匹配实际 Report Descriptor 长度。
- CDC Union Descriptor 的接口编号必须正确。

### 示例：设备描述符

```
static const uint8_t device_descriptor[] = {
    18U,                         /* bLength */
    USB_DESC_TYPE_DEVICE,        /* bDescriptorType */
    0x00U, 0x02U,                /* bcdUSB = 2.00 */
    0x00U,                       /* bDeviceClass */
    0x00U,                       /* bDeviceSubClass */
    0x00U,                       /* bDeviceProtocol */
    64U,                         /* bMaxPacketSize0 */
    0x34U, 0x12U,                /* idVendor */
    0x78U, 0x56U,                /* idProduct */
    0x00U, 0x01U,                /* bcdDevice */
    1U,                          /* iManufacturer */
    2U,                          /* iProduct */
    3U,                          /* iSerialNumber */
    1U                           /* bNumConfigurations */
};
```

生产系统中不要随意使用未分配的 VID。产品量产需要使用合法 VID/PID 组合，并处理序列号唯一性。

## 5.4 端点与数据切换位

Bulk、Interrupt 和 Control 数据传输使用 DATA0/DATA1 数据切换同步机制。

如果某次数据包成功完成，下一次应切换 DATA PID：

```
DATA0 -> DATA1 -> DATA0 -> ...
```

当端点复位或新的控制传输开始时，数据切换位需要重新同步。

### 为什么会出现“第一次正常，后续全部失败”

常见根因：

- Device 和 Host 的 DATA PID 状态不同步。
- 清空端点 FIFO 时没有重置数据切换位。
- 传输失败后错误地切换 PID。
- 重枚举后使用旧的端点上下文。
- Host 重新配置接口，但 Device 没有重置端点状态。

## 5.5 NAK、STALL、NYET 和错误重试

### NAK

表示当前不能传输数据，但不是永久错误。

典型原因：

- Device 尚未准备好数据。
- Device 暂时没有接收空间。
- Host 轮询过快。
- 应用层队列为空。

### STALL

表示端点或请求不可用，通常需要软件清除：

```
Host 发现 STALL
  -> Clear Feature(ENDPOINT_HALT)
  -> 重置端点状态
  -> 重新提交传输
```

### CRC 错误和超时

硬件通常会自动进行有限次重试，但上层仍需要：

- 记录错误计数。
- 区分瞬态错误和持续错误。
- 超过阈值后重置端点或重新枚举。
- 避免在 USB ISR 中无限重试。

## 5.6 DMA 与 Cache 一致性

USB 控制器通过 DMA 访问内存时，CPU D-Cache 可能导致数据不一致。

### Device OUT 方向

```
USB DMA -> RAM
CPU 读取前需要 invalidate cache
```

### Device IN 方向

```
CPU 写 RAM -> USB DMA 读取
DMA 启动前需要 clean cache
```

### 示例

```
#define USB_CACHE_LINE_SIZE 32U

static size_t align_down(size_t value, size_t align)
{
    return value & ~(align - 1U);
}

static size_t align_up(size_t value, size_t align)
{
    return (value + align - 1U) & ~(align - 1U);
}

void usb_dma_prepare_tx(void *buffer, size_t length)
{
    uintptr_t start = (uintptr_t)buffer;
    uintptr_t end = start + length;

    start = align_down(start, USB_CACHE_LINE_SIZE);
    end = align_up(end, USB_CACHE_LINE_SIZE);

    dcache_clean_by_addr((void *)start, end - start);
    __DSB();
}

void usb_dma_complete_rx(void *buffer, size_t length)
{
    uintptr_t start = (uintptr_t)buffer;
    uintptr_t end = start + length;

    start = align_down(start, USB_CACHE_LINE_SIZE);
    end = align_up(end, USB_CACHE_LINE_SIZE);

    __DSB();
    dcache_invalidate_by_addr((void *)start, end - start);
}
```

**不能只对有效数据长度做 Cache 操作而忽略 Cache Line 对齐。** 否则可能影响同一 Cache Line 中相邻变量。

## 5.7 Host 侧枚举流程

Host 枚举流程：

```
检测 VBUS 和设备连接
  -> 总线复位
  -> 地址 0 获取 Device Descriptor 前 8 Bytes
  -> 根据 bMaxPacketSize0 配置 EP0
  -> 分配新地址
  -> 获取完整 Device Descriptor
  -> 获取 Configuration Descriptor Header
  -> 获取完整 Configuration Descriptor
  -> 解析 Interface/Endpoint
  -> 加载类驱动
  -> SET_CONFIGURATION
  -> 创建 Pipe/URB
  -> 开始业务传输
```

### Host 枚举伪代码

```
int usb_host_enumerate(usb_port_t *port)
{
    usb_device_t *dev = usb_device_alloc();

    if (dev == NULL) {
        return -ENOMEM;
    }

    dev->address = 0U;
    dev->speed = usb_port_get_speed(port);

    int rc = usb_bus_reset(port, 100U);
    if (rc < 0) {
        goto fail;
    }

    rc = usb_control_get_descriptor(
        dev,
        USB_DESC_DEVICE,
        0U,
        dev->descriptor,
        8U,
        100U
    );
    if (rc < 0) {
        goto fail;
    }

    dev->ep0_max_packet = dev->descriptor[7];

    rc = usb_set_address(dev, usb_allocate_address());
    if (rc < 0) {
        goto fail;
    }

    rc = usb_control_get_descriptor(
        dev,
        USB_DESC_DEVICE,
        0U,
        dev->descriptor,
        sizeof(dev->descriptor),
        100U
    );
    if (rc < 0) {
        goto fail;
    }

    rc = usb_host_read_configuration(dev);
    if (rc < 0) {
        goto fail;
    }

    rc = usb_class_bind(dev);
    if (rc < 0) {
        goto fail;
    }

    rc = usb_set_configuration(dev, dev->selected_configuration);
    if (rc < 0) {
        goto fail;
    }

    dev->state = USB_HOST_CONFIGURED;
    return 0;

fail:
    usb_device_free(dev);
    return rc;
}
```

---

## 6. 性能量化分析

以下数据以典型 Cortex-M4/M7、USB FS、48 MHz USB 时钟、RTOS、DMA 方案为参考。具体数据会受到 MCU USB IP、主机驱动、缓存和应用协议影响。

## 6.1 USB FS 理论时间

USB FS 每帧为 1 ms：

```
12 Mbps / 8 = 1.5 MB/s 原始比特速率
```

但 USB 包包含：

- SYNC
- PID
- 地址与端点字段
- CRC
- EOP
- Inter-packet gap
- Token/Data/Handshake 开销

因此 Bulk 最大包的有效效率约为 60%～75%。

经验值：

```
理论应用吞吐 ≈ 1.5 MB/s × 0.65 = 975 KB/s
```

实际系统还要扣除：

- 主机调度空隙
- RTOS 调度
- 内存拷贝
- 文件系统写入
- USB 类协议头
- 缓冲区不足导致的 NAK

### 典型实测范围

|方案|方向|实际吞吐|
|---|---|---|
|CDC FS，轮询 API|Device -> Host|250～500 KB/s|
|CDC FS，DMA + 双缓冲|Device -> Host|500～800 KB/s|
|Vendor Bulk，零拷贝|Device -> Host|700～950 KB/s|
|MSC FS，Flash 后端|Host -> Device|100～600 KB/s|
|HID FS|双向|通常小于 64 KB/s|

## 6.2 中断负载

假设 USB FS Bulk OUT 使用 64 Bytes 包：

```
1 MB/s / 64 Bytes ≈ 15625 包/s
```

如果每个包产生一次中断，则中断频率可能达到 15 kHz 级别。

每次中断若消耗 2～5 微秒，则 CPU 开销为：

```
15625 × 3 us = 46875 us/s ≈ 4.7% CPU
```

实际还包含：

- FIFO 搬运
- Cache 操作
- 队列通知
- 协议解析
- 上下文切换

因此工程上通常采用：

- DMA
- 批量读取 FIFO
- 中断中只记录事件
- 任务中完成协议解析
- 环形缓冲区
- 双缓冲或多缓冲

## 6.3 RAM 开销估算

一个典型 CDC Device：

|项目|典型 RAM|
|---|---|
|EP0 控制缓冲|128～512 Bytes|
|CDC RX 缓冲|1～4 KB|
|CDC TX 缓冲|1～4 KB|
|RTOS 队列和控制块|0.5～2 KB|
|描述符运行时状态|0.5～2 KB|
|DMA 对齐预留|0.1～1 KB|
|合计|3～13 KB|

Host 侧一个简单 Bulk Device：

|项目|典型 RAM|
|---|---|
|Device/Interface/Endpoint 对象|1～4 KB|
|URB/Pipe 控制块|1～4 KB|
|枚举缓冲|1～4 KB|
|RX/TX 数据缓冲|4～32 KB|
|类驱动状态|2～16 KB|
|合计|10～60 KB|

## 6.4 延迟分析

HID Interrupt IN 的延迟近似为：

```
T_latency ≈ T_poll_interval + T_host_schedule + T_device_ISR + T_app
```

例如：

```
T_poll_interval = 1 ms
T_host_schedule = 0.05 ms
T_device_ISR = 0.01 ms
T_app = 0.2 ms
```

则平均延迟约为：

```
1.26 ms
```

CDC Bulk 没有固定轮询周期，延迟受主机调度、缓存聚合和发送策略影响。小包频繁发送可能得到较低延迟，但会显著降低吞吐。

## 6.5 优化收益

|优化措施|典型收益|
|---|---|
|中断搬运改 DMA|CPU 占用下降 2～8%|
|单缓冲改双缓冲|吞吐提高 10%～30%|
|每字节发送改批量发送|CPU 开销下降 50% 以上|
|复制式队列改指针队列|延迟下降，减少内存带宽|
|Cache 正确维护|消除偶发数据错误|
|增加 TX FIFO|降低 NAK，吞吐提高 5%～20%|
|任务解析代替 ISR 解析|缩短中断阻塞时间|
|Vendor Bulk 代替 CDC|减少协议层和驱动层额外开销|

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
需要 USB 通信
  |
  +-- MCU 连接 PC/手机，MCU 作为外设？
  |       |
  |       +-- 需要系统免驱？
  |       |       |
  |       |       +-- 键盘、鼠标、按键上报 -> HID
  |       |       +-- 虚拟串口、命令行       -> CDC ACM
  |       |       +-- U 盘、磁盘             -> MSC
  |       |
  |       +-- 追求高吞吐或自定义协议？
  |               |
  |               +-- PC 可安装专用驱动/库 -> Vendor Bulk
  |               +-- 需要系统原生支持       -> CDC/MSC
  |
  +-- MCU 需要读取 U 盘、键盘、鼠标？
  |       |
  |       +-- MCU 资源较小、设备固定 -> Host 类驱动
  |       +-- 设备种类复杂、带 Hub  -> 完整 Host Stack
  |
  +-- 同一接口需要动态切换角色？
          |
          +-- 支持 ID/VBUS 检测 -> OTG Dual Role
          +-- 仅软件切换、硬件供电可控 -> DRD/Role Switch
```

## 7.2 典型场景

|需求|方案|理由|
|---|---|---|
|工业仪器连接 PC 配置|CDC 或 Vendor Bulk|开发简单，支持命令和参数交互|
|低延迟按键、旋钮上报|HID Interrupt|主机免驱，轮询延迟可控|
|固件升级|DFU 或 Vendor Control/Bulk|支持镜像校验、回滚和断电恢复|
|MCU 写 U 盘日志|USB Host MSC|使用成熟的 Bulk-only Transport|
|录音设备|USB Audio Isochronous|需要固定周期和带宽预留|
|USB 网卡|CDC ECM/NCM|与网络协议栈集成|
|自研 PC 工具，高速数据|Vendor Bulk|协议自由，吞吐和批量效率较高|
|现场插拔多个外设|Host + Hub|需要端口管理和类驱动动态绑定|

---

## 8. 工程最佳实践

## 8.1 分层设计

推荐架构：

```
Application
  |
Class Driver
  |
USB Core
  |
Transfer Manager / URB / Pipe
  |
Controller Driver
  |
USB PHY / DMA / Registers
```

Device 侧：

```
Application
  |
Class Function
  |
USB Device Core
  |
Endpoint Manager
  |
USB Peripheral Driver
  |
USB Controller + PHY
```

### 分层职责

- Controller Driver：处理中断、FIFO、DMA、寄存器。
- USB Core：处理传输、端点和协议状态。
- Class Driver：CDC/HID/MSC 等类协议。
- Application：业务命令、数据处理和存储。
- 不应在 ISR 中执行文件系统、复杂解析或阻塞操作。

## 8.2 设计原则

1. **EP0 必须独立管理**
2. **USB ISR 只完成硬件事件收集**
3. **传输上下文必须拥有明确所有权**
4. **DMA 缓冲区固定地址和长度**
5. **所有超时都必须有上限**
6. **所有端点必须支持异常恢复**
7. **枚举日志必须可追踪**
8. **类协议和业务协议分离**
9. **应用层不能直接操作 USB 寄存器**
10. **断开、复位、重新枚举必须可重复执行**

## 8.3 选型决策矩阵

评分范围：1～5，数值越高越有利。

|方案|开发效率|免驱能力|吞吐|实时性|灵活性|资源消耗|
|---|---|---|---|---|---|---|
|HID|5|5|2|5|2|2|
|CDC|5|4|3|3|4|2|
|MSC|3|5|4|1|3|4|
|Vendor Bulk|2|1|5|4|5|3|
|Isochronous|2|4|5|5|4|4|

## 8.4 工业级编码规范

```
int usb_ep_submit(usb_endpoint_t *ep,
                  void *buffer,
                  size_t length,
                  usb_complete_cb_t callback,
                  void *context);
```

建议约束：

- `buffer == NULL && length != 0` 必须拒绝。
- 长度必须限制在端点和 DMA 支持范围内。
- 回调函数不能阻塞。
- 提交成功后，调用者不能修改缓冲区。
- 回调完成后才归还缓冲区所有权。
- 传输上下文必须包含序号、超时、重试次数和错误码。
- 所有硬件错误转换为统一的软件错误码。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：描述符长度不一致

### 错误代码

```
static const uint8_t config_descriptor[] = {
    9, USB_DESC_TYPE_CONFIGURATION,
    32, 0,       /* 实际数据长度不是 32 */
    1, 1, 0, 0x80, 50,
    /* 后续还有更多描述符 */
};
```

### 根因

`wTotalLength` 是整个配置描述符集合的总长度，不是 Configuration Descriptor 头部长度。

### 正确实现

```
#define CONFIG_DESC_TOTAL_LEN 67U

static const uint8_t config_descriptor[] = {
    9U, USB_DESC_TYPE_CONFIGURATION,
    (uint8_t)(CONFIG_DESC_TOTAL_LEN & 0xffU),
    (uint8_t)(CONFIG_DESC_TOTAL_LEN >> 8),
    /* 其余配置内容 */
};
```

### 风险影响

- Windows/Linux 只读取部分描述符。
- 类驱动绑定失败。
- 设备看似枚举成功，但端点不存在。

## 9.2 错误二：在 USB ISR 中执行阻塞操作

### 错误代码

```
void USB_IRQHandler(void)
{
    usb_rx_data_ready();

    xQueueSend(rx_queue, &data, portMAX_DELAY); /* 错误 */
    fs_write(log_file, buffer, length);         /* 错误 */
}
```

### 根因

ISR 中不能等待任务、文件系统锁或 USB 传输完成。

### 正确实现

```
void USB_IRQHandler(void)
{
    usb_event_t event;

    while (usb_hw_get_event(&event)) {
        usb_event_ring_push_from_isr(&event);
    }

    rtos_notify_from_isr(usb_worker_task);
}

void usb_worker(void *arg)
{
    usb_event_t event;

    for (;;) {
        rtos_wait_notification();

        while (usb_event_ring_pop(&event)) {
            usb_process_event(&event);
        }
    }
}
```

### 风险影响

- 中断长时间占用 CPU。
- 系统出现优先级反转。
- USB SOF、定时器和其他实时中断丢失。

## 9.3 错误三：忽略 Cache 一致性

### 错误代码

```
memcpy(tx_buf, payload, payload_len);
usb_dma_start_tx(tx_buf, payload_len);
```

### 根因

CPU 写入的数据可能仍停留在 D-Cache 中，USB DMA 读取到旧数据。

### 正确实现

```
memcpy(tx_buf, payload, payload_len);
usb_dma_prepare_tx(tx_buf, payload_len);
usb_dma_start_tx(tx_buf, payload_len);
```

### 风险影响

- 数据偶发错误。
- Debug 版本正常，开启优化或 Cache 后失败。
- 错误具有随机性，难以复现。

## 9.4 错误四：把 NAK 当作永久故障

### 错误代码

```
if (status == USB_STATUS_NAK) {
    usb_endpoint_reset(ep);
    usb_device_reenumerate();
}
```

### 根因

NAK 只表示当前没有数据或空间，不是端点损坏。

### 正确实现

```
if (status == USB_STATUS_NAK) {
    ep->nak_count++;

    if (ep->nak_count < USB_NAK_RETRY_LIMIT) {
        usb_resubmit_after_interval(ep, USB_RETRY_INTERVAL_MS);
    } else {
        usb_endpoint_recover(ep);
    }

    return;
}
```

### 风险影响

- 设备频繁重置。
- 主机侧出现设备反复断开重连。
- 正常流控被误判为硬件故障。

## 9.5 错误五：USB 缓冲区位于不可 DMA 区域

### 错误代码

```
uint8_t tx_buffer[512]; /* 可能位于 DTCM 或非 DMA RAM */
```

### 根因

部分 MCU 的 USB DMA 不能访问 DTCM、Cache-only 区域或特定 SRAM Bank。

### 正确实现

```
__attribute__((section(".usb_dma"), aligned(32)))
static uint8_t tx_buffer[512];

__attribute__((section(".usb_dma"), aligned(32)))
static uint8_t rx_buffer[512];
```

链接脚本：

```
.usb_dma (NOLOAD) :
{
    . = ALIGN(32);
    *(.usb_dma)
    . = ALIGN(32);
} >RAM_D2
```

### 风险影响

- DMA 总线错误。
- 数据完全不发送。
- 访问异常或只在高负载下失败。

## 9.6 错误六：CDC 接收按“消息”而不是“字节流”理解

### 错误代码

```
void cdc_rx_callback(uint8_t *data, size_t len)
{
    if (data[len - 1U] == '\n') {
        process_command((char *)data);
    }
}
```

### 根因

CDC Bulk 是字节流，USB 包边界不等于应用消息边界。

### 正确实现

```
void cdc_rx_callback(const uint8_t *data, size_t len)
{
    for (size_t i = 0; i < len; ++i) {
        if (ringbuf_put(&cmd_ring, data[i]) < 0) {
            g_stats.rx_overflow++;
            break;
        }
    }

    rtos_notify(cmd_parser_task);
}
```

应用层再通过换行符、长度字段或 CRC 分帧。

---

## 10. 多机制组合使用方案

## 10.1 USB Device + RTOS + DMA + 零拷贝环形缓冲

推荐数据流：

```
USB RX DMA
  -> DMA Buffer
  -> Cache Invalidate
  -> RX Descriptor Queue
  -> Protocol Task
  -> Application Queue
```

TX 方向：

```
Application
  -> TX Ring
  -> USB TX Task
  -> DMA Buffer
  -> Cache Clean
  -> USB Endpoint
```

### 传输描述符

```
typedef struct {
    uint8_t *buffer;
    size_t length;
    size_t capacity;
    uint32_t sequence;
    uint32_t timestamp;
    volatile bool in_use;
} usb_buf_desc_t;

typedef struct {
    usb_buf_desc_t desc[8];
    volatile uint32_t producer;
    volatile uint32_t consumer;
} usb_ring_t;

static bool usb_ring_push(usb_ring_t *ring, usb_buf_desc_t item)
{
    uint32_t next = (ring->producer + 1U) % 8U;

    if (next == ring->consumer) {
        return false;
    }

    ring->desc[ring->producer] = item;
    __DMB();
    ring->producer = next;

    return true;
}

static bool usb_ring_pop(usb_ring_t *ring, usb_buf_desc_t *item)
{
    if (ring->consumer == ring->producer) {
        return false;
    }

    *item = ring->desc[ring->consumer];
    __DMB();
    ring->consumer = (ring->consumer + 1U) % 8U;

    return true;
}
```

### 关键设计点

- Ring 的生产者和消费者只能单向修改自己的索引。
- ISR 只负责写入事件和索引。
- 任务负责复杂处理。
- 缓冲区所有权必须明确。
- 溢出时必须统计并上报，而不是静默丢弃。

## 10.2 USB Host + Hub + 类驱动框架

```
Root Hub
  -> Port Manager
      -> Device Manager
          -> Enumeration
              -> Descriptor Parser
                  -> Class Driver Matching
                      -> Pipe Manager
                          -> URB Scheduler
```

核心对象：

```
typedef struct usb_host_device usb_host_device_t;

typedef struct {
    uint8_t address;
    uint8_t endpoint_number;
    uint8_t direction;
    uint8_t type;
    uint16_t max_packet;
    uint8_t interval;
    void *controller_pipe;
} usb_host_endpoint_t;

struct usb_host_device {
    uint8_t address;
    uint8_t speed;
    uint8_t configuration;
    uint8_t interface_count;
    usb_host_endpoint_t endpoints[16];
    void *class_context;
};
```

Host 设计中必须区分：

- 设备地址
- 端点地址
- Pipe
- URB
- Transfer 状态
- 类驱动状态
- 物理端口状态

不能把一个简单的 `usb_transfer()` 函数扩展成完整 Host 架构，否则热插拔、重试和 Hub 支持会很快失控。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业仪器 USB 虚拟串口

### 需求

- 连接 PC 进行参数配置和诊断。
- 支持固件日志输出。
- 支持命令请求和响应。
- 断开后自动恢复。
- 单次命令最大 1 KB。

### 架构

```
CDC ACM
  |
RX Bulk -> DMA -> Ring Buffer -> Command Parser
TX Bulk <- TX Queue <- Logger / Command Response
Control Interrupt Endpoint <- Line Coding / Control Line State
```

### 核心代码

```
typedef struct {
    uint16_t length;
    uint16_t crc16;
    uint8_t payload[1024];
} command_frame_t;

int command_send(const uint8_t *payload, uint16_t length)
{
    if (payload == NULL || length == 0U || length > 1024U) {
        return -EINVAL;
    }

    command_frame_t frame = {0};
    frame.length = length;
    memcpy(frame.payload, payload, length);
    frame.crc16 = crc16_ccitt(frame.payload, length);

    return usb_cdc_write(
        (const uint8_t *)&frame,
        sizeof(frame.length) + length + sizeof(frame.crc16),
        100U
    );
}
```

### 设计要点

- CDC 只提供字节流，应用层必须自行分帧。
- 日志和命令响应使用不同优先级队列。
- 日志不能无限占用 TX。
- 断开时释放未完成的传输。
- 需要加入命令序列号和超时机制。

## 11.2 案例二：设备作为 USB Host 读取 U 盘

### 需求

- 插入 U 盘后自动挂载。
- 支持 FAT32。
- 记录测量数据。
- 拔出时保证文件系统一致性。
- U 盘异常时自动重新枚举。

### 架构

```
USB Host Controller
  -> MSC Class Driver
      -> Bulk-Only Transport
          -> SCSI READ10/WRITE10
              -> Block Device
                  -> FATFS
                      -> Data Logger
```

### MSC 传输流程

```
CBW OUT
  -> SCSI Command
  -> Data IN/OUT
  -> CSW IN
```

### 设计要点

- 不能只判断 USB 设备是否连接，还要判断 MSC 配置和 SCSI 初始化是否成功。
- `TEST UNIT READY` 失败时需要轮询，不应立刻卸载。
- 文件系统写入必须考虑电源掉电。
- 拔出事件到达后，禁止继续提交新的 Bulk 传输。
- 需要检查 CSW 的签名、Tag、Residue 和 Status。
- 重要日志建议使用临时文件加原子重命名，或追加日志并周期性同步。

## 11.3 案例三：USB HID 工业控制面板

### 需求

- PC 免安装驱动。
- 面板包含 32 个按键、8 个旋钮。
- 按键变化延迟小于 5 ms。
- 设备断线后可恢复。
- 主机偶发忙碌时不能阻塞控制任务。

### 方案

- HID Interrupt IN：周期性上报按键和旋钮状态。
- HID Interrupt OUT：接收指示灯和蜂鸣器控制。
- Report Descriptor 描述输入输出字段。
- 设备内部使用状态快照和变化检测。

### 设计要点

```
采样任务
  -> 输入状态快照
  -> 变化检测
  -> HID Report 队列
  -> Interrupt IN
```

不要在采样任务中直接等待 USB 发送完成。USB 未配置、端点 NAK 或设备断开都不应阻塞输入采样。

---

## 12. 高频问题深度答疑

### 问题一：为什么 USB Device 不能主动发送数据？

USB 总线采用 Host 调度模型。Device 没有总线仲裁权，不能自行发送 Token。Device 要上报数据，必须：

1. 在本地准备数据；
2. 等待 Host 发送 IN Token；
3. 返回 DATA 包；
4. 等待 Host ACK。

因此，Device 侧“发送”本质上是：

```
准备 IN Endpoint 数据 -> 等待 Host 轮询
```

如果 Host 没有轮询，即使设备缓存中有数据，也不会产生总线传输。

### 问题二：Bulk 和 Interrupt 的区别是什么？

Interrupt 不是 CPU 中断，也不代表 USB Device 能主动中断 Host。

Interrupt Transfer 的含义是：

- Host 按固定间隔轮询；
- 设备可以返回数据或 NAK；
- Host 为其预留一定调度机会；
- 延迟相对可预测。

Bulk Transfer：

- 没有固定的实时带宽保证；
- 总线空闲时可以获得较高吞吐；
- 在大量周期性传输存在时可能延迟增加。

因此：

- 控制命令和大数据：Bulk。
- 小数据、低延迟状态上报：Interrupt。
- 严格周期音频：Isochronous。

### 问题三：为什么枚举只在某些 PC 上失败？

常见原因：

- 描述符不符合规范但某些主机容错。
- USB 时钟偏差超出范围。
- EP0 最大包长处理不正确。
- `SET_ADDRESS` 时机错误。
- 返回描述符速度与真实速度不匹配。
- VBUS、上拉、电气时序问题。
- 设备在主机请求后响应超时。
- 字符串描述符编码错误。
- 配置描述符长度或接口数量不一致。

定位顺序：

```
电气信号
  -> USB Reset
  -> Device Descriptor
  -> SET_ADDRESS
  -> Configuration Descriptor
  -> SET_CONFIGURATION
  -> 类请求
```

不要只看“设备管理器是否识别”，必须看失败发生在哪一个控制请求。

### 问题四：USB 传输为什么会偶发丢数据？

常见根因：

- 环形缓冲区溢出。
- DMA 和 Cache 不一致。
- 应用层错误地依赖 USB 包边界。
- CDC 数据没有分帧。
- 传输完成回调与缓冲区复用存在竞态。
- ISR 和任务共享索引没有内存屏障。
- 端点 FIFO 溢出。
- Host 端读取策略造成长期 NAK。

应该同时记录：

```
包序号
传输长度
端点状态
DMA 状态
FIFO 水位
Ring Buffer 水位
Cache 操作
错误计数
时间戳
```

### 问题五：什么时候使用双缓冲？

适合以下情况：

- 连续 Bulk 数据流。
- DMA 搬运和应用处理可以并行。
- 单个缓冲区处理时间可能超过一个 USB 调度周期。
- 需要减少 NAK 和流水线空洞。

双缓冲可以形成：

```
Buffer A: USB DMA 正在填充
Buffer B: CPU 正在解析
```

如果应用处理时间超过两个缓冲区的容纳能力，应使用环形多缓冲，而不是盲目扩大单个缓冲区。

### 问题六：Host 是否需要支持所有 USB 设备？

不需要。Host 可以只支持目标设备所需的类和协议。

工业设备中推荐：

- 明确支持的 VID/PID、Class、Subclass、Protocol。
- 对未知设备进行安全拒绝。
- 限制最大描述符长度和最大端点数量。
- 对异常描述符做边界检查。
- 对 Hub 层级、设备数量和地址范围设置上限。

这可以显著降低 RAM、代码复杂度和攻击面。

---

## 13. 课程核心总结

### 核心要点

1. **USB 是 Host 主导、Device 响应的总线协议。**
2. **Endpoint 是 USB 数据通信的逻辑终点。**
3. **EP0 是所有设备的协议基础，必须独立、可靠地实现。**
4. **枚举失败优先检查描述符、EP0、地址切换和控制请求时序。**
5. **CDC 是字节流，不存在天然消息边界。**
6. **HID 适合免驱、小数据、低延迟控制。**
7. **MSC 不是简单的块读写，还包括 BOT、SCSI 和文件系统一致性。**
8. **Isochronous 适合实时媒体，但不会重试错误。**
9. **DMA、Cache、FIFO 和缓冲区所有权决定工业级可靠性。**
10. **Host 架构必须把枚举、Pipe、URB、类驱动和热插拔分层。**

### 性能排序

按典型吞吐能力：

```
USB HS Vendor Bulk
  > USB FS Vendor Bulk
  > USB FS MSC
  > USB FS CDC
  > USB FS HID
```

按实时性：

```
Isochronous
  > Interrupt
  > Control
  > Bulk
```

按开发简单度：

```
HID
  > CDC
  > Vendor Bulk
  > MSC
  > Audio/Host/OTG
```

### 通用选型结论

- **免驱键鼠类控制：HID**
- **虚拟串口与诊断：CDC**
- **大容量存储：MSC**
- **高吞吐自定义协议：Vendor Bulk**
- **周期媒体流：Isochronous**
- **MCU 读取 U 盘：Host MSC**
- **复杂多设备环境：Host + Hub + 动态类驱动**
- **角色动态切换：OTG/DRD，但必须同时处理 VBUS、ID、状态机和供电管理**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐方案|关键端点|重点关注|
|---|---|---|---|
|PC 命令行|CDC ACM|Bulk IN/OUT|分帧、缓存|
|PC 高速采集|Vendor Bulk|Bulk IN/OUT|DMA、零拷贝|
|键盘/旋钮|HID|Interrupt IN|报告描述符|
|U 盘设备|MSC|Bulk IN/OUT|SCSI、FATFS|
|音频|USB Audio|Isochronous|时钟、丢包|
|固件升级|DFU|Control/Bulk|镜像校验、回滚|
|MCU 读取 U 盘|Host MSC|Bulk Pipe|热插拔、SCSI|
|MCU 读取键盘|Host HID|Interrupt Pipe|Report Parser|
|双角色设备|OTG|动态|VBUS、角色切换|

### 14.2 特性对比表

|特性|Device|Host|
|---|---|---|
|是否发起事务|否|是|
|是否负责枚举|响应|负责|
|是否管理地址|被分配|分配|
|是否维护 Pipe|通常维护端点|必须维护|
|RAM 需求|较低|较高|
|典型故障|描述符、端点、FIFO|枚举、调度、类驱动|
|关键调试点|EP0、DMA、NAK|Port、URB、Pipe、Hub|

### 14.3 常用诊断命令语义

|操作|目的|
|---|---|
|Bus Reset|初始化设备状态|
|GET_DESCRIPTOR|获取设备能力|
|SET_ADDRESS|分配设备地址|
|SET_CONFIGURATION|激活配置|
|CLEAR_FEATURE/HALT|清除端点 STALL|
|GET_MAX_LUN|MSC 获取逻辑单元数量|
|SCSI TEST UNIT READY|检查存储设备就绪|
|SCSI READ10/WRITE10|读写磁盘块|

---

## 15. 学习效果自检

完成本课后，应能够回答并完成以下任务：

- 能否画出 USB Device 从上电到 Configured 的状态机？
- 能否解释 Host 为什么必须发送 IN Token？
- 能否根据十六进制数据解析 Device Descriptor？
- 能否检查 `wTotalLength`、`bNumInterfaces` 和 Endpoint 地址是否一致？
- 能否实现 EP0 的 `GET_DESCRIPTOR` 和 `SET_CONFIGURATION`？
- 能否说明 CDC 为什么必须在应用层分帧？
- 能否解释 DATA0/DATA1 的作用？
- 能否区分 NAK、STALL、CRC Error 和 Timeout？
- 能否计算 USB FS Bulk 的理论吞吐量？
- 能否设计 USB DMA 缓冲区的链接脚本区域？
- 能否识别 Cortex-M7 USB DMA 的 Cache 一致性问题？
- 能否设计 ISR、USB Worker Task 和应用任务之间的数据流？
- 能否写出 Host 枚举的主要步骤？
- 能否说明 MSC BOT 中 CBW、Data、CSW 的顺序？
- 能否设计拔出 U 盘时的传输取消和文件系统卸载流程？
- 能否使用抓包工具定位枚举失败发生在哪个控制请求？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：最小 USB CDC Device

要求：

- 实现 Device Descriptor。
- 实现 Configuration Descriptor。
- 支持 `GET_DESCRIPTOR`。
- 支持 `SET_ADDRESS`。
- 支持 `SET_CONFIGURATION`。
- 完成 CDC Bulk IN/OUT。
- 使用 PC 发送和接收命令。

验收指标：

- 能够稳定枚举 100 次。
- 连续发送 1 MB 数据无丢包。
- 断开后重新连接可自动恢复。

### 任务二：CDC 高吞吐优化

实现三种版本：

```
版本 A：轮询 + 单缓冲
版本 B：中断 + 环形缓冲
版本 C：DMA + 双缓冲 + Cache 维护
```

记录：

- CPU 占用率。
- 平均吞吐。
- 最大延迟。
- Ring Buffer 峰值水位。
- NAK 数量。
- CRC/传输错误数量。

### 任务三：HID 控制面板

要求：

- 设计 32 键输入 Report。
- 设计 8 个旋钮输入字段。
- 支持 LED 和蜂鸣器输出。
- 设置 1 ms 或 2 ms Interrupt Interval。
- 测量按键变化到 PC 收到数据的延迟。

### 任务四：USB Host HID

要求：

- 检测键盘插入。
- 读取完整配置描述符。
- 解析 HID Report Descriptor。
- 支持 Boot Keyboard。
- 处理拔出和重新插入。
- 对未知 HID 设备安全拒绝。

### 任务五：USB Host MSC + FATFS

要求：

- 枚举 U 盘。
- 完成 SCSI 初始化。
- 读取容量。
- 挂载 FAT32。
- 写入循环日志。
- 模拟拔出、写保护和异常断电。

### 任务六：Vendor Bulk 工业协议

建议帧格式：

```
Magic    : 2 Bytes
Version  : 1 Byte
Type     : 1 Byte
Sequence : 4 Bytes
Length   : 2 Bytes
Payload  : N Bytes
CRC32    : 4 Bytes
```

必须支持：

- 序列号检测。
- 长度边界检查。
- CRC 校验。
- 请求超时。
- 重复请求幂等处理。
- 设备断开后事务失效。
- 协议版本兼容。

## 16.2 性能测试方法

### 测试环境

- MCU：Cortex-M4 或 Cortex-M7
- USB：Full Speed 12 Mbps
- 主机：Linux 或 Windows
- 工具：USB Protocol Analyzer、逻辑分析仪、RTOS Runtime Stats
- 编译配置：Debug、Release、开启/关闭 D-Cache
- 数据模式：64 Bytes 小包、512 Bytes 批量包、随机长度包

### 必测指标

```
吞吐量
平均延迟
P99 延迟
CPU 占用率
最大 ISR 执行时间
最大临界区时间
NAK 数量
STALL 数量
超时数量
DMA 错误
缓存一致性错误
缓冲区峰值水位
```

### 测试公式

吞吐量：

```
Throughput = SuccessfulBytes / TestDuration
```

CPU 占用：

```
CPU_Load = USB_CPU_Time / Total_Time × 100%
```

P99 延迟：

```
将所有传输延迟排序，取第 ceil(0.99 × N) 个样本
```

缓冲区安全余量：

```
Buffer_Margin = Buffer_Capacity - Peak_Usage
```

工业系统中不应只看平均值。应重点观察 **P99/P999 延迟、最大 ISR 时间和最坏情况下的缓存水位**。

## 16.3 进阶学习方向

1. USB 2.0 规范：
    
    - 电气层和信号质量
    - 包格式和事务调度
    - 设备状态和标准请求
    - Hub、Suspend、Resume、Remote Wakeup
2. 控制器底层：
    
    - Synopsys USB OTG IP
    - FIFO 配置
    - DMA 描述符
    - Host Channel 与 Device Endpoint
    - OTG 状态机和 VBUS 控制
3. 操作系统 USB 栈：
    
    - Linux `usbcore`
    - Linux `xhci-hcd`
    - Linux Gadget Framework
    - Windows USB Class Driver
    - libusb 与 WinUSB
4. 工业级可靠性：
    
    - 热插拔压力测试
    - 枚举故障注入
    - CRC、超时和 STALL 注入
    - 断电恢复
    - USB ESD 和 EMC 测试
    - 长时间吞吐稳定性测试
5. 高级协议：
    
    - USB Audio
    - USB Video
    - USB Ethernet
    - USB DFU
    - USB Type-C
    - USB Power Delivery
    - USB 3.x SuperSpeed

本课的工程结论是：**USB 开发的难点不在于调用一个发送 API，而在于正确处理枚举状态机、端点生命周期、DMA/Cache 一致性、传输调度、异常恢复和应用层数据边界。**