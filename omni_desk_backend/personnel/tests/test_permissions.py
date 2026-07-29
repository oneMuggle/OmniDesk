"""P0-A personnel 行级权限测试

覆盖 Contract 等 5 个子 ViewSet 的行级隔离:
- 本人可读自己 personnel 名下的合同
- 其他普通用户列表结果为空、详情 404
- admin/manager 仍可见全量
"""
from datetime import date

import pytest
from rest_framework.test import APIClient

from personnel.models import Contract, Personnel
from users.models import CustomUser


def _make_user_with_personnel(username):
    """创建 user + 其 personnel 档案并完成关联。"""
    personnel = Personnel.objects.create(name=username)
    user = CustomUser.objects.create_user(username=username, password="pass12345", personnel=personnel)
    return user, personnel


def _make_contract(personnel, number="C-001"):
    return Contract.objects.create(
        personnel=personnel,
        contract_number=number,
        start_date=date(2024, 1, 1),
        end_date=date(2026, 1, 1),
        contract_type="fixed-term",
    )


@pytest.fixture
def alice():
    return _make_user_with_personnel("alice")


@pytest.fixture
def bob():
    return _make_user_with_personnel("bob")


@pytest.mark.django_db
class TestContractRowLevelPermission:
    def test_owner_can_read_own_contract(self, alice):
        user, personnel = alice
        contract = _make_contract(personnel)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get("/api/personnel/contracts/")
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.data["results"]]
        assert contract.id in ids

        detail = client.get(f"/api/personnel/contracts/{contract.id}/")
        assert detail.status_code == 200
        assert detail.data["contract_number"] == "C-001"

    def test_other_user_cannot_read_others_contract(self, alice, bob):
        _, alice_personnel = alice
        bob_user, _ = bob
        contract = _make_contract(alice_personnel)
        client = APIClient()
        client.force_authenticate(user=bob_user)

        resp = client.get("/api/personnel/contracts/")
        assert resp.status_code == 200
        assert resp.data["results"] == []

        # 直接访问详情:行级过滤后 404,而非 403(不泄露存在性)
        detail = client.get(f"/api/personnel/contracts/{contract.id}/")
        assert detail.status_code == 404

    def test_other_user_cannot_modify_others_contract(self, alice, bob):
        _, alice_personnel = alice
        bob_user, _ = bob
        contract = _make_contract(alice_personnel)
        client = APIClient()
        client.force_authenticate(user=bob_user)

        resp = client.delete(f"/api/personnel/contracts/{contract.id}/")
        assert resp.status_code == 404
        assert Contract.objects.filter(id=contract.id).exists()

    def test_manager_can_see_all_contracts(self, alice, manager_user_obj):
        _, alice_personnel = alice
        contract = _make_contract(alice_personnel)
        client = APIClient()
        client.force_authenticate(user=manager_user_obj)

        resp = client.get("/api/personnel/contracts/")
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.data["results"]]
        assert contract.id in ids

    def test_anonymous_rejected(self):
        resp = APIClient().get("/api/personnel/contracts/")
        assert resp.status_code in (401, 403)
