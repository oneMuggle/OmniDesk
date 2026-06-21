"""Agent 角色体系单元测试

覆盖 agents/roles.py 的所有公开接口:
- AgentRole 枚举完整性
- RoleProfile 字段校验
- ROLE_PROFILES 注册表
- get_profile / list_roles / get_role_by_name 工具函数
"""

import pytest

from smart_assistant.agents.roles import (
    ROLE_PROFILES,
    AgentRole,
    RoleProfile,
    get_profile,
    get_role_by_name,
    list_roles,
)


class TestAgentRoleEnum:
    """AgentRole 枚举测试"""

    def test_all_expected_roles_exist(self):
        """验证所有 11 个预期角色都已定义"""
        expected = {
            "SUPERVISOR", "SYNTHESIZER",
            "RESEARCHER", "ANALYST", "VISUALIZER",
            "WRITER", "EDITOR",
            "CODER", "TESTER", "REVIEWER",
            "GENERAL",
        }
        actual = {r.name for r in AgentRole}
        assert actual == expected

    def test_role_values_are_strings(self):
        """验证所有角色值都是小写字符串"""
        for role in AgentRole:
            assert isinstance(role.value, str)
            assert role.value == role.value.lower()

    def test_role_string_representation(self):
        """验证 AgentRole 继承 str,可直接作为字符串使用"""
        role = AgentRole.RESEARCHER
        assert str(role) == "AgentRole.RESEARCHER"
        assert role.value == "researcher"
        # 可用于字典键、集合成员等
        assert {role} == {AgentRole.RESEARCHER}


class TestRoleProfiles:
    """ROLE_PROFILES 注册表测试"""

    def test_all_roles_registered(self):
        """验证每个 AgentRole 都有对应的 RoleProfile"""
        for role in AgentRole:
            assert role in ROLE_PROFILES, f"角色 {role} 未在 ROLE_PROFILES 中注册"

    def test_profile_count_matches_role_count(self):
        """验证注册表数量与角色数量一致"""
        assert len(ROLE_PROFILES) == len(AgentRole)

    def test_profile_role_field_matches_key(self):
        """验证每个 profile 的 role 字段与注册表 key 一致"""
        for role, profile in ROLE_PROFILES.items():
            assert profile.role == role

    def test_all_profiles_have_required_fields(self):
        """验证每个 profile 的必要字段都已填充"""
        for role, profile in ROLE_PROFILES.items():
            assert profile.display_name, f"{role} 缺少 display_name"
            assert profile.system_prompt, f"{role} 缺少 system_prompt"
            assert isinstance(profile.allowed_tools, list), f"{role} 的 allowed_tools 不是 list"
            assert isinstance(profile.max_tokens, int) and profile.max_tokens > 0, (
                f"{role} 的 max_tokens 必须为正整数"
            )
            assert isinstance(profile.temperature, float) and 0 <= profile.temperature <= 2, (
                f"{role} 的 temperature 必须在 [0, 2] 范围内"
            )
            assert isinstance(profile.quality_criteria, list), f"{role} 的 quality_criteria 不是 list"

    def test_supervisor_profile_json_contract(self):
        """验证 SUPERVISOR 的 output_contract 包含必需字段"""
        profile = ROLE_PROFILES[AgentRole.SUPERVISOR]
        assert "properties" in profile.output_contract
        required = {"objective", "execution_mode", "subtasks"}
        assert required.issubset(profile.output_contract["properties"].keys())

    def test_supervisor_low_temperature(self):
        """验证 SUPERVISOR 使用低温度(保证 JSON 结构稳定)"""
        profile = ROLE_PROFILES[AgentRole.SUPERVISOR]
        assert profile.temperature <= 0.5

    def test_worker_roles_have_system_prompts_in_chinese(self):
        """验证所有 Worker 角色的 system_prompt 是中文"""
        worker_roles = [
            AgentRole.RESEARCHER, AgentRole.ANALYST, AgentRole.VISUALIZER,
            AgentRole.WRITER, AgentRole.EDITOR, AgentRole.CODER,
            AgentRole.TESTER, AgentRole.REVIEWER,
        ]
        chinese_chars = "的你是"  # 简单检测,中文高频字
        for role in worker_roles:
            prompt = ROLE_PROFILES[role].system_prompt
            assert any(c in prompt for c in chinese_chars), (
                f"{role} 的 system_prompt 应包含中文"
            )

    def test_researcher_allowed_tools(self):
        """验证 RESEARCHER 角色绑定的工具列表"""
        profile = ROLE_PROFILES[AgentRole.RESEARCHER]
        expected_tools = {"rag_tool", "document_tool", "news_tool", "external_link_tool"}
        assert set(profile.allowed_tools) == expected_tools

    def test_general_role_has_broad_tools(self):
        """验证 GENERAL 角色有广泛的工具访问(兜底)"""
        profile = ROLE_PROFILES[AgentRole.GENERAL]
        assert len(profile.allowed_tools) >= 5


class TestGetProfile:
    """get_profile() 工具函数测试"""

    def test_get_existing_role(self):
        """查询已注册角色返回对应的 RoleProfile"""
        profile = get_profile(AgentRole.WRITER)
        assert isinstance(profile, RoleProfile)
        assert profile.role == AgentRole.WRITER
        assert profile.display_name == "撰写专家"

    def test_get_unknown_role_raises_key_error(self):
        """查询未注册角色抛出 KeyError"""
        # 伪造一个未注册的枚举值(通过字符串绕过)
        with pytest.raises(KeyError):
            get_profile("unknown_role")

    def test_get_profile_returns_frozen_instance(self):
        """返回的 RoleProfile 是 frozen dataclass,不可修改"""
        profile = get_profile(AgentRole.ANALYST)
        with pytest.raises(AttributeError):
            profile.display_name = "新名字"  # type: ignore[misc]


class TestListRoles:
    """list_roles() 工具函数测试"""

    def test_returns_all_roles(self):
        """返回所有已注册角色"""
        roles = list_roles()
        assert set(roles) == set(AgentRole)
        assert len(roles) == len(AgentRole)

    def test_returns_list_not_iterator(self):
        """返回的是 list,可多次迭代"""
        roles = list_roles()
        assert isinstance(roles, list)
        assert len(roles) == len(list(roles))  # 可重复遍历


class TestGetRoleByName:
    """get_role_by_name() 工具函数测试"""

    def test_uppercase_name(self):
        """大写名称可查询"""
        assert get_role_by_name("RESEARCHER") == AgentRole.RESEARCHER

    def test_lowercase_name(self):
        """小写名称可查询(大小写不敏感)"""
        assert get_role_by_name("researcher") == AgentRole.RESEARCHER

    def test_mixed_case_name(self):
        """混合大小写可查询"""
        assert get_role_by_name("ReSeArChEr") == AgentRole.RESEARCHER

    def test_all_roles_queryable_by_value(self):
        """所有角色都可以通过其 value 字符串查询到"""
        for role in AgentRole:
            assert get_role_by_name(role.value) == role

    def test_unknown_name_returns_none(self):
        """未知名称返回 None(不抛异常)"""
        assert get_role_by_name("nonexistent") is None
        assert get_role_by_name("") is None
