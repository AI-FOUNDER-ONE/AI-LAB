"""
timeline_panel.py - 议程状态栏 (Slim Status Bar)
===============================================
底部状态栏：高度 36px，仅展示当前阶段和极简进度。
Compact Mode: Icons only + Current Phase Text.
"""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from ui.styles import COLORS
from config import AppState


class TimelinePanel(QFrame):
    """议程状态栏：进度百分比 + 阶段圆点 + 状态文字"""

    node_clicked = pyqtSignal(str)

    STAGES = [
        ("💡", "需求打磨", AppState.GROUNDING),
        ("🏛️", "方案博弈", AppState.DEBATE),
        ("⚡", "执行",     AppState.PRODUCTION),
        ("🔧", "验证",     AppState.VERIFICATION),
        ("🏁", "完成",     AppState.COMPLETED),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("timeline_bar")
        self.setFixedHeight(32)
        self.setStyleSheet(f"""
            QFrame#timeline_bar {{
                background-color: {COLORS['bg_primary']};
                border-top: 1px solid {COLORS['border']};
            }}
            QLabel {{
                color: {COLORS['text_secondary']};
                font-family: -apple-system, sans-serif;
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        self.dots = {}
        self._init_ui()

    def _init_ui(self):
        """初始化阶段圆点与进度条"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(8)

        # 1. 进度文字
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet(f"color: {COLORS.get('accent_blue', '#58A6FF')}; font-weight: bold; font-size: 11px; background: transparent; border: none;")
        self.progress_label.setFixedWidth(36)
        layout.addWidget(self.progress_label)

        # 2. 阶段圆点
        for i, (icon, label, state_id) in enumerate(self.STAGES):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {COLORS['border']}; font-size: 10px; background: transparent; border: none;")
            dot.setToolTip(f"{icon} {label}")
            self.dots[state_id] = dot
            layout.addWidget(dot)
            
            if i < len(self.STAGES) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedWidth(24)
                line.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px; border: none;")
                layout.addWidget(line)

        layout.addStretch()

        # 3. 状态文字（右对齐）
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.status_label)

    def set_current_state(self, state: str):
        """更新阶段圆点状态"""
        stage_ids = [s[2] for s in self.STAGES]
        current_idx = -1
        if state in stage_ids:
            current_idx = stage_ids.index(state)

        if current_idx >= 0:
            pct = int((current_idx / (len(self.STAGES) - 1)) * 100)
            self.progress_label.setText(f"{pct}%")
        
        for i, (_, label, state_id) in enumerate(self.STAGES):
            dot = self.dots[state_id]
            if i < current_idx:
                dot.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 10px; background: transparent; border: none;")
                dot.setToolTip(f"已完成: {label}")
            elif i == current_idx:
                dot.setStyleSheet(f"color: {COLORS.get('accent_blue', '#58A6FF')}; font-size: 14px; background: transparent; border: none;")
            else:
                dot.setStyleSheet(f"color: {COLORS['border']}; font-size: 10px; background: transparent; border: none;")
                dot.setToolTip(f"待开始: {label}")

    def reset(self):
        self.set_current_state(AppState.GROUNDING)
        self.progress_label.setText("0%")

    def set_status_message(self, msg: str):
        self.status_label.setText(msg)
