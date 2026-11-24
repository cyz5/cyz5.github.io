
> 本课以 STM32H7、STM32U5、STM32L4 等 MCU 中常见的 **BDMA（Basic DMA）** 为主要参考对象，同时抽象出适用于低功耗 DMA、基础型 DMA 和简化 DMA 控制器的通用设计方法。不同厂商对 BDMA 的命名和能力差异较大，部分芯片称为 **Basic DMA、Low-Power DMA、LPDMA 或 DMA Lite**，最终配置必须以目标芯片参考手册为准。

---

## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 BDMA 与普通 DMA、MDMA、LPDMA、DMA2D 的定位差异。
- 理解 BDMA 的基本硬件结构：
    - 通道；
    - 请求源；
    - 源地址；
    - 目标地址；
    - 传输计数；
    - 传输方向；
    - 地址递增；
    - 传输完成与错误标志。
- 理解 BDMA 与低功耗域、备份域、外设 FIFO 和低速外设之间的协同方式。
- 理解 BDMA 的优势和限制：
    - 功耗低；
    - 结构简单；
    - 资源少；
    - 吞吐量有限；
    - 高级链式能力不足。
- 理解 BDMA 在 Stop、Sleep、低功耗唤醒场景中的工作条件。

### 掌握

- 掌握 BDMA 单次外设到内存、内存到外设传输。
- 掌握 BDMA 与 UART、SPI、I²C、ADC、DAC、LPTIM 等低速外设的配合。
- 掌握 BDMA 环形缓冲、单次缓冲和简单双缓冲框架。
- 掌握 BDMA 通道、请求源和中断资源管理。
- 掌握 BDMA Buffer 的内存区域和低功耗域配置方法。
- 掌握 BDMA 传输超时、错误恢复和重启流程。

### 精通

- 能分析 BDMA 在低功耗模式中的时钟、复位、总线可达性和唤醒条件。
- 能判断 BDMA 是否适合某一外设和数据流。
- 能识别 BDMA 传输宽度、地址递增、请求映射和计数单位错误。
- 能量化 BDMA 的 CPU 节省、功耗收益、启动开销和传输吞吐量。
- 能处理 BDMA 与 CPU、Cache、RTOS、低功耗唤醒机制之间的一致性问题。

### 能够设计

- 能设计低功耗 UART 接收框架。
- 能设计低功耗 ADC 周期采样和唤醒方案。
- 能设计 BDMA + LPTIM + RTC 的传感器采集架构。
- 能设计 BDMA 驱动层的资源管理、状态机和错误恢复。
- 能根据数据量、实时性、功耗和可达内存选择 BDMA、普通 DMA 或 MDMA。

---

## 2. 前置要求

### 知识要求

- C 语言：
    - 指针；
    - 数组；
    - `volatile`；
    - 地址运算；
    - 对齐；
    - `uintptr_t`。
- MCU 时钟树、复位控制和低功耗模式。
- AHB、APB、总线矩阵和外设寄存器访问。
- UART、SPI、I²C、ADC、DAC 基本原理。
- 中断、NVIC、ISR 和临界区。
- RTOS 任务通知、事件组和队列。
- Cache、MPU、内存屏障基本概念。

### 技能要求

- 能阅读芯片参考手册中的 BDMA 章节。
- 能检查某个外设是否映射到 BDMA 请求源。
- 能配置链接脚本，将 Buffer 放入指定 SRAM 区域。
- 能使用逻辑分析仪验证 BDMA 对外设请求的响应。
- 能测量低功耗模式下的电流和唤醒时间。
- 能通过调试器查看 BDMA 状态寄存器、剩余传输数和错误标志。

---

## 3. 技术概述

## 3.1 BDMA 的定义

BDMA，Basic DMA，通常指一种功能较为精简的 DMA 控制器。

它一般支持：

- 外设到内存；
- 内存到外设；
- 部分平台支持内存到内存；
- 单次传输；
- 循环传输；
- 基本地址递增；
- 基本传输完成中断；
- 基本传输错误中断。

BDMA 通常不强调：

- 复杂链式描述符；
- 多级 FIFO；
- 高级突发传输；
- Scatter-Gather；
- 二维 Block Repeat；
- 复杂数据重排；
- 高带宽 AXI 主设备能力。

BDMA 的核心目标通常是：

> **以较低硬件复杂度和较低功耗，为低速或低功耗域外设提供基本数据搬运能力。**

---

## 3.2 BDMA 的典型数据路径

```
低功耗外设 / 低速外设
          |
          v
       BDMA Channel
          |
          v
     SRAM / 低功耗 SRAM
```

典型使用方式：

```
LPUART RX -> BDMA -> SRAM
ADC       -> BDMA -> SRAM
SPI RX    -> BDMA -> SRAM
DAC       <- BDMA <- SRAM
```

与 MDMA 的典型区别：

```
BDMA：
    低速外设实时搬运
    功能简单
    功耗较低

MDMA：
    大块内存搬运
    复杂地址组织
    链式和二维操作
    总线吞吐量较高
```

---

## 3.3 BDMA 的技术价值

### 降低 CPU 中断负载

如果 CPU 以字节中断方式接收 UART 数据，每个字节都可能触发一次 ISR。

BDMA 可以改为：

```
多个数据单元 -> 一次传输完成中断
```

### 支持低功耗运行

部分 MCU 中，BDMA 与低功耗 SRAM、低功耗外设时钟域相连，可以在 CPU 进入 Sleep 或部分 Stop 模式后继续搬运数据。

### 降低系统实现复杂度

对于简单数据流，BDMA 不需要：

- 复杂描述符；
- 链式管理；
- 大型 DMA 抽象层；
- 多通道调度器。

### 降低硬件资源和功耗

BDMA 通常拥有：

- 更少通道；
- 更小 FIFO；
- 更低总线能力；
- 更简单的仲裁逻辑。

因此功耗和面积开销通常低于高级 DMA 控制器。

---

## 3.4 BDMA 的限制

BDMA 的能力不能被高估。常见限制包括：

- 通道数量较少。
- 传输计数位宽较小。
- 不支持完整的双缓冲。
- 不支持复杂链式传输。
- 不支持二维地址偏移。
- 不支持高级 FIFO 或 Burst。
- 只能访问特定 SRAM 区域。
- 低功耗模式下可访问的内存更少。
- 某些平台仅支持 8 bit 和 16 bit 数据宽度。
- 某些平台没有独立请求复用器。
- 某些平台只能由低功耗外设触发。

因此，BDMA 的选型原则是：

> **数据量小、结构简单、频率较低、功耗敏感时优先考虑 BDMA。**

---

## 4. 核心特性横向对比

## 4.1 BDMA、普通 DMA、MDMA 对比

|维度|BDMA|普通 DMA|MDMA|
|---|---|---|---|
|主要定位|基础低功耗数据搬运|外设实时数据搬运|高级内存主控搬运|
|典型数据量|小到中等|中等到大|大块、复杂结构|
|外设请求|常见|强|通常通过事件或软件|
|通道数量|少|中等|视平台而定|
|FIFO 能力|无或很弱|中等|较强|
|Burst 能力|通常无|部分支持|较强|
|链式传输|通常不支持|视平台而定|常见|
|二维搬运|不适合|不方便|支持度较高|
|低功耗支持|通常较好|视 DMA 域而定|通常较弱|
|硬件复杂度|低|中|高|
|软件复杂度|低|中|中高|
|典型应用|LPUART、低功耗 ADC|UART、SPI、ADC|图像、存储、数据重排|

## 4.2 BDMA 与中断驱动对比

|维度|中断驱动|BDMA|
|---|---|---|
|每数据单元 CPU 介入|常见|不需要|
|CPU 占用|中高|低|
|单个数据延迟|低|低到中|
|低功耗支持|一般|较好|
|软件复杂度|低|中|
|缓冲管理|简单|需要额外处理|
|适合连续流|一般|较好|
|适合极低速单字节|可以|可能不划算|
|典型风险|ISR 过多|地址、计数和唤醒配置错误|

## 4.3 BDMA 工作模式对比

|模式|行为|适用场景|优点|风险|
|---|---|---|---|---|
|单次模式|完成后停止|固定长度数据块|简单|需要重新启动|
|循环模式|完成后回到起始地址|连续采样|自动运行|覆盖未消费数据|
|半传输|半块完成触发|连续流|降低单次延迟|处理必须及时|
|双缓冲|视芯片支持情况|采集与处理并行|所有权清晰|硬件支持不统一|
|内存到外设|Buffer 写入外设|DAC、LPUART TX|CPU 负载低|外设结束状态需额外判断|
|外设到内存|外设写入 Buffer|UART、ADC、SPI RX|适合采集|缓冲区溢出|

---

## 5. 核心特性横向对比：低功耗域中的 DMA 方案

|方案|CPU 是否需要运行|低功耗能力|数据复杂度|典型场景|
|---|---|---|---|---|
|CPU 轮询|是|差|低|极低速传感器|
|外设中断|可唤醒|中|低|低速命令|
|BDMA|可保持睡眠|较好|低～中|LPUART、ADC|
|LPDMA|通常更好|很好|中|Stop 模式采集|
|普通 DMA|依赖 DMA 域|中|中|普通高速外设|
|MDMA|通常需较完整系统时钟|一般|高|大块搬运|

---

## 5. 底层原理与功能特性深度解析

## 5.1 BDMA 的基本硬件结构

一个简化的 BDMA 通道可以抽象为：

```
+-------------------+
外设请求 ------>| Request Logic     |
                +---------+---------+
                          |
                          v
                +-------------------+
                | Address Generator|
                +---------+---------+
                          |
                          v
                +-------------------+
                | Transfer Counter |
                +---------+---------+
                          |
                          v
                +-------------------+
                | Bus Master       |
                +---------+---------+
                          |
                          v
                   SRAM / 外设寄存器
```

一次传输通常执行：

1. 外设产生 DMA Request。
2. BDMA 检查通道是否使能。
3. 仲裁访问总线。
4. 从源地址读取一个数据单元。
5. 向目标地址写入一个数据单元。
6. 更新源地址和目标地址。
7. 递减剩余计数。
8. 产生半传输、传输完成或错误事件。

---

## 5.2 BDMA 核心配置项

不同平台寄存器命名不同，但通常包括：

```
typedef struct {
    volatile uint32_t CCR;   /* Channel Control Register */
    volatile uint32_t CNDTR; /* Number of Data Register */
    volatile uint32_t CPAR;  /* Peripheral Address Register */
    volatile uint32_t CMAR;  /* Memory Address Register */
    volatile uint32_t ISR;   /* Interrupt Status Register */
    volatile uint32_t IFCR;  /* Interrupt Flag Clear Register */
} bdma_channel_regs_t;
```

典型配置项：

- `DIR`：方向。
- `MINC`：内存地址递增。
- `PINC`：外设地址递增。
- `MSIZE`：内存数据宽度。
- `PSIZE`：外设数据宽度。
- `CIRC`：循环模式。
- `TCIE`：传输完成中断。
- `HTIE`：半传输中断。
- `TEIE`：传输错误中断。
- `PL`：通道优先级。
- `EN`：通道使能。

BDMA 通常不像高级 DMA 那样拥有丰富的：

- FIFO 控制；
- Burst 配置；
- Double Buffer；
- 链式描述符；
- 地址偏移；
- 请求生成器。

---

## 5.3 BDMA 单次传输

下面使用平台无关接口表示一个基础 BDMA 驱动。

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>

typedef enum {
    BDMA_OK = 0,
    BDMA_ERR_PARAM = -1,
    BDMA_ERR_BUSY = -2,
    BDMA_ERR_TIMEOUT = -3,
    BDMA_ERR_HW = -4,
    BDMA_ERR_UNSUPPORTED = -5,
} bdma_status_t;

typedef enum {
    BDMA_PERIPH_TO_MEM = 0,
    BDMA_MEM_TO_PERIPH = 1,
    BDMA_MEM_TO_MEM = 2,
} bdma_direction_t;

typedef enum {
    BDMA_WIDTH_8BIT = 1,
    BDMA_WIDTH_16BIT = 2,
    BDMA_WIDTH_32BIT = 4,
} bdma_width_t;

typedef struct {
    volatile bool busy;
    volatile bool done;
    volatile bool error;
    volatile uint32_t error_flags;
} bdma_state_t;

static bdma_state_t g_bdma_state;
```

### 基本单次传输接口

```
bdma_status_t bdma_start(const void *src,
                         void *dst,
                         size_t length,
                         bdma_direction_t direction,
                         bdma_width_t width)
{
    if (src == NULL || dst == NULL || length == 0U) {
        return BDMA_ERR_PARAM;
    }

    if ((length % (size_t)width) != 0U) {
        return BDMA_ERR_PARAM;
    }

    if (g_bdma_state.busy) {
        return BDMA_ERR_BUSY;
    }

    bdma_disable_channel(BDMA_CHANNEL_0);
    bdma_clear_all_flags(BDMA_CHANNEL_0);

    g_bdma_state.busy = true;
    g_bdma_state.done = false;
    g_bdma_state.error = false;
    g_bdma_state.error_flags = 0U;

    bdma_set_memory_address(BDMA_CHANNEL_0,
                            (uintptr_t)dst);

    bdma_set_peripheral_address(BDMA_CHANNEL_0,
                                (uintptr_t)src);

    bdma_set_transfer_length(BDMA_CHANNEL_0,
                             length / (size_t)width);

    bdma_set_memory_width(BDMA_CHANNEL_0, width);
    bdma_set_peripheral_width(BDMA_CHANNEL_0, width);

    bdma_set_memory_increment(BDMA_CHANNEL_0,
                              true);

    /*
     * 默认外设地址固定。
     * 对内存到内存模式，平台可能需要单独配置源地址。
     */
    bdma_set_peripheral_increment(BDMA_CHANNEL_0,
                                  false);

    bdma_set_direction(BDMA_CHANNEL_0,
                       direction);

    bdma_set_circular_mode(BDMA_CHANNEL_0,
                           false);

    bdma_enable_irq(BDMA_CHANNEL_0,
                    BDMA_IRQ_TRANSFER_COMPLETE |
                    BDMA_IRQ_TRANSFER_ERROR);

    bdma_enable_channel(BDMA_CHANNEL_0);

    return BDMA_OK;
}
```

注意：

- `length` 是字节数还是传输元素数，必须在驱动层统一。
- 一些 BDMA 的 `CNDTR` 单位是数据元素，不是字节。
- 不能将字节长度直接写入要求元素数量的寄存器。
- 源地址和目标地址的配置方式随 BDMA 方向而变化。

---

## 5.4 BDMA 与 LPUART RX 协同

低功耗 UART 是 BDMA 的典型应用。

### 典型数据路径

```
LPUART RX Data Register
          |
          v
        BDMA
          |
          v
低功耗 SRAM / SRAM4
          |
          v
CPU 唤醒后解析
```

### 初始化流程

```
1. 打开 BDMA 时钟
2. 打开 LPUART 时钟
3. 配置 BDMA 请求源为 LPUART_RX
4. 配置外设地址为 LPUART_RDR
5. 配置内存地址为 RX Buffer
6. 配置数据宽度为 8 bit
7. 配置外设地址固定
8. 配置内存地址递增
9. 配置循环或单次模式
10. 清除状态标志
11. 使能 BDMA
12. 使能 LPUART DMA RX
13. 进入 Sleep / Stop 模式
```

### LPUART BDMA 接收代码

```
#define LPUART_RX_BUFFER_SIZE 128U

static uint8_t lpuart_rx_buffer[LPUART_RX_BUFFER_SIZE]
    __attribute__((section(".lowpower_sram"), aligned(4)));

static volatile uint32_t lpuart_rx_done;
static volatile uint32_t lpuart_rx_error;

int lpuart_bdma_rx_start(void)
{
    bdma_disable_channel(BDMA_CHANNEL_0);
    bdma_clear_all_flags(BDMA_CHANNEL_0);

    bdma_set_request(BDMA_CHANNEL_0,
                     BDMA_REQUEST_LPUART1_RX);

    bdma_set_peripheral_address(
        BDMA_CHANNEL_0,
        (uintptr_t)&LPUART1->RDR);

    bdma_set_memory_address(
        BDMA_CHANNEL_0,
        (uintptr_t)lpuart_rx_buffer);

    bdma_set_transfer_length(
        BDMA_CHANNEL_0,
        LPUART_RX_BUFFER_SIZE);

    bdma_set_peripheral_width(
        BDMA_CHANNEL_0,
        BDMA_WIDTH_8BIT);

    bdma_set_memory_width(
        BDMA_CHANNEL_0,
        BDMA_WIDTH_8BIT);

    bdma_set_peripheral_increment(
        BDMA_CHANNEL_0,
        false);

    bdma_set_memory_increment(
        BDMA_CHANNEL_0,
        true);

    bdma_set_direction(
        BDMA_CHANNEL_0,
        BDMA_PERIPH_TO_MEM);

    bdma_set_circular_mode(
        BDMA_CHANNEL_0,
        true);

    bdma_enable_irq(
        BDMA_CHANNEL_0,
        BDMA_IRQ_HALF_TRANSFER |
        BDMA_IRQ_TRANSFER_COMPLETE |
        BDMA_IRQ_TRANSFER_ERROR);

    bdma_enable_channel(BDMA_CHANNEL_0);
    lpuart_enable_dma_rx(LPUART1);

    return 0;
}
```

---

## 5.5 BDMA 环形模式

环形模式下，BDMA 完成一个缓冲区后自动回到起始地址：

```
Buffer[0] -> Buffer[1] -> ... -> Buffer[N-1]
      ^                              |
      +------------------------------+
```

### 简单环形读写模型

```
typedef struct {
    uint8_t *buffer;
    size_t size;
    size_t read_pos;
    uint32_t overflow_count;
} bdma_ring_t;

static bdma_ring_t g_lpuart_ring = {
    .buffer = lpuart_rx_buffer,
    .size = LPUART_RX_BUFFER_SIZE,
    .read_pos = 0U,
    .overflow_count = 0U,
};
```

读取当前写位置：

```
static size_t lpuart_bdma_get_write_pos(void)
{
    uint32_t remaining =
        bdma_get_remaining(BDMA_CHANNEL_0);

    size_t write_pos =
        LPUART_RX_BUFFER_SIZE - remaining;

    return write_pos % LPUART_RX_BUFFER_SIZE;
}
```

### 处理可用数据

```
static size_t ring_available(const bdma_ring_t *ring,
                             size_t write_pos)
{
    if (write_pos >= ring->read_pos) {
        return write_pos - ring->read_pos;
    }

    return ring->size - ring->read_pos + write_pos;
}

static size_t bdma_ring_read(bdma_ring_t *ring,
                             size_t write_pos,
                             uint8_t *output,
                             size_t output_size)
{
    size_t available;
    size_t count;

    if (ring == NULL ||
        output == NULL ||
        output_size == 0U) {
        return 0U;
    }

    available = ring_available(ring, write_pos);
    count = (available < output_size) ?
            available :
            output_size;

    for (size_t i = 0U; i < count; ++i) {
        output[i] = ring->buffer[ring->read_pos];

        ring->read_pos++;
        if (ring->read_pos >= ring->size) {
            ring->read_pos = 0U;
        }
    }

    return count;
}
```

### 环形模式的关键问题

BDMA 环形缓冲区存在两个位置：

```
BDMA 写位置
CPU 读位置
```

必须保证：

DataProduced−DataConsumed≤BufferSizeDataProduced−DataConsumed≤BufferSize

当：

DataProduced−DataConsumed>BufferSizeDataProduced−DataConsumed>BufferSize

就发生溢出。

工程上建议使用单调递增计数，而不是仅使用取模后的索引。

---

## 5.6 BDMA 半传输模式

如果 BDMA 支持半传输中断，可以将 Buffer 分为两部分：

```
+-------------------+-------------------+
| Half 0            | Half 1            |
+-------------------+-------------------+
       HT                    TC
```

### 中断框架

```
void BDMA_Channel0_IRQHandler(void)
{
    uint32_t flags =
        bdma_get_flags(BDMA_CHANNEL_0);

    if ((flags & BDMA_FLAG_TRANSFER_ERROR) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_0,
            BDMA_FLAG_TRANSFER_ERROR);

        bdma_disable_channel(BDMA_CHANNEL_0);

        g_lpuart_rx_error++;
        lpuart_bdma_error_recover();
        return;
    }

    if ((flags & BDMA_FLAG_HALF_TRANSFER) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_0,
            BDMA_FLAG_HALF_TRANSFER);

        lpuart_rx_half_ready_notify_from_isr();
    }

    if ((flags & BDMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_0,
            BDMA_FLAG_TRANSFER_COMPLETE);

        lpuart_rx_full_ready_notify_from_isr();
    }
}
```

BDMA 的半传输能力并不是所有平台都支持。若不支持，可以使用：

- UART IDLE；
- 外设 FIFO 阈值；
- 定时轮询 `NDTR`；
- 软件超时；
- 单次 DMA 重启。

---

## 5.7 BDMA 与 UART IDLE 协同

对于不定长 UART 数据，单独依赖 BDMA TC 不够，因为无法知道帧何时结束。

推荐架构：

```
LPUART RX
   |
   +--> BDMA Circular Buffer
   |
   +--> UART IDLE Event
                 |
                 v
           唤醒协议任务
                 |
                 v
           读取 DMA 写指针
                 |
                 v
           解析变长帧
```

### 处理逻辑

```
void LPUART1_IRQHandler(void)
{
    if (lpuart_idle_flag(LPUART1)) {
        lpuart_clear_idle_flag(LPUART1);

        /*
         * 不停止 BDMA，先记录当前写位置。
         */
        size_t write_pos =
            lpuart_bdma_get_write_pos();

        lpuart_notify_rx_frame_from_isr(write_pos);
    }
}
```

任务侧：

```
void lpuart_protocol_task(void *arg)
{
    uint8_t parse_buffer[64];

    for (;;) {
        size_t write_pos;

        if (!lpuart_wait_rx_event(&write_pos,
                                  portMAX_DELAY)) {
            continue;
        }

        size_t available =
            ring_available(&g_lpuart_ring,
                           write_pos);

        while (available > 0U) {
            size_t count =
                bdma_ring_read(&g_lpuart_ring,
                               write_pos,
                               parse_buffer,
                               sizeof(parse_buffer));

            if (count == 0U) {
                break;
            }

            protocol_feed(parse_buffer, count);

            available =
                ring_available(&g_lpuart_ring,
                               write_pos);
        }
    }
}
```

---

## 5.8 BDMA 与低功耗模式

BDMA 能否在低功耗模式运行，不是由“BDMA”这个名称决定的，而是由以下条件共同决定：

```
BDMA 时钟是否保持？
BDMA 所属电源域是否保持？
外设时钟是否保持？
目标 SRAM 是否保持？
请求源是否允许在低功耗模式产生？
中断唤醒源是否配置？
唤醒后的时钟是否已恢复？
```

### 典型低功耗数据路径

```
LPUART / LPTIM / ADC
          |
          v
        BDMA
          |
          v
      SRAM4 / SRAM2
          |
          v
CPU Stop Mode
          |
          v
事件到达后唤醒
```

### 进入低功耗前的检查

```
typedef enum {
    LP_OK = 0,
    LP_ERR_DMA_NOT_READY = -1,
    LP_ERR_MEMORY_NOT_RETENTION = -2,
    LP_ERR_CLOCK_NOT_READY = -3,
    LP_ERR_REQUEST_NOT_SUPPORTED = -4,
} lp_status_t;

lp_status_t bdma_prepare_low_power(void)
{
    if (!bdma_is_enabled(BDMA_CHANNEL_0)) {
        return LP_ERR_DMA_NOT_READY;
    }

    if (!memory_is_retention_region(lpuart_rx_buffer,
                                    sizeof(lpuart_rx_buffer))) {
        return LP_ERR_MEMORY_NOT_RETENTION;
    }

    if (!bdma_clock_retained_in_stop_mode()) {
        return LP_ERR_CLOCK_NOT_READY;
    }

    if (!request_supported_in_stop_mode(
            BDMA_REQUEST_LPUART1_RX)) {
        return LP_ERR_REQUEST_NOT_SUPPORTED;
    }

    cpu_dsb();

    return LP_OK;
}
```

### 唤醒后的恢复顺序

```
1. 恢复系统时钟
2. 恢复外设时钟
3. 检查 BDMA 状态
4. 检查传输错误
5. 读取剩余传输数
6. 更新软件写指针
7. 处理接收到的数据
8. 必要时重新配置 BDMA
```

---

## 5.9 BDMA 与 Cache

BDMA 通常用于低功耗域和 SRAM，但如果目标平台开启 D-Cache，仍然必须处理一致性。

### BDMA 接收

```
BDMA 写 SRAM
      |
      v
CPU Cache 可能保留旧数据
      |
      v
CPU 读取旧 Cache Line
```

在 CPU 读取新数据前：

```
dma_cache_invalidate(rx_buffer, received_length);
cpu_dmb();
```

### BDMA 发送

```
CPU 修改发送 Buffer
      |
      v
新数据仍在 Cache 中
      |
      v
BDMA 从 SRAM 读取旧数据
```

启动 BDMA 前：

```
dma_cache_clean(tx_buffer, transmit_length);
cpu_dsb();
```

### 低功耗场景的额外问题

进入 Stop 模式前，如果 Cache 中存在脏数据：

```
Cache 中是新数据
SRAM 中是旧数据
进入低功耗
BDMA 读取 SRAM
```

因此必须在进入低功耗前：

```
dma_cache_clean(lpuart_tx_buffer,
                sizeof(lpuart_tx_buffer));
cpu_dsb();
```

如果 BDMA 接收期间 CPU 可能曾经缓存过目标 Buffer，则唤醒后必须失效对应 Cache Line。

---

## 5.10 BDMA 传输宽度与计数单位

BDMA 的 `CNDTR` 常常以“传输元素数”为单位，而不是字节数。

例如：

```
数据宽度：16 bit
CNDTR：128
实际字节数：128 × 2 = 256 Byte
```

因此驱动中必须统一接口：

```
static bool bdma_length_valid(size_t bytes,
                              bdma_width_t width)
{
    if (width == 0U) {
        return false;
    }

    return (bytes % (size_t)width) == 0U;
}

static uint32_t bdma_count_from_bytes(size_t bytes,
                                      bdma_width_t width)
{
    return (uint32_t)(bytes / (size_t)width);
}
```

错误示例：

```
uint16_t adc_buffer[128];

bdma_set_transfer_length(BDMA_CHANNEL_0,
                         sizeof(adc_buffer));
```

如果 BDMA 的计数单位是半字，则错误地配置成：

```
256 个半字
```

而不是预期的：

```
128 个半字
```

正确实现：

```
bdma_set_transfer_length(BDMA_CHANNEL_0,
                         sizeof(adc_buffer) /
                         sizeof(adc_buffer[0]));
```

---

## 5.11 BDMA 请求映射与通道冲突

BDMA 通常通道较少，资源冲突比普通 DMA 更常见。

典型资源表：

```
typedef struct {
    uint8_t channel;
    uint32_t request;
    const char *owner;
    uint8_t priority;
    bool low_power_capable;
    bool in_use;
} bdma_resource_t;

static bdma_resource_t g_bdma_resources[] = {
    {
        .channel = 0U,
        .request = BDMA_REQUEST_LPUART1_RX,
        .owner = "lpuart_rx",
        .priority = 2U,
        .low_power_capable = true,
        .in_use = false,
    },
    {
        .channel = 1U,
        .request = BDMA_REQUEST_ADC4,
        .owner = "sensor_adc",
        .priority = 1U,
        .low_power_capable = true,
        .in_use = false,
    },
};
```

启动阶段应验证：

- 一个通道是否被多个外设使用。
- 请求源是否确实映射到该通道。
- 请求源是否支持低功耗模式。
- 外设和 BDMA 的 IRQ 是否冲突。
- 通道优先级是否符合实时性要求。

---

## 6. 性能量化分析

以下数据为示例测试条件：

- MCU：Cortex-M33，160 MHz。
- BDMA 时钟：80 MHz。
- UART：115200 bit/s。
- LPUART：9600 bit/s。
- ADC：100 kSPS。
- SRAM：内部低功耗 SRAM。
- D-Cache：平台可能开启，示例数据不包含极端 Cache Miss。

实际数据取决于芯片架构。

## 6.1 UART 字节到达时间

UART 使用：

```
1 起始位 + 8 数据位 + 1 停止位 = 10 bit/Byte
```

### 115200 baud

Tbyte=10115200≈86.8μsTbyte​=11520010​≈86.8μs

每秒数据量：

Throughput=11520010=11520Byte/sThroughput=10115200​=11520Byte/s

### 9600 baud

Tbyte=109600≈1.04msTbyte​=960010​≈1.04ms

对于 9600 baud：

- 每字节中断本身并不一定造成严重 CPU 负载。
- 但若 CPU 频繁进入唤醒状态，系统功耗可能明显增加。
- BDMA 的主要收益变成 **减少唤醒次数**，而不仅是减少 CPU 指令。

## 6.2 CPU 占用计算

假设 115200 baud：

```
数据率：11520 Byte/s
每字节 ISR：2.0 μs
```

CPU 占用：

CPUIRQ=11520×2μs=23.04ms/s≈2.3%CPUIRQ​=11520×2μs=23.04ms/s≈2.3%

如果使用 BDMA，每 32 Byte 触发一次任务通知：

ISRrate=1152032=360次/sISRrate​=3211520​=360次/s

假设一次块处理和通知耗时 4 μs：

CPUBDMA=360×4μs=1.44ms/s≈0.14%CPUBDMA​=360×4μs=1.44ms/s≈0.14%

### 低功耗收益

如果每次 CPU 唤醒额外消耗：

```
唤醒时间：20 μs
```

逐字节中断的唤醒时间：

11520×20μs=230.4ms/s11520×20μs=230.4ms/s

每 32 Byte 唤醒一次：

360×20μs=7.2ms/s360×20μs=7.2ms/s

理论唤醒活动时间约降低：

1−7.2230.4=96.875%1−230.47.2​=96.875%

这通常比 CPU 指令节省更有价值。

## 6.3 ADC 采样缓冲周期

假设：

```
ADC 采样率：100 kSPS
Buffer：256 个样本
```

整个 Buffer 填充时间：

Tbuffer=256100000=2.56msTbuffer​=100000256​=2.56ms

半缓冲时间：

Thalf=128100000=1.28msThalf​=100000128​=1.28ms

如果 BDMA 半传输事件触发后，CPU 处理一半数据，那么最坏处理时间必须满足：

Tprocess,max<1.28msTprocess,max​<1.28ms

工业系统建议：

Tprocess,max<0.7×ThalfTprocess,max​<0.7×Thalf​

即：

Tprocess,max<896μsTprocess,max​<896μs

为中断抖动、Cache Miss 和 RTOS 调度保留余量。

## 6.4 BDMA 启动开销

BDMA 单次传输需要：

1. 禁止通道。
2. 清除标志。
3. 配置请求源。
4. 写入源 / 目标地址。
5. 写入传输数量。
6. 配置方向和地址递增。
7. 使能中断。
8. 启动通道。
9. 启动外设 DMA 请求。

示例测量：

|项目|典型时间|
|---|---|
|BDMA 寄存器配置|0.8～2.0 μs|
|完成 ISR|0.5～1.5 μs|
|RTOS 通知|0.5～3.0 μs|
|Cache 操作|0～数 μs|
|总固定开销|约 2～7 μs|

因此对于很小的数据块，BDMA 可能不如直接 CPU 访问。

### 推荐阈值

```
#define BDMA_MIN_TRANSFER_SIZE 32U
```

实际阈值应通过目标平台实测：

```
如果数据量 < 阈值：
    CPU 直接处理

如果数据量 >= 阈值：
    使用 BDMA
```

但低功耗场景需要另外考虑：

```
即使数据很小，只要 BDMA 能避免 CPU 唤醒，
仍可能值得使用 BDMA。
```

## 6.5 功耗估算

设：

- Sleep 电流：`I_sleep = 5 μA`
- CPU 活跃电流：`I_active = 8 mA`
- CPU 每秒活跃时间：`t_active`

平均电流：

Iavg=Isleep×(1−tactive)+Iactive×tactiveIavg​=Isleep​×(1−tactive​)+Iactive​×tactive​

假设：

```
CPU 每秒活跃 230 ms
```

Iavg≈5μA×0.77+8mA×0.23≈1.84mAIavg​≈5μA×0.77+8mA×0.23≈1.84mA

若使用 BDMA 后 CPU 每秒活跃 10 ms：

Iavg≈5μA×0.99+8mA×0.01≈85μAIavg​≈5μA×0.99+8mA×0.01≈85μA

实际系统还需要计入：

- 外设工作电流；
- BDMA 自身电流；
- 低功耗 SRAM 保持电流；
- 时钟树电流；
- 唤醒和恢复瞬态电流。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
数据是否由外设产生或消费？
|
+-- 否 --> 是否为大块内存复制？
|          |
|          +-- 是 --> 使用 MDMA / 普通 DMA
|          +-- 否 --> CPU 处理
|
+-- 是 --> 系统是否有低功耗或低速域要求？
           |
           +-- 否 --> 数据量和速率是否较高？
           |          |
           |          +-- 是 --> 使用普通 DMA
           |          +-- 否 --> 中断或普通 DMA
           |
           +-- 是 --> 外设和 DMA 是否允许在目标低功耗模式运行？
                      |
                      +-- 否 --> 使用外设中断唤醒
                      |
                      +-- 是 --> 是否只需简单连续搬运？
                                 |
                                 +-- 是 --> 使用 BDMA / LPDMA
                                 |
                                 +-- 否 --> 是否需要链式、二维或复杂重排？
                                            |
                                            +-- 是 --> 普通 DMA + MDMA
                                            +-- 否 --> 重新评估 BDMA 配置
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|低功耗 UART 接收|BDMA + 环形 Buffer|降低 CPU 唤醒次数|
|LPUART 变长帧|BDMA + IDLE|支持连续接收和帧边界检测|
|低功耗 ADC 采样|BDMA + LPTIM 触发|CPU 可周期性唤醒|
|高速 ADC|普通 DMA|BDMA 吞吐和缓存能力可能不足|
|低速 SPI 传感器|BDMA|配置简单、功耗较低|
|高速 SPI Flash|普通 DMA / MDMA|BDMA 可能带宽不足|
|DAC 低速波形|BDMA 循环模式|周期性输出|
|大块内存复制|MDMA / 普通 DMA|BDMA 功能和带宽有限|
|多段内存聚合|MDMA Linked List|BDMA 通常不支持|
|规则二维图像复制|MDMA / DMA2D|BDMA 不适合|
|极低速单字节事件|中断|BDMA 启动开销可能不划算|
|Stop 模式数据采集|BDMA / LPDMA|取决于低功耗域支持|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：优先确认低功耗可达性

不能仅凭普通运行模式验证 BDMA。

必须分别验证：

```
Run 模式：
    BDMA 是否工作？

Sleep 模式：
    BDMA 是否工作？

Stop 模式：
    BDMA、外设和 SRAM 是否保持？

唤醒后：
    状态和数据是否完整？
```

### 原则二：BDMA Buffer 放在正确内存区域

推荐优先级：

1. BDMA 明确可访问的内部 SRAM。
2. 低功耗保持 SRAM。
3. 非 Cacheable SRAM。
4. 普通 SRAM，但配合 Cache Maintenance。
5. 外部存储器，仅在参考手册明确支持时使用。

### 原则三：不要让 BDMA 承担复杂数据组织

BDMA 适合：

```
固定外设地址 <-> 线性 Buffer
```

不适合：

```
非连续地址
复杂二维 stride
多个不同长度段
动态描述符链
```

遇到复杂布局，应使用：

- 普通 DMA + MDMA；
- GPDMA；
- DMA2D；
- CPU / DSP；
- 专用外设控制器。

### 原则四：低功耗系统优先降低唤醒次数

低功耗数据流应尽量使用：

```
DMA 块传输
+
IDLE / 半传输 / 超时事件
+
一次任务处理多个数据单元
```

不要使用：

```
每字节中断
+
每字节唤醒
+
每字节任务切换
```

### 原则五：所有 BDMA 传输都要有终止条件

必须设计：

- 传输完成；
- 超时；
- 外设停止；
- DMA 错误；
- 接收溢出；
- 低功耗退出；
- 系统复位；
- 传输取消。

## 8.2 BDMA 资源决策矩阵

评分范围为 1～5，分数越高越适合。

|方案|低功耗|高吞吐|配置简单度|复杂数据组织|CPU 释放|
|---|---|---|---|---|---|
|CPU 轮询|1|1|5|3|1|
|外设中断|2|2|4|3|2|
|BDMA|5|2～3|4|1|4|
|普通 DMA|3|4～5|3|2～3|5|
|MDMA|2|5|2|5|5|
|LPDMA|5|3～4|3|3|5|

## 8.3 工业级编码规范

- 统一定义长度单位：
    - 接口层使用字节；
    - 硬件寄存器层转换为数据元素。
- 所有地址使用 `uintptr_t`。
- 所有 Buffer 显式指定 section 和对齐。
- 所有 BDMA 通道使用资源表管理。
- 进入低功耗前检查：
    - 通道使能；
    - 时钟保持；
    - 外设状态；
    - SRAM 保持；
    - 中断唤醒源。
- 中断服务函数只完成：
    - 读取状态；
    - 清除标志；
    - 更新指针；
    - 投递事件。
- 不在 BDMA ISR 中调用阻塞 API。
- 接收环形 Buffer 必须记录溢出次数。
- 错误恢复不能只清中断标志，还要重新初始化通道。
- 发送完成不等于外设物理发送完成。
- 对低功耗唤醒后的时钟恢复顺序进行明确设计。
- 在生产测试中验证 Stop 模式下的真实电流和数据完整性。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：把字节数直接写入元素计数寄存器

### 错误代码

```
uint16_t adc_buffer[128];

bdma_set_memory_width(BDMA_CHANNEL_0,
                      BDMA_WIDTH_16BIT);

bdma_set_transfer_length(BDMA_CHANNEL_0,
                         sizeof(adc_buffer));
```

### 根因

`sizeof(adc_buffer)` 为 256 Byte，而 BDMA 的传输计数可能要求填写 16 bit 元素数量。

### 正确实现

```
bdma_set_transfer_length(
    BDMA_CHANNEL_0,
    sizeof(adc_buffer) /
    sizeof(adc_buffer[0]));
```

### 风险影响

- BDMA 访问越界。
- 缓冲区被覆盖。
- 传输完成时间变成预期的两倍。
- 发生 HardFault 或总线错误。

---

## 9.2 错误二：低功耗模式下 Buffer 位于非保持 SRAM

### 错误代码

```
static uint8_t rx_buffer[128]
    __attribute__((section(".fast_sram")));
```

系统进入 Stop 模式后，该 SRAM 电源域被关闭。

### 根因

普通运行模式下代码工作正常，但低功耗模式下目标内存内容不再保持，或者 BDMA 无法访问该区域。

### 正确实现

链接脚本：

```
.lowpower_buffer (NOLOAD) :
{
    . = ALIGN(4);
    *(.lowpower_sram)
    . = ALIGN(4);
} >SRAM_RETENTION
```

C 代码：

```
static uint8_t rx_buffer[128]
    __attribute__((section(".lowpower_sram"),
                   aligned(4)));
```

### 风险影响

- 唤醒后收到的数据为空。
- 帧头丢失。
- BDMA 访问错误。
- 低功耗测试与正常运行测试结果不一致。

---

## 9.3 错误三：BDMA 通道和请求源映射错误

### 错误代码

```
bdma_set_request(BDMA_CHANNEL_0,
                 BDMA_REQUEST_UART1_TX);

/* 实际外设使用的是 LPUART1_RX */
lpuart_enable_dma_rx(LPUART1);
```

### 根因

BDMA 通道配置的请求源与实际外设请求不一致。

### 正确实现

```
bdma_set_request(BDMA_CHANNEL_0,
                 BDMA_REQUEST_LPUART1_RX);

lpuart_enable_dma_rx(LPUART1);
```

同时在启动日志中记录：

```
log_info("BDMA ch=%u request=%u peripheral=%s",
         0U,
         BDMA_REQUEST_LPUART1_RX,
         "LPUART1_RX");
```

### 风险影响

- BDMA 通道完全不响应。
- `CNDTR` 不变化。
- 没有传输完成中断。
- 调试时误以为外设或时钟故障。

---

## 9.4 错误四：进入 Stop 模式前没有确认时钟保持

### 错误代码

```
bdma_enable_channel(BDMA_CHANNEL_0);
lpuart_enable_dma_rx(LPUART1);

/* 直接进入 Stop */
enter_stop_mode();
```

### 根因

BDMA、LPUART 或请求路由器的时钟在 Stop 模式下被关闭。

### 正确实现

```
if (!bdma_clock_retained_in_stop_mode() ||
    !lpuart_clock_retained_in_stop_mode()) {
    return -1;
}

if (!bdma_request_allowed_in_stop_mode(
        BDMA_REQUEST_LPUART1_RX)) {
    return -2;
}

cpu_dsb();
enter_stop_mode();
```

### 风险影响

- Stop 模式下数据丢失。
- 唤醒事件不产生。
- 系统看起来进入了低功耗，但通信完全中断。

---

## 9.5 错误五：循环 DMA 未处理 Buffer 溢出

### 错误代码

```
void lpuart_rx_task(void *arg)
{
    for (;;) {
        size_t write_pos =
            lpuart_bdma_get_write_pos();

        parse_from_ring(write_pos);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
```

### 根因

任务每 100 ms 才处理一次数据，期间 BDMA 可能已经绕环多次。

### 正确实现

```
void lpuart_rx_task(void *arg)
{
    for (;;) {
        size_t write_pos =
            lpuart_bdma_get_write_pos();

        size_t available =
            ring_available(&g_lpuart_ring,
                           write_pos);

        if (available >= g_lpuart_ring.size) {
            g_lpuart_ring.overflow_count++;

            /*
             * 保留最新一圈数据。
             */
            g_lpuart_ring.read_pos = write_pos;
        } else {
            consume_ring_data(&g_lpuart_ring,
                              write_pos,
                              available);
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
```

### 风险影响

- 数据被覆盖。
- 协议帧无法重组。
- 长时间运行后通信随机失步。
- 丢包原因难以追踪。

---

## 9.6 错误六：BDMA 传输完成后立即关闭外设发送器

### 错误代码

```
void BDMA_TX_IRQHandler(void)
{
    if (bdma_tc_flag(BDMA_CHANNEL_1)) {
        bdma_clear_tc_flag(BDMA_CHANNEL_1);

        lpuart_disable(LPUART1);
        rs485_set_tx_enable(false);
    }
}
```

### 根因

BDMA TC 只表示最后一个数据已经写入外设数据寄存器，外设移位寄存器可能仍在发送。

### 正确实现

```
void BDMA_TX_IRQHandler(void)
{
    if (bdma_tc_flag(BDMA_CHANNEL_1)) {
        bdma_clear_tc_flag(BDMA_CHANNEL_1);

        lpuart_enable_transmit_complete_irq(LPUART1);
    }
}

void LPUART1_IRQHandler(void)
{
    if (lpuart_transmit_complete_flag(LPUART1)) {
        lpuart_clear_transmit_complete_flag(LPUART1);
        lpuart_disable_transmit_complete_irq(LPUART1);

        rs485_set_tx_enable(false);
    }
}
```

### 风险影响

- 最后一个字节被截断。
- RS-485 总线方向切换过早。
- 对端校验失败。
- 低波特率时不明显，高波特率时更容易暴露。

---

## 10. 多机制组合使用方案

## 10.1 BDMA + LPUART + IDLE + RTOS

### 总体架构

```
LPUART RX
    |
    v
BDMA Circular Buffer
    |
    +--> IDLE Event
    +--> Half / Full Event
    +--> DMA Error
             |
             v
      ISR 更新写指针
             |
             v
      RTOS Task Notification
             |
             v
      Protocol Parser Task
```

### 设计目标

- CPU 不逐字节唤醒。
- 支持变长数据帧。
- 支持 Stop 模式。
- 支持接收溢出检测。
- 支持 DMA 错误恢复。
- 解析任务与 BDMA 完全解耦。

### 完整框架

```
#define LPUART_RX_SIZE 256U

static uint8_t lpuart_rx_buf[LPUART_RX_SIZE]
    __attribute__((section(".lowpower_sram"),
                   aligned(4)));

typedef struct {
    uint32_t total_written;
    uint32_t total_read;
    uint32_t overflow_count;
    uint32_t error_count;
} lpuart_rx_state_t;

static volatile lpuart_rx_state_t g_lpuart_rx;

static size_t lpuart_get_write_pos(void)
{
    uint32_t remaining =
        bdma_get_remaining(BDMA_CHANNEL_0);

    size_t pos =
        LPUART_RX_SIZE - remaining;

    return pos % LPUART_RX_SIZE;
}

void BDMA_Channel0_IRQHandler(void)
{
    uint32_t flags =
        bdma_get_flags(BDMA_CHANNEL_0);

    if ((flags & BDMA_FLAG_TRANSFER_ERROR) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_0,
            BDMA_FLAG_TRANSFER_ERROR);

        bdma_disable_channel(BDMA_CHANNEL_0);
        lpuart_disable_dma_rx(LPUART1);

        g_lpuart_rx.error_count++;

        lpuart_bdma_recovery_notify_from_isr();
        return;
    }

    if ((flags & (BDMA_FLAG_HALF_TRANSFER |
                  BDMA_FLAG_TRANSFER_COMPLETE)) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_0,
            BDMA_FLAG_HALF_TRANSFER |
            BDMA_FLAG_TRANSFER_COMPLETE);

        lpuart_rx_data_notify_from_isr();
    }
}

void LPUART1_IRQHandler(void)
{
    if (lpuart_idle_flag(LPUART1)) {
        lpuart_clear_idle_flag(LPUART1);

        lpuart_rx_data_notify_from_isr();
    }
}

void lpuart_rx_task(void *arg)
{
    uint8_t temp[64];

    for (;;) {
        lpuart_wait_rx_event(portMAX_DELAY);

        size_t write_pos =
            lpuart_get_write_pos();

        size_t available;

        if (write_pos >=
            (g_lpuart_rx.total_read %
             LPUART_RX_SIZE)) {
            available =
                write_pos -
                (g_lpuart_rx.total_read %
                 LPUART_RX_SIZE);
        } else {
            available =
                LPUART_RX_SIZE -
                (g_lpuart_rx.total_read %
                 LPUART_RX_SIZE) +
                write_pos;
        }

        if (available > LPUART_RX_SIZE) {
            g_lpuart_rx.overflow_count++;

            g_lpuart_rx.total_read =
                g_lpuart_rx.total_written -
                LPUART_RX_SIZE;

            available = LPUART_RX_SIZE;
        }

        while (available > 0U) {
            size_t read_pos =
                g_lpuart_rx.total_read %
                LPUART_RX_SIZE;

            size_t contiguous =
                LPUART_RX_SIZE - read_pos;

            size_t count = available;

            if (count > contiguous) {
                count = contiguous;
            }

            if (count > sizeof(temp)) {
                count = sizeof(temp);
            }

            dma_cache_invalidate(&lpuart_rx_buf[read_pos],
                                 count);
            cpu_dmb();

            memcpy(temp,
                   &lpuart_rx_buf[read_pos],
                   count);

            protocol_feed(temp, count);

            g_lpuart_rx.total_read += count;
            available -= count;
        }
    }
}
```

> 对严格工业实现，应在 ISR 或任务中用一致的单调写入计数器更新 `total_written`，不能只依赖取模索引推导长期运行状态。

---

## 10.2 BDMA + LPTIM + ADC + Stop 模式

### 总体架构

```
LPTIM 周期事件
      |
      v
ADC 采样
      |
      v
BDMA 写入低功耗 SRAM
      |
      v
达到块长度
      |
      v
BDMA 中断唤醒 CPU
      |
      v
处理一批采样数据
      |
      v
再次进入 Stop 模式
```

### 适合场景

- 电池供电传感器。
- 周期温度采样。
- 振动监测的低频预采样。
- 远程仪表。
- 环境监测节点。

### 核心设计要点

- 由定时器硬件触发采样，避免软件定时抖动。
- BDMA 负责搬运。
- CPU 以块为单位唤醒。
- Buffer 放在低功耗保持 SRAM。
- 块处理完成后重新进入低功耗。
- 使用 ADC 校准和采样时间保证数据质量。

### 简化代码框架

```
#define SENSOR_SAMPLE_COUNT 64U

static uint16_t sensor_samples[SENSOR_SAMPLE_COUNT]
    __attribute__((section(".lowpower_sram"),
                   aligned(4)));

int sensor_bdma_start(void)
{
    bdma_disable_channel(BDMA_CHANNEL_1);
    bdma_clear_all_flags(BDMA_CHANNEL_1);

    bdma_set_request(BDMA_CHANNEL_1,
                     BDMA_REQUEST_ADC4);

    bdma_set_peripheral_address(
        BDMA_CHANNEL_1,
        (uintptr_t)&ADC4->DR);

    bdma_set_memory_address(
        BDMA_CHANNEL_1,
        (uintptr_t)sensor_samples);

    bdma_set_transfer_length(
        BDMA_CHANNEL_1,
        SENSOR_SAMPLE_COUNT);

    bdma_set_peripheral_width(
        BDMA_CHANNEL_1,
        BDMA_WIDTH_16BIT);

    bdma_set_memory_width(
        BDMA_CHANNEL_1,
        BDMA_WIDTH_16BIT);

    bdma_set_peripheral_increment(
        BDMA_CHANNEL_1,
        false);

    bdma_set_memory_increment(
        BDMA_CHANNEL_1,
        true);

    bdma_set_direction(
        BDMA_CHANNEL_1,
        BDMA_PERIPH_TO_MEM);

    bdma_set_circular_mode(
        BDMA_CHANNEL_1,
        false);

    bdma_enable_irq(
        BDMA_CHANNEL_1,
        BDMA_IRQ_TRANSFER_COMPLETE |
        BDMA_IRQ_TRANSFER_ERROR);

    bdma_enable_channel(BDMA_CHANNEL_1);
    adc_enable_dma(ADC4);
    lptim_enable_adc_trigger();

    return 0;
}

void BDMA_Channel1_IRQHandler(void)
{
    uint32_t flags =
        bdma_get_flags(BDMA_CHANNEL_1);

    if ((flags & BDMA_FLAG_TRANSFER_ERROR) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_1,
            BDMA_FLAG_TRANSFER_ERROR);

        sensor_dma_error_count++;
        sensor_sampling_error_notify_from_isr();
        return;
    }

    if ((flags & BDMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        bdma_clear_flags(
            BDMA_CHANNEL_1,
            BDMA_FLAG_TRANSFER_COMPLETE);

        sensor_block_ready_notify_from_isr();
    }
}
```

---

## 10.3 BDMA + 普通 DMA + MDMA 的分层协同

在复杂系统中，可以采用三级分工：

```
低速或低功耗外设
        |
        v
      BDMA
        |
        v
低功耗 SRAM
        |
        v
普通 DMA / MDMA
        |
        v
高速处理 SRAM / 外部 SDRAM
```

例如：

```
LPUART -> BDMA -> SRAM4
                |
                v
               MDMA
                |
                v
           AXI SRAM
                |
                v
          协议栈任务
```

适用于：

- 低功耗唤醒后批量转移数据。
- 低功耗域与高性能域之间的数据交换。
- BDMA 只负责低速外设接收。
- MDMA 负责唤醒后的大块数据整理。

需要重点管理：

- 两个 DMA 控制器之间的 Buffer Ownership。
- SRAM 电源域和时钟域。
- 低功耗唤醒后的 Cache 状态。
- 数据块版本号和有效长度。
- 错误恢复顺序。

---

## 11. 工业级实际案例分析

## 11.1 案例一：电池供电仪表的低功耗 UART 接收

### 需求

- LPUART 波特率：9600。
- 系统绝大多数时间处于 Stop 模式。
- 接收到完整命令后唤醒 CPU。
- 命令长度：4～128 Byte。
- 不允许逐字节唤醒。
- 必须检测帧超时和 CRC 错误。

### 架构

```
LPUART RX
    |
    v
BDMA Circular Buffer
    |
    v
IDLE / 超时事件
    |
    v
唤醒 CPU
    |
    v
协议解析
    |
    +--> CRC 校验
    +--> 地址过滤
    +--> 命令执行
    +--> 响应发送
```

### 关键设计

1. 使用 BDMA 保持数据接收。
2. 使用 IDLE 或定时器判断一帧结束。
3. Buffer 放在 SRAM Retention 区。
4. 唤醒后先恢复时钟，再读取 BDMA 状态。
5. 解析任务不直接操作 DMA 寄存器。
6. 响应发送完成必须等待 UART TC。

### 功耗收益

假设一帧 64 Byte：

```
逐字节唤醒：64 次 CPU 唤醒
BDMA + IDLE：通常 1～2 次 CPU 唤醒
```

对于低速电池设备，这种架构通常比单纯减少 ISR 指令更能降低平均功耗。

---

## 11.2 案例二：远程环境传感器周期采样

### 需求

- 每 1 秒采样一次。
- 每次采集 32 个 ADC 样本。
- 采样期间 CPU 保持睡眠。
- 采样完成后唤醒 CPU 计算均值和异常值。
- 系统工作电压变化较大。
- 需要记录 ADC、BDMA 和唤醒错误。

### 架构

```
RTC / LPTIM
     |
     v
ADC Trigger
     |
     v
ADC
     |
     v
BDMA -> Retention SRAM
     |
     v
TC Interrupt
     |
     v
CPU Wakeup
     |
     v
均值 / 方差 / 越界判断
     |
     v
回到低功耗
```

### 设计要点

- ADC 触发源必须是硬件定时器。
- BDMA Buffer 采用 16 bit 宽度。
- 传输长度设置为 32 个元素，而不是 64 Byte。
- 唤醒后执行 Cache Invalidate，若平台启用 Cache。
- 处理完成后清除旧状态，再启动下一周期。
- 对 ADC 过采样结果执行范围和 CRC 检查。

---

## 11.3 案例三：工业传感器的低速 SPI 批量读取

### 需求

- SPI 传感器工作频率：4 MHz。
- 每次读取 24 Byte。
- 读取周期：10 ms。
- CPU 同时运行控制任务。
- 传感器有 DRDY 引脚。
- 读取完成后需要校验数据帧。

### 架构

```
Sensor DRDY
    |
    v
EXTI / Timer
    |
    v
SPI TX/RX
    |
    +--> BDMA TX
    +--> BDMA RX
            |
            v
       RX Buffer
            |
            v
       完成中断
            |
            v
       RTOS 数据任务
```

### 设计要点

- SPI 全双工通常需要 TX 和 RX 两路 DMA。
- 发送命令 Buffer 长度必须与接收长度一致，或使用固定填充值。
- NSS / CS 必须覆盖完整事务。
- BDMA RX 完成不一定代表 SPI BSY 已清零。
- 释放 CS 前要等待 SPI 最后一个时钟完成。
- 如果 BDMA 没有 FIFO，要特别关注 SPI 数据寄存器与请求节奏。

---

## 12. 高频问题深度答疑

## 问题一：BDMA 与 LPDMA 有什么区别？

不同厂商定义并不统一。

一般而言：

- **BDMA** 更强调基础、简单、低资源的数据搬运。
- **LPDMA** 更强调在 Stop、低功耗域、低频时钟环境中保持运行。
- LPDMA 可能支持：
    - 链式请求；
    - 更灵活的触发；
    - 更低功耗时钟；
    - 更强的低功耗保持能力。

不能仅根据名称判断，应该比较：

```
低功耗模式支持
可访问内存
外设请求源
传输宽度
计数器宽度
链式能力
地址递增能力
唤醒能力
```

---

## 问题二：BDMA 为什么不适合大块高速传输？

常见原因：

- 没有 FIFO。
- Burst 能力弱。
- 通道数少。
- 总线访问宽度有限。
- 低功耗域总线带宽低。
- 传输计数器位宽较小。
- 外设请求响应能力有限。

对于高速、大块数据，应优先评估：

- 普通 DMA；
- MDMA；
- GPDMA；
- DMA2D；
- 专用外设 DMA。

---

## 问题三：BDMA 可以在 Stop 模式下工作吗？

不能直接假设可以。

需要逐项确认：

1. BDMA 时钟是否在 Stop 模式保持。
2. 外设时钟是否在 Stop 模式保持。
3. 请求路由器是否工作。
4. Buffer 所在 SRAM 是否保持。
5. BDMA 所在电源域是否供电。
6. 外设是否支持 Stop 模式请求。
7. 传输完成中断是否可作为唤醒源。
8. 唤醒后是否需要重新初始化时钟和 BDMA。

必须通过实际电流和数据测试验证，而不是只看初始化代码执行成功。

---

## 问题四：BDMA 环形模式下如何确定接收了多少数据？

常见方法：

```
已配置长度 - 剩余传输数
```

公式：

WritePos=(BufferSize−NDTR)  BufferSizeWritePos=(BufferSize−NDTR)modBufferSize

但该值只是当前环形位置，不代表累计接收量。

长期运行应维护：

```
软件累计写入计数
软件累计读取计数
溢出计数
```

并周期性处理 `NDTR` 环绕。

---

## 问题五：BDMA 是否需要 Cache Maintenance？

取决于：

- CPU 是否有 Cache；
- Buffer 是否位于 Cacheable 区域；
- BDMA 是否直接访问该区域；
- 平台是否具备硬件 Cache Coherency。

通用规则：

```
BDMA 读取 CPU 写入的数据：
    Clean

CPU 读取 BDMA 写入的数据：
    Invalidate

BDMA 使用的描述符：
    Clean
```

对于低功耗系统，还要在进入低功耗前处理脏 Cache Line。

---

## 问题六：为什么 BDMA 传输完成了，但 SPI 仍然不能释放 CS？

SPI 数据路径通常为：

```
BDMA 写 SPI 数据寄存器
        |
        v
SPI FIFO / 数据寄存器
        |
        v
SPI 移位寄存器
        |
        v
SCK / MOSI 引脚
```

BDMA TC 只表示最后一个数据已经交给 SPI，SPI 可能仍在输出最后几个时钟。

正确流程：

```
BDMA TC
   |
   v
等待 SPI TX FIFO 空
   |
   v
等待 SPI BSY 清零
   |
   v
释放 CS
```

---

## 问题七：BDMA 的低功耗收益是否总是存在？

不一定。

如果数据量很小、CPU 本来就会保持运行，BDMA 可能引入：

- 通道配置开销；
- 中断开销；
- 时钟保持开销；
- 额外 SRAM 保持电流；
- DMA 控制器自身功耗。

BDMA 真正有价值的场景是：

```
CPU 可以长期睡眠
+
数据可以批量搬运
+
外设能在低功耗模式继续工作
```

---

## 13. 课程核心总结

### 13.1 核心要点

- **BDMA 是基础型、资源精简、低功耗友好的 DMA 控制器。**
- **BDMA 主要解决简单的外设与内存之间的数据搬运问题。**
- BDMA 典型适用场景包括：
    - LPUART；
    - 低速 UART；
    - 低功耗 ADC；
    - 低速 SPI 传感器；
    - DAC 周期输出；
    - Stop 模式下的数据采集。
- BDMA 的核心配置包括：
    - 请求源；
    - 外设地址；
    - 内存地址；
    - 数据宽度；
    - 传输数量；
    - 传输方向；
    - 地址递增；
    - 循环模式；
    - 中断使能。
- **BDMA 的传输计数通常是数据元素数量，不一定是字节数。**
- 低功耗场景的关键不只是 DMA 本身，还包括：
    - BDMA 时钟保持；
    - 外设时钟保持；
    - 请求源可用；
    - SRAM 电源保持；
    - 唤醒中断配置；
    - 唤醒后的时钟恢复。
- **BDMA Buffer 必须位于 BDMA 可访问的内存区域。**
- **CPU 不能访问 BDMA 正在写入的 Buffer，BDMA 也不能覆盖 CPU 正在处理的数据。**
- 环形 BDMA 必须配套：
    - 读指针；
    - 写指针；
    - 累计计数；
    - 溢出检测；
    - 错误计数。
- `volatile` 不能解决 DMA Cache 一致性问题。
- **BDMA TC 只表示 BDMA 搬运完成，不一定表示 UART、SPI 等外设已经完成物理发送。**
- BDMA 适合“简单、连续、低功耗”的数据流，不适合：
    - 多段非连续搬运；
    - 复杂二维数据；
    - 高速大块内存复制；
    - 链式描述符；
    - 高级数据重排。
- BDMA 与其他 DMA 的典型分工是：

```
BDMA：
    低功耗域、低速外设、基础数据搬运

普通 DMA：
    高速外设实时数据搬运

MDMA：
    大块数据整理、二维搬运、链式传输
```

### 13.2 BDMA 的系统定位

```
低功耗外设
    |
    v
BDMA
    |
    v
低功耗 SRAM
    |
    +--> CPU 唤醒后处理
    |
    +--> MDMA 二次搬运
    |
    +--> 通信协议任务
```

### 13.3 BDMA 的性能排序

从硬件能力和数据组织能力来看：

```
BDMA
    <
普通 DMA
    <
MDMA / GPDMA
    <
DMA2D / 专用外设加速器
```

从低功耗适应性来看，通常是：

```
普通 CPU 访问
    <
外设中断
    <
普通 DMA
    <
BDMA / LPDMA
```

但实际结果取决于芯片的：

- 低功耗时钟架构；
- SRAM 电源域；
- DMA 总线连接；
- 外设请求路由；
- Cache 和 MPU 配置。

### 13.4 通用选型结论

|需求|推荐方案|
|---|---|
|低速、低频、单字节控制数据|中断|
|LPUART 连续接收|BDMA + 环形 Buffer|
|低功耗 ADC 周期采样|BDMA + LPTIM / RTC|
|高速 UART、SPI、ADC|普通 DMA|
|大块内存复制|MDMA / 普通 DMA|
|二维图像搬运|MDMA Block Repeat / DMA2D|
|多段内存聚合|MDMA Linked List|
|Stop 模式持续数据采集|BDMA / LPDMA|
|数据量极小且 CPU 已经唤醒|CPU 直接访问|
|需要低唤醒次数|BDMA 块传输|
|复杂数据重排|普通 DMA + MDMA 或专用硬件|

### 13.5 必须记住的工程判断

采用 BDMA 前，必须回答：

```
1. 目标外设是否支持 BDMA 请求？
2. BDMA 通道和请求源是否正确映射？
3. BDMA 在目标低功耗模式下是否仍然运行？
4. BDMA 所属时钟域和电源域是否保持？
5. Buffer 所在 SRAM 是否由 BDMA 可访问？
6. Buffer 是否在低功耗模式下保持内容？
7. 传输计数是字节数还是元素数？
8. 源地址和目标地址是否正确配置递增？
9. 是否需要环形模式？
10. 是否有 Buffer 溢出策略？
11. 是否需要 Cache Clean / Invalidate？
12. BDMA TC 后是否还需要等待外设 TC 或 BSY 清零？
13. 是否存在更适合的普通 DMA、LPDMA 或 MDMA？
14. 错误后是否能够安全停止、清标志并重新初始化？
```

---

## 14. 快速参考速查表

## 14.1 BDMA 场景选型表

|场景|推荐配置|关键注意事项|
|---|---|---|
|LPUART RX|外设到内存、循环、8 bit|外设地址固定，内存递增|
|LPUART TX|内存到外设、单次、8 bit|BDMA TC 后等待 UART TC|
|低速 UART 变长帧|BDMA 环形 + IDLE|维护软件读写指针|
|低功耗 ADC|外设到内存、单次或循环、16 bit|计数通常按样本数配置|
|周期 ADC 采样|LPTIM 触发 + BDMA|确认 Stop 模式时钟保持|
|低速 SPI RX|BDMA 外设到内存|RX 完成后等待 SPI BSY 清零|
|低速 SPI TX|BDMA 内存到外设|CS 不能仅依据 BDMA TC 释放|
|DAC 波形输出|内存到外设、循环|由定时器触发更稳定|
|SRAM 到 SRAM|视平台支持|通常普通 DMA / MDMA 更合适|
|多段内存搬运|不推荐 BDMA|使用 MDMA Linked List|
|二维内存搬运|不推荐 BDMA|使用 MDMA 或 DMA2D|
|大块高速传输|不推荐 BDMA|使用普通 DMA、MDMA 或 GPDMA|

## 14.2 地址递增配置表

|应用|外设地址|内存地址|
|---|---|---|
|UART RX|固定|递增|
|UART TX|固定|递增|
|ADC RX|固定|递增|
|SPI RX|固定|递增|
|SPI TX|固定|递增|
|DAC TX|固定|递增|
|内存到内存|源递增|目标递增|
|固定寄存器写入|固定|递增|
|固定内存地址写外设|视需求|固定|

## 14.3 传输长度换算表

假设硬件计数器的单位是数据元素：

|数据类型|Buffer 大小|正确传输计数|
|---|---|---|
|`uint8_t buffer[128]`|128 Byte|128|
|`uint16_t buffer[128]`|256 Byte|128|
|`uint32_t buffer[128]`|512 Byte|128|
|`uint16_t buffer[256]`|512 Byte|256|

通用公式：

TransferCount=TotalBytesDataWidthBytesTransferCount=DataWidthBytesTotalBytes​

代码封装：

```
static bool bdma_validate_length(size_t bytes,
                                 bdma_width_t width)
{
    if (width == 0U) {
        return false;
    }

    return (bytes % (size_t)width) == 0U;
}

static uint32_t bdma_bytes_to_count(size_t bytes,
                                     bdma_width_t width)
{
    return (uint32_t)(bytes / (size_t)width);
}
```

## 14.4 Cache 操作速查表

|操作|CPU 侧处理|
|---|---|
|BDMA 读取 CPU 修改后的 TX Buffer|Clean|
|CPU 读取 BDMA 写入的 RX Buffer|Invalidate|
|进入低功耗前，BDMA 将读取 Buffer|Clean + `DSB`|
|唤醒后读取 BDMA 写入 Buffer|Invalidate + `DMB`|
|BDMA 描述符被 CPU 修改|Clean 描述符|
|Buffer 位于 Non-cacheable SRAM|通常不需要 Cache 操作|
|Buffer 跨 Cache Line|按 Cache Line 对齐处理|

## 14.5 低功耗检查表

```
[ ] BDMA 时钟在低功耗模式保持
[ ] 外设时钟在低功耗模式保持
[ ] BDMA 请求源在低功耗模式可用
[ ] 目标 SRAM 电源域保持
[ ] Buffer 放置位置正确
[ ] BDMA 中断可唤醒 CPU
[ ] 低功耗进入前已清除旧 DMA 标志
[ ] 低功耗退出后时钟恢复顺序正确
[ ] 已读取 NDTR 和状态寄存器
[ ] 已处理 DMA 错误和外设溢出
[ ] 已验证真实电流
[ ] 已验证真实数据完整性
```

## 14.6 BDMA 错误排查表

|现象|优先检查项|
|---|---|
|`CNDTR` 不变化|时钟、通道使能、请求源映射|
|没有完成中断|IRQ 使能、NVIC、标志清除|
|传输数量不正确|字节数与元素数混淆|
|ADC 数据异常|数据宽度、外设寄存器地址、采样触发|
|UART 数据丢失|Buffer 太小、任务处理不及时、IDLE 配置|
|Stop 模式丢数据|时钟保持、SRAM 保持、请求源支持|
|目标数据是旧数据|Cache Invalidate|
|发送数据是旧内容|Cache Clean|
|SPI 最后字节错误|BDMA TC 后未等待 SPI BSY 清零|
|重新启动失败|通道未关闭、标志未清除、外设请求仍开启|
|只在某些芯片上失败|内存区域可达性或低功耗域不同|
|长时间运行后失步|环形 Buffer 溢出或累计计数错误|

---

## 15. 学习效果自检

## 15.1 架构理解

- [ ]  能解释 BDMA 与普通 DMA 的主要区别。
- [ ]  能解释 BDMA 与 MDMA 的系统定位差异。
- [ ]  能画出 `LPUART -> BDMA -> SRAM -> CPU` 数据流。
- [ ]  能说明 BDMA 为什么适合低功耗场景。
- [ ]  能说明 BDMA 为什么不适合复杂二维数据搬运。

## 15.2 硬件配置

- [ ]  能正确配置 BDMA 请求源。
- [ ]  能配置外设地址和内存地址。
- [ ]  能配置外设地址固定、内存地址递增。
- [ ]  能根据数据宽度计算传输元素数。
- [ ]  能配置单次和循环模式。
- [ ]  能配置传输完成和传输错误中断。
- [ ]  能正确读取并清除 BDMA 状态标志。

## 15.3 低功耗能力

- [ ]  能确认 BDMA 是否属于可保持运行的时钟域。
- [ ]  能确认外设在 Stop 模式中是否继续产生 DMA 请求。
- [ ]  能确认目标 SRAM 是否保持。
- [ ]  能将 Buffer 放入指定低功耗内存段。
- [ ]  能配置 BDMA 完成中断作为唤醒源。
- [ ]  能设计低功耗进入和退出流程。
- [ ]  能使用功耗仪验证实际电流。

## 15.4 环形 Buffer

- [ ]  能根据 `NDTR` 计算当前写位置。
- [ ]  能维护软件读指针。
- [ ]  能处理 Buffer 跨尾部读取。
- [ ]  能识别读写指针追赶。
- [ ]  能统计溢出次数。
- [ ]  能处理 DMA 环绕。
- [ ]  能结合 UART IDLE 识别变长帧。

## 15.5 Cache 和内存

- [ ]  能判断 BDMA Buffer 是否位于 Cacheable 区域。
- [ ]  能在 BDMA 发送前执行 Clean。
- [ ]  能在 CPU 读取 BDMA 接收数据前执行 Invalidate。
- [ ]  能理解 `volatile` 不等于 Cache 一致性。
- [ ]  能确认 BDMA 对目标内存的可访问性。
- [ ]  能处理低功耗前后的 Cache 生命周期。

## 15.6 故障恢复

- [ ]  能处理 BDMA 传输错误。
- [ ]  能处理 UART ORE、SPI FIFO 错误和 ADC 溢出。
- [ ]  能设置传输超时。
- [ ]  能安全停止 BDMA 通道。
- [ ]  能清除旧状态标志。
- [ ]  能重新初始化请求源和地址。
- [ ]  能记录错误次数和故障上下文。

---

## 16. 实践与进阶路径

## 16.1 第一阶段：BDMA 单次传输验证

### 实践任务

实现一个基础传输：

```
UART / SPI 外设
       |
       v
BDMA
       |
       v
SRAM Buffer
```

建议先使用 UART TX 或 ADC RX。

### 测试内容

1. 配置 8 bit 传输。
2. 配置 16 bit 传输。
3. 验证单次传输。
4. 验证传输完成中断。
5. 验证传输错误中断。
6. 检查 `NDTR` 或 `CNDTR` 变化。
7. 使用固定模式校验数据：

```
static void fill_test_pattern(uint8_t *buf,
                              size_t len)
{
    for (size_t i = 0U; i < len; ++i) {
        buf[i] = (uint8_t)(i ^ 0x5AU);
    }
}

static bool verify_test_pattern(const uint8_t *buf,
                                size_t len)
{
    for (size_t i = 0U; i < len; ++i) {
        if (buf[i] != (uint8_t)(i ^ 0x5AU)) {
            return false;
        }
    }

    return true;
}
```

### 验收标准

```
1. 10000 次传输无错误。
2. 错误标志能够被正确捕获。
3. 通道停止后能够重新启动。
4. 传输长度与实际数据长度一致。
5. 传输完成中断只触发一次。
```

---

## 16.2 第二阶段：BDMA 环形接收

### 实践任务

实现：

```
LPUART RX
    |
    v
BDMA Circular Buffer
    |
    v
RTOS 接收任务
```

要求：

- Buffer 大小为 128 或 256 Byte。
- 使用 `NDTR` 获取写位置。
- 支持跨 Buffer 尾部读取。
- 记录累计读取量。
- 检测 Buffer 溢出。
- 输出接收统计信息。

### 推荐测试

```
1. 连续发送固定长度数据。
2. 连续发送变长数据。
3. 发送速率高于任务处理速度。
4. 人为延迟接收任务。
5. 进入和退出 Sleep 模式。
6. 人为触发 UART ORE。
7. 统计丢包、溢出和 CRC 错误。
```

### 关键指标

```
生产速率
消费速率
Buffer 使用峰值
溢出次数
事件到任务唤醒延迟
协议解析延迟
```

必须满足：

Rconsume≥RproduceRconsume​≥Rproduce​

如果短时间内无法满足，则需要：

- 增大 Buffer；
- 降低数据速率；
- 提高接收任务优先级；
- 减少任务阻塞；
- 改进协议分帧；
- 增加硬件 FIFO。

---

## 16.3 第三阶段：BDMA + UART IDLE

### 实践任务

实现变长串口协议接收：

```
帧格式：
+--------+------+----------+-----+
| Header | Len  | Payload  | CRC |
+--------+------+----------+-----+
```

要求：

- BDMA 采用环形模式。
- UART IDLE 作为帧结束提示。
- 协议任务读取当前写位置。
- 支持帧长度异常。
- 支持 CRC 错误。
- 支持帧超时。
- 支持帧头重同步。

### 验收场景

```
1. 正常完整帧
2. 两帧连续到达
3. 帧间无空闲间隔
4. 帧被截断
5. 长度字段错误
6. CRC 错误
7. 帧头中出现随机噪声
8. Buffer 即将溢出
```

---

## 16.4 第四阶段：BDMA + LPTIM + ADC 低功耗采样

### 实践任务

实现：

```
LPTIM 周期触发
       |
       v
ADC 采样
       |
       v
BDMA 写入 Retention SRAM
       |
       v
完成中断唤醒 CPU
       |
       v
计算均值、最大值、最小值
```

### 需要测量

- Stop 模式电流。
- 采样周期误差。
- ADC 采样完成到 CPU 唤醒的延迟。
- BDMA 传输完成到任务运行的延迟。
- 每周期 CPU 活跃时间。
- 平均功耗。
- 数据完整性。

平均功耗可按下式估算：

Iavg=Isleep(1−D)+IactiveDIavg​=Isleep​(1−D)+Iactive​D

其中：

- `D`：CPU 活跃占空比；
- `I_sleep`：低功耗电流；
- `I_active`：CPU 活跃电流。

### 验收标准

```
1. 连续采样 24 小时无 Buffer 错误。
2. 进入 Stop 后数据仍然完整。
3. 唤醒后时钟恢复正确。
4. 平均功耗达到设计目标。
5. 采样周期误差满足系统要求。
```

---

## 16.5 第五阶段：BDMA 双通道 SPI 传输

### 实践任务

实现 SPI 传感器读写：

```
SPI TX <- BDMA TX
SPI RX -> BDMA RX
```

要求：

- TX 和 RX 分别使用一个 BDMA 通道。
- 支持固定命令和 Dummy Byte。
- 使用 DRDY 触发读取。
- 传输完成后等待 SPI BSY 清零。
- 校验接收帧 CRC。
- 支持 SPI 超时恢复。

### 状态机

```
typedef enum {
    SPI_BDMA_IDLE = 0,
    SPI_BDMA_WAIT_DRDY,
    SPI_BDMA_RUNNING,
    SPI_BDMA_DMA_DONE,
    SPI_BDMA_WAIT_SPI_IDLE,
    SPI_BDMA_COMPLETE,
    SPI_BDMA_ERROR,
} spi_bdma_state_t;
```

推荐流程：

```
等待 DRDY
   |
   v
拉低 CS
   |
   v
配置 TX / RX BDMA
   |
   v
启动 SPI
   |
   v
等待 BDMA TC
   |
   v
等待 SPI BSY 清零
   |
   v
释放 CS
   |
   v
校验数据
   |
   v
提交结果
```

---

## 16.6 第六阶段：低功耗模式故障注入

### 实践任务

针对 BDMA 低功耗架构，主动注入以下故障：

```
1. 关闭 BDMA 时钟
2. 关闭外设时钟
3. 将 Buffer 放到非保持 SRAM
4. 配置错误请求源
5. 设置非法长度
6. 设置非对齐地址
7. 提前退出 Stop
8. 强制触发 UART ORE
9. 让接收任务长时间不运行
10. 在 Cache 未同步时读取 Buffer
```

### 需要观察

- 是否能够检测故障。
- 是否能够记录错误上下文。
- 是否能够恢复通道。
- 是否会产生中断风暴。
- 是否会导致系统死锁。
- 是否会丢失后续数据。
- 是否能够进入安全状态。

---

## 16.7 第七阶段：工业级 BDMA 驱动封装

建议将 BDMA 驱动拆分为以下模块：

```
bdma_core.c
bdma_core.h
    - 通道初始化
    - 请求源配置
    - 单次传输
    - 循环传输
    - 状态查询
    - 超时
    - 取消
    - 错误恢复

bdma_resource.c
bdma_resource.h
    - 通道资源管理
    - 请求源分配
    - 所有者管理
    - 优先级管理

bdma_lowpower.c
bdma_lowpower.h
    - 低功耗前检查
    - 时钟保持检查
    - SRAM 保持检查
    - 唤醒后恢复

bdma_cache.c
bdma_cache.h
    - Source Clean
    - Destination Invalidate
    - Cache Line 对齐

bdma_trace.c
bdma_trace.h
    - 传输计数
    - 错误计数
    - 溢出统计
    - 唤醒次数
    - 平均功耗关联数据

bdma_test.c
bdma_test.h
    - 边界测试
    - 压力测试
    - 故障注入
    - 低功耗测试
```

### 推荐统一接口

```
typedef uint32_t bdma_handle_t;

typedef struct {
    uintptr_t peripheral_address;
    uintptr_t memory_address;
    size_t length_bytes;
    bdma_direction_t direction;
    bdma_width_t peripheral_width;
    bdma_width_t memory_width;
    bool peripheral_increment;
    bool memory_increment;
    bool circular;
    bool half_transfer_irq;
    bool complete_irq;
    bool error_irq;
} bdma_request_t;

int bdma_init(void);

int bdma_submit(const bdma_request_t *request,
                bdma_handle_t *handle);

int bdma_start(bdma_handle_t handle);

int bdma_wait(bdma_handle_t handle,
              uint32_t timeout_ms);

int bdma_cancel(bdma_handle_t handle);

int bdma_get_remaining(bdma_handle_t handle,
                       size_t *remaining);

int bdma_get_status(bdma_handle_t handle,
                    uint32_t *status);

int bdma_recover(bdma_handle_t handle);
```

### 驱动层必须封装的细节

上层业务不应直接操作：

- `CNDTR`；
- `CPAR`；
- `CMAR`；
- DMA 状态寄存器；
- 中断清除寄存器；
- 低功耗时钟寄存器。

上层只应看到：

```
提交传输
等待事件
读取数据
处理错误
取消传输
```

---

## 16.8 进阶学习方向

完成 BDMA 后，建议继续学习：

1. **LPDMA**
    - 低功耗模式下的更强 DMA；
    - 链式请求；
    - 低功耗触发；
    - 自主运行。
2. **GPDMA**
    - Linked List；
    - Trigger；
    - Repeat Block；
    - 数据重排；
    - 复杂请求调度。
3. **MDMA**
    - 大块内存搬运；
    - 二维数据；
    - DMA 级联；
    - 链式描述符。
4. **DMA 与 Cache Coherency**
    - Cache Line；
    - MPU；
    - 内存屏障；
    - Non-cacheable 区域。
5. **低功耗系统架构**
    - Stop / Standby / Shutdown；
    - SRAM Retention；
    - Wakeup Source；
    - 时钟恢复。
6. **总线和功耗分析**
    - DMA 总线带宽；
    - 电源域；
    - 时钟门控；
    - 唤醒抖动。
7. **DMA 安全**
    - Buffer 越界；
    - 请求源隔离；
    - 外设访问控制；
    - DMA 描述符保护。
8. **实时数据流架构**
    - Ring Buffer；
    - Ping-Pong Buffer；
    - Zero-Copy；
    - Lock-Free SPSC Queue。
9. **工业级验证**
    - 长时间压力测试；
    - 低电压测试；
    - 高低温测试；
    - 时钟切换测试；
    - 低功耗电流测试；
    - 故障注入和恢复测试。

### 本课最终能力要求

面对实际项目时，应能够给出类似以下的设计结论：

```
LPUART 接收采用 BDMA 环形模式；
Buffer 放入低功耗保持 SRAM；
使用 IDLE 或块完成事件唤醒协议任务；
任务侧根据 NDTR 计算 DMA 写位置；
维护单调读写计数和溢出统计；
进入 Stop 前确认 BDMA、LPUART、SRAM 时钟及电源域保持；
唤醒后恢复时钟并检查 BDMA 状态；
接收数据读取前执行必要的 Cache Invalidate；
若需要复杂数据重排，再交由 MDMA 处理；
若数据速率和总线带宽超过 BDMA 能力，则切换到普通 DMA 或 GPDMA。
```

**BDMA 的核心价值不是提供最高吞吐量，而是在资源有限、功耗敏感和数据流结构简单的条件下，让外设能够以较低 CPU 介入成本持续运行。**