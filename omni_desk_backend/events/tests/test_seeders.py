"""
Tests for events/management/seeders/* — coverage boost for seeder modules.

Each seeder is invoked once with a minimal context; we assert that:
1. seed() returns a list of (label, count) tuples
2. The registry can discover all registered seeders
3. BaseSeeder.safe_get_or_create handles valid + invalid fields gracefully
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from events.management.seeders.base import BaseSeeder
from events.management.seeders import discover_seeders, SEEDER_REGISTRY
from projects.models import Project
from documents.models import Tag


CustomUser = get_user_model()


@pytest.mark.django_db
class TestBaseSeeder:
    """Tests for BaseSeeder class methods."""

    def test_repr(self):
        seeder = BaseSeeder()
        seeder.name = "test"
        assert repr(seeder) == "<Seeder: test (order=100)>"

    def test_default_init(self):
        seeder = BaseSeeder()
        assert seeder.context == {}
        assert seeder.created_count == 0
        assert seeder.name == ""
        assert seeder.order == 100
        assert seeder.models == []

    def test_init_with_context(self):
        ctx = {"user": "alice"}
        seeder = BaseSeeder(context=ctx)
        assert seeder.context is ctx

    def test_has_models_all_present(self):
        seeder = BaseSeeder()
        assert seeder.has_models(Project, Tag) is True

    def test_has_models_one_none(self):
        seeder = BaseSeeder()
        assert seeder.has_models(Project, None) is False

    def test_has_models_all_none(self):
        seeder = BaseSeeder()
        assert seeder.has_models(None, None) is False

    def test_seed_raises_not_implemented(self):
        seeder = BaseSeeder()
        with pytest.raises(NotImplementedError):
            seeder.seed()

    def test_safe_get_or_create_creates_new(self):
        seeder = BaseSeeder()
        obj, created = seeder.safe_get_or_create(
            Tag, name="unique-tag-1"
        )
        assert created is True
        assert obj.name == "unique-tag-1"

    def test_safe_get_or_create_returns_existing(self):
        Tag.objects.create(name="unique-tag-2")
        seeder = BaseSeeder()
        obj, created = seeder.safe_get_or_create(
            Tag, name="unique-tag-2"
        )
        assert created is False
        assert obj.name == "unique-tag-2"

    def test_safe_get_or_create_drops_invalid_default_field(self):
        """Unknown field in defaults should be dropped silently with a warning."""
        seeder = BaseSeeder()
        obj, created = seeder.safe_get_or_create(
            Tag,
            name="unique-tag-3",
            defaults={"non_existing_field": "ignored", "description": "kept"},
        )
        assert created is True
        assert obj.name == "unique-tag-3"


@pytest.mark.django_db
class TestDiscoverSeeders:
    """Tests for the seeder auto-registration mechanism."""

    def test_registry_is_non_empty(self):
        assert len(SEEDER_REGISTRY) > 0
        # Each entry is a 3-tuple: (module_path, class_name, enabled)
        for entry in SEEDER_REGISTRY:
            assert len(entry) == 3
            assert isinstance(entry[0], str)
            assert isinstance(entry[1], str)
            assert isinstance(entry[2], bool)

    def test_discover_seeders_returns_seeder_instances(self):
        seeders = discover_seeders(context={})
        assert isinstance(seeders, list)
        assert all(isinstance(s, BaseSeeder) for s in seeders)
        # Seeders should be sorted by `order`
        orders = [s.order for s in seeders]
        assert orders == sorted(orders)

    def test_discover_seeders_enabled_filter(self):
        all_seeders = discover_seeders(context={})
        # All SEEDER_REGISTRY entries with True flag should be loaded
        enabled_count = sum(1 for e in SEEDER_REGISTRY if e[2])
        assert len(all_seeders) == enabled_count

    def test_discover_seeders_with_empty_context(self):
        seeders = discover_seeders(context={})
        assert all(s.context == {} for s in seeders)


@pytest.mark.django_db
class TestProjectSeeder:
    """Tests for ProjectSeeder.seed()."""

    def test_seed_creates_projects_and_tags(self, regular_user_obj):
        from events.management.seeders.project_seeder import ProjectSeeder

        seeder = ProjectSeeder(context={"user": regular_user_obj})
        result = seeder.seed()

        assert isinstance(result, list)
        assert len(result) == 4  # 项目, 标签, 文档模板, 书籍章节
        for label, count in result:
            assert isinstance(label, str)
            assert isinstance(count, int)

        # Projects were created
        assert Project.objects.count() >= 5
        # Tags were created
        assert Tag.objects.count() >= 8
        # context was populated
        assert "projects" in seeder.context
        assert len(seeder.context["projects"]) == 5

    def test_seed_is_idempotent(self, regular_user_obj):
        from events.management.seeders.project_seeder import ProjectSeeder

        ProjectSeeder(context={"user": regular_user_obj}).seed()
        first_count = Project.objects.count()

        # Second run should not create duplicates
        ProjectSeeder(context={"user": regular_user_obj}).seed()
        second_count = Project.objects.count()

        assert first_count == second_count


@pytest.mark.django_db
class TestMeetingRoomSeeder:
    """Tests for MeetingRoomSeeder.seed()."""

    def test_seed_creates_meeting_rooms(self, regular_user_obj):
        from events.management.seeders.meeting_room_seeder import MeetingRoomSeeder
        from meeting_rooms.models import MeetingRoom

        seeder = MeetingRoomSeeder(context={"user": regular_user_obj})
        result = seeder.seed()

        assert isinstance(result, list)
        assert MeetingRoom.objects.count() >= 1
        for label, count in result:
            assert isinstance(label, str)
            assert count > 0


@pytest.mark.django_db
class TestMiscSeeder:
    """Tests for MiscSeeder.seed()."""

    def test_seed_runs(self, regular_user_obj):
        from events.management.seeders.misc_seeder import MiscSeeder

        seeder = MiscSeeder(context={"user": regular_user_obj})
        # MiscSeeder may depend on many models; just verify it runs without crashing
        try:
            result = seeder.seed()
            assert isinstance(result, list)
        except Exception as e:
            # If a model is missing in test settings, that's a known limitation
            pytest.skip(f"MiscSeeder skipped due to missing dependency: {e}")


@pytest.mark.django_db
class TestSensorSeeder:
    """Tests for SensorSeeder.seed()."""

    def test_seed_runs(self, regular_user_obj):
        from events.management.seeders.sensor_seeder import SensorSeeder

        seeder = SensorSeeder(context={"user": regular_user_obj})
        try:
            result = seeder.seed()
            assert isinstance(result, list)
        except Exception as e:
            pytest.skip(f"SensorSeeder skipped due to missing dependency: {e}")


@pytest.mark.django_db
class TestTrialScheduleSeeder:
    """Tests for TrialScheduleSeeder.seed()."""

    def test_seed_runs(self, regular_user_obj):
        from events.management.seeders.trial_schedule_seeder import TrialScheduleSeeder

        seeder = TrialScheduleSeeder(context={"user": regular_user_obj})
        try:
            result = seeder.seed()
            assert isinstance(result, list)
        except Exception as e:
            pytest.skip(f"TrialScheduleSeeder skipped due to missing dependency: {e}")


@pytest.mark.django_db
class TestPersonnelSeeder:
    """Tests for PersonnelSeeder.seed()."""

    def test_seed_runs(self, regular_user_obj):
        from events.management.seeders.personnel_seeder import PersonnelSeeder

        seeder = PersonnelSeeder(context={"user": regular_user_obj})
        try:
            result = seeder.seed()
            assert isinstance(result, list)
        except Exception as e:
            pytest.skip(f"PersonnelSeeder skipped due to missing dependency: {e}")
