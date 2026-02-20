import google.generativeai as genai
from google.api_core import client_options
import os

# New Key
key = "AIzaSyBiClJsFsD6dcvg7iD7Pn2kR7wk2DT9ruc"

print(f"Testing Key: {key}")

# Test 1: Standard Endpoint (Failed previously)
print("\n--- Test 1: Standard Endpoint ---")
try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content("Hello")
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"Failed: {e}")

# Test 2: List Models again with detail
print("\n--- Test 2: List Models Detail ---")
try:
    for m in genai.list_models():
        print(f" - {m.name} ({m.supported_generation_methods})")
except Exception as e:
    print(f"List Models Failed: {e}")

# Test 3: Check for specific common models explicitly
print("\n--- Test 3: Explicit Model Check ---")
models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro"]
for m_name in models_to_try:
    print(f"Trying {m_name}...")
    try:
        model = genai.GenerativeModel(m_name)
        response = model.generate_content("Hi")
        print(f"  SUCCESS with {m_name}!")
        break
    except Exception as e:
        print(f"  Failed with {m_name}: {e}")

print("\nDone.")
