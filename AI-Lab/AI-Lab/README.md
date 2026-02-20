# AI-Lab-Commander

AI 多角色协作平台，基于 PyQt6 构建的桌面应用。

## 项目概述

AI-Lab-Commander 是一个多 AI 角色协作平台，通过模拟真实项目团队的工作流程，将复杂任务分解为多个专业角色协同完成。

## 核心特性

- **六角色协作团队**：CKO (首席知识官)、PM (项目经理)、Arch (架构师)、Designer (设计师)、Coder (程序员)、Tester (测试员)
- **状态机驱动工作流**：IDLE → GROUNDING → DEBATE → PRODUCTION → VERIFICATION → COMPLETED
- **多 AI 提供商支持**：Gemini、DeepSeek、Claude、GLM、xAI、VolcEngine 等
- **线程安全架构**：所有 API 调用在后台线程执行，不阻塞 UI
- **实时日志与审计**：CKO Vision Keeper 关键节点审计机制
- **现代化 UI**：三面板布局 (Bridge/War Room/Execution) + 底部时间轴

## 快速开始

### 环境要求
- Python 3.10+
- PyQt6
- API 密钥（至少一个 AI 提供商）

### 安装步骤

1. 克隆仓库：
   ```bash
   git clone <repository-url>
   cd AI-Lab-Commander
   ```

2. 创建虚拟环境：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # 或
   .venv\Scripts\activate  # Windows
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入你的 API 密钥
   ```

5. 运行应用：
   ```bash
   python main.py
   ```

### 开发环境

安装开发依赖：
```bash
pip install -r requirements-dev.txt
```

运行测试：
```bash
pytest
```

代码格式化：
```bash
black .
isort .
```

## 架构设计

### 核心组件

1. **Orchestrator** (`core/orchestrator.py`) - 编排引擎，驱动工作流
2. **BaseAgent** (`agents/base_agent.py`) - 所有 AI 角色的抽象基类
3. **StateController** (`core/state_controller.py`) - 状态机控制器
4. **SessionStore** (`core/session_store.py`) - 会话数据管理
5. **Logger** (`core/logger.py`) - 统一日志系统

### 工作流程

1. **需求打磨 (GROUNDING)**：用户与 CKO 对话，明确需求
2. **方案博弈 (DEBATE)**：PM 解读任务书，组织 Arch 和 Designer 设计方案
3. **代码编写 (PRODUCTION)**：Coder 根据设计方案实现代码
4. **测试验证 (VERIFICATION)**：Tester 验证代码质量
5. **交付完成 (COMPLETED)**：PM 终审，项目完成

### 角色配置

在 `config.py` 中配置各角色使用的 AI 模型：

```python
AGENT_MODELS = {
    "KE":       {"provider": "novai", "model": "gemini-3-pro-preview-thinking"},
    "PM":       {"provider": "xai",   "model": "grok-4-0709"},
    "Arch":     {"provider": "volcengine", "model": "doubao-seed-2-0-pro-260215"},
    # ...
}
```

## 配置说明

### API 密钥支持

支持以下 AI 提供商：
- Gemini (Google)
- DeepSeek
- Claude (Anthropic)
- GLM (智谱AI)
- xAI (Grok)
- Qwen (通义千问)
- VolcEngine (火山引擎)
- NovAI (Gemini 代理)

### 环境变量

参考 `.env.example` 文件，配置所需的 API 密钥。

## 测试

项目包含单元测试和集成测试：

```bash
# 运行所有测试
pytest

# 运行特定测试模块
pytest tests/unit/test_state_controller.py

# 生成测试覆盖率报告
pytest --cov=core --cov=agents tests/
```

## 开发指南

### 代码规范
- 使用 Black 进行代码格式化
- 使用 isort 进行导入排序
- 使用 flake8 进行代码检查
- 使用 mypy 进行类型检查

### 提交前检查
```bash
black . --check
isort . --check-only
flake8 .
mypy .
```

### 添加新功能
1. 创建对应的 Agent 类（继承 BaseAgent）
2. 在 Orchestrator 中集成新角色
3. 更新状态机逻辑（如果需要）
4. 添加单元测试

## 故障排除

### 常见问题

1. **线程安全问题**：如果遇到 "QThread: Destroyed while thread is still running"，检查 `orchestrator.py` 中的线程管理逻辑。

2. **API 密钥错误**：确保 `.env` 文件中的 API 密钥正确，并在 `config.py` 中正确引用。

3. **UI 冻结**：所有长时间运行的操作都应在 QThread 中执行，检查是否阻塞了 UI 线程。

### 日志查看

应用日志保存在 `data/logs/` 目录下，按日期分割：
- `ai_lab_YYYYMMDD.log` - 应用日志
- `crash.log` - 崩溃日志

## 路线图

- [ ] 插件系统支持
- [ ] 多语言界面
- [ ] 离线模式
- [ ] 团队协作功能
- [ ] 云同步

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 贡献指南

欢迎提交 Issue 和 Pull Request。在提交代码前，请确保：
1. 代码通过所有测试
2. 遵循代码规范
3. 更新相关文档

## 联系方式

如有问题或建议，请通过项目 Issue 页面提交。