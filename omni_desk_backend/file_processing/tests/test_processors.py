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


class TestWordProcessor:

    def test_extract_text(self):
        from file_processing.processors.word import WordProcessor
        processor = WordProcessor()
        text = processor.extract_text('tests/fixtures/sample.docx')
        assert '测试文档' in text
        assert '这是第一段内容' in text

    def test_extract_markdown(self):
        from file_processing.processors.word import WordProcessor
        processor = WordProcessor()
        md = processor.extract_markdown('tests/fixtures/sample.docx')
        assert '# 测试文档' in md or '**测试文档**' in md

    def test_extract_structured(self):
        from file_processing.processors.word import WordProcessor
        processor = WordProcessor()
        data = processor.extract_structured('tests/fixtures/sample.docx')
        assert 'paragraphs' in data
        assert 'tables' in data
        assert len(data['tables']) > 0


class TestPDFProcessor:

    def test_extract_text(self):
        from file_processing.processors.pdf import PDFProcessor
        processor = PDFProcessor()
        text = processor.extract_text('tests/fixtures/sample.pdf')
        assert len(text) > 0

    def test_extract_markdown(self):
        from file_processing.processors.pdf import PDFProcessor
        processor = PDFProcessor()
        md = processor.extract_markdown('tests/fixtures/sample.pdf')
        assert len(md) > 0

    def test_get_metadata(self):
        from file_processing.processors.pdf import PDFProcessor
        processor = PDFProcessor()
        metadata = processor.get_metadata('tests/fixtures/sample.pdf')
        assert 'page_count' in metadata
        assert metadata['page_count'] > 0
