"""
VncComputer - 直接连接到已存在的 VNC 服务器

继承自 Computer，但不需要启动/停止 VM，只需要 IP 和端口即可连接。
适用于连接到已经运行的远程桌面或 VNC 服务器。
"""

import asyncio
import logging
import time
import traceback
from typing import Optional, Union, cast

from .computer import Computer, OSType
from .interface.factory import InterfaceFactory
from .logger import Logger, LogLevel


class VncComputer(Computer):
    """
    VNC Computer - 直接连接到已存在的 VNC/远程桌面服务器

    继承自 Computer，但跳过了 VM 的启动/停止流程，直接连接到指定的 IP 和端口。
    适用于：
    - 已经运行的 VNC 服务器
    - 远程桌面服务
    - Docker 容器中已经运行的 computer-server
    - 任何已经运行 computer-server 的远程主机

    Example:
        # 连接到远程主机
        async with VncComputer(ip="192.168.1.100", os_type="linux") as computer:
            # 使用 computer.interface 进行操作
            screenshot = await computer.interface.screenshot()
            result = await computer.interface.run_command("ls -la")
    """

    def __init__(
        self,
        ip: str,
        port: int = 8000,
        os_type: OSType = "linux",
        verbosity: Union[int, LogLevel] = logging.INFO,
        telemetry_enabled: bool = False,
    ):
        """
        初始化 VncComputer

        Args:
            ip: 远程主机的 IP 地址
            port: computer-server 的端口（默认 8000）
            os_type: 操作系统类型 ('linux', 'macos', 'windows')
            verbosity: 日志级别
            telemetry_enabled: 是否启用遥测
        """
        # 存储 VNC 连接参数
        self.vnc_ip = ip
        self.vnc_port = port

        # 调用父类的 __init__，使用 use_host_computer_server 模式
        # 这样可以避免 VM provider 的初始化
        super().__init__(
            os_type=os_type,
            use_host_computer_server=True,  # 关键：不启动 VM
            verbosity=verbosity,
            telemetry_enabled=telemetry_enabled,
            port=port,
            host=ip,
        )

        # 覆盖父类设置的 host
        self.host = ip
        self.port = port

        self.logger.info(f"VncComputer 初始化: {ip}:{port} (OS: {os_type})")

    async def run(self) -> Optional[str]:
        """
        初始化连接到远程 VNC/computer-server

        不启动 VM，直接连接到指定的 IP 和端口
        """
        # 如果已经初始化，跳过
        if hasattr(self, "_initialized") and self._initialized:
            self.logger.info("VncComputer 已经初始化，跳过重复初始化")
            return None

        self.logger.info(f"连接到远程 computer-server: {self.vnc_ip}:{self.vnc_port}")
        start_time = time.time()

        try:
            # 使用指定的 IP 地址（不需要启动 VM）
            ip_address = self.vnc_ip

            # 创建 interface
            self.logger.info(f"初始化 interface for {self.os_type} at {ip_address}:{self.vnc_port}")
            from .interface.base import BaseComputerInterface

            interface = cast(
                BaseComputerInterface,
                InterfaceFactory.create_interface_for_os(
                    os=cast(OSType, self.os_type),
                    ip_address=ip_address,
                ),
            )
            self._interface = interface
            self._original_interface = interface

            # 等待 WebSocket 连接就绪
            self.logger.info("正在连接到 WebSocket interface...")
            try:
                await self._interface.wait_for_ready(timeout=30)
                self.logger.info("WebSocket interface 连接成功")
            except TimeoutError as e:
                self.logger.error(f"连接到 WebSocket interface 失败: {ip_address}:{self.vnc_port}")
                raise TimeoutError(
                    f"无法连接到 WebSocket interface at {ip_address}:{self.vnc_port}/ws: {str(e)}"
                )

            # 标记为已初始化
            self._initialized = True
            self._running = True

            # 设置为默认 computer（用于 remote decorators）
            from . import helpers

            helpers.set_default_computer(self)

            self.logger.info("VncComputer 成功连接并初始化")

        except Exception as e:
            self.logger.error(f"VncComputer 初始化失败: {e}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"无法连接到 VNC computer server: {e}")
        finally:
            # 记录连接时间
            duration_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"VncComputer 连接耗时 {duration_ms:.2f}ms")

        return ip_address

    async def stop(self) -> None:
        """
        断开与远程服务器的连接

        注意：不会停止远程服务器，只是断开连接
        """
        start_time = time.time()

        try:
            self.logger.info("断开 VncComputer 连接...")

            # 只需要断开 interface 连接，不需要停止 VM
            await self.disconnect()

            self._initialized = False
            self._running = False

            self.logger.info("VncComputer 连接已断开")
        except Exception as e:
            self.logger.debug(f"断开连接时出错: {e}")
        finally:
            # 记录断开时间
            duration_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"VncComputer 断开连接耗时 {duration_ms:.2f}ms")

    async def restart(self) -> None:
        """
        重新连接到远程服务器

        注意：这只是断开并重新连接，不会重启远程服务器
        """
        self.logger.info("重新连接 VncComputer...")

        # 断开当前连接
        if self._interface:
            try:
                self._interface.close()
            except Exception as e:
                self.logger.debug(f"关闭 interface 时出错: {e}")

        # 重置状态
        self._initialized = False
        self._running = False

        # 重新连接
        await self.run()

        self.logger.info("VncComputer 重新连接成功")

    async def get_ip(self, max_retries: int = 15, retry_delay: int = 3) -> str:
        """
        获取 IP 地址

        对于 VncComputer，直接返回配置的 IP 地址
        """
        return self.vnc_ip

    async def wait_vm_ready(self) -> None:
        """
        等待 VM 就绪

        对于 VncComputer，这个方法什么也不做，因为不需要等待 VM 启动
        """
        # VNC 模式下不需要等待 VM
        return None

    async def update(self, cpu: Optional[int] = None, memory: Optional[str] = None):
        """
        更新 VM 设置

        对于 VncComputer，这个方法不支持，因为没有 VM
        """
        raise NotImplementedError(
            "VncComputer 不支持更新 VM 设置，因为它不管理 VM。"
            "如果需要更改远程服务器的资源，请在远程服务器上直接操作。"
        )

    def __repr__(self) -> str:
        """字符串表示"""
        status = "connected" if self._initialized else "disconnected"
        return f"VncComputer(ip={self.vnc_ip}, port={self.vnc_port}, os={self.os_type}, status={status})"
