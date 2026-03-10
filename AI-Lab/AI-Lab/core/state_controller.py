"""
state_controller.py - 状态驱动引擎
====================================
管理项目流程的状态机，控制状态转换逻辑，
通过 Qt 信号通知 UI 层状态变更。

状态流转: 空闲 → 需求打磨 → 方案博弈 → 执行阶段 → 验证阶段 → 任务完成
"""

import time
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from config import AppState


class StateController(QObject):
    """状态驱动引擎

    管理 AI-Lab-Commander 的核心流程状态机。
    每次状态变更均通过 Signal 通知 UI 和其他组件。

    信号:
        state_changed: 状态变更信号 (old_state, new_state)
        error_occurred: 错误信号 (error_message)
    """

    state_changed = pyqtSignal(str, str)     # (旧状态, 新状态)
    error_occurred = pyqtSignal(str)          # 错误消息

    # 合法的状态转换路径
    VALID_TRANSITIONS = {
        AppState.IDLE:         [AppState.GROUNDING],
        AppState.GROUNDING:    [AppState.DEBATE, AppState.IDLE],
        AppState.DEBATE:       [AppState.PRODUCTION, AppState.GROUNDING, AppState.IDLE],
        AppState.PRODUCTION:   [AppState.VERIFICATION, AppState.DEBATE, AppState.IDLE],
        AppState.VERIFICATION: [AppState.DELIVERY, AppState.PRODUCTION, AppState.DEBATE, AppState.COMPLETED, AppState.IDLE],  # 支持 VERIFICATION→DEBATE 闭环回退
        AppState.DELIVERY:     [AppState.COMPLETED, AppState.VERIFICATION, AppState.IDLE],
        AppState.COMPLETED:    [AppState.IDLE, AppState.DEBATE],  # 可返工：回到方案博弈重新评审
    }

    # 状态描述
    STATE_DESCRIPTIONS = {
        AppState.IDLE:         "空闲 - 等待新任务",
        AppState.GROUNDING:    "需求打磨 - CKO 深度访谈中",
        AppState.DEBATE:       "方案博弈 - PM/Arch/Designer 讨论中",
        AppState.PRODUCTION:   "执行阶段 - Coder/Expert 执行中",
        AppState.VERIFICATION: "验证阶段 - Tester/Reviewer 检验中",
        AppState.DELIVERY:     "交付汇总 - 打包最终成果",
        AppState.COMPLETED:    "任务完成",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_state = AppState.IDLE
        self._history = []  # 状态变更历史 [{ from_state, to_state, timestamp, trigger }, ...]
        self._current_state_entered_at = time.time()  # 进入当前状态的时刻（用于 get_time_in_stage）

    @property
    def current_state(self) -> str:
        """获取当前状态"""
        return self._current_state

    @property
    def state_description(self) -> str:
        """获取当前状态的中文描述"""
        return self.STATE_DESCRIPTIONS.get(self._current_state, "未知状态")

    def transition_to(self, new_state: str, trigger: str = "") -> bool:
        """尝试转换到新状态

        Args:
            new_state: 目标状态
            trigger: 可选，描述触发原因

        Returns:
            True 表示转换成功, False 表示转换被拒绝
        """
        valid_targets = self.VALID_TRANSITIONS.get(self._current_state, [])
        if new_state not in valid_targets:
            err_msg = (
                f"非法状态转换: {self._current_state} → {new_state}。"
                f"允许的目标: {valid_targets}"
            )
            self.error_occurred.emit(err_msg)
            return False

        old_state = self._current_state
        self._current_state = new_state
        self._current_state_entered_at = time.time()
        self._history.append({
            "from_state": old_state,
            "to_state": new_state,
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger,
        })
        self.state_changed.emit(old_state, new_state)
        return True

    def reset(self):
        """重置回 IDLE 状态"""
        old = self._current_state
        self._current_state = AppState.IDLE
        self._history.clear()
        self._current_state_entered_at = time.time()
        self.state_changed.emit(old, AppState.IDLE)

    def can_transition_to(self, target: str) -> bool:
        """检查是否可以转换到目标状态"""
        return target in self.VALID_TRANSITIONS.get(self._current_state, [])

    def get_history(self) -> list[dict]:
        """获取状态变更历史，每项为 { from_state, to_state, timestamp, trigger }"""
        return self._history.copy()

    def get_time_in_stage(self) -> float:
        """返回当前状态已持续的秒数"""
        return time.time() - self._current_state_entered_at
