import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

def probe(url, headers, payload):
    try:
        print(f"Checking {url} ...")
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"SUCCESS MATCH: {url}")
            print(f"Response Body Sample: {resp.text[:200]}")
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

def main():
    api_key = os.getenv("CLAUDE_CUSTOM_API_KEY")
    base = "https://yunyi.rdzhvip.com/claude"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    payload = {
        "model": "claude-opus-4-6", 
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 10
    }

    candidates = [
        f"{base}/v1/messages",  # Anthropic style?
        f"{base}/messages",
        f"{base}/v1/chat/completions",
        f"{base}/api/openai/v1/chat/completions",
    ]
    
    for url in candidates:
        if probe(url, headers, payload):
            break

if __name__ == "__main__":
    main()
