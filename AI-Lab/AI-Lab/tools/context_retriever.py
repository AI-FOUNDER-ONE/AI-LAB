"""
context_retriever.py - 会话历史语义检索工具
============================================
从当前 session 的 meeting_logs 中检索与 query 最相关的历史消息，
支持关键词匹配 + 时间衰减；若已安装 sentence-transformers 则使用 embedding 相似度。
"""

import re
import math
from typing import Dict, Any, List, Optional

# 可选：embedding 相似度（安装 sentence_transformers 时启用）
_embedding_model = None

def _try_load_embedding_model():
    global _embedding_model
    if _embedding_model is False:
        return False
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return _embedding_model
    except Exception:
        _embedding_model = False
        return False


def _tokenize(text: str) -> List[str]:
    """中英文分词：字母数字与 CJK 连续序列为 token，英文转小写。"""
    if not text:
        return []
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return [t.lower() if t.isascii() else t for t in tokens]


def _tf_idf_scores(documents: List[List[str]], query_tokens: List[str]) -> List[float]:
    """基于词频与逆文档频率计算每条文档与 query 的相似度（无向量库）。"""
    if not query_tokens or not documents:
        return [0.0] * len(documents)
    N = len(documents)
    # 文档频率
    df: Dict[str, int] = {}
    for doc in documents:
        seen = set()
        for t in doc:
            if t not in seen:
                seen.add(t)
                df[t] = df.get(t, 0) + 1
    # idf(t)
    idf = {}
    for t in set(query_tokens):
        idf[t] = math.log((N + 1) / (df.get(t, 0) + 1)) + 1.0
    # 每个 doc 与 query 的得分：sum over t in query of tf(t,doc)*idf(t)，再按文档长度弱归一化
    scores = []
    for doc in documents:
        if not doc:
            scores.append(0.0)
            continue
        tf = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        raw = sum(tf.get(t, 0) * idf.get(t, 0) for t in query_tokens)
        norm = 1.0 + math.log(1 + len(doc))
        scores.append(raw / norm)
    return scores


def _embedding_scores(contents: List[str], query: str, model) -> List[float]:
    """使用 sentence_transformers 计算 query 与每条 content 的余弦相似度。"""
    if not contents or not query:
        return [0.0] * len(contents)
    from sentence_transformers import SentenceTransformer
    import numpy as np
    if not isinstance(model, SentenceTransformer):
        return [0.0] * len(contents)
    q_emb = model.encode([query], normalize_embeddings=True)
    doc_emb = model.encode(contents, normalize_embeddings=True)
    sim = np.dot(doc_emb, q_emb.T).flatten()
    return [float(s) for s in sim]


def context_retriever(
    query: str,
    session_store: Any = None,
    max_results: int = 5,
) -> Dict[str, Any]:
    """从 meeting_logs 中检索与 query 最相关的历史消息。

    Args:
        query: 检索问句或关键词。
        session_store: SessionStore 实例，用于读取当前 session 的 meeting_logs。
        max_results: 返回的最大条数，默认 5。

    Returns:
        dict，含 results: [{"speaker": str, "content": str, "timestamp": str, "relevance": float}]，
        以及 ok、message、backend（"embedding" | "keyword"）。
    """
    if not session_store:
        return {"ok": False, "message": "未提供 session_store", "results": []}
    session = session_store.get_current_session()
    if not session:
        return {"ok": False, "message": "无当前会话", "results": []}
    logs = session.get("meeting_logs") or []
    if not logs:
        return {"ok": True, "message": "暂无会议记录", "results": [], "backend": "keyword"}

    # 时间衰减：越新的消息权重越高（logs 按时间顺序，最后一条最新）
    n = len(logs)
    decay = 0.92
    time_weights = [decay ** (n - 1 - i) for i in range(n)]

    query = (query or "").strip()
    if not query:
        return {"ok": True, "results": [], "message": "query 为空", "backend": "keyword"}

    max_results = max(1, min(max_results, 50))

    model = _try_load_embedding_model()
    if model:
        contents = [m.get("content", "") or "" for m in logs]
        raw_scores = _embedding_scores(contents, query, model)
        backend = "embedding"
    else:
        doc_tokens = [_tokenize(m.get("content", "") or "") for m in logs]
        query_tokens = _tokenize(query)
        raw_scores = _tf_idf_scores(doc_tokens, query_tokens)
        backend = "keyword"

    # 结合时间衰减
    combined = [s * w for s, w in zip(raw_scores, time_weights)]
    # 归一化到 [0,1] 便于阅读（按当前批次最大值）
    max_s = max(combined) if combined else 0.0
    if max_s > 0:
        combined = [x / max_s for x in combined]
    # 按得分降序取索引
    indexed = [(i, combined[i]) for i in range(len(combined))]
    indexed.sort(key=lambda x: -x[1])
    top_indices = [idx for idx, _ in indexed[:max_results]]

    results = []
    for i in top_indices:
        m = logs[i]
        results.append({
            "speaker": m.get("role", ""),
            "content": m.get("content", ""),
            "timestamp": m.get("timestamp", ""),
            "relevance": round(combined[i], 4),
        })

    return {
        "ok": True,
        "results": results,
        "message": f"共 {len(logs)} 条记录，返回 {len(results)} 条",
        "backend": backend,
    }
