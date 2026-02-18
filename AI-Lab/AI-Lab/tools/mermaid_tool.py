"""
mermaid_tool.py - Mermaid 图表生成工具
======================================
供 Arch（架构师）使用，将 Mermaid DSL 代码保存为 .mmd 文件，
并尝试调用 mmdc CLI 渲染为 PNG 图片。

安全性审计:
  ✅ 文件写入限制在 data/generated_docs/ 目录
  ✅ 不执行任意命令，仅调用 mmdc
  ✅ 异常处理完善，mmdc 不可用时优雅降级
"""

import os
import time
import subprocess
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class MermaidInput(BaseModel):
    """MermaidTool 的输入参数模型。"""
    code: str = Field(
        ...,
        description=(
            "Mermaid DSL 代码，例如：\n"
            "graph TD\n"
            "    A[用户请求] --> B[CKO 分析]\n"
            "    B --> C[PM 主持]"
        )
    )
    filename: str = Field(
        default="",
        description="可选的输出文件名（不含扩展名）。留空则自动生成时间戳名称。"
    )


class MermaidTool(BaseTool):
    """Mermaid 图表生成工具。

    将 Mermaid DSL 代码保存为 .mmd 文件，若系统安装了
    mermaid-cli (mmdc) 则自动渲染为 PNG 图片。

    使用场景:
      - 架构图（graph TD / graph LR）
      - 序列图（sequenceDiagram）
      - 甘特图（gantt）
      - 流程图（flowchart）
    """
    name: str = "mermaid_chart_generator"
    description: str = (
        "将 Mermaid DSL 代码生成为图表文件（.mmd + .png）。"
        "输入 Mermaid 语法代码，输出保存路径。"
        "支持 graph/flowchart/sequenceDiagram/gantt 等所有 Mermaid 图表类型。"
    )
    args_schema: Type[BaseModel] = MermaidInput

    def _run(self, code: str, filename: str = "") -> str:
        """执行 Mermaid 图表生成。

        Args:
            code: Mermaid DSL 代码
            filename: 可选的输出文件名（不含扩展名）

        Returns:
            生成文件的路径信息和状态
        """
        # ---------- 1. 确定输出路径 ----------
        from config import GENERATED_DOCS_DIR

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"mermaid_{timestamp}"

        # 安全检查：移除路径分隔符防止目录遍历
        filename = filename.replace(os.sep, "_").replace("/", "_")

        mmd_path = os.path.join(GENERATED_DOCS_DIR, f"{filename}.mmd")
        png_path = os.path.join(GENERATED_DOCS_DIR, f"{filename}.png")

        # ---------- 2. 保存 .mmd 源文件 ----------
        try:
            with open(mmd_path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            return f"❌ 保存 Mermaid 文件失败: {e}"

        # ---------- 3. 尝试渲染为 PNG ----------
        png_status = "（mmdc 未安装，仅保存了 .mmd 源文件）"
        try:
            # 检查 mmdc 是否可用
            result = subprocess.run(
                ["mmdc", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # 渲染 PNG
                render_result = subprocess.run(
                    ["mmdc", "-i", mmd_path, "-o", png_path, "-b", "white"],
                    capture_output=True, text=True, timeout=30
                )
                if render_result.returncode == 0 and os.path.exists(png_path):
                    png_status = f"✅ PNG 已渲染: {png_path}"
                else:
                    png_status = f"⚠️ PNG 渲染失败: {render_result.stderr[:200]}"
        except FileNotFoundError:
            # mmdc 未安装，这是正常情况
            png_status = "ℹ️ mmdc 未安装，已保存 .mmd 源文件（可在 Mermaid Live Editor 中查看）"
        except Exception as e:
            png_status = f"⚠️ 渲染异常: {str(e)[:100]}"

        return (
            f"✅ Mermaid 图表已生成\n"
            f"  .mmd 文件: {mmd_path}\n"
            f"  {png_status}"
        )
