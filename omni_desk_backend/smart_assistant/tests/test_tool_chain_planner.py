"""工具链规划器的 keyword 子串重叠消解单测。"""

from django.test import TestCase


class TestMemoKeywordOverlap(TestCase):
    """PR1 遗留:『提醒我』同时命中 memo_query(提醒)与 memo_create(提醒我)。"""

    def test_remind_me_is_single_intent(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [
            {"name": "memo_query"},
            {"name": "memo_create"},
            {"name": "memo_update"},
            {"name": "memo_delete"},
        ]
        result = _resolve_intent_overlap("提醒我明天开会", schemas)
        self.assertEqual(result, ["memo_create"])

    def test_remind_me_plus_schedule_is_multi_intent(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [
            {"name": "memo_query"},
            {"name": "memo_create"},
            {"name": "schedule_query"},
        ]
        result = _resolve_intent_overlap("提醒我开会和查明天排班", schemas)
        self.assertEqual(result, ["memo_create", "schedule_query"])

    def test_update_keyword_routes_to_update(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [{"name": "memo_query"}, {"name": "memo_create"}, {"name": "memo_update"}]
        # "改提醒" 是独立 token,不被 "提醒" 覆盖(反向),也不覆盖它
        result = _resolve_intent_overlap("把开会的备忘改提醒到后天", schemas)
        self.assertEqual(result, ["memo_update"])

    def test_delete_keyword_routes_to_delete(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [{"name": "memo_query"}, {"name": "memo_delete"}]
        # "删除" 是 memo_delete 动词关键词;与 memo_query("备忘录"/"便签"/"提醒")、
        # memo_update("改备忘"/"修改备忘"/"更新备忘"/"改提醒")均无子串重叠 → 唯一意图
        result = _resolve_intent_overlap("删除买菜备忘", schemas)
        self.assertEqual(result, ["memo_delete"])
