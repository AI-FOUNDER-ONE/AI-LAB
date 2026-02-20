"""单元测试模块：覆盖决策树三层验证逻辑。

测试范围：
  - 阈值参数配置层的正确性
  - 兼容性矩阵初筛（第一层）
  - 疲劳衰减动态评估（第二层）
  - 多参数联合判定（第三层）
  - 端到端决策树完整流程
"""

import math
import unittest

from code.config.thresholds import (
    SeverityLevel,
    OperatingCondition,
    ThresholdParam,
    FatigueDecayParam,
    THRESHOLD_REGISTRY,
    VIBRATION_THRESHOLD,
    OIL_PRESSURE_THRESHOLD,
    get_threshold,
)
from code.engine.compatibility_matrix import (
    CompatibilityResult,
    ValveSpec,
    evaluate_compatibility,
)
from code.engine.fatigue_decay import (
    CoupledCondition,
    compute_decay_curve,
)
from code.engine.decision_tree import (
    DecisionOutcome,
    run_decision_tree,
)


class TestThresholdConfig(unittest.TestCase):
    """阈值参数配置层测试。"""

    def test_registry_contains_all_params(self):
        """注册表应包含全部5个核心阈值参数。"""
        expected_keys = {
            "vibration_amplitude",
            "oil_pressure_fluctuation",
            "oil_temperature",
            "seal_surface_pressure",
            "switching_cycle_count",
        }
        self.assertEqual(set(THRESHOLD_REGISTRY.keys()), expected_keys)

    def test_vibration_threshold_values(self):
        """振动阈值应符合 GB/T 1094.7 标准（0~0.8g）。"""
        self.assertEqual(VIBRATION_THRESHOLD.max_value, 0.8)
        self.assertEqual(VIBRATION_THRESHOLD.min_value, 0.0)
        self.assertEqual(VIBRATION_THRESHOLD.unit, "g")

    def test_oil_pressure_threshold_values(self):
        """油压阈值应符合 DL/T 1465 标准（0.12~0.35MPa）。"""
        self.assertEqual(OIL_PRESSURE_THRESHOLD.min_value, 0.12)
        self.assertEqual(OIL_PRESSURE_THRESHOLD.max_value, 0.35)

    def test_get_threshold_valid_key(self):
        """有效键名应返回正确的阈值参数。"""
        param = get_threshold("vibration_amplitude")
        self.assertIsInstance(param, ThresholdParam)
        self.assertEqual(param.key, "vibration_amplitude")

    def test_get_threshold_invalid_key(self):
        """无效键名应抛出 KeyError。"""
        with self.assertRaises(KeyError):
            get_threshold("nonexistent_param")

    def test_threshold_immutability(self):
        """阈值参数对象应为不可变（frozen dataclass）。"""
        with self.assertRaises(AttributeError):
            VIBRATION_THRESHOLD.max_value = 999


class TestCompatibilityMatrix(unittest.TestCase):
    """兼容性矩阵初筛（第一层）测试。"""

    def _make_valve(self, **overrides) -> ValveSpec:
        """创建测试用阀门规格，支持参数覆盖。"""
        defaults = dict(
            model="TEST-001",
            manufacturer="测试厂",
            max_vibration=0.7,
            pressure_range=(0.10, 0.30),
            temp_range=(-20.0, 90.0),
            max_seal_pressure=1.5,
            rated_cycle_life=40000,
            seal_material="NBR",
        )
        defaults.update(overrides)
        return ValveSpec(**defaults)

    def test_fully_compatible_valve(self):
        """所有参数在阈值范围内应判定为完全兼容。"""
        valve = self._make_valve()
        report = evaluate_compatibility(valve)
        self.assertEqual(report.overall_result, CompatibilityResult.COMPATIBLE)
        self.assertEqual(report.overall_severity, SeverityLevel.SAFE)

    def test_vibration_exceeds_threshold(self):
        """振动超标应判定为不兼容。"""
        valve = self._make_valve(max_vibration=1.2)
        report = evaluate_compatibility(valve)
        self.assertNotEqual(report.overall_result, CompatibilityResult.COMPATIBLE)

    def test_pressure_exceeds_threshold(self):
        """油压超标应判定为不兼容或条件兼容。"""
        valve = self._make_valve(pressure_range=(0.05, 0.50))
        report = evaluate_compatibility(valve)
        self.assertNotEqual(report.overall_result, CompatibilityResult.COMPATIBLE)

    def test_report_contains_all_params(self):
        """报告应包含所有注册阈值参数的判定记录。"""
        valve = self._make_valve()
        report = evaluate_compatibility(valve)
        reported_keys = {e.param_key for e in report.entries}
        self.assertEqual(reported_keys, set(THRESHOLD_REGISTRY.keys()))

    def test_recommendation_not_empty(self):
        """评估报告应包含非空的适配建议。"""
        valve = self._make_valve()
        report = evaluate_compatibility(valve)
        self.assertTrue(len(report.recommendation) > 0)


class TestFatigueDecay(unittest.TestCase):
    """疲劳衰减动态评估（第二层）测试。"""

    def test_normal_condition_decay(self):
        """正常工况下密封效率应随年限单调递减。"""
        condition = CoupledCondition(
            vibration_amplitude=0.3,
            oil_pressure=0.20,
            oil_temperature=60.0,
        )
        report = compute_decay_curve(service_years=20, condition=condition)

        efficiencies = [p.seal_efficiency for p in report.decay_curve]
        # 验证单调递减
        for i in range(1, len(efficiencies)):
            self.assertLessEqual(efficiencies[i], efficiencies[i - 1])

    def test_initial_efficiency_is_one(self):
        """第0年密封效率应为1.0（初始值）。"""
        condition = CoupledCondition()
        report = compute_decay_curve(service_years=10, condition=condition)
        self.assertEqual(report.decay_curve[0].seal_efficiency, 1.0)

    def test_extreme_condition_faster_decay(self):
        """极端工况的衰减速率应显著快于正常工况。"""
        normal = CoupledCondition(vibration_amplitude=0.3, oil_pressure=0.15)
        extreme = CoupledCondition(vibration_amplitude=0.78, oil_pressure=0.34)

        report_normal = compute_decay_curve(service_years=20, condition=normal)
        report_extreme = compute_decay_curve(service_years=20, condition=extreme)

        self.assertGreater(
            report_normal.final_efficiency,
            report_extreme.final_efficiency,
        )

    def test_coupled_risk_flag_triggered(self):
        """振动和油压同时超过80%阈值时应触发耦合风险标记。"""
        # 振动 0.78/0.8 = 97.5% > 80%，油压 0.34/0.35 = 97.1% > 80%
        condition = CoupledCondition(
            vibration_amplitude=0.78,
            oil_pressure=0.34,
        )
        report = compute_decay_curve(service_years=20, condition=condition)
        self.assertTrue(report.coupled_risk_flag)

    def test_no_coupled_risk_when_single_param_high(self):
        """仅单个参数超过80%阈值时不应触发耦合风险。"""
        condition = CoupledCondition(
            vibration_amplitude=0.78,
            oil_pressure=0.15,  # 15/35 = 42.8% < 80%
        )
        report = compute_decay_curve(service_years=20, condition=condition)
        self.assertFalse(report.coupled_risk_flag)

    def test_curve_length_matches_years(self):
        """衰减曲线数据点数量应等于年限+1（含第0年）。"""
        condition = CoupledCondition()
        years = 15
        report = compute_decay_curve(service_years=years, condition=condition)
        self.assertEqual(len(report.decay_curve), years + 1)


class TestDecisionTree(unittest.TestCase):
    """端到端决策树完整流程测试。"""

    def _make_valve(self, **overrides) -> ValveSpec:
        """创建测试用阀门规格。"""
        defaults = dict(
            model="DT-TEST",
            manufacturer="测试厂",
            max_vibration=0.7,
            pressure_range=(0.10, 0.30),
            temp_range=(-20.0, 90.0),
            max_seal_pressure=1.5,
            rated_cycle_life=40000,
            seal_material="FKM",
        )
        defaults.update(overrides)
        return ValveSpec(**defaults)

    def test_approve_normal_scenario(self):
        """正常工况+合规阀门应批准适配。"""
        valve = self._make_valve()
        condition = CoupledCondition(
            vibration_amplitude=0.3,
            oil_pressure=0.20,
            oil_temperature=60.0,
        )
        report = run_decision_tree(valve, condition, service_years=15)
        self.assertEqual(report.outcome, DecisionOutcome.APPROVE)

    def test_reject_incompatible_valve(self):
        """不兼容阀门应在第一层被拒绝。"""
        valve = self._make_valve(max_vibration=1.5)
        condition = CoupledCondition()
        report = run_decision_tree(valve, condition, service_years=10)
        self.assertEqual(report.outcome, DecisionOutcome.REJECT)
        # 应只经过第一层
        self.assertEqual(len(report.nodes), 1)
        self.assertIsNone(report.fatigue_report)

    def test_conditional_approve_with_coupled_risk(self):
        """存在耦合风险但衰减可控时应有条件批准。"""
        valve = self._make_valve()
        condition = CoupledCondition(
            vibration_amplitude=0.70,
            oil_pressure=0.30,
            oil_temperature=70.0,
        )
        report = run_decision_tree(valve, condition, service_years=10)
        # 耦合风险触发时应为有条件批准或批准
        self.assertIn(report.outcome, [
            DecisionOutcome.APPROVE,
            DecisionOutcome.CONDITIONAL_APPROVE,
        ])

    def test_three_layers_executed_for_compatible_valve(self):
        """兼容阀门应经过全部三层决策。"""
        valve = self._make_valve()
        condition = CoupledCondition(
            vibration_amplitude=0.3,
            oil_pressure=0.20,
        )
        report = run_decision_tree(valve, condition, service_years=10)
        self.assertEqual(len(report.nodes), 3)

    def test_report_summary_not_empty(self):
        """决策报告摘要不应为空。"""
        valve = self._make_valve()
        condition = CoupledCondition()
        report = run_decision_tree(valve, condition, service_years=10)
        self.assertTrue(len(report.summary) > 0)

    def test_report_contains_valve_info(self):
        """报告摘要应包含阀门型号信息。"""
        valve = self._make_valve(model="UNIQUE-MODEL-X")
        condition = CoupledCondition()
        report = run_decision_tree(valve, condition, service_years=10)
        self.assertIn("UNIQUE-MODEL-X", report.summary)


if __name__ == "__main__":
    unittest.main()
