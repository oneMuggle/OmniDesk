"""personnel 模块综合测试：Position、Personnel、子资源 CRUD、加密字段等。"""

import pytest
import datetime
from django.test import override_settings

from personnel.models import (
    Personnel, Position, Contract, Education, WorkExperience,
    ProfessionalQualification, FamilyMember,
)
from users.models import CustomUser


# ==================== Position 测试 ====================

@pytest.mark.django_db
class TestPosition:
    def test_create_position(self, admin_client):
        """创建职位"""
        resp = admin_client.post('/api/personnel/positions/', {'name': '高级工程师'}, format='json')
        assert resp.status_code == 201, resp.data
        assert Position.objects.filter(name='高级工程师').exists()

    def test_position_uniqueness(self, admin_client):
        """职位名唯一性约束"""
        Position.objects.create(name='唯一职位')
        resp = admin_client.post('/api/personnel/positions/', {'name': '唯一职位'}, format='json')
        assert resp.status_code in [400, 409]

    def test_list_positions(self, admin_client):
        """职位列表"""
        Position.objects.create(name='职位A')
        Position.objects.create(name='职位B')
        resp = admin_client.get('/api/personnel/positions/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 2


# ==================== Personnel CRUD 测试 ====================

@pytest.mark.django_db
class TestPersonnelViewSet:
    def test_create_personnel(self, admin_client):
        """创建人员"""
        pos = Position.objects.create(name='开发人员')
        resp = admin_client.post('/api/personnel/personnel/', {
            'name': '新员工',
            'department': '技术部',
            'position_id': pos.id,
            'status': 'active',
        }, format='json')
        assert resp.status_code == 201, resp.data
        assert Personnel.objects.filter(name='新员工').exists()

    def test_update_personnel(self, admin_client):
        """更新人员信息"""
        p = Personnel.objects.create(name='更新前', department='旧部门')
        resp = admin_client.patch(f'/api/personnel/personnel/{p.id}/', {
            'name': '更新后',
            'department': '新部门',
        }, format='json')
        assert resp.status_code == 200, resp.data
        p.refresh_from_db()
        assert p.name == '更新后'
        assert p.department == '新部门'

    def test_delete_personnel(self, admin_client):
        """删除人员"""
        p = Personnel.objects.create(name='待删除')
        resp = admin_client.delete(f'/api/personnel/personnel/{p.id}/')
        assert resp.status_code == 204
        assert not Personnel.objects.filter(id=p.id).exists()

    def test_search_personnel(self, admin_client):
        """搜索人员"""
        Personnel.objects.create(name='张三', department='技术部')
        Personnel.objects.create(name='李四', department='财务部')
        resp = admin_client.get('/api/personnel/personnel/', {'search': '张'})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        names = [r['name'] for r in results]
        assert '张三' in names
        assert '李四' not in names

    def test_filter_by_status(self, admin_client):
        """按状态过滤"""
        # 清除已有数据
        Personnel.objects.all().delete()
        Personnel.objects.create(name='在职员工', status='active')
        Personnel.objects.create(name='离职员工', status='inactive')
        resp = admin_client.get('/api/personnel/personnel/', {'status': 'active'})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1
        # 验证至少有一个 active 结果
        statuses = set(r['status'] for r in results)
        assert 'active' in statuses


# ==================== Encrypted Field 测试 ====================

@pytest.mark.django_db
class TestEncryptedField:
    def test_id_card_encryption(self):
        """身份证号应加密存储"""
        p = Personnel.objects.create(name='加密测试', id_card_number='110101199001011234')
        # 从数据库直接读取应为加密值
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_card_number FROM personnel_personnel WHERE id = %s", [p.id])
            row = cursor.fetchone()
            stored_value = row[0]
        # 存储值不应等于原文
        assert stored_value != '110101199001011234'
        # 但通过 ORM 读取应自动解密
        p.refresh_from_db()
        assert p.id_card_number == '110101199001011234'

    def test_encrypted_field_null_handling(self):
        """加密字段应允许空值"""
        p = Personnel.objects.create(name='空身份证', id_card_number=None)
        assert p.id_card_number is None

    @override_settings(SECRET_KEY='different-key-for-test')
    def test_different_key_corruption(self):
        """用不同 SECRET_KEY 读取应返回原始加密值而非崩溃"""
        from personnel.models import _encrypt_field, _decrypt_field
        original = 'secret-data'
        encrypted = _encrypt_field(original, 'key-a')
        # 用不同 key 解密
        result = _decrypt_field(encrypted, 'key-b')
        # 应不崩溃，但结果不等于原文
        assert result != original


# ==================== Contract CRUD 测试 ====================

@pytest.mark.django_db
class TestContractViewSet:
    def test_contract_crud(self, admin_client):
        """合同 CRUD"""
        p = Personnel.objects.create(name='合同员工')
        # Create
        resp = admin_client.post('/api/personnel/contracts/', {
            'personnel': p.id,
            'contract_number': 'C-2026-001',
            'contract_type': 'permanent',
            'start_date': '2026-01-01',
            'end_date': '2029-01-01',
        }, format='json')
        assert resp.status_code == 201, resp.data
        contract_id = resp.data['id']

        # Read
        resp = admin_client.get(f'/api/personnel/contracts/{contract_id}/')
        assert resp.status_code == 200

        # Update
        resp = admin_client.patch(f'/api/personnel/contracts/{contract_id}/', {
            'contract_number': 'C-2026-UPDATED',
        }, format='json')
        assert resp.status_code == 200

        # Delete
        resp = admin_client.delete(f'/api/personnel/contracts/{contract_id}/')
        assert resp.status_code == 204


# ==================== Education CRUD 测试 ====================

@pytest.mark.django_db
class TestEducationViewSet:
    def test_education_crud(self, admin_client):
        """教育经历 CRUD"""
        p = Personnel.objects.create(name='教育员工')
        resp = admin_client.post('/api/personnel/educations/', {
            'personnel': p.id,
            'school': '清华大学',
            'degree': '本科',
            'major': '计算机',
            'start_date': '2018-09-01',
            'end_date': '2022-06-01',
        }, format='json')
        assert resp.status_code == 201, resp.data
        edu_id = resp.data['id']

        resp = admin_client.get(f'/api/personnel/educations/{edu_id}/')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/personnel/educations/{edu_id}/')
        assert resp.status_code == 204


# ==================== WorkExperience CRUD 测试 ====================

@pytest.mark.django_db
class TestWorkExperienceViewSet:
    def test_work_experience_crud(self, admin_client):
        """工作经历 CRUD"""
        p = Personnel.objects.create(name='工作经历员工')
        resp = admin_client.post('/api/personnel/work-experiences/', {
            'personnel': p.id,
            'company': '某公司',
            'position': '工程师',
            'start_date': '2020-01-01',
            'end_date': '2024-01-01',
        }, format='json')
        assert resp.status_code == 201, resp.data
        we_id = resp.data['id']

        resp = admin_client.delete(f'/api/personnel/work-experiences/{we_id}/')
        assert resp.status_code == 204


# ==================== ProfessionalQualification CRUD 测试 ====================

@pytest.mark.django_db
class TestProfessionalQualificationViewSet:
    def test_qualification_crud(self, admin_client):
        """专业资格 CRUD"""
        p = Personnel.objects.create(name='资格员工')
        resp = admin_client.post('/api/personnel/qualifications/', {
            'personnel': p.id,
            'qualification_name': 'PMP认证',
            'issuing_authority': 'PMI',
            'issue_date': '2024-01-01',
        }, format='json')
        assert resp.status_code == 201, resp.data
        pq_id = resp.data['id']

        resp = admin_client.delete(f'/api/personnel/qualifications/{pq_id}/')
        assert resp.status_code == 204


# ==================== FamilyMember CRUD 测试 ====================

@pytest.mark.django_db
class TestFamilyMemberViewSet:
    def test_family_member_crud(self, admin_client):
        """家庭成员 CRUD"""
        p = Personnel.objects.create(name='家庭员工')
        resp = admin_client.post('/api/personnel/family-members/', {
            'personnel': p.id,
            'name': '配偶',
            'relationship': '夫妻',
            'phone': '13800000000',
        }, format='json')
        assert resp.status_code == 201, resp.data
        fm_id = resp.data['id']

        resp = admin_client.delete(f'/api/personnel/family-members/{fm_id}/')
        assert resp.status_code == 204


# ==================== Personnel-User 关联测试 ====================

@pytest.mark.django_db
class TestPersonnelUserLink:
    def test_user_personnel_model_link(self):
        """用户模型应能关联 personnel"""
        from users.models import CustomUser
        p = Personnel.objects.create(name='关联员工')
        user = CustomUser.objects.create_user(username='link_test', password='pass123')
        user.personnel = p
        user.save()
        user.refresh_from_db()
        assert user.personnel == p
