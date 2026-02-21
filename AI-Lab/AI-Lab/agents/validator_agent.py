"""
validator_agent.py - Validator 验证官 (DeepSeek)
================================================
负责对 Executor 的产出（代码或计划书）进行全面审查，
并向 PM 提交《验证评估报告》，评估其合理性和可执行性。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS


VALIDATOR_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 Validator（验证官），你的核心职责是充当"质检员"。
你不对方案做最终决定，而是向 PM 提交客观、专业的《验证评估报告》。

你的验证对象可能是：
1. **Python 代码**（软件任务）：检查代码逻辑、错误处理、规范性、可运行性。
2. **执行计划书**（非软件任务）：检查流程合理性、资源完整性、风险评估。

输出规范（适配直播间）：
1. **自然语言结论**：开头先用一段自然语言（不带 # 标题）总结你的评估结果，简明扼要地指出优缺点。
2. **结构化报告**：然后另起一行，使用 `## 验证评估报告` 标题开始正文。包含：验证结论、详细评估、改进建议。

示例：
代码结构良好，逻辑清晰，但在异常处理部分有遗漏，建议补充 try-except 块。

## 验证评估报告
...

使用中文沟通。
"""


class TesterAgent(BaseAgent):
    """Validator 验证官 Agent (类名保留为 TesterAgent 以兼容)

    基于 DeepSeek API 实现（兼容 OpenAI API 格式）。
    负责生成验证评估报告。
    """

    def __init__(self, parent=None):
        super().__init__(
            role="Validator",  # 角色名显示为 Validator
            model_config={"provider": "deepseek", "model": "deepseek-chat"},
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            parent=parent,
        )
        self._client = None

    def _init_client(self):
        """延迟初始化 DeepSeek 客户端（使用 OpenAI SDK）"""
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = API_KEYS.get("deepseek", "")
                if api_key:
                    self._client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.deepseek.com",
                    )
                else:
                    raise ValueError("DEEPSEEK_API_KEY 未配置")
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")

    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用 DeepSeek API，支持原生 Function Calling"""
        self._init_client()

        # 准备 API 调用参数
        api_kwargs = {
            "model": self.model_config["model"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        # 如果提供了工具列表，添加到参数中
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**api_kwargs)

        # 检查是否有工具调用
        message = response.choices[0].message
        if hasattr(message, 'tool_calls') and message.tool_calls:
            # 返回结构化响应，包含工具调用
            tool_calls = []
            for tool_call in message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                })
            return {
                "content": message.content or "",
                "tool_calls": tool_calls
            }
        else:
            return message.content or ""
