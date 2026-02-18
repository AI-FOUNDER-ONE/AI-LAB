"""测试不同 LiteLLM 前缀对 PM grok-4-0709 的影响"""
import sys, os
sys.path.insert(0, ".")

import litellm
litellm.drop_params = True

from crewai import LLM, Agent, Task, Crew, Process
from config import API_KEYS

api_key = API_KEYS["xai"]
base_url = "https://api.x.ai/v1"

# 测试1: 不带前缀 — 让 LiteLLM 自动识别
print("=" * 40)
print("Test 1: 无前缀 (grok-4-0709)")
print("=" * 40)
try:
    llm = LLM(model="grok-4-0709", api_key=api_key, base_url=base_url, temperature=0.7)
    agent = Agent(role="PM", goal="Test", backstory="PM", llm=llm, verbose=True)
    task = Task(description="Say OK", expected_output="OK", agent=agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    r = crew.kickoff()
    print(f"Test1 OK: {str(r)[:100]}")
except Exception as e:
    print(f"Test1 FAIL: {e}")

# 测试2: xai/ 前缀
print("\n" + "=" * 40)
print("Test 2: xai/ 前缀")
print("=" * 40)
try:
    llm = LLM(model="xai/grok-4-0709", api_key=api_key, base_url=base_url, temperature=0.7)
    agent = Agent(role="PM", goal="Test", backstory="PM", llm=llm, verbose=True)
    task = Task(description="Say OK", expected_output="OK", agent=agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    r = crew.kickoff()
    print(f"Test2 OK: {str(r)[:100]}")
except Exception as e:
    print(f"Test2 FAIL: {e}")

# 测试3: openai/ + 手动 stop=""
print("\n" + "=" * 40)
print("Test 3: openai/ + stop=''")
print("=" * 40)
try:
    llm = LLM(model="openai/grok-4-0709", api_key=api_key, base_url=base_url, temperature=0.7, stop="")
    agent = Agent(role="PM", goal="Test", backstory="PM", llm=llm, verbose=True)
    task = Task(description="Say OK", expected_output="OK", agent=agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    r = crew.kickoff()
    print(f"Test3 OK: {str(r)[:100]}")
except Exception as e:
    print(f"Test3 FAIL: {e}")
