# VncComputer - 直接连接到远程服务器

## 概述

`VncComputer` 是 `Computer` 类的一个子类，专门用于连接到已经运行的远程服务器，而不需要启动或停止虚拟机。这使得它非常适合以下场景：

- 连接到已运行的 VNC 服务器
- 连接到远程桌面服务
- 连接到 Docker 容器中的 computer-server
- 连接到任何已经运行 computer-server 的远程主机

## 主要特点

✅ **简单连接**：只需要 IP 和端口，无需启动 VM  
✅ **完全兼容**：继承自 `Computer`，可用于任何需要 `Computer` 的场景  
✅ **自动管理**：支持 `async with` 语法，自动管理连接生命周期  
✅ **轻量级**：没有 VM 管理的开销  
✅ **可用于 Agent**：可以直接在 `ComputerAgent` 中使用  

## 前提条件

远程主机需要先安装并启动 computer-server：

```bash
pip install cua-computer-server
python -m computer_server
```

## 快速开始

### 基本用法

```python
import asyncio
from computer import VncComputer

async def main():
    # 只需要提供 IP 地址，端口默认为 8000
    async with VncComputer(ip="192.168.1.100", os_type="linux") as computer:
        # 使用 computer.interface 进行操作
        result = await computer.interface.run_command("whoami")
        print(result.stdout)
        
        # 截图
        screenshot = await computer.interface.screenshot()
        
        # 鼠标和键盘操作
        await computer.interface.run_command(
            'python3 -c "import pyautogui; pyautogui.moveTo(500, 500)"'
        )

asyncio.run(main())
```

### 与 Computer 的对比

**传统 Computer（需要启动 VM）：**

```python
from computer import Computer

async with Computer(
    image="ubuntu:latest",
    os_type="linux",
    provider_type="docker"
) as computer:
    # 需要等待 VM 启动
    # ...
```

**VncComputer（直接连接）：**

```python
from computer import VncComputer

async with VncComputer(
    ip="192.168.1.100",
    os_type="linux"
) as computer:
    # 立即连接，无需等待启动
    # ...
```

## 完整示例

### 示例 1：执行命令

```python
async with VncComputer(ip="192.168.1.100") as computer:
    # 执行 Shell 命令
    result = await computer.interface.run_command("ls -la")
    print(result.stdout)
    
    # 执行 Python 代码
    result = await computer.interface.run_command(
        'python3 -c "print(\"Hello from remote!\")"'
    )
    print(result.stdout)
```

### 示例 2：截图

```python
async with VncComputer(ip="192.168.1.100") as computer:
    # 获取屏幕尺寸
    screen_size = await computer.interface.get_screen_size()
    print(f"屏幕尺寸: {screen_size}")
    
    # 截图
    screenshot = await computer.interface.screenshot()
    
    # 保存截图
    with open("screenshot.png", "wb") as f:
        f.write(screenshot)
```

### 示例 3：鼠标和键盘操作

```python
async with VncComputer(ip="192.168.1.100") as computer:
    # 移动鼠标
    await computer.interface.run_command(
        'python3 -c "import pyautogui; pyautogui.moveTo(500, 500)"'
    )
    
    # 点击
    await computer.interface.run_command(
        'python3 -c "import pyautogui; pyautogui.click()"'
    )
    
    # 输入文字
    await computer.interface.run_command(
        'python3 -c "import pyautogui; pyautogui.write(\'Hello\')"'
    )
```

### 示例 4：手动管理连接

```python
# 创建实例
computer = VncComputer(ip="192.168.1.100", os_type="linux")

try:
    # 手动连接
    await computer.run()
    
    # 执行操作
    result = await computer.interface.run_command("whoami")
    print(result.stdout)
    
    # 重新连接
    await computer.restart()
    
finally:
    # 手动断开
    await computer.stop()
```

## 在 ComputerAgent 中使用

`VncComputer` 继承自 `Computer`，因此可以直接在 `ComputerAgent` 中使用：

```python
from computer import VncComputer
from agent import ComputerAgent

# 创建 VncComputer
computer = VncComputer(ip="192.168.1.100", os_type="linux")

# 在 Agent 中使用
agent = ComputerAgent(computer=computer)

# Agent 可以像使用 Computer 一样使用 VncComputer
await agent.run("打开浏览器并访问 google.com")
```

## API 参考

### 构造函数

```python
VncComputer(
    ip: str,                    # 远程主机 IP 地址（必需）
    port: int = 8000,           # computer-server 端口
    os_type: OSType = "linux",  # 操作系统类型：'linux', 'macos', 'windows'
    verbosity: Union[int, LogLevel] = logging.INFO,  # 日志级别
    telemetry_enabled: bool = True,  # 是否启用遥测
)
```

### 主要方法

#### `async run()`
连接到远程服务器

#### `async stop()`
断开与远程服务器的连接（不会停止远程服务器）

#### `async restart()`
重新连接到远程服务器

#### `async get_ip()`
获取 IP 地址（返回配置的 IP）

### 属性

#### `interface`
获取 computer interface，用于执行具体操作

## 与 Computer 的区别

| 特性 | Computer | VncComputer |
|-----|----------|-------------|
| **启动 VM** | ✅ 需要 | ❌ 不需要 |
| **停止 VM** | ✅ 支持 | ❌ 不支持（只断开连接） |
| **连接方式** | 启动后连接 | 直接连接 |
| **资源管理** | 管理 VM 资源 | 不管理资源 |
| **使用场景** | 需要创建新环境 | 连接已有环境 |
| **启动时间** | 较长（需要启动 VM） | 很快（直接连接） |
| **在 Agent 中使用** | ✅ 支持 | ✅ 支持 |

## 不支持的操作

由于 `VncComputer` 不管理 VM，以下操作不支持：

- `update()` - 更新 VM 配置（会抛出 `NotImplementedError`）
- VM 相关的 provider 操作

## 错误处理

```python
try:
    async with VncComputer(ip="192.168.1.100") as computer:
        result = await computer.interface.run_command("some_command")
        if result.returncode != 0:
            print(f"命令执行失败: {result.stderr}")
except ConnectionError as e:
    print(f"连接失败: {e}")
except TimeoutError as e:
    print(f"连接超时: {e}")
except Exception as e:
    print(f"发生错误: {e}")
```

## 注意事项

1. **远程服务器必须运行 computer-server**：VncComputer 连接到 computer-server 提供的 WebSocket 接口
2. **不会停止远程服务器**：调用 `stop()` 只会断开连接，不会停止远程服务器
3. **防火墙设置**：确保远程主机的端口（默认 8000）可以访问
4. **操作系统类型**：`os_type` 参数应该与远程主机的实际操作系统匹配

## 相关示例

- `examples/vnc_computer_quickstart.py` - 快速开始示例
- `examples/vnc_computer_example.py` - 完整示例，包含所有功能演示
- `examples/remote_server_simple.py` - RemoteCodeExecutor 示例（另一种远程执行方式）

## 许可证

与 CUA Computer 项目相同的许可证。

