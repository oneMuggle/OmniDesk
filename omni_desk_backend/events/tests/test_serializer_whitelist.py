"""events serializer 白名单化测试 (R3-B1 PR-3)。

契约(plan §3.2 PR-3 + §3.1 嵌套保留原则):
- 7 个 serializer(TimeSlot/Trial/DocumentTemplate/Schedule/Announcement/UploadedImage/Holiday)
  显式白名单字段,不随 `__all__` 暴露模型全部字段
- TrialSerializer 保留前端深度消费的嵌套字段:time_slots/responsible_persons/equipments
  (前端 eventTransformers.jsx/TrialDetails.jsx 消费 trial.time_slots)
"""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from events.models import (
    Announcement,
    DocumentTemplate,
    Holiday,
    Schedule,
    TimeSlot,
    Trial,
    UploadedImage,
)
from events.serializers import (
    AnnouncementSerializer,
    DocumentTemplateSerializer,
    HolidaySerializer,
    ScheduleSerializer,
    TimeSlotSerializer,
    TrialSerializer,
    UploadedImageSerializer,
)
from personnel.models import Personnel


@pytest.fixture
def personnel(db):
    return Personnel.objects.create(name="张三", department="研发部")


@pytest.mark.django_db
class TestTimeSlotSerializerWhitelist:
    def test_fields_whitelisted(self):
        start = timezone.now()
        slot = TimeSlot.objects.create(
            trial=Trial.objects.create(title="试验A", client="客户A", description="描述"),
            start_time=start,
            end_time=start + timedelta(hours=1),
            description="上午时段",
        )

        data = TimeSlotSerializer(slot).data

        assert set(data.keys()) == {"id", "trial", "start_time", "end_time", "description"}

    def test_write_accepts_fields(self):
        trial = Trial.objects.create(title="试验A", client="客户A", description="描述")
        start = timezone.now()
        serializer = TimeSlotSerializer(
            data={
                "trial": trial.id,
                "start_time": start,
                "end_time": start + timedelta(hours=1),
                "description": "上午时段",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["trial"] == trial


@pytest.mark.django_db
class TestTrialSerializerWhitelist:
    def test_fields_whitelisted(self, personnel):
        trial = Trial.objects.create(
            title="试验A",
            version=1,
            client="客户A",
            description="描述",
            status="planned",
        )
        trial.responsible_persons.add(personnel)

        data = TrialSerializer(trial).data

        # time_slots_data 为 write_only 自定义字段,读响应不含;
        # 嵌套 time_slots/responsible_persons/equipments 前端深度消费,保留
        assert set(data.keys()) == {
            "id",
            "title",
            "version",
            "client",
            "description",
            "start_date",
            "end_date",
            "equipments",
            "responsible_persons",
            "status",
            "created_at",
            "updated_at",
            "time_slots",
        }

    def test_write_accepts_time_slots_data(self):
        start = timezone.now()
        serializer = TrialSerializer(
            data={
                "title": "试验A",
                "client": "客户A",
                "description": "描述",
                "time_slots_data": [
                    {
                        "start_time": start,
                        "end_time": start + timedelta(hours=1),
                        "description": "上午时段",
                    }
                ],
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert len(serializer.validated_data["time_slots_data"]) == 1


@pytest.mark.django_db
class TestDocumentTemplateSerializerWhitelist:
    def test_fields_whitelisted(self, regular_user_obj):
        doc = DocumentTemplate.objects.create(
            name="化学实验模板",
            experiment_type="chemical",
            template_file=SimpleUploadedFile("tpl.docx", b"x"),
            owner=regular_user_obj,
        )

        data = DocumentTemplateSerializer(doc).data

        assert set(data.keys()) == {
            "id",
            "name",
            "experiment_type",
            "template_file",
            "created_at",
            "owner",
        }

    def test_write_accepts_fields(self, regular_user_obj):
        """写路径仍接受全部白名单可写字段(防未来误删可写字段)。"""
        serializer = DocumentTemplateSerializer(
            data={
                "name": "生物实验模板",
                "experiment_type": "biological",
                "template_file": SimpleUploadedFile("tpl2.docx", b"x"),
                "owner": regular_user_obj.id,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "生物实验模板"
        assert serializer.validated_data["owner"] == regular_user_obj


@pytest.mark.django_db
class TestScheduleSerializerWhitelist:
    def test_fields_whitelisted(self, personnel):
        sched = Schedule.objects.create(
            duty_date="2026-08-20",
            duty_person=personnel,
            duty_leader=personnel,
        )

        data = ScheduleSerializer(sched).data

        assert set(data.keys()) == {"id", "duty_date", "duty_person", "duty_leader"}

    def test_nested_duty_person_kept(self, personnel):
        sched = Schedule.objects.create(
            duty_date="2026-08-21",
            duty_person=personnel,
        )

        data = ScheduleSerializer(sched).data

        assert data["duty_person"]["name"] == "张三"

    def test_write_accepts_duty_date(self):
        """duty_person/duty_leader 为只读嵌套(写入走视图层),写路径接受 duty_date。"""
        serializer = ScheduleSerializer(data={"duty_date": "2026-08-22"})

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["duty_date"].isoformat() == "2026-08-22"


@pytest.mark.django_db
class TestAnnouncementSerializerWhitelist:
    def test_fields_whitelisted(self, regular_user_obj):
        ann = Announcement.objects.create(
            title="公告标题",
            content="公告内容",
            author=regular_user_obj,
        )

        data = AnnouncementSerializer(ann).data

        assert set(data.keys()) == {
            "id",
            "title",
            "content",
            "author",
            "created_at",
            "updated_at",
        }

    def test_write_accepts_fields(self, regular_user_obj):
        serializer = AnnouncementSerializer(
            data={
                "title": "新公告",
                "content": "新内容",
                "author": regular_user_obj.id,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["author"] == regular_user_obj


@pytest.mark.django_db
class TestUploadedImageSerializerWhitelist:
    def test_fields_whitelisted(self):
        img = UploadedImage.objects.create(
            image=SimpleUploadedFile("photo.png", b"x", content_type="image/png"),
        )

        data = UploadedImageSerializer(img).data

        assert set(data.keys()) == {"id", "image", "uploaded_at"}


@pytest.mark.django_db
class TestHolidaySerializerWhitelist:
    def test_fields_whitelisted(self):
        holiday = Holiday.objects.create(
            name="国庆节",
            start_date="2026-10-01",
            end_date="2026-10-07",
        )

        data = HolidaySerializer(holiday).data

        assert set(data.keys()) == {"id", "name", "start_date", "end_date"}

    def test_write_accepts_fields(self):
        serializer = HolidaySerializer(
            data={
                "name": "元旦",
                "start_date": "2027-01-01",
                "end_date": "2027-01-03",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "元旦"
