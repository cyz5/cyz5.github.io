
## 1. 学习目标

### 理解

- 理解 NOR Flash 的阵列结构、读写粒度、擦除粒度及电荷存储原理。
- 理解 MCU 内部 Flash、外部 SPI/QSPI/OSPI Flash、Data Flash、EEPROM Emulation 的差异。
- 理解 IAP、OTA、Bootloader、应用程序、升级包、回滚分区之间的关系。
- 理解 Flash 编程过程中总线访问、缓存、流水线、看门狗和中断的影响。

### 掌握

- 掌握 Flash 解锁、擦除、编程、校验、加锁的完整流程。
- 掌握单镜像 IAP、双镜像 A/B OTA、下载区升级和断电恢复设计。
- 掌握 CRC、Hash、数字签名、版本回滚保护等升级安全机制。
- 掌握 Flash 地址规划、镜像头设计、状态机和升级日志设计。

### 精通

- 能定位 Flash 编程失败、ECC 错误、Cache 不一致、写保护、掉电损坏等问题。
- 能分析升级过程中的原子性、实时性、寿命和安全风险。
- 能设计适配 Cortex-M、RTOS 和嵌入式 Linux 的可靠升级架构。
- 能根据 Flash 容量、RAM 容量、网络带宽和安全等级完成方案选型。

### 能够设计

- 能设计工业级 Bootloader 和 IAP/OTA 升级协议。
- 能设计支持断点续传、断电恢复、自动回滚和防降级的升级系统。
- 能定义完整的镜像格式、升级状态机、异常恢复机制和生产测试策略。
- 能建立升级功能的可靠性、安全性和性能验收指标。

---

## 2. 前置要求

### 知识要求

- 熟悉 C 语言指针、结构体、位操作、链接脚本和内存映射。
- 熟悉 MCU 启动流程、向量表、异常入口和中断重定位。
- 熟悉 RTOS 任务、临界区、互斥锁、看门狗和定时器。
- 熟悉 CRC、Hash、数字签名和基本网络传输概念。
- 了解 MCU 的 Flash 控制器、Cache、总线矩阵和 MPU。

### 技能要求

- 能阅读芯片参考手册中的 Flash Controller 章节。
- 能使用调试器查看 Flash 内容、寄存器和异常现场。
- 能编写链接脚本，将 Bootloader、应用和升级区放置到不同地址。
- 能使用 Python、Shell 或构建系统生成和校验固件镜像。
- 能执行断电测试、异常复位测试、长时间擦写寿命测试。

---

## 3. 技术概述

### 3.1 Flash 的核心定义

Flash 是一种**非易失性存储器**。数据通过改变存储单元中的电荷状态表示，掉电后仍能保持内容。

对于大多数 MCU 内部 NOR Flash：

- 读取通常按字节、半字、字或缓存行进行。
- 编程只能把位从 `1` 变为 `0`。
- 擦除才能把位从 `0` 恢复为 `1`。
- 编程粒度通常为 8/16/32/64 bit，或芯片定义的 Flash word。
- 擦除粒度通常为 Page、Sector 或 Block。
- 擦除时间远大于编程时间。
- 擦除和编程期间，CPU 可能无法从同一 Flash Bank 取指。

典型状态转换：

```
已擦除状态：0xFF
编程操作：  1 -> 0
再次编程：  只能继续 1 -> 0
恢复为 1：  必须擦除整个页/扇区
```

### 3.2 IAP、OTA 和 Bootloader

```
Bootloader
    |
    +-- IAP：通过 UART/CAN/USB/以太网等本地接口更新
    |
    +-- OTA：通过 Wi-Fi/蜂窝网络/以太网远程获取升级包
```

IAP 和 OTA 的本质相同，都是：

1. 接收或读取新镜像。
2. 校验镜像完整性和真实性。
3. 将镜像写入目标区域。
4. 设置升级状态。
5. 重启进入 Bootloader。
6. Bootloader 决定启动、确认或回滚。

差异主要在于**升级包获取路径、通信可靠性和运维体系**。

### 3.3 主流存储架构

#### 单分区直接覆盖

```
+-------------------+
| Bootloader        |
+-------------------+
| Application       |  <- 下载后直接擦除并覆盖
+-------------------+
```

优点是容量利用率高，缺点是升级失败后应用可能不可启动。

#### 下载区 + 应用区

```
+-------------------+
| Bootloader        |
+-------------------+
| Application       |
+-------------------+
| Download Storage  |  <- 保存完整升级包
+-------------------+
```

Bootloader 重启后将下载区镜像复制到应用区。

#### A/B 双镜像

```
+-------------------+
| Bootloader        |
+-------------------+
| Image A           |
+-------------------+
| Image B           |
+-------------------+
| Metadata          |
+-------------------+
```

当前运行 A，升级写入 B；B 启动成功后再确认。失败时继续启动 A。

#### 外部 Flash + XIP

```
外部 QSPI/OSPI Flash
    |
    +-- 固件镜像存储
    +-- 文件系统
    +-- 资源数据
    +-- XIP 执行区
```

适合资源较大或需要更大升级缓存的设备，但要处理 QSPI 初始化、掉电一致性和总线异常。

---

## 4. 核心特性横向对比

|方案|额外 Flash|失败恢复|RAM 需求|升级复杂度|适用场景|
|---|---|---|---|---|---|
|单分区覆盖|低|差|低|低|生产下载、可线刷设备|
|下载区复制|中|中|低|中|具备独立升级存储区的 MCU|
|A/B 双镜像|高，约 2 倍|优秀|低|高|远程 OTA、工业设备|
|外部 Flash 缓存|中到高|中到高|低|高|内部 Flash 不足|
|RAM 下载后刷写|低|差|高|中|镜像较小、RAM 充足|
|双 Bank 内部 Flash|中|优秀|低|高|支持 Bank Swap 的高端 MCU|
|差分升级|低|依赖基线镜像|中|很高|带宽昂贵、镜像较大|
|MCUboot 类框架|由布局决定|良好|低到中|中到高|需要成熟安全启动方案|

### 4.1 完整性与真实性对比

|机制|解决的问题|能防篡改|能防伪造|性能|典型用途|
|---|---|---|---|---|---|
|无校验|无|否|否|最高|不建议生产使用|
|CRC32|传输错误、存储位翻转|否|否|高|完整性快速检查|
|SHA-256|内容完整性|否|否|中|镜像摘要|
|HMAC-SHA256|共享密钥认证|是|是|中|对称密钥设备|
|ECDSA/Ed25519|非对称签名认证|是|是|验签较慢|固件真实性验证|
|AES-GCM|机密性 + 完整性|是|是|中|需要保密的固件|

**CRC 不能替代数字签名**。CRC 只能检测随机错误，攻击者可以重新计算 CRC。

---

## 5. 底层原理与功能特性深度解析

## 5.1 Flash 编程的基本流程

典型 MCU Flash 编程顺序如下：

```
关闭或暂停可能访问 Flash 的任务
    |
解锁 Flash 控制器
    |
检查并清除旧错误标志
    |
按芯片要求擦除 Page/Sector
    |
按编程粒度写入数据
    |
等待 BUSY 清零
    |
检查 EOP、PGERR、WRPERR、ECCERR 等状态
    |
读回校验
    |
重新加锁
```

不同 MCU 的寄存器名称不同，但控制逻辑基本一致。

### 5.1.1 生产级抽象接口

```
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef enum {
    FLASH_OK = 0,
    FLASH_EINVAL,
    FLASH_ALIGN,
    FLASH_BUSY,
    FLASH_TIMEOUT,
    FLASH_PROGRAM_ERROR,
    FLASH_VERIFY_ERROR,
    FLASH_PROTECTED
} flash_status_t;

typedef struct {
    uintptr_t base;
    size_t size;
    size_t page_size;
    size_t program_size;
    uint32_t timeout_ms;
} flash_geometry_t;

flash_status_t flash_erase(uintptr_t address, size_t length);
flash_status_t flash_program(uintptr_t address,
                             const void *data,
                             size_t length);
bool flash_is_erased(uintptr_t address, size_t length);
```

接口设计要点：

- 地址和长度必须做整数溢出检查。
- 地址必须落在合法 Flash 区域。
- 编程地址和长度必须满足芯片粒度要求。
- 擦除只能按页或扇区边界执行。
- 所有操作必须有超时。
- 错误状态必须被读取并转换为上层可识别错误。

### 5.1.2 地址范围和整数溢出检查

错误实现：

```
if (address + length > FLASH_END) {
    return FLASH_EINVAL;
}
```

`address + length` 可能整数溢出。

正确实现：

```
static bool range_valid(uintptr_t address,
                        size_t length,
                        uintptr_t base,
                        size_t region_size)
{
    if (address < base) {
        return false;
    }

    uintptr_t offset = address - base;

    if (offset > region_size) {
        return false;
    }

    return length <= (region_size - offset);
}
```

### 5.1.3 按编程粒度写入

假设芯片要求 8 字节编程：

```
#define FLASH_PROGRAM_SIZE 8U

static bool is_aligned_uintptr(uintptr_t value, size_t alignment)
{
    return (value % alignment) == 0U;
}

flash_status_t flash_program_aligned(uintptr_t address,
                                     const uint8_t *data,
                                     size_t length)
{
    if (data == NULL || length == 0U) {
        return FLASH_EINVAL;
    }

    if (!is_aligned_uintptr(address, FLASH_PROGRAM_SIZE) ||
        (length % FLASH_PROGRAM_SIZE) != 0U) {
        return FLASH_ALIGN;
    }

    for (size_t offset = 0; offset < length; offset += FLASH_PROGRAM_SIZE) {
        uint64_t word = 0U;

        /*
         * 使用 memcpy 避免未对齐指针解引用和严格别名问题。
         * 实际项目还应根据芯片要求处理 endian 和 ECC 粒度。
         */
        memcpy(&word, &data[offset], sizeof(word));

        flash_hw_clear_errors();

        if (!flash_hw_program_double_word(address + offset, word)) {
            return FLASH_PROGRAM_ERROR;
        }

        if (!flash_hw_wait_ready(FLASH_PROGRAM_TIMEOUT_MS)) {
            return FLASH_TIMEOUT;
        }

        if (*(const volatile uint64_t *)(address + offset) != word) {
            return FLASH_VERIFY_ERROR;
        }
    }

    return FLASH_OK;
}
```

注意：

- 不能假设所有 MCU 都允许直接读取刚写入的 Flash。
- 某些芯片需要等待 Cache 刷新或执行 `DSB/ISB`。
- 某些芯片需要从 RAM 执行整个 Flash 编程函数。
- 某些架构不允许在 Flash 编程时读取同一 Bank。

---

## 5.2 擦除粒度与写放大

Flash 页擦除会影响整个页。即使只修改 4 字节，也可能必须：

1. 读取整页到 RAM。
2. 修改目标字段。
3. 擦除整页。
4. 将整页重新写回。

设页大小为 `P`，实际修改数据为 `D`，则写放大近似为：

WA=PDWA=DP​

例如页大小 2048 字节，只修改 16 字节：

WA=204816=128WA=162048​=128

这会直接降低擦写寿命并增加掉电风险。

因此：

- 配置数据应采用日志结构。
- 高频计数器应使用 Wear Leveling。
- 不应在每次参数变化时直接擦除同一页。
- 升级元数据应设计冗余和提交标志。

---

## 5.3 Flash 擦写寿命

假设某页额定寿命为 10,000 次擦除，每次业务操作造成一次擦除：

T=10000NdayT=Nday​10000​

如果每天写入 20 次：

T=1000020=500 天T=2010000​=500 天

采用 16 页轮换后：

T≈500×16=8000 天T≈500×16=8000 天

实际还要考虑：

- 温度对寿命的影响。
- 擦除分布是否均匀。
- 电源异常是否造成额外擦除。
- 数据恢复是否导致重复提交。
- 厂商额定值通常是统计保证，而非绝对上限。

---

## 5.4 Bootloader 启动和向量表切换

Cortex-M 应用跳转通常需要：

1. 关闭 SysTick。
2. 关闭或清除中断。
3. 停止 Bootloader 初始化的外设。
4. 设置 `VTOR` 为应用向量表地址。
5. 设置主栈指针 MSP。
6. 跳转到应用 Reset Handler。
7. 使用 `DSB/ISB` 确保流水线同步。

```
#include <stdint.h>
#include <stdbool.h>

typedef void (*app_entry_t)(void);

static bool app_vector_valid(uintptr_t app_base,
                             uintptr_t sram_base,
                             uintptr_t sram_end)
{
    uint32_t initial_msp = *(const volatile uint32_t *)app_base;
    uint32_t reset_pc    = *(const volatile uint32_t *)(app_base + 4U);

    bool msp_valid = (initial_msp >= sram_base) &&
                     (initial_msp <= sram_end);

    /* Cortex-M Thumb 指令地址最低位必须为 1。 */
    bool pc_valid = ((reset_pc & 1U) != 0U);

    return msp_valid && pc_valid;
}

__attribute__((noreturn))
static void jump_to_application(uintptr_t app_base)
{
    uint32_t app_msp   = *(const volatile uint32_t *)app_base;
    uint32_t app_reset = *(const volatile uint32_t *)(app_base + 4U);

    __disable_irq();

    SysTick->CTRL = 0U;
    SysTick->LOAD = 0U;
    SysTick->VAL  = 0U;

    for (uint32_t irq = 0U; irq < NUMBER_OF_NVIC_REGISTERS; ++irq) {
        NVIC->ICER[irq] = 0xFFFFFFFFU;
        NVIC->ICPR[irq] = 0xFFFFFFFFU;
    }

    SCB->VTOR = (uint32_t)app_base;
    __DSB();
    __ISB();

    __set_MSP(app_msp);

    ((app_entry_t)app_reset)();

    while (true) {
        /* Reset Handler 不应正常返回。 */
    }
}
```

工程注意事项：

- 不能只检查向量表第一个字是否非 `0xFFFFFFFF`。
- 应检查 MSP 是否位于合法 SRAM 范围。
- 应检查 Reset Handler 是否位于合法应用区并且为 Thumb 地址。
- Bootloader 与应用必须明确外设清理协议。
- 应用链接地址必须与实际分区地址一致。

---

## 5.5 升级镜像格式

推荐使用固定头部 + 数据区 + 签名区的格式：

```
#define IMAGE_MAGIC 0x494D4731UL /* "IMG1" */

typedef struct {
    uint32_t magic;
    uint32_t header_size;
    uint32_t image_size;
    uint32_t image_version;
    uint32_t target_id;
    uint32_t flags;
    uint8_t  sha256[32];
    uint8_t  signature[64];
    uint32_t header_crc;
} image_header_t;
```

字段作用：

|字段|作用|
|---|---|
|`magic`|判断是否为合法镜像|
|`header_size`|支持头部扩展|
|`image_size`|防止越界读写|
|`image_version`|防降级|
|`target_id`|防止刷错硬件型号|
|`flags`|加密、压缩、试运行等属性|
|`sha256`|镜像内容摘要|
|`signature`|验证发布者身份|
|`header_crc`|快速检测头部损坏|

### 5.5.1 镜像校验顺序

```
1. 校验头部地址和长度
2. 校验 magic 和 header_size
3. 校验 target_id
4. 检查 image_size 是否超出目标分区
5. 检查 image_version 是否低于最低允许版本
6. 计算镜像 SHA-256
7. 校验数字签名
8. 校验应用向量表
9. 校验 Flash 回读内容
```

不能只依赖应用自身校验。Bootloader 必须在跳转前完成验证。

---

## 5.6 升级状态机和掉电原子性

建议状态机：

```
IDLE
  |
DOWNLOADING
  |
READY_TO_TEST
  |
BOOT_TRIAL
  |
CONFIRMED
  |
FAILED -> ROLLBACK
```

状态不能只用一个字节直接覆盖。更可靠的方式是使用双记录：

```
typedef struct {
    uint32_t sequence;
    uint32_t state;
    uint32_t image_version;
    uint32_t image_crc;
    uint32_t commit_marker;
    uint32_t record_crc;
} boot_record_t;
```

提交流程：

```
1. 擦除下一条记录所在页
2. 写入 sequence、state、版本、摘要
3. 回读并校验记录
4. 最后写入 commit_marker
5. 下次启动只接受 marker 正确且 CRC 正确的记录
```

由于 Flash 只能从 `1` 编程为 `0`，`commit_marker` 应设计为一个最终提交字段。掉电发生在提交前，Bootloader 忽略该记录。

---

## 6. 性能量化分析

以下数据为典型 120 MHz Cortex-M4/M7、内部 NOR Flash 的工程估算值，具体数值必须以目标芯片实测和数据手册为准。

### 6.1 典型操作耗时

|操作|典型耗时|
|---|---|
|8 字节编程|0.05～0.5 ms|
|256 字节连续编程|1～8 ms|
|2 KB Page 擦除|20～100 ms|
|16 KB Sector 擦除|100～1000 ms|
|CRC32，硬件加速|10～50 MB/s|
|CRC32，纯软件|2～15 MB/s|
|SHA-256，硬件加速|10～80 MB/s|
|ECDSA P-256 验签|20～500 ms|
|Ed25519 验签|1～30 ms|

### 6.2 OTA 下载时间

升级包大小为 `S`，有效吞吐为 `R`：

Tdownload=8SRTdownload​=R8S​

假设：

- 镜像大小：512 KiB
- 有效吞吐：80 KiB/s
- 擦除和写入额外耗时：4 s

则：

Tdownload=51280=6.4sTdownload​=80512​=6.4s

总升级时间约：

Ttotal=6.4+4=10.4sTtotal​=6.4+4=10.4s

如果加入 TLS、重传、签名验证和低信号环境，现场时间可能达到 15～60 秒。

### 6.3 RAM 占用

|组件|典型 RAM|
|---|---|
|Bootloader 基础代码运行栈|2～8 KiB|
|4 KiB 下载缓冲区|4 KiB|
|SHA-256 上下文|200～500 B|
|升级元数据|128 B～4 KiB|
|TLS 协议栈额外内存|20～100 KiB|
|A/B OTA|不要求保存完整镜像到 RAM|

**不要把整个固件下载到 RAM 再刷写**，除非镜像很小且 RAM 明确足够。工业方案通常采用流式写入：

```
网络接收块 -> RAM 缓冲 -> 校验 -> Flash 写入 -> 回读或分段确认
```

### 6.4 主要瓶颈

1. **Sector 擦除时间**：通常是最明显的阻塞点。
2. **网络吞吐**：低速蜂窝网络下远大于本地 Flash 操作时间。
3. **数字签名验证**：资源受限 MCU 上可能达到数百毫秒。
4. **单 Bank 取指冲突**：Flash 操作期间代码无法执行。
5. **Cache 一致性**：写入后 CPU 仍可能读取旧缓存。
6. **日志写放大**：频繁元数据更新消耗 Flash 寿命。

### 6.5 优化手段

|优化措施|典型收益|
|---|---|
|使用硬件 CRC|校验吞吐提升 5～30 倍|
|批量编程|减少寄存器配置和等待开销|
|双 Bank|降低升级期间 CPU 停顿|
|A/B 分区|失败恢复时间从重新下载降至一次重启|
|差分升级|带宽减少 30%～90%，取决于版本差异|
|元数据日志化|降低单页擦除频率|
|分段 SHA-256|RAM 降至几百字节|
|预擦除空闲扇区|缩短用户感知的刷写停顿|

---

## 7. 应用场景选型指南

### 7.1 纯文本决策流程图

```
是否需要远程升级？
|
+-- 否
|   |
|   +-- 是否允许升级失败后人工重新下载？
|       |
|       +-- 是 -> 单分区 IAP
|       +-- 否 -> 下载区复制或 A/B
|
+-- 是
    |
    +-- 是否有足够空间保存两个完整镜像？
    |   |
    |   +-- 是 -> A/B OTA
    |   |
    |   +-- 否
    |       |
    |       +-- 是否有外部 Flash？
    |           |
    |           +-- 是 -> 外部 Flash 下载区 + Bootloader 复制
    |           +-- 否 -> 单分区升级 + 强制恢复链路
    |
    +-- 是否有安全合规要求？
        |
        +-- 是 -> SHA-256 + 数字签名 + 防降级 + 安全启动
        +-- 否 -> CRC32 + 版本检查至少不能省略
```

### 7.2 典型场景

|场景|需求|方案|理由|
|---|---|---|---|
|工业传感器 UART 升级|现场串口、Flash 小|单分区 IAP|成本低，可人工恢复|
|电机控制器 CAN 升级|升级时不能破坏原固件|下载区复制|CAN 带宽低，故障可重试|
|家庭网关 Wi-Fi OTA|远程无人值守|A/B OTA|支持自动回滚|
|汽车 ECU|安全、分区、诊断协议|双 Bank/A-B + 签名|满足高可靠和安全要求|
|低功耗传感器|电池供电、镜像小|差分或压缩 OTA|降低无线传输能耗|
|医疗设备|防篡改、审计、回滚|安全启动 + 签名 + 日志|强化可追溯性|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **Bootloader 必须足够小且稳定**，其升级机制应独立设计。
2. **Bootloader 不信任应用镜像**，所有边界、版本和签名都必须重新验证。
3. **升级过程必须可恢复**，不能假设电源、网络和存储永远可靠。
4. **升级元数据必须具备原子提交语义**。
5. **所有耗时操作必须有超时和错误码**。
6. **Flash 区域必须由链接脚本和构建系统统一管理**。
7. **生产版本禁止使用绕过签名的调试路径**。
8. **升级流程中不能依赖正在被擦除的代码或常量数据**。

## 8.2 选型决策矩阵

评分：1 为较差，5 为优秀。

|方案|成本|可靠性|安全性|空间效率|远程运维|
|---|---|---|---|---|---|
|单分区覆盖|5|1|2|5|1|
|下载区复制|3|3|3|3|3|
|A/B OTA|1|5|5|1|5|
|外部 Flash|2|4|4|2|4|
|差分升级|3|3|4|4|5|

## 8.3 工业级编码规范

- 不使用裸常量表示 Flash 地址，使用分区宏或链接符号。
- 不直接对 Flash 映射地址执行未对齐访问。
- 不在业务层直接操作 Flash 控制器寄存器。
- 所有擦除、编程、校验函数都返回明确错误码。
- 不使用无界等待：

```
while (FLASH->SR & FLASH_SR_BSY) {
}
```

应改为带超时的等待：

```
uint32_t deadline = tick_now() + timeout_ms;

while (flash_hw_busy()) {
    if (time_after_eq(tick_now(), deadline)) {
        return FLASH_TIMEOUT;
    }
}
```

- 对升级包大小、目标地址、版本号和硬件型号进行边界检查。
- 编译时生成 map 文件并检查分区溢出。
- 对 Bootloader 和应用分别进行静态分析、单元测试和故障注入测试。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：没有擦除就重复写入

错误代码：

```
*(volatile uint32_t *)address = value;
*(volatile uint32_t *)address = new_value;
```

根因：

- Flash 编程只能执行 `1 -> 0`。
- 第二次写入可能需要恢复某些 `0 -> 1` 位。

正确实现：

```
flash_erase(page_address, page_size);
flash_program(address, &new_value, sizeof(new_value));
```

风险影响：

- 写入值错误。
- ECC 异常。
- 某些芯片报告编程错误。
- 长期运行后出现随机数据损坏。

---

## 9.2 错误二：擦除期间继续从同一 Flash 执行代码

错误代码：

```
void update(void)
{
    flash_erase(APP_BASE, APP_SIZE);
    flash_program(APP_BASE, image, image_size);
}
```

根因：

- CPU 取指和读取常量也可能访问被擦除的 Flash。
- 芯片可能停顿、BusFault 或执行异常。

正确实现策略：

```
__attribute__((section(".ramfunc")))
static flash_status_t flash_program_from_ram(uintptr_t address,
                                             const void *data,
                                             size_t size)
{
    /*
     * 此函数及其依赖的常量、底层寄存器访问代码必须位于 SRAM。
     */
    return flash_hw_program(address, data, size);
}
```

风险影响：

- 升级中断后无法恢复。
- 看门狗无法喂狗导致复位。
- 复位后 Bootloader 也可能损坏。

---

## 9.3 错误三：只校验 CRC，不验证镜像身份

错误代码：

```
if (crc32(image, image_size) == header->crc) {
    jump_to_application(APP_BASE);
}
```

根因：

- CRC 不是密码学认证。
- 攻击者可修改镜像并重新计算 CRC。

正确实现：

```
if (!sha256_verify(image, image_size, header->sha256)) {
    return UPDATE_HASH_ERROR;
}

if (!ecdsa_verify(public_key,
                  header->signature,
                  header->sha256)) {
    return UPDATE_SIGNATURE_ERROR;
}
```

风险影响：

- 恶意固件被安装。
- 设备被植入后门。
- 版本供应链被绕过。

---

## 9.4 错误四：升级标志只有一个变量

错误代码：

```
typedef struct {
    uint32_t update_pending;
} update_flag_t;
```

根因：

- 写标志过程中掉电，可能得到不可判定状态。
- 单个 Flash 页反复擦写会快速耗尽寿命。

正确实现：

- 双记录。
- 序列号递增。
- CRC 校验。
- 最后提交 marker。
- 多页轮换存储。

风险影响：

- Bootloader 既不知道是否存在新镜像，也无法判断旧状态。
- 设备陷入无限重启或错误升级。

---

## 9.5 错误五：未处理 Cache 和流水线

错误代码：

```
flash_program(APP_BASE, image, size);
jump_to_application(APP_BASE);
```

根因：

- I-Cache、D-Cache 可能保留旧指令或旧数据。
- Cortex-M7 等平台需要清理 Cache 和同步流水线。

正确实现：

```
SCB_CleanDCache_by_Addr((uint32_t *)APP_BASE, (int32_t)size);
SCB_InvalidateICache();
SCB_InvalidateDCache();

__DSB();
__ISB();

SCB->VTOR = APP_BASE;
__DSB();
__ISB();
```

风险影响：

- 新旧代码混合执行。
- 读回校验正确但启动仍失败。
- 问题只在优化版本或特定温度下出现。

---

## 9.6 错误六：没有防降级

错误代码：

```
if (image_signature_valid(image)) {
    install_image(image);
}
```

根因：

- 只验证签名，不验证版本新旧。
- 攻击者可以安装带合法签名但存在已知漏洞的旧版本。

正确实现：

```
if (image_version < secure_counter_get()) {
    return UPDATE_ROLLBACK_REJECTED;
}

if (!image_signature_valid(image)) {
    return UPDATE_SIGNATURE_ERROR;
}

secure_counter_commit(image_version);
```

风险影响：

- 已修复漏洞重新出现。
- 安全补丁被绕过。
- 设备进入不受支持的软件状态。

---

## 10. 多机制组合使用方案

推荐的工业级组合架构：

```
网络协议/TLS
    |
OTA 下载管理器
    |
分段接收 + 断点续传
    |
CRC32 快速检查
    |
Flash 下载区
    |
SHA-256 摘要
    |
数字签名验证
    |
Boot Metadata 双记录
    |
Bootloader
    |
A/B 镜像选择
    |
应用试运行
    |
应用确认
    |
失败自动回滚
```

### 10.1 升级框架

```
typedef enum {
    UPDATE_IDLE,
    UPDATE_RECEIVING,
    UPDATE_VERIFYING,
    UPDATE_READY,
    UPDATE_TRIAL,
    UPDATE_CONFIRMED,
    UPDATE_ROLLBACK
} update_state_t;

typedef struct {
    uint32_t expected_size;
    uint32_t received_size;
    uint32_t version;
    uint32_t target_id;
    uint32_t running_crc;
    sha256_ctx_t sha;
} update_context_t;

update_result_t update_begin(update_context_t *ctx,
                             const image_header_t *header)
{
    if (header == NULL) {
        return UPDATE_INVALID_ARGUMENT;
    }

    if (header->target_id != DEVICE_TARGET_ID) {
        return UPDATE_WRONG_TARGET;
    }

    if (header->image_size > APP_SLOT_SIZE) {
        return UPDATE_TOO_LARGE;
    }

    if (header->image_version < secure_counter_get()) {
        return UPDATE_ROLLBACK_REJECTED;
    }

    if (flash_erase(DOWNLOAD_BASE, header->image_size) != FLASH_OK) {
        return UPDATE_STORAGE_ERROR;
    }

    ctx->expected_size = header->image_size;
    ctx->received_size = 0U;
    ctx->version = header->image_version;
    ctx->target_id = header->target_id;
    ctx->running_crc = crc32_init();
    sha256_init(&ctx->sha);

    return UPDATE_OK;
}

update_result_t update_write_chunk(update_context_t *ctx,
                                   const uint8_t *chunk,
                                   size_t length)
{
    if (ctx == NULL || chunk == NULL || length == 0U) {
        return UPDATE_INVALID_ARGUMENT;
    }

    if (length > (ctx->expected_size - ctx->received_size)) {
        return UPDATE_SIZE_ERROR;
    }

    uintptr_t destination = DOWNLOAD_BASE + ctx->received_size;

    if (flash_program_aligned(destination, chunk, length) != FLASH_OK) {
        return UPDATE_STORAGE_ERROR;
    }

    ctx->running_crc = crc32_update(ctx->running_crc, chunk, length);
    sha256_update(&ctx->sha, chunk, length);
    ctx->received_size += length;

    metadata_checkpoint(ctx->received_size, ctx->running_crc);

    return UPDATE_OK;
}
```

生产实现还应考虑：

- 接收数据长度可能不是 Flash 编程粒度的整数倍。
- 最后一个块需要填充，但镜像真实长度不能被填充数据污染。
- 断点续传必须避免重复写入或正确处理重复块。
- 每个块应带 offset、length、sequence 和块级 CRC。
- 元数据 checkpoint 不能每块都擦页，应使用日志或周期性提交。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业网关 A/B OTA

### 需求

- 设备无人值守。
- 通过以太网或蜂窝网络升级。
- 断电后自动恢复。
- 新版本启动失败时自动回滚。
- 固件必须由平台签名。

### 架构

```
Bootloader
    |
    +-- Slot A：当前固件
    +-- Slot B：候选固件
    +-- Metadata：两个冗余记录
```

### 启动逻辑

```
if (slot_b_ready() && signature_valid(SLOT_B)) {
    boot_slot(SLOT_B);
    set_trial_counter(3);
} else {
    boot_slot(SLOT_A);
}
```

应用启动后完成关键自检：

```
bool app_self_test(void)
{
    return peripheral_init_ok() &&
           configuration_valid() &&
           communication_stack_ready() &&
           watchdog_service_active();
}

void app_confirm_if_ready(void)
{
    if (app_self_test()) {
        boot_metadata_confirm_current();
    }
}
```

### 设计要点

- Bootloader 设定最多 3 次试启动。
- 应用在网络、关键外设和配置加载成功后确认。
- 试启动期间发生看门狗复位，Bootloader 递减次数。
- 次数归零后标记候选镜像失败并切换回旧镜像。
- A/B 两个分区必须互相独立，禁止启动时依赖另一个损坏分区。

---

## 11.2 案例二：电机控制器 CAN IAP

### 需求

- 使用 CAN-FD。
- 实时控制任务不能因升级长时间失去响应。
- 升级过程允许中断。
- 不具备双镜像容量。

### 架构

```
Bootloader
    |
Application
    |
External SPI NOR Download Area
```

工作流程：

```
应用运行
  -> CAN 接收升级包并写外部 Flash
  -> 完整接收并验证签名
  -> 设置待升级标志
  -> 进入 Bootloader
  -> 分块复制到应用区
  -> 每段回读校验
  -> 启动新应用
```

### 设计要点

- 下载过程运行在低优先级任务或独立通信协程。
- 电机控制 ISR 不应直接执行 Flash 擦除。
- 升级请求必须经过诊断会话和权限认证。
- 擦除应用区前，必须确保外部 Flash 中存在完整合法镜像。
- 复制过程中断电时，下一次仍可从外部 Flash 重新复制。
- 对应用区写入采用段级状态记录，防止重复复制。

---

## 11.3 案例三：低功耗无线传感器差分升级

### 需求

- 内部 Flash 仅 256 KiB。
- 单镜像 180 KiB。
- 电池供电，空中传输能耗高。
- 无法容纳完整 A/B 镜像。

### 方案

```
旧镜像 + 差分包 -> RAM/外部小缓存 -> 分区重建
```

适用条件：

- 旧镜像基线必须准确。
- 差分算法、补丁格式和恢复流程必须经过严格验证。
- 差分包失败时必须保留旧镜像可启动。
- 如果在原地重建，必须设计页级恢复机制，否则断电会破坏旧镜像。

工程上更稳妥的替代方案：

- 使用压缩包代替差分包。
- 增加小容量外部 NOR Flash。
- 采用 Bank Swap。
- 只对资源文件做差分，代码仍采用整包更新。

---

## 12. 高频问题深度答疑

### 问题一：IAP 和 OTA 的本质区别是什么？

本质没有区别，都是**固件可信下载、存储、验证和启动切换**。IAP 通常指设备本地接口升级，OTA 指网络远程升级。OTA 额外引入：

- 网络中断。
- 断点续传。
- TLS。
- 设备身份认证。
- 云端任务管理。
- 灰度发布。
- 失败统计和远程回滚。

因此 OTA 不是简单地把 UART 接收替换成 TCP 接收。

### 问题二：为什么推荐 A/B，而不是直接覆盖应用区？

直接覆盖应用区的主要问题是：升级过程本身破坏了当前可运行镜像。

A/B 的代价是需要约两倍镜像存储空间，但提供：

- 升级失败保留旧版本。
- 断电后可恢复。
- 新版本试运行。
- 自动回滚。
- 远程无人值守能力。

如果设备具备足够存储空间，A/B 通常是可靠性最高的通用方案。

### 问题三：Flash 编程时是否必须关闭中断？

不一定。

需要关闭中断的情况：

- 中断向量表位于当前被操作的 Flash。
- ISR 或 ISR 使用的常量位于当前 Flash Bank。
- 芯片明确禁止 Flash 操作期间响应中断。
- 需要保证一段关键序列不可抢占。

不必完全关闭中断的情况：

- 芯片支持双 Bank 并且 ISR 位于另一 Bank 或 SRAM。
- Flash 控制器允许并行读取。
- 实时任务可以容忍短暂延迟。

更好的策略是：

```
短临界区保护寄存器操作
+ Flash 操作函数放 SRAM
+ 必要 ISR 放 SRAM
+ 看门狗和通信超时单独评估
```

### 问题四：CRC32、SHA-256 和数字签名应该如何组合？

推荐：

```
传输块 CRC32
    -> 快速发现通信错误

整镜像 SHA-256
    -> 确认内容摘要

数字签名
    -> 确认发布者身份和内容未被篡改
```

CRC 速度快但不抗攻击；SHA-256 能检测篡改但不证明发布者身份；数字签名用于真实性认证。

### 问题五：应用如何判断“启动成功”？

不能仅以 Reset Handler 被执行作为成功标准。建议在启动后的规定时间内完成：

- 时钟初始化。
- 关键外设初始化。
- 配置数据校验。
- 看门狗服务。
- 通信栈启动。
- 传感器或执行器自检。
- 关键任务创建。
- 持久化确认。

满足条件后写入 `CONFIRMED`。否则由看门狗复位，Bootloader 继续试启动或回滚。

### 问题六：如何处理升级过程中的断电？

必须明确每个阶段的持久化状态：

```
下载阶段断电：
    保留已接收 offset，支持续传

镜像验证阶段断电：
    下次重新验证，不信任中间结果

目标区复制阶段断电：
    通过 A/B 保留旧镜像
    或通过下载区重新复制

启动试运行阶段断电：
    Bootloader 根据 trial counter 回滚

确认阶段断电：
    采用最终 commit marker 保证状态可判定
```

核心原则是：**任何掉电点都必须对应一个确定的下次启动行为**。

---

## 13. 课程核心总结

### 核心要点

- Flash 编程遵循 **`1 -> 0`，擦除恢复 `0 -> 1`** 。
- 编程粒度和擦除粒度不同，页擦除会导致明显写放大。
- Bootloader 必须独立验证镜像大小、目标型号、版本、Hash、签名和向量表。
- IAP/OTA 的核心不是传输，而是**可信安装和故障恢复**。
- 可靠 OTA 必须具备试启动、确认、回滚和掉电恢复。
- CRC 解决随机错误，数字签名解决真实性问题。
- Flash 操作期间必须处理 Cache、流水线、中断、看门狗和代码执行位置。
- 远程无人值守设备优先选择 A/B 或双 Bank 架构。

### 性能排序

#### 读取性能

```
内部 Flash 直接读取
    > QSPI Memory-Mapped 读取
    > SPI Flash 普通读取
    > 低速外设读取
```

#### 写入性能

```
RAM
    > 内部 Flash 连续编程
    > QSPI/OSPI Page Program
    > 擦除操作
```

#### 可靠性排序

```
单分区覆盖
    < 下载区复制
    < 外部 Flash + Bootloader
    < A/B + 自动回滚 + 签名验证
```

### 通用选型结论

- **可人工维护、空间极紧张**：单分区 IAP。
- **需要断电恢复但没有双镜像空间**：下载区复制。
- **远程无人值守**：A/B OTA。
- **有安全要求**：SHA-256 + 数字签名 + 防降级。
- **有强实时约束**：双 Bank、RAM 执行 Flash 驱动或预擦除策略。
- **镜像很大且带宽昂贵**：压缩或差分升级，但必须额外设计恢复机制。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|条件|推荐方案|
|---|---|
|只支持串口，允许人工恢复|单分区 IAP|
|升级期间不能丢失旧固件|下载区复制|
|远程无人值守|A/B OTA|
|Flash 空间不足|外部 Flash 或双 Bank|
|高安全要求|安全启动 + 数字签名|
|网络不稳定|分块传输 + 断点续传|
|电池供电|压缩/差分 + 批量传输|
|高实时控制|RAM Flash 驱动 + 双 Bank|

### 14.2 特性对比表

|特性|最低要求|推荐工业方案|
|---|---|---|
|传输校验|CRC16/CRC32|分块 CRC32|
|镜像校验|CRC32|SHA-256|
|身份认证|无或共享密钥|ECDSA/Ed25519|
|版本控制|普通版本号|单调计数器防降级|
|掉电恢复|重试|A/B + 元数据双记录|
|状态存储|单变量|日志记录 + CRC + commit marker|
|启动判断|向量表非空|向量表 + 分区边界 + 签名|
|错误处理|返回失败|状态机 + 错误分类 + 回滚|
|诊断|串口日志|持久化升级事件和远程上报|

---

## 15. 学习效果自检

完成本课后，应能够回答并实现以下任务：

- [ ]  解释为什么 Flash 不能直接把 `0` 写回 `1`。
- [ ]  根据芯片数据手册确定编程粒度和擦除粒度。
- [ ]  设计 Bootloader、应用区、下载区和元数据区的地址布局。
- [ ]  编写带超时、边界检查和错误码的 Flash 驱动。
- [ ]  解释单 Bank Flash 编程期间代码执行限制。
- [ ]  实现安全的应用跳转和向量表切换。
- [ ]  设计含版本、目标型号、Hash 和签名的镜像头。
- [ ]  设计可抗掉电的升级状态机。
- [ ]  解释 CRC 与数字签名的安全边界。
- [ ]  实现 A/B 镜像试启动和自动回滚。
- [ ]  设计断点续传协议和块级校验。
- [ ]  计算升级时间、写放大和 Flash 寿命。
- [ ]  编写断电、看门狗复位、签名错误和空间不足测试用例。
- [ ]  能说明何时选择单分区、下载区复制或 A/B OTA。

---

## 16. 实践与进阶路径

### 阶段一：Flash 驱动基础

实践任务：

1. 读取芯片 Flash ID、容量和状态寄存器。
2. 实现页擦除、粒度编程和回读校验。
3. 添加超时、错误清除和保护检查。
4. 测量单页擦除、连续编程和回读时间。
5. 使用逻辑分析仪或 GPIO 翻转测量真实耗时。

验收指标：

- 任意非法地址不会破坏其他区域。
- 编程失败可区分超时、保护和校验错误。
- 连续 1000 次测试无数据错误。

### 阶段二：基础 IAP

实践任务：

1. 设计 Bootloader 和 Application 分区。
2. 通过 UART 实现分块传输。
3. 增加块序号、块 CRC 和重传。
4. 实现应用向量表检查和跳转。
5. 测试传输中断、复位和非法镜像。

验收指标：

- 传输中断后可以从指定 offset 继续。
- 错误镜像不会被启动。
- 应用区被破坏时 Bootloader 仍可进入升级模式。

### 阶段三：掉电恢复

实践任务：

1. 增加双记录 Boot Metadata。
2. 定义 `DOWNLOADING`、`READY`、`TRIAL`、`CONFIRMED` 状态。
3. 在擦除、写入、校验、提交各阶段随机断电。
4. 使用自动化继电器或电源控制器执行断电注入。
5. 统计每个掉电点的启动结果。

验收指标：

- 所有断电点均有确定恢复路径。
- 不出现无限重启。
- 元数据损坏时能选择最近一条有效记录。

### 阶段四：安全 OTA

实践任务：

1. 生成 SHA-256 镜像摘要。
2. 使用离线私钥签名。
3. Bootloader 内置公钥或证书链。
4. 实现版本单调递增和防降级。
5. 增加密钥轮换和密钥吊销策略。

验收指标：

- 修改任意镜像字节后验签失败。
- 使用错误设备型号镜像时拒绝安装。
- 旧版本镜像即使签名合法也无法降级。

### 阶段五：A/B OTA 与性能优化

实践任务：

1. 实现 A/B 镜像切换。
2. 实现试启动计数器。
3. 实现应用确认与自动回滚。
4. 对比软件 CRC、硬件 CRC、SHA-256 的吞吐。
5. 对比整包、压缩包和差分包的升级时间。
6. 分析双 Bank、Cache 和 SRAM 执行对实时性的影响。

### 性能测试方法

应至少记录以下指标：

```
擦除耗时：T_erase
编程耗时：T_program
校验耗时：T_verify
签名验证耗时：T_signature
网络传输耗时：T_download
最大中断延迟：T_irq_block
升级峰值 RAM：RAM_peak
单次升级写入量：W_update
元数据擦除次数：N_metadata_erase
```

建议测试矩阵：

|测试类别|测试条件|
|---|---|
|正常升级|满速网络、稳定电源|
|弱网升级|丢包 1%～10%、延迟 100～1000 ms|
|断电测试|每个 Flash 操作阶段随机断电|
|镜像攻击|修改数据、签名、版本和目标型号|
|存储异常|写保护、擦除超时、ECC 错误|
|资源压力|最低电压、最高温度、最小 RAM|
|长期可靠性|连续升级 1000～10000 次|
|实时性|升级同时运行控制 ISR 和通信任务|

### 进阶方向

- MCUboot、TF-M、Trusted Firmware-M。
- Secure Boot、Root of Trust 和硬件密钥存储。
- TrustZone-M、MPU、HUK、OTP 和安全计数器。
- UDS、ISO 14229、DoIP 和汽车 ECU 刷写。
- Linux U-Boot、RAUC、SWUpdate、Mender。
- SquashFS、OverlayFS 和嵌入式 Linux 双系统。
- 差分升级、二进制压缩和内容寻址存储。
- Flash Translation Layer、Wear Leveling 和日志结构文件系统。
- OTA 灰度发布、设备分组、失败率监控和远程诊断。
- 基于故障注入的升级可靠性验证与安全评估。