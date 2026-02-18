"""验证 Coder monkey-patch 在 CrewAI 中是否生效"""
import sys
sys.path.insert(0, ".")

# 导入 crew_agents 触发 monkey-patch
from agents.crew_agents import get_llm

from crewai import Agent, Task, Crew, Process

print("=" * 50)
print("验证 Coder (yunyi Claude + monkey-patch)")
print("=" * 50)
try:
    coder_llm = get_llm("Coder")
    coder = Agent(
        role="Coder",
        goal="Write code",
        backstory="You are a senior developer. Write clean Python code.",
        llm=coder_llm,
        verbose=True
    )
    task = Task(
        description="Write a hello world function in Python. Keep it simple.",
        expected_output="Python code with a hello_world function",
        agent=coder
    )
    crew = Crew(agents=[coder], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(f"\n=== CODER RESULT ===")
    print(str(result)[:500])
except Exception as e:
    import traceback
    print(f"\nCODER FAILED: {e}")
    traceback.print_exc()
