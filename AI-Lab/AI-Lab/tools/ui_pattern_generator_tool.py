"""
ui_pattern_generator_tool.py - UI设计模式生成工具
=============================================
供 Designer（设计师）使用，根据需求自动生成UI设计模式建议。
包括布局模式、组件选择、交互模式、配色方案等建议。

安全性审计:
  ✅ 仅分析文本，不执行代码
  ✅ 不读取外部文件
  ✅ 输出结构化UI设计建议
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


class UIPatternGeneratorInput(BaseModel):
    """UIPatternGeneratorTool 的输入参数模型。"""
    ui_requirement: str = Field(
        ...,
        description=(
            "UI需求描述。可以是：\n"
            "1. 产品功能需求\n"
            "2. 用户界面描述\n"
            "3. 用户体验目标\n"
            "4. 设计约束（如平台、屏幕尺寸等）\n"
            "示例：一个电商移动端App的商品列表页面，需要支持搜索、筛选、排序功能，目标用户是年轻消费者。"
        )
    )
    platform: str = Field(
        default="web",
        description=(
            "目标平台。可选值：\n"
            "- 'web': Web应用（默认）\n"
            "- 'mobile': 移动应用\n"
            "- 'desktop': 桌面应用\n"
            "- 'tablet': 平板应用\n"
            "- 'responsive': 响应式设计"
        )
    )
    complexity: str = Field(
        default="medium",
        description=(
            "UI复杂度。可选值：\n"
            "- 'simple': 简单界面（1-3个主要功能）\n"
            "- 'medium': 中等界面（4-7个主要功能，默认）\n"
            "- 'complex': 复杂界面（8+个主要功能）\n"
            "- 'dashboard': 仪表板类型"
        )
    )


class UIPatternGeneratorTool(BaseTool):
    """UI设计模式生成工具。

    根据UI需求自动生成设计模式建议。
    包括布局、组件、交互、配色等方面的专业建议。
    """

    name: str = "ui_pattern_generator"
    description: str = (
        "根据UI需求自动生成设计模式建议。"
        "支持布局模式、组件选择、交互模式、配色方案等建议。"
        "输出结构化UI设计建议，可直接用于设计参考。"
    )
    args_schema: Type[BaseModel] = UIPatternGeneratorInput

    def _run(self, ui_requirement: str, platform: str = "web", complexity: str = "medium") -> str:
        """执行UI设计模式生成。

        Args:
            ui_requirement: UI需求描述
            platform: 目标平台
            complexity: UI复杂度

        Returns:
            格式化的UI设计建议报告
        """
        try:
            # 1. 分析UI需求
            requirement_info = self._analyze_requirement(ui_requirement, platform, complexity)

            # 2. 生成设计模式建议
            pattern_suggestions = self._generate_patterns(requirement_info, platform, complexity)

            # 3. 生成完整报告
            return self._generate_report(requirement_info, platform, complexity, pattern_suggestions)

        except Exception as e:
            return f"❌ UI设计模式生成失败: {str(e)}"

    def _analyze_requirement(self, requirement: str, platform: str, complexity: str) -> Dict[str, Any]:
        """分析UI需求"""
        info = {
            "word_count": len(requirement.split()),
            "has_navigation": False,
            "has_data_display": False,
            "has_forms": False,
            "has_charts": False,
            "has_search": False,
            "has_filters": False,
            "has_user_profile": False,
            "has_shopping": False,
            "has_social": False,
            "has_content": False,
            "key_features": [],
            "user_groups": [],
            "constraints": [],
        }

        # 检查导航需求
        nav_keywords = [
            r'\b(navigation|menu|sidebar|header|footer|tab|tabbar)\b',
            r'\b(routing|route|page|screen|view)\b',
            r'\b(home|dashboard|settings|profile|account)\b',
        ]
        for pattern in nav_keywords:
            if re.search(pattern, requirement, re.IGNORECASE):
                info["has_navigation"] = True
                break

        # 检查数据显示需求
        data_keywords = [
            r'\b(table|list|grid|card|item|row|column)\b',
            r'\b(data|information|details|content|item)\b',
            r'\b(display|show|present|view)\b',
        ]
        for pattern in data_keywords:
            if re.search(pattern, requirement, re.IGNORECASE):
                info["has_data_display"] = True
                break

        # 检查表单需求
        form_keywords = [
            r'\b(form|input|field|textarea|select|dropdown)\b',
            r'\b(button|submit|cancel|save|edit|update)\b',
            r'\b(login|register|signin|signup|authentication)\b',
        ]
        for pattern in form_keywords:
            if re.search(pattern, requirement, re.IGNORECASE):
                info["has_forms"] = True
                break

        # 检查搜索和筛选
        if re.search(r'\b(search|find|query)\b', requirement, re.IGNORECASE):
            info["has_search"] = True
        if re.search(r'\b(filter|sort|order|category)\b', requirement, re.IGNORECASE):
            info["has_filters"] = True

        # 检查购物相关
        if re.search(r'\b(shop|cart|checkout|buy|purchase|product)\b', requirement, re.IGNORECASE):
            info["has_shopping"] = True

        # 检查社交功能
        if re.search(r'\b(social|share|comment|like|follow|message)\b', requirement, re.IGNORECASE):
            info["has_social"] = True

        # 检查图表需求
        if re.search(r'\b(chart|graph|visualization|statistics|analytics)\b', requirement, re.IGNORECASE):
            info["has_charts"] = True

        # 提取关键功能
        functional_phrases = [
            "需要支持", "要实现", "包括功能", "包含", "需要", "必须",
            "should support", "must have", "includes"
        ]
        lines = requirement.split('\n')
        for line in lines:
            line_lower = line.lower()
            for phrase in functional_phrases:
                if phrase in line_lower:
                    info["key_features"].append(line.strip())
                    break

        # 如果关键功能为空，使用整个需求
        if not info["key_features"] and requirement:
            info["key_features"] = [requirement[:200] + "..." if len(requirement) > 200 else requirement]

        return info

    def _generate_patterns(self, requirement_info: Dict[str, Any], platform: str, complexity: str) -> Dict[str, Any]:
        """生成设计模式建议"""
        patterns = {
            "layout_patterns": [],
            "component_patterns": [],
            "interaction_patterns": [],
            "color_palettes": [],
            "typography_suggestions": [],
            "accessibility_recommendations": [],
        }

        # 布局模式建议
        if platform == "mobile":
            patterns["layout_patterns"] = [
                "底部标签栏导航 (Bottom Tab Bar)",
                "侧边抽屉导航 (Drawer Navigation)",
                "全屏滚动布局 (Full-screen Scrolling)",
                "卡片式布局 (Card-based Layout)",
            ]
        elif platform == "web":
            patterns["layout_patterns"] = [
                "响应式网格布局 (Responsive Grid Layout)",
                "侧边栏+主内容布局 (Sidebar + Main Content)",
                "顶部导航+内容区域 (Top Navigation + Content Area)",
                "卡片网格布局 (Card Grid Layout)",
            ]
        else:
            patterns["layout_patterns"] = [
                "自适应网格系统 (Adaptive Grid System)",
                "模块化布局 (Modular Layout)",
                "分层内容结构 (Hierarchical Content Structure)",
            ]

        # 组件模式建议
        component_suggestions = []

        if requirement_info["has_navigation"]:
            if platform == "mobile":
                component_suggestions.append("底部导航栏 (Bottom Navigation Bar)")
                component_suggestions.append("汉堡菜单 (Hamburger Menu)")
            else:
                component_suggestions.append("顶部水平导航栏 (Top Horizontal Navigation)")
                component_suggestions.append("左侧垂直导航栏 (Left Sidebar Navigation)")

        if requirement_info["has_data_display"]:
            if complexity in ["simple", "medium"]:
                component_suggestions.append("卡片列表 (Card List)")
                component_suggestions.append("简单表格 (Simple Table)")
            else:
                component_suggestions.append("可排序表格 (Sortable Table)")
                component_suggestions.append("分页列表 (Paginated List)")
                component_suggestions.append("网格视图 (Grid View)")

        if requirement_info["has_forms"]:
            component_suggestions.append("表单验证组件 (Form Validation Components)")
            component_suggestions.append("输入字段组 (Input Field Groups)")
            if platform == "mobile":
                component_suggestions.append("移动优化表单 (Mobile-optimized Forms)")

        if requirement_info["has_search"]:
            component_suggestions.append("搜索输入框 (Search Input)")
            component_suggestions.append("实时搜索建议 (Real-time Search Suggestions)")

        if requirement_info["has_filters"]:
            component_suggestions.append("筛选面板 (Filter Panel)")
            component_suggestions.append("排序控件 (Sort Controls)")

        if requirement_info["has_shopping"]:
            component_suggestions.append("购物车图标 (Shopping Cart Icon)")
            component_suggestions.append("商品卡片 (Product Card)")
            component_suggestions.append("结账流程组件 (Checkout Flow Components)")

        patterns["component_patterns"] = component_suggestions

        # 交互模式建议
        interaction_patterns = []

        if requirement_info["has_data_display"]:
            interaction_patterns.append("下拉刷新 (Pull-to-refresh)")
            interaction_patterns.append("无限滚动 (Infinite Scroll)")

        if requirement_info["has_search"]:
            interaction_patterns.append("实时搜索 (Real-time Search)")
            interaction_patterns.append("搜索历史 (Search History)")

        if platform == "mobile":
            interaction_patterns.append("手势导航 (Gesture Navigation)")
            interaction_patterns.append("滑动操作 (Swipe Actions)")

        if requirement_info["has_forms"]:
            interaction_patterns.append("逐步表单填写 (Progressive Form Filling)")
            interaction_patterns.append("实时表单验证 (Real-time Form Validation)")

        patterns["interaction_patterns"] = interaction_patterns

        # 配色方案建议
        color_palettes = []

        if requirement_info["has_shopping"]:
            color_palettes.append({
                "name": "电商活力配色",
                "primary": "#FF6B6B",
                "secondary": "#4ECDC4",
                "accent": "#FFD166",
                "background": "#F7F9FC",
                "text": "#2D3436"
            })
        elif requirement_info["has_social"]:
            color_palettes.append({
                "name": "社交友好配色",
                "primary": "#4285F4",
                "secondary": "#34A853",
                "accent": "#FBBC05",
                "background": "#FFFFFF",
                "text": "#202124"
            })
        else:
            color_palettes.append({
                "name": "专业中性配色",
                "primary": "#2E3A59",
                "secondary": "#7B8FA1",
                "accent": "#00A8FF",
                "background": "#F8F9FA",
                "text": "#212529"
            })

        patterns["color_palettes"] = color_palettes

        # 字体建议
        if platform == "mobile":
            patterns["typography_suggestions"] = [
                "主要字体: Roboto 或 San Francisco (iOS)",
                "正文大小: 16px 最小以确保可读性",
                "标题层级: H1: 24px, H2: 20px, H3: 18px",
                "行高: 正文1.5倍行距，标题1.2倍行距"
            ]
        else:
            patterns["typography_suggestions"] = [
                "主要字体: Inter 或 Roboto",
                "正文大小: 16px",
                "标题层级: H1: 32px, H2: 24px, H3: 20px",
                "行高: 正文1.6倍行距，标题1.3倍行距"
            ]

        # 无障碍建议
        patterns["accessibility_recommendations"] = [
            "确保颜色对比度至少4.5:1",
            "为所有交互元素提供键盘导航支持",
            "为图像提供替代文本",
            "为表单字段提供清晰的标签",
            "确保焦点状态可见"
        ]

        return patterns

    def _generate_report(self, requirement_info: Dict[str, Any], platform: str,
                        complexity: str, patterns: Dict[str, Any]) -> str:
        """生成完整UI设计建议报告"""
        report = f"""# UI设计模式生成报告

## 需求分析
- **需求描述**: {requirement_info['word_count']} 词
- **目标平台**: {platform}
- **复杂度级别**: {complexity}
- **关键功能**: {len(requirement_info['key_features'])} 个
- **检测到的需求**: {', '.join([k for k, v in requirement_info.items() if v is True and k.startswith('has_')])}

## 设计模式建议

### 1. 布局模式
{self._format_list(patterns['layout_patterns'])}

### 2. 组件选择
{self._format_list(patterns['component_patterns'])}

### 3. 交互模式
{self._format_list(patterns['interaction_patterns'])}

### 4. 配色方案
"""

        for palette in patterns['color_palettes']:
            report += f"- **{palette['name']}**:\n"
            report += f"  - 主色: `{palette['primary']}`\n"
            report += f"  - 辅色: `{palette['secondary']}`\n"
            report += f"  - 强调色: `{palette['accent']}`\n"
            report += f"  - 背景: `{palette['background']}`\n"
            report += f"  - 文字: `{palette['text']}`\n"

        report += f"""
### 5. 字体建议
{self._format_list(patterns['typography_suggestions'])}

### 6. 无障碍建议
{self._format_list(patterns['accessibility_recommendations'])}

## 平台特定建议
{self._get_platform_specific_advice(platform, complexity)}

## 结构化数据（JSON）
```json
{json.dumps({
    "requirement_analysis": requirement_info,
    "platform": platform,
    "complexity": complexity,
    "design_patterns": patterns
}, ensure_ascii=False, indent=2)}
```
"""

        return report

    def _format_list(self, items: List[str]) -> str:
        """格式化列表项"""
        if not items:
            return "暂无建议"
        return "\n".join([f"- {item}" for item in items])

    def _get_platform_specific_advice(self, platform: str, complexity: str) -> str:
        """获取平台特定建议"""
        advice = ""

        if platform == "mobile":
            advice = """
- **触控友好**: 确保按钮和交互元素至少44×44像素
- **手势支持**: 考虑添加常用手势操作（滑动、长按、双指缩放）
- **单手操作**: 将关键操作放置在屏幕底部区域
- **离线体验**: 考虑网络不稳定时的降级体验
"""
        elif platform == "web":
            advice = """
- **响应式设计**: 确保在桌面、平板、手机上都良好显示
- **浏览器兼容**: 测试主流浏览器兼容性
- **加载性能**: 优化首屏加载时间，考虑懒加载
- **SEO友好**: 确保关键内容能被搜索引擎抓取
"""
        elif platform == "desktop":
            advice = """
- **键盘导航**: 为所有功能提供键盘快捷键
- **多窗口支持**: 考虑多窗口同时操作的场景
- **系统集成**: 考虑与操作系统功能的集成
- **离线能力**: 提供完善的离线功能支持
"""

        if complexity == "dashboard":
            advice += """
- **数据可视化**: 选择合适的图表类型展示数据
- **实时更新**: 考虑数据实时刷新的机制
- **个性化**: 允许用户自定义仪表板布局
- **导出功能**: 提供数据导出和分享功能
"""

        return advice


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = UIPatternGeneratorTool()

    test_requirement = '''
    需要一个电商移动端App的商品列表页面，需要支持：
    1. 搜索商品功能
    2. 按价格、销量、评分筛选
    3. 商品卡片展示（图片、名称、价格、评分）
    4. 添加到购物车功能
    5. 用户评分和评论查看
    '''

    result = tool._run(
        ui_requirement=test_requirement,
        platform="mobile",
        complexity="medium"
    )

    print("测试结果:")
    print(result)
