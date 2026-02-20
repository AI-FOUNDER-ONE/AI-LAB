"""测试 PM agent 通过 CrewAI 执行"""
import sys
sys.path.insert(0, ".")

from crewai import LLM, Agent, Task, Crew, Process
from config import API_KEYS, AGENT_MODELS

cfg = AGENT_MODELS["PM"]
print(f"PM config: {cfg}")

api_key = API_KEYS[cfg["provider"]]
print(f"API key (masked): {api_key[:8]}...{api_key[-4:]}")

try:
    llm = LLM(
        model=f"openai/{cfg['model']}",
        api_key=api_key,
        base_url=cfg["base_url"],
        temperature=0.7,
    )
    print("LLM created OK")

    agent = Agent(
        role="PM",
        goal="Test PM agent",
        backstory="You are a project manager.",
        llm=llm,
        verbose=True,
    )
    print("Agent created OK")

    task = Task(
        description="Say hello in Chinese, keep it brief.",
        expected_output="A Chinese greeting",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(f"\n=== PM Result ===")
    print(str(result)[:500])

except Exception as e:
    import traceback
    print(f"\n=== PM FAILED ===")
    print(f"Error: {e}")
    traceback.print_exc()
