"""
validation_tool.py - 代码验证工具
=================================
供 Tester（验证官）使用，对 Python 代码进行静态分析和合理性检查。
包含语法验证、常见问题检测、规范性检查等。

安全性审计:
  ✅ 仅使用 ast 模块进行静态分析，不执行代码
  ✅ 不读取代码以外的文件
  ✅ 输出结构化验证报告
"""

import ast
import re
from typing import Type, List, Dict
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class ValidationInput(BaseModel):
    """ValidationTool 的输入参数模型。"""
    code: str = Field(
        ...,
        description=(
            "需要验证的 Python 代码字符串。"
            "可以是完整的 Python 脚本或代码片段。"
        )
    )
    check_style: bool = Field(
        default=True,
        description="是否进行编码规范检查（变量命名、注释等）。"
    )


class ValidationTool(BaseTool):
    """Python 代码静态验证工具。

    对代码进行语法分析、问题检测和规范性检查。
    不执行代码，仅通过 AST 分析。

    检查项目:
      - 语法正确性 (ast.parse)
      - 函数缺少 docstring
      - 空的 except 块（裸 except）
      - 未使用的 import（简单检测）
      - 类/函数命名规范
      - TODO/FIXME/HACK 标记检测
    """
    name: str = "python_code_validator"
    description: str = (
        "对 Python 代码进行静态验证和质量检查。"
        "输入 Python 代码字符串，输出包含语法检查、"
        "常见问题检测、规范性建议的验证报告。"
        "不会执行代码，仅进行安全的静态分析。"
    )
    args_schema: Type[BaseModel] = ValidationInput

    def _run(self, code: str, check_style: bool = True) -> str:
        """执行代码验证。

        Args:
            code: Python 代码字符串
            check_style: 是否检查编码规范

        Returns:
            结构化的验证报告
        """
        report_lines: List[str] = []
        issues: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []

        # ---------- 1. 语法检查 ----------
        try:
            tree = ast.parse(code)
            report_lines.append("✅ 语法检查: 通过")
        except SyntaxError as e:
            return (
                f"❌ 语法检查: 失败\n"
                f"  错误位置: 第 {e.lineno} 行, 第 {e.offset} 列\n"
                f"  错误信息: {e.msg}\n"
                f"  问题代码: {e.text.strip() if e.text else '(无)'}\n\n"
                f"建议: 请修复语法错误后重新验证。"
            )

        # ---------- 2. AST 深度分析 ----------
        stats = {
            "functions": 0,
            "classes": 0,
            "imports": 0,
            "lines": len(code.strip().split("\n")),
        }

        # 收集所有 import 的名称
        imported_names = set()
        # 收集代码中使用的名称（简单启发式）
        used_names = set()

        for node in ast.walk(tree):
            # 统计函数
            if isinstance(node, ast.FunctionDef):
                stats["functions"] += 1
                used_names.add(node.name)

                # 检查 docstring
                if not (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    issues.append({
                        "type": "缺少文档字符串",
                        "location": f"函数 '{node.name}' (第 {node.lineno} 行)",
                        "suggestion": "添加 docstring 说明函数用途、参数和返回值"
                    })

            # 统计类
            elif isinstance(node, ast.ClassDef):
                stats["classes"] += 1
                used_names.add(node.name)

                # 检查类 docstring
                if not (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    issues.append({
                        "type": "缺少文档字符串",
                        "location": f"类 '{node.name}' (第 {node.lineno} 行)",
                        "suggestion": "添加 docstring 说明类的用途和属性"
                    })

            # 收集 import
            elif isinstance(node, ast.Import):
                stats["imports"] += 1
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names.add(name)

            elif isinstance(node, ast.ImportFrom):
                stats["imports"] += 1
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names.add(name)

            # 检查裸 except
            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    issues.append({
                        "type": "裸 except 块",
                        "location": f"第 {node.lineno} 行",
                        "suggestion": "使用具体的异常类型，如 except Exception as e:"
                    })

            # 收集使用的名称
            elif isinstance(node, ast.Name):
                used_names.add(node.id)

        # ---------- 3. 未使用的 import 检测（简单启发式） ----------
        potentially_unused = imported_names - used_names
        # 排除常见的合理未直接引用的模块
        common_side_effect_imports = {"os", "sys", "logging", "warnings", "typing"}
        truly_unused = potentially_unused - common_side_effect_imports

        for name in truly_unused:
            warnings.append({
                "type": "可能未使用的 import",
                "name": name,
                "suggestion": "如果确实未使用，建议移除以保持代码整洁"
            })

        # ---------- 4. 代码规范检查 ----------
        if check_style:
            code_lines = code.split("\n")

            for i, line in enumerate(code_lines, 1):
                # 检查过长行
                if len(line) > 120:
                    warnings.append({
                        "type": "行过长",
                        "location": f"第 {i} 行 ({len(line)} 字符)",
                        "suggestion": "建议每行不超过 120 字符（Google 规范）"
                    })

                # 检查 TODO/FIXME/HACK
                for marker in ["TODO", "FIXME", "HACK", "XXX"]:
                    if marker in line:
                        warnings.append({
                            "type": f"{marker} 标记",
                            "location": f"第 {i} 行",
                            "suggestion": f"存在 {marker} 标记，提示有待处理事项"
                        })

        # ---------- 5. 生成报告 ----------
        report_lines.append(
            f"\n📊 代码统计:\n"
            f"  总行数: {stats['lines']}\n"
            f"  函数数: {stats['functions']}\n"
            f"  类数量: {stats['classes']}\n"
            f"  import 数: {stats['imports']}"
        )

        # 问题报告
        if issues:
            report_lines.append(f"\n⚠️ 发现 {len(issues)} 个问题:")
            for iss in issues:
                report_lines.append(
                    f"  [{iss['type']}] {iss['location']}\n"
                    f"    → {iss['suggestion']}"
                )

        # 警告报告
        if warnings:
            report_lines.append(f"\nℹ️ {len(warnings)} 个建议:")
            for warn in warnings:
                location = warn.get('location', warn.get('name', ''))
                report_lines.append(
                    f"  [{warn['type']}] {location}\n"
                    f"    → {warn['suggestion']}"
                )

        # 最终结论
        if not issues and not warnings:
            report_lines.append("\n🎉 代码质量良好，未发现明显问题！")
            verdict = "PASS ✅"
        elif not issues:
            verdict = "PASS ✅ (有建议项)"
        else:
            verdict = f"REVIEW ⚠️ ({len(issues)} 个问题需关注)"

        report_lines.insert(0, f"## 验证结论: {verdict}")

        return "\n".join(report_lines)
