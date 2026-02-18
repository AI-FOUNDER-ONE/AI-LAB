"""诊断 PM grok-4-0709 参数兼容性问题"""
import sys, os
sys.path.insert(0, ".")
from config import API_KEYS, AGENT_MODELS

cfg = AGENT_MODELS["PM"]
api_key = API_KEYS[cfg["provider"]]

# 测试1: 直接用 litellm 调用，捕获完整错误
import litellm
litellm.set_verbose = True

try:
    resp = litellm.completion(
        model=f"openai/{cfg['model']}",
        api_key=api_key,
        api_base=cfg["base_url"],
        messages=[{"role": "user", "content": "Say OK"}],
        temperature=0.7,
    )
    print(f"Test1 OK: {resp.choices[0].message.content}")
except Exception as e:
    print(f"Test1 FAIL: {e}")

# 测试2: 不带 temperature
try:
    resp = litellm.completion(
        model=f"openai/{cfg['model']}",
        api_key=api_key,
        api_base=cfg["base_url"],
        messages=[{"role": "user", "content": "Say OK"}],
    )
    print(f"Test2 (no temp) OK: {resp.choices[0].message.content}")
except Exception as e:
    print(f"Test2 FAIL: {e}")
