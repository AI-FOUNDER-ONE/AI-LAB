import sys
import os
from dotenv import load_dotenv

# Ensure we can import from current directory
sys.path.append(os.getcwd())

load_dotenv()

from agents.arch_agent import ArchAgent

def test_arch():
    print("Testing Arch Agent...")
    try:
        agent = ArchAgent()
        print(f"Agent initialized. Model: {agent.model_config}")
        
        print("Sending message...")
        response = agent.send_message("Hello, Architect. Are you online?")
        print(f"Response: {response}")
        print("✅ Arch Agent Test Passed")
    except Exception as e:
        print(f"❌ Arch Agent Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_arch()
