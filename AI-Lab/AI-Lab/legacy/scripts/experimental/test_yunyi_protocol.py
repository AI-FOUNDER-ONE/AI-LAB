"""直接测试 yunyi 代理的两种 API 协议"""
import sys, os, json
sys.path.insert(0, ".")
from config import API_KEYS, AGENT_MODELS
import httpx

cfg = AGENT_MODELS["Coder"]
api_key = API_KEYS[cfg["provider"]]
base_url = cfg["base_url"]

print(f"Coder config: {cfg}")
print(f"API key: {api_key[:8]}...{api_key[-4:]}")
print(f"Base URL: {base_url}")

# Test 1: Anthropic /v1/messages 格式
print("\n" + "=" * 50)
print("Test 1: Anthropic /v1/messages 格式")
print("=" * 50)
try:
    url = f"{base_url}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": cfg["model"],
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Say OK"}]
    }
    print(f"  POST {url}")
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:300]}")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 2: OpenAI /v1/chat/completions 格式
print("\n" + "=" * 50)
print("Test 2: OpenAI /v1/chat/completions 格式")
print("=" * 50)
try:
    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json"
    }
    payload = {
        "model": cfg["model"],
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Say OK"}]
    }
    print(f"  POST {url}")
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:300]}")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 3: Anthropic /v1/messages with system param (like CrewAI sends)
print("\n" + "=" * 50)
print("Test 3: Anthropic /v1/messages + system (CrewAI 格式)")
print("=" * 50)
try:
    url = f"{base_url}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": cfg["model"],
        "max_tokens": 100,
        "system": "You are a helpful coder.",
        "messages": [{"role": "user", "content": "Say OK"}]
    }
    print(f"  POST {url}")
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:300]}")
except Exception as e:
    print(f"  FAILED: {e}")
