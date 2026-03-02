"""
execution_panel.py - 执行与测试实验室 (Execution Lab)
=====================================================
右侧面板：实时查看 Coder 编写的代码（语法高亮）
以及 Validator 的运行日志（终端风格输出）。
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QTextEdit, QSplitter, QSizePolicy, QWidget,
    QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QFont, QTextCursor, QSyntaxHighlighter,
    QTextCharFormat, QColor
)
import re

from ui.styles import COLORS, get_panel_style, get_header_style, get_code_editor_style


class PythonHighlighter(QSyntaxHighlighter):
    """Python 语法高亮器

    为代码编辑器提供基本的 Python 语法高亮 (Dark Mode)。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        # Dark Theme Syntax Highlighting (Dracula-inspired)
        
        # Keywords (Pink/Purple)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#FF79C6")) 
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class',
            'continue', 'def', 'del', 'elif', 'else', 'except', 'finally',
            'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
            'while', 'with', 'yield', 'True', 'False', 'None',
        ]
        for kw in keywords:
            pattern = rf'\b{kw}\b'
            self._rules.append((re.compile(pattern), keyword_format))

        # Builtins (Cyan)
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#8BE9FD"))
        builtins = ['print', 'len', 'range', 'enumerate', 'zip', 'map',
                     'filter', 'sorted', 'list', 'dict', 'set', 'tuple',
                     'int', 'float', 'str', 'bool', 'type', 'isinstance',
                     'super', 'self', 'open', 'input', 'format']
        for b in builtins:
            self._rules.append((re.compile(rf'\b{b}\b'), builtin_format))

        # Decorators (Yellow)
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#F1FA8C"))
        self._rules.append((re.compile(r'@\w+'), decorator_format))

        # Numbers (Orange)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#FFB86C"))
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), number_format))

        # Strings (Green)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#50FA7B"))
        self._rules.append((re.compile(r'\".*?\"'), string_format))
        self._rules.append((re.compile(r"\'.*?\'"), string_format))

        # Comments (Blue/Grey)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6272A4"))
        comment_format.setFontItalic(True)
        self._rules.append((re.compile(r'#.*$'), comment_format))

        # Function Names (Green)
        func_format = QTextCharFormat()
        func_format.setForeground(QColor("#50FA7B"))
        self._rules.append((re.compile(r'\bdef\s+(\w+)'), func_format))

        # Class Names (Cyan)
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#8BE9FD"))
        self._rules.append((re.compile(r'\bclass\s+(\w+)'), class_format))

    def highlightBlock(self, text: str):
        """对一行文本进行高亮处理"""
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class ExecutionPanel(QFrame):
    """执行与测试实验室面板

    上半部分：代码编辑器（带 Python 语法高亮）
    下半部分：终端风格的测试日志控制台
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style())
        self._init_ui()

    def _init_ui(self):
        """GitHub Style Execution Lab (Terminal Black)"""
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style(bg=COLORS['bg_terminal']))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. Header (Small Label)
        self.header_label = QLabel("EXECUTION LAB")
        self.header_label.setStyleSheet(get_header_style())
        layout.addWidget(self.header_label)

        # 2. Splitter for Editor and Logs
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(1) # Hairline

        # --- Reference Docs Area (Top) ---
        self.ref_container = QWidget()
        self.ref_container.setFixedHeight(0) # Hidden by default
        self.ref_layout = QHBoxLayout(self.ref_container)
        self.ref_layout.setContentsMargins(0, 0, 0, 4)
        self.ref_layout.setSpacing(8)
        
        ref_label = QLabel("🔗 REFERENCES:")
        ref_label.setStyleSheet("color: #8B949E; font-size: 10px; font-weight: 700;")
        self.ref_layout.addWidget(ref_label)
        
        # New: File Label for source code
        self.code_file_label = QLabel("")
        self.code_file_label.setStyleSheet("color: #58A6FF; font-size: 10px; font-weight: bold;")
        self.ref_layout.addWidget(self.code_file_label)
        
        self.ref_layout.addStretch()
        
        layout.addWidget(self.ref_container)

        # --- Editor Card ---
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)
        
        editor_label = QLabel("SOURCE CODE")
        editor_label.setStyleSheet("color: #8B949E; font-size: 10px; font-weight: 700;")
        editor_layout.addWidget(editor_label)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setReadOnly(True)
        self.code_editor.setPlaceholderText("/* Code will manifest in GitHub Dark Dimmed... */")
        self.code_editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #000000;
                color: #C9D1D9;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                font-family: 'SFMono-Regular', Consolas, monospace;
                font-size: 13px;
                padding: 8px;
            }}
        """)
        self._highlighter = PythonHighlighter(self.code_editor.document())
        editor_layout.addWidget(self.code_editor)
        
        self.splitter.addWidget(editor_container)

        # --- Logs Card ---
        logs_container = QWidget()
        logs_layout = QVBoxLayout(logs_container)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(8)
        
        logs_label = QLabel("RUNTIME CONSOLE")
        logs_label.setStyleSheet("color: #8B949E; font-size: 10px; font-weight: 700;")
        logs_layout.addWidget(logs_label)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("> Waiting for execution...")
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: #000000;
                color: #B2B2B2;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                font-family: 'SFMono-Regular', Consolas, monospace;
                font-size: 12px;
                padding: 8px;
            }}
        """)
        logs_layout.addWidget(self.log_console)
        
        self.splitter.addWidget(logs_container)

        self.splitter.setSizes([600, 200])
        layout.addWidget(self.splitter)
        layout.setStretchFactor(self.splitter, 1)

        # Status Label
        self.status_label = QLabel("Terminal Idle")
        self.status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
        layout.addWidget(self.status_label)

    def set_code(self, code: str, filename: str = ""):
        """设置代码编辑器内容

        Args:
            code: 代码文本
            filename: 文件名（可选）
        """
        self.code_editor.setPlainText(code)
        if filename:
            self.code_file_label.setText(f"📄 {filename}")

    def append_code(self, text: str):
        """追加代码文本（流式输出效果）"""
        self.code_editor.moveCursor(QTextCursor.MoveOperation.End)
        self.code_editor.insertPlainText(text)

    def add_reference_doc(self, file_path: str):
        """Add a reference document link to the top bar"""
        import os
        filename = os.path.basename(file_path)
        
        btn_doc = QPushButton(f"📄 {filename}")
        btn_doc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_doc.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('bg_secondary', '#0D1117')};
                color: {COLORS.get('accent_blue', '#58A6FF')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('border', '#30363D')};
            }}
        """)
        btn_doc.clicked.connect(lambda: self._open_file(file_path))
        
        self.ref_container.setFixedHeight(32) # Show container
        self.ref_layout.insertWidget(self.ref_layout.count() - 1, btn_doc)

    def _open_file(self, path: str):
        import os
        if os.path.exists(path):
            os.startfile(path)

    def append_log(self, text: str, level: str = "info"):
        """追加日志条目

        Args:
            text: 日志文本
            level: 日志级别 (info/error/success/warning)
        """
        color_map = {
            "info":    COLORS['accent_green'],
            "error":   COLORS['accent_red'],
            "success": COLORS['accent_green'],
            "warning": COLORS['accent_orange'],
        }
        color = color_map.get(level, COLORS['text_primary'])
        timestamp = ""  # 可扩展添加时间戳

        html = f'<span style="color: {color}; font-family: Cascadia Code, Consolas, monospace; font-size: 12px;">{text}</span><br>'
        self.log_console.append(html)

        # 自动滚动到底部
        cursor = self.log_console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_console.setTextCursor(cursor)

    def append_error_traceback(self, traceback_text: str):
        """追加错误 Traceback（红色高亮）"""
        self.append_log("❌ ───── ERROR TRACEBACK ─────", "error")
        for line in traceback_text.strip().split("\n"):
            self.append_log(f"  {line}", "error")
        self.append_log("❌ ──────────────────────────", "error")

    def set_status(self, text: str):
        """更新状态栏"""
        self.status_label.setText(text)

    def clear_code(self):
        """清空代码编辑器"""
        self.code_editor.clear()
        self.code_file_label.setText("")

    def clear_log(self):
        """清空日志控制台"""
        self.log_console.clear()
