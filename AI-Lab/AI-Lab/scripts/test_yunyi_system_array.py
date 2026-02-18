"""验证 yunyi 是否接受数组格式的 system 参数"""
import sys
sys.path.insert(0, ".")
from config import API_KEYS, AGENT_MODELS
import httpx

cfg = AGENT_MODELS["Coder"]
api_key = API_KEYS[cfg["provider"]]
base_url = cfg["base_url"]

# Test: system 以数组格式传递
url = f"{base_url}/v1/messages"
headers = {
    "x-api-key": api_key,
    "content-type": "application/json",
    "anthropic-version": "2023-06-01"
}
payload = {
    "model": cfg["model"],
    "max_tokens": 100,
    "system": [{"type": "text", "text": "You are a helpful coder."}],
    "messages": [{"role": "user", "content": "Say OK"}]
}
print(f"POST {url}")
resp = httpx.post(url, json=payload, headers=headers, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:300]}")
