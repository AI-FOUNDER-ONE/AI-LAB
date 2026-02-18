"""
tools/__init__.py - 工具包统一导出
===================================
导出所有自定义 Agent 工具，方便统一导入。

工具清单:
  - DocxParserTool:        深度解析文档（CKO 使用）
  - CodeWriterTool:        代码写入（Coder 使用）
  - MermaidTool:           Mermaid 图表生成（Arch 使用）
  - MatplotlibDesignTool:  设计图生成（Designer 使用）
  - DocxGeneratorTool:     生成 Word 文档（Coder 使用）
  - ValidationTool:        代码静态验证（Tester 使用）
  - parse_document:        统一文档解析入口函数
"""

from tools.crew_tools import DocxParserTool, CodeWriterTool
from tools.mermaid_tool import MermaidTool
from tools.matplotlib_design_tool import MatplotlibDesignTool
from tools.docx_generator_tool import DocxGeneratorTool
from tools.validation_tool import ValidationTool
from tools.document_parser import parse_document, ParsedDocument

__all__ = [
    "DocxParserTool",
    "CodeWriterTool",
    "MermaidTool",
    "MatplotlibDesignTool",
    "DocxGeneratorTool",
    "ValidationTool",
    "parse_document",
    "ParsedDocument",
]
