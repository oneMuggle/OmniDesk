"""PiiMaskingHook PII 脱敏钩子(Phase 2 落地)

对工具返回结果(post_execute 阶段)中的个人敏感信息做掩码:

- 手机号(11 位,``1[3-9]\\d{9}``)→ ``138****1234``(前 3 后 4)
- 身份证号(18 位,末位可为 X/x)→ ``110101********1234``(前 6 后 4)
- 邮箱 → ``zha****@example.com``(local 部分保留前 3 位;过短保留第 1 位)

设计要点
========

- **可开关**:构造参数 ``enabled`` 优先;未显式指定时每次执行从 settings
  ``SMART_ASSISTANT_PII_MASKING`` 动态读取(默认 True,getattr 兜底),
  便于运行时配置与测试 override。
- **递归遍历**:工具返回值可能是嵌套的 dict / list / tuple / str,
  递归深入逐层掩码;非字符串标量(数字/布尔/None)原样透传。
- **匹配顺序**:先邮箱 → 再身份证 → 最后手机号。身份证先于手机号掩码,
  可避免 18 位数字中的 11 位子串被误判为手机号(另有数字边界断言兜底)。
- **不可变**:掩码过程生成新容器,不原地修改入参(符合项目不可变约定,
  也保证 HookRegistry 的 ``new_result != current_result`` 比较可靠)。

与工具级脱敏的关系
==================

``PersonnelTool._mask_phone`` 等字段级脱敏是 Phase 1 的临时方案;
本 Hook 是 Phase 2 的统一出口脱敏,接入生产钩子链后工具级脱敏可逐步移除。
两者并存时双重掩码是幂等安全的("138****1234" 不再匹配完整号码正则)。

Example:
    from smart_assistant.hooks import HookEvent, get_registry
    from smart_assistant.hooks.builtin.pii_masking import PiiMaskingHook

    registry = get_registry()
    # 优先级低于审计(先审计原文,再脱敏输出)
    registry.register(HookEvent.POST_EXECUTE, PiiMaskingHook(), priority=5)
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings

from ..base import ToolHookBase

# settings 配置项名称(集中定义,避免散落字符串)
SETTING_ENABLED = "SMART_ASSISTANT_PII_MASKING"

# ---------------------------------------------------------------------------
# 正则定义
# ---------------------------------------------------------------------------
# 边界断言 (?<!\d) / (?!\d) 防止从长数字串中截取误报(如订单号、ID 内嵌片段)。

# 手机号:1 开头,第 2 位 3-9,共 11 位数字
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

# 身份证号:18 位,结构为 6 位地区码 + 8 位出生日期(18/19/20 年) + 3 位顺序码
# + 1 位校验码(数字或 X/x)。收紧生日段(月 01-12、日 01-31)以降低误报。
_ID_CARD_RE = re.compile(
    r"(?<!\d)"
    r"[1-9]\d{5}"  # 地区码(首位非 0)
    r"(?:18|19|20)\d{2}"  # 出生年
    r"(?:0[1-9]|1[0-2])"  # 出生月
    r"(?:0[1-9]|[12]\d|3[01])"  # 出生日
    r"\d{3}"  # 顺序码
    r"[\dXx]"  # 校验码
    r"(?![\dXx])"
)

# 邮箱:常规字符集 + 域名至少一个点
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


# ---------------------------------------------------------------------------
# 掩码函数
# ---------------------------------------------------------------------------


def mask_phone(phone: str) -> str:
    """手机号掩码:保留前 3 后 4,如 138****1234"""
    return f"{phone[:3]}****{phone[-4:]}"


def mask_id_card(id_card: str) -> str:
    """身份证掩码:保留前 6 后 4,如 110101********1234(长度保持 18)"""
    return f"{id_card[:6]}{'*' * 8}{id_card[-4:]}"


def mask_email(email: str) -> str:
    """邮箱掩码:local 部分保留前 3 位(过短保留第 1 位),域名完整保留

    Examples:
        zhangsan@example.com → zha****@example.com
        ab@x.com             → a***@x.com
    """
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = f"{local[:1]}***"
    else:
        masked_local = f"{local[:3]}****"
    return f"{masked_local}@{domain}"


def mask_text(text: str) -> str:
    """对一段文本做全量 PII 掩码(邮箱 → 身份证 → 手机号)"""
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    text = _ID_CARD_RE.sub(lambda m: mask_id_card(m.group(0)), text)
    text = _PHONE_RE.sub(lambda m: mask_phone(m.group(0)), text)
    return text


def mask_value(value: Any) -> Any:
    """递归掩码任意结构中的字符串

    - str → mask_text
    - dict → 新 dict(键不动,值递归)
    - list / tuple → 同类型新容器(元素递归)
    - 其他标量(int/float/bool/None 等)→ 原样返回
    """
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_value(item) for item in value)
    return value


# ---------------------------------------------------------------------------
# Hook 实现
# ---------------------------------------------------------------------------


class PiiMaskingHook(ToolHookBase):
    """PII 脱敏 Hook(post_execute 阶段对工具输出掩码)

    Attributes:
        name: Hook 名称(固定为 "pii_masking")
        _enabled: 显式开关;None 表示每次从 settings 动态读取
    """

    name: str = "pii_masking"

    def __init__(self, enabled: bool | None = None) -> None:
        """初始化 PII 脱敏 Hook

        Args:
            enabled: 显式开关。None(默认)表示 post_execute 每次从 settings
                ``SMART_ASSISTANT_PII_MASKING`` 读取(默认 True),支持运行时
                切换与测试 override。
        """
        self._enabled: bool | None = None if enabled is None else bool(enabled)

    @property
    def enabled(self) -> bool:
        """当前是否启用:显式值优先,否则读 settings(getattr 兜底默认 True)"""
        if self._enabled is not None:
            return self._enabled
        return bool(getattr(settings, SETTING_ENABLED, True))

    async def post_execute(self, tool: Any, result: Any, ctx: Any) -> Any:
        """对工具返回结果递归掩码;关闭时原样透传

        Args:
            tool: 执行完成的工具实例
            result: 工具返回值(任意可 JSON 化的结构)
            ctx: 当前上下文

        Returns:
            掩码后的新结果(关闭或未命中任何模式时与原值相等)
        """
        if not self.enabled:
            return result
        return mask_value(result)
