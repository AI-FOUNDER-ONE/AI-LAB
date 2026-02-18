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
2. **非软件交付物**（文档/方案）：
   - **项目计划书**：检查 WBS 分解是否合理，时间表是否可行。
   - **立项申请书/可行性报告**：检查逻辑是否严密，论据是否充分，创新点是否突出。
   - **工业设计**：检查工艺是否可实现，人机交互是否合理。

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
    """Validator 验证官 Agent
    
    负责生成验证评估报告。
    支持 DeepSeek (默认) 或 Anthropic (Claude) 等模型。
    """

    def __init__(self, parent=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("Tester", {"provider": "deepseek", "model": "deepseek-chat"})
        
        super().__init__(
            role="Validator",
            model_config=model_config,
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            parent=parent,
        )
        self._client = None

    def _init_client(self):
        """延迟初始化 AI 客户端"""
        if self._client is None:
            provider = self.model_config.get("provider", "deepseek")
            
            if provider == "deepseek":
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
            
            elif provider == "anthropic":
                try:
                    import anthropic
                    api_key = API_KEYS.get("anthropic", "")
                    if api_key:
                        self._client = anthropic.Anthropic(api_key=api_key)
                    else:
                        raise ValueError("ANTHROPIC_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 anthropic: pip install anthropic")

            elif provider == "zhipuai":
                try:
                    from zhipuai import ZhipuAI
                    api_key = API_KEYS.get("zhipuai", "")
                    if api_key:
                        self._client = ZhipuAI(api_key=api_key)
                    else:
                        raise ValueError("ZHIPUAI_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 zhipuai: pip install zhipuai")

    def _call_api(self, messages: list) -> str:
        """调用 AI API"""
        self._init_client()
        provider = self.model_config.get("provider", "deepseek")

        if provider == "deepseek":
            response = self._client.chat.completions.create(
                model=self.model_config["model"],
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        
        elif provider == "anthropic":
            # Anthropic Claude API 适配
            # 提取 system prompt
            system_prompt = ""
            active_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    active_messages.append(msg)
            
            response = self._client.messages.create(
                model=self.model_config["model"],
                system=system_prompt,
                messages=active_messages,
                max_tokens=2000,
                temperature=0.7,
            )
            return response.content[0].text
            
        elif provider == "zhipuai":
            response = self._client.chat.completions.create(
                model=self.model_config["model"],
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content

        return "⚠️ 未知的模型提供商配置"
