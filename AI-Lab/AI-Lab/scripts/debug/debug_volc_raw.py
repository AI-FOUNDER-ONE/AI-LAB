"""Debug Volcengine Kimi Web Search Payload"""
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
        {"role": "user", "content": "今天有什么热点新闻"}
    ],
    "tools": [
        {
            "type": "web_search",
            "max_keyword": 3
        }
    ]
}

print(f"Testing Payload: {json.dumps(payload, ensure_ascii=False)}")

# Test 1: Standard OpenAI Endpoint /chat/completions
url1 = f"{base_url}/chat/completions"
print(f"\n[Test 1] POST {url1}")
try:
    resp = requests.post(url1, headers=headers, json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: User provided endpoint /responses ? (Checking if valid)
# User wrote: curl https://ark.cn-beijing.volces.com/api/v3/responses
url2 = "https://ark.cn-beijing.volces.com/api/v3/responses" 
# Note: /responses might be for Bot API or something specific?
print(f"\n[Test 2] POST {url2}")
try:
    # User example used "input" instead of "messages"?
    # User payload:
    # {
    #     "model": "...",
    #     "input": [{ "role": "user", "content": [...] }]
    # }
    # Let's try user's exact structure for Test 2
    payload2 = {
        "model": model,
        "stream": False,
        "tools": [{"type": "web_search", "max_keyword": 3}],
        "input": [ # Note: "input" instead of "messages"
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "今天有什么热点新闻"}]
            }
        ]
    }
    resp = requests.post(url2, headers=headers, json=payload2, timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

