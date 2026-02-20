import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from agents.arch_agent import ArchAgent
from config import AGENT_MODELS, API_KEYS

def test_arch_hiapi():
    print("Testing Arch Agent with HiAPI Configuration...")
    print(f"Config: {AGENT_MODELS.get('Arch')}")
    print(f"Key ends with: ...{API_KEYS.get('hiapi')[-6:]}")
    
    try:
        agent = ArchAgent()
        # Ensure provider is hiapi
        if agent.model_config['provider'] != 'hiapi':
             print(f"❌ Config Mismatch! Provider is {agent.model_config['provider']}")
             return

        print("Sending message...")
        response = agent.send_message("Hello from HiAPI Gemini test. Who are you?")
        print(f"Response: {response}")
        print("✅ Arch Agent (HiAPI/Gemini) Test Passed")
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_arch_hiapi()
