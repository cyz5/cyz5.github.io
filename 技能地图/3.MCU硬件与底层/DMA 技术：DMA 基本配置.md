
## 1. 学习目标

### 理解

完成本课后，应能够：

- 理解 DMA 在 MCU 数据搬运链路中的系统定位。
- 理解 DMA 控制器、通道、请求源、传输单元、地址递增和传输完成事件之间的关系。
- 理解 **外设寄存器、内存、FIFO、总线矩阵、Cache** 对 DMA 行为的影响。
- 理解 DMA 传输完成、中断、半传输、错误事件的硬件触发逻辑。
- 理解单次传输、循环传输、双缓冲传输的工作边界。

### 掌握

能够：

- 配置内存到外设、外设到内存、内存到内存三类 DMA。
- 配置 DMA 传输方向、数据宽度、地址递增、优先级、循环模式。
- 正确处理 DMA 中断、错误标志和资源释放。
- 使用 DMA 完成 UART、SPI、ADC 等外设的数据搬运。
- 计算 DMA 缓冲区大小、带宽、占用率和实时性裕量。

### 精通

能够：

- 根据外设数据率、CPU 负载、实时性要求选择 DMA 传输模式。
- 分析 DMA 与 CPU、Cache、总线仲裁、外设 FIFO 之间的耦合问题。
- 处理 DMA 缓冲区数据一致性、环形缓冲、半传输和双缓冲。
- 定位 DMA 不传输、数据错位、首包异常、偶发丢包等工业现场问题。
- 设计可复用、可测试、可移植的 DMA 驱动抽象层。

### 能够设计

能够设计：

- 面向 UART/SPI/ADC 的生产级 DMA 驱动。
- 基于双缓冲或 Ping-Pong Buffer 的连续采集框架。
- 支持超时、错误恢复、取消传输、并发保护的 DMA 管理模块。
- 具备 Cache 一致性处理、低 CPU 占用和故障诊断能力的 DMA 架构。

---

## 2. 前置要求

### 知识要求

1. 熟悉 C 语言指针、数组、结构体、`volatile`。
    
2. 理解 MCU 的：
    
    - 内存映射；
    - 外设寄存器；
    - 中断控制器；
    - 时钟树；
    - 总线结构；
    - SRAM、Flash、外设地址空间。
3. 理解 UART、SPI、ADC 至少一种外设的基本工作原理。
    
4. 了解中断服务函数、临界区和并发访问。
    
5. 具备基本的 RTOS 任务、队列或信号量知识。
    
6. 了解 Cortex-M 的 D-Cache、内存屏障和 MPU 基础概念。
    

### 技能要求

1. 能够阅读芯片参考手册中的 DMA 章节。
2. 能够通过寄存器或 HAL/LL 驱动完成外设配置。
3. 能够使用逻辑分析仪、示波器、调试器验证数据时序。
4. 能够查看 DMA 状态寄存器和错误标志。
5. 能够编写基础的环形缓冲区和中断驱动代码。

---

## 3. 技术概述

## 3.1 DMA 的定义

DMA，即 Direct Memory Access，直接存储器访问，是一种允许硬件控制器在 **内存与外设之间，或内存与内存之间直接搬运数据** 的机制。

传统 CPU 搬运模式：

```
CPU 读取外设寄存器
    ↓
CPU 将数据写入内存
    ↓
CPU 重复执行 N 次
```

DMA 搬运模式：

```
DMA 控制器读取外设寄存器
    ↓
DMA 控制器写入内存
    ↓
N 次传输完成后通知 CPU
```

核心区别是：

> **DMA 将数据搬运工作从 CPU 指令执行路径中剥离出来，但不会消除总线带宽消耗。**

DMA 的主要价值：

- 降低 CPU 中断频率和指令负载；
- 提升连续数据流处理能力；
- 改善实时性；
- 适用于高吞吐、周期性、批量数据搬运；
- 允许 CPU 与外设数据传输并行执行。

DMA 并不是“更快的内存”，而是：

> **一种由硬件驱动的总线数据传输机制。**

---

## 3.2 DMA 基本数据通路

以 ADC 采样为例：

```
ADC 数据寄存器
      │
      │ 外设请求
      ▼
DMA 请求选择器 / DMAMUX
      │
      ▼
DMA 通道
      │
      ├── 外设地址：固定
      ├── 内存地址：递增
      ├── 数据宽度：16 bit
      ├── 计数器：N
      └── 传输模式：循环
      │
      ▼
SRAM 缓冲区
```

以 UART 发送为例：

```
SRAM 缓冲区
      │
      ▼
DMA 通道
      │
      ├── 内存地址：递增
      ├── 外设地址：固定
      ├── 数据宽度：8 bit
      ├── 方向：Memory → Peripheral
      └── 模式：Normal
      │
      ▼
UART 发送数据寄存器
```

---

## 3.3 DMA 主要技术分支

### 按传输方向分类

1. **Peripheral-to-Memory**
    
    - ADC 采样；
    - UART 接收；
    - SPI 接收；
    - 摄像头数据接收。
2. **Memory-to-Peripheral**
    
    - UART 发送；
    - SPI 发送；
    - DAC 波形输出；
    - PWM 波形更新。
3. **Memory-to-Memory**
    
    - 大块缓冲区复制；
    - 图像搬运；
    - 数据预处理；
    - 内存初始化。

### 按运行方式分类

1. Normal 模式：传输完成后停止。
2. Circular 模式：传输完成后自动重新装载。
3. Double Buffer 模式：两个内存缓冲区交替工作。
4. Scatter-Gather 模式：多个 DMA 描述符连续执行。
5. Linked List 模式：高端 DMA 控制器支持的链表传输。

### 按数据组织方式分类

1. 单次传输；
2. 突发传输；
3. FIFO 聚合传输；
4. 多块传输；
5. 二维或二维步进传输。

---

## 4. 核心特性横向对比

### 4.1 不同搬运方式对比

|方案|CPU 参与程度|中断频率|实时性|吞吐能力|适用场景|
|---|---|---|---|---|---|
|CPU 轮询|极高|低|差|低|极低速、初始化、简单控制|
|CPU 中断逐字节处理|高|很高|中|低到中|低速 UART、少量控制数据|
|DMA 单次模式|低|低|高|高|UART/SPI 批量发送|
|DMA 循环模式|极低|低到中|高|高|ADC 连续采样、UART 环形接收|
|DMA 双缓冲|极低|中|很高|很高|音频、图像、连续采样|
|DMA 链表|极低|很低|高|很高|高端 MCU、复杂数据流|

### 4.2 DMA 传输模式对比

|模式|传输完成后|缓冲区组织|优点|缺点|
|---|---|---|---|---|
|Normal|DMA 停止|单缓冲|简单、易控制|连续数据流会出现空洞|
|Circular|自动重启|环形缓冲|连续采集、低开销|需要处理覆盖和读写同步|
|Double Buffer|切换另一缓冲区|两块缓冲|CPU 与 DMA 并行处理|配置复杂、内存增加|
|Linked List|执行下一个描述符|多描述符|灵活、适合复杂流水线|调试难度高|

### 4.3 DMA 地址配置对比

|配置项|外设地址|内存地址|典型用途|
|---|---|---|---|
|外设到内存|固定|递增|ADC、UART RX、SPI RX|
|内存到外设|固定|递增|UART TX、SPI TX、DAC|
|内存到内存|递增|递增|缓冲区复制|
|外设到外设|取决于控制器|不一定需要|少数高级 DMA 支持|

### 4.4 数据宽度对比

|数据宽度|传输单位|典型用途|关键风险|
|---|---|---|---|
|8 bit|1 字节|UART、SPI 字节流|访问 16/32 位寄存器时需确认硬件要求|
|16 bit|2 字节|ADC、SPI 16 位模式|地址对齐和计数单位容易误解|
|32 bit|4 字节|内存复制、FIFO|外设寄存器不一定支持 32 位访问|

---

## 5. 底层原理与功能特性深度解析

## 5.1 DMA 的核心寄存器模型

不同厂商命名不同，但基本上包含以下寄存器：

```
DMA_CPAR   Peripheral Address Register
DMA_CMAR   Memory Address Register
DMA_CNDTR  Number of Data Register
DMA_CCR    Configuration Register
DMA_ISR    Interrupt and Status Register
DMA_IFCR   Interrupt Flag Clear Register
```

典型配置字段：

```
DMA_CCR:
    EN       DMA 使能
    TCIE     传输完成中断使能
    HTIE     半传输中断使能
    TEIE     传输错误中断使能
    DIR      传输方向
    CIRC     循环模式
    PINC     外设地址递增
    MINC     内存地址递增
    PSIZE    外设数据宽度
    MSIZE    内存数据宽度
    PL       优先级
```

DMA 启动逻辑通常为：

```
1. 关闭 DMA 通道
2. 清除旧状态标志
3. 配置外设地址
4. 配置内存地址
5. 配置传输数量
6. 配置方向、宽度、地址递增、模式
7. 配置中断
8. 使能外设 DMA 请求
9. 使能 DMA 通道
```

顺序不能随意交换。

例如：

- 未关闭 DMA 就修改地址，可能造成运行时寄存器更新失败；
- 未清除旧标志，启动后可能立即进入中断；
- 先打开外设 DMA 请求，再配置 DMA，可能造成首个数据丢失。

---

## 5.2 DMA 与外设请求的关系

DMA 通道本身不会主动知道何时搬运数据。

通常流程如下：

```
外设状态满足条件
    ↓
外设产生 DMA Request
    ↓
DMAMUX 选择对应请求源
    ↓
DMA 控制器获得总线访问权
    ↓
完成一次数据传输
    ↓
更新地址和剩余计数
```

以 UART 接收为例：

```
UART 接收到一个字节
    ↓
UART_RXNE = 1
    ↓
UART 发出 DMA 请求
    ↓
DMA 读取 UART_RDR
    ↓
DMA 写入 SRAM
    ↓
UART_RXNE 清零
    ↓
DMA 计数器减一
```

因此，如果 DMA 已经正确配置，但外设没有产生请求，DMA 仍然不会移动任何数据。

常见原因：

- 未打开 UART 的 DMA 接收请求；
- UART 波特率或 GPIO 配置错误；
- DMAMUX 请求源映射错误；
- 使用了错误的 DMA 通道；
- 外设状态标志未满足请求条件；
- DMA 通道被其他外设占用。

---

## 5.3 地址递增与数据宽度

假设：

```
uint16_t adc_buf[1024];
```

配置：

```
Peripheral Width = 16 bit
Memory Width     = 16 bit
Peripheral Inc   = Disable
Memory Inc       = Enable
Transfer Count   = 1024
```

传输地址变化：

```
外设地址：
ADC_DR → ADC_DR → ADC_DR → ...

内存地址：
adc_buf[0] → adc_buf[1] → adc_buf[2] → ...
```

内存地址每次增加：

```
ΔAddress = MemoryWidth / 8
```

即：

```
ΔAddress = 16 / 8 = 2 bytes
```

如果误配为 8 bit：

```
内存地址每次只增加 1 byte
```

可能导致：

- 数据交错；
- 高低字节覆盖；
- 缓冲区内容错位；
- 半字访问非对齐；
- 采样结果异常。

生产级约束：

```
_Static_assert(sizeof(adc_buf[0]) == 2, "ADC buffer width mismatch");
```

---

## 5.4 Normal 模式配置示例：UART DMA 发送

以下代码采用通用寄存器模型，实际项目需要替换为具体 MCU 的寄存器定义。

```
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef enum {
    DMA_OK = 0,
    DMA_ERR_PARAM = -1,
    DMA_ERR_BUSY = -2,
    DMA_ERR_STATE = -3
} dma_status_t;

typedef struct {
    volatile uint32_t CCR;
    volatile uint32_t CNDTR;
    volatile uint32_t CPAR;
    volatile uint32_t CMAR;
} dma_channel_regs_t;

typedef struct {
    volatile uint32_t CR1;
    volatile uint32_t ISR;
    volatile uint32_t RDR;
    volatile uint32_t TDR;
} uart_regs_t;

#define DMA_CCR_EN       (1u << 0)
#define DMA_CCR_TCIE     (1u << 1)
#define DMA_CCR_TEIE     (1u << 3)
#define DMA_CCR_DIR      (1u << 4)
#define DMA_CCR_MINC     (1u << 7)
#define DMA_CCR_PSIZE_8  (0u << 8)
#define DMA_CCR_MSIZE_8  (0u << 10)

#define UART_CR1_TXDMAEN (1u << 7)

typedef struct {
    dma_channel_regs_t *dma;
    uart_regs_t *uart;
    volatile bool busy;
} uart_dma_tx_t;

static uart_dma_tx_t g_uart_dma_tx;

int uart_dma_tx_start(const uint8_t *data, size_t len)
{
    if (data == NULL || len == 0u || len > 0xFFFFu) {
        return DMA_ERR_PARAM;
    }

    uart_dma_tx_t *ctx = &g_uart_dma_tx;

    if (ctx->busy) {
        return DMA_ERR_BUSY;
    }

    /*
     * 关键顺序：
     * 1. 禁止 DMA 通道
     * 2. 清理旧状态
     * 3. 配置地址和计数
     * 4. 配置控制位
     * 5. 打开 UART DMA 请求
     * 6. 最后使能 DMA
     */
    ctx->dma->CCR &= ~DMA_CCR_EN;

    /*
     * 此处必须增加：
     * - 清除 DMA TC/TE/HT 标志
     * - 等待 EN 真正清零
     * 具体方式取决于芯片参考手册。
     */

    ctx->dma->CPAR = (uint32_t)&ctx->uart->TDR;
    ctx->dma->CMAR = (uint32_t)data;
    ctx->dma->CNDTR = (uint32_t)len;

    ctx->dma->CCR =
        DMA_CCR_DIR  |
        DMA_CCR_MINC |
        DMA_CCR_PSIZE_8 |
        DMA_CCR_MSIZE_8 |
        DMA_CCR_TCIE |
        DMA_CCR_TEIE;

    ctx->busy = true;

    ctx->uart->CR1 |= UART_CR1_TXDMAEN;
    ctx->dma->CCR |= DMA_CCR_EN;

    return DMA_OK;
}
```

需要注意：

1. `data` 在 DMA 完成前必须保持有效。
2. 不能传入函数内部的临时数组。
3. 如果内存位于 Cache 区域，发送前需要执行 Clean 操作。
4. DMA 完成通常表示数据已经写入 UART 发送数据寄存器，不一定表示最后一个停止位已经从 TX 引脚发出。

---

## 5.5 DMA 完成与 UART 真正发送完成不是一回事

UART 发送链路通常为：

```
DMA 写入 TDR
    ↓
UART 将 TDR 内容装载到移位寄存器
    ↓
UART 在 TX 引脚上发送
    ↓
最后一个停止位发送完成
    ↓
TC 标志置位
```

DMA TC 的含义：

```
DMA 已经完成 N 次内存到外设寄存器的写入
```

UART TC 的含义：

```
UART 移位寄存器和发送数据寄存器都为空，线路发送结束
```

因此：

- 仅使用 DMA TC 就关闭 RS485 DE，可能截断最后一个字节；
- RS485 半双工发送完成必须等待 UART TC；
- DMA TC 适合表示“数据已全部提交给 UART”；
- UART TC 适合表示“线路上的最后一位已完成”。

典型 RS485 发送逻辑：

```
void rs485_dma_tx_complete_isr(void)
{
    /*
     * DMA TC：
     * 数据已全部写入 UART 外设。
     * 不能立即关闭 DE。
     */
    uart_enable_tc_interrupt();
}

void uart_tc_isr(void)
{
    /*
     * UART TC：
     * 最后一个停止位已经发送。
     */
    rs485_set_de(false);
    uart_disable_tc_interrupt();
    tx_complete_notify();
}
```

---

## 5.6 循环模式配置：ADC 连续采样

```
#define ADC_DMA_BUFFER_LENGTH 1024u

static uint16_t adc_dma_buffer[ADC_DMA_BUFFER_LENGTH]
    __attribute__((aligned(32)));

void adc_dma_start(void)
{
    dma_channel_regs_t *dma = get_adc_dma_channel();
    adc_regs_t *adc = get_adc_regs();

    dma->CCR &= ~DMA_CCR_EN;

    dma_clear_all_flags();

    dma->CPAR = (uint32_t)&adc->DR;
    dma->CMAR = (uint32_t)adc_dma_buffer;
    dma->CNDTR = ADC_DMA_BUFFER_LENGTH;

    dma->CCR =
        DMA_CCR_CIRC       |
        DMA_CCR_MINC       |
        DMA_CCR_TCIE       |
        DMA_CCR_HTIE       |
        DMA_CCR_TEIE       |
        DMA_CCR_PSIZE_16   |
        DMA_CCR_MSIZE_16;

    adc_enable_dma_request();
    dma->CCR |= DMA_CCR_EN;
}
```

循环缓冲的逻辑：

```
DMA 写入：
[0 ... 511]   → 半传输事件
[512 ... 1023] → 传输完成事件
重新从 [0] 开始
```

半传输和传输完成可以将一个大缓冲区拆成两个处理窗口：

```
DMA 正在写入后半区时，CPU 处理前半区
DMA 正在写入前半区时，CPU 处理后半区
```

这是连续采集系统中常见的生产级结构。

中断处理：

```
void ADC_DMA_IRQHandler(void)
{
    uint32_t status = dma_get_status();

    if ((status & DMA_FLAG_TE) != 0u) {
        dma_clear_flag(DMA_FLAG_TE);
        adc_dma_stop();
        adc_dma_error_notify();
        return;
    }

    if ((status & DMA_FLAG_HT) != 0u) {
        dma_clear_flag(DMA_FLAG_HT);

        /*
         * 仅投递事件，不在 ISR 中执行复杂算法。
         */
        adc_block_ready_notify(
            &adc_dma_buffer[0],
            ADC_DMA_BUFFER_LENGTH / 2u
        );
    }

    if ((status & DMA_FLAG_TC) != 0u) {
        dma_clear_flag(DMA_FLAG_TC);

        adc_block_ready_notify(
            &adc_dma_buffer[ADC_DMA_BUFFER_LENGTH / 2u],
            ADC_DMA_BUFFER_LENGTH / 2u
        );
    }
}
```

---

## 5.7 Cache 一致性问题

在带 D-Cache 的 Cortex-M7、Cortex-M33 高性能实现或 MPU 系统中，DMA 和 CPU 可能看到不同的数据。

### DMA 接收问题

```
DMA 写入 SRAM
CPU 读取 Cache 中的旧副本
```

解决方法：

```
SCB_InvalidateDCache_by_Addr(
    (uint32_t *)buffer,
    buffer_size
);
```

### DMA 发送问题

```
CPU 修改了 Cache 中的数据
DMA 直接读取 SRAM 中的旧数据
```

解决方法：

```
SCB_CleanDCache_by_Addr(
    (uint32_t *)buffer,
    buffer_size
);
```

### 生产级 Cache 处理函数

```
#define CACHE_LINE_SIZE 32u

static uintptr_t align_down(uintptr_t value, uintptr_t align)
{
    return value & ~(align - 1u);
}

static uintptr_t align_up(uintptr_t value, uintptr_t align)
{
    return (value + align - 1u) & ~(align - 1u);
}

void dma_cache_clean(const void *addr, size_t len)
{
    uintptr_t start;
    uintptr_t end;

    if (addr == NULL || len == 0u) {
        return;
    }

    start = align_down((uintptr_t)addr, CACHE_LINE_SIZE);
    end = align_up((uintptr_t)addr + len, CACHE_LINE_SIZE);

    SCB_CleanDCache_by_Addr(
        (uint32_t *)start,
        (int32_t)(end - start)
    );

    __DSB();
}

void dma_cache_invalidate(void *addr, size_t len)
{
    uintptr_t start;
    uintptr_t end;

    if (addr == NULL || len == 0u) {
        return;
    }

    start = align_down((uintptr_t)addr, CACHE_LINE_SIZE);
    end = align_up((uintptr_t)addr + len, CACHE_LINE_SIZE);

    __DSB();

    SCB_InvalidateDCache_by_Addr(
        (uint32_t *)start,
        (int32_t)(end - start)
    );

    __DSB();
}
```

### Cache 使用原则

|DMA 方向|DMA 前|DMA 后|
|---|---|---|
|内存到外设|Clean Cache|通常无需 Invalidate|
|外设到内存|通常无需 Clean|Invalidate Cache|
|内存到内存|源地址 Clean|目标地址 Invalidate|
|循环 DMA|每个处理块按边界维护 Cache|防止 CPU 读取旧缓存|

重要风险：

> DMA 缓冲区与其他变量共享同一个 Cache Line 时，Cache 维护可能误伤邻近变量。

建议：

- DMA 缓冲区按 Cache Line 对齐；
- 独占完整 Cache Line；
- 或将 DMA Buffer 放入非 Cache 内存区；
- 通过 MPU 配置 DMA 区域为 Non-cacheable。

---

## 6. 性能量化分析

## 6.1 CPU 搬运与 DMA 搬运的基本模型

假设：

- 数据量：`N` 字节；
- CPU 每字节搬运需要 `C_cpu` 个周期；
- DMA 启动和中断处理固定开销为 `C_dma_fixed`；
- DMA 每字节总线和控制开销为 `C_dma_byte`；
- CPU 时钟：`F_cpu`。

CPU 搬运周期：

```
T_cpu_cycles = N × C_cpu
```

DMA 占用的 CPU 周期：

```
T_dma_cpu_cycles = C_dma_fixed + C_irq
```

CPU 节省比例：

```
Saving =
1 - (C_dma_fixed + C_irq) / (N × C_cpu)
```

### 示例

假设实测：

- CPU 逐字节 UART 搬运：每字节约 42 cycles；
- DMA 启动和完成中断总开销：约 520 cycles；
- 传输长度：1024 bytes；
- CPU 频率：168 MHz。

CPU 方式：

```
1024 × 42 = 43008 cycles
```

时间：

```
43008 / 168 MHz ≈ 256 μs
```

DMA 方式：

```
CPU 参与约 520 cycles
```

时间：

```
520 / 168 MHz ≈ 3.1 μs
```

CPU 参与度下降约：

```
1 - 520 / 43008 ≈ 98.8%
```

注意：

> **DMA 不会把 UART 的物理发送时间变短。**

如果 UART 波特率为 921600 bit/s，8N1 每字节 10 bit：

```
单字节时间 = 10 / 921600 ≈ 10.85 μs
1024 字节时间 ≈ 11.11 ms
```

DMA 的优势是：

- CPU 不需要在 11.11 ms 内持续参与；
- CPU 可以执行其他任务；
- 中断数量从 1024 次降低为通常 1～2 次。

---

## 6.2 中断频率分析

逐字节中断：

```
f_irq = 数据率 / 传输单位
```

对于 UART 921600 bit/s、8N1：

```
字节率 = 921600 / 10 = 92160 bytes/s
```

逐字节中断频率：

```
f_irq ≈ 92.16 kHz
```

如果使用 256 字节 DMA：

```
f_irq ≈ 92160 / 256 ≈ 360 Hz
```

中断频率下降约：

```
92.16 kHz / 360 Hz ≈ 256 倍
```

---

## 6.3 DMA 缓冲区大小计算

对于连续数据接收，缓冲区至少应满足：

```
BufferSize ≥ DataRate × MaxServiceLatency
```

如果使用双半缓冲：

```
HalfBufferSize ≥ DataRate × MaxProcessLatency
```

示例：

- UART 数据率：92160 bytes/s；
- 最高任务调度延迟：2 ms；
- 处理任务最坏执行时间：3 ms；
- 需要额外 50% 安全裕量。

则：

```
基础半缓冲 = 92160 × 3 ms = 276.5 bytes
```

考虑安全裕量：

```
276.5 × 1.5 ≈ 415 bytes
```

选择 512 bytes 半缓冲：

```
总 DMA 缓冲区 = 2 × 512 = 1024 bytes
```

如果系统存在更高优先级中断阻塞或 RTOS 调度抖动，还应继续提高缓冲区容量。

---

## 6.4 总线带宽分析

DMA 传输带宽：

```
BW_dma = SampleRate × BytesPerSample × ChannelCount
```

ADC 示例：

- 采样率：1 MSPS；
- 每采样 16 bit；
- 4 通道。

```
BW_dma = 1,000,000 × 2 × 4
       = 8 MB/s
```

如果 MCU 总线频率为 100 MHz、每次总线传输约 1 个周期，理论最大带宽可能达到数百 MB/s，但实际还需扣除：

- CPU 指令取指；
- Flash 等待周期；
- LCD/摄像头等高优先级 DMA；
- SRAM 仲裁；
- 总线突发效率；
- 外设 FIFO 空闲间隔。

工程上不建议让 DMA 总带宽长期超过可用总线带宽的 50%～70%。

---

## 6.5 性能瓶颈与优化收益

|瓶颈|表现|优化手段|
|---|---|---|
|中断过多|CPU 占用高|增大块大小、使用半传输|
|缓冲区过小|丢包、覆盖|增大缓冲区、提高处理任务优先级|
|Cache 不一致|数据旧、数据重复|Clean/Invalidate、非 Cache 区|
|DMA 优先级过低|高速外设溢出|调高 DMA 优先级、调整请求调度|
|DMA 突发过大|CPU 延迟增加|调整 Burst、FIFO 阈值|
|内存带宽不足|外设 FIFO 溢出|放置到高速 SRAM、减少其他 DMA|
|ISR 处理过重|实时性下降|ISR 只投递事件，任务中处理|

---

## 7. 应用场景选型指南

## 7.1 纯文本决策流程图

```
是否存在连续或批量数据搬运？
├── 否
│   └── 使用 CPU 轮询或普通中断
└── 是
    ├── 数据量很小，且频率很低？
    │   └── 使用普通中断，避免 DMA 管理成本
    └── 否
        ├── 传输结束后停止即可？
        │   └── 使用 DMA Normal 模式
        └── 否
            ├── 数据流持续到来？
            │   ├── 可按固定块处理？
            │   │   └── 使用 DMA Circular + HT/TC
            │   └── 处理时间不确定或数据块切换复杂？
            │       └── 使用 DMA Double Buffer
            └── 否
                ├── 是否需要多个不同地址/长度的连续传输？
                │   └── 使用 Linked List / Scatter-Gather
                └── 否
                    └── 使用 DMA Normal
```

## 7.2 典型场景选型

|场景需求|推荐方案|理由|
|---|---|---|
|UART 发送一帧日志|DMA Normal|发送完成后停止，结构简单|
|UART 持续接收协议帧|DMA Circular + IDLE|降低中断频率，适配不定长帧|
|ADC 连续采集|DMA Circular + HT/TC|双半区流水处理|
|SPI 发送固定命令|DMA Normal|批量发送，CPU 只处理完成事件|
|SPI 全双工采集|TX/RX 双 DMA|保持收发同步|
|DAC 输出波形|DMA Circular|周期性重复输出|
|图像帧搬运|DMA Double Buffer|采集和算法处理并行|
|多段非连续内存传输|Linked List|避免 CPU 频繁重配 DMA|
|小于 4～8 字节的控制命令|CPU 中断|DMA 配置成本可能高于收益|

---

## 8. 工程最佳实践

## 8.1 设计原则

### 原则一：DMA 是驱动的一部分，不是简单配置项

生产级 DMA 驱动至少应包含：

- 参数校验；
- 状态管理；
- 启动、停止、取消；
- 完成回调；
- 错误回调；
- 超时处理；
- 并发保护；
- Cache 一致性；
- 调试统计；
- 故障恢复。

### 原则二：所有 DMA 缓冲区必须有明确生命周期

错误：

```
void send_packet(void)
{
    uint8_t packet[64];

    build_packet(packet);
    uart_dma_tx_start(packet, sizeof(packet));
}
```

函数退出后 `packet` 失效，DMA 仍可能访问该区域。

正确：

```
static uint8_t tx_packet[64];

void send_packet(void)
{
    build_packet(tx_packet);
    uart_dma_tx_start(tx_packet, sizeof(tx_packet));
}
```

### 原则三：禁止在 DMA 活动期间修改关键配置

除非芯片明确支持动态修改，否则以下操作应在 DMA 禁止时完成：

- 地址；
- 传输计数；
- 数据宽度；
- 传输方向；
- 循环模式；
- 优先级。

### 原则四：ISR 中不做复杂处理

DMA ISR 应尽量只做：

```
读取状态
清除标志
记录错误
切换缓冲区
投递事件
```

不要在 ISR 中：

- 解析完整协议；
- 执行浮点滤波；
- 调用阻塞 API；
- 访问文件系统；
- 获取不确定延迟的互斥锁。

---

## 8.2 DMA 选型决策矩阵

|需求维度|低要求|中要求|高要求|
|---|---|---|---|
|数据率|CPU 中断|DMA Normal|DMA Circular/Double Buffer|
|连续性|单帧|分块|Ping-Pong/链表|
|CPU 负载|可接受|需要降低|极低|
|实时性|普通|较高|硬实时|
|Cache 复杂度|无 Cache|可控|MPU/非 Cache 区|
|资源消耗|低|中|高|
|调试难度|低|中|高|

---

## 8.3 工业级编码规范

1. DMA 缓冲区使用固定宽度类型：

```
uint8_t
uint16_t
uint32_t
```

2. 所有 DMA 长度使用 `size_t` 接收，再转换前检查硬件计数器上限。
3. DMA 共享状态使用 `volatile`，但 `volatile` 不等于线程安全。
4. 使用明确状态机：

```
typedef enum {
    DMA_STATE_IDLE,
    DMA_STATE_RUNNING,
    DMA_STATE_COMPLETE,
    DMA_STATE_ERROR,
    DMA_STATE_ABORTED
} dma_state_t;
```

5. ISR 与任务之间使用：

- 原子变量；
- 二值信号量；
- 事件组；
- 无锁环形队列；
- 消息队列。

6. 记录以下诊断数据：

```
typedef struct {
    uint32_t start_count;
    uint32_t complete_count;
    uint32_t error_count;
    uint32_t abort_count;
    uint32_t overflow_count;
    uint32_t max_latency_us;
} dma_statistics_t;
```

---

## 9. 常见错误与避坑指南

## 9.1 错误一：DMA 缓冲区使用局部变量

### 错误代码

```
void uart_send(void)
{
    uint8_t data[32] = "hello";

    uart_dma_tx_start(data, 5);
}
```

### 根因

函数退出后，栈空间可能被其他函数覆盖，DMA 使用悬空指针。

### 正确实现

```
static uint8_t tx_data[32];

void uart_send(void)
{
    tx_data[0] = 'h';
    tx_data[1] = 'e';
    tx_data[2] = 'l';
    tx_data[3] = 'l';
    tx_data[4] = 'o';

    uart_dma_tx_start(tx_data, 5);
}
```

### 风险影响

- 数据随机错误；
- 仅在优化打开时出现；
- 调试版本正常、发布版本异常；
- 现场难以复现。

---

## 9.2 错误二：未清除旧 DMA 标志

### 错误代码

```
dma->CCR &= ~DMA_CCR_EN;
dma->CPAR = peripheral_addr;
dma->CMAR = memory_addr;
dma->CNDTR = length;
dma->CCR |= DMA_CCR_EN;
```

### 根因

上一次传输的 TC 或 TE 标志未清除，启动后立即触发中断。

### 正确实现

```
dma->CCR &= ~DMA_CCR_EN;

while ((dma->CCR & DMA_CCR_EN) != 0u) {
    /* 等待硬件完成关闭 */
}

dma_clear_all_flags();

dma->CPAR = peripheral_addr;
dma->CMAR = memory_addr;
dma->CNDTR = length;
dma->CCR = config;
dma->CCR |= DMA_CCR_EN;
```

### 风险影响

- 误判传输完成；
- 状态机提前进入空闲；
- 首次传输失败；
- 中断风暴。

---

## 9.3 错误三：DMA 数据宽度不匹配

### 错误代码

```
uint16_t adc_buf[256];

dma_config_memory_width(DMA_WIDTH_8BIT);
dma_config_peripheral_width(DMA_WIDTH_16BIT);
```

### 根因

内存端按字节搬运，C 代码按半字解释，导致地址步长和数据排列不一致。

### 正确实现

```
_Static_assert(sizeof(uint16_t) == 2u, "Unexpected uint16_t size");

dma_config_memory_width(DMA_WIDTH_16BIT);
dma_config_peripheral_width(DMA_WIDTH_16BIT);
```

### 风险影响

- ADC 结果错位；
- 高低字节异常；
- 缓冲区有效长度计算错误；
- 非对齐访问异常。

---

## 9.4 错误四：只等待 DMA TC，不等待 UART TC

### 错误代码

```
void dma_tx_done_callback(void)
{
    rs485_set_de(false);
}
```

### 根因

DMA TC 只说明最后一个字节已写入 UART 数据寄存器，UART 可能仍在移位发送。

### 正确实现

```
void dma_tx_done_callback(void)
{
    uart_enable_transmission_complete_interrupt();
}

void uart_tc_callback(void)
{
    uart_disable_transmission_complete_interrupt();
    rs485_set_de(false);
}
```

### 风险影响

- RS485 最后一个字节被截断；
- CRC 错误；
- 从站偶发不响应；
- 低波特率下更明显。

---

## 9.5 错误五：忽略 Cache 一致性

### 错误代码

```
memcpy(tx_buffer, packet, packet_len);
dma_start_memory_to_peripheral(tx_buffer, packet_len);
```

### 根因

CPU 修改的数据仍在 D-Cache 中，DMA 从 SRAM 读取旧内容。

### 正确实现

```
memcpy(tx_buffer, packet, packet_len);

dma_cache_clean(tx_buffer, packet_len);

dma_start_memory_to_peripheral(tx_buffer, packet_len);
```

### 风险影响

- 发送旧数据；
- 数据偶发正确；
- 仅在高性能 MCU 上出现；
- 开启 Cache 后问题出现。

---

## 9.6 错误六：循环 DMA 中 CPU 处理速度不足

### 错误代码

```
void dma_half_callback(void)
{
    process_samples(&buffer[0], 512);
}

void dma_complete_callback(void)
{
    process_samples(&buffer[512], 512);
}
```

如果 `process_samples()` 的最坏执行时间大于 DMA 填满半区的时间，就会覆盖尚未处理的数据。

### 根因

处理吞吐低于采集吞吐：

```
CPU Processing Time > DMA Buffer Refill Time
```

### 正确实现

- 增大缓冲区；
- 使用更高优先级处理任务；
- 降低采样率；
- 使用 DSP 硬件；
- 分阶段处理；
- 使用双缓冲或多缓冲。

### 风险影响

- 数据块丢失；
- 频谱分析出现断裂；
- 采样序列不连续；
- 故障只在高负载场景出现。

---

## 10. 多机制组合使用方案

## 10.1 UART DMA Circular + IDLE + Ring Buffer

这是工业通信中常见的高可靠接收架构。

```
UART RX
  ↓
DMA Circular Buffer
  ↓
DMA HT/TC 或 UART IDLE
  ↓
计算 DMA 当前写指针
  ↓
复制到软件 Ring Buffer
  ↓
协议解析任务
```

核心思想：

- DMA 负责连续写入；
- UART IDLE 用于识别一帧间隔；
- 软件环形缓冲区负责跨任务解耦；
- 协议解析任务不直接操作 DMA 当前写入区。

### 环形缓冲区框架

```
#define RX_DMA_SIZE 256u
#define RX_RING_SIZE 1024u

static uint8_t rx_dma_buf[RX_DMA_SIZE];
static uint8_t rx_ring_buf[RX_RING_SIZE];

static volatile size_t dma_last_pos;
static volatile size_t ring_head;
static volatile size_t ring_tail;

static bool ring_push_byte(uint8_t data)
{
    size_t next = (ring_head + 1u) % RX_RING_SIZE;

    if (next == ring_tail) {
        return false;
    }

    rx_ring_buf[ring_head] = data;
    ring_head = next;
    return true;
}

void uart_rx_dma_event(void)
{
    size_t current_pos;
    size_t pos;

    /*
     * NDTR 是剩余数量，DMA 写指针可由此计算。
     */
    current_pos = RX_DMA_SIZE - dma_get_remaining_count();
    current_pos %= RX_DMA_SIZE;

    pos = dma_last_pos;

    while (pos != current_pos) {
        if (!ring_push_byte(rx_dma_buf[pos])) {
            rx_overflow_record();
            break;
        }

        pos++;
        if (pos >= RX_DMA_SIZE) {
            pos = 0u;
        }
    }

    dma_last_pos = current_pos;
    protocol_parser_notify();
}
```

工程注意事项：

- 读取 `NDTR` 时要了解芯片是否允许运行时安全读取；
- 某些 DMA 控制器存在寄存器读取时序要求；
- DMA 缓冲区和软件 Ring Buffer 不应混为一体；
- Ring Buffer 满时必须有明确策略：丢新、丢旧、阻塞或复位协议。

---

## 10.2 ADC DMA + Ping-Pong + RTOS 任务

```
ADC 触发器
    ↓
DMA Buffer A/B
    ↓
半传输/全传输事件
    ↓
ISR 投递 buffer_ready 事件
    ↓
高优先级处理任务
    ↓
滤波 / FFT / 控制算法
```

事件结构：

```
typedef struct {
    uint16_t *buffer;
    size_t length;
    uint32_t timestamp;
} adc_block_event_t;
```

ISR 中：

```
void adc_dma_half_isr(void)
{
    adc_block_event_t event = {
        .buffer = &adc_buffer[0],
        .length = ADC_HALF_SIZE,
        .timestamp = timer_get_us()
    };

    BaseType_t higher_priority_woken = pdFALSE;

    xQueueSendFromISR(
        adc_queue,
        &event,
        &higher_priority_woken
    );

    portYIELD_FROM_ISR(higher_priority_woken);
}
```

任务中：

```
void adc_processing_task(void *argument)
{
    adc_block_event_t event;

    for (;;) {
        if (xQueueReceive(adc_queue, &event, portMAX_DELAY) == pdTRUE) {
            dma_cache_invalidate(event.buffer,
                                 event.length * sizeof(uint16_t));

            process_adc_block(event.buffer, event.length);
        }
    }
}
```

关键设计点：

- DMA 缓冲区不能在任务处理完成前被重新使用；
- 如果 DMA 循环速度过快，单纯双半区可能不够；
- 高负载系统应采用多缓冲队列或预留多个块；
- 事件队列必须有溢出统计。

---

## 11. 工业级实际案例分析

## 11.1 案例一：RS485 Modbus RTU 从站

### 需求

- 波特率：115200；
- 帧长度：最大 256 字节；
- 帧间隔检测：3.5 个字符时间；
- CPU 运行 RTOS；
- 要求不能因其他任务阻塞造成接收丢帧。

### 架构设计

```
UART RX DMA Circular
        ↓
UART IDLE 中断
        ↓
计算 DMA 写位置
        ↓
Ring Buffer
        ↓
Modbus Parser Task
        ↓
CRC + 地址 + 功能码解析
```

### 设计要点

1. UART RX 使用 DMA Circular。
2. UART IDLE 只作为“可能一帧结束”的提示。
3. 不能简单认为一次 IDLE 就一定是完整合法帧。
4. Modbus RTU 仍需结合长度、CRC 和协议超时判断。
5. RS485 DE 控制必须等待 UART TC，而不是 DMA TC。

### 关键参数

115200、8N1 时：

```
每字符约 10 bit
字符时间 ≈ 10 / 115200 ≈ 86.8 μs
3.5 字符时间 ≈ 304 μs
```

系统应确保：

```
DMA 缓冲区容量 > 最长帧长度 + 调度延迟期间接收的数据
```

---

## 11.2 案例二：多通道 ADC 电机电流采样

### 需求

- ADC 采样率：2 MSPS；
- 4 通道；
- 每个采样点 16 bit；
- 使用 DMA 连续采样；
- 每 256 个采样点执行一次电流环计算；
- 电流环周期必须稳定。

### 带宽计算

```
BW = 2,000,000 × 2 × 4
   = 16 MB/s
```

### 架构

```
定时器 TRGO
    ↓
ADC 多通道扫描
    ↓
DMA Circular
    ↓
HT/TC 中断
    ↓
实时控制任务
    ↓
电流校准、滤波、PI 控制
```

### 设计要点

- ADC 由定时器触发，不能依赖软件启动；
- DMA 数据宽度设置为 16 bit；
- 缓冲区按 Cache Line 对齐；
- HT/TC 事件只允许一次投递；
- 控制任务优先级高于普通通信任务；
- 处理时间必须小于半缓冲填充时间。

半缓冲填充时间：

```
256 samples / 2,000,000 samples/s
= 128 μs
```

如果电流环处理最坏执行时间为 90 μs，则理论剩余裕量：

```
128 - 90 = 38 μs
```

但还要考虑：

- 高优先级中断；
- Cache 维护；
- RTOS 调度；
- 总线争用。

工程上建议处理时间控制在半缓冲填充时间的 50%～70% 以内。

---

## 11.3 案例三：SPI 传感器批量采集

### 需求

- SPI 频率：20 MHz；
- 一次读取 512 字节；
- 每 10 ms 采集一次；
- 需要同时发送命令并接收数据；
- 不允许 CPU 忙等。

### 架构

```
SPI TX DMA ─┐
             ├── SPI 全双工传输
SPI RX DMA ─┘
        ↓
RX DMA 完成
        ↓
校验、解析和时间戳处理
```

### 关键问题

SPI 全双工必须同时处理 TX 和 RX：

- 只配置 TX DMA，RX 数据可能溢出；
- 只配置 RX DMA，SPI 时钟可能无法产生；
- 必须保证 TX/RX DMA 长度一致；
- CS 拉低、DMA 启动、SPI 启动顺序必须符合芯片手册要求。

典型流程：

```
拉低 CS
配置 RX DMA
配置 TX DMA
清除 SPI/DMA 状态
使能 SPI DMA 请求
启动 SPI
等待 RX DMA 完成
等待 SPI BSY 清零
拉高 CS
```

---

## 12. 高频问题深度答疑

## 问题一：DMA 一定比 CPU 搬运快吗？

不一定。

DMA 优势是减少 CPU 参与，而不是保证单次传输延迟更低。

对于极小数据块：

```
DMA 初始化成本 > CPU 直接搬运成本
```

例如仅传输 2～4 字节，DMA 配置、启动和中断处理的固定开销可能高于 CPU 直接写寄存器。

建议：

- 小块低频数据：CPU；
- 中等块或高频数据：DMA；
- 连续数据流：DMA Circular/Double Buffer。

---

## 问题二：DMA 传输完成后，数据一定已经到达物理引脚吗？

不一定。

以 UART 为例：

- DMA TC：最后一个字节已写入 UART TDR；
- UART TC：最后一个停止位已经发送完成。

以 SPI 为例：

- DMA TC：最后一个数据寄存器访问完成；
- SPI BSY 清零：SPI 总线传输真正结束。

因此，关闭片选、释放总线或切换收发方向时，应等待外设自身的完成标志。

---

## 问题三：为什么 DMA 缓冲区数据看起来会“倒退”或“重复”？

常见原因：

1. Cache 未失效；
2. 循环 DMA 正在覆盖 CPU 尚未处理的数据；
3. CPU 和 DMA 同时访问同一 Cache Line；
4. DMA 位置计算错误；
5. `NDTR` 在运行时读取时发生边界竞争；
6. 软件环形缓冲区的 head/tail 管理错误。

排查顺序：

```
检查 DMA 状态
→ 检查当前写指针
→ 检查 Cache
→ 检查缓冲区覆盖
→ 检查并发同步
```

---

## 问题四：DMA 优先级越高越好吗？

不是。

DMA 优先级过高可能导致：

- CPU 访问 SRAM 延迟上升；
- 其他 DMA 通道长期得不到总线；
- 实时控制任务执行抖动；
- 总线突发阻塞。

优先级应根据数据丢失风险和截止时间设计：

```
不能丢数据的高速采集 > 普通日志发送
硬实时控制反馈 > 低优先级图像搬运
```

---

## 问题五：为什么 UART DMA 接收仍然会丢数据？

可能原因：

1. DMA 缓冲区太小；
2. CPU 处理延迟超过缓冲区覆盖时间；
3. UART 溢出错误未清除；
4. IDLE 中断处理逻辑错误；
5. DMA 通道被意外关闭；
6. Ring Buffer 满；
7. 中断优先级配置不合理；
8. 读取 UART 状态寄存器顺序错误。

核心判断公式：

```
可容忍延迟 ≤ 缓冲区可承载字节数 / 数据率
```

如果 UART 字节率为 92.16 KB/s，DMA 缓冲区剩余 128 字节：

```
可容忍时间 ≈ 128 / 92160 ≈ 1.39 ms
```

系统必须在 1.39 ms 内完成数据转移或处理。

---

## 问题六：DMA 与 RTOS 如何安全协同？

推荐结构：

```
DMA ISR
    ├── 清状态
    ├── 保存错误信息
    ├── 固定时间切换缓冲区
    └── 投递信号量/队列
        ↓
RTOS 任务
    ├── 执行数据处理
    ├── Cache 维护
    ├── 协议解析
    └── 错误恢复
```

不要：

- 在 ISR 中等待 DMA；
- 在 ISR 中调用普通阻塞队列 API；
- 在 DMA 回调中申请不确定时延的内存；
- 让多个任务直接操作同一个 DMA 通道。

---

## 13. 课程核心总结

### 核心要点

1. **DMA 的本质是硬件驱动的总线数据搬运。**
    
2. DMA 不消除总线带宽消耗，只减少 CPU 指令参与。
    
3. 基本配置必须正确处理：
    
    - 方向；
    - 外设地址；
    - 内存地址；
    - 数据宽度；
    - 地址递增；
    - 传输数量；
    - 循环模式；
    - 中断；
    - 请求源。
4. DMA 完成不等于外设物理传输完成。
    
5. 带 Cache 的系统必须处理内存一致性。
    
6. 连续数据流优先考虑：
    
    - Circular；
    - Half Transfer；
    - Double Buffer；
    - Ring Buffer。
7. DMA 驱动必须包含错误处理、超时、取消和状态管理。
    
8. 缓冲区大小必须根据数据率和最坏服务延迟量化计算。
    

### 性能排序

从 CPU 负载最高到最低：

```
轮询 > 逐字节中断 > DMA 单次 > DMA 循环 > DMA 双缓冲 > DMA 链表
```

从实现简单到复杂：

```
轮询 < 普通中断 < DMA Normal < DMA Circular < DMA Double Buffer < Linked List
```

### 通用选型结论

|场景|结论|
|---|---|
|小数据、低频率|CPU 或普通中断|
|中等批量数据|DMA Normal|
|连续固定速率数据|DMA Circular|
|连续数据且 CPU 需要并行处理|DMA Double Buffer|
|多段复杂搬运|Linked List|
|高性能 MCU 开启 Cache|必须设计 Cache 一致性方案|

---

## 14. 快速参考速查表

### 14.1 场景选型表

|场景|DMA 方向|模式|地址配置|典型事件|
|---|---|---|---|---|
|UART TX|内存→外设|Normal|内存递增、外设固定|TC|
|UART RX|外设→内存|Circular|内存递增、外设固定|IDLE、HT、TC|
|SPI TX|内存→外设|Normal|内存递增、外设固定|TC|
|SPI RX|外设→内存|Normal/Circular|内存递增、外设固定|TC|
|ADC|外设→内存|Circular|内存递增、外设固定|HT、TC|
|DAC|内存→外设|Circular|内存递增、外设固定|HT、TC|
|内存复制|内存→内存|Normal|源递增、目的递增|TC|

### 14.2 DMA 基本配置表

|配置项|外设到内存|内存到外设|
|---|---|---|
|方向|Peripheral → Memory|Memory → Peripheral|
|外设地址|固定|固定|
|内存地址|递增|递增|
|外设宽度|与寄存器匹配|与寄存器匹配|
|内存宽度|与缓冲区元素匹配|与缓冲区元素匹配|
|Normal|单次接收|单次发送|
|Circular|连续接收|周期输出|
|Cache|接收后 Invalidate|发送前 Clean|

### 14.3 DMA 启动检查清单

```
[ ] DMA 时钟已打开
[ ] 外设时钟已打开
[ ] DMA 请求源映射正确
[ ] DMA 通道未被其他外设占用
[ ] DMA 已关闭后再修改配置
[ ] 旧状态标志已清除
[ ] 外设地址正确
[ ] 内存地址有效且生命周期足够
[ ] 传输长度未超出硬件计数器范围
[ ] 数据宽度与缓冲区类型一致
[ ] 地址递增配置正确
[ ] 外设 DMA 请求已打开
[ ] DMA 中断优先级合理
[ ] Cache 一致性已处理
[ ] 完成、错误、超时路径已实现
```

---

## 15. 学习效果自检

完成本课后，应能够回答以下问题：

### 基础能力

- [ ]  DMA 与 CPU 逐字节搬运的本质区别是什么？
- [ ]  Peripheral-to-Memory 和 Memory-to-Peripheral 如何区分？
- [ ]  外设地址为什么通常不递增？
- [ ]  DMA 传输数量的单位是字节还是数据单元？
- [ ]  8 bit、16 bit、32 bit 宽度如何影响地址步长？

### 配置能力

- [ ]  能否独立配置 UART TX DMA？
- [ ]  能否独立配置 ADC Circular DMA？
- [ ]  能否正确清除 DMA 状态标志？
- [ ]  能否处理 DMA TC、HT、TE 三类事件？
- [ ]  能否实现 DMA 取消和超时恢复？

### 工程能力

- [ ]  能否解释 DMA TC 与 UART TC 的区别？
- [ ]  能否计算连续接收所需缓冲区大小？
- [ ]  能否处理 D-Cache 与 DMA 的数据一致性？
- [ ]  能否判断循环 DMA 是否存在覆盖风险？
- [ ]  能否设计 DMA ISR 与 RTOS 任务之间的事件传递机制？

### 故障定位能力

- [ ]  DMA 不动时，能否从请求源、通道、外设标志、使能顺序逐项排查？
- [ ]  数据错位时，能否检查数据宽度和地址对齐？
- [ ]  偶发旧数据时，能否检查 Cache？
- [ ]  RS485 末字节丢失时，能否检查 UART TC？
- [ ]  高负载丢包时，能否用数据率和延迟计算缓冲区裕量？

---

## 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：UART TX DMA

要求：

- 发送固定长度数据；
- 支持 Busy 状态；
- 支持完成回调；
- 支持错误回调；
- 使用逻辑分析仪验证波形；
- 对比 CPU 发送和 DMA 发送的 CPU 占用。

验收指标：

```
[ ] 数据内容正确
[ ] 不允许重复启动
[ ] DMA TC 可正确触发
[ ] UART TC 可正确识别
[ ] 支持取消发送
```

### 任务二：ADC Circular DMA

要求：

- 配置 2 个 ADC 通道；
- 使用 16 bit DMA；
- 采集 1024 个样本；
- 使用 HT/TC 分别处理前后半区；
- 统计处理耗时和最大延迟。

验收指标：

```
[ ] 样本无错位
[ ] 无数据覆盖
[ ] HT/TC 事件顺序正确
[ ] 处理时间小于半缓冲填充时间
```

### 任务三：UART DMA Circular + IDLE

要求：

- 支持不定长帧；
- 使用 DMA Circular；
- 使用 UART IDLE 检测帧间隔；
- 设计 Ring Buffer；
- 处理 Ring Buffer 满和协议异常。

验收指标：

```
[ ] 连续帧不丢失
[ ] 长帧正确处理
[ ] Ring Buffer 溢出可统计
[ ] 可恢复非法帧
```

### 任务四：SPI 双 DMA

要求：

- 同时配置 TX DMA 和 RX DMA；
- 实现全双工传输；
- 校验 CS、DMA TC、SPI BSY 的时序；
- 在不同 SPI 频率下测试稳定性。

---

## 16.2 性能测试方法

### CPU 占用测试

使用 DWT CYCCNT：

```
uint32_t start = DWT->CYCCNT;

dma_start_transfer();

uint32_t end = DWT->CYCCNT;
uint32_t cycles = end - start;
```

应分别统计：

- DMA 启动开销；
- DMA ISR 开销；
- 数据处理开销；
- Cache 维护开销；
- 总 CPU 周期。

### 吞吐测试

测试变量：

```
数据长度：
8 / 32 / 128 / 512 / 1024 / 4096 bytes

传输方式：
CPU / 中断 / DMA Normal / DMA Circular

指标：
总耗时
CPU 占用
中断次数
最大延迟
错误率
```

### 压力测试

同时开启：

- UART 高速收发；
- ADC 连续采样；
- SPI 周期传输；
- RTOS 高负载任务；
- Cache；
- Flash 访问；
- 多 DMA 通道并发。

重点观察：

- DMA TE；
- 外设 OVR；
- UART ORE；
- 缓冲区覆盖；
- 中断延迟；
- 任务调度抖动；
- 总线占用率。

---

## 16.3 进阶学习方向

1. **DMA 与 Cache/MPU**
    
    - Non-cacheable 区域；
    - Shareable 属性；
    - Cache Line 伪共享；
    - 内存屏障；
    - DMA 缓冲区内存布局。
2. **DMA 与总线矩阵**
    
    - AHB/APB/AXI；
    - 总线仲裁；
    - Burst；
    - FIFO；
    - QoS；
    - 多主设备竞争。
3. **双缓冲与多缓冲**
    
    - Ping-Pong Buffer；
    - 三缓冲；
    - 无锁数据交接；
    - 数据块生命周期管理。
4. **高端 DMA 架构**
    
    - DMAMUX；
    - Scatter-Gather；
    - Linked List；
    - Descriptor Ring；
    - 二维传输；
    - 外设触发链。
5. **实时系统协同**
    
    - DMA ISR 与 RTOS；
    - 零拷贝；
    - 事件驱动；
    - 优先级反转；
    - 数据流背压；
    - 端到端延迟分析。
6. **工业级验证**
    
    - DMA 错误注入；
    - 总线压力测试；
    - 随机长度测试；
    - Cache 开关对比；
    - 长时间 soak test；
    - 断电、复位和异常恢复测试。

本课的核心工程结论是：

> **DMA 基本配置不是简单地打开一个通道，而是要同时保证请求源、地址、数据宽度、缓冲区生命周期、完成语义、Cache 一致性和实时处理能力全部闭环。**