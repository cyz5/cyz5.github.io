
## 1. 学习目标

### 理解

- 理解 NOR Flash、NAND Flash、SPI-NOR、Raw NAND、eMMC/UFS 在可靠性、擦写粒度和地址映射上的差异。
- 理解 Flash 文件系统与块设备文件系统的本质区别。
- 理解擦除前写入限制、有限擦写寿命、掉电一致性、坏块管理和磨损均衡的底层约束。
- 理解 LittleFS、JFFS2、YAFFS2、UBIFS、SPIFFS 等主流方案的设计边界。

### 掌握

- 掌握 Flash 文件系统的分层架构、挂载流程和块分配机制。
- 掌握 LittleFS 的 copy-on-write、元数据 pair、CTZ skip-list 和动态磨损均衡机制。
- 掌握分区布局、擦写参数配置、缓存配置和一致性测试方法。
- 掌握文件系统适配层的读、写、擦除、同步和错误处理接口。

### 精通

- 能够定位掉电、缓存、并发、坏块和寿命耗尽导致的文件系统故障。
- 能够根据容量、写入频率、实时性、掉电风险和 RAM 约束选择文件系统。
- 能够设计日志型、参数型、升级型和配置型数据存储方案。
- 能够量化写放大、寿命、挂载时间、RAM 消耗和最坏情况延迟。

### 能够设计

- 能够设计一套具备掉电恢复、版本回滚、磨损均衡和故障诊断能力的工业级 Flash 存储架构。
- 能够建立文件系统可靠性测试、寿命测试和异常注入测试体系。
- 能够将 Flash 文件系统与 Bootloader、OTA、诊断日志、参数管理和安全启动协同设计。

---

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、函数指针、位操作和内存模型。
- MCU 启动流程、链接脚本、Flash 地址映射和中断机制。
- SPI、QSPI、OSPI、并行 NAND 等 Flash 控制器基础。
- RTOS 任务、互斥锁、临界区和优先级反转。
- CRC、哈希、事务一致性和基本故障模型。
- 了解文件、目录、块设备和 VFS 的基本概念。

### 技能要求

- 能够读取 Flash 数据手册并提取以下参数：
    - Page Program Size
    - Sector/Block Erase Size
    - Program Time
    - Erase Time
    - Endurance
    - Data Retention
    - ECC 要求
- 能够编写可靠的 Flash 驱动和硬件抽象层。
- 能够使用逻辑分析仪、示波器和故障注入工具分析 Flash 总线行为。
- 能够进行断电测试、长时间循环写入和文件系统一致性检查。

---

## 3. 技术概述

### 3.1 Flash 的本质限制

典型 SPI-NOR Flash 具有以下约束：

1. 写入只能将 bit 从 `1` 改为 `0`。
2. 从 `0` 恢复为 `1` 必须执行擦除。
3. 写入粒度通常为 Page，例如 256 B。
4. 擦除粒度通常为 Sector，例如 4 KiB。
5. 擦除次数存在上限，例如 `10^4`、`10^5` 次。
6. 写入和擦除可能耗时数百微秒到数秒。
7. 掉电可能发生在任意 bit、page 或 sector 操作中。

因此，普通 RAM 风格的随机覆盖写不适合直接映射到 Flash。

### 3.2 Flash 文件系统的职责

Flash 专用文件系统通常负责：

- 逻辑地址到物理地址映射。
- 擦除前的空间回收。
- 写放大控制。
- 动态或静态磨损均衡。
- 元数据一致性。
- 掉电恢复。
- 坏块管理。
- 文件和目录抽象。
- 崩溃恢复和垃圾回收。

### 3.3 主流技术分支

|文件系统|典型介质|核心机制|适用场景|
|---|---|---|---|
|LittleFS|SPI-NOR、内部 Flash|Copy-on-write、metadata pair、CTZ|MCU、配置、日志、小型文件|
|SPIFFS|SPI-NOR|日志结构、静态磨损均衡|ESP 类设备、小容量文件|
|JFFS2|Raw NOR、Raw NAND|日志结构、全扫描挂载|Linux、小中型 Flash|
|YAFFS2|Raw NAND|NAND 专用日志结构|原始 NAND|
|UBIFS|Raw NAND + UBI|UBI 磨损均衡、树结构索引|大容量 NAND|
|F2FS|eMMC、UFS、SSD|Flash-friendly block FS|有 FTL 的块设备|
|FATFS|SD、eMMC、USB MSC|块设备文件系统|交换介质、PC 兼容|
|NVS/KV|NOR、内部 Flash|键值存储、日志追加|参数和校准值|

关键结论：

> **LittleFS 适合 MCU 直接管理的 SPI-NOR；UBIFS 适合 Linux Raw NAND；FATFS 适合已经提供块映射和坏块管理的设备。**

---

## 4. 核心特性横向对比

|维度|LittleFS|SPIFFS|JFFS2|UBIFS|FATFS|
|---|---|---|---|---|---|
|主要介质|NOR|NOR|NOR/NAND|Raw NAND|SD/eMMC/USB|
|掉电一致性|强|较强|强|强|依赖实现|
|动态磨损均衡|有|有限|有|强，由 UBI 提供|通常由设备提供|
|静态磨损均衡|有限|有限|较好|较好|取决于 FTL|
|RAM 消耗|低|低|较高|较高|中|
|挂载时间|快|中|可能较慢|较快|快|
|目录支持|支持|有限制|支持|支持|完整|
|大文件性能|中|较差|中|好|好|
|断电恢复|设计内建|支持|支持|支持|依赖日志/缓存|
|典型容量|KB 至数十 MB|KB 至数十 MB|MB 级以上|数十 MB 至 GB|GB 级|
|代码复杂度|中|中|高|高|中|
|MCU 适配难度|低|中|高|不适用|中|

### 4.1 选择结论

- 内部 Flash、外部 SPI-NOR、RAM 较小：优先 LittleFS。
- ESP-IDF 既有 SPIFFS 生态，且需求简单：可使用 SPIFFS，但需评估长期维护。
- Linux 直接使用 Raw NAND：使用 UBI + UBIFS。
- SD/eMMC/UFS：使用 FATFS、ext4 或 F2FS，不要把 LittleFS 当作块设备文件系统替代品。
- 仅存储固定配置参数：KV/NVS 通常比完整文件系统更简单、可控。

---

## 5. 底层原理与功能特性深度解析

## 5.1 Flash 写入与擦除模型

典型 NOR Flash 的写操作可以抽象为：

```
old_data & new_data == new_data
```

因为只能执行 `1 -> 0`。例如：

```
old = 1111_0000
new = 1100_0000
old & new = 1100_0000
```

合法。

但：

```
old = 1100_0000
new = 1111_0000
old & new = 1100_0000 != new
```

不合法，必须先擦除。

### 生产级 Flash 适配层

```
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef enum {
    FLASH_OK = 0,
    FLASH_EINVAL = -1,
    FLASH_EIO = -2,
    FLASH_ETIMEOUT = -3,
    FLASH_EBUSY = -4,
} flash_status_t;

typedef struct {
    int (*read)(uint32_t addr, void *buf, size_t len);
    int (*program)(uint32_t addr, const void *buf, size_t len);
    int (*erase)(uint32_t addr, size_t len);
    int (*sync)(void);
    size_t page_size;
    size_t erase_size;
    size_t total_size;
} flash_device_t;

static bool range_valid(const flash_device_t *dev,
                        uint32_t addr,
                        size_t len)
{
    if (dev == NULL || len > dev->total_size) {
        return false;
    }

    return addr <= dev->total_size - len;
}

int flash_program_checked(flash_device_t *dev,
                          uint32_t addr,
                          const void *data,
                          size_t len)
{
    if (dev == NULL || data == NULL || len == 0 ||
        !range_valid(dev, addr, len)) {
        return FLASH_EINVAL;
    }

    /*
     * Page Program 不能跨页。
     * 适配层必须拆分跨页写入，避免不同芯片产生回卷或截断。
     */
    while (len > 0) {
        size_t page_off = addr % dev->page_size;
        size_t chunk = dev->page_size - page_off;

        if (chunk > len) {
            chunk = len;
        }

        int rc = dev->program(addr, data, chunk);
        if (rc != FLASH_OK) {
            return rc;
        }

        addr += chunk;
        data = (const uint8_t *)data + chunk;
        len -= chunk;
    }

    return dev->sync();
}
```

## 5.2 LittleFS 的 metadata pair

LittleFS 不直接覆盖原有元数据，而是维护两个元数据块：

```
metadata pair:
    block A: 有效版本
    block B: 上一次或下一次版本
```

更新过程通常为：

1. 读取当前有效 metadata。
2. 在另一个块构造新版本。
3. 写入新内容。
4. 写入提交标记或 CRC。
5. 新版本校验通过后，旧版本自然失效。
6. 断电后选择有效版本。

这种设计本质上是小型 copy-on-write 事务。

### 简化版元数据提交模型

```
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t payload_len;
    uint32_t crc;
} metadata_header_t;

static uint32_t crc32(const void *data, size_t len);

int metadata_commit(flash_device_t *flash,
                    uint32_t target,
                    const void *payload,
                    size_t payload_len,
                    uint32_t version)
{
    if (flash == NULL || payload == NULL ||
        payload_len > flash->erase_size - sizeof(metadata_header_t)) {
        return FLASH_EINVAL;
    }

    metadata_header_t hdr = {
        .magic = 0x4D455441U,
        .version = version,
        .payload_len = payload_len,
        .crc = crc32(payload, payload_len),
    };

    int rc = flash->erase(target, flash->erase_size);
    if (rc != FLASH_OK) {
        return rc;
    }

    rc = flash_program_checked(flash, target, &hdr, sizeof(hdr));
    if (rc != FLASH_OK) {
        return rc;
    }

    rc = flash_program_checked(flash,
                               target + sizeof(hdr),
                               payload,
                               payload_len);
    if (rc != FLASH_OK) {
        return rc;
    }

    /*
     * 实际实现还应回读验证：
     * 1. magic
     * 2. version
     * 3. payload_len
     * 4. CRC
     */
    return flash->sync();
}
```

注意：示例展示的是事务思路，不是完整替代 LittleFS。生产代码应使用成熟文件系统，避免重复实现复杂的恢复逻辑。

## 5.3 CTZ 文件数据结构

LittleFS 对大文件使用 CTZ skip-list：

```
file block 0 -> block 1 -> block 2 -> block 4 -> block 8 ...
```

它具有以下特性：

- 文件内容按数据块追加。
- 通过跳跃指针减少从文件头遍历到末尾的成本。
- 文件扩展不要求移动整个文件。
- 文件截断和追加可以保持较低的元数据更新成本。

但其代价是：

- 文件更新通常产生新物理块。
- 频繁覆盖小文件会产生写放大。
- 垃圾回收需要搬移仍然有效的数据。

## 5.4 掉电恢复

掉电点可发生在：

|阶段|可能结果|
|---|---|
|擦除中|目标块部分失效|
|Page Program 中|数据不完整|
|元数据写入中|新旧版本同时存在|
|文件同步前|用户态缓存未落盘|
|控制器 DMA 中|总线事务未完成|

文件系统必须满足：

```
恢复后：
- 要么看到旧版本
- 要么看到新版本
- 不能看到结构损坏的中间版本
```

应用层仍然需要执行：

```
fflush();
fsync();       /* 或 LittleFS 的文件关闭/同步语义 */
```

不要把 `write()` 成功等同于数据已经进入 Flash。

---

## 6. 性能量化分析

以下数据为典型工程测量范围，平台假设：

- MCU：Cortex-M4，120 MHz
- Flash：Winbond W25Q64，SPI 80 MHz
- Page：256 B
- Sector：4 KiB
- 文件系统：LittleFS
- 编译器：GCC `-O2`
- 无 DMA，单线程访问

### 6.1 线性读性能

SPI 物理吞吐上限：

```
80 MHz / 8 = 10 MB/s
```

考虑命令、地址、dummy cycle 和协议损耗，实际连续读取通常为：

```
7.5 MB/s ~ 9.2 MB/s
```

单字节随机读的协议开销显著：

```
命令 1 B + 地址 3 B + dummy + 数据 1 B
```

因此小块随机读取的有效吞吐可能低于：

```
0.5 MB/s
```

### 6.2 擦除和写入延迟

典型实测范围：

|操作|典型时间|最坏时间|
|---|---|---|
|Page Program 256 B|0.6 ms|3 ms|
|Sector Erase 4 KiB|35 ms|400 ms|
|Block Erase 64 KiB|150 ms|2 s|
|读取 4 KiB|0.5~1 ms|2 ms|

若实时任务直接执行 Sector Erase，可能产生数十到数百毫秒的不可接受阻塞。

### 6.3 寿命估算

假设：

- 单个 4 KiB sector 擦写寿命：`100,000` 次。
- 每次业务更新逻辑数据：`512 B`。
- 使用追加日志，每 4 KiB 产生一次擦除。
- 每小时更新一次。

理想情况下：

```
寿命 = 100,000 小时
     = 11.4 年
```

但如果所有更新集中在一个物理 sector，且存在 2 倍写放大：

```
寿命 = 100,000 / 2 小时
     = 50,000 小时
     = 5.7 年
```

如果没有磨损均衡，最热块会先失效，整体容量并不能等价为整体寿命。

### 6.4 写放大

定义：

```
WA = Flash 实际写入量 / 用户逻辑写入量
```

例如用户修改 100 B 参数，文件系统因为元数据和块回收实际写入 1 KiB：

```
WA = 1024 / 100 = 10.24
```

降低写放大的方法：

- 将多个参数批量提交。
- 使用追加日志代替随机覆盖。
- 增大缓存，减少元数据提交次数。
- 避免高频更新文件时间戳。
- 将易变数据与静态数据分区。
- 设置合理的垃圾回收阈值。
- 对计数器使用专用日志或单调编码。

### 6.5 RAM 估算

LittleFS RAM 通常近似为：

```
RAM ≈ 2 × cache_size × cache_count + file_handle + metadata buffers
```

例如：

```
cache_size = 256 B
cache_count = 2
file handle = 100 B
metadata buffers ≈ 500 B

RAM ≈ 2 × 256 × 2 + 100 + 500
    ≈ 1.6 KiB
```

实际值依版本、编译选项和文件句柄数量变化，必须以 map 文件和运行时测量为准。

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否直接管理 Raw Flash？
├─ 否
│  ├─ 设备是 SD/eMMC/UFS/USB？
│  │  └─ 使用 FATFS、ext4 或 F2FS
│  └─ 设备是已有 FTL 的 NOR/NAND？
│     └─ 按块设备文件系统设计
└─ 是
   ├─ 是否为 Raw NAND？
   │  ├─ 是
   │  │  └─ Linux：UBI + UBIFS；嵌入式 NAND：YAFFS2 等
   │  └─ 否，通常为 NOR
   │     ├─ 仅固定参数、少量配置？
   │     │  └─ NVS/KV/双备份参数区
   │     ├─ 需要目录、文件、掉电恢复？
   │     │  └─ LittleFS
   │     └─ 已有成熟 SPIFFS 生态？
   │        └─ SPIFFS，但评估容量和维护风险
```

### 7.2 典型场景

|场景|需求|方案|理由|
|---|---|---|---|
|电机控制器参数|几十个参数，更新低频|双备份参数区/NVS|简单、可验证、启动快|
|传感器数据日志|持续追加、断电不能丢全部数据|LittleFS + 环形日志|支持追加和恢复|
|OTA 固件|大文件、分区切换、回滚|原始分区 + Bootloader 元数据|不建议依赖普通文件名切换|
|Linux NAND|大容量、坏块、掉电恢复|UBI + UBIFS|NAND 坏块和磨损均衡完整|
|用户导出文件|需要 PC 读取|FATFS + SD/eMMC|兼容性优先|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **文件系统和原始 Flash 分区隔离。**
2. **禁止多个模块直接访问同一 Flash 区域。**
3. **Flash 驱动层统一处理跨页写、对齐、超时和忙状态。**
4. **文件系统 API 访问必须具备并发保护。**
5. **高频数据与低频配置分离。**
6. **所有关键配置具备版本号、长度和 CRC。**
7. **设计恢复路径，而不仅是正常路径。**
8. **对擦除操作设置独立任务，避免阻塞实时控制链路。**
9. **对文件系统空间设置水位线，禁止写满后才处理。**
10. **量产前执行掉电、寿命、异常复位和总线错误测试。**

### 8.2 选型决策矩阵

|指标|权重|LittleFS|NVS/KV|UBIFS|FATFS|
|---|---|---|---|---|---|
|MCU 适配|5|5|5|1|4|
|掉电可靠性|5|5|5|5|3|
|大容量性能|4|3|1|5|5|
|目录文件能力|3|4|1|5|5|
|RAM 约束适应性|4|4|5|2|3|
|PC 兼容性|2|1|1|1|5|

### 8.3 工业级编码规范

- 不使用无边界 `sprintf`、`strcpy`。
- 所有文件路径长度显式检查。
- 所有 Flash 地址执行溢出检查。
- 所有底层超时使用单调时钟，不使用可回拨的 RTC。
- 错误码分层定义，禁止丢失底层错误原因。
- 文件句柄必须成对打开和关闭。
- 对只读分区设置硬件或软件写保护。
- 对关键文件执行 CRC、版本和长度检查。
- 记录擦除计数和挂载恢复次数。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：直接覆盖 Flash 数据

错误代码：

```
flash_program(addr, &new_value, sizeof(new_value));
```

根因：

- 新数据可能要求 `0 -> 1`。
- 没有先擦除 sector。
- 可能破坏同一 sector 中其他数据。

正确实现：

```
read_sector(sector_addr, sector_buf, SECTOR_SIZE);

memcpy(sector_buf + offset, &new_value, sizeof(new_value));

erase_sector(sector_addr);
program_pages(sector_addr, sector_buf, SECTOR_SIZE);
```

更好的实现是使用 LittleFS 或专用参数日志。

风险：

- 参数随机损坏。
- 配置校验失败。
- 长期运行后出现不可复现故障。

### 9.2 错误二：假设 `write()` 已经落盘

错误代码：

```
write(fd, data, len);
system_reset();
```

根因：

- 数据可能仍在文件系统缓存。
- 元数据提交可能尚未完成。
- 控制器可能仍处于忙状态。

正确实现：

```
ssize_t written = write(fd, data, len);
if (written != (ssize_t)len) {
    handle_storage_error();
}

if (fsync(fd) != 0) {
    handle_storage_error();
}
```

对于 LittleFS，应确保文件关闭或显式同步完成。

风险：

- 复位后文件长度错误。
- 目录项存在但数据块缺失。
- 日志尾部损坏。

### 9.3 错误三：多个任务并发访问文件系统

错误代码：

```
/* Task A */
lfs_file_open(&file_a, "config", LFS_O_RDONLY);

/* Task B */
lfs_file_open(&file_b, "config", LFS_O_WRONLY);
```

根因：

- 文件系统内部状态不是天然线程安全。
- 两个任务可能同时修改 allocator、cache 或 metadata。
- 中断上下文调用文件系统会导致不可预测行为。

正确实现：

```
mutex_lock(&fs_mutex);

int rc = lfs_file_open(&lfs, &file, "config", LFS_O_RDONLY);

mutex_unlock(&fs_mutex);
return rc;
```

生产实现通常使用存储服务任务，将所有文件系统操作串行化。

风险：

- 元数据损坏。
- 死锁。
- 随机返回 `CORRUPT`、`IO_ERROR`。

### 9.4 错误四：高频更新单个文件导致早期磨损

错误代码：

```
for (;;) {
    counter++;
    write_counter_to_file(counter);
    sleep_ms(100);
}
```

根因：

- 每次更新都可能触发元数据和数据块写入。
- 写放大远大于逻辑数据量。
- 物理热块集中磨损。

正确实现：

```
/*
 * 仅在累计变化达到阈值或定时周期到达时提交。
 * 关键业务数据应使用追加日志和批量提交。
 */
if (counter - persisted_counter >= 100 ||
    elapsed_ms(last_commit) >= 60000) {
    persist_counter(counter);
    persisted_counter = counter;
    last_commit = now_ms();
}
```

风险：

- Flash 寿命从数年缩短到数月。
- 垃圾回收频繁触发。
- 写延迟抖动增大。

### 9.5 错误五：擦除操作运行在实时控制任务

错误代码：

```
void control_task(void)
{
    if (need_save) {
        lfs_file_write(...);  /* 可能隐式触发 erase */
    }

    control_loop();
}
```

根因：

- Sector Erase 可能阻塞几十到几百毫秒。
- 控制周期被破坏。
- 看门狗可能复位。

正确实现：

```
控制任务：
    只发送保存请求到 storage_task

存储任务：
    执行文件系统写入和擦除
    记录结果
    通知控制任务
```

风险：

- 电机失控。
- 通信超时。
- 任务堆积导致系统级故障。

---

## 10. 多机制组合使用方案

## 10.1 推荐架构

```
应用任务
   │
   ▼
Storage Service
   ├─ 配置管理器：版本 + CRC + 双备份
   ├─ 日志管理器：追加写 + 环形回收
   ├─ OTA 管理器：镜像分区 + 状态机
   └─ 诊断管理器：错误码 + 擦写统计
   │
   ▼
LittleFS / Raw Partition Manager
   │
   ▼
Flash HAL
   ├─ SPI/QSPI 驱动
   ├─ DMA
   ├─ Busy/Timeout
   ├─ Page split
   └─ 电源故障处理
   │
   ▼
SPI-NOR Flash
```

## 10.2 存储服务接口

```
typedef enum {
    STORAGE_REQ_SAVE_CONFIG,
    STORAGE_REQ_APPEND_LOG,
    STORAGE_REQ_READ_CONFIG,
} storage_req_type_t;

typedef struct {
    storage_req_type_t type;
    const void *data;
    size_t len;
    uint32_t timeout_ms;
} storage_request_t;

typedef struct {
    int result;
    size_t processed;
} storage_response_t;

int storage_submit(const storage_request_t *req,
                   storage_response_t *resp);
```

设计约束：

- 调用者不能直接持有底层文件句柄。
- 存储服务统一执行互斥和超时。
- 关键请求具备优先级，但擦除不能无限抢占实时任务。
- 请求队列满时必须有明确策略：丢弃、覆盖或阻塞。

## 10.3 配置双版本结构

```
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t payload_len;
    uint32_t sequence;
    uint32_t crc;
} config_header_t;

typedef struct {
    uint32_t sample_rate;
    uint16_t gain;
    uint8_t  mode;
    uint8_t  reserved;
} device_config_t;

static bool config_valid(const config_header_t *hdr,
                         const device_config_t *cfg)
{
    if (hdr->magic != 0x43464731U ||
        hdr->payload_len != sizeof(*cfg)) {
        return false;
    }

    return hdr->crc == crc32(cfg, sizeof(*cfg));
}
```

启动时：

1. 读取 A、B 两份配置。
2. 校验 magic、长度、CRC。
3. 选择 sequence 最大且合法的一份。
4. 两份都无效时加载编译期默认值。
5. 恢复默认值时记录故障事件。

---

## 11. 工业级实际案例分析

## 11.1 案例一：工业传感器配置存储

### 需求

- 配置大小：2 KiB。
- 上电读取。
- 每天更新少于 20 次。
- 掉电不能出现半套参数。
- 支持未来字段扩展。

### 架构

```
config_a.bin
config_b.bin
```

每个文件包含：

```
magic + schema_version + sequence + payload_len + payload + CRC32
```

### 核心流程

```
加载：
    读取 A/B
    校验 CRC 和版本
    选择 sequence 最大者
    都失败则加载默认值

保存：
    sequence++
    写入非当前版本文件
    fsync
    校验回读
    成功后切换当前序号
```

### 设计要点

- 不原地覆盖当前配置。
- schema_version 用于字段迁移。
- sequence 使用无符号回绕比较。
- 保存失败时继续使用内存中的旧配置。
- 参数文件和运行日志分离。

## 11.2 案例二：电池管理系统故障日志

### 需求

- 每秒可能产生数十条日志。
- 单条日志 64 B。
- 设备寿命 10 年。
- 必须保留最近 30 天故障信息。
- 控制任务周期为 1 ms。

### 架构

```
ISR/控制任务
    │ 仅写无锁或短临界区环形 RAM 队列
    ▼
日志任务
    │ 批量聚合 1~4 KiB
    ▼
LittleFS 追加日志
    │
按文件大小轮转
    ▼
log_0001.bin, log_0002.bin ...
```

### 设计要点

- 控制任务不执行 Flash 擦除。
- 日志任务批量写入，降低写放大。
- 日志文件达到阈值后轮转。
- 文件头写入时间范围、设备序号和 CRC。
- 文件系统满时删除最老文件，而不是让写入随机失败。
- 关键故障日志可同步写入，普通诊断日志异步写入。

## 11.3 案例三：工业网关 OTA

### 需求

- 固件大小 4 MiB。
- 下载过程可能断电。
- 新版本启动失败必须回滚。
- 需要防止镜像篡改。

### 架构

```
Bootloader
 ├─ Slot A：当前运行镜像
 ├─ Slot B：下载镜像
 ├─ Boot metadata：状态和尝试次数
 └─ Public key / hash
```

状态机：

```
EMPTY
  ↓ 下载完成 + SHA256 校验
DOWNLOADED
  ↓ 签名校验
VERIFIED
  ↓ Bootloader 设置试运行
TRIAL
  ├─ 应用确认成功 → CONFIRMED
  └─ 超时/崩溃 → 回滚 SLOT A
```

设计要点：

- OTA 镜像不应完全依赖普通文件系统保证原子性。
- Boot metadata 至少双备份。
- `TRIAL` 状态必须有启动次数上限。
- SHA-256 用于完整性，签名用于真实性。
- 断电测试必须覆盖下载、校验、切换、首次启动和确认阶段。

---

## 12. 高频问题深度答疑

### 问题一：LittleFS 能否替代 FATFS？

不能简单替代。

LittleFS 的目标是可靠管理 Raw Flash，强调掉电一致性和低 RAM。FATFS 的目标是实现 FAT 文件系统，适合 SD、eMMC 和 USB 等块设备，并具有 PC 兼容性。

如果需要把卡拔出后插入电脑读取，应使用 FATFS；如果是 MCU 直接控制 SPI-NOR，应优先考虑 LittleFS。

### 问题二：为什么有了磨损均衡仍然会磨损？

磨损均衡只能尽量分散擦除次数，不能消除擦除。

如果某个区域持续写入，文件系统需要在有限空间内搬移数据和回收块。写放大、保留空间不足、静态数据搬移和坏块都会降低有效寿命。

必须同时控制：

```
实际寿命 = 介质额定寿命 × 可用物理空间 / 写放大
```

这只是近似模型，真实寿命还受温度、擦除粒度和坏块影响。

### 问题三：为什么“写文件后立即断电”仍然可能丢数据？

因为数据可能存在多个缓存层：

```
应用缓冲
→ 文件系统缓存
→ Flash 驱动缓存
→ SPI 控制器 FIFO/DMA
→ Flash 内部 Page Buffer
```

只有完成同步、等待 Flash 非忙状态并确认元数据提交，才能认为数据稳定。应用必须明确区分“已接受请求”和“已持久化”。

### 问题四：是否应该每条日志都调用 fsync？

不应一概而论。

- 安全事件、保护动作、关键故障：可以同步写入。
- 高频遥测、调试信息：应批量写入。
- 允许丢失最近几秒数据：按时间窗口同步。
- 不允许丢失任何事件：需要独立高可靠日志机制或硬件掉电保持。

同步调用越频繁，写放大和实时性压力越高。

### 问题五：Flash 文件系统是否需要 CRC？

需要，但 CRC 的职责有限。

CRC 可检测随机位翻转、部分写入和数据损坏，但不能防止恶意篡改，也不能保证整个事务状态正确。

完整方案通常包括：

```
magic + version + length + sequence + CRC
```

安全场景还需要：

```
hash + digital signature + rollback protection
```

### 问题六：内部 MCU Flash 和外部 SPI-NOR 应如何选择？

|需求|内部 Flash|外部 SPI-NOR|
|---|---|---|
|成本|较低|增加器件成本|
|访问延迟|低|受总线影响|
|容量|通常较小|容量可扩展|
|擦写影响|可能阻塞取指|可与代码执行隔离|
|数据可靠性|依赖 MCU 工艺|可选工业级器件|
|维护升级|需谨慎分区|分区更灵活|

如果日志量大、需要 OTA 或参数和代码强隔离，外部 NOR 通常更合适。

---

## 13. 课程核心总结

### 核心要点

1. **Flash 不是可直接覆盖的 RAM。**
2. **擦除粒度通常远大于写入粒度。**
3. **文件系统必须解决掉电一致性、磨损均衡和空间回收。**
4. **LittleFS 适合 MCU + SPI-NOR + 低 RAM 场景。**
5. **Raw NAND 应使用 UBI + UBIFS 或 NAND 专用文件系统。**
6. **高频数据应使用批量追加日志，而不是频繁覆盖单一文件。**
7. **关键配置应具备版本、长度、序号和 CRC。**
8. **OTA 应采用双分区状态机，不能仅依赖文件名切换。**
9. **实时任务不能直接执行不可预测的 Flash 擦除。**
10. **性能瓶颈通常来自擦除延迟和写放大，而不是顺序读取。**

### 性能排序

典型情况下：

```
顺序读取速度：
内存映射 NOR > QSPI NOR > SPI NOR > 文件系统随机读取

更新延迟：
RAM > Page Program > 文件系统提交 > Sector Erase > Block Erase

可靠性设计复杂度：
单值参数 < 双备份参数 < 日志结构 < 完整文件系统 < OTA + 安全回滚
```

### 通用选型结论

```
Raw SPI-NOR + MCU：
    LittleFS

少量固定参数：
    NVS/KV/双备份参数区

Raw NAND + Linux：
    UBI + UBIFS

SD/eMMC/UFS：
    FATFS/ext4/F2FS

OTA：
    独立镜像分区 + Boot metadata + 签名校验
```

---

## 14. 快速参考速查表

### 14.1 场景选型表

|使用场景|推荐方案|
|---|---|
|1~几十 KiB 参数|NVS/KV 或双备份参数|
|SPI-NOR 文件、目录和日志|LittleFS|
|ESP 既有 SPIFFS 工程|SPIFFS，评估维护周期|
|Raw NAND Linux|UBI + UBIFS|
|SD 卡用户文件|FATFS|
|eMMC/UFS 大容量数据|ext4/F2FS|
|OTA 固件镜像|双 Slot 原始分区|
|高频计数器|追加日志/专用磨损均衡计数器|

### 14.2 特性对比表

|特性|推荐机制|
|---|---|
|掉电一致性|Copy-on-write、双备份、事务提交|
|防止热块磨损|动态磨损均衡、日志追加、批量写入|
|快速启动|固定索引、减少全盘扫描、保存挂载信息|
|大文件追加|CTZ/日志结构|
|配置兼容升级|schema version + migration|
|文件完整性|CRC32|
|防篡改|SHA-256 + 数字签名|
|写入失败恢复|回读验证 + 旧版本保留|
|实时性|存储服务任务 + 异步队列|
|空间不足|水位线、文件轮转、主动 GC|

---

## 15. 学习效果自检

完成本课后，应能够回答：

- [ ]  为什么 Flash 写入不能从 `0` 改回 `1`？
- [ ]  Page Program 和 Sector Erase 的粒度分别是什么？
- [ ]  为什么文件系统必须执行磨损均衡？
- [ ]  LittleFS 的 metadata pair 解决了什么问题？
- [ ]  什么是写放大，如何测量？
- [ ]  如何估算某类日志的 Flash 寿命？
- [ ]  为什么擦除操作不能运行在 1 ms 控制任务中？
- [ ]  如何设计掉电后选择新旧配置版本的算法？
- [ ]  FATFS、LittleFS、UBIFS 的适用边界是什么？
- [ ]  OTA 的 `DOWNLOADED`、`VERIFIED`、`TRIAL`、`CONFIRMED` 状态分别有什么意义？
- [ ]  如何验证文件系统的掉电一致性？
- [ ]  如何区分数据完整性、真实性和防回滚？

---

## 16. 实践与进阶路径

### 16.1 梯度实战任务

#### 任务一：实现 Flash HAL

要求：

- 支持跨 Page 写入。
- 检查地址和长度溢出。
- 支持忙状态轮询和超时。
- 支持模拟 Flash 后端。
- 覆盖非法地址、跨页、超时和写保护测试。

#### 任务二：移植 LittleFS

要求：

- 实现 `read/prog/erase/sync` 回调。
- 配置 `read_size`、`prog_size`、`block_size`、`block_count`。
- 验证格式化、挂载、创建目录、文件追加和删除。
- 记录挂载时间、RAM 消耗和擦除次数。

#### 任务三：实现掉电注入测试

在以下位置随机复位：

```
erase 开始前
erase 中
program 开始前
program 中
metadata 提交前
metadata 提交后
fsync 前
fsync 后
```

测试判定：

- 文件系统能否重新挂载。
- 旧版本或新版本是否完整。
- 是否出现目录丢失。
- 是否出现无法回收的空间。
- 是否出现静默数据错误。

#### 任务四：建立寿命测试模型

记录：

```
逻辑写入量
物理 Page Program 次数
物理 Erase 次数
写放大
最大擦除次数
最小擦除次数
GC 次数
平均和 P99 写延迟
```

重点观察：

```
磨损均衡差异 = 最大擦除次数 - 最小擦除次数
```

#### 任务五：设计 OTA 存储系统

实现：

- 双 Slot 镜像布局。
- SHA-256 校验。
- 签名验证。
- 试运行确认。
- 启动失败回滚。
- Boot metadata 双备份。
- 断电和看门狗复位注入。

### 16.2 性能测试方法

至少测量：

- 顺序读取吞吐。
- 小块随机读取延迟。
- Page Program 平均值和 P99。
- Sector Erase 平均值和最大值。
- 文件创建、追加、删除延迟。
- 挂载时间。
- 文件系统满容量时的写入延迟。
- 多任务竞争下的最大阻塞时间。
- 掉电恢复耗时。
- 写放大和擦除分布。

### 16.3 进阶学习方向

1. LittleFS 源码中的 block allocator、metadata pair 和 CTZ skip-list。
2. Linux MTD、UBI、UBIFS 的映射关系。
3. NAND Flash ECC、坏块标记和读扰动。
4. FTL、L2P 映射、GC 和 over-provisioning。
5. Flash Translation Layer 与数据库 WAL 的设计类比。
6. 存储系统形式化一致性验证。
7. OTA 安全启动、密钥管理和防回滚。
8. 高可靠数据记录器的时间戳、序列号和事件溯源设计。
9. 基于故障注入的存储可靠性验证。
10. 面向 IEC 61508、ISO 26262 的非易失存储安全机制。