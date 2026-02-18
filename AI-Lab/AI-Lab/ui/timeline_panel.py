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
    """议程状态栏 (Slim Sticky Bar)
    
    Layout: [Progress %] [Phase 1] > [Phase 2] > ... [Status Msg]
    """

    node_clicked = pyqtSignal(str) # 保留信号接口，虽然可能暂时无法点击详情

    STAGES = [
        ("💡", "Grounding", AppState.GROUNDING),
        ("🏛️", "Debate",    AppState.DEBATE),
        ("⚡", "Exec",      AppState.PRODUCTION),
        ("🔧", "Verify",    AppState.VERIFICATION),
        ("🏁", "Done",      AppState.COMPLETED),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("timeline_bar")
        self.setFixedHeight(32) # Ultra slim: 32px
        self.setStyleSheet(f"""
            QFrame#timeline_bar {{
                background-color: {COLORS['bg_primary']};
                border-top: 1px solid {COLORS['border']};
            }}
            QLabel {{
                color: {COLORS['text_secondary']};
                font-family: -apple-system, sans-serif;
                font-size: 11px;
            }}
        """)
        self.dots = {} # Store dots to update
        self._init_ui()

    def _init_ui(self):
        """Initialize Slim Dot UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(8)

        # 1. Progress Text
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet(f"color: {COLORS.get('accent_blue', '#58A6FF')}; font-weight: bold; font-size: 11px;")
        self.progress_label.setFixedWidth(36)
        layout.addWidget(self.progress_label)

        # 2. Stage Indicators (Dots)
        # We want: Dot - Line - Dot - Line ...
        
        for i, (icon, label, state_id) in enumerate(self.STAGES):
            # Container for Dot
            dot = QLabel("●") # Unicode Dot
            dot.setStyleSheet(f"color: {COLORS['border']}; font-size: 10px;") # Default Inactive
            dot.setToolTip(f"{icon} {label}")
            self.dots[state_id] = dot
            layout.addWidget(dot)
            
            # Line (if not last)
            if i < len(self.STAGES) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedWidth(24) # Length of line
                line.setStyleSheet(f"color: {COLORS['border']}; background-color: {COLORS['border']}; max-height: 1px;")
                layout.addWidget(line)

        layout.addStretch()

        # 3. Status Message (Right aligned)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
        layout.addWidget(self.status_label)

    def set_current_state(self, state: str):
        """Update Dot Status"""
        stage_ids = [s[2] for s in self.STAGES]
        
        current_idx = -1
        if state in stage_ids:
            current_idx = stage_ids.index(state)

        # Update percent
        if current_idx >= 0:
            pct = int((current_idx / (len(self.STAGES) - 1)) * 100)
            self.progress_label.setText(f"{pct}%")
        
        # Update dots
        for i, (_, label, state_id) in enumerate(self.STAGES):
            dot = self.dots[state_id]
            
            if i < current_idx:
                # Completed
                dot.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 10px;")
                dot.setToolTip(f"Completed: {label}")
            elif i == current_idx:
                # Active (Larger, Blue)
                dot.setStyleSheet(f"color: {COLORS.get('accent_blue', '#58A6FF')}; font-size: 14px;")
            else:
                dot.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 14px;")
                # Pending
                dot.setStyleSheet(f"color: {COLORS['border']}; font-size: 10px;")
                dot.setToolTip(f"Pending: {label}")

    def reset(self):
        self.set_current_state(AppState.GROUNDING)
        self.progress_label.setText("0%")

    def set_status_message(self, msg: str):
        self.status_msg.setText(msg)
