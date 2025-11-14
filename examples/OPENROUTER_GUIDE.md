# OpenRouter 使用指南

## 概述

OpenRouter 提供统一的 API 来访问多个 AI 模型提供商的模型。通过 OpenRouter，您可以使用单一的 API Key 访问来自 Anthropic、OpenAI、Google、Meta 等公司的各种模型。

## 优势

✅ **统一接口** - 一个 API 访问所有模型  
✅ **灵活计费** - 按使用付费，无需多个订阅  
✅ **自动故障转移** - 模型不可用时自动切换  
✅ **成本优化** - 根据任务选择最合适的模型  
✅ **实时可用性** - 访问最新发布的模型  

## 快速开始

### 1. 获取 API Key

1. 访问 [OpenRouter](https://openrouter.ai/)
2. 注册账号
3. 前往 [API Keys](https://openrouter.ai/keys) 页面
4. 创建新的 API Key

### 2. 设置环境变量

**方法 1：命令行设置**
```bash
export OPENROUTER_API_KEY='your-api-key-here'
```

**方法 2：.env 文件**
```bash
# 在项目根目录创建 .env 文件
OPENROUTER_API_KEY=your-api-key-here
```

### 3. 运行示例

```bash
# 快速开始
python examples/agent_openrouter_quickstart.py

# 完整示例
python examples/agent_openrouter_example.py
```

## 使用方法

### 基本用法

```python
from agent import ComputerAgent
from computer import Computer

# 创建 Computer
computer = Computer(os_type="macos")

# 使用 OpenRouter 模型
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",  # 模型格式
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),  # API Key
)

# 执行任务
history = [{"role": "user", "content": "打开浏览器"}]
async for result in agent.run(history):
    # 处理结果
    pass
```

### 模型格式

OpenRouter 模型使用以下格式：

```
openrouter/<provider>/<model-name>
```

**示例：**
- `openrouter/anthropic/claude-3.5-sonnet`
- `openrouter/openai/gpt-4o`
- `openrouter/google/gemini-pro-1.5`
- `openrouter/meta-llama/llama-3.1-70b-instruct`

### 完整模型列表

访问 [OpenRouter Models](https://openrouter.ai/models) 查看所有可用模型。

## 支持的模型

### Anthropic Claude 系列

| 模型 | OpenRouter ID | 特点 |
|-----|---------------|------|
| Claude 3.5 Sonnet | `openrouter/anthropic/claude-3.5-sonnet` | 最新版本，性能优秀 |
| Claude 3 Opus | `openrouter/anthropic/claude-3-opus` | 最强大的模型 |
| Claude 3 Sonnet | `openrouter/anthropic/claude-3-sonnet` | 平衡性能和成本 |
| Claude 3 Haiku | `openrouter/anthropic/claude-3-haiku` | 快速响应 |

### OpenAI GPT 系列

| 模型 | OpenRouter ID | 特点 |
|-----|---------------|------|
| GPT-4o | `openrouter/openai/gpt-4o` | 多模态，最新 GPT-4 |
| GPT-4 Turbo | `openrouter/openai/gpt-4-turbo` | 更快的 GPT-4 |
| GPT-4 | `openrouter/openai/gpt-4` | 原版 GPT-4 |
| GPT-3.5 Turbo | `openrouter/openai/gpt-3.5-turbo` | 经济实惠 |

### Google Gemini 系列

| 模型 | OpenRouter ID | 特点 |
|-----|---------------|------|
| Gemini Pro 1.5 | `openrouter/google/gemini-pro-1.5` | 长上下文支持 |
| Gemini Pro | `openrouter/google/gemini-pro` | 通用模型 |

### Meta Llama 系列

| 模型 | OpenRouter ID | 特点 |
|-----|---------------|------|
| Llama 3.1 405B | `openrouter/meta-llama/llama-3.1-405b-instruct` | 最大模型 |
| Llama 3.1 70B | `openrouter/meta-llama/llama-3.1-70b-instruct` | 平衡性能 |
| Llama 3.1 8B | `openrouter/meta-llama/llama-3.1-8b-instruct` | 轻量快速 |

## 代码示例

### 示例 1：基本使用

```python
import asyncio
import os
from agent import ComputerAgent
from computer import Computer

async def main():
    computer = Computer(os_type="macos")
    
    agent = ComputerAgent(
        model="openrouter/anthropic/claude-3.5-sonnet",
        tools=[computer],
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    
    history = [{"role": "user", "content": "截图"}]
    async for result in agent.run(history):
        print(result)

asyncio.run(main())
```

### 示例 2：使用 VncComputer

```python
from computer import VncComputer

# 连接到远程主机
computer = VncComputer(ip="192.168.1.100", os_type="linux")

agent = ComputerAgent(
    model="openrouter/openai/gpt-4o",
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
```

### 示例 3：多轮对话

```python
history = []

tasks = [
    "打开终端",
    "运行 ls 命令",
    "告诉我当前目录的内容",
]

for task in tasks:
    history.append({"role": "user", "content": task})
    
    async for result in agent.run(history):
        # 将输出添加到历史
        history += result.get("output", [])
```

### 示例 4：预算控制

```python
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),
    max_trajectory_budget=1.0,  # 最大预算 $1.00
)
```

### 示例 5：自定义参数

```python
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),
    # 额外参数
    temperature=0.7,
    max_tokens=4096,
    top_p=0.9,
)
```

## 高级功能

### 提示缓存

对于 Anthropic 模型，可以启用提示缓存来减少成本：

```python
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),
    use_prompt_caching=True,  # 启用缓存
)
```

### 轨迹保存

自动保存对话历史和截图：

```python
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),
    trajectory_dir="trajectories",  # 保存目录
)
```

### 图像保留策略

只保留最近的 N 张图像以节省 token：

```python
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",
    tools=[computer],
    api_key=os.getenv("OPENROUTER_API_KEY"),
    only_n_most_recent_images=3,  # 只保留最近 3 张图像
)
```

## 成本优化建议

### 1. 根据任务选择模型

| 任务类型 | 推荐模型 | 原因 |
|---------|---------|------|
| 简单任务 | GPT-3.5 Turbo / Claude Haiku | 成本低 |
| 中等任务 | Claude 3.5 Sonnet / GPT-4o | 性能平衡 |
| 复杂任务 | Claude 3 Opus / GPT-4 Turbo | 最佳效果 |

### 2. 使用提示缓存

Anthropic 模型支持提示缓存，可以显著降低重复请求的成本。

### 3. 限制图像数量

```python
only_n_most_recent_images=3  # 减少上下文中的图像
```

### 4. 设置预算限制

```python
max_trajectory_budget=1.0  # 防止意外超支
```

## 故障排除

### 问题 1：API Key 无效

**错误信息：** `Authentication failed`

**解决方法：**
1. 检查 API Key 是否正确
2. 确认环境变量已设置
3. 访问 [OpenRouter Keys](https://openrouter.ai/keys) 验证

### 问题 2：模型不可用

**错误信息：** `Model not found`

**解决方法：**
1. 访问 [OpenRouter Models](https://openrouter.ai/models) 确认模型 ID
2. 检查模型格式是否正确：`openrouter/<provider>/<model>`
3. 确认账户有足够额度

### 问题 3：余额不足

**错误信息：** `Insufficient credits`

**解决方法：**
1. 访问 [OpenRouter Credits](https://openrouter.ai/credits)
2. 充值账户

### 问题 4：速率限制

**错误信息：** `Rate limit exceeded`

**解决方法：**
1. 等待一段时间后重试
2. 升级账户计划
3. 使用不同的模型

## 与其他方式对比

| 特性 | OpenRouter | 直接 API | 优势 |
|-----|-----------|----------|------|
| **API Key 数量** | 1 个 | 多个 | OpenRouter 统一管理 |
| **模型切换** | 修改字符串 | 重写代码 | OpenRouter 更灵活 |
| **计费方式** | 统一 | 各不相同 | OpenRouter 更简单 |
| **故障转移** | 自动 | 手动 | OpenRouter 更可靠 |

## 最佳实践

### 1. 环境变量管理

```bash
# .env 文件
OPENROUTER_API_KEY=sk-or-v1-xxx
REMOTE_HOST=192.168.1.100  # 如果使用 VncComputer
```

### 2. 错误处理

```python
try:
    async for result in agent.run(history):
        # 处理结果
        pass
except Exception as e:
    logger.error(f"执行失败: {e}")
    # 重试或切换模型
```

### 3. 日志记录

```python
agent = ComputerAgent(
    model="openrouter/anthropic/claude-3.5-sonnet",
    tools=[computer],
    verbosity=logging.INFO,  # 设置日志级别
)
```

### 4. 测试和验证

在生产环境使用前，先在测试环境验证：

```python
# 测试模型
test_models = [
    "openrouter/openai/gpt-3.5-turbo",  # 低成本测试
]

for model in test_models:
    # 测试基本功能
    pass
```

## 相关资源

- [OpenRouter 官网](https://openrouter.ai/)
- [OpenRouter 文档](https://openrouter.ai/docs)
- [模型列表](https://openrouter.ai/models)
- [定价信息](https://openrouter.ai/docs/pricing)
- [API 参考](https://openrouter.ai/docs/api-reference)

## 示例文件

- `agent_openrouter_quickstart.py` - 快速开始示例
- `agent_openrouter_example.py` - 完整功能示例
- `agent_examples.py` - 通用 Agent 示例

## 总结

OpenRouter 为 ComputerAgent 提供了灵活且强大的模型访问能力：

✅ **简单易用** - 只需一个 API Key  
✅ **模型丰富** - 访问所有主流 AI 模型  
✅ **成本可控** - 按需付费，预算管理  
✅ **开发友好** - 统一接口，快速切换  

立即开始使用 OpenRouter，体验多模型的强大能力！

