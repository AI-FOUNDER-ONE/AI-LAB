import sys
import os
from dotenv import load_dotenv

# Ensure we can import from current directory
sys.path.append(os.getcwd())

load_dotenv()

from agents.arch_agent import ArchAgent
from config import AGENT_MODELS

def test_arch_gemini():
    print("Testing Arch Agent with Gemini Configuration...")
    
    # 强制覆盖配置以确保测试的是 Gemini
    # 虽然 Config 已经改了，但双重确认
    print(f"Current Config for Arch: {AGENT_MODELS.get('Arch')}")
    
    try:
        agent = ArchAgent()
        print(f"Agent initialized. Model: {agent.model_config}")
        
        if agent.model_config['provider'] != 'gemini':
            print("❌ Error: Agent is not using Gemini provider!")
            return

        print("Sending message...")
        response = agent.send_message("Hello Gemini, please confirm you are the Architect.")
        print(f"Response: {response}")
        print("✅ Arch Agent (Gemini) Test Passed")
        
    except Exception as e:
        print(f"❌ Arch Agent Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_arch_gemini()
