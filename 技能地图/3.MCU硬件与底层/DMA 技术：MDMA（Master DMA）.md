
> 本课以 **STM32H7 等带 MDMA 控制器的 Cortex-M7/M33 MCU** 为主要参考对象，同时抽象出适用于其他“主 DMA / 高级 DMA / 链式 DMA”实现的通用设计方法。不同芯片对 MDMA 的命名、触发机制、地址更新规则和总线能力存在差异，最终配置必须以目标芯片参考手册为准。

---

## 1. 学习目标

### 理解

- 理解 MDMA 与普通 DMA、BDMA、DMA2D、GPDMA 的架构差异。
- 理解 MDMA 作为独立总线主设备时的工作方式。
- 理解 MDMA 的：
    - 内存到内存传输；
    - 链式块传输；
    - 外设触发；
    - 数据打包与解包；
    - 地址偏移；
    - Repeat Block；
    - Linked List；
    - 传输完成和错误机制。
- 理解 MDMA 与 Cache、MPU、AXI SRAM、DTCM、外部 SDRAM 的协同关系。

### 掌握

- 掌握 MDMA 单块、块重复、链式和外设触发传输的配置方法。
- 掌握 MDMA 与普通 DMA 级联使用的设计方法。
- 掌握大块内存复制、图像搬运、帧缓冲更新、非连续数据搬运的实现。
- 掌握 MDMA 源地址 / 目标地址偏移的计算方法。
- 掌握 MDMA 传输完成、块完成、Buffer Transfer、错误中断的处理方法。

### 精通

- 能分析 MDMA 的总线带宽、Burst、FIFO、AXI 竞争和 Cache 一致性问题。
- 能设计 MDMA 描述符链，避免大块数据搬运占用 CPU。
- 能处理 MDMA 与普通 DMA 之间的生产者 / 消费者同步。
- 能定位跨 SRAM、SDRAM、Flash、外设 FIFO 传输中的地址和访问属性错误。
- 能建立 MDMA 超时、取消、错误恢复和传输审计机制。

### 能够设计

- 能设计 UART / SPI / ADC 普通 DMA + MDMA 后处理架构。
- 能设计 RGB565 / RGB888 图像搬运和 2D 行间隔传输。
- 能设计多段非连续内存聚合、解聚合和数据格式转换框架。
- 能设计支持 Cache、RTOS、双缓冲、链表和异常恢复的 MDMA 驱动层。
- 能对 MDMA 方案进行吞吐量、延迟、CPU 占用和内存成本评估。

---

## 2. 前置要求

### 知识要求

- MCU 总线架构：
    - AHB；
    - AXI；
    - APB；
    - Bus Matrix；
    - SRAM Bank；
    - 外部存储器控制器。
- 普通 DMA 的：
    - Request；
    - Channel / Stream；
    - NDTR；
    - Circular；
    - Double Buffer；
    - FIFO。
- Cortex-M Cache、MPU、内存屏障。
- UART、SPI、ADC、SDMMC、LTDC、Ethernet 基本工作原理。
- RTOS 任务、ISR、队列、信号量和事件通知。
- C 语言指针、结构体、地址运算和内存对齐。

### 技能要求

- 能阅读 MCU Reference Manual 中的 MDMA 章节。
- 能查看 DMA / MDMA 状态寄存器和错误标志。
- 能通过链接脚本分配不同内存区域。
- 能使用示波器、逻辑分析仪、DWT CYCCNT 测量执行时间。
- 能分析 map 文件、Cache 属性和 MPU 配置。
- 能构建独立的内存到内存 DMA 测试工程。

---

## 3. 技术概述

## 3.1 MDMA 是什么

MDMA 通常表示 **Master DMA**，即具备更强自主总线访问能力的 DMA 控制器。

与普通 DMA 相比，MDMA 通常更强调：

- 独立访问多个内存区域；
- 内存到内存搬运；
- 块级重复传输；
- 链式描述符；
- 复杂地址偏移；
- 外部存储器与内部 SRAM 之间的数据搬运；
- 由其他 DMA 或外设事件触发；
- 数据打包和解包。

典型数据路径：

```
外设 DMA / 外设 FIFO
          |
          v
       SRAM Buffer
          |
          v
         MDMA
          |
          +--> AXI SRAM
          +--> D2 SRAM
          +--> SDRAM
          +--> Flash
          +--> 其他可访问内存
```

MDMA 本身通常不是最适合直接服务 UART 单字节请求的控制器，而是更适合在普通 DMA 完成数据采集后，执行进一步的：

- 缓冲区搬运；
- 数据聚合；
- 数据解聚合；
- 行间隔复制；
- 帧缓冲更新；
- 外部内存转移；
- 多段内存链式传输。

---

## 3.2 普通 DMA 与 MDMA 的架构差异

普通 DMA 的典型使用方式：

```
ADC Request -> DMA -> SRAM
UART Request -> DMA -> SRAM
SPI Request -> DMA -> SRAM
```

MDMA 的典型使用方式：

```
普通 DMA -> Buffer A
              |
              v
             MDMA
              |
              +--> Buffer B
              +--> SDRAM
              +--> Framebuffer
              +--> Non-contiguous destination
```

普通 DMA 主要响应外设实时请求，MDMA 主要负责高阶内存搬运和数据组织。

---

## 3.3 MDMA 的主要功能分支

### 按触发方式分类

1. **软件触发**
    
    - CPU 配置完成后启动。
    - 适合普通内存复制。
2. **DMA 事件触发**
    
    - 普通 DMA 传输完成后触发 MDMA。
    - 适合 DMA 级联。
3. **外设事件触发**
    
    - 由外设请求或事件触发。
    - 适合与显示、存储、采集链协同。
4. **链式触发**
    
    - 当前块完成后装载下一个描述符。
    - 适合多段搬运。

### 按地址组织分类

- 源地址递增、目标地址递增。
- 源地址固定、目标地址递增。
- 源地址递增、目标地址固定。
- 源地址固定偏移。
- 目标地址固定偏移。
- 块之间使用正向偏移。
- 块之间使用负向偏移。
- 二维行列搬运。
- 非连续缓冲区搬运。

### 按数据操作分类

- 单字节复制。
- 半字复制。
- 字复制。
- 源数据打包。
- 目标数据解包。
- 数据宽度转换。
- 块重复。
- 链式块传输。

---

## 4. 核心特性横向对比

## 4.1 DMA、BDMA、MDMA、DMA2D 对比

|维度|普通 DMA|BDMA|MDMA|DMA2D|
|---|---|---|---|---|
|主要定位|外设数据搬运|低功耗域简单搬运|高级内存主控搬运|图像二维操作|
|典型方向|外设 ↔ 内存|外设 ↔ 内存|内存 ↔ 内存|内存 ↔ 显存|
|外设请求|强|强|通常较弱或通过事件触发|图形相关|
|链式传输|视芯片而定|通常有限|强|通常有寄存器配置|
|地址偏移|有限|有限|强|行偏移专用|
|数据打包|有限|通常无|支持度较高|像素格式相关|
|2D 搬运|通常不方便|不适合|可通过块偏移实现|原生支持|
|CPU 释放能力|高|中|很高|很高|
|适用场景|UART、ADC、SPI|低功耗外设|大块和复杂内存搬运|LCD、图像|
|软件复杂度|低～中|低|中～高|中|

## 4.2 MDMA 传输模式对比

|模式|描述|典型场景|优点|主要风险|
|---|---|---|---|---|
|单块传输|一次搬运一个连续区域|Buffer Copy|简单|大块配置需 CPU 重启|
|Block Repeat|一个块重复搬运|二维行复制|节省描述符|偏移计算错误|
|Linked List|多个节点自动执行|多段内存搬运|CPU 介入少|描述符一致性|
|DMA 级联|普通 DMA 完成触发 MDMA|ADC 后处理|自动化程度高|事件丢失、竞态|
|外设触发|外设事件启动 MDMA|显存、FIFO 协同|时序可控|触发语义复杂|
|双缓冲|两组地址交替|连续流处理|生产消费并行|所有权管理复杂|

## 4.3 MDMA 与 CPU `memcpy` 对比

|维度|CPU `memcpy`|MDMA|
|---|---|---|
|启动延迟|极低|较高|
|小数据性能|通常更好|通常较差|
|大数据 CPU 占用|高|很低|
|是否异步|否|是|
|是否受 Cache 影响|是|是，且需要一致性处理|
|是否能处理非连续布局|一般|可通过块偏移实现|
|是否会占用总线|会|会|
|是否适合实时主循环|小块适合|大块异步适合|
|软件复杂度|低|中高|

---

## 5. 底层原理与功能特性深度解析

## 5.1 MDMA 的基本传输模型

一个 MDMA 传输可以抽象为：

```
Source Address
      |
      v
+------------------+
| MDMA Read Engine |
+------------------+
      |
      v
  Internal FIFO
      |
      v
+-------------------+
| MDMA Write Engine |
+-------------------+
      |
      v
Destination Address
```

一次传输通常经历：

1. 读取源地址数据。
2. 放入 MDMA 内部 FIFO。
3. 根据打包 / 解包规则重组数据。
4. 根据目标宽度写入目标地址。
5. 更新源地址和目标地址。
6. 更新剩余计数。
7. 产生块完成或传输完成事件。
8. 如果存在链式节点，则装载下一个节点。

---

## 5.2 MDMA 传输粒度

MDMA 通常支持按以下粒度访问：

```
typedef enum {
    MDMA_WIDTH_BYTE = 1,
    MDMA_WIDTH_HALFWORD = 2,
    MDMA_WIDTH_WORD = 4,
    MDMA_WIDTH_DOUBLEWORD = 8,
} mdma_width_t;
```

源和目标宽度可以相同，也可能不同：

```
源：8 bit
目标：32 bit
```

这类宽度转换可能涉及：

- 打包；
- 解包；
- 端序处理；
- 对齐要求；
- 长度换算。

### 长度计算

设：

- 源元素数量为 `Nsrc`
- 源宽度为 `Ws`
- 目标宽度为 `Wd`

则总字节数必须满足：

Nsrc×Ws=Ndst×WdNsrc×Ws=Ndst×Wd

例如：

```
源：1024 个 uint8_t = 1024 Byte
目标：256 个 uint32_t = 1024 Byte
```

---

## 5.3 MDMA 单块内存复制

以下为平台无关抽象接口：

```
typedef enum {
    MDMA_OK = 0,
    MDMA_ERR_PARAM = -1,
    MDMA_ERR_BUSY = -2,
    MDMA_ERR_TIMEOUT = -3,
    MDMA_ERR_HW = -4,
    MDMA_ERR_NOT_SUPPORTED = -5,
} mdma_status_t;

typedef struct {
    uintptr_t src;
    uintptr_t dst;
    size_t length;
    mdma_width_t src_width;
    mdma_width_t dst_width;
    bool src_inc;
    bool dst_inc;
    uint8_t priority;
} mdma_transfer_t;

typedef struct {
    volatile bool busy;
    volatile bool done;
    volatile bool error;
    volatile uint32_t error_flags;
} mdma_state_t;

static mdma_state_t g_mdma_state;
```

### 提交单次传输

```
mdma_status_t mdma_memcpy_submit(const void *src,
                                 void *dst,
                                 size_t length)
{
    if (src == NULL || dst == NULL || length == 0U) {
        return MDMA_ERR_PARAM;
    }

    if (g_mdma_state.busy) {
        return MDMA_ERR_BUSY;
    }

    /*
     * 对内存到内存传输，源和目的区域不能非法重叠。
     * 若需要支持重叠复制，应改用 memmove 语义。
     */
    if (memory_regions_overlap(src, dst, length)) {
        return MDMA_ERR_PARAM;
    }

    mdma_disable(MDMA_CHANNEL_0);
    mdma_clear_all_flags(MDMA_CHANNEL_0);

    g_mdma_state.busy = true;
    g_mdma_state.done = false;
    g_mdma_state.error = false;
    g_mdma_state.error_flags = 0U;

    mdma_set_source_address(MDMA_CHANNEL_0,
                            (uintptr_t)src);
    mdma_set_destination_address(MDMA_CHANNEL_0,
                                 (uintptr_t)dst);
    mdma_set_length(MDMA_CHANNEL_0, length);

    mdma_set_source_width(MDMA_CHANNEL_0,
                          MDMA_WIDTH_WORD);
    mdma_set_destination_width(MDMA_CHANNEL_0,
                               MDMA_WIDTH_WORD);

    mdma_set_source_increment(MDMA_CHANNEL_0, true);
    mdma_set_destination_increment(MDMA_CHANNEL_0, true);

    mdma_set_priority(MDMA_CHANNEL_0, MDMA_PRIORITY_MEDIUM);
    mdma_enable_irq(MDMA_CHANNEL_0,
                    MDMA_IRQ_TRANSFER_COMPLETE |
                    MDMA_IRQ_TRANSFER_ERROR);

    /*
     * 若源数据刚由 CPU 写入 Cache，启动前必须 Clean。
     * 目标区域在 DMA 写入前应避免存在脏 Cache Line。
     */
    dma_cache_clean((void *)src, length);
    dma_cache_invalidate(dst, length);
    cpu_dsb();

    mdma_enable(MDMA_CHANNEL_0);

    return MDMA_OK;
}
```

### MDMA 中断

```
void MDMA_IRQHandler(void)
{
    uint32_t flags = mdma_get_flags(MDMA_CHANNEL_0);

    if ((flags & MDMA_FLAG_TRANSFER_ERROR) != 0U) {
        mdma_clear_flags(MDMA_CHANNEL_0,
                         MDMA_FLAG_TRANSFER_ERROR);

        g_mdma_state.error_flags = flags;
        g_mdma_state.error = true;
        g_mdma_state.busy = false;

        mdma_disable(MDMA_CHANNEL_0);
        mdma_error_notify_from_isr();
        return;
    }

    if ((flags & MDMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        mdma_clear_flags(MDMA_CHANNEL_0,
                         MDMA_FLAG_TRANSFER_COMPLETE);

        dma_cache_invalidate(mdma_current_dst(),
                             mdma_current_length());

        g_mdma_state.done = true;
        g_mdma_state.busy = false;

        mdma_complete_notify_from_isr();
    }
}
```

> 生产实现中不能直接使用抽象的 `mdma_current_dst()` 和 `mdma_current_length()`，应在提交请求时保存上下文，或使用传输句柄关联源地址、目的地址和长度。

---

## 5.4 MDMA Block Repeat：块重复传输

MDMA 的一个重要能力是：**传输一个块后自动调整源地址和目标地址，然后重复执行多个块**。

这特别适合二维数据。

### 典型场景：复制二维图像区域

源图像每行有完整 stride：

```
Source:
+-----------------------------+  Row 0
| valid pixels | padding     |
+-----------------------------+  Row 1
| valid pixels | padding     |
+-----------------------------+  Row 2
| valid pixels | padding     |
+-----------------------------+
```

目标区域可能是连续紧凑布局：

```
Destination:
+-------------------+ Row 0
| valid pixels      |
+-------------------+ Row 1
| valid pixels      |
+-------------------+ Row 2
| valid pixels      |
+-------------------+
```

设：

- 每行有效数据：`row_bytes`
- 源行跨度：`src_stride`
- 目标行跨度：`dst_stride`
- 行数：`rows`

则每次块完成后的地址更新为：

Srcnext=Srccurrent+src_strideSrcnext​=Srccurrent​+src_strideDstnext=Dstcurrent+dst_strideDstnext​=Dstcurrent​+dst_stride

而不是简单地：

Srcnext=Srccurrent+row_bytesSrcnext​=Srccurrent​+row_bytes

### 二维复制配置

```
typedef struct {
    uintptr_t src;
    uintptr_t dst;
    size_t row_bytes;
    size_t rows;
    size_t src_stride;
    size_t dst_stride;
} mdma_2d_copy_t;

mdma_status_t mdma_copy_2d(const mdma_2d_copy_t *cfg)
{
    if (cfg == NULL ||
        cfg->src == 0U ||
        cfg->dst == 0U ||
        cfg->row_bytes == 0U ||
        cfg->rows == 0U) {
        return MDMA_ERR_PARAM;
    }

    if (cfg->src_stride < cfg->row_bytes ||
        cfg->dst_stride < cfg->row_bytes) {
        return MDMA_ERR_PARAM;
    }

    if (g_mdma_state.busy) {
        return MDMA_ERR_BUSY;
    }

    mdma_disable(MDMA_CHANNEL_1);
    mdma_clear_all_flags(MDMA_CHANNEL_1);

    mdma_set_source_address(MDMA_CHANNEL_1, cfg->src);
    mdma_set_destination_address(MDMA_CHANNEL_1, cfg->dst);

    /*
     * 一个 Block 是一整行有效数据。
     */
    mdma_set_block_length(MDMA_CHANNEL_1,
                          cfg->row_bytes);

    mdma_set_block_count(MDMA_CHANNEL_1,
                         cfg->rows);

    /*
     * Repeat Block Offset：
     * 每一行搬运完成后，源地址跳过源 stride，
     * 目标地址跳过目标 stride。
     */
    mdma_set_source_block_offset(MDMA_CHANNEL_1,
                                 (int32_t)(cfg->src_stride -
                                           cfg->row_bytes));

    mdma_set_destination_block_offset(MDMA_CHANNEL_1,
                                      (int32_t)(cfg->dst_stride -
                                                cfg->row_bytes));

    mdma_set_source_width(MDMA_CHANNEL_1,
                          MDMA_WIDTH_WORD);
    mdma_set_destination_width(MDMA_CHANNEL_1,
                               MDMA_WIDTH_WORD);

    mdma_set_source_increment(MDMA_CHANNEL_1, true);
    mdma_set_destination_increment(MDMA_CHANNEL_1, true);

    mdma_enable_irq(MDMA_CHANNEL_1,
                    MDMA_IRQ_BLOCK_COMPLETE |
                    MDMA_IRQ_TRANSFER_COMPLETE |
                    MDMA_IRQ_TRANSFER_ERROR);

    dma_cache_clean((void *)cfg->src,
                    cfg->src_stride * cfg->rows);
    dma_cache_invalidate((void *)cfg->dst,
                         cfg->dst_stride * cfg->rows);
    cpu_dsb();

    g_mdma_state.busy = true;
    mdma_enable(MDMA_CHANNEL_1);

    return MDMA_OK;
}
```

### 关键风险

- 偏移是“块传输结束后的额外偏移”，还是“下一块绝对步长”，必须以芯片手册为准。
- 偏移可能是有符号数。
- 负偏移用于反向或交错访问时必须特别验证。
- `row_bytes`、stride、元素宽度必须满足对齐限制。
- 源和目标 Cache 维护范围不能只覆盖有效数据，还要考虑实际访问的 Cache Line。

---

## 5.5 MDMA Linked List：链式描述符

链式 MDMA 将多个传输节点放入内存：

```
Descriptor 0
     |
     v
Descriptor 1
     |
     v
Descriptor 2
     |
     v
Descriptor 3
```

每个节点可以包含：

- 源地址；
- 目标地址；
- 传输长度；
- 源 / 目标递增模式；
- 数据宽度；
- 块重复参数；
- 下一节点地址；
- 中断策略；
- 触发策略。

### 描述符结构示例

实际硬件描述符布局必须依照芯片定义，以下仅表示软件抽象：

```
typedef struct mdma_desc mdma_desc_t;

struct mdma_desc {
    uintptr_t src;
    uintptr_t dst;
    uint32_t length;
    int32_t src_block_offset;
    int32_t dst_block_offset;
    uint32_t block_count;
    uint32_t control;
    mdma_desc_t *next;
} __attribute__((aligned(32)));
```

### 建立描述符链

```
#define MDMA_DESC_COUNT 4U

static mdma_desc_t mdma_desc_pool[MDMA_DESC_COUNT]
    __attribute__((section(".dma_desc"), aligned(32)));

static void mdma_build_chain(const void *src_base,
                             void *dst_base,
                             size_t segment_size)
{
    for (size_t i = 0U; i < MDMA_DESC_COUNT; ++i) {
        mdma_desc_pool[i].src =
            (uintptr_t)src_base + i * segment_size;

        mdma_desc_pool[i].dst =
            (uintptr_t)dst_base + i * segment_size;

        mdma_desc_pool[i].length = segment_size;
        mdma_desc_pool[i].src_block_offset = 0;
        mdma_desc_pool[i].dst_block_offset = 0;
        mdma_desc_pool[i].block_count = 1U;
        mdma_desc_pool[i].control =
            MDMA_DESC_SRC_INC |
            MDMA_DESC_DST_INC |
            MDMA_DESC_IRQ_ON_COMPLETE;

        if (i + 1U < MDMA_DESC_COUNT) {
            mdma_desc_pool[i].next =
                &mdma_desc_pool[i + 1U];
        } else {
            mdma_desc_pool[i].next = NULL;
        }
    }

    /*
     * 描述符由 CPU 写入后，必须 Clean 到内存。
     */
    dma_cache_clean(mdma_desc_pool,
                    sizeof(mdma_desc_pool));
    cpu_dsb();
}
```

### 描述符链的工程要求

1. 描述符必须放在 MDMA 可访问内存。
2. 描述符必须满足硬件对齐要求。
3. 启动前 Clean 描述符 Cache。
4. 链式传输期间不能修改正在使用的节点。
5. 节点状态必须区分：
    - CPU 构建中；
    - MDMA 使用中；
    - MDMA 已完成；
    - CPU 回收中。
6. 最后一个节点必须显式标识链尾。
7. 对链表建立 CRC 或版本号，便于检测描述符破坏。

---

## 5.6 MDMA 与普通 DMA 级联

### 级联结构

```
ADC
 |
 v
普通 DMA
 |
 +--> 原始采样 Buffer
          |
          v DMA Transfer Complete Event
         MDMA
          |
          +--> 连续处理 Buffer
          +--> 外部 SDRAM
          +--> 数据聚合区
```

### 适用场景

- 普通 DMA 负责严格实时的外设搬运。
- MDMA 负责非实时或次实时的数据整理。
- CPU 不参与中间数据复制。
- 通过 DMA 事件或软件事件自动启动 MDMA。

### 设计时序

```
T0: ADC 产生采样请求
T1: 普通 DMA 搬运数据
T2: 普通 DMA 完成一个块
T3: DMA 事件触发 MDMA
T4: MDMA 搬运 / 重排数据
T5: MDMA 完成，通知 DSP Task
```

### 级联配置框架

```
typedef struct {
    void *raw_buffer;
    void *processed_buffer;
    size_t block_size;
} dma_mdmа_pipeline_t;

static dma_mdmа_pipeline_t g_pipeline;

int adc_dma_mdmа_pipeline_start(void)
{
    int ret;

    ret = adc_dma_start_circular(g_pipeline.raw_buffer,
                                 g_pipeline.block_size);
    if (ret != 0) {
        return ret;
    }

    ret = mdma_config_external_trigger(
        MDMA_TRIGGER_ADC_DMA_BLOCK_DONE);
    if (ret != 0) {
        adc_dma_stop();
        return ret;
    }

    ret = mdma_config_copy(
        g_pipeline.raw_buffer,
        g_pipeline.processed_buffer,
        g_pipeline.block_size);
    if (ret != 0) {
        adc_dma_stop();
        mdma_deinit();
        return ret;
    }

    return mdma_enable();
}
```

> 级联设计必须确认：DMA 完成事件是在“最后一次总线写入完成”时产生，还是在“外设请求完成”时产生。两者并不总是等价。

---

## 5.7 MDMA 数据打包与解包

假设源端是 4 个 8 bit 数据：

```
A B C D
```

目标端要求一个 32 bit 单元：

```
0xDDCCBBAA
```

MDMA 可能通过 Pack / Unpack 实现：

```
4 × 8 bit -> 1 × 32 bit
```

反向则是：

```
1 × 32 bit -> 4 × 8 bit
```

工程中必须明确：

- 字节序；
- 外设数据寄存器端序；
- Pack 阈值；
- 源、目标地址更新单位；
- 未满一个打包单元时如何处理；
- 长度是否必须是 Pack 因子的整数倍。

示例校验函数：

```
static bool mdma_pack_length_valid(size_t bytes,
                                   size_t pack_factor)
{
    if (pack_factor == 0U) {
        return false;
    }

    return (bytes % pack_factor) == 0U;
}
```

不要只看“DMA 传输完成”，还要对转换结果执行固定测试向量校验。

---

## 5.8 MDMA 与 Cache、MPU、内存屏障

## 5.8.1 MDMA 发送数据

```
CPU 写入 Cache
        |
        v
Cache 中是新数据，SRAM 中可能仍是旧数据
        |
        v
MDMA 读取 SRAM
        |
        v
MDMA 读到旧数据
```

正确生命周期：

```
prepare_for_mdma_read(src, len);
mdma_start(src, dst, len);
```

实现：

```
void prepare_for_mdma_read(const void *src, size_t len)
{
    dma_cache_clean((void *)src, len);
    cpu_dsb();
}
```

## 5.8.2 MDMA 接收数据

```
MDMA 写入 SRAM
        |
        v
CPU Cache 中仍保留旧 Cache Line
        |
        v
CPU 读到旧数据
```

正确生命周期：

```
mdma_wait_complete();
prepare_for_cpu_read(dst, len);
```

实现：

```
void prepare_for_cpu_read(void *dst, size_t len)
{
    cpu_dmb();
    dma_cache_invalidate(dst, len);
    cpu_dsb();
}
```

## 5.8.3 MDMA 描述符 Cache

描述符本身也是 DMA 输入数据：

```
mdma_desc_t desc __attribute__((aligned(32)));

desc.src = src;
desc.dst = dst;
desc.length = len;

dma_cache_clean(&desc, sizeof(desc));
cpu_dsb();

mdma_start_linked(&desc);
```

如果忘记 Clean 描述符，MDMA 可能使用旧的地址和长度。

---

## 5.9 MDMA 内存区域与总线可达性

不同内存区域的 DMA 可达性可能不同：

|内存区域|CPU 访问|普通 DMA|MDMA|典型用途|
|---|---|---|---|---|
|ITCM|很快|通常不可达|通常不可达|指令|
|DTCM|很快|视芯片而定，常不可达|视芯片而定|实时数据|
|AXI SRAM|快|通常可达|通常可达|高性能 DMA Buffer|
|D2 SRAM|中等|通常可达|通常可达|外设 DMA|
|D3 SRAM|中等|部分可达|部分可达|低功耗域数据|
|外部 SDRAM|延迟较高|通常可达|通常可达|Framebuffer、大缓存|
|Flash|可读|可读性依芯片而定|可能可读|常量、固件数据|

必须验证三个属性：

```
CPU 可访问
DMA 可访问
MDMA 可访问
```

不能因为 CPU 能访问某区域，就推断 MDMA 也能访问。

---

## 5.10 MDMA 中断和错误状态

常见 MDMA 事件：

- Block Transfer Complete；
- Buffer Transfer Complete；
- Linked List Transfer Complete；
- Transfer Complete；
- Address Error；
- Block Transfer Error；
- Buffer Transfer Error；
- Bus Error；
- Trigger Overrun；
- Link Update Error。

推荐 ISR 框架：

```
void MDMA_Channel0_IRQHandler(void)
{
    uint32_t flags = mdma_get_channel_flags(0U);

    if ((flags & MDMA_FLAG_ERROR_MASK) != 0U) {
        mdma_clear_channel_flags(0U,
                                 flags & MDMA_FLAG_ERROR_MASK);

        mdma_disable_channel(0U);

        mdma_record_error(flags);
        mdma_release_current_owner();
        mdma_notify_error_from_isr();
        return;
    }

    if ((flags & MDMA_FLAG_BLOCK_COMPLETE) != 0U) {
        mdma_clear_channel_flags(0U,
                                 MDMA_FLAG_BLOCK_COMPLETE);

        mdma_block_complete_from_isr();
    }

    if ((flags & MDMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        mdma_clear_channel_flags(0U,
                                 MDMA_FLAG_TRANSFER_COMPLETE);

        mdma_transfer_complete_from_isr();
    }
}
```

工程要求：

- 错误优先于完成处理。
- 不在 ISR 中释放复杂资源。
- 对链式传输保存当前节点编号。
- 遇到地址错误时记录源地址、目标地址、长度、节点地址。
- 支持通道复位后重新初始化。
- 防止异常状态下永久占用通道。

---

## 6. 性能量化分析

以下为示例测量平台：

- MCU：Cortex-M7，480 MHz。
- AXI 总线：240 MHz。
- MDMA 源和目标：内部 AXI SRAM。
- Cache：D-Cache 32 Byte。
- 编译器：GCC `-O2`。
- 测量工具：DWT CYCCNT。
- 数据量：4 KB、64 KB、1 MB。

实际性能会受具体芯片、总线矩阵、存储器等待周期和 DMA 配置影响。

## 6.1 MDMA 传输时间

理想情况下：

Ttransfer=DataSizeEffectiveBandwidthTtransfer​=EffectiveBandwidthDataSize​

若有效总线带宽为 800 MB/s，传输 64 KB：

T=65536800×106≈81.9μsT=800×10665536​≈81.9μs

实际时间还应加上：

Ttotal=Tsetup+Tcache+Ttransfer+TcompletionTtotal​=Tsetup​+Tcache​+Ttransfer​+Tcompletion​

例如：

```
MDMA 配置：2.5 μs
Cache Clean：4.0 μs
实际搬运：82 μs
完成处理：1.5 μs
总时间：90 μs 左右
```

## 6.2 示例实测数据

|数据量|CPU `memcpy` 时间|MDMA 总时间|CPU 活跃时间|说明|
|---|---|---|---|---|
|32 B|0.10 μs|3.8 μs|3.8 μs|MDMA 不划算|
|128 B|0.22 μs|4.0 μs|4.0 μs|仍可能不划算|
|4 KB|3.1 μs|9.5 μs|3.2 μs|CPU 可并行|
|64 KB|48 μs|86 μs|5.4 μs|MDMA 明显释放 CPU|
|1 MB|0.74 ms|1.28 ms|7.2 μs|总线时间高，但 CPU 释放最大|

这里不能只比较：

```
CPU 复制 48 μs
MDMA 86 μs
```

MDMA 的核心收益是：

```
CPU 活跃时间从 48 μs 降至约 5.4 μs
```

## 6.3 DMA 使用阈值

设：

- CPU 单位复制成本为 `Ccpu × N`
- MDMA 配置和中断固定成本为 `Cmdma`
- MDMA 搬运单位成本为 `Cmdma_data × N`

当：

CcpuN=Cmdma+Cmdma_dataNCcpu​N=Cmdma​+Cmdma_data​N

得到 DMA 阈值：

Nthreshold=CmdmaCcpu−Cmdma_dataNthreshold​=Ccpu​−Cmdma_data​Cmdma​​

如果测得：

```
MDMA 固定开销：3.5 μs
CPU 复制速率：0.8 GB/s
MDMA 传输速率：500 MB/s
```

则：

Ccpu=1.25ns/ByteCcpu​=1.25ns/ByteCmdma_data=2ns/ByteCmdma_data​=2ns/Byte

此时 MDMA 单纯从延迟角度并不优于 CPU，但从 CPU 释放角度仍然有价值。

因此阈值不能只由速度决定，还要考虑：

- 当前 CPU 是否繁忙。
- 是否允许异步执行。
- 是否存在实时任务。
- 总线竞争是否严重。
- 是否需要二维或链式能力。

## 6.4 2D 搬运带宽

设每行有效数据 `V`，stride 为 `S`，总行数为 `R`。

有效数据量：

Dvalid=V×RDvalid​=V×R

总线实际读取量可能为：

Dread=S×RDread​=S×R

带宽利用率：

Efficiency=DvalidDread=VSEfficiency=Dread​Dvalid​​=SV​

例如：

```
有效宽度：800 Byte
源 stride：1024 Byte
行数：480
```

Efficiency=8001024=78.125%Efficiency=1024800​=78.125%

其余带宽消耗在行间 padding 上。若能重新组织 framebuffer 或使用更合适的图像控制器，可以降低总线浪费。

## 6.5 总线竞争分析

假设：

- MDMA 理论占用：200 MB/s。
- LCD DMA：150 MB/s。
- Ethernet DMA：80 MB/s。
- CPU Cache Miss：平均 50 MB/s。
- 总线可用带宽：400 MB/s。

总需求：

200+150+80+50=480MB/s200+150+80+50=480MB/s

已经超过可用带宽，系统将产生：

- 仲裁等待；
- CPU 访问抖动；
- DMA 延迟增大；
- FIFO 溢出；
- 实时任务响应不稳定。

优化方法：

1. 降低 MDMA Burst 长度。
2. 将大块搬运拆成小块。
3. 调整不同 DMA 优先级。
4. 分离 SRAM Bank。
5. 将非实时搬运安排到空闲窗口。
6. 降低 LCD 刷新区域。
7. 使用 DMA2D 或专用图像控制器。
8. 增加外部内存预取和缓存策略。
9. 避免多个 DMA 同时高峰启动。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
需求是否直接由 UART/SPI/ADC 等外设请求驱动？
|
+-- 是 --> 普通 DMA 是否可以直接完成？
|          |
|          +-- 是 --> 使用普通 DMA
|          |
|          +-- 否 --> 是否需要二次搬运、数据重排或多段输出？
|                     |
|                     +-- 是 --> 普通 DMA + MDMA 级联
|                     +-- 否 --> 重新评估外设 DMA 配置
|
+-- 否 --> 是否为大块内存复制？
           |
           +-- 否 --> CPU memcpy / 专用硬件加速
           |
           +-- 是 --> 数据是否连续？
                      |
                      +-- 是 --> MDMA 单块传输
                      |
                      +-- 否 --> 是否为规则二维布局？
                                 |
                                 +-- 是 --> MDMA Block Repeat
                                 |
                                 +-- 否 --> 是否为多个固定内存片段？
                                            |
                                            +-- 是 --> MDMA Linked List
                                            |
                                            +-- 否 --> CPU 软件处理或专用外设
```

## 7.2 典型需求与方案

|需求|推荐方案|主要理由|
|---|---|---|
|UART 接收字节|普通 DMA|外设请求驱动更自然|
|ADC 采样后复制到处理区|普通 DMA + MDMA|分离实时采样和后处理|
|摄像头帧行搬运|MDMA Block Repeat|支持行跨度和二维布局|
|RGB565 局部刷新|MDMA 2D / DMA2D|支持行间偏移|
|多段报文聚合|MDMA Linked List|避免 CPU 逐段复制|
|大块 SRAM 到 SDRAM|MDMA 单块|释放 CPU|
|数据格式重组|MDMA Pack / Unpack|硬件完成基本重组|
|外部 Flash 数据加载|MDMA + QSPI / OSPI DMA|降低 CPU 拷贝成本|
|Ethernet 描述符处理|Ethernet DMA 优先|MDMA 负责二次整理|
|小于 128 B 的复制|CPU `memcpy`|避免启动开销|
|高实时闭环控制|普通 DMA / 外设专用 DMA|MDMA 不应介入最短实时路径|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：普通 DMA 负责实时请求，MDMA 负责数据组织

推荐分层：

```
外设请求实时性
      |
      v
普通 DMA
      |
      v
原始数据 Buffer
      |
      v
MDMA 数据整理
      |
      v
算法 / 协议 / UI
```

不要让 MDMA 替代所有普通 DMA。

### 原则二：明确 MDMA 的所有权

```
typedef enum {
    MDMA_BUF_FREE = 0,
    MDMA_BUF_SOURCE_READY,
    MDMA_BUF_MDMA_READING,
    MDMA_BUF_DESTINATION_WRITING,
    MDMA_BUF_CPU_READY,
    MDMA_BUF_ERROR,
} mdma_buf_state_t;
```

### 原则三：描述符必须静态、对齐、可审计

```
#define MDMA_DESC_ALIGN 32U

_Static_assert((sizeof(mdma_desc_t) % MDMA_DESC_ALIGN) == 0U,
               "Descriptor size alignment error");
```

### 原则四：为每个 MDMA 通道建立资源表

```
typedef struct {
    uint8_t channel;
    const char *owner;
    uint32_t trigger;
    uint8_t priority;
    bool in_use;
} mdma_resource_t;
```

避免多个模块无协同地抢占同一个 MDMA 通道。

### 原则五：配置和提交分离

```
初始化阶段：
    配置通道能力、IRQ、触发源

运行阶段：
    提交地址、长度、描述符

完成阶段：
    释放资源、通知上层
```

### 原则六：所有异步 API 都要定义 Buffer 生命周期

调用者必须知道：

```
submit 后源缓冲区是否可修改？
完成前目标缓冲区是否可读取？
错误后缓冲区是否需要重新初始化？
取消后是否允许立即复用？
```

## 8.2 选型决策矩阵

评分范围为 1～5，越高越适合。

|方案|小块延迟|大块吞吐|非连续搬运|CPU 释放|软件复杂度|
|---|---|---|---|---|---|
|CPU memcpy|5|3|2|1|5|
|普通 DMA|3|4|2|4|4|
|MDMA 单块|2|5|2|5|4|
|MDMA Block Repeat|2|5|4|5|3|
|MDMA Linked List|2|5|5|5|2|
|DMA2D|2|5|5|5|3|
|专用外设 DMA|4|5|3|5|3|

## 8.3 工业级编码规范

- 所有地址使用 `uintptr_t`，避免 32 / 64 位平台转换告警。
- 所有 MDMA Buffer 显式指定内存段和对齐。
- 所有描述符放入专用链接段。
- 对 Cache 平台统一封装：
    - `mdma_prepare_source()`；
    - `mdma_prepare_destination()`；
    - `mdma_complete_destination()`。
- 所有异步传输必须提供超时和取消接口。
- 禁止在 MDMA ISR 中执行图像算法、协议解析和大块 `memcpy`。
- 不使用未经验证的负地址偏移。
- 对链式节点记录节点编号和版本号。
- 对源地址、目标地址、长度进行边界检查。
- 在启动时验证内存区域 DMA 可达性。
- 对错误路径进行故障注入测试。
- 对总线竞争进行最坏情况测试，不只测空载速度。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：把 MDMA 放在最短实时路径中

### 错误代码

```
void control_loop(void)
{
    mdma_start(adc_raw_buf,
               adc_process_buf,
               ADC_BLOCK_SIZE);

    mdma_wait_complete(10U);
    foc_process(adc_process_buf);
}
```

### 根因

MDMA 具有配置、触发和总线仲裁延迟，不适合作为严格固定延迟路径中的同步等待设备。

### 正确实现

```
void adc_dma_block_complete_isr(void)
{
    /*
     * 采样数据已经完成后，异步提交 MDMA。
     */
    if (mdma_submit_async(adc_raw_buf,
                          adc_process_buf,
                          ADC_BLOCK_SIZE) != MDMA_OK) {
        adc_pipeline_error_count++;
        return;
    }

    notify_dsp_task_from_isr();
}
```

或者更进一步：

```
普通 DMA 完成
      |
      v
MDMA 自动级联
      |
      v
MDMA 完成通知控制任务
```

### 风险影响

- 控制周期抖动。
- 任务阻塞。
- 最坏延迟不可控。
- 高负载时闭环稳定性下降。

---

## 9.2 错误二：忽略描述符 Cache 一致性

### 错误代码

```
desc->src = src;
desc->dst = dst;
desc->length = len;

mdma_start_linked(desc);
```

### 根因

CPU 仅修改了 Cache 中的描述符，MDMA 读取到内存中的旧描述符。

### 正确实现

```
desc->src = src;
desc->dst = dst;
desc->length = len;

dma_cache_clean(desc, sizeof(*desc));
cpu_dsb();

mdma_start_linked(desc);
```

### 风险影响

- MDMA 使用旧地址。
- 长度异常。
- 链表跳转错误。
- 传输完成后目标区域数据不完整。

---

## 9.3 错误三：Block Offset 计算错误

### 错误代码

```
mdma_set_block_length(channel, row_bytes);
mdma_set_block_count(channel, rows);

/* 错误：将 stride 直接作为额外偏移 */
mdma_set_source_block_offset(channel, src_stride);
```

### 根因

很多硬件定义的 Block Offset 是：

```
当前块结束后的额外偏移
```

而不是下一块起始地址与当前块起始地址的总跨度。

### 正确实现

```
int32_t src_offset =
    (int32_t)src_stride - (int32_t)row_bytes;

int32_t dst_offset =
    (int32_t)dst_stride - (int32_t)row_bytes;

mdma_set_source_block_offset(channel, src_offset);
mdma_set_destination_block_offset(channel, dst_offset);
```

### 风险影响

- 每行错位。
- 图像出现斜纹。
- 数据包字段跨行错位。
- 只在第二个 Block 后开始出现错误。

---

## 9.4 错误四：MDMA 访问不可达内存

### 错误代码

```
uint8_t source[4096] __attribute__((section(".dtcm")));
uint8_t target[4096] __attribute__((section(".itcm")));

mdma_memcpy_submit(source, target, sizeof(source));
```

### 根因

ITCM / DTCM 经常连接到 CPU TCM 接口，未接入 MDMA 的系统总线。

### 正确实现

```
uint8_t source[4096]
    __attribute__((section(".dma_sram"), aligned(32)));

uint8_t target[4096]
    __attribute__((section(".dma_sram"), aligned(32)));
```

并在链接脚本中确保 `.dma_sram` 位于 MDMA 可访问区域。

### 风险影响

- 总线访问错误。
- MDMA 卡死或触发 Transfer Error。
- 不同芯片型号行为不同。
- Debug 模式与 Release 模式表现不同。

---

## 9.5 错误五：未处理 MDMA 与普通 DMA 的事件竞态

### 错误代码

```
void dma_complete_isr(void)
{
    mdma_start(raw_buf, processed_buf, block_size);
}

void mdma_complete_isr(void)
{
    process(processed_buf);
}
```

### 根因

普通 DMA 可能已经开始复用 `raw_buf`，而 MDMA 仍在读取它。

### 正确实现

```
typedef enum {
    PIPE_RAW_FREE = 0,
    PIPE_RAW_READY,
    PIPE_MDMA_READING,
    PIPE_PROCESSING,
} pipe_state_t;

static volatile pipe_state_t state;

void dma_complete_isr(void)
{
    if (state != PIPE_RAW_FREE) {
        pipeline_overrun_count++;
        return;
    }

    state = PIPE_MDMA_READING;

    if (mdma_submit_async(raw_buf,
                          processed_buf,
                          block_size) != MDMA_OK) {
        state = PIPE_RAW_FREE;
        pipeline_error_count++;
    }
}

void mdma_complete_isr(void)
{
    state = PIPE_PROCESSING;
    notify_processing_task_from_isr();
}

void processing_task(void *arg)
{
    for (;;) {
        wait_processing_event();

        process(processed_buf);

        state = PIPE_RAW_FREE;
    }
}
```

### 风险影响

- MDMA 读取过程中源数据被覆盖。
- 结果随负载随机变化。
- 数据校验偶发失败。
- 长时间运行后出现不可复现问题。

---

## 10. 多机制组合使用方案

## 10.1 普通 DMA + MDMA + 双缓冲 + RTOS

### 总体架构

```
外设
 |
 v
普通 DMA M0/M1
 |
 +--> Raw Buffer 0
 |
 +--> Raw Buffer 1
          |
          v
       MDMA
          |
          +--> Process Buffer
          +--> External SDRAM
          +--> Framebuffer
          |
          v
       RTOS Worker Task
```

### 角色分工

|模块|职责|
|---|---|
|外设|产生实时数据|
|普通 DMA|实时搬运外设数据|
|MDMA|数据整理、复制、聚合、转移|
|ISR|更新所有权、记录状态、发送通知|
|RTOS 任务|算法、协议、图像处理|
|Cache 层|保证 CPU 与 DMA 数据可见|
|错误管理器|超时、重启、统计和故障上报|

### 完整框架

```
typedef struct {
    uint8_t *raw;
    uint8_t *processed;
    size_t length;
    volatile bool dma_ready;
    volatile bool mdma_busy;
    volatile bool processed_ready;
    volatile uint32_t error_count;
} pipeline_buffer_t;

static pipeline_buffer_t g_pipeline[2];

static uint8_t raw_buf0[1024]
    __attribute__((section(".dma_sram"), aligned(32)));

static uint8_t raw_buf1[1024]
    __attribute__((section(".dma_sram"), aligned(32)));

static uint8_t processed_buf0[1024]
    __attribute__((section(".dma_sram"), aligned(32)));

static uint8_t processed_buf1[1024]
    __attribute__((section(".dma_sram"), aligned(32)));

void pipeline_init(void)
{
    g_pipeline[0] = (pipeline_buffer_t) {
        .raw = raw_buf0,
        .processed = processed_buf0,
        .length = sizeof(raw_buf0),
    };

    g_pipeline[1] = (pipeline_buffer_t) {
        .raw = raw_buf1,
        .processed = processed_buf1,
        .length = sizeof(raw_buf1),
    };

    ordinary_dma_start_double_buffer(raw_buf0,
                                     raw_buf1,
                                     sizeof(raw_buf0));
}

void ordinary_dma_buffer_done_isr(uint32_t buffer_id)
{
    pipeline_buffer_t *p = &g_pipeline[buffer_id];

    if (p->mdma_busy) {
        p->error_count++;
        pipeline_overrun_count++;
        return;
    }

    p->mdma_busy = true;
    p->dma_ready = true;

    dma_cache_clean(p->raw, p->length);
    dma_cache_invalidate(p->processed, p->length);
    cpu_dsb();

    if (mdma_submit_async(p->raw,
                          p->processed,
                          p->length,
                          buffer_id) != MDMA_OK) {
        p->mdma_busy = false;
        p->dma_ready = false;
        p->error_count++;
        return;
    }
}

void mdma_complete_isr(uint32_t buffer_id)
{
    pipeline_buffer_t *p = &g_pipeline[buffer_id];

    dma_cache_invalidate(p->processed, p->length);
    cpu_dsb();

    p->mdma_busy = false;
    p->dma_ready = false;
    p->processed_ready = true;

    processing_task_notify_from_isr(buffer_id);
}

void mdma_error_isr(uint32_t buffer_id,
                    uint32_t error_flags)
{
    pipeline_buffer_t *p = &g_pipeline[buffer_id];

    p->mdma_busy = false;
    p->dma_ready = false;
    p->processed_ready = false;
    p->error_count++;

    mdma_record_error(buffer_id, error_flags);
    pipeline_recovery_notify_from_isr(buffer_id);
}

void processing_task(void *arg)
{
    uint32_t buffer_id;
    pipeline_buffer_t *p;

    for (;;) {
        if (!processing_task_wait(&buffer_id,
                                  &p)) {
            continue;
        }

        if (!p->processed_ready) {
            continue;
        }

        p->processed_ready = false;

        process_data(p->processed, p->length);
    }
}
```

---

## 10.2 MDMA + DMA2D + LTDC 图像流水线

适合 HMI、仪表盘和工业显示：

```
摄像头 / 网络图像
       |
       v
普通 DMA 接收
       |
       v
MDMA 搬运或行重排
       |
       v
DMA2D 像素格式转换 / 混合
       |
       v
Framebuffer
       |
       v
LTDC 扫描输出
```

MDMA 负责：

- 行间隔处理；
- 非连续区域复制；
- 外部 SDRAM 与内部 SRAM 之间搬运；
- 图像缓存预取。

DMA2D 负责：

- RGB565 ↔ RGB888；
- Alpha Blend；
- Fill；
- 颜色格式转换。

LTDC 负责：

- 按显示时序读取 Framebuffer；
- 输出到 LCD。

不要让 MDMA 承担 DMA2D 的像素运算职责，也不要让 CPU 逐像素操作大图像。

---

## 11. 工业级实际案例分析

## 11.1 案例一：ADC 普通 DMA + MDMA 数据聚合

### 需求

- 8 路 ADC 扫描。
- 每通道 16 bit。
- 采样频率：250 kSPS。
- 普通 DMA 写入交错格式。
- DSP 需要非交错格式：

```
原始：
A0 B0 C0 D0 A1 B1 C1 D1 ...

目标：
A0 A1 A2 ...
B0 B1 B2 ...
C0 C1 C2 ...
D0 D1 D2 ...
```

### 方案

```
ADC Scan DMA
      |
      v
Interleaved Raw Buffer
      |
      v
MDMA Linked List / 多段搬运
      |
      v
Channel-Separated Buffer
      |
      v
DSP Task
```

### 设计要点

- 如果 MDMA 只支持规则地址偏移，可使用多个链式节点。
- 每个节点负责一个通道的采样点搬运。
- 不要在 ISR 中执行通道解交错。
- 如果 MDMA 不支持真正的 stride gather，应评估：
    - CPU DSP 指令；
    - 专用硬件过滤器；
    - 改变 ADC 数据布局；
    - 使用外设 FIFO 配置。

### 数据量

每个采样组：

```
8 × 2 Byte = 16 Byte
```

每个块包含 256 组：

RawSize=256×16=4096ByteRawSize=256×16=4096Byte

目标也是 4096 Byte，但目标布局更适合 DSP 的连续访问。

---

## 11.2 案例二：工业 HMI 的二维局部刷新

### 需求

- 显示区域：800 × 480。
- 像素格式：RGB565。
- Framebuffer 位于外部 SDRAM。
- UI 控件局部更新。
- CPU 需要同时执行协议栈和控制逻辑。

### 方案

```
UI Render Buffer（内部 SRAM）
          |
          v
MDMA 2D Copy
          |
          v
External SDRAM Framebuffer
          |
          v
LTDC
```

### 参数示例

```
控件宽度：240 pixel
控件高度：80 pixel
像素宽度：2 Byte
有效行长度：480 Byte
Framebuffer stride：1600 Byte
```

MDMA 每行处理：

```
Block Length = 480 Byte
Block Count  = 80
Source Offset = source_stride - 480
Destination Offset = 1600 - 480
```

### 设计要点

- 源 Buffer 通常是紧凑连续的。
- 目标 Framebuffer 每行包含全屏 stride。
- 目标区域必须在 LTDC 当前未扫描的安全时间窗口更新，或使用双 Framebuffer。
- 如果 Framebuffer 位于 Cacheable SDRAM，MDMA 写入后 LTDC 读取前要处理 Cache 和内存屏障。
- 多个 UI 控件更新时，使用 Linked List 将多个 Dirty Rectangle 一次提交。

---

## 11.3 案例三：QSPI Flash 数据加载到算法缓冲区

### 需求

- 固件资源存储在外部 QSPI Flash。
- 图标、字体、模型参数需要加载到内部 SRAM。
- 资源加载不能长期阻塞 UI 任务。
- 支持多个资源分段加载。

### 方案

```
QSPI Memory-Mapped Flash
          |
          v
普通 DMA / QSPI 控制器
          |
          v
MDMA Linked List
          |
          +--> 多个内部 SRAM Buffer
          +--> 对齐修正
          +--> 资源拼接
```

### 注意事项

- 确认 MDMA 是否允许从 Memory-Mapped Flash 读取。
- Flash 读取等待周期会降低 MDMA 实际吞吐。
- 外部 Flash 可能受 Cache 和预取影响。
- 不能在 Flash 正在擦除 / 编程时读取同一 Bank。
- 资源描述符本身不能与目标 Buffer 发生覆盖。
- 对资源头、长度、CRC 做校验。

### 资源加载接口

```
typedef struct {
    uintptr_t flash_addr;
    uintptr_t ram_addr;
    size_t size;
    uint32_t crc32;
} resource_segment_t;

int resource_load(const resource_segment_t *segments,
                  size_t count)
{
    if (segments == NULL || count == 0U) {
        return -1;
    }

    for (size_t i = 0U; i < count; ++i) {
        if (!resource_address_valid(segments[i].flash_addr,
                                    segments[i].size) ||
            !ram_address_valid(segments[i].ram_addr,
                               segments[i].size)) {
            return -2;
        }

        if (mdma_submit_sync(segments[i].flash_addr,
                             segments[i].ram_addr,
                             segments[i].size,
                             100U) != MDMA_OK) {
            return -3;
        }

        dma_cache_invalidate((void *)segments[i].ram_addr,
                             segments[i].size);

        if (crc32_calc((void *)segments[i].ram_addr,
                       segments[i].size) != segments[i].crc32) {
            return -4;
        }
    }

    return 0;
}
```

---

## 12. 高频问题深度答疑

## 问题一：MDMA 是否可以直接替代普通 DMA？

通常不能完全替代。

普通 DMA 更适合：

- UART；
- SPI；
- ADC；
- DAC；
- 定时器；
- 外设 FIFO。

这些场景需要外设请求精确驱动每一次数据传输。

MDMA 更适合：

- 内存到内存；
- 块重复；
- 链式节点；
- 二次搬运；
- 非连续数据布局；
- 大块异步传输。

最佳实践是：

```
普通 DMA 做外设实时数据搬运
MDMA 做后续内存数据组织
```

---

## 问题二：为什么 MDMA 的总耗时可能比 CPU memcpy 更长？

因为 MDMA 包含固定成本：

TMDMA=Tsetup+Ttrigger+Tbus+TISRTMDMA​=Tsetup​+Ttrigger​+Tbus​+TISR​

而 CPU `memcpy` 可能直接命中 D-Cache，几十字节数据很快就能复制完成。

但 MDMA 的优势在于：

- CPU 不需要持续执行复制指令。
- 可以和其他任务并行。
- 可处理非连续布局。
- 可通过链式描述符自动完成多个操作。

所以要区分：

```
单次完成延迟
CPU 活跃时间
系统吞吐量
实时任务抖动
```

---

## 问题三：MDMA 的 Block Repeat 与普通二维复制有什么本质区别？

普通二维复制通常需要：

```
for (row = 0; row < rows; ++row) {
    memcpy(dst + row * dst_stride,
           src + row * src_stride,
           row_bytes);
}
```

MDMA Block Repeat 将：

```
每一行复制 + 地址跳转 + 行计数
```

交给硬件完成。

CPU 只需要配置：

- 行长度；
- 行数；
- 源偏移；
- 目标偏移。

适合规则二维布局。不适合完全随机地址访问。

---

## 问题四：MDMA 什么时候应该使用链式描述符？

使用条件通常包括：

1. 数据分布在多个非连续区域。
2. 每段长度不同。
3. 需要自动连续提交多个传输。
4. CPU 不希望在每个段完成时介入。
5. 描述符数量和内存成本可接受。

如果只有一个连续 Buffer，使用链式描述符反而增加复杂度和故障面。

---

## 问题五：MDMA 与 CPU 同时访问同一 SRAM，会不会破坏数据？

可能不会“破坏”单个总线事务，但会产生：

- 访问延迟；
- 事务交错；
- Cache 脏数据覆盖；
- Buffer Ownership 竞态；
- 读写时序不确定。

必须区分两个问题：

### 总线层面

由硬件仲裁器保证总线事务完整性。

### 软件语义层面

由软件保证：

```
CPU 不读 DMA 正在写的区域
CPU 不改 DMA 正在读的区域
```

MDMA 不能替代所有权协议。

---

## 问题六：MDMA 失败后是否可以直接重新启动？

不建议直接启动。

错误恢复步骤通常为：

```
记录错误状态
   |
   v
禁止 MDMA 通道
   |
   v
清除所有状态标志
   |
   v
确认触发源已关闭
   |
   v
释放 Buffer Ownership
   |
   v
重新初始化源 / 目标地址
   |
   v
重新 Clean 描述符和源数据 Cache
   |
   v
重新启动
```

如果是总线错误或非法地址，应先修复根因。盲目重启可能导致：

- 错误循环；
- 中断风暴；
- 数据覆盖；
- 系统卡死。

## 13. 课程核心总结

### 13.1 核心要点

- **MDMA 是高级内存主控 DMA，不是普通外设 DMA 的简单替代品。**
- **普通 DMA 负责外设实时搬运，MDMA 负责复杂内存组织。**
- MDMA 的核心能力包括：
    - **Block Repeat**；
    - **地址偏移**；
    - **Linked List**；
    - **事件触发**；
    - **数据打包 / 解包**；
    - **大块异步传输**。
- 二维搬运的关键是正确计算：

Offset=Stride−BlockLengthOffset=Stride−BlockLength

其中：

- `Stride`：下一行起始地址与当前行起始地址之间的跨度；
- `BlockLength`：当前行实际搬运的有效字节数；
- `Offset`：当前块传输结束后，硬件还需要额外跳过的地址数量。

例如：

```
每行有效数据：480 Byte
源行跨度：512 Byte
源 Block Offset：512 - 480 = 32 Byte
```

- MDMA 传输完成并不等于外围物理操作完成。
- MDMA 描述符、源数据、目标数据都必须考虑 **Cache 一致性**。
- MDMA Buffer 必须位于 **MDMA 可访问的内存区域**。
- MDMA 传输需要明确：
    - Buffer Ownership；
    - 地址生命周期；
    - 传输超时；
    - 取消机制；
    - 错误恢复；
    - 数据完整性校验。
- MDMA 不应介入最短、最严格的控制实时路径，实时路径应尽量由：
    - 外设硬件触发；
    - 普通 DMA；
    - 定时器；
    - 专用加速器完成。

### 13.2 MDMA 典型系统定位

```
实时外设事件
      |
      v
普通 DMA
      |
      v
原始数据缓冲区
      |
      v
MDMA
      |
      +--> 内存复制
      +--> 数据重排
      +--> 二维行搬运
      +--> 多段数据聚合
      +--> 外部内存转移
      |
      v
算法 / 协议 / UI / 存储任务
```

### 13.3 MDMA 的主要性能排序

从 CPU 释放能力和复杂数据组织能力来看：

```
CPU memcpy
    <
普通 DMA
    <
MDMA 单块传输
    <
MDMA Block Repeat
    <
MDMA Linked List
    <
普通 DMA + MDMA 自动级联流水线
```

但这不是单次传输延迟排序。

从单次小数据传输的延迟来看，通常是：

```
CPU memcpy
    <
普通 DMA
    <
MDMA 单块
    <
MDMA Linked List
```

原因是 MDMA 的配置、触发、描述符装载和完成处理存在固定开销。

### 13.4 通用选型结论

|需求|推荐技术|
|---|---|
|UART、SPI、ADC 等外设实时搬运|普通 DMA|
|大块连续内存复制|MDMA 单块|
|规则二维数据搬运|MDMA Block Repeat|
|多个非连续内存段搬运|MDMA Linked List|
|普通 DMA 完成后的二次整理|普通 DMA + MDMA 级联|
|图像颜色转换和 Alpha 混合|DMA2D 等专用图形硬件|
|小于 DMA 启动阈值的数据|CPU `memcpy`|
|严格固定周期的电机控制路径|外设触发 + 普通 DMA / 专用硬件|
|Cache 开启的高性能系统|非 Cache 区域或严格 Cache Maintenance|
|多个 DMA 同时运行|总线带宽、优先级和 SRAM Bank 分区设计|

### 13.5 必须记住的工程判断

判断是否采用 MDMA，至少要回答以下问题：

```
1. 数据是否足够大，能够摊平 MDMA 启动开销？
2. CPU 是否需要在传输期间执行其他任务？
3. 数据是否存在二维 stride 或非连续布局？
4. 是否需要多个传输节点自动串联？
5. 源和目标内存是否均可被 MDMA 访问？
6. 是否正确处理了 D-Cache？
7. 是否明确 DMA 与 CPU 的 Buffer Ownership？
8. 总线是否能够承受额外 MDMA 带宽？
9. 传输失败后是否可以安全恢复？
10. 是否有超时、溢出、错误计数和故障上报机制？
```

---

## 14. 快速参考速查表

## 14.1 MDMA 模式选型表

|传输需求|MDMA 模式|关键参数|典型应用|
|---|---|---|---|
|一次连续复制|单块传输|源地址、目标地址、长度|SRAM 到 SDRAM|
|多行连续复制|Block Repeat|Block Length、Block Count、Offset|图像区域|
|多段非连续复制|Linked List|描述符地址、Next Pointer|报文聚合|
|普通 DMA 完成后处理|级联触发|DMA Event、Trigger Source|ADC 后处理|
|数据格式转换|Pack / Unpack|Source Width、Destination Width|字节到字转换|
|连续双缓冲处理|双缓冲 / 链表|M0、M1、Ownership|音频、图像|
|大块低 CPU 占用搬运|异步单块|完成事件、超时|资源加载|

## 14.2 地址配置速查表

|场景|源地址递增|目标地址递增|
|---|---|---|
|内存到内存复制|是|是|
|UART TX|是|否|
|UART RX|否|是|
|ADC 采样|否|是|
|DAC 输出|是|否|
|外设固定 FIFO 读写|视外设定义|视目标定义|
|二维图像复制|是|是，配合 Block Offset|
|多段链式传输|每个节点独立配置|每个节点独立配置|

## 14.3 二维搬运参数速查表

设：

```
有效行长度 = block_length
源行跨度   = src_stride
目标行跨度 = dst_stride
```

则通常：

```
源 Block Offset = src_stride - block_length
目标 Block Offset = dst_stride - block_length
```

示例：

```
源有效行长度：800 Byte
源 stride：1024 Byte
源 offset：224 Byte

目标有效行长度：800 Byte
目标 stride：1600 Byte
目标 offset：800 Byte
```

注意：某些芯片手册对 Offset 的定义可能是“下一块起始位置”而不是“额外跳过距离”。必须确认硬件语义，不能机械套用公式。

## 14.4 Cache 操作速查表

|DMA 行为|CPU 侧操作|
|---|---|
|MDMA 读取 CPU 刚写入的数据|`Clean` 源 Buffer|
|MDMA 写入、CPU 随后读取|`Invalidate` 目标 Buffer|
|MDMA 读取链式描述符|`Clean` 描述符|
|CPU 和 MDMA 共享状态变量|内存屏障 + 原子访问|
|Buffer 跨 Cache Line|按 Cache Line 对齐处理|
|Buffer 位于 Non-cacheable 区域|通常不需要 Clean / Invalidate|

推荐封装：

```
static inline void mdma_prepare_source(const void *src,
                                       size_t len)
{
    dma_cache_clean((void *)src, len);
    cpu_dsb();
}

static inline void mdma_prepare_destination(void *dst,
                                            size_t len)
{
    dma_cache_invalidate(dst, len);
    cpu_dsb();
}

static inline void mdma_complete_destination(void *dst,
                                             size_t len)
{
    cpu_dmb();
    dma_cache_invalidate(dst, len);
    cpu_dsb();
}
```

## 14.5 MDMA 错误排查表

|现象|优先检查项|
|---|---|
|MDMA 完全不启动|通道使能、触发源、时钟、请求映射|
|传输错误|地址可达性、地址对齐、数据宽度|
|每行图像错位|Block Length、Stride、Offset|
|目标数据是旧数据|Cache Invalidate|
|源数据发送旧内容|Cache Clean|
|链式节点跳转错误|描述符地址、对齐、Next Pointer、Cache|
|传输偶发超时|总线竞争、外部内存时序、触发丢失|
|数据被覆盖|Buffer Ownership、双缓冲状态机|
|CPU 负载降低但系统变慢|MDMA 总线竞争、Burst 配置、内存布局|
|错误后无法再次启动|状态标志、通道复位、触发源未关闭|

---

## 15. 学习效果自检

完成本课后，应能够独立回答并验证以下问题。

### 15.1 架构理解

- [ ]  能说明普通 DMA 和 MDMA 在系统中的不同定位。
- [ ]  能说明为什么 UART RX 更适合普通 DMA，而不是直接使用 MDMA。
- [ ]  能画出“普通 DMA + MDMA + RTOS 任务”的数据流。
- [ ]  能解释 MDMA 为什么也是总线竞争参与者。

### 15.2 寄存器和配置

- [ ]  能配置源地址和目标地址。
- [ ]  能配置源、目标地址递增模式。
- [ ]  能配置传输宽度和长度。
- [ ]  能配置 Block Repeat。
- [ ]  能配置外部触发或 DMA 事件触发。
- [ ]  能构建并启动一个 Linked List。
- [ ]  能正确清除 MDMA 状态标志。

### 15.3 二维传输

- [ ]  能区分有效行长度和行跨度。
- [ ]  能计算正向 Block Offset。
- [ ]  能验证 Block Offset 是额外偏移还是绝对跨度。
- [ ]  能使用逻辑分析或内存校验验证每一行的起始地址。
- [ ]  能处理源和目标 stride 不同的情况。

### 15.4 Cache 和内存

- [ ]  能确认某个 SRAM 是否被 MDMA 访问。
- [ ]  能识别 DTCM / ITCM 不一定可被 MDMA 访问。
- [ ]  能在 MDMA 读源数据前执行 Cache Clean。
- [ ]  能在 CPU 读目标数据前执行 Cache Invalidate。
- [ ]  能对描述符执行 Cache Clean。
- [ ]  能保证描述符和 Buffer 满足 Cache Line 对齐要求。

### 15.5 并发和所有权

- [ ]  能定义 DMA、MDMA、CPU 三者的 Buffer Ownership。
- [ ]  能防止普通 DMA 覆盖 MDMA 正在读取的源 Buffer。
- [ ]  能防止 CPU 读取 MDMA 正在写入的目标 Buffer。
- [ ]  能处理双缓冲状态切换。
- [ ]  能识别生产速度大于消费速度导致的溢出。

### 15.6 故障处理

- [ ]  能处理 MDMA 地址错误。
- [ ]  能处理传输错误和总线错误。
- [ ]  能为传输设置超时。
- [ ]  能安全取消正在进行的传输。
- [ ]  能在错误后重新初始化通道。
- [ ]  能记录源地址、目标地址、长度、描述符编号和错误标志。

---

## 16. 实践与进阶路径

## 16.1 第一阶段：MDMA 单块传输验证

### 实践任务

实现一个 4 KB 内存复制测试：

```
AXI SRAM Buffer A
        |
        v
       MDMA
        |
        v
AXI SRAM Buffer B
```

测试内容：

1. 填充固定模式：
    - `0x00`；
    - `0x55`；
    - `0xAA`；
    - 伪随机数；
    - 递增计数。
2. 使用 MDMA 复制。
3. 使用 CRC32 比较源和目标。
4. 测量：
    - 配置时间；
    - 传输时间；
    - 完成中断时间；
    - CPU 活跃周期。
5. 注入非法地址和非对齐地址，确认错误路径。

### 验收标准

```
1. 10000 次循环无数据错误。
2. 非法地址能够触发错误恢复。
3. 超时后通道能够重新启动。
4. CPU 活跃时间可通过 DWT 量化。
```

---

## 16.2 第二阶段：MDMA 二维 Block Repeat

### 实践任务

实现图像区域复制：

```
源图像：1280 × 720
目标图像：800 × 480
像素格式：RGB565
```

要求：

- 从源图像中截取一个矩形区域。
- 源和目标 stride 不同。
- 使用 MDMA Block Repeat。
- 禁止 CPU 逐行调用 `memcpy`。
- 对目标区域执行 CRC 或逐行比较。

### 验证内容

```
1. 第一行正确。
2. 中间行没有错位。
3. 最后一行没有越界。
4. 源区域右边界不会读出有效范围。
5. 目标区域不会覆盖无关区域。
```

推荐增加边界测试：

```
矩形起点在 0,0
矩形贴近右边界
矩形贴近下边界
宽度为 1 像素
高度为 1 行
宽度不是 4 Byte 对齐
```

---

## 16.3 第三阶段：Linked List 多段聚合

### 实践任务

将多个非连续报文片段聚合到连续发送 Buffer：

```
Header Buffer
Payload Segment 0
Payload Segment 1
CRC Buffer
        |
        v
MDMA Linked List
        |
        v
Contiguous TX Buffer
```

要求：

- 至少 4 个描述符。
- 每个节点长度不同。
- 节点源地址不连续。
- 目标地址连续。
- 传输完成后由任务统一发送。
- 描述符和目标 Buffer 进行 Cache 维护。
- 支持节点链表 CRC 校验。

### 验收标准

- 多次提交链表无数据错位。
- 任意一个节点非法时能够定位节点编号。
- 链表传输被取消后，目标 Buffer 状态可恢复。
- 描述符修改后，MDMA 使用的是最新配置。

---

## 16.4 第四阶段：普通 DMA + MDMA 级联流水线

### 实践任务

实现：

```
SPI / ADC
   |
   v
普通 DMA 双缓冲
   |
   v
MDMA 数据整理
   |
   v
RTOS DSP Task
```

要求：

- 普通 DMA 采集两个 Buffer。
- 每个 Buffer 完成后触发 MDMA。
- MDMA 完成后发送任务通知。
- DSP 任务计算均值、峰峰值、RMS 或 FFT。
- 记录：
    - DMA 延迟；
    - MDMA 延迟；
    - 任务调度延迟；
    - Buffer 溢出次数；
    - 最大处理时间。

### 必须验证的边界

```
1. DSP 处理时间接近 Buffer 周期。
2. 人为增加高优先级任务。
3. 人为延长临界区。
4. 让 MDMA 访问速度下降。
5. 让任务处理速度低于数据生产速度。
6. 注入 DMA / MDMA 错误。
```

最终应得到：

TDMA+TMDMA+TProcess<TBufferPeriodTDMA​+TMDMA​+TProcess​<TBufferPeriod​

并且：

TProcess,max<TBufferPeriodTProcess,max​<TBufferPeriod​

---

## 16.5 第五阶段：总线竞争和最坏情况测试

### 测试矩阵

|测试项|空载|LCD 并行|Ethernet 并行|SDRAM 高负载|全部并行|
|---|---|---|---|---|---|
|MDMA 4 KB 延迟|测量|测量|测量|测量|测量|
|MDMA 64 KB 延迟|测量|测量|测量|测量|测量|
|CPU 中断延迟|测量|测量|测量|测量|测量|
|DMA FIFO 峰值|测量|测量|测量|测量|测量|
|数据错误数|0|0|0|0|0|
|任务最大抖动|测量|测量|测量|测量|测量|

### 重点观察

- MDMA 实际吞吐量是否下降。
- 普通 DMA 是否发生 FIFO 溢出。
- CPU 最坏中断响应时间是否增加。
- 控制任务周期是否超限。
- 外部 SDRAM 是否出现访问超时。
- DMA 和 MDMA 是否存在优先级反转或资源饥饿。

---

## 16.6 第六阶段：工业级驱动封装

最终建议形成如下模块结构：

```
mdma_core.c
mdma_core.h
    - 通道申请与释放
    - 单块传输
    - Block Repeat
    - Linked List
    - 超时和取消
    - 错误恢复

mdma_cache.c
mdma_cache.h
    - Source Clean
    - Destination Invalidate
    - Descriptor Clean
    - 对齐处理

mdma_resource.c
mdma_resource.h
    - 通道资源表
    - 触发源管理
    - 优先级管理

mdma_trace.c
mdma_trace.h
    - 传输统计
    - 错误记录
    - 延迟测量
    - 带宽统计

mdma_test.c
mdma_test.h
    - 数据一致性测试
    - 边界测试
    - 故障注入
    - 压力测试
```

推荐的统一接口：

```
typedef struct {
    uintptr_t src;
    uintptr_t dst;
    size_t length;
    mdma_width_t src_width;
    mdma_width_t dst_width;
    bool src_increment;
    bool dst_increment;
    uint32_t trigger;
    uint32_t flags;
} mdma_request_t;

typedef uint32_t mdma_handle_t;

int mdma_init(void);

int mdma_submit(const mdma_request_t *request,
                mdma_handle_t *handle);

int mdma_submit_2d(const mdma_2d_copy_t *request,
                   mdma_handle_t *handle);

int mdma_submit_linked(mdma_desc_t *first,
                       mdma_handle_t *handle);

int mdma_wait(mdma_handle_t handle,
              uint32_t timeout_ms);

int mdma_cancel(mdma_handle_t handle);

int mdma_get_status(mdma_handle_t handle,
                    mdma_status_t *status);

int mdma_recover(mdma_handle_t handle);
```

### 16.7 进阶学习方向

完成本课实践后，可以继续深入：

1. **GPDMA / LPDMA / Linked-List DMA**
    - 新一代通用 DMA 的链式请求设计。
2. **DMA Descriptor Ring**
    - Ethernet、USB、SDMMC 中的描述符环。
3. **Scatter-Gather DMA**
    - 非连续内存与零拷贝网络架构。
4. **DMA 与 Cache Coherency**
    - Cortex-A、SMMU、IOMMU、共享内存。
5. **总线矩阵与 QoS**
    - AXI 仲裁、突发长度、优先级和带宽整形。
6. **DMA 安全**
    - DMA 越界访问；
    - MPU 隔离；
    - TrustZone；
    - 外设访问控制；
    - 描述符篡改防护。
7. **零拷贝架构**
    - 网络接收；
    - 摄像头；
    - 音频；
    - 高速存储。
8. **专用数据搬运硬件**
    - DMA2D；
    - JPEG Codec；
    - PXP；
    - VENC / VDEC；
    - NPU 前处理引擎。
9. **实时性能验证**
    - WCET；
    - 总线利用率；
    - 中断响应最坏值；
    - 端到端数据延迟；
    - 长时间压力测试。

### 本课最终能力要求

能够在面对实际需求时，给出类似以下的工程结论：

```
UART 接收由普通 DMA + 环形缓冲区完成；
ADC 数据由普通 DMA 双缓冲采集；
MDMA 在块完成后负责数据重排和外部内存搬运；
图像二维复制使用 MDMA Block Repeat 或 DMA2D；
多段报文使用 MDMA Linked List；
所有 Buffer 和描述符位于 DMA 可达、Cache 策略明确的内存区域；
通过 Buffer Ownership、超时、错误恢复和总线压力测试保证长期稳定性。
```

**MDMA 的核心不是“让 CPU 少写几条复制指令”，而是把复杂、连续、可预测的数据搬运从软件控制流提升为硬件数据流。**