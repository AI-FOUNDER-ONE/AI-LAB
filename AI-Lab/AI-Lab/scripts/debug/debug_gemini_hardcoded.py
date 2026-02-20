import google.generativeai as genai

# HARDCODED KEY FROM USER INPUT
# "CKO Gemini  KEY=AIzaSyBiClJsFsD6dcvg7iD7Pn2kR7wk2DT9ruc"
key = "AIzaSyBiClJsFsD6dcvg7iD7Pn2kR7wk2DT9ruc"

print(f"Testing Hardcoded Key: {key}")

try:
    genai.configure(api_key=key)
    print("Configuration successful.")
except Exception as e:
    print(f"Configuration failed: {e}")

print("Attempting list_models...")
try:
    models = list(genai.list_models())
    print(f"Success! Found {len(models)} models.")
    for m in models:
        print(f" - {m.name}")
except Exception as e:
    print(f"API Call Failed: {e}")
