"""smart_assistant 通用工具函数。"""

import math


def percentile(values, pct: float) -> int:
    """最近秩法百分位；空列表返回 0。

    Args:
        values: 数值列表（None 值会被过滤）
        pct: 百分位数（0-100）

    Returns:
        百分位数值，空列表返回 0
    """
    data = sorted(v for v in values if v is not None)
    if not data:
        return 0
    rank = max(1, math.ceil(pct / 100 * len(data)))
    return int(data[rank - 1])
