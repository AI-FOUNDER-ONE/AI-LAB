"""
risk_assessment_tool.py - 风险评估工具
====================================
供 PM（项目经理）使用，对项目方案进行风险评估。
考虑技术风险、时间风险、成本风险、团队风险等多个维度。

安全性审计:
  ✅ 仅分析文本，不执行代码
  ✅ 不读取外部文件
  ✅ 输出结构化风险评估报告
"""

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


class RiskAssessmentInput(BaseModel):
    """RiskAssessmentTool 的输入参数模型。"""
    project_description: str = Field(
        ...,
        description=(
            "项目方案描述。可以是：\n"
            "1. 项目需求文档\n"
            "2. 技术方案描述\n"
            "3. 项目计划概要\n"
            "4. 商业计划书摘要\n"
            "示例：一个软件开发项目的描述，包括目标、技术栈、时间计划、团队构成等"
        )
    )
    assessment_depth: str = Field(
        default="standard",
        description=(
            "评估深度。可选值：\n"
            "- 'quick': 快速评估，生成3-5个主要风险\n"
            "- 'standard': 标准评估，生成5-10个风险点（默认）\n"
            "- 'deep': 深度评估，生成10-15个详细风险分析"
        )
    )
    industry: str = Field(
        default="software",
        description=(
            "行业领域。可选值：\n"
            "- 'software': 软件开发（默认）\n"
            "- 'hardware': 硬件/嵌入式\n"
            "- 'research': 科学研究\n"
            "- 'business': 商业项目\n"
            "- 'engineering': 工程项目"
        )
    )


class RiskAssessmentTool(BaseTool):
    """风险评估工具。

    对项目方案进行多维度风险评估，提供改进建议。
    """

    name: str = "risk_assessment"
    description: str = (
        "对项目方案进行多维度风险评估，考虑技术风险、时间风险、成本风险、团队风险等因素。"
        "输入项目方案描述，输出结构化风险评估报告和改进建议。"
    )
    args_schema: Type[BaseModel] = RiskAssessmentInput

    def _run(self, project_description: str, assessment_depth: str = "standard",
             industry: str = "software") -> str:
        """执行风险评估。

        Args:
            project_description: 项目方案描述
            assessment_depth: 评估深度
            industry: 行业领域

        Returns:
            格式化的风险评估报告
        """
        try:
            # 1. 分析项目描述
            project_info = self._analyze_project(project_description, industry)

            # 2. 执行风险评估
            risk_assessment = self._assess_risks(project_info, assessment_depth, industry)

            # 3. 生成报告
            return self._generate_report(project_info, assessment_depth, industry, risk_assessment)

        except Exception as e:
            return f"❌ 风险评估失败: {str(e)}"

    def _analyze_project(self, description: str, industry: str) -> Dict[str, Any]:
        """分析项目描述"""
        info = {
            "length": len(description),
            "word_count": len(description.split()),
            "has_technical_details": False,
            "has_timeline": False,
            "has_budget": False,
            "has_team_info": False,
            "has_dependencies": False,
            "complexity": "medium",
            "key_themes": [],
        }

        # 检查技术细节
        technical_keywords = [
            r'\b(api|sdk|framework|library|database|server|client|backend|frontend)\b',
            r'\b(python|javascript|java|c\+\+|rust|go|react|vue|angular)\b',
            r'\b(algorithm|data structure|architecture|design pattern)\b',
            r'\b(microservice|monolith|container|docker|kubernetes)\b',
        ]
        description_lower = description.lower()
        for pattern in technical_keywords:
            if re.search(pattern, description_lower):
                info["has_technical_details"] = True
                break

        # 检查时间线
        timeline_keywords = [
            r'\b(week|month|year|quarter|deadline|timeline|schedule|milestone)\b',
            r'\b(\d+\s*(day|week|month|year)s?)\b',
            r'\b(Q[1-4]|quarter)\b',
        ]
        for pattern in timeline_keywords:
            if re.search(pattern, description_lower, re.IGNORECASE):
                info["has_timeline"] = True
                break

        # 检查预算
        budget_keywords = [
            r'\b(budget|cost|funding|investment|price|fee|expense)\b',
            r'\b(\$|€|¥|£)\s*\d+',
            r'\b\d+\s*(k|m|b|thousand|million|billion)\b',
        ]
        for pattern in budget_keywords:
            if re.search(pattern, description_lower, re.IGNORECASE):
                info["has_budget"] = True
                break

        # 检查团队信息
        team_keywords = [
            r'\b(team|member|developer|engineer|designer|tester|pm|product manager)\b',
            r'\b(\d+\s*(person|people|member|engineer)s?)\b',
            r'\b(skill|experience|expertise)\b',
        ]
        for pattern in team_keywords:
            if re.search(pattern, description_lower, re.IGNORECASE):
                info["has_team_info"] = True
                break

        # 检查依赖项
        dependency_keywords = [
            r'\b(depend|relay|integrat|third-party|external|vendor|supplier)\b',
            r'\b(API key|credential|license|permission|approval)\b',
        ]
        for pattern in dependency_keywords:
            if re.search(pattern, description_lower, re.IGNORECASE):
                info["has_dependencies"] = True
                break

        # 提取关键主题
        # 简单实现：提取名词短语
        words = description.split()
        stop_words = {'的', '了', '在', '是', '和', '与', '或', '及', '等', '一个', '一种', 'this', 'that', 'the', 'a', 'an'}
        themes = [word for word in words if word not in stop_words and len(word) > 1]
        info["key_themes"] = themes[:10]

        # 评估复杂度
        word_count = info["word_count"]
        if word_count < 100:
            info["complexity"] = "low"
        elif word_count < 500:
            info["complexity"] = "medium"
        else:
            info["complexity"] = "high"

        return info

    def _assess_risks(self, project_info: Dict[str, Any], assessment_depth: str,
                     industry: str) -> Dict[str, Any]:
        """执行风险评估"""
        # 定义风险维度
        risk_dimensions = {
            "technical": self._assess_technical_risk(project_info, industry),
            "schedule": self._assess_schedule_risk(project_info, industry),
            "cost": self._assess_cost_risk(project_info, industry),
            "team": self._assess_team_risk(project_info, industry),
            "dependency": self._assess_dependency_risk(project_info, industry),
            "market": self._assess_market_risk(project_info, industry),
        }

        # 根据评估深度调整
        depth_map = {"quick": 4, "standard": 6, "deep": 6}
        dimensions_to_include = depth_map.get(assessment_depth, 6)

        # 选择风险最高的维度
        sorted_dimensions = sorted(
            risk_dimensions.items(),
            key=lambda x: x[1]["score"],
            reverse=True  # 分数越低风险越高
        )[:dimensions_to_include]

        # 计算总体风险分数
        total_score = 0
        for dim_name, dim_data in sorted_dimensions:
            total_score += dim_data["score"]
        avg_score = total_score / len(sorted_dimensions) if sorted_dimensions else 0

        # 风险等级
        if avg_score >= 8.0:
            risk_level = "低风险 (Low Risk)"
            color = "🟢"
        elif avg_score >= 6.0:
            risk_level = "中风险 (Medium Risk)"
            color = "🟡"
        elif avg_score >= 4.0:
            risk_level = "高风险 (High Risk)"
            color = "🟠"
        else:
            risk_level = "极高风险 (Critical Risk)"
            color = "🔴"

        return {
            "dimensions": dict(sorted_dimensions),
            "overall_score": avg_score,
            "risk_level": risk_level,
            "risk_color": color,
            "depth": assessment_depth,
        }

    def _assess_technical_risk(self, project_info: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """评估技术风险"""
        score = 7.0  # 基础分
        factors = []
        recommendations = []

        if not project_info["has_technical_details"]:
            score -= 2.0
            factors.append("缺少详细技术描述")
            recommendations.append("补充技术方案细节，明确技术选型和架构设计")

        if project_info["complexity"] == "high":
            score -= 1.5
            factors.append("项目复杂度高")
            recommendations.append("考虑分阶段实施，降低单阶段复杂度")
        elif project_info["complexity"] == "low":
            score += 1.0
            factors.append("项目复杂度低")

        # 行业特定风险
        if industry == "software":
            # 软件开发特有风险
            score += 0.5  # 软件开发相对成熟
        elif industry == "hardware":
            score -= 1.0
            factors.append("硬件项目技术风险较高")
            recommendations.append("加强硬件选型和原型验证")
        elif industry == "research":
            score -= 1.5
            factors.append("研究项目技术不确定性高")
            recommendations.append("设置技术探索阶段，预留技术验证时间")

        score = max(0, min(10, score))

        return {
            "score": score,
            "factors": factors,
            "recommendations": recommendations,
            "weight": 1.2,  # 技术风险权重较高
        }

    def _assess_schedule_risk(self, project_info: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """评估时间进度风险"""
        score = 6.0  # 基础分
        factors = []
        recommendations = []

        if not project_info["has_timeline"]:
            score -= 2.0
            factors.append("缺少明确时间计划")
            recommendations.append("制定详细的项目时间表，包括里程碑节点")

        if project_info["complexity"] == "high":
            score -= 1.0
            factors.append("高复杂度可能影响进度")
            recommendations.append("考虑增加缓冲时间，应对不可预见问题")

        # 检查时间表述是否模糊
        vague_time_patterns = [
            r'\b(尽快|尽快地|尽快完成|尽快交付)\b',
            r'\b(大约|大概|左右|差不多|可能)\s*\d+\s*(天|周|月|年)\b',
            r'\b(待定|TBD|to be determined)\b',
        ]
        description_lower = " ".join(project_info["key_themes"]).lower()
        for pattern in vague_time_patterns:
            if re.search(pattern, description_lower):
                score -= 1.0
                factors.append("时间计划表述模糊")
                recommendations.append("明确具体时间节点，避免模糊表述")
                break

        score = max(0, min(10, score))

        return {
            "score": score,
            "factors": factors,
            "recommendations": recommendations,
            "weight": 1.1,
        }

    def _assess_cost_risk(self, project_info: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """评估成本风险"""
        score = 5.0  # 基础分
        factors = []
        recommendations = []

        if not project_info["has_budget"]:
            score -= 2.5
            factors.append("缺少预算信息")
            recommendations.append("制定详细预算计划，包括人力、硬件、软件等成本")

        # 检查是否有成本控制措施
        cost_control_patterns = [
            r'\b(预算控制|成本控制|费用管理|成本估算)\b',
            r'\b(ROI|投资回报率|成本效益)\b',
            r'\b(节约|节省|降低成本)\b',
        ]
        description_lower = " ".join(project_info["key_themes"]).lower()
        has_cost_control = False
        for pattern in cost_control_patterns:
            if re.search(pattern, description_lower):
                has_cost_control = True
                break

        if has_cost_control:
            score += 1.0
            factors.append("提及成本控制措施")
        else:
            score -= 0.5
            recommendations.append("建立成本监控机制，定期评估预算执行情况")

        # 行业特定成本风险
        if industry == "hardware":
            score -= 1.0
            factors.append("硬件项目成本波动大")
            recommendations.append("考虑物料成本波动，预留成本缓冲")
        elif industry == "research":
            score -= 0.5
            factors.append("研究项目成本不确定性高")

        score = max(0, min(10, score))

        return {
            "score": score,
            "factors": factors,
            "recommendations": recommendations,
            "weight": 1.0,
        }

    def _assess_team_risk(self, project_info: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """评估团队风险"""
        score = 6.0  # 基础分
        factors = []
        recommendations = []

        if not project_info["has_team_info"]:
            score -= 2.0
            factors.append("缺少团队信息")
            recommendations.append("明确团队构成、角色分工和技能要求")

        # 检查技能匹配
        skill_keywords = {
            "software": ["developer", "engineer", "programmer", "architect", "tester"],
            "hardware": ["硬件工程师", "电子工程师", "机械工程师", "embedded"],
            "research": ["研究员", "科学家", "博士", "postdoc"],
        }

        industry_keywords = skill_keywords.get(industry, [])
        description_lower = " ".join(project_info["key_themes"]).lower()
        has_skill_mention = False
        for keyword in industry_keywords:
            if keyword.lower() in description_lower:
                has_skill_mention = True
                break

        if has_skill_mention:
            score += 0.5
            factors.append("提及相关技能要求")
        else:
            score -= 0.5
            recommendations.append("明确所需专业技能，评估团队能力匹配度")

        # 检查团队规模
        team_size_pattern = r'\b(\d+)\s*(person|people|member|engineer)s?\b'
        match = re.search(team_size_pattern, description_lower)
        if match:
            team_size = int(match.group(1))
            if team_size < 3:
                score -= 1.0
                factors.append(f"团队规模较小 ({team_size}人)")
                recommendations.append("评估工作量与团队规模的匹配度，考虑增加人手")
            elif team_size > 10:
                score -= 0.5
                factors.append(f"团队规模较大 ({team_size}人)")
                recommendations.append("加强团队沟通协调，建立有效管理机制")

        score = max(0, min(10, score))

        return {
            "score": score,
            "factors": factors,
            "recommendations": recommendations,
            "weight": 1.0,
        }

    def _assess_dependency_risk(self, project_info: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """评估依赖风险"""
        score = 7.0  # 基础分
        factors = []
        recommendations = []

        if project_info["has_dependencies"]:
            score -= 1.0
            factors.append("存在外部依赖")
            recommendations.append("识别关键依赖，制定备选方案和应急计划")
        else:
            score += 0.5
            factors.append("无明显外部依赖")

        # 检查API/第三方服务依赖
        api_patterns = [
            r'\b(API|接口|第三方|external|third-party)\b',
            r'\b(Google|AWS|Azure|腾讯云|阿里云)\b',
            r'\b(开源|open source|library|package)\b',
        ]
        description_lower = " ".join(project_info["key_themes"]).lower()
        has_api_dependency = False
        for pattern in api_patterns:
            if re.search(pattern, description_lower, re.IGNORECASE):
                has_api_dependency = True
                break

        if has_api_dependency:
            score -= 1.5
            factors.append("依赖第三方API/服务")
            recommendations.append("评估API稳定性，准备降级方案，关注服务等级协议(SLA)")

        # 检查法律合规依赖
        legal_patterns = [
            r'\b(许可证|license|合规|compliance|法规|regulation)\b',
            r'\b(专利|patent|版权|copyright|商标|trademark)\b',
        ]
        has_legal_dependency = False
        for pattern in legal_patterns:
            if re.search(pattern, description_lower):
                has_legal_dependency = True
                break

        if has_legal_dependency:
            score -= 1.0
            factors.append("涉及法律合规要求")
            recommendations.append("咨询法律专家，确保合规性，获取必要授权")

        score = max(0, min(10, score))

        return {
            "score": score,
            "factors": factors,
            "recommendations": recommendations,
            "weight": 0.9,
        }

    def _assess_market_risk(self, project_info: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """评估市场风险"""
        score = 6.0  # 基础分
        factors = []
        recommendations = []

        # 检查市场需求提及
        market_patterns = [
            r'\b(市场|需求|用户|customer|client|需求分析|market)\b',
            r'\b(竞争|competitor|竞品|competitive)\b',
            r'\b(趋势|trend|流行|popular)\b',
        ]
        description_lower = " ".join(project_info["key_themes"]).lower()
        has_market_analysis = False
        for pattern in market_patterns:
            if re.search(pattern, description_lower):
                has_market_analysis = True
                break

        if has_market_analysis:
            score += 1.0
            factors.append("提及市场分析")
        else:
            score -= 1.0
            factors.append("缺少市场分析")
            recommendations.append("进行市场需求调研，分析目标用户和竞争环境")

        # 检查商业价值
        value_patterns = [
            r'\b(价值|value|收益|benefit|优势|advantage)\b',
            r'\b(收入|revenue|利润|profit|商业化|commercial)\b',
            r'\b(创新|innovation|独特|unique|差异化|differentiation)\b',
        ]
        has_value_proposition = False
        for pattern in value_patterns:
            if re.search(pattern, description_lower):
                has_value_proposition = True
                break

        if has_value_proposition:
            score += 0.5
            factors.append("明确价值主张")
        else:
            score -= 0.5
            recommendations.append("明确项目商业价值，制定商业化策略")

        # 行业特定市场风险
        if industry == "research":
            score += 0.5  # 研究项目市场风险相对较低
            factors.append("研究项目市场风险较低")
        elif industry == "business":
            score -= 0.5
            factors.append("商业项目市场敏感度高")
            recommendations.append("密切关注市场变化，灵活调整产品策略")

        score = max(0, min(10, score))

        return {
            "score": score,
            "factors": factors,
            "recommendations": recommendations,
            "weight": 0.8,  # 市场风险权重相对较低
        }

    def _generate_report(self, project_info: Dict[str, Any], assessment_depth: str,
                        industry: str, risk_assessment: Dict[str, Any]) -> str:
        """生成风险评估报告"""
        dimensions = risk_assessment["dimensions"]
        overall_score = risk_assessment["overall_score"]
        risk_level = risk_assessment["risk_level"]
        risk_color = risk_assessment["risk_color"]

        report = f"""# 项目风险评估报告

## 评估概览
- **总体风险分数**: {overall_score:.2f}/10.0 {risk_color} {risk_level}
- **评估深度**: {assessment_depth}
- **行业领域**: {industry}
- **项目描述长度**: {project_info['word_count']} 词

## 项目分析摘要
- **技术细节**: {'有' if project_info['has_technical_details'] else '无'}
- **时间计划**: {'有' if project_info['has_timeline'] else '无'}
- **预算信息**: {'有' if project_info['has_budget'] else '无'}
- **团队信息**: {'有' if project_info['has_team_info'] else '无'}
- **依赖关系**: {'有' if project_info['has_dependencies'] else '无'}
- **项目复杂度**: {project_info['complexity']}

## 风险维度评估
"""

        # 各维度风险评估
        for dim_name, dim_data in dimensions.items():
            dim_score = dim_data["score"]
            dim_factors = dim_data["factors"]
            dim_recommendations = dim_data["recommendations"]

            # 风险等级图标
            if dim_score >= 8.0:
                dim_icon = "🟢"
            elif dim_score >= 6.0:
                dim_icon = "🟡"
            elif dim_score >= 4.0:
                dim_icon = "🟠"
            else:
                dim_icon = "🔴"

            report += f"\n### {dim_name.upper()} - {dim_score:.2f}/10.0 {dim_icon}\n"

            if dim_factors:
                report += "**风险因素**:\n"
                for factor in dim_factors:
                    report += f"- {factor}\n"

            if dim_recommendations:
                report += "**改进建议**:\n"
                for rec in dim_recommendations:
                    report += f"- 💡 {rec}\n"

        # 关键风险汇总
        report += "\n## 关键风险汇总\n"
        high_risks = [(name, data) for name, data in dimensions.items() if data["score"] < 6.0]
        medium_risks = [(name, data) for name, data in dimensions.items() if 6.0 <= data["score"] < 8.0]
        low_risks = [(name, data) for name, data in dimensions.items() if data["score"] >= 8.0]

        if high_risks:
            report += "### 🔴 高风险 (需立即关注)\n"
            for name, data in high_risks:
                report += f"- **{name}** ({data['score']:.1f}/10.0): {', '.join(data['factors'][:2])}\n"

        if medium_risks:
            report += "\n### 🟡 中风险 (需监控)\n"
            for name, data in medium_risks:
                report += f"- **{name}** ({data['score']:.1f}/10.0): {', '.join(data['factors'][:1])}\n"

        if low_risks:
            report += "\n### 🟢 低风险 (可控)\n"
            for name, data in low_risks:
                report += f"- **{name}** ({data['score']:.1f}/10.0)\n"

        # 风险管理计划建议
        report += f"""
## 风险管理计划建议

### 1. 高风险应对策略
- 建立专项风险应对小组
- 制定详细应急预案
- 增加监控频率 (每周评估)

### 2. 中风险监控措施
- 指定风险责任人
- 定期评估风险状态 (每两周)
- 制定缓解措施时间表

### 3. 低风险跟踪机制
- 记录风险日志
- 定期审查 (每月)
- 关注风险变化趋势

### 4. 通用风险管理建议
- 建立风险管理文化
- 鼓励团队成员报告风险
- 定期更新风险评估

## 结构化数据（JSON）
```json
{json.dumps({
    "project_info": project_info,
    "assessment_config": {"depth": assessment_depth, "industry": industry},
    "risk_assessment": risk_assessment,
    "summary": {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "high_risk_count": len(high_risks),
        "medium_risk_count": len(medium_risks),
        "low_risk_count": len(low_risks),
    }
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = RiskAssessmentTool()

    test_project = """
    项目名称：智能电商推荐系统
    目标：开发一个基于机器学习的个性化商品推荐系统，提升用户购买转化率30%
    技术栈：Python、TensorFlow、FastAPI、Redis、MySQL
    团队：5人（2名算法工程师，2名后端工程师，1名前端工程师）
    时间计划：3个月完成开发和测试
    预算：50万人民币
    依赖：需要访问用户历史行为数据，依赖商品数据库API
    风险点：算法效果不确定性、数据质量可能影响推荐准确性
    """

    result = tool._run(
        project_description=test_project,
        assessment_depth="standard",
        industry="software"
    )

    print("测试结果:")
    print(result)