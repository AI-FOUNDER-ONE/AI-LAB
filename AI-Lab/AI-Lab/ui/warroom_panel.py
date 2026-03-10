"""
warroom_panel.py - 作战室（多角色讨论区）
=========================================
中间面板：实时展示 PM、Arch、Designer 等角色讨论的聊天气泡。
支持角色头像、身份标注与「正在输入」状态。

消息展示：短消息直接展示；长方案缩略显示，可点击展开或折叠；系统事件居中标签。
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QSizePolicy, QScrollArea, QWidget,
    QPushButton, QSplitter, QComboBox, QFileDialog,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QTextCursor, QColor

from ui.styles import COLORS, get_panel_style, get_button_style, get_audit_stamp_style, get_thinking_style, get_header_style, get_input_style
from config import AGENT_PROFILES
import math

# ---------- 判断消息是否为"长内容"的阈值 ----------
COLLAPSE_LINE_THRESHOLD = 6      # 超过 6 行视为长内容
COLLAPSE_CHAR_THRESHOLD = 300    # 超过 300 字符视为长内容
SUMMARY_MAX_CHARS = 120          # 摘要最多显示 120 字符
# 流式时只显示「红框摘要」打字机，不显示蓝框折叠内容；结束后整体显示红框+蓝框
def _streaming_summary_only(buffer: str) -> str:
    """从流式 buffer 中取出仅用于展示的摘要（红框部分），不包含折叠的详细内容。"""
    if not buffer.strip():
        return ""
    # 已有双换行：只显示第一段（摘要），不显示后续
    if "\n\n" in buffer:
        intro = buffer.split("\n\n", 1)[0].strip()
        return intro
    # 已有 Markdown 标题：只显示标题前的内容
    lines = buffer.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(("# ", "## ", "### ")):
            return "\n".join(lines[:i]).strip() or buffer[:SUMMARY_MAX_CHARS]
    return buffer


class CollapsibleMessage(QWidget):
    """可折叠消息卡片 (Chat Bubble Style)
    
    Layout: [Avatar] [Bubble Container] (or reversed for user)
    """

    def __init__(self, role: str, content: str, profile: dict, parent=None):
        super().__init__(parent)
        self._is_expanded = False
        self._content = content
        self._role = role
        self._profile = profile
        self._init_ui()
        self._check_audit_stamp()

    def _init_ui(self):
        """构建气泡 UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 8, 0, 8)
        main_layout.setSpacing(12)

        is_user = (self._role == "Commander") or (self._role == "User")
        
        # 1. Avatar（Cursor 线稿风：灰底+浅灰图标，无彩色）
        avatar_char = "U" if is_user else self._profile.get("icon", "◆")
        avatar = QLabel(avatar_char)
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            background-color: {COLORS['bg_avatar']};
            color: {COLORS['text_primary']};
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            border: none;
        """)
        
        # 2. 内容区（无气泡：透明底、无边框，用户与 AI 统一）
        self.bubble_container = QFrame()
        bubble_layout = QVBoxLayout(self.bubble_container)
        bubble_layout.setContentsMargins(8, 4, 8, 4)
        bubble_layout.setSpacing(4)
        
        self.bubble_style_sheet = f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
            QLabel {{
                background-color: transparent;
                color: {COLORS['text_primary']};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }}
        """
        self.bubble_container.setStyleSheet(self.bubble_style_sheet)

        # 2.1 角色名
        if not is_user:
            name_label = QLabel(self._profile["name"])
            name_label.setStyleSheet(f"""
                color: {COLORS['text_tertiary']};
                font-size: 10px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                border: none;
                background: transparent;
                margin-bottom: 2px;
            """)
            bubble_layout.addWidget(name_label)

        # 2.2 正文
        intro, detail = self._split_content(self._content)
        if intro:
            intro_label = QLabel(intro)
            intro_label.setWordWrap(True)
            bubble_layout.addWidget(intro_label)

        # 2.3 详情折叠区
        if detail:
           self._init_detail_ui(detail, bubble_layout, is_user)

        # 主布局
        if is_user:
            main_layout.addStretch()
            main_layout.addWidget(self.bubble_container)
            main_layout.addWidget(avatar)
            main_layout.setAlignment(avatar, Qt.AlignmentFlag.AlignTop)
            main_layout.setAlignment(self.bubble_container, Qt.AlignmentFlag.AlignTop)
        else:
            main_layout.addWidget(avatar)
            main_layout.addWidget(self.bubble_container)
            main_layout.addStretch()
            main_layout.setAlignment(avatar, Qt.AlignmentFlag.AlignTop)
            main_layout.setAlignment(self.bubble_container, Qt.AlignmentFlag.AlignTop)
            
        self.bubble_container.setMaximumWidth(600)

    def _init_detail_ui(self, detail, layout, is_user):
        """初始化详情折叠区"""
        self.toggle_btn = QPushButton("📄 查看详细方案 ▼")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                margin-top: 8px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_avatar']};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_expand)
        layout.addWidget(self.toggle_btn)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setHtml(self._format_content(detail))
        self.detail_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                margin-top: 4px;
            }}
        """)
        doc_height = min(400, max(150, detail.count('\n') * 20 + 60))
        self.detail_text.setFixedHeight(doc_height)
        self.detail_text.setVisible(False)
        layout.addWidget(self.detail_text)

    def _check_audit_stamp(self):
        """检查是否需要加盖 CKO 审计印章"""
        if self._role != "CKO":
            return

        # 简单的关键字匹配
        status = None
        if "PASS" in self._content or "✅" in self._content:
            status = "PASS"
        elif "FAIL" in self._content or "❌" in self._content:
            status = "FAIL"
        
        if status:
            stamp = QLabel(status, self.bubble_container) # Parent is bubble
            stamp.setStyleSheet(get_audit_stamp_style(status))
            stamp.adjustSize()
            # 定位到右上角
            stamp.move(self.bubble_container.width() - stamp.width() - 20, 10)
            stamp.show()
            
            # Save stamp for resize event
            self.audit_stamp = stamp

            # 如果是 FAIL，仅加左侧红线（无气泡时不再整框描边）
            if status == "FAIL":
                self.bubble_container.setStyleSheet(f"""
                    QFrame {{ background-color: transparent; border: none; border-left: 3px solid {COLORS['accent_red']}; }}
                    QLabel {{ background-color: transparent; color: {COLORS['text_primary']}; font-size: 13px; line-height: 1.5; }}
                """)

    def resizeEvent(self, event):
        """处理大小调整"""
        super().resizeEvent(event)
        # 如果有印章，重新定位
        if hasattr(self, 'audit_stamp') and self.audit_stamp:
             self.audit_stamp.move(self.bubble_container.width() - self.audit_stamp.width() - 20, 10)


    def _split_content(self, content: str) -> tuple[str, str]:
        """分离自然语言前言和详细方案

        策略：
        1. 查找第一个 Markdown 标题（# 或 ##）
        2. 标题前为前言，标题后（含）为详情
        3. 如果没有标题，则根据长度判断
        4. 【重要】确保 intro 永远不为空，至少截取前一段作为摘要
        """
        lines = content.split('\n')
        split_idx = -1

        for i, line in enumerate(lines):
            if line.strip().startswith(('# ', '## ', '### ')):
                split_idx = i
                break
        
        if split_idx != -1:
            intro = "\n".join(lines[:split_idx]).strip()
            detail = "\n".join(lines[split_idx:]).strip()
            # 【Fix】如果 intro 为空（内容直接以标题开头），从 detail 中提取摘要
            if not intro and detail:
                # 取第一个非标题行，或截取前 120 字符
                for line in lines:
                    stripped = line.strip().lstrip('#').strip()
                    if stripped and len(stripped) > 5:
                        intro = stripped[:SUMMARY_MAX_CHARS] + ("..." if len(stripped) > SUMMARY_MAX_CHARS else "")
                        break
                if not intro:
                    intro = content[:SUMMARY_MAX_CHARS].replace('\n', ' ') + "..."
            return intro, detail
        
        # 没有标题的情况
        if len(content) > COLLAPSE_CHAR_THRESHOLD:
            parts = content.split('\n\n')
            if len(parts) > 1 and len(parts[0]) < 200:
                 return parts[0], "\n\n".join(parts[1:])
            else:
                 intro = content[:SUMMARY_MAX_CHARS].replace('\n', ' ') + "..."
                 return intro, content
        
        # 多段落（含 \n\n）且长度足够：首段为摘要，其余为「详细方案」以便显示「查看详细方案」
        if "\n\n" in content and len(content) > 100:
            parts = content.split('\n\n', 1)
            intro = parts[0].strip()
            detail = parts[1].strip() if len(parts) > 1 else ""
            if intro and detail:
                return intro, "\n\n" + detail
            if len(content) > SUMMARY_MAX_CHARS:
                return content[:SUMMARY_MAX_CHARS].replace('\n', ' ') + "...", content
        
        # 短内容 → 全部作为前言，无详情
        return content, ""



    def _toggle_expand(self):
        """切换展开/折叠状态"""
        self._is_expanded = not self._is_expanded

        if self._is_expanded:
            self.detail_text.setVisible(True)
            self.toggle_btn.setText("📄 收起详细方案 ▲")
        else:
            self.detail_text.setVisible(False)
            self.toggle_btn.setText("📄 查看详细方案 ▼")

    def _make_summary(self, content: str) -> str:
        """生成内容摘要

        提取首行或前 N 个字符作为摘要预览。

        Args:
            content: 完整消息内容

        Returns:
            格式化的摘要文本
        """
        # 取首行有意义的文字
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if not lines:
            return "（空内容）"

        # 取首行作为标题
        first_line = lines[0]
        # 去掉 markdown 标记
        for prefix in ['##', '#', '**', '- ', '> ']:
            first_line = first_line.lstrip(prefix).strip()

        # 截断过长
        if len(first_line) > SUMMARY_MAX_CHARS:
            first_line = first_line[:SUMMARY_MAX_CHARS] + "..."

        # 统计内容量
        total_lines = len(lines)
        total_chars = len(content)
        meta = f"  [{total_lines} 行 · {total_chars} 字]"

        return f"💬 {first_line}{meta}"

    def _format_content(self, content: str) -> str:
        """将内容格式化为 HTML (支持简单的代码块渲染)"""
        html_lines = []
        in_code_block = False
        
        for line in content.split('\n'):
            stripped = line.strip()
            
            # Code Block Start/End
            if stripped.startswith('```'):
                if in_code_block:
                    # End
                    html_lines.append("</pre></div>")
                    in_code_block = False
                else:
                    # Start
                    html_lines.append(
                        f"<div style='background-color:{COLORS['bg_secondary']}; border-radius:6px; padding:10px; margin:8px 0; border:1px solid {COLORS['border']};'>"
                        f"<pre style='font-family:Consolas, monospace; font-size:12px; color:{COLORS['text_primary']}; margin:0; white-space:pre-wrap;'>"
                    )
                    in_code_block = True
                continue
            
            if in_code_block:
                # Code content
                safe_line = line.replace("<", "&lt;").replace(">", "&gt;")
                html_lines.append(f"{safe_line}")
                continue

            # Normal Markdown
            if stripped.startswith('## '):
                html_lines.append(
                    f"<h3 style='color:{COLORS['accent_blue']};margin:12px 0 6px 0;'>"
                    f"{stripped[3:]}</h3>"
                )
            elif stripped.startswith('# '):
                html_lines.append(
                    f"<h2 style='color:{COLORS['accent_purple']};margin:16px 0 8px 0;'>"
                    f"{stripped[2:]}</h2>"
                )
            elif stripped.startswith('- '):
                html_lines.append(
                    f"<div style='margin-left:12px; margin-bottom:4px;'>• {stripped[2:]}</div>"
                )
            elif stripped.startswith('> '):
                 html_lines.append(
                    f"<div style='border-left:3px solid {COLORS['accent_orange']}; padding-left:8px; color:{COLORS['text_secondary']}; margin:4px 0;'>{stripped[2:]}</div>"
                )
            elif stripped:
                html_lines.append(f"<div style='margin-bottom:4px;'>{stripped}</div>")
            else:
                html_lines.append("<br>")

        if in_code_block: # Close if unclosed
             html_lines.append("</pre></div>")

        return (
            f"<div style='color:{COLORS['text_primary']};font-size:13px;"
            f"line-height:1.6; font-family: Segoe UI, sans-serif;'>"
            + "\n".join(html_lines)
            + "</div>"
        )


class SystemEventLabel(QFrame):
    """系统事件通知标签（居中显示）"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        label = QLabel(f"── {text} ──")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 12px;
            background-color: {COLORS['bg_secondary']};
            padding: 4px 16px;
            border-radius: 12px;
            border: 1px solid {COLORS['border_subtle']};
        """)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()


class WarRoomPanel(QFrame):
    """多路会议直播间面板

    real-time display of AI role discussions.
    Short messages are displayed directly, long messages are automatically collapsed into summaries that can be clicked to expand.
    """

    user_intervention_sent = pyqtSignal(str)
    rework_requested = pyqtSignal(str)
    file_linked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_attachment = None
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style())
        self._current_state = "ALL"
        self._streaming_messages = {}
        self._streaming_buffers = {}
        self._streaming_display_prefix = {}  # role -> 已打出显示的摘要前缀，逐字追赶 summary，避免打一半卡顿
        self._streaming_pending = {}
        self._streaming_deferred_final = {}  # role -> final_content，延后 finalize 等打字机排空
        self._typewriter_timer = None
        self._scroll_to_bottom_scheduled = False  # 打字机 tick 内防抖，避免每 35ms 都触发滚动导致卡顿
        self._typing_timers = {}
        self._init_ui()

    def _init_ui(self):
        """Initialize interface layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Use 0 margin for splitter
        layout.setSpacing(0)

        # Main splitter to separate chat area and input area
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background: transparent; height: 1px; max-height: 1px; }
        """)

        # Top container (Title + Chat)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. 标题
        self.header_label = QLabel("作战室")
        self.header_label.setStyleSheet(get_header_style())
        layout.addWidget(self.header_label)

        # 2. 消息区
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.message_container = QWidget()
        self.message_container.setStyleSheet("background: transparent;")
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(12)
        self.message_layout.addStretch()
        
        # 空状态：菱形 Logo（呼吸灯发光）+ 文案 + 快捷指令建议按钮
        self.placeholder = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder)
        placeholder_layout.setContentsMargins(24, 24, 24, 24)
        placeholder_layout.setSpacing(16)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_logo = QLabel("❖")
        self.placeholder_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_logo.setStyleSheet("font-size: 48px; color: #4a4a5a; background: transparent; border: none;")
        glow = QGraphicsDropShadowEffect(self.placeholder_logo)
        glow.setColor(QColor(100, 80, 220))
        glow.setBlurRadius(20)
        glow.setOffset(0, 0)
        self.placeholder_logo.setGraphicsEffect(glow)
        self._glow_effect = glow
        self._glow_phase = 0.0
        self._glow_timer = QTimer(self.placeholder)
        self._glow_timer.timeout.connect(self._tick_placeholder_glow)
        self._glow_timer.start(80)
        placeholder_layout.addWidget(self.placeholder_logo)
        _sub = QLabel("协作会话空闲…")
        _sub.setStyleSheet("font-size: 14px; font-weight: 500; color: #8B949E;")
        _sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(_sub, 0, Qt.AlignmentFlag.AlignCenter)
        self.message_layout.insertWidget(0, self.placeholder)
        
        self.scroll_area.setWidget(self.message_container)

        # 输入区：凹槽感（内阴影模拟）+ 聚焦时主题蓝边框
        self._input_focused = False
        self.input_container = QFrame()
        self.input_container.setMinimumHeight(60)
        self.input_container.setMaximumHeight(380)
        self._apply_input_container_style(focused=False)
        
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(8, 6, 8, 6)
        input_layout.setSpacing(8)
        
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("")
        self.input_edit.setMinimumWidth(200)
        self.input_edit.setMinimumHeight(56)
        self.input_edit.setMaximumHeight(380)
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {COLORS['text_primary']};
                font-size: 13px;
                padding: 4px 0;
                min-height: 28px;
            }}
        """)
        doc = self.input_edit.document()
        doc.setDocumentMargin(6)
        self.input_edit.setViewportMargins(0, 2, 0, 2)
        self.input_edit.installEventFilter(self)
        input_layout.addWidget(self.input_edit, 1)

        # 聊天区与输入区用 1px 细线分隔（Cursor 风格），可拖拽调整输入框高度
        self.chat_input_splitter = QSplitter(Qt.Orientation.Vertical)
        self.chat_input_splitter.setHandleWidth(1)
        self.chat_input_splitter.setChildrenCollapsible(False)
        self.chat_input_splitter.setStyleSheet("""
            QSplitter::handle { background: transparent; height: 1px; max-height: 1px; }
        """)
        self.chat_input_splitter.addWidget(self.scroll_area)
        self.chat_input_splitter.addWidget(self.input_container)
        self.chat_input_splitter.setStretchFactor(0, 1)
        self.chat_input_splitter.setStretchFactor(1, 0)
        # 初始：输入区足够高，保证占位符「输入消息（Ctrl+Enter 发送）」完整显示
        self.chat_input_splitter.setSizes([400, 100])

        layout.addWidget(self.chat_input_splitter)

        self.btn_attach = QPushButton("📎")
        self.btn_attach.setFixedSize(36, 36)
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setToolTip("附加文档（Word/PDF 等）")
        self.btn_attach.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255,255,255,0.06);
                color: {COLORS['text_tertiary']};
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.12);
                color: {COLORS['text_primary']};
            }}
            QPushButton:pressed {{ background-color: #404040; }}
        """)
        self.btn_attach.clicked.connect(self._on_attach_clicked)
        input_layout.addWidget(self.btn_attach)

        self.btn_send = QPushButton("发送")
        self.btn_send.setFixedHeight(36)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent_primary_blue']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #4096FF;
            }}
            QPushButton:pressed {{ background-color: #0958d9; }}
            QPushButton:disabled {{ background-color: #2a2a2a; color: #666; }}
        """)
        self.btn_send.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.btn_send)

        # 任务完成后的「不满意 → 重新评审」内嵌区（默认隐藏）
        self.rework_container = QFrame()
        self.rework_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_tertiary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        rework_layout = QVBoxLayout(self.rework_container)
        rework_layout.setContentsMargins(12, 10, 12, 10)
        rework_layout.setSpacing(8)
        self.rework_label = QLabel("对结果不满意？请说明哪里需要改进，然后让团队重新评审方案。")
        self.rework_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self.rework_label.setWordWrap(True)
        rework_layout.addWidget(self.rework_label)
        self.rework_category = QComboBox()
        self.rework_category.addItems([
            "请选择不满类型（可选）",
            "需求理解有偏差",
            "方案或架构不合适",
            "实现或代码有问题",
            "其他",
        ])
        self.rework_category.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
            }}
        """)
        rework_layout.addWidget(self.rework_category)
        self.rework_input = QTextEdit()
        self.rework_input.setPlaceholderText("请具体说明哪里不满意…")
        self.rework_input.setMaximumHeight(72)
        self.rework_input.setStyleSheet(f"background-color: {COLORS['bg_secondary']}; border: 1px solid {COLORS['border_subtle']}; border-radius: 4px; color: {COLORS['text_secondary']}; font-size: 12px; padding: 6px;")
        rework_layout.addWidget(self.rework_input)
        self.rework_btn = QPushButton("重新评审方案")
        self.rework_btn.setStyleSheet(get_button_style(variant="primary"))
        self.rework_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rework_btn.clicked.connect(self._on_rework_clicked)
        rework_layout.addWidget(self.rework_btn)
        self.rework_container.setVisible(False)
        layout.addWidget(self.rework_container)

        # 状态行：状态文字（在线状态已移至左侧成员列表头像旁）
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        status_row.addStretch()

        # 状态文字
        self.status_label = QLabel("协作环境就绪")
        self.status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: 500; font-size: 11px;")
        status_row.addWidget(self.status_label)
        
        layout.addLayout(status_row)

    def eventFilter(self, obj, event):
        """Ctrl+Enter 发送；输入框聚焦时容器边框主题蓝"""
        if obj == self.input_edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Return and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self._on_send_clicked()
                    return True
            elif event.type() == QEvent.Type.FocusIn:
                self._input_focused = True
                self._apply_input_container_style(focused=True)
            elif event.type() == QEvent.Type.FocusOut:
                self._input_focused = False
                self._apply_input_container_style(focused=False)
        return super().eventFilter(obj, event)

    def _apply_input_container_style(self, focused: bool):
        """输入区凹槽样式：内凹感（深色背景+上/左暗边）+ 聚焦时主题蓝边框"""
        if focused:
            self.input_container.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a1a;
                    border: 1px solid {COLORS['accent_primary_blue']};
                    border-radius: 6px;
                }}
            """)
        else:
            self.input_container.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a1a;
                    border: 1px solid {COLORS['border_subtle']};
                    border-radius: 6px;
                    border-top: 2px solid rgba(0,0,0,0.4);
                    border-left: 2px solid rgba(0,0,0,0.35);
                }}
            """)

    def _tick_placeholder_glow(self):
        """呼吸灯：蓝紫色发光强度周期变化"""
        self._glow_phase += 0.06
        if self._glow_phase > 2 * math.pi:
            self._glow_phase -= 2 * math.pi
        r = 12 + int(10 * math.sin(self._glow_phase))
        self._glow_effect.setBlurRadius(max(8, r))

    def _init_input_area(self, container: QWidget):
        # Merged into _init_ui for centering logic
        pass

    def resizeEvent(self, event):
        """Handle resize"""
        super().resizeEvent(event)
        # Position shortcut hint on the right side of input
        if hasattr(self, 'input_edit') and hasattr(self, 'shortcut_hint'):
            padding_right = 10
            x = self.input_edit.width() - self.shortcut_hint.width() - padding_right
            y = (self.input_edit.height() - self.shortcut_hint.height()) // 2
            self.shortcut_hint.move(x, y)

    def _on_attach_clicked(self):
        """选择并附加文件"""
        import os
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", "",
            "全部支持 (*.docx *.pdf *.txt *.md *.csv *.json);;Word (*.docx);;PDF (*.pdf);;全部 (*.*)"
        )
        if path:
            self.current_attachment = path
            name = os.path.basename(path)
            self.input_edit.setPlaceholderText("")
            self.file_linked.emit(path)

    def _on_send_clicked(self):
        """发送消息（可带附件）"""
        content = self.input_edit.toPlainText().strip()
        if not content and not self.current_attachment:
            return
        if self.current_attachment:
            content = f"[ATTACHMENT: {self.current_attachment}]\n{content}".strip()
            self.current_attachment = None
            self.input_edit.setPlaceholderText("")
        self.input_edit.clear()
        self.user_intervention_sent.emit(content)

    def _on_rework_clicked(self):
        """用户点击「重新评审方案」：汇总反馈并发出信号"""
        category = self.rework_category.currentText()
        detail = self.rework_input.toPlainText().strip()
        if not detail:
            detail = "(用户未填写具体说明)"
        if category and category != "请选择不满类型（可选）":
            feedback = f"[不满类型：{category}]\n\n{detail}"
        else:
            feedback = detail
        self.rework_input.clear()
        self.rework_category.setCurrentIndex(0)
        self.rework_requested.emit(feedback)

    def set_rework_visible(self, visible: bool):
        """任务完成时显示/隐藏「不满意 → 重新评审」区域"""
        self.rework_container.setVisible(visible)

    def append_message(self, role: str, content: str, state_id: str = None):
        """追加一条角色消息到对话流

        Args:
            role: 角色标识 (PM/Arch/Designer 等)
            content: 消息内容
            state_id: 消息所属的状态 ID (用于时间轴过滤)
        """
        print(f"[DEBUG] append_message called: role={role}, content length={len(content)}, state_id={state_id}")
        # 如果该角色有正在进行的流式消息，先结束它
        if role in self._streaming_messages:
            print(f"[DEBUG] 角色{role}有流式消息，调用finalize_streaming_message")
            self.finalize_streaming_message(role, content)
            return

        # 首次收到消息时隐藏占位提示
        if self.placeholder.isVisible():
            self.placeholder.setVisible(False)

        profile = AGENT_PROFILES.get(role, {
            "name": role, "color": COLORS['text_secondary'], "icon": "🤖"
        })

        # 创建可折叠消息卡片
        msg_widget = CollapsibleMessage(role, content, profile)

        # 绑定状态标签和角色标识
        msg_widget.setProperty("state_id", state_id)
        msg_widget.setProperty("role", role)  # 标记消息角色，便于后续查找
        msg_widget.setProperty("is_streaming", False)  # 标记为非流式消息

        # 插到弹簧前面（倒数第一个是 stretch）
        insert_pos = self.message_layout.count() - 1
        self.message_layout.insertWidget(insert_pos, msg_widget)

        # 根据当前过滤状态决定是否显示
        if self._current_state != "ALL" and state_id and state_id != self._current_state:
            msg_widget.setVisible(False)

        # 滚动到底部
        self._scroll_to_bottom()

    def filter_messages(self, state_id: str):
        """根据状态 ID 过滤消息显示
        
        Args:
            state_id: 要显示的状态 ID (e.g., 'grounding', 'debate'). 
                      如果为 'ALL' 或 None，则显示所有.
        """
        self._current_state = state_id
        
        # 遍历所有消息控件进行显隐切换
        # layout 里的 item 可能是 widget 或 spacer
        for i in range(self.message_layout.count()):
            item = self.message_layout.itemAt(i)
            widget = item.widget()
            
            if widget and isinstance(widget, CollapsibleMessage):
                msg_state = widget.property("state_id")
                # 如果当前不过滤，或者消息没有状态标签，或者状态匹配 -> 显示
                if not state_id or state_id == "ALL" or not msg_state or msg_state == state_id:
                    widget.setVisible(True)
                else:
                    widget.setVisible(False)
                    
        # 重新滚动到底部
        self._scroll_to_bottom()

    def append_system_event(self, text: str):
        """追加系统事件通知（居中显示）"""
        # 首次收到消息时隐藏占位提示
        if self.placeholder.isVisible():
            self.placeholder.setVisible(False)

        event_widget = SystemEventLabel(text)
        insert_pos = self.message_layout.count() - 1
        self.message_layout.insertWidget(insert_pos, event_widget)
        self._scroll_to_bottom()

    def set_typing_status(self, role: str, is_typing: bool):
        """更新角色输入状态

        Args:
            role: 角色标识
            is_typing: 是否正在输入
        """
        if is_typing:
            profile = AGENT_PROFILES.get(role, {"icon": "🤖", "name": role})
            self.status_label.setText(
                f"{profile['icon']} {profile['name']} 正在思考..."
            )
            self.status_label.setStyleSheet(get_thinking_style())
        else:
            self.status_label.setText("会议室待命")
            self.status_label.setStyleSheet(f"""
                color: {COLORS['text_tertiary']};
                font-size: 11px;
                font-weight: 500;
                padding: 4px;
                background-color: transparent;
            """)

    def clear_display(self):
        """清空所有消息"""
        # 移除所有消息控件（保留弹簧和占位提示）
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.placeholder:
                widget.deleteLater()

        # 清除流式消息跟踪
        self._streaming_messages.clear()
        self._streaming_buffers.clear()
        self._streaming_display_prefix.clear()
        for timer in self._typing_timers.values():
            if timer and timer.isActive():
                timer.stop()
        self._typing_timers.clear()

        # 重新显示占位提示
        self.placeholder.setVisible(True)
        if self.placeholder.parent() is None:
            self.message_layout.insertWidget(0, self.placeholder)

    def append_stream_chunk(self, role: str, chunk: str):
        """追加流式片段到待显示缓冲，由定时器逐字打出打字机效果"""
        if self.placeholder.isVisible():
            self.placeholder.setVisible(False)
        if role not in self._streaming_buffers:
            self._streaming_buffers[role] = ""
        if role not in self._streaming_pending:
            self._streaming_pending[role] = ""
        self._streaming_pending[role] += chunk

        if role not in self._streaming_messages:
            profile = AGENT_PROFILES.get(role, {
                "name": role, "color": COLORS['text_secondary'], "icon": "🤖"
            })
            msg_widget = CollapsibleMessage(role, "", profile)
            msg_widget.setProperty("is_streaming", True)
            # 流式时不显示框线
            msg_widget.bubble_container.setStyleSheet(f"""
                QFrame {{ background-color: transparent; border: none; }}
                QLabel {{
                    background-color: transparent;
                    color: {COLORS['text_primary']};
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    font-size: 13px;
                    line-height: 1.5;
                }}
            """)
            msg_widget.setProperty("stream_role", role)
            msg_widget.setProperty("role", role)
            insert_pos = self.message_layout.count() - 1
            self.message_layout.insertWidget(insert_pos, msg_widget)
            self._streaming_messages[role] = msg_widget
            if self._current_state != "ALL":
                msg_widget.setVisible(False)

        if self._typewriter_timer is None or not self._typewriter_timer.isActive():
            self._typewriter_timer = QTimer(self)
            self._typewriter_timer.timeout.connect(self._tick_warroom_typewriter)
            self._typewriter_timer.start(35)
        self._scroll_to_bottom()

    def _tick_warroom_typewriter(self):
        """打字机滴漏：每 tick 多排一些字；摘要打完后若已有最终内容则立即替换，避免卡顿后整段跳出。"""
        for role in list(self._streaming_pending.keys()):
            pending = self._streaming_pending[role]
            if not pending:
                continue
            # 仅当 buffer 中已有 \n\n（摘要与详情已分界）且绿框摘要已打满时，才提前替换，避免误判导致没有打字机
            if role in self._streaming_deferred_final:
                buffer = self._streaming_buffers.get(role, "")
                if "\n\n" in buffer:
                    target = _streaming_summary_only(buffer)
                    cur = self._streaming_display_prefix.get(role, "")
                    if cur == target and target:
                        del self._streaming_pending[role]
                        self._do_finalize_streaming_message(role)
                        continue
            # 每 tick 多取字以减少积压（后端常以 ~50 字/块推送）；英文最多 4 字/ tick，中文最多 2 字
            if len(pending) >= 2 and ord(pending[0]) < 0x80 and ord(pending[1]) < 0x80:
                take = min(4, len(pending))
            else:
                take = min(2, len(pending)) if pending else 0
            self._streaming_buffers[role] += pending[:take]
            self._streaming_pending[role] = pending[take:]
            target = _streaming_summary_only(self._streaming_buffers[role])
            if not self._streaming_pending[role]:
                del self._streaming_pending[role]
                self._streaming_display_prefix[role] = target  # pending 排空时摘要一次性显示完整
            else:
                cur = self._streaming_display_prefix.get(role, "")
                lag = len(target) - len(cur)
                step = min(4, max(1, lag))  # 每 tick 最多前进 4 字，与排水匹配
                new_len = min(len(cur) + step, len(target))
                self._streaming_display_prefix[role] = target[:new_len]
            self._refresh_streaming_display(role)
        for role in list(self._streaming_deferred_final.keys()):
            if role not in self._streaming_pending or not self._streaming_pending.get(role):
                self._do_finalize_streaming_message(role)
        if not self._streaming_pending and not self._streaming_deferred_final and self._typewriter_timer:
            self._typewriter_timer.stop()
            self._scroll_to_bottom_scheduled = False
        # 防抖：打字机期间只预约一次滚动，避免每 35ms 都滚动造成卡顿
        if not getattr(self, "_scroll_to_bottom_scheduled", False):
            self._scroll_to_bottom_scheduled = True
            QTimer.singleShot(80, self._scroll_to_bottom_debounced)

    def _refresh_streaming_display(self, role: str):
        """流式阶段：只显示红框摘要的逐字前缀+光标，不显示蓝框；单块、仅更新文本避免跳动。"""
        if role not in self._streaming_messages:
            return
        msg_widget = self._streaming_messages[role]
        display_text = self._streaming_display_prefix.get(role, "")
        layout = msg_widget.bubble_container.layout()
        content_label = getattr(msg_widget, "_stream_content_label", None)
        if content_label is not None and content_label.parent() is not None:
            content_label.setText(display_text)
            return
        is_user = (role == "Commander") or (role == "User")
        if not is_user:
            profile = AGENT_PROFILES.get(role, AGENT_PROFILES["System"])
            name_label = QLabel(profile["name"])
            name_label.setStyleSheet(f"""
                color: {COLORS['text_secondary']};
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                border: none;
                background: transparent;
                margin-bottom: 2px;
            """)
            layout.addWidget(name_label)
        content_label = QLabel(display_text)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("border: none; outline: none;")
        layout.addWidget(content_label)
        msg_widget._stream_content_label = content_label

    def finalize_streaming_message(self, role: str, final_content: str = None):
        """结束流式消息：若该角色尚有 pending 则延后，等打字机排空后再替换为最终消息"""
        if role not in self._streaming_messages:
            return
        self._streaming_deferred_final[role] = final_content if final_content is not None else (self._streaming_buffers.get(role, "") + self._streaming_pending.get(role, ""))
        if role not in self._streaming_pending or not self._streaming_pending.get(role):
            self._do_finalize_streaming_message(role)
        elif self._typewriter_timer is None or not self._typewriter_timer.isActive():
            self._typewriter_timer = QTimer(self)
            self._typewriter_timer.timeout.connect(self._tick_warroom_typewriter)
            self._typewriter_timer.start(35)

    def _do_finalize_streaming_message(self, role: str):
        """真正执行：移除流式气泡并追加最终消息（由 tick 排空后或 finalize 无 pending 时调用）"""
        if role not in self._streaming_deferred_final:
            return
        final_content = self._streaming_deferred_final.pop(role, "").replace("█", "")
        if self._typewriter_timer and not self._streaming_pending and not self._streaming_deferred_final:
            self._typewriter_timer.stop()
        msg_widget = self._streaming_messages.pop(role, None)
        if role in self._streaming_buffers:
            del self._streaming_buffers[role]
        if role in self._streaming_display_prefix:
            del self._streaming_display_prefix[role]
        if role in self._streaming_pending:
            del self._streaming_pending[role]
        if msg_widget:
            self.message_layout.removeWidget(msg_widget)
            msg_widget.deleteLater()
        if final_content.strip():
            profile = AGENT_PROFILES.get(role, {"name": role, "color": COLORS['text_secondary'], "icon": "🤖"})
            final_widget = CollapsibleMessage(role, final_content, profile)
            final_widget.setProperty("is_streaming", False)
            final_widget.setProperty("role", role)
            insert_pos = self.message_layout.count() - 1
            self.message_layout.insertWidget(insert_pos, final_widget)
            if self._current_state != "ALL":
                final_widget.setVisible(False)
        self._scroll_to_bottom()

    def _scroll_to_bottom_debounced(self):
        """打字机防抖：执行滚动并允许下次再预约"""
        self._scroll_to_bottom_scheduled = False
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到底部"""
        QTimer.singleShot(50, lambda: (
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
        ))
