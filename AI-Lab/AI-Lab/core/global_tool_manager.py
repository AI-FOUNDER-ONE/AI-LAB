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
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入现有的ToolSecurityManager和枚举
from core.tool_security import ToolSecurityManager, ToolPermission
from config import AppState


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


@dataclass
class ContextInfo:
    """上下文信息"""
    current_state: AppState
    current_role: str
    task_category: TaskCategory
    mission_protocol: Optional[str] = None
    recent_messages: List[str] = field(default_factory=list)
    active_agents: List[str] = field(default_factory=list)
    project_type: str = "general"


class GlobalToolManager(ToolSecurityManager):
    """全局工具管理器：扩展ToolSecurityManager，添加上下文感知功能"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("ai_lab.global_tool_manager")

        # 工具元数据存储
        self.tool_metadata: Dict[str, ToolMetadata] = {}

        # 上下文信息
        self.current_context: Optional[ContextInfo] = None

        # 工具推荐权重
        self.recommendation_weights = {
            "category_match": 2.0,
            "state_match": 1.5,
            "role_match": 1.2,
            "recent_usage": 0.8,
            "success_rate": 1.0,
        }

        # 初始化工具分类映射
        self._init_tool_category_mappings()

    def _init_tool_category_mappings(self):
        """初始化工具分类映射"""
        # 状态到工具分类的映射
        self.state_to_categories: Dict[AppState, List[ToolCategory]] = {
            AppState.GROUNDING: [ToolCategory.DOCUMENT_PROCESSING],
            AppState.DEBATE: [ToolCategory.ARCHITECTURE, ToolCategory.UI_DESIGN],
            AppState.PRODUCTION: [ToolCategory.CODE_GENERATION, ToolCategory.CODE_ANALYSIS],
            AppState.VERIFICATION: [ToolCategory.TESTING, ToolCategory.SECURITY],
            AppState.DELIVERY: [ToolCategory.DOCUMENT_PROCESSING, ToolCategory.UTILITY],
        }

        # 角色到工具分类的映射
        self.role_to_categories: Dict[str, List[ToolCategory]] = {
            "CKO": [ToolCategory.DOCUMENT_PROCESSING, ToolCategory.UTILITY],
            "PM": [ToolCategory.ARCHITECTURE, ToolCategory.UTILITY],
            "Arch": [ToolCategory.ARCHITECTURE, ToolCategory.CODE_ANALYSIS],
            "Designer": [ToolCategory.UI_DESIGN, ToolCategory.DATA_VISUALIZATION],
            "Coder": [ToolCategory.CODE_GENERATION, ToolCategory.CODE_ANALYSIS],
            "Validator": [ToolCategory.TESTING, ToolCategory.SECURITY],
            "QA": [ToolCategory.TESTING, ToolCategory.UTILITY],
        }

        # 任务类别到工具分类的映射
        self.task_to_categories: Dict[TaskCategory, List[ToolCategory]] = {
            TaskCategory.SOFTWARE_DEV: [ToolCategory.CODE_GENERATION, ToolCategory.ARCHITECTURE,
                                       ToolCategory.TESTING, ToolCategory.DEPENDENCY],
            TaskCategory.DOCUMENTATION: [ToolCategory.DOCUMENT_PROCESSING],
            TaskCategory.RESEARCH: [ToolCategory.DATA_VISUALIZATION, ToolCategory.UTILITY],
            TaskCategory.DESIGN: [ToolCategory.UI_DESIGN, ToolCategory.DATA_VISUALIZATION],
            TaskCategory.DATA_ANALYSIS: [ToolCategory.DATA_VISUALIZATION, ToolCategory.UTILITY],
            TaskCategory.CODE_GENERATION: [ToolCategory.CODE_GENERATION, ToolCategory.CODE_ANALYSIS],
            TaskCategory.TESTING: [ToolCategory.TESTING, ToolCategory.SECURITY],
            TaskCategory.REVIEW: [ToolCategory.CODE_ANALYSIS, ToolCategory.ARCHITECTURE],
        }

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

    def update_context(self, context: ContextInfo):
        """更新当前上下文信息"""
        self.current_context = context
        self.logger.debug(f"上下文更新: 状态={context.current_state}, 角色={context.current_role}, 任务={context.task_category}")

    def recommend_tools(self,
                       role: str = None,
                       limit: int = 5,
                       include_all_available: bool = False) -> List[Dict[str, Any]]:
        """
        基于当前上下文推荐工具

        Args:
            role: 推荐给特定角色（默认使用当前上下文角色）
            limit: 返回的工具数量限制
            include_all_available: 是否包含所有可用工具（不仅仅是推荐工具）

        Returns:
            推荐工具列表，包含工具信息和推荐分数
        """
        if not self.current_context:
            self.logger.warning("上下文未设置，返回所有可用工具")
            return self._get_all_available_tools(role, limit)

        target_role = role or self.current_context.current_role
        recommendations = []

        for tool_name, tool_info in self.registered_tools.items():
            # 检查权限
            if not self.can_execute(target_role, tool_name):
                continue

            # 计算推荐分数
            score = self._calculate_recommendation_score(tool_name, target_role)

            # 获取工具元数据
            metadata = self.tool_metadata.get(tool_name)

            recommendations.append({
                "name": tool_name,
                "description": tool_info.get("description", ""),
                "category": metadata.category.value if metadata else "unknown",
                "permission_level": tool_info["permission_level"].value,
                "allowed_roles": tool_info["allowed_roles"],
                "recommendation_score": score,
                "metadata": metadata.__dict__ if metadata else {},
            })

        # 按推荐分数排序
        recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)

        if include_all_available:
            # 包含所有可用工具，但按推荐分数排序
            return recommendations[:limit]
        else:
            # 只返回推荐分数较高的工具
            filtered = [r for r in recommendations if r["recommendation_score"] > 0.3]
            return filtered[:limit]

    def _calculate_recommendation_score(self, tool_name: str, role: str) -> float:
        """计算工具推荐分数"""
        if not self.current_context:
            return 0.5  # 默认分数

        metadata = self.tool_metadata.get(tool_name)
        if not metadata:
            return 0.5

        score = 0.0
        weights = self.recommendation_weights

        # 1. 类别匹配分数
        category_score = self._calculate_category_match_score(metadata.category)
        score += category_score * weights["category_match"]

        # 2. 状态匹配分数
        state_score = self._calculate_state_match_score(metadata.category)
        score += state_score * weights["state_match"]

        # 3. 角色匹配分数
        role_score = self._calculate_role_match_score(metadata.category, role)
        score += role_score * weights["role_match"]

        # 4. 使用历史分数
        usage_score = self._calculate_usage_score(metadata)
        score += usage_score * weights["recent_usage"]

        # 5. 成功率分数
        success_score = self._calculate_success_rate_score(tool_name)
        score += success_score * weights["success_rate"]

        # 归一化到0-1范围
        max_possible_score = sum(weights.values())
        normalized_score = score / max_possible_score if max_possible_score > 0 else 0

        return normalized_score

    def _calculate_category_match_score(self, tool_category: ToolCategory) -> float:
        """计算工具类别与任务类别的匹配分数"""
        if not self.current_context or not self.current_context.task_category:
            return 0.5

        expected_categories = self.task_to_categories.get(self.current_context.task_category, [])
        if tool_category in expected_categories:
            return 1.0

        # 检查相关类别
        related_categories = self._get_related_categories(tool_category)
        if any(cat in expected_categories for cat in related_categories):
            return 0.7

        return 0.3

    def _calculate_state_match_score(self, tool_category: ToolCategory) -> float:
        """计算工具类别与当前状态的匹配分数"""
        if not self.current_context:
            return 0.5

        expected_categories = self.state_to_categories.get(self.current_context.current_state, [])
        if tool_category in expected_categories:
            return 1.0

        return 0.3

    def _calculate_role_match_score(self, tool_category: ToolCategory, role: str) -> float:
        """计算工具类别与角色的匹配分数"""
        expected_categories = self.role_to_categories.get(role, [])
        if tool_category in expected_categories:
            return 1.0

        return 0.5

    def _calculate_usage_score(self, metadata: ToolMetadata) -> float:
        """计算使用历史分数（考虑使用次数和最近使用时间）"""
        if metadata.usage_count == 0:
            return 0.5  # 未使用过的工具给中等分数

        # 基于使用次数的分数（使用越多，分数越高，但边际递减）
        usage_factor = min(metadata.usage_count / 10, 1.0)
        usage_score = 0.3 + 0.7 * usage_factor

        # 基于最近使用时间的衰减
        if metadata.last_used:
            days_since_last_use = (datetime.now() - metadata.last_used).days
            recency_factor = max(0, 1.0 - days_since_last_use / 30)  # 30天衰减周期
            usage_score *= recency_factor

        return usage_score

    def _calculate_success_rate_score(self, tool_name: str) -> float:
        """计算工具执行成功率分数"""
        # 从执行历史中计算成功率
        tool_executions = [e for e in self.execution_history if e.get("tool") == tool_name]
        if not tool_executions:
            return 0.7  # 没有历史记录，给中等分数

        successful = sum(1 for e in tool_executions if e.get("success", False))
        success_rate = successful / len(tool_executions)

        # 有至少5次执行记录时，才完全信任成功率
        confidence = min(len(tool_executions) / 5, 1.0)

        return 0.3 + 0.7 * success_rate * confidence

    def _get_related_categories(self, category: ToolCategory) -> List[ToolCategory]:
        """获取相关工具类别"""
        related_map = {
            ToolCategory.CODE_GENERATION: [ToolCategory.CODE_ANALYSIS, ToolCategory.UTILITY],
            ToolCategory.CODE_ANALYSIS: [ToolCategory.CODE_GENERATION, ToolCategory.TESTING],
            ToolCategory.DOCUMENT_PROCESSING: [ToolCategory.UTILITY],
            ToolCategory.DATA_VISUALIZATION: [ToolCategory.UI_DESIGN],
            ToolCategory.UI_DESIGN: [ToolCategory.DATA_VISUALIZATION, ToolCategory.ARCHITECTURE],
            ToolCategory.ARCHITECTURE: [ToolCategory.CODE_ANALYSIS, ToolCategory.DEPENDENCY],
            ToolCategory.TESTING: [ToolCategory.SECURITY, ToolCategory.CODE_ANALYSIS],
            ToolCategory.SECURITY: [ToolCategory.TESTING],
            ToolCategory.DEPENDENCY: [ToolCategory.CODE_ANALYSIS],
            ToolCategory.UTILITY: [ToolCategory.DOCUMENT_PROCESSING],
        }
        return related_map.get(category, [])

    def _get_all_available_tools(self, role: str, limit: int) -> List[Dict[str, Any]]:
        """获取所有可用的工具"""
        tools = []
        for tool_name, tool_info in self.registered_tools.items():
            if not self.can_execute(role, tool_name):
                continue

            metadata = self.tool_metadata.get(tool_name)

            tools.append({
                "name": tool_name,
                "description": tool_info.get("description", ""),
                "category": metadata.category.value if metadata else "unknown",
                "permission_level": tool_info["permission_level"].value,
                "allowed_roles": tool_info["allowed_roles"],
                "recommendation_score": 0.5,  # 默认分数
                "metadata": metadata.__dict__ if metadata else {},
            })

        return tools[:limit]

    def get_tool_schema_for_agent(self, role: str, include_recommended_only: bool = True) -> List[Dict]:
        """
        为Agent获取工具JSON Schema

        Args:
            role: Agent角色
            include_recommended_only: 是否只包含推荐的工具

        Returns:
            工具JSON Schema列表
        """
        if include_recommended_only and self.current_context:
            recommended = self.recommend_tools(role, limit=10, include_all_available=False)
            tool_names = [r["name"] for r in recommended]
        else:
            # 获取所有有权限的工具
            tool_names = [name for name in self.registered_tools.keys()
                         if self.can_execute(role, name)]

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