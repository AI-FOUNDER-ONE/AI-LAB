"""
crew_agents.py — AI-Lab-Commander 增强版 Agent 定义
=====================================================
定义 6 个核心 Agent 及其角色信息、LLM 配置。

增强:
  - 每个 Agent 的 backstory 增加 War Room 交互行为指令
  - 鼓励 @提及、明确表态、引用前文
  - 每个 Agent 带有独特的「讨论风格」描述

安全性审计:
  ✅ API 密钥通过 config.py 统一管理
  ✅ LLM 初始化封装在 get_llm() 中
"""
import os
from crewai import Agent, LLM
from config import API_KEYS, AGENT_MODELS

# ---------- 工具导入 ----------
from tools.crew_tools import DocxParserTool, CodeWriterTool
from tools.mermaid_tool import MermaidTool
from tools.matplotlib_design_tool import MatplotlibDesignTool
from tools.docx_generator_tool import DocxGeneratorTool
from tools.docx_generator_tool import DocxGeneratorTool
from tools.validation_tool import ValidationTool, PytestRunnerTool, TypeCheckTool

# ---------- LLM 初始化工厂 ----------

# 全局: 让 LiteLLM 自动丢弃不支持的参数（如 grok 不支持 stop/temperature）
try:
    import litellm
    litellm.drop_params = True
except ImportError:
    pass

# ---------- Anthropic Client Monkey-Patch ----------
# yunyi 代理不支持 system 参数以字符串格式传递 (返回 500)，
# 但接受数组格式 [{"type":"text","text":"..."}]。
# CrewAI 的 Anthropic provider 内部以字符串形式发送 system，
# 这里拦截 client.messages.create 自动转换格式。
def _patch_anthropic_client():
    """拦截 Anthropic Messages.create，将 system 字符串转为数组格式。"""
    try:
        from anthropic.resources.messages import Messages
        _original_create = Messages.create

        def _patched_create(self, *args, **kwargs):
            system = kwargs.get("system")
            if isinstance(system, str) and system:
                # 将字符串转为 yunyi 兼容的数组格式
                kwargs["system"] = [{"type": "text", "text": system}]
            return _original_create(self, *args, **kwargs)

        Messages.create = _patched_create
        print("[PATCH] Anthropic Messages.create 已 patch (system string → array)")
    except Exception as e:
        print(f"[PATCH] Anthropic patch 跳过: {e}")

_patch_anthropic_client()

def get_llm(role: str) -> LLM:
    """根据角色配置创建 CrewAI 原生 LLM 实例。

    Provider 策略:
      - hiapi/deepseek: openai/ 前缀 + base_url → OpenAI 兼容
      - xai: openai/ 前缀, 通过 litellm.drop_params 丢弃 stop
      - claude_custom (yunyi): anthropic/ 前缀 + ANTHROPIC_API_KEY 环境变量

    Args:
        role: Agent 角色名 (CKO/PM/Arch/Designer/Coder/Tester)

    Returns:
        LLM: CrewAI 原生 LLM 实例
    """
    cfg = AGENT_MODELS.get(role, {"provider": "hiapi", "model": "gpt-4o", "base_url": "https://hiapi.online/v1"})
    provider = cfg["provider"]
    model = cfg["model"]
    base_url = cfg.get("base_url", "https://hiapi.online/v1")
    api_key = API_KEYS.get(provider, "")
    api_type = cfg.get("api_type", "openai")

    # ① Anthropic 代理 (yunyi) — 设置环境变量让 CrewAI Anthropic provider 认证
    if api_type == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
        os.environ["ANTHROPIC_BASE_URL"] = base_url
        return LLM(
            model=f"anthropic/{model}",
            temperature=0.7,
            max_tokens=8000,
        )

    # ② xAI (Grok) — 无前缀, 走 LiteLLM 通道, 利用 drop_params 丢弃不支持的 stop 参数
    # 注意: openai/ 前缀走 CrewAI 内置 OpenAI provider, 不经过 LiteLLM, drop_params 无效
    if provider == "xai":
        os.environ["XAI_API_KEY"] = api_key
        return LLM(
            model=f"xai/{model}",
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
            max_tokens=8000,
        )

    # ③ OpenAI 兼容 API (hiapi/deepseek/volcengine) — openai/ 前缀 + base_url
    return LLM(
        model=f"openai/{model}",
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
        max_tokens=8000,
    )


# ==============================================================================
#  Agent 定义 — 带增强 War Room 交互指令 (工厂模式)
# ==============================================================================

def create_agents(step_callback=None):
    """创建并返回一组新的 Agent 实例 (支持动态配置和回调)。

    Args:
        step_callback: CrewAI step callback function for streaming thoughts.

    Returns:
        Dict[str, Agent]: 角色名到 Agent 实例的映射
    """
    agents = {}

    # CKO (Chief Knowledge Officer) - 原 KE
    agents["CKO"] = Agent(
        role="CKO · 首席知识官",
        goal="深入理解用户需求，生成结构化任务协议",
        backstory=(
            "你是一位资深的首席知识官 (CKO)，擅长需求分析和知识管理。"
            "你的核心职责是确保项目有清晰、可执行的任务协议。\n\n"
            "## War Room 交互规则\n"
            "- 当其他人讨论需求变更时，主动用 @角色名 @PM 确认是否需要更新任务协议\n"
            "- 你说话风格温和但严谨，善用反问引导深入思考\n"
            "- 发现模糊需求时必须追问，不要假设\n"
            "- 引用之前的讨论：'正如之前提到的…'\n"
            "- 明确表态时说 '我同意…' 或 '我认为需要更多信息…'"
        ),
        verbose=True,
        llm=get_llm("CKO"),
        tools=[DocxParserTool()],
        allow_delegation=False,
        step_callback=step_callback,
    )

    # QA (Quality Auditor) - 新增角色
    agents["QA"] = Agent(
        role="QA · 质量审计",
        goal="监督辩论质量，确保方案完整性和合规性",
        backstory=(
            "你是一位严格的质量审计师 (QA)，负责监督项目流程和交付物质量。"
            "你不直接产出方案，而是评估各方输出是否符合规范和安全性要求。\n\n"
            "## War Room 交互规则\n"
            "- 在辩论中，关注非功能性需求（安全、合规、性能）\n"
            "- 发现方案存在风险时，主动 @PM 预警\n"
            "- 审核 Coder 的代码和 Tester 的测试报告是否闭环\n"
            "- 你的风格是客观、冷静、基于事实"
        ),
        verbose=True,
        llm=get_llm("QA"),
        allow_delegation=False,
        step_callback=step_callback,
    )

    # PM
    agents["PM"] = Agent(
        role="PM · 项目经理",
        goal="主持讨论，推动共识达成，管理项目进度",
        backstory=(
            "你是一位经验丰富的项目经理 (PM)，擅长引导团队讨论达成共识。"
            "你是 War Room 的主持人，负责推进议程、总结决策。\n\n"
            "## War Room 交互规则\n"
            "- 每轮开始时先总结上轮要点和未决问题\n"
            "- 主动 @角色名 邀请特定角色发言（如 '@Arch 对技术选型有什么看法？'）\n"
            "- 检测到分歧时，用 @角色名 明确指出冲突双方\n"
            "- 推动投票时说 '让我们对当前方案表态'\n"
            "- 形成共识时说 '方案通过' 或 '我同意现有方案'\n"
            "- 果断但公平，确保每个角色都有发言机会"
        ),
        verbose=True,
        llm=get_llm("PM"),
        allow_delegation=True,
        step_callback=step_callback,
    )

    # Arch
    agents["Arch"] = Agent(
        role="Arch · 架构师",
        goal="设计技术架构，评估方案的可行性和扩展性",
        backstory=(
            "你是一位资深系统架构师 (Arch)，擅长技术架构设计和系统思维。"
            "你关注性能、扩展性、模块化和技术选型。\n\n"
            "## War Room 交互规则\n"
            "- 当讨论涉及技术选型时，必须主动发言\n"
            "- 用 @Designer 讨论架构对 UI 的影响，用 @Coder 讨论实现复杂度\n"
            "- 如果你反对某方案，必须说 '我反对' 并提出替代方案\n"
            "- 引用之前的讨论：'正如 @某某 在第 N 轮提到的…'\n"
            "- 用具体的技术指标（QPS、延迟、内存）支撑你的观点\n"
            "- 明确表态：'我同意 @PM 的方案' 或 '我认为有更好的选择'"
        ),
        verbose=True,
        llm=get_llm("Arch"),
        tools=[MermaidTool()],
        allow_delegation=False,
        step_callback=step_callback,
    )

    # Designer
    agents["Designer"] = Agent(
        role="Designer · 设计师",
        goal="制定详细设计方案，确保用户体验和可实现性",
        backstory=(
            "你是一位全栈设计师 (Designer)，同时精通 UX 设计和技术实现方案。"
            "你关注用户体验、界面交互和设计与工程的平衡。\n\n"
            "## War Room 交互规则\n"
            "- 当 @Arch 提出架构方案时，评估其对用户体验的影响\n"
            "- 当需要 Coder 评估工作量时，主动 @Coder 提问\n"
            "- 如果架构限制导致 UX 降级，必须说 '我反对' 并解释原因\n"
            "- 善于用场景描述来支撑设计决策\n"
            "- 明确表态：'这个方案对用户体验…' 或 '我同意…但建议…'"
        ),
        verbose=True,
        llm=get_llm("Designer"),
        tools=[MatplotlibDesignTool()],
        allow_delegation=False,
        step_callback=step_callback,
    )

    # Coder
    agents["Coder"] = Agent(
        role="Coder · 程序员",
        goal="编写高质量、符合规范的生产代码",
        backstory=(
            "你是一位资深全栈工程师 (Coder)，擅长 Python 开发和代码设计。"
            "你遵循 Google 编程规范，注重代码质量、可维护性和安全性。\n\n"
            "## War Room 交互规则\n"
            "- 当 @Arch 或 @Designer 讨论方案时，从实现复杂度角度评估\n"
            "- 如果方案实现困难，主动说 '实现需要…' 并给出工作量估算\n"
            "- 收到 @Tester 的缺陷报告时，分析根因并给出修复方案\n"
            "- 代码输出使用 ```python 代码块 ```\n"
            "- 所有注释使用详细中文"
        ),
        verbose=True,
        llm=get_llm("Coder"),
        # 注意: tools 在这里虽初始化，但在 commander_crew_v2 中会被动态覆盖/补充
        tools=[CodeWriterTool(), DocxGeneratorTool()],
        allow_delegation=False,
        step_callback=step_callback,
    )

    # Tester
    agents["Tester"] = Agent(
        role="Tester · 测试员",
        goal="验证代码质量，发现缺陷并给出修复建议",
        backstory=(
            "你是一位严谨的 QA 工程师 (Tester)，擅长质量保证和测试策略。"
            "你关注边界条件、错误处理、安全漏洞和代码规范。\n\n"
            "## War Room 交互规则\n"
            "- 直接 @Coder 报告问题和修复建议\n"
            "- 测试通过时说 '测试通过 ✅' + 验证要点\n"
            "- 测试失败时说 '测试失败 ❌' + 具体问题 + 修复方向\n"
            "- 关注安全性、性能和边界条件，对每个细节都不放过\n"
            "- 发现问题同时给出修复建议，而不是只指出问题\n"
            "- **工具使用**：\n"
            "  - 使用 `python_code_validator` 进行静态语法检查\n"
            "  - 使用 `pytest_runner` 运行单元测试 (确保测试文件存在)\n"
            "  - 使用 `mypy_checker` 进行类型检查"
        ),
        verbose=True,
        llm=get_llm("Tester"),
        tools=[ValidationTool(), PytestRunnerTool(), TypeCheckTool()],
        allow_delegation=False,
        step_callback=step_callback,
    )

    return agents
