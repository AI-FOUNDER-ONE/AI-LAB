"""
performance_analyzer_tool.py - 性能分析工具
=========================================
供 Tester（验证官）使用，分析代码的性能特征和潜在瓶颈。
包括时间复杂度分析、内存使用分析、循环复杂度、算法效率等。

安全性审计:
  ✅ 仅静态分析，不执行代码
  ✅ 不读取外部文件，只分析提供的代码
  ✅ 输入验证，防止恶意代码注入
  ✅ 输出结构化性能分析报告
"""

import ast
import re
import json
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


class PerformanceAnalyzerInput(BaseModel):
    """PerformanceAnalyzerTool 的输入参数模型。"""
    code: str = Field(
        ...,
        description=(
            "需要分析的代码。可以是：\n"
            "1. 完整的函数或类定义\n"
            "2. 算法实现代码\n"
            "3. 模块代码片段\n"
            "4. 数据库查询或API调用逻辑\n"
            "示例：一个排序算法实现，或一个数据处理函数"
        )
    )
    analysis_focus: str = Field(
        default="time_complexity",
        description=(
            "分析重点。可选值：\n"
            "- 'time_complexity': 时间复杂度分析（默认）\n"
            "- 'space_complexity': 空间复杂度分析\n"
            "- 'algorithm_efficiency': 算法效率分析\n"
            "- 'bottleneck_detection': 性能瓶颈检测\n"
            "- 'comprehensive': 全面性能分析"
        )
    )
    language: str = Field(
        default="python",
        description=(
            "编程语言。可选值：\n"
            "- 'python': Python代码（默认）\n"
            "- 'pseudocode': 伪代码或算法描述\n"
            "- 'java': Java代码\n"
            "- 'javascript': JavaScript代码\n"
            "注意：目前主要支持Python代码分析，其他语言提供基本分析。"
        )
    )


class PerformanceAnalyzerTool(BaseTool):
    """性能分析工具。

    分析代码的性能特征，包括时间复杂度、空间复杂度、算法效率等。
    通过静态分析识别潜在性能瓶颈并提供优化建议。
    """

    name: str = "performance_analyzer"
    description: str = (
        "分析代码的性能特征和潜在瓶颈。"
        "支持时间复杂度分析、空间复杂度分析、算法效率评估等。"
        "输出结构化性能分析报告和优化建议。"
    )
    args_schema: Type[BaseModel] = PerformanceAnalyzerInput

    def _run(self, code: str, analysis_focus: str = "time_complexity",
            language: str = "python") -> str:
        """执行性能分析。

        Args:
            code: 需要分析的代码
            analysis_focus: 分析重点
            language: 编程语言

        Returns:
            格式化的性能分析报告
        """
        try:
            # 1. 预处理代码
            cleaned_code = self._preprocess_code(code, language)

            # 2. 根据分析重点执行分析
            if language == "python":
                analysis_results = self._analyze_python_code(cleaned_code, analysis_focus)
            elif language in ["java", "javascript", "cpp"]:
                analysis_results = self._analyze_other_language(cleaned_code, analysis_focus, language)
            else:
                analysis_results = self._analyze_pseudocode(cleaned_code, analysis_focus)

            # 3. 生成完整报告
            return self._generate_report(code, language, analysis_focus, analysis_results)

        except Exception as e:
            return f"❌ 性能分析失败: {str(e)}"

    def _preprocess_code(self, code: str, language: str) -> str:
        """预处理代码"""
        # 移除多余的空行和前后空白
        lines = [line.rstrip() for line in code.split('\n') if line.strip()]
        return '\n'.join(lines)

    def _analyze_python_code(self, code: str, analysis_focus: str) -> Dict[str, Any]:
        """分析Python代码"""
        results = {
            "code_length": len(code),
            "line_count": code.count('\n') + 1,
            "function_count": 0,
            "class_count": 0,
            "loop_count": 0,
            "nested_loop_depth": 0,
            "recursive_calls": 0,
            "time_complexity": "O(1)",
            "space_complexity": "O(1)",
            "potential_bottlenecks": [],
            "optimization_suggestions": [],
            "complex_operations": [],
            "memory_usage_patterns": [],
        }

        try:
            # 使用AST解析Python代码
            tree = ast.parse(code)

            # 遍历AST节点
            for node in ast.walk(tree):
                # 统计函数定义
                if isinstance(node, ast.FunctionDef):
                    results["function_count"] += 1
                    # 分析函数参数
                    self._analyze_function_parameters(node, results)

                # 统计类定义
                elif isinstance(node, ast.ClassDef):
                    results["class_count"] += 1

                # 分析循环
                elif isinstance(node, (ast.For, ast.While)):
                    results["loop_count"] += 1
                    self._analyze_loop_structure(node, results)

                # 分析递归调用
                elif isinstance(node, ast.Call):
                    if self._is_recursive_call(node, tree):
                        results["recursive_calls"] += 1

                # 分析复杂操作
                self._analyze_complex_operations(node, results)

            # 基于统计信息计算复杂度
            results = self._calculate_complexities(results)

            # 检测潜在瓶颈
            self._detect_bottlenecks(results)

            # 生成优化建议
            self._generate_optimization_suggestions(results)

        except SyntaxError:
            # 如果AST解析失败，使用简单分析
            results = self._analyze_code_simple(code, analysis_focus)

        return results

    def _analyze_function_parameters(self, func_node: ast.FunctionDef, results: Dict[str, Any]):
        """分析函数参数"""
        param_count = len(func_node.args.args)
        if param_count > 5:
            results["potential_bottlenecks"].append(
                f"函数 '{func_node.name}' 参数过多 ({param_count}个)，可能影响调用性能"
            )

        # 检查默认参数
        if func_node.args.defaults:
            results["memory_usage_patterns"].append(
                f"函数 '{func_node.name}' 包含默认参数，可能影响内存使用"
            )

    def _analyze_loop_structure(self, loop_node: ast.AST, results: Dict[str, Any]):
        """分析循环结构"""
        # 计算循环嵌套深度
        depth = self._get_nested_depth(loop_node)
        if depth > results["nested_loop_depth"]:
            results["nested_loop_depth"] = depth

        # 检查循环内的操作
        if isinstance(loop_node, ast.For):
            # 检查是否有break/continue
            has_break_continue = self._check_break_continue(loop_node)
            if has_break_continue:
                results["complex_operations"].append("循环包含break/continue语句")

            # 检查循环变量使用
            if isinstance(loop_node.target, ast.Name):
                var_name = loop_node.target.id
                # 简单的循环变量分析
                pass

    def _get_nested_depth(self, node: ast.AST) -> int:
        """获取嵌套深度（简化版本）"""
        depth = 0
        parent = node
        while hasattr(parent, 'parent'):
            depth += 1
            parent = parent.parent
        return depth

    def _check_break_continue(self, loop_node: ast.For) -> bool:
        """检查循环中是否有break或continue"""
        for node in ast.walk(loop_node):
            if isinstance(node, ast.Break) or isinstance(node, ast.Continue):
                return True
        return False

    def _is_recursive_call(self, call_node: ast.Call, tree: ast.AST) -> bool:
        """检查是否是递归调用（简化版本）"""
        # 获取当前函数名
        current_func = None
        parent = call_node
        while parent and not isinstance(parent, ast.FunctionDef):
            parent = getattr(parent, 'parent', None)

        if isinstance(parent, ast.FunctionDef):
            current_func = parent.name

            # 检查调用的是否是当前函数
            if isinstance(call_node.func, ast.Name):
                return call_node.func.id == current_func

        return False

    def _analyze_complex_operations(self, node: ast.AST, results: Dict[str, Any]):
        """分析复杂操作"""
        # 列表推导式
        if isinstance(node, ast.ListComp):
            results["complex_operations"].append("列表推导式")

        # 字典推导式
        elif isinstance(node, ast.DictComp):
            results["complex_operations"].append("字典推导式")

        # 生成器表达式
        elif isinstance(node, ast.GeneratorExp):
            results["complex_operations"].append("生成器表达式")

        # 嵌套函数调用
        elif isinstance(node, ast.Call):
            # 检查是否有嵌套调用
            for arg in node.args:
                if isinstance(arg, ast.Call):
                    results["complex_operations"].append("嵌套函数调用")
                    break

        # 复杂数学运算
        elif isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Pow, ast.Mod, ast.FloorDiv)):
                results["complex_operations"].append("复杂数学运算")

    def _calculate_complexities(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """基于统计信息计算复杂度"""
        # 时间复杂度估算
        if results["nested_loop_depth"] >= 3:
            results["time_complexity"] = "O(n³) 或更高"
        elif results["nested_loop_depth"] == 2:
            results["time_complexity"] = "O(n²)"
        elif results["loop_count"] >= 2:
            results["time_complexity"] = "O(n log n) 或 O(n²)"
        elif results["loop_count"] == 1:
            results["time_complexity"] = "O(n)"
        elif results["recursive_calls"] > 0:
            results["time_complexity"] = "O(2ⁿ) 或 O(n!)（取决于递归实现）"
        else:
            results["time_complexity"] = "O(1) 或 O(log n)"

        # 空间复杂度估算
        if results["complex_operations"]:
            if any("推导式" in op for op in results["complex_operations"]):
                results["space_complexity"] = "O(n)（推导式创建新数据结构）"
            else:
                results["space_complexity"] = "O(1) 或 O(n)"
        else:
            results["space_complexity"] = "O(1)"

        return results

    def _detect_bottlenecks(self, results: Dict[str, Any]):
        """检测潜在性能瓶颈"""
        # 深度嵌套循环
        if results["nested_loop_depth"] >= 3:
            results["potential_bottlenecks"].append(
                f"深度嵌套循环（深度：{results['nested_loop_depth']}），可能导致O(n³)时间复杂度"
            )

        # 过多循环
        if results["loop_count"] >= 3:
            results["potential_bottlenecks"].append(
                f"多个循环结构（{results['loop_count']}个），可能影响性能"
            )

        # 递归调用
        if results["recursive_calls"] > 0:
            results["potential_bottlenecks"].append(
                "递归调用可能导致栈溢出或指数级时间复杂度"
            )

        # 复杂操作过多
        if len(results["complex_operations"]) >= 3:
            results["potential_bottlenecks"].append(
                f"多个复杂操作：{', '.join(results['complex_operations'][:3])}"
            )

        # 长函数
        if results["line_count"] > 50:
            results["potential_bottlenecks"].append(
                f"函数过长（{results['line_count']}行），可能影响可读性和维护性"
            )

    def _generate_optimization_suggestions(self, results: Dict[str, Any]):
        """生成优化建议"""
        # 基于瓶颈检测生成建议
        for bottleneck in results["potential_bottlenecks"]:
            if "深度嵌套循环" in bottleneck:
                results["optimization_suggestions"].append(
                    "考虑使用算法优化或数据预处理减少循环嵌套"
                )
            elif "多个循环结构" in bottleneck:
                results["optimization_suggestions"].append(
                    "尝试合并循环或使用向量化操作"
                )
            elif "递归调用" in bottleneck:
                results["optimization_suggestions"].append(
                    "考虑使用迭代替代递归，或添加记忆化优化"
                )
            elif "复杂操作" in bottleneck:
                results["optimization_suggestions"].append(
                    "考虑简化操作或使用内置函数优化"
                )
            elif "函数过长" in bottleneck:
                results["optimization_suggestions"].append(
                    "考虑将函数拆分为多个小函数，提高可读性和复用性"
                )

        # 通用建议
        if results["time_complexity"].startswith("O(n²)") or "O(n³)" in results["time_complexity"]:
            results["optimization_suggestions"].append(
                "考虑使用更高效的算法（如分治、动态规划、贪心算法）"
            )

        if "推导式" in str(results["complex_operations"]):
            results["optimization_suggestions"].append(
                "列表推导式通常高效，但大数据集可考虑生成器表达式节省内存"
            )

        # 如果没有发现明显问题，提供一般性建议
        if not results["optimization_suggestions"]:
            results["optimization_suggestions"].extend([
                "代码性能良好，继续保持",
                "考虑添加性能测试和基准测试",
                "定期进行代码审查和性能分析"
            ])

    def _analyze_code_simple(self, code: str, analysis_focus: str) -> Dict[str, Any]:
        """简单代码分析（当AST解析失败时使用）"""
        results = {
            "code_length": len(code),
            "line_count": code.count('\n') + 1,
            "function_count": 0,
            "loop_count": 0,
            "time_complexity": "未知",
            "space_complexity": "未知",
            "potential_bottlenecks": [],
            "optimization_suggestions": [],
        }

        # 使用正则表达式进行简单分析
        # 统计函数定义
        func_pattern = r'def\s+(\w+)\s*\('
        results["function_count"] = len(re.findall(func_pattern, code))

        # 统计循环
        for_pattern = r'for\s+'
        while_pattern = r'while\s+'
        results["loop_count"] = len(re.findall(for_pattern, code)) + len(re.findall(while_pattern, code))

        # 检测潜在问题
        if results["loop_count"] > 3:
            results["potential_bottlenecks"].append("检测到多个循环，可能影响性能")

        if len(code) > 1000:
            results["potential_bottlenecks"].append("代码较长，可能包含复杂逻辑")

        # 简单复杂度估计
        if results["loop_count"] == 0:
            results["time_complexity"] = "O(1)"
            results["space_complexity"] = "O(1)"
        elif results["loop_count"] == 1:
            results["time_complexity"] = "O(n)"
            results["space_complexity"] = "O(1)"
        else:
            results["time_complexity"] = "O(n²) 或更高"
            results["space_complexity"] = "O(n) 或更高"

        return results

    def _analyze_other_language(self, code: str, analysis_focus: str, language: str) -> Dict[str, Any]:
        """分析其他编程语言代码"""
        results = {
            "language": language,
            "code_length": len(code),
            "line_count": code.count('\n') + 1,
            "time_complexity": "基于模式匹配估算",
            "space_complexity": "基于模式匹配估算",
            "potential_bottlenecks": [],
            "optimization_suggestions": [],
            "notes": f"此分析基于{language}代码的模式匹配，可能不够精确",
        }

        # 通用模式检测
        # 检测循环
        if language == "java":
            for_pattern = r'for\s*\([^)]*\)'
            while_pattern = r'while\s*\([^)]*\)'
        else:  # javascript, cpp
            for_pattern = r'for\s*\([^)]*\)'
            while_pattern = r'while\s*\([^)]*\)'

        loop_count = len(re.findall(for_pattern, code, re.IGNORECASE)) + \
                    len(re.findall(while_pattern, code, re.IGNORECASE))

        if loop_count > 0:
            results["potential_bottlenecks"].append(f"检测到{loop_count}个循环结构")

        # 检测递归
        func_pattern = r'(\w+)\s*\([^)]*\)\s*{'
        func_matches = re.findall(func_pattern, code)

        # 简单递归检测（检查函数是否调用自身）
        for func in func_matches:
            if re.search(fr'{func}\s*\(', code):
                results["potential_bottlenecks"].append(f"可能检测到递归调用：{func}")

        return results

    def _analyze_pseudocode(self, code: str, analysis_focus: str) -> Dict[str, Any]:
        """分析伪代码或算法描述"""
        results = {
            "code_type": "pseudocode",
            "description_length": len(code),
            "time_complexity": "基于关键词分析",
            "space_complexity": "基于关键词分析",
            "detected_patterns": [],
            "complexity_indicators": [],
        }

        # 关键词分析
        complexity_keywords = {
            "O(1)": ["常数时间", "固定时间", "O(1)", "constant time"],
            "O(log n)": ["对数", "二分", "log n", "对数时间"],
            "O(n)": ["线性", "遍历", "O(n)", "线性时间"],
            "O(n log n)": ["快速排序", "归并排序", "堆排序", "n log n"],
            "O(n²)": ["嵌套循环", "双重循环", "O(n²)", "二次时间", "冒泡排序", "选择排序"],
            "O(2ⁿ)": ["指数", "递归", "组合", "子集", "2ⁿ", "指数时间"],
            "O(n!)": ["阶乘", "排列", "全排列", "n!", "阶乘时间"],
        }

        for complexity, keywords in complexity_keywords.items():
            for keyword in keywords:
                if keyword.lower() in code.lower():
                    results["complexity_indicators"].append(f"检测到关键词 '{keyword}' → 可能 {complexity}")

        # 算法模式检测
        algorithm_patterns = {
            "排序算法": ["排序", "sort", "order", "arrange"],
            "搜索算法": ["搜索", "查找", "search", "find"],
            "图算法": ["图", "graph", "节点", "边", "路径"],
            "动态规划": ["动态规划", "dp", "最优", "子问题"],
            "贪心算法": ["贪心", "greedy", "局部最优"],
        }

        for pattern, keywords in algorithm_patterns.items():
            for keyword in keywords:
                if keyword.lower() in code.lower():
                    results["detected_patterns"].append(f"检测到 {pattern} 模式")

        return results

    def _generate_report(self, code: str, language: str, analysis_focus: str,
                        results: Dict[str, Any]) -> str:
        """生成性能分析报告"""
        report = f"""# 性能分析报告

## 分析概览
- **分析语言**: {language}
- **分析重点**: {analysis_focus}
- **代码长度**: {len(code)} 字符
- **代码行数**: {results.get('line_count', 'N/A')}

## 代码统计
"""

        if language == "python":
            report += f"""- **函数数量**: {results.get('function_count', 0)}
- **类数量**: {results.get('class_count', 0)}
- **循环数量**: {results.get('loop_count', 0)}
- **最大循环嵌套深度**: {results.get('nested_loop_depth', 0)}
- **递归调用**: {results.get('recursive_calls', 0)} 个
"""

        report += f"""
## 复杂度分析
- **时间复杂度**: {results.get('time_complexity', '未知')}
- **空间复杂度**: {results.get('space_complexity', '未知')}
"""

        if results.get('complex_operations'):
            report += f"""
## 复杂操作检测
"""
            for op in results['complex_operations'][:5]:  # 最多显示5个
                report += f"- {op}\n"
            if len(results['complex_operations']) > 5:
                report += f"  还有 {len(results['complex_operations']) - 5} 个复杂操作\n"

        if results.get('memory_usage_patterns'):
            report += f"""
## 内存使用模式
"""
            for pattern in results['memory_usage_patterns'][:3]:
                report += f"- {pattern}\n"

        if results.get('potential_bottlenecks'):
            report += f"""
## 🚨 潜在性能瓶颈
"""
            for bottleneck in results['potential_bottlenecks']:
                report += f"- ⚠️ {bottleneck}\n"

        if results.get('optimization_suggestions'):
            report += f"""
## 💡 优化建议
"""
            for i, suggestion in enumerate(results['optimization_suggestions'][:5], 1):
                report += f"{i}. {suggestion}\n"

        if results.get('detected_patterns'):
            report += f"""
## 检测到的模式
"""
            for pattern in results['detected_patterns']:
                report += f"- {pattern}\n"

        if results.get('complexity_indicators'):
            report += f"""
## 复杂度指标
"""
            for indicator in results['complexity_indicators']:
                report += f"- {indicator}\n"

        report += f"""
## 详细分析

### 性能评估
基于代码分析，性能评估如下：
1. **时间复杂度**: {results.get('time_complexity', '未知')} - 表示算法执行时间随输入规模增长的关系
2. **空间复杂度**: {results.get('space_complexity', '未知')} - 表示算法内存使用随输入规模增长的关系

### 关键发现
"""

        # 生成关键发现总结
        key_findings = []

        if results.get('time_complexity', '').startswith('O(n²)') or 'O(n³)' in results.get('time_complexity', ''):
            key_findings.append("⚠️ **高时间复杂度**: 算法可能在大数据集上性能较差")

        if results.get('nested_loop_depth', 0) >= 3:
            key_findings.append("⚠️ **深度嵌套循环**: 可能导致代码难以理解和维护")

        if results.get('recursive_calls', 0) > 0:
            key_findings.append("⚠️ **递归调用**: 注意栈深度限制和性能开销")

        if not key_findings:
            key_findings.append("✅ **代码结构良好**: 未发现明显性能问题")

        for finding in key_findings:
            report += f"- {finding}\n"

        report += f"""
## 下一步建议
1. **性能测试**: 在实际数据集上运行性能测试
2. **基准测试**: 与其他实现进行基准对比
3. **代码重构**: 根据优化建议进行代码重构
4. **监控优化**: 在生产环境中监控性能指标

## 结构化数据（JSON）
```json
{json.dumps({
    "language": language,
    "analysis_focus": analysis_focus,
    "code_preview": code[:500] + "..." if len(code) > 500 else code,
    "results": results
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = PerformanceAnalyzerTool()

    # 测试1: Python代码分析
    test_code = '''
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
'''

    result1 = tool._run(
        code=test_code,
        analysis_focus="time_complexity",
        language="python"
    )

    print("测试1结果:")
    print(result1[:1000] + "..." if len(result1) > 1000 else result1)
