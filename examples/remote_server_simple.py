"""
远程代码执行示例：使用 RemoteCodeExecutor 工具类

本示例展示如何使用完全自动化的 RemoteCodeExecutor 工具类远程执行代码。

前提条件：
    远程主机需要先安装并启动 computer-server：
        pip install cua-computer-server
        python -m computer_server

✨ 核心特点：RemoteCodeExecutor
    一个完全自动化的远程代码执行器，强制使用 with 语句保证资源安全：
    ✅ 强制 with 语句（确保资源一定释放）
    ✅ 完全自动化（自动连接、执行、断开）
    ✅ Python 代码执行（单行/多行）
    ✅ Shell 命令/脚本执行
    ✅ 自动处理转义和编码问题
    ✅ 统一的错误处理
    ✅ JSON 结果自动解析
    ✅ 格式化的结果输出

🚀 最简单的使用方式（同步调用，必须使用 with）：
    # 使用 with 语句（自动管理连接）
    with RemoteCodeExecutor("10.xx.xx.32") as executor:
        # 直接执行（无需 await，就像普通函数一样）
        result = executor.run_python("print('Hello')")

        # 打印结果
        print(executor.format_result(result))
        # 或直接打印
        print(result)

        # 访问结果属性
        if result.success:
            print(result.stdout)
        else:
            print(result.error_message)
    # 退出 with 块时自动关闭连接

💡 也支持异步调用（如果你在异步上下文中）：
    # 使用 async with（自动管理连接）
    async with RemoteCodeExecutor("10.xx.xx.32") as executor:
        # 异步执行（需要 await）
        result = await executor.run_python_async("print('Hello')")

        # 打印结果
        print(executor.format_result(result))
    # 退出时自动关闭连接

📖 完整示例（所有方式都必须使用 with）：

1. 同步调用（推荐，最简单）：
    with RemoteCodeExecutor("10.xx.xx.32") as executor:
        # 执行 Python 代码
        result = executor.run_python("print('Hello')")
        print(executor.format_result(result))

        # 执行 Shell 命令
        result = executor.run_shell("whoami")
        print(executor.format_result(result))

        # 执行多行代码
        code = '''
import json
data = {"status": "ok"}
print(json.dumps(data))
'''
        result = executor.run_python(code, parse_json=True)
        print(result.data)  # 自动解析的 JSON
    # 退出 with 块时自动关闭连接

2. 异步调用（在异步上下文中使用）：
    async with RemoteCodeExecutor("10.xx.xx.32") as executor:
        # 使用异步方法
        result = await executor.run_python_async("print('Hello')")
        result = await executor.run_shell_async("whoami")
        # 退出时自动关闭

本示例包含的演示：
    - sync_example(): 同步方法示例（最简单，推荐，无需 async/await）
    - simple_example(): 异步方法示例（使用 await）
    - async_with_example(): 使用 async with 的异步示例
    - main(): 原始 interface API 示例（旧方法）
"""

import asyncio
import base64
import ipaddress
import json
import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional
from computer.interface.factory import InterfaceFactory


class RemoteResult:
    """
    远程代码执行结果的封装类

    提供便捷的属性访问和工具方法
    """

    def __init__(
        self,
        success: bool,
        code: int,
        stdout: str = "",
        stderr: str = "",
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """
        初始化执行结果

        Args:
            success: 是否执行成功
            code: 命令返回码（0 表示成功）
            stdout: 标准输出
            stderr: 标准错误输出
            data: 解析后的 JSON 数据（如果有）
            error: 错误信息（如果有）
        """
        self.success = success
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.data = data
        self.error = error

    @property
    def output(self) -> str:
        """获取标准输出（stdout 的别名）"""
        return self.stdout

    @property
    def is_success(self) -> bool:
        """检查是否执行成功（success 的别名）"""
        return self.success

    @property
    def has_error(self) -> bool:
        """检查是否有错误"""
        return not self.success or self.error is not None

    @property
    def error_message(self) -> str:
        """获取错误信息"""
        if self.error:
            return self.error
        elif self.stderr:
            return self.stderr
        elif not self.success:
            return f"执行失败，返回码: {self.code}"
        return ""

    def raise_for_error(self) -> None:
        """如果执行失败，抛出异常"""
        if not self.success:
            raise RuntimeError(self.error_message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（向后兼容）"""
        return {
            "success": self.success,
            "code": self.code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "data": self.data,
            "error": self.error,
        }

    def __str__(self) -> str:
        """字符串表示"""
        if self.success:
            return f"✓ 执行成功\n输出: {self.stdout.strip()}"
        else:
            return f"✗ 执行失败\n错误: {self.error_message}"

    def __repr__(self) -> str:
        """详细表示"""
        return (
            f"RemoteResult(success={self.success}, "
            f"code={self.code}, "
            f"stdout={self.stdout[:50]!r}...)"
        )

    def __bool__(self) -> bool:
        """布尔值：是否成功"""
        return self.success


class RemoteCodeExecutor:
    """
    远程代码执行工具类，支持 Python 和 Shell 代码

    完全自动化管理连接，用户只需调用执行方法即可
    """

    def __init__(
        self,
        host: str,
        port: int = 8000,
        os_type: Literal["linux", "macos", "windows"] = "linux",
        timeout: int = 30,
    ):
        """
        初始化远程代码执行器

        ⚠️  必须使用 with 语句来确保资源安全释放！

        Args:
            host: 远程主机 IP 地址（必须是合法的 IPv4 或 IPv6 地址）
            port: computer-server 端口，默认 8000
            os_type: 操作系统类型，"linux", "macos", "windows"
            timeout: 连接超时时间（秒），默认 30

        Raises:
            ValueError: 如果 host 不是合法的 IP 地址

        Examples:
            # 同步方式（推荐）
            with RemoteCodeExecutor("10.xx.136.32") as executor:
                result = executor.run_python("print('Hello')")
                result = executor.run_shell("whoami")
            # 退出 with 块时自动关闭连接

            # 异步方式
            async with RemoteCodeExecutor("10.xx.136.32") as executor:
                result = await executor.run_python_async("print('Hello')")
            # 退出 with 块时自动关闭连接
        """
        # 验证 IP 地址合法性
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(
                f"无效的 IP 地址: '{host}'\n"
                f"host 参数必须是合法的 IPv4 或 IPv6 地址。\n"
                f"示例：\n"
                f"  - IPv4: '192.168.1.100', '10.0.0.1'\n"
                f"  - IPv6: '::1', 'fe80::1'"
            )

        self.host: str = host
        self.port: int = port
        self.os_type: Literal["linux", "macos", "windows"] = os_type
        self.timeout: int = timeout
        self.interface: Optional[Any] = None
        self._connected: bool = False
        self._in_context: bool = False  # 跟踪是否在 with 块中

    async def _ensure_connected(self) -> None:
        """确保已连接（内部方法，自动连接）"""
        # 检查是否在 with 块中使用
        if not self._in_context:
            raise RuntimeError(
                "RemoteCodeExecutor 必须在 with 语句中使用以确保资源安全释放！\n\n"
                "正确用法：\n"
                "  with RemoteCodeExecutor('10.xx.xx.xx') as executor:\n"
                "      result = executor.run_python(\"print('Hello')\")\n\n"
                "或者异步方式：\n"
                "  async with RemoteCodeExecutor('10.xx.xx.32') as executor:\n"
                "      result = await executor.run_python_async(\"print('Hello')\")"
            )

        if self._connected and self.interface is not None:
            return

        try:
            # 创建 interface
            self.interface = InterfaceFactory.create_interface_for_os(
                os=self.os_type,
                ip_address=self.host,
                # port=self.port,  # 如果 InterfaceFactory 支持端口参数
            )

            # 等待连接就绪
            await self.interface.wait_for_ready(timeout=self.timeout)
            self._connected = True

        except Exception as e:
            raise ConnectionError(f"连接到 {self.host}:{self.port} 失败: {e}")

    def close(self) -> None:
        """
        关闭连接（内部方法）

        通常由 with 语句的 __exit__ 自动调用，不需要手动调用
        """
        if self.interface and self._connected:
            self.interface.close()
            self._connected = False
            self.interface = None
        self._in_context = False

    def __enter__(self):
        """支持同步 with 语法（推荐）"""
        self._in_context = True
        # 同步方法不能直接 await，所以这里不预先连接
        # 连接会在第一次调用 run_*() 时自动建立
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 时自动关闭连接"""
        self.close()
        return False

    async def __aenter__(self):
        """支持异步 async with 语法"""
        self._in_context = True
        await self._ensure_connected()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出 async with 时自动断开连接"""
        self.close()
        return False

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.interface is not None

    async def _execute(
        self,
        code: str,
        code_type: str = "python",
        parse_json: bool = False,
        python_cmd: str = "python3",
    ) -> RemoteResult:
        """
        内部方法：远程执行代码的核心实现

        这是一个私有方法，用户应使用公开的 run_*() 或 run_*_async() 方法

        Args:
            code: 要执行的代码（支持多行）
            code_type: 代码类型，"python" 或 "shell"
            parse_json: 是否尝试解析输出为 JSON
            python_cmd: Python 解释器命令，默认 "python3"

        Returns:
            RemoteResult: 执行结果对象，包含以下属性：
                - success: 是否执行成功
                - code: 返回码
                - stdout: 标准输出
                - stderr: 标准错误
                - data: 解析后的 JSON 数据（如果 parse_json=True）
                - error: 错误信息（如果有）
        """
        # 自动连接（如果未连接）
        try:
            await self._ensure_connected()
        except Exception as e:
            return RemoteResult(
                success=False,
                code=-1,
                stdout="",
                stderr="",
                data=None,
                error=f"连接失败: {e}",
            )

        code = code.strip()

        # 构造执行命令
        if code_type == "python":
            # Python 代码
            if "\n" in code or len(code) > 200:
                # 多行或较长的代码，使用 base64 编码
                encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
                command = f"{python_cmd} -c \"import base64; exec(base64.b64decode('{encoded}').decode('utf-8'))\""
            else:
                # 简单的单行代码，直接执行
                # 转义双引号
                escaped_code = code.replace('"', '\\"')
                command = f'{python_cmd} -c "{escaped_code}"'

        elif code_type == "shell":
            # Shell 代码
            if "\n" in code or len(code) > 200:
                # 多行 Shell 脚本，使用 base64 编码
                encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
                command = f'echo "{encoded}" | base64 -d | bash'
            else:
                # 简单命令，直接执行
                command = code
        else:
            return RemoteResult(
                success=False,
                code=-1,
                stdout="",
                stderr="",
                data=None,
                error=f"不支持的代码类型: {code_type}，请使用 'python' 或 'shell'",
            )

        # 执行命令
        try:
            if self.interface is None:
                raise RuntimeError("Interface 未初始化")
            result = await self.interface.run_command(command)
        except Exception as e:
            return RemoteResult(
                success=False,
                code=-1,
                stdout="",
                stderr=str(e),
                data=None,
                error=f"执行命令时出错: {e}",
            )

        # 构造返回结果
        success = result.returncode == 0
        error_msg = None if success else (result.stderr or "执行失败")
        data = None

        # 如果需要解析 JSON
        if parse_json and result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout.strip())
            except json.JSONDecodeError as e:
                error_msg = f"JSON 解析失败: {e}"
            except Exception as e:
                error_msg = f"处理输出时出错: {e}"

        return RemoteResult(
            success=success,
            code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            data=data,
            error=error_msg,
        )

    # ========== 同步方法（主要接口，推荐使用） ==========

    def run_python(
        self, code: str, parse_json: bool = False, python_cmd: str = "python3"
    ) -> RemoteResult:
        """
        执行 Python 代码（同步方法，推荐）

        用户可以直接调用，无需 await，内部自动处理异步操作

        Args:
            code: Python 代码
            parse_json: 是否解析 JSON 输出
            python_cmd: Python 命令，默认 "python3"

        Returns:
            RemoteResult: 执行结果对象

        Examples:
            # 不需要 await，直接调用
            executor = RemoteCodeExecutor("10.xx.xx.32")
            result = executor.run_python("print('Hello')")
            print(executor.format_result(result))
        """
        return self._run_async(
            self.run_python_async(code, parse_json=parse_json, python_cmd=python_cmd)
        )

    def run_shell(self, code: str) -> RemoteResult:
        """
        执行 Shell 命令（同步方法，推荐）

        用户可以直接调用，无需 await，内部自动处理异步操作

        Args:
            code: Shell 命令或脚本

        Returns:
            RemoteResult: 执行结果对象

        Examples:
            # 不需要 await，直接调用
            executor = RemoteCodeExecutor("10.xx.xx.32")
            result = executor.run_shell("whoami")
            print(executor.format_result(result))
        """
        return self._run_async(self.run_shell_async(code))

    def run(
        self,
        code: str,
        code_type: str = "python",
        parse_json: bool = False,
        python_cmd: str = "python3",
    ) -> RemoteResult:
        """
        执行代码的通用方法（同步方法，推荐）

        用户可以直接调用，无需 await，内部自动处理异步操作

        Args:
            code: 要执行的代码
            code_type: 代码类型，"python" 或 "shell"
            parse_json: 是否解析 JSON 输出
            python_cmd: Python 命令，默认 "python3"

        Returns:
            RemoteResult: 执行结果对象

        Examples:
            # 不需要 await，直接调用
            executor = RemoteCodeExecutor("10.xx.xx.32")
            result = executor.run("print('Hello')", code_type="python")
            print(executor.format_result(result))
        """
        return self._run_async(
            self.run_async(code, code_type=code_type, parse_json=parse_json, python_cmd=python_cmd)
        )

    # ========== 异步方法（在异步上下文中使用） ==========

    async def run_python_async(
        self, code: str, parse_json: bool = False, python_cmd: str = "python3"
    ) -> RemoteResult:
        """
        执行 Python 代码（异步方法）

        在异步上下文中使用，需要 await

        Args:
            code: Python 代码
            parse_json: 是否解析 JSON 输出
            python_cmd: Python 命令，默认 "python3"

        Returns:
            RemoteResult: 执行结果对象

        Examples:
            # 在异步函数中使用
            async def my_function():
                executor = RemoteCodeExecutor("10.xx.xx.32")
                result = await executor.run_python_async("print('Hello')")
                print(executor.format_result(result))
        """
        return await self.run_async(
            code, code_type="python", parse_json=parse_json, python_cmd=python_cmd
        )

    async def run_shell_async(self, code: str) -> RemoteResult:
        """
        执行 Shell 命令（异步方法）

        在异步上下文中使用，需要 await

        Args:
            code: Shell 命令或脚本

        Returns:
            RemoteResult: 执行结果对象

        Examples:
            # 在异步函数中使用
            async def my_function():
                executor = RemoteCodeExecutor("10.xx.xx.32")
                result = await executor.run_shell_async("whoami")
                print(executor.format_result(result))
        """
        return await self.run_async(code, code_type="shell")

    async def run_async(
        self,
        code: str,
        code_type: str = "python",
        parse_json: bool = False,
        python_cmd: str = "python3",
    ) -> RemoteResult:
        """
        执行代码的通用方法（异步方法）

        这是底层的异步执行方法，在异步上下文中使用，需要 await

        Args:
            code: 要执行的代码
            code_type: 代码类型，"python" 或 "shell"
            parse_json: 是否解析 JSON 输出
            python_cmd: Python 命令，默认 "python3"

        Returns:
            RemoteResult: 执行结果对象

        Examples:
            # 在异步函数中使用
            async def my_function():
                executor = RemoteCodeExecutor("10.xx.xx.32")
                result = await executor.run_async("print('Hello')", code_type="python")
                print(executor.format_result(result))
        """
        return await self._execute(
            code, code_type=code_type, parse_json=parse_json, python_cmd=python_cmd
        )

    def _run_async(self, coro) -> RemoteResult:
        """
        内部方法：在同步上下文中运行异步代码

        自动检测是否已在事件循环中，并选择合适的执行方式
        """
        try:
            # 检查是否已在运行的事件循环中
            loop = asyncio.get_running_loop()
            # 如果已在事件循环中，不能使用 asyncio.run()
            # 这种情况下用户应该使用异步版本的方法
            raise RuntimeError(
                "检测到已在运行的事件循环中。\n"
                "请使用异步方法：await executor.run_python_async() 而不是 executor.run_python()\n"
                "或者在非异步上下文中调用此方法。"
            )
        except RuntimeError:
            # 没有运行的事件循环，可以创建新的
            pass

        # 创建新的事件循环并运行
        try:
            return asyncio.run(coro)
        except Exception as e:
            return RemoteResult(
                success=False,
                code=-1,
                stdout="",
                stderr=str(e),
                data=None,
                error=f"执行时出错: {e}",
            )

    def format_result(self, result: RemoteResult) -> str:
        """
        格式化输出结果，便于打印

        Args:
            result: RemoteResult 对象

        Returns:
            格式化的字符串
        """
        # 直接使用 RemoteResult 的 __str__ 方法
        return str(result)


async def main(REMOTE_HOST):
    # 1. 配置远程服务器信息
    OS_TYPE = "linux"  # 或 "macos", "windows"

    print(f"正在连接到远程 computer-server: {REMOTE_HOST}")

    # 2. 创建 interface 连接到远程服务器
    interface = InterfaceFactory.create_interface_for_os(
        os=OS_TYPE,
        ip_address=REMOTE_HOST,
    )

    try:
        # 3. 等待连接就绪
        await interface.wait_for_ready(timeout=30)
        print("✓ 连接成功！")

        # 4. 获取屏幕尺寸
        screen_size = await interface.get_screen_size()
        print(f"✓ 屏幕尺寸: {screen_size}")

        # 5. 截图测试
        screenshot = await interface.screenshot()
        output_dir = Path("./output")
        output_dir.mkdir(exist_ok=True)

        with open(output_dir / "remote_screenshot.png", "wb") as f:
            f.write(screenshot)
        print(f"✓ 截图已保存到: {output_dir / 'remote_screenshot.png'}")

        # 6. 命令执行测试
        result = await interface.run_command("pwd")
        print(f"✓ 当前目录: {result.stdout.strip()}")

        # 7. 远程执行 pyautogui 代码示例
        print("\n=== 远程执行 pyautogui 代码 ===")

        # 方法1: 使用 run_command 执行简单的 pyautogui 命令
        print("\n方法1: 使用 run_command 执行 pyautogui")

        # 获取屏幕尺寸
        pyautogui_cmd = 'python3 -c "import pyautogui; print(pyautogui.size())"'
        result = await interface.run_command(pyautogui_cmd)
        if result.returncode == 0:
            print(f"✓ PyAutoGUI 屏幕尺寸: {result.stdout.strip()}")
        else:
            print(f"✗ 执行失败: {result.stderr.strip()}")

        # 获取鼠标位置
        pyautogui_cmd = "python3 -c \"import pyautogui; pos = pyautogui.position(); print(f'x={pos.x}, y={pos.y}')\""
        result = await interface.run_command(pyautogui_cmd)
        print(f"✓ 当前鼠标位置: {result.stdout.strip()}")

        # 移动鼠标
        print("\n正在移动鼠标到 (500, 500)...")
        pyautogui_cmd = 'python3 -c "import pyautogui; pyautogui.moveTo(500, 500, duration=1)"'
        await interface.run_command(pyautogui_cmd)
        print("✓ 鼠标移动成功")

        # 移动后验证位置
        await asyncio.sleep(1)  # 等待移动完成
        pyautogui_cmd = "python3 -c \"import pyautogui; pos = pyautogui.position(); print(f'x={pos.x}, y={pos.y}')\""
        result = await interface.run_command(pyautogui_cmd)
        print(f"✓ 移动后鼠标位置: {result.stdout.strip()}")

    except Exception as e:
        print(f"✗ 错误: {e}")
    finally:
        interface.close()
        print("连接已关闭")


def sync_example(REMOTE_HOST):
    """
    完全同步的示例（最简单，推荐给初学者）

    不需要 async/await，就像普通函数一样调用
    """
    print(f"\n=== 完全同步示例（无需 async/await） ===")
    print(f"目标主机: {REMOTE_HOST}\n")

    # 演示：IP 地址验证
    print("【演示】IP 地址验证")
    print("-" * 50)

    # 测试无效的 IP 地址
    invalid_hosts = ["invalid.host", "256.256.256.256", "abc.def.ghi.jkl"]
    for invalid_host in invalid_hosts:
        try:
            executor = RemoteCodeExecutor(invalid_host)
        except ValueError as e:
            print(f"✓ 检测到无效 IP '{invalid_host}'")

    # 测试有效的 IP 地址
    print(f"✓ 验证有效 IP '{REMOTE_HOST}' 通过")
    print()

    # 方式1: 使用 with 语句（推荐，自动关闭）
    print("【方式1】使用 with 语句（推荐，自动关闭）")
    print("-" * 50)

    with RemoteCodeExecutor(REMOTE_HOST) as executor:
        # 示例1: 执行 Python 代码（不需要 await）
        print("【示例1】执行 Python 代码...")
        result = executor.run_python("print('Hello from Python!')")
        print(executor.format_result(result))

        # 示例2: 双击操作
        print("\n【示例2】双击浏览器图标...")
        result = executor.run_python("import pyautogui; pyautogui.doubleClick(x=71, y=374)")
        print(executor.format_result(result))

        time.sleep(1)

        # 示例3: 获取鼠标位置并解析 JSON
        print("\n【示例3】获取鼠标位置...")
        code = """
import pyautogui
import json
pos = pyautogui.position()
print(json.dumps({"x": pos.x, "y": pos.y}))
"""
        result = executor.run_python(code, parse_json=True)
        print(executor.format_result(result))
        if result.data:
            print(f"   → 鼠标坐标: ({result.data['x']}, {result.data['y']})")

        # 示例4: 执行 Shell 命令
        print("\n【示例4】执行 Shell 命令...")
        result = executor.run_shell("whoami && hostname")
        print(executor.format_result(result))

    # 退出 with 块后自动调用 close()
    print("\n✓ 退出 with 块，自动关闭连接")


async def simple_example():
    """
    异步示例：展示异步方法的使用（必须使用 async with）
    在异步上下文中使用 await
    """
    REMOTE_HOST = "10.xx.xx.32"  # 修改为您的远程主机 IP

    print(f"\n=== 异步示例：使用 async with ===")
    print(f"目标主机: {REMOTE_HOST}\n")

    # 使用 async with 执行多个操作
    print("【示例】使用 async with 执行多个操作")
    print("-" * 50)

    async with RemoteCodeExecutor(REMOTE_HOST) as executor:
        # 执行1: 双击操作
        print("执行双击操作...")
        result = await executor.run_python_async(
            "import pyautogui; pyautogui.doubleClick(x=71, y=374)"
        )
        print(executor.format_result(result))

        # 执行2: 获取鼠标位置
        print("\n执行获取鼠标位置...")
        code = """
import pyautogui
import json
pos = pyautogui.position()
print(json.dumps({"x": pos.x, "y": pos.y}))
"""
        result = await executor.run_python_async(code, parse_json=True)
        print(executor.format_result(result))
        if result.data:
            print(f"   → 鼠标坐标: ({result.data['x']}, {result.data['y']})")

        # 执行3: 多个命令
        print("\n执行多个 Shell 命令...")
        result1 = await executor.run_python_async("print('Hello from Python!')")
        print(f"1. {executor.format_result(result1)}")

        result2 = await executor.run_shell_async("whoami")
        print(f"2. {executor.format_result(result2)}")

        result3 = await executor.run_shell_async("hostname")
        print(f"3. {executor.format_result(result3)}")

    # 退出 async with 后自动关闭
    print("\n✓ 退出 async with 块，连接已自动关闭")


async def async_with_example(REMOTE_HOST):
    """
    使用 async with 的示例（自动清理资源）
    """
    print(f"\n=== 使用 async with 示例 ===")
    print(f"目标主机: {REMOTE_HOST}\n")

    # 使用 async with 确保资源自动清理
    async with RemoteCodeExecutor(REMOTE_HOST) as executor:
        print("执行操作...")

        result1 = await executor.run_python_async("print('Hello from Python!')")
        print(executor.format_result(result1))

        result2 = await executor.run_shell_async("uname -a")
        print(executor.format_result(result2))

    # 退出 async with 后自动关闭连接
    print("\n✓ 连接已自动关闭")


if __name__ == "__main__":
    print("=" * 60)
    print("RemoteCodeExecutor - 远程代码执行工具")
    print("=" * 60)

    print("\n✨ 核心特点：")
    print("   🔒 强制使用 with 语句，确保资源安全释放")
    print("   ✅ 完全自动化，无需手动管理连接")
    print("   ✅ 支持同步调用，无需 async/await")
    print("   ✅ 同时支持异步调用（async with）")

    print("\n可用的示例：")
    print("1. sync_example() - 同步示例（推荐，最简单，使用 with）")
    print("2. simple_example() - 异步示例（使用 async with）")
    print("3. async_with_example() - async with 详细示例")
    print("4. main() - 原始 interface API 示例（旧方法）")

    import os
    from dotenv import load_dotenv

    # 加载 .env 文件中的环境变量
    load_dotenv()

    REMOTE_HOST = os.getenv("REMOTE_HOST")

    if not REMOTE_HOST:
        print("\n⚠️  错误：未设置 REMOTE_HOST 环境变量！")
        exit(1)

    # 默认运行同步示例（最简单）
    print("\n运行: sync_example()")
    print("=" * 60)
    sync_example(REMOTE_HOST)

    # 如需运行其他示例，取消注释下面的行：
    # asyncio.run(simple_example())
    # asyncio.run(async_with_example())
    # asyncio.run(main())
