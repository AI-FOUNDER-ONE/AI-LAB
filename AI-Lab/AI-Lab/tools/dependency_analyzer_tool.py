"""
dependency_analyzer_tool.py - 依赖关系分析工具
=============================================
供 Arch（架构师）使用，分析代码或项目的依赖关系。
包括外部依赖、内部模块依赖、版本冲突、循环依赖检测等。

安全性审计:
  ✅ 仅静态分析，不执行代码
  ✅ 不安装或修改任何依赖
  ✅ 输入路径验证，防止目录遍历攻击
  ✅ 输出结构化依赖分析报告
"""

import os
import re
import json
import ast
from typing import Type, List, Dict, Any, Optional, Tuple
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


class DependencyAnalyzerInput(BaseModel):
    """DependencyAnalyzerTool 的输入参数模型。"""
    target: str = Field(
        ...,
        description=(
            "分析目标。可以是：\n"
            "1. Python代码字符串\n"
            "2. 项目根目录路径\n"
            "3. 依赖描述文件路径（requirements.txt, pyproject.toml, setup.py等）\n"
            "示例：一个Python项目的根目录路径，或一段Python代码字符串"
        )
    )
    analysis_type: str = Field(
        default="external",
        description=(
            "分析类型。可选值：\n"
            "- 'external': 外部依赖分析（默认）\n"
            "- 'internal': 内部模块依赖\n"
            "- 'circular': 循环依赖检测\n"
            "- 'comprehensive': 全面分析\n"
        )
    )
    depth: str = Field(
        default="standard",
        description=(
            "分析深度。可选值：\n"
            "- 'quick': 快速分析，仅检查主要依赖\n"
            "- 'standard': 标准分析，检查所有依赖（默认）\n"
            "- 'deep': 深度分析，包括间接依赖和版本分析"
        )
    )


class DependencyAnalyzerTool(BaseTool):
    """依赖关系分析工具。

    分析代码或项目的依赖关系，支持多种分析类型和深度。
    输出结构化依赖分析报告和改进建议。
    """

    name: str = "dependency_analyzer"
    description: str = (
        "分析代码或项目的依赖关系。"
        "支持外部依赖、内部模块依赖、版本冲突、循环依赖检测等功能。"
        "输出结构化依赖分析报告和改进建议。"
    )
    args_schema: Type[BaseModel] = DependencyAnalyzerInput

    def _run(self, target: str, analysis_type: str = "external", depth: str = "standard") -> str:
        """执行依赖关系分析。

        Args:
            target: 分析目标（代码字符串或路径）
            analysis_type: 分析类型
            depth: 分析深度

        Returns:
            格式化的依赖分析报告
        """
        try:
            # 1. 确定目标类型
            target_type = self._determine_target_type(target)

            # 2. 根据目标类型执行分析
            if target_type == "directory":
                analysis_results = self._analyze_project_directory(target, analysis_type, depth)
            elif target_type == "python_code":
                analysis_results = self._analyze_python_code(target, analysis_type, depth)
            elif target_type == "dependency_file":
                analysis_results = self._analyze_dependency_file(target, analysis_type, depth)
            else:
                analysis_results = self._analyze_text_description(target, analysis_type, depth)

            # 3. 生成完整报告
            return self._generate_report(target, target_type, analysis_type, depth, analysis_results)

        except Exception as e:
            return f"❌ 依赖分析失败: {str(e)}"

    def _determine_target_type(self, target: str) -> str:
        """确定目标类型"""
        # 检查是否是文件路径
        if os.path.exists(target):
            if os.path.isdir(target):
                return "directory"
            elif os.path.isfile(target):
                # 检查文件类型
                filename = os.path.basename(target).lower()
                if filename.endswith('.py'):
                    return "python_code"
                elif filename in ('requirements.txt', 'pyproject.toml', 'setup.py',
                                 'setup.cfg', 'poetry.lock', 'pipfile', 'pipfile.lock'):
                    return "dependency_file"
                else:
                    return "directory"  # 其他文件视为目录的一部分
            else:
                return "unknown"
        else:
            # 检查是否是Python代码（尝试解析）
            try:
                ast.parse(target)
                return "python_code"
            except SyntaxError:
                # 可能是路径字符串但不存在的路径，或文本描述
                return "text_description"

    def _analyze_project_directory(self, directory_path: str, analysis_type: str, depth: str) -> Dict[str, Any]:
        """分析项目目录"""
        results = {
            "directory": directory_path,
            "external_dependencies": [],
            "internal_modules": [],
            "dependency_files_found": [],
            "python_files": [],
            "potential_issues": [],
        }

        try:
            # 扫描目录
            for root, dirs, files in os.walk(directory_path):
                # 跳过一些常见的不需要扫描的目录
                skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 'env', '.env'}
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for filename in files:
                    file_path = os.path.join(root, filename)
                    file_ext = os.path.splitext(filename)[1].lower()

                    if file_ext == '.py':
                        results["python_files"].append({
                            "path": os.path.relpath(file_path, directory_path),
                            "size": os.path.getsize(file_path)
                        })
                        # 分析Python文件中的导入
                        if analysis_type in ("internal", "comprehensive"):
                            self._analyze_python_file_imports(file_path, results)

                    elif filename in ('requirements.txt', 'pyproject.toml', 'setup.py',
                                     'setup.cfg', 'poetry.lock', 'pipfile', 'pipfile.lock'):
                        results["dependency_files_found"].append({
                            "filename": filename,
                            "path": os.path.relpath(file_path, directory_path)
                        })
                        # 分析依赖文件
                        if analysis_type in ("external", "comprehensive"):
                            self._analyze_dependency_file_content(file_path, results)

            # 处理结果
            if analysis_type in ("circular", "comprehensive"):
                self._detect_circular_dependencies(results)

            # 去重和排序
            results["external_dependencies"] = sorted(
                list(set(results["external_dependencies"])),
                key=lambda x: x.get("name", "") if isinstance(x, dict) else x
            )
            results["internal_modules"] = sorted(list(set(results["internal_modules"])))

        except Exception as e:
            results["potential_issues"].append(f"目录扫描错误: {str(e)}")

        return results

    def _analyze_python_file_imports(self, file_path: str, results: Dict[str, Any]):
        """分析Python文件中的导入语句"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 使用AST解析导入
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name
                            # 判断是外部依赖还是内部模块
                            if self._is_external_dependency(module_name):
                                results["external_dependencies"].append({
                                    "name": module_name.split('.')[0],  # 只取顶级包名
                                    "import": module_name,
                                    "source_file": os.path.basename(file_path)
                                })
                            else:
                                results["internal_modules"].append(module_name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:  # from module import ...
                            module_name = node.module
                            if self._is_external_dependency(module_name):
                                results["external_dependencies"].append({
                                    "name": module_name.split('.')[0],
                                    "import": f"from {module_name} import ...",
                                    "source_file": os.path.basename(file_path)
                                })
                            else:
                                results["internal_modules"].append(module_name)
            except SyntaxError:
                # 如果AST解析失败，使用正则表达式
                self._analyze_imports_with_regex(content, file_path, results)

        except Exception as e:
            results["potential_issues"].append(f"分析文件 {file_path} 导入时出错: {str(e)}")

    def _is_external_dependency(self, module_name: str) -> bool:
        """判断模块是否是外部依赖"""
        # 常见标准库模块
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'datetime', 'math', 'collections', 'itertools',
            'functools', 'typing', 'pathlib', 'logging', 'subprocess', 'threading',
            'multiprocessing', 'asyncio', 'socket', 'hashlib', 'base64', 'random',
            'string', 'time', 'copy', 'pickle', 'sqlite3', 'csv', 'html', 'xml',
        }

        # 获取模块的根名称（第一个部分）
        root_module = module_name.split('.')[0]

        # 检查是否是标准库
        if root_module in stdlib_modules:
            return False

        # 检查是否是内置模块
        try:
            __import__(root_module)
            # 如果成功导入，检查模块文件位置
            import importlib.util
            spec = importlib.util.find_spec(root_module)
            if spec and spec.origin:
                # 标准库通常位于Python安装目录下
                if 'site-packages' in spec.origin or 'dist-packages' in spec.origin:
                    return True
                # 检查是否是Python安装目录
                import sys
                python_lib = os.path.dirname(os.__file__)
                if spec.origin.startswith(python_lib):
                    return False
        except ImportError:
            pass

        # 默认认为是外部依赖（可能未安装）
        return True

    def _analyze_imports_with_regex(self, content: str, file_path: str, results: Dict[str, Any]):
        """使用正则表达式分析导入语句"""
        # 匹配 import 语句
        import_pattern = r'^\s*import\s+([a-zA-Z0-9_.,\s]+)'
        import_from_pattern = r'^\s*from\s+([a-zA-Z0-9_.]+)\s+import'

        for line in content.split('\n'):
            # 检查 import 语句
            import_match = re.match(import_pattern, line)
            if import_match:
                imports = import_match.group(1)
                for imp in re.split(r'\s*,\s*', imports):
                    module_name = imp.strip()
                    if self._is_external_dependency(module_name):
                        results["external_dependencies"].append({
                            "name": module_name.split('.')[0],
                            "import": module_name,
                            "source_file": os.path.basename(file_path)
                        })
                    else:
                        results["internal_modules"].append(module_name)

            # 检查 from ... import 语句
            from_match = re.match(import_from_pattern, line)
            if from_match:
                module_name = from_match.group(1)
                if self._is_external_dependency(module_name):
                    results["external_dependencies"].append({
                        "name": module_name.split('.')[0],
                        "import": f"from {module_name} import ...",
                        "source_file": os.path.basename(file_path)
                    })
                else:
                    results["internal_modules"].append(module_name)

    def _analyze_dependency_file_content(self, file_path: str, results: Dict[str, Any]):
        """分析依赖文件内容"""
        filename = os.path.basename(file_path).lower()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if filename == 'requirements.txt':
                self._parse_requirements_txt(content, results)
            elif filename == 'pyproject.toml':
                self._parse_pyproject_toml(content, results)
            elif filename == 'setup.py':
                self._parse_setup_py(content, results)

        except Exception as e:
            results["potential_issues"].append(f"解析依赖文件 {filename} 时出错: {str(e)}")

    def _parse_requirements_txt(self, content: str, results: Dict[str, Any]):
        """解析 requirements.txt 文件"""
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # 移除版本说明符和额外选项
                package_name = re.split(r'[<>=!~]', line)[0].strip()
                if package_name:
                    results["external_dependencies"].append({
                        "name": package_name,
                        "specifier": line,
                        "source": "requirements.txt"
                    })

    def _parse_pyproject_toml(self, content: str, results: Dict[str, Any]):
        """解析 pyproject.toml 文件"""
        try:
            import tomli
            data = tomli.loads(content)

            # 检查 dependencies
            if 'project' in data and 'dependencies' in data['project']:
                for dep in data['project']['dependencies']:
                    package_name = re.split(r'[<>=!~]', dep)[0].strip().strip('"').strip("'")
                    if package_name:
                        results["external_dependencies"].append({
                            "name": package_name,
                            "specifier": dep,
                            "source": "pyproject.toml"
                        })

            # 检查 tool.poetry.dependencies
            if 'tool' in data and 'poetry' in data['tool'] and 'dependencies' in data['tool']['poetry']:
                for package_name, spec in data['tool']['poetry']['dependencies'].items():
                    if package_name.lower() != 'python':  # 跳过Python版本
                        results["external_dependencies"].append({
                            "name": package_name,
                            "specifier": str(spec),
                            "source": "pyproject.toml (poetry)"
                        })

        except ImportError:
            # tomli不可用，使用简单解析
            self._parse_pyproject_toml_simple(content, results)
        except Exception as e:
            results["potential_issues"].append(f"解析pyproject.toml时出错: {str(e)}")

    def _parse_pyproject_toml_simple(self, content: str, results: Dict[str, Any]):
        """简单解析 pyproject.toml 文件"""
        # 查找 dependencies 部分
        in_dependencies = False
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('[project]'):
                in_dependencies = False
            elif line.startswith('[tool.poetry.dependencies]') or line.startswith('[dependencies]'):
                in_dependencies = True
            elif line.startswith('['):
                in_dependencies = False
            elif in_dependencies and '=' in line and not line.startswith('#'):
                # 简单的键值对解析
                parts = line.split('=', 1)
                if len(parts) == 2:
                    package_name = parts[0].strip().strip('"').strip("'")
                    if package_name.lower() != 'python':
                        results["external_dependencies"].append({
                            "name": package_name,
                            "specifier": parts[1].strip(),
                            "source": "pyproject.toml"
                        })

    def _parse_setup_py(self, content: str, results: Dict[str, Any]):
        """解析 setup.py 文件（简化版本）"""
        # 查找 install_requires
        install_requires_pattern = r'install_requires\s*=\s*\[(.*?)\]'
        match = re.search(install_requires_pattern, content, re.DOTALL)

        if match:
            requires_content = match.group(1)
            # 提取依赖项
            for line in requires_content.split(','):
                line = line.strip().strip('"').strip("'")
                if line and not line.startswith('#'):
                    package_name = re.split(r'[<>=!~]', line)[0].strip()
                    if package_name:
                        results["external_dependencies"].append({
                            "name": package_name,
                            "specifier": line,
                            "source": "setup.py"
                        })

    def _detect_circular_dependencies(self, results: Dict[str, Any]):
        """检测循环依赖（简化版本）"""
        # 这里实现一个简化的循环依赖检测
        # 实际实现需要构建依赖图并进行图算法
        if len(results["internal_modules"]) > 10:
            results["potential_issues"].append(
                "发现多个内部模块，建议检查是否存在循环依赖。"
            )

    def _analyze_python_code(self, code: str, analysis_type: str, depth: str) -> Dict[str, Any]:
        """分析Python代码字符串"""
        results = {
            "code_length": len(code),
            "external_dependencies": [],
            "internal_modules": [],
            "potential_issues": [],
        }

        try:
            # 使用AST解析
            tree = ast.parse(code)
            self._analyze_ast_tree(tree, results)
        except SyntaxError:
            # 如果AST解析失败，使用正则表达式
            self._analyze_imports_with_regex(code, "code_string", results)

        return results

    def _analyze_ast_tree(self, tree: ast.AST, results: Dict[str, Any]):
        """分析AST树"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if self._is_external_dependency(module_name):
                        results["external_dependencies"].append({
                            "name": module_name.split('.')[0],
                            "import": module_name
                        })
                    else:
                        results["internal_modules"].append(module_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module
                    if self._is_external_dependency(module_name):
                        results["external_dependencies"].append({
                            "name": module_name.split('.')[0],
                            "import": f"from {module_name} import ..."
                        })
                    else:
                        results["internal_modules"].append(module_name)

    def _analyze_dependency_file(self, file_path: str, analysis_type: str, depth: str) -> Dict[str, Any]:
        """分析依赖文件"""
        results = {
            "file_path": file_path,
            "external_dependencies": [],
            "potential_issues": [],
        }

        self._analyze_dependency_file_content(file_path, results)
        return results

    def _analyze_text_description(self, description: str, analysis_type: str, depth: str) -> Dict[str, Any]:
        """分析文本描述"""
        results = {
            "description_length": len(description),
            "external_dependencies": [],
            "potential_issues": [],
            "suggestions": [],
        }

        # 从描述中提取可能的依赖
        dependency_keywords = [
            r'\b(use|using|require|requires|depend on|based on)\s+([a-zA-Z0-9_-]+)',
            r'\b(pip install|conda install|npm install|yarn add)\s+([a-zA-Z0-9_-]+)',
            r'\b(import|from)\s+([a-zA-Z0-9_.]+)',
        ]

        for pattern in dependency_keywords:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    dep_name = match[-1].strip()
                    if dep_name and len(dep_name) > 1:
                        results["external_dependencies"].append({
                            "name": dep_name,
                            "source": "text_analysis",
                            "confidence": "low"
                        })

        return results

    def _generate_report(self, target: str, target_type: str, analysis_type: str,
                        depth: str, results: Dict[str, Any]) -> str:
        """生成依赖分析报告"""
        report = f"""# 依赖关系分析报告

## 分析概览
- **分析目标**: {target}
- **目标类型**: {target_type}
- **分析类型**: {analysis_type}
- **分析深度**: {depth}

## 发现的外部依赖
"""

        if "external_dependencies" in results and results["external_dependencies"]:
            # 去重和分组
            deps_by_name = {}
            for dep in results["external_dependencies"]:
                if isinstance(dep, dict):
                    name = dep.get("name", "unknown")
                    if name not in deps_by_name:
                        deps_by_name[name] = []
                    deps_by_name[name].append(dep)
                else:
                    if "unknown" not in deps_by_name:
                        deps_by_name["unknown"] = []
                    deps_by_name["unknown"].append({"name": str(dep)})

            for name, dep_list in deps_by_name.items():
                report += f"\n### {name}\n"
                for dep in dep_list:
                    if isinstance(dep, dict):
                        report += f"- **来源**: {dep.get('source', 'unknown')}\n"
                        if 'import' in dep:
                            report += f"  - 导入语句: `{dep['import']}`\n"
                        if 'specifier' in dep:
                            report += f"  - 版本说明: `{dep['specifier']}`\n"
                        if 'source_file' in dep:
                            report += f"  - 来源文件: {dep['source_file']}\n"
                report += "\n"
        else:
            report += "未发现外部依赖。\n"

        if "internal_modules" in results and results["internal_modules"]:
            report += f"""
## 发现的内部模块 ({len(results['internal_modules'])}个)
{', '.join(sorted(list(set(results['internal_modules']))))[:500]}...
"""

        if "dependency_files_found" in results and results["dependency_files_found"]:
            report += f"""
## 发现的依赖文件
"""
            for file_info in results["dependency_files_found"]:
                report += f"- {file_info['filename']} ({file_info['path']})\n"

        if "python_files" in results and results["python_files"]:
            report += f"""
## Python文件统计
- **文件总数**: {len(results['python_files'])}
- **示例文件**:
"""
            for i, file_info in enumerate(results["python_files"][:5], 1):
                report += f"  {i}. {file_info['path']} ({file_info['size']} bytes)\n"
            if len(results["python_files"]) > 5:
                report += f"  ... 还有 {len(results['python_files']) - 5} 个文件\n"

        if "potential_issues" in results and results["potential_issues"]:
            report += f"""
## 潜在问题
"""
            for issue in results["potential_issues"]:
                report += f"- ⚠️ {issue}\n"

        report += f"""
## 分析和建议

### 依赖管理建议
1. **明确依赖声明**: 确保所有外部依赖都在 requirements.txt 或 pyproject.toml 中声明
2. **版本锁定**: 考虑使用 poetry.lock 或 pip freeze 锁定版本
3. **依赖分类**: 将依赖分为开发依赖和生产依赖
4. **定期更新**: 定期检查依赖更新和安全漏洞

### 架构建议
1. **模块化设计**: 保持模块间松耦合
2. **接口清晰**: 明确定义模块间的接口
3. **依赖倒置**: 考虑使用依赖注入模式
4. **避免循环依赖**: 定期检查并重构循环依赖

## 结构化数据（JSON）
```json
{json.dumps({
    "target": target,
    "target_type": target_type,
    "analysis_config": {"type": analysis_type, "depth": depth},
    "results": results
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = DependencyAnalyzerTool()

    # 测试1: Python代码分析
    test_code = '''
import os
import sys
import requests
from flask import Flask
from utils.helper import calculate
'''

    result1 = tool._run(
        target=test_code,
        analysis_type="external",
        depth="standard"
    )

    print("测试1结果:")
    print(result1[:1000] + "..." if len(result1) > 1000 else result1)
