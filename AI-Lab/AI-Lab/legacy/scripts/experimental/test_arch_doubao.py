"""Verify Arch Agent with Volcengine Doubao Model"""
import sys
import os
sys.path.insert(0, ".")

from agents.crew_agents import get_llm
from crewai import Agent, Task, Crew, Process

# Force verbose to see API calls if possible (though LiteLLM might need its own debug flag)
os.environ["LITELLM_LOG"] = "INFO"

def test_arch():
    print("="*50)
    print("Testing Arch Agent (Volcengine Doubao)")
    print("="*50)
    
    try:
        llm = get_llm("Arch")
        print(f"LLM Configured: Model={llm.model}, BaseURL={llm.base_url}")
        
        arch = Agent(
            role="Arch",
            goal="Test Connectivity",
            backstory="Testing",
            llm=llm,
            verbose=True
        )
        
        task = Task(
            description="Say 'Hello Doubao' and nothing else.",
            expected_output="Hello Doubao",
            agent=arch
        )
        
        crew = Crew(agents=[arch], tasks=[task], verbose=True)
        result = crew.kickoff()
        
        print("\n" + "="*50)
        print("RESULT SUCCESS:")
        print(result)
        print("="*50)
        
    except Exception as e:
        print("\n" + "="*50)
        print("RESULT FAILED:")
        print(e)
        import traceback
        traceback.print_exc()
        print("="*50)

if __name__ == "__main__":
    test_arch()
