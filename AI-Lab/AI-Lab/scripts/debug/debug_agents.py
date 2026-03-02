import sys
import os
from config import AGENT_MODELS, API_KEYS

print(f"Python: {sys.version}")
print("Checking API Keys...")
for provider, key in API_KEYS.items():
    status = "OK" if key else "MISSING"
    print(f"  {provider}: {status}")

print("\nChecking Agent Initialization...")
try:
    from agents.pm_agent import PMAgent
    print("  Initializing PM Agent...")
    pm = PMAgent()
    print("  PM Agent Initialized.")
    # pm._init_client() # Lazy init test
    # print("  PM Client Initialized.")
except Exception as e:
    print(f"  ALL_CAPS_ERROR: PM Agent failed: {e}")
    import traceback
    traceback.print_exc()

try:
    from agents.arch_agent import ArchAgent
    print("  Initializing Arch Agent...")
    arch = ArchAgent()
    print("  Arch Agent Initialized.")
except Exception as e:
    print(f"  ALL_CAPS_ERROR: Arch Agent failed: {e}")
    traceback.print_exc()

try:
    from agents.coder_agent import CoderAgent
    print("  Initializing Coder Agent...")
    coder = CoderAgent()
    print("  Coder Agent Initialized.")
except Exception as e:
    print(f"  ALL_CAPS_ERROR: Coder Agent failed: {e}")
    traceback.print_exc()

try:
    from agents.validator_agent import ValidatorAgent
    print("  Initializing Validator Agent...")
    validator = ValidatorAgent()
    print("  Validator Agent Initialized.")
except Exception as e:
    print(f"  ALL_CAPS_ERROR: Validator Agent failed: {e}")
    traceback.print_exc()

print("\nDone.")
