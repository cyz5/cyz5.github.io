
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 DMA 控制器在总线、存储器、外设之间的角色定位。
- 理解 DMA 请求、仲裁、突发传输、地址递增、数据宽度、循环模式、双缓冲模式的底层行为。
- 理解 DMA 与 UART、SPI、I²C、ADC、DAC、定时器、以太网 MAC 等外设的协同机制。
- 理解 DMA 传输完成、中断、半传输、错误、总线冲突和缓存一致性的关系。

### 掌握

- 掌握 DMA 通道 / Stream / Request Mapping 的配置方法。
- 掌握内存到外设、外设到内存、内存到内存三类传输模式。
- 掌握环形 DMA、Ping-Pong 双缓冲、分散聚集、链式 DMA 的设计。
- 掌握 DMA 与 RTOS 任务、ISR、Ring Buffer、Cache 管理的组合方式。
- 掌握 DMA 传输长度、带宽、CPU 占用率和中断频率的量化计算。

### 精通

- 能分析 DMA 传输过程中出现的丢包、乱序、重复数据、缓存脏数据和“偶发错误”。
- 能处理 Cortex-M7、Cortex-A 等带 D-Cache 系统中的 DMA 一致性问题。
- 能解决 DMA 与 CPU、LCD、以太网、Flash、SDMMC 等主设备之间的总线竞争。
- 能建立 DMA 传输的超时、错误恢复、状态机和故障注入机制。
- 能根据实时性、吞吐量、内存占用和功耗要求选择合适 DMA 架构。

### 能够设计

- 能设计工业级 UART 高吞吐接收框架。
- 能设计 ADC 连续采样、双缓冲处理和数据流水线。
- 能设计 SPI 显示刷新、摄像头采集、音频采集等 DMA 传输架构。
- 能设计支持 Cache、RTOS、多缓冲、错误恢复和动态负载的 DMA 抽象层。
- 能评估 DMA 方案在目标平台上的最坏延迟、带宽上限和资源消耗。

---

## 2. 前置要求

### 知识要求

- C 语言指针、数组、结构体、`volatile`、内存对齐。
- MCU 总线架构：AHB、AXI、APB、DMA Bus Matrix。
- 中断、NVIC、优先级、临界区。
- UART、SPI、ADC、定时器、I²C 等外设基本工作原理。
- RTOS 任务、队列、信号量、事件组和 ISR 安全 API。
- Cache、MPU、内存屏障和 DMA 一致性基本概念。

### 技能要求

- 能阅读芯片参考手册中的 DMA 章节。
- 能使用逻辑分析仪或示波器测量外设波形。
- 能使用调试器查看 DMA 寄存器和内存。
- 能完成中断级驱动开发。
- 能使用 map 文件、DWT、ETM 或系统定时器进行性能测量。
- 能构建最小化 DMA 验证工程并进行边界测试。

---

## 3. 技术概述

### 3.1 DMA 的定义

DMA，Direct Memory Access，直接存储器访问，是一种允许外设或内存之间在无需 CPU 逐字节搬运的情况下完成数据传输的硬件机制。

典型数据路径为：

```
外设寄存器 <-> DMA 控制器 <-> 系统总线 <-> SRAM / SDRAM / Flash
```

CPU 的职责主要是：

1. 初始化 DMA。
2. 配置源地址、目标地址、传输宽度和传输长度。
3. 启动外设和 DMA。
4. 响应半传输、完成、错误等事件。
5. 处理 DMA 完成后的数据。

CPU 不再参与每个字节或每个采样点的搬运。

### 3.2 DMA 的价值

DMA 主要解决三个工程问题：

|问题|CPU 逐字节处理|DMA 方案|
|---|---|---|
|高速数据搬运|CPU 占用高|CPU 占用显著降低|
|实时采样|ISR 频繁进入|以块为单位处理|
|外设连续传输|容易丢数据|由硬件持续搬运|
|大块内存复制|受 CPU 负载影响|可由 DMA 异步执行|
|低功耗|CPU 必须保持运行|CPU 可睡眠等待完成|

### 3.3 DMA 主流分类

#### 按数据方向分类

1. **Peripheral-to-Memory**
    
    - UART 接收
    - ADC 采样
    - SPI 接收
    - 摄像头采集
2. **Memory-to-Peripheral**
    
    - UART 发送
    - SPI 发送
    - DAC 输出
    - LCD 刷屏
3. **Memory-to-Memory**
    
    - 大块内存复制
    - 图像缓冲搬运
    - 数据清零
    - 数据格式转换前的数据搬运

#### 按传输组织方式分类

- 单次传输
- 循环传输
- 双缓冲传输
- 链式描述符传输
- Scatter-Gather 分散聚集
- 2D / Stride 传输
- 外设流控 DMA
- DMA 控制器流控

#### 按 DMA 触发方式分类

- 外设请求触发
- 软件启动
- 定时器触发
- DMAMUX 路由
- 外设事件触发
- 链式事件触发

---

## 4. 核心特性横向对比

### 4.1 常用 DMA 工作模式对比

|模式|缓冲区变化|适用场景|实时性|软件复杂度|典型风险|
|---|---|---|---|---|---|
|单次模式|传输完成即停止|UART 单帧、SPI 一次交易|高|低|需要重复启动|
|循环模式|自动回到起始地址|ADC、UART 连续接收|高|中|读写指针同步|
|半传输模式|半缓冲触发一次|音频、连续采样|高|中|半缓冲处理不及时|
|双缓冲模式|M0/M1 交替使用|网络、音频、摄像头|很高|中高|缓冲切换竞态|
|链式 DMA|描述符自动串联|复杂数据流、以太网|高|高|描述符一致性|
|Scatter-Gather|多个非连续区域|分段报文、复杂帧|高|高|地址和长度错误|
|内存到内存|两个内存地址|图像、数据搬运|中|低|总线竞争|

### 4.2 外设协同方式对比

|协同方式|请求源|CPU 介入频率|吞吐能力|典型用途|
|---|---|---|---|---|
|CPU 轮询|无 DMA|每个数据单元|低|低速控制|
|中断驱动|外设中断|每字节或每 FIFO|中|中低速通信|
|DMA + 完成中断|DMA 请求|每块数据|高|UART、SPI、ADC|
|DMA + 半传输|DMA 请求|半缓冲|很高|音频、采样|
|DMA + 环形缓冲|外设持续请求|周期性|很高|连续流|
|DMA + 双缓冲|外设持续请求|缓冲切换|很高|摄像头、音频、网络|
|DMA + 链式描述符|请求 / 链表|描述符级|极高|Ethernet、存储控制器|

### 4.3 DMA 传输宽度对比

|数据宽度|总线访问次数|适用场景|注意事项|
|---|---|---|---|
|8 bit|较多|UART、8 位外设|可能降低总线效率|
|16 bit|中等|ADC、SPI、音频|地址和长度需对齐|
|32 bit|少|内存复制、32 位寄存器|不适用于字节寄存器|
|64/128 bit Burst|最少|AXI、SDRAM、显示|对齐和总线支持要求高|

---

## 5. 底层原理与功能特性深度解析

## 5.1 DMA 传输的基本时序

以 UART RX DMA 为例：

```
UART 接收到 1 字节
        |
        v
UART RXNE / FIFO 阈值事件
        |
        v
DMA Request 产生
        |
        v
DMA 仲裁总线
        |
        v
读取 UART_RDR
        |
        v
写入 SRAM[write_index]
        |
        v
地址递增、剩余计数递减
        |
        v
传输完成 / 半传输 / 错误事件
```

DMA 不一定“每个字节都立即搬运”。具体行为取决于：

- 外设 FIFO 深度。
- DMA FIFO 配置。
- Burst 长度。
- 总线仲裁延迟。
- 外设请求保持时间。
- DMA 控制器是否支持请求合并。

### 5.1.1 DMA 的核心寄存器抽象

不同芯片命名不同，但通常包含：

```
typedef struct {
    volatile uint32_t CR;      /* 控制寄存器 */
    volatile uint32_t NDTR;    /* 剩余传输数量 */
    volatile uint32_t PAR;     /* 外设地址 */
    volatile uint32_t M0AR;    /* 内存 0 地址 */
    volatile uint32_t M1AR;    /* 内存 1 地址 */
    volatile uint32_t FCR;     /* FIFO 控制 */
    volatile uint32_t ISR;     /* 状态 */
    volatile uint32_t IFCR;    /* 状态清除 */
} dma_stream_regs_t;
```

核心字段含义：

- `PAR`：外设端地址。
- `M0AR`：内存缓冲区地址。
- `NDTR`：剩余传输数量。
- `DIR`：传输方向。
- `MINC`：内存地址是否递增。
- `PINC`：外设地址是否递增。
- `PSIZE`：外设数据宽度。
- `MSIZE`：内存数据宽度。
- `CIRC`：是否循环。
- `DBM`：是否双缓冲。
- `TCIE`：传输完成中断使能。
- `HTIE`：半传输中断使能。
- `TEIE`：传输错误中断使能。

---

## 5.2 外设地址与内存地址递增

UART 数据寄存器地址固定，因此：

```
外设地址：固定
内存地址：递增
```

配置逻辑：

```
dma_config.periph_addr_inc = false;
dma_config.mem_addr_inc    = true;
```

对于内存复制：

```
源地址：递增
目标地址：递增
```

对于 ADC：

```
ADC 数据寄存器：固定
采样缓冲区：递增
```

错误示例：

```
/* 错误：ADC 数据寄存器地址递增 */
dma_config.periph_addr_inc = true;
```

这会导致第二个采样点开始从错误地址读取，通常表现为：

- DMA 传输错误。
- 读到无效数据。
- 总线 Fault。
- 缓冲区内容异常。

---

## 5.3 DMA 传输宽度与数据对齐

假设 ADC 是 12 位采样，数据寄存器为 16 位有效访问：

```
typedef uint16_t adc_sample_t;

static adc_sample_t adc_buf[1024] __attribute__((aligned(4)));
```

推荐：

```
dma_config.periph_width = DMA_WIDTH_16BIT;
dma_config.mem_width    = DMA_WIDTH_16BIT;
```

如果使用 8 位内存宽度：

```
dma_config.mem_width = DMA_WIDTH_8BIT;
```

则可能出现：

- 高 8 位被截断。
- 数据按字节分裂。
- DMA 剩余计数单位和预期不一致。
- 半传输位置不再对应采样点。

### 传输字节数计算

设：

- 传输元素数量为 `N`
- 内存数据宽度为 `Wm`
- 外设数据宽度为 `Wp`

当 DMA 采用内存宽度作为计数单位时：

Bytesmemory=N×WmBytesmemory​=N×Wm​

例如：

```
N = 1024
Wm = 2 Byte
内存占用 = 2048 Byte
```

---

## 5.4 外设请求与 DMA Request Mapping

现代 MCU 通常通过 DMAMUX 将外设请求映射到 DMA 通道：

```
UART1_RX Request
       |
       v
DMAMUX Channel 3
       |
       v
DMA1 Channel 5
       |
       v
SRAM Buffer
```

需要重点确认：

1. 一个 DMA 通道是否只能绑定一个请求源。
2. 请求源是否可通过 DMAMUX 动态选择。
3. 请求是否具有优先级。
4. 是否存在请求生成器。
5. DMA 通道和外设中断是否使用同一 IRQ。
6. 是否有多个外设共享 DMA 资源。

典型配置：

```
typedef enum {
    DMA_REQ_UART1_RX,
    DMA_REQ_UART1_TX,
    DMA_REQ_ADC1,
    DMA_REQ_SPI1_RX,
    DMA_REQ_SPI1_TX,
} dma_request_t;

typedef struct {
    dma_request_t request;
    uint8_t channel;
    uint8_t priority;
} dma_request_cfg_t;
```

工程上不要只依赖 HAL 默认映射，应在启动阶段记录实际映射关系：

```
log_info("DMA UART1_RX: controller=%u channel=%u request=%u",
         dma_ctrl_id,
         dma_channel_id,
         dma_request_id);
```

---

## 5.5 单次 DMA 传输

适合一次性数据块。

```
typedef enum {
    DMA_OK = 0,
    DMA_ERR_PARAM = -1,
    DMA_ERR_BUSY = -2,
    DMA_ERR_HW = -3,
} dma_status_t;

typedef struct {
    volatile bool busy;
    volatile bool completed;
    volatile bool error;
} dma_state_t;

static dma_state_t g_uart_tx_dma;

dma_status_t uart_dma_send(const uint8_t *data, size_t len)
{
    if (data == NULL || len == 0U || len > UART_TX_MAX_SIZE) {
        return DMA_ERR_PARAM;
    }

    if (g_uart_tx_dma.busy) {
        return DMA_ERR_BUSY;
    }

    dma_disable(UART1_TX_DMA);

    if (dma_clear_flags(UART1_TX_DMA) != 0) {
        return DMA_ERR_HW;
    }

    g_uart_tx_dma.busy = true;
    g_uart_tx_dma.completed = false;
    g_uart_tx_dma.error = false;

    dma_set_peripheral_address(UART1_TX_DMA,
                               (uintptr_t)&UART1->TDR);
    dma_set_memory_address(UART1_TX_DMA,
                           (uintptr_t)data);
    dma_set_length(UART1_TX_DMA, len);
    dma_set_direction(UART1_TX_DMA, DMA_MEM_TO_PERIPH);
    dma_set_memory_increment(UART1_TX_DMA, true);
    dma_set_peripheral_increment(UART1_TX_DMA, false);
    dma_set_memory_width(UART1_TX_DMA, DMA_WIDTH_8BIT);
    dma_set_peripheral_width(UART1_TX_DMA, DMA_WIDTH_8BIT);

    dma_enable_irq(UART1_TX_DMA,
                   DMA_IRQ_TC | DMA_IRQ_TE);

    dma_enable(UART1_TX_DMA);
    uart_enable_dma_tx(UART1);

    return DMA_OK;
}
```

### 传输完成不等于 UART 线路发送完成

这是一个非常重要的工程细节。

DMA TC 表示：

```
DMA 已经将最后一个字节写入 UART TDR
```

但 UART 可能仍在：

```
TDR -> 移位寄存器 -> TX 引脚
```

因此 RS-485 发送完成应等待：

```
DMA TC
+
UART TC（Transmission Complete）
```

错误做法：

```
void uart_dma_tc_isr(void)
{
    rs485_set_tx_enable(false); /* 过早关闭发送器 */
}
```

正确做法：

```
void uart_dma_tc_isr(void)
{
    dma_disable(UART1_TX_DMA);
    uart_enable_irq(UART1, UART_IRQ_TC);
}

void uart_line_complete_isr(void)
{
    uart_disable_irq(UART1, UART_IRQ_TC);
    rs485_set_tx_enable(false);
    tx_complete_notify();
}
```

---

## 5.6 环形 DMA

环形 DMA 适用于连续数据流：

```
DMA 写指针不断前进：

0 -> 1 -> 2 -> ... -> N-1 -> 0 -> 1 -> ...
```

例如 UART 接收 256 字节环形缓冲区：

```
#define UART_RX_DMA_SIZE 256U

static uint8_t uart_rx_dma_buf[UART_RX_DMA_SIZE]
    __attribute__((aligned(32)));

void uart_rx_dma_start(void)
{
    dma_disable(UART1_RX_DMA);

    dma_set_peripheral_address(UART1_RX_DMA,
                               (uintptr_t)&UART1->RDR);
    dma_set_memory_address(UART1_RX_DMA,
                           (uintptr_t)uart_rx_dma_buf);
    dma_set_length(UART1_RX_DMA, UART_RX_DMA_SIZE);

    dma_set_direction(UART1_RX_DMA, DMA_PERIPH_TO_MEM);
    dma_set_peripheral_increment(UART1_RX_DMA, false);
    dma_set_memory_increment(UART1_RX_DMA, true);
    dma_set_circular_mode(UART1_RX_DMA, true);

    dma_enable_irq(UART1_RX_DMA,
                   DMA_IRQ_HT | DMA_IRQ_TC | DMA_IRQ_TE);

    dma_enable(UART1_RX_DMA);
    uart_enable_dma_rx(UART1);
}
```

### 读取 DMA 当前写位置

假设 `NDTR` 表示剩余数量：

```
static size_t uart_rx_dma_get_write_pos(void)
{
    uint32_t remaining = dma_get_remaining(UART1_RX_DMA);

    return (UART_RX_DMA_SIZE - remaining) % UART_RX_DMA_SIZE;
}
```

但必须注意：

- `NDTR` 可能在读取后立即变化。
- 多字节协议不能只依靠一次位置读取。
- CPU 处理速度必须大于数据到达速度。
- 若写指针追上读指针，说明发生溢出。

### Ring Buffer 软件消费模型

```
typedef struct {
    uint8_t *buf;
    size_t size;
    size_t read_pos;
} dma_ring_t;

static dma_ring_t g_uart_ring = {
    .buf = uart_rx_dma_buf,
    .size = UART_RX_DMA_SIZE,
    .read_pos = 0U,
};

static size_t ring_available(const dma_ring_t *r, size_t write_pos)
{
    if (write_pos >= r->read_pos) {
        return write_pos - r->read_pos;
    }

    return r->size - r->read_pos + write_pos;
}

static size_t ring_read(dma_ring_t *r,
                        size_t write_pos,
                        uint8_t *out,
                        size_t max_len)
{
    size_t available = ring_available(r, write_pos);
    size_t count = (available < max_len) ? available : max_len;

    for (size_t i = 0U; i < count; ++i) {
        out[i] = r->buf[r->read_pos];
        r->read_pos = (r->read_pos + 1U) % r->size;
    }

    return count;
}
```

生产环境中建议：

- 使用单调递增计数器，而不是只保存取模位置。
- 使用溢出计数。
- 对 DMA 写指针和软件读指针分别进行原子访问。
- 必要时关闭对应 DMA 中断后读取多个状态寄存器。

---

## 5.7 半传输与双缓冲

### 半传输模式

一个缓冲区分为前后两半：

```
+-------------------+-------------------+
| Buffer Half 0     | Buffer Half 1     |
+-------------------+-------------------+
          HT                    TC
```

- HT：前半区填满。
- TC：后半区填满。
- CPU 处理一半时，DMA 填充另一半。

典型 ADC 采样：

```
#define ADC_BLOCK_SIZE 1024U

static uint16_t adc_buf[ADC_BLOCK_SIZE]
    __attribute__((aligned(32)));

void adc_dma_half_isr(void)
{
    /*
     * DMA 正在填充后半区，前半区已经稳定。
     */
    cache_invalidate(adc_buf,
                     (ADC_BLOCK_SIZE / 2U) * sizeof(adc_buf[0]));

    adc_block_ready_isr(adc_buf,
                        ADC_BLOCK_SIZE / 2U);
}

void adc_dma_full_isr(void)
{
    /*
     * DMA 已经填充后半区，前半区即将被重新使用。
     */
    cache_invalidate(&adc_buf[ADC_BLOCK_SIZE / 2U],
                     (ADC_BLOCK_SIZE / 2U) * sizeof(adc_buf[0]));

    adc_block_ready_isr(&adc_buf[ADC_BLOCK_SIZE / 2U],
                        ADC_BLOCK_SIZE / 2U);
}
```

### 双缓冲模式

```
DMA 当前写入 M0
CPU 处理 M1

切换后：

DMA 当前写入 M1
CPU 处理 M0
```

伪代码：

```
static uint16_t adc_buf0[ADC_BLOCK_SIZE]
    __attribute__((aligned(32)));
static uint16_t adc_buf1[ADC_BLOCK_SIZE]
    __attribute__((aligned(32)));

void adc_dma_start(void)
{
    dma_disable(ADC1_DMA);

    dma_set_memory0_address(ADC1_DMA,
                            (uintptr_t)adc_buf0);
    dma_set_memory1_address(ADC1_DMA,
                            (uintptr_t)adc_buf1);

    dma_set_length(ADC1_DMA, ADC_BLOCK_SIZE);
    dma_set_double_buffer_mode(ADC1_DMA, true);
    dma_set_circular_mode(ADC1_DMA, true);

    dma_enable_irq(ADC1_DMA,
                   DMA_IRQ_TC | DMA_IRQ_TE);

    dma_enable(ADC1_DMA);
    adc_enable_dma(ADC1);
    adc_start(ADC1);
}
```

双缓冲的关键不在于“有两个数组”，而在于：

- DMA 当前目标缓冲区状态可被可靠读取。
- CPU 绝不能处理 DMA 当前正在写入的缓冲区。
- 缓冲区状态切换必须是原子的。
- 处理时间必须小于另一块缓冲区的填充时间。

---

## 5.8 DMA 与 D-Cache 一致性

这是 Cortex-M7、Cortex-A 系统中最常见且最隐蔽的问题之一。

### 5.8.1 DMA 接收场景

DMA 将数据写入 SRAM，但 CPU 可能已经将旧数据缓存到 D-Cache：

```
DMA 写 SRAM: 新数据
CPU 读 Cache: 旧数据
```

此时 CPU 读到旧数据。

解决方式：

```
cache_invalidate_by_addr(rx_buf, len);
```

### 5.8.2 DMA 发送场景

CPU 修改了发送缓冲区，但修改内容还停留在 Cache 中：

```
CPU 写 Cache: 新数据
SRAM: 旧数据
DMA 读 SRAM: 旧数据
```

解决方式：

```
cache_clean_by_addr(tx_buf, len);
```

### 5.8.3 Cache 行对齐

假设 Cache Line 为 32 字节，不能只对任意地址做局部失效而忽略同一 Cache Line 中的其他数据。

```
#define CACHE_LINE_SIZE 32U

static uintptr_t align_down(uintptr_t addr, uintptr_t align)
{
    return addr & ~(align - 1U);
}

static uintptr_t align_up(uintptr_t addr, uintptr_t align)
{
    return (addr + align - 1U) & ~(align - 1U);
}

void dma_cache_clean(void *addr, size_t len)
{
    uintptr_t start = align_down((uintptr_t)addr,
                                 CACHE_LINE_SIZE);
    uintptr_t end = align_up((uintptr_t)addr + len,
                             CACHE_LINE_SIZE);

    cache_clean_by_addr((void *)start, end - start);
    cpu_dmb();
}

void dma_cache_invalidate(void *addr, size_t len)
{
    uintptr_t start = align_down((uintptr_t)addr,
                                 CACHE_LINE_SIZE);
    uintptr_t end = align_up((uintptr_t)addr + len,
                             CACHE_LINE_SIZE);

    cpu_dmb();
    cache_invalidate_by_addr((void *)start, end - start);
}
```

更稳妥的架构选择：

1. DMA 缓冲区放入非 Cache 区域。
2. 通过 MPU 将 DMA Buffer 配置为 Non-cacheable。
3. 使用明确的 `clean/invalidate` 生命周期。
4. 对 DMA Buffer 做 Cache Line 对齐并独占 Cache Line。

---

## 5.9 `volatile` 不能解决 DMA 一致性

错误理解：

```
volatile uint8_t dma_buf[256];
```

`volatile` 只表示：

- 编译器不能删除或合并对该内存的访问。

它不能保证：

- Cache 一致性。
- 多核一致性。
- DMA 和 CPU 的访问顺序。
- 总线写入已经完成。

DMA 与 CPU 共享数据时，需要根据平台使用：

- Cache Maintenance。
- `DMB`。
- `DSB`。
- MPU 内存属性。
- 原子状态变量。
- 明确的 Ownership 协议。

---

## 5.10 DMA 中断状态处理

典型 DMA ISR：

```
void DMA1_Channel1_IRQHandler(void)
{
    uint32_t flags = dma_get_flags(ADC1_DMA);

    if ((flags & DMA_FLAG_TRANSFER_ERROR) != 0U) {
        dma_clear_flag(ADC1_DMA, DMA_FLAG_TRANSFER_ERROR);

        dma_disable(ADC1_DMA);
        adc_disable_dma(ADC1);

        g_adc_dma_error_count++;
        adc_dma_error_notify_from_isr();
        return;
    }

    if ((flags & DMA_FLAG_HALF_TRANSFER) != 0U) {
        dma_clear_flag(ADC1_DMA, DMA_FLAG_HALF_TRANSFER);

        adc_cache_invalidate_half(0);
        adc_half_ready_notify_from_isr(0);
    }

    if ((flags & DMA_FLAG_TRANSFER_COMPLETE) != 0U) {
        dma_clear_flag(ADC1_DMA, DMA_FLAG_TRANSFER_COMPLETE);

        adc_cache_invalidate_half(1);
        adc_half_ready_notify_from_isr(1);
    }
}
```

注意事项：

- 先读取完整状态，再清除标志。
- 错误标志优先处理。
- 清除标志后再退出。
- 避免在 ISR 中执行复杂算法。
- 不要在 ISR 中调用可能阻塞的 API。
- 防止重复处理中断。
- 对 DMA 状态机进行显式管理。

---

## 6. 性能量化分析

以下数据以一个典型平台为例：

- MCU：Cortex-M7，主频 480 MHz
- SRAM 总线：240 MHz
- D-Cache：32 Byte Cache Line
- UART：921600 bit/s
- SPI：40 MHz
- ADC：2 MSPS
- DMA 数据宽度：16 bit
- RTOS：FreeRTOS 类内核

实际数据会随芯片 DMA 架构、总线矩阵、Flash 等待周期和编译器优化而变化。

## 6.1 UART 带宽计算

异步 UART 常见格式为：

```
1 起始位 + 8 数据位 + 1 停止位 = 10 bit/Byte
```

因此：

Throughput=Baudrate10Throughput=10Baudrate​

当波特率为 921600：

Throughput=92160010=92160 Byte/sThroughput=10921600​=92160 Byte/s

每字节到达间隔：

Tbyte=10921600≈10.85 μsTbyte​=92160010​≈10.85 μs

若使用每字节中断，CPU 必须在约 10.85 μs 内完成一次中断响应和数据处理。

如果每次 ISR 平均耗时 1.2 μs：

CPU Occupancy≈92160×1.2μs=11.06%CPU Occupancy≈92160×1.2μs=11.06%

DMA 按 64 字节触发一次：

ISR Rate=9216064=1440 次/sISR Rate=6492160​=1440 次/s

若每次块处理耗时 5 μs：

CPU Occupancy=1440×5μs=0.72%CPU Occupancy=1440×5μs=0.72%

**DMA 的收益不仅是减少数据搬运指令，更重要的是减少中断频率。**

## 6.2 ADC 连续采样计算

ADC 采样率：

```
2 MSPS
```

每个采样点 16 bit：

Bandwidth=2M×2=4MB/sBandwidth=2M×2=4MB/s

缓冲区为 1024 点，半缓冲为 512 点：

Thalf=5122M=256μsThalf​=2M512​=256μs

因此 CPU 必须在 **256 μs** 内完成前半缓冲处理，否则后续会发生数据覆盖。

若算法处理半缓冲最大耗时为 180 μs，则时序裕量：

Margin=256−180=76μsMargin=256−180=76μs

裕量比例：

76256×100%≈29.7%25676​×100%≈29.7%

工业系统建议最坏处理时间不超过缓冲周期的 60%～70%，为中断抖动、Cache Miss、总线竞争保留空间。

## 6.3 DMA 内存占用

双缓冲采样：

```
每个缓冲区：1024 × 2 Byte = 2048 Byte
双缓冲：4096 Byte
```

再考虑：

- Cache 对齐填充：最多 64 Byte
- 描述符：例如 32～128 Byte
- RTOS 消息结构：若每块 16 Byte

总占用约为：

Memory≈4096+64+128+16=4304 ByteMemory≈4096+64+128+16=4304 Byte

## 6.4 DMA 与 CPU 搬运性能

以 1 MB 数据复制为例，假设测量结果如下：

|方案|CPU 时间|CPU 占用|备注|
|---|---|---|---|
|`memcpy`，D-Cache 开启|0.62 ms|100%|CPU 独占|
|32 bit 手工复制|0.78 ms|100%|通常不如库函数|
|DMA，单次传输|1.10 ms|约 3%|含启动和完成等待|
|DMA，异步执行|0.95 ms 总线时间|约 2%|CPU 可并行执行|
|DMA + 高总线竞争|1.8 ms|约 2%|LCD/SDRAM 竞争明显|

结论：

- 小于 64～128 Byte 的复制，DMA 启动开销可能抵消收益。
- 大块数据、异步搬运和持续流处理更适合 DMA。
- DMA 不等于绝对更快，DMA 也会参与总线竞争。
- DMA 最重要的收益通常是 **CPU 释放和实时性改善**。

## 6.5 DMA 启动开销

典型 DMA 启动流程包括：

1. 禁止 DMA。
2. 清除标志。
3. 写地址寄存器。
4. 写长度寄存器。
5. 配置控制寄存器。
6. 打开 DMA 请求。
7. 使能 DMA。

假设启动配置耗时 1.5 μs，完成中断和状态处理耗时 1.0 μs：

Toverhead=2.5μsToverhead​=2.5μs

对于 16 Byte 数据：

```
DMA 实际搬运可能只需约 0.5 μs
```

此时 DMA 不一定比 CPU 复制有优势。

对于 4 KB 数据：

```
DMA 启动开销占比很低
```

因此需要设置 DMA 使用阈值：

```
#define DMA_COPY_THRESHOLD 128U

void *optimized_copy(void *dst,
                     const void *src,
                     size_t len)
{
    if (len < DMA_COPY_THRESHOLD) {
        return memcpy(dst, src, len);
    }

    dma_memcpy_async(dst, src, len);
    return dst;
}
```

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否存在持续或大块数据搬运？
|
+-- 否 --> 数据量是否小于 DMA 启动阈值？
|          |
|          +-- 是 --> 直接 CPU 访问 / 中断
|          |
|          +-- 否 --> 使用一次性 DMA
|
+-- 是 --> 数据是否连续、不能停止？
           |
           +-- 否 --> 单次 DMA + 完成中断
           |
           +-- 是 --> 是否需要边采集边处理？
                      |
                      +-- 否 --> 环形 DMA
                      |
                      +-- 是 --> 处理时间是否小于半缓冲周期？
                                 |
                                 +-- 是 --> 半传输 / 双缓冲
                                 |
                                 +-- 否 --> 增大缓冲区、降低采样率、
                                            优化算法或增加处理核
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|UART 低速命令行|中断或短 DMA|数据量低，软件简单|
|UART 高速协议|环形 DMA + IDLE|避免每字节中断|
|SPI 传感器批量读取|全双工 DMA|同时处理 TX/RX|
|ADC 连续采样|循环 DMA + 半传输|持续采集、块级处理|
|DAC 波形输出|循环 DMA + 定时器触发|精确定时|
|LCD 刷屏|内存到外设 DMA|释放 CPU|
|摄像头采集|双缓冲 / 链式 DMA|采集和处理并行|
|Ethernet RX|描述符环 + DMA|适合变长帧和零拷贝|
|大块内存复制|内存到内存 DMA|CPU 异步执行|
|小于 64 Byte 复制|CPU `memcpy`|DMA 启动开销不划算|
|低功耗持续采样|DMA + 低功耗唤醒|降低 CPU 活跃时间|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：明确 DMA Buffer Ownership

任何 DMA 缓冲区都必须明确当前所有权：

```
DMA Owned:
    CPU 不能读取或修改

CPU Owned:
    DMA 不能覆盖或读取
```

推荐状态机：

```
typedef enum {
    BUF_FREE = 0,
    BUF_DMA_WRITING,
    BUF_READY,
    BUF_CPU_PROCESSING,
} buffer_state_t;
```

### 原则二：DMA API 必须区分同步和异步

错误设计：

```
void dma_transfer(void *src, void *dst, size_t len);
```

调用者无法知道：

- 是否立即完成。
- 是否可以修改 `src`。
- 什么时候可以复用 `dst`。
- 错误如何返回。

推荐：

```
typedef void (*dma_done_cb_t)(void *arg, int result);

int dma_submit(const dma_transfer_t *transfer,
               dma_done_cb_t callback,
               void *arg);

int dma_wait(dma_handle_t handle,
             uint32_t timeout_ms);
```

### 原则三：不要把 DMA 中断当作业务处理线程

DMA ISR 只做：

- 读取状态。
- 清除标志。
- 切换缓冲区所有权。
- 投递事件。
- 必要的 Cache 操作。

复杂解析、滤波、协议处理应放到任务或工作队列。

### 原则四：所有传输都必须有错误恢复路径

必须覆盖：

- 传输错误。
- FIFO 错误。
- 总线错误。
- 外设溢出。
- DMA 超时。
- 取消传输。
- 缓冲区溢出。
- 外设异常复位。

### 原则五：长度和地址都进行静态约束

```
_Static_assert((UART_RX_DMA_SIZE & (UART_RX_DMA_SIZE - 1U)) == 0U,
               "DMA ring size must be power of two");

_Static_assert((sizeof(adc_buf) % 32U) == 0U,
               "ADC buffer should align with cache line");
```

## 8.2 选型决策矩阵

评分范围：1～5，分数越高越适合。

|方案|吞吐量|实时性|CPU 释放|内存成本|软件复杂度|
|---|---|---|---|---|---|
|轮询|1|2|1|5|5|
|中断|2|3|2|5|4|
|单次 DMA|4|4|4|4|4|
|环形 DMA|5|5|5|3|3|
|双缓冲 DMA|5|5|5|2|2|
|链式 DMA|5|5|5|2|1|

## 8.3 工业级编码规范

- DMA 地址统一使用 `uintptr_t`。
- DMA 缓冲区显式对齐。
- DMA 缓冲区尽量静态分配，避免栈上分配。
- 所有 DMA 状态变量使用明确的数据类型。
- 不在 DMA ISR 中调用阻塞 API。
- 不假设 DMA 传输完成后外设已经完成物理输出。
- 统一清除 DMA 状态标志。
- 对 `NDTR`、当前目标地址、错误标志进行一致性读取。
- 对 Cache 平台统一封装 `dma_prepare_tx()` 和 `dma_prepare_rx()`。
- 用逻辑分析仪验证外设请求节奏和时序。
- 为每个 DMA 通道定义唯一资源所有者。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：DMA TC 后立即认为串口发送完成

### 错误代码

```
void DMA_TX_IRQHandler(void)
{
    if (dma_tc_flag()) {
        dma_clear_tc_flag();
        rs485_set_tx_enable(false);
    }
}
```

### 根因

DMA 只保证最后一个字节已写入 UART 数据寄存器，不保证最后一个停止位已经从 TX 引脚发出。

### 正确实现

```
void DMA_TX_IRQHandler(void)
{
    if (dma_tc_flag()) {
        dma_clear_tc_flag();
        uart_enable_tc_interrupt();
    }
}

void UART_IRQHandler(void)
{
    if (uart_tc_flag()) {
        uart_clear_tc_flag();
        uart_disable_tc_interrupt();
        rs485_set_tx_enable(false);
    }
}
```

### 风险影响

- RS-485 尾字节被截断。
- 对端 CRC 错误。
- 高温、低压、高波特率条件下出现偶发丢帧。

---

## 9.2 错误二：带 Cache 平台直接让 DMA 读写普通缓存区

### 错误代码

```
uint8_t tx_buf[1024];

memcpy(tx_buf, packet, packet_len);
dma_start_tx(tx_buf, packet_len);
```

### 根因

CPU 修改的数据可能仅在 D-Cache 中，DMA 从 SRAM 读取旧数据。

### 正确实现

```
memcpy(tx_buf, packet, packet_len);
dma_cache_clean(tx_buf, packet_len);
cpu_dsb();

dma_start_tx(tx_buf, packet_len);
```

接收场景：

```
dma_wait_rx_done();

dma_cache_invalidate(rx_buf, rx_len);
cpu_dmb();

parse_packet(rx_buf, rx_len);
```

### 风险影响

- 发出的数据偶发为旧包。
- 接收数据随机回退。
- 调试器查看内存时与 CPU 读取结果不一致。
- 关闭 Cache 后问题消失，导致误判为“Cache 有 Bug”。

---

## 9.3 错误三：环形 DMA 只处理半传输和全传输，不处理溢出

### 错误代码

```
void uart_dma_half_isr(void)
{
    protocol_parse(uart_dma_buf, 128);
}

void uart_dma_full_isr(void)
{
    protocol_parse(&uart_dma_buf[128], 128);
}
```

### 根因

解析任务可能因为高优先级任务、Flash 操作或临界区延迟，无法及时消费数据。

### 正确实现

```
typedef struct {
    uint32_t overflow_count;
    uint32_t last_write_total;
    uint32_t read_total;
} rx_stream_t;

static rx_stream_t g_rx_stream;

void uart_rx_poll(void)
{
    uint32_t write_total = dma_get_total_written();
    uint32_t available = write_total - g_rx_stream.read_total;

    if (available > UART_RX_DMA_SIZE) {
        g_rx_stream.overflow_count++;

        /*
         * 丢弃旧数据，保留最新一圈。
         */
        g_rx_stream.read_total =
            write_total - UART_RX_DMA_SIZE;
        available = UART_RX_DMA_SIZE;
    }

    consume_rx_bytes(g_rx_stream.read_total,
                     available);

    g_rx_stream.read_total += available;
}
```

### 风险影响

- 协议帧粘连。
- 帧头丢失。
- CRC 错误。
- 长时间运行后通信失步。

---

## 9.4 错误四：DMA 数据宽度配置错误

### 错误代码

```
uint16_t adc_buf[1024];

dma_set_peripheral_width(ADC_DMA, DMA_WIDTH_8BIT);
dma_set_memory_width(ADC_DMA, DMA_WIDTH_8BIT);
```

### 根因

ADC 有效数据为 12 位，使用 8 位传输会截断高位或导致数据排列不符合预期。

### 正确实现

```
dma_set_peripheral_width(ADC_DMA, DMA_WIDTH_16BIT);
dma_set_memory_width(ADC_DMA, DMA_WIDTH_16BIT);
dma_set_length(ADC_DMA, 1024U);
```

### 风险影响

- ADC 分辨率下降。
- 采样值幅度异常。
- FFT、滤波、控制算法结果错误。
- 数据长度计算错误。

---

## 9.5 错误五：DMA Buffer 放在 DMA 不可访问的内存区域

### 错误代码

```
uint8_t dma_buf[512];

/* 实际链接到了 DTCM，但 DMA 控制器不支持访问 DTCM */
dma_start(dma_buf, 512);
```

### 根因

某些 MCU 的 DMA 控制器只能访问部分 SRAM，不能访问：

- DTCM。
- ITCM。
- 某些高速缓存区域。
- 外部内存未正确初始化的区域。

### 正确实现

链接脚本：

```
.dma_buffer (NOLOAD) :
{
    . = ALIGN(32);
    *(.dma_buffer)
    . = ALIGN(32);
} >RAM_D2
```

C 代码：

```
static uint8_t dma_buf[512]
    __attribute__((section(".dma_buffer"), aligned(32)));
```

### 风险影响

- DMA 无响应。
- 总线错误。
- 传输完成标志不产生。
- 仅在某些构建配置下失败。

---

## 10. 多机制组合使用方案

## 10.1 UART DMA + IDLE + Ring Buffer + RTOS

推荐架构：

```
UART RX
  |
  v
DMA Circular Buffer
  |
  +--> Half Transfer ISR
  |
  +--> Transfer Complete ISR
  |
  +--> UART IDLE ISR
              |
              v
       Event / Task Notification
              |
              v
       Protocol Parser Task
              |
              v
       Message Queue / Business Task
```

### 组合设计逻辑

- DMA：持续搬运字节。
- IDLE：检测一段时间没有新字节，用于识别变长帧。
- 环形缓冲区：避免每次重新配置 DMA。
- RTOS 通知：低开销唤醒解析任务。
- 协议任务：处理帧边界、CRC、超时和重同步。

### 完整代码框架

```
#define UART_RX_BUF_SIZE 1024U

static uint8_t uart_rx_buf[UART_RX_BUF_SIZE]
    __attribute__((aligned(32)));

static volatile uint32_t rx_write_total;
static volatile uint32_t rx_read_total;

static TaskHandle_t protocol_task_handle;

void uart_dma_init(void)
{
    dma_disable(UART1_RX_DMA);
    dma_clear_all_flags(UART1_RX_DMA);

    dma_set_request(UART1_RX_DMA, DMA_REQ_UART1_RX);
    dma_set_peripheral_address(UART1_RX_DMA,
                               (uintptr_t)&UART1->RDR);
    dma_set_memory_address(UART1_RX_DMA,
                           (uintptr_t)uart_rx_buf);
    dma_set_length(UART1_RX_DMA, UART_RX_BUF_SIZE);

    dma_set_direction(UART1_RX_DMA, DMA_PERIPH_TO_MEM);
    dma_set_circular_mode(UART1_RX_DMA, true);
    dma_set_peripheral_increment(UART1_RX_DMA, false);
    dma_set_memory_increment(UART1_RX_DMA, true);
    dma_set_peripheral_width(UART1_RX_DMA, DMA_WIDTH_8BIT);
    dma_set_memory_width(UART1_RX_DMA, DMA_WIDTH_8BIT);

    dma_enable_irq(UART1_RX_DMA,
                   DMA_IRQ_HT |
                   DMA_IRQ_TC |
                   DMA_IRQ_TE);

    uart_enable_dma_rx(UART1);
    uart_enable_idle_irq(UART1);

    dma_enable(UART1_RX_DMA);
}

static void notify_parser_from_isr(void)
{
    BaseType_t higher_priority_woken = pdFALSE;

    vTaskNotifyGiveFromISR(protocol_task_handle,
                           &higher_priority_woken);

    portYIELD_FROM_ISR(higher_priority_woken);
}

void UART1_IRQHandler(void)
{
    if (uart_idle_flag(UART1)) {
        uart_clear_idle_flag(UART1);
        notify_parser_from_isr();
    }
}

void DMA1_Channel2_IRQHandler(void)
{
    uint32_t flags = dma_get_flags(UART1_RX_DMA);

    if ((flags & DMA_FLAG_TRANSFER_ERROR) != 0U) {
        dma_clear_flag(UART1_RX_DMA,
                       DMA_FLAG_TRANSFER_ERROR);

        dma_disable(UART1_RX_DMA);
        uart_disable_dma_rx(UART1);

        uart_dma_recover();
        notify_parser_from_isr();
        return;
    }

    if ((flags & (DMA_FLAG_HALF_TRANSFER |
                  DMA_FLAG_TRANSFER_COMPLETE)) != 0U) {
        dma_clear_flag(UART1_RX_DMA,
                       DMA_FLAG_HALF_TRANSFER |
                       DMA_FLAG_TRANSFER_COMPLETE);

        notify_parser_from_isr();
    }
}

static uint32_t dma_get_write_total(void)
{
    static uint32_t last_pos;
    static uint32_t wrap_count;

    uint32_t pos = UART_RX_BUF_SIZE -
                   dma_get_remaining(UART1_RX_DMA);

    pos %= UART_RX_BUF_SIZE;

    if (pos < last_pos) {
        wrap_count++;
    }

    last_pos = pos;

    return wrap_count * UART_RX_BUF_SIZE + pos;
}

void protocol_task(void *arg)
{
    uint8_t parse_buf[256];

    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        uint32_t write_total = dma_get_write_total();
        uint32_t available = write_total - rx_read_total;

        if (available > UART_RX_BUF_SIZE) {
            /*
             * 环形缓冲区已溢出，丢弃最旧数据。
             */
            rx_read_total = write_total - UART_RX_BUF_SIZE;
            available = UART_RX_BUF_SIZE;
        }

        while (available > 0U) {
            size_t chunk = available;

            if (chunk > sizeof(parse_buf)) {
                chunk = sizeof(parse_buf);
            }

            size_t offset = rx_read_total % UART_RX_BUF_SIZE;
            size_t contiguous = UART_RX_BUF_SIZE - offset;

            if (chunk > contiguous) {
                chunk = contiguous;
            }

            dma_cache_invalidate(&uart_rx_buf[offset], chunk);

            memcpy(parse_buf, &uart_rx_buf[offset], chunk);
            protocol_feed(parse_buf, chunk);

            rx_read_total += chunk;
            available -= chunk;
        }
    }
}
```

---

## 10.2 ADC DMA + 双缓冲 + DSP 任务

```
ADC 定时器触发
      |
      v
ADC 数据寄存器
      |
      v
DMA M0/M1 双缓冲
      |
      +--> Buffer Ready Event
      |
      v
DSP Task
      |
      +--> FIR / FFT / RMS / 特征提取
      |
      v
控制任务 / 存储任务 / 通信任务
```

关键约束：

Tprocess,max<TbufferTprocess,max​<Tbuffer​

如果：

```
采样率 = 2 MSPS
每块样本数 = 512
```

则：

Tbuffer=256μsTbuffer​=256μs

DSP 任务最坏执行时间必须小于 256 μs，建议控制在 150～180 μs 以内。

---

## 11. 工业级实际案例分析

## 11.1 案例一：变频器 Modbus RTU 高速串口接收

### 需求

- 波特率：921600。
- 帧长度：8～512 Byte。
- 支持变长帧。
- 不允许因高优先级控制任务导致串口丢帧。
- 需要检测 CRC 错误和接收溢出。

### 架构

```
UART RX + DMA Circular Buffer
         |
         +--> IDLE 事件
         +--> DMA HT/TC 事件
         +--> UART ORE 错误
         |
         v
Parser Task
         |
         +--> 帧边界检测
         +--> 地址过滤
         +--> CRC16
         +--> 超时处理
```

### 设计要点

1. DMA 缓冲区至少覆盖系统最坏调度延迟：

BufferSize≥Throughput×WorstCaseDelayBufferSize≥Throughput×WorstCaseDelay

若最坏任务延迟为 5 ms：

BufferSize≥92160×0.005=460.8ByteBufferSize≥92160×0.005=460.8Byte

实际选择 1024 Byte，保留约 11 ms 缓冲时间。

2. 使用单调计数器避免环绕判断错误。
3. UART ORE 错误时：
    - 记录错误。
    - 清除状态。
    - 必要时重置 UART。
    - 不随意清空全部有效缓冲区。
4. CRC 在任务中执行，避免 ISR 过长。

---

## 11.2 案例二：电机控制系统 ADC 连续采样

### 需求

- ADC 采样率：1 MSPS。
- 采集三相电流、电压。
- 采样数据用于 FOC 控制。
- 控制周期：20 kHz。
- 采样必须与 PWM 中点同步。

### 架构

```
PWM Timer Compare Event
          |
          v
ADC Trigger
          |
          v
ADC Scan Sequence
          |
          v
DMA Circular Buffer
          |
          v
Half Transfer ISR
          |
          v
FOC Control Task / ISR
```

### 设计要点

- 使用定时器触发 ADC，禁止软件启动采样。
- DMA 使用 16 bit 外设宽度和内存宽度。
- 采样缓冲区采用 Cache 非缓存区域或严格 Cache 管理。
- 控制计算使用固定周期数据，不能处理“半更新”的数据。
- 半传输和全传输事件分别对应两个完整采样块。
- 若控制算法执行时间超过采样块周期，需要：
    - 增大缓冲区。
    - 降低采样频率。
    - 使用定点化。
    - 使用 DSP 指令。
    - 将采样和控制分配到不同执行单元。

### 典型数据结构

```
typedef struct {
    int16_t ia;
    int16_t ib;
    int16_t ic;
    int16_t va;
    int16_t vb;
    int16_t vc;
} adc_frame_t;

static adc_frame_t adc_dma_buf[64]
    __attribute__((aligned(32)));
```

若每个 Frame 12 Byte，采样块 64 Frame：

Memory=64×12=768ByteMemory=64×12=768Byte

---

## 11.3 案例三：工业 HMI LCD DMA 刷新

### 需求

- RGB565。
- 屏幕分辨率：800 × 480。
- 局部区域刷新。
- CPU 同时运行协议栈和 UI 逻辑。
- 避免 LCD 刷新阻塞控制任务。

### 全屏数据量

RGB565 每像素 2 Byte：

DataSize=800×480×2=768000Byte≈750KBDataSize=800×480×2=768000Byte≈750KB

如果通过 SPI 40 MHz 发送：

T=768000×840M=153.6msT=40M768000×8​=153.6ms

这意味着全屏刷新理论上最高约 6.5 FPS，实际还会受命令、空闲和 DMA 竞争影响。

### 局部刷新收益

刷新 100 × 50 区域：

DataSize=100×50×2=10000ByteDataSize=100×50×2=10000Byte

发送时间：

T=10000×840M=2msT=40M10000×8​=2ms

因此工业 UI 应优先使用：

- Dirty Rectangle。
- 局部 DMA 刷新。
- 双 Framebuffer。
- DMA 链式命令和像素数据发送。
- SPI FIFO + DMA Burst。

---

## 12. 高频问题深度答疑

## 问题一：DMA 是否一定比中断更快？

不一定。

DMA 具有固定启动开销：

TDMA=Tsetup+Ttransfer+TISRTDMA​=Tsetup​+Ttransfer​+TISR​

CPU 复制耗时：

TCPU=TcopyTCPU​=Tcopy​

当数据量很小时：

Tsetup+Ttransfer>TCPUTsetup​+Ttransfer​>TCPU​

此时 CPU 直接复制更快。

但 DMA 的价值还包括：

- CPU 可并行执行其他任务。
- 减少中断次数。
- 提高持续流稳定性。
- 降低任务抖动。

因此不能只比较单次搬运耗时。

---

## 问题二：DMA 传输完成后，为什么外设仍然没有完成？

因为 DMA 和外设内部通常存在至少两级缓冲：

```
DMA Memory
   |
   v
外设数据寄存器 / FIFO
   |
   v
外设移位寄存器
   |
   v
物理引脚
```

DMA TC 通常只代表第一步完成。对于 UART、SPI、I²C、RS-485 等，需要额外等待：

- UART TC。
- SPI BSY 清零。
- I²C STOP 完成。
- LCD TE 或 BUSY 状态结束。
- DAC 输出流水线稳定。

---

## 问题三：环形 DMA 为什么会丢数据？

常见根因：

1. CPU 消费速度低于生产速度。
2. 缓冲区过小。
3. RTOS 任务被高优先级任务长期抢占。
4. 长时间关闭中断。
5. DMA 写指针和 CPU 读指针同步错误。
6. `NDTR` 读取与环绕判断存在竞态。
7. Cache 未失效导致软件误判数据未更新。

基本条件：

Rconsume≥RproduceRconsume​≥Rproduce​

如果长期不满足，任何环形缓冲区最终都会溢出，只是时间早晚不同。

---

## 问题四：半传输和双缓冲应该如何选择？

### 半传输

适用于：

- 缓冲区固定。
- 数据连续。
- 前后半区大小相同。
- DMA 控制器支持可靠 HT 事件。

### 双缓冲

适用于：

- 需要明确的 Buffer Ownership。
- 采集和处理严格并行。
- 需要在 M0/M1 之间切换。
- 传输链较复杂或需要动态替换缓冲区。

双缓冲的软件语义更清晰，但硬件支持和状态管理更复杂。

---

## 问题五：DMA 是否会影响实时性？

会。

DMA 也是总线主设备，会与 CPU、显示控制器、以太网、SDMMC 等竞争总线。

可能造成：

- CPU 访问 SRAM 延迟增加。
- Cache Miss 代价上升。
- LCD 刷新时控制任务抖动。
- SDRAM 仲裁延迟增大。
- 最坏中断响应时间恶化。

需要关注：

- DMA 优先级。
- Burst 长度。
- FIFO 阈值。
- 总线矩阵 QoS。
- 内存区域分配。
- 是否将高实时数据放到独立 SRAM。
- 是否限制大块 DMA 的连续占用时间。

---

## 问题六：DMA 缓冲区应该放在哪里？

选择顺序通常为：

1. **DMA 可访问的内部 SRAM**。
2. 非 Cache SRAM。
3. 与 CPU 高实时路径分离的 SRAM Bank。
4. 外部 SDRAM。
5. 共享内存或特殊内存区域。

不建议放在：

- DMA 不可访问的 TCM。
- 未初始化的外部 RAM。
- 栈内临时数组。
- 与其他高带宽 DMA 设备严重竞争的区域。

---

## 13. 课程核心总结

### 13.1 核心要点

- DMA 本质上是一个独立总线主设备。
- DMA 传输必须同时配置地址、方向、宽度、长度、递增和请求源。
- DMA TC 不一定等于外设物理传输结束。
- 环形 DMA 解决持续数据流问题，但必须设计读写指针和溢出策略。
- 双缓冲的核心是 CPU 与 DMA 的所有权切换。
- 带 Cache 平台必须处理 Clean、Invalidate 和内存屏障。
- DMA 可以降低 CPU 搬运负载，但可能增加总线竞争。
- DMA Buffer 的内存位置、对齐和访问属性与代码逻辑同样重要。
- DMA ISR 应保持短小，复杂工作放入任务。
- 任何 DMA 架构都必须具备超时、错误恢复和取消机制。

### 13.2 性能排序

一般情况下：

```
CPU 轮询 < 字节中断 < 块中断 < 单次 DMA < 环形 DMA < 双缓冲 DMA < 链式 DMA
```

但这是综合吞吐量和 CPU 占用的排序，不是所有场景下的单次延迟排序。

### 13.3 通用选型结论

- **小块、低频、控制型数据**：CPU 或中断。
- **中等大小的一次性数据**：单次 DMA。
- **高速连续数据流**：环形 DMA。
- **采集与处理并行**：半传输或双缓冲 DMA。
- **复杂报文和多段缓冲区**：链式 / Scatter-Gather DMA。
- **带 Cache 的高性能 MCU**：非缓存内存或严格 Cache 生命周期管理。
- **实时控制系统**：优先保证触发时序和最坏延迟，而不是只追求平均吞吐量。

---

## 14. 快速参考速查表

## 14.1 场景选型表

|需求|推荐模式|关键配置|
|---|---|---|
|UART TX 单帧|单次 DMA|外设地址固定、内存递增|
|UART RX 变长帧|环形 DMA + IDLE|DMA 循环、软件读写指针|
|ADC 连续采样|循环 DMA|半传输、全传输|
|ADC + DSP|双缓冲 DMA|明确 Buffer Ownership|
|SPI 全双工|RX/TX 两路 DMA|同步启动、处理 NSS|
|DAC 波形|定时器触发 DMA|循环|