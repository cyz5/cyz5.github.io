
## 1. 学习目标

### 理解

- 理解死锁的四个必要条件：**互斥、占有且等待、不可剥夺、循环等待**。
- 区分死锁、活锁、饥饿、优先级反转和资源长期占用。
- 理解死锁预防、死锁避免、死锁检测和故障恢复的差异。
- 理解 RTOS 中任务、mutex、队列、事件组、ISR 之间可能形成的等待依赖。

### 掌握

- 掌握全局锁顺序、一次性获取、多资源预留、超时回退等死锁预防方法。
- 掌握等待图、资源分配图和锁依赖图的构建方法。
- 掌握 RTOS 运行时锁监控、超时诊断和任务快照设计。
- 掌握带超时 mutex、try-lock、资源所有者任务和消息传递的使用边界。

### 精通

- 能从任务调用路径、锁顺序和阻塞 API 中定位死锁形成链。
- 能分析嵌套锁、锁超时、任务删除、优先级继承和中断回调之间的复杂交互。
- 能建立可审计的锁依赖矩阵和运行时死锁监测机制。
- 能计算死锁检测和锁监控引入的时间、内存与实时性开销。

### 能够设计

- 能为多任务 RTOS 系统设计无循环等待的资源访问架构。
- 能设计生产级死锁检测、告警、转储和恢复机制。
- 能为关键任务制定“检测后安全降级”策略，而不是简单重启。
- 能通过静态检查、压力测试和故障注入验证死锁风险。

## 2. 前置要求

### 知识要求

- 抢占式固定优先级调度、任务状态和上下文切换。
- mutex、递归 mutex、信号量、事件组、消息队列的同步语义。
- 优先级反转、优先级继承和优先级天花板。
- 中断上下文限制、临界区和原子操作。
- C 语言指针、链表、原子变量和错误处理。

### 技能要求

- 能阅读 RTOS 的 mutex、阻塞、超时和任务调度源码。
- 能绘制任务调用关系图、锁依赖图和资源分配图。
- 能使用 trace、调试器、GPIO 打点或硬件计数器分析任务阻塞。
- 能编写压力测试、故障注入测试和超时路径测试。
- 能检查 ELF map、任务栈高水位和内核对象生命周期。

## 3. 技术概述

### 3.1 死锁定义

**死锁**是指一组任务永久等待彼此持有或依赖的资源，导致这组任务均无法继续执行。

最典型的两个任务场景：

```
任务 A：持有 Lock_A，等待 Lock_B
任务 B：持有 Lock_B，等待 Lock_A
```

如果两个锁都不可被强制夺取，且任务一直保持已持有的锁，则系统进入死锁状态。

### 3.2 死锁的四个必要条件

死锁成立必须同时满足以下四个条件：

|条件|含义|RTOS 中的典型表现|
|---|---|---|
|互斥|资源同一时刻只能由一个任务使用|mutex、独占外设、单个 DMA 通道|
|占有且等待|任务持有资源的同时继续等待其他资源|持有 `SPI_LOCK` 后等待 `LOG_LOCK`|
|不可剥夺|已分配资源不能被系统强制夺走|mutex 不能被其他任务强制释放|
|循环等待|任务形成闭环等待链|A 等 B，B 等 C，C 等 A|

**工程结论**：只要破坏其中任意一个条件，就可以从理论上消除死锁。

### 3.3 相关问题辨析

|问题|任务是否最终能继续|典型原因|主要处理方法|
|---|---|---|---|
|死锁|否|循环等待|锁顺序、超时、检测恢复|
|活锁|可能长期不能有效推进|任务反复让步、重试、回滚|退避、随机抖动、限制重试|
|饥饿|某任务长期得不到资源|优先级或队列策略不公平|公平队列、优先级老化|
|优先级反转|能继续，但高优先级任务被延迟|低优先级持锁，中优先级抢占|PI、PCP、缩短临界区|
|资源泄漏|资源永久不可用|忘记释放、任务异常退出|所有权管理、清理回调、监控|
|长期阻塞|可能最终恢复|外设、队列或硬件等待过长|超时、异步化、状态机|

### 3.4 四类处理策略

```
死锁风险
|
+-- 预防：从设计上破坏必要条件
|
+-- 避免：分配资源前判断是否会进入不安全状态
|
+-- 检测：允许死锁发生，运行时识别等待环
|
+-- 恢复：释放资源、重启任务、复位模块或系统降级
```

- **死锁预防**：工程上最常用，重点是统一锁顺序和限制嵌套锁。
- **死锁避免**：类似银行家算法，要求提前知道资源最大需求，嵌入式实时系统中使用较少。
- **死锁检测**：适合资源关系复杂、需要运行时诊断的系统。
- **死锁恢复**：必须谨慎，错误释放 mutex 可能破坏共享状态。

## 4. 核心特性横向对比

|方案|核心机制|是否允许死锁形成|运行时开销|可证明性|适用场景|
|---|---|---|---|---|---|
|全局锁顺序|所有代码按统一顺序获取锁|否，前提是规则完整执行|极低|高|多任务共享多个短临界区|
|一次性获取|所有资源准备齐后再一次获取|通常否|中|中到高|资源数量固定、锁数量较少|
|try-lock + 回退|获取失败时释放已有资源并重试|可避免循环等待|中到高|中|业务操作可回滚|
|超时锁|等待超过上限后返回|限制永久阻塞，但不保证无死锁|低|中|一般业务路径和诊断|
|资源所有者任务|资源只由一个任务直接操作|基本消除共享锁死锁|队列和调度开销|高|SPI、UART、Flash、文件系统|
|优先级天花板|通过资源上限限制任务调度|可减少锁链问题|中|高|强实时、多资源系统|
|运行时等待图|跟踪任务等待和资源持有关系|允许发生后检测|中到高|高|复杂系统、开发和诊断版本|
|看门狗复位|超时后重启任务或系统|无法预防|极低|低|最后防线，不是根治方案|

### 4.1 预防、避免、检测的区别

|方法|决策时机|依赖信息|典型实现|
|---|---|---|---|
|预防|编码和架构设计阶段|锁顺序、资源关系|锁等级、静态检查|
|避免|资源分配前|任务最大资源需求|安全状态检查|
|检测|运行时|当前持锁和等待状态|等待图环检测|
|恢复|检测到异常后|资源可否安全释放|重启任务、模块复位|

## 5. 底层原理与功能特性深度解析

## 5.1 资源分配图

资源分配图包含两类节点：

- 任务节点：`T1`、`T2`。
- 资源节点：`R1`、`R2`。

边的含义：

```
T1 -> R1：T1 正在等待 R1
R1 -> T1：R1 当前分配给 T1
```

死锁示例：

```
R1 -> T1 -> R2 -> T2 -> R1
```

含义：

```
R1 被 T1 持有
T1 等待 R2
R2 被 T2 持有
T2 等待 R1
```

图中存在环，且每个资源都是单实例不可剥夺资源，因此形成死锁。

## 5.2 等待图

如果每个资源只有一个所有者，可以将资源节点折叠，直接建立任务等待图：

```
T1 -> T2：T1 等待 T2 持有的资源
T2 -> T1：T2 等待 T1 持有的资源
```

此时检测有向图是否存在环即可判断死锁。

### 环检测伪代码

```
typedef enum {
    NODE_UNVISITED = 0,
    NODE_VISITING,
    NODE_VISITED
} node_state_t;

static bool dfs_has_cycle(uint32_t node,
                          const bool graph[MAX_TASKS][MAX_TASKS],
                          node_state_t state[MAX_TASKS])
{
    state[node] = NODE_VISITING;

    for (uint32_t next = 0U; next < MAX_TASKS; ++next) {
        if (!graph[node][next]) {
            continue;
        }

        if (state[next] == NODE_VISITING) {
            return true;
        }

        if ((state[next] == NODE_UNVISITED) &&
            dfs_has_cycle(next, graph, state)) {
            return true;
        }
    }

    state[node] = NODE_VISITED;
    return false;
}

bool wait_graph_has_cycle(const bool graph[MAX_TASKS][MAX_TASKS])
{
    node_state_t state[MAX_TASKS] = { NODE_UNVISITED };

    for (uint32_t i = 0U; i < MAX_TASKS; ++i) {
        if ((state[i] == NODE_UNVISITED) &&
            dfs_has_cycle(i, graph, state)) {
            return true;
        }
    }

    return false;
}
```

这段代码适合诊断任务或离线分析。不要直接在高优先级任务或中断中执行，因为其时间复杂度为：

O(V+E)O(V+E)

其中：

- VV：任务节点数；
- EE：等待关系边数。

生产系统应在低优先级诊断任务中运行，或在记录事件后离线分析。

## 5.3 全局锁顺序

为每把锁分配一个全局等级：

```
enum {
    LOCK_LEVEL_SYSTEM_STATE = 10,
    LOCK_LEVEL_BUS          = 20,
    LOCK_LEVEL_DEVICE       = 30,
    LOCK_LEVEL_LOG          = 40
};
```

规则：

```
只能从低等级锁向高等级锁获取：
SYSTEM_STATE -> BUS -> DEVICE -> LOG
```

禁止：

```
LOG -> BUS
DEVICE -> SYSTEM_STATE
```

### 锁等级检查框架

```
typedef struct {
    const char *name;
    uint16_t level;
} lock_info_t;

typedef struct {
    uint16_t highest_held_level;
    uint32_t held_count;
} task_lock_context_t;

status_t checked_lock(task_lock_context_t *ctx,
                      const lock_info_t *lock,
                      uint32_t timeout_ticks)
{
    if ((ctx == NULL) || (lock == NULL)) {
        return STATUS_INVALID;
    }

    if ((ctx->held_count > 0U) &&
        (lock->level < ctx->highest_held_level)) {
        lock_order_violation_report(lock, ctx);
        return STATUS_LOCK_ORDER;
    }

    if (mutex_lock_timeout(lock, timeout_ticks) != STATUS_OK) {
        return STATUS_TIMEOUT;
    }

    if (ctx->held_count == 0U ||
        lock->level > ctx->highest_held_level) {
        ctx->highest_held_level = lock->level;
    }

    ctx->held_count++;
    return STATUS_OK;
}
```

实际实现需要处理：

- 同一任务重复获取同一锁；
- 递归 mutex；
- 解锁后重新计算当前持有锁的最高等级；
- 锁超时后的状态恢复；
- 任务删除和异常路径清理。

**关键点**：锁顺序检查只能证明“获取顺序没有违反规则”，不能证明临界区内没有其他阻塞，也不能解决任务与 ISR 之间的依赖错误。

## 5.4 一次性获取多个资源

如果任务需要多个资源，可以先按统一顺序检查并获取：

```
status_t acquire_device_resources(device_ctx_t *dev,
                                  uint32_t timeout_ticks)
{
    if (checked_lock(&dev->bus_lock,
                     &dev->lock_ctx,
                     timeout_ticks) != STATUS_OK) {
        return STATUS_TIMEOUT;
    }

    if (checked_lock(&dev->state_lock,
                     &dev->lock_ctx,
                     timeout_ticks) != STATUS_OK) {
        checked_unlock(&dev->bus_lock, &dev->lock_ctx);
        return STATUS_TIMEOUT;
    }

    return STATUS_OK;
}

void release_device_resources(device_ctx_t *dev)
{
    /* 必须严格按获取顺序的逆序释放。 */
    checked_unlock(&dev->state_lock, &dev->lock_ctx);
    checked_unlock(&dev->bus_lock, &dev->lock_ctx);
}
```

注意：

- 一次性获取并不能自动消除锁顺序问题。
- 如果获取第二把锁失败，必须释放已获取的第一把锁。
- 不要在持有部分资源时调用不可预测的阻塞 API。
- 如果锁数量较多，优先考虑资源所有者任务。

## 5.5 try-lock 与回退

当业务操作可以重新执行或回滚时，可以使用非阻塞尝试：

```
status_t update_two_devices(device_ctx_t *a,
                            device_ctx_t *b)
{
    if (mutex_try_lock(&a->lock) != STATUS_OK) {
        return STATUS_BUSY;
    }

    if (mutex_try_lock(&b->lock) != STATUS_OK) {
        mutex_unlock(&a->lock);
        return STATUS_BUSY;
    }

    update_a_and_b(a, b);

    mutex_unlock(&b->lock);
    mutex_unlock(&a->lock);
    return STATUS_OK;
}
```

若任务直接循环重试：

```
while (mutex_try_lock(&lock) != STATUS_OK) {
    task_yield();
}
```

可能产生**活锁**或高 CPU 占用。生产实现应包含：

- 最大重试次数；
- 固定或指数退避；
- 调度让步；
- 随机抖动，避免多个任务同步重试；
- 业务级取消和超时。

```
status_t lock_with_backoff(mutex_t *lock,
                           uint32_t max_attempts)
{
    uint32_t delay_ticks = 1U;

    for (uint32_t i = 0U; i < max_attempts; ++i) {
        if (mutex_try_lock(lock) == STATUS_OK) {
            return STATUS_OK;
        }

        task_delay(delay_ticks);

        if (delay_ticks < 16U) {
            delay_ticks <<= 1U;
        }
    }

    return STATUS_TIMEOUT;
}
```

## 5.6 超时不是死锁预防的完整替代品

带超时锁可以让任务从永久等待中返回：

```
if (mutex_lock_timeout(&resource_lock, 20U) != STATUS_OK) {
    return STATUS_TIMEOUT;
}
```

但超时策略有三个风险：

1. **超时过短**：正常竞争被误判为故障。
2. **超时过长**：任务已经错过截止时间。
3. **超时后状态不一致**：已经完成部分操作，但事务未完成。

超时后的代码必须明确：

```
获取失败 -> 不访问未保护资源
已获取部分锁 -> 逆序释放
操作部分完成 -> 回滚或标记为待恢复
重试 -> 限制次数并避免重试风暴
```

## 5.7 RTOS mutex 的生命周期问题

死锁检测经常忽略对象生命周期。以下情况可能产生类似死锁的永久阻塞：

- 持锁任务被删除；
- mutex 所属模块被卸载；
- 任务异常退出但没有执行清理；
- 任务栈被覆盖导致锁上下文损坏；
- 复位外设后仍有任务等待旧状态；
- mutex 被重复初始化；
- 在 ISR 中释放了不属于当前上下文的资源。

因此，mutex 监控至少应记录：

```
typedef struct {
    const char *name;
    task_handle_t owner;
    uint32_t acquired_tick;
    uint32_t owner_priority;
    uint32_t recursion_count;
    uint32_t wait_count;
    uint32_t max_hold_ticks;
} mutex_debug_info_t;
```

## 5.8 任务删除与锁清理

直接删除持锁任务是危险操作：

```
task_delete(owner_task);
```

如果该任务持有 mutex，其他任务可能永久等待。

推荐方案：

```
请求任务退出
    |
    +-- 设置 stop 标志
    +-- 唤醒任务
    +-- 任务自行停止 I/O
    +-- 释放所有 mutex
    +-- 上报退出状态
    +-- 由管理任务回收任务对象
```

只有在明确支持“持锁任务异常清理”或 robust mutex 语义时，才可设计强制恢复。即使 mutex 被标记为可恢复，共享数据也可能处于半更新状态，必须配合事务状态、版本号或校验和恢复。

## 6. 性能量化分析

以下数据是用于方法说明的可复现实验规格，不应视为所有 MCU 或 RTOS 的固定值。

### 6.1 测试平台

示例测试条件：

- MCU：Cortex-M4F，主频 168 MHz；
- RTOS：带任务 mutex 和超时 API；
- 编译器：`-O2`；
- 时间基准：1 kHz tick；
- 任务数量：8；
- mutex 数量：16；
- 测量工具：DWT `CYCCNT`；
- 测试方法：空载、单任务竞争、双任务竞争、锁顺序检查和等待图扫描。

### 6.2 典型路径测量项目

|操作|示例周期数|168 MHz 下约耗时|
|---|---|---|
|无竞争 mutex 获取与释放|300~700 cycles|1.8~4.2 µs|
|有一个等待者的释放与唤醒|800~1800 cycles|4.8~10.7 µs|
|锁等级检查|30~80 cycles|0.18~0.48 µs|
|记录一次锁等待事件|100~300 cycles|0.6~1.8 µs|
|8 任务等待图扫描|约 1500~4000 cycles|8.9~23.8 µs|
|16 任务等待图扫描|约 5000~12000 cycles|29.8~71.4 µs|

实际值会受以下因素影响：

- RTOS 就绪队列实现；
- 是否启用优先级继承；
- 临界区中断屏蔽时间；
- trace hook 数量；
- cache、Flash wait state；
- 调试日志是否同步输出；
- mutex 等待队列节点分配方式。

### 6.3 内存开销

静态监控方案的近似内存模型：

M≈Mmutex+Mtask+Medge+MeventM≈Mmutex​+Mtask​+Medge​+Mevent​

例如：

- 16 个 mutex，每个监控结构 32 字节：512 字节；
- 8 个任务，每个任务锁上下文 24 字节：192 字节；
- 任务等待矩阵 `8 x 8`，按 `uint8_t` 存储：64 字节；
- 256 条事件记录，每条 24 字节：6144 字节。

总计约：

512+192+64+6144=6912 bytes512+192+64+6144=6912 bytes

如果只保留最新等待事件、不保存完整环形日志，可将监控内存降低到 1 KB 以下。

### 6.4 检测时间复杂度

设：

- TT：任务数；
- RR：资源数；
- EE：当前等待边数。

等待图 DFS 检测复杂度：

O(T+E)O(T+E)

若使用固定大小邻接矩阵，构建和扫描可能接近：

O(T2)O(T2)

资源分配图的边数上限通常为：

E≤T×RE≤T×R

对于典型 MCU 上少量任务和锁，检测成本可控。但不能在每次 `mutex_lock()` 的高优先级路径中对完整图执行复杂遍历。更实用的方法是：

1. 每次锁获取、等待和释放时记录增量事件；
2. 由低优先级诊断任务周期性扫描；
3. 关键任务超时后立即触发快速检查；
4. 在开发版本启用完整检测，量产版本只保留轻量监控。

### 6.5 持锁时间与检测阈值

设：

- 正常最大持锁时间：Hmax⁡Hmax​；
- 调度抖动：JJ；
- 高优先级中断干扰：II；
- 诊断裕量：MM。

锁超时告警阈值可初步设置为：

Hwarn=Hmax⁡+J+I+MHwarn​=Hmax​+J+I+M

例如测得：

- 正常最大持锁时间：200 µs；
- 调度抖动：50 µs；
- 中断干扰：80 µs；
- 诊断裕量：170 µs。

则：

Hwarn=200+50+80+170=500 μsHwarn​=200+50+80+170=500 μs

这只是告警阈值，不是 mutex 等待超时。等待超时还要考虑前方任务排队、优先级继承和任务截止时间。

### 6.6 优化手段与收益

|优化手段|预期收益|风险|
|---|---|---|
|静态分配监控对象|消除监控路径动态分配|需要预估容量|
|事件增量记录|避免每次完整扫描|日志可能丢失上下文|
|位图表示等待关系|减少图存储空间|任务数量受字长影响|
|低优先级异步检测|降低实时路径开销|检测存在延迟|
|分层检测|关键锁实时监控，普通锁周期扫描|架构更复杂|
|只保存最长持锁记录|显著降低 RAM|丢失完整时序|

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
资源是否由多个任务直接共享？
|
+-- 否 --> 采用单一所有者任务，避免共享锁
|
+-- 是
    |
    +-- 是否需要同时持有多把锁？
    |   |
    |   +-- 否 --> 单锁 + 超时 + 持锁时间监控
    |   |
    |   +-- 是
    |       |
    |       +-- 是否能定义全局锁顺序？
    |       |   |
    |       |   +-- 是 --> 锁等级检查 + 静态规则 + 逆序释放
    |       |   |
    |       |   +-- 否 --> 重构资源所有权或使用一次性资源请求
    |       |
    |       +-- 业务操作是否支持回滚？
    |           |
    |           +-- 是 --> try-lock + 回退 + 有限重试
    |           +-- 否 --> 资源所有者任务或事务化设计
    |
    +-- 是否有严格实时截止时间？
        |
        +-- 是 --> 禁止无限阻塞；使用可证明的锁协议和上界分析
        +-- 否 --> 超时 + 运行时检测 + 故障恢复
```

### 7.2 典型场景

|需求|推荐方案|理由|
|---|---|---|
|两个任务访问两个共享状态对象|统一锁等级|成本低、易审计、可静态检查|
|多任务访问 SPI 总线|SPI 所有者任务|避免业务任务嵌套总线锁和设备锁|
|共享配置和状态只需短暂读取|快照、版本号或原子索引|减少锁数量和持锁时间|
|多资源事务必须原子完成|全局锁顺序或事务管理器|防止中途获取失败导致资源半占用|
|开发阶段验证锁关系|运行时等待图|能发现隐藏调用路径中的循环等待|
|高可靠设备|预防 + 检测 + 看门狗|设计缺陷、运行时异常和硬件故障需分层处理|
|ISR 通知任务处理外设|ISR 通知 + 任务队列|避免 ISR 等待 mutex 或参与锁依赖|

## 8. 工程最佳实践

### 8.1 设计原则

1. **优先减少共享资源，而不是增加锁数量**。
2. 所有可阻塞 API 都必须进入阻塞依赖分析。
3. 所有多锁场景必须有书面锁顺序。
4. 锁顺序规则应由代码、静态检查和运行时断言共同约束。
5. 禁止在持有业务 mutex 时调用未知模块函数。
6. 禁止在持锁期间等待队列、信号量、事件、通知或外设完成。
7. 禁止在持锁期间执行可能触发回调的 API，除非回调锁依赖已证明安全。
8. 任务退出必须释放所有资源，不能依赖任务删除自动清理。
9. 超时必须伴随状态恢复策略，不能只返回错误码。
10. 量产版本应保留至少最小化的锁等待和持有时间统计。

### 8.2 选型决策矩阵

|条件|首选方案|必要验证|
|---|---|---|
|单锁、短临界区|mutex + 超时|最大持锁时间|
|多锁、顺序固定|锁等级 + 逆序释放|全调用路径锁顺序|
|多锁、顺序不固定|重构或资源所有者任务|是否真的需要同时持锁|
|操作可回滚|try-lock + 退避|活锁、重试风暴|
|外设事务长|资源所有者任务|队列容量、取消、截止时间|
|高实时性|PCP/PI + 形式化分析|阻塞上界和任务响应时间|
|故障必须可定位|等待图 + 事件记录|RAM、日志完整性|
|故障必须自动恢复|检测 + 模块复位|共享状态一致性和复位边界|

### 8.3 工业级编码规范

- 每把 mutex 必须有唯一名称、保护对象和锁等级。
- 不允许在业务代码中直接调用匿名 `lock()`，应使用带资源名的封装 API。
- 锁获取失败必须区分：超时、顺序违规、对象无效、任务上下文错误。
- 所有锁必须使用逆序释放。
- 不允许通过“强制释放其他任务的 mutex”实现恢复。
- 任务删除前必须检查其持有锁列表。
- 调试构建启用锁依赖断言和等待图；量产构建保留超时计数与最长持锁时间。
- 诊断日志不能在持锁路径中同步输出到慢速串口。
- 锁监控结构必须静态分配或使用受控内存池。
- 对可调用回调的 API，必须明确回调是否允许获取锁。

## 9. 常见错误与避坑指南

### 错误一：两个任务使用相反锁顺序

错误代码：

```
/* 任务 A */
mutex_lock(&bus_lock);
mutex_lock(&device_lock);
update_device();
mutex_unlock(&device_lock);
mutex_unlock(&bus_lock);

/* 任务 B */
mutex_lock(&device_lock);
mutex_lock(&bus_lock);
read_device();
mutex_unlock(&bus_lock);
mutex_unlock(&device_lock);
```

根因：

```
任务 A：持有 bus，等待 device
任务 B：持有 device，等待 bus
```

正确实现：

```
/* 所有任务统一使用 bus -> device */
mutex_lock(&bus_lock);
mutex_lock(&device_lock);

operation();

mutex_unlock(&device_lock);
mutex_unlock(&bus_lock);
```

风险：两个任务可能永久阻塞；优先级继承只能改变任务优先级，不能打破循环等待。

### 错误二：获取第二把锁失败后不释放第一把锁

错误代码：

```
mutex_lock(&state_lock);

if (mutex_lock_timeout(&bus_lock, 10U) != STATUS_OK) {
    return STATUS_TIMEOUT;
}
```

根因：错误路径泄漏了 `state_lock`。

正确实现：

```
status_t operation(device_ctx_t *ctx)
{
    if (mutex_lock_timeout(&ctx->state_lock, 10U) != STATUS_OK) {
        return STATUS_TIMEOUT;
    }

    if (mutex_lock_timeout(&ctx->bus_lock, 10U) != STATUS_OK) {
        mutex_unlock(&ctx->state_lock);
        return STATUS_TIMEOUT;
    }

    do_operation();

    mutex_unlock(&ctx->bus_lock);
    mutex_unlock(&ctx->state_lock);
    return STATUS_OK;
}
```

风险：第一次失败后资源永久被占用，后续任务表现为“全部超时”。

### 错误三：把超时返回误认为已经完成恢复

错误代码：

```
if (mutex_lock_timeout(&config_lock, 20U) != STATUS_OK) {
    config_valid = false;
}

/* 仍然访问受保护数据 */
use_shared_config();
```

根因：获取锁失败后仍访问共享资源。

正确实现：

```
if (mutex_lock_timeout(&config_lock, 20U) != STATUS_OK) {
    record_config_lock_timeout();
    return STATUS_TIMEOUT;
}

config_t local_config = shared_config;
mutex_unlock(&config_lock);

use_config(&local_config);
return STATUS_OK;
```

风险：数据竞争、结构体撕裂、配置版本混用和不可复现故障。

### 错误四：用强制释放 mutex 解除死锁

错误代码：

```
if (lock_timeout()) {
    mutex_force_unlock(&shared_mutex);
}
```

根因：不知道原持锁任务是否正在修改共享对象，也不知道其临界区是否完成。

正确实现：

```
检测到锁异常
    |
    +-- 停止相关业务入口
    +-- 请求持锁任务安全退出
    +-- 等待其释放资源
    +-- 必要时复位整个资源所有者模块
    +-- 使用版本号、校验和或事务日志恢复状态
```

风险：共享数据被半更新，产生比死锁更隐蔽的数据损坏。

### 错误五：在持锁期间调用可能回调的函数

错误代码：

```
mutex_lock(&state_lock);
driver_send_async(buffer, completion_callback);
mutex_unlock(&state_lock);
```

回调可能在驱动任务中执行：

```
void completion_callback(void)
{
    mutex_lock(&state_lock);
    mark_complete();
    mutex_unlock(&state_lock);
}
```

根因：异步驱动回调路径重新获取当前任务或其他任务依赖的锁，造成隐式锁环。

正确实现：

```
mutex_lock(&state_lock);
prepare_transfer(&transfer);
mutex_unlock(&state_lock);

/* 锁外启动异步操作 */
driver_send_async(&transfer, completion_callback);
```

风险：调用关系表面上没有嵌套锁，但运行时通过回调形成循环等待。

### 错误六：无限重试导致活锁

错误代码：

```
for (;;) {
    if (mutex_try_lock(&lock_a) == STATUS_OK) {
        if (mutex_try_lock(&lock_b) == STATUS_OK) {
            break;
        }
        mutex_unlock(&lock_a);
    }

    task_yield();
}
```

根因：多个任务采用完全相同的重试时机，可能反复同时获取、失败、释放。

正确实现：

```
for (uint32_t attempt = 0U; attempt < MAX_RETRY; ++attempt) {
    if (mutex_try_lock(&lock_a) != STATUS_OK) {
        task_delay(backoff_ticks(attempt));
        continue;
    }

    if (mutex_try_lock(&lock_b) == STATUS_OK) {
        perform_operation();
        mutex_unlock(&lock_b);
        mutex_unlock(&lock_a);
        return STATUS_OK;
    }

    mutex_unlock(&lock_a);
    task_delay(backoff_ticks_with_jitter(attempt));
}

return STATUS_BUSY;
```

风险：CPU 占用升高、任务响应抖动、系统吞吐下降。

## 10. 多机制组合使用方案

### 10.1 组合架构

推荐采用四层机制：

```
设计期：
全局锁顺序 + 资源所有权划分 + 静态锁依赖检查
        |
运行期快速路径：
带超时 mutex + 优先级继承 + 锁等级断言
        |
运行期诊断：
持锁时间统计 + 等待事件记录 + 等待图检测
        |
异常恢复：
任务安全退出 + 资源所有者重启 + 模块复位 + 看门狗
```

每层解决不同问题：

|层级|解决问题|
|---|---|
|设计期预防|防止循环等待进入代码|
|快速路径约束|限制正常竞争和优先级反转|
|运行时检测|发现遗漏路径和异常持锁|
|故障恢复|防止单个故障扩散到整个系统|

### 10.2 锁监控框架

```
typedef struct {
    const char *name;
    uint16_t level;
    task_handle_t owner;
    uint32_t acquired_tick;
    uint32_t max_hold_ticks;
    uint32_t wait_count;
    bool held;
} monitored_mutex_t;

typedef struct {
    task_handle_t waiting_task;
    monitored_mutex_t *waiting_lock;
    uint32_t wait_start_tick;
    bool waiting;
} task_wait_state_t;

status_t monitored_lock(monitored_mutex_t *m,
                         task_wait_state_t *wait_state,
                         uint32_t timeout_ticks)
{
    task_handle_t self = task_current();

    if ((m == NULL) || (wait_state == NULL)) {
        return STATUS_INVALID;
    }

    if (lock_order_check(self, m->level) != STATUS_OK) {
        lock_order_violation_report(self, m);
        return STATUS_LOCK_ORDER;
    }

    wait_state->waiting_task = self;
    wait_state->waiting_lock = m;
    wait_state->wait_start_tick = task_tick_count();
    wait_state->waiting = true;

    m->wait_count++;

    status_t result = mutex_lock_timeout(&m->mutex, timeout_ticks);

    wait_state->waiting = false;
    wait_state->waiting_lock = NULL;

    if (result != STATUS_OK) {
        lock_timeout_report(self, m, task_tick_count());
        return result;
    }

    m->owner = self;
    m->acquired_tick = task_tick_count();
    m->held = true;
    return STATUS_OK;
}

status_t monitored_unlock(monitored_mutex_t *m)
{
    task_handle_t self = task_current();

    if ((m == NULL) || !m->held || (m->owner != self)) {
        return STATUS_NOT_OWNER;
    }

    uint32_t held_ticks = task_tick_count() - m->acquired_tick;
    if (held_ticks > m->max_hold_ticks) {
        m->max_hold_ticks = held_ticks;
    }

    m->owner = NULL;
    m->held = false;
    mutex_unlock(&m->mutex);
    return STATUS_OK;
}
```

### 10.3 等待图构建

当任务等待锁 `L`，且 `L.owner` 为任务 `O` 时，记录：

```
waiting_task -> owner_task
```

伪代码：

```
void wait_graph_add(task_handle_t waiting,
                    monitored_mutex_t *lock)
{
    task_handle_t owner = lock->owner;

    if ((owner != NULL) && (owner != waiting)) {
        graph_set_edge(waiting, owner, true);
    }
}

void wait_graph_remove(task_handle_t waiting)
{
    graph_clear_outgoing_edges(waiting);
}
```

检测到环后，系统应记录：

- 环中的任务 ID、任务名和优先级；
- 每个任务持有的锁；
- 每个任务等待的锁；
- 锁持有时间和等待时间；
- 当前 PC、LR 或调用点；
- 任务栈高水位；
- 最近一次调度切换信息。

### 10.4 资源所有者任务方案

对于 SPI、UART、Flash 等慢资源，推荐：

```
业务任务
    |
    +-- 请求队列
            |
            +-- 资源所有者任务
                    |
                    +-- 直接访问硬件
                    +-- 完成通知
                    +-- 超时与错误恢复
```

示例：

```
typedef struct {
    uint32_t client_id;
    const uint8_t *tx;
    uint8_t *rx;
    size_t length;
    uint32_t deadline_ticks;
    completion_event_t *completion;
} bus_request_t;

void bus_owner_task(void *arg)
{
    bus_request_t request;

    for (;;) {
        if (queue_receive(&bus_queue,
                          &request,
                          WAIT_FOREVER) != STATUS_OK) {
            continue;
        }

        if (deadline_expired(request.deadline_ticks)) {
            complete_request(&request, STATUS_TIMEOUT);
            continue;
        }

        status_t result = bus_transfer(request.tx,
                                       request.rx,
                                       request.length);

        complete_request(&request, result);
    }
}
```

该方案的关键不是“把 mutex 换成队列”，而是建立清晰的**资源唯一所有权**：

- 只有所有者任务直接操作硬件；
- 其他任务只能提交请求；
- 请求必须有长度、截止时间、取消和完成语义；
- 队列满时必须定义丢弃、覆盖、降级或阻塞策略。

## 11. 工业级实际案例分析

### 案例一：电机控制器中的双锁死锁

#### 需求

- 电机任务访问控制状态和故障状态。
- 通信任务修改控制参数并写入诊断日志。
- 原始设计存在 `state_lock -> log_lock` 和 `log_lock -> state_lock` 两条路径。

#### 问题链

```
电机任务：持有 state_lock，等待 log_lock
通信任务：持有 log_lock，等待 state_lock
```

#### 设计改进

1. 将日志记录改成无锁事件投递。
2. 电机任务只在锁内生成固定长度日志事件。
3. 日志任务独占输出缓冲区。
4. 对 `state_lock` 保留 PI mutex 和 500 µs 等待告警。

#### 核心代码

```
void motor_fault_report(uint32_t fault_code)
{
    log_event_t event;

    if (mutex_lock_timeout(&state_lock, 2U) != STATUS_OK) {
        fault_monitor_increment(FAULT_STATE_LOCK_TIMEOUT);
        return;
    }

    event.timestamp = system_time_us();
    event.code = fault_code;
    event.state = motor_state_snapshot();
    mutex_unlock(&state_lock);

    /* 锁外投递，避免日志模块反向获取 state_lock。 */
    if (queue_send(&log_queue, &event, 0U) != STATUS_OK) {
        fault_monitor_increment(FAULT_LOG_QUEUE_FULL);
    }
}
```

#### 设计要点

- 锁内只复制数据，不进行格式化和串口输出。
- 日志队列满时不能再次获取状态锁进行复杂错误处理。
- 故障路径也必须遵守普通路径的锁规则。
- 高实时性控制环应优先使用快照或双缓冲，而不是等待日志资源。

### 案例二：共享 SPI 总线与 Flash 存储

#### 需求

- 传感器任务每 1 ms 访问一次 SPI。
- 配置任务偶尔写 Flash。
- 显示任务周期性读取显示控制器。
- Flash 擦除可能持续数十毫秒甚至更久。

#### 原始设计问题

```
传感器任务：bus_lock -> sensor_lock
Flash 任务：flash_lock -> bus_lock
显示任务：display_lock -> bus_lock
```

同时 Flash 擦除在 `bus_lock` 内执行，导致：

- 传感器任务长时间阻塞；
- 其他任务形成多锁等待链；
- 看门狗和采样截止时间可能超时。

#### 改进架构

```
传感器任务 ----+
显示任务 ------+--> SPI 请求队列 --> SPI 所有者任务
Flash 管理任务-+
```

Flash 操作拆成：

```
准备命令 -> 提交硬件操作 -> 释放 SPI -> 等待 Flash 内部完成
```

不要在等待 Flash 内部忙状态期间占用 SPI mutex。

#### 设计要点

- SPI 总线独占时间限制为单次事务，而非整个 Flash 操作。
- 每个请求带截止时间和优先级。
- 高优先级传感器请求不能被无限的显示请求饿死。
- Flash 写入失败后应进入状态机恢复，不应持锁重试。

### 案例三：工业网关中的模块停止与资源回收

#### 需求

网关支持通信模块动态停止。模块任务可能持有 socket、缓存、日志和配置资源。

#### 风险

管理任务直接删除模块任务：

```
task_delete(module_task);
```

模块任务可能在以下路径中：

```
持有 config_lock
等待 network_event
```

直接删除后，`config_lock` 永久保持占用。

#### 改进方案

```
管理任务发送 STOP 请求
    |
模块任务收到 STOP
    |
停止接收新请求
    |
取消网络等待
    |
关闭 socket
    |
释放 cache_lock、config_lock
    |
发送 STOPPED 通知
    |
管理任务回收任务对象
```

#### 核心代码

```
void module_task(void *arg)
{
    module_ctx_t *ctx = arg;

    for (;;) {
        event_t event = wait_module_event(ctx);

        if (event.type == EVENT_STOP) {
            module_stop_io(ctx);

            /* 所有清理动作必须在任务自身上下文完成。 */
            module_release_resources(ctx);
            event_send(ctx->manager, EVENT_STOPPED);
            task_exit();
        }

        module_process_event(ctx, &event);
    }
}
```

#### 设计要点

- 管理任务不得强制删除正常持有资源的任务。
- 停止协议必须有超时。
- 超时后可复位整个模块，而不是强制释放单把 mutex。
- 模块状态必须区分 `RUNNING`、`STOPPING`、`STOPPED`、`FAULTED`。

## 12. 高频问题深度答疑

### 1. 有了 mutex 超时，是否就不需要死锁预防？

不需要。超时只是让任务有机会返回，不能消除循环等待。

例如：

```
A 等待 B，超时后重试
B 等待 A，超时后重试
```

如果重试策略一致，可能变成活锁。正确做法仍是优先建立全局锁顺序，并将超时作为故障检测和降级机制。

### 2. 优先级继承能解决死锁吗？

不能。优先级继承只改变调度优先级，不释放资源，也不改变等待图。

```
A 持有 X，等待 Y
B 持有 Y，等待 X
```

无论 A 或 B 的有效优先级如何提升，循环等待仍然存在。

### 3. 统一按优先级获取锁是否合理？

通常不建议直接按任务优先级决定锁顺序。锁顺序应基于**资源依赖关系**，而不是调用任务当前优先级。

更稳定的规则是：

```
系统状态锁 < 总线锁 < 设备锁 < 日志锁
```

任务优先级可能随 PI 动态变化，不能用它作为长期稳定的资源排序依据。

### 4. 为什么所有 mutex 都使用同一个锁顺序仍可能死锁？

因为死锁依赖可能不只来自 mutex。例如：

```
任务 A：持有 mutex，等待队列消息
任务 B：持有队列关联资源，等待 mutex
```

或者：

```
任务 A：持锁等待 ISR
ISR：等待任务 A 清除状态
```

因此必须把以下关系一起纳入分析：

- mutex；
- 队列；
- 信号量；
- 事件组；
- 任务通知；
- ISR 完成信号；
- 回调；
- 外设忙状态；
- DMA 完成事件。

### 5. 检测到等待图有环后，能否自动释放其中一把锁？

通常不能直接释放。系统并不知道持锁任务是否正在更新：

- 链表；
- 文件系统元数据；
- Flash 缓存；
- 协议状态；
- 引用计数；
- DMA 描述符。

更安全的恢复顺序是：

```
停止相关业务
    -> 请求持锁任务安全退出
    -> 等待资源释放
    -> 恢复事务状态
    -> 必要时复位资源所有者模块
```

只有具备事务回滚或 robust mutex 语义时，才可自动接管资源。

### 6. 死锁检测应该放在量产版本吗？

应保留分层能力：

- 量产版本：锁超时计数、最长持锁时间、任务阻塞快照、故障复位原因。
- 工程版本：完整锁依赖、等待图、调用点、实时断言。
- 现场诊断版本：可通过诊断命令导出当前任务和锁状态。

完整图扫描和详细日志可能影响实时性，因此可采用低优先级异步检测和事件采样。

### 7. 任务被删除后，RTOS 会自动释放 mutex 吗？

不能假设会。不同 RTOS 的行为不同：

- 有的内核不自动释放；
- 有的提供 robust mutex；
- 有的只清理任务等待节点，不清理其持有锁；
- 有的在调试构建中直接触发断言。

必须查看具体 RTOS 版本源码和文档。工程上应避免删除持锁任务，采用协作式退出。

### 8. 如何区分死锁和外设自身长期忙？

需要同时查看：

- 任务是否在等待 mutex；
- mutex 当前所有者是谁；
- 所有者是否在运行、阻塞还是异常退出；
- 任务是否在等待硬件事件；
- 外设状态寄存器是否仍在变化；
- DMA 中断是否丢失；
- 是否存在任务间循环等待。

如果只有一个任务等待外设，且外设状态可恢复，通常是硬件等待故障；如果多个任务形成等待闭环，才是死锁或复合故障。

## 13. 课程核心总结

### 核心要点

- 死锁必须满足**互斥、占有且等待、不可剥夺、循环等待**四个条件。
- 最有效的预防方法是**统一全局锁顺序**，并对其进行静态和运行时检查。
- 超时只能限制无限等待，不能代替锁顺序设计。
- 优先级继承解决优先级反转，不解决循环等待。
- 慢速外设和长事务应采用资源所有者任务，降低共享锁复杂度。
- 死锁检测依赖任务等待关系、资源所有者和阻塞 API 的完整记录。
- 自动恢复不能简单强制释放 mutex，必须考虑共享数据一致性。
- 任务停止应采用协作式退出，避免删除持锁任务。

### 机制性能排序

在一般 Cortex-M RTOS 中，从低运行时开销到高运行时开销大致为：

```
静态锁顺序规则
    < 锁等级运行时检查
    < mutex 超时和持锁统计
    < 事件记录
    < 周期性等待图扫描
    < 完整调用栈、任务快照和故障转储
```

### 通用选型结论

```
短临界区 + 多任务共享
    -> PI mutex + 全局锁顺序 + 超时

长时间外设操作
    -> 资源所有者任务 + 有界请求队列

多锁且能定义顺序
    -> 锁等级检查 + 逆序释放

多锁且不能定义稳定顺序
    -> 重构资源所有权，不要依赖无限重试

高可靠产品
    -> 设计期预防 + 运行时检测 + 协作式恢复 + 看门狗最后防线
```

## 14. 快速参考速查表

### 场景选型表

|场景|推荐方案|关键约束|
|---|---|---|
|单任务访问资源|无锁或单一所有者|明确所有权|
|多任务共享一个短资源|mutex + 超时|限制最大持锁时间|
|多任务共享多把锁|全局锁顺序|严格逆序释放|
|资源获取失败可回滚|try-lock + 回退|限制重试和退避|
|SPI/UART/Flash 长事务|资源所有者任务|请求队列和截止时间|
|复杂锁关系|等待图检测|低优先级异步扫描|
|动态停止任务|协作式退出|任务自行释放资源|
|高可靠系统|预防、检测、恢复组合|记录故障上下文|

### 特性对比表

|机制|预防死锁|检测死锁|运行时开销|是否需要回滚|
|---|---|---|---|---|
|全局锁顺序|是|否|极低|否|
|锁等级检查|是|间接|低|否|
|try-lock|可避免|否|中|通常需要|
|超时 mutex|否，只限制等待|间接|低|视业务而定|
|等待图|否|是|中到高|检测后需要|
|资源所有者任务|基本是|否|队列和调度开销|通常不需要锁回滚|
|看门狗|否|只能发现无响应|极低|通常通过复位恢复|

## 15. 学习效果自检

- [ ]  能说明死锁四个必要条件及其在 RTOS 中的对应对象。
- [ ]  能画出两个任务、两把锁形成的资源分配图。
- [ ]  能区分死锁、活锁、饥饿和优先级反转。
- [ ]  能为系统中的所有 mutex 编制全局锁等级。
- [ ]  能检查多锁路径是否始终按统一顺序获取。
- [ ]  能检查第二把锁获取失败时是否释放第一把锁。
- [ ]  能解释为什么强制释放 mutex 可能破坏共享数据。
- [ ]  能设计任务协作式退出和资源回收流程。
- [ ]  能构建任务等待图并检测环。
- [ ]  能设计至少一个低优先级异步死锁诊断任务。
- [ ]  能测量锁持有时间、等待时间和检测算法开销。
- [ ]  能为死锁检测后的任务、模块和系统恢复定义不同策略。

## 16. 实践与进阶路径

### 16.1 梯度实战任务

1. 创建两个任务和两把 mutex，故意使用相反锁顺序复现死锁。
2. 增加锁等级检查，使锁顺序违规在运行时立即报告。
3. 为每把 mutex 增加持有者、等待者、获取时间和最长持有时间统计。
4. 实现 4 个任务的等待图，并使用 DFS 检测循环等待。
5. 将同步 SPI 访问重构成资源所有者任务，对比 mutex 方案的延迟和抖动。
6. 测试任务安全停止、超时停止、异常复位和资源回收。
7. 通过故障注入模拟：
    - 忘记释放 mutex；
    - 持锁任务卡死；
    - DMA 完成中断丢失；
    - 队列满；
    - 回调反向获取锁；
    - 任务被异常删除。

### 16.2 性能测试方法

测试报告至少包含：

- MCU 型号和主频；
- RTOS 名称、版本和配置；
- 编译器及优化级别；
- 任务数量和优先级；
- mutex 数量和锁依赖关系；
- 空载与竞争负载；
- 锁平均持有时间、最大持有时间；
- 锁平均等待时间、最大等待时间；
- 超时次数和误报次数；
- 等待图扫描周期和最大执行时间；
- 诊断功能引入的中断延迟和任务抖动。

建议在关键位置使用 `DWT->CYCCNT` 或硬件定时器打点：

```
uint32_t start = DWT->CYCCNT;

status_t result = monitored_lock(&resource_lock,
                                 &task_wait_state,
                                 LOCK_TIMEOUT_TICKS);

uint32_t elapsed = DWT->CYCCNT - start;
record_lock_wait_cycles(resource_lock.name, elapsed, result);
```

不要使用同步串口日志测量锁时间，因为日志自身可能引入阻塞、抢占和额外锁依赖。

### 16.3 进阶学习方向

- Priority Ceiling Protocol 与 Stack Resource Policy。
- 实时系统阻塞时间和响应时间分析。
- 多核 RTOS 中的跨核 mutex、缓存一致性和锁竞争。
- Lockdep 类锁依赖验证机制。
- Robust mutex、事务日志和共享状态恢复。
- 无锁队列、内存序和 ABA 问题。
- 基于 trace 的任务等待图重建。
- 模型检测、形式化验证和并发故障注入。
- 安全关键系统中的 deadlock freedom 证明与失效安全设计。