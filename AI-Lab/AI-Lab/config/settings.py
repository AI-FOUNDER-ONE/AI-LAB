"""
config.py - AI-Lab-Commander 全局配置
=============================================
从 .env 文件安全加载 API 密钥，定义角色映射与全局常量。
"""

import os
from dotenv import load_dotenv

# ---------- 加载环境变量 ----------
load_dotenv()

API_KEYS = {
    "gemini": os.getenv("GEMINI_API_KEY", ""),
    "openai": os.getenv("OPENAI_API_KEY", ""),
    "xai": os.getenv("XAI_API_KEY", ""),
    "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
    "deepseek_tester": os.getenv("DEEPSEEK_TESTER_API_KEY", ""),
    "zhipuai": os.getenv("ZHIPUAI_API_KEY", ""),
    "qwen": os.getenv("QWEN_API_KEY", ""),
    "hiapi": os.getenv("HIAPI_API_KEY", ""),
    "claude_custom": os.getenv("CLAUDE_CUSTOM_API_KEY", ""),
    "volcengine": os.getenv("VOLCENGINE_API_KEY", ""),  # 火山引擎 Ark API
    "novai": os.getenv("NOVAI_API_KEY", ""),            # NovAI Gemini 代理
    "bigmodel": os.getenv("BIGMODEL_API_KEY", ""),      # BigModel (ZhipuAI Coding)
}

# ---------- 角色 → 模型 映射 ----------
AGENT_MODELS = {
    "CKO":      {"provider": "novai",           "model": "gemini-3-pro-preview", "base_url": "https://once.novai.su/v1"},
    "QA":       {"provider": "deepseek",       "model": "deepseek-reasoner",        "base_url": "https://api.deepseek.com"},
    "PM":       {"provider": "xai",            "model": "grok-4-1-fast-reasoning",  "base_url": "https://api.x.ai/v1"},
    "Arch":     {"provider": "volcengine",     "model": "doubao-seed-2-0-pro-260215", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "Designer": {"provider": "deepseek",       "model": "deepseek-reasoner",        "base_url": "https://api.deepseek.com"},
    "Coder":    {"provider": "bigmodel",       "model": "glm-5",                    "base_url": "https://open.bigmodel.cn/api/coding/paas/v4"},
    "Validator":{"provider": "deepseek",       "model": "deepseek-reasoner",        "base_url": "https://api.deepseek.com"},
}

# ---------- 角色颜色与显示名 (Monochrome/Technical) ----------
AGENT_PROFILES = {
    "CKO":      {"name": "CKO",      "color": "#64748B", "icon": "◉"}, # Slate-500
    "QA":       {"name": "QA",       "color": "#0D9488", "icon": "🛡️"}, # Teal-600
    "PM":       {"name": "PM",       "color": "#475569", "icon": "▲"}, # Slate-600
    "Arch":     {"name": "Arch",     "color": "#334155", "icon": "◆"}, # Slate-700
    "Designer": {"name": "Designer", "color": "#1E293B", "icon": "■"}, # Slate-800
    "Coder":    {"name": "Coder",    "color": "#0F172A", "icon": "●"}, # Slate-900
    "Validator":{"name": "Validator","color": "#94A3B8", "icon": "◈"}, # Slate-400
    "Commander":{"name": "Commander","color": "#58A6FF", "icon": "👤"},
    "System":   {"name": "System",   "color": "#8B949E", "icon": "⚙️"},
}

# ---------- 状态机阶段定义 ----------
class AppState:
    """状态机阶段枚举"""
    IDLE         = "IDLE"           # 空闲状态
    GROUNDING    = "GROUNDING"      # CKO 需求打磨阶段
    DEBATE       = "DEBATE"         # PM/Arch/Designer 方案博弈阶段
    PRODUCTION   = "PRODUCTION"     # Coder 编码阶段
    VERIFICATION = "VERIFICATION"   # Validator 验证阶段
    DELIVERY     = "DELIVERY"       # 交付汇总阶段
    COMPLETED    = "COMPLETED"      # 任务完成

# ---------- 路径配置 ----------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
GENERATED_DOCS_DIR = os.path.join(DATA_DIR, "generated_docs")

# 确保数据目录存在
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
os.makedirs(GENERATED_DOCS_DIR, exist_ok=True)

# ---------- UI 全局常量 ----------
APP_TITLE = "AI-Lab-Commander · AI 多角色协作平台"
WINDOW_MIN_WIDTH = 1400
WINDOW_MIN_HEIGHT = 900
FONT_FAMILY = "Microsoft YaHei UI"
FONT_SIZE_BASE = 12

# ---------- 逻辑控制 ----------
MAX_DEBATE_ROUNDS = 999  # 最大博弈交互轮次 (解除限制)


# ---------- 配置验证函数 ----------
def validate_config():
    """验证配置完整性，检查必需的API密钥"""
    import logging
    logger = logging.getLogger("ai_lab.config")

    missing_keys = []
    for key_name, key_value in API_KEYS.items():
        if not key_value:
            missing_keys.append(key_name)

    if missing_keys:
        logger.warning(f"以下API密钥未配置: {', '.join(missing_keys)}")
        logger.warning("部分功能可能受限")

    # 检查必需的角色模型配置
    required_roles = ["CKO", "QA", "PM", "Arch", "Designer", "Coder", "Validator"]
    missing_roles = []
    for role in required_roles:
        if role not in AGENT_MODELS:
            missing_roles.append(role)

    if missing_roles:
        logger.error(f"以下角色缺少模型配置: {', '.join(missing_roles)}")
        return False

    return True


def get_api_key(provider: str) -> str:
    """安全获取API密钥，提供缺失时的警告"""
    key = API_KEYS.get(provider, "")
    if not key:
        import logging
        logger = logging.getLogger("ai_lab.config")
        logger.warning(f"API密钥缺失: {provider}")

    return key


def check_model_config(role: str) -> dict:
    """获取角色模型配置，验证完整性"""
    config = AGENT_MODELS.get(role, {})
    if not config:
        import logging
        logger = logging.getLogger("ai_lab.config")
        logger.error(f"角色配置缺失: {role}")
        return {}

    required_fields = ["provider", "model"]
    missing_fields = [field for field in required_fields if field not in config]

    if missing_fields:
        import logging
        logger = logging.getLogger("ai_lab.config")
        logger.error(f"角色 {role} 配置不完整，缺少字段: {', '.join(missing_fields)}")
        return {}

    return config


def list_available_providers() -> list:
    """列出已配置API密钥的可用提供者"""
    return [provider for provider, key in API_KEYS.items() if key]


# 应用启动时自动验证配置
if __name__ != "__main__":
    # 只有在被导入时运行验证
    validate_config()
