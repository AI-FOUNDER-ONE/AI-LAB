import requests
import os
from dotenv import load_dotenv

load_dotenv()

def probe(url, headers, payload):
    try:
        print(f"Probing {url} ...")
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:200]}")
        return resp.status_code
    except Exception as e:
        print(f"Error: {e}")
        return -1

def main():
    api_key = os.getenv("CLAUDE_CUSTOM_API_KEY")
    base = "https://yunyi.rdzhvip.com/claude" # User provided
    
    # OpenAI Style
    headers_openai = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload_openai = {
        "model": "claude-opus-4.6",
        "messages": [{"role": "user", "content": "hi"}]
    }

    # Test exact URL
    probe(base, headers_openai, payload_openai)

if __name__ == "__main__":
    main()
