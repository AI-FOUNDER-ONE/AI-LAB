"""
chat_history.py - 对话历史管理器
=================================
维护每个 Agent 的对话历史，自动格式化为 API 调用所需格式，
并将完整历史序列化存储到 SessionStore。
"""

from typing import Optional
from datetime import datetime


class ChatHistoryManager:
    """对话历史管理器

    为每个 AI 角色维护独立的消息历史，格式化为各 API 规范格式，
    并提供历史检索和摘要功能。
    """

    def __init__(self):
        """初始化，创建各角色的消息历史存储"""
        self._histories: dict[str, list] = {}

    def init_role(self, role: str, system_prompt: str = ""):
        """初始化某个角色的对话历史

        Args:
            role: 角色标识 (CKO/PM/Arch/Designer/Coder/Tester)
            system_prompt: 系统提示词
        """
        self._histories[role] = []
        if system_prompt:
            self._histories[role].append({
                "role": "system",
                "content": system_prompt,
                "timestamp": datetime.now().isoformat(),
            })

    def add_message(self, role: str, sender: str, content: str):
        """添加一条消息到角色历史

        Args:
            role: 目标角色标识
            sender: 消息发送者类型 (user/assistant/system)
            content: 消息内容
        """
        if role not in self._histories:
            self._histories[role] = []

        self._histories[role].append({
            "role": sender,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_messages(self, role: str, include_system: bool = True) -> list:
        """获取角色的完整消息历史（格式化为 API 调用格式）

        Args:
            role: 角色标识
            include_system: 是否包含系统提示词

        Returns:
            格式化的消息列表 [{"role": "...", "content": "..."}]
        """
        history = self._histories.get(role, [])
        messages = []
        for msg in history:
            if not include_system and msg["role"] == "system":
                continue
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        return messages

    def get_last_message(self, role: str) -> Optional[dict]:
        """获取角色最后一条消息"""
        history = self._histories.get(role, [])
        if history:
            return history[-1]
        return None

    def get_full_log(self) -> list:
        """获取所有角色的完整对话日志（按时间排序）

        Returns:
            所有消息的合并列表，按时间排序
        """
        all_messages = []
        for role, history in self._histories.items():
            for msg in history:
                all_messages.append({
                    "agent_role": role,
                    **msg,
                })
        all_messages.sort(key=lambda x: x.get("timestamp", ""))
        return all_messages

    def clear_role(self, role: str):
        """清除某个角色的对话历史（保留系统提示词）"""
        if role in self._histories:
            system_msgs = [m for m in self._histories[role] if m["role"] == "system"]
            self._histories[role] = system_msgs

    def clear_all(self):
        """清除所有角色的对话历史"""
        for role in self._histories:
            self.clear_role(role)

    def to_dict(self) -> dict:
        """将完整历史导出为字典（用于 JSON 序列化）"""
        return {role: history for role, history in self._histories.items()}

    def from_dict(self, data: dict):
        """从字典恢复历史（用于 JSON 反序列化）"""
        self._histories = data
