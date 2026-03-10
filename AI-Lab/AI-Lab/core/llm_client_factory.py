"""
core/llm_client_factory.py - 统一 LLM 客户端工厂
================================================
根据 provider 创建 OpenAI 兼容客户端，供各 Agent 复用。
"""

from config import API_KEYS

# provider -> (api_key_name, base_url 或 None 表示从 model_config 取/默认)
_PROVIDER_CONFIG = {
    "deepseek": ("deepseek", "https://api.deepseek.com"),
    "xai": ("xai", "https://api.x.ai/v1"),
    "qwen": ("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "hiapi": ("hiapi", "https://hiapi.online/v1"),
    "openai": ("openai", None),
}


def create_llm_client(provider: str, model_config: dict):
    """根据 provider 创建 OpenAI 兼容客户端。

    Args:
        provider: 提供商名称，如 deepseek, xai, qwen, bigmodel, novai, volcengine, hiapi, openai
        model_config: 模型配置 dict，可含 base_url（bigmodel/novai/volcengine 会从此取）

    Returns:
        openai.OpenAI 实例，统一 max_retries=5

    Raises:
        ValueError: 不支持的 provider
        ValueError: 对应 API key 未配置
    """
    from openai import OpenAI

    if provider in _PROVIDER_CONFIG:
        api_key_name, base_url = _PROVIDER_CONFIG[provider]
        api_key = API_KEYS.get(api_key_name, "")
        if not api_key:
            raise ValueError(f"{api_key_name.upper()}_API_KEY 未配置")
        kwargs = {"api_key": api_key, "max_retries": 5}
        if base_url is not None:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

    if provider == "bigmodel":
        api_key = API_KEYS.get("bigmodel", "")
        if not api_key:
            raise ValueError("BIGMODEL_API_KEY 未配置")
        base_url = model_config.get("base_url", "https://open.bigmodel.cn/api/coding/paas/v4")
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=5)

    if provider == "novai":
        api_key = API_KEYS.get("novai", "")
        if not api_key:
            raise ValueError("NOVAI_API_KEY 未配置")
        base_url = model_config.get("base_url", "https://once.novai.su/v1")
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=5)

    if provider == "volcengine":
        api_key = API_KEYS.get("volcengine", "")
        if not api_key:
            raise ValueError("VOLCENGINE_API_KEY 未配置")
        base_url = model_config.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=5)

    raise ValueError(f"不支持的 provider: {provider}")
