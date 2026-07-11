import pytest
from file_processing.processors.excel import ExcelProcessor


class TestExcelProcessor:

    def test_extract_text_simple(self):
        processor = ExcelProcessor()
        text = processor.extract_text('tests/fixtures/simple.xlsx')
        assert 'Sheet1' in text
        assert '张三' in text
        assert '25' in text

    def test_extract_markdown_table(self):
        processor = ExcelProcessor()
        md = processor.extract_markdown('tests/fixtures/simple.xlsx')
        assert '## Sheet1' in md
        assert '| 姓名 | 年龄 | 城市 |' in md
        assert '| --- | --- | --- |' in md
        assert '| 张三 | 25 | 北京 |' in md

    def test_extract_structured_single_sheet(self):
        processor = ExcelProcessor()
        data = processor.extract_structured('tests/fixtures/simple.xlsx')
        assert data['sheet_count'] == 1
        assert len(data['sheets']) == 1
        assert data['sheets'][0]['name'] == 'Sheet1'
        assert data['sheets'][0]['row_count'] == 3
        assert data['sheets'][0]['column_count'] == 3

    def test_extract_structured_multi_sheet(self):
        processor = ExcelProcessor()
        data = processor.extract_structured('tests/fixtures/multi_sheet.xlsx')
        assert data['sheet_count'] == 2
        assert data['sheets'][0]['name'] == '销售数据'
        assert data['sheets'][1]['name'] == '员工信息'

    def test_get_metadata(self):
        processor = ExcelProcessor()
        metadata = processor.get_metadata('tests/fixtures/multi_sheet.xlsx')
        assert metadata['sheet_count'] == 2
        assert '销售数据' in metadata['sheet_names']
        assert '员工信息' in metadata['sheet_names']
