import sys
from config import API_KEYS

print(f"Python: {sys.version}")

try:
    from agents.cko_agent import CKOAgent
    print("  Initializing CKO Agent...")
    cko = CKOAgent()
    print("  CKO Agent Initialized.")
except Exception as e:
    print(f"  ALL_CAPS_ERROR: CKO Agent failed: {e}")
    import traceback
    traceback.print_exc()

try:
    from agents.designer_agent import DesignerAgent
    print("  Initializing Designer Agent...")
    designer = DesignerAgent()
    print("  Designer Agent Initialized.")
except Exception as e:
    print(f"  ALL_CAPS_ERROR: Designer Agent failed: {e}")
    traceback.print_exc()

print("\nDone.")
