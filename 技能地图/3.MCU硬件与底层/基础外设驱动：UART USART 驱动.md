
## 1. 学习目标

### 理解

- 理解 UART 异步通信帧结构、波特率生成、采样时钟与误码机制。
- 理解 USART 同步模式与 UART 异步模式的硬件差异。
- 理解 TXE、TC、RXNE、IDLE、ORE、FE、NE、PE 等状态位的产生条件。
- 理解轮询、中断、DMA 三种驱动模型的 CPU、内存和实时性代价。

### 掌握

- 掌握寄存器级 UART 初始化、收发、错误处理与超时控制。
- 掌握基于环形缓冲区的全双工非阻塞驱动。
- 掌握 DMA 循环接收、空闲线检测和不定长帧提取。
- 掌握 RS-485 方向控制、发送完成判定和总线冲突规避。

### 精通

- 精通 UART 接收数据路径中的并发、溢出、缓存一致性与竞态问题。
- 精通高吞吐场景下 DMA 缓冲区尺寸、服务周期和中断负载的量化设计。
- 精通 RTOS 环境下 ISR、任务、队列、Stream Buffer 之间的职责划分。
- 精通波特率误差、时钟漂移、采样裕量与物理层质量的联合分析。

### 能够设计

- 能够设计跨 MCU、可测试、可观测、可恢复的工业级 UART 驱动层。
- 能够根据吞吐量、延迟、RAM、功耗和协议边界选择收发机制。
- 能够设计 UART、DMA、RTOS、协议解析器协同工作的完整通信架构。

---

## 2. 前置要求

### 知识要求

- ARM Cortex-M 异常与 NVIC 工作机制。
- volatile、内存屏障、原子访问和单生产者单消费者模型。
- MCU 时钟树、APB 总线、GPIO 复用与 DMA 请求映射。
- RTOS 中断优先级、任务通知、信号量和临界区。
- CRC、帧同步、超时和状态机等协议基础。

### 技能要求

- 能阅读 MCU Reference Manual、Datasheet 和芯片 Errata。
- 能使用示波器或逻辑分析仪测量波特率、帧间隔和中断延迟。
- 能进行寄存器级调试，并区分外设状态错误与软件逻辑错误。
- 能通过 map 文件、周期计数器和 RTOS trace 量化资源开销。

---

## 3. 技术概述

### 核心定义

UART 是基于起始位和停止位完成字符同步的**异步串行通信控制器**。USART 在 UART 基础上增加同步时钟输出或输入能力。

典型 `8N1` 帧包含：

```
空闲高电平 | 1 位起始位 | 8 位数据 | 无校验 | 1 位停止位
```

每传输 1 字节占用 10 bit，因此有效载荷吞吐量为：

```
payload_bytes_per_second = baud_rate / bits_per_frame
115200 8N1 = 115200 / 10 = 11520 byte/s
```

### 技术价值

- MCU 调试日志、Bootloader、AT 指令和维护控制台。
- GNSS、蜂窝模组、蓝牙模组和传感器通信。
- 配合 RS-232、RS-485 收发器构成长距离工业通信链路。
- 在低成本、低引脚数量条件下提供确定性字节流通道。

### 主流技术分支

- **轮询收发**：逻辑简单，但阻塞 CPU。
- **中断逐字节收发**：延迟低，适合低到中等吞吐量。
- **DMA 分块收发**：CPU 开销低，适合定长或大块数据。
- **DMA 循环接收 + IDLE**：适合高吞吐、不定长协议。
- **双缓冲 DMA**：适合持续数据流和严格无缝接收。
- **同步 USART**：外部时钟参与采样，应用范围小于异步 UART。

---

## 4. 核心特性横向对比

|方案|CPU 开销|首字节延迟|RAM 开销|不定长帧|持续高吞吐|实现复杂度|
|---|---|---|---|---|---|---|
|阻塞轮询|极高|低|极低|支持|差|低|
|中断逐字节|中到高|低|环形队列|支持|中|中|
|普通 DMA|低|取决于块大小|DMA 缓冲区|较弱|高|中|
|DMA + IDLE|很低|约 1 帧时间|循环缓冲区|强|高|较高|
|DMA 半满/满中断|很低|半缓冲周期|双区缓冲|中|很高|较高|
|DMA 双缓冲|最低|可配置|两个数据块|中|很高|高|

|特性|UART|USART 异步模式|USART 同步模式|
|---|---|---|---|
|时钟线|无|无|有|
|起止位|必需|必需|通常仍由外设帧格式控制|
|全双工|支持|支持|支持|
|时钟偏差敏感性|高|高|低|
|多处理器地址模式|依芯片而定|常见|常见|
|LIN/IrDA/Smartcard|少见|常见|依芯片而定|

---

## 5. 底层原理与功能特性深度解析

### 5.1 接收与采样原理

接收器检测 RX 从高到低，确认起始位后，按过采样时钟在位中心采样。常见过采样率为 16 或 8。

以 16 倍过采样为例：

```
RX:       ----\__________/---- data bits ----
sample:         7  8  9
decision:       多数表决
```

接收误差来自：

- 发送端与接收端时钟偏差。
- 波特率分频取整误差。
- 边沿抖动和传输线噪声。
- 帧越长导致采样点累计漂移。
- 过采样 8 模式下采样裕量降低。

工程上通常要求双方总波特率偏差控制在 **±2% 左右**。具体上限取决于数据位、校验位、停止位、过采样方式和芯片实现，必须以芯片手册为准。

### 5.2 波特率生成

对一类典型 USART，在 16 倍过采样模式下：

```
USARTDIV = fPCLK / baud
实际波特率 = fPCLK / round(USARTDIV)
误差率 = (实际波特率 - 目标波特率) / 目标波特率 × 100%
```

例如 `fPCLK = 80 MHz`、目标 `115200 baud`：

```
divider = round(80,000,000 / 115,200) = 694
actual  = 80,000,000 / 694 = 115,273.78
error   = +0.064%
```

不同 STM32 世代的 `BRR` 编码和 `OVER8` 规则不同，不应把某一系列的公式直接移植到另一系列。

### 5.3 寄存器级初始化

以下代码使用抽象寄存器定义表达驱动结构。量产代码应由芯片头文件提供寄存器地址和位定义。

```
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    volatile uint32_t CR1;
    volatile uint32_t CR2;
    volatile uint32_t CR3;
    volatile uint32_t BRR;
    volatile uint32_t ISR;
    volatile uint32_t ICR;
    volatile uint32_t RDR;
    volatile uint32_t TDR;
} uart_regs_t;

#define UART_CR1_UE       (1u << 0)
#define UART_CR1_RE       (1u << 2)
#define UART_CR1_TE       (1u << 3)
#define UART_CR1_RXNEIE   (1u << 5)
#define UART_CR1_TXEIE    (1u << 7)
#define UART_CR1_IDLEIE   (1u << 4)

#define UART_ISR_PE       (1u << 0)
#define UART_ISR_FE       (1u << 1)
#define UART_ISR_NE       (1u << 2)
#define UART_ISR_ORE      (1u << 3)
#define UART_ISR_IDLE     (1u << 4)
#define UART_ISR_RXNE     (1u << 5)
#define UART_ISR_TC       (1u << 6)
#define UART_ISR_TXE      (1u << 7)

#define UART_ICR_PECF     (1u << 0)
#define UART_ICR_FECF     (1u << 1)
#define UART_ICR_NECF     (1u << 2)
#define UART_ICR_ORECF    (1u << 3)
#define UART_ICR_IDLECF   (1u << 4)

typedef enum {
    UART_OK = 0,
    UART_EINVAL,
    UART_EBAUD,
    UART_ETIMEOUT,
    UART_EBUSY
} uart_status_t;

static uart_status_t uart_hw_init(uart_regs_t *uart,
                                  uint32_t peripheral_hz,
                                  uint32_t baud)
{
    if ((uart == NULL) || (baud == 0u) || (peripheral_hz < baud)) {
        return UART_EINVAL;
    }

    const uint32_t divider = (peripheral_hz + (baud / 2u)) / baud;
    if ((divider == 0u) || (divider > 0xFFFFu)) {
        return UART_EBAUD;
    }

    uart->CR1 = 0u;                    /* 配置期间关闭外设 */
    uart->CR2 = 0u;                    /* 8N1 的停止位配置 */
    uart->CR3 = 0u;
    uart->BRR = divider;
    uart->ICR = UART_ICR_PECF | UART_ICR_FECF |
                UART_ICR_NECF | UART_ICR_ORECF |
                UART_ICR_IDLECF;
    uart->CR1 = UART_CR1_RE | UART_CR1_TE | UART_CR1_UE;

    return UART_OK;
}
```

初始化顺序应为：

```
外设时钟使能
  -> GPIO 电气属性和复用配置
  -> 外设保持禁用
  -> 波特率、帧格式、流控配置
  -> 清除遗留状态
  -> 配置 DMA/NVIC
  -> 使能 USART
  -> 最后开启中断和数据通路
```

### 5.4 有超时的轮询发送

超时必须基于单调递增时基，并使用无符号减法处理计数器回绕。

```
typedef uint32_t (*uart_get_tick_fn)(void);

static uart_status_t uart_write_polling(uart_regs_t *uart,
                                        const uint8_t *data,
                                        size_t length,
                                        uint32_t timeout_ticks,
                                        uart_get_tick_fn get_tick)
{
    if ((uart == NULL) || ((data == NULL) && (length != 0u)) ||
        (get_tick == NULL)) {
        return UART_EINVAL;
    }

    const uint32_t start = get_tick();

    for (size_t i = 0u; i < length; ++i) {
        while ((uart->ISR & UART_ISR_TXE) == 0u) {
            if ((uint32_t)(get_tick() - start) >= timeout_ticks) {
                return UART_ETIMEOUT;
            }
        }
        uart->TDR = data[i];
    }

    /* TXE 仅表示 TDR 可写；TC 才表示最后停止位已离开引脚。 */
    while ((uart->ISR & UART_ISR_TC) == 0u) {
        if ((uint32_t)(get_tick() - start) >= timeout_ticks) {
            return UART_ETIMEOUT;
        }
    }

    return UART_OK;
}
```

### 5.5 中断与环形缓冲区

单生产者单消费者环形队列中：

- RX：ISR 是生产者，任务是消费者。
- TX：任务是生产者，ISR 是消费者。
- 使用单调递增索引可避免“头尾相等究竟为空还是满”的歧义。
- 缓冲区容量为 2 的幂时，可用位掩码代替取模。

```
#define UART_RING_SIZE 256u
#define UART_RING_MASK (UART_RING_SIZE - 1u)

_Static_assert((UART_RING_SIZE & UART_RING_MASK) == 0u,
               "ring size must be a power of two");

typedef struct {
    uint8_t data[UART_RING_SIZE];
    volatile uint32_t write_seq;
    volatile uint32_t read_seq;
} uart_ring_t;

typedef struct {
    uart_regs_t *regs;
    uart_ring_t rx;
    uart_ring_t tx;
    volatile uint32_t rx_overflow;
    volatile uint32_t overrun_errors;
    volatile uint32_t framing_errors;
    volatile uint32_t noise_errors;
    volatile uint32_t parity_errors;
} uart_driver_t;

static bool ring_push(uart_ring_t *ring, uint8_t value)
{
    const uint32_t write = ring->write_seq;
    const uint32_t read = ring->read_seq;

    if ((uint32_t)(write - read) >= UART_RING_SIZE) {
        return false;
    }

    ring->data[write & UART_RING_MASK] = value;
    __DMB();                           /* 发布数据后再发布索引 */
    ring->write_seq = write + 1u;
    return true;
}

static bool ring_pop(uart_ring_t *ring, uint8_t *value)
{
    const uint32_t read = ring->read_seq;

    if (read == ring->write_seq) {
        return false;
    }

    *value = ring->data[read & UART_RING_MASK];
    __DMB();
    ring->read_seq = read + 1u;
    return true;
}
```

中断服务函数必须先处理错误，再接收数据，并限制单次 ISR 工作量。

```
void uart_irq_handler(uart_driver_t *driver)
{
    uart_regs_t *const uart = driver->regs;
    uint32_t status = uart->ISR;

    if ((status & UART_ISR_PE) != 0u) {
        driver->parity_errors++;
        uart->ICR = UART_ICR_PECF;
    }
    if ((status & UART_ISR_FE) != 0u) {
        driver->framing_errors++;
        uart->ICR = UART_ICR_FECF;
    }
    if ((status & UART_ISR_NE) != 0u) {
        driver->noise_errors++;
        uart->ICR = UART_ICR_NECF;
    }
    if ((status & UART_ISR_ORE) != 0u) {
        driver->overrun_errors++;
        uart->ICR = UART_ICR_ORECF;
    }

    if ((status & UART_ISR_RXNE) != 0u) {
        const uint8_t value = (uint8_t)uart->RDR;
        if (!ring_push(&driver->rx, value)) {
            driver->rx_overflow++;
        }
    }

    if (((status & UART_ISR_TXE) != 0u) &&
        ((uart->CR1 & UART_CR1_TXEIE) != 0u)) {
        uint8_t value;

        if (ring_pop(&driver->tx, &value)) {
            uart->TDR = value;
        } else {
            uart->CR1 &= ~UART_CR1_TXEIE;
        }
    }
}
```

`volatile` 只能阻止特定编译器优化，**不能自动提供原子性、跨核同步或缓存一致性**。上述模型成立的前提是：

- 索引宽度可被 CPU 原子读写。
- 每个索引只有一个写入者。
- DMA 不直接访问该环形队列。
- 使用适合目标架构和编译器的 acquire/release 语义；示例中的 `__DMB()` 需替换为平台封装。

### 5.6 DMA 循环接收与 IDLE

DMA 写入固定循环缓冲区，通过 `NDTR` 推导硬件写位置：

```
dma_position = buffer_size - NDTR
new_length =
    dma_position >= old_position
    ? dma_position - old_position
    : buffer_size - old_position + dma_position
```

```
#define UART_DMA_RX_SIZE 512u

typedef struct {
    uint8_t buffer[UART_DMA_RX_SIZE];
    size_t consumed;
} uart_dma_rx_t;

typedef uint32_t (*dma_remaining_fn)(void);
typedef void (*uart_rx_consume_fn)(const uint8_t *data, size_t length);

static void uart_dma_rx_drain(uart_dma_rx_t *rx,
                              dma_remaining_fn remaining,
                              uart_rx_consume_fn consume)
{
    const uint32_t left = remaining();

    if ((left > UART_DMA_RX_SIZE) || (consume == NULL)) {
        return;
    }

    const size_t produced = UART_DMA_RX_SIZE - left;

    if (produced == rx->consumed) {
        return;
    }

    if (produced > rx->consumed) {
        consume(&rx->buffer[rx->consumed], produced - rx->consumed);
    } else {
        consume(&rx->buffer[rx->consumed],
                UART_DMA_RX_SIZE - rx->consumed);
        if (produced != 0u) {
            consume(&rx->buffer[0], produced);
        }
    }

    rx->consumed = produced;
}
```

必须处理三个硬件细节：

1. `NDTR` 与 DMA 写操作可能在读取瞬间变化，应在临界窗口内读取，或采用两次稳定读取。
2. Cortex-M7、Cortex-A 等带数据缓存平台上，CPU 读取前必须进行 **D-cache invalidate**。
3. 只有 IDLE 事件而没有 DMA 半满/满事件时，连续无空闲数据可能绕环覆盖，因此两类事件应共同驱动 drain。

---

## 6. 性能量化分析

### 测试基线

以下数据为参考测量，不是跨平台保证值：

- MCU：STM32F407，Cortex-M4F，`168 MHz`
- 编译器：GCC 12，`-O2`
- UART：`921600 baud`、`8N1`
- 有效吞吐：`92,160 byte/s`
- DWT CYCCNT 统计 ISR 周期
- RX 缓冲区：`512 byte`
- 不包含上层协议解析时间

|接收机制|中断频率|单次 CPU 周期|CPU 占用|接收 RAM|
|---|---|---|---|---|
|每字节 RXNE|92,160/s|150~220|8.2%~12.1%|256 B|
|DMA 每 32 B|2,880/s|310~430|0.53%~0.74%|32 B+|
|DMA 每 128 B|720/s|340~470|0.15%~0.20%|128 B+|
|DMA 512 B 半满/满|360/s|390~520|0.08%~0.11%|512 B|
|DMA + IDLE|取决于帧率|400~650|典型 <0.2%|512 B|

CPU 占用计算：

```
CPU% = 中断频率 × 单次中断周期 / CPU频率 × 100%
```

例如逐字节中断按 180 周期计算：

```
CPU% = 92160 × 180 / 168000000 × 100% = 9.87%
```

### 缓冲区容量计算

最小接收缓冲区：

```
buffer_min >= byte_rate × worst_service_latency × safety_factor
```

`921600 baud`、`8N1`、任务最长 5 ms 未调度、安全系数 2：

```
buffer_min >= 92160 × 0.005 × 2 = 921.6 byte
```

应选择至少 **1024 byte**。如果期间可能关闭中断 20 ms，则需要至少：

```
92160 × 0.020 × 2 = 3686.4 byte
```

### 主要瓶颈

- 逐字节中断导致高异常进入/退出成本。
- 日志格式化时间可能远高于 UART 发送时间。
- 小 DMA 块会退化为高频中断。
- 大 DMA 块降低中断频率，但增加首批数据交付延迟。
- Cache line 失效范围未对齐会破坏相邻数据或增加维护成本。
- 在 ISR 中解析协议会扩大最高优先级阻塞时间。

### 优化收益

- RXNE 改为 DMA 128 B 分块：CPU 占用可从约 **9.9% 降到 0.2%** 。
- TX 使用 DMA 聚合 128 B：显著减少逐字节 TXE 中断。
- 使用零拷贝片段描述符：可省去一次 `memcpy`，但会增加缓冲区生命周期复杂度。
- 将日志格式化和协议解析移到任务：降低 ISR 最坏执行时间和系统抖动。

---

## 7. 应用场景选型指南

### 决策流程图

```
UART 数据量是否极低且仅用于初始化？
├─ 是 -> 有超时轮询
└─ 否
   ├─ 峰值速率 < 115200，且 RAM 极小？
   │  ├─ 是 -> RX/TX 中断 + 环形队列
   │  └─ 否
   ├─ 接收长度固定？
   │  ├─ 是 -> 普通 DMA
   │  └─ 否
   ├─ 帧间存在空闲间隔？
   │  ├─ 是 -> 循环 DMA + IDLE + 半满/满事件
   │  └─ 否 -> 双缓冲 DMA + 流式协议解析
   └─ 是否使用 RS-485 半双工？
      ├─ 是 -> DMA TX + TC 完成后切换 DE
      └─ 否 -> 标准全双工数据通路
```

|典型场景|需求|推荐方案|理由|
|---|---|---|---|
|Bootloader 命令行|低速、实现小|中断 RX + 轮询 TX|RX 不丢字节，代码体积可控|
|GNSS NMEA|不定长、有帧间隙|DMA + IDLE|降低高频接收中断|
|4G/5G AT 模组|突发大数据|DMA 循环 RX + 流解析|可处理 URC 与命令响应交织|
|RS-485 Modbus RTU|半双工、帧间隔敏感|DMA + 定时器/IDLE + TC|正确处理静默时间和 DE|
|高频调试日志|TX 为主、允许排队|TX DMA + 日志环形队列|避免阻塞实时任务|
|安全控制命令|低延迟、需审计|中断 RX + 固定协议状态机|控制处理路径和错误传播|

---

## 8. 工程最佳实践

### 设计原则

- **硬件层只操作寄存器，驱动层管理缓冲和并发，协议层处理帧语义。**
- ISR 只完成搬运、计数、清状态和唤醒，不做格式化、动态分配或复杂解析。
- 所有阻塞 API 必须有超时，禁止无限等待状态位。
- 错误不能只清标志，必须维护 ORE、FE、NE、PE、DMA error 统计。
- RX 缓冲区溢出策略必须明确：丢新数据、覆盖旧数据、复位会话或进入故障态。
- 发送完成应区分“软件已入队”“DMA 已结束”“最后停止位已发送”。
- 引脚复用、时钟源、DMA 通道和 IRQ 优先级应来自板级配置。
- 驱动应支持故障注入和主机侧单元测试。

### 选型决策矩阵

|约束|轮询|中断|DMA|
|---|---|---|---|
|代码体积最小|5|3|1|
|CPU 效率|1|3|5|
|首字节低延迟|4|5|3|
|持续高吞吐|1|3|5|
|不定长接收|3|5|4|
|可维护性|4|4|3|
|低功耗睡眠|1|4|5|

### 工业级编码规范

- 寄存器位操作使用芯片定义，不在业务代码中散布魔数。
- 长度使用 `size_t`，硬件计数器边界处执行显式范围检查。
- ISR 与任务共享字段应满足单写者原则，或由临界区/原子操作保护。
- 错误码区分参数错误、忙、超时、溢出、硬件错误和取消。
- 禁止在 UART ISR 中调用不可重入标准库函数。
- DMA 缓冲区显式对齐到 Cache line，并放置在 DMA 可访问内存域。
- 配置变更时先停止数据通路，再等待 TC，最后禁用外设。

---

## 9. 常见错误与避坑指南

### 错误一：使用 TXE 判断 RS-485 发送结束

错误代码：

```
while ((uart->ISR & UART_ISR_TXE) == 0u) {
}
rs485_de_set(false);
```

根因：TXE 仅表示发送数据寄存器为空，移位寄存器仍可能发送数据。

正确实现：

```
while ((uart->ISR & UART_ISR_TC) == 0u) {
}
uart->ICR = UART_ISR_TC; /* 实际清除方式以芯片手册为准 */
rs485_de_set(false);
```

风险：最后一个字节或停止位被截断，形成随机 CRC 错误。

### 错误二：接收中断不读取数据或不清 ORE

错误代码：

```
if ((uart->ISR & UART_ISR_ORE) != 0u) {
    error_count++;
}
```

根因：部分 MCU 要求按特定顺序读取状态和数据寄存器，另一些 MCU 使用 ICR 清除。处理方式具有芯片相关性。

正确实现：

```
if ((uart->ISR & UART_ISR_ORE) != 0u) {
    const uint8_t discarded = (uint8_t)uart->RDR;
    (void)discarded;
    uart->ICR = UART_ICR_ORECF;
    error_count++;
}
```

风险：中断风暴、接收器停滞或后续字节持续丢失。

### 错误三：用 volatile 代替并发协议

错误代码：

```
volatile uint16_t count;

void uart_isr(void)
{
    count++;
}

void task(void)
{
    count--;
}
```

根因：读改写不是天然原子操作，两个执行上下文会丢失更新。

正确实现：

```
void task_consume(void)
{
    uint32_t irq_state = platform_irq_save();
    if (count != 0u) {
        count--;
    }
    platform_irq_restore(irq_state);
}
```

风险：队列计数失真、越界访问和不可复现的数据损坏。

### 错误四：DMA 缓冲区在 Cache 中读取旧数据

错误代码：

```
parse(rx_dma_buffer, received);
```

根因：DMA 已写入 SRAM，但 CPU D-cache 中仍保留旧 Cache line。

正确实现：

```
platform_dcache_invalidate(rx_dma_buffer,
                           cache_aligned_length(received));
__DMB();
parse(rx_dma_buffer, received);
```

风险：高端 Cortex-M7/A 平台出现随机旧帧、CRC 错误或字段跳变。

### 错误五：未检查环形缓冲区满

错误代码：

```
rx_buffer[write_index++ & MASK] = uart->RDR;
```

根因：生产速率超过消费速率时覆盖尚未消费的数据。

正确实现：

```
if (!ring_push(&driver->rx, (uint8_t)uart->RDR)) {
    driver->rx_overflow++;
    driver->rx_resync_required = true;
}
```

风险：协议层得到由新旧数据拼接成的伪帧，严重时执行错误控制命令。

### 错误六：DMA 完成即释放 RS-485 DE

错误代码：

```
void dma_tx_complete_isr(void)
{
    rs485_de_set(false);
}
```

根因：DMA 完成仅表示最后一个字节已写入 UART TDR，不代表已经离开 TX 引脚。

正确实现：

```
void dma_tx_complete_isr(void)
{
    uart_enable_tc_interrupt();
}

void uart_tc_isr(void)
{
    uart_clear_tc();
    rs485_de_set(false);
    tx_state = TX_IDLE;
}
```

风险：最后一字节被截断，且故障随波特率、负载和芯片流水线变化。

---

## 10. 多机制组合使用方案

### 技术协同架构

```
UART RX 引脚
  -> USART 接收器
  -> 循环 DMA 缓冲区
  -> DMA 半满/满 + USART IDLE
  -> ISR 更新生产位置并通知任务
  -> RX 工作任务
  -> 流式协议解析器
  -> 命令队列
  -> 业务任务

业务任务
  -> 消息编码器
  -> TX 描述符队列
  -> DMA TX
  -> DMA 完成
  -> UART TC
  -> RS-485 DE 释放/完成通知
```

### 完整代码框架

```
typedef enum {
    UART_TX_IDLE,
    UART_TX_DMA_ACTIVE,
    UART_TX_WAIT_TC
} uart_tx_state_t;

typedef struct {
    uart_driver_t base;
    uart_dma_rx_t dma_rx;
    volatile uart_tx_state_t tx_state;
    volatile bool rx_event;
    volatile bool tx_done;
} uart_port_t;

void uart_idle_isr(uart_port_t *port)
{
    if ((port->base.regs->ISR & UART_ISR_IDLE) != 0u) {
        port->base.regs->ICR = UART_ICR_IDLECF;
        port->rx_event = true;
        rtos_notify_from_isr(RX_TASK_ID);
    }
}

void uart_dma_rx_half_or_full_isr(uart_port_t *port)
{
    dma_clear_rx_event();
    port->rx_event = true;
    rtos_notify_from_isr(RX_TASK_ID);
}

void uart_rx_task(void *argument)
{
    uart_port_t *port = argument;

    for (;;) {
        rtos_wait_notification();

        do {
            port->rx_event = false;
            uart_dma_rx_drain(&port->dma_rx,
                              dma_rx_remaining,
                              protocol_stream_consume);
        } while (port->rx_event);
    }
}

uart_status_t uart_tx_start(uart_port_t *port,
                            const uint8_t *data,
                            size_t length)
{
    if ((data == NULL) || (length == 0u) ||
        (length > DMA_MAX_TRANSFER)) {
        return UART_EINVAL;
    }

    uint32_t state = platform_irq_save();

    if (port->tx_state != UART_TX_IDLE) {
        platform_irq_restore(state);
        return UART_EBUSY;
    }

    port->tx_state = UART_TX_DMA_ACTIVE;
    port->tx_done = false;
    rs485_de_set(true);
    dma_tx_configure(data, length);
    dma_tx_start();

    platform_irq_restore(state);
    return UART_OK;
}

void uart_dma_tx_complete_isr(uart_port_t *port)
{
    dma_clear_tx_complete();
    dma_tx_disable();
    port->tx_state = UART_TX_WAIT_TC;
    uart_clear_tc();
    uart_enable_tc_interrupt();
}

void uart_tx_complete_isr(uart_port_t *port)
{
    uart_disable_tc_interrupt();
    uart_clear_tc();
    rs485_de_set(false);
    port->tx_state = UART_TX_IDLE;
    port->tx_done = true;
    rtos_notify_from_isr(TX_TASK_ID);
}
```

该架构把**数据搬运、事件通知、协议解析和业务执行**分离，可分别进行时序预算和故障隔离。

---

## 11. 工业级实际案例分析

### 案例一：RS-485 Modbus RTU 主站

需求：

- `115200 baud`，最多 32 个从站。
- 半双工通信。
- 依据 `3.5` 字符静默时间判断帧边界。
- 单次事务超时 100 ms。

架构：

```
事务调度器 -> Modbus 编码 -> DMA TX -> TC -> DE 关闭
                                      |
DMA 循环 RX <- 定时器静默检测 <- RX 边沿/IDLE
      -> CRC 校验 -> 地址/功能码匹配 -> 事务完成
```

字符时间：

```
11 bit/字符时：
Tchar = 11 / 115200 = 95.49 us
T3.5  = 334.2 us
```

核心处理：

```
void modbus_on_rx_activity(void)
{
    timer_restart_us(335u);
}

void modbus_silence_timer_isr(void)
{
    const size_t length = uart_rx_snapshot(frame_buffer,
                                           sizeof(frame_buffer));
    if ((length >= 4u) &&
        (modbus_crc16(frame_buffer, length) == 0u)) {
        modbus_post_frame_from_isr(frame_buffer, length);
    } else {
        diagnostics.modbus_bad_frame++;
    }
}
```

设计要点：

- IDLE 的定义通常是约一帧字符空闲，不能直接等同于 Modbus `T3.5`。
- DE 必须在 TC 后关闭，并考虑收发器使能/关闭传播延迟。
- 响应必须同时匹配站址、功能码和当前事务，避免旧响应误配。

### 案例二：蜂窝模组 AT 与数据通道

需求：

- 命令响应与 URC 异步交织。
- 峰值 `921600 baud`。
- 单包可达数 KB。
- 不能在 AT 等待期间丢失网络事件。

架构：

```
DMA RX -> 流式词法解析
       -> 响应匹配器 -> 当前 AT 事务
       -> URC 分派器 -> 网络状态任务
       -> 二进制载荷通道 -> socket 数据队列
```

核心状态机：

```
typedef enum {
    PARSER_LINE,
    PARSER_BINARY
} parser_mode_t;

typedef struct {
    parser_mode_t mode;
    size_t binary_remaining;
    char line[256];
    size_t line_length;
} modem_parser_t;

void modem_consume(modem_parser_t *parser,
                   const uint8_t *data,
                   size_t length)
{
    while (length-- != 0u) {
        const uint8_t ch = *data++;

        if (parser->mode == PARSER_BINARY) {
            socket_payload_push(ch);
            if (--parser->binary_remaining == 0u) {
                parser->mode = PARSER_LINE;
            }
            continue;
        }

        if (ch == '\n') {
            parser->line[parser->line_length] = '\0';
            modem_dispatch_line(parser->line);
            parser->line_length = 0u;
        } else if ((ch != '\r') &&
                   (parser->line_length + 1u < sizeof(parser->line))) {
            parser->line[parser->line_length++] = (char)ch;
        } else if (ch != '\r') {
            parser->line_length = 0u;
            diagnostics.modem_line_overflow++;
        }
    }
}
```

设计要点：

- 不得用“一次 DMA 回调等于一条 AT 响应”的假设。
- 解析器必须支持跨 DMA 块的行和二进制载荷。
- 命令锁只序列化发送事务，不应阻塞 URC 接收与分发。

### 案例三：高实时控制器日志系统

需求：

- 控制周期 100 μs。
- 日志峰值 200 KB/s。
- 日志不得阻塞控制任务。
- 故障前保留最近 4 KB 数据。

架构：

```
控制任务 -> 二进制事件记录 -> 无锁 SPSC 环形区
                              -> 低优先级日志任务
                              -> TX DMA 聚合发送
故障发生 -> 冻结最近 4 KB -> Flash/备用接口导出
```

核心写入：

```
bool trace_write_isr(trace_ring_t *ring, const trace_record_t *record)
{
    const uint32_t write = ring->write_seq;
    const uint32_t read = ring->read_seq;

    if ((uint32_t)(write - read) >= TRACE_RECORD_COUNT) {
        ring->dropped++;
        return false;
    }

    ring->records[write & TRACE_RECORD_MASK] = *record;
    __DMB();
    ring->write_seq = write + 1u;
    return true;
}
```

设计要点：

- 实时路径记录二进制事件，不执行 `printf`。
- 队列满时丢日志而不是阻塞控制任务。
- 发送带宽不足时必须有降采样、分级或限流策略。

---

## 12. 高频问题深度答疑

### 1. TXE 与 TC 为什么必须区分？

TXE 表示 TDR 可接受下一字节，用于维持连续发送；TC 表示 TDR 和移位寄存器都为空。普通全双工发送可主要依赖 TXE，RS-485 切换方向和进入低功耗前必须等待 TC。

### 2. IDLE 能否可靠表示协议帧结束？

只能在协议明确保证帧内不会出现一个字符时间以上空闲时使用。Modbus RTU 要求 `3.5` 字符间隔，通常还需要定时器。连续二进制流则不能依赖 IDLE，必须依据长度、分隔符或协议状态机。

### 3. DMA 是否一定比中断更快？

DMA 降低的是 CPU 搬运开销，不会提高 UART 线速。小包、高频启停 DMA 时，配置和 Cache 维护成本可能高于逐字节中断。DMA 的优势在中高吞吐、批量搬运和持续流。

### 4. 为什么高波特率偶发 ORE？

ORE 表示新数据到达时旧数据尚未从接收寄存器取走。根因通常是长时间关中断、高优先级 ISR 占用、Flash 擦写阻塞总线、错误中断未清除或驱动在临界区中执行耗时操作。

### 5. UART 环形队列需要互斥锁吗？

严格 SPSC 且索引原子读写时通常不需要互斥锁，但要保证内存顺序。多个任务同时发送时，TX 队列已变为多生产者模型，需要锁、消息队列或单独发送任务。禁止把 SPSC 实现直接用于 MPSC。

### 6. 波特率相同为什么仍然乱码？

还应核对数据位、奇偶校验、停止位、信号电平、地参考、反相配置、时钟误差和线路质量。TTL UART、RS-232 与 RS-485 的电气层不能直接连接。示波器测得的实际位宽比软件配置值更可信。

---

## 13. 课程核心总结

### 核心要点

- UART 是字节流外设，不提供天然消息边界、可靠性或流量控制。
- RXNE 表示可读，TXE 表示可继续填充，TC 表示物理发送完成。
- 高吞吐不定长接收的通用方案是**循环 DMA + 半满/满事件 + IDLE + 流式解析器**。
- ISR 应负责搬运和通知，协议解析应在任务上下文完成。
- 工业驱动必须处理超时、溢出、ORE、FE、NE、PE、DMA 错误和恢复。
- 带 Cache 平台必须显式解决 DMA 一致性。
- 缓冲区容量应依据最坏服务延迟计算，而不是凭经验选取。

### 性能排序

```
CPU 效率：
DMA 双缓冲 ≈ 循环 DMA > 分块 DMA > 中断 > 轮询

首字节交付延迟：
中断 > 小块 DMA > IDLE DMA > 大块 DMA

实现复杂度：
轮询 < 中断环形队列 < 普通 DMA < 循环 DMA + IDLE < 双缓冲 DMA
```

### 通用选型结论

- 低速控制：中断环形队列。
- 固定长度数据：普通 DMA。
- 不定长突发数据：循环 DMA + IDLE。
- 连续高速流：半满/满中断或双缓冲 DMA。
- RS-485：DMA TX + UART TC 控制方向。
- 实时日志：二进制缓冲 + 后台 DMA，禁止同步 `printf`。

---

## 14. 快速参考速查表

### 场景选型表

|场景|RX|TX|帧边界|
|---|---|---|---|
|调试控制台|中断环形队列|中断或 DMA|CR/LF|
|GNSS|DMA 循环|低频轮询/中断|CR/LF|
|AT 模组|DMA 循环|DMA 队列|行状态机|
|Modbus RTU|DMA 循环|DMA + TC|`T3.5`|
|固定传感器包|定长 DMA|DMA|固定长度|
|连续数据流|双缓冲 DMA|DMA|协议长度/同步字|

### 特性速查表

|标志/事件|含义|驱动动作|
|---|---|---|
|RXNE/RXFNE|接收数据可读|立即读取 RDR|
|TXE/TXFNF|TDR 可写|写下一字节|
|TC|物理发送完成|结束事务、释放 DE|
|IDLE|RX 空闲达到硬件阈值|提取 DMA 新数据|
|ORE|接收溢出|清除、计数、协议重同步|
|FE|帧格式错误|检查波特率和线路|
|NE|噪声错误|检查信号完整性|
|PE|奇偶校验错误|丢弃或标记当前字符|
|DMA HT|半缓冲完成|消费前半区|
|DMA TC|缓冲区完成|消费后半区或切换缓冲|

---

## 15. 学习效果自检

- 能否从时钟树推导 BRR，并计算实际波特率误差？
- 能否解释 TXE、DMA 完成、TC 三个时刻的差异？
- 能否计算给定波特率和最坏任务延迟所需的缓冲区容量？
- 能否实现无阻塞、可检测溢出的 SPSC 环形队列？
- 能否正确处理 DMA 循环缓冲区回绕？
- 能否说明 IDLE 为什么不能无条件作为协议帧边界？
- 能否在 Cortex-M7 上正确执行 DMA Cache 维护？
- 能否设计 RS-485 DE 切换和 Modbus `T3.5` 检测？
- 能否保证 ISR 中不存在动态分配、阻塞和复杂协议解析？
- 能否通过错误计数器定位波特率、线路质量和调度延迟问题？

---

## 16. 实践与进阶路径

### 梯度实战任务

1. **寄存器级驱动**  
    实现 `8N1` 初始化、有超时的轮询收发，并验证 9600、115200、921600 三档波特率。
    
2. **中断环形队列**  
    实现全双工 SPSC 队列，加入溢出计数和并发压力测试。
    
3. **DMA 接收**  
    实现普通 DMA、循环 DMA、半满/满中断和 IDLE 数据提取。
    
4. **工业协议**  
    实现 Modbus RTU 收发、CRC、事务超时、异常响应和 RS-485 DE 控制。
    
5. **故障恢复**  
    注入 ORE、FE、DMA error、缓冲区溢出和线缆断开，验证驱动可恢复性。
    
6. **跨平台抽象**  
    将 GPIO、UART、DMA、Cache 和 RTOS 通知封装为平台接口，在两类 MCU 上移植。
    

### 性能测试方法

- 使用 DWT CYCCNT 测量 ISR 平均周期和最大周期。
- 使用 GPIO 翻转观察 ISR 延迟、执行时间与 DE 切换。
- 用逻辑分析仪测量实际位宽、帧间隔和最后停止位。
- 持续发送伪随机序列，使用序号和 CRC 检测丢包、乱序与破坏。
- 注入高优先级中断和 Flash 擦写，测量最坏服务延迟。
- 在不同 DMA 块尺寸下记录 CPU 占用、RAM、吞吐和交付延迟。
- 至少连续运行 24 小时，检查错误计数器和缓冲区水位峰值。

### 进阶学习方向

- FIFO 型 UART、接收超时中断和硬件自动波特率检测。
- Scatter-Gather、Linked-List DMA 与零拷贝数据管线。
- Cortex-M7/A 系列 Cache、MPU 和 DMA 一致性设计。
- LIN、IrDA、Smartcard、ISO 7816 与多处理器地址模式。
- RS-485 隔离、防雷、终端匹配、偏置电阻和 EMC 设计。
- UART Bootloader 的认证、加密、防回滚与掉电恢复。
- 基于 property-based testing 和硬件在环测试的串口驱动验证。