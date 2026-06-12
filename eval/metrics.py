"""检索评估指标 — Recall@K, MRR, NDCG@K

所有指标都基于二元相关性（relevant / not relevant）。
"""

import math
from typing import Dict, List, Set


def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Recall@K: 检索到的相关文档数 / 所有相关文档数

    Args:
        retrieved: 检索结果 doc_id 列表 (按排名顺序)
        relevant: 相关文档 doc_id 集合
        k: 截断位置

    Returns:
        float: 0.0 ~ 1.0
    """
    if not relevant:
        return 0.0
    retrieved_k = set(retrieved[:k])
    return len(retrieved_k & relevant) / len(relevant)


def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Precision@K: 检索到的相关文档数 / K

    Args:
        retrieved: 检索结果 doc_id 列表
        relevant: 相关文档 doc_id 集合
        k: 截断位置

    Returns:
        float: 0.0 ~ 1.0
    """
    if k == 0:
        return 0.0
    retrieved_k = set(retrieved[:k])
    return len(retrieved_k & relevant) / k


def mean_reciprocal_rank(
    retrieved_list: List[List[str]],
    relevant_list: List[Set[str]],
) -> float:
    """MRR: 首个相关文档排名的倒数均值

    Args:
        retrieved_list: 每个查询的检索结果列表
        relevant_list: 每个查询的相关文档集合

    Returns:
        float: MRR 值
    """
    if not retrieved_list:
        return 0.0

    rr_sum = 0.0
    for retrieved, relevant in zip(retrieved_list, relevant_list):
        found = False
        for i, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                rr_sum += 1.0 / i
                found = True
                break
        # 如果没找到相关文档，贡献 0

    return rr_sum / len(retrieved_list)


def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """NDCG@K: 归一化折损累计增益 (二元相关性)

    DCG_k = Σ_{i=1..k} rel_i / log2(i+1)
    IDCG_k = DCG of ideal ranking (all relevant docs at top)

    Args:
        retrieved: 检索结果 doc_id 列表
        relevant: 相关文档 doc_id 集合
        k: 截断位置

    Returns:
        float: 0.0 ~ 1.0
    """
    if not relevant or k == 0:
        return 0.0

    # DCG
    dcg = 0.0
    for i, doc_id in enumerate(retrieved[:k], 1):
        if doc_id in relevant:
            dcg += 1.0 / math.log2(i + 1)

    # IDCG (理想情况：所有相关文档都排在最前面)
    ideal_count = min(k, len(relevant))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))

    return dcg / idcg if idcg > 0 else 0.0


def evaluate_all(
    retrieved_by_query: Dict[str, List[str]],
    ground_truth: Dict[str, Set[str]],
    k_values: List[int] = None,
) -> Dict:
    """计算所有查询的聚合指标

    Args:
        retrieved_by_query: {query_id: [doc_id, ...]}
        ground_truth: {query_id: {relevant_doc_id, ...}}
        k_values: K 值列表，默认 [3, 5, 10]

    Returns:
        dict: {
            "recall@{k}": {"mean": float, "per_query": {qid: float}},
            "ndcg@{k}": {"mean": float, "per_query": {qid: float}},
            "mrr": float,
        }
    """
    if k_values is None:
        k_values = [3, 5, 10]

    results = {}

    # Recall@K
    for k in k_values:
        scores = {}
        for qid, retrieved in retrieved_by_query.items():
            scores[qid] = recall_at_k(retrieved, ground_truth.get(qid, set()), k)
        results[f"recall@{k}"] = {
            "mean": sum(scores.values()) / len(scores) if scores else 0.0,
            "per_query": scores,
        }

    # NDCG@K
    for k in k_values:
        scores = {}
        for qid, retrieved in retrieved_by_query.items():
            scores[qid] = ndcg_at_k(retrieved, ground_truth.get(qid, set()), k)
        results[f"ndcg@{k}"] = {
            "mean": sum(scores.values()) / len(scores) if scores else 0.0,
            "per_query": scores,
        }

    # MRR
    r_list = list(retrieved_by_query.values())
    g_list = [ground_truth.get(qid, set()) for qid in retrieved_by_query]
    results["mrr"] = mean_reciprocal_rank(r_list, g_list)

    return results
