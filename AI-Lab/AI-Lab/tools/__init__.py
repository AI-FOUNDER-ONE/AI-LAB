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
  - RequirementsAnalyzerTool: 需求分析（CKO 使用）
  - CodeReviewTool:        代码审查（Coder 使用）
  - DocumentationGeneratorTool: 文档生成（Coder 使用）
  - TestCaseGeneratorTool: 测试用例生成（Tester 使用）
  - ArchitectureEvaluatorTool: 架构评估（Arch 使用）
  - ValidationTool:        代码静态验证（Tester 使用）
  - RiskAssessmentTool:    风险评估（PM 使用）
  - UIPatternGeneratorTool: UI设计模式生成（Designer 使用）
  - KnowledgeRetrievalTool: 知识检索（CKO 使用）
  - DependencyAnalyzerTool: 依赖关系分析（Arch 使用）
  - PerformanceAnalyzerTool: 性能分析（Tester 使用）
  - parse_document:        统一文档解析入口函数
"""

# 优雅导入工具，允许crewai缺失
try:
    from tools.crew_tools import DocxParserTool, CodeWriterTool
except ImportError:
    DocxParserTool = None
    CodeWriterTool = None
    print("[tools] 警告: crew_tools导入失败，DocxParserTool和CodeWriterTool不可用")

try:
    from tools.mermaid_tool import MermaidTool
except ImportError:
    MermaidTool = None
    print("[tools] 警告: mermaid_tool导入失败，MermaidTool不可用")

try:
    from tools.matplotlib_design_tool import MatplotlibDesignTool
except ImportError:
    MatplotlibDesignTool = None
    print("[tools] 警告: matplotlib_design_tool导入失败，MatplotlibDesignTool不可用")

try:
    from tools.docx_generator_tool import DocxGeneratorTool
except ImportError:
    DocxGeneratorTool = None
    print("[tools] 警告: docx_generator_tool导入失败，DocxGeneratorTool不可用")

try:
    from tools.requirements_analyzer_tool import RequirementsAnalyzerTool
except ImportError:
    RequirementsAnalyzerTool = None
    print("[tools] 警告: requirements_analyzer_tool导入失败，RequirementsAnalyzerTool不可用")

try:
    from tools.code_review_tool import CodeReviewTool
except ImportError:
    CodeReviewTool = None
    print("[tools] 警告: code_review_tool导入失败，CodeReviewTool不可用")

try:
    from tools.test_case_generator_tool import TestCaseGeneratorTool
except ImportError:
    TestCaseGeneratorTool = None
    print("[tools] 警告: test_case_generator_tool导入失败，TestCaseGeneratorTool不可用")

try:
    from tools.architecture_evaluator_tool import ArchitectureEvaluatorTool
except ImportError:
    ArchitectureEvaluatorTool = None
    print("[tools] 警告: architecture_evaluator_tool导入失败，ArchitectureEvaluatorTool不可用")

try:
    from tools.documentation_generator_tool import DocumentationGeneratorTool
except ImportError:
    DocumentationGeneratorTool = None
    print("[tools] 警告: documentation_generator_tool导入失败，DocumentationGeneratorTool不可用")

try:
    from tools.validation_tool import ValidationTool
except ImportError:
    ValidationTool = None
    print("[tools] 警告: validation_tool导入失败，ValidationTool不可用")

try:
    from tools.risk_assessment_tool import RiskAssessmentTool
except ImportError:
    RiskAssessmentTool = None
    print("[tools] 警告: risk_assessment_tool导入失败，RiskAssessmentTool不可用")

try:
    from tools.ui_pattern_generator_tool import UIPatternGeneratorTool
except ImportError:
    UIPatternGeneratorTool = None
    print("[tools] 警告: ui_pattern_generator_tool导入失败，UIPatternGeneratorTool不可用")

try:
    from tools.knowledge_retrieval_tool import KnowledgeRetrievalTool
except ImportError:
    KnowledgeRetrievalTool = None
    print("[tools] 警告: knowledge_retrieval_tool导入失败，KnowledgeRetrievalTool不可用")

try:
    from tools.dependency_analyzer_tool import DependencyAnalyzerTool
except ImportError:
    DependencyAnalyzerTool = None
    print("[tools] 警告: dependency_analyzer_tool导入失败，DependencyAnalyzerTool不可用")

try:
    from tools.performance_analyzer_tool import PerformanceAnalyzerTool
except ImportError:
    PerformanceAnalyzerTool = None
    print("[tools] 警告: performance_analyzer_tool导入失败，PerformanceAnalyzerTool不可用")

from tools.document_parser import parse_document, ParsedDocument

__all__ = [
    "DocxParserTool",
    "CodeWriterTool",
    "MermaidTool",
    "MatplotlibDesignTool",
    "DocxGeneratorTool",
    "RequirementsAnalyzerTool",
    "CodeReviewTool",
    "TestCaseGeneratorTool",
    "ArchitectureEvaluatorTool",
    "DocumentationGeneratorTool",
    "ValidationTool",
    "RiskAssessmentTool",
    "UIPatternGeneratorTool",
    "KnowledgeRetrievalTool",
    "DependencyAnalyzerTool",
    "PerformanceAnalyzerTool",
    "parse_document",
    "ParsedDocument",
]
