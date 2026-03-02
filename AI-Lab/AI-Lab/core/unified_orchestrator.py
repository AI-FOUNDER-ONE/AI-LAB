"""
unified_orchestrator.py - 统一多智能体编排引擎（全新设计）
==========================================================

结合 V1（状态机驱动）和 V2（事件驱动）的优点，提供更智能、安全、可扩展的协作框架。

核心设计原则：
1. 事件驱动 + 状态机引导：动态路由 + 结构化流程
2. 智能多策略路由：不依赖单一关键词，基于上下文意图
3. 共识形成机制：多角色投票，辩论总结，妥协方案
4. 统一工具平台：安全沙箱，权限控制，集中管理
5. 模块化架构：可插拔组件，易于扩展

架构组件：
- UnifiedOrchestrator: 主编排器
- EnhancedConversationContext: 增强上下文（支持情感分析、意图识别）
- SmartRouter: 智能路由引擎（多策略决策）
- ConsensusEngine: 共识形成引擎（投票、辩论总结）
- ToolSecurityManager: 工具安全管理器（沙箱、权限控制）
- StateGuidanceEngine: 状态引导引擎（状态机 + 事件驱动）
"""

import traceback
import re
import json
import time
from typing import Optional, List, Dict, Any, Callable, Set, Tuple
from enum import Enum
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

# 重用现有组件
from agents.cko_agent import CKOAgent
from agents.pm_agent import PMAgent
from agents.arch_agent import ArchAgent
from agents.designer_agent import DesignerAgent
from agents.coder_agent import CoderAgent
from agents.validator_agent import ValidatorAgent
from agents.base_agent import BaseAgent

from core.state_controller import StateController
from core.session_store import SessionStore
from core.global_tool_manager import GlobalToolManager
from core.tool_security import ToolPermission, ToolSecurityManager
from config import AppState, MAX_DEBATE_ROUNDS

# ==============================================================================
# 1. 增强上下文管理
# ==============================================================================

class MessageIntent(Enum):
    """消息意图分类"""
    STATEMENT = "statement"      # 陈述观点
    QUESTION = "question"        # 提出问题
    CRITIQUE = "critique"        # 批评建议
    AGREEMENT = "agreement"      # 同意支持
    COMMAND = "command"          # 指令命令
    DECISION = "decision"        # 决策裁决
    PROPOSAL = "proposal"        # 方案提议
    CLARIFICATION = "clarification"  # 澄清说明

class Message:
    """增强的消息对象，支持情感分析和意图识别"""
    def __init__(self, role: str, content: str, intent: MessageIntent = MessageIntent.STATEMENT):
        self.role = role
        self.content = content
        self.intent = intent
        self.timestamp = time.time()  # 真实时间戳
        self.mentions: List[str] = self._extract_mentions(content)
        self.emotion_score: float = 0.0  # 情感分数 (-1.0 到 1.0)
        self.confidence_score: float = 1.0  # 置信度分数

    def _extract_mentions(self, text: str) -> List[str]:
        """提取@提及的角色"""
        return re.findall(r"@(\w+)", text)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于序列化"""
        return {
            "role": self.role,
            "content": self.content,
            "intent": self.intent.value,
            "timestamp": self.timestamp,
            "mentions": self.mentions,
            "emotion_score": self.emotion_score,
            "confidence_score": self.confidence_score
        }

class EnhancedConversationContext:
    """增强的对话上下文管理

    支持：
    - 情感分析追踪
    - 意图识别
    - 共识度计算
    - 话题追踪
    """

    def __init__(self):
        self.history: List[Message] = []
        self.artifacts: Dict[str, Any] = {}  # 共享文档/代码
        self.mission_protocol: Dict[str, Any] = {}  # 结构化任务书
        self.task_type: str = "SOFTWARE"  # 任务类型
        self.current_topic: str = ""  # 当前讨论话题
        self.consensus_level: float = 0.0  # 共识度 (0.0-1.0)

    def add_message(self, role: str, content: str, intent: MessageIntent = MessageIntent.STATEMENT) -> Message:
        """添加消息到历史记录"""
        msg = Message(role, content, intent)
        self.history.append(msg)

        # 更新共识度（简化实现）
        self._update_consensus_level()

        return msg

    def get_recent_history(self, limit: int = 10) -> str:
        """获取最近的历史记录（用于LLM上下文）"""
        lines = []
        for msg in self.history[-limit:]:
            lines.append(f"{msg.role}: {msg.content}")
        return "\n".join(lines)

    def get_messages_by_role(self, role: str, limit: int = 5) -> List[Message]:
        """获取特定角色的消息"""
        return [msg for msg in self.history if msg.role == role][-limit:]

    def get_last_message(self) -> Optional[Message]:
        """获取最后一条消息"""
        return self.history[-1] if self.history else None

    def get_messages_by_intent(self, intent: MessageIntent, limit: int = 5) -> List[Message]:
        """获取特定意图的消息"""
        return [msg for msg in self.history if msg.intent == intent][-limit:]

    def _update_consensus_level(self):
        """更新共识度（简化实现）"""
        if len(self.history) < 2:
            self.consensus_level = 0.0
            return

        # 简化的共识度计算：基于最近消息中的关键词
        recent_msgs = self.history[-5:] if len(self.history) >= 5 else self.history
        agreement_keywords = ["同意", "赞同", "支持", "批准", "通过", "✅", "👍"]
        disagreement_keywords = ["反对", "不同意", "拒绝", "驳回", "❌", "👎"]

        agreement_count = 0
        disagreement_count = 0

        for msg in recent_msgs:
            content_lower = msg.content.lower()
            if any(keyword in content_lower for keyword in agreement_keywords):
                agreement_count += 1
            if any(keyword in content_lower for keyword in disagreement_keywords):
                disagreement_count += 1

        total = agreement_count + disagreement_count
        if total > 0:
            self.consensus_level = agreement_count / total
        else:
            self.consensus_level = 0.5  # 中性

# ==============================================================================
# 2. 智能路由引擎
# ==============================================================================

class RoutingStrategy(Enum):
    """路由策略"""
    EXPLICIT_MENTION = "explicit_mention"      # @提及优先级
    STRUCTURED_COMMAND = "structured_command"  # 结构化命令 (NEXT_SPEAKER:)
    INTENT_ANALYSIS = "intent_analysis"        # 意图分析
    STAGE_DEFAULT = "stage_default"            # 阶段默认路由
    USER_PREFERENCE = "user_preference"        # 用户偏好
    CONSENSUS_BASED = "consensus_based"        # 基于共识

class SmartRouter:
    """智能路由引擎：多策略决策"""

    def __init__(self, context: EnhancedConversationContext):
        self.context = context
        self.participants = ["CKO", "PM", "Arch", "Designer", "Coder", "Validator"]
        self.routing_history: List[Tuple[str, str, RoutingStrategy]] = []  # (from_role, to_role, strategy)

    def decide_next_speaker(self, current_state: AppState) -> Optional[str]:
        """决策下一发言者（多策略融合）"""
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
                candidates[result] += 1  # 简单计分

        # 选择得分最高的角色
        if candidates:
            selected = max(candidates.items(), key=lambda x: x[1])[0]

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
        """策略2：结构化命令（NEXT_SPEAKER:）"""
        import re
        match = re.search(r'NEXT_SPEAKER:\s*([A-Za-z]+)', last_msg.content, re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            for p in self.participants:
                if p.lower() == target.lower():
                    if p != last_msg.role:
                        return p
        return None

    def _intent_analysis(self, last_msg: Message, current_state: AppState) -> Optional[str]:
        """策略3：意图分析"""
        content_lower = last_msg.content.lower()

        # 问题意图：通常需要专家回答
        if "?" in last_msg.content or any(word in content_lower for word in ["如何", "怎么", "为什么", "请问"]):
            # 根据关键词决定专家
            if any(word in content_lower for word in ["架构", "设计", "系统", "数据库"]):
                return "Arch"
            elif any(word in content_lower for word in ["界面", "UI", "UX", "设计", "样式"]):
                return "Designer"
            elif any(word in content_lower for word in ["代码", "实现", "bug", "错误", "修复"]):
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
            if last_msg.role == "Commander":
                return "CKO"
            elif last_msg.role == "CKO":
                return "PM"
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

# ==============================================================================
# 3. 共识形成引擎
# ==============================================================================

class ConsensusEngine:
    """共识形成引擎：支持投票、辩论总结、妥协方案"""

    def __init__(self, context: EnhancedConversationContext):
        self.context = context
        self.vote_records: Dict[str, Dict[str, str]] = {}  # 议题 -> {角色 -> 立场}
        self.debate_summaries: Dict[str, str] = {}  # 议题 -> 总结

    def initiate_vote(self, topic: str, options: List[str]) -> Dict[str, Dict[str, str]]:
        """发起投票"""
        self.vote_records[topic] = {}
        return self.vote_records[topic]

    def cast_vote(self, topic: str, role: str, choice: str) -> bool:
        """角色投票"""
        if topic not in self.vote_records:
            return False
        self.vote_records[topic][role] = choice
        return True

    def get_vote_result(self, topic: str) -> Dict[str, Any]:
        """获取投票结果"""
        if topic not in self.vote_records:
            return {"status": "no_vote", "result": None}

        votes = self.vote_records[topic]
        if not votes:
            return {"status": "empty", "result": None}

        # 统计票数
        from collections import Counter
        counter = Counter(votes.values())
        most_common = counter.most_common(1)

        if most_common:
            winning_choice, count = most_common[0]
            total = len(votes)
            return {
                "status": "completed",
                "winning_choice": winning_choice,
                "votes": dict(votes),
                "count": count,
                "total": total,
                "percentage": count / total if total > 0 else 0
            }

        return {"status": "error", "result": None}

    def summarize_debate(self, topic: str, messages: List[Message]) -> str:
        """总结辩论要点"""
        # 提取关键观点
        key_points = []
        disagreements = []
        agreements = []

        for msg in messages:
            if msg.intent == MessageIntent.PROPOSAL:
                key_points.append(f"{msg.role}: {msg.content[:100]}...")
            elif msg.intent == MessageIntent.CRITIQUE:
                disagreements.append(f"{msg.role}: {msg.content[:100]}...")
            elif msg.intent == MessageIntent.AGREEMENT:
                agreements.append(f"{msg.role}: {msg.content[:100]}...")

        summary = f"# 辩论总结: {topic}\n\n"
        summary += f"## 关键观点 ({len(key_points)}个)\n"
        for point in key_points:
            summary += f"- {point}\n"

        summary += f"\n## 分歧点 ({len(disagreements)}个)\n"
        for point in disagreements:
            summary += f"- {point}\n"

        summary += f"\n## 共识点 ({len(agreements)}个)\n"
        for point in agreements:
            summary += f"- {point}\n"

        self.debate_summaries[topic] = summary
        return summary

    def generate_compromise(self, topic: str, conflicting_positions: Dict[str, str]) -> str:
        """生成妥协方案"""
        # 简化的妥协方案生成
        positions = list(conflicting_positions.values())
        if len(positions) < 2:
            return "无显著冲突，无需妥协方案"

        # 提取共同关键词
        all_words = []
        for pos in positions:
            words = set(re.findall(r'\w+', pos.lower()))
            all_words.append(words)

        # 查找共同关键词
        common_words = set.intersection(*all_words) if all_words else set()

        compromise = f"# 妥协方案: {topic}\n\n"
        compromise += "## 分析\n"
        compromise += f"- 涉及{len(positions)}种不同立场\n"
        compromise += f"- 发现{len(common_words)}个共同关注点\n\n"

        compromise += "## 建议方案\n"
        if common_words:
            compromise += "1. **基于共同关注点构建方案**: "
            compromise += ", ".join(list(common_words)[:5]) + "\n"
        compromise += "2. **分阶段实施**: 先实现共识部分，争议部分后续评估\n"
        compromise += "3. **设置评估标准**: 明确成功指标，定期评审\n"

        return compromise

# ==============================================================================
# 4. 工具安全管理器（框架）
# ==============================================================================

# class ToolPermission(Enum):
#     """工具权限级别"""
#     READ_ONLY = "read_only"      # 只读权限
#     LOCAL_EXECUTION = "local_execution"  # 本地执行（受限）
#     FULL_ACCESS = "full_access"  # 完全访问（危险）

class _ToolSecurityManager:
    """工具安全管理器：沙箱执行和权限控制"""

    def __init__(self):
        self.registered_tools: Dict[str, Dict] = {}  # 工具名称 -> 工具定义
        self.role_permissions: Dict[str, Set[str]] = {}  # 角色 -> 允许的工具集合
        self.execution_history: List[Dict] = []  # 执行历史

    def register_tool(self, tool_name: str, tool_func: Callable,
                     allowed_roles: List[str] = None,
                     permission_level: ToolPermission = ToolPermission.LOCAL_EXECUTION,
                     description: str = "") -> bool:
        """注册工具，设置权限"""
        if tool_name in self.registered_tools:
            return False

        self.registered_tools[tool_name] = {
            "function": tool_func,
            "permission_level": permission_level,
            "description": description,
            "allowed_roles": allowed_roles or []  # 空列表表示所有角色可用
        }

        # 更新角色权限
        if allowed_roles:
            for role in allowed_roles:
                if role not in self.role_permissions:
                    self.role_permissions[role] = set()
                self.role_permissions[role].add(tool_name)

        return True

    def can_execute(self, role: str, tool_name: str) -> bool:
        """检查角色是否有权限执行工具"""
        if tool_name not in self.registered_tools:
            return False

        tool_info = self.registered_tools[tool_name]
        allowed_roles = tool_info["allowed_roles"]

        # 如果允许的角色列表为空，表示所有角色可用
        if not allowed_roles:
            return True

        return role in allowed_roles

    def execute_tool_safely(self, role: str, tool_name: str, args: Dict) -> Dict[str, Any]:
        """安全执行工具（带沙箱）"""
        if not self.can_execute(role, tool_name):
            return {"success": False, "error": f"角色 '{role}' 无权执行工具 '{tool_name}'"}

        if tool_name not in self.registered_tools:
            return {"success": False, "error": f"工具 '{tool_name}' 未注册"}

        tool_info = self.registered_tools[tool_name]
        tool_func = tool_info["function"]
        permission_level = tool_info["permission_level"]

        # 记录执行开始
        exec_id = len(self.execution_history)
        start_time = time.time()

        try:
            # 根据权限级别应用不同的安全措施
            if permission_level == ToolPermission.READ_ONLY:
                # 只读工具：可以安全执行
                result = tool_func(**args)
            elif permission_level == ToolPermission.LOCAL_EXECUTION:
                # 本地执行：限制性沙箱
                result = self._execute_in_sandbox(tool_func, args)
            else:  # FULL_ACCESS
                # 完全访问：直接执行（危险）
                result = tool_func(**args)

            # 记录执行成功
            execution_record = {
                "id": exec_id,
                "timestamp": time.time(),
                "role": role,
                "tool": tool_name,
                "args": args,
                "success": True,
                "result": str(result)[:500],  # 截断长结果
                "duration": time.time() - start_time
            }
            self.execution_history.append(execution_record)

            return {"success": True, "result": result}

        except Exception as e:
            # 记录执行失败
            execution_record = {
                "id": exec_id,
                "timestamp": time.time(),
                "role": role,
                "tool": tool_name,
                "args": args,
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
            self.execution_history.append(execution_record)

            return {"success": False, "error": str(e)}

    def _execute_in_sandbox(self, tool_func: Callable, args: Dict) -> Any:
        """在沙箱中执行工具（基于子进程的隔离）"""
        import multiprocessing
        import pickle
        import traceback
        from multiprocessing import TimeoutError as MP_TimeoutError

        # 创建通信队列
        result_queue = multiprocessing.Queue()
        error_queue = multiprocessing.Queue()

        # 定义在子进程中执行的包装函数
        def worker(func_bytes: bytes, args_bytes: bytes, result_q, error_q):
            """子进程工作函数"""
            try:
                # 反序列化函数和参数
                import pickle
                func = pickle.loads(func_bytes)
                args_dict = pickle.loads(args_bytes)

                # 执行函数
                result = func(**args_dict)

                # 序列化结果
                result_q.put(("success", pickle.dumps(result)))

            except Exception as e:
                # 捕获异常并发送
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
                error_q.put(("error", pickle.dumps(error_info)))

        try:
            # 序列化函数和参数
            # 注意：函数必须是可pickle的（不能是lambda或闭包）
            func_bytes = pickle.dumps(tool_func)
            args_bytes = pickle.dumps(args)

            # 创建子进程
            process = multiprocessing.Process(
                target=worker,
                args=(func_bytes, args_bytes, result_queue, error_queue),
                daemon=True  # 主进程退出时子进程也会退出
            )

            process.start()

            # 等待结果，设置超时（30秒）
            timeout = 30
            process.join(timeout=timeout)

            if process.is_alive():
                # 超时，终止进程
                process.terminate()
                process.join(timeout=5)  # 等待终止
                if process.is_alive():
                    process.kill()  # 强制终止
                raise TimeoutError(f"工具执行超时（{timeout}秒）")

            # 检查结果
            if not result_queue.empty():
                status, result_bytes = result_queue.get()
                if status == "success":
                    return pickle.loads(result_bytes)

            if not error_queue.empty():
                status, error_bytes = error_queue.get()
                if status == "error":
                    error_info = pickle.loads(error_bytes)
                    error_msg = f"{error_info['type']}: {error_info['message']}"
                    raise RuntimeError(f"工具执行错误: {error_msg}")

            # 如果没有结果也没有错误，抛出异常
            raise RuntimeError("工具执行未返回结果")

        except (pickle.PickleError, EOFError) as e:
            # 序列化错误
            raise RuntimeError(f"工具无法序列化: {str(e)}")
        except Exception as e:
            # 其他错误
            raise RuntimeError(f"沙箱执行失败: {str(e)}")

# ==============================================================================
# 5. 统一编排器（主类）
# ==============================================================================

class UnifiedOrchestrator(QObject):
    """统一编排器：结合V1和V2的优点"""

    # 信号（保持与现有UI兼容）
    agent_response = pyqtSignal(str, str)
    state_changed = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)
    workflow_completed = pyqtSignal()
    debate_round_info = pyqtSignal(int, int)
    agent_typing = pyqtSignal(str, bool)
    agent_stream_chunk = pyqtSignal(str, str)

    # 内部信号
    _next_turn_ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. 核心组件
        self.state_ctrl = StateController(self)
        self.ctx = EnhancedConversationContext()
        self.router = SmartRouter(self.ctx)
        self.consensus_engine = ConsensusEngine(self.ctx)
        self.tool_security = GlobalToolManager()
        self.session_store = SessionStore()

        # 2. Agent实例
        self.agents_map = self._create_agents()

        # 3. 连接信号
        self._connect_signals()

        # 4. 内部状态
        self._active_worker = None
        self._turn_count = 0
        self._max_turns = 100  # 安全限制

        # 5. 事件循环触发
        self._next_turn_ready.connect(self._process_next_turn)

        print("[UnifiedOrchestrator] 初始化完成")

    def _create_agents(self) -> Dict[str, BaseAgent]:
        """创建所有Agent实例"""
        agents = {
            "CKO": CKOAgent(self, self.tool_security),
            "PM": PMAgent(self, self.tool_security),
            "Arch": ArchAgent(self, self.tool_security),
            "Designer": DesignerAgent(self, self.tool_security),
            "Coder": CoderAgent(self, self.tool_security),
            "Validator": ValidatorAgent(self, self.tool_security)
        }

        # 连接Agent信号
        for role, agent in agents.items():
            agent.typing_started.connect(lambda r=role: self.agent_typing.emit(r, True))
            agent.typing_finished.connect(lambda r=role: self.agent_typing.emit(r, False))
            agent.stream_chunk.connect(self.agent_stream_chunk.emit)

        return agents

    def _connect_signals(self):
        """连接信号"""
        self.state_ctrl.state_changed.connect(self.state_changed.emit)
        self.state_ctrl.error_occurred.connect(self.error_occurred.emit)

    # ==========================================================================
    # 公共API（与现有UI兼容）
    # ==========================================================================

    def inject_user_message(self, message: str):
        """用户消息注入入口"""
        # 1. 在UI中显示
        self.agent_response.emit("Commander", message)

        # 2. 添加到上下文
        self.ctx.add_message("Commander", message, MessageIntent.COMMAND)
        self.session_store.append_meeting_log("Commander", message)

        # 3. 触发事件循环
        self._next_turn_ready.emit()

    def send_to_cko(self, message: str):
        """Bridge Panel入口（Grounding阶段）"""
        # 确保在GROUNDING状态
        if self.state_ctrl.current_state == AppState.IDLE:
            self.state_ctrl.transition_to(AppState.GROUNDING)

        # 作为用户消息处理
        self.inject_user_message(message)

    def confirm_project(self):
        """用户确认立项"""
        # 1. 从上下文提取Mission Protocol
        last_cko_msg = None
        for msg in reversed(self.ctx.history):
            if msg.role == "CKO":
                last_cko_msg = msg.content
                break

        if last_cko_msg:
            try:
                # 尝试提取JSON
                match = re.search(r"```json(.*?)```", last_cko_msg, re.DOTALL)
                protocol_str = match.group(1).strip() if match else last_cko_msg
                self.ctx.mission_protocol = json.loads(protocol_str)
                self.ctx.task_type = self.ctx.mission_protocol.get("task_type", "SOFTWARE").upper()
            except Exception as e:
                print(f"Protocol解析错误: {e}")
                self.ctx.task_type = "SOFTWARE"

        # 2. 更新Agent领域角色
        for role, agent in self.agents_map.items():
            if role != "CKO":
                agent.set_domain_persona(self.ctx.task_type)

        # 3. 转换到DEBATE阶段
        self.state_ctrl.transition_to(AppState.DEBATE)

        # 4. 系统消息
        sys_msg = f"项目已确认。模式: [{self.ctx.task_type}]。进入辩论阶段。"
        self.ctx.add_message("System", sys_msg, MessageIntent.STATEMENT)
        self.agent_response.emit("System", sys_msg)

        # 5. 触发事件循环
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    def new_session(self):
        """开始新会话"""
        print("[UnifiedOrchestrator] 开始新会话...")

        # 重置所有组件
        self.state_ctrl.reset()
        self.ctx = EnhancedConversationContext()
        self.router = SmartRouter(self.ctx)
        self.consensus_engine = ConsensusEngine(self.ctx)
        self.session_store.create_session(user_intent="新会话")
        self._turn_count = 0

        # 停止活跃worker
        if self._active_worker:
            self._active_worker.quit()

        # 通知UI
        self.agent_response.emit("System", "会话已重置。准备接收新命令。")

    def handle_user_intervention(self, message: str):
        """处理用户从 War Room 面板发起的干预指令（兼容V2 API）"""
        print(f"[UnifiedOrchestrator] 用户干预: {message[:30]}...")
        # 将用户干预作为 Commander 消息注入
        self.inject_user_message(message)

    def stop_all(self):
        """中止所有活跃的 Worker 线程（兼容V1 API）"""
        print("[UnifiedOrchestrator] 停止所有工作线程...")
        if self._active_worker:
            self._active_worker.quit()
            self._active_worker = None
        self.agent_response.emit("系统", "🛑 所有任务已中止。")

    # ==========================================================================
    # 事件循环处理
    # ==========================================================================

    def _process_next_turn(self):
        """主事件循环：决定谁发言并执行"""
        current_state = self.state_ctrl.current_state

        # 检查终止条件
        if current_state in (AppState.IDLE, AppState.COMPLETED):
            return

        # 安全检查：防止无限循环
        self._turn_count += 1
        if self._turn_count > self._max_turns:
            self.agent_response.emit("System", f"⚠️ 达到最大交互次数({self._max_turns})，暂停自动流转。")
            return

        # 1. 智能路由决策
        next_role = self.router.decide_next_speaker(current_state)
        print(f"[UnifiedOrchestrator] 下一发言者: {next_role}")

        if not next_role:
            print(f"[UnifiedOrchestrator] 暂停自动流转，等待外部输入")
            return

        # 2. 获取Agent并执行
        agent = self.agents_map.get(next_role)
        if not agent:
            print(f"错误: 未知角色 {next_role}")
            return

        # 3. 准备上下文并执行
        self._run_agent(agent, current_state)

    def _run_agent(self, agent: BaseAgent, current_state: AppState):
        """运行Agent"""
        # 准备上下文
        recent_history = self.ctx.get_recent_history(limit=10)

        # 构建提示（集成状态感知和纪律要求）
        prompt = (
            f"你是War Room讨论组中的{agent.role}。\n"
            f"当前开发阶段: {current_state}\n"
            f"任务类型: {self.ctx.task_type}\n\n"
            f"【核心纪律要求】:\n"
            f"1. 使用流利、自然的中文回复，避免机器翻译腔。\n"
            f"2. 禁止互相吹捧、客套废话或无意义的认同。\n"
            f"3. 发言必须直奔主题，只输出干货、代码、实质性建议或决策。\n"
            f"4. 除非需要强制移交发言权，否则避免随意使用`@角色名`。\n"
            f"5. 如果达成共识或任务完成，请清楚表达。\n\n"
            f"--- 历史对话 ---\n{recent_history}\n\n"
            f"你的回复:"
        )

        # 使用Worker线程执行
        worker = AgentWorker(agent, prompt)
        worker.finished_with_result.connect(self._on_agent_finished)
        worker.error_occurred.connect(lambda r, e: self.error_occurred.emit(e))
        worker.finished.connect(worker.deleteLater)

        self._active_worker = worker
        worker.start()

    def _on_agent_finished(self, role: str, content: str):
        """Agent回复处理"""
        # 0. 处理工具调用结果
        if content.startswith("__TOOL_RESULT__:"):
            try:
                tool_data = json.loads(content[len("__TOOL_RESULT__:"):])
                content = tool_data.get("content", "").strip()
                if not content:
                    content = "【已执行内部工具调用】"
            except Exception as e:
                print(f"[UnifiedOrchestrator] 解析工具调用结果错误: {e}")

        # 1. 更新上下文
        # 自动识别意图（简化）
        intent = MessageIntent.STATEMENT
        content_lower = content.lower()
        if "?" in content or any(word in content_lower for word in ["如何", "怎么", "为什么"]):
            intent = MessageIntent.QUESTION
        elif any(word in content_lower for word in ["建议", "提议", "方案"]):
            intent = MessageIntent.PROPOSAL
        elif any(word in content_lower for word in ["同意", "赞同", "支持", "批准"]):
            intent = MessageIntent.AGREEMENT
        elif any(word in content_lower for word in ["反对", "不同意", "拒绝", "批评"]):
            intent = MessageIntent.CRITIQUE
        elif any(word in content_lower for word in ["决定", "决策", "裁决"]):
            intent = MessageIntent.DECISION

        self.ctx.add_message(role, content, intent)
        self.session_store.append_meeting_log(role, content)

        # 2. 更新UI
        self.agent_response.emit(role, content)

        # 3. 特殊处理（代码提取等）
        if role == "Coder":
            self._handle_code_extraction(content)

        # 4. 检查状态转换（基于决策意图）
        if intent == MessageIntent.DECISION:
            self._check_state_transition(role, content)

        # 5. 继续事件循环
        QTimer.singleShot(1500, self._next_turn_ready.emit)

    def _handle_code_extraction(self, content: str):
        """处理代码提取（从Coder回复中提取代码块）"""
        try:
            # 重用V1/V2中的代码提取逻辑
            import os
            import re
            import datetime

            # 更新会话
            self.session_store.update_session(final_code=content)

            # 提取代码块
            matches = list(re.finditer(r"```([a-zA-Z]*)\n(.*?)```", content, re.DOTALL))

            if matches:
                workspace_dir = os.path.join("data", "workspace")
                os.makedirs(workspace_dir, exist_ok=True)

                saved_files = []
                for i, match in enumerate(matches):
                    lang_tag = match.group(1).strip().lower()
                    pure_code = match.group(2)

                    # 提取文件名
                    filename = None
                    lines = pure_code.split('\n')
                    if lines:
                        first_line = lines[0].strip()
                        name_match = re.search(r'(?://|#|/\*|<!--)\s*filename:\s*([^\s\*>]+)', first_line, re.IGNORECASE)
                        if name_match:
                            filename = name_match.group(1).strip()
                            pure_code = '\n'.join(lines[1:]).strip()

                    if not filename:
                        # 默认文件扩展名映射
                        EXTENSION_MAP = {
                            "python": ".py", "py": ".py",
                            "javascript": ".js", "js": ".js",
                            "typescript": ".ts", "ts": ".ts",
                            "cpp": ".cpp", "c++": ".cpp",
                            "c": ".c", "java": ".java",
                            "html": ".html", "css": ".css",
                            "json": ".json", "yaml": ".yaml", "yml": ".yml",
                            "markdown": ".md", "md": ".md",
                            "bash": ".sh", "sh": ".sh",
                            "sql": ".sql"
                        }
                        ext = EXTENSION_MAP.get(lang_tag, ".py")
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"generated_{timestamp}_{i}{ext}"

                    # 安全写入
                    file_path = os.path.abspath(os.path.join(workspace_dir, filename))
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(pure_code)
                    saved_files.append(file_path)

                # 广播消息
                if saved_files:
                    joined_paths = "\n".join(saved_files)
                    self.agent_response.emit("System", f"💾 代码已保存:\n{joined_paths}")
        except Exception as e:
            print(f"[UnifiedOrchestrator] 代码提取错误: {e}")

    def _check_state_transition(self, role: str, content: str):
        """检查状态转换（基于决策）"""
        current_state = self.state_ctrl.current_state
        content_lower = content.lower()

        if role == "PM":
            # PM批准方案
            if ("批准" in content_lower or "同意" in content_lower or "通过" in content_lower or
                "approve" in content_lower or "✅" in content):
                if current_state == AppState.DEBATE:
                    self.state_ctrl.transition_to(AppState.PRODUCTION)
                    self.agent_response.emit("System", "PM批准方案，进入生产阶段。")

            # PM交付
            elif ("交付" in content_lower or "发布" in content_lower or "完成" in content_lower or
                  "deliver" in content_lower or "🚀" in content):
                if current_state == AppState.PRODUCTION or current_state == AppState.VERIFICATION:
                    self.state_ctrl.transition_to(AppState.DELIVERY)
                    self.agent_response.emit("System", "PM确认交付，进入交付阶段。")

        elif role == "CKO":
            # CKO审计通过
            if ("通过" in content_lower or "批准" in content_lower or "合格" in content_lower or
                "pass" in content_lower or "✅" in content):
                if current_state == AppState.VERIFICATION:
                    self.state_ctrl.transition_to(AppState.DELIVERY)
                    self.agent_response.emit("System", "CKO审计通过，准备交付。")

    def _run_audit(self, stage: str, context: str, callback):
        """运行 CKO 审计"""
        self.agent_response.emit("CKO", f"👁️ [Vision Keeper] 正在审计 {stage} 产出...")
        # 注意: self.ctx.mission_protocol 必须存在
        worker = AuditWorker(self.agents_map["CKO"], stage, context,
                           self.ctx.mission_protocol, self)
        worker.audit_finished.connect(callback)
        worker.error_occurred.connect(self._on_agent_error)
        self._start_worker(worker)

    def _on_agent_error(self, role: str, error_msg: str):
        """统一处理 Agent 错误"""
        self.error_occurred.emit(f"[{role}] {error_msg}")

    def _start_worker(self, worker):
        """启动 Worker 线程（简化实现）"""
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_debate_audit_finished(self, result: str):
        """DEBATE阶段审计完成处理"""
        if result.startswith("FAIL"):
            self.agent_response.emit("CKO", f"❌ [Vision Alert] 审计未通过: {result}")
            # 审计未通过，反馈给PM
            objection_msg = (
                f"CKO (Vision Keeper) 拒绝了当前的 Approved 方案。\n"
                f"审计意见: {result}\n\n"
                f"你需要重新召集大家解决这个问题，或者给出强有力的理由并再次尝试提交。"
            )
            # 这里可以调用PM，但为了简化，我们只是记录
            self.ctx.add_message("CKO", objection_msg, MessageIntent.CRITIQUE)
            self.agent_response.emit("CKO", objection_msg)
        else:
            self.agent_response.emit("CKO", "✅ [Vision Keeper] 审计通过，准许开发。")
            # 进入生产阶段
            self.state_ctrl.transition_to(AppState.PRODUCTION)
            self.agent_response.emit("System", "CKO审计通过，进入生产阶段。")

    def _on_verification_audit_finished(self, result: str):
        """VERIFICATION阶段审计完成处理"""
        if result.startswith("FAIL"):
            self.agent_response.emit("CKO", f"❌ [Vision Alert] 审计未通过: {result}")
            # 审计未通过，需要PM决策
            outcome_msg = (
                f"⚠️ CKO (Vision Keeper) 发现最终交付物严重偏离 Mission Protocol。\n"
                f"审计意见: {result}\n\n"
                f"这是最后一道防线。作为 PM，请仔细评估是否强制返工还是允许带病发布。"
            )
            self.ctx.add_message("CKO", outcome_msg, MessageIntent.CRITIQUE)
            self.agent_response.emit("CKO", outcome_msg)
        else:
            self.agent_response.emit("CKO", "✅ [Vision Keeper] 审计通过，准备交付 PM 验收。")
            # 进入交付阶段
            self.state_ctrl.transition_to(AppState.DELIVERY)
            self.agent_response.emit("System", "CKO审计通过，进入交付阶段。")

# ==============================================================================
# 6. AgentWorker（重用V2实现）
# ==============================================================================

class AgentWorker(QThread):
    """Agent工作线程"""
    finished_with_result = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str, str)

    def __init__(self, agent, message: str, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.message = message

    def run(self):
        try:
            response = self.agent.send_message(self.message)
            self.finished_with_result.emit(self.agent.role, response)
        except Exception as e:
            self.error_occurred.emit(self.agent.role, str(e))

# ==============================================================================
# 7. 审计工作线程（CKO Vision Keeper）
# ==============================================================================

class AuditWorker(QThread):
    """审计工作线程 (CKO Vision Keeper)"""

    audit_finished = pyqtSignal(str)   # 审计结果 (PASS / FAIL: xxx)
    error_occurred = pyqtSignal(str, str)   # (角色, 错误消息)

    def __init__(self, cko_agent, stage, context, mission_protocol, parent=None):
        super().__init__(parent)
        self.cko = cko_agent
        self.stage = stage
        self.context = context
        self.protocol = mission_protocol
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled or self.isInterruptionRequested():
                print("[AuditWorker] 审计取消")
                return

            result = self.cko.audit_node(self.stage, self.context, self.protocol)

            if self._is_cancelled or self.isInterruptionRequested():
                print("[AuditWorker] 审计完成后取消，丢弃结果")
                return

            self.audit_finished.emit(result)

        except Exception as e:
            if self._is_cancelled or self.isInterruptionRequested():
                print("[AuditWorker] 异常期间取消")
                return
            self.error_occurred.emit("CKO", f"CKO 审计异常: {str(e)}")

    def cancel(self):
        """取消审计"""
        self._is_cancelled = True
        self.requestInterruption()  # 请求线程中断
        self.quit()  # 请求线程退出

# ==============================================================================
# 8. 主入口点适配（供main.py使用）
# ==============================================================================

if __name__ == "__main__":
    print("UnifiedOrchestrator 模块测试...")
    # 简单测试代码
    orchestrator = UnifiedOrchestrator()
    print(f"创建成功: {orchestrator}")