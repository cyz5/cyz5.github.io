
## 1. 学习目标

### 理解

- 理解 SPI 的四线模型：`SCK`、`MOSI`、`MISO`、`CS/NSS`。
- 理解 CPOL、CPHA、SPI Mode 0~3 的采样与更新边沿。
- 理解 SPI 主机时钟生成、从机时钟同步、片选边界和帧长度。
- 理解全双工移位寄存器、发送缓冲区、接收缓冲区和状态标志之间的关系。

### 掌握

- 掌握 SPI 主机轮询、中断、DMA 三种驱动架构。
- 掌握不同外设的片选控制、命令阶段、地址阶段、数据阶段组织方式。
- 掌握超时、总线异常、设备无响应、DMA 竞争和总线恢复处理。
- 掌握 SPI 从机在外部时钟驱动下的实时性约束。

### 精通

- 能够分析 CPHA 配置错误、片选时序错误、读写错位和数据一致性问题。
- 能够通过逻辑分析仪定位采样边沿、字长、频率和 CS 时序问题。
- 能够量化轮询、中断、DMA 方案的 CPU 占用、吞吐率和延迟。
- 能够设计支持多设备、多速率、多协议帧格式的 SPI 总线抽象层。

### 能够设计

- 设计工业级 SPI 主设备驱动。
- 设计受限于外部时钟和严格响应窗口的 SPI 从设备驱动。
- 设计 SPI 与 RTOS、DMA、缓存一致性和电源管理的协同架构。
- 设计具备错误检测、总线恢复和可测试性的 SPI 设备访问框架。

---

## 2. 前置要求

### 知识要求

- C 语言指针、结构体、枚举、位操作和 `volatile`。
- MCU 时钟树、GPIO 复用、寄存器读写和中断机制。
- 中断上下文与线程上下文的区别。
- 基本数字电路知识：建立时间、保持时间、上升沿、下降沿。
- RTOS 任务、互斥锁、信号量和队列。
- DMA 基本工作模式及内存地址递增配置。

### 技能要求

- 能阅读 MCU Reference Manual 中的 SPI 章节。
- 能使用示波器或逻辑分析仪观察数字波形。
- 能配置 GPIO 复用、外设时钟和中断向量。
- 能编写带错误处理和超时机制的底层驱动。
- 能使用单元测试或硬件在环测试验证驱动行为。

---

## 3. 技术概述

SPI 是一种**同步、全双工、面向帧传输的串行总线**。传统 SPI 没有统一的寻址、应答、错误检测和仲裁协议，因此这些功能通常由上层驱动自行定义。

### 3.1 基本信号

|信号|主机方向|从机方向|作用|
|---|---|---|---|
|`SCK`|输出|输入|主机提供串行时钟|
|`MOSI`|输出|输入|主机到从机|
|`MISO`|输入|输出|从机到主机|
|`CS/NSS`|输出|输入|片选和帧边界|

部分 MCU 使用：

- `SDI/SDO`
- `COPI/CIPO`
- `SCLK`
- `SS`

其中 `COPI` 和 `CIPO` 比 `MOSI/MISO` 更能避免主从视角歧义。

### 3.2 主从关系

SPI 通常采用一个主机、一个或多个从机：

```
MCU Master
  |
  +-- SCK --------------------> Device A
  +-- MOSI -------------------> Device A
  +-- MISO <------------------- Device A
  +-- CS_A -------------------> Device A
  |
  +-- CS_B -------------------> Device B
```

多个从机通常共享 `SCK/MOSI/MISO`，每个设备单独使用一个 `CS`。

### 3.3 SPI Mode

SPI 模式由 `CPOL` 和 `CPHA` 确定：

|Mode|CPOL|CPHA|空闲电平|第一个有效边沿|
|---|---|---|---|---|
|Mode 0|0|0|低|上升沿采样|
|Mode 1|0|1|低|下降沿采样|
|Mode 2|1|0|高|下降沿采样|
|Mode 3|1|1|高|上升沿采样|

需要注意：不同芯片数据手册对“采样边沿”和“数据变化边沿”的文字描述可能不同，不能只看 Mode 编号，必须结合时序图确认。

### 3.4 SPI 的主要实现方式

1. **GPIO 模拟 SPI**
    
    - 通过软件控制 GPIO。
    - 时序可控，兼容性高。
    - CPU 占用高，速度和实时性受限。
2. **硬件 SPI 轮询**
    
    - CPU 直接等待发送和接收标志。
    - 实现简单，延迟可预测。
    - 长数据传输期间会阻塞 CPU。
3. **硬件 SPI 中断**
    
    - 通过 TXE、RXNE、错误中断驱动状态机。
    - CPU 占用低于轮询。
    - 中断频率高时会产生明显调度开销。
4. **硬件 SPI DMA**
    
    - DMA 自动搬运数据。
    - 适合大块数据和连续流。
    - 需要处理缓存一致性、DMA 生命周期和事务完成同步。

---

## 4. 核心特性横向对比

|维度|GPIO 模拟|硬件轮询|硬件中断|硬件 DMA|
|---|---|---|---|---|
|最大速率|通常 < 5 MHz|取决于外设|取决于外设|取决于外设|
|CPU 占用|极高|高|中|低|
|单字节延迟|高|低|中|较高启动延迟|
|长帧吞吐|低|中|中|高|
|时序可定制性|很高|低|低|低|
|实现复杂度|中|低|中|高|
|适合短命令|是|是|是|否|
|适合大数据|否|一般|一般|是|
|调试难度|中|低|中|高|
|典型风险|中断扰动时序|CPU 长时间阻塞|状态机错误|缓存、竞态、资源释放|

工程上通常采用：

```
短控制命令       -> 轮询
中等长度异步事务 -> 中断
大块连续数据     -> DMA
极端定制时序     -> GPIO 模拟
```

---

## 5. 底层原理与功能特性深度解析

### 5.1 全双工移位原理

SPI 没有独立的“读操作”和“写操作”。每输出一个 bit，主机同时输入一个 bit：

```
主机发送寄存器: 1010 0101
从机返回数据:   1100 0011
时钟边沿:       8 个
```

因此，主机读取从机数据时必须发送填充值，常用 `0xFF` 或 `0x00`：

```
static int spi_transfer_byte(const spi_bus_t *bus,
                             uint8_t tx,
                             uint8_t *rx,
                             uint32_t timeout_us)
{
    uint32_t start = board_time_us();

    spi_hw_write_dr(bus->instance, tx);

    while (!spi_hw_rx_ready(bus->instance)) {
        if ((board_time_us() - start) >= timeout_us) {
            return -ETIMEDOUT;
        }
    }

    uint8_t value = spi_hw_read_dr(bus->instance);

    if (rx != NULL) {
        *rx = value;
    }

    return 0;
}
```

实际 MCU 可能要求：

1. 等待发送缓冲区空。
2. 写入发送寄存器。
3. 等待接收缓冲区非空。
4. 读取接收寄存器。
5. 检查溢出、模式错误、帧错误等状态。

不能只等待发送完成而不读取接收寄存器，否则可能出现 `OVR` 溢出。

### 5.2 事务边界与片选

一个 SPI 事务通常包括：

```
CS 拉低
  命令
  地址
  Dummy
  数据
CS 拉高
```

很多器件把 `CS` 的上升沿作为命令结束标志。例如 NOR Flash：

```
CS_LOW
  0x03              // Read command
  address[23:16]
  address[15:8]
  address[7:0]
  dummy clocks
  data...
CS_HIGH
```

生产级代码应将 CS 纳入事务生命周期：

```
typedef struct {
    spi_instance_t instance;
    gpio_pin_t cs;
    uint32_t hz;
    spi_mode_t mode;
    spi_word_size_t word_size;
    bool cs_active_low;
} spi_device_t;

static int spi_device_begin(const spi_device_t *dev)
{
    int rc = spi_hw_config(dev->instance,
                           dev->hz,
                           dev->mode,
                           dev->word_size);
    if (rc != 0) {
        return rc;
    }

    gpio_write(dev->cs, dev->cs_active_low ? 0 : 1);
    return 0;
}

static void spi_device_select(const spi_device_t *dev)
{
    gpio_write(dev->cs, dev->cs_active_low ? 1 : 0);
}

static void spi_device_deselect(const spi_device_t *dev)
{
    gpio_write(dev->cs, dev->cs_active_low ? 0 : 1);
}
```

上例中的 `spi_device_begin()` 仅用于配置，实际项目应明确 GPIO 有效电平命名，避免 `cs_active_low` 逻辑造成误用。更推荐：

```
typedef enum {
    GPIO_LEVEL_INACTIVE = 0,
    GPIO_LEVEL_ACTIVE = 1
} gpio_active_level_t;

typedef struct {
    gpio_pin_t pin;
    gpio_active_level_t active_level;
} chip_select_t;
```

### 5.3 SPI 主机轮询驱动框架

```
typedef struct {
    spi_instance_t instance;
    mutex_t lock;
    bool initialized;
} spi_bus_t;

int spi_bus_transfer(spi_bus_t *bus,
                     const spi_device_t *dev,
                     const uint8_t *tx,
                     uint8_t *rx,
                     size_t length,
                     uint32_t timeout_us)
{
    if (bus == NULL || dev == NULL || length == 0U) {
        return -EINVAL;
    }

    if (tx == NULL && rx == NULL) {
        return -EINVAL;
    }

    if (!bus->initialized) {
        return -ENODEV;
    }

    if (mutex_lock_timeout(&bus->lock, timeout_us) != 0) {
        return -EBUSY;
    }

    int rc = spi_hw_config(bus->instance,
                           dev->hz,
                           dev->mode,
                           dev->word_size);
    if (rc != 0) {
        mutex_unlock(&bus->lock);
        return rc;
    }

    spi_device_select(dev);

    for (size_t i = 0; i < length; ++i) {
        uint8_t tx_byte = tx != NULL ? tx[i] : 0xFFU;
        uint8_t rx_byte = 0U;

        rc = spi_transfer_byte(bus,
                               tx_byte,
                               &rx_byte,
                               timeout_us);
        if (rc != 0) {
            spi_hw_abort(bus->instance);
            spi_device_deselect(dev);
            mutex_unlock(&bus->lock);
            return rc;
        }

        if (rx != NULL) {
            rx[i] = rx_byte;
        }
    }

    spi_device_deselect(dev);
    mutex_unlock(&bus->lock);

    return 0;
}
```

关键设计点：

- **总线锁必须覆盖完整事务**，不能只锁单个字节。
- `CS` 拉低到拉高期间，不能被其他设备插入访问。
- 失败时必须执行 `spi_hw_abort()` 和 `CS` 释放。
- 所有等待都必须有超时。
- `tx == NULL` 时发送 dummy；`rx == NULL` 时丢弃接收数据。

### 5.4 主机与从机的核心差异

主机：

- 生成 `SCK`。
- 决定传输何时开始。
- 可控制 CS。
- 可通过降低时钟规避从机响应能力不足。

从机：

- 不生成时钟。
- 不能主动开始传输。
- 必须在外部时钟到来前准备好发送数据。
- 片选通常决定状态机复位和帧起止。
- 对中断延迟、DMA 配置时机和硬件 FIFO 深度更加敏感。

### 5.5 SPI 从机驱动

从机不能用“等待发送开始”的普通线程逻辑，因为外部主机可能随时拉低 CS 并开始输出时钟。

典型流程：

```
CS 下降沿
  -> 清空上一帧状态
  -> 准备首字节
  -> 等待 SCK
  -> 收到命令
  -> 解析长度和地址
  -> 准备响应
CS 上升沿
  -> 结束本帧
  -> 校验并提交数据
```

从机中断框架：

```
typedef struct {
    uint8_t rx_buf[256];
    uint8_t tx_buf[256];
    size_t rx_len;
    size_t tx_len;
    size_t tx_pos;
    bool frame_active;
    bool frame_error;
} spi_slave_context_t;

void spi_slave_cs_falling_isr(spi_slave_context_t *ctx)
{
    ctx->rx_len = 0U;
    ctx->tx_len = 0U;
    ctx->tx_pos = 0U;
    ctx->frame_active = true;
    ctx->frame_error = false;

    spi_hw_clear_status();
    spi_hw_write_dr(0xFFU);
}

void spi_slave_rx_isr(spi_slave_context_t *ctx)
{
    uint8_t value = spi_hw_read_dr();

    if (!ctx->frame_active) {
        return;
    }

    if (ctx->rx_len >= sizeof(ctx->rx_buf)) {
        ctx->frame_error = true;
        return;
    }

    ctx->rx_buf[ctx->rx_len++] = value;

    uint8_t response = spi_slave_next_response(ctx);
    spi_hw_write_dr(response);
}

void spi_slave_cs_rising_isr(spi_slave_context_t *ctx)
{
    ctx->frame_active = false;

    if (!ctx->frame_error) {
        spi_slave_submit_frame(ctx->rx_buf, ctx->rx_len);
    }
}
```

该代码展示状态机结构，实际实现必须根据 MCU 手册确认：

- CS 是否由硬件 NSS 管理。
- RXNE 和 TXE 的触发顺序。
- 首字节预装载时机。
- 是否存在发送 underrun。
- 读写状态寄存器的清除顺序。

---

## 6. 性能量化分析

### 6.1 理论吞吐率

SPI 原始线速：

Rbit=fSCKRbit​=fSCK​

8 bit 数据字长下的理论字节速率：

Rbyte=fSCK8Rbyte​=8fSCK​​

例如：

```
SCK = 20 MHz
理论吞吐 = 20,000,000 / 8 = 2.5 MB/s
```

如果每次事务包含 4 字节命令和地址，实际有效载荷为 `N` 字节，则：

η=NN+4η=N+4N​

当 `N = 16` 时：

η=1620=80%η=2016​=80%

若 CS 拉低、配置和任务切换额外消耗时间，则实际效率还会进一步下降。

### 6.2 参考实测数据

测试平台：

```
MCU: Cortex-M4 @ 168 MHz
SPI: 20 MHz
编译器: GCC -O2
总线: 单设备、8 bit、Mode 0
测试长度: 4 KB
```

|方式|CPU 占用|单次启动延迟|4 KB 传输时间|备注|
|---|---|---|---|---|
|轮询|约 18%|1~3 us|约 1.65 ms|接近线速|
|中断|约 7%|4~8 us|约 1.70 ms|每字节中断|
|DMA|< 1%|8~20 us|约 1.67 ms|适合长帧|

计算依据：

Twire=4096×820MHz≈1.638msTwire​=20MHz4096×8​≈1.638ms

以上数据是典型参考值，不同 MCU 的 FIFO 深度、DMA 仲裁、缓存策略和驱动实现会导致明显差异。工程验收必须以目标板实测为准。

### 6.3 瓶颈

主要瓶颈包括：

- SPI 外设最高时钟限制。
- 从机最大输入时钟。
- GPIO 上升下降时间。
- PCB 走线和串扰。
- CPU 轮询等待。
- 中断响应延迟。
- DMA 启动开销。
- RTOS 锁竞争。
- Flash 等待时间。
- Cache 与 DMA 不一致。

### 6.4 优化收益

- 连续传输减少 CS 翻转和事务初始化，短帧延迟可降低 **20%~60%** 。
- DMA 适用于大于约 **32~64 字节** 的连续数据块。
- 使用硬件 FIFO 可减少中断次数。
- 将设备配置缓存到驱动对象中，可避免每字节重复配置。
- 对 Cortex-M7 等带 D-Cache 的 MCU，正确执行 Clean/Invalidate 可避免大量随机数据错误。

DMA 缓存处理示例：

```
int spi_dma_txrx(uint8_t *tx, uint8_t *rx, size_t length)
{
    if (!is_aligned(tx, CACHE_LINE_SIZE) ||
        !is_aligned(rx, CACHE_LINE_SIZE)) {
        return -EINVAL;
    }

    dcache_clean(tx, length);
    dcache_invalidate(rx, length);

    dma_start(tx, rx, length);

    if (semaphore_take_timeout(&spi_done, SPI_TIMEOUT_MS) != 0) {
        dma_abort();
        return -ETIMEDOUT;
    }

    dcache_invalidate(rx, length);
    return 0;
}
```

实际项目中，缓存操作的地址和长度通常要按 Cache line 向下、向上对齐，不能简单使用原始缓冲区范围。

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否需要 SPI？
  |
  +-- 否 -> 使用 I2C、UART、CAN、并行总线等
  |
  +-- 是
       |
       +-- 数据量是否小于 16~32 字节？
       |      |
       |      +-- 是 -> 轮询
       |      +-- 否
       |
       +-- 是否要求异步执行？
       |      |
       |      +-- 否 -> 轮询
       |      +-- 是
       |
       +-- 是否是连续大块数据？
              |
              +-- 是 -> DMA
              +-- 否 -> 中断
```

### 7.2 典型场景

|场景|需求|推荐方案|理由|
|---|---|---|---|
|温度传感器寄存器|几字节读写|轮询|代码简单，延迟低|
|SPI NOR Flash|页编程、连续读取|DMA + 轮询命令|数据阶段吞吐要求高|
|LCD/OLED|大量像素数据|DMA|降低 CPU 占用|
|ADC 高速采样|连续稳定数据流|DMA 环形缓冲|需要持续接收|
|外部 FPGA 从机|固定帧协议|中断或 DMA 从机|需要处理外部时钟|
|无硬件 SPI 的低速设备|特殊边沿、低速|GPIO 模拟|时序可完全控制|
|多设备共享 SPI|设备速率不同|事务队列 + 总线锁|保证配置和 CS 原子性|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **总线层与设备层分离**
    
    - 总线层负责时钟、模式、传输、DMA。
    - 设备层负责命令、地址、寄存器和协议状态。
2. **每个设备独立保存配置**
    
    - SPI Mode。
    - 最大时钟。
    - 字长。
    - CS 引脚。
    - 片选建立和释放延迟。
3. **完整事务加锁**
    
    - 锁范围必须覆盖 CS 拉低到 CS 拉高。
    - 禁止其他线程在中间改变 SPI 模式。
4. **所有硬件等待必须有超时**
    
    - TXE。
    - RXNE。
    - BSY 清除。
    - DMA 完成。
    - 设备 Busy 释放。
5. **错误路径必须释放资源**
    
    - 释放 CS。
    - 停止 DMA。
    - 清除状态标志。
    - 释放互斥锁。
    - 恢复总线状态。

### 8.2 选型决策矩阵

|条件|轮询|中断|DMA|
|---|---|---|---|
|数据少于 8 字节|优先|不推荐|不推荐|
|数据 8~64 字节|可选|优先|视平台|
|数据大于 64 字节|不推荐|可选|优先|
|CPU 负载敏感|否|可|优先|
|极低延迟敏感|优先|可|需评估启动延迟|
|需要后台异步|否|优先|优先|
|需要从机连续响应|受限|可|通常优先|

### 8.3 编码规范

- 使用 `size_t` 表示缓冲区长度。
- 使用固定宽度类型表示协议字段。
- 不在 ISR 中执行阻塞操作。
- 不在 ISR 中调用不可重入的日志函数。
- 对外部输入的长度、地址和状态进行边界检查。
- 不用裸 `0x01` 表示 CS 有效电平，使用具名宏或枚举。
- 不假设 `uint8_t` 缓冲区可以直接作为 DMA 缓冲区，确认对齐和 Cache 约束。
- 将 SPI 错误映射为统一错误码，例如 `-ETIMEDOUT`、`-EIO`、`-EINVAL`。

---

## 9. 常见错误与避坑指南

### 9.1 CPOL/CPHA 配置错误

错误代码：

```
spi_init(10U * 1000U * 1000U, SPI_MODE_0);
```

但设备数据手册要求 Mode 3。

根因：

- 只参考了其他项目配置。
- 将 CPOL 和 CPHA 的含义混淆。
- 没有观察第一位数据的采样边沿。

正确实现：

```
spi_config_t cfg = {
    .clock_hz = 10000000U,
    .mode = SPI_MODE_3,
    .bit_order = SPI_MSB_FIRST,
    .word_size = 8U
};

spi_configure(&cfg);
```

风险：

- 每个字节 bit 错位。
- 读回数据全部异常。
- 某些设备在低速下“偶尔可用”，高速下完全失败。

### 9.2 CS 在事务中间被释放

错误代码：

```
cs_low();
spi_write(command, 1);
cs_high();

cs_low();
spi_write(address, 3);
cs_high();
```

根因：

- 将命令、地址和数据分别抽象为独立操作。
- 忽略设备将 CS 上升沿作为帧结束。

正确实现：

```
cs_low();

spi_write(command, 1);
spi_write(address, 3);
spi_read(data, length);

cs_high();
```

风险：

- Flash、ADC、显示控制器将后续字节解释为新命令。
- 状态机复位，导致读写失败。

### 9.3 只发送不读取接收寄存器

错误代码：

```
spi_hw_write_dr(value);

while (!spi_hw_tx_empty()) {
}
```

根因：

- 误以为 SPI 是单向发送外设。
- 忽略发送同时产生接收数据。

正确实现：

```
spi_hw_write_dr(value);

while (!spi_hw_rx_ready()) {
    if (timeout_expired()) {
        return -ETIMEDOUT;
    }
}

(void)spi_hw_read_dr();
```

风险：

- RX 溢出。
- 后续事务读取到旧数据。
- SPI 状态机停止或触发错误中断。

### 9.4 无超时等待硬件标志

错误代码：

```
while (!spi_hw_rx_ready()) {
}
```

根因：

- 假设硬件一定会完成。
- 没有考虑外设时钟关闭、DMA 配置错误或总线异常。

正确实现：

```
uint32_t deadline = board_time_us() + timeout_us;

while (!spi_hw_rx_ready()) {
    if (time_after_eq(board_time_us(), deadline)) {
        spi_hw_abort();
        return -ETIMEDOUT;
    }
}
```

风险：

- 任务永久阻塞。
- 看门狗复位。
- 故障设备拖垮整个系统。

### 9.5 多线程并发访问 SPI

错误代码：

```
task_a: cs_a_low();
task_a: spi_transfer(...);

task_b: cs_b_low();
task_b: spi_transfer(...);
```

根因：

- 只保护了设备对象，没有保护共享 SPI 控制器。
- SPI 模式和时钟配置可能被其他线程修改。

正确实现：

```
mutex_lock(&spi_bus_lock);

spi_configure(&device_cfg);
cs_low();
spi_transfer(tx, rx, length);
cs_high();

mutex_unlock(&spi_bus_lock);
```

风险：

- 数据交叉。
- 设备 A 收到设备 B 的命令。
- 模式配置被覆盖。

### 9.6 DMA 与 Cache 不一致

错误代码：

```
memcpy(tx_buf, data, length);
dma_start(tx_buf, rx_buf, length);
```

根因：

- CPU 修改的数据仍停留在 D-Cache。
- DMA 直接访问 SRAM，读取到旧数据。

正确实现：

```
dcache_clean_by_addr(tx_buf, length);
dcache_invalidate_by_addr(rx_buf, length);
dma_start(tx_buf, rx_buf, length);
```

风险：

- 数据偶发错误。
- Debug 版本正常、Release 版本失败。
- 低频率复现，难以定位。

---

## 10. 多机制组合使用方案

### 10.1 推荐架构

```
应用任务
   |
设备驱动层
   |  命令、寄存器、协议帧
SPI 事务层
   |  队列、总线锁、CS、超时
SPI HAL
   |  轮询 / 中断 / DMA
MCU SPI 外设
   |
GPIO / DMA / NVIC
```

### 10.2 事务描述

```
typedef struct {
    const uint8_t *tx;
    uint8_t *rx;
    size_t length;
    uint32_t timeout_ms;
    bool keep_cs;
} spi_segment_t;

typedef struct {
    spi_device_t *device;
    const spi_segment_t *segments;
    size_t segment_count;
} spi_transaction_t;
```

### 10.3 组合事务框架

```
int spi_submit_transaction(spi_bus_t *bus,
                           const spi_transaction_t *transaction)
{
    if (bus == NULL || transaction == NULL ||
        transaction->device == NULL ||
        transaction->segments == NULL ||
        transaction->segment_count == 0U) {
        return -EINVAL;
    }

    mutex_lock(&bus->lock);

    int rc = spi_hw_config(bus->instance,
                           transaction->device->hz,
                           transaction->device->mode,
                           transaction->device->word_size);
    if (rc != 0) {
        mutex_unlock(&bus->lock);
        return rc;
    }

    spi_device_select(transaction->device);

    for (size_t i = 0; i < transaction->segment_count; ++i) {
        const spi_segment_t *segment = &transaction->segments[i];

        if (segment->length == 0U) {
            rc = -EINVAL;
            break;
        }

        if (segment->length >= SPI_DMA_THRESHOLD) {
            rc = spi_dma_transfer(segment->tx,
                                  segment->rx,
                                  segment->length,
                                  segment->timeout_ms);
        } else {
            rc = spi_polling_transfer(segment->tx,
                                      segment->rx,
                                      segment->length,
                                      segment->timeout_ms);
        }

        if (rc != 0 || !segment->keep_cs) {
            break;
        }
    }

    spi_device_deselect(transaction->device);
    spi_hw_clear_errors();
    mutex_unlock(&bus->lock);

    return rc;
}
```

这里的 `keep_cs` 允许将命令、地址、数据拆成多个逻辑段，同时保持一个完整的物理帧。

### 10.4 RTOS 注意事项

- 总线锁使用互斥锁，不使用普通二值信号量替代资源所有权。
- DMA 完成中断只负责清状态和释放同步信号。
- 不能在 DMA ISR 中执行设备协议解析。
- 设备驱动可使用工作队列处理复杂协议。
- 高优先级任务访问 SPI 时，应评估低优先级任务持锁造成的优先级反转。
- 对长期 DMA 传输，可增加取消接口和系统休眠禁止策略。

---

## 11. 工业级实际案例分析

### 11.1 案例一：SPI NOR Flash 固件存储

#### 需求

- 读取固件镜像。
- 单次读取长度可达 64 KB。
- 读取期间 CPU 需要运行通信任务。
- 支持超时和设备 Busy 检查。

#### 架构

```
Flash Driver
  |
  +-- Read Status: 轮询
  +-- Write Enable: 轮询
  +-- Page Program: DMA
  +-- Fast Read: DMA
  +-- Erase: 命令轮询 + Busy 超时
```

#### 核心代码

```
int nor_flash_read(uint32_t address, uint8_t *data, size_t length)
{
    if (data == NULL || length == 0U) {
        return -EINVAL;
    }

    uint8_t header[4] = {
        0x0BU,
        (uint8_t)(address >> 16),
        (uint8_t)(address >> 8),
        (uint8_t)address
    };

    spi_segment_t segments[] = {
        {
            .tx = header,
            .rx = NULL,
            .length = sizeof(header),
            .timeout_ms = 10U,
            .keep_cs = true
        },
        {
            .tx = NULL,
            .rx = data,
            .length = length,
            .timeout_ms = 1000U,
            .keep_cs = false
        }
    };

    spi_transaction_t transaction = {
        .device = &flash_device,
        .segments = segments,
        .segment_count = 2U
    };

    return spi_submit_transaction(&flash_bus, &transaction);
}
```

#### 设计要点

- 读取命令的 Dummy 字节不能遗漏。
- 页编程不能跨越 Page Boundary。
- 擦除操作不能只用 SPI 传输完成作为完成标志，必须轮询状态寄存器。
- 需要检查地址范围，防止整数溢出。

### 11.2 案例二：SPI ADC 高速采样

#### 需求

- 外部 ADC 通过 DRDY 信号通知数据就绪。
- 每次采样 3 字节。
- 采样率 100 kSPS。
- CPU 不应逐样本处理。

#### 架构

```
ADC DRDY GPIO 中断
   -> 启动 SPI DMA
   -> DMA 完成 ISR
   -> 环形缓冲区提交
   -> 高优先级数据处理任务
```

#### 设计要点

- DRDY 到 SPI 时钟启动之间必须满足 ADC 时序约束。
- DMA 缓冲区采用双缓冲或环形缓冲。
- 溢出时必须有计数器，而不是静默覆盖。
- 时间戳应在 DRDY 中断或硬件定时器中产生。
- 若 SPI 时钟速率不足，应通过公式验证：

fSCK≥fsample×bitsper sample×marginfSCK​≥fsample​×bitsper sample​×margin

例如：

```
100 kSPS × 24 bit × 1.25 = 3 MHz
```

至少应选择 3 MHz，并考虑帧间隙和启动延迟。

### 11.3 案例三：MCU 作为 SPI 从机连接 FPGA

#### 需求

- FPGA 作为主机。
- MCU 作为从机响应寄存器访问。
- FPGA 可能在任意时间拉低 CS。
- MCU 必须在首个响应字节时限内准备数据。

#### 架构

```
CS 边沿中断
  -> 复位从机帧状态
  -> 预装载 TX FIFO
SCK 到来
  -> SPI 硬件移位
  -> DMA 搬运 RX/TX 缓冲
CS 上升沿
  -> 完成本帧校验
  -> 提交寄存器写入
```

#### 设计要点

- 从机首字节必须提前写入发送寄存器或 FIFO。
- 不能依赖任务调度后再准备首字节。
- FPGA 协议应包含长度字段、序号和 CRC。
- CS 拉低时间超限时应丢弃当前帧。
- 需要明确 FPGA 是否允许跨 CS 连续帧。
- 若从机无法及时准备数据，应通过 READY GPIO 或协议握手降低时序压力。

---

## 12. 高频问题深度答疑

### 问题一：SPI 为什么没有统一的读写方向？

SPI 的本质是移位寄存器交换。主机输出时钟后，双方同时移位。因此“读”只是主机发送 dummy 数据并采集 MISO；“写”也会产生无效接收数据。

这使 SPI 获得了高吞吐率和低协议开销，但也意味着必须处理接收寄存器，不能只关注发送路径。

### 问题二：Mode 0 和 Mode 3 的实际差异是什么？

核心差异是空闲时钟电平：

- Mode 0：SCK 空闲低，第一个上升沿采样。
- Mode 3：SCK 空闲高，第一个上升沿采样。

很多设备同时支持 Mode 0 和 Mode 3，但不能假设它们完全等价。设备手册可能对 CS 建立时间、首位输出时刻和切换边沿有额外约束。

### 问题三：为什么 SPI 速率越高越容易出错？

高速下，单 bit 时间缩短：

Tbit=1fSCKTbit​=fSCK​1​

当信号传播延迟、GPIO 边沿时间、从机建立保持时间和输入滤波时间接近 `Tbit` 时，采样窗口缩小。问题可能表现为：

- 某些 bit 随机翻转。
- 温度变化后出错。
- 只有特定板卡出错。
- 逻辑分析仪正常，但真实器件异常。

需要同时检查信号完整性和采样时序，不能只降低软件重试次数。

### 问题四：SPI 是否需要上拉电阻？

通常 SCK、MOSI、CS 由主机主动驱动，不一定需要上拉。但 CS 在 MCU 复位、GPIO 高阻或启动阶段可能悬空，从机可能误认为被选中，因此常在 CS 上配置上拉。

MISO 由从机驱动，未选中时必须高阻。如果某个从机没有正确释放 MISO，多设备共享总线会发生电气冲突。

### 问题五：为什么从机比主机更难实现？

主机拥有时钟控制权，可以在任何时刻等待设备准备完成；从机不能控制外部时钟，必须在主机产生下一个采样边沿前准备好数据。

因此从机设计必须关注：

- 首字节预装载。
- FIFO 深度。
- ISR 最坏响应时间。
- DMA 启动时机。
- CS 异步边沿。
- 外部主机超时行为。

### 问题六：轮询、中断、DMA 的分界点如何确定？

不能只按字节数固定选择。需要测量：

Ttotal=Tsetup+Ttransfer+Tsync+TcleanupTtotal​=Tsetup​+Ttransfer​+Tsync​+Tcleanup​

当 `T_setup` 占比很高时，DMA 不一定比轮询快。通常：

- 超短事务关注端到端延迟，轮询更合适。
- 中等事务关注 CPU 和响应平衡，中断更合适。
- 大块事务关注吞吐和 CPU 释放，DMA 更合适。

阈值应通过目标平台基准测试确定，而不是照搬其他 MCU 的数值。

---

## 13. 课程核心总结

### 核心要点

- SPI 是同步全双工移位总线。
- 每次发送必然伴随接收，每次接收也必须发送 dummy。
- CPOL/CPHA 必须依据设备时序图配置。
- CS 不只是电平信号，通常还是协议帧边界。
- 多设备共享 SPI 时，必须将配置、CS 和数据传输作为一个原子事务。
- 主机重点是吞吐、设备切换和总线互斥。
- 从机重点是响应延迟、首字节准备和外部时钟约束。
- DMA 不是自动变快，而是减少 CPU 参与。

### 性能排序

以 CPU 占用和大块吞吐综合排序：

```
DMA > 中断 > 轮询 > GPIO 模拟
```

以短事务端到端延迟排序：

```
轮询 > 中断 > DMA
```

### 通用选型结论

```
短命令、低延迟 -> 轮询
异步中等帧     -> 中断
大块连续数据   -> DMA
特殊时序       -> GPIO 模拟
严格从机响应   -> 硬件 FIFO + DMA/高优先级 ISR
```

---

## 14. 快速参考速查表

### 场景选型表

|场景|推荐实现|
|---|---|
|传感器寄存器读写|轮询|
|NOR Flash 连续读取|DMA|
|LCD 像素刷新|DMA|
|ADC 连续采样|DMA 环形缓冲|
|FPGA 访问 MCU 从机寄存器|从机 DMA 或高优先级中断|
|无硬件 SPI|GPIO 模拟|
|多设备共享 SPI|总线锁 + 独立 CS + 设备配置缓存|

### 特性对比表

|特性|Mode 0|Mode 1|Mode 2|Mode 3|
|---|---|---|---|---|
|CPOL|0|0|1|1|
|CPHA|0|1|0|1|
|SCK 空闲|低|低|高|高|
|常见用途|传感器、Flash|部分 ADC|少见|显示器、传感器|

### 驱动检查表

```
[ ] SPI 外设时钟已打开
[ ] GPIO 复用和电气属性正确
[ ] CPOL/CPHA 与数据手册一致
[ ] MSB/LSB 顺序正确
[ ] 字长正确
[ ] CS 空闲电平正确
[ ] CS 建立、保持、释放时间满足要求
[ ] TX 和 RX 状态都已处理
[ ] 所有等待都有超时
[ ] DMA 缓存一致性已处理
[ ] 错误路径释放 CS、DMA 和锁
[ ] 已使用逻辑分析仪验证波形
```

---

## 15. 学习效果自检

完成本课后，应能够回答并实现：

- 能否根据时序图确定 SPI Mode？
- 能否解释一次 8 bit 传输中 MOSI 和 MISO 的同步关系？
- 能否写出带超时的单字节全双工传输函数？
- 能否保证多个线程访问同一 SPI 总线时事务不交叉？
- 能否解释为什么 CS 必须覆盖命令、地址和数据完整阶段？
- 能否设计一个支持轮询、中断和 DMA 的统一传输接口？
- 能否识别从机首字节响应不及时的根因？
- 能否计算给定采样率和数据字长所需的最低 SPI 时钟？
- 能否定位 DMA 缓存不一致导致的偶发数据错误？
- 能否使用逻辑分析仪确认频率、模式、字长和帧边界？

---

## 16. 实践与进阶路径

### 阶段一：主机轮询

实现一个 SPI 主机驱动，要求：

- 支持 Mode 0~3。
- 支持 8 bit 和 16 bit 字长。
- 支持独立 CS。
- 支持传输超时。
- 支持 TX-only、RX-only、全双工。

测试内容：

```
1. 回环测试：MOSI 与 MISO 短接
2. 0x00、0xFF、0xAA、0x55 模式测试
3. 不同 SPI Mode 对比
4. 不同 SCK 频率下误码率测试
```

### 阶段二：SPI NOR Flash

实现：

- JEDEC ID 读取。
- 状态寄存器读取。
- 页编程。
- 扇区擦除。
- 连续读取。
- Busy 超时。
- 地址范围检查。
- 页边界自动拆分。

验证：

```
写入 -> 读取 -> CRC 校验 -> 擦除 -> 再读取确认
```

### 阶段三：中断与 DMA

实现统一接口：

```
int spi_transfer_polling(...);
int spi_transfer_irq(...);
int spi_transfer_dma(...);
```

对比测试：

- 1 字节、8 字节、32 字节、256 字节、4 KB。
- CPU 占用率。
- 端到端延迟。
- 总线有效吞吐率。
- RTOS 下高优先级任务响应时间。

### 阶段四：SPI 从机

实现一个 MCU 从机寄存器协议：

```
请求:
  [命令][地址][长度][数据][CRC]

响应:
  [状态][长度][数据][CRC]
```

要求：

- CS 边沿复位帧状态。
- 支持非法长度检测。
- 支持 CRC 校验。
- 支持超长帧丢弃。
- 支持命令超时。
- 支持 FPGA 或另一块 MCU 作为主机进行压力测试。

### 阶段五：工业级验证

建立以下测试矩阵：

|测试项|方法|
|---|---|
|模式兼容性|Mode 0~3 全覆盖|
|频率裕量|从低速逐步升频，统计误码率|
|温度稳定性|高低温环境循环|
|并发访问|多任务随机发起事务|
|异常恢复|强制拉低 CS、停止 DMA、断开从机|
|电源时序|MCU 复位、从机复位、热插拔|
|长时间稳定性|连续运行 24~72 小时|
|数据完整性|CRC、序号、回读比对|

### 进阶方向

- SPI DMA 链表和 scatter-gather。
- Cortex-M7 D-Cache 与 DMA 一致性。
- Linux SPI framework、`spi_device` 和 `spi_driver`。
- Linux `spidev` 与内核态 SPI 驱动差异。
- QSPI、OSPI、HyperBus 和内存映射模式。
- SPI 从机协议设计与流控。
- 多主机 SPI 仲裁。
- 高速 SPI 信号完整性和 PCB 阻抗控制。
- 基于逻辑分析仪的自动化协议解码。
- SPI 故障注入、总线恢复和安全启动存储。