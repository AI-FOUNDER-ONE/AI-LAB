"""
architecture_evaluator_tool.py - 架构评估工具
==========================================
供 Arch（架构师）使用，对架构方案进行评估。
考虑可扩展性、可维护性、性能、安全性、成本等多个维度。

安全性审计:
  ✅ 仅分析文本描述，不执行代码
  ✅ 不读取外部文件
  ✅ 输出结构化评估报告
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


class ArchitectureEvaluatorInput(BaseModel):
    """ArchitectureEvaluatorTool 的输入参数模型。"""
    architecture_description: str = Field(
        ...,
        description=(
            "架构描述或方案。可以是：\n"
            "1. 架构文字描述\n"
            "2. 系统组件清单\n"
            "3. 架构图描述\n"
            "4. 技术栈选择说明\n"
            "示例：一个微服务架构的描述，包含服务划分、技术选型、数据流等"
        )
    )
    evaluation_focus: str = Field(
        default="comprehensive",
        description=(
            "评估重点。可选值：\n"
            "- 'comprehensive': 全面评估（默认）\n"
            "- 'scalability': 可扩展性评估\n"
            "- 'maintainability': 可维护性评估\n"
            "- 'performance': 性能评估\n"
            "- 'security': 安全性评估\n"
            "- 'cost': 成本评估"
        )
    )
    project_scale: str = Field(
        default="medium",
        description=(
            "项目规模。可选值：\n"
            "- 'small': 小型项目（团队<5人，开发周期<3个月）\n"
            "- 'medium': 中型项目（团队5-15人，开发周期3-12个月）\n"
            "- 'large': 大型项目（团队>15人，开发周期>12个月）"
        )
    )


class ArchitectureEvaluatorTool(BaseTool):
    """架构评估工具。

    对架构方案进行多维度评估，提供改进建议。
    """

    name: str = "architecture_evaluator"
    description: str = (
        "对架构方案进行多维度评估，考虑可扩展性、可维护性、性能、安全性、成本等因素。"
        "输入架构描述，输出结构化评估报告和改进建议。"
    )
    args_schema: Type[BaseModel] = ArchitectureEvaluatorInput

    def _run(self, architecture_description: str, evaluation_focus: str = "comprehensive",
             project_scale: str = "medium") -> str:
        """执行架构评估。

        Args:
            architecture_description: 架构描述或方案
            evaluation_focus: 评估重点
            project_scale: 项目规模

        Returns:
            格式化的架构评估报告
        """
        try:
            # 1. 分析架构描述
            architecture_info = self._analyze_architecture(architecture_description)

            # 2. 根据项目规模调整评估标准
            scale_factors = self._get_scale_factors(project_scale)

            # 3. 执行评估
            evaluation_results = self._evaluate_architecture(
                architecture_info, evaluation_focus, scale_factors)

            # 4. 生成报告
            return self._generate_report(architecture_info, evaluation_focus,
                                        project_scale, evaluation_results)

        except Exception as e:
            return f"❌ 架构评估失败: {str(e)}"

    def _analyze_architecture(self, description: str) -> Dict[str, Any]:
        """分析架构描述，提取关键信息"""
        info = {
            "components": [],
            "technologies": [],
            "patterns": [],
            "data_flow": "unknown",
            "communication": "unknown",
            "deployment": "unknown",
            "complexity": "medium",
        }

        # 提取组件信息
        component_patterns = [
            r'(服务|模块|组件|系统|layer|service|module|component)\s+[\"\']?([a-zA-Z0-9_\- ]+)[\"\']?',
            r'(前端|后端|数据库|缓存|消息队列|网关|负载均衡|API\s+网关)',
            r'(微服务|单体|SOA|事件驱动|分层|微内核|管道过滤器)',
        ]

        for pattern in component_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    component = match[1] if len(match) > 1 else match[0]
                else:
                    component = match
                if component and component not in info["components"]:
                    info["components"].append(component)

        # 提取技术栈
        tech_keywords = {
            "python": ["python", "django", "flask", "fastapi"],
            "java": ["java", "spring", "spring boot"],
            "javascript": ["javascript", "node.js", "react", "vue", "angular"],
            "database": ["mysql", "postgresql", "mongodb", "redis", "elasticsearch"],
            "cloud": ["aws", "azure", "gcp", "阿里云", "腾讯云"],
            "container": ["docker", "kubernetes", "容器"],
            "message": ["kafka", "rabbitmq", "rocketmq", "消息队列"],
        }

        description_lower = description.lower()
        for category, keywords in tech_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    if keyword not in info["technologies"]:
                        info["technologies"].append(keyword)

        # 识别架构模式
        patterns = [
            ("微服务", ["微服务", "microservice", "service mesh"]),
            ("单体", ["单体", "monolith", "monolithic"]),
            ("事件驱动", ["事件驱动", "event-driven", "event sourcing"]),
            ("分层", ["分层", "layered", "三层架构", "3-tier"]),
            ("SOA", ["SOA", "面向服务"]),
        ]

        for pattern_name, pattern_keywords in patterns:
            for keyword in pattern_keywords:
                if keyword in description_lower:
                    if pattern_name not in info["patterns"]:
                        info["patterns"].append(pattern_name)
                    break

        # 评估复杂度
        component_count = len(info["components"])
        tech_count = len(info["technologies"])
        pattern_count = len(info["patterns"])

        if component_count > 10 or tech_count > 8 or pattern_count > 2:
            info["complexity"] = "high"
        elif component_count > 5 or tech_count > 4:
            info["complexity"] = "medium"
        else:
            info["complexity"] = "low"

        return info

    def _get_scale_factors(self, project_scale: str) -> Dict[str, float]:
        """根据项目规模获取评估因子"""
        scale_factors = {
            "small": {
                "scalability_weight": 0.6,
                "maintainability_weight": 0.8,
                "performance_weight": 0.7,
                "security_weight": 0.5,
                "cost_weight": 0.9,
            },
            "medium": {
                "scalability_weight": 0.8,
                "maintainability_weight": 0.9,
                "performance_weight": 0.8,
                "security_weight": 0.7,
                "cost_weight": 0.7,
            },
            "large": {
                "scalability_weight": 0.9,
                "maintainability_weight": 0.9,
                "performance_weight": 0.9,
                "security_weight": 0.8,
                "cost_weight": 0.6,
            }
        }
        return scale_factors.get(project_scale, scale_factors["medium"])

    def _evaluate_architecture(self, architecture_info: Dict[str, Any],
                              evaluation_focus: str, scale_factors: Dict[str, float]) -> Dict[str, Any]:
        """执行架构评估"""
        evaluations = {
            "scalability": self._evaluate_scalability(architecture_info),
            "maintainability": self._evaluate_maintainability(architecture_info),
            "performance": self._evaluate_performance(architecture_info),
            "security": self._evaluate_security(architecture_info),
            "cost": self._evaluate_cost(architecture_info),
        }

        # 应用权重
        for dimension in evaluations.keys():
            weight_key = f"{dimension}_weight"
            if weight_key in scale_factors:
                evaluations[dimension]["score"] *= scale_factors[weight_key]
                evaluations[dimension]["weight"] = scale_factors[weight_key]

        # 计算总体得分
        total_score = 0
        total_weight = 0
        for dimension, eval_data in evaluations.items():
            weight = eval_data.get("weight", 1.0)
            total_score += eval_data["score"] * weight
            total_weight += weight

        overall_score = total_score / total_weight if total_weight > 0 else 0

        return {
            "dimensions": evaluations,
            "overall_score": overall_score,
            "focus": evaluation_focus,
        }

    def _evaluate_scalability(self, architecture_info: Dict[str, Any]) -> Dict[str, Any]:
        """评估可扩展性"""
        score = 7.0  # 基础分
        strengths = []
        weaknesses = []
        suggestions = []

        components = architecture_info["components"]
        technologies = architecture_info["technologies"]
        patterns = architecture_info["patterns"]

        # 检查微服务模式
        if "微服务" in patterns:
            score += 2.0
            strengths.append("采用微服务架构，具有良好的水平扩展能力")
        elif "单体" in patterns:
            score -= 1.0
            weaknesses.append("单体架构在扩展性方面存在限制")
            suggestions.append("考虑将关键组件拆分为独立服务以提高扩展性")

        # 检查容器化技术
        if any(tech in ["docker", "kubernetes", "容器"] for tech in technologies):
            score += 1.5
            strengths.append("使用容器化技术，便于部署和扩展")

        # 检查负载均衡
        if any("负载均衡" in comp or "gateway" in comp.lower() for comp in components):
            score += 1.0
            strengths.append("包含负载均衡组件，支持流量分发")

        # 检查无状态设计
        if "stateless" in " ".join(components).lower() or "无状态" in architecture_info.get("description", ""):
            score += 1.0
            strengths.append("无状态设计有利于水平扩展")

        # 检查数据存储扩展性
        if any(db in ["mongodb", "cassandra", "redis"] for db in technologies):
            score += 1.0
            strengths.append("使用可扩展的数据库技术")

        # 分数限制在0-10
        score = max(0, min(10, score))

        return {
            "score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "weight": 1.0,
        }

    def _evaluate_maintainability(self, architecture_info: Dict[str, Any]) -> Dict[str, Any]:
        """评估可维护性"""
        score = 6.0  # 基础分
        strengths = []
        weaknesses = []
        suggestions = []

        components = architecture_info["components"]
        technologies = architecture_info["technologies"]
        complexity = architecture_info["complexity"]

        # 检查组件数量
        if len(components) > 10:
            score -= 2.0
            weaknesses.append("组件数量过多，增加了维护复杂度")
            suggestions.append("考虑合并相关功能或抽象通用组件")

        # 检查技术栈一致性
        tech_categories = set()
        for tech in technologies:
            if "python" in tech:
                tech_categories.add("python")
            elif "java" in tech:
                tech_categories.add("java")
            elif "javascript" in tech:
                tech_categories.add("javascript")

        if len(tech_categories) > 2:
            score -= 1.5
            weaknesses.append("技术栈过于分散，增加了维护成本")
            suggestions.append("统一技术栈，减少技术多样性")

        # 检查文档和监控
        if any(word in " ".join(components).lower() for word in ["文档", "监控", "日志", "告警"]):
            score += 1.5
            strengths.append("包含可观测性组件，便于问题排查")

        # 检查模块化程度
        if any(word in " ".join(components).lower() for word in ["模块", "组件", "service"]):
            score += 1.0
            strengths.append("模块化设计有利于独立维护")

        # 复杂度影响
        if complexity == "high":
            score -= 1.0
            weaknesses.append("架构复杂度高，维护难度大")
        elif complexity == "low":
            score += 1.0
            strengths.append("架构简洁，易于维护")

        score = max(0, min(10, score))

        return {
            "score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "weight": 1.0,
        }

    def _evaluate_performance(self, architecture_info: Dict[str, Any]) -> Dict[str, Any]:
        """评估性能"""
        score = 7.0  # 基础分
        strengths = []
        weaknesses = []
        suggestions = []

        components = architecture_info["components"]
        technologies = architecture_info["technologies"]

        # 检查缓存组件
        if any("缓存" in comp or "cache" in comp.lower() or "redis" in tech for comp in components for tech in technologies):
            score += 1.5
            strengths.append("包含缓存机制，有利于提升性能")

        # 检查异步处理
        if any(word in " ".join(components).lower() for word in ["异步", "消息队列", "mq", "kafka", "rabbitmq"]):
            score += 1.0
            strengths.append("支持异步处理，提高系统吞吐量")

        # 检查CDN/静态资源处理
        if any(word in " ".join(components).lower() for word in ["cdn", "静态资源", "对象存储"]):
            score += 1.0
            strengths.append("考虑静态资源优化，减少服务器压力")

        # 检查数据库优化
        if any(word in " ".join(technologies) for word in ["索引", "分库", "分表", "读写分离"]):
            score += 1.0
            strengths.append("考虑数据库性能优化")

        # 检查负载均衡
        if any("负载均衡" in comp for comp in components):
            score += 0.5
            strengths.append("负载均衡有助于性能分布")

        # 检查单点故障
        if any(word in " ".join(components).lower() for word in ["单点", "single point"]):
            score -= 1.5
            weaknesses.append("存在单点故障风险，可能影响性能")
            suggestions.append("考虑高可用设计，消除单点故障")

        score = max(0, min(10, score))

        return {
            "score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "weight": 1.0,
        }

    def _evaluate_security(self, architecture_info: Dict[str, Any]) -> Dict[str, Any]:
        """评估安全性"""
        score = 5.0  # 基础分
        strengths = []
        weaknesses = []
        suggestions = []

        components = architecture_info["components"]
        technologies = architecture_info["technologies"]

        # 检查安全组件
        security_components = ["认证", "授权", "防火墙", "WAF", "加密", "SSL", "TLS"]
        found_security = False
        for sec_comp in security_components:
            if any(sec_comp in comp for comp in components):
                score += 1.0
                strengths.append(f"包含{sec_comp}安全组件")
                found_security = True

        if not found_security:
            score -= 1.0
            weaknesses.append("缺少明确的安全组件")
            suggestions.append("考虑添加认证、授权、加密等安全机制")

        # 检查API网关
        if any("API网关" in comp or "gateway" in comp.lower() for comp in components):
            score += 1.0
            strengths.append("API网关有助于统一安全控制")

        # 检查数据加密
        if any(word in " ".join(technologies).lower() for word in ["加密", "ssl", "tls", "https"]):
            score += 1.0
            strengths.append("考虑数据传输加密")

        # 检查日志审计
        if any(word in " ".join(components).lower() for word in ["审计", "日志", "监控"]):
            score += 0.5
            strengths.append("包含审计日志，便于安全追溯")

        # 检查外部依赖安全性
        if len(technologies) > 8:
            score -= 0.5
            weaknesses.append("外部依赖过多可能引入安全风险")
            suggestions.append("定期进行依赖安全扫描和更新")

        score = max(0, min(10, score))

        return {
            "score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "weight": 1.0,
        }

    def _evaluate_cost(self, architecture_info: Dict[str, Any]) -> Dict[str, Any]:
        """评估成本"""
        score = 8.0  # 基础分
        strengths = []
        weaknesses = []
        suggestions = []

        components = architecture_info["components"]
        technologies = architecture_info["technologies"]

        # 检查云服务使用
        cloud_services = ["aws", "azure", "gcp", "阿里云", "腾讯云"]
        cloud_count = sum(1 for tech in technologies if any(cloud in tech.lower() for cloud in cloud_services))

        if cloud_count > 3:
            score -= 2.0
            weaknesses.append("使用多个云服务可能增加成本")
            suggestions.append("考虑成本优化，整合云服务使用")
        elif cloud_count > 0:
            score -= 0.5
            weaknesses.append("云服务使用会增加运营成本")

        # 检查商业软件
        commercial_tech = ["oracle", "windows server", "sql server"]
        if any(commercial in " ".join(technologies).lower() for commercial in commercial_tech):
            score -= 1.5
            weaknesses.append("使用商业软件增加授权成本")
            suggestions.append("考虑开源替代方案")

        # 检查复杂度对成本的影响
        if architecture_info["complexity"] == "high":
            score -= 1.5
            weaknesses.append("架构复杂度高，开发和维护成本高")
        elif architecture_info["complexity"] == "low":
            score += 1.0
            strengths.append("架构简洁，成本可控")

        # 检查容器化技术（可能降低部署成本）
        if any(tech in ["docker", "kubernetes"] for tech in technologies):
            score += 0.5
            strengths.append("容器化技术有助于降低部署成本")

        score = max(0, min(10, score))

        return {
            "score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "weight": 1.0,
        }

    def _generate_report(self, architecture_info: Dict[str, Any], evaluation_focus: str,
                        project_scale: str, evaluation_results: Dict[str, Any]) -> str:
        """生成完整评估报告"""
        dimensions = evaluation_results["dimensions"]
        overall_score = evaluation_results["overall_score"]

        # 评分等级
        if overall_score >= 8.0:
            grade = "优秀 (Excellent)"
            color = "🟢"
        elif overall_score >= 6.0:
            grade = "良好 (Good)"
            color = "🟡"
        elif overall_score >= 4.0:
            grade = "一般 (Fair)"
            color = "🟠"
        else:
            grade = "需要改进 (Needs Improvement)"
            color = "🔴"

        report = f"""# 架构评估报告

## 评估概览
- **总体评分**: {overall_score:.2f}/10.0 {color} {grade}
- **评估重点**: {evaluation_focus}
- **项目规模**: {project_scale}
- **架构复杂度**: {architecture_info['complexity']}

## 架构分析摘要
- **识别组件**: {', '.join(architecture_info['components'][:5])}{'...' if len(architecture_info['components']) > 5 else ''}
- **技术栈**: {', '.join(architecture_info['technologies'][:5])}{'...' if len(architecture_info['technologies']) > 5 else ''}
- **架构模式**: {', '.join(architecture_info['patterns']) if architecture_info['patterns'] else '未识别到明确模式'}

## 维度评估详情
"""

        # 各维度评估
        for dimension, data in dimensions.items():
            dim_score = data["score"]
            dim_strengths = data["strengths"]
            dim_weaknesses = data["weaknesses"]
            dim_suggestions = data["suggestions"]

            report += f"\n### {dimension.upper()} - {dim_score:.2f}/10.0\n"

            if dim_strengths:
                report += "**优势**:\n"
                for strength in dim_strengths:
                    report += f"- ✅ {strength}\n"

            if dim_weaknesses:
                report += "**不足**:\n"
                for weakness in dim_weaknesses:
                    report += f"- ⚠️ {weakness}\n"

            if dim_suggestions:
                report += "**改进建议**:\n"
                for suggestion in dim_suggestions:
                    report += f"- 💡 {suggestion}\n"

        # 关键建议汇总
        report += "\n## 关键改进建议\n"
        all_suggestions = []
        for dimension, data in dimensions.items():
            if data["score"] < 6.0:  # 分数较低的维度
                for suggestion in data["suggestions"][:2]:  # 取前两条建议
                    if suggestion not in all_suggestions:
                        all_suggestions.append(suggestion)

        if all_suggestions:
            for i, suggestion in enumerate(all_suggestions[:5], 1):  # 最多5条
                report += f"{i}. {suggestion}\n"
        else:
            report += "架构整体良好，无关键改进项。\n"

        # 实施路线图建议
        report += f"""
## 实施路线图建议

根据项目规模 **{project_scale}** 和评估结果，建议按以下优先级进行优化：

1. **高优先级** (Score < 5.0): 立即处理的安全问题和性能瓶颈
2. **中优先级** (Score 5.0-6.5): 架构优化和可维护性改进
3. **低优先级** (Score > 6.5): 优化和成本控制

## 结构化数据（JSON）
```json
{json.dumps({
    "architecture_info": architecture_info,
    "evaluation_config": {"focus": evaluation_focus, "project_scale": project_scale},
    "evaluation_results": evaluation_results,
    "summary": {
        "overall_score": overall_score,
        "grade": grade,
        "priority_areas": [dim for dim, data in dimensions.items() if data["score"] < 6.0]
    }
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = ArchitectureEvaluatorTool()

    test_architecture = """
    这是一个微服务架构的电商系统，包含以下组件：
    1. 用户服务 (User Service) - 负责用户认证和授权，使用Python Flask开发
    2. 商品服务 (Product Service) - 管理商品信息，使用Java Spring Boot
    3. 订单服务 (Order Service) - 处理订单流程，使用Python FastAPI
    4. 支付服务 (Payment Service) - 集成第三方支付，使用Node.js
    5. API网关 (API Gateway) - 统一入口，负载均衡
    6. 数据库: MySQL用于业务数据，Redis用于缓存，MongoDB用于日志
    7. 消息队列: Kafka用于异步处理订单
    8. 容器化部署: Docker + Kubernetes
    9. 监控: Prometheus + Grafana
    10. 部署在阿里云上
    """

    result = tool._run(
        architecture_description=test_architecture,
        evaluation_focus="comprehensive",
        project_scale="medium"
    )

    print("测试结果:")
    print(result)