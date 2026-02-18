import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

print(f"Python: {sys.version}")
load_dotenv()

key = os.getenv("GEMINI_API_KEY")
if not key:
    print("No Key found")
    sys.exit(1)

key = key.strip()
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"

print(f"Testing URL: https://generativelanguage.googleapis.com/v1beta/models?key=...{key[-5:]}")

try:
    with urllib.request.urlopen(url) as response:
        print(f"Status: {response.status}")
        data = json.loads(response.read().decode())
        print("Success! Models found:")
        # print(json.dumps(data, indent=2))
        print(f"Count: {len(data.get('models', []))}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")
