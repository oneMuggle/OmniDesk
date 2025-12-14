from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PersonnelViewSet,
    ContractViewSet,
    EducationViewSet,
    WorkExperienceViewSet,
    ProfessionalQualificationViewSet,
    FamilyMemberViewSet
)

router = DefaultRouter()
router.register(r'personnel', PersonnelViewSet, basename='personnel')
router.register(r'contracts', ContractViewSet, basename='contracts')
router.register(r'educations', EducationViewSet, basename='educations')
router.register(r'work-experiences', WorkExperienceViewSet, basename='work-experiences')
router.register(r'qualifications', ProfessionalQualificationViewSet, basename='qualifications')
router.register(r'family-members', FamilyMemberViewSet, basename='family-members')

urlpatterns = [
    path('', include(router.urls)),
]