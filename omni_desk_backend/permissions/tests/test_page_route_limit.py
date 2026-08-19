"""PageRouteViewSet 全集封顶 1000 测试。"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from permissions.models import PageRoute

# 联培生模块的 data migration (0003_seed_page_routes) 会创建 12 个 PageRoute。
# 本测试需要在受控计数下验证视图集行为,故用 fixture 临时移除这些种子路由,
# 测试结束后恢复 — 避免污染其他测试。
_JOINT_STUDENT_SEED_PATHS = [
    "/joint-students/admin/students",
    "/joint-students/admin/students/new",
    "/joint-students/admin/students/:id",
    "/joint-students/admin/reports",
    "/joint-students/admin/cycles",
    "/joint-students/admin/cycles/:id",
    "/joint-students/admin/stipends",
    "/joint-students/expert/scoring",
    "/joint-students/student/reports",
    "/joint-students/student/reports/new",
    "/joint-students/student/stipends",
    "/joint-students/mentor/overview",
]


@pytest.fixture
def isolated_page_routes():
    """测试期间屏蔽联培生模块的 12 个 PageRoute 种子,结束后按拓扑顺序恢复。"""
    seed_routes = list(
        PageRoute.objects.filter(path__in=_JOINT_STUDENT_SEED_PATHS).order_by("id")
    )
    # 记录原始 id 与 parent_id,恢复时按 parent_id 引用重新建立的 id
    snapshots = [(r.id, r.parent_id, r.name, r.path, r.component) for r in seed_routes]
    if seed_routes:
        PageRoute.objects.filter(path__in=_JOINT_STUDENT_SEED_PATHS).delete()
    yield
    # 按 parent_id 拓扑顺序恢复:parent 为 None 的先建,parent 已建后建
    id_map = {}
    pending = list(snapshots)
    while pending:
        progress = False
        for snap in pending[:]:
            old_id, parent_old_id, name, path, component = snap
            if parent_old_id is None or parent_old_id in id_map:
                new_parent_id = id_map.get(parent_old_id)
                new_route = PageRoute.objects.create(
                    name=name, path=path, component=component,
                    parent_id=new_parent_id,
                )
                id_map[old_id] = new_route.id
                pending.remove(snap)
                progress = True
        if not progress:
            # 环路或缺失 parent 时跳过剩余,避免 fixture 卡死
            break


@pytest.mark.django_db
class TestPageRouteLimit:
    def test_returns_full_set_when_under_limit(self, api_client, admin_user_obj, isolated_page_routes):
        PageRoute.objects.create(name="route-1", path="/r1/", component="Test", parent=None)
        PageRoute.objects.create(name="route-2", path="/r2/", component="Test", parent=None)
        api_client.force_authenticate(admin_user_obj)
        response = api_client.get("/api/permissions/pages/")
        assert response.status_code == status.HTTP_200_OK
        # pagination_class = None,响应始终为 list;无需 envelope 分支
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # 不触发封顶,完整返回

    def test_caps_at_1000_when_over_limit(self, api_client, admin_user_obj, isolated_page_routes):
        """验证 PageRouteViewSet 列表在数据量 > 1000 时封顶到 1000。

        之前的测试只造 2 条数据后断言 `len(data) <= 1000`,无论实现是否封顶都通过。
        本测试用 bulk_create 高效造 1001 条 PageRoute,断言响应长度恰好等于 1000,
        实际触发并验证 list() 中的 queryset[:1000] 切片。
        """
        PageRoute.objects.bulk_create(
            [
                PageRoute(name=f"route-{i}", path=f"/r{i}/", component="TestComp", parent=None)
                for i in range(1001)
            ]
        )
        # 确认底层确实造了 1001 条,且全是 parent__isnull=True(viewset 的过滤条件)
        assert PageRoute.objects.filter(parent__isnull=True).count() == 1001

        api_client.force_authenticate(admin_user_obj)
        response = api_client.get("/api/permissions/pages/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # 关键断言:封顶到 1000,而非返回 1001 条
        assert len(data) == 1000
        # 次要断言:确实没有截到更低(确认是精确 1000 而非随意截断)
        assert len(data) < 1001
