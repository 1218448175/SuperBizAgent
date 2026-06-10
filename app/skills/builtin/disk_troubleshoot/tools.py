"""磁盘故障诊断专用工具

此 Skill 主要依赖现有的通用工具（retrieve_knowledge, get_current_time,
query_prometheus_alerts 等）。

如需添加磁盘诊断专用工具（如扫描大文件、分析 inode 等），
可在此文件中使用 @tool 装饰器定义，SkillManager 会自动发现和加载。
"""

# 示例：如需添加专用工具，参考以下模板
#
# from langchain_core.tools import tool
#
# @tool
# def find_large_files(directory: str = "/") -> str:
#     \"\"\"扫描目录找出最大的文件\"\"\"
#     ...
