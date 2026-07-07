"""多工具结果聚合器。

接收多工具执行结果,按时间排序,按模块分组,生成结构化聚合数据
供前端 <AggregatedDayCard> 直接渲染。
"""
from __future__ import annotations

from typing import Any


class ResultSynthesizer:
    """将多个工具结果合并为一个结构化回答。

    设计意图:
    - 输入:每个工具返回的 dict(含 module_label, posts/rooms/schedules 等数组)
    - 输出:统一结构 {summary, items, total_count, module_counts}
    - 前端只需消费 items[].{type, module, data, sort_key} 即可分组渲染
    """

    # 已知的 items 数组字段名(按优先级)
    ITEM_FIELDS = ("posts", "rooms", "schedules", "items", "issues", "links", "events", "memos", "results")

    def synthesize(self, tool_results: list[dict], query: str) -> dict:
        """聚合多工具结果。

        参数:
            tool_results: 每个元素是一个工具返回的 dict,至少含
                - "tool": intent_type 字符串
                - "module_label": 前端显示用模块名
                - "found": bool
                以及 items 数组(字段名见 ITEM_FIELDS)
            query: 用户原始 query(预留,当前未使用)

        返回:
            {
                "summary": str,           # 人类可读汇总
                "items": list[dict],      # 排序后的所有 item,前端聚合卡片渲染
                "total_count": int,       # item 总数
                "module_counts": dict,    # {模块名: 数量}
            }
        """
        items = []
        for r in tool_results:
            module = r.get("module_label", r.get("tool", "unknown"))
            tool_name = r.get("tool", "")
            # 找 items 数组
            raw_items = None
            for f in self.ITEM_FIELDS:
                if f in r and isinstance(r[f], list):
                    raw_items = r[f]
                    break

            if raw_items:
                for raw in raw_items:
                    items.append({
                        "type": tool_name,
                        "module": module,
                        "data": raw,
                        "sort_key": raw.get("sort_key") or "9999",
                    })
            elif r.get("found"):
                # 单条结果(无数组字段):整 dict 作为一条 item
                items.append({
                    "type": tool_name,
                    "module": module,
                    "data": {k: v for k, v in r.items() if k not in ("found", "tool", "module_label", "message")},
                    "sort_key": r.get("sort_key") or "9999",
                })

        # 排序:按 sort_key 升序
        items.sort(key=lambda x: x["sort_key"])

        # 模块统计
        module_counts: dict[str, int] = {}
        for it in items:
            module_counts[it["module"]] = module_counts.get(it["module"], 0) + 1

        # 生成 summary
        if items:
            summary_parts = [f"{m} {n} 条" for m, n in module_counts.items()]
            summary = f"共 {len(items)} 项:" + "、".join(summary_parts)
        else:
            summary = "未找到相关信息"

        return {
            "summary": summary,
            "items": items,
            "total_count": len(items),
            "module_counts": module_counts,
        }
