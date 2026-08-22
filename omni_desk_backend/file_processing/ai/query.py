"""自然语言查询 - 通过 LLMRouter 调用 LLM 生成回答。

P1A-1 改写:不再 import ollama SDK 直连 qwen2.5:7b,改走
``llm_service.router.get_router()`` 统一中台。

收益:
- DB 端点配置 + 优先级降级链
- cost 核算(estimated_cost / endpoint_id / model_name)
- 与 chat 路径同栈,运维单点治理

``file_processing`` 当前不在 ``LlmAppConfig.APP_CHOICES``(仅注册
``smart_assistant`` 与 ``office_assistant``),因此
``get_router(app_name="file_processing")`` 走 Ollama 本地兜底链路。
如需后续单独配置,新增 APP_CHOICES 条目即可(``P1A-1+``)。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from observability import get_logger

logger = get_logger(__name__, "file_processing.ai.query")


class NaturalLanguageQuery:
    """自然语言查询 - 基于表格数据回答用户问题(走 LLMRouter)。

    与 P1A-1 之前相比:不再 import ollama SDK,改走 ``llm_service.router``。
    ``query()`` 签名从 ``str`` 改为 ``tuple[str, dict]``,对齐
    ``LLMRouter.generate()`` 返回。
    """

    APP_NAME = "file_processing"

    def __init__(self):
        # 延迟导入:避免模块加载阶段触发 router 的 DB 查询
        from llm_service.router import get_router

        self._router = get_router(app_name=self.APP_NAME)

    def _build_prompt(self, question: str, context: dict[str, Any]) -> str:
        """构建 LLM 提示(via LLMRouter,不再直连 Ollama)。

        将表格数据转换为 Markdown 格式,并构建清晰的提示文本。
        只使用前 100 行数据,避免超出 LLM 上下文限制。

        Args:
            question: 用户的自然语言问题
            context: 包含 sheets_data 的上下文字典

        Returns:
            构建完成的 LLM 提示字符串
        """
        sheets = context.get("sheets_data", [])
        if not sheets:
            return "没有表格数据可供分析。"

        sheet = sheets[0]
        # 验证数据行列匹配
        headers = sheet.get("headers", [])
        data = sheet.get("data", [])

        if not headers:
            return "表格数据格式错误：缺少列名。"

        # 限制数据量,避免内存问题
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

表格数据(Sheet: {sheet["name"]}):
{markdown_table}

用户问题: {question}

请用中文回答,简洁明了。如果数据不足以回答问题,请说明。"""

        return prompt

    def query(self, question: str, context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """用自然语言查询表格数据(走 LLMRouter)。

        Args:
            question: 用户的自然语言问题
            context: 包含 sheets_data 的上下文字典

        Returns:
            ``(content, usage)`` 元组:
            - ``content``: LLM 生成的回答文本(空数据时返回 early 消息)
            - ``usage``: 元数据字典,包含 ``model_name`` / ``endpoint_id``
              / ``estimated_cost``,正常 LLM 调用时还含 ``total_tokens``。
        """
        # 空数据:短路早期返回,不触发 LLM 调用(节省 token + cost 归零)
        if not context.get("sheets_data"):
            early_usage = {
                "model_name": self._router._resolve_ollama_model(),
                "endpoint_id": None,
                "estimated_cost": 0.0,
            }
            return ("没有表格数据可供分析。", early_usage)

        prompt = self._build_prompt(question, context)
        system_message = "你是一个数据分析助手,基于用户提供的表格数据回答问题。回答简洁准确。"

        content, usage = self._router.generate(
            prompt=prompt,
            system_message=system_message,
            stream=False,
        )
        logger.info(
            "file_processing query: tokens=%s model=%s cost=%s",
            usage.get("total_tokens"),
            usage.get("model_name"),
            usage.get("estimated_cost"),
        )
        return content, usage
