import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

def probe(method, url, headers, payload=None):
    try:
        print(f"\n{method} {url} ...")
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        else:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:1000]}") # Print more
        return resp.status_code
    except Exception as e:
        print(f"Error: {e}")
        return -1

def main():
    api_key = os.getenv("CLAUDE_CUSTOM_API_KEY")
    base = "https://yunyi.rdzhvip.com/claude"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    # 1. Check Models (confirmed working?)
    probe("GET", f"{base}/v1/models", headers)
    
    # 2. Check Chat Completions (OpenAI)
    payload = {
        "model": "claude-opus-4.6", # Try exact model user gave, or one from list if found
        "messages": [{"role": "user", "content": "hi"}]
    }
    probe("POST", f"{base}/v1/chat/completions", headers, payload)
    
    # 3. Check Chat Completions (without v1)
    probe("POST", f"{base}/chat/completions", headers, payload)

if __name__ == "__main__":
    main()
