"""内存故障诊断专用工具

此 Skill 主要依赖现有的通用工具（retrieve_knowledge, get_current_time,
query_prometheus_alerts 等）。

如需添加内存诊断专用工具（如解析 jmap 输出、分析 GC 日志等），
可在此文件中使用 @tool 装饰器定义，SkillManager 会自动发现和加载。
"""

# 示例：如需添加专用工具，参考以下模板
#
# from langchain_core.tools import tool
#
# @tool
# def analyze_heap_dump(dump_path: str) -> str:
#     \"\"\"分析 JVM 堆转储文件，找出内存泄漏点\"\"\"
#     ...
