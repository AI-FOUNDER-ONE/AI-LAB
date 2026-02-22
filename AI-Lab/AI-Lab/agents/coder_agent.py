"""
coder_agent.py - Coder 程序员 (通义千问)
======================================
读取方案规范，输出完整的代码文件。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS
# 尝试导入工具，如果crewai不可用则提供空值
try:
    from tools.tool_schema_adapter import crew_tool_to_schema
    from tools.crew_tools import CodeWriterTool, DocxParserTool
    from tools.code_review_tool import CodeReviewTool
    from tools.documentation_generator_tool import DocumentationGeneratorTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    # crewai可能不可用，提供空值
    TOOLS_AVAILABLE = False
    crew_tool_to_schema = None
    CodeWriterTool = None
    DocxParserTool = None
    CodeReviewTool = None
    DocumentationGeneratorTool = None
    print(f"[CoderAgent] 工具导入警告: {e}. 原生Function Calling工具将不可用。")


CODER_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 Executor（执行官）。
你的核心职责是根据 Upstream（上游）确定的方案和指令，产出最终的执行成果。

**你的行为准则**：
1. **绝对服从指令**：严格按照 Mission Protocol 和 PM/Arch/Designer 的要求执行。
2. **格式规范**：输出内容必须结构清晰，符合 Markdown 标准。
3. **专业性**：
   - 如果是代码任务，遵循 Google 编程规范。
   - 如果是文档任务，逻辑严密，论证充分。
   - 如果是设计任务，关注细节和可行性。

不要自行猜测任务类型，请根据当前的 Prompt 指令行动。
使用中文沟通。
"""


class CoderAgent(BaseAgent):
    """Coder 程序员 Agent

    使用通义千问 (Qwen) API 实现（兼容 OpenAI API 格式）。
    负责根据规范编写代码。
    """

    def __init__(self, parent=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("Coder", {"provider": "qwen", "model": "qwen-max"})

        super().__init__(
            role="Coder",
            model_config=model_config,
            system_prompt=CODER_SYSTEM_PROMPT,
            parent=parent,
        )
        self._client = None

        # 注册原生 Function Calling 工具（示例）
        self._register_crew_tools()

    def _register_crew_tools(self):
        """注册 CrewAI 工具作为原生 Function Calling 工具"""
        if not TOOLS_AVAILABLE or CodeWriterTool is None or DocxParserTool is None:
            print("[CoderAgent] 工具不可用，跳过注册")
            return

        try:
            # 1. CodeWriterTool - 代码写入工具
            code_writer = CodeWriterTool()
            def write_code(filename: str, code: str) -> str:
                """将代码写入指定文件"""
                return code_writer._run(filename=filename, code=code)
            self.register_tool(write_code, name="code_writer",
                             description="将代码写入指定文件。输入文件名和代码内容。")

            # 2. DocxParserTool - 文档解析工具
            docx_parser = DocxParserTool()
            def parse_document(path: str) -> str:
                """解析文档文件，提取所有内容"""
                return docx_parser._run(path=path)
            self.register_tool(parse_document, name="document_parser",
                             description="深度解析文档文件，提取所有内容。支持 .docx、.pdf、.txt、.md 等格式。")

            # 3. CodeReviewTool - 代码审查工具
            if CodeReviewTool is not None:
                code_review = CodeReviewTool()
                def review_code(code: str, review_focus: str = "all", language: str = "python") -> str:
                    """对代码进行静态分析，提供审查建议"""
                    return code_review._run(code=code, review_focus=review_focus, language=language)
                self.register_tool(review_code, name="code_reviewer",
                                 description="对代码进行静态分析，提供审查建议。支持安全、性能、编码规范、逻辑等多方面审查。目前仅支持Python语言。")
            else:
                print("[CoderAgent] CodeReviewTool不可用，跳过注册")

            # 4. DocumentationGeneratorTool - 文档生成工具
            if DocumentationGeneratorTool is not None:
                doc_generator = DocumentationGeneratorTool()
                def generate_documentation(source: str, doc_type: str = "api",
                                         format: str = "markdown", language: str = "python") -> str:
                    """根据代码或需求自动生成文档"""
                    return doc_generator._run(source=source, doc_type=doc_type,
                                            format=format, language=language)
                self.register_tool(generate_documentation, name="documentation_generator",
                                 description="根据代码或需求自动生成文档。支持API文档、用户手册、技术文档、README等多种类型。输入代码或描述，输出结构化文档。")
            else:
                print("[CoderAgent] DocumentationGeneratorTool不可用，跳过注册")

            print(f"[CoderAgent] 已注册 {len(self.tools)} 个工具")
        except Exception as e:
            print(f"[CoderAgent] 工具注册失败: {e}")

    def _init_client(self):
        """延迟初始化客户端（支持 Qwen 和 Custom Claude）"""
        if self._client is None:
            provider = self.model_config.get("provider", "qwen")
            
            try:
                from openai import OpenAI
                
                if provider == "qwen":
                    api_key = API_KEYS.get("qwen", "")
                    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                elif provider == "claude_custom":
                    api_key = API_KEYS.get("claude_custom", "")
                    # 用户提供的 Endpoint
                    base_url = self.model_config.get("base_url", "https://yunyi.rdzhvip.com/claude")
                elif provider == "bigmodel":
                    api_key = API_KEYS.get("bigmodel", "")
                    base_url = self.model_config.get("base_url", "https://open.bigmodel.cn/api/coding/paas/v4")
                else:
                    raise ValueError(f"CoderAgent 不支持的 Provider: {provider}")

                if api_key:
                    self._client = OpenAI(
                        api_key=api_key,
                        base_url=base_url,
                        max_retries=5,
                    )
                else:
                    raise ValueError(f"{provider.upper()}_API_KEY 未配置")
                    
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")

    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用通义千问 API，支持原生 Function Calling

        增强：自动识别文档克隆指令
        """
        self._init_client()

        # --- 智能意图识别 (Simple Heuristic for Cloning) ---
        # 检查最新的一条 User 消息是否包含特定的克隆指令格式
        # 约定格式： "MISSION: DOCUMENT_CLONING"
        # 或者在内容中寻找 "原型文档：" 和 "新内容：" 的关键词
        if messages and messages[-1]["role"] == "user":
            user_content = messages[-1]["content"]
            if "MISSION: DOCUMENT_CLONING" in user_content or ("【原型文档】" in user_content and "【新内容】" in user_content):
                import re

                # 尝试提取
                prototype_match = re.search(r"【原型文档】[:\s]*([\s\S]*?)(?=【新内容】|$)", user_content)
                new_content_match = re.search(r"【新内容】[:\s]*([\s\S]*)", user_content)

                if prototype_match and new_content_match:
                    proto = prototype_match.group(1).strip()
                    new_c = new_content_match.group(1).strip()

                    if proto and new_c:
                        # 触发克隆逻辑
                        return self.run_document_cloning(proto, new_c)

        # 常规调用
        provider = self.model_config.get("provider", "qwen")
        if provider == "claude_custom":
            # Claude 自定义端点可能不支持工具调用，回退到无工具
            return self._call_api_claude(messages)

        # 准备 API 调用参数
        api_kwargs = {
            "model": self.model_config["model"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000,
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

    def _call_api_claude(self, messages: list, tools: list = None) -> str:
        """调用 Claude Endpoint (Anthropic Native Format)"""
        import httpx
        import json
        
        api_key = API_KEYS.get("claude_custom", "")
        # base_url Should be .../v1/messages for Anthropic
        # But we determined the working URL is https://yunyi.rdzhvip.com/claude/v1/messages
        url = "https://yunyi.rdzhvip.com/claude/v1/messages"
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # 转换消息格式 (提取 System Prompt)
        system_prompt = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt += msg["content"] + "\n"
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
        
        payload = {
            "model": self.model_config["model"], # claude-opus-4-6
            "messages": anthropic_messages,
            "max_tokens": 4096,
            "temperature": 0.7
        }
        
        # fix: yunyi.rdzhvip.com rejects top-level 'system' param with 500 error.
        # It accepts 'role: system' in messages (OpenAI-style behavior).
        if system_prompt:
            # Insert system prompt as the first message
            payload["messages"].insert(0, {"role": "system", "content": system_prompt.strip()})

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                # Parse Anthropic Response
                # {"content": [{"text": "..."}]}
                content_blocks = data.get("content", [])
                text_content = "".join([block.get("text", "") for block in content_blocks if block.get("type") == "text"])
                return text_content
                
        except Exception as e:
            raise RuntimeError(f"Claude API 调用失败: {str(e)}")

    def run_document_cloning(self, prototype_input: str, new_content_input: str) -> str:
        """执行文档克隆与重组任务
        
        Args:
            prototype_input: 原型文档内容 或 .docx 文件路径
            new_content_input: 新内容文本 或 .docx 文件路径
            
        Returns:
            生成的 JSON 结构化文档/字符串 (如果是文件模式，返回保存路径信息)
        """
        self._init_client()
        
        from core.doc_logic_engine import DocumentLogicEngine
        import json
        import os
        from config import GENERATED_DOCS_DIR
        
        # 适配器逻辑
        client = self._client
        if self.model_config.get("provider") == "claude_custom":
            client = ClaudeAdapter(self)

        engine = DocumentLogicEngine(client, self.model_config["model"])
        
        # --- 1. 输入预处理 (自动读取文件) ---
        prototype_text = prototype_input
        if os.path.exists(prototype_input) and prototype_input.endswith(".docx"):
            try:
                prototype_text = engine.read_docx(prototype_input)
                # self.stream_chunk.emit(self.role, f"已读取原型文档: {os.path.basename(prototype_input)}\n")
            except Exception as e:
                return f"读取原型文档失败: {str(e)}"

        # 暂时只支持新内容为文本，或者简单读取
        new_content_text = new_content_input
        if os.path.exists(new_content_input) and new_content_input.endswith(".docx"):
            try:
                new_content_text = engine.read_docx(new_content_input)
                # self.stream_chunk.emit(self.role, f"已读取新内容文档: {os.path.basename(new_content_input)}\n")
            except Exception as e:
                return f"读取新内容文档失败: {str(e)}"

        # --- 2. 核心处理 ---
        self.typing_started.emit(self.role)
        try:
            # 分析
            structure = engine.analyze_prototype(prototype_text)
            
            # 重组
            result_json = engine.process_content_to_template(new_content_text, structure)
            
            # --- 3. 结果后处理 (生成文件) ---
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"ClonedDoc_{timestamp}.docx"
            output_path = os.path.join(GENERATED_DOCS_DIR, filename)
            
            try:
                engine.save_to_docx(result_json, output_path)
                msg = f"""文档克隆完成！
                
生成的 JSON 结构已转换为 Word 文档。
保存路径: {output_path}
"""
                return msg
            except Exception as e:
                return f"文档生成成功但保存失败: {str(e)}\nJSON结果:\n{json.dumps(result_json, ensure_ascii=False, indent=2)}"
            
        except Exception as e:
            return f"文档克隆失败: {str(e)}"
        finally:
            self.typing_finished.emit(self.role)


class ClaudeAdapter:
    """Adapts CoderAgent's Claude implementation to OpenAI interface for DocumentLogicEngine"""
    def __init__(self, agent):
        self.agent = agent
        self.chat = self
        self.completions = self
        
    def create(self, model, messages, **kwargs):
        # Delegate to the agent's internal logic
        # Note: DocumentLogicEngine sends response_format={"type": "json_object"}, 
        # but Claude handles JSON via prompt usually.
        # We invoke _call_api_claude which returns a string.
        
        content = self.agent._call_api_claude(messages)
        
        # Mock OpenAI Response Object structure
        class MockMessage:
            def __init__(self, c): self.content = c
        class MockChoice:
            def __init__(self, c): self.message = MockMessage(c)
        class MockResponse:
            def __init__(self, c): self.choices = [MockChoice(c)]
            
        return MockResponse(content)
