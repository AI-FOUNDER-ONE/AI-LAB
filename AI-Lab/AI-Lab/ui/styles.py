"""
ui/styles.py - GitHub Dark Dimmed Theme System
==============================================
Strict pixel-perfect execution of GitHub-style aesthetics.
"""

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import QRegularExpression

# ---------- GitHub Dark Dimmed Palette ----------
COLORS = {
    'bg_primary': '#161B22',    # Panels / Cards (Lighter Dark)
    'bg_secondary': '#0D1117',  # App Background / Input Bg (Deep Dark)
    'bg_tertiary': '#21262d',   # Muted Blocks / Code (Lighter than Primary)
    'bg_terminal': '#000000',   # Pure Black for Execution Lab
    
    'text_primary': '#FFFFFF',  # Headers / Titles
    'text_secondary': '#C9D1D9',# Body / Main Text
    'text_tertiary': '#8B949E', # Muted / Labels
    
    'border': '#30363D',        # Borders
    
    'accent_green': '#238636',  # GitHub Green (Confirm Button)
    'accent_blue': '#58A6FF',   # GitHub Blue (Links/Icons)
    'accent_gold': '#F59E0B',   # Gold/Amber (CKO Accent)
    'accent_purple': '#8957e5', # GitHub Purple (Markdown Headers)
    'accent_orange': '#d29922', # GitHub Orange (Blockquotes)
    'accent_red': '#F85149',    # Red (Fail Status)
    'accent_primary': '#58A6FF',
    'accent_header': '#161B22',
}

def get_main_stylesheet() -> str:
    """Global Reset for GitHub Dark Mode"""
    return f"""
    QMainWindow {{
        background-color: {COLORS['bg_secondary']};
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
    QSplitter::handle {{
        background-color: {COLORS['border']};
        width: 1px;
        height: 1px;
    }}
    """

def get_navbar_style() -> str:
    """GitHub Header Style"""
    return f"""
    QFrame#navbar {{
        background-color: {COLORS['bg_primary']};
        border-bottom: 1px solid {COLORS['border']};
    }}
    QLabel#nav_title {{
        color: {COLORS['text_primary']};
        font-weight: 600;
        font-size: 14px;
    }}
    """

def get_panel_style(bg: str = None) -> str:
    """GitHub Card Style"""
    target_bg = bg if bg else COLORS['bg_primary']
    return f"""
    QFrame#panel {{
        background-color: {target_bg};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
    }}
    """

def get_header_style() -> str:
    """GitHub Small Label Header"""
    return f"""
    QLabel {{
        color: {COLORS['text_tertiary']};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }}
    """

def get_input_style() -> str:
    """GitHub Chat Bar Style"""
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
    """GitHub Button Variants"""
    if variant == "success": # GitHub Green
        bg = COLORS['accent_green']
        color = "#FFFFFF"
        border = "1px solid rgba(240, 246, 252, 0.1)"
        hover = "#2EA043"
    elif variant == "icon":
        bg = "transparent"
        color = COLORS['text_tertiary']
        border = "none"
        hover = "rgba(255, 255, 255, 0.1)"
    else: # Default Dark
        bg = "#21262D"
        color = COLORS['text_secondary']
        border = "1px solid #30363D"
        hover = "#30363D"
        
    return f"""
    QPushButton {{
        background-color: {bg};
        color: {color};
        border: {border};
        border-radius: 6px;
        padding: 4px 12px;
        font-weight: 600;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {hover if variant != "icon" else "rgba(255, 255, 255, 0.1)"};
        { "color: #FFFFFF;" if variant == "icon" else "" }
    }}
    """

def get_log_console_style() -> str:
    """GitHub Style Console"""
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
