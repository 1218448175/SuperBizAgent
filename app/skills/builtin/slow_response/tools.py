"""响应慢诊断专用工具

此 Skill 主要依赖现有的通用工具（retrieve_knowledge, get_current_time,
query_prometheus_alerts 等）。

如需添加性能诊断专用工具（如 APM 数据查询、火焰图分析等），
可在此文件中使用 @tool 装饰器定义，SkillManager 会自动发现和加载。
"""

# 示例：如需添加专用工具，参考以下模板
#
# from langchain_core.tools import tool
#
# @tool
# def analyze_slow_queries(time_range_minutes: int = 30) -> str:
#     \"\"\"分析最近N分钟内的慢查询\"\"\"
#     ...
