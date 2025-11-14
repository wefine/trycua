"""
VncComputer 使用示例

展示如何使用 VncComputer 连接到已存在的远程服务器。
VncComputer 继承自 Computer，但不需要启动/停止 VM，只需要 IP 和端口即可连接。

前提条件：
    远程主机需要先安装并启动 computer-server：
        pip install cua-computer-server
        python -m computer_server

特点：
    ✅ 只需要 IP 和端口
    ✅ 不需要启动/停止 VM
    ✅ 继承 Computer 的所有功能
    ✅ 可在 ComputerAgent 中使用
    ✅ 支持所有 interface 操作
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# 导入 VncComputer 和 Computer
from computer import VncComputer, Computer


async def basic_example(remote_host: str):
    """
    基础示例：连接并执行基本操作
    """
    print("\n" + "=" * 60)
    print("示例 1：基础操作")
    print("=" * 60)

    # 使用 async with 自动管理连接
    async with VncComputer(ip=remote_host, os_type="linux") as computer:
        print(f"✓ 已连接到: {computer}")

        # 获取屏幕尺寸
        screen_size = await computer.interface.get_screen_size()
        print(f"✓ 屏幕尺寸: {screen_size}")

        # 执行命令
        result = await computer.interface.run_command("whoami")
        print(f"✓ 当前用户: {result.stdout.strip()}")

        result = await computer.interface.run_command("hostname")
        print(f"✓ 主机名: {result.stdout.strip()}")

        # 获取当前工作目录
        result = await computer.interface.run_command("pwd")
        print(f"✓ 当前目录: {result.stdout.strip()}")

    print("\n✓ 连接已自动关闭")


async def screenshot_example(remote_host: str):
    """
    示例 2：截图操作
    """
    print("\n" + "=" * 60)
    print("示例 2：截图操作")
    print("=" * 60)

    async with VncComputer(ip=remote_host, os_type="linux") as computer:
        print(f"✓ 已连接到: {remote_host}")

        # 截图
        print("正在截图...")
        screenshot = await computer.interface.screenshot()

        # 保存截图
        output_dir = Path("./output")
        output_dir.mkdir(exist_ok=True)

        screenshot_path = output_dir / "vnc_screenshot.png"
        with open(screenshot_path, "wb") as f:
            f.write(screenshot)

        print(f"✓ 截图已保存到: {screenshot_path}")


async def mouse_keyboard_example(remote_host: str):
    """
    示例 3：鼠标和键盘操作
    """
    print("\n" + "=" * 60)
    print("示例 3：鼠标和键盘操作")
    print("=" * 60)

    async with VncComputer(ip=remote_host, os_type="linux") as computer:
        print(f"✓ 已连接到: {remote_host}")

        # 获取当前鼠标位置
        code = """
import pyautogui
import json
pos = pyautogui.position()
print(json.dumps({"x": pos.x, "y": pos.y}))
"""
        result = await computer.interface.run_command(
            f'python3 -c "{code.replace(chr(10), " ").replace(chr(34), chr(92)+chr(34))}"'
        )
        print(f"✓ 当前鼠标位置: {result.stdout.strip()}")

        # 移动鼠标
        print("\n正在移动鼠标到 (500, 500)...")
        await computer.interface.run_command(
            'python3 -c "import pyautogui; pyautogui.moveTo(500, 500, duration=0.5)"'
        )
        print("✓ 鼠标已移动")

        # 等待一下
        await asyncio.sleep(0.5)

        # 验证鼠标位置
        result = await computer.interface.run_command(
            f'python3 -c "{code.replace(chr(10), " ").replace(chr(34), chr(92)+chr(34))}"'
        )
        print(f"✓ 移动后的鼠标位置: {result.stdout.strip()}")


async def pyautogui_example(remote_host: str):
    """
    示例 4：使用 pyautogui 执行复杂操作
    """
    print("\n" + "=" * 60)
    print("示例 4：PyAutoGUI 复杂操作")
    print("=" * 60)

    async with VncComputer(ip=remote_host, os_type="linux") as computer:
        print(f"✓ 已连接到: {remote_host}")

        # 获取屏幕信息
        print("\n【获取屏幕信息】")
        result = await computer.interface.run_command(
            'python3 -c "import pyautogui; print(pyautogui.size())"'
        )
        print(f"屏幕尺寸: {result.stdout.strip()}")

        # 双击操作示例
        print("\n【双击操作示例】")
        print("将在坐标 (100, 100) 执行双击...")
        await computer.interface.run_command(
            'python3 -c "import pyautogui; pyautogui.doubleClick(100, 100)"'
        )
        print("✓ 双击完成")

        # 输入文字示例
        print("\n【输入文字示例】")
        print("模拟输入文字...")
        await computer.interface.run_command(
            'python3 -c "import pyautogui; pyautogui.write(\'Hello from VncComputer\', interval=0.1)"'
        )
        print("✓ 文字输入完成")


async def multi_command_example(remote_host: str):
    """
    示例 5：执行多个命令
    """
    print("\n" + "=" * 60)
    print("示例 5：批量执行命令")
    print("=" * 60)

    async with VncComputer(ip=remote_host, os_type="linux") as computer:
        print(f"✓ 已连接到: {remote_host}")

        # 定义多个命令
        commands = [
            ("获取系统信息", "uname -a"),
            ("查看内存使用", "free -h"),
            ("查看磁盘使用", "df -h"),
            ("查看当前进程", "ps aux | head -10"),
        ]

        # 执行所有命令
        for description, cmd in commands:
            print(f"\n【{description}】")
            result = await computer.interface.run_command(cmd)
            if result.returncode == 0:
                print(result.stdout.strip())
            else:
                print(f"✗ 错误: {result.stderr.strip()}")


async def error_handling_example(remote_host: str):
    """
    示例 6：错误处理
    """
    print("\n" + "=" * 60)
    print("示例 6：错误处理")
    print("=" * 60)

    try:
        async with VncComputer(ip=remote_host, os_type="linux") as computer:
            print(f"✓ 已连接到: {remote_host}")

            # 执行一个会失败的命令
            print("\n执行一个不存在的命令...")
            result = await computer.interface.run_command("this_command_does_not_exist")

            if result.returncode == 0:
                print(f"✓ 成功: {result.stdout}")
            else:
                print(f"✗ 命令执行失败 (返回码: {result.returncode})")
                print(f"   错误信息: {result.stderr.strip()}")

    except Exception as e:
        print(f"\n✗ 发生异常: {e}")


async def reconnect_example(remote_host: str):
    """
    示例 7：重新连接
    """
    print("\n" + "=" * 60)
    print("示例 7：重新连接")
    print("=" * 60)

    # 创建 VncComputer 实例
    computer = VncComputer(ip=remote_host, os_type="linux")

    try:
        # 第一次连接
        print("\n【第一次连接】")
        await computer.run()
        print(f"✓ 已连接到: {computer}")

        result = await computer.interface.run_command("whoami")
        print(f"✓ 当前用户: {result.stdout.strip()}")

        # 断开连接
        print("\n【断开连接】")
        await computer.stop()
        print("✓ 连接已断开")

        # 重新连接
        print("\n【重新连接】")
        await computer.restart()
        print("✓ 重新连接成功")

        result = await computer.interface.run_command("hostname")
        print(f"✓ 主机名: {result.stdout.strip()}")

    finally:
        # 最后确保断开连接
        await computer.stop()
        print("\n✓ 最终清理完成")


async def computer_agent_example(remote_host: str):
    """
    示例 8：在 ComputerAgent 中使用 VncComputer
    
    这展示了 VncComputer 可以像 Computer 一样在 Agent 中使用
    """
    print("\n" + "=" * 60)
    print("示例 8：在 ComputerAgent 中使用")
    print("=" * 60)

    # VncComputer 继承自 Computer，所以可以直接用在需要 Computer 的地方
    async with VncComputer(ip=remote_host, os_type="linux") as computer:
        print(f"✓ 已连接到: {remote_host}")
        print(f"✓ Computer 类型: {type(computer).__name__}")
        print(f"✓ 是否是 Computer 实例: {isinstance(computer, Computer)}")

        # 展示可以使用 Computer 的所有方法
        print("\n使用 Computer 的方法:")

        # interface 属性
        print(f"  - computer.interface: {computer.interface}")

        # 获取 IP（对于 VncComputer 返回配置的 IP）
        ip = await computer.get_ip()
        print(f"  - computer.get_ip(): {ip}")

        # 其他 Computer 方法也都可用
        print("\n✓ VncComputer 完全兼容 Computer API")
        print("✓ 可以直接用于 ComputerAgent 或其他需要 Computer 的场景")


async def main():
    """主函数：运行所有示例"""
    # 加载环境变量
    load_dotenv()

    # 从环境变量获取远程主机 IP
    remote_host = os.getenv("REMOTE_HOST")

    if not remote_host:
        print("❌ 错误：未设置 REMOTE_HOST 环境变量！")
        print("\n请在 .env 文件中设置：")
        print("  REMOTE_HOST=your.remote.ip.address")
        return

    print("=" * 60)
    print("VncComputer 使用示例")
    print("=" * 60)
    print(f"\n目标主机: {remote_host}")
    print("\n提示：VncComputer 继承自 Computer，但不需要启动/停止 VM")
    print("      只需要提供 IP 和端口即可连接到已运行的远程服务器")

    try:
        # 运行所有示例
        await basic_example(remote_host)
        await screenshot_example(remote_host)
        await mouse_keyboard_example(remote_host)
        await pyautogui_example(remote_host)
        await multi_command_example(remote_host)
        await error_handling_example(remote_host)
        await reconnect_example(remote_host)
        await computer_agent_example(remote_host)

        print("\n" + "=" * 60)
        print("✓ 所有示例运行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 运行示例时发生错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())

