
本课以 **FreeRTOS** 为主线，重点讨论：

- **定长消息队列**：每条消息大小固定，内核负责复制消息内容；
- **变长消息队列**：每条消息长度不同，通常通过指针队列、内存池、消息缓冲区或自定义描述符实现；
- 消息拷贝、所有权转移、队列容量、背压、超时和内存生命周期之间的工程约束。

一个重要结论先给出：

> **FreeRTOS 原生 Queue 是“固定长度元素队列”，不是原生变长消息队列。**  
> 所谓“变长消息队列”通常是“固定大小消息描述符队列 + 外部数据存储”，或者使用 `StreamBuffer` / `MessageBuffer`。

---

# 1. 学习目标

## 1.1 理解

完成本课后，应能够：

- 理解消息队列的生产者—消费者模型。
- 理解定长消息队列和变长消息队列的内存布局差异。
- 理解消息队列的：
    - FIFO 顺序；
    - 阻塞；
    - 超时；
    - 队列满；
    - 队列空；
    - 消息拷贝；
    - 所有权转移。
- 区分消息队列、环形缓冲区、流缓冲区、消息缓冲区和指针队列。
- 理解“传值”和“传指针”两种通信语义的风险差异。

## 1.2 掌握

能够：

- 创建和使用 FreeRTOS 定长消息队列。
- 正确使用 `xQueueSend()`、`xQueueReceive()`、`xQueueSendFromISR()`。
- 设计固定大小消息描述符。
- 使用固定块内存池实现变长数据传递。
- 处理队列满、队列空、消息超时和内存池耗尽。
- 正确处理 DMA 缓冲区、Cache 一致性和数据所有权。
- 使用队列集、覆盖发送和通知机制完成组合设计。

## 1.3 精通

能够：

- 从 `queue.c` 源码分析消息队列的复制、阻塞和唤醒路径。
- 根据消息大小、吞吐量和实时性预算选择传值或传指针。
- 计算队列容量、最大积压、内存占用和端到端延迟。
- 分析队列优先级反转、队列满导致的背压和指针生命周期错误。
- 设计无动态内存、可观测、可恢复的变长消息通道。

## 1.4 能够设计

能够设计：

- UART、TCP、CAN、传感器数据的消息通信架构。
- 定长控制消息与变长数据消息组合通道。
- DMA 缓冲区加指针队列的零拷贝架构。
- 固定块内存池加消息描述符队列。
- 具备超时、背压、丢弃策略、统计和故障恢复能力的工业级消息总线。

---

# 2. 前置要求

## 2.1 知识要求

- C 语言：
    - 结构体、指针和数组；
    - 内存生命周期；
    - `memcpy()`；
    - 对齐；
    - 整数溢出；
    - `const` 和 `volatile`。
- RTOS：
    - 任务状态；
    - 阻塞和唤醒；
    - 优先级调度；
    - Tick 超时；
    - ISR 与任务上下文区别。
- MCU：
    - 中断；
    - DMA；
    - Cache；
    - 内存屏障；
    - 外设 FIFO。
- FreeRTOS：
    - 队列；
    - 信号量；
    - 任务通知；
    - 静态内存分配；
    - `FromISR` API。

## 2.2 技能要求

- 能够实现环形缓冲区和固定块内存池。
- 能够阅读 `queue.c`、`stream_buffer.c`。
- 能够使用逻辑分析仪测量 ISR 到任务的消息延迟。
- 能够查看 map 文件和静态对象大小。
- 能够定位队列满、队列空、消息覆盖和缓冲区悬空指针问题。

---

# 3. 技术概述

## 3.1 消息队列的定义

消息队列是一个由 RTOS 管理的 FIFO 通信对象：

```
生产者：
    Send(message)

消费者：
    Receive(message)
```

队列通常包含：

```
消息存储区
写入位置
读取位置
当前消息数量
最大消息数量
发送等待任务列表
接收等待任务列表
```

抽象模型：

```
typedef struct
{
    uint8_t *storage;
    size_t item_size;
    size_t capacity;
    size_t count;
    size_t write_index;
    size_t read_index;
} message_queue_t;
```

基本约束：

```
0 <= count <= capacity
```

队列满时：

```
发送立即失败，或者发送任务阻塞
```

队列空时：

```
接收立即失败，或者接收任务阻塞
```

---

## 3.2 定长消息队列

定长队列中的每个元素大小一致：

```
队列容量：8
单条消息大小：32 字节
总数据存储：8 × 32 = 256 字节
```

示例：

```
typedef struct
{
    uint32_t command;
    uint32_t argument;
    uint8_t payload[24];
} command_msg_t;
```

创建：

```
QueueHandle_t queue =
    xQueueCreate(8U, sizeof(command_msg_t));
```

发送：

```
command_msg_t msg = {
    .command = CMD_START,
    .argument = 100U
};

xQueueSend(queue, &msg, timeout);
```

特点：

- API 简单；
- 内存布局确定；
- 生命周期清晰；
- 每次发送通常执行一次消息拷贝；
- 不适合大尺寸、长度差异很大的消息。

---

## 3.3 变长消息队列

变长消息意味着每条消息长度可以不同：

```
消息 1：12 字节
消息 2：128 字节
消息 3：37 字节
```

FreeRTOS 原生 Queue 不直接支持这种格式，因为它要求：

```
每个队列项 item_size 固定
```

常见实现方式：

|方案|实现方式|适用场景|
|---|---|---|
|指针队列|队列保存数据指针|大块数据、零拷贝|
|固定块内存池 + 指针队列|预分配多个固定块|工业产品、无堆|
|消息缓冲区|字节流中保存变长消息|单生产者/单消费者|
|StreamBuffer|字节流，不保存消息边界|连续字节流|
|定长最大数组 + length|队列元素固定，实际长度可变|小消息、简单协议|
|外部环形缓冲区 + 描述符队列|队列保存偏移和长度|高吞吐数据平面|

核心结论：

> **变长不是“把队列 item_size 设置成变量”，而是重新设计数据存储和所有权转移。**

---

## 3.4 定长与变长的本质差异

|项目|定长队列|变长队列|
|---|---|---|
|单条消息大小|固定|可变|
|内核直接支持|是|原生 Queue 不直接支持|
|内存管理|简单|需要额外管理|
|消息拷贝|固定长度|可按实际长度或传指针|
|碎片风险|无或低|动态分配时较高|
|生命周期|队列内自包含|指针方案需明确所有权|
|DMA 友好性|一般|指针队列更适合|
|大消息性能|较差|传指针更优|
|实现复杂度|低|中到高|
|故障风险|队列满、拷贝|悬空指针、重复释放、池耗尽|

---

# 4. 核心特性横向对比

## 4.1 FreeRTOS 通信机制对比

|机制|数据模型|消息边界|拷贝方式|多生产者|多消费者|ISR 支持|典型用途|
|---|---|---|---|---|---|---|---|
|Queue|固定大小元素|保留|内核复制|支持|支持|支持|控制消息|
|指针 Queue|固定大小指针|保留|只复制指针|支持|支持|支持|大块数据|
|MessageBuffer|变长字节消息|保留|内核复制|通常单生产者|通常单消费者|支持|帧、命令、日志|
|StreamBuffer|字节流|不保留|内核复制|通常单生产者|通常单消费者|支持|UART、音频流|
|RingBuffer|变长或定长|依实现|通常少拷贝|需设计|需设计|依实现|高吞吐数据|
|EventGroup|位集合|不适用|不传数据|支持|支持|支持|状态同步|
|Task Notification|整数、位或计数|不适用|极低开销|受限|固定任务|支持|单任务快速通知|

## 4.2 传值队列与指针队列

|维度|传值队列|指针队列|
|---|---|---|
|队列保存内容|完整消息|指针或描述符|
|拷贝成本|与消息长度成正比|通常固定 4/8 字节|
|生命周期风险|低|高|
|外部缓冲区管理|不需要|必须管理|
|DMA 适配|较差|较好|
|大消息性能|差|好|
|并发安全|内核负责消息复制|数据区需明确所有权|
|内存占用|容量 × 消息大小|容量 × 指针大小 + 数据池|

## 4.3 MessageBuffer 与 StreamBuffer

|特性|MessageBuffer|StreamBuffer|
|---|---|---|
|消息边界|保留|不保留|
|一次发送一条消息|支持|仅字节流|
|接收缓冲区不足|通常无法取出整条消息|可取部分数据|
|适合协议帧|是|需要上层组帧|
|适合连续采样流|一般|是|
|生产者模型|通常单生产者|通常单生产者|
|消费者模型|通常单消费者|通常单消费者|
|变长数据|原生支持|原生支持，但无边界|

---

# 5. 底层原理与功能特性深度解析

## 5.1 FreeRTOS 定长 Queue 的内部结构

FreeRTOS Queue 的典型内部字段包括：

```
typedef struct QueueDefinition
{
    int8_t *pcHead;
    int8_t *pcWriteTo;

    union
    {
        QueuePointers_t xQueue;
        SemaphoreData_t xSemaphore;
    } u;

    List_t xTasksWaitingToSend;
    List_t xTasksWaitingToReceive;

    volatile UBaseType_t uxMessagesWaiting;
    UBaseType_t uxLength;
    UBaseType_t uxItemSize;

    int8_t *pcReadFrom;
} Queue_t;
```

核心字段：

|字段|含义|
|---|---|
|`pcHead`|数据区起始位置|
|`pcWriteTo`|下一次写入位置|
|`pcReadFrom`|上一次读取位置|
|`uxMessagesWaiting`|当前消息数量|
|`uxLength`|最大消息数量|
|`uxItemSize`|单条消息大小|
|`xTasksWaitingToSend`|队列满时的发送等待任务|
|`xTasksWaitingToReceive`|队列空时的接收等待任务|

队列数据区大小近似为：

```
QueueStorage = uxLength × uxItemSize
```

实际还可能包含：

- 对齐填充；
- 控制块；
- 静态对象对齐；
- 堆管理头部。

---

## 5.2 创建定长队列

动态创建：

```
QueueHandle_t queue =
    xQueueCreate(
        16U,
        sizeof(sensor_sample_t));

if (queue == NULL)
{
    system_fatal_error(
        SYSTEM_ERR_QUEUE_CREATE);
}
```

静态创建：

```
#define SENSOR_QUEUE_LENGTH 16U

static StaticQueue_t s_sensor_queue_control;
static uint8_t s_sensor_queue_storage[
    SENSOR_QUEUE_LENGTH * sizeof(sensor_sample_t)];

static QueueHandle_t s_sensor_queue;

void sensor_queue_init(void)
{
    s_sensor_queue = xQueueCreateStatic(
        SENSOR_QUEUE_LENGTH,
        sizeof(sensor_sample_t),
        s_sensor_queue_storage,
        &s_sensor_queue_control);

    configASSERT(s_sensor_queue != NULL);
}
```

生产要求：

- 存储数组大小必须至少为：

```
length * item_size
```

- `item_size` 必须与发送和接收对象一致；
- 不能把局部变量地址直接作为队列存储区；
- 静态队列存储区的生命周期必须覆盖队列生命周期。

---

## 5.3 `xQueueSend()` 的消息拷贝语义

调用：

```
xQueueSend(queue, &message, timeout);
```

并不会把 `message` 指针保存到队列，而是将其指向的数据复制到队列内部。

简化流程：

```
BaseType_t xQueueGenericSend(
    QueueHandle_t queue,
    const void *item,
    TickType_t timeout,
    BaseType_t position)
{
    for (;;)
    {
        taskENTER_CRITICAL();

        if (queue->uxMessagesWaiting <
            queue->uxLength)
        {
            memcpy(
                queue->pcWriteTo,
                item,
                queue->uxItemSize);

            queue->pcWriteTo =
                advance_write_pointer(queue);

            queue->uxMessagesWaiting++;

            wake_one_waiting_receiver(queue);

            taskEXIT_CRITICAL();
            return pdPASS;
        }

        if (timeout == 0U)
        {
            taskEXIT_CRITICAL();
            return errQUEUE_FULL;
        }

        place_task_on_send_wait_list(
            queue,
            timeout);

        taskEXIT_CRITICAL();

        portYIELD_WITHIN_API();
    }
}
```

实际源码还要处理：

- 队列覆盖发送；
- 队列前端发送；
- 调度器挂起；
- 超时列表；
- 中断并发；
- Trace；
- 临界区范围。

关键结论：

> **发送成功后，原始变量可以立即离开作用域；队列中保存的是数据副本。**

---

## 5.4 `xQueueReceive()` 的消息拷贝语义

```
sensor_sample_t sample;

if (xQueueReceive(
        s_sensor_queue,
        &sample,
        pdMS_TO_TICKS(100)) == pdPASS)
{
    process_sample(&sample);
}
```

内核流程：

```
检查队列是否为空
    |
    +-- 非空：
    |       从 pcReadFrom 复制 item_size 字节
    |       移动读指针
    |       count--
    |       唤醒发送等待任务
    |
    +-- 为空：
            timeout == 0：立即失败
            timeout > 0：任务阻塞
```

接收目标缓冲区必须至少有：

```
sizeof(item_type)
```

否则会发生越界写入。

---

## 5.5 队列满与背压

队列容量有限。发送速度高于接收速度时：

```
队列积压增长
    -> count == capacity
    -> 发送阻塞或失败
```

系统必须选择背压策略：

|策略|实现|适用场景|
|---|---|---|
|阻塞生产者|`xQueueSend(..., timeout)`|事件不能丢，生产者可等待|
|立即丢弃|timeout 为 0|非关键日志、状态刷新|
|丢弃旧消息|`xQueueOverwrite()`|只关心最新状态，队列长度通常为 1|
|降级|降低采样率或丢低优先级数据|资源紧张时|
|DMA 暂停|停止硬件生产|可控硬件链路|
|分级队列|高优先级与普通消息分开|重要消息不能被低优先级填满|

不能无条件使用：

```
xQueueSend(queue, &msg, portMAX_DELAY);
```

否则队列满时生产者可能永久阻塞，且掩盖消费者失效。

---

## 5.6 定长消息中的变长内容

一种简单方式是固定最大长度加实际长度：

```
#define MAX_PAYLOAD_SIZE 128U

typedef struct
{
    uint16_t length;
    uint8_t data[MAX_PAYLOAD_SIZE];
} frame_msg_t;
```

发送：

```
frame_msg_t msg = {0};

if (payload_length > MAX_PAYLOAD_SIZE)
{
    return false;
}

msg.length = payload_length;
memcpy(msg.data, payload, payload_length);

return xQueueSend(
           frame_queue,
           &msg,
           pdMS_TO_TICKS(10)) == pdPASS;
```

优点：

- 实现简单；
- 生命周期安全；
- 消息边界天然保留；
- 不需要外部内存管理。

缺点：

- 每条消息都按最大长度占用队列空间；
- 小消息浪费 RAM；
- 大消息复制开销较高。

适用于：

```
最大消息长度不大
消息大小差异有限
实时性和可靠性优先
```

---

## 5.7 指针队列：变长消息的常用实现

定义消息描述符：

```
typedef struct
{
    uint8_t *data;
    uint16_t length;
    uint16_t capacity;
    uint32_t timestamp;
    uint16_t type;
} message_desc_t;
```

队列保存的是：

```
sizeof(message_desc_t)
```

而不是完整数据。

创建：

```
QueueHandle_t queue =
    xQueueCreate(
        8U,
        sizeof(message_desc_t));
```

发送：

```
message_desc_t desc = {
    .data = buffer,
    .length = length,
    .capacity = capacity,
    .timestamp = get_timestamp(),
    .type = MSG_SENSOR_FRAME
};

if (xQueueSend(
        queue,
        &desc,
        pdMS_TO_TICKS(10)) != pdPASS)
{
    release_buffer(buffer);
}
```

接收：

```
message_desc_t desc;

if (xQueueReceive(
        queue,
        &desc,
        pdMS_TO_TICKS(100)) == pdPASS)
{
    process_message(desc.data, desc.length);
    release_buffer(desc.data);
}
```

关键约束：

> 队列只复制指针和描述符，不负责复制指针指向的数据，也不负责释放数据。

---

## 5.8 指针队列的所有权协议

推荐定义明确的状态：

```
FREE：
    内存池持有，生产者可申请

FILLING：
    生产者正在写入，不能发送

QUEUED：
    指针已经进入队列，消费者拥有处理权

PROCESSING：
    消费者正在处理

RETURNING：
    消费者完成校验，准备归还池

FREE：
    重新回到内存池
```

状态转移：

```
FREE -> FILLING -> QUEUED -> PROCESSING -> FREE
```

禁止：

```
生产者发送指针后继续修改缓冲区
消费者释放后继续访问缓冲区
多个任务同时释放同一缓冲区
```

---

## 5.9 固定块内存池 + 指针队列

这是工业项目中最常见的变长消息方案之一。

架构：

```
固定块内存池
    |
    +-- 申请一个块
    +-- 写入实际长度的数据
    +-- 发送指针/描述符
    |
    v
指针队列
    |
    +-- 接收描述符
    +-- 处理实际长度
    +-- 归还内存块
```

定义：

```
#define RX_BLOCK_COUNT 16U
#define RX_BLOCK_SIZE  512U

typedef struct
{
    uint16_t length;
    uint16_t type;
    uint32_t timestamp;
    uint8_t data[RX_BLOCK_SIZE];
} rx_block_t;

typedef struct
{
    rx_block_t *block;
    uint16_t length;
    uint16_t type;
    uint32_t timestamp;
} rx_message_t;
```

队列保存：

```
sizeof(rx_message_t)
```

池保存：

```
RX_BLOCK_COUNT × sizeof(rx_block_t)
```

这样每条消息实际有效长度可以变化，但最大长度受块大小限制。

---

## 5.10 MessageBuffer 的内部思想

FreeRTOS `MessageBuffer` 适合单生产者、单消费者的变长消息传递。

其逻辑存储布局类似：

```
[消息长度][消息数据][消息长度][消息数据]...
```

发送：

```
写入消息长度
写入消息内容
```

接收：

```
读取消息长度
确认目标缓冲区足够
复制完整消息
```

典型接口：

```
MessageBufferHandle_t xMessageBufferCreate(
    size_t size);

size_t xMessageBufferSend(
    MessageBufferHandle_t xMessageBuffer,
    const void *pvTxData,
    size_t xDataLengthBytes,
    TickType_t xTicksToWait);

size_t xMessageBufferReceive(
    MessageBufferHandle_t xMessageBuffer,
    void *pvRxData,
    size_t xBufferLengthBytes,
    TickType_t xTicksToWait);
```

特点：

- 原生支持变长消息；
- 具有消息边界；
- 内核会复制数据；
- 发送者和接收者通常应分别只有一个；
- 不适合天然多生产者、多消费者模型。

---

## 5.11 StreamBuffer 与 MessageBuffer 的选择

### MessageBuffer

```
一条发送操作对应一条接收消息
```

适合：

- 协议帧；
- 变长命令；
- 日志记录；
- 单生产者到单消费者。

### StreamBuffer

```
只保证字节序列连续，不保证应用消息边界
```

适合：

- UART 字节流；
- 音频采样流；
- 网络字节流；
- 连续传感器数据。

如果协议帧为：

```
帧头 + 长度 + 载荷 + CRC
```

可以使用 StreamBuffer，再由任务实现组帧状态机。

---

## 5.12 ISR 发送消息

定长消息：

```
void USART1_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    uart_event_t event;

    if (uart_frame_complete())
    {
        event.type = UART_EVENT_FRAME_READY;
        event.length = uart_get_frame_length();

        if (xQueueSendFromISR(
                g_uart_event_queue,
                &event,
                &woken) != pdPASS)
        {
            g_uart_event_queue_overflow++;
        }
    }

    portYIELD_FROM_ISR(woken);
}
```

限制：

- ISR 发送的数据必须位于有效内存；
- `xQueueSendFromISR()` 会复制数据；
- 不要在 ISR 中发送大消息；
- 不能使用普通 `xQueueSend()`；
- 必须检查队列满。

指针消息：

```
void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    rx_message_t message;

    rx_block_t *block = dma_get_completed_block();

    if (block != NULL)
    {
        message.block = block;
        message.length = block->length;
        message.type = block->type;

        if (xQueueSendFromISR(
                g_rx_queue,
                &message,
                &woken) != pdPASS)
        {
            /*
             * 发送失败时必须归还 DMA 块，
             * 否则缓冲池会逐渐耗尽。
             */
            dma_release_block_from_isr(block);
        }
    }

    portYIELD_FROM_ISR(woken);
}
```

注意：

- ISR 发送指针后，硬件不能继续写这个缓冲区；
- 需要明确 DMA 所有权转移时刻；
- Cortex-M7 等带 Cache 平台需要执行 Cache 维护操作。

---

# 6. 性能量化分析

## 6.1 测试平台与数据边界

以下给出：

- 可直接计算的内存公式；
- 典型平台上的测量方法；
- 设计预算示例。

除公式外，具体周期必须通过目标工程实测确认。

参考平台：

```
MCU：STM32F407
CPU：Cortex-M4F，168 MHz
FreeRTOS：固定版本
编译：GCC -O2
Tick：1 kHz
测量：DWT CYCCNT + GPIO
```

## 6.2 定长队列内存公式

设：

```
N：队列长度
S：单条消息大小
C：Queue 控制块大小
A：堆管理额外开销
```

动态队列 RAM 近似为：

```
Rqueue = C + N × S + A
```

静态队列 RAM 近似为：

```
Rqueue_static = sizeof(StaticQueue_t) + N × S
```

例如：

```
N = 16
S = 32 字节
```

数据存储区：

```
16 × 32 = 512 字节
```

如果使用指针队列：

```
N = 16
S = 8 字节
```

队列数据区：

```
16 × 8 = 128 字节
```

但还要额外分配数据池。

若数据池为：

```
16 × 512 = 8192 字节
```

则总数据相关 RAM：

```
128 + 8192 = 8320 字节
```

它可能比直接定长队列更大，但可以：

- 支持实际变长数据；
- 避免每条消息都占用最大长度；
- 与 DMA 缓冲区共享；
- 减少大块复制。

## 6.3 拷贝成本模型

传值队列的单次数据拷贝成本近似：

```
Tcopy = Tfixed + S / Bmemory
```

其中：

- `S`：消息字节数；
- `Bmemory`：有效内存复制带宽；
- `Tfixed`：函数调用、边界和调度固定开销。

端到端传值通常包含：

```
生产者栈/缓冲区 -> 队列
队列 -> 消费者缓冲区
```

因此总复制字节数约为：

```
Bytes_total ≈ 2 × S
```

指针队列通常为：

```
Bytes_total ≈ 2 × sizeof(pointer/descriptor)
```

但数据本体不会被复制，消费者必须直接访问外部缓冲区。

## 6.4 典型内存复制预算

若消息大小：

```
S = 1024 字节
```

每秒消息数量：

```
R = 1000 messages/s
```

若采用完整传值队列，粗略复制流量：

```
CopyRate ≈ 2 × 1024 × 1000
         = 2,048,000 字节/s
         ≈ 1.95 MiB/s
```

这还未包含：

- Cache 操作；
- 对齐；
- 协议解析；
- DMA；
- 其他任务复制。

若采用指针队列，队列数据复制可能仅为：

```
2 × sizeof(pointer)
```

通常只有 8~16 字节级别，但需要承担：

- 缓冲区管理；
- 生命周期验证；
- Cache 一致性；
- 池耗尽处理。

## 6.5 队列容量计算

设：

```
λp：生产速率
λc：消费速率
Tb：最大突发时间
Tblock：消费者最长不可服务时间
```

最小容量可估算为：

```
Nmin >= max(
    (λp - λc) × Tb,
    λp × Tblock
)
```

还需增加：

```
调度裕量
中断抖动裕量
故障恢复裕量
```

示例：

```
生产速率：2000 条/s
消费速率：1500 条/s
最大突发：100 ms
消费者最长不可服务：20 ms
```

突发积压：

```
(2000 - 1500) × 0.1 = 50 条
```

消费者暂停期间积压：

```
2000 × 0.02 = 40 条
```

至少应选择：

```
N >= 50 + 裕量
```

例如配置 64 或 80，而不是机械地配置 50。

## 6.6 端到端延迟模型

消息从生产到消费的端到端延迟：

```
Tend_to_end =
    Tisr_or_producer
  + Tqueue_send
  + Twait
  + Tschedule
  + Tqueue_receive
  + Tprocess_start
```

其中最大延迟通常由：

- 前面消息数量；
- 消费者处理时间；
- 高优先级任务抢占；
- 中断延迟；
- 队列竞争；
- 消费者自身阻塞；

共同决定。

如果队列当前积压 `Q` 条，消费者单条处理最坏时间为 `Tprocess_wcet`：

```
Tqueue_delay ≈ Q × Tprocess_wcet
```

因此，队列容量越大不一定实时性越好。过大的队列可能只是把延迟转化为积压。

## 6.7 定长与指针队列的典型取舍

|指标|定长传值|指针队列|
|---|---|---|
|小消息延迟|通常较好|需要池申请，可能相当|
|大消息延迟|随消息长度增加|通常更好|
|RAM 可预测性|高|高，若使用静态池|
|开发复杂度|低|中高|
|内存安全|容易保证|依赖所有权协议|
|DMA|一般|更适合|
|故障恢复|队列重建较简单|需回收所有未消费缓冲区|

## 6.8 性能优化手段

|手段|主要收益|
|---|---|
|控制消息传值，数据消息传指针|降低大块复制|
|使用静态队列和静态内存池|消除堆碎片|
|批量接收|减少调度和函数调用次数|
|DMA + 指针队列|提高吞吐、降低 CPU 占用|
|将高优先级消息独立队列|降低关键消息排队延迟|
|队列元素只放描述符|降低队列数据区|
|预分配消息对象|避免运行时 malloc|
|统计队列高水位|防止容量不足被隐藏|
|消息合并|降低高频小消息调度开销|

---

# 7. 应用场景选型指南

## 7.1 决策流程图

```
需要传递数据？
|
+-- 否
|   +-- 使用任务通知、信号量或事件组
|
+-- 是
    |
    +-- 每条消息大小是否固定且较小？
    |   |
    |   +-- 是 -> 定长 Queue 传值
    |
    +-- 否
        |
        +-- 是否需要保留消息边界？
        |   |
        |   +-- 否 -> StreamBuffer / 字节环形缓冲区
        |
        |   +-- 是
        |       |
        |       +-- 是否单生产者、单消费者？
        |       |   |
        |       |   +-- 是 -> MessageBuffer
        |       |
        |       +-- 是否需要多生产者/多消费者？
        |           |
        |           +-- 是 -> 固定块内存池 + 描述符 Queue
        |
        +-- 数据是否很大或来自 DMA？
            |
            +-- 是 -> 指针/描述符 Queue + 明确所有权
            +-- 否 -> 最大长度数组 + length 字段
```

## 7.2 典型场景选型

|场景|推荐方案|理由|
|---|---|---|
|控制命令|定长 Queue 传值|消息小、生命周期简单|
|UART 字节流|StreamBuffer|不必为每字节创建队列元素|
|UART 完整帧|MessageBuffer 或描述符队列|保留帧边界|
|TCP 大报文|缓冲池 + 指针队列|避免大块复制|
|CAN 固定帧|定长 Queue|帧格式固定|
|DMA 音频块|DMA 缓冲区 + 指针队列|零拷贝或少拷贝|
|日志消息|MessageBuffer 或固定日志块|变长、通常单生产者|
|多任务事件|定长 Queue|消息结构明确|
|高优先级报警|独立报警队列|防止被普通消息填满|
|最新状态|长度为 1 的覆盖队列|旧值可丢弃|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：控制面和数据面分离

控制消息：

```
typedef struct
{
    uint16_t command;
    uint16_t argument;
} control_msg_t;
```

大块数据：

```
typedef struct
{
    uint8_t *data;
    uint32_t length;
    uint16_t type;
} data_desc_t;
```

不要把 4 KB 数据直接塞进高频控制消息队列。

### 原则二：传指针必须传所有权

推荐文档化：

```
Send 成功后：
    生产者不再访问 buffer

Receive 成功后：
    消费者独占 buffer

Process 完成后：
    消费者调用 release_buffer()

Send 失败：
    发送者负责 release_buffer()
```

### 原则三：队列满必须有业务策略

至少选择一种：

```
阻塞
丢新
丢旧
覆盖
降级
反压
复位生产者
```

不能默认静默丢失。

### 原则四：消息结构包含版本和长度

适用于跨模块接口：

```
typedef struct
{
    uint16_t version;
    uint16_t header_size;
    uint32_t payload_length;
    uint32_t sequence;
} message_header_t;
```

这样有利于：

- 兼容字段扩展；
- 边界校验；
- 诊断；
- 接口版本管理。

### 原则五：每条变长消息都要校验长度

```
if (msg.length > msg.capacity)
{
    report_protocol_fault();
    release_message(&msg);
    return;
}
```

不要信任来自 ISR、DMA、网络或其他模块的长度字段。

## 8.2 选型决策矩阵

|需求|定长 Queue|指针 Queue|MessageBuffer|StreamBuffer|
|---|---|---|---|---|
|小控制消息|5|2|3|1|
|大块数据|1|5|3|4|
|变长且保留边界|2|5|5|2|
|多生产者|5|5|2|2|
|多消费者|5|5|2|2|
|单生产者/单消费者|4|5|5|5|
|DMA|2|5|2|3|
|生命周期简单|5|2|4|4|
|无堆内存|5|5|5|5|
|零拷贝|1|5|1|1|

评分仅表示典型适配度，不替代具体约束分析。

## 8.3 工业级编码规范

### 定长队列

```
BaseType_t result = xQueueSend(
    queue,
    &message,
    pdMS_TO_TICKS(20));

if (result != pdPASS)
{
    queue_send_timeout_or_full();
}
```

### ISR 队列发送

```
BaseType_t woken = pdFALSE;

if (xQueueSendFromISR(
        queue,
        &message,
        &woken) != pdPASS)
{
    isr_queue_overflow_count++;
}

portYIELD_FROM_ISR(woken);
```

### 指针队列

必须为每个所有权路径提供：

```
allocate
send
receive
release
send_fail_release
consumer_abort_release
queue_delete_drain
```

### 删除队列前清空外部对象

如果队列中存的是指针，删除队列不会自动释放指针指向的内存。

正确流程：

```
停止生产者
停止 DMA
逐条取出队列中的描述符
释放对应缓冲区
删除队列
销毁内存池
```

---

# 9. 常见错误与避坑指南

## 9.1 错误一：把局部变量指针发送到指针队列

### 错误代码

```
void producer_task(void *argument)
{
    uint8_t local_buffer[128];

    fill_data(local_buffer);

    uint8_t *ptr = local_buffer;

    xQueueSend(
        g_pointer_queue,
        &ptr,
        portMAX_DELAY);

    /* 函数返回或下一轮循环后 local_buffer 失效或被覆盖 */
}
```

### 根因分析

队列只复制了：

```
local_buffer 的地址
```

没有复制数据本体。

### 正确实现

使用静态池或生命周期足够长的缓冲区：

```
rx_block_t *block =
    buffer_pool_acquire(pdMS_TO_TICKS(10));

if (block == NULL)
{
    return;
}

block->length = fill_data(
    block->data,
    sizeof(block->data));

if (xQueueSend(
        g_pointer_queue,
        &block,
        pdMS_TO_TICKS(10)) != pdPASS)
{
    buffer_pool_release(block);
}
```

### 风险影响

- 悬空指针；
- 数据被覆盖；
- HardFault；
- 偶现协议解析错误。

---

## 9.2 错误二：发送指针后生产者继续使用缓冲区

### 错误代码

```
xQueueSend(g_queue, &buffer, 0);

/* 错误：消费者可能已经开始读取 */
fill_next_frame(buffer);
```

### 根因分析

发送成功意味着所有权已经转移，生产者不能继续修改。

### 正确实现

```
if (xQueueSend(
        g_queue,
        &buffer,
        pdMS_TO_TICKS(10)) == pdPASS)
{
    buffer = NULL; /* 本任务不再拥有 */
}
else
{
    buffer_pool_release(buffer);
    buffer = NULL;
}
```

### 风险影响

- 生产者和消费者数据竞争；
- CRC 错误；
- DMA 与 CPU 同时修改；
- 数据帧撕裂。

---

## 9.3 错误三：定长队列元素大小配置错误

### 错误代码

```
QueueHandle_t queue =
    xQueueCreate(
        8U,
        sizeof(uint8_t));

command_msg_t message;

xQueueSend(queue, &message, 0U);
```

### 根因分析

队列只复制一个字节，但接收者可能按完整结构体读取，或者结构体队列与字节队列语义混用。

### 正确实现

```
QueueHandle_t queue =
    xQueueCreate(
        8U,
        sizeof(command_msg_t));
```

发送和接收必须使用相同类型：

```
command_msg_t tx;
command_msg_t rx;

xQueueSend(queue, &tx, timeout);
xQueueReceive(queue, &rx, timeout);
```

### 风险影响

- 数据截断；
- 接收缓冲区部分未初始化；
- 越界读取；
- 接口兼容性破坏。

---

## 9.4 错误四：把 MessageBuffer 当作多生产者队列

### 错误代码

```
/* 任务 A */
xMessageBufferSend(
    g_message_buffer,
    data_a,
    length_a,
    0U);

/* 任务 B */
xMessageBufferSend(
    g_message_buffer,
    data_b,
    length_b,
    0U);
```

### 根因分析

FreeRTOS MessageBuffer/StreamBuffer 通常针对：

```
单生产者、单消费者
```

设计。多个生产者同时调用可能破坏内部读写状态或违反使用约束。

### 正确实现

方案一：

```
每个生产者拥有独立 MessageBuffer
消费者通过多个消息源接收
```

方案二：

```
多个生产者先进入 Queue
由一个聚合任务写入 MessageBuffer
```

方案三：

```
使用原生 Queue 或固定块池 + 指针 Queue
```

### 风险影响

- 内部索引破坏；
- 消息边界异常；
- 数据交错；
- 偶现系统崩溃。

---

## 9.5 错误五：队列满时静默丢弃

### 错误代码

```
(void)xQueueSend(
    g_event_queue,
    &event,
    0U);
```

### 根因分析

忽略发送返回值，无法区分：

```
消息已经排队
消息被丢弃
队列对象失效
```

### 正确实现

```
if (xQueueSend(
        g_event_queue,
        &event,
        pdMS_TO_TICKS(5)) != pdPASS)
{
    g_event_drop_count++;
    diagnostic_report(
        DIAG_EVENT_QUEUE_FULL,
        event.type);
}
```

根据业务进一步选择：

- 丢弃低优先级事件；
- 合并同类事件；
- 扩容队列；
- 降低生产速率；
- 进入背压状态。

### 风险影响

- 控制命令丢失；
- 状态机不同步；
- 故障告警遗漏；
- 数据完整性无法证明。

---

## 9.6 错误六：消费者释放后继续使用指针

### 错误代码

```
rx_block_t *block;

if (xQueueReceive(
        g_queue,
        &block,
        timeout) == pdPASS)
{
    buffer_pool_release(block);

    log_payload(block->data, block->length);
}
```

### 根因分析

释放后该块可能立即被其他生产者重新分配和覆盖。

### 正确实现

```
if (xQueueReceive(
        g_queue,
        &block,
        timeout) == pdPASS)
{
    process_payload(block->data, block->length);

    buffer_pool_release(block);
    block = NULL;
}
```

如果日志必须异步执行：

```
复制日志所需数据
或转移缓冲区所有权给日志任务
```

### 风险影响

- Use-after-free；
- 日志内容随机；
- 数据竞争；
- 内存池状态异常。

---

## 9.7 错误七：接收缓冲区小于消息长度

### 错误代码

```
uint8_t buffer[32];

xQueueReceive(
    g_queue,       /* 队列元素是 128 字节 */
    buffer,
    timeout);
```

### 根因分析

`xQueueReceive()` 会按队列元素大小复制，不会根据目标数组实际大小自动截断。

### 正确实现

```
typedef struct
{
    uint16_t length;
    uint8_t data[128];
} frame_t;

frame_t frame;

if (xQueueReceive(
        g_queue,
        &frame,
        timeout) == pdPASS)
{
    if (frame.length <= sizeof(frame.data))
    {
        process_frame(&frame);
    }
}
```

### 风险影响

- 栈破坏；
- 相邻变量覆盖；
- 返回地址损坏；
- HardFault。

---

# 10. 多机制组合使用方案

## 10.1 定长控制队列 + 变长数据队列

典型架构：

```
控制面：
    Queue<control_msg_t>

数据面：
    BufferPool + Queue<data_desc_t>

控制消息中只保存：
    数据类型
    数据块索引
    长度
    序号
```

示例：

```
typedef struct
{
    uint16_t command;
    uint16_t flags;
    uint32_t sequence;
} control_msg_t;

typedef struct
{
    rx_block_t *block;
    uint16_t length;
    uint16_t type;
} data_desc_t;
```

优点：

- 控制消息小且确定；
- 大块数据不重复复制；
- 可分别配置控制面和数据面的优先级与容量；
- 可对数据面执行丢弃或背压。

---

## 10.2 DMA + 指针队列 + 固定块池

```
DMA 完成中断
    |
    +-- 当前 DMA 块所有权转给软件
    +-- 提交 block 指针到 Queue
    +-- 切换到下一个空闲块
    |
    v
处理任务
    |
    +-- Receive block
    +-- Cache invalidate
    +-- 校验长度
    +-- 处理数据
    +-- Release block
```

关键状态：

```
DMA_OWNED
CPU_OWNED
QUEUED
PROCESSING
FREE
```

禁止：

```
DMA_OWNED 与 CPU_OWNED 同时存在
```

---

## 10.3 多生产者安全的变长消息方案

由于 MessageBuffer 通常要求单生产者，多个生产者可以采用：

```
生产者 A -> Queue<producer_event>
生产者 B -> Queue<producer_event>
生产者 C -> Queue<producer_event>
                |
                v
        Message Aggregator Task
                |
                v
          MessageBuffer
```

更常用的是直接：

```
多个生产者 -> 固定块池 + 原生指针 Queue -> 消费者
```

这样避免了 MessageBuffer 的单生产者限制。

---

## 10.4 零拷贝描述符框架

```
#define DATA_POOL_COUNT 8U
#define DATA_BLOCK_SIZE 1024U

typedef struct
{
    uint8_t data[DATA_BLOCK_SIZE];
    uint16_t length;
    uint16_t type;
    uint32_t sequence;
} data_block_t;

typedef struct
{
    data_block_t *block;
    uint16_t length;
    uint16_t type;
    uint32_t sequence;
} data_desc_t;

static QueueHandle_t g_desc_queue;
static SemaphoreHandle_t g_free_count;
static StaticSemaphore_t g_free_count_storage;

static bool data_submit(data_block_t *block)
{
    data_desc_t desc = {
        .block = block,
        .length = block->length,
        .type = block->type,
        .sequence = block->sequence
    };

    if (xQueueSend(
            g_desc_queue,
            &desc,
            pdMS_TO_TICKS(5)) != pdPASS)
    {
        data_block_release(block);
        return false;
    }

    return true;
}

static void data_consumer_task(void *argument)
{
    data_desc_t desc;

    (void)argument;

    for (;;)
    {
        if (xQueueReceive(
                g_desc_queue,
                &desc,
                pdMS_TO_TICKS(100)) != pdPASS)
        {
            data_consumer_timeout();
            continue;
        }

        if (desc.block == NULL ||
            desc.length > DATA_BLOCK_SIZE ||
            desc.length != desc.block->length)
        {
            data_protocol_fault();

            if (desc.block != NULL)
            {
                data_block_release(desc.block);
            }

            continue;
        }

        process_data(
            desc.block->data,
            desc.length,
            desc.type);

        data_block_release(desc.block);
    }
}
```

工程中还需要：

- 检查 `block` 地址是否属于池；
- 检查序号是否重复；
- 检查状态是否为 `QUEUED`；
- 释放时执行状态转换；
- 队列删除前排空所有描述符。

---

# 11. 工业级实际案例分析

## 11.1 案例一：UART 协议帧接收

### 需求

- UART 波特率：3 Mbps；
- 帧长度：8~512 字节；
- DMA 循环接收；
- 需要保留帧边界；
- 协议解析在任务中完成；
- 不能逐字节唤醒任务。

### 架构

```
UART DMA
    |
    +-- 空闲线/半传输/全传输中断
    +-- 将新增字节写入环形缓冲区
    +-- 发送帧边界事件
    |
    v
Protocol Task
    |
    +-- 从环形缓冲区组帧
    +-- CRC 校验
    +-- 命令分发
```

如果 DMA 已经写入连续字节流，推荐：

```
StreamBuffer 或环形缓冲区
```

如果 ISR 已经识别完整帧，并且帧长度变化较大：

```
固定块内存池 + 指针 Queue
```

### 设计要点

- 不要为每个字节发送一个 Queue 消息；
- DMA 接收和 CPU 解析必须有明确的读写索引；
- DMA 重新使用缓冲区前，必须确认消费者完成；
- 帧长度必须检查上限；
- CRC 失败的帧也必须正确归还缓冲区。

---

## 11.2 案例二：ADC 多缓冲数据采集

### 需求

- ADC 采样率：200 kHz；
- 每块采样点数：256；
- 4 个 DMA 缓冲块；
- 算法任务执行滤波和特征提取；
- 每个缓冲块必须按顺序处理。

### 时间预算

单块到达周期：

```
Tblock = 256 / 200000
       = 1.28 ms
```

若算法最坏处理时间：

```
Tprocess_wcet = 900 μs
```

尚有约：

```
1.28 ms - 0.90 ms = 380 μs
```

用于：

- 中断；
- 调度；
- 其他任务；
- 处理抖动；
- Cache 操作。

### 推荐实现

```
DMA block 0 完成
    -> 发送 block 0 指针

DMA 切换 block 1
    -> 继续采样

算法任务
    -> 接收 block 0
    -> 处理
    -> 归还 block 0
```

### 设计要点

- DMA 缓冲块数量必须能覆盖任务最长阻塞时间；
- 队列满时不能简单释放仍由 DMA 使用的块；
- 如果处理不及时，应统计：
    - 队列高水位；
    - 块池耗尽；
    - DMA 覆盖次数；
    - 处理超时。
- Cortex-M7 上要执行 DMA Cache 维护。

---

## 11.3 案例三：工业控制命令与大块诊断数据

### 需求

- 高优先级控制命令消息较小；
- 低优先级诊断任务产生变长日志；
- 控制命令不能被诊断日志挤占；
- 日志长度为 32~1024 字节。

### 架构

```
控制队列：
    Queue<control_msg_t>
    高优先级任务消费

日志数据池：
    固定块或分级块池

日志描述符队列：
    Queue<log_desc_t>
    低优先级任务消费
```

禁止使用一个大队列混合：

```
控制命令 + 大块日志
```

原因：

- 大消息可能填满队列；
- 控制命令排队延迟不可预测；
- 队列元素必须按最大消息尺寸配置；
- 诊断流量可能影响控制闭环。

### 设计要点

- 控制面和数据面独立容量；
- 控制消息优先级独立；
- 日志池耗尽时执行丢弃或降级；
- 日志不得阻塞控制路径；
- 记录日志丢弃数量和最高占用量。

---

# 12. 高频问题深度答疑

## 问题一：FreeRTOS Queue 是传指针还是传值？

默认是**传值**。

调用：

```
xQueueSend(queue, &msg, timeout);
```

会把 `msg` 指向的 `item_size` 字节复制到队列存储区。

如果你希望传指针，必须显式定义：

```
QueueHandle_t queue =
    xQueueCreate(8U, sizeof(data_block_t *));
```

然后发送指针变量的地址：

```
data_block_t *block = ...;

xQueueSend(queue, &block, timeout);
```

此时队列只复制指针。

---

## 问题二：为什么不直接使用 `malloc()` 实现变长消息？

可以，但在工业 MCU 产品中通常存在风险：

- 堆碎片；
- 分配时间不确定；
- 释放路径复杂；
- 异常路径容易泄漏；
- 多任务并发分配增加锁竞争；
- 长期运行后行为退化。

更推荐：

```
固定块内存池
分级块内存池
静态环形缓冲区
预分配消息对象
```

如果必须动态分配，应至少具备：

- 分配失败处理；
- 最大耗时测量；
- 碎片监控；
- 泄漏检测；
- 看门狗和故障恢复策略。

---

## 问题三：MessageBuffer 和 Queue 到底如何选择？

选择 Queue：

```
多生产者或多消费者
消息结构固定
需要按优先级或位置发送
需要多个任务竞争消费
```

选择 MessageBuffer：

```
单生产者
单消费者
消息长度变化
必须保留消息边界
希望减少自定义内存管理
```

选择 StreamBuffer：

```
单生产者
单消费者
只关心连续字节流
消息边界由上层协议解析
```

---

## 问题四：消息队列可以实现优先级消息吗？

普通 FreeRTOS Queue 是 FIFO，不会根据消息内部的优先级字段自动排序。

可选方案：

1. 高优先级和普通消息分离两个队列；
2. 维护有序队列；
3. 使用队列前端发送：
    
    ```
    xQueueSendToFront()
    ```
    
4. 使用优先级调度任务；
5. 使用集中消息调度器。

不建议依赖频繁的 `SendToFront()` 模拟完整优先级队列，因为可能造成低优先级消息饥饿。

---

## 问题五：队列容量越大越好吗？

不是。

容量过小：

```
容易满
产生阻塞或丢消息
```

容量过大：

```
隐藏消费能力不足
增加 RAM
放大最坏排队延迟
使故障发现变晚
```

队列容量应根据：

```
峰值生产速率
消费速率
最长不可服务时间
可接受延迟
故障恢复时间
```

计算，并通过高水位统计验证。

---

## 问题六：指针队列是零拷贝吗？

不一定。

指针队列只避免了：

```
数据本体复制到 Queue
```

但仍可能存在：

- 生产者写入数据的复制；
- DMA 到内存的硬件写入；
- 消费者处理时的中间复制；
- Cache 维护；
- 数据格式转换。

更准确的说法是：

> **指针队列通常是“少拷贝”或“避免队列层大块复制”，是否零拷贝取决于整个数据路径。**

---

# 13. 课程核心总结

## 13.1 核心要点

1. **FreeRTOS 原生 Queue 的元素大小固定。**
2. 定长队列通过内核复制保存完整消息。
3. 变长消息需要使用：
    - 最大长度数组；
    - 指针队列；
    - 固定块池；
    - MessageBuffer；
    - StreamBuffer；
    - 自定义环形缓冲区。
4. 指针队列的关键不是发送指针，而是定义所有权。
5. 队列满必须有背压、丢弃或降级策略。
6. Queue 适合多生产者、多消费者和结构化消息。
7. MessageBuffer/StreamBuffer 通常适合单生产者、单消费者。
8. 大消息、DMA 数据和高吞吐链路优先评估指针队列。
9. 控制面和数据面应分离，避免大数据阻塞控制消息。
10. 删除保存指针的队列不会自动释放外部缓冲区。

## 13.2 性能排序

针对大块数据的典型数据路径：

```
DMA + 指针队列
    >
固定块池 + 指针队列
    >
MessageBuffer
    >
定长大数组 Queue 传值
```

针对小型控制消息：

```
定长 Queue 传值
    >
指针队列
```

因为小消息传值的生命周期更简单，指针管理的额外复杂度未必有收益。

## 13.3 通用选型结论

```
小而固定的控制消息：
    定长 Queue

变长且单生产者/单消费者：
    MessageBuffer

连续字节流：
    StreamBuffer

大块数据或 DMA：
    固定块池 + 指针 Queue

多生产者、多消费者的变长消息：
    固定块池 + 原生 Queue<描述符>

只需传递事件数量：
    计数信号量或任务通知

只需传递状态：
    事件组或任务通知位
```

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|推荐方案|
|---|---|
|小型控制命令|定长 Queue|
|CAN 固定帧|定长 Queue|
|UART 字节流|StreamBuffer|
|UART 完整帧|MessageBuffer 或指针 Queue|
|TCP 大报文|缓冲池 + 指针 Queue|
|ADC/DMA 数据块|DMA 缓冲池 + 指针 Queue|
|日志|MessageBuffer 或日志块池|
|最新状态|长度为 1 的覆盖 Queue|
|多生产者变长消息|固定块池 + 原生 Queue|
|高优先级报警|独立报警队列|
|多条件状态|EventGroup|
|单任务事件|Task Notification|

## 14.2 API 速查表

|需求|FreeRTOS API|
|---|---|
|动态创建定长队列|`xQueueCreate()`|
|静态创建定长队列|`xQueueCreateStatic()`|
|任务发送|`xQueueSend()`|
|任务接收|`xQueueReceive()`|
|ISR 发送|`xQueueSendFromISR()`|
|ISR 接收|`xQueueReceiveFromISR()`|
|发送到队首|`xQueueSendToFront()`|
|覆盖发送|`xQueueOverwrite()`|
|查询队列消息数|`uxQueueMessagesWaiting()`|
|查询剩余空间|`uxQueueSpacesAvailable()`|
|删除队列|`vQueueDelete()`|
|创建变长消息缓冲区|`xMessageBufferCreate()`|
|发送变长消息|`xMessageBufferSend()`|
|接收变长消息|`xMessageBufferReceive()`|
|创建流缓冲区|`xStreamBufferCreate()`|
|发送流数据|`xStreamBufferSend()`|
|接收流数据|`xStreamBufferReceive()`|

## 14.3 关键约束表

|项目|约束|
|---|---|
|Queue 元素大小|固定|
|Queue 发送语义|默认复制数据|
|指针 Queue|必须管理数据生命周期|
|MessageBuffer|通常单生产者、单消费者|
|StreamBuffer|不保留消息边界|
|ISR API|使用 `FromISR` 版本|
|队列满|必须检查返回值|
|指针发送失败|必须回收缓冲区|
|队列删除|不会自动释放外部指针|
|DMA 缓冲区|必须明确硬件/CPU 所有权|
|Cache 平台|处理 DMA Cache 一致性|
|长度字段|必须做上限和一致性校验|

# 15. 学习效果自检

## 基础能力

- [ ]  能解释 FreeRTOS Queue 为什么是定长元素。
- [ ]  能区分 Queue、MessageBuffer 和 StreamBuffer。
- [ ]  能说明 Queue 的传值语义。
- [ ]  能说明指针 Queue 的所有权转移规则。
- [ ]  能解释队列满和队列空时的行为。

## API 能力

- [ ]  能正确创建静态定长队列。
- [ ]  能正确使用 `xQueueSend()` 和 `xQueueReceive()`。
- [ ]  能正确使用 `xQueueSendFromISR()`。
- [ ]  能检查队列满和超时。
- [ ]  能使用 `xMessageBufferSend()` 传递变长消息。
- [ ]  能使用 `xStreamBufferReceive()` 接收字节流。

## 工程设计能力

- [ ]  能设计固定长度控制消息队列。
- [ ]  能设计固定块池加指针队列。
- [ ]  能设计 DMA 缓冲区所有权转移。
- [ ]  能处理指针队列发送失败。
- [ ]  能处理消费者异常退出和缓冲区归还。
- [ ]  能为队列容量计算高水位和最坏积压。
- [ ]  能区分单生产者模型和多生产者模型。

## 性能验证能力

- [ ]  能测量传值队列发送和接收时间。
- [ ]  能测量指针队列和大块传值队列的差异。
- [ ]  能统计队列高水位。
- [ ]  能计算消息拷贝带宽。
- [ ]  能测量端到端消息延迟。
- [ ]  能验证 DMA 与 CPU 的 Cache 一致性。

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：定长控制命令队列

实现：

```
按键/通信任务
    -> control_msg_t Queue
    -> 控制任务
```

要求：

- 静态创建队列；
- 支持命令、参数和序号；
- 处理队列满；
- 统计最大队列深度；
- 控制任务超时后进入安全状态。

### 任务二：UART StreamBuffer

实现：

```
UART RX ISR/DMA
    -> StreamBuffer
    -> 协议解析任务
```

要求：

- 支持半帧；
- 支持多帧粘连；
- 支持帧头、长度和 CRC；
- 处理缓冲区满；
- 不允许逐字节创建 Queue 消息。

### 任务三：MessageBuffer 变长帧

实现：

```
生产任务
    -> MessageBuffer
    -> 消费任务
```

要求：

- 帧长度 1~512 字节；
- 目标接收区必须验证大小；
- 测试单生产者和错误的多生产者场景；
- 记录发送失败和接收超时。

### 任务四：固定池 + 指针 Queue

实现：

```
8 个 512 字节固定块
描述符 Queue
消费者处理并归还
```

要求：

- 不使用 `malloc()`；
- 发送失败自动回收；
- 检测重复释放；
- 检测非法指针；
- 验证：

```
空闲块 + 队列块 + 处理块 = 总块数
```

### 任务五：DMA 零拷贝接收

实现：

```
DMA 双缓冲
    -> 指针 Queue
    -> 数据处理任务
```

要求：

- 明确 DMA 和 CPU 所有权；
- 在 Cortex-M7 等平台处理 Cache；
- 模拟队列满；
- 模拟消费者长时间阻塞；
- 统计 DMA 覆盖和缓冲池耗尽。

### 任务六：高优先级控制面与低优先级数据面

实现：

```
控制 Queue：
    高优先级

诊断数据池 + 指针 Queue：
    低优先级
```

要求：

- 诊断流不能阻塞控制命令；
- 控制消息独立统计延迟；
- 诊断池耗尽时丢弃低优先级数据；
- 记录两条数据通道的高水位和丢弃数。

## 16.2 性能测试方法

### 方法一：DWT 测量 Queue 传值

```
uint32_t start = DWT->CYCCNT;

BaseType_t result = xQueueSend(
    g_queue,
    &message,
    0U);

uint32_t cycles =
    DWT->CYCCNT - start;

if (result != pdPASS)
{
    queue_send_failed();
}

record_cycles(cycles);
```

分别测试：

```
4 字节消息
32 字节消息
128 字节消息
512 字节消息
1024 字节消息
```

对比：

```
传值 Queue
指针 Queue
MessageBuffer
```

### 方法二：GPIO 测量端到端延迟

生产者：

```
gpio_set(PRODUCER_PIN);

xQueueSend(
    g_queue,
    &message,
    0U);

gpio_clear(PRODUCER_PIN);
```

消费者：

```
if (xQueueReceive(
        g_queue,
        &message,
        portMAX_DELAY) == pdPASS)
{
    gpio_set(CONSUMER_PIN);

    process_message(&message);

    gpio_clear(CONSUMER_PIN);
}
```

测量：

```
生产标记 -> 消费任务开始标记
```

测试负载：

- 无竞争；
- 同优先级任务运行；
- 高优先级周期任务抢占；
- 队列接近满；
- 多生产者竞争；
- ISR 发送。

### 方法三：高水位和积压监控

```
static void queue_update_high_watermark(
    QueueHandle_t queue)
{
    UBaseType_t waiting =
        uxQueueMessagesWaiting(queue);

    if (waiting > g_queue_high_watermark)
    {
        g_queue_high_watermark = waiting;
    }
}
```

建议记录：

```
发送总数
接收总数
发送失败数
接收超时数
当前深度
最大深度
最大等待时间
丢弃消息类型
内存池剩余块数
```

### 方法四：指针生命周期故障注入

测试：

```
发送后生产者继续写入
消费者提前释放
队列满时忘记释放
消费者异常退出
删除队列但不排空指针
DMA 仍使用时交给 CPU
```

要求系统能够：

- 检测非法状态转换；
- 记录缓冲区地址和序号；
- 阻止重复释放；
- 执行池重建；
- 进入降级或复位流程。

## 16.3 进阶学习方向

1. 阅读 FreeRTOS：
    - `queue.c`；
    - `stream_buffer.c`；
    - `tasks.c`；
    - 队列阻塞列表和调度路径。
2. 研究：
    - 单生产者单消费者环形缓冲区；
    - 多生产者队列；
    - 无锁队列；
    - 内存屏障；
    - Cache 一致性。
3. 学习：
    - 固定块内存池；
    - 分级内存池；
    - slab allocator；
    - DMA 描述符环。
4. 研究消息系统：
    - 零拷贝；
    - 引用计数；
    - 所有权类型；
    - 消息优先级；
    - 背压协议。
5. 进行实时性分析：
    - 队列最坏积压；
    - 消费者 WCET；
    - 端到端延迟；
    - 消息丢失预算；
    - 队列容量证明。
6. 进一步设计工业级消息总线：
    - 统一消息头；
    - 版本兼容；
    - 消息序号；
    - 超时与取消；
    - 通道隔离；
    - 故障快照；
    - 运行时高水位监控。