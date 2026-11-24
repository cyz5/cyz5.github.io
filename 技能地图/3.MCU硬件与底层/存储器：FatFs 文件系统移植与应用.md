
## 1. 学习目标

### 理解

- 理解 FatFs 的分层架构：应用层、FatFs 核心层、Disk I/O 介质适配层。
- 理解 FAT12/FAT16/FAT32/exFAT 的目录、FAT 表、簇、扇区和文件分配机制。
- 理解 `ffconf.h` 配置项对代码体积、RAM 占用、实时性和功能边界的影响。
- 理解 SD 卡、SPI NOR Flash、QSPI Flash、USB MSC 等存储介质的访问差异。

### 掌握

- 掌握 FatFs 在裸机、FreeRTOS 和嵌入式 Linux 辅助系统中的移植方法。
- 掌握 `disk_initialize()`、`disk_status()`、`disk_read()`、`disk_write()`、`disk_ioctl()` 的实现。
- 掌握文件、目录、同步、格式化、分区、卷挂载和错误恢复流程。
- 掌握缓存一致性、扇区对齐、写保护、超时和掉电保护设计。

### 精通

- 能够分析文件系统损坏、写入卡顿、目录遍历变慢、数据丢失等现场问题。
- 能够根据介质特性选择 FATFS、LittleFS、原始块存储或数据库式日志结构。
- 能够量化 FatFs 的 Flash、RAM、吞吐量、写放大和实时性影响。
- 能够设计多任务环境下的文件访问互斥与后台写入架构。

### 能够设计

- 能够设计支持 SD 卡热插拔、异常掉电、自动挂载、日志滚动和空间回收的工业级存储模块。
- 能够实现高可靠数据记录器、配置存储、升级包存储和导出介质管理方案。
- 能够建立文件系统压力测试、故障注入和数据完整性验证体系。

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、函数指针、位操作和错误处理。
- MCU 启动流程、中断、DMA、Cache 和内存屏障。
- SPI、SDIO/SDMMC、QSPI、USB MSC 等总线和存储控制器。
- FreeRTOS 任务、互斥锁、信号量、临界区和优先级调度。
- FAT 文件系统基本概念：扇区、簇、目录项、FAT 表、根目录。

### 技能要求

- 能够阅读 MCU 厂商 HAL/LL 驱动和 DMA 驱动。
- 能够使用逻辑分析仪、示波器和文件系统检查工具。
- 能够进行硬件故障注入、掉电测试和长期稳定性测试。
- 能够编写可重复的单元测试、压力测试和性能测试程序。

## 3. 技术概述

FatFs 是一个面向嵌入式系统的轻量级 FAT 文件系统模块。它本身不直接驱动 SD 卡或 Flash，而是通过统一的 Disk I/O 接口访问底层块设备。

典型分层如下：

```
业务应用
  |
  | f_open / f_read / f_write / f_sync / f_close
  v
FatFs 核心层
  |
  | disk_initialize / disk_read / disk_write / disk_ioctl
  v
块设备适配层
  |
  +-- SDMMC/SDIO
  +-- SPI SD Card
  +-- USB MSC
  +-- SPI NOR Flash
  +-- NAND/eMMC
```

### FAT 文件系统基本对象

- **物理扇区**：设备最小读写单位，常见为 512 字节。
- **簇 Cluster**：文件系统分配空间的最小单位，由一个或多个扇区组成。
- **FAT 表**：记录簇链关系。
- **目录项 Directory Entry**：保存文件名、属性、起始簇和文件大小。
- **FSInfo**：FAT32 可选结构，用于缓存空闲簇数量和下一次分配位置。
- **卷 Volume**：一个独立的文件系统区域。

FatFs 支持的主要文件系统类型：

|类型|典型容量范围|长处|局限|
|---|---|---|---|
|FAT12|软盘、小容量介质|实现简单|容量很小|
|FAT16|小型 Flash、旧式设备|兼容性好|单卷容量受限|
|FAT32|SD 卡、U 盘|通用性最好|单文件最大约 4 GiB|
|exFAT|大容量 SDXC、U 盘|支持超大文件|代码、RAM 和授权/兼容要求更高|
|原始块存储|配置、参数、环形日志|可控、实时性强|缺少通用文件接口|
|LittleFS|NOR Flash|掉电恢复和磨损均衡较好|与 PC 交换不如 FAT 方便|

## 4. 核心特性横向对比

### 不同底层介质

|维度|SDMMC SD 卡|SPI SD 卡|SPI NOR Flash|USB MSC|
|---|---|---|---|---|
|接口带宽|高，典型 10~50 MB/s|低至中，约 0.5~8 MB/s|中，约 1~20 MB/s|取决于 USB，FS 约 1~10 MB/s|
|最小访问|512 字节扇区|512 字节扇区|通常 256/4 KiB 页或擦除块|512 字节逻辑块|
|写入延迟|1~500 ms，波动大|1~500 ms，波动大|页写 0.3~~3 ms，擦除 10~~500 ms|波动大|
|掉电风险|高|高|高，需设计日志和擦除策略|高|
|多任务访问|需要锁|需要锁|需要锁|通常需要设备状态管理|
|PC 兼容性|高|高|需额外 FAT 层|高|
|适合场景|大容量日志、数据导出|成本敏感、小吞吐|固定配置、内部文件|外部 U 盘数据交换|

### FatFs 配置选项

|配置项|作用|工程影响|
|---|---|---|
|`FF_FS_READONLY`|只读模式|关闭写路径，减少代码和风险|
|`FF_FS_MINIMIZE`|裁剪 API|禁用不需要的功能|
|`FF_USE_MKFS`|是否支持格式化|生产设备通常应谨慎开放|
|`FF_USE_LFN`|长文件名|增加栈/RAM，需配置编码和工作缓冲区|
|`FF_FS_EXFAT`|exFAT 支持|增加代码量和兼容能力|
|`FF_FS_REENTRANT`|多任务重入保护|需要实现同步对象|
|`FF_FS_TINY`|减少文件对象缓存|节省 RAM，但可能增加介质访问|
|`FF_MAX_SS`|最大扇区大小|影响工作区和接口兼容性|
|`FF_FS_LOCK`|文件共享锁|防止同一文件被非法并发打开|
|`FF_STR_VOLUME_ID`|字符串卷标识|方便多卷管理，但增加配置复杂度|

## 5. 底层原理与功能特性深度解析

### 5.1 FatFs 的调用链

以写文件为例：

```
f_write()
  -> validate()
  -> move_window()
  -> create_chain()
  -> disk_read()
  -> disk_write()
  -> sync_window()
  -> disk_ioctl(CTRL_SYNC)
```

`f_write()` 并不保证每次调用都立即把全部数据写入物理介质。FatFs 可能先更新：

- 文件数据区；
- FAT 表；
- 目录项；
- 文件长度；
- 文件起始簇和后续簇链。

只有在 `f_sync()` 或 `f_close()` 时，目录项和缓存数据才会完整提交。

### 5.2 Disk I/O 接口实现

以下示例以 STM32 + SDMMC + DMA 为例。底层 HAL 函数名需要根据具体芯片调整。

```
#include "diskio.h"
#include "sd_driver.h"

static volatile DSTATUS g_sd_status = STA_NOINIT;
static volatile bool g_sd_present = true;

DSTATUS disk_initialize(BYTE pdrv)
{
    if (pdrv != 0 || !g_sd_present) {
        return STA_NOINIT;
    }

    if (sd_hw_init() != SD_OK) {
        g_sd_status = STA_NOINIT;
        return g_sd_status;
    }

    if (sd_get_block_size() != 512U) {
        g_sd_status = STA_NOINIT;
        return g_sd_status;
    }

    g_sd_status = 0;
    return g_sd_status;
}

DSTATUS disk_status(BYTE pdrv)
{
    if (pdrv != 0 || !g_sd_present) {
        return STA_NOINIT;
    }

    return g_sd_status;
}

DRESULT disk_read(BYTE pdrv, BYTE *buff, LBA_t sector, UINT count)
{
    if (pdrv != 0 || buff == NULL || count == 0U) {
        return RES_PARERR;
    }

    if (g_sd_status & STA_NOINIT) {
        return RES_NOTRDY;
    }

    if (sd_read_blocks_dma(buff, sector, count, 1000U) != SD_OK) {
        return RES_ERROR;
    }

    return RES_OK;
}

DRESULT disk_write(BYTE pdrv, const BYTE *buff, LBA_t sector, UINT count)
{
#if FF_FS_READONLY == 0
    if (pdrv != 0 || buff == NULL || count == 0U) {
        return RES_PARERR;
    }

    if (g_sd_status & STA_NOINIT) {
        return RES_NOTRDY;
    }

    if (sd_write_blocks_dma(buff, sector, count, 2000U) != SD_OK) {
        return RES_ERROR;
    }

    return RES_OK;
#else
    (void)pdrv;
    (void)buff;
    (void)sector;
    (void)count;
    return RES_WRPRT;
#endif
}

DRESULT disk_ioctl(BYTE pdrv, BYTE cmd, void *buff)
{
    if (pdrv != 0 || buff == NULL) {
        return RES_PARERR;
    }

    switch (cmd) {
    case CTRL_SYNC:
        return sd_wait_ready(2000U) == SD_OK ? RES_OK : RES_ERROR;

    case GET_SECTOR_COUNT:
        *(LBA_t *)buff = sd_get_sector_count();
        return RES_OK;

    case GET_SECTOR_SIZE:
        *(WORD *)buff = 512U;
        return RES_OK;

    case GET_BLOCK_SIZE:
        /* 返回以扇区为单位的擦除块大小 */
        *(DWORD *)buff = sd_get_erase_block_sectors();
        return RES_OK;

    default:
        return RES_PARERR;
    }
}
```

### 5.3 `CTRL_SYNC` 的正确含义

`CTRL_SYNC` 不是简单地返回 `RES_OK`。它必须确保：

1. DMA 已经完成；
2. SD 卡内部写忙状态已经释放；
3. 控制器 FIFO 没有残留数据；
4. Cache 已完成清理或失效处理；
5. 介质可以接受下一条命令。

错误实现：

```
case CTRL_SYNC:
    return RES_OK;
```

这会导致 `f_close()` 返回成功，但数据仍停留在 SD 卡内部缓存，掉电后文件可能损坏。

### 5.4 文件写入示例

```
FRESULT storage_append(const char *path, const void *data, UINT size)
{
    FIL file;
    FRESULT fr;
    UINT written;

    if (path == NULL || data == NULL || size == 0U) {
        return FR_INVALID_PARAMETER;
    }

    fr = f_open(&file, path, FA_OPEN_APPEND | FA_WRITE);
    if (fr != FR_OK) {
        return fr;
    }

    fr = f_write(&file, data, size, &written);
    if (fr == FR_OK && written != size) {
        fr = FR_DISK_ERR;
    }

    if (fr == FR_OK) {
        fr = f_sync(&file);
    }

    {
        FRESULT close_fr = f_close(&file);
        if (fr == FR_OK) {
            fr = close_fr;
        }
    }

    return fr;
}
```

注意：高频每条记录都调用 `f_sync()` 会明显增加写放大和延迟。工业系统一般采用批量提交策略。

### 5.5 挂载、格式化和目录创建

#### 5.5.1 挂载文件系统

`f_mount()` 只负责把 `FATFS` 工作对象注册到 FatFs 卷管理器中，并不一定立即访问物理介质。

```
#include "ff.h"
#include "diskio.h"

static FATFS g_fs;
static bool g_fs_mounted = false;

FRESULT storage_mount(void)
{
    FRESULT fr;

    /*
     * opt = 1：
     * 立即执行挂载和文件系统识别。
     * opt = 0 只注册对象，首次文件访问时再挂载。
     */
    fr = f_mount(&g_fs, "0:", 1);

    if (fr == FR_OK) {
        g_fs_mounted = true;
    } else {
        g_fs_mounted = false;
    }

    return fr;
}
```

生产环境不建议忽略返回值。典型处理策略如下：

```
typedef enum {
    STORAGE_STATE_OFFLINE = 0,
    STORAGE_STATE_INIT,
    STORAGE_STATE_MOUNTED,
    STORAGE_STATE_NO_FILESYSTEM,
    STORAGE_STATE_ERROR
} storage_state_t;

static storage_state_t g_storage_state;

FRESULT storage_start(void)
{
    FRESULT fr;

    g_storage_state = STORAGE_STATE_INIT;

    if (disk_initialize(0) & STA_NOINIT) {
        g_storage_state = STORAGE_STATE_OFFLINE;
        return FR_NOT_READY;
    }

    fr = f_mount(&g_fs, "0:", 1);

    switch (fr) {
    case FR_OK:
        g_storage_state = STORAGE_STATE_MOUNTED;
        break;

    case FR_NO_FILESYSTEM:
        g_storage_state = STORAGE_STATE_NO_FILESYSTEM;
        break;

    case FR_DISK_ERR:
    case FR_NOT_READY:
        g_storage_state = STORAGE_STATE_ERROR;
        break;

    default:
        g_storage_state = STORAGE_STATE_ERROR;
        break;
    }

    return fr;
}
```

#### 5.5.2 自动格式化策略

自动格式化必须谨慎。以下场景不应默认格式化：

- 用户数据盘；
- 现场采集数据盘；
- 无法确认介质身份的可插拔 SD 卡；
- 发生单次读错误而不是 `FR_NO_FILESYSTEM` 时；
- 设备中存在未导出的关键数据。

推荐策略：

```
挂载
 |
 +-- FR_OK
 |     |
 |     +-- 正常工作
 |
 +-- FR_NO_FILESYSTEM
 |     |
 |     +-- 判断是否允许自动格式化
 |           |
 |           +-- 允许：格式化并创建目录
 |           +-- 不允许：上报“未格式化”
 |
 +-- FR_DISK_ERR / FR_NOT_READY
       |
       +-- 不格式化
       +-- 检查卡插入状态、供电、总线和硬件错误
```

#### 5.5.3 格式化函数

不同 FatFs 版本的 `f_mkfs()` 原型可能不同。以下示例适用于较新的 FatFs 版本：

```
FRESULT storage_format(void)
{
#if FF_USE_MKFS
    MKFS_PARM opt;
    BYTE work[FF_MAX_SS];
    FRESULT fr;

    memset(&opt, 0, sizeof(opt));

    /*
     * fmt = 0：
     * 由 FatFs 根据介质容量选择 FAT 类型。
     *
     * au_size = 0：
     * 由 FatFs 自动选择分配单元大小。
     */
    opt.fmt = FM_ANY;
    opt.au_size = 0;

    fr = f_mkfs("0:", &opt, work, sizeof(work));
    if (fr != FR_OK) {
        return fr;
    }

    /*
     * 格式化后重新挂载。
     */
    (void)f_mount(NULL, "0:", 0);

    return f_mount(&g_fs, "0:", 1);
#else
    return FR_DENIED;
#endif
}
```

如果项目要求固定 FAT32，可以明确指定：

```
opt.fmt = FM_FAT32;
```

但不建议对小容量介质强制 FAT32，因为会造成簇空间浪费和兼容性问题。

#### 5.5.4 创建目录

```
FRESULT storage_mkdir_if_needed(const char *path)
{
    FRESULT fr;

    if (path == NULL || path[0] == '\0') {
        return FR_INVALID_PARAMETER;
    }

    fr = f_mkdir(path);

    if (fr == FR_OK || fr == FR_EXIST) {
        return FR_OK;
    }

    return fr;
}
```

初始化目录树：

```
FRESULT storage_prepare_directories(void)
{
    FRESULT fr;

    fr = storage_mkdir_if_needed("0:/config");
    if (fr != FR_OK) {
        return fr;
    }

    fr = storage_mkdir_if_needed("0:/log");
    if (fr != FR_OK) {
        return fr;
    }

    fr = storage_mkdir_if_needed("0:/update");
    if (fr != FR_OK) {
        return fr;
    }

    fr = storage_mkdir_if_needed("0:/export");
    if (fr != FR_OK) {
        return fr;
    }

    return FR_OK;
}
```

目录创建不是事务操作。如果创建到中间目录失败，后续目录不会自动回滚。启动流程应允许重复执行，确保幂等。

#### 5.5.5 完整启动流程

```
FRESULT storage_init(bool allow_format)
{
    FRESULT fr;

    fr = storage_start();

    if (fr == FR_NO_FILESYSTEM && allow_format) {
        fr = storage_format();
    }

    if (fr != FR_OK) {
        return fr;
    }

    fr = storage_prepare_directories();
    if (fr != FR_OK) {
        (void)f_mount(NULL, "0:", 0);
        g_fs_mounted = false;
        return fr;
    }

    return FR_OK;
}
```

### 5.6 文件系统卸载和热插拔

#### 5.6.1 正确卸载流程

```
FRESULT storage_unmount(void)
{
    FRESULT fr;

    if (!g_fs_mounted) {
        return FR_OK;
    }

    /*
     * 先确保上层没有正在使用的 FIL、DIR 对象。
     * FatFs 不会替应用自动关闭所有文件。
     */
    fr = f_mount(NULL, "0:", 0);

    if (fr == FR_OK) {
        g_fs_mounted = false;
    }

    return fr;
}
```

不能在其他任务仍持有打开文件时直接卸载。正确流程应为：

```
停止写入请求
    |
等待写入任务退出或进入空闲态
    |
执行 f_sync / f_close
    |
执行 f_mount(NULL, ...)
    |
关闭 SD 卡电源或释放总线
```

#### 5.6.2 热插拔检测

SD 卡检测通常由卡座的 CD 引脚完成。检测到拔出后，不能只设置一个标志位，还需要阻断后续 I/O。

```
void storage_card_removed_isr(void)
{
    /*
     * 中断中只做状态通知，不执行 FatFs API。
     */
    storage_event_notify(STORAGE_EVENT_REMOVED);
}
```

任务中处理：

```
void storage_event_task(void *argument)
{
    storage_event_t event;

    for (;;) {
        if (storage_event_wait(&event, portMAX_DELAY) != 0) {
            continue;
        }

        if (event == STORAGE_EVENT_REMOVED) {
            storage_set_online(false);

            /*
             * 关闭上层文件句柄，停止后台写入。
             */
            log_service_stop();

            /*
             * 不再访问物理卡。
             */
            (void)storage_unmount();
        } else if (event == STORAGE_EVENT_INSERTED) {
            vTaskDelay(pdMS_TO_TICKS(100));

            if (storage_init(false) == FR_OK) {
                storage_set_online(true);
                log_service_start();
            }
        }
    }
}
```

拔卡时如果底层仍在 DMA 读写，必须先停止 DMA 并复位 SD 控制器，否则重新插卡后可能出现总线状态机卡死。

### 5.7 多任务与重入保护

#### 5.7.1 `FF_FS_REENTRANT`

启用多任务支持：

```
#define FF_FS_REENTRANT    1
#define FF_FS_TIMEOUT      1000
```

同时实现同步对象接口。接口名称依 FatFs 版本不同，通常在 `ffsystem.c` 中实现：

```
#include "ff.h"
#include "FreeRTOS.h"
#include "semphr.h"

#if FF_FS_REENTRANT

static SemaphoreHandle_t g_fs_mutex;

int ff_cre_syncobj(BYTE vol, FF_SYNC_t *sobj)
{
    (void)vol;

    if (sobj == NULL) {
        return 0;
    }

    g_fs_mutex = xSemaphoreCreateMutex();
    if (g_fs_mutex == NULL) {
        *sobj = NULL;
        return 0;
    }

    *sobj = g_fs_mutex;
    return 1;
}

int ff_del_syncobj(FF_SYNC_t sobj)
{
    if (sobj != NULL) {
        vSemaphoreDelete((SemaphoreHandle_t)sobj);
    }

    g_fs_mutex = NULL;
    return 1;
}

int ff_req_grant(FF_SYNC_t sobj)
{
    if (sobj == NULL) {
        return 0;
    }

    return xSemaphoreTake(
        (SemaphoreHandle_t)sobj,
        pdMS_TO_TICKS(FF_FS_TIMEOUT)
    ) == pdTRUE;
}

void ff_rel_grant(FF_SYNC_t sobj)
{
    if (sobj != NULL) {
        (void)xSemaphoreGive((SemaphoreHandle_t)sobj);
    }
}

#endif
```

#### 5.7.2 不要把 FatFs 锁和底层总线锁混为一谈

存在两类锁：

1. **文件系统锁**：保护 FatFs 内部状态；
2. **设备总线锁**：保护 SPI、SDMMC 或共享 DMA 控制器。

如果多个外设共享 SPI，总线驱动仍然需要单独加锁：

```
FRESULT spi_disk_read(BYTE *buff, LBA_t sector, UINT count)
{
    FRESULT fr = FR_OK;

    if (spi_bus_lock(pdMS_TO_TICKS(100)) != true) {
        return FR_TIMEOUT;
    }

    if (spi_sd_select() != 0) {
        fr = FR_NOT_READY;
        goto exit;
    }

    if (spi_sd_read_blocks(buff, sector, count) != 0) {
        fr = FR_DISK_ERR;
    }

    spi_sd_deselect();

exit:
    spi_bus_unlock();
    return fr;
}
```

锁顺序必须固定。例如：

```
文件系统锁 -> SPI 总线锁 -> SD 卡设备锁
```

禁止某些路径采用：

```
SPI 总线锁 -> 文件系统锁
```

否则可能形成死锁。

### 5.8 长文件名与 Unicode

启用长文件名：

```
#define FF_USE_LFN       2
#define FF_MAX_LFN       255
#define FF_CODE_PAGE     936
```

常见 `FF_USE_LFN` 模式：

|配置|缓冲区位置|特点|
|---|---|---|
|`0`|不支持 LFN|代码和 RAM 最小|
|`1`|栈|简单，但可能造成任务栈溢出|
|`2`|FatFs 工作区|常用，降低任务栈风险|
|`3`|静态缓冲区|RAM 占用固定，需要考虑并发|
|`>= 2`|需要 LFN 工作空间|工作区大小约与最大文件名相关|

嵌入式设备推荐：

- 文件名由系统生成时，优先使用 ASCII 短文件名；
- 与 PC 交互且需要中文文件名时，再启用 LFN；
- 不要在小任务栈中使用栈上的 LFN 缓冲；
- 明确处理不同工具链和 PC 环境的编码差异。

### 5.9 文件同步与掉电保护

#### 5.9.1 `f_write()`、`f_sync()`、`f_close()` 的区别

|API|作用|
|---|---|
|`f_write()`|写入文件数据，可能只更新缓存|
|`f_sync()`|将文件数据、FAT 和目录项同步到介质|
|`f_close()`|同步并释放文件对象|
|`f_lseek()`|改变文件指针，不等于提交数据|

对于关键记录，应采用：

```
f_write();
f_sync();
```

不要认为 `f_write()` 返回 `FR_OK` 就意味着数据已安全落盘。

#### 5.9.2 两阶段提交文件

防止设备掉电时产生半文件：

```
FRESULT storage_write_atomic(
    const char *final_path,
    const void *data,
    UINT size)
{
    FIL file;
    FRESULT fr;
    UINT written;
    const char *tmp_path = "0:/config/config.tmp";

    fr = f_open(&file, tmp_path, FA_CREATE_ALWAYS | FA_WRITE);
    if (fr != FR_OK) {
        return fr;
    }

    fr = f_write(&file, data, size, &written);
    if (fr == FR_OK && written != size) {
        fr = FR_DISK_ERR;
    }

    if (fr == FR_OK) {
        fr = f_sync(&file);
    }

    {
        FRESULT close_fr = f_close(&file);
        if (fr == FR_OK) {
            fr = close_fr;
        }
    }

    if (fr != FR_OK) {
        (void)f_unlink(tmp_path);
        return fr;
    }

    /*
     * FAT 没有真正的 POSIX rename 事务语义。
     * 生产系统还应使用版本号、校验和和启动恢复逻辑。
     */
    (void)f_unlink(final_path);

    fr = f_rename(tmp_path, final_path);
    return fr;
}
```

更可靠的配置文件格式：

```
magic
version
sequence
payload_length
payload_crc32
payload
```

启动时：

1. 检查 `magic`；
2. 检查版本；
3. 检查长度；
4. 计算 CRC32；
5. 比较序列号；
6. 在 `.tmp` 和正式文件之间选择最新有效版本。

### 6. 性能量化分析

以下数据为典型工程测量范围，测试平台：

- MCU：STM32H743，480 MHz；
- RTOS：FreeRTOS；
- FatFs：R0.15；
- SD 卡：工业级 8 GB；
- 扇区：512 字节；
- DMA：启用；
- Cache：D-Cache 启用并正确维护；
- 编译器：GCC `-O2`；
- 测试数据：连续写入 8 MiB。

实际数值会受到 SD 卡型号、温度、文件系统碎片、总线频率和写入模式影响。

#### 6.1 典型性能数据

|操作|典型耗时/吞吐|
|---|---|
|单扇区读取 512 B|0.2~2 ms|
|连续读取 1 MiB|8~40 ms|
|单扇区写入|2~200 ms|
|连续写入 1 MiB|20~300 ms|
|`f_sync()` 正常延迟|2~100 ms|
|`f_sync()` 极端延迟|0.5~2 s|
|创建普通文件|1~100 ms|
|遍历 1000 个短文件|20~500 ms|

SD 卡写入延迟不是稳定常数。垃圾回收、擦除块管理和内部 FTL 整理会造成长尾延迟。

#### 6.2 写入方式对比

|写入策略|平均吞吐|写放大|实时性|
|---|---|---|---|
|每条记录 `f_open/f_write/f_close`|低|很高|差|
|长期打开文件，逐条 `f_write`|中|中|受缓存影响|
|批量写入 4~32 KiB|高|较低|较好|
|批量写入并周期 `f_sync`|高|可控|可预测性较好|
|预分配连续文件后写入|最高|低|最好|

#### 6.3 写放大分析

假设每条日志为 100 字节，每条记录都打开、写入并关闭文件：

```
有效数据：100 B
物理扇区最小写入：512 B
目录项/FAT 更新：约 512~1536 B
潜在内部擦除：若干 KiB
```

仅从文件系统逻辑层估计：

```
写放大 ≈ 512 / 100 + FAT/目录额外开销
       ≈ 5.12 + 额外开销
```

如果将 32 条记录聚合为 3200 字节：

```
有效数据：3200 B
数据扇区：7 个 512 B 扇区
目录和 FAT 更新次数显著减少
```

通常可获得：

- **2~10 倍吞吐提升**；
- **显著降低 `f_sync()` 次数**；
- **降低 SD 卡内部垃圾回收概率**；
- **减少文件系统碎片**。

#### 6.4 内存开销

典型配置下：

|对象|典型 RAM 占用|
|---|---|
|`FATFS` 对象|500 B~2 KiB|
|`FIL` 对象|500 B~1 KiB|
|`DIR` 对象|500 B~1 KiB|
|512 B 扇区缓冲区|512 B|
|LFN 缓冲区|512 B~1 KiB 或更高|
|应用层批量日志缓冲区|4~64 KiB|

启用长文件名、exFAT、多卷和文件锁后，RAM 与 Flash 占用都会增加。

#### 6.5 优化措施

##### 优化一：使用 DMA

```
CPU 轮询收发 -> DMA 块传输
```

收益：

- 降低 CPU 占用；
- 允许任务在等待期间阻塞；
- 减少高优先级任务被长时间占用的概率。

##### 优化二：批量读写

推荐批量大小：

```
512 B：功能验证
4 KiB：通用配置
8~32 KiB：日志和数据记录
64 KiB 以上：大文件连续传输
```

##### 优化三：缓存对齐

```
__attribute__((aligned(32)))
static uint8_t g_sd_dma_buffer[32 * 1024];
```

对于 Cortex-M7，Cache line 通常为 32 字节。DMA 缓冲区应满足：

- 起始地址按 Cache line 对齐；
- 长度按 Cache line 对齐；
- DMA 写入前执行 Clean；
- DMA 写入后执行 Invalidate。

##### 优化四：减少目录中文件数量

大量小文件会导致：

- 目录遍历变慢；
- 文件创建和删除变慢；
- 目录碎片增加；
- FAT 表和目录项更新频繁。

日志系统应优先采用：

```
按时间滚动的大文件
```

而不是：

```
每条记录一个文件
```

### 7. 应用场景选型指南

#### 7.1 纯文本决策流程图

```
是否需要与 PC、Windows、Linux 直接交换文件？
|
+-- 否
|   |
|   +-- 是否要求强掉电恢复和磨损均衡？
|       |
|       +-- 是 --> LittleFS / 日志结构存储
|       +-- 否 --> 原始块存储 / 双备份参数区
|
+-- 是
    |
    +-- 介质是否为 SD 卡、U 盘、eMMC？
    |   |
    |   +-- 是 --> FatFs
    |
    +-- 介质是否为内部 NOR Flash？
        |
        +-- 是
            |
            +-- 数据量小、实时性要求高 --> 原始参数区
            +-- 需要文件接口但不强调 PC 兼容 --> LittleFS
            +-- 必须拔出后由 PC 读取 --> FatFs + Flash 块设备适配
```

#### 7.2 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|设备运行日志|连续追加、掉电容错|FatFs + 批量日志 + 滚动文件|方便导出和分析|
|参数配置|小数据、强一致性|双文件/双槽位 + CRC|不应直接频繁改 FAT|
|固件升级包|大文件、校验和版本管理|FatFs + 临时文件 + SHA/CRC|支持外部介质导入|
|SD 卡数据导出|PC 兼容|FatFs|工具链成熟|
|内部 NOR 配置|低延迟、高可靠|原始块 + CRC + 序列号|避免 FAT 写放大|
|音频/波形记录|大吞吐|SDMMC + 预分配 + 大块写|降低实时性抖动|
|黑匣子记录|关键数据不可丢失|双介质或环形日志|提高故障存活能力|

### 8. 工程最佳实践

#### 8.1 设计原则

1. **FatFs 只处理文件系统，不负责业务一致性。**
2. **底层 Disk I/O 必须提供明确的超时和错误分类。**
3. **所有文件访问必须有生命周期管理。**
4. **高频数据必须批量写入。**
5. **关键文件必须有版本号、长度和 CRC。**
6. **不要在中断中调用 FatFs API。**
7. **不要在高优先级实时任务中直接执行 `f_sync()`。**
8. **不要把 `FR_OK` 简单等同于数据已经物理落盘。**
9. **文件系统异常时不要立即自动格式化。**
10. **必须对拔卡、掉电、总线错误和介质寿命进行设计。**

#### 8.2 选型决策矩阵

|需求|FatFs|LittleFS|原始块存储|
|---|---|---|---|
|PC 直接读取|5|1|1|
|大容量文件|5|3|2|
|NOR Flash 适配|3|5|5|
|掉电恢复|2|5|4|
|实时性|2|4|5|
|开发通用性|5|3|2|
|文件目录能力|5|4|1|
|维护成本|4|3|2|

评分：1 表示弱，5 表示强。

#### 8.3 工业级编码规范

- 所有 FatFs 返回值必须检查。
- `UINT *bw`、`UINT *br` 必须检查实际读写长度。
- 路径统一使用卷号前缀，例如 `"0:/log/data.bin"`。
- 文件句柄必须保证所有错误路径都执行 `f_close()`。
- 禁止返回局部变量地址作为 FatFs 缓冲区。
- DMA 缓冲区必须满足对齐和 Cache 一致性要求。
- 对大文件操作使用 `FSIZE_t`，不要使用 32 位有符号整数保存文件大小。
- 目录遍历过程中正确处理 `f_readdir()` 返回的空文件名。
- 需要支持 4 GiB 以上文件时评估 exFAT 和 `FSIZE_t` 配置。
- 关键路径应记录错误码、介质状态、当前文件和扇区信息。

### 9. 常见错误与避坑指南

#### 9.1 错误一：忽略实际读写长度

错误代码：

```
UINT bw;

f_write(&file, buffer, sizeof(buffer), &bw);

/* 错误：默认认为已经写完 */
return FR_OK;
```

根因：

- SD 卡空间不足；
- 介质中途拔出；
- DMA 超时；
- 底层驱动提前终止。

正确实现：

```
UINT bw;
FRESULT fr;

fr = f_write(&file, buffer, sizeof(buffer), &bw);

if (fr != FR_OK) {
    return fr;
}

if (bw != sizeof(buffer)) {
    return FR_DISK_ERR;
}
```

风险：

- 日志尾部丢失；
- 固件包被截断；
- 上层错误判断为成功。

#### 9.2 错误二：在中断中调用 FatFs

错误代码：

```
void sd_detect_irq_handler(void)
{
    f_mount(NULL, "0:", 0);  /* 错误 */
}
```

根因：

- FatFs 可能获取互斥锁；
- 可能执行长时间介质访问；
- 可能调用非 ISR 安全的 RTOS API；
- 中断上下文不允许阻塞。

正确实现：

```
void sd_detect_irq_handler(void)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    xQueueSendFromISR(
        g_storage_event_queue,
        &(storage_event_t){ STORAGE_EVENT_REMOVED },
        &higher_priority_task_woken
    );

    portYIELD_FROM_ISR(higher_priority_task_woken);
}
```

风险：

- 系统死锁；
- HardFault；
- 中断延迟失控；
- 文件系统内部状态破坏。

#### 9.3 错误三：`CTRL_SYNC` 直接返回成功

错误代码：

```
DRESULT disk_ioctl(BYTE pdrv, BYTE cmd, void *buff)
{
    if (cmd == CTRL_SYNC) {
        return RES_OK;
    }

    return RES_PARERR;
}
```

根因：

- 未等待卡内部 Busy；
- 未等待 DMA；
- 未清理 Cache；
- 破坏了 FatFs 对同步语义的假设。

正确实现：

```
case CTRL_SYNC:
    if (sd_dma_is_busy()) {
        if (sd_wait_dma_done(2000U) != SD_OK) {
            return RES_ERROR;
        }
    }

    if (sd_wait_ready(2000U) != SD_OK) {
        return RES_ERROR;
    }

    return RES_OK;
```

风险：

- 文件关闭成功但掉电丢数据；
- FAT 表与目录项不一致；
- 下次挂载出现 `FR_INT_ERR` 或 `FR_NO_FILESYSTEM`。

#### 9.4 错误四：Cortex-M7 DMA 与 Cache 不一致

错误代码：

```
uint8_t buffer[512];

sd_read_blocks_dma(buffer, sector, 1);

/* 直接读取 Cache 中的旧内容 */
process(buffer);
```

根因：

- DMA 直接写 RAM；
- CPU Cache 中仍保存旧数据；
- CPU 读取的是旧 Cache line。

正确实现：

```
#define CACHE_LINE_SIZE 32U

static uint8_t g_rx_buffer[512]
    __attribute__((aligned(CACHE_LINE_SIZE)));

static void cache_invalidate_for_dma(void *addr, size_t len)
{
    uintptr_t start = (uintptr_t)addr & ~(CACHE_LINE_SIZE - 1U);
    uintptr_t end = ((uintptr_t)addr + len + CACHE_LINE_SIZE - 1U)
                    & ~(CACHE_LINE_SIZE - 1U);

    SCB_InvalidateDCache_by_Addr(
        (uint32_t *)start,
        (int32_t)(end - start)
    );
}

cache_invalidate_for_dma(g_rx_buffer, sizeof(g_rx_buffer));

if (sd_read_blocks_dma(g_rx_buffer, sector, 1) != SD_OK) {
    /* 错误处理 */
}
```

工程上还应确认 Cache 维护发生在正确时序位置：

```
DMA 写内存完成
    |
Invalidate D-Cache
    |
CPU 读取数据
```

风险：

- 文件内容随机损坏；
- 校验偶发失败；
- 只在高负载或特定地址下复现，难以定位。

#### 9.5 错误五：高频小文件写入

错误代码：

```
void save_sensor_sample(const sample_t *sample)
{
    FIL file;

    f_open(&file, "0:/sample.dat", FA_OPEN_APPEND | FA_WRITE);
    f_write(&file, sample, sizeof(*sample), NULL);
    f_close(&file);
}
```

根因：

- 频繁更新目录项；
- FAT 链接更新次数过多；
- 每次都触发底层同步；
- SD 卡内部擦除和垃圾回收频繁发生。

正确实现：

```
#define LOG_BATCH_SIZE 4096U

static uint8_t g_log_batch[LOG_BATCH_SIZE];
static size_t g_log_used;

bool log_append_sample(const sample_t *sample)
{
    if (sample == NULL ||
        sizeof(*sample) > LOG_BATCH_SIZE - g_log_used) {
        return false;
    }

    memcpy(&g_log_batch[g_log_used], sample, sizeof(*sample));
    g_log_used += sizeof(*sample);

    return true;
}

FRESULT log_flush(void)
{
    FRESULT fr;
    UINT bw;
    FIL file;

    if (g_log_used == 0U) {
        return FR_OK;
    }

    fr = f_open(&file, "0:/log/current.bin",
                FA_OPEN_APPEND | FA_WRITE);
    if (fr != FR_OK) {
        return fr;
    }

    fr = f_write(&file, g_log_batch, g_log_used, &bw);

    if (fr == FR_OK && bw != g_log_used) {
        fr = FR_DISK_ERR;
    }

    if (fr == FR_OK) {
        fr = f_sync(&file);
    }

    {
        FRESULT close_fr = f_close(&file);
        if (fr == FR_OK) {
            fr = close_fr;
        }
    }

    if (fr == FR_OK) {
        g_log_used = 0U;
    }

    return fr;
}
```

风险：

- 写吞吐不足；
- 实时任务阻塞；
- 卡寿命下降；
- 文件系统碎片快速增长。

### 10. 多机制组合使用方案

### #10.1 推荐架构：生产者—消费者—后台提交

```
采集任务
  |
  | 固定长度消息 / 环形缓冲区
  v
日志队列
  |
  v
日志写入任务
  |
  +-- 批量聚合
  +-- FatFs f_write
  +-- 周期 f_sync
  +-- 文件滚动
  +-- 空间检查
  v
SD 卡
```

核心原则：

- 采集任务不直接访问 FatFs；
- 日志任务独占文件句柄；
- 使用固定内存，避免运行时频繁 malloc；
- 通过周期同步平衡可靠性和吞吐；
- 发生介质错误时立即停止消费并上报。

#### 10.2 日志记录格式

推荐二进制记录格式：

```
typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint32_t sequence;
    uint32_t timestamp_ms;
    uint16_t type;
    uint16_t payload_len;
    uint32_t payload_crc;
    uint8_t  payload[LOG_PAYLOAD_MAX];
} log_record_t;
```

注意事项：

- 使用固定端序；
- 添加版本号；
- 添加记录长度；
- 每条记录独立校验；
- 不直接保存 C 结构体中的指针；
- 对结构体布局使用静态断言。

```
_Static_assert(sizeof(log_record_t) <= 512U,
               "log record must fit within one sector");
```

#### 10.3 日志任务框架

```
static FIL g_log_file;
static bool g_log_opened;

static FRESULT log_open(void)
{
    FRESULT fr;

    if (g_log_opened) {
        return FR_OK;
    }

    fr = f_open(&g_log_file,
                "0:/log/current.bin",
                FA_OPEN_ALWAYS | FA_WRITE);

    if (fr != FR_OK) {
        return fr;
    }

    fr = f_lseek(&g_log_file, f_size(&g_log_file));
    if (fr != FR_OK) {
        (void)f_close(&g_log_file);
        return fr;
    }

    g_log_opened = true;
    return FR_OK;
}

static FRESULT log_write_batch(
    const void *buffer,
    UINT size)
{
    FRESULT fr;
    UINT bw;

    fr = log_open();
    if (fr != FR_OK) {
        return fr;
    }

    fr = f_write(&g_log_file, buffer, size, &bw);
    if (fr != FR_OK) {
        return fr;
    }

    if (bw != size) {
        return FR_DISK_ERR;
    }

    return f_sync(&g_log_file);
}

void log_task(void *argument)
{
    uint8_t batch[8192];
    UINT used = 0U;
    TickType_t last_sync = xTaskGetTickCount();

    (void)argument;

    for (;;) {
        log_item_t item;

        if (log_queue_receive(&item, pdMS_TO_TICKS(100)) == true) {
            if (item.length <= sizeof(batch) - used) {
                memcpy(&batch[used], item.data, item.length);
                used += item.length;
            }
        }

        if (used >= 4096U ||
            (xTaskGetTickCount() - last_sync) >= pdMS_TO_TICKS(1000)) {

            if (used > 0U) {
                if (log_write_batch(batch, used) != FR_OK) {
                    storage_report_error();
                } else {
                    used = 0U;
                }
            }

            last_sync = xTaskGetTickCount();
        }
    }
}
```

该架构的主要权衡：

| 参数            | 增大后的收益     | 增大后的代价          |
| ------------- | ---------- | --------------- |
| 批量缓冲区         | 吞吐提高、写放大降低 | RAM 增加、掉电丢失窗口变大 |
| `f_sync()` 周期 | 写入效率提高     | 掉电时丢失更多数据       |
| 日志文件大小        | 文件数量减少     | 单文件恢复和导出时间增加    |
| 队列深度          | 抗瞬时突发能力增强  | RAM 增加、延迟可能隐藏   |

### 11. 工业级实际案例分析

#### 11.1 案例一：工业振动数据记录器

#### 需求

- 采样率：每通道 10 kHz；
- 4 个通道；
- 每个采样点 16 bit；
- 连续记录到工业级 SD 卡；
- 不允许采集任务被文件系统长时间阻塞；
- 发生拔卡时保留 RAM 中最近一批数据。

#### 数据速率

```
10,000 × 4 × 2 B = 80,000 B/s
                     ≈ 78.1 KiB/s
```

FatFs 逻辑吞吐并不困难，真正风险是 SD 卡写入长尾延迟。

#### 架构

```
ADC DMA 双缓冲
    |
采样处理任务
    |
8~64 KiB 环形缓冲区
    |
日志写入任务
    |
SDMMC 4-bit + FatFs
```

#### 设计要点

- ADC DMA 中断只切换缓冲区；
- 采样任务不调用 FatFs；
- 每次写入 16~32 KiB；
- 每 500 ms~2 s 调用一次 `f_sync()`；
- 记录文件头包含采样率、通道数、设备序列号和时间基准；
- 文件大小达到 64~256 MiB 后滚动。

#### 风险计算

如果环形缓冲区为 64 KiB：

```
容忍卡写入阻塞时间
= 64 KiB / 78.1 KiB/s
≈ 0.82 s
```

如果现场测得 SD 卡最大写阻塞 1.5 s，则 64 KiB 不足，应至少配置：

```
1.5 × 78.1 KiB/s × 1.5 安全系数
≈ 176 KiB
```

工程上可取 256 KiB。

### 11.2 案例二：电机控制器参数和故障日志

#### 需求

- 参数文件小于 8 KiB；
- 参数更新频率低；
- 需要掉电恢复；
- 故障日志必须可导出；
- 参数损坏时自动回退到上一版本。

#### 架构

```
参数配置：
  config_a.bin
  config_b.bin
  CRC32 + sequence

故障日志：
  faults/YYYYMMDD.bin
  批量写入 + 周期同步
```

#### 参数文件结构

```
typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    uint32_t sequence;
    uint32_t payload_size;
    uint32_t payload_crc;
} config_header_t;
```

#### 启动恢复策略

```
读取 config_a.bin
  |
校验头、长度、CRC
  |
读取 config_b.bin
  |
校验头、长度、CRC
  |
选择 sequence 较大的有效文件
  |
两个都无效 -> 使用默认参数并上报故障
```

这种设计不能完全依赖文件名替换，因为 FAT 的目录项更新和介质写入不是全局事务。

### 11.3 案例三：现场升级包导入

#### 需求

- 用户通过 U 盘或 SD 卡导入固件；
- 支持大于数 MB 的镜像；
- 传输中断后不能误升级；
- 必须校验版本、长度、CRC/SHA；
- 升级失败后可回退。

#### 文件流程

```
firmware.pkg
    |
复制到 firmware.tmp
    |
边读边计算 SHA-256
    |
检查长度、签名、版本
    |
f_sync + f_close
    |
写入升级标志
    |
Bootloader 校验并升级
```

不要直接对 `firmware.pkg` 进行升级。必须先复制到临时文件，并在文件完整关闭后再设置升级请求标志。

### 12. 高频问题深度答疑

#### 问题一：为什么 `f_write()` 返回成功，掉电后文件仍损坏？

`FR_OK` 只表示 FatFs 当前层完成了请求，不必然表示存储卡内部 NAND 已经完成编程。必须正确实现：

- `f_sync()`；
- `disk_ioctl(CTRL_SYNC)`；
- DMA 完成等待；
- 卡 Busy 状态等待；
- Cache 维护。

对于关键数据，还需要文件级校验和和恢复策略。

#### 问题二：FatFs 能不能直接运行在 SPI NOR Flash 上？

可以，但不能简单把 NOR Flash 的页写接口直接映射为 `disk_write()`。

因为：

- FatFs 面向块设备；
- NOR Flash 写入通常要求先擦除；
- 擦除粒度一般为 4 KiB、32 KiB 或 64 KiB；
- 擦除前需要保存同一擦除块中的其他数据；
- 需要处理写放大和磨损。

因此必须实现块设备转换层，或者直接选择更适合 NOR Flash 的 LittleFS。

#### 问题三：为什么连续写入速度很高，但偶尔会卡几百毫秒？

SD 卡内部存在：

- NAND 擦除；
- FTL 映射更新；
- 垃圾回收；
- 坏块管理；
- 磨损均衡；
- 写缓存刷新。

这是介质内部不可完全控制的长尾延迟。解决方向：

- 使用工业级或高耐久卡；
- 批量写入；
- 预分配文件；
- 增大 RAM 环形缓冲区；
- 把严格实时任务与文件写入任务解耦；
- 设置最大阻塞监控和降级策略。

#### 问题四：是否应该每次写日志都调用 `f_sync()`？

不应该一概而论。

|数据类型|建议|
|---|---|
|普通调试日志|1~5 秒同步一次|
|重要状态变化|状态变化后立即同步|
|安全相关事件|使用独立高可靠存储或双介质|
|音频/波形数据|批量写入，周期同步|
|升级包|写完后必须同步并完整校验|

本质是权衡：

```
数据安全性 <-> 写入吞吐 <-> 掉电丢失窗口
```

#### 问题五：`FF_FS_REENTRANT` 开启后是否所有问题都解决了？

没有。它主要保护 FatFs 内部对象和卷状态，不能解决：

- 同一个 `FIL` 被多个任务同时操作；
- 底层 SPI 总线被其他设备抢占；
- 应用层文件生命周期错误；
- 拔卡时 DMA 仍在运行；
- 文件内容业务一致性；
- 上层缓存与文件内容不同步。

推荐原则：

```
一个文件句柄只归一个任务所有；
跨任务传输数据，不跨任务共享 FIL。
```

#### 问题六：什么时候应该放弃 FatFs？

以下情况应评估其他方案：

- 数据只存在 MCU 内部 NOR Flash；
- 需要严格确定的写入延迟；
- 需要高频随机更新小数据；
- 需要强掉电一致性；
- 不能接受 FAT 的写放大；
- 不需要 PC 直接读取；
- 需要每次写入都有明确事务语义。

此时可以选择：

- LittleFS；
- 原始双备份参数区；
- 环形日志；
- EEPROM 仿真；
- 数据库式 KV 存储；
- 专用 NAND Flash 文件系统。

### 13. 课程核心总结

#### 核心要点

1. FatFs 的本质是**文件系统核心 + Disk I/O 适配层**。
2. `disk_read()`、`disk_write()` 和 `disk_ioctl()` 的语义必须严格实现。
3. `CTRL_SYNC` 必须真正等待 DMA、控制器和介质完成。
4. 文件写入成功不等于物理介质已经安全提交。
5. 多任务系统中应启用重入保护，但仍需管理文件句柄和总线锁。
6. SD 卡具有显著写入长尾延迟，必须采用缓冲和生产者—消费者架构。
7. 关键配置文件应使用版本号、序列号、长度和 CRC。
8. 自动格式化不能作为所有挂载失败的默认处理。
9. 内部 NOR Flash 不应机械套用 FAT，应评估 LittleFS 或原始块存储。
10. 高吞吐和高可靠性通常依靠**批量写入、预分配、周期同步和故障恢复**共同实现。

#### 性能排序

在同一硬件平台上，通常为：

```
SDMMC DMA 连续大块写
    >
SPI SD DMA 连续大块写
    >
SDMMC 小块频繁写
    >
SPI SD 小块频繁写
    >
每条记录 open/write/close
```

#### 通用选型结论

```
需要 PC 兼容文件交换 -> FatFs
需要内部 NOR 掉电恢复 -> LittleFS
需要小数据强实时持久化 -> 原始双备份存储
需要连续高速采集 -> FatFs + 大缓冲 + DMA + 文件预分配
需要关键数据不可丢失 -> 文件系统之外增加校验、事务和冗余
```

### 14. 快速参考速查表

#### 14.1 场景选型表

|需求|推荐实现|
|---|---|
|SD 卡读取配置文件|FatFs + 启动挂载|
|SD 卡连续日志|独占日志任务 + 8~32 KiB 批量写|
|关键配置保存|临时文件 + CRC + sequence|
|固件包导入|临时文件 + SHA/签名 + 完整关闭后升级|
|内部 NOR 参数|双槽位原始块存储|
|内部 NOR 文件系统|LittleFS|
|可拔插介质|卡检测 + 事件任务 + 卸载流程|
|多任务文件访问|`FF_FS_REENTRANT` + 句柄所有权|

#### 14.2 特性对比表

|特性|FatFs|LittleFS|原始块|
|---|---|---|---|
|PC 兼容|高|低|无|
|大文件|强|中|需自行实现|
|掉电恢复|需应用增强|强|可定制|
|实时性|中低|中高|高|
|RAM 占用|低|中|低|
|工程成熟度|很高|高|取决于自研质量|
|适合 SD 卡|很适合|一般|不推荐|
|适合 NOR Flash|一般|很适合|很适合|

#### 14.3 常用 API

|API|用途|
|---|---|
|`f_mount()`|挂载/卸载卷|
|`f_open()`|打开文件|
|`f_read()`|读文件|
|`f_write()`|写文件|
|`f_sync()`|同步文件|
|`f_close()`|关闭文件|
|`f_lseek()`|定位文件指针|
|`f_stat()`|获取文件信息|
|`f_unlink()`|删除文件/目录|
|`f_rename()`|重命名|
|`f_opendir()`|打开目录|
|`f_readdir()`|读取目录项|
|`f_mkdir()`|创建目录|
|`f_mkfs()`|格式化卷|
|`f_getfree()`|获取空闲空间|

#### 14.4 常见错误码

|错误码|含义|典型原因|
|---|---|---|
|`FR_OK`|成功|操作完成|
|`FR_DISK_ERR`|底层磁盘错误|总线、供电、介质故障|
|`FR_NOT_READY`|设备未就绪|未初始化、拔卡|
|`FR_NO_FILESYSTEM`|无有效文件系统|未格式化或文件系统损坏|
|`FR_DENIED`|操作被拒绝|只读、文件属性、空间问题|
|`FR_EXIST`|文件已存在|创建目录/文件重复|
|`FR_INVALID_OBJECT`|对象无效|文件已关闭或内存破坏|
|`FR_TIMEOUT`|获取资源超时|多任务锁竞争或底层等待超时|

### 15. 学习效果自检

完成本课后，应能够回答并实现以下内容：

- [ ]  能画出 FatFs、Disk I/O、底层驱动和硬件介质之间的分层关系。
- [ ]  能独立实现五个 Disk I/O 基本接口。
- [ ]  能解释 `CTRL_SYNC` 为什么不能直接返回成功。
- [ ]  能区分 `f_write()`、`f_sync()` 和 `f_close()` 的持久化语义。
- [ ]  能处理 `FR_NO_FILESYSTEM`、`FR_DISK_ERR` 和 `FR_NOT_READY`。
- [ ]  能设计 SD 卡拔出和重新插入流程。
- [ ]  能设计多任务环境下的文件句柄所有权。
- [ ]  能解释 Cortex-M7 DMA 与 D-Cache 的一致性问题。
- [ ]  能计算采样带宽、缓冲区容量和最大可容忍写阻塞时间。
- [ ]  能实现配置文件的双版本、CRC 和启动恢复机制。
- [ ]  能说明 FatFs 与 LittleFS、原始块存储的选型边界。
- [ ]  能设计日志批量写入和滚动文件策略。
- [ ]  能完成异常掉电、拔卡、满盘和介质错误测试。

### 16. 实践与进阶路径

#### 阶段一：基础移植验证

实现以下功能：

1. SD 卡初始化；
2. `disk_status()`；
3. 单扇区读写；
4. `f_mount()`；
5. 创建目录；
6. 创建并读取文本文件；
7. 删除和重命名文件。

验收指标：

- 连续挂载 1000 次无异常；
- 读写文件内容 CRC 正确；
- 所有错误路径返回明确错误码。

#### 阶段二：性能测试

测试以下维度：

```
单扇区随机读
单扇区随机写
4 KiB 连续读写
32 KiB 连续读写
256 KiB 连续读写
不同 f_sync 周期
文件碎片化前后
不同 SD 卡型号
不同温度
```

建议记录：

```
typedef struct {
    uint32_t operation;
    uint32_t request_size;
    uint32_t elapsed_us;
    uint32_t result;
    uint32_t free_space;
} storage_perf_record_t;
```

核心指标：

- 平均吞吐；
- P95/P99 延迟；
- 最大写入延迟；
- CPU 占用；
- RAM 使用；
- 掉电后文件可恢复比例。

#### 阶段三：可靠性测试

##### 掉电测试

在以下时间点随机断电：

- `f_open()` 后；
- `f_write()` 中途；
- `f_sync()` 前；
- `f_sync()` 中途；
- `f_close()` 中途；
- 文件重命名过程中；
- 目录创建过程中。

检查：

- 是否能重新挂载；
- 是否能识别最近一个完整文件；
- 是否能恢复配置；
- 是否出现交叉链接或丢失簇；
- 是否影响其他文件。

##### 介质故障注入

模拟：

- SD 卡拔出；
- SPI CRC 错误；
- DMA 超时；
- 卡忙超时；
- 写保护；
- 满盘；
- 文件句柄耗尽；
- 总线被其他设备长期占用。

#### 阶段四：日志系统进阶

实现：

- 固定大小环形缓冲区；
- 多优先级日志；
- 高优先级故障日志抢占普通日志；
- 文件大小滚动；
- 自动删除最旧文件；
- 启动恢复未完成文件；
- 文件头和记录级 CRC；
- 日志导出状态机。

#### 阶段五：系统架构进阶

进一步研究：

- SDMMC 多块读写命令；
- DMA 描述符和总线吞吐；
- Cortex-M Cache 一致性；
- FAT 目录和簇链结构；
- 文件预分配策略；
- FATFS 与 LittleFS 的可靠性对比；
- eMMC、UFS 和 USB MSC 设备模型；
- 加密文件、签名升级包和安全擦除；
- 断电保护电容和存储器电源时序。

#### 最终工程任务

设计一个完整的工业数据记录模块，至少包含：

```
存储器检测
文件系统挂载
自动目录创建
日志批量写入
周期同步
文件滚动
空间阈值监控
拔卡处理
满盘处理
掉电恢复
数据 CRC
性能统计
错误事件上报
```

最终验收目标：

- 连续运行 30 天；
- 累计写入不少于 100 GB；
- 随机掉电测试不少于 10,000 次；
- 随机拔卡测试不少于 1,000 次；
- P99 写入延迟满足系统实时性预算；
- 无不可恢复文件系统损坏；
- 关键配置文件恢复成功率达到 **100%** 。
