from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"
    verbose_name = "排班与试验管理"

    def ready(self):
        # SP3: 注册 ScheduleSwapRequest 信号
        import events.signals  # noqa: F401
