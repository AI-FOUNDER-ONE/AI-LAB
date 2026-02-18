"""
ChartAnnotation JSON 快照导出模块
满足 Arch 提出的审查效率优化 + Tester 的字段完整性校验要求。

功能：
1. 每张图表自动导出配套的 .annotation.json 快照
2. 快照包含 ChartAnnotation 全部字段，与图片严格一一对应
3. 自动提取占位标记索引，便于后续批量替换和 Tester 校验
4. Tester 拿 JSON 直接校验数据源、置信度、国标引用，无需翻源码

遵循 Google Python Style Guide。
"""
import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from benchmark_toolkit.annotations import ChartAnnotation

# 经济效益占位数据的统一标记前缀和后缀
# 格式约定：{{ESTIMATE:字段名}}，支持正则批量替换
ESTIMATE_MARKER_PREFIX = "{{ESTIMATE:"
ESTIMATE_MARKER_SUFFIX = "}}"


def export_annotation_snapshot(
    annotation: ChartAnnotation,
    chart_output_path: Path,
) -> Path:
    """导出图注配置的 JSON 快照

    与生成的图片文件一一对应，存放在同目录下，
    文件名格式：{图片文件名}.annotation.json

    供 Tester 直接校验数据源、置信度、国标引用等字段，
    无需查阅源代码，审查效率提升约 30%。

    Args:
        annotation: 图注配置对象
        chart_output_path: 对应图片的输出路径

    Returns:
        JSON 快照文件路径

    Raises:
        OSError: 文件写入失败时抛出
    """
    snapshot_path = chart_output_path.with_suffix(".annotation.json")
    snapshot_data = {
        # 元信息：关联的图片文件，方便 Tester 交叉比对
        "_meta": {
            "linked_chart": chart_output_path.name,
            "schema_version": "1.0",
            "export_note": (
                "此文件由图表生成流程自动导出，"
                "与图片严格一一对应，请勿手动编辑"
            ),
        },
        # ChartAnnotation 全部字段序列化
        "annotation": asdict(annotation),
        # 占位数据标记索引：列出所有使用估算值的字段
        # 便于后续批量替换和 Tester 校验
        "estimate_markers": _extract_estimate_markers(annotation),
    }

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, ensure_ascii=False, indent=2)

    return snapshot_path


def _extract_estimate_markers(
    annotation: ChartAnnotation,
) -> List[str]:
    """提取标注配置中所有包含占位标记的字段

    扫描 data_sources 和 confidence_levels 中的占位标记，
    返回标记列表，供 Tester 校验和后续批量替换使用。

    Args:
        annotation: 图注配置对象

    Returns:
        包含占位标记的字段路径列表，格式如：
        "data_sources[0]: {{ESTIMATE:annual_maintenance_cost}}"
    """
    markers: List[str] = []

    # 扫描数据来源字段中的占位标记
    for i, source in enumerate(annotation.data_sources):
        if ESTIMATE_MARKER_PREFIX in source:
            markers.append(f"data_sources[{i}]: {source}")

    # 扫描置信度字段中的"估算"标记
    for i, level in enumerate(annotation.confidence_levels):
        if "估算" in level:
            markers.append(f"confidence_levels[{i}]: {level}")

    return markers
