"""
requirements_analyzer_tool.py - 需求分析工具
============================================
供 CKO（首席知识官）使用，对用户需求进行深度分析，输出结构化需求（JSON）。

安全性审计:
  ✅ 仅分析文本，不执行代码
  ✅ 输入内容经过清洗处理
  ✅ 输出结构化 JSON，无副作用
"""

import re
import json
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field

# ---------- 结构化输出 Schema（LLM 必须按此格式返回 JSON）----------
REQUIREMENTS_SCHEMA = {
    "goals": ["str"],              # 项目目标列表
    "constraints": ["str"],        # 约束条件
    "inputs": ["str"],             # 输入物
    "outputs": ["str"],            # 期望产出
    "acceptance_criteria": ["str"],  # 验收标准
    "dependencies": ["str"],       # 外部依赖
    "priority": "HIGH|MEDIUM|LOW",  # 优先级
}

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

    def _run(
        self, user_input: str, analysis_depth: str = "standard", domain_hint: str = ""
    ) -> Dict[str, Any]:
        """执行需求分析，调用 LLM 生成结构化 JSON，解析失败时最多重试 2 次。

        Args:
            user_input: 用户的原始需求描述
            analysis_depth: 分析深度级别（quick/standard/deep）
            domain_hint: 领域提示词

        Returns:
            解析后的需求结构 dict，符合 REQUIREMENTS_SCHEMA。
        """
        cleaned_input = self._preprocess_input(user_input)
        prompt = self._build_structured_prompt(cleaned_input, analysis_depth, domain_hint)
        max_attempts = 3  # 首次 + 最多 2 次重试
        last_error: Optional[Exception] = None
        for attempt in range(max_attempts):
            try:
                raw = self._call_llm(prompt)
                data = self._parse_json_from_response(raw)
                return self._normalize_to_schema(data)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    prompt = self._build_retry_prompt(cleaned_input, analysis_depth, domain_hint, str(e))
                continue
        return {
            "goals": [],
            "constraints": [],
            "inputs": [],
            "outputs": [],
            "acceptance_criteria": [],
            "dependencies": [],
            "priority": "MEDIUM",
            "_error": f"解析失败（已重试 {max_attempts - 1} 次）: {last_error!s}",
        }

    def _preprocess_input(self, user_input: str) -> str:
        """预处理用户输入"""
        return re.sub(r"\s+", " ", user_input.strip())

    def _build_structured_prompt(
        self, user_input: str, analysis_depth: str, domain_hint: str
    ) -> str:
        """构建要求输出 JSON 的 prompt。"""
        schema_desc = json.dumps(REQUIREMENTS_SCHEMA, ensure_ascii=False)
        depth_hint = {"quick": "简要列出", "standard": "完整列出", "deep": "详尽列出"}.get(
            analysis_depth, "完整列出"
        )
        domain_part = f"领域提示：{domain_hint}。" if domain_hint else ""
        return f"""你是一名需求分析专家。请根据用户的描述，输出**唯一一段合法 JSON**，不要包含任何其他文字、markdown 标记或代码块包裹。

输出必须严格符合以下结构（键名与类型不可改）：
{schema_desc}

要求：
- goals: 项目目标列表，{depth_hint}。
- constraints: 约束条件（时间、资源、技术等）。
- inputs: 输入物（文档、数据、接口等）。
- outputs: 期望产出（交付物、功能、指标等）。
- acceptance_criteria: 验收标准列表。
- dependencies: 外部依赖（系统、服务、人力等）。
- priority: 取 exactly  one of "HIGH" | "MEDIUM" | "LOW"。

用户需求描述：
---
{user_input}
---
{domain_part}

请只输出一行或一块合法 JSON，不要用 ```json 包裹。"""

    def _build_retry_prompt(
        self, user_input: str, analysis_depth: str, domain_hint: str, parse_error: str
    ) -> str:
        """重试时强调只要 JSON、并提示上次解析错误。"""
        base = self._build_structured_prompt(user_input, analysis_depth, domain_hint)
        return base + f"\n\n（上次解析错误，请务必只输出合法 JSON：{parse_error}）"

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM，返回模型回复正文。"""
        try:
            from config import AGENT_MODELS
            from core.llm_client_factory import create_llm_client
            cfg = AGENT_MODELS.get("CKO", {"provider": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com"})
            client = create_llm_client(cfg["provider"], cfg)
            model = cfg.get("model", "deepseek-chat")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )
            content = resp.choices[0].message.content
            return (content or "").strip()
        except Exception as e:
            raise ValueError(f"LLM 调用失败: {e}") from e

    def _parse_json_from_response(self, raw: str) -> Dict[str, Any]:
        """从回复中提取并解析 JSON，解析失败则抛出 json.JSONDecodeError。"""
        text = raw.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end]
        return json.loads(text)

    def _normalize_to_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将解析结果规范为 REQUIREMENTS_SCHEMA 结构。"""
        def to_str_list(v: Any) -> List[str]:
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x) for x in v]
            return [str(v)]

        priority = (data.get("priority") or "MEDIUM").upper()
        if priority not in ("HIGH", "MEDIUM", "LOW"):
            priority = "MEDIUM"
        return {
            "goals": to_str_list(data.get("goals")),
            "constraints": to_str_list(data.get("constraints")),
            "inputs": to_str_list(data.get("inputs")),
            "outputs": to_str_list(data.get("outputs")),
            "acceptance_criteria": to_str_list(data.get("acceptance_criteria")),
            "dependencies": to_str_list(data.get("dependencies")),
            "priority": priority,
        }


# 示例用法
if __name__ == "__main__":
    tool = RequirementsAnalyzerTool()
    test_input = "我想开发一个个人财务管理应用，帮助我追踪日常开支和投资，最好能有图表分析功能。"
    result = tool._run(
        user_input=test_input,
        analysis_depth="standard",
        domain_hint="软件开发",
    )
    print("测试结果 (结构化 dict):")
    print(json.dumps(result, ensure_ascii=False, indent=2))