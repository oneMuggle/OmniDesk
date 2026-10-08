"""utils 子包:smart_assistant 通用工具模块。"""

import math


def percentile(values, pct: float) -> int:
    """最近秩法百分位；空列表返回 0。"""
    data = sorted(v for v in values if v is not None)
    if not data:
        return 0
    rank = max(1, math.ceil(pct / 100 * len(data)))
    return int(data[rank - 1])
