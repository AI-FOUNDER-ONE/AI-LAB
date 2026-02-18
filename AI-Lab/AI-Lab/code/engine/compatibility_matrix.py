"""兼容性矩阵模块。

实现阀门型号与变压器工况的兼容性匹配逻辑。
矩阵数据与判定逻辑分离，支持动态扩展。

修复内容：
  - 修复综合判定中使用字符串比较代替枚举序数的 bug
  - 使用明确的严重等级排序逻辑替代隐式比较
  - 优化 _check_single_param 中除零保护
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from code.config.thresholds import (
    SeverityLevel,
    OperatingCondition,
    ThresholdParam,
    THRESHOLD_REGISTRY,
)


# 风险等级严重程度排序映射（数值越大越严重）
_SEVERITY_ORDER: Dict[SeverityLevel, int] = {
    SeverityLevel.SAFE: 0,
    SeverityLevel.WARNING: 1,
    SeverityLevel.CRITICAL: 2,
    SeverityLevel.REJECT: 3,
}

# 兼容性结果严重程度排序映射
_COMPAT_ORDER: Dict["CompatibilityResult", int] = {}


class CompatibilityResult(Enum):
    """兼容性判定结果枚举。"""
    COMPATIBLE = "完全兼容"
    CONDITIONAL = "条件兼容"
    INCOMPATIBLE = "不兼容"


# 初始化兼容性结果排序（枚举定义后填充）
_COMPAT_ORDER.update({
    CompatibilityResult.COMPATIBLE: 0,
    CompatibilityResult.CONDITIONAL: 1,
    CompatibilityResult.INCOMPATIBLE: 2,
})


@dataclass
class ValveSpec:
    """阀门型号规格参数。

    Attributes:
        model: 阀门型号标识。
        manufacturer: 制造商名称。
        max_vibration: 最大耐受振动幅值（g）。
        pressure_range: 耐受油压范围（MPa），元组 (min, max)。
        temp_range: 耐受温度范围（℃），元组 (min, max)。
        max_seal_pressure: 最大密封面压力（MPa）。
        rated_cycle_life: 额定切换寿命（次）。
        seal_material: 密封材料类型。
    """
    model: str
    manufacturer: str
    max_vibration: float
    pressure_range: Tuple[float, float]
    temp_range: Tuple[float, float]
    max_seal_pressure: float
    rated_cycle_life: int
    seal_material: str = "NBR"


@dataclass
class CompatibilityEntry:
    """兼容性矩阵单条判定记录。

    Attributes:
        param_key: 阈值参数键名。
        param_name: 参数中文名称。
        standard_range: 标准允许范围描述。
        valve_spec_value: 阀门规格对应值描述。
        result: 单项判定结果。
        severity: 风险等级。
        note: 备注说明。
    """
    param_key: str
    param_name: str
    standard_range: str
    valve_spec_value: str
    result: CompatibilityResult
    severity: SeverityLevel
    note: str = ""


@dataclass
class CompatibilityReport:
    """兼容性矩阵完整报告。

    Attributes:
        valve: 被评估的阀门规格。
        condition: 运行工况类型。
        entries: 各参数的判定记录列表。
        overall_result: 综合判定结果。
        overall_severity: 综合风险等级。
        recommendation: 适配建议。
    """
    valve: ValveSpec
    condition: OperatingCondition
    entries: List[CompatibilityEntry] = field(default_factory=list)
    overall_result: CompatibilityResult = CompatibilityResult.COMPATIBLE
    overall_severity: SeverityLevel = SeverityLevel.SAFE
    recommendation: str = ""


def _check_single_param(
    value: float,
    threshold: ThresholdParam,
) -> Tuple[CompatibilityResult, SeverityLevel]:
    """单参数阈值校验。

    根据实际值与标准阈值的偏离程度，分级判定兼容性：
      - 在范围内 → 完全兼容/安全
      - 越限 ≤10% → 条件兼容/警告
      - 越限 ≤25% → 不兼容/危险
      - 越限 >25% → 不兼容/拒绝适配

    Args:
        value: 实际参数值。
        threshold: 阈值参数配置。

    Returns:
        (兼容性结果, 风险等级) 元组。
    """
    if threshold.min_value <= value <= threshold.max_value:
        return CompatibilityResult.COMPATIBLE, SeverityLevel.SAFE

    # 计算越限比例，用于分级判定
    if value > threshold.max_value:
        # 防止除零：max_value 为 0 时视为完全越限
        if threshold.max_value == 0:
            exceed_ratio = 1.0
        else:
            exceed_ratio = (value - threshold.max_value) / threshold.max_value
    else:
        # value < min_value 的情况
        if threshold.min_value == 0:
            exceed_ratio = 1.0
        else:
            exceed_ratio = abs(threshold.min_value - value) / abs(threshold.min_value)

    # 越限10%以内为条件兼容（警告），超过则不兼容
    if exceed_ratio <= 0.10:
        return CompatibilityResult.CONDITIONAL, SeverityLevel.WARNING
    elif exceed_ratio <= 0.25:
        return CompatibilityResult.INCOMPATIBLE, SeverityLevel.CRITICAL
    else:
        return CompatibilityResult.INCOMPATIBLE, SeverityLevel.REJECT


def _extract_valve_value_for_param(
    valve: ValveSpec,
    param_key: str,
) -> Optional[float]:
    """从阀门规格中提取与阈值参数对应的数值。

    Args:
        valve: 阀门规格对象。
        param_key: 阈值参数键名。

    Returns:
        对应的数值，无法映射时返回 None。
    """
    mapping = {
        "vibration_amplitude": valve.max_vibration,
        "oil_pressure_fluctuation": valve.pressure_range[1],
        "oil_temperature": valve.temp_range[1],
        "seal_surface_pressure": valve.max_seal_pressure,
        "switching_cycle_count": float(valve.rated_cycle_life),
    }
    return mapping.get(param_key)


def evaluate_compatibility(
    valve: ValveSpec,
    condition: OperatingCondition = OperatingCondition.NORMAL,
) -> CompatibilityReport:
    """执行兼容性矩阵评估（第一层：标准阈值初筛）。

    遍历所有注册的阈值参数，逐项校验阀门规格是否满足标准要求，
    生成完整的兼容性报告。综合判定取所有单项中最差的结果。

    Args:
        valve: 待评估的阀门规格。
        condition: 当前运行工况类型。

    Returns:
        兼容性评估报告。
    """
    report = CompatibilityReport(valve=valve, condition=condition)
    worst_result = CompatibilityResult.COMPATIBLE
    worst_severity = SeverityLevel.SAFE

    for param_key, threshold in THRESHOLD_REGISTRY.items():
        value = _extract_valve_value_for_param(valve, param_key)

        if value is None:
            # 无法映射的参数，标记为需人工复核
            entry = CompatibilityEntry(
                param_key=param_key,
                param_name=threshold.name,
                standard_range=f"{threshold.min_value}~{threshold.max_value} {threshold.unit}",
                valve_spec_value="数据缺失",
                result=CompatibilityResult.CONDITIONAL,
                severity=SeverityLevel.WARNING,
                note="阀门规格中未提供该参数，需人工复核",
            )
        else:
            result, severity = _check_single_param(value, threshold)
            entry = CompatibilityEntry(
                param_key=param_key,
                param_name=threshold.name,
                standard_range=f"{threshold.min_value}~{threshold.max_value} {threshold.unit}",
                valve_spec_value=f"{value} {threshold.unit}",
                result=result,
                severity=severity,
            )

        report.entries.append(entry)

        # 使用排序映射取最差结果（修复原有字符串比较 bug）
        if _COMPAT_ORDER.get(entry.result, 0) > _COMPAT_ORDER.get(worst_result, 0):
            worst_result = entry.result
        if _SEVERITY_ORDER.get(entry.severity, 0) > _SEVERITY_ORDER.get(worst_severity, 0):
            worst_severity = entry.severity

    report.overall_result = worst_result
    report.overall_severity = worst_severity
    report.recommendation = _generate_recommendation(report)

    return report


def _generate_recommendation(report: CompatibilityReport) -> str:
    """根据评估结果生成适配建议。

    Args:
        report: 兼容性评估报告。

    Returns:
        中文适配建议文本。
    """
    if report.overall_result == CompatibilityResult.COMPATIBLE:
        return (f"阀门型号 {report.valve.model} 在{report.condition.value}下"
                f"完全满足标准要求，可直接适配使用。")

    if report.overall_result == CompatibilityResult.CONDITIONAL:
        warning_params = [e.param_name for e in report.entries
                         if e.severity == SeverityLevel.WARNING]
        return (f"阀门型号 {report.valve.model} 在{report.condition.value}下"
                f"条件兼容，以下参数需关注: {', '.join(warning_params)}。"
                f"建议加强监测或缩短检修周期。")

    # 不兼容情况
    critical_params = [e.param_name for e in report.entries
                      if e.severity in (SeverityLevel.CRITICAL, SeverityLevel.REJECT)]
    return (f"阀门型号 {report.valve.model} 在{report.condition.value}下"
            f"不满足标准要求，不兼容参数: {', '.join(critical_params)}。"
            f"建议更换阀门型号或降低运行工况等级。")
