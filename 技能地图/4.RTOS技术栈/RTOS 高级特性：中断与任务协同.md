
## 1. 学习目标

### 理解

- 理解中断上下文与任务上下文在抢占、栈、调度和 API 使用上的根本差异。
- 理解中断如何通过通知、信号量、队列和共享缓冲区唤醒任务。
- 理解中断延迟、ISR 执行时间、任务唤醒延迟和端到端响应时间之间的关系。
- 理解中断优先级、RTOS 临界区和调度器锁之间的约束关系。

### 掌握

- 掌握 ISR 与任务之间的数据交接、事件通知和缓冲区所有权管理。
- 掌握“ISR 只做必要工作，任务完成复杂处理”的分层设计。
- 掌握 DMA 完成、UART 接收、ADC 采样、定时器到期等常见协同模式。
- 掌握 ISR-safe API 的调用约束及其对调度切换的影响。

### 精通

- 能基于目标 RTOS 和 MCU 架构分析中断入口、异常返回、PendSV 切换及临界区实现。
- 能量化 ISR 执行时间、任务唤醒延迟、最坏中断屏蔽时间和端到端响应时间。
- 能处理事件合并、队列溢出、DMA 缓冲区复用、缓存一致性和多中断源竞争。
- 能识别中断嵌套、优先级配置错误、ISR 过长和任务延迟处理造成的系统级故障。

### 能够设计

- 能为硬实时数据路径设计 ISR、缓冲区、通知和处理任务的协同架构。
- 能为中断负载、任务优先级和缓冲区容量制定可验证的上界。
- 能设计过载策略、故障检测和中断风暴防护。
- 能在目标板上对协同路径进行追踪、测量和压力验证。

## 2. 前置要求

### 知识要求

- Cortex-M 异常模型、优先级和异常返回基础。
- RTOS 任务状态、调度策略、任务优先级和上下文切换。
- 临界区、互斥锁、信号量、队列、任务通知和事件组。
- DMA、环形缓冲区、双缓冲和外设中断基础。
- C 语言 `volatile`、原子操作、内存屏障和对齐概念。

### 技能要求

- 能查阅具体 RTOS 的 ISR-safe API 和中断优先级约束。
- 能阅读启动代码、向量表、SysTick、PendSV 和临界区实现。
- 能用 DWT 周期计数器、硬件定时器、GPIO 和逻辑分析仪测量时延。
- 能检查中断优先级配置、RTOS tick 配置和任务栈余量。
- 能编写中断负载、队列满、DMA 覆盖和中断丢失测试。

## 3. 技术概述

### 3.1 中断与任务的职责边界

中断是硬件事件到 CPU 的快速响应路径。任务是可调度的执行单元，适合进行有状态、可阻塞、耗时较长的处理。

常见的协同方式：

```
外设事件
   |
   v
ISR：确认源、取必要数据、记录状态、唤醒任务
   |
   v
任务：排空缓冲区、解析、状态机处理、调用其他模块
```

**核心原则**：ISR 负责将硬件状态转化为软件可消费的事件，任务负责完成业务处理。ISR 不是“高优先级任务”，而是更受限制的执行上下文。

### 3.2 为什么不在 ISR 中完成全部工作

ISR 执行时通常不能阻塞。它可能：

- 抢占正在运行的任何任务；
- 阻止同级或更低优先级中断运行；
- 延迟 RTOS 调度和其他任务；
- 持有独立的中断栈或当前任务栈；
- 在某些 RTOS 中受限于可调用 API 和中断优先级。

在 ISR 中执行协议解析、日志格式化、动态内存分配、等待外设、复杂锁操作，会让中断响应时间和抖动不可控。

### 3.3 常见协同模式

|模式|ISR 传递内容|任务接收方式|适用情况|
|---|---|---|---|
|事件唤醒|无数据或少量状态|二值信号量、通知位|“有事要处理”|
|事件计数|发生次数|计数通知、计数信号量|脉冲、采样完成次数|
|小消息传递|固定结构体|ISR-safe 队列|少量短消息，需逐条处理|
|缓冲区 + 通知|数据写入共享缓冲区|通知任务后排空缓冲区|高频字节流、采样流|
|DMA + 描述符|已完成缓冲区索引或指针|队列、通知、事件组|大块数据传输|
|快照/标志位|当前状态或错误位|原子变量、通知位|最新状态或可合并事件|
|延迟中断处理|最小化顶半部|任务执行底半部|需要较重后处理的外设|

## 4. 核心特性横向对比

|协同机制|ISR 开销|数据容量|是否保留每次事件|多生产者能力|主要注意事项|
|---|---|---|---|---|---|
|二值信号量|低|仅表示有/无|否，事件可合并|通常可|不适合要求逐次计数的事件|
|计数信号量|低|有计数上限|有计数语义|通常可|溢出和计数饱和必须处理|
|任务通知位|很低|固定位数|同一位重复置位会合并|需统一位分配|适合单一目标任务|
|任务通知计数|很低|计数值范围内|可计数|依 API 设计|不能承载复杂消息|
|ISR-safe 队列|中|固定队列容量|通常逐条保留|通常支持|拷贝成本、队列满和临界区开销|
|Ring buffer + 通知|低到中|由缓冲区决定|可逐条保留数据|需匹配并发模型|必须正确处理索引和溢出|
|DMA + 双缓冲|ISR 极低|缓冲区大小决定|按块保留|通常由 DMA 单生产者|所有权切换和 cache 一致性|
|共享状态快照|很低|固定状态结构|只保留最新状态|通常需单写者或额外同步|多字段一致性和读写重叠|

### 4.1 选择机制时的关键问题

|问题|设计影响|
|---|---|
|每次硬件事件都必须处理吗？|若是，使用计数或数据队列；若否，可合并通知|
|ISR 是否产生数据，还是只产生状态？|数据通常放缓冲区；通知只负责唤醒|
|是否存在多个中断源？|需要区分来源，不能让单一标志丢失语义|
|中断频率和突发长度是多少？|决定 ISR 成本、缓冲区大小和任务服务能力|
|任务处理是否可能慢于输入？|必须加入背压、丢弃或过载降级|
|DMA 是否写入带 cache 的内存？|需考虑 cache clean/invalidate 和内存屏障|
|ISR 优先级是否允许调用 RTOS API？|必须符合端口的 syscall 优先级边界|

## 5. 底层原理与功能特性深度解析

### 5.1 Cortex-M 上的典型切换路径

以常见 Cortex-M RTOS 设计为例：

1. 外设触发 IRQ。
2. CPU 保存部分异常现场，进入 ISR。
3. ISR 确认中断源并执行必要处理。
4. ISR 调用 ISR-safe API，将任务从 Blocked 变为 Ready。
5. 若新就绪任务优先级高于当前任务，RTOS 设置“需要切换”状态。
6. ISR 返回时触发 PendSV，完成任务上下文保存与恢复。
7. 新任务开始运行。

常见端口会让高优先级中断直接抢占，但由 PendSV 完成任务切换，以避免在多个 ISR 级别重复进行完整切换。

### 5.2 中断优先级与 RTOS API 边界

在 Cortex-M 上，优先级数值方向和可屏蔽行为容易混淆：

- CMSIS 配置接口通常以 **数值越小，硬件优先级越高** 表示。
- 很多 RTOS 只允许优先级低于某个门限的中断调用内核 API。
- 高于该门限的高紧急度中断可抢占内核，但不得调用会修改内核数据结构的 API。
- `BASEPRI` 临界区通常屏蔽达到某个优先级门限的中断，不一定屏蔽最高优先级中断。

具体限制必须以所用 RTOS 端口、芯片实现和配置为准。错误地从高优先级 ISR 调用队列或信号量 API，可能造成内核列表损坏或难以复现的调度故障。

### 5.3 ISR-safe API 的实际语义

ISR-safe API 通常有不同于任务 API 的接口和约束：

- 不阻塞等待资源；
- 不能使用“无限等待”参数；
- 通常通过输出参数告知是否唤醒了更高优先级任务；
- 必须在 ISR 退出路径请求一次可能的调度切换；
- 某些 API 只允许特定中断优先级调用。

典型模式：

```
void PERIPHERAL_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;

    clear_peripheral_irq();

    vTaskNotifyGiveFromISR(worker_task_handle,
                           &higher_priority_woken);

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

其中“是否需要切换”不是装饰参数。若 ISR 唤醒了更高优先级任务却未触发调度，新任务可能要等到下一次 tick 或其他调度点才运行。

### 5.4 顶半部与底半部

“顶半部/底半部”是常见架构划分，不一定是具体 RTOS 的官方术语：

- **顶半部**：硬件 ISR，执行时间短、不可阻塞，完成确认中断和数据交接。
- **底半部**：由任务、工作队列或 deferred interrupt 机制执行的后续处理。

适合放在顶半部的内容：

- 读取并清除中断状态；
- 读取少量状态寄存器；
- 记录 DMA 完成索引；
- 将数据写入无阻塞缓冲区；
- 发通知或投递短消息；
- 处理必须立即响应的硬件动作。

适合放在任务中的内容：

- 协议解析；
- 复杂状态机；
- 校验和、解密、压缩；
- 动态对象管理；
- 多模块调用；
- 可阻塞操作；
- 低优先级日志与诊断。

### 5.5 通知合并与事件计数

二值事件通常只回答：“至少发生过一次事件吗？”

如果 ISR 在任务运行前连续发生 5 次，二值信号量可能只留下一个“已发生”状态。若这 5 次必须逐一处理，应使用：

- 计数通知；
- 计数信号量；
- 带数据的队列；
- 缓冲区中的逐条记录。

如果事件只是“硬件状态有更新”，合并通常更高效。消费者应在唤醒后读取当前状态或排空缓冲区，而不是假设一次唤醒对应一次硬件事件。

### 5.6 ISR 与 Ring Buffer 协同

单生产者单消费者模型是常见的 ISR 数据通路：

```
ISR：唯一生产者，写入 ring buffer
任务：唯一消费者，读取 ring buffer
```

设计必须明确：

- 是否只有一个 ISR 写入；
- 是否有多个任务读取；
- 缓冲区满时如何处理；
- 索引是否原子；
- 生产者发布数据前是否需要内存屏障；
- consumer 读完后何时释放槽位。

SPSC 环形缓冲区中，ISR 只写 `head`，任务只写 `tail`。若多个 ISR 都可能写同一缓冲区，就不再是 SPSC，需要额外串行化或采用经过验证的 MPSC 结构。

### 5.7 DMA 缓冲区的所有权状态机

DMA 与任务协同的核心不是通知 API，而是缓冲区所有权：

```
FREE
  -> DMA_OWNED
  -> READY_FOR_TASK
  -> TASK_OWNED
  -> FREE
```

每次转移都必须由一个明确事件触发：

- 启动 DMA：CPU 将缓冲区交给 DMA。
- DMA 完成：ISR 将已完成缓冲区标记为可处理。
- 任务处理：任务取得缓冲区所有权。
- 处理结束：缓冲区归还给 DMA 或缓冲池。

禁止以下情况：

- DMA 仍写入时任务读取；
- 任务处理时 DMA 覆盖同一缓冲区；
- 多个任务同时持有同一缓冲区；
- 任务提前释放仍被 DMA 使用的缓冲区；
- 使用栈上缓冲区启动异步 DMA。

### 5.8 缓存一致性和内存屏障

在没有数据 cache 的小型 MCU 上，DMA 与 CPU 共享 SRAM 通常较直接；有 D-cache 的 MCU 则需额外处理：

- CPU 写、DMA 读：DMA 开始前可能需要 clean cache。
- DMA 写、CPU 读：CPU 处理前可能需要 invalidate cache。
- 缓冲区地址和长度应满足 cache line 对齐要求，避免影响相邻数据。
- 编译器屏障、CPU 内存屏障和 cache 维护是不同概念，不能相互替代。
- 必须遵从芯片手册、BSP 和 RTOS DMA API 的约定。

### 5.9 时间预算与最坏中断响应

一个中断协同路径的粗略端到端时延：

Levent=Lirq-entry+CISR+Ldefer+Lschedule+Ltask-queue+CtaskLevent​=Lirq-entry​+CISR​+Ldefer​+Lschedule​+Ltask-queue​+Ctask​

其中：

- Lirq-entryLirq-entry​：硬件进入中断的延迟；
- CISRCISR​：ISR 执行时间；
- LdeferLdefer​：任务因高优先级任务或中断未能运行的时间；
- LscheduleLschedule​：从 ISR 退出到任务开始运行的调度延迟；
- Ltask-queueLtask-queue​：任务之前已有工作的排队时间；
- CtaskCtask​：任务处理时间。

**中断“已触发”不等于任务“已处理”** 。实时需求应在正确的阶段打点，例如硬件边沿到任务处理结束，而不是只测 ISR 本身。

## 6. 性能量化分析

### 6.1 实测数据应如何报告

下表仅是 Cortex-M4F、约 168 MHz、静态分配、`-O2` 环境下常见的**量级参考**，不是任何 RTOS 的性能保证。实际结果与编译器、Flash wait state、临界区实现、优先级和竞争负载相关。

|路径|代表性量级|说明|
|---|---|---|
|硬件 IRQ 进入至 ISR 首条 C 语句|约 0.1~1 µs|受中断屏蔽、当前指令和总线状态影响|
|短 ISR：读状态、清中断、置标志|约 0.5~3 µs|不包含复杂驱动处理|
|ISR 发任务通知，不导致切换|约 1~4 µs|受内核临界区和通知对象实现影响|
|ISR 唤醒高优先级任务并切换|约 3~15 µs|含 PendSV 和上下文切换，需实测|
|ISR 入队 16 字节消息|约 2~8 µs|队列未满时；竞争与唤醒会增加成本|
|任务从通知唤醒到开始运行|约 2~20 µs|受更高优先级任务和中断干扰影响|

这些数字用于初步估算。用于实时性签核的数据必须来自目标板，在目标优化级别和最坏负载下测量。

### 6.2 CPU 负载估算

若中断频率为 ff，平均 ISR 执行时间为 CISRCISR​，CPU 频率为 FCPUFCPU​，ISR 占用率近似为：

UISR=f⋅CISRFCPUUISR​=FCPU​f⋅CISR​​

例如：

- 中断频率：20 kHz；
- 每次 ISR：1.5 µs；
- CPU 频率：168 MHz。

换算为每秒 CPU 时间：

20,000×1.5 μs=30 ms/s20,000×1.5 μs=30 ms/s

占用率约为：

UISR=3%UISR​=3%

此计算尚未包含任务处理、上下文切换和更高优先级中断。

### 6.3 中断合并与批处理的收益

若每个样本都唤醒一次任务，单位时间调度次数约等于样本频率 fsfs​。若每 NN 个样本或每块 DMA 数据唤醒一次，调度频率可近似降低为：

fwake≈fsNfwake​≈Nfs​​

例如 16 kHz 采样，每 16 个样本处理一次：

fwake≈1 kHzfwake​≈1 kHz

调度和通知次数约减少 16 倍，但会增加最多约 15 个采样周期的批次形成延迟。若系统时限不允许这段等待，应改用半满 DMA 中断、更小块大小或双阈值机制。

### 6.4 缓冲区容量估算

若数据以 λλ 字节/秒到达，任务最长可能无法运行 TstallTstall​ 秒，额外突发量为 BB 字节，缓冲区最小容量可先估算为：

Nbuffer≥⌈λ⋅Tstall⌉+BNbuffer​≥⌈λ⋅Tstall​⌉+B

例如：

- UART 输入速率：115200 bit/s，按 8N1 约 11520 byte/s；
- 消费任务最长停顿：30 ms；
- 突发余量：128 字节。

Nbuffer≥⌈11520×0.03⌉+128=474 bytesNbuffer​≥⌈11520×0.03⌉+128=474 bytes

工程上可先选 512 或 1024 字节，再进行压力测试并监控高水位。若消费者长期处理速度低于输入速率，增加缓冲区只能延迟溢出，不能解决持续过载。

### 6.5 最坏中断延迟来源

最坏中断响应通常由以下因素叠加：

- 全局关中断或 `BASEPRI` 屏蔽窗口；
- 更高优先级 ISR 执行时间；
- 同优先级中断不能相互抢占；
- 总线竞争和 Flash wait state；
- 驱动读取状态寄存器的额外等待；
- 临界区嵌套；
- 长时间 ISR 和中断风暴；
- cache miss、DMA 总线访问或外设同步延迟。

中断响应时间分析至少应记录：

- 最大中断屏蔽时间；
- 高于目标 IRQ 的中断执行时间和到达频率；
- 目标 ISR 的 WCET；
- ISR 返回到任务运行的最坏调度延迟。

### 6.6 性能优化手段及代价

|优化方法|收益|代价或风险|
|---|---|---|
|ISR 只做必要工作|降低中断阻塞和抖动|任务端处理延迟增加|
|通知与数据缓冲分离|减少每事件的消息拷贝|需管理缓冲区和溢出|
|DMA 双缓冲|降低逐字节 ISR 负载|所有权和 cache 处理复杂|
|批处理|降低调度次数和固定开销|增加批次等待时延|
|静态缓冲池|避免堆分配抖动和碎片|需要预留 RAM|
|提升处理任务优先级|降低事件处理延迟|可能影响其他实时任务|
|缩短临界区|降低 IRQ 屏蔽延迟|可能增加共享状态同步成本|
|合并重复事件|减少队列压力|不能用于必须逐条处理的事件|

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
ISR 是否产生必须逐条保留的数据？
|
+-- 否，只需表示“状态已变化”
|   |
|   +-- 单一目标任务 --> task notification / 二值信号量
|   +-- 多条件状态 --> event flags / 状态快照
|
+-- 是
    |
    +-- 数据量很小，事件频率低？
    |   |
    |   +-- 是 --> ISR-safe queue
    |   +-- 否 --> ring buffer / stream buffer / DMA
    |
    +-- 是否为大块连续数据？
        |
        +-- 是 --> DMA + 双缓冲或缓冲池 + 描述符通知
        +-- 否 --> 固定结构队列或 SPSC ring buffer

最后检查：
    |
    +-- ISR 优先级是否允许调用该 RTOS API？
    +-- 队列/缓冲区满时怎么办？
    +-- 消费任务是否有足够服务能力？
    +-- 数据所有权和 cache 维护是否清晰？
```

### 7.2 典型场景选型表

|场景|推荐协同方式|关键考虑|
|---|---|---|
|GPIO 按键中断|ISR 去抖触发定时器/通知任务|不在 ISR 中延时去抖|
|ADC 低频单样本|ISR 读取样本并通知任务|若样本不可丢，使用计数或缓冲区|
|ADC 高频采样|DMA + 半满/完成中断 + 处理任务|DMA 缓冲区时限和覆盖|
|UART 接收|DMA circular buffer + 通知|处理 DMA 写位置和缓冲溢出|
|UART 发送完成|ISR 清状态并通知发送任务|任务管理后续发送和超时|
|SPI DMA 完成|ISR 更新事务状态并唤醒所有者任务|上下文恢复、取消和错误处理|
|定时器周期事件|直接任务通知或计数通知|是否必须保留每次到期|
|外设错误中断|ISR 保存错误状态、触发高优先级处理任务|错误恢复路径不能同步打印日志|
|高频网络帧|DMA/Ring + 协议任务|批处理、优先级和缓存管理|

## 8. 工程最佳实践

### 8.1 ISR 设计原则

- 先读取并确认中断源，遵循外设手册规定的清除顺序。
- ISR 只执行有明确上界的操作。
- ISR 不等待 mutex、信号量、队列空间或外设完成。
- ISR 不执行动态内存分配、复杂日志、文件访问和阻塞 I/O。
- ISR 不调用普通任务 API，除非 RTOS 明确允许。
- 对可能反复触发的中断源，确认状态清除逻辑能防止中断风暴。
- 对边沿/电平中断分别处理重新触发和清除时序。
- 多个中断源共享处理任务时，携带来源位图、索引或独立状态，避免事件混淆。

### 8.2 任务设计原则

- 任务被唤醒后优先排空缓冲区，避免一条消息处理完就睡回去导致积压。
- 任务处理逻辑采用有界批次，避免长时间霸占 CPU。
- 处理任务优先级依据数据截止时间、积压风险和系统调度分析决定。
- 需要保留顺序的事务使用有序队列，不依赖任务抢占顺序。
- 对过期事件设置策略：处理、丢弃、合并或降级。
- 任务不能假设每次中断都有对应的一次唤醒。

### 8.3 优先级与 API 规范

- 根据 RTOS port 的要求配置“可调用内核 API 的最低紧急度”边界。
- 数值越高还是越低表示优先级更高，必须以芯片和 API 语义分别确认。
- 高紧急度中断如果不能调用 RTOS API，应通过共享原子状态或更低紧急度的 deferred IRQ 交接。
- 在 ISR 调用唤醒 API 后，使用 RTOS 提供的 ISR 退出让步机制。
- 不在高优先级 ISR 中调用可能使用内核锁或更新复杂等待队列的 API。
- 临界区和关中断窗口必须有可测量的上界。

### 8.4 过载与故障策略

对每条中断数据路径定义：

- 缓冲区满时是丢弃新数据还是覆盖旧数据；
- 能否对上游硬件施加背压；
- 如何计数丢包和 overrun；
- 过载时是否降低采样率或丢弃低优先级数据；
- 数据异常如何恢复同步；
- 任务未按时处理时是否报警、复位外设或进入降级模式。

### 8.5 监控指标

至少监控：

- ISR 最大执行时间；
- IRQ 最大响应延迟；
- ISR 触发频率和异常频率；
- ISR 到任务开始运行的最大延迟；
- 缓冲区高水位和溢出次数；
- 任务处理时间最大值；
- 消息序号缺口；
- DMA 错误和 cache 相关异常；
- 中断风暴和任务未响应次数。

## 9. 常见错误与避坑指南

### 错误一：在 ISR 中调用阻塞 API

错误代码：

```
void UART_IRQHandler(void)
{
    mutex_lock(&uart_mutex);
    process_rx_data();
    mutex_unlock(&uart_mutex);
}
```

根因：ISR 不能阻塞等待任务释放 mutex；当前持锁任务也可能正等待该 ISR 或其后续事件。

正确实现：

```
void UART_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;

    uint8_t byte = uart_read_data_register();
    rx_ring_push_from_isr(byte);

    vTaskNotifyGiveFromISR(rx_task_handle,
                           &higher_priority_woken);

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

风险：死锁、内核状态损坏、ISR 重入异常或系统失去调度能力。

### 错误二：ISR 中进行完整协议解析

错误代码：

```
void CAN_IRQHandler(void)
{
    can_frame_t frame;
    can_read_frame(&frame);
    protocol_decode(&frame);
    update_database(&frame);
    log_frame(&frame);
}
```

根因：协议解析、数据库访问和日志都可能耗时不确定，延长中断屏蔽和其他 ISR 等待时间。

正确实现：

```
void CAN_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;
    can_frame_t frame;

    if (can_read_frame(&frame) == STATUS_OK) {
        if (queue_send_from_isr(&can_rx_queue,
                                &frame,
                                &higher_priority_woken) != STATUS_OK) {
            can_rx_overrun_count++;
        }
    }

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

若帧流量较高，应考虑 DMA、硬件 FIFO 和环形缓冲区，避免逐帧队列拷贝。

### 错误三：用二值通知表示必须逐次处理的事件计数

错误代码：

```
vTaskNotifyGiveFromISR(worker, &higher_priority_woken);
/* worker 每次醒来只处理一项 */
```

根因：多次 ISR 可能在任务运行前合并成一次唤醒。

正确实现：

```
ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

while (event_ring_pop(&event)) {
    process_event(&event);
}
```

或者使用计数通知，并确认计数范围和溢出语义满足要求。

风险：漏处理脉冲、样本或完成事件，造成状态机永久不同步。

### 错误四：忘记在 ISR 退出时请求任务切换

错误代码：

```
void DMA_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;

    vTaskNotifyGiveFromISR(worker_task, &higher_priority_woken);
    /* 忘记调用 ISR 退出让步宏 */
}
```

根因：任务虽然已变为 Ready，但没有立即切换，可能延迟到下一次 tick 或其他调度点。

正确实现：

```
portYIELD_FROM_ISR(higher_priority_woken);
```

宏名称和调用位置依 RTOS port 而异，应使用端口提供的写法。

风险：额外延迟和抖动，导致高频数据缓冲区在任务运行前溢出。

### 错误五：高优先级 IRQ 调用 RTOS API

错误代码：

```
void HIGH_URGENCY_IRQHandler(void)
{
    queue_send_from_isr(&queue, &item, &woken);
}
```

根因：该 IRQ 优先级可能高于 RTOS 允许调用内核 API 的门限。API 内部临界区无法保护被该 IRQ 抢占的数据结构。

正确实现：

- 将该中断调整到允许调用内核 API 的优先级范围；
- 或 ISR 只写入专用寄存器/原子状态，再由可调用内核 API 的较低优先级中断或任务处理；
- 按 RTOS 配置和芯片优先级分组核验数值关系。

风险：内核等待链、就绪队列或调度状态损坏，通常表现为随机 HardFault 或异常死锁。

### 错误六：DMA 尚未完成就复用缓冲区

错误代码：

```
dma_start(rx_buffer, sizeof(rx_buffer));
fill_next_packet(rx_buffer);  /* DMA 仍可能写入 */
```

根因：CPU 和 DMA 同时访问同一缓冲区，发生写写或读写竞争。

正确实现：使用双缓冲或缓冲池，并通过明确状态转换交接所有权：

```
DMA_OWNED -> READY_FOR_TASK -> TASK_OWNED -> FREE
```

风险：数据块混杂、帧校验失败、随机协议错误或缓存内容损坏。

### 错误七：在 ISR 中打印日志

错误代码：

```
void ERROR_IRQHandler(void)
{
    printf("hardware error\n");
}
```

根因：格式化和串口输出可能阻塞、调用锁或触发复杂 libc 路径。

正确实现：ISR 记录错误码和硬件状态，再通知低优先级诊断任务输出：

```
void ERROR_IRQHandler(void)
{
    error_snapshot = read_error_status();
    error_pending = 1U;
    notify_diagnostic_task_from_isr();
}
```

风险：中断时延暴涨、递归中断、锁死或因日志输出速度慢导致持续过载。

## 10. 多机制组合使用方案

### 10.1 高频数据路径架构

推荐结构：

```
外设
  |
  +-- DMA 写入 Buffer A/B
        |
        +-- DMA 完成 ISR
              - 清中断
              - 记录 buffer index
              - 发布缓冲区状态
              - 通知处理任务
                    |
                    +-- 排空已完成块
                    +-- 校验、解析、状态机处理
                    +-- 归还或重新提交缓冲区
```

该结构把三种职责分开：

- DMA 搬运数据；
- ISR 完成硬件与软件状态交接；
- 任务完成可变时长的处理逻辑。

### 10.2 多中断源汇聚方案

若多个低速中断只表示状态变化，可使用通知位：

```
IRQ A -> 设置 EVENT_A
IRQ B -> 设置 EVENT_B
IRQ C -> 设置 EVENT_C
             |
             v
      设备服务任务读取状态快照
```

任务必须明确位的合并语义：同一事件连续发生多次可能只保留一次。若需要计数或逐条参数，使用单独计数器或队列。

### 10.3 高优先级 IRQ 与 RTOS 解耦

对于必须设为高紧急度、但不允许调用内核 API 的 IRQ：

```
高紧急度 IRQ
    -> 只记录硬件状态 / 写入固定长度 lock-free mailbox
    -> 触发较低紧急度 deferred IRQ
    -> deferred IRQ 调用 RTOS API 唤醒任务
```

要求：

- 高紧急度 IRQ 路径必须有界；
- mailbox 并发模型与 IRQ 数量匹配；
- 写入顺序和内存屏障正确；
- deferred IRQ 自身优先级满足 RTOS API 约束；
- mailbox 满时有明确策略。

### 10.4 生产级 C 框架：DMA 完成交接

下面是与具体 RTOS API 无关的框架。项目需将接口映射到目标芯片和 RTOS。

```
typedef enum {
    BUFFER_FREE = 0,
    BUFFER_DMA_OWNED,
    BUFFER_READY,
    BUFFER_TASK_OWNED
} buffer_state_t;

typedef struct {
    uint8_t *data;
    uint16_t length;
    uint16_t capacity;
    volatile buffer_state_t state;
    uint32_t sequence;
} dma_buffer_t;

static dma_buffer_t rx_buffers[2];

void DMA_RX_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;
    uint32_t completed_index = dma_get_completed_buffer_index();

    dma_clear_irq_flags();

    dma_buffer_t *completed = &rx_buffers[completed_index];

    /*
     * 有 D-cache 的平台在这里按 BSP 规范执行 invalidate；
     * 缓冲区地址和长度必须满足 cache line 要求。
     */
    dma_rx_cache_invalidate(completed->data, completed->length);

    completed->sequence++;
    completed->state = BUFFER_READY;

    if (queue_send_from_isr(&rx_ready_queue,
                            &completed,
                            &higher_priority_woken) != STATUS_OK) {
        rx_overrun_count++;
        completed->state = BUFFER_FREE;
    }

    portYIELD_FROM_ISR(higher_priority_woken);
}

void dma_rx_task(void *arg)
{
    for (;;) {
        dma_buffer_t *buffer = NULL;

        if (queue_receive(&rx_ready_queue,
                          &buffer,
                          WAIT_FOREVER) != STATUS_OK) {
            continue;
        }

        if ((buffer == NULL) || (buffer->state != BUFFER_READY)) {
            report_buffer_state_fault();
            continue;
        }

        buffer->state = BUFFER_TASK_OWNED;
        process_rx_block(buffer->data, buffer->length);

        buffer->state = BUFFER_FREE;
        dma_submit_free_buffer(buffer);
    }
}
```

这个框架还需要补齐：

- DMA 的实际完成判定和重装顺序；
- 处理任务尚未完成时的备用缓冲区策略；
- 任务处理超时和缓冲区回收；
- cache line 对齐；
- 队列满时是否允许丢块；
- 多个 DMA 通道共享 buffer pool 的同步；
- `volatile` 不能代替原子操作或完整的内存屏障。

## 11. 工业级实际案例分析

以下是常见工程设计模式，不代表特定厂商产品实现。

### 案例一：UART DMA 接收协议帧

#### 需求

- UART 连续接收字节流；
- 协议帧长度可变；
- 接收速率可能突发；
- 协议解析不可在 ISR 中完成。

#### 架构设计

```
UART DMA circular buffer
    -> 半满/全满/空闲中断
    -> ISR 记录 DMA 写位置并通知协议任务
    -> 协议任务按软件读指针提取字节
    -> 帧解析与校验
```

#### 核心代码思路

```
void UART_RX_IRQHandler(void)
{
    BaseType_t higher_priority_woken = pdFALSE;

    uint16_t dma_pos = uart_dma_get_write_position();
    atomic_store_explicit(&dma_write_position,
                          dma_pos,
                          memory_order_release);

    vTaskNotifyGiveFromISR(protocol_task_handle,
                           &higher_priority_woken);

    portYIELD_FROM_ISR(higher_priority_woken);
}

void protocol_task(void *arg)
{
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        uint16_t write_pos =
            atomic_load_explicit(&dma_write_position,
                                 memory_order_acquire);

        while (software_read_position != write_pos) {
            uint8_t byte = uart_dma_buffer[software_read_position];
            protocol_parser_feed(byte);

            software_read_position =
                (software_read_position + 1U) % UART_DMA_BUFFER_SIZE;
        }
    }
}
```

#### 设计要点

- 通知用于唤醒，数据仍保留在 DMA ring buffer。
- 半满、全满和空闲事件可能同时发生，需要正确处理重复位置通知。
- 软件读指针不能落后到 DMA 覆盖旧数据之前。
- 应监控 overrun、最大读写差和解析任务最大延迟。
- 有 D-cache 时按平台要求处理 DMA buffer cache 一致性。

### 案例二：ADC 采样与控制任务

#### 需求

- ADC 以固定频率采样；
- 低延迟处理每批样本；
- 不能让每个采样都触发一次复杂任务切换。

#### 架构设计

```
ADC + DMA 双缓冲
    -> 每半缓冲完成触发 ISR
    -> ISR 发布 block index 并通知控制任务
    -> 控制任务处理固定大小样本块
```

#### 设计要点

- 每块样本数决定批次延迟和调度开销。
- 控制任务需在 DMA 回到该块前处理完成。
- 若控制任务偶发超时，应增加缓冲深度、降低块大小或降低处理负载，而不是仅静默覆盖。
- 用 DWT 测量从 DMA 完成到控制任务结束的端到端时延。
- 若采样数据是闭环控制必需数据，丢块必须触发安全策略，而非只增加计数器。

### 案例三：工业设备的紧急故障中断

#### 需求

- 硬件故障输入必须快速关闭功率输出；
- 同时需要收集故障信息并进行复杂诊断；
- 诊断过程不能阻塞紧急关断。

#### 架构设计

```
高紧急度 Fault IRQ
    -> 直接关闭硬件输出或触发安全外设
    -> 记录最小故障快照
    -> 触发低紧急度 deferred IRQ 或任务通知
    -> 诊断任务读取寄存器、记录日志、决定恢复策略
```

#### 设计要点

- 物理安全动作应尽可能由硬件保护路径完成，不依赖普通任务调度。
- 高紧急度 ISR 不调用不允许的 RTOS API。
- 诊断任务不能解除安全锁定，除非状态机和安全条件全部满足。
- 故障快照应先保存到固定 SRAM 区或有校验的数据结构，再执行格式化日志。
- 看门狗不能替代硬件关断路径。

## 12. 高频问题深度答疑

### 1. ISR 是否应该尽可能短？

应该让 ISR 的执行时间**有界且足够短**，但不是为了“短”而省略必要的硬件状态确认。若 ISR 未正确清除中断源，可能立刻重新进入，造成中断风暴。正确目标是：以最小的确定性工作完成硬件服务和软件交接。

### 2. ISR 中可以调用队列发送吗？

只有在 RTOS 提供 ISR-safe 版本，并且当前中断优先级符合内核限制时才可以。ISR 不能等待队列空间；发送失败必须明确处理。数据量大或频率高时，通常使用缓冲区保存数据，再用通知唤醒任务。

### 3. 任务通知一定比队列快吗？

一般来说，目标明确、数据简单的任务通知开销较低，但不能把不同语义混为一谈。通知适合事件、计数或少量标志；队列适合必须逐条传递的消息。若为了快而用通知，却丢失必须保留的事件，优化是错误的。

### 4. 一个通知能否对应多次中断？

可以，但具体取决于使用通知位还是通知计数，以及 RTOS API 的清除规则。通知位通常会合并相同事件；计数通知可以保留次数，但仍受计数范围限制。对于数据流，推荐通知任务后排空缓冲区，不依赖通知次数表示数据条数。

### 5. 为什么 ISR 唤醒了高优先级任务，任务仍没有立即运行？

可能原因包括：

- ISR API 没有正确返回“更高优先级任务已就绪”的状态；
- 忘记使用 ISR 退出让步宏；
- 当前还有更高优先级任务正在运行或就绪；
- 调度器被锁定或在临界区；
- ISR 优先级或 RTOS port 配置不正确；
- 任务优先级设置并不如预期。

应同时测量 ISR 退出点、PendSV、任务第一条指令，而不是只观察 API 返回值。

### 6. ISR 与任务共享变量时，`volatile` 够吗？

通常不够。`volatile` 主要约束编译器对读写的优化，不保证：

- 复合操作原子性；
- 多字段结构一致性；
- CPU 和 DMA 缓存一致性；
- 不同执行上下文间的内存顺序。

应根据数据形态使用原子操作、短临界区、双缓冲、序列锁或 RTOS 同步原语，并检查目标平台对原子宽度和内存屏障的支持。

### 7. 高优先级中断为什么不能调用 RTOS API？

RTOS API 通常需要修改任务状态、等待链或就绪队列。内核通过临界区屏蔽一部分中断来保护这些结构。若一个优先级高于屏蔽门限的 IRQ 仍调用内核 API，它可能在内核数据结构更新到一半时抢占，从而破坏一致性。

### 8. ISR 中能否做一小段协议解析？

要看 WCET、重入、外设时限和系统截止时间，不能仅按代码行数判断。固定长度、常数时间的位提取可能合理；带可变长度循环、校验、回调和复杂状态访问的解析通常应移到任务。必须测量最坏执行时间并纳入所有更低优先级中断的响应分析。

### 9. DMA 完成通知成功是否意味着数据安全可读？

不一定。还需要确认：

- DMA 已停止写该缓冲区；
- 外设状态和 DMA 标志清除顺序正确；
- cache 已按平台规则维护；
- 缓冲区所有权已转移；
- 任务没有读到下一轮 DMA 正在覆盖的数据；
- DMA 描述符和长度已完成同步。

### 10. 中断频率过高时，优先升级处理任务还是优化 ISR？

先确认瓶颈。若 ISR 占用 CPU 过高，应降低中断频率、使用 DMA、批处理或硬件 FIFO。若 ISR 很短但任务队列积压，则要分析消费者服务率、任务优先级和下游处理时间。盲目提高任务优先级可能让系统其他实时路径失效。

## 13. 课程核心总结

### 核心要点

- ISR 是硬件事件的快速响应路径，任务是可阻塞、可调度的业务处理路径。
- ISR 与任务协同的关键在于**正确交接状态、数据和缓冲区所有权**。
- 事件通知可以合并；逐条数据必须有能保留数据本身的缓冲机制。
- ISR-safe API 不等于“可在任意中断优先级调用”。
- DMA、通知和任务之间必须有明确的缓冲区生命周期和 cache 策略。
- 中断实时性需要分析最大屏蔽时间、更高优先级 ISR、ISR WCET、任务调度延迟和队列积压。
- 数据生产速度长期超过消费者速度时，增大缓冲区只能延后溢出，必须处理过载。
- 高可靠故障路径应优先依赖硬件安全机制，任务负责诊断和恢复。

### 常见方案的性能与语义排序

粗略按 ISR 侧开销从低到高：

```
置原子状态/通知位
    <= 任务通知
    < 信号量
    < 固定小消息 ISR 队列
    < 大消息拷贝队列
```

大数据路径通常更适合：

```
DMA + 缓冲区 + 描述符/索引 + 任务通知
```

这不是绝对性能排名。正确性、事件保留语义和目标 RTOS 实现优先于微小的 API 时间差异。

## 14. 快速参考速查表

### 场景选型表

|场景|推荐机制|
|---|---|
|ISR 只报告状态变化|通知位或二值信号量|
|每次事件都必须计数|计数通知或计数信号量|
|必须逐条传递小消息|ISR-safe 固定大小队列|
|高频连续数据|ring buffer + 通知|
|大块外设数据|DMA + 双缓冲/缓冲池|
|最新状态比历史状态重要|快照或双缓冲|
|高紧急度 IRQ 不能调用 RTOS API|原子 mailbox + deferred IRQ|
|外设操作需串行化|资源所有者任务 + 请求队列|

### 特性对比表

|机制|事件可合并|可传数据|拷贝成本|主要限制|
|---|---|---|---|---|
|通知位|是|位标志|极低|不适合逐条事件|
|计数通知|否，计数范围内|计数值|极低|不能承载复杂消息|
|信号量|二值时可合并|否|低|二值语义可能丢次数|
|ISR 队列|通常否|是|固定大小拷贝|队列容量和 ISR 时间|
|Ring buffer|由数据策略决定|是|可无额外消息拷贝|并发模型与溢出策略|
|DMA 双缓冲|按块保留|是|CPU 通常不搬运数据|所有权、cache、块时限|

## 15. 学习效果自检

- [ ]  能画出外设 IRQ 到任务处理完成的完整协同路径。
- [ ]  能解释 Cortex-M 上 PendSV 在任务切换中的作用。
- [ ]  能区分任务 API 和 ISR-safe API。
- [ ]  能说明目标 RTOS 对 ISR 调用 API 的优先级门限。
- [ ]  能判断某个事件是否允许合并，或必须逐次计数。
- [ ]  能设计 ISR 写 ring buffer、任务排空 buffer 的数据通路。
- [ ]  能为 DMA 缓冲区建立完整所有权状态机。
- [ ]  能解释 `volatile`、原子操作、内存屏障和 cache 维护的差异。
- [ ]  能估算 ISR 占用率和缓冲区最低容量。
- [ ]  能识别 ISR 中阻塞、日志、动态分配和复杂解析等风险。
- [ ]  能测量 IRQ 到任务开始运行的延迟和端到端处理时延。
- [ ]  能定义队列满、DMA overrun 和任务过载时的行为。

## 16. 实践与进阶路径

### 16.1 梯度实战任务

1. 编写定时器 ISR，分别使用二值信号量、计数信号量和任务通知唤醒任务，比较事件合并语义。
2. 编写 ISR-safe 队列收发小型固定结构，测试队列满、任务未运行和高优先级唤醒路径。
3. 实现 ISR 单生产者、任务单消费者的 ring buffer，加入溢出计数和高水位统计。
4. 将 UART 中断逐字节处理改为 DMA circular buffer + 任务通知。
5. 实现 DMA 双缓冲所有权状态机，注入任务超时和缓冲区复用故障。
6. 在具有 D-cache 的 MCU 上测量并验证 cache clean/invalidate 流程。
7. 在最坏中断负载下测量 IRQ 响应、ISR WCET、PendSV 开销和任务端到端时延。
8. 模拟中断风暴、任务服务率下降和队列满，验证降级与恢复行为。

### 16.2 性能测试方法

- 使用 DWT `CYCCNT` 或独立硬件定时器打点。
- 在 ISR 入口、ISR 退出、任务第一条指令、处理完成处分别记录时间。
- 使用 GPIO 脉冲和逻辑分析仪测量硬件边沿到任务处理完成的外部时延。
- 在高优先级任务和更高优先级中断同时运行时测量，不只测空载。
- 测量最大值和高分位值，不只报告平均值。
- 记录队列深度、ring buffer 高水位、丢失计数、任务处理时间和 DMA overrun。
- 禁止用同步串口日志作为关键路径计时工具。
- 测试报告包含 MCU、时钟、编译器、优化级别、RTOS 版本、优先级配置和中断负载。

示例打点：

```
void PERIPHERAL_IRQHandler(void)
{
    uint32_t isr_entry_cycle = DWT->CYCCNT;

    clear_peripheral_irq();
    notify_worker_from_isr();

    record_isr_cycles(DWT->CYCCNT - isr_entry_cycle);
}

void worker_task(void *arg)
{
    for (;;) {
        wait_for_notification();

        uint32_t task_start_cycle = DWT->CYCCNT;
        process_pending_data();
        record_task_cycles(DWT->CYCCNT - task_start_cycle);
    }
}
```

### 16.3 进阶方向

- RTOS 的 deferred interrupt 和工作队列实现。
- Cortex-M `BASEPRI`、`PRIMASK`、NVIC 优先级分组及其对 RTOS 临界区的影响。
- DMA 与 D-cache 一致性、MPU non-cacheable 区域和 cache line 对齐。
- 多生产者多消费者队列的无锁算法与内存序。
- 中断响应时间分析、ISR WCET 和固定优先级可调度性分析。
- 高速网络、USB、ADC 和音视频数据通路中的零拷贝架构。
- 中断风暴检测、外设故障隔离和安全关键硬件关断设计。