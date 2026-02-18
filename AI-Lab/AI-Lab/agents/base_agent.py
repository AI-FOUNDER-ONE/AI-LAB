"""
base_agent.py - AI Agent 抽象基类
===================================
统一接口定义：send_message() / get_response()
内置消息历史管理和系统提示词配置。
所有具体角色 Agent 均继承此基类。
"""

import traceback
from abc import ABC, abstractmethod
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


class BaseAgent(QObject):
    """AI Agent 抽象基类

    定义所有 AI 角色的统一接口和通用行为。

    信号:
        response_ready: AI 回复完成信号 (role, content)
        stream_chunk: 流式输出信号 (role, chunk)
        error_occurred: 错误信号 (role, error_message)
        typing_started: 开始输入信号 (role)
        typing_finished: 结束输入信号 (role)
    """

    response_ready = pyqtSignal(str, str)    # (角色, 回复内容)
    stream_chunk = pyqtSignal(str, str)      # (角色, 文本片段)
    error_occurred = pyqtSignal(str, str)    # (角色, 错误消息)
    typing_started = pyqtSignal(str)         # (角色)
    typing_finished = pyqtSignal(str)        # (角色)

    def __init__(self, role: str, model_config: dict, system_prompt: str = "", parent=None):
        """初始化 Agent

        Args:
            role: 角色标识 (CKO/PM/Arch/Designer/Coder/Tester)
            model_config: 模型配置 {"provider": "...", "model": "..."}
            system_prompt: 系统提示词
            parent: Qt 父对象
        """
        super().__init__(parent)
        self.role = role
        self.model_config = model_config
        self.system_prompt = system_prompt
        self._messages = []
        self._is_active = False

        # 初始化消息历史
        if system_prompt:
            self._messages.append({
                "role": "system",
                "content": system_prompt,
            })

    def update_system_prompt(self, new_prompt: str):
        """Dynamic System Prompt Injection"""
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = new_prompt
        else:
            self._messages.insert(0, {"role": "system", "content": new_prompt})

    def set_domain_persona(self, task_type: str):
        """Dynamic Persona Injection based on Task Type"""
        persona_map = {
            "SOFTWARE": {
                "Arch": "System Architect", "Designer": "UI/UX Designer", "Coder": "Full-Stack Developer", "Tester": "QA Engineer"
            },
            "ENGINEERING": {
                "Arch": "Chief Engineer", "Designer": "CAD Specialist", "Coder": "Calculation Engineer", "Tester": "Safety Inspector"
            },
            "DESIGN": {
                "Arch": "Feasibility Analyst", "Designer": "Industrial Designer", "Coder": "Prototype Engineer", "Tester": "User Researcher"
            },
            "RESEARCH": {
                "Arch": "Methodology Expert", "Designer": "Data Visualizer", "Coder": "Data Analyst", "Tester": "Peer Reviewer"
            }
        }
        
        domain_role = persona_map.get(task_type, {}).get(self.role, self.role)
        
        injection = (
            f"\n\n[SYSTEM UPDATE]\n"
            f"Current Project Mode: {task_type}\n"
            f"Your Role Adaptation: {domain_role}\n"
            f"Please adjust your expertise and output format accordingly."
        )
        self.update_system_prompt(injection)

    @property
    def is_active(self) -> bool:
        """Agent 是否正在处理请求"""
        return self._is_active

    def send_message(self, content: str) -> str:
        """发送消息并获取回复（同步方法，由 QThread 调用）

        Args:
            content: 用户或系统发送的消息内容

        Returns:
            AI 的回复文本
        """
        self._is_active = True
        self.typing_started.emit(self.role)

        # 添加用户消息到历史
        self._messages.append({
            "role": "user",
            "content": content,
        })

        try:
            # 调用具体实现的 API 调用方法
            response = self._call_api(self._messages)

            # 添加助手回复到历史
            self._messages.append({
                "role": "assistant",
                "content": response,
            })

            self.response_ready.emit(self.role, response)
            return response

        except Exception as e:
            error_msg = f"[{self.role}] API 调用失败: {str(e)}\n{traceback.format_exc()}"
            self.error_occurred.emit(self.role, error_msg)
            return f"⚠️ 错误: {str(e)}"

        finally:
            self._is_active = False
            self.typing_finished.emit(self.role)

    @abstractmethod
    def _call_api(self, messages: list) -> str:
        """调用具体的 AI API（子类实现）

        Args:
            messages: 完整的消息历史列表

        Returns:
            API 返回的文本回复
        """
        raise NotImplementedError

    def add_context(self, content: str, role: str = "system"):
        """手动向消息历史中注入上下文

        Args:
            content: 上下文内容
            role: 消息角色 (system/user/assistant)
        """
        self._messages.append({
            "role": role,
            "content": content,
        })

    def get_messages(self) -> list:
        """获取完整消息历史"""
        return self._messages.copy()

    def clear_history(self):
        """清除消息历史（保留系统提示词）"""
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        self._messages = system_msgs

    def stop(self):
        """中止当前任务"""
        self._is_active = False
