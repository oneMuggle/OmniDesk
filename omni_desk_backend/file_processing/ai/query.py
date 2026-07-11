from ollama import Client
import pandas as pd
from django.conf import settings


class NaturalLanguageQuery:
    """自然语言查询 - 允许用户用自然语言提问表格数据，通过 Ollama LLM 生成回答"""

    def __init__(self):
        # 从 Django settings 或环境变量读取 Ollama 端点
        ollama_endpoint = getattr(settings, 'OLLAMA_ENDPOINT', 'http://localhost:11434')
        self.client = Client(host=ollama_endpoint)

    def query(self, question: str, context: dict[str, any]) -> str:
        """用自然语言查询表格数据

        Args:
            question: 用户的自然语言问题
            context: 包含 sheets_data 的上下文字典

        Returns:
            LLM 生成的回答字符串
        """
        # 如果没有数据，直接返回
        if not context.get('sheets_data'):
            return "没有表格数据可供分析。"

        prompt = self._build_prompt(question, context)

        response = self.client.chat(
            model='qwen2.5:7b',
            messages=[{'role': 'user', 'content': prompt}]
        )

        return response['message']['content']

    def _build_prompt(self, question: str, context: dict[str, any]) -> str:
        """构建 LLM 提示

        将表格数据转换为 Markdown 格式，并构建清晰的提示文本。
        只使用前 100 行数据，避免超出 LLM 上下文限制。

        Args:
            question: 用户的自然语言问题
            context: 包含 sheets_data 的上下文字典

        Returns:
            构建完成的 LLM 提示字符串
        """
        sheets = context.get('sheets_data', [])
        if not sheets:
            return "没有表格数据可供分析。"

        sheet = sheets[0]
        # 验证数据行列匹配
        headers = sheet.get('headers', [])
        data = sheet.get('data', [])

        if not headers:
            return "表格数据格式错误：缺少列名。"

        # 限制数据量，避免内存问题
        max_rows = min(100, len(data))
        # 确保每行列数与 headers 匹配
        validated_data = []
        for row in data[:max_rows]:
            if len(row) == len(headers):
                validated_data.append(row)
            else:
                # 跳过不匹配的行
                continue

        if not validated_data:
            return "表格数据格式错误：数据行列数不匹配。"

        df = pd.DataFrame(validated_data, columns=headers)
        markdown_table = df.to_markdown(index=False)

        prompt = f"""你是一个数据分析助手。请根据以下表格数据回答用户的问题。

表格数据（Sheet: {sheet['name']}）:
{markdown_table}

用户问题: {question}

请用中文回答，简洁明了。如果数据不足以回答问题，请说明。"""

        return prompt
