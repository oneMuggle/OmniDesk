import pytest
from file_processing.ai.summarizer import DataSummarizer


class TestDataSummarizer:

    def test_summarize_single_sheet(self):
        summarizer = DataSummarizer()
        sheets_data = [
            {
                'name': 'Sheet1',
                'headers': ['姓名', '年龄', '城市'],
                'data': [
                    ['张三', 25, '北京'],
                    ['李四', 30, '上海'],
                    ['王五', 28, '北京'],
                ],
            }
        ]

        summary = summarizer.summarize_table(sheets_data)

        assert summary['sheet_count'] == 1
        assert summary['total_rows'] == 3
        assert len(summary['summaries']) == 1
        assert summary['summaries'][0]['sheet_name'] == 'Sheet1'
        assert summary['summaries'][0]['row_count'] == 3
        assert summary['summaries'][0]['column_count'] == 3

    def test_summarize_multi_sheet(self):
        summarizer = DataSummarizer()
        sheets_data = [
            {
                'name': '销售数据',
                'headers': ['月份', '销售额', '成本'],
                'data': [
                    ['1月', 10000, 6000],
                    ['2月', 15000, 8000],
                ],
            },
            {
                'name': '员工信息',
                'headers': ['姓名', '部门', '薪资'],
                'data': [
                    ['张三', '销售', 8000],
                ],
            }
        ]

        summary = summarizer.summarize_table(sheets_data)

        assert summary['sheet_count'] == 2
        assert summary['total_rows'] == 3  # 2 + 1
        assert len(summary['summaries']) == 2

    def test_summarize_numeric_columns(self):
        summarizer = DataSummarizer()
        sheets_data = [
            {
                'name': 'Sales',
                'headers': ['Product', 'Price', 'Quantity'],
                'data': [
                    ['Apple', 10, 100],
                    ['Banana', 5, 200],
                    ['Orange', 8, 150],
                ],
            }
        ]

        summary = summarizer.summarize_table(sheets_data)

        # 检查数值列是否有统计信息
        columns = summary['summaries'][0]['columns']
        assert len(columns) == 3

        # Price 列应该有数值统计
        price_col = next(c for c in columns if c['name'] == 'Price')
        assert 'min' in price_col
        assert 'max' in price_col
        assert 'mean' in price_col
        assert 'sum' in price_col

        # Product 列是字符串，不应该有数值统计
        product_col = next(c for c in columns if c['name'] == 'Product')
        assert 'min' not in product_col or product_col.get('min') is None

    def test_summarize_empty_data(self):
        summarizer = DataSummarizer()
        sheets_data = []

        summary = summarizer.summarize_table(sheets_data)

        assert summary['sheet_count'] == 0
        assert summary['total_rows'] == 0
        assert len(summary['summaries']) == 0
