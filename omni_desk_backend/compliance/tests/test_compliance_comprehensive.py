"""compliance 模块综合测试：ComplianceChecker service、ViewSet CRUD、权限等。"""

import pytest

from compliance.models import ComplianceIssue
from compliance.services.compliance_engine import ComplianceChecker
from projects.models import Project
from documents.models import Book
from users.models import CustomUser


# ==================== ComplianceChecker Service 测试 ====================

@pytest.mark.django_db
class TestComplianceChecker:
    def test_get_visible_issues_staff(self):
        """staff 用户应看到所有问题"""
        staff = CustomUser.objects.create_superuser(username='staff_cc', email='s@t.com', password='pass123')
        project = Project.objects.create(name='员工项目', description='描述', manager=None)
        ComplianceIssue.objects.create(
            project=project, issue_type='不规范', description='问题1'
        )
        issues = ComplianceChecker.get_visible_issues(staff)
        assert issues.count() == 1

    def test_get_visible_issues_project_manager(self):
        """项目经理应只看到自己项目的问题"""
        manager = CustomUser.objects.create_user(username='mgr_cc', password='pass123')
        p1 = Project.objects.create(name='项目1', manager=manager)
        p2 = Project.objects.create(name='项目2')
        ComplianceIssue.objects.create(project=p1, issue_type='不规范', description='经理的问题')
        ComplianceIssue.objects.create(project=p2, issue_type='时间冲突', description='别人的问题')
        issues = ComplianceChecker.get_visible_issues(manager)
        assert issues.count() == 1
        assert issues.first().description == '经理的问题'

    def test_get_visible_issues_regular_user(self):
        """普通用户（非项目经理）应看不到问题"""
        regular = CustomUser.objects.create_user(username='reg_cc', password='pass123')
        project = Project.objects.create(name='无经理项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='问题')
        issues = ComplianceChecker.get_visible_issues(regular)
        assert issues.count() == 0

    def test_can_modify_issue_staff(self):
        """staff 用户应能修改任何问题"""
        staff = CustomUser.objects.create_superuser(username='staff_mod', email='sm@t.com', password='pass123')
        project = Project.objects.create(name='修改项目')
        issue = ComplianceIssue.objects.create(project=project, issue_type='不规范', description='问题')
        assert ComplianceChecker.can_modify_issue(staff, issue) is True

    def test_can_modify_issue_project_manager(self):
        """项目经理应能修改自己项目的问题"""
        manager = CustomUser.objects.create_user(username='mgr_mod', password='pass123')
        project = Project.objects.create(name='经理修改项目', manager=manager)
        issue = ComplianceIssue.objects.create(project=project, issue_type='不规范', description='问题')
        assert ComplianceChecker.can_modify_issue(manager, issue) is True

    def test_cannot_modify_issue_regular_user(self):
        """普通用户不能修改非自己项目的问题"""
        regular = CustomUser.objects.create_user(username='reg_mod', password='pass123')
        other_manager = CustomUser.objects.create_user(username='other_mgr', password='pass123')
        project = Project.objects.create(name='他人项目', manager=other_manager)
        issue = ComplianceIssue.objects.create(project=project, issue_type='不规范', description='问题')
        assert ComplianceChecker.can_modify_issue(regular, issue) is False

    def test_get_unread_count_staff(self):
        """staff 用户应看到所有未读问题计数"""
        staff = CustomUser.objects.create_superuser(username='staff_unread', email='su@t.com', password='pass123')
        project = Project.objects.create(name='未读项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='未读问题', status='待处理')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='已解决问题', status='已解决')
        count = ComplianceChecker.get_unread_count(staff)
        assert count == 1

    def test_get_unread_count_project_manager(self):
        """项目经理应只计算自己项目的未读问题"""
        manager = CustomUser.objects.create_user(username='mgr_unread', password='pass123')
        p1 = Project.objects.create(name='经理项目1', manager=manager)
        p2 = Project.objects.create(name='经理项目2', manager=manager)
        ComplianceIssue.objects.create(project=p1, issue_type='不规范', description='未读1', status='待处理')
        ComplianceIssue.objects.create(project=p2, issue_type='时间冲突', description='未读2', status='处理中')
        ComplianceIssue.objects.create(project=p1, issue_type='不规范', description='已解决', status='已解决')
        count = ComplianceChecker.get_unread_count(manager)
        assert count == 2


# ==================== ComplianceIssue ViewSet 测试 ====================

@pytest.mark.django_db
class TestComplianceIssueViewSet:
    def test_list_issues(self, admin_client):
        """合规问题列表"""
        project = Project.objects.create(name='列表项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='问题A')
        resp = admin_client.get('/api/compliance/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1

    def test_create_issue(self, admin_client):
        """创建合规问题"""
        project = Project.objects.create(name='创建问题项目')
        resp = admin_client.post('/api/compliance/', {
            'project': project.id,
            'issue_type': '不规范',
            'description': '新创建的问题',
            'status': '待处理',
            'severity': '中',
        }, format='json')
        assert resp.status_code == 201, resp.data
        assert ComplianceIssue.objects.filter(description='新创建的问题').exists()

    def test_update_issue_status(self, admin_client):
        """更新问题状态"""
        project = Project.objects.create(name='更新项目')
        issue = ComplianceIssue.objects.create(project=project, issue_type='不规范', description='待更新')
        resp = admin_client.patch(f'/api/compliance/{issue.id}/', {
            'status': '处理中',
        }, format='json')
        assert resp.status_code == 200, resp.data
        issue.refresh_from_db()
        assert issue.status == '处理中'

    def test_delete_issue(self, admin_client):
        """删除合规问题"""
        project = Project.objects.create(name='删除项目')
        issue = ComplianceIssue.objects.create(project=project, issue_type='不规范', description='待删除')
        resp = admin_client.delete(f'/api/compliance/{issue.id}/')
        assert resp.status_code == 204
        assert not ComplianceIssue.objects.filter(id=issue.id).exists()

    def test_filter_by_status(self, admin_client):
        """按状态过滤"""
        project = Project.objects.create(name='过滤项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='问题1', status='待处理')
        ComplianceIssue.objects.create(project=project, issue_type='时间冲突', description='问题2', status='已解决')
        resp = admin_client.get('/api/compliance/', {'status': '待处理'})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1

    def test_filter_by_severity(self, admin_client):
        """按严重程度过滤"""
        project = Project.objects.create(name='严重度项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='高严重', severity='高')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='低严重', severity='低')
        resp = admin_client.get('/api/compliance/', {'severity': '高'})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1

    def test_search_issues(self, admin_client):
        """搜索问题"""
        project = Project.objects.create(name='搜索项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='独特搜索关键词')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='其他问题')
        resp = admin_client.get('/api/compliance/', {'search': '独特'})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        descriptions = [r['description'] for r in results]
        assert '独特搜索关键词' in descriptions

    def test_unread_count_endpoint(self, admin_client):
        """unread_count 端点"""
        project = Project.objects.create(name='未读端点项目')
        ComplianceIssue.objects.create(project=project, issue_type='不规范', description='未读', status='待处理')
        resp = admin_client.get('/api/compliance/unread_count/')
        assert resp.status_code == 200
        assert 'unread_count' in resp.data


# ==================== ComplianceIssue 模型测试 ====================

@pytest.mark.django_db
class TestComplianceIssueModel:
    def test_create_with_book(self):
        """关联书籍创建问题"""
        project = Project.objects.create(name='书籍关联项目')
        book = Book.objects.create(title='关联书籍', author='作者')
        issue = ComplianceIssue.objects.create(
            project=project,
            document_book=book,
            issue_type='内容缺失',
            description='书籍内容缺失',
        )
        assert issue.document_book == book
        assert '关联书籍' in str(issue)

    def test_str_representation(self):
        """__str__ 应包含项目和描述"""
        project = Project.objects.create(name='字符串项目')
        issue = ComplianceIssue.objects.create(
            project=project,
            issue_type='不规范',
            description='这是一个很长的描述用于测试字符串表示',
        )
        str_repr = str(issue)
        assert '字符串项目' in str_repr
        assert '不规范' in str_repr
