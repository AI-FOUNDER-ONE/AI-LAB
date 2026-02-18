"""阈值参数独立配置层。

将所有工况阈值参数从决策逻辑中解耦，统一管理。
标准更新时只需修改本文件，决策逻辑层零改动。
后续接入仿真模块时，可替换为实时数据源。

参考标准:
    - GB/T 1094.7 电力变压器油浸式变压器负载导则
    - DL/T 1465 变压器用有载分接开关技术条件
    - GB/T 34986 数字孪生术语
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any


class SeverityLevel(Enum):
    """风险严重等级枚举。"""
    SAFE = "安全"
    WARNING = "警告"
    CRITICAL = "危险"
    REJECT = "拒绝适配"


class OperatingCondition(Enum):
    """运行工况类型枚举。"""
    NORMAL = "正常工况"
    HEAVY_LOAD = "重载工况"
    EXTREME = "极端工况"
    FATIGUE = "疲劳衰减工况"


@dataclass(frozen=True)
class ThresholdParam:
    """单个阈值参数定义。

    Attributes:
        name: 参数中文名称。
        key: 参数唯一标识键名。
        unit: 物理单位。
        min_value: 最小允许值（含）。
        max_value: 最大允许值（含）。
        standard_ref: 引用标准编号。
        description: 参数说明。
    """
    name: str
    key: str
    unit: str
    min_value: float
    max_value: float
    standard_ref: str
    description: str = ""


@dataclass(frozen=True)
class FatigueDecayParam:
    """疲劳衰减模型参数。

    Attributes:
        initial_seal_efficiency: 初始密封效率（0-1）。
        annual_decay_rate: 年衰减率。
        vibration_acceleration_factor: 振动加速衰减因子。
        pressure_acceleration_factor: 油压波动加速衰减因子。
        max_service_years: 最大设计服务年限。
    """
    initial_seal_efficiency: float = 1.0
    annual_decay_rate: float = 0.02
    vibration_acceleration_factor: float = 1.5
    pressure_acceleration_factor: float = 1.3
    max_service_years: int = 30


# ============================================================
# 核心阈值参数配置（独立配置层）
# 所有数值来源于 GB/T 1094.7、DL/T 1465 等标准
# ============================================================

VIBRATION_THRESHOLD = ThresholdParam(
    name="最高振动幅值",
    key="vibration_amplitude",
    unit="g",
    min_value=0.0,
    max_value=0.8,
    standard_ref="GB/T 1094.7",
    description="变压器本体及附件的最大允许振动加速度幅值",
)

OIL_PRESSURE_THRESHOLD = ThresholdParam(
    name="油压波动范围",
    key="oil_pressure_fluctuation",
    unit="MPa",
    min_value=0.12,
    max_value=0.35,
    standard_ref="DL/T 1465",
    description="有载分接开关油室正常运行油压波动允许范围",
)

TEMPERATURE_THRESHOLD = ThresholdParam(
    name="油温上限",
    key="oil_temperature",
    unit="℃",
    min_value=-25.0,
    max_value=105.0,
    standard_ref="GB/T 1094.7",
    description="变压器油允许运行温度范围",
)

SEAL_PRESSURE_THRESHOLD = ThresholdParam(
    name="密封面压力",
    key="seal_surface_pressure",
    unit="MPa",
    min_value=0.5,
    max_value=2.0,
    standard_ref="DL/T 1465",
    description="阀门密封面允许工作压力范围",
)

CYCLE_COUNT_THRESHOLD = ThresholdParam(
    name="分接切换次数上限",
    key="switching_cycle_count",
    unit="次/年",
    min_value=0,
    max_value=50000,
    standard_ref="DL/T 1465",
    description="有载分接开关年允许最大切换次数",
)

# 疲劳衰减模型默认参数
DEFAULT_FATIGUE_PARAMS = FatigueDecayParam()

# 所有阈值参数注册表（便于遍历和动态查找）
THRESHOLD_REGISTRY: Dict[str, ThresholdParam] = {
    t.key: t for t in [
        VIBRATION_THRESHOLD,
        OIL_PRESSURE_THRESHOLD,
        TEMPERATURE_THRESHOLD,
        SEAL_PRESSURE_THRESHOLD,
        CYCLE_COUNT_THRESHOLD,
    ]
}


def get_threshold(key: str) -> ThresholdParam:
    """根据参数键名获取阈值配置。

    Args:
        key: 参数唯一标识键名。

    Returns:
        对应的阈值参数对象。

    Raises:
        KeyError: 当键名不存在于注册表中时抛出。
    """
    if key not in THRESHOLD_REGISTRY:
        raise KeyError(f"未知的阈值参数键名: '{key}'，"
                       f"可用键名: {list(THRESHOLD_REGISTRY.keys())}")
    return THRESHOLD_REGISTRY[key]
