
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 RPMsg 在 Linux、RemoteProc、VirtIO、Mailbox 和共享内存之间的架构定位。
- 区分 **RPMsg、VirtIO、OpenAMP、RemoteProc、Mailbox、共享内存和 DMA** 的职责边界。
- 理解 Cortex-A 与 Cortex-M/DSP/NPU 之间的控制消息、地址空间和端点模型。
- 理解 RPMsg 的 Name Service、Endpoint、Address、Channel 和消息生命周期。
- 理解 Linux Host 与远端 RTOS/裸机固件的启动、握手、通信和复位路径。

### 掌握

能够：

- 设计 Linux + Cortex-M 的 RPMsg 通信拓扑。
- 使用 RemoteProc 加载、启动和监控远端固件。
- 创建 RPMsg 服务端点，完成请求—响应和异步事件通信。
- 处理 VirtIO vring、共享内存、通知中断和内存屏障。
- 实现超时、流控、消息长度校验、Token 匹配和远端复位恢复。

### 精通

能够深入分析：

- RPMsg 如何基于 VirtIO 实现跨处理器消息传输。
- vring 描述符、available ring、used ring 的所有权转移。
- Linux `rpmsg_core`、`virtio_rpmsg_bus`、`remoteproc` 的调用链。
- Name Service 动态创建设备与端点的机制。
- 非一致性 Cache、IOMMU、物理地址与远端设备地址之间的映射关系。
- 多通道并发、队列拥塞、远端崩溃和消息迟到的系统性处理。

### 能够设计

能够设计：

- 控制面、事件面、数据面分离的异构核通信架构。
- 支持版本协商、能力发现、权限控制和故障恢复的 RPMsg 服务。
- 基于 DMA 描述符和 RPMsg 控制通道的音视频、传感器或工业控制系统。
- Linux 与 RTOS 共存时的实时性隔离和资源配额机制。
- 满足安全启动、功能安全和可观测性要求的生产级 RPMsg 平台。

---

## 2. 前置要求

### 知识要求

- ARMv7-A/ARMv8-A 与 Cortex-M 异常、中断和内存模型。
- MMU、Cache、DMA、IOMMU、物理地址和共享内存属性。
- Linux 驱动模型、设备树、Platform Device 和中断处理。
- VirtIO、环形队列、生产者—消费者模型。
- RTOS 任务、ISR、信号量、消息队列和优先级调度。
- Mailbox、RemoteProc、OpenAMP 和基本 IPC 设计。
- C 语言内存管理、并发、原子操作和错误处理。

### 技能要求

- 能够阅读 Linux `drivers/rpmsg/`、`drivers/remoteproc/` 和 VirtIO 代码。
- 能够阅读 SoC 手册中的共享内存、Mailbox 和中断章节。
- 能够使用 JTAG、串口、ftrace、trace-cmd 和逻辑分析仪定位 IPC 问题。
- 能够分析设备树中的 `memory-region`、`mboxes`、`vring` 和 `rproc` 配置。
- 能够编写 Linux RPMsg 客户端和 Cortex-M RPMsg 服务端。

---

## 3. 技术概述

### 3.1 RPMsg 的定义

RPMsg（Remote Processor Messaging）是运行在异构处理器之间的消息通信框架，通常由以下层次组成：

```
业务客户端/服务
        |
RPMsg Endpoint / Channel
        |
RPMsg Core
        |
VirtIO RPMsg Transport
        |
vring + Shared Memory
        |
Mailbox / IPI / Doorbell
        |
Remote Processor Firmware
```

RPMsg 本身主要解决：

- 远端服务发现；
- 逻辑端点管理；
- 消息收发；
- 地址和通道隔离；
- 与 VirtIO 传输层的衔接。

它**不负责**：

- 远端固件加载本身；
- 大块数据的高吞吐搬运；
- 业务协议定义；
- 自动保证消息幂等性；
- 自动完成故障恢复。

### 3.2 与相关机制的职责边界

|机制|核心职责|是否定义业务消息|
|---|---|---|
|RemoteProc|加载、启动、停止、监控远端处理器|否|
|VirtIO|标准化虚拟设备和 vring 传输|否|
|RPMsg|跨处理器端点和消息通道|部分定义控制消息|
|OpenAMP|异构通信的软件框架实现|否|
|Mailbox|Doorbell、通知和硬件通道|否|
|Shared Memory|承载消息或共享数据|否|
|DMA|大块数据传输|否|
|SCMI|时钟、电源、性能等平台资源协议|是|

核心结论：

> **RPMsg 是通信框架，VirtIO/vring 是传输抽象，Mailbox 是通知机制，RemoteProc 是远端处理器生命周期管理。**

### 3.3 典型启动路径

```
Linux remoteproc 驱动
    |
    +-- 加载 ELF/固件镜像
    +-- 配置 carveout、vring、资源表
    +-- 启动 Cortex-M/DSP
    v
远端固件初始化 VirtIO RPMsg
    |
    +-- 创建 vring
    +-- 发布 Name Service
    +-- 触发 Mailbox 通知
    v
Linux virtio_rpmsg_bus
    |
    +-- 解析服务名
    +-- 创建 RPMsg Channel
    +-- 绑定客户端驱动
```

### 3.4 地址模型

RPMsg 中通常存在三类地址：

- **物理地址**：用于共享内存和 DMA 映射。
- **VirtIO vring 地址**：用于描述符环和缓冲区管理。
- **RPMsg Endpoint 地址**：用于消息逻辑路由，不等同于 CPU 物理地址。

不能将 RPMsg endpoint address 直接当作物理地址使用，也不能未经映射校验就接受远端提交的任意 DMA 地址。

---

## 4. 核心特性横向对比

### 4.1 RPMsg 与其他 IPC 方案

|维度|共享内存自定义协议|RPMsg|RPMsg + OpenAMP|RPMsg + DMA|Mailbox FIFO|
|---|---|---|---|---|---|
|标准化程度|低|中|高|高|中|
|消息复杂度|取决于实现|中|中|高|低|
|大数据能力|高|低～中|低～中|高|低|
|服务发现|通常无|支持|支持|支持|通常无|
|Linux 集成|需自研|成熟|成熟|需配合 DMA|取决于驱动|
|远端固件要求|自定义|RPMsg|OpenAMP|OpenAMP/DMA|自定义|
|实现复杂度|中～高|中|中|高|低～中|
|故障恢复|自行设计|自行设计|自行设计|更复杂|自行设计|
|适用场景|特殊协议|控制和事件|通用异构 IPC|音视频/采样|短控制消息|

### 4.2 通信模式对比

|模式|典型实现|优点|主要风险|
|---|---|---|---|
|同步 RPC|request/response + completion|编程模型简单|超时、死锁、远端迟到响应|
|异步事件|独立 endpoint + worker|不阻塞调用方|事件丢失、队列溢出|
|单向命令|A→M endpoint|延迟低|缺少执行确认|
|描述符通知|RPMsg + DMA descriptor|大数据零拷贝|地址、Cache、生命周期复杂|
|批量消息|多消息一次通知|降低 IRQ 负载|延迟增加、队列管理复杂|

### 4.3 典型性能范围

|路径|典型延迟|
|---|---|
|同核函数调用|10～50 ns|
|本地 Mailbox 通知|0.1～2 μs|
|RPMsg 小消息，缓存一致平台|5～30 μs|
|RPMsg 小消息，非一致性平台|10～80 μs|
|RPMsg + 远端任务调度|20～150 μs|
|DMA 描述符通知|10～100 μs|
|远端硬件服务执行|20 μs～数 ms|

以上是典型 Cortex-A55 + Cortex-M 平台的工程估算，必须在目标 SoC 上测量 P50、P95、P99 和最大值。

---

## 5. 底层原理与功能特性深度解析

### 5.1 VirtIO vring 工作机制

vring 通常由三部分组成：

```
Descriptor Table
    |
Available Ring  ---- 发送端发布待处理描述符
    |
Used Ring       ---- 接收端发布已完成描述符
```

发送流程：

```
1. 从 free descriptor pool 获取描述符
2. 填写 buffer address、length、flags
3. 将 descriptor 索引写入 available ring
4. 发布 available index
5. 执行内存屏障
6. 通过 Mailbox/通知寄存器通知远端
7. 远端消费并写入 used ring
8. 接收完成通知
9. 回收 descriptor
```

所有权原则：

```
FREE -> OWNED_BY_SENDER -> OWNED_BY_REMOTE -> USED -> FREE
```

禁止在远端仍持有描述符时修改或释放其 Buffer。

### 5.2 RPMsg 地址与端点

一个 RPMsg endpoint 至少包含：

```
struct rpmsg_endpoint_desc {
    uint32_t local_addr;
    uint32_t remote_addr;
    uint32_t service_id;
    uint32_t flags;
};
```

端点的作用是：

- 将消息路由到具体服务；
- 隔离不同客户端；
- 支持多个服务复用同一 vring；
- 将异步事件与同步 RPC 分离。

生产代码必须限制：

- endpoint 数量；
- 单端点队列深度；
- 单消息最大长度；
- 服务可访问的命令集合；
- 远端创建动态端点的权限。

### 5.3 Name Service 服务发现

远端通常通过 Name Service 宣布服务：

```
服务名称：com.example.motor_ctrl
远端地址：0x400
标志：创建新通道
```

Linux 收到后通常执行：

```
解析服务名
  -> 检查版本和权限
  -> 创建 rpmsg_channel
  -> 匹配客户端驱动
  -> 创建 endpoint
```

不能仅凭服务名信任远端。工业系统还应校验：

- 固件签名和版本；
- 服务名称白名单；
- 远端处理器身份；
- 最大消息能力；
- 协议版本；
- 是否允许该服务访问当前资源。

### 5.4 Linux 侧客户端框架

以下为概念性 Linux 驱动框架：

```
struct motor_rpc {
    struct rpmsg_device *rpdev;
    struct mutex lock;
    atomic_t next_token;
    struct xarray pending;
    wait_queue_head_t waitq;
};

static int motor_rpmsg_cb(struct rpmsg_device *rpdev,
                          void *data,
                          int len,
                          void *priv,
                          u32 src)
{
    struct motor_rpc *rpc = dev_get_drvdata(&rpdev->dev);
    struct rpc_response *rsp = data;

    if (len < sizeof(*rsp) || rsp->magic != RPC_MAGIC)
        return -EPROTO;

    if (rsp->payload_len > len - sizeof(*rsp))
        return -EMSGSIZE;

    complete_pending_transaction(rpc, rsp->token, rsp, len);
    return 0;
}

static int motor_rpmsg_probe(struct rpmsg_device *rpdev)
{
    struct motor_rpc *rpc;

    rpc = devm_kzalloc(&rpdev->dev, sizeof(*rpc), GFP_KERNEL);
    if (!rpc)
        return -ENOMEM;

    mutex_init(&rpc->lock);
    xa_init_flags(&rpc->pending, XA_FLAGS_ALLOC);
    init_waitqueue_head(&rpc->waitq);
    dev_set_drvdata(&rpdev->dev, rpc);

    return 0;
}

static void motor_rpmsg_remove(struct rpmsg_device *rpdev)
{
    struct motor_rpc *rpc = dev_get_drvdata(&rpdev->dev);

    fail_all_pending(rpc, -ENODEV);
    xa_destroy(&rpc->pending);
}
```

注意：真实 Linux 内核代码应使用内核提供的 `rpmsg_send()`、`rpmsg_trysend()`、`rpmsg_sendto()` 或适合版本的 API，不能直接假设所有平台都支持相同的发送语义。

### 5.5 同步 RPC 设计

```
struct rpc_request {
    __le32 magic;
    __le16 version;
    __le16 header_len;
    __le32 total_len;
    __le32 command;
    __le32 token;
    __le32 flags;
};

struct rpc_waiter {
    struct completion done;
    u32 token;
    int status;
    size_t response_len;
    u8 response[256];
};

int motor_rpc_call(struct motor_rpc *rpc,
                   u32 command,
                   const void *payload,
                   size_t payload_len,
                   void *response,
                   size_t response_capacity,
                   unsigned long timeout)
{
    struct rpc_waiter *waiter;
    struct rpc_request *req;
    u32 token;
    int ret;

    if (!rpc || !payload || !response)
        return -EINVAL;
    if (payload_len > 192)
        return -EMSGSIZE;

    waiter = kzalloc(sizeof(*waiter), GFP_KERNEL);
    if (!waiter)
        return -ENOMEM;

    init_completion(&waiter->done);
    token = alloc_rpc_token(rpc);
    if (!token) {
        kfree(waiter);
        return -EBUSY;
    }
    waiter->token = token;

    ret = register_pending(rpc, waiter);
    if (ret)
        goto out_token;

    req = build_request(command, token, payload, payload_len);
    if (!req) {
        ret = -ENOMEM;
        goto out_pending;
    }

    ret = rpmsg_send(rpc->rpdev->ept, req,
                     sizeof(*req) + payload_len);
    kfree(req);
    if (ret)
        goto out_pending;

    if (!wait_for_completion_timeout(&waiter->done, timeout)) {
        mark_aborted(waiter);
        quarantine_token(rpc, token);
        schedule_remote_recovery(rpc);
        ret = -ETIMEDOUT;
        goto out_pending;
    }

    if (waiter->response_len > response_capacity) {
        ret = -EMSGSIZE;
        goto out_pending;
    }

    memcpy(response, waiter->response, waiter->response_len);
    ret = waiter->status;

out_pending:
    unregister_pending(rpc, token);
out_token:
    if (!is_quarantined(rpc, token))
        free_rpc_token(rpc, token);
    kfree(waiter);
    return ret;
}
```

关键点：

- 登记 pending 必须早于发送。
- 超时后不能立即复用 Token。
- 回调中只根据 Token 查找事务，不应把任意远端消息当作当前响应。
- 调用方必须设置绝对超时，并区分 `-ETIMEDOUT`、`-ENODEV`、`-EPROTO` 和远端业务错误。

### 5.6 远端 RTOS 服务端

```
struct motor_request {
    uint32_t command;
    uint32_t token;
    uint32_t payload_len;
    uint8_t payload[192];
};

static void motor_service_task(void *arg)
{
    struct motor_request req;
    struct motor_response rsp;
    int ret;

    for (;;) {
        if (rpmsg_recv(&req, sizeof(req), RTOS_WAIT_FOREVER) != 0)
            continue;

        if (req.payload_len > sizeof(req.payload)) {
            send_error_response(req.token, -EMSGSIZE);
            continue;
        }

        if (!command_allowed(req.command)) {
            send_error_response(req.token, -EACCES);
            continue;
        }

        memset(&rsp, 0, sizeof(rsp));
        rsp.magic = RPC_MAGIC;
        rsp.version = RPC_VERSION;
        rsp.token = req.token;

        ret = dispatch_motor_command(&req, &rsp);
        rsp.status = ret;
        rsp.total_len = response_length(&rsp);

        if (rpmsg_send(&rsp, rsp.total_len) != 0)
            fault_report(RESPONSE_SEND_FAILED);
    }
}
```

实时任务不应直接承担 RPMsg 解析和复杂内存分配。推荐分层：

```
RPMsg RX ISR/回调
    -> 固定槽位消息池
    -> RPC Server Task
    -> 无锁/有界命令队列
    -> Real-Time Control Task
```

### 5.7 Cache 与共享内存

非一致性平台发送前通常需要：

```
填写消息或 vring 描述符
    -> Clean D-Cache
    -> DMB/DSB
    -> 写 Mailbox/Notify
```

接收时通常需要：

```
读取远端通知
    -> Invalidate D-Cache
    -> DMB
    -> 读取 used ring 和消息
```

但不能机械地在所有平台使用整块 Cache Clean。需要确认：

- 共享内存是否为 Normal Non-cacheable；
- 是否处于硬件一致性域；
- DMA 是否经过 IOMMU；
- Mailbox 寄存器是否为 Device memory；
- cache line 是否发生 false sharing；
- 远端是否使用不同的内存属性。

### 5.8 消息长度、字节序和 ABI

跨处理器 ABI 不应依赖：

- C 结构体默认填充；
- `long`、指针等平台相关类型；
- 编译器 bit-field 布局；
- 主机字节序假设。

推荐使用：

```
struct rpmsg_wire_header {
    uint32_t magic_le;
    uint16_t version_le;
    uint16_t header_len_le;
    uint32_t total_len_le;
    uint32_t command_le;
    uint32_t token_le;
    uint32_t crc32_le;
};
```

读取时使用显式转换，例如 Linux 中的 `le32_to_cpu()`，远端使用固定的 little-endian 编解码函数。

---

## 6. 性能量化分析

### 6.1 测量平台

采用一个典型实验模型：

- Cortex-A55：1.2 GHz；
- Cortex-M33：200 MHz；
- Linux 6.x；
- RTOS 远端固件；
- Shared Memory + VirtIO vring；
- Mailbox Doorbell + IRQ；
- Cache 开启；
- Generic Timer、PMU 和 GPIO 作为测量工具。

### 6.2 端到端延迟模型

```
T_total = T_build
        + T_cache
        + T_vring
        + T_doorbell
        + T_irq
        + T_remote_schedule
        + T_service
        + T_response
```

示例：

```
T_build             = 1.5 μs
T_cache             = 2.5 μs
T_vring             = 1.0 μs
T_doorbell_irq      = 4.0 μs
T_remote_schedule   = 6.0 μs
T_service           = 8.0 μs
T_response          = 3.0 μs
--------------------------------
T_total             = 26.0 μs
```

### 6.3 不同消息长度的典型数据

|消息长度|平均延迟|主要影响|
|---|---|---|
|32 B|15～30 μs|IRQ 和调度占主导|
|128 B|18～35 μs|Cache 和拷贝增加|
|256 B|22～45 μs|接近控制消息实用上限|
|1 KB|35～100 μs|不建议频繁走 RPMsg|
|4 KB|80～250 μs|应考虑共享内存描述符或 DMA|

### 6.4 中断负载

若每条消息触发一次中断，单次 ISR 和延后处理共耗时 3 μs，每秒 40,000 条消息：

```
CPU_Load = 40,000 × 3 μs / 1 s = 12%
```

优化方式：

- 批量消费 vring；
- 合并 Doorbell；
- 事件环使用阈值中断；
- 将高频采样改为 DMA；
- 将状态查询改为周期采样或缓存；
- 控制面和数据面使用不同 vring/通道。

### 6.5 内存开销示例

|项目|典型大小|
|---|---|
|每个 vring|4～64 KB|
|共享消息池|8～256 KB|
|每个 RPMsg endpoint|128～512 B|
|Pending 事务对象|128～512 B/个|
|32 个事务对象|4～16 KB|
|DMA 描述符池|1～64 KB|

一个包含 2 个 vring、128 KB 消息池、32 个事务对象和 32 KB DMA 描述符池的系统，静态通信内存通常约为 **180～300 KB**，实际值取决于 vring 深度、消息缓冲区大小和固件资源表配置。

### 6.6 吞吐量估算

```
Throughput = Payload_Size × Messages_Per_Second
```

例如 256 B 消息、每秒 20,000 条：

```
256 × 20,000 = 5,120,000 B/s ≈ 4.88 MiB/s
```

但实际吞吐量受以下最小值约束：

```
min(
    Linux 构造速度,
    vring 消费速度,
    Mailbox 通知速度,
    远端调度速度,
    远端服务速度,
    共享内存带宽
)
```

**RPMsg 适合控制面，不应以消息拷贝方式承载持续大吞吐数据。**

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否需要跨处理器通信？
├─ 否
│  └─ 使用本地函数、队列或共享线程同步
└─ 是
   |
   消息是否为短控制命令或异步事件？
   ├─ 是
   │  └─ 是否需要标准服务发现和 Linux 集成？
   │      ├─ 是 -> RPMsg
   │      └─ 否 -> Mailbox + 自定义协议
   └─ 否
      |
      是否为大块或持续数据流？
      ├─ 是
      │  └─ DMA Buffer/Ring，RPMsg 只传描述符
      └─ 否
         |
         是否为平台电源、时钟、DVFS 管理？
         ├─ 是
         │  └─ SCMI over Mailbox/RPMsg，按平台架构选择
         └─ 否
            └─ RPMsg + 自定义业务协议
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|Linux 配置 Cortex-M 电机参数|RPMsg RPC|支持服务发现和请求响应|
|M 核上报故障事件|独立 RPMsg Event Endpoint|不阻塞命令通道|
|摄像头帧传输|DMA Buffer + RPMsg 描述符|避免消息拷贝|
|音频 DSP 控制|RPMsg 控制面 + DMA 数据面|低延迟且可扩展|
|平台电源管理|SCMI over Mailbox|标准化资源管理|
|固件启动和停止|RemoteProc|职责明确|
|极简裸机点对点通知|Doorbell + 共享内存|依赖少、实现简单|
|多 VM 通信|VirtIO/RPMsg 虚拟化|支持隔离和资源复用|

---

## 8. 工程最佳实践

### 8.1 架构原则

1. **RemoteProc 管生命周期，RPMsg 管通信，业务协议管语义。**
2. **控制面、事件面、数据面、恢复面分离。**
3. RPMsg 消息应有固定最大长度、版本、命令白名单和 CRC/校验机制。
4. 每个同步请求必须有 Token、超时和明确的所有权状态。
5. 不在 ISR 或 RPMsg 回调中执行不可控时长业务。
6. 不允许 Linux 直接访问远端私有寄存器或任意物理地址。
7. 所有共享内存区域通过设备树、资源表或固件协议明确声明。
8. 远端复位后，旧端点、旧 Token、旧 vring 索引和旧 DMA 描述符全部视为失效。

### 8.2 选型决策矩阵

|需求|RPMsg 小消息|RPMsg + 共享内存|RPMsg + DMA|自定义 Mailbox|
|---|---|---|---|---|
|Linux 集成|高|高|中|低～中|
|服务发现|高|高|高|低|
|大数据吞吐|低|中|高|低|
|低延迟|中|中|中|高|
|通用性|高|高|高|低|
|实现复杂度|中|中|高|低～中|
|故障恢复|中|中|低|需自研|
|适合控制面|高|高|中|高|
|适合数据面|低|中|高|低|

### 8.3 Linux 设备树关注点

典型配置需要明确：

```
reserved-memory {
    rproc_mem: rproc-memory@90000000 {
        reg = <0x0 0x90000000 0x0 0x00100000>;
        no-map;
    };

    vdev0vring0: vring0@90100000 {
        reg = <0x0 0x90100000 0x0 0x00008000>;
        no-map;
    };
};

remoteproc@... {
    memory-region = <&rproc_mem>, <&vdev0vring0>;
    mboxes = <&mailbox 0>;
    status = "okay";
};
```

实际字段依赖具体 SoC binding，不能照搬通用示例。必须核对：

- carveout 是否与 Linux 内存重叠；
- vring 是否满足对齐和大小要求；
- 远端地址是否需要转换；
- IOMMU/SMMU 是否已配置；
- Mailbox 通道是否被其他客户端占用。

### 8.4 可观测性要求

至少记录：

- 远端固件版本和构建 ID；
- RPMsg 服务名和端点地址；
- 消息 Token、命令、长度和状态；
- 发送、接收、完成时间戳；
- vring avail/used 索引；
- 重试、超时、丢包、CRC 错误；
- 远端心跳和复位次数；
- DMA Buffer 地址、序号和生命周期。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：把 RPMsg 当作大数据通道

#### 错误代码

```
for (size_t off = 0; off < frame_size; off += 256)
    rpmsg_send(ept, frame + off, min(frame_size - off, 256));
```

#### 根因

重复消息拷贝、vring 消费和中断通知，导致 CPU 占用和延迟抖动急剧增加。

#### 正确实现

```
struct dma_desc desc = {
    .address = dma_phys_addr(buffer),
    .length = frame_size,
    .sequence = sequence,
    .flags = DMA_DESC_VALID,
};

clean_dcache_range(buffer, frame_size);
clean_dcache_range(&desc, sizeof(desc));
dsb_sy();
rpmsg_send(ept, &desc, sizeof(desc));
```

#### 风险影响

吞吐量不足、FIFO/vring 堵塞、控制消息无法及时发送，最终导致实时任务超时。

### 9.2 错误二：消息回调中执行阻塞业务

#### 错误代码

```
static int rpmsg_cb(...)
{
    motor_reconfigure(); /* 可能耗时数毫秒 */
    wait_for_completion(&remote_done);
    return 0;
}
```

#### 根因

回调可能运行在软中断、工作队列或受限上下文，且阻塞期间会延迟其他消息消费。

#### 正确实现

```
static int rpmsg_cb(...)
{
    if (!queue_event_from_callback(data, len))
        return -ENOSPC;

    schedule_work(&motor_work);
    return 0;
}
```

#### 风险影响

消息堆积、递归通信、死锁、调度延迟和远端发送阻塞。

### 9.3 错误三：忽略远端复位后的旧消息

#### 错误代码

```
if (response.token == pending_token)
    complete(&waiter->done);
```

#### 根因

远端复位后可能重新从 Token 0 开始，旧响应和新会话响应可能出现相同 Token。

#### 正确实现

```
struct session_token {
    uint32_t boot_generation;
    uint32_t token;
};

if (response.boot_generation != client->boot_generation)
    return -ESTALE;

if (!pending_token_valid(client, response.token))
    return -EPROTO;
```

远端每次启动应发布新的 boot generation 或 session ID。

#### 风险影响

旧响应交付给新事务，导致执行器、时钟或参数状态错误。

### 9.4 错误四：未验证远端消息长度

#### 错误代码

```
memcpy(local_buf, data, hdr->total_len);
```

#### 根因

远端可能发送非法长度、整数溢出值或损坏消息。

#### 正确实现

```
if (len < sizeof(struct rpc_header))
    return -EPROTO;

if (hdr->header_len < sizeof(*hdr) ||
    hdr->total_len < hdr->header_len ||
    hdr->total_len > len ||
    hdr->total_len > RPC_MAX_MESSAGE)
    return -EMSGSIZE;

memcpy(local_buf, data, hdr->total_len);
```

#### 风险影响

越界访问、内存破坏、内核崩溃甚至远程代码执行。

### 9.5 错误五：忽略 vring 和共享内存的 Cache 属性

#### 错误代码

```
fill_vring_descriptor(desc, buffer, len);
write_mailbox_kick();
```

#### 根因

远端观察到旧描述符或旧消息内容。

#### 正确实现

```
fill_vring_descriptor(desc, buffer, len);
clean_dcache_range(desc, sizeof(*desc));
clean_dcache_range(buffer, len);
dmb_sy();
write_mailbox_kick();
```

接收端按平台要求执行 invalidate，并在读取 ring 索引前后使用正确屏障。

#### 风险影响

偶发丢包、错误地址、重复消费和难以复现的数据损坏。

### 9.6 错误六：服务名无权限控制

#### 错误代码

```
if (!strcmp(name, "debug_service"))
    create_rpmsg_endpoint(name);
```

#### 根因

仅凭远端字符串创建高权限服务，未验证固件身份、版本和权限。

#### 正确实现

```
if (!firmware_is_authenticated() ||
    !service_in_allowlist(name) ||
    !service_version_supported(version))
    return -EACCES;

return create_restricted_endpoint(name);
```

#### 风险影响

未经授权的寄存器访问、权限绕过、跨安全域攻击和系统控制面失陷。

---

## 10. 多机制组合使用方案

### 10.1 推荐分层架构

```
业务驱动
    |
业务协议：Motor RPC / Audio Control / Sensor Service
    |
RPMsg Endpoint
    |
RPMsg Core / VirtIO
    |
vring + Shared Memory
    |
Mailbox / IPI / Doorbell
    |
RemoteProc 生命周期管理
    |
Cortex-M / DSP 固件
```

### 10.2 控制面与数据面

```
控制面：RPMsg 小消息
    - 配置
    - 模式切换
    - 参数设置
    - 状态查询
    - 错误确认

事件面：独立 RPMsg Endpoint
    - 温度告警
    - 故障事件
    - 远端状态
    - 异步完成通知

数据面：DMA Buffer + Ring/Descriptor
    - 音频帧
    - 传感器采样
    - 图像帧
    - 日志批量数据

恢复面：RemoteProc + 独立心跳/恢复通道
    - 心跳
    - 远端复位
    - 会话代次
    - 状态重建
```

### 10.3 完整事务框架

```
struct rpmsg_transport {
    struct rpmsg_endpoint *cmd_ept;
    struct rpmsg_endpoint *event_ept;
    struct rpmsg_endpoint *recovery_ept;
    struct mutex lock;
    u32 boot_generation;
    struct xarray pending;
    atomic_t next_token;
};

int transport_call(struct rpmsg_transport *t,
                   u32 command,
                   const void *req,
                   size_t req_len,
                   void *rsp,
                   size_t rsp_capacity,
                   unsigned long timeout)
{
    struct rpc_waiter *waiter;
    struct rpc_packet packet;
    u32 token;
    int ret;

    if (!t || !req || !rsp || req_len > RPC_MAX_PAYLOAD)
        return -EINVAL;

    token = alloc_token(t);
    if (!token)
        return -EBUSY;

    waiter = waiter_alloc(t, token, rsp, rsp_capacity);
    if (!waiter) {
        free_token(t, token);
        return -ENOMEM;
    }

    packet = make_packet(t->boot_generation, token,
                         command, req, req_len);

    ret = register_pending(t, waiter);
    if (ret)
        goto out;

    ret = rpmsg_send(t->cmd_ept, &packet, packet.total_len);
    if (ret)
        goto out_pending;

    if (!wait_for_completion_timeout(&waiter->done, timeout)) {
        waiter->state = XFER_ABORTED;
        quarantine_token(t, token);
        schedule_recovery(t);
        ret = -ETIMEDOUT;
        goto out_pending;
    }

    ret = waiter->status;

out_pending:
    unregister_pending(t, token);
out:
    if (waiter->state != XFER_ABORTED)
        free_token(t, token);
    waiter_free(waiter);
    return ret;
}
```

### 10.4 资源获取与回滚

RPMsg 服务涉及远端资源时，必须使用事务式回滚：

```
int remote_device_enable(struct remote_device *dev)
{
    int ret;

    ret = rpmsg_set_power(dev, true);
    if (ret)
        return ret;

    ret = rpmsg_set_clock(dev, true);
    if (ret)
        goto rollback_power;

    ret = rpmsg_configure(dev);
    if (ret)
        goto rollback_clock;

    return 0;

rollback_clock:
    rpmsg_set_clock(dev, false);
rollback_power:
    rpmsg_set_power(dev, false);
    return ret;
}
```

---

## 11. 工业级实际案例分析

### 11.1 案例一：Linux 与 Cortex-M 电机控制 RPC

#### 需求

- Linux 负责参数管理、诊断和人机界面。
- Cortex-M 负责 20 kHz 电流环和 1 kHz 速度环。
- Linux 可以设置目标转速和控制模式。
- Cortex-M 必须上报过流、过温、编码器异常。
- Linux 重启或卡死不能阻塞 Cortex-M 的安全停机路径。

#### 架构

```
Linux
├── Control RPMsg Endpoint
├── Event RPMsg Endpoint
└── Recovery/Heartbeat
        |
Shared vring + Mailbox
        |
Cortex-M
├── RPMsg Server Task
├── Real-Time Control Task
├── Fault ISR
└── Safety Watchdog
```

#### 设计要点

- 控制命令只修改 shadow parameters，由实时任务在控制周期边界提交。
- 过流和过温由 Cortex-M 本地硬件/ISR直接处理，不等待 Linux。
- Linux 只能设置目标值，不能直接关闭安全保护。
- 事件队列满时，故障消息进入独立高优先级通道。
- 每个命令带有效时间、序号和会话代次。

#### 性能预算

```
RPMsg 控制事务：P99 < 100 μs
实时控制周期：50 μs
安全故障响应：由本地 ISR 完成，不依赖 RPMsg
```

结论：RPMsg 适合配置与诊断，**不应进入 20 kHz 控制闭环**。

### 11.2 案例二：音频 DSP 控制与 PCM 数据面

#### 需求

- Cortex-A/Linux 运行 ALSA 或 Android Audio HAL。
- DSP 执行 AEC、EQ、采样率转换和动态增益。
- 参数更新要求小于一个音频 frame 的控制延迟。
- PCM 数据持续流动，不能通过 RPMsg 拷贝。

#### 架构

```
Linux Audio Stack
├── RPMsg Control Endpoint
├── DMA Buffer Pool
├── Descriptor Ring
└── DSP Recovery Manager
        |
        +-- RPMsg/VirtIO Control
        +-- DMA Descriptor Notification
        v
DSP Firmware
├── Command Task
├── Audio Processing Loop
├── DMA Completion ISR
└── Health Monitor
```

48 kHz、128 samples/frame 时：

```
Frame_Time = 128 / 48000 ≈ 2.67 ms
```

RPMsg 控制消息应尽量在 **100 μs 级**完成，PCM 数据则通过 DMA Buffer 传输。

#### 设计要点

- 控制参数通过固定长度消息传递。
- 音频 Buffer 由预分配 DMA 池管理。
- 描述符含物理地址、长度、序号、方向和 CRC。
- DSP 复位后丢弃旧描述符，重新建立 pipeline。
- 通过 sequence number 检查重复、丢失和乱序。

### 11.3 案例三：传感器 Hub 与 Linux 低功耗协同

#### 需求

- Cortex-M 在低功耗状态下持续采集 IMU、温度和加速度数据。
- Linux 唤醒后读取批量数据。
- 传感器事件可触发 AP 唤醒。
- Linux 与 M 核之间需要共享时间戳和采样序号。

#### 架构

```
Cortex-M Sensor Hub
├── Sampling ISR
├── Sensor Ring Buffer
├── Event Detector
└── RPMsg Event Service
        |
Shared Memory + Doorbell/Wakeup IRQ
        |
Linux
├── RPMsg Client
├── Batch Reader
└── Runtime PM
```

#### 设计要点

- 采样数据写入固定大小环形缓冲区，RPMsg 只发送 head、tail、序号和唤醒原因。
- Linux 休眠时不依赖普通同步 RPC 完成唤醒。
- 环形缓冲区必须定义溢出策略：丢旧数据、丢新数据或进入故障状态。
- 远端使用单调递增序号；Linux 通过序号检测丢样本。
- 低功耗恢复后重新协商环索引和时间基准。

---

## 12. 高频问题深度答疑

### 问题一：RPMsg 和 OpenAMP 是什么关系？

RPMsg 是消息通信模型和接口；OpenAMP 是面向异构多处理器的开源框架，通常提供 RemoteProc、RPMsg、VirtIO 等组件。

可以理解为：

```
OpenAMP = 一套实现和集成框架
RPMsg   = 其中的消息通信机制
VirtIO  = RPMsg 常用的传输抽象
```

Linux 不一定使用 OpenAMP 作为 Host 实现，但可以与符合 RPMsg/VirtIO 约定的远端固件通信。

### 问题二：RPMsg 是否保证消息可靠到达？

不应默认认为它提供业务级可靠性。底层通常可以保证描述符被传输和回收，但以下问题仍需业务协议处理：

- 远端复位；
- 服务执行失败；
- 响应超时；
- 消息重复；
- 业务命令不可逆；
- 会话代次变化。

生产协议应自行定义 ACK、序号、幂等性和恢复语义。

### 问题三：为什么要使用多个 RPMsg endpoint？

单端点会使不同类型消息共享队列和锁，容易造成优先级反转。例如大量日志或配置请求可能阻塞故障事件。

推荐至少分离：

- 同步控制 endpoint；
- 异步事件 endpoint；
- 高优先级故障 endpoint；
- 数据描述符 endpoint；
- 恢复/心跳 endpoint。

### 问题四：RPMsg 消息长度为什么不能随意增大？

RPMsg 消息通常受单个共享 Buffer、vring 描述符和底层实现限制。过长消息会：

- 占用多个描述符；
- 增加拷贝和 Cache 操作；
- 延长占用时间；
- 阻塞高优先级消息；
- 引起不同实现之间的兼容性问题。

大消息应采用共享内存或 DMA 描述符。

### 问题五：远端复位后，Linux 应该保留旧 endpoint 吗？

通常不能继续信任旧 endpoint。远端复位可能导致：

- 服务状态丢失；
- 地址重新分配；
- Token 重新开始；
- vring 索引回到初始值；
- DMA Buffer 所有权失效。

应先标记所有 pending 失败，清理旧队列和描述符，等待远端重新发布服务并完成能力协商。

### 问题六：RPMsg 能否进入硬实时控制环？

通常不建议。RPMsg 延迟包含 Linux 调度、Mailbox IRQ、vring 操作、Cache 和远端任务调度，最坏延迟难以由通用 Linux 保证。

合理架构是：

```
Linux/RPMsg：参数、模式、监控、诊断
Cortex-M 本地任务：固定周期控制环
本地硬件/ISR：安全保护和紧急关断
```

### 问题七：如何处理 RPMsg 发送队列满？

不能无限重试。应根据业务类型区分：

|消息类型|处理方式|
|---|---|
|状态快照|合并，只保留最新值|
|故障事件|独立队列，不能静默丢弃|
|可重试配置|有界重试并退避|
|一次性动作|返回忙或失败，禁止盲目重放|
|数据描述符|进行流控或暂停生产者|

---

## 13. 课程核心总结

1. **RPMsg 是异构处理器消息框架，不是大数据传输协议。**
2. **RemoteProc 管理远端生命周期，VirtIO/vring 管理传输，Mailbox 负责通知。**
3. RPMsg endpoint 用于服务隔离和消息路由。
4. Name Service 只解决发现，不等于权限认证。
5. 同步 RPC 必须具备 Token、超时、响应校验和会话代次。
6. 远端复位后，旧 endpoint、Token、vring 和 DMA 所有权全部需要重新验证。
7. 共享内存必须明确 Cache 属性、内存屏障、物理地址和所有权转移。
8. 控制面和数据面必须分离；大数据使用 DMA 或共享环。
9. ISR/回调只做快速搬运和唤醒，不执行阻塞业务。
10. RPMsg 不应进入硬实时控制闭环，实时闭环应留在 Cortex-M/DSP 本地。
11. 工业级 RPMsg 的核心指标是**协议边界、可观测性、故障隔离、最坏延迟和恢复能力**。

### 性能排序

```
本地函数/寄存器
    <
Mailbox Doorbell
    <
共享内存直接访问
    <
RPMsg 小消息
    <
RPMsg + 远端任务调度
    <
RPMsg + 业务服务执行
    <
DMA/硬件数据处理完成
```

### 通用选型结论

- 短控制消息：**RPMsg**。
- 服务发现和 Linux 集成：**RPMsg + VirtIO/OpenAMP**。
- 大块数据：**DMA Buffer + RPMsg 描述符**。
- 平台资源管理：**SCMI over Mailbox 或平台规定的标准传输**。
- 远端固件生命周期：**RemoteProc**。
- 硬实时闭环：**Cortex-M/DSP 本地任务和硬件机制**。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|首选方案|
|---|---|
|Linux 配置远端 MCU|RPMsg RPC|
|远端异步告警|独立 RPMsg Event Endpoint|
|远端启动/停止|RemoteProc|
|电源/时钟/DVFS|SCMI over Mailbox/平台传输|
|音频 PCM|DMA Buffer + RPMsg Descriptor|
|摄像头帧|DMA/IOMMU + Descriptor Ring|
|低功耗传感器批量数据|Shared Ring + RPMsg 唤醒通知|
|硬实时控制环|远端本地 RTOS/裸机，不依赖 RPMsg|

### 14.2 故障处理表

|故障|首要动作|是否可直接重试|
|---|---|---|
|发送队列满|有界等待或返回 `-EBUSY`|视命令幂等性|
|响应超时|隔离 Token，检查远端|否|
|服务未发现|检查远端启动和资源表|否|
|CRC/长度错误|丢弃、计数、上报|通常否|
|Endpoint 消失|失败所有 pending|重新握手后才可|
|远端复位|清理 vring/Token/DMA 状态|需重新协商|
|DMA 地址非法|拒绝并触发安全告警|否|

### 14.3 经验参数

|项目|典型范围|
|---|---|
|RPMsg 控制消息|32～256 B|
|单端点队列深度|8～64 条|
|小消息延迟|5～30 μs|
|远端调度后延迟|20～150 μs|
|同步 RPC 超时|100 μs～100 ms|
|DMA 描述符大小|16～64 B|
|控制面 vring|4～32 KB|
|数据面 Buffer 池|64 KB～数 MB|

---

## 15. 学习效果自检

完成本课后，应能够：

- 画出 RemoteProc、VirtIO、RPMsg、vring、Mailbox 和远端服务的完整路径。
- 说明 RPMsg 与 OpenAMP、Mailbox、共享内存和 DMA 的职责边界。
- 解释 Name Service 如何发现远端服务。
- 说明 endpoint address、物理地址和 DMA 地址的区别。
- 设计控制、事件、数据和恢复四类通道。
- 编写带长度、版本、Token 和 CRC 校验的消息头。
- 设计 pending transaction 表和超时后的 Token 隔离机制。
- 解释 vring descriptor 的所有权转移过程。
- 处理非一致性平台的 Cache Clean/Invalidate 和内存屏障。
- 设计远端复位后的服务重发现和状态重建流程。
- 计算 RPMsg 延迟、中断负载和消息吞吐量。
- 判断某个数据流是否应该迁移到 DMA。
- 解释为什么 RPMsg 不适合硬实时控制闭环。
- 设计 Linux + Cortex-M 的生产级 RPMsg 系统。

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：构建最小 RPMsg 点对点通信

要求：

- Linux 加载远端固件；
- 完成资源表和 vring 配置；
- 远端发布一个 Name Service；
- Linux 创建客户端 endpoint；
- 实现 Echo 请求和响应。

验收指标：

- 连续发送 10,000 条消息无丢失；
- 能记录 P50/P95/P99 延迟；
- 服务移除后所有 pending 请求正确失败。

#### 任务二：实现同步 RPC 框架

要求：

- Token 分配；
- pending 表；
- 响应长度和 CRC 校验；
- 有界超时；
- 幂等命令重试；
- 非幂等命令禁止盲目重放。

#### 任务三：实现独立事件 endpoint

注入以下故障：

- 事件突发；
- 事件队列满；
- Linux 线程暂停；
- 重复事件；
- 事件序号跳变。

要求定义丢弃、合并、保留和故障升级策略。

#### 任务四：加入 DMA 数据面

要求：

- 预分配 DMA Buffer Pool；
- 实现描述符环；
- 校验地址、长度、方向和权限；
- 处理 Cache Clean/Invalidate；
- 防止重复释放和远端继续访问已回收 Buffer。

#### 任务五：实现远端复位恢复

注入：

- Cortex-M 看门狗复位；
- Mailbox 中断丢失；
- vring 索引损坏；
- 服务名重复或版本不兼容；
- 迟到响应；
- DMA 描述符未完成。

验收标准：

- Linux 不永久阻塞；
- 旧消息不污染新会话；
- 所有 DMA Buffer 可回收或隔离；
- 能重新完成服务发现和能力协商；
- 能恢复到安全的最小功能状态。

### 16.2 性能测试方法

分别测量：

```
1. 消息构造时间
2. vring 描述符提交时间
3. Cache 操作时间
4. Doorbell 到远端 IRQ 的时间
5. 远端 vring 消费时间
6. 远端任务调度时间
7. 业务服务执行时间
8. 响应提交和返回通知时间
9. Linux 回调到事务完成时间
10. 端到端总延迟
```

#### 延迟测量框架

Linux 侧可使用 Generic Timer、`ktime_get_ns()`、ftrace 或 tracepoint；Cortex-M 侧使用 DWT CYCCNT、通用定时器或 GPIO 翻转。为了区分各阶段延迟，建议在共享消息头中加入时间戳字段：

```
struct rpmsg_trace_stamp {
    uint64_t host_submit;
    uint64_t remote_irq;
    uint64_t remote_dequeue;
    uint64_t service_begin;
    uint64_t service_end;
    uint64_t remote_submit;
    uint64_t host_complete;
};
```

测试时必须记录：

- **P50、P95、P99、最大值**，不能只记录平均值；
- CPU 频率、调度策略和中断负载；
- Cache 属性和 IOMMU 配置；
- 消息长度、vring 深度和 endpoint 数量；
- 远端任务优先级及是否发生抢占；
- 单向通知、同步 RPC 和 DMA 描述符通知的区别。

#### 推荐测试矩阵

|变量|测试档位|
|---|---|
|消息长度|32 B、128 B、256 B、1 KB、4 KB|
|vring 深度|8、16、32、64|
|通信模式|单条、批量、突发|
|通知方式|每条 IRQ、批量 IRQ、轮询|
|内存属性|Cacheable、一致性、Non-cacheable|
|并发度|1、2、4、8 个发送者|
|远端负载|空闲、50%、90% CPU 利用率|
|错误场景|丢 IRQ、队列满、远端复位、迟到响应|

#### 吞吐量测试

吞吐量可按以下公式计算：

```
Throughput = 有效 Payload 字节数 / 测试持续时间
```

例如，256 B 有效载荷，在 10 秒内成功完成 200,000 条消息：

```
Throughput = 256 × 200,000 / 10
           = 5,120,000 B/s
           ≈ 4.88 MiB/s
```

应同时采集：

- 消息发送数和完成数；
- vring available/used 索引变化；
- 队列峰值深度；
- 丢弃数和重试数；
- Mailbox IRQ 次数；
- Linux 与 Cortex-M CPU 占用率；
- Cache 维护耗时；
- 远端服务处理时间。

#### 最坏情况验证

RPMsg 的工程验收不能只在空闲系统下进行。至少应进行以下压力组合：

```
Linux 高负载
+ 远端高优先级控制任务持续运行
+ 事件突发
+ DMA 持续传输
+ 多个同步 RPC 并发
+ 人为注入一次远端延迟或丢中断
```

验收条件建议包括：

- 控制 RPC 的 **P99 延迟不超过预算**；
- 队列满时不会无限阻塞；
- 远端实时任务的周期抖动满足指标；
- 远端复位后所有 pending 请求在规定时间内失败；
- 旧会话消息不会进入新会话；
- DMA Buffer 不发生重复释放或越权访问；
- 故障恢复过程不会触发安全执行器的误动作。

#### Linux 侧示例：使用 tracepoint 统计延迟

```
struct rpmsg_latency_stat {
    u64 count;
    u64 total_ns;
    u64 max_ns;
    u64 p99_ns;
};

static void rpmsg_record_latency(struct rpmsg_latency_stat *stat,
                                 u64 start_ns,
                                 u64 end_ns)
{
    u64 delta;

    if (stat == NULL || end_ns < start_ns)
        return;

    delta = end_ns - start_ns;
    stat->count++;
    stat->total_ns += delta;

    if (delta > stat->max_ns)
        stat->max_ns = delta;

    /* 生产实现应将样本写入有界直方图，计算真实 P99。 */
}
```

不能用“最大值乘以某个系数”近似 P99。生产系统应使用有界直方图、分桶统计或离线 trace 分析，并避免在实时路径中动态分配内存。

---

### 16.3 进阶学习方向

#### Linux 内核方向

- 深入阅读 `drivers/rpmsg/`、`drivers/remoteproc/` 和 VirtIO vring 实现；
- 分析 `rpmsg_send()`、`rpmsg_trysend()` 的队列满处理和上下文限制；
- 研究 remoteproc 资源表、carveout、vring 和状态机；
- 掌握 threaded IRQ、workqueue、completion、wait queue 和 RCU 的适用边界；
- 结合 ftrace、trace-cmd、perf、PMU 和 lockdep 定位调度抖动、锁竞争和死锁；
- 研究 IOMMU/SMMU、DMA-BUF、cache coherency 和内存屏障对 RPMsg 数据路径的影响。

#### 远端固件与 RTOS 方向

- 实现符合 VirtIO/RPMsg 约定的最小远端固件；
- 深入掌握 Cortex-M NVIC、PendSV、任务优先级和 ISR-Task 通信；
- 建立固定内存池、无锁 SPSC 队列和有界消息队列；
- 设计远端心跳、看门狗、故障隔离和安全降级状态机；
- 研究远端固件升级、回滚、版本兼容和启动自检；
- 对远端命令处理实行命令白名单、权限分级和资源配额。

#### 通信协议与数据面方向

- 学习 OpenAMP、libmetal、VirtIO 和 RPMsg endpoint 管理；
- 设计 RPMsg 控制面与 DMA 数据面的零拷贝架构；
- 研究固定槽位环、变长消息环和多生产者队列的正确性证明；
- 引入序号、CRC、会话代次、ACK、幂等性和有界重试；
- 研究音视频、传感器和工业采样场景中的时间戳同步与数据完整性；
- 在使用 IOMMU 的平台上完成 DMA 地址授权和生命周期验证。

#### 安全与功能安全方向

- 验证远端固件签名、版本和服务白名单；
- 隔离不同安全域、虚拟机和租户的 endpoint、vring 与 DMA Buffer；
- 防止远端提交任意物理地址、越界长度和伪造服务名；
- 为故障事件建立独立高优先级路径，避免普通数据流造成阻塞；
- 对丢包、重复、乱序、超时、远端复位和 CRC 错误进行故障注入；
- 根据 ISO 26262、IEC 61508 等目标标准建立通信监控器和安全状态转换。

#### 系统架构方向

- Linux + Cortex-M/DSP/NPU 的异构计算平台；
- SCMI over Mailbox/RPMsg 的资源管理架构；
- 虚拟化环境中的 VirtIO、虚拟 RPMsg 和多 VM 隔离；
- 低功耗传感器 Hub 与 AP 的唤醒、批量采样和时间基准同步；
- 远端处理器热升级、无损重连和 DMA Buffer 安全回收；
- 控制面、事件面、数据面、恢复面的统一可观测性设计。

---

### 16.4 最终工程检查清单

在评审一套生产级 RPMsg 系统时，至少检查以下项目：

```
协议版本和能力协商
服务名白名单与固件认证
RemoteProc 生命周期
资源表与 carveout 配置
vring 地址、大小和对齐
Mailbox/通知寄存器语义
中断触发方式与清除顺序
Cache 属性与内存屏障
Endpoint 地址和权限隔离
消息长度、字节序和 CRC
Token、序号和会话代次
pending 事务生命周期
超时、迟到响应和重试策略
队列满时的流控策略
控制面与数据面分离
DMA 地址、长度和所有权
实时任务优先级与抖动预算
远端复位和状态重建
故障注入与恢复时间
日志、trace 和性能统计
```

最终应能够回答以下架构问题：

1. 这个消息为什么必须使用 RPMsg，而不是本地 Mailbox 或共享内存接口？
2. 消息是否属于控制面，是否可以迁移到 DMA 数据面？
3. 远端处理器复位时，哪些状态必须失效，哪些硬件状态需要重新读取？
4. 如何证明旧消息不会污染新会话？
5. 如何证明队列满、IRQ 丢失和远端卡死时系统不会永久阻塞？
6. 最坏情况下，Linux 调度抖动是否会影响 Cortex-M 的实时控制环？
7. 远端提交的地址和服务请求是否经过完整的权限验证？
8. 故障发生后，系统能否在规定时间内回到安全状态？

## 本课完

**RPMsg 的正确定位是：以 VirtIO/vring 为传输基础、以 Mailbox 为通知手段、以 endpoint 为逻辑隔离、以 RemoteProc 管理生命周期的异构处理器消息框架。**

在工业系统中，真正可交付的 RPMsg 方案必须同时满足：

- **协议可兼容**；
- **消息可验证**；
- **并发可控制**；
- **延迟可量化**；
- **数据面可扩展**；
- **远端故障可隔离**；
- **复位后可恢复**；
- **安全边界可证明**。