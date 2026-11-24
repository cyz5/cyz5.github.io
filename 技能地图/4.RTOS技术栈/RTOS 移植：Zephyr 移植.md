
> 本课以 **Zephyr 3.x/4.x、Cortex-M、GCC/Clang、west + CMake + Devicetree + Kconfig** 为主线。Zephyr 的移植方式与 FreeRTOS、RT-Thread、embOS 有明显差异：大多数常见 CPU 架构已经有官方调度器和上下文切换实现，新增 MCU/开发板时，重点通常是 **SoC 支持、Devicetree、Kconfig、启动代码、时钟、系统定时器、串口控制台、Flash 和构建系统**，而不是直接重写 RTOS 内核。

**注意：** Zephyr 的内部符号、目录结构和设备驱动 API 会随版本演进。涉及 `arch` 内部接口、系统计时器驱动、初始化级别和 Devicetree binding 时，应以当前 Zephyr 版本源码和官方文档为准。

---

# 1. 学习目标

## 理解

- 理解 Zephyr 的内核、架构层、SoC 层、Board 层、Devicetree、Kconfig 和驱动模型之间的职责边界。
- 理解 Zephyr 的 `west`、CMake、Kconfig、Devicetree 四者如何共同生成最终固件。
- 理解 Cortex-M 上线程栈、异常入口、PendSV、SysTick/硬件定时器以及中断上下文之间的关系。
- 理解 Zephyr 的设备模型、设备树实例化、驱动初始化和设备就绪状态。
- 理解 Zephyr 与传统“复制一个 BSP 后修改”的 RTOS 移植模式之间的差异。

## 掌握

- 能基于现有 SoC 或相近 Board 创建 Zephyr Board。
- 能编写和维护 `board.yml`、Board DTS、Kconfig、Kconfig.defconfig、CMakeLists 和 `board.cmake`。
- 能使用 `west build`、`west flash`、`west debug` 和 `menuconfig` 完成构建、下载和配置验证。
- 能完成 GPIO、UART、系统时钟、Flash、控制台和系统 Tick 的基础移植。
- 能正确使用 Zephyr 的线程、信号量、消息队列、工作队列和设备 API。
- 能利用 Devicetree overlay 和 Kconfig fragment 进行产品级硬件变体管理。

## 精通

- 能通过生成的 Devicetree、Kconfig、map 文件和 ELF 符号定位启动失败、设备未就绪、配置未生效和链接空间不足。
- 能分析 Zephyr 的中断延迟、调度延迟、系统 Tick、线程栈、内核对象和内存池消耗。
- 能处理 Cortex-M7 Cache、DMA、MPU、TrustZone-M、低功耗和多镜像启动问题。
- 能设计符合 Zephyr 上游风格的 SoC、Board 和驱动支持，避免将板级代码硬编码到应用中。

## 能够设计

- 能从零建立可上游维护的 Zephyr Board 支持包。
- 能设计 Board、SoC、Shield、应用 overlay 和产品配置的分层模型。
- 能为高实时、高吞吐、低功耗和安全启动产品制定 Zephyr 移植验收标准。
- 能建立 Zephyr 版本、模块、工具链、镜像和第三方组件的可复现构建流程。

---

# 2. 前置要求

## 知识要求

### 嵌入式底层

- Cortex-M 异常模型。
- MSP、PSP、异常自动压栈。
- PendSV、SysTick、NVIC 和 `EXC_RETURN`。
- 启动文件、向量表、VTOR、链接脚本。
- ARM ABI、栈对齐和 FPU ABI。
- 芯片时钟树、复位控制和低功耗模式。

### RTOS

- 抢占式调度。
- 线程状态和阻塞/唤醒。
- 优先级和时间片。
- 信号量、互斥量、消息队列、事件。
- 中断上下文与线程上下文差异。
- 优先级反转、死锁和临界区。

### Zephyr 工程体系

- CMake 基础。
- Kconfig 配置系统。
- Devicetree 语法和节点结构。
- west 工作区和模块管理。
- ELF、map 文件和 Ninja 构建流程。

## 技能要求

- 能使用 `west build -t menuconfig` 和 `west build -t guiconfig`。
- 能查看 `build/zephyr/.config`。
- 能查看 `build/zephyr/zephyr.dts`。
- 能通过 `devicetree_generated.h` 检查宏展开结果。
- 能用 `nm`、`objdump`、`readelf` 分析 ELF。
- 能使用 J-Link、CMSIS-DAP 或厂商调试器。
- 能使用逻辑分析仪和 DWT 周期计数器测量时序。

---

# 3. 技术概述

## 3.1 Zephyr 的系统分层

```
应用层
  ├── src/
  ├── prj.conf
  ├── app.overlay
  └── sysbuild/多镜像配置

Zephyr 内核和子系统
  ├── kernel/
  ├── subsys/
  ├── drivers/
  ├── lib/
  ├── net/
  └── fs/

架构层
  ├── arch/arm/
  ├── arch/riscv/
  ├── 上下文切换
  ├── 异常入口
  ├── 原子操作
  └── 系统计时器接口

SoC 层
  ├── soc/arm/<vendor>/<family>/
  ├── 时钟和复位
  ├── SoC 启动
  ├── 中断控制器
  └── 芯片特有外设定义

Board 层
  ├── boards/<arch>/<board>/
  ├── Board DTS
  ├── Kconfig
  ├── Board CMake
  ├── Flash/debug runner
  └── 板级默认配置

工具和模块
  ├── west
  ├── CMake
  ├── Kconfig
  ├── Devicetree
  └── 外部模块
```

## 3.2 Zephyr 移植的三个典型层次

### 层次一：已有 SoC，新增开发板

这是最常见、风险最低的方式。

需要完成：

```
Board DTS
Board Kconfig
Kconfig.defconfig
CMakeLists.txt
board.yml
board.cmake
调试/下载 runner 配置
```

此时通常不需要修改架构层和 SoC 层。

### 层次二：已有 CPU 架构，新增 SoC

需要额外完成：

```
SoC 启动和初始化
SoC Kconfig
SoC DTSI
时钟控制器
复位控制
中断控制器
系统定时器
Flash/Pinmux 等基础外设
```

### 层次三：新增 CPU 架构

需要实现或适配：

```
上下文切换
异常入口
中断控制
系统调用
原子操作
线程栈初始化
系统时钟
编译器和链接约定
```

这是最高风险的路径。对于商业产品，应优先评估是否可以使用 Zephyr 已支持的架构或由芯片供应商提供支持。

## 3.3 Zephyr 的四个配置源

Zephyr 最终配置通常来自四类输入：

|配置源|作用|
|---|---|
|`prj.conf`|应用级 Kconfig 配置|
|Board `defconfig`|板级默认配置|
|SoC/架构 Kconfig|芯片和架构能力配置|
|Devicetree|硬件描述、外设实例、引脚和中断|

关键区别：

- **Kconfig 决定软件功能是否编译和启用。**
- **Devicetree 描述硬件实例、地址、中断、引脚和状态。**
- Kconfig 不能替代 Devicetree。
- Devicetree 也不能替代驱动所需的 Kconfig 选项。

---

# 4. 核心特性横向对比

## 4.1 不同 Zephyr 移植路径

|路径|适用场景|工作量|主要风险|
|---|---|---|---|
|复制同芯片 Board|同一 MCU、不同板卡|低|引脚、晶振、Flash、LED/按键差异|
|新增 Board，复用 SoC|新开发板、已有 SoC|中|DTS、启动、调试和默认配置|
|新增 SoC|Zephyr 尚未支持芯片系列|高|时钟、中断、计时器和启动|
|新增架构|新 CPU ISA|很高|上下文切换和系统调用|
|仅应用 overlay|硬件与现有 Board 高度兼容|很低|不能表达真正的板级差异|
|使用外部 Module|芯片厂商私有支持或产品闭源驱动|中|版本、路径和上游兼容性|

## 4.2 Devicetree 与 Kconfig 的职责对比

|问题|Devicetree|Kconfig|
|---|---|---|
|UART 实例地址|是|否|
|GPIO 引脚|是|否|
|UART 驱动是否编译|否|是|
|是否启用 Shell|否|是|
|SPI 总线上的设备|是|否|
|是否启用 SPI 子系统|否|是|
|中断号和触发方式|是|通常否|
|线程数量/栈大小|否|是|
|芯片是否有某外设|通常由 DTS 和 SoC 描述|可用 Kconfig 限制能力|

## 4.3 系统时基方案对比

|方案|优点|风险|适用场景|
|---|---|---|---|
|SysTick|Cortex-M 通用、配置简单|低功耗和多功能复用受限|常规 MCU|
|通用定时器|可与低功耗/硬件功能结合|定时器资源竞争|需要独立时基|
|低功耗定时器|支持睡眠计时|分辨率和频率较低|电池设备|
|Cycle counter|高分辨率|不能作为长期 Tick，低功耗时停止|性能测量|
|硬件事件驱动|减少 Tick 开销|实现复杂|高性能、低功耗系统|

---

# 5. 底层原理与功能特性深度解析

## 5.1 Zephyr 的启动流程

典型启动过程：

```
Reset_Handler
  |
  |-- 初始化 MSP
  |-- 初始化 .data/.bss
  |-- SystemInit / SoC early init
  |-- C 运行库初始化
  |
  |-- z_cstart()
        |
        |-- 架构初始化
        |-- 内核数据结构初始化
        |-- 板级和 SoC 初始化
        |-- 设备初始化
        |-- 主线程创建
        |-- 空闲线程创建
        |-- 切换到主线程
              |
              |-- main()
```

实际内部符号可能随版本变化，应用层不应直接依赖 `z_*` 私有符号。

Zephyr 中常见初始化级别包括：

```
PRE_KERNEL_1
PRE_KERNEL_2
POST_KERNEL
APPLICATION
SMP
```

不同阶段的职责不同：

|阶段|典型内容|
|---|---|
|`PRE_KERNEL_1`|极早期硬件、核心时钟、基础中断|
|`PRE_KERNEL_2`|驱动和内核相关设备|
|`POST_KERNEL`|内核已基本可用的系统服务和设备|
|`APPLICATION`|应用层设备、业务组件|
|`SMP`|多核系统相关初始化|

设备驱动通常通过 `DEVICE_DT_DEFINE()` 等宏注册到特定初始化阶段。开发时应查看构建生成的设备初始化表和驱动宏，而不是假定所有设备在 `main()` 前已经完全可用。

## 5.2 Board、SoC 和 Devicetree 的关系

推荐分层：

```
soc/<vendor>/<family>/
  └── family.dtsi
        ├── CPU
        ├── NVIC/中断控制器
        ├── 时钟控制器
        ├── UART/SPI/I2C/Timer 基地址
        └── 芯片复位和外设公共定义

boards/arm/my_board/
  └── my_board.dts
        ├── chosen
        ├── aliases
        ├── LED/按键
        ├── 板级晶振
        └── 板级外设状态

应用
  └── app.overlay
        ├── 产品外设
        ├── 传感器
        └── 调试配置
```

### SoC DTSI 应描述

- CPU 节点。
- 中断控制器。
- 芯片级时钟控制器。
- 外设控制器。
- 外设基地址、寄存器长度和中断。
- 芯片级 pin controller。
- Flash 和 RAM。
- DMA 控制器。
- 定时器和 RTC。

### Board DTS 应描述

- 板载晶振。
- 连接到具体引脚的 LED、按键和 UART。
- 选择控制台和 Shell 的设备。
- 板载传感器。
- 板级 aliases。
- 板级 `chosen` 节点。

示意 DTS：

```
/dts-v1/;
#include <st/my_mcu.dtsi>

/ {
    model = "Example MCU Board";
    compatible = "example,my-board";

    chosen {
        zephyr,console = &usart1;
        zephyr,shell-uart = &usart1;
        zephyr,sram = &sram0;
        zephyr,flash = &flash0;
    };

    aliases {
        led0 = &user_led;
        sw0 = &user_button;
    };

    leds {
        compatible = "gpio-leds";

        user_led: user_led_0 {
            gpios = <&gpioc 13 GPIO_ACTIVE_LOW>;
            label = "User LED";
        };
    };
};

&usart1 {
    current-speed = <115200>;
    status = "okay";
};

&gpioc {
    status = "okay";
};
```

节点名称、compatible、GPIO 控制器和 binding 必须与目标 SoC 支持一致，不能只复制语法结构。

## 5.3 Devicetree 验证方法

构建后重点查看：

```
build/zephyr/zephyr.dts
build/zephyr/include/generated/zephyr/devicetree_generated.h
```

验证内容：

- 目标外设是否为 `status = "okay"`。
- `chosen` 是否指向预期设备。
- GPIO 控制器和引脚是否正确。
- 中断号和优先级是否正确。
- DMA 通道是否冲突。
- 芯片和 Board 的 `compatible` 是否命中正确 binding。
- overlay 是否真的被构建系统加载。

常用命令：

```
west build -b my_board app
west build -t menuconfig
west build -t pristine
```

对于配置或 Devicetree 变更后出现“修改不生效”，优先执行 pristine build，而不是继续在旧 build 目录上猜测。

## 5.4 Kconfig 配置链

典型应用配置：

```
CONFIG_GPIO=y
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y
CONFIG_PRINTK=y

CONFIG_MAIN_STACK_SIZE=2048
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=2048

CONFIG_LOG=y
CONFIG_LOG_MODE_DEFERRED=y

CONFIG_THREAD_NAME=y
CONFIG_ASSERT=y
```

Kconfig 配置最终生成：

```
build/zephyr/.config
```

排查配置时，应区分：

- 用户没有配置。
- 配置被依赖条件关闭。
- Board 默认值覆盖或限制。
- SoC 能力不满足。
- 驱动没有被加入构建。
- Devicetree 节点未启用。
- 配置值被 `select` 或 `depends on` 影响。

不要只看 `prj.conf`；最终生效值以 `build/zephyr/.config` 为准。

## 5.5 Cortex-M 上下文切换

Zephyr 的 Cortex-M 上下文切换通常由官方架构层负责。高层移植工作一般不应修改 `arch/arm` 下的切换代码。

典型机制：

```
线程运行
  |
  |-- 发生阻塞、抢占或主动让出
  |
  |-- 设置调度请求
  |
  |-- PendSV 或端口规定的异常路径
        |
        |-- 保存当前线程上下文
        |-- 选择下一个可运行线程
        |-- 恢复目标线程上下文
        |-- 异常返回
```

Cortex-M 的异常硬件可能自动保存：

```
R0-R3
R12
LR
PC
xPSR
```

端口还需要保存编译器 ABI 要求的其他寄存器，例如：

```
R4-R11
CONTROL/PSP 等架构状态
可选 FPU 状态
```

具体栈布局由 Zephyr 架构端口决定。新增 Board 不应自己实现这些代码。

## 5.6 新增 CPU 架构时需要实现的内容

若是全新 ISA，才需要深入实现：

- 线程初始栈帧。
- 上下文保存和恢复。
- 异常入口。
- 中断嵌套。
- 核心锁和自旋锁。
- 原子操作。
- 系统调用入口。
- 用户态和内核态切换。
- 栈保护。
- 系统时钟。
- 编译器约束。
- 调试和异常转储。

建议顺序：

```
裸机启动
  -> 单线程内核启动
  -> Tick 工作
  -> 两线程切换
  -> 阻塞/唤醒
  -> 中断唤醒
  -> 系统调用/用户态
  -> SMP 或高级功能
```

不要在系统还不能稳定完成两个线程切换时，同时引入 MPU、用户态、低功耗和网络组件。

## 5.7 系统 Tick 和时钟驱动

Zephyr 的系统计时器负责：

- 维护内核时间。
- 处理线程超时。
- 唤醒延时线程。
- 触发时间片调度。
- 支持 tickless 或动态 Tick。
- 对接低功耗时钟。

常见配置：

```
CONFIG_SYS_CLOCK_TICKS_PER_SEC=1000
CONFIG_TICKLESS_KERNEL=y
```

配置 Tick 频率时考虑：

|因素|影响|
|---|---|
|控制周期|Tick 不应替代硬件定时器|
|超时精度|Tick 越高，时间粒度越细|
|ISR 开销|Tick 越高，固定开销越大|
|低功耗|tickless 可减少周期唤醒|
|长期计时|需要考虑计数宽度和时钟漂移|
|线程数量|唤醒和超时处理成本增加|

计算：

```
T_tick = 1 / CONFIG_SYS_CLOCK_TICKS_PER_SEC
```

如果 Tick 为 1000 Hz：

```
T_tick = 1 ms
```

但是，线程延时实际唤醒时间还受到：

- 当前 Tick 相位。
- 中断延迟。
- 高优先级线程执行时间。
- 调度器和上下文切换开销。
- 低功耗唤醒误差。

## 5.8 设备驱动模型

Zephyr 驱动通常由三部分组成：

```
Devicetree 节点
  -> 驱动实例宏
  -> 设备结构体和 API
  -> 应用调用
```

应用通过 Devicetree 获取设备：

```
#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>

#define LED0_NODE DT_ALIAS(led0)

#if !DT_NODE_HAS_STATUS(LED0_NODE, okay)
#error "led0 is not enabled in the devicetree"
#endif

static const struct gpio_dt_spec led =
    GPIO_DT_SPEC_GET(LED0_NODE, gpios);

int main(void)
{
    int ret;

    if (!gpio_is_ready_dt(&led)) {
        return -ENODEV;
    }

    ret = gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE);
    if (ret < 0) {
        return ret;
    }

    for (;;) {
        ret = gpio_pin_toggle_dt(&led);
        if (ret < 0) {
            return ret;
        }

        k_msleep(500);
    }
}
```

这里体现了 Zephyr 的典型开发方式：

- 硬件连接由 Devicetree 描述。
- `DT_ALIAS(led0)` 获取逻辑设备。
- `gpio_dt_spec` 携带控制器、引脚和 flags。
- `gpio_is_ready_dt()` 检查设备初始化状态。
- 应用不直接访问 GPIO 寄存器。

### 5.8.1 UART 配置

Board DTS：

```
&usart1 {
    current-speed = <115200>;
    status = "okay";
};
```

应用：

```
#include <zephyr/drivers/uart.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>

#define UART_NODE DT_CHOSEN(zephyr_console)

static const struct device *uart_dev =
    DEVICE_DT_GET(UART_NODE);

int uart_check(void)
{
    if (!device_is_ready(uart_dev)) {
        return -ENODEV;
    }

    return 0;
}
```

UART 驱动移植时需要核对：

- 轮询、IRQ、异步或 DMA 模式。
- 中断状态清除顺序。
- 接收 FIFO 溢出。
- 波特率误差。
- DMA 缓冲区 Cache。
- 电源管理恢复。
- 控制台和业务 UART 是否冲突。

## 5.9 初始化优先级和设备就绪状态

Zephyr 的设备初始化通常由宏和初始化级别控制。设备存在于 Devicetree，不代表一定可以使用。应用必须检查：

```
if (!device_is_ready(dev)) {
    return -ENODEV;
}
```

初始化失败的影响包括：

- 设备对象存在但未就绪。
- 时钟没有打开。
- 外设复位仍保持。
- pinctrl 配置失败。
- 中断控制器未初始化。
- DMA 通道分配失败。
- 依赖设备初始化失败。

生产代码不能仅通过 `DEVICE_DT_GET()` 获得指针后直接调用。

## 5.10 GPIO、pinctrl 和时钟控制

Zephyr Board 移植中，最容易被低估的是引脚复用和时钟依赖。

应明确：

```
时钟控制器
  -> 外设时钟
  -> pinctrl
  -> 外设寄存器配置
  -> 中断/DMA
  -> device_is_ready()
```

如果 UART 设备存在但没有输出，排查顺序：

```
chosen 是否指向正确 UART
  -> UART status 是否为 okay
  -> current-speed 是否配置
  -> pinctrl 是否启用
  -> TX/RX 引脚是否正确
  -> 外设时钟是否开启
  -> 控制台 Kconfig 是否启用
  -> 物理串口电平和波特率是否正确
```

---

# 6. 性能量化分析

## 6.1 测试平台定义

性能报告至少记录：

```
MCU：Cortex-M4F，120 MHz
Zephyr：具体 tag 或 commit
工具链：GCC 版本
优化：-O2/-Os
CONFIG_SYS_CLOCK_TICKS_PER_SEC：1000
CONFIG_PREEMPT_ENABLED：开启/关闭
FPU：软浮点或硬浮点
Cache：开启/关闭
日志：关闭、同步或延迟模式
测试线程数量
测量工具：DWT + GPIO
```

不要将某块开发板上的结果直接当作所有 Zephyr Board 的通用结论。

## 6.2 Tick 占用

```
U_tick = C_tick × f_tick / f_cpu
```

假设：

```
C_tick = 1200 cycles
f_tick = 1000 Hz
f_cpu = 120 MHz
```

则：

```
U_tick =
1200 × 1000 / 120000000
≈ 1.0%
```

这只是系统计时器基础开销，不包含 Tick 导致的线程切换、日志和驱动工作。

## 6.3 上下文切换占用

```
U_switch = C_switch × f_switch / f_cpu
```

例如：

```
C_switch = 550 cycles
f_switch = 2000 switches/s
f_cpu = 120 MHz
```

则：

```
U_switch =
550 × 2000 / 120000000
≈ 0.92%
```

实际切换周期会受以下因素影响：

- 当前线程是否使用 FPU。
- 是否发生抢占。
- 是否涉及用户态/内核态切换。
- 是否启用栈保护。
- 编译器优化。
- Cache 和总线状态。
- 线程控制块布局。

## 6.4 线程栈 RAM

Zephyr 的栈通常通过宏创建：

```
K_THREAD_STACK_DEFINE(sensor_stack, 2048);
static struct k_thread sensor_thread;
```

应使用工具和运行时统计确认实际栈消耗，不能只凭数组大小估算。总 RAM 预算包括：

```
线程栈
+ struct k_thread
+ 内核对象
+ 中断栈
+ 系统工作队列栈
+ 主线程栈
+ 空闲线程栈
+ DMA/网络/文件系统缓冲区
+ 链接器和对齐损耗
```

启用线程名称、用户态、栈保护、日志和网络组件都可能增加栈和 RAM 使用。

## 6.5 测量 DWT 周期

```
#include <stdint.h>
#include "cmsis_core.h"

static void dwt_enable(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t dwt_read(void)
{
    return DWT->CYCCNT;
}
```

测量要点：

- 先测量读取计数器本身的开销。
- 使用 `__DSB()`/`__ISB()` 处理关键边界。
- 多次采样，记录最小值、平均值、最大值和高分位值。
- 分别测量正常路径、峰值路径和异常路径。
- 记录是否开启日志、Shell、Cache、FPU 和用户态。

## 6.6 中断响应测量

建议建立 GPIO 测试：

```
外部触发
  -> ISR 入口 GPIO 拉高
  -> ISR 完成 GPIO 拉低
  -> 唤醒线程
  -> 线程运行 GPIO 拉高
```

测量：

```
外部事件到 ISR 的延迟
ISR 执行时间
ISR 到线程运行的延迟
最高优先级线程阻塞时间
最大不可抢占区
```

## 6.7 性能瓶颈和优化

|瓶颈|典型表现|优化手段|
|---|---|---|
|Tick 频率过高|固定 CPU 占用过大|降低 Tick、使用 tickless|
|日志同步输出|任务和 ISR 延迟增加|延迟日志、专用日志线程|
|工作队列过载|延迟任务积压|分离高实时工作队列|
|线程过多|切换次数和栈开销增加|合并线程、事件驱动|
|网络缓冲不足|丢包和重传|固定池、调整网络 buffer|
|DMA Cache 不一致|偶发数据错误|Cache 维护或非缓存区|
|大量 Kconfig 功能|Flash/RAM 增长|按功能裁剪|
|过多设备初始化|启动变慢|调整初始化级别，延迟初始化|
|长时间关中断|ISR 延迟超标|缩小临界区，使用原子操作|

---

# 7. 应用场景选型指南

## 7.1 决策流程图

```
开始
 |
 |-- 目标 CPU 架构是否已被 Zephyr 支持？
 |       |-- 是：继续复用官方架构层
 |       |-- 否：先评估新增架构的长期维护成本
 |
 |-- 目标 SoC 是否已有 Zephyr 支持？
 |       |-- 是：新增或复用 Board
 |       |-- 否：先实现 SoC 基础支持
 |
 |-- 目标硬件是否仅与已有 Board 引脚不同？
 |       |-- 是：优先新建 Board DTS 和 Board 配置
 |       |-- 否：不要把复杂硬件差异塞进 app.overlay
 |
 |-- 是否需要网络、USB、文件系统、蓝牙？
 |       |-- 是：启用对应子系统，并建立 RAM/Flash 预算
 |       |-- 否：通过 Kconfig 裁剪组件
 |
 |-- 是否需要低功耗？
 |       |-- 是：选择低功耗定时器、PM 策略和 tickless
 |       |-- 否：先建立稳定的固定 Tick 基线
 |
 |-- 是否启用 DMA、Cache、MPU、TrustZone？
         |-- 是：专项验证内存属性、上下文和安全边界
         |-- 否：执行基础 Board 验收
```

## 7.2 典型场景

|场景|方案|理由|
|---|---|---|
|同 MCU 新开发板|新增 Board，复用 SoC|工作量小，层次清晰|
|同 Board 多个产品变体|Board + overlay + Kconfig fragment|便于维护硬件和功能差异|
|新芯片同架构|新增 SoC 支持，再创建 Board|避免把 SoC 代码硬编码到 Board|
|工业网关|Zephyr + 网络/文件系统/OTA|子系统和设备模型完整|
|小型传感器节点|精简 Kconfig + 静态对象|降低 Flash/RAM 和启动开销|
|高速采集|DMA + ISR + work/thread|减少 ISR 计算和数据复制|
|低功耗产品|tickless + PM + RTC/LPTIM|控制周期唤醒功耗|
|安全产品|TrustZone/MPU/安全启动|明确安全域、内存和启动链|

---

# 8. 工程最佳实践

## 8.1 设计原则

### 原则一：先确认移植层级

开始前先回答：

```
是新应用？
是新 Board？
是新 SoC？
还是新架构？
```

如果只是新开发板，不要直接修改架构层或内核层。

### 原则二：Board 描述硬件，应用描述产品

推荐：

```
Board DTS：
  板级固定硬件、晶振、LED、按键、控制台

app.overlay：
  产品连接的传感器、执行器和可选外设

prj.conf：
  产品软件功能和内核参数
```

不要把所有设备都写进 Board DTS，也不要在应用 C 代码里硬编码芯片引脚。

### 原则三：最终配置必须可审计

构建产物至少保留：

```
build/zephyr/.config
build/zephyr/zephyr.dts
build/zephyr/zephyr.map
构建命令
west.yml
工具链版本
Zephyr commit
```

### 原则四：不直接依赖私有内部 API

应用优先使用：

- `k_thread_*`
- `k_sem_*`
- `k_msgq_*`
- `k_work_*`
- `device_is_ready()`
- `DEVICE_DT_GET()`
- `GPIO_DT_SPEC_GET()`
- 官方驱动 API

不要让业务代码直接调用 `z_*` 私有函数或依赖内部结构体布局。

### 原则五：设备错误必须可观察

至少记录：

- 设备未就绪。
- 初始化失败。
- DMA 错误。
- UART 溢出。
- 队列满。
- 内存池耗尽。
- 看门狗复位。
- HardFault 和复位原因。

## 8.2 最小 Board 文件结构

典型结构：

```
boards/arm/my_board/
  CMakeLists.txt
  Kconfig.board
  Kconfig.defconfig
  board.yml
  my_board.dts
  my_board.yaml
  board.cmake
  pinctrl.dtsi
```

不同 Zephyr 版本对 Board 元数据文件的要求可能不同，应参考相近官方 Board 的完整结构。

### `CMakeLists.txt` 示意

```
if(CONFIG_BOARD_MY_BOARD)
  board_runner_args(jlink "--device=STM32F407VG" "--speed=4000")
endif()

include(${ZEPHYR_BASE}/boards/common/jlink.board.cmake)
```

具体 runner 参数取决于芯片型号、调试器和 Zephyr 版本。

### `Kconfig.board` 示意

```
config BOARD_MY_BOARD
    bool "My board"
    depends on SOC_FAMILY_STM32
    select SOC_SERIES_STM32F4X
```

### `Kconfig.defconfig` 示意

```
if BOARD_MY_BOARD

config BOARD
    default "my_board"

config UART_CONSOLE
    default y

endif
```

实际配置符号必须与目标 Zephyr 版本和 SoC Kconfig 层级一致。

## 8.3 线程创建最佳实践

```
#include <zephyr/kernel.h>

#define SENSOR_STACK_SIZE 2048
#define SENSOR_PRIORITY   5

K_THREAD_STACK_DEFINE(sensor_stack, SENSOR_STACK_SIZE);
static struct k_thread sensor_thread_data;

static void sensor_entry(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);

    while (true) {
        sensor_sample();
        k_sleep(K_MSEC(10));
    }
}

static int sensor_thread_start(void)
{
    k_tid_t tid;

    tid = k_thread_create(&sensor_thread_data,
                          sensor_stack,
                          K_THREAD_STACK_SIZEOF(sensor_stack),
                          sensor_entry,
                          NULL,
                          NULL,
                          NULL,
                          SENSOR_PRIORITY,
                          0,
                          K_NO_WAIT);

    if (tid == NULL) {
        return -ENOMEM;
    }

    k_thread_name_set(tid, "sensor");
    return 0;
}
```

注意：

- 使用 `K_THREAD_STACK_DEFINE()`，不要普通数组替代架构所需的栈对象。
- 使用 `K_THREAD_STACK_SIZEOF()` 获取有效栈大小。
- 线程入口不要直接返回，除非明确设计了线程退出和资源清理。
- 线程优先级要结合实际响应时间和 CPU 占用评估。
- `CONFIG_THREAD_NAME` 未启用时，线程命名功能可能不可用或被裁剪。

## 8.4 消息队列与 ISR

```
#include <zephyr/kernel.h>

struct sample_msg {
    uint32_t timestamp;
    uint16_t value;
};

K_MSGQ_DEFINE(sample_msgq,
              sizeof(struct sample_msg),
              16,
              4);

void ADC_IRQHandler(void)
{
    struct sample_msg msg = {
        .timestamp = timer_capture_timestamp(),
        .value = adc_read_result(),
    };

    /*
     * ISR 中必须使用允许在中断上下文调用的 API。
     * 若队列满，不能阻塞等待。
     */
    if (k_msgq_put(&sample_msgq, &msg, K_NO_WAIT) != 0) {
        sample_drop_count++;
    }
}

static void sample_thread(void)
{
    struct sample_msg msg;

    while (true) {
        if (k_msgq_get(&sample_msgq, &msg, K_FOREVER) == 0) {
            process_sample(&msg);
        }
    }
}
```

工程重点：

- ISR 发送消息时使用 `K_NO_WAIT`。
- 队列满时必须定义丢弃或背压策略。
- 不要在 ISR 中等待消费者。
- 如果消息数量高、数据较大，考虑环形缓冲区或内存池传递指针。
- DMA 缓冲区需要单独处理 Cache 和所有权。

---

# 9. 常见错误与避坑指南

## 9.1 错误一：只修改 `prj.conf`，忽略 Devicetree

错误示例：

```
CONFIG_UART_CONSOLE=y
CONFIG_SERIAL=y
```

但 Board DTS 中没有启用 UART，也没有配置 `chosen`：

```
/ {
    chosen {
        /* 缺少 zephyr,console */
    };
};
```

### 根因

Kconfig 只会编译 UART 支持，并不会告诉系统实际使用哪一个 UART，也不会配置引脚、地址和中断。

### 正确实现

```
/ {
    chosen {
        zephyr,console = &usart1;
    };
};

&usart1 {
    current-speed = <115200>;
    status = "okay";
};
```

### 风险影响

- 编译通过但没有串口输出。
- 控制台绑定错误设备。
- 驱动没有进入就绪状态。
- 调试误以为内核没有启动。

## 9.2 错误二：修改 overlay 后没有 pristine build

错误现象：

```
已经修改 app.overlay，但生成的 zephyr.dts 没有变化。
```

### 根因

CMake、Kconfig 或 Devicetree 生成文件仍使用旧缓存。

### 正确实现

```
west build -t pristine
west build -b my_board app
```

或者使用全新构建目录：

```
west build -d build_clean -b my_board app
```

### 风险影响

- 硬件配置与实际固件不一致。
- 错误诊断方向。
- 旧的设备地址、引脚或中断配置持续生效。

## 9.3 错误三：设备指针存在但没有检查 `device_is_ready()`

错误示例：

```
const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(i2c1));

i2c_configure(dev, config);
```

### 根因

`DEVICE_DT_GET()` 通常只生成设备对象地址，不保证设备初始化成功。

### 正确实现

```
const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(i2c1));

if (!device_is_ready(dev)) {
    LOG_ERR("I2C device is not ready");
    return -ENODEV;
}

return i2c_configure(dev, config);
```

### 风险影响

- 调用未初始化的驱动。
- 空时钟、复位或 pinctrl 导致硬Fault。
- 设备初始化失败被业务逻辑掩盖。

## 9.4 错误四：在 ISR 中使用阻塞 API

错误示例：

```
void GPIO_IRQHandler(void)
{
    k_sem_take(&sem, K_FOREVER);
}
```

### 根因

ISR 没有线程上下文，不能阻塞等待。

### 正确实现

```
void GPIO_IRQHandler(void)
{
    gpio_clear_interrupt();

    if (k_sem_give(&sem) != 0) {
        irq_error_count++;
    }
}

static void worker(void)
{
    while (true) {
        k_sem_take(&sem, K_FOREVER);
        process_event();
    }
}
```

### 风险影响

- 系统死锁。
- 中断无法退出。
- 调度器内部状态损坏。
- 看门狗复位。

## 9.5 错误五：使用普通数组作为线程栈

错误示例：

```
static uint8_t stack[2048];
static struct k_thread thread_data;

k_thread_create(&thread_data,
                stack,
                sizeof(stack),
                worker,
                NULL, NULL, NULL,
                5, 0, K_NO_WAIT);
```

### 根因

Zephyr 的线程栈可能需要架构特定的对齐、保护区、边界标记或用户态区域。普通数组无法保证这些条件。

### 正确实现

```
K_THREAD_STACK_DEFINE(worker_stack, 2048);

k_thread_create(&thread_data,
                worker_stack,
                K_THREAD_STACK_SIZEOF(worker_stack),
                worker,
                NULL, NULL, NULL,
                5, 0, K_NO_WAIT);
```

### 风险影响

- 栈保护失效。
- 用户态线程启动失败。
- 栈边界覆盖相邻对象。
- FPU 或异常嵌套时随机崩溃。

## 9.6 错误六：DMA 缓冲区忽略 Cache 一致性

错误示例：

```
static uint8_t rx_buffer[2048];

start_dma(rx_buffer, sizeof(rx_buffer));
```

### 根因

Cortex-M7 等带 D-Cache 的内核中，CPU 可能读取旧 Cache 内容，DMA 则直接访问 RAM。

### 正确实现

根据芯片 Cache line 和 Zephyr 平台支持方式：

```
/* 伪代码：具体 cache API 和对齐要求以目标平台为准。 */
cache_data_invd_range(rx_buffer, sizeof(rx_buffer));
start_dma(rx_buffer, sizeof(rx_buffer));
```

发送前：

```
cache_data_flush_range(tx_buffer, tx_length);
start_tx_dma(tx_buffer, tx_length);
```

还需考虑：

- 缓冲区地址对齐。
- 长度按 Cache line 对齐。
- 缓冲区是否与其他变量共享 Cache line。
- DMA 区域是否可放置在非缓存 RAM。
- MPU 区域属性。

### 风险影响

- 接收到旧数据。
- 发出的数据不是 CPU 最新写入内容。
- 故障仅在开启 Cache、优化或高负载下出现。

## 9.7 错误七：直接修改生成文件或 `build/zephyr/.config`

错误示例：

```
手动修改 build/zephyr/.config
手动修改 build/zephyr/zephyr.dts
```

### 根因

这些文件是构建生成物，下一次构建会被覆盖。

### 正确实现

- Kconfig 修改 `prj.conf`、Board defconfig 或 Kconfig fragment。
- Devicetree 修改 `.dts`、`.dtsi` 或 overlay。
- 修改后执行 pristine build。
- 在生成文件中验证结果，而不是把生成文件当作源文件维护。

### 风险影响

- 本地构建有效，CI 或其他开发机无效。
- 配置不可复现。
- 问题难以追踪。

## 9.8 错误八：把 Board 差异全部写进应用代码

错误示例：

```
#if defined(BOARD_A)
#define SENSOR_CS_PIN 4
#elif defined(BOARD_B)
#define SENSOR_CS_PIN 7
#endif
```

### 根因

将硬件描述和业务逻辑耦合，导致产品变体增加后条件编译失控。

### 正确实现

Devicetree：

```
&spi1 {
    status = "okay";

    sensor@0 {
        compatible = "vendor,sensor";
        reg = <0>;
        spi-max-frequency = <8000000>;
        irq-gpios = <&gpioa 4 GPIO_ACTIVE_HIGH>;
    };
};
```

应用通过 `DT_INST()`、`DT_NODELABEL()` 或驱动 API 获取硬件配置。

### 风险影响

- Board 切换时大量修改 C 代码。
- 硬件配置无法被工具验证。
- 驱动复用困难。

---

# 10. 多机制组合使用方案

## 10.1 DMA + 中断 + 环形缓冲区 + 工作队列

适合中等吞吐数据采集和通信。

```
DMA
  -> 半传输/全传输中断
  -> 缓冲区所有权切换
  -> 环形缓冲区写指针更新
  -> 提交工作项
  -> 工作队列批量处理
  -> 业务线程或消息队列
```

示意代码：

```
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#define RX_BUFFER_SIZE 1024U

static uint8_t rx_buffer[RX_BUFFER_SIZE];
static struct k_work rx_work;

static volatile size_t dma_write_pos;
static volatile size_t worker_read_pos;
static volatile uint32_t rx_overrun_count;

static void rx_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    while (worker_read_pos != dma_write_pos) {
        uint8_t byte = rx_buffer[worker_read_pos];

        worker_read_pos++;
        if (worker_read_pos == RX_BUFFER_SIZE) {
            worker_read_pos = 0U;
        }

        protocol_feed_byte(byte);
    }
}

static void dma_rx_isr(void)
{
    size_t new_pos;

    dma_clear_irq();
    new_pos = dma_get_write_position();

    /*
     * Cortex-M7 等平台需在这里执行目标平台要求的
     * Cache invalidate 和内存屏障。
     */
    dma_rx_prepare_cpu_read(rx_buffer, RX_BUFFER_SIZE);

    if (ring_distance(new_pos, worker_read_pos,
                      RX_BUFFER_SIZE) >= RX_BUFFER_SIZE - 1U) {
        rx_overrun_count++;
        dma_recover_rx();
        return;
    }

    dma_write_pos = new_pos;
    k_work_submit(&rx_work);
}
```

### 10.1.1 组合设计要点

- ISR 中不执行协议解析。
- `k_work_submit()` 不代表一定立即执行，工作队列可能被其他工作项占用。
- 对严格实时数据，不要将高实时工作提交到共享系统工作队列；可以创建专用工作队列。
- 环形缓冲区的读写索引必须明确由谁修改。
- 单生产者/单消费者可以使用无锁设计，但多生产者/多消费者需要额外同步。
- DMA 更新指针后必须有适当的内存可见性保证。
- 缓冲区满时必须有明确丢包或背压策略。

## 10.2 专用工作队列

```
#define APP_WQ_STACK_SIZE 2048
#define APP_WQ_PRIORITY   4

K_THREAD_STACK_DEFINE(app_wq_stack, APP_WQ_STACK_SIZE);

static struct k_work_q app_work_q;

static void app_work_queue_init(void)
{
    k_work_queue_init(&app_work_q);

    k_work_queue_start(&app_work_q,
                       app_wq_stack,
                       K_THREAD_STACK_SIZEOF(app_wq_stack),
                       APP_WQ_PRIORITY,
                       NULL);
}
```

适合：

- 高吞吐协议处理。
- 不希望被系统工作队列中的低优先级任务拖延。
- 需要独立的栈预算和优先级。

注意：Zephyr 不同版本对工作队列启动接口和配置方式可能有所变化，应以对应版本 API 为准。

---

# 11. 工业级实际案例分析

## 11.1 案例一：工业传感器采集节点

### 需求

- ADC 以 20 kHz 采样。
- SPI 连接外部传感器。
- DMA 连续搬运。
- 采样数据需要滤波、阈值判断和低速上传。
- 设备需要低功耗待机。

### 硬件和软件架构

```
硬件定时器
  -> ADC/SPI 触发
  -> DMA 缓冲区
  -> DMA ISR
  -> 专用工作队列
  -> 滤波任务
  -> 事件/消息队列
  -> 通信线程
```

### Zephyr 配置重点

```
CONFIG_GPIO=y
CONFIG_SPI=y
CONFIG_ADC=y
CONFIG_DMA=y
CONFIG_PM=y
CONFIG_TICKLESS_KERNEL=y
CONFIG_LOG=y
CONFIG_LOG_MODE_DEFERRED=y
```

### 设计要点

- 采样时钟由硬件定时器提供，不依赖内核 Tick。
- DMA 缓冲区放在正确的内存区域。
- 采样线程不直接调用同步日志。
- 通过固定大小消息队列传递统计结果，而不是复制大批量原始数据。
- 记录 DMA overrun、队列满、采样丢失和最大处理延迟。
- 低功耗进入前必须停止或重新配置 DMA、ADC 和定时器。

### 验收指标

```
采样周期误差
DMA 中断响应时间
每个数据块处理最大时间
连续采样丢样数
低功耗唤醒延迟
24 小时运行内存稳定性
```

## 11.2 案例二：工业网关和多协议设备

### 需求

- 以太网、CAN、UART 并发。
- 支持 MQTT/工业协议、配置文件、OTA 和日志。
- 设备长期运行。
- 网络峰值流量高于平均流量。

### 架构

```
Ethernet DMA
  -> 网络驱动
  -> 网络协议栈线程

CAN DMA/IRQ
  -> CAN 接收线程
  -> 协议路由层

UART
  -> DMA + 环形缓冲
  -> 串口协议线程

Flash
  -> Flash 管理线程
  -> 配置/OTA 状态机
```

### Zephyr 特性使用

- Devicetree 描述各总线和外设。
- Kconfig 控制网络、Flash、文件系统和日志。
- 固定内存池管理高频协议对象。
- 专用工作队列处理高优先级协议事件。
- sysbuild 管理主应用、引导程序和辅助镜像。
- OTA 使用镜像校验、版本管理和回滚策略。

### 关键风险

- 网络 buffer RAM 不足。
- 多协议线程优先级不合理。
- Flash 写入阻塞高优先级任务。
- 日志同步输出占用串口。
- DMA 缓冲区 Cache 不一致。
- 多镜像版本不匹配。
- Kconfig 打开大量组件导致 Flash 超预算。

## 11.3 案例三：TrustZone-M 低功耗控制器

### 需求

- Cortex-M33。
- 安全区域管理密钥和关键寄存器。
- 非安全应用执行通信和业务。
- 低功耗唤醒后保持时间基准。
- 支持安全启动和固件升级。

### 架构

```
安全镜像
  -> 安全启动
  -> 密钥管理
  -> 安全外设
  -> 非安全调用入口

非安全镜像
  -> Zephyr 应用
  -> 网络/传感器/用户业务
  -> 非安全设备驱动
```

### 设计要点

- 安全和非安全镜像的内存区域由链接脚本和平台配置共同确定。
- 非安全线程不能访问安全地址。
- 异常入口和栈区域必须满足安全状态切换约束。
- secure/non-secure veneer、SAU/IDAU、MPU 配置需要联合验证。
- 低功耗唤醒时必须按安全状态恢复外设。
- OTA 更新必须同时校验主镜像和安全镜像的兼容性。

---

# 12. 高频问题深度答疑

## Q1：Zephyr 移植是不是只需要创建一个 Board 目录？

只有在目标 SoC 已被 Zephyr 支持，并且现有架构层和驱动能直接复用时，才可能主要通过 Board 目录完成。新 SoC 还需要补充：

- SoC DTSI。
- SoC Kconfig。
- 时钟和复位。
- 中断控制器。
- 系统计时器。
- 基础外设驱动。
- 启动和链接配置。

应先判断目标属于 Board 移植还是 SoC 移植。

## Q2：为什么 Devicetree 中有 UART 节点，驱动仍然没有输出？

设备树节点存在不代表设备已启用。需要同时检查：

```
节点 status 是否为 okay
  -> compatible 是否匹配驱动
  -> UART Kconfig 是否启用
  -> chosen 是否指向该 UART
  -> pinctrl 是否正确
  -> 外设时钟是否打开
  -> device_is_ready() 是否成功
  -> 物理串口电气连接是否正确
```

必须查看生成后的 `build/zephyr/zephyr.dts`，不要只看源 `.dts`。

## Q3：Kconfig 和 Devicetree 哪个优先？

它们解决不同问题，没有简单的优先级关系：

- Kconfig 决定代码是否编译、功能是否启用、资源参数是多少。
- Devicetree 决定硬件实例、地址、IRQ、引脚、总线和状态。

例如启用 `CONFIG_I2C=y` 只会启用 I2C 软件支持；没有 Devicetree 节点，系统仍不知道使用哪个 I2C 控制器。

## Q4：Zephyr 的系统 Tick 是否适合高精度控制？

普通内核 Tick 不应直接承担严格周期控制。高精度控制通常使用：

- 硬件定时器。
- PWM/ADC 硬件触发。
- DMA。
- 外设捕获比较。
- 专用 ISR 或实时线程。

Zephyr Tick 适合线程超时、调度时基和软件定时，不适合作为所有硬实时事件的唯一时钟源。

## Q5：为什么修改 `prj.conf` 后配置没有生效？

可能原因：

- 配置符号拼写错误。
- 被依赖条件关闭。
- 被 Board 或 SoC 配置限制。
- 使用了错误的构建目录。
- CMake 缓存没有刷新。
- 模块版本不匹配。
- 配置只对另一个镜像生效。

排查顺序：

```
查看 build/zephyr/.config
  -> west build -t menuconfig
  -> 检查依赖和最终值
  -> 执行 pristine build
  -> 检查目标镜像是否正确
```

## Q6：为什么不能把普通数组作为 Zephyr 线程栈？

Zephyr 线程栈宏可能根据架构和配置增加：

- 对齐。
- 栈保护区域。
- 用户态权限区域。
- 栈边界标记。
- 额外保留空间。

因此应使用：

```
K_THREAD_STACK_DEFINE()
K_THREAD_STACK_SIZEOF()
```

而不是普通 `uint8_t[]`。

## Q7：Zephyr 的工作队列和线程有什么区别？

工作队列是一个线程上下文执行模型，同一工作队列上的多个 work item 共享一个线程和栈。优点是资源开销低，缺点是一个耗时 work item 会阻塞同一队列上的其他 work item。

适合工作队列：

- 短小、非阻塞、可串行执行的异步工作。

适合独立线程：

- 需要独立优先级。
- 需要较大栈。
- 可能长时间运行。
- 需要阻塞等待。
- 不能被其他工作项拖延。

## Q8：新增 Zephyr Board 时，哪些文件最容易漏？

常见遗漏：

- `board.yml` 或新版 Board 元数据。
- `Kconfig.board`。
- `Kconfig.defconfig`。
- Board DTS。
- Board CMake。
- Flash/debug runner。
- pinctrl 文件。
- Board 目录没有加入 west/CMake 可发现范围。
- 默认 UART/console 配置。
- linker 或 SRAM/Flash 描述。
- 板级晶振和时钟配置。

最可靠的方法是复制一个硬件结构最接近的官方 Board，逐项比较文件，而不是只创建 DTS。

## Q9：Zephyr 版本升级为什么容易出现 DTS 或 Kconfig 问题？

Zephyr 的设备模型、binding、Kconfig 符号、Board 元数据和驱动接口都可能演进。版本升级后应同时检查：

- `west.yml` 和模块版本。
- Board 元数据格式。
- DTS binding。
- Kconfig 依赖。
- 设备 API。
- linker 和 runner。
- 生成的 `zephyr.dts` 与 `.config`。
- 构建警告和弃用提示。

不能只修改一个编译错误后直接交付。

---

# 13. 课程核心总结

## 核心要点

1. Zephyr 移植的核心不是简单重写上下文切换，而是建立完整的：

```
架构层
+ SoC 层
+ Board 层
+ Devicetree
+ Kconfig
+ 驱动
+ 构建和下载流程
```

2. 如果目标架构和 SoC 已经被支持，新增 Board 通常是最佳路径。
3. Devicetree 描述硬件，Kconfig 控制软件功能和资源，不能相互替代。
4. 任何设备使用前都应检查 `device_is_ready()`。
5. 线程栈必须使用 Zephyr 的栈定义宏。
6. 系统 Tick 负责内核时间，不应替代硬件定时器完成严格周期控制。
7. DMA、Cache、MPU、TrustZone 和低功耗必须进行专项验证。
8. 生成的 `.config`、`zephyr.dts` 和 map 文件是移植调试的核心证据。
9. 高实时路径应采用硬件触发、DMA、短 ISR 和专用工作线程/工作队列。
10. Zephyr 版本、模块、工具链和 Board 支持必须纳入可复现构建管理。

## 通用选型结论

```
已有架构 + 已有 SoC + 新开发板：
    新建 Board，复用 SoC 和驱动。

已有架构 + 新 SoC：
    先完成 SoC 层，再创建 Board。

新架构：
    先实现最小架构端口，再扩展系统调用、用户态和 SMP。

硬实时控制：
    使用硬件定时器/DMA，RTOS 负责线程管理和业务协作。

低功耗：
    选择低功耗时钟和 tickless，测量唤醒误差与时间漂移。

复杂产品：
    使用 Devicetree、Kconfig、sysbuild 和模块化工程组织。
```

---

# 14. 快速参考速查表

## 14.1 移植层级速查

|目标|主要工作|
|---|---|
|新应用|`prj.conf`、应用代码、overlay|
|新 Board|DTS、Kconfig、CMake、runner、Board 元数据|
|新 SoC|DTSI、Kconfig、时钟、复位、中断、Tick、基础驱动|
|新架构|上下文切换、异常、原子、系统调用、工具链支持|
|新产品变体|Board 配置 + overlay + Kconfig fragment|
|多镜像产品|sysbuild、镜像依赖、共享分区和版本管理|

## 14.2 调试文件速查

|文件|用途|
|---|---|
|`build/zephyr/.config`|查看最终 Kconfig|
|`build/zephyr/zephyr.dts`|查看最终 Devicetree|
|`devicetree_generated.h`|查看 Devicetree 宏展开|
|`zephyr.map`|查看符号、段和 RAM/Flash 占用|
|ELF 文件|查看异常向量、驱动和线程符号|
|`west.yml`|查看 Zephyr 和模块版本|
|linker map|检查内存区域、堆栈和镜像布局|

## 14.3 常见命令

```
# 初始化/更新工作区
west update

# 构建
west build -b my_board app

# 指定构建目录
west build -d build_debug -b my_board app

# 打开 Kconfig
west build -t menuconfig

# 清理构建
west build -t pristine

# 下载
west flash

# 调试
west debug
```

## 14.4 场景选型表

|场景|建议|
|---|---|
|新开发板|复制相近官方 Board，逐项替换硬件描述|
|外接传感器|使用 app overlay，不在 C 中硬编码引脚|
|多产品变体|Board + overlay + Kconfig fragment|
|高速数据流|DMA + 环形缓冲区 + 专用工作队列|
|固定大小消息|`k_mem_slab` 或固定消息队列|
|长期运行网关|固定内存池、网络 buffer 预算、异步日志|
|低功耗|PM + tickless + 低功耗计时源|
|TrustZone|多镜像、内存区域、安全入口联合设计|
|新 SoC|先完成 SoC 基础支持，再做 Board|

---

# 15. 学习效果自检

完成本课后，应能回答：

- Zephyr 的架构层、SoC 层和 Board 层分别负责什么？
- 为什么新增 Board 通常不需要重写上下文切换？
- Devicetree 和 Kconfig 的职责有什么区别？
- 如何确认应用 overlay 实际被构建系统加载？
- 如何确认最终 UART 控制台指向正确设备？
- 为什么 `DEVICE_DT_GET()` 后还必须调用 `device_is_ready()`？
- 为什么线程栈必须使用 `K_THREAD_STACK_DEFINE()`？
- 系统 Tick 与高精度硬件定时器分别适合什么场景？
- 如何设计 DMA 缓冲区的 Cache 和所有权策略？
- 如何判断工作队列是否应该替换为独立线程？
- 如何从 `.config` 判断 Kconfig 配置最终是否生效？
- 如何从 `zephyr.dts` 判断设备树 overlay 是否正确？
- 如何定位设备初始化失败、驱动未编译和硬件未连接之间的差异？
- 新增 SoC 时，哪些内容不能简单复制 Board 代码？
- Zephyr 版本升级时需要执行哪些回归检查？

---

# 16. 实践与进阶路径

## 16.1 梯度实战任务

### 任务一：构建官方 Board 示例

目标：

```
west workspace 正常
  -> 官方 Board 正常构建
  -> west flash 正常下载
  -> UART 控制台正常输出
  -> GPIO 示例正常运行
```

重点检查：

- 工具链。
- runner。
- Board 名称。
- Devicetree。
- Kconfig。
- 生成的 map 文件。

### 任务二：复制 Board 创建新板

步骤：

1. 选择同 MCU 或同系列官方 Board。
2. 复制 Board 目录。
3. 修改 Board 元数据。
4. 修改 DTS 的 model、compatible、chosen、aliases。
5. 修改时钟、晶振和 pinctrl。
6. 修改 `Kconfig.board` 和 `Kconfig.defconfig`。
7. 验证 UART、LED、按键和 Flash。
8. 添加 `west flash` 和 `west debug` 支持。

### 任务三：增加传感器 overlay

实现：

```
SPI/I2C 控制器
  -> 传感器节点
  -> 中断 GPIO
  -> 设备就绪检查
  -> 采样线程
```

验证：

- 节点 status。
- compatible。
- 地址和片选。
- GPIO 中断。
- 总线速率。
- 设备初始化错误。
- 传感器断线恢复。

### 任务四：DMA 数据通路

实现：

```
硬件定时器
  -> DMA
  -> ISR
  -> 缓冲区
  -> 专用工作队列
  -> 数据处理线程
```

验证：

- 高速连续数据。
- 缓冲区满。
- DMA error。
- Cache 开启。
- 线程处理延迟。
- 数据丢失统计。

### 任务五：内存和实时性测试

测量：

- Tick ISR 周期。
- 线程切换周期。
- ISR 到线程响应延迟。
- 最大临界区时间。
- 主线程和工作队列栈高水位。
- 系统工作队列峰值负载。
- 网络 buffer 峰值占用。
- Flash/RAM 余量。

### 任务六：低功耗与多镜像

实现：

- PM 状态切换。
- RTC/LPTIM 唤醒。
- tickless。
- Bootloader + Application。
- 镜像校验和回滚。
- 低功耗恢复后的设备重新初始化。

## 16.2 性能测试方法

### 调度测试

分别测量：

```
主动让出 CPU
线程阻塞后唤醒
高优先级线程抢占
Tick 触发调度
ISR 退出触发线程运行
```

每个场景至少记录：

```
最小值
平均值
最大值
P95/P99
异常样本
```

### 内存测试

记录：

- Flash 使用量。
- RAM 使用量。
- 每个线程栈高水位。
- 系统工作队列栈高水位。
- 网络和文件系统缓冲区峰值。
- 内存池最小剩余块数。
- 消息队列最大深度。
- DMA buffer overrun 次数。

### 故障注入

至少覆盖：

- Devicetree 设备禁用。
- 设备初始化失败。
- UART 溢出。
- DMA 超时。
- 消息队列满。
- 内存池耗尽。
- 线程栈接近边界。
- Cache 未维护。
- 时钟切换失败。
- 低功耗唤醒失败。
- 看门狗复位。
- OTA 镜像校验失败。

## 16.3 进阶学习方向

- 阅读 Zephyr `arch/` 中目标架构的上下文切换和异常处理。
- 阅读 `kernel/` 中线程、调度、超时和同步对象实现。
- 深入 Devicetree binding 和驱动实例化宏。
- 研究 Kconfig 依赖、默认值、`select` 和配置覆盖关系。
- 研究 SoC、Board、Shield、Module 和 sysbuild 的组织方式。
- 研究 Cortex-M7 Cache、MPU、DMA、TrustZone-M 和用户态。
- 研究 tickless、PM device runtime、RTC 校时和长期时间漂移。
- 研究网络 buffer、固定内存池、零拷贝和高吞吐调度。
- 建立持续集成流程：
    - 固定 west manifest。
    - 自动执行 pristine build。
    - 检查最终 `.config`。
    - 检查最终 `zephyr.dts`。
    - 检查 Flash/RAM 预算。
    - 执行硬件回归。
    - 执行性能和栈水位回归。
    - 记录 Zephyr 版本升级差异。