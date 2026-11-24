
## 1. 学习目标

### 理解

- 理解 BSP、HAL、驱动、RTOS 适配层之间的职责边界。
- 理解跨 RTOS 移植的主要耦合点：线程、锁、信号量、队列、延时、临界区、中断上下文和内存分配。
- 理解裸机、FreeRTOS、ThreadX、Zephyr 等运行环境在驱动模型上的差异。

### 掌握

- 掌握分层 BSP 的目录组织与依赖方向。
- 掌握通过 OSAL、设备资源描述表和统一驱动接口隔离 RTOS 依赖。
- 掌握中断安全 API、超时语义、错误码和资源生命周期设计。
- 掌握同一份 UART、SPI、I2C 驱动代码在不同 RTOS 下的适配方法。

### 精通

- 能定位驱动移植中的优先级反转、ISR 调用非法 API、缓存一致性、时钟初始化顺序等问题。
- 能设计支持静态内存、动态内存和无 RTOS 模式的统一驱动框架。
- 能量化比较不同 OS 抽象方式的延迟、内存和实时性代价。

### 能够设计

- 能设计可复用、可测试、可裁剪、可认证的跨 RTOS BSP。
- 能构建板级设备描述、启动流程、驱动注册和电源管理体系。
- 能将一个已有驱动从某 RTOS 移植到另一 RTOS，并保持上层 API 稳定。

---

## 2. 前置要求

### 知识要求

- C 语言：指针、结构体、函数指针、`volatile`、内存对齐、链接脚本。
- MCU：中断控制器、时钟树、GPIO、DMA、UART、SPI、I2C。
- RTOS：任务调度、优先级、信号量、互斥锁、消息队列、ISR 约束。
- 基本软件架构：分层、依赖倒置、接口抽象、错误处理。
- 基本并发理论：竞态、死锁、优先级反转、内存屏障。

### 技能要求

- 能阅读 MCU 厂商参考手册和启动文件。
- 能使用逻辑分析仪、示波器、调试器和 trace 工具。
- 能编写 Makefile/CMake 构建配置。
- 能独立分析 HardFault、总线错误和 DMA 数据损坏问题。

---

## 3. 技术概述

### 3.1 BSP 的定义

BSP 是连接**硬件板卡、芯片 SDK、驱动框架和操作系统**的工程层。它通常包含：

```
应用层
  |
设备服务层 / Middleware
  |
统一设备接口
  |
芯片无关驱动
  |
HAL / OSAL / 板级资源描述
  |
MCU 寄存器、启动文件、链接脚本
  |
实际硬件
```

BSP 不应成为“所有底层代码的垃圾桶”。其核心责任是：

1. 初始化板级资源。
2. 描述设备与引脚、DMA、IRQ、时钟之间的关系。
3. 提供统一的硬件访问入口。
4. 隔离芯片、编译器和 RTOS 差异。
5. 管理启动顺序、设备注册和板级电源策略。

### 3.2 跨 RTOS 设计的核心目标

跨 RTOS 不是简单把：

```
xSemaphoreTake(lock, timeout);
```

替换为：

```
tx_mutex_get(lock, timeout);
```

真正需要隔离的是四类依赖：

|依赖类别|典型内容|设计目标|
|---|---|---|
|同步依赖|Mutex、Semaphore、Event、Queue|统一超时和上下文语义|
|调度依赖|Task、Thread、优先级、Tick|屏蔽任务创建和调度 API|
|内存依赖|malloc、内存池、静态对象|明确所有权和释放责任|
|中断依赖|ISR 注册、屏蔽、FromISR API|严格区分线程上下文和中断上下文|

### 3.3 主流实现分支

1. **纯 HAL + OSAL**
    
    - 适合已有大量自研驱动的 MCU 项目。
    - 可控性高，迁移成本较低。
2. **统一设备模型**
    
    - 例如 Zephyr Device Model、RT-Thread Device、Linux 风格设备模型。
    - 适合设备数量较多、需要标准化访问的系统。
3. **厂商 HAL + RTOS Adapter**
    
    - 直接封装 STM32 HAL、NXP MCUXpresso、TI DriverLib。
    - 交付快，但厂商 API 容易泄漏到业务层。
4. **裸机兼容层 + RTOS 扩展**
    
    - 驱动核心默认不依赖 RTOS，异步能力通过适配器注入。
    - 最适合高复用和安全认证场景。

---

## 4. 核心特性横向对比

|方案|RTOS 依赖|代码复用|实时性|学习成本|适用场景|
|---|---|---|---|---|---|
|驱动直接调用 FreeRTOS|高|低|高|低|单一产品、快速交付|
|驱动直接调用 ThreadX|高|低|高|低|Azure RTOS 产品|
|驱动直接调用 Zephyr API|高|中|高|中|Zephyr 生态|
|自研 OSAL|低|高|高|中|多 RTOS 产品线|
|纯同步 HAL 驱动|无|高|可控|低|小型设备、裸机|
|统一设备模型|中|高|中到高|高|多设备、复杂平台|
|POSIX 兼容层|中|中|较低|低|Linux/仿真优先|
|RTOS 依赖注入|极低|极高|高|高|工业级平台化产品|

推荐架构：

```
业务代码
  |
通用设备 API
  |
设备驱动核心逻辑
  |---- 硬件访问接口
  |---- OSAL 接口
  |
BSP 资源描述
  |---- GPIO
  |---- IRQ
  |---- DMA
  |---- Clock
  |
RTOS 适配层
  |---- FreeRTOS
  |---- ThreadX
  |---- Zephyr
  |---- Bare-metal
```

---

## 5. 底层原理与功能特性深度解析

### 5.1 分层原则：驱动核心不直接依赖 RTOS

错误结构：

```
uart_driver.c
  |
  +-- freertos/FreeRTOS.h
  +-- xSemaphoreTake()
  +-- xQueueSendFromISR()
  +-- HAL_UART_Transmit()
```

推荐结构：

```
uart_core.c
  |
  +-- uart_port.h
  +-- osal.h
  +-- uart_hw.h
```

`uart_core.c` 只依赖抽象接口：

```
typedef enum {
    DRV_OK       = 0,
    DRV_EINVAL   = -1,
    DRV_ETIMEOUT = -2,
    DRV_EBUSY    = -3,
    DRV_EIO      = -4,
    DRV_ECONTEXT = -5,
} drv_status_t;

typedef struct {
    void *arg;

    drv_status_t (*lock)(void *arg, uint32_t timeout_ms);
    void (*unlock)(void *arg);

    uint32_t (*irq_save)(void *arg);
    void (*irq_restore)(void *arg, uint32_t key);

    uint32_t (*get_tick_ms)(void *arg);
} drv_os_ops_t;
```

驱动实例：

```
typedef struct {
    uintptr_t base;
    int irq_num;
    uint32_t baudrate;
    uint8_t *rx_buf;
    size_t rx_size;

    volatile size_t rx_head;
    volatile size_t rx_tail;

    const drv_os_ops_t *os;
    void *os_arg;
} uart_dev_t;
```

关键设计点：

- `base` 使用 `uintptr_t`，避免将整数地址错误转换为普通指针。
- 环形缓冲区的生产者和消费者必须明确。
- ISR 只做寄存器处理和数据搬运，不执行复杂协议解析。
- 锁、临界区、时间源由平台提供。

---

### 5.2 OSAL 接口设计

OSAL 不应只是 RTOS API 的机械别名，必须统一语义。

```
typedef void *osal_mutex_t;
typedef void *osal_sem_t;
typedef void *osal_thread_t;
typedef void *osal_queue_t;

typedef enum {
    OSAL_WAIT_NONE = 0,
    OSAL_WAIT_FOREVER = 0xFFFFFFFFu
} osal_wait_t;

int osal_mutex_create(osal_mutex_t *mutex, const char *name);
int osal_mutex_delete(osal_mutex_t mutex);
int osal_mutex_lock(osal_mutex_t mutex, uint32_t timeout_ms);
int osal_mutex_unlock(osal_mutex_t mutex);

int osal_sem_create(osal_sem_t *sem, uint32_t initial_count);
int osal_sem_delete(osal_sem_t sem);
int osal_sem_wait(osal_sem_t sem, uint32_t timeout_ms);
int osal_sem_post(osal_sem_t sem);
int osal_sem_post_isr(osal_sem_t sem, bool *need_switch);

uint32_t osal_tick_ms(void);
bool osal_in_isr(void);
void osal_yield_from_isr(bool need_switch);
```

#### 超时统一

不同 RTOS 的时间单位不同：

- FreeRTOS：Tick
- ThreadX：Tick
- Zephyr：`k_timeout_t`
- 裸机：毫秒或硬件定时器计数

OSAL 内部应统一为毫秒或纳秒，并集中转换：

```
static uint32_t ms_to_ticks_ceil(uint32_t ms, uint32_t tick_hz)
{
    if (ms == 0U) {
        return 0U;
    }

    uint64_t ticks = ((uint64_t)ms * tick_hz + 999U) / 1000U;
    return ticks > UINT32_MAX ? UINT32_MAX : (uint32_t)ticks;
}
```

使用向上取整而不是截断，否则 1 ms 超时在 100 Hz Tick 下会被转换为 0 Tick，实际变成“不等待”。

---

### 5.3 FreeRTOS 适配示例

```
#include "FreeRTOS.h"
#include "semphr.h"
#include "task.h"

int osal_mutex_create(osal_mutex_t *mutex, const char *name)
{
    (void)name;

    if (mutex == NULL) {
        return -1;
    }

    SemaphoreHandle_t h = xSemaphoreCreateMutex();
    if (h == NULL) {
        return -2;
    }

    *mutex = h;
    return 0;
}

int osal_mutex_lock(osal_mutex_t mutex, uint32_t timeout_ms)
{
    if (mutex == NULL || osal_in_isr()) {
        return -1;
    }

    TickType_t ticks;

    if (timeout_ms == OSAL_WAIT_FOREVER) {
        ticks = portMAX_DELAY;
    } else {
        ticks = pdMS_TO_TICKS(timeout_ms);

        /* 防止非零毫秒被截断为 0 Tick */
        if (ticks == 0U && timeout_ms != 0U) {
            ticks = 1U;
        }
    }

    return xSemaphoreTake((SemaphoreHandle_t)mutex, ticks) == pdTRUE
           ? 0 : -2;
}

int osal_mutex_unlock(osal_mutex_t mutex)
{
    if (mutex == NULL || osal_in_isr()) {
        return -1;
    }

    return xSemaphoreGive((SemaphoreHandle_t)mutex) == pdTRUE
           ? 0 : -2;
}

int osal_sem_post_isr(osal_sem_t sem, bool *need_switch)
{
    BaseType_t higher_priority_woken = pdFALSE;

    if (sem == NULL || need_switch == NULL) {
        return -1;
    }

    BaseType_t ok = xSemaphoreGiveFromISR(
        (SemaphoreHandle_t)sem,
        &higher_priority_woken
    );

    *need_switch = (higher_priority_woken == pdTRUE);
    return ok == pdTRUE ? 0 : -2;
}
```

---

### 5.4 ThreadX 适配示例

ThreadX 的超时单位通常由 `TX_TIMER_TICKS_PER_SECOND` 决定：

```
#include "tx_api.h"

static ULONG ms_to_tx_ticks(uint32_t ms)
{
    uint64_t ticks;

    if (ms == OSAL_WAIT_FOREVER) {
        return TX_WAIT_FOREVER;
    }

    ticks = ((uint64_t)ms * TX_TIMER_TICKS_PER_SECOND + 999U) / 1000U;

    if (ticks == 0U && ms != 0U) {
        ticks = 1U;
    }

    return ticks > UINT32_MAX ? UINT32_MAX : (ULONG)ticks;
}

int osal_mutex_lock(osal_mutex_t mutex, uint32_t timeout_ms)
{
    if (mutex == NULL || osal_in_isr()) {
        return -1;
    }

    UINT rc = tx_mutex_get(
        (TX_MUTEX *)mutex,
        ms_to_tx_ticks(timeout_ms)
    );

    return rc == TX_SUCCESS ? 0 : -2;
}
```

ThreadX 不允许在 ISR 中调用普通线程同步 API。必须使用事件标志、信号量或专门的 ISR 交互机制。

---

### 5.5 ISR 与线程上下文分离

推荐采用“ISR 生产，线程消费”模型：

```
void UARTx_IRQHandler(void)
{
    bool need_switch = false;

    while (uart_hw_rx_ready()) {
        uint8_t data = uart_hw_read_rx();

        if (ring_push_isr(&g_uart.rx_ring, data) != 0) {
            g_uart.rx_overflow++;
        }
    }

    if (uart_hw_rx_idle()) {
        uart_hw_clear_idle();
        (void)osal_sem_post_isr(g_uart.rx_sem, &need_switch);
    }

    osal_yield_from_isr(need_switch);
}
```

线程侧：

```
int uart_read_line(uart_dev_t *dev,
                   uint8_t *buf,
                   size_t capacity,
                   uint32_t timeout_ms)
{
    if (dev == NULL || buf == NULL || capacity < 2U) {
        return DRV_EINVAL;
    }

    uint32_t start = osal_tick_ms();

    while (true) {
        size_t n = ring_read_until_newline(
            &dev->rx_ring,
            buf,
            capacity
        );

        if (n > 0U) {
            return (int)n;
        }

        uint32_t elapsed = osal_tick_ms() - start;

        if (timeout_ms != OSAL_WAIT_FOREVER &&
            elapsed >= timeout_ms) {
            return DRV_ETIMEOUT;
        }

        uint32_t remain = timeout_ms == OSAL_WAIT_FOREVER
                        ? OSAL_WAIT_FOREVER
                        : timeout_ms - elapsed;

        int rc = osal_sem_wait(dev->rx_sem, remain);
        if (rc != 0) {
            return DRV_ETIMEOUT;
        }
    }
}
```

注意：

- 不在 ISR 中调用阻塞函数。
- 不在 ISR 中访问可能被线程同时修改的复杂对象。
- 环形缓冲区的单生产者、单消费者场景可以无锁，但必须保证索引读写的原子性。
- 多生产者或多消费者必须使用锁或消息队列。

---

### 5.6 设备资源描述

不要把 GPIO、DMA、IRQ 硬编码在驱动核心中。

```
typedef struct {
    uint32_t port;
    uint16_t pin;
    bool active_low;
} gpio_pin_t;

typedef struct {
    uintptr_t base;
    int irq;
    uint32_t clock_id;
    int dma_rx;
    int dma_tx;
} uart_resource_t;

typedef struct {
    uart_resource_t hw;
    gpio_pin_t tx_pin;
    gpio_pin_t rx_pin;
    uint32_t baudrate;
} uart_board_cfg_t;
```

板级实例：

```
static const uart_board_cfg_t console_cfg = {
    .hw = {
        .base = USART1_BASE,
        .irq = USART1_IRQn,
        .clock_id = RCC_USART1,
        .dma_rx = DMA1_CHANNEL3,
        .dma_tx = DMA1_CHANNEL4,
    },
    .tx_pin = { GPIOA, 9U, false },
    .rx_pin = { GPIOA, 10U, false },
    .baudrate = 115200U,
};
```

驱动核心只接收 `uart_board_cfg_t`，不关心具体芯片型号。

---

### 5.7 生命周期设计

建议明确以下状态：

```
typedef enum {
    DEV_STATE_OFF = 0,
    DEV_STATE_READY,
    DEV_STATE_SUSPENDED,
    DEV_STATE_ERROR,
} dev_state_t;
```

状态转换：

```
OFF -> READY       init 成功
READY -> SUSPENDED suspend 成功
SUSPENDED -> READY resume 成功
READY -> ERROR     硬件故障或不可恢复错误
READY -> OFF       deinit 成功
```

`deinit()` 必须按照反向依赖释放：

```
停止 DMA
  |
禁止外设中断
  |
注销 ISR
  |
释放队列、信号量和锁
  |
关闭外设时钟
  |
复位 GPIO
```

---

## 6. 性能量化分析

以下数据为典型 Cortex-M4 @ 168 MHz、ARM GCC `-O2`、FreeRTOS Tick 1 kHz 的工程基准参考值，实际数值必须在目标芯片上复测。

### 6.1 典型开销

|操作|典型 CPU 时间|RAM 开销|
|---|---|---|
|直接寄存器读写|20~80 ns|0 B|
|HAL 单次 GPIO 操作|80~250 ns|0 B|
|OSAL Mutex Lock/Unlock|0.8~2.5 us|约 80~120 B|
|二值信号量等待/释放|0.7~2.0 us|约 70~100 B|
|消息队列发送 16 B|1.5~4.0 us|队列控制块 + 16 B/项|
|ISR 投递信号量|0.3~1.2 us|0 B，控制块另计|
|任务切换|1.5~5.0 us|依赖上下文保存规模|
|DMA 启动|0.5~2.0 us|DMA 控制块|

### 6.2 延迟计算

一次异步 UART 接收路径的端到端延迟可近似为：

```
T_total =
    T_irq_entry
  + T_reg_read
  + T_ring_push
  + T_signal_post
  + T_scheduler
  + T_task_wakeup
  + T_protocol_parse
```

例如：

```
0.35 us + 0.15 us + 0.20 us + 0.70 us
+ 3.00 us + 1.20 us + 4.00 us
≈ 9.6 us
```

如果在 ISR 中进行协议解析，虽然减少了任务唤醒延迟，但会增加：

- ISR 执行时间；
- 关闭中断时间；
- 高优先级中断响应抖动；
- 协议代码在异常帧下的不可控执行时间。

通常应优先保证 ISR 短小确定。

### 6.3 内存计算

一个静态 UART 接收实例：

```
环形缓冲区：2048 B
驱动控制块：约 128~256 B
信号量/锁控制块：约 100~250 B
任务栈：1024~4096 B
DMA 描述符：32~128 B
```

若有 6 个 UART：

```
6 × (2048 + 256 + 200 + 2048)
≈ 27 KB
```

因此对于多设备系统，应考虑：

- 共享协议任务；
- 静态对象池；
- DMA 双缓冲；
- 按需创建同步对象；
- 统一事件队列而不是每个设备独立任务。

### 6.4 优化手段

|优化手段|典型收益|风险|
|---|---|---|
|ISR 环形缓冲替代逐字节队列|CPU 降低 20%~60%|缓冲区溢出|
|DMA 接收|CPU 降低 50%~95%|Cache、一致性、边界|
|统一事件任务|RAM 降低 10%~40%|任务间延迟增加|
|静态 OS 对象|消除碎片风险|配置复杂|
|减少 OSAL 层重复检查|延迟降低 0.1~0.5 us|错误防护下降|
|锁粒度缩小|并发吞吐提升|状态一致性更难保证|

---

## 7. 应用场景选型指南

### 7.1 决策流程图

```
是否需要支持多个 RTOS？
|
+-- 否 --> 驱动直接使用目标 RTOS API
|
+-- 是
    |
    +-- 是否需要裸机运行？
    |      |
    |      +-- 是 --> 驱动核心无 RTOS 依赖 + OSAL 注入
    |      |
    |      +-- 否 --> 统一 OSAL
    |
    +-- 是否有大量异步设备？
    |      |
    |      +-- 是 --> 事件/消息队列 + ISR 适配
    |      |
    |      +-- 否 --> 同步 HAL + 统一锁接口
    |
    +-- 是否需要设备热插拔/电源管理？
           |
           +-- 是 --> 统一设备状态机和 PM 接口
           |
           +-- 否 --> 静态设备表即可
```

### 7.2 典型场景

|场景需求|推荐方案|理由|
|---|---|---|
|同一驱动运行在 FreeRTOS 和 ThreadX|自研 OSAL|保持驱动核心稳定|
|工业控制器需要裸机启动诊断|OSAL 支持空实现|启动阶段不依赖调度器|
|高速 UART/以太网|DMA + ISR + 事件任务|降低 CPU 占用|
|低功耗传感器|设备状态机 + PM 接口|支持 suspend/resume|
|多 MCU 产品线|资源描述表 + 芯片 HAL|隔离引脚和寄存器差异|
|功能安全项目|静态对象 + 显式错误码|减少不可控行为|
|Linux 仿真测试|POSIX OSAL + 虚拟硬件|支持主机单元测试|

---

## 8. 工程最佳实践

### 8.1 设计原则

1. **依赖方向单向化**

```
应用 -> 设备接口 -> 驱动核心 -> OSAL/HAL -> BSP
```

禁止 BSP 反向依赖业务模块。

2. **核心逻辑与平台实现分离**

- `*_core.c`：协议、状态机、缓冲区。
- `*_hw.c`：寄存器、DMA、IRQ。
- `osal_*.c`：RTOS 实现。
- `board_*.c`：具体板卡资源。

3. **所有阻塞 API 明确上下文**

函数文档必须说明：

```
/**
 * @brief Read received data.
 * @note Thread context only. May block.
 * @param timeout_ms Timeout in milliseconds.
 */
```

4. **错误码不可混用**

不要直接把不同 RTOS 的错误码暴露给驱动上层。

5. **禁止驱动内部隐式创建任务**

任务创建应由 BSP 或设备服务层完成，便于：

- 统一优先级管理；
- 统一栈大小配置；
- 静态内存审计；
- 启动顺序控制。

### 8.2 选型决策矩阵

|需求|直接 RTOS API|OSAL|设备模型|纯 HAL|
|---|---|---|---|---|
|单产品快速开发|高|中|低|高|
|多 RTOS|低|高|高|高|
|裸机复用|低|高|中|高|
|设备数量多|中|高|高|中|
|运行时性能|高|高|中|最高|
|安全认证|中|高|中|高|
|团队维护难度|低|中|高|中|

### 8.3 工业级编码规范

- ISR 函数只调用明确标记为 ISR-safe 的 API。
- 所有 DMA 缓冲区显式指定对齐：

```
__attribute__((aligned(32)))
static uint8_t dma_rx_buf[1024];
```

- 不在驱动中使用无限制 `malloc()`。
- 所有数组访问验证长度。
- 所有寄存器位操作使用掩码，不依赖结构体位域的布局。
- 不在公共头文件中泄漏 RTOS 类型。
- 统一使用 `size_t` 表示缓冲区长度。
- 对 32 位 MCU 的共享索引使用自然对齐。
- 将编译器、芯片和 RTOS 差异集中到有限目录。

---

## 9. 常见错误与避坑指南

### 9.1 错误一：在 ISR 中使用普通阻塞 API

错误代码：

```
void SPI_IRQHandler(void)
{
    osal_mutex_lock(g_spi_mutex, 10);
    spi_process_frame();
    osal_mutex_unlock(g_spi_mutex);
}
```

根因：

- ISR 没有可阻塞的任务上下文。
- 可能触发 RTOS 断言或死锁。
- 锁持有者可能正在等待当前 ISR 完成。

正确实现：

```
void SPI_IRQHandler(void)
{
    bool need_switch = false;

    spi_hw_collect_rx(&g_spi.rx_ring);
    osal_sem_post_isr(g_spi.event_sem, &need_switch);
    osal_yield_from_isr(need_switch);
}
```

风险影响：

- 系统 HardFault；
- 中断延迟不可控；
- 高优先级任务无法运行。

---

### 9.2 错误二：将 Tick 截断为 0

错误代码：

```
uint32_t ticks = timeout_ms / portTICK_PERIOD_MS;
```

当 `timeout_ms = 1`，而 Tick 周期为 10 ms 时，结果为 0。

正确实现：

```
uint32_t ticks = (timeout_ms + portTICK_PERIOD_MS - 1U)
               / portTICK_PERIOD_MS;

if (timeout_ms != 0U && ticks == 0U) {
    ticks = 1U;
}
```

风险：

- 函数从“等待 1 ms”变为“立即返回”；
- 造成偶发通信失败；
- 不同 RTOS 上表现不一致。

---

### 9.3 错误三：DMA 缓存一致性错误

错误代码：

```
dma_start(rx_buf, 128);
```

在带 D-Cache 的 Cortex-M7 上，DMA 可能读取旧缓存或写入内存后 CPU 仍读取旧缓存。

正确处理：

```
SCB_CleanDCache_by_Addr(
    (uint32_t *)rx_buf,
    ALIGN_UP(128U, 32U)
);

dma_start(rx_buf, 128);

/* DMA 完成后 */
SCB_InvalidateDCache_by_Addr(
    (uint32_t *)rx_buf,
    ALIGN_UP(128U, 32U)
);
```

还需满足：

- 地址按 Cache line 对齐；
- 长度按 Cache line 对齐；
- DMA 缓冲区不能与非 DMA 数据共享 Cache line；
- 或将缓冲区放入 Non-cacheable 区域。

风险：

- 数据随机损坏；
- 仅在高优化、特定负载下复现；
- 现场极难定位。

---

### 9.4 错误四：驱动内部创建多个隐藏任务

错误代码：

```
int uart_init(void)
{
    osal_thread_create("uart_rx", uart_rx_task, NULL, 512, 10);
    osal_thread_create("uart_tx", uart_tx_task, NULL, 512, 10);
    return 0;
}
```

根因：

- 驱动初始化顺序不可见；
- 任务栈和优先级分散管理；
- 设备关闭时任务生命周期难以回收。

正确实现：

```
typedef struct {
    osal_thread_t worker;
    osal_sem_t event;
    uint8_t *stack;
    size_t stack_size;
} uart_runtime_t;

int uart_start(uart_dev_t *dev, const uart_runtime_t *runtime)
{
    if (dev == NULL || runtime == NULL) {
        return DRV_EINVAL;
    }

    dev->runtime = *runtime;
    return osal_thread_create(
        &dev->runtime.worker,
        "uart",
        uart_worker,
        dev,
        dev->runtime.stack,
        dev->runtime.stack_size,
        UART_TASK_PRIORITY
    );
}
```

风险：

- RAM 泄漏；
- 关闭设备后仍访问已释放对象；
- 多实例设备互相影响。

---

### 9.5 错误五：跨 RTOS 暴露原生对象类型

错误代码：

```
#include "FreeRTOS.h"
#include "semphr.h"

typedef struct {
    SemaphoreHandle_t lock;
} sensor_t;
```

正确实现：

```
typedef struct {
    osal_mutex_t lock;
} sensor_t;
```

风险：

- ThreadX/Zephyr 无法复用；
- 业务层被迫包含 RTOS 头文件；
- 单元测试和主机仿真困难。

---

## 10. 多机制组合使用方案

### 10.1 推荐异步设备架构

```
硬件中断
   |
   v
ISR：读取寄存器、写入环形缓冲区
   |
   v
ISR-safe 信号量/事件
   |
   v
设备工作线程
   |
   +-- 协议解析
   +-- 状态机推进
   +-- 超时处理
   +-- 上报统一设备事件
```

### 10.2 完整框架

```
typedef struct {
    uart_dev_t hw;
    osal_mutex_t tx_lock;
    osal_sem_t rx_event;
    osal_thread_t worker;

    uint8_t *rx_buf;
    size_t rx_capacity;

    volatile uint32_t rx_overflow;
    volatile dev_state_t state;
} uart_runtime_t;

static void uart_worker(void *arg)
{
    uart_runtime_t *rt = arg;

    while (rt->state == DEV_STATE_READY) {
        int rc = osal_sem_wait(
            rt->rx_event,
            100U
        );

        if (rc != 0) {
            uart_protocol_timeout(&rt->hw);
            continue;
        }

        while (uart_protocol_has_frame(&rt->hw)) {
            uart_frame_t frame;

            if (uart_protocol_get_frame(&rt->hw, &frame) == 0) {
                uart_dispatch_frame(&frame);
            }
        }
    }
}

int uart_write(uart_runtime_t *rt,
               const uint8_t *data,
               size_t len,
               uint32_t timeout_ms)
{
    if (rt == NULL || data == NULL || len == 0U) {
        return DRV_EINVAL;
    }

    int rc = osal_mutex_lock(rt->tx_lock, timeout_ms);
    if (rc != 0) {
        return DRV_ETIMEOUT;
    }

    rc = uart_hw_dma_transmit(&rt->hw, data, len);

    int unlock_rc = osal_mutex_unlock(rt->tx_lock);

    if (rc != 0 || unlock_rc != 0) {
        return DRV_EIO;
    }

    return DRV_OK;
}
```

### 10.3 组合机制的职责

|机制|责任|
|---|---|
|Mutex|保护发送路径和共享配置|
|Semaphore/Event|ISR 通知工作线程|
|Ring Buffer|吸收突发数据|
|DMA|降低 CPU 搬运开销|
|Worker Task|执行非实时协议逻辑|
|Timer|超时、帧间隔和重试|
|Device State|管理初始化、挂起和故障|

---

## 11. 工业级实际案例分析

### 11.1 案例一：同一 UART 驱动支持 FreeRTOS 与 ThreadX

#### 需求

- 115200 bps 控制台。
- 支持 DMA 接收和空闲中断。
- 驱动核心代码不修改。
- 支持超时读取和设备挂起。

#### 架构

```
console_service
  |
uart_core.c
  |
uart_hw_stm32.c
  |
osal_freertos.c / osal_threadx.c
```

#### 设计要点

- UART 核心只操作 ring buffer 和事件。
- FreeRTOS 使用 `xSemaphoreGiveFromISR`。
- ThreadX 使用 `tx_semaphore_put`。
- 两者都映射为 `osal_sem_post_isr()`。
- 控制台服务不包含任何 RTOS 头文件。

#### 关键指标

- DMA 接收比逐字节中断降低 CPU 占用约 60%~90%。
- 端到端帧通知延迟主要由任务调度和 DMA 空闲检测决定。
- 设备切换 RTOS 时，核心驱动变更量通常低于 10%。

---

### 11.2 案例二：工业传感器 RS-485 驱动

#### 需求

- Modbus RTU。
- 半双工方向控制。
- 3 个串口实例。
- 支持异常重试和总线超时。
- 不能因单个设备阻塞整个采集系统。

#### 架构

```
采集调度任务
   |
Modbus 服务层
   |
RS485 驱动
   +-- TX Mutex
   +-- RX Ring Buffer
   +-- DMA
   +-- Timer
   +-- GPIO DE 控制
```

#### 关键代码

```
int rs485_transaction(rs485_dev_t *dev,
                      const uint8_t *request,
                      size_t request_len,
                      uint8_t *response,
                      size_t response_cap,
                      uint32_t timeout_ms)
{
    if (dev == NULL || request == NULL ||
        response == NULL || request_len == 0U) {
        return DRV_EINVAL;
    }

    int rc = osal_mutex_lock(dev->bus_lock, timeout_ms);
    if (rc != 0) {
        return DRV_EBUSY;
    }

    gpio_write(dev->de_pin, true);

    rc = uart_dma_write(dev->uart, request, request_len, timeout_ms);
    if (rc != 0) {
        gpio_write(dev->de_pin, false);
        osal_mutex_unlock(dev->bus_lock);
        return rc;
    }

    uart_wait_tx_complete(dev->uart, timeout_ms);
    gpio_write(dev->de_pin, false);

    rc = uart_read_frame(
        dev->uart,
        response,
        response_cap,
        timeout_ms
    );

    osal_mutex_unlock(dev->bus_lock);
    return rc;
}
```

#### 设计要点

- DE 引脚必须在最后一个停止位发送完成后再拉低。
- 不能用 DMA 完成事件代替 UART 移位寄存器空闲事件。
- 总线锁的范围应覆盖完整事务。
- 事务超时后必须清理 DMA、UART 状态和 DE 引脚。

---

### 11.3 案例三：低功耗 I2C 传感器 BSP

#### 需求

- 运行于 FreeRTOS 和裸机模式。
- 睡眠电流低于 10 uA。
- 传感器支持运行、待机、关断三种状态。
- 支持 I2C 错误恢复。

#### 状态机

```
OFF
 |
 +-- power_on --> INIT
                    |
                    +-- init_ok --> READY
                    |                |
                    |                +-- suspend --> SLEEP
                    |                |                 |
                    |                |                 +-- resume --> READY
                    |                |
                    |                +-- bus_error --> RECOVER
                    |
                    +-- init_fail --> ERROR
```

#### I2C 恢复流程

```
int i2c_bus_recover(i2c_bus_t *bus)
{
    if (bus == NULL) {
        return DRV_EINVAL;
    }

    i2c_disable_peripheral(bus);

    gpio_to_open_drain(bus->scl);
    gpio_to_open_drain(bus->sda);

    for (unsigned i = 0U; i < 9U; ++i) {
        gpio_write(bus->scl, false);
        delay_us(5U);
        gpio_write(bus->scl, true);
        delay_us(5U);

        if (gpio_read(bus->sda)) {
            break;
        }
    }

    /* 产生 STOP */
    gpio_write(bus->sda, false);
    delay_us(5U);
    gpio_write(bus->scl, true);
    delay_us(5U);
    gpio_write(bus->sda, true);

    i2c_reinit_peripheral(bus);
    return 0;
}
```

#### 设计要点

- 睡眠前停止 DMA 和中断。
- 恢复后重新配置 GPIO 复用和 I2C 时钟。
- 不假设从设备一定释放 SDA。
- 裸机模式下 OSAL Mutex 可以映射为关中断或禁用总线重入，但必须明确不可重入限制。

---

## 12. 高频问题深度答疑

### 问题一：OSAL 是否会损失实时性？

会有少量开销，但通常不是主要瓶颈。真正影响实时性的因素通常是：

- 锁竞争；
- 任务优先级配置；
- 临界区长度；
- 中断嵌套策略；
- DMA 和 Cache 管理；
- 调度粒度。

对于高频路径，可以保留两层接口：

```
osal_mutex_lock();        /* 通用路径 */
port_fast_lock();         /* 已验证的高性能路径 */
```

但快速路径必须限制在硬件适配层，不能让业务代码到处使用平台 API。

### 问题二：驱动应该使用 Mutex 还是 Semaphore？

- 保护共享资源：Mutex。
- 表示事件或资源计数：Semaphore。
- 传递数据：Queue/Ring Buffer。
- 只允许一个线程访问总线：Mutex。
- ISR 通知线程有数据：Binary Semaphore/Event。

不要使用二值信号量替代互斥锁，因为它通常不具备优先级继承。

### 问题三：为什么不直接采用 POSIX API？

POSIX 有利于移植和仿真，但在 MCU 上存在问题：

- API 语义可能过于宽泛；
- 对 ISR 支持弱；
- 时间和错误码映射复杂；
- 额外抽象层影响代码尺寸；
- 很多 RTOS 的原生高效机制无法暴露。

建议：主机测试可以使用 POSIX OSAL，目标 MCU 使用轻量原生适配。

### 问题四：驱动是否应该自己创建任务？

通常不应该。任务属于系统资源管理层。驱动只需要：

- 提供工作函数；
- 提供事件接口；
- 声明所需栈大小和优先级建议；
- 由 BSP 或系统启动层创建任务。

特殊情况下，复杂协议栈可以由驱动包创建内部任务，但必须提供显式 `start/stop/deinit` 和静态资源配置。

### 问题五：怎样处理不同 RTOS 的优先级模型？

不同 RTOS 的优先级方向和范围可能不同：

- 某些系统数字越小优先级越高；
- 某些系统数字越大优先级越高；
- 支持的等级数量不同。

应使用逻辑优先级：

```
typedef enum {
    TASK_PRIO_LOW,
    TASK_PRIO_NORMAL,
    TASK_PRIO_HIGH,
    TASK_PRIO_ISR_DEFERRED,
} logical_prio_t;
```

各 RTOS 适配层负责映射，禁止业务层直接使用数值优先级。

### 问题六：如何证明驱动真正跨 RTOS？

至少要完成以下验证：

1. 相同 API 在裸机、FreeRTOS、ThreadX 下编译。
2. 相同测试向量得到相同协议结果。
3. 超时边界一致。
4. ISR 与线程竞态测试通过。
5. 设备重复初始化和反初始化无资源泄漏。
6. DMA、Cache、异常恢复测试通过。
7. 使用静态分析检查 RTOS API 越界调用。

---

## 13. 课程核心总结

### 13.1 核心要点

1. **BSP 的本质是稳定硬件、驱动框架和操作系统之间的边界**，而不是简单归集启动文件、HAL 和外设初始化代码。
2. **跨 RTOS 移植的核心是语义统一**，而非 API 名称替换。超时、ISR 安全性、调度触发、对象生命周期和错误码必须具有一致定义。
3. **驱动核心应避免直接依赖具体 RTOS**。RTOS 差异集中在 OSAL，芯片差异集中在 HAL 或硬件适配层，板卡差异集中在资源描述层。
4. **ISR 与线程上下文必须严格分离**。ISR 负责快速采集、状态清除和事件通知，线程负责协议解析、阻塞操作和复杂状态机。
5. **Mutex、Semaphore、Event 和 Queue 不可仅按 API 形态替换**：
    - Mutex 用于互斥所有权和优先级继承；
    - Semaphore 用于事件或资源计数；
    - Event Flags 用于组合状态通知；
    - Queue 用于传递具有所有权的数据。
6. **DMA 移植不止涉及 DMA 控制器**，还涉及 Cache 一致性、内存区域属性、总线可达性、对齐约束和描述符生命周期。
7. **设备资源不得硬编码在驱动核心中**。GPIO、Clock、IRQ、DMA 和实例基地址应由板级静态配置表或设备树提供。
8. **初始化和反初始化必须对称**。部分初始化失败时，应按依赖关系逆序回滚已获取的资源。
9. **驱动内部应避免隐式创建任务和动态分配内存**，尤其是在功能安全、长期运行和资源受限系统中。
10. **跨 RTOS 能力必须通过测试证明**，包括编译矩阵、超时边界、ISR 竞态、资源泄漏、故障注入和性能基准。

### 13.2 性能排序

典型路径按执行开销从低到高排序：

```
直接寄存器访问
  < 芯片 HAL 内联接口
  < 无竞争临界区
  < OSAL 函数间接调用
  < 无竞争 Mutex
  < ISR 投递 Event/Semaphore
  < Queue 复制小消息
  < 触发任务切换
  < 动态内存分配
  < 高竞争锁或同步 I/O 阻塞
```

对于数据搬运方式，典型 CPU 占用从低到高排序：

```
DMA 链式传输
  < DMA 单块传输
  < FIFO 批量中断
  < 逐字节中断
  < 轮询等待
```

这里不存在绝对最优方案：

- 小于数个字节的短传输中，DMA 配置成本可能高于轮询。
- 极低延迟控制路径中，任务唤醒成本可能高于 ISR 内执行固定长度操作。
- 高吞吐场景中，逐字节 Queue 投递通常明显劣于环形缓冲区加批量通知。
- 无竞争 Mutex 的开销通常可控，但锁竞争会引入调度延迟和优先级反转风险。

### 13.3 通用选型结论

|系统条件|推荐结论|
|---|---|
|产品只运行一种 RTOS，生命周期短|可直接使用原生 RTOS API，但仍应隔离业务层|
|同一驱动需要支持两个以上 RTOS|建立语义明确的轻量 OSAL|
|同时支持 RTOS 和裸机|驱动核心采用非阻塞状态机，OSAL 通过能力注入|
|数据率高、突发明显|DMA + Ring Buffer + ISR 延迟处理|
|硬实时、低抖动|静态资源、固定执行路径、短临界区、避免运行期分配|
|设备数量多且支持电源管理|统一设备模型、生命周期状态机和依赖管理|
|功能安全或高可靠场景|静态对象、确定性超时、完整回滚、故障注入测试|
|需要 Linux 主机仿真|驱动核心与寄存器访问分离，提供 POSIX 和虚拟硬件适配|
|存在 Cortex-M7/A 等 Cache|建立统一 DMA 内存与 Cache 维护接口|
|多板卡共用同一 MCU|板级资源表或设备树与驱动实现彻底分离|

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|同步机制|数据通道|推荐执行模型|关键风险|
|---|---|---|---|---|
|低速 GPIO 扩展器|Mutex|同步 I2C|调用线程执行|总线锁粒度|
|UART 控制台|TX Mutex、RX Event|Ring Buffer|ISR + 工作线程|日志递归、缓冲溢出|
|Modbus RTU|总线 Mutex、响应 Event|DMA + Ring Buffer|单事务状态机|DE 时序、帧间隔|
|SPI Flash|Bus Mutex、完成 Event|DMA|同步封装异步底层|擦除超时、掉电|
|高频 ADC|Event/Notification|DMA 双缓冲|ISR 交换缓冲，任务处理|Cache、处理不及时|
|CAN/CAN FD|TX Mutex、RX Event|Mailbox + Queue|ISR + 协议线程|总线关闭恢复|
|Ethernet MAC|Event、无锁描述符环|DMA Descriptor|NAPI 类批处理|Cache、描述符所有权|
|低功耗传感器|Mutex、Timer|同步或异步 I2C|状态机 + PM|唤醒顺序|
|安全看门狗|临界区或原子操作|状态位图|独立高优先级任务|虚假喂狗|
|固件升级 Flash|全局升级锁|分块缓冲|工作线程|掉电一致性|

### 14.2 特性对比表

|机制|可阻塞|ISR 可用性|优先级继承|数据携带|典型用途|
|---|---|---|---|---|---|
|临界区|否|受限|否|否|极短共享状态保护|
|Spinlock|忙等|平台相关|否|否|SMP 极短临界区|
|Mutex|是|否|通常支持|否|共享设备互斥|
|Binary Semaphore|是|通常可投递|通常不支持|否|ISR 到任务通知|
|Counting Semaphore|是|通常可投递|否|计数|资源数量管理|
|Event Flags|是|通常可置位|否|位状态|多事件组合等待|
|Queue|是|通常有 ISR API|否|是|命令和消息传输|
|Ring Buffer|由实现决定|适合 ISR 写入|否|是|连续字节流|
|Direct Notification|是|通常支持|否|小整数/位|单任务高效通知|
|Polling|否|可用|不适用|否|启动期或极短操作|

### 14.3 上下文约束表

|操作|线程上下文|ISR 上下文|启动前上下文|
|---|---|---|---|
|Mutex Lock|允许|禁止|通常禁止|
|阻塞 Queue Send|允许|禁止|禁止|
|ISR Queue Send|禁止或无意义|允许|禁止|
|动态分配|谨慎允许|禁止|依赖堆初始化|
|忙等待微秒延时|谨慎使用|仅极短时序|允许|
|DMA 启动|允许|仅经验证后允许|依赖时钟初始化|
|Cache 维护|允许|可用但应受控|依赖 Cache 状态|
|日志格式化|允许但有开销|禁止|取决于后端|
|电源状态切换|允许|禁止|板级初始化阶段允许|

### 14.4 移植检查表

|检查项|必须确认的内容|
|---|---|
|Tick|频率、宽度、回绕、向上取整、永久等待表示|
|优先级|数值方向、可用范围、系统保留级别|
|ISR API|可调用接口、切换触发方式、最大系统调用中断优先级|
|Mutex|是否支持优先级继承、递归行为、所有者检查|
|Queue|复制语义、元素对齐、ISR 限制、满队列行为|
|Timer|回调上下文、精度、是否允许阻塞|
|内存|动态分配线程安全性、静态对象大小、对齐要求|
|DMA|可访问区域、Cache、一致性、总线仲裁|
|启动|调度器启动前允许使用的 API|
|关闭|ISR/DMA 停止顺序、等待中的线程如何唤醒|
|错误码|超时、忙、无内存、上下文非法的统一映射|
|构建|RTOS 头文件不得泄漏至公共设备接口|

---

## 15. 学习效果自检

### 15.1 架构能力

- [ ]  能清晰区分 BSP、HAL、OSAL、驱动核心和设备服务层。
- [ ]  能画出目标项目的依赖方向，并识别反向依赖。
- [ ]  能把板级资源从驱动算法中拆分出来。
- [ ]  能设计支持多实例设备的资源描述结构。
- [ ]  能设计 `init/start/stop/suspend/resume/deinit` 生命周期。

### 15.2 RTOS 移植能力

- [ ]  能统一 FreeRTOS、ThreadX 和 Zephyr 的超时语义。
- [ ]  能处理非零毫秒转换成 0 Tick 的边界问题。
- [ ]  能定义普通上下文和 ISR 上下文两组 API。
- [ ]  能映射不同 RTOS 的优先级方向和范围。
- [ ]  能解释为什么 Mutex 不能被二值信号量无条件替代。
- [ ]  能实现裸机 OSAL，并明确其并发能力边界。

### 15.3 驱动设计能力

- [ ]  能实现单生产者、单消费者环形缓冲区。
- [ ]  能证明共享索引访问满足原子性和内存顺序要求。
- [ ]  能设计 DMA 双缓冲或 Ping-Pong Buffer。
- [ ]  能正确区分 DMA 完成和外设真正发送完成。
- [ ]  能处理设备超时后的寄存器、DMA 和同步对象复位。
- [ ]  能保证部分初始化失败时资源完整回滚。

### 15.4 实时性与性能能力

- [ ]  能测量 ISR 执行时间、任务唤醒延迟和端到端延迟。
- [ ]  能根据吞吐量计算最小缓冲区容量。
- [ ]  能评估 Queue 复制与 Ring Buffer 的 CPU、RAM 差异。
- [ ]  能定位优先级反转和长临界区。
- [ ]  能确定 DMA 在短传输下的盈亏平衡点。
- [ ]  能建立平均值、P99、最大值和抖动统计，而非只看平均值。

### 15.5 可靠性与验证能力

- [ ]  能进行 ISR 与线程并发压力测试。
- [ ]  能注入丢中断、DMA 错误、总线卡死和超时故障。
- [ ]  能测试 Tick 回绕和无限等待。
- [ ]  能验证重复初始化、停止和反初始化。
- [ ]  能在带 Cache 平台验证 DMA 缓冲区一致性。
- [ ]  能通过编译规则阻止驱动核心包含具体 RTOS 头文件。

若上述检查项中有 **5 项以上无法独立完成**，说明仍停留在 API 适配层；若能完成全部项目并给出量化数据，才具备平台级 BSP 设计能力。

---

## 16. 实践与进阶路径

### 16.1 第一阶段：建立最小 OSAL

#### 任务

实现以下接口，并分别适配 FreeRTOS 和 ThreadX：

```
int osal_mutex_create(osal_mutex_t *mutex, const char *name);
int osal_mutex_lock(osal_mutex_t mutex, uint32_t timeout_ms);
int osal_mutex_unlock(osal_mutex_t mutex);

int osal_sem_create(osal_sem_t *sem, uint32_t initial_count);
int osal_sem_wait(osal_sem_t sem, uint32_t timeout_ms);
int osal_sem_post(osal_sem_t sem);
int osal_sem_post_isr(osal_sem_t sem, bool *need_switch);

uint32_t osal_tick_ms(void);
bool osal_in_isr(void);
```

#### 验收标准

- `0 ms` 表示立即返回。
- 非零短超时至少等待 1 Tick。
- 永久等待在两个 RTOS 中语义一致。
- ISR 调用线程接口能够被断言或返回错误捕获。
- Tick 回绕不破坏时间差计算。
- 公共头文件不包含具体 RTOS 头文件。

---

### 16.2 第二阶段：移植 UART 异步驱动

#### 任务

实现：

- DMA 循环接收；
- UART Idle Line 帧边界检测；
- ISR 到线程通知；
- Ring Buffer；
- 超时读取；
- DMA 异步发送；
- `suspend/resume/deinit`。

#### 缓冲区容量计算

若最大阻塞时间为 `T_block`，输入数据率为 `R_byte`，安全系数为 `K`：

```
Buffer_min = ceil(R_byte × T_block × K)
```

例如，UART 921600 bps、8N1：

```
R_byte = 921600 / 10 = 92160 byte/s
T_block = 20 ms
K = 1.5

Buffer_min = ceil(92160 × 0.020 × 1.5)
           = 2765 byte
```

工程上应选择 **4096 B**。

#### 验收标准

- 持续满速接收 24 小时无溢出或数据错序。
- ISR 最大执行时间可量化。
- 接收通知延迟具有 P99 和最大值。
- 超时后下一帧仍能正常接收。
- 反初始化后无中断访问失效对象。
- FreeRTOS 和 ThreadX 上通过相同测试向量。

---

### 16.3 第三阶段：建立统一设备生命周期

#### 任务

为 UART、SPI 和 I2C 定义统一操作集：

```
typedef struct {
    int (*init)(void *dev);
    int (*start)(void *dev);
    int (*suspend)(void *dev);
    int (*resume)(void *dev);
    int (*stop)(void *dev);
    int (*deinit)(void *dev);
} device_ops_t;
```

增加以下能力：

- 引用计数或所有权管理；
- 依赖设备启动顺序；
- 初始化失败逆序回滚；
- 电源域和时钟门控；
- 状态转换合法性检查。

#### 验收标准

- 任意初始化步骤失败后均无资源泄漏。
- `deinit()` 可重复调用或明确返回状态错误。
- Suspend 期间不会产生非法 DMA 和 IRQ。
- Resume 后寄存器状态、GPIO 复用和时钟完整恢复。

---

### 16.4 第四阶段：主机仿真与故障注入

#### 任务

编写 POSIX OSAL 和虚拟 UART 后端：

```
uart_core.c
  |
  +-- osal_posix.c
  +-- uart_hw_mock.c
```

注入以下故障：

- 丢失中断；
- DMA 部分完成；
- Ring Buffer 溢出；
- 设备长时间 Busy；
- Tick 回绕；
- 信号量重复投递；
- 初始化到第 N 步失败；
- 设备关闭时仍有线程等待。

#### 验收标准

- 核心状态机达到较高分支覆盖率。
- 所有故障均有确定错误码或恢复路径。
- ThreadSanitizer 环境下无已知数据竞争。
- AddressSanitizer 环境下无越界、释放后使用和泄漏。

---

### 16.5 性能测试方法

#### GPIO 脉冲测量

在关键路径入口和出口翻转 GPIO：

```
void UARTx_IRQHandler(void)
{
    trace_gpio_set();

    uart_irq_handler(&g_uart);

    trace_gpio_clear();
}
```

通过示波器或逻辑分析仪测量：

- ISR 执行时间；
- IRQ 到任务开始运行的延迟；
- DMA 完成到协议处理完成的延迟；
- 临界区持续时间。

#### DWT Cycle Counter 测量

```
static void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t cycles_now(void)
{
    return DWT->CYCCNT;
}
```

时间换算：

```
T_us = cycles × 1,000,000 / CPU_Hz
```

测试时必须记录：

- MCU 型号和主频；
- Flash Wait State；
- Cache 和分支预测状态；
- 编译器版本；
- 优化级别；
- RTOS Tick 频率；
- 中断负载；
- 测试样本数量。

#### 统计指标

不要只报告平均值。至少输出：

```
最小值
平均值
P95
P99
最大值
标准差
超时次数
缓冲区峰值占用
```

对于硬实时路径，**最大值和上界证明**比平均值更重要。

---

### 16.6 建议的 CI 验证矩阵

|维度|配置|
|---|---|
|RTOS|Bare-metal、FreeRTOS、ThreadX、POSIX Mock|
|编译器|GCC、Clang，必要时增加 IAR/Arm Compiler|
|优化级别|`-O0`、`-O2`、`-Os`|
|断言|Enabled、Disabled|
|内存模式|Static、Dynamic|
|数据宽度|32-bit Host、64-bit Host|
|Endianness|目标平台允许时覆盖|
|测试类型|Unit、Integration、HIL、Stress|
|故障类型|Timeout、DMA Error、IRQ Loss、Bus Stuck|
|静态分析|MISRA、CERT C、未定义行为、调用图|

建议设置以下构建门禁：

```
驱动核心包含 FreeRTOS/ThreadX/Zephyr 头文件 -> 构建失败
ISR 调用非 ISR-safe OSAL 接口             -> 静态检查失败
公共头文件暴露 RTOS 原生类型              -> 接口检查失败
存在未处理的编译器警告                    -> 构建失败
性能基准回退超过设定阈值                  -> CI 失败
```

---

### 16.7 进阶学习方向

1. **设备树与代码生成**
    
    - 从 DTS、YAML 或 SVD 生成板级资源描述。
    - 在构建期检查引脚、DMA 通道和 IRQ 冲突。
2. **零拷贝驱动**
    
    - Descriptor Ring；
    - Buffer Ownership；
    - Scatter-Gather DMA；
    - Cache line 隔离。
3. **SMP 与多核 MCU**
    
    - Spinlock；
    - 核间中断；
    - 内存屏障；
    - Cache Coherency；
    - 驱动实例归属。
4. **低功耗体系**
    
    - Runtime PM；
    - Wakeup Source；
    - Clock Domain；
    - Suspend Dependency Graph；
    - Tickless Idle 协同。
5. **功能安全与高可靠设计**
    
    - MISRA C；
    - ISO 26262；
    - IEC 61508；
    - 静态资源证明；
    - 故障注入与诊断覆盖率。
6. **安全启动与可信驱动**
    
    - TrustZone-M；
    - MPU 隔离；
    - 安全/非安全中断路由；
    - DMA 访问控制；
    - 外设权限最小化。
7. **形式化与确定性分析**
    
    - 最坏执行时间 WCET；
    - 锁依赖图；
    - 状态机模型检查；
    - 中断响应上界；
    - 栈深度静态分析。

最终实践目标是形成一套具备以下属性的 BSP：

```
板卡资源可配置
RTOS 可替换
驱动核心可复用
ISR 行为可证明
资源生命周期可回滚
DMA 与 Cache 一致性可验证
实时性能可量化
故障恢复路径可测试
构建依赖可自动检查
```

达到这一目标后，BSP 才不再是单板初始化代码集合，而是能够支撑多芯片、多板卡、多 RTOS 产品线的**可演进底层平台**。