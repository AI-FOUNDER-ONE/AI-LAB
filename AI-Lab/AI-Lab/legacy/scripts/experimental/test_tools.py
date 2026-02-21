"""
test_tools.py - 新增自定义工具单元测试
========================================
测试 MermaidTool、MatplotlibDesignTool、DocxGeneratorTool、ValidationTool
的 _run() 方法是否正常工作。

安全性审计:
  ✅ 测试文件产出写入 data/generated_docs/ 目录
  ✅ 不涉及外部 API 调用
  ✅ 测试完成后不清理文件（供人工检查）
"""

import sys
import os
import json

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ---------- 导入工具 ----------
from tools.mermaid_tool import MermaidTool
from tools.matplotlib_design_tool import MatplotlibDesignTool
from tools.docx_generator_tool import DocxGeneratorTool
from tools.validation_tool import ValidationTool


def test_mermaid_tool():
    """测试 MermaidTool: 生成 .mmd 文件"""
    print("[1/4] 测试 MermaidTool...")
    tool = MermaidTool()
    mermaid_code = """graph TD
    A[用户请求] --> B[CKO 分析]
    B --> C[PM 主持辩论]
    C --> D[Arch 架构设计]
    C --> E[Designer 详细设计]
    D --> F[Coder 编码]
    E --> F
    F --> G[Tester 验证]
    G -->|通过| H[交付]
    G -->|失败| C"""

    result = tool._run(code=mermaid_code, filename="test_architecture")
    print(f"  结果: {result}")
    assert "✅" in result, f"MermaidTool 失败: {result}"
    print("  [OK] MermaidTool 通过\n")
    return True


def test_matplotlib_design_tool():
    """测试 MatplotlibDesignTool: 生成 PNG 设计图"""
    print("[2/4] 测试 MatplotlibDesignTool...")
    tool = MatplotlibDesignTool()
    design = {
        "title": "AI-Lab-Commander 系统拓扑",
        "type": "layout",
        "components": [
            {"name": "用户 UI", "x": 0.5, "y": 0.9, "color": "#4FC3F7", "width": 0.7, "height": 0.08},
            {"name": "CommanderCrew", "x": 0.5, "y": 0.75, "color": "#81C784", "width": 0.5, "height": 0.06},
            {"name": "DebateWorker", "x": 0.3, "y": 0.6, "color": "#FFB74D", "width": 0.3, "height": 0.06},
            {"name": "WarRoomContext", "x": 0.7, "y": 0.6, "color": "#CE93D8", "width": 0.3, "height": 0.06},
            {"name": "CrewAI Agents", "x": 0.5, "y": 0.4, "color": "#EF5350", "width": 0.6, "height": 0.08},
            {"name": "LLM APIs", "x": 0.5, "y": 0.2, "color": "#78909C", "width": 0.5, "height": 0.06},
        ],
        "connections": [
            {"from": "用户 UI", "to": "CommanderCrew"},
            {"from": "CommanderCrew", "to": "DebateWorker"},
            {"from": "CommanderCrew", "to": "WarRoomContext"},
            {"from": "DebateWorker", "to": "CrewAI Agents"},
            {"from": "CrewAI Agents", "to": "LLM APIs"},
        ]
    }

    result = tool._run(design_json=json.dumps(design, ensure_ascii=False), filename="test_topology")
    print(f"  结果: {result}")
    has_ok = "✅" in result
    has_no_matplotlib = "matplotlib 未安装" in result
    assert has_ok or has_no_matplotlib, f"MatplotlibDesignTool 失败: {result}"
    print(f"  [OK] MatplotlibDesignTool {'通过' if has_ok else '(matplotlib 未安装，已优雅降级)'}\n")
    return True


def test_docx_generator_tool():
    """测试 DocxGeneratorTool: 生成 Word 文档"""
    print("[3/4] 测试 DocxGeneratorTool...")
    tool = DocxGeneratorTool()
    markdown_content = """# 工业无人机设计方案

## 1. 项目概述

本项目旨在设计一款**工业级多旋翼无人机**，适用于以下场景：

- 电力巡检
- 农业植保
- 地理测绘

## 2. 技术架构

### 2.1 硬件平台

1. 飞控系统：基于 PX4 开源固件
2. 动力系统：6轴 X8 布局
3. 传感器：RTK-GPS + 激光雷达

### 2.2 软件架构

```python
class DroneController:
    def __init__(self):
        self.flight_mode = "STABILIZE"
        self.gps_enabled = True
```

## 3. 项目计划

- **第一阶段**: 需求分析与概念设计 (2周)
- **第二阶段**: 详细设计与原型制造 (4周)
- *第三阶段*: 测试验证与迭代优化 (3周)
"""

    result = tool._run(
        content=markdown_content,
        doc_title="工业无人机设计方案 V1.0",
        filename="test_drone_design"
    )
    print(f"  结果: {result}")
    has_ok = "✅" in result
    has_no_docx = "python-docx 未安装" in result
    assert has_ok or has_no_docx, f"DocxGeneratorTool 失败: {result}"
    print(f"  [OK] DocxGeneratorTool {'通过' if has_ok else '(python-docx 未安装，已优雅降级)'}\n")
    return True


def test_validation_tool():
    """测试 ValidationTool: Python 代码静态验证"""
    print("[4/4] 测试 ValidationTool...")
    tool = ValidationTool()

    # 测试 1: 合法代码
    good_code = '''
import os
from typing import List

def calculate_area(width: float, height: float) -> float:
    """计算矩形面积。

    Args:
        width: 矩形宽度
        height: 矩形高度

    Returns:
        面积值
    """
    if width <= 0 or height <= 0:
        raise ValueError("宽度和高度必须为正数")
    return width * height

class Rectangle:
    """矩形类。"""
    def __init__(self, w: float, h: float):
        self.width = w
        self.height = h
        self.area = calculate_area(w, h)
'''
    result_good = tool._run(code=good_code)
    print(f"  合法代码结果: {result_good[:100]}...")
    assert "语法检查: 通过" in result_good

    # 测试 2: 有问题的代码
    bad_code = '''
import json
import xml

def process():
    try:
        data = json.loads("{}")
    except:
        pass
'''
    result_bad = tool._run(code=bad_code)
    print(f"  问题代码结果: {result_bad[:100]}...")
    assert "语法检查: 通过" in result_bad  # 语法本身没问题
    assert "裸 except" in result_bad or "文档字符串" in result_bad  # 但有质量问题

    # 测试 3: 语法错误代码
    syntax_error_code = '''
def broken_function(
    return None
'''
    result_syntax = tool._run(code=syntax_error_code)
    print(f"  语法错误结果: {result_syntax[:100]}...")
    assert "❌" in result_syntax

    print("  [OK] ValidationTool 通过\n")
    return True


def main():
    """主测试入口"""
    print("=" * 60)
    print("  AI-Lab-Commander - 自定义工具单元测试")
    print("=" * 60)
    print()

    results = {}
    tests = [
        ("MermaidTool", test_mermaid_tool),
        ("MatplotlibDesignTool", test_matplotlib_design_tool),
        ("DocxGeneratorTool", test_docx_generator_tool),
        ("ValidationTool", test_validation_tool),
    ]

    for name, test_fn in tests:
        try:
            results[name] = test_fn()
        except Exception as e:
            print(f"  [FAIL] {name}: {e}\n")
            results[name] = False

    # 汇总
    print("=" * 60)
    print("  Summary Report")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status:6s} {name}")

    print(f"\n  Result: {passed}/{total} passed")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
