
## 1. 学习目标

### 理解

- 理解 CAN 总线的**无主通信模型、仲裁机制、错误检测机制和帧格式**。
- 理解 Classical CAN 与 CAN-FD 在**速率、帧结构、CRC、数据长度和控制器资源**上的差异。
- 理解 CAN 驱动中发送邮箱、接收 FIFO、过滤器、错误状态和总线恢复之间的关系。
- 理解 CAN 的实时性并非只由波特率决定，还受到**总线利用率、仲裁优先级、帧长度和中断延迟**影响。

### 掌握

- 掌握 CAN / CAN-FD 控制器初始化、位时序计算、过滤器配置和收发流程。
- 掌握基于中断和 DMA/Message RAM 的接收架构。
- 掌握发送队列、接收队列、超时、错误处理和总线离线恢复。
- 掌握标准帧、扩展帧、远程帧、BRS、ESI、错误帧和过载帧的工程含义。

### 精通

- 能够分析**优先级反转、发送邮箱耗尽、RX FIFO 溢出、错误主动/错误被动和 Bus-Off**。
- 能够根据消息周期、最大延迟和总线负载设计 CAN ID 优先级。
- 能够从寄存器、Message RAM、ISR 和协议栈边界分析驱动性能。
- 能够设计支持 Classical CAN、CAN-FD、时间戳、错误统计和诊断的统一驱动接口。

### 能够设计

- 能够设计适用于量产 ECU、机器人控制器、BMS、网关和工业控制器的 CAN/CAN-FD 驱动。
- 能够建立从底层控制器到信号解码、诊断协议和应用任务的分层架构。
- 能够制定总线负载、端到端延迟、错误恢复和压力测试方案。
- 能够为高可靠系统设计冗余、故障降级、总线隔离和运行时诊断机制。

---

## 2. 前置要求

### 知识要求

- C 语言：指针、结构体、位操作、`volatile`、内存屏障、环形队列。
- MCU：中断控制器、时钟树、GPIO 复用、定时器和 DMA 基础。
- RTOS：任务、ISR、队列、信号量、临界区和优先级调度。
- 数字通信：串行通信、采样、时钟误差、CRC 和差分信号。
- 基本网络概念：优先级、广播、过滤、拥塞和故障隔离。

### 技能要求

- 能阅读 MCU Reference Manual 中的 CAN 控制器章节。
- 能使用示波器、逻辑分析仪或 CAN 分析仪观察总线。
- 能编写中断驱动和无锁/单生产者单消费者环形缓冲区。
- 能使用编译器 map 文件、逻辑分析仪和性能计数器进行定量分析。

---

## 3. 技术概述

### 3.1 CAN 的核心定义

CAN 是一种基于消息标识符的多主串行总线。节点不使用地址进行通信，而是使用 **CAN ID 表示消息类型和优先级**。

在标准 CAN 仲裁中：

- 逻辑 `0` 为显性位，逻辑 `1` 为隐性位。
- 多个节点可以同时开始发送。
- 发送显性位的节点可以覆盖发送隐性位的节点。
- 如果节点发送隐性位但读取到显性位，则说明自身优先级较低，立即停止发送。
- **数值越小的 CAN ID，优先级越高**。

CAN 的关键特点：

- 多主通信。
- 非破坏性位仲裁。
- 高可靠错误检测。
- 广播式消息分发。
- 确定性优先级调度。
- 硬件自动应答和错误重传。

### 3.2 Classical CAN 与 CAN-FD

|项目|Classical CAN|CAN-FD|
|---|---|---|
|仲裁速率|通常最高 1 Mbit/s|通常 500 kbit/s、1 Mbit/s|
|数据阶段速率|与仲裁阶段相同|可通过 BRS 提高，常见 2~8 Mbit/s|
|最大数据长度|8 字节|64 字节|
|DLC 编码|0~8|0~8、12、16、20、24、32、48、64|
|CRC|CRC-15|CRC-17 或 CRC-21|
|支持 BRS|否|是|
|支持 ESI|否|是|
|兼容性|兼容 Classical CAN 节点|CAN-FD 节点通常兼容 Classical CAN 帧|
|典型用途|车身控制、低速传感器、传统 ECU|OTA、诊断、BMS、雷达、网关、域控制器|
|控制器 RAM 需求|较低|较高，需要 Message RAM|
|设计复杂度|中等|较高|

### 3.3 帧类型

CAN 帧主要包括：

1. 数据帧：携带应用数据。
2. 远程帧：请求其他节点发送某个 ID 的数据，实际工程中使用较少。
3. 错误帧：节点检测错误后主动发送。
4. 过载帧：用于请求延迟下一帧。
5. CAN-FD 数据帧：增加 FDF、BRS、ESI 等控制位。

典型 CAN-FD 数据帧结构：

```
SOF
  -> Arbitration Field: ID + RTR/IDE
  -> Control Field: FDF + BRS + ESI + DLC
  -> Data Field: 0~64 bytes
  -> CRC Field
  -> ACK Field
  -> EOF
```

---

## 4. 核心特性横向对比

### 4.1 驱动接收方式对比

|方案|CPU 占用|实时性|实现复杂度|适用场景|
|---|---|---|---|---|
|轮询|高|差|低|启动阶段、低速诊断|
|每帧中断|中|好|中|普通控制器|
|FIFO 中断|低|好|中|常规量产产品|
|DMA/Message RAM|低|很好|高|高速 CAN-FD、网关|
|专用 CAN 接收任务|可控|取决于调度|中|RTOS 系统|
|ISR 直接解析协议|不稳定|初始延迟低|高风险|不建议|

### 4.2 发送策略对比

|方案|优点|缺点|适用场景|
|---|---|---|---|
|直接写发送寄存器|简单|容易阻塞、邮箱耗尽|低负载|
|发送邮箱轮询|可预测|CPU 等待|Bootloader、短事务|
|软件发送队列 + ISR|吞吐高|需要处理队列满|量产系统|
|RTOS 消息队列|模块边界清晰|有上下文切换开销|多任务系统|
|优先级发送队列|满载下保证关键帧|实现复杂|安全控制、动力域|
|时间触发发送|周期精确|依赖硬件能力|采样同步、控制闭环|

### 4.3 过滤方式对比

|过滤方式|CPU 开销|可维护性|过滤粒度|典型用途|
|---|---|---|---|---|
|硬件精确匹配|最低|中|单 ID|关键控制帧|
|硬件掩码匹配|很低|高|ID 位域|一组相关消息|
|范围过滤|很低|高|ID 区间|诊断、节点地址|
|软件过滤|高|高|任意规则|动态协议、网关|
|硬件粗过滤 + 软件细过滤|低|高|分层|推荐通用方案|

### 4.4 错误恢复方式对比

|恢复模式|行为|优点|风险|
|---|---|---|---|
|自动重传|硬件自动重发失败帧|对瞬态干扰有效|可能增加延迟|
|自动 Bus-Off 恢复|硬件等待恢复序列后重启|实现简单|上层不易感知|
|软件 Bus-Off 恢复|驱动通知应用后重启|可实现故障降级|设计复杂|
|禁止自动恢复|保持离线，等待人工/策略恢复|安全可控|业务可能永久中断|
|分级恢复|重启、降速、隔离、告警|工业级可靠性高|需要系统级设计|

---

## 5. 底层原理与功能特性深度解析

## 5.1 非破坏性位仲裁

假设三个节点同时发送：

```
节点 A: 0 1 0 ...
节点 B: 0 1 1 ...
节点 C: 0 0 0 ...
```

在第二个比较位上：

```
A 发送 1
B 发送 1
C 发送 0
```

总线读取为显性 `0`，A 和 B 发现：

```
发送的是隐性 1，读取的是显性 0
```

因此 A、B 退出仲裁，C 获得总线。

仲裁结论：

- ID 数值越小，显性 `0` 越早出现。
- 关键控制消息应使用较高优先级。
- 不应简单根据“消息来源模块”分配 ID，应根据**最坏延迟要求**分配 ID。

### 工程建议

```
0x000 ~ 0x07F: 紧急控制、保护动作
0x080 ~ 0x1FF: 快速闭环、执行器反馈
0x200 ~ 0x5FF: 周期状态、传感器
0x600 ~ 0x6FF: 诊断与配置
0x700 ~ 0x7FF: 节点管理、保留
```

这只是工程模板，实际分配应结合消息周期和最大响应时间。

---

## 5.2 位时序与采样点

一个 CAN 位通常分成：

```
SYNC_SEG + PROP_SEG + PHASE_SEG1 + PHASE_SEG2
```

常用公式：

```
TQ = 1 / (f_can_clk / Prescaler)

NominalBitRate =
    f_can_clk /
    (Prescaler × (1 + TSEG1 + TSEG2))

SamplePoint =
    (1 + TSEG1) /
    (1 + TSEG1 + TSEG2)
```

例如：

```
CAN 时钟 f_can_clk = 80 MHz
目标仲裁速率 = 500 kbit/s
Prescaler = 10
总 TQ = 16
TSEG1 = 12
TSEG2 = 3
SJW = 3
```

则：

```
BitRate = 80 MHz / (10 × 16)
        = 500 kbit/s

SamplePoint = (1 + 12) / 16
             = 81.25%
```

CAN-FD 通常有两套位时序：

- Nominal Bit Timing：仲裁阶段。
- Data Bit Timing：数据阶段。

示例：

```
仲裁阶段：500 kbit/s，采样点 80%
数据阶段：2 Mbit/s，采样点 70%
```

### 关键约束

- `SJW <= TSEG2`
- 采样点必须适应总线长度、收发器延迟和时钟误差。
- 数据阶段速率越高，对 PCB、线缆、收发器和拓扑要求越严格。
- CAN-FD BRS 帧在仲裁阶段使用低速率，在数据阶段切换高速率。
- 非 FD 节点无法正确处理 CAN-FD 帧，不能将 CAN-FD 当作透明升级。

---

## 5.3 CAN-FD DLC 映射

CAN-FD 的 DLC 并不是简单的“数据长度值”。

```
#include <stdint.h>

static uint8_t canfd_dlc_to_len(uint8_t dlc)
{
    static const uint8_t table[16] = {
        0, 1, 2, 3, 4, 5, 6, 7,
        8, 12, 16, 20, 24, 32, 48, 64
    };

    return dlc < 16U ? table[dlc] : 0U;
}

static uint8_t canfd_len_to_dlc(uint8_t len)
{
    if (len <= 8U) {
        return len;
    }

    if (len <= 12U) {
        return 9U;
    }

    if (len <= 16U) {
        return 10U;
    }

    if (len <= 20U) {
        return 11U;
    }

    if (len <= 24U) {
        return 12U;
    }

    if (len <= 32U) {
        return 13U;
    }

    if (len <= 48U) {
        return 14U;
    }

    if (len <= 64U) {
        return 15U;
    }

    return 0xFFU;
}
```

生产级要求：

- 禁止直接把任意长度强制转换成 DLC。
- `len > 64` 必须返回参数错误。
- 接收时必须根据 DLC 解码，并校验硬件报告长度。
- 对协议层，建议区分 `payload_length` 和 `buffer_capacity`。

---

## 5.4 驱动数据结构设计

底层驱动应避免把硬件寄存器结构直接暴露给应用层。

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    CAN_FRAME_CLASSICAL = 0,
    CAN_FRAME_FD
} can_frame_format_t;

typedef enum {
    CAN_ID_STANDARD = 0,
    CAN_ID_EXTENDED
} can_id_type_t;

typedef struct {
    uint32_t id;
    can_id_type_t id_type;
    can_frame_format_t format;
    bool bit_rate_switch;
    bool error_state_indicator;
    uint8_t dlc;
    uint8_t len;
    uint8_t data[64];
    uint32_t timestamp;
} can_frame_t;

typedef enum {
    CAN_STATUS_OK = 0,
    CAN_STATUS_INVALID_PARAM,
    CAN_STATUS_BUSY,
    CAN_STATUS_QUEUE_FULL,
    CAN_STATUS_TIMEOUT,
    CAN_STATUS_BUS_OFF,
    CAN_STATUS_NOT_READY,
    CAN_STATUS_HW_ERROR
} can_status_t;
```

设计要点：

- `id` 使用统一的逻辑值，不把 IDE 位混入 ID。
- `len` 表示真实有效字节数。
- `dlc` 表示硬件帧编码。
- `timestamp` 由底层统一提供，避免上层自行读取系统 Tick。
- 数据缓冲区固定为 64 字节，避免接收路径动态内存分配。

---

## 5.5 发送队列与发送邮箱

发送路径应分为：

```
应用任务
  -> 驱动发送 API
  -> 软件优先级队列
  -> 硬件发送邮箱
  -> TX Complete ISR
  -> 补充下一个待发帧
```

简单的软件队列框架：

```
#define CAN_TX_QUEUE_SIZE 32U

typedef struct {
    can_frame_t items[CAN_TX_QUEUE_SIZE];
    uint16_t count;
} can_tx_queue_t;

typedef struct {
    can_tx_queue_t tx_queue;
    volatile uint32_t tx_submitted;
    volatile uint32_t tx_completed;
    volatile uint32_t tx_dropped;
} can_driver_t;

static bool can_tx_queue_push(can_tx_queue_t *queue,
                              const can_frame_t *frame)
{
    if ((queue == NULL) || (frame == NULL)) {
        return false;
    }

    if (queue->count >= CAN_TX_QUEUE_SIZE) {
        return false;
    }

    queue->items[queue->count] = *frame;
    queue->count++;
    return true;
}

static bool can_tx_queue_pop_highest_priority(can_tx_queue_t *queue,
                                              can_frame_t *frame)
{
    uint16_t best_index = 0U;

    if ((queue == NULL) || (frame == NULL) || (queue->count == 0U)) {
        return false;
    }

    for (uint16_t i = 1U; i < queue->count; i++) {
        if (queue->items[i].id < queue->items[best_index].id) {
            best_index = i;
        }
    }

    *frame = queue->items[best_index];

    for (uint16_t i = best_index; i + 1U < queue->count; i++) {
        queue->items[i] = queue->items[i + 1U];
    }

    queue->count--;
    return true;
}
```

这个实现适合教学和低吞吐场景。高负载系统建议：

- 使用固定优先级桶，避免每次遍历整个队列。
- 或使用二叉堆，复杂度从 `O(n)` 降为 `O(log n)`。
- 将紧急帧和普通帧分成独立队列。
- 队列满时不能静默丢帧，必须记录丢弃计数和消息 ID。

---

## 5.6 接收 FIFO 与 ISR 分层

ISR 中只做三件事：

1. 读取硬件 FIFO。
2. 拷贝到软件环形队列。
3. 记录状态并唤醒接收任务。

不应在 ISR 中执行：

- 信号解码。
- 复杂 CRC。
- 诊断服务处理。
- 阻塞等待。
- 日志格式化。
- 动态内存分配。

```
#define CAN_RX_QUEUE_SIZE 64U

typedef struct {
    can_frame_t items[CAN_RX_QUEUE_SIZE];
    volatile uint16_t head;
    volatile uint16_t tail;
    volatile uint32_t overflow_count;
} can_rx_queue_t;

static bool can_rx_queue_push_from_isr(can_rx_queue_t *queue,
                                       const can_frame_t *frame)
{
    uint16_t next_head;

    if ((queue == NULL) || (frame == NULL)) {
        return false;
    }

    next_head = (uint16_t)((queue->head + 1U) % CAN_RX_QUEUE_SIZE);

    if (next_head == queue->tail) {
        queue->overflow_count++;
        return false;
    }

    queue->items[queue->head] = *frame;

    /*
     * 对带数据缓存的 MCU，需要在此处使用适当的内存屏障，
     * 确保数据写入先于 head 发布。
     */
    queue->head = next_head;
    return true;
}

static bool can_rx_queue_pop(can_rx_queue_t *queue,
                             can_frame_t *frame)
{
    if ((queue == NULL) || (frame == NULL)) {
        return false;
    }

    if (queue->tail == queue->head) {
        return false;
    }

    *frame = queue->items[queue->tail];
    queue->tail = (uint16_t)((queue->tail + 1U) % CAN_RX_QUEUE_SIZE);
    return true;
}
```

注意：

- 上述结构适合**单 ISR 生产者、单任务消费者**。
- 如果存在多个 ISR、多任务或缓存一致性问题，必须引入临界区、原子操作或 RTOS 队列。
- 在 Cortex-M7、带 D-Cache 的 MCU 上，DMA/Message RAM 必须处理 cache clean/invalidate 和内存区域属性。

---

## 5.7 硬件过滤器

掩码过滤的基本逻辑：

```
(received_id & mask) == (filter_id & mask)
```

例如只接收 `0x180 ~ 0x18F`：

```
#define CAN_ID_RANGE_BASE 0x180U
#define CAN_ID_RANGE_MASK 0x7F0U

static bool can_id_match(uint32_t received_id,
                         uint32_t filter_id,
                         uint32_t mask)
{
    return (received_id & mask) == (filter_id & mask);
}
```

工程上需要注意：

- 标准 ID 和扩展 ID 必须分别配置。
- 硬件过滤器中 ID 往往需要左移，具体取决于控制器寄存器格式。
- 不要把过滤器配置错误归因于“总线没有数据”。
- 量产版本应提供过滤器命中计数、拒绝计数和 FIFO 溢出计数。

---

## 5.8 错误状态机

CAN 控制器维护两个主要错误计数器：

- TEC：Transmit Error Counter。
- REC：Receive Error Counter。

典型状态：

```
错误主动 Error Active
  -> TEC 或 REC 达到错误被动阈值
错误被动 Error Passive
  -> TEC 达到 Bus-Off 阈值
Bus-Off
  -> 执行恢复策略
```

常见阈值：

```
TEC/REC < 128              Error Active
TEC >= 128 或 REC >= 128   Error Passive
TEC >= 256                 Bus-Off
```

实际阈值和状态位以控制器手册为准。

驱动必须将以下状态暴露给上层：

```
typedef struct {
    uint32_t tx_error_count;
    uint32_t rx_error_count;
    uint32_t bus_off_count;
    uint32_t rx_fifo_overflow;
    uint32_t tx_queue_overflow;
    uint32_t protocol_error_count;
    bool error_passive;
    bool bus_off;
} can_error_stats_t;
```

---

## 5.9 Bus-Off 恢复

Bus-Off 不能简单理解为“重新初始化一次”。工业实现至少需要：

```
检测 Bus-Off
  -> 停止新发送
  -> 记录故障原因和计数
  -> 清空/保留发送队列
  -> 等待恢复时间或硬件恢复条件
  -> 重新配置控制器
  -> 验证 Error Active
  -> 恢复发送
  -> 通知上层故障恢复
```

参考实现：

```
typedef enum {
    CAN_STATE_STOPPED = 0,
    CAN_STATE_RUNNING,
    CAN_STATE_BUS_OFF,
    CAN_STATE_RECOVERING
} can_state_t;

can_status_t can_handle_bus_off(can_driver_t *driver)
{
    if (driver == NULL) {
        return CAN_STATUS_INVALID_PARAM;
    }

    /*
     * 生产系统中此处还应：
     * 1. 禁止发送路径继续向硬件投递帧
     * 2. 保存 bus_off 时间戳
     * 3. 增加故障计数
     * 4. 按安全策略决定是否丢弃旧周期帧
     */
    return CAN_STATUS_OK;
}
```

对于控制系统，Bus-Off 恢复后不能盲目发送历史控制帧。周期状态帧可以重新生成，已经过期的执行命令通常应丢弃。

---

## 6. 性能量化分析

以下数据为**参考测试模型**，不是特定 MCU 的绝对值。测试平台假设：

```
MCU：Cortex-M7，400 MHz
CAN 控制器：支持 CAN-FD Message RAM
RTOS：FreeRTOS
编译器：GCC -O2
仲裁速率：500 kbit/s
数据速率：2 Mbit/s
RX：FIFO + 中断
TX：3 个硬件邮箱 + 软件优先级队列
```

### 6.1 帧长度估算

Classical CAN 8 字节数据帧，考虑仲裁字段、控制字段、CRC、ACK、EOF 和位填充后，实际长度通常约为：

```
L_classical ≈ 110 ~ 135 bits
```

CAN-FD 64 字节、2 Mbit/s 数据阶段的帧长度取决于：

- 标准/扩展 ID。
- 是否启用 BRS。
- 数据阶段速率。
- 位填充数量。
- 控制字段和 CRC 类型。

粗略估算：

```
T_frame =
    T_arbitration +
    T_control +
    T_data +
    T_crc +
    T_ack
```

若：

```
仲裁阶段约 50 bits，速率 500 kbit/s
数据及 CRC 约 600 bits，速率 2 Mbit/s
```

则：

```
T_frame ≈ 50 / 500k + 600 / 2M
        ≈ 100 us + 300 us
        ≈ 400 us
```

实际值需要使用 CAN 分析仪或控制器发送时间戳校准。

### 6.2 总线负载

总线负载：

```
BusLoad =
    Σ(FrameBits_i × FrameFrequency_i) /
    BusBitRate
```

例如有三类周期帧：

```
消息 A：130 bits，100 Hz
消息 B：250 bits，50 Hz
消息 C：700 bits，20 Hz
总线速率：500 kbit/s
```

则：

```
Load =
(130 × 100 + 250 × 50 + 700 × 20) / 500000
     = 39500 / 500000
     = 7.9%
```

如果 BRS 数据阶段仅加速数据字段，不能简单把整帧都除以数据速率。

工业建议：

|总线类型|推荐长期平均负载|允许峰值|
|---|---|---|
|高可靠闭环控制|< 30%|< 50%|
|普通车身/工业 I/O|< 50%|< 70%|
|诊断/日志通道|< 30%|< 60%|
|高速 CAN-FD 网关|< 60%|需严格验证|

### 6.3 延迟估算

高优先级消息的最坏等待时间可以近似表示为：

```
R_i = J_i + B_i
      + Σ ceil(R_i / T_h) × C_h
      + Σ ceil(R_i / T_k) × C_k
```

其中：

- `R_i`：消息最坏响应时间。
- `J_i`：任务和中断抖动。
- `B_i`：当前已经开始发送的低优先级帧造成的阻塞。
- `C_h`：高优先级消息的发送时间。
- `T_h`：高优先级消息周期。
- `C_k`、`T_k`：其他竞争消息的发送时间。

CAN 仲裁只能阻止后续低优先级消息，**不能打断已经开始发送的帧**。因此高优先级控制帧仍会受到一帧低优先级消息的阻塞。

### 6.4 内存开销

假设 `can_frame_t` 按 4 字节对齐：

```
固定字段约 20~24 字节
data[64] = 64 字节
单帧约 88~96 字节
```

软件接收队列 64 帧：

```
96 × 64 = 6144 bytes
```

软件发送队列 32 帧：

```
96 × 32 = 3072 bytes
```

再加控制块、统计字段和 Message RAM，单 CAN 实例通常需要：

```
约 10 KB ~ 20 KB SRAM
```

CAN-FD 网关可能需要：

```
RX 256 帧 + TX 128 帧
约 40 KB 以上 SRAM
```

### 6.5 参考性能数据

|测试项|参考结果|
|---|---|
|中断入口到硬件 FIFO 读取|0.8~1.5 us|
|单帧拷贝到软件 RX 队列|0.3~0.8 us|
|经典 CAN 8 字节 RX CPU 占用|约 1%~3%|
|CAN-FD 64 字节 RX CPU 占用|约 2%~6%|
|软件优先级队列入队|0.2~0.5 us|
|32 项线性优先级查找|0.5~1.5 us|
|Message RAM DMA 路径|通常低于纯 CPU 拷贝占用|

优化方向：

1. 使用硬件 FIFO 降低中断次数。
2. 使用批量读取，一次处理多个 FIFO 元素。
3. 将协议解析从 ISR 移到高优先级接收任务。
4. 使用固定长度对象池，避免动态内存。
5. 高频周期帧采用预构造模板，仅更新数据字段。
6. 使用硬件时间戳和 Message RAM，避免重复寄存器访问。
7. 发送队列使用优先级桶，避免线性扫描。

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
需要传输的数据是否超过 8 字节？
├─ 否
│  ├─ 现有节点只支持 Classical CAN？
│  │  ├─ 是 -> 使用 Classical CAN
│  │  └─ 否 -> 继续评估 CAN-FD 的带宽收益
│  └─ 是否需要 >1 Mbit/s 数据阶段速率？
│     ├─ 否 -> Classical CAN 或 CAN-FD 均可
│     └─ 是 -> 使用 CAN-FD + BRS
└─ 是
   └─ 使用 CAN-FD

是否有严格实时控制要求？
├─ 是
│  ├─ 设计高优先级 ID
│  ├─ 限制总线负载
│  ├─ 使用中断/FIFO
│  └─ 做最坏响应时间分析
└─ 否
   └─ 可使用较低优先级消息和诊断传输

是否存在旧节点？
├─ 是 -> 禁止同一总线直接发送 CAN-FD 帧，或通过网关隔离
└─ 否 -> 可统一规划 CAN-FD 速率和 Message RAM

是否需要多协议并发？
├─ 是 -> 硬件粗过滤 + 软件协议分发
└─ 否 -> 精确硬件过滤即可

是否属于安全关键系统？
├─ 是 -> 设计 Bus-Off 策略、故障降级、独立监控和超时检测
└─ 否 -> 实现标准错误统计和自动恢复
```

### 7.2 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|电机控制器|1~10 ms 周期、低延迟|Classical CAN 或 CAN-FD|小帧、高优先级、严格时序|
|BMS|电压、电流、均衡、诊断|CAN-FD|数据量大，需诊断和升级|
|车载网关|多总线转发|CAN-FD + 双 FIFO + 路由表|需要吞吐和消息隔离|
|工业机器人|控制状态与故障码|CANopen / CAN-FD|需要对象字典或大数据传输|
|UDS 诊断|分段传输、刷写|ISO-TP over CAN/CAN-FD|单帧不足，需要流控和重组|
|低速传感器|少量周期数据|Classical CAN|成本、兼容性和简单性优先|

---

## 8. 工程最佳实践

### 8.1 分层架构

推荐分为五层：

```
Application
  -> Signal / Message Codec
  -> Transport Protocol: ISO-TP、CANopen 等
  -> CAN Driver
  -> MCU CAN HAL / Register Layer
```

职责边界：

- MCU 寄存器层：时钟、复用、Message RAM、位时序。
- CAN Driver：帧收发、FIFO、过滤、错误状态。
- 传输层：分段、重组、流控。
- 消息编解码层：字节序、缩放、有效范围。
- 应用层：业务状态和故障策略。

### 8.2 选型决策矩阵

|评价项|权重|Classical CAN|CAN-FD|
|---|---|---|---|
|旧节点兼容|5|5|2|
|单帧数据量|4|2|5|
|高速数据传输|4|2|5|
|控制器资源|3|5|3|
|协议生态成熟度|3|5|4|
|诊断刷写效率|4|2|5|
|布线和 EMI 容忍度|4|4|3|

### 8.3 编码规范

- 不在驱动中使用 `malloc`。
- 不在 ISR 中调用可能阻塞的 API。
- 所有硬件超时都必须有明确返回码。
- 所有 FIFO、邮箱和软件队列都必须有溢出计数器。
- 发送接口必须区分“成功进入软件队列”和“成功进入硬件邮箱”。
- 接收回调必须明确运行上下文：ISR 还是任务。
- 不能依赖结构体位域直接映射硬件寄存器，除非 ABI 和编译器行为已经被验证。
- 复杂寄存器字段使用掩码和移位宏。
- 驱动初始化、停止、恢复操作必须幂等。
- 应用层不得直接访问 CAN 控制器寄存器。

---

## 9. 常见错误与避坑指南

## 9.1 位时序计算错误

### 错误代码

```
/* 错误：忽略总线时钟和 Prescaler 之间的关系 */
can_set_bitrate(500000U);
```

### 根因

- 没有确认 CAN 内核时钟。
- 把 APB 时钟误认为 CAN 时钟。
- 忽略同步段固定占用 1 个 TQ。
- 只设置 nominal timing，没有设置 data timing。

### 正确实现

```
typedef struct {
    uint16_t prescaler;
    uint8_t tseg1;
    uint8_t tseg2;
    uint8_t sjw;
} can_bit_timing_t;

static uint32_t can_calc_bitrate(uint32_t clock_hz,
                                 const can_bit_timing_t *timing)
{
    uint32_t tq_count;

    if ((timing == NULL) || (timing->prescaler == 0U)) {
        return 0U;
    }

    tq_count = 1U + timing->tseg1 + timing->tseg2;

    return clock_hz /
           ((uint32_t)timing->prescaler * tq_count);
}
```

### 风险影响

- 节点完全无法通信。
- 可能表现为 ACK Error，而不是明显的波特率错误。
- CAN-FD 只在数据阶段错误，导致问题难以复现。

---

## 9.2 把 ID 当作地址或优先级设计错误

### 错误代码

```
/* 错误：所有模块使用连续 ID，不考虑实时优先级 */
#define MOTOR_STATUS_ID  0x500U
#define MOTOR_COMMAND_ID 0x501U
#define SAFETY_STOP_ID   0x502U
```

### 根因

- 按模块编号顺序分配 ID。
- 没有根据最大延迟分配优先级。
- 安全停止消息反而被普通状态帧阻塞。

### 正确实现

```
#define SAFETY_STOP_ID    0x020U
#define MOTOR_COMMAND_ID  0x080U
#define MOTOR_STATUS_ID   0x280U
```

### 风险影响

- 满载时关键控制帧延迟不可预测。
- 保护动作响应时间超标。
- 发生优先级饥饿，低优先级帧长期发送不出去。

---

## 9.3 在 ISR 中解析完整协议

### 错误代码

```
void CAN_RX_IRQHandler(void)
{
    can_frame_t frame;

    can_hw_read(&frame);
    uds_process_frame(&frame);       /* 可能耗时 */
    signal_decode_and_update(&frame); /* 修改多个共享对象 */
    log_printf("rx id=%x", frame.id); /* 可能阻塞 */
}
```

### 根因

- 将“接收完成”和“业务处理”混在一起。
- 忽略 ISR 抖动和嵌套中断。
- 共享数据没有事务边界。

### 正确实现

```
void CAN_RX_IRQHandler(void)
{
    can_frame_t frame;

    while (can_hw_rx_pending()) {
        if (!can_hw_read(&frame)) {
            break;
        }

        if (!can_rx_queue_push_from_isr(&g_can_rx_queue, &frame)) {
            g_can_stats.rx_fifo_overflow++;
        }
    }

    rtos_notify_from_isr(CAN_RX_TASK_ID);
}
```

### 风险影响

- 高优先级中断被延迟。
- FIFO 继续堆积，最终溢出。
- 业务数据更新一半时被其他任务读取，产生不一致。

---

## 9.4 Bus-Off 后盲目恢复并重发旧命令

### 错误代码

```
void can_bus_off_callback(void)
{
    can_hw_restart();
    can_send_all_queued_frames();
}
```

### 根因

- 没有区分周期状态帧和一次性控制命令。
- 没有确认物理故障已经消失。
- 没有通知应用进入故障状态。

### 正确实现

```
void can_bus_off_callback(void)
{
    g_can_state = CAN_STATE_BUS_OFF;
    g_can_stats.bus_off_count++;

    /*
     * 周期状态帧可重新生成；
     * 已过期的执行命令必须丢弃；
     * 安全相关命令需要应用重新确认。
     */
    can_tx_queue_drop_expired(&g_can_driver.tx_queue);
    app_notify_can_fault(CAN_STATUS_BUS_OFF);
}
```

### 风险影响

- 总线持续反复 Bus-Off。
- 执行器收到过期命令。
- 故障恢复后出现非预期动作。

---

## 9.5 过滤器配置过宽

### 错误代码

```
/* 错误：接收所有 ID，再由 CPU 过滤 */
can_filter_set_mask(0x000U, 0x000U);
```

### 根因

- 认为软件过滤更加灵活。
- 没有评估高负载下的 CPU 和 FIFO 压力。

### 正确实现

```
/* 只接收 0x180 ~ 0x18F */
can_filter_set_mask(0x180U, 0x7F0U);
```

### 风险影响

- 无关报文挤占 FIFO。
- ISR 频率增加。
- 合法关键帧因 FIFO 溢出被丢弃。

---

## 9.6 忽略缓存一致性

### 错误代码

```
void can_dma_receive_complete(void)
{
    /* 直接读取 DMA 写入的缓存 */
    process_frame(&g_dma_rx_buffer);
}
```

### 根因

- Cortex-M7 D-Cache 中仍然保留旧数据。
- DMA 写内存后 CPU 没有 invalidate cache。
- CPU 写发送缓冲后 DMA 没有看到最新数据。

### 正确实现

```
void can_dma_receive_complete(void)
{
    cache_invalidate(g_dma_rx_buffer,
                     sizeof(g_dma_rx_buffer));

    process_frame(&g_dma_rx_buffer);
}
```

### 风险影响

- 接收数据偶发错误。
- 问题与优化等级、运行负载和缓存状态相关。
- 现场难以通过日志复现。

---

## 10. 多机制组合使用方案

推荐的量产架构：

```
高优先级控制帧
  -> 紧急发送队列
  -> 硬件 TX Mailbox

普通周期帧
  -> 普通发送队列
  -> 硬件 TX Mailbox

接收路径
  -> 硬件过滤器
  -> RX FIFO
  -> RX ISR
  -> 软件环形队列
  -> CAN RX Task
  -> 协议分发器
  -> 信号解码 / ISO-TP / 网关路由

错误路径
  -> Error ISR
  -> 错误统计
  -> Bus-Off 状态机
  -> 系统故障管理
```

### 10.1 统一发送框架

```
typedef enum {
    CAN_TX_CLASS_EMERGENCY = 0,
    CAN_TX_CLASS_CONTROL,
    CAN_TX_CLASS_PERIODIC,
    CAN_TX_CLASS_DIAGNOSTIC
} can_tx_class_t;

typedef struct {
    can_frame_t frame;
    can_tx_class_t tx_class;
    uint32_t deadline_tick;
    bool discard_if_expired;
} can_tx_item_t;

can_status_t can_submit(can_driver_t *driver,
                        const can_tx_item_t *item,
                        uint32_t now_tick)
{
    if ((driver == NULL) || (item == NULL)) {
        return CAN_STATUS_INVALID_PARAM;
    }

    if (item->frame.len > 64U) {
        return CAN_STATUS_INVALID_PARAM;
    }

    if (driver->state == CAN_STATE_BUS_OFF ||
        driver->state == CAN_STATE_RECOVERING) {
        return CAN_STATUS_BUS_OFF;
    }

    if (item->discard_if_expired &&
        ((int32_t)(now_tick - item->deadline_tick) > 0)) {
        return CAN_STATUS_TIMEOUT;
    }

    if (!can_tx_queue_insert_by_class_and_id(driver, item)) {
        driver->tx_dropped++;
        return CAN_STATUS_QUEUE_FULL;
    }

    can_kick_tx_mailbox(driver);
    return CAN_STATUS_OK;
}
```

### 10.2 接收分发框架

```
typedef void (*can_message_handler_t)(const can_frame_t *frame);

typedef struct {
    uint32_t id;
    uint32_t mask;
    can_id_type_t id_type;
    can_message_handler_t handler;
} can_route_entry_t;

static const can_route_entry_t g_routes[] = {
    { 0x080U, 0x7FFU, CAN_ID_STANDARD, motor_command_handler },
    { 0x180U, 0x7F0U, CAN_ID_STANDARD, motor_status_handler },
    { 0x600U, 0x7F0U, CAN_ID_STANDARD, isotp_handler }
};

void can_dispatch_frame(const can_frame_t *frame)
{
    if (frame == NULL) {
        return;
    }

    for (uint32_t i = 0U;
         i < sizeof(g_routes) / sizeof(g_routes[0]);
         i++) {
        const can_route_entry_t *route = &g_routes[i];

        if (route->id_type != frame->id_type) {
            continue;
        }

        if ((frame->id & route->mask) ==
            (route->id & route->mask)) {
            route->handler(frame);
            return;
        }
    }

    g_can_stats.unhandled_frame_count++;
}
```

这里仍然是线性查找。高负载网关建议使用：

- ID 直接索引表。
- 二级查找表。
- 按 ID 区间分组。
- 编译期生成路由表。
- 对转发消息预计算目标端口和修改规则。

---

## 11. 工业级实际案例分析

## 11.1 案例一：电机控制器

### 需求

- 控制周期：1 ms。
- 速度反馈周期：2 ms。
- 故障停止响应：小于 5 ms。
- 总线速率：500 kbit/s。
- 关键帧不能因普通诊断流量而长时间延迟。

### 架构

```
安全停止 ID 0x020
电机控制 ID 0x080
速度反馈 ID 0x180
状态信息 ID 0x280
诊断消息 ID 0x600
```

### 核心代码

```
void motor_control_1ms_task(void)
{
    can_frame_t frame = {0};

    frame.id = 0x080U;
    frame.id_type = CAN_ID_STANDARD;
    frame.format = CAN_FRAME_CLASSICAL;
    frame.len = 8U;
    frame.dlc = 8U;

    frame.data[0] = motor_target_torque & 0xFFU;
    frame.data[1] = motor_target_torque >> 8;
    frame.data[2] = motor_target_speed & 0xFFU;
    frame.data[3] = motor_target_speed >> 8;
    frame.data[4] = motor_enable;
    frame.data[5] = motor_control_counter;
    frame.data[6] = motor_control_crc;
    frame.data[7] = 0U;

    can_submit_periodic(&frame, 1U);
}
```

### 设计要点

- 控制帧 ID 必须高于状态帧和诊断帧。
- 帧内增加 rolling counter 和 CRC，解决“CAN 总线成功但数据已过期/错序”的问题。
- 发送超时后不能无限重试，应进入电机安全状态。
- 速度反馈的有效性由应用层监控，不应只依赖驱动接收成功。

---

## 11.2 案例二：BMS 使用 CAN-FD

### 需求

- 采集 96 节电芯电压。
- 单次需要传输大量电芯状态。
- 支持 UDS 诊断和固件刷写。
- 仲裁速率 500 kbit/s，数据阶段 2 Mbit/s。

### 架构

```
CAN-FD + BRS
0x100~0x13F：电池控制关键状态
0x200~0x2FF：电芯分组数据
0x600~0x6FF：UDS / ISO-TP
```

### 数据打包

```
typedef struct {
    uint16_t cell_mv[16];
    uint16_t min_mv;
    uint16_t max_mv;
    uint16_t temperature;
    uint8_t group_index;
    uint8_t counter;
} bms_group_t;

static can_status_t bms_send_group(const bms_group_t *group)
{
    can_frame_t frame = {0};

    if (group == NULL) {
        return CAN_STATUS_INVALID_PARAM;
    }

    frame.id = 0x200U + group->group_index;
    frame.id_type = CAN_ID_STANDARD;
    frame.format = CAN_FRAME_FD;
    frame.bit_rate_switch = true;
    frame.len = 40U;
    frame.dlc = canfd_len_to_dlc(frame.len);

    if (frame.dlc == 0xFFU) {
        return CAN_STATUS_INVALID_PARAM;
    }

    for (uint32_t i = 0U; i < 16U; i++) {
        frame.data[2U * i] =
            (uint8_t)(group->cell_mv[i] & 0xFFU);
        frame.data[2U * i + 1U] =
            (uint8_t)(group->cell_mv[i] >> 8);
    }

    frame.data[32] = group->min_mv & 0xFFU;
    frame.data[33] = group->min_mv >> 8;
    frame.data[34] = group->max_mv & 0xFFU;
    frame.data[35] = group->max_mv >> 8;
    frame.data[36] = group->temperature & 0xFFU;
    frame.data[37] = group->temperature >> 8;
    frame.data[38] = group->group_index;
    frame.data[39] = group->counter;

    return can_submit_frame(&frame);
}
```

### 设计要点

- BRS 只能在总线物理层和所有节点能力都支持时使用。
- 电芯数据适合 CAN-FD，但安全告警仍然应使用独立高优先级短帧。
- 固件刷写不能占满总线，必须限制诊断流量。
- 电池状态帧需要 counter、CRC、超时和范围校验。
- 接收端要拒绝不符合预期 DLC 的帧。

---

## 11.3 案例三：双 CAN 网关

### 需求

- CAN-A：500 kbit/s Classical CAN。
- CAN-B：500 kbit/s 仲裁、2 Mbit/s 数据阶段 CAN-FD。
- 对指定 ID 进行转发和字段映射。
- 防止 CAN-B 的高速流量淹没 CAN-A。

### 路由架构

```
CAN-A RX
  -> 硬件过滤
  -> A_RX_QUEUE
  -> 路由表
  -> B_TX_QUEUE

CAN-B RX
  -> 硬件过滤
  -> B_RX_QUEUE
  -> 路由表
  -> A_TX_QUEUE
```

### 关键策略

- 每个 CAN 控制器独立 RX/TX 队列。
- 转发必须限制最大队列深度。
- 转发消息必须带 TTL 或跳转标志，防止环路。
- 从 CAN-FD 转 Classical CAN 时，长度超过 8 字节必须分段、截断或拒绝，不能静默截断。
- 网关必须统计：
    - 接收帧数。
    - 转发帧数。
    - 目标总线队列满次数。
    - DLC 不兼容次数。
    - 路由未命中次数。
    - 转发延迟分布。

---

## 12. 高频问题深度答疑

### 问题一：为什么 CAN ID 越小优先级越高？

因为 CAN 仲裁使用显性位覆盖隐性位。ID 的高位先发送，数值更小的 ID 通常会更早出现显性 `0`，从而保留总线控制权。

但“ID 越小越好”是不完整的工程结论。真正目标是：

```
关键性 + 最坏响应时间 + 总线负载 + 公平性
```

低优先级消息可能长期等待，因此应通过周期限制、队列老化或带宽预留避免饥饿。

### 问题二：CAN-FD 为什么不能和 Classical CAN 节点直接混用？

CAN-FD 帧引入了 FDF、BRS 和新的 CRC 结构。无法识别 FD 格式的 Classical CAN 控制器可能将其识别为格式错误并产生错误帧。

因此：

- 统一网络中所有节点必须明确支持 CAN-FD。
- 旧节点必须通过独立总线或网关接入。
- 网关需要处理帧长和速率能力差异。

### 问题三：自动重传是不是越多越可靠？

不是。自动重传可以抵抗瞬时干扰，但在持续物理故障下会导致：

- 发送延迟增长。
- 高优先级消息阻塞。
- 错误计数累积。
- 总线最终进入 Bus-Off。

控制消息通常需要配置发送超时。超过上层允许的时间后，应由应用进入安全策略，而不是继续等待硬件重传。

### 问题四：为什么节点显示发送成功，但对端没有收到？

“发送成功”可能只表示：

- 成功写入软件队列。
- 成功装载硬件邮箱。
- 硬件开始发送。
- 收到 ACK。
- 对端协议层接受并处理。

这些含义不同。应至少区分：

```
QUEUED
SUBMITTED
TRANSMITTED
ACKED
PROTOCOL_ACCEPTED
APPLICATION_ACCEPTED
```

CAN 控制器通常能确认物理层 ACK，但不能确认应用层已经正确处理。

### 问题五：如何处理 RX FIFO 溢出？

不能只增加 FIFO 深度。应按以下顺序排查：

1. 硬件过滤是否过宽。
2. ISR 是否执行了过多逻辑。
3. 接收任务优先级是否过低。
4. 软件队列是否太小。
5. 协议解析是否阻塞。
6. 总线负载是否超过设计上限。
7. 是否存在错误帧导致异常中断风暴。

量产产品必须统计并上报溢出事件，而不是静默丢帧。

### 问题六：如何选择 CAN-FD 数据阶段速率？

不能只看控制器支持的最高速率。还要考虑：

- 线缆长度。
- 拓扑结构。
- 收发器回路延迟。
- PCB 走线和阻抗。
- 节点时钟误差。
- EMC 环境。
- 采样点和 TDC 配置。
- 连接器和终端电阻。

实际工程中应先以 2 Mbit/s 建立稳定网络，再根据波形、误码率和最坏温度条件评估是否提高速率。

---

## 13. 课程核心总结

### 核心要点

1. **CAN 是基于消息 ID 的优先级总线，不是地址总线。**
2. **ID 设计直接决定实时性和系统行为。**
3. **CAN-FD 的主要收益是 64 字节单帧和独立数据阶段速率。**
4. **驱动必须把发送队列、硬件邮箱、RX FIFO 和应用处理解耦。**
5. **ISR 负责搬运数据和状态通知，协议解析应放到任务上下文。**
6. **Bus-Off 是系统级故障状态，不是单纯的硬件重启事件。**
7. **硬件过滤、队列深度和总线负载必须联合设计。**
8. **安全控制消息必须具备超时、计数器、CRC 和故障降级机制。**

### 性能排序

接收 CPU 开销通常从高到低：

```
轮询 + 软件过滤
  > 每帧中断 + 软件过滤
  > FIFO 中断 + 软件队列
  > 硬件过滤 + FIFO
  > 硬件过滤 + DMA/Message RAM
```

发送实时性通常从差到好：

```
阻塞轮询
  < 普通 FIFO
  < 软件队列
  < 优先级软件队列
  < 硬件优先级邮箱 + 软件优先级调度
```

### 通用选型结论

- 兼容旧 ECU、数据量小：**Classical CAN**。
- 数据量大、需要诊断刷写：**CAN-FD**。
- 高速闭环：高优先级 ID、严格负载控制、FIFO 中断。
- 网关：双控制器独立队列、路由表、带宽隔离。
- 安全关键系统：错误统计、Bus-Off 状态机、消息超时和应用级故障降级。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|需求|方案|
|---|---|
|最大 8 字节、旧节点多|Classical CAN|
|单帧超过 8 字节|CAN-FD|
|需要 2 Mbit/s 以上数据传输|CAN-FD + BRS|
|关键控制周期小于 5 ms|高优先级 ID + 中断 FIFO|
|高速网关|硬件过滤 + 双向队列 + 路由统计|
|诊断刷写|ISO-TP over CAN/CAN-FD|
|安全关键动作|高优先级独立帧 + counter + CRC + timeout|
|总线故障频发|检查终端、电平、位时序、接地和收发器|

### 14.2 特性对比表

|特性|Classical CAN|CAN-FD|
|---|---|---|
|最大 payload|8 B|64 B|
|仲裁速率|通常 1 Mbit/s 以下|通常 500 kbit/s 或 1 Mbit/s|
|数据速率|同仲裁速率|可提高到 2~8 Mbit/s|
|CRC|CRC-15|CRC-17 / CRC-21|
|BRS|不支持|支持|
|旧节点兼容|好|需隔离或确认兼容|
|SRAM 需求|低|中高|
|刷写效率|低|高|
|物理层要求|相对宽松|更严格|

### 14.3 常用状态码

```
OK              操作成功
INVALID_PARAM   参数错误
BUSY            控制器或邮箱忙
QUEUE_FULL      软件队列满
TIMEOUT         超时
BUS_OFF         总线离线
NOT_READY       尚未初始化
HW_ERROR        硬件故障
```

### 14.4 最小驱动接口

```
can_status_t can_init(const can_config_t *config);
can_status_t can_start(void);
can_status_t can_stop(void);

can_status_t can_send(const can_frame_t *frame,
                      uint32_t timeout_ms);

bool can_receive(can_frame_t *frame,
                 uint32_t timeout_ms);

can_status_t can_set_filter(const can_filter_t *filter);
can_status_t can_get_error_stats(can_error_stats_t *stats);
can_status_t can_recover_bus_off(void);
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

- [ ]  根据 CAN 时钟计算 500 kbit/s 的 nominal bit timing。
- [ ]  解释 CAN 显性位和隐性位的仲裁过程。
- [ ]  解释为什么 ID 数值越小优先级越高。
- [ ]  正确区分标准 ID、扩展 ID、DLC 和 payload length。
- [ ]  设计 Classical CAN 和 CAN-FD 的双阶段位时序。
- [ ]  实现硬件掩码过滤器。
- [ ]  实现单生产者、单消费者的 RX 环形队列。
- [ ]  设计发送邮箱耗尽时的软件排队策略。
- [ ]  计算给定消息集合的总线负载。
- [ ]  估算一条高优先级消息的最坏响应时间。
- [ ]  解释 Error Active、Error Passive 和 Bus-Off。
- [ ]  设计 Bus-Off 后的恢复和故障降级策略。
- [ ]  说明为什么不能在 ISR 中执行 UDS 或复杂信号解析。
- [ ]  处理 CAN-FD DLC 的非连续长度编码。
- [ ]  识别 Cortex-M7 D-Cache 对 DMA/Message RAM 的影响。
- [ ]  设计一个至少包含统计、超时和溢出检测的 CAN 驱动。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：Classical CAN 基础驱动

实现：

- GPIO 复用。
- CAN 时钟配置。
- 500 kbit/s 位时序。
- 标准帧发送。
- RX FIFO 中断接收。
- 硬件精确过滤。

验收标准：

```
连续发送 100000 帧：
- 无错误帧
- 无 FIFO 溢出
- 无发送超时
- 接收计数与发送计数一致
```

#### 任务二：软件队列与错误管理

增加：

- 32 帧 TX 软件队列。
- 64 帧 RX 环形队列。
- 队列满计数。
- RX FIFO 溢出统计。
- Error Passive 和 Bus-Off 回调。
- 发送超时。

验收标准：

```
总线负载 50% 以上时：
- 关键帧最大延迟可测量
- 普通帧允许丢弃或过期
- 关键帧不得静默丢失
```

#### 任务三：CAN-FD BRS

增加：

- 500 kbit/s 仲裁阶段。
- 2 Mbit/s 数据阶段。
- 12、16、20、24、32、48、64 字节 DLC。
- 64 字节接收缓冲。
- 数据阶段错误统计。

验收标准：

```
发送长度：0、8、12、16、32、48、64
要求：
- 接收长度正确
- 内容完全一致
- DLC 映射正确
- 不支持长度被拒绝
```

#### 任务四：ISO-TP 诊断传输

实现：

- Single Frame。
- First Frame。
- Consecutive Frame。
- Flow Control。
- Block Size。
- STmin。
- 超时和会话取消。

重点验证：

```
FF_TIMEOUT
CF_TIMEOUT
FC_TIMEOUT
WRONG_SEQUENCE
BUFFER_OVERFLOW
BUS_BUSY
```

#### 任务五：双 CAN 网关

实现：

- 两个控制器独立驱动。
- 静态路由表。
- 标准帧与扩展帧路由。
- CAN-FD 到 Classical CAN 的长度兼容检查。
- 转发延迟统计。
- 路由环路保护。

### 16.2 性能测试方法

至少记录以下指标：

```
1. RX ISR 延迟
2. RX FIFO 最大深度
3. RX 软件队列最大深度
4. TX 排队延迟
5. TX 到 ACK 的时间
6. 关键消息最坏响应时间
7. 总线负载
8. Error Passive 次数
9. Bus-Off 次数
10. FIFO 溢出次数
11. 队列丢帧次数
12. 数据阶段误码率
```

测试组合：

|测试|方法|
|---|---|
|满载测试|持续发送低优先级帧至 70%~90% 负载|
|仲裁测试|多节点同时发送不同 ID|
|错误注入|断开终端、干扰 CANH/CANL、改变采样点|
|Bus-Off 测试|制造持续 ACK/位错误并验证恢复|
|FIFO 溢出测试|降低接收任务优先级并观察统计|
|Cache 测试|开启 D-Cache，验证 DMA 缓冲一致性|
|温度测试|在最大时钟误差和温度范围内测试|
|拓扑测试|长线、星形支线、不同终端电阻配置|

### 16.3 进阶学习方向

1. **CAN 控制器底层**
    
    - Bosch M_CAN 架构。
    - Message RAM 配置。
    - Tx Event FIFO。
    - Time Triggered Operation。
    - Transceiver Delay Compensation。
2. **协议栈**
    
    - ISO-TP。
    - UDS。
    - CANopen。
    - J1939。
    - AUTOSAR CAN Driver、CanIf、PduR、CanTp。
3. **实时性**
    
    - CAN 消息响应时间分析。
    - 总线负载建模。
    - 优先级分配和任务调度联合分析。
    - 时间同步和控制闭环抖动分析。
4. **可靠性**
    
    - 端到端保护。
    - Alive Counter。
    - CRC。
    - 超时监控。
    - 故障注入与安全状态机。
5. **工程工具**
    
    - CANoe、CANalyzer。
    - SocketCAN。
    - 总线示波器波形分析。
    - Tracealyzer、Percepio、MCU 性能计数器。
    - 自动生成 DBC 编解码代码。

**最终工程结论：CAN/CAN-FD 驱动的核心不是“把一帧数据发出去”，而是同时保证帧格式正确、仲裁优先级合理、队列不失控、错误可恢复、延迟可证明、数据可验证。**