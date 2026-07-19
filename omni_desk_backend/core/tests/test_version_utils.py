"""version_utils 单元测试."""

import pytest

from core.version_utils import (
    CHANNELS,
    ParsedVersion,
    compare_versions,
    derive_channel_from_branch,
    format_version,
    parse_version,
)


class TestParseVersion:
    def test_plain_stable(self):
        result = parse_version("1.2.3")
        assert result == ParsedVersion(1, 2, 3, None, None)

    def test_alpha(self):
        result = parse_version("1.2.3-alpha.1")
        assert result == ParsedVersion(1, 2, 3, "alpha", 1)

    def test_beta(self):
        result = parse_version("0.5.9-beta.3")
        assert result == ParsedVersion(0, 5, 9, "beta", 3)

    def test_rc(self):
        result = parse_version("1.2.0-rc.2")
        assert result == ParsedVersion(1, 2, 0, "rc", 2)

    @pytest.mark.parametrize("bad", ["1.2", "v1.2.3", "1.2.3-alpha", "1.2.3-rc", "1.2.3-alpha.x"])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_version(bad)


class TestFormatVersion:
    def test_stable(self):
        assert format_version(1, 2, 3, None, None) == "1.2.3"

    def test_alpha(self):
        assert format_version(1, 2, 3, "alpha", 1) == "1.2.3-alpha.1"

    def test_channel_without_num_raises(self):
        with pytest.raises(ValueError):
            format_version(1, 2, 3, "alpha", None)


class TestDeriveChannelFromBranch:
    @pytest.mark.parametrize("branch,expected", [
        ("main", "alpha"),
        ("beta", "beta"),
        ("rc", "preview"),
        ("release", "stable"),
        ("feat/foo", "none"),
        ("fix/bar", "none"),
        ("main-1.2", "none"),  # 防止前缀误匹配
    ])
    def test_branches(self, branch, expected):
        assert derive_channel_from_branch(branch) == expected


class TestCompareVersions:
    def test_stable_vs_stable(self):
        assert compare_versions("1.2.3", "1.2.3") == 0
        assert compare_versions("1.2.4", "1.2.3") == 1
        assert compare_versions("1.2.3", "1.2.4") == -1

    def test_stable_higher_than_rc(self):
        assert compare_versions("1.2.0", "1.2.0-rc.2") == 1

    def test_rc_higher_than_beta(self):
        assert compare_versions("1.2.0-rc.1", "1.2.0-beta.3") == 1

    def test_alpha_lowest(self):
        assert compare_versions("1.2.0-alpha.1", "1.2.0") == -1

    def test_same_channel_seq(self):
        assert compare_versions("1.2.0-alpha.2", "1.2.0-alpha.1") == 1


class TestTryParseVersion:
    def test_valid_stable(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("1.2.3") == ParsedVersion(1, 2, 3, None, None)

    def test_valid_alpha(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("0.6.0-alpha.2") == ParsedVersion(0, 6, 0, "alpha", 2)

    def test_valid_beta(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("0.5.9-beta.3") == ParsedVersion(0, 5, 9, "beta", 3)

    def test_valid_rc(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("1.2.0-rc.2") == ParsedVersion(1, 2, 0, "rc", 2)

    def test_strips_whitespace(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("  0.5.9  ") == ParsedVersion(0, 5, 9, None, None)

    def test_invalid_returns_none(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("v1.2.3") is None  # 前导 'v' 仍被拒绝(契约不变)

    def test_chinese_returns_none(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("渠道机制引入") is None

    def test_non_string_returns_none(self):
        from core.version_utils import try_parse_version
        assert try_parse_version(None) is None
        assert try_parse_version(123) is None
