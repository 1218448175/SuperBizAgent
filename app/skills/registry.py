"""Skill 运行时注册表 — 管理已加载的 Skill 及其生命周期"""

from typing import Dict, List, Optional
from loguru import logger

from app.skills.base import SkillManifest, SkillContext


class SkillRegistry:
    """Skill 运行时注册表

    负责：
    - 存储所有已发现的 Skill 元数据
    - 跟踪激活/停用状态
    - 提供查询接口
    """

    def __init__(self):
        # 所有已发现的 Skill（key: skill name）
        self._manifests: Dict[str, SkillManifest] = {}
        # 已激活的 Skill 上下文（key: skill name）
        self._active_contexts: Dict[str, SkillContext] = {}
        # 变更版本号（每次激活/停用/重载 +1，供 Agent 检测是否需要刷新）
        self._version: int = 0

    # ── 注册/注销 ──────────────────────────────────────────────

    def register(self, manifest: SkillManifest) -> None:
        """注册一个 Skill 元数据"""
        if manifest.name in self._manifests:
            logger.warning(f"Skill '{manifest.name}' 已存在，将覆盖")
        self._manifests[manifest.name] = manifest
        logger.debug(f"Skill 已注册: {manifest.name} (enabled={manifest.enabled})")

    def unregister(self, name: str) -> bool:
        """注销一个 Skill"""
        removed = self._manifests.pop(name, None) is not None
        self._active_contexts.pop(name, None)
        if removed:
            logger.info(f"Skill 已注销: {name}")
        return removed

    # ── 查询 ────────────────────────────────────────────────────

    def get_manifest(self, name: str) -> Optional[SkillManifest]:
        """获取 Skill 元数据"""
        return self._manifests.get(name)

    def list_manifests(self) -> List[SkillManifest]:
        """列出所有已注册的 Skill 元数据"""
        return list(self._manifests.values())

    def list_enabled(self) -> List[SkillManifest]:
        """列出所有启用的 Skill"""
        return [m for m in self._manifests.values() if m.enabled]

    def list_disabled(self) -> List[SkillManifest]:
        """列出所有禁用的 Skill"""
        return [m for m in self._manifests.values() if not m.enabled]

    @property
    def version(self) -> int:
        """Skill 注册表版本号（每次变更递增）"""
        return self._version

    @property
    def active_skill_names(self) -> List[str]:
        """当前激活的 Skill 名称列表"""
        return list(self._active_contexts.keys())

    # ── 激活/停用（运行时上下文）────────────────────────────────

    def activate(self, context: SkillContext) -> None:
        """激活一个 Skill（将上下文注入运行时）"""
        name = context.manifest.name
        if name not in self._manifests:
            raise ValueError(f"Skill '{name}' 未注册，请先 register()")
        self._active_contexts[name] = context
        self._version += 1
        logger.info(f"Skill 已激活: {name} (version={self._version})")

    def deactivate(self, name: str) -> bool:
        """停用一个 Skill（从运行时移除上下文）"""
        removed = self._active_contexts.pop(name, None) is not None
        if removed:
            self._version += 1
            logger.info(f"Skill 已停用: {name} (version={self._version})")
        return removed

    def get_active_context(self, name: str) -> Optional[SkillContext]:
        """获取已激活的 Skill 上下文"""
        return self._active_contexts.get(name)

    def get_all_active_contexts(self) -> Dict[str, SkillContext]:
        """获取所有已激活的 Skill 上下文"""
        return dict(self._active_contexts)

    def is_active(self, name: str) -> bool:
        """检查 Skill 是否已激活"""
        return name in self._active_contexts

    # ── 聚合查询 ────────────────────────────────────────────────

    def get_active_tools(self) -> list:
        """获取所有已激活 Skill 的工具（去重）"""
        seen = set()
        tools = []
        for ctx in self._active_contexts.values():
            for tool in ctx.tools:
                tool_name = getattr(tool, "name", str(tool))
                if tool_name not in seen:
                    seen.add(tool_name)
                    tools.append(tool)
        return tools

    def get_active_prompts(self, separator: str = "\n\n") -> str:
        """获取所有已激活 Skill 的提示词（拼接）"""
        parts = []
        for ctx in self._active_contexts.values():
            if ctx.prompt:
                parts.append(
                    f"## 领域能力: {ctx.manifest.display_name}\n\n{ctx.prompt}"
                )
        return separator.join(parts)

    def get_active_skill_names(self) -> List[str]:
        """获取所有已激活 Skill 的名称列表（用于向量检索过滤）"""
        return [ctx.manifest.name for ctx in self._active_contexts.values()]

    # ── 统计 ────────────────────────────────────────────────────

    @property
    def total_count(self) -> int:
        return len(self._manifests)

    @property
    def active_count(self) -> int:
        return len(self._active_contexts)

    def summary(self) -> dict:
        """返回注册表概览"""
        return {
            "total": self.total_count,
            "active": self.active_count,
            "enabled": len(self.list_enabled()),
            "disabled": len(self.list_disabled()),
            "active_names": self.active_skill_names,
        }


# 全局单例
skill_registry = SkillRegistry()
