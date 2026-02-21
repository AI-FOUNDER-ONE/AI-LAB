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

import sys
import traceback
import os
import logging

# [FIX] Windows 平台强制 UTF-8 编码，防止 emoji 打印报错
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# 禁用 CrewAI Telemetry 防止 SSL 报错 (必须在导入 crewai 前设置)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter,
    QVBoxLayout, QWidget, QMenuBar, QMenu,
    QFrame, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QAction

from config import APP_TITLE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
from core.orchestrator import Orchestrator
from core.logger import setup_logging, logger
from core.orchestrator_dynamic import OrchestratorDynamic
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

        # ------ 创建动态编排引擎 ------
        self.orchestrator = OrchestratorDynamic(self)

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

    def _init_layout(self):
        """初始化主窗口三列 + 底部时间轴布局"""
        # 中央容器
        central_widget = QWidget()
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
        
        # ------ 三列分割器 ------
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(16) # 增加列间距

        # 左: Bridge 面板（CKO 对话区）
        self.splitter.addWidget(self.bridge_panel)

        # 中: War Room 面板（博弈直播间）
        self.splitter.addWidget(self.warroom_panel)

        # 右: Execution 面板（代码 + 日志）
        self.splitter.addWidget(self.execution_panel)

        # 设置初始比例 (War Room Focus: 20% / 60% / 20%)
        # Assuming min width ~1200px
        self.splitter.setSizes([240, 720, 240])

        # [FIX] 固定拉伸因子，防止文件名等内容撧开面板比例
        # War Room (index=1) 获得最大拉伸权重
        self.splitter.setStretchFactor(0, 1)   # Bridge: 低拉伸
        self.splitter.setStretchFactor(1, 3)   # War Room: 高拉伸
        self.splitter.setStretchFactor(2, 1)   # Execution: 低拉伸

        # [FIX] 禁止子面板按内容大小拉伸，强制使用设定比例
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
        
        # [NEW] GitHub Green Confirm Button (Top Right)
        # 连接到 orchestrator.confirm_project 触发 Phase 2
        self.btn_confirm_nav = QPushButton("Confirm Project")
        self.btn_confirm_nav.setStyleSheet(get_button_style(variant="success"))
        self.btn_confirm_nav.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm_nav.setFixedSize(130, 28)
        self.btn_confirm_nav.setEnabled(False)  # Phase 1 完成前禁用
        layout.addWidget(self.btn_confirm_nav)
        
        # Icon Buttons
        btn_new = QPushButton("＋")
        btn_new.setToolTip("New Session")
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
                border-top: 1px solid {COLORS['border']};
                font-size: 12px;
                padding: 4px;
            }}
        """)

    def _connect_signals(self):
        """连接所有信号与槽"""

        # ============================================================
        #  Bridge → Orchestrator: 用户消息 → CrewAI
        # ============================================================
        self.bridge_panel.message_sent.connect(
            self.orchestrator.start_mission
        )

        # ============================================================
        #  Confirm Button → Orchestrator: 确认项目 → Phase 2 启动
        # ============================================================
        self.btn_confirm_nav.clicked.connect(
            self._on_confirm_project
        )
        self.warroom_panel.user_intervention_sent.connect(
            self.orchestrator.handle_user_intervention
        )
        
        # ============================================================
        #  Bridge → Execution: 文件链接
        # ============================================================
        self.bridge_panel.file_linked.connect(
            self.execution_panel.add_reference_doc
        )

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
        #  CKO Agent 输入状态 → Bridge 面板
        # ============================================================
        self.orchestrator.cko.typing_started.connect(
            lambda: self.bridge_panel.set_ke_typing(True)
        )
        self.orchestrator.cko.typing_finished.connect(
            lambda: self.bridge_panel.set_ke_typing(False)
        )

        # ============================================================
        #  Debate Agent 输入状态 → War Room 面板
        # ============================================================
        # Use a list of (proxy_agent, role_name) tuples for explicit mapping
        debate_agents = [
            (self.orchestrator.pm, "PM"),
            (self.orchestrator.arch, "Arch"),
            (self.orchestrator.designer, "Designer")
        ]
        
        for agent_proxy, role_id in debate_agents:
            # Fix: AgentProxy objects emit (is_typing: bool)
            agent_proxy.typing_started.connect(
                lambda role=role_id: self.warroom_panel.set_typing_status(role, True)
            )
            agent_proxy.typing_finished.connect(
                lambda role=role_id: self.warroom_panel.set_typing_status(role, False)
            )

        # (Removed duplicate user_intervention_sent connection)

        # ============================================================
        #  Timeline → War Room: 过滤消息
        # ============================================================
        self.timeline_panel.node_clicked.connect(
            self.warroom_panel.filter_messages
        )

    # ==================================================================
    #  信号处理槽函数
    # ==================================================================

    def _dispatch_agent_response(self, role: str, content: str):
        """根据角色分发 Agent 回复到对应的 UI 面板（重构版 - 解耦角色硬编码）

        Args:
            role: Agent 角色标识
            content: 回复内容
        """
        # 获取当前状态 ID，用于标记消息
        current_state = self.orchestrator.state_ctrl.current_state

        # 1. Commander 消息直接写入 War Room 并返回
        if role == "Commander":
            self.warroom_panel.append_message(role, content, state_id=current_state)
            return

        # 2. CKO（原 KE）特殊处理：Bridge 面板 + War Room
        if role == "CKO":
            # 1. 始终显示在 Bridge 面板 (确保立项主要流程完整)
            self.bridge_panel.append_ke_response(content)
            # 2. 同时显示在 War Room (作为公屏回应)
            self.warroom_panel.append_message(role, content, state_id=current_state)
            # 3. Enable Confirm Button in Navbar
            self.btn_confirm_nav.setEnabled(True)
            # 后续处理（代码提取和日志标签）仍然执行
        # 3. 系统消息特殊处理
        elif role == "系统":
            self.warroom_panel.append_system_event(content)
            # 后续处理（代码提取和日志标签）仍然执行
        else:
            # 4. 所有其他角色消息统一写入 War Room
            self.warroom_panel.append_message(role, content, state_id=current_state)

        # 5. 增强正则提取所有语言的代码块（支持多语言）
        import re
        code_match = re.search(r"```[a-zA-Z]*\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            # 默认文件名为 generated.py，可根据语言后缀调整
            filename = "generated.py"
            # 可选：提取语言标记
            lang_match = re.search(r"```([a-zA-Z]+)", content)
            if lang_match:
                lang = lang_match.group(1).lower()
                if lang in ["python", "py"]:
                    filename = "generated.py"
                elif lang in ["javascript", "js"]:
                    filename = "generated.js"
                elif lang in ["typescript", "ts"]:
                    filename = "generated.ts"
                elif lang in ["java"]:
                    filename = "Generated.java"
                elif lang in ["cpp", "c++"]:
                    filename = "generated.cpp"
                elif lang in ["go"]:
                    filename = "generated.go"
                elif lang in ["rust"]:
                    filename = "generated.rs"
                elif lang in ["html"]:
                    filename = "generated.html"
                elif lang in ["css"]:
                    filename = "generated.css"
                elif lang in ["markdown", "md"]:
                    filename = "generated.md"
                elif lang in ["json"]:
                    filename = "generated.json"
            self.execution_panel.set_code(code, filename=filename)

        # 6. 结构化系统日志标签处理
        if "<SYS_LOG:SUCCESS>" in content:
            # 提取标签后的内容（可选）
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

        # 7. 兼容旧版 Tester 表情符号检测（保留向后兼容）
        if role == "Tester":
            if "✅" in content or "测试通过" in content:
                self.execution_panel.append_log(content, level="success")
            elif "❌" in content or "测试失败" in content:
                self.execution_panel.append_log(content, level="error")
            else:
                self.execution_panel.append_log(content, level="info")

    def _on_confirm_project(self):
        """用户点击 Confirm Project 按钮"""
        self.btn_confirm_nav.setEnabled(False)  # 防止重复点击
        self.btn_confirm_nav.setText("Processing...")
        self.orchestrator.confirm_project()

    def _on_state_changed(self, state_id: str, description: str):
        """状态变更时更新 UI

        Args:
            state_id: 状态标识 (如 GROUNDING, AWAITING_CONFIRM, DESIGNING 等)
            description: 状态描述文本
        """
        # 更新时间轴
        self.timeline_panel.set_current_state(state_id)
        
        # 只要状态变更，War Room 自动显示全部
        self.warroom_panel.filter_messages("ALL")

        # 更新状态栏
        self.statusBar().showMessage(f"🔄 {description}")

        # ===== Phase 1 完成 → 启用 Confirm 按钮 =====
        if state_id == "AWAITING_CONFIRM":
            self.btn_confirm_nav.setEnabled(True)
            self.btn_confirm_nav.setText("✅ Confirm Project")
            self.btn_confirm_nav.setStyleSheet(get_button_style(variant="success"))
        elif state_id == "DESIGNING":
            self.warroom_panel.set_active_roles(["Arch", "Coder", "PM"])
            self.warroom_panel.append_system_event("🚀 项目已确认，设计阶段开始")
        elif state_id == "COMPLETED":
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
        self.warroom_panel.set_active_roles([])
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
            "<li>🧪 Tester · 测试员 (Claude)</li>"
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
