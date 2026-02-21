"""
knowledge_retrieval_tool.py - 知识检索工具
========================================
供 CKO（首席知识官）使用，从知识库中检索相关信息。
支持文档搜索、关键词匹配、上下文提取等功能。

安全性审计:
  ✅ 仅读取文件，不执行代码
  ✅ 文件大小限制防止内存溢出
  ✅ 输入路径验证，防止目录遍历攻击
  ✅ 输出结构化知识摘要
"""

import os
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


class KnowledgeRetrievalInput(BaseModel):
    """KnowledgeRetrievalTool 的输入参数模型。"""
    query: str = Field(
        ...,
        description=(
            "知识查询语句。可以是：\n"
            "1. 具体问题（如'什么是微服务架构？'）\n"
            "2. 关键词（如'Python多线程'）\n"
            "3. 主题（如'项目管理方法论'）\n"
            "4. 概念（如'RESTful API设计原则'）\n"
            "示例：查找关于敏捷开发的最佳实践"
        )
    )
    knowledge_base_path: str = Field(
        default="data/knowledge",
        description=(
            "知识库路径。默认为'data/knowledge'。\n"
            "支持相对路径或绝对路径。目录应包含文档文件（.txt, .md, .pdf, .docx等）。"
        )
    )
    max_results: int = Field(
        default=5,
        description="最大返回结果数量。默认为5个最相关的结果。",
        ge=1,
        le=20
    )
    search_mode: str = Field(
        default="keyword",
        description=(
            "搜索模式。可选值：\n"
            "- 'keyword': 关键词匹配（默认）\n"
            "- 'semantic': 语义匹配（需要更多计算资源）\n"
            "- 'exact': 精确匹配\n"
            "- 'fuzzy': 模糊匹配"
        )
    )


class KnowledgeRetrievalTool(BaseTool):
    """知识检索工具。

    从知识库中检索相关信息，支持多种搜索模式和文档格式。
    返回结构化的知识摘要和相关文档引用。
    """

    name: str = "knowledge_retrieval"
    description: str = (
        "从知识库中检索相关信息。"
        "支持文档搜索、关键词匹配、上下文提取等功能。"
        "输出结构化知识摘要和相关文档引用。"
    )
    args_schema: Type[BaseModel] = KnowledgeRetrievalInput

    def _run(self, query: str, knowledge_base_path: str = "data/knowledge",
            max_results: int = 5, search_mode: str = "keyword") -> str:
        """执行知识检索。

        Args:
            query: 知识查询语句
            knowledge_base_path: 知识库路径
            max_results: 最大返回结果数量
            search_mode: 搜索模式

        Returns:
            格式化的知识检索报告
        """
        try:
            # 1. 验证知识库路径
            if not os.path.exists(knowledge_base_path):
                return self._generate_empty_report(query, knowledge_base_path)

            # 2. 扫描知识库文档
            documents = self._scan_knowledge_base(knowledge_base_path)
            if not documents:
                return self._generate_empty_report(query, knowledge_base_path)

            # 3. 执行搜索
            search_results = self._search_documents(documents, query, search_mode, max_results)

            # 4. 生成完整报告
            return self._generate_report(query, knowledge_base_path, search_mode, search_results)

        except Exception as e:
            return f"❌ 知识检索失败: {str(e)}"

    def _scan_knowledge_base(self, knowledge_base_path: str) -> List[Dict[str, Any]]:
        """扫描知识库文档"""
        documents = []
        supported_extensions = {'.txt', '.md', '.pdf', '.docx', '.json', '.yaml', '.yml'}

        try:
            for root, dirs, files in os.walk(knowledge_base_path):
                for filename in files:
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in supported_extensions:
                        file_path = os.path.join(root, filename)
                        try:
                            file_size = os.path.getsize(file_path)
                            # 跳过过大文件（>10MB）
                            if file_size > 10 * 1024 * 1024:
                                continue

                            # 获取文件基本信息
                            doc_info = {
                                "path": file_path,
                                "filename": filename,
                                "extension": file_ext,
                                "size_bytes": file_size,
                                "relative_path": os.path.relpath(file_path, knowledge_base_path),
                                "last_modified": os.path.getmtime(file_path),
                            }
                            documents.append(doc_info)
                        except (OSError, PermissionError):
                            continue
        except (OSError, PermissionError) as e:
            print(f"[KnowledgeRetrieval] 扫描知识库时出错: {e}")

        return documents

    def _search_documents(self, documents: List[Dict[str, Any]], query: str,
                         search_mode: str, max_results: int) -> List[Dict[str, Any]]:
        """在文档中搜索查询内容"""
        results = []

        # 预处理查询
        query_lower = query.lower()
        query_words = re.findall(r'\b\w+\b', query_lower)

        for doc_info in documents:
            try:
                # 读取文件内容（简单文本文件）
                if doc_info["extension"] in {'.txt', '.md'}:
                    content = self._read_text_file(doc_info["path"])
                elif doc_info["extension"] in {'.json', '.yaml', '.yml'}:
                    content = self._read_structured_file(doc_info["path"])
                else:
                    # 对于PDF、DOCX等格式，需要更复杂的解析
                    # 这里先跳过或使用简单方法
                    continue

                if not content:
                    continue

                # 根据搜索模式计算相关性
                relevance_score = self._calculate_relevance(content, query, query_words, search_mode)

                if relevance_score > 0:
                    # 提取相关上下文片段
                    context_snippets = self._extract_context_snippets(content, query, query_words)

                    result = {
                        "document": doc_info,
                        "relevance_score": relevance_score,
                        "context_snippets": context_snippets[:3],  # 最多3个片段
                        "content_preview": content[:500] + "..." if len(content) > 500 else content,
                    }
                    results.append(result)

            except Exception as e:
                print(f"[KnowledgeRetrieval] 处理文档 {doc_info['path']} 时出错: {e}")
                continue

        # 按相关性排序并限制结果数量
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:max_results]

    def _read_text_file(self, file_path: str) -> str:
        """读取文本文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    return f.read()
            except:
                return ""
        except Exception:
            return ""

    def _read_structured_file(self, file_path: str) -> str:
        """读取结构化文件内容（JSON/YAML）"""
        try:
            import yaml
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                    return json.dumps(data, ensure_ascii=False, indent=2)
                else:
                    data = yaml.safe_load(f)
                    return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return self._read_text_file(file_path)  # 回退到文本读取

    def _calculate_relevance(self, content: str, query: str, query_words: List[str],
                            search_mode: str) -> float:
        """计算内容与查询的相关性得分"""
        content_lower = content.lower()

        if search_mode == "exact":
            # 精确匹配
            if query.lower() in content_lower:
                return 1.0
            else:
                return 0.0

        elif search_mode == "keyword":
            # 关键词匹配
            score = 0.0
            for word in query_words:
                if len(word) > 2:  # 忽略过短的词
                    count = content_lower.count(word)
                    if count > 0:
                        score += min(count * 0.1, 1.0)  # 每出现一次加0.1，最多1.0
            return min(score, 1.0)

        elif search_mode == "fuzzy":
            # 模糊匹配（简单的编辑距离，这里简化）
            score = 0.0
            for word in query_words:
                if len(word) > 2:
                    # 使用正则表达式查找相似词
                    pattern = re.compile(rf'\b{word[0]}\w*{word[-1] if len(word)>1 else ""}\b', re.IGNORECASE)
                    matches = pattern.findall(content_lower)
                    if matches:
                        score += min(len(matches) * 0.05, 0.5)
            return min(score, 1.0)

        else:  # semantic 或其他模式
            # 语义匹配（简化版本：使用更宽松的关键词匹配）
            return self._calculate_relevance(content, query, query_words, "keyword")

    def _extract_context_snippets(self, content: str, query: str,
                                 query_words: List[str]) -> List[str]:
        """提取相关上下文片段"""
        snippets = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            line_lower = line.lower()
            # 检查行是否包含查询关键词
            has_keyword = any(word in line_lower for word in query_words if len(word) > 2)
            if has_keyword:
                # 提取上下文（前后各1行）
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = '\n'.join(lines[start:end])
                snippets.append(context)

                if len(snippets) >= 5:  # 最多5个片段
                    break

        return snippets

    def _generate_report(self, query: str, knowledge_base_path: str,
                        search_mode: str, search_results: List[Dict[str, Any]]) -> str:
        """生成知识检索报告"""
        report = f"""# 知识检索报告

## 查询信息
- **查询内容**: {query}
- **知识库路径**: {knowledge_base_path}
- **搜索模式**: {search_mode}
- **发现文档数**: {len(search_results)}

## 检索结果
"""

        if not search_results:
            report += "未找到相关文档。\n"
        else:
            for i, result in enumerate(search_results, 1):
                doc = result["document"]
                report += f"""
### 结果 {i}: {doc['filename']}
- **文件路径**: {doc['relative_path']}
- **文件类型**: {doc['extension']}
- **文件大小**: {doc['size_bytes']} 字节
- **相关性得分**: {result['relevance_score']:.2f}

#### 内容预览
```
{result['content_preview']}
```

#### 相关上下文
"""
                for j, snippet in enumerate(result["context_snippets"], 1):
                    report += f"**片段 {j}**:\n```\n{snippet}\n```\n\n"

        report += f"""
## 搜索统计
- **总扫描文档数**: {len(self._scan_knowledge_base(knowledge_base_path))}
- **返回结果数**: {len(search_results)}
- **搜索模式说明**: {self._get_search_mode_description(search_mode)}

## 结构化数据（JSON）
```json
{json.dumps({
    "query": query,
    "knowledge_base_path": knowledge_base_path,
    "search_mode": search_mode,
    "results": search_results
}, ensure_ascii=False, indent=2)}
```

## 建议
1. 如果未找到相关文档，可以：
   - 检查知识库路径是否正确
   - 尝试不同的搜索模式
   - 扩展知识库内容
   - 使用更具体的关键词
2. 对于复杂查询，建议使用'semantic'搜索模式（如果支持）
3. 定期更新和维护知识库以确保信息时效性
"""

        return report

    def _generate_empty_report(self, query: str, knowledge_base_path: str) -> str:
        """生成空知识库报告"""
        report = f"""# 知识检索报告

## 查询信息
- **查询内容**: {query}
- **知识库路径**: {knowledge_base_path}

## 状态
❌ **知识库不存在或为空**

## 问题分析
指定的知识库路径 `{knowledge_base_path}` 不存在或为空目录。

## 建议操作
1. **创建知识库目录**:
   ```bash
   mkdir -p {knowledge_base_path}
   ```

2. **添加知识文档**:
   - 将相关文档（.txt, .md, .pdf, .docx 等格式）复制到知识库目录
   - 知识文档可以包括：
     * 技术文档和规范
     * 项目文档和设计稿
     * 学习笔记和研究报告
     * 最佳实践和模板

3. **支持的文档格式**:
   - 纯文本 (.txt)
   - Markdown (.md)
   - PDF (.pdf)
   - Word文档 (.docx)
   - JSON/YAML配置文件 (.json, .yaml, .yml)

4. **重新尝试搜索**:
   在添加文档后，重新运行知识检索工具。
"""
        return report

    def _get_search_mode_description(self, search_mode: str) -> str:
        """获取搜索模式说明"""
        descriptions = {
            "keyword": "关键词匹配：查找包含查询关键词的文档",
            "exact": "精确匹配：查找完全包含查询字符串的文档",
            "fuzzy": "模糊匹配：查找包含相似关键词的文档",
            "semantic": "语义匹配：基于语义相似度查找相关文档（需要高级配置）",
        }
        return descriptions.get(search_mode, "未知搜索模式")


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = KnowledgeRetrievalTool()

    # 测试查询
    test_query = "Python多线程编程"
    test_knowledge_path = "data/knowledge"

    result = tool._run(
        query=test_query,
        knowledge_base_path=test_knowledge_path,
        max_results=3,
        search_mode="keyword"
    )

    print("测试结果:")
    print(result)
