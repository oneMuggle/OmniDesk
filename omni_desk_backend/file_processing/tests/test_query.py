import pytest
from unittest.mock import Mock, patch
from file_processing.ai.query import NaturalLanguageQuery


class TestNaturalLanguageQuery:

    @patch('file_processing.ai.query.Client')
    def test_query_basic(self, mock_client_class):
        # Mock Ollama client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.chat.return_value = {
            'message': {'content': '2月份的销售额最高，为15000元。'}
        }

        query = NaturalLanguageQuery()
        context = {
            'sheets_data': [
                {
                    'name': '销售数据',
                    'headers': ['月份', '销售额'],
                    'data': [
                        ['1月', 10000],
                        ['2月', 15000],
                        ['3月', 12000],
                    ],
                }
            ]
        }

        answer = query.query('哪个月份销售额最高？', context)

        assert '2月' in answer or '15000' in answer
        mock_client.chat.assert_called_once()

    @patch('file_processing.ai.query.Client')
    def test_query_empty_data(self, mock_client_class):
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        query = NaturalLanguageQuery()
        context = {'sheets_data': []}

        answer = query.query('数据是什么？', context)

        assert '没有表格数据' in answer or answer == ''

    def test_build_prompt(self):
        query = NaturalLanguageQuery()
        context = {
            'sheets_data': [
                {
                    'name': 'Sales',
                    'headers': ['Product', 'Price'],
                    'data': [
                        ['Apple', 10],
                        ['Banana', 5],
                    ],
                }
            ]
        }

        prompt = query._build_prompt('What is the total?', context)

        assert 'Sales' in prompt
        assert 'Product' in prompt
        assert 'Price' in prompt
        assert 'Apple' in prompt
        assert 'What is the total?' in prompt
