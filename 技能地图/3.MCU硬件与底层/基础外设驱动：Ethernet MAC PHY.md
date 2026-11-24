
## 1. 学习目标

### 理解

- 理解 Ethernet、MAC、PHY、RMII/RGMII、MDIO/MDC、DMA 描述符之间的分层关系。
- 理解以太网帧从 PHY 到 MAC、DMA、内存、协议栈的完整数据路径。
- 理解自动协商、链路状态、双工模式、速率切换和时钟来源。

### 掌握

- 掌握 MAC、PHY 初始化顺序和复位时序。
- 掌握 RX/TX DMA 描述符环、缓存一致性和零拷贝收发。
- 掌握 MDIO 读写、PHY ID 检测、链路状态读取。
- 掌握中断、轮询、NAPI 类批处理机制及其适用场景。

### 精通

- 能定位丢包、帧错误、DMA 卡死、链路抖动、优先级反转和缓存污染问题。
- 能根据实时性、吞吐量、内存容量和功耗要求进行 MAC/PHY 方案选型。
- 能设计可观测、可恢复、可测试的工业级 Ethernet 驱动。

### 能够设计

- 能设计带链路管理、DMA、缓存维护、错误恢复和统计监控的完整 Ethernet 驱动框架。
- 能为 FreeRTOS、裸机或嵌入式 Linux 网络栈适配底层 Ethernet HAL。
- 能设计满足工业控制、网关、TSN 或高吞吐数据采集要求的网络接口。

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、位操作、内存屏障和 `volatile`。
- MCU 总线、时钟树、中断控制器、DMA 和 Cache 基础。
- TCP/IP 分层模型、ARP、IP、UDP、TCP、ICMP。
- RTOS 任务、队列、信号量、事件组和中断上下文约束。
- 基本数字电路：时钟、复位、电平、信号完整性。

### 技能要求

- 能阅读 MCU Ethernet、DMA 和 PHY 数据手册。
- 能使用示波器或逻辑分析仪观察 `REF_CLK`、`TX_EN`、`RX_DV` 等信号。
- 能使用 Wireshark、`ethtool`、`tcpdump`、`iperf3`。
- 能独立编译、下载和调试裸机或 RTOS 工程。

## 3. 技术概述

Ethernet 数据路径通常为：

```
RJ45/Magnetics
      |
     PHY
      |  RMII/RGMII/SGMII
      v
    MAC
      |
     DMA
      |
    SRAM/DDR
      |
   网络协议栈
```

### MAC 的职责

MAC 位于数据链路层，主要负责：

- Ethernet 帧封装和解析。
- 源地址、目的地址和帧长度处理。
- CRC 生成与校验。
- 前导码、帧间隙和最小帧长度处理。
- DMA 描述符管理。
- 单播、组播、广播过滤。
- 流控、校验和卸载、时间戳等硬件功能。

### PHY 的职责

PHY 完成物理层和部分 PCS 功能：

- 10/100/1000 Mbps 物理信号收发。
- MLT-3、4B/5B、8B/10B 等编码。
- 自动协商。
- 双工模式检测。
- 模拟前端、均衡和回波消除。
- 通过 MDIO 管理寄存器。

### 常见接口

|接口|典型速率|引脚数量|适用场景|关键风险|
|---|---|---|---|---|
|MII|10/100 Mbps|较多|老旧 MCU、低成本设计|引脚占用大|
|RMII|10/100 Mbps|较少|Cortex-M、工业控制|50 MHz 时钟方向配置复杂|
|GMII|1000 Mbps|很多|高速 MAC/PHY|PCB 布线复杂|
|RGMII|1000 Mbps|较少|千兆 MCU/MPU|DDR 时序和延迟校准|
|SGMII|1 Gbps|差分对|SoC、交换芯片|SerDes 配置复杂|
|MDI/MDIX|物理双绞线|4 对线|PHY 到磁性器件|变压器和阻抗要求高|

## 4. 核心特性横向对比

|维度|轮询 DMA|中断 DMA|中断 + 批处理|零拷贝|
|---|---|---|---|---|
|CPU 占用|高|中|低到中|最低|
|平均延迟|取决于轮询周期|低|中|低|
|峰值吞吐|高|高|很高|很高|
|实现复杂度|低|中|高|很高|
|Cache 管理|需要|需要|需要|更严格|
|小包性能|差|较好|好|好|
|适合场景|早期 bring-up|普通控制器|网关、数据采集|高吞吐、DDR 系统|
|典型问题|忙等|中断风暴|批处理延迟|缓冲区生命周期错误|

## 5. 底层原理与功能特性深度解析

### 5.1 MAC 与 PHY 初始化顺序

正确顺序通常是：

```
1. 使能 MAC/PHY 相关时钟
2. 配置 GPIO 复用和电气属性
3. 释放 PHY 复位
4. 等待 PHY 上电稳定
5. 通过 MDIO 读取 PHY ID
6. 配置 PHY 模式并启动自动协商
7. 配置 MAC 工作模式
8. 初始化 DMA 描述符和缓冲区
9. 清除 pending 状态
10. 使能 DMA 和 MAC
11. 等待 Link Up
```

MAC 不应在 PHY 尚未确定速率和双工模式时直接发送数据。典型配置关系为：

```
PHY 协商结果 -> MAC speed/duplex 配置 -> MAC enable
```

### 5.2 MDIO 管理接口

MDIO 使用 MDC 时钟和双向 MDIO 数据线。Clause 22 基本帧格式为：

```
Preamble | Start | OP | PHY Address | REG Address | Turnaround | Data
```

生产级 MDIO 访问必须包含：

- 总线忙超时。
- 读写错误检查。
- PHY 地址扫描或设备树配置。
- PHY ID 校验。
- 访问互斥锁。
- 复位后的延时。
- 读回验证。

示例 HAL：

```
#include <stdint.h>
#include <stdbool.h>

#define MDIO_TIMEOUT_US 1000U

typedef enum {
    ETH_OK = 0,
    ETH_E_TIMEOUT = -1,
    ETH_E_IO = -2,
    ETH_E_PARAM = -3,
} eth_status_t;

typedef struct {
    volatile uint32_t *mac_mdio_reg;
    void (*delay_us)(uint32_t us);
    uint32_t (*time_us)(void);
} mdio_bus_t;

static eth_status_t mdio_wait_idle(const mdio_bus_t *bus)
{
    uint32_t start;

    if (bus == NULL || bus->mac_mdio_reg == NULL) {
        return ETH_E_PARAM;
    }

    start = bus->time_us();
    while ((*bus->mac_mdio_reg & (1UL << 0)) != 0U) {
        if ((bus->time_us() - start) >= MDIO_TIMEOUT_US) {
            return ETH_E_TIMEOUT;
        }
    }

    return ETH_OK;
}

eth_status_t phy_read(const mdio_bus_t *bus,
                      uint8_t phy_addr,
                      uint8_t reg_addr,
                      uint16_t *value)
{
    uint32_t command;

    if (value == NULL || phy_addr >= 32U || reg_addr >= 32U) {
        return ETH_E_PARAM;
    }

    if (mdio_wait_idle(bus) != ETH_OK) {
        return ETH_E_TIMEOUT;
    }

    command = /* SoC-specific read command */
        ((uint32_t)phy_addr << 21) |
        ((uint32_t)reg_addr << 16) |
        (1UL << 0);

    *bus->mac_mdio_reg = command;

    if (mdio_wait_idle(bus) != ETH_OK) {
        return ETH_E_TIMEOUT;
    }

    *value = (uint16_t)((*bus->mac_mdio_reg >> 16) & 0xFFFFU);
    return ETH_OK;
}
```

实际项目中，寄存器的读写位域必须以具体 MCU Reference Manual 为准，不能直接套用上述位位置。

### 5.3 PHY 自动协商

PHY 通常通过以下信息决定链路能力：

- 10/100/1000 Mbps 能力。
- 半双工或全双工。
- Pause 流控能力。
- 主从模式。
- EEE 能力。

自动协商失败时，常见现象是：

- `Link Up` 不稳定。
- 速率显示为 10 Mbps。
- 双工模式错误。
- 大包丢失。
- TCP 吞吐低但 Ping 正常。

链路状态处理应区分：

```
PHY 检测到 Link Down
        |
        v
停止发送路径，避免继续提交 TX
        |
        v
清理/复位 MAC DMA
        |
        v
读取 PHY speed/duplex
        |
        v
重新配置 MAC
        |
        v
Link Up 后恢复协议栈发送
```

### 5.4 DMA 描述符环

典型 RX 描述符：

```
typedef struct {
    volatile uint32_t status;
    volatile uint32_t control;
    volatile uint32_t buf_addr;
    volatile uint32_t next;
} eth_rx_desc_t;

typedef struct {
    volatile uint32_t status;
    volatile uint32_t control;
    volatile uint32_t buf_addr;
    volatile uint32_t next;
} eth_tx_desc_t;
```

RX 描述符状态通常包含：

```
OWN = 1：DMA 拥有描述符
OWN = 0：CPU 拥有描述符
FS  ：First Segment
LS  ：Last Segment
ES  ：Error Summary
FL  ：Frame Length
```

初始化 RX 环：

```
#define RX_DESC_COUNT 16U
#define RX_BUF_SIZE   1536U

static eth_rx_desc_t rx_desc[RX_DESC_COUNT]
    __attribute__((aligned(32)));

static uint8_t rx_buf[RX_DESC_COUNT][RX_BUF_SIZE]
    __attribute__((aligned(32)));

static void rx_ring_init(void)
{
    for (uint32_t i = 0; i < RX_DESC_COUNT; i++) {
        uint32_t next = (i + 1U) % RX_DESC_COUNT;

        rx_desc[i].buf_addr = (uint32_t)&rx_buf[i][0];
        rx_desc[i].next = (uint32_t)&rx_desc[next];
        rx_desc[i].control = RX_BUF_SIZE;
        rx_desc[i].status = DESC_OWN_BY_DMA;
    }

    /*
     * 对带 D-Cache 的 Cortex-M7/A 系列处理器：
     * 1. 描述符写回内存
     * 2. 对 RX buffer 做 cache invalidate
     * 3. 执行 DMB/DSB
     */
    cache_clean(&rx_desc[0], sizeof(rx_desc));
    __DMB();
}
```

### 5.5 Cache 一致性

DMA 和 CPU 访问同一内存时，必须处理以下问题：

```
CPU 写 Cache
      |
      | 未回写 SRAM
      v
DMA 读取旧数据
```

或者：

```
DMA 写 SRAM
      |
      | CPU Cache 中仍有旧副本
      v
CPU 读取旧数据
```

推荐策略：

|区域|推荐方式|
|---|---|
|DMA 描述符|Non-cacheable，或显式 Clean/Invalidate|
|RX 缓冲区|DMA 写前 Invalidate，CPU 读前再次确认|
|TX 缓冲区|DMA 发送前 Clean|
|高吞吐系统|使用 MPU 配置专用 Non-cacheable 区域|
|多核系统|结合 Cache coherency 和内存屏障|

示例：

```
static void tx_submit(eth_tx_desc_t *desc,
                      const void *buffer,
                      uint32_t length)
{
    if (desc == NULL || buffer == NULL || length == 0U ||
        length > RX_BUF_SIZE) {
        return;
    }

    desc->buf_addr = (uint32_t)buffer;
    desc->control = length | TX_FIRST_SEGMENT | TX_LAST_SEGMENT;

    cache_clean(buffer, length);
    cache_clean(desc, sizeof(*desc));

    /*
     * 确保 descriptor 和 buffer 的写操作
     * 在 DMA 获得 OWN 权限前已经对外可见。
     */
    __DMB();
    desc->status = DESC_OWN_BY_DMA;
    cache_clean(desc, sizeof(*desc));
}
```

### 5.6 RX 处理

中断服务程序中不应执行完整协议栈解析。推荐：

```
ISR：
  清除 DMA 中断
  记录事件
  唤醒 RX task

RX task：
  批量回收描述符
  做 Cache invalidate
  检查帧错误
  将 packet buffer 交给协议栈
  重新挂回 RX descriptor
```

伪代码：

```
static uint32_t rx_poll(uint32_t budget)
{
    uint32_t processed = 0U;

    while (processed < budget) {
        eth_rx_desc_t *desc = &rx_desc[rx_consumer];

        if ((desc->status & DESC_OWN_BY_DMA) != 0U) {
            break;
        }

        cache_invalidate(rx_buf[rx_consumer], RX_BUF_SIZE);

        if ((desc->status & DESC_ERROR) == 0U) {
            uint32_t length = desc->status & DESC_FRAME_LENGTH_MASK;
            netif_receive(rx_buf[rx_consumer], length);
        } else {
            eth_stats.rx_errors++;
        }

        desc->status = DESC_OWN_BY_DMA;
        cache_clean(desc, sizeof(*desc));

        rx_consumer = (rx_consumer + 1U) % RX_DESC_COUNT;
        processed++;
    }

    return processed;
}
```

## 6. 性能量化分析

以下数据为工程参考值，测试平台假设为：

```
MCU：Cortex-M7，600 MHz
Ethernet：1000BASE-T
内存：片上 SRAM，D-Cache 32 KB
协议栈：FreeRTOS + lwIP
编译器：GCC -O2
测试工具：iperf3、Wireshark、DWT cycle counter
```

### 6.1 线速计算

Ethernet 标准帧最大有效载荷为 1500 字节，线速还包含：

- 7 字节 Preamble。
- 1 字节 SFD。
- 14 字节 Ethernet Header。
- 4 字节 FCS。
- 12 字节 Inter Frame Gap。

单帧线上总长度：

```
7 + 1 + 14 + 1500 + 4 + 12 = 1538 bytes
```

100 Mbps 下，理论最大满载帧率约为：

```
100,000,000 / (1538 × 8) ≈ 8127 frames/s
```

1000 Mbps 下约为：

```
1,000,000,000 / (1538 × 8) ≈ 81,274 frames/s
```

### 6.2 参考测试结果

|场景|单包大小|CPU 占用|RX 单包处理时间|吞吐|
|---|---|---|---|---|
|中断逐包|64 B|38%|1.9 us|48 Mbps|
|中断逐包|1500 B|22%|3.7 us|918 Mbps|
|批处理 8 包|1500 B|14%|2.3 us|944 Mbps|
|零拷贝 + 批处理|1500 B|9%|1.5 us|952 Mbps|
|Non-cacheable Buffer|1500 B|17%|2.8 us|927 Mbps|

这些数据依赖总线、Cache、驱动实现和协议栈配置，应通过目标平台实测确认。

### 6.3 内存开销

假设：

```
RX 描述符：16 个 × 16 字节 = 256 字节
TX 描述符：16 个 × 16 字节 = 256 字节
RX buffer：16 × 1536 = 24 KB
TX buffer：16 × 1536 = 24 KB
```

仅 DMA 缓冲区约为：

```
24 KB + 24 KB + 512 B ≈ 48.5 KB
```

增加 buffer 数量可提升突发吸收能力，但会增加 SRAM 压力和 Cache 维护成本。

### 6.4 主要瓶颈

- 小包场景下中断频率过高。
- RX buffer 不足导致 overrun。
- Cache 维护占用 CPU。
- DMA 描述符未按 Cache line 对齐。
- 协议栈拷贝次数过多。
- PHY 协商错误导致实际速率降级。
- 内存总线带宽不足。

### 6.5 优化手段

|优化手段|典型收益|
|---|---|
|中断合并/批处理|CPU 占用下降 20%～50%|
|增加 RX ring 深度|减少突发丢包|
|零拷贝|减少一次或多次内存复制|
|Cache 对齐|降低一致性异常|
|硬件校验和卸载|降低协议栈 CPU 开销|
|绑定高优先级 RX 任务|降低接收延迟|
|增加 DMA burst|提高总线利用率|

## 7. 应用场景选型指南

### 决策流程图

```
是否需要 1000 Mbps？
|
+-- 否 --> MCU 是否只有 RMII？
|          |
|          +-- 是 --> RMII + 10/100 PHY
|          |
|          +-- 否 --> 根据引脚和 EMI 选择 RMII/MII
|
+-- 是 --> 芯片是否支持千兆 MAC？
           |
           +-- 否 --> 外置 Ethernet Controller 或升级 MCU/MPU
           |
           +-- 是 --> RGMII/SGMII
                      |
                      +-- 高实时性 --> DMA + 批处理 + 硬件时间戳
                      |
                      +-- 普通 TCP/IP --> 标准 RX/TX ring
```

### 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|工业传感器|低成本、10/100 Mbps|RMII + 轻量 PHY|引脚少、软件复杂度低|
|PLC 网关|多连接、稳定链路|RMII/RGMII + DMA ring|支持突发流量和链路恢复|
|视频采集|高吞吐|千兆 MAC + RGMII/SGMII|带宽和 DMA 性能优先|
|EtherCAT 从站|周期低延迟|专用 EtherCAT 控制器或硬件时间戳|普通 TCP/IP MAC 不等价|
|TSN|确定性时延|支持 Qbv、802.1AS 的 MAC/交换芯片|需要硬件调度和时间同步|
|低功耗设备|休眠唤醒|PHY 低功耗、WoL|减少待机功耗|

## 8. 工程最佳实践

### 设计原则

1. **MAC 和 PHY 解耦**：使用 `mac_ops`、`phy_ops` 接口。
2. **DMA 所有权明确**：任何时刻只能由 CPU 或 DMA 一方拥有描述符。
3. **链路状态独立管理**：Link Up/Down 不应散落在发送和接收代码中。
4. **错误可观测**：维护 CRC、alignment、overrun、missed、underrun、bus error 统计。
5. **所有硬件访问有超时**：禁止无限等待。
6. **ISR 最小化**：只清状态、记录事件、唤醒任务。
7. **资源可恢复**：DMA 卡死后支持停止、清状态、重建 ring、重新启动。

### 选型决策矩阵

|约束|低|中|高|
|---|---|---|---|
|吞吐量|10/100 Mbps|100 Mbps|1 Gbps|
|延迟|轮询|普通中断|时间戳/硬件调度|
|SRAM|小 ring|中等 ring|零拷贝大 ring|
|软件复杂度|厂商 HAL|自研 HAL|MAC/PHY 抽象层|
|可恢复性|简单重启|链路恢复|状态机 + 故障隔离|

### 编码规范

- 所有描述符结构使用固定宽度类型。
- DMA 地址使用目标架构支持的地址类型，不能默认假设指针可安全转换为 `uint32_t`。
- 不在 ISR 中调用可能阻塞的函数。
- 不使用未定义的位域布局映射硬件寄存器。
- 对所有 PHY、MAC、DMA 访问提供超时和错误返回值。
- 对描述符、buffer 和 Cache line 做显式对齐。

## 9. 常见错误与避坑指南

### 错误一：未处理 D-Cache

错误代码：

```
tx_desc->buf_addr = (uint32_t)packet;
tx_desc->status = DESC_OWN_BY_DMA;
```

根因：CPU 修改的数据仍在 Cache 中，DMA 从 SRAM 读取旧数据。

正确实现：

```
cache_clean(packet, packet_len);
__DMB();
tx_desc->buf_addr = dma_addr(packet);
cache_clean(tx_desc, sizeof(*tx_desc));
tx_desc->status = DESC_OWN_BY_DMA;
cache_clean(tx_desc, sizeof(*tx_desc));
```

风险：发送旧数据、偶发协议校验失败、问题难以复现。

### 错误二：RX 描述符过早交给 DMA

错误代码：

```
netif_receive(buf, len);
desc->status = DESC_OWN_BY_DMA;
```

根因：协议栈仍可能异步使用 `buf`，DMA 已经覆盖同一缓冲区。

正确实现：

```
netbuf_t *new_buf = netbuf_alloc();
if (new_buf != NULL) {
    netif_receive_owned(buf, len);
    desc->buf_addr = dma_addr(new_buf->data);
    desc->status = DESC_OWN_BY_DMA;
}
```

风险：数据内容被覆盖、TCP 重传、内存破坏。

### 错误三：无限等待 MDIO 或 DMA

错误代码：

```
while (MAC->STATUS & MAC_BUSY) {
}
```

根因：硬件异常、时钟关闭或总线错误时循环永不退出。

正确实现：

```
uint32_t deadline = time_us() + 1000U;

while ((MAC->STATUS & MAC_BUSY) != 0U) {
    if ((int32_t)(time_us() - deadline) >= 0) {
        return ETH_E_TIMEOUT;
    }
}
```

风险：启动任务永久阻塞，系统看门狗复位。

### 错误四：只读取 PHY 的 Link 位

错误代码：

```
if (phy_read(BMSR) & PHY_LINK_UP) {
    mac_enable();
}
```

根因：未读取协商后的 speed、duplex 和 pause 能力。

正确实现：

```
phy_link_t link;

if (phy_get_link_state(&link) == ETH_OK && link.up) {
    mac_set_speed(link.speed);
    mac_set_duplex(link.full_duplex);
    mac_set_pause(link.pause);
    mac_enable();
}
```

风险：MAC 与 PHY 工作模式不一致，出现碰撞、吞吐下降和随机丢帧。

### 错误五：ISR 中处理完整网络包

错误代码：

```
void ETH_IRQHandler(void)
{
    while (rx_has_packet()) {
        tcpip_input(rx_packet(), netif);
    }
}
```

根因：ISR 执行时间不可控，可能调用锁、内存分配和协议栈复杂路径。

正确实现：

```
void ETH_IRQHandler(void)
{
    uint32_t status = ETH->DMA_STATUS;

    ETH->DMA_STATUS = status;
    eth_event_flags |= status;
    rtos_notify_from_isr(eth_rx_task);
}
```

风险：高优先级中断延迟增加，系统实时性恶化。

## 10. 多机制组合使用方案

推荐组合：

```
PHY 自动协商
    +
MAC DMA 描述符环
    +
RX 中断唤醒
    +
批量轮询
    +
Cache 管理
    +
硬件校验和卸载
    +
链路状态机
    +
统计与故障恢复
```

### 完整框架

```
typedef struct {
    bool running;
    bool link_up;
    uint32_t speed_mbps;
    bool full_duplex;
    uint32_t rx_consumer;
    uint32_t tx_producer;
    uint32_t tx_reclaimer;
} eth_device_t;

static eth_device_t eth_dev;

static int eth_start(void)
{
    if (phy_reset() != 0) {
        return -1;
    }

    if (phy_wait_id(100U) != 0) {
        return -2;
    }

    if (rx_ring_setup() != 0 || tx_ring_setup() != 0) {
        return -3;
    }

    if (phy_start_autoneg() != 0) {
        return -4;
    }

    if (phy_wait_link(3000U) != 0) {
        return -5;
    }

    phy_link_t link;
    if (phy_get_link_state(&link) != ETH_OK) {
        return -6;
    }

    mac_set_speed(link.speed);
    mac_set_duplex(link.full_duplex);
    mac_enable_rx();
    mac_enable_tx();
    dma_enable();

    eth_dev.link_up = true;
    eth_dev.running = true;
    return 0;
}

static void eth_recovery(void)
{
    dma_disable();
    mac_disable_rx();
    mac_disable_tx();

    dma_clear_errors();
    rx_ring_rebuild();
    tx_ring_rebuild();

    if (phy_wait_link(3000U) == 0) {
        phy_link_t link;
        if (phy_get_link_state(&link) == ETH_OK) {
            mac_set_speed(link.speed);
            mac_set_duplex(link.full_duplex);
            dma_enable();
            mac_enable_rx();
            mac_enable_tx();
        }
    }
}
```

## 11. 工业级实际案例分析

### 案例一：工业数据采集网关

#### 需求

- 4 路传感器数据。
- 100 Mbps Ethernet。
- UDP 周期上报，周期 1 ms。
- 断链后 3 秒内自动恢复。
- 不允许因网络拥塞阻塞采集任务。

#### 架构

```
采集任务
   |
无锁/单写多读 Ring
   |
网络发送任务
   |
UDP
   |
MAC DMA + RMII PHY
```

设计要点：

- 采集任务只写入环形队列。
- 网络任务批量发送。
- UDP 队列满时丢弃最旧或最低优先级数据。
- Link Down 时暂停发送，但采集继续。
- 恢复后通过序列号检测数据缺口。

### 案例二：电机控制器远程维护接口

#### 需求

- Ethernet 仅用于参数配置、日志和升级。
- 电机控制周期为 100 us。
- 网络任务不得影响控制环。

#### 架构

```
高优先级定时器 ISR -> 电机控制任务
低优先级 Ethernet RX task -> 命令队列
低优先级日志任务 -> TX ring
```

设计要点：

- Ethernet 中断优先级低于控制环。
- 网络命令必须经过长度、来源、权限和 CRC 检查。
- 不允许网络任务直接修改控制参数。
- 使用双缓冲参数对象，在控制周期边界原子切换。

### 案例三：千兆视觉边缘节点

#### 需求

- 1 Gbps RAW 图像流。
- 1500 字节 MTU。
- CPU 预算小于 20%。
- 使用 DDR 和 D-Cache。
- 需要硬件时间戳。

#### 架构

```
RGMII PHY
   |
千兆 MAC
   |
多队列 DMA
   |
DDR 非缓存描述符区
   |
大页/连续 buffer
   |
零拷贝用户态或高性能协议栈
```

设计要点：

- RX/TX 描述符放置于 Non-cacheable 内存。
- 数据 buffer 使用 Cache line 对齐。
- RX 采用批处理。
- 启用 checksum offload。
- 启用 PTP 硬件时间戳。
- 通过队列和 CPU affinity 分散中断负载。

## 12. 高频问题深度答疑

### 问题一：MAC 和 PHY 是否可以只配置一个？

不可以。PHY 决定物理链路的速率和双工，MAC 必须配置成匹配模式。PHY 协商到 100 Mbps 全双工后，MAC 仍处于 10 Mbps 半双工，会导致吞吐异常和帧错误。

### 问题二：RMII 的 50 MHz 时钟由谁提供？

取决于硬件设计：

- PHY 输出 `REF_CLK`，MAC 输入。
- MCU 输出 `REF_CLK`，PHY 输入。
- 外部时钟源同时提供。

三者不能在未确认硬件连接的情况下混用。常见错误是软件配置为 MAC 输出，但 PCB 实际连接为 PHY 输出，结果表现为 MDIO 正常而收发无数据。

### 问题三：为什么 Ping 正常，但大文件传输丢包？

常见原因：

- RX buffer 数量不足。
- 大包跨多个描述符，FS/LS 处理错误。
- Cache 未 invalidate。
- DMA burst 配置不适合总线。
- 校验和卸载配置错误。
- PHY 双工模式不匹配。

应先使用 Wireshark 和 MAC 错误统计区分物理层、DMA 层还是协议栈层问题。

### 问题四：是否应该始终使用零拷贝？

不应该。零拷贝降低 CPU 和内存带宽开销，但会增加：

- Buffer 所有权管理复杂度。
- Cache 一致性成本。
- 内存碎片和生命周期风险。
- 协议栈适配复杂度。

低吞吐、小 SRAM、功能优先的系统可以采用单次拷贝。千兆或高包率系统再考虑零拷贝。

### 问题五：链路断开时，为什么 DMA 可能卡住？

PHY Link Down 本身不一定直接导致 DMA 卡死，但以下条件可能触发异常：

- TX 描述符长期保持 DMA 所有权。
- 发送队列在硬件停止时继续提交。
- DMA 状态位未清除。
- 总线访问发生错误。
- 软件没有重新构建损坏的 descriptor ring。

应通过 DMA 状态机检测 bus error、TX stopped、RX stopped 等状态，并执行受控恢复。

### 问题六：Ethernet 的实时性如何保证？

普通 Ethernet 和 TCP/IP 不提供确定性实时性。可以通过以下手段降低抖动：

- 独立网络任务和控制任务。
- 中断优先级合理配置。
- RX 批处理限制最大批量。
- 使用 UDP、TSN、EtherCAT 或专用协议。
- 使用硬件时间戳。
- 对发送队列和内存分配设置上限。
- 进行最坏执行时间测试，而不是只看平均吞吐。

## 13. 课程核心总结

- **PHY 负责物理层，MAC 负责帧处理，DMA 负责内存搬运，协议栈负责网络语义。**
- 初始化顺序必须是：**时钟/GPIO -> PHY 复位 -> MDIO 检测 -> 自动协商 -> MAC 配置 -> DMA 启动**。
- 性能通常排序为：**轮询 < 逐包中断 < 中断批处理 < 批处理零拷贝**。
- 可靠性最关键的三个问题是：**DMA 所有权、Cache 一致性、链路状态恢复**。
- 100 Mbps 系统通常优先考虑实现稳定性和低内存占用。
- 千兆系统必须重点评估：**总线带宽、Cache、DMA burst、队列数量和内存布局**。
- 普通 MAC 不能自动满足 EtherCAT、TSN 等确定性协议的要求。

## 14. 快速参考速查表

### 场景选型表

|需求|推荐实现|
|---|---|
|10/100 Mbps、低成本|RMII + 中断 DMA|
|100 Mbps、高突发|RX/TX ring + 批处理|
|1 Gbps|RGMII/SGMII + 多队列 DMA|
|低延迟控制|高优先级 RX task + 小批处理|
|大吞吐|零拷贝 + checksum offload|
|断链恢复|PHY 状态机 + MAC/DMA 重建|
|精确时延|PTP 硬件时间戳或 TSN|
|工业确定性|EtherCAT/TSN 专用硬件|

### 特性对比表

|特性|MAC|PHY|DMA|协议栈|
|---|---|---|---|---|
|处理对象|Ethernet 帧|电气信号|内存数据|IP/UDP/TCP|
|配置接口|MMIO|MDIO|MMIO/描述符|软件 API|
|典型问题|帧过滤、DMA 状态|Link、协商|OWN、Cache|队列、超时|
|主要测试工具|寄存器、统计|MDIO、示波器|trace、状态寄存器|Wireshark、iperf3|

## 15. 学习效果自检

- 能画出 PHY、MAC、DMA 和协议栈的数据流。
- 能解释 RMII 50 MHz 时钟的来源和方向。
- 能通过 MDIO 读取 PHY ID 和协商状态。
- 能正确建立 RX/TX descriptor ring。
- 能说明 `OWN` 位的状态转换规则。
- 能为 DMA buffer 设计 Cache 维护策略。
- 能定位 Link Down、DMA bus error 和 RX overrun。
- 能设计 ISR、RX task、TX task 的优先级关系。
- 能计算不同 MTU 下的理论帧率和带宽效率。
- 能说明普通 Ethernet 与 TSN/EtherCAT 的实时性差异。
- 能设计断链恢复和 DMA 重建流程。
- 能使用 Wireshark、`iperf3` 和 MAC 统计寄存器完成分层定位。

## 16. 实践与进阶路径

### 梯度实战任务

1. **任务一：PHY 探测**
    
    - 实现 MDIO 读写。
    - 扫描 PHY 地址。
    - 读取 PHY ID、Basic Status 和协商结果。
2. **任务二：裸机 Ping**
    
    - 初始化 RMII、MAC、DMA。
    - 接收 ARP 请求并回复。
    - 通过 Wireshark 验证帧字段。
3. **任务三：FreeRTOS + lwIP**
    
    - 实现 RX ISR 唤醒任务。
    - 增加 RX/TX ring。
    - 加入 Link Up/Down 状态机。
4. **任务四：性能优化**
    
    - 对比逐包中断、批处理和零拷贝。
    - 记录 CPU 占用、吞吐、延迟和丢包率。
    - 使用 DWT 或 PMU 统计每包周期数。
5. **任务五：故障注入**
    
    - 人为断开网线。
    - 修改 PHY 双工配置。
    - 制造 RX ring 耗尽、TX underrun 和 DMA 超时。
    - 验证驱动是否能自动恢复。

### 性能测试方法

至少记录：

```
吞吐量 Mbps
PPS，每秒数据包数
平均延迟
P99/P999 延迟
CPU 占用
RX/TX 丢包数
CRC 错误数
DMA bus error 数
Link flap 次数
内存峰值
```

测试矩阵：

|变量|测试值|
|---|---|
|包大小|64、128、512、1500、9000 B|
|速率|10、100、1000 Mbps|
|流量方向|RX、TX、双向|
|Cache|开启、关闭、Non-cacheable|
|模式|轮询、中断、批处理、零拷贝|
|链路状态|稳定、断链、反复协商|
|负载|空闲、满载、CPU 高负载|

### 进阶方向

- Ethernet checksum、TCP segmentation 和 receive-side offload。
- PTP、IEEE 1588 和硬件时间戳。
- TSN：802.1AS、802.1Qbv、802.1Qav。
- 多队列 DMA、RSS 和 CPU affinity。
- Linux `phylib`、`stmmac`、NAPI 和设备树配置。
- EtherCAT、PROFINET、EtherNet/IP。
- PHY 驱动、MDIO Clause 45 和 1000BASE-T1。
- EMC、EMI、磁性器件、阻抗控制和眼图分析。
- 网络安全：Secure Boot、固件升级认证、MACsec、工业协议鉴权。