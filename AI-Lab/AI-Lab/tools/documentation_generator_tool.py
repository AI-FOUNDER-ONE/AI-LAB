"""
documentation_generator_tool.py - 文档生成工具
==========================================
供 Coder（程序员）使用，根据代码或需求自动生成文档。
支持多种文档类型：API文档、使用手册、技术文档、README等。

安全性审计:
  ✅ 仅分析文本，不执行代码
  ✅ 不读取代码以外的文件
  ✅ 输出结构化文档，无副作用
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


class DocumentationGeneratorInput(BaseModel):
    """DocumentationGeneratorTool 的输入参数模型。"""
    source: str = Field(
        ...,
        description=(
            "源内容。可以是：\n"
            "1. Python 代码字符串\n"
            "2. 需求描述文本\n"
            "3. API 接口定义\n"
            "4. 功能描述\n"
            "示例：一个Python函数代码或一段功能描述"
        )
    )
    doc_type: str = Field(
        default="api",
        description=(
            "文档类型。可选值：\n"
            "- 'api': API 文档（默认）\n"
            "- 'user_guide': 用户使用手册\n"
            "- 'technical': 技术设计文档\n"
            "- 'readme': README 文档\n"
            "- 'changelog': 更新日志\n"
            "- 'tutorial': 教程文档"
        )
    )
    format: str = Field(
        default="markdown",
        description=(
            "输出格式。可选值：\n"
            "- 'markdown': Markdown 格式（默认）\n"
            "- 'asciidoc': AsciiDoc 格式\n"
            "- 'restructuredtext': reStructuredText 格式"
        )
    )
    language: str = Field(
        default="python",
        description="源代码语言。目前主要支持Python。"
    )


class DocumentationGeneratorTool(BaseTool):
    """文档生成工具。

    根据代码或需求自动生成各种类型的文档。
    """

    name: str = "documentation_generator"
    description: str = (
        "根据代码或需求自动生成文档。"
        "支持API文档、用户手册、技术文档、README等多种类型。"
        "输入代码或描述，输出结构化文档。"
    )
    args_schema: Type[BaseModel] = DocumentationGeneratorInput

    def _run(self, source: str, doc_type: str = "api", format: str = "markdown",
             language: str = "python") -> str:
        """执行文档生成。

        Args:
            source: 源内容（代码或描述）
            doc_type: 文档类型
            format: 输出格式
            language: 源代码语言

        Returns:
            格式化的文档
        """
        try:
            if language.lower() != "python":
                # 目前主要支持Python，其他语言按文本处理
                print(f"[DocumentationGenerator] 警告: 主要支持Python，{language} 将按文本处理")

            # 1. 分析源内容
            source_info = self._analyze_source(source, language)

            # 2. 根据文档类型生成文档结构
            doc_structure = self._create_doc_structure(source_info, doc_type)

            # 3. 根据格式生成文档
            formatted_doc = self._format_document(doc_structure, format, doc_type)

            # 4. 生成完整报告
            return self._generate_report(source_info, doc_type, format, doc_structure, formatted_doc)

        except Exception as e:
            return f"❌ 文档生成失败: {str(e)}"

    def _analyze_source(self, source: str, language: str) -> Dict[str, Any]:
        """分析源内容"""
        info = {
            "type": "unknown",
            "language": language,
            "functions": [],
            "classes": [],
            "modules": [],
            "description": "",
            "complexity": "low",
        }

        # 尝试解析为Python代码
        if language.lower() == "python":
            try:
                tree = ast.parse(source)
                info["type"] = "python_code"

                # 提取函数信息
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_info = {
                            "name": node.name,
                            "line": node.lineno,
                            "args": self._extract_function_args(node),
                            "returns": self._extract_function_returns(node),
                            "docstring": ast.get_docstring(node) or "",
                        }
                        info["functions"].append(func_info)

                    elif isinstance(node, ast.ClassDef):
                        class_info = {
                            "name": node.name,
                            "line": node.lineno,
                            "methods": [],
                            "docstring": ast.get_docstring(node) or "",
                        }
                        for subnode in node.body:
                            if isinstance(subnode, ast.FunctionDef):
                                class_info["methods"].append(subnode.name)
                        info["classes"].append(class_info)

                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            info["modules"].append(alias.name)

                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            info["modules"].append(node.module)

                # 评估复杂度
                total_elements = len(info["functions"]) + len(info["classes"]) + len(info["modules"])
                if total_elements > 10:
                    info["complexity"] = "high"
                elif total_elements > 5:
                    info["complexity"] = "medium"

            except SyntaxError:
                # 如果不是有效Python代码，当作文本描述处理
                info["type"] = "text"
                info["description"] = source[:500] + "..." if len(source) > 500 else source

        else:
            # 其他语言当作文本处理
            info["type"] = "text"
            info["description"] = source[:500] + "..." if len(source) > 500 else source

        return info

    def _extract_function_args(self, func_node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """提取函数参数信息"""
        args = []

        # 普通参数
        for arg in func_node.args.args:
            args.append({
                "name": arg.arg,
                "type": "arg",
                "default": None,
            })

        # 默认参数
        defaults = func_node.args.defaults
        if defaults:
            # 从后往前匹配默认值
            for i, default in enumerate(reversed(defaults)):
                idx = len(func_node.args.args) - len(defaults) + i
                if idx < len(args):
                    if isinstance(default, ast.Constant):
                        args[idx]["default"] = repr(default.value)
                    else:
                        args[idx]["default"] = ast.unparse(default) if hasattr(ast, 'unparse') else str(default)

        # 可变参数
        if func_node.args.vararg:
            args.append({
                "name": func_node.args.vararg.arg,
                "type": "vararg",
                "default": None,
            })

        # 关键字参数
        if func_node.args.kwarg:
            args.append({
                "name": func_node.args.kwarg.arg,
                "type": "kwarg",
                "default": None,
            })

        return args

    def _extract_function_returns(self, func_node: ast.FunctionDef) -> Optional[str]:
        """提取函数返回值信息"""
        # 简单实现：检查是否有return语句
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return):
                if node.value:
                    if isinstance(node.value, ast.Constant):
                        return f"-> {type(node.value.value).__name__}"
                    else:
                        return "-> Any"
        return None

    def _create_doc_structure(self, source_info: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
        """根据源信息和文档类型创建文档结构"""
        structure = {
            "title": "",
            "sections": [],
            "metadata": {
                "generated_by": "DocumentationGeneratorTool",
                "source_type": source_info["type"],
                "complexity": source_info["complexity"],
            }
        }

        if doc_type == "api":
            structure["title"] = "API 文档"
            structure["sections"] = self._create_api_sections(source_info)
        elif doc_type == "user_guide":
            structure["title"] = "用户使用手册"
            structure["sections"] = self._create_user_guide_sections(source_info)
        elif doc_type == "technical":
            structure["title"] = "技术设计文档"
            structure["sections"] = self._create_technical_sections(source_info)
        elif doc_type == "readme":
            structure["title"] = "README"
            structure["sections"] = self._create_readme_sections(source_info)
        elif doc_type == "changelog":
            structure["title"] = "更新日志"
            structure["sections"] = self._create_changelog_sections(source_info)
        elif doc_type == "tutorial":
            structure["title"] = "教程文档"
            structure["sections"] = self._create_tutorial_sections(source_info)

        return structure

    def _create_api_sections(self, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建API文档章节"""
        sections = []

        # 概述
        sections.append({
            "title": "概述",
            "content": "本文档描述提供的API接口。",
            "level": 1,
        })

        # 函数文档
        if source_info["functions"]:
            sections.append({
                "title": "函数列表",
                "content": "以下函数可供调用：",
                "level": 1,
            })

            for func in source_info["functions"]:
                sections.append({
                    "title": f"函数: {func['name']}",
                    "content": self._format_function_doc(func),
                    "level": 2,
                })

        # 类文档
        if source_info["classes"]:
            sections.append({
                "title": "类列表",
                "content": "以下类可供使用：",
                "level": 1,
            })

            for cls in source_info["classes"]:
                sections.append({
                    "title": f"类: {cls['name']}",
                    "content": self._format_class_doc(cls),
                    "level": 2,
                })

        # 使用示例
        sections.append({
            "title": "使用示例",
            "content": "```python\n# 这里添加使用示例代码\n```",
            "level": 1,
        })

        return sections

    def _create_user_guide_sections(self, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建用户手册章节"""
        sections = []

        sections.append({
            "title": "用户使用手册",
            "content": "本手册指导用户如何使用该软件。",
            "level": 1,
        })

        sections.append({
            "title": "快速开始",
            "content": "### 安装\n```bash\npip install package_name\n```\n\n### 基本使用\n```python\nimport module\n# 示例代码\n```",
            "level": 1,
        })

        if source_info["functions"]:
            sections.append({
                "title": "功能说明",
                "content": "### 主要功能\n" + "\n".join([f"- {func['name']}: {func['docstring'][:100] if func['docstring'] else '暂无描述'}" for func in source_info["functions"][:5]]),
                "level": 1,
            })

        sections.append({
            "title": "常见问题",
            "content": "### Q1: 如何安装？\nA: 使用pip安装。\n\n### Q2: 如何配置？\nA: 参考配置说明。",
            "level": 1,
        })

        return sections

    def _create_technical_sections(self, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建技术文档章节"""
        sections = []

        sections.append({
            "title": "技术设计文档",
            "content": "本文档描述系统的技术架构和设计。",
            "level": 1,
        })

        sections.append({
            "title": "架构设计",
            "content": "### 整体架构\n描述系统整体架构。\n\n### 组件设计\n描述各个组件功能。",
            "level": 1,
        })

        if source_info["functions"] or source_info["classes"]:
            sections.append({
                "title": "核心实现",
                "content": "### 关键函数\n" + "\n".join([f"- {func['name']}: 第{func['line']}行，参数: {len(func['args'])}个" for func in source_info["functions"][:3]]) +
                          "\n\n### 关键类\n" + "\n".join([f"- {cls['name']}: 第{cls['line']}行，方法: {len(cls['methods'])}个" for cls in source_info["classes"][:3]]),
                "level": 1,
            })

        sections.append({
            "title": "性能考虑",
            "content": "### 时间复杂度\n分析关键操作的时间复杂度。\n\n### 空间复杂度\n分析内存使用情况。",
            "level": 1,
        })

        return sections

    def _create_readme_sections(self, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建README章节"""
        sections = []

        sections.append({
            "title": "项目名称",
            "content": "简短的项目描述。",
            "level": 1,
        })

        sections.append({
            "title": "功能特性",
            "content": "- 功能1: 描述\n- 功能2: 描述\n- 功能3: 描述",
            "level": 2,
        })

        sections.append({
            "title": "安装",
            "content": "```bash\npip install package_name\n```",
            "level": 2,
        })

        sections.append({
            "title": "快速开始",
            "content": "```python\nimport package\n\n# 示例代码\nresult = package.do_something()\nprint(result)\n```",
            "level": 2,
        })

        if source_info["functions"]:
            sections.append({
                "title": "API参考",
                "content": "主要函数：\n" + "\n".join([f"- `{func['name']}()`: {func['docstring'][:80] if func['docstring'] else '函数'}" for func in source_info["functions"][:3]]),
                "level": 2,
            })

        sections.append({
            "title": "贡献",
            "content": "欢迎提交Issue和Pull Request。",
            "level": 2,
        })

        sections.append({
            "title": "许可证",
            "content": "MIT License",
            "level": 2,
        })

        return sections

    def _create_changelog_sections(self, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建更新日志章节"""
        sections = []

        sections.append({
            "title": "更新日志",
            "content": "记录项目的重要变更。",
            "level": 1,
        })

        sections.append({
            "title": "[版本号] - 日期",
            "content": "### 新增\n- 功能1\n- 功能2\n\n### 修复\n- 问题1\n- 问题2\n\n### 变更\n- 调整1\n- 调整2",
            "level": 2,
        })

        return sections

    def _create_tutorial_sections(self, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建教程章节"""
        sections = []

        sections.append({
            "title": "教程",
            "content": "本教程指导用户学习如何使用该软件。",
            "level": 1,
        })

        sections.append({
            "title": "第一章: 入门",
            "content": "### 1.1 安装\n安装步骤说明。\n\n### 1.2 配置\n配置方法说明。",
            "level": 1,
        })

        sections.append({
            "title": "第二章: 基本使用",
            "content": "### 2.1 第一个示例\n```python\n# 示例代码\nprint(\"Hello World\")\n```\n\n### 2.2 常用操作\n常用操作说明。",
            "level": 1,
        })

        if source_info["functions"]:
            sections.append({
                "title": "第三章: 高级功能",
                "content": "### 3.1 高级函数\n" + "\n".join([f"- {func['name']}: {func['docstring'][:100] if func['docstring'] else '高级功能'}" for func in source_info["functions"][:2]]) + "\n\n### 3.2 最佳实践\n使用建议和最佳实践。",
                "level": 1,
            })

        return sections

    def _format_function_doc(self, func: Dict[str, Any]) -> str:
        """格式化函数文档"""
        doc = f"**函数**: `{func['name']}`\n\n"

        if func['docstring']:
            doc += f"{func['docstring']}\n\n"

        doc += "**参数**:\n"
        for arg in func['args']:
            default_str = f" = {arg['default']}" if arg['default'] else ""
            doc += f"- `{arg['name']}`{default_str}: 参数描述\n"

        if func['returns']:
            doc += f"\n**返回值**: {func['returns']}\n"

        doc += f"\n**位置**: 第{func['line']}行\n"

        return doc

    def _format_class_doc(self, cls: Dict[str, Any]) -> str:
        """格式化类文档"""
        doc = f"**类**: `{cls['name']}`\n\n"

        if cls['docstring']:
            doc += f"{cls['docstring']}\n\n"

        if cls['methods']:
            doc += "**方法**:\n"
            for method in cls['methods']:
                doc += f"- `{method}()`: 方法描述\n"

        doc += f"\n**位置**: 第{cls['line']}行\n"

        return doc

    def _format_document(self, doc_structure: Dict[str, Any], format: str, doc_type: str) -> str:
        """根据格式生成文档"""
        if format == "markdown":
            return self._format_markdown(doc_structure)
        elif format == "asciidoc":
            return self._format_asciidoc(doc_structure)
        elif format == "restructuredtext":
            return self._format_restructuredtext(doc_structure)
        else:
            return self._format_markdown(doc_structure)  # 默认Markdown

    def _format_markdown(self, doc_structure: Dict[str, Any]) -> str:
        """格式化为Markdown"""
        lines = []
        lines.append(f"# {doc_structure['title']}\n")

        for section in doc_structure['sections']:
            level = section['level']
            title = section['title']
            content = section['content']

            if level == 1:
                lines.append(f"## {title}\n")
            elif level == 2:
                lines.append(f"### {title}\n")
            elif level == 3:
                lines.append(f"#### {title}\n")
            else:
                lines.append(f"# {title}\n")

            lines.append(f"{content}\n")

        return "\n".join(lines)

    def _format_asciidoc(self, doc_structure: Dict[str, Any]) -> str:
        """格式化为AsciiDoc"""
        lines = []
        lines.append(f"= {doc_structure['title']}\n")

        for section in doc_structure['sections']:
            level = section['level']
            title = section['title']
            content = section['content']

            if level == 1:
                lines.append(f"== {title}\n")
            elif level == 2:
                lines.append(f"=== {title}\n")
            elif level == 3:
                lines.append(f"==== {title}\n")
            else:
                lines.append(f"= {title}\n")

            # 简单转换Markdown到AsciiDoc
            content = content.replace("```python", "[source,python]\n----")
            content = content.replace("```", "----")
            content = content.replace("**", "*")
            content = content.replace("`", "`")

            lines.append(f"{content}\n")

        return "\n".join(lines)

    def _format_restructuredtext(self, doc_structure: Dict[str, Any]) -> str:
        """格式化为reStructuredText"""
        lines = []
        lines.append(f"{doc_structure['title']}\n")
        lines.append("=" * len(doc_structure['title']) + "\n")

        for section in doc_structure['sections']:
            level = section['level']
            title = section['title']
            content = section['content']

            lines.append(f"{title}\n")
            if level == 1:
                lines.append("-" * len(title) + "\n")
            elif level == 2:
                lines.append("~" * len(title) + "\n")
            elif level == 3:
                lines.append("." * len(title) + "\n")

            # 简单转换Markdown到reStructuredText
            content = content.replace("```python", ".. code-block:: python\n\n   ")
            content = content.replace("```", "\n")
            content = re.sub(r"\*\*(.+?)\*\*", r"**\1**", content)
            content = re.sub(r"`(.+?)`", r"``\1``", content)

            lines.append(f"{content}\n")

        return "\n".join(lines)

    def _generate_report(self, source_info: Dict[str, Any], doc_type: str, format: str,
                        doc_structure: Dict[str, Any], formatted_doc: str) -> str:
        """生成完整报告"""
        report = f"""# 文档生成报告

## 生成概览
- **源内容类型**: {source_info['type']}
- **文档类型**: {doc_type}
- **输出格式**: {format}
- **源内容复杂度**: {source_info['complexity']}

## 源内容分析
- **函数数量**: {len(source_info['functions'])}
- **类数量**: {len(source_info['classes'])}
- **模块数量**: {len(source_info['modules'])}
"""

        if source_info['functions']:
            report += "\n### 主要函数\n"
            for func in source_info['functions'][:3]:
                report += f"- `{func['name']}`: 第{func['line']}行，{len(func['args'])}个参数\n"

        if source_info['classes']:
            report += "\n### 主要类\n"
            for cls in source_info['classes'][:3]:
                report += f"- `{cls['name']}`: 第{cls['line']}行，{len(cls['methods'])}个方法\n"

        report += f"""
## 生成的文档结构
文档标题: {doc_structure['title']}
章节数量: {len(doc_structure['sections'])}
"""

        report += f"""
## 生成的文档内容 ({format.upper()} 格式)
```{format}
{formatted_doc}
```

## 使用说明
1. 将生成的文档保存为对应格式的文件
2. 根据需要补充具体内容和示例
3. 保持文档与代码同步更新

## 结构化数据（JSON）
```json
{json.dumps({
    "source_info": source_info,
    "doc_config": {"type": doc_type, "format": format},
    "doc_structure": doc_structure,
    "metadata": doc_structure["metadata"]
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = DocumentationGeneratorTool()

    test_code = '''
def calculate_sum(a: int, b: int) -> int:
    """计算两个整数的和

    Args:
        a: 第一个整数
        b: 第二个整数

    Returns:
        两个整数的和
    """
    return a + b

class DataProcessor:
    """数据处理类"""

    def __init__(self, data):
        self.data = data

    def process(self):
        """处理数据"""
        return [item * 2 for item in self.data]
'''

    result = tool._run(
        source=test_code,
        doc_type="api",
        format="markdown",
        language="python"
    )

    print("测试结果:")
    print(result)