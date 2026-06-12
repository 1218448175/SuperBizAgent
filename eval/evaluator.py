"""检索评估器 — 对比 Vector-only / BM25-only / Hybrid (RRF) 三路检索"""

from typing import Dict, List, Set, Tuple

from langchain_core.documents import Document
from loguru import logger

from app.config import config
from app.services.vector_store_manager import vector_store_manager
from app.services.bm25_index_service import bm25_index_service
from app.services.hybrid_retriever_service import hybrid_retriever_service
from eval.queries import TEST_QUERIES
from eval.ground_truth import build_ground_truth, build_ground_truth_from_milvus
from eval.metrics import evaluate_all


class RetrievalEvaluator:
    """三路检索对比评估器

    对每个测试查询，分别用 Vector / BM25 / Hybrid 三种方法检索，
    然后与 ground truth 对比计算 Recall@K, MRR, NDCG@K。

    用法:
        evaluator = RetrievalEvaluator()
        results = evaluator.run_comparison()
        evaluator.print_report(results)
    """

    METHODS = [
        ("vector_only", "纯向量检索 (L2)"),
        ("bm25_only", "纯 BM25 检索"),
        ("hybrid_rrf", "混合检索 (BM25+Vector+RRF)"),
    ]

    def __init__(self, ground_truth: Dict[str, Set[str]] | None = None):
        """
        Args:
            ground_truth: {query_id: {relevant_doc_id, ...}}
                          如果为 None，自动从 Milvus 构建
        """
        if ground_truth is None:
            skill_map = build_ground_truth_from_milvus()
            self.ground_truth = build_ground_truth(skill_map)
        else:
            self.ground_truth = ground_truth

    # ── 检索方法 ──────────────────────────────────────────────────

    def _retrieve_vector_only(self, query: str, k: int) -> Tuple[List[str], List[Document]]:
        """纯向量检索"""
        vector_store = vector_store_manager.get_vector_store()
        docs = vector_store.similarity_search(query, k=k)
        doc_ids = [self._get_doc_id(doc) for doc in docs]
        return doc_ids, docs

    def _retrieve_bm25_only(self, query: str, k: int) -> Tuple[List[str], List[Document]]:
        """纯 BM25 检索"""
        results = bm25_index_service.search(query, top_k=k)
        doc_ids = [self._get_doc_id(doc) for doc, _ in results]
        docs = [doc for doc, _ in results]
        return doc_ids, docs

    def _retrieve_hybrid(self, query: str, k: int) -> Tuple[List[str], List[Document]]:
        """混合检索 (RRF)"""
        # 临时调整 top_k 以获取 k 个结果
        _orig_final = config.hybrid_final_top_k
        config.hybrid_final_top_k = k
        try:
            docs = hybrid_retriever_service.retrieve(query)
        finally:
            config.hybrid_final_top_k = _orig_final
        doc_ids = [self._get_doc_id(doc) for doc in docs]
        return doc_ids, docs

    # ── 评估 ──────────────────────────────────────────────────────

    def evaluate_method(self, method: str, k_values: List[int]) -> Dict:
        """对一种检索方法运行全部测试查询

        Args:
            method: "vector_only" | "bm25_only" | "hybrid_rrf"
            k_values: K 值列表

        Returns:
            dict: metrics 结果
        """
        retrieve_fn = {
            "vector_only": self._retrieve_vector_only,
            "bm25_only": self._retrieve_bm25_only,
            "hybrid_rrf": self._retrieve_hybrid,
        }[method]

        max_k = max(k_values)
        retrieved_by_query: Dict[str, List[str]] = {}

        for q in TEST_QUERIES:
            try:
                doc_ids, _ = retrieve_fn(q["query"], max_k)
                # 去重：每个 _file_name 只保留首次出现
                seen = set()
                deduped_ids = []
                for did in doc_ids:
                    if did not in seen:
                        seen.add(did)
                        deduped_ids.append(did)
                retrieved_by_query[q["id"]] = deduped_ids
            except Exception as e:
                logger.warning(f"{method} 检索失败 [{q['id']}]: {e}")
                retrieved_by_query[q["id"]] = []

        return evaluate_all(retrieved_by_query, self.ground_truth, k_values)

    def run_comparison(self, k_values: List[int] = None) -> Dict:
        """运行三路完整对比

        Args:
            k_values: K 值列表，默认 [3, 5, 10]

        Returns:
            dict: {method_name: metrics_result, ...}
        """
        if k_values is None:
            k_values = [3, 5, 10]

        results = {}
        for method_key, method_label in self.METHODS:
            logger.info(f"评估 {method_label}...")
            try:
                results[method_key] = self.evaluate_method(method_key, k_values)
                logger.info(f"  {method_label} 完成")
            except Exception as e:
                logger.error(f"  {method_label} 失败: {e}")
                results[method_key] = {"error": str(e)}

        return results

    # ── 报告 ──────────────────────────────────────────────────────

    def print_report(self, comparison: Dict, k_values: List[int] = None) -> str:
        """格式化对比报告为 Markdown 表格

        Args:
            comparison: run_comparison() 返回的结果
            k_values: K 值列表

        Returns:
            str: Markdown 格式报告
        """
        if k_values is None:
            k_values = [3, 5, 10]

        lines = []
        lines.append("# 检索质量评估报告：Vector vs BM25 vs Hybrid (RRF)")
        lines.append("")
        lines.append(f"**测试查询数**: {len(TEST_QUERIES)} (5 个 Skill 领域各 3 条)")
        lines.append(f"**Ground Truth**: 基于文档 skill 标签自动标注")
        lines.append("")

        # ── 汇总表 ──
        lines.append("## 汇总对比")
        lines.append("")

        method_labels = {
            "vector_only": "纯向量 (L2)",
            "bm25_only": "纯 BM25",
            "hybrid_rrf": "混合 (RRF)",
        }

        # Recall@K 表
        for k in k_values:
            lines.append(f"### Recall@{k}")
            lines.append("")
            lines.append("| 方法 | Mean Recall |")
            lines.append("|------|-------------|")
            for method_key, method_label in self.METHODS:
                if method_key in comparison and "error" not in comparison[method_key]:
                    score = comparison[method_key].get(f"recall@{k}", {}).get("mean", 0)
                    lines.append(f"| {method_label} | {score:.4f} |")
                else:
                    lines.append(f"| {method_label} | N/A |")
            lines.append("")

        # MRR 表
        lines.append("### MRR (Mean Reciprocal Rank)")
        lines.append("")
        lines.append("| 方法 | MRR |")
        lines.append("|------|-----|")
        for method_key, method_label in self.METHODS:
            if method_key in comparison and "error" not in comparison[method_key]:
                mrr = comparison[method_key].get("mrr", 0)
                lines.append(f"| {method_label} | {mrr:.4f} |")
            else:
                lines.append(f"| {method_label} | N/A |")
        lines.append("")

        # NDCG@K 表
        for k in k_values:
            lines.append(f"### NDCG@{k}")
            lines.append("")
            lines.append("| 方法 | Mean NDCG |")
            lines.append("|------|-----------|")
            for method_key, method_label in self.METHODS:
                if method_key in comparison and "error" not in comparison[method_key]:
                    score = comparison[method_key].get(f"ndcg@{k}", {}).get("mean", 0)
                    lines.append(f"| {method_label} | {score:.4f} |")
                else:
                    lines.append(f"| {method_label} | N/A |")
            lines.append("")

        # ── 提升分析 ──
        lines.append("## 提升分析 (Hybrid vs 纯向量)")
        lines.append("")
        lines.append("| 指标 | 纯向量 | 混合 | 提升 |")
        lines.append("|------|--------|------|------|")
        for k in k_values:
            vec_recall = comparison.get("vector_only", {}).get(f"recall@{k}", {}).get("mean", 0)
            hyb_recall = comparison.get("hybrid_rrf", {}).get(f"recall@{k}", {}).get("mean", 0)
            if vec_recall > 0:
                lift = (hyb_recall - vec_recall) / vec_recall * 100
                lines.append(f"| Recall@{k} | {vec_recall:.4f} | {hyb_recall:.4f} | {lift:+.1f}% |")
            else:
                lines.append(f"| Recall@{k} | {vec_recall:.4f} | {hyb_recall:.4f} | N/A |")

        for k in k_values:
            vec_ndcg = comparison.get("vector_only", {}).get(f"ndcg@{k}", {}).get("mean", 0)
            hyb_ndcg = comparison.get("hybrid_rrf", {}).get(f"ndcg@{k}", {}).get("mean", 0)
            if vec_ndcg > 0:
                lift = (hyb_ndcg - vec_ndcg) / vec_ndcg * 100
                lines.append(f"| NDCG@{k} | {vec_ndcg:.4f} | {hyb_ndcg:.4f} | {lift:+.1f}% |")
            else:
                lines.append(f"| NDCG@{k} | {vec_ndcg:.4f} | {hyb_ndcg:.4f} | N/A |")

        vec_mrr = comparison.get("vector_only", {}).get("mrr", 0)
        hyb_mrr = comparison.get("hybrid_rrf", {}).get("mrr", 0)
        if vec_mrr > 0:
            lift = (hyb_mrr - vec_mrr) / vec_mrr * 100
            lines.append(f"| MRR | {vec_mrr:.4f} | {hyb_mrr:.4f} | {lift:+.1f}% |")
        else:
            lines.append(f"| MRR | {vec_mrr:.4f} | {hyb_mrr:.4f} | N/A |")

        lines.append("")

        # ── 逐查询详情 ──
        lines.append("## 逐查询 Recall@5 详情")
        lines.append("")
        lines.append("| 查询ID | 查询 | 纯向量 | 纯BM25 | 混合 |")
        lines.append("|--------|------|--------|--------|------|")
        for q in TEST_QUERIES:
            qid = q["id"]
            query_short = q["query"][:30] + "..." if len(q["query"]) > 30 else q["query"]
            vec_r = comparison.get("vector_only", {}).get("recall@5", {}).get("per_query", {}).get(qid, 0)
            bm25_r = comparison.get("bm25_only", {}).get("recall@5", {}).get("per_query", {}).get(qid, 0)
            hyb_r = comparison.get("hybrid_rrf", {}).get("recall@5", {}).get("per_query", {}).get(qid, 0)
            lines.append(f"| {qid} | {query_short} | {vec_r:.4f} | {bm25_r:.4f} | {hyb_r:.4f} |")

        report = "\n".join(lines)
        return report

    # ── 辅助 ──────────────────────────────────────────────────────

    @staticmethod
    def _get_doc_id(doc: Document) -> str:
        """从 Document 提取文档标识

        使用 _file_name 作为统一键（BM25 和 Vector 两路结果均包含此字段）。
        """
        file_name = doc.metadata.get("_file_name", "")
        if file_name:
            return file_name
        # Fallback
        return str(hash(doc.page_content))
