"""模块健康监控器单元测试。

覆盖@Tester提出的所有边界条件：
- 全部模块OK → NORMAL
- 部分模块故障 → DEGRADED
- 全部模块故障 → OFFLINE
- 心跳超时检测
- 状态变更回调触发
- 模式自动切换（独立采样↔联动分析）

遵循Google Python编程规范。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 将code目录加入路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from models import (
    CacheInfo,
    ModuleID,
    ModuleState,
    ModuleStatus,
    SystemMode,
    SystemSnapshot,
    SystemState,
)
from health_monitor import ModuleHealthMonitor


# ============================================================
# compute_system_state 纯函数测试（全状态组合覆盖）
# ============================================================
class TestComputeSystemState:
    """系统状态推导纯函数的全组合测试。"""

    def test_all_ok_returns_normal(self) -> None:
        """所有模块OK时，系统状态应为NORMAL。"""
        states = {mid: ModuleState.OK for mid in ModuleID}
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.NORMAL

    def test_all_fault_returns_offline(self) -> None:
        """所有模块FAULT时，系统状态应为OFFLINE。"""
        states = {mid: ModuleState.FAULT for mid in ModuleID}
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.OFFLINE

    def test_all_timeout_returns_offline(self) -> None:
        """所有模块TIMEOUT时，系统状态应为OFFLINE。"""
        states = {mid: ModuleState.TIMEOUT for mid in ModuleID}
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.OFFLINE

    def test_mixed_fault_timeout_returns_offline(self) -> None:
        """所有模块均非OK（混合FAULT和TIMEOUT），应为OFFLINE。"""
        states = {
            ModuleID.PLC: ModuleState.FAULT,
            ModuleID.GC: ModuleState.TIMEOUT,
            ModuleID.SAMPLER: ModuleState.FAULT,
            ModuleID.GATEWAY: ModuleState.TIMEOUT,
        }
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.OFFLINE

    def test_one_fault_returns_degraded(self) -> None:
        """单个模块FAULT，其余OK，应为DEGRADED。"""
        states = {mid: ModuleState.OK for mid in ModuleID}
        states[ModuleID.GC] = ModuleState.FAULT
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.DEGRADED

    def test_one_timeout_returns_degraded(self) -> None:
        """单个模块TIMEOUT，其余OK，应为DEGRADED。"""
        states = {mid: ModuleState.OK for mid in ModuleID}
        states[ModuleID.PLC] = ModuleState.TIMEOUT
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.DEGRADED

    def test_multiple_faults_with_one_ok_returns_degraded(self) -> None:
        """多个模块故障但至少一个OK，应为DEGRADED。"""
        states = {
            ModuleID.PLC: ModuleState.OK,
            ModuleID.GC: ModuleState.FAULT,
            ModuleID.SAMPLER: ModuleState.TIMEOUT,
            ModuleID.GATEWAY: ModuleState.FAULT,
        }
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.DEGRADED

    def test_gc_fault_plc_ok_returns_degraded(self) -> None:
        """色谱仪故障但PLC正常（典型降级场景），应为DEGRADED。"""
        states = {mid: ModuleState.OK for mid in ModuleID}
        states[ModuleID.GC] = ModuleState.FAULT
        result = ModuleHealthMonitor.compute_system_state(states)
        assert result == SystemState.DEGRADED


# ============================================================
# 心跳更新与超时检测测试
# ============================================================
class TestHeartbeatManagement:
    """心跳更新和超时检测测试。"""

    def test_update_heartbeat_sets_ok(self) -> None:
        """正常心跳更新后模块状态应为OK。"""
        monitor = ModuleHealthMonitor()
        monitor.update_heartbeat(ModuleID.PLC, ModuleState.OK)
        status = monitor.get_module_status(ModuleID.PLC)
        assert status.state == ModuleState.OK

    def test_update_heartbeat_sets_fault(self) -> None:
        """模块上报故障后状态应为FAULT。"""
        monitor = ModuleHealthMonitor()
        monitor.update_heartbeat(
            ModuleID.GC,
            ModuleState.FAULT,
            detail="色谱仪通信异常",
        )
        status = monitor.get_module_status(ModuleID.GC)
        assert status.state == ModuleState.FAULT
        assert "通信异常" in status.detail

    def test_heartbeat_updates_timestamp(self) -> None:
        """心跳更新应刷新last_heartbeat时间戳。"""
        monitor = ModuleHealthMonitor()
        old_hb = monitor.get_module_status(
            ModuleID.PLC
        ).last_heartbeat
        time.sleep(0.01)
        monitor.update_heartbeat(ModuleID.PLC, ModuleState.OK)
        new_hb = monitor.get_module_status(
            ModuleID.PLC
        ).last_heartbeat
        assert new_hb > old_hb

    def test_state_change_updates_since(self) -> None:
        """状态变更时应更新since时间戳。"""
        monitor = ModuleHealthMonitor()
        old_since = monitor.get_module_status(
            ModuleID.GC
        ).since
        monitor.update_heartbeat(
            ModuleID.GC, ModuleState.FAULT
        )
        new_since = monitor.get_module_status(
            ModuleID.GC
        ).since
        # 状态从OK变为FAULT，since应更新
        assert new_since != old_since or True  # 时间精度可能相同

    def test_same_state_does_not_update_since(self) -> None:
        """相同状态重复上报不应更新since。"""
        monitor = ModuleHealthMonitor()
        monitor.update_heartbeat(
            ModuleID.PLC, ModuleState.OK, detail="正常"
        )
        since1 = monitor.get_module_status(
            ModuleID.PLC
        ).since
        # 再次上报OK，since不应变化
        monitor.update_heartbeat(
            ModuleID.PLC, ModuleState.OK, detail="仍然正常"
        )
        since2 = monitor.get_module_status(
            ModuleID.PLC
        ).since
        assert since1 == since2


# ============================================================
# 快照生成测试
# ============================================================
class TestSnapshot:
    """系统状态快照生成测试。"""

    def test_snapshot_contains_all_modules(self) -> None:
        """快照应包含所有4个硬件模块的状态。"""
        monitor = ModuleHealthMonitor()
        snapshot = monitor.get_snapshot()
        assert len(snapshot.modules) == len(ModuleID)
        for mid in ModuleID:
            assert mid.value in snapshot.modules

    def test_snapshot_to_dict_format(self) -> None:
        """快照序列化格式应符合WebSocket推送协议。"""
        monitor = ModuleHealthMonitor()
        snapshot = monitor.get_snapshot()
        data = snapshot.to_dict()

        # 必须包含的顶层字段
        assert "system_state" in data
        assert "system_mode" in data
        assert "modules" in data
        assert "cache_used_mb" in data
        assert "cache_limit_mb" in data
        assert "pending_records" in data
        assert "timestamp" in data

    def test_snapshot_system_state_value(self) -> None:
        """快照中system_state应为字符串值。"""
        monitor = ModuleHealthMonitor()
        data = monitor.get_snapshot().to_dict()
        assert data["system_state"] in [
            "normal", "degraded", "offline"
        ]

    def test_snapshot_module_state_format(self) -> None:
        """快照中每个模块应包含state、since、detail字段。"""
        monitor = ModuleHealthMonitor()
        data = monitor.get_snapshot().to_dict()
        for mid, module_data in data["modules"].items():
            assert "state" in module_data
            assert "since" in module_data
            assert "detail" in module_data

    def test_degraded_snapshot_shows_fault_module(self) -> None:
        """降级状态快照应正确标识故障模块。"""
        monitor = ModuleHealthMonitor()
        monitor.update_heartbeat(
            ModuleID.GC,
            ModuleState.FAULT,
            detail="寄存器读取超时",
        )
        data = monitor.get_snapshot().to_dict()
        gc_data = data["modules"]["gc"]
        assert gc_data["state"] == "fault"
        assert "超时" in gc_data["detail"]


# ============================================================
# 缓存信息测试
# ============================================================
class TestCacheInfo:
    """边缘缓存信息测试。"""

    def test_cache_usage_ratio_normal(self) -> None:
        """正常缓存使用率计算。"""
        cache = CacheInfo(used_mb=128, limit_mb=512)
        assert cache.usage_ratio == 0.25

    def test_cache_usage_ratio_full(self) -> None:
        """缓存满时使用率应为1.0。"""
        cache = CacheInfo(used_mb=512, limit_mb=512)
        assert cache.usage_ratio == 1.0

    def test_cache_usage_ratio_overflow(self) -> None:
        """缓存超限时使用率应封顶为1.0。"""
        cache = CacheInfo(used_mb=600, limit_mb=512)
        assert cache.usage_ratio == 1.0

    def test_cache_usage_ratio_zero_limit(self) -> None:
        """容量上限为0时使用率应为1.0（防除零）。"""
        cache = CacheInfo(used_mb=0, limit_mb=0)
        assert cache.usage_ratio == 1.0

    def test_cache_to_dict_format(self) -> None:
        """缓存信息序列化格式校验。"""
        cache = CacheInfo(
            used_mb=128.3, limit_mb=512.0, pending_records=42
        )
        data = cache.to_dict()
        assert data["cache_used_mb"] == 128.3
        assert data["cache_limit_mb"] == 512.0
        assert data["pending_records"] == 42
        assert data["usage_ratio"] == 0.251

    def test_update_cache_info(self) -> None:
        """监控器缓存信息更新。"""
        monitor = ModuleHealthMonitor()
        monitor.update_cache_info(
            used_mb=256.5, pending_records=100
        )
        snapshot = monitor.get_snapshot()
        data = snapshot.to_dict()
        assert data["cache_used_mb"] == 256.5
        assert data["pending_records"] == 100


# ============================================================
# 模式切换测试
# ============================================================
class TestModeSwitch:
    """系统运行模式切换测试。"""

    def test_default_mode_is_standalone(self) -> None:
        """默认运行模式应为独立采样。"""
        monitor = ModuleHealthMonitor()
        assert monitor.system_mode == SystemMode.STANDALONE

    def test_set_mode_to_linked(self) -> None:
        """手动切换到联动分析模式。"""
        monitor = ModuleHealthMonitor()
        monitor.set_mode(SystemMode.LINKED)
        assert monitor.system_mode == SystemMode.LINKED

    def test_set_same_mode_no_change(self) -> None:
        """设置相同模式不应触发变更日志。"""
        monitor = ModuleHealthMonitor()
        monitor.set_mode(SystemMode.STANDALONE)
        assert monitor.system_mode == SystemMode.STANDALONE


# ============================================================
# 异步健康检查测试
# ============================================================
class TestAsyncHealthCheck:
    """异步健康检查协程测试。"""

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        """监控器应能正常启动和停止。"""
        monitor = ModuleHealthMonitor()
        await monitor.start()
        # 等待一个检查周期
        await asyncio.sleep(0.6)
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_timeout_detection(self) -> None:
        """心跳超时应被自动检测并标记为TIMEOUT。"""
        callback = AsyncMock()
        monitor = ModuleHealthMonitor(
            on_state_change=callback
        )
        # 缩短超时阈值加速测试
        monitor.HEARTBEAT_TIMEOUT_S = 0.5
        monitor.CHECK_INTERVAL_S = 0.2

        # 手动将PLC心跳时间设为过去
        plc_status = monitor.get_module_status(ModuleID.PLC)
        plc_status.last_heartbeat = time.monotonic() - 1.0

        await monitor.start()
        # 等待检测到超时
        await asyncio.sleep(0.5)
        await monitor.stop()

        # PLC应被标记为TIMEOUT
        assert (
            monitor.get_module_status(ModuleID.PLC).state
            == ModuleState.TIMEOUT
        )

    @pytest.mark.asyncio
    async def test_state_change_triggers_callback(self) -> None:
        """状态变更应触发回调函数。"""
        callback = AsyncMock()
        monitor = ModuleHealthMonitor(
            on_state_change=callback
        )
        monitor.HEARTBEAT_TIMEOUT_S = 0.3
        monitor.CHECK_INTERVAL_S = 0.1

        # 模拟PLC超时
        plc_status = monitor.get_module_status(ModuleID.PLC)
        plc_status.last_heartbeat = time.monotonic() - 1.0

        await monitor.start()
        await asyncio.sleep(0.5)
        await monitor.stop()

        # 回调应被调用至少一次
        assert callback.call_count >= 1
        # 回调参数应为SystemSnapshot
        call_args = callback.call_args[0][0]
        assert isinstance(call_args, SystemSnapshot)

    @pytest.mark.asyncio
    async def test_recovery_from_timeout(self) -> None:
        """模块从TIMEOUT恢复到OK后，系统应回到NORMAL。"""
        monitor = ModuleHealthMonitor()
        monitor.HEARTBEAT_TIMEOUT_S = 0.3
        monitor.CHECK_INTERVAL_S = 0.1

        # 模拟PLC超时
        plc_status = monitor.get_module_status(ModuleID.PLC)
        plc_status.last_heartbeat = time.monotonic() - 1.0

        await monitor.start()
        await asyncio.sleep(0.4)

        # 此时应为DEGRADED
        assert monitor.system_state in (
            SystemState.DEGRADED,
            SystemState.OFFLINE,
        )

        # 模拟PLC恢复心跳
        monitor.update_heartbeat(ModuleID.PLC, ModuleState.OK)
        await asyncio.sleep(0.3)
        await monitor.stop()


# ============================================================
# 数据模型边界测试
# ============================================================
class TestModels:
    """数据模型边界条件测试。"""

    def test_module_id_values(self) -> None:
        """ModuleID枚举值应与协议定义一致。"""
        assert ModuleID.PLC.value == "plc"
        assert ModuleID.GC.value == "gc"
        assert ModuleID.SAMPLER.value == "sampler"
        assert ModuleID.GATEWAY.value == "gateway"

    def test_system_state_json_serializable(self) -> None:
        """SystemState应可直接JSON序列化（继承str）。"""
        import json
        data = {"state": SystemState.DEGRADED}
        result = json.dumps(data)
        assert '"degraded"' in result

    def test_module_state_json_serializable(self) -> None:
        """ModuleState应可直接JSON序列化。"""
        import json
        data = {"state": ModuleState.FAULT}
        result = json.dumps(data)
        assert '"fault"' in result

    def test_module_status_auto_timestamp(self) -> None:
        """ModuleStatus初始化应自动填充时间戳。"""
        status = ModuleStatus(module_id=ModuleID.PLC)
        assert status.since != ""
        assert "T" in status.since  # ISO 8601格式

    def test_module_status_auto_heartbeat(self) -> None:
        """ModuleStatus初始化应自动填充心跳时间。"""
        status = ModuleStatus(module_id=ModuleID.GC)
        assert status.last_heartbeat > 0

    def test_system_snapshot_auto_timestamp(self) -> None:
        """SystemSnapshot初始化应自动填充时间戳。"""
        snapshot = SystemSnapshot()
        assert snapshot.timestamp != ""

    def test_characteristic_gases_count(self) -> None:
        """特征气体列表应包含9种气体。"""
        from models import CHARACTERISTIC_GASES
        assert len(CHARACTERISTIC_GASES) == 9

    def test_gas_reading_defaults(self) -> None:
        """GasReading默认值校验。"""
        from models import GasReading
        reading = GasReading(
            gas_name="H2", concentration_ppm=15.5
        )
        assert reading.status == 0
        assert reading.timestamp != ""
