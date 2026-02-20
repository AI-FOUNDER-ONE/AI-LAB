# AI-Lab-Commander 虚拟环境迁移指南
# 从项目内虚拟环境迁移到外部Poetry管理

## 📊 当前问题分析
项目总文件数: 87,796个，其中:
- 虚拟环境和缓存: 87,559个 (99.7%)
- 实际项目代码: 204个 (0.2%)
- 磁盘占用: ~2.4GB

虚拟环境位置（项目内）:
- `.venv/` - 476MB
- `.venv_311/` - 982MB
- `venv311/` - 982MB (可能是副本)

## 🎯 迁移目标
1. 虚拟环境移到外部全局目录
2. 使用Poetry统一管理依赖
3. 项目目录仅保留源代码
4. 文件数: 87,796 → ~200个
5. 磁盘占用: 2.4GB → <50MB (仅项目)

## 📋 迁移步骤

### 第1步：清理Python缓存文件（安全操作）
```bash
# 删除所有Python缓存文件（可重新生成）
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# 清理后预计减少33,106个文件
```

### 第2步：安装Poetry
```bash
# 方法1: 官方安装脚本
curl -sSL https://install.python-poetry.org | python3 -

# 方法2: 使用pip安装
pip install --user poetry

# 验证安装
poetry --version
```

### 第3步：配置Poetry使用外部虚拟环境
```bash
# 配置虚拟环境在项目外创建
poetry config virtualenvs.in-project false

# 设置虚拟环境存储位置（默认: ~/.cache/pypoetry/virtualenvs/）
poetry config virtualenvs.path ~/.cache/pypoetry/virtualenvs

# 验证配置
poetry config --list
```

### 第4步：初始化Poetry项目
```bash
# 项目已有pyproject.toml（PEP 621标准），直接初始化
poetry init --no-interaction

# 或从现有pyproject.toml创建poetry.toml
cp pyproject.toml poetry.toml
```

### 第5步：安装依赖
```bash
# 安装主依赖（从pyproject.toml读取）
poetry install

# 安装开发依赖
poetry add --group dev pytest black isort flake8 mypy pre-commit pytest-qt pytest-cov

# 或一次性安装所有依赖
poetry install --with dev
```

### 第6步：验证新环境
```bash
# 激活Poetry环境
poetry shell

# 验证Python版本
python --version

# 验证依赖安装
poetry run python -c "import PyQt6; import openai; import crewai; print('所有依赖加载成功')"

# 运行主程序测试
poetry run python main.py
```

### 第7步：清理旧虚拟环境
```bash
# 确认新环境正常工作后，删除旧虚拟环境
rm -rf .venv .venv_311 venv311

# 删除冗余依赖文件（可选）
rm requirements.txt requirements-dev.txt
```

### 第8步：配置IDE（VSCode示例）
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
    // 改为使用Poetry环境
    "python.terminal.activateEnvironment": true,
    "python.terminal.activateEnvInCurrentTerminal": true,
    "python.poetryPath": "poetry"
}
```

或手动选择解释器路径：`~/.cache/pypoetry/virtualenvs/ai-lab-commander-*/bin/python`

## 🔧 日常使用命令

### 激活环境
```bash
# 进入项目目录，激活环境
poetry shell

# 或直接运行命令
poetry run python main.py
poetry run pytest
```

### 添加/移除依赖
```bash
# 添加生产依赖
poetry add package_name

# 添加开发依赖
poetry add --group dev package_name

# 移除依赖
poetry remove package_name

# 更新所有依赖
poetry update
```

### 环境管理
```bash
# 列出所有虚拟环境
poetry env list

# 显示当前环境信息
poetry env info

# 删除虚拟环境
poetry env remove python
```

## ⚠️ 注意事项

### 1. 备份重要数据
- 确保 `data/sessions/` 中的会话历史已备份
- 检查 `.env` 文件中的API密钥配置

### 2. 环境隔离
- Poetry环境与系统Python完全隔离
- 不同项目使用独立虚拟环境

### 3. 依赖锁定
- `poetry.lock` 文件确保环境一致性
- 提交 `poetry.lock` 到版本控制

### 4. CI/CD配置
```yaml
# GitHub Actions示例
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install poetry
      - run: poetry install --with dev
      - run: poetry run pytest
```

## 📊 迁移前后对比

| 指标 | 迁移前 | 迁移后 |
|------|--------|--------|
| **项目文件数** | 87,796 | **~200** |
| **磁盘占用** | 2.4GB | **<50MB** |
| **虚拟环境位置** | 项目内 | 外部全局 |
| **依赖管理** | 分散(3文件) | 统一(pyproject.toml) |
| **环境复现** | 手动操作 | `poetry install`一键完成 |
| **Git性能** | 扫描87k+文件 | 扫描200+文件 |

## 🆘 故障排除

### Poetry安装问题
```bash
# 如果pip安装失败
python -m pip install --user poetry

# 配置环境变量（Windows）
set PATH=%APPDATA%\Python\Scripts;%PATH%
```

### 依赖冲突
```bash
# 查看依赖树
poetry show --tree

# 更新特定包
poetry update package_name

# 清除缓存并重试
poetry cache clear --all pypi
```

### 环境激活失败
```bash
# 重新创建虚拟环境
poetry env remove python
poetry install

# 手动指定Python路径
poetry env use /path/to/python
```

## 🎉 迁移完成验证
1. ✅ `poetry run python main.py` 正常运行
2. ✅ 项目目录仅剩源代码文件（~200个）
3. ✅ 虚拟环境在 `~/.cache/pypoetry/virtualenvs/`
4. ✅ Git操作变快（仅跟踪核心文件）
5. ✅ IDE索引性能提升

---

**重要提示**: 建议在执行第7步（删除旧虚拟环境）前，完全验证新环境工作正常。可以保留旧环境1-2天作为回滚备份。