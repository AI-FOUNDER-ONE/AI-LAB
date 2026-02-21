"""
commander_crew.py - CommanderCrew 增强型多 Agent 辩论引擎
=========================================================

合并 CrewAI 任务执行和事件驱动 War Room 辩论模拟。

核心架构：
  1. WarRoomContext:  增强消息总线 (意图检测、共识跟踪、立场追踪)
  2. DebateRouter:    智能路由器 (阶段路由、冲突检测、@提及优先)
  3. CommanderCrew:   主编排器 (多轮辩论、子辩论、用户干预)

工作流:
  Phase 1: CKO Grounding (需求访谈)
  Phase 2: Debate Loop (PM主持 → Arch/Designer 博弈 → 共识检查)
  Phase 3: Production (Coder 编码 + Tester 反馈循环)
  Phase 4: PM Final Review (最终审批)
"""

import os
import re
import sys
import queue
import random
import threading
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

from crewai import Crew, Process, Task, Agent
from config import API_KEYS, AppState

# ============================================================
#  环境设置 — 在导入 crew_agents 之前配置
# ============================================================
os.environ["OPENAI_API_KEY"] = API_KEYS.get("hiapi", "")
os.environ["OPENAI_API_BASE"] = "https://hiapi.online/v1"

from agents.crew_agents import (
    cko_agent, pm_agent, arch_agent,
    designer_agent, coder_agent, tester_agent
)
from core.crew_tasks import grounding_task

# Windows UTF-8 编码修复
if sys.platform == "win32":
    try:
        import codecs
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
            sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except Exception:
        pass

# ============================================================
#  配置常量 — 辩论引擎参数
# ============================================================
DEBATE_MAX_ROUNDS = 5       # 最大辩论轮次
DEBATE_MIN_ROUNDS = 2       # 最少辩论轮次（保证充分讨论）
CONSENSUS_THRESHOLD = 0.7   # 共识阈值 (70% Agent 同意即通过)
PRODUCTION_MAX_LOOPS = 3    # 生产-测试最大循环次数
THINKING_DELAY_MS = 300     # 模拟思考延迟 (毫秒)

# 冲突检测关键词 — 检测 Agent 之间的分歧
CONFLICT_KEYWORDS_CN = [
    "反对", "不同意", "不行", "有问题", "质疑", "担心",
    "但是", "然而", "存在风险", "不可行", "重新考虑",
    "不够", "缺陷", "漏洞", "我认为不",
]
CONFLICT_KEYWORDS_EN = [
    "disagree", "however", "but", "issue", "problem",
    "concern", "risk", "alternative", "instead",
]

# 同意检测关键词
AGREEMENT_KEYWORDS = [
    "同意", "赞成", "认可", "支持", "没问题", "可以",
    "LGTM", "agree", "approved", "好的方案", "我同意",
    "通过", "确认", "接受",
]


# ==============================================================================
#  1. WarRoomMessage — 增强消息数据类
# ==============================================================================

@dataclass
class WarRoomMessage:
    """War Room 中的一条消息，包含元数据用于辩论分析。
    
    Attributes:
        role: 发言者角色 (CKO/PM/Arch/Designer/Coder/Tester/Commander/System)
        content: 消息内容
        intent: 意图分类 (statement/question/critique/agreement/dissent/command)
        mentions: @提及的角色列表
        sentiment: 情感倾向 (positive/negative/neutral)
        round_num: 所属辩论轮次
        timestamp: 逻辑时间戳
    """
    role: str
    content: str
    intent: str = "statement"
    mentions: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    round_num: int = 0
    timestamp: int = 0

    def __post_init__(self):
        """自动检测意图、情感和 @提及。"""
        # @提及检测
        self.mentions = re.findall(r"@(\w+)", self.content)
        
        # 意图检测 — 基于关键词的简单分类
        content_lower = self.content.lower()
        if self.role == "Commander":
            self.intent = "command"
        elif any(kw in self.content for kw in CONFLICT_KEYWORDS_CN):
            self.intent = "critique"
            self.sentiment = "negative"
        elif any(kw in content_lower for kw in CONFLICT_KEYWORDS_EN):
            self.intent = "critique"
            self.sentiment = "negative"
        elif any(kw in self.content for kw in AGREEMENT_KEYWORDS):
            self.intent = "agreement"
            self.sentiment = "positive"
        elif "?" in self.content or "？" in self.content:
            self.intent = "question"
        else:
            self.intent = "statement"
            self.sentiment = "neutral"


# ==============================================================================
#  2. WarRoomContext — 增强消息总线 & 共识追踪
# ==============================================================================

class WarRoomContext:
    """War Room 会话上下文管理器。
    
    管理完整的辩论历史、Agent 立场追踪、共识判断。
    """
    
    def __init__(self):
        self.history: List[WarRoomMessage] = []
        self.artifacts: Dict[str, Any] = {}          # 共享文档/代码
        self.mission_protocol: Dict[str, Any] = {}   # 结构化任务协议
        self.task_type: str = "SOFTWARE"              # 任务类型

        # 共识追踪 — 记录每个 Agent 对当前方案的立场
        # "agree" / "disagree" / "neutral" / "conditional"
        self.consensus_tracker: Dict[str, str] = {
            "PM": "neutral", "Arch": "neutral", "Designer": "neutral",
            "Coder": "neutral", "Tester": "neutral",
        }
        
        # 冲突记录
        self.active_conflicts: List[Dict[str, Any]] = []
        
    def add_message(self, role: str, content: str, round_num: int = 0) -> WarRoomMessage:
        """添加消息并自动分析意图和情感。"""
        msg = WarRoomMessage(
            role=role, content=content, round_num=round_num,
            timestamp=len(self.history) + 1
        )
        self.history.append(msg)
        
        # 自动更新共识追踪
        if role in self.consensus_tracker:
            if msg.intent == "agreement":
                self.consensus_tracker[role] = "agree"
            elif msg.intent == "critique":
                self.consensus_tracker[role] = "disagree"
        
        return msg
        
    def get_recent_history(self, limit: int = 8) -> str:
        """格式化最近消息供 LLM 上下文注入。"""
        lines = []
        for msg in self.history[-limit:]:
            # 包含意图标签，帮助 LLM 理解对话氛围
            intent_tag = f"[{msg.intent}]" if msg.intent != "statement" else ""
            lines.append(f"**{msg.role}** {intent_tag}: {msg.content}")
        return "\n\n".join(lines)
    
    def get_debate_summary(self) -> str:
        """生成辩论摘要：谁同意、谁反对、核心分歧是什么。"""
        agrees = [r for r, s in self.consensus_tracker.items() if s == "agree"]
        disagrees = [r for r, s in self.consensus_tracker.items() if s == "disagree"]
        neutrals = [r for r, s in self.consensus_tracker.items() if s == "neutral"]
        
        summary = "## 当前辩论态势\n"
        if agrees:
            summary += f"- ✅ 同意方: {', '.join(agrees)}\n"
        if disagrees:
            summary += f"- ❌ 反对方: {', '.join(disagrees)}\n"
        if neutrals:
            summary += f"- ⏳ 中立方: {', '.join(neutrals)}\n"
        
        # 核心分歧
        if self.active_conflicts:
            summary += "\n### 活跃分歧:\n"
            for conflict in self.active_conflicts[-3:]:  # 最近3个
                summary += f"- {conflict.get('description', '未指定')}\n"
        
        return summary
    
    def check_consensus(self) -> bool:
        """检查是否达成共识（超过阈值的 Agent 同意）。"""
        total = len(self.consensus_tracker)
        agrees = sum(1 for s in self.consensus_tracker.values() if s == "agree")
        ratio = agrees / total if total > 0 else 0
        return ratio >= CONSENSUS_THRESHOLD
    
    def get_last_message(self) -> Optional[WarRoomMessage]:
        return self.history[-1] if self.history else None
    
    def reset(self):
        """重置上下文，准备新一轮任务。"""
        self.history.clear()
        self.artifacts.clear()
        self.mission_protocol.clear()
        self.task_type = "SOFTWARE"
        for role in self.consensus_tracker:
            self.consensus_tracker[role] = "neutral"
        self.active_conflicts.clear()


# ==============================================================================
#  3. DebateRouter — 智能路由器
# ==============================================================================

class DebateRouter:
    """辩论路由器 — 决定谁是下一个发言人，检测冲突。
    
    路由优先级:
      1. @提及 — 被点名的 Agent 最优先
      2. 用户干预 — Commander 消息后由 PM 响应
      3. 阶段特定路由 — 根据 task_type 决定辩论顺序
      4. 冲突触发 — 检测到分歧时安排反对方发言
    """
    
    ALL_ROLES = ["CKO", "PM", "Arch", "Designer", "Coder", "Tester"]
    
    def __init__(self, ctx: WarRoomContext):
        self.ctx = ctx
    
    def get_debate_order(self, round_num: int) -> List[str]:
        """根据任务类型和轮次返回辩论发言顺序。
        
        Returns:
            发言角色列表（不含 PM，PM 单独在轮次开始/结束时调用）
        """
        task_type = self.ctx.task_type
        
        if task_type == "RESEARCH":
            # 研究型: CKO(方法论) → Arch(技术可行性) → Designer(实证分析) 
            base_order = ["CKO", "Arch", "Designer"]
        elif task_type == "DESIGN":
            # 设计型: Designer(主导) → Arch(技术约束) → CKO(需求对齐)
            base_order = ["Designer", "Arch", "CKO"]
        elif task_type == "ENGINEERING":
            # 工程型: Arch(主导) → Designer(落地) → Coder(可行性)
            base_order = ["Arch", "Designer", "Coder"]
        else:
            # 软件型 (默认): Arch(架构) → Designer(详设) → Coder(可行性)
            base_order = ["Arch", "Designer", "Coder"]
        
        # 后续轮次可以微调顺序，增加随机性
        if round_num > 2:
            # 让反对者先说，增加辩论深度
            disagrees = [r for r in base_order 
                         if self.ctx.consensus_tracker.get(r) == "disagree"]
            others = [r for r in base_order if r not in disagrees]
            base_order = disagrees + others
        
        return base_order
    
    def get_production_order(self) -> List[str]:
        """生产阶段发言顺序。"""
        return ["Coder", "Tester"]
    
    def detect_conflict(self) -> bool:
        """检测最近消息中是否存在冲突。"""
        recent = self.ctx.history[-3:] if len(self.ctx.history) >= 3 else self.ctx.history
        
        for msg in recent:
            if msg.intent == "critique" and msg.sentiment == "negative":
                # 记录冲突
                conflict = {
                    "instigator": msg.role,
                    "description": f"{msg.role} 对当前方案提出质疑",
                    "content_preview": msg.content[:100],
                }
                # 避免重复记录
                if not any(c["instigator"] == msg.role for c in self.ctx.active_conflicts):
                    self.ctx.active_conflicts.append(conflict)
                return True
        return False
    
    def should_trigger_sub_debate(self) -> bool:
        """是否应触发子辩论（严重冲突）。"""
        # 如果有2个以上 Agent 反对，触发子辩论
        disagrees = sum(1 for s in self.ctx.consensus_tracker.values() if s == "disagree")
        return disagrees >= 2
    
    def get_response_to_mention(self, mentions: List[str]) -> Optional[str]:
        """解析 @提及，返回应该回应的角色。"""
        for mention in mentions:
            for role in self.ALL_ROLES:
                if role.lower() == mention.lower():
                    return role
        return None


# ==============================================================================
#  4. StreamRedirector — stdout 重定向 (复用已有逻辑)
# ==============================================================================

class StreamRedirector:
    """将 stdout 重定向到回调函数，同时保持终端输出。"""
    
    def __init__(self, callback, original_stream=None):
        self.callback = callback
        self.original_stream = original_stream
        self.buffer = ""

    def write(self, s):
        if self.original_stream:
            try:
                self.original_stream.write(s)
                self.original_stream.flush()
            except Exception:
                pass
        
        # 子线程的输出才发送到回调
        if threading.current_thread() is threading.main_thread():
            return len(s)

        self.buffer += s
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            for line in lines[:-1]:
                self.callback(line)
            self.buffer = lines[-1]
        return len(s)
    
    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass

    @property
    def encoding(self):
        return getattr(self.original_stream, 'encoding', 'utf-8')


# ==============================================================================
#  5. DebateWorker — 辩论工作线程
# ==============================================================================

class DebateWorker(QThread):
    """在后台线程中运行单个 Agent 的 CrewAI 任务调用。
    
    Signals:
        agent_responded: (role, content) — Agent 完成回复
        round_completed: (round_num,) — 一轮辩论结束
        debate_finished: (summary,) — 整个辩论阶段结束
        error_occurred: (error_msg,) — 错误
        thought_stream: (text,) — 中间思考流（供调试）
    """
    agent_responded = pyqtSignal(str, str)    # role, content
    round_completed = pyqtSignal(int)         # round_num
    debate_finished = pyqtSignal(str)         # summary
    production_finished = pyqtSignal(str)     # result
    error_occurred = pyqtSignal(str)          # error
    thought_stream = pyqtSignal(str)          # raw output

    def __init__(self, mode: str, ctx: WarRoomContext, router: DebateRouter,
                 user_input: str = "", parent=None):
        """
        Args:
            mode: "grounding" / "debate" / "production" / "review"
            ctx: 共享的 War Room 上下文
            router: 辩论路由器
            user_input: 用户的原始输入
        """
        super().__init__(parent)
        self.mode = mode
        self.ctx = ctx
        self.router = router
        self.user_input = user_input
        self._stop_flag = False
        
    def stop(self):
        """请求停止辩论。"""
        self._stop_flag = True

    def run(self):
        """线程主逻辑 — 根据模式执行不同的辩论流程。"""
        # 重定向 stdout 以捕获 CrewAI 输出
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        redirector = StreamRedirector(self.thought_stream.emit, original_stdout)
        sys.stdout = redirector
        sys.stderr = redirector
        
        try:
            if self.mode == "grounding":
                self._run_grounding()
            elif self.mode == "debate":
                self._run_debate()
            elif self.mode == "production":
                self._run_production()
            elif self.mode == "review":
                self._run_review()
        except Exception as e:
            import traceback
            self.error_occurred.emit(f"[ERROR] {self.mode}: {e}\n{traceback.format_exc()}")
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    # ------------------------------------------------------------------
    #  Phase 1: CKO Grounding (需求访谈)
    # ------------------------------------------------------------------
    def _run_grounding(self):
        """CKO 需求分析 — 使用 CrewAI 单任务执行。"""
        grounding_task.description = (
            f"用户输入: {self.user_input}\n\n"
            f"【任务指令】作为 CKO（首席知识官），请对用户输入进行需求分析：\n"
            f"1. 如果用户输入仅为简短问候或模糊描述，你必须：\n"
            f"   - 先礼貌回应\n"
            f"   - 然后提出 3-5 个编号的结构化追问，覆盖以下维度：\n"
            f"     a) 项目类型（软件/研究/设计/工程）\n"
            f"     b) 核心功能和目标\n"
            f"     c) 技术栈偏好\n"
            f"     d) 目标用户群体\n"
            f"     e) 时间和规模要求\n"
            f"   - 明确告知用户需要回答这些问题后才能生成任务协议\n"
            f"2. 如果用户已提供具体需求，请直接生成结构化任务协议\n"
            f"3. 输出必须使用简体中文\n"
            f"4. 先写自然语言摘要，再用编号列表提问"
        )
        
        crew = Crew(
            agents=[cko_agent],
            tasks=[grounding_task],
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        self.debate_finished.emit(str(result))
    
    # ------------------------------------------------------------------
    #  Phase 2: Debate Loop (多轮方案博弈)
    # ------------------------------------------------------------------
    def _run_debate(self):
        """多轮辩论 — PM 主持，Arch/Designer 博弈，共识检查。"""
        print(f"\n{'='*60}")
        print(f"[DEBATE] 辩论阶段启动 | 最大轮次: {DEBATE_MAX_ROUNDS}")
        print(f"{'='*60}\n")
        
        for round_num in range(1, DEBATE_MAX_ROUNDS + 1):
            if self._stop_flag:
                break
                
            print(f"\n[DEBATE] ===== 第 {round_num} 轮辩论开始 =====\n")
            self.round_completed.emit(round_num)
            
            # ---- PM 主持本轮 ----
            pm_prompt = self._build_debate_prompt("PM", round_num, is_moderator=True)
            pm_response = self._execute_single_agent(pm_agent, pm_prompt)
            if pm_response:
                self.ctx.add_message("PM", pm_response, round_num)
                self.agent_responded.emit("PM", pm_response)
            
            if self._stop_flag:
                break
            
            # ---- 路由器决定本轮发言顺序 ----
            speakers = self.router.get_debate_order(round_num)
            
            for speaker_role in speakers:
                if self._stop_flag:
                    break
                
                # 模拟思考延迟 — 增加真实感
                time.sleep(THINKING_DELAY_MS / 1000.0)
                
                agent = self._get_agent_by_role(speaker_role)
                if not agent:
                    continue
                
                # 构建含上下文的辩论提示
                prompt = self._build_debate_prompt(speaker_role, round_num)
                response = self._execute_single_agent(agent, prompt)
                
                if not response:
                    continue
                
                # 记录到上下文并通知 UI
                msg = self.ctx.add_message(speaker_role, response, round_num)
                self.agent_responded.emit(speaker_role, response)
                
                # ---- @提及处理：被提及的 Agent 立即回应 ----
                if msg.mentions:
                    for mentioned_role in msg.mentions:
                        target = self.router.get_response_to_mention([mentioned_role])
                        if target and target != speaker_role:
                            print(f"[DEBATE] {speaker_role} @提及 {target}，触发即时回应")
                            time.sleep(THINKING_DELAY_MS / 1000.0)
                            
                            reply_agent = self._get_agent_by_role(target)
                            if reply_agent:
                                reply_prompt = self._build_mention_response_prompt(
                                    target, speaker_role, response, round_num
                                )
                                reply = self._execute_single_agent(reply_agent, reply_prompt)
                                if reply:
                                    self.ctx.add_message(target, reply, round_num)
                                    self.agent_responded.emit(target, reply)
                
                # ---- 冲突检测 ----
                if self.router.detect_conflict():
                    print(f"[DEBATE] ⚠️ 检测到冲突！考虑是否触发子辩论...")
                    if self.router.should_trigger_sub_debate():
                        self._run_sub_debate(round_num)
            
            # ---- 共识检查 ----
            if round_num >= DEBATE_MIN_ROUNDS and self.ctx.check_consensus():
                print(f"\n[DEBATE] ✅ 共识达成！在第 {round_num} 轮结束辩论。")
                break
            else:
                consensus_status = {k: v for k, v in self.ctx.consensus_tracker.items()}
                print(f"[DEBATE] 共识状态: {consensus_status}")
        
        # ---- PM 最终裁决 ----
        final_prompt = self._build_final_decision_prompt()
        final_response = self._execute_single_agent(pm_agent, final_prompt)
        if final_response:
            self.ctx.add_message("PM", final_response)
            self.agent_responded.emit("PM", final_response)
        
        summary = self.ctx.get_debate_summary()
        self.debate_finished.emit(summary)
    
    # ------------------------------------------------------------------
    #  Phase 3: Production (编码 + 测试循环)
    # ------------------------------------------------------------------
    def _run_production(self):
        """Coder 编码 + Tester 验证循环。"""
        print(f"\n[PRODUCTION] 生产阶段启动 | 最大循环: {PRODUCTION_MAX_LOOPS}\n")
        
        for loop in range(1, PRODUCTION_MAX_LOOPS + 1):
            if self._stop_flag:
                break
                
            print(f"\n[PRODUCTION] --- 循环 {loop}/{PRODUCTION_MAX_LOOPS} ---\n")
            
            # ---- Coder 编码 ----
            coder_prompt = self._build_production_prompt("Coder", loop)
            coder_response = self._execute_single_agent(coder_agent, coder_prompt)
            if coder_response:
                self.ctx.add_message("Coder", coder_response)
                self.agent_responded.emit("Coder", coder_response)
            
            if self._stop_flag:
                break
            
            time.sleep(THINKING_DELAY_MS / 1000.0)
            
            # ---- Tester 验证 ----
            tester_prompt = self._build_production_prompt("Tester", loop)
            tester_response = self._execute_single_agent(tester_agent, tester_prompt)
            if tester_response:
                msg = self.ctx.add_message("Tester", tester_response)
                self.agent_responded.emit("Tester", tester_response)
                
                # 如果 Tester 通过，跳出循环
                if msg.sentiment == "positive" or "通过" in tester_response:
                    print(f"[PRODUCTION] ✅ Tester 通过! 跳出循环。")
                    break
                else:
                    print(f"[PRODUCTION] ❌ Tester 发现问题, Coder 需要修复...")
        
        self.production_finished.emit("生产阶段完成")
    
    # ------------------------------------------------------------------
    #  Phase 4: PM Final Review (最终审批)
    # ------------------------------------------------------------------
    def _run_review(self):
        """PM 最终审批。"""
        review_prompt = self._build_review_prompt()
        response = self._execute_single_agent(pm_agent, review_prompt)
        if response:
            self.ctx.add_message("PM", response)
            self.agent_responded.emit("PM", response)
        self.debate_finished.emit("最终审批完成")
    
    # ------------------------------------------------------------------
    #  子辩论 — 冲突解决
    # ------------------------------------------------------------------
    def _run_sub_debate(self, parent_round: int):
        """针对特定冲突进行子辩论（最多 2 轮）。"""
        print(f"\n[SUB-DEBATE] 🔥 子辩论启动 (冲突解决)\n")
        
        # 找出所有反对者
        disagrees = [r for r, s in self.ctx.consensus_tracker.items() if s == "disagree"]
        
        if not disagrees:
            return
        
        # 让反对者详细阐述 → PM 调停
        for dissenter in disagrees[:2]:  # 最多处理2个反对者
            if self._stop_flag:
                break
            agent = self._get_agent_by_role(dissenter)
            if not agent:
                continue
            
            prompt = (
                f"你是 {dissenter}，你之前对方案提出了质疑。\n"
                f"现在请详细阐述你的反对理由，并给出你认为更好的替代方案。\n"
                f"请具体、有建设性、用数据或案例支撑你的观点。\n\n"
                f"## 当前讨论上下文\n{self.ctx.get_recent_history(limit=5)}\n\n"
                f"请用简体中文回应："
            )
            response = self._execute_single_agent(agent, prompt)
            if response:
                self.ctx.add_message(dissenter, response, parent_round)
                self.agent_responded.emit(dissenter, response)
        
        # PM 调停裁决
        mediator_prompt = (
            f"你是 PM（项目经理），团队中出现了分歧。\n"
            f"请综合各方意见，给出一个各方都能接受的折中方案。\n"
            f"如果某一方的观点确实更优，也可以采纳并说明理由。\n\n"
            f"## 当前讨论上下文\n{self.ctx.get_recent_history(limit=8)}\n\n"
            f"请用简体中文做出裁决："
        )
        mediator_response = self._execute_single_agent(pm_agent, mediator_prompt)
        if mediator_response:
            self.ctx.add_message("PM", mediator_response, parent_round)
            self.agent_responded.emit("PM", mediator_response)
        
        print(f"[SUB-DEBATE] 子辩论结束\n")
    
    # ------------------------------------------------------------------
    #  Agent 调用 — 使用 CrewAI Task 单次执行
    # ------------------------------------------------------------------
    def _execute_single_agent(self, agent: Agent, prompt: str) -> Optional[str]:
        """使用 CrewAI 执行单个 Agent 任务。
        
        通过创建临时 Task 和单 Agent Crew 来执行，
        这样可以利用 CrewAI 的工具调用和内存功能。
        """
        try:
            # 创建临时任务
            temp_task = Task(
                description=prompt,
                expected_output="简体中文的详细回复",
                agent=agent
            )
            
            # 单 Agent Crew 执行
            mini_crew = Crew(
                agents=[agent],
                tasks=[temp_task],
                process=Process.sequential,
                verbose=True
            )
            
            result = mini_crew.kickoff()
            response = str(result).strip()
            
            # 过滤 CrewAI 元数据噪声
            response = self._clean_response(response)
            
            return response if response and len(response) > 3 else None
            
        except Exception as e:
            print(f"[ERROR] Agent {agent.role} 执行失败: {e}")
            return None
    
    def _clean_response(self, text: str) -> str:
        """清理 CrewAI 输出中的元数据噪声。"""
        # 移除常见的 CrewAI 元数据标签
        noise_patterns = [
            r'^Agent:.*$', r'^Task Completed.*$', r'^Name:.*$',
            r'^User Request:.*$', r'^Final Answer:?\s*',
        ]
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            if any(re.match(p, line.strip(), re.IGNORECASE) for p in noise_patterns):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned).strip()
    
    # ------------------------------------------------------------------
    #  提示词构建 — 动态上下文注入
    # ------------------------------------------------------------------
    def _build_debate_prompt(self, role: str, round_num: int, 
                             is_moderator: bool = False) -> str:
        """构建辩论阶段的动态提示词。"""
        debate_summary = self.ctx.get_debate_summary()
        recent_history = self.ctx.get_recent_history(limit=6)
        
        if is_moderator:
            return (
                f"你是 PM（项目经理），正在主持第 {round_num} 轮方案讨论。\n\n"
                f"{debate_summary}\n\n"
                f"## 最近讨论\n{recent_history}\n\n"
                f"## 你的任务\n"
                f"{'- 这是第一轮，请基于任务协议提出初始方案框架，然后邀请 Arch 和 Designer 发表意见。' if round_num == 1 else '- 总结上一轮讨论的进展和分歧，引导团队聚焦核心问题。'}\n"
                f"- 如果发现团队即将达成共识，明确说 '我同意现有方案' 或 '方案通过'\n"
                f"- 如果有未解决的分歧，指出具体问题并 @相关角色\n"
                f"- 使用简体中文，先自然语言摘要，技术细节用 ## 标题"
            )
        else:
            return (
                f"你是 {role}，正在 War Room 中参与第 {round_num} 轮方案辩论。\n\n"
                f"{debate_summary}\n\n"
                f"## 最近讨论\n{recent_history}\n\n"
                f"## 你的任务\n"
                f"- 回应上一位发言者的观点\n"
                f"- 如果你同意，明确表示 '我同意...' 并补充你的专业视角\n"
                f"- 如果你反对，用 '@角色名' 指出分歧并提出替代方案\n"
                f"- 如果你需要其他角色的信息，用 '@角色名' 点名提问\n"
                f"- 输出使用简体中文，先自然语言回应，技术细节用 ## 标题\n"
                f"- 控制在 300 字以内（除非有重要技术分析）"
            )
    
    def _build_mention_response_prompt(self, responder: str, mentioner: str,
                                       mention_content: str, round_num: int) -> str:
        """被 @提及时的回应提示词。"""
        return (
            f"你是 {responder}。{mentioner} 在讨论中 @提及了你并说：\n"
            f"「{mention_content[:300]}」\n\n"
            f"## 最近讨论上下文\n{self.ctx.get_recent_history(limit=4)}\n\n"
            f"请直接回应 {mentioner} 的观点或问题。\n"
            f"- 如果同意，说 '我同意 @{mentioner} 的观点...' 并补充你的视角\n"
            f"- 如果反对，明确说明理由并给出替代方案\n"
            f"- 简体中文，控制在 200 字以内"
        )
    
    def _build_final_decision_prompt(self) -> str:
        """PM 最终裁决提示词。"""
        return (
            f"你是 PM（项目经理），辩论阶段即将结束。\n\n"
            f"{self.ctx.get_debate_summary()}\n\n"
            f"## 完整讨论回顾\n{self.ctx.get_recent_history(limit=15)}\n\n"
            f"## 你的任务\n"
            f"- 综合所有人的意见，做出最终方案决定\n"
            f"- 明确列出最终采纳的方案要点\n"
            f"- 说明为什么采纳/拒绝某些观点\n"
            f"- 以 '方案通过：...' 开头，明确表示你的裁决\n"
            f"- 简体中文输出"
        )
    
    def _build_production_prompt(self, role: str, loop: int) -> str:
        """生产阶段提示词。"""
        recent = self.ctx.get_recent_history(limit=6)
        
        if role == "Coder":
            extra = (
                f"{'请根据最终方案编写代码。' if loop == 1 else '请根据 Tester 的反馈修复代码。'}\n"
                f"- 遵循 Google 编程规范\n"
                f"- 代码中必须包含详尽的中文注释\n"
                f"- 使用 ```python 代码块 ```"
            )
        else:  # Tester
            extra = (
                f"请验证 Coder 产出的代码/方案。\n"
                f"- 检查逻辑正确性、错误处理、规范性\n"
                f"- 如果通过，说 '测试通过 ✅'\n"
                f"- 如果不通过，说明具体问题和建议修复方案"
            )
        
        return (
            f"你是 {role}，当前处于生产阶段第 {loop} 轮。\n\n"
            f"## 讨论上下文\n{recent}\n\n"
            f"## 任务\n{extra}\n"
            f"- 简体中文输出"
        )
    
    def _build_review_prompt(self) -> str:
        """PM 最终审批提示词。"""
        return (
            f"你是 PM（项目经理），请对整个项目进行最终审批。\n\n"
            f"## 项目完整回顾\n{self.ctx.get_recent_history(limit=20)}\n\n"
            f"## 任务\n"
            f"- 审查所有阶段的产出\n"
            f"- 判断是否满足原始需求\n"
            f"- 给出最终审批意见\n"
            f"- 简体中文输出"
        )
    
    def _get_agent_by_role(self, role: str) -> Optional[Agent]:
        """根据角色名获取 CrewAI Agent 实例。"""
        agent_map = {
            "CKO": cko_agent, "PM": pm_agent, "Arch": arch_agent,
            "Designer": designer_agent, "Coder": coder_agent, "Tester": tester_agent,
        }
        return agent_map.get(role)


# ==============================================================================
#  6. ProxyAgent — UI 兼容代理
# ==============================================================================

class ProxyAgent(QObject):
    """为 UI 信号绑定提供的代理对象，模拟旧版 Agent 接口。"""
    typing_started = pyqtSignal()
    typing_finished = pyqtSignal()
    response_ready = pyqtSignal(str)
    state_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)


# ==============================================================================
#  7. CommanderCrew — 主编排器
# ==============================================================================

class CommanderCrew(QObject):
    """CommanderCrew: 增强型多 Agent 辩论引擎。
    
    合并了 CrewManager (CrewAI 执行) 和 OrchestratorDynamic (事件驱动辩论) 的功能。
    
    信号接口与 CrewManager 完全兼容，main.py 只需换 import 即可使用。
    
    Signals:
        agent_response: (role, content) — Agent 回复，分发到 UI
        state_changed: (state_id, description) — 状态变更
        debate_round_info: (current_round, max_rounds) — 辩论轮次进度
        workflow_completed: () — 整个工作流结束
        error_occurred: (error_msg) — 错误
    """
    
    # ---- 与 CrewManager 兼容的信号 ----
    agent_response = pyqtSignal(str, str)      # role, content
    state_changed = pyqtSignal(str, str)        # state_id, description
    debate_round_info = pyqtSignal(int, int)    # current, max
    workflow_completed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # ---- ProxyAgent 代理 (UI 兼容) ----
        self.cko = ProxyAgent()
        self.pm = ProxyAgent()
        self.arch = ProxyAgent()
        self.designer = ProxyAgent()
        self.coder = ProxyAgent()
        self.tester = ProxyAgent()
        
        # ---- 状态控制器 (模拟) ----
        self.state_ctrl = type('obj', (object,), {
            'current_state': "IDLE",
            'state_description': "CommanderCrew 就绪"
        })
        
        # ---- 核心组件 ----
        self.ctx = WarRoomContext()
        self.router = DebateRouter(self.ctx)
        
        # ---- 工作线程 ----
        self._worker: Optional[DebateWorker] = None
        self._last_user_input = ""
        
        # ---- 块级累积 (兼容 _on_thought_stream) ----
        self._answer_buffer: List[str] = []
        self._current_role = "System"
        self._in_answer_block = False
        self._seen_messages: set = set()
        
    # ==================================================================
    #  Public API — 与 CrewManager 兼容
    # ==================================================================
    
    def start_mission(self, user_input: str):
        """Phase 1: CKO 需求分析/立项。
        
        用户发送消息后，仅 CKO 响应。其他 Agent 等待确认后启动。
        """
        print(f"\n[COMMANDER] Phase 1 (CKO Grounding) | input: {user_input[:50]}...")
        
        self._reset_state()
        self._last_user_input = user_input
        self.ctx.add_message("Commander", user_input)
        
        self._worker = DebateWorker("grounding", self.ctx, self.router, user_input)
        self._worker.thought_stream.connect(self._on_thought_stream)
        self._worker.debate_finished.connect(self._on_grounding_complete)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.start()
        
        self.state_changed.emit("GROUNDING", "CKO 正在分析需求...")
    
    def confirm_project(self):
        """Phase 2: 用户确认后启动辩论。"""
        print(f"\n[COMMANDER] Phase 2 (Debate) triggered by Confirm button.")
        
        self._reset_stream_state()
        
        self._worker = DebateWorker("debate", self.ctx, self.router, self._last_user_input)
        self._worker.agent_responded.connect(self._on_agent_responded)
        self._worker.round_completed.connect(self._on_round_completed)
        self._worker.debate_finished.connect(self._on_debate_complete)
        self._worker.thought_stream.connect(self._on_thought_stream)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.start()
        
        self.agent_response.emit("System", "🚀 项目已确认！进入**方案辩论**阶段。PM 将主持讨论...")
        self.state_changed.emit("DEBATE", "方案博弈中 — PM 主持讨论...")
    
    def handle_user_intervention(self, message: str):
        """用户在 War Room 中发送干预消息 — 最高优先级。"""
        print(f"[COMMANDER] 用户干预: {message[:50]}...")
        
        # 记录到上下文
        self.ctx.add_message("Commander", message)
        
        # 广播到 UI
        self.agent_response.emit("Commander", message)
    
    def stop_all(self):
        """停止当前所有工作。"""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        
    # ==================================================================
    #  信号处理 — 内部回调
    # ==================================================================
    
    def _on_grounding_complete(self, result: str):
        """Phase 1 完成：CKO 已回复。"""
        self._flush_buffer()
        self.agent_response.emit(
            "System", 
            "📋 CKO 需求分析已完成。请点击右上角 **Confirm Project** 按钮确认立项，启动后续辩论流程。"
        )
        self.state_changed.emit("AWAITING_CONFIRM", "等待用户确认立项...")
    
    def _on_agent_responded(self, role: str, content: str):
        """单个 Agent 回复完成 — 直接发射到 UI。"""
        # 内容级过滤（防止 CrewAI 元数据泄漏）
        stripped = re.sub(r'[✅❌🤖🚀📋⚡💬🧠■□▪▫●○◆◇\s]', '', content).strip()
        noise_words = {"Agent", "AgentStarted", "AgentCompleted", "TaskCompleted",
                       "PASS", "FAIL", "FinalAnswer", "WorkingAgent"}
        if stripped in noise_words or not stripped or len(content.strip()) < 3:
            return
        
        # 去重
        content_hash = hash(content)
        if content_hash in self._seen_messages:
            return
        self._seen_messages.add(content_hash)
        
        self.agent_response.emit(role, content)
    
    def _on_round_completed(self, round_num: int):
        """辩论轮次完成。"""
        self.debate_round_info.emit(round_num, DEBATE_MAX_ROUNDS)
        self.state_changed.emit("DEBATE", f"辩论第 {round_num} 轮完成")
    
    def _on_debate_complete(self, summary: str):
        """辩论阶段完成 — 进入生产阶段。"""
        self._flush_buffer()
        self.agent_response.emit("System", f"✅ 方案辩论结束。进入**生产阶段**...")
        
        # 自动启动 Phase 3: Production
        self._start_production()
    
    def _start_production(self):
        """启动 Phase 3: Production。"""
        self._reset_stream_state()
        
        self._worker = DebateWorker("production", self.ctx, self.router, self._last_user_input)
        self._worker.agent_responded.connect(self._on_agent_responded)
        self._worker.production_finished.connect(self._on_production_complete)
        self._worker.thought_stream.connect(self._on_thought_stream)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.start()
        
        self.state_changed.emit("PRODUCTION", "Coder 正在编码...")
    
    def _on_production_complete(self, result: str):
        """生产阶段完成 — 检查验证结果决定下一步。
        
        闭环逻辑:
          - Tester 通过 → PM 最终审批
          - Tester 反对 → 回退到 DEBATE 阶段重新讨论（最多 2 次）
        """
        self._flush_buffer()
        
        # 检查 Tester 最终立场
        tester_stance = self.ctx.consensus_tracker.get("Tester", "neutral")
        rework_count = getattr(self, '_rework_count', 0)
        
        if tester_stance == "disagree" and rework_count < 2:
            # ---- 验证失败：回退到 DEBATE 阶段 ----
            self._rework_count = rework_count + 1
            self.agent_response.emit(
                "System", 
                f"❌ 验证未通过（第 {self._rework_count} 次回退）！"
                f"回退到**方案博弈**阶段修正..."
            )
            
            self._reset_stream_state()
            self._worker = DebateWorker(
                "debate", self.ctx, self.router, self._last_user_input
            )
            self._worker.agent_responded.connect(self._on_agent_responded)
            self._worker.round_completed.connect(self._on_round_completed)
            self._worker.debate_finished.connect(self._on_debate_complete)
            self._worker.thought_stream.connect(self._on_thought_stream)
            self._worker.error_occurred.connect(self.error_occurred.emit)
            self._worker.start()
            
            self.state_changed.emit("DEBATE", "验证失败，返回方案博弈修正...")
            return
        
        self.agent_response.emit("System", "🔍 生产阶段完成。PM 正在进行最终审批...")
        self._start_review()
    
    def _start_review(self):
        """启动 Phase 4: PM Final Review。"""
        self._reset_stream_state()
        
        self._worker = DebateWorker("review", self.ctx, self.router, self._last_user_input)
        self._worker.agent_responded.connect(self._on_agent_responded)
        self._worker.debate_finished.connect(self._on_review_complete)
        self._worker.thought_stream.connect(self._on_thought_stream)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.start()
        
        self.state_changed.emit("VERIFICATION", "PM 最终审批中...")
    
    def _on_review_complete(self, result: str):
        """全部完成。"""
        self._flush_buffer()
        self.agent_response.emit("System", "🎉 项目全流程完成！请查看 War Room 中的完整讨论记录。")
        self.state_changed.emit("COMPLETED", "任务完成")
        self.workflow_completed.emit()
    
    # ==================================================================
    #  _on_thought_stream — 块级累积 (从 CrewManager 继承)
    # ==================================================================
    
    def _on_thought_stream(self, text: str):
        """处理 CrewAI 的逐行输出，使用块级累积策略。
        
        与 CrewManager 的逻辑完全一致，保证 UI 消息不碎片化。
        """
        if not text:
            return
        
        raw = text
        
        # Unicode 解码
        if "\\u" in raw:
            try:
                import codecs
                raw = codecs.decode(raw, 'unicode_escape')
            except Exception:
                pass
        
        # 清理行 — 移除 ANSI 和装饰字符
        cleaned = self._clean_line(raw)
        
        if not cleaned:
            return
        
        # ===== 1. 检测角色切换 =====
        detected_role = self._detect_role(cleaned)
        if detected_role:
            if self._in_answer_block and self._answer_buffer:
                self._flush_buffer()
            self._current_role = detected_role
        
        # ===== 2. 检测 "Final Answer" 块开始 =====
        if "Final Answer" in cleaned or "Final Answer" in raw:
            self._in_answer_block = True
            remainder = cleaned.split("Final Answer")[-1].strip().lstrip(":").strip()
            if remainder and len(remainder) > 2:
                self._answer_buffer.append(remainder)
            return
        
        # ===== 3. 累积模式 =====
        if self._in_answer_block:
            # 结束信号
            end_signals = [
                "Agent:", "Working Agent:", "Starting Task:",
                "╭─", "╰─", "━━━", "───", "╔═", "╚═",
                "Task Completed", "Name:", "User Request:",
            ]
            if any(sig in raw for sig in end_signals):
                self._flush_buffer()
                return
            
            # 过滤噪声行
            skip_labels = [
                "Agent:", "Final Answer:", "Task:", "Using tool:",
                "Task Completed", "Name:", "User Request:", "Agent",
                "Working Agent",
            ]
            if any(cleaned.startswith(lbl) for lbl in skip_labels):
                return
            
            # 过滤装饰框和空行
            if self._is_box_border(cleaned) or len(cleaned) < 2:
                return
            
            # 累积有效内容
            self._answer_buffer.append(cleaned)
            return
        
        # ===== 4. 非累积模式：跳过非答案行 =====
    
    def _flush_buffer(self):
        """将累积缓冲区发射为完整消息。"""
        if not self._answer_buffer:
            return
        
        full_content = "\n".join(self._answer_buffer).strip()
        self._answer_buffer.clear()
        self._in_answer_block = False
        
        if not full_content or len(full_content) < 3:
            return
        
        # 内容级保护 — 过滤 CrewAI 元数据噪声
        stripped_text = re.sub(r'[✅❌🤖🚀📋⚡💬🧠■□▪▫●○◆◇\s]', '', full_content).strip()
        noise_words = {"Agent", "AgentStarted", "AgentCompleted", "TaskCompleted",
                       "PASS", "FAIL", "FinalAnswer", "WorkingAgent"}
        if stripped_text in noise_words or not stripped_text:
            return
        
        # 去重
        content_hash = hash(full_content)
        if content_hash in self._seen_messages:
            return
        self._seen_messages.add(content_hash)
        
        role = self._current_role
        self.agent_response.emit(role, full_content)
    
    def _clean_line(self, line: str) -> str:
        """清理一行文本。"""
        line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
        line = re.sub(r'[│┃┌┐└┘├┤┬┴┼─━═╭╮╰╯╔╗╚╝╟╢╤╧╪┕┑┍┙┏┓┗┛┣┫┳┻╋║╠╣╦╩╬]', '', line)
        return line.strip()
    
    def _detect_role(self, line: str) -> str:
        """从文本中检测角色。"""
        role_map = {
            "首席知识官": "CKO", "CKO": "CKO",
            "项目经理": "PM", "PM": "PM",
            "系统架构师": "Arch", "Arch": "Arch",
            "设计师": "Designer", "Designer": "Designer",
            "资深开发工程师": "Coder", "Coder": "Coder",
            "验证官": "Tester", "Tester": "Tester",
        }
        for key, val in role_map.items():
            if key in line:
                return val
        return ""
    
    def _is_box_border(self, line: str) -> bool:
        """检测是否为装饰框边框。"""
        border_chars = set("─━═╭╮╰╯╔╗╚╝┌┐└┘ -+")
        return len(line) > 3 and all(c in border_chars for c in line)
    
    def _reset_state(self):
        """完全重置所有状态。"""
        self._seen_messages.clear()
        self._answer_buffer.clear()
        self._current_role = "System"
        self._in_answer_block = False
        self._rework_count = 0  # 回退计数器归零
        self.ctx.reset()
    
    def _reset_stream_state(self):
        """仅重置流处理状态（不重置上下文）。"""
        self._answer_buffer.clear()
        self._current_role = "System"
        self._in_answer_block = False
