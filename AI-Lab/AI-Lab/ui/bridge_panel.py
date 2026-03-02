"""
bridge_panel.py - CKO 深度沟通区 (The Bridge)
================================================
左侧面板：用户与 CKO (Gemini) 的需求打磨对话区。
包含对话流显示、输入框、发送按钮和"确认立项"按钮。
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QSizePolicy, QFileDialog,
    QScrollArea, QWidget, QGridLayout
)
import os
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from ui.styles import COLORS, get_panel_style, get_header_style, get_button_style, get_audit_stamp_style, get_input_style
from ui.warroom_panel import CollapsibleMessage, SystemEventLabel
from config import AGENT_PROFILES


class BridgePanel(QFrame):
    """CKO 深度沟通区面板

    信号:
        message_sent: 用户发送消息时触发, 携带消息文本
        project_confirmed: 用户点击"确认立项"时触发
    """

    # ---------- 自定义信号 ----------
    message_sent = pyqtSignal(str)           # 用户发送消息
    project_confirmed = pyqtSignal()          # 确认立项
    file_linked = pyqtSignal(str)           # [NEW] 文件链接信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.projectId = f"PROJ-{hash(self) % 10000:04d}"
        self._is_sending = False  # 防止重复发送标志
        self._init_ui()

    def _init_ui(self):
        """Standard GitHub Style UI"""
        # Ensure Qt is accessible in this scope
        from PyQt6.QtCore import Qt
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. Header (Small Label)
        self.header_label = QLabel("BRIDGE")
        self.header_label.setStyleSheet(get_header_style())
        layout.addWidget(self.header_label)

        # 2. Message Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.message_container = QWidget()
        self.message_container.setStyleSheet("background: transparent;")
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(12)
        self.message_layout.addStretch()
        
        self.scroll_area.setWidget(self.message_container)
        layout.addWidget(self.scroll_area)

        # 3. Input Area (GitHub Style Compact Bar)
        # Force fixed height for the container as requested
        self.input_container = QFrame()
        self.input_container.setFixedHeight(60) 
        self.input_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(8, 4, 8, 4)
        input_layout.setSpacing(8)
        
        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Brief the CKO...")
        self.input_box.setStyleSheet("background: transparent; border: none; color: #C9D1D9;")
        input_layout.addWidget(self.input_box)
        
        # Send Button (Icon only)
        self.btn_send = QPushButton("→") 
        self.btn_send.setFixedSize(28, 28)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet(get_button_style(variant="icon"))
        self.btn_send.clicked.connect(self._on_send)
        input_layout.addWidget(self.btn_send)
        
        # [NEW] Attach Button (Clip Icon)
        self.btn_attach = QPushButton("📎")
        self.btn_attach.setFixedSize(28, 28)
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setToolTip("Attach Word Document")
        self.btn_attach.setStyleSheet(get_button_style(variant="icon"))
        self.btn_attach.clicked.connect(self._on_attach)
        input_layout.insertWidget(1, self.btn_attach) # Insert before input box or after? Let's put it left of input
        
        layout.addWidget(self.input_container)

        # Status Label (Muted)
        self.status_label = QLabel("Waiting for mission data...")
        self.status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
        # [FIX] 防止长文件名撧开面板宽度
        self.status_label.setWordWrap(False)
        self.status_label.setMaximumWidth(400)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(self.status_label)
        
        self.current_attachment = None

    def _on_attach(self):
        """Handle file attachment"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "",
            "All Supported (*.docx *.pdf *.txt *.md *.csv *.json);;"
            "Word Documents (*.docx);;"
            "PDF Files (*.pdf);;"
            "Text Files (*.txt *.md *.csv *.json);;"
            "All Files (*.*)"
        )
        if file_path:
            self.current_attachment = file_path
            filename = os.path.basename(file_path)
            # [FIX] 截断长文件名防止撧开面板比例
            display_name = filename if len(filename) <= 25 else filename[:22] + "..."
            self.status_label.setText(f"📎 Attached: {display_name}")
            self.input_box.setPlaceholderText(f"Ask CKO about {display_name}...")
            
            # Emit signal to update other panels
            self.file_linked.emit(file_path)

    def _on_send(self):
        """发送消息"""
        # 防止重复发送
        if self._is_sending:
            # print(f"[DEBUG] BridgePanel: 正在发送中，忽略重复调用")
            return

        self._is_sending = True
        try:
            content = self.input_box.toPlainText().strip()
            # print(f"[DEBUG] BridgePanel: _on_send called, content={repr(content)}, has_attachment={self.current_attachment is not None}")

            if not content and not self.current_attachment:
                # print(f"[DEBUG] BridgePanel: 空内容，返回")
                self._is_sending = False
                return

            # Prepend attachment path if exists
            context_msg = content
            if self.current_attachment:
                context_msg = f"[ATTACHMENT: {self.current_attachment}]\n{content}"
                self.current_attachment = None # Reset after sending
                self.status_label.setText("Waiting for mission data...")
                self.input_box.setPlaceholderText("Brief the CKO...")

            # print(f"[DEBUG] BridgePanel: Emitting message_sent signal with content: {context_msg[:100]}")
            self.message_sent.emit(context_msg)

            # 清空输入框
            self.input_box.clear()

            # 显示用户消息到UI
            print("[DEBUG] BridgePanel: Appending message to UI...")
            self._append_message("Commander", content, COLORS['bg_secondary'])
            self.btn_send.setEnabled(False)

            print(f"[DEBUG] BridgePanel: 发送完成")

        except Exception as e:
            print(f"[ERROR] BridgePanel: _on_send error: {e}")
            import traceback
            traceback.print_exc()
            self._is_sending = False
            raise
        finally:
            # 小延迟后重置发送标志，避免快速连续发送问题
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: setattr(self, '_is_sending', False)) 
        



    def _on_upload(self):
        """处理上传按钮点击"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Word 文档",
            "",
            "All Supported (*.docx *.pdf *.txt *.md *.csv *.json);;"
            "Word Documents (*.docx);;"
            "PDF Files (*.pdf);;"
            "Text Files (*.txt *.md *.csv *.json);;"
            "All Files (*.*)"
        )
        if file_path:
            self._current_file_path = file_path
            self.file_linked.emit(file_path) # Emit signal
            
            # Show processed text preview
            self._process_docx(file_path)

    def _process_docx(self, file_path: str):
        """解析文档并填入输入框（支持多格式）"""
        try:
            from tools.document_parser import parse_document
            result = parse_document(file_path)
            content = result.to_prompt_text()
            filename = os.path.basename(file_path)

            # 格式化插入内容
            insert_text = (
                f"【已加载文档: {filename}】\n"
                f"{'─' * 40}\n"
                f"{content}\n"
                f"{'─' * 40}\n"
                f"请根据上述文档内容，分析用户需求并提取关键任务点。\n"
            )

            # 追加到输入框（保留用户已有输入）
            current_text = self.input_box.toPlainText()
            if current_text:
                self.input_box.setText(current_text + "\n\n" + insert_text)
            else:
                self.input_box.setText(insert_text)

            self.status_label.setText(f"📎 已加载: {filename}")

        except ImportError:
            # 降级: 使用旧版 docx 解析
            self._process_docx_legacy(file_path)
        except Exception as e:
            self.status_label.setText(f"❌ 文档解析失败: {str(e)}")

    def _process_docx_legacy(self, file_path: str):
        """降级解析（仅 docx 纯文本提取）"""
        try:
            import docx as docx_lib
            doc = docx_lib.Document(file_path)
            full_text = [para.text for para in doc.paragraphs if para.text.strip()]
            content = "\n".join(full_text)
            filename = os.path.basename(file_path)

            insert_text = (
                f"【已加载文档: {filename}】\n"
                f"{'─' * 40}\n"
                f"{content}\n"
                f"{'─' * 40}\n"
                f"请根据上述文档内容，分析用户需求并提取关键任务点。\n"
            )

            current_text = self.input_box.toPlainText()
            if current_text:
                self.input_box.setText(current_text + "\n\n" + insert_text)
            else:
                self.input_box.setText(insert_text)

            self.status_label.setText(f"📎 已加载: {filename}")
        except Exception as e:
            self.status_label.setText(f"❌ 文档解析失败: {str(e)}")


    def _on_confirm(self):
        """处理确认立项按钮点击"""
        self._append_system_message("✅ 任务已确认立项！正在将 Mission Protocol 发送至团队...")
        self.project_confirmed.emit()

    def _append_message(self, role: str, content: str, color: str, is_user: bool = False):
        """向对话流中追加一条消息"""
        # 构造 Profile
        if is_user:
            profile = {"name": "User", "color": color, "icon": "👤"}
        else:
            # 尝试从配置获取，默认 CKO
            profile = AGENT_PROFILES.get("CKO", {"name": "CKO", "color": color, "icon": "🧠"})
            
        # 创建可折叠消息卡片
        msg_widget = CollapsibleMessage(role, content, profile)
        
        # 插到弹簧前面
        insert_pos = self.message_layout.count() - 1
        self.message_layout.insertWidget(insert_pos, msg_widget)
        
        # 滚动到底部
        self._scroll_to_bottom()

    def _append_system_message(self, content: str):
        """追加系统消息（居中显示）"""
        event_widget = SystemEventLabel(content)
        insert_pos = self.message_layout.count() - 1
        self.message_layout.insertWidget(insert_pos, event_widget)
        self._scroll_to_bottom()

    def append_ke_response(self, content: str):
        """追加 CKO 回复到对话流（外部调用接口）"""
        self._append_message("🧠 CKO", content, COLORS.get('accent_blue', '#58A6FF'))

    def set_status(self, text: str):
        """更新状态栏文字"""
        self.status_label.setText(text)

    def set_ke_typing(self, is_typing: bool):
        """设置 CKO 正在输入状态"""
        if is_typing:
            self.set_status("🧠 CKO 正在思考...")
            self.btn_send.setEnabled(False)
        else:
            self.set_status("💡 状态：等待输入需求...")
            self.btn_send.setEnabled(True)

    def keyPressEvent(self, event):
        """Ctrl+Enter 快捷发送"""
        if (event.key() == Qt.Key.Key_Return and
                event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self._on_send()
        else:
            super().keyPressEvent(event)

    def _scroll_to_bottom(self):
        """滚动到底部"""
        QTimer.singleShot(50, lambda: (
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
        ))
