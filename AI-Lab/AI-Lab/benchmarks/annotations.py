"""
技术对标分析 - 图注配置层
将图注、数据源脚注、置信度标注、方法论说明等评审必需信息参数化，
与图表生成逻辑解耦，方便 Designer 调整样式而不改业务代码。

满足 Arch 提出的评审可溯源标注要求：
1. 雷达图归一化取反逻辑必须在图注中明确标注
2. 所有图表底部必须附带数据源和置信度标注

遵循 Google Python Style Guide。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# 方案标签常量，与可视化模块共享
SCHEME_LABELS: List[str] = [
    "本方案（自动取样）",
    "人工取样",
    "现有在线监测",
]


@dataclass
class ChartAnnotation:
    """图表标注配置

    将图注、数据源脚注、置信度说明等评审必需信息参数化，
    与图表生成逻辑解耦。Designer 改样式只需调配置字段，
    不碰生成逻辑。

    Attributes:
        title: 图表主标题
        subtitle: 副标题（可选，用于补充说明）
        methodology_note: 方法论说明，如归一化取反逻辑的语义解释
        data_sources: 数据来源列表，每项对应一个方案的数据出处
        confidence_levels: 置信度列表，每项对应一个方案的数据可信度
        footnote_fontsize: 脚注字号，默认 8 号保持不喧宾夺主
        footnote_color: 脚注颜色，默认深灰 #555555
        show_timestamp: 是否在脚注中显示生成时间戳
    """
    title: str = ""
    subtitle: str = ""
    methodology_note: str = ""
    data_sources: List[str] = field(default_factory=list)
    confidence_levels: List[str] = field(default_factory=list)
    footnote_fontsize: int = 8
    footnote_color: str = "#555555"
    show_timestamp: bool = True

    def build_footnote_text(self) -> str:
        """构建完整的脚注文本

        自动拼接数据来源、置信度和方法论说明，
        格式化为评审友好的多行脚注。

        Returns:
            格式化后的脚注字符串，可直接传入 matplotlib figtext
        """
        lines: List[str] = []

        # 数据来源标注：逐方案列出，确保可溯源
        if self.data_sources:
            source_parts = []
            for i, (label, source) in enumerate(
                zip(SCHEME_LABELS, self.data_sources)
            ):
                confidence = (
                    self.confidence_levels[i]
                    if i < len(self.confidence_levels)
                    else "未标注"
                )
                source_parts.append(
                    f"{label}: {source} [置信度: {confidence}]"
                )
            lines.append("数据来源: " + " | ".join(source_parts))

        # 方法论说明：如雷达图归一化取反逻辑
        if self.methodology_note:
            lines.append(f"注: {self.methodology_note}")

        # 可选时间戳
        if self.show_timestamp:
            lines.append(
                f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        return "\n".join(lines)


# ============================================================
# 预置标注配置 —— 基于 BENCHMARK_DATASET 自动填充
# 评审所需的数据来源和置信度信息全部内嵌，开箱即用
# ============================================================
BAR_CHART_ANNOTATION = ChartAnnotation(
    title="技术对标分析 — 三类方案核心指标对比",
    data_sources=[
        "设计指标 + DL/T 596 参考限值",
        "GB/T 7595 附录 + 行业调研均值",
        "南瑞/许继产品白皮书公开参数",
    ],
    confidence_levels=["估算（待实测验证）", "文献", "文献"],
)

RADAR_CHART_ANNOTATION = ChartAnnotation(
    title="三类方案综合性能雷达图\n（面积越大越优）",
    methodology_note=(
        "各维度已归一化处理（公式: 1 - x/max），"
        "数值越大代表性能越优。原始指标（取样误差率、"
        "响应时延、年均运维成本）均为越低越好。"
    ),
    data_sources=[
        "设计指标 + DL/T 596 参考限值",
        "GB/T 7595 附录 + 行业调研均值",
        "南瑞/许继产品白皮书公开参数",
    ],
    confidence_levels=["估算（待实测验证）", "文献", "文献"],
)
