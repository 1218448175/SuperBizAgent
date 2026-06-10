"""Skill 基础模型定义

每个 Skill 是一个自包含的领域知识包，包含：
- 元数据 (skill.yaml)
- 领域提示词 (prompt.md)
- 知识文档 (docs/*.md)
- 专用工具 (tools.py)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    """Skill 元数据清单 — 从 skill.yaml 解析"""

    name: str = Field(description="Skill 唯一标识，如 cpu_troubleshoot")
    display_name: str = Field(description="展示名称，如 CPU 故障诊断")
    description: str = Field(description="Skill 功能描述，用于匹配和展示")
    version: str = Field(default="1.0.0", description="Skill 版本号")
    enabled: bool = Field(default=True, description="是否启用")
    keywords: List[str] = Field(
        default_factory=list,
        description="触发关键词列表，用户问题命中任一关键词即激活此 Skill",
    )
    trigger_patterns: List[str] = Field(
        default_factory=list,
        description="正则触发模式（可选），高级匹配用",
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Skill 自带的工具函数名列表（从 tools.py 自动发现）",
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="依赖的其他 Skill name 列表",
    )
    author: str = Field(default="", description="作者")
    tags: List[str] = Field(default_factory=list, description="分类标签")

    class Config:
        extra = "allow"  # 允许 skill.yaml 中有额外字段，保持向前兼容


class SkillContext(BaseModel):
    """Skill 运行时上下文 — 激活后注入 Agent"""

    manifest: SkillManifest = Field(description="Skill 元数据")
    prompt: str = Field(default="", description="领域系统提示词")
    tools: list = Field(default_factory=list, description="领域专用 @tool 函数列表")
    doc_count: int = Field(default=0, description="知识文档数量")
    indexed: bool = Field(default=False, description="知识文档是否已索引到向量库")

    class Config:
        arbitrary_types_allowed = True  # 允许 tool 函数对象
