"""
config package - AI-Lab-Commander 配置模块
重新导出settings.py中的所有配置，保持向后兼容性
"""

from .settings import (
    # API配置
    API_KEYS,
    AGENT_MODELS,
    AGENT_PROFILES,

    # 应用状态
    AppState,

    # 路径配置
    PROJECT_ROOT,
    DATA_DIR,
    SESSIONS_DIR,
    KNOWLEDGE_DIR,
    GENERATED_DOCS_DIR,
    WORKSPACE_ROOT,

    # UI配置
    APP_TITLE,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    FONT_FAMILY,
    FONT_SIZE_BASE,

    # 逻辑控制
    MAX_DEBATE_ROUNDS,

    # 配置验证
    validate_config,
)

# 为方便使用，也可以直接导入所有
__all__ = [
    'API_KEYS',
    'AGENT_MODELS',
    'AGENT_PROFILES',
    'AppState',
    'PROJECT_ROOT',
    'DATA_DIR',
    'SESSIONS_DIR',
    'KNOWLEDGE_DIR',
    'GENERATED_DOCS_DIR',
    'WORKSPACE_ROOT',
    'APP_TITLE',
    'WINDOW_MIN_WIDTH',
    'WINDOW_MIN_HEIGHT',
    'FONT_FAMILY',
    'FONT_SIZE_BASE',
    'MAX_DEBATE_ROUNDS',
    'validate_config',
]