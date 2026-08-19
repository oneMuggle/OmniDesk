"""upload_template 修复测试 (fix: 对无 file 字段的 model 传 file= 导致 500)。

背景:DocumentTemplate model 无 `file` 字段,`templates.py upload_template` 却传 `file=file_obj`
→ TypeError 必然 500(被 except 捕获),上传功能从未成功过;且 `template_type`/`content`
为非空字段,`create()` 未提供 → 即使去掉 `file=` 也会 IntegrityError。
修复:移除 `file=`,`content` 取提取文本,`template_type` 允许请求体传入、缺省用首个 choices。
"""

from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from rest_framework import status

from documents.models import DocumentTemplate


@pytest.mark.django_db
class TestUploadTemplate:
    @pytest.fixture(autouse=True)
    def mock_process_uploaded_file(self, mocker):
        """mock 文本提取,避免真实调用外部 OCR/解析依赖。"""
        return mocker.patch(
            "documents.views.templates.process_uploaded_file",
            return_value="提取的模板文本",
        )

    def _upload(self, api_client, user, *, project_id=None, template_type=None, filename="plan.docx"):
        payload = {
            "template": SimpleUploadedFile(
                filename,
                b"dummy-bytes",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }
        if project_id is not None:
            payload["project"] = project_id
        if template_type is not None:
            payload["template_type"] = template_type
        api_client.force_authenticate(user=user)
        return api_client.post("/api/documents/templates/upload/", payload, format="multipart")

    def test_upload_creates_template(self, api_client, regular_user_obj, mock_process_uploaded_file):
        response = self._upload(api_client, regular_user_obj)

        assert response.status_code == status.HTTP_201_CREATED
        template = DocumentTemplate.objects.get(name="plan.docx")
        assert template.owner == regular_user_obj
        assert template.extracted_text == "提取的模板文本"
        assert template.content == "提取的模板文本"
        assert template.template_type == "tech_design"  # 缺省取首个 choices
        assert template.project is None

    def test_upload_with_project(self, api_client, regular_user_obj, mock_process_uploaded_file):
        from projects.models import Project

        project = Project.objects.create(name="项目X", status="进行中")

        response = self._upload(api_client, regular_user_obj, project_id=project.id)

        assert response.status_code == status.HTTP_201_CREATED
        template = DocumentTemplate.objects.get(name="plan.docx")
        assert template.project == project

    def test_upload_with_explicit_template_type(self, api_client, regular_user_obj, mock_process_uploaded_file):
        response = self._upload(api_client, regular_user_obj, template_type="test_case")

        assert response.status_code == status.HTTP_201_CREATED
        assert DocumentTemplate.objects.get(name="plan.docx").template_type == "test_case"

    def test_upload_with_empty_template_type_falls_back_to_default(
        self, api_client, regular_user_obj, mock_process_uploaded_file
    ):
        response = self._upload(api_client, regular_user_obj, template_type="")

        assert response.status_code == status.HTTP_201_CREATED
        assert DocumentTemplate.objects.get(name="plan.docx").template_type == "tech_design"

    def test_upload_with_invalid_template_type_returns_400(
        self, api_client, regular_user_obj, mock_process_uploaded_file
    ):
        response = self._upload(api_client, regular_user_obj, template_type="garbage")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid template_type" in response.data["error"]
        assert DocumentTemplate.objects.count() == 0

    def test_upload_without_file_returns_400(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post("/api/documents/templates/upload/", {}, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_with_nonexistent_project_returns_404(
        self, api_client, regular_user_obj, mock_process_uploaded_file
    ):
        response = self._upload(api_client, regular_user_obj, project_id=99999)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_upload_with_non_numeric_project_id_returns_400(
        self, api_client, regular_user_obj, mock_process_uploaded_file
    ):
        response = self._upload(api_client, regular_user_obj, project_id="abc")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid project_id" in response.data["error"]
        assert DocumentTemplate.objects.count() == 0
