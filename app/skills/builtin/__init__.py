"""内置 Skill 集合

每个子目录代表一个独立的领域知识包，包含：
- skill.yaml: 元数据和触发关键词
- prompt.md: 领域系统提示词
- docs/: 知识文档（自动索引到 Milvus）
- tools.py: 领域专用 @tool 函数（可选）
"""
