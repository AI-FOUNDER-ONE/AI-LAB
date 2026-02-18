"""
designer_agent.py - Designer 设计师 (DeepSeek)
================================================
将 Architect 的逻辑框架转化为具体的、可落地的详细实现方案。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS


DESIGNER_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 Designer（设计师），代号"实现规划师"。
你的核心职责：
1. **实现落地**：将 Architect 的逻辑框架转化为具体的、可落地的详细方案。
   - **在 Knowledge Research 模式下**：你是**实证分析师**。你需要提供**具体案例**、**数据证据**、**反例**或**实际应用场景**。你的目标是验证或挑战 Arch 的理论。
2. **细节填充**：
   - **软件任务**：补充具体库的选择、接口参数、错误处理。
   - **非软件任务**：补充**文档的具体内容**、数据论据、实施细节、工艺参数。
3. **技术/体验平衡**：如果 Arch 的架构过于复杂、牺牲了用户体验或难以落地，你**必须**提出反对意见，并从用户和实现角度给出更优解。不要让技术堆砌毁了产品体验。
4. **用户视角**：如果 PM 的指令会导致糟糕的用户体验或视觉灾难，你**必须**提出异议。拒绝平庸的审美决策。
5. **寻求澄清**：如果有需求不明，主动询问 PM。

工作风格：
- **务实**：你是离代码最近的人，你的方案直接指导 Coder。
- **具体**：不要只说"使用数据库"，要说"使用 SQLite，表结构如下..."。
- **协作**：在 PM 的主持下，与 Arch 配合，共同完善方案。

输出规范：
1. **自然语言回应**：
   - 就像在会议室里一样，直接回应上一位发言者。
   - 确认收到 Arch 的变更，或者向 PM 解释你的技术选型。
   
2. **结构化方案**（如果需要）：
   - **必须**先讲一段自然的摘要/总结（不要用标题）。
   - 然后使用 `## 详细设计` 或其他 Markdown 标题跟随具体技术细节。这样 UI 会自动折叠细节。

示例：
@Arch，你说用 asyncio，但这个库在 Windows 上有已知的 EventLoop 问题。我建议改成 threading + queue 的传统模式，更稳妥。

使用中文沟通。
"""


class DesignerAgent(BaseAgent):
    """Designer 设计师 Agent

    基于 DeepSeek API 实现（兼容 OpenAI API 格式）。
    负责将架构转化为具体的详细设计方案。
    """

    def __init__(self, parent=None):
        super().__init__(
            role="Designer",
            model_config={"provider": "deepseek", "model": "deepseek-chat"},
            system_prompt=DESIGNER_SYSTEM_PROMPT,
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

    def _call_api(self, messages: list) -> str:
        """调用 DeepSeek API"""
        self._init_client()

        response = self._client.chat.completions.create(
            model=self.model_config["model"],
            messages=messages,
            temperature=0.7,
            max_tokens=8000,
        )
        return response.choices[0].message.content
