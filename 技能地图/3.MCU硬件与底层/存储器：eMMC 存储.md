

## 1. 学习目标

### 1.1 理解

完成本课后，应能够：

- 理解 eMMC 的内部组成：**NAND Flash、Flash Translation Layer（FTL）、控制器、ECC、坏块管理、磨损均衡、缓存与协议接口**。
- 区分 eMMC 与裸 NAND、SPI-NAND、SD 卡、UFS、SSD 的系统定位。
- 理解 eMMC 的逻辑地址模型、擦除块组织、写放大、寿命消耗与掉电一致性。
- 理解 eMMC 启动分区、RPMB、用户分区、GP 分区和分区配置机制。

### 1.2 掌握

- 掌握 eMMC 总线模式：Legacy、High-Speed、HS200、HS400。
- 掌握 eMMC 初始化、识别、分区、读写、擦除、可靠写入和异常恢复流程。
- 掌握 Linux 下通过 MMC 子系统、块设备、ioctl、sysfs、debugfs 管理 eMMC。
- 掌握 eMMC 可靠性相关参数：`EXT_CSD`、寿命估计、预 EOL、缓存、可靠写、BKOPS。
- 掌握 Boot0/Boot1、RPMB 和 User Area 的访问边界。

### 1.3 精通

- 能分析 eMMC 写延迟尖峰、GC、磨损均衡、BKOPS 对实时性的影响。
- 能定位 eMMC 初始化失败、读写超时、CRC 错误、掉电损坏、寿命耗尽等现场问题。
- 能设计适合工业控制、网关、车载终端和嵌入式 Linux 的 eMMC 存储架构。
- 能构建 eMMC 压力测试、掉电测试、寿命评估与故障诊断体系。

### 1.4 能够设计

- 能够设计完整的 **Bootloader + Linux + RootFS + 数据分区 + OTA + 日志分区 + RPMB** 存储方案。
- 能够根据容量、性能、掉电安全、寿命、温度、供应链和成本进行器件选型。
- 能够制定 eMMC 分区策略、文件系统策略、写入策略和工厂烧录流程。
- 能够设计满足工业级可靠性的 eMMC 存储抽象层和故障恢复机制。

---

## 2. 前置要求

### 2.1 知识要求

- C 语言、指针、结构体、位操作、错误处理。
- MCU 或 SoC 启动流程。
- NAND Flash 的 Page、Block、Plane、Die 基本概念。
- Linux 块设备、文件系统、设备树和驱动基础。
- DMA、中断、缓存一致性和总线时序。
- 基本的 CRC、ECC、掉电保护和事务一致性知识。

### 2.2 技能要求

- 能使用示波器或逻辑分析仪观察 CLK、CMD、DAT0~DAT7。
- 能使用 Linux 命令分析 `/sys/block/mmcblkX` 和 `/dev/mmcblkX`。
- 能编译 U-Boot、Linux Kernel 和设备树。
- 能编写块设备压力测试、顺序/随机 I/O 测试工具。
- 能分析 kernel log、MMC tracepoint、ftrace 和 IO 延迟。
- 能进行电源掉电、温度、振动和批量烧录测试。

---

## 3. 技术概述

## 3.1 eMMC 的定义

eMMC（Embedded MultiMediaCard）是将以下组件封装在一个 BGA 器件中的嵌入式存储设备：

```
+-----------------------------------------------------+
|                     eMMC Package                   |
|                                                     |
|  +----------------+       +---------------------+   |
|  | NAND Flash     | <---> | eMMC Controller     |   |
|  | SLC/TLC/MLC    |       | FTL                 |   |
|  | Bad Block      |       | ECC                 |   |
|  | Physical Pages  |       | Wear Leveling       |   |
|  +----------------+       | Garbage Collection  |   |
|                           | Power Loss Mgmt     |   |
|                           +----------+----------+   |
|                                      |              |
|                              MMC Protocol           |
+--------------------------------------+--------------+
                                       |
                         Host SoC / MCU
```

主机只看到一个类似块设备的逻辑存储器，不直接管理 NAND 的：

- 坏块；
- ECC；
- 物理擦除；
- 页编程；
- 磨损均衡；
- 垃圾回收；
- 坏块替换；
- 物理地址映射。

这部分由 eMMC 内部控制器中的 FTL 完成。

## 3.2 eMMC 的典型内部区域

|区域|作用|是否适合普通文件系统|典型用途|
|---|---|---|---|
|User Area|主用户数据区|是|RootFS、应用数据、日志|
|Boot0|启动分区|通常否|Bootloader 第一阶段|
|Boot1|启动分区|通常否|Bootloader 冗余备份|
|RPMB|防回滚、密钥、计数器|否|安全数据、认证计数器|
|General Purpose Partition|可配置专用分区|视设计而定|高可靠数据或独立区域|
|Enhanced User Data Area|增强可靠性区域|可选|关键元数据、日志|

## 3.3 eMMC 的主要版本与速度模式

|标准/模式|总线宽度|典型时钟|理论吞吐量|主要特点|
|---|---|---|---|---|
|Legacy|1/4/8 bit|20 MHz|20 MB/s 左右|兼容性最好|
|High-Speed|1/4/8 bit|26/52 MHz|26~52 MB/s 左右|主流基础模式|
|HS200|8 bit|200 MHz SDR|200 MB/s|高速单沿采样|
|HS400|8 bit|200 MHz DDR|400 MB/s|双沿传输，调试复杂|
|HS400 Enhanced Strobe|8 bit|200 MHz DDR|400 MB/s|读数据使用增强选通信号|

理论值不等于实际文件系统吞吐量。实际性能还受到以下因素限制：

- NAND 内部编程速度；
- FTL 映射；
- 写放大；
- eMMC 内部缓存；
- 主控 DMA；
- 文件系统；
- I/O 队列；
- 温度；
- 后台垃圾回收；
- 数据模式和访问随机性。

## 3.4 eMMC 与其他存储器对比

|方案|控制器集成|主机复杂度|随机写性能|掉电可靠性|适合场景|
|---|---|---|---|---|---|
|SPI NOR|否/部分|中|低|高|启动代码、参数、小容量|
|SPI-NAND|部分|高|中|取决于软件|中等容量、成本敏感|
|裸 NAND|否|很高|高|需自建|专用存储系统|
|SD 卡|是|低|不稳定|通常较弱|可插拔、消费类|
|eMMC|是|低|中高|工业型号较好|嵌入式 Linux、工业设备|
|UFS|是|中|高|高|高端 SoC、移动/车载|
|SSD|是|低|很高|取决于型号|大容量、高性能系统|

---

## 4. 核心特性横向对比

## 4.1 eMMC 与 SD 卡对比

|维度|eMMC|SD 卡|
|---|---|---|
|物理连接|BGA 焊接|插拔连接|
|机械可靠性|高|插槽接触可能失效|
|供电稳定性|主板统一设计|受插拔和卡座影响|
|性能一致性|通常较好|不同卡差异很大|
|工业温度|有工业级型号|需单独确认|
|掉电保护|可配置可靠写|普遍较弱|
|寿命可预测性|可读 EXT_CSD|通常较差|
|量产一致性|好|型号混用风险高|
|安全区域|有 RPMB|通常没有等价机制|
|推荐定位|工业产品|可移除介质、升级介质|

## 4.2 eMMC 模式对比

|模式|信号特点|优点|缺点|典型风险|
|---|---|---|---|---|
|Legacy|低速单沿|兼容性强|性能低|传输瓶颈|
|High-Speed|单沿高速|稳定、易调试|速度有限|信号完整性|
|HS200|200 MHz SDR|速度高|需要调节采样点|CMD/DAT 时序裕量|
|HS400|200 MHz DDR|吞吐最高|读写时序复杂|走线、电源、PHY 配置|
|HS400ES|增强选通|读性能更稳定|主控和器件需同时支持|设备树/PHY 配置错误|

## 4.3 分区类型对比

|分区|可否普通块读写|擦写模型|安全性|典型用途|
|---|---|---|---|---|
|User Area|是|普通块设备|一般|文件系统、镜像|
|Boot0/1|是，但需专用访问|小容量固定区域|中|启动程序|
|RPMB|否，需认证协议|带计数器的认证写|高|密钥、反回滚|
|GP Partition|是|独立逻辑区域|取决于配置|专用数据|
|Enhanced Area|是|设备相关增强模式|中高|关键数据|

---

## 5. 底层原理与功能特性深度解析

# 5.1 eMMC 启动与初始化流程

典型初始化流程如下：

```
上电
  |
  v
等待电源稳定
  |
  v
CMD0：进入 Idle State
  |
  v
CMD1：协商 OCR、电压、Busy 状态
  |
  v
CMD2：读取 CID
  |
  v
CMD3：分配 RCA
  |
  v
CMD9：读取 CSD
  |
  v
CMD7：选择卡
  |
  v
CMD8/CMD6：读取和切换 EXT_CSD / 总线模式
  |
  v
切换 4/8 bit、High-Speed/HS200/HS400
  |
  v
执行 tuning
  |
  v
注册块设备
```

不同芯片的命令细节由主控 MMC 控制器驱动完成。Linux 中通常由：

```
mmc core
  |
  +-- host controller driver
  |     +-- dw_mmc
  |     +-- sdhci
  |     +-- fsl_esdhc
  |     +-- meson-gx-mmc
  |
  +-- block layer
  |
  +-- partition parser
```

组成。

## 5.2 EXT_CSD：eMMC 的核心能力描述寄存器

`EXT_CSD` 是 512 字节数据结构，包含：

- 设备容量；
- 启动分区大小；
- 总线宽度；
- HS200/HS400 支持能力；
- 缓存配置；
- BKOPS 状态；
- 寿命估计；
- 预 EOL 信息；
- RPMB 容量；
- 分区配置；
- 可靠写支持；
- 擦除组信息；
- 高优先级中断能力。

Linux 下查看：

```
mmc extcsd read /dev/mmcblk0
```

常见输出字段：

```
CACHE_SIZE
DEVICE_LIFE_TIME_EST_TYP_A
DEVICE_LIFE_TIME_EST_TYP_B
PRE_EOL_INFO
RPMB_SIZE_MULT
PARTITION_CONFIG
ERASE_GROUP_DEF
HC_ERASE_GRP_SIZE
SEC_COUNT
CARD_TYPE
```

工程上不能只依据 `SEC_COUNT` 判断设备质量。至少需要同时检查：

1. `CARD_TYPE`；
2. `EXT_CSD_REV`；
3. `DEVICE_LIFE_TIME_EST_TYP_A/B`；
4. `PRE_EOL_INFO`；
5. `CACHE_SIZE`；
6. `REL_WR_SEC_C`；
7. `BKOPS_SUPPORT`；
8. 温度等级和 NAND 类型；
9. 厂商数据手册中的 TBW 或擦写保证。

## 5.3 FTL 与逻辑地址映射

主机发送逻辑块地址 LBA：

```
Host LBA
   |
   v
eMMC Controller
   |
   +-- Logical-to-Physical Mapping
   +-- ECC
   +-- Bad Block Management
   +-- Wear Leveling
   +-- Garbage Collection
   |
   v
NAND Physical Page / Block
```

一个逻辑写入可能导致多个物理操作：

```
逻辑覆盖写：
LBA 1000 -> New Data

内部可能执行：
1. 读取旧块中其他有效页
2. 将新数据写入新物理页
3. 更新映射表
4. 标记旧页失效
5. 后台擦除旧块
```

因此：

```
物理写入量 = 主机写入量 × 写放大系数 WAF
```

通常：

```
WAF = NAND 实际写入量 / Host 写入量
```

在顺序写、预留空间充分时，WAF 可能接近 1.1~~1.5；在小块随机覆盖写、空间接近满载、频繁同步时，可能达到 3~~10 甚至更高。实际值必须通过器件和工作负载测试测量。

## 5.4 NAND 页、块和擦除约束

NAND 的基本操作约束：

- 读取以页或多个页为单位；
- 编程以页为单位；
- 擦除以块为单位；
- 同一个物理页不能无限次重复编程；
- 擦除次数存在上限；
- 坏块可能在出厂时存在，也可能运行中产生。

eMMC 控制器通过 FTL 把这些复杂性隐藏起来，但不能消除其物理成本。

特别需要注意：

> **块设备的 4 KiB 写入，不等于 NAND 只发生 4 KiB 物理写入。**

当文件系统频繁修改小文件、日志同步、数据库提交时，eMMC 可能执行更大范围的数据搬移。

## 5.5 ECC 与数据可靠性

NAND 存储单元会受到以下影响：

- 电荷泄漏；
- 读干扰；
- 写干扰；
- 温度；
- 编程次数；
- 数据保持时间；
- 单元间耦合。

eMMC 内部使用 ECC 对 NAND 页进行纠错。常见实现可能使用 BCH、LDPC 或厂商定制方案，但主机通常无法直接控制。

当错误超过 ECC 能力时，主机可能看到：

```
mmc0: error -110 whilst initialising MMC card
mmcblk0: error -84 transferring data
blk_update_request: I/O error
mmc0: Timeout waiting for hardware interrupt
```

错误码含义需要结合上下文判断：

|错误|可能原因|
|---|---|
|`-110 ETIMEDOUT`|超时、供电、时钟、信号、设备内部 Busy|
|`-84 EILSEQ`|CRC/传输校验错误、信号完整性|
|`-5 EIO`|设备 I/O 失败|
|`-19 ENODEV`|设备消失或初始化失败|
|`-22 EINVAL`|参数、模式或分区配置错误|

## 5.6 HS200/HS400 与 tuning

高速模式下，主控需要选择合适的数据采样相位。以 HS200 为例，tuning 的目标是：

```
采样点落在数据眼图中心区域
```

可抽象为：

```
有效采样窗口 = [左边界, 右边界]
最佳采样点 = (左边界 + 右边界) / 2
```

如果眼图窗口只有 5 个 delay tap，而温度、电压和板级噪声造成采样漂移，就容易出现偶发 CRC 错误。

高速模式问题通常不是简单“降低频率”就可以结束。工程上应同时检查：

- CLK 走线长度；
- CMD/DAT 线长匹配；
- 上拉配置；
- IO 电压；
- 驱动强度；
- slew rate；
- PCB 参考平面；
- 电源纹波；
- PHY delay；
- tuning 结果；
- 温度变化下的稳定性。

设备树示例：

```
&sdhci1 {
    bus-width = <8>;
    non-removable;
    cap-mmc-highspeed;
    mmc-hs200-1_8v;
    mmc-hs400-1_8v;
    mmc-hs400-enhanced-strobe;

    vmmc-supply = <&reg_3v3>;
    vqmmc-supply = <&reg_1v8>;

    /*
     * 实际 delay 参数必须基于 SoC TRM、PHY 文档和实测 tuning 结果。
     * 不应盲目复制其他平台配置。
     */
};
```

## 5.7 Reliable Write

普通写入与可靠写入的语义不同。

普通写入：

```
Host 发起写入
  |
  v
数据可能进入 eMMC Cache
  |
  v
内部映射和 NAND 编程
```

掉电时可能出现：

- 新数据丢失；
- 旧数据被部分覆盖；
- 元数据与数据不一致；
- 文件系统日志损坏。

可靠写通常用于保证一个写操作具有更强的原子性或掉电一致性语义，但它不是“所有数据永久不丢失”的万能机制。

Linux 中常见相关机制：

- 文件系统 `fsync()`；
- 块设备 flush；
- FUA；
- eMMC reliable write；
- 设备内部 cache flush；
- 文件系统日志；
- A/B 分区；
- 双副本元数据。

示例：

```
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>

int durable_write_file(const char *path,
                       const void *data,
                       size_t len)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd < 0) {
        perror("open");
        return -1;
    }

    const unsigned char *p = data;
    size_t written = 0;

    while (written < len) {
        ssize_t n = write(fd, p + written, len - written);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("write");
            close(fd);
            return -1;
        }

        if (n == 0) {
            close(fd);
            errno = EIO;
            return -1;
        }

        written += (size_t)n;
    }

    /*
     * fsync 确保文件数据和相关元数据提交到内核/块设备路径。
     * 是否已经安全到达 NAND，还取决于块层、设备缓存和 eMMC 可靠写语义。
     */
    if (fsync(fd) != 0) {
        perror("fsync");
        close(fd);
        return -1;
    }

    if (close(fd) != 0) {
        perror("close");
        return -1;
    }

    return 0;
}
```

## 5.8 掉电一致性：双副本提交协议

对于关键配置，不建议直接覆盖原文件：

```
config.bin
```

更可靠的方式：

```
config_A
config_B
```

每份数据包含：

```
#include <stdint.h>

#define CONFIG_MAGIC 0x43464731u

struct config_record {
    uint32_t magic;
    uint32_t version;
    uint32_t payload_len;
    uint32_t crc32;
    uint8_t  payload[256];
} __attribute__((packed));
```

提交流程：

```
1. 读取 A/B
2. 校验 magic、长度、CRC
3. 选择 version 最大且有效的副本
4. 写入另一份副本
5. fsync
6. 更新版本号
7. 再次校验
```

关键点：

- 不能依赖 `write()` 返回成功就认为数据安全；
- 不能只保存一个副本；
- 不能使用未校验的版本号；
- 必须限制 `payload_len`；
- 必须处理两个副本都损坏的恢复路径。

## 5.9 RPMB

RPMB（Replay Protected Memory Block）具有：

- 认证写；
- 写计数器；
- HMAC 校验；
- 防重放；
- 专用密钥；
- 不能像普通 User Area 一样直接挂载文件系统。

典型用途：

- 安全启动状态；
- 固件回滚计数器；
- 设备激活状态；
- 许可证计数器；
- 密钥派生材料；
- 安全审计计数器。

关键限制：

1. RPMB 密钥通常只能编程一次；
2. 误烧录密钥可能导致整批设备不可用；
3. RPMB 不是通用高频日志区域；
4. 写计数器必须严格同步；
5. 密钥管理必须与制造流程绑定。

## 5.10 Boot 分区

eMMC 启动配置通常涉及：

```
BOOT_PARTITION_ENABLE
BOOT_PARTITION_ACCESS
PARTITION_CONFIG
```

典型启动结构：

```
ROM Boot
   |
   v
eMMC Boot0
   |
   v
SPL / FSBL
   |
   v
eMMC Boot1 或 User Area
   |
   v
U-Boot / TF-A
   |
   v
Linux Kernel
```

建议：

- Boot0 与 Boot1 写入相同或可回退的启动代码；
- Bootloader 需要版本、CRC、长度和回滚策略；
- 不要在现场随意修改 `PARTITION_CONFIG`；
- 量产工具必须验证启动分区写保护状态；
- Boot 分区内容应支持离线读取和审计。

---

## 6. 性能量化分析

以下数据为典型工程测试范围，不代表所有器件。测试平台示例：

- SoC：四核 ARM Cortex-A53，1.4 GHz；
- Linux：6.x；
- eMMC：工业级 64 GB，HS200/HS400；
- 文件系统：ext4；
- 测试工具：`fio`；
- 温度：25℃；
- 电源：1.8 V I/O、3.3 V NAND；
- 数据未启用硬件加密；
- 结果为多次测试区间，实际需以目标器件复测。

## 6.1 典型吞吐量

|测试项目|HS200|HS400|说明|
|---|---|---|---|
|顺序读，1 MiB|145~185 MB/s|220~330 MB/s|受 SoC 和设备内部 NAND 影响|
|顺序写，1 MiB|70~150 MB/s|100~220 MB/s|写入通常低于读取|
|随机读，4 KiB，QD1|3~12 MB/s|5~18 MB/s|约 750~4500 IOPS|
|随机写，4 KiB，QD1|0.5~8 MB/s|1~12 MB/s|受 FTL 和 GC 影响|
|随机写，4 KiB，QD32|5~35 MB/s|10~60 MB/s|设备内部并行度被利用|
|写入延迟 P99|2~50 ms|2~50 ms|GC 时可能超过 100 ms|
|写入延迟 P99.9|20~500 ms|20~500 ms|取决于容量占用和型号|

## 6.2 总线理论吞吐量

HS200：

```
200 MHz × 8 bit / 8 = 200 MB/s
```

HS400 DDR：

```
200 MHz × 8 bit × 2 / 8 = 400 MB/s
```

实际吞吐量：

```
T_real = T_bus × η_host × η_protocol × η_flash
```

例如：

```
T_real = 400 × 0.85 × 0.90 × 0.80
       ≈ 244.8 MB/s
```

其中：

- `η_host`：DMA、CPU、驱动效率；
- `η_protocol`：命令、响应、等待开销；
- `η_flash`：NAND 内部读写能力和 FTL 效率。

## 6.3 写放大与寿命估算

假设：

- 每天主机写入：10 GB；
- 设备使用年限：5 年；
- 写放大系数：3；
- NAND 额定等效擦写次数：3000 P/E；
- 用户可用容量：64 GB。

总物理写入量：

```
Physical Write
= 10 GB/day × 365 × 5 × 3
= 54,750 GB
```

平均物理擦写次数近似：

```
P/E ≈ 54,750 / 64
    ≈ 855 次
```

理论上低于 3000 次，但实际寿命还会受到：

- 温度；
- 数据保持时间；
- 读干扰；
- 坏块增长；
- 磨损均衡效率；
- 空间占用率；
- 突发写入；
- 不同 NAND 区域寿命差异。

## 6.4 小写入对寿命的影响

假设每次只更新 512 字节：

```
应用层写入：512 B
文件系统块：4 KiB
NAND 编程粒度：16 KiB
内部 GC 搬移：可能达到 64 KiB 或更大
```

理论写放大至少包含：

```
WAF ≥ 16 KiB / 512 B = 32
```

实际还可能更高。

优化方式：

1. 在应用层聚合小更新；
2. 使用 append-only 日志；
3. 减少高频 `fsync()`；
4. 将易变数据放到独立分区；
5. 避免分区长期接近 100%；
6. 选择支持高耐久度和增强区域的器件；
7. 让文件系统和 eMMC 的擦除组对齐；
8. 使用数据库 WAL，但控制 checkpoint 频率。

## 6.5 延迟尾部比平均值更重要

平均写延迟可能是：

```
平均值：2 ms
P99：20 ms
P99.9：300 ms
```

对于实时控制系统，平均值没有代表性。应关注：

- `P95`；
- `P99`；
- `P99.9`；
- 最大延迟；
- 连续写入 24 小时后的尾延迟；
- 温度变化下的尾延迟；
- 掉电恢复过程中的尾延迟。

典型瓶颈：

|瓶颈|表现|优化|
|---|---|---|
|FTL GC|写延迟周期性尖峰|增加空闲空间、后台维护|
|文件系统日志|高频同步|批量提交、合理 mount 参数|
|eMMC Cache|突然长时间 Busy|控制 flush 周期|
|CPU/DMA|顺序吞吐上不去|检查 DMA、cache、队列|
|高速信号|CRC、重试|降速、调 PHY、优化 PCB|
|温度|高温下写入下降|散热、降频、温度策略|

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否需要可插拔存储？
├── 是
│   ├── 工业级可靠性要求高？
│   │   ├── 是：工业级 SD / UFS 卡，并设计插拔和掉电保护
│   │   └── 否：普通 SD 卡
│
└── 否
    ├── 容量 < 256 MB，主要存放启动代码？
    │   ├── 是：SPI NOR
    │   └── 否
    │
    ├── 是否运行嵌入式 Linux？
    │   ├── 是
    │   │   ├── 需要极高随机 I/O 和高并发？
    │   │   │   ├── 是：UFS / SSD
    │   │   │   └── 否：eMMC
    │   │
    │   └── 否
    │       ├── 是否能接受自建 NAND FTL？
    │       │   ├── 是：裸 NAND / SPI-NAND
    │       │   └── 否：eMMC
    │
    ├── 是否有高频小块写入？
    │   ├── 是：优先工业高耐久 eMMC，配合日志聚合和分区隔离
    │   └── 否：普通工业 eMMC
    │
    ├── 是否需要防回滚和认证计数器？
    │   ├── 是：使用 RPMB
    │   └── 否：普通 User Area + 双副本
    │
    └── 是否要求掉电不丢关键事务？
        ├── 是：可靠写 + 文件系统日志 + A/B 或双副本 + 掉电测试
        └── 否：普通块写 + 合理 flush
```

## 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|工业网关 Linux RootFS|8~32 GB 工业 eMMC|成本、集成度、稳定性平衡|
|车载记录终端|高耐久 eMMC/UFS|高频写入、温度和振动要求|
|PLC 参数保存|NOR + eMMC|NOR 保存关键启动参数，eMMC 保存历史数据|
|OTA 设备|eMMC A/B 分区|镜像回退简单、可验证|
|安全计数器|RPMB|防重放、防篡改|
|高速视觉设备|UFS/SSD|随机吞吐和队列深度要求高|
|低成本消费终端|eMMC 或 SD|根据可维护性和成本选择|

---

## 8. 工程最佳实践

## 8.1 设计原则

1. **不要把 eMMC 当作无限寿命的 RAM 使用。**
2. **不要只验证顺序读写，要验证随机写和延迟尾部。**
3. **不要只测新盘，必须测试接近满盘和老化后的盘。**
4. **不要只验证正常上电，要验证任意时刻掉电。**
5. **不要依赖单一厂商型号，建立兼容性矩阵。**
6. **不要把 RPMB 当普通文件系统使用。**
7. **不要在量产阶段随意写入一次性配置字段。**
8. **高速模式必须进行电压、温度和批次覆盖测试。**

## 8.2 分区建议

一种典型 A/B 方案：

```
Boot0       4 MB       启动代码
Boot1       4 MB       启动代码备份
User:
  GPT       1 MB
  env       8 MB       Bootloader 环境，双副本
  boot_a    128 MB
  boot_b    128 MB
  rootfs_a  2 GB
  rootfs_b  2 GB
  data      剩余空间
  persist   64~256 MB 设备参数
  logs      独立日志区
RPMB        4~16 MB    安全计数器和密钥相关数据
```

实际分区需结合：

- 镜像大小增长；
- OTA 双镜像空间；
- 日志写入量；
- 文件系统；
- 工厂工具；
- 维修策略；
- 安全启动需求。

## 8.3 选型决策矩阵

|维度|权重|低要求|中要求|高要求|
|---|---|---|---|---|
|容量|15%|4~8 GB|16~64 GB|>128 GB|
|顺序性能|10%|50 MB/s|100 MB/s|>200 MB/s|
|随机写|20%|<1 MB/s|1~10 MB/s|>10 MB/s|
|写寿命|20%|消费级|工业级|高耐久/增强区域|
|掉电安全|15%|文件系统日志|reliable write|硬件 PLP/系统级事务|
|温度|10%|0~70℃|-25~85℃|-40~105℃|
|供应链|10%|单一来源|双来源|多批次长期供货|

## 8.4 编码规范

- 所有块设备操作必须检查短读、短写和 `errno`。
- 所有关键数据必须带魔数、版本、长度和 CRC。
- 不允许直接覆盖唯一配置副本。
- 对 eMMC 原始分区操作必须显式指定设备和分区。
- 禁止将 `/dev/mmcblk0` 与 `/dev/mmcblk0boot0` 混淆。
- 禁止在生产程序中无条件执行 `mmc hwreset enable`、分区重配置或 RPMB 密钥烧录。
- 关键写入必须具备超时、重试、回退和错误上报。
- 记录设备 CID、EXT_CSD 摘要、寿命字段和异常计数。

---

## 9. 常见错误与避坑指南

## 9.1 错误一：直接覆盖关键配置

### 错误代码

```
int save_config(const char *path, const void *buf, size_t len)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    write(fd, buf, len);
    close(fd);
    return 0;
}
```

### 根因

- 没有检查 `open()`；
- 没有处理短写；
- 没有 `fsync()`；
- 没有双副本；
- 掉电时文件可能被截断。

### 正确实现

采用：

```
临时文件写入
    |
    v
fsync(临时文件)
    |
    v
rename()
    |
    v
fsync(父目录)
```

并保留旧版本或 A/B 副本。

### 风险影响

- 设备配置丢失；
- 启动参数损坏；
- 设备进入恢复模式；
- 批量现场设备无法远程修复。

---

## 9.2 错误二：把 eMMC 当作低延迟实时存储

### 错误代码

```
void control_loop(void)
{
    while (1) {
        control_output();

        write(log_fd, sensor_data, 4096);
        fsync(log_fd);

        sleep_us(1000);
    }
}
```

### 根因

- 在实时线程中执行阻塞 I/O；
- `fsync()` 可能触发设备内部 flush；
- eMMC GC 可能产生数百毫秒尾延迟。

### 正确实现

```
实时线程
  |
  +-- 只写入无锁环形缓冲区
              |
              v
低优先级日志线程
  |
  +-- 批量写入
  +-- 定期 fsync
  +-- 空间回收
```

### 风险影响

- 控制周期抖动；
- 看门狗复位；
- 电机控制异常；
- 丢失实时性保证。

---

## 9.3 错误三：只用一个 eMMC 型号测试

### 错误方式

研发阶段使用某一型号 eMMC：

```
研发样机：Vendor A / 16 GB / HS200
量产替代：任意容量相同、接口兼容的 eMMC
```

或者在软件中只根据容量判断兼容性：

```
if (capacity_gb >= 16) {
    storage_is_supported = true;
}
```

### 根因分析

不同 eMMC 即使容量、封装和引脚完全兼容，内部行为也可能完全不同：

- NAND 类型不同：SLC、MLC、TLC 或厂商混合方案；
- FTL 映射粒度不同；
- Cache 大小不同；
- 垃圾回收策略不同；
- BKOPS 行为不同；
- 随机写性能差异明显；
- `EXT_CSD` 版本不同；
- HS200/HS400 支持能力不同；
- reliable write 语义和性能不同；
- 寿命估计字段实现不同；
- 高温下性能衰减程度不同；
- 掉电恢复策略不同。

例如：

|指标|型号 A|型号 B|
|---|---|---|
|顺序读|180 MB/s|135 MB/s|
|顺序写|120 MB/s|55 MB/s|
|4 KiB 随机写 QD1|5 MB/s|0.8 MB/s|
|正常 P99 写延迟|30 ms|180 ms|
|GC 时最大延迟|250 ms|1.2 s|
|HS400|支持|不支持|
|高温降速|轻微|明显|

### 正确实现

建立 eMMC 兼容性矩阵，并在软件启动阶段识别关键特征。

建议至少记录：

```
厂商 ID
产品名称
CID
CSD
EXT_CSD 版本
容量
CARD_TYPE
总线宽度
支持的高速模式
CACHE_SIZE
RPMB_SIZE_MULT
可靠写能力
BKOPS 能力
寿命估计
温度等级
```

Linux 端可获取基础信息：

```
cat /sys/block/mmcblk0/device/cid
cat /sys/block/mmcblk0/device/csd
cat /sys/block/mmcblk0/device/name
cat /sys/block/mmcblk0/device/oemid
cat /sys/block/mmcblk0/device/manfid

mmc extcsd read /dev/mmcblk0
```

生产软件应维护白名单或能力匹配策略：

```
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

struct emmc_identity {
    uint8_t  manfid;
    char     name[32];
    uint8_t  ext_csd_rev;
    uint32_t card_type;
    uint64_t capacity_bytes;
};

struct emmc_profile {
    uint8_t  manfid;
    const char *name;
    uint32_t required_card_type;
    uint64_t min_capacity;
    bool     allow_hs400;
};

static const struct emmc_profile g_profiles[] = {
    {
        .manfid = 0x13,
        .name = "industrial-emmc-a",
        .required_card_type = 0x30,
        .min_capacity = 16ULL * 1024 * 1024 * 1024,
        .allow_hs400 = true,
    },
    {
        .manfid = 0x45,
        .name = "industrial-emmc-b",
        .required_card_type = 0x20,
        .min_capacity = 16ULL * 1024 * 1024 * 1024,
        .allow_hs400 = false,
    },
};

static bool emmc_is_compatible(const struct emmc_identity *id)
{
    if (id == NULL) {
        return false;
    }

    for (size_t i = 0; i < sizeof(g_profiles) / sizeof(g_profiles[0]); ++i) {
        const struct emmc_profile *p = &g_profiles[i];

        if (id->manfid != p->manfid) {
            continue;
        }

        if (id->capacity_bytes < p->min_capacity) {
            continue;
        }

        if ((id->card_type & p->required_card_type) !=
            p->required_card_type) {
            continue;
        }

        return true;
    }

    return false;
}
```

需要注意：**白名单不能替代性能测试**。白名单只解决“是否允许启动”，不能证明替代料满足系统性能和可靠性要求。

### 测试矩阵

每个候选型号至少覆盖：

|测试维度|测试内容|
|---|---|
|初始化|上电、复位、Legacy、High-Speed、HS200、HS400|
|温度|低温、常温、高温|
|电压|额定电压上下限、动态压降|
|性能|顺序读写、随机读写、QD1、QD32|
|延迟|P50、P95、P99、P99.9、最大值|
|可靠性|连续写入、满盘、碎片化、GC|
|掉电|任意时刻掉电、写缓存开启/关闭|
|寿命|高写放大负载、长时间老化|
|软件|Kernel、U-Boot、文件系统、OTA|
|量产|烧录速度、校验、批量一致性|

### 风险影响

- 替代料无法进入 HS400；
- 初始化阶段偶发超时；
- 顺序写性能不足导致 OTA 超时；
- 后台 GC 引起业务线程阻塞；
- 高温环境下随机 I/O 延迟失控；
- 掉电后文件系统或启动分区损坏；
- 量产后才发现不同批次行为不一致。

---

## 9.4 错误四：把 `fsync()` 当成绝对掉电保护

### 错误代码

```
write(fd, data, len);
fsync(fd);
```

### 根因分析

`fsync()` 的语义是请求内核将文件数据和相关元数据提交到更稳定的存储层，但最终安全边界取决于整个链路：

```
应用
  |
  v
VFS
  |
  v
文件系统
  |
  v
块层
  |
  v
MMC 驱动
  |
  v
eMMC Cache
  |
  v
FTL
  |
  v
NAND
```

可能存在以下问题：

- 文件系统元数据已经提交，但数据尚未完成；
- eMMC 内部 Cache 尚未真正落盘；
- 电源在控制器内部映射更新过程中消失；
- 供电下降速度快于 eMMC 掉电处理时间；
- 主控复位而 eMMC 仍处于 Busy 状态；
- 文件系统本身没有采用事务或日志策略。

### 正确实现

关键数据应采用多层保护：

```
应用层事务
  |
  +-- 双副本 / A-B
  +-- 序列号
  +-- CRC
  +-- 完整性校验
  |
  v
文件写入
  |
  +-- fsync()
  +-- rename()
  +-- 父目录 fsync()
  |
  v
块设备 Flush / FUA
  |
  v
eMMC Reliable Write / Cache Flush
  |
  v
硬件掉电保持或受控关机
```

推荐的文件替换流程：

```
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static int write_all(int fd, const void *buf, size_t len)
{
    const unsigned char *p = buf;
    size_t off = 0;

    while (off < len) {
        ssize_t n = write(fd, p + off, len - off);

        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }

        if (n == 0) {
            errno = EIO;
            return -1;
        }

        off += (size_t)n;
    }

    return 0;
}

int atomic_replace_file(const char *tmp_path,
                        const char *final_path,
                        const void *data,
                        size_t len)
{
    int fd = open(tmp_path,
                  O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC,
                  0644);
    if (fd < 0) {
        return -1;
    }

    if (write_all(fd, data, len) != 0) {
        close(fd);
        unlink(tmp_path);
        return -1;
    }

    if (fsync(fd) != 0) {
        close(fd);
        unlink(tmp_path);
        return -1;
    }

    if (close(fd) != 0) {
        unlink(tmp_path);
        return -1;
    }

    if (rename(tmp_path, final_path) != 0) {
        unlink(tmp_path);
        return -1;
    }

    /*
     * 确保持久化 rename 对应的目录元数据。
     */
    int dirfd = open(".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dirfd < 0) {
        return -1;
    }

    int ret = fsync(dirfd);
    close(dirfd);

    return ret;
}
```

对于启动镜像、关键配置和 OTA 元数据，不应只依赖单文件替换，而应设计：

```
有效副本 A
有效副本 B
当前选择标志
镜像 CRC / SHA-256
版本号
回滚计数器
启动尝试次数
```

### 风险影响

- 用户以为数据已经安全，实际掉电后仍丢失；
- 文件存在但内容为空；
- 文件头和数据体不一致；
- OTA 标志更新成功但镜像未完整写入；
- 设备启动到错误或损坏分区。

---

## 9.5 错误五：在实时线程中直接写 eMMC

### 错误代码

```
void motor_control_task(void *arg)
{
    for (;;) {
        control_algorithm();

        /*
         * 错误：实时线程执行文件 I/O。
         */
        write(log_fd, &control_state, sizeof(control_state));
        fsync(log_fd);

        sleep_until_next_period();
    }
}
```

### 根因分析

eMMC 写入具有非确定性：

- 写命令可能等待设备内部 Busy；
- FTL 可能触发垃圾回收；
- Cache flush 可能产生长延迟；
- 文件系统可能更新多个元数据块；
- block layer 可能发生队列等待；
- 设备在高温或高占用率下可能主动降速。

即使平均写延迟只有 2 ms，P99.9 也可能达到数百毫秒。

### 正确实现

将实时采样与持久化分离：

```
实时控制线程
  |
  +-- 计算控制量
  +-- 写入无阻塞环形缓冲区
  |
  v
日志线程
  |
  +-- 批量读取
  +-- 顺序写入
  +-- 定期 flush
  +-- 空间管理
```

简化的单生产者环形缓冲区：

```
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define RING_CAPACITY 1024

struct sample {
    uint64_t timestamp;
    int32_t  value;
};

struct sample_ring {
    struct sample items[RING_CAPACITY];
    atomic_size_t write_pos;
    atomic_size_t read_pos;
};

bool sample_ring_push(struct sample_ring *r, const struct sample *s)
{
    size_t w = atomic_load_explicit(&r->write_pos,
                                    memory_order_relaxed);
    size_t rd = atomic_load_explicit(&r->read_pos,
                                     memory_order_acquire);

    if ((w - rd) >= RING_CAPACITY) {
        /*
         * 满时必须明确策略：丢最新、丢最旧或触发告警。
         */
        return false;
    }

    r->items[w % RING_CAPACITY] = *s;

    atomic_store_explicit(&r->write_pos,
                          w + 1,
                          memory_order_release);
    return true;
}

bool sample_ring_pop(struct sample_ring *r, struct sample *s)
{
    size_t rd = atomic_load_explicit(&r->read_pos,
                                     memory_order_relaxed);
    size_t w = atomic_load_explicit(&r->write_pos,
                                    memory_order_acquire);

    if (rd == w) {
        return false;
    }

    *s = r->items[rd % RING_CAPACITY];

    atomic_store_explicit(&r->read_pos,
                          rd + 1,
                          memory_order_release);
    return true;
}
```

日志线程应批量聚合，例如每次写入 64 KiB 或 256 KiB，而不是每条记录调用一次 `fsync()`。

### 风险影响

- 控制周期超时；
- 电机、电源或执行机构抖动；
- 看门狗复位；
- 实时线程优先级被 I/O 阻塞；
- 现场出现难以复现的偶发故障。

---

## 9.6 错误六：分区接近满载后仍继续高频写入

### 错误方式

```
/data 分区使用率达到 98%
仍持续写入日志和数据库
```

### 根因分析

eMMC 的 FTL 需要空闲块执行：

- 垃圾回收；
- 数据搬移；
- 磨损均衡；
- 坏块替换；
- 映射表更新。

当文件系统和设备内部可用空间都不足时，写放大和延迟会快速恶化。

### 正确实现

分层设置阈值：

```
< 70%：正常运行
70%~85%：降低日志级别
85%~92%：停止非关键日志
92%~95%：执行日志轮转和空间回收
> 95%：禁止普通写入，仅保留故障记录
```

示例：

```
enum storage_state {
    STORAGE_NORMAL,
    STORAGE_WARNING,
    STORAGE_CRITICAL,
    STORAGE_READ_ONLY,
};

static enum storage_state classify_usage(uint64_t used,
                                          uint64_t total)
{
    if (total == 0 || used > total) {
        return STORAGE_READ_ONLY;
    }

    uint64_t percent = used * 100 / total;

    if (percent >= 95) {
        return STORAGE_READ_ONLY;
    }

    if (percent >= 92) {
        return STORAGE_CRITICAL;
    }

    if (percent >= 85) {
        return STORAGE_WARNING;
    }

    return STORAGE_NORMAL;
}
```

### 风险影响

- 写延迟尖峰；
- 文件系统频繁触发空间整理；
- 日志写入失败；
- OTA 没有足够空间；
- 设备表现为“偶发卡死”。

---

## 10. 多机制组合使用方案

## 10.1 工业级存储协同架构

推荐架构：

```
+------------------------------------------------------+
|                  Application Layer                  |
|  配置管理 | 日志管理 | OTA管理 | 数据库 | 诊断系统 |
+--------------------------+---------------------------+
                           |
+------------------------------------------------------+
|              Storage Policy Layer                  |
|  关键数据策略 | 日志策略 | 空间策略 | 寿命策略      |
+--------------------------+---------------------------+
                           |
+------------------------------------------------------+
|              Storage Abstraction Layer              |
|  原子更新 | 双副本 | CRC | 版本管理 | 回滚 | 统计   |
+--------------------------+---------------------------+
                           |
+------------------------------------------------------+
|              Linux VFS / File System                |
|  ext4 / f2fs / UBIFS（视介质而定）                  |
+--------------------------+---------------------------+
                           |
+------------------------------------------------------+
|              MMC Block Layer                        |
|  Flush | FUA | Queue | Timeout | Retry              |
+--------------------------+---------------------------+
                           |
+------------------------------------------------------+
|              eMMC Hardware                         |
|  FTL | ECC | Wear Leveling | Cache | RPMB | BKOPS  |
+------------------------------------------------------+
```

## 10.2 数据分类策略

|数据类型|写入频率|一致性要求|推荐策略|
|---|---|---|---|
|启动代码|低|极高|Boot0/Boot1 双备份、CRC、回滚|
|OTA 镜像|低|极高|A/B 分区、SHA-256、版本校验|
|设备配置|中|高|双副本、版本号、CRC、原子提交|
|运行日志|高|中|环形文件、批量写、空间阈值|
|计量数据|中高|高|顺序追加、批量提交、断点恢复|
|安全计数器|低中|极高|RPMB、认证写、防重放|
|临时缓存|高|低|独立目录、可丢弃、禁止参与启动|

## 10.3 配置双副本代码框架

```
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define RECORD_MAGIC 0x52454331u
#define MAX_PAYLOAD  1024u

struct persistent_record {
    uint32_t magic;
    uint32_t generation;
    uint32_t payload_len;
    uint32_t crc32;
    uint8_t  payload[MAX_PAYLOAD];
};

static bool record_valid(const struct persistent_record *r)
{
    if (r == NULL) {
        return false;
    }

    if (r->magic != RECORD_MAGIC) {
        return false;
    }

    if (r->payload_len > MAX_PAYLOAD) {
        return false;
    }

    uint32_t crc = crc32_compute(r->payload, r->payload_len);

    return crc == r->crc32;
}

int persistent_record_load(struct persistent_record *out)
{
    struct persistent_record a;
    struct persistent_record b;

    bool valid_a = storage_read_copy("config.a", &a, sizeof(a)) == 0 &&
                   record_valid(&a);

    bool valid_b = storage_read_copy("config.b", &b, sizeof(b)) == 0 &&
                   record_valid(&b);

    if (!valid_a && !valid_b) {
        return -1;
    }

    if (valid_a && (!valid_b || a.generation >= b.generation)) {
        *out = a;
    } else {
        *out = b;
    }

    return 0;
}

int persistent_record_store(const void *payload, size_t len)
{
    if (payload == NULL || len == 0 || len > MAX_PAYLOAD) {
        return -1;
    }

    struct persistent_record old;
    struct persistent_record next = {0};

    uint32_t generation = 0;

    if (persistent_record_load(&old) == 0) {
        generation = old.generation + 1;
    }

    next.magic = RECORD_MAGIC;
    next.generation = generation;
    next.payload_len = (uint32_t)len;

    memcpy(next.payload, payload, len);
    next.crc32 = crc32_compute(next.payload, len);

    /*
     * 根据当前有效副本选择另一个副本写入，避免覆盖唯一有效数据。
     */
    const char *target = select_inactive_copy();
    return storage_atomic_update(target, &next, sizeof(next));
}
```

该框架还需要补充：

- 故障注入；
- 写入后重新读取校验；
- 两份副本都损坏时的默认配置；
- generation 溢出处理；
- 文件系统空间不足处理；
- 设备只读状态处理。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业网关 A/B OTA

### 需求

- 设备长期在线；
- OTA 过程中不能破坏当前系统；
- 升级失败后自动回滚；
- 支持断电恢复；
- 固件版本不能回退到存在漏洞的旧版本。

### 架构

```
Boot0/Boot1
    |
    v
Bootloader
    |
    +-- rootfs_a
    +-- rootfs_b
    +-- persistent
    +-- data
    +-- RPMB rollback counter
```

### OTA 流程

```
1. 下载镜像到 inactive 分区
2. 校验传输完整性
3. 校验 SHA-256
4. 校验签名
5. 读取 RPMB 版本计数器
6. 判断新版本是否允许安装
7. 设置 pending_upgrade
8. fsync / reliable write
9. 重启
10. Bootloader 启动 inactive 分区
11. Linux 完成自检
12. 写入 boot_success
13. 清除 pending_upgrade
```

### 设计要点

- `pending_upgrade` 与镜像状态必须原子更新；
- Bootloader 必须限制启动尝试次数；
- 新系统未完成健康检查前不能标记成功；
- RPMB 只存储安全计数器，不存储大镜像；
- OTA 镜像写入应采用大块顺序写；
- 升级前确认剩余空间和电源状态。

---

## 11.2 案例二：车载终端高频日志

### 需求

- 每秒写入数 MB 数据；
- 设备可能在车辆断电时突然失电；
- 工作温度：-40~85℃；
- 运行周期 5~10 年；
- 不能让日志写入影响实时通信任务。

### 架构

```
CAN / Ethernet 接收任务
          |
          v
内存环形队列
          |
          v
日志聚合任务
          |
          +-- 256 KiB 顺序写
          +-- 事件触发 fsync
          +-- 周期性 fsync
          +-- 文件轮转
          |
          v
独立 logs 分区
```

### 写入策略

- 正常数据：批量写，不逐条同步；
- 关键故障事件：立即写入独立事件记录；
- 电源预警：停止非关键日志，执行快速 flush；
- 日志文件：按大小轮转，避免单文件过大；
- 空间超过阈值：删除最旧普通日志；
- 关键故障日志：使用独立保留区。

### 设计要点

- 日志线程不能与控制线程共享阻塞锁；
- 使用单生产者/单消费者队列减少同步开销；
- 记录丢包计数和队列溢出次数；
- 对日志写入执行长期 WAF 和 P99.9 测试；
- 不能简单通过 `noatime` 等参数解决所有寿命问题。

---

## 11.3 案例三：安全启动和防回滚

### 需求

- 固件必须经过签名验证；
- 旧版本固件不可重新安装；
- 设备激活状态不可被普通用户篡改；
- 支持现场维修但不能暴露密钥。

### 架构

```
SoC ROM
  |
  v
签名验证 Bootloader
  |
  +-- 读取 RPMB 版本计数器
  +-- 验证镜像签名
  +-- 比较镜像版本
  |
  v
Linux
  |
  +-- 访问受控 RPMB 服务
  +-- 普通数据存于 User Area
```

### 设计要点

- RPMB key 只能在受控制造站写入；
- RPMB 写计数器必须防止回退和重放；
- 不允许 Linux 普通应用直接访问 RPMB 原始接口；
- 版本计数器更新时必须处理掉电；
- 维修工具不能通过刷写 User Area 清除安全状态；
- 设备唯一密钥不能硬编码在普通文件系统。

---

## 12. 高频问题深度答疑

### 问题一：eMMC 和 SD 卡本质上有什么区别？

二者协议族相近，都由控制器管理 NAND，但系统定位不同。

eMMC 是焊接在主板上的嵌入式器件，通常具有更好的：

- 供电设计；
- 机械可靠性；
- 工业温度选项；
- 批量一致性；
- 生命周期信息；
- 启动分区；
- RPMB；
- 可靠写能力。

SD 卡面向可插拔使用，产品差异大，不同卡的 FTL 和 NAND 质量可能差异明显。**工业固定式设备优先考虑 eMMC，而不是把普通 SD 卡当作 eMMC 替代品。**

### 问题二：为什么 eMMC 顺序写很快，随机写却很慢？

顺序写可以让 FTL：

- 连续分配物理页；
- 减少映射更新；
- 减少数据搬移；
- 更好利用 NAND 并行度；
- 降低垃圾回收频率。

随机写会导致：

```
小块覆盖写
    |
    v
有效页和无效页混杂
    |
    v
GC 搬移有效页
    |
    v
擦除旧块
    |
    v
再次编程新数据
```

因此应尽量将高频小写入转换成：

- 顺序日志；
- 批量写；
- WAL；
- 内存聚合后定期落盘。

### 问题三：HS400 一定比 HS200 好吗？

不一定。

HS400 的理论总线带宽是 HS200 的两倍，但实际收益取决于：

- eMMC NAND 内部速度；
- SoC 控制器；
- DMA；
- 文件系统；
- 访问模式；
- PCB 信号质量；
- PHY tuning；
- 温度和电源稳定性。

如果应用主要是 4 KiB 随机写，HS400 可能只带来有限收益，却增加调试复杂度。工业设备中应以实测的 P99/P99.9 延迟和稳定性决定是否使用 HS400，而不是只看理论带宽。

### 问题四：eMMC 的寿命字段能否精确预测寿命？

不能。

`DEVICE_LIFE_TIME_EST_TYP_A/B` 通常是离散分档估计，不是精确剩余百分比。它还不能完全反映：

- 当前写放大；
- 局部热点；
- 温度加速；
- 数据保持能力；
- 突发写入；
- 坏块增长；
- 未来业务变化。

工程上应结合：

```
EXT_CSD 寿命字段
+ 主机写入统计
+ 工作温度
+ WAF 测量
+ 长期老化测试
+ 故障率数据
```

### 问题五：为什么设备没有写满，仍然会出现严重写放大？

“文件系统未写满”不等于“FTL 有足够可用块”。

可能原因：

- eMMC 内部预留空间已被消耗；
- 文件系统频繁覆盖写；
- 数据分布形成局部热点；
- 大量小文件元数据更新；
- 长时间未执行后台维护；
- 分区布局导致有效块无法高效回收；
- 设备启用了较大的安全或增强区域。

### 问题六：是否应该关闭 eMMC Cache？

不能简单回答“开启”或“关闭”。

开启 Cache：

- 顺序写性能通常更好；
- 突发写延迟可能更低；
- 掉电风险依赖 flush/reliable write 是否正确执行。

关闭 Cache：

- 行为更容易理解；
- 写性能可能下降；
- 不能消除 FTL、GC 和 NAND 编程延迟。

推荐策略：

- 普通日志：开启 Cache，批量写入；
- 关键事务：使用正确的 flush、fsync、可靠写或双副本；
- 对关键数据进行实际掉电测试；
- 不要以“关闭 Cache”代替完整的一致性设计。

---

## 13. 课程核心总结

## 13.1 核心要点

1. **eMMC 是带控制器的 NAND 存储系统，而不是简单的 Flash 芯片。**
2. 主机看到的是 LBA，真正的物理映射、ECC、磨损均衡和 GC 由 FTL 完成。
3. **随机小写入是性能和寿命的主要风险来源。**
4. eMMC 的性能必须关注 **P99/P99.9 延迟**，而不仅是平均吞吐量。
5. HS400 理论性能高，但对 PCB、PHY、tuning、电源和温度更敏感。
6. `fsync()` 不是完整的掉电保护方案，关键数据必须使用事务、双副本或 A/B。
7. Boot0/Boot1、User Area、RPMB 的用途和访问语义不同，不能混用。
8. **不能只用一个 eMMC 型号测试，也不能只依据容量判断兼容性。**
9. eMMC 选型必须覆盖容量、性能、寿命、温度、掉电、供应链和批次一致性。
10. 工业级存储系统应由应用层策略、文件系统、块层和硬件能力共同保证。

## 13.2 性能排序

典型情况下：

```
顺序读 > 顺序写 > 随机读 > 随机写
```

典型延迟稳定性：

```
SPI NOR > 工业 eMMC 顺序写 > 工业 eMMC 随机写 > 普通 SD 卡随机写
```

高速模式理论带宽：

```
HS400 > HS200 > High-Speed > Legacy
```

但工程最终排序必须以目标平台实测为准。

## 13.3 通用选型结论

- 固定式工业 Linux 设备：优先工业级 eMMC；
- 高并发随机 I/O：考虑 UFS 或 SSD；
- 小容量启动存储：SPI NOR；
- 安全计数器和防回滚：RPMB；
- 高写入量：高耐久 eMMC + 日志聚合 + 分区隔离；
- 需要可靠 OTA：A/B 分区 + 签名验证 + 回滚计数器；
- 对供应链敏感：建立多型号兼容矩阵并执行替代料验证。

---

## 14. 快速参考速查表

## 14.1 场景选型表

|需求|推荐方案|
|---|---|
|启动代码、小容量参数|SPI NOR|
|嵌入式 Linux RootFS|工业级 eMMC|
|高并发随机访问|UFS / SSD|
|可插拔数据介质|工业级 SD|
|防回滚计数器|RPMB|
|关键配置|双副本 + CRC + fsync|
|OTA|A/B 分区 + 签名 + 版本计数器|
|高频日志|顺序追加 + 批量写 + 独立日志分区|
|实时控制|内存缓冲，禁止实时线程直接写 eMMC|

## 14.2 关键命令

```
# 查看块设备
lsblk

# 查看 eMMC 基本信息
cat /sys/block/mmcblk0/device/cid
cat /sys/block/mmcblk0/device/csd
cat /sys/block/mmcblk0/device/name
cat /sys/block/mmcblk0/device/manfid

# 读取 EXT_CSD
mmc extcsd read /dev/mmcblk0

# 查看分区
cat /proc/partitions
ls -l /dev/mmcblk0*

# 顺序性能测试
fio --name=seq-read \
    --filename=/dev/mmcblk0 \
    --rw=read \
    --bs=1M \
    --iodepth=8 \
    --direct=1 \
    --runtime=60 \
    --time_based

# 随机写测试，注意不要直接在生产数据盘运行
fio --name=rand-write \
    --filename=/path/testfile \
    --rw=randwrite \
    --bs=4k \
    --iodepth=1 \
    --direct=1 \
    --size=1G \
    --runtime=60 \
    --time_based
```

## 14.3 特性对比表

|特性|普通写|Reliable Write|双副本|A/B 分区|RPMB|
|---|---|---|---|---|---|
|防单次掉电损坏|低|中高|高|高|高|
|防重放|否|否|否|否|是|
|适合大数据|是|一般|一般|是|否|
|实现复杂度|低|中|中|高|高|
|适合关键配置|否|是|是|视情况|视情况|
|适合 OTA|否|辅助|辅助|是|存版本计数器|

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  eMMC 控制器为什么能隐藏 NAND 的坏块和 ECC 复杂性？
- [ ]  FTL 为什么会导致写放大？
- [ ]  为什么 4 KiB 随机写可能产生几十 KiB 甚至更大的物理写入？
- [ ]  HS200 和 HS400 的理论吞吐量如何计算？
- [ ]  为什么 HS400 可能比 HS200 更难稳定？
- [ ]  `EXT_CSD` 中哪些字段用于寿命、能力和分区判断？
- [ ]  Boot0、Boot1、User Area 和 RPMB 的用途分别是什么？
- [ ]  为什么 `fsync()` 不能单独保证关键数据不丢？
- [ ]  如何设计一个掉电安全的双副本配置系统？
- [ ]  为什么实时线程不能直接调用 `write()` 和 `fsync()`？
- [ ]  如何设计多 eMMC 型号兼容性矩阵？
- [ ]  如何评估 eMMC 的 P99.9 写延迟？
- [ ]  如何计算主机写入量、WAF 和理论磨损次数？
- [ ]  何时应该选择 eMMC，何时应该选择 UFS 或 SSD？
- [ ]  RPMB 为什么不能当作普通文件系统使用？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：eMMC 信息采集工具

实现一个工具，输出：

```
CID
CSD
EXT_CSD revision
容量
卡类型
启动分区大小
RPMB 容量
Cache 大小
寿命估计
预 EOL 状态
```

要求：

- 检查设备路径；
- 区分读取失败和字段不存在；
- 输出原始值和解释值；
- 保存设备唯一身份摘要；
- 支持批量设备采集。

### 任务二：性能基线测试

对同一型号 eMMC 完成：

```
顺序读：128 KiB、1 MiB
顺序写：128 KiB、1 MiB
随机读：4 KiB、QD1/QD32
随机写：4 KiB、QD1/QD32
```

记录：

```
平均带宽
IOPS
P50
P95
P99
P99.9
最大延迟
CPU 占用
温度
```

分别测试：

- 空盘；
- 50% 使用率；
- 80% 使用率；
- 95% 使用率；
- 连续运行 24 小时后。

### 任务三：掉电一致性实验

测试对象：

- 单文件覆盖写；
- 临时文件 + rename；
- 双副本配置；
- A/B 元数据；
- `fsync()` 前掉电；
- `fsync()` 后掉电；
- 文件系统 mount 后掉电。

每次记录：

```
掉电时间点
最后一次成功提交版本
启动结果
文件完整性
CRC
文件系统修复时间
是否发生只读挂载
```

### 任务四：多型号兼容性测试

至少准备 3 个型号：

```
型号 A：HS400
型号 B：HS200
型号 C：仅 High-Speed
```

验证：

- 启动；
- 读写；
- OTA；
- 高温；
- 低压；
- 满盘；
- 长时间随机写；
- 突发掉电；
- 批量烧录。

最终形成：

```
支持型号
限制型号
禁止型号
对应降级策略
```

### 任务五：实时性隔离测试

创建两个线程：

```
实时线程：1 ms 周期
日志线程：持续写入 eMMC
```

对比：

1. 实时线程直接写 eMMC；
2. 实时线程写内存环；
3. 日志线程批量顺序写；
4. 日志线程每次 `fsync()`；
5. 日志线程每 1 秒 `fsync()`。

测量：

```
周期抖动
最大阻塞时间
丢样本数量
eMMC 写延迟
CPU 占用
```

## 16.2 性能测试方法

测试过程中应避免以下误区：

- 只测一次；
- 只测空盘；
- 只测顺序读；
- 使用 page cache 结果代替真实存储性能；
- 把文件系统性能误认为 eMMC 原始性能；
- 忽略温度和电源；
- 忽略预热阶段；
- 只看平均值；
- 测试过程中未记录设备内部状态。

推荐测试流程：

```
设备识别
  |
  v
记录 CID / EXT_CSD
  |
  v
清理测试环境
  |
  v
预热
  |
  v
顺序 I/O 基线
  |
  v
随机 I/O 基线
  |
  v
填充到不同容量占用率
  |
  v
长时间老化
  |
  v
重复性能测试
  |
  v
温度/电压扫描
  |
  v
掉电注入
  |
  v
结果归档和型号评级
```

## 16.3 进阶学习方向

### 方向一：Linux MMC 子系统

深入学习：

- `drivers/mmc/core/`
- `drivers/mmc/host/`
- SDHCI；
- DesignWare MMC；
- MMC request；
- DMA descriptor；
- tuning；
- CQE；
- BKOPS；
- cache flush；
- reliable write；
- block queue。

### 方向二：文件系统与闪存协同

重点方向：

- ext4 journal；
- f2fs checkpoint；
- writeback；
- `fsync()`；
- discard；
- FITRIM；
- I/O scheduler；
- 日志结构化写入；
- 数据库 WAL；
- 文件系统掉电恢复。

### 方向三：存储可靠性工程

学习：

- WAF 测量；
- P/E 周期；
- retention；
- read disturb；
- 高温加速模型；
- 预 EOL；
- SMART 类监控；
- 现场寿命统计；
- 故障树分析；
- HALT/HASS 测试。

### 方向四：安全存储

学习：

- RPMB 协议；
- HMAC-SHA256；
- 写计数器；
- TEE；
- OP-TEE RPMB；
- 安全启动；
- 防回滚；
- 密钥生命周期；
- 工厂密钥烧录；
- 设备身份绑定。

### 方向五：高可靠启动与 OTA

学习：

- U-Boot A/B；
- TF-A；
- AVB；
- FIT Image；
- dm-verity；
- RAUC；
- SWUpdate；
- Mender；
- 断电恢复状态机；
- 安全回滚策略；
- 镜像可验证启动链。

**最终能力目标：不是会读写 eMMC，而是能够设计一套在高温、掉电、老化、替代料和长期运行条件下仍然可诊断、可恢复、可量产的嵌入式存储系统。**