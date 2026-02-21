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
from agents.tester_agent import TesterAgent
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

    def get_last_message(self) -> Optional[Message]:
        return self.history[-1] if self.history else None

# ==============================================================================
# 2. Dynamic Router (The "Brain" of the Room)
# ==============================================================================

class InteractionManager:
    """Decides the next turn based on conversation state."""
    
    def __init__(self, context: ConversationContext):
        self.context = context
        self.participants = ["CKO", "PM", "Arch", "Designer", "Coder", "Tester"]

    def decide_next_speaker(self, current_stage: str) -> str:
        """Analyze history and pick the next speaker."""
        last_msg = self.context.get_last_message()
        if not last_msg:
            return "PM" # Default starter

        # 1. Direct Mention Priority (@Coder)
        if last_msg.mentions:
            target = last_msg.mentions[0]
            for p in self.participants:
                if p.lower() in target.lower():
                    return p
        
        # 2. Stage-Specific Routing Logic
        if current_stage == AppState.GROUNDING:
            # In Grounding, if Commander just spoke, it's ALWAYS CKO's turn
            if last_msg.role == "Commander":
                return "CKO"
            # If CKO just spoke, wait for Commander or PM to confirm
            return "PM"

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
                return "Tester"
            # Default fallback for Commander in other phases
            return "PM"

        # 3. Stage-Specific Routing Logic
        task_type = self.context.task_type
        if current_stage == AppState.DEBATE:
            # Domain-Specific Debate Order
            if task_type == "RESEARCH":
                if last_msg.role == "PM": return "CKO"
                if last_msg.role == "CKO": return "Arch"
                if last_msg.role == "Arch": return "Tester"
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
            if last_msg.role == "Coder": return "Tester"
            if last_msg.role == "Tester":
                 if "FAIL" in last_msg.content or "❌" in last_msg.content:
                     return "Coder"
                 else:
                     return "PM"
            return "PM"

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
        self.tester = TesterAgent(self)
        
        self.agents_map = {
            "CKO": self.cko, "PM": self.pm, "Arch": self.arch,
            "Designer": self.designer, "Coder": self.coder, "Tester": self.tester
        }

        # 3. Wiring
        for role, agent in self.agents_map.items():
            agent.typing_started.connect(lambda r=role: self.agent_typing.emit(r, True))
            agent.typing_finished.connect(lambda r=role: self.agent_typing.emit(r, False))
        
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

    def send_to_cko(self, message: str):
        """Legacy entry for Bridge Panel (Grounding)"""
        print(f"DEBUG: Orchestrator.send_to_cko called with: {message[:30]}...")
        # Ensure we are in Grounding mode
        if self.state_ctrl.current_state == AppState.IDLE:
             print("DEBUG: Transitioning from IDLE to GROUNDING")
             self.state_ctrl.transition_to(AppState.GROUNDING)
        
        # In Grounding, the Router should pick CKO.
        # But CKO is special in V1 (Bridge Panel logic). 
        # For hybrid V2, we can just treat it as a Commander message
        # and let the Router send it to CKO if Stage=Grounding.
        # However, to be safe and support legacy Bridge flow:
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
        self._next_turn_ready.emit()

    # --------------------------------------------------------------------------
    # Event Loop Processing
    # --------------------------------------------------------------------------

    def _process_next_turn(self):
        """The Main Brain: Decides who speaks and executes it."""
        current_state = self.state_ctrl.current_state
        if current_state == AppState.IDLE:
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
             
        # 3. Special Handling: PM Decision Parsing (Structured System Commands)
        if last_msg and last_msg.role == "PM":
            content = last_msg.content
            # Match structured system command: <SYS_CMD:APPROVE> or legacy "APPROVED"
            if (re.search(r'<SYS_CMD:(APPROVE|APPROVED)>', content, re.IGNORECASE) or "APPROVED" in content) and current_state == AppState.DEBATE:
                self.state_ctrl.transition_to(AppState.PRODUCTION)
                self.agent_response.emit("System", f"PM Approved Plan. Moving to PRODUCTION ({self.ctx.task_type}).")
                # Trigger initial coder kickoff by adding a system nudge
                self.ctx.add_message("System", f"Phase changed to PRODUCTION. Team, please execute the {self.ctx.task_type} plan.")
                self._next_turn_ready.emit()
                return

        # 4. Delivery Handling (Structured System Commands)
        if last_msg and last_msg.role == "PM":
            content = last_msg.content
            # Match structured system command: <SYS_CMD:DELIVER> or legacy "DELIVER"
            if (re.search(r'<SYS_CMD:(DELIVER)>', content, re.IGNORECASE) or "DELIVER" in content) and current_state == AppState.VERIFICATION:
                self._start_delivery()
                return

        # 4. Execute
        agent = self.agents_map.get(next_role)
        if not agent:
            print(f"Error: Unknown role {next_role}")
            return
            
        # 5. Check if we should wait for user? 
        # For V2, we let the loop run until it stabilizes or hits max turns.
        
        self._run_agent(agent)

    def _run_agent(self, agent):
        # Prepare Prompt with Context (The "Dynamic" part)
        recent_history = self.ctx.get_recent_history(limit=10)
        
        # Inject "Awareness"
        prompt = (
            f"You are {agent.role} in a War Room debate.\n"
            f"Current Phase: {self.state_ctrl.current_state}\n"
            f"Review the recent history and respond to the last speaker or the Commander.\n"
            f"If you need to address someone, use @Role.\n"
            f"If consensus is reached (or job done), indicate it.\n\n"
            f"--- History ---\n{recent_history}\n\n"
            f"Your response:"
        )

        # Worker Thread
        worker = AgentWorker(agent, prompt) # Worker is local class
        worker.finished_with_result.connect(self._on_agent_finished)
        worker.error_occurred.connect(lambda r, e: self.error_occurred.emit(e)) # Simplified string error
        worker.finished.connect(worker.deleteLater)  # Fix memory leak

        self._active_worker = worker # Keep ref
        worker.start()

    def _on_agent_finished(self, role: str, content: str):
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
        if self._turn_count > 50: # Safety break
            self.agent_response.emit("System", "Max turns reached. Pausing.")
            return 
            
        # Recursive Step (Async via Signal to avoid stack depth)
    def _start_delivery(self):
        """Phase 5: DELIVERY - Compile final pack"""
        if not self.state_ctrl.transition_to(AppState.DELIVERY):
            return
            
        self.agent_response.emit("System", "🚀 Entering DELIVERY Phase. Compiling final project package...")
        
        # Compile Summary
        summary = f"# Final Delivery Package\n\n## Project: {self.ctx.mission_protocol.get('project_title', 'Untitled')}\n"
        summary += f"## Domain: {self.ctx.task_type}\n\n"
        summary += "### Component Contributions:\n"
        
        for role in ["Arch", "Designer", "Coder", "Tester"]:
            summary += f"- **{role}**: Completed {self.ctx.task_type} related tasks.\n"
            
        summary += "\n### Final Assets:\n- Ready for deployment/presentation."
        
        self.agent_response.emit("System", summary)
        QTimer.singleShot(2000, lambda: self.state_ctrl.transition_to(AppState.COMPLETED))

