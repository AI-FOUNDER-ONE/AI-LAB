"""
execution_panel.py - 执行区
===========================
右侧面板：展示 Coder 产出代码（语法高亮）与 Validator 运行日志（终端风格）。
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

# 执行区代码/控制台：嵌入感与等宽字体
INNER_BG = "#0D0D0D"
INNER_BORDER = "#333333"
MONO_FONT = "'Fira Code', 'SF Mono', Consolas, 'Courier New', monospace"
# Mac 风格顶栏三色点
TRAFFIC_RED, TRAFFIC_YELLOW, TRAFFIC_GREEN = "#FF5F57", "#FEBC2E", "#28C840"


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
        """执行区与左中右三面板统一：提亮一级 #1F1F1F + 细边框 + 8px 圆角"""
        self.setObjectName("panel")
        self.setStyleSheet(get_panel_style())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. 标题
        self.header_label = QLabel("执行区")
        self.header_label.setStyleSheet(get_header_style())
        layout.addWidget(self.header_label)

        # 2. 编辑器与日志分割（Cursor 风格：1px 细线）
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background: transparent; height: 1px; max-height: 1px; }
        """)

        # 参考文档区（顶部）
        self.ref_container = QWidget()
        self.ref_container.setFixedHeight(0)
        self.ref_layout = QHBoxLayout(self.ref_container)
        self.ref_layout.setContentsMargins(0, 0, 0, 4)
        self.ref_layout.setSpacing(8)
        
        ref_label = QLabel("🔗 参考:")
        ref_label.setStyleSheet("color: #8B949E; font-size: 10px; font-weight: 700;")
        self.ref_layout.addWidget(ref_label)
        
        self.code_file_label = QLabel("")
        self.code_file_label.setStyleSheet("color: #58A6FF; font-size: 10px; font-weight: bold;")
        self.ref_layout.addWidget(self.code_file_label)
        
        self.ref_layout.addStretch()
        
        layout.addWidget(self.ref_container)

        # 源代码编辑区：Mac 风格顶栏（红黄绿点 + Code Tab）+ 嵌入感内容区
        editor_container = QFrame()
        editor_container.setStyleSheet(f"""
            QFrame {{ background-color: #1a1a1a; border: 1px solid {INNER_BORDER}; border-radius: 6px; }}
        """)
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        # 顶栏：仅用底边线区分层级，背景透明与卡片融合
        editor_bar = QWidget()
        editor_bar.setFixedHeight(28)
        editor_bar.setStyleSheet("background: transparent; border-bottom: 1px solid #333; border-radius: 6px 6px 0 0;")
        bar_layout = QHBoxLayout(editor_bar)
        bar_layout.setContentsMargins(10, 0, 8, 0)
        bar_layout.setSpacing(6)
        for c in (TRAFFIC_RED, TRAFFIC_YELLOW, TRAFFIC_GREEN):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background-color: {c}; border: none; border-radius: 5px;")
            bar_layout.addWidget(dot)
        bar_layout.addSpacing(8)
        code_tab = QLabel("Code")
        code_tab.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 600; background: transparent;")
        bar_layout.addWidget(code_tab)
        bar_layout.addStretch()
        editor_layout.addWidget(editor_bar)
        # 内容区：深底 #0D0D0D、#333 边框、等宽字体
        code_inner = QFrame()
        code_inner.setStyleSheet(f"""
            QFrame {{
                background-color: {INNER_BG};
                border: 1px solid {INNER_BORDER};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        code_inner_layout = QVBoxLayout(code_inner)
        code_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.code_editor = QPlainTextEdit()
        self.code_editor.setReadOnly(True)
        self.code_editor.setPlaceholderText("/* 代码将在此显示… */")
        self.code_editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {INNER_BG};
                color: #C9D1D9;
                border: none;
                font-family: {MONO_FONT};
                font-size: 13px;
                padding: 10px;
            }}
        """)
        self.code_editor.setFont(QFont("Fira Code", 13))
        self._highlighter = PythonHighlighter(self.code_editor.document())
        code_inner_layout.addWidget(self.code_editor)
        editor_layout.addWidget(code_inner)
        self.splitter.addWidget(editor_container)

        # 运行控制台：顶栏（红黄绿点 + Terminal Tab）+ 嵌入感内容区
        logs_container = QFrame()
        logs_container.setStyleSheet(f"""
            QFrame {{ background-color: #1a1a1a; border: 1px solid {INNER_BORDER}; border-radius: 6px; }}
        """)
        logs_layout = QVBoxLayout(logs_container)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(0)
        logs_bar = QWidget()
        logs_bar.setFixedHeight(28)
        logs_bar.setStyleSheet("background: transparent; border-bottom: 1px solid #333; border-radius: 6px 6px 0 0;")
        logs_bar_layout = QHBoxLayout(logs_bar)
        logs_bar_layout.setContentsMargins(10, 0, 8, 0)
        logs_bar_layout.setSpacing(6)
        for c in (TRAFFIC_RED, TRAFFIC_YELLOW, TRAFFIC_GREEN):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background-color: {c}; border: none; border-radius: 5px;")
            logs_bar_layout.addWidget(dot)
        logs_bar_layout.addSpacing(8)
        term_tab = QLabel("Terminal")
        term_tab.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 600; background: transparent;")
        logs_bar_layout.addWidget(term_tab)
        logs_bar_layout.addStretch()
        logs_layout.addWidget(logs_bar)
        logs_inner = QFrame()
        logs_inner.setStyleSheet(f"""
            QFrame {{
                background-color: {INNER_BG};
                border: 1px solid {INNER_BORDER};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        logs_inner_layout = QVBoxLayout(logs_inner)
        logs_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("> 等待执行…")
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {INNER_BG};
                color: #B2B2B2;
                border: none;
                font-family: {MONO_FONT};
                font-size: 12px;
                padding: 10px;
            }}
        """)
        self.log_console.setFont(QFont("Fira Code", 12))
        logs_inner_layout.addWidget(self.log_console)
        logs_layout.addWidget(logs_inner)
        self.splitter.addWidget(logs_container)

        self.splitter.setSizes([600, 200])
        layout.addWidget(self.splitter)
        layout.setStretchFactor(self.splitter, 1)

        # 状态栏
        self.status_label = QLabel("终端空闲")
        self.status_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; background: transparent; border: none;")
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
        """在顶部栏添加参考文档链接"""
        import os
        filename = os.path.basename(file_path)
        
        btn_doc = QPushButton(f"📄 {filename}")
        btn_doc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_doc.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['accent_blue']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {COLORS['border_subtle']};
            }}
        """)
        btn_doc.clicked.connect(lambda: self._open_file(file_path))
        
        self.ref_container.setFixedHeight(32)
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
        self.append_log("❌ ───── 错误堆栈 ─────", "error")
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
