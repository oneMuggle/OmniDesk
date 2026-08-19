"""联培生模块 URL 路由。

端点列表:
    GET    /api/joint-students/personnel-pool/         联培生管理员 可选 Personnel 池
    GET    /api/joint-students/students/               联培生列表
    POST   /api/joint-students/students/               创建联培生
    POST   /api/joint-students/students/{id}/graduate/ 标记毕业
    GET    /api/joint-students/reports/                月度报告列表
    POST   /api/joint-students/reports/{id}/submit/    联培生提交
    POST   /api/joint-students/reports/{id}/approve/   管理员通过
    POST   /api/joint-students/reports/{id}/reject/    管理员驳回 (需 reviewer_comment)
    GET    /api/joint-students/cycles/                 考核批次列表
    POST   /api/joint-students/cycles/trigger/         管理员手动触发
    POST   /api/joint-students/cycles/{id}/force_close/ 强制截止
    GET    /api/joint-students/scores/                 专家打分列表 (仅自己的)
    POST   /api/joint-students/scores/                 专家打分
    POST   /api/joint-students/scores/{id}/unlock/     admin 解锁
    GET    /api/joint-students/stipends/               补助记录
    POST   /api/joint-students/stipends/{id}/lock/     管理员复核锁定
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssessmentCycleViewSet,
    ExpertScoreViewSet,
    JointStudentViewSet,
    MonthlyReportViewSet,
    PersonnelPoolView,
    StipendRecordViewSet,
)

router = DefaultRouter()
router.register(r"students", JointStudentViewSet, basename="joint-student")
router.register(r"reports", MonthlyReportViewSet, basename="monthly-report")
router.register(r"cycles", AssessmentCycleViewSet, basename="assessment-cycle")
router.register(r"scores", ExpertScoreViewSet, basename="expert-score")
router.register(r"stipends", StipendRecordViewSet, basename="stipend")

urlpatterns = [
    path("personnel-pool/", PersonnelPoolView.as_view(), name="personnel-pool"),
    path("", include(router.urls)),
]
