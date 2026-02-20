"""
test_commander_crew.py — CommanderCrew V2 集成测试 (无 GUI)
============================================================
测试 CommanderCrew 的实例化和基本流程。
"""

import os
import sys

# 确保项目根目录在 path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=" * 60)
print("[TEST] CommanderCrew V2 集成测试 (无 GUI)")
print("=" * 60)

# ---- Step 1: 导入测试 ----
print("\nStep 1: 导入 CommanderCrew...")
try:
    from core.commander_crew_v2 import (
        CommanderCrew, WarRoomContext, DebateRouter,
        PersonalityEngine, WarRoomMessage
    )
    print("✅ CommanderCrew 导入成功")
except Exception as e:
    import traceback
    print(f"❌ 导入失败: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# ---- Step 2: 单元测试 — PersonalityEngine ----
print("\nStep 2: PersonalityEngine 测试...")
try:
    style = PersonalityEngine.get_style_directive("PM")
    assert isinstance(style, str) and len(style) > 5
    print(f"  PM 风格: {style}")

    style2 = PersonalityEngine.get_style_directive("Arch")
    print(f"  Arch 风格: {style2}")
    print("✅ PersonalityEngine 正常")
except Exception as e:
    print(f"❌ PersonalityEngine 失败: {e}")

# ---- Step 3: 单元测试 — WarRoomContext ----
print("\nStep 3: WarRoomContext 测试...")
try:
    ctx = WarRoomContext()
    
    # 添加消息
    msg1 = ctx.add_message("PM", "大家讨论一下架构方案 @Arch", round_num=1)
    assert msg1.mentions == ["Arch"]
    print(f"  PM 消息意图: {msg1.intent}, 提及: {msg1.mentions}")

    msg2 = ctx.add_message("Arch", "我反对这个方案，存在性能风险", round_num=1)
    assert msg2.intent == "critique"
    assert msg2.sentiment == "negative"
    print(f"  Arch 消息意图: {msg2.intent}, 情感: {msg2.sentiment}")

    msg3 = ctx.add_message("Designer", "我同意 PM 的方案", round_num=1)
    assert msg3.intent == "agreement"
    print(f"  Designer 消息意图: {msg3.intent}")

    # 共识检查
    status = dict(ctx.consensus_tracker)
    print(f"  共识状态: {status}")

    # 相关历史检索
    relevant = ctx.get_relevant_history("Arch")
    print(f"  Arch 相关历史: {relevant[:80] if relevant else '(无)'}")

    # 立场摘要
    stance = ctx.get_stance_summary()
    print(f"  立场态势:\n    {stance.replace(chr(10), chr(10) + '    ')}")

    # 投票
    ctx.register_vote("Arch", "disagree", "性能无法满足要求", round_num=1)
    ctx.register_vote("Designer", "agree", "方案可行", round_num=1)
    assert len(ctx.vote_records) == 2
    print(f"  投票记录: {ctx.vote_records}")

    print("✅ WarRoomContext 正常")
except Exception as e:
    import traceback
    print(f"❌ WarRoomContext 失败: {e}\n{traceback.format_exc()}")

# ---- Step 4: 单元测试 — DebateRouter ----
print("\nStep 4: DebateRouter 测试...")
try:
    ctx2 = WarRoomContext()
    router = DebateRouter(ctx2)

    # 辩论顺序
    order = router.get_debate_order(1)
    print(f"  第1轮辩论顺序: {order}")
    assert len(order) >= 2

    # 语义相关性
    msg = WarRoomMessage(role="PM", content="架构模块设计的API接口需要优化")
    should_respond = router.should_agent_respond("Arch", msg)
    print(f"  Arch 是否应回应 PM 关于架构的消息: {should_respond}")
    assert should_respond is True

    should_not = router.should_agent_respond("Tester", msg)
    print(f"  Tester 是否应回应 PM 关于架构的消息: {should_not}")

    print("✅ DebateRouter 正常")
except Exception as e:
    import traceback
    print(f"❌ DebateRouter 失败: {e}\n{traceback.format_exc()}")

# ---- Step 5: CommanderCrew 实例化测试 (需要 PyQt6) ----
print("\nStep 5: CommanderCrew 实例化测试...")
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    
    commander = CommanderCrew()
    assert hasattr(commander, 'start_mission')
    assert hasattr(commander, 'confirm_project')
    assert hasattr(commander, 'handle_user_intervention')
    assert hasattr(commander, 'new_session')
    assert hasattr(commander, 'stop_all')
    assert hasattr(commander, 'agent_response')
    assert hasattr(commander, 'state_changed')
    assert hasattr(commander, 'error_occurred')
    assert hasattr(commander, 'workflow_completed')
    
    # ProxyAgent 测试
    assert hasattr(commander, 'cko')
    assert hasattr(commander, 'pm')
    assert hasattr(commander, 'arch')
    assert hasattr(commander, 'designer')
    assert hasattr(commander.cko, 'typing_started')
    assert hasattr(commander.cko, 'typing_finished')
    
    print("✅ CommanderCrew 实例化成功")
    print(f"  状态: {commander.state_ctrl.current_state}")
    print(f"  ProxyAgents: cko={commander.cko.role}, pm={commander.pm.role}")
except Exception as e:
    import traceback
    print(f"❌ CommanderCrew 实例化失败: {e}\n{traceback.format_exc()}")

print("\n" + "=" * 60)
print("[TEST] 测试完成")
print("=" * 60)
