import sys
import os
import requests
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from config import API_KEYS

def list_models():
    api_key = API_KEYS.get("hiapi")
    if not api_key:
        print("No HiAPI key found!")
        return

    url = "https://hiapi.online/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        print(f"Querying {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            print(f"Found {len(models)} models.")
            for m in models:
                mid = m.get("id")
                if "gemini" in mid.lower():
                    print(f"GEMINI MATCH: {mid}")
                elif "gpt" in mid.lower():
                     pass # Too many gpts
                else:
                     pass # print(f"Other: {mid}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    list_models()
