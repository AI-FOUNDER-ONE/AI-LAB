"""快速验证 PM 和 Coder 能在 CrewAI 中正常执行"""
import sys, os
sys.path.insert(0, ".")

from crewai import Agent, Task, Crew, Process
from agents.crew_agents import get_llm

# === Test PM (grok-4-0709 without temperature) ===
print("=" * 50)
print("测试 PM (grok-4-0709)")
print("=" * 50)
try:
    pm_llm = get_llm("PM")
    pm = Agent(role="PM", goal="Manage project", backstory="Project manager", llm=pm_llm, verbose=True)
    pm_task = Task(description="Say 'PM working' in Chinese", expected_output="Chinese text", agent=pm)
    crew1 = Crew(agents=[pm], tasks=[pm_task], process=Process.sequential, verbose=True)
    r1 = crew1.kickoff()
    print(f"\nPM Result: {str(r1)[:200]}\n")
except Exception as e:
    print(f"\nPM FAILED: {e}\n")

# === Test Coder (Claude via anthropic) ===
print("=" * 50)
print("测试 Coder (claude-opus-4-6)")
print("=" * 50)
try:
    coder_llm = get_llm("Coder")
    coder = Agent(role="Coder", goal="Write code", backstory="Senior developer", llm=coder_llm, verbose=True)
    coder_task = Task(description="Say 'Coder working' in Chinese", expected_output="Chinese text", agent=coder)
    crew2 = Crew(agents=[coder], tasks=[coder_task], process=Process.sequential, verbose=True)
    r2 = crew2.kickoff()
    print(f"\nCoder Result: {str(r2)[:200]}\n")
except Exception as e:
    import traceback
    print(f"\nCoder FAILED: {e}")
    traceback.print_exc()
