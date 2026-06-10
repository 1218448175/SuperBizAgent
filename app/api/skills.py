"""Skill 管理 API — 提供 Skill 的热加载/卸载/查询接口"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

from app.skills import skill_manager, skill_registry
from app.skills.base import SkillManifest


router = APIRouter(prefix="/skills", tags=["Skill 管理"])


# ── 响应模型 ────────────────────────────────────────────────────

class SkillSummary(BaseModel):
    """Skill 概览"""
    name: str
    display_name: str
    description: str
    version: str
    enabled: bool
    active: bool
    indexed: bool
    doc_count: int
    tools_count: int
    keywords: List[str]
    tags: List[str]


class SkillDetail(SkillSummary):
    """Skill 详情"""
    prompt_preview: str = Field(default="", description="提示词前 500 字符")
    trigger_patterns: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    author: str = ""


class ActivateResult(BaseModel):
    """激活/停用结果"""
    success: bool
    message: str


class MatchRequest(BaseModel):
    """匹配请求"""
    query: str = Field(description="用户查询文本")
    top_k: int = Field(default=2, description="返回最相关的 N 个 Skill")
    auto_activate: bool = Field(default=False, description="是否自动激活匹配到的 Skill")


class MatchResponse(BaseModel):
    """匹配响应"""
    query: str
    matched: List[SkillSummary]
    auto_activated: List[str] = Field(default_factory=list)


class IndexResult(BaseModel):
    """索引结果"""
    skill_name: str
    chunks_indexed: int
    error: str = ""


# ── 辅助方法 ────────────────────────────────────────────────────

def _build_summary(name: str) -> SkillSummary:
    """构建 Skill 概览"""
    manifest = skill_registry.get_manifest(name)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 未注册")

    ctx = skill_registry.get_active_context(name)
    active = ctx is not None
    return SkillSummary(
        name=manifest.name,
        display_name=manifest.display_name,
        description=manifest.description,
        version=manifest.version,
        enabled=manifest.enabled,
        active=active,
        indexed=ctx.indexed if ctx else False,
        doc_count=ctx.doc_count if ctx else 0,
        tools_count=len(ctx.tools) if ctx else 0,
        keywords=manifest.keywords,
        tags=manifest.tags,
    )


def _build_detail(name: str) -> SkillDetail:
    """构建 Skill 详情"""
    manifest = skill_registry.get_manifest(name)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 未注册")

    ctx = skill_registry.get_active_context(name)
    active = ctx is not None
    prompt = ctx.prompt if ctx else ""
    return SkillDetail(
        name=manifest.name,
        display_name=manifest.display_name,
        description=manifest.description,
        version=manifest.version,
        enabled=manifest.enabled,
        active=active,
        indexed=ctx.indexed if ctx else False,
        doc_count=ctx.doc_count if ctx else 0,
        tools_count=len(ctx.tools) if ctx else 0,
        keywords=manifest.keywords,
        tags=manifest.tags,
        prompt_preview=prompt[:500] + ("..." if len(prompt) > 500 else ""),
        trigger_patterns=manifest.trigger_patterns,
        depends_on=manifest.depends_on,
        author=manifest.author,
    )


# ── 查询接口 ────────────────────────────────────────────────────

@router.get("", response_model=List[SkillSummary])
async def list_skills(
    active_only: bool = Query(default=False, description="只显示已激活的 Skill"),
    enabled_only: bool = Query(default=False, description="只显示启用的 Skill"),
):
    """列出所有 Skill"""
    manifests = skill_registry.list_manifests()
    if enabled_only:
        manifests = [m for m in manifests if m.enabled]
    if active_only:
        manifests = [m for m in manifests if skill_registry.is_active(m.name)]

    return [_build_summary(m.name) for m in manifests]


@router.get("/{name}", response_model=SkillDetail)
async def get_skill(name: str):
    """获取 Skill 详情"""
    return _build_detail(name)


@router.get("/registry/summary")
async def get_registry_summary():
    """获取 Skill 注册表概览统计"""
    return skill_registry.summary()


# ── 激活/停用接口（热加载核心）──────────────────────────────────

@router.post("/{name}/activate", response_model=ActivateResult)
async def activate_skill(name: str):
    """激活指定 Skill（热加载：加载 tools + prompt + 索引 docs）"""
    logger.info(f"API 请求: 激活 Skill '{name}'")
    success, message = skill_manager.activate(name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return ActivateResult(success=success, message=message)


@router.post("/{name}/deactivate", response_model=ActivateResult)
async def deactivate_skill(name: str):
    """停用指定 Skill"""
    logger.info(f"API 请求: 停用 Skill '{name}'")
    success, message = skill_manager.deactivate(name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return ActivateResult(success=success, message=message)


@router.post("/activate-all", response_model=Dict[str, ActivateResult])
async def activate_all_skills():
    """激活所有启用的 Skill"""
    logger.info("API 请求: 激活所有 Skill")
    results = skill_manager.activate_all()
    return {
        name: ActivateResult(success=ok, message=msg)
        for name, (ok, msg) in results.items()
    }


@router.post("/deactivate-all", response_model=Dict[str, ActivateResult])
async def deactivate_all_skills():
    """停用所有已激活的 Skill"""
    logger.info("API 请求: 停用所有 Skill")
    results = skill_manager.deactivate_all()
    return {
        name: ActivateResult(success=ok, message=msg)
        for name, (ok, msg) in results.items()
    }


# ── 重载接口 ────────────────────────────────────────────────────

@router.post("/{name}/reload", response_model=ActivateResult)
async def reload_skill(name: str):
    """重载指定 Skill（从磁盘重新加载配置、工具和提示词）"""
    logger.info(f"API 请求: 重载 Skill '{name}'")
    success, message = skill_manager.reload(name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return ActivateResult(success=success, message=message)


@router.post("/reload-all", response_model=Dict[str, ActivateResult])
async def reload_all_skills():
    """重载所有 Skill"""
    logger.info("API 请求: 重载所有 Skill")
    results = skill_manager.reload_all()
    return {
        name: ActivateResult(success=ok, message=msg)
        for name, (ok, msg) in results.items()
    }


# ── 索引接口 ────────────────────────────────────────────────────

@router.post("/{name}/index", response_model=IndexResult)
async def index_skill_docs(name: str):
    """索引指定 Skill 的知识文档到向量库"""
    logger.info(f"API 请求: 索引 Skill '{name}' 文档")
    count, error = skill_manager.index_skill(name)
    if error and count == 0:
        raise HTTPException(status_code=400, detail=error)
    return IndexResult(skill_name=name, chunks_indexed=count, error=error)


@router.post("/index-all", response_model=List[IndexResult])
async def index_all_skill_docs():
    """索引所有 Skill 的知识文档到向量库"""
    logger.info("API 请求: 索引所有 Skill 文档")
    results = skill_manager.index_all_skills()
    return [
        IndexResult(skill_name=name, chunks_indexed=count, error=error)
        for name, (count, error) in results.items()
    ]


# ── 匹配接口 ────────────────────────────────────────────────────

@router.post("/match", response_model=MatchResponse)
async def match_skills(body: MatchRequest):
    """根据查询文本匹配 Skill（关键词匹配）"""
    logger.info(f"API 请求: 匹配 Skill, query='{body.query[:80]}...'")
    matched = skill_manager.match(body.query, top_k=body.top_k)
    auto_activated: List[str] = []
    if body.auto_activate:
        for m in matched:
            if not skill_registry.is_active(m.name):
                success, _ = skill_manager.activate(m.name)
                if success:
                    auto_activated.append(m.name)
    return MatchResponse(
        query=body.query,
        matched=[_build_summary(m.name) for m in matched],
        auto_activated=auto_activated,
    )


# ── 发现接口 ────────────────────────────────────────────────────

@router.post("/discover", response_model=List[SkillSummary])
async def discover_skills():
    """重新扫描 Skill 目录，发现新 Skill（已注册的会被覆盖）"""
    logger.info("API 请求: 重新发现 Skill")
    discovered = skill_manager.discover_all()
    return [_build_summary(m.name) for m in discovered]
