"""
checklist_tracker.py - 阶段交付物清单工具
==========================================
管理阶段交付物清单，状态持久化到 session_store 的 session 的 checklist 字段。
"""

from typing import Dict, Any, List, Optional

# 默认阶段清单模板
STAGE_CHECKLISTS = {
    "GROUNDING": [
        "需求目标已明确",
        "Mission Protocol JSON 已生成",
        "task_type 已确定",
        "用户已确认立项",
    ],
    "DEBATE": [
        "技术方案已确定",
        "风险已评估",
        "里程碑已定义",
        "PM 已批准方案",
    ],
    "PRODUCTION": [
        "核心模块已实现",
        "代码已通过基础校验",
        "文档/注释已添加",
    ],
    "VERIFICATION": [
        "Validator 测试已通过",
        "CKO 审计已通过",
        "无遗留的阻塞问题",
    ],
}


def checklist_tracker(
    action: str,
    stage: str = "",
    item: str = "",
    session_store: Any = None,
) -> Dict[str, Any]:
    """管理阶段交付物清单。

    Args:
        action: "create"（创建阶段清单）、"check"（标记完成）、
                "uncheck"（标记未完成）、"status"（查看当前状态）、
                "is_ready"（检查是否可推进到下一阶段）
        stage: 阶段名，如 GROUNDING、DEBATE、PRODUCTION、VERIFICATION
        item: 清单项文案（check/uncheck 时用于定位）
        session_store: SessionStore 实例，用于读写 session["checklist"]

    Returns:
        dict，含 ok、message 及 action 相关字段（如 status 的 items/checked，is_ready 的 ready/unchecked）
    """
    if not session_store:
        return {"ok": False, "message": "未提供 session_store"}
    session = session_store.get_current_session()
    if not session:
        return {"ok": False, "message": "无当前会话"}

    checklist = session.get("checklist")
    if checklist is None:
        checklist = {}
        session["checklist"] = checklist

    action = (action or "").strip().lower()
    stage = (stage or "").strip().upper()

    if action == "create":
        if stage not in STAGE_CHECKLISTS:
            return {"ok": False, "message": f"未知阶段: {stage}", "stages": list(STAGE_CHECKLISTS.keys())}
        items = list(STAGE_CHECKLISTS[stage])
        checklist[stage] = {"items": items, "checked": [False] * len(items)}
        session_store.update_session(checklist=checklist)
        return {"ok": True, "message": f"已创建 {stage} 清单", "stage": stage, "items": items}

    if action == "check":
        if not stage or stage not in checklist:
            return {"ok": False, "message": f"阶段 {stage} 无清单，请先 create"}
        entry = checklist[stage]
        items, checked = entry["items"], entry["checked"]
        idx = _index_of_item(items, item)
        if idx is None:
            return {"ok": False, "message": f"未找到项: {item}", "items": items}
        checked[idx] = True
        session_store.update_session(checklist=checklist)
        return {"ok": True, "message": f"已勾选: {item}", "stage": stage, "item": item}

    if action == "uncheck":
        if not stage or stage not in checklist:
            return {"ok": False, "message": f"阶段 {stage} 无清单"}
        entry = checklist[stage]
        items, checked = entry["items"], entry["checked"]
        idx = _index_of_item(items, item)
        if idx is None:
            return {"ok": False, "message": f"未找到项: {item}", "items": items}
        checked[idx] = False
        session_store.update_session(checklist=checklist)
        return {"ok": True, "message": f"已取消勾选: {item}", "stage": stage, "item": item}

    if action == "status":
        if stage:
            if stage not in checklist:
                return {"ok": True, "stage": stage, "items": [], "checked": [], "message": "该阶段尚未创建清单"}
            entry = checklist[stage]
            return {
                "ok": True,
                "stage": stage,
                "items": entry["items"],
                "checked": entry["checked"],
                "message": "当前清单状态",
            }
        return {"ok": True, "checklist": dict(checklist), "message": "全部阶段清单状态"}

    if action == "is_ready":
        if not stage or stage not in checklist:
            return {"ok": True, "ready": False, "stage": stage, "unchecked": [], "message": "该阶段无清单或未创建"}
        entry = checklist[stage]
        items, checked = entry["items"], entry["checked"]
        unchecked = [items[i] for i in range(len(items)) if not checked[i]]
        ready = len(unchecked) == 0
        return {
            "ok": True,
            "ready": ready,
            "stage": stage,
            "unchecked": unchecked,
            "message": "可推进" if ready else f"尚有 {len(unchecked)} 项未完成",
        }

    return {"ok": False, "message": f"未知 action: {action}", "allowed": ["create", "check", "uncheck", "status", "is_ready"]}


def _index_of_item(items: List[str], item: str) -> Optional[int]:
    """匹配项（精确或包含），返回索引。"""
    item = (item or "").strip()
    if not item:
        return None
    for i, s in enumerate(items):
        if s == item or item in s or s in item:
            return i
    return None
