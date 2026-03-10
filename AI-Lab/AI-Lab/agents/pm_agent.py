"""
pm_agent.py - PM 项目经理 (通义千问)
====================================
审查 Arch 和 Designer 的方案，决定是否批准或要求迭代。
"""

from agents.base_agent import BaseAgent
from config import API_KEYS, AppState

# 尝试导入工具
try:
    from tools.risk_assessment_tool import RiskAssessmentTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    # 工具可能不可用，提供空值
    TOOLS_AVAILABLE = False
    RiskAssessmentTool = None
    print(f"[PMAgent] 工具导入警告: {e}. 原生Function Calling工具将不可用。")


PM_SYSTEM_PROMPT = """你是 AI-Lab-Commander 的 PM（项目经理），代号"决策裁判"。
你的核心职责：
1. **担任动态圆桌会议主持人**：审视当前对话进展，决定下一位发言者是谁，或者宣布讨论结束。
2. **审查方案**：评估 Architect 的逻辑框架和 Designer 的实现方案，指出漏洞或风险。
3. **推动共识**：引导团队在 Mission Protocol 的约束下达成一致。
4. **理性审视**：随时审视 Arch 的架构和 Designer 的方案是否**合理**（可行性、成本、效率）。
5. **方向纠偏**：主动邀请 CKO 确认当前方向是否偏离设计意图。
6. **知识探究（针对 task_type="knowledge_research"）**：
   - 此时你是"首席研究员"，你的目标是**Fact-Checking（事实查证）**。
   - 引导 Arch 提供**理论依据**或宏观视角。
   - 引导 Designer 提供**反例**、**实证**或微观数据。
   - 确保结论经过了充分的辩论和交叉验证。

工作流程：
- 分析当前上下文。
- 判断还需要谁的输入？（例如：Arch 的方案缺细节 -> 呼叫 Designer；Designer 的实现偏离架构 -> 呼叫 Arch）。
- **流程强制**：在 Arch 的架构定稿后，**必须**邀请 Designer 进行详细设计。只有当 Designer 也完成了方案，且双方达成一致后，才能宣布 APPROVE。
- 如果方案已成熟且达成共识 -> 宣布 APPROVE。

输出规范（非常重要）：
1. **自然语言主持/点评**（**必须精简**）：
   - 在对话框中显示的文本必须**言简意赅**（建议 3-5 句话）。
   - **不要**长篇大论或重复技术细节，直接给出核心态度（同意/反对/质疑）和关键理由。
   - 像一位高效的 CEO 或主持人，直击要点。
   - ⚠️ **严禁客套与随意使用 `@角色名` 提及他人**：系统依赖 `@` 符号进行高优先级路由。如果你不想立刻把麦克风强塞给别人，**绝对不要**在文本里带 `@` 符号。
   
2. **决策指令**（必须放在最后，独占一行）：
   - 格式：`下一发言者: [角色名]` 或 `决策: [结果]`
   
   **指令选项**：
   - `下一发言者: Arch`  (架构师发言)
   - `下一发言者: Designer` (设计师发言)
   - `下一发言者: CKO`   (呼叫 CKO 确认方向)
   - `决策: 通过`  (批准方案)
   - `决策: 驳回`  (驳回方案)

示例 1 (继续讨论)：
Designer 的方案不错，但可能超预算。Arch，请确认架构约束。
下一发言者: Arch

示例 2 (呼叫 CKO)：
大家的讨论似乎有点偏离了"轻量级"这个初衷。CKO，请帮我们回顾一下 Mission Protocol 的约束。
下一发言者: CKO

示例 3 (批准)：
方案已完善，批准执行。
决策: 通过

使用中文沟通。
"""


class PMAgent(BaseAgent):
    """PM 项目经理 Agent

    使用通义千问 (Qwen) API 实现（兼容 OpenAI API 格式）。
    负责审查和批准方案。
    """

    def __init__(self, parent=None, tool_manager=None):
        # 从配置中动态加载模型参数
        from config import AGENT_MODELS
        model_config = AGENT_MODELS.get("PM", {"provider": "xai", "model": "grok-2-latest"})

        super().__init__(
            role="PM",
            model_config=model_config,
            system_prompt=PM_SYSTEM_PROMPT,
            parent=parent,
            tool_manager=tool_manager,
        )
        self._client = None

        # 注册原生 Function Calling 工具
        self._register_tools()

    def _register_tools(self):
        """注册 PM 专用工具"""
        # 首先注册三个核心工作流工具（通过闭包注入 state_ctrl / router / ctx，直接触发状态与路由）
        try:
            def delegate_to_role(role_name: str, instruction: str = "") -> str:
                """将发言权委托给指定角色，可以附带简要指令。直接设置下一发言者。"""
                parent = self.parent()
                router = getattr(parent, "router", None) if parent else None
                if router and hasattr(router, "set_forced_next_speaker"):
                    router.set_forced_next_speaker(role_name.strip())
                    return f"已将发言权交给 {role_name}" + (f"，指令：{instruction}" if instruction else "")
                return f"已将发言权交给 {role_name}（路由未就绪，由系统自动分配）"

            self.register_tool(
                delegate_to_role,
                name="delegate_to_role",
                description="将发言权委托给指定角色（Arch、Designer、Coder、Validator、CKO）。可以附带简要指令。"
            )

            def approve_solution(reason: str) -> str:
                """批准当前方案，进入执行阶段。直接触发状态机转换。"""
                parent = self.parent()
                state_ctrl = getattr(parent, "state_ctrl", None) if parent else None
                if not state_ctrl:
                    return "错误：无法获取状态控制器，请稍后重试。"
                ok = state_ctrl.transition_to(AppState.PRODUCTION, trigger="PM approved")
                if ok:
                    return f"方案已批准（理由：{reason or '无'}），已进入执行阶段。"
                return "状态转换失败：当前阶段不允许进入执行阶段，请确认是否处于方案博弈阶段且方案已就绪。"

            self.register_tool(
                approve_solution,
                name="approve_solution",
                description="批准当前方案，进入下一阶段。需要提供批准理由。"
            )

            def reject_solution(reason: str) -> str:
                """驳回当前方案，要求重新讨论。将反馈写入上下文，保持 DEBATE。"""
                parent = self.parent()
                ctx = getattr(parent, "ctx", None) if parent else None
                if ctx:
                    from core.context import MessageIntent
                    ctx.add_message("PM", f"方案被驳回。理由：{reason}", MessageIntent.CRITIQUE)
                return f"方案被驳回，原因：{reason}，继续 DEBATE。"

            self.register_tool(
                reject_solution,
                name="reject_solution",
                description="驳回当前方案，要求重新讨论。需要提供驳回理由。"
            )

            print(f"[PMAgent] 已注册核心工作流工具: delegate_to_role, approve_solution, reject_solution")
        except Exception as e:
            print(f"[PMAgent] 核心工作流工具注册失败: {e}")

        # checklist_tracker - 阶段交付物清单（session_store 闭包注入）
        try:
            from tools.checklist_tracker import checklist_tracker as _checklist_tracker
            def checklist_tracker(action: str, stage: str = "", item: str = "") -> dict:
                store = (self.parent().session_store if self.parent() and getattr(self.parent(), "session_store", None) else None)
                return _checklist_tracker(action=action, stage=stage, item=item, session_store=store)
            self.register_tool(
                checklist_tracker,
                name="checklist_tracker",
                description="管理阶段交付物清单。action: create(创建阶段清单)、check(标记完成)、uncheck(标记未完成)、status(查看状态)、is_ready(检查是否可推进下一阶段)。stage: GROUNDING/DEBATE/PRODUCTION/VERIFICATION。"
            )
        except Exception as e:
            print(f"[PMAgent] checklist_tracker 注册失败: {e}")

        # context_retriever - 从 meeting_logs 语义检索历史（session_store 闭包注入）
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
            print(f"[PMAgent] context_retriever 注册失败: {e}")

        # json_schema_validator - 校验 JSON 是否符合内置 Schema
        try:
            from tools.json_schema_validator import json_schema_validator
            self.register_tool(
                json_schema_validator,
                name="json_schema_validator",
                description="校验 JSON 字符串是否符合预定义 Schema。schema_name: mission_protocol / validation_report / delivery_summary。返回 valid、errors、parsed。"
            )
        except Exception as e:
            print(f"[PMAgent] json_schema_validator 注册失败: {e}")

        # 原有风险评估工具（可选）
        if not TOOLS_AVAILABLE or RiskAssessmentTool is None:
            print("[PMAgent] 风险评估工具不可用，跳过注册")
            return

        try:
            # RiskAssessmentTool - 风险评估工具
            risk_assessor = RiskAssessmentTool()
            def assess_risk(project_description: str, assessment_depth: str = "standard",
                          industry: str = "software") -> str:
                """对项目方案进行多维度风险评估"""
                return risk_assessor._run(
                    project_description=project_description,
                    assessment_depth=assessment_depth,
                    industry=industry
                )
            self.register_tool(assess_risk, name="risk_assessor",
                             description="对项目方案进行多维度风险评估。输入项目描述，输出包含技术、时间、成本、团队、依赖、市场等维度的结构化风险评估报告。")

            print(f"[PMAgent] 已注册 {len(self.tools)} 个工具（包含风险评估工具）")
        except Exception as e:
            print(f"[PMAgent] 风险评估工具注册失败: {e}")

    def _init_client(self):
        """延迟初始化客户端"""
        if self._client is None:
            from core.llm_client_factory import create_llm_client
            self._client = create_llm_client(
                self.model_config.get("provider", "qwen"), self.model_config
            )

    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用通义千问 API，支持原生 Function Calling"""
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

        # 检查是否有工具调用（PM 通常不需要工具，但保持接口一致）
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
