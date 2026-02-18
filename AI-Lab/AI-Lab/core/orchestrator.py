"""
orchestrator.py - 编排引擎 (PM 主导模式)
==========================================
在后台线程中调度 Agent 之间的交互，管理状态流转。

核心流程:
  用户 → CKO(需求打磨) → PM(解读任务书/分配/审批)
  → Arch(架构设计) → Designer(实现规划)
  → PM(终审) → Coder(编码) → Tester(验证)

组件:
  - AgentWorker(QThread): 封装单次 Agent API 调用，避免阻塞 UI
  - Orchestrator(QObject): 核心编排器，驱动完整工作流

安全性审计:
  ✅ 所有 API 调用在 QThread 中执行，不阻塞 UI
  ✅ 异常处理覆盖 API 调用和线程生命周期
  ✅ 支持随时中止所有活跃的 Worker 线程
"""

import traceback
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from agents.cko_agent import CKOAgent
from agents.pm_agent import PMAgent
from agents.arch_agent import ArchAgent
from agents.designer_agent import DesignerAgent
from agents.coder_agent import CoderAgent
from agents.tester_agent import TesterAgent
from core.state_controller import StateController
from core.chat_history import ChatHistoryManager
from core.session_store import SessionStore
from config import AppState, MAX_DEBATE_ROUNDS


class AgentWorker(QThread):
    """Agent 工作线程

    将单次 Agent API 调用封装在独立线程中执行，
    避免阻塞 UI 主线程，通过信号返回结果。

    信号:
        finished_with_result: 调用完成信号 (角色, 回复内容)
        error_occurred: 错误信号 (角色, 错误消息)
    """

    finished_with_result = pyqtSignal(str, str)  # (角色, 回复内容)
    error_occurred = pyqtSignal(str, str)        # (角色, 错误消息)

    def __init__(self, agent, message: str, parent=None):
        """初始化工作线程

        Args:
            agent: BaseAgent 子类实例
            message: 发送给 Agent 的消息内容
            parent: Qt 父对象
        """
        super().__init__(parent)
        self._agent = agent
        self._message = message
        self._is_cancelled = False

    def run(self):
        """执行 Agent API 调用（在后台线程中运行）"""
        try:
            if self._is_cancelled:
                return
            response = self._agent.send_message(self._message)
            if not self._is_cancelled:
                self.finished_with_result.emit(self._agent.role, response)
        except Exception as e:
            error_msg = f"Agent [{self._agent.role}] 执行失败: {str(e)}\n{traceback.format_exc()}"
            self.error_occurred.emit(self._agent.role, error_msg)

    def cancel(self):
        """取消当前工作"""
        self._is_cancelled = True
        self._agent.stop()


class AuditWorker(QThread):
    """审计工作线程 (CKO Vision Keeper)"""
    
    audit_finished = pyqtSignal(str)   # 审计结果 (PASS / FAIL: xxx)
    error_occurred = pyqtSignal(str)   # 错误消息

    def __init__(self, cko_agent, stage, context, mission_protocol, parent=None):
        super().__init__(parent)
        self.cko = cko_agent
        self.stage = stage
        self.context = context
        self.protocol = mission_protocol

    def run(self):
        try:
            result = self.cko.audit_node(self.stage, self.context, self.protocol)
            self.audit_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(f"CKO 审计异常: {str(e)}")

    def cancel(self):
        """取消审计"""
        # 审计通常是同步调用，无法立即中断，但可标记停止
        pass


class Orchestrator(QObject):
    """核心编排引擎 (PM 主导模式)

    工作流:
    IDLE → GROUNDING(CKO) → DEBATE(PM解读→Arch→Designer→CKO审计→PM审批)
    → PRODUCTION(Coder) → VERIFICATION(Tester→CKO审计) → COMPLETED

    PM 在 DEBATE 阶段扮演双重角色:
      1. 任务解读者: 接收 CKO 的任务书，解读并下达执行方向
      2. 终审裁判: 审查 Arch + Designer 的方案，决定批准或打回

    信号:
        agent_response: Agent 回复信号 (角色, 内容)
        state_changed: 状态变更信号 (旧状态, 新状态)
        error_occurred: 错误信号 (错误消息)
        workflow_completed: 整个工作流完成信号
        debate_round_info: 博弈轮次信息 (当前轮次, 最大轮次)
    """

    agent_response = pyqtSignal(str, str)       # (角色, 回复内容)
    state_changed = pyqtSignal(str, str)        # (旧状态, 新状态)
    error_occurred = pyqtSignal(str)            # 错误消息
    workflow_completed = pyqtSignal()           # 工作流完成
    debate_round_info = pyqtSignal(int, int)    # (当前轮次, 最大轮次)
    agent_typing = pyqtSignal(str, bool)        # (角色, 是否正在输入)

    # ---------- 常量 ----------
    # MAX_DEBATE_ROUNDS 已移至 config.py

    def __init__(self, parent=None):
        """初始化编排引擎，创建所有 Agent 和核心组件"""
        super().__init__(parent)
        
        # 加载配置
        self.MAX_DEBATE_ROUNDS = MAX_DEBATE_ROUNDS

        # ------ 核心组件 ------
        self.state_ctrl = StateController(self)
        self.chat_history = ChatHistoryManager()
        self.session_store = SessionStore()

        # ------ 创建 Agent 实例 ------
        self.cko = CKOAgent(self)
        self.pm = PMAgent(self)
        self.arch = ArchAgent(self)
        self.designer = DesignerAgent(self)
        self.coder = CoderAgent(self)
        self.tester = TesterAgent(self)
        
        # ------ 连接 Agent 的输入状态信号 ------
        for agent in [self.cko, self.pm, self.arch, self.designer, self.coder, self.tester]:
            agent.typing_started.connect(lambda role, a=agent: self.agent_typing.emit(role, True))
            agent.typing_finished.connect(lambda role, a=agent: self.agent_typing.emit(role, False))

        # ------ 活跃的 Worker 线程列表 ------
        self._active_workers = []
        
        # ------ 内部状态 ------
        self._debate_round = 0
        self._mission_protocol = ""
        self._pm_direction = ""
        
        # 循环检测
        self._last_speaker_role = None
        self._consecutive_speaker_count = 0
        self._active_workers: list[AgentWorker] = []

        # ------ 博弈状态 ------
        self._debate_round = 0
        self._mission_protocol = ""  # CKO 生成的任务书
        self._pm_direction = ""      # PM 解读后的执行方向

        # ------ 转发状态变更信号 ------
        self.state_ctrl.state_changed.connect(self.state_changed.emit)
        self.state_ctrl.error_occurred.connect(self.error_occurred.emit)

    # ======================================================================
    #  第一阶段: GROUNDING — 用户与 CKO 对话
    # ======================================================================

    def send_to_cko(self, message: str):
        """用户发送消息给 CKO（需求打磨阶段）

        Args:
            message: 用户输入的消息

        自动将状态从 IDLE 转换到 GROUNDING（如果当前是 IDLE）。
        """
        # 如果当前是 IDLE，转换到 GROUNDING
        if self.state_ctrl.current_state == AppState.IDLE:
            if not self.state_ctrl.transition_to(AppState.GROUNDING):
                return
            # 创建新会话
            self.session_store.create_session(user_intent=message)
            self.session_store.append_timeline_event(
                AppState.GROUNDING, "开始需求打磨"
            )

        # 记录用户消息
        self.session_store.append_cko_log("user", message)

        # 启动 CKO Worker
        worker = AgentWorker(self.cko, message, self)
        worker.finished_with_result.connect(self._on_cko_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_cko_response(self, role: str, content: str):
        """CKO 回复处理

        Args:
            role: 角色标识 (CKO)
            content: CKO 回复内容
        """
        # 记录 CKO 回复
        self.session_store.append_cko_log("CKO", content)
        self.agent_response.emit(role, content)

    # ======================================================================
    #  用户确认立项 → CKO 任务书交给 PM
    # ======================================================================

    def confirm_project(self):
        """用户确认立项

        将 CKO 最后的回复作为 Mission Protocol（任务书），
        先交给 PM 解读和制定执行计划，再由 PM 指挥后续角色。
        """
        # 获取 CKO 的最后回复作为 Mission Protocol
        cko_messages = self.cko.get_messages()
        if cko_messages:
            for msg in reversed(cko_messages):
                if msg["role"] == "assistant":
                    self._mission_protocol = msg["content"]
                    break

        if not self._mission_protocol:
            self.error_occurred.emit("⚠️ 无法获取 Mission Protocol，请先与 CKO 完成需求沟通。")
            return

        # 更新会话
        self.session_store.update_session(mission_protocol=self._mission_protocol)

        # 状态转换: GROUNDING → DEBATE
        if not self.state_ctrl.transition_to(AppState.DEBATE):
            return

        self.session_store.append_timeline_event(
            AppState.DEBATE, "PM 接收任务书，方案博弈开始"
        )

        # ★ 核心改动: 先将任务书交给 PM 解读
        self._send_protocol_to_pm()

    # ======================================================================
    #  第二阶段: DEBATE — PM 主导的博弈循环
    #  流程: PM 解读 → Arch 架构 → Designer 细化 → PM 终审
    # ======================================================================

    def _send_protocol_to_pm(self):
        """将 CKO 的任务书发送给 PM 进行解读

        PM 作为总指挥，先解读任务书，制定执行方向和约束条件，
        然后将指令下达给 Arch 开始架构设计。
        """
        pm_msg = (
            f"CKO（首席知识官）已完成需求打磨，生成了以下 Mission Protocol（任务书）。\n"
            f"作为项目经理，请你：\n"
            f"1. 解读这份任务书的核心需求和约束\n"
            f"2. 制定执行方向和优先级\n"
            f"3. 给出你对 Architect（架构师）的指令，明确告诉他应该重点关注什么\n\n"
            f"## Mission Protocol:\n{self._mission_protocol}\n\n"
            f"请输出你的解读和对架构师的指令。"
        )

        worker = AgentWorker(self.pm, pm_msg, self)
        worker.finished_with_result.connect(self._on_pm_direction)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_pm_direction(self, role: str, content: str):
        """PM 解读完毕 → 进入动态圆桌博弈
        
        Args:
            role: 角色标识 (PM)
            content: PM 制定的执行方向和对架构师的指令
        """
        self.agent_response.emit(role, content)
        self.session_store.append_meeting_log(role, content)
        self._pm_direction = content

        # PM 解读完成 → 开始动态博弈循环
        self._debate_round = 0
        self._run_moderator_loop()

    def _run_moderator_loop(self):
        """进入/继续 PM 主持的博弈循环"""
        print(f"DEBUG: _run_moderator_loop entered. State={self.state_ctrl.current_state}, Round={self._debate_round}")
        # 1. 状态检查：如果已停止 (IDLE)，则不再执行
        if self.state_ctrl.current_state == AppState.IDLE:
            return

        # 2. 状态转换/检查
        if self.state_ctrl.current_state != AppState.DEBATE:
            if not self.state_ctrl.transition_to(AppState.DEBATE):
                return

        self._debate_round += 1
        
        # 安全熔断：超过最大轮次强制结束
        if self._debate_round > self.MAX_DEBATE_ROUNDS * 3: # 动态交互次数较多，放宽上限
            self.agent_response.emit("系统", "⚠️ 达到最大交互次数，强制进入开发阶段。")
            self._start_production()
            return

        self.debate_round_info.emit(self._debate_round, self.MAX_DEBATE_ROUNDS * 3)

        # 组装上下文给 PM
        history = self._get_recent_debate_history()
        moderator_msg = (
            f"我是系统。当前博弈进行到第 {self._debate_round} 次交互。\n"
            f"请回顾最新的对话进展：\n\n{history}\n\n"
            f"作为主持人，请决定下一步行动。\n"
            f"如果需要某人发言，输出 `NEXT_SPEAKER: [角色]`。\n"
            f"如果方案已完善，输出 `DECISION: APPROVED`。\n"
            f"如果方案严重跑偏，输出 `DECISION: REJECTED`。"
        )

        worker = AgentWorker(self.pm, moderator_msg, self)
        worker.finished_with_result.connect(self._on_moderator_decision)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_moderator_decision(self, role: str, content: str):
        """处理 PM 主持人的决策"""
        # 状态检查
        if self.state_ctrl.current_state == AppState.IDLE:
             return

        self.agent_response.emit(role, content)
        self.session_store.append_meeting_log(role, content)

        # 解析指令
        import re
        next_speaker = None
        decision = None

        if "NEXT_SPEAKER:" in content:
            match = re.search(r"NEXT_SPEAKER:\s*(\w+)", content)
            if match:
                next_speaker = match.group(1)
        
        if "DECISION:" in content:
            match = re.search(r"DECISION:\s*(\w+)", content)
            if match:
                decision = match.group(1)

        # 执行决策
        if decision == "APPROVED":
            self.agent_response.emit("系统", "✅ PM 宣布方案通过。")
            self.agent_response.emit("系统", "🔍 [Vision Keeper] CKO 正在进行最终方案审计...")
            # 进入 CKO 审计环节
            self.session_store.append_timeline_event(AppState.DEBATE, "CKO 方案审计")
            
            # 获取完整上下文进行审计
            full_context = self.session_store.get_all_meeting_logs()
            self._run_audit("Debate Phase", full_context, self._on_debate_audit_finished)

        elif decision == "REJECTED":
            self.agent_response.emit("系统", "❌ PM 否决了当前方案，需要重新审视任务书。")
            # 这里简单处理：重置轮次继续讨论，或者提示用户干预
            self.agent_response.emit("系统", "请用户介入干预或重启会话。")
        elif next_speaker:
            # --- 循环 / 死锁检测 ---
            if next_speaker == self._last_speaker_role:
                self._consecutive_speaker_count += 1
            else:
                self._last_speaker_role = next_speaker
                self._consecutive_speaker_count = 1
            
            if self._consecutive_speaker_count >= 5:
                # 强制打断循环
                self.agent_response.emit("系统", f"⚠️ 检测到 PM 连续 {self._consecutive_speaker_count} 次调用 {next_speaker}，强制打断循环。")
                self.agent_response.emit("系统", "将邀请 Designer 尝试打破僵局。")
                next_speaker = "Designer"
                self._last_speaker_role = "Designer"
                self._consecutive_speaker_count = 1

            if "Arch" in next_speaker:
                self._call_agent(self.arch)
            elif "Designer" in next_speaker:
                self._call_agent(self.designer)
            elif "Coder" in next_speaker:
                self._call_agent(self.coder)  # Allow Coder to speak
            elif "CKO" in next_speaker:
                self._call_agent(self.cko)
            else:
                 # 无法识别的角色，默认叫 Arch
                 self.agent_response.emit("系统", f"⚠️ 未知角色 {next_speaker}，默认邀请 Architect 发言。")
                 self._call_agent(self.arch)
        else:
             # 如果 PM 没给指令（可能是纯点评），默认让 Designer 回应（通常是 Arch 发言后 PM 点评，然后 Designer 接话）
             # 或者再次询问 PM
             self.agent_response.emit("系统", "⚠️ PM 未给出明确指令，继续请求裁决...")
             self._run_moderator_loop()

    def _call_agent(self, agent):
        """调用指定 Agent 发言"""
        print(f"DEBUG: Orchestrator._call_agent called for {agent.role}")
        if self.state_ctrl.current_state == AppState.IDLE:
             print("DEBUG: Orchestrator state is IDLE, aborting call")
             return

        # 构建 prompt：包含最近的上下文
        history = self._get_recent_debate_history()
        msg = (
            f"PM (主持人) 邀请你发言。请根据当前上下文回应。\n"
            f"## 最近对话记录:\n{history}\n\n"
            f"请输出你的观点或方案。"
        )
        
        print(f"DEBUG: Starting AgentWorker for {agent.role}")
        worker = AgentWorker(agent, msg, self)
        # 统一使用通用回调，因为处理逻辑一样：记录 -> 回到 Moderator
        worker.finished_with_result.connect(self._on_debate_agent_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_debate_agent_response(self, role: str, content: str):
        """Arch/Designer 发言完毕 -> 记录并交回主持棒"""
        print(f"DEBUG: Orchestrator received response from {role}")
        if self.state_ctrl.current_state == AppState.IDLE:
             print("DEBUG: State is IDLE, ignoring response")
             return

        self.agent_response.emit(role, content)
        self.session_store.append_meeting_log(role, content)
        
        # 话筒交回给 PM
        print("DEBUG: Passing control back to Moderator loop")
        self._run_moderator_loop()

    def _get_recent_debate_history(self, limit=5) -> str:
        """获取最近几条博弈记录用于构建 Prompt"""
        # 这里简化处理，实际可以直接从 session_store 获取
        # 假设 session_store 有 get_history 方法，或者我们只读内存缓存
        # 临时方案：读取最后 N 条 assistant 消息
        # 更好的方案是 session_store 提供结构化接口
        # 这里暂时构造一个简单的字符串
        return self.session_store.get_debate_context(limit=limit)

    def _on_debate_audit_finished(self, result: str):
        """CKO 方案审计完成 -> 决定进入开发还是被打回"""
        if result.startswith("FAIL"):
            self.agent_response.emit("CKO", f"❌ [Vision Alert] 审计未通过: {result}")
            
            # 审计未通过，将异议反馈给 PM
            objection_msg = (
                f"CKO (Vision Keeper) 拒绝了当前的 Approved 方案。\n"
                f"审计意见: {result}\n\n"
                f"你需要重新召集大家解决这个问题，或者给出强有力的理由并再次尝试提交。"
            )
            
            worker = AgentWorker(self.pm, objection_msg, self)
            worker.finished_with_result.connect(self._on_moderator_decision) 
            worker.error_occurred.connect(self._on_agent_error)
            self._start_worker(worker)
            
        else:
            self.agent_response.emit("CKO", "✅ [Vision Keeper] 审计通过，准许开发。")
            self._start_production()

    # ======================================================================
    #  第三阶段: PRODUCTION — Coder 编写代码
    # ======================================================================

    def _start_production(self):
        """进入代码编写阶段

        将通过审查的架构方案和实现方案发送给 Coder。
        """
        # 状态转换: DEBATE → PRODUCTION
        if not self.state_ctrl.transition_to(AppState.PRODUCTION):
            return

        self.session_store.append_timeline_event(
            AppState.PRODUCTION, "代码编写开始"
        )

        # 获取 Arch 和 Designer 的最终方案
        arch_content = self._get_last_assistant_msg(self.arch)
        designer_content = self._get_last_assistant_msg(self.designer)
        
        # 获取完整会议记录，让 Coder "旁听" 整个博弈过程
        full_debate_history = self.session_store.get_all_meeting_logs()

        coder_msg = (
            f"PM 已批准以下方案，请作为 Executor（执行官）制作最终执行成果。\n"
            f"你已全程'旁听'了方案博弈过程，请结合上下文进行开发。\n\n"
            f"## Mission Protocol (原始任务书):\n{self._mission_protocol}\n\n"
            f"## 完整会议记录 (Context):\n{full_debate_history}\n\n"
            f"## 架构方案（Architect）:\n{arch_content}\n\n"
            f"## 详细设计（Designer）:\n{designer_content}\n\n"
            f"## 架构方案（Architect）:\n{arch_content}\n\n"
            f"## 详细设计（Designer）:\n{designer_content}\n\n"
            f"请根据任务类型（软件/非软件）智能判断输出形式：\n"
            f"1. 软件任务：输出完整、可运行的 Python 代码。\n"
            f"2. 非软件任务：输出详细的《项目执行计划书》和步骤清单。"
        )

        worker = AgentWorker(self.coder, coder_msg, self)
        worker.finished_with_result.connect(self._on_coder_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_coder_response(self, role: str, content: str):
        """Coder 完成编码 → 进入 VERIFICATION 阶段
        
        Refactored:
        1. 完整回复 -> War Room (SSOT)
        2. 代码块 -> Execution Panel (Terminal)
        """
        try:
            # 1. 路由消息到 War Room
            self.main_window.warroom_panel.append_message(role, content, self.state_ctrl.current_state)
            self.session_store.append_meeting_log(role, content)

            # 2. 提取并部署代码到 Execution Lab
            import re
            code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
                self.main_window.execution_panel.set_code(code)
                self.main_window.execution_panel.append_log(f"[{role}] Code extracted and deployed to runtime environment.")
            else:
                self.main_window.execution_panel.append_log(f"[{role}] Message received (No code block detected).")

            self.session_store.update_session(final_code=content)

            # 启动测试验证
            self._start_verification(content)
        except Exception as e:
            self._on_agent_error(role, f"处理响应时发生异常: {e}\n{traceback.format_exc()}")

    # ======================================================================
    #  第四阶段: VERIFICATION — Tester 测试验证
    # ======================================================================

    def _start_verification(self, code: str):
        """进入测试验证阶段

        Args:
            code: Coder 编写的代码内容
        """
        # 状态转换: PRODUCTION → VERIFICATION
        if not self.state_ctrl.transition_to(AppState.VERIFICATION):
            return

        self.session_store.append_timeline_event(
            AppState.VERIFICATION, "代码测试验证开始"
        )

        tester_msg = (
            f"Executor 已提交成果，请作为 Validator 进行验证评估：\n\n"
            f"```\n{code}\n```\n\n"
            f"请评估其逻辑合理性、完整性和可执行性，并输出《验证评估报告》。"
        )

        worker = AgentWorker(self.tester, tester_msg, self)
        worker.finished_with_result.connect(self._on_tester_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_tester_response(self, role: str, content: str):
        """Validator 评估完毕 → 提交 CKO 审计
        
        Refactored:
        1. 完整报告 -> War Room (SSOT)
        2. 验证结果摘要 -> Execution Panel (Log)
        """
        try:
            # 1. 路由消息到 War Room
            self.main_window.warroom_panel.append_message(role, content, self.state_ctrl.current_state)
            self.session_store.append_meeting_log(role, content)
            
            # 2. 记录到 Execution Log
            if "PASS" in content:
                self.main_window.execution_panel.append_log(f"[{role}] VERIFICATION PASSED. Submitting for Audit.")
            else:
                 self.main_window.execution_panel.append_log(f"[{role}] ISSUES DETECTED. See War Room for details.")

            self.session_store.append_test_report({
                "role": role,
                "result": content,
            })

            # 触发 CKO 关键节点审计
            self._run_audit("Verification Phase", content, self._on_verification_audit_finished)

        except Exception as e:
            self._on_agent_error(role, f"处理测试报告时发生异常: {e}\n{traceback.format_exc()}")

    def _on_verification_audit_finished(self, result: str):
        """Verification 审计完成 → 决定流向"""
        if result.startswith("FAIL"):
            self.agent_response.emit("CKO", f"❌ [Vision Alert] 审计未通过: {result}")
            
            outcome_msg = (
                f"⚠️ CKO (Vision Keeper) 发现最终交付物严重偏离 Mission Protocol。\n"
                f"审计意见: {result}\n\n"
                f"这是最后一道防线。作为 PM，请仔细评估是否强制返工还是允许带病发布（不建议）。"
            )
            worker = AgentWorker(self.pm, outcome_msg, self)
            worker.finished_with_result.connect(self._on_pm_final_decision) 
            worker.error_occurred.connect(self._on_agent_error)
            self._start_worker(worker)
        else:
            self.agent_response.emit("CKO", "✅ [Vision Keeper] 审计通过，准备交付 PM 验收。")
            
            # 获取 Validator 报告
            validator_report = self._get_last_assistant_msg(self.tester)
            
            self.agent_response.emit("系统", "🔍 Validator 已提交评估报告，正在转交 PM 进行终审...")
            self._start_pm_final_audit(validator_report)

    def _start_pm_final_audit(self, validator_report: str):
        """PM 终审阶段

        PM 结合 Executor 的产出和 Validator 的报告，决定项目命运。

        Args:
            validator_report: Validator 提交的评估报告
        """
        try:
            # 获取 Executor (Coder) 的产出
            session_data = self.session_store.get_current_session()
            executor_output = session_data.get("final_code", "") if session_data else "（未找到执行结果）"

            pm_msg = (
                f"Executor 已完成执行，Validator 已提交评估报告。\n"
                f"请作为项目经理 (PM) 进行最终验收裁决。\n\n"
                f"## Validator 评估报告:\n{validator_report}\n\n"
                f"## 决策指令:\n"
                f"1. 如果验收合格：请回复 '✅ PROJECT COMPLETED'。\n"
                f"2. 如果需要返工：请回复 '❌ REWORK REQUIRED'，并列出具体的修改指令给 Executor。\n\n"
                f"请给出你的裁决和理由。"
            )

            worker = AgentWorker(self.pm, pm_msg, self)
            worker.finished_with_result.connect(self._on_pm_final_decision)
            worker.error_occurred.connect(self._on_agent_error)
            self._start_worker(worker)
        except Exception as e:
            self._on_agent_error("PM", f"启动终审时发生异常: {e}\n{traceback.format_exc()}")

    def _on_pm_final_decision(self, role: str, content: str):
        """PM 终审裁决处理

        Args:
            role: 角色标识 (PM)
            content: PM 的裁决内容
        """
        self.agent_response.emit(role, content)
        self.session_store.append_meeting_log(role, content)

        if "PROJECT COMPLETED" in content or "✅" in content:
            # 验收通过 → COMPLETED
            self.agent_response.emit("系统", "🎉 PM 验收通过，项目完成！")
            self._complete_workflow()
        else:
            # 需要返工 → 回到 PRODUCTION 让 Executor 修复
            self.agent_response.emit("系统", "⚠️ PM 驳回验收，要求 Executor 返工...")
            self._handle_rework(content)

    def _handle_rework(self, pm_instruction: str):
        """处理返工：将 PM 指令反馈给 Executor

        Args:
            pm_instruction: PM 的返工指令
        """
        # 回到 PRODUCTION 状态
        if not self.state_ctrl.transition_to(AppState.PRODUCTION):
            self._complete_workflow()
            return

        executor_msg = (
            f"PM 驳回了你的交付成果，要求返工。\n"
            f"请根据以下 PM 指令和 Validator 报告进行修改：\n\n"
            f"## PM 返工指令:\n{pm_instruction}\n\n"
            f"请输出修改后的完整成果（代码或计划书）。"
        )

        worker = AgentWorker(self.coder, executor_msg, self)
        worker.finished_with_result.connect(self._on_coder_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    # ======================================================================
    #  完成工作流
    # ======================================================================

    def _complete_workflow(self):
        """完成整个工作流"""
        self.state_ctrl.transition_to(AppState.COMPLETED)
        self.session_store.append_timeline_event(
            AppState.COMPLETED, "任务完成！"
        )
        self.session_store.update_session(state=AppState.COMPLETED)
        self.workflow_completed.emit()

    # ======================================================================
    #  工具方法
    # ======================================================================

    def _start_worker(self, worker: AgentWorker):
        """启动 Worker 线程并加入活跃列表

        Args:
            worker: 待启动的 AgentWorker
        """
        # 清理已完成的 Worker
        self._active_workers = [
            w for w in self._active_workers if w.isRunning()
        ]
        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _cleanup_worker(self, worker: AgentWorker):
        """清理已完成的 Worker

        Args:
            worker: 已完成的 AgentWorker
        """
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def _on_agent_error(self, role: str, error_msg: str):
        """统一处理 Agent 错误

        Args:
            role: 出错的 Agent 角色
            error_msg: 错误消息
        """
        self.error_occurred.emit(f"[{role}] {error_msg}")

    def inject_user_message(self, message: str):
        """注入用户干预消息（Commander Instruction）
        
        [Refined Interaction Logic]:
        1. Always display user message in chat stream (via signal).
        2. Auto-identify target role if not explicitly @-mentioned.
        """
        print(f"[DEBUG] Orchestrator received user message: {message}") # DEBUG
        
        # 1. 在 UI 上显示（角色: Commander）
        # This triggers WarRoomPanel.append_message => shows user bubble
        self.agent_response.emit("Commander", message)
        self.session_store.append_meeting_log("Commander", message)

        # 2. 智能路由解析 (@Role or Keyword)
        target_role = self._resolve_target_role(message)
        
        if target_role:
            # --- 定向交互模式 ---
            # self.agent_response.emit("系统", f"⚡ 正在呼叫 {target_role}...") # Optional: reduce noise
            self._trigger_direct_response(target_role, message)
        else:
            # --- 全局广播 / 默认路由 ---
            # 如果没有明确目标，默认所有 Agent 都会收到上下文更新，但不强制所有人回复
            # 为了避免"所有人同时说话"的混乱，我们可以引入一个"默认接待员"（通常是 PM 或 当前发言者）
            
            # 策略：作为 Context 注入所有人，但要求当前阶段的主导者回应
            context_msg = f"👊 [Commander Intervention] 指挥官指令：\n{message}\n\n请根据此指令调整行动。"
            
            agents = [self.cko, self.pm, self.arch, self.designer, self.coder, self.tester]
            for agent in agents:
                agent.add_context(context_msg, role="system")

            self.agent_response.emit("系统", "⚡ 指令已同步全员。")

    def _resolve_target_role(self, message: str) -> Optional[str]:
        """智能解析目标角色 (@Role 优先，其次 Keyword 分析)"""
        import re
        
        # 1. Explicit @Role
        roles_map = {
            "PM": ["pm", "project manager", "manager", "管理"],
            "Arch": ["arch", "architect", "架构"],
            "Designer": ["designer", "ui", "ux", "设计"],
            "Coder": ["coder", "executor", "dev", "代码", "bug", "implement", "fix", "写", "改"],
            "Tester": ["tester", "qa", "test", "verification", "测试", "验证"],
            "CKO": ["cko", "knowledge", "research", "vision", "mission", "需求", "文档"]
        }
        
        # Check for @Tag first
        match = re.search(r"@(\w+|[\u4e00-\u9fa5]+)", message)
        if match:
            tag = match.group(1).lower()
            for role, keywords in roles_map.items():
                if tag == role.lower() or tag in keywords:
                    return role
                    
        # 2. Contextual Keyword Matching (if no @Tag)
        # Simple heuristic: specific keywords trigger specific roles
        msg_lower = message.lower()
        
        # Priority Keywords
        if any(w in msg_lower for w in ["bug", "error", "exception", "crash", "fix", "code", "python"]):
            return "Coder"
        if any(w in msg_lower for w in ["test", "verify", "pass", "fail", "qa"]):
            return "Tester"
        if any(w in msg_lower for w in ["design", "ui", "color", "layout", "style", "css"]):
            return "Designer"
        if any(w in msg_lower for w in ["architecture", "database", "structure", "system"]):
            return "Arch"
        if any(w in msg_lower for w in ["requirement", "plan", "scope", "timeline"]):
            return "PM"
            
        return None

    def _trigger_direct_response(self, role: str, message: str):
        """触发特定 Agent 的直接回复 (不影响状态机)"""
        agent_map = {
            "PM": self.pm,
            "Arch": self.arch,
            "Designer": self.designer,
            "Coder": self.coder,
            "Tester": self.tester,
            "CKO": self.cko
        }
        agent = agent_map.get(role)
        if not agent:
            self.error_occurred.emit(f"无法找到角色: {role}")
            return

        # 构造 Prompt，告诉 Agent 这是用户的直接提问
        direct_msg = (
            f"Commander (用户) 直接向你提问：\n"
            f"\"{message}\"\n\n"
            f"请忽略当前的会议流程，直接回答这个问题。回答尽量简练。"
        )

        # 使用 Worker 执行，回调到 _on_direct_response
        worker = AgentWorker(agent, direct_msg, self)
        worker.finished_with_result.connect(self._on_direct_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_direct_response(self, role: str, content: str):
        """处理直接回复"""
        self.agent_response.emit(role, content)
        self.session_store.append_meeting_log(role, content)
        # 不触发 _run_moderator_loop，保持原有流程状态不变

    def _get_last_assistant_msg(self, agent) -> str:
        """获取 Agent 最后一条 assistant 消息

        Args:
            agent: BaseAgent 子类实例

        Returns:
            最后一条 assistant 消息内容，未找到则返回空字符串
        """
        messages = agent.get_messages()
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""

    def stop_all(self):
        """中止所有活跃的 Worker 线程"""
        for worker in self._active_workers:
            worker.cancel()
            worker.quit()
            worker.wait(3000)  # 最多等 3 秒

        self._active_workers.clear()
        self.state_ctrl.reset()
        self.agent_response.emit(
            "系统", "🛑 所有任务已中止。"
        )

    def new_session(self):
        """开始新会话，重置所有状态"""
        self.stop_all()

        # 重置所有 Agent 的消息历史
        self.cko.clear_history()
        self.pm.clear_history()
        self.arch.clear_history()
        self.designer.clear_history()
        self.coder.clear_history()
        self.tester.clear_history()

        # 重置内部状态
        self._debate_round = 0
        self._mission_protocol = ""
        self._pm_direction = ""

    def _run_audit(self, stage, context, callback):
        """运行 CKO 审计"""
        self.agent_response.emit("CKO", f"👁️ [Vision Keeper] 正在审计 {stage} 产出...")
        # 注意: self._mission_protocol 必须存在
        worker = AuditWorker(self.cko, stage, context, self._mission_protocol, self)
        worker.audit_finished.connect(callback)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)
