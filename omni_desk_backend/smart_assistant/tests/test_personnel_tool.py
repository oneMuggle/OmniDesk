"""PersonnelTool 单元测试。

包含 ``_mask_phone`` 字段级最小脱敏的纯函数测试,以及
``PersonnelTool.execute`` 入口的语义测试(用于在更大的
``test_tools.py:TestPersonnelTool`` 之外建立一份聚焦的回归覆盖,
保证脱敏行为不会在未来重构中意外回退)。
"""

from smart_assistant.tools.personnel_tool import _mask_phone


class TestMaskPhone:
    """``_mask_phone`` 纯函数单元测试。"""

    def test_masks_eleven_digit_chinese_mobile(self):
        """11 位手机号应保留前 3 后 4,中间替换为 ****."""
        assert _mask_phone("13800000000") == "138****0000"

    def test_returns_stars_for_short_input(self):
        """长度过短(<= 4)的输入应返回 ***."""
        assert _mask_phone("123") == "***"
        assert _mask_phone("1234") == "***"

    def test_returns_stars_for_empty_input(self):
        """空字符串 / None 应返回 ***(避免 NoneType 异常)。"""
        assert _mask_phone("") == "***"
        assert _mask_phone(None) == "***"
