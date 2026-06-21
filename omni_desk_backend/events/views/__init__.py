"""events.views — 事件模块视图包

Phase 3 优化:将原 791 行 events/views.py 拆分为子模块。
本文件重新导出所有 ViewSet,保持 events/urls.py 的导入路径不变。

子模块:
- schedules: ScheduleViewSet, MyScheduleView
- trials: TrialViewSet, EquipmentViewSet, TimeSlotViewSet
- announcements: AnnouncementViewSet, ImageUploadView
- sequences: PersonnelSequenceViewSet, LeaderSequenceViewSet, HolidayViewSet
- swap: SwapRequestViewSet
"""

from .announcements import AnnouncementViewSet, ImageUploadView
from .schedules import MyScheduleView, ScheduleViewSet
from .sequences import HolidayViewSet, LeaderSequenceViewSet, PersonnelSequenceViewSet
from .swap import SwapRequestViewSet
from .trials import EquipmentViewSet, TimeSlotViewSet, TrialViewSet

__all__ = [
    "AnnouncementViewSet",
    "EquipmentViewSet",
    "HolidayViewSet",
    "ImageUploadView",
    "LeaderSequenceViewSet",
    "MyScheduleView",
    "PersonnelSequenceViewSet",
    "ScheduleViewSet",
    "SwapRequestViewSet",
    "TimeSlotViewSet",
    "TrialViewSet",
]
