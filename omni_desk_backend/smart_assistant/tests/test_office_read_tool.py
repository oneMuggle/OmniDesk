from smart_assistant.tools.office_read_tool import OfficeReadTool


def _ctx(**kw):
    base = {"history": [], "attachment": {"text": "a" * 20_000, "filename": "长文.txt"}}
    base.update(kw)
    return base


class TestOfficeReadTool:
    def setup_method(self):
        self.tool = OfficeReadTool()

    def test_reads_chunk_range(self):
        result = self.tool.execute("", _ctx())
        assert result["found"] is True
        assert len(result["chunks"]) == 1  # 默认读第 1 片

    def test_reads_specific_chunk(self):
        ctx = _ctx()
        ctx["attachment"]["chunk_index"] = 2
        result = self.tool.execute("", ctx)
        # 20000 字符按 8000 切片:chunk0/1 各 8000,chunk2 为 4000
        assert result["chunks"][0] == "a" * 4_000

    def test_no_attachment_returns_not_found(self):
        result = self.tool.execute("", {"history": []})
        assert result["found"] is False
        assert "未找到" in result["message"]

    def test_invalid_chunk_index_returns_not_found(self):
        ctx = _ctx()
        ctx["attachment"]["chunk_index"] = 99
        result = self.tool.execute("", ctx)
        assert result["found"] is False
