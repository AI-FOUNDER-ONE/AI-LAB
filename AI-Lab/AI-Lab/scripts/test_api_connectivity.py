"""
test_api_connectivity.py — 各角色 API 联通测试
=================================================
逐个测试 6 个 Agent 的 LLM 端点是否可用。
"""
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 强制 UTF-8
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer)
    except Exception:
        pass

from config import API_KEYS, AGENT_MODELS

print("=" * 60)
print("[TEST] API 联通测试 - 6 个角色")
print("=" * 60)

# 显示配置信息
for role, cfg in AGENT_MODELS.items():
    key = API_KEYS.get(cfg["provider"], "")
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "(empty)"
    print(f"  {role:10s} | {cfg['provider']:15s} | {cfg['model']:25s} | {cfg.get('base_url','N/A'):35s} | key={masked}")

print("\n" + "-" * 60)

# 逐个测试
from langchain_openai import ChatOpenAI

ROLES = ["CKO", "PM", "Arch", "Designer", "Coder", "Tester"]
results = {}

for role in ROLES:
    cfg = AGENT_MODELS[role]
    provider = cfg["provider"]
    model = cfg["model"]
    base_url = cfg.get("base_url", "https://hiapi.online/v1")
    api_key = API_KEYS.get(provider, "")

    print(f"\n[{role}] Testing {provider}/{model} @ {base_url}...")

    if not api_key:
        print(f"  SKIP: No API key for provider '{provider}'")
        results[role] = "SKIP (no key)"
        continue

    try:
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
            max_tokens=30,
        )
        response = llm.invoke("Say 'OK' in one word.")
        content = response.content.strip()
        print(f"  OK: \"{content[:80]}\"")
        results[role] = "OK"
    except Exception as e:
        err = str(e)[:150]
        print(f"  FAIL: {err}")
        results[role] = f"FAIL: {err[:60]}"

# 汇总
print("\n" + "=" * 60)
print("[SUMMARY]")
print("=" * 60)
for role, status in results.items():
    icon = "OK" if status == "OK" else "FAIL" if "FAIL" in status else "SKIP"
    print(f"  {role:10s} : {icon} - {status}")
print()
