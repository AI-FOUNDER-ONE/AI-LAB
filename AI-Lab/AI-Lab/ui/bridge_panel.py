"""
bridge_panel.py - 项目组成员列表（左侧）
==========================================
带头像、名称与状态的 AI 成员列表，对话输入在作战室进行。
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PyQt6.QtCore import pyqtSignal, Qt

from ui.styles import COLORS, get_panel_style, get_header_style
from config import AGENT_PROFILES

# 标题左侧装饰条与状态点颜色
ACCENT_BAR_COLOR = COLORS.get("accent_primary_blue", "#1677FF")
STATUS_DOT_IDLE = "#8C8C8C"
STATUS_DOT_READY = "#52C41A"  # 就绪/活跃绿
STATUS_DOT_TYPING = "#1677FF"  # 思考中蓝
STATUS_DOT_SPEAKING = "#52C41A"  # 发言中绿
# 在线/离线指示灯（与工作状态独立）
ONLINE_DOT_COLOR = "#52C41A"   # 在线绿点
OFFLINE_DOT_COLOR = "#8C8C8C"  # 离线灰点

BRIDGE_ROLES = ["CKO", "PM", "Arch", "Designer", "Coder", "Validator"]
STATUS_TEXT = {"idle": "空闲", "typing": "思考中", "speaking": "发言中"}

# 成员列表：Cursor 线稿风（灰底+首字母，无彩色）
TEAM_AVATAR_STYLE = {
    "CKO":      {"icon": "K", "name": "CKO"},
    "PM":       {"icon": "P", "name": "PM"},
    "Arch":     {"icon": "A", "name": "Arch"},
    "Designer": {"icon": "D", "name": "Designer"},
    "Coder":    {"icon": "C", "name": "Coder"},
    "Validator":{"icon": "V", "name": "Validator"},
}


class BridgePanel(QFrame):
    """项目组成员列表：头像 + 名称 + 状态"""

    project_confirmed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._role_status = {}
        self._role_rows = {}
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题：左侧 3px×16px 主题蓝竖线 + 加粗文字（背景透明，透出面板）
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(8)
        accent_bar = QFrame()
        accent_bar.setFixedSize(3, 16)
        accent_bar.setStyleSheet(f"background-color: {ACCENT_BAR_COLOR}; border: none; border-radius: 1px;")
        header_layout.addWidget(accent_bar)
        self.header_label = QLabel("项目组成员列表")
        self.header_label.setStyleSheet(f"""
            color: {COLORS['text_tertiary']};
            font-size: 11px;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        layout.addWidget(header_widget)

        list_container = QFrame()
        list_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_tertiary']};
                border: none;
                border-radius: 4px;
            }}
        """)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(10, 10, 10, 10)
        list_layout.setSpacing(8)

        self._role_online = {r: False for r in BRIDGE_ROLES}
        for role in BRIDGE_ROLES:
            style = TEAM_AVATAR_STYLE.get(role, {"icon": "?", "name": role})
            self._role_status[role] = "idle"
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(12)

            # 头像容器：头像 + 右下角在线/离线指示灯（与工作状态共存）
            avatar_container = QWidget()
            avatar_container.setFixedSize(36, 36)
            avatar = QLabel(style["icon"])
            avatar.setParent(avatar_container)
            avatar.setGeometry(0, 0, 36, 36)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet(f"""
                QLabel {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {COLORS['bg_avatar']}, stop:1 #2a2a2a);
                    color: {COLORS['text_primary']};
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: 500;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                }}
            """)
            online_dot = QLabel()
            online_dot.setParent(avatar_container)
            online_dot.setFixedSize(8, 8)
            online_dot.setGeometry(26, 26, 8, 8)
            online_dot.setStyleSheet(
                f"background-color: {OFFLINE_DOT_COLOR}; border: 1px solid {COLORS['bg_tertiary']}; border-radius: 4px;"
            )
            name_label = QLabel(style["name"])
            name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 600; font-size: 13px; background: transparent; border: none;")
            name_label.setFixedWidth(72)
            # 状态指示灯（圆点）+ 状态文字
            status_dot = QLabel()
            status_dot.setFixedSize(6, 6)
            status_dot.setStyleSheet(f"background-color: {STATUS_DOT_IDLE}; border: none; border-radius: 3px;")
            status_label = QLabel(STATUS_TEXT["idle"])
            status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; background: transparent; border: none;")
            status_row = QWidget()
            status_row_layout = QHBoxLayout(status_row)
            status_row_layout.setContentsMargins(0, 0, 0, 0)
            status_row_layout.setSpacing(6)
            status_row_layout.addWidget(status_dot)
            status_row_layout.addWidget(status_label)
            status_row_layout.addStretch()

            row_layout.addWidget(avatar_container)
            row_layout.addWidget(name_label)
            row_layout.addWidget(status_row, 1)
            list_layout.addWidget(row)
            self._role_rows[role] = {
                "avatar": avatar,
                "name": name_label,
                "status": status_label,
                "status_dot": status_dot,
                "online_dot": online_dot,
            }

        layout.addWidget(list_container)
        layout.addStretch()

    def set_role_status(self, role: str, status: str):
        """设置某 AI 角色工作状态：idle=灰点，typing/speaking=绿点/蓝点，并更新状态文字（与在线指示灯独立）"""
        if role not in self._role_rows:
            return
        self._role_status[role] = status
        text = STATUS_TEXT.get(status, "空闲")
        self._role_rows[role]["status"].setText(text)
        # 工作状态指示灯：空闲=灰，思考中=蓝，发言中/就绪=绿
        dot_color = STATUS_DOT_IDLE
        if status == "typing":
            dot_color = STATUS_DOT_TYPING
        elif status == "speaking":
            dot_color = STATUS_DOT_READY
        self._role_rows[role]["status_dot"].setStyleSheet(
            f"background-color: {dot_color}; border: none; border-radius: 3px;"
        )
        text_color = COLORS["text_tertiary"]
        if status == "typing":
            text_color = COLORS.get("accent_blue", "#1677FF")
        elif status == "speaking":
            text_color = STATUS_DOT_READY
        self._role_rows[role]["status"].setStyleSheet(
            f"color: {text_color}; font-size: 11px; background: transparent; border: none;"
        )

    def set_role_online(self, role: str, is_online: bool):
        """设置某角色的在线/离线状态（头像右下角绿点/灰点），与工作状态共存"""
        self._role_online[role] = is_online
        if role not in self._role_rows or "online_dot" not in self._role_rows[role]:
            return
        color = ONLINE_DOT_COLOR if is_online else OFFLINE_DOT_COLOR
        self._role_rows[role]["online_dot"].setStyleSheet(
            f"background-color: {color}; border: 1px solid {COLORS['bg_tertiary']}; border-radius: 4px;"
        )

    def set_roles_online(self, roles: list):
        """批量设置在线角色，其余为离线。roles 为在线角色 id 列表（如 ['Arch','Coder','PM']）。"""
        for r in BRIDGE_ROLES:
            self.set_role_online(r, r in roles)

    def set_status(self, text: str):
        """保留接口兼容"""
        pass

    def _on_confirm(self):
        """确认立项（由导航栏按钮触发）"""
        self.project_confirmed.emit()
