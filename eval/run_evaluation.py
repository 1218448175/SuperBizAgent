#!/usr/bin/env python
"""运行检索评估 — 对比 Vector / BM25 / Hybrid (RRF) 三路检索质量

用法:
    python eval/run_evaluation.py          # 运行评估并输出报告
    python eval/run_evaluation.py --json   # 输出 JSON 结果

前提:
    - Milvus 已启动且已连接
    - biz collection 中有已索引的文档
"""

import json
import sys
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from app.core.milvus_client import milvus_manager
from app.services.vector_store_manager import vector_store_manager
from app.services.bm25_index_service import bm25_index_service
from eval.evaluator import RetrievalEvaluator


def main():
    json_only = "--json" in sys.argv

    # ── 1. 连接 Milvus ──
    if not json_only:
        print("=" * 60)
        print("  检索质量评估：Vector vs BM25 vs Hybrid (RRF)")
        print("=" * 60)
        print()
        print("[1/5] 连接 Milvus...")

    milvus_manager.connect()
    vector_store_manager._ensure_initialized()

    if not json_only:
        print("       Milvus 已连接")

    # ── 2. 构建 BM25 索引 ──
    if not json_only:
        print("[2/5] 构建 BM25 索引...")

    doc_count = bm25_index_service.refresh()

    if not json_only:
        print(f"       BM25 索引就绪: {doc_count} 个文档")

    if doc_count == 0:
        print("错误: Milvus collection 为空，请先索引文档！")
        print("提示: 启动 FastAPI 后调用 POST /api/skills/index-all")
        sys.exit(1)

    # ── 3. 构建 Ground Truth ──
    if not json_only:
        print("[3/5] 构建 Ground Truth...")

    evaluator = RetrievalEvaluator()

    if not json_only:
        gt_total = sum(len(v) for v in evaluator.ground_truth.values())
        print(f"       Ground Truth 就绪: {len(evaluator.ground_truth)} 个查询, {gt_total} 个相关标注")

    # ── 4. 运行评估 ──
    k_values = [3, 5, 10]
    if not json_only:
        print(f"[4/5] 运行评估 (K={k_values})...")
        print()

    results = evaluator.run_comparison(k_values=k_values)

    # ── 5. 输出报告 ──
    if not json_only:
        print("[5/5] 生成报告...")
        print()

    if json_only:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        report = evaluator.print_report(results, k_values=k_values)
        print(report)

        # 保存报告
        output_dir = Path("eval/results")
        output_dir.mkdir(exist_ok=True)

        report_path = output_dir / "report.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"报告已保存至: {report_path}")

        json_path = output_dir / "results.json"
        json_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON 结果已保存至: {json_path}")
        print()

        # ── 总结 ──
        vec_recall5 = results["vector_only"].get("recall@5", {}).get("mean", 0)
        hyb_recall5 = results["hybrid_rrf"].get("recall@5", {}).get("mean", 0)

        print("=" * 60)
        if hyb_recall5 > vec_recall5:
            lift = (hyb_recall5 - vec_recall5) / max(vec_recall5, 0.001) * 100
            print(f"  ✅ 混合检索 Recall@5 提升: {vec_recall5:.4f} → {hyb_recall5:.4f} (+{lift:.1f}%)")
        elif hyb_recall5 == vec_recall5:
            print(f"  ➡️  混合检索 Recall@5 持平: {hyb_recall5:.4f}")
        else:
            drop = (vec_recall5 - hyb_recall5) / max(vec_recall5, 0.001) * 100
            print(f"  ⚠️  混合检索 Recall@5 下降: {vec_recall5:.4f} → {hyb_recall5:.4f} (-{drop:.1f}%)")

        vec_mrr = results["vector_only"].get("mrr", 0)
        hyb_mrr = results["hybrid_rrf"].get("mrr", 0)
        print(f"      MRR: {vec_mrr:.4f} → {hyb_mrr:.4f}")
        print("=" * 60)


if __name__ == "__main__":
    main()
