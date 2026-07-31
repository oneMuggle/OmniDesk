"""P0-I office_assistant 能力收敛测试

文本处理白名单固定为 proofread / translate / polish,
且每个 action 都有对应 system prompt(无悬空项)。
"""
from office_assistant.views import ALLOWED_ACTIONS, SYSTEM_PROMPTS


class TestCapabilityScope:
    def test_allowed_actions_whitelist(self):
        assert ALLOWED_ACTIONS == ("proofread", "translate", "polish")

    def test_every_action_has_prompt(self):
        assert set(SYSTEM_PROMPTS.keys()) == set(ALLOWED_ACTIONS)

    def test_prompts_non_empty(self):
        for action in ALLOWED_ACTIONS:
            assert SYSTEM_PROMPTS[action].strip()
