"""Ground Truth 构建 — 基于文档 _file_name 自动生成相关性标注

策略: 每个查询明确属于一个 skill 领域，该 skill 的知识文档（按文件名）视为 relevant。
使用 _file_name 作为文档键，因为它是 BM25 和 Vector 两路结果中唯一共有的标识字段。

Key: _file_name (如 "cpu_high_usage.md")
"""

import json
from pathlib import Path
from typing import Dict, Set


# Skill → Relevant file names 的硬编码映射
# 每个 skill 只有一个核心知识文档，高度领域内聚
SKILL_FILE_MAP = {
    "cpu_troubleshoot": {"cpu_high_usage.md"},
    "memory_troubleshoot": {"memory_high_usage.md"},
    "disk_troubleshoot": {"disk_high_usage.md"},
    "service_unavailable": {"service_unavailable.md"},
    "slow_response": {"slow_response.md"},
}


def build_ground_truth_from_milvus() -> Dict[str, Set[str]]:
    """从 Milvus metadata 加载 skill → file_names 映射

    Returns:
        Dict[str, Set[str]]: {skill_name: {file_name_1, file_name_2, ...}}
    """
    from app.core.milvus_client import milvus_manager

    skill_to_files: Dict[str, Set[str]] = {}

    try:
        collection = milvus_manager.get_collection()
        results = collection.query(
            expr="",
            output_fields=["metadata"],
            limit=10000,
        )

        for row in results:
            metadata = row.get("metadata", {}) or {}
            skill = metadata.get("skill", "")
            file_name = metadata.get("_file_name", "")

            if skill and file_name:
                if skill not in skill_to_files:
                    skill_to_files[skill] = set()
                skill_to_files[skill].add(file_name)

    except Exception as e:
        print(f"警告: 从 Milvus 加载 ground truth 失败: {e}")
        # 降级使用硬编码映射
        return dict(SKILL_FILE_MAP)

    # 如果 Milvus 有数据就用 Milvus 的，否则降级
    if not skill_to_files:
        print("Milvus 中无数据，使用硬编码 Skill-File 映射")
        return dict(SKILL_FILE_MAP)

    return skill_to_files


def build_ground_truth(
    skill_to_files: Dict[str, Set[str]] | None = None,
    manual_path: str = "",
) -> Dict[str, Set[str]]:
    """构建查询级别的 ground truth

    使用 _file_name 作为文档键（BM25/Vector 两路共同拥有）。

    Args:
        skill_to_files: skill → file_names 映射（None 时自动构建）
        manual_path: 手动标注文件路径 (可选)

    Returns:
        Dict[str, Set[str]]: {query_id: {relevant_file_name, ...}}
    """
    from eval.queries import TEST_QUERIES

    if skill_to_files is None:
        skill_to_files = build_ground_truth_from_milvus()

    ground_truth: Dict[str, Set[str]] = {}

    # 自动标注: query 的 skill 对应文件视为 relevant
    for q in TEST_QUERIES:
        query_skill = q["skill"]
        relevant_files = skill_to_files.get(query_skill, set())
        ground_truth[q["id"]] = relevant_files

    # 手动标注覆盖 (如果存在)
    if manual_path:
        manual_file = Path(manual_path)
        if manual_file.exists():
            manual = json.loads(manual_file.read_text(encoding="utf-8"))
            for qid, file_names in manual.items():
                ground_truth[qid] = set(file_names)
            print(f"已加载手动标注: {len(manual)} 个查询")

    total_relevant = sum(len(v) for v in ground_truth.values())
    print(
        f"Ground Truth 构建完成: {len(ground_truth)} 个查询, "
        f"共 {total_relevant} 个相关文件标注"
    )

    for qid, files in ground_truth.items():
        if not files:
            print(f"  警告: 查询 '{qid}' 没有相关文件（skill 可能无文档）")

    return ground_truth
