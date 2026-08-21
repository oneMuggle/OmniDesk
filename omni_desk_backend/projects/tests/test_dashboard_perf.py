"""R5-B3: dashboard 性能相关测试。

Project.updated_at 有 db_index(dashboard recent_projects 按 -updated_at 排序)。
"""

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


class TestProjectUpdatedAtIndex:
    def test_updated_at_has_index(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, "projects_project")
        index_columns = [
            name for name, c in constraints.items() if c.get("index") and c.get("columns") == ["updated_at"]
        ]
        assert index_columns, (
            f"projects_project.updated_at 缺少索引,现有约束: "
            f"{[(n, c['columns']) for n, c in constraints.items()]}"
        )
