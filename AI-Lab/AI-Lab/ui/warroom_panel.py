"""
warroom_panel.py - 多路会议直播间 (The War Room)
================================================
中间面板：实时展示 PM、Arch、Designer 三角博弈的聊天气泡流。
支持角色头像/身份标注、"正在输入..."状态显示。

★ 消息展示策略:
  - 自然语义对话: 直接完整展示
  - 详细方案/审批内容: 缩略显示，点击按钮展开or折叠
  - 系统事件: 居中小标签
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QSizePolicy, QScrollArea, QWidget,
    QPushButton, QSplitter
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

from ui.styles import COLORS, get_panel_style, get_button_style, get_audit_stamp_style, get_thinking_style, get_header_style, get_input_style
from config import AGENT_PROFILES

# ---------- 判断消息是否为"长内容"的阈值 ----------
COLLAPSE_LINE_THRESHOLD = 6      # 超过 6 行视为长内容
COLLAPSE_CHAR_THRESHOLD = 300    # 超过 300 字符视为长内容
SUMMARY_MAX_CHARS = 120          # 摘要最多显示 120 字符


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
        
        # 1. Avatar
        avatar = QLabel(self._profile["icon"])
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use a safe color for avatar background if profile color is text color
        bg_color = self._profile["color"]
        if bg_color.startswith("#"):
             pass
        else:
             bg_color = COLORS['accent_purple'] # Fallback
             
        avatar.setStyleSheet(f"""
            background-color: {bg_color};
            color: white;
            border-radius: 20px;
            font-size: 20px;
            font-family: 'Segoe UI Emoji';
        """)
        
        # 2. Bubble Container (Holds Name + Content)
        self.bubble_container = QFrame()
        bubble_layout = QVBoxLayout(self.bubble_container)
        bubble_layout.setContentsMargins(12, 8, 12, 8) # Compact: 16/12 -> 12/8
        bubble_layout.setSpacing(4)
        
        # Bubble Style
        
        # Bubble Style
        from ui.styles import get_chat_bubble_css
        # Determine strict colors for role
        if is_user:
            role_color = COLORS.get('accent_blue', '#58A6FF')
        else:
            role_color = COLORS['bg_secondary']
            
        # Use centralized style function
        self.bubble_style_sheet = f"""
            QFrame {{
                {get_chat_bubble_css(role_color, is_user).replace("text-align", "qproperty-alignment").replace("margin", "qproperty-margin")}
            }}
            QLabel {{
                background-color: transparent;
                color: {'white' if is_user else COLORS['text_primary']};
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }}
        """
        # Note: get_chat_bubble_css returns raw CSS properties (e.g. "background-color: ...;")
        # We need to wrap them in QFrame { ... }
        # Re-implementing specific QSS construction here to be safe and precise for QFrame
        
        # Bubble Style
        if is_user:
            bg = "#005FB8" # Windows/WeChat-ish Blue for User
            text_color = "#FFFFFF"
            radius = "12px 12px 2px 12px"
            border = "none"
        else:
            bg = COLORS['bg_secondary'] # Consistency fix
            text_color = COLORS['text_secondary']
            radius = "12px 12px 12px 2px"
            border = f"1px solid {COLORS['border']}"
            
        self.bubble_style_sheet = f"""
            QFrame {{
                background-color: {bg};
                border: {border};
                border-radius: {radius};
            }}
            QLabel {{
                background-color: transparent;
                color: {text_color};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }}
        """
        self.bubble_container.setStyleSheet(self.bubble_style_sheet)

        # 2.1 Name Label (High-End Polish)
        if not is_user:
            name_label = QLabel(self._profile["name"])
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
            bubble_layout.addWidget(name_label)

        # 2.2 Content
        intro, detail = self._split_content(self._content)
        
        if intro:
            intro_label = QLabel(intro)
            intro_label.setWordWrap(True)
            bubble_layout.addWidget(intro_label)

        # 2.3 Detail Button & Area
        if detail:
           self._init_detail_ui(detail, bubble_layout, is_user)

        # Assemble Main Layout
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
            
        # Max width constraint for bubble
        self.bubble_container.setMaximumWidth(600)

    def _init_detail_ui(self, detail, layout, is_user):
        """Initialize detail section"""
        # Toggle Button
        self.toggle_btn = QPushButton("📄 查看详细方案 ▼")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background-color: rgba(255, 255, 255, 0.2);
                color: {'#FFFFFF' if is_user else COLORS.get('accent_blue', '#58A6FF')};
                border: None;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
                margin-top: 8px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.3);
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_expand)
        layout.addWidget(self.toggle_btn)

        # Detail Text
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

            # 如果是 FAIL，给整个 bubble 加红色边框
            if status == "FAIL":
                # Append red border to existing style
                fail_style = self.bubble_style_sheet.replace(
                    f"border-radius: {self.radius};",
                    f"border-radius: {self.radius}; border: 2px solid {COLORS['accent_red']};"
                )
                self.bubble_container.setStyleSheet(fail_style)

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
            border: 1px solid {COLORS['border']};
        """)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()


class WarRoomPanel(QFrame):
    """多路会议直播间面板

    real-time display of AI role discussions.
    Short messages are displayed directly, long messages are automatically collapsed into summaries that can be clicked to expand.
    """

    user_intervention_sent = pyqtSignal(str)  # Signal: User sends intervention instruction

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style())
        self._current_state = "ALL"  # 当前过滤状态
        # 流式消息跟踪
        self._streaming_messages = {}  # role -> message widget
        self._streaming_buffers = {}   # role -> buffer content
        self._typing_timers = {}       # role -> typing timer
        self._init_ui()

    def _init_ui(self):
        """Initialize interface layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Use 0 margin for splitter
        layout.setSpacing(0)

        # Main splitter to separate chat area and input area
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border']};
            }}
        """)

        # Top container (Title + Chat)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. Header (Small Label)
        self.header_label = QLabel("WAR ROOM")
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
        
        # Placeholder (Empty State)
        self.placeholder = QLabel()
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setText(
            "<span style='font-size: 48px; color: #30363D;'>❖</span><br>"
            "<span style='font-size: 14px; font-weight: 500; color: #8B949E;'>Collaborative session idle...</span>"
        )
        self.message_layout.insertWidget(0, self.placeholder)
        
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
        
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Command the War Room (Ctrl+Enter to send)...")
        self.input_edit.setStyleSheet("background: transparent; border: none; color: #C9D1D9;")
        self.input_edit.installEventFilter(self)
        input_layout.addWidget(self.input_edit)
        
        layout.addWidget(self.input_container)

        # Status row: Indicators + Status Label
        status_row = QHBoxLayout()
        status_row.setSpacing(12)

        # 4. Online Indicator
        self.online_indicator = QLabel("● NO AGENTS ONLINE")
        self.online_indicator.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 10px; font-weight: bold;")
        status_row.addWidget(self.online_indicator)
        
        status_row.addStretch()

        # 5. Status Label (Muted)
        self.status_label = QLabel("Collaborative Environment Ready")
        self.status_label.setStyleSheet(f"color: {COLORS.get('accent_blue', '#58A6FF')}; font-weight: bold; font-size: 11px;")
        status_row.addWidget(self.status_label)
        
        layout.addLayout(status_row)

    def eventFilter(self, obj, event):
        """Handle Ctrl+Enter to send"""
        if obj == self.input_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._on_send_clicked()
                return True
        return super().eventFilter(obj, event)

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

    def _on_send_clicked(self):
        """Handle send button click"""
        content = self.input_edit.toPlainText().strip()
        if not content:
            return
            
        print(f"[DEBUG] WarRoomPanel sending: {content}") # DEBUG
        # Clear input box
        self.input_edit.clear()
        
        # Emit signal
        self.user_intervention_sent.emit(content)

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
            self.status_label.setText("🔇 会议室待命")
            self.status_label.setStyleSheet(f"""
                color: {COLORS['text_secondary']};
                font-size: 11px;
                padding: 4px;
                background-color: {COLORS['bg_primary']};
                border-radius: 4px;
            """)

    def set_active_roles(self, roles: list):
        """更新在线角色指示器"""
        icons = []
        for role in roles:
            profile = AGENT_PROFILES.get(role, {"icon": "🤖"})
            icons.append(profile["icon"])
        self.online_indicator.setText(" ".join(icons) + " 在线")

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
        for timer in self._typing_timers.values():
            if timer and timer.isActive():
                timer.stop()
        self._typing_timers.clear()

        # 重新显示占位提示
        self.placeholder.setVisible(True)
        if self.placeholder.parent() is None:
            self.message_layout.insertWidget(0, self.placeholder)

    def append_stream_chunk(self, role: str, chunk: str):
        """追加流式输出片段到指定角色的消息

        Args:
            role: 角色标识
            chunk: 流式片段内容
        """
        print(f"[DEBUG] append_stream_chunk called: role={role}, chunk={repr(chunk)}")
        # 首次收到消息时隐藏占位提示
        if self.placeholder.isVisible():
            self.placeholder.setVisible(False)

        # 初始化角色的缓冲区
        if role not in self._streaming_buffers:
            self._streaming_buffers[role] = ""

        # 追加新片段到缓冲区
        self._streaming_buffers[role] += chunk

        # 移除原先遍历所有消息寻找旧消息的错误逻辑
        # 这种逻辑会导致如果该角色在历史中发过言，其后续流式都会被强制丢弃。

        # 检查是否已有该角色的流式消息部件
        if role not in self._streaming_messages:
            print(f"[DEBUG] 创建新的流式消息部件 for {role}")
            # 创建新的流式消息部件
            profile = AGENT_PROFILES.get(role, {
                "name": role, "color": COLORS['text_secondary'], "icon": "🤖"
            })

            # 创建初始消息，显示为"正在输入..."
            initial_content = f"{chunk}█"  # 添加光标效果
            msg_widget = CollapsibleMessage(role, initial_content, profile)

            # 标记为流式消息
            msg_widget.setProperty("is_streaming", True)
            msg_widget.setProperty("stream_role", role)
            msg_widget.setProperty("role", role)  # 设置角色标识

            # 添加到布局
            insert_pos = self.message_layout.count() - 1
            self.message_layout.insertWidget(insert_pos, msg_widget)

            # 保存引用
            self._streaming_messages[role] = msg_widget

            # 根据当前过滤状态决定是否显示
            if self._current_state != "ALL":
                msg_widget.setVisible(False)
        else:
            # print(f"[DEBUG] 更新现有流式消息部件 for {role}")
            msg_widget = self._streaming_messages[role]
            
            # 更新内容
            content_with_cursor = f"{self._streaming_buffers[role]}█"
            
            # 查找内容所在的 QLabel/QTextEdit 组件并更新
            # CollapsibleMessage 使用了 QLabel 或者是 QTextEdit 存放 intro 和 detail
            # 这里我们直接强制重新执行它的内部 _split_content 拆分并重新渲染
            
            # 清理旧的 bubble_layout 里的内容（除了 name_label 以外）
            layout = msg_widget.bubble_container.layout()
            
            # 从后往前删，保留最后的 stretch 和 name_label
            while layout.count() > 1: # 保留第一个元素通常是 name_label 或第一个 intro
                item = layout.takeAt(1)
                if item.widget():
                    item.widget().deleteLater()
                    
            # 获取 name_label 后的第一个 intro_label
            if layout.count() > 0:
                first_item = layout.itemAt(0).widget()
                # 如果这个不是 name_label，而是直接的 intro_label (User 角色)
                if not getattr(first_item, 'text', lambda: "")().isupper(): # 简单判断是不是 name_label
                    item = layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

            is_user = (role == "Commander") or (role == "User")
            if not is_user and layout.count() == 0:
                # 理论上保留 name_label，这里保守重建
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

            intro, detail = msg_widget._split_content(content_with_cursor)
            
            if intro:
                intro_label = QLabel(intro)
                intro_label.setWordWrap(True)
                layout.addWidget(intro_label)

            if detail:
               msg_widget._init_detail_ui(detail, layout, is_user)

        # 滚动到底部
        self._scroll_to_bottom()

    def finalize_streaming_message(self, role: str, final_content: str = None):
        """结束指定角色的流式消息，转换为普通消息

        Args:
            role: 角色标识
            final_content: 最终完整内容（如果为None则使用缓冲区内容）
        """
        print(f"[DEBUG] finalize_streaming_message called: role={role}, final_content provided={final_content is not None}")
        if role not in self._streaming_messages:
            print(f"[DEBUG] 角色{role}没有流式消息，直接返回")
            return

        # 获取缓冲区的最终内容
        if final_content is None:
            final_content = self._streaming_buffers.get(role, "")
        print(f"[DEBUG] 最终内容长度: {len(final_content)}")

        # 移除光标效果
        final_content = final_content.replace("█", "")

        # 移除旧的流式消息部件
        msg_widget = self._streaming_messages.pop(role, None)
        if msg_widget:
            print(f"[DEBUG] 移除流式消息部件")
            self.message_layout.removeWidget(msg_widget)
            msg_widget.deleteLater()

        # 清除缓冲区
        if role in self._streaming_buffers:
            del self._streaming_buffers[role]

        # 创建最终的普通消息
        if final_content.strip():
            print(f"[DEBUG] 创建最终的普通消息")
            profile = AGENT_PROFILES.get(role, {
                "name": role, "color": COLORS['text_secondary'], "icon": "🤖"
            })
            final_widget = CollapsibleMessage(role, final_content, profile)
            final_widget.setProperty("is_streaming", False)
            final_widget.setProperty("role", role)  # 设置角色标识

            # 添加到布局末尾（在弹簧之前）
            insert_pos = self.message_layout.count() - 1
            self.message_layout.insertWidget(insert_pos, final_widget)

            # 根据过滤状态设置可见性
            if self._current_state != "ALL":
                final_widget.setVisible(False)

            # 滚动到底部
            self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到底部"""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: (
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
        ))
