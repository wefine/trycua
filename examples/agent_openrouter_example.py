"""
OpenRouter 模型支持示例 - VncComputer + GPT-4o-mini

展示如何使用 OpenRouter 上的 GPT-4o-mini 模型与 VncComputer 连接到远程 Linux 服务器。
OpenRouter 提供了统一的 API 来访问多个 AI 模型提供商的模型。

前提条件：
    1. 注册 OpenRouter 账号：https://openrouter.ai/
    2. 获取 API Key：https://openrouter.ai/keys
    3. 设置环境变量：
       - OPENROUTER_API_KEY: OpenRouter API Key
       - REMOTE_HOST: 远程 Linux 服务器的 IP 地址
    4. 远程服务器需要运行 computer-server:
       pip install cua-computer-server
       python -m computer_server

本示例使用：
    - VncComputer: 连接到远程 Linux 服务器
    - OpenRouter GPT-4o-mini: 高性价比的 AI 模型
    - Linux 环境: 适用于服务器和容器
    - Omniparser: 用于普通 GPT 模型的 grounding 组件（必需）

注意：
    - 普通 GPT 模型（如 gpt-4o-mini）需要使用 "omniparser+" 前缀
    - 格式：omniparser+openrouter/<provider>/<model-name>
    - Computer Use 专用模型（如 computer-use-preview）可以直接使用

优势：
    ✅ 统一的 API 接口
    ✅ 访问多个模型提供商
    ✅ 灵活的计费方式
    ✅ 无需多个 API Key
    ✅ 远程服务器操作
"""

import asyncio
import logging
import os
import signal
import traceback

from agent import ComputerAgent
from computer import Computer, VncComputer, VMProviderType
from utils import handle_sigint, load_dotenv_files

# ============================================================================
# 关于 Telemetry (PostHog) 的说明
# ============================================================================
# CUA 项目使用 PostHog (eu.i.posthog.com) 收集匿名使用数据
# 这是 CUA 项目自己的遥测系统，与 MLflow 完全独立
#
# 如何禁用 PostHog Telemetry：
#   1. 环境变量：export CUA_TELEMETRY_ENABLED=false
#   2. 在代码中：agent = ComputerAgent(..., telemetry_enabled=False)
#
# 注意：PostHog telemetry 不会影响 MLflow 的功能
# ============================================================================

# 设置日志
# 创建 logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 创建格式化器
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

import datetime

# 文件处理器
file_handler = logging.FileHandler(
    f"computer_server_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.log", mode="a"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


# 设置 MLflow 日志
def setup_mlflow_logging():
    """设置 MLflow 自动追踪 LiteLLM 调用

    根据官方文档：https://mlflow.org/docs/latest/genai/tracing/integrations/listing/litellm/
    MLflow >= 3.0.0 支持 LiteLLM 自动追踪

    注意：
    - MLflow 和 PostHog Telemetry 是两个独立的系统
    - PostHog (eu.i.posthog.com) 是 CUA 项目的遥测服务，用于收集匿名使用数据
    - MLflow 用于追踪 ML 实验和模型调用，与 PostHog 无关
    """
    try:
        import mlflow

        # 检查 MLflow 版本
        mlflow_version = mlflow.__version__
        logger.info(f"MLflow version: {mlflow_version}")

        # 尝试导入 genai 模块以确保它被加载
        try:
            import mlflow.genai  # noqa: F401  # 触发 genai 模块加载
        except ImportError:
            logger.warning("mlflow.genai module not found, but litellm may still work")

        # 配置 MLflow tracking（需要在 autolog 之前设置）
        mlflow.set_tracking_uri("http://localhost:5000")  # Use local MLflow server
        mlflow.set_experiment("trycua")

        # Enable autologging for LiteLLM（不是 OpenAI！）
        # 根据官方文档，使用 mlflow.litellm.autolog() 而不是 mlflow.openai.autolog()
        try:
            mlflow.litellm.autolog()  # type: ignore[attr-defined]
            logger.info("✅ MLflow LiteLLM autologging enabled successfully")
        except AttributeError as e:
            logger.error(
                f"❌ MLflow LiteLLM integration not available: {e}\n"
                f"MLflow version: {mlflow_version}\n"
                "可能的原因：\n"
                "  1. MLflow 版本过低（需要 >= 3.0.0）\n"
                "  2. 需要安装 genai 扩展: pip install 'mlflow[genai]'\n"
                "  3. 可能需要重新安装: pip install --upgrade mlflow\n"
                "参考文档: https://mlflow.org/docs/latest/genai/tracing/integrations/listing/litellm/"
            )
            raise
    except ImportError as e:
        logger.warning(f"MLflow not installed, skipping MLflow logging: {e}")
    except Exception as e:
        # 不要因为 MLflow 配置失败而中断程序
        logger.warning(f"Failed to setup MLflow logging: {e}")


# 启用 MLflow 日志（可选，如果 MLflow 服务器未运行会记录警告）
setup_mlflow_logging()


async def run_openrouter_example_basic():
    """
    示例 1：使用 OpenRouter 的基本示例

    使用 VncComputer 连接到远程 Linux 服务器，使用 GPT-4o-mini 模型
    """
    print("\n" + "=" * 60)
    print("示例 1：OpenRouter 基础示例 - GPT-4o-mini + VncComputer")
    print("=" * 60)

    remote_host = os.getenv("REMOTE_HOST")
    if not remote_host:
        print("❌ 未设置 REMOTE_HOST 环境变量，跳过此示例")
        return

    try:
        # 使用 VncComputer 连接到远程 Linux 服务器
        computer = VncComputer(
            ip=remote_host,
            os_type="linux",
            verbosity=logging.DEBUG,
        )

        # 创建 ComputerAgent，使用 OpenRouter 的 GPT-4o-mini
        # 格式：omniparser+openrouter/<provider>/<model-name>
        # 注意：普通 GPT 模型需要使用 omniparser 前缀才能工作
        agent = ComputerAgent(
            model="openrouter/bytedance/ui-tars-1.5-7b+openrouter/qwen/qwen3-vl-8b-instruct",
            tools=[computer],
            only_n_most_recent_images=3,
            verbosity=logging.DEBUG,
            trajectory_dir="trajectories",
            telemetry_enabled=False,  # 禁用 PostHog telemetry
            api_key=os.getenv("OPENROUTER_API_KEY"),  # OpenRouter API Key
        )

        # 简单任务
        task = "打开浏览器，查询深圳明天的天气情况"

        print(f"\n连接到: {remote_host}")
        print(f"执行任务: {task}")

        # 运行 agent
        history = [{"role": "user", "content": task}]

        async for result in agent.run(history, stream=False):
            # 处理输出
            for item in result.get("output", []):
                if item.get("type") == "message":
                    content = item.get("content", [])
                    for content_part in content:
                        if content_part.get("text"):
                            print(f"Agent: {content_part.get('text')}")

        print("\n✅ 任务完成")

    except Exception as e:
        logger.error(f"错误: {e}")
        traceback.print_exc()


async def run_openrouter_example_multiple_models():
    """
    示例 2：展示 OpenRouter 上的多个模型

    演示如何使用不同提供商的模型
    """
    print("\n" + "=" * 60)
    print("示例 2：OpenRouter 多模型支持")
    print("=" * 60)

    # OpenRouter 上可用的模型示例
    # 注意：普通 GPT 模型需要使用 "omniparser+" 前缀才能工作
    models = {
        "claude-3.5-sonnet": "openrouter/anthropic/claude-3.5-sonnet",  # Claude 支持 Computer Use
        "claude-3-opus": "openrouter/anthropic/claude-3-opus",  # Claude 支持 Computer Use
        "gpt-4o": "omniparser+openrouter/openai/gpt-4o",  # 普通 GPT 需要 omniparser
        "gpt-4-turbo": "omniparser+openrouter/openai/gpt-4-turbo",  # 普通 GPT 需要 omniparser
        "gpt-4o-mini": "omniparser+openrouter/openai/gpt-4o-mini",  # 普通 GPT 需要 omniparser
        "gemini-pro-1.5": "openrouter/google/gemini-pro-1.5",
        "llama-3.1-70b": "openrouter/meta-llama/llama-3.1-70b-instruct",
    }

    print("\nOpenRouter 支持的模型示例:")
    for name, model_id in models.items():
        print(f"  • {name}: {model_id}")

    print("\n提示：使用以下格式来指定模型：")
    print("  - Computer Use 专用模型（如 Claude）: model='openrouter/<provider>/<model-name>'")
    print("  - 普通 GPT 模型: model='omniparser+openrouter/<provider>/<model-name>'")
    print("\n查看完整模型列表：https://openrouter.ai/models")


async def run_openrouter_example_with_vnc():
    """
    示例 3：OpenRouter + VncComputer

    结合 VncComputer 使用 OpenRouter 模型
    """
    print("\n" + "=" * 60)
    print("示例 3：OpenRouter + VncComputer")
    print("=" * 60)

    remote_host = os.getenv("REMOTE_HOST")

    if not remote_host:
        print("❌ 未设置 REMOTE_HOST 环境变量，跳过此示例")
        return

    try:
        # 使用 VncComputer 连接到远程 Linux 服务器
        computer = VncComputer(
            ip=remote_host,
            os_type="linux",
            verbosity=logging.INFO,
        )

        # 使用 OpenRouter 的 GPT-4o-mini 模型
        # 注意：普通 GPT 模型需要使用 omniparser 前缀
        agent = ComputerAgent(
            model="omniparser+openrouter/openai/gpt-4o-mini",
            tools=[computer],
            only_n_most_recent_images=3,
            verbosity=logging.INFO,
            telemetry_enabled=False,  # 禁用 PostHog telemetry
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        task = "检查当前系统信息"

        print(f"\n连接到: {remote_host}")
        print(f"执行任务: {task}")

        history = [{"role": "user", "content": task}]

        async for result in agent.run(history, stream=False):
            for item in result.get("output", []):
                if item.get("type") == "message":
                    content = item.get("content", [])
                    for content_part in content:
                        if content_part.get("text"):
                            print(f"Agent: {content_part.get('text')}")

        print("\n✅ 任务完成")

    except Exception as e:
        logger.error(f"错误: {e}")
        traceback.print_exc()


async def run_openrouter_example_advanced():
    """
    示例 4：高级用法 - 多轮对话与预算控制

    展示 OpenRouter 的高级功能
    """
    print("\n" + "=" * 60)
    print("示例 4：OpenRouter 高级用法")
    print("=" * 60)

    remote_host = os.getenv("REMOTE_HOST")
    if not remote_host:
        print("❌ 未设置 REMOTE_HOST 环境变量，跳过此示例")
        return

    try:
        # 使用 VncComputer 连接到远程 Linux 服务器
        computer = VncComputer(
            ip=remote_host,
            os_type="linux",
            verbosity=logging.INFO,
        )

        # 创建 Agent，带预算控制
        # 注意：普通 GPT 模型需要使用 omniparser 前缀
        agent = ComputerAgent(
            model="omniparser+openrouter/openai/gpt-4o-mini",
            tools=[computer],
            only_n_most_recent_images=3,
            verbosity=logging.INFO,
            trajectory_dir="trajectories",
            use_prompt_caching=True,  # 使用提示缓存
            max_trajectory_budget=0.5,  # 设置最大预算 $0.50
            telemetry_enabled=False,  # 禁用 PostHog telemetry
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        # 多轮对话任务（Linux 环境）
        tasks = [
            "打开终端",
            "创建一个新目录叫 'openrouter_test'",
            "在该目录中创建一个文本文件",
        ]

        print(f"\n连接到: {remote_host}")
        history = []

        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}] 任务: {task}")

            # 添加用户消息
            history.append({"role": "user", "content": task})

            # 运行 agent
            async for result in agent.run(history, stream=False):
                # 将输出添加到历史
                history += result.get("output", [])

                # 打印消息
                for item in result.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for content_part in content:
                            if content_part.get("text"):
                                print(f"  Agent: {content_part.get('text')}")

            print(f"  ✅ 任务 {i} 完成")

        print("\n✅ 所有任务完成")

    except Exception as e:
        logger.error(f"错误: {e}")
        traceback.print_exc()


async def run_openrouter_example_custom_options():
    """
    示例 5：自定义 OpenRouter 选项

    展示如何传递 OpenRouter 特定的参数
    """
    print("\n" + "=" * 60)
    print("示例 5：OpenRouter 自定义选项")
    print("=" * 60)

    remote_host = os.getenv("REMOTE_HOST")
    if not remote_host:
        print("❌ 未设置 REMOTE_HOST 环境变量，跳过此示例")
        return

    try:
        # 使用 VncComputer 连接到远程 Linux 服务器
        computer = VncComputer(
            ip=remote_host,
            os_type="linux",
            verbosity=logging.INFO,
        )

        # 创建 Agent，使用自定义参数
        # 注意：普通 GPT 模型需要使用 omniparser 前缀
        agent = ComputerAgent(
            model="omniparser+openrouter/openai/gpt-4o-mini",
            tools=[computer],
            only_n_most_recent_images=3,
            verbosity=logging.INFO,
            telemetry_enabled=False,  # 禁用 PostHog telemetry
            api_key=os.getenv("OPENROUTER_API_KEY"),
            # OpenRouter 特定参数可以通过 additional_generation_kwargs 传递
            # 例如：
            # temperature=0.7,
            # max_tokens=4096,
            # top_p=0.9,
        )

        task = "截图并描述当前屏幕内容"

        print(f"\n连接到: {remote_host}")
        print(f"执行任务: {task}")

        history = [{"role": "user", "content": task}]

        async for result in agent.run(history, stream=False):
            for item in result.get("output", []):
                if item.get("type") == "message":
                    content = item.get("content", [])
                    for content_part in content:
                        if content_part.get("text"):
                            print(f"Agent: {content_part.get('text')}")

        print("\n✅ 任务完成")

    except Exception as e:
        logger.error(f"错误: {e}")
        traceback.print_exc()


async def compare_openrouter_models():
    """
    示例 6：比较不同的 OpenRouter 模型

    对比不同模型的表现
    """
    print("\n" + "=" * 60)
    print("示例 6：OpenRouter 模型对比")
    print("=" * 60)

    remote_host = os.getenv("REMOTE_HOST")
    if not remote_host:
        print("❌ 未设置 REMOTE_HOST 环境变量，跳过此示例")
        return

    # 要对比的模型（使用 GPT-4o-mini 作为主模型）
    # 注意：普通 GPT 模型需要使用 omniparser 前缀
    models_to_compare = [
        ("GPT-4o-mini", "omniparser+openrouter/openai/gpt-4o-mini"),
        ("GPT-4o", "omniparser+openrouter/openai/gpt-4o"),
        # 可以添加更多模型
    ]

    task = "告诉我当前日期和时间"

    print(f"\n连接到: {remote_host}")

    for model_name, model_id in models_to_compare:
        print(f"\n--- 测试模型: {model_name} ---")

        try:
            # 使用 VncComputer 连接到远程 Linux 服务器
            computer = VncComputer(
                ip=remote_host,
                os_type="linux",
                verbosity=logging.WARNING,  # 减少日志输出
            )

            agent = ComputerAgent(
                model=model_id,
                tools=[computer],
                verbosity=logging.WARNING,
                telemetry_enabled=False,  # 禁用 PostHog telemetry
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )

            history = [{"role": "user", "content": task}]

            async for result in agent.run(history, stream=False):
                for item in result.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for content_part in content:
                            if content_part.get("text"):
                                print(f"{model_name}: {content_part.get('text')}")

        except Exception as e:
            logger.error(f"{model_name} 错误: {e}")


def check_environment():
    """检查环境配置"""
    print("\n=== 环境检查 ===")

    all_ok = True

    # 检查 OPENROUTER_API_KEY
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 未设置 OPENROUTER_API_KEY 环境变量")
        print("\n请按以下步骤设置：")
        print("1. 访问 https://openrouter.ai/")
        print("2. 注册账号并获取 API Key")
        print("3. 设置环境变量：")
        print("   export OPENROUTER_API_KEY='your-api-key-here'")
        print("   或在 .env 文件中添加：")
        print("   OPENROUTER_API_KEY=your-api-key-here")
        all_ok = False
    else:
        print(f"✅ OPENROUTER_API_KEY 已设置: {api_key[:8]}...")

    # 检查 REMOTE_HOST
    remote_host = os.getenv("REMOTE_HOST")
    if not remote_host:
        print("❌ 未设置 REMOTE_HOST 环境变量")
        print("\n请设置远程 Linux 服务器的 IP 地址：")
        print("   export REMOTE_HOST='192.168.1.100'")
        print("   或在 .env 文件中添加：")
        print("   REMOTE_HOST=192.168.1.100")
        all_ok = False
    else:
        print(f"✅ REMOTE_HOST 已设置: {remote_host}")

    return all_ok


def main():
    """主函数：运行 OpenRouter 示例"""
    print("=" * 60)
    print("OpenRouter + VncComputer + GPT-4o-mini 示例")
    print("=" * 60)

    # 加载环境变量
    load_dotenv_files()

    # 检查环境
    if not check_environment():
        return

    # 注册信号处理
    signal.signal(signal.SIGINT, handle_sigint)

    print("\n可用的示例：")
    print("1. run_openrouter_example_basic() - 基础示例")
    print("2. run_openrouter_example_multiple_models() - 多模型展示")
    print("3. run_openrouter_example_with_vnc() - 配合 VncComputer 使用")
    print("4. run_openrouter_example_advanced() - 高级用法")
    print("5. run_openrouter_example_custom_options() - 自定义选项")
    print("6. compare_openrouter_models() - 模型对比")

    try:
        # 运行示例（可以注释/取消注释不同的示例）

        # 基础示例
        asyncio.run(run_openrouter_example_basic())

        # 多模型展示
        # asyncio.run(run_openrouter_example_multiple_models())

        # VNC 示例
        # asyncio.run(run_openrouter_example_with_vnc())

        # 高级示例
        # asyncio.run(run_openrouter_example_advanced())

        # 自定义选项
        # asyncio.run(run_openrouter_example_custom_options())

        # 模型对比
        # asyncio.run(compare_openrouter_models())

    except Exception as e:
        print(f"\n❌ 运行示例时出错: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
