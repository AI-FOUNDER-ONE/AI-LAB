"""模块健康监控与状态机调度服务。

本模块实现硬件模块心跳监控、系统状态推导、以及状态变更事件的
异步分发机制。采用事件驱动架构，状态变更时通过回调通知WebSocket层，
推送延迟≤100ms（通信50ms + 状态机计算50ms）。

设计要点：
- 心跳超时阈值3秒，兼顾Modbus TCP轮询周期（1s）和网络抖动容忍度
- compute_system_state为纯函数，无副作用，便于单元测试
- 各模块独立监控，单模块崩溃不影响其他模块状态上报（物理隔离一致性）

遵循Google Python编程规范。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from models import (
    CacheInfo,
    ModuleID,
    ModuleState,
    ModuleStatus,
    SystemMode,
    SystemSnapshot,
    SystemState,
)

# 日志配置
logger = logging.getLogger(__name__)

# 类型别名：状态变更回调函数签名
StateChangeCallback = Callable[[SystemSnapshot], Awaitable[None]]


class ModuleHealthMonitor:
    """模块健康监控器。

    聚合各硬件模块的心跳信号，实时推导系统级运行状态，
    并在状态变更时触发回调（WebSocket广播）。

    Attributes:
        HEARTBEAT_TIMEOUT_S: 心跳超时阈值（秒），超时判定为TIMEOUT。
        CHECK_INTERVAL_S: 健康检查轮询间隔（秒）。
    """

    HEARTBEAT_TIMEOUT_S: float = 3.0
    CHECK_INTERVAL_S: float = 0.5

    def __init__(
        self,
        on_state_change: Optional[StateChangeCallback] = None,
    ) -> None:
        """初始化监控器。

        Args:
            on_state_change: 系统状态变更时的异步回调函数，
                用于WebSocket广播推送。可为None（测试场景）。
        """
        # 各模块状态字典，初始化为OK
        self._modules: Dict[ModuleID, ModuleStatus] = {
            mid: ModuleStatus(module_id=mid) for mid in ModuleID
        }
        # 当前系统级状态
        self._system_state: SystemState = SystemState.NORMAL
        # 当前运行模式
        self._system_mode: SystemMode = SystemMode.STANDALONE
        # 边缘缓存信息
        self._cache: CacheInfo = CacheInfo()
        # 状态变更回调
        self._on_state_change = on_state_change
        # 后台检查任务句柄
        self._check_task: Optional[asyncio.Task[None]] = None

    @property
    def system_state(self) -> SystemState:
        """获取当前系统级运行状态。"""
        return self._system_state

    @property
    def system_mode(self) -> SystemMode:
        """获取当前系统运行模式。"""
        return self._system_mode

    def get_module_status(self, module_id: ModuleID) -> ModuleStatus:
        """获取指定模块的详细状态。

        Args:
            module_id: 目标模块标识。

        Returns:
            该模块的当前状态信息。
        """
        return self._modules[module_id]

    def get_snapshot(self) -> SystemSnapshot:
        """生成当前系统状态快照，用于WebSocket推送。

        Returns:
            包含所有模块状态和缓存信息的完整快照。
        """
        return SystemSnapshot(
            system_state=self._system_state,
            system_mode=self._system_mode,
            modules={
                mid.value: status
                for mid, status in self._modules.items()
            },
            cache=self._cache,
        )

    @staticmethod
    def compute_system_state(
        module_states: Dict[ModuleID, ModuleState],
    ) -> SystemState:
        """根据各模块状态推导系统级状态（纯函数）。

        状态推导规则：
        - 全部OK → NORMAL
        - 全部非OK → OFFLINE
        - 部分OK部分非OK → DEGRADED

        Args:
            module_states: 各模块当前状态的字典。

        Returns:
            推导出的系统级状态。
        """
        states = set(module_states.values())

        if states == {ModuleState.OK}:
            return SystemState.NORMAL

        if ModuleState.OK not in states:
            return SystemState.OFFLINE

        return SystemState.DEGRADED

    def update_heartbeat(
        self,
        module_id: ModuleID,
        state: ModuleState = ModuleState.OK,
        detail: str = "",
    ) -> None:
        """更新指定模块的心跳信息。

        由Modbus TCP采集服务在每次成功通信后调用。

        Args:
            module_id: 上报心跳的模块标识。
            state: 模块自报状态，默认OK。
            detail: 附加状态描述（如故障原因）。
        """
        status = self._modules[module_id]
        old_state = status.state

        status.last_heartbeat = time.monotonic()
        status.state = state
        status.detail = detail

        # 状态发生变化时更新since时间戳
        if old_state != state:
            status.since = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            logger.info(
                "模块 %s 状态变更: %s → %s, 原因: %s",
                module_id.value,
                old_state.value,
                state.value,
                detail or "心跳更新",
            )

    def update_cache_info(
        self,
        used_mb: float,
        pending_records: int,
    ) -> None:
        """更新边缘端缓存信息。

        Args:
            used_mb: 当前已使用缓存空间（MB）。
            pending_records: 待上传记录数。
        """
        self._cache.used_mb = used_mb
        self._cache.pending_records = pending_records

        # 缓存使用率超过90%时发出警告
        if self._cache.usage_ratio > 0.9:
            logger.warning(
                "边缘缓存使用率 %.1f%% 已超过90%%阈值，"
                "请检查网络连接或清理历史数据。",
                self._cache.usage_ratio * 100,
            )

    def set_mode(self, mode: SystemMode) -> None:
        """切换系统运行模式。

        Args:
            mode: 目标运行模式。
        """
        if self._system_mode != mode:
            logger.info(
                "系统模式切换: %s → %s",
                self._system_mode.value,
                mode.value,
            )
            self._system_mode = mode

    async def _check_health(self) -> None:
        """周期性健康检查协程。

        每隔CHECK_INTERVAL_S秒检查一次所有模块的心跳超时情况，
        并在系统状态发生变更时触发回调通知。
        """
        while True:
            try:
                now = time.monotonic()
                state_changed = False

                # 检查各模块心跳超时
                for mid, status in self._modules.items():
                    elapsed = now - status.last_heartbeat
                    if (
                        elapsed > self.HEARTBEAT_TIMEOUT_S
                        and status.state == ModuleState.OK
                    ):
                        # 心跳超时，标记为TIMEOUT
                        status.state = ModuleState.TIMEOUT
                        status.since = datetime.now(
                            timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                        status.detail = (
                            f"心跳超时 {elapsed:.1f}s "
                            f"(阈值 {self.HEARTBEAT_TIMEOUT_S}s)"
                        )
                        logger.warning(
                            "模块 %s 心跳超时: %.1fs",
                            mid.value,
                            elapsed,
                        )
                        state_changed = True

                # 推导新的系统级状态
                current_states = {
                    mid: s.state for mid, s in self._modules.items()
                }
                new_state = self.compute_system_state(current_states)

                if new_state != self._system_state:
                    old = self._system_state
                    self._system_state = new_state
                    state_changed = True
                    logger.info(
                        "系统状态变更: %s → %s",
                        old.value,
                        new_state.value,
                    )

                    # 自动模式切换：降级时切换到联动分析模式
                    if new_state == SystemState.DEGRADED:
                        self.set_mode(SystemMode.LINKED)
                    elif new_state == SystemState.NORMAL:
                        self.set_mode(SystemMode.STANDALONE)

                # 状态变更时触发回调（WebSocket广播）
                if state_changed and self._on_state_change:
                    snapshot = self.get_snapshot()
                    await self._on_state_change(snapshot)

            except asyncio.CancelledError:
                logger.info("健康检查任务已取消。")
                raise
            except Exception:
                logger.exception("健康检查过程中发生异常。")

            await asyncio.sleep(self.CHECK_INTERVAL_S)

    async def start(self) -> None:
        """启动后台健康检查任务。"""
        if self._check_task is None or self._check_task.done():
            self._check_task = asyncio.create_task(
                self._check_health()
            )
            logger.info(
                "模块健康监控已启动，检查间隔 %.1fs，"
                "心跳超时阈值 %.1fs。",
                self.CHECK_INTERVAL_S,
                self.HEARTBEAT_TIMEOUT_S,
            )

    async def stop(self) -> None:
        """停止后台健康检查任务。"""
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            logger.info("模块健康监控已停止。")
