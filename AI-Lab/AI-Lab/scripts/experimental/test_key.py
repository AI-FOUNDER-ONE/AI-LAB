
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_hiapi_key():
    api_key = os.getenv("HIAPI_API_KEY", "sk-GFUVZDomT4fbLH5RiCE7w2KVld5SfZIZhdEcLLmewnNzuJei")
    base_url = "https://hiapi.online/v1/chat/completions"
    
    print(f"Testing Key: {api_key[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 5
    }
    
    try:
        response = requests.post(base_url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code == 200:
            print("SUCCESS: API Key is valid.")
        else:
            print(f"FAILED: {response.status_code} - Check key or billing.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_hiapi_key()
