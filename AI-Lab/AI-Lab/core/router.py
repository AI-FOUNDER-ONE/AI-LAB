"""
core/router.py - 智能路由引擎
=============================
从 unified_orchestrator 拆出：RoutingStrategy、SmartRouter。
"""

import re
from enum import Enum
from typing import Optional, List, Dict, Tuple

from core.context import Message, EnhancedConversationContext
from config import AppState


class RoutingStrategy(Enum):
    """路由策略"""
    EXPLICIT_MENTION = "explicit_mention"      # @提及优先级
    STRUCTURED_COMMAND = "structured_command"  # 结构化命令（下一发言者:）
    INTENT_ANALYSIS = "intent_analysis"        # 意图分析
    STAGE_DEFAULT = "stage_default"            # 阶段默认路由
    USER_PREFERENCE = "user_preference"        # 用户偏好
    CONSENSUS_BASED = "consensus_based"        # 基于共识


STRATEGY_WEIGHTS = {
    RoutingStrategy.EXPLICIT_MENTION: 10,
    RoutingStrategy.STRUCTURED_COMMAND: 8,
    RoutingStrategy.INTENT_ANALYSIS: 3,
    RoutingStrategy.STAGE_DEFAULT: 2,
    RoutingStrategy.CONSENSUS_BASED: 1,
}


class SmartRouter:
    """智能路由引擎：多策略决策。支持 PM 通过 set_forced_next_speaker 强制指定下一发言者。"""

    def __init__(self, context: EnhancedConversationContext):
        self.context = context
        self.participants = ["CKO", "PM", "Arch", "Designer", "Coder", "Validator"]
        self.routing_history: List[Tuple[str, str, RoutingStrategy]] = []  # (from_role, to_role, strategy)
        self._forced_next_speaker: Optional[str] = None

    def set_forced_next_speaker(self, role: str) -> None:
        """强制指定下一发言者（由 PM 的 delegate_to_role 等工具调用）。下次 decide_next_speaker 将返回该角色并清除。"""
        self._forced_next_speaker = role

    def decide_next_speaker(self, current_state: AppState) -> Optional[str]:
        """决策下一发言者（多策略融合）。若 PM 已通过 set_forced_next_speaker 指定，则优先返回该角色。"""
        if self._forced_next_speaker:
            role = self._forced_next_speaker
            self._forced_next_speaker = None
            if role in self.participants:
                last_msg = self.context.get_last_message()
                self.routing_history.append((last_msg.role if last_msg else "PM", role, RoutingStrategy.STRUCTURED_COMMAND))
                return role
        last_msg = self.context.get_last_message()
        if not last_msg:
            return "PM"  # 默认起始

        # 收集所有策略的建议
        strategies = [
            (self._explicit_mention, RoutingStrategy.EXPLICIT_MENTION),
            (self._structured_command, RoutingStrategy.STRUCTURED_COMMAND),
            (self._intent_analysis, RoutingStrategy.INTENT_ANALYSIS),
            (self._stage_default, RoutingStrategy.STAGE_DEFAULT),
            (self._consensus_based, RoutingStrategy.CONSENSUS_BASED),
        ]

        candidates: Dict[str, int] = {}  # 角色 -> 得分

        for strategy_func, strategy_type in strategies:
            result = strategy_func(last_msg, current_state)
            if result:
                if result not in candidates:
                    candidates[result] = 0
                candidates[result] += STRATEGY_WEIGHTS.get(strategy_type, 1)

        # 选择得分最高的角色
        if candidates:
            selected = max(candidates.items(), key=lambda x: x[1])[0]

            # 需求打磨阶段只允许 CKO 发言，禁止 PM/Arch/Designer 等插入
            if current_state == AppState.GROUNDING and selected != "CKO":
                return None

            # 防止死循环：检查最近路由历史
            recent_routes = [r[1] for r in self.routing_history[-3:]]  # 最近3次路由目标
            if selected in recent_routes and len(recent_routes) >= 3:
                # 尝试选择第二高的角色
                sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
                if len(sorted_candidates) > 1:
                    selected = sorted_candidates[1][0]

            # 记录路由决策
            strategy_used = self._determine_strategy(selected, strategies, last_msg, current_state)
            self.routing_history.append((last_msg.role, selected, strategy_used))

            return selected

        return None

    def _explicit_mention(self, last_msg: Message, current_state: AppState) -> Optional[str]:
        """策略1：显式@提及"""
        if last_msg.mentions:
            for mention in last_msg.mentions:
                for p in self.participants:
                    if p.lower() == mention.lower():
                        # 防乒乓：不将发言权交回给刚发言的人
                        if p != last_msg.role:
                            return p
        return None

    def _structured_command(self, last_msg: Message, current_state: AppState) -> Optional[str]:
        """策略2：结构化命令（下一发言者: / NEXT_SPEAKER:）"""
        match = re.search(r'(?:下一发言者|NEXT_SPEAKER)\s*:\s*([A-Za-z]+)', last_msg.content, re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            for p in self.participants:
                if p.lower() == target.lower():
                    if p != last_msg.role:
                        return p
        return None

    def _intent_analysis(self, last_msg: Message, current_state: AppState) -> Optional[str]:
        """策略3：意图分析。方案博弈阶段不因「代码/实现」把发言权交给 Coder，避免过早写代码。"""
        content_lower = last_msg.content.lower()

        # 问题意图：通常需要专家回答
        if "?" in last_msg.content or any(word in content_lower for word in ["如何", "怎么", "为什么", "请问"]):
            if any(word in content_lower for word in ["架构", "设计", "系统", "数据库"]):
                return "Arch"
            elif any(word in content_lower for word in ["界面", "UI", "UX", "设计", "样式"]):
                return "Designer"
            elif any(word in content_lower for word in ["代码", "实现", "bug", "错误", "修复"]):
                # 方案博弈阶段：实现类问题交给 Arch/Designer 讲思路，不交给 Coder
                if current_state == AppState.DEBATE:
                    return "Arch"  # 实现思路、技术可行性由架构先答
                return "Coder"
            elif any(word in content_lower for word in ["测试", "验证", "质量"]):
                return "Validator"
            elif any(word in content_lower for word in ["需求", "任务", "范围", "计划"]):
                return "PM"

        # 决策意图：需要PM或CKO
        if any(word in content_lower for word in ["决定", "决策", "批准", "否决", "终审"]):
            if current_state == AppState.DEBATE:
                return "PM"
            else:
                return "CKO"

        return None

    def _stage_default(self, last_msg: Message, current_state: AppState) -> Optional[str]:
        """策略4：阶段默认路由"""
        task_type = self.context.task_type

        if current_state == AppState.GROUNDING:
            # 仅允许 Commander ↔ CKO 对话，确认立项前其他角色不插入
            if last_msg.role == "Commander":
                return "CKO"
            elif last_msg.role == "CKO":
                return None  # 等待用户继续与 CKO 讨论或点击「确认立项」
            return None

        elif current_state == AppState.DEBATE:
            # 基于任务类型的默认辩论顺序
            if task_type == "RESEARCH":
                if last_msg.role == "PM": return "CKO"
                if last_msg.role == "CKO": return "Arch"
                if last_msg.role == "Arch": return "Validator"
                return "PM"
            elif task_type == "DESIGN":
                if last_msg.role == "PM": return "Designer"
                if last_msg.role == "Designer": return "Arch"
                if last_msg.role == "Arch": return "PM"
                return "PM"
            else:  # SOFTWARE
                if last_msg.role == "PM": return "Arch"
                if last_msg.role == "Arch": return "Designer"
                if last_msg.role == "Designer": return "PM"
                return "PM"

        elif current_state == AppState.PRODUCTION:
            if last_msg.role == "PM": return "Coder"
            if last_msg.role == "Coder": return "Validator"
            if last_msg.role == "Validator":
                if "FAIL" in last_msg.content or "❌" in last_msg.content:
                    return "Coder"
                else:
                    return "PM"
            return "PM"

        elif current_state == AppState.VERIFICATION:
            if last_msg.role == "Validator": return "CKO"
            if last_msg.role == "CKO": return "PM"
            return "Validator"

        return "PM"  # 默认回退

    def _consensus_based(self, last_msg: Message, current_state: AppState) -> Optional[str]:
        """策略5：基于共识的路由"""
        # 当共识度高时，推进流程；共识度低时，引入更多角色
        consensus = self.context.consensus_level

        if current_state == AppState.DEBATE:
            if consensus > 0.7:  # 高共识，推进到PM决策
                if last_msg.role != "PM":
                    return "PM"
            elif consensus < 0.3:  # 低共识，引入更多专家
                # 检查哪些角色最近没有发言
                recent_roles = [msg.role for msg in self.context.history[-5:]]
                for role in ["Arch", "Designer", "CKO"]:
                    if role not in recent_roles:
                        return role

        return None

    def _determine_strategy(self, selected_role: str, strategies: List,
                           last_msg: Message, current_state: AppState) -> RoutingStrategy:
        """确定实际使用的策略"""
        for strategy_func, strategy_type in strategies:
            result = strategy_func(last_msg, current_state)
            if result == selected_role:
                return strategy_type
        return RoutingStrategy.STAGE_DEFAULT  # 默认
