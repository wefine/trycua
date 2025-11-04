# 连接到远程 computer-server

本文档说明如何在远程 VNC 主机上安装 computer-server 并通过 CUA SDK 进行连接。

## 架构说明

```
┌─────────────────────────┐       WebSocket/HTTP        ┌─────────────────────────┐
│   本地机器              │  ───────────────────────>   │   远程 VNC 主机         │
│                         │                              │                         │
│  Python 脚本            │                              │  VNC Server             │
│  └── Interface          │                              │  Computer Server :8000  │
│      (连接远程 IP)      │                              │  (控制桌面环境)         │
└─────────────────────────┘                              └─────────────────────────┘
```

## 一、远程主机配置

### 1. 安装 computer-server

在远程 VNC 主机上执行：

```bash
# 安装 computer-server
pip install cua-computer-server

# 或从源码安装
cd libs/python/computer-server
pip install -e .
```

### 2. 启动 computer-server

```bash
# 启动服务器（默认监听 0.0.0.0:8000）
python -m computer_server

# 或指定端口
python -m computer_server --port 8000
```

### 3. 配置防火墙

确保防火墙允许访问端口 8000：

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 二、本地连接方式

### 方式 1：直接使用 Interface（推荐）

这是最直接的方式，绕过 `Computer` 类的限制：

```python
import asyncio
from computer.interface.factory import InterfaceFactory

async def main():
    # 创建 interface 连接到远程服务器
    interface = InterfaceFactory.create_interface_for_os(
        os="linux",  # 或 "macos", "windows"
        ip_address="192.168.1.100",  # 远程主机 IP
    )
    
    try:
        # 等待连接就绪
        await interface.wait_for_ready(timeout=30)
        
        # 获取截图
        screenshot = await interface.screenshot()
        with open("screenshot.png", "wb") as f:
            f.write(screenshot)
        
        # 执行命令
        result = await interface.run_command("ls -la")
        print(result.stdout)
        
        # 鼠标和键盘操作
        await interface.move_cursor(100, 100)
        await interface.left_click()
        await interface.type_text("Hello!")
        
    finally:
        interface.close()

asyncio.run(main())
```

### 方式 2：修改 Computer 类支持远程连接

如果您需要使用完整的 `Computer` 对象功能，需要修改源码：

**修改文件**: `libs/python/computer/computer/computer.py`

**位置**: 第 266-269 行

**原代码**:
```python
if self.use_host_computer_server:
    self.logger.info("Using host computer server")
    # Set ip_address for host computer server mode
    ip_address = "localhost"
```

**修改为**:
```python
if self.use_host_computer_server:
    self.logger.info("Using host computer server")
    # Set ip_address for host computer server mode
    # Support remote host via self.host parameter
    ip_address = self.host if self.host != "localhost" else "127.0.0.1"
```

修改后可以这样使用：

```python
from computer import Computer

computer = Computer(
    os_type="linux",
    use_host_computer_server=True,
    host="192.168.1.100",  # 远程主机 IP
)

await computer.run()
screenshot = await computer.interface.screenshot()
```

### 方式 3：通过 Docker 连接远程 Docker 主机

如果远程主机运行的是 Docker，可以通过 `DOCKER_HOST` 环境变量连接：

```bash
# 在远程主机上启动 Docker 容器
docker run -d \
  --name my-cua \
  -p 8000:8000 \
  -p 6901:6901 \
  trycua/cua-ubuntu:latest

# 本地设置环境变量
export DOCKER_HOST=tcp://192.168.1.100:2375
```

```python
from computer import Computer, VMProviderType

# Docker provider 会使用 DOCKER_HOST 环境变量
computer = Computer(
    os_type="linux",
    provider_type=VMProviderType.DOCKER,
    name="my-cua",
)

await computer.run()
```

## 三、测试连接

### 使用测试脚本

```bash
# 测试 WebSocket 连接
cd libs/python/computer-server
python test_connection.py --host 192.168.1.100 --port 8000
```

### 使用简单测试脚本

```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://192.168.1.100:8000/ws"
    async with websockets.connect(uri) as ws:
        # 测试版本
        await ws.send(json.dumps({"command": "version", "params": {}}))
        response = await ws.recv()
        print(f"Version: {response}")
        
        # 测试屏幕尺寸
        await ws.send(json.dumps({"command": "get_screen_size", "params": {}}))
        response = await ws.recv()
        print(f"Screen size: {response}")

asyncio.run(test())
```

## 四、示例代码

完整示例请参考：
- `examples/remote_server_simple.py` - 简单连接示例
- `examples/remote_computer_server_example.py` - 完整功能示例

## 五、常见问题

### 1. 连接被拒绝

- 检查 computer-server 是否正在运行
- 检查防火墙设置
- 确认 IP 地址正确

### 2. 连接超时

- 检查网络连接
- 尝试增加 timeout 参数
- 确认远程主机可访问

### 3. 命令执行失败

- 确认远程操作系统类型正确（linux/macos/windows）
- 检查用户权限
- 查看 computer-server 日志

## 六、安全建议

1. **不要在公网暴露 computer-server**：computer-server 默认没有认证，仅在内网使用
2. **使用 VPN 或 SSH 隧道**：对于远程访问，建议通过 VPN 或 SSH 端口转发
3. **配置防火墙**：限制访问来源 IP

### SSH 隧道示例

```bash
# 在本地建立 SSH 隧道
ssh -L 8000:localhost:8000 user@remote-host

# 然后在本地连接到 localhost:8000
```

```python
interface = InterfaceFactory.create_interface_for_os(
    os="linux",
    ip_address="localhost",  # 通过 SSH 隧道访问
)
```

## 七、VNC 访问

computer-server 不包含 VNC 服务器。如果需要可视化访问：

### 在远程主机上运行 VNC + computer-server

**选项 1：使用 Docker 容器**
```bash
docker run -d \
  -p 5901:5901 \
  -p 6901:6901 \
  -p 8000:8000 \
  trycua/cua-xfce:latest
```

- VNC 直连：`vnc://remote-host:5901`
- Web 访问：`http://remote-host:6901`
- API 访问：`http://remote-host:8000`

**选项 2：手动配置**
```bash
# 安装 VNC 服务器
sudo apt install tigervnc-standalone-server

# 启动 VNC
vncserver :1 -geometry 1920x1080

# 在 VNC 会话中启动 computer-server
DISPLAY=:1 python -m computer_server
```

## 八、端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 8000 | computer-server API | WebSocket/HTTP API |
| 5901 | VNC Server | VNC 直连端口 |
| 6901 | noVNC | Web VNC 接口 |
| 8443 | computer-server (HTTPS) | 云服务使用 |

## 参考

- [Computer SDK 文档](docs/content/docs/computer-sdk/)
- [computer-server 源码](libs/python/computer-server/)
- [Docker 容器配置](libs/xfce/README.md)

