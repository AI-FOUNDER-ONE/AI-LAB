"""
debug_pm_coder.py - PM 和 Coder 专项诊断
=========================================
单独测试 PM (Grok) 和 Coder (Claude) 的 API 调用，
并模拟生产阶段的 Prompt 来检查 Coder 是否能输出代码。
"""

import sys
import os
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 禁用 CrewAI Telemetry 防止 SSL 报错
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from dotenv import load_dotenv
load_dotenv()

from crewai import Task, Crew, Process, Agent

# 设置 litellm drop_params
try:
    import litellm
    litellm.drop_params = True
except ImportError:
    pass

# 导入 Agent 和配置
from config import API_KEYS, AGENT_MODELS

print("=" * 70)
print("  PM & Coder 专项诊断")
print("=" * 70)

# ============================================================
#  1. 检查配置
# ============================================================
print("\n[1/5] 检查 API 配置...")

for role in ["PM", "Coder"]:
    cfg = AGENT_MODELS.get(role, {})
    provider = cfg.get("provider", "?")
    model = cfg.get("model", "?")
    base_url = cfg.get("base_url", "?")
    api_key = API_KEYS.get(provider, "")
    key_preview = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "(缺失!)"
    print(f"  {role}: provider={provider}, model={model}")
    print(f"       base_url={base_url}")
    print(f"       api_key={key_preview}")

# ============================================================
#  2. 导入 Agents (捕获导入错误)
# ============================================================
print("\n[2/5] 导入 CrewAI Agent 定义...")
try:
    from agents.crew_agents import pm_agent, coder_agent
    print("  ✅ pm_agent 和 coder_agent 导入成功")
    print(f"  PM role: {pm_agent.role}")
    print(f"  Coder role: {coder_agent.role}")
except Exception as e:
    print(f"  ❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# ============================================================
#  3. 测试 PM (Grok)
# ============================================================
print("\n[3/5] 测试 PM (Grok) API 调用...")
try:
    pm_test_task = Task(
        description="你是 PM，请用一句话介绍你在团队中的角色。不超过50字。",
        expected_output="一句话介绍",
        agent=pm_agent
    )
    crew = Crew(agents=[pm_agent], tasks=[pm_test_task],
                process=Process.sequential, verbose=True)
    
    start = time.time()
    result = crew.kickoff()
    elapsed = time.time() - start
    
    response = str(result).strip()
    if response and len(response) > 3:
        print(f"\n  ✅ PM 响应成功 ({elapsed:.1f}s, {len(response)} 字符)")
        print(f"  回复: {response[:200]}")
    else:
        print(f"\n  ⚠️ PM 返回空或过短响应: '{response}'")
except Exception as e:
    print(f"\n  ❌ PM 调用失败:")
    traceback.print_exc()

# ============================================================
#  4. 测试 Coder (Claude) — 简单任务
# ============================================================
print("\n\n[4/5] 测试 Coder (Claude) API 调用 — 简单任务...")
try:
    coder_test_task = Task(
        description="你是 Coder，请用一句话介绍你在团队中的角色。不超过50字。",
        expected_output="一句话介绍",
        agent=coder_agent
    )
    crew = Crew(agents=[coder_agent], tasks=[coder_test_task],
                process=Process.sequential, verbose=True)
    
    start = time.time()
    result = crew.kickoff()
    elapsed = time.time() - start
    
    response = str(result).strip()
    if response and len(response) > 3:
        print(f"\n  ✅ Coder 简单响应成功 ({elapsed:.1f}s, {len(response)} 字符)")
        print(f"  回复: {response[:200]}")
    else:
        print(f"\n  ⚠️ Coder 返回空或过短响应: '{response}'")
except Exception as e:
    print(f"\n  ❌ Coder 简单调用失败:")
    traceback.print_exc()

# ============================================================
#  5. 测试 Coder — 模拟生产阶段 Prompt
# ============================================================
print("\n\n[5/5] 测试 Coder (Claude) — 模拟生产阶段代码生成...")
try:
    production_prompt = (
        "你是 Coder，生产阶段第 1 轮。\n\n"
        "## 上下文\n"
        "PM: 方案通过。项目是一个 Python 计算器，需要支持加减乘除四则运算。\n"
        "Arch: 建议使用简单的函数式设计，每个运算符一个函数。\n\n"
        "## 任务\n"
        "根据最终方案编写代码。\n"
        "- 遵循 Google 编程规范，详尽中文注释\n"
        "- 使用 ```python 代码块 ```\n"
        "- 简体中文"
    )
    
    coder_prod_task = Task(
        description=production_prompt,
        expected_output="包含 Python 代码的详细回复",
        agent=coder_agent
    )
    crew = Crew(agents=[coder_agent], tasks=[coder_prod_task],
                process=Process.sequential, verbose=True)
    
    start = time.time()
    result = crew.kickoff()
    elapsed = time.time() - start
    
    response = str(result).strip()
    has_code = "```" in response or "def " in response or "class " in response
    
    if response and len(response) > 10:
        print(f"\n  ✅ Coder 生产响应成功 ({elapsed:.1f}s, {len(response)} 字符)")
        print(f"  包含代码块: {'✅' if has_code else '❌ (未检测到代码!)'}")
        print(f"  回复前300字: {response[:300]}")
    else:
        print(f"\n  ⚠️ Coder 生产返回空或过短: '{response}'")
except Exception as e:
    print(f"\n  ❌ Coder 生产调用失败:")
    traceback.print_exc()

print("\n" + "=" * 70)
print("  诊断完成")
print("=" * 70)
