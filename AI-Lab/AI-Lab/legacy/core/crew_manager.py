import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from crewai import Crew, Process
from config import API_KEYS
# Set environment variables before importing crew_agents
os.environ["OPENAI_API_KEY"] = API_KEYS.get("hiapi", "")
os.environ["OPENAI_API_BASE"] = "https://hiapi.online/v1"

from agents.crew_agents import (
    cko_agent, pm_agent, arch_agent, 
    designer_agent, coder_agent, tester_agent
)
from core.crew_tasks import (
    grounding_task, design_task, detail_design_task,
    production_task, verification_task, review_task
)
import threading
import sys
import io
import re
import queue # For human input synchronization

# Set UTF-8 encoding for Windows standard output to avoid UnicodeEncodeError (GBK issues)
if sys.platform == "win32":
    try:
        import codecs
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
            sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except Exception:
        pass

class StreamRedirector(io.StringIO):
    """Redirects stdout to a Qt signal line by line with passthrough."""
    def __init__(self, callback, original_stream=None):
        super().__init__()
        self.callback = callback
        self.original_stream = original_stream
        self.buffer = ""

    def write(self, s):
        # Always passthrough to original terminal for my own debugging
        if self.original_stream:
            try:
                self.original_stream.write(s)
                self.original_stream.flush()
            except Exception:
                # Use backslashreplace to see the escape sequences instead of just '?'
                try:
                    safe_s = s.encode(sys.stdout.encoding or 'ascii', errors='backslashreplace').decode(sys.stdout.encoding or 'ascii')
                    self.original_stream.write(safe_s)
                    self.original_stream.flush()
                except:
                    pass
            
        # Only process for the signal/UI if it's NOT from the main thread
        if threading.current_thread() is threading.main_thread():
            return len(s)

        self.buffer += s
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            # CRITICAL: We need the full raw lines for signal parsing
            for line in lines[:-1]:
                self.callback(line)
            self.buffer = lines[-1]
        return len(s)

class CrewWorker(QThread):
    """Worker thread for running CrewAI without blocking UI."""
    result_ready = pyqtSignal(str)
    thought_stream = pyqtSignal(str) # Internal thoughts/logs

    def __init__(self, crew: Crew):
        super().__init__()
        self.crew = crew

    def run(self):
        # Redirect both stdout and stderr to capture all CrewAI output
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        # Use a single redirector instance with passthrough
        redirector = StreamRedirector(self.thought_stream.emit, original_stdout)
        sys.stdout = redirector
        sys.stderr = redirector
        
        print("[DEBUG] CrewWorker: Thread execution beginning...")
        try:
            # We use kickoff(inputs={}) if preferred, but start_mission already set task descriptions
            result = self.crew.kickoff()
            print(f"[TRACE] CrewWorker: Kickoff finished. Result preview: {str(result)[:50]}...")
            self.result_ready.emit(str(result))
        except Exception as e:
            import traceback
            err = f"[ERROR] CrewAI Execution Failed: {str(e)}\n{traceback.format_exc()}"
            print(err)
            self.thought_stream.emit(err)
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            print("[DEBUG] CrewWorker: Thread execution finished and streams restored.")

class ProxyAgent(QObject):
    """Mocks the legacy agent interface for UI compatibility."""
    typing_started = pyqtSignal()
    typing_finished = pyqtSignal()
    response_ready = pyqtSignal(str)
    state_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

class CrewManager(QObject):
    """Orchestrates CrewAI agents and manages signal-based communication with the UI.
    
    核心架构：
    - **两阶段工作流**：
      - Phase 1: 仅运行 CKO grounding_task（需求分析/立项）
      - Phase 2: 用户点击"确认项目"后，才运行 design → production → review
    - CrewAI 的 verbose 输出通过 StreamRedirector 逐行捕获
    - _on_thought_stream 使用【块级累积】策略，将多行输出合并为完整消息后再发射
    """
    agent_response = pyqtSignal(str, str)     # role, content
    state_changed = pyqtSignal(str, str)      # state_id, description
    error_occurred = pyqtSignal(str)          # error_message
    workflow_completed = pyqtSignal()         # Full cycle finished
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Mock legacy agents to satisfy main.py signal connections
        self.cko = ProxyAgent()
        self.pm = ProxyAgent()
        self.arch = ProxyAgent()
        self.designer = ProxyAgent()
        self.coder = ProxyAgent()
        self.tester = ProxyAgent()
        
        self.state_ctrl = type('obj', (object,), {'current_state': "IDLE", 'state_description': "CrewAI Initializing..."})
        
        # ===== 两阶段 Crew 定义 =====
        # Phase 1: 仅 CKO 做需求分析/立项
        self._crew_phase1 = Crew(
            agents=[cko_agent],
            tasks=[grounding_task],
            process=Process.sequential,
            verbose=True
        )
        # Phase 2: 设计 → 详设 → 开发 → 验证 → 审批（用户确认后才运行）
        self._crew_phase2 = Crew(
            agents=[arch_agent, designer_agent, coder_agent, tester_agent, pm_agent],
            tasks=[design_task, detail_design_task, production_task, verification_task, review_task],
            process=Process.sequential,
            verbose=True
        )
        
        self._worker = None
        self._seen_messages = set()         # 精确匹配去重（只存完整消息的哈希）
        self._input_queue = queue.Queue()   # 人类输入同步队列
        self._last_user_input = ""          # 保存用户输入供 Phase 2 使用
        
        # ===== 块级累积状态 =====
        self._answer_buffer = []            # 累积 Final Answer 的行
        self._current_role = "System"       # 当前正在说话的角色
        self._in_answer_block = False       # 是否正在累积 Final Answer 块
        self._in_box = False                # 是否在装饰框内

    def start_mission(self, user_input: str):
        """Phase 1: 仅运行 CKO grounding_task（需求分析/立项）。
        
        用户发送消息后，只有 CKO 会响应。其他 Agent 需要等待用户
        点击"确认项目"按钮后才启动。
        """
        print(f"[TRACE] CrewManager: Phase 1 (CKO grounding) triggered with: {user_input[:50]}...")
        try:
            self._reset_state()
            self._last_user_input = user_input
            
            if not grounding_task:
                 print("[CRITICAL] CrewManager: grounding_task is None!")
                 return

            grounding_task.description = (
                f"用户输入: {user_input}\n\n"
                f"【任务指令】作为 CKO（首席知识官），请对用户输入进行需求分析：\n"
                f"1. 如果用户输入仅为简短问候或模糊描述，你必须：\n"
                f"   - 先礼貌回应\n"
                f"   - 然后提出 3-5 个编号的结构化追问，覆盖以下维度：\n"
                f"     a) 项目类型（软件/研究/设计/工程）\n"
                f"     b) 核心功能和目标\n"
                f"     c) 技术栈偏好\n"
                f"     d) 目标用户群体\n"
                f"     e) 时间和规模要求\n"
                f"   - 明确告知用户需要回答这些问题后才能生成任务协议\n"
                f"2. 如果用户已提供具体需求，请直接生成结构化任务协议\n"
                f"3. 输出必须使用简体中文\n"
                f"4. 先写自然语言摘要，再用编号列表提问"
            )
            
            self._worker = CrewWorker(self._crew_phase1)
            self._worker.result_ready.connect(self._on_phase1_complete)
            self._worker.thought_stream.connect(self._on_thought_stream)
            self._worker.start()
            
            self.state_changed.emit("GROUNDING", "CKO 正在分析需求...")
            
        except Exception as e:
            import traceback
            err = f"[FATAL] CrewManager Error in start_mission: {str(e)}\n{traceback.format_exc()}"
            print(err)
            self.error_occurred.emit(err)

    def _on_phase1_complete(self, result: str):
        """Phase 1 完成：CKO 已回复，等待用户确认。"""
        self._flush_buffer()
        self.agent_response.emit("System", "📋 CKO 需求分析已完成。请点击右上角 **Confirm Project** 按钮确认立项，启动后续开发流程。")
        self.state_changed.emit("AWAITING_CONFIRM", "等待用户确认立项...")

    def confirm_project(self):
        """用户点击"确认项目"后触发 Phase 2：设计 → 开发 → 评审。"""
        print("[TRACE] CrewManager: Phase 2 (design → production → review) triggered by Confirm button.")
        try:
            self._reset_state()
            
            self._worker = CrewWorker(self._crew_phase2)
            self._worker.result_ready.connect(self._on_mission_complete)
            self._worker.thought_stream.connect(self._on_thought_stream)
            self._worker.start()
            
            self.agent_response.emit("System", "🚀 项目已确认！设计 → 开发 → 评审 流程启动中...")
            self.state_changed.emit("DESIGNING", "Arch 正在设计系统架构...")
            
        except Exception as e:
            import traceback
            err = f"[FATAL] CrewManager Error in confirm_project: {str(e)}\n{traceback.format_exc()}"
            print(err)
            self.error_occurred.emit(err)

    def _reset_state(self):
        """重置所有内部状态，准备新一轮执行。"""
        self._seen_messages.clear()
        self._answer_buffer.clear()
        self._in_answer_block = False
        self._in_box = False
        self._current_role = "System"

    def _clean_line(self, line: str) -> str:
        """清理单行文本：移除 ANSI 转义、装饰框字符、前后空白"""
        # 解码 backslashreplace 产生的 \uXXXX 转义
        if "\\u" in line:
            try:
                import codecs
                line = codecs.decode(line, 'unicode_escape')
            except Exception:
                pass
        # 移除 ANSI 颜色码
        line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
        # 移除装饰框字符（│ ┃ ┌ ┐ └ ┘ ─ ━ ═ ╭ ╮ ╰ ╯ ╔ ╗ ╚ ╝ 等）
        line = re.sub(r'[│┃┌┐└┘├┤┬┴┼─━═╭╮╰╯╔╗╚╝╟╢╤╧╪┕┑┍┙┏┓┗┛┣┫┳┻╋║╠╣╦╩╬]', '', line)
        return line.strip()

    def _detect_role(self, line: str) -> str:
        """从一行文本中检测角色"""
        role_map = {
            "首席知识官": "CKO", "CKO": "CKO",
            "项目经理": "PM", "PM": "PM",
            "系统架构师": "Arch", "Arch": "Arch",
            "设计师": "Designer", "Designer": "Designer",
            "资深开发工程师": "Coder", "Coder": "Coder",
            "验证官": "Tester", "Tester": "Tester",
        }
        for key, val in role_map.items():
            if key in line:
                return val
        return None

    def _is_box_border(self, raw_line: str) -> bool:
        """判断原始行是否只是装饰框边框"""
        stripped = re.sub(r'[│┃┌┐└┘├┤┬┴┼─━═╭╮╰╯╔╗╚╝╟╢╤╧╪┕┑┍┙┏┓┗┛┣┫┳┻╋║╠╣╦╩╬\s🚀🤖💬📋✅❌🧠⚡]', '', raw_line)
        return len(stripped) < 3

    def _flush_buffer(self):
        """将累积缓冲区的内容合并为一条消息并发射"""
        if not self._answer_buffer:
            return
        
        # 合并所有累积的行
        full_content = "\n".join(self._answer_buffer).strip()
        self._answer_buffer.clear()
        self._in_answer_block = False
        
        if not full_content or len(full_content) < 3:
            return
        
        # 【内容级保护】去掉 emoji 和特殊符号后，如果只剩下 CrewAI 元数据则不发射
        stripped_text = re.sub(r'[✅❌🤖🚀📋⚡💬🧠■□▪▫●○◆◇\s]', '', full_content).strip()
        noise_words = {"Agent", "AgentStarted", "AgentCompleted", "TaskCompleted", 
                       "PASS", "FAIL", "FinalAnswer", "WorkingAgent"}
        if stripped_text in noise_words or not stripped_text:
            print(f"[TRACE] _flush_buffer: BLOCKED noise content: {repr(full_content[:80])}")
            return
        
        # 精确匹配去重（使用内容哈希）
        content_hash = hash(full_content)
        if content_hash in self._seen_messages:
            return
        self._seen_messages.add(content_hash)
        
        role = self._current_role
        
        # 触发打字指示器
        proxy = getattr(self, role.lower(), None)
        if proxy:
            proxy.typing_started.emit()
        
        # 发射完整消息
        print(f"[EMIT] role={role} | len={len(full_content)} | content={repr(full_content[:100])}")
        self.agent_response.emit(role, full_content)

    def _on_thought_stream(self, text: str):
        """处理 CrewAI 的逐行输出，使用块级累积策略。
        
        策略：
        1. 检测 "Agent Final Answer" 等块开始标记 → 开始累积
        2. 在累积模式下，将清理后的内容行追加到缓冲区
        3. 检测块结束标记（新的 Agent 块、装饰框结尾）→ flush 缓冲区
        4. 非 Final Answer 的行（如 Thought/Action）直接忽略
        """
        # 0. 解码 Unicode 转义
        processed = text
        if "\\u" in processed:
            try:
                import codecs
                processed = codecs.decode(processed, 'unicode_escape')
            except Exception:
                pass
        
        raw = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', processed)  # 只去 ANSI，保留框格用于逻辑判断
        cleaned = self._clean_line(processed)
        
        if not cleaned and not raw.strip():
            return
        
        # ===== 1. 检测角色切换（Agent: xxx） =====
        detected_role = self._detect_role(cleaned)
        if detected_role:
            # 如果正在累积前一个角色的回答，先 flush
            if self._in_answer_block and self._answer_buffer:
                self._flush_buffer()
            self._current_role = detected_role
        
        # ===== 2. 检测 "Final Answer" 块开始 =====
        if "Final Answer" in cleaned or "Final Answer" in raw:
            # 如果已经有缓冲区内容，先 flush
            if self._in_answer_block and self._answer_buffer:
                self._flush_buffer()
            self._in_answer_block = True
            # "Final Answer:" 本身不是内容，跳过
            fa_content = re.sub(r'Final\s*Answer\s*:?\s*', '', cleaned).strip()
            if fa_content and len(fa_content) > 3:
                self._answer_buffer.append(fa_content)
            return
        
        # ===== 3. 如果正在累积模式 =====
        if self._in_answer_block:
            # 检测块结束信号
            # - 新的任务开始 (Working Agent, Crew Execution, etc.)
            # - Human Feedback Required
            end_signals = ["Working Agent:", "Crew Execution", "Human Feedback Required", 
                           "Provide feedback", "Task Assignment",
                           "Task Completed", "Task Completion", "Task Output",
                           "Agent Completed", "## Agent:"]
            if any(sig in raw for sig in end_signals):
                self._flush_buffer()
                return
            
            # 跳过纯装饰框边界线
            if self._is_box_border(raw):
                return
            
            # 跳过空行
            if not cleaned:
                return
            
            # 跳过纯标签行（Agent: xxx, Final Answer:, 任务元数据 等）
            skip_labels = ["Agent:", "Agent", "Final Answer:", "Expected Output:", "Task Description:",
                          "Task Completed", "Task Completion", "Name:", "User Request:",
                          "Task Output", "## Agent", "Working Agent", "Agent Started"]
            # 精确匹配：纯 "Agent" 或带 emoji 的变体
            if any(cleaned.startswith(label) for label in skip_labels):
                return
            if re.match(r'^[\s✅🤖■]*Agent[:\s]*$', cleaned):
                return
            
            # 有效内容行 → 追加到缓冲区
            self._answer_buffer.append(cleaned)
            return
        
        # ===== 4. 非累积模式：检测是否应该开始累积 =====
        # 如果是 "Agent" 相关标识行，跳过（仅用于角色检测）
        if re.match(r'^[\s✅🤖■]*Agent[:\s]*', cleaned):
            return
        
        # 跳过 CrewAI 内部思考标签
        skip_tags = ["Thought:", "Action:", "Action Input:", "Observation:", 
                     "Expected Output:", "I need to", "Using tool:", "Tool:",
                     "[DEBUG]", "[TRACE]", "[ERROR]"]
        if any(cleaned.lower().startswith(tag.lower()) for tag in skip_tags):
            return
        
        # 跳过装饰框行
        if self._is_box_border(raw):
            return
        
        # 跳过短无意义内容
        if len(cleaned) < 10:
            return

    def _get_human_input(self) -> str:
        """Called by CrewAI when a task needs human intervention."""
        # 先 flush 任何待发送的内容
        self._flush_buffer()
        
        self.agent_response.emit("System", "🔔 Agent 正在等待您的确认，请在 War Room 输入您的指令...")
        self.state_changed.emit("AWAITING_INPUT", "等待用户确认...")
        
        try:
            return self._input_queue.get(block=True, timeout=300)
        except queue.Empty:
            return "请继续执行。"

    def handle_user_intervention(self, text: str):
        """Called when user sends text via the WarRoomPanel input bar."""
        print(f"[DEBUG] CrewManager received intervention: {text}")
        self._input_queue.put(text)

    def _on_mission_complete(self, result: str):
        # flush 最后的缓冲区
        self._flush_buffer()
        self.agent_response.emit("System", "✅ 任务已完成。")
        self.workflow_completed.emit()
