"""
arch_agent.py - Architect 架构师 (Claude)
==========================================
提出逻辑框架和技术架构方案。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS

# 尝试导入工具
try:
    from tools.mermaid_tool import MermaidTool
    from tools.architecture_evaluator_tool import ArchitectureEvaluatorTool
    from tools.dependency_analyzer_tool import DependencyAnalyzerTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    # 工具可能不可用，提供空值
    TOOLS_AVAILABLE = False
    MermaidTool = None
    ArchitectureEvaluatorTool = None
    DependencyAnalyzerTool = None
    print(f"[ArchAgent] 工具导入警告: {e}. 原生Function Calling工具将不可用。")


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
   - ⚠️ **严禁客套与随意使用 `@角色名` 提及他人**：评价或陈述时请直接下定论。只有在**你需要把发言权强制交接给下一个人**时，才允许使用 `@角色名`。如果在发言完毕后不想强制丢麦克风给特定的人，**绝对不要**在文本里带 `@` 符号，系统会自动按照阶段流转分配。
   
2. **结构化内容**（如果需要）：
   - **必须**先讲一段自然的摘要/总结（不要用标题）。
   - 然后使用 `## 核心架构` 或其他 Markdown 标题跟随具体技术细节。这样 UI 会自动折叠细节。

使用中文沟通。
"""


class ArchAgent(BaseAgent):
    """Architect 架构师 Agent

    【临时】使用智谱 GLM API 进行测试。
    正式版应切回 Anthropic Claude API。
    """

    def __init__(self, parent=None, tool_manager=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("Arch", {"provider": "hiapi", "model": "gpt-4o"})

        super().__init__(
            role="Arch",
            model_config=model_config,
            system_prompt=ARCH_SYSTEM_PROMPT,
            parent=parent,
            tool_manager=tool_manager,
        )
        self._client = None

        # 注册原生 Function Calling 工具
        self._register_tools()

    def _register_tools(self):
        """注册 Arch 专用工具"""
        if not TOOLS_AVAILABLE or (MermaidTool is None and ArchitectureEvaluatorTool is None and DependencyAnalyzerTool is None):
            print("[ArchAgent] 工具不可用，跳过注册")
            return

        try:
            # 1. MermaidTool - Mermaid图表生成工具
            mermaid_tool = MermaidTool()
            def generate_mermaid(diagram_type: str, content: str) -> str:
                """生成Mermaid图表代码"""
                return mermaid_tool._run(diagram_type=diagram_type, content=content)
            self.register_tool(generate_mermaid, name="mermaid_generator",
                             description="生成Mermaid图表代码。支持流程图、序列图、类图、状态图等。输入图表类型和内容描述，输出Mermaid代码。")

            # 2. ArchitectureEvaluatorTool - 架构评估工具
            arch_evaluator = ArchitectureEvaluatorTool()
            def evaluate_architecture(architecture_description: str, evaluation_focus: str = "comprehensive",
                                     project_scale: str = "medium") -> str:
                """对架构方案进行多维度评估"""
                return arch_evaluator._run(
                    architecture_description=architecture_description,
                    evaluation_focus=evaluation_focus,
                    project_scale=project_scale
                )
            self.register_tool(evaluate_architecture, name="architecture_evaluator",
                             description="对架构方案进行多维度评估，考虑可扩展性、可维护性、性能、安全性、成本等因素。输入架构描述，输出结构化评估报告和改进建议。")

            # 3. DependencyAnalyzerTool - 依赖关系分析工具
            if DependencyAnalyzerTool is not None:
                dependency_analyzer = DependencyAnalyzerTool()
                def analyze_dependencies(target: str, analysis_type: str = "external",
                                       depth: str = "standard") -> str:
                    """分析代码或项目的依赖关系"""
                    return dependency_analyzer._run(
                        target=target,
                        analysis_type=analysis_type,
                        depth=depth
                    )
                self.register_tool(analyze_dependencies, name="dependency_analyzer",
                                 description="分析代码或项目的依赖关系。支持外部依赖、内部模块依赖、版本冲突、循环依赖检测等功能。输入分析目标，输出结构化依赖分析报告。")
            else:
                print("[ArchAgent] DependencyAnalyzerTool不可用，跳过注册")

            print(f"[ArchAgent] 已注册 {len(self.tools)} 个工具")
        except Exception as e:
            print(f"[ArchAgent] 工具注册失败: {e}")

        # context_retriever - 从 meeting_logs 语义检索历史（与 Crew 工具解耦，始终尝试注册）
        try:
            from tools.context_retriever import context_retriever as _context_retriever
            def context_retriever(query: str, max_results: int = 5) -> dict:
                store = (self.parent().session_store if self.parent() and getattr(self.parent(), "session_store", None) else None)
                return _context_retriever(query=query, session_store=store, max_results=max_results)
            self.register_tool(
                context_retriever,
                name="context_retriever",
                description="从当前会话的会议记录中检索与 query 最相关的历史消息。返回 results: [{speaker, content, timestamp, relevance}]。用于长对话中找回关键信息。"
            )
        except Exception as e:
            print(f"[ArchAgent] context_retriever 注册失败: {e}")

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
                        self._client = OpenAI(api_key=api_key, max_retries=5)
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
                            max_retries=5,
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
                            max_retries=5,
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
                            max_retries=5,
                        )
                    else:
                        raise ValueError("VOLCENGINE_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 openai: pip install openai")



    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用 AI API，支持原生 Function Calling"""
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
                # 智谱 GLM 调用（可能不支持工具调用）
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
                # OpenAI / xAI / HiAPI / 火山引擎调用（支持工具调用）
                # 准备 API 调用参数
                api_kwargs = {
                    "model": self.model_config["model"],
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 8000,
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
                    content = message.content or ""
                    print(f"DEBUG: ArchAgent ({provider}) response received: {len(content)} chars")
                    return content

            return "⚠️ 未知的模型提供商配置"
        except Exception as e:
            print(f"DEBUG: ArchAgent API Error: {e}")
            raise e
