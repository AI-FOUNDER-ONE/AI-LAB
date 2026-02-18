"""
arch_agent.py - Architect 架构师 (Claude)
==========================================
提出逻辑框架和技术架构方案。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS


ARCH_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 Architect（架构师），代号"逻辑构建者"。
你的核心职责：
1. **构建与捍卫架构**：基于 Mission Protocol 设计系统逻辑框架（软件架构 或 **文档/方案的大纲结构**）。
   - **在 Knowledge Research 模式下**：你是**首席研究员**。你需要提供**宏观理论框架**、**核心概念定义**、**学术/技术溯源**。你的发言应偏向理论和原理。
2. **动态协作**：在 PM 的主持下，与 Designer 进行多轮辩论。
3. **贯彻意图**：严格检查 Designer 的设计方案，确保其**贯彻**了你的架构意图。
4. **理性反驳**：如果 PM 的指令在技术上不可行、存在重大风险或违背 Mission Protocol，你**必须**提出明确的反对意见，并给出替代方案。不要盲目服从。

工作风格：
- **不要被动等待**：如果 Designer 的方案有漏洞，你要犀利地指出来。
- **关注核心**：模块划分、数据流向、关键接口。
- **Pythonic**：在 Windows 环境下优先考虑 Python 生态系统最佳实践。

输出规范：
1. **自然语言辩论**：
   - 就像在会议室里一样，直接回应上一位发言者（PM 或 Designer）。
   - 如果是 Designer 发言，评估其方案是否符合你的架构设计。
   
2. **结构化内容**（如果需要）：
   - **必须**先讲一段自然的摘要/总结（不要用标题）。
   - 然后使用 `## 核心架构` 或其他 Markdown 标题跟随具体技术细节。这样 UI 会自动折叠细节。

示例：
@Designer，你提出的这个 Redis 缓存方案太重了。我们的并发量不需要引入额外的中间件，直接用内存 LRU cache 足够。请简化你的设计。

使用中文沟通。
"""


class ArchAgent(BaseAgent):
    """Architect 架构师 Agent

    【临时】使用智谱 GLM API 进行测试。
    正式版应切回 Anthropic Claude API。
    """

    def __init__(self, parent=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("Arch", {"provider": "hiapi", "model": "gpt-4o"})

        super().__init__(
            role="Arch",
            model_config=model_config,
            system_prompt=ARCH_SYSTEM_PROMPT,
            parent=parent,
        )
        self._client = None

    def _init_client(self):
        """延迟初始化客户端"""
        if self._client is None:
            provider = self.model_config.get("provider", "openai")
            
            if provider == "zhipuai":
                try:
                    from zhipuai import ZhipuAI
                    api_key = API_KEYS.get("zhipuai", "")
                    if api_key:
                        self._client = ZhipuAI(api_key=api_key)
                    else:
                        raise ValueError("ZHIPUAI_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 zhipuai: pip install zhipuai")
            
            elif provider == "openai":
                try:
                    from openai import OpenAI
                    api_key = API_KEYS.get("openai", "")
                    if api_key:
                        self._client = OpenAI(api_key=api_key)
                    else:
                        raise ValueError("OPENAI_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 openai: pip install openai")
            
            elif provider == "xai":
                 try:
                    from openai import OpenAI
                    api_key = API_KEYS.get("xai", "")
                    if api_key:
                        self._client = OpenAI(
                            api_key=api_key,
                            base_url="https://api.x.ai/v1",
                        )
                    else:
                        raise ValueError("XAI_API_KEY 未配置")
                 except ImportError:
                    raise ImportError("请安装 openai: pip install openai")
            
            elif provider == "hiapi":
                try:
                    from openai import OpenAI
                    api_key = API_KEYS.get("hiapi", "")
                    if api_key:
                        self._client = OpenAI(
                            api_key=api_key,
                            base_url="https://hiapi.online/v1",
                        )
                    else:
                        raise ValueError("HIAPI_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 openai: pip install openai")

            elif provider == "volcengine":
                # 火山引擎 Ark API（兼容 OpenAI SDK）
                try:
                    from openai import OpenAI
                    api_key = API_KEYS.get("volcengine", "")
                    base_url = self.model_config.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
                    if api_key:
                        self._client = OpenAI(
                            api_key=api_key,
                            base_url=base_url,
                        )
                    else:
                        raise ValueError("VOLCENGINE_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 openai: pip install openai")



    def _call_api(self, messages: list) -> str:
        """调用 AI API"""
        print(f"DEBUG: ArchAgent._call_api called with {len(messages)} messages")
        self._init_client()
        provider = self.model_config.get("provider", "openai")
        print(f"DEBUG: ArchAgent provider is {provider}")

        if provider == "gemini":
            try:
                import google.generativeai as genai
                api_key = API_KEYS.get("gemini", "")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY 未配置")
                
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(self.model_config["model"])
                
                prompt = ""
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "system":
                        prompt += f"System: {content}\n"
                    elif role == "user":
                        prompt += f"User: {content}\n"
                    elif role == "assistant":
                        prompt += f"Model: {content}\n"
                
                response = model.generate_content(prompt)
                content = response.text
                print(f"DEBUG: ArchAgent (gemini-native) response received: {len(content)} chars")
                return content
            except Exception as e:
                print(f"Gemini Native Error: {e}")
                raise e

        try:
            if provider == "zhipuai":
                # 智谱 GLM 调用
                response = self._client.chat.completions.create(
                    model=self.model_config["model"],
                    messages=messages,
                    temperature=0.7,
                    max_tokens=8000,
                )
                content = response.choices[0].message.content
                print(f"DEBUG: ArchAgent (zhipuai) response received: {len(content)} chars")
                return content
            
            elif provider in ("openai", "xai", "hiapi", "volcengine"):
                # OpenAI / xAI / HiAPI 调用
                response = self._client.chat.completions.create(
                    model=self.model_config["model"],
                    messages=messages,
                    temperature=0.7,
                    max_tokens=8000,
                )
                content = response.choices[0].message.content
                print(f"DEBUG: ArchAgent ({provider}) response received: {len(content)} chars")
                return content
            
            return "⚠️ 未知的模型提供商配置"
        except Exception as e:
            print(f"DEBUG: ArchAgent API Error: {e}")
            raise e
