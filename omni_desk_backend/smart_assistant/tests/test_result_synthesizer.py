import pytest
from smart_assistant.agent.result_synthesizer import ResultSynthesizer


@pytest.fixture
def synth():
    return ResultSynthesizer()


def test_empty_results_returns_no_items(synth):
    result = synth.synthesize([], "query")
    assert result["total_count"] == 0
    assert result["items"] == []
    assert "未找到" in result["summary"] or "无" in result["summary"]


def test_single_tool_result_count(synth):
    tool_results = [{
        "tool": "schedule_query",
        "module_label": "排班",
        "posts": [{"title": "周一", "sort_key": "2026-07-08"}],
    }]
    result = synth.synthesize(tool_results, "本周")
    assert result["total_count"] == 1
    assert result["module_counts"] == {"排班": 1}


def test_multiple_tools_aggregated(synth):
    tool_results = [
        {"tool": "schedule_query", "module_label": "排班",
         "schedules": [{"duty_date": "2026-07-08", "sort_key": "2026-07-08"}]},
        {"tool": "meeting_room_query", "module_label": "会议室",
         "rooms": [{"name": "R1", "sort_key": "2026-07-09"}]},
        {"tool": "announcement_query", "module_label": "公告",
         "posts": [{"title": "x", "sort_key": "2026-07-07"}]},
    ]
    result = synth.synthesize(tool_results, "本周")
    assert result["total_count"] == 3
    assert result["module_counts"] == {"排班": 1, "会议室": 1, "公告": 1}


def test_items_sorted_by_sort_key(synth):
    tool_results = [{
        "tool": "schedule_query", "module_label": "排班",
        "schedules": [
            {"sort_key": "2026-07-10"},
            {"sort_key": "2026-07-08"},
            {"sort_key": "2026-07-09"},
        ],
    }]
    result = synth.synthesize(tool_results, "")
    keys = [it["sort_key"] for it in result["items"]]
    assert keys == ["2026-07-08", "2026-07-09", "2026-07-10"]


def test_items_without_sort_key_appear_last(synth):
    tool_results = [{
        "tool": "schedule_query", "module_label": "排班",
        "schedules": [
            {"random_field": "x"},  # 无 sort_key → fallback 到 "9999"
            {"sort_key": "2026-07-10"},
        ],
    }]
    result = synth.synthesize(tool_results, "")
    # 无 sort_key 的项目在最后
    assert result["items"][0]["sort_key"] == "2026-07-10"
    assert result["items"][1]["sort_key"] == "9999"


def test_summary_format_chinese(synth):
    tool_results = [
        {"tool": "schedule_query", "module_label": "排班", "schedules": [{}, {}, {}]},
        {"tool": "announcement_query", "module_label": "公告", "posts": [{}]},
    ]
    result = synth.synthesize(tool_results, "本周")
    assert "排班 3 条" in result["summary"]
    assert "公告 1 条" in result["summary"]


def test_each_item_has_type_module_data(synth):
    tool_results = [{
        "tool": "schedule_query", "module_label": "排班",
        "schedules": [{"duty_date": "2026-07-08"}],
    }]
    result = synth.synthesize(tool_results, "")
    item = result["items"][0]
    assert item["type"] == "schedule_query"
    assert item["module"] == "排班"
    assert item["data"] == {"duty_date": "2026-07-08"}


def test_items_with_only_top_level_field(synth):
    """如果工具结果直接是单条数据(无 items 数组),也作为 1 条 item"""
    tool_results = [{
        "tool": "x", "module_label": "X",
        "date": "2026-07-08", "found": True,
        # 注意:无 posts/rooms/schedules 等数组字段
    }]
    result = synth.synthesize(tool_results, "")
    assert len(result["items"]) >= 1


def test_summary_handles_zero_results(synth):
    tool_results = [{
        "tool": "schedule_query", "module_label": "排班",
        "found": False, "message": "未找到",
    }]
    result = synth.synthesize(tool_results, "")
    assert "未找到" in result["summary"] or "0" in result["summary"]


def test_module_counts_aggregated_correctly(synth):
    tool_results = [
        {"tool": "schedule_query", "module_label": "排班",
         "schedules": [{"sort_key": "d1"}, {"sort_key": "d2"}, {"sort_key": "d3"}]},
        {"tool": "announcement_query", "module_label": "公告",
         "posts": [{"sort_key": "d1"}]},
    ]
    result = synth.synthesize(tool_results, "")
    assert result["module_counts"]["排班"] == 3
    assert result["module_counts"]["公告"] == 1
