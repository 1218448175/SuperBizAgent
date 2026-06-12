"""BM25 索引服务 — 基于 Milvus 文档构建 BM25 稀疏检索索引

为混合检索提供关键词精确匹配能力，弥补纯向量检索的盲区。
"""

from typing import List, Tuple

import numpy as np
from langchain_core.documents import Document
from loguru import logger
from rank_bm25 import BM25Okapi

from app.core.milvus_client import milvus_manager
from app.config import config


# 安全限制：单次从 Milvus 加载的最大文档数
MAX_DOCS_LOAD = 10000


class BM25IndexService:
    """BM25 稀疏检索索引服务

    从 Milvus biz collection 加载所有文档，使用 jieba 中文分词后构建 BM25Okapi 索引。
    遵循 lazy-initialization 模式，首次 search() 时自动构建。

    用法:
        docs = bm25_index_service.search("CPU使用率过高", top_k=10)
    """

    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._documents: List[Document] = []
        self._tokenized_corpus: List[List[str]] = []
        self._initialized: bool = False
        self._doc_count_at_index: int = 0  # 建索引时的文档数，用于检测变更
        logger.info("BM25IndexService 已创建（延迟初始化）")

    # ── 公开接口 ──────────────────────────────────────────────────

    def refresh(self) -> int:
        """强制重建 BM25 索引

        Returns:
            int: 索引中的文档数量
        """
        self._initialized = False
        self._bm25 = None
        self._documents = []
        self._tokenized_corpus = []
        self._ensure_initialized()
        return len(self._documents)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Document, float]]:
        """BM25 检索

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            List[Tuple[Document, float]]: (文档, BM25分数) 列表，按分数降序
        """
        self._ensure_initialized()

        if self._bm25 is None or not self._documents:
            logger.debug("BM25 索引为空，返回空结果")
            return []

        import jieba
        query_tokens = jieba.lcut(query)

        # 过滤空 token
        query_tokens = [t.strip() for t in query_tokens if t.strip()]
        if not query_tokens:
            return []

        # BM25 打分
        scores = self._bm25.get_scores(query_tokens)

        # 获取 top_k 索引
        actual_k = min(top_k, len(scores))
        if actual_k == 0:
            return []

        # 对于小规模语料直接用 argsort（比 argpartition 更精确且规模小时更快）
        top_indices = np.argsort(scores)[::-1][:actual_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有正分数的文档
                results.append((self._documents[idx], float(scores[idx])))

        logger.debug(f"BM25 检索: query='{query[:50]}', 返回 {len(results)}/{top_k} 个结果")
        return results

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """公开的分词方法（供外部使用）"""
        import jieba
        tokens = jieba.lcut(text)
        return [t.strip() for t in tokens if t.strip()]

    # ── 内部实现 ──────────────────────────────────────────────────

    def _ensure_initialized(self):
        """确保索引已构建（懒加载，幂等）"""
        if self._initialized and not self._stale():
            return

        if self._initialized:
            logger.info("检测到文档变更，正在重建 BM25 索引...")

        self._load_and_build()

    def _stale(self) -> bool:
        """检查索引是否过期（Milvus 中文档数有变化）"""
        try:
            collection = milvus_manager.get_collection()
            # 使用 num_entities 获取文档数
            current_count = collection.num_entities
            return current_count != self._doc_count_at_index
        except Exception:
            return False  # 无法检测时不认为过期

    def _load_and_build(self):
        """从 Milvus 加载文档并构建 BM25 索引"""
        docs = self._load_all_documents()
        if not docs:
            logger.warning("Milvus 中没有文档，BM25 索引保持为空")
            self._bm25 = None
            self._documents = []
            self._tokenized_corpus = []
            self._initialized = True
            self._doc_count_at_index = 0
            return

        self._documents = docs
        self._build_index(docs)
        self._initialized = True
        self._doc_count_at_index = len(docs)
        logger.info(f"BM25 索引构建完成，共 {len(docs)} 个文档")

    def _load_all_documents(self) -> List[Document]:
        """从 Milvus biz collection 加载所有文档"""
        try:
            collection = milvus_manager.get_collection()

            # 查询所有文档的 id, content, metadata
            results = collection.query(
                expr="",
                output_fields=["id", "content", "metadata"],
                limit=MAX_DOCS_LOAD,
            )

            if not results:
                logger.info("Milvus collection 为空")
                return []

            documents = []
            for row in results:
                metadata = row.get("metadata", {}) or {}
                # 把 Milvus id 存入 metadata 供 RRF 去重
                metadata["_doc_id"] = row.get("id", "")
                doc = Document(
                    page_content=row.get("content", ""),
                    metadata=metadata,
                )
                documents.append(doc)

            logger.info(f"从 Milvus 加载了 {len(documents)} 个文档")
            return documents

        except Exception as e:
            logger.error(f"从 Milvus 加载文档失败: {e}")
            return []

    def _build_index(self, documents: List[Document]):
        """用 jieba 分词后构建 BM25Okapi 索引"""
        import jieba

        # 为中文分词添加技术术语
        # 不需要额外词典，jieba 对技术文档有较好的默认分词效果

        self._tokenized_corpus = []
        for doc in documents:
            tokens = jieba.lcut(doc.page_content)
            tokens = [t.strip() for t in tokens if t.strip()]
            self._tokenized_corpus.append(tokens)

        self._bm25 = BM25Okapi(self._tokenized_corpus)
        logger.info(
            f"BM25Okapi 索引构建完成: {len(documents)} 文档, "
            f"平均每文档 {sum(len(t) for t in self._tokenized_corpus) // max(len(self._tokenized_corpus), 1)} token"
        )


# 全局单例
bm25_index_service = BM25IndexService()
