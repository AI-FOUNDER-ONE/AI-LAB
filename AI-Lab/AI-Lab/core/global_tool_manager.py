"""
global_tool_manager.py - 全局工具管理器
=======================================

基于上下文感知的智能工具管理系统，扩展ToolSecurityManager，提供：
1. 上下文感知工具推荐
2. 动态工具注册和发现
3. 工具依赖管理
4. 工具元数据管理
5. 工具使用统计和监控
"""

import time
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入现有的ToolSecurityManager和枚举
from core.tool_security import ToolSecurityManager, ToolPermission
from config import AppState


class ToolTimeoutError(Exception):
    """工具执行超时异常"""
    def __init__(self, tool_name: str, timeout_seconds: float):
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        super().__init__(f"工具 '{tool_name}' 执行超时 ({timeout_seconds}s)")

# ---------- 工具权限矩阵：角色 + 阶段 ----------
# 未在 TOOL_PERMISSIONS 中配置的工具默认对所有角色和阶段开放
TOOL_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "requirements_analyzer": {
        "allowed_roles": ["CKO", "PM"],
        "allowed_stages": ["GROUNDING", "DEBATE"],
    },
    "code_validator": {
        "allowed_roles": ["Validator", "Coder"],
        "allowed_stages": ["PRODUCTION", "VERIFICATION"],
    },
    "code_reviewer": {
        "allowed_roles": ["Validator", "CKO"],
        "allowed_stages": ["PRODUCTION", "VERIFICATION"],
    },
    "architecture_evaluator": {
        "allowed_roles": ["Arch", "CKO"],
        "allowed_stages": ["DEBATE", "VERIFICATION"],
    },
    "mermaid_generator": {
        "allowed_roles": ["Arch", "Designer"],
        "allowed_stages": ["DEBATE", "PRODUCTION"],
    },
    "file_reader": {
        "allowed_roles": [],
        "allowed_stages": [],
    },
    "file_writer": {
        "allowed_roles": ["Coder"],
        "allowed_stages": ["PRODUCTION"],
    },
    "checklist_tracker": {
        "allowed_roles": ["PM", "CKO"],
        "allowed_stages": [],  # 空表示所有阶段可用
    },
    "context_retriever": {
        "allowed_roles": [],  # 所有角色
        "allowed_stages": [],  # 所有阶段
    },
    "shell_executor": {
        "allowed_roles": ["Coder", "Validator"],
        "allowed_stages": ["PRODUCTION", "VERIFICATION"],
    },
    "json_schema_validator": {
        "allowed_roles": ["PM", "CKO"],
        "allowed_stages": [],  # 所有阶段
    },
}

# ---------- 工具超时与重试配置 ----------
TOOL_CONFIG: Dict[str, Any] = {
    "default_timeout": 30,
    "default_max_retries": 0,
    "overrides": {
        "docx_generator": {"timeout": 60, "max_retries": 1},
        "web_search": {"timeout": 15, "max_retries": 2},
        "code_validator": {"timeout": 45, "max_retries": 0},
        "knowledge_retriever": {"timeout": 20, "max_retries": 1},
    },
}


class TaskCategory(Enum):
    """任务分类枚举"""
    SOFTWARE_DEV = "software_development"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    DESIGN = "design"
    DATA_ANALYSIS = "data_analysis"
    CODE_GENERATION = "code_generation"
    TESTING = "testing"
    REVIEW = "review"
    OTHER = "other"


class ToolCategory(Enum):
    """工具分类枚举"""
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    DOCUMENT_PROCESSING = "document_processing"
    DATA_VISUALIZATION = "data_visualization"
    UI_DESIGN = "ui_design"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    UTILITY = "utility"


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # 依赖的工具名称
    required_permissions: List[str] = field(default_factory=list)  # 需要的系统权限
    example_usage: str = ""
    limitations: str = ""


class GlobalToolManager(ToolSecurityManager):
    """全局工具管理器：扩展ToolSecurityManager，添加上下文感知功能"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("ai_lab.global_tool_manager")

        # 工具元数据存储
        self.tool_metadata: Dict[str, ToolMetadata] = {}

        # 最小上下文（仅用于 execute_tool_safely 阶段权限与 get_tool_schema 默认 stage）
        self._current_state: Optional[AppState] = None
        self._current_role: Optional[str] = None

        # 结构化执行日志（供 get_execution_logs / get_execution_stats 使用）
        self._execution_logs: List[Dict[str, Any]] = []

        # 超时执行用线程池（超时/重试对工具函数透明）
        self._executor = ThreadPoolExecutor(max_workers=8)

    def _normalize_stage(self, stage: Any) -> str:
        """将阶段转为字符串（AppState 使用 .name）。"""
        if hasattr(stage, "name"):
            return getattr(stage, "name", str(stage))
        return str(stage)

    def check_permission(self, tool_name: str, role: str, stage: str) -> bool:
        """
        检查当前角色在当前阶段是否有权调用该工具。
        未在 TOOL_PERMISSIONS 中配置的工具默认允许所有角色和阶段。
        stage 为空字符串时不按阶段过滤（视为允许）。
        """
        stage_str = self._normalize_stage(stage)
        if tool_name not in TOOL_PERMISSIONS:
            return True
        perm = TOOL_PERMISSIONS[tool_name]
        allowed_roles = perm.get("allowed_roles") or []
        allowed_stages = perm.get("allowed_stages") or []
        if allowed_roles and role not in allowed_roles:
            return False
        if allowed_stages and stage_str and stage_str not in allowed_stages:
            return False
        return True

    def get_available_tools(self, role: str, stage: str) -> List[ToolMetadata]:
        """
        返回当前角色在当前阶段可用的工具列表（含元数据）。
        仅包含已注册且具有元数据的工具，且通过 check_permission 检查。
        """
        stage_str = self._normalize_stage(stage)
        out: List[ToolMetadata] = []
        for tool_name in self.registered_tools:
            if not self.check_permission(tool_name, role, stage_str):
                continue
            if not self.can_execute(role, tool_name):
                continue
            meta = self.tool_metadata.get(tool_name)
            if meta is not None:
                out.append(meta)
        return out

    def update_context(self, state: Optional[AppState] = None, role: Optional[str] = None, **kwargs: Any) -> None:
        """更新当前上下文（仅 state/role，供权限与推荐用）。可传 context 对象：update_context(context=obj)。"""
        if "context" in kwargs:
            ctx = kwargs["context"]
            state = getattr(ctx, "current_state", state)
            role = getattr(ctx, "current_role", role)
        self._current_state = state
        self._current_role = role
        if state is not None or role is not None:
            self.logger.debug("上下文更新: state=%s, role=%s", state, role)

    def _log_tool_execution(
        self,
        tool_name: str,
        caller_role: str,
        stage: str,
        input_summary: str,
        output_summary: str,
        duration_ms: float,
        success: bool,
        error: str = "",
    ) -> None:
        """写入一条工具执行的结构化日志。"""
        log_entry = {
            "tool_name": tool_name,
            "caller": caller_role,
            "stage": stage,
            "input_summary": input_summary[:200],
            "output_summary": output_summary[:200],
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        self._execution_logs.append(log_entry)

    def get_execution_logs(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        返回执行日志列表。若传入 session_id 则仅返回该会话的日志；
        当前实现未在日志中写入 session_id，故 session_id 非空时返回空列表，可后续扩展。
        """
        if session_id is not None:
            return [e for e in self._execution_logs if e.get("session_id") == session_id]
        return list(self._execution_logs)

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        返回执行统计：total_calls, success_rate, avg_duration_ms, most_used_tools。
        """
        logs = self._execution_logs
        total = len(logs)
        if total == 0:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "most_used_tools": [],
            }
        success_count = sum(1 for e in logs if e.get("success"))
        durations = [e.get("duration_ms", 0) for e in logs]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        tool_counts = Counter(e.get("tool_name", "") for e in logs)
        most_used = [{"tool_name": name, "count": count} for name, count in tool_counts.most_common(10)]
        return {
            "total_calls": total,
            "success_rate": success_count / total,
            "avg_duration_ms": round(avg_duration, 2),
            "most_used_tools": most_used,
        }

    def _get_tool_timeout_config(self, tool_name: str) -> Tuple[float, int]:
        """返回 (timeout_秒, max_retries)。"""
        overrides = TOOL_CONFIG.get("overrides") or {}
        cfg = overrides.get(tool_name, {})
        timeout = cfg.get("timeout", TOOL_CONFIG.get("default_timeout", 30))
        max_retries = cfg.get("max_retries", TOOL_CONFIG.get("default_max_retries", 0))
        return float(timeout), int(max_retries)

    def _execute_tool_once(self, role: str, tool_name: str, args: Dict) -> Dict[str, Any]:
        """单次执行：直接调用父类 execute_tool_safely，供线程池 + 超时使用。"""
        return ToolSecurityManager.execute_tool_safely(self, role, tool_name, args)

    def execute_tool_safely(self, role: str, tool_name: str, args: Dict) -> Dict[str, Any]:
        """
        安全执行工具：权限检查 → 超时 + 重试（ThreadPoolExecutor + future.result(timeout）→ 执行日志。
        超时抛出 ToolTimeoutError；重试时每次失败 sleep 1 秒再试，并记录日志。
        """
        if self._current_state is not None:
            if not self.check_permission(tool_name, role, self._current_state):
                return {
                    "success": False,
                    "error": f"角色 '{role}' 在当前阶段无权调用工具 '{tool_name}'（权限矩阵限制）",
                }
            stage = self._normalize_stage(self._current_state)
        else:
            stage = ""

        timeout_seconds, max_retries = self._get_tool_timeout_config(tool_name)
        input_summary = str(args)[:200]
        start = time.time()
        last_result: Optional[Dict[str, Any]] = None
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                future = self._executor.submit(self._execute_tool_once, role, tool_name, args)
                last_result = future.result(timeout=timeout_seconds)
                last_error = None
                break
            except FuturesTimeoutError:
                last_error = ToolTimeoutError(tool_name, timeout_seconds)
                self.logger.warning(
                    "工具 %s 执行超时 (%.0fs)，重试 %d/%d",
                    tool_name, timeout_seconds, attempt + 1, max_retries + 1,
                )
                if attempt < max_retries:
                    time.sleep(1)
                else:
                    raise last_error
            except Exception as e:
                last_error = e
                self.logger.warning(
                    "工具 %s 执行异常: %s，重试 %d/%d",
                    tool_name, e, attempt + 1, max_retries + 1,
                )
                if attempt < max_retries:
                    time.sleep(1)
                else:
                    raise

        duration_ms = (time.time() - start) * 1000
        success = last_result.get("success", False) if last_result else False
        output_summary = str(last_result.get("result", last_result.get("error", "")))[:200] if last_result else ""
        err_msg = "" if success else (last_result.get("error", "") if last_result else str(last_error or ""))
        self._log_tool_execution(
            tool_name=tool_name,
            caller_role=role,
            stage=stage,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=duration_ms,
            success=success,
            error=err_msg,
        )
        return last_result

    def register_tool_with_metadata(self,
                                   tool_name: str,
                                   tool_func: Callable,
                                   metadata: ToolMetadata,
                                   allowed_roles: List[str] = None,
                                   permission_level: ToolPermission = ToolPermission.LOCAL_EXECUTION) -> bool:
        """注册工具并关联元数据"""
        success = self.register_tool(tool_name, tool_func, allowed_roles, permission_level, metadata.description)
        if success:
            self.tool_metadata[tool_name] = metadata
            self.logger.info(f"已注册工具 '{tool_name}' (类别: {metadata.category.value})")
        return success

    def recommend_tools(self, role: str, stage: str, task_type: str = "") -> List[ToolMetadata]:
        """
        基于权限矩阵的简单推荐：返回角色在当前阶段可用的工具列表。
        可选按 task_type 简单排序（SOFTWARE 时代码类工具靠前）。
        """
        available = self.get_available_tools(role, stage)
        if task_type == "SOFTWARE":
            code_cats = (ToolCategory.CODE_GENERATION, ToolCategory.CODE_ANALYSIS)
            code_tools = [t for t in available if t.category in code_cats]
            other_tools = [t for t in available if t.category not in code_cats]
            return code_tools + other_tools
        return available

    def get_tool_schema_for_agent(
        self, role: str, stage: Optional[str] = None, include_recommended_only: bool = True
    ) -> List[Dict]:
        """
        为 Agent 获取工具 JSON Schema。

        Args:
            role: Agent 角色
            stage: 阶段（未传时使用 _current_state）；空字符串表示不按阶段过滤
            include_recommended_only: 为 True 时仅包含 recommend_tools 返回的工具
        """
        stage_str = self._normalize_stage(stage if stage is not None else self._current_state) if (stage is not None or self._current_state is not None) else ""
        if include_recommended_only:
            recommended = self.recommend_tools(role, stage_str, task_type="")
            tool_names = [t.name for t in recommended]
        else:
            available = self.get_available_tools(role, stage_str if stage_str else "")
            tool_names = [t.name for t in available]

        # 转换为JSON Schema格式
        tools_schema = []
        for tool_name in tool_names:
            if tool_name in self.registered_tools:
                tool_info = self.registered_tools[tool_name]

                # 从工具函数中提取参数schema
                func = tool_info["function"]
                try:
                    import inspect
                    sig = inspect.signature(func)
                    params = {}
                    required = []

                    for param_name, param in sig.parameters.items():
                        if param_name == 'self':
                            continue

                        param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                        param_default = param.default if param.default != inspect.Parameter.empty else None

                        # 简化类型映射
                        type_map = {
                            str: "string",
                            int: "integer",
                            float: "number",
                            bool: "boolean",
                            list: "array",
                            dict: "object"
                        }
                        param_type_str = type_map.get(param_type, "string")

                        param_schema = {"type": param_type_str}
                        if param_default is not None:
                            param_schema["default"] = param_default
                        else:
                            required.append(param_name)

                        params[param_name] = param_schema

                    parameters_schema = {
                        "type": "object",
                        "properties": params,
                        "required": required if required else None
                    }

                    tools_schema.append({
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool_info.get("description", ""),
                            "parameters": parameters_schema
                        }
                    })

                except Exception as e:
                    self.logger.warning(f"无法为工具 '{tool_name}' 生成schema: {e}")

        return tools_schema

    def record_tool_usage(self, tool_name: str, success: bool):
        """记录工具使用情况"""
        if tool_name in self.tool_metadata:
            metadata = self.tool_metadata[tool_name]
            metadata.usage_count += 1
            metadata.last_used = datetime.now()

            self.logger.debug(f"记录工具使用: {tool_name}, 成功={success}, 使用次数={metadata.usage_count}")

    def get_tool_statistics(self) -> Dict[str, Any]:
        """获取工具使用统计"""
        stats = {
            "total_tools": len(self.registered_tools),
            "tools_by_category": {},
            "top_used_tools": [],
            "success_rate_by_tool": {},
            "recent_executions": self.execution_history[-20:] if self.execution_history else [],
        }

        # 按类别统计
        for tool_name, metadata in self.tool_metadata.items():
            category = metadata.category.value
            if category not in stats["tools_by_category"]:
                stats["tools_by_category"][category] = 0
            stats["tools_by_category"][category] += 1

        # 最常使用的工具
        sorted_by_usage = sorted(self.tool_metadata.items(),
                                key=lambda x: x[1].usage_count,
                                reverse=True)
        stats["top_used_tools"] = [
            {"name": name, "usage_count": metadata.usage_count, "last_used": metadata.last_used}
            for name, metadata in sorted_by_usage[:10]
        ]

        # 成功率统计
        for tool_name in self.registered_tools.keys():
            tool_executions = [e for e in self.execution_history if e.get("tool") == tool_name]
            if tool_executions:
                successful = sum(1 for e in tool_executions if e.get("success", False))
                stats["success_rate_by_tool"][tool_name] = successful / len(tool_executions)

        return stats

    def export_tool_registry(self, filepath: str):
        """导出工具注册表到JSON文件"""
        registry = {
            "export_time": datetime.now().isoformat(),
            "tools": {},
            "metadata": {},
            "statistics": self.get_tool_statistics(),
        }

        for tool_name, tool_info in self.registered_tools.items():
            registry["tools"][tool_name] = {
                "description": tool_info.get("description", ""),
                "permission_level": tool_info["permission_level"].value,
                "allowed_roles": tool_info["allowed_roles"],
            }

            if tool_name in self.tool_metadata:
                metadata = self.tool_metadata[tool_name]
                registry["metadata"][tool_name] = {
                    "category": metadata.category.value,
                    "version": metadata.version,
                    "author": metadata.author,
                    "created_at": metadata.created_at.isoformat(),
                    "last_used": metadata.last_used.isoformat() if metadata.last_used else None,
                    "usage_count": metadata.usage_count,
                    "tags": metadata.tags,
                    "dependencies": metadata.dependencies,
                    "example_usage": metadata.example_usage,
                }

        try:
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(registry, f, ensure_ascii=False, indent=2)
            self.logger.info(f"工具注册表已导出到: {filepath}")
        except Exception as e:
            self.logger.error(f"导出工具注册表失败: {e}")

    def import_tool_registry(self, filepath: str) -> bool:
        """从JSON文件导入工具注册表（注意：只导入元数据，不注册函数）"""
        try:
            import json
            with open(filepath, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            self.logger.info(f"从 {filepath} 导入工具注册表，包含 {len(registry.get('tools', {}))} 个工具")

            # 注意：这里只导入元数据，不注册实际的函数
            # 实际函数需要在运行时重新注册
            for tool_name, tool_info in registry.get("tools", {}).items():
                # 可以在这里记录工具信息，但函数需要后续注册
                self.logger.debug(f"导入工具信息: {tool_name}")

            return True

        except Exception as e:
            self.logger.error(f"导入工具注册表失败: {e}")
            return False