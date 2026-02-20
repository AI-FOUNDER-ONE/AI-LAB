import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

print(f"Python: {sys.version}")

print("Loading .env...")
load_dotenv(verbose=True)

key = os.getenv("GEMINI_API_KEY")

if not key:
    print("ERROR: GENINI_API_KEY is None")
else:
    print(f"Key Repr: {repr(key)}")
    
    # Clean the key just in case
    clean_key = key.strip()
    print(f"Clean Key Repr: {repr(clean_key)}")
    
    # Strategy 1: Set ENV var which SDK auto-detects
    os.environ["GOOGLE_API_KEY"] = clean_key
    
    # Strategy 2: Explicit configure
    print("Configuring GenAI with clean key...")
    try:
        genai.configure(api_key=clean_key)
    except Exception as e:
        print(f"Configure failed: {e}")

    print("Attempting list_models...")
    try:
        models = list(genai.list_models())
        print(f"Success! Found {len(models)} models.")
    except Exception as e:
        print(f"API Call Failed: {e}")
