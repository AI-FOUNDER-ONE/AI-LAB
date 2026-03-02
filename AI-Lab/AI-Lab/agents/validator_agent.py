"""
validator_agent.py - Validator 验证官 (DeepSeek)
================================================
负责对 Executor 的产出（代码或计划书）进行全面审查，
并向 PM 提交《验证评估报告》，评估其合理性和可执行性。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS

# 尝试导入工具
try:
    from tools.validation_tool import ValidationTool
    from tools.test_case_generator_tool import TestCaseGeneratorTool
    from tools.performance_analyzer_tool import PerformanceAnalyzerTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    # 工具可能不可用，提供空值
    TOOLS_AVAILABLE = False
    ValidationTool = None
    TestCaseGeneratorTool = None
    PerformanceAnalyzerTool = None
    print(f"[ValidatorAgent] 工具导入警告: {e}. 原生Function Calling工具将不可用。")


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
   - ⚠️ **严禁客套与随意使用 `@角色名` 提及他人**：评价或陈述时请直接下定论。只有在**你需要把发言权强制交接给下一个人**时，才允许使用 `@角色名`。如果在发言完毕后不想强制丢麦克风给特定的人，**绝对不要**在文本里带 `@` 符号，系统会自动按照阶段流转分配。
2. **结构化报告**：然后另起一行，使用 `## 验证评估报告` 标题开始正文。包含：验证结论、详细评估、改进建议。

示例：
代码结构良好，逻辑清晰，但在异常处理部分有遗漏，建议补充 try-except 块。

## 验证评估报告
...

使用中文沟通。
"""



class ValidatorAgent(BaseAgent):
    """Validator 验证官 Agent
    
    负责生成验证评估报告。
    支持 DeepSeek (默认) 或 Anthropic (Claude) 等模型。
    """

    def __init__(self, parent=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("Validator", {"provider": "deepseek", "model": "deepseek-chat"})
        
        super().__init__(
            role="Validator",
            model_config=model_config,
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            parent=parent,
        )
        self._client = None

        # 注册原生 Function Calling 工具
        self._register_tools()

    def _register_tools(self):
        """注册 Validator 专用工具"""
        if not TOOLS_AVAILABLE or (ValidationTool is None and TestCaseGeneratorTool is None and PerformanceAnalyzerTool is None):
            print("[ValidatorAgent] 工具不可用，跳过注册")
            return

        try:
            # 1. ValidationTool - 代码验证工具
            validator = ValidationTool()
            def validate_code(code: str, check_style: bool = True) -> str:
                """对 Python 代码进行静态验证和质量检查"""
                return validator._run(code=code, check_style=check_style)
            self.register_tool(validate_code, name="code_validator",
                             description="对 Python 代码进行静态验证和质量检查。输入Python代码字符串，输出包含语法检查、常见问题检测、规范性建议的验证报告。")

            # 2. TestCaseGeneratorTool - 测试用例生成工具
            test_generator = TestCaseGeneratorTool()
            def generate_test_cases(target: str, test_type: str = "unit",
                                  framework: str = "pytest", language: str = "python") -> str:
                """根据代码或需求自动生成测试用例"""
                return test_generator._run(target=target, test_type=test_type,
                                          framework=framework, language=language)
            self.register_tool(generate_test_cases, name="test_case_generator",
                             description="根据代码或需求自动生成测试用例。支持单元测试、集成测试、边界测试等多种测试类型。输出结构化测试用例，可直接用于测试执行。")

            # 3. PerformanceAnalyzerTool - 性能分析工具
            if PerformanceAnalyzerTool is not None:
                performance_analyzer = PerformanceAnalyzerTool()
                def analyze_performance(code: str, analysis_focus: str = "time_complexity",
                                      language: str = "python") -> str:
                    """分析代码的性能特征和潜在瓶颈"""
                    return performance_analyzer._run(
                        code=code,
                        analysis_focus=analysis_focus,
                        language=language
                    )
                self.register_tool(analyze_performance, name="performance_analyzer",
                                 description="分析代码的性能特征和潜在瓶颈。支持时间复杂度分析、空间复杂度分析、算法效率评估等。输出结构化性能分析报告和优化建议。")
            else:
                print("[ValidatorAgent] PerformanceAnalyzerTool不可用，跳过注册")

            print(f"[ValidatorAgent] 已注册 {len(self.tools)} 个工具")
        except Exception as e:
            print(f"[ValidatorAgent] 工具注册失败: {e}")

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
                            max_retries=5,
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

    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用 AI API，支持原生 Function Calling"""
        self._init_client()
        provider = self.model_config.get("provider", "deepseek")

        if provider == "deepseek":
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

            # Anthropic 工具调用处理（简化版）
            # 注意：Anthropic API 工具调用格式不同，这里简化处理
            response = self._client.messages.create(
                model=self.model_config["model"],
                system=system_prompt,
                messages=active_messages,
                max_tokens=2000,
                temperature=0.7,
                # Anthropic tools 参数处理需要额外实现
            )
            return response.content[0].text

        elif provider == "zhipuai":
            # 智谱 GLM 调用（可能不支持工具调用）
            response = self._client.chat.completions.create(
                model=self.model_config["model"],
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content

        return "⚠️ 未知的模型提供商配置"
