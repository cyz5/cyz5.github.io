
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 ARM 系统控制接口在 SoC 软件栈中的定位。
- 区分 **SMC、HVC、SMCCC、PSCI、SCMI、Mailbox** 的职责边界。
- 理解 EL3 固件、Hypervisor、操作系统、管理处理器之间的调用关系。
- 掌握 ARM 异常级别 EL0～EL3 与系统控制接口的关系。
- 理解 SMC 调用中的寄存器约定、Function ID 编码和返回值语义。

### 掌握

能够：

- 设计 Linux、RTOS、TF-A、OP-TEE、Hypervisor 之间的接口路径。
- 使用 PSCI 完成 CPU 启停、系统关机、系统重启和挂起。
- 使用 SCMI 管理时钟、电源域、复位、性能状态和传感器。
- 正确处理 32 位/64 位调用、SMC/HVC 调用方式和 ABI 兼容性。
- 实现基于共享内存和 Mailbox 的 SCMI 传输层。
- 进行接口延迟、功耗和并发性能分析。

### 精通

能够深入分析：

- TF-A 中 SMC 分发、服务注册和上下文切换机制。
- PSCI CPU_ON、CPU_OFF、CPU_SUSPEND 的状态机与竞态条件。
- SCMI 通道初始化、消息序列化、Token 匹配和超时恢复。
- EL3 受信任服务、OP-TEE、Hypervisor 对系统控制接口的拦截和转发。
- 安全状态、物理地址空间、设备权限和接口暴露面之间的关系。
- Linux cpufreq、cpuidle、clock、reset、regulator 驱动对 SCMI/PSCI 的依赖关系。

### 能够设计

能够设计：

- 工业级异构 SoC 的电源、时钟、复位和性能管理架构。
- Linux + RTOS + EL3 固件共存的系统控制接口。
- 支持多 OS、多安全域、多处理器和故障恢复的 SCMI 平台。
- 具备超时、版本协商、错误隔离、日志追踪和回退策略的控制平面。
- 满足功能安全和安全启动要求的系统控制服务。

---

## 2. 前置要求

### 知识要求

- ARMv7-A 或 ARMv8-A 异常级别和异常向量。
- AArch32/AArch64 寄存器和调用约定。
- MMU、Cache、内存屏障和共享内存一致性。
- 多核启动、CPU 热插拔、低功耗状态。
- Linux Device Tree、驱动模型和电源管理框架。
- RTOS 任务调度、锁、消息队列和中断。
- 基本 TrustZone、Secure/Non-secure 状态知识。
- C 语言指针、结构体、位操作和并发编程。

### 技能要求

- 能够阅读 ARM Architecture Reference Manual。
- 能够阅读 TF-A、U-Boot、Linux ARM64 相关代码。
- 能够使用 JTAG、串口、Trace、ftrace 或 ETM 进行问题定位。
- 能够分析内存映射、设备树和异常寄存器。
- 能够编写跨 EL、跨 CPU 的低级调用代码。
- 能够使用逻辑分析仪或示波器测量控制接口延迟。

---

## 3. 技术概述

## 3.1 系统控制接口的定义

ARM 系统控制接口是一组位于操作系统、固件、Hypervisor 和硬件管理控制器之间的标准化调用协议，用于完成：

- CPU 启停与核间电源管理
- 系统关机、重启和挂起
- 时钟配置
- 电源域控制
- 复位控制
- DVFS 和性能状态管理
- 温度和传感器读取
- 设备电源状态协调
- 安全服务和受信任服务调用

其核心思想是：

> **操作系统不直接修改 SoC 电源、时钟和安全寄存器，而是通过标准接口请求系统控制固件或管理处理器完成操作。**

典型架构如下：

```
+-----------------------------+
| Linux / RTOS / Hypervisor   |
+--------------+--------------+
               |
      SMC / HVC / MMIO
               |
+--------------v--------------+
| EL3 Firmware / SCMI Server  |
| TF-A / Secure Firmware      |
+--------------+--------------+
               |
       Mailbox / Shared Mem
               |
+--------------v--------------+
| SCP / PMIC Controller / MCU |
+--------------+--------------+
               |
+--------------v--------------+
| Clock / Power / Reset / PLL |
+-----------------------------+
```

---

## 3.2 主要接口分类

|接口|主要用途|调用方式|典型实现位置|
|---|---|---|---|
|SMC|Secure Monitor Call，进入 EL3|`SMC` 指令|操作系统到 EL3|
|HVC|Hypervisor Call，进入 EL2|`HVC` 指令|Guest 到 Hypervisor|
|SMCCC|定义 SMC/HVC 的 ABI 和 Function ID|SMC/HVC|ARM 标准调用约定|
|PSCI|CPU、电源、系统级电源状态管理|SMCCC|TF-A、EL3 固件|
|SCMI|时钟、电源域、性能、传感器等系统管理|Mailbox/共享内存|SCP、固件、管理 MCU|
|SDEI|Software Delegated Exception Interface|SMC|固件到 OS 的异步事件|
|FF-A|Secure Partition 与 Normal World 通信|SMC|TF-A、OP-TEE、Hypervisor|
|Mailbox|异步消息传递|MMIO/中断|SoC 内部处理器间通信|
|Device Tree/ACPI|描述接口资源和拓扑|静态描述|Bootloader/固件|

### 核心边界

- **PSCI 解决“处理器和系统电源状态”问题。**
- **SCMI 解决“平台资源管理”问题。**
- **SMCCC 解决“调用 ABI 和约定”问题。**
- **SMC/HVC 是具体的异常指令。**
- **Mailbox/共享内存是 SCMI 等协议的传输机制。**

---

## 3.3 ARM 异常级别与接口路径

AArch64 下通常有以下异常级别：

|异常级别|典型软件|主要职责|
|---|---|---|
|EL0|用户空间程序|非特权应用|
|EL1|Linux Kernel、RTOS|操作系统内核|
|EL2|Hypervisor|虚拟化、Guest 隔离|
|EL3|TF-A、Secure Monitor|安全监控、电源管理、可信服务|

典型路径：

```
Linux EL1
   |
   | SMC #0
   v
TF-A EL3 PSCI Handler
   |
   | 操作 PMU / 电源控制器 / SCP
   v
SoC Hardware
```

虚拟化环境下：

```
Guest OS EL1
   |
   | HVC
   v
Hypervisor EL2
   |
   | SMC 或内部服务
   v
TF-A EL3
```

---

# 4. 核心特性横向对比

## 4.1 SMC、HVC、PSCI、SCMI 对比

|维度|SMC|HVC|PSCI|SCMI|
|---|---|---|---|---|
|类型|指令|指令|功能协议|管理协议|
|目标|EL3|EL2|处理器/系统电源|平台资源|
|是否标准 ABI|通过 SMCCC 标准化|通过 SMCCC 标准化|通过 SMCCC 标准化|协议标准化|
|典型调用|安全服务、电源服务|Guest Hypercall|CPU_ON、SYSTEM_OFF|Clock、Power、Perf|
|同步性|同步|同步|通常同步|同步或异步|
|传输数据|通用寄存器|通用寄存器|通用寄存器|共享内存消息|
|消息规模|小|小|小|较大|
|典型延迟|约 0.5～5 μs|约 0.2～2 μs|约 1～20 μs|约 5～100 μs|
|适用场景|快速安全调用|虚拟化调用|CPU/系统级电源|复杂资源管理|
|主要风险|安全边界错误|虚拟化逃逸|状态机错误|超时、并发和通道错误|

以上延迟是典型 Cortex-A 系统的工程估算范围，不同 SoC、频率、EL3 实现、Mailbox 和管理处理器负载会有明显差异，实际项目必须测量。

## 4.2 PSCI 与 SCMI 的职责对比

|能力|PSCI|SCMI|
|---|---|---|
|CPU 启动|强项|通常不负责|
|CPU 关闭|强项|通常不负责|
|系统关机|强项|通常不负责|
|系统重启|强项|通常不负责|
|CPU Idle|强项|可配合性能状态|
|时钟|非核心职责|强项|
|电源域|非核心职责|强项|
|DVFS|非核心职责|强项|
|传感器|不负责|强项|
|复位|不负责或平台相关|强项|
|复杂消息|不适合|强项|
|跨处理器通信|不适合|强项|

## 4.3 SCMI 传输方式对比

|传输方式|优点|缺点|适用场景|
|---|---|---|---|
|Doorbell + Shared Memory|延迟低、消息容量大|需要处理一致性和并发|高性能 SCP 管理|
|MMIO Mailbox|简单、硬件支持广|访问慢、消息容量有限|小型 SoC|
|Interrupt + Shared Memory|异步能力强|中断配置复杂|电源、性能事件|
|Polling|实现简单|占用 CPU、实时性差|启动阶段或调试|
|VirtIO/虚拟 SCMI|虚拟化友好|多一层转发开销|VM 环境|

---

# 5. 底层原理与功能特性深度解析

## 5.1 SMCCC Function ID 编码

SMCCC Function ID 通常包含以下字段：

```
31            30 29 28 27             24 23                  16 15       0
+---------------+--+--+----------------+----------------------+----------+
| Call Type     |O |64|   Convention    |     Owner            | Function |
+---------------+--+--+----------------+----------------------+----------+
```

常见含义：

- Bit 31：是否为快速调用
- Bit 30：调用类型，SMC 或 HVC
- Bit 29：是否为 64 位调用
- Owner：服务拥有者，例如 Standard Service、Trusted OS
- Function：具体功能号

在 TF-A 中常见宏：

```
#define SMC_TYPE_FAST              0U
#define SMC_TYPE_YIELDING          1U
#define SMC_64                      1U
#define SMC_32                      0U

#define OEN_STD_START               0U
#define OEN_STD_END                 0x3FU
#define OEN_TOS_START               0x32U
```

实际项目中不应手工拼接魔数，应使用统一宏：

```
#define ARM_SMCCC_CALL_VAL(type, calling_convention, owner, func) \
    (((type) << 31) | ((calling_convention) << 30) | \
     ((owner) << 24) | (func))

#define ARM_SMCCC_FAST_CALL \
    (0U << 31)

#define ARM_SMCCC_SMC_64 \
    (1U << 30)

#define ARM_SMCCC_OWNER_STANDARD \
    4U

#define PSCI_FN_CPU_ON \
    0x03U

#define PSCI_CPU_ON64 \
    (ARM_SMCCC_FAST_CALL | ARM_SMCCC_SMC_64 | \
     (ARM_SMCCC_OWNER_STANDARD << 24) | PSCI_FN_CPU_ON)
```

注意：具体宏定义应优先使用平台已有的 Linux、TF-A 或 CMSIS 头文件，避免不同组件之间 Function ID 不一致。

---

## 5.2 SMC 指令调用机制

AArch64 下，调用参数通常放入 `x0～x7`：

```
static inline void smc_call(struct smc_args *args)
{
    __asm__ volatile (
        "smc    #0"
        : "+r"(args->x0), "+r"(args->x1),
          "+r"(args->x2), "+r"(args->x3),
          "+r"(args->x4), "+r"(args->x5),
          "+r"(args->x6), "+r"(args->x7)
        :
        : "memory"
    );
}
```

生产代码需要注意：

1. `memory` clobber 防止编译器重排共享内存访问。
2. SMC 之前必须完成共享数据写入。
3. 如果参数指向共享内存，必须满足缓存一致性要求。
4. 不应把未经验证的用户指针直接传入安全世界。
5. 需要正确保存调用者上下文。
6. SMC 返回后必须检查错误码，而不是只判断 `x0 == 0`。

推荐封装：

```
struct smc_result {
    uint64_t a0;
    uint64_t a1;
    uint64_t a2;
    uint64_t a3;
};

static inline struct smc_result smc_invoke(
    uint64_t fid,
    uint64_t a1,
    uint64_t a2,
    uint64_t a3,
    uint64_t a4)
{
    register uint64_t x0 __asm__("x0") = fid;
    register uint64_t x1 __asm__("x1") = a1;
    register uint64_t x2 __asm__("x2") = a2;
    register uint64_t x3 __asm__("x3") = a3;
    register uint64_t x4 __asm__("x4") = a4;

    __asm__ volatile (
        "smc #0"
        : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3), "+r"(x4)
        :
        : "x5", "x6", "x7", "memory"
    );

    return (struct smc_result) {
        .a0 = x0,
        .a1 = x1,
        .a2 = x2,
        .a3 = x3,
    };
}
```

---

## 5.3 快速调用与 Yielding 调用

### Fast Call

Fast Call 通常不允许被抢占，适合：

- 读取固件版本
- 设置少量寄存器
- 电源状态查询
- 高优先级、短执行时间服务

特点：

- 预期执行时间短
- 不能执行长时间阻塞操作
- 一般不应等待慢速外设
- 对实时性影响较小

### Yielding Call

Yielding Call 允许调用过程中让出 CPU，适合：

- 等待安全世界资源
- OP-TEE 长事务
- 复杂的安全服务
- 需要异步完成的操作

错误设计示例：

```
/* 错误：把可能等待数百微秒甚至毫秒的操作定义成 Fast Call */
uint64_t fast_flash_erase(void)
{
    return secure_flash_erase();  /* 可能阻塞 */
}
```

正确方法是：

- 使用 Yielding Call；
- 或者由固件启动异步操作，调用方轮询/等待完成；
- 对操作设置明确超时。

---

## 5.4 PSCI 核心功能

PSCI 常见接口：

|PSCI 接口|功能|
|---|---|
|`PSCI_VERSION`|查询 PSCI 版本|
|`CPU_SUSPEND`|当前 CPU 进入低功耗|
|`CPU_OFF`|当前 CPU 关闭|
|`CPU_ON`|启动指定 CPU|
|`AFFINITY_INFO`|查询 CPU Affinity 状态|
|`MIGRATE`|迁移 Trusted OS 上下文|
|`SYSTEM_OFF`|系统关机|
|`SYSTEM_RESET`|系统重启|
|`FEATURES`|查询功能支持情况|
|`MEM_PROTECT`|内存保护相关功能|

### CPU_ON 基本逻辑

```
目标 CPU 当前状态
    |
    +-- ON        -> 返回 ALREADY_ON
    +-- ON_PENDING-> 返回 ON_PENDING
    +-- OFF       -> 设置启动地址和上下文
                         |
                         +-- 打开电源
                         +-- 释放复位
                         +-- 设置入口地址
                         +-- 唤醒目标 CPU
                         +-- 目标 CPU 进入初始化
```

伪代码：

```
int psci_cpu_on(uint64_t target_cpu,
                uint64_t entry,
                uint64_t context_id)
{
    if (!cpu_id_valid(target_cpu))
        return PSCI_E_INVALID_PARAMS;

    if (!entry_is_valid(entry))
        return PSCI_E_INVALID_ADDRESS;

    lock(&cpu_state_lock[target_cpu]);

    if (cpu_state[target_cpu] == CPU_ON)
        goto already_on;

    if (cpu_state[target_cpu] == CPU_ON_PENDING)
        goto pending;

    cpu_state[target_cpu] = CPU_ON_PENDING;
    cpu_boot_context[target_cpu].entry = entry;
    cpu_boot_context[target_cpu].context_id = context_id;

    ret = platform_power_on_cpu(target_cpu);
    if (ret != 0) {
        cpu_state[target_cpu] = CPU_OFF;
        unlock(&cpu_state_lock[target_cpu]);
        return PSCI_E_INTERNAL_FAILURE;
    }

    unlock(&cpu_state_lock[target_cpu]);
    return PSCI_E_SUCCESS;

already_on:
    unlock(&cpu_state_lock[target_cpu]);
    return PSCI_E_ALREADY_ON;

pending:
    unlock(&cpu_state_lock[target_cpu]);
    return PSCI_E_ON_PENDING;
}
```

工程关键点：

- CPU 状态必须是**显式状态机**，不能仅依赖硬件寄存器。
- `CPU_ON` 必须防止重复启动。
- 目标 CPU 的启动参数需要内存屏障保证可见性。
- 电源打开、复位释放、入口地址设置顺序不能颠倒。
- 启动失败后必须回滚软件状态。

---

## 5.5 SCMI 架构

SCMI 通常分成三层：

```
+-----------------------------+
| SCMI Protocol Layer         |
| Base / Clock / Power / Perf |
+-----------------------------+
| SCMI Transport Layer        |
| Shared Memory / Mailbox     |
+-----------------------------+
| Platform Layer              |
| SCP Firmware / Hardware     |
+-----------------------------+
```

常见协议：

|协议|主要功能|
|---|---|
|Base|版本、协议发现、通知和权限|
|Clock|时钟数量、状态、频率|
|Power Domain|电源域开关、状态|
|Performance|DVFS、OPP、性能级别|
|Sensor|温度、电压、电流等|
|Reset Domain|复位控制|
|Voltage|电压设置|
|System Power|系统关机、重启等|
|pin control|引脚控制，取决于实现版本|

---

## 5.6 SCMI 共享内存消息结构

典型共享内存区域包括：

```
struct scmi_shared_mem {
    uint32_t reserved0;
    uint32_t channel_status;
    uint32_t reserved1;
    uint32_t flags;
    uint32_t length;
    uint32_t message_header;
    uint8_t  payload[];
};
```

实现时必须注意：

- `length` 是协议定义的消息长度，不是整个缓冲区长度。
- `message_header` 包含协议 ID、消息 ID 和 Token。
- 共享内存必须满足对齐要求。
- 发送前应清理 Cache，接收后应失效 Cache，具体取决于内存属性和一致性域。
- 发送和接收缓冲区应避免并发复用。
- 同一通道上必须正确匹配 Token。

典型消息流程：

```
Client:
  1. 获取空闲通道
  2. 构造 Header
  3. 写入 Payload
  4. 写入 Length
  5. DMB/DSB
  6. Doorbell/发送中断
  7. 等待完成中断
  8. 读取响应
  9. 校验 Token、长度和状态
```

示例框架：

```
int scmi_xfer(struct scmi_channel *ch,
              uint8_t protocol_id,
              uint8_t message_id,
              const void *tx,
              size_t tx_len,
              void *rx,
              size_t rx_capacity,
              uint32_t timeout_us)
{
    struct scmi_shared_mem *mem;
    uint16_t token;
    uint32_t header;
    int ret;

    if (ch == NULL || ch->shmem == NULL)
        return -EINVAL;

    if (tx_len > ch->tx_max_payload ||
        rx_capacity > ch->rx_max_payload)
        return -EMSGSIZE;

    ret = channel_acquire(ch, timeout_us);
    if (ret != 0)
        return ret;

    token = channel_next_token(ch);

    header = SCMI_HEADER(protocol_id, message_id, token);

    mem = ch->shmem;

    memcpy(mem->payload, tx, tx_len);
    mem->message_header = header;
    mem->length = sizeof(header) + tx_len;

    /* 确保共享内存内容先于 Doorbell 对端可见 */
    dsb_sy();
    mailbox_ring(ch->mailbox);

    ret = channel_wait_complete(ch, timeout_us);
    if (ret != 0)
        goto out_release;

    /* 防止读取缓存中的旧响应 */
    dmb_sy();

    if (mem->message_header != header) {
        ret = -EPROTO;
        goto out_release;
    }

    if (mem->length < sizeof(uint32_t) ||
        mem->length - sizeof(uint32_t) > rx_capacity) {
        ret = -EMSGSIZE;
        goto out_release;
    }

    memcpy(rx,
           mem->payload,
           mem->length - sizeof(uint32_t));

    ret = 0;

out_release:
    channel_release(ch);
    return ret;
}
```

---

## 5.7 SCMI Token 与并发控制

Token 的作用是识别请求与响应的对应关系。

错误实现：

```
/* 错误：所有请求固定使用 Token 0 */
header = SCMI_HEADER(protocol_id, message_id, 0);
```

风险：

- 并发请求响应错配；
- 一个请求超时后，迟到响应污染下一个请求；
- 导致时钟、功耗和 DVFS 状态异常。

正确方案：

```
static uint16_t alloc_token(struct scmi_channel *ch)
{
    uint16_t token;

    do {
        token = ++ch->next_token;
        token &= SCMI_TOKEN_MASK;
    } while (token == 0 || token_in_use(ch, token));

    bitmap_set(ch->token_bitmap, token);
    return token;
}
```

如果硬件通道只支持单 outstanding transaction，则必须：

- 使用互斥锁；
- 禁止递归发送；
- 中断回调中不能再次同步调用同一通道；
- 设置明确超时和通道复位机制。

---

## 5.8 电源域控制与引用计数

共享电源域必须采用引用计数或所有权模型。

```
struct power_domain {
    mutex_t lock;
    uint32_t users;
    bool hw_on;
};

int power_domain_get(struct power_domain *pd)
{
    int ret = 0;

    mutex_lock(&pd->lock);

    if (pd->users == 0) {
        ret = scmi_power_state_set(pd->id, SCMI_POWER_STATE_ON);
        if (ret != 0)
            goto out;
        pd->hw_on = true;
    }

    pd->users++;

out:
    mutex_unlock(&pd->lock);
    return ret;
}

int power_domain_put(struct power_domain *pd)
{
    int ret = 0;

    mutex_lock(&pd->lock);

    if (pd->users == 0) {
        ret = -EINVAL;
        goto out;
    }

    pd->users--;

    if (pd->users == 0) {
        ret = scmi_power_state_set(pd->id, SCMI_POWER_STATE_OFF);
        if (ret == 0)
            pd->hw_on = false;
    }

out:
    mutex_unlock(&pd->lock);
    return ret;
}
```

生产系统中还需要考虑：

- 子设备和父电源域的拓扑依赖；
- 异步关闭；
- 关闭失败后的状态回读；
- 电源域状态通知；
- suspend/resume 期间的引用冻结；
- 崩溃恢复后的引用重建。

---

# 6. 性能量化分析

## 6.1 实测平台定义

下面给出一个可复现实验模型：

- CPU：Cortex-A55，1.2 GHz
- EL3：TF-A，Release 构建
- OS：Linux 6.x
- SCP：Cortex-M33，200 MHz
- Mailbox：MMIO Doorbell + 共享内存
- Cache：L1/L2 开启
- 内存：DDR4
- 测量工具：Generic Timer、PMU cycle counter、GPIO 翻转

注意：以下数据是典型工程测量范围和计算示例，不代表所有平台的固定结果。

## 6.2 调用延迟

|操作|典型延迟|
|---|---|
|普通 C 函数|10～50 ns|
|SMC 快速调用，无硬件操作|0.5～2 μs|
|PSCI CPU 状态查询|1～5 μs|
|PSCI SYSTEM_RESET|不适用，调用后系统重启|
|SCMI 共享内存请求，SCP 空闲|5～20 μs|
|SCMI 时钟设置，包含 PLL 锁定|20 μs～2 ms|
|SCMI 电源域上电|50 μs～10 ms|
|CPU 冷启动|0.5～20 ms|

### 延迟计算

ARM Generic Timer 频率为 `f_timer`，读取起止计数值：

```
T_us = (cnt_end - cnt_begin) × 10^6 / f_timer
```

例如：

```
f_timer = 24 MHz
delta_cnt = 384
T = 384 × 10^6 / 24 × 10^6 = 16 μs
```

## 6.3 SCMI 内存开销

典型开销：

|项目|估算|
|---|---|
|一个共享内存通道|128～4 KB|
|每个同步事务对象|64～256 B|
|Token 位图|8～128 B|
|协议设备对象|1～8 KB|
|时钟描述表|每时钟 16～64 B|
|性能状态表|每 OPP 16～64 B|

如果系统有：

- 4 个通道；
- 每个通道 1 KB；
- 80 个时钟；
- 20 个 OPP；

则静态内存约为：

```
通道内存 = 4 × 1 KB = 4 KB
时钟表   = 80 × 32 B = 2.5 KB
OPP 表    = 20 × 32 B = 640 B
控制对象  ≈ 8 KB
总计      ≈ 15 KB～25 KB
```

## 6.4 瓶颈分析

### 瓶颈一：Mailbox 往返延迟

如果每次调频都通过 SCMI 发送同步请求：

```
总耗时 = 请求构造 + Doorbell + 中断往返 + SCP 执行 + 响应解析
```

频繁调频时，协议开销可能超过实际寄存器配置时间。

优化方式：

- 批量设置；
- 设置性能级别而不是频率；
- 在 SCP 侧缓存状态；
- 避免重复设置当前值；
- 将高频查询改成本地缓存或通知机制。

### 瓶颈二：锁竞争

单通道串行化会造成：

```
多个客户端
   |
   v
同一 SCMI Mutex
   |
   v
请求排队
```

优化方式：

- 使用命令通道和通知通道分离；
- 不同协议使用不同通道；
- 允许多个 outstanding transaction；
- 采用 wait queue 替代忙等待。

### 瓶颈三：低功耗状态切换

电源域开关的主要耗时通常不在 SMC/SCMI，而在：

- PMIC 响应；
- 电压爬升；
- PLL 锁定；
- SRAM retention；
- 时钟稳定时间；
- 外设状态保存与恢复。

因此不能只优化接口指令，而忽略硬件状态转换时间。

## 6.5 优化收益示例

|优化措施|优化前|优化后|收益|
|---|---|---|---|
|去除重复 Clock Set|100 次/秒|20 次/秒|请求量下降 80%|
|查询结果缓存|15 μs/次|0.1 μs/次|约 150 倍|
|独立通知通道|竞争 40 μs|竞争 8 μs|降低 80%|
|Token 位图替代线性扫描|2 μs|0.1 μs|降低 95%|
|中断替代轮询|CPU 占用 3%|<0.2%|显著降低功耗|

---

# 7. 应用场景选型指南

## 7.1 决策流程图

```
是否需要 CPU 启停、系统关机或系统重启？
├─ 是
│  └─ 使用 PSCI，通过 SMCCC 暴露
└─ 否
   |
   是否需要访问 EL3 安全服务？
   ├─ 是
   │  └─ 使用 SMC + SMCCC，自定义 Trusted Service
   └─ 否
      |
      是否需要访问 EL2 Hypervisor 服务？
      ├─ 是
      │  └─ 使用 HVC + SMCCC
      └─ 否
         |
         是否管理时钟、电源域、DVFS、传感器或复位？
         ├─ 是
         │  └─ 使用 SCMI
         └─ 否
            |
            是否存在异构处理器或管理 MCU？
            ├─ 是
            │  └─ Mailbox + Shared Memory + SCMI
            └─ 否
               └─ 可使用本地 MMIO，但需评估可移植性和安全边界
```

## 7.2 典型场景

|场景需求|方案|理由|
|---|---|---|
|Linux 启动 CPU2|PSCI CPU_ON|标准化、由固件统一控制|
|Android 系统重启|PSCI SYSTEM_RESET|OS 不直接操作复位寄存器|
|Linux cpufreq 调频|SCMI Performance|支持复杂 DVFS 和平台策略|
|GPU 电源域控制|SCMI Power Domain|支持共享资源和状态管理|
|Linux 访问安全密钥服务|SMC Trusted Service|进入安全世界|
|Guest Linux 关闭虚拟 CPU|HVC 到 Hypervisor|Guest 不应直接访问 EL3|
|SCP 管理 PLL 和 PMIC|SCMI + Mailbox|适合复杂异步平台资源管理|
|快速读取芯片唯一 ID|Fast SMC|小参数、短执行时间|
|温度变化通知|SCMI Sensor Notification|避免高频轮询|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：职责分层

不要让 Linux 直接操作：

- PMIC 寄存器；
- 关键 PLL；
- 安全电源控制器；
- 其他 CPU 的复位控制；
- Secure World 资源。

应通过 PSCI/SCMI 进行抽象。

### 原则二：接口必须版本化

启动时执行：

```
SCMI_BASE_PROTOCOL_VERSION
SCMI_BASE_PROTOCOL_ATTRIBUTES
SCMI_BASE_DISCOVER_LIST_PROTOCOLS
SCMI_BASE_PROTOCOL_MESSAGE_ATTRIBUTES
```

根据协商结果启用功能，不能假设固件永远支持某个协议。

### 原则三：所有同步请求必须有超时

不能使用无限等待：

```
while (!response_ready)
    ;
```

必须使用：

```
ret = wait_for_completion_timeout(&xfer->done,
                                  timeout_us);
if (ret != 0)
    return ret;
```

### 原则四：状态必须通过回读确认

发送 `POWER_STATE_SET(ON)` 后，不应直接假定硬件已上电。必要时执行：

```
SET -> WAIT -> GET -> VERIFY
```

### 原则五：失败后进行通道恢复

超时后应：

1. 禁止继续发送；
2. 记录当前 Token；
3. 读取通道状态；
4. 清除 Doorbell；
5. 重置共享内存；
6. 重新初始化 Mailbox；
7. 上报故障；
8. 必要时触发平台级恢复。

## 8.2 选型决策矩阵

|需求|本地 MMIO|SMC|PSCI|SCMI|
|---|---|---|---|---|
|低延迟|高|中|中|低|
|跨 OS 一致性|低|高|高|高|
|安全隔离|低|高|高|高|
|复杂参数|中|低|低|高|
|跨处理器|低|中|中|高|
|平台可移植性|低|高|高|高|
|实现复杂度|低|中|中|高|
|资源动态管理|低|低|低|高|

## 8.3 工业级编码规范

- 所有 Function ID 使用命名宏。
- 所有返回值使用统一错误码转换函数。
- 禁止在中断上下文中执行不可控时长的同步 SCMI 请求。
- 禁止把共享内存结构体直接作为跨编译器 ABI，必须明确字段宽度和字节序。
- 禁止依赖 C bit-field 作为协议格式。
- 所有共享内存操作明确 Cache 和内存屏障策略。
- 所有通道支持统计：请求数、超时数、错误数、最大延迟、平均延迟。
- 所有协议版本和固件版本写入启动日志。
- 所有平台相关代码隔离在 `platform/` 层。
- 不允许驱动层直接调用底层 Mailbox 寄存器。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：把 SCMI 消息长度填写错误

### 错误代码

```
mem->length = sizeof(struct scmi_shared_mem);
```

### 根因

`length` 表示当前消息有效长度，而不是共享内存缓冲区总大小。

### 正确实现

```
mem->length = sizeof(uint32_t) + payload_len;
```

### 风险影响

- 对端解析越界；
- 响应被判定为非法；
- 不同固件版本间出现兼容性问题；
- 可能产生安全边界绕过。

---

## 9.2 错误二：忽略 Cache 一致性

### 错误代码

```
memcpy(shmem->payload, request, len);
mailbox_ring();
```

### 根因

CPU Cache 中的数据尚未写回共享内存，SCP 读取到旧数据。

### 正确实现

```
memcpy(shmem->payload, request, len);
clean_cache(shmem, sizeof_header + len);
dsb_sy();
mailbox_ring();
```

接收时：

```
wait_irq();
invalidate_cache(shmem, response_len);
dmb_sy();
parse_response(shmem);
```

### 风险影响

- 偶发错误；
- 与负载、CPU 频率和 Cache 状态相关；
- 难以复现；
- 可能表现为“固件随机失效”。

---

## 9.3 错误三：无限等待 SCMI 响应

### 错误代码

```
while (ch->state != SCMI_COMPLETE)
    cpu_relax();
```

### 根因

没有考虑：

- SCP 崩溃；
- Mailbox 中断丢失；
- 电源域关闭导致响应无法返回；
- 通道状态损坏。

### 正确实现

```
ret = wait_event_timeout(ch->waitq,
                         ch->state == SCMI_COMPLETE,
                         usec_to_ticks(timeout_us));

if (ret == 0) {
    scmi_channel_abort(ch);
    return -ETIMEDOUT;
}
```

### 风险影响

- 内核线程永久阻塞；
- suspend/resume 死锁；
- 看门狗复位；
- 整机不可恢复。

---

## 9.4 错误四：CPU_ON 缺少状态锁

### 错误代码

```
if (!cpu_is_on(cpu)) {
    power_on_cpu(cpu);
    release_cpu_reset(cpu);
}
```

### 根因

两个 CPU 或两个线程可能同时执行 CPU_ON。

### 正确实现

```
lock(&cpu_state_lock[cpu]);

if (cpu_state[cpu] == CPU_ON) {
    ret = PSCI_E_ALREADY_ON;
    goto out;
}

if (cpu_state[cpu] == CPU_ON_PENDING) {
    ret = PSCI_E_ON_PENDING;
    goto out;
}

cpu_state[cpu] = CPU_ON_PENDING;
ret = platform_cpu_on(cpu);

if (ret != 0)
    cpu_state[cpu] = CPU_OFF;

out:
unlock(&cpu_state_lock[cpu]);
```

### 风险影响

- 目标 CPU 重复释放复位；
- 启动地址被覆盖；
- 多核启动随机失败；
- 破坏电源状态机。

---

## 9.5 错误五：将长耗时服务定义为 Fast Call

### 错误代码

```
/* Fast SMC 中直接等待 PMIC */
uint64_t secure_power_on(void)
{
    while (!pmic_ready())
        ;
    return 0;
}
```

### 根因

Fast Call 的语义要求短、不可长时间阻塞。

### 正确实现

- 快速调用只提交请求；
- 通过异步机制完成；
- 或使用 Yielding Call；
- 设置超时和错误回滚。

### 风险影响

- EL3 长时间占用；
- 其他 CPU 无法进入关键安全服务；
- 看门狗超时；
- 系统实时性崩溃。

---

# 10. 多机制组合使用方案

## 10.1 推荐组合架构

```
Linux EL1
├── PSCI Driver
│   └── SMC/HVC -> TF-A EL3
├── SCMI Clock Driver
├── SCMI Power Driver
├── SCMI Perf Driver
└── SCMI Sensor Driver
        |
        v
SCMI Transport
├── Shared Memory
├── Mailbox
└── Interrupt
        |
        v
SCP Firmware
├── Clock Manager
├── Power Manager
├── DVFS Manager
├── Thermal Manager
└── Fault Recovery
```

### 组合职责

- **PSCI**：CPU 和系统级状态。
- **SCMI**：平台资源状态。
- **SMC/SMCCC**：把 PSCI 或安全服务暴露给 OS。
- **Mailbox**：把 SCMI 请求发送到 SCP。
- **共享内存**：承载复杂请求和响应。
- **通知机制**：异步传递温度、性能和故障事件。

## 10.2 完整控制框架

```
struct system_control {
    struct psci_ops psci;
    struct scmi_channel scmi;
    struct power_domain cpu_pd;
    struct clock_manager clocks;
    struct perf_manager perf;
};

int system_device_enable(struct system_control *sys,
                         uint32_t dev_id,
                         uint32_t clk_id)
{
    int ret;

    ret = power_domain_get(&sys->cpu_pd);
    if (ret != 0)
        return ret;

    ret = scmi_clock_enable(&sys->scmi, clk_id);
    if (ret != 0)
        goto rollback_power;

    ret = device_runtime_init(dev_id);
    if (ret != 0)
        goto rollback_clock;

    return 0;

rollback_clock:
    scmi_clock_disable(&sys->scmi, clk_id);
rollback_power:
    power_domain_put(&sys->cpu_pd);
    return ret;
}
```

这是典型的**分层资源获取 + 失败回滚**模式。

---

# 11. 工业级实际案例分析

## 11.1 案例一：汽车域控制器的异构电源管理

### 需求

- Cortex-A 主控运行 Linux；
- Cortex-R 运行实时控制任务；
- Cortex-M SCP 管理 PMIC、PLL 和外设电源；
- 支持运行时 DVFS、睡眠和唤醒；
- 关键控制域不能被 Linux 直接关闭。

### 架构

```
Linux
  |
  +-- PSCI -> EL3 -> CPU Power Controller
  |
  +-- SCMI -> Mailbox -> SCP
                       |
                       +-- PMIC
                       +-- PLL
                       +-- Power Domain
                       +-- Thermal
```

### 设计要点

- Cortex-R 安全控制域设置为 SCMI 权限只读。
- Linux 的 SCMI 请求由 SCP 进行资源权限校验。
- CPU 深度睡眠由 PSCI 协调，避免 Linux 和 SCP 分别控制同一电源域。
- 所有 DVFS 调整必须受温度和电压约束。
- SCP 看门狗异常后，EL3 负责恢复最低安全状态。

### 核心代码

```
int dvfs_set_level(struct scmi_perf *perf,
                   uint32_t domain,
                   uint32_t level)
{
    uint32_t max_level;
    int ret;

    ret = scmi_perf_level_get(perf, domain, &max_level);
    if (ret != 0)
        return ret;

    if (level > max_level)
        return -ERANGE;

    ret = scmi_perf_level_set(perf, domain, level);
    if (ret != 0)
        return ret;

    return scmi_perf_wait_transition(perf, domain, 5000);
}
```

---

## 11.2 案例二：服务器 ARMv8 平台 CPU 热插拔

### 需求

- 64 核 Neoverse 平台；
- Linux 支持 CPU offline/online；
- CPU 核心和簇级电源状态由 EL3 管理；
- 不能影响其他核的 L3 Cache 和共享电源域。

### 关键状态

```
CPU_ON
CPU_ON_PENDING
CPU_ON_FAILED
CPU_ON
CPU_OFF_PENDING
CPU_OFF
```

### 设计要点

- CPU_OFF 前执行任务迁移和中断清理。
- EL1 只请求 CPU_OFF，不直接关闭电源。
- EL3 维护物理 CPU 状态。
- Cluster 电源域只有在所有子 CPU 都 OFF 时才允许关闭。
- CPU_ON 必须保证启动参数在目标核可见。

### 启动参数可见性

```
boot_ctx[cpu].entry = entry;
boot_ctx[cpu].context = context;

dsb_sy();  /* 保证启动上下文写入完成 */
sev();     /* 唤醒处于 WFE 的目标 CPU */
```

目标 CPU：

```
for (;;) {
    wfe();

    if (boot_ctx_valid(my_cpu())) {
        dsb_sy();
        entry = boot_ctx[my_cpu()].entry;
        context = boot_ctx[my_cpu()].context;
        break;
    }
}
```

---

## 11.3 案例三：移动终端的 Linux + OP-TEE + SCMI

### 需求

- Linux 管理普通设备；
- OP-TEE 管理密钥和安全存储；
- SCP 管理时钟、电源和温度；
- TrustZone 防止普通世界访问安全资源。

### 调用关系

```
Linux
├── SMC -> OP-TEE Secure Monitor
│          └── Trusted Application
│
├── SCMI -> SCP
│           └── Clock/Power/Thermal
│
└── PSCI -> TF-A
            └── CPU/System Power
```

### 设计要点

- 不要用一个自定义 SMC 服务替代已有 SCMI。
- OP-TEE 只管理安全服务，不直接接管所有电源资源。
- TF-A 负责安全世界切换、PSCI 和服务路由。
- SCP 对来自 Linux 的资源请求执行权限检查。
- 安全服务和资源管理服务使用不同 Owner ID 和调用入口。

---

# 12. 高频问题深度答疑

## 问题一：为什么 Linux 不直接操作电源和时钟寄存器？

主要原因有四个：

1. **安全隔离**：关键电源寄存器可能影响安全域或其他 OS。
2. **资源共享**：多个设备可能共享 PLL、时钟源和电源域。
3. **硬件差异**：不同 SoC 的寄存器布局和状态机差异很大。
4. **策略与机制分离**：Linux 决定策略，SCP/固件执行硬件机制。

直接 MMIO 适合简单、单 OS、非安全的固定平台；工业级异构平台优先采用 SCMI。

## 问题二：PSCI 和 SCMI 是否可以互相替代？

通常不能。

- PSCI 的核心是 CPU 和系统级电源状态。
- SCMI 的核心是平台资源管理。

可以存在平台相关的交叠，但不建议混用。例如：

- CPU_ON 使用 PSCI；
- CPU 频率使用 SCMI Performance；
- CPU Cluster 电源域可以由 SCMI 管理，但必须与 PSCI 的 CPU 状态机协调。

## 问题三：SMC 和 HVC 如何选择？

选择原则：

```
调用方是普通 OS，目标是安全监控/EL3？
    -> SMC

调用方是 Guest OS，目标是 Hypervisor/EL2？
    -> HVC

调用方是 EL1，但平台没有 Hypervisor？
    -> 通常通过 SMC 进入 EL3

Hypervisor 需要调用 EL3 服务？
    -> 由 Hypervisor 代为 SMC
```

在虚拟化平台，Guest 不应被允许直接对 EL3 发送任意 SMC。

## 问题四：SCMI 超时后可以立即重发吗？

不能盲目重发。

需要先确认：

- 原请求是否已在 SCP 执行；
- 原响应是否只是中断丢失；
- Token 是否已被释放；
- SCP 是否仍然健康；
- 操作是否幂等。

例如：

- `CLOCK_RATE_SET` 通常可以设计为幂等；
- `POWER_STATE_SET` 需要回读状态；
- 固件升级、写入不可逆寄存器等操作不能简单重试。

## 问题五：SCMI 是否一定比 MMIO 慢？

是的，单次调用通常更慢，因为包含：

```
消息构造 + 内存同步 + Doorbell + 中断 + SCP 调度 + 响应解析
```

但系统总体性能不一定更差，因为 SCMI 可以：

- 合并请求；
- 在 SCP 侧执行复杂策略；
- 减少 Linux 端锁和硬件细节；
- 避免多个 OS 同时修改寄存器；
- 提供异步通知。

因此应比较**端到端系统性能**，而不是单次寄存器写延迟。

## 问题六：为什么电源管理接口最容易出现死锁？

典型循环依赖：

```
Linux suspend
  -> SCMI Power OFF
      -> SCP 等待 Linux ACK
          -> Linux suspend 线程已停止响应
```

或者：

```
SCMI 请求持有通道锁
  -> 等待电源域唤醒
      -> 唤醒路径再次请求同一 SCMI 通道
```

解决方法：

- suspend 路径使用专用通道；
- 禁止持有通道锁等待会触发回调的操作；
- 异步执行电源切换；
- 明确锁顺序；
- 为每个电源域定义状态转换图；
- 对恢复路径进行故障注入测试。

---

# 13. 课程核心总结

## 13.1 核心要点

1. **SMC/HVC 是指令，SMCCC 是 ABI，PSCI/SCMI 是服务协议。**
2. **PSCI 管理 CPU 和系统状态，SCMI 管理平台资源。**
3. SCMI 通常采用 **共享内存 + Mailbox + 中断**。
4. 所有跨处理器共享内存都必须明确 Cache、一致性和屏障策略。
5. 所有控制请求都必须具备版本协商、错误处理和超时机制。
6. 电源管理的关键不是接口调用本身，而是完整状态机和资源依赖。
7. Fast Call 只能执行短、确定性操作。
8. CPU_ON、Power Domain、Clock、DVFS 必须进行并发和回滚设计。
9. 生产系统应实现通道统计、故障恢复和权限控制。
10. Linux 负责策略，EL3/SCP 负责安全边界和硬件机制。

## 13.2 性能排序

从低延迟到高延迟，典型排序：

```
本地寄存器访问
    <
普通函数调用
    <
SMC Fast Call
    <
PSCI 状态查询
    <
SCMI 简单请求
    <
SCMI + SCP 硬件状态切换
    <
电源域/PLL/PMIC 完整转换
```

## 13.3 通用选型结论

- **CPU 启停：PSCI**
- **系统关机/重启：PSCI**
- **安全服务：SMC + Trusted Service**
- **Guest 到 Hypervisor：HVC**
- **时钟、电源、性能、传感器：SCMI**
- **异构处理器之间传输：Mailbox + Shared Memory**
- **简单单核裸机系统：可使用 MMIO，但必须封装平台层**
- **多 OS、安全关键、复杂 SoC：优先使用标准接口**

---

# 14. 快速参考速查表

## 14.1 场景选型表

|场景|首选接口|
|---|---|
|启动 CPU|PSCI CPU_ON|
|关闭当前 CPU|PSCI CPU_OFF|
|CPU 低功耗|PSCI CPU_SUSPEND|
|系统关机|PSCI SYSTEM_OFF|
|系统重启|PSCI SYSTEM_RESET|
|时钟开关|SCMI Clock|
|设置时钟频率|SCMI Clock|
|电源域开关|SCMI Power Domain|
|CPU/GPU DVFS|SCMI Performance|
|温度读取|SCMI Sensor|
|硬件复位|SCMI Reset|
|访问密钥|SMC Trusted Service|
|Guest 系统服务|HVC|
|异步平台事件|SCMI Notification/SDEI|
|Secure Partition 通信|FF-A|

## 14.2 特性对比表

|特性|SMC|HVC|PSCI|SCMI|
|---|---|---|---|---|
|入口|EL3|EL2|EL3 服务|SCP/固件|
|参数容量|小|小|小|大|
|典型同步性|同步|同步|同步|同步/异步|
|是否适合电源策略|否|否|部分|是|
|是否适合复杂资源|否|否|否|是|
|是否需要共享内存|通常不需要|通常不需要|通常不需要|通常需要|
|是否需要 Token|否|否|否|是|
|是否需要版本发现|SMCCC|SMCCC|PSCI|SCMI|
|常见实现|TF-A|Hypervisor|TF-A|SCP|

---

# 15. 学习效果自检

完成本课后，应能够回答并实践以下问题：

- 能否解释 SMC、HVC、SMCCC 三者的关系？
- 能否画出 Linux 到 EL3、Linux 到 SCP 的完整调用路径？
- 能否说明 PSCI 和 SCMI 的职责边界？
- 能否正确构造一个 64 位 SMCCC Function ID？
- 能否解释 Fast Call 和 Yielding Call 的适用条件？
- 能否实现带超时的 SCMI 共享内存事务？
- 能否说明为什么必须使用 Token？
- 能否处理共享内存 Cache 一致性？
- 能否设计 CPU_ON 的状态机和并发锁？
- 能否设计电源域引用计数与失败回滚？
- 能否解释 SCMI 超时后的安全恢复流程？
- 能否识别 Linux suspend 与 SCP 之间的死锁路径？
- 能否设计 PSCI 与 SCMI 协同的多核低功耗架构？
- 能否列出至少三项接口安全风险？
- 能否测量一次 SMC 和一次 SCMI 调用的端到端延迟？

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：实现最小 SMC 调用封装

要求：

- 支持 AArch64；
- 支持 4 个输入参数；
- 保存返回寄存器；
- 增加错误码转换；
- 使用 Generic Timer 测量延迟。

验收指标：

- 调用前后寄存器值正确；
- 负数错误码不被误解释为成功；
- 延迟统计至少采集 10,000 次。

### 任务二：实现 PSCI Mock Server

实现以下接口：

- `PSCI_VERSION`
- `CPU_ON`
- `CPU_OFF`
- `AFFINITY_INFO`
- `SYSTEM_RESET`

要求：

- CPU 状态机；
- 重复调用检测；
- 参数合法性检查；
- 并发锁；
- 故障注入。

### 任务三：实现最小 SCMI Base + Clock Client

要求：

- 共享内存通道；
- Mailbox Doorbell；
- Token 分配；
- 超时；
- 响应校验；
- Base 协议发现；
- Clock Enable/Disable/Rate Set。

### 任务四：加入故障恢复

注入以下故障：

- SCP 不响应；
- 中断丢失；
- 错误 Token；
- 错误长度；
- 重复响应；
- 电源域上电失败；
- SCP 重启。

要求系统：

- 不能死循环；
- 不能污染下一个事务；
- 能记录完整诊断信息；
- 能恢复到可控状态。

### 任务五：构建 Linux + SCP 集成环境

建议使用：

- TF-A；
- U-Boot；
- Linux ARM64；
- QEMU 或真实开发板；
- OpenAMP/RPMsg 或自定义 Mailbox；
- SCMI Linux 驱动框架。

重点验证：

```
CPU hotplug
cpufreq
cpuidle
clock enable/disable
runtime PM
system suspend/resume
thermal notification
```

## 16.2 性能测试方法

### SMC 测试

```
1. 读取 Generic Timer 起始值
2. 执行 SMC
3. 读取结束值
4. 统计最小值、平均值、P50、P95、P99、最大值
```

### SCMI 测试

分别测量：

- 客户端消息构造时间；
- Cache 清理时间；
- Doorbell 到 SCP 收到请求时间；
- SCP 执行时间；
- 响应中断延迟；
- 客户端解析时间；
- 总事务时间。

### 必须采集的指标

|指标|目的|
|---|---|
|平均延迟|常态性能|
|P99 延迟|实时性评估|
|超时率|稳定性|
|通道占用率|并发瓶颈|
|SCP CPU 利用率|管理处理器负载|
|请求合并率|协议优化效果|
|电源切换耗时|低功耗设计|
|故障恢复时间|系统韧性|

## 16.3 进阶学习方向

### 固件方向

- TF-A BL31 架构；
- PSCI 实现和平台端口；
- Trusted Board Boot；
- EL3 Runtime Service；
- SDEI；
- FF-A；
- OP-TEE 调度和安全监控。

### Linux 方向

- `drivers/firmware/arm_scmi/`
- `drivers/cpufreq/scmi-cpufreq.c`
- `drivers/cpuidle/`
- CPU hotplug；
- Runtime PM；
- Generic Power Domain；
- Thermal Framework；
- Device Tree SCMI 节点。

### 架构方向

- 多租户 SoC 资源管理；
- Hypervisor 虚拟化 SCMI；
- 安全世界与普通世界资源隔离；
- 功能安全状态机；
- 电源管理形式化验证；
- 异构多处理器故障恢复；
- 车规级 AUTOSAR 与 ARM 系统控制接口协同。

### 最终能力目标

能够从以下维度评审一套 ARM SoC 控制架构：

```
接口标准性
调用路径
异常级别边界
安全隔离
协议版本兼容
共享内存一致性
并发控制
实时性
功耗
故障恢复
可观测性
跨平台迁移成本
```

最终应形成如下工程判断：

> **凡是涉及跨处理器、跨安全域、跨操作系统的系统资源管理，都不应停留在“直接写寄存器”的局部实现，而应通过 SMCCC、PSCI、SCMI 和可靠传输层构建明确