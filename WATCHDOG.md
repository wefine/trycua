# Watchdog 看门狗设计说明

## 📋 核心用途

这是一个**服务器健康监控和自动恢复系统**，专门用于监控 Computer API 服务器的运行状态。当服务器出现故障时，能够自动检测并尝试重启服务，确保服务的高可用性。

## 🏗️ 设计要点

### 1. 平台限制

```python
if platform.system() not in ["Linux", "Darwin"]:
    raise RuntimeError("Watchdog is only supported on Unix/Linux systems")
```

仅支持 Unix/Linux 系统（包括 macOS），因为依赖于 `fcntl`、`lsof` 等 Unix 特有工具。

### 2. 单例保护机制

```python
def instance_already_running(label="watchdog"):
    """
    Detect if an an instance with the label is already running, globally
    at the operating system level.

    Using `os.open` ensures that the file pointer won't be closed
    by Python's garbage collector after the function's scope is exited.

    The lock will be released when the program exits, or could be
    released if the file pointer were closed.
    """

    lock_file_pointer = os.open(f"/tmp/instance_{label}.lock", os.O_WRONLY | os.O_CREAT)

    try:
        fcntl.lockf(lock_file_pointer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        already_running = False
    except IOError:
        already_running = True

    return already_running
```

使用文件锁机制防止多个看门狗实例同时运行。

### 3. 健康检查机制

```python
async def ping(self) -> bool:
    """
    Test connection to the WebSocket endpoint.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Create a simple ping message
        ping_message = {"command": "get_screen_size", "params": {}}

        # Try to connect to the WebSocket
        async with websockets.connect(
            self.ws_uri, max_size=1024 * 1024 * 10  # 10MB limit to match server
        ) as websocket:
            # Send ping message
            await websocket.send(json.dumps(ping_message))

            # Wait for any response or just close
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                logger.debug(f"Ping response received: {response[:100]}...")
                return True
            except asyncio.TimeoutError:
                return False
    except Exception as e:
        logger.warning(f"Ping failed: {e}")
        return False
```

健康检查特点：
- 通过 WebSocket 连接发送 `get_screen_size` 命令
- 5秒超时机制
- 根据响应判断服务器是否正常

### 4. 故障检测策略

```python
consecutive_failures = 0
max_failures = 3

while self.running:
    try:
        success = await self.ping()

        if success:
            if consecutive_failures > 0:
                logger.info("Server connection restored")
            consecutive_failures = 0
            logger.debug("Ping successful")
        else:
            consecutive_failures += 1
            logger.warning(f"Ping failed ({consecutive_failures}/{max_failures})")

            if consecutive_failures >= max_failures:
                logger.error(
                    f"Server appears to be down after {max_failures} consecutive failures"
                )

                # Attempt to restart the server
                if self.restart_enabled:
                    logger.info("Attempting automatic server restart...")
                    restart_success = self.restart_server()

                    if restart_success:
                        logger.info("Server restart initiated, waiting before next ping...")
                        # Wait longer after restart attempt
                        await asyncio.sleep(self.ping_interval * 2)
                        consecutive_failures = 0  # Reset counter after restart attempt
                    else:
                        logger.error("Server restart failed")
                else:
                    logger.warning("Automatic restart is disabled")
```

故障检测策略：
- **连续失败阈值**：3次失败后触发重启
- **故障恢复检测**：成功恢复后记录日志
- **可配置重启**：支持禁用自动重启功能

### 5. 智能重启机制

重启流程分为以下步骤：

#### 步骤 1：终止旧进程

```python
def kill_processes_on_port(self, port: int) -> bool:
    """
    Kill any processes using the specified port.

    Args:
        port: Port number to check and kill processes on

    Returns:
        True if processes were killed or none found, False on error
    """
    try:
        # Find processes using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            logger.info(f"Found {len(pids)} processes using port {port}: {pids}")

            # Kill each process
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(["kill", "-9", pid.strip()], timeout=5)
                        logger.info(f"Killed process {pid}")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Timeout killing process {pid}")
                    except Exception as e:
                        logger.warning(f"Error killing process {pid}: {e}")

            return True
        else:
            logger.debug(f"No processes found using port {port}")
            return True

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout finding processes on port {port}")
        return False
    except Exception as e:
        logger.error(f"Error finding processes on port {port}: {e}")
        return False
```

使用 `lsof` 找到占用端口的进程，用 `kill -9` 强制终止。

#### 步骤 2：等待清理

```python
# Wait a moment for processes to die
time.sleep(2)
```

等待2秒让进程完全退出。

#### 步骤 3：模式区分重启

```python
# Try to restart the server
# In container mode, we can't easily restart, so just log
if self.container_name:
    logger.warning("Container mode detected - cannot restart server automatically")
    logger.warning("Container orchestrator should handle restart")
    return False
else:
    # For local mode, try to restart the CLI
    logger.info("Attempting to restart local server...")

    # Get the current Python executable and script
    python_exe = sys.executable

    # Build command with all original CLI arguments
    cmd = [python_exe, "-m", "computer_server.cli"]

    # Add all CLI arguments except watchdog-related ones
    for key, value in self.cli_args.items():
        if key in ["watchdog", "watchdog_interval", "no_restart"]:
            continue  # Skip watchdog args to avoid recursive watchdog

        # Convert underscores to hyphens for CLI args
        arg_name = f"--{key.replace('_', '-')}"

        if isinstance(value, bool):
            if value:  # Only add flag if True
                cmd.append(arg_name)
        else:
            cmd.extend([arg_name, str(value)])

    logger.info(f"Starting server with command: {' '.join(cmd)}")

    # Start process in background
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    logger.info("Server restart initiated")
    return True
```

- **容器模式**：不重启，由容器编排器（如 Kubernetes）处理
- **本地模式**：重新构建 CLI 命令并在后台启动新进程

#### 步骤 4：参数保留

保留原始 CLI 参数（排除看门狗相关参数，避免递归）。

### 6. 双模式支持

```python
@property
def ws_uri(self) -> str:
    """Get the WebSocket URI using the current IP address.

    Returns:
        WebSocket URI for the Computer API Server
    """
    ip_address = (
        "localhost"
        if not self.container_name
        else f"{self.container_name}.containers.cloud.trycua.com"
    )
    protocol = "wss" if self.container_name else "ws"
    port = "8443" if self.container_name else "8000"
    return f"{protocol}://{ip_address}:{port}/ws"
```

支持两种运行模式：
- **本地模式**：`ws://localhost:8000/ws`
- **云容器模式**：`wss://{container_name}.containers.cloud.trycua.com:8443/ws`

## 🎯 使用场景

1. **开发环境**：本地开发时自动恢复崩溃的服务器
2. **生产环境**：提供额外的监控层，在容器编排器之外
3. **长时间运行**：确保需要持续运行的服务器任务不中断

## 💡 设计亮点

- ✅ **异步设计**：使用 `asyncio` 实现非阻塞监控
- ✅ **渐进式故障检测**：避免网络抖动导致的误判
- ✅ **优雅降级**：容器模式下不强制重启
- ✅ **可配置性**：支持自定义 ping 间隔和禁用重启
- ✅ **完整的日志**：详细记录所有操作便于调试
- ✅ **单例保护**：使用文件锁防止多实例冲突
- ✅ **参数传递**：重启时保留原始启动参数

## 📝 使用示例

### 命令行独立运行

```bash
python -m computer_server.watchdog --host localhost --port 8000 --ping-interval 30
```

### 在代码中使用

```python
import asyncio
from computer_server.watchdog import run_watchdog

# CLI 参数
cli_args = {
    "host": "localhost",
    "port": 8000,
}

# 运行看门狗
asyncio.run(run_watchdog(cli_args, ping_interval=30))
```

### 与服务器集成

看门狗通常会在服务器启动时作为独立进程或线程启动，监控主服务器进程。

## ⚙️ 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `cli_args` | `dict` | `{}` | 服务器启动的 CLI 参数 |
| `ping_interval` | `int` | `30` | 健康检查间隔（秒） |
| `host` | `str` | `"localhost"` | 服务器主机地址 |
| `port` | `int` | `8000` | 服务器端口 |
| `restart_enabled` | `bool` | `True` | 是否启用自动重启 |

## 🔍 日志级别

- `DEBUG`：每次 ping 的详细信息
- `INFO`：正常状态变化（启动、恢复、重启）
- `WARNING`：ping 失败、重启禁用
- `ERROR`：连续失败、重启失败

## ⚠️ 注意事项

1. **平台限制**：仅支持 Unix/Linux/macOS 系统
2. **容器环境**：在容器中运行时不会自动重启服务器
3. **端口冲突**：确保指定的端口没有被其他服务占用
4. **权限要求**：需要足够的权限来终止进程（kill 命令）
5. **单例运行**：同一标签的看门狗只能运行一个实例

## 🔧 故障排除

### 看门狗无法启动

检查是否已有实例在运行：
```bash
ls -la /tmp/instance_watchdog.lock
```

### 重启失败

检查日志中的错误信息，常见原因：
- 端口被占用
- 权限不足
- CLI 参数错误
- Python 环境问题

### Ping 持续失败

检查服务器是否真的在运行：
```bash
# 检查端口监听
lsof -i :8000

# 检查 WebSocket 连接
wscat -c ws://localhost:8000/ws
```

## 📚 相关文件

- `watchdog.py` - 看门狗主模块
- `cli.py` - 服务器 CLI 入口
- `main.py` - 服务器主逻辑

---

*本文档生成于 2025-11-03*



