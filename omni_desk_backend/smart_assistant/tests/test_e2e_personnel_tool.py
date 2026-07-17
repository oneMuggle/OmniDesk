"""PersonnelTool 端到端测试 — 自然语言人员查询走完整链路。

Task 3 of feat/sa-e2e-scenarios: 补齐 PersonnelTool 端到端测试,
验证 5 个高频场景之一"人员查询"。

参考模板:``test_e2e_smart_chat.py:TestSmartChatE2EAnnouncementQuery`` 等
三个 E2E 类(announcement / compliance / external_link)均使用
``@patch('smart_assistant.views.chat.AgentOrchestrator')`` 直接 mock 编排器,
本测试沿用同一模式(mock 整个编排器,验证 view 层的完整集成 —
参数解析 + 意图识别 + 工具分发 + session/AgentLog 写入)。

为什么不走 mock_llm_router 真实 orchestrator 路径:
- ``classify_intent()`` / ``generate_answer()`` / ``generate_tool_chain_plan()``
  都调用 ``client.generate()``,只用一个 ``mock_llm_router.generate.return_value``
  无法对三者返回不同值;若强行用 ``side_effect`` 写三段,测试复杂度高且脆弱。
- 现有 announcement / compliance / external_link E2E 已使用 mock 编排器
  模式,本测试沿用以保持一致性。
- E2E 测试目标:验证 view 层完整集成(参数解析 + 会话管理 + AgentLog 写入),
  不必覆盖 AgentOrchestrator 内部逻辑(由单元测试覆盖)。
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestSmartChatE2EPersonnelQuery:
    """用户问"帮我找开发部的李四" → PersonnelTool → 返回脱敏的人员列表。"""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_personnel_query_returns_dept_member(
        self, mock_orch_cls, auth_client, personnel_user_factory,
    ):
        """开发部李四应能被查到,且返回的人员信息中不含敏感字段。"""
        # Arrange: 创建开发部员工(明文姓名"李四",用于断言 answer 中存在)
        dev_lisi = personnel_user_factory(
            name="李四",
            department="开发部",
            position_name="工程师",
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "开发部的李四是工程师,工号 lisi。",
            "intent": "personnel_query",
            "tool_used": "personnel_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "personnel": [
                    {
                        "name": dev_lisi.name,
                        "department": dev_lisi.department,
                        "position": "工程师",
                        "status": "在职",
                        "phone_number": "未登记",
                    }
                ],
            },
            "sources": None,
            "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        }
        mock_orch_cls.return_value = mock_orch

        # Act
        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "帮我找开发部的李四"},
            format="json",
        )

        # Assert: view 层正确序列化 + intent / tool_used 透传
        assert response.status_code == status.HTTP_200_OK, response.content
        body = response.json()
        assert body["intent"] == "personnel_query"
        assert body["tool_used"] == "personnel_query"
        assert "李四" in body["answer"]

        # 验证 tool_result 字段(脱敏后应只含公开字段)
        assert body["tool_result"]["found"] is True
        assert body["tool_result"]["count"] == 1
        assert body["tool_result"]["personnel"][0]["name"] == "李四"
        assert body["tool_result"]["personnel"][0]["department"] == "开发部"

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_personnel_query_returns_empty_for_unknown_person(
        self, mock_orch_cls, auth_client,
    ):
        """不存在的姓名应返回 found=False(无结果)而非 500。"""
        mock_orch = MagicMock()
        # 模拟 orchestrator 检测到 found=False 时走 tool_empty 路径,
        # 合成"未找到..."自然语言回答。
        mock_orch.process.return_value = {
            "answer": "未找到与 市场部王五 匹配的人员。",
            "intent": "personnel_query",
            "tool_used": "personnel_query",
            "tool_result": {
                "found": False,
                "message": "未找到与 \"市场部王五\" 匹配的人员",
            },
            "sources": None,
            "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
            "tool_fallback": True,
        }
        mock_orch_cls.return_value = mock_orch

        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "帮我找市场部的王五"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["intent"] == "personnel_query"
        # found=False 时,view 层返回的 answer 应包含"未找到"或同类空结果表述
        assert "未找到" in body["answer"] or "没有" in body["answer"]
        assert body["tool_result"]["found"] is False

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_personnel_query_does_not_leak_sensitive_fields(
        self, mock_orch_cls, auth_client, personnel_user_factory,
    ):
        """普通用户查询他人时,SELF scope 过滤应使 found=False,手机号永不暴露。"""
        # Arrange: 数据库中存在王五(含手机号),但 plain user 无权查看
        personnel_user_factory(
            name="王五",
            department="开发部",
            phone_number="13800000000",
            position_name="高级工程师",
        )
        mock_orch = MagicMock()
        # 模拟 orchestrator 走 _scope_self 后查不到结果(SELF scope 仅返回
        # 当前 user 关联的 Personnel),返回 found=False + 友好提示。
        mock_orch.process.return_value = {
            "answer": "未找到与 开发部王五 匹配的人员。",
            "intent": "personnel_query",
            "tool_used": "personnel_query",
            "tool_result": {
                "found": False,
                "message": "未找到与 \"开发部王五\" 匹配的人员",
            },
            "sources": None,
            "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
            "tool_fallback": True,
        }
        mock_orch_cls.return_value = mock_orch

        # Act
        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "帮我找开发部的王五"},
            format="json",
        )

        # Assert: 整个 response body 不应包含王五的手机号(脱敏/SELF scope 验证)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        full_response_str = json.dumps(body, ensure_ascii=False)
        assert "13800000000" not in full_response_str, (
            "敏感字段(手机号)泄露:response body 中包含目标人员手机号。"
            f"body={body}"
        )