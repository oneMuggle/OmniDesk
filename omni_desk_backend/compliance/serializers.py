from rest_framework import serializers

from .models import ComplianceIssue


class ComplianceIssueSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    document_book_title = serializers.CharField(source="document_book.title", read_only=True)
    document_template_name = serializers.CharField(source="document_template.name", read_only=True)

    class Meta:
        model = ComplianceIssue
        fields = [
            "id",
            "project",
            "project_name",
            "document_book",
            "document_book_title",
            "document_template",
            "document_template_name",
            "issue_type",
            "description",
            "location",
            "status",
            "severity",
            "due_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
