"""
ui/styles.py - 深色主题样式
==========================
面板、按钮、输入框、控制台等统一样式。
"""

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import QRegularExpression

# ---------- 色板（暗黑层次：底层极暗，面板提亮一级）----------
COLORS = {
    'bg_base': '#141414',       # 全局底层极暗灰黑
    'bg_panel': '#1F1F1F',     # 左中右三面板卡片（提亮一级）
    'bg_primary': '#252526',    # 侧栏
    'bg_secondary': '#1e1e1e',  # 主背景
    'bg_tertiary': '#2a2a2a',   # 悬浮/选中
    'bg_avatar': '#313131',     # 头像/图标底
    'bg_terminal': '#1e1e1e',
    'accent_primary_blue': '#1677FF',  # 确认立项等核心操作（科技蓝）
    
    'text_primary': '#CCCCCC',
    'text_secondary': '#CCCCCC',
    'text_tertiary': '#858585',
    
    'border': '#3c3c3c',
    'border_subtle': '#2a2a2a',
    
    'accent_green': '#3c8b7e',  # 柔和绿（确认立项不突兀）
    'accent_blue': '#569CD6',
    'accent_gold': '#DCDCAA',
    'accent_purple': '#C586C0',
    'accent_orange': '#CE9178',
    'accent_red': '#F14C4C',
    'accent_primary': '#569CD6',
    'accent_header': '#252526',
}

def get_main_stylesheet() -> str:
    """全局深色主题（底层极暗灰黑 #141414）"""
    return f"""
    QMainWindow {{
        background-color: {COLORS['bg_base']};
        color: {COLORS['text_secondary']};
    }}
    QWidget {{
        color: {COLORS['text_secondary']};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 13px;
        selection-background-color: #388BFD;
        selection-color: #FFFFFF;
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    /* Cursor 风格：分割条不显示线条，仅保留拖拽区域 */
    QSplitter::handle {{
        background: transparent;
        width: 1px;
        height: 1px;
        max-width: 1px;
        max-height: 1px;
    }}
    """

def get_navbar_style() -> str:
    """顶栏样式（Cursor 风：无底边线）"""
    return f"""
    QFrame#navbar {{
        background-color: {COLORS['bg_primary']};
        border: none;
    }}
    QLabel#nav_title {{
        color: {COLORS['text_primary']};
        font-weight: 500;
        font-size: 13px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        background: transparent;
        border: none;
    }}
    """

def get_panel_style(bg: str = None) -> str:
    """左中右三面板卡片：提亮一级 #1F1F1F，细边框，8px 圆角"""
    target_bg = bg if bg else COLORS['bg_panel']
    return f"""
    QFrame#panel {{
        background-color: {target_bg};
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
    }}
    """

def get_header_style() -> str:
    """面板小标题样式（Cursor 字体与色），背景透明以透出面板"""
    return f"""
    QLabel {{
        color: {COLORS['text_tertiary']};
        font-size: 11px;
        font-weight: 500;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        background: transparent;
        border: none;
    }}
    """

def get_input_style() -> str:
    """输入框样式"""
    return f"""
    QTextEdit, QLineEdit {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px;
        font-size: 13px;
    }}
    QTextEdit:focus, QLineEdit:focus {{
        border: 1px solid {COLORS['accent_blue']};
    }}
    """

def get_button_style(variant: str = "primary") -> str:
    """按钮样式（含确认立项科技蓝 + Hover 提亮）"""
    if variant == "success":
        # 确认立项：科技感主题蓝 #1677FF，白字，Hover 提亮
        bg = COLORS.get('accent_primary_blue', '#1677FF')
        color = "#FFFFFF"
        border = "none"
        hover = "#4096FF"
    elif variant == "icon":
        bg = "transparent"
        color = COLORS['text_tertiary']
        border = "none"
        hover = "rgba(255, 255, 255, 0.08)"
    else:
        bg = COLORS['bg_tertiary']
        color = COLORS['text_primary']
        border = "none"
        hover = "#3c3c3c"
    return f"""
    QPushButton {{
        background-color: {bg};
        color: {color};
        border: {border};
        border-radius: 4px;
        padding: 6px 14px;
        font-weight: 500;
        font-size: 13px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    }}
    QPushButton:hover {{
        background-color: {hover};
        color: {color};
    }}
    QPushButton:pressed {{
        background-color: #505050;
    }}
    QPushButton:disabled {{
        background-color: #2a2a2a;
        color: #666666;
    }}
    """

def get_log_console_style() -> str:
    """运行控制台样式"""
    return f"""
    QTextEdit {{
        background-color: {COLORS['bg_terminal']};
        color: #B2B2B2;
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        font-family: 'SFMono-Regular', Consolas, monospace;
        font-size: 12px;
        padding: 8px;
    }}
    """

def get_code_editor_style() -> str:
    """GitHub Editor (Terminal/Code View)"""
    return f"""
    QPlainTextEdit {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        font-family: 'ui-monospace', 'SFMono-Regular', 'SF Mono', 'Menlo', 'Consolas', 'Liberation Mono', monospace;
        font-size: 13px;
        padding: 8px;
    }}
    """

def get_audit_stamp_style(status: str) -> str:
    color = "#3FB950" if status == "PASS" else "#F85149"
    return f"""
        color: {color};
        border: 1px solid {color};
        border-radius: 4px;
        font-size: 10px;
        font-weight: 800;
        padding: 2px 4px;
        background: transparent;
    """

def get_thinking_style() -> str:
    return f"""
    QTextEdit {{
        background-color: transparent;
        color: {COLORS['text_tertiary']};
        font-style: italic;
        border: none;
    }}
    """

def get_chat_bubble_css(bg_color: str, is_user: bool) -> str:
    return f"""
        background-color: {bg_color};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px;
    """

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#FF7B72")) # GitHub Red/Orange
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = ["def", "class", "if", "else", "elif", "while", "for", "return", "import", "from"]
        for word in keywords:
            pattern = QRegularExpression(f"\\b{word}\\b")
            self.highlighting_rules.append((pattern, keyword_format))
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#A5D6FF")) # GitHub Blue
        self.highlighting_rules.append((QRegularExpression("\".*\""), string_format))
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#8B949E")) # Grey
        self.highlighting_rules.append((QRegularExpression("#[^\n]*"), comment_format))
