"""
debug_claude_custom.py - Test Custom Claude Endpoint
====================================================
"""
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load .env but also rely on config.py logic if needed
load_dotenv()

def test_endpoint(base_url, api_key, model):
    print(f"\nScanning: {base_url} ...")
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Hi"}
            ],
            max_tokens=10
        )
        print("SUCCESS!")
        print(response.choices[0].message.content)
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

def main():
    print("Testing Custom Claude Endpoint Variants...")
    
    api_key = os.getenv("CLAUDE_CUSTOM_API_KEY")
    model = "claude-opus-4.6"
    
    if not api_key:
        print("ERROR: CLAUDE_CUSTOM_API_KEY not found in .env")
        return

    # User provided: https://yunyi.rdzhvip.com/claude
    
    candidates = [
        "https://yunyi.rdzhvip.com/claude",       # -> /claude/chat/completions
        "https://yunyi.rdzhvip.com/claude/v1",    # -> /claude/v1/chat/completions
        "https://yunyi.rdzhvip.com/v1",           # -> /v1/chat/completions
        "https://yunyi.rdzhvip.com",              # -> /chat/completions
    ]

    for url in candidates:
        if test_endpoint(url, api_key, model):
            print(f"\n>>> FOUND WORKING BASE_URL: {url} <<<")
            break

if __name__ == "__main__":
    main()
