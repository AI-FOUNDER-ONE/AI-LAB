"""Verify Kimi Model Basic Connectivity (No Tools)"""
import os
import sys
import requests
import json
sys.path.insert(0, ".")
from config import API_KEYS

api_key = API_KEYS["volcengine"]
base_url = "https://ark.cn-beijing.volces.com/api/v3"
model = "kimi-k2-thinking-251104"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "stream": False,
    "messages": [
        {"role": "user", "content": "Hello Kimi"}
    ]
    # No tools
}

print(f"Testing Payload (No Tools): {json.dumps(payload, ensure_ascii=False)}")

url = f"{base_url}/chat/completions"
print(f"\nPOST {url}")
try:
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
