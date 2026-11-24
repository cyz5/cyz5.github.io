

## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 Mailbox 在 SoC 多处理器、异构处理器和系统控制架构中的定位。
- 区分硬件 Mailbox、共享内存、Doorbell、IPI、RPMsg 和 SCMI 的职责。
- 理解 Mailbox 的发送、接收、中断、确认和错误状态机制。
- 理解 Cortex-A、Cortex-M、SCP、DSP、NPU 之间的消息传递路径。
- 理解 Mailbox 驱动中发送端、接收端和协议层的边界。

### 掌握

能够：

- 设计基于寄存器 FIFO、Doorbell 和共享内存的 Mailbox 通道。
- 实现发送、接收、中断确认、超时和错误恢复。
- 处理 Mailbox 多通道、多客户端和并发访问。
- 设计 Mailbox 与 SCMI、RPMsg、OpenAMP 的组合架构。
- 在 Linux、RTOS 和裸机环境中实现统一的 Mailbox 抽象。

### 精通

能够深入分析：

- Mailbox 硬件寄存器、FIFO、状态位和中断逻辑。
- 发送完成中断与接收事件中断的竞态。
- 多核 Cache 一致性、内存屏障和共享内存可见性。
- Mailbox 通道拥塞、消息丢失、重复发送和乱序问题。
- 多生产者、多消费者模型下的锁、Token 和事务匹配。
- Mailbox 控制器复位、远端处理器崩溃和通道恢复机制。

### 能够设计

能够设计：

- Linux + SCP 的系统控制 Mailbox。
- Cortex-A + Cortex-M 的异构消息通道。
- 支持同步 RPC、异步通知、批量消息和故障恢复的通信框架。
- 具有版本协商、权限校验、超时、监控和安全隔离能力的工业级 Mailbox 系统。
- 满足低延迟、低功耗和功能安全要求的多通道架构。

---

## 2. 前置要求

### 知识要求

- ARMv7-A、ARMv8-A 或 ARMv8-M 异常和中断机制。
- MMIO 寄存器访问、位操作和内存屏障。
- Cache、一致性域、DMA 和共享内存。
- 多核并发、锁、环形队列和生产者消费者模型。
- Linux 中断、设备树、Mailbox Framework 和 workqueue。
- RTOS 任务、信号量、消息队列和 ISR 约束。
- 基本 SCMI、RPMsg、OpenAMP 和异构多处理器知识。
- C 语言结构体布局、原子操作和错误处理。

### 技能要求

- 能够阅读 SoC Reference Manual 中的 Mailbox 章节。
- 能够使用 JTAG、逻辑分析仪和示波器分析中断与 Doorbell。
- 能够阅读 Linux `drivers/mailbox/` 和 `drivers/remoteproc/` 代码。
- 能够分析设备树中的 Mailbox 控制器和客户端关系。
- 能够编写裸机或 RTOS 下的中断驱动。
- 能够使用 Generic Timer、PMU 或 GPIO 测量端到端延迟。

---

## 3. 技术概述

## 3.1 Mailbox 的定义

Mailbox 是一种用于处理器、硬件模块或安全域之间传递控制消息的硬件机制。其典型组成包括：

```
发送端
  |
  | 写入消息或共享内存地址
  | 设置 Doorbell / 发送触发位
  v
+-------------------+
| Mailbox Controller|
| FIFO / Status     |
| IRQ / Doorbell    |
+---------+---------+
          |
          v
接收端中断处理函数
  |
  | 读取消息或共享内存
  | 清除状态
  | 发送 ACK
  v
协议层 / 服务层
```

Mailbox 通常不定义业务协议。它只负责：

- 通知对端；
- 传输少量消息；
- 提供通道状态；
- 触发中断；
- 管理发送完成和接收事件。

SCMI、RPMsg、OpenAMP 等协议可以运行在 Mailbox 之上。

---

## 3.2 Mailbox 与相关机制的关系

|机制|主要职责|是否承载复杂数据|
|---|---|---|
|Mailbox|通知和传输控制消息|通常不适合|
|Doorbell|触发对端事件|否|
|Shared Memory|承载大消息和数据|是|
|IPI|处理器间中断|否|
|FIFO|短消息排队|有限|
|RPMsg|远程处理器消息协议|是|
|SCMI|平台资源管理协议|是|
|OpenAMP|异构通信框架|是|
|DMA|大块数据传输|是|

核心结论：

> **Mailbox 通常是通知通道，不是完整的数据传输系统。大消息应放在共享内存或 DMA 缓冲区中，Mailbox 只传递地址、长度、方向和 Token。**

---

## 3.3 常见 Mailbox 硬件形态

### 形态一：单寄存器 Doorbell

```
发送端写 DOORBELL_SET
        |
        v
对端产生中断
```

适合：

- 事件通知；
- 共享内存消息；
- 低复杂度平台。

### 形态二：寄存器 FIFO

```
TX FIFO -> Mailbox Controller -> RX FIFO
```

适合：

- 短控制消息；
- 消息数量有限；
- 硬件自动排队。

### 形态三：共享内存 + Doorbell

```
+------------------+       +------------------+
| Shared Memory    |       | Shared Memory    |
| Request/Response |       | Request/Response |
+--------+---------+       +--------+---------+
         ^                          ^
         |                          |
      CPU-A ---- Doorbell ----> CPU-B
```

这是 SCMI、RPMsg 和异构 SoC 中最常见的结构。

### 形态四：双向独立通道

```
Channel A -> B: TX_A / RX_B / IRQ_B
Channel B -> A: TX_B / RX_A / IRQ_A
```

优点：

- 方向明确；
- 不容易出现双向状态覆盖；
- 可分别配置优先级和中断。

---

## 3.4 Mailbox 通信的基本模型

### 同步 RPC

```
Client
  |
  | send request
  v
Mailbox
  |
  v
Remote Service
  |
  | response
  v
Client wakes up
```

适合：

- SCMI；
- 电源控制；
- 时钟配置；
- 远程寄存器服务。

### 异步事件

```
Remote Service
  |
  | event notification
  v
Mailbox IRQ
  |
  v
ISR -> Deferred Worker -> Event Callback
```

适合：

- 温度告警；
- 远端启动完成；
- 传感器事件；
- 远端异常通知。

### 单向通知

```
CPU-A: write shared memory -> ring doorbell
CPU-B: IRQ -> read shared memory
```

适合：

- 日志；
- 状态变更；
- 低功耗唤醒；
- 设备事件。

---

# 4. 核心特性横向对比

## 4.1 Mailbox 实现方案对比

|维度|Doorbell|寄存器 FIFO|Shared Memory + Doorbell|DMA + Doorbell|
|---|---|---|---|---|
|单条消息容量|极小|小～中|大|极大|
|实现复杂度|低|中|中|高|
|中断延迟|低|低|低|中|
|CPU 拷贝开销|低|中|可避免|可避免|
|是否支持排队|软件实现|硬件实现|软件实现|软件实现|
|适合复杂协议|否|有限|是|是|
|一致性要求|低|低|高|高|
|故障恢复难度|低|中|中|高|
|典型用途|事件通知|控制命令|SCMI/RPMsg|大数据控制面|

## 4.2 发送完成机制对比

|机制|优点|缺点|适用场景|
|---|---|---|---|
|轮询|简单、可控|占用 CPU|启动阶段、低频请求|
|TX Done IRQ|CPU 开销低|需要硬件支持|同步发送|
|RX Response IRQ|支持完整事务|协议复杂|RPC|
|ACK Mailbox|状态明确|消息开销增加|可靠控制|
|超时回收|能避免永久阻塞|无法保证远端完成|所有生产系统|

## 4.3 Mailbox 与共享内存组合对比

|方案|延迟|吞吐|CPU 占用|工程复杂度|
|---|---|---|---|---|
|纯寄存器消息|低|低|中|低|
|Doorbell + 共享内存|低|高|低～中|中|
|FIFO + 共享内存|低|高|低|中|
|DMA + Doorbell|中|极高|低|高|
|RPMsg/OpenAMP|中|高|中|高|

---

# 5. 底层原理与功能特性深度解析

## 5.1 典型寄存器模型

不同 SoC 寄存器定义不同，但通常包含以下类别：

|寄存器|作用|
|---|---|
|`TX_DATA`|写入发送数据|
|`RX_DATA`|读取接收数据|
|`TX_STATUS`|发送 FIFO 空间和状态|
|`RX_STATUS`|接收 FIFO 数据数量|
|`DOORBELL_SET`|触发对端|
|`DOORBELL_CLEAR`|清除通知|
|`IRQ_STATUS`|中断状态|
|`IRQ_ENABLE`|中断使能|
|`IRQ_CLEAR`|中断确认|
|`CHANNEL_RESET`|通道复位|
|`ERROR_STATUS`|溢出、下溢、协议错误|

### 常见状态位

```
#define MBOX_STATUS_TX_FULL       BIT(0)
#define MBOX_STATUS_TX_EMPTY      BIT(1)
#define MBOX_STATUS_RX_FULL       BIT(2)
#define MBOX_STATUS_RX_EMPTY      BIT(3)
#define MBOX_STATUS_TX_DONE       BIT(4)
#define MBOX_STATUS_RX_PENDING    BIT(5)
#define MBOX_STATUS_ERROR         BIT(31)
```

实际驱动中不得假设状态位具有统一含义，必须依据芯片手册确认：

- 写 1 清零还是写 0 清零；
- 状态是否需要读回确认；
- 中断状态是否自动清除；
- FIFO 读写是否带副作用；
- 是否支持多核并发访问。

---

## 5.2 Doorbell 的硬件工作过程

以发送 Doorbell 为例：

```
1. 发送端写共享内存
2. 发送端执行 DMB/DSB
3. 发送端写 DOORBELL_SET
4. Mailbox 控制器设置远端 IRQ
5. 远端 CPU 进入 ISR
6. ISR 读取共享内存
7. ISR 清除 Doorbell 状态
8. ISR 投递工作项
```

关键顺序：

```
Shared Memory Write
        |
       DMB/DSB
        |
Doorbell Write
```

如果 Doorbell 先于共享内存写入完成，接收端可能看到旧数据。

---

## 5.3 发送端实现

```
struct mbox_regs {
    volatile uint32_t tx_data;
    volatile uint32_t rx_data;
    volatile uint32_t status;
    volatile uint32_t irq_status;
    volatile uint32_t irq_enable;
    volatile uint32_t irq_clear;
    volatile uint32_t doorbell_set;
    volatile uint32_t doorbell_clear;
};

struct mbox_chan {
    struct mbox_regs *regs;
    mutex_t lock;
    uint32_t channel_id;
    bool busy;
};

int mbox_send_word(struct mbox_chan *ch,
                   uint32_t word,
                   uint32_t timeout_us)
{
    uint64_t deadline;
    uint32_t status;

    if (ch == NULL || ch->regs == NULL)
        return -EINVAL;

    mutex_lock(&ch->lock);

    deadline = timer_now_us() + timeout_us;

    do {
        status = ch->regs->status;

        if ((status & MBOX_STATUS_TX_FULL) == 0)
            break;

        if (timer_now_us() >= deadline) {
            mutex_unlock(&ch->lock);
            return -ETIMEDOUT;
        }

        cpu_relax();
    } while (true);

    ch->regs->tx_data = word;

    /*
     * 如果发送端和接收端通过共享状态协作，
     * 必须保证数据写入先于 Doorbell。
     */
    dsb_sy();

    ch->regs->doorbell_set = BIT(ch->channel_id);

    mutex_unlock(&ch->lock);
    return 0;
}
```

工程注意：

- 不能在中断上下文中获取可能睡眠的 Mutex。
- 如果发送寄存器是 FIFO，必须确认 FIFO 空间。
- 如果 Doorbell 是电平触发，必须有清除流程。
- 如果是边沿触发，连续写相同值可能不会产生新事件。

---

## 5.4 接收中断处理

ISR 中不应执行复杂协议解析或阻塞等待。

```
void mbox_irq_handler(struct mbox_chan *ch)
{
    uint32_t irq;
    uint32_t data;

    if (ch == NULL || ch->regs == NULL)
        return;

    irq = ch->regs->irq_status;

    if (irq & MBOX_IRQ_RX_PENDING) {
        while ((ch->regs->status & MBOX_STATUS_RX_EMPTY) == 0) {
            data = ch->regs->rx_data;

            if (!rx_ring_push_isr(ch, data)) {
                ch->rx_overflow++;
                break;
            }
        }

        ch->regs->irq_clear = MBOX_IRQ_RX_PENDING;
        ch->regs->doorbell_clear = BIT(ch->channel_id);

        /*
         * 只做最小化处理，复杂工作交给线程或 workqueue。
         */
        schedule_rx_worker(ch);
    }

    if (irq & MBOX_IRQ_ERROR) {
        ch->error_count++;
        ch->regs->irq_clear = MBOX_IRQ_ERROR;
        schedule_error_worker(ch);
    }
}
```

中断处理函数的核心原则：

- 快速读取硬件状态；
- 清除中断；
- 搬运到软件环形队列；
- 记录错误；
- 将复杂逻辑延迟到线程上下文；
- 防止 FIFO 溢出；
- 防止中断风暴。

---

## 5.5 共享内存消息格式

建议使用显式宽度字段，避免直接依赖 C 位域。

```
#define MBOX_MAGIC 0x4D424F58U

struct mbox_msg_hdr {
    uint32_t magic;
    uint16_t version;
    uint16_t header_len;
    uint32_t total_len;
    uint32_t protocol;
    uint32_t message_id;
    uint32_t token;
    uint32_t flags;
    uint32_t crc32;
};
```

消息校验：

```
int mbox_validate_header(const struct mbox_msg_hdr *hdr,
                         size_t buffer_size)
{
    if (hdr == NULL)
        return -EINVAL;

    if (hdr->magic != MBOX_MAGIC)
        return -EPROTO;

    if (hdr->version == 0)
        return -EPROTO;

    if (hdr->header_len < sizeof(*hdr))
        return -EPROTO;

    if (hdr->total_len < hdr->header_len ||
        hdr->total_len > buffer_size)
        return -EMSGSIZE;

    return 0;
}
```

不能只依赖消息长度：

```
/* 错误：缺少整数溢出和边界检查 */
memcpy(local, shmem, hdr->total_len);
```

正确方式：

```
if (hdr->total_len > sizeof(local))
    return -EMSGSIZE;

if (hdr->total_len < hdr->header_len)
    return -EPROTO;

memcpy(local, shmem, hdr->total_len);
```

---

## 5.6 环形队列设计

共享内存环形队列通常包含：

```
struct mbox_ring {
    uint32_t size;
    volatile uint32_t head;
    volatile uint32_t tail;
    uint8_t data[];
};
```

发送：

```
static bool ring_push(struct mbox_ring *ring,
                      const void *data,
                      uint32_t len)
{
    uint32_t head;
    uint32_t next;

    if (len > ring->size - sizeof(uint32_t))
        return false;

    head = ring->head;
    next = (head + sizeof(uint32_t) + len) % ring->size;

    if (next == ring->tail)
        return false;

    memcpy(&ring->data[head], &len, sizeof(len));
    memcpy(&ring->data[head + sizeof(len)],
           data,
           len);

    /*
     * 数据先写入，再发布新的 head。
     */
    dmb_sy();
    ring->head = next;

    return true;
}
```

但上述简单实现有一个重要限制：

- 只适合单生产者、单消费者；
- 不适合多生产者；
- 不处理跨尾部的消息拆分；
- 不处理消费者异常退出；
- 需要对索引和内存屏障进行平台适配。

生产系统中应明确采用：

- SPSC；
- MPSC；
- MPMC；
- 固定长度槽位；
- 变长消息；
- 锁保护；
- 原子 CAS。

### 固定槽位比变长槽位更适合控制面

```
#define MBOX_SLOT_SIZE 256U
#define MBOX_SLOT_COUNT 64U

struct mbox_slot {
    atomic_uint state;
    uint8_t payload[MBOX_SLOT_SIZE];
};
```

优点：

- 不需要处理跨尾部；
- 回收简单；
- 易于做超时和故障恢复；
- 可通过状态位实现所有权转移。

---

## 5.7 Token 与请求响应匹配

同步调用必须为每个请求分配 Token：

```
struct mbox_transaction {
    uint32_t token;
    bool completed;
    int result;
    completion_t done;
    uint8_t response[256];
    size_t response_len;
};
```

发送流程：

```
int mbox_call(struct mbox_chan *ch,
              const void *request,
              size_t request_len,
              void *response,
              size_t response_capacity,
              uint32_t timeout_us)
{
    struct mbox_transaction *xfer;
    uint32_t token;
    int ret;

    xfer = xfer_alloc(ch);
    if (xfer == NULL)
        return -ENOMEM;

    token = token_alloc(ch);
    if (token == 0) {
        xfer_free(xfer);
        return -EBUSY;
    }

    xfer->token = token;
    xfer_register(ch, xfer);

    ret = mbox_post_message(ch, token, request, request_len);
    if (ret != 0)
        goto unregister;

    ret = wait_for_completion_timeout(&xfer->done, timeout_us);
    if (ret != 0)
        goto unregister;

    if (xfer->response_len > response_capacity) {
        ret = -EMSGSIZE;
        goto unregister;
    }

    memcpy(response, xfer->response, xfer->response_len);
    ret = xfer->result;

unregister:
    xfer_unregister(ch, token);
    token_free(ch, token);
    xfer_free(xfer);
    return ret;
}
```

不能在超时后立即释放事务对象，除非已经确保远端不会再访问它。更稳妥的方式是：

```
超时
  |
  +-- 标记事务为 ABORTED
  +-- 禁止复用 Token
  +-- 等待远端迟到响应
  +-- 丢弃迟到响应
  +-- 完成通道恢复
```

否则可能出现：

```
旧请求 Token 7 超时
Token 7 被新请求复用
旧响应返回
旧响应被误交付给新请求
```

---

## 5.8 中断确认与电平触发陷阱

### 错误顺序

```
irq_clear();
read_rx_fifo();
```

如果读取 FIFO 才能让硬件释放中断源，先清中断会导致：

- 清除无效；
- ISR 退出后立即再次触发；
- 形成中断风暴。

### 正确顺序

```
read_rx_fifo();
drain_pending_status();
irq_clear();
readback_irq_status();
```

对电平触发中断，一般需要：

1. 读取所有待处理数据；
2. 清除 FIFO 或状态源；
3. 写中断清除寄存器；
4. 读回状态确认；
5. 如果仍有 pending，继续处理或重新调度。

---

## 5.9 Cache、一致性和内存屏障

### 非一致性平台

发送端：

```
memcpy(shared, request, len);
clean_dcache_range(shared, len);
dsb_sy();
write_doorbell();
```

接收端：

```
read_doorbell_status();
invalidate_dcache_range(shared, len);
dmb_sy();
parse_message(shared);
```

### 一致性平台

即使硬件 Cache 一致，也不能完全省略内存屏障。原因是：

- 编译器可能重排；
- CPU 可能重排；
- 外设观察顺序与 CPU 执行顺序不同；
- Doorbell 寄存器访问可能是 Device Memory。

推荐逻辑：

```
写共享数据
  -> DMB/DSB
  -> 写 Doorbell

读 Doorbell
  -> DMB
  -> 读共享数据
```

具体使用 `dmb sy`、`dsb sy` 还是更窄的域，取决于平台内存模型和硬件手册。

---

## 5.10 Mailbox 与 DMA

对于大块数据：

```
1. 从 DMA Buffer Pool 获取缓冲区
2. 填充描述符
3. Cache Clean
4. Mailbox 发送 Buffer Address + Length
5. 远端 DMA 处理
6. 远端发送完成通知
7. Cache Invalidate
8. 回收 DMA Buffer
```

描述符：

```
struct mbox_dma_desc {
    uint64_t phys_addr;
    uint32_t length;
    uint32_t flags;
    uint32_t token;
    uint32_t reserved;
};
```

必须验证：

- 地址是否属于允许的共享内存范围；
- 长度是否溢出；
- 是否满足 DMA 对齐；
- Buffer 是否已被其他事务占用；
- 远端是否有权限访问；
- 完成后是否只释放一次。

---

# 6. 性能量化分析

## 6.1 实测平台模型

采用以下典型配置：

- 主 CPU：Cortex-A55，1.2 GHz
- 远端控制器：Cortex-M33，200 MHz
- Mailbox：MMIO Doorbell + 共享内存
- 中断控制器：GIC
- 共享内存：Non-cacheable 或硬件一致性内存
- 测量工具：ARM Generic Timer、GPIO、PMU
- 消息大小：32 B、128 B、1 KB、4 KB

以下数据是典型工程范围，实际项目必须在目标 SoC 上复测。

## 6.2 延迟数据

|通信路径|典型延迟|
|---|---|
|同核寄存器通知|0.05～0.2 μs|
|Doorbell + 本地 IRQ|0.5～2 μs|
|Doorbell + 远端 CPU IRQ|1～5 μs|
|共享内存 + 双向 Doorbell|5～20 μs|
|SCMI 简单请求|8～30 μs|
|RPMsg 小消息|10～50 μs|
|DMA 描述符通知|10～80 μs|
|PMIC/PLL 操作|20 μs～10 ms|

端到端延迟：

```
T_total =
T_prepare
+ T_cache
+ T_doorbell
+ T_irq
+ T_remote_dispatch
+ T_service
+ T_response
```

如果：

```
T_prepare = 1.2 μs
T_cache = 2.0 μs
T_doorbell = 0.4 μs
T_irq = 3.5 μs
T_service = 4.0 μs
T_response = 2.5 μs
```

则：

```
T_total = 13.6 μs
```

## 6.3 吞吐量计算

固定长度消息吞吐量：

```
Throughput = Message_Size × Messages_Per_Second
```

例如：

```
消息大小 = 256 B
每秒消息数 = 20,000
吞吐量 = 256 × 20,000 = 5,120,000 B/s ≈ 4.88 MiB/s
```

环形队列受以下因素约束：

```
最大吞吐量 =
min(
    发送端构造速度,
    Mailbox 通知速度,
    接收端中断处理速度,
    远端服务处理速度,
    共享内存带宽
)
```

## 6.4 中断负载

假设：

- 每条消息一次接收中断；
- 每秒 50,000 条消息；
- 单次 ISR 处理 2 μs。

则单核 CPU 中断占用：

```
CPU_Load = 50,000 × 2 μs / 1 s
         = 10%
```

优化方法：

- 一次中断批量读取多个 FIFO 消息；
- 使用共享内存环形队列；
- 使用阈值中断；
- 合并 Doorbell；
- 将高频状态变更改为采样或批量上报；
- 将大数据路径迁移到 DMA。

## 6.5 内存开销

典型配置：

|项目|大小|
|---|---|
|每个 Doorbell 通道状态|64～256 B|
|共享内存控制块|256 B～4 KB|
|64 槽固定消息队列，每槽 256 B|16 KB|
|Token 位图|8～128 B|
|每个事务对象|128～512 B|
|DMA 描述符池|1～64 KB|

例如：

```
4 个通道 × 16 KB = 64 KB
事务对象 32 个 × 256 B = 8 KB
控制结构约 8 KB
总计约 80 KB～100 KB
```

## 6.6 主要瓶颈与优化

|瓶颈|表现|优化|
|---|---|---|
|中断频率过高|CPU 占用高|批量读取、阈值中断|
|共享内存 Cache 操作|延迟抖动|使用一致性内存、缩小 Clean 范围|
|单通道锁竞争|请求排队|多通道、无锁 SPSC|
|远端服务慢|Mailbox 堵塞|异步化、优先级队列|
|FIFO 太小|溢出|软件环形队列、流控|
|Token 线性扫描|分配慢|位图、空闲链表|
|频繁 Doorbell|通知开销大|合并通知、批量发送|
|远端崩溃|请求永久等待|超时、通道复位、状态重建|

---

# 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
消息是否需要跨处理器或跨安全域？
├─ 否
│  └─ 使用本地函数、队列或寄存器
└─ 是
   |
   消息是否大于硬件 FIFO 容量？
   ├─ 否
   │  └─ 使用寄存器 FIFO 或短消息 Mailbox
   └─ 是
      |
      是否需要高吞吐数据传输？
      ├─ 是
      │  └─ DMA/共享内存传数据，Mailbox 只传描述符
      └─ 否
         |
         是否需要请求-响应事务？
         ├─ 是
         │  └─ Shared Memory + Mailbox + Token + Timeout
         └─ 否
            |
            是否需要高频事件通知？
            ├─ 是
            │  └─ Doorbell + Ring Buffer + Batch IRQ
            └─ 否
               └─ 单向 Doorbell 或小型消息 FIFO
```

## 7.2 典型场景

|需求|方案|理由|
|---|---|---|
|Linux 控制 SCP 时钟|SCMI + Mailbox|标准协议、资源集中管理|
|Cortex-A 与 Cortex-M RPC|共享内存 + Doorbell|支持复杂参数和低延迟|
|音频 DSP 控制命令|FIFO Mailbox|消息短、实时性要求高|
|摄像头帧数据|DMA + 共享内存描述符|避免 Mailbox 搬运大数据|
|温度事件上报|Doorbell + 异步消息|不需要同步等待|
|远端启动完成通知|Doorbell|单次事件、数据很少|
|安全世界服务请求|SMC + Mailbox|EL3 负责入口，Mailbox 连接安全 MCU|
|虚拟机间通信|VirtIO/RPMsg + 虚拟 Mailbox|支持虚拟化隔离|

---

# 8. 工程最佳实践

## 8.1 架构设计原则

### 原则一：Mailbox 只负责传输，不承载业务策略

推荐分层：

```
业务驱动
  |
协议层：SCMI / RPMsg / 自定义 RPC
  |
Mailbox Client API
  |
Mailbox Controller Driver
  |
硬件寄存器
```

禁止业务驱动直接访问 Mailbox 控制器寄存器。

### 原则二：控制面和数据面分离

```
控制面：Mailbox + Shared Memory Descriptor
数据面：DMA Buffer / IOVA / Physical Buffer
```

不要通过 Mailbox FIFO 搬运大块数据。

### 原则三：每条消息都可追踪

至少记录：

- 通道 ID；
- 消息类型；
- Token；
- 发送时间；
- 完成时间；
- 返回码；
- 超时次数；
- 重试次数；
- 远端状态。

### 原则四：远端不可信时必须验证所有字段

验证：

- Magic；
- 版本；
- Header 长度；
- 总长度；
- Token；
- 协议 ID；
- 消息 ID；
- Buffer 地址；
- Buffer 长度；
- 权限和所有权。

### 原则五：远端复位后重新建立状态

不能假定远端复位后仍保留：

- Token；
- 通道占用；
- 电源域状态；
- 时钟状态；
- 共享内存索引；
- 正在执行的事务。

必须执行：

```
检测远端复位
  -> 禁止新请求
  -> 标记未完成事务失败
  -> 清空软件队列
  -> 复位 Mailbox
  -> 重新协商协议版本
  -> 查询硬件实际状态
  -> 恢复可用资源
```

## 8.2 选型决策矩阵

|需求|Doorbell|FIFO|Shared Memory|DMA|
|---|---|---|---|---|
|事件通知|高|中|高|低|
|短消息|中|高|高|低|
|大消息|低|低|高|高|
|低延迟|高|高|中|中|
|高吞吐|低|中|高|极高|
|软件复杂度|低|中|中|高|
|故障恢复|高|中|中|低|
|数据零拷贝|否|否|是|是|
|适合 SCMI|高|中|高|中|
|适合视频/音频数据|低|低|中|高|

## 8.3 工业级编码规范

- 所有寄存器使用固定宽度类型。
- 禁止对硬件寄存器使用普通结构体直接批量赋值。
- 所有中断状态先读后清，并确认清除结果。
- 明确寄存器访问的 `volatile`、内存属性和屏障策略。
- 不在 ISR 中执行阻塞操作。
- 不在 ISR 中调用可能睡眠的锁。
- 所有同步请求设置绝对超时。
- Token 不得在迟到响应尚未处理前复用。
- 共享内存消息明确字节序和版本。
- 设备端必须限制最大消息长度。
- 远端复位后必须重新初始化协议状态。
- 对 FIFO 溢出、下溢和非法消息计数。
- 发送失败必须区分 `-EBUSY`、`-ETIMEDOUT`、`-EIO` 和 `-EPROTO`。
- 通过设备树或 ACPI 描述通道和中断资源。
- 业务层不得依赖具体 Mailbox 寄存器布局。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：Doorbell 先于共享内存发布

### 错误代码

```
write_reg(MBOX_DOORBELL_SET, channel);
memcpy(shmem, request, request_len);
```

### 根因

接收端可能在读取共享内存前已经收到中断，导致读取旧数据或未完成数据。

### 正确实现

```
memcpy(shmem, request, request_len);
clean_dcache_range(shmem, request_len);
dsb_sy();

write_reg(MBOX_DOORBELL_SET, channel);
```

### 风险影响

- 偶发协议解析失败；
- 高负载下数据不一致；
- 远端执行旧命令；
- 产生难以复现的系统故障。

---

## 9.2 错误二：中断只清状态，不清真正的中断源

### 错误代码

```
write_reg(MBOX_IRQ_CLEAR, MBOX_IRQ_RX);
return;
```

### 根因

RX FIFO 仍有数据，电平触发中断条件仍然成立。

### 正确实现

```
while (!rx_fifo_empty()) {
    data = read_rx_fifo();
    push_rx_queue(data);
}

write_reg(MBOX_IRQ_CLEAR, MBOX_IRQ_RX);
read_reg(MBOX_IRQ_STATUS);
```

### 风险影响

- 中断风暴；
- CPU 长时间停留在 ISR；
- 系统调度延迟；
- 看门狗复位。

---

## 9.3 错误三：发送不检查 FIFO 满状态

### 错误代码

```
write_reg(MBOX_TX_DATA, word);
write_reg(MBOX_DOORBELL_SET, channel);
```

### 根因

发送 FIFO 已满时，写入可能丢弃、覆盖或触发硬件错误。

### 正确实现

```
ret = wait_tx_space(ch, timeout_us);
if (ret != 0)
    return ret;

write_reg(MBOX_TX_DATA, word);
dsb_sy();
write_reg(MBOX_DOORBELL_SET, channel);
```

### 风险影响

- 消息丢失；
- 请求响应永久等待；
- 远端状态机失步；
- 后续所有消息解析错误。

---

## 9.4 错误四：超时后立即复用 Token

### 错误代码

```
ret = wait_response(xfer, timeout_us);

token_free(xfer->token);
xfer_free(xfer);

/* 下一个请求直接复用相同 Token */
```

### 根因

旧请求可能仍在远端执行，迟到响应会被识别为新请求响应。

### 正确实现

```
ret = wait_response(xfer, timeout_us);

if (ret == -ETIMEDOUT) {
    xfer->state = XFER_ABORTED;
    token_quarantine(ch, xfer->token);
    channel_recovery_schedule(ch);
}
```

只有在通道恢复或确认迟到响应已处理后，才允许复用 Token。

### 风险影响

- 响应错配；
- 电源、时钟和复位状态被错误修改；
- 内存破坏；
- 系统随机崩溃。

---

## 9.5 错误五：把 Mailbox 当作大数据通道

### 错误代码

```
for (i = 0; i < frame_size; i += 4)
    write_reg(MBOX_TX_DATA, frame[i]);
```

### 根因

Mailbox FIFO 容量有限，且每个字都需要寄存器访问和状态管理。

### 正确实现

```
desc.phys_addr = dma_addr;
desc.length = frame_size;
desc.flags = DMA_TO_REMOTE;
desc.token = token;

clean_dcache_range(dma_buffer, frame_size);
mbox_send_descriptor(ch, &desc);
```

### 风险影响

- 吞吐量低；
- CPU 占用高；
- FIFO 溢出；
- 实时任务被大量寄存器访问拖慢。

---

## 9.6 错误六：ISR 中执行同步 RPC

### 错误代码

```
void mbox_irq_handler(void)
{
    read_event();
    scmi_clock_set_rate(600000000); /* 可能等待远端 */
}
```

### 根因

ISR 中执行不可控时长操作，可能再次等待同一个 Mailbox。

### 正确实现

```
void mbox_irq_handler(void)
{
    event = read_event();
    queue_work(&event_work, event);
}

void event_worker(void *arg)
{
    scmi_clock_set_rate(600000000);
}
```

### 风险影响

- 中断嵌套；
- 死锁；
- 丢失后续中断；
- 破坏实时性。

---

# 10. 多机制组合使用方案

## 10.1 推荐的 SCMI Mailbox 架构

```
Linux Client
  |
SCMI Protocol Driver
  |
SCMI Transport
  |
Mailbox Client
  |
+-----------------------------+
| Shared Memory               |
| Header + Payload + Status   |
+-----------------------------+
  |
Mailbox Controller
  |
IRQ / Doorbell
  |
SCP SCMI Server
  |
Clock / Power / Perf / Sensor
```

### 通道划分

|通道|方向|用途|
|---|---|---|
|Command Channel|双向|同步控制请求|
|Notification Channel|SCP -> Linux|异步事件|
|High Priority Channel|双向|紧急安全控制|
|Bulk Channel|双向|大消息和批量操作|
|Recovery Channel|双向|远端恢复和状态重建|

## 10.2 完整事务框架

```
struct mbox_transport {
    struct mbox_chan *cmd;
    struct mbox_chan *notify;
    struct mbox_chan *recovery;
    mutex_t cmd_lock;
    atomic_uint next_token;
    struct xfer_table pending;
};

int transport_call(struct mbox_transport *t,
                   uint32_t protocol,
                   uint32_t message_id,
                   const void *request,
                   size_t request_len,
                   void *response,
                   size_t response_len,
                   uint32_t timeout_us)
{
    struct mbox_msg_hdr hdr;
    uint32_t token;
    int ret;

    if (request_len > MBOX_MAX_PAYLOAD)
        return -EMSGSIZE;

    token = transport_alloc_token(t);
    if (token == 0)
        return -EBUSY;

    hdr.magic = MBOX_MAGIC;
    hdr.version = 1;
    hdr.header_len = sizeof(hdr);
    hdr.total_len = sizeof(hdr) + request_len;
    hdr.protocol = protocol;
    hdr.message_id = message_id;
    hdr.token = token;
    hdr.flags = MBOX_FLAG_REQUEST;
    hdr.crc32 = 0;

    ret = xfer_prepare(t, &hdr, response, response_len);
    if (ret != 0)
        goto out_token;

    ret = mbox_send_shared(t->cmd, &hdr, request, request_len);
    if (ret != 0)
        goto out_xfer;

    ret = xfer_wait(t, token, timeout_us);
    if (ret != 0)
        goto out_xfer;

    ret = xfer_copy_response(t, token, response, response_len);

out_xfer:
    xfer_remove(t, token);
out_token:
    transport_release_token(t, token);
    return ret;
}
```

## 10.3 异步通知框架

```
struct mbox_event {
    uint32_t protocol;
    uint32_t event_id;
    uint32_t payload_len;
    uint8_t payload[128];
};

void mbox_notification_isr(struct mbox_chan *ch)
{
    struct mbox_event event;

    if (read_event_from_shared_memory(&event) != 0) {
        ch->protocol_errors++;
        return;
    }

    if (!event_queue_push_isr(&event)) {
        ch->event_dropped++;
        return;
    }

    schedule_event_worker();
}

void notification_worker(void)
{
    struct mbox_event event;

    while (event_queue_pop(&event)) {
        dispatch_event(&event);
    }
}
```

---

# 11. 工业级实际案例分析

## 11.1 案例一：Linux 与 SCP 的 SCMI 控制通道

### 需求

- Linux 管理 CPU 频率、电源域和温度策略；
- SCP 管理 PMIC、PLL 和时钟树；
- 控制请求必须支持超时；
- SCP 复位后 Linux 能够重新建立通信。

### 架构

```
Linux SCMI Driver
      |
      v
Mailbox Client
      |
      +-- Shared Memory
      +-- Doorbell IRQ
      |
      v
SCP SCMI Server
      |
      +-- Clock Manager
      +-- Power Manager
      +-- Thermal Manager
```

### 设计要点

- 共享内存中只放一条当前事务或使用环形队列。
- Doorbell 触发请求。
- SCP 完成后写响应并触发返回中断。
- Linux 通过 Token 匹配响应。
- 超时后进入通道恢复状态。
- SCP 重启后重新执行 SCMI Base 协商和资源状态查询。

### 关键状态机

```
IDLE
  -> TX_BUSY
  -> WAIT_RESPONSE
  -> COMPLETE
  -> IDLE

WAIT_RESPONSE
  -> TIMEOUT
  -> RECOVERY
  -> REINIT
  -> IDLE
```

---

## 11.2 案例二：Cortex-A 与 Cortex-M 的实时控制 RPC

### 11.2.1 需求与约束

系统由 Cortex-A 与 Cortex-M 构成异构控制平台：

- **Cortex-A**：运行 Linux，负责配置管理、诊断、日志和非实时策略。
- **Cortex-M**：运行 RTOS，负责电机控制、传感器采集或执行器闭环。
- Linux 向 Cortex-M 下发参数、模式切换和控制命令。
- Cortex-M 向 Linux 上报故障、状态和实时事件。
- 高频采样数据不经过 Mailbox FIFO，而通过 **DMA Buffer + 描述符** 传递。
- Cortex-M 的控制环不能因为 Linux 阻塞、调度抖动或重启而失去确定性。

关键约束是：**Mailbox 只承载控制面通知，实时数据面必须与控制面解耦。**

### 11.2.2 总体架构

```
Cortex-A / Linux
├── RPC Client
├── Command Mailbox
├── Event Mailbox
├── DMA Buffer Manager
└── Recovery Manager
        |
        | Shared Memory + Doorbell + IRQ
        v
+---------------------------------------+
| Mailbox Controller                    |
| TX/RX FIFO, Doorbell, IRQ, Status     |
+-------------------+-------------------+
                    |
                    v
Cortex-M / RTOS
├── RPC Server Task
├── Command ISR/Queue
├── Real-time Control Task
├── Event Producer
├── DMA Engine
└── Watchdog/Fault Manager
```

数据路径分为三类：

```
控制命令：
Cortex-A -> Command Ring -> Doorbell -> Cortex-M RPC Server

实时事件：
Cortex-M -> Event Ring -> Doorbell -> Cortex-A Worker

采样数据：
Cortex-M -> DMA Buffer -> Descriptor Mailbox -> Cortex-A
```

### 11.2.3 通道划分

|通道|方向|传输内容|实时要求|设计方式|
|---|---|---|---|---|
|Command|A → M|配置、模式、参数|中|共享内存环 + Doorbell|
|Response|M → A|RPC 响应|中|Token + 响应环|
|Event|M → A|告警、状态、故障|高|独立事件环 + 批量中断|
|Data Descriptor|双向|DMA 缓冲区描述符|高|固定长度描述符|
|Recovery|双向|心跳、复位、状态重建|最高|独立高优先级通道|

**Command、Event 和 Recovery 不应共用一个不可并发的同步通道。** 否则大量配置请求可能阻塞故障通知，导致系统在真正需要保护时无法及时响应。

### 11.2.4 消息格式设计

协议消息必须固定字段宽度、明确字节序和版本，不应使用 C 位域直接定义跨处理器 ABI。

```
#include <stdint.h>
#include <stddef.h>

#define RPC_MAGIC              0x52504331U /* "RPC1" */
#define RPC_VERSION            1U
#define RPC_MAX_PAYLOAD        192U
#define RPC_FLAG_REQUEST       (1U << 0)
#define RPC_FLAG_RESPONSE      (1U << 1)
#define RPC_FLAG_EVENT         (1U << 2)
#define RPC_FLAG_ACK_REQUIRED  (1U << 3)

struct rpc_header {
    uint32_t magic;
    uint16_t version;
    uint16_t header_len;
    uint32_t total_len;
    uint32_t service;
    uint32_t command;
    uint32_t token;
    uint32_t flags;
    int32_t  status;
    uint32_t crc32;
};

struct rpc_message {
    struct rpc_header header;
    uint8_t payload[RPC_MAX_PAYLOAD];
};
```

#### 消息校验

```
static int rpc_validate(const struct rpc_message *msg,
                        size_t buffer_size)
{
    const struct rpc_header *h;

    if (msg == NULL || buffer_size < sizeof(struct rpc_header))
        return -1;

    h = &msg->header;

    if (h->magic != RPC_MAGIC || h->version != RPC_VERSION)
        return -2;

    if (h->header_len < sizeof(struct rpc_header) ||
        h->header_len > buffer_size)
        return -3;

    if (h->total_len < h->header_len ||
        h->total_len > buffer_size ||
        h->total_len - h->header_len > RPC_MAX_PAYLOAD)
        return -4;

    if ((h->flags & (RPC_FLAG_REQUEST | RPC_FLAG_RESPONSE)) ==
        (RPC_FLAG_REQUEST | RPC_FLAG_RESPONSE))
        return -5;

    return 0;
}
```

生产系统还应校验：

- `service` 和 `command` 是否在允许范围内；
- `token` 是否属于当前通道；
- 请求方是否具有对应服务权限；
- CRC 是否有效；
- 消息是否已被重复消费；
- 版本是否兼容。

### 11.2.5 Cortex-A 发送命令

Cortex-A 侧负责分配 Token、登记待完成事务、发布消息并等待响应。

```
struct rpc_xfer {
    uint32_t token;
    bool completed;
    bool aborted;
    int result;
    completion_t done;
    uint8_t response[RPC_MAX_PAYLOAD];
    size_t response_len;
};

int rpc_call(struct rpc_client *client,
             uint32_t service,
             uint32_t command,
             const void *payload,
             size_t payload_len,
             void *response,
             size_t response_capacity,
             uint32_t timeout_us)
{
    struct rpc_xfer *xfer;
    struct rpc_message msg;
    int ret;

    if (client == NULL || payload == NULL || response == NULL)
        return -EINVAL;

    if (payload_len > RPC_MAX_PAYLOAD)
        return -EMSGSIZE;

    xfer = rpc_xfer_alloc(client);
    if (xfer == NULL)
        return -ENOMEM;

    ret = rpc_token_alloc(client, &xfer->token);
    if (ret != 0)
        goto out_free_xfer;

    memset(&msg, 0, sizeof(msg));
    msg.header.magic = RPC_MAGIC;
    msg.header.version = RPC_VERSION;
    msg.header.header_len = sizeof(struct rpc_header);
    msg.header.total_len = sizeof(struct rpc_header) + payload_len;
    msg.header.service = service;
    msg.header.command = command;
    msg.header.token = xfer->token;
    msg.header.flags = RPC_FLAG_REQUEST;
    memcpy(msg.payload, payload, payload_len);
    msg.header.crc32 = rpc_crc32(&msg, msg.header.total_len);

    ret = rpc_register_pending(client, xfer);
    if (ret != 0)
        goto out_token;

    ret = ring_push_producer(&client->command_ring,
                             &msg,
                             msg.header.total_len);
    if (ret != 0)
        goto out_pending;

    /* 发布共享内存内容后才能敲 Doorbell */
    clean_dcache_range(&client->command_ring, sizeof(msg));
    dsb_sy();
    mailbox_ring(client->command_channel);

    ret = wait_for_completion_timeout(&xfer->done, timeout_us);
    if (ret != 0) {
        xfer->aborted = true;
        rpc_token_quarantine(client, xfer->token);
        rpc_schedule_recovery(client);
        goto out_pending;
    }

    if (xfer->response_len > response_capacity) {
        ret = -EMSGSIZE;
        goto out_pending;
    }

    memcpy(response, xfer->response, xfer->response_len);
    ret = xfer->result;

out_pending:
    rpc_unregister_pending(client, xfer->token);
out_token:
    if (!xfer->aborted)
        rpc_token_free(client, xfer->token);
out_free_xfer:
    rpc_xfer_free(xfer);
    return ret;
}
```

#### 关键设计点

1. **先登记事务，再发送消息**，避免远端响应过快导致响应找不到接收对象。
2. Token 超时后进入隔离区，不能立即复用。
3. 共享内存发布必须先于 Doorbell。
4. 远端返回的长度、状态和 Token 都必须重新校验。
5. 超时不是简单的“重发”，而是一次通道健康状态转换。

### 11.2.6 Cortex-M 接收与处理

ISR 只负责清除硬件事件、搬运索引和唤醒 RPC 任务，不能在中断中执行复杂业务。

```
void mbox_command_isr(struct mbox_channel *ch)
{
    uint32_t irq;

    irq = mbox_irq_status(ch);

    if ((irq & MBOX_IRQ_RX_PENDING) != 0U) {
        /* 先消费真正的中断源，再清除中断状态 */
        while (!mailbox_rx_empty(ch))
            command_event_set_from_isr(ch);

        mailbox_irq_clear(ch, MBOX_IRQ_RX_PENDING);
        rtos_task_notify_from_isr(ch->rpc_task);
    }

    if ((irq & MBOX_IRQ_ERROR) != 0U) {
        ch->error_count++;
        mailbox_irq_clear(ch, MBOX_IRQ_ERROR);
        rtos_task_notify_from_isr(ch->recovery_task);
    }
}
```

RPC 任务在任务上下文中完成解析和执行：

```
void rpc_server_task(void *arg)
{
    struct rpc_message msg;
    struct rpc_message response;
    int ret;

    for (;;) {
        rtos_task_wait_notification(RTOS_WAIT_FOREVER);

        while (ring_pop_consumer(&rpc_cmd_ring,
                                 &msg,
                                 sizeof(msg)) == 0) {
            ret = rpc_validate(&msg, sizeof(msg));
            if (ret != 0) {
                rpc_send_error(&msg, -EPROTO);
                continue;
            }

            if (!rpc_authorize(msg.header.service,
                               msg.header.command)) {
                rpc_send_error(&msg, -EACCES);
                continue;
            }

            memset(&response, 0, sizeof(response));
            ret = rpc_dispatch(&msg, &response);
            response.header.status = ret;
            response.header.flags = RPC_FLAG_RESPONSE;
            response.header.token = msg.header.token;
            response.header.crc32 = rpc_crc32(&response,
                                              response.header.total_len);

            if (ring_push_producer(&rpc_rsp_ring,
                                   &response,
                                   response.header.total_len) != 0) {
                fault_report(RPC_RESPONSE_RING_FULL);
                break;
            }
        }

        dsb_sy();
        mailbox_ring(&response_channel);
    }
}
```

### 11.2.7 实时事件与数据面设计

Cortex-M 不应因为 Linux 没有及时读取事件而阻塞控制任务。事件环需要定义溢出策略：

|事件类型|环满时策略|
|---|---|
|普通状态|丢弃旧状态，保留最新值|
|故障告警|保留并触发独立故障通道|
|控制确认|不允许丢失，使用 ACK/重试|
|统计数据|批量丢弃并累计丢包计数|

采样数据采用 DMA 描述符：

```
struct dma_desc {
    uint64_t address;
    uint32_t length;
    uint32_t sequence;
    uint32_t flags;
    uint32_t crc32;
};

int publish_sample(struct dma_desc *desc,
                   void *buffer,
                   size_t length,
                   uint32_t sequence)
{
    if (desc == NULL || buffer == NULL || length == 0U)
        return -EINVAL;

    if (!dma_address_allowed(buffer, length) ||
        length > MAX_SAMPLE_SIZE)
        return -EACCES;

    desc->address = dma_phys_addr(buffer);
    desc->length = (uint32_t)length;
    desc->sequence = sequence;
    desc->flags = DMA_DESC_VALID;
    desc->crc32 = crc32(buffer, length);

    clean_dcache_range(buffer, length);
    clean_dcache_range(desc, sizeof(*desc));
    dsb_sy();
    mailbox_ring(&data_descriptor_channel);

    return 0;
}
```

必须防止：

- DMA 地址越界；
- Buffer 被提前回收；
- 同一描述符重复释放；
- 序号回绕未处理；
- Cache 未清理导致远端读到旧数据；
- Linux 侧读取时远端仍在写入。

### 11.2.8 故障与恢复策略

#### Cortex-M 看门狗复位

```
Linux 检测心跳超时
        |
        v
禁止新 RPC 请求
        |
        v
将所有 pending 事务标记为 -EHOSTDOWN
        |
        v
复位 Mailbox 控制器和共享环索引
        |
        v
等待 Cortex-M 发布 READY
        |
        v
重新协商协议版本和能力
        |
        v
查询当前硬件状态
        |
        v
恢复必要资源，重新开放服务
```

#### 幂等性要求

适合重试的命令：

- 设置目标转速；
- 设置采样周期；
- 设置目标频率；
- 查询当前状态。

不应盲目重试的命令：

- 触发一次性执行器动作；
- 清除故障锁存；
- 启动不可逆硬件操作；
- 写入只允许执行一次的校准流程。

### 11.2.9 性能预算示例

假设控制命令仅允许占用 **50 μs** 的非实时预算：

|阶段|预算|
|---|---|
|Linux 消息构造|2 μs|
|Cache/屏障|3 μs|
|Doorbell 与中断|5 μs|
|Cortex-M 任务调度|8 μs|
|RPC 解析|4 μs|
|服务执行|20 μs|
|响应返回|8 μs|
|合计|50 μs|

如果实测 P99 超过预算，优先检查：

1. 是否与高优先级 DMA 或中断竞争；
2. 是否错误地共用事件和命令通道；
3. 是否在 Cortex-M 上使用动态内存；
4. 是否存在 Cache Clean 的整页操作；
5. 是否把高频数据误走 RPC 控制路径。

### 11.2.10 案例结论

该架构的核心不是“把 Linux 和 Cortex-M 连起来”，而是建立清晰的**控制面、事件面、数据面和恢复面**：

- Mailbox 负责通知和少量控制消息；
- 共享内存负责消息承载；
- DMA 负责大数据；
- Token 负责事务匹配；
- 超时和隔离机制负责防止迟到响应污染新事务；
- 独立 Recovery 通道负责远端复位后的状态重建；
- Cortex-M 的实时控制任务必须与 Linux 的 RPC 服务解耦。

---

## 11.3 案例三：音频 DSP 的低延迟控制与数据传输

### 需求

- Cortex-A 运行 Linux 音频框架；
- DSP 执行音频滤波、回声消除和采样率转换；
- 控制参数需要低延迟下发；
- PCM 数据不能通过 Mailbox FIFO 传输；
- DSP 异常时 Linux 必须能够检测并恢复。

### 架构

```
Linux Audio Stack
├── Control RPC
├── PCM DMA Buffer Pool
├── Completion Queue
└── DSP Recovery Manager
        |
        +-- Control Mailbox
        +-- Event Mailbox
        +-- DMA Descriptor Ring
        v
DSP Firmware
├── Command Task
├── Audio Processing Loop
├── DMA Completion ISR
└── Health Monitor
```

### 设计要点

- 控制参数通过固定长度 Mailbox 消息传递。
- PCM buffer 使用预分配的 DMA 内存池。
- Mailbox 只发送 buffer 地址、长度、时间戳和序号。
- 音频数据路径不持有控制通道锁。
- DSP 复位后，Linux 丢弃旧 descriptor，重新建立音频 pipeline。
- 通过 sequence number 检测丢包、重复消费和乱序。

典型端到端延迟预算：

```
控制消息：5～30 μs
DMA 描述符通知：10～80 μs
音频处理延迟：由 frame size 和 DSP 算法决定
```

例如 48 kHz、128 samples/frame：

```
Frame_Time = 128 / 48000 ≈ 2.67 ms
```

Mailbox 延迟应显著小于一个音频 frame，否则控制更新可能跨 frame 生效，造成听感或时序问题。

---

# 12. 高频问题深度答疑

## 问题一：Mailbox 和 IPI 有什么区别？

**IPI 本质上是处理器间中断，Mailbox 是带有通道状态、消息寄存器、FIFO 或 Doorbell 语义的硬件通信机制。**

IPI 通常只表示“有事件发生”；Mailbox 可以额外提供：

- FIFO 空满状态；
- 发送完成状态；
- 接收挂起状态；
- 通道复位；
- 错误状态；
- 多通道隔离。

实际平台中 Mailbox 可能底层使用 IPI，但软件抽象层次不同。

## 问题二：为什么 Doorbell 不能代替共享内存？

Doorbell 只携带事件，不携带复杂数据。它无法可靠承载：

- 大于寄存器宽度的结构体；
- 可变长度消息；
- DMA 描述符集合；
- 多条排队事务。

正确组合是：**共享内存保存数据，Doorbell 负责通知。**

## 问题三：共享内存已经硬件 Cache 一致，为什么还需要屏障？

Cache 一致性保证的是缓存副本最终能够观察到一致内容，但不一定保证“共享数据写入先于 Doorbell 被远端观察”。

屏障用于约束访问顺序：

```
写数据 -> DMB/DSB -> 写 Doorbell
读 Doorbell -> DMB -> 读数据
```

具体屏障域和类型必须结合 ARM 内存模型、设备属性及 SoC 手册确定。

## 问题四：Mailbox 超时后为什么不能立即重试？

因为超时只表示本端在规定时间内没有观察到响应，不代表远端没有执行请求。远端可能：

- 已经完成但响应中断丢失；
- 仍在执行；
- 已写响应但本端尚未读取；
- 已经复位。

必须先判断操作幂等性、隔离旧 Token，并确认通道状态后再决定重试。

## 问题五：单通道和多通道如何选择？

|场景|推荐|
|---|---|
|低频启动配置|单通道|
|控制命令与异步事件并存|至少双通道|
|高优先级故障通知|独立高优先级通道|
|多租户或多 VM|按安全域/租户隔离通道|
|高吞吐数据|DMA 描述符通道 + 独立数据面|

多通道会增加硬件和软件资源，但可以显著降低锁竞争和优先级反转风险。

## 问题六：为什么 ISR 中不能直接调用 Mailbox 同步 API？

同步 API 可能：

- 获取睡眠锁；
- 等待远端响应；
- 触发同一通道中断；
- 进入调度器；
- 持有资源等待另一个中断释放。

因此 ISR 应只完成状态读取、FIFO 搬运、中断确认和唤醒工作线程，复杂处理放到线程上下文。

---

# 13. 课程核心总结

1. **Mailbox 是通信基础设施，不是业务协议。**
2. **Doorbell 负责通知，Shared Memory 负责承载，DMA 负责大数据。**
3. 中断处理必须先处理真正的中断源，再清除中断状态。
4. 跨处理器共享内存必须明确 Cache、一致性、内存屏障和所有权转移。
5. 同步 RPC 必须具备 Token、超时、响应校验和事务回收机制。
6. 超时后的 Token 必须隔离，不能立即复用。
7. 控制面、事件面、数据面和恢复面应分离设计。
8. ISR 不做阻塞操作，不调用可能睡眠的锁，不执行不可控时长 RPC。
9. 远端处理器复位后必须重建通道、协议能力和硬件资源状态。
10. **工业级 Mailbox 的核心指标不是“能发消息”，而是可证明的顺序性、可靠性、实时性和可恢复性。**

## 性能排序

```
本地寄存器通知
    <
本地 Doorbell
    <
远端 IRQ Doorbell
    <
共享内存 + Doorbell
    <
SCMI/RPMsg 协议事务
    <
DMA 描述符通知
    <
远端 PLL/PMIC/电源状态转换
```

## 通用选型结论

- 单次事件：**Doorbell**。
- 短控制消息：**寄存器 FIFO Mailbox**。
- 复杂请求响应：**Shared Memory + Doorbell + Token**。
- 高频事件：**Ring Buffer + 批量中断**。
- 大块数据：**DMA + Descriptor Mailbox**。
- 平台资源管理：**SCMI over Mailbox**。
- 异构处理器通信：**Mailbox + Shared Memory + OpenAMP/RPMsg**。

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|首选方案|
|---|---|
|单次唤醒通知|Doorbell|
|小于 FIFO 容量的命令|寄存器 FIFO|
|Linux 与 SCP 控制|SCMI + Mailbox|
|A 与 M 请求响应|共享内存环 + Doorbell + Token|
|温度/故障异步通知|独立 Event Mailbox|
|音视频帧传输|DMA Buffer + 描述符 Mailbox|
|高优先级故障恢复|独立 Recovery Channel|
|虚拟机通信|VirtIO/RPMsg + 虚拟 Mailbox|

## 14.2 故障处理速查表

|故障|首要动作|是否可直接重试|
|---|---|---|
|TX FIFO 满|等待或返回 `-EBUSY`|视命令而定|
|RX FIFO 溢出|记录、清空、重建队列|否|
|响应超时|隔离 Token、检查远端|否|
|CRC 错误|丢弃消息、计数、上报|仅幂等操作|
|Token 不匹配|丢弃并记录|否|
|远端复位|失败所有 pending、重新初始化|需重新协商|
|Doorbell 卡死|复位控制器、读回状态|需确认状态|

## 14.3 推荐延迟与容量经验值

|项目|典型范围|
|---|---|
|本地 Doorbell|0.05～2 μs|
|远端 IRQ 通知|1～5 μs|
|共享内存 RPC|5～20 μs|
|SCMI 小事务|8～30 μs|
|单个控制消息|64～256 B|
|固定槽位数量|32～256|
|同步事务超时|100 μs～100 ms，按业务定义|

以上数据只能作为预算起点，必须在目标 SoC 上采集 P50、P95、P99 和最大值。

---

# 15. 学习效果自检

完成本课后，应能够：

- 画出 Doorbell、FIFO、共享内存和 DMA 的通信路径。
- 说明 Mailbox 与 IPI、SCMI、RPMsg 的职责边界。
- 根据硬件手册正确处理 FIFO 空满和 IRQ 状态位。
- 编写发送端的超时等待和中断触发流程。
- 编写不会阻塞的 Mailbox ISR。
- 设计 SPSC 环形队列并说明其适用边界。
- 设计带 Token 的同步 RPC 事务表。
- 解释超时后 Token 隔离的必要性。
- 处理非一致性 Cache 平台上的 Clean/Invalidate 流程。
- 设计 DMA 描述符的地址、长度、权限和生命周期校验。
- 设计远端处理器复位后的通道恢复状态机。
- 计算中断频率、消息吞吐量和端到端延迟。
- 说明为什么控制面和数据面必须分离。
- 识别 ISR 中同步 RPC、Doorbell 顺序错误和 IRQ 清除错误。
- 设计 Linux + Cortex-M 的实时控制 RPC 架构。

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：实现裸机 Doorbell 通道

要求：

- 配置 TX、RX、IRQ 和 Doorbell 寄存器；
- 实现发送超时；
- 实现接收中断；
- 处理电平触发和边沿触发差异；
- 记录 FIFO 满、空和错误次数。

### 任务二：实现共享内存 SPSC 环

要求：

- 固定槽位；
- 单生产者、单消费者；
- 明确发布和消费屏障；
- 支持环满、环空和序号回绕；
- 注入消费者暂停和生产者突发流量故障。

### 任务三：实现同步 RPC

要求：

- Token 分配与回收；
- pending transaction 表；
- 响应校验；
- 超时和迟到响应丢弃；
- 错误码映射；
- P50/P95/P99 延迟统计。

### 任务四：加入 DMA 数据面

要求：

- 建立 DMA Buffer Pool；
- 实现描述符队列；
- 校验物理地址、长度和权限；
- 处理 Cache Clean/Invalidate；
- 防止重复释放和 Buffer 生命周期错误。

### 任务五：实现远端复位恢复

故障注入包括：

- 远端不响应；
- 丢失接收中断；
- FIFO 溢出；
- 错误 Token；
- 错误 CRC；
- 远端任务死锁；
- Cortex-M 看门狗复位。

验收标准：

- 本端不能永久阻塞；
- 旧响应不能污染新事务；
- 能够记录通道、Token、时间戳和错误原因；
- 能够重新协商协议并恢复到安全状态。

## 16.2 性能测试方法

### 延迟测试

```
1. 读取 Generic Timer 起始值
2. 写入共享内存
3. 执行必要的 Cache 操作和屏障
4. 写 Doorbell
5. 远端执行并返回响应
6. 读取结束值
7. 统计 P50、P95、P99、最大值
```

### 吞吐测试

分别测试：

- 32 B、128 B、256 B、1 KB 消息；
- 单条发送和批量发送；
- 单通道和多通道；
- 轮询、中断和批量中断；
- Cacheable、Non-cacheable 和硬件一致内存。

### 必须采集的指标

|指标|目的|
|---|---|
|平均延迟|常态性能|
|P99 延迟|实时性|
|最大延迟|最坏情况|
|消息吞吐量|容量评估|
|IRQ 次数|中断优化|
|FIFO 溢出数|流控可靠性|
|Token 冲突数|并发正确性|
|超时率|远端稳定性|
|恢复时间|系统韧性|
|丢事件数|数据完整性|
|DMA Buffer 利用率|数据面效率|

## 16.3 进阶学习方向

### 驱动与内核

- Linux Mailbox Framework；
- `drivers/mailbox/` 控制器驱动；
- `remoteproc` 与 `rpmsg`；
- OpenAMP VirtIO；
- DMA-BUF 与 IOMMU；
- NAPI、workqueue 和 threaded IRQ。

### 固件与 RTOS

- Cortex-M NVIC 和中断优先级；
- FreeRTOS/Zephyr 的 ISR-Task 通信；
- 远端固件启动和健康监测；
- 无锁 SPSC/MPSC 队列；
- 看门狗与故障安全状态机。

### 系统架构

- SCMI over Mailbox；
- Linux + SCP 电源管理；
- RPMsg/OpenAMP 异构通信；
- 多租户和虚拟化 Mailbox；
- 安全世界与普通世界通道隔离；
- 功能安全通信监控器；
- Mailbox 协议的形式化验证与故障注入。

## 最终能力目标

能够从以下维度评审一套 Mailbox 架构：

```
硬件通道模型
FIFO/队列容量
Doorbell 语义
中断触发方式
寄存器访问顺序
Cache 一致性
内存屏障
Token 生命周期
并发模型
超时策略
远端复位恢复
控制面/数据面分离
DMA 权限
实时性预算
故障可观测性
安全隔离
跨平台迁移成本
```

最终应形成如下工程判断：

> **Mailbox 不是“写一个寄存器就完成通信”，而是一套包含硬件状态、内存可见性、中断确认、事务匹配、流量控制和故障恢复的跨处理器通信基础设施。