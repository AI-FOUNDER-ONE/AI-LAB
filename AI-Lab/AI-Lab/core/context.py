"""
core/context.py - 增强对话上下文与消息模型
============================================
从 unified_orchestrator 拆出：MessageIntent、Message、EnhancedConversationContext。
"""

import re
import time
from enum import Enum
from typing import Optional, List, Dict, Any


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
        """更新共识度：委托给 ConsensusEngine（若已注入），否则置为 0.0"""
        engine = getattr(self, "consensus_engine", None)
        if engine is not None:
            self.consensus_level = engine.calculate_consensus()
        else:
            self.consensus_level = 0.0
