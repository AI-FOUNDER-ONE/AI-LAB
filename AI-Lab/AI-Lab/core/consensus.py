"""
core/consensus.py - 共识形成引擎
================================
从 unified_orchestrator 拆出：ConsensusEngine。
共识度计算：强/弱/负信号权重，归一化到 [0, 1]。
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from core.context import Message, MessageIntent, EnhancedConversationContext


# ---------- 共识信号权重（用于 calculate_consensus）----------
SIGNAL_STRONG = 1.0   # 强同意
SIGNAL_WEAK = 0.3     # 弱同意
SIGNAL_NEGATIVE = -1.0  # 反对

KEYWORDS_STRONG = ["批准", "approve", "通过", "agree", "lgtm"]
KEYWORDS_WEAK = ["可以", "ok", "不错", "reasonable"]
KEYWORDS_NEGATIVE = ["反对", "reject", "不同意", "disagree", "rework"]

# 参与共识计算的最大消息条数（取最近 N 条）
CONSENSUS_MESSAGE_LIMIT = 50


class ConsensusEngine:
    """共识形成引擎：支持投票、辩论总结、妥协方案与加权共识度计算"""

    def __init__(self, context: EnhancedConversationContext):
        self.context = context
        self.vote_records: Dict[str, Dict[str, str]] = {}  # 议题 -> {角色 -> 立场}
        self.debate_summaries: Dict[str, str] = {}  # 议题 -> 总结
        self._last_detail: Optional[Dict[str, Any]] = None  # 最近一次 get_consensus_detail 的缓存（由 calculate_consensus 更新）

    def _signal_weight_for_message(self, content: str) -> Tuple[float, List[str]]:
        """计算单条消息的最高信号权重及命中的关键词列表。返回 (weight, matched_keywords)。"""
        content_lower = content.lower().strip()
        found: List[tuple[float, str]] = []
        for kw in KEYWORDS_STRONG:
            if kw in content_lower:
                found.append((SIGNAL_STRONG, kw))
        for kw in KEYWORDS_WEAK:
            if kw in content_lower:
                found.append((SIGNAL_WEAK, kw))
        for kw in KEYWORDS_NEGATIVE:
            if kw in content_lower:
                found.append((SIGNAL_NEGATIVE, kw))
        if not found:
            return 0.0, []
        # 取最高权重（1.0 > 0.3 > 0 > -1.0）
        best = max(found, key=lambda x: x[0])
        return best[0], [k for w, k in found if w == best[0]]

    def calculate_consensus(self, messages: Optional[List[Message]] = None) -> float:
        """
        基于强/弱/负信号计算共识度。
        共识度 = 对参与消息的（每条消息最高信号权重）求和 / 消息数，再线性归一化到 [0, 1]。
        无消息或无有效消息时返回 0.0。
        """
        if messages is None:
            messages = getattr(self.context, "history", []) or []
        if not messages:
            self._last_detail = {"messages": [], "total_messages": 0, "raw_sum": 0.0, "consensus": 0.0}
            return 0.0
        recent = messages[-CONSENSUS_MESSAGE_LIMIT:] if len(messages) > CONSENSUS_MESSAGE_LIMIT else messages
        n = len(recent)
        detail_messages: List[Dict[str, Any]] = []
        raw_sum = 0.0
        for msg in recent:
            weight, signals = self._signal_weight_for_message(msg.content)
            raw_sum += weight
            detail_messages.append({
                "role": msg.role,
                "content_snippet": (msg.content[:80] + "…") if len(msg.content) > 80 else msg.content,
                "signals": signals,
                "score": weight,
            })
        # 归一化：raw 在 [-1, 1] 区间，映射到 [0, 1]：(raw + 1) / 2，再裁剪
        raw_mean = raw_sum / n
        consensus = max(0.0, min(1.0, (raw_mean + 1.0) / 2.0))
        self._last_detail = {
            "messages": detail_messages,
            "total_messages": n,
            "raw_sum": raw_sum,
            "raw_mean": raw_mean,
            "consensus": consensus,
        }
        return consensus

    def get_consensus_detail(self) -> Dict[str, Any]:
        """
        返回最近一次共识计算的明细（每条消息的信号与得分），用于调试与可解释性。
        若尚未调用过 calculate_consensus，会先基于 context.history 计算一次。
        """
        if self._last_detail is None:
            self.calculate_consensus()
        return dict(self._last_detail or {})

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
