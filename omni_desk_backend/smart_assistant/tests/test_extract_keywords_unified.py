"""R5-D2 BaseTool.extract_keywords 统一 — 行为等价性与接口测试。

重构前:6 个查询工具各自定义静态 ``_extract_keywords``(replace 链),
基类 ``extract_keywords`` 返回 list 且无人使用。

重构后:
- 基类提供唯一实现 ``extract_keywords(query) -> str``;
- 指令词(command_words)默认 ``("搜索", "查找")``,子类可整体置空;
- 领域停用词(stopwords)由各子类以**有序元组**声明(替换顺序敏感,
  必须与旧 replace 链同序,保证任意输入逐字等价);
- 各工具旧的 ``_extract_keywords`` 静态方法删除。

本文件的核心是 ``TestLegacyEquivalence``:以重构前的 replace 链为 oracle,
对代表性输入(含顺序敏感的交叉词输入)逐一断言新实现输出与旧链完全一致。
"""

import typing

import pytest

from smart_assistant.tools.base import BaseTool
from smart_assistant.tools.document_tool import DocumentTool
from smart_assistant.tools.memo_tool import MemoTool
from smart_assistant.tools.news_tool import NewsTool
from smart_assistant.tools.personnel_tool import PersonnelTool
from smart_assistant.tools.project_tool import ProjectTool
from smart_assistant.tools.sensor_tool import SensorTool

ALL_TOOLS = [DocumentTool, MemoTool, NewsTool, ProjectTool, PersonnelTool, SensorTool]


class _BareTool(BaseTool):
    """未覆盖任何词表属性的裸 BaseTool 子类(验证基类默认行为)."""

    name = "bare_test_tool"
    description = "测试用最小工具"
    intent_type = "bare_test"

    def execute(self, query: str, context=None) -> dict:
        return {"found": True}


class _CustomWordsTool(BaseTool):
    """覆盖 stopwords 与 command_words 的自定义子类."""

    name = "custom_words_tool"
    description = "测试用自定义词表工具"
    intent_type = "custom_words"
    command_words = ("帮我",)
    stopwords = ("日程", "会议")

    def execute(self, query: str, context=None) -> dict:
        return {"found": True}


# =============================================================================
# 重构前各工具 _extract_keywords 的 replace 链(等价性 oracle)
# =============================================================================

#: 与重构前各工具静态方法完全一致的替换序列(顺序不可变)
_LEGACY_CHAINS = {
    DocumentTool: ("搜索", "查找", "文档", "公文"),
    MemoTool: ("搜索", "查找", "备忘录", "便签"),
    NewsTool: ("搜索", "查找", "新闻", "通知"),
    ProjectTool: ("搜索", "查找", "项目"),
    PersonnelTool: ("谁", "是", "的"),
    SensorTool: ("搜索", "查找", "传感器", "设备"),
}

# 代表性输入:常规 query、纯停用词、领域词交叉(顺序敏感)、空白、空串
_EQUIVALENCE_INPUTS = [
    "",
    "搜索",
    "查找",
    "帮我搜索备忘录xxx",
    "搜索备忘录xxx",
    "查找张三的文档",
    "查设备验收模板",
    "搜索最近的公文",
    "搜查找索",  # 顺序敏感:'查找' 先于 '搜索' 替换会得到不同结果
    "搜索查找",
    "备忘录便签",
    "新闻通知",
    "传感器设备",
    "设备传感器",  # 反向交叉
    "项目项目",
    "谁是的",
    "是谁的人",
    "研发部有哪些人",
    "查温湿度传感器",
    "所有在校传感器统计",
    "找一下会议纪要",
    "搜索本周的便签",
    "最近的培训通知",
    "本周项目进度",
    "  前后空白  ",
    "搜索  中间 空格 ",
    "公文文档混合词",
]


def _legacy_clean(query: str, words: tuple) -> str:
    """按重构前的 replace 链逐词清洗(oracle 实现)."""
    text = query
    for word in words:
        text = text.replace(word, "")
    return text.strip()


# =============================================================================
# 基类默认行为
# =============================================================================


class TestBaseDefaultBehavior:
    """BaseTool 默认实现:无 stopwords 时只剥指令词."""

    def test_returns_str_type(self):
        result = _BareTool().extract_keywords("搜索天气")

        assert isinstance(result, str)

    def test_default_strips_command_words_only(self):
        """裸子类(未声明 stopwords)只剥离默认指令词 搜索/查找."""
        tool = _BareTool()

        assert tool.extract_keywords("搜索天气预报") == "天气预报"
        assert tool.extract_keywords("查找会议纪要") == "会议纪要"

    def test_default_keeps_domain_words(self):
        """裸子类不剥离领域词('备忘录' 等应保留)."""
        assert _BareTool().extract_keywords("备忘录列表") == "备忘录列表"

    def test_empty_string_returns_empty_string(self):
        assert _BareTool().extract_keywords("") == ""

    def test_strips_surrounding_whitespace(self):
        assert _BareTool().extract_keywords("  搜索 天气  ") == "天气"

    def test_custom_stopwords_override(self):
        """子类覆盖 stopwords 后领域词被剥离."""
        tool = _CustomWordsTool()

        assert tool.extract_keywords("查看今日日程安排") == "查看今日安排"

    def test_custom_command_words_override(self):
        """子类覆盖 command_words 后默认指令词不再剥离."""
        tool = _CustomWordsTool()

        # '搜索' 不再是指令词,保留在结果中;'帮我' 被剥离
        assert tool.extract_keywords("帮我搜索日程") == "搜索"

    def test_repeated_occurrences_all_removed(self):
        """同一停用词出现多次全部移除(replace 链语义)."""
        assert _BareTool().extract_keywords("搜索搜索天气") == "天气"


# =============================================================================
# 各子类 stopwords 生效
# =============================================================================


class TestPerToolStopwords:
    """每个子类的领域停用词生效(brief 指定场景:memo 输入 '搜索备忘录xxx' → 'xxx')."""

    def test_memo_tool(self):
        assert MemoTool().extract_keywords("搜索备忘录xxx") == "xxx"
        assert MemoTool().extract_keywords("查找便签内容") == "内容"

    def test_document_tool(self):
        assert DocumentTool().extract_keywords("查找公文模板") == "模板"
        assert DocumentTool().extract_keywords("搜索文档验收单") == "验收单"

    def test_news_tool(self):
        assert NewsTool().extract_keywords("搜索新闻头条") == "头条"
        assert NewsTool().extract_keywords("查找通知详情") == "详情"

    def test_sensor_tool(self):
        assert SensorTool().extract_keywords("查找传感器温度") == "温度"
        assert SensorTool().extract_keywords("搜索设备台账") == "台账"

    def test_project_tool(self):
        assert ProjectTool().extract_keywords("搜索项目进度") == "进度"

    def test_personnel_tool_keeps_legacy_word_list(self):
        """PersonnelTool 旧链只剥 谁/是/的,不剥 搜索/查找(行为等价的关键差异点)."""
        tool = PersonnelTool()

        assert tool.extract_keywords("谁是张三") == "张三"
        assert tool.extract_keywords("搜索张三") == "搜索张三"  # 指令词保留


# =============================================================================
# 返回类型
# =============================================================================


class TestReturnType:
    """统一签名:str -> str(不再是 list)."""

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS + [_BareTool])
    def test_all_tools_return_str(self, tool_cls):
        result = tool_cls().extract_keywords("搜索示例关键词")

        assert isinstance(result, str)

    def test_base_annotation_is_str(self):
        hints = typing.get_type_hints(BaseTool.extract_keywords)

        assert hints.get("return") is str


# =============================================================================
# 行为等价性(核心保障):新实现输出必须与重构前 replace 链逐字一致
# =============================================================================


class TestLegacyEquivalence:
    """以重构前各工具 _extract_keywords 为 oracle 的全量等价断言."""

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS)
    @pytest.mark.parametrize("query", _EQUIVALENCE_INPUTS)
    def test_matches_legacy_replace_chain(self, tool_cls, query):
        expected = _legacy_clean(query, _LEGACY_CHAINS[tool_cls])
        actual = tool_cls().extract_keywords(query)

        assert actual == expected, (
            f"{tool_cls.__name__}.extract_keywords({query!r}) ={actual!r}, 期望(旧链)={expected!r}"
        )

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS)
    def test_old_static_method_removed(self, tool_cls):
        """收敛要求:旧的 _extract_keywords 静态方法已删除."""
        assert not hasattr(tool_cls, "_extract_keywords")
