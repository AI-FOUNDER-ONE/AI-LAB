"""
unified_orchestrator.py - 统一多智能体编排引擎（全新设计）
==========================================================

结合 V1（状态机驱动）和 V2（事件驱动）的优点，提供更智能、安全、可扩展的协作框架。

核心设计原则：
1. 事件驱动 + 状态机引导：动态路由 + 结构化流程
2. 智能多策略路由：不依赖单一关键词，基于上下文意图
3. 共识形成机制：多角色投票，辩论总结，妥协方案
4. 统一工具平台：安全沙箱，权限控制，集中管理
5. 模块化架构：可插拔组件，易于扩展

架构组件：
- UnifiedOrchestrator: 主编排器
- EnhancedConversationContext: 增强上下文（支持情感分析、意图识别）
- SmartRouter: 智能路由引擎（多策略决策）
- ConsensusEngine: 共识形成引擎（投票、辩论总结）
- ToolSecurityManager: 工具安全管理器（沙箱、权限控制）
- StateGuidanceEngine: 状态引导引擎（状态机 + 事件驱动）
"""

import os
import traceback
import re
import json
import time
from typing import Optional, List, Dict, Any, Callable, Set, Tuple
from enum import Enum
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

# 重用现有组件
from agents.cko_agent import CKOAgent
from agents.pm_agent import PMAgent
from agents.arch_agent import ArchAgent
from agents.designer_agent import DesignerAgent
from agents.coder_agent import CoderAgent
from agents.validator_agent import ValidatorAgent
from agents.base_agent import BaseAgent

from core.state_controller import StateController
from core.session_store import SessionStore
from core.global_tool_manager import GlobalToolManager
from core.tool_security import ToolPermission, ToolSecurityManager
from core.context import MessageIntent, Message, EnhancedConversationContext
from core.router import SmartRouter
from core.consensus import ConsensusEngine
from config import AppState, MAX_DEBATE_ROUNDS

# ==============================================================================
# 1. 工具安全管理器（框架）
# ==============================================================================

# class ToolPermission(Enum):
#     """工具权限级别"""
#     READ_ONLY = "read_only"      # 只读权限
#     LOCAL_EXECUTION = "local_execution"  # 本地执行（受限）
#     FULL_ACCESS = "full_access"  # 完全访问（危险）

class _ToolSecurityManager:
    """工具安全管理器：沙箱执行和权限控制"""

    def __init__(self):
        self.registered_tools: Dict[str, Dict] = {}  # 工具名称 -> 工具定义
        self.role_permissions: Dict[str, Set[str]] = {}  # 角色 -> 允许的工具集合
        self.execution_history: List[Dict] = []  # 执行历史

    def register_tool(self, tool_name: str, tool_func: Callable,
                     allowed_roles: List[str] = None,
                     permission_level: ToolPermission = ToolPermission.LOCAL_EXECUTION,
                     description: str = "") -> bool:
        """注册工具，设置权限"""
        if tool_name in self.registered_tools:
            return False

        self.registered_tools[tool_name] = {
            "function": tool_func,
            "permission_level": permission_level,
            "description": description,
            "allowed_roles": allowed_roles or []  # 空列表表示所有角色可用
        }

        # 更新角色权限
        if allowed_roles:
            for role in allowed_roles:
                if role not in self.role_permissions:
                    self.role_permissions[role] = set()
                self.role_permissions[role].add(tool_name)

        return True

    def can_execute(self, role: str, tool_name: str) -> bool:
        """检查角色是否有权限执行工具"""
        if tool_name not in self.registered_tools:
            return False

        tool_info = self.registered_tools[tool_name]
        allowed_roles = tool_info["allowed_roles"]

        # 如果允许的角色列表为空，表示所有角色可用
        if not allowed_roles:
            return True

        return role in allowed_roles

    def execute_tool_safely(self, role: str, tool_name: str, args: Dict) -> Dict[str, Any]:
        """安全执行工具（带沙箱）"""
        if not self.can_execute(role, tool_name):
            return {"success": False, "error": f"角色 '{role}' 无权执行工具 '{tool_name}'"}

        if tool_name not in self.registered_tools:
            return {"success": False, "error": f"工具 '{tool_name}' 未注册"}

        tool_info = self.registered_tools[tool_name]
        tool_func = tool_info["function"]
        permission_level = tool_info["permission_level"]

        # 记录执行开始
        exec_id = len(self.execution_history)
        start_time = time.time()

        try:
            # 根据权限级别应用不同的安全措施
            if permission_level == ToolPermission.READ_ONLY:
                # 只读工具：可以安全执行
                result = tool_func(**args)
            elif permission_level == ToolPermission.LOCAL_EXECUTION:
                # 本地执行：限制性沙箱
                result = self._execute_in_sandbox(tool_func, args)
            else:  # FULL_ACCESS
                # 完全访问：直接执行（危险）
                result = tool_func(**args)

            # 记录执行成功
            execution_record = {
                "id": exec_id,
                "timestamp": time.time(),
                "role": role,
                "tool": tool_name,
                "args": args,
                "success": True,
                "result": str(result)[:500],  # 截断长结果
                "duration": time.time() - start_time
            }
            self.execution_history.append(execution_record)

            return {"success": True, "result": result}

        except Exception as e:
            # 记录执行失败
            execution_record = {
                "id": exec_id,
                "timestamp": time.time(),
                "role": role,
                "tool": tool_name,
                "args": args,
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
            self.execution_history.append(execution_record)

            return {"success": False, "error": str(e)}

    def _execute_in_sandbox(self, tool_func: Callable, args: Dict) -> Any:
        """在沙箱中执行工具（基于子进程的隔离）"""
        import multiprocessing
        import pickle
        import traceback
        from multiprocessing import TimeoutError as MP_TimeoutError

        # 创建通信队列
        result_queue = multiprocessing.Queue()
        error_queue = multiprocessing.Queue()

        # 定义在子进程中执行的包装函数
        def worker(func_bytes: bytes, args_bytes: bytes, result_q, error_q):
            """子进程工作函数"""
            try:
                # 反序列化函数和参数
                import pickle
                func = pickle.loads(func_bytes)
                args_dict = pickle.loads(args_bytes)

                # 执行函数
                result = func(**args_dict)

                # 序列化结果
                result_q.put(("success", pickle.dumps(result)))

            except Exception as e:
                # 捕获异常并发送
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
                error_q.put(("error", pickle.dumps(error_info)))

        try:
            # 序列化函数和参数
            # 注意：函数必须是可pickle的（不能是lambda或闭包）
            func_bytes = pickle.dumps(tool_func)
            args_bytes = pickle.dumps(args)

            # 创建子进程
            process = multiprocessing.Process(
                target=worker,
                args=(func_bytes, args_bytes, result_queue, error_queue),
                daemon=True  # 主进程退出时子进程也会退出
            )

            process.start()

            # 等待结果，设置超时（30秒）
            timeout = 30
            process.join(timeout=timeout)

            if process.is_alive():
                # 超时，终止进程
                process.terminate()
                process.join(timeout=5)  # 等待终止
                if process.is_alive():
                    process.kill()  # 强制终止
                raise TimeoutError(f"工具执行超时（{timeout}秒）")

            # 检查结果
            if not result_queue.empty():
                status, result_bytes = result_queue.get()
                if status == "success":
                    return pickle.loads(result_bytes)

            if not error_queue.empty():
                status, error_bytes = error_queue.get()
                if status == "error":
                    error_info = pickle.loads(error_bytes)
                    error_msg = f"{error_info['type']}: {error_info['message']}"
                    raise RuntimeError(f"工具执行错误: {error_msg}")

            # 如果没有结果也没有错误，抛出异常
            raise RuntimeError("工具执行未返回结果")

        except (pickle.PickleError, EOFError) as e:
            # 序列化错误
            raise RuntimeError(f"工具无法序列化: {str(e)}")
        except Exception as e:
            # 其他错误
            raise RuntimeError(f"沙箱执行失败: {str(e)}")

# ==============================================================================
# 5. 统一编排器（主类）
# ==============================================================================

class UnifiedOrchestrator(QObject):
    """统一编排器：结合V1和V2的优点"""

    # 信号（保持与现有UI兼容）
    agent_response = pyqtSignal(str, str)
    state_changed = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)
    workflow_completed = pyqtSignal()
    debate_round_info = pyqtSignal(int, int)
    agent_typing = pyqtSignal(str, bool)
    agent_stream_chunk = pyqtSignal(str, str)

    # 内部信号
    _next_turn_ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. 核心组件
        self.state_ctrl = StateController(self)
        self.ctx = EnhancedConversationContext()
        self.router = SmartRouter(self.ctx)
        self.consensus_engine = ConsensusEngine(self.ctx)
        self.ctx.consensus_engine = self.consensus_engine  # 供 context 更新共识度
        self.tool_security = GlobalToolManager()
        self.session_store = SessionStore()

        # 2. Agent实例
        self.agents_map = self._create_agents()

        # 3. 连接信号
        self._connect_signals()

        # 4. 内部状态
        self._active_worker = None
        self._turn_count = 0
        self._max_turns = 100  # 安全限制

        # 5. 事件循环触发
        self._next_turn_ready.connect(self._process_next_turn)

        print("[UnifiedOrchestrator] 初始化完成")

    def _create_agents(self) -> Dict[str, BaseAgent]:
        """创建所有Agent实例"""
        agents = {
            "CKO": CKOAgent(self, self.tool_security),
            "PM": PMAgent(self, self.tool_security),
            "Arch": ArchAgent(self, self.tool_security),
            "Designer": DesignerAgent(self, self.tool_security),
            "Coder": CoderAgent(self, self.tool_security),
            "Validator": ValidatorAgent(self, self.tool_security)
        }

        # 连接Agent信号
        for role, agent in agents.items():
            agent.typing_started.connect(lambda r=role: self.agent_typing.emit(r, True))
            agent.typing_finished.connect(lambda r=role: self.agent_typing.emit(r, False))
            agent.stream_chunk.connect(self.agent_stream_chunk.emit)

        return agents

    def _connect_signals(self):
        """连接信号"""
        self.state_ctrl.state_changed.connect(self.state_changed.emit)
        self.state_ctrl.error_occurred.connect(self.error_occurred.emit)

    # ==========================================================================
    # 公共API（与现有UI兼容）
    # ==========================================================================

    def inject_user_message(self, message: str):
        """用户消息注入入口"""
        # 1. 在UI中显示
        self.agent_response.emit("Commander", message)

        # 2. 添加到上下文
        self.ctx.add_message("Commander", message, MessageIntent.COMMAND)
        self.session_store.append_meeting_log("Commander", message)

        # 3. 触发事件循环
        self._next_turn_ready.emit()

    def send_to_cko(self, message: str):
        """Bridge Panel入口（需求打磨阶段）"""
        if self.state_ctrl.current_state == AppState.IDLE:
            self.state_ctrl.transition_to(AppState.GROUNDING)
        # 首次发话时创建会话与独立项目目录
        if self.session_store.get_current_session() is None:
            self.session_store.create_session(user_intent=(message[:200] or "首次对话"))

        self.inject_user_message(message)

    def confirm_project(self):
        """用户确认立项"""
        # 1. 从上下文提取Mission Protocol
        last_cko_msg = None
        for msg in reversed(self.ctx.history):
            if msg.role == "CKO":
                last_cko_msg = msg.content
                break

        if last_cko_msg:
            try:
                match = re.search(r"```json(.*?)```", last_cko_msg, re.DOTALL)
                protocol_str = match.group(1).strip() if match else last_cko_msg
                self.ctx.mission_protocol = json.loads(protocol_str)
                self.ctx.task_type = self.ctx.mission_protocol.get("task_type", "").strip().upper() or "SOFTWARE"
                # 若 JSON 里写了非标准值，归一化
                if self.ctx.task_type not in ("SOFTWARE", "ENGINEERING", "DESIGN", "RESEARCH"):
                    self.ctx.task_type = self._infer_task_type(last_cko_msg)
            except Exception as e:
                print(f"Protocol解析错误: {e}")
                self.ctx.task_type = self._infer_task_type(last_cko_msg or "")
            if not self.ctx.task_type:
                self.ctx.task_type = "SOFTWARE"
        else:
            self.ctx.task_type = self._infer_task_type(self.ctx.get_recent_history(limit=5) or "")

        # 2. 更新Agent领域角色
        for role, agent in self.agents_map.items():
            if role != "CKO":
                agent.set_domain_persona(self.ctx.task_type)

        # 3. 转换到DEBATE阶段
        self.state_ctrl.transition_to(AppState.DEBATE)

        # 4. 系统消息
        sys_msg = f"项目已确认。模式: [{self.ctx.task_type}]。进入辩论阶段。"
        self.ctx.add_message("System", sys_msg, MessageIntent.STATEMENT)
        self.agent_response.emit("System", sys_msg)

        # 5. 触发事件循环
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    def request_rework(self, feedback: str):
        """任务完成后用户不满意：根据反馈回到方案博弈重新评审"""
        if self.state_ctrl.current_state != AppState.COMPLETED:
            print("[UnifiedOrchestrator] request_rework 仅在任务完成状态下可用")
            return
        if not self.state_ctrl.transition_to(AppState.DEBATE):
            self.error_occurred.emit("返工失败：无法回到方案博弈阶段")
            return
        sys_msg = "Commander 对交付结果不满意，要求团队根据以下反馈重新评审方案。"
        self.ctx.add_message("System", sys_msg, MessageIntent.STATEMENT)
        self.agent_response.emit("System", sys_msg)
        self.ctx.add_message("Commander", feedback, MessageIntent.COMMAND)
        self.session_store.append_meeting_log("Commander", feedback)
        self.agent_response.emit("Commander", feedback)
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    def new_session(self):
        """开始新会话"""
        print("[UnifiedOrchestrator] 开始新会话...")

        # 重置所有组件
        self.state_ctrl.reset()
        self.ctx = EnhancedConversationContext()
        self.router = SmartRouter(self.ctx)
        self.consensus_engine = ConsensusEngine(self.ctx)
        self.session_store.create_session(user_intent="新会话")
        self._turn_count = 0

        # 停止活跃worker
        if self._active_worker:
            self._active_worker.quit()

        # 通知UI
        self.agent_response.emit("System", "会话已重置。准备接收新命令。")

    def handle_user_intervention(self, message: str):
        """处理用户从 War Room 面板发起的干预指令（兼容V2 API）"""
        print(f"[UnifiedOrchestrator] 用户干预: {message[:30]}...")
        # 将用户干预作为 Commander 消息注入
        self.inject_user_message(message)

    def stop_all(self):
        """中止所有活跃的 Worker 线程（兼容V1 API）"""
        print("[UnifiedOrchestrator] 停止所有工作线程...")
        if self._active_worker:
            self._active_worker.quit()
            self._active_worker = None
        self.agent_response.emit("系统", "🛑 所有任务已中止。")

    # ==========================================================================
    # 事件循环处理
    # ==========================================================================

    def _process_next_turn(self):
        """主事件循环：决定谁发言并执行"""
        current_state = self.state_ctrl.current_state

        # 检查终止条件：IDLE/COMPLETED 不再继续；DELIVERY 为收尾阶段，不再安排下一人发言，避免任务完成后 AI 重复发言
        if current_state in (AppState.IDLE, AppState.COMPLETED, AppState.DELIVERY):
            return

        # 安全检查：防止无限循环
        self._turn_count += 1
        if self._turn_count > self._max_turns:
            self.agent_response.emit("System", f"⚠️ 达到最大交互次数({self._max_turns})，暂停自动流转。")
            return

        # 1. 智能路由决策
        next_role = self.router.decide_next_speaker(current_state)
        print(f"[UnifiedOrchestrator] 下一发言者: {next_role}")

        if not next_role:
            print(f"[UnifiedOrchestrator] 暂停自动流转，等待外部输入")
            return

        # 2. 获取 Agent
        agent = self.agents_map.get(next_role)
        if not agent:
            print(f"错误: 未知角色 {next_role}")
            return

        # 3. Coder 前加短延迟，避免紧接上一角色后立刻请求导致 429
        if next_role == "Coder":
            QTimer.singleShot(2500, lambda: self._run_agent(agent, current_state))
        else:
            self._run_agent(agent, current_state)

    def _run_agent(self, agent: BaseAgent, current_state: AppState):
        """运行Agent"""
        recent_history = self.ctx.get_recent_history(limit=10)
        workspace_dir = self.session_store.get_workspace_dir() or ""

        stage_name = getattr(current_state, "value", str(current_state))
        stage_instruction = self._get_stage_instruction(agent.role, current_state, stage_name)
        prompt = (
            f"你是War Room讨论组中的{agent.role}。\n"
            f"【当前阶段】: {stage_name}\n"
            f"【任务类型】: {self.ctx.task_type}\n\n"
            f"{stage_instruction}\n\n"
        )
        if agent.role == "Coder" and workspace_dir:
            prompt += (
                f"【项目产出目录】: {os.path.abspath(workspace_dir)}\n"
                f"请在此目录下按需搭建项目结构（如 src/、docs/、tests/）。"
                f"每个代码块第一行用注释指定相对路径，例如：\n"
                f"  // filename: src/main.py  或  # filename: docs/README.md\n"
                f"系统会自动创建子目录并保存。\n\n"
            )
        prompt += (
            f"【核心纪律要求】:\n"
            f"1. 使用流利、自然的中文回复，避免机器翻译腔。\n"
            f"2. 禁止互相吹捧、客套废话或无意义的认同。\n"
            f"3. 发言必须直奔主题，只输出干货、代码、实质性建议或决策。\n"
            f"4. 除非需要强制移交发言权，否则避免随意使用`@角色名`。\n"
            f"5. 如果达成共识或任务完成，请清楚表达。\n\n"
            f"--- 历史对话 ---\n{recent_history}\n\n"
            f"你的回复:"
        )

        # 使用Worker线程执行
        worker = AgentWorker(agent, prompt)
        worker.finished_with_result.connect(self._on_agent_finished)
        worker.error_occurred.connect(lambda r, e: self.error_occurred.emit(e))
        worker.finished.connect(worker.deleteLater)

        self._active_worker = worker
        worker.start()

    def _get_stage_instruction(self, role: str, current_state: AppState, stage_name: str) -> str:
        """按阶段与任务类型返回约束。只有 SOFTWARE 才以代码为主要产出；工程/科研/设计一律禁止往写代码方向走。"""
        tt = (self.ctx.task_type or "SOFTWARE").upper()
        only_software_code = (
            "【项目产出形态】本项目任务类型为「SOFTWARE」，执行阶段可产出可执行代码。\n"
        )
        no_code_emphasis = {
            "ENGINEERING": (
                "【项目产出形态】本项目是**工程类**（工程方案/施工计划/机械结构/系统架构等），"
                "产出应为**方案文档、图纸说明、计算书、风险评估报告**等，**不是软件代码**。\n"
                "全程禁止以编写或展示代码为主要产出；讨论与交付均以文档、图纸、方案为主。若有人要求写代码，请引导回工程方案/图纸/计算。"
            ),
            "RESEARCH": (
                "【项目产出形态】本项目是**科研类**（文献综述/实验设计/数据分析/调研报告等），"
                "产出应为**综述、实验方案、数据分析计划、调研报告**等，**不是软件代码**。\n"
                "全程禁止以编写代码为主要产出。若有人要求写代码，请引导回文献、方法、实验设计或报告。"
            ),
            "DESIGN": (
                "【项目产出形态】本项目是**设计类**（工业设计/外观/UX/3D 概念等），"
                "产出应为**设计说明、效果图描述、交互说明、模型概念**等，**不是软件代码**。\n"
                "全程禁止以编写代码为主要产出。若有人要求写代码，请引导回设计稿、说明或原型描述。"
            ),
        }
        task_instruction = only_software_code if tt == "SOFTWARE" else no_code_emphasis.get(tt, only_software_code)

        if current_state == AppState.DEBATE:
            stage = (
                "【本阶段纪律】当前为「方案博弈」阶段，仅讨论方案、架构与设计。\n"
                "禁止输出可执行代码或完整实现；可简要说明思路，不得输出可直接运行的代码块。\n"
            )
            if tt != "SOFTWARE":
                stage += "本项目并非软件开发，请勿将讨论引向写代码。\n"
            return task_instruction + stage
        if current_state == AppState.PRODUCTION:
            if role == "Coder":
                if tt == "SOFTWARE":
                    return (
                        task_instruction
                        + "【本阶段纪律】当前为「执行阶段」，请根据已定方案与 Mission Protocol 输出完整、可运行的代码或文档。\n"
                    )
                return (
                    task_instruction
                    + "【本阶段纪律】当前为「执行阶段」，你的产出应为**文档/方案/报告/图纸说明**等，**不要产出可执行代码**。请整理并输出工程方案/科研报告/设计说明等最终成果。\n"
                )
            return task_instruction + "【本阶段纪律】当前为「执行阶段」，请配合执行（补充说明或审查），不要输出大段代码。\n"
        if current_state == AppState.VERIFICATION:
            return task_instruction + "【本阶段纪律】当前为「验证阶段」，请基于验证结果做结论或修正建议。\n"
        if current_state == AppState.GROUNDING:
            return "【本阶段纪律】当前为「需求打磨」阶段（仅 CKO 与用户对话）；若你被意外调用，请简短说明身份后收尾。\n"
        return task_instruction + "【本阶段纪律】请根据当前阶段与项目产出形态行事。\n"

    def _infer_task_type(self, text: str) -> str:
        """从 CKO/用户文案推断任务类型，避免一律落成 SOFTWARE。"""
        if not text:
            return "SOFTWARE"
        t = text.lower()
        if any(k in t for k in ["工程", "施工", "机械", "结构设计", "制造", "工艺", "设备", "engineering"]):
            return "ENGINEERING"
        if any(k in t for k in ["科研", "研究", "文献", "实验设计", "调研", "综述", "research"]):
            return "RESEARCH"
        if any(k in t for k in ["工业设计", "外观", "造型", "ui", "ux", "3d", "设计图", "design"]):
            return "DESIGN"
        return "SOFTWARE"

    def _on_agent_finished(self, role: str, content: str):
        """Agent回复处理"""
        # 0. 处理工具调用结果
        if content.startswith("__TOOL_RESULT__:"):
            try:
                tool_data = json.loads(content[len("__TOOL_RESULT__:"):])
                content = tool_data.get("content", "").strip()
                if not content:
                    content = "【已执行内部工具调用】"
            except Exception as e:
                print(f"[UnifiedOrchestrator] 解析工具调用结果错误: {e}")

        # 1. 更新上下文
        # 自动识别意图（简化）
        intent = MessageIntent.STATEMENT
        content_lower = content.lower()
        if "?" in content or any(word in content_lower for word in ["如何", "怎么", "为什么"]):
            intent = MessageIntent.QUESTION
        elif any(word in content_lower for word in ["建议", "提议", "方案"]):
            intent = MessageIntent.PROPOSAL
        elif any(word in content_lower for word in ["同意", "赞同", "支持", "批准"]):
            intent = MessageIntent.AGREEMENT
        elif any(word in content_lower for word in ["反对", "不同意", "拒绝", "批评"]):
            intent = MessageIntent.CRITIQUE
        elif any(word in content_lower for word in ["决定", "决策", "裁决"]):
            intent = MessageIntent.DECISION

        self.ctx.add_message(role, content, intent)
        self.session_store.append_meeting_log(role, content)

        # 2. 更新UI
        self.agent_response.emit(role, content)

        # 3. 特殊处理（代码提取等）
        if role == "Coder":
            self._handle_code_extraction(content)

        # 4. 检查状态转换：PM/CKO 的“交付/完成/通过”等必须每次都检查，否则会漏判导致未进入 DELIVERY、下一轮继续发言（重复对话）
        if role in ("PM", "CKO"):
            self._check_state_transition(role, content)

        # 5. 若已进入交付/完成阶段，不再调度下一轮
        if self.state_ctrl.current_state in (AppState.DELIVERY, AppState.COMPLETED):
            return

        # 6. 继续事件循环
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    def _handle_code_extraction(self, content: str):
        """处理代码提取（从Coder回复中提取代码块）"""
        try:
            # 重用V1/V2中的代码提取逻辑
            import os
            import re
            import datetime

            # 更新会话
            self.session_store.update_session(final_code=content)

            # 提取代码块
            matches = list(re.finditer(r"```([a-zA-Z]*)\n(.*?)```", content, re.DOTALL))

            if matches:
                workspace_dir = self.session_store.get_workspace_dir()
                if not workspace_dir:
                    workspace_dir = os.path.join("data", "workspace", "default")
                    os.makedirs(workspace_dir, exist_ok=True)

                saved_files = []
                for i, match in enumerate(matches):
                    lang_tag = match.group(1).strip().lower()
                    pure_code = match.group(2)

                    # 提取文件名
                    filename = None
                    lines = pure_code.split('\n')
                    if lines:
                        first_line = lines[0].strip()
                        name_match = re.search(r'(?://|#|/\*|<!--)\s*filename:\s*([^\s\*>]+)', first_line, re.IGNORECASE)
                        if name_match:
                            filename = name_match.group(1).strip()
                            pure_code = '\n'.join(lines[1:]).strip()

                    if not filename:
                        # 默认文件扩展名映射
                        EXTENSION_MAP = {
                            "python": ".py", "py": ".py",
                            "javascript": ".js", "js": ".js",
                            "typescript": ".ts", "ts": ".ts",
                            "cpp": ".cpp", "c++": ".cpp",
                            "c": ".c", "java": ".java",
                            "html": ".html", "css": ".css",
                            "json": ".json", "yaml": ".yaml", "yml": ".yml",
                            "markdown": ".md", "md": ".md",
                            "bash": ".sh", "sh": ".sh",
                            "sql": ".sql"
                        }
                        ext = EXTENSION_MAP.get(lang_tag, ".py")
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"generated_{timestamp}_{i}{ext}"

                    # 安全写入
                    file_path = os.path.abspath(os.path.join(workspace_dir, filename))
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(pure_code)
                    saved_files.append(file_path)

                # 广播消息
                if saved_files:
                    joined_paths = "\n".join(saved_files)
                    self.agent_response.emit("System", f"💾 代码已保存:\n{joined_paths}")
        except Exception as e:
            print(f"[UnifiedOrchestrator] 代码提取错误: {e}")

    def _check_state_transition(self, role: str, content: str):
        """检查状态转换（基于决策）"""
        current_state = self.state_ctrl.current_state
        content_lower = content.lower()

        if role == "PM":
            # PM批准方案
            if ("批准" in content_lower or "同意" in content_lower or "通过" in content_lower or
                "approve" in content_lower or "✅" in content):
                if current_state == AppState.DEBATE:
                    self.state_ctrl.transition_to(AppState.PRODUCTION)
                    self.agent_response.emit("System", "PM 批准方案，进入执行阶段。")

            # PM交付
            elif ("交付" in content_lower or "发布" in content_lower or "完成" in content_lower or
                  "deliver" in content_lower or "🚀" in content):
                if current_state == AppState.PRODUCTION or current_state == AppState.VERIFICATION:
                    self._enter_delivery_and_complete("PM确认交付，进入交付阶段。")

        elif role == "CKO":
            # CKO审计通过
            if ("通过" in content_lower or "批准" in content_lower or "合格" in content_lower or
                "pass" in content_lower or "✅" in content):
                if current_state == AppState.VERIFICATION:
                    self._enter_delivery_and_complete("CKO审计通过，准备交付。")

    def _run_audit(self, stage: str, context: str, callback):
        """运行 CKO 审计"""
        self.agent_response.emit("CKO", f"👁️ [Vision Keeper] 正在审计 {stage} 产出...")
        # 注意: self.ctx.mission_protocol 必须存在
        worker = AuditWorker(self.agents_map["CKO"], stage, context,
                           self.ctx.mission_protocol, self)
        worker.audit_finished.connect(callback)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_agent_error(self, role: str, error_msg: str):
        """统一处理 Agent 错误"""
        self.error_occurred.emit(f"[{role}] {error_msg}")

    def _start_worker(self, worker):
        """启动 Worker 线程（简化实现）"""
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_debate_audit_finished(self, result: str):
        """方案博弈阶段审计完成处理"""
        if result.startswith("FAIL"):
            self.agent_response.emit("CKO", f"❌ [Vision Alert] 审计未通过: {result}")
            # 审计未通过，反馈给PM
            objection_msg = (
                f"CKO (Vision Keeper) 拒绝了当前的 Approved 方案。\n"
                f"审计意见: {result}\n\n"
                f"你需要重新召集大家解决这个问题，或者给出强有力的理由并再次尝试提交。"
            )
            # 这里可以调用PM，但为了简化，我们只是记录
            self.ctx.add_message("CKO", objection_msg, MessageIntent.CRITIQUE)
            self.agent_response.emit("CKO", objection_msg)
        else:
            self.agent_response.emit("CKO", "✅ [Vision Keeper] 审计通过，准许开发。")
            # 进入生产阶段
            self.state_ctrl.transition_to(AppState.PRODUCTION)
            self.agent_response.emit("System", "CKO审计通过，进入生产阶段。")

    def _on_verification_audit_finished(self, result: str):
        """验证阶段审计完成处理"""
        if result.startswith("FAIL"):
            self.agent_response.emit("CKO", f"❌ [Vision Alert] 审计未通过: {result}")
            # 审计未通过，需要PM决策
            outcome_msg = (
                f"⚠️ CKO (Vision Keeper) 发现最终交付物严重偏离 Mission Protocol。\n"
                f"审计意见: {result}\n\n"
                f"这是最后一道防线。作为 PM，请仔细评估是否强制返工还是允许带病发布。"
            )
            self.ctx.add_message("CKO", outcome_msg, MessageIntent.CRITIQUE)
            self.agent_response.emit("CKO", outcome_msg)
        else:
            self.agent_response.emit("CKO", "✅ [Vision Keeper] 审计通过，准备交付 PM 验收。")
            self._enter_delivery_and_complete("CKO审计通过，进入交付阶段。")

    def _enter_delivery_and_complete(self, system_message: str):
        """进入交付阶段并在一小段延迟后标记为 COMPLETED，避免后续再触发下一轮发言。"""
        if not self.state_ctrl.transition_to(AppState.DELIVERY):
            return
        self.agent_response.emit("System", system_message)
        self.agent_response.emit("System", "🎉 项目交付完成！")
        QTimer.singleShot(1500, self._finish_workflow)

    def _finish_workflow(self):
        """将状态置为 COMPLETED 并发出 workflow_completed 信号。"""
        self.state_ctrl.transition_to(AppState.COMPLETED)
        self.workflow_completed.emit()

# ==============================================================================
# 6. AgentWorker（重用V2实现）
# ==============================================================================

class AgentWorker(QThread):
    """Agent工作线程"""
    finished_with_result = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str, str)

    def __init__(self, agent, message: str, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.message = message

    def run(self):
        try:
            response = self.agent.send_message(self.message)
            self.finished_with_result.emit(self.agent.role, response)
        except Exception as e:
            self.error_occurred.emit(self.agent.role, str(e))

# ==============================================================================
# 7. 审计工作线程（CKO Vision Keeper）
# ==============================================================================

class AuditWorker(QThread):
    """审计工作线程 (CKO Vision Keeper)"""

    audit_finished = pyqtSignal(str)   # 审计结果 (PASS / FAIL: xxx)
    error_occurred = pyqtSignal(str, str)   # (角色, 错误消息)

    def __init__(self, cko_agent, stage, context, mission_protocol, parent=None):
        super().__init__(parent)
        self.cko = cko_agent
        self.stage = stage
        self.context = context
        self.protocol = mission_protocol
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled or self.isInterruptionRequested():
                print("[AuditWorker] 审计取消")
                return

            result = self.cko.audit_node(self.stage, self.context, self.protocol)

            if self._is_cancelled or self.isInterruptionRequested():
                print("[AuditWorker] 审计完成后取消，丢弃结果")
                return

            self.audit_finished.emit(result)

        except Exception as e:
            if self._is_cancelled or self.isInterruptionRequested():
                print("[AuditWorker] 异常期间取消")
                return
            self.error_occurred.emit("CKO", f"CKO 审计异常: {str(e)}")

    def cancel(self):
        """取消审计"""
        self._is_cancelled = True
        self.requestInterruption()  # 请求线程中断
        self.quit()  # 请求线程退出

# ==============================================================================
# 8. 主入口点适配（供main.py使用）
# ==============================================================================

if __name__ == "__main__":
    print("UnifiedOrchestrator 模块测试...")
    # 简单测试代码
    orchestrator = UnifiedOrchestrator()
    print(f"创建成功: {orchestrator}")