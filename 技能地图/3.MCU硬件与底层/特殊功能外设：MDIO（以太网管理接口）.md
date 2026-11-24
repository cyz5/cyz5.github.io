

## 1. 学习目标

- **理解**：Clause 22/45 帧格式、PHY 地址、寄存器页与 MDC/MDIO 电气时序。
- **掌握**：轮询、读写、复位、链路状态获取、超时与总线恢复。
- **精通**：跨 MAC/PHY/交换芯片的管理架构、分页寄存器、扩展 MMD、并发访问与实时性约束。
- **能够设计**：具备故障诊断、可移植 HAL、启动配置和量产测试能力的 MDIO 驱动。

## 2. 前置要求

### 知识要求

- 以太网 MAC/PHY、IEEE 802.3 基础；
- GPIO 复用、开漏输出、上拉、电平与时序；
- C 语言位操作、并发、超时和错误处理；
- RTOS 互斥锁、设备树或板级配置。

### 技能要求

能够阅读 PHY 数据手册和波形，使用示波器/逻辑分析仪验证 MDC、MDIO，并能定位链路协商、复位和地址冲突问题。

## 3. 技术概述

MDIO 是 MAC 管理 PHY/交换芯片的低速串行管理总线，**不承载以太网数据**。典型信号为：

- **MDC**：管理时钟，通常最高 2.5 MHz（具体以芯片和标准版本为准）；
- **MDIO**：双向半双工管理数据线，需上拉，写入时主机驱动，读取时 PHY 驱动。

主要分支：

1. **Clause 22**：经典 PHY 管理，5 位寄存器地址，32 个寄存器，常用地址 0~31。
2. **Clause 45**：通过端口地址 `PRTAD` 和设备地址 `DEVAD` 访问更大寄存器空间，常用于 10G PHY、EEE、诊断和扩展管理。
3. **硬件 MDIO 控制器**：由 MAC 外设自动产生帧，CPU 只写寄存器。
4. **GPIO bit-bang**：适用于无硬件控制器、早期启动或特殊板级兼容，但实时性和可靠性较差。

## 4. 核心特性横向对比

|维度|Clause 22|Clause 45|硬件控制器|GPIO 模拟|
|---|---|---|---|---|
|地址空间|PHY 5 位 + Reg 5 位|PRTAD + DEVAD + 16 位寄存器|取决于协议|取决于软件|
|典型速率|10/100/1000M PHY|高速 PHY/扩展功能|稳定|易受中断影响|
|CPU 占用|低|低|最低|高|
|复杂度|低|中高|中|高|
|调试难度|低|中高|中|高|
|适用场景|普通铜缆 PHY|10G、EEE、诊断|量产产品首选|Bootloader/无硬件 MDIO|

**结论：** 产品驱动优先使用硬件 MDIO；Clause 22 足够时不要为扩展性引入 Clause 45 复杂度，但应为未来 MMD 访问预留接口。

## 5. 底层原理与功能特性深度解析

### 5.1 Clause 22 帧

一帧通常为：

```
PRE(32 个 1) | ST(01) | OP | PHYAD(5) | REGAD(5) | TA(2) | DATA(16)
```

读操作的 TA 由主机释放 MDIO，PHY 在第二个 TA 位开始驱动数据；写操作 TA 为 `10`，主机继续驱动。

### 5.2 Clause 22 寄存器

- `0x00 BMCR`：复位、速率、双工、自协商使能；
- `0x01 BMSR`：链路状态、自协商完成；部分 PHY 的链路位具有**读两次清除/锁存**语义；
- `0x02/0x03`：PHY ID；
- `0x04/0x05`：自协商能力与对端能力。

### 5.3 硬件控制器抽象

```
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    MDIO_OK = 0, MDIO_E_TIMEOUT = -1, MDIO_E_PARAM = -2,
    MDIO_E_BUS = -3
} mdio_status_t;

typedef struct {
    mdio_status_t (*read22)(uint8_t phy, uint8_t reg, uint16_t *val,
                            uint32_t timeout_us);
    mdio_status_t (*write22)(uint8_t phy, uint8_t reg, uint16_t val,
                             uint32_t timeout_us);
    void (*lock)(void);
    void (*unlock)(void);
} mdio_bus_t;

static mdio_status_t phy_read_id(mdio_bus_t *bus, uint8_t phy,
                                 uint32_t *id, uint32_t timeout_us)
{
    uint16_t hi, lo;
    if (!bus || !bus->read22 || !id || phy > 31) return MDIO_E_PARAM;
    bus->lock();
    mdio_status_t s = bus->read22(phy, 2, &hi, timeout_us);
    if (s == MDIO_OK) s = bus->read22(phy, 3, &lo, timeout_us);
    bus->unlock();
    if (s != MDIO_OK) return s;
    *id = ((uint32_t)hi << 16) | lo;
    return MDIO_OK;
}
```

**关键点：** 硬件完成位不能只等待固定延时，必须使用超时；读数据前确认控制器已释放总线；同一 MDIO 控制器上的访问必须串行化。

### 5.4 Clause 45 间接访问

常见控制器通过两帧完成：先发送地址帧，再发送数据读/写帧；更换 `DEVAD` 或寄存器时不能假设地址状态仍然有效。驱动应封装为原子操作，禁止其他线程插入。

### 5.5 GPIO bit-bang 核心

```
static void mdio_write_bit(int bit)
{
    gpio_set_output();              // 开漏：0 输出，1 应释放
    gpio_write(bit ? 1 : 0);
    delay_ns(200);                  // 依据 MDC 频率和器件时序校准
    gpio_write_mdc(1);
    delay_ns(200);
    gpio_write_mdc(0);
}

static int mdio_read_bit(void)
{
    int v;
    gpio_set_input();               // 释放 MDIO，由 PHY 驱动
    delay_ns(200);
    gpio_write_mdc(1);
    v = gpio_read_mdio();
    gpio_write_mdc(0);
    return v;
}
```

实际代码必须加入前导码、同步、TA 检查、临界区、异常退出后的 MDIO 释放和总线恢复。**绝不能以推挽高电平驱动 MDIO**，否则可能与 PHY 对冲。

## 6. 性能量化分析

假设 MDC 为 2.5 MHz，周期为 400 ns。Clause 22 一帧约 64 位：

```
T_frame ≈ 64 / 2.5 MHz = 25.6 μs
```

加控制器启动、总线空闲和软件调度，硬件访问典型约 **30~50 μs/次**；GPIO 模拟若每半周期延时 200 ns，通常约 **30~80 μs/次**，RTOS 抢占可能扩大到毫秒级。

启动阶段读取 6 个寄存器约需 `6 × 40 μs = 240 μs`，但链路协商通常需要几十到数百毫秒，瓶颈不在 MDIO，而在 PHY 状态机和电缆协商。

优化手段：

- 使用硬件控制器并批量初始化；
- 只在链路事件或定时器触发时轮询，不在高频数据路径访问 MDIO；
- 用中断/事件等待控制器完成；
- 缓存静态能力寄存器，动态状态按 10~100 ms 周期采样；
- 对超时记录 MDC/MDIO 波形和最后一次命令。

## 7. 应用场景选型指南

```
需要管理普通 10/100/1000M PHY？
├─ 是：硬件 MDIO + Clause 22
└─ 否：需要 EEE/10G/高级诊断？
    ├─ 是：硬件 MDIO + Clause 45/MMD
    └─ 否：芯片无 MDIO 控制器？
        └─ GPIO bit-bang，并严格限制访问频率
```

|场景|方案|理由|
|---|---|---|
|上电 PHY 初始化|Clause 22|BMCR、广告能力和 ID 足够|
|10G 光电 PHY|Clause 45|需要 DEVAD 和扩展寄存器|
|交换芯片端口配置|Clause 22/45 + 设备专用页|可能存在分页与间接窗口|
|量产测试|MDIO 扫描 + ID/状态校验|可快速发现地址、电源和焊接问题|
|无 MAC 控制器的 Bootloader|GPIO 模拟|依赖最少，但必须有恢复机制|

## 8. 工程最佳实践

1. **总线层、协议层、PHY 型号层分离**：`mdio_bus` 不应知道某型号寄存器含义。
2. 所有访问带**超时、返回码和锁**。
3. 设备地址、最大 MDC、复位 GPIO、时钟稳定时间全部板级配置化。
4. 对 PHY ID 做白名单匹配，避免把错误器件当成目标 PHY。
5. 复位后等待晶振/电源稳定，再访问寄存器。
6. 记录原始寄存器和链路状态，支持现场诊断。

### 选型决策矩阵

|要求|Clause 22|Clause 45|
|---|---|---|
|普通链路配置|★★★★★|★★|
|扩展诊断|★★|★★★★★|
|实现复杂度|★★★★★|★★★|
|可移植性|★★★★★|★★★|

## 9. 常见错误与避坑指南

### 错误一：MDIO 推挽驱动

```
gpio_mode_push_pull();
gpio_write(1); // 错误：PHY 读操作时可能对冲
```

根因是 MDIO 为共享半双工线；正确做法是开漏输出或输入高阻表示逻辑 1。风险是过流、波形畸变甚至损坏 IO。

### 错误二：无超时死等

```
while (!(MDIO->STATUS & DONE)) {}
```

根因是时钟未开、控制器复位、总线卡死都会使 DONE 永不置位。应使用单调时钟超时并复位控制器；否则任务永久阻塞。

### 错误三：并发交错 Clause 45 操作

```
write_addr(devad, reg_a);
// 线程 B 插入另一条访问
read_data(&v); // 读到错误寄存器
```

正确实现是把地址帧和数据帧放在同一互斥锁临界区。风险是偶发错误配置，难以复现。

### 错误四：只读一次 BMSR 判断链路

部分 PHY 的链路状态为锁存低或读两次更新语义。正确做法是按数据手册要求连续读取并解释；错误实现会造成链路掉线漏报。

### 错误五：写分页寄存器后未恢复页

```
write22(phy, PAGE_SEL, 3);
write22(phy, 0x10, value);
// 忘记恢复 PAGE_SEL=0
```

后续标准寄存器访问将落到错误页。应使用带恢复的作用域封装，并在失败路径同样恢复。

## 10. 多机制组合使用方案

推荐架构：**硬件 MDIO + RTOS 互斥锁 + PHY 状态机 + 链路事件 + 诊断日志**。

```
typedef enum { PHY_DOWN, PHY_RESETTING, PHY_AUTONEG, PHY_UP,
               PHY_FAULT } phy_state_t;

void phy_task(void *arg)
{
    phy_state_t state = PHY_RESETTING;
    for (;;) {
        switch (state) {
        case PHY_RESETTING:
            phy_hw_reset();
            os_delay_ms(10);
            state = PHY_AUTONEG;
            break;
        case PHY_AUTONEG:
            if (phy_start_autoneg() != MDIO_OK) state = PHY_FAULT;
            else state = PHY_UP;
            break;
        case PHY_UP:
            if (!phy_link_is_up()) state = PHY_AUTONEG;
            os_delay_ms(100);
            break;
        default:
            log_phy_registers();
            os_delay_ms(1000);
            state = PHY_RESETTING;
            break;
        }
    }
}
```

状态机避免在网络发送路径同步等待协商；锁保护总线，事件减少无意义轮询，日志保留故障上下文。

## 11. 工业级实际案例分析

### 案例一：工业网关千兆 PHY

- **需求**：上电自动协商，断线恢复，现场可读取 PHY ID。
- **架构**：MAC 硬件 MDIO、独立 PHY 任务、100 ms 状态采样、链路变化通知网络栈。
- **要点**：复位后等待参考时钟稳定；BMSR 按手册读取；配置失败重试但限制次数，避免系统启动永久卡住。

### 案例二：交换芯片多端口管理

- **需求**：16 个端口、分页寄存器、并发诊断。
- **架构**：统一总线锁；端口配置 API 使用 `try/finally` 风格页恢复；批量采集放到低优先级任务。
- **要点**：区分 PHY 地址和交换芯片管理地址；扫描时检查非法全 1/全 0 ID；避免诊断任务影响实时业务。

### 案例三：10G PHY Clause 45 诊断

- **需求**：读取 PMA、PCS、AN、EEE 状态和误码计数。
- **架构**：MMD 访问层 + 型号适配层 + 诊断快照；每次快照原子锁住地址/数据序列。
- **要点**：明确计数器清零语义、状态寄存器锁存语义和设备复位副作用；不能把 Clause 22 的寄存器假设套用到 Clause 45。

## 12. 高频问题深度答疑

### 1. MDC 为什么不能随意加速？

PHY 的输入滤波、建立保持时间和控制器规格都有上限。超频会使实验室偶尔成功、温度或批次变化时失败；应以控制器和 PHY 两者较小规格为准。

### 2. MDIO 读全 1 代表什么？

可能是空总线、地址错误、上拉异常、PHY 未上电，也可能是真实寄存器值。必须结合 PHY ID、波形、复位状态和电源测量判断。

### 3. 为什么链路已通但 BMSR 不稳定？

链路状态可能为锁存位，且自协商状态机仍在转换；应读取扩展状态、确认读取语义，并由状态机去抖，而非单次采样决定业务状态。

### 4. 是否可以每个数据包查询 PHY？

不可以。MDIO 是低速管理面，访问延迟远高于数据面，且会造成总线竞争。应采用周期采样、PHY 中断或 MAC 链路事件。

### 5. GPIO 模拟一定不可靠吗？

不是。短线、低速、严格时序和完整异常恢复下可可靠工作，但它占用 CPU、受中断影响，量产产品应优先硬件控制器。

### 6. Clause 22 能访问 Clause 45 PHY 吗？

部分器件支持通过 MMD 间接机制访问，但实现依赖 Clause 22 的特定寄存器窗口。必须按具体 PHY 手册实现，不应假定所有设备一致。

## 13. 课程核心总结

- **MDIO 是管理面，不是数据面**；
- 普通 PHY 优先 **Clause 22**，扩展和高速 PHY 使用 **Clause 45**；
- 最重要的可靠性机制是：**开漏/释放、超时、互斥、复位等待、错误日志**；
- 性能排序通常为：硬件控制器异步访问 > 硬件控制器轮询 > GPIO 模拟；
- 工业级实现必须把 PHY 型号差异、分页、锁存状态和失败恢复封装起来。

## 14. 快速参考速查表

### 场景选型

|场景|推荐|
|---|---|
|普通百兆/千兆 PHY|Clause 22|
|10G/EEE/高级诊断|Clause 45|
|无 MDIO 外设|GPIO bit-bang|
|多线程访问|总线互斥 + 原子复合操作|
|故障诊断|ID、BMCR、BMSR、AN、扩展状态快照|

### 特性对比

|项目|C22|C45|
|---|---|---|
|实现难度|低|中高|
|地址容量|小|大|
|普通兼容性|高|取决于器件|
|扩展能力|有限|强|

## 15. 学习效果自检

- 能否画出 Clause 22 读/写完整帧？
- 能否解释 TA 阶段为什么必须释放 MDIO？
- 能否实现带超时和锁的 C22 读写？
- 能否识别 PHY ID、复位、协商完成和链路状态？
- 能否处理分页寄存器和 Clause 45 原子访问？
- 能否用波形区分无上拉、地址错误、控制器未启动和 PHY 未驱动？
- 能否设计断线恢复而不阻塞网络数据面？

## 16. 实践与进阶路径

### 梯度实战

1. 实现 GPIO bit-bang C22，读取 PHY ID；
2. 增加写 BMCR、软复位和超时；
3. 迁移到硬件 MDIO，比较 CPU 占用和访问延迟；
4. 实现分页寄存器安全封装；
5. 实现 C45 MMD 访问和诊断快照；
6. 构建自动化测试：地址扫描、复位恢复、拔插网线、异常波形注入。

### 性能测试方法

记录 1000 次读操作的最小/平均/最大延迟、超时率、任务占用率和 MDC 抖动；在不同温度、电压、线长和中断负载下重复测试。验收建议包括：无误读、无永久阻塞、总线冲突为零、链路恢复时间满足系统指标。

### 进阶方向

深入 IEEE 802.3 Clause 22/45、PHY 自协商状态机、EEE、PCS/PMA、眼图与抖动、交换芯片管理、Linux phylib、设备树 PHY 框架，以及基于逻辑分析仪的协议自动解码。