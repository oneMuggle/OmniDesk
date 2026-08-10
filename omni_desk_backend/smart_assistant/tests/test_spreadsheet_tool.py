from unittest.mock import MagicMock, patch

from smart_assistant.tools.spreadsheet_tool import SpreadsheetTool


def _ctx_with_sheets():
    return {
        "history": [],
        "attachment": {
            "filename": "名单.xlsx",
            "sheets": [
                {
                    "name": "人员表",
                    "headers": ["姓名", "部门", "人数"],
                    "data": [["张三", "技术部", "3"], ["李四", "市场部", "5"]],
                }
            ],
        },
    }


class TestSpreadsheetTool:
    def setup_method(self):
        self.tool = SpreadsheetTool()

    def test_simple_aggregation(self):
        result = self.tool.execute("总人数", _ctx_with_sheets())
        assert result["found"] is True
        assert result["stats"]["total_rows"] == 2
        assert result["stats"]["columns"] == ["姓名", "部门", "人数"]

    @patch("smart_assistant.tools.spreadsheet_tool.NaturalLanguageQuery")
    def test_natural_language_query_falls_back_to_llm(self, mock_cls):
        mock_query = MagicMock()
        # P1A-1: query() 返回 (content, usage) 元组
        mock_query.query.return_value = ("总人数为 8 人", {
            "total_tokens": 12,
            "model_name": "qwen2.5:7b",
            "endpoint_id": None,
            "estimated_cost": 0.0,
        })
        mock_cls.return_value = mock_query
        result = self.tool.execute("各列人数加总", _ctx_with_sheets())
        assert result["found"] is True
        assert "8" in result["answer"]
        mock_query.query.assert_called_once()

    def test_no_sheets_returns_not_found(self):
        result = self.tool.execute("统计", {"history": []})
        assert result["found"] is False