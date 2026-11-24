
## 1. 学习目标

### 理解

- 理解 **Armv8-M TrustZone** 将 MCU 执行环境划分为 Secure 与 Non-secure 两个硬件隔离安全状态的基本模型。
- 理解 SAU、IDAU、MPU、NVIC、异常入口和安全网关在隔离链路中的职责。

### 掌握

- 能配置 SAU 区域、Secure/Non-secure Flash 与 SRAM 属性。
- 能编写 Secure Gateway（NSC）接口并从 Non-secure 应用安全调用。
- 能识别 Secure Fault、非法跳转、越权 DMA 等典型问题。

### 精通

- 能分析 `SG` 指令、堆栈切换、异常状态转换及 `EXC_RETURN` 安全位。
- 能设计最小权限 Secure 服务接口，防止 TOCTOU、指针越界和 Non-secure 回调攻击。

### 能够设计

- 能完成工业设备 Secure Boot、密钥服务、OTA 验签、安全通信凭据隔离的 TrustZone 架构。
- 能制定安全分区、接口 ABI、内存保护策略及量产调试锁定策略。

## 2. 前置要求

### 知识要求

- Cortex-M 异常模型、NVIC、MSP/PSP、特权级。
- ARM Thumb-2 指令基础及链接脚本概念。
- Flash/RAM 映射、MPU、DMA 和启动流程。
- C 语言内存模型、指针边界检查、并发与中断安全。

### 技能要求

- 能阅读 CMSIS 头文件和启动文件。
- 能配置 GCC/Armclang 链接脚本。
- 能使用 J-Link、OpenOCD 或厂商调试器定位 Fault。
- 能完成 MCU Bootloader 与应用镜像的构建部署。

## 3. 技术概述

**TrustZone for Armv8-M** 是 Cortex-M23、M33、M35P、M55、M85 等内核支持的硬件安全扩展。它将系统资源划分为：

- **Secure（S）** ：安全状态，保存密钥、启动验证、权限策略和安全服务。
- **Non-secure（NS）** ：普通业务状态，运行通信、UI、控制逻辑等可被攻击面较大的代码。
- **Non-secure Callable（NSC）** ：位于 Secure Flash 的受控入口区域，允许 NS 代码通过 `SG` 指令进入 Secure 服务。

核心价值是：即使 Non-secure 固件被利用，攻击者也不能直接读取 Secure SRAM、访问密钥寄存器、重配置安全外设或跳过 Secure Boot。

主流实现分支：

|分支|作用|典型实现|
|---|---|---|
|SAU|内核侧安全属性划分|`SAU->RNR/RBAR/RLAR`|
|IDAU|芯片厂商定义的固定安全属性|STM32 GTZC、NXP TrustZone Controller|
|Secure MPU|限制 Secure 软件自身权限|Cortex-M33 MPU|
|Non-secure MPU|限制普通应用任务或模块|RTOS MPU Port|
|NSC Gateway|NS 到 S 的唯一合法调用入口|`cmse_nonsecure_entry`|
|Secure Boot|建立 Root of Trust|TF-M、MCUboot、厂商 ROM Boot|

## 4. 核心特性横向对比

|维度|无 TrustZone|TrustZone 单 Secure 服务层|TrustZone + TF-M/PSA|
|---|---|---|---|
|密钥隔离|软件约束，弱|硬件隔离|硬件隔离 + 标准化服务|
|Secure Boot|自研且易耦合|可实现|完整 RoT 链|
|NS 调用安全服务|直接函数调用|NSC Gateway|PSA IPC/直接调用模型|
|攻击面|全系统共享|Secure TCB 可控|TCB 更小、服务分区化|
|RAM 开销|最低|通常 1~8 KB|通常 16~64 KB 以上|
|适合场景|无安全需求低端设备|工业控制器、智能仪表|联网设备、支付、医疗、长生命周期设备|
|典型风险|任意漏洞全盘失守|Gateway 参数验证不足|配置复杂、服务边界设计不当|

## 5. 底层原理与功能特性深度解析

### 5.1 安全状态与地址属性

一个地址是否为 Secure，不由 C 指针类型决定，而由硬件地址属性决定：

```
CPU 发起访问
├── SAU：定义 CPU 可见区域的 S / NS / NSC 属性
├── IDAU：芯片固定或可配置的安全属性
├── 属性合并：通常 IDAU 可进一步收紧 SAU 配置
├── MPU：在当前安全状态下执行访问权限检查
└── 总线矩阵/外设安全控制器：决定 DMA、外设主机是否允许访问
```

**Secure 地址只能由 Secure 状态访问。** Non-secure 地址可由 Secure 和 Non-secure 状态访问，因此 Secure 代码不应默认信任来自 NS RAM 的数据。

### 5.2 SAU 区域配置

以下示例将 `0x08000000~0x0803FFFF` 配置为 Secure Flash，将 `0x08040000~0x0807FFFF` 配置为 Non-secure Flash，并为 NSC 保留 8 KB 区域。实际地址必须与芯片 IDAU、链接脚本一致。

```
#include "cmsis.h"
#include <stdbool.h>
#include <stdint.h>

#define SAU_REGION_SECURE_FLASH      0U
#define SAU_REGION_NSC_FLASH         1U
#define SAU_REGION_NS_FLASH          2U
#define SAU_REGION_SECURE_SRAM       3U
#define SAU_REGION_NS_SRAM           4U

static void sau_config_region(uint32_t region,
                              uint32_t base,
                              uint32_t limit,
                              bool nsc)
{
    /* SAU 区间最低 5 bit 必须为 0，limit 为区域最后一个有效字节。 */
    SAU->RNR  = region;
    SAU->RBAR = base & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (limit & SAU_RLAR_LADDR_Msk) |
                (nsc ? SAU_RLAR_NSC_Msk : 0U) |
                SAU_RLAR_ENABLE_Msk;
}

void TrustZone_SAU_Init(void)
{
    SAU->CTRL = 0U;

    sau_config_region(SAU_REGION_SECURE_FLASH,
                      0x08000000U, 0x0803FFE0U, false);

    sau_config_region(SAU_REGION_NSC_FLASH,
                      0x0803E000U, 0x0803FFE0U, true);

    sau_config_region(SAU_REGION_NS_FLASH,
                      0x08040000U, 0x0807FFE0U, false);

    sau_config_region(SAU_REGION_SECURE_SRAM,
                      0x20000000U, 0x2000FFE0U, false);

    sau_config_region(SAU_REGION_NS_SRAM,
                      0x20010000U, 0x2001FFE0U, false);

    /* ALLNS=0：未匹配区域默认 Secure，遵循默认拒绝原则。 */
    SAU->CTRL = SAU_CTRL_ENABLE_Msk;
    __DSB();
    __ISB();
}
```

工程注意点：

- SAU 配置必须在跳转 Non-secure 镜像之前完成。
- NSC 区域必须位于 Secure 区域中，不能和 Non-secure Flash 重叠。
- `ALLNS=1` 会使未覆盖区域默认变为 Non-secure，通常不适合工业安全产品。
- DMA 是否能访问 Secure SRAM，取决于芯片的外设安全控制器，不能仅依赖 SAU。

### 5.3 NSC 区域与 `SG` 指令

NS 代码不能跳转到任意 Secure 函数。唯一合法路径是跳转到 NSC 区中的函数入口，处理器要求入口前存在 **Secure Gateway (`SG`) 指令**。

使用 Arm CMSE 扩展时，编译器会生成该入口：

```
#include <arm_cmse.h>
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    SEC_OK = 0,
    SEC_ERR_ARGUMENT = -1,
    SEC_ERR_POLICY = -2,
} secure_status_t;

__attribute__((cmse_nonsecure_entry))
secure_status_t Secure_GetDeviceId(uint8_t *ns_out, uint32_t len)
{
    if ((ns_out == NULL) || (len < 16U)) {
        return SEC_ERR_ARGUMENT;
    }

    /* 校验整个输出缓冲区均可由 Non-secure 访问且可写。 */
    if (cmse_check_address_range(ns_out, 16U,
            CMSE_NONSECURE | CMSE_MPU_READWRITE) == NULL) {
        return SEC_ERR_ARGUMENT;
    }

    static const uint8_t device_id[16] = {
        0x5A, 0x13, 0xC4, 0x70, 0x11, 0x9B, 0x28, 0xF0,
        0x62, 0xD3, 0x44, 0x8E, 0xA1, 0x07, 0x3D, 0x59
    };

    for (uint32_t i = 0U; i < 16U; ++i) {
        ns_out[i] = device_id[i];
    }

    return SEC_OK;
}
```

`cmse_check_address_range()` 的作用不是普通空指针检查，而是验证地址范围的安全状态及 MPU 权限。它是 Secure Gateway 参数校验的核心机制。

### 5.4 从 Secure 跳转至 Non-secure Reset_Handler

Secure Boot 验签成功后，需要设置 Non-secure 向量表、Non-secure MSP，并通过带 `cmse_nonsecure_call` 的函数指针跳转。

```
#include <arm_cmse.h>
#include <stdint.h>

typedef void (*ns_reset_handler_t)(void) __attribute__((cmse_nonsecure_call));

#define NS_VECTOR_TABLE_ADDR    (0x08040000UL)

void Secure_JumpToNonSecure(void)
{
    const uint32_t *ns_vector = (const uint32_t *)NS_VECTOR_TABLE_ADDR;
    uint32_t ns_msp = ns_vector[0];
    uint32_t ns_reset = ns_vector[1];

    /* 基本镜像合法性检查。生产环境还需校验签名、版本和回滚计数。 */
    if ((ns_msp < 0x20010000UL) || (ns_msp >= 0x20020000UL)) {
        for (;;) {
            __WFI();
        }
    }

    SCB_NS->VTOR = NS_VECTOR_TABLE_ADDR;
    __TZ_set_MSP_NS(ns_msp);

    ns_reset_handler_t reset_handler =
        (ns_reset_handler_t)cmse_nsfptr_create((void *)ns_reset);

    __DSB();
    __ISB();
    reset_handler();
}
```

关键点：

- `cmse_nsfptr_create()` 将函数指针转换为合法的 Non-secure 调用指针。
- Non-secure 向量表必须放在 Non-secure Flash。
- Secure Boot 不能仅检查 MSP 与 Reset Handler 地址，还必须验证镜像签名、长度、版本、撤销状态和回滚策略。

### 5.5 中断与异常的安全状态

NVIC 中断可被配置为 Secure 或 Non-secure。原则如下：

|中断类型|建议归属|原因|
|---|---|---|
|Watchdog|Secure|防止 NS 停止或篡改复位策略|
|Crypto/RNG|Secure|防止密钥材料泄露|
|Flash 控制器|Secure|防止篡改固件与 Option Bytes|
|安全篡改检测|Secure|必须直接触发密钥清除或安全复位|
|UART、显示、按键|Non-secure|通常属于业务层|
|网络协议栈 DMA|多数为 Non-secure|但密钥相关缓冲区不可映射到 Secure SRAM|

**Secure 中断处理程序不可直接信任 NS 共享缓冲区。** 若中断来自 DMA 或网络外设，应先在 Secure 侧做边界、长度、状态机和完整性检查。

## 6. 性能量化分析

以下数据为 **Cortex-M33，160 MHz，IAR/Armclang -O2，零等待 SRAM，典型实现** 的量级参考；不同芯片、Flash 等待周期、编译器和 FPU 配置会改变结果。

|操作|典型周期|160 MHz 时间|主要开销|
|---|---|---|---|
|普通 C 函数调用|4~12 cycles|25~75 ns|保存 LR、分支、寄存器分配|
|NSC Gateway 空调用|35~70 cycles|219~438 ns|`SG`、状态切换、寄存器清理|
|NSC 调用含 32 字节拷贝|70~130 cycles|438~813 ns|参数检查与内存复制|
|Secure 异常入口/退出增量|20~60 cycles|125~375 ns|安全状态堆栈与上下文切换|
|SHA-256 软件计算 1 KB|80k~200k cycles|0.5~1.25 ms|CPU 指令吞吐|
|硬件 Hash 1 KB|5k~20k cycles|31~125 us|DMA、外设启动与轮询|

NSC 调用成本可近似表示为：

```
T_gateway =
T_state_switch
+ T_parameter_validation
+ T_copy_in
+ T_secure_service
+ T_copy_out
+ T_return
```

若每次调用复制 `N` 字节，SRAM 拷贝带宽为 `B` byte/s：

```
T_copy ≈ N / B
```

例如有效拷贝带宽为 80 MB/s、输入输出共 512 B：

```
T_copy ≈ 512 / (80 × 10^6) = 6.4 us
```

优化策略：

|瓶颈|优化方式|预期收益|
|---|---|---|
|高频细粒度 NSC 调用|批量 API、命令队列|Gateway 次数降低 10~100 倍|
|大块 NS 缓冲区拷贝|Secure 验证后分块读取|降低 Secure SRAM 占用|
|加密耗时|使用 Secure 硬件加密引擎/DMA|通常提升 5~30 倍|
|Secure IRQ 过多|只将真正安全关键 IRQ 设为 Secure|减少状态切换抖动|
|Secure 服务锁竞争|无锁单生产者队列或优先级设计|降低最坏响应时间|

## 7. 应用场景选型指南

```
是否保存设备私钥、证书、固件签名公钥？
├── 否
│   └── 是否存在远程 OTA 或网络攻击面？
│       ├── 否：可不使用 TrustZone，但仍应使用 MPU 和安全启动。
│       └── 是：建议最小 Secure Boot + 密钥隔离。
└── 是
    ├── 是否需要多类安全服务？
    │   ├── 否：自定义 Secure 服务层 + NSC Gateway。
    │   └── 是：采用 TF-M / PSA Firmware Framework。
    └── 是否有功能安全或高等级合规要求？
        ├── 是：Secure Boot、Anti-rollback、调试锁定、密钥生命周期管理。
        └── 否：至少实现签名验签、隔离密钥、生产调试禁用。
```

|场景|方案|理由|
|---|---|---|
|工业传感器|Secure Boot + AES/HMAC 服务|防止伪造节点和 OTA 篡改|
|智能电表|TrustZone + 安全计量密钥服务|计费密钥不可暴露给通信协议栈|
|电机驱动器|Secure Boot + 参数签名校验|防止危险控制参数被恶意刷写|
|网关设备|TF-M + PSA Crypto + ITS|服务多、证书与密钥生命周期复杂|
|离线低端执行器|MPU + 签名 Boot 可优先|TrustZone 收益可能低于实现成本|

## 8. 工程最佳实践

### 设计原则

1. **默认拒绝**：未定义 SAU 区域保持 Secure。
2. **最小 TCB**：Secure 区只保留 Boot、密钥、验签、关键控制策略。
3. **最小接口**：NSC API 使用固定长度、句柄化、批量化接口。
4. **不信任 NS 输入**：所有 NS 指针、长度、枚举、回调地址都必须验证。
5. **密钥不可出 Secure 世界**：NS 只持有 key handle，不能获得明文密钥。
6. **故障默认安全**：Secure Fault、验签失败、篡改事件应进入受控复位或降级状态。

### 选型决策矩阵

|条件|自定义 TrustZone|TF-M|
|---|---|---|
|Flash 小于 256 KB|更适合|通常压力较大|
|服务数量少于 5 个|更适合|可用但偏重|
|PSA 认证/生态要求|不优先|推荐|
|多租户安全服务|复杂|推荐|
|团队具备安全架构能力|推荐|推荐|
|快速产品化|取决于基础代码质量|推荐使用成熟移植包|

### 工业级编码规范

- Secure 接口禁止暴露裸寄存器写入能力。
- 所有长度计算必须防止整数溢出，例如 `if (len > MAX || offset > MAX - len)`。
- 密钥、派生中间值使用后应显式清零，使用防优化清零函数。
- Secure 服务错误码不能泄露敏感状态，例如不要区分“密钥不存在”和“认证失败”。
- Secure 日志不得输出密钥、挑战值、完整签名或解密后载荷。
- 量产镜像必须关闭或认证调试接口，并配置读保护、回滚保护和安全生命周期状态。

## 9. 常见错误与避坑指南

### 错误 1：Secure Gateway 未校验 Non-secure 指针

```
__attribute__((cmse_nonsecure_entry))
int Secure_Write(uint8_t *buf, uint32_t len)
{
    secure_flash_write(buf, len);
    return 0;
}
```

根因：Secure 代码解引用了未验证指针，`buf` 可能指向 Secure SRAM、无效地址或攻击者构造的边界区域。

正确实现：

```
__attribute__((cmse_nonsecure_entry))
int Secure_Write(const uint8_t *buf, uint32_t len)
{
    if ((buf == NULL) || (len == 0U) || (len > 256U)) {
        return -1;
    }

    const uint8_t *checked = cmse_check_address_range(
        buf, len, CMSE_NONSECURE | CMSE_MPU_READ);

    if (checked == NULL) {
        return -1;
    }

    uint8_t local[256];
    memcpy(local, checked, len); /* 防止检查后内容被并发修改 */
    return secure_flash_write(local, len);
}
```

风险影响：泄露 Secure 数据、越权写 Flash、触发 Secure Fault 或构造控制流攻击。

### 错误 2：检查后直接使用 NS 缓冲区

```
if (cmse_check_address_range(buf, len, CMSE_NONSECURE) != NULL) {
    verify_and_program(buf, len);
}
```

根因：这是 **TOCTOU**。NS 线程或 DMA 可在地址检查后修改内容。

正确实现：

```
uint8_t staging[512];

if ((len > sizeof(staging)) ||
    (cmse_check_address_range(buf, len,
        CMSE_NONSECURE | CMSE_MPU_READ) == NULL)) {
    return -1;
}

memcpy(staging, buf, len);
return verify_and_program(staging, len);
```

风险影响：验签对象与实际写入对象不一致，OTA 可被替换。

### 错误 3：将密钥缓冲区放入 Non-secure SRAM

```
uint8_t aes_key[32];
load_key_from_secure_storage(aes_key);
ns_network_encrypt(aes_key, packet, packet_len);
```

根因：任何 NS 漏洞、调试接口、DMA 或内存转储都可能读取密钥。

正确实现：

```
typedef uint32_t secure_key_handle_t;

__attribute__((cmse_nonsecure_entry))
int Secure_AesGcmEncrypt(secure_key_handle_t handle,
                         const uint8_t *ns_in,
                         uint32_t in_len,
                         uint8_t *ns_out,
                         uint32_t out_len)
{
    /* 在 Secure 内部按 handle 查找密钥，密钥不离开 Secure SRAM。 */
    return secure_aes_gcm_by_handle(handle, ns_in, in_len, ns_out, out_len);
}
```

风险影响：设备身份被克隆，历史通信可被解密，整个产品信任根失效。

### 错误 4：SAU 和链接脚本地址不一致

```
/* Non-secure 链接脚本 */
FLASH (rx) : ORIGIN = 0x0803E000, LENGTH = 256K
```

根因：`0x0803E000` 若属于 NSC 区，则 Non-secure 应用会覆盖 Secure Gateway。

正确实现：

```
/* NS 镜像必须从 SAU 配置的 Non-secure Flash 首地址开始。 */
FLASH (rx) : ORIGIN = 0x08040000, LENGTH = 256K
RAM   (rwx): ORIGIN = 0x20010000, LENGTH = 64K
```

风险影响：无法启动、Secure Fault、Gateway 被覆盖、镜像边界失效。

### 错误 5：把 Flash、RNG、调试控制寄存器留给 NS

```
/* NS 代码可直接擦写 Flash 或读取随机数外设状态。 */
FLASH->CR |= FLASH_CR_PER;
```

根因：仅隔离 SRAM 没有意义，攻击者可重刷 NS 或篡改 Secure 配置。

正确实现：在芯片安全控制器中将 Flash、RNG、Crypto、调试和时钟安全配置寄存器归属 Secure，并在 Secure 服务中提供有限能力接口。

风险影响：攻击者可绕过更新验证、降低安全配置或干扰安全服务。

## 10. 多机制组合使用方案

推荐组合：

```
ROM Boot
└── Secure Boot
    ├── 镜像验签与版本回滚保护
    ├── SAU / IDAU / 外设安全归属初始化
    ├── Secure MPU 配置
    ├── 密钥派生与安全存储
    └── 跳转 Non-secure Application
        ├── RTOS + Non-secure MPU
        ├── 网络协议栈
        ├── OTA 下载器
        └── 经 NSC 调用 Crypto / Storage / Attestation
```

完整服务框架：

```
typedef enum {
    SEC_CMD_VERIFY_IMAGE,
    SEC_CMD_SIGN_CHALLENGE,
    SEC_CMD_ENCRYPT,
} secure_command_t;

typedef struct {
    secure_command_t command;
    const uint8_t *input;
    uint32_t input_len;
    uint8_t *output;
    uint32_t output_len;
} secure_request_t;

__attribute__((cmse_nonsecure_entry))
int Secure_Dispatch(const secure_request_t *ns_req)
{
    secure_request_t req;

    if (cmse_check_address_range(ns_req, sizeof(req),
        CMSE_NONSECURE | CMSE_MPU_READ) == NULL) {
        return -1;
    }

    memcpy(&req, ns_req, sizeof(req));

    if ((req.input_len > 1024U) || (req.output_len > 1024U)) {
        return -1;
    }

    switch (req.command) {
    case SEC_CMD_VERIFY_IMAGE:
        return secure_verify_image(req.input, req.input_len);
    case SEC_CMD_SIGN_CHALLENGE:
        return secure_sign_challenge(req.input, req.input_len,
                                     req.output, req.output_len);
    case SEC_CMD_ENCRYPT:
        return secure_encrypt(req.input, req.input_len,
                              req.output, req.output_len);
    default:
        return -1;
    }
}
```

生产版本中，`req.input`、`req.output` 仍需逐项执行 `cmse_check_address_range()`；对于安全敏感命令应复制输入到 Secure staging buffer。

## 11. 工业级实际案例分析

### 案例 1：工业 PLC 安全 OTA

需求：远程升级控制程序，防止固件回滚、篡改和非法刷写。

架构：

```
Secure Boot
├── OTP 中的公钥哈希
├── 双镜像元数据
├── ECDSA 验签
├── 单调版本计数器
└── Secure Flash 驱动
Non-secure OTA Agent
├── 下载镜像
├── 断点续传
└── 请求 Secure 校验与切换
```

核心代码：

```
__attribute__((cmse_nonsecure_entry))
int Secure_ActivateImage(uint32_t slot, uint32_t version,
                         const uint8_t *ns_sig, uint32_t sig_len)
{
    if ((slot > 1U) || (sig_len != 64U) ||
        (cmse_check_address_range(ns_sig, sig_len,
         CMSE_NONSECURE | CMSE_MPU_READ) == NULL)) {
        return -1;
    }

    if (version <= secure_monotonic_version_read()) {
        return -2; /* 禁止回滚 */
    }

    if (!secure_verify_slot_signature(slot, ns_sig, sig_len)) {
        return -3;
    }

    return secure_mark_pending_image(slot, version);
}
```

设计要点：下载数据可位于 NS Flash，但签名验证、镜像激活标志和版本计数必须在 Secure 域完成。

### 案例 2：智能电表密钥与计量数据保护

需求：通信协议栈复杂且暴露网络攻击面，计费密钥和累计电量不能被普通应用篡改。

架构：NS 运行 DLMS/COSEM、GPRS/以太网协议栈；S 保存主密钥、执行 MAC 计算、维护带完整性保护的计量累计值。

设计要点：

- NS 永不获取主密钥。
- 电量累计值采用 `value + sequence + CMAC` 持久化。
- Secure Watchdog 防止 NS 恶意停机逃避安全策略。
- 篡改中断直接进入 Secure ISR，执行会话密钥清除。

### 案例 3：医疗便携设备身份认证

需求：设备连接云端时执行设备身份认证，私钥不可被诊断功能或蓝牙协议栈读取。

架构：Secure 域存储 ECC 私钥，并暴露 `SignChallenge()`；NS 域负责 TLS 网络传输。

设计要点：

- NS 传入挑战随机数，Secure 侧限制长度并复制。
- 签名算法与随机数发生器均在 Secure 域。
- 调试认证与量产生命周期状态由 Secure Boot 管理。
- 出厂证书更新必须经双签名授权，避免单一服务器密钥失陷。

## 12. 高频问题深度答疑

### 1. TrustZone 能替代 MPU 吗？

不能。TrustZone 解决 **Secure 与 Non-secure 的世界级隔离**；MPU 解决同一世界内部任务、驱动、协议栈之间的权限隔离。Secure 软件也可能存在漏洞，因此 Secure MPU 同样重要。

### 2. Secure 代码能否直接访问 Non-secure RAM？

可以，但不应无验证地访问。NS RAM 内容可能被并发篡改，也可能由 DMA 修改。对于命令、签名、升级包元数据，应校验后复制到 Secure 内存再处理。

### 3. NSC 函数是否越少越好？

原则上是。每个 NSC API 都是 Secure TCB 的攻击入口。接口应面向能力而不是资源，例如提供“使用密钥句柄签名”，不要提供“读取密钥地址”。

### 4. Secure Boot 后，攻击者还能替换 Non-secure 固件吗？

若实现了签名校验、受保护的启动元数据、反回滚计数和 Flash 写保护，攻击者不能运行未授权镜像。若只验证一次而允许 NS 修改启动标记，则仍可能被绕过。

### 5. DMA 能绕过 TrustZone 吗？

可能。DMA 是总线主机，具体是否具备 Secure/Non-secure 属性由芯片实现决定。必须配置 GTZC、MPC、PPC、AHB 安全控制器等厂商模块，确保 NS DMA 不可访问 Secure SRAM 或 Secure 外设。

### 6. 是否应把整个 RTOS 放在 Secure 域？

通常不应。完整 RTOS、网络协议栈、文件系统放入 Secure 域会扩大 TCB、增加补丁成本并削弱隔离价值。Secure 域应只保留最小化安全服务和必要中断处理。

## 13. 课程核心总结

- **TrustZone 的核心不是“加密”，而是硬件安全状态隔离。**
- SAU 定义地址区域属性，IDAU 与芯片安全控制器决定最终可访问性。
- NS 到 S 的唯一受控入口是 **NSC Gateway + `SG` 指令**。
- Secure Gateway 的第一原则是：**不信任任何 Non-secure 指针、长度、状态和回调。**
- 高性能排序通常为：普通函数调用 > 批量 NSC 服务 > 单次 NSC 服务 > PSA IPC 服务。
- 通用选型结论：小型工业产品采用最小 Secure Boot + 自定义 Secure 服务；复杂联网设备优先采用 **TF-M/PSA**。

## 14. 快速参考速查表

|场景|建议方案|
|---|---|
|固件防篡改|Secure Boot + 签名验签 + Flash Secure 属性|
|防止版本回退|Secure 单调计数器 + 签名元数据|
|私钥保护|Secure SRAM/安全存储 + 句柄化 Crypto API|
|网络 TLS 身份|Secure 私钥签名服务|
|OTA 更新|NS 下载，S 验签与激活|
|安全关键中断|配置为 Secure IRQ|
|协议栈隔离|NS RTOS + Non-secure MPU|

|特性|Secure|Non-secure|NSC|
|---|---|---|---|
|可访问 Secure SRAM|是|否|仅作为 Secure 代码入口|
|可调用普通 Secure 函数|是|否|入口后可调用|
|可访问 NS RAM|是，但需校验|是|取决于 Gateway 实现|
|典型内容|Boot、密钥、验签|RTOS、协议栈、业务|安全服务 API|
|信任级别|高，但仍需 MPU|不可信边界|受严格审计|

## 15. 学习效果自检

- [ ]  能解释 SAU、IDAU、MPU 和外设安全控制器的边界。
- [ ]  能独立划分 Secure、NSC、Non-secure Flash/SRAM。
- [ ]  能配置 Secure Boot 跳转到 Non-secure 向量表。
- [ ]  能使用 `cmse_check_address_range()` 校验所有 NS 输入。
- [ ]  能解释 TOCTOU 在 NS/S 共享缓冲区中的攻击路径。
- [ ]  能设计不暴露明文密钥的 NSC Crypto API。
- [ ]  能通过 Secure Fault 寄存器和调试器定位非法安全状态访问。
- [ ]  能评估 TrustZone、TF-M、MPU 的资源与维护成本。

## 16. 实践与进阶路径

1. 在 Cortex-M33 开发板上完成 Secure/Non-secure 双镜像启动，分别设置独立向量表与 MSP。
2. 实现 `Secure_GetDeviceId()`、`Secure_Random()`、`Secure_SignChallenge()` 三个 NSC 服务，并完成恶意指针测试。
3. 实现双槽 OTA：NS 下载镜像，S 验签、版本检查、镜像激活与失败回退。
4. 使用 DWT `CYCCNT` 测量普通调用、NSC 调用、PSA IPC 调用的周期数。
5. 注入攻击测试：越界指针、Secure 地址伪造、长度溢出、DMA 并发修改、旧版本镜像回滚。
6. 进阶学习 **TF-M、PSA Certified、MCUboot、Armv8-M Exception Model、Cortex-M MPU、芯片 GTZC/MPC/PPC 安全控制器**。