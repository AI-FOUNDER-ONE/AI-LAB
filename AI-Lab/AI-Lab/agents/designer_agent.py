"""
designer_agent.py - Designer 设计师 (DeepSeek)
================================================
将 Architect 的逻辑框架转化为具体的、可落地的详细实现方案。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS

# 尝试导入工具
try:
    from tools.matplotlib_design_tool import MatplotlibDesignTool
    from tools.ui_pattern_generator_tool import UIPatternGeneratorTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    # 工具可能不可用，提供空值
    TOOLS_AVAILABLE = False
    MatplotlibDesignTool = None
    UIPatternGeneratorTool = None
    print(f"[DesignerAgent] 工具导入警告: {e}. 原生Function Calling工具将不可用。")


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

        # 注册原生 Function Calling 工具
        self._register_tools()

    def _register_tools(self):
        """注册 Designer 专用工具"""
        if not TOOLS_AVAILABLE or (MatplotlibDesignTool is None and UIPatternGeneratorTool is None):
            print("[DesignerAgent] 工具不可用，跳过注册")
            return

        try:
            # 1. MatplotlibDesignTool - 设计图生成工具
            if MatplotlibDesignTool is not None:
                design_tool = MatplotlibDesignTool()
                def generate_design(design_json: str, filename: str = "") -> str:
                    """生成设计示意图"""
                    return design_tool._run(design_json=design_json, filename=filename)
                self.register_tool(generate_design, name="design_generator",
                                 description="基于matplotlib生成设计示意图。输入设计描述的JSON字符串，输出图像文件路径。支持布局图、色彩方案图、用户流程图等。")
            else:
                print("[DesignerAgent] MatplotlibDesignTool不可用，跳过注册")

            # 2. UIPatternGeneratorTool - UI设计模式生成工具
            if UIPatternGeneratorTool is not None:
                pattern_tool = UIPatternGeneratorTool()
                def generate_ui_patterns(ui_requirement: str, platform: str = "web",
                                       complexity: str = "medium") -> str:
                    """生成UI设计模式建议"""
                    return pattern_tool._run(
                        ui_requirement=ui_requirement,
                        platform=platform,
                        complexity=complexity
                    )
                self.register_tool(generate_ui_patterns, name="ui_pattern_generator",
                                 description="根据UI需求生成设计模式建议。输入UI需求描述，输出包含布局、组件、交互、配色等建议的结构化报告。")
            else:
                print("[DesignerAgent] UIPatternGeneratorTool不可用，跳过注册")

            print(f"[DesignerAgent] 已注册 {len(self.tools)} 个工具")
        except Exception as e:
            print(f"[DesignerAgent] 工具注册失败: {e}")

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
                        max_retries=5,
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
            return message.content or ""
