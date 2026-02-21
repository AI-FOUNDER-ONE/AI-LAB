"""
code_review_tool.py - 代码审查工具
===================================
供 Coder（程序员）使用，对代码进行静态分析，提供审查建议。

安全性审计:
  ✅ 仅使用ast模块进行静态分析，不执行代码
  ✅ 不读取代码以外的文件
  ✅ 输出结构化审查报告
"""

import ast
import re
import json
from typing import Type, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

# 尝试导入 crewai，如果失败则提供本地替代
try:
    from crewai.tools import BaseTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # 提供本地 BaseTool 替代
    class BaseTool:
        """本地 BaseTool 替代，用于在没有 crewai 的情况下运行"""
        name: str = ""
        description: str = ""
        args_schema: Type[BaseModel] = None

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def _run(self, **kwargs) -> str:
            raise NotImplementedError("Subclasses must implement _run method")


class CodeReviewInput(BaseModel):
    """CodeReviewTool 的输入参数模型。"""
    code: str = Field(
        ...,
        description=(
            "需要审查的代码字符串。可以是完整的Python脚本或代码片段。\n"
            "示例：一个函数、一个类或完整的模块代码。"
        )
    )
    review_focus: str = Field(
        default="all",
        description=(
            "审查重点。可选值：\n"
            "- 'all': 全面审查（默认）\n"
            "- 'security': 安全审查\n"
            "- 'performance': 性能审查\n"
            "- 'style': 编码规范审查\n"
            "- 'logic': 逻辑审查"
        )
    )
    language: str = Field(
        default="python",
        description="代码语言。目前仅支持Python。"
    )


class CodeReviewTool(BaseTool):
    """代码审查工具。

    对代码进行静态分析，提供审查建议。
    包括：语法检查、安全漏洞检测、性能问题、编码规范、逻辑错误等。
    """

    name: str = "code_review"
    description: str = (
        "对代码进行静态分析，提供审查建议。"
        "输入代码字符串，输出结构化审查报告。"
        "支持安全、性能、编码规范等多方面审查。"
    )
    args_schema: Type[BaseModel] = CodeReviewInput

    def _run(self, code: str, review_focus: str = "all", language: str = "python") -> str:
        """执行代码审查。

        Args:
            code: 需要审查的代码字符串
            review_focus: 审查重点（all/security/performance/style/logic）
            language: 代码语言（目前仅支持Python）

        Returns:
            格式化的代码审查报告
        """
        try:
            if language.lower() != "python":
                return f"❌ 暂不支持 {language} 语言的代码审查，目前仅支持Python。"

            # 1. 预处理代码
            cleaned_code = self._preprocess_code(code)

            # 2. 执行审查
            review_results = self._perform_code_review(cleaned_code, review_focus)

            # 3. 格式化输出
            return self._format_report(code, review_results)

        except SyntaxError as e:
            return f"❌ 代码语法错误：{str(e)}"
        except Exception as e:
            return f"❌ 代码审查失败：{str(e)}"

    def _preprocess_code(self, code: str) -> str:
        """预处理代码"""
        # 移除多余空白字符，但保留缩进
        lines = code.split('\n')
        cleaned_lines = []
        for line in lines:
            # 保留行尾注释
            cleaned_line = line.rstrip()
            if cleaned_line:  # 不添加空行
                cleaned_lines.append(cleaned_line)
        return '\n'.join(cleaned_lines)

    def _perform_code_review(self, code: str, review_focus: str) -> Dict[str, Any]:
        """执行代码审查"""
        results = {
            "summary": {
                "total_lines": len(code.split('\n')),
                "issues_found": 0,
                "review_focus": review_focus,
            },
            "issues": [],
            "suggestions": [],
            "security_risks": [],
            "performance_concerns": [],
        }

        try:
            # 解析AST
            tree = ast.parse(code)

            # 根据审查重点执行不同的检查
            if review_focus in ["all", "security"]:
                security_issues = self._check_security(tree)
                results["security_risks"] = security_issues
                results["summary"]["issues_found"] += len(security_issues)

            if review_focus in ["all", "performance"]:
                performance_issues = self._check_performance(tree)
                results["performance_concerns"] = performance_issues
                results["summary"]["issues_found"] += len(performance_issues)

            if review_focus in ["all", "style"]:
                style_issues = self._check_style(code, tree)
                results["issues"].extend(style_issues)
                results["summary"]["issues_found"] += len(style_issues)

            if review_focus in ["all", "logic"]:
                logic_issues = self._check_logic(tree)
                results["issues"].extend(logic_issues)
                results["summary"]["issues_found"] += len(logic_issues)

            # 生成总体建议
            results["suggestions"] = self._generate_suggestions(results)

        except SyntaxError:
            # 语法错误已经在主函数中处理
            pass

        return results

    def _check_security(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """安全检查"""
        issues = []
        security_visitor = SecurityVisitor()
        security_visitor.visit(tree)

        # 检查eval/exec调用
        for node in security_visitor.eval_calls:
            issues.append({
                "type": "security",
                "severity": "high",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "发现 eval() 调用，可能存在代码注入风险",
                "suggestion": "避免使用 eval()，考虑使用 ast.literal_eval() 或设计更安全的替代方案"
            })

        # 检查os.system调用
        for node in security_visitor.system_calls:
            issues.append({
                "type": "security",
                "severity": "high",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "发现 os.system() 调用，可能存在命令注入风险",
                "suggestion": "使用 subprocess.run() 并正确转义参数，或使用更安全的替代方案"
            })

        # 检查pickle加载
        for node in security_visitor.pickle_loads:
            issues.append({
                "type": "security",
                "severity": "medium",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "发现 pickle.loads() 调用，反序列化可能存在安全风险",
                "suggestion": "考虑使用 json、msgpack 等更安全的序列化格式，或使用签名验证"
            })

        return issues

    def _check_performance(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """性能检查"""
        issues = []
        performance_visitor = PerformanceVisitor()
        performance_visitor.visit(tree)

        # 检查循环中的append
        for node in performance_visitor.loop_appends:
            issues.append({
                "type": "performance",
                "severity": "low",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "在循环中使用 list.append() 可能影响性能",
                "suggestion": "考虑使用列表推导式或提前分配列表大小"
            })

        # 检查字符串拼接
        for node in performance_visitor.string_concats:
            issues.append({
                "type": "performance",
                "severity": "low",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "在循环中进行字符串拼接可能影响性能",
                "suggestion": "考虑使用 str.join() 或 io.StringIO"
            })

        return issues

    def _check_style(self, code: str, tree: ast.AST) -> List[Dict[str, Any]]:
        """编码规范检查"""
        issues = []

        # 检查行长度
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({
                    "type": "style",
                    "severity": "low",
                    "line": i,
                    "message": f"行过长 ({len(line)} 字符)",
                    "suggestion": "建议将行长度限制在120字符以内，提高可读性"
                })

        # 检查函数/类命名
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not re.match(r'^[a-z_][a-z0-9_]*$', node.name):
                    issues.append({
                        "type": "style",
                        "severity": "low",
                        "line": node.lineno,
                        "message": f"函数命名 '{node.name}' 不符合蛇形命名规范",
                        "suggestion": "函数名应使用蛇形命名法，如：calculate_total"
                    })

                # 检查函数是否有docstring
                if not ast.get_docstring(node):
                    issues.append({
                        "type": "style",
                        "severity": "medium",
                        "line": node.lineno,
                        "message": f"函数 '{node.name}' 缺少文档字符串",
                        "suggestion": "添加函数docstring，描述功能、参数和返回值"
                    })

            elif isinstance(node, ast.ClassDef):
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                    issues.append({
                        "type": "style",
                        "severity": "low",
                        "line": node.lineno,
                        "message": f"类命名 '{node.name}' 不符合帕斯卡命名规范",
                        "suggestion": "类名应使用帕斯卡命名法，如：DataProcessor"
                    })

        # 检查未使用的导入（简化版）
        import_visitor = ImportVisitor()
        import_visitor.visit(tree)

        # 这里可以添加更复杂的未使用导入检查
        # 当前版本简化处理

        return issues

    def _check_logic(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """逻辑检查"""
        issues = []
        logic_visitor = LogicVisitor()
        logic_visitor.visit(tree)

        # 检查空的except块
        for node in logic_visitor.bare_excepts:
            issues.append({
                "type": "logic",
                "severity": "high",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "发现空的 except 块，会捕获所有异常",
                "suggestion": "指定具体的异常类型，或至少记录异常信息"
            })

        # 检查比较中的赋值
        for node in logic_visitor.assign_in_compares:
            issues.append({
                "type": "logic",
                "severity": "medium",
                "line": node.lineno if hasattr(node, 'lineno') else "unknown",
                "message": "在比较表达式中发现赋值操作（可能是误用 ==）",
                "suggestion": "检查是否误将赋值运算符 = 用作了比较运算符 =="
            })

        return issues

    def _generate_suggestions(self, results: Dict[str, Any]) -> List[str]:
        """生成总体建议"""
        suggestions = []

        issue_count = results["summary"]["issues_found"]
        if issue_count == 0:
            suggestions.append("代码质量良好，未发现明显问题。")
            return suggestions

        # 根据问题类型生成建议
        security_count = len(results["security_risks"])
        performance_count = len(results["performance_concerns"])
        style_logic_count = len([i for i in results["issues"] if i["type"] in ["style", "logic"]])

        if security_count > 0:
            suggestions.append(f"发现 {security_count} 个安全问题，建议优先处理。")

        if performance_count > 0:
            suggestions.append(f"发现 {performance_count} 个性能问题，可在优化阶段处理。")

        if style_logic_count > 0:
            suggestions.append(f"发现 {style_logic_count} 个编码规范/逻辑问题，建议在代码审查中讨论。")

        suggestions.append("建议按照严重程度（high > medium > low）依次处理问题。")
        suggestions.append("所有修复完成后，建议重新运行代码审查以验证改进。")

        return suggestions

    def _format_report(self, original_code: str, results: Dict[str, Any]) -> str:
        """格式化审查报告"""
        summary = results["summary"]

        report = f"""# 代码审查报告

## 审查摘要
- **审查代码行数**: {summary['total_lines']}
- **发现问题总数**: {summary['issues_found']}
- **审查重点**: {summary['review_focus']}

"""

        # 安全问题
        if results["security_risks"]:
            report += "## 🔒 安全问题\n"
            for i, issue in enumerate(results["security_risks"], 1):
                report += f"{i}. **[{issue['severity'].upper()}]** 第{issue['line']}行: {issue['message']}\n"
                report += f"   建议: {issue['suggestion']}\n\n"

        # 性能问题
        if results["performance_concerns"]:
            report += "## ⚡ 性能问题\n"
            for i, issue in enumerate(results["performance_concerns"], 1):
                report += f"{i}. **[{issue['severity'].upper()}]** 第{issue['line']}行: {issue['message']}\n"
                report += f"   建议: {issue['suggestion']}\n\n"

        # 编码规范/逻辑问题
        if results["issues"]:
            report += "## 📝 编码规范与逻辑问题\n"
            for i, issue in enumerate(results["issues"], 1):
                report += f"{i}. **[{issue['severity'].upper()}]** 第{issue['line']}行: {issue['message']}\n"
                report += f"   建议: {issue['suggestion']}\n\n"

        # 总体建议
        if results["suggestions"]:
            report += "## 💡 总体建议\n"
            for suggestion in results["suggestions"]:
                report += f"- {suggestion}\n"

        # 原始代码片段（前20行）
        report += "\n## 📋 审查的代码（前20行）\n```python\n"
        lines = original_code.split('\n')
        for i, line in enumerate(lines[:20], 1):
            report += f"{i:3d}: {line}\n"
        if len(lines) > 20:
            report += f"... 省略 {len(lines) - 20} 行\n"
        report += "```\n"

        # 结构化数据（供程序处理）
        report += f"\n## 📊 结构化数据（JSON）\n```json\n{json.dumps(results, ensure_ascii=False, indent=2)}\n```"

        return report


# ==============================================================================
# AST Visitor 类
# ==============================================================================

class SecurityVisitor(ast.NodeVisitor):
    """安全检查Visitor"""

    def __init__(self):
        self.eval_calls = []
        self.system_calls = []
        self.pickle_loads = []

    def visit_Call(self, node):
        """检查函数调用"""
        if isinstance(node.func, ast.Name):
            # 检查 eval()
            if node.func.id == 'eval':
                self.eval_calls.append(node)
            # 检查 pickle.loads()
            elif node.func.id == 'loads':
                # 简单检查，可能需要更精确
                self.pickle_loads.append(node)

        elif isinstance(node.func, ast.Attribute):
            # 检查 os.system()
            if (isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'os' and
                node.func.attr == 'system'):
                self.system_calls.append(node)

            # 检查 pickle.loads()
            if (isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'pickle' and
                node.func.attr == 'loads'):
                self.pickle_loads.append(node)

        self.generic_visit(node)


class PerformanceVisitor(ast.NodeVisitor):
    """性能检查Visitor"""

    def __init__(self):
        self.loop_appends = []
        self.string_concats = []

    def visit_Call(self, node):
        """检查函数调用"""
        if isinstance(node.func, ast.Attribute):
            # 检查 list.append() 在循环中
            if node.func.attr == 'append':
                # 简化检查：如果父节点是For或While循环
                parent = getattr(node, 'parent', None)
                if parent and isinstance(parent, (ast.For, ast.While)):
                    self.loop_appends.append(node)

        self.generic_visit(node)

    def visit_BinOp(self, node):
        """检查字符串拼接"""
        if isinstance(node.op, ast.Add):
            # 检查操作数是否为字符串
            left_str = self._is_string_literal(node.left)
            right_str = self._is_string_literal(node.right)
            if left_str or right_str:
                # 简化检查：如果父节点是循环
                parent = getattr(node, 'parent', None)
                if parent and isinstance(parent, (ast.For, ast.While)):
                    self.string_concats.append(node)

        self.generic_visit(node)

    def _is_string_literal(self, node):
        """检查节点是否为字符串字面量"""
        return isinstance(node, ast.Str) or (isinstance(node, ast.Constant) and isinstance(node.value, str))


class LogicVisitor(ast.NodeVisitor):
    """逻辑检查Visitor"""

    def __init__(self):
        self.bare_excepts = []
        self.assign_in_compares = []

    def visit_ExceptHandler(self, node):
        """检查空的except块"""
        if node.type is None:  # 裸except
            self.bare_excepts.append(node)
        elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
            # 捕获所有异常
            self.bare_excepts.append(node)

        self.generic_visit(node)

    def visit_Compare(self, node):
        """检查比较中的赋值"""
        for comparator in node.comparators:
            if isinstance(comparator, ast.Name):
                # 简化检查：如果比较符是 '==' 或 '!='，且操作数可能是赋值
                # 实际实现需要更复杂的分析
                pass

        self.generic_visit(node)


class ImportVisitor(ast.NodeVisitor):
    """导入检查Visitor"""

    def __init__(self):
        self.imports = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = CodeReviewTool()

    test_code = '''
import os
import pickle

def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result

def risky_function(user_input):
    # 危险：使用eval
    return eval(user_input)

def another_risky():
    # 危险：系统调用
    os.system("rm -rf /tmp/*")

    # 危险：pickle反序列化
    data = pickle.loads(some_data)

    # 性能问题：字符串拼接
    output = ""
    for i in range(100):
        output += str(i)

    return output
'''

    result = tool._run(
        code=test_code,
        review_focus="all",
        language="python"
    )

    print("测试结果:")
    print(result)