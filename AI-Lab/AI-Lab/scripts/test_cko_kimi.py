"""Verify CKO Agent with Kimi Model and Web Search"""
import sys
import os
sys.path.insert(0, ".")

from agents.crew_agents import get_llm
from crewai import Agent, Task, Crew, Process

# Force verbose to see API calls if possible (though LiteLLM might need its own debug flag)
os.environ["LITELLM_LOG"] = "INFO"

def test_cko():
    print("="*50)
    print("Testing CKO Agent (Kimi + Web Search)")
    print("="*50)
    
    try:
        llm = get_llm("CKO")
        print(f"LLM Configured: Model={llm.model}, BaseURL={llm.base_url}")
        
        cko = Agent(
            role="CKO",
            goal="Provide latest news",
            backstory="You are a news reporter.",
            llm=llm,
            verbose=True
        )
        
        task = Task(
            description="今天有什么热点新闻 (What are the hot news today?)",
            expected_output="A summary of today's hot news.",
            agent=cko
        )
        
        crew = Crew(agents=[cko], tasks=[task], verbose=True)
        result = crew.kickoff()
        
        print("\n" + "="*50)
        print("RESULT:")
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
    test_cko()
