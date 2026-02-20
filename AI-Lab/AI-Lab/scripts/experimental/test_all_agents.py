"""
test_all_agents.py - 6 角色 AI 调用连通性测试
==============================================
直接通过 HTTP API 测试每个 Agent 的 LLM 调用是否正常,
不依赖 crewai 框架, 仅使用 openai SDK 和 anthropic SDK。

安全性审计:
  ✅ API 密钥通过 config.py 统一管理
  ✅ 所有请求使用 HTTPS
  ✅ 敏感信息不打印到日志
"""

import sys
import os
import time
import json

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import API_KEYS, AGENT_MODELS

# ---------- 测试用提示词 ----------
TEST_PROMPT = "请用一句话介绍你自己的角色。"

# ---------- 结果存储 ----------
results = {}


def mask_key(key: str) -> str:
    """遮盖 API 密钥, 仅显示前4和后4位"""
    if not key or len(key) < 10:
        return "*** (未配置)"
    return f"{key[:4]}****{key[-4:]}"


def test_openai_compatible(role: str, cfg: dict) -> dict:
    """测试 OpenAI 兼容 API (deepseek / volcengine / hiapi)
    
    Args:
        role: 角色名
        cfg: 模型配置字典
        
    Returns:
        dict: 包含 success, response, latency, error 的结果
    """
    try:
        from openai import OpenAI
    except ImportError:
        return {"success": False, "error": "openai SDK 未安装", "latency": 0}
    
    provider = cfg["provider"]
    model = cfg["model"]
    base_url = cfg.get("base_url", "")
    api_key = API_KEYS.get(provider, "")
    
    if not api_key:
        return {"success": False, "error": f"API Key 未配置 (provider={provider})", "latency": 0}
    
    print(f"  → 使用 OpenAI 兼容模式: {base_url}")
    print(f"  → 模型: {model}")
    print(f"  → Key: {mask_key(api_key)}")
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"你是 AI-Lab 的 {role} 角色。"},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=200,
            temperature=0.7,
            timeout=30,
        )
        latency = round(time.time() - start, 2)
        content = response.choices[0].message.content.strip()
        return {"success": True, "response": content, "latency": latency}
    except Exception as e:
        latency = round(time.time() - start, 2)
        return {"success": False, "error": str(e)[:200], "latency": latency}


def test_xai(role: str, cfg: dict) -> dict:
    """测试 xAI (Grok) API
    
    Args:
        role: 角色名
        cfg: 模型配置字典
        
    Returns:
        dict: 包含 success, response, latency, error 的结果
    """
    try:
        from openai import OpenAI
    except ImportError:
        return {"success": False, "error": "openai SDK 未安装", "latency": 0}
    
    model = cfg["model"]
    base_url = cfg.get("base_url", "https://api.x.ai/v1")
    api_key = API_KEYS.get("xai", "")
    
    if not api_key:
        return {"success": False, "error": "XAI_API_KEY 未配置", "latency": 0}
    
    print(f"  → 使用 xAI 模式: {base_url}")
    print(f"  → 模型: {model}")
    print(f"  → Key: {mask_key(api_key)}")
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"你是 AI-Lab 的 {role} 角色。"},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=200,
            temperature=0.7,
            timeout=30,
        )
        latency = round(time.time() - start, 2)
        content = response.choices[0].message.content.strip()
        return {"success": True, "response": content, "latency": latency}
    except Exception as e:
        latency = round(time.time() - start, 2)
        return {"success": False, "error": str(e)[:200], "latency": latency}


def test_anthropic(role: str, cfg: dict) -> dict:
    """测试 Anthropic (Claude) API (通过 yunyi 代理)
    
    Args:
        role: 角色名
        cfg: 模型配置字典
        
    Returns:
        dict: 包含 success, response, latency, error 的结果
    """
    try:
        import anthropic
    except ImportError:
        # Fallback: 使用 openai SDK 兼容模式调用 yunyi
        return _test_anthropic_via_openai(role, cfg)
    
    model = cfg["model"]
    base_url = cfg.get("base_url", "")
    api_key = API_KEYS.get("claude_custom", "")
    
    if not api_key:
        return {"success": False, "error": "CLAUDE_CUSTOM_API_KEY 未配置", "latency": 0}
    
    print(f"  → 使用 Anthropic SDK: {base_url}")
    print(f"  → 模型: {model}")
    print(f"  → Key: {mask_key(api_key)}")
    
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    
    start = time.time()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            system=[{"type": "text", "text": f"你是 AI-Lab 的 {role} 角色。"}],
            messages=[
                {"role": "user", "content": TEST_PROMPT}
            ],
        )
        latency = round(time.time() - start, 2)
        content = response.content[0].text.strip()
        return {"success": True, "response": content, "latency": latency}
    except Exception as e:
        latency = round(time.time() - start, 2)
        return {"success": False, "error": str(e)[:200], "latency": latency}


def _test_anthropic_via_openai(role: str, cfg: dict) -> dict:
    """当 anthropic SDK 不可用时, 使用 openai SDK 兼容模式"""
    try:
        from openai import OpenAI
    except ImportError:
        return {"success": False, "error": "openai 和 anthropic SDK 均未安装", "latency": 0}
    
    model = cfg["model"]
    base_url = cfg.get("base_url", "")
    api_key = API_KEYS.get("claude_custom", "")
    
    if not api_key:
        return {"success": False, "error": "CLAUDE_CUSTOM_API_KEY 未配置", "latency": 0}
    
    print(f"  → 使用 OpenAI 兼容模式调用 yunyi: {base_url}")
    print(f"  → 模型: {model}")
    
    # yunyi 代理也支持 /v1/chat/completions 格式
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"你是 AI-Lab 的 {role} 角色。"},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=200,
            timeout=30,
        )
        latency = round(time.time() - start, 2)
        content = response.choices[0].message.content.strip()
        return {"success": True, "response": content, "latency": latency}
    except Exception as e:
        latency = round(time.time() - start, 2)
        return {"success": False, "error": str(e)[:200], "latency": latency}


def run_test(role: str) -> dict:
    """根据角色配置自动选择测试方法
    
    Args:
        role: 角色名 (CKO/PM/Arch/Designer/Coder/Tester)
        
    Returns:
        dict: 测试结果
    """
    cfg = AGENT_MODELS.get(role)
    if not cfg:
        return {"success": False, "error": f"角色 {role} 未在 AGENT_MODELS 中配置", "latency": 0}
    
    provider = cfg["provider"]
    api_type = cfg.get("api_type", "openai")
    
    # 根据 provider/api_type 路由到对应测试函数
    if api_type == "anthropic":
        return test_anthropic(role, cfg)
    elif provider == "xai":
        return test_xai(role, cfg)
    else:
        # OpenAI 兼容 (deepseek, volcengine, hiapi, qwen 等)
        return test_openai_compatible(role, cfg)


def main():
    """主测试入口 - 依次测试 6 个角色"""
    print("=" * 68)
    print("  AI-Lab-Commander · 6 角色 AI 调用连通性测试")
    print("=" * 68)
    print()
    
    roles = ["CKO", "PM", "Arch", "Designer", "Coder", "Tester"]
    
    for i, role in enumerate(roles, 1):
        cfg = AGENT_MODELS.get(role, {})
        provider = cfg.get("provider", "?")
        model = cfg.get("model", "?")
        
        print(f"[{i}/6] 🧪 测试 {role} ({provider}/{model})")
        print("-" * 50)
        
        result = run_test(role)
        results[role] = result
        
        if result["success"]:
            print(f"  ✅ 成功 ({result['latency']}s)")
            # 截取回复前80字符展示
            preview = result["response"][:80].replace("\n", " ")
            print(f"  💬 \"{preview}...\"")
        else:
            print(f"  ❌ 失败 ({result['latency']}s)")
            print(f"  ⚠️  {result['error']}")
        
        print()
    
    # ---------- 汇总报告 ----------
    print("=" * 68)
    print("  📊 测试汇总报告")
    print("=" * 68)
    
    success_count = sum(1 for r in results.values() if r["success"])
    total = len(results)
    
    for role, result in results.items():
        cfg = AGENT_MODELS.get(role, {})
        status = "✅" if result["success"] else "❌"
        latency = f"{result['latency']}s"
        provider = cfg.get("provider", "?")
        model = cfg.get("model", "?")
        print(f"  {status} {role:10s} | {provider:15s} | {model:30s} | {latency}")
    
    print(f"\n  结果: {success_count}/{total} 通过")
    
    if success_count == total:
        print("  🎉 所有角色 AI 调用正常!")
    else:
        failed = [r for r, v in results.items() if not v["success"]]
        print(f"  ⚠️  失败角色: {', '.join(failed)}")
    
    print("=" * 68)
    return success_count == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
