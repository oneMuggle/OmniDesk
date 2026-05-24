"""排班生成服务模块。

将排班生成的核心算法从 ScheduleViewSet 中分离，便于测试和复用。
"""
import calendar
from datetime import datetime, timedelta

from django.db import transaction
from rest_framework.exceptions import ValidationError

from personnel.models import Personnel


class ScheduleGenerator:
    """根据人员顺序、领导顺序和日期范围自动生成排班。"""

    def __init__(
        self,
        workday_sequence,
        leader_sequence,
        start_date,
        duration_days,
        holiday_sequence=None,
        start_personnel_id=None,
        start_holiday_personnel_id=None,
        start_leader_id=None,
    ):
        self.workday_sequence = workday_sequence
        self.leader_sequence = leader_sequence
        self.holiday_sequence = holiday_sequence
        self.start_date = start_date
        self.duration_days = duration_days
        self.start_personnel_id = start_personnel_id
        self.start_holiday_personnel_id = start_holiday_personnel_id
        self.start_leader_id = start_leader_id

    def generate(self):
        """生成排班列表并保存到数据库。

        返回 (schedules, start_date, end_date)。
        """
        # 1. 提取并清洗 ID 列表
        workday_ids = self._clean_sequence(self.workday_sequence.sequence)
        leader_ids = self._clean_sequence(self.leader_sequence.sequence)

        if self.holiday_sequence and self.holiday_sequence.sequence:
            holiday_ids = self._clean_sequence(self.holiday_sequence.sequence)
        else:
            holiday_ids = workday_ids

        if not workday_ids or not leader_ids:
            raise ValidationError('排班序列不能为空')

        # 2. 验证所有人员 ID 有效
        all_ids = set(workday_ids) | set(leader_ids) | set(holiday_ids)
        existing_ids = set(
            Personnel.objects.select_for_update()
            .filter(id__in=all_ids)
            .values_list('id', flat=True)
        )
        missing = all_ids - existing_ids
        if missing:
            raise ValidationError(
                f'排班序列中的部分人员ID无效，请检查配置: {", ".join(map(str, sorted(missing)))}'
            )

        # 3. 计算日期范围
        end_date = self.start_date + timedelta(days=self.duration_days - 1)

        # 4. 收集节假日
        from .models import Holiday
        holidays = Holiday.objects.filter(start_date__lte=end_date, end_date__gte=self.start_date)
        holiday_dates = self._expand_holidays(holidays, self.start_date, end_date)

        # 5. 计算起始索引
        workday_idx = self._find_index(workday_ids, self.start_personnel_id, 'workday')
        holiday_idx = self._find_index(holiday_ids, self.start_holiday_personnel_id, 'holiday')
        leader_idx = self._find_index(leader_ids, self.start_leader_id, 'leader')

        # 6. 生成排班
        schedules = []
        workday_count = 0
        holiday_count = 0

        for i in range(self.duration_days):
            current_date = self.start_date + timedelta(days=i)
            is_holiday = current_date in holiday_dates or current_date.weekday() >= 5

            if is_holiday:
                if not holiday_ids:
                    raise ValidationError('节假日日期需要配置节假日人员序列')
                personnel_id = holiday_ids[(holiday_idx + holiday_count) % len(holiday_ids)]
                holiday_count += 1
            else:
                personnel_id = workday_ids[(workday_idx + workday_count) % len(workday_ids)]
                workday_count += 1

            weeks_passed = (current_date - self.start_date).days // 7
            leader_id = leader_ids[(leader_idx + weeks_passed) % len(leader_ids)]

            from .models import Schedule
            schedules.append(
                Schedule(
                    duty_date=current_date,
                    duty_person_id=personnel_id,
                    duty_leader_id=leader_id,
                )
            )

        # 7. 删除原排班并批量创建
        from .models import Schedule
        Schedule.objects.filter(duty_date__gte=self.start_date, duty_date__lte=end_date).delete()
        Schedule.objects.bulk_create(schedules)

        return list(
            Schedule.objects.filter(duty_date__gte=self.start_date, duty_date__lte=end_date)
        ), self.start_date, end_date

    @staticmethod
    def _clean_sequence(raw_sequence):
        """清洗序列数据，过滤无效条目。"""
        return [int(pid) for pid in raw_sequence if pid is not None and str(pid).strip().isdigit()]

    @staticmethod
    def _expand_holidays(holidays, start_date, end_date):
        """将节假日展开为日期集合。"""
        holiday_dates = set()
        for holiday in holidays:
            current_day = holiday.start_date
            while current_day <= holiday.end_date:
                if start_date <= current_day <= end_date:
                    holiday_dates.add(current_day)
                current_day += timedelta(days=1)
        return holiday_dates

    @staticmethod
    def _find_index(id_list, target_id, label):
        """在序列中查找目标的起始索引。"""
        if not target_id:
            return 0
        try:
            target_int = int(target_id)
        except (ValueError, TypeError):
            raise ValidationError({f'start_{label}_id': f'起始{label}人员ID必须为整数'})
        try:
            return id_list.index(target_int)
        except ValueError:
            raise ValidationError({f'start_{label}_id': f'起始{label}人员ID不在序列中'})
