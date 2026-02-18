"""主入口模块：阀门机械适配决策评估系统。

提供命令行接口和编程接口，串联兼容性矩阵初筛、
疲劳衰减动态评估、多参数联合判定三层决策逻辑。

使用示例:
    python -m code.main
"""

from code.config.thresholds import (
    OperatingCondition,
    FatigueDecayParam,
    DEFAULT_FATIGUE_PARAMS,
)
from code.engine.compatibility_matrix import ValveSpec
from code.engine.fatigue_decay import CoupledCondition
from code.engine.decision_tree import run_decision_tree, DecisionReport


def create_sample_valve() -> ValveSpec:
    """创建示例阀门规格（用于演示和测试）。

    Returns:
        一个典型的有载分接开关阀门规格对象。
    """
    return ValveSpec(
        model="ZYV-200A",
        manufacturer="示例阀门制造厂",
        max_vibration=0.75,
        pressure_range=(0.10, 0.32),
        temp_range=(-20.0, 95.0),
        max_seal_pressure=1.8,
        rated_cycle_life=45000,
        seal_material="FKM",
    )


def create_sample_condition() -> CoupledCondition:
    """创建示例联合工况条件（用于演示和测试）。

    Returns:
        一个典型的现场运行工况条件对象。
    """
    return CoupledCondition(
        vibration_amplitude=0.65,
        oil_pressure=0.28,
        oil_temperature=78.0,
        annual_switching_cycles=12000,
    )


def run_evaluation(
    valve: ValveSpec,
    condition: CoupledCondition,
    service_years: int = 20,
    operating_condition: OperatingCondition = OperatingCondition.NORMAL,
    fatigue_params: FatigueDecayParam = DEFAULT_FATIGUE_PARAMS,
) -> DecisionReport:
    """执行完整的适配决策评估（编程接口）。

    Args:
        valve: 待评估的阀门规格。
        condition: 实际联合工况条件。
        service_years: 预计运行年限。
        operating_condition: 运行工况类型。
        fatigue_params: 疲劳衰减模型参数（可选）。

    Returns:
        完整的决策评估报告。
    """
    return run_decision_tree(
        valve=valve,
        coupled_condition=condition,
        service_years=service_years,
        condition=operating_condition,
        fatigue_params=fatigue_params,
    )


def print_decay_curve(report: DecisionReport) -> None:
    """打印衰减曲线的简要文本图表。

    Args:
        report: 决策评估报告（需包含疲劳衰减数据）。
    """
    if not report.fatigue_report:
        print("  （无疲劳衰减数据）")
        return

    print("\n── 密封效率衰减曲线 ──")
    print(f"  {'年份':>4s}  {'效率':>7s}  {'风险等级':<6s}  {'图示'}")
    print(f"  {'─' * 4}  {'─' * 7}  {'─' * 8}  {'─' * 30}")

    for point in report.fatigue_report.decay_curve:
        # 每隔一定间隔打印，避免输出过长
        if point.year % max(1, report.service_years // 10) != 0 and \
           point.year != report.service_years:
            continue

        bar_len = int(point.seal_efficiency * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        marker = " ← 失效" if point.is_failure_point and \
            point.year == report.fatigue_report.predicted_failure_year else ""

        print(
            f"  {point.year:>4d}  "
            f"{point.seal_efficiency:>6.1%}  "
            f"{point.severity.value:<8s}  "
            f"{bar}{marker}"
        )


def main() -> None:
    """主函数：运行示例评估并输出报告。"""
    print("=" * 60)
    print("  阀门机械适配决策评估系统 v1.0")
    print("  基于 GB/T 1094.7 / DL/T 1465 标准")
    print("=" * 60)

    # 创建示例数据
    valve = create_sample_valve()
    condition = create_sample_condition()

    # 场景一：正常工况，20年运行
    print("\n【场景一】正常工况 - 20年运行评估")
    print("-" * 50)
    report = run_evaluation(
        valve=valve,
        condition=condition,
        service_years=20,
        operating_condition=OperatingCondition.NORMAL,
    )
    print(report.summary)
    print_decay_curve(report)

    # 场景二：极端工况（振动和油压同时接近上限）
    print("\n\n【场景二】极端工况 - 多参数耦合场景")
    print("-" * 50)
    extreme_condition = CoupledCondition(
        vibration_amplitude=0.78,
        oil_pressure=0.34,
        oil_temperature=95.0,
        annual_switching_cycles=40000,
    )
    report_extreme = run_evaluation(
        valve=valve,
        condition=extreme_condition,
        service_years=20,
        operating_condition=OperatingCondition.EXTREME,
    )
    print(report_extreme.summary)
    print_decay_curve(report_extreme)

    # 场景三：不兼容阀门（振动耐受不足）
    print("\n\n【场景三】不兼容阀门 - 初筛拦截")
    print("-" * 50)
    weak_valve = ValveSpec(
        model="LV-100B",
        manufacturer="测试制造厂",
        max_vibration=1.2,
        pressure_range=(0.05, 0.50),
        temp_range=(-10.0, 120.0),
        max_seal_pressure=2.5,
        rated_cycle_life=60000,
        seal_material="EPDM",
    )
    report_weak = run_evaluation(
        valve=weak_valve,
        condition=condition,
        service_years=15,
    )
    print(report_weak.summary)


if __name__ == "__main__":
    main()
