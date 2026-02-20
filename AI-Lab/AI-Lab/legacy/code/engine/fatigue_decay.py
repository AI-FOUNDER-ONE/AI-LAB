"""疲劳衰减模型模块（第二层：动态调整）。

基于初始密封效率和年衰减率，结合振动、油压等加速因子，
计算阀门密封性能随运行年限的衰减曲线。
支持多参数联合判定，覆盖极端工况耦合场景。

修复内容：
  - 为 _compute_coupled_acceleration_factor 增加输入边界校验
  - 修复温度修正因子在低温场景下可能产生负指数异常的问题
  - 增加衰减曲线数据点的效率下限钳位（不低于0）
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from code.config.thresholds import (
    SeverityLevel,
    OperatingCondition,
    FatigueDecayParam,
    DEFAULT_FATIGUE_PARAMS,
    THRESHOLD_REGISTRY,
)


@dataclass
class DecayPoint:
    """衰减曲线上的单个数据点。

    Attributes:
        year: 运行年份。
        seal_efficiency: 当前密封效率（0-1）。
        severity: 当前风险等级。
        is_failure_point: 是否为失效临界点。
    """
    year: int
    seal_efficiency: float
    severity: SeverityLevel
    is_failure_point: bool = False


@dataclass
class CoupledCondition:
    """多参数联合工况描述。

    Attributes:
        vibration_amplitude: 实际振动幅值（g），必须 >= 0。
        oil_pressure: 实际油压波动值（MPa），必须 >= 0。
        oil_temperature: 实际油温（℃）。
        annual_switching_cycles: 年切换次数，必须 >= 0。
    """
    vibration_amplitude: float = 0.0
    oil_pressure: float = 0.0
    oil_temperature: float = 60.0
    annual_switching_cycles: int = 10000

    def __post_init__(self):
        """输入边界校验：确保物理量非负。"""
        if self.vibration_amplitude < 0:
            raise ValueError(
                f"振动幅值不能为负数: {self.vibration_amplitude}")
        if self.oil_pressure < 0:
            raise ValueError(
                f"油压波动值不能为负数: {self.oil_pressure}")
        if self.annual_switching_cycles < 0:
            raise ValueError(
                f"年切换次数不能为负数: {self.annual_switching_cycles}")


@dataclass
class FatigueDecayReport:
    """疲劳衰减评估报告。

    Attributes:
        service_years: 预计运行年限。
        fatigue_params: 使用的衰减模型参数。
        coupled_condition: 联合工况条件。
        decay_curve: 衰减曲线数据点列表。
        predicted_failure_year: 预测失效年份（密封效率低于阈值）。
        final_efficiency: 目标年限末的密封效率。
        final_severity: 目标年限末的风险等级。
        coupled_risk_flag: 多参数耦合风险标记。
        recommendation: 评估建议。
    """
    service_years: int
    fatigue_params: FatigueDecayParam
    coupled_condition: CoupledCondition
    decay_curve: List[DecayPoint] = field(default_factory=list)
    predicted_failure_year: Optional[int] = None
    final_efficiency: float = 1.0
    final_severity: SeverityLevel = SeverityLevel.SAFE
    coupled_risk_flag: bool = False
    recommendation: str = ""


# ============================================================
# 密封效率阈值（用于风险分级）
# ============================================================
_EFFICIENCY_SAFE = 0.75        # 高于此值为安全
_EFFICIENCY_WARNING = 0.60     # 高于此值为警告
_EFFICIENCY_CRITICAL = 0.45    # 高于此值为危险，低于则拒绝适配
_EFFICIENCY_FAILURE = 0.45     # 失效临界点


def _classify_efficiency(efficiency: float) -> SeverityLevel:
    """根据密封效率值判定风险等级。

    Args:
        efficiency: 当前密封效率（0-1）。

    Returns:
        对应的风险严重等级。
    """
    if efficiency >= _EFFICIENCY_SAFE:
        return SeverityLevel.SAFE
    elif efficiency >= _EFFICIENCY_WARNING:
        return SeverityLevel.WARNING
    elif efficiency >= _EFFICIENCY_CRITICAL:
        return SeverityLevel.CRITICAL
    else:
        return SeverityLevel.REJECT


def _compute_coupled_acceleration_factor(
    condition: CoupledCondition,
    params: FatigueDecayParam,
) -> float:
    """计算多参数联合加速衰减因子。

    核心逻辑：单独达标不代表联合达标。
    当振动和油压同时接近阈值上限时，耦合效应会产生
    超过单因素叠加的加速衰减。

    Args:
        condition: 联合工况条件。
        params: 疲劳衰减模型参数。

    Returns:
        综合加速因子（>=1.0，1.0表示无加速）。

    Raises:
        ValueError: 当阈值配置中 max_value 为零导致无法计算比率时。
    """
    vib_threshold = THRESHOLD_REGISTRY["vibration_amplitude"]
    pressure_threshold = THRESHOLD_REGISTRY["oil_pressure_fluctuation"]

    # 防御性校验：阈值上限不能为零
    if vib_threshold.max_value == 0 or pressure_threshold.max_value == 0:
        raise ValueError("振动或油压阈值上限配置为零，无法计算加速因子")

    # 计算各参数的阈值占比（归一化到0-1）
    vib_ratio = condition.vibration_amplitude / vib_threshold.max_value
    pressure_ratio = condition.oil_pressure / pressure_threshold.max_value

    # 单因素加速：超过阈值80%时开始加速
    vib_factor = 1.0
    if vib_ratio > 0.8:
        vib_factor = 1.0 + (vib_ratio - 0.8) * params.vibration_acceleration_factor

    pressure_factor = 1.0
    if pressure_ratio > 0.8:
        pressure_factor = 1.0 + (pressure_ratio - 0.8) * params.pressure_acceleration_factor

    # 多参数耦合效应：当两个参数同时超过80%阈值时，
    # 产生额外的交叉加速效应（非线性耦合项）
    coupling_factor = 1.0
    if vib_ratio > 0.8 and pressure_ratio > 0.8:
        # 耦合加速 = 两个越限比例的乘积 × 耦合系数
        coupling_factor = 1.0 + (vib_ratio - 0.8) * (pressure_ratio - 0.8) * 5.0

    # 温度修正因子：高温加速老化（Arrhenius近似）
    temp_threshold = THRESHOLD_REGISTRY["oil_temperature"]
    temp_factor = 1.0
    if temp_threshold.max_value > 0:
        temp_baseline = temp_threshold.max_value * 0.7
        if condition.oil_temperature > temp_baseline:
            # 温度每升高10℃，衰减速率翻倍
            temp_excess = condition.oil_temperature - temp_baseline
            # 钳位：防止极端高温导致因子爆炸（上限16倍，即超40℃）
            temp_excess = min(temp_excess, 40.0)
            temp_factor = math.pow(2.0, temp_excess / 10.0)

    # 综合加速因子 = 各单因素 × 耦合项
    total_factor = vib_factor * pressure_factor * coupling_factor * temp_factor

    return max(total_factor, 1.0)


def compute_decay_curve(
    service_years: int,
    condition: CoupledCondition,
    params: FatigueDecayParam = DEFAULT_FATIGUE_PARAMS,
) -> FatigueDecayReport:
    """计算密封性能疲劳衰减曲线。

    整合标准约束、实测工况阈值和长期疲劳衰减模型，
    逐年计算密封效率并生成完整的衰减报告。

    Args:
        service_years: 预计运行年限，必须 > 0。
        condition: 联合工况条件。
        params: 疲劳衰减模型参数，默认使用标准配置。

    Returns:
        疲劳衰减评估报告，包含衰减曲线和风险预测。

    Raises:
        ValueError: 当 service_years <= 0 时抛出。
    """
    if service_years <= 0:
        raise ValueError(f"运行年限必须为正整数: {service_years}")

    report = FatigueDecayReport(
        service_years=service_years,
        fatigue_params=params,
        coupled_condition=condition,
    )

    # 计算综合加速因子
    accel_factor = _compute_coupled_acceleration_factor(condition, params)

    # 判断是否存在多参数耦合风险
    vib_threshold = THRESHOLD_REGISTRY["vibration_amplitude"]
    pressure_threshold = THRESHOLD_REGISTRY["oil_pressure_fluctuation"]
    vib_ratio = condition.vibration_amplitude / vib_threshold.max_value
    pressure_ratio = condition.oil_pressure / pressure_threshold.max_value
    report.coupled_risk_flag = (vib_ratio > 0.8 and pressure_ratio > 0.8)

    # 逐年计算衰减曲线
    effective_decay_rate = params.annual_decay_rate * accel_factor

    for year in range(0, service_years + 1):
        if year == 0:
            efficiency = params.initial_seal_efficiency
        else:
            # 指数衰减模型：E(t) = E0 × e^(-λ×t)
            # 其中 λ = 基础衰减率 × 综合加速因子
            efficiency = params.initial_seal_efficiency * math.exp(
                -effective_decay_rate * year
            )

        # 效率下限钳位：物理意义上不低于0
        efficiency = max(efficiency, 0.0)

        severity = _classify_efficiency(efficiency)
        is_failure = efficiency < _EFFICIENCY_FAILURE

        point = DecayPoint(
            year=year,
            seal_efficiency=round(efficiency, 4),
            severity=severity,
            is_failure_point=is_failure,
        )
        report.decay_curve.append(point)

        # 记录首次失效年份
        if is_failure and report.predicted_failure_year is None:
            report.predicted_failure_year = year

    # 填充报告汇总字段
    final_point = report.decay_curve[-1]
    report.final_efficiency = final_point.seal_efficiency
    report.final_severity = final_point.severity
    report.recommendation = _generate_fatigue_recommendation(report)

    return report


def _generate_fatigue_recommendation(report: FatigueDecayReport) -> str:
    """根据疲劳衰减评估结果生成建议。

    Args:
        report: 疲劳衰减评估报告。

    Returns:
        中文评估建议文本。
    """
    parts = []

    # 耦合风险提示
    if report.coupled_risk_flag:
        parts.append(
            "⚠ 检测到多参数耦合风险：振动与油压同时接近阈值上限，"
            "衰减速率显著高于单因素叠加，建议重点监控。"
        )

    # 失效年份预测
    if report.predicted_failure_year is not None:
        if report.predicted_failure_year <= report.service_years:
            parts.append(
                f"预测第 {report.predicted_failure_year} 年密封效率将降至失效临界值以下，"
                f"建议在第 {max(1, report.predicted_failure_year - 2)} 年前安排预防性更换。"
            )
    else:
        parts.append(
            f"在 {report.service_years} 年运行周期内，密封效率保持在安全范围，"
            f"末期效率为 {report.final_efficiency:.1%}。"
        )

    # 风险等级建议
    severity_advice = {
        SeverityLevel.SAFE: "当前风险等级为安全，按常规周期检修即可。",
        SeverityLevel.WARNING: "当前风险等级为警告，建议缩短检修周期至标准的50%。",
        SeverityLevel.CRITICAL: "当前风险等级为危险，建议立即评估更换方案。",
        SeverityLevel.REJECT: "当前风险等级为拒绝适配，该阀门在此工况下不可继续使用。",
    }
    parts.append(severity_advice.get(report.final_severity, ""))

    return "\n".join(parts)
