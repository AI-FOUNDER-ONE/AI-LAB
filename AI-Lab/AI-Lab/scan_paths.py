import requests
import os
from dotenv import load_dotenv

load_dotenv()

def probe(url, headers, payload):
    try:
        print(f"Scanning {url} ...")
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 404:
            print(f"FOUND POTENTIAL MATCH! Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
    except Exception as e:
        pass

def main():
    api_key = os.getenv("CLAUDE_CUSTOM_API_KEY")
    base = "https://yunyi.rdzhvip.com/claude"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    payload = {
        "model": "claude-opus-4-6", # Use ID found in models list
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 10
    }

    candidates = [
        # Standard OpenAI
        f"{base}/v1/chat/completions",
        f"{base}/chat/completions",
        
        # Anthropic
        f"{base}/v1/messages",
        f"{base}/messages",
        
        # OneAPI / NewAPI variations
        f"{base}/api/v1/chat/completions",
        f"{base}/api/openai/v1/chat/completions",
        f"{base}/openai/v1/chat/completions",
        
        # Root variations (in case /claude is treated as folder but API is elsewhere)
        "https://yunyi.rdzhvip.com/v1/chat/completions",
        "https://yunyi.rdzhvip.com/api/v1/chat/completions",
    ]
    
    for url in candidates:
        probe(url, headers, payload)

if __name__ == "__main__":
    main()
