"""
matplotlib_design_tool.py - 设计图生成工具
==========================================
供 Designer（设计师）使用，基于 matplotlib 生成设计示意图。
支持组件布局图、色彩方案图、用户流程图等。

安全性审计:
  ✅ 文件写入限制在 data/generated_docs/ 目录
  ✅ 使用 Agg 后端，无需 GUI 环境
  ✅ 输入验证防止注入
"""

import os
import json
import time
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class DesignInput(BaseModel):
    """MatplotlibDesignTool 的输入参数模型。"""
    design_json: str = Field(
        ...,
        description=(
            "设计描述的 JSON 字符串。格式示例：\n"
            '{\n'
            '  "title": "系统架构布局",\n'
            '  "type": "layout",\n'
            '  "components": [\n'
            '    {"name": "前端 UI", "x": 0.5, "y": 0.9, "color": "#4FC3F7", "width": 0.8},\n'
            '    {"name": "API 网关", "x": 0.5, "y": 0.7, "color": "#81C784", "width": 0.6},\n'
            '    {"name": "数据库", "x": 0.5, "y": 0.3, "color": "#FFB74D", "width": 0.4}\n'
            '  ],\n'
            '  "connections": [\n'
            '    {"from": "前端 UI", "to": "API 网关"},\n'
            '    {"from": "API 网关", "to": "数据库"}\n'
            '  ]\n'
            '}'
        )
    )
    filename: str = Field(
        default="",
        description="可选的输出文件名（不含扩展名）。留空则自动生成。"
    )


class MatplotlibDesignTool(BaseTool):
    """设计图生成工具。

    基于 matplotlib 将设计描述生成为 PNG 示意图。
    适用于：组件布局、系统拓扑、色彩方案、流程示意等。

    使用场景:
      - 系统组件布局图
      - 用户交互流程图
      - 色彩/主题方案预览
      - 工业设计外观草图
    """
    name: str = "design_diagram_generator"
    description: str = (
        "根据 JSON 描述生成设计示意图（PNG）。"
        "输入包含组件名称、位置、颜色、连接关系的 JSON，"
        "输出组件布局图或系统拓扑图。"
    )
    args_schema: Type[BaseModel] = DesignInput

    def _run(self, design_json: str, filename: str = "") -> str:
        """执行设计图生成。

        Args:
            design_json: 设计描述的 JSON 字符串
            filename: 可选的输出文件名

        Returns:
            生成文件的路径信息
        """
        # ---------- 1. 解析输入 ----------
        try:
            design = json.loads(design_json)
        except json.JSONDecodeError as e:
            return f"❌ JSON 解析失败: {e}。请确保输入是合法的 JSON 格式。"

        # ---------- 2. 确定输出路径 ----------
        from config import GENERATED_DOCS_DIR

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"design_{timestamp}"

        filename = filename.replace(os.sep, "_").replace("/", "_")
        output_path = os.path.join(GENERATED_DOCS_DIR, f"{filename}.png")

        # ---------- 3. 使用 matplotlib 绘制 ----------
        try:
            import matplotlib
            matplotlib.use("Agg")  # 无 GUI 后端
            import matplotlib.pyplot as plt
            import matplotlib.patches as patches

            fig, ax = plt.subplots(1, 1, figsize=(12, 8))
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_aspect('equal')
            ax.axis('off')

            title = design.get("title", "设计示意图")
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20,
                         fontfamily='Microsoft YaHei')

            # 绘制组件
            components = design.get("components", [])
            comp_positions = {}  # 记录组件中心位置用于连线

            for comp in components:
                name = comp.get("name", "未命名")
                x = float(comp.get("x", 0.5))
                y = float(comp.get("y", 0.5))
                color = comp.get("color", "#64B5F6")
                width = float(comp.get("width", 0.3))
                height = float(comp.get("height", 0.08))

                # 绘制圆角矩形
                rect = patches.FancyBboxPatch(
                    (x - width / 2, y - height / 2), width, height,
                    boxstyle="round,pad=0.01",
                    facecolor=color, edgecolor="#333333",
                    linewidth=1.5, alpha=0.85
                )
                ax.add_patch(rect)

                # 组件名称标签
                ax.text(x, y, name, ha='center', va='center',
                        fontsize=11, fontweight='bold', color='white',
                        fontfamily='Microsoft YaHei')

                comp_positions[name] = (x, y)

            # 绘制连接线
            connections = design.get("connections", [])
            for conn in connections:
                from_name = conn.get("from", "")
                to_name = conn.get("to", "")

                if from_name in comp_positions and to_name in comp_positions:
                    x1, y1 = comp_positions[from_name]
                    x2, y2 = comp_positions[to_name]

                    ax.annotate(
                        "", xy=(x2, y2), xytext=(x1, y1),
                        arrowprops=dict(
                            arrowstyle="->", color="#555555",
                            lw=1.5, connectionstyle="arc3,rad=0.1"
                        )
                    )

            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight',
                        facecolor='white', edgecolor='none')
            plt.close(fig)

            return f"✅ 设计示意图已生成: {output_path}"

        except ImportError:
            return (
                "❌ matplotlib 未安装。请运行: pip install matplotlib\n"
                f"设计数据已解析成功，包含 {len(design.get('components', []))} 个组件。"
            )
        except Exception as e:
            return f"❌ 图表生成失败: {e}"
