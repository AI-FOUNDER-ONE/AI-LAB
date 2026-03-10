#!/usr/bin/env python3
"""
检查各 AI 角色所需的 API Key 是否已配置。
在项目根目录执行: uv run python scripts/check_api_keys.py
"""
import os
import sys

# 确保从项目根加载 .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import API_KEYS, AGENT_MODELS

# provider 名称 -> 环境变量名（与 settings.py 一致）
PROVIDER_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "xai": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "deepseek_tester": "DEEPSEEK_TESTER_API_KEY",
    "zhipuai": "ZHIPUAI_API_KEY",
    "qwen": "QWEN_API_KEY",
    "hiapi": "HIAPI_API_KEY",
    "claude_custom": "CLAUDE_CUSTOM_API_KEY",
    "volcengine": "VOLCENGINE_API_KEY",
    "novai": "NOVAI_API_KEY",
    "bigmodel": "BIGMODEL_API_KEY",
}


def main():
    missing = []
    ok = []
    for role, cfg in AGENT_MODELS.items():
        provider = cfg.get("provider", "")
        if not provider:
            missing.append((role, "", "未配置 provider"))
            continue
        key_value = API_KEYS.get(provider, "")
        env_name = PROVIDER_ENV.get(provider, f"{provider.upper()}_API_KEY")
        if not (key_value and key_value.strip()):
            missing.append((role, env_name, provider))
        else:
            ok.append((role, env_name))

    print("=== AI 角色 API Key 检查 ===\n")
    if missing:
        print("缺失 API Key 的角色：")
        for role, env_name, prov in missing:
            print(f"  • {role:12} -> 请设置环境变量: {env_name}  (provider: {prov})")
        print()
    if ok:
        print("已配置 API Key 的角色：")
        for role, env_name in ok:
            print(f"  • {role:12} -> {env_name}")
    if missing:
        print("\n请在项目根目录的 .env 文件中添加上述变量（可参考 .env.example）。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
