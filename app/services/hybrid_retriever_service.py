"""混合检索服务 — BM25 + 向量双路召回 + RRF 融合

将 BM25 关键词检索（精确匹配）与向量相似度检索（语义泛化）结合，
通过 Reciprocal Rank Fusion (RRF) 融合排序，提升检索召回质量。

用法:
    context, docs = hybrid_retriever_service.retrieve("CPU使用率过高如何排查")
"""

from typing import Dict, List, Tuple

from langchain_core.documents import Document
from loguru import logger

from app.config import config
from app.services.vector_store_manager import vector_store_manager
from app.services.bm25_index_service import bm25_index_service


class HybridRetrieverService:
    """混合检索服务 — BM25 + 向量双路召回 + RRF 融合

    核心流程:
    1. BM25 关键词检索 (bm25_top_k 候选)
    2. 向量相似度检索 (vector_top_k 候选)
    3. RRF 融合排序 → 取 final_top_k 结果
    """

    def __init__(self):
        logger.info("HybridRetrieverService 已创建")

    # ── 公开接口 ──────────────────────────────────────────────────

    def retrieve(self, query: str) -> List[Document]:
        """执行混合检索

        Args:
            query: 用户查询文本

        Returns:
            List[Document]: RRF 融合后的文档列表
        """
        if not config.hybrid_enabled:
            logger.debug("Hybrid 检索已禁用，使用纯向量检索")
            return self._vector_only_retrieve(query)

        try:
            # 1. BM25 关键词检索
            bm25_results = bm25_index_service.search(
                query, top_k=config.hybrid_bm25_top_k
            )

            # 2. 向量相似度检索
            vector_store = vector_store_manager.get_vector_store()
            vector_results: List[Tuple[Document, float]] = (
                vector_store.similarity_search_with_score(
                    query, k=config.hybrid_vector_top_k
                )
            )

            logger.debug(
                f"双路召回: BM25={len(bm25_results)}, Vector={len(vector_results)}"
            )

            # 3. RRF 融合
            merged_docs = self._rrf_merge(
                bm25_results,
                vector_results,
                top_k=config.hybrid_final_top_k,
                rrf_k=config.hybrid_rrf_k,
            )

            if not merged_docs:
                logger.info(f"混合检索未找到相关文档: '{query[:80]}'")
                return []

            logger.info(
                f"混合检索完成: '{query[:50]}...' → {len(merged_docs)} 个结果"
            )
            return merged_docs

        except Exception as e:
            logger.warning(f"混合检索失败，降级为纯向量检索: {e}")
            return self._vector_only_retrieve(query)

    # ── RRF 融合算法 ─────────────────────────────────────────────

    def _rrf_merge(
        self,
        bm25_results: List[Tuple[Document, float]],
        vector_results: List[Tuple[Document, float]],
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> List[Document]:
        """Reciprocal Rank Fusion (RRF) 融合排序

        RRF 公式: score(doc) = Σ 1/(k + rank_i(doc))
        其中 k 是平滑常数，rank_i 是文档在第 i 路检索中的排名(1-based)

        Args:
            bm25_results: BM25 检索结果 [(doc, score), ...]
            vector_results: 向量检索结果 [(doc, score), ...]
            top_k: 返回文档数
            rrf_k: RRF 平滑常数 (标准值 60)

        Returns:
            List[Document]: 融合后的文档列表
        """
        # doc_id -> {"doc": Document, "bm25_rank": int|None, "vector_rank": int|None}
        doc_map: Dict[str, dict] = {}

        # 注册 BM25 结果（rank 从 1 开始）
        for rank, (doc, _score) in enumerate(bm25_results, start=1):
            doc_id = self._get_doc_key(doc)
            if doc_id not in doc_map:
                doc_map[doc_id] = {}
            doc_map[doc_id]["doc"] = doc
            doc_map[doc_id]["bm25_rank"] = rank

        # 注册向量结果
        for rank, (doc, _score) in enumerate(vector_results, start=1):
            doc_id = self._get_doc_key(doc)
            if doc_id not in doc_map:
                doc_map[doc_id] = {}
            if "doc" not in doc_map[doc_id]:
                doc_map[doc_id]["doc"] = doc
            doc_map[doc_id]["vector_rank"] = rank

        # 计算 RRF 分数
        rrf_scores: Dict[str, float] = {}
        for doc_id, entry in doc_map.items():
            rrf = 0.0
            if entry.get("bm25_rank") is not None:
                rrf += 1.0 / (rrf_k + entry["bm25_rank"])
            if entry.get("vector_rank") is not None:
                rrf += 1.0 / (rrf_k + entry["vector_rank"])
            rrf_scores[doc_id] = rrf

        # 按 RRF 分数降序排序
        sorted_doc_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

        # 取 top_k
        result = []
        for doc_id in sorted_doc_ids[:top_k]:
            doc = doc_map[doc_id]["doc"]
            # 将 RRF 分数和双路 rank 存入 metadata 便于调试
            doc.metadata["_rrf_score"] = round(rrf_scores[doc_id], 6)
            doc.metadata["_bm25_rank"] = doc_map[doc_id].get("bm25_rank")
            doc.metadata["_vector_rank"] = doc_map[doc_id].get("vector_rank")
            result.append(doc)

        logger.debug(
            f"RRF 融合: {len(doc_map)} 候选 → {len(result)} 结果 "
            f"(BM25贡献: {len(bm25_results)}, Vector贡献: {len(vector_results)})"
        )

        return result

    # ── 内部辅助 ──────────────────────────────────────────────────

    @staticmethod
    def _get_doc_key(doc: Document) -> str:
        """获取文档的去重键

        使用 _file_name + page_content 前80字符作为 key，
        确保同一文件的不同 chunk 可以分别参与 RRF 融合。
        """
        file_name = doc.metadata.get("_file_name", "")
        content_prefix = doc.page_content[:80]
        return f"{file_name}::{hash(content_prefix)}"

    def _vector_only_retrieve(self, query: str) -> List[Document]:
        """纯向量检索（降级路径）"""
        try:
            vector_store = vector_store_manager.get_vector_store()
            retriever = vector_store.as_retriever(
                search_kwargs={"k": config.rag_top_k}
            )
            docs = retriever.invoke(query)

            if not docs:
                return []

            logger.info(f"向量降级检索: '{query[:50]}...' → {len(docs)} 个结果")
            return docs

        except Exception as e:
            logger.error(f"向量降级检索也失败: {e}")
            return []


# 全局单例
hybrid_retriever_service = HybridRetrieverService()
