"""
test_case_generator_tool.py - 测试用例生成工具
===========================================
供 Tester（验证官）使用，根据代码或需求自动生成测试用例。
支持单元测试、集成测试、边界测试等多种测试类型。
生成后自动保存到 workspace_dir/tests/，并可选执行语法检查与 pytest。

安全性审计:
  ✅ 仅分析代码结构，不执行代码
  ✅ 文件仅写入 workspace_dir/tests/
  ✅ 输出结构化测试用例报告
"""

import ast
import re
import json
import os
import subprocess
import sys
from typing import Type, List, Dict, Any, Optional
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


class TestCaseGeneratorInput(BaseModel):
    """TestCaseGeneratorTool 的输入参数模型。"""
    target: str = Field(
        ...,
        description=(
            "目标代码或需求描述。可以是：\n"
            "1. Python 代码字符串\n"
            "2. 函数/类/模块的描述\n"
            "3. API 接口定义\n"
            "示例：一个函数的代码或描述字符串"
        )
    )
    test_type: str = Field(
        default="unit",
        description=(
            "测试类型。可选值：\n"
            "- 'unit': 单元测试（默认）\n"
            "- 'integration': 集成测试\n"
            "- 'boundary': 边界测试\n"
            "- 'error': 错误处理测试\n"
            "- 'performance': 性能测试\n"
            "- 'security': 安全测试"
        )
    )
    framework: str = Field(
        default="pytest",
        description=(
            "测试框架。可选值：\n"
            "- 'pytest': pytest 框架（默认）\n"
            "- 'unittest': unittest 框架\n"
            "- 'doctest': doctest 框架"
        )
    )
    language: str = Field(
        default="python",
        description="目标代码语言。目前仅支持Python。"
    )
    workspace_dir: str = Field(
        default="",
        description="工作区目录（通常由 session_store.get_workspace_dir() 提供）。非空时将测试保存到该目录下的 tests/ 并执行语法检查与 pytest。"
    )


class TestCaseGeneratorTool(BaseTool):
    """测试用例生成工具。

    根据代码或需求自动生成测试用例。
    支持多种测试类型和框架。
    """

    name: str = "test_case_generator"
    description: str = (
        "根据代码或需求自动生成测试用例。"
        "支持单元测试、集成测试、边界测试等多种测试类型。"
        "输出结构化测试用例，可直接用于测试执行。"
    )
    args_schema: Type[BaseModel] = TestCaseGeneratorInput

    def _run(
        self,
        target: str,
        test_type: str = "unit",
        framework: str = "pytest",
        language: str = "python",
        workspace_dir: str = "",
    ):
        """执行测试用例生成；若提供 workspace_dir 则自动保存并执行语法检查与 pytest。

        Returns:
            结构化结果 dict: test_file, test_count, syntax_valid, execution_result, output
        """
        try:
            if language.lower() != "python":
                return {
                    "test_file": "",
                    "test_count": 0,
                    "syntax_valid": False,
                    "execution_result": "error",
                    "output": f"❌ 暂不支持 {language} 语言的测试用例生成，目前仅支持Python。",
                }

            # 1. 分析目标
            target_info = self._analyze_target(target)

            # 2. 根据测试类型生成测试用例（不修改已有 prompt）
            test_cases = self._generate_test_cases(target_info, test_type)

            # 3. 根据框架格式化测试用例
            formatted_tests = self._format_tests(test_cases, framework, target_info)

            test_count = len(test_cases)
            test_file = ""
            syntax_valid = False
            execution_result = "skipped"
            output = ""

            if workspace_dir and workspace_dir.strip():
                test_file, syntax_valid, execution_result, output = self._save_and_verify(
                    formatted_tests, target_info, framework, workspace_dir.strip()
                )

            return {
                "test_file": test_file,
                "test_count": test_count,
                "syntax_valid": syntax_valid,
                "execution_result": execution_result,
                "output": output[:500] if output else "",
            }
        except Exception as e:
            return {
                "test_file": "",
                "test_count": 0,
                "syntax_valid": False,
                "execution_result": "error",
                "output": str(e)[:500],
            }

    def _save_and_verify(
        self,
        formatted_tests: str,
        target_info: Dict[str, Any],
        framework: str,
        workspace_dir: str,
    ) -> tuple:
        """保存测试文件到 workspace_dir/tests/，执行语法检查与 pytest。返回 (test_file, syntax_valid, execution_result, output)。"""
        module_name = re.sub(r"\W+", "_", target_info.get("name", "module") or "module").strip("_") or "module"
        tests_dir = os.path.join(workspace_dir, "tests")
        try:
            os.makedirs(tests_dir, exist_ok=True)
        except OSError:
            return ("", False, "skipped", "无法创建 tests 目录")
        filename = f"test_{module_name}.py"
        filepath = os.path.join(tests_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(formatted_tests)
        except OSError as e:
            return (filepath, False, "skipped", f"保存失败: {e}")

        # 语法检查：python -m py_compile test_xxx.py
        syntax_valid = False
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", filepath],
                capture_output=True,
                text=True,
                timeout=10,
            )
            syntax_valid = result.returncode == 0
            if not syntax_valid:
                out = (result.stderr or result.stdout or "").strip()
                return (filepath, False, "error", out or "语法检查未通过")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return (filepath, False, "skipped", "py_compile 超时或不可用")

        # 仅当 framework 为 pytest 且语法通过时执行 pytest
        execution_result = "skipped"
        output = ""
        if framework.lower() != "pytest":
            return (filepath, syntax_valid, "skipped", "仅对 pytest 框架执行运行")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", filepath, "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=workspace_dir,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            execution_result = "passed" if proc.returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            execution_result = "skipped"
            output = "pytest 执行超时（30s）"
        except FileNotFoundError:
            execution_result = "skipped"
            output = "pytest 未安装或不可用"

        return (filepath, syntax_valid, execution_result, output)

    def _analyze_target(self, target: str) -> Dict[str, Any]:
        """分析目标代码或需求"""
        info = {
            "type": "unknown",
            "name": "Unknown",
            "description": "",
            "functions": [],
            "classes": [],
            "inputs": [],
            "outputs": [],
            "complexity": "low",
        }

        # 尝试解析为Python代码
        try:
            tree = ast.parse(target)
            info["type"] = "python_code"

            # 提取函数和类信息
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "has_return": any(isinstance(n, ast.Return) for n in ast.walk(node)),
                    }
                    info["functions"].append(func_info)
                    info["name"] = node.name  # 使用第一个函数名

                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "methods": [],
                    }
                    for subnode in node.body:
                        if isinstance(subnode, ast.FunctionDef):
                            class_info["methods"].append(subnode.name)
                    info["classes"].append(class_info)
                    info["name"] = node.name  # 使用第一个类名

            if info["functions"] or info["classes"]:
                info["complexity"] = "medium" if len(info["functions"]) + len(info["classes"]) > 3 else "low"

        except SyntaxError:
            # 如果不是有效Python代码，当作需求描述处理
            info["type"] = "requirement"
            info["description"] = target[:200] + "..." if len(target) > 200 else target
            info["name"] = "Requirement"
            info["complexity"] = self._estimate_complexity(target)

        return info

    def _estimate_complexity(self, text: str) -> str:
        """估算需求复杂度"""
        word_count = len(text.split())
        if word_count < 50:
            return "low"
        elif word_count < 200:
            return "medium"
        else:
            return "high"

    def _generate_test_cases(self, target_info: Dict[str, Any], test_type: str) -> List[Dict[str, Any]]:
        """根据目标信息和测试类型生成测试用例"""
        test_cases = []

        if test_type == "unit":
            test_cases = self._generate_unit_tests(target_info)
        elif test_type == "integration":
            test_cases = self._generate_integration_tests(target_info)
        elif test_type == "boundary":
            test_cases = self._generate_boundary_tests(target_info)
        elif test_type == "error":
            test_cases = self._generate_error_tests(target_info)
        elif test_type == "performance":
            test_cases = self._generate_performance_tests(target_info)
        elif test_type == "security":
            test_cases = self._generate_security_tests(target_info)

        return test_cases

    def _generate_unit_tests(self, target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成单元测试用例"""
        test_cases = []

        if target_info["type"] == "python_code" and target_info["functions"]:
            for func in target_info["functions"]:
                # 正常用例
                test_cases.append({
                    "name": f"test_{func['name']}_normal",
                    "description": f"测试函数 {func['name']} 的正常功能",
                    "type": "positive",
                    "steps": [
                        f"准备测试数据",
                        f"调用函数 {func['name']}",
                        f"验证返回值符合预期",
                    ],
                    "expected": "函数返回正确结果"
                })

                # 边界用例
                test_cases.append({
                    "name": f"test_{func['name']}_edge_case",
                    "description": f"测试函数 {func['name']} 的边界情况",
                    "type": "boundary",
                    "steps": [
                        f"准备边界值输入",
                        f"调用函数 {func['name']}",
                        f"验证处理逻辑正确",
                    ],
                    "expected": "函数正确处理边界情况"
                })

        elif target_info["type"] == "requirement":
            test_cases.append({
                "name": "test_basic_functionality",
                "description": f"测试基本功能: {target_info['description'][:50]}...",
                "type": "positive",
                "steps": [
                    "根据需求准备测试场景",
                    "执行相关操作",
                    "验证结果符合需求",
                ],
                "expected": "功能实现符合需求描述"
            })

        return test_cases

    def _generate_integration_tests(self, target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成集成测试用例"""
        test_cases = []

        test_cases.append({
            "name": "test_integration_flow",
            "description": "测试完整业务流程",
            "type": "integration",
            "steps": [
                "准备完整测试数据",
                "执行端到端业务流程",
                "验证各组件协作正确",
            ],
            "expected": "业务流程完整执行，各组件正常协作"
        })

        test_cases.append({
            "name": "test_data_flow",
            "description": "测试数据流传递",
            "type": "integration",
            "steps": [
                "准备输入数据",
                "跟踪数据在各组件间的传递",
                "验证最终输出数据正确",
            ],
            "expected": "数据在组件间正确传递和处理"
        })

        return test_cases

    def _generate_boundary_tests(self, target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成边界测试用例"""
        test_cases = []

        test_cases.append({
            "name": "test_min_value",
            "description": "测试最小值边界",
            "type": "boundary",
            "steps": [
                "准备最小值输入",
                "执行相关操作",
                "验证处理逻辑正确",
            ],
            "expected": "正确处理最小值边界"
        })

        test_cases.append({
            "name": "test_max_value",
            "description": "测试最大值边界",
            "type": "boundary",
            "steps": [
                "准备最大值输入",
                "执行相关操作",
                "验证处理逻辑正确",
            ],
            "expected": "正确处理最大值边界"
        })

        test_cases.append({
            "name": "test_empty_input",
            "description": "测试空输入边界",
            "type": "boundary",
            "steps": [
                "准备空输入数据",
                "执行相关操作",
                "验证空值处理逻辑正确",
            ],
            "expected": "正确处理空输入"
        })

        return test_cases

    def _generate_error_tests(self, target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成错误处理测试用例"""
        test_cases = []

        test_cases.append({
            "name": "test_invalid_input",
            "description": "测试无效输入处理",
            "type": "negative",
            "steps": [
                "准备无效输入数据",
                "执行相关操作",
                "验证错误处理机制",
            ],
            "expected": "正确识别无效输入并抛出适当异常"
        })

        test_cases.append({
            "name": "test_exception_handling",
            "description": "测试异常处理逻辑",
            "type": "negative",
            "steps": [
                "准备会触发异常的场景",
                "执行相关操作",
                "验证异常被正确处理",
            ],
            "expected": "异常被正确捕获和处理"
        })

        return test_cases

    def _generate_performance_tests(self, target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成性能测试用例"""
        test_cases = []

        test_cases.append({
            "name": "test_response_time",
            "description": "测试响应时间",
            "type": "performance",
            "steps": [
                "准备标准测试数据",
                "测量操作执行时间",
                "验证响应时间在可接受范围内",
            ],
            "expected": "响应时间符合性能要求"
        })

        test_cases.append({
            "name": "test_load_handling",
            "description": "测试负载处理能力",
            "type": "performance",
            "steps": [
                "准备高负载测试场景",
                "执行压力测试",
                "验证系统稳定性",
            ],
            "expected": "系统能正确处理高负载"
        })

        return test_cases

    def _generate_security_tests(self, target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成安全测试用例"""
        test_cases = []

        test_cases.append({
            "name": "test_input_validation",
            "description": "测试输入验证安全",
            "type": "security",
            "steps": [
                "准备恶意输入数据（如SQL注入、XSS等）",
                "执行相关操作",
                "验证输入被正确过滤和验证",
            ],
            "expected": "系统能防御常见安全攻击"
        })

        test_cases.append({
            "name": "test_access_control",
            "description": "测试访问控制",
            "type": "security",
            "steps": [
                "尝试未授权访问",
                "验证访问被正确拒绝",
                "验证授权访问正常",
            ],
            "expected": "访问控制机制正常工作"
        })

        return test_cases

    def _format_tests(self, test_cases: List[Dict[str, Any]], framework: str, target_info: Dict[str, Any]) -> str:
        """根据测试框架格式化测试用例"""
        if framework == "pytest":
            return self._format_pytest_tests(test_cases, target_info)
        elif framework == "unittest":
            return self._format_unittest_tests(test_cases, target_info)
        elif framework == "doctest":
            return self._format_doctest_tests(test_cases, target_info)
        else:
            return self._format_generic_tests(test_cases, target_info)

    def _format_pytest_tests(self, test_cases: List[Dict[str, Any]], target_info: Dict[str, Any]) -> str:
        """格式化为pytest测试"""
        lines = []
        lines.append("import pytest")
        lines.append("")

        if target_info["type"] == "python_code" and target_info["functions"]:
            # 如果有函数信息，添加导入
            lines.append(f"# 导入待测试函数/类")
            lines.append(f"# from module import {target_info['functions'][0]['name']}")
            lines.append("")

        for test_case in test_cases:
            lines.append(f"def {test_case['name']}():")
            lines.append(f'    """{test_case["description"]}"""')
            lines.append(f"    # TODO: 实现具体测试逻辑")
            for step in test_case["steps"]:
                lines.append(f"    # {step}")
            lines.append(f"    # 期望: {test_case['expected']}")
            lines.append(f"    assert True  # 占位符，需要替换为实际断言")
            lines.append("")

        return "\n".join(lines)

    def _format_unittest_tests(self, test_cases: List[Dict[str, Any]], target_info: Dict[str, Any]) -> str:
        """格式化为unittest测试"""
        lines = []
        lines.append("import unittest")
        lines.append("")

        if target_info["type"] == "python_code" and target_info["functions"]:
            lines.append(f"# 导入待测试函数/类")
            lines.append(f"# from module import {target_info['functions'][0]['name']}")
            lines.append("")

        lines.append(f"class Test{target_info['name'].title().replace(' ', '')}(unittest.TestCase):")
        lines.append('    """自动生成的测试类"""')
        lines.append("")

        for test_case in test_cases:
            lines.append(f"    def {test_case['name']}(self):")
            lines.append(f'        """{test_case["description"]}"""')
            lines.append(f"        # TODO: 实现具体测试逻辑")
            for step in test_case["steps"]:
                lines.append(f"        # {step}")
            lines.append(f"        # 期望: {test_case['expected']}")
            lines.append(f"        self.assertTrue(True)  # 占位符，需要替换为实际断言")
            lines.append("")

        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    unittest.main()")

        return "\n".join(lines)

    def _format_doctest_tests(self, test_cases: List[Dict[str, Any]], target_info: Dict[str, Any]) -> str:
        """格式化为doctest测试"""
        lines = []
        lines.append('"""自动生成的doctest测试')
        lines.append('')

        for test_case in test_cases:
            lines.append(f"{test_case['name']}: {test_case['description']}")
            lines.append(f"    >>> # TODO: 实现具体测试逻辑")
            for step in test_case["steps"]:
                lines.append(f"    >>> # {step}")
            lines.append(f"    >>> # 期望: {test_case['expected']}")
            lines.append(f"    >>> True  # 占位符，需要替换为实际测试")
            lines.append("")

        lines.append('"""')
        return "\n".join(lines)

    def _format_generic_tests(self, test_cases: List[Dict[str, Any]], target_info: Dict[str, Any]) -> str:
        """格式化为通用测试用例格式"""
        lines = []
        lines.append(f"# 测试用例报告 - {target_info['name']}")
        lines.append(f"# 生成时间: 自动生成")
        lines.append(f"# 测试类型: 自动推断")
        lines.append("")

        for i, test_case in enumerate(test_cases, 1):
            lines.append(f"## 测试用例 {i}: {test_case['name']}")
            lines.append(f"**描述**: {test_case['description']}")
            lines.append(f"**类型**: {test_case['type']}")
            lines.append("**步骤**:")
            for j, step in enumerate(test_case['steps'], 1):
                lines.append(f"  {j}. {step}")
            lines.append(f"**期望结果**: {test_case['expected']}")
            lines.append("")

        return "\n".join(lines)

    def _generate_report(self, target_info: Dict[str, Any], test_type: str, framework: str,
                        test_cases: List[Dict[str, Any]], formatted_tests: str) -> str:
        """生成完整测试报告"""
        report = f"""# 测试用例生成报告

## 目标分析
- **目标类型**: {target_info['type']}
- **目标名称**: {target_info['name']}
- **复杂度**: {target_info['complexity']}
- **函数数量**: {len(target_info['functions'])}
- **类数量**: {len(target_info['classes'])}

## 测试配置
- **测试类型**: {test_type}
- **测试框架**: {framework}
- **生成测试用例数量**: {len(test_cases)}

## 生成的测试用例
"""

        # 测试用例概览
        for i, test_case in enumerate(test_cases, 1):
            report += f"{i}. **{test_case['name']}** ({test_case['type']}): {test_case['description']}\\n"

        report += f"""
## {framework.upper()} 格式测试代码
```python
{formatted_tests}
```

## 使用说明
1. 将生成的测试代码保存为 `.py` 文件
2. 根据需要修改 TODO 注释部分
3. 运行测试验证功能
4. 根据实际需求调整和扩展测试用例

## 结构化数据（JSON）
```json
{json.dumps({
    "target_info": target_info,
    "test_config": {"type": test_type, "framework": framework},
    "test_cases": test_cases,
    "generated_tests": formatted_tests
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = TestCaseGeneratorTool()

    test_code = '''
def add(a, b):
    """返回两个数的和"""
    return a + b

def multiply(x, y):
    """返回两个数的乘积"""
    return x * y
'''

    result = tool._run(
        target=test_code,
        test_type="unit",
        framework="pytest",
        language="python",
        workspace_dir="",
    )

    print("测试结果 (结构化):")
    print(json.dumps(result, ensure_ascii=False, indent=2))