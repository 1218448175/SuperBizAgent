"""CPU 故障诊断专用工具

此 Skill 主要依赖现有的通用工具（retrieve_knowledge, get_current_time,
query_prometheus_alerts 等）。

如需添加 CPU 诊断专用工具（如解析 /proc/stat、分析 perf 数据等），
可在此文件中使用 @tool 装饰器定义，SkillManager 会自动发现和加载。
"""

# 示例：如需添加专用工具，参考以下模板
#
# from langchain_core.tools import tool
#
# @tool
# def analyze_cpu_profile(profile_data: str) -> str:
#     \"\"\"分析 CPU profile 数据，找出热点函数\"\"\"
#     ...
