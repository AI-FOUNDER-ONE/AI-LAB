"""
main.py - AI-Lab-Commander 主入口
=================================
QMainWindow 主窗口，组装所有 UI 面板并连接信号与槽。

布局结构:
  ┌─────────────┬──────────────┬──────────────┐
  │  Bridge     │  War Room    │ Execution    │
  │  (CKO对话)   │ (博弈直播)    │  (代码/日志)  │
  │             │              │              │
  ├─────────────┴──────────────┴──────────────┤
  │  Timeline (议程时间轴)                       │
  └───────────────────────────────────────────┘

安全性审计:
  ✅ API 密钥不在此文件中出现
  ✅ 所有 API 调用通过 Orchestrator 在后台线程执行
  ✅ 异常处理覆盖信号连接和 UI 操作
"""

import re
import sys
import traceback
import os
import logging

# [FIX] Windows 平台强制 UTF-8 编码，防止 emoji 打印报错
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 禁用 CrewAI Telemetry 防止 SSL 报错 (必须在导入 crewai 前设置)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter,
    QVBoxLayout, QWidget, QMenuBar, QMenu,
    QFrame, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QAction

from config import APP_TITLE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, AppState
# TODO: migrate to UnifiedOrchestrator
from core.orchestrator import Orchestrator
from core.logger import setup_logging, logger
# TODO: migrate to UnifiedOrchestrator
from core.orchestrator_dynamic import OrchestratorDynamic
from core.unified_orchestrator import UnifiedOrchestrator
from ui.bridge_panel import BridgePanel
from ui.warroom_panel import WarRoomPanel
from ui.execution_panel import ExecutionPanel
from ui.timeline_panel import TimelinePanel
from ui.styles import (
    get_main_stylesheet, get_navbar_style, get_button_style,
    get_panel_style, get_input_style, COLORS
)

class MainWindow(QMainWindow):
    """AI-Lab-Commander 主窗口"""

    def __init__(self):
        super().__init__()

        # Use global logger
        self.logger = logger
        self.logger.info("AI-Lab-Commander MainWindow initialized")

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # 应用全局暗色主题样式
        self.setStyleSheet(get_main_stylesheet())

        # ------ 创建统一编排引擎 ------
        self.orchestrator = UnifiedOrchestrator(self)

        # ------ 创建 UI 面板 ------
        self.bridge_panel = BridgePanel(self)
        self.warroom_panel = WarRoomPanel(self)
        self.execution_panel = ExecutionPanel(self)
        self.timeline_panel = TimelinePanel(self)

        # ------ Apply High-Fidelity Shadows ------
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        from PyQt6.QtGui import QColor

        def apply_shadow(widget):
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setXOffset(0)
            shadow.setYOffset(4)
            shadow.setColor(QColor(0, 0, 0, 15)) # 0.06 alpha
            widget.setGraphicsEffect(shadow)

        # Apply to main 3 panels
        apply_shadow(self.bridge_panel)
        apply_shadow(self.warroom_panel)
        apply_shadow(self.execution_panel)

        # ------ 搭建布局 ------
        self._init_layout()

        # ------ 创建菜单栏 ------
        self._init_menu_bar()

        # ------ 创建状态栏 ------
        self._init_status_bar()

        # ------ 连接信号与槽 ------
        self._connect_signals()

        # 应用退出时强制落盘会话数据（SessionStore 增量写入防抖后需在退出时 flush）
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._flush_session_store)

        # ------ 定时刷新左侧 AI 在线状态（每 20 秒，全阶段一致）------
        self._status_refresh_timer = QTimer(self)
        self._status_refresh_timer.timeout.connect(self._refresh_roles_online_from_state)
        self._status_refresh_timer.start(20_000)  # 20 秒

    def _flush_session_store(self):
        """应用退出时将会话未落盘改动写入磁盘"""
        try:
            self.orchestrator.session_store.flush()
        except Exception:
            pass

    def _init_layout(self):
        """初始化主窗口三列 + 底部时间轴布局"""
        # 中央容器（全局底层极暗灰黑 #141414）
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {COLORS['bg_base']};")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 16) # Top 0 for Navbar
        main_layout.setSpacing(0)

        # 1. Navbar
        navbar = self._init_navbar()
        main_layout.addWidget(navbar)
        
        # 2. Main Content Area (with margins)
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(16, 16, 16, 0)
        content_layout.setSpacing(16)
        
        # ------ 三列分割器（Cursor 风格：1px 细线，无粗分割条）------
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background: transparent; width: 1px; max-width: 1px; }
        """)

        # 左: 桥接区（仅角色列表） 中: 作战室（主聊区） 右: 执行面板
        self.splitter.addWidget(self.bridge_panel)
        self.splitter.addWidget(self.warroom_panel)
        self.splitter.addWidget(self.execution_panel)

        # 参照微信群聊比例：左侧窄、中间宽、右侧窄
        self.bridge_panel.setMinimumWidth(160)
        self.warroom_panel.setMinimumWidth(420)
        self.execution_panel.setMinimumWidth(200)
        self.splitter.setSizes([200, 780, 220])

        self.splitter.setStretchFactor(0, 0)   # 桥接区尽量窄
        self.splitter.setStretchFactor(1, 1)   # 作战室占满剩余
        self.splitter.setStretchFactor(2, 0)   # 执行面板固定感
        self.splitter.setChildrenCollapsible(False)

        content_layout.addWidget(self.splitter, stretch=1)
        
        main_layout.addWidget(content_container, stretch=1)

        # ------ 底部时间轴 ------
        content_layout.addWidget(self.timeline_panel)

    def _init_menu_bar(self):
        """初始化菜单栏 (Hidden, replaced by Navbar)"""
        # Hide default menu bar
        self.menuBar().hide()

    def _init_navbar(self):
        """GitHub Style Header"""
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(48)
        navbar.setStyleSheet(get_navbar_style())
        
        layout = QHBoxLayout(navbar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        
        # Logo / Title
        logo = QLabel("AI-Lab")
        logo.setObjectName("nav_title")
        layout.addWidget(logo)
        
        layout.addStretch()
        
        # 确认立项按钮（需求打磨完成后启用）
        self.btn_confirm_nav = QPushButton("确认立项")
        self.btn_confirm_nav.setStyleSheet(get_button_style(variant="success"))
        self.btn_confirm_nav.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm_nav.setFixedSize(130, 28)
        self.btn_confirm_nav.setEnabled(False)  # Phase 1 完成前禁用
        layout.addWidget(self.btn_confirm_nav)
        
        # 图标按钮
        btn_new = QPushButton("＋")
        btn_new.setToolTip("新会话")
        btn_new.clicked.connect(self._on_new_session)
        btn_new.setFixedSize(28, 28)
        btn_new.setStyleSheet(get_button_style(variant="icon"))
        layout.addWidget(btn_new)
        
        return navbar

    def _init_status_bar(self):
        """初始化状态栏"""
        self.statusBar().showMessage("💡 就绪 — 空闲状态")
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                border: none;
                font-size: 12px;
                padding: 4px;
            }}
            QStatusBar QLabel {{
                background: transparent;
                border: none;
            }}
        """)

    def _connect_signals(self):
        """连接所有信号与槽"""

        # ============================================================
        #  War Room 输入 → 统一对话入口（需求/干预均由作战室发送）
        # ============================================================
        self.warroom_panel.user_intervention_sent.connect(self._on_warroom_message_sent)
        self.warroom_panel.rework_requested.connect(self._on_rework_requested)
        self.warroom_panel.file_linked.connect(self.execution_panel.add_reference_doc)

        self.btn_confirm_nav.clicked.connect(self._on_confirm_project)

        # ============================================================
        #  Orchestrator → Bridge: CKO 回复
        # ============================================================
        self.orchestrator.agent_response.connect(
            self._dispatch_agent_response
        )

        # ============================================================
        #  Orchestrator → Timeline: 状态变更
        # ============================================================
        self.orchestrator.state_changed.connect(
            self._on_state_changed
        )

        # 初始在线状态：按当前阶段显示对应角色在线（避免启动后“全离线”）
        self._apply_roles_online_for_state(self.orchestrator.state_ctrl.current_state)

        # ============================================================
        #  Orchestrator → 错误处理
        # ============================================================
        self.orchestrator.error_occurred.connect(
            self._on_error
        )

        # ============================================================
        #  Orchestrator → 工作流完成
        # ============================================================
        self.orchestrator.workflow_completed.connect(
            self._on_workflow_completed
        )

        # ============================================================
        #  Agent 输入/结束 → Bridge 角色状态 + War Room 打字状态
        # ============================================================
        self.orchestrator.agent_typing.connect(self._on_agent_typing)
        debate_agents = [
            (self.orchestrator.agents_map["PM"], "PM"),
            (self.orchestrator.agents_map["Arch"], "Arch"),
            (self.orchestrator.agents_map["Designer"], "Designer"),
            (self.orchestrator.agents_map["CKO"], "CKO"),
            (self.orchestrator.agents_map["Coder"], "Coder"),
            (self.orchestrator.agents_map["Validator"], "Validator"),
        ]
        for agent_proxy, role_id in debate_agents:
            agent_proxy.typing_started.connect(
                lambda r=role_id: self.warroom_panel.set_typing_status(r, True)
            )
            agent_proxy.typing_finished.connect(
                lambda r=role_id: self.warroom_panel.set_typing_status(r, False)
            )

        # (Removed duplicate user_intervention_sent connection)

        # ============================================================
        #  Timeline → War Room: 过滤消息
        # ============================================================
        self.timeline_panel.node_clicked.connect(
            self.warroom_panel.filter_messages
        )

        # ============================================================
        #  Orchestrator → 流式输出处理
        # ============================================================
        self.orchestrator.agent_stream_chunk.connect(
            self._on_agent_stream_chunk
        )

    # ==================================================================
    #  信号处理槽函数
    # ==================================================================

    def _extract_and_save_code(self, content: str, agent_name: str) -> None:
        """从回复内容中提取 Markdown 代码块并写入 ExecutionPanel（支持多语言、多个代码块）。"""
        EXTENSION_MAP = {
            "python": "generated.py",
            "py": "generated.py",
            "javascript": "generated.js",
            "js": "generated.js",
            "typescript": "generated.ts",
            "ts": "generated.ts",
            "java": "Generated.java",
            "cpp": "generated.cpp",
            "c++": "generated.cpp",
            "go": "generated.go",
            "rust": "generated.rs",
            "html": "generated.html",
            "css": "generated.css",
            "markdown": "generated.md",
            "md": "generated.md",
            "json": "generated.json",
        }
        code_matches = re.findall(r"```([a-zA-Z]*)\n(.*?)```", content, re.DOTALL)
        for lang, code in code_matches:
            code = code.strip()
            filename = EXTENSION_MAP.get((lang or "").lower(), "generated.py")
            self.execution_panel.set_code(code, filename=filename)

    def _check_state_transition(self, content: str, agent_name: str) -> None:
        """检查回复内容是否触发状态转换（预留扩展点，当前由 Orchestrator 侧驱动状态）。"""
        pass

    def _update_ui_for_response(self, agent_name: str, content: str) -> None:
        """根据角色更新 War Room、ExecutionPanel、Bridge 状态等 UI。"""
        current_state = self.orchestrator.state_ctrl.current_state
        if agent_name not in ("Commander", "系统"):
            self.bridge_panel.set_role_status(agent_name, "idle")
        if agent_name == "Commander":
            self.warroom_panel.append_message(agent_name, content, state_id=current_state)
            return
        if agent_name == "CKO":
            self.warroom_panel.append_message(agent_name, content, state_id=current_state)
            self.btn_confirm_nav.setEnabled(True)
        elif agent_name == "系统":
            self.warroom_panel.append_system_event(content)
        else:
            self.warroom_panel.append_message(agent_name, content, state_id=current_state)

        if "<SYS_LOG:SUCCESS>" in content:
            log_content = content.replace("<SYS_LOG:SUCCESS>", "").strip()
            self.execution_panel.append_log(log_content, level="success")
        elif "<SYS_LOG:ERROR>" in content:
            log_content = content.replace("<SYS_LOG:ERROR>", "").strip()
            self.execution_panel.append_log(log_content, level="error")
        elif "<SYS_LOG:INFO>" in content:
            log_content = content.replace("<SYS_LOG:INFO>", "").strip()
            self.execution_panel.append_log(log_content, level="info")
        elif "<SYS_LOG:WARNING>" in content:
            log_content = content.replace("<SYS_LOG:WARNING>", "").strip()
            self.execution_panel.append_log(log_content, level="warning")

        if agent_name == "Validator":
            if "✅" in content or "验证通过" in content or "测试通过" in content:
                self.execution_panel.append_log(content, level="success")
            elif "❌" in content or "验证失败" in content or "测试失败" in content:
                self.execution_panel.append_log(content, level="error")
            else:
                self.execution_panel.append_log(content, level="info")

    def _log_agent_response(self, agent_name: str, content: str) -> None:
        """写入会议日志。当前由 Orchestrator 在发出 agent_response 前已写入 session_store，此处为扩展点。"""
        pass

    def _dispatch_agent_response(self, role: str, content: str) -> None:
        """根据角色分发 Agent 回复到对应的 UI 面板；对话仅在 War Room，Bridge 仅展示角色状态。"""
        self._update_ui_for_response(role, content)
        if role == "Commander":
            return
        self._extract_and_save_code(content, role)
        self._check_state_transition(content, role)
        self._log_agent_response(role, content)

    def _on_agent_typing(self, role: str, is_typing: bool):
        """更新 Bridge 角色状态"""
        self.bridge_panel.set_role_status(role, "typing" if is_typing else "idle")

    def _on_agent_stream_chunk(self, role: str, chunk: str):
        """所有角色流式输出均在 War Room 展示（打字机仅非折叠部分）"""
        self.warroom_panel.append_stream_chunk(role, chunk)
        self.bridge_panel.set_role_status(role, "speaking")

    def _on_warroom_message_sent(self, content: str):
        """作战室发送的消息：需求阶段走 CKO，其余阶段走用户干预"""
        state = self.orchestrator.state_ctrl.current_state
        if state in (AppState.IDLE, AppState.GROUNDING):
            self.orchestrator.send_to_cko(content)
        else:
            self.orchestrator.handle_user_intervention(content)

    def _on_rework_requested(self, feedback: str):
        """用户提交「哪里不满意」并请求重新评审方案"""
        self.warroom_panel.set_rework_visible(False)
        self.orchestrator.request_rework(feedback)

    def _on_confirm_project(self):
        """用户点击确认立项按钮"""
        self.btn_confirm_nav.setEnabled(False)
        self.btn_confirm_nav.setText("处理中…")
        self.orchestrator.confirm_project()

    def _roles_online_for_state(self, state_id: str):
        """根据当前阶段返回应在左侧显示为「在线」的角色列表（与状态机一致）"""
        if state_id == AppState.GROUNDING:
            return ["CKO"]
        if state_id == AppState.DEBATE:
            return ["PM", "Arch", "Designer"]
        if state_id == AppState.PRODUCTION:
            return ["Coder"]
        if state_id == AppState.VERIFICATION:
            return ["Validator"]
        if state_id == "DESIGNING":
            return ["Arch", "Coder", "PM"]
        if state_id == "AWAITING_CONFIRM":
            return ["CKO", "PM"]
        if state_id == AppState.IDLE:
            # 空闲时下一阶段为需求打磨，CKO 作为首轮参与角色显示为在线
            return ["CKO"]
        # DELIVERY / COMPLETED 等：显示为空
        return []

    def _apply_roles_online_for_state(self, state_id: str):
        """根据状态更新左侧成员列表的在线指示灯"""
        self.bridge_panel.set_roles_online(self._roles_online_for_state(state_id))

    def _refresh_roles_online_from_state(self):
        """定时回调：按当前阶段刷新左侧 AI 在线状态（每 20 秒，全阶段实时一致）"""
        try:
            state = self.orchestrator.state_ctrl.current_state
            self._apply_roles_online_for_state(state)
        except Exception:
            pass

    def _on_state_changed(self, state_id: str, description: str):
        """状态变更时更新 UI

        Args:
            state_id: 旧状态（信号第一参数）
            description: 新状态（信号第二参数，用于时间轴与在线角色）
        """
        # 更新时间轴（使用新状态）
        self.timeline_panel.set_current_state(description)
        
        # 只要状态变更，War Room 自动显示全部
        self.warroom_panel.filter_messages("ALL")

        # 任务完成时显示「不满意→重新评审」区，否则隐藏
        self.warroom_panel.set_rework_visible(description == AppState.COMPLETED)

        # 更新状态栏
        self.statusBar().showMessage(f"🔄 {description}")

        # 按新状态更新左侧成员列表的在线指示灯
        self._apply_roles_online_for_state(description)

        # ===== Phase 1 完成 → 启用 Confirm 按钮 =====
        if description == AppState.GROUNDING:
            self.btn_confirm_nav.setEnabled(True)
            self.btn_confirm_nav.setText("✅ 确认立项")
            self.btn_confirm_nav.setStyleSheet(get_button_style(variant="success"))
        elif description == AppState.DEBATE:
            self.warroom_panel.append_system_event("🚀 项目已确认，设计阶段开始")
        elif description == AppState.COMPLETED:
            self.execution_panel.set_status("✅ 任务完成!")

    def _on_error(self, error_msg: str):
        """错误处理

        Args:
            error_msg: 错误消息
        """
        self.statusBar().showMessage(f"⚠️ 错误: {error_msg}")
        self.execution_panel.append_log(error_msg, level="error")

    def _on_workflow_completed(self):
        """工作流完成处理"""
        self.statusBar().showMessage("🏁 任务完成!")
        self.warroom_panel.append_system_event("🏁 全部任务已完成！")

    def _on_nav_confirm_clicked(self):
        """Handle projects confirmation from navbar"""
        self.btn_confirm_nav.setEnabled(False)
        self.bridge_panel._on_confirm()

    def _on_new_session(self):
        """新建会话"""
        self.orchestrator.new_session()

        # 清空所有面板
        self.bridge_panel.set_status("💡 状态：等待输入需求...")
        self.warroom_panel.clear_display()
        self.bridge_panel.set_roles_online([])
        self.execution_panel.clear_code()
        self.execution_panel.clear_log()
        self.timeline_panel.reset()
        self.statusBar().showMessage("💡 就绪 — 新会话已创建")

    def _on_stop_all(self):
        """停止所有任务"""
        self.orchestrator.stop_all()
        self.statusBar().showMessage("🛑 所有任务已中止")

    def _on_about(self):
        """关于对话框"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于 AI-Lab-Commander",
            "<h2>AI-Lab-Commander</h2>"
            "<p>AI 多角色协作平台 v0.1</p>"
            "<p>基于 PyQt6 构建的桌面应用</p>"
            "<hr>"
            "<p><b>角色团队：</b></p>"
            "<ul>"
            "<li>🧠 CKO · 首席知识官 (Gemini)</li>"
            "<li>📋 PM · 项目经理 (GPT-4o)</li>"
            "<li>🏗️ Arch · 架构师 (Claude)</li>"
            "<li>🎨 Designer · 设计师 (DeepSeek)</li>"
            "<li>💻 Coder · 程序员 (GLM)</li>"
            "<li>🧪 Validator · 验证官 (DeepSeek)</li>"
            "</ul>"
        )


def main():
    """应用主入口"""
    # Initialize logging system
    logger = setup_logging(log_level=logging.INFO, log_to_file=True)
    logger.info("Starting AI-Lab-Commander application")

    # 配置全局异常捕获
    def exception_hook(exctype, value, traceback_obj):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        error_msg = f"[{timestamp}] CRITICAL ERROR:\n"
        error_msg += "".join(traceback.format_exception(exctype, value, traceback_obj))

        # 写入日志文件
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(error_msg + "\n" + "="*80 + "\n")

        # 尝试使用logger记录（如果可用）
        try:
            logger.error(f"Unhandled exception: {error_msg}")
        except:
            # logger可能不可用，保留原始print
            print(error_msg)

        # 尝试在主线程显示错误弹窗（如果 QApplication 已创建）
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            from PyQt6.QtCore import QTimer
            app = QApplication.instance()
            if app is not None:
                # 使用 QTimer.singleShot 确保在主线程执行
                def show_error():
                    QMessageBox.critical(
                        None,
                        "严重错误",
                        "发生严重错误，已记录到日志。\n\n"
                        "请检查 crash.log 文件获取详细信息。"
                    )
                QTimer.singleShot(0, show_error)
        except Exception as e:
            # 弹窗失败不影响错误记录
            print(f"Failed to show error dialog: {e}")

        sys.__excepthook__(exctype, value, traceback_obj)

    sys.excepthook = exception_hook

    app = QApplication(sys.argv)

    # 设置全局字体
    font = QFont("Inter", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
