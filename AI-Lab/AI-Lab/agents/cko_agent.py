"""
cko_agent.py - CKO 首席知识官 (Gemini)
========================================
负责需求深度访谈，基于用户输入和历史数据进行追问，
最终生成 Mission_Protocol.json。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS
# 尝试导入工具，如果crewai不可用则提供空值
try:
    from tools.tool_schema_adapter import crew_tool_to_schema
    from tools.requirements_analyzer_tool import RequirementsAnalyzerTool
    from tools.knowledge_retrieval_tool import KnowledgeRetrievalTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    # crewai可能不可用，提供空值
    TOOLS_AVAILABLE = False
    crew_tool_to_schema = None
    RequirementsAnalyzerTool = None
    KnowledgeRetrievalTool = None
    print(f"[CKOAgent] 工具导入警告: {e}. 原生Function Calling工具将不可用。")


# CKO 系统提示词
CKO_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 CKO（首席知识官），代号"学术桥梁"。
你的核心职责：
1. 深度理解用户的研究意图和需求
2. 基于用户输入进行结构化追问，确保需求无遗漏
3. 整合历史项目偏好和科研禁忌
4. 最终输出一份结构化的 Mission Protocol（任务书）

工作风格：
- **在需求阶段 (Grounding)**：像一位资深的学术导师，温和严谨地追问。
- **在博弈阶段 (Debate)**：
  - **身份**：列席会议的"最高解释权"持有者。
  - **被点名时**：当 PM 呼叫你 (`NEXT_SPEAKER: CKO`) 或用户干预时，请**明确澄清** Mission Protocol 的原意，裁决争议，或指出当前讨论的偏离点。
  - **主动干预**：如果发现话题严重跑偏，必须严厉指出。
  - **发言风格**：言简意赅，直击要害，引用 Mission Protocol 的具体条款。
- 使用中文沟通，专业术语保留英文
- **输出格式规范**：
  - **必须**先讲一段自然的摘要/总结（不要用标题）。
  - 然后使用 `## 详细方案` / `## 追问` / `## Mission Protocol` 等 Markdown 标题跟随具体内容。
  - 这样 UI 会自动将标题后的内容折叠，保持界面整洁。
  - ⚠️ **严禁客套与随意使用 `@角色名` 提及他人**：系统依赖 `@` 符号进行高优先级路由。除了在必要时点名，其余陈述时**绝对不要**在文本里带 `@` 符号，以免引发无限死循环对话。

输出格式（当用户确认立项时）：
```json
{
  "project_title": "项目标题",
  "objective": "核心目标",
  "constraints": ["约束条件列表"],
  "tech_preferences": ["技术偏好"],
  "acceptance_criteria": ["验收标准"],
  "priority": "high/medium/low",
  "estimated_complexity": "1-10",
  "task_type": "SOFTWARE / ENGINEERING / DESIGN / RESEARCH"
}
```

**关于 task_type 的严格分类**：
- **SOFTWARE**: 软件开发、代码编写、脚本、算法实现。
- **ENGINEERING**: 工程方案、施工计划、机械结构、风险评估、系统架构。
- **DESIGN**: 工业设计、外观造型、平面设计、用户体验、3D建模概念。
- **RESEARCH**: 科学调研、文献综述、数据分析、趋势研究、实验设计。
"""


class CKOAgent(BaseAgent):
    """CKO 首席知识官 Agent

    【临时】使用智谱 GLM API 进行测试。
    正式版应切回 Google Gemini API。
    """

    def __init__(self, parent=None, tool_manager=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("CKO", {"provider": "deepseek", "model": "deepseek-chat"})

        super().__init__(
            role="CKO",
            model_config=model_config,
            system_prompt=CKO_SYSTEM_PROMPT,
            parent=parent,
            tool_manager=tool_manager,
        )
        self._client = None

        # 注册原生 Function Calling 工具
        self._register_crew_tools()

    def _register_crew_tools(self):
        """注册 CrewAI 工具作为原生 Function Calling 工具"""
        if not TOOLS_AVAILABLE or (RequirementsAnalyzerTool is None and KnowledgeRetrievalTool is None):
            print("[CKOAgent] 工具不可用，跳过注册")
            return

        try:
            # RequirementsAnalyzerTool - 需求分析工具
            if RequirementsAnalyzerTool is not None:
                requirements_analyzer = RequirementsAnalyzerTool()
                def analyze_requirements(user_input: str, analysis_depth: str = "standard", domain_hint: str = "") -> str:
                    """分析用户需求，生成结构化追问问题"""
                    return requirements_analyzer._run(user_input=user_input, analysis_depth=analysis_depth, domain_hint=domain_hint)
                self.register_tool(analyze_requirements, name="requirements_analyzer",
                                 description="深度分析用户需求，生成结构化追问问题。输入用户需求描述、分析深度和领域提示，输出需要进一步澄清的问题列表。")
            else:
                print("[CKOAgent] RequirementsAnalyzerTool不可用，跳过注册")

            # KnowledgeRetrievalTool - 知识检索工具
            if KnowledgeRetrievalTool is not None:
                knowledge_retriever = KnowledgeRetrievalTool()
                def retrieve_knowledge(query: str, knowledge_base_path: str = "data/knowledge",
                                      max_results: int = 5, search_mode: str = "keyword") -> str:
                    """从知识库中检索相关信息"""
                    return knowledge_retriever._run(
                        query=query,
                        knowledge_base_path=knowledge_base_path,
                        max_results=max_results,
                        search_mode=search_mode
                    )
                self.register_tool(retrieve_knowledge, name="knowledge_retriever",
                                 description="从知识库中检索相关信息。输入查询语句、知识库路径、最大结果数和搜索模式，输出结构化知识摘要和相关文档引用。")
            else:
                print("[CKOAgent] KnowledgeRetrievalTool不可用，跳过注册")

            print(f"[CKOAgent] 已注册 {len(self.tools)} 个工具")
        except Exception as e:
            print(f"[CKOAgent] 工具注册失败: {e}")

    def _init_client(self):
        """延迟初始化客户端"""
        if self._client is None:
            provider = self.model_config.get("provider", "gemini")
            
            if provider == "gemini":
                try:
                    import google.generativeai as genai
                    api_key = API_KEYS.get("gemini", "")
                    if api_key:
                        genai.configure(api_key=api_key)
                        self._client = genai
                    else:
                        raise ValueError("GEMINI_API_KEY 未配置")
                except ImportError:
                    raise ImportError("请安装 google-generativeai: pip install google-generativeai")

            elif provider == "deepseek":
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

            elif provider == "novai":
                try:
                    from openai import OpenAI
                    api_key = API_KEYS.get("novai", "")
                    base_url = self.model_config.get("base_url", "https://once.novai.su/v1")
                    if api_key:
                        self._client = OpenAI(
                            api_key=api_key,
                            base_url=base_url,
                            max_retries=5,
                        )
                    else:
                        print("Warning: NOVAI_API_KEY not found.")
                except ImportError:
                    pass

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
                        raise ValueError("HIAPI_API_KEY (used for CKO) 未配置")
                except ImportError:
                    raise ImportError("请安装 openai: pip install openai")

    def _parse_docx(self, path):
        """解析 Word 文档，提取文本和图片"""
        import docx
        import zipfile
        import io
        from PIL import Image

        text = ""
        images = []
        try:
            doc = docx.Document(path)
            text = "\n".join([para.text for para in doc.paragraphs])
            
            # Extract images from zip structure
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.startswith("word/media/") and name.lower().endswith(('.png', '.jpg', '.jpeg')):
                        img_data = z.read(name)
                        try:
                            img = Image.open(io.BytesIO(img_data))
                            images.append(img)
                        except Exception:
                            continue
        except Exception as e:
            text = f"[Error parsing document: {e}]"
            
        return text, images

    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用 AI API (支持多模态文档和原生 Function Calling)"""
        self._init_client()
        provider = self.model_config.get("provider", "gemini")

        if provider == "gemini":
            # Gemini 调用逻辑（Gemini 工具调用需要不同处理，这里简化）
            import re

            gemini_history = []
            system_instruction = self.system_prompt

            # Check for attachment in the last user message
            last_user_msg = None
            attachment_path = None

            # Pre-process messages to find attachment tag
            clean_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    content = msg["content"]
                    match = re.search(r"\[ATTACHMENT: (.*?)\]", content)
                    if match:
                        attachment_path = match.group(1)
                        content = content.replace(match.group(0), "").strip()
                    clean_messages.append({"role": "user", "content": content})
                else:
                    clean_messages.append(msg)

            # Build History
            for msg in clean_messages[:-1]: # All except last
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    gemini_history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    gemini_history.append({"role": "model", "parts": [msg["content"]]})

            # Handle Last Message (with potential attachment)
            last_msg_content = clean_messages[-1]["content"] if clean_messages else ""
            input_parts = [last_msg_content]

            if attachment_path:
                doc_text, doc_images = self._parse_docx(attachment_path)
                input_parts.append(f"\n\n[ATTACHED DOCUMENT CONTENT]:\n{doc_text}\n")
                if doc_images:
                    input_parts.append("\n[ATTACHED IMAGES]:\n")
                    input_parts.extend(doc_images)

            model = self._client.GenerativeModel(
                model_name=self.model_config["model"],
                system_instruction=system_instruction
            )

            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(input_parts)
            return response.text

        elif provider == "zhipuai":
            # 智谱 GLM 调用（可能不支持工具调用）
            response = self._client.chat.completions.create(
                model=self.model_config["model"],
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content

        elif provider in ("deepseek", "hiapi", "novai"):
            try:
                print(f"DEBUG: CKOAgent calling {provider} with model {self.model_config['model']}")
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
                    content = message.content or ""
                    print(f"DEBUG: CKOAgent ({provider}) response received: {len(content)} chars")
                    return content
            except Exception as e:
                print(f"DEBUG: CKOAgent ({provider}) API Error: {e}")
                return f"Error ({provider}): {e}"

        return "⚠️ 未知的模型提供商配置"

    def audit_node(self, stage: str, context: str, mission_protocol: str) -> str:
        """执行关键节点审计 (Vision Keeper)

        Args:
            stage: 当前审计阶段 (e.g., "Design Phase", "Verification Phase")
            context: 待审计的内容 (e.g., 架构方案, 测试报告)
            mission_protocol: 原始任务书 (Mission Protocol)

        Returns:
            审计结果 (PASS 或 FAIL: 原因)
        """
        self._init_client()
        
        # 根据阶段定制提示词
        stage_instruction = ""
        if "Debate" in stage:
            stage_instruction = (
                "**注意**：当前处于[方案博弈阶段]，尚未进入编码环节。\n"
                "你应该重点审计：\n"
                "1. 架构方案与其设计是否能够支撑 Mission Protocol 的目标？\n"
                "2. 是否存在逻辑漏洞或未被满足的关键约束？\n"
                "3. **切勿**以'没有代码'为由驳回，此阶段本来就不包含代码。"
            )
        elif "Verification" in stage:
            stage_instruction = (
                "**注意**：当前处于[验收阶段]。\n"
                "你应该重点审计：\n"
                "1. 最终产出是否达到了 Mission Protocol 定义的验收标准？\n"
                "2. 测试结果是否通过？"
            )

        audit_system_prompt = (
            "你是项目的守护者 (Vision Keeper)。你的职责是确保项目在关键节点"
            "严格遵守最初的 Mission Protocol (任务书)。\n"
            "请对比 [任务书] 和 [当前产出]，判断是否存在偏离。\n\n"
            f"{stage_instruction}\n\n"
            "输出规则：\n"
            "1. 如果符合或偏差可接受：仅输出 'PASS'\n"
            "2. 如果严重偏离：输出 'FAIL: [具体原因]'\n"
            "不要输出其他废话。"
        )

        audit_msg = (
            f"Stage: {stage}\n\n"
            f"## Mission Protocol (基准):\n{mission_protocol}\n\n"
            f"## Current Artifact (当前产出):\n{context}\n\n"
            f"请进行审计。"
        )

        try:
            provider = self.model_config.get("provider", "gemini")
            if provider == "gemini":
                # Gemini 调用
                model = self._client.GenerativeModel(
                    model_name=self.model_config["model"],
                    system_instruction=audit_system_prompt
                )
                response = model.generate_content(audit_msg)
                return response.text.strip()
            
            else:
                # OpenAI / DeepSeek / ZhipuAI 调用
                response = self._client.chat.completions.create(
                    model=self.model_config["model"],
                    messages=[
                        {"role": "system", "content": audit_system_prompt},
                        {"role": "user", "content": audit_msg}
                    ],
                    temperature=0.1,  # 审计需要严谨
                    max_tokens=500,
                )
                return response.choices[0].message.content.strip()
        except Exception as e:
            return f"FAIL: 审计过程发生错误 - {str(e)}"

