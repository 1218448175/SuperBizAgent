"""Prometheus 监控目标查询工具

通过 Prometheus HTTP API `GET /api/v1/targets` 拉取当前所有抓取目标及其健康状态。
Agent 可借此回答"监控了哪些服务""哪些目标挂了""采集状态如何"等运维问题。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from langchain_core.tools import tool
from loguru import logger

from app.config import config

TARGETS_API_PATH = "/api/v1/targets"


def _query_targets_api() -> tuple[list[dict[str, Any]], dict[str, int], str | None]:
    """请求 `GET {prometheus_base_url}/api/v1/targets`。

    返回 (active_targets, health_counts, error)。
    - active_targets: 已简化的活跃目标列表，按健康状态（UP 优先）排序
    - health_counts: {"up": N, "down": N}
    - error: 成功时为 None
    """
    base_url = config.prometheus_base_url.rstrip("/")
    api_url = f"{base_url}{TARGETS_API_PATH}"
    logger.info("Querying Prometheus targets: {}", api_url)

    try:
        with httpx.Client(timeout=config.prometheus_request_timeout) as client:
            resp = client.get(api_url)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        return [], {}, f"failed to query Prometheus targets: {e}"
    except json.JSONDecodeError as e:
        return [], {}, f"failed to parse response: {e}"

    if body.get("status") != "success":
        err_msg = body.get("error") or "Prometheus returned non-success status"
        return [], {}, str(err_msg)

    data = body.get("data") or {}
    active = data.get("activeTargets") or []
    if not isinstance(active, list):
        return [], {}, "unexpected response format: activeTargets is not a list"

    health_counts: dict[str, int] = {"up": 0, "down": 0}
    simplified: list[dict[str, Any]] = []

    for t in active:
        if not isinstance(t, dict):
            continue

        labels = t.get("labels") or {}
        health = str(t.get("health", "") or "").lower()
        if health in health_counts:
            health_counts[health] += 1

        # 提取最后一次抓取错误（如有）
        last_error = str(t.get("lastError", "") or "") or None

        simplified.append(
            {
                "job": str(labels.get("job", "")),
                "instance": str(labels.get("instance", "")),
                "health": health,
                "scrape_url": str(t.get("scrapeUrl", "")),
                "last_scrape": str(t.get("lastScrape", "")),
                "last_error": last_error,
            }
        )

    # 排序：UP 在前，然后按 job 名称排序
    simplified.sort(key=lambda x: (0 if x["health"] == "up" else 1, x["job"]))

    return simplified, health_counts, None


@tool
def query_prometheus_targets() -> str:
    """查询 Prometheus 当前所有监控目标（抓取目标）及其健康状态。

    适用场景：用户关心「监控了哪些服务」「哪些目标挂掉了 (DOWN)」「Prometheus 在采集哪些
    端点」「某个 job 的采集状态如何」等运维/可观测性问题。无需参数，直接调用即可获取
    Prometheus 服务端当前注册的全部 scrape target 列表。

    返回内容：每个目标包含 job 名称、instance、健康状态 (up/down)、抓取 URL、
    最后一次抓取时间、以及最后一次错误信息（仅 DOWN 时有值）。结果按 UP 优先排序，
    并附带健康统计计数 (health_counts: {"up": N, "down": M})。

    Returns:
        str: JSON 字符串。成功时含 targets 列表与 health_counts 统计；
             失败时含 success=false 与 error。
    """
    targets, health_counts, err = _query_targets_api()
    if err:
        out = {
            "success": False,
            "error": err,
            "message": "Failed to query Prometheus targets",
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    out = {
        "success": True,
        "targets": targets,
        "total": len(targets),
        "health_counts": health_counts,
        "message": (
            f"共 {len(targets)} 个监控目标："
            f"{health_counts.get('up', 0)} 个 UP, "
            f"{health_counts.get('down', 0)} 个 DOWN"
        ),
    }
    logger.info(
        "Prometheus targets query completed: {} targets, up={}, down={}",
        len(targets),
        health_counts.get("up", 0),
        health_counts.get("down", 0),
    )
    return json.dumps(out, ensure_ascii=False, indent=2)
