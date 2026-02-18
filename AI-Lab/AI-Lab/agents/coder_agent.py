"""
coder_agent.py - Coder 程序员 (通义千问)
======================================
读取方案规范，输出完整的代码文件。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS


CODER_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 Executor（执行官），你的核心职责是将 Detailed Design（详细设计）转化为可落地的执行成果。

根据任务性质，你的输出有两种模式：

🔹 **模式 A：软件开发任务**
- **上下文感知**：你不仅要参考架构和设计文档，**必须**仔细阅读《完整会议记录 (Context)》，理解 PM、Arch 和 Designer 的博弈过程，捕捉隐含的修正和约束。
- 输出：完整的、可运行的源代码
- 规范：Google 编程规范，包含详细中文注释
- 兼容性：确保在 Windows 环境下运行

🔹 **模式 B：非软件任务（文档/方案/设计）**
- **智能识别**：根据 Mission Protocol 判断输出类型，可能是：
  1. **工程开发项目计划书**：包含WBS分解、甘特图（Mermaid）、资源预算。
  2. **科研项目立项申请书**：包含研究背景、技术路线、创新点、预期成果。
  3. **可行性研究报告**：包含市场分析、技术可行性、经济效益分析。
  4. **工业设计方案**：包含外观描述、材质工艺、人机工程学分析。
- **输出格式**：
  - 必须使用标准 **Markdown** 格式。
  - 结构清晰，层级分明。
  - 遇到图表时，使用 Mermaid 代码块绘制（如甘特图、流程图）。

🔹 **模式 C：知识探究报告 (Knowledge Research w/ Fact-Check)**
- **适用场景**：`task_type="knowledge_research"`
- **输出**：一份**深度研究报告**
- **核心要求**：
  1. **多视角辩证**：整合 Arch 的理论视角和 Designer 的实证视角。
  2. **消除幻觉**：对于有争议的数据或事实，标注"存在争议"或引用具体来源。
  3. **结构建议**：
     - **核心结论** (Executive Summary)
     - **理论框架** (Theoretical Basis - from Arch)
     - **实证/数据** (Evidence & Analysis - from Designer)
     - **潜在风险/争议点** (Critical Uncertainties)

**智能判断**：
请优先检查 Mission Protocol 中的 `task_type` 字段：
- 如果 `task_type` 是 "software_development" -> 走模式 A。
- 如果 `task_type` 是 "document_writing" 或 "industrial_design" -> 走模式 B。
- 如果 `task_type` 是 "knowledge_research" -> 走模式 C。
- 如果未指定，则根据 Architects 和 Designer 的方案内容自动判断。

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
                    base_url = "https://yunyi.rdzhvip.com/claude"
                else:
                    raise ValueError(f"CoderAgent 不支持的 Provider: {provider}")

                if api_key:
                    self._client = OpenAI(
                        api_key=api_key,
                        base_url=base_url,
                    )
                else:
                    raise ValueError(f"{provider.upper()}_API_KEY 未配置")
                    
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")

    def _call_api(self, messages: list) -> str:
        """调用通义千问 API
        
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
            return self._call_api_claude(messages)
            
        response = self._client.chat.completions.create(
            model=self.model_config["model"],
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )
        return response.choices[0].message.content

    def _call_api_claude(self, messages: list) -> str:
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
