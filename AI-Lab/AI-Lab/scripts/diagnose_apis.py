import os
import sys
from dotenv import load_dotenv

# Add project root to path
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from config import API_KEYS, AGENT_MODELS
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

def test_hiapi():
    print("--- Testing HIAPI (OpenAI Compatible) ---")
    key = API_KEYS.get("hiapi")
    if not key:
        print("Error: HIAPI_API_KEY not found in config/env")
        return False
    
    try:
        llm = ChatOpenAI(
            openai_api_key=key,
            openai_api_base="https://hiapi.online/v1",
            model_name="gpt-4o",
            temperature=0,
            max_tokens=50
        )
        response = llm.invoke("Hello, are you online? Answer with 'YES' if you are.")
        print(f"Response: {response.content}")
        return "YES" in response.content.upper()
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_gemini():
    print("\n--- Testing Gemini ---")
    key = API_KEYS.get("gemini")
    if not key:
        print("Error: GEMINI_API_KEY not found in config/env")
        return False
    
    models_to_try = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]
    for model in models_to_try:
        print(f"Trying Gemini model: {model}...")
        try:
            llm = ChatGoogleGenerativeAI(
                google_api_key=key,
                model=model,
                temperature=0,
                max_output_tokens=50
            )
            response = llm.invoke("Hello, are you online? Answer with 'YES' if you are.")
            print(f"Response ({model}): {response.content}")
            if "YES" in response.content.upper():
                print(f"Success with model: {model}")
                return True
        except Exception as e:
            print(f"Failed with {model}: {e}")
    return False

if __name__ == "__main__":
    load_dotenv()
    print("AI-Lab-Commander API Diagnostics\n")
    
    hiapi_ok = test_hiapi()
    gemini_ok = test_gemini()
    
    print("\n--- Final Results ---")
    print(f"HIAPI: {'PASSED' if hiapi_ok else 'FAILED'}")
    print(f"Gemini: {'PASSED' if gemini_ok else 'FAILED'}")
