"""创建联培生模块的 12 个 PageRoute (用于前端 ProtectedRoute 权限控制)。"""
from django.db import migrations

PAGE_ROUTES_DATA = [
    ("联培生-管理员首页", "/joint-students/admin/students", "StudentListPage", None),
    ("联培生-创建联培生", "/joint-students/admin/students/new", "StudentEditPage", "联培生-管理员首页"),
    ("联培生-联培生详情", "/joint-students/admin/students/:id", "StudentDetailPage", "联培生-管理员首页"),
    ("联培生-报告审核", "/joint-students/admin/reports", "ReportReviewPage", None),
    ("联培生-批次管理", "/joint-students/admin/cycles", "CycleManagementPage", None),
    ("联培生-批次详情", "/joint-students/admin/cycles/:id", "CycleDetailPage", "联培生-批次管理"),
    ("联培生-补助复核", "/joint-students/admin/stipends", "StipendReviewPage", None),
    ("联培生-专家打分", "/joint-students/expert/scoring", "ExpertScoringPage", None),
    ("联培生-我的报告", "/joint-students/student/reports", "MyReportsPage", None),
    ("联培生-填报报告", "/joint-students/student/reports/new", "ReportSubmitPage", "联培生-我的报告"),
    ("联培生-我的补助", "/joint-students/student/stipends", "MyStipendsPage", None),
    ("联培生-导师视图", "/joint-students/mentor/overview", "MentorOverviewPage", None),
]


def create_page_routes(apps, schema_editor):
    PageRoute = apps.get_model("permissions", "PageRoute")
    name_to_route = {}
    for name, path, component, parent_name in PAGE_ROUTES_DATA:
        parent = name_to_route.get(parent_name) if parent_name else None
        route, _ = PageRoute.objects.get_or_create(
            path=path,
            defaults={"name": name, "component": component, "parent": parent},
        )
        name_to_route[name] = route


def remove_page_routes(apps, schema_editor):
    PageRoute = apps.get_model("permissions", "PageRoute")
    paths = [route[1] for route in PAGE_ROUTES_DATA]
    PageRoute.objects.filter(path__in=paths).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("joint_students", "0002_seed_groups"),
        ("permissions", "0001_initial"),
    ]
    operations = [migrations.RunPython(create_page_routes, remove_page_routes)]
