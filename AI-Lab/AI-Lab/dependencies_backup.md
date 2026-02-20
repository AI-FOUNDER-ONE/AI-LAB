# 虚拟环境迁移备份 - AI-Lab-Commander
# 备份时间: $(date)
# 总文件数: 87,796 (虚拟环境占99.7%)
# 总磁盘占用: ~2.4GB

## 当前虚拟环境状态
1. `.venv/` - 13,389文件, 476MB (Python 3.x)
2. `.venv_311/` - 37,085文件, 982MB (Python 3.11)
3. `venv311/` - 37,085文件, 982MB (可能是.venv_311副本)

## 依赖配置文件

### pyproject.toml (已存在，PEP 621标准)
```
[project]
name = "ai-lab-commander"
version = "0.1.0"
description = "AI multi-agent collaboration platform for project development"
requires-python = ">=3.10"
dependencies = [
    "PyQt6>=6.6.0",
    "openai>=1.12.0",
    "google-generativeai>=0.4.0",
    "anthropic>=0.18.0",
    "zhipuai>=2.0.0",
    "python-dotenv>=1.0.0",
    "crewai>=0.11.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-qt>=4.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0",
]
```

### requirements.txt (将迁移到Poetry)
```
PyQt6>=6.6.0
openai>=1.12.0
google-generativeai>=0.4.0
anthropic>=0.18.0
zhipuai>=2.0.0
python-dotenv>=1.0.0
crewai>=0.11.0
```

### requirements-dev.txt (将迁移到Poetry开发依赖组)
```
pytest>=7.0.0
pytest-qt>=4.0.0
pytest-cov>=4.0.0
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.0.0
pre-commit>=3.0.0
```

## 迁移计划
1. 安装Poetry
2. 配置Poetry使用外部虚拟环境
3. 从pyproject.toml初始化Poetry项目
4. 安装依赖
5. 清理旧虚拟环境

## 预期结果
- 项目文件数: 87,796 → ~200个
- 虚拟环境位置: 项目内 → 外部全局目录
- 磁盘占用: 2.4GB → <50MB (仅项目文件)
- 依赖管理: 分散冗余 → 统一标准化