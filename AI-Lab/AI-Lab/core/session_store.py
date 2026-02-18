"""
session_store.py - 会话数据持久化
==================================
管理 JSON 格式的会话存储，支持创建、读取、更新和列举历史会话。
存储路径: data/sessions/{timestamp}.json
"""

import os
import json
from datetime import datetime
from typing import Optional

from config import SESSIONS_DIR


class SessionStore:
    """会话数据持久化管理器

    负责将每次任务协作的完整记录存储为 JSON 文件，
    包括用户意图、会议记录、最终代码和测试报告。
    """

    def __init__(self):
        """初始化，确保存储目录存在"""
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self._current_session = None
        self._current_path = None

    def create_session(self, user_intent: str = "") -> dict:
        """创建新会话

        Args:
            user_intent: 用户的初始意图描述

        Returns:
            新会话的数据字典
        """
        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}.json"
        self._current_path = os.path.join(SESSIONS_DIR, filename)

        self._current_session = {
            "session_id": session_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "user_intent": user_intent,
            "state": "IDLE",
            "mission_protocol": None,
            "cko_logs": [],
            "meeting_logs": [],
            "final_code": "",
            "test_reports": [],
            "timeline_events": [],
        }
        self._save()
        return self._current_session

    def update_session(self, **kwargs):
        """更新当前会话的字段

        Args:
            **kwargs: 要更新的字段键值对
        """
        if self._current_session is None:
            return
        self._current_session["updated_at"] = datetime.now().isoformat()
        self._current_session.update(kwargs)
        self._save()

    def append_cko_log(self, role: str, content: str):
        """追加 CKO 对话记录"""
        if self._current_session is None:
            return
        self._current_session["cko_logs"].append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        })
        self._save()

    def append_meeting_log(self, role: str, content: str):
        """追加会议讨论记录"""
        if self._current_session is None:
            return
        self._current_session["meeting_logs"].append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        })
        self._save()

    def append_test_report(self, report: dict):
        """追加测试报告记录"""
        if self._current_session is None:
            return
        report["timestamp"] = datetime.now().isoformat()
        self._current_session["test_reports"].append(report)
        self._save()

    def append_timeline_event(self, state: str, description: str):
        """追加时间轴事件"""
        if self._current_session is None:
            return
        self._current_session["timeline_events"].append({
            "timestamp": datetime.now().isoformat(),
            "state": state,
            "description": description,
        })
        self._save()

    def get_current_session(self) -> Optional[dict]:
        """获取当前会话数据"""
        return self._current_session

    def list_sessions(self) -> list:
        """列举所有历史会话

        Returns:
            按时间倒序排列的会话摘要列表
        """
        sessions = []
        if not os.path.exists(SESSIONS_DIR):
            return sessions

        for filename in sorted(os.listdir(SESSIONS_DIR), reverse=True):
            if filename.endswith(".json"):
                filepath = os.path.join(SESSIONS_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id", ""),
                        "created_at": data.get("created_at", ""),
                        "user_intent": data.get("user_intent", ""),
                        "state": data.get("state", "IDLE"),
                        "filepath": filepath,
                    })
                except (json.JSONDecodeError, IOError):
                    continue
        return sessions

    def load_session(self, filepath: str) -> Optional[dict]:
        """加载历史会话

        Args:
            filepath: 会话 JSON 文件路径

        Returns:
            会话数据字典，加载失败返回 None
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self._current_session = json.load(f)
                self._current_path = filepath
            return self._current_session
        except (json.JSONDecodeError, IOError) as e:
            print(f"[SessionStore] 加载会话失败: {e}")
            return None

    def get_debate_context(self, limit: int = 5) -> str:
        """获取最近的博弈上下文用于构建 Prompt
        
        Args:
            limit: 返回最近的几条记录
            
        Returns:
            格式化后的对话历史字符串
        """
        if self._current_session is None:
            return ""
            
        logs = self._current_session.get("meeting_logs", [])
        if not logs:
            return "（暂无历史记录）"
            
        # 取最后 N 条
        recent_logs = logs[-limit:]
        
        context_lines = []
        for log in recent_logs:
            role = log.get("role", "Unknown")
            content = log.get("content", "")
            # 截断过长内容以节省 Token
            if len(content) > 500:
                content = content[:500] + "...(内容过长已截断)"
            context_lines.append(f"[{role}]: {content}")
            
        return "\n\n".join(context_lines)

    def get_all_meeting_logs(self) -> str:
        """获取所有会议记录（用于 Coder 上下文）
        
        Returns:
             格式化后的完整会议记录字符串
        """
        if self._current_session is None:
            return "（暂无会议记录）"
            
        logs = self._current_session.get("meeting_logs", [])
        if not logs:
            return "（暂无会议记录）"
            
        context_lines = []
        for log in logs:
            role = log.get("role", "Unknown")
            content = log.get("content", "")
            timestamp = log.get("timestamp", "")[11:19] # 只取时间部分
            context_lines.append(f"[{timestamp}] [{role}]: {content}")
            
        return "\n\n".join(context_lines)

    def _save(self):
        """将当前会话数据写入 JSON 文件"""
        if self._current_session is None or self._current_path is None:
            return
        try:
            with open(self._current_path, "w", encoding="utf-8") as f:
                json.dump(self._current_session, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[SessionStore] 保存会话失败: {e}")
