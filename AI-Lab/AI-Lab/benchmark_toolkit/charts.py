"""
技术对标分析 - 可视化模块
生成柱状图和雷达图，支撑报告的技术对标章节。

功能：
1. 柱状图：三类方案在三个核心指标上的并排对比
2. 雷达图：归一化后的综合性能叠加展示
3. 所有图表底部自动附带数据源、置信度、方法论脚注
4. 每张图自动导出配套的 JSON 快照供 Tester 校验

依赖：matplotlib >= 3.7, numpy >= 1.24
输出：PNG/SVG 静态图片 + .annotation.json 快照

遵循 Google Python Style Guide。
"""
import math
from pathlib import Path
from typing import Optional, Sequence

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from benchmark_toolkit.annotations import (
    SCHEME_LABELS,
    ChartAnnotation,
)
from benchmark_toolkit.snapshot import export_annotation_snapshot

# ============================================================
# 全局样式配置
# 使用系统中文字体，确保图表中文标签正常渲染
# 配色方案参考电力行业报告常用的蓝灰色系，保持专业感
# ============================================================
matplotlib.rcParams["font.sans-serif"] = [
    "SimHei", "Microsoft YaHei", "PingFang SC",
]
matplotlib.rcParams["axes.unicode_minus"] = False

# 专业配色：本方案(深蓝)、人工取样(灰色)、在线监测(浅蓝)
SCHEME_COLORS = ["#1a5276", "#aab7b8", "#5dade2"]

# 默认输出目录
OUTPUT_DIR = Path("output/charts")


def _ensure_output_dir(output_dir: Path) -> None:
    """确保输出目录存在，不存在则递归创建

    Args:
        output_dir: 目标输出目录路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)


def _apply_footnote(
    fig: plt.Figure,
    annotation: Optional[ChartAnnotation],
) -> None:
    """将脚注标注应用到图表底部

    统一处理所有图表的脚注渲染逻辑，
    包括数据来源、置信度、方法论说明等评审必需信息。

    Args:
        fig: matplotlib 图表对象
        annotation: 图注配置，为 None 时跳过
    """
    if annotation is None:
        return

    footnote_text = annotation.build_footnote_text()
    if not footnote_text:
        return

    fig.text(
        0.5, -0.08,
        footnote_text,
        ha="center",
        va="top",
        fontsize=annotation.footnote_fontsize,
        color=annotation.footnote_color,
        style="italic",
        wrap=True,
    )


def generate_bar_chart(
    error_rates: Sequence[float],
    latencies: Sequence[float],
    costs: Sequence[float],
    annotation: Optional[ChartAnnotation] = None,
    output_filename: str = "benchmark_bar_chart.png",
    output_dir: Optional[Path] = None,
    dpi: int = 300,
) -> Path:
    """生成三维度并排柱状图

    将取样误差率、响应时延、年均运维成本三个核心指标
    以分组柱状图形式展示，直观对比三类方案的性能差异。
    底部自动附带数据源和置信度脚注。
    同时导出 JSON 快照供 Tester 校验。

    Args:
        error_rates: 三类方案的取样误差率 (%)
        latencies: 三类方案的响应时延 (分钟)
        costs: 三类方案的年均运维成本 (万元)
        annotation: 图注配置对象，控制脚注内容和样式
        output_filename: 输出文件名
        output_dir: 输出目录，默认为 OUTPUT_DIR
        dpi: 图片分辨率，默认 300 满足印刷要求

    Returns:
        生成的图片文件路径
    """
    target_dir = output_dir or OUTPUT_DIR
    _ensure_output_dir(target_dir)

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    # 使用 annotation 中的标题，若未配置则使用默认标题
    chart_title = (
        annotation.title if annotation and annotation.title
        else "技术对标分析 — 三类方案核心指标对比"
    )
    fig.suptitle(chart_title, fontsize=14, fontweight="bold", y=1.02)

    # 三个指标子图横向排列
    datasets = [
        ("取样误差率 (%)", error_rates),
        ("响应时延 (min)", latencies),
        ("年均运维成本 (万元)", costs),
    ]

    for ax, (ylabel, values) in zip(axes, datasets):
        x = np.arange(len(SCHEME_LABELS))
        bars = ax.bar(
            x, values, color=SCHEME_COLORS, width=0.5, edgecolor="white",
        )

        # 在柱顶标注具体数值，方便评审专家快速读数
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.02,
                f"{val}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(
            SCHEME_LABELS, fontsize=8, rotation=15, ha="right",
        )
        # 去掉顶部和右侧边框，保持简洁
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.tight_layout()

    # 应用评审可溯源脚注
    _apply_footnote(fig, annotation)

    output_path = target_dir / output_filename
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 自动导出 JSON 快照供 Tester 校验
    if annotation is not None:
        export_annotation_snapshot(annotation, output_path)

    return output_path


def generate_radar_chart(
    error_rates: Sequence[float],
    latencies: Sequence[float],
    costs: Sequence[float],
    annotation: Optional[ChartAnnotation] = None,
    output_filename: str = "benchmark_radar_chart.png",
    output_dir: Optional[Path] = None,
    dpi: int = 300,
) -> Path:
    """生成归一化雷达图（综合优势对比）

    将三个维度归一化到 [0, 1] 并取反后，以雷达图叠加展示。
    归一化取反逻辑：原始值越小越好 → 归一化后越大越优。
    底部自动附带归一化方法论说明和数据源脚注。

    Args:
        error_rates: 三类方案的取样误差率 (%)
        latencies: 三类方案的响应时延 (分钟)
        costs: 三类方案的年均运维成本 (万元)
        annotation: 图注配置对象
        output_filename: 输出文件名
        output_dir: 输出目录，默认为 OUTPUT_DIR
        dpi: 图片分辨率

    Returns:
        生成的图片文件路径
    """
    target_dir = output_dir or OUTPUT_DIR
    _ensure_output_dir(target_dir)

    dimensions = ["取样精度", "响应速度", "运维经济性"]
    raw_data = np.array([error_rates, latencies, costs]).T  # shape: (3, 3)

    # 归一化并取反：原始值越小越好 → 归一化后越大越好
    max_vals = raw_data.max(axis=0)
    # 避免除零，对最大值为 0 的维度做保护
    safe_max = np.where(max_vals == 0, 1, max_vals)
    normalized = 1 - (raw_data / safe_max)

    # 雷达图角度计算
    num_dims = len(dimensions)
    angles = [n / float(num_dims) * 2 * math.pi for n in range(num_dims)]
    angles += angles[:1]  # 闭合多边形

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    chart_title = (
        annotation.title if annotation and annotation.title
        else "三类方案综合性能雷达图\n（面积越大越优）"
    )
    ax.set_title(chart_title, fontsize=13, fontweight="bold", pad=20)

    for i, (label, color) in enumerate(zip(SCHEME_LABELS, SCHEME_COLORS)):
        values = normalized[i].tolist()
        values += values[:1]  # 闭合
        ax.plot(angles, values, "o-", linewidth=2, label=label, color=color)
        ax.fill(angles, values, alpha=0.15, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, fontsize=11)
    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=9)

    # 应用评审可溯源脚注（含归一化方法论说明）
    _apply_footnote(fig, annotation)

    output_path = target_dir / output_filename
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # 自动导出 JSON 快照供 Tester 校验
    if annotation is not None:
        export_annotation_snapshot(annotation, output_path)

    return output_path
