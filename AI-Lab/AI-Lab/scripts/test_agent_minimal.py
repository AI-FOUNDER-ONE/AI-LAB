
import os
import sys
from crewai import Agent, LLM

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.crew_tools import DocxParserTool, CodeWriterTool

def test_minimal_agent():
    print("=== [START] Minimal Agent Test with Tools ===")
    
    # 0. Test Tool Creation
    print("Step 0: Creating Tools...")
    try:
        docx_tool = DocxParserTool()
        code_tool = CodeWriterTool()
        print("Tools created.")
    except Exception as e:
        print(f"FAILED: Tool creation error: {e}")
        return

    # 1. Test LLM Creation
    print("Step 1: Creating LLM object...")
    try:
        my_llm = LLM(
            model="openai/gpt-4o",
            api_key="sk-test",
            base_url="https://hiapi.online/v1",
            temperature=0.7
        )
        print("LLM object created.")
    except Exception as e:
        print(f"FAILED: LLM creation error: {e}")
        return

    # 2. Test Agent Creation with Tool
    print("Step 2: Creating Agent object (with LLM and Tool)...")
    try:
        test_agent = Agent(
            role='首席知识官 (CKO)',
            goal='提取并完善用户需求',
            backstory='你是需求工程专家',
            tools=[docx_tool],
            llm=my_llm,
            verbose=True,
            allow_delegation=False
        )
        print("Agent object created successfully.")
    except Exception as e:
        print(f"FAILED: Agent creation error: {e}")
        return

    print("=== [END] Minimal Agent Test ===")

if __name__ == "__main__":
    test_minimal_agent()
