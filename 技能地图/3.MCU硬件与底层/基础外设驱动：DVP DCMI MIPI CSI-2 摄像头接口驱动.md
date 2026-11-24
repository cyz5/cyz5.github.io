
## 1. 学习目标

### 理解

- 理解摄像头从 **像素阵列、时序输出、物理层、接收控制器、DMA、缓存、图像处理链路** 到应用层的完整数据路径。
- 理解 DVP、STM32 DCMI、MIPI CSI-2 在物理连接、协议封装、同步方式、带宽和调试方法上的本质差异。
- 理解摄像头驱动中常见的 `VSync`、`HSync`、`PCLK`、`D0~D7/D15`、`HS`、`VS`、`LP/HS`、`Frame Start`、`Line Start` 等信号含义。

### 掌握

- 掌握 DVP 摄像头初始化、SCCB/I2C 配置、并口采样、DMA 双缓冲和帧同步。
- 掌握 STM32 DCMI 的同步极性、数据宽度、裁剪、DMA 链路和帧事件处理。
- 掌握 MIPI CSI-2 接收链路中的 D-PHY、CSI-2 Packet、Virtual Channel、Data Type 和 ECC/CRC。
- 掌握 RGB565、YUV422、RAW8、RAW10 等格式的字节布局和带宽计算。
- 掌握缓存一致性、Cache 对齐、DMA 缓冲区布局、帧丢弃和过载保护。

### 精通

- 能够定位花屏、错行、偏色、帧撕裂、随机丢帧、DMA 溢出、CSI-2 CRC 错误等工业现场问题。
- 能够根据分辨率、帧率、像素格式和平台吞吐量选择 DVP、DCMI 或 MIPI CSI-2。
- 能够设计具备超时、复位、掉电、错误恢复和动态帧率控制能力的摄像头驱动。
- 能够评估 ISP、硬件缩放器、GPU、NPU 和 CPU 对图像数据的带宽压力。

### 能够设计

- 能够设计从传感器到应用的完整采集架构。
- 能够设计多缓冲视频采集系统，保证生产者和消费者之间没有数据竞争。
- 能够为高分辨率、高帧率系统设计 MIPI CSI-2 Lane 数量、时钟、内存带宽和错误监测方案。
- 能够建立摄像头驱动的验证矩阵、性能基线和现场故障诊断机制。

---

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、位操作、内存模型和中断。
- MCU 时钟树、GPIO 复用、DMA、定时器、外部中断。
- I2C/SCCB 总线时序和设备寄存器初始化。
- RGB565、YUV422、RAW Bayer 等基本图像格式。
- RTOS 任务、队列、信号量、事件组和中断服务程序。
- ARM Cortex-M 异常模型、D-Cache、MPU 和内存屏障。
- 对 Linux 平台，还需要理解设备树、V4L2、Media Controller 和 DMA-BUF。

### 技能要求

- 能够使用示波器或逻辑分析仪观察 `PCLK`、`HSYNC`、`VSYNC`。
- 能够使用寄存器手册配置 GPIO、DMA 和摄像头接口。
- 能够使用 I2C/SCCB 读取摄像头 ID 并修改寄存器。
- 能够编写基本的 DMA 环形缓冲和双缓冲代码。
- 能够通过 CRC、帧计数、行计数和图像模式测试定位问题。

---

## 3. 技术概述

### 3.1 摄像头驱动的分层结构

典型链路如下：

```
图像传感器
    |
    | 物理层与像素时序
    v
DVP / MIPI D-PHY + CSI-2
    |
    v
MCU DCMI / SoC CSI Receiver
    |
    v
FIFO / DMA
    |
    v
SRAM / DDR / DMA-BUF
    |
    +--> ISP
    +--> JPEG Encoder
    +--> LCD / HDMI
    +--> AI 推理
    +--> 网络传输
```

摄像头驱动通常包含四个逻辑部分：

```
Sensor Control Driver
    - I2C/SCCB
    - 复位、掉电、时钟
    - 分辨率、帧率、格式配置

Interface Driver
    - DVP 或 CSI-2 接收器
    - 极性、Lane、Data Type
    - 错误中断

DMA/Buffer Manager
    - 帧缓冲
    - Cache 一致性
    - 所有权转移
    - 丢帧策略

Application Adapter
    - ioctl / V4L2 / RTOS API
    - 帧获取与释放
    - 超时与恢复
```

### 3.2 DVP

DVP 是并行数字视频接口，常见信号：

```
PCLK       像素时钟
VSYNC      帧同步
HSYNC/HREF 行同步或有效窗口
D[7:0]     8 bit 像素数据
D[15:0]    16 bit 像素数据
XCLK/MCLK 传感器输入时钟
SCL/SDA    SCCB/I2C 配置接口
RESET      复位
PWDN       掉电控制
```

常见输出形式：

- RGB565：每像素 16 bit。
- YUV422：每像素平均 16 bit。
- RAW8：每像素 8 bit。
- RAW10：每像素平均 10 bit，但常按打包格式传输。
- JPEG：压缩码流，帧长度可变。

DVP 的核心特点是：**时序直观、硬件成本低、调试容易，但引脚和吞吐能力受限**。

### 3.3 DCMI

DCMI 通常指 STM32 系列中的 Digital Camera Memory Interface。它本质上是 **DVP 接收控制器**，负责：

- 根据 `PCLK` 采样数据。
- 根据 `HSYNC/HREF` 判断行有效区。
- 根据 `VSYNC` 判断帧边界。
- 将采样数据写入内部 FIFO 或 DMA。
- 支持 8 bit、10 bit、12 bit、14 bit 等输入宽度，具体取决于芯片型号。
- 支持硬件裁剪和 JPEG 模式。
- 产生帧完成、溢出、同步错误等事件。

DCMI 不等于 MIPI CSI-2。DCMI 接受的是并行时序信号，不能直接接 MIPI 差分 Lane。

### 3.4 MIPI CSI-2

MIPI CSI-2 由两层组成：

```
D-PHY
    - 差分物理层
    - Clock Lane + Data Lane
    - LP 模式与 HS 模式
    - 终端匹配、速率、Lane 数

CSI-2 Protocol
    - Short Packet
    - Long Packet
    - Data ID
    - Word Count
    - ECC
    - Payload
    - CRC
```

CSI-2 长包结构：

```
+----------------+----------------+----------------+----------------+
| Data ID        | Word Count     | ECC            | Payload        |
| 8 bit          | 16 bit         | 8 bit          | N bytes        |
+----------------+----------------+----------------+----------------+
| CRC16          |
+----------------+
```

常见 CSI-2 Data Type：

|Data Type|含义|
|---|---|
|`0x2A`|RAW8|
|`0x2B`|RAW10|
|`0x2C`|RAW12|
|`0x1E`|YUV422 8 bit|
|`0x22`|RGB565|
|`0x24`|RGB888|
|`0x18`|User Defined 8 bit|
|`0x00`|Frame Start|
|`0x01`|Frame End|
|`0x02`|Line Start|
|`0x03`|Line End|

CSI-2 的核心特点是：**引脚少、吞吐高、抗干扰能力较强，但 PHY、协议、时钟和调试复杂度显著增加**。

---

## 4. 核心特性横向对比

|维度|DVP|MCU DCMI|MIPI CSI-2|
|---|---|---|---|
|本质|并行视频时序|DVP 接收控制器|高速串行协议|
|物理信号|单端并行|单端并行|差分 Clock/Data Lane|
|典型引脚|10~20 根|10~20 根|2~10 根|
|配置接口|I2C/SCCB|MCU 寄存器|I2C/SCCB + CSI Receiver|
|最大吞吐|受 GPIO/PCLK 限制|受 DCMI、DMA、SRAM 限制|受 Lane 速率、PHY、DDR 带宽限制|
|时序复杂度|低|中|高|
|调试难度|低|中|高|
|抗串扰能力|中|中|高，依赖 PCB 和 PHY|
|布线要求|数据线等长性较敏感|中等|差分阻抗、长度匹配、过孔控制|
|帧边界|VSYNC|DCMI 识别 VSYNC|Frame Start/End Packet|
|行边界|HSYNC/HREF|DCMI 识别 HSYNC/HREF|Line Start/End 或包长度|
|帧长度|通常固定|通常固定|可变，尤其压缩格式|
|硬件成本|低|低至中|中至高|
|典型场景|VGA、QVGA、低功耗 MCU|STM32 摄像头采集|高分辨率、高帧率、Linux SoC|
|适合 RAW|可以|可以，受宽度限制|原生支持更好|
|适合 JPEG|传输方便|常有 JPEG 模式|需要接收器支持对应 Data Type|
|错误检测|主要依赖时序监测|溢出、同步错误|ECC、CRC、PHY 错误|
|扩展能力|低|中|高|

---

## 5. 底层原理与功能特性深度解析

### 5.1 传感器时钟与像素时序

多数 CMOS 传感器需要外部输入时钟 `XCLK/MCLK`，典型值为：

- 6 MHz
- 12 MHz
- 24 MHz
- 25 MHz

传感器内部通过 PLL 生成：

```
XCLK -> Sensor PLL -> Pixel Clock -> PCLK
```

像素时钟与帧率关系近似为：

FPS=PCLKHTS×VTSFPS=HTS×VTSPCLK​

其中：

- `HTS`：水平总周期，包括有效像素和水平消隐。
- `VTS`：垂直总周期，包括有效行和垂直消隐。
- `PCLK`：像素时钟。

例如：

```
PCLK = 24 MHz
HTS   = 800
VTS   = 525
```

则：

FPS=24,000,000800×525≈57.14FPS=800×52524,000,000​≈57.14

若目标是 30 FPS，通常需要降低 PCLK 或增加 `VTS`。

#### 工程代码：XCLK 配置

```
typedef struct {
    uint32_t input_hz;
    uint32_t target_hz;
    uint32_t tolerance_hz;
} cam_clk_cfg_t;

static int cam_validate_xclk(const cam_clk_cfg_t *cfg)
{
    if (cfg == NULL || cfg->input_hz == 0U || cfg->target_hz == 0U) {
        return -EINVAL;
    }

    uint32_t diff = (cfg->input_hz > cfg->target_hz) ?
                    (cfg->input_hz - cfg->target_hz) :
                    (cfg->target_hz - cfg->input_hz);

    if (diff > cfg->tolerance_hz) {
        return -ERANGE;
    }

    return 0;
}
```

实际系统中，XCLK 误差可能造成：

- 传感器 PLL 锁定失败。
- 帧率偏差。
- 曝光时间异常。
- 传感器输出 PCLK 超出接收器范围。
- MIPI Lane 速率计算错误。

---

### 5.2 DVP 数据采样

DVP 在每个 PCLK 边沿采样数据，数据有效关系由传感器和接收器共同决定：

```
        ____      ____      ____
PCLK __|    |____|    |____|    |__

DATA ----< P0 >----< P1 >----< P2 >----
```

接收器需要配置：

- PCLK 上升沿或下降沿采样。
- HSYNC 高有效或低有效。
- VSYNC 高有效或低有效。
- HREF 模式或独立 HSYNC 模式。
- 数据位宽。
- 数据排列顺序。

典型错误：

```
正确 RGB565:
Byte0 = RRRRRGGG
Byte1 = GGGBBBBB

错误采样边沿:
Byte0/Byte1 可能错位
结果通常表现为横向条纹、颜色异常或图像抖动
```

#### DCMI 初始化关键字段

```
typedef struct {
    uint32_t data_width;
    bool pclk_rising;
    bool hsync_high;
    bool vsync_high;
    bool jpeg_mode;
    uint16_t crop_x;
    uint16_t crop_y;
    uint16_t crop_w;
    uint16_t crop_h;
} dcmi_cfg_t;
```

初始化时必须先停采集，再修改控制寄存器：

```
static int dcmi_configure(const dcmi_cfg_t *cfg)
{
    if (cfg == NULL || cfg->crop_w == 0U || cfg->crop_h == 0U) {
        return -EINVAL;
    }

    if (dcmi_is_capture_active()) {
        dcmi_stop_capture();
    }

    dcmi_clear_flags(DCMI_FLAG_ALL);

    dcmi_set_data_width(cfg->data_width);
    dcmi_set_pclk_polarity(cfg->pclk_rising);
    dcmi_set_hsync_polarity(cfg->hsync_high);
    dcmi_set_vsync_polarity(cfg->vsync_high);
    dcmi_set_jpeg_mode(cfg->jpeg_mode);

    if (dcmi_set_crop(cfg->crop_x, cfg->crop_y,
                      cfg->crop_w, cfg->crop_h) != 0) {
        return -ERANGE;
    }

    return 0;
}
```

---

### 5.3 SCCB/I2C 传感器控制

OV2640、OV5640、GC2145 等传感器通常通过 SCCB 或兼容 I2C 的接口配置。

常见寄存器表：

```
typedef struct {
    uint16_t reg;
    uint8_t  value;
    uint16_t delay_ms;
} sensor_regval_t;
```

生产级初始化不能只循环写寄存器，还需要：

- 总线超时。
- ACK 检查。
- 设备 ID 校验。
- 软件复位后的等待。
- 延迟寄存器支持。
- 写入失败重试。
- 失败后的硬件复位。
- 禁止无界循环。

```
static int sensor_write_table(const sensor_regval_t *table,
                              size_t count)
{
    if (table == NULL || count == 0U) {
        return -EINVAL;
    }

    for (size_t i = 0; i < count; ++i) {
        int ret;

        if (table[i].reg == SENSOR_REG_DELAY) {
            os_delay_ms(table[i].delay_ms);
            continue;
        }

        for (unsigned retry = 0U; retry < 3U; ++retry) {
            ret = sensor_write_reg(table[i].reg, table[i].value);
            if (ret == 0) {
                break;
            }
        }

        if (ret != 0) {
            return ret;
        }
    }

    return 0;
}
```

设备 ID 校验必须放在初始化前：

```
static int sensor_check_id(void)
{
    uint8_t high;
    uint8_t low;

    if (sensor_read_reg(SENSOR_ID_HIGH, &high) != 0 ||
        sensor_read_reg(SENSOR_ID_LOW, &low) != 0) {
        return -EIO;
    }

    uint16_t id = ((uint16_t)high << 8) | low;

    if (id != SENSOR_EXPECTED_ID) {
        return -ENODEV;
    }

    return 0;
}
```

---

### 5.4 DMA 帧接收

对于固定尺寸的非压缩图像：

FrameBytes=Width×Height×BytesPerPixelFrameBytes=Width×Height×BytesPerPixel

RGB565 和 YUV422：

BytesPerPixel=2BytesPerPixel=2

RAW8：

BytesPerPixel=1BytesPerPixel=1

RAW10 的实际内存占用取决于接收器：

- 对齐到 16 bit：通常按 2 byte/pixel 保存。
- 紧凑打包：平均 1.25 byte/pixel。
- 硬件展开到 16 bit：2 byte/pixel。

#### 三缓冲状态机

推荐定义明确的缓冲所有权：

```
FREE -> CAPTURING -> READY -> PROCESSING -> FREE
```

不要让采集 DMA 写入 `PROCESSING` 状态的缓冲。

```
typedef enum {
    BUF_FREE = 0,
    BUF_CAPTURING,
    BUF_READY,
    BUF_PROCESSING
} cam_buf_state_t;

typedef struct {
    uintptr_t addr;
    size_t size;
    size_t payload;
    uint32_t sequence;
    cam_buf_state_t state;
} cam_buffer_t;
```

DMA 完成中断中只做最少工作：

```
void camera_dma_frame_done_isr(void)
{
    int index = camera_get_active_buffer();

    cache_invalidate_by_addr((void *)buffers[index].addr,
                             buffers[index].size);

    buffers[index].payload = camera_get_frame_length();
    buffers[index].sequence = ++frame_sequence;
    buffers[index].state = BUF_READY;

    int next = buffer_find_free(index);

    if (next < 0) {
        frame_drop_count++;
        camera_stop_capture();
        camera_raise_event(CAM_EVENT_NO_BUFFER);
        return;
    }

    buffers[next].state = BUF_CAPTURING;
    camera_start_dma((void *)buffers[next].addr, buffers[next].size);
    camera_raise_event(CAM_EVENT_FRAME_READY);
}
```

实际工程中，`cache_invalidate` 是否能在 ISR 执行取决于平台。更常见的方式是：

```
ISR:
    标记 buffer READY
    投递 frame event

Task:
    执行 Cache invalidate
    验证帧
    交给消费者
```

---

### 5.5 Cache 一致性

Cortex-M7、Cortex-M55、A 类应用处理器通常存在 D-Cache。DMA 和 CPU 看到的内存可能不同：

```
CPU 写 Cache
    |
    | 未 Clean
    v
内存仍是旧数据
    |
DMA 读取旧数据
```

接收摄像头时则相反：

```
DMA 写内存
    |
CPU Cache 仍保留旧 Cache Line
    |
CPU 读取到旧图像
```

必须满足：

- DMA 缓冲区按 Cache Line 对齐。
- 缓冲区长度按 Cache Line 对齐。
- DMA 写入后执行 invalidate。
- CPU 写入后 DMA 读取前执行 clean。
- 不要只对图像起始地址做 invalidate，必须覆盖完整范围。

```
#define CACHE_LINE_SIZE 32U

static uintptr_t align_down(uintptr_t value, uintptr_t align)
{
    return value & ~(align - 1U);
}

static uintptr_t align_up(uintptr_t value, uintptr_t align)
{
    return (value + align - 1U) & ~(align - 1U);
}

static void camera_rx_cache_invalidate(void *addr, size_t len)
{
    uintptr_t start = align_down((uintptr_t)addr, CACHE_LINE_SIZE);
    uintptr_t end = align_up((uintptr_t)addr + len, CACHE_LINE_SIZE);

    dcache_invalidate((void *)start, end - start);
    __DSB();
}
```

更高性能的方案：

- 将 DMA 缓冲区放在 non-cacheable MPU 区域。
- 使用片上 SRAM 的专用 DMA 区。
- 采集和处理分区，只有元数据进入 Cache。
- Linux 平台使用 DMA-BUF 统一管理缓存属性。

---

### 5.6 MIPI CSI-2 接收流程

MIPI CSI-2 接收器通常完成以下动作：

```
D-PHY 锁定
    |
Lane 状态检测
    |
HS 进入
    |
接收 CSI-2 Header
    |
校验 ECC
    |
接收 Payload
    |
校验 CRC
    |
根据 Virtual Channel/Data Type 路由
    |
写入 FIFO/DMA
    |
产生 Frame Start/Frame End
```

接收器关键配置：

```
typedef struct {
    uint8_t lane_count;
    uint32_t lane_rate_mbps;
    uint8_t virtual_channel;
    uint8_t data_type;
    uint16_t width;
    uint16_t height;
    bool continuous_clock;
} csi2_cfg_t;
```

Lane 速率估算：

Rlane=Width×Height×FPS×BitsPerPixel×OverheadLaneCountRlane​=LaneCountWidth×Height×FPS×BitsPerPixel×Overhead​

CSI-2 还存在协议和物理层开销，工程设计通常加入 10%~25% 裕量。

例如 1920×1080、30 FPS、RAW10、2 Lane：

Rpayload=1920×1080×30×10=622.08 Mbit/sRpayload​=1920×1080×30×10=622.08 Mbit/s

考虑 20% 裕量：

Rlane=622.08×1.22≈373.25 Mbit/sRlane​=2622.08×1.2​≈373.25 Mbit/s

因此每 Lane 至少应支持约 400 Mbps，工程上可能选择 500 Mbps 或更高档位。

#### CSI-2 错误分类

|错误|可能原因|
|---|---|
|PHY SoT Error|差分信号质量、时钟、终端匹配|
|ECC Error|Header 被破坏、信号完整性问题|
|CRC Error|Payload 被破坏、Lane 速率过高|
|Frame Sync Error|VS/FS/FE 丢失、Virtual Channel 错误|
|FIFO Overflow|DMA、DDR 或消费者吞吐不足|
|Data Type Error|传感器输出格式与接收器配置不一致|
|Lane Deskew Error|Lane 长度或 PHY 参数问题|

---

## 6. 性能量化分析

### 6.1 图像带宽

|分辨率|格式|帧大小|30 FPS 原始带宽|
|---|---|---|---|
|640×480|RGB565|614,400 B|18.43 MB/s|
|640×480|YUV422|614,400 B|18.43 MB/s|
|1280×720|RGB565|1,843,200 B|55.30 MB/s|
|1920×1080|RGB565|4,147,200 B|124.42 MB/s|
|1920×1080|RAW10 紧凑|2,592,000 B|77.76 MB/s|
|1920×1080|RAW10 对齐 16 bit|4,147,200 B|124.42 MB/s|

换算公式：

BandwidthMB/s=Width×Height×Bpp×FPS106BandwidthMB/s​=106Width×Height×Bpp×FPS​

注意：

- 这里是有效图像数据带宽。
- DVP 还需考虑水平、垂直消隐。
- MIPI 还需考虑包头、CRC、PHY 编码和空闲时间。
- DDR 总线实际占用通常高于图像写入带宽，因为存在读写、Cache、仲裁和突发效率损失。

### 6.2 帧缓冲内存

以 1920×1080 RGB565 为例：

```
单帧 = 1920 × 1080 × 2
     = 4,147,200 B
     ≈ 3.96 MiB
```

三缓冲：

```
≈ 11.87 MiB
```

若系统只有 512 KB SRAM，则必须：

- 降低分辨率。
- 使用外部 SDRAM/DDR。
- 使用 JPEG 输出。
- 使用 ROI 或硬件缩放。
- 使用分块处理，而不是整帧缓存。

### 6.3 DMA 传输时间

假设有效带宽为 100 MB/s：

```
640×480 RGB565:
614,400 / 100 MB/s ≈ 6.14 ms

1280×720 RGB565:
1,843,200 / 100 MB/s ≈ 18.43 ms
```

30 FPS 的帧周期为：

Tframe=130=33.33msTframe​=301​=33.33ms

如果采集、Cache 维护、颜色转换和推理总时间超过 33.33 ms，系统必须：

- 降低帧率。
- 丢弃旧帧。
- 使用流水线。
- 减小输入尺寸。
- 使用硬件加速。
- 允许消费者处理最新帧，而不是每一帧。

### 6.4 示例平台性能基线

以下数据是一个典型工程测量基线，假设平台为：

```
MCU: Cortex-M7，400 MHz
D-Cache: 32 KB，Cache Line 32 B
RAM: 外部 SDRAM，100 MHz
接口: DCMI + DMA
格式: RGB565
```

|操作|640×480|1280×720|
|---|---|---|
|DMA 写入|6.5~8.0 ms|19~24 ms|
|Cache invalidate|0.10~0.25 ms|0.30~0.75 ms|
|CPU RGB565 转灰度|1.5~3.0 ms|4.5~8.0 ms|
|双缓冲下最小安全队列|2 帧|3 帧|
|推荐处理预算|<25 ms|<25 ms|

这些数值会随 SDRAM 时序、DMA 突发长度、MPU 属性、编译器和其他总线主设备变化，必须在目标板上重新测量。

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
需要摄像头输入
 |
 +-- 分辨率 <= VGA，MCU 无 MIPI PHY？
 |       |
 |       +-- 是 --> 选择 DVP + DCMI
 |
 +-- SoC/MCU 是否集成 MIPI CSI-2 Receiver？
 |       |
 |       +-- 否 --> 选择 DVP，或增加外部桥接芯片
 |
 +-- 引脚资源是否紧张？
 |       |
 |       +-- 是 --> 选择 MIPI CSI-2
 |
 +-- 数据吞吐是否超过 DVP/MCU DMA能力？
 |       |
 |       +-- 是 --> 选择 MIPI CSI-2
 |
 +-- 需要 RAW10/RAW12、多摄像头或高帧率？
 |       |
 |       +-- 是 --> 选择 MIPI CSI-2
 |
 +-- 系统需要快速验证、低成本和易调试？
         |
         +-- 是 --> 选择 DVP + DCMI
```

### 7.2 典型场景

|场景|需求|方案|理由|
|---|---|---|---|
|MCU 图像采集|320×240、QVGA、15 FPS|DVP + DCMI|成本低、调试简单|
|LCD 取景器|640×480、RGB565、30 FPS|DCMI + DMA 双缓冲|带宽可控，接口直接|
|条码识别|1280×720、RAW8|DVP 或 CSI-2|取决于 MCU 内存和引脚|
|机器视觉|1920×1080、RAW10、60 FPS|CSI-2 2/4 Lane|DVP 引脚和吞吐不足|
|Linux 摄像头|多分辨率、自动曝光、ISP|CSI-2 + V4L2|支持媒体拓扑和 DMA-BUF|
|低功耗抓拍|低帧率 JPEG|DVP + JPEG DMA|降低内存和传输压力|
|多摄像头同步|2~4 路图像|CSI-2 + Virtual Channel 或多 Receiver|便于扩展和复用|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **传感器控制与接口接收解耦**  
    Sensor Driver 只负责寄存器和模式，DCMI/CSI Driver 只负责数据接收。
    
2. **所有初始化步骤可回滚**  
    时钟、GPIO、复位、I2C、接口、DMA、缓冲区都必须有失败路径。
    
3. **帧边界必须由硬件事件确认**  
    不要仅凭 DMA 传输完成判断一帧有效，尤其是 JPEG 或可变长度数据。
    
4. **ISR 不执行复杂图像处理**  
    ISR 只记录状态、切换缓冲区、发送事件。
    
5. **明确 Buffer Ownership**  
    每个缓冲区在任意时刻只能被 DMA、CPU 或消费者中的一个拥有。
    
6. **驱动提供统计信息**  
    至少统计帧数、丢帧数、DMA 溢出、同步错误、ECC/CRC 错误和最大处理延迟。
    

### 8.2 选型决策矩阵

|条件|DVP|CSI-2|
|---|---|---|
|低成本|5|3|
|易调试|5|2|
|低引脚数|2|5|
|高分辨率|2|5|
|高帧率|2|5|
|MCU 直接支持|5|依芯片|
|多摄像头扩展|2|5|
|PCB 要求|4|2|
|软件复杂度|4|2|

### 8.3 工业级编码规范

- 所有寄存器访问使用明确宽度类型。
- 所有超时使用绝对时间，不使用无限循环。
- 对分辨率、帧率、像素格式和 DMA 长度做整数溢出检查。
- 对 DMA 地址做对齐检查。
- 设备 ID、芯片版本和寄存器读回值必须校验。
- 中断状态必须先读出并清除，再执行事件处理。
- 不允许在图像缓冲中混用控制结构体和像素数据。
- 对 JPEG 使用实际帧长度，不使用固定长度向下游传递。
- 关闭摄像头时遵循：停止采集、停止 DMA、等待总线空闲、关闭时钟、拉低 PWDN。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：同步极性配置错误

错误代码：

```
dcmi_set_vsync_polarity(DCMI_POLARITY_LOW);
dcmi_set_hsync_polarity(DCMI_POLARITY_LOW);
```

根因：

- 传感器实际为高有效，而接收器配置成低有效。
- HREF 被误认为 HSYNC。
- 数据有效窗口被反转。

表现：

- 黑屏。
- 图像上下翻转或只有部分行。
- DMA 持续溢出。
- 帧完成事件不产生。

正确实现：

```
dcmi_set_vsync_polarity(sensor->vsync_active_high ?
                        DCMI_POLARITY_HIGH :
                        DCMI_POLARITY_LOW);

dcmi_set_hsync_polarity(sensor->hsync_active_high ?
                        DCMI_POLARITY_HIGH :
                        DCMI_POLARITY_LOW);
```

风险影响：

- 驱动可能表现为“偶尔能采到图像”，现场问题难以复现。
- 错误同步会导致后续所有像素位置失去意义。

---

### 9.2 错误二：忽略 Cache 一致性

错误代码：

```
void camera_frame_done(void)
{
    process_image(frame_buffer);
}
```

根因：

- DMA 已写入内存，但 CPU 读取了旧 Cache Line。
- 只有首地址对齐，长度没有覆盖完整 Cache Line。
- 使用普通 Cache API，未执行 `DSB`。

正确实现：

```
void camera_frame_done_task(void)
{
    size_t bytes = frame_width * frame_height * bytes_per_pixel;

    camera_rx_cache_invalidate(frame_buffer, bytes);
    process_image(frame_buffer);
}
```

风险影响：

- 图像部分区域更新、部分区域为旧帧。
- 现象具有随机性，与任务调度和 Cache 命中率有关。

---

### 9.3 错误三：DMA 缓冲区被消费者同时使用

错误代码：

```
void frame_ready_isr(void)
{
    camera_start_dma(frame_buffer, FRAME_SIZE);
    image_queue_send_from_isr(frame_buffer);
}
```

根因：

- DMA 重新写入缓冲区时，图像处理任务仍在读取。
- 没有定义缓冲区所有权。

正确实现：

```
typedef struct {
    uint8_t *addr;
    volatile bool dma_owned;
    volatile bool consumer_owned;
} frame_slot_t;

static bool frame_acquire_for_dma(frame_slot_t *slot)
{
    if (slot->dma_owned || slot->consumer_owned) {
        return false;
    }

    slot->dma_owned = true;
    return true;
}
```

风险影响：

- 图像撕裂。
- 一帧上半部分来自旧帧，下半部分来自新帧。
- AI 推理输入不稳定。

---

### 9.4 错误四：使用固定帧大小处理 JPEG

错误代码：

```
jpeg_decode(frame_buffer, WIDTH * HEIGHT * 2);
```

根因：

- JPEG 是可变长度码流。
- DMA 实际接收长度没有记录。
- 可能把下一帧残留数据当作当前帧内容。

正确实现：

```
size_t jpeg_len = camera_get_frame_length();

if (jpeg_len == 0U || jpeg_len > JPEG_BUFFER_SIZE) {
    camera_drop_frame();
    return;
}

jpeg_decode(frame_buffer, jpeg_len);
```

风险影响：

- 解码失败。
- 内存越界。
- 随机崩溃或异常重启。

---

### 9.5 错误五：只配置传感器，不验证接收器格式

错误代码：

```
sensor_set_format(SENSOR_FORMAT_RGB565);
dcmi_set_data_width(DCMI_DATA_WIDTH_8);
```

根因：

- 传感器输出总线宽度和 DCMI 配置不一致。
- RGB565 需要两个字节，接收器只接收一个字节。
- DVP 数据线高低字节接反。

正确实现：

```
if (sensor_format == SENSOR_FORMAT_RGB565) {
    dcmi_set_data_width(DCMI_DATA_WIDTH_8);
    sensor_set_byte_order(SENSOR_BYTE_ORDER_RGB565);
} else if (sensor_format == SENSOR_FORMAT_RAW10) {
    dcmi_set_data_width(DCMI_DATA_WIDTH_10);
}
```

风险影响：

- 颜色错乱。
- 图像尺寸看似正确，但所有像素值错误。
- 后端算法精度显著下降。

---

### 9.6 错误六：MIPI Lane 速率没有裕量

错误代码：

```
csi2_set_lane_rate(320); // Mbps
```

根因：

- 仅按有效像素带宽计算，没有考虑协议、PHY 和时钟偏差。
- 实际传感器输出使用了更高的 blanking。
- 供电噪声和 PCB 损耗导致边界速率不稳定。

正确实现：

```
uint32_t payload_mbps = width * height * fps * bits_per_pixel / 1000000U;
uint32_t lane_mbps = (payload_mbps * 120U) / (lane_count * 100U);

lane_mbps = csi2_round_supported_rate(lane_mbps);
csi2_set_lane_rate(lane_mbps);
```

风险影响：

- 常温正常，高温或低压下 CRC 错误。
- 高速连续运行后偶发丢帧。

---

## 10. 多机制组合使用方案

### 10.1 推荐架构

```
Sensor Power/Clock Manager
          |
          v
Sensor Control Driver <---- I2C/SCCB
          |
          v
DVP/DCMI 或 CSI-2 Receiver
          |
          v
DMA + Buffer Manager
          |
          v
Frame Event Dispatcher
          |
          +--> ISP/颜色转换
          +--> JPEG 编码
          +--> AI 推理
          +--> 显示
```

### 10.2 统一摄像头接口

```
typedef enum {
    CAM_IF_DVP_DCMI,
    CAM_IF_MIPI_CSI2
} cam_interface_t;

typedef enum {
    CAM_FMT_RGB565,
    CAM_FMT_YUV422,
    CAM_FMT_RAW8,
    CAM_FMT_RAW10,
    CAM_FMT_JPEG
} cam_format_t;

typedef struct {
    cam_interface_t interface;
    cam_format_t format;
    uint16_t width;
    uint16_t height;
    uint32_t fps;
    uint8_t lane_count;
} camera_config_t;

typedef struct {
    int (*power_on)(void);
    int (*power_off)(void);
    int (*set_mode)(const camera_config_t *cfg);
    int (*start)(void);
    int (*stop)(void);
    int (*get_frame)(cam_buffer_t **buf, uint32_t timeout_ms);
    int (*release_frame)(cam_buffer_t *buf);
} camera_ops_t;
```

### 10.3 启动流程

```
int camera_open(const camera_config_t *cfg)
{
    int ret;

    if (cfg == NULL || cfg->width == 0U ||
        cfg->height == 0U || cfg->fps == 0U) {
        return -EINVAL;
    }

    ret = camera_power_on();
    if (ret != 0) {
        return ret;
    }

    ret = sensor_check_id();
    if (ret != 0) {
        goto fail_power;
    }

    ret = sensor_set_mode(cfg);
    if (ret != 0) {
        goto fail_power;
    }

    ret = camera_interface_configure(cfg);
    if (ret != 0) {
        goto fail_power;
    }

    ret = camera_buffers_init(cfg);
    if (ret != 0) {
        goto fail_interface;
    }

    ret = camera_start();
    if (ret != 0) {
        goto fail_buffers;
    }

    return 0;

fail_buffers:
    camera_buffers_deinit();
fail_interface:
    camera_interface_deinit();
fail_power:
    camera_power_off();
    return ret;
}
```

### 10.4 生产者消费者模型

```
采集任务:
    等待 Frame Done
    标记 READY
    获取 FREE 缓冲区
    启动下一帧 DMA

处理任务:
    获取 READY
    Cache invalidate
    校验帧序号和长度
    执行 ISP/算法
    标记 FREE

监控任务:
    统计 FPS
    统计丢帧和错误
    超时时执行恢复
```

推荐策略：

- 实时显示：丢弃旧帧，处理最新帧。
- 视频编码：尽量保持顺序，背压或降低帧率。
- AI 推理：使用 latest-frame 策略，避免处理过期图像。
- 工业测量：不允许静默丢帧，必须上报采集完整性错误。

---

## 11. 工业级实际案例分析

### 11.1 案例一：STM32 DCMI + OV2640 + JPEG 抓拍

#### 需求

- 分辨率：1600×1200。
- 输出：JPEG。
- 触发方式：GPIO 外部触发。
- SRAM：512 KB。
- 需要将图像通过 USB 或以太网上传。

#### 架构

```
GPIO Trigger
    |
    v
RTOS Event
    |
    v
OV2640 切换 JPEG 模式
    |
    v
DCMI + DMA 接收
    |
    v
JPEG Buffer
    |
    +--> 文件系统
    +--> USB
    +--> 网络
```

#### 设计要点

- 使用 JPEG 输出避免存储完整 RGB565。
- DMA 缓冲区必须按最大 JPEG 尺寸预留。
- 使用帧结束事件获取真实码流长度。
- 连续模式下如果 JPEG 长度变化，必须使用接收器的实际计数器。
- 外部触发后增加传感器曝光稳定时间。
- 上传任务不能直接阻塞采集任务。

#### 核心代码

```
static int capture_one_jpeg(uint8_t *buf, size_t capacity,
                            size_t *actual_size)
{
    if (buf == NULL || actual_size == NULL || capacity == 0U) {
        return -EINVAL;
    }

    camera_flush_events();
    camera_dma_start(buf, capacity);

    int ret = camera_wait_frame_done(500U);
    if (ret != 0) {
        camera_dma_stop();
        return ret;
    }

    size_t length = camera_get_frame_length();
    camera_dma_stop();

    if (length == 0U || length > capacity) {
        return -EOVERFLOW;
    }

    camera_rx_cache_invalidate(buf, length);
    *actual_size = length;
    return 0;
}
```

---

### 11.2 案例二：工业视觉 SoC + MIPI CSI-2 + RAW10

#### 需求

- 1920×1080。
- 60 FPS。
- RAW10。
- 2 Lane CSI-2。
- 后端 ISP 做黑电平校正、去马赛克和白平衡。
- 延迟小于 50 ms。

#### 带宽

1920×1080×60×10=1.24416 Gbit/s1920×1080×60×10=1.24416 Gbit/s

考虑 20% 裕量：

1.493 Gbit/s1.493 Gbit/s

2 Lane 平均每 Lane：

746.6 Mbit/s746.6 Mbit/s

工程上至少选择 800 Mbps/Lane，最好根据 PHY 支持档位选择 1 Gbps/Lane。

#### 架构

```
Sensor RAW10
    |
    v
MIPI D-PHY 2 Lane
    |
    v
CSI-2 Receiver
    |
    v
ISP DMA-BUF
    |
    v
ISP
    |
    +--> DDR YUV
    +--> AI Accelerator
```

#### 设计要点

- RAW10 是压缩打包格式，不要假设一个像素占一个字节。
- CSI Receiver 的 Data Type 必须配置为 RAW10。
- 使用 DMA-BUF 共享缓冲，减少 CPU 拷贝。
- ISP 输入输出缓冲区分别建立队列。
- 监测 ECC、CRC、FIFO Overflow 和 Frame Sync。
- 使用硬件时间戳关联图像帧和工业触发信号。

---

### 11.3 案例三：双摄像头 CSI-2 + Virtual Channel

#### 需求

- 两颗摄像头同时采集。
- 每路 1280×720、30 FPS。
- 共用一组物理 CSI-2 Lane。
- 后端需要区分左右相机。

#### 架构

```
Camera A -> VC0
Camera B -> VC1
              |
              v
       CSI-2 Aggregator
              |
              v
       CSI Receiver
        |           |
      VC0         VC1
        |           |
      DMA A       DMA B
```

#### 设计要点

- 每个摄像头必须使用唯一 Virtual Channel。
- 接收器应依据 `Virtual Channel + Data Type` 路由数据。
- 两路 DMA 缓冲池必须隔离。
- 帧同步要记录各路 SOF 时间戳。
- 若两路帧时间差超过阈值，应丢弃未配对帧。

```
typedef struct {
    uint32_t sequence;
    uint64_t timestamp_us;
    cam_buffer_t *buffer;
} stereo_frame_t;

static bool stereo_pair_valid(const stereo_frame_t *left,
                              const stereo_frame_t *right)
{
    if (left == NULL || right == NULL) {
        return false;
    }

    uint64_t delta = (left->timestamp_us > right->timestamp_us) ?
                     (left->timestamp_us - right->timestamp_us) :
                     (right->timestamp_us - left->timestamp_us);

    return delta <= 1000U; /* 允许 1 ms 时间差 */
}
```

---

## 12. 高频问题深度答疑

### 问题一：DVP 和 DCMI 是同一种东西吗？

不是。

- DVP 是摄像头输出接口规范，描述并行数据和同步信号。
- DCMI 是 MCU 内部的数字摄像头接收外设。
- DCMI 通常用于接收 DVP，但不同 MCU 的 DCMI 能力不同。
- DCMI 不能直接替代 MIPI CSI-2 Receiver。

---

### 问题二：为什么图像有颜色但严重偏色？

常见原因按优先级排查：

1. RGB565 字节顺序错误。
2. RGB/BGR 通道顺序错误。
3. 传感器输出实际是 YUV422，但接收器按 RGB565 解释。
4. UV 顺序为 UYVY 与 YUYV 不匹配。
5. 传感器 ISP 未正确配置白平衡或色彩矩阵。
6. DVP 数据线高低位连接错误。

建议使用固定色块或彩条模式，不要直接通过自然图像判断。

---

### 问题三：为什么低分辨率正常，高分辨率花屏？

常见原因：

- PCLK 随分辨率提升，超过接收器或 DMA 能力。
- SDRAM 带宽不足。
- DMA FIFO 阈值或突发长度不合适。
- Cache 维护时间增加，处理任务无法及时释放缓冲区。
- DVP 数据线建立保持时间不足。
- MIPI Lane 速率不够或 PHY 裕量不足。

应同时观测：

```
PCLK 频率
DMA Overflow
FIFO Level
Frame Period
CPU 占用率
DDR 带宽
Cache Miss
CRC/ECC 错误
```

---

### 问题四：应该使用双缓冲还是三缓冲？

- **双缓冲**：延迟低、内存少，适合采集和显示速度接近的系统。
- **三缓冲**：抗抖动能力更好，适合采集、处理、显示三个异步阶段。
- **环形缓冲**：适合视频流和连续采集，但必须定义满时策略。

若处理时间接近帧周期，双缓冲容易出现缓冲耗尽。对于 30 FPS 图像处理，通常优先采用三缓冲。

---

### 问题五：MIPI CRC 错误一定是软件配置错误吗？

不一定。

CRC 错误说明 Payload 校验失败，可能原因包括：

- Lane 速率过高。
- 差分阻抗不连续。
- 电源噪声。
- 连接器或柔性板信号质量问题。
- 传感器输出电压不匹配。
- PHY 终端或 settle time 参数不合适。
- 时钟 Lane 抖动过大。

软件应记录：

```
错误计数
发生时的 Lane 速率
当前温度和电压
帧序号
Virtual Channel
Data Type
PHY 状态
```

这样才能区分配置错误和物理层边界问题。

---

### 问题六：为什么不能在帧完成中断中直接调用图像算法？

原因：

- 算法执行时间不可预测。
- 中断上下文可能禁止阻塞。
- 高优先级中断被长期屏蔽。
- Cache 操作和浮点运算会放大中断延迟。
- 下一帧 DMA 可能因缓冲区未释放而溢出。

正确模型是：

```
ISR 只做:
    读取状态
    保存错误码
    切换 Buffer
    发送事件

任务做:
    Cache 维护
    图像校验
    ISP/算法
    释放 Buffer
```

---

## 13. 课程核心总结

### 核心要点

- **DVP 是并行物理接口，DCMI 是 MCU 接收外设，CSI-2 是高速串行协议。**
- DVP/DCMI 的关键是同步极性、PCLK 采样边沿、数据宽度和 DMA。
- CSI-2 的关键是 Lane 数、Lane 速率、PHY 状态、Virtual Channel、Data Type 和 ECC/CRC。
- 图像采集系统的瓶颈通常不是单一接口，而是：

```
传感器输出速率
    + 接收器 FIFO
    + DMA 吞吐
    + Cache 维护
    + 内存带宽
    + 图像处理时间
    + 缓冲区数量
```

### 性能排序

在相同有效图像带宽下：

```
CPU 拷贝 < DMA 单缓冲 < DMA 双缓冲 < DMA 三缓冲 + 零拷贝
```

在可扩展性上：

```
低分辨率 DVP > 单路 CSI-2 > 多 Lane CSI-2 > 多摄像头 CSI-2 + Virtual Channel
```

### 通用选型结论

- **低成本、低分辨率、快速调试：DVP + DCMI。**
- **MCU 需要持续采集：DCMI + DMA + 双/三缓冲。**
- **高分辨率、高帧率、RAW10/RAW12、多摄像头：MIPI CSI-2。**
- **Linux 多媒体系统：CSI-2 + V4L2 + Media Controller + DMA-BUF。**
- **内存紧张但传感器支持压缩：JPEG 输出优先。**
- **图像算法需要原始动态范围：RAW8/RAW10，配合 ISP。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|需求|推荐方案|
|---|---|
|QVGA/VGA，低成本|DVP|
|STM32 摄像头采集|DCMI + DVP|
|RGB565 显示|DVP/DCMI|
|JPEG 抓拍|DVP/DCMI JPEG 模式|
|1080p 30 FPS|CSI-2|
|1080p 60 FPS RAW10|CSI-2 2 Lane 或 4 Lane|
|多摄像头|CSI-2 Virtual Channel|
|Linux 摄像头框架|CSI-2 + V4L2|
|片上 SRAM 很小|JPEG、ROI、分块或外部 DDR|
|低延迟 AI|CSI-2 + DMA-BUF + 零拷贝|

### 14.2 特性对比表

|项目|DVP/DCMI|MIPI CSI-2|
|---|---|---|
|同步方式|VSYNC/HSYNC/PCLK|CSI-2 Short/Long Packet|
|错误检测|Overflow/Sync Error|PHY/ECC/CRC/FIFO|
|带宽扩展|增加并行位宽或 PCLK|增加 Lane 数或速率|
|软件重点|GPIO、极性、DMA|PHY、协议、包路由|
|硬件重点|并行线时序|差分阻抗和长度匹配|
|缓冲要求|固定帧常见|固定帧或可变帧|
|调试工具|逻辑分析仪|高速示波器、协议分析仪|

### 14.3 关键公式

```
FrameBytes = Width × Height × BytesPerPixel

FramePeriod = 1 / FPS

FPS = PCLK / (HTS × VTS)

MIPI LaneRate =
Width × Height × FPS × BitsPerPixel × Overhead / LaneCount
```

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  DVP、DCMI、CSI-2 三者分别处于哪一层。
- [ ]  如何通过示波器确认 PCLK、HSYNC、VSYNC 极性。
- [ ]  RGB565 每像素占用多少字节，YUV422 如何计算平均带宽。
- [ ]  为什么 DMA 接收图像时需要 Cache invalidate。
- [ ]  如何设计 `FREE/CAPTURING/READY/PROCESSING` 缓冲状态机。
- [ ]  JPEG 为什么必须使用实际帧长度。
- [ ]  如何计算 1920×1080 RAW10 30 FPS 的 MIPI Lane 速率。
- [ ]  ECC 错误与 CRC 错误的定位方向有什么不同。
- [ ]  双缓冲和三缓冲分别适合什么场景。
- [ ]  如何让摄像头驱动在 DMA 溢出后完成自动恢复。
- [ ]  如何保证多摄像头帧之间的时间配对。
- [ ]  如何避免 ISR 中执行不可预测的图像处理。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：DVP 基础采集

目标：

- 使用 OV7670 或 OV2640。
- 配置 320×240 RGB565。
- 通过逻辑分析仪确认 `PCLK`、`HREF`、`VSYNC`。
- 使用 DMA 将一帧写入 SRAM。

验收标准：

```
连续采集 1000 帧
帧完成率 >= 99.9%
无 DMA Overflow
图像颜色正确
```

#### 任务二：DCMI 双缓冲

目标：

- 增加双缓冲。
- 采集任务和显示任务并行工作。
- 统计帧率、丢帧数和最大处理时间。
- 加入 DMA 超时恢复。

验收标准：

```
30 FPS 连续运行 30 分钟
无死锁
无缓冲区越界
丢帧原因可统计
```

#### 任务三：Cache 一致性验证

测试方法：

1. DMA 写入图像。
2. CPU 不执行 invalidate，读取固定像素。
3. CPU 执行 invalidate，再次读取同一像素。
4. 比较两次结果。
5. 改变缓冲区对齐和长度，验证边界行为。

验收重点：

- 能解释旧 Cache 数据来源。
- 能验证 Cache Line 对齐要求。
- 能确认 MPU non-cacheable 区域的收益和代价。

#### 任务四：MIPI CSI-2 带宽设计

目标：

- 设计 1280×720 RAW10 60 FPS 系统。
- 计算有效 Payload、协议裕量和 Lane 速率。
- 配置 Data Type、Virtual Channel 和 Frame Event。
- 统计 ECC、CRC、FIFO 错误。

验收标准：

```
连续运行 8 小时
CRC/ECC 错误为 0
帧率抖动小于 1%
无 DDR 带宽溢出
```

#### 任务五：多摄像头同步采集

目标：

- 两路 CSI-2 或两路 DVP。
- 为每帧记录硬件时间戳。
- 实现帧配对和超时丢弃。
- 测试不同曝光时间和帧率下的同步误差。

验收标准：

```
帧配对成功率 >= 99.99%
时间差统计可输出
异常帧能够定位到具体通道
```

### 16.2 性能测试方法

必须至少测量：

```
采集 FPS
帧完成延迟
DMA 传输时间
Cache 维护时间
图像处理时间
缓冲区占用率
丢帧计数
DMA/FIFO 错误
CSI-2 ECC/CRC 错误
DDR 带宽利用率
```

推荐使用硬件时间戳：

```
typedef struct {
    uint32_t frame_sequence;
    uint32_t sof_timestamp;
    uint32_t eof_timestamp;
    uint32_t process_start;
    uint32_t process_end;
    uint32_t error_flags;
} camera_frame_stat_t;
```

处理预算：

Tcapture+Tcache+Tprocess+Tqueue<TframeTcapture​+Tcache​+Tprocess​+Tqueue​<Tframe​

若无法满足，应优先采取：

1. 降低输入分辨率。
2. 使用硬件缩放。
3. 降低帧率。
4. 改用 latest-frame 丢帧策略。
5. 使用零拷贝。
6. 使用 ISP、DSP、GPU 或 NPU。

### 16.3 进阶学习方向

- CSI-2 v2.x 数据类型、Virtual Channel 和多流路由。
- MIPI D-PHY/C-PHY 物理层调试。
- Linux V4L2 Subdev、Media Controller 和异步绑定。
- DMA-BUF、IOMMU 和零拷贝视频管线。
- ISP 统计模块、3A 算法和 RAW Bayer 处理。
- HDR、DOL-WDR 和多曝光帧组合。
- 摄像头硬件同步、FSIN/VSYNC 触发和时间戳对齐。
- GStreamer、libcamera 和硬件视频编码器协同。
- 摄像头链路安全、固件签名和恶意图像输入防护。
- 面向 AI 的图像预处理、量化和 NPU 内存规划。