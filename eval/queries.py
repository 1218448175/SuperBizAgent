"""测试查询集 — 覆盖 5 个 Skill 领域，每个领域 3 条查询"""

TEST_QUERIES = [
    # ── CPU 故障诊断 ──
    {
        "id": "cpu_01",
        "query": "CPU使用率突然升高到90%以上怎么排查",
        "skill": "cpu_troubleshoot",
    },
    {
        "id": "cpu_02",
        "query": "如何定位死循环导致的服务器CPU飙升",
        "skill": "cpu_troubleshoot",
    },
    {
        "id": "cpu_03",
        "query": "定时任务导致CPU负载过高如何处理",
        "skill": "cpu_troubleshoot",
    },

    # ── 内存故障诊断 ──
    {
        "id": "mem_01",
        "query": "Java应用内存使用率持续升高怎么排查",
        "skill": "memory_troubleshoot",
    },
    {
        "id": "mem_02",
        "query": "线上服务发生OOM内存溢出如何处理",
        "skill": "memory_troubleshoot",
    },
    {
        "id": "mem_03",
        "query": "排查JVM堆内存泄漏的方法和步骤",
        "skill": "memory_troubleshoot",
    },

    # ── 磁盘故障诊断 ──
    {
        "id": "disk_01",
        "query": "服务器磁盘空间不足告警怎么处理",
        "skill": "disk_troubleshoot",
    },
    {
        "id": "disk_02",
        "query": "日志文件过大导致磁盘写满该怎么办",
        "skill": "disk_troubleshoot",
    },
    {
        "id": "disk_03",
        "query": "Docker overlay2占用大量磁盘空间如何清理",
        "skill": "disk_troubleshoot",
    },

    # ── 服务不可用诊断 ──
    {
        "id": "svc_01",
        "query": "线上服务突然不可用了怎么快速恢复",
        "skill": "service_unavailable",
    },
    {
        "id": "svc_02",
        "query": "客户端调用接口返回503错误排查",
        "skill": "service_unavailable",
    },
    {
        "id": "svc_03",
        "query": "服务启动失败connection refused怎么处理",
        "skill": "service_unavailable",
    },

    # ── 响应慢诊断 ──
    {
        "id": "slow_01",
        "query": "API接口响应时间超过3秒如何优化",
        "skill": "slow_response",
    },
    {
        "id": "slow_02",
        "query": "数据库慢查询导致服务响应延迟怎么办",
        "skill": "slow_response",
    },
    {
        "id": "slow_03",
        "query": "服务P99延迟突然变高从哪些方面排查",
        "skill": "slow_response",
    },
]
