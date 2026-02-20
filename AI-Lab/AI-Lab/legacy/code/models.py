"""数据模型与枚举定义模块。

本模块定义了向家坝电站主变压器自动取油装置系统的核心数据结构，
包括硬件模块标识、系统运行状态、模块状态、以及WebSocket推送消息格式。
所有枚举均继承str以支持JSON序列化。

遵循Google Python编程规范。
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ModuleID(str, Enum):
    """硬件模块标识枚举。

    每个枚举值对应一个物理隔离的硬件模块，
    单个模块故障不会触发整机停机。
    """

    PLC = "plc"           # PLC控制模块（西门子S7-1500）
    GC = "gc"             # 气相色谱分析模块
    SAMPLER = "sampler"   # 取样执行机构（伺服控制）
    GATEWAY = "gateway"   # 数据网关（IEC61850/Modbus TCP）


class SystemState(str, Enum):
    """系统运行状态枚举，驱动前端UI布局切换。

    状态转换规则：
    - NORMAL: 所有模块状态均为OK
    - DEGRADED: 部分模块故障，UI灰显故障控件+红色故障标签
    - OFFLINE: 所有模块均不可用，仅显示本地缓存数据
    """

    NORMAL = "normal"       # 全模块正常，完整界面
    DEGRADED = "degraded"   # 部分模块故障，降级模式
    OFFLINE = "offline"     # 整机离线，仅本地缓存


class SystemMode(str, Enum):
    """系统运行模式枚举。

    默认"独立采样"模式，异常报警时自动切换"联动分析"模式。
    """

    STANDALONE = "standalone"   # 独立采样模式
    LINKED = "linked"           # 联动分析模式


class ModuleState(str, Enum):
    """单个硬件模块的运行状态。

    状态判定逻辑：
    - OK: 心跳正常，数据读取成功
    - FAULT: 模块主动上报异常或数据校验失败
    - TIMEOUT: 心跳超时（超过HEARTBEAT_TIMEOUT_S秒未收到心跳）
    """

    OK = "ok"
    FAULT = "fault"
    TIMEOUT = "timeout"


@dataclass
class ModuleStatus:
    """单个模块的详细状态信息。

    Attributes:
        module_id: 模块标识。
        state: 当前状态。
        since: 进入当前状态的UTC时间戳（ISO 8601格式）。
        last_heartbeat: 最近一次心跳的单调时钟时间戳（秒）。
        detail: 附加状态描述信息，如故障原因。
    """

    module_id: ModuleID
    state: ModuleState = ModuleState.OK
    since: str = ""
    last_heartbeat: float = 0.0
    detail: str = ""

    def __post_init__(self) -> None:
        """初始化时自动填充时间戳和心跳。"""
        if not self.since:
            self.since = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = time.monotonic()

    def to_dict(self) -> Dict[str, Any]:
        """转换为可JSON序列化的字典（排除内部字段）。"""
        return {
            "state": self.state.value,
            "since": self.since,
            "detail": self.detail,
        }


@dataclass
class CacheInfo:
    """边缘端本地缓存信息（SQLite缓存 + 消息队列）。

    用于断点续传机制，网络恢复后自动补传。
    UI上显示"已缓存/容量上限"进度条。

    Attributes:
        used_mb: 已使用缓存空间（MB）。
        limit_mb: 缓存容量上限（MB）。
        pending_records: 待上传的记录数。
    """

    used_mb: float = 0.0
    limit_mb: float = 512.0
    pending_records: int = 0

    @property
    def usage_ratio(self) -> float:
        """缓存使用率（0.0 ~ 1.0）。"""
        if self.limit_mb <= 0:
            return 1.0
        return min(self.used_mb / self.limit_mb, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """转换为可JSON序列化的字典。"""
        return {
            "cache_used_mb": round(self.used_mb, 1),
            "cache_limit_mb": round(self.limit_mb, 1),
            "pending_records": self.pending_records,
            "usage_ratio": round(self.usage_ratio, 3),
        }


@dataclass
class SystemSnapshot:
    """系统状态快照，作为WebSocket推送的消息载体。

    推送格式示例：
    {
        "system_state": "degraded",
        "system_mode": "standalone",
        "modules": {
            "gc": {"state": "fault", "since": "2027-03-15T10:32:00Z", "detail": "..."},
            "plc": {"state": "ok", "since": "...", "detail": ""}
        },
        "cache_used_mb": 128,
        "cache_limit_mb": 512,
        "pending_records": 42,
        "usage_ratio": 0.25,
        "timestamp": "2027-03-15T10:32:01Z"
    }

    Attributes:
        system_state: 系统级运行状态。
        system_mode: 系统运行模式。
        modules: 各模块状态字典。
        cache: 缓存信息。
        timestamp: 快照生成时间。
    """

    system_state: SystemState = SystemState.NORMAL
    system_mode: SystemMode = SystemMode.STANDALONE
    modules: Dict[str, ModuleStatus] = field(default_factory=dict)
    cache: CacheInfo = field(default_factory=CacheInfo)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为WebSocket推送的JSON格式。"""
        result: Dict[str, Any] = {
            "system_state": self.system_state.value,
            "system_mode": self.system_mode.value,
            "modules": {
                mid: ms.to_dict() for mid, ms in self.modules.items()
            },
            "timestamp": self.timestamp,
        }
        result.update(self.cache.to_dict())
        return result


@dataclass
class GasReading:
    """单次气体浓度读数。

    覆盖变压器油中9种特征气体的色谱分析结果。

    Attributes:
        gas_name: 气体名称（如H2, CH4, C2H2等）。
        concentration_ppm: 浓度值（ppm）。
        status: 数据状态（0=正常, 1=超限报警, 2=数据异常）。
        timestamp: 采样时间。
    """

    gas_name: str
    concentration_ppm: float
    status: int = 0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )


# 变压器油中9种特征气体列表
CHARACTERISTIC_GASES: List[str] = [
    "H2",      # 氢气
    "CH4",     # 甲烷
    "C2H6",    # 乙烷
    "C2H4",    # 乙烯
    "C2H2",    # 乙炔
    "CO",      # 一氧化碳
    "CO2",     # 二氧化碳
    "O2",      # 氧气
    "N2",      # 氮气
]
