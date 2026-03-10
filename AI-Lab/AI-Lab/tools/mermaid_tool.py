"""
mermaid_tool.py - Mermaid 图表生成工具
======================================
供 Arch（架构师）使用。支持 (diagram_type, content) 由 LLM 生成 Mermaid 代码，
或直接传入 (code, filename)。生成后做基础语法验证，失败则重试 LLM（最多 2 次）。

安全性审计:
  ✅ 文件写入限制在 data/generated_docs/ 目录
  ✅ 不执行任意命令，仅调用 mmdc
  ✅ 异常处理完善，mmdc 不可用时优雅降级
  ✅ 不引入新外部依赖
"""

import os
import re
import time
import subprocess
from typing import Type, Tuple
from pydantic import BaseModel, Field
from tools.base_tool import BaseTool


class MermaidInput(BaseModel):
    """MermaidTool 的输入参数模型。"""
    code: str = Field(
        default="",
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
    diagram_type: str = Field(
        default="",
        description="图表类型，如 flowchart, sequenceDiagram。与 content 一起时由 LLM 生成代码。"
    )
    content: str = Field(
        default="",
        description="内容描述，与 diagram_type 一起时由 LLM 生成 Mermaid 代码。"
    )


def _validate_mermaid_syntax(code: str) -> Tuple[bool, str]:
    """基础语法检查（不依赖 mermaid-cli）。返回 (是否通过, 错误信息)。"""
    if not (code or code.strip()):
        return False, "Empty code"
    valid_starts = [
        "graph", "flowchart", "sequenceDiagram", "classDiagram",
        "stateDiagram", "erDiagram", "gantt", "pie", "gitgraph",
    ]
    first_line = code.strip().split("\n")[0].strip()
    if not any(first_line.startswith(vs) for vs in valid_starts):
        return False, f"Invalid diagram type: {first_line[:80]}"
    if code.count("(") != code.count(")") or code.count("[") != code.count("]"):
        return False, "Mismatched brackets"
    return True, ""


class MermaidTool(BaseTool):
    """Mermaid 图表生成工具。

    支持 (diagram_type, content) 由 LLM 生成代码并做语法验证（失败则重试最多 2 次）；
    或直接传入 (code, filename) 保存。将 .mmd 保存到 data/generated_docs/，可选 mmdc 渲染 PNG。
    """
    name: str = "mermaid_chart_generator"
    description: str = (
        "将 Mermaid DSL 代码生成为图表文件（.mmd + .png）。"
        "可传入图表类型和内容描述由 LLM 生成代码，或直接传入 Mermaid 代码。"
        "支持 graph/flowchart/sequenceDiagram/gantt 等。"
    )
    args_schema: Type[BaseModel] = MermaidInput

    def _run(
        self,
        code: str = "",
        filename: str = "",
        diagram_type: str = "",
        content: str = "",
    ) -> str:
        """执行 Mermaid 图表生成。可 (diagram_type + content) 生成，或直接 (code + filename)。"""
        if diagram_type or content:
            return self._run_generate_and_save(diagram_type, content, filename)
        return self._run_save_only(code, filename)

    def _generate_mermaid_llm(
        self, diagram_type: str, content: str, last_error: str = ""
    ) -> str:
        """调用 LLM 生成 Mermaid 代码。"""
        try:
            from config import AGENT_MODELS
            from core.llm_client_factory import create_llm_client
            cfg = AGENT_MODELS.get("Arch", {"provider": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com"})
            client = create_llm_client(cfg["provider"], cfg)
            model = cfg.get("model", "deepseek-chat")
            prompt = (
                f"Generate Mermaid diagram code only. Type: {diagram_type or 'flowchart'}. "
                f"Content/description: {content}\n\n"
                "Output only the Mermaid code block, no markdown fences and no explanation."
            )
            if last_error:
                prompt += f"\n\nPrevious attempt had syntax error, fix it: {last_error}"
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )
            raw = (resp.choices[0].message.content or "").strip()
            # 去掉 ```mermaid 和 ``` 包裹
            if "```" in raw:
                m = re.search(r"```(?:mermaid)?\s*([\s\S]*?)```", raw)
                if m:
                    raw = m.group(1).strip()
            return raw
        except Exception as e:
            return f"# LLM error: {e}\nflowchart LR\nA[Error]"

    def _run_generate_and_save(
        self, diagram_type: str, content: str, filename: str = ""
    ) -> str:
        """由 LLM 生成代码，验证通过后保存；验证失败则重试最多 2 次。"""
        last_error = ""
        code = ""
        for attempt in range(3):
            code = self._generate_mermaid_llm(diagram_type, content, last_error)
            ok, err = _validate_mermaid_syntax(code)
            if ok:
                break
            last_error = err
        if not code:
            code = "flowchart LR\nA[Empty]"
        ok, err = _validate_mermaid_syntax(code)
        if not ok:
            code = code + "\n\n<!-- 语法验证未通过: " + err + " -->"
        return self._run_save_only(code, filename, syntax_warning=err if not ok else None)

    def _run_save_only(
        self, code: str, filename: str = "", syntax_warning: str = None
    ) -> str:
        """仅保存已有 code 到 .mmd（并可选渲染 PNG）。"""
        from config import GENERATED_DOCS_DIR

        if not code or not code.strip():
            return "❌ 未提供 Mermaid 代码。"

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"mermaid_{timestamp}"

        filename = filename.replace(os.sep, "_").replace("/", "_")
        mmd_path = os.path.join(GENERATED_DOCS_DIR, f"{filename}.mmd")
        png_path = os.path.join(GENERATED_DOCS_DIR, f"{filename}.png")

        try:
            with open(mmd_path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            return f"❌ 保存 Mermaid 文件失败: {e}"

        png_status = "（mmdc 未安装，仅保存了 .mmd 源文件）"
        try:
            result = subprocess.run(
                ["mmdc", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                render_result = subprocess.run(
                    ["mmdc", "-i", mmd_path, "-o", png_path, "-b", "white"],
                    capture_output=True, text=True, timeout=30
                )
                if render_result.returncode == 0 and os.path.exists(png_path):
                    png_status = f"✅ PNG 已渲染: {png_path}"
                else:
                    png_status = f"⚠️ PNG 渲染失败: {render_result.stderr[:200] or 'unknown'}"
        except FileNotFoundError:
            png_status = "ℹ️ mmdc 未安装，已保存 .mmd 源文件（可在 Mermaid Live Editor 中查看）"
        except Exception as e:
            png_status = f"⚠️ 渲染异常: {str(e)[:100]}"

        out = (
            f"✅ Mermaid 图表已生成\n"
            f"  .mmd 文件: {mmd_path}\n"
            f"  {png_status}"
        )
        if syntax_warning:
            out += f"\n  ⚠️ 语法验证未通过，已保存原始代码供修改: {syntax_warning}"
        return out
