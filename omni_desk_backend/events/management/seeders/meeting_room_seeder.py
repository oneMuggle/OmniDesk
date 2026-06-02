"""会议室 Seeder：会议室、预约、维护"""

import random
from datetime import date, datetime, timedelta, timezone as dt_tz
from meeting_rooms.models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance
from events.management.seeders.base import BaseSeeder


class MeetingRoomSeeder(BaseSeeder):
    name = "会议室管理"
    order = 30
    models = [MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance]

    def seed(self):
        user = self.context.get("user")
        rooms_data = [
            ("A101 第一会议室", "一楼东侧，配备投影仪和白板", 20, "一楼东侧"),
            ("B201 第二会议室", "二楼北侧，配备视频会议系统", 10, "二楼北侧"),
            ("C301 第三会议室", "三楼中央，小型讨论室", 6, "三楼中央"),
            ("D401 培训室", "四楼西侧，配备音响和投影", 40, "四楼西侧"),
            ("E501 高管会议室", "五楼，配备智能会议系统", 15, "五楼"),
        ]

        rooms = []
        for name, desc, capacity, location in rooms_data:
            obj, _ = self.safe_get_or_create(
                MeetingRoom,
                name=name,
                defaults={"description": desc, "capacity": capacity, "location": location},
            )
            rooms.append(obj)

        # 预约（未来7天内）
        booking_count = 0
        if user:
            today = date.today()
            booking_titles = [
                "项目周例会",
                "技术方案评审",
                "客户来访接待",
                "月度工作总结",
                "新员工培训",
                "安全生产会议",
                "设备校准讨论",
                "质量问题分析",
                "年度计划讨论",
                "部门协调会议",
            ]
            for i in range(len(booking_titles)):
                room = rooms[i % len(rooms)]
                day = today + timedelta(days=i % 7)
                hour = 9 + (i % 8)
                start_dt = datetime.combine(day, datetime.min.time().replace(hour=hour), tzinfo=dt_tz.utc)
                end_dt = start_dt + timedelta(hours=1)
                try:
                    MeetingRoomBooking.objects.get_or_create(
                        meeting_room=room,
                        user=user,
                        start_time=start_dt,
                        end_time=end_dt,
                        defaults={
                            "title": booking_titles[i],
                            "participants": "张三, 李四, 王五",
                            "description": f"{booking_titles[i]}的定期会议",
                        },
                    )
                    booking_count += 1
                except Exception:
                    pass

        # 维护记录
        for i, room in enumerate(rooms[:3]):
            day = date.today() + timedelta(days=14 + i)
            start_dt = datetime.combine(day, datetime.min.time().replace(hour=8), tzinfo=dt_tz.utc)
            end_dt = start_dt + timedelta(hours=4)
            MeetingRoomMaintenance.objects.get_or_create(
                meeting_room=room,
                start_time=start_dt,
                end_time=end_dt,
                defaults={"reason": random.choice(["设备检修", "系统升级", "环境改造"])},
            )

        return [
            ("会议室", len(rooms)),
            ("预约", booking_count),
            ("维护", 3),
        ]
