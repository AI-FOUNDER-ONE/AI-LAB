"""静态决策树引擎模块。

实现分层验证逻辑：
  第一层：基于标准阈值的兼容性矩阵初筛
  第二层：结合长期疲劳衰减数据的动态调整
  联合判定：多参数耦合场景的组合校验

决策逻辑只引用参数键名，不硬编码数值，
实现逻辑与参数的完全解耦。

修复内容：
  - 第三层联合判定中硬编码的阈值替换为从配置层读取
  - 增加 service_years 输入校验
  - 优化 _aggregate_decision 逻辑覆盖所有分支
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from code.config.thresholds import (
    SeverityLevel,
    OperatingCondition,
    DEFAULT_FATIGUE_PARAMS,
    FatigueDecayParam,
    THRESHOLD_REGISTRY,
)
from code.engine.compatibility_matrix import (
    CompatibilityResult,
    CompatibilityReport,
    ValveSpec,
    evaluate_compatibility,
)
from code.engine.fatigue_decay import (
    CoupledCondition,
    FatigueDecayReport,
    compute_decay_curve,
)


class DecisionOutcome(Enum):
    """决策树最终判定结果。"""
    APPROVE = "批准适配"
    CONDITIONAL_APPROVE = "有条件批准"
    REVIEW_REQUIRED = "需人工复核"
    REJECT = "拒绝适配"


@dataclass
class DecisionNode:
    """决策树节点记录。

    Attributes:
        layer: 所属决策层级（1=初筛, 2=疲劳衰减, 3=联合判定）。
        node_name: 节点名称。
        input_summary: 输入摘要。
        result_summary: 判定结果摘要。
        passed: 是否通过该节点。
    """
    layer: int
    node_name: str
    input_summary: str
    result_summary: str
    passed: bool


@dataclass
class DecisionReport:
    """决策树完整评估报告。

    Attributes:
        valve: 被评估的阀门规格。
        condition: 运行工况。
        service_years: 预计运行年限。
        nodes: 决策路径中经过的所有节点。
        compatibility_report: 第一层兼容性评估报告。
        fatigue_report: 第二层疲劳衰减评估报告。
        outcome: 最终判定结果。
        risk_level: 综合风险等级。
        summary: 综合评估摘要。
    """
    valve: ValveSpec
    condition: OperatingCondition
    service_years: int
    nodes: List[DecisionNode] = field(default_factory=list)
    compatibility_report: Optional[CompatibilityReport] = None
    fatigue_report: Optional[FatigueDecayReport] = None
    outcome: DecisionOutcome = DecisionOutcome.REVIEW_REQUIRED
    risk_level: SeverityLevel = SeverityLevel.SAFE
    summary: str = ""


def run_decision_tree(
    valve: ValveSpec,
    coupled_condition: CoupledCondition,
    service_years: int = 20,
    condition: OperatingCondition = OperatingCondition.NORMAL,
    fatigue_params: FatigueDecayParam = DEFAULT_FATIGUE_PARAMS,
) -> DecisionReport:
    """执行完整的分层决策树评估。

    决策流程：
      1. 第一层 - 兼容性矩阵初筛（标准阈值校验）
      2. 第二层 - 疲劳衰减动态评估（长期运行预测）
      3. 第三层 - 多参数联合判定（耦合风险校验）
      4. 综合裁决 - 汇总三层结果给出最终判定

    Args:
        valve: 待评估的阀门规格。
        coupled_condition: 实际联合工况条件。
        service_years: 预计运行年限，必须 > 0。
        condition: 运行工况类型。
        fatigue_params: 疲劳衰减模型参数。

    Returns:
        完整的决策评估报告。

    Raises:
        ValueError: 当 service_years <= 0 时抛出。
    """
    if service_years <= 0:
        raise ValueError(f"运行年限必须为正整数: {service_years}")

    report = DecisionReport(
        valve=valve,
        condition=condition,
        service_years=service_years,
    )

    # ========== 第一层：兼容性矩阵初筛 ==========
    compat_report = evaluate_compatibility(valve, condition)
    report.compatibility_report = compat_report

    layer1_passed = compat_report.overall_result != CompatibilityResult.INCOMPATIBLE
    report.nodes.append(DecisionNode(
        layer=1,
        node_name="兼容性矩阵初筛",
        input_summary=f"阀门型号={valve.model}, 工况={condition.value}",
        result_summary=(
            f"判定={compat_report.overall_result.value}, "
            f"风险={compat_report.overall_severity.value}"
        ),
        passed=layer1_passed,
    ))

    # 第一层不通过则直接拒绝，不进入后续层级
    if not layer1_passed:
        report.outcome = DecisionOutcome.REJECT
        report.risk_level = compat_report.overall_severity
        report.summary = _build_summary(report)
        return report

    # ========== 第二层：疲劳衰减动态评估 ==========
    fatigue_report = compute_decay_curve(
        service_years=service_years,
        condition=coupled_condition,
        params=fatigue_params,
    )
    report.fatigue_report = fatigue_report

    # 判定标准：目标年限内密封效率不低于警告阈值
    layer2_passed = fatigue_report.final_severity in (
        SeverityLevel.SAFE, SeverityLevel.WARNING
    )
    report.nodes.append(DecisionNode(
        layer=2,
        node_name="疲劳衰减动态评估",
        input_summary=(
            f"运行年限={service_years}年, "
            f"振动={coupled_condition.vibration_amplitude}g, "
            f"油压={coupled_condition.oil_pressure}MPa"
        ),
        result_summary=(
            f"末期效率={fatigue_report.final_efficiency:.1%}, "
            f"预测失效年={fatigue_report.predicted_failure_year or '无'}"
        ),
        passed=layer2_passed,
    ))

    # ========== 第三层：多参数联合判定 ==========
    # 从配置层读取阈值上限，不硬编码
    vib_max = THRESHOLD_REGISTRY["vibration_amplitude"].max_value
    pressure_max = THRESHOLD_REGISTRY["oil_pressure_fluctuation"].max_value

    layer3_passed = not fatigue_report.coupled_risk_flag
    coupled_note = "未检测到耦合风险" if layer3_passed else "振动与油压耦合风险已触发"

    # 计算占比时使用配置层的阈值
    vib_pct = (coupled_condition.vibration_amplitude / vib_max * 100
               if vib_max > 0 else 0)
    pressure_pct = (coupled_condition.oil_pressure / pressure_max * 100
                    if pressure_max > 0 else 0)

    report.nodes.append(DecisionNode(
        layer=3,
        node_name="多参数联合判定",
        input_summary=(
            f"振动占比={vib_pct:.0f}%, "
            f"油压占比={pressure_pct:.0f}%"
        ),
        result_summary=coupled_note,
        passed=layer3_passed,
    ))

    # ========== 综合裁决 ==========
    report.outcome, report.risk_level = _aggregate_decision(
        layer1_passed, layer2_passed, layer3_passed,
        compat_report, fatigue_report,
    )
    report.summary = _build_summary(report)

    return report


def _aggregate_decision(
    layer1_ok: bool,
    layer2_ok: bool,
    layer3_ok: bool,
    compat: CompatibilityReport,
    fatigue: FatigueDecayReport,
) -> Tuple[DecisionOutcome, SeverityLevel]:
    """汇总三层判定结果，给出最终裁决。

    决策矩阵：
      - 三层全通过 → 批准适配
      - 第一层通过 + 第二层通过 + 第三层耦合风险 → 有条件批准
      - 第一层通过 + 第二层不通过（衰减严重） → 需人工复核或拒绝
      - 第一层不通过 → 拒绝适配（已在上游拦截）

    Args:
        layer1_ok: 第一层是否通过。
        layer2_ok: 第二层是否通过。
        layer3_ok: 第三层是否通过。
        compat: 兼容性报告。
        fatigue: 疲劳衰减报告。

    Returns:
        (决策结果, 风险等级) 元组。
    """
    # 情况1：三层全部通过
    if layer1_ok and layer2_ok and layer3_ok:
        return DecisionOutcome.APPROVE, SeverityLevel.SAFE

    # 情况2：兼容且衰减可控，但存在耦合风险
    if layer1_ok and layer2_ok and not layer3_ok:
        return DecisionOutcome.CONDITIONAL_APPROVE, SeverityLevel.WARNING

    # 情况3：初筛通过但长期衰减不可接受
    if layer1_ok and not layer2_ok:
        if fatigue.final_severity == SeverityLevel.REJECT:
            return DecisionOutcome.REJECT, SeverityLevel.REJECT
        return DecisionOutcome.REVIEW_REQUIRED, SeverityLevel.CRITICAL

    # 情况4：第一层未通过（理论上不会到达此处，已在上游拦截）
    return DecisionOutcome.REJECT, SeverityLevel.REJECT


def _build_summary(report: DecisionReport) -> str:
    """构建综合评估摘要文本。

    Args:
        report: 完整决策报告。

    Returns:
        中文综合评估摘要。
    """
    lines = [
        f"═══ 适配决策评估报告 ═══",
        f"阀门型号: {report.valve.model} ({report.valve.manufacturer})",
        f"运行工况: {report.condition.value}",
        f"评估年限: {report.service_years} 年",
        f"",
        f"── 决策路径 ──",
    ]

    for node in report.nodes:
        status = "✓ 通过" if node.passed else "✗ 未通过"
        lines.append(f"  第{node.layer}层 [{node.node_name}] {status}")
        lines.append(f"    输入: {node.input_summary}")
        lines.append(f"    结果: {node.result_summary}")

    lines.extend([
        f"",
        f"── 最终裁决 ──",
        f"判定结果: {report.outcome.value}",
        f"风险等级: {report.risk_level.value}",
    ])

    # 附加疲劳衰减建议
    if report.fatigue_report and report.fatigue_report.recommendation:
        lines.extend([
            f"",
            f"── 疲劳衰减评估 ──",
            report.fatigue_report.recommendation,
        ])

    # 附加兼容性建议
    if report.compatibility_report:
        lines.extend([
            f"",
            f"── 兼容性评估 ──",
            report.compatibility_report.recommendation,
        ])

    return "\n".join(lines)
