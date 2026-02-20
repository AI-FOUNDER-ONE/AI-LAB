
import os
import sys
import threading
from crewai import Crew, Process, LLM
# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import API_KEYS
import time

# Ensure paths
# sys.path.append(os.getcwd()) # This line is now redundant due to the project_root addition

from agents.crew_agents import cko_agent, pm_agent, arch_agent, coder_agent
from core.crew_tasks import grounding_task, design_task, production_task, review_task

def test_internal_flow():
    print("=== [START] Deep Flow Diagnosis ===")
    
    # Check LLM Initialization
    print(f"Testing LLM connectivity for CKO...")
    try:
        llm = cko_agent.llm
        # Attempt a dry run if possible or just check config
        print(f"CKO LLM Config: model={llm.model}, base_url={llm.base_url}")
    except Exception as e:
        print(f"FAILED: LLM initialization error: {e}")
        return

    # Check Task Setup
    print(f"CKO Task: description='{grounding_task.description[:50]}...', human_input={grounding_task.human_input}")

    # Define a simple intervention mock
    def mock_input_callback():
        print("[MOCK] get_input_callback triggered by CrewAI!")
        return "I want to build a simple timer app."

    # Create a minimal crew for testing
    test_crew = Crew(
        agents=[cko_agent],
        tasks=[grounding_task],
        process=Process.sequential,
        verbose=True,
        get_input_callback=mock_input_callback
    )

    print("\n[STEP 1] Starting kickoff in background thread...")
    
    execution_error = None
    result = None
    
    def run_crew():
        nonlocal result, execution_error
        try:
            print("[THREAD] Kickoff started...")
            result = test_crew.kickoff()
            print("[THREAD] Kickoff finished.")
        except Exception as e:
            execution_error = str(e)
            print(f"[THREAD] KICKOFF FAILED: {e}")

    t = threading.Thread(target=run_crew)
    t.start()
    
    # Monitor stdout and wait
    print("[STEP 2] Monitoring for 30 seconds...")
    timeout = 30
    start_time = time.time()
    while t.is_alive() and (time.time() - start_time < timeout):
        time.sleep(1)
        
    if t.is_alive():
        print("FAILED: Crew execution TIMEOUT after 30s. Possible deadlocks or API hang.")
    elif execution_error:
        print(f"FAILED: Crew execution error: {execution_error}")
    else:
        print(f"SUCCESS: Crew finished. Result length: {len(str(result)) if result else 0}")

    print("=== [END] Deep Flow Diagnosis ===")

if __name__ == "__main__":
    test_internal_flow()
