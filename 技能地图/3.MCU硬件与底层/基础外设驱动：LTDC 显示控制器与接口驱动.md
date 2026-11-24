
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 LTDC（LCD-TFT Display Controller）的硬件组成、像素时序与帧缓冲模型。
- 理解 RGB 并行接口中 HSYNC、VSYNC、DE、PCLK 的电气与时序关系。
- 理解显示控制器、显存、图形层、像素格式、DMA 与 Cache 之间的关系。
- 理解 tearing、行同步、双缓冲、局部刷新和垂直空白期的底层机制。

### 掌握

能够：

- 根据屏幕规格书计算 LTDC 时序寄存器参数。
- 配置 RGB565、RGB888、ARGB8888 等常见像素格式。
- 配置单层、双层显示区域以及透明混合。
- 正确计算 framebuffer 地址、stride、行长度和起始偏移。
- 处理 Cortex-M7/M33 D-Cache 与 LCD-TFT DMA 之间的数据一致性问题。
- 使用 DMA2D 配合 LTDC 完成填充、拷贝、像素格式转换和 Alpha 混合。

### 精通

能够分析：

- LTDC 黑屏、偏色、花屏、撕裂、错行、局部闪烁等现场问题。
- 显示带宽、总线竞争、帧率下降和 CPU 占用之间的定量关系。
- 双缓冲、三缓冲、局部刷新、TE 同步和整帧刷新方案的实时性权衡。
- LTDC 与 SDRAM、QSPI、DMA2D、GUI 框架以及 RTOS 显示线程之间的系统耦合。

### 能够设计

能够设计：

- 面向 STM32 高级 MCU 的工业级 LTDC 显示驱动抽象层。
- 支持 framebuffer、图层、双缓冲、Cache 管理和 VSYNC 同步的显示架构。
- 针对不同 RAM 资源、分辨率和刷新率的显示方案。
- 可被 LVGL、emWin、自研 GUI 或产品业务层复用的 BSP 显示接口。

---

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、数组、位操作和内存模型。
- MCU 时钟树、GPIO 复用、DMA 和中断。
- SRAM、SDRAM、Flash、总线矩阵和 Cache 基础。
- RGB565、RGB888、ARGB8888 等像素格式。
- RTOS 任务、信号量、事件组和互斥锁。
- 基本的示波器或逻辑分析仪使用方法。

### 技能要求

- 能阅读 MCU Reference Manual 中的时序和寄存器章节。
- 能根据显示屏 datasheet 读取 timing 参数。
- 能使用示波器测量 PCLK、HSYNC、VSYNC、DE。
- 能定位 linker script 中的内存区域。
- 能编译、下载和调试 STM32 HAL/LL 工程。
- 能使用 DMA2D 或类似图形 DMA 外设。

---

## 3. 技术概述

### 3.1 LTDC 的定义

LTDC 是 MCU 内部的专用 LCD-TFT 显示控制器，主要负责：

1. 从帧缓冲区读取像素数据。
2. 按照配置的时序产生显示扫描信号。
3. 对多个图层进行 Alpha 混合。
4. 将像素数据通过 RGB 并行接口发送给外部 LCD。
5. 在指定位置产生行中断、帧中断或错误中断。

LTDC **本身通常不负责绘图**。它只负责持续扫描 framebuffer。绘图、清屏、拷贝和格式转换通常由 CPU、DMA2D、GPU 或 GUI 框架完成。

### 3.2 RGB 并行接口信号

典型 RGB 接口包括：

|信号|作用|
|---|---|
|`PCLK`|像素时钟，每个有效像素对应一个像素时钟周期|
|`HSYNC`|行同步信号，标记一行扫描边界|
|`VSYNC`|场同步信号，标记一帧扫描边界|
|`DE`|Data Enable，有效显示区域指示|
|`R[ ]`|红色像素数据|
|`G[ ]`|绿色像素数据|
|`B[ ]`|蓝色像素数据|

常见 RGB 屏幕工作方式：

```
一帧
+----------------------------------------------------------+
| 垂直前肩 Vertical Front Porch                           |
|                                                          |
| 垂直有效区                                               |
|   行 0:  HSYNC | HBP | Active Pixels | HFP               |
|   行 1:  HSYNC | HBP | Active Pixels | HFP               |
|   ...                                                    |
|                                                          |
| 垂直后肩 Vertical Back Porch                            |
+----------------------------------------------------------+
```

### 3.3 主流实现分支

|方案|控制方式|典型用途|
|---|---|---|
|MCU LTDC + RGB|MCU 持续输出 RGB 时序|中高分辨率 TFT|
|MCU SPI/QSPI + LCD 控制器|MCU 发送命令和像素数据|小尺寸屏、低引脚数|
|MCU LTDC + 外部 RGB 转换芯片|MCU 输出 RGB，外部转换|HDMI、LVDS、MIPI 桥接|
|MCU LTDC + SDRAM framebuffer|显存位于外部 SDRAM|WVGA、720p 等较大分辨率|
|MCU LTDC + DMA2D|LTDC 扫描，DMA2D 加速绘图|工业 HMI、仪表盘|
|MCU + GPU/专用显示引擎|硬件合成与加速|高级 GUI、多层复杂 UI|

---

## 4. 核心特性横向对比

### 4.1 LTDC 与 SPI/QSPI 显示方案对比

|维度|LTDC RGB|SPI LCD 控制器|QSPI/8080 类接口|
|---|---|---|---|
|显存模型|MCU framebuffer|通常在 LCD 内部|依赖控制器配置|
|刷新方式|持续扫描|主机主动写入|主机主动写入|
|CPU/DMA 负担|主要是显存访问|主要是总线传输|主要是总线传输|
|最大刷新能力|高|中低|中高|
|引脚数量|较多|少|中等|
|撕裂控制|依赖同步/双缓冲|依赖 TE 和更新窗口|依赖 TE 和更新窗口|
|多图层|通常支持|通常不支持|取决于 LCD 控制器|
|Alpha 混合|硬件支持|软件预合成|软件预合成|
|典型分辨率|480×272、800×480、1280×800|240×320、320×480|480×800、480×272|
|功耗|较高，持续输出|刷新时较高|刷新时较高|
|适用场景|高刷新率、复杂 GUI|低成本、小屏|中等分辨率、引脚受限|

### 4.2 像素格式对比

|格式|每像素字节数|颜色数|典型带宽|优点|缺点|
|---|---|---|---|---|---|
|RGB565|2|65,536|低|显存和带宽小|无 Alpha，颜色精度低|
|RGB888|3|16.7M|中|颜色质量高|非 32 位对齐，访问复杂|
|ARGB8888|4|16.7M + Alpha|高|Alpha 混合方便|显存和带宽最高|
|L8|1|256 色|很低|显存小|依赖 CLUT|
|AL44|1|16 色 + 4 位 Alpha|很低|适合图标|色彩有限|
|AL88|2|256 色 + 8 位 Alpha|低|Alpha 精细|需要调色板|

### 4.3 缓冲策略对比

|策略|显存需求|撕裂风险|延迟|适用场景|
|---|---|---|---|---|
|单缓冲|1 帧|高|低|静态页面、低要求界面|
|双缓冲|2 帧|低|1 帧以内|动态 UI、仪表盘|
|三缓冲|3 帧|很低|可控|高负载动画、异步渲染|
|局部缓冲|小于 1 帧|取决于同步|低|小区域更新、资源受限|
|前后端分离|2 帧或更多|低|可控|GUI 框架、RTOS 产品|

---

## 5. 底层原理与功能特性深度解析

## 5.1 LTDC 时序计算

假设屏幕规格书提供：

```
Active Width   = 800
Active Height  = 480
HSYNC          = 1
HBP            = 46
HFP            = 16
VSYNC          = 1
VBP            = 23
VFP            = 7
```

LTDC 的累计边界通常按如下方式计算：

```
AccumulatedHBP = HSYNC + HBP
AccumulatedActiveW = HSYNC + HBP + Active Width
TotalWidth = HSYNC + HBP + Active Width + HFP

AccumulatedVBP = VSYNC + VBP
AccumulatedActiveH = VSYNC + VBP + Active Height
TotalHeight = VSYNC + VBP + Active Height + VFP
```

因此：

```
AccumulatedHBP      = 1 + 46 = 47
AccumulatedActiveW  = 1 + 46 + 800 = 847
TotalWidth          = 1 + 46 + 800 + 16 = 863

AccumulatedVBP      = 1 + 23 = 24
AccumulatedActiveH  = 1 + 23 + 480 = 504
TotalHeight         = 1 + 23 + 480 + 7 = 511
```

像素时钟：

```
PCLK = TotalWidth × TotalHeight × RefreshRate
```

当刷新率为 60 Hz：

```
PCLK = 863 × 511 × 60
     ≈ 26.46 MHz
```

实际项目中应以屏幕规格书要求为准。PCLK 偏差过大可能导致：

- 屏幕无显示；
- 图像水平偏移；
- 行抖动；
- 垂直滚动；
- 颜色或数据采样错误；
- 高温或低电压时不稳定。

### HAL 配置示例

```
static LTDC_HandleTypeDef hltdc;

static void ltdc_init(void)
{
    hltdc.Instance = LTDC;

    hltdc.Init.HSPolarity = LTDC_HSPOLARITY_AL;
    hltdc.Init.VSPolarity = LTDC_VSPOLARITY_AL;
    hltdc.Init.DEPolarity = LTDC_DEPOLARITY_AL;
    hltdc.Init.PCPolarity = LTDC_PCPOLARITY_IPCLK;

    hltdc.Init.HorizontalSync = 1U;
    hltdc.Init.VerticalSync = 1U;

    hltdc.Init.AccumulatedHBP = 47U;
    hltdc.Init.AccumulatedVBP = 24U;

    hltdc.Init.AccumulatedActiveW = 847U;
    hltdc.Init.AccumulatedActiveH = 504U;

    hltdc.Init.TotalWidth = 863U;
    hltdc.Init.TotalHeigh = 511U;

    hltdc.Init.Backcolor.Red = 0U;
    hltdc.Init.Backcolor.Green = 0U;
    hltdc.Init.Backcolor.Blue = 0U;

    if (HAL_LTDC_Init(&hltdc) != HAL_OK) {
        system_fault(SYSTEM_FAULT_LTDC_INIT);
    }
}
```

注意：不同 STM32 系列 HAL 字段命名和极性定义可能不同，应以对应芯片头文件和 Reference Manual 为准。

---

## 5.2 图层窗口与 framebuffer 地址

一个图层通常包含：

```
窗口左边界 WindowX0
窗口右边界 WindowX1
窗口上边界 WindowY0
窗口下边界 WindowY1
像素格式 PixelFormat
显存地址 FBStartAdress
行长度 ImageWidth
行数量 ImageHeight
行间距 Pitch
```

显示窗口坐标相对于有效显示区：

```
layer_cfg.WindowX0 = 0U;
layer_cfg.WindowX1 = 800U;
layer_cfg.WindowY0 = 0U;
layer_cfg.WindowY1 = 480U;

layer_cfg.ImageWidth  = 800U;
layer_cfg.ImageHeight = 480U;
```

RGB565 framebuffer：

```
#define LCD_WIDTH       800U
#define LCD_HEIGHT      480U
#define LCD_BPP_BYTES   2U

static uint16_t framebuffer[LCD_WIDTH * LCD_HEIGHT]
    __attribute__((section(".framebuffer"), aligned(32)));
```

地址计算：

```
static inline uintptr_t framebuffer_pixel_address(uint32_t x, uint32_t y)
{
    return (uintptr_t)&framebuffer[y * LCD_WIDTH + x];
}
```

当 framebuffer 每行存在对齐填充时，不能使用 `width * bytes_per_pixel` 作为固定假设，应显式维护 stride：

```
typedef struct {
    uint8_t  *base;
    uint32_t  width;
    uint32_t  height;
    uint32_t  stride_bytes;
    uint32_t  bytes_per_pixel;
} framebuffer_t;

static uint8_t *framebuffer_at(const framebuffer_t *fb,
                               uint32_t x,
                               uint32_t y)
{
    if (fb == NULL ||
        x >= fb->width ||
        y >= fb->height) {
        return NULL;
    }

    return fb->base + y * fb->stride_bytes
                  + x * fb->bytes_per_pixel;
}
```

### 关键约束

- framebuffer 必须位于 LTDC 可访问的内存区域。
- 该内存不能被 MPU 配置为不可访问。
- 外部 SDRAM 必须先完成 FMC 初始化和内存校准。
- stride 必须满足 LTDC 图层行长度寄存器的格式要求。
- framebuffer 起始地址必须满足 DMA 和 Cache 对齐要求。
- 不能把普通片上 Flash 地址误配置为动态 framebuffer。

---

## 5.3 像素格式与字节序

### RGB565

RGB565 编码：

```
bit[15:11] Red   5 bit
bit[10:5]  Green 6 bit
bit[4:0]   Blue  5 bit
```

代码：

```
static uint16_t rgb888_to_rgb565(uint8_t r, uint8_t g, uint8_t b)
{
    return (uint16_t)(((uint16_t)(r & 0xF8U) << 8) |
                      ((uint16_t)(g & 0xFCU) << 3) |
                      ((uint16_t)b >> 3));
}
```

反向转换：

```
static void rgb565_to_rgb888(uint16_t pixel,
                             uint8_t *r,
                             uint8_t *g,
                             uint8_t *b)
{
    if (r == NULL || g == NULL || b == NULL) {
        return;
    }

    *r = (uint8_t)(((pixel >> 11) & 0x1FU) * 255U / 31U);
    *g = (uint8_t)(((pixel >> 5)  & 0x3FU) * 255U / 63U);
    *b = (uint8_t)((pixel & 0x1FU) * 255U / 31U);
}
```

### ARGB8888

ARGB8888 通常表示为：

```
31:24 Alpha
23:16 Red
15:8  Green
7:0   Blue
```

代码：

```
static uint32_t argb8888_pack(uint8_t a,
                              uint8_t r,
                              uint8_t g,
                              uint8_t b)
{
    return ((uint32_t)a << 24) |
           ((uint32_t)r << 16) |
           ((uint32_t)g << 8)  |
           (uint32_t)b;
}
```

实际内存中的字节顺序受 MCU 端序和总线访问方式影响。遇到偏色问题时，不应只调整 RGB 数据，还应确认：

- LTDC 像素格式选择；
- GPIO 数据线到 LCD 的物理连接；
- R/G/B 位线顺序；
- 是否存在数据线反接或错位；
- 屏幕控制器对 RGB565 的字节采样顺序。

---

## 5.4 多图层与 Alpha 混合

典型图层合成：

```
Output = Foreground × Alpha + Background × (1 - Alpha)
```

对于 8 位 Alpha：

```
static uint8_t alpha_blend_channel(uint8_t fg,
                                    uint8_t bg,
                                    uint8_t alpha)
{
    uint32_t value = (uint32_t)fg * alpha +
                     (uint32_t)bg * (255U - alpha);

    return (uint8_t)((value + 127U) / 255U);
}
```

LTDC 的硬件混合可以避免 CPU 对整帧图像逐像素合成。适合：

- 状态栏叠加；
- 半透明弹窗；
- 图标层；
- 视频层与 UI 层；
- 指针或告警标记。

设计时应注意：

- 图层顺序决定最终视觉结果。
- Alpha 叠加会增加带宽。
- 两个全屏 ARGB8888 图层会显著增加 SDRAM 总线压力。
- 图层混合效果依赖预乘 Alpha 还是非预乘 Alpha 的约定。
- GUI 框架生成的像素格式必须和 LTDC 配置一致。

---

## 5.5 DMA2D 协同

LTDC 负责读，DMA2D 负责搬运和图形操作。

### 颜色填充

```
static HAL_StatusTypeDef lcd_fill_rgb565(uint16_t *dst,
                                         uint32_t pixel_count,
                                         uint16_t color)
{
    if (dst == NULL || pixel_count == 0U) {
        return HAL_ERROR;
    }

    DMA2D_HandleTypeDef hdma2d = {0};

    hdma2d.Instance = DMA2D;
    hdma2d.Init.Mode = DMA2D_R2M;
    hdma2d.Init.ColorMode = DMA2D_OUTPUT_RGB565;
    hdma2d.Init.OutputOffset = 0U;

    if (HAL_DMA2D_Init(&hdma2d) != HAL_OK) {
        return HAL_ERROR;
    }

    if (HAL_DMA2D_Start(&hdma2d,
                        color,
                        (uintptr_t)dst,
                        pixel_count,
                        1U) != HAL_OK) {
        return HAL_ERROR;
    }

    if (HAL_DMA2D_PollForTransfer(&hdma2d, 100U) != HAL_OK) {
        return HAL_TIMEOUT;
    }

    return HAL_OK;
}
```

生产代码中不建议每次操作都临时初始化 DMA2D。应在系统启动时初始化一次，然后通过互斥锁或图形服务线程统一访问。

### 二维区域填充

```
typedef struct {
    uint16_t *base;
    uint32_t  width;
    uint32_t  height;
} rgb565_surface_t;

static HAL_StatusTypeDef surface_fill_rect(rgb565_surface_t *surface,
                                           uint32_t x,
                                           uint32_t y,
                                           uint32_t width,
                                           uint32_t height,
                                           uint16_t color)
{
    if (surface == NULL ||
        surface->base == NULL ||
        width == 0U ||
        height == 0U ||
        x >= surface->width ||
        y >= surface->height ||
        width > surface->width - x ||
        height > surface->height - y) {
        return HAL_ERROR;
    }

    for (uint32_t row = 0U; row < height; ++row) {
        uint16_t *line = &surface->base[
            (y + row) * surface->width + x
        ];

        /*
         * 实际产品中可使用 DMA2D M2M 或 R2M 替代该循环。
         * 这里保留二维地址关系，便于理解 stride。
         */
        for (uint32_t col = 0U; col < width; ++col) {
            line[col] = color;
        }
    }

    return HAL_OK;
}
```

---

## 5.6 Cache 与 DMA 一致性

Cortex-M7 常见问题：

1. CPU 修改 framebuffer，仅修改了 D-Cache。
2. LTDC DMA 从 SRAM/SDRAM 读取旧内容。
3. 屏幕仍显示旧图像。

CPU 写回内存前，需要执行 Clean：

```
static void display_clean_region(void *address, size_t size)
{
    uintptr_t start = (uintptr_t)address;
    uintptr_t end = start + size;

    start &= ~(uintptr_t)31U;
    end = (end + 31U) & ~(uintptr_t)31U;

    SCB_CleanDCache_by_Addr((uint32_t *)start,
                            (int32_t)(end - start));
    __DSB();
}
```

当 DMA2D 或 LTDC 写入内存、CPU 随后读取时，需要 Invalidate：

```
static void display_invalidate_region(void *address, size_t size)
{
    uintptr_t start = (uintptr_t)address;
    uintptr_t end = start + size;

    start &= ~(uintptr_t)31U;
    end = (end + 31U) & ~(uintptr_t)31U;

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                 (int32_t)(end - start));
    __DSB();
}
```

工程注意事项：

- Cache line 通常为 32 字节，但必须以具体 Cortex-M 内核为准。
- 地址和长度应按 Cache line 对齐。
- 对局部刷新区域执行 Cache 操作时，必须覆盖实际字节范围。
- 如果多个对象共享同一 Cache line，Clean/Invalidate 可能影响相邻数据。
- 可将 framebuffer 放入 MPU 配置为 non-cacheable 的区域，简化一致性，但通常会降低 CPU 绘图性能。
- 推荐方案通常是：**Cacheable framebuffer + 明确 Clean 策略**。

---

## 5.7 VSYNC、行中断与撕裂控制

撕裂发生的根因：

```
LTDC 正在从 framebuffer 的前半部分读取
CPU/DMA2D 同时修改同一个 framebuffer 的后半部分
一帧图像包含两个不同时间点的数据
```

### 双缓冲流程

```
Buffer A: LTDC 当前扫描
Buffer B: GUI/CPU/DMA2D 正在绘制

绘制完成
    |
Clean D-Cache
    |
等待 VSYNC
    |
切换 LTDC framebuffer 地址
    |
Buffer B 成为显示缓冲
    |
Buffer A 成为下一次绘制缓冲
```

切换示例：

```
static volatile uint32_t displayed_buffer;

static HAL_StatusTypeDef display_request_buffer(uint32_t buffer_index)
{
    if (buffer_index > 1U) {
        return HAL_ERROR;
    }

    uintptr_t address = (buffer_index == 0U) ?
                        (uintptr_t)framebuffer0 :
                        (uintptr_t)framebuffer1;

    display_clean_region((void *)address,
                         LCD_WIDTH * LCD_HEIGHT * LCD_BPP_BYTES);

    if (HAL_LTDC_SetAddress_NoReload(&hltdc,
                                     address,
                                     LTDC_LAYER_1) != HAL_OK) {
        return HAL_ERROR;
    }

    displayed_buffer = buffer_index;
    return HAL_OK;
}
```

在 VSYNC 或垂直空白期执行 reload：

```
static HAL_StatusTypeDef display_reload_at_vsync(void)
{
    return HAL_LTDC_Reload(&hltdc,
                           LTDC_RELOAD_VERTICAL_BLANKING);
}
```

不同 STM32 系列可能提供不同的 reload 模式，包括立即重载和垂直空白期重载。必须确认当前芯片是否支持该功能以及中断行为。

---

## 6. 性能量化分析

以下数据以一个典型参考平台进行估算：

```
MCU：STM32H7，Cortex-M7，主频 400 MHz
D-Cache：启用
显示：800 × 480，60 Hz
显存：外部 SDRAM
接口：RGB 并行，RGB565
DMA2D：启用
```

### 6.1 单帧显存占用

公式：

```
FrameBytes = Width × Height × BytesPerPixel
```

800×480：

|格式|单帧显存|双缓冲|
|---|---|---|
|RGB565|768,000 B，约 750 KiB|1,536,000 B|
|RGB888|1,152,000 B，约 1.10 MiB|2,304,000 B|
|ARGB8888|1,536,000 B，约 1.46 MiB|3,072,000 B|

实际设计还要考虑：

- SDRAM 行对齐；
- 多图层；
- GUI draw buffer；
- 字体和图片资源；
- DMA2D 临时缓冲；
- RTOS 和业务任务内存。

### 6.2 有效像素带宽

公式：

```
ActivePixelBandwidth =
    Width × Height × RefreshRate × BytesPerPixel
```

RGB565：

```
800 × 480 × 60 × 2
= 46,080,000 B/s
≈ 43.95 MiB/s
```

ARGB8888：

```
800 × 480 × 60 × 4
= 92,160,000 B/s
≈ 87.89 MiB/s
```

但是 LTDC 实际还会读取 blanking 区对应的像素时钟周期，系统总线带宽还需考虑：

```
TotalScanBandwidth =
    TotalWidth × TotalHeight × RefreshRate × BytesPerPixel
```

采用前述时序：

```
863 × 511 × 60 × 2
≈ 52.9 MB/s
```

### 6.3 多图层带宽

假设两个全屏图层：

```
Layer 1 RGB565: 52.9 MB/s
Layer 2 ARGB8888: 105.8 MB/s
Output/写回或额外搬运: 视硬件合成方式而定
```

总线还要承受：

- CPU 访问 SDRAM；
- DMA2D 读写；
- 摄像头 DMA；
- 音频 DMA；
- 外部存储访问；
- 指令和数据 Cache miss。

因此不能仅依据“SDRAM 标称带宽”判断系统是否可用，应使用总线实测数据。

### 6.4 理论刷新时间

整帧 CPU 绘制像素数：

```
PixelCount = 800 × 480 = 384,000
```

如果 CPU 每像素写入平均消耗 12 个周期：

```
Cycles = 384,000 × 12 = 4,608,000 cycles
Time = 4,608,000 / 400 MHz
     ≈ 11.52 ms
```

理论上可以在 16.67 ms 的 60 Hz 帧周期内完成，但这不包含：

- Cache miss；
- SDRAM 刷新；
- GUI 控件布局；
- 图片解码；
- RTOS 调度；
- 其他中断和任务。

使用 DMA2D 后，CPU 通常只需要提交任务和等待完成，中大型区域填充的 CPU 占用可从毫秒级下降到微秒级提交开销，但 DMA2D 本身会增加总线竞争。

### 6.5 性能瓶颈与优化

|瓶颈|现象|优化|
|---|---|---|
|SDRAM 时序过慢|花屏、刷新不足、CPU 等待|优化 FMC 时序和内存布局|
|framebuffer 格式过大|带宽过高|RGB565、局部 Alpha、减少图层|
|CPU 逐像素绘图|CPU 占用高|DMA2D 填充/拷贝|
|Cache 未维护|显示内容不更新|Clean D-Cache|
|全屏重绘|帧率下降|dirty rectangle|
|过多透明图层|混合带宽高|合并静态图层|
|不合理 stride|SDRAM 访问效率差|行对齐、合理布局|
|VSYNC 等待策略错误|UI 延迟增加|双缓冲队列化|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
开始
 |
 |-- 是否需要持续刷新和高帧率？
 |       |
 |       +-- 否 --> 屏幕尺寸小、引脚有限？
 |       |             |
 |       |             +-- 是 --> SPI/QSPI LCD
 |       |             +-- 否 --> 继续评估并行接口
 |       |
 |       +-- 是
 |
 |-- 是否需要多图层、透明混合或复杂 GUI？
 |       |
 |       +-- 是 --> MCU 是否具备 LTDC？
 |       |             |
 |       |             +-- 是 --> LTDC + DMA2D + 双缓冲
 |       |             +-- 否 --> 外部显示控制器或专用 GPU
 |       |
 |       +-- 否
 |
 |-- framebuffer 是否能放入片上 SRAM？
 |       |
 |       +-- 是 --> 单缓冲或双缓冲
 |       |
 |       +-- 否 --> 外部 SDRAM + FMC + LTDC
 |
 |-- 是否存在摄像头/视频/高带宽 DMA？
 |       |
 |       +-- 是 --> 做总线带宽预算和仲裁验证
 |       +-- 否 --> 常规 LTDC 架构
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|240×320 状态显示|SPI + LCD 控制器|引脚少，刷新压力低|
|480×272 工业 HMI|LTDC + RGB565 + 双缓冲|帧率和 GUI 体验较好|
|800×480 多页面 GUI|LTDC + SDRAM + DMA2D|显存和图形操作需求较高|
|视频叠加 UI|LTDC 双层 + DMA2D|视频层与 UI 层分离|
|低功耗静态页面|SPI 或 LTDC 降频|降低持续扫描功耗|
|摄像头预览|摄像头 DMA + LTDC|减少 CPU 拷贝|
|高可靠报警界面|静态背景层 + 动态前景层|降低更新量和撕裂概率|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **显示驱动与 GUI 业务解耦**  
    底层只负责初始化、buffer 管理、刷新同步和区域更新。
    
2. **所有尺寸使用明确单位**  
    分别区分 pixel、byte、stride、line count，避免混用。
    
3. **所有外部输入做边界检查**  
    尤其是区域更新、图层窗口、图片尺寸和 buffer 地址。
    
4. **显存放置策略显式化**  
    通过 linker section 固定放入指定 SRAM/SDRAM 区域。
    
5. **Cache 策略在架构层确定**  
    不允许每个业务模块各自决定是否 Clean/Invalidate。
    
6. **错误处理必须可观测**  
    记录 LTDC 错误中断、DMA2D 错误、SDRAM 初始化错误和 VSYNC 超时。
    

### 8.2 选型决策矩阵

|条件|RGB565|RGB888|ARGB8888|
|---|---|---|---|
|显存不足|高适配|低适配|很低|
|高颜色质量|中|高|高|
|Alpha 混合|低|低|高|
|带宽压力|低|中|高|
|GUI 常规控件|高|中|高|
|摄像头原始数据|取决于输入|高|中|
|代码复杂度|低|中|低|

### 8.3 工业级编码规范

- 采用 `uint32_t` 表示像素坐标和长度，避免有符号下溢。
- 所有硬件寄存器配置完成后检查返回值。
- 不在 ISR 中执行整帧 Cache 操作或大块绘图。
- 不在多个任务中直接操作 LTDC/DMA2D，使用显示服务层串行化。
- `framebuffer` 使用 `aligned(32)` 或具体 Cache line 对齐属性。
- 图层 ID、像素格式、buffer index 使用枚举或宏定义，不使用魔数。
- 对 DMA2D 操作设置超时，防止硬件异常导致任务永久阻塞。
- 通过逻辑分析仪验证时序，而不是仅凭“屏幕亮了”判断配置正确。

---

## 9. 常见错误与避坑指南

## 9.1 时序累计值计算错误

### 错误代码

```
hltdc.Init.AccumulatedActiveW = 800U;
hltdc.Init.TotalWidth = 816U;
```

### 根因

把 Active Width 误认为寄存器所需的累计值，忽略了 HSYNC 和 HBP。

### 正确实现

```
hltdc.Init.AccumulatedHBP = HSYNC + HBP;
hltdc.Init.AccumulatedActiveW = HSYNC + HBP + ACTIVE_WIDTH;
hltdc.Init.TotalWidth = HSYNC + HBP + ACTIVE_WIDTH + HFP;
```

### 风险影响

- 图像整体偏移；
- DE 区间错误；
- 显示内容被截断；
- 部分屏幕完全不显示。

---

## 9.2 framebuffer 地址未映射到 LTDC 可访问区域

### 错误代码

```
static uint16_t framebuffer[800 * 480];

layer_cfg.FBStartAdress = (uint32_t)framebuffer;
```

### 根因

数组可能位于默认 SRAM 区域，而该区域不在 LTDC/DMA 可访问路径上，或者链接脚本将其放入了不适合 DMA 的区域。

### 正确实现

```
__attribute__((section(".framebuffer"), aligned(32)))
static uint16_t framebuffer[800U * 480U];
```

并在 linker script 中明确：

```
.framebuffer (NOLOAD) :
{
    . = ALIGN(32);
    *(.framebuffer)
    . = ALIGN(32);
} > SDRAM
```

### 风险影响

- 黑屏；
- 总线错误；
- DMA 读到异常数据；
- 低地址或高地址区域表现不一致。

---

## 9.3 忽略 D-Cache

### 错误代码

```
framebuffer[0] = 0xF800U;
HAL_LTDC_Reload(&hltdc, LTDC_RELOAD_IMMEDIATE);
```

### 根因

CPU 写入只更新了 Cache，LTDC 读取内存中的旧数据。

### 正确实现

```
framebuffer[0] = 0xF800U;

display_clean_region(framebuffer,
                     sizeof(framebuffer));

HAL_LTDC_Reload(&hltdc,
                LTDC_RELOAD_VERTICAL_BLANKING);
```

### 风险影响

- 画面不更新；
- 偶发旧图像；
- 仅部分区域更新；
- 开启优化或改变变量布局后问题重现。

---

## 9.4 图层窗口和图像尺寸不一致

### 错误代码

```
layer_cfg.WindowX1 = 800U;
layer_cfg.WindowY1 = 480U;
layer_cfg.ImageWidth = 480U;
layer_cfg.ImageHeight = 800U;
```

### 根因

混淆横屏和竖屏坐标，或者只旋转了业务坐标而未同步调整 framebuffer 布局。

### 正确实现

```
layer_cfg.WindowX0 = 0U;
layer_cfg.WindowX1 = DISPLAY_WIDTH;
layer_cfg.WindowY0 = 0U;
layer_cfg.WindowY1 = DISPLAY_HEIGHT;
layer_cfg.ImageWidth = DISPLAY_WIDTH;
layer_cfg.ImageHeight = DISPLAY_HEIGHT;
```

### 风险影响

- 错行；
- 图像越界；
- 访问非法地址；
- 画面只显示部分区域。

---

## 9.5 在显示扫描期间直接修改前台 buffer

### 错误代码

```
while (1) {
    draw_full_screen(framebuffer);
}
```

### 根因

CPU 和 LTDC 同时访问同一个 framebuffer，写入过程与扫描过程没有时间隔离。

### 正确实现

```
uint16_t *draw_buffer = framebuffer0;
uint16_t *display_buffer = framebuffer1;

draw_frame(draw_buffer);
display_clean_region(draw_buffer, FRAME_BYTES);

display_wait_vsync();
display_set_pending_buffer(draw_buffer);

uint16_t *temp = display_buffer;
display_buffer = draw_buffer;
draw_buffer = temp;
```

### 风险影响

- 撕裂；
- 半帧新旧内容混合；
- 动画边缘断裂；
- 高速运动场景明显闪烁。

---

## 9.6 未处理 DMA2D 完成和异常状态

### 错误代码

```
HAL_DMA2D_Start(&hdma2d, color, dst, width, height);
/* 立即使用 dst */
```

### 根因

DMA2D 是异步外设，启动函数返回不代表传输完成。

### 正确实现

```
if (HAL_DMA2D_Start(&hdma2d,
                    color,
                    (uintptr_t)dst,
                    width,
                    height) != HAL_OK) {
    return DISPLAY_ERR_DMA_START;
}

if (HAL_DMA2D_PollForTransfer(&hdma2d, DMA_TIMEOUT_MS) != HAL_OK) {
    HAL_DMA2D_Abort(&hdma2d);
    return DISPLAY_ERR_DMA_TIMEOUT;
}
```

### 风险影响

- 目标区域数据不完整；
- 后续任务覆盖 DMA2D 正在使用的 buffer；
- DMA2D 错误状态未清除导致后续操作全部失败。

---

## 10. 多机制组合使用方案

## 10.1 推荐架构

```
+------------------------------+
|          业务页面             |
+------------------------------+
              |
+------------------------------+
|       GUI / Display Service   |
|  页面调度、脏矩形、帧缓冲管理  |
+------------------------------+
       |                 |
+-------------+   +-------------+
|   DMA2D     |   |   VSYNC     |
| 填充/拷贝/混合 |   | 同步/切换     |
+-------------+   +-------------+
              |
+------------------------------+
|            LTDC              |
|  时序、图层、地址、错误中断    |
+------------------------------+
              |
+------------------------------+
| SDRAM / SRAM / MPU / Cache   |
+------------------------------+
              |
+------------------------------+
| RGB TFT Panel               |
+------------------------------+
```

## 10.2 显示服务接口

```
typedef enum {
    DISPLAY_OK = 0,
    DISPLAY_ERR_PARAM,
    DISPLAY_ERR_BUSY,
    DISPLAY_ERR_TIMEOUT,
    DISPLAY_ERR_HW
} display_status_t;

typedef struct {
    uint32_t x;
    uint32_t y;
    uint32_t width;
    uint32_t height;
} display_rect_t;

display_status_t display_init(void);

display_status_t display_begin_frame(void **buffer);

display_status_t display_mark_dirty(const display_rect_t *rect);

display_status_t display_present(void);

display_status_t display_wait_vsync(uint32_t timeout_ms);
```

## 10.3 双缓冲状态机

```
typedef enum {
    BUFFER_FREE = 0,
    BUFFER_DRAWING,
    BUFFER_READY,
    BUFFER_DISPLAYING
} buffer_state_t;

typedef struct {
    uint8_t       *address;
    size_t         size;
    buffer_state_t state;
} display_buffer_t;

static display_buffer_t buffers[2];
static uint32_t active_index;
static uint32_t pending_index;

static display_status_t present_buffer(uint32_t index)
{
    if (index >= 2U ||
        buffers[index].state != BUFFER_READY) {
        return DISPLAY_ERR_PARAM;
    }

    display_clean_region(buffers[index].address,
                         buffers[index].size);

    pending_index = index;
    buffers[index].state = BUFFER_DISPLAYING;

    if (HAL_LTDC_SetAddress_NoReload(
            &hltdc,
            (uintptr_t)buffers[index].address,
            LTDC_LAYER_1) != HAL_OK) {
        buffers[index].state = BUFFER_READY;
        return DISPLAY_ERR_HW;
    }

    if (HAL_LTDC_Reload(
            &hltdc,
            LTDC_RELOAD_VERTICAL_BLANKING) != HAL_OK) {
        buffers[index].state = BUFFER_READY;
        return DISPLAY_ERR_HW;
    }

    return DISPLAY_OK;
}
```

实际系统中，buffer 状态切换应由 VSYNC 回调或显示任务完成，避免业务线程将“提交地址”和“实际生效”误认为同一时刻。

---

## 11. 工业级实际案例分析

## 11.1 案例一：800×480 工业 HMI

### 需求

- 800×480 分辨率。
- 60 Hz 刷新。
- 多页面切换。
- 需要按钮、曲线、告警图标。
- 动态区域约占屏幕 20%。
- 不能出现明显撕裂。

### 架构设计

```
MCU STM32H7
  |
  +-- LTDC RGB565，单主图层
  +-- DMA2D
  +-- 外部 SDRAM，双 framebuffer
  +-- 片上 SRAM，GUI dirty buffer
  +-- VSYNC 中断
  +-- Display Task
```

### 设计要点

- 背景图片保持静态，页面切换时一次性绘制。
- 动态控件使用 dirty rectangle。
- DMA2D 执行矩形填充和图片拷贝。
- 每次提交前 Clean 修改区域，而不是无条件 Clean 整帧。
- VSYNC 中切换前后台 buffer。
- 对刷新超时记录诊断计数器。

---

## 11.2 案例二：摄像头预览叠加告警框

### 需求

- 摄像头输出 RGB565。
- LTDC 显示实时画面。
- 叠加半透明告警框和文字。
- 摄像头 DMA 持续写入显存。
- 不允许 CPU 整帧拷贝。

### 架构设计

```
Camera DMA --> Video Buffer --> LTDC Layer 1
                                      |
UI Buffer ----------------------> LTDC Layer 2
```

### 设计要点

- 视频层使用 RGB565。
- UI 层使用 ARGB8888 或 AL44。
- 由 LTDC 硬件完成图层 Alpha 混合。
- Camera DMA 和 LTDC 访问同一 buffer 时，必须设计 buffer 生命周期。
- 不能在 LTDC 正在读取时让摄像头 DMA 覆盖同一帧，必要时使用摄像头双缓冲。
- 对视频 buffer 的 Cache 策略优先采用 non-cacheable 区域，减少频繁维护开销。

---

## 11.3 案例三：低 RAM 设备的局部刷新

### 需求

- 480×272 显示。
- 片上 RAM 只能容纳小块 draw buffer。
- UI 主要是文本和少量图标。
- 允许以区域为单位更新。

### 架构设计

```
GUI 绘制 480×40 行缓冲
        |
DMA2D 拷贝到目标 framebuffer
        |
Clean 对应区域
        |
等待安全同步点
        |
刷新局部区域
```

### 设计要点

- 采用 line buffer 或 tile buffer。
- 以 16、32 或 40 行为一个更新块。
- 更新区域按 Cache line 和 DMA2D 对齐。
- 对高速动画区域使用更高优先级显示任务。
- 需要评估局部更新期间的视觉一致性，避免不同区域处于不同帧状态。

---

## 12. 高频问题深度答疑

### 问题一：LTDC 为什么配置正确但仍然黑屏？

重点检查顺序：

```
时钟是否开启
  -> GPIO 复用是否正确
  -> PCLK 是否输出
  -> HSYNC/VSYNC/DE 极性是否匹配
  -> framebuffer 地址是否有效
  -> 图层是否启用
  -> 图层 Alpha 是否非零
  -> SDRAM 是否初始化成功
  -> 显示屏背光和复位时序是否正确
```

最有效的定位方式是先让 LTDC 输出纯色背景，不依赖 framebuffer：

```
hltdc.LayerCfg[0].Backcolor.Red = 255U;
hltdc.LayerCfg[0].Backcolor.Green = 0U;
hltdc.LayerCfg[0].Backcolor.Blue = 0U;
```

如果纯色背景也没有显示，问题偏向时序、GPIO、电源、背光和屏幕复位；如果纯色正常而 framebuffer 异常，问题偏向显存地址、Cache、像素格式和 SDRAM。

### 问题二：为什么画面撕裂，即使使用了双缓冲？

双缓冲只有在以下条件同时满足时才有效：

- 绘制只发生在非显示 buffer。
- buffer 切换发生在安全同步点。
- 地址更新和 reload 时序正确。
- buffer 在 DMA2D 完成后才提交。
- Cache 已 Clean。
- GUI 没有继续写入已经提交的 buffer。

如果直接调用立即 reload，仍可能在当前帧中途切换地址，导致撕裂。优先使用垂直空白期 reload。

### 问题三：RGB565 是否足够用于工业 HMI？

多数工业 HMI 足够。原因：

- 显存仅为 ARGB8888 的一半。
- 带宽压力较低。
- DMA2D 和 LTDC 支持成熟。
- 人眼对常规控件和文本中的色彩量化不敏感。

但以下情况可能需要更高格式：

- 高质量渐变；
- 照片或视频；
- 多级半透明叠加；
- 医疗影像；
- 需要减少色带的视觉设计。

### 问题四：为什么启用 Cache 后显示更快，但数据反而错误？

Cache 改善了 CPU 访问性能，却改变了 CPU 和 LTDC 对内存的可见性时序。CPU 认为已经写入的数据可能仍在 Cache 中，LTDC 只能读取外部内存中的旧内容。

解决方法有三类：

1. framebuffer 设置为 non-cacheable。
2. CPU 绘制后执行 Clean。
3. 通过 MPU 将不同显示区域采用不同 Cache 策略。

工程上通常使用第 2 种，因为它兼顾 CPU 绘制性能和 DMA 可见性。

### 问题五：LTDC 和 DMA2D 都访问 SDRAM，如何判断带宽够不够？

不能只看 SDRAM 芯片的理论频率。需要测量：

- LTDC 开启时 CPU 对 SDRAM 的读写吞吐。
- DMA2D 全屏填充耗时。
- 摄像头 DMA 同时开启时的丢帧情况。
- SDRAM 刷新和总线仲裁造成的等待。
- LTDC FIFO underrun 错误。

建议使用：

- DWT cycle counter；
- DMA2D 完成时间戳；
- LTDC underrun 中断计数；
- 逻辑分析仪测量 VSYNC 周期；
- ETM/Trace 或总线性能监控工具。

### 问题六：应使用全屏双缓冲还是局部刷新？

选择依据：

```
动态区域大、动画连续、视觉要求高
    -> 全屏双缓冲

动态区域小、RAM 受限、页面以控件更新为主
    -> dirty rectangle / tile buffer

有视频层和复杂 UI 层
    -> LTDC 多图层 + 分层缓冲

需要严格帧一致性且内存允许
    -> 双缓冲或三缓冲
```

局部刷新不等于天然无撕裂。局部区域仍需考虑 LTDC 当前扫描位置和更新时机。

---

## 13. 课程核心总结

### 核心要点

- **LTDC 是显示扫描控制器，不是绘图引擎。**
- 屏幕时序必须由 `HSYNC + HBP + Active + HFP` 和对应垂直参数计算。
- framebuffer 地址、stride、像素格式和内存可访问性必须同时正确。
- RGB565 适合大多数资源受限型工业 HMI。
- DMA2D 应用于填充、拷贝、格式转换和 Alpha 混合。
- Cortex-M7 上必须显式处理 D-Cache 与 LTDC/DMA2D 的一致性。
- 双缓冲只有配合 VSYNC 或垂直空白期切换才真正解决撕裂。
- SDRAM 带宽、总线仲裁和其他 DMA 活动决定实际帧率。
- 图层、显存、DMA2D、GUI 和 RTOS 应通过显示服务层统一管理。

### 性能排序

在典型资源受限平台上：

```
显存占用：
L8 < RGB565 < RGB888 < ARGB8888

LTDC 读取带宽：
L8 < RGB565 < RGB888 < ARGB8888

Alpha 混合能力：
RGB565 < RGB888 < ARGB8888

通用 GUI 易用性：
RGB565 ≈ ARGB8888 > RGB888

CPU 绘图效率：
DMA2D > 优化后的 CPU 批量操作 > CPU 逐像素操作
```

### 通用选型结论

- 小屏、低刷新要求、引脚有限：SPI/QSPI。
- 中等分辨率、复杂 GUI：LTDC + RGB565 + DMA2D。
- 高质量透明叠加：ARGB8888 图层。
- RAM 不足：外部 SDRAM 或局部缓冲。
- 动态画面：双缓冲 + VSYNC。
- 摄像头/视频叠加：多图层 + DMA buffer 生命周期管理。
- 高可靠产品：增加 underrun 检测、VSYNC 超时、DMA2D 错误和显存校验机制。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|需求|方案|
|---|---|
|小屏低速显示|SPI LCD|
|480×272 工业界面|LTDC + RGB565|
|800×480 动态 GUI|LTDC + SDRAM + DMA2D|
|半透明 UI|ARGB8888 图层|
|防止撕裂|双缓冲 + VSYNC|
|RAM 紧张|局部 draw buffer|
|摄像头预览|Camera DMA + LTDC|
|多媒体叠加|LTDC 多图层|

### 14.2 时序公式

```
HBP累计 = HSYNC + HBP
有效宽累计 = HSYNC + HBP + ActiveWidth
总宽 = HSYNC + HBP + ActiveWidth + HFP

VBP累计 = VSYNC + VBP
有效高累计 = VSYNC + VBP + ActiveHeight
总高 = VSYNC + VBP + ActiveHeight + VFP

PCLK = TotalWidth × TotalHeight × RefreshRate
```

### 14.3 显存公式

```
FrameBytes = Width × Height × BytesPerPixel
DoubleBufferBytes = 2 × FrameBytes
```

### 14.4 Cache 处理原则

|操作|Cache 动作|
|---|---|
|CPU 写 framebuffer，LTDC 读|Clean|
|DMA2D 写 framebuffer，CPU 读|Invalidate|
|DMA2D 读 CPU 刚写的数据|Clean|
|DMA 写入后 CPU 读取|Invalidate|
|non-cacheable 区域|通常无需维护，但 CPU 访问较慢|

### 14.5 调试顺序

```
1. 检查背光、电源、复位
2. 检查 PCLK/HSYNC/VSYNC/DE 波形
3. 输出纯色背景
4. 验证 framebuffer 地址
5. 验证 RGB 数据线和像素格式
6. 验证 SDRAM 读写
7. 验证 Cache 维护
8. 检查 DMA2D 完成状态
9. 检查 LTDC underrun
10. 检查双缓冲切换时机
```

---

## 15. 学习效果自检

完成本课后，应能回答并实践以下内容：

- [ ]  能从屏幕规格书计算 LTDC 全部时序参数。
- [ ]  能解释 `PCLK`、`DE`、`HSYNC`、`VSYNC` 的关系。
- [ ]  能计算 RGB565 和 ARGB8888 的显存占用。
- [ ]  能根据分辨率和刷新率估算显示带宽。
- [ ]  能独立配置一个 LTDC 图层。
- [ ]  能解释 framebuffer stride 的意义。
- [ ]  能实现 RGB888 到 RGB565 的转换。
- [ ]  能使用 DMA2D 完成区域填充。
- [ ]  能处理 Cache Clean 和 Invalidate。
- [ ]  能实现双缓冲和 VSYNC 切换。
- [ ]  能定位黑屏、偏色、花屏、撕裂和错行问题。
- [ ]  能判断片上 SRAM 是否足够容纳 framebuffer。
- [ ]  能为 SDRAM、LTDC、DMA2D 和摄像头 DMA 做带宽预算。
- [ ]  能设计显示服务层，避免业务代码直接操作硬件寄存器。
- [ ]  能给出 RGB565、ARGB8888、SPI 和 LTDC 的选型理由。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：纯色输出

目标：

- 配置 LTDC 时序。
- 输出纯红、纯绿、纯蓝和白色。
- 使用示波器确认 PCLK、HSYNC、VSYNC 和 DE。

验收标准：

- 屏幕稳定显示指定颜色。
- PCLK 频率与计算值误差在屏幕规格书允许范围内。
- 逻辑波形周期稳定。

#### 任务二：RGB565 framebuffer

目标：

- 将 framebuffer 放入指定 SRAM 或 SDRAM。
- 显示颜色条、棋盘格和渐变。
- 验证像素坐标到地址的映射。

验收标准：

- 无错行、无镜像、无偏色。
- 显示区域边界正确。
- SDRAM 全区域读写测试通过。

#### 任务三：DMA2D 图形加速

目标：

- 使用 DMA2D 实现矩形填充。
- 实现 RGB565 图片拷贝。
- 实现 RGB565 与 ARGB8888 格式转换。

验收标准：

- 对比 CPU 和 DMA2D 的耗时。
- 验证 DMA2D 完成中断和错误路径。
- 测试非 4 字节对齐地址和非整行区域。

#### 任务四：双缓冲与 VSYNC

目标：

- 实现前台显示 buffer 和后台绘制 buffer。
- 通过 VSYNC 完成地址切换。
- 播放移动矩形或滚动文本。

验收标准：

- 高速运动时无明显撕裂。
- 统计每帧绘制耗时和 VSYNC 等待时间。
- 模拟 DMA2D 超时后系统仍可恢复。

#### 任务五：多图层合成

目标：

- Layer 1 显示背景。
- Layer 2 显示透明图标和告警框。
- 修改 Layer 2 Alpha 值并观察合成效果。

验收标准：

- Alpha 合成颜色正确。
- 图层窗口越界被拒绝。
- 层关闭和重新启用不会导致 LTDC 错误。

#### 任务六：与 GUI 框架集成

目标：

- 实现 `flush_cb` 或等效显示刷新接口。
- 使用 dirty rectangle。
- 将 GUI draw buffer 放在片上 SRAM，framebuffer 放在 SDRAM。

验收标准：

- 页面切换、控件刷新和动画正常。
- Cache 操作覆盖正确区域。
- 测量 GUI 周期、刷新周期和 CPU 占用。

### 16.2 性能测试方法

使用 DWT 测量代码耗时：

```
static void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}
```

测试 DMA2D 操作：

```
uint32_t start = dwt_cycles();

display_fill_rect_dma2d(&rect, color);

uint32_t elapsed = dwt_cycles() - start;
double elapsed_us = (double)elapsed / (SystemCoreClock / 1000000.0);
```

应至少记录：

- CPU 整帧绘制周期。
- DMA2D 整帧填充周期。
- DMA2D 局部区域填充周期。
- SDRAM 单次读写吞吐。
- 开启/关闭 D-Cache 后的差异。
- 单图层/双图层下的 LTDC underrun 次数。
- VSYNC 等待时间。
- GUI 任务最大执行时间和平均执行时间。

### 16.3 进阶学习方向

- STM32 LTDC 寄存器级配置与 HAL/LL 差异。
- FMC SDRAM 初始化、时序调优和内存测试。
- MPU 区域属性、Write-Back、Write-Through 和 Shareable 属性。
- DMA2D 完整模式：M2M、M2M_PFC、M2M_BLEND、R2M。
- LVGL framebuffer、partial refresh 和 direct mode。
- TE 信号与 RGB/SPI 显示同步。
- 三缓冲、帧队列和低延迟渲染。
- 摄像头 DCMI/CSI 与 LTDC 零拷贝显示。
- MIPI DSI、LVDS、HDMI 桥接方案。
- 显示安全：显存越界防护、异常画面检测和安全状态页。
- 基于 Trace 的总线带宽分析和实时性证明。
- 面向 ISO 26262、IEC 61508 的 HMI 显示诊断设计。