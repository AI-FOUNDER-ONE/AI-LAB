"""
requirements_analyzer_tool.py - 需求分析工具
============================================
供 CKO（首席知识官）使用，对用户需求进行深度分析，生成结构化追问问题。

安全性审计:
  ✅ 仅分析文本，不执行代码
  ✅ 输入内容经过清洗处理
  ✅ 输出结构化问题，无副作用
"""

import os
import re
import json
from typing import Type, List, Dict, Any
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


class RequirementsAnalyzerInput(BaseModel):
    """RequirementsAnalyzerTool 的输入参数模型。"""
    user_input: str = Field(
        ...,
        description=(
            "用户的原始需求描述。可以是几句话或一段文字。\n"
            "示例：\"我想开发一个个人财务管理应用，帮助我追踪日常开支和投资。\""
        )
    )
    analysis_depth: str = Field(
        default="standard",
        description=(
            "分析深度级别。可选值：\n"
            "- 'quick': 快速分析，生成3-5个核心问题\n"
            "- 'standard': 标准分析，生成5-10个结构化问题\n"
            "- 'deep': 深度分析，生成10-15个详细追问问题"
        )
    )
    domain_hint: str = Field(
        default="",
        description=(
            "领域提示词，帮助工具更精准地分析。\n"
            "示例：\"软件开发\"、\"学术研究\"、\"商业计划\"、\"工程方案\""
        )
    )


class RequirementsAnalyzerTool(BaseTool):
    """需求分析工具。

    对用户需求进行深度分析，识别需求中的模糊点、假设和遗漏信息，
    生成结构化追问问题，帮助CKO进行深度需求访谈。
    """

    name: str = "requirements_analyzer"
    description: str = (
        "深度分析用户需求，生成结构化追问问题。"
        "输入用户需求描述，输出需要进一步澄清的问题列表。"
        "适用于CKO在需求访谈阶段使用。"
    )
    args_schema: Type[BaseModel] = RequirementsAnalyzerInput

    def _run(self, user_input: str, analysis_depth: str = "standard", domain_hint: str = "") -> str:
        """执行需求分析。

        Args:
            user_input: 用户的原始需求描述
            analysis_depth: 分析深度级别（quick/standard/deep）
            domain_hint: 领域提示词

        Returns:
            格式化的追问问题列表（JSON格式）
        """
        try:
            # 1. 预处理用户输入
            cleaned_input = self._preprocess_input(user_input)

            # 2. 分析需求特征
            features = self._analyze_requirements_features(cleaned_input, domain_hint)

            # 3. 根据分析深度生成问题
            questions = self._generate_questions(features, analysis_depth)

            # 4. 格式化输出
            return self._format_output(cleaned_input, features, questions)

        except Exception as e:
            return f"❌ 需求分析失败: {str(e)}"

    def _preprocess_input(self, user_input: str) -> str:
        """预处理用户输入"""
        # 移除多余空白字符
        cleaned = re.sub(r'\s+', ' ', user_input.strip())
        return cleaned

    def _analyze_requirements_features(self, user_input: str, domain_hint: str) -> Dict[str, Any]:
        """分析需求特征"""
        features = {
            "length": len(user_input),
            "word_count": len(user_input.split()),
            "has_technical_terms": self._contains_technical_terms(user_input),
            "has_quantitative_info": self._contains_quantitative_info(user_input),
            "has_vague_phrases": self._contains_vague_phrases(user_input),
            "domain": self._detect_domain(user_input, domain_hint),
            "key_topics": self._extract_key_topics(user_input),
        }
        return features

    def _contains_technical_terms(self, text: str) -> bool:
        """检查是否包含技术术语"""
        technical_patterns = [
            r'\b(api|sdk|framework|library|database|server|client|backend|frontend)\b',
            r'\b(python|javascript|java|c\+\+|rust|go|react|vue|angular)\b',
            r'\b(algorithm|data structure|architecture|design pattern)\b',
        ]
        text_lower = text.lower()
        for pattern in technical_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _contains_quantitative_info(self, text: str) -> bool:
        """检查是否包含定量信息"""
        quantitative_patterns = [
            r'\b\d+\b',  # 数字
            r'\b(mb|gb|tb|ms|s|min|hour|day|week|month|year)\b',  # 单位
            r'\b(users|customers|visits|requests|transactions)\s+\d+\b',  # 数量
        ]
        for pattern in quantitative_patterns:
            if re.search(pattern, text.lower()):
                return True
        return False

    def _contains_vague_phrases(self, text: str) -> bool:
        """检查是否包含模糊表述"""
        vague_phrases = [
            '大概', '大约', '可能', '也许', '差不多', '左右',
            'easy', 'simple', 'quick', 'fast', 'basic', 'standard',
            '用户友好', '高效', '稳定', '可靠', '安全'
        ]
        text_lower = text.lower()
        for phrase in vague_phrases:
            if phrase in text_lower:
                return True
        return False

    def _detect_domain(self, text: str, domain_hint: str) -> str:
        """检测领域"""
        if domain_hint:
            return domain_hint

        domain_keywords = {
            "SOFTWARE": ['软件', '应用', '程序', '网站', 'app', '系统', '代码', '开发'],
            "ENGINEERING": ['工程', '施工', '机械', '制造', '生产', '工艺', '设备'],
            "DESIGN": ['设计', '界面', 'ui', 'ux', '视觉', '外观', '用户体验'],
            "RESEARCH": ['研究', '分析', '调查', '实验', '论文', '学术', '科学'],
        }

        text_lower = text.lower()
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return domain

        return "GENERAL"

    def _extract_key_topics(self, text: str) -> List[str]:
        """提取关键主题"""
        # 简单实现：提取名词短语
        words = text.split()
        # 移除常见停用词
        stop_words = {'的', '了', '在', '是', '和', '与', '或', '及', '等', '一个', '一种'}
        topics = [word for word in words if word not in stop_words and len(word) > 1]
        return topics[:10]  # 最多返回10个主题

    def _generate_questions(self, features: Dict[str, Any], analysis_depth: str) -> List[str]:
        """根据特征和深度生成追问问题"""
        question_templates = []

        # 根据分析深度确定问题数量
        depth_map = {"quick": 3, "standard": 8, "deep": 12}
        max_questions = depth_map.get(analysis_depth, 8)

        # 基础问题模板
        base_questions = [
            "这个项目的核心目标是什么？",
            "目标用户是谁？",
            "预期的使用场景是什么？",
            "有哪些关键功能需求？",
            "项目的时间约束是什么？",
            "预算范围是多少？",
        ]

        # 根据特征添加特定问题
        if not features["has_quantitative_info"]:
            question_templates.append("能提供一些具体的量化指标吗？（例如：用户数量、数据量、响应时间要求等）")

        if features["has_vague_phrases"]:
            question_templates.append("您提到的'XXX'具体指什么？能否提供更明确的定义或标准？")

        if features["domain"] == "SOFTWARE":
            question_templates.extend([
                "技术栈有特殊要求吗？",
                "需要支持哪些平台？（Web/桌面/移动）",
                "数据存储有什么特殊需求？",
                "需要集成第三方服务吗？",
            ])
        elif features["domain"] == "DESIGN":
            question_templates.extend([
                "有没有参考的设计风格或品牌规范？",
                "目标用户的审美偏好是什么？",
                "需要支持哪些设备或屏幕尺寸？",
            ])

        # 组合问题
        all_questions = base_questions + question_templates
        return all_questions[:max_questions]

    def _format_output(self, user_input: str, features: Dict[str, Any], questions: List[str]) -> str:
        """格式化输出"""
        output = {
            "original_input": user_input,
            "analysis_summary": {
                "domain": features["domain"],
                "input_length": features["length"],
                "key_topics": features["key_topics"],
                "needs_clarification": features["has_vague_phrases"],
            },
            "generated_questions": questions,
            "recommended_next_steps": [
                "根据这些问题进行深度访谈",
                "整理用户回答并更新需求文档",
                "识别潜在的技术挑战和风险",
            ]
        }

        # 格式化为易读的文本
        formatted = f"""# 需求分析报告

## 原始需求
{user_input}

## 分析摘要
- **领域**: {features['domain']}
- **输入长度**: {features['length']} 字符
- **关键主题**: {', '.join(features['key_topics'][:5])}
- **需要澄清**: {'是' if features['has_vague_phrases'] else '否'}

## 生成的追问问题 ({len(questions)} 个)
"""

        for i, question in enumerate(questions, 1):
            formatted += f"{i}. {question}\n"

        formatted += "\n## 建议后续步骤\n"
        for step in output["recommended_next_steps"]:
            formatted += f"- {step}\n"

        # 同时提供JSON格式供程序处理
        formatted += f"\n## 结构化数据（JSON）\n```json\n{json.dumps(output, ensure_ascii=False, indent=2)}\n```"

        return formatted


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = RequirementsAnalyzerTool()

    test_input = "我想开发一个个人财务管理应用，帮助我追踪日常开支和投资，最好能有图表分析功能。"

    result = tool._run(
        user_input=test_input,
        analysis_depth="standard",
        domain_hint="软件开发"
    )

    print("测试结果:")
    print(result)