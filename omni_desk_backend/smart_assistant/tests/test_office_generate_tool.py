"""OfficeGenerateTool 测试 —— TDD 红阶段：先写测试，确认失败（模块不存在）"""

from unittest.mock import patch

from smart_assistant.tools.office_generate_tool import OfficeGenerateTool


def _ctx(**kw):
    base = {"history": [], "user": None}
    base.update(kw)
    return base


class TestOfficeGenerateTool:
    def setup_method(self):
        self.tool = OfficeGenerateTool()

    @patch("smart_assistant.tools.office_generate_tool._plan_document_structure")
    def test_dry_run_returns_draft(self, mock_plan):
        mock_plan.return_value = {
            "structure": [
                {"type": "heading", "content": "请假单"},
                {"type": "paragraph", "content": "姓名：{name}，日期：{date}"},
            ],
            "variables": {"name": "张三", "date": "2026-08-05"},
        }
        result = self.tool.execute("生成请假单，张三，2026-08-05", _ctx(dry_run=True))
        assert result["found"] is True
        assert result["draft"]["summary"] == "确认生成文档《请假单.docx》"

    @patch("smart_assistant.tools.office_generate_tool._plan_document_structure")
    def test_dry_run_plan_failure_returns_not_found(self, mock_plan):
        mock_plan.return_value = None
        result = self.tool.execute("随便生成", _ctx(dry_run=True))
        assert result["found"] is False

    @patch("smart_assistant.tools.office_generate_tool._render_docx_to_file")
    def test_confirmed_generates_file(self, mock_render):
        mock_render.return_value = ("tmp_office/请假单.docx", b"fake-docx-bytes")
        with patch(
            "smart_assistant.tools.office_generate_tool.create_download_token",
            return_value="tok123",
        ):
            result = self.tool.execute(
                "生成请假单",
                _ctx(
                    confirmed=True,
                    user={"pk": 7, "id": 7},  # mock 风格 dict，模拟 ToolContext.user.pk
                    draft={
                        "structure": [{"type": "paragraph", "content": "正文 {name}"}],
                        "variables": {"name": "张三"},
                    },
                ),
            )
        assert result["found"] is True
        assert result["file_download"]["filename"] == "请假单.docx"
        assert result["file_download"]["download_url"].endswith("office-download/tok123/")
        mock_render.assert_called_once()