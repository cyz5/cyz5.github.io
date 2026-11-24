

## 1. 学习目标

### 理解

- 理解 Cortex-M MPU 的硬件定位：**通过地址范围、访问权限、执行权限、内存属性和安全属性约束软件访问**。
- 理解 MPU Region、Region Number、优先级覆盖、Subregion Disable 和背景区域的关系。
- 理解 Memory Type：Normal、Device、Strongly-ordered，以及 Shareable、Cacheable、Bufferable 属性。
- 理解 MPU 对 Thread Mode、Handler Mode、特权态和非特权态的不同约束。
- 理解 MemManage Fault 的触发条件、故障升级和故障现场定位。

### 掌握

- 掌握 Cortex-M3/M4/M7/M33 MPU 的基本配置流程。
- 掌握 Flash、SRAM、外设、DMA 缓冲区、共享内存和任务栈的典型区域配置。
- 掌握 Region 大小、基地址对齐、最小区域大小和权限编码。
- 掌握 MPU 开启前后的 `DSB`、`ISB` 使用要求。
- 掌握 RTOS 中按任务切换 MPU 配置的方法。
- 掌握 MemManage Handler 的现场解析和非法访问地址识别。

### 精通

- 精通区域重叠时的优先级覆盖规则和高低优先级设计。
- 精通 Cortex-M7 Cache、DMA 和 MPU 内存属性之间的一致性关系。
- 精通 XN、RO、Privileged-only、Unprivileged-only 组合形成的权限模型。
- 精通 MPU 配置对实时性、上下文切换、代码布局和栈预算的影响。
- 精通 MPU 保护边界、权限升级、指针验证和 SVC 系统调用安全设计。
- 精通 ARMv8-M 中 PMSAv8、TrustZone、SAU/IDAU 与 MPU 的协同关系。

### 能够设计

- 能够设计适用于裸机、RTOS、Bootloader 和工业控制器的 MPU 地址布局。
- 能够设计基于 MPU 的任务隔离、驱动隔离、共享内存和安全服务接口。
- 能够设计具备栈溢出检测、故障记录和故障恢复能力的内存保护框架。
- 能够设计满足实时性和功能安全要求的 MPU 配置审计与测试方案。
- 能够量化 MPU 区域数量、切换开销、内存浪费和故障响应时间。

---

## 2. 前置要求

### 知识要求

- Cortex-M 异常模型、Thread Mode、Handler Mode、MSP、PSP。
- ARMv7-M 或 ARMv8-M 编程模型。
- C 语言指针、数组越界、函数指针和内存布局。
- Flash、SRAM、外设寄存器、DMA 和 Cache 基础。
- 链接脚本、Section、启动代码和向量表。
- RTOS 任务、上下文切换、特权态和系统调用。

### 技能要求

- 能阅读 CMSIS `core_cm*.h` 中的 MPU 定义。
- 能修改链接脚本，将代码、数据和共享缓冲区放入指定区域。
- 能使用 GDB/J-Link 读取 `MPU->RNR`、`RBAR`、`RASR`、`SCB->CFSR` 等寄存器。
- 能编写异常 Handler 并解析自动压入的异常栈帧。
- 能使用故障注入验证权限边界和栈保护。
- 能测量 Cache、MPU 配置和任务切换对实时性的影响。

---

## 3. 技术概述

### 3.1 MPU 的核心定义

MPU 是一种**硬件地址访问控制单元**。它根据当前访问的：

- 地址；
- 访问类型；
- 当前处理器模式；
- 当前特权级；
- 指令取址或数据访问；
- 读、写权限；
- 内存属性；

判断访问是否允许。

如果访问违反 MPU 配置，处理器产生 **MemManage Fault**。如果 MemManage Fault 未启用，通常会升级为 HardFault。

MPU 主要解决：

- 任务之间的内存隔离；
- 只读代码和常量保护；
- 外设寄存器权限控制；
- 栈溢出检测；
- 数据执行防护；
- 驱动和应用的权限边界；
- DMA 缓冲区属性控制；
- 故障影响范围缩小。

MPU **不是 MMU**：

|对比项|MPU|MMU|
|---|---|---|
|地址转换|不支持|支持虚拟地址到物理地址|
|页面换入换出|不支持|支持|
|区域数量|少量固定 Region|通常大量页表项|
|硬件复杂度|低|高|
|实时性|高、确定性较好|可能存在 TLB/缺页抖动|
|典型系统|Cortex-M RTOS|Cortex-A Linux|
|保护粒度|区域|页面|

### 3.2 主流实现分支

|分支|典型内核|主要特性|
|---|---|---|
|ARMv7-M MPU|Cortex-M3/M4/M7|基于 Region 的 PMSA|
|ARMv8-M Baseline MPU|Cortex-M23|简化区域保护|
|ARMv8-M Mainline MPU|Cortex-M33/M55/M85|PMSAv8、权限和属性能力增强|
|TrustZone + MPU|Cortex-M23/M33 等|安全域与非安全域隔离|
|厂商 MPU 扩展|部分 MCU|Region 数量、属性或权限有额外差异|

### 3.3 MPU 的保护边界

MPU 只能保护**处理器通过该内核访问的内存事务**。以下情况需要额外注意：

- DMA 是否经过 MPU 检查，取决于 MCU 总线架构；很多 Cortex-M MCU 的 DMA **不受 CPU MPU 直接限制**。
- 外设 DMA 可能访问任务禁止访问的 RAM。
- Cache 属性配置错误会导致数据一致性问题，但不一定触发 MPU Fault。
- 某些调试访问、系统总线访问可能有独立权限路径。
- MPU 不能阻止已经具有足够权限的代码主动读写其他区域。
- MPU 不能替代输入校验、控制流保护、栈金丝雀和看门狗。

---

## 4. 核心特性横向对比

### 4.1 权限类型对比

|配置|特权读|特权写|非特权读|非特权写|典型用途|
|---|---|---|---|---|---|
|`NO_ACCESS`|否|否|否|否|保留区、栈下方 guard|
|`PRIV_RO_URO`|是|否|是|否|只读代码/常量|
|`PRIV_RW_URO`|是|是|是|否|共享只读数据、特权更新|
|`FULL_ACCESS`|是|是|是|是|任务私有 RAM|
|`PRIV_RO`|是|否|否|否|仅内核代码|
|`PRIV_RW`|是|是|否|否|内核数据、外设|
|`PRIV_RW_U RW`|是|是|是|是|应用可读写共享区|

CMSIS 枚举名称可能因版本不同略有差异，应以目标芯片的 `core_cm*.h` 为准。

### 4.2 Region 大小对比

在典型 ARMv7-M MPU 中：

Size=2N+1 bytesSize=2N+1 bytes

其中 `SIZE` 字段编码通常为：

N=log⁡2(Size)−1N=log2​(Size)−1

例如：

|期望大小|SIZE 字段|
|---|---|
|32 B|4|
|64 B|5|
|128 B|6|
|256 B|7|
|1 KiB|9|
|4 KiB|11|
|32 KiB|14|
|64 KiB|15|
|1 MiB|19|

要求：

- **区域大小必须是 2 的幂**。
- **基地址必须按区域大小对齐**。
- 典型 ARMv7-M 最小 Region 大小为 32 字节。
- 实际芯片可能有额外限制，必须检查芯片参考手册。

### 4.3 内存类型对比

|类型|顺序要求|可缓存|适用对象|典型风险|
|---|---|---|---|---|
|Normal|可乱序、可合并|可选|Flash、SRAM、DMA Buffer|Cache 一致性、排序误解|
|Device|访问具设备语义|通常不可缓存|外设寄存器、MMIO|访问宽度和顺序要求|
|Strongly Ordered|强顺序|否|严格顺序外设访问|性能较低、现代内核较少使用|
|Shareable Normal|多主设备共享语义|可选|CPU/DMA/多核共享 RAM|属性与 Cache 需一致|
|Non-shareable Normal|单处理器局部数据|可选|任务私有数据|DMA 访问时可能配置错误|

### 4.4 配置方式对比

|方式|优点|缺点|适用场景|
|---|---|---|---|
|直接操作寄存器|可控、无依赖|可读性差、易编码错误|启动代码、底层验证|
|CMSIS `ARM_MPU_Region_t`|可读、可移植性较好|受 CMSIS 版本影响|通用驱动和系统初始化|
|RTOS MPU Port|与任务生命周期集成|Region 资源有限|安全任务隔离|
|静态链接脚本布局|地址和权限可审计|灵活性低|固件、Bootloader|
|动态重配置|灵活|切换开销和竞态复杂|任务切换、特权服务|

---

## 5. 底层原理与功能特性深度解析

## 5.1 MPU 寄存器结构

典型 ARMv7-M MPU 具有：

```
MPU->TYPE     实现能力、Region 数量
MPU->CTRL     MPU 总开关、背景区域、Handler 行为
MPU->RNR      当前 Region 编号
MPU->RBAR     Region 基地址及有效位
MPU->RASR     Region 属性、权限、大小、使能
```

典型配置寄存器逻辑：

```
RBAR:
[31:5]  Region Base Address
[4]     VALID
[3:0]   Region Number

RASR:
[31:29] 内存属性 TEX
[28]    Shareable
[27]    Cacheable
[26]    Bufferable
[21:19] 权限 AP
[28?]    XN 位置依具体寄存器定义
[18:1]  Region Size
[0]     Enable
```

实际位布局以目标架构手册和 CMSIS 头文件为准，不应自行复制其他内核的寄存器定义。

### 5.1.1 Region 数量

```
uint32_t mpu_region_count(void)
{
    return (MPU->TYPE >> MPU_TYPE_DREGION_Pos) &
           MPU_TYPE_DREGION_Msk;
}
```

常见实现数量：

- 8 个 Region；
- 16 个 Region；
- 某些较新实现提供更多配置能力。

Region 数量有限，因此 MPU 设计本质上是一个**权限分配和空间布局优化问题**。

---

## 5.2 区域匹配与覆盖规则

访问某个地址时，MPU 会判断地址落在哪些 Region 中。如果多个 Region 重叠：

> **编号更高的 Region 通常具有更高覆盖优先级。**

示例：

```
Region 0：整个 SRAM，RW，可执行关闭
Region 1：任务私有 RAM，RW
Region 2：任务私有 RAM 中的只读表，RO
Region 7：任务栈底部 Guard，NO_ACCESS
```

由于 Region 7 最高，栈 Guard 可以覆盖 Region 0 的整体 SRAM 权限。

### 设计原则

- 低编号 Region 放大范围、默认属性。
- 高编号 Region 放例外、保护边界和 Guard。
- 不要依赖隐含重叠关系，必须在设计文档中列出地址和优先级。
- 变更 Region 编号时必须重新审核所有覆盖关系。

---

## 5.3 背景区域与 PRIVDEFENA

`MPU->CTRL` 中的 `PRIVDEFENA` 常用于允许特权代码使用默认内存映射。

典型选择：

|设置|特权访问未匹配区域|非特权访问未匹配区域|
|---|---|---|
|`PRIVDEFENA = 0`|受 MPU 限制，未匹配通常 Fault|Fault|
|`PRIVDEFENA = 1`|可使用默认内存映射|仍受 MPU 区域限制|

生产系统常见策略：

- **强隔离模式**：`PRIVDEFENA = 0`。
- **兼容传统驱动模式**：`PRIVDEFENA = 1`，但必须明确特权代码可访问的默认空间。

对于任务隔离，通常至少要求：

```
非特权任务：只能访问显式授予的 Region
特权 Handler：能够访问内核资源
```

---

## 5.4 XN：禁止数据区域执行

`XN` 表示 Execute Never。设置后，处理器不能从该 Region 取指。

推荐配置：

|区域|XN|
|---|---|
|Flash 代码|0|
|Flash 常量|1|
|普通 SRAM|1|
|栈|1|
|DMA 缓冲区|1|
|外设寄存器|1|
|共享消息区|1|

代码执行防护是阻止栈溢出后跳转到注入代码的关键手段之一，但要注意：

- XN 不能防止数据被修改。
- 如果攻击者能修改已有代码或合法函数指针，仍可能形成控制流攻击。
- XN 必须与栈不可执行、只读代码、CFI、指针校验协同使用。

---

## 5.5 访问权限编码

典型权限语义可以抽象为：

```
AP = 000：无访问
AP = 001：特权 RW，非特权无访问
AP = 010：特权 RW，非特权 RO
AP = 011：全权限 RW
AP = 101：特权 RO，非特权无访问
AP = 110：特权 RO，非特权 RO
```

实际编码和 CMSIS 枚举请以具体内核版本为准。

### 工程化封装

```
#include <stdint.h>
#include <stdbool.h>
#include "core_cm4.h"

typedef enum {
    MPU_ACCESS_NONE = 0,
    MPU_ACCESS_PRIV_RW,
    MPU_ACCESS_PRIV_RW_URO,
    MPU_ACCESS_FULL,
    MPU_ACCESS_PRIV_RO,
    MPU_ACCESS_RO
} mpu_access_t;

typedef struct {
    uint32_t base;
    uint32_t size;
    mpu_access_t access;
    bool execute;
    bool shareable;
    bool cacheable;
    bool bufferable;
    uint8_t subregion_disable;
} mpu_region_config_t;

static bool is_power_of_two(uint32_t value)
{
    return value >= 32U && ((value & (value - 1U)) == 0U);
}

static bool mpu_region_valid(const mpu_region_config_t *config)
{
    if (config == NULL) {
        return false;
    }

    if (!is_power_of_two(config->size)) {
        return false;
    }

    if ((config->base & (config->size - 1U)) != 0U) {
        return false;
    }

    return true;
}
```

---

## 5.6 Subregion Disable

当 Region 大小至少为 256 字节时，通常可将区域分为 8 个等大子区域，每个子区域大小为：

SubregionSize=RegionSize8SubregionSize=8RegionSize​

例如 4 KiB Region：

SubregionSize=40968=512 bytesSubregionSize=84096​=512 bytes

用途：

- 在一个大 Region 中裁剪无效空间。
- 实现不规则区域的近似覆盖。
- 构造栈底 Guard 或空洞。

限制：

- 不能替代任意大小区域。
- 粒度较粗。
- 对小型任务内存可能造成较大内部碎片。
- 关闭所有子区域后的行为应结合实现确认。

---

## 5.7 Region 配置流程

生产级 MPU 初始化流程：

```
1. 关闭 MPU
2. 禁止相关中断或保证无并发访问
3. 清理所有旧 Region
4. 配置低编号默认 Region
5. 配置代码、数据、外设和共享区
6. 配置高编号 Guard/例外 Region
7. 清理相关状态
8. 开启 MPU
9. 执行 DSB
10. 执行 ISB
11. 开启 MemManage Fault
```

CMSIS 风格示例：

```
#include "core_cm4.h"

static void mpu_disable(void)
{
    MPU->CTRL = 0U;
    __DSB();
    __ISB();
}

static void mpu_enable(bool privileged_default_map)
{
    uint32_t ctrl = MPU_CTRL_ENABLE_Msk;

    if (privileged_default_map) {
        ctrl |= MPU_CTRL_PRIVDEFENA_Msk;
    }

    MPU->CTRL = ctrl;
    __DSB();
    __ISB();
}

static void mpu_clear_all_regions(void)
{
    const uint32_t count = mpu_region_count();

    for (uint32_t i = 0U; i < count; ++i) {
        MPU->RNR = i;
        MPU->RASR = 0U;
        MPU->RBAR = 0U;
    }
}
```

实际项目中建议优先使用厂商提供的 CMSIS MPU 宏，以避免手工构造属性位。

---

## 5.8 静态系统 MPU 配置示例

以下示例以典型 Cortex-M4/M7 地址布局为例，地址必须替换为目标 MCU 的真实映射。

```
#include "core_cm7.h"

#define FLASH_BASE_ADDR       0x08000000UL
#define FLASH_REGION_SIZE     (1024UL * 1024UL)

#define SRAM_BASE_ADDR        0x20000000UL
#define SRAM_REGION_SIZE      (256UL * 1024UL)

#define PERIPH_BASE_ADDR      0x40000000UL
#define PERIPH_REGION_SIZE    (512UL * 1024UL)

#define SHARED_BASE_ADDR      0x20040000UL
#define SHARED_REGION_SIZE    (16UL * 1024UL)

void system_mpu_init(void)
{
    ARM_MPU_Region_t regions[] = {
        /*
         * Region 0：Flash 代码和只读数据
         * RO，允许执行，Normal memory，Cacheable。
         */
        {
            .RBAR = ARM_MPU_RBAR(0,
                                  FLASH_BASE_ADDR),
            .RASR = ARM_MPU_RASR(0,
                                  ARM_MPU_AP_RO,
                                  ARM_MPU_CACHEABLE,
                                  ARM_MPU_CACHEABLE,
                                  ARM_MPU_TEX_LEVEL0,
                                  0U,
                                  0U,
                                  ARM_MPU_REGION_SIZE_1MB)
        },

        /*
         * Region 1：SRAM 数据和栈
         * RW，XN，Normal memory。
         */
        {
            .RBAR = ARM_MPU_RBAR(1,
                                  SRAM_BASE_ADDR),
            .RASR = ARM_MPU_RASR(1,
                                  ARM_MPU_AP_FULL,
                                  0U,
                                  1U,
                                  ARM_MPU_TEX_LEVEL0,
                                  1U,
                                  0U,
                                  ARM_MPU_REGION_SIZE_256KB)
        },

        /*
         * Region 2：外设寄存器
         * RW，XN，Device memory，不缓存。
         */
        {
            .RBAR = ARM_MPU_RBAR(2,
                                  PERIPH_BASE_ADDR),
            .RASR = ARM_MPU_RASR(2,
                                  ARM_MPU_AP_FULL,
                                  0U,
                                  1U,
                                  ARM_MPU_TEX_LEVEL0,
                                  0U,
                                  0U,
                                  ARM_MPU_REGION_SIZE_512KB)
        },

        /*
         * Region 7：共享消息区，禁止执行。
         * 若需要非特权任务访问，应根据其接口需求选择权限。
         */
        {
            .RBAR = ARM_MPU_RBAR(7,
                                  SHARED_BASE_ADDR),
            .RASR = ARM_MPU_RASR(7,
                                  ARM_MPU_AP_FULL,
                                  0U,
                                  1U,
                                  ARM_MPU_TEX_LEVEL0,
                                  1U,
                                  0U,
                                  ARM_MPU_REGION_SIZE_16KB)
        }
    };

    ARM_MPU_Disable();

    ARM_MPU_Load(regions,
                 sizeof(regions) / sizeof(regions[0]));

    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);

    __DSB();
    __ISB();

    fault_system_init();
}
```

注意：不同 CMSIS 版本中 `ARM_MPU_RASR()` 参数顺序和 Cache/Shareable 宏定义可能不同。**编译通过不代表属性语义正确**，必须对照目标内核和芯片手册审核。

---

## 5.9 Fault 触发与 MemManage Handler

常见 MemManage Fault：

- 访问 `NO_ACCESS` Region。
- 非特权代码写入只读区域。
- 从 XN 区域取指。
- 违反 MPU Region 的特权限制。
- 异常入栈或出栈访问了受保护区域。
- 返回地址、栈指针或上下文导致权限错误。

### MemManage Fault 栈帧解析

```
#include <stdint.h>
#include "core_cm4.h"

typedef struct {
    uint32_t r0;
    uint32_t r1;
    uint32_t r2;
    uint32_t r3;
    uint32_t r12;
    uint32_t lr;
    uint32_t pc;
    uint32_t xpsr;
} exception_frame_t;

typedef struct {
    uint32_t magic;
    uint32_t pc;
    uint32_t lr;
    uint32_t cfsr;
    uint32_t mmfar;
    uint32_t shcsr;
    uint32_t task_id;
} memmanage_record_t;

#define MEMMANAGE_MAGIC 0x4D4D464CUL

__attribute__((section(".noinit.fault")))
static volatile memmanage_record_t g_memmanage_record;

__NO_RETURN static void memmanage_record_and_reset(
    const exception_frame_t *frame)
{
    __disable_irq();

    g_memmanage_record.magic = MEMMANAGE_MAGIC;
    g_memmanage_record.cfsr = SCB->CFSR;
    g_memmanage_record.shcsr = SCB->SHCSR;
    g_memmanage_record.task_id = scheduler_current_task_id();

    if ((SCB->CFSR & SCB_CFSR_MMARVALID_Msk) != 0U) {
        g_memmanage_record.mmfar = SCB->MMFAR;
    } else {
        g_memmanage_record.mmfar = UINT32_MAX;
    }

    if (frame != NULL) {
        g_memmanage_record.pc = frame->pc;
        g_memmanage_record.lr = frame->lr;
    }

    __DSB();
    NVIC_SystemReset();

    for (;;) {
        __NOP();
    }
}

__attribute__((naked)) void MemManage_Handler(void)
{
    __asm volatile (
        "tst lr, #4          \n"
        "ite eq              \n"
        "mrseq r0, msp       \n"
        "mrsne r0, psp       \n"
        "b memmanage_record_and_reset \n"
    );
}
```

### CFSR 中的 MemManage 状态

|位|含义|
|---|---|
|`IACCVIOL`|指令取址违反 MPU 权限|
|`DACCVIOL`|数据访问违反 MPU 权限|
|`MUNSTKERR`|异常返回出栈期间发生 MPU 错误|
|`MSTKERR`|异常进入压栈期间发生 MPU 错误|
|`MLSPERR`|浮点延迟保存/恢复期间发生错误|
|`MMARVALID`|MMFAR 中地址有效|

如果发生 `MSTKERR`、`MUNSTKERR`，原始异常栈帧可能不完整，不能盲目按标准 8 字节帧解析。

---

## 5.10 栈保护设计

### 方案一：栈底 Guard Region

假设任务栈向低地址增长：

```
高地址
+---------------------------+
| 任务栈可访问区域          |
|                           |
|                           |
+---------------------------+
| Guard Region: NO_ACCESS   |
+---------------------------+
低地址
```

栈向下增长越过底部 Guard 后，触发 MemManage Fault。

优点：

- 能捕获实际越界访问。
- 比单纯栈水位检测更及时。

限制：

- Region 必须满足对齐和二次幂大小约束。
- Guard 会消耗一个 Region。
- 如果栈一次跨过 Guard，且代码后续未触碰受保护区，可能需要结合栈水位检测。
- 异常入栈本身可能因 MSP/PSP 空间不足产生 `MSTKERR`。

### 方案二：栈水位检测

初始化时填充固定模式：

```
#define STACK_PATTERN 0xA5A5A5A5UL

size_t stack_unused_bytes(const uint32_t *stack_begin,
                          size_t word_count)
{
    if (stack_begin == NULL) {
        return 0U;
    }

    size_t unused_words = 0U;

    while (unused_words < word_count &&
           stack_begin[unused_words] == STACK_PATTERN) {
        unused_words++;
    }

    return unused_words * sizeof(uint32_t);
}
```

推荐组合：

```
MPU Guard：捕获即时越界
+
栈水位：评估峰值使用量
+
编译器静态栈分析：识别调用链风险
+
任务运行时监控：异常趋势告警
```

---

## 5.11 RTOS 中的 MPU 任务隔离

典型任务切换逻辑：

```
调度器选择下一个任务
    ↓
切换 PSP
    ↓
加载任务 MPU Region
    ↓
DSB/ISB
    ↓
恢复任务上下文
    ↓
返回 Thread Mode
```

任务上下文至少包含：

- PSP；
- R4～R11 等软件保存寄存器；
- CONTROL；
- MPU Region 配置；
- 浮点上下文，若使用 FPU；
- 任务权限和资源描述。

### 任务 MPU 描述符

```
#define TASK_MAX_REGIONS 5U

typedef struct {
    uint32_t rbar;
    uint32_t rasr;
} mpu_region_raw_t;

typedef struct {
    uint32_t psp;
    uint32_t control;
    uint32_t region_count;
    mpu_region_raw_t regions[TASK_MAX_REGIONS];
} task_context_t;

static void task_mpu_load(const task_context_t *task)
{
    if (task == NULL || task->region_count > TASK_MAX_REGIONS) {
        system_panic();
    }

    /*
     * 任务切换期间必须保证不会有非预期线程继续运行。
     * RTOS Port 通常在 PendSV 中完成。
     */
    for (uint32_t i = 0U; i < task->region_count; ++i) {
        MPU->RNR = i;
        MPU->RBAR = task->regions[i].rbar;
        MPU->RASR = task->regions[i].rasr;
    }

    __DSB();
    __ISB();
}
```

设计难点：

- 每个任务可用 Region 数量有限。
- 共享区、代码区、数据区、栈 Guard 可能争夺 Region。
- 任务切换时重载多个 Region 会产生固定周期开销。
- 不能允许普通任务修改 MPU 寄存器。
- MPU 配置本身属于内核状态，必须由特权代码管理。

---

## 5.12 SVC 与 MPU 的协同

非特权任务不应直接访问：

- 外设寄存器；
- 系统控制寄存器；
- 其他任务内存；
- 内核调度器数据；
- Flash 擦写控制器。

正确模型：

```
非特权任务
  ↓
SVC 指令
  ↓
Handler Mode / 特权
  ↓
参数校验
  ↓
特权驱动执行
  ↓
返回结果
```

### 指针校验

不能只检查指针非空：

```
static bool range_inside(uint32_t address,
                         uint32_t length,
                         uint32_t region_start,
                         uint32_t region_size)
{
    if (length == 0U) {
        return false;
    }

    const uint64_t end =
        (uint64_t)address + (uint64_t)length;

    const uint64_t region_end =
        (uint64_t)region_start + (uint64_t)region_size;

    return address >= region_start && end <= region_end;
}
```

检查必须覆盖：

- `address + length` 溢出；
- 起始地址；
- 结束地址；
- 对齐要求；
- 读/写方向；
- 任务是否拥有该缓冲区；
- 缓冲区是否位于允许的共享 Region；
- DMA 操作期间所有权是否转移。

---

## 5.13 Cache、DMA 与 MPU 属性

Cortex-M7 等带 Cache 的内核中，MPU 属性会影响：

- 是否允许 Cache；
- Cache 行一致性；
- 写回/直写策略；
- Shareable 属性；
- DMA 与 CPU 看到的数据版本。

### 典型问题

```
CPU 写入 Cache
    ↓
数据尚未回写 SRAM
    ↓
DMA 从 SRAM 读取旧数据
```

或者：

```
DMA 写入 SRAM
    ↓
CPU Cache 中仍保留旧数据
    ↓
CPU 读取到过期副本
```

### 方案选择

|缓冲区类型|推荐属性/操作|
|---|---|
|CPU 私有数据|Normal Cacheable|
|DMA TX 缓冲区|Clean D-Cache 后启动 DMA|
|DMA RX 缓冲区|DMA 后 Invalidate D-Cache|
|非一致性共享区|配置为 Non-cacheable，或显式维护 Cache|
|外设寄存器|Device、不可执行、不可缓存|
|描述符环|通常使用 Non-cacheable 或严格 Cache 维护|

Cache 维护示例：

```
#include "core_cm7.h"

#define CACHE_LINE_SIZE 32U

static uintptr_t align_down(uintptr_t address, uintptr_t alignment)
{
    return address & ~(alignment - 1U);
}

static uintptr_t align_up(uintptr_t address, uintptr_t alignment)
{
    return (address + alignment - 1U) & ~(alignment - 1U);
}

void dma_prepare_tx(const void *buffer, size_t length)
{
    if (buffer == NULL || length == 0U) {
        return;
    }

    const uintptr_t start =
        align_down((uintptr_t)buffer, CACHE_LINE_SIZE);
    const uintptr_t end =
        align_up((uintptr_t)buffer + length, CACHE_LINE_SIZE);

    SCB_CleanDCache_by_Addr((uint32_t *)start,
                            (int32_t)(end - start));
    __DSB();
}

void dma_complete_rx(void *buffer, size_t length)
{
    if (buffer == NULL || length == 0U) {
        return;
    }

    const uintptr_t start =
        align_down((uintptr_t)buffer, CACHE_LINE_SIZE);
    const uintptr_t end =
        align_up((uintptr_t)buffer + length, CACHE_LINE_SIZE);

    SCB_InvalidateDCache_by_Addr((uint32_t *)start,
                                 (int32_t)(end - start));
    __DSB();
}
```

注意：Cache 行对齐时不能让 DMA 缓冲区与其他 CPU 数据共享同一 Cache line，否则维护一个缓冲区可能影响邻近数据。生产系统通常对 DMA Buffer 做：

```
__attribute__((aligned(32), section(".dma_buffer")))
static uint8_t g_dma_buffer[2048];
```

---

## 5.14 ARMv8-M：MPU、SAU 与 TrustZone

在 ARMv8-M 安全系统中，至少存在以下层次：

```
安全状态/非安全状态
        ↓
SAU / IDAU：决定地址安全属性
        ↓
Secure MPU / Non-secure MPU
        ↓
特权态/非特权态访问权限
```

典型设计：

|区域|安全状态|MPU 权限|
|---|---|---|
|安全启动代码|Secure|Secure Privileged RO/X|
|密钥存储|Secure|Secure Privileged RW/XN|
|非安全应用|Non-secure|Non-secure Unprivileged|
|安全调用门|Secure Callable|受控执行|
|共享邮箱|按设计|非执行、边界明确|

安全接口还需要：

- CMSE 安全网关；
- 参数范围校验；
- 指针安全检查；
- 防重入；
- 调用频率限制；
- 安全异常处理；
- 安全/非安全栈独立预算。

---

## 6. 性能量化分析

## 6.1 测试平台和测量方法

以下为工程量级示例：

|项目|配置|
|---|---|
|MCU|STM32F767，Cortex-M7|
|主频|216 MHz|
|Flash|I-Cache/D-Cache 开启|
|编译器|GCC Arm Embedded，`-O2`|
|测量方法|DWT_CYCCNT、GPIO、ETM|
|MPU Region|8 个|
|任务切换|PendSV 中重载 5 个 Region|

实际数值会受：

- Flash 等待周期；
- Cache 命中率；
- TCM 使用；
- 编译器；
- 总线竞争；
- 是否带 FPU；
- RTOS Port 实现；

影响。

## 6.2 MPU 配置开销

代表性周期范围：

|操作|典型周期|
|---|---|
|关闭/开启 MPU + DSB/ISB|20～50|
|写入 1 个 Region|5～12|
|重载 4 个 Region|30～70|
|重载 8 个 Region|60～130|
|任务切换中重载 5 个 Region|50～110|
|触发 MemManage Fault 到 Handler|约 20～80+|

216 MHz 下：

Tcycle=1216MHz≈4.63nsTcycle​=216MHz1​≈4.63ns

重载 5 个 Region，假设 80 周期：

T=80×4.63≈370nsT=80×4.63≈370ns

如果任务每秒切换 10,000 次，则 MPU 重载占用：

U=80×10000216000000≈0.37%U=21600000080×10000​≈0.37%

如果切换频率为 100 kHz：

U≈3.7%U≈3.7%

因此 MPU 任务隔离的主要代价通常不是单次配置，而是**高频任务切换下的累计开销和 Cache/流水线扰动**。

## 6.3 内存浪费

MPU Region 必须使用二次幂大小，实际分配空间存在内部碎片。

若需求大小为 DD，Region 大小为：

R=2⌈log⁡2(D)⌉R=2⌈log2​(D)⌉

内部浪费：

W=R−DW=R−D

示例：

|需求大小|Region 大小|浪费|
|---|---|---|
|6 KiB|8 KiB|2 KiB|
|17 KiB|32 KiB|15 KiB|
|33 KiB|64 KiB|31 KiB|
|60 KiB|64 KiB|4 KiB|

当任务数据区接近但略超过二次幂时，浪费可能很大。优化方法：

- 通过链接脚本将多个只读对象合并。
- 将多个小型共享区合并为一个 Region。
- 使用 Subregion Disable。
- 通过高优先级小 Region 覆盖低优先级大 Region。
- 对高价值保护边界单独保留 Region。

## 6.4 MPU 对访问延迟的影响

在典型实现中，MPU 匹配属于硬件路径，单次普通访问通常不会引入可见的软件函数开销。但真实影响可能来自：

- Region 匹配；
- 属性导致的 Cache 行为改变；
- Shareable 导致的内存顺序限制；
- Device 类型不允许合并访问；
- 保护失败进入异常路径；
- 任务切换重载 Region 后的 `ISB` 流水线同步。

异常路径开销通常远高于普通 MPU 检查本身：

|路径|代表性成本|
|---|---|
|合法 SRAM 访问|近似普通访问|
|合法 Device 访问|受设备总线延迟影响|
|触发 MemManage|数十到数百周期，取决于 Handler|
|Fault 记录和复位|微秒到毫秒级|
|复杂日志上报|不应在 Fault Handler 中执行|

## 6.5 栈和故障预算

MPU Guard 设计要为 Fault Handler 预留独立安全栈：

```
MSP 初始区域
├─ Fault Handler 预留空间
├─ 中断嵌套空间
├─ 普通 Handler 调用栈
└─ 启动代码调用栈

PSP
├─ 任务栈可用区
└─ Guard Region
```

如果任务使用 PSP，而 MemManage Fault 发生在任务访问阶段：

- 被中断任务上下文可能压入 PSP；
- Fault Handler 运行在 MSP；
- MSP 必须在故障情况下仍然可用；
- 若 MSP 位于被破坏或被 MPU 禁止的区域，可能发生 `MSTKERR` 或 Lockup。

## 6.6 瓶颈和优化收益

|瓶颈|表现|优化|
|---|---|---|
|Region 数量不足|无法同时保护代码、栈、共享区和外设|合并同属性区域，使用重叠覆盖|
|Region 内部碎片|任务内存浪费|二次幂布局、Subregion|
|任务切换配置过多|PendSV 延迟增加|固定 Region 模板、减少每任务 Region|
|Cache 属性错误|DMA 数据旧、偶发协议错误|Non-cacheable Buffer 或显式维护|
|保护区过宽|任务越权风险|收紧区域、拆分共享接口|
|Fault Handler 栈不足|二次故障、无法记录|MSP 预留、最小化 Handler|
|异常频繁触发|CPU 被 Fault 消耗|修复边界、加入故障限流和恢复策略|
|依赖特权默认映射|隔离边界模糊|强隔离模式或建立显式访问表|

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要任务/模块之间的内存隔离？
├─ 否
│  ├─ 是否只需要防栈溢出？
│  │  ├─ 是：栈水位 + MPU Guard
│  │  └─ 否：可不启用 MPU，但必须评估安全风险
│
└─ 是
   ├─ 是否运行 RTOS？
   │  ├─ 是
   │  │  ├─ RTOS 是否有 MPU Port？
   │  │  │  ├─ 是：使用原生 MPU 任务模型
   │  │  │  └─ 否：扩展任务切换与特权服务
   │  │  └─ 任务数量是否超过 Region 预算？
   │  │     ├─ 是：使用共享 Region、模板和分组设计
   │  │     └─ 否：按任务独立配置
   │  │
   │  └─ 否
   │     ├─ 是否存在第三方/插件代码？
   │     │  ├─ 是：非特权执行 + SVC
   │     │  └─ 否：静态代码/数据/栈区域保护
   │
   ├─ 是否有 Cortex-M7/M55 Cache？
   │  ├─ 是：单独设计 DMA Buffer 属性和 Cache 维护
   │  └─ 否：仍需配置 Normal/Device 属性
   │
   ├─ 是否涉及安全域？
   │  ├─ 是：SAU/IDAU + Secure/Non-secure MPU
   │  └─ 否：使用普通 MPU
   │
   └─ 是否为硬实时系统？
      ├─ 是：量化 Region 切换、Fault 延迟和 ISR WCET
      └─ 否：优先提高隔离能力和可维护性
```

## 7.2 典型场景需求—方案—理由

|场景|方案|理由|
|---|---|---|
|RTOS 多任务隔离|PSP + 每任务 MPU Region|限制任务越权和栈破坏|
|第三方协议栈|非特权任务 + SVC|限制协议解析器访问系统资源|
|任务栈溢出|栈底 NO_ACCESS Guard|越界后立即产生 MemManage|
|Flash 代码防篡改|RO + X|阻止普通写入|
|SRAM 防代码执行|RW + XN|降低代码注入风险|
|外设驱动保护|Privileged RW + XN + Device|防止普通任务直接操作硬件|
|DMA 缓冲区|Normal Non-cacheable 或 Cache 维护|避免 CPU/DMA 数据不一致|
|共享消息区|独立、非执行、边界固定|明确数据交换和权限|
|Bootloader 与应用隔离|独立 Flash Region + VTOR|防止应用覆盖启动代码|
|安全密钥区|最高优先级保护 Region 或 Secure MPU|限制非授权访问|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **默认拒绝，显式授权**：非特权任务只获得完成任务所需的最小区域。
2. **代码只读、数据不可执行**：Flash 代码使用 RO/X，RAM 使用 RW/XN。
3. **外设统一设为 Device、XN、不可缓存**。
4. **共享内存独立布局**，不要直接把整个 SRAM 作为共享区。
5. **高优先级 Region 放置 Guard 和安全例外**。
6. **MPU 初始化只在特权启动阶段完成**。
7. **任务 MPU 配置由内核统一管理**，业务代码不可直接访问 MPU。
8. **每个 Region 在设计文档中标注起止地址、属性、拥有者和覆盖关系**。
9. **启用 MemManage Fault，而不是让所有错误直接变成 HardFault**。
10. **Fault Handler 只做最小记录、进入安全状态和复位**。
11. **对所有输入指针进行范围、长度、溢出和权限检查**。
12. **DMA 缓冲区不能只看 MPU 权限，还要看 DMA 主设备权限和 Cache 一致性**。
13. **MPU 变更后使用 `DSB` 和 `ISB`** 。
14. **Bootloader 跳转前清理 MPU、Cache、NVIC 和异常状态**。
15. **量产系统必须进行权限边界故障注入测试**。

## 8.2 区域规划模板

|Region 编号|推荐用途|典型属性|
|---|---|---|
|0|默认代码/大范围内存|低优先级、Normal|
|1|Flash 代码|RO、X、Cacheable|
|2|常量表|RO、XN、Cacheable|
|3|普通 SRAM|RW、XN|
|4|外设|RW、XN、Device|
|5|共享内存|按接口需求、XN|
|6|DMA 区|Non-cacheable 或严格 Cache 维护|
|7|Guard/安全覆盖|NO_ACCESS 或更严格属性|

实际编号需根据任务切换和 RTOS Port 重新分配。

## 8.3 工业级编码规范

- 统一封装 `mpu_region_configure()`，禁止业务代码直接写 `RBAR/RASR`。
- 运行时检查大小是否为 2 的幂、基地址是否对齐。
- 所有区域配置使用固定宽度类型。
- 禁止用未说明的魔法数字构造权限和属性位。
- 配置表应放在只读 Section，并通过静态检查验证。
- 不能用 `memcpy()` 复制包含硬件寄存器语义的 MPU 配置，除非明确验证过布局。
- 所有 SVC 接口定义输入缓冲区所有权。
- 所有共享缓冲区定义 Producer、Consumer、生命周期和 Cache 策略。
- 对 `MMFAR` 必须先检查 `MMARVALID`。
- 对 `MSTKERR/MUNSTKERR` 不得按完整栈帧无条件解析。
- Fault 记录结构增加版本号、序列号和 CRC。
- 在 CI 中自动检查：
    - Region 是否重叠；
    - Region 是否对齐；
    - 代码是否位于可执行区；
    - 栈是否位于 XN 区；
    - DMA 区是否满足 Cache 行对齐；
    - 特权接口是否有边界校验。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：Region 大小和基地址未对齐

### 错误代码

```
/* 6 KiB 不是 2 的幂，0x20001000 也不是 8 KiB 对齐地址。 */
configure_region(0x20001000UL, 6144U);
```

### 根因分析

典型 MPU 只支持二次幂大小区域，基地址必须按区域大小对齐。错误配置可能导致：

- 配置被硬件截断；
- 实际保护范围与预期不同；
- 区域覆盖其他对象；
- 运行时出现无法解释的权限 Fault。

### 正确实现

```
configure_region(0x20000000UL, 8192U);
```

或者通过链接脚本将对象放入满足边界的专用 Section。

### 风险影响

- 保护边界偏移；
- 任务访问合法数据却触发 Fault；
- 任务越权访问相邻对象。

---

## 9.2 错误二：把整个 SRAM 配为可执行可写

### 错误代码

```
/*
 * FULL_ACCESS + 允许执行。
 * 任务栈、堆和缓冲区均可被执行。
 */
mpu_configure_sram(MPU_AP_FULL, false);
```

### 根因分析

RWX 区域违反最小权限原则。缓冲区溢出后，攻击者或随机错误可能将控制流转入 SRAM 中的异常数据。

### 正确实现

```
/*
 * 普通 SRAM：读写，不可执行。
 */
mpu_configure_sram(MPU_AP_FULL, true /* XN */);

/*
 * 仅 Flash 代码区允许执行。
 */
mpu_configure_flash(MPU_AP_RO, false /* executable */);
```

### 风险影响

- 代码注入风险；
- 栈溢出后可执行恶意数据；
- 故障隔离能力下降。

---

## 9.3 错误三：用 MPU 保护 CPU，却忽略 DMA

### 错误代码

```
void task_start_dma(uint8_t *buffer, size_t length)
{
    /*
     * 只验证 buffer 属于任务 Region，
     * 但 DMA 可能继续访问整个 SRAM。
     */
    dma_start(buffer, length);
}
```

### 根因分析

许多 MCU 中 DMA 是独立总线主设备，不经过 Cortex-M CPU MPU 的权限判断。即使任务本身没有权限访问某区域，DMA 仍可能读写该区域。

### 正确实现

```
bool dma_buffer_is_valid(uintptr_t address, size_t length)
{
    return range_inside((uint32_t)address,
                        (uint32_t)length,
                        DMA_BUFFER_START,
                        DMA_BUFFER_SIZE);
}

int task_start_dma_checked(uint8_t *buffer, size_t length)
{
    if (!dma_buffer_is_valid((uintptr_t)buffer, length)) {
        return -1;
    }

    if (!is_cache_line_aligned_range(buffer, length)) {
        return -2;
    }

    dma_prepare_tx(buffer, length);
    dma_start(buffer, length);
    return 0;
}
```

### 风险影响

- DMA 修改内核数据；
- DMA 破坏其他任务栈；
- Cache 与 SRAM 数据不一致；
- 形成难以定位的内存损坏。

---

## 9.4 错误四：未启用 MemManage Fault

### 错误代码

```
void mpu_init(void)
{
    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);

    /* 忘记开启 MemManage Fault。 */
}
```

### 根因分析

MPU 违规可能升级为 HardFault，丢失具体异常分类，降低诊断精度。

### 正确实现

```
void mpu_init(void)
{
    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);

    SCB->SHCSR |= SCB_SHCSR_MEMFAULTENA_Msk;

    __DSB();
    __ISB();
}
```

### 风险影响

- 无法快速判断是数据访问、取指还是栈异常；
- 故障恢复策略无法区分任务错误和系统错误；
- 调试现场信息减少。

---

## 9.5 错误五：配置 MPU 后缺少同步屏障

### 错误代码

```
MPU->RBAR = new_rbar;
MPU->RASR = new_rasr;

/* 立即切换到新任务，未执行同步。 */
switch_to_thread_mode();
```

### 根因分析

MPU 配置更新涉及流水线和存储系统。没有 `DSB/ISB`，后续指令可能在旧属性或旧权限语义下继续执行。

### 正确实现

```
MPU->RBAR = new_rbar;
MPU->RASR = new_rasr;

__DSB();
__ISB();

switch_to_thread_mode();
```

### 风险影响

- 任务切换后偶发非法访问；
- Cache/Device 属性未及时生效；
- 只在高优化级别或高负载下复现。

---

## 9.6 错误六：只检查指针非空

### 错误代码

```
int privileged_copy(const void *user_buffer, uint32_t length)
{
    if (user_buffer == NULL) {
        return -1;
    }

    memcpy(kernel_buffer, user_buffer, length);
    return 0;
}
```

### 根因分析

非空指针可能：

- 指向任务无权访问区域；
- 跨越区域边界；
- `address + length` 溢出；
- 指向外设地址；
- 指向不可读或不可写内存；
- 指向任务栈中即将失效的对象。

### 正确实现

```
int privileged_copy_from_user(void *dst,
                              size_t dst_size,
                              const void *src,
                              size_t length)
{
    if (dst == NULL || src == NULL || length == 0U) {
        return -1;
    }

    if (length > dst_size) {
        return -2;
    }

    if (!current_task_buffer_readable(src, length)) {
        return -3;
    }

    /*
     * 对需要严格隔离的系统，还应执行访问期间的生命周期保护。
     */
    memcpy(dst, src, length);
    return 0;
}
```

### 风险影响

- SVC 接口被利用读取内核数据；
- 越界读写；
- 非确定性 MemManage Fault；
- 安全边界被绕过。

---

## 10. 多机制组合使用方案

## 10.1 技术协同架构

```
链接脚本
├─ Flash 代码：RO + X
├─ Flash 常量：RO + XN
├─ 内核 SRAM：Privileged RW + XN
├─ 任务 SRAM：按任务分区
├─ 任务栈：RW + XN
├─ 栈 Guard：NO_ACCESS
├─ DMA Buffer：Non-cacheable/Cache 维护
└─ 共享 IPC：显式授权 + XN

启动阶段
├─ 清理旧 MPU
├─ 配置系统 Region
├─ 开启 MemManage Fault
└─ DSB + ISB

任务运行
├─ PSP
├─ 非特权 Thread Mode
├─ SVC 访问内核服务
├─ PendSV 切换任务和 MPU Region
└─ RTOS 管理权限模板

故障路径
├─ MemManage Handler
├─ 读取 CFSR/MMFAR
├─ 记录任务和异常栈帧
├─ 关闭危险输出
└─ 复位或隔离故障任务
```

## 10.2 组合设计模式

### 模式一：任务隔离 + SVC 驱动代理

```
非特权任务
  └─ 只能访问任务私有区和共享邮箱
      └─ SVC
          └─ 特权驱动检查参数
              └─ 访问外设
```

适合：

- 第三方协议栈；
- 可更新应用；
- 复杂通信任务；
- 多团队模块集成。

### 模式二：栈 Guard + 水位 + PSPLIM

在支持 ARMv8-M 栈限制寄存器的内核上：

```
PSPLIM：硬件限制栈指针下界
+
MPU Guard：区域级访问禁止
+
栈水位：运行峰值统计
```

三者分别解决：

- 即时边界保护；
- 地址区域保护；
- 使用趋势和容量评估。

### 模式三：MPU + DMA + Cache 管理

```
MPU：约束 CPU 对 DMA 区的访问属性
DMA：执行数据搬运
Cache API：维护 CPU Cache 与 SRAM 一致性
所有权协议：防止 DMA 与 CPU 同时使用 Buffer
```

单独使用其中一个都不完整。

---

## 10.3 完整系统配置框架

```
#include <stdint.h>
#include <stdbool.h>
#include "core_cm7.h"

typedef enum {
    REGION_FLASH_CODE = 0U,
    REGION_KERNEL_RAM  = 1U,
    REGION_PERIPHERAL  = 2U,
    REGION_SHARED_IPC  = 3U,
    REGION_DMA_BUFFER  = 4U,
    REGION_TASK_STACK  = 6U,
    REGION_STACK_GUARD = 7U
} system_region_id_t;

static bool region_is_aligned(uint32_t base, uint32_t size)
{
    return size >= 32U &&
           (size & (size - 1U)) == 0U &&
           (base & (size - 1U)) == 0U;
}

static void configure_system_regions(void)
{
    /*
     * 实际 RBAR/RASR 属性由目标芯片地址图和 CMSIS 宏生成。
     * 以下流程强调配置顺序和架构边界。
     */
    ARM_MPU_Disable();

    /*
     * 低优先级大区域。
     */
    configure_flash_code_region(REGION_FLASH_CODE);
    configure_kernel_ram_region(REGION_KERNEL_RAM);
    configure_peripheral_region(REGION_PERIPHERAL);
    configure_shared_ipc_region(REGION_SHARED_IPC);
    configure_dma_buffer_region(REGION_DMA_BUFFER);

    /*
     * 高优先级保护例外。
     */
    configure_current_task_stack_region(REGION_TASK_STACK);
    configure_stack_guard_region(REGION_STACK_GUARD);

    __DSB();
    __ISB();

    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);

    /*
     * MPU 开启后，立即同步流水线。
     */
    __DSB();
    __ISB();

    SCB->SHCSR |= SCB_SHCSR_MEMFAULTENA_Msk;

    __DSB();
    __ISB();
}

void privileged_system_init(void)
{
    if (!region_is_aligned(TASK_STACK_BASE,
                           TASK_STACK_REGION_SIZE)) {
        system_panic();
    }

    if (!region_is_aligned(STACK_GUARD_BASE,
                           STACK_GUARD_SIZE)) {
        system_panic();
    }

    configure_system_regions();
}
```

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业控制器的协议栈隔离

### 需求

- 网络协议栈由独立团队维护。
- 协议栈存在复杂输入解析。
- 协议栈不能直接访问电机 PWM、看门狗和安全配置。
- 单个协议异常不能破坏控制任务。
- 通信吞吐不低于 20 Mbps。

### 架构设计

```
特权控制任务
├─ 电机控制
├─ 安全状态机
└─ 外设驱动

非特权协议任务
├─ 任务私有代码/数据
├─ 只读协议常量
├─ 共享 RX/TX 邮箱
└─ 通过 SVC 请求发送、参数读取和配置服务
```

### Region 规划

|Region|内容|权限|
|---|---|---|
|0|协议代码 Flash|Non-secure RO/X|
|1|协议常量|RO/XN|
|2|协议任务 RAM|RW/XN|
|3|协议任务栈|RW/XN|
|4|栈 Guard|NO_ACCESS|
|5|IPC 邮箱|RW/XN|
|6|外设|Privileged RW/XN|
|7|内核 RAM|Privileged RW/XN|

### 设计要点

- 共享邮箱不能让协议任务看到控制任务全部数据。
- SVC 接口返回复制后的值，不返回内核内部指针。
- 协议任务发生 MemManage Fault 时，仅杀死该任务或重启协议服务。
- 控制任务和安全任务仍使用独立 MSP/高优先级路径。
- 队列满时丢弃协议包，不得阻塞控制环。

---

## 11.2 案例二：Cortex-M7 Ethernet DMA Cache 一致性

### 需求

- Ethernet RX/TX 使用 DMA。
- Cortex-M7 开启 D-Cache。
- 必须避免随机 CRC 错误、旧数据和描述符失效。
- CPU 解析数据，DMA 持续搬运。

### 架构设计

```
DMA 描述符：独立 32 字节对齐 Section
RX Buffer：Non-cacheable，或每次 DMA 后 Invalidate
TX Buffer：Cacheable，但启动前 Clean
MPU：RX/TX 区域 XN
协议栈：只通过所有权标志访问 Buffer
```

### 关键所有权协议

```
DMA-owned
  -> DMA 完成
CPU-owned
  -> CPU 处理
  -> 释放/重新提交
DMA-owned
```

### 设计要点

- CPU 和 DMA 不能同时拥有一个 Buffer。
- RX Invalidate 前，必须确保 CPU 不再持有旧脏 Cache line。
- DMA Buffer 起始地址和长度最好按 Cache line 对齐。
- 描述符状态更新需要使用正确的内存屏障。
- MPU 的 Shareable 属性不能替代 Cache Clean/Invalidate。
- 性能测试必须覆盖 Cache 热、冷以及高总线负载状态。

---

## 11.3 案例三：带栈保护的电机驱动 RTOS

### 需求

- 每个任务具备独立 PSP。
- 任务栈溢出必须在越界时被检测。
- PendSV 负责任务切换。
- 任务切换额外开销不超过 1 μs。
- 发生任务故障后，系统保持安全输出关闭。

### 架构设计

```
任务
├─ PSP
├─ 任务私有 RW/XN Region
├─ 栈 RW/XN Region
└─ 栈底 NO_ACCESS Guard

PendSV
├─ 保存软件上下文
├─ 保存当前任务 PSP
├─ 加载下一个任务 MPU Region
├─ 恢复下一个任务 PSP
└─ 异常返回 Thread Mode + PSP

MemManage
├─ 判断任务 ID
├─ 记录 PC/LR/MMFAR/CFSR
├─ 关闭 PWM
└─ 重启任务或系统复位
```

### 性能预算

假设：

- CPU：216 MHz；
- 任务切换中加载 5 个 Region：80 周期；
- 软件上下文保存/恢复：160 周期；
- 其他调度开销：80 周期。

总计：

Cswitch=80+160+80=320 cyclesCswitch​=80+160+80=320 cycles

时间：

Tswitch=320216MHz≈1.48 μsTswitch​=216MHz320​≈1.48 μs

超过 1 μs 目标，需要优化：

- 减少每任务独立 Region 数；
- 使用固定系统 Region，任务只切换少量私有 Region；
- 将任务代码和常量布局合并；
- 使用更高效的 PendSV 汇编；
- 降低不必要的切换频率；
- 使用 MPU Region 模板缓存。

---

## 12. 高频问题深度答疑

### 12.1 MPU 能否防止所有内存破坏？

不能。

MPU 能防止**不符合配置权限的访问**，但不能防止：

- 合法权限范围内的越界；
- 任务破坏自身数据；
- 特权代码错误写入；
- DMA 越权；
- Cache 一致性错误；
- 被授权共享区中的协议逻辑错误；
- 控制流跳转到合法但错误的地址。

因此应与以下机制结合：

```
MPU
+ 编译器边界检查/静态分析
+ SVC 参数校验
+ DMA 所有权管理
+ 栈水位
+ 栈 Guard
+ 看门狗
+ 控制流保护
+ 故障注入
```

---

### 12.2 为什么把整个 SRAM 设置成 RW/XN 还不够？

它可以阻止从 SRAM 执行，但无法阻止：

- 任务 A 修改任务 B 数据；
- 任务修改内核对象；
- 栈溢出覆盖其他任务；
- 外设 DMA 覆盖任意 SRAM；
- 非特权任务访问敏感配置。

正确目标不是“SRAM 不可执行”这么简单，而是：

```
代码：RO/X
常量：RO/XN
任务数据：按任务隔离 RW/XN
内核数据：Privileged RW/XN
外设：Privileged RW/Device/XN
共享数据：最小范围 RW/XN
栈底：NO_ACCESS
```

---

### 12.3 `PRIVDEFENA` 是否应该始终开启？

不应该一概而论。

开启的优点：

- 兼容旧驱动；
- 特权代码可以访问未显式配置的默认映射；
- 初始化阶段更容易集成。

关闭的优点：

- 强制所有访问都显式匹配；
- 更容易发现遗漏区域；
- 隔离边界更清晰。

建议：

- **安全或高隔离系统**：优先关闭。
- **遗留驱动迁移阶段**：可以开启，但要把特权默认映射当作受控兼容机制。
- 非特权访问无论如何都不应依赖默认映射。

---

### 12.4 MPU Region 不够用怎么办？

优先级顺序建议如下：

1. 合并属性相同且生命周期一致的区域。
2. 用链接脚本重排对象。
3. 用高优先级 Region 覆盖低优先级默认区域。
4. 使用 Subregion Disable。
5. 让任务共享只读代码 Region。
6. 将多个小共享缓冲区合并为一个 IPC 区。
7. 降低不必要的任务独立权限。
8. 重新评估是否需要每个任务完全独立 MPU。
9. 使用分组任务或服务进程模型。
10. 在 ARMv8-M 中结合安全域和安全网关重新分层。

不建议通过“扩大所有 Region”简单解决，这会显著降低隔离能力。

---

### 12.5 MPU Region 重叠会不会带来安全问题？

会。重叠本身不是问题，**未审计的重叠**才是问题。

必须明确：

- 哪个 Region 覆盖哪个 Region；
- 高编号 Region 是否意外放宽权限；
- 例外 Region 是否覆盖了 Guard；
- 新增 Region 是否改变原有优先级；
- 重叠边界是否存在对齐造成的额外暴露。

建议建立机器可检查的表：

```
Region 0: 0x20000000 - 0x2003FFFF, RW/XN
Region 7: 0x2003F000 - 0x2003FFFF, NO_ACCESS
```

并在 CI 中验证：

- Guard 的编号最高；
- 代码区无 RW 覆盖；
- 外设区无用户态访问；
- 共享区不覆盖内核区。

---

### 12.6 MemManage Fault 中能否安全地读取 MMFAR？

只有在 `MMFSR.MMARVALID` 置位时，MMFAR 才能作为有效故障地址使用。

```
uint32_t cfsr = SCB->CFSR;

if ((cfsr & SCB_CFSR_MMARVALID_Msk) != 0U) {
    uint32_t address = SCB->MMFAR;
    /* 地址可用于诊断。 */
} else {
    /* 不能信任 MMFAR。 */
}
```

如果发生：

- `MSTKERR`；
- `MUNSTKERR`；
- 总线错误；
- Fault 嵌套；

则上下文和故障地址可能不完整，必须降低解析假设。

---

### 12.7 MPU 对实时性的影响是否可以忽略？

普通合法访问的硬件检查通常可以视为低开销，但以下部分不能忽略：

- 任务切换时重载 Region；
- `DSB/ISB` 引入的同步成本；
- Device/Shareable 属性对访问顺序和吞吐的影响；
- Cache 属性变化；
- Fault 路径；
- 高优先级异常对 MPU 配置切换的并发影响。

硬实时系统必须测量：

```
普通访问平均时间
Region 重载时间
任务切换 WCET
Cache 冷启动时间
DMA Buffer 维护时间
MemManage 响应时间
```

---

## 13. 课程核心总结

### 核心要点

1. MPU 是**区域级硬件访问控制器**，不是地址转换单元。
2. Region 大小通常必须是二次幂，基地址必须按区域大小对齐。
3. Region 编号越高，通常覆盖优先级越高。
4. 代码应配置为 RO/X，数据、栈、外设和共享区通常配置为 XN。
5. 外设应使用 Device 属性，不应配置为普通 Cacheable SRAM。
6. 非特权任务通过 PSP 运行，通过 SVC 请求特权服务。
7. MPU 保护 CPU 访问，不等于自动保护 DMA。
8. Cortex-M7 及以上 Cache 系统必须单独设计 DMA Buffer 一致性策略。
9. MemManage Fault 必须解析 CFSR、MMFAR 和异常栈帧。
10. 栈保护应组合使用 MPU Guard、栈水位和栈限制寄存器。
11. RTOS MPU 的核心代价是任务切换中的 Region 重载和同步屏障。
12. MPU 的安全性取决于**区域布局、接口校验、DMA 权限和故障处理的整体设计**。

### 性能排序

普通内存访问路径的确定性通常为：

```
TCM / 非缓存 SRAM
> Cache 命中 Normal SRAM
> Cache miss Normal SRAM
> Device 外设访问
> DMA/总线竞争下的共享访问
> 触发 MemManage Fault 的异常路径
```

内存保护强度通常为：

```
全局 RWX
< 全局 RW/XN
< 代码 RO/X + 数据 RW/XN
< 任务独立 Region
< 任务独立 Region + 栈 Guard + SVC
< TrustZone + Secure/Non-secure MPU + SVC/安全网关
```

### 通用选型结论

- **裸机小系统**：至少配置代码 RO/X、SRAM RW/XN、外设 Device/XN。
- **RTOS 多任务系统**：使用 PSP、非特权任务、任务 MPU Region 和 SVC。
- **高安全系统**：关闭或严格限制 `PRIVDEFENA`，所有权限显式授权。
- **Cortex-M7/M55**：MPU 属性、Cache、DMA 必须联合设计。
- **功能安全系统**：MPU 违规必须可记录、可诊断、可进入安全状态。
- **第三方代码**：优先放入非特权任务，通过最小 SVC 接口访问系统能力。

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|Region 配置|额外机制|
|---|---|---|
|Flash 代码|RO/X/Cacheable|Bootloader 保护|
|Flash 常量|RO/XN/Cacheable|校验和或签名|
|普通 SRAM|RW/XN|栈水位|
|任务栈|RW/XN|Guard/PSPLIM|
|栈 Guard|NO_ACCESS/XN|Fault 记录|
|外设寄存器|Privileged RW/Device/XN|SVC 驱动代理|
|DMA TX|Normal Cacheable 或 Non-cacheable|Clean + DSB|
|DMA RX|Normal Non-cacheable 或 Cacheable|Invalidate + DSB|
|共享 IPC|显式 RW/XN|所有权/边界校验|
|第三方代码|Non-privileged RO/X|SVC、故障隔离|
|安全数据|Secure Privileged RW/XN|TrustZone、密钥生命周期|

### 14.2 特性对比表

|特性|关键结论|
|---|---|
|MPU 类型|Region-based，不做虚拟地址转换|
|Region 大小|通常为 2 的幂|
|基地址|按 Region 大小对齐|
|区域覆盖|高编号 Region 通常优先|
|最小 Region|典型 ARMv7-M 为 32 字节|
|子区域|大 Region 可分为 8 个 Subregion|
|XN|禁止从区域取指|
|AP|控制特权/非特权读写权限|
|Device|外设寄存器常用|
|MemManage|MPU 违规异常|
|MMFAR|数据/指令违规地址，需检查 VALID|
|PRIVDEFENA|控制特权默认映射|
|同步屏障|配置后使用 DSB + ISB|
|DMA|通常不自动受 CPU MPU 约束|
|Cache|必须和 DMA Buffer 属性一起设计|
|RTOS|PSP + 非特权任务 + SVC + PendSV|
|栈保护|Guard + 水位 + PSPLIM 组合最佳|

### 14.3 最小权限配置模板

```
Flash Code:
  Privileged RO + Unprivileged RO
  Execute
  Cacheable

Flash Constant:
  Privileged RO + Unprivileged RO
  XN
  Cacheable

Kernel RAM:
  Privileged RW
  XN
  Normal

Task RAM:
  Full Access 或任务所需最小权限
  XN
  Normal

Peripheral:
  Privileged RW
  XN
  Device
  Non-cacheable

Shared IPC:
  仅暴露必要地址范围
  XN
  明确 Cache/所有权策略

Task Stack:
  RW
  XN

Stack Guard:
  NO_ACCESS
  XN
```

---

## 15. 学习效果自检

- [ ]  能解释 MPU 与 MMU 的差异。
- [ ]  能根据 Region 大小计算基地址对齐要求。
- [ ]  能解释高编号 Region 的覆盖优先级。
- [ ]  能为 Flash、SRAM、外设、共享区和栈分别选择权限。
- [ ]  能解释 XN 对栈和数据执行防护的意义。
- [ ]  能解释 `PRIVDEFENA` 的两种系统策略。
- [ ]  能配置并开启 MemManage Fault。
- [ ]  能解析 `IACCVIOL`、`DACCVIOL`、`MSTKERR`、`MUNSTKERR`。
- [ ]  能正确判断 MMFAR 是否有效。
- [ ]  能设计栈底 Guard Region。
- [ ]  能说明 MPU 为什么不能单独保护 DMA。
- [ ]  能设计 Cortex-M7 DMA Buffer 的 Cache 策略。
- [ ]  能设计非特权任务到特权驱动的 SVC 接口。
- [ ]  能对 SVC 指针执行长度、溢出、范围和权限校验。
- [ ]  能估算 RTOS 任务切换中的 MPU 重载开销。
- [ ]  能建立 Region 编号、地址、属性和所有者审计表。
- [ ]  能通过故障注入验证读、写、取指和栈越界保护。
- [ ]  能区分系统级复位、单任务重启和安全降级策略。
- [ ]  能解释 MPU、Cache、DMA、SVC 和 RTOS 的协同关系。

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：静态 MPU 地址布局

要求：

- 将 Flash 代码配置为 RO/X。
- 将 SRAM 配置为 RW/XN。
- 将外设配置为 Device/RW/XN。
- 开启 MemManage Fault。
- 对每个 Region 输出地址、大小、权限和属性。

验收：

- 代码写入失败；
- SRAM 取指失败；
- 外设区域不可被非特权访问；
- 合法访问不产生异常。

### 任务二：栈溢出检测

要求：

- 每个任务使用独立 PSP。
- 栈底设置 NO_ACCESS Guard。
- 任务创建时填充栈水位模式。
- 主动制造递归或大局部数组。

验收：

- Guard 越界立即触发 MemManage；
- Fault 记录包含任务 ID、PC、LR、CFSR 和 MMFAR；
- 能区分正常高水位和实际越界。

### 任务三：SVC 驱动代理

要求：

- 非特权任务不能直接访问 UART 或 GPIO。
- 设计 `svc_uart_write()` 和 `svc_gpio_set()`。
- 验证空指针、长度溢出、越权指针和非法枚举值。

验收：

- 合法调用可完成；
- 非法调用返回错误；
- 非特权任务直接访问外设产生 MemManage；
- SVC Handler 不信任用户指针。

### 任务四：MPU + DMA + Cache

要求：

- Cortex-M7 开启 D-Cache。
- 配置 DMA RX/TX Buffer。
- 对比 Non-cacheable 和 Cacheable + 维护 Cache 两种方案。
- 测量吞吐和 CPU 占用率。

验收：

- 连续传输无数据一致性错误；
- Buffer 无 Cache line 共享污染；
- 输出 Clean、Invalidate 和 DMA 处理时间。

### 任务五：RTOS MPU Port

要求：

- 每任务保存 PSP 和 MPU Region 配置。
- PendSV 中完成任务切换。
- 统计上下文切换周期。
- 设计任务故障隔离策略。

验收：

- 任务 A 无法访问任务 B；
- 任务栈越界触发保护；
- 任务切换 WCET 满足目标；
- 故障任务不会直接破坏控制任务状态。

## 16.2 性能测试方法

必须测试：

|指标|测量方法|
|---|---|
|MPU 开启前后访问时间|DWT 周期计数|
|Region 重载时间|PendSV 入口到返回测量|
|任务切换 WCET|覆盖最大 Region 数和最坏 Cache 状态|
|Fault 响应时间|非法访问到 Handler GPIO|
|Fault 记录可靠性|故障注入后复位读取|
|栈使用峰值|栈填充扫描 + Guard|
|DMA Cache 维护开销|Clean/Invalidate 周期统计|
|区域内部碎片|链接映像实际占用与 Region 容量比较|
|权限覆盖率|自动化读/写/取指测试|
|故障恢复时间|Fault 到安全状态或系统复位|

测试矩阵至少包括：

```
特权 / 非特权
Thread Mode / Handler Mode
Flash / SRAM / 外设
读 / 写 / 取指
Cache 开启 / 关闭
DMA 空闲 / 高负载
单层异常 / 嵌套异常
正常栈 / 临界栈深度
```

## 16.3 进阶学习方向

1. **ARMv7-M Architecture Reference Manual**
    
    - PMSA 区域匹配；
    - AP、XN、TEX/C/B/S 属性；
    - 异常升级和背景区域。
2. **ARMv8-M Architecture**
    
    - PMSAv8；
    - MAIR；
    - PSPLIM/MSPLIM；
    - TrustZone 异常和安全状态切换。
3. **RTOS MPU Port 源码**
    
    - FreeRTOS MPU；
    - Zephyr Memory Domain；
    - CMSIS-RTOS 权限模型；
    - PendSV 中 Region 重载。
4. **Cortex-M7 存储系统**
    
    - Cache line、写回、写分配；
    - TCM；
    - AXI/AHB 总线；
    - DMA 一致性。
5. **链接脚本与安全布局**
    
    - 任务独立 Section；
    - 共享 IPC Section；
    - no-init Fault Section；
    - 镜像签名和 Bootloader 防覆盖。
6. **功能安全和安全启动**
    
    - 内存隔离诊断覆盖率；
    - 栈溢出检测；
    - TrustZone；
    - Secure Boot；
    - 故障注入和安全降级。
7. **高级防护技术**
    
    - PAC/BTI，取决于内核实现；
    - CFI；
    - 栈金丝雀；
    - 控制流监控；
    - DMA 权限控制器；
    - 总线防火墙和外设安全属性。

**本课最终工程结论：MPU 的价值不在于“打开一个开关”，而在于建立一套可审计的内存所有权模型。只有当 Region 布局、任务权限、SVC 接口、DMA 所有权、Cache 属性和 Fault 恢复策略共同闭环时，MPU 才能真正形成工业级的内存隔离能力。**