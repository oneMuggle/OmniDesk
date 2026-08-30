from .in_app import InAppChannel


SUPPORTED_CHANNELS = {"in_app": InAppChannel}


def resolve_channel(user, notification_type):
    """根据偏好选择已实现渠道；未知/空配置安全回落站内。"""
    try:
        preference = user.notification_pref
        settings = preference.channel_settings or {}
    except Exception:
        settings = {}
    for name, type_settings in settings.items():
        if name in SUPPORTED_CHANNELS and isinstance(type_settings, dict) and type_settings.get(notification_type):
            return SUPPORTED_CHANNELS[name]()
    return InAppChannel()
