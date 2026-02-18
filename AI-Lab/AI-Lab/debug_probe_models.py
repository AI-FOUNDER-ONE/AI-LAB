import requests
import os
from dotenv import load_dotenv

load_dotenv()

def probe_get(url, headers):
    try:
        print(f"GET {url} ...")
        resp = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    api_key = os.getenv("CLAUDE_CUSTOM_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    base = "https://yunyi.rdzhvip.com/claude"
    
    probe_get(f"{base}/v1/models", headers)
    probe_get(f"{base}/models", headers)
    probe_get(f"{base}/api/v1/models", headers)

if __name__ == "__main__":
    main()
