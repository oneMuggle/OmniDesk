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


class TestNormalizeChangelogHeader:
    @pytest.mark.parametrize("raw,expected", [
        # 已规范
        ("0.7.0-alpha.1", "0.7.0-alpha.1"),
        ("0.5.9", "0.5.9"),
        # 去 v 前缀
        ("v0.6.0-alpha.2", "0.6.0-alpha.2"),
        ("V0.4.0", "0.4.0"),
        # 中文/英文后缀保留语义(0.5.9 修复 与 0.5.9 是不同 release)
        ("0.5.9 修复", None),
        ("0.4.0 hotfix", None),
        ("0.6.0-rc.5 release", None),
        # 空白处理
        ("  0.6.0-beta.1  ", "0.6.0-beta.1"),
        # 非版本
        ("渠道机制引入", None),
        ("未发布", None),
        ("", None),
        ("v", None),
        ("1.2", None),
        # 复合:有 v 前缀 + 后缀
        ("v0.5.0-rc.1 hotfix", None),
    ])
    def test_normalize(self, raw, expected):
        from core.version_utils import normalize_changelog_header
        assert normalize_changelog_header(raw) == expected

    def test_non_string_returns_none(self):
        from core.version_utils import normalize_changelog_header
        assert normalize_changelog_header(None) is None
        assert normalize_changelog_header(123) is None


class TestRankTuple:
    """`_rank_tuple` 必须与 `compare_versions` 在所有 SemVer 排序规则下同向."""

    @pytest.mark.parametrize("a,b", [
        # stable vs stable
        ("1.2.4", "1.2.3"),
        ("1.3.0", "1.2.9"),
        ("2.0.0", "1.99.99"),
        # stable > pre-release
        ("1.2.0", "1.2.0-rc.2"),
        ("1.2.0", "1.2.0-beta.1"),
        ("1.2.0", "1.2.0-alpha.99"),
        # channel ordering
        ("1.2.0-rc.1", "1.2.0-beta.1"),
        ("1.2.0-beta.1", "1.2.0-alpha.1"),
        # same channel, different seq
        ("1.2.0-alpha.2", "1.2.0-alpha.1"),
        ("1.2.0-beta.3", "1.2.0-beta.2"),
    ])
    def test_rank_agrees_with_compare(self, a, b):
        from core.version_utils import _rank_tuple, try_parse_version
        pa, pb = try_parse_version(a), try_parse_version(b)
        assert pa is not None and pb is not None
        assert _rank_tuple(pa) > _rank_tuple(pb)
        assert _rank_tuple(pb) < _rank_tuple(pa)
        # 与 compare_versions 同向
        assert compare_versions(a, b) == 1
        assert compare_versions(b, a) == -1

    @pytest.mark.parametrize("version,expected_rank", [
        ("1.2.0-alpha.3", (1, 2, 0, 0, 3)),
        ("1.2.0", (1, 2, 0, 3, 0)),
        ("1.2.0-rc.5", (1, 2, 0, 2, 5)),
        ("0.0.1-alpha.1", (0, 0, 1, 0, 1)),
    ])
    def test_rank_format(self, version, expected_rank):
        from core.version_utils import _rank_tuple
        assert _rank_tuple(parse_version(version)) == expected_rank
