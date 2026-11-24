
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解片内 Flash 的阵列结构、页/扇区/块组织方式及其与 SRAM 的本质差异。
- 理解 Flash 擦除、编程、读取、校验、错误纠正和写保护的底层机制。
- 理解“只能从 1 写成 0，不能直接从 0 写回 1”的物理约束。
- 理解 Flash 编程期间对 CPU、总线、Cache、ISR 和实时性的影响。
- 理解单 Bank、双 Bank、RWW、ECC、Option Bytes 等常见架构。

### 掌握

- 掌握片内 Flash 编程完整流程：解锁、擦除、编程、等待、状态检查、重新加锁。
- 掌握页擦除、扇区擦除、整片擦除和增量写入的选型方法。
- 掌握按字节、半字、字、双字、Flash Word 编程的适用边界。
- 掌握电源异常、复位、看门狗、写保护和异常中断下的数据一致性设计。
- 掌握 Flash 参数区、设备配置、升级标志、日志和固件镜像的可靠存储方案。

### 精通

- 能够分析 Flash 编程造成的实时性抖动、阻塞时间、总线冲突及 Cache 失效。
- 能够设计带 CRC、版本、序列号、双副本、提交标志和磨损均衡的可靠存储层。
- 能够针对不同 MCU 厂商的 Flash 控制器寄存器和 HAL 实现进行源码级审查。
- 能够处理 Flash ECC、ECC 双位错误、非法编程、对齐错误和读写保护异常。
- 能够设计支持掉电恢复、固件回滚和安全启动的片内 Flash 布局。

### 能够设计

- 能够独立设计工业级片内 Flash 参数管理模块。
- 能够设计 Bootloader 与应用程序之间的固件升级存储架构。
- 能够建立 Flash 编程时间、擦写寿命、数据可靠性和功耗的量化模型。
- 能够制定 Flash 编程驱动、测试、故障注入和量产校准方案。

---

## 2. 前置要求

### 知识要求

1. 掌握 C 语言指针、结构体、位操作、`volatile`、链接脚本和内存布局。
2. 理解 MCU 的地址空间、总线矩阵、取指过程、异常向量表和中断机制。
3. 理解 SRAM、ROM、Flash、EEPROM、外部 NOR/NAND Flash 的基本差异。
4. 了解 MCU 时钟、供电、复位、看门狗和 Cache/预取机制。
5. 了解 CRC、版本管理、双备份和事务提交思想。
6. 具备 RTOS 任务、临界区、互斥锁和优先级反转基础。

### 技能要求

1. 能够阅读 MCU Reference Manual 中的 Flash Controller 章节。
2. 能够使用调试器读取 Flash 状态寄存器、错误寄存器和保护寄存器。
3. 能够编写链接脚本，将配置区、Bootloader、应用程序和升级区分离。
4. 能够使用逻辑分析仪、示波器或 DWT/Trace 测量编程时间。
5. 能够编写掉电、复位、非法地址和错误状态测试程序。
6. 能够理解厂商 HAL 驱动，并具备绕过 HAL 直接操作寄存器的能力。

---

## 3. 技术概述

### 3.1 片内 Flash 的定义

片内 Flash 是集成在 MCU 内部、用于保存程序代码和非易失性数据的存储器。其典型特征为：

- **断电保持数据**；
- 读取速度接近 MCU 执行速度，但通常需要等待周期、预取或 Cache；
- 编程速度远低于读取速度；
- 擦除粒度大于编程粒度；
- 擦写寿命有限；
- 擦除和编程通常由 Flash 控制器完成；
- 编程期间可能限制 CPU 从同一 Bank 取指。

### 3.2 典型 Flash 层次结构

```
Flash Device
├── Bank
│   ├── Sector / Block
│   │   ├── Page
│   │   │   └── Program Unit
│   │   │       ├── Byte
│   │   │       ├── Half-word
│   │   │       ├── Word
│   │   │       └── Double-word / Flash Word
```

不同 MCU 对术语定义不同：

|术语|常见含义|工程注意事项|
|---|---|---|
|Bank|可独立操作的 Flash 分区|双 Bank 可能支持读写并行|
|Sector|较大的擦除单位|常见于 STM32、车规 MCU|
|Page|固定大小擦除单位|常见于多数 Cortex-M MCU|
|Program Unit|最小编程单位|可能是 8/16/32/64/128 bit|
|Flash Word|厂商自定义编程宽度|不等价于 CPU 的 Word|

### 3.3 主流实现分支

1. **单 Bank Flash**
    
    - 结构简单；
    - 编程或擦除期间通常不能正常从同一 Flash 取指；
    - 适合低成本、低复杂度产品。
2. **双 Bank Flash**
    
    - 一个 Bank 执行代码，另一个 Bank 编程；
    - 支持更好的在线升级和实时控制；
    - 地址映射、Bank 边界和 Cache 管理更复杂。
3. **支持 RWW 的 Flash**
    
    - Read-While-Write；
    - 写一个区域时可以读取另一区域；
    - 不是所有 RWW 都支持跨 Bank 任意读写。
4. **带 ECC 的 Flash**
    
    - 控制器对数据自动生成和校验 ECC；
    - 可纠正单比特错误，检测部分多比特错误；
    - ECC 粒度可能大于用户编程粒度。
5. **带 Option Bytes/安全区域的 Flash**
    
    - 用于读保护、写保护、启动配置、BOR、看门狗配置等；
    - 修改通常伴随特殊擦除和复位流程。

---

## 4. 核心特性横向对比

### 4.1 不同非易失性存储方案对比

|维度|片内 Flash|片内 EEPROM|外部 SPI NOR|外部 FRAM|
|---|---|---|---|---|
|读取延迟|低|中|中/高|低|
|编程速度|中|中|中|高|
|擦除要求|通常需要|通常不需要|需要|不需要|
|最小写入单位|8~128 bit|字节级|页级|字节级|
|擦写寿命|10⁴~10⁵ 次典型值|10⁵~10⁶ 次|10⁴~10⁵ 次|10¹² 次以上|
|掉电写入风险|高|中|高|低|
|占用 MCU 引脚|无|无|需要 SPI/QSPI|需要 SPI/I²C|
|成本|最低|较高|中|高|
|适合代码执行|是|否|XIP 可选|通常不适合|
|适合高频参数写入|否|一般|一般|是|

### 4.2 Flash 编程方式对比

|方式|典型编程粒度|优点|缺点|适用场景|
|---|---|---|---|---|
|字节编程|8 bit|灵活|效率低，可能不被支持|小容量配置|
|半字编程|16 bit|兼容性较好|速度和寿命一般|传统 MCU|
|字编程|32 bit|实现简单|可能存在 ECC/对齐要求|常规数据|
|双字编程|64 bit|吞吐量高|对齐要求严格|新型 Cortex-M|
|Flash Word|128 bit 或更大|与 ECC 匹配|缓冲和掉电设计复杂|高性能 MCU|

### 4.3 擦除策略对比

|策略|擦除粒度|时间|寿命利用率|数据风险|
|---|---|---|---|---|
|每次更新前擦除整页|页|中|低|掉电可能丢整页|
|双页轮换|页|中|中|可恢复|
|日志追加|编程单位|低|高|需要回收|
|预擦除|后台完成|业务路径短|中|需要预留空闲页|
|磨损均衡|多页|较高|高|实现复杂|

---

## 5. 底层原理与功能特性深度解析

## 5.1 Flash 单元的物理约束

传统浮栅 Flash 通过改变浮栅上的电荷量表示逻辑状态。工程上通常表现为：

- 擦除：将单元恢复到擦除态；
- 编程：向部分单元注入电荷；
- 编程只能改变某些位方向；
- 从已编程状态恢复到擦除态，必须执行页/扇区擦除。

通常可以抽象为：

```
擦除：0 → 1
编程：1 → 0
```

但实际逻辑极性由芯片实现决定，不能只根据抽象模型直接假设，必须遵循 Reference Manual。

### 5.1.1 编程前状态检查

```
static bool flash_can_program(uint64_t old_value, uint64_t new_value)
{
    /*
     * 典型 NOR Flash 约束：
     * 只能由 1 编程为 0。
     *
     * 若出现 old=0、new=1，则必须先擦除。
     */
    return ((old_value & new_value) == new_value);
}
```

例如：

```
old = 0xFFFF_FFFF
new = 0x1234_5678  -> 合法

old = 0x1234_5678
new = 0x1234_5679  -> 某些位尝试 0 → 1，不合法
```

但不要仅依赖软件检查。硬件控制器通常也会检测非法编程并置位错误标志。

---

## 5.2 标准 Flash 编程状态机

典型流程如下：

```
检查地址和长度
    ↓
检查供电、电压范围、时钟条件
    ↓
关闭或屏蔽可能影响流程的中断
    ↓
解锁 Flash 控制器
    ↓
清除历史错误标志
    ↓
执行页/扇区擦除
    ↓
等待 BUSY 清零
    ↓
检查擦除状态
    ↓
按最小编程单位写入
    ↓
等待 BUSY 清零
    ↓
检查编程状态
    ↓
回读校验
    ↓
重新加锁
```

### 5.2.1 通用抽象接口

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef enum {
    FLASH_OK = 0,
    FLASH_ERR_PARAM,
    FLASH_ERR_ALIGN,
    FLASH_ERR_RANGE,
    FLASH_ERR_BUSY_TIMEOUT,
    FLASH_ERR_PROGRAM,
    FLASH_ERR_ERASE,
    FLASH_ERR_VERIFY,
    FLASH_ERR_POWER,
} flash_status_t;

typedef struct {
    uintptr_t base;
    uintptr_t end;
    uint32_t  page_size;
    uint32_t  program_size;
    uint32_t  timeout_us;
} flash_region_t;

flash_status_t flash_write(const flash_region_t *region,
                           uintptr_t address,
                           const void *data,
                           size_t length);
```

这里的接口不应直接暴露厂商 HAL 的枚举和寄存器定义。应用层依赖抽象错误码，便于后续更换 MCU。

---

## 5.3 页擦除与编程的差异

擦除具有以下特点：

- 粒度较大；
- 时间明显长于单次编程；
- 峰值电流可能高于普通读取；
- 可能阻塞取指；
- 不能在擦除过程中对同一页执行普通访问；
- 某些 MCU 擦除过程中需要稳定的系统时钟；
- 擦除失败可能与供电、电压范围、温度和 Flash 老化有关。

### 5.3.1 页边界计算

```
static uintptr_t flash_page_start(uintptr_t address,
                                  uint32_t page_size)
{
    return address & ~((uintptr_t)page_size - 1U);
}

static bool is_power_of_two(uint32_t value)
{
    return value != 0U && ((value & (value - 1U)) == 0U);
}
```

如果页大小不是 2 的幂，不能使用按位掩码：

```
static uintptr_t flash_page_start_general(uintptr_t address,
                                          uint32_t page_size)
{
    return (address / page_size) * page_size;
}
```

---

## 5.4 编程粒度、对齐与补齐

假设 MCU 最小编程单位为 8 字节，则必须同时满足：

```
address % 8 == 0
length  % 8 == 0
```

如果业务数据长度不是编程粒度整数倍，需要补齐。但补齐值通常应该使用擦除态值：

```
#define FLASH_ERASED_BYTE 0xFFU

static void pad_erased_value(uint8_t *buffer,
                             size_t valid_len,
                             size_t padded_len)
{
    for (size_t i = valid_len; i < padded_len; ++i) {
        buffer[i] = FLASH_ERASED_BYTE;
    }
}
```

注意：补齐为 `0xFF` 只在对应 Flash 的擦除态确实为 `0xFF` 时成立。

---

## 5.5 参考实现：工业级写入框架

以下代码为厂商无关框架，底层寄存器操作需要由目标 MCU 实现。

```
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdbool.h>

#define FLASH_MAX_PROGRAM_SIZE 16U

typedef struct {
    uintptr_t base;
    uintptr_t end;
    uint32_t page_size;
    uint32_t program_size;
    uint32_t timeout_us;
} flash_region_t;

typedef enum {
    F_OK = 0,
    F_PARAM,
    F_RANGE,
    F_ALIGN,
    F_TIMEOUT,
    F_HW,
    F_VERIFY
} fstatus_t;

/* 以下函数由芯片适配层实现 */
extern fstatus_t flash_hw_unlock(void);
extern void      flash_hw_lock(void);
extern void      flash_hw_clear_errors(void);
extern bool      flash_hw_is_busy(void);
extern fstatus_t flash_hw_erase_page(uintptr_t page);
extern fstatus_t flash_hw_program(uintptr_t address,
                                  const uint8_t *data,
                                  size_t size);
extern uint32_t  platform_time_us(void);
extern void      platform_watchdog_kick(void);

static bool range_valid(const flash_region_t *r,
                        uintptr_t address,
                        size_t length)
{
    if (r == NULL || length == 0U) {
        return false;
    }

    if (address < r->base || address >= r->end) {
        return false;
    }

    if (length > (size_t)(r->end - address)) {
        return false;
    }

    return true;
}

static fstatus_t flash_wait_ready(uint32_t timeout_us)
{
    uint32_t start = platform_time_us();

    while (flash_hw_is_busy()) {
        platform_watchdog_kick();

        if ((uint32_t)(platform_time_us() - start) >= timeout_us) {
            return F_TIMEOUT;
        }
    }

    return F_OK;
}

static fstatus_t flash_program_aligned(const flash_region_t *r,
                                       uintptr_t address,
                                       const uint8_t *data,
                                       size_t length)
{
    if ((address % r->program_size) != 0U ||
        (length % r->program_size) != 0U) {
        return F_ALIGN;
    }

    for (size_t offset = 0U; offset < length; offset += r->program_size) {
        fstatus_t status = flash_hw_program(address + offset,
                                            &data[offset],
                                            r->program_size);
        if (status != F_OK) {
            return status;
        }

        status = flash_wait_ready(r->timeout_us);
        if (status != F_OK) {
            return status;
        }

        /*
         * 不建议每个 Program Unit 都调用通用 memcmp，
         * 但在可靠性要求高的参数区中，回读校验是合理的。
         */
        if (memcmp((const void *)(address + offset),
                   &data[offset],
                   r->program_size) != 0) {
            return F_VERIFY;
        }
    }

    return F_OK;
}
```

### 5.5.1 事务化写入

参数区不能简单地“擦除后直接写入”。必须设计提交状态。

```
#define RECORD_MAGIC       0x52454344U  /* "RECD" */
#define RECORD_COMMITTED   0x00000000U
#define RECORD_UNCOMMITTED 0xFFFFFFFFU

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint32_t version;
    uint32_t sequence;
    uint32_t payload_len;
    uint32_t payload_crc;
    uint32_t commit;
    uint8_t  payload[32];
} config_record_t;
```

推荐写入顺序：

```
1. 擦除目标页
2. 写入 magic/version/sequence/length/payload/CRC
3. 回读并验证 payload CRC
4. 最后写入 commit = 0
5. 重启后只接受 commit 正确且 CRC 正确的记录
```

原因是 `commit` 放在最后，相当于一个不可逆提交动作。若中途掉电，记录保持未提交状态。

---

## 5.6 Flash 编程期间的执行位置问题

### 单 Bank MCU

如果 CPU 正在 Flash 中执行代码，同时同一 Flash Bank 正在擦除或编程，可能产生：

- CPU 停顿；
- 指令取值失败；
- HardFault；
- 中断响应延迟；
- 看门狗未及时喂狗；
- DMA/总线访问异常。

常见解决方案：

1. 将 Flash 驱动放入 SRAM 执行；
2. 将相关中断向量和 ISR 放入 SRAM；
3. 禁止在 Flash 操作期间触发不必要中断；
4. 使用双 Bank；
5. 将写入操作放到低实时性窗口。

### 将函数放入 SRAM

```
#if defined(__GNUC__)
#define RAMFUNC __attribute__((section(".ramfunc"), noinline))
#else
#define RAMFUNC
#endif

RAMFUNC static fstatus_t flash_ram_program(...);
```

链接脚本示例：

```
.ramfunc :
{
    . = ALIGN(4);
    *(.ramfunc*)
    . = ALIGN(4);
} > RAM AT > FLASH
```

启动代码必须将 `.ramfunc` 从 Flash 拷贝到 RAM。

### 中断向量表迁移

```
SCB->VTOR = (uint32_t)&__ram_vector_table;
__DSB();
__ISB();
```

但仅迁移向量表不够，ISR 本体、其调用链和常量数据也可能仍位于 Flash。必须审查完整调用路径。

---

## 5.7 Cache、预取和流水线一致性

在带 I-Cache/D-Cache 的 MCU 上，Flash 编程后需要考虑：

- 指令 Cache 仍可能保存旧指令；
- 数据 Cache 可能保存旧数据；
- 预取缓冲区可能未失效；
- 写入后立即执行新代码可能得到旧内容。

常见处理流程：

```
SCB_CleanDCache();
SCB_InvalidateICache();
__DSB();
__ISB();
```

具体顺序和函数必须遵循目标 MCU 的手册。某些 MCU 还要求：

- 关闭并重新开启 ART/预取；
- 对指定 Bank 执行 Cache flush；
- 在修改 Option Bytes 后执行系统复位。

---

## 5.8 ECC 机制

若 Flash 以 64 bit 或 128 bit 数据配套 ECC 存储，可能出现以下问题：

1. 用户只写入部分数据；
2. 控制器内部自动生成完整 ECC；
3. 后续再对同一 ECC 行进行局部编程；
4. 新旧数据组合不满足 ECC/编程约束；
5. 出现 ECC 错误或编程错误。

因此，使用 ECC Flash 时必须确认：

- 最小可编程单位；
- ECC 保护粒度；
- 是否允许重复编程；
- 是否允许只写全 `1` 的数据；
- 单比特和双比特错误的处理方式；
- ECC 错误是否会触发 NMI、BusFault 或异常标志。

---

## 6. 性能量化分析

以下数据为**典型 Cortex-M4/M33 级 MCU、80~120 MHz、3.3 V、片内 Flash** 的工程测量量级，不代表某一具体型号。实际值必须以目标芯片手册和实测结果为准。

### 6.1 典型时间数据

|操作|典型时间|
|---|---|
|Flash 读取单字|20~100 ns|
|64 bit 编程|50~300 μs|
|256 Byte 连续编程|2~10 ms|
|2 KB 页擦除|10~50 ms|
|16 KB 页擦除|30~150 ms|
|128 KB 扇区擦除|0.5~3 s|
|RAM 中执行单次编程函数|1~10 μs，不含硬件 Busy|
|CRC32 计算，硬件 CRC|1~10 μs/KB|
|CRC32 计算，软件实现|20~200 μs/KB|

### 6.2 吞吐量计算

若 64 bit 编程耗时 200 μs：

```
吞吐量 = 8 Byte / 200 μs
       = 40 KB/s
```

若每次编程还包含 20 μs 软件准备开销：

```
有效时间 = 200 μs + 20 μs = 220 μs
吞吐量 = 8 / 220 μs ≈ 36.4 KB/s
```

如果每个 8 Byte 数据都触发一次驱动初始化，软件开销会严重降低吞吐量。因此应：

- 一次解锁，多次连续编程；
- 一次等待机制复用；
- 采用 DMA/缓冲区时批量提交；
- 不要在每个 Program Unit 之间执行复杂日志和锁操作。

### 6.3 擦写寿命估算

若某页额定擦写寿命为 `N = 10,000` 次，每次写入一次就擦除一次：

```
寿命写入次数 = 10,000 次
```

如果通过 16 页轮换：

```
理论寿命 ≈ 10,000 × 16 = 160,000 次
```

考虑温度、数据分布、异常掉电和保守降额，工程上通常再乘以 0.5~0.8 的可靠系数。

### 6.4 实时性影响

假设控制任务周期为 1 ms，而页擦除耗时 30 ms：

```
阻塞周期数 = 30 ms / 1 ms = 30 个控制周期
```

这对电机控制、功率控制、汽车底盘控制通常不可接受。优化方法：

1. 把擦除动作放在非实时任务；
2. 使用双 Bank；
3. 使用预擦除页；
4. 采用日志追加，避免高频擦除；
5. 将参数写入外部 FRAM/EEPROM；
6. 将擦除前置到系统空闲阶段。

### 6.5 功耗估算

Flash 擦除期间电流可能增加。例如：

```
V = 3.3 V
I_active = 30 mA
t_erase = 30 ms

E = V × I × t
  = 3.3 × 0.03 × 0.03
  = 2.97 mJ
```

电池设备必须考虑擦除期间的电源跌落。若电源路径储能不足，可能在擦除中途掉电，导致：

- 当前页数据不可用；
- 状态寄存器报错；
- 下次启动无法识别有效记录；
- 进入 Bootloader 故障分支。

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
需要保存的数据是什么？
├── 固件代码
│   ├── 需要在线升级？
│   │   ├── 是
│   │   │   ├── 双 Bank/RWW 可用？
│   │   │   │   ├── 是 → 双 Bank A/B 升级
│   │   │   │   └── 否 → Bootloader + 外部/备用区域
│   │   └── 否 → 单 Bank 固件存储
│   │
│   └── 需要安全启动？
│       ├── 是 → 签名验证 + 防回滚 + 受保护区域
│       └── 否 → CRC/Hash 完整性校验
│
├── 低频配置参数
│   ├── 写入频率 < 10 次/天？
│   │   ├── 是 → 双副本参数页
│   │   └── 否 → 日志追加 + 页轮换
│   └── 允许掉电丢失？
│       ├── 是 → 延迟写入
│       └── 否 → 事务提交 + 掉电保护
│
├── 高频计数器/运行日志
│   ├── 写入频率高？
│   │   ├── 是 → FRAM/EEPROM/外部存储
│   │   └── 否 → Flash 日志区
│   └── 要求寿命 > 10^6 次？
│       ├── 是 → 磨损均衡或换存储介质
│       └── 否 → 多页轮换
│
└── 出厂校准数据
    ├── 需要防篡改？
    │   ├── 是 → 写保护 + MAC/签名 + 版本
    │   └── 否 → CRC + 双副本
    └── 是否允许量产重写？
        ├── 是 → 受控解锁流程
        └── 否 → Option Bytes/硬件写保护
```

## 7.2 典型场景选型

|场景|需求|方案|理由|
|---|---|---|---|
|工业传感器参数|低频写入、掉电可靠|双页双副本|实现简单，恢复可靠|
|电机控制参数|实时性高|后台日志写入或外部 EEPROM|避免控制周期被阻塞|
|Bootloader 升级|镜像完整性、回滚|A/B 分区 + CRC/签名|防止升级中断导致变砖|
|出厂校准|不常修改、防篡改|独立区域 + 写保护 + CRC/MAC|保证校准有效性|
|运行小时计数|高频写入|日志追加 + 磨损均衡|降低单页擦写压力|
|电池产品|写入时电源不稳定|超级电容/电压检测/提交标志|防止掉电半写入|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **Flash 驱动与业务逻辑分层**  
    驱动层只负责硬件操作，存储层负责记录格式，业务层负责参数语义。
    
2. **任何写入都必须可验证**  
    至少包含回读验证；关键数据还应包含 CRC、版本和长度。
    
3. **不要在实时路径执行擦除**  
    擦除是不可预测的长时间操作，应异步化。
    
4. **不要假设 Flash 可以覆盖写**  
    每次写入前必须确认位变化是否满足硬件约束。
    
5. **提交标志必须最后写入**  
    先写数据，最后写提交标记，建立单向事务边界。
    
6. **错误状态必须显式清除和读取**  
    不要仅检查返回值，必须读取控制器错误寄存器。
    
7. **所有地址必须来自链接脚本或芯片头文件**  
    禁止在业务代码中硬编码容易变化的地址。
    
8. **Flash 区域必须在构建阶段静态检查**  
    防止 Bootloader、应用和参数区重叠。
    

## 8.2 选型决策矩阵

|需求|双副本|日志追加|A/B 镜像|外部 EEPROM/FRAM|
|---|---|---|---|---|
|实现复杂度|低|中|高|中|
|掉电可靠性|高|高|很高|高|
|高频写入|低|中/高|低|很高|
|存储容量利用率|中|高|低|高|
|适合固件升级|否|否|是|可选|
|适合配置参数|是|是|否|是|
|对实时性的影响|中|低|中|低|

## 8.3 工业级编码规范

- 所有 Flash 地址使用 `uintptr_t`，不要使用有符号整数。
- 所有硬件状态寄存器使用 `volatile`。
- 不在 Flash 编程过程中使用可能位于 Flash 的复杂日志函数。
- 处理超时，禁止无限等待 `while (BUSY) {}`。
- 将错误原因细分为：参数、对齐、范围、超时、擦除、编程、验证、ECC、保护。
- 编程完成后检查：
    - Busy；
    - 编程错误；
    - 写保护错误；
    - ECC 错误；
    - 电压/时钟异常；
    - 回读结果。
- 关键数据结构显式定义字节序和结构对齐，不直接依赖编译器默认布局。
- 不把指针、函数地址和编译器私有类型直接作为持久化格式。
- 版本升级时必须支持旧版本数据迁移或安全丢弃。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：直接覆盖写入

### 错误代码

```
*(uint32_t *)CONFIG_ADDR = new_value;
```

### 根因

- 没有执行解锁、擦除和编程流程；
- 违反 Flash 编程时序；
- 未检查对齐和编程粒度；
- 未等待 Busy 清零。

### 正确实现

```
flash_unlock();
flash_clear_errors();

flash_program(CONFIG_ADDR, &new_value, sizeof(new_value));

if (flash_wait_ready(FLASH_TIMEOUT_US) != FLASH_OK) {
    flash_lock();
    return FLASH_ERR_BUSY_TIMEOUT;
}

if (*(const uint32_t *)CONFIG_ADDR != new_value) {
    flash_lock();
    return FLASH_ERR_VERIFY;
}

flash_lock();
```

### 风险影响

- 写入失败；
- 触发 BusFault/HardFault；
- 数据随机损坏；
- 某些位保持旧值，形成隐蔽错误。

---

## 9.2 错误二：未擦除就尝试 0 → 1

### 错误代码

```
/* 旧值为 0x00，尝试写入 0xFF */
flash_program(addr, &value, sizeof(value));
```

### 根因

Flash 只能执行有限方向的位转换，不能把已编程位直接恢复为擦除态。

### 正确实现

```
uint32_t old_value = *(const uint32_t *)addr;

if (!flash_can_program(old_value, value)) {
    flash_erase_page(flash_page_start(addr, PAGE_SIZE));
}
```

### 风险影响

- 编程错误标志置位；
- 数据保持旧值或部分变化；
- 页面中其他参数被一起擦除；
- 未设计副本时造成永久数据丢失。

---

## 9.3 错误三：Flash 编程期间继续执行同一 Bank 代码

### 错误代码

```
void update_parameter(void)
{
    flash_erase_page(PARAM_PAGE);
    printf("erase done\n");  /* printf 代码和常量可能位于 Flash */
}
```

### 根因

- CPU 需要从同一 Bank 取指；
- `printf` 的代码、字符串、格式化表均可能位于 Flash；
- 中断也可能从 Flash 执行。

### 正确实现

```
RAMFUNC void flash_service_in_ram(void)
{
    /*
     * 此函数及其调用链、关键常量应放入 RAM。
     * Flash 操作期间禁止调用普通日志系统。
     */
    flash_erase_page(PARAM_PAGE);
    flash_program(PARAM_ADDR, buffer, PROGRAM_SIZE);
}
```

### 风险影响

- 随机卡死；
- 中断延迟；
- HardFault；
- 现场仅在某些温度、频率或编译优化等级下复现。

---

## 9.4 错误四：没有掉电事务机制

### 错误代码

```
void save_config(const config_t *cfg)
{
    flash_erase_page(CONFIG_PAGE);
    flash_program(CONFIG_PAGE, cfg, sizeof(*cfg));
}
```

### 根因

擦除和写入不是原子操作。任何阶段掉电都可能造成：

- 页面为空；
- 结构体只写入一半；
- CRC 未更新；
- 版本号和数据不匹配。

### 正确实现

```
void save_config_transaction(const config_t *cfg)
{
    config_record_t record;

    record.magic      = RECORD_MAGIC;
    record.version    = next_version();
    record.sequence   = next_sequence();
    record.payload_len = sizeof(*cfg);
    memcpy(record.payload, cfg, sizeof(*cfg));
    record.payload_crc = crc32(record.payload, sizeof(*cfg));
    record.commit     = RECORD_UNCOMMITTED;

    erase_target_page();
    program_record_without_commit(&record);

    if (!verify_record_without_commit(&record)) {
        return;
    }

    uint32_t commit = RECORD_COMMITTED;
    program_commit_field(&commit);
}
```

### 风险影响

- 上电后读取到半条数据；
- 参数越界；
- 控制参数异常；
- 设备进入不可恢复状态。

---

## 9.5 错误五：忽略 ECC 和编程粒度

### 错误代码

```
flash_program(addr + 3, data, 1);
```

### 根因

- 目标 MCU 最小编程单位可能为 8/16/32 字节；
- ECC 以整行数据生成；
- 地址未对齐；
- 写入过程破坏 ECC 一致性。

### 正确实现

```
uintptr_t aligned = addr & ~(PROGRAM_SIZE - 1U);
uint8_t line[PROGRAM_SIZE];

memcpy(line, (const void *)aligned, PROGRAM_SIZE);
line[addr - aligned] = new_byte;

flash_program(aligned, line, PROGRAM_SIZE);
```

### 风险影响

- 编程错误；
- ECC 单比特/双比特异常；
- 读数据触发异常；
- 数据无法通过量产测试。

---

## 10. 多机制组合使用方案

## 10.1 双副本 + CRC + 序列号 + 提交标志

### 记录格式

```
typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint16_t format_version;
    uint16_t payload_len;
    uint32_t sequence;
    uint32_t payload_crc;
    uint32_t commit;
    uint8_t  payload[64];
} nv_record_t;
```

### 读取算法

```
读取副本 A
├── magic 正确？
├── commit 已提交？
├── payload_len 合法？
├── CRC 正确？
└── 记录有效

读取副本 B
├── 同样验证
└── 记录有效

A、B 都有效？
├── 是 → 选择 sequence 较大的记录
├── 只有 A 有效 → 使用 A
├── 只有 B 有效 → 使用 B
└── 都无效 → 使用默认参数并上报故障
```

### 设计收益

- 掉电时至少保留一份旧数据；
- 可检测半写入；
- 支持版本回滚；
- 支持后续格式迁移。

---

## 10.2 日志追加 + 垃圾回收

```
页空间
├── Record 0
├── Record 1
├── Record 2
├── ...
└── 空闲区域

空间不足
├── 找出最新有效记录
├── 擦除备用页
├── 搬移最新记录
├── 切换活动页
└── 擦除旧页
```

### 日志记录状态

```
typedef enum {
    LOG_EMPTY       = 0xFF,
    LOG_WRITING     = 0x7F,
    LOG_COMMITTED   = 0x3F,
    LOG_INVALID     = 0x00
} log_state_t;
```

状态应设计为只发生单向位变化，避免频繁擦除状态字段。

---

## 10.3 RTOS 下的 Flash 存储服务

推荐架构：

```
业务任务
    ↓ Queue
Flash Storage Task
    ↓ Mutex / Critical Section
Flash HAL
    ↓
Flash Controller
```

设计原则：

- 业务任务不直接操作 Flash；
- Flash 任务串行化所有操作；
- 高优先级实时任务不等待 Flash 擦除；
- 写入请求合并和去重；
- 参数变化后延迟提交；
- 系统空闲时执行擦除；
- 启动时扫描和恢复在初始化阶段完成。

示例请求结构：

```
typedef struct {
    uint16_t key;
    uint16_t length;
    uint8_t  data[64];
    bool     force_commit;
} flash_request_t;
```

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业传感器参数保存

### 需求

- 保存采样周期、量程、报警阈值；
- 修改频率低于每天 10 次；
- 断电不能丢失最近一次有效配置；
- 页面擦除时间约 30 ms；
- 上电需要在 10 ms 内完成参数加载。

### 架构设计

```
Flash 配置区
├── Page A：记录集合
└── Page B：记录集合
```

采用：

- 记录头；
- CRC32；
- 单调递增序列号；
- 最后写提交标志；
- 两页轮换；
- 启动扫描只读取固定大小的记录头和最新记录。

### 关键代码

```
bool config_record_valid(const nv_record_t *record)
{
    if (record->magic != RECORD_MAGIC) {
        return false;
    }

    if (record->commit != RECORD_COMMITTED) {
        return false;
    }

    if (record->payload_len > sizeof(record->payload)) {
        return false;
    }

    return crc32(record->payload, record->payload_len)
           == record->payload_crc;
}
```

### 设计要点

- 新记录永远写入空闲位置；
- 不覆盖已有有效记录；
- 只有整页无空间时才擦除旧页；
- 启动时选择最大 `sequence`；
- 若两个页面均无效，恢复出厂默认值并记录故障。

---

## 11.2 案例二：双 Bank 在线固件升级

### 需求

- 主应用运行在 Bank A；
- 新固件写入 Bank B；
- 升级期间控制任务仍需运行；
- 断电后可回滚；
- 需要校验镜像并防止版本降级。

### 架构

```
Bank A
├── Bootloader
└── Active Application

Bank B
└── Downloaded Application

Metadata
├── active_bank
├── candidate_bank
├── image_size
├── image_hash
├── version
├── boot_attempts
└── commit_state
```

### 升级流程

```
下载镜像到非活动 Bank
    ↓
分块写入
    ↓
计算并验证 Hash/签名
    ↓
写入 candidate 元数据
    ↓
系统复位
    ↓
Bootloader 启动候选 Bank
    ↓
应用完成自检
    ↓
写入 confirmed
    ↓
切换 active_bank
```

### 设计要点

- 不在运行中的 Bank 上擦除当前执行代码；
- 元数据至少使用双副本；
- 候选应用必须限制启动次数；
- 启动失败后回滚；
- 版本号必须防回滚；
- 签名验证必须在跳转前完成；
- 修改 VTOR、Cache 和 MPU 配置；
- 跳转前关闭旧应用中断和 DMA。

---

## 11.3 案例三：电机控制器出厂校准数据

### 需求

- 保存电流零点、位置偏差、温度补偿系数；
- 数据量约 256 Byte；
- 量产写入 1~3 次；
- 运行过程中只读；
- 禁止现场普通用户修改。

### 方案

- 单独 Flash 区域；
- 编译时固定地址；
- 量产工具通过 Bootloader 写入；
- 写入后 CRC32 + HMAC；
- 写保护；
- 应用仅允许读取；
- 校准版本与硬件版本绑定。

### 运行时验证

```
bool calibration_load(calibration_t *out)
{
    const calibration_record_t *record =
        (const calibration_record_t *)CALIBRATION_ADDR;

    if (record->magic != CALIB_MAGIC) {
        return false;
    }

    if (record->hw_version != BOARD_HW_VERSION) {
        return false;
    }

    if (!verify_hmac(record)) {
        return false;
    }

    memcpy(out, record->payload, sizeof(*out));
    return true;
}
```

### 设计要点

- 校准数据不可仅依赖 CRC，CRC 只能发现随机错误，不能防篡改；
- 关键参数应进行范围验证；
- 读取失败时不能静默使用未初始化内存；
- 默认参数必须经过安全性评估；
- 校准区地址必须从链接脚本导出。

---

## 12. 高频问题深度答疑

### 问题一：为什么 Flash 写入前通常必须擦除？

因为编程和擦除对应不同的物理操作。编程只能改变部分位状态，而擦除才负责恢复整个页/扇区中的单元状态。即使软件希望只修改一个字节，硬件通常也无法只擦除这个字节，因此必须按页或扇区整体擦除。

### 问题二：为什么不能在中断里直接写 Flash？

主要原因有三个：

1. Flash 编程/擦除是长时间、不可预测的操作；
2. ISR 可能阻塞其他关键中断；
3. 单 Bank MCU 在 Flash Busy 时可能无法取指。

更合理的方式是 ISR 只投递事件，专用存储任务异步处理。

### 问题三：把 Flash 驱动放到 RAM 后，是否就完全安全？

不一定。以下内容也可能仍位于 Flash：

- 被调用的子函数；
- 查表数据；
- 常量字符串；
- 中断服务函数；
- C 库函数；
- 异常处理路径；
- RTOS 调度器代码。

必须检查完整调用链、链接段和中断行为。

### 问题四：CRC 能否保证 Flash 数据安全？

不能。CRC 主要用于检测随机错误和传输错误，不具备抗篡改能力，也不能保证写入事务完整性。工业级方案通常组合：

```
提交标志 + 长度检查 + CRC + 版本 + 序列号 + 范围检查
```

若存在恶意篡改风险，还需要：

```
MAC 或数字签名 + 安全密钥存储
```

### 问题五：双副本是否等同于绝对可靠？

不是。双副本只能降低单次掉电损坏概率，不能解决：

- 两个副本同时被错误擦除；
- Flash 老化；
- 软件写错地址；
- CRC 算法错误；
- 序列号回绕；
- 电磁干扰造成控制流异常。

应结合写保护、地址范围检查、故障注入、定期自检和合理的版本策略。

### 问题六：如何选择 Flash 日志和 EEPROM/FRAM？

主要看写入频率和实时性：

- 每天几次、对延迟不敏感：片内 Flash 双副本即可；
- 每分钟/每秒写入：Flash 日志或外部 EEPROM；
- 高频计数器、毫秒级写入：优先 FRAM 或专用数据存储器；
- 需要执行固件升级：必须考虑双 Bank、外部 Flash 或专用升级区域。

---

## 13. 课程核心总结

### 核心要点

1. **Flash 编程不是普通内存写入，而是受硬件状态机控制的事务流程。**
2. **编程粒度、对齐、ECC 粒度和擦除粒度必须以具体 MCU 手册为准。**
3. **擦除通常是长延迟操作，不应位于硬实时路径。**
4. **单 Bank MCU 必须关注代码执行位置和中断取指问题。**
5. **关键数据必须采用 CRC、版本、序列号和提交标志。**
6. **双副本能够提高掉电可靠性，日志追加能够提高擦写寿命。**
7. **固件升级应使用 A/B 镜像、签名验证、启动确认和回滚机制。**
8. **ECC、Cache、预取、写保护和 Option Bytes 都属于 Flash 编程正确性的一部分。**

### 性能排序

#### 读取性能

```
SRAM > Cache 命中 Flash > 普通 Flash > 外部 SPI Flash
```

#### 写入速度

```
FRAM > EEPROM > 片内 Flash 编程 > 片内 Flash 擦除
```

#### 写入寿命

```
FRAM > EEPROM > Flash + 磨损均衡 > 普通 Flash 单页反复擦写
```

#### 实现复杂度

```
单值写入 < 双副本 < 日志追加 < 磨损均衡 < A/B 升级 + 安全启动
```

### 通用选型结论

- **低频配置：双页双副本。**
- **中频配置：日志追加 + 页轮换。**
- **高频数据：外部 EEPROM/FRAM。**
- **在线升级：双 Bank 或 A/B 镜像。**
- **高实时系统：RAM 执行 Flash 驱动，或将 Flash 操作放入非实时窗口。**
- **安全产品：CRC 之外增加 MAC/签名、版本防回滚和写保护。**

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|推荐方案|
|---|---|
|低频参数|双副本 + CRC + 序列号|
|高频参数|日志追加 + 磨损均衡|
|运行计数器|FRAM/EEPROM 或批量聚合后写入|
|固件升级|A/B 分区 + Hash/签名 + 回滚|
|出厂校准|独立区域 + CRC/MAC + 写保护|
|单 Bank 实时系统|RAM 中执行驱动 + 非实时擦除|
|双 Bank 实时系统|一 Bank 执行，另一 Bank 更新|

### 14.2 编程流程表

|步骤|必须动作|
|---|---|
|1|检查地址范围|
|2|检查对齐和编程粒度|
|3|检查电压、时钟和温度条件|
|4|解锁 Flash|
|5|清除历史错误|
|6|擦除目标页/扇区|
|7|等待 Busy 清零|
|8|检查硬件错误|
|9|按最小单位编程|
|10|回读校验|
|11|写入提交标志|
|12|重新加锁|

### 14.3 故障定位表

|现象|优先检查|
|---|---|
|写入后数据不变|未解锁、未等待 Busy、写保护|
|部分数据错误|对齐、编程粒度、非法 0→1|
|擦除超时|时钟、电压、温度、寿命、供电|
|写入时 HardFault|同 Bank 取指、ISR、Cache|
|上电参数失效|无事务提交、CRC/长度错误|
|升级后无法启动|向量表、Bank 映射、Cache、签名/CRC|
|偶发 ECC 错误|非完整 ECC 行编程、Flash 老化|
|看门狗复位|擦除时间超过喂狗窗口|

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  Flash 与 SRAM 在编程、擦除和掉电保持方面有什么根本差异？
- [ ]  为什么 Flash 不能直接执行任意覆盖写？
- [ ]  目标 MCU 的最小编程单位和最小擦除单位分别是多少？
- [ ]  如何判断一次写入是否违反 0→1 约束？
- [ ]  单 Bank Flash 编程期间，CPU 和 ISR 可能发生什么问题？
- [ ]  如何将 Flash 驱动及其调用链放入 RAM？
- [ ]  为什么提交标志必须最后写入？
- [ ]  如何使用 CRC、版本和序列号选择最新有效副本？
- [ ]  如何估算一页 Flash 的理论擦写寿命？
- [ ]  如何降低高频写入对单页 Flash 的磨损？
- [ ]  ECC 的保护粒度是否等于用户可以任意写入的粒度？
- [ ]  Cache 和预取在 Flash 编程后为什么需要处理？
- [ ]  如何设计断电后可回滚的 A/B 固件升级？
- [ ]  为什么 CRC 不能替代数字签名？
- [ ]  如何验证 Flash 擦除时间不会破坏控制任务实时性？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：基础 Flash 驱动

实现：

- Flash 解锁/加锁；
- 页擦除；
- 64 bit 编程；
- Busy 超时；
- 错误状态读取；
- 回读验证。

验收标准：

- 支持非法地址检查；
- 支持未对齐错误；
- 支持超时返回；
- 不允许无限循环等待。

### 任务二：双副本参数区

实现：

- 两页配置存储；
- CRC32；
- 版本号；
- 序列号；
- 提交标志；
- 上电选择最新有效记录。

测试：

- 正常写入；
- 写入中复位；
- 写入中模拟掉电；
- CRC 破坏；
- 两个副本分别损坏。

### 任务三：Flash 日志和磨损均衡

实现：

- 多页日志；
- 记录追加；
- 页满回收；
- 页序号；
- 有效记录迁移；
- 统计每页擦除次数。

目标：

- 将单页理论寿命提升至少 8 倍；
- 验证随机掉电后数据可恢复；
- 测量平均写入延迟和最坏延迟。

### 任务四：RTOS Flash 存储服务

实现：

- 存储服务任务；
- 请求队列；
- 写入合并；
- 延迟提交；
- 非实时擦除；
- 任务超时与故障上报。

重点观察：

- 高优先级控制任务抖动；
- Flash 任务优先级；
- Mutex 持有时间；
- 擦除期间系统响应能力。

### 任务五：A/B 固件升级

实现：

- 两个应用镜像区；
- 镜像 CRC/Hash；
- 版本号；
- 启动确认；
- 失败回滚；
- 启动尝试次数限制。

进阶要求：

- 增加数字签名；
- 增加防回滚；
- 增加升级断点续传；
- 增加升级日志。

## 16.2 性能测试方法

### 测量指标

- 单次 Program Unit 时间；
- 页擦除时间；
- 扇区擦除时间；
- 最小、平均、最大延迟；
- Flash 操作期间中断延迟；
- 看门狗复位概率；
- 写入峰值电流；
- 温度和电压对编程时间的影响；
- 经过多次擦写后的失败概率。

### 推荐测量方式

```
GPIO 翻转 + 示波器
    → 测量硬件 Busy 时间

DWT CYCCNT
    → 测量软件和硬件总周期

RTOS Trace
    → 测量任务阻塞与高优先级任务抖动

电源分析仪
    → 测量擦除/编程峰值电流

故障注入器
    → 在擦除、编程、提交阶段切断电源
```

### 性能报告至少包含

```
MCU 型号
主频
供电电压
环境温度
Flash Bank/页大小
编程粒度
擦除时间 P50/P95/P99
编程时间 P50/P95/P99
中断最大延迟
失败率
测试次数
```

## 16.3 进阶学习方向

1. Flash 控制器寄存器级驱动开发。
2. ECC 编码、校验和故障注入。
3. 双 Bank/RWW 架构与 Cache 一致性。
4. Bootloader、Secure Boot 和 Trusted Firmware。
5. MCUboot、签名验证和防回滚。
6. Flash Translation Layer 与磨损均衡。
7. 外部 QSPI NOR 的 XIP、内存映射和缓存管理。
8. 车规 MCU 的 HSM、OTA 和 ASIL 数据完整性设计。
9. 断电保护、电源储能和 brown-out 检测。
10. 面向量产的 Flash 寿命筛选、参数烧录和产测自动化。