from .in_app import InAppChannel


SUPPORTED_CHANNELS = {"in_app": InAppChannel}


def resolve_channels(user, notification_type):
    """根据偏好返回所有启用渠道；空/未知配置安全回落站内。"""
    try:
        settings = user.notification_pref.channel_settings or {}
    except Exception:
        settings = {}
    channels = [
        SUPPORTED_CHANNELS[name]()
        for name, type_settings in settings.items()
        if name in SUPPORTED_CHANNELS
        and isinstance(type_settings, dict)
        and type_settings.get(notification_type)
    ]
    return channels or [InAppChannel()]


def resolve_channel(user, notification_type):
    """兼容旧调用方，返回首个已解析渠道。"""
    return resolve_channels(user, notification_type)[0]
