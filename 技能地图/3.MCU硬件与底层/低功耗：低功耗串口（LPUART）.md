
> 本课聚焦 **LPUART（Low-Power Universal Asynchronous Receiver/Transmitter）** 的低功耗工作机制、时钟选择、Stop 模式唤醒、接收缓冲、DMA、波特率误差、协议设计和工业级故障处理。示例采用 Cortex-M + STM32 风格伪 HAL/寄存器接口，具体寄存器位、低功耗保持能力和唤醒方式必须以目标 MCU 的 Reference Manual、Datasheet 和 Errata 为准。

---

## 1. 学习目标

### 理解

- 理解 LPUART 与普通 UART 的架构差异和适用边界。
- 理解低功耗串口的完整数据链路：

```
外部总线
    ↓
RX 输入同步/采样
    ↓
LPUART 波特率发生器
    ↓
Start Bit / 地址 / 字符匹配
    ↓
唤醒逻辑
    ↓
CPU 退出 Stop
    ↓
接收寄存器 / FIFO / DMA
    ↓
协议栈处理
```

- 理解 LPUART 在 Stop 模式下运行所依赖的低速时钟域。
- 理解起始位唤醒、地址匹配唤醒、帧匹配唤醒和 RXNE 中断唤醒之间的差异。
- 理解低功耗串口系统中首字节丢失、波特率误差、总线反灌和收发器待机电流等问题。

### 掌握

- 配置 LPUART 的时钟源、波特率、数据格式和唤醒源。
- 配置 Stop 模式下的接收唤醒。
- 使用 DMA、空闲线检测、接收超时和环形缓冲处理不定长数据。
- 正确执行 LPUART 进入低功耗前的挂起与唤醒后的恢复。
- 处理过载、帧错误、噪声、奇偶校验和接收超时。

### 精通

- 分析 LPUART 的波特率分频、采样时序、同步延迟和首字节捕获路径。
- 量化不同波特率、时钟源和唤醒策略对功耗与可靠性的影响。
- 设计带协议前导码、设备地址、CRC、重同步和重传机制的工业通信方案。
- 处理 RTOS、DMA、Stop、唤醒中断和协议栈之间的并发关系。

### 能够设计

- 支持 Stop 唤醒的 LPUART 驱动；
- 低功耗 RS-485、GNSS、Modbus、传感器总线或主从通信方案；
- LPUART + DMA + 环形缓冲 + 帧超时的完整架构；
- 包含时钟恢复、收发器电源控制、错误统计和安全降级能力的工业级串口系统。

---

## 2. 前置要求

### 知识要求

- UART 异步串行协议：Start Bit、Data Bit、Parity、Stop Bit；
- Cortex-M 中断、NVIC、DMA、Stop、WFI/WFE；
- RCC 时钟树、LSE、LSI、HSI、PCLK 和时钟门控；
- GPIO 复用、上拉下拉、输入滤波和电平转换；
- RTOS 任务、队列、信号量、Tickless Idle；
- RS-232、RS-485、LIN 等物理层基础；
- CRC、帧同步、超时和重传机制。

### 技能要求

- 能阅读 LPUART、RCC、PWR、GPIO 和 DMA 章节；
- 能使用逻辑分析仪分析 UART 波形；
- 能使用示波器测量唤醒延迟、波特率和电源波形；
- 能编写 ISR-safe、DMA-safe 的环形缓冲；
- 能定位 UART 乱码、丢首字节、过载和 Stop 后无法接收问题。

---

## 3. 技术概述

## 3.1 LPUART 的定位

LPUART 是专门面向低功耗场景设计的异步串口外设，典型特征包括：

- 可使用 LSE、LSI 或低功耗内部时钟；
- 支持在 Stop 模式下接收或唤醒；
- 低速时钟下仍可支持较低波特率；
- 可通过起始位、地址或字符匹配唤醒；
- 通常支持 DMA、空闲线检测和接收超时；
- 发射和接收能力可能与普通 UART 不完全一致。

**工程上不能将 LPUART 简单理解为“功耗更低的 UART”。**

它通常具有不同的：

- 时钟源；
- 波特率分频算法；
- 最大/最小波特率；
- Stop 模式保持条件；
- 唤醒方式；
- FIFO 和 DMA 能力；
- 复位与状态保持行为。

## 3.2 普通 UART 与 LPUART 的主要区别

普通 UART 通常依赖：

```
PCLK / APB Clock / HSI / HSE
```

这些时钟在 Stop 模式中往往被关闭。

LPUART 通常依赖：

```
LSE / LSI / HSI16 / 低功耗内部时钟 / 外部低速时钟
```

这些时钟可能在 Stop 模式中继续运行，从而实现：

```
MCU 进入 Stop
    ↓
LPUART 保持接收逻辑和低速时钟
    ↓
检测 Start Bit 或匹配字符
    ↓
唤醒 MCU
    ↓
继续接收数据
```

## 3.3 低功耗串口的系统约束

LPUART 设计必须同时满足：

1. 波特率误差；
2. 接收采样时序；
3. Stop 模式时钟保持；
4. 首字节是否可被硬件缓存；
5. 收发器的待机和反灌电流；
6. 唤醒延迟；
7. 接收 FIFO/DMA 缓冲深度；
8. 协议的前导码和重同步能力；
9. RTOS 调度延迟；
10. 低功耗模式进入和退出时序。

---

## 4. 核心特性横向对比

以下参数为典型工程特征，具体指标必须以目标芯片手册为准。

|维度|普通 UART|LPUART|软件 Bit-bang|
|---|---|---|---|
|Stop 中接收|通常不支持或受限|通常支持|通常不可靠|
|低速时钟支持|有限|较强|依赖 CPU|
|波特率范围|较宽|受低速时钟和分频器限制|受 CPU 实时性限制|
|低功耗能力|中|高|低|
|首字节唤醒|依芯片支持|常见支持|软件处理|
|DMA|通常支持|通常支持|不适用|
|时钟恢复复杂度|中|高|高|
|协议可靠性|高|高，但需处理唤醒窗口|低|
|适合 RS-485|是|是，需配合收发器|不推荐|
|适合低功耗传感器|一般|很适合|不推荐|
|适合高波特率|较好|受时钟和硬件限制|差|
|典型风险|中断丢失、过载|首字节、时钟、Stop 保持|时序抖动|

### 常见低功耗时钟比较

|时钟源|典型频率|精度|Stop 保持|功耗|适用场景|
|---|---|---|---|---|---|
|LSE|32.768 kHz|高|通常支持|极低|低波特率、低功耗|
|LSI|32~100 kHz|较低|通常支持|低|容差较宽的控制链路|
|HSI16|16 MHz|中|依芯片支持|中|较高波特率、快速唤醒|
|HSI48|48 MHz|中|通常不保持|较高|普通 UART/USB|
|外部时钟|依外部源|依外部源|依系统设计|依系统设计|工业精密通信|

### 波特率和时钟关系

LPUART 的波特率分频公式由具体 MCU 决定。常见形式之一：

BRR=fkerbaudBRR=baudfker​​

但部分 LPUART 使用特殊过采样或固定倍率，例如：

BRR=256×fkerbaudBRR=baud256×fker​​

因此**不能直接套用普通 USART 的 BRR 公式**。

---

## 5. 底层原理与功能特性深度解析

## 5.1 LPUART 接收采样原理

异步串口接收通常通过以下步骤完成：

1. RX 线从空闲高电平变为低电平；
2. 接收器检测 Start Bit；
3. 根据波特率时钟定位数据位中心；
4. 对数据位进行一次或多次采样；
5. 检查 Stop Bit；
6. 设置 RXNE、IDLE、ORE、FE、NE、PE 等状态；
7. 将数据移入 RDR/FIFO/DMA。

波特率误差来自发送端和接收端时钟误差：

ϵtotal=ϵtx+ϵrxϵtotal​=ϵtx​+ϵrx​

假设发送端误差为 +ϵtx+ϵtx​，接收端误差为 −ϵrx−ϵrx​，则最坏相对误差为：

∣ϵtotal∣=∣ϵtx∣+∣ϵrx∣∣ϵtotal​∣=∣ϵtx​∣+∣ϵrx​∣

若一帧为：

```
1 Start + 8 Data + 1 Stop = 10 bit
```

接收端在最后一个 Stop Bit 的采样位置可能累积较大相位偏差。因此：

- 低波特率并不一定更容易；
- 时钟精度和过采样配置仍然重要；
- LSI 可能无法满足高可靠工业通信；
- RS-485 长线还会叠加边沿畸变、EMI 和地电位差。

## 5.2 LPUART 时钟配置

```
typedef enum {
    LPUART_CLK_LSE,
    LPUART_CLK_LSI,
    LPUART_CLK_HSI16,
    LPUART_CLK_EXTERNAL,
} lpuart_clock_source_t;

typedef struct {
    lpuart_clock_source_t source;
    uint32_t clock_hz;
    uint32_t baudrate;
    uint8_t data_bits;
    uint8_t stop_bits;
    bool parity_enable;
    bool wakeup_enable;
} lpuart_config_t;

bool lpuart_clock_configure(const lpuart_config_t *cfg)
{
    if (cfg == NULL || cfg->clock_hz == 0U ||
        cfg->baudrate == 0U) {
        return false;
    }

    if (!rcc_enable_lpuart_clock_source(cfg->source)) {
        return false;
    }

    if (!rcc_wait_clock_ready(cfg->source, 100U)) {
        return false;
    }

    if (!rcc_select_lpuart_kernel_clock(cfg->source)) {
        return false;
    }

    if (!lpuart_baudrate_is_supported(cfg->clock_hz,
                                      cfg->baudrate)) {
        return false;
    }

    return lpuart_set_baudrate_from_kernel_clock(
        cfg->clock_hz,
        cfg->baudrate);
}
```

### 选择时钟源的工程原则

- 需要最低功耗：优先 LSE；
- 需要较高波特率：选择更高频、精度足够的时钟；
- 需要 Stop 中接收：确认该时钟在目标 Stop 模式保持；
- 使用 LSI：必须测量实际频率或允许更大的波特率容差；
- 需要 USB/CAN/Ethernet 等精密时基：不要让这些协议依赖 LSE 低频时钟。

## 5.3 波特率计算与误差验证

```
typedef struct {
    uint32_t brr;
    uint32_t actual_baud;
    int32_t error_ppm;
} lpuart_baud_result_t;

bool lpuart_calc_baud(uint32_t kernel_hz,
                      uint32_t baudrate,
                      lpuart_baud_result_t *result)
{
    if (kernel_hz == 0U || baudrate == 0U || result == NULL) {
        return false;
    }

    /*
     * 这里假设目标芯片采用：
     * BRR = 256 * kernel_clock / baudrate
     * 实际器件可能使用不同公式。
     */
    uint64_t numerator = 256ULL * kernel_hz;
    uint32_t brr = (uint32_t)((numerator + baudrate / 2U) /
                              baudrate);

    if (brr == 0U) {
        return false;
    }

    uint32_t actual = (uint32_t)(numerator / brr);
    int64_t error = ((int64_t)actual - baudrate) *
                    1000000LL / baudrate;

    result->brr = brr;
    result->actual_baud = actual;
    result->error_ppm = (int32_t)error;

    return true;
}
```

工程验收不应只看“配置成功”，还应记录：

- 目标波特率；
- 实际波特率；
- 分频值；
- 时钟源实测频率；
- 发送端误差；
- 接收端误差；
- 温度和电压条件；
- 长帧、连续帧和异常帧测试结果。

## 5.4 LPUART Stop 唤醒模式

常见唤醒模式：

### 起始位唤醒

```
RX 空闲高
    ↓
检测到 Start Bit
    ↓
LPUART 触发 Wakeup
    ↓
CPU 退出 Stop
    ↓
继续接收后续数据
```

优点：

- 响应快；
- 协议简单；
- 适合点对点或总线有前导码的场景。

缺点：

- 首字节可能无法完整保存；
- 唤醒和时钟恢复存在延迟；
- 可能因噪声低脉冲产生伪唤醒。

### 地址匹配唤醒

```
总线开始发送
    ↓
LPUART 保持接收若干字符
    ↓
匹配设备地址
    ↓
匹配成功后唤醒 CPU
```

优点：

- 多从机总线可减少无关唤醒；
- 降低总线监听功耗。

缺点：

- 硬件必须支持地址匹配保持；
- 地址字节之前的数据可能被硬件消耗；
- 协议格式必须固定。

### 字符匹配唤醒

适合固定同步字或唤醒字：

```
0x55 0x55 0xA5
```

匹配成功后 CPU 唤醒并接收完整数据帧。

## 5.5 LPUART 唤醒配置框架

```
typedef enum {
    LPUART_WAKE_START_BIT,
    LPUART_WAKE_ADDRESS,
    LPUART_WAKE_MATCH,
} lpuart_wakeup_mode_t;

typedef struct {
    lpuart_wakeup_mode_t mode;
    uint8_t address;
    uint8_t match_char;
    bool interrupt_enable;
    bool pwr_wakeup_enable;
} lpuart_wakeup_config_t;

bool lpuart_wakeup_configure(
    const lpuart_wakeup_config_t *cfg)
{
    if (cfg == NULL) {
        return false;
    }

    lpuart_disable_wakeup();
    lpuart_clear_wakeup_flag();
    exti_clear_pending(LPUART_WAKE_LINE);
    nvic_clear_pending(LPUART_IRQn);
    pwr_clear_lpuart_wakeup_flag();

    switch (cfg->mode) {
    case LPUART_WAKE_START_BIT:
        lpuart_set_wakeup_event(LPUART_EVENT_START_BIT);
        break;

    case LPUART_WAKE_ADDRESS:
        lpuart_set_address(cfg->address);
        lpuart_set_wakeup_event(LPUART_EVENT_ADDRESS_MATCH);
        break;

    case LPUART_WAKE_MATCH:
        lpuart_set_match_character(cfg->match_char);
        lpuart_set_wakeup_event(LPUART_EVENT_CHARACTER_MATCH);
        break;

    default:
        return false;
    }

    lpuart_clear_wakeup_flag();
    exti_clear_pending(LPUART_WAKE_LINE);

    if (cfg->interrupt_enable) {
        lpuart_enable_wakeup_interrupt();
        nvic_enable_irq(LPUART_IRQn);
    }

    if (cfg->pwr_wakeup_enable) {
        pwr_enable_lpuart_wakeup();
    }

    lpuart_enable_wakeup();
    return true;
}
```

## 5.6 LPUART + DMA 接收

中断逐字节接收在高吞吐或突发数据场景下会产生较高 CPU 活动。DMA 适合：

- 连续帧；
- 高波特率；
- 长报文；
- Stop 唤醒后的批量接收；
- RTOS 中减少 ISR 压力。

### 环形 DMA 缓冲

```
#define LPUART_RX_DMA_SIZE 256U

static uint8_t g_lpuart_rx_dma[LPUART_RX_DMA_SIZE];

bool lpuart_dma_rx_start(void)
{
    lpuart_clear_all_flags();
    dma_disable(LPUART_RX_DMA_CHANNEL);
    dma_clear_all_flags(LPUART_RX_DMA_CHANNEL);

    dma_config_memory_to_peripheral(
        LPUART_RX_DMA_CHANNEL,
        &LPUARTx->RDR,
        g_lpuart_rx_dma,
        LPUART_RX_DMA_SIZE,
        DMA_MODE_CIRCULAR,
        DMA_PRIORITY_HIGH);

    dma_enable(LPUART_RX_DMA_CHANNEL);
    lpuart_enable_dma_rx();
    lpuart_enable_idle_interrupt();

    return true;
}
```

### 空闲线检测

当总线一段时间没有接收到数据，LPUART 可产生 IDLE 事件，用于判断一帧结束。

```
void LPUART_IRQHandler(void)
{
    uint32_t status = lpuart_get_status();

    if ((status & LPUART_STATUS_IDLE) != 0U) {
        lpuart_clear_idle_flag();
        dma_memory_barrier();

        size_t write_pos = lpuart_dma_write_position();
        rx_ring_commit_until(write_pos);

        wake_event_post_isr(WAKE_SRC_LPUART_IDLE,
                            (uint32_t)write_pos,
                            low_power_timestamp());
    }

    if ((status & LPUART_STATUS_WUF) != 0U) {
        lpuart_clear_wakeup_flag();
        wake_event_post_isr(WAKE_SRC_LPUART,
                            0U,
                            low_power_timestamp());
    }

    if ((status & LPUART_STATUS_ORE) != 0U) {
        lpuart_clear_overrun_flag();
        lpuart_error_record_isr(LPUART_ERR_OVERRUN);
    }

    if ((status & LPUART_STATUS_FE) != 0U) {
        lpuart_clear_frame_error_flag();
        lpuart_error_record_isr(LPUART_ERR_FRAME);
    }
}
```

### DMA 缓冲设计注意事项

- DMA 写入缓冲区必须位于 DMA 可访问内存；
- 带 Cache 的 Cortex-M7/M33 系统需要处理 Cache 一致性；
- 缓冲区起始地址和长度应满足 Cache Line 对齐要求；
- ISR 与任务共享读写索引时需要内存屏障；
- 不应在任务中直接修改 DMA 正在写入的区域。

## 5.7 接收环形缓冲

```
typedef struct {
    uint8_t *buffer;
    uint32_t size;
    volatile uint32_t read_pos;
    volatile uint32_t write_pos;
} byte_ring_t;

static uint32_t ring_available(const byte_ring_t *ring)
{
    if (ring == NULL || ring->size == 0U) {
        return 0U;
    }

    uint32_t w = ring->write_pos;
    uint32_t r = ring->read_pos;

    return (w >= r) ? (w - r)
                    : (ring->size - r + w);
}

bool ring_read(byte_ring_t *ring, uint8_t *data, uint32_t len)
{
    if (ring == NULL || data == NULL ||
        len == 0U || ring_available(ring) < len) {
        return false;
    }

    for (uint32_t i = 0U; i < len; ++i) {
        data[i] = ring->buffer[ring->read_pos];
        ring->read_pos =
            (ring->read_pos + 1U) % ring->size;
    }

    return true;
}
```

生产代码还应明确：

- 满缓冲处理策略：覆盖旧数据、丢弃新数据或触发故障；
- 是否需要无锁单生产者单消费者模型；
- 读取过程中是否允许 DMA 更新；
- 是否支持零拷贝；
- 数据帧最大长度和超时策略。

## 5.8 LPUART 发送与低功耗

发送期间不能直接进入 Stop，否则可能截断尾字节。

```
bool lpuart_wait_tx_complete(uint32_t timeout_ms)
{
    uint32_t start = os_time_ms();

    while (!lpuart_tx_complete_flag()) {
        if ((os_time_ms() - start) >= timeout_ms) {
            return false;
        }

        /*
         * 允许任务切换，但不能在此期间关闭 LPUART 时钟。
         */
        os_thread_yield();
    }

    return true;
}
```

对于 RS-485：

```
bool rs485_send_frame(const uint8_t *data, uint32_t len)
{
    if (data == NULL || len == 0U) {
        return false;
    }

    rs485_set_de(true);
    delay_us(RS485_TURNAROUND_US);

    if (!lpuart_dma_tx_start(data, len)) {
        rs485_set_de(false);
        return false;
    }

    if (!lpuart_wait_tx_complete(100U)) {
        lpuart_abort_tx();
        rs485_set_de(false);
        return false;
    }

    /*
     * 必须等待移位寄存器完成，而非仅等待 TXE。
     */
    rs485_set_de(false);
    return true;
}
```

**TXE 只表示发送数据寄存器为空，不代表最后一个停止位已经发完。** RS-485 的 DE 必须在 TC 后关闭，否则最后一个字节可能被截断。

## 5.9 LPUART 低功耗进入与恢复

### 进入前

```
typedef enum {
    LPUART_PM_OK = 0,
    LPUART_PM_BUSY,
    LPUART_PM_ERROR,
} lpuart_pm_status_t;

lpuart_pm_status_t lpuart_prepare_stop(void)
{
    if (lpuart_tx_busy() || dma_tx_busy()) {
        return LPUART_PM_BUSY;
    }

    if (lpuart_rx_frame_in_progress()) {
        /*
         * 根据协议选择等待、丢弃半帧或保存上下文。
         */
        lpuart_abort_partial_frame();
    }

    lpuart_clear_error_flags();
    lpuart_clear_idle_flag();

    /*
     * 保持 LPUART、低功耗内核时钟和唤醒逻辑。
     */
    if (!rcc_lpuart_clock_retained_in_stop()) {
        return LPUART_PM_ERROR;
    }

    lpuart_enable_wakeup();
    pwr_enable_lpuart_wakeup();

    return LPUART_PM_OK;
}
```

### 唤醒后

```
bool lpuart_resume_after_stop(void)
{
    /*
     * 如果 LPUART 内核时钟发生改变，需要重新配置波特率。
     */
    if (!lpuart_kernel_clock_is_valid()) {
        if (!lpuart_reconfigure_clock()) {
            return false;
        }
    }

    lpuart_clear_stale_flags();
    lpuart_recover_rx_state();
    lpuart_restart_dma_if_needed();

    return true;
}
```

应验证：

- LPUART 寄存器是否保持；
- BRR 是否保持；
- 接收器是否继续运行；
- FIFO 中是否保留唤醒前后数据；
- DMA 是否在 Stop 中继续工作；
- 唤醒后第一个字节是否可读；
- 低功耗模式退出后是否需要重新开启外设时钟。

## 5.10 错误状态处理

常见错误标志：

|标志|含义|典型原因|
|---|---|---|
|ORE|Overrun|CPU/DMA 未及时读取|
|FE|Frame Error|波特率错误、噪声、线路异常|
|NE|Noise Error|EMI、线缆、接地问题|
|PE|Parity Error|数据格式不一致|
|IDLE|总线空闲|一帧结束或接收间隔|
|WUF|Wakeup Flag|触发唤醒事件|
|TC|Transmission Complete|移位寄存器发送完成|

错误恢复框架：

```
typedef struct {
    uint32_t overrun_count;
    uint32_t frame_error_count;
    uint32_t noise_error_count;
    uint32_t parity_error_count;
    uint32_t wakeup_count;
    uint32_t reset_count;
} lpuart_diag_t;

static lpuart_diag_t g_lpuart_diag;

void lpuart_error_recovery(uint32_t status)
{
    if ((status & LPUART_STATUS_ORE) != 0U) {
        g_lpuart_diag.overrun_count++;
        lpuart_flush_rx_fifo();
        lpuart_dma_resync();
    }

    if ((status & LPUART_STATUS_FE) != 0U) {
        g_lpuart_diag.frame_error_count++;
        protocol_resynchronize();
    }

    if ((status & LPUART_STATUS_NE) != 0U) {
        g_lpuart_diag.noise_error_count++;
    }

    if ((status & LPUART_STATUS_PE) != 0U) {
        g_lpuart_diag.parity_error_count++;
        protocol_drop_current_frame();
    }
}
```

---

## 6. 性能量化分析

## 6.1 示例测试平台

- MCU：Cortex-M4；
- LPUART 时钟：LSE 32.768 kHz；
- 备用高频时钟：HSI16；
- 波特率：2400、9600、19200 bit/s；
- Stop：SRAM 保持；
- DMA：环形接收；
- 温度：25 ℃；
- 测试仪器：200 MHz 示波器、逻辑分析仪、功耗分析仪。

|项目|示例测量值|
|---|---|
|LPUART Stop 保持电流|约 1.2~3.5 μA|
|起始位到 CPU 唤醒|20~80 μs|
|唤醒到 ISR 入口|35~100 μs|
|Stop 唤醒后时钟恢复|60~120 μs|
|DMA 环形接收 ISR 压力|低|
|单字节中断接收 CPU 占用|中~高|
|2400 bit/s 单字节时间|4.167 ms|
|9600 bit/s 单字节时间|1.042 ms|
|115200 bit/s 单字节时间|86.8 μs|

以 8N1 为例：

Tbyte=10baudrateTbyte​=baudrate10​

在 9600 bit/s 时：

Tbyte=109600=1.0417msTbyte​=960010​=1.0417ms

如果 MCU 唤醒、恢复时钟和进入任务的最坏延迟为 1.5 ms，则**无法保证捕获唤醒后的下一个字节**，协议必须增加前导码或硬件 FIFO。

## 6.2 波特率误差

目标波特率为 BtBt​，实际波特率为 BaBa​：

ϵbaud=Ba−BtBt×100%ϵbaud​=Bt​Ba​−Bt​​×100%

例如目标 9600 bit/s，实际 9580 bit/s：

ϵbaud=9580−96009600≈−0.208%ϵbaud​=96009580−9600​≈−0.208%

单端设备误差可能尚可接受，但通信链路应使用两端误差之和：

ϵlink≈∣ϵtx∣+∣ϵrx∣ϵlink​≈∣ϵtx​∣+∣ϵrx​∣

还要考虑：

- LSI 温漂；
- 电源电压；
- 芯片批次；
- 线缆和收发器延迟；
- 过采样倍数；
- 帧长度。

## 6.3 接收缓冲容量

若 CPU 最长不可服务时间为 TblockTblock​，波特率为 BB，每字节包含 NbitsNbits​ 位，则所需最小缓冲容量：

Cmin≥⌈B×TblockNbits⌉Cmin​≥⌈Nbits​B×Tblock​​⌉

例如：

- 波特率：115200；
- 8N1：10 bit/byte；
- 最长不可服务时间：5 ms。

Cmin≥⌈115200×0.00510⌉=58 bytesCmin​≥⌈10115200×0.005​⌉=58 bytes

工程上应考虑安全系数 2~~4 倍，建议至少 128~~256 bytes。

## 6.4 功耗模型

LPUART 低功耗通信周期平均电流可近似为：

Iavg=IrunTrun+IlpuartTlisten+IwakeTwake+ItransceiverTbusTcycleIavg​=Tcycle​Irun​Trun​+Ilpuart​Tlisten​+Iwake​Twake​+Itransceiver​Tbus​​

若总线空闲时间很长，LPUART 监听电流和 RS-485 收发器待机电流决定待机功耗；若数据突发频繁，则唤醒和协议处理能耗成为主导项。

### 示例

假设：

- LPUART 监听：3 μA；
- Stop 监听：900 ms；
- CPU 活动：8 mA，20 ms；
- RS-485 接收器待机：10 μA；
- 周期：1 s。

Iavg≈3μA×0.9+8mA×0.02+10μA×1Iavg​≈3μA×0.9+8mA×0.02+10μA×1Iavg≈173.7μAIavg​≈173.7μA

若把 CPU 活动时间从 20 ms 降至 5 ms：

Iavg≈53.7μAIavg​≈53.7μA

收益远大于把 LPUART 本身从 3 μA 优化至 1 μA。

## 6.5 主要瓶颈和优化手段

|瓶颈|表现|优化|
|---|---|---|
|LSI 误差大|乱码、帧错误|LSE、校准或降低波特率|
|首字节丢失|帧头不完整|前导码、同步字、硬件 FIFO|
|逐字节中断|CPU 活动时间长|DMA + IDLE|
|收发器待机电流高|Stop 功耗仍较大|Shutdown、低 IQ 型号|
|RS-485 偏置电阻|总线空闲持续耗电|优化终端和偏置拓扑|
|Stop 中时钟未保持|无法唤醒|使用支持保持的时钟源|
|RX 线浮空|随机唤醒|外部上拉、收发器状态管理|
|频繁唤醒|平均功耗高|地址过滤、帧聚合、批量处理|

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否需要 CPU 处于 Stop 时监听串口？
├─ 否
│  ├─ 高速或复杂通信 → 普通 UART + DMA
│  └─ 低速简单通信 → LPUART 也可使用
└─ 是
   ├─ 波特率是否在低功耗时钟可支持范围内？
   │  ├─ 否 → 选择更高频保持时钟或普通 UART
   │  └─ 是
   ├─ 是否允许丢失第一个字节？
   │  ├─ 是 → 起始位唤醒
   │  └─ 否 → 前导码/FIFO/地址匹配/主站延迟
   ├─ 是否为多从机总线？
   │  ├─ 是 → 地址匹配唤醒
   │  └─ 否 → 起始位或字符匹配唤醒
   ├─ 数据是否连续或突发？
   │  ├─ 是 → DMA + IDLE + 环形缓冲
   │  └─ 否 → 中断接收
   └─ 是否需要 RS-485 半双工？
      ├─ 是 → DE/RE + TC + 收发器 Shutdown
      └─ 否 → 单端 UART/LPUART
```

### 7.2 典型场景

|场景|推荐方案|理由|
|---|---|---|
|电池传感器串口配置|LPUART + Stop + 起始位唤醒|低功耗和低速配置通信|
|RS-485 低功耗从站|LPUART + 地址匹配 + DMA|减少无关唤醒和 CPU 负载|
|GNSS 周期唤醒|LPUART + RTC + DMA|GNSS 模块按周期上电和接收|
|Modbus RTU 从站|LPUART + DMA + IDLE/LPTIM 超时|支持帧间隔判断|
|高速日志输出|普通 UART + DMA|LPUART 低速时钟可能不适合|
|电机控制通信|普通 UART/高速外设|实时性、波特率和确定性优先|
|低功耗调试接口|LPUART + 唤醒命令|允许远程唤醒和诊断|
|LIN 低功耗节点|LPUART + Break 唤醒|低速总线和节点唤醒适配|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **先确认目标 LPUART 实例在目标低功耗模式中是否支持接收和唤醒。**
2. 时钟源必须同时满足低功耗保持、波特率误差和温漂要求。
3. 协议必须允许唤醒延迟，不能假设 CPU 能在 Start Bit 后立即执行应用代码。
4. 起始位唤醒场景优先设计前导码和同步帧。
5. 长报文使用 DMA + 环形缓冲 + IDLE/超时检测。
6. ISR 只做状态确认、快照和事件投递。
7. RS-485 必须使用 TC 而不是 TXE 判断发送完成。
8. 进入低功耗前必须完成 TX、DMA 和半双工方向控制。
9. 记录 ORE、FE、NE、PE、WUF 和重同步次数。
10. 低功耗通信故障必须有重试上限和安全降级路径。

## 8.2 选型决策矩阵

|指标|普通 UART|LPUART 起始位唤醒|LPUART 地址唤醒|LPUART + DMA|
|---|---|---|---|---|
|最低功耗|2|5|5|4|
|高速能力|5|2~3|2~3|4|
|首字节可靠性|5|2|3~4|4|
|多从机适配|3|2|5|5|
|CPU 占用|3|3|4|5|
|实现复杂度|4|3|2~3|2|
|协议改造需求|2|4|4|3|

## 8.3 工业级编码规范

- LPUART 驱动分为：
    - 时钟管理；
    - 波特率配置；
    - 唤醒配置；
    - 接收路径；
    - 发送路径；
    - DMA 管理；
    - 错误恢复；
    - 诊断统计。
- 禁止业务层直接清除 UART 状态寄存器。
- 所有接收帧必须带长度边界和超时保护。
- 接收缓冲溢出必须可观测，不允许静默覆盖。
- 所有波特率配置经过整数运算和范围检查。
- 进入 Stop 前保存 DMA 写指针、协议状态和半帧信息。
- 退出 Stop 后执行时钟、DMA、FIFO、错误标志和协议状态检查。
- 低功耗模式下禁止使用依赖主时钟的忙等待延时。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：LPUART 使用了 Stop 中关闭的时钟

**错误代码：**

```
rcc_select_lpuart_clock(APB1_CLOCK);
lpuart_enable();
enter_stop();
```

**根因：** APB 时钟在 Stop 中关闭，LPUART 无法继续采样 RX。

**正确实现：**

```
rcc_select_lpuart_clock(LSE_CLOCK);

if (!rcc_clock_retained_in_stop(LSE_CLOCK)) {
    return LPUART_PM_ERROR;
}

lpuart_set_baudrate_from_kernel_clock(32768U, 2400U);
lpuart_enable_wakeup();
```

**风险影响：**

- Stop 中无法接收；
- 唤醒事件丢失；
- 总线主站认为从站离线。

### 9.2 错误二：假设起始位唤醒后首字节一定完整

**错误代码：**

```
void lpuart_wakeup_handler(void)
{
    uint8_t first = lpuart_read_rdr();
    protocol_parse(first);
}
```

**根因：** 起始位唤醒可能消耗首字节，或唤醒时钟恢复晚于数据采样时刻。

**正确实现：**

```
主站发送：
0x55 0x55 0xA5 ADDRESS LENGTH PAYLOAD CRC16

从站：
唤醒 → 丢弃/识别前导码 → 等待 A5 → 接收完整帧
```

**风险影响：**

- 首帧偶发丢失；
- 协议状态机失步；
- 现场出现难以复现的通信异常。

### 9.3 错误三：使用 LSI 却假设波特率精确

**错误代码：**

```
lpuart_set_clock(LSI);
lpuart_set_baudrate(9600U);
```

**根因：** LSI 频率受温度、电压和芯片批次影响较大，实际频率可能偏离标称值。

**正确实现：**

- 使用 LSE；
- 或启动时测量 LSI 实际频率；
- 或降低波特率并验证两端误差；
- 或使用自动波特率检测。

**风险影响：**

- 高温或低温下乱码；
- 长帧 CRC 失败；
- 不同批次设备通信表现不一致。

### 9.4 错误四：用 TXE 判断 RS-485 发送完成

**错误代码：**

```
lpuart_send(data, len);

while (!lpuart_txe_flag()) {
}

rs485_set_de(false);
```

**根因：** TXE 只表示发送数据寄存器为空，最后一个字节可能仍在移位寄存器中发送。

**正确实现：**

```
while (!lpuart_tc_flag()) {
    if (timeout_expired()) {
        lpuart_abort_tx();
        rs485_set_de(false);
        return false;
    }
}

rs485_set_de(false);
return true;
```

**风险影响：**

- 最后一个字节被截断；
- CRC 错误；
- Modbus/RS-485 帧偶发失败。

### 9.5 错误五：DMA 环形缓冲未处理 Cache 一致性

**错误代码：**

```
dma_start_rx(rx_buffer, sizeof(rx_buffer));
/* CPU 直接读取缓存 */
parse_frame(rx_buffer);
```

**根因：** Cortex-M7/M33 Cache 可能读取旧数据，DMA 写入内存未及时反映到 CPU Cache。

**正确实现：**

```
void lpuart_dma_rx_commit(uint32_t pos)
{
    dcache_invalidate_by_addr(
        &g_lpuart_rx_dma[0],
        LPUART_RX_DMA_SIZE);

    __DMB();
    rx_ring_update_write_position(pos);
}
```

实际应按芯片 Cache Line 对齐规则实现，并避免 CPU 与 DMA 同时写同一 Cache Line。

**风险影响：**

- 收到旧数据；
- 帧长度异常；
- 间歇性 CRC 错误。

### 9.6 错误六：RX 线浮空导致伪唤醒

**错误代码：**

```
gpio_config_input(LPUART_RX_PIN);
lpuart_enable_wakeup();
enter_stop();
```

**根因：** 收发器关闭或断开时，RX 没有稳定的空闲高电平。

**正确实现：**

- 按物理层定义配置上拉；
- 收发器 Shutdown 时保证 RO 输出状态确定；
- 必要时使用外部上拉；
- 对唤醒脉冲增加数字滤波或协议验证。

**风险影响：**

- 系统随机唤醒；
- 平均电流升高；
- CPU 反复恢复和再次睡眠。

### 9.7 错误七：唤醒后未重新配置 DMA

**错误代码：**

```
enter_stop();
lpuart_resume_clock();
protocol_receive();
```

**根因：** Stop 期间 DMA 通道、请求源或内存指针状态可能丢失或暂停。

**正确实现：**

```
bool lpuart_resume(void)
{
    if (!lpuart_resume_clock()) {
        return false;
    }

    lpuart_clear_stale_flags();
    dma_disable(LPUART_RX_DMA_CHANNEL);
    dma_reconfigure_rx_buffer();
    dma_enable(LPUART_RX_DMA_CHANNEL);
    lpuart_enable_dma_rx();

    return true;
}
```

**风险影响：**

- 唤醒后只有第一帧正常；
- 后续帧丢失；
- DMA 指针回退或缓冲区覆盖。

---

## 10. 多机制组合使用方案

## 10.1 系统架构

```
Low-Power Serial Manager
├── LPUART Clock Manager
│   ├── LSE/LSI/HSI
│   └── Clock Retention Check
├── Wakeup Manager
│   ├── Start Bit Wakeup
│   ├── Address Match
│   └── Character Match
├── RX Path
│   ├── FIFO
│   ├── DMA Circular Buffer
│   ├── IDLE Detection
│   └── Frame Timeout
├── TX Path
│   ├── DMA TX
│   ├── TC Detection
│   └── RS-485 DE Control
├── Protocol Layer
│   ├── Preamble
│   ├── Address
│   ├── Length
│   ├── CRC
│   └── Retry/Resync
├── Power Manager
│   ├── Sleep
│   ├── Stop
│   └── Standby
└── Diagnostics
    ├── Error Counters
    ├── Wakeup Counters
    └── Power Waveform Markers
```

## 10.2 低功耗串口协议框架

推荐帧格式：

```
PREAMBLE | SYNC | ADDRESS | TYPE | LENGTH | PAYLOAD | CRC16
```

例如：

```
0x55 0x55 0xA5 0x12 0x01 0x04 DATA0 DATA1 DATA2 DATA3 CRC_L CRC_H
```

字段作用：

|字段|作用|
|---|---|
|PREAMBLE|给 LPUART 和接收端提供唤醒/同步时间|
|SYNC|确认帧边界|
|ADDRESS|多从机过滤|
|TYPE|消息类型|
|LENGTH|边界检查|
|PAYLOAD|业务数据|
|CRC16|错误检测|

## 10.3 完整接收状态机

```
typedef enum {
    RX_WAIT_PREAMBLE,
    RX_WAIT_SYNC,
    RX_WAIT_ADDRESS,
    RX_WAIT_TYPE,
    RX_WAIT_LENGTH,
    RX_WAIT_PAYLOAD,
    RX_WAIT_CRC,
    RX_FRAME_READY,
    RX_ERROR,
} rx_state_t;

typedef struct {
    rx_state_t state;
    uint8_t address;
    uint8_t type;
    uint16_t expected_len;
    uint16_t received_len;
    uint8_t frame_buf[256];
    uint16_t crc;
    uint32_t last_byte_time_ms;
} lpuart_protocol_t;

static lpuart_protocol_t g_protocol;

void lpuart_protocol_reset(void)
{
    g_protocol.state = RX_WAIT_PREAMBLE;
    g_protocol.expected_len = 0U;
    g_protocol.received_len = 0U;
    g_protocol.crc = CRC16_INIT;
}

bool lpuart_protocol_input(uint8_t byte)
{
    uint32_t now = os_time_ms();

    if ((now - g_protocol.last_byte_time_ms) >
        LPUART_FRAME_TIMEOUT_MS) {
        lpuart_protocol_reset();
    }

    g_protocol.last_byte_time_ms = now;

    switch (g_protocol.state) {
    case RX_WAIT_PREAMBLE:
        if (byte == 0x55U) {
            g_protocol.state = RX_WAIT_SYNC;
        }
        break;

    case RX_WAIT_SYNC:
        if (byte == 0xA5U) {
            g_protocol.state = RX_WAIT_ADDRESS;
        } else if (byte != 0x55U) {
            lpuart_protocol_reset();
        }
        break;

    case RX_WAIT_ADDRESS:
        if (byte != DEVICE_ADDRESS &&
            byte != BROADCAST_ADDRESS) {
            lpuart_protocol_reset();
            break;
        }
        g_protocol.address = byte;
        g_protocol.state = RX_WAIT_TYPE;
        break;

    case RX_WAIT_TYPE:
        g_protocol.type = byte;
        g_protocol.state = RX_WAIT_LENGTH;
        break;

    case RX_WAIT_LENGTH:
        g_protocol.expected_len = byte;

        if (g_protocol.expected_len >
            sizeof(g_protocol.frame_buf)) {
            g_protocol.state = RX_ERROR;
            break;
        }

        g_protocol.received_len = 0U;
        g_protocol.state = (g_protocol.expected_len == 0U)
                               ? RX_WAIT_CRC
                               : RX_WAIT_PAYLOAD;
        break;

    case RX_WAIT_PAYLOAD:
        g_protocol.frame_buf[g_protocol.received_len++] = byte;

        if (g_protocol.received_len >=
            g_protocol.expected_len) {
            g_protocol.state = RX_WAIT_CRC;
        }
        break;

    case RX_WAIT_CRC:
        /*
         * 实际实现应接收两个 CRC 字节并比较。
         */
        g_protocol.state = RX_FRAME_READY;
        return protocol_verify_and_dispatch();

    default:
        lpuart_protocol_reset();
        break;
    }

    return true;
}
```

实际项目中应将协议解析与 DMA 环形缓冲分离，协议层不应直接操作 DMA 寄存器。

## 10.4 LPUART 与 RTOS 协同

```
LPUART ISR/DMA
    ↓
提交 DMA 写指针
    ↓
发送轻量事件到 RX 任务
    ↓
RX 任务解析协议
    ↓
命中业务命令
    ↓
唤醒高优先级任务
    ↓
处理完成后重新进入 Stop
```

RTOS 设计要点：

- ISR 使用 `xQueueSendFromISR()` 或等价 API；
- 不在 ISR 中执行 CRC、Flash 写入和复杂协议解析；
- 接收任务设置明确优先级；
- 空闲时采用 Tickless；
- LPUART 唤醒后根据缓冲数据量决定是否继续保持 Run；
- 任务处理完毕后再判断是否可以重新进入 Stop。

---

## 11. 工业级实际案例分析

## 11.1 案例一：低功耗 RS-485 Modbus 从站

### 需求

- 总线空闲时 MCU 进入 Stop；
- 主站发送地址后从站唤醒；
- 支持 Modbus RTU；
- 不响应其他从站地址；
- 帧处理时间小于 2 ms；
- 待机电流小于 50 μA。

### 架构

```
RS-485 总线
    ↓
低功耗收发器
    ↓
LPUART 地址/起始位唤醒
    ↓
DMA 环形接收
    ↓
IDLE + LPTIM 帧超时
    ↓
地址过滤 + CRC16
    ↓
业务处理
    ↓
LPUART TX + RS-485 DE/TC
    ↓
Stop
```

### 设计要点

- 主站帧前增加唤醒前导时间；
- LPUART 使用 LSE 或经校准的低功耗时钟；
- 地址匹配减少无关从机唤醒；
- DMA 接收避免每字节 ISR；
- LPTIM 判断 Modbus 帧间隔；
- RS-485 DE 在 TC 后关闭；
- 收发器 Shutdown 脚和 RO 输出电平必须明确。

### 风险控制

- 总线噪声导致 Start Bit 伪唤醒：使用前导码和 CRC；
- 低功耗收发器误反灌：检查 RO、DI、DE/RE 电平；
- 长帧期间 DMA 缓冲溢出：按最大不可服务时间计算缓冲；
- Stop 唤醒过慢：增加前导码或提高保持时钟频率。

## 11.2 案例二：电池传感器配置接口

### 需求

- 设备平时处于 Stop；
- 通过 LPUART 接收现场配置指令；
- 低功耗时不允许持续运行主时钟；
- 指令错误不能破坏原有配置。

### 方案

```
LPUART 起始位唤醒
    ↓
接收同步帧和配置命令
    ↓
CRC + 版本 + 参数范围校验
    ↓
写入临时配置区
    ↓
双槽位提交
    ↓
应答
    ↓
重新进入 Stop
```

### 配置数据结构

```
typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t length;
    uint32_t sample_period_s;
    uint32_t report_period_s;
    uint32_t sequence;
    uint32_t crc;
} device_config_t;

bool config_validate(const device_config_t *cfg)
{
    if (cfg == NULL ||
        cfg->magic != CONFIG_MAGIC ||
        cfg->version == 0U ||
        cfg->length != sizeof(device_config_t)) {
        return false;
    }

    if (cfg->sample_period_s < 1U ||
        cfg->sample_period_s > 86400U) {
        return false;
    }

    if (cfg->report_period_s <
        cfg->sample_period_s) {
        return false;
    }

    return cfg->crc ==
           crc32(cfg, offsetof(device_config_t, crc));
}
```

### 设计要点

- 配置参数必须进行范围和关系校验；
- 写 Flash 前先写备用槽位；
- 电源中断或复位时保留旧配置；
- 应答只有在持久化成功后发送；
- 指令处理完成后关闭 LPUART 接收和外部收发器。

## 11.3 案例三：低功耗 GNSS 接收终端

### 需求

- 每 10 分钟唤醒 GNSS 模块；
- LPUART 接收 NMEA/二进制定位数据；
- 定位结束后关闭 GNSS；
- 设备大部分时间处于 Stop 或 Standby。

### 架构

```
RTC/LPTIM 唤醒 MCU
    ↓
打开 GNSS 电源
    ↓
LPUART 初始化 + DMA
    ↓
等待定位数据
    ↓
解析 GGA/RMC 或二进制帧
    ↓
超时则关闭 GNSS
    ↓
保存定位结果
    ↓
Stop/Standby
```

### 设计要点

- GNSS 电源启动时间不应由固定延时盲等，优先使用模块 Ready 信号；
- LPUART 接收使用 DMA + IDLE；
- GNSS 无响应必须有硬件和软件超时；
- 关闭 GNSS 前确保 TX 完成并将 RX 设置为安全电平；
- 定位失败不能无限重试，否则功耗可能失控。

---

## 12. 高频问题深度答疑

### 问题一：LPUART 的低功耗优势主要来自哪里？

主要来自两个方面：

1. 使用低功耗时钟域，在 Stop 中仍可保持接收和唤醒；
2. 唤醒前不需要保持 CPU 主时钟和完整外设时钟树。

但 LPUART 并不会自动降低外部收发器、传感器或电源芯片功耗。整机功耗必须单独核算。

### 问题二：LPUART 能否在 Stop 中持续接收完整数据帧？

取决于具体 MCU：

- 有些器件只支持检测 Start Bit，然后唤醒 CPU；
- 有些器件具有 FIFO，可在唤醒期间缓存部分数据；
- 有些支持地址匹配后再唤醒；
- 有些 DMA 通道在 Stop 中无法运行。

因此必须确认：

- Stop 中接收器是否工作；
- RXNE/FIFO 是否保持；
- DMA 是否继续搬运；
- 首字节是否能保存；
- 数据帧速度是否超过缓冲和唤醒能力。

### 问题三：为什么 LPUART 用 LSE 时只能支持较低波特率？

LSE 频率只有 32.768 kHz，波特率分频器需要使用整数或有限精度的分频值。对于高波特率，分频值过小，量化误差会显著增加，且接收采样时钟分辨率不足。

解决方案：

- 使用更高频的保持时钟；
- 降低波特率；
- 使用硬件自动波特率检测；
- 重新评估通信帧格式和时序裕量。

### 问题四：LPUART 起始位唤醒为什么容易丢首字节？

起始位到数据位之间只有约一个 bit 时间：

Tbit=1baudrateTbit​=baudrate1​

在 9600 bit/s 时约为 104 μs，在 115200 bit/s 时仅约为 8.68 μs。CPU 唤醒、时钟恢复和接收路径初始化很可能超过这个时间，因此首字节无法完整接收。

工程解决方案：

- 增加前导码；
- 使用地址匹配或字符匹配；
- 使用硬件 FIFO；
- 提高保持时钟频率；
- 让发送端等待唤醒确认；
- 使用可靠重传。

### 问题五：LPUART 进入 Stop 前是否需要关闭接收器？

如果需要在 Stop 中监听总线，不能关闭接收器。应关闭的是不必要的发送路径、DMA 事务和其他外设，并保持：

- LPUART 内核时钟；
- RX 输入；
- 唤醒逻辑；
- 必要的 PWR 连接；
- 外部收发器接收输出。

如果不需要监听，则应关闭 LPUART 和收发器，以获得更低功耗。

### 问题六：LPUART 和普通 UART 能否共享时钟源？

可能可以，但需要确认 RCC 复用矩阵和外设时钟切换影响。共享时钟可能导致：

- 普通 UART 和 LPUART 不能独立调频；
- Stop 保持策略受限；
- 某个外设切换时钟影响另一个外设。

工业系统中，若两个串口的低功耗和实时性需求不同，优先使用独立内核时钟配置。

### 问题七：LPUART 接收为什么会出现 ORE？

常见原因：

- CPU 唤醒太慢；
- 接收波特率过高；
- FIFO 未启用；
- DMA 未正常运行；
- ISR 优先级过低；
- Stop 恢复后 DMA 指针未重建；
- Cache 未失效；
- 主循环长时间关闭中断。

应通过错误计数、DMA 写指针和波形打点定位，而不是简单清除 ORE 后继续运行。

### 问题八：RS-485 收发器的待机电流为什么会抵消 LPUART 的低功耗收益？

很多 RS-485 收发器即使 MCU 进入 Stop，仍会消耗几十微安到数毫安。若收发器不支持低功耗 Shutdown，或 DE/RE 电平配置错误，系统待机电流将由它主导。

必须同时检查：

- 收发器 VCC；
- Shutdown/Enable；
- DE/RE；
- RO 输出；
- A/B 终端和偏置电阻；
- MCU GPIO 反向供电路径。

---

## 13. 课程核心总结

### 核心要点

1. **LPUART 的核心价值是在低功耗时钟域中保持串口接收和唤醒能力。**
2. LPUART 不是普通 UART 的简单低功耗替代品，必须重新验证时钟、波特率和 Stop 行为。
3. 起始位唤醒存在首字节丢失风险，协议必须提供前导码、同步字或地址匹配。
4. 低速时钟的频率精度决定波特率可靠性，LSI 需要校准或放宽容差。
5. 长数据接收优先使用 DMA、FIFO、IDLE 和环形缓冲。
6. RS-485 必须等待 TC，再关闭 DE。
7. LPUART 的功耗收益不能脱离外部收发器、电源域和 PCB 漏电单独评价。
8. Stop 唤醒后要验证时钟、DMA、FIFO、错误标志和协议状态。
9. 低功耗串口必须具备错误统计、帧超时、重同步、重试上限和安全降级。
10. **低功耗通信的最终目标不是“串口能唤醒”，而是数据不丢、协议不失步、功耗可控、故障可恢复。**

### 性能排序

典型低功耗监听功耗从低到高：

```
LPUART + LSE + Stop
    < LPUART + HSI/中频时钟 + Stop
    < 普通 UART + Sleep
    < 普通 UART + Run 轮询
```

典型接收性能从高到低：

```
普通高速 UART + DMA
    > LPUART + 高频保持时钟 + DMA
    > LPUART + LSE
    > 软件 Bit-bang
```

首字节可靠性从高到低通常为：

```
硬件 FIFO/预留前导码
    > 地址/字符匹配
    > 起始位唤醒
    > 无协议补偿的直接解析
```

### 通用选型结论

- **Stop 中低速监听：LPUART + LSE/低功耗时钟**；
- **多从机总线：地址匹配唤醒 + DMA**；
- **高可靠长帧：DMA + IDLE + 超时 + CRC**；
- **RS-485 半双工：LPUART + TC + DE 控制**；
- **高波特率和严格实时：普通 UART/高速串口**；
- **协议不允许丢首字节：前导码、硬件 FIFO 或握手机制必须存在**。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选方案|关键检查|
|---|---|---|
|Stop 中串口唤醒|LPUART + Start Bit|时钟保持、首字节策略|
|多从机总线|LPUART + Address Match|地址过滤、协议格式|
|长帧接收|LPUART + DMA + IDLE|DMA 缓冲、Cache 一致性|
|Modbus RTU|LPUART + DMA + IDLE + LPTIM|帧间超时、CRC|
|RS-485 发送|LPUART + DMA + TC + DE|最后停止位完成|
|低速传感器|LPUART + LSE|波特率误差、功耗|
|高速日志|普通 UART + DMA|高速时钟、带宽|
|低功耗 GNSS|RTC/LPTIM + LPUART DMA|模块电源和接收超时|

### 14.2 唤醒模式对比

|模式|首字节风险|多从机适配|CPU 唤醒次数|协议要求|
|---|---|---|---|---|
|Start Bit|高|一般|高|前导码/重同步|
|Address Match|中|高|低|固定地址字段|
|Character Match|中|中~高|低|固定同步字符|
|FIFO/持续接收|低|高|低|FIFO/DMA 支持|

### 14.3 关键状态标志表

|标志|处理方式|
|---|---|
|RXNE|读取 RDR 或由 DMA 搬运|
|IDLE|清标志并提交当前 DMA 数据|
|ORE|记录、清除、重同步接收路径|
|FE|丢弃当前帧并重新找同步字|
|NE|记录线路噪声并评估物理层|
|PE|丢帧或请求重传|
|WUF|记录唤醒原因|
|TXE|数据寄存器可继续写入|
|TC|移位寄存器和最后停止位完成|

### 14.4 LPUART 配置检查清单

```
[ ] LPUART 实例支持目标低功耗模式
[ ] 内核时钟在 Stop 中保持
[ ] 时钟源精度满足波特率误差预算
[ ] BRR 使用目标芯片专用公式
[ ] 数据位、停止位、校验位两端一致
[ ] 起始位/地址/字符唤醒模式已确认
[ ] 首字节丢失有协议补偿
[ ] RX 线有确定空闲电平
[ ] DMA 缓冲区位于可访问内存
[ ] Cache 一致性策略已实现
[ ] IDLE/超时可判定帧结束
[ ] RX 缓冲溢出可检测
[ ] TX 使用 TC 判断完整发送
[ ] RS-485 DE/RE 时序已验证
[ ] Stop 前 TX/DMA 状态已确认
[ ] 唤醒后时钟、DMA、FIFO 已恢复
[ ] ORE/FE/NE/PE/WUF 有统计和恢复策略
[ ] 外部收发器待机电流已测量
[ ] 波特率、功耗和唤醒延迟已在温度/电压范围内验证
```

---

## 15. 学习效果自检

- [ ]  能解释 LPUART 与普通 UART 的时钟和低功耗差异。
- [ ]  能确认某个 LPUART 时钟源是否在 Stop 中保持。
- [ ]  能根据目标时钟计算实际波特率和误差。
- [ ]  能说明为什么起始位唤醒可能丢失首字节。
- [ ]  能为低功耗串口设计前导码和同步机制。
- [ ]  能配置 GPIO、LPUART、EXTI、PWR 和 NVIC 的唤醒链路。
- [ ]  能实现 DMA 环形接收和 IDLE 帧结束检测。
- [ ]  能计算指定波特率和不可服务时间下的最小接收缓冲区。
- [ ]  能区分 TXE 和 TC，并正确控制 RS-485 DE。
- [ ]  能处理 ORE、FE、NE、PE 和接收超时。
- [ ]  能设计 LPUART Stop 前后的挂起和恢复流程。
- [ ]  能分析 Cache/DMA 一致性问题。
- [ ]  能统计伪唤醒、丢帧、重同步和重试次数。
- [ ]  能判断 LPUART 的低功耗收益是否被外部收发器功耗抵消。
- [ ]  能使用波形验证首字节、唤醒延迟、DMA 接收和低功耗电流。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：LPUART 基础通信

- 使用 LSE 或低功耗内部时钟；
- 配置 2400、9600 bit/s；
- 测量实际波特率和误差；
- 验证不同温度、电压下的通信稳定性。

验收：输出实际波特率、误差 ppm 和连续帧 CRC 统计。

#### 任务二：起始位唤醒

- MCU 进入 Stop；
- 外部串口发送前导码和数据帧；
- 记录 Start Bit 到 ISR、任务和首个有效字节的时间；
- 验证首字节丢失场景。

验收：协议能够重新同步，首帧不因唤醒延迟导致永久失步。

#### 任务三：DMA + IDLE 接收

- 配置环形 DMA；
- 使用 IDLE 判断一帧结束；
- 处理半帧、连续帧和缓冲区绕回；
- 注入 Cache 不一致和 DMA 指针异常。

验收：在最大波特率和最坏任务阻塞时间下不丢帧。

#### 任务四：低功耗 RS-485 从站

- 配置地址匹配唤醒；
- 增加 CRC、长度和地址字段；
- 使用 LPTIM 处理帧间超时；
- 使用 TC 控制 DE；
- 测量待机电流、发射峰值和帧成功率。

验收：无关地址不唤醒业务处理，最后一个字节不丢失。

#### 任务五：LPUART + Stop + RTOS

- LPUART 接收唤醒 RTOS；
- ISR 投递事件，任务解析协议；
- 处理 Tickless、DMA、时钟恢复和超时；
- 注入低功耗时钟失效、DMA 停止和过载异常。

验收：唤醒、接收、处理和重新睡眠形成稳定闭环。

#### 任务六：整机低功耗通信回归

覆盖：

- LSE/LSI/高频保持时钟；
- 2400~115200 bit/s；
- 不同帧长度；
- 连续帧、突发帧和半帧；
- 温度、电压和器件批次；
- RS-485 总线偏置和终端变化；
- 调试器连接/断开；
- 多源唤醒和看门狗复位。

### 16.2 性能测试方法

|测试项|方法|
|---|---|
|实际波特率|逻辑分析仪测量 bit 时间|
|唤醒延迟|Start Bit 边沿到测试 GPIO 翻转|
|首字节可靠性|改变前导码长度和主站发送间隔|
|DMA 接收能力|最大波特率下发送连续长帧|
|缓冲区裕量|增大任务阻塞时间并观察 ORE|
|帧错误率|长时间发送随机数据并统计 CRC/FE/NE|
|低功耗电流|Stop 稳态和总线监听窗口平均值|
|RS-485 方向控制|TX 波形、DE 波形和最后停止位对齐|
|外部漏电|分别断开收发器、终端、偏置和 GPIO|
|恢复可靠性|注入时钟、DMA、FIFO 和看门狗异常|

波特率：

Bactual=1TbitBactual​=Tbit​1​

波特率误差：

ϵB=Bactual−BtargetBtargetϵB​=Btarget​Bactual​−Btarget​​

字节时间：

Tbyte=NbitsBTbyte​=BNbits​​

接收缓冲下限：

Cmin≥⌈B×TblockNbits⌉Cmin​≥⌈Nbits​B×Tblock​​⌉

平均电流：

Iavg=∑IiTiTcycleIavg​=Tcycle​∑Ii​Ti​​

单次通信能量：

Eframe=∫t0t1V(t)I(t)dtEframe​=∫t0​t1​​V(t)I(t)dt

### 16.3 进阶学习方向

1. LPUART 在 Stop 模式下的异步接收、FIFO 和唤醒状态机；
2. UART 自动波特率检测、LIN Break 和地址标记；
3. DMA 环形缓冲、Cache 一致性和零拷贝协议解析；
4. RS-485 收发器低功耗、终端匹配、偏置网络和 EMC；
5. Modbus RTU、LIN、SLIP、HDLC 风格帧同步和 CRC；
6. RTOS Tickless 与 LPUART 接收唤醒协同；
7. 低功耗串口与 RTC/LPTIM 的超时调度；
8. 低功耗无线模块、GNSS、蜂窝模组的串口电源时序；
9. LPUART 波形自动分析、长时间误码统计和 CI 回归；
10. 通过硬件 FIFO、地址匹配和协议握手构建零丢首字节通信系统。

**最终工程结论：LPUART 的核心不是“在 Stop 中打开串口中断”，而是对低功耗时钟、接收采样、唤醒延迟、首字节策略、DMA 缓冲、协议同步、外部收发器和故障恢复进行联合设计。只有做到“唤醒可靠、首帧可恢复、长帧不丢、方向控制正确、功耗可测、错误可诊断”，低功耗串口才能达到工业级可用性。**