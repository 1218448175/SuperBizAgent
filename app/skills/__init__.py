"""Skill 模块 — 领域知识包系统

提供可插拔的 Skill 管理能力，每个 Skill 包含：
- 领域知识文档（自动索引到 Milvus）
- 专用工具函数（使用 @tool 装饰器）
- 专业系统提示词

用法示例:
    from app.skills import skill_manager, skill_registry

    # 发现并激活所有 Skill
    skill_manager.discover_all()
    skill_manager.activate_all()

    # 匹配用户问题
    matched = skill_manager.match("CPU 使用率过高")
    for m in matched:
        skill_manager.activate(m.name)

    # 获取当前激活的 Skill 工具和提示词
    tools, prompt = skill_manager.get_active_context_for_agent()
"""

from app.skills.base import SkillManifest, SkillContext
from app.skills.registry import SkillRegistry, skill_registry
from app.skills.manager import SkillManager, skill_manager

__all__ = [
    "SkillManifest",
    "SkillContext",
    "SkillRegistry",
    "skill_registry",
    "SkillManager",
    "skill_manager",
]
