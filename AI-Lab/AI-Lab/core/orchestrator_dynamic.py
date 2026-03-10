"""
orchestrator_dynamic.py - 动态多智能体编排引擎 (V2)
==================================================

Replaces fixed-loop logic with an Event-Driven Architecture.

Key Concepts:
  1. ConversationContext: Global message bus (The "War Room" State).
  2. InteractionManager: Decides "Who speaks next?" based on history.
  3. Dynamic Loop: Agents respond to events, not just PM commands.

"""

import traceback
import re
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

# Reuse existing agents
from agents.cko_agent import CKOAgent
from agents.pm_agent import PMAgent
from agents.arch_agent import ArchAgent
from agents.designer_agent import DesignerAgent
from agents.coder_agent import CoderAgent
from agents.validator_agent import ValidatorAgent
from agents.base_agent import BaseAgent

from core.state_controller import StateController
from core.session_store import SessionStore
from config import AppState, MAX_DEBATE_ROUNDS

# ==============================================================================
# 1. Context & Message Bus
# ==============================================================================

class Message:
    def __init__(self, role: str, content: str, intent: str = "statement"):
        self.role = role
        self.content = content
        self.intent = intent  # statement, question, critique, agreement, command
        self.timestamp = 0    # Logical clock or real time
        self.mentions: List[str] = self._extract_mentions(content)

    def _extract_mentions(self, text: str) -> List[str]:
        # Extract @Role
        return re.findall(r"@(\w+)", text)

class ConversationContext:
    """Manages the shared state of the War Room discussion."""
    def __init__(self):
        self.history: List[Message] = []
        self.artifacts: Dict[str, Any] = {} # Shared docs/code
        self.mission_protocol: Dict[str, Any] = {} # Structured Protocol
        self.task_type: str = "SOFTWARE" # Default
    
    def add_message(self, role: str, content: str, intent="statement"):
        msg = Message(role, content, intent)
        # Simple logical clock simulation
        msg.timestamp = len(self.history) + 1
        self.history.append(msg)
        return msg

    def get_recent_history(self, limit=10) -> str:
        """Format history for LLM Context Window."""
        lines = []
        for msg in self.history[-limit:]:
            lines.append(f"{msg.role}: {msg.content}")
        return "\n".join(lines)

    def get_incremental_context(self, exclude_role="PM", limit=10) -> str:
        """Get context excluding recent messages from a specific role to avoid repetition."""
        if not self.history:
            return ""

        # Find the last message from the excluded role
        last_exclude_index = -1
        for i, msg in enumerate(reversed(self.history)):
            if msg.role == exclude_role:
                last_exclude_index = len(self.history) - 1 - i
                break

        # If no excluded role found or it's the last message, return recent history
        if last_exclude_index == -1 or last_exclude_index >= len(self.history) - 1:
            return self.get_recent_history(limit)

        # Get messages after the last excluded role message
        start_idx = last_exclude_index + 1
        recent_msgs = self.history[start_idx:]

        # Limit the number of messages
        if len(recent_msgs) > limit:
            recent_msgs = recent_msgs[-limit:]

        lines = []
        for msg in recent_msgs:
            lines.append(f"{msg.role}: {msg.content}")
        return "\n".join(lines)

    def get_last_message(self) -> Optional[Message]:
        return self.history[-1] if self.history else None

# ==============================================================================
# 2. Dynamic Router (The "Brain" of the Room)
# ==============================================================================

class InteractionManager:
    """Decides the next turn based on conversation state."""
    
    def __init__(self, context: ConversationContext):
        self.context = context
        self.participants = ["CKO", "PM", "Arch", "Designer", "Coder", "Validator"]

    def decide_next_speaker(self, current_stage: str) -> str:
        """Analyze history and pick the next speaker."""
        last_msg = self.context.get_last_message()
        if not last_msg:
            return "PM" # Default starter

        # 0. Anti-repetition: Prevent PM from speaking too frequently
        if last_msg and last_msg.role == "PM":
            # Check last 5 messages for PM frequency
            recent_msgs = self.context.history[-5:] if len(self.context.history) >= 5 else self.context.history
            pm_count = sum(1 for msg in recent_msgs if msg.role == "PM")
            if pm_count >= 3:  # PM has spoken too much recently
                # Force another role to speak based on current stage
                if current_stage == AppState.DEBATE:
                    # Check who hasn't spoken recently
                    recent_roles = [msg.role for msg in recent_msgs]
                    for role in ["Arch", "Designer", "CKO"]:
                        if role not in recent_roles:
                            return role
                    # Fallback to Arch
                    return "Arch"
                elif current_stage == AppState.PRODUCTION:
                    return "Coder" if "Coder" not in [msg.role for msg in recent_msgs[-2:]] else "Validator"

        # 1. Direct Mention Priority (@Role) - ANY role can mention another to hand off
        # Highest priority: If the last message explicitly mentions someone, they are next.
        # 需求打磨阶段只允许 CKO 被呼叫，禁止其他角色插入
        if last_msg.mentions:
            for mention in last_msg.mentions:
                for p in self.participants:
                    if p.lower() == mention.lower():
                        if p != last_msg.role:
                            if current_stage == AppState.GROUNDING and p != "CKO":
                                break  # 不交给非 CKO，继续走阶段逻辑
                            print(f"[InteractionManager] Route override: {last_msg.role} explicitly called @{p}")
                            return p

        # 1.5 下一发言者指令（下一发言者: 角色名 或 NEXT_SPEAKER: 角色名）
        if last_msg:
            import re
            match = re.search(r'(?:下一发言者|NEXT_SPEAKER)\s*:\s*([A-Za-z]+)', last_msg.content, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                for p in self.participants:
                    if p.lower() == target.lower():
                        if p != last_msg.role:
                            if current_stage == AppState.GROUNDING and p != "CKO":
                                break  # 需求打磨阶段不交给非 CKO
                            print(f"[InteractionManager] Route override: {last_msg.role} directed next speaker to {p}")
                            return p

        # 2. Stage-Specific Routing Logic
        if current_stage == AppState.GROUNDING:
            # 仅允许 Commander ↔ CKO 对话，确认立项前其他角色不插入
            if last_msg.role == "Commander":
                return "CKO"
            if last_msg.role == "CKO":
                return None  # 等待用户继续与 CKO 讨论或点击「确认立项」
            return None

        # 3. User Command Override (NLP-inspired keywords)
        if last_msg.role == "Commander":
            txt = last_msg.content.lower()
            if "bug" in txt or "error" in txt or "code" in txt or "fix" in txt:
                return "Coder"
            if "design" in txt or "color" in txt or "ui" in txt or "style" in txt:
                return "Designer"
            if "plan" in txt or "task" in txt or "schedule" in txt:
                return "PM"
            if "test" in txt or "verify" in txt:
                return "Validator"
            # Default fallback for Commander in other phases
            return "PM"

        # 3. Stage-Specific Routing Logic
        task_type = self.context.task_type
        if current_stage == AppState.DEBATE:
            # Domain-Specific Debate Order
            if task_type == "RESEARCH":
                if last_msg.role == "PM": return "CKO"
                if last_msg.role == "CKO": return "Arch"
                if last_msg.role == "Arch": return "Validator"
                return "PM"
            elif task_type == "DESIGN":
                if last_msg.role == "PM": return "Designer"
                if last_msg.role == "Designer": return "Arch"
                if last_msg.role == "Arch": return "PM"
                return "PM"
            else:
                if last_msg.role == "PM": return "Arch"
                if last_msg.role == "Arch": return "Designer"
                if last_msg.role == "Designer": return "PM"
                return "PM"
            
        elif current_stage == AppState.PRODUCTION:
            if last_msg.role == "PM": return "Coder"
            if last_msg.role == "Coder": return "Validator"
            if last_msg.role == "Validator":
                 if "FAIL" in last_msg.content or "❌" in last_msg.content:
                     return "Coder"
                 else:
                     return "PM"
            return "PM"

        if last_msg.role == "PM":
            return None

        return "PM"
# ==============================================================================
# 3. Orchestrator Implementation
# ==============================================================================

class AgentWorker(QThread):
    finished_with_result = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str, str)

    def __init__(self, agent, message: str, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.message = message

    def run(self):
        try:
            # Dynamic Context Injection (simulated here, can be moved to agent class)
            # self.agent.update_system_prompt(...) 
            response = self.agent.send_message(self.message)
            self.finished_with_result.emit(self.agent.role, response)
        except Exception as e:
            self.error_occurred.emit(self.agent.role, str(e))

class OrchestratorDynamic(QObject):
    """
    V2 Orchestrator: Event-Driven.
    Replaces the fixed 'run_moderator_loop'.
    """
    # Signals (Same API as V1 for UI compatibility)
    agent_response = pyqtSignal(str, str)
    state_changed = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)
    workflow_completed = pyqtSignal()
    debate_round_info = pyqtSignal(int, int)
    agent_typing = pyqtSignal(str, bool)
    agent_stream_chunk = pyqtSignal(str, str)   # (角色, 文本片段)

    # Internal Signals for Event Loop
    _next_turn_ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. State & Context
        self.state_ctrl = StateController(self)
        self.ctx = ConversationContext()
        self.router = InteractionManager(self.ctx)
        self.session_store = SessionStore() # Persist to disk
        
        # 2. Agents
        self.cko = CKOAgent(self)
        self.pm = PMAgent(self)
        self.arch = ArchAgent(self)
        self.designer = DesignerAgent(self)
        self.coder = CoderAgent(self)
        self.validator = ValidatorAgent(self)
        
        self.agents_map = {
            "CKO": self.cko, "PM": self.pm, "Arch": self.arch,
            "Designer": self.designer, "Coder": self.coder, "Validator": self.validator
        }

        # 3. Wiring
        for role, agent in self.agents_map.items():
            # agent emits (role) as first arg, map to (role, bool)
            agent.typing_started.connect(lambda emitted_role: self.agent_typing.emit(emitted_role, True))
            agent.typing_finished.connect(lambda emitted_role: self.agent_typing.emit(emitted_role, False))
            # agent emits (role, chunk), pass through directly
            agent.stream_chunk.connect(self.agent_stream_chunk.emit)

        # Forward state signals
        self.state_ctrl.state_changed.connect(self.state_changed.emit)
        
        # Event Loop Trigger
        self._next_turn_ready.connect(self._process_next_turn)
        self._active_worker = None
        self._turn_count = 0

    # --------------------------------------------------------------------------
    # Public API (UI Triggers)
    # --------------------------------------------------------------------------

    def inject_user_message(self, message: str):
        """Entry point for User (Commander)"""
        # 1. Display in UI immediately
        self.agent_response.emit("Commander", message)
        
        # 2. Add to Context
        self.ctx.add_message("Commander", message, intent="command")
        self.session_store.append_meeting_log("Commander", message)
        
        # 3. Trigger Event Loop
        self._next_turn_ready.emit()

    def new_session(self):
        """Reset the orchestrator for a new session."""
        print("[OrchestratorV2] Starting new session...")
        self.state_ctrl.reset()  # Reset to IDLE
        self.ctx = ConversationContext() # Clear context
        self.router = InteractionManager(self.ctx) # Re-bind router to new context
        self.session_store.create_session(user_intent="New Session") # Create new log
        self._turn_count = 0
        if self._active_worker:
            self._active_worker.quit()
        # Notify UI to clear
        self.agent_response.emit("System", "Session Reset. Ready for new commands.")

    def send_to_cko(self, message: str):
        """Legacy entry for Bridge Panel (Grounding)"""
        print(f"DEBUG: Orchestrator.send_to_cko called with: {message[:30]}...")
        # Ensure we are in Grounding mode
        if self.state_ctrl.current_state == AppState.IDLE:
             print("DEBUG: 从空闲进入需求打磨")
             self.state_ctrl.transition_to(AppState.GROUNDING)
        
        # In Grounding, the Router should pick CKO.
        # But CKO is special in V1 (Bridge Panel logic). 
        # For hybrid V2, we can just treat it as a Commander message
        # and let the Router send it to CKO if Stage=Grounding.
        # However, to be safe and support legacy Bridge flow:
        self.inject_user_message(message)

    def handle_user_intervention(self, message: str):
        """处理用户从 War Room 面板发起的干预指令"""
        print(f"DEBUG: User intervention received: {message[:30]}...")
        # 将用户干预作为 Commander 消息注入
        self.inject_user_message(message)

    def confirm_project(self):
        """Legacy: User clicks Confirm in Bridge"""
        # 1. Parse Mission Protocol from Context
        import json
        last_cko_msg = None
        for msg in reversed(self.ctx.history):
            if msg.role == "CKO":
                last_cko_msg = msg.content
                break
        
        if last_cko_msg:
            try:
                # Extract JSON from CKO response
                match = re.search(r"```json(.*?)```", last_cko_msg, re.DOTALL)
                protocol_str = match.group(1).strip() if match else last_cko_msg
                self.ctx.mission_protocol = json.loads(protocol_str)
                self.ctx.task_type = self.ctx.mission_protocol.get("task_type", "SOFTWARE").upper()
            except Exception as e:
                print(f"Protocol Parse Error: {e}")
                self.ctx.task_type = "SOFTWARE"

        # 2. Update Personas
        for role, agent in self.agents_map.items():
            if role != "CKO": # CKO is always CKO
                agent.set_domain_persona(self.ctx.task_type)

        # 3. Transition to Debate
        self.state_ctrl.transition_to(AppState.DEBATE)
        
        # Inject Event to Update Context
        sys_msg = f"PROJECT CONFIRMED. Mode: [{self.ctx.task_type}]. Entering DEBATE phase."
        self.ctx.add_message("System", sys_msg, intent="system_event")
        self.agent_response.emit("System", sys_msg)
        
        # Trigger loop to start PM
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    # --------------------------------------------------------------------------
    # Event Loop Processing
    # --------------------------------------------------------------------------

    def _process_next_turn(self):
        """The Main Brain: Decides who speaks and executes it."""
        current_state = self.state_ctrl.current_state
        if current_state in (AppState.IDLE, AppState.COMPLETED):
            return

        # 1. Router Decision
        next_role = self.router.decide_next_speaker(current_state)
        print(f"[OrchestratorV2] Next Speaker: {next_role}")

        # 2. Check Termination / Pauses -> Logic inside Router or here
        last_msg = self.ctx.get_last_message()
        if last_msg:
             # Stop loop if we just heard from the same person (simple debounce)
             # unless it's a multi-part message? Let's strictly enforce turn-taking for now.
             pass
             
        # 3. Special Handling: PM Decision Parsing (Structured System Commands & NLP Cues)
        if last_msg and last_msg.role == "PM":
            content = last_msg.content
            # 匹配批准类指令：决策: 通过 / DECISION: APPROVED / 下一发言者: Coder 等
            approved = (re.search(r'<SYS_CMD:(APPROVE|APPROVED)>', content, re.IGNORECASE) or
                        re.search(r'(?:决策|DECISION)\s*:\s*(?:通过|APPROVED)', content, re.IGNORECASE) or
                        "APPROVED" in content or "通过" in content or
                        re.search(r'(?:下一发言者|NEXT_SPEAKER)\s*:\s*Coder', content, re.IGNORECASE))

            if approved and current_state == AppState.DEBATE:
                self.state_ctrl.transition_to(AppState.PRODUCTION)
                self.agent_response.emit("System", f"PM 批准方案，进入执行阶段（{self.ctx.task_type}）。")
                # Trigger initial coder kickoff by adding a system nudge
                self.ctx.add_message("System", f"Phase changed to PRODUCTION. Team, please execute the {self.ctx.task_type} plan.")
                QTimer.singleShot(1500, self._next_turn_ready.emit)
                return

        # 4. Delivery Handling (Structured System Commands & NLP Cues)
        if last_msg and last_msg.role == "PM":
            content = last_msg.content
            # 匹配交付类指令：下一发言者: Validator / 终局发布 等
            delivered = (re.search(r'<SYS_CMD:(DELIVER)>', content, re.IGNORECASE) or
                        "DELIVER" in content or
                        "测试终局发布" in content or "圆满终局" in content or "封神终局" in content or
                        re.search(r'(?:下一发言者|NEXT_SPEAKER)\s*:\s*Validator', content, re.IGNORECASE))

            if delivered and current_state in [AppState.PRODUCTION, AppState.VERIFICATION]:
                self._start_delivery()
                return

        # 4. Execute
        if not next_role:
            print(f"[OrchestratorV2] 暂停自动流转，等待外部输入 (Role={next_role})")
            return
            
        agent = self.agents_map.get(next_role)
        if not agent:
            print(f"Error: Unknown role {next_role}")
            return
            
        # 5. Check if we should wait for user?
        # For V2, we let the loop run until it stabilizes or hits max turns.
        
        self._run_agent(agent)

    def _run_agent(self, agent):
        # Prepare Prompt with Context (The "Dynamic" part)
        # Use incremental context for PM to avoid repetition
        if agent.role == "PM":
            recent_history = self.ctx.get_incremental_context(exclude_role="PM", limit=10)
            if not recent_history.strip():
                # Fallback to recent history if no incremental context
                recent_history = self.ctx.get_recent_history(limit=10)
        else:
            recent_history = self.ctx.get_recent_history(limit=10)

        # Inject "Awareness"
        prompt = (
            f"你是 War Room 讨论组中的 {agent.role}。\n"
            f"当前开发阶段: {self.state_ctrl.current_state}\n"
            f"【核心纪律要求】:\n"
            f"1. 请务必使用流利、自然的中文回复，切勿使用机器翻译腔。\n"
            f"2. 绝对禁止互相吹捧、客套废话或无意义的认同（如'你说的很对'、'非常赞同'等）。\n"
            f"3. 你的发言必须直奔主题，只输出干货、代码、实质性建议或决策。\n"
            f"4. ⚠️ 除非你真的需要强制将**下一个发言权**精准移交给某个人，否则**绝对不要**随意使用 `@角色名`（严禁客套）。系统会自动分配下一轮发言。\n"
            f"   (PM 可使用 `下一发言者: 角色名`，其他角色如确需交接请在句末使用 `@角色名`)。\n"
            f"5. 如果达成共识或你的任务已完成，请清楚地表达出来。\n\n"
            f"--- 历史对话 ---\n{recent_history}\n\n"
            f"你的回复:"
        )

        # Worker Thread
        worker = AgentWorker(agent, prompt) # Worker is local class
        worker.finished_with_result.connect(self._on_agent_finished)
        worker.error_occurred.connect(lambda r, e: self.error_occurred.emit(e)) # Simplified string error
        worker.finished.connect(worker.deleteLater)  # Fix memory leak

        self._active_worker = worker # Keep ref
        worker.start()

    def _on_agent_finished(self, role: str, content: str):
        # 0. 拦截并处理工具调用结果，防止原始 JSON 暴露在 UI
        if content.startswith("__TOOL_RESULT__:"):
            try:
                import json
                tool_data = json.loads(content[len("__TOOL_RESULT__:") :])
                content = tool_data.get("content", "").strip()
                # 如果只有工具调用而没有实质文本，给予默认提示或略过
                if not content:
                    content = "【已执行内部工具调用】"
            except Exception as e:
                print(f"[OrchestratorV2] 解析工具调用结果时出错: {e}")

        # 0. Real-time repetition detection for PM
        if role == "PM":
            original_length = len(content)
            content = self._detect_and_handle_pm_repetition(content)
            if len(content) != original_length:
                print(f"[重复处理] PM回复已精简: {original_length} → {len(content)} 字符")

        # 1. Update State
        self.ctx.add_message(role, content)
        self.session_store.append_meeting_log(role, content)

        # 2. Update UI
        self.agent_response.emit(role, content)

        # 3. Special Handling (Code Extraction)
        if role == "Coder":
            self._handle_code_extraction(content)

        # 4. Continue Loop
        # Check constraints (max turns?)
        self._turn_count += 1
        # if self._turn_count > 50: # Safety break
        #     self.agent_response.emit("System", "Max turns reached. Pausing.")
        #     return

        # Recursive Step (Async via Signal to avoid stack depth)
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（基于Jaccard相似度）

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            相似度分数 0.0-1.0
        """
        # 简单实现：基于词集的Jaccard相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

    def _detect_and_handle_pm_repetition(self, content: str) -> str:
        """检测并处理PM回复的重复内容

        Args:
            content: PM的回复内容

        Returns:
            处理后的内容（如果重复则精简）
        """
        # 获取最近的PM回复（排除当前）
        pm_messages = []
        for msg in reversed(self.ctx.history[:-1]):  # 排除当前消息（尚未添加）
            if msg.role == "PM":
                pm_messages.append(msg.content)
                if len(pm_messages) >= 2:  # 检查最近2条PM回复
                    break

        if not pm_messages:
            return content

        # 计算与最近PM回复的最大相似度
        max_similarity = 0.0
        for pm_content in pm_messages:
            similarity = self._calculate_text_similarity(content, pm_content)
            max_similarity = max(max_similarity, similarity)

        # 如果相似度超过阈值，精简回复
        if max_similarity > 0.6:  # 60%相似度阈值
            print(f"[重复检测] PM回复相似度{max_similarity:.2f}，已标记")
            # 精简策略：保留第一段或前100字符
            lines = content.split('\n')
            if len(lines) > 1:
                # 尝试提取核心部分（第一段）
                simplified = lines[0].strip()
                if len(simplified) < 20:  # 太短则保留前两行
                    simplified = '\n'.join(lines[:2]).strip()
                content = f"【精简版】{simplified}...（与之前回复相似度较高）"
            else:
                # 单行内容，截断
                if len(content) > 100:
                    content = f"【精简版】{content[:100]}...（与之前回复相似）"
            return content

        return content

    def _handle_code_extraction(self, content: str):
        """处理代码提取逻辑（从 Coder 回复中提取代码块）

        Args:
            content: Coder 回复的完整内容
        """
        import os
        import re
        import datetime

        try:
            # 1. 更新会话中的 final_code
            self.session_store.update_session(final_code=content)

            # 2. 尝试正则提取代码
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

                    # 尝试从代码文本第一行提取文件名
                    filename = None
                    lines = pure_code.split('\n')
                    if lines:
                        first_line = lines[0].strip()
                        # 匹配 // filename: x.js 或 # filename: x.py 或 /* filename: x.css */ 或 <!-- filename: x.html -->
                        name_match = re.search(r'(?://|#|/\*|<!--)\s*filename:\s*([^\s\*>]+)', first_line, re.IGNORECASE)
                        if name_match:
                            filename = name_match.group(1).strip()
                            # （可选）从纯代码中移除文件名那一行
                            pure_code = '\n'.join(lines[1:]).strip()

                    if not filename:
                        # 3. 动态文件后缀推导 fallback
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
                        ext = EXTENSION_MAP.get(lang_tag, ".py") # 如果未识别，默认 .py
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"generated_{timestamp}_{i}{ext}"

                    # 5. 安全写入与命名
                    # 确保子目录结构被创建
                    file_path = os.path.abspath(os.path.join(workspace_dir, filename))
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(pure_code)
                    saved_files.append(file_path)

                # 6. 系统消息广播
                joined_paths = "\n".join(saved_files)
                print(f"[Orchestrator] 成功提取代码并保存:\n{joined_paths}")
                self.agent_response.emit("System", f"💾 最终代码已保存至:\n{joined_paths}")
            else:
                print("[Orchestrator] 未找到标准 Markdown 代码块，略过自动保存。")
        except Exception as e:
            print(f"[Orchestrator] 解析并保存代码文件时发生异常: {e}")

    def _start_delivery(self):
        """Phase 5: DELIVERY - Compile final pack"""
        if not self.state_ctrl.transition_to(AppState.DELIVERY):
            return

        self.agent_response.emit("System", "🚀 Entering DELIVERY Phase. Compiling final project package...")

        # Compile Summary
        summary = f"# Final Delivery Package\n\n## Project: {self.ctx.mission_protocol.get('project_title', 'Untitled')}\n"
        summary += f"## Domain: {self.ctx.task_type}\n\n"
        summary += "### Component Contributions:\n"

        for role in ["Arch", "Designer", "Coder", "Validator"]:
            summary += f"- **{role}**: Completed {self.ctx.task_type} related tasks.\n"

        summary += "\n### Final Assets:\n- Ready for deployment/presentation."

        self.agent_response.emit("System", summary)
        QTimer.singleShot(2000, lambda: self.state_ctrl.transition_to(AppState.COMPLETED))

