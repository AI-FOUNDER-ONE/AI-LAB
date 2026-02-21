"""
test_crewai_agents.py - 通过 CrewAI 框架测试 6 角色 AI 调用
============================================================
直接导入 crew_agents.py 中的 Agent 定义,
使用 CrewAI 的 Task.execute_sync() 验证每个角色是否能正常响应。

安全性审计:
  ✅ API 密钥通过 config.py 统一管理
  ✅ 使用 CrewAI 原生 LLM 调用链
  ✅ 敏感信息不打印到日志
"""

import sys
import os
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ---------- 导入 CrewAI 框架及 Agent 定义 ----------
from crewai import Task
from agents.crew_agents import (
    cko_agent, pm_agent, arch_agent,
    designer_agent, coder_agent, tester_agent
)

# ---------- 测试用简短提示词 ----------
TEST_PROMPT = "请用一句话(不超过50字)介绍你在团队中的角色定位。不要输出其他内容。"

# ---------- 结果存储 ----------
results = {}


def test_agent(name: str, agent, prompt: str) -> dict:
    """通过 CrewAI Task 测试单个 Agent 的 LLM 调用

    Args:
        name: 角色显示名
        agent: CrewAI Agent 实例
        prompt: 测试提示词

    Returns:
        dict: 包含 success, response, latency, error 的结果
    """
    task = Task(
        description=prompt,
        expected_output="一句话介绍",
        agent=agent,
    )

    start = time.time()
    try:
        result = task.execute_sync(agent=agent)
        latency = round(time.time() - start, 2)
        # CrewAI TaskOutput 对象
        content = str(result).strip()
        if content:
            return {"success": True, "response": content, "latency": latency}
        else:
            return {"success": False, "error": "空响应", "latency": latency}
    except Exception as e:
        latency = round(time.time() - start, 2)
        error_msg = str(e)[:200]
        return {"success": False, "error": error_msg, "latency": latency}


def main():
    """主测试入口 - 依次通过 CrewAI 框架测试 6 个角色"""
    print("=" * 68)
    print("  AI-Lab-Commander - CrewAI 集成测试 (6 角色)")
    print("=" * 68)
    print()

    # 角色名 → Agent 实例 映射
    agents = [
        ("CKO",      cko_agent),
        ("PM",       pm_agent),
        ("Arch",     arch_agent),
        ("Designer", designer_agent),
        ("Coder",    coder_agent),
        ("Tester",   tester_agent),
    ]

    for i, (name, agent) in enumerate(agents, 1):
        model_info = getattr(agent, 'llm', None)
        model_str = str(model_info.model) if model_info and hasattr(model_info, 'model') else "unknown"

        print(f"[{i}/6] Testing {name} (model: {model_str})")
        print("-" * 50)

        result = test_agent(name, agent, TEST_PROMPT)
        results[name] = result

        if result["success"]:
            print(f"  [OK] ({result['latency']}s)")
            # 截取回复前80字符展示
            preview = result["response"][:80].replace("\n", " ")
            print(f'  Response: "{preview}"')
        else:
            print(f"  [FAIL] ({result['latency']}s)")
            print(f"  Error: {result['error']}")

        print()

    # ---------- 汇总报告 ----------
    print("=" * 68)
    print("  Summary Report")
    print("=" * 68)

    success_count = sum(1 for r in results.values() if r["success"])
    total = len(results)

    for name, result in results.items():
        status = "[OK]" if result["success"] else "[FAIL]"
        latency = f"{result['latency']}s"
        print(f"  {status:6s} {name:10s} | {latency}")

    print(f"\n  Result: {success_count}/{total} passed")

    if success_count == total:
        print("  All agents working via CrewAI!")
    else:
        failed = [r for r, v in results.items() if not v["success"]]
        print(f"  Failed: {', '.join(failed)}")

    print("=" * 68)
    return success_count == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
