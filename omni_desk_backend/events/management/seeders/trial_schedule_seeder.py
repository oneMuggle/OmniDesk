"""试验与排班 Seeder：设备、试验、时间段、排班、节假日、人员序列、公告"""
import random
from datetime import date, datetime, time, timedelta, timezone as dt_tz
from personnel.models import Personnel
from events.models import Equipment, Trial, TimeSlot, Schedule, Holiday, PersonnelSequence, LeaderSequence, Announcement
from events.management.seeders.base import BaseSeeder

EQUIPMENT_NAMES = [
    ("高温试验箱", "用于高温环境下的产品性能测试，温度范围-40°C至+150°C"),
    ("振动试验台", "模拟运输和使用过程中的振动环境，频率范围5-2000Hz"),
    ("盐雾试验箱", "用于金属材料的耐腐蚀性测试，符合GB/T 2423.17标准"),
    ("万能材料试验机", "拉伸、压缩、弯曲试验，最大载荷100kN"),
    ("精密电子天平", "精度0.01mg，用于精密称量"),
    ("光谱分析仪", "用于材料成分分析，波长范围200-800nm"),
    ("环境试验箱", "温湿度复合环境模拟，温度-70°C至+180°C"),
    ("冲击试验机", "摆锤式冲击试验，能量范围1J至50J"),
]

TRIAL_TITLES = [
    "新型复合材料耐热性测试",
    "航空发动机叶片疲劳试验",
    "电子设备电磁兼容性验证",
    "高强度螺栓拉伸性能评估",
    "防腐蚀涂层盐雾试验",
    "传感器温度漂移特性研究",
    "新能源电池充放电循环测试",
    "精密轴承寿命加速试验",
    "光学透镜透光率对比分析",
    "密封件低温性能验证",
]

CLIENTS = [
    "中国航天科技集团", "中航工业集团公司", "中国船舶重工集团", "中国电子科技集团",
    "中国兵器工业集团", "国家航天局", "中科院物理研究所", "航天科工集团",
]


class TrialScheduleSeeder(BaseSeeder):
    name = "试验与排班"
    order = 20
    models = [Equipment, Trial, TimeSlot, Schedule, Holiday, PersonnelSequence, LeaderSequence, Announcement]

    def seed(self):
        results = []

        # 设备
        equipments = []
        for name, desc in EQUIPMENT_NAMES:
            obj, _ = self.safe_get_or_create(Equipment, name=name, defaults={"description": desc})
            equipments.append(obj)
        results.append(("设备", len(equipments)))

        # 试验
        personnel = self.context.get("personnel", [])
        today = date.today()
        trials = []
        for i, title in enumerate(TRIAL_TITLES):
            status = ["planned", "in_progress", "completed", "cancelled"][i % 4]
            trial, created = self.safe_get_or_create(
                Trial,
                title=title,
                defaults={
                    "version": i + 1,
                    "client": CLIENTS[i % len(CLIENTS)],
                    "description": f"本试验旨在验证{title}的相关性能指标是否满足设计要求。",
                    "status": status,
                }
            )
            if created:
                trial.equipments.set(random.sample(equipments, min(random.randint(2, 4), len(equipments))))
                if personnel:
                    trial.responsible_persons.set(random.sample(personnel, min(random.randint(1, 3), len(personnel))))

                base_date = today + timedelta(days=i * 3 - 10)
                for j in range(random.randint(2, 4)):
                    day = base_date + timedelta(days=j * 2)
                    start = datetime.combine(day, time(8, 0), tzinfo=dt_tz.utc)
                    end = datetime.combine(day, time(17, 0), tzinfo=dt_tz.utc)
                    TimeSlot.objects.get_or_create(
                        trial=trial, start_time=start, end_time=end,
                        defaults={"description": f"第{j + 1}阶段试验"},
                    )
                trial.refresh_from_db()
            trials.append(trial)
        results.append(("试验", len(trials)))

        # 排班
        if personnel:
            sched_count = self._seed_schedules(personnel)
            results.append(("排班", sched_count))

            # 节假日
            holiday_count = self._seed_holidays()
            results.append(("节假日", holiday_count))

            # 人员序列
            self._seed_sequences(personnel)
            results.append(("人员序列", 1))
            results.append(("领导序列", 1))

        # 公告
        user = self.context.get("user")
        ann_count = self._seed_announcements(user)
        results.append(("公告", ann_count))

        self.context["equipments"] = equipments
        self.context["trials"] = trials
        return results

    def _seed_schedules(self, personnel_list):
        today = date.today()
        start = today - timedelta(days=30)
        end = today + timedelta(days=30)
        count = 0
        d = start
        while d <= end:
            if d.weekday() < 5:
                self.safe_get_or_create(
                    Schedule,
                    duty_date=d,
                    defaults={
                        "duty_person": random.choice(personnel_list),
                        "duty_leader": random.choice(personnel_list),
                    }
                )
                count += 1
            d += timedelta(days=1)
        return count

    def _seed_holidays(self):
        holidays = [
            ("元旦", date(2026, 1, 1), date(2026, 1, 3)),
            ("春节", date(2026, 2, 17), date(2026, 2, 23)),
            ("清明节", date(2026, 4, 5), date(2026, 4, 7)),
            ("劳动节", date(2026, 5, 1), date(2026, 5, 5)),
            ("端午节", date(2026, 6, 19), date(2026, 6, 21)),
            ("中秋节", date(2026, 9, 25), date(2026, 9, 27)),
            ("国庆节", date(2026, 10, 1), date(2026, 10, 7)),
        ]
        for name, s, e in holidays:
            self.safe_get_or_create(Holiday, name=name, defaults={"start_date": s, "end_date": e})
        return len(holidays)

    def _seed_sequences(self, personnel_list):
        if len(personnel_list) < 3:
            return
        ps, _ = self.safe_get_or_create(
            PersonnelSequence,
            name="常规值班序列",
            defaults={
                "sequence": [p.id for p in personnel_list[:5]],
                "holiday_sequence": [p.id for p in personnel_list[5:8]] if len(personnel_list) > 5 else [],
            }
        )
        ps.personnel.set(personnel_list[:5])
        if len(personnel_list) > 5:
            ps.holiday_personnel.set(personnel_list[5:8])

        ls, _ = self.safe_get_or_create(
            LeaderSequence,
            name="值班领导序列",
            defaults={"sequence": [p.id for p in personnel_list[:3]]},
        )
        ls.personnel.set(personnel_list[:3])

    def _seed_announcements(self, user):
        announcements = [
            ("关于2026年五一劳动节放假安排", "根据国务院办公厅通知，结合我单位实际情况，现将2026年五一劳动节放假安排通知如下：\n1. 放假时间：5月1日至5月5日，共5天。\n2. 4月26日（星期日）、5月9日（星期六）上班。\n3. 节假日期间，请各部门安排好值班工作，确保安全。"),
            ("关于开展安全生产大检查的通知", "为加强安全生产工作，防范各类事故发生，经研究决定，在全所范围内开展安全生产大检查活动。请各部门于4月30日前完成自查工作，并将自查报告报送安全部。"),
            ("2026年度试验设备校准计划", "根据年度工作计划，现发布2026年度试验设备校准计划。所有计量设备需在规定时间内完成校准，请各使用部门积极配合。"),
        ]
        for title, content in announcements:
            self.safe_get_or_create(
                Announcement,
                title=title,
                defaults={"content": content, "author": user},
            )
        return len(announcements)
