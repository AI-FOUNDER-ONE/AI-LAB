import sys
import os
# Force reload of modules
import importlib

print(f"Python: {sys.version}")

try:
    print("Importing config...")
    import config
    importlib.reload(config)
    print(f"PM Model in config: {config.AGENT_MODELS['PM']}")
    
    print("Importing cko_agent...")
    import agents.cko_agent
    importlib.reload(agents.cko_agent)
    from agents.cko_agent import CKOAgent
    
    print("Initializing CKO Agent...")
    cko = CKOAgent()
    print("CKO Agent Initialized.")
    print(f"CKO Model Config: {cko.model_config}")
    
    print("Initializing Client (Lazy Load Check)...")
    try:
        cko._init_client()
        print("CKO Client successfully initialized (google.generativeai loaded).")
    except Exception as e:
        print(f"CKO Client Init Failed: {e}")

except Exception as e:
    print(f"ALL_CAPS_ERROR: Testing CKO Agent failed: {e}")
    import traceback
    traceback.print_exc()

print("\nDone.")
