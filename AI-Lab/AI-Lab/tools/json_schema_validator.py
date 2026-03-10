"""
json_schema_validator.py - JSON Schema 校验工具
================================================
校验 Agent 输出的 JSON（如 Mission Protocol、验证报告）是否符合预定义 Schema。
"""

import json
from typing import Dict, Any, List

SCHEMAS = {
    "mission_protocol": {
        "required": ["goal", "task_type", "deliverables"],
        "optional": ["constraints", "acceptance_criteria", "timeline", "priority"],
    },
    "validation_report": {
        "required": ["test_results", "pass_rate", "issues"],
        "optional": ["recommendations", "performance_metrics"],
    },
    "delivery_summary": {
        "required": ["scope", "deliverables", "status"],
        "optional": ["limitations", "next_steps", "acceptance_result"],
    },
}


def _is_valid_required_type(value: Any) -> bool:
    """要求类型为 string 或 list；string 需非空（strip 后），list 允许空。"""
    if value is None:
        return False
    if isinstance(value, str):
        return len((value or "").strip()) > 0
    if isinstance(value, list):
        return True
    return False


def _validate_against_schema(data: Dict[str, Any], schema: Dict[str, List[str]]) -> List[str]:
    errors: List[str] = []
    required = schema.get("required") or []
    for key in required:
        if key not in data:
            errors.append(f"缺少必填字段: {key!r}")
            continue
        val = data[key]
        if not _is_valid_required_type(val):
            if isinstance(val, str):
                errors.append(f"必填字段 {key!r} 不能为空")
            else:
                errors.append(f"必填字段 {key!r} 类型须为 string 或 list，当前为 {type(val).__name__}")
    return errors


def json_schema_validator(json_str: str, schema_name: str) -> Dict[str, Any]:
    """校验 JSON 字符串是否符合指定内置 Schema。

    Args:
        json_str: 待校验的 JSON 字符串（如 Agent 输出的 Mission Protocol、验证报告等）。
        schema_name: 内置 schema 名："mission_protocol" / "validation_report" / "delivery_summary"。

    Returns:
        {"valid": bool, "errors": [str], "parsed": dict|None}
        - valid: 是否通过校验
        - errors: 错误信息列表（解析失败或必填缺失/类型不符）
        - parsed: 解析后的 dict，解析失败时为 None
    """
    schema_name = (schema_name or "").strip().lower()
    if schema_name not in SCHEMAS:
        return {
            "valid": False,
            "errors": [f"未知 schema: {schema_name!r}，可选: {list(SCHEMAS.keys())}"],
            "parsed": None,
        }

    raw = (json_str or "").strip()
    if not raw:
        return {"valid": False, "errors": ["JSON 字符串为空"], "parsed": None}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "errors": [f"JSON 解析失败: {e}"],
            "parsed": None,
        }

    if not isinstance(parsed, dict):
        return {
            "valid": False,
            "errors": ["根节点须为对象 (dict)"],
            "parsed": None,
        }

    schema = SCHEMAS[schema_name]
    errors = _validate_against_schema(parsed, schema)
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "parsed": parsed,
    }
