"""联培生模块 DRF 序列化器。"""

from rest_framework import serializers

from joint_students.models import (
    AssessmentCycle,
    ExpertScore,
    JointStudent,
    MonthlyReport,
    StipendRecord,
)


class JointStudentSerializer(serializers.ModelSerializer):
    """联培生列表/详情。"""

    personnel_name = serializers.CharField(source="personnel.name", read_only=True)
    mentor_name = serializers.CharField(source="mentor.name", read_only=True, default=None)
    student_type_display = serializers.CharField(source="get_student_type_display", read_only=True)

    class Meta:
        model = JointStudent
        fields = [
            "id",
            "personnel",
            "personnel_name",
            "student_type",
            "student_type_display",
            "student_id",
            "enrollment_date",
            "graduation_date",
            "mentor",
            "mentor_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class MonthlyReportSerializer(serializers.ModelSerializer):
    """月度报告。"""

    student_name = serializers.CharField(source="joint_student.personnel.name", read_only=True)
    student_id = serializers.CharField(source="joint_student.student_id", read_only=True)

    def validate(self, attrs):
        """禁止通过普通报告更新接口改绑联培生。"""
        if self.instance is not None and "joint_student" in self.initial_data:
            raise serializers.ValidationError({"joint_student": "报告归属不可修改"})
        return attrs

    class Meta:
        model = MonthlyReport
        fields = [
            "id",
            "joint_student",
            "student_name",
            "student_id",
            "year",
            "month",
            "work_progress",
            "work_highlights",
            "attendance_days_actual",
            "attendance_days_expected",
            "attendance_notes",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewer",
            "reviewer_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewer",
            "created_at",
            "updated_at",
        ]


class AssessmentCycleSerializer(serializers.ModelSerializer):
    """考核批次。"""

    class Meta:
        model = AssessmentCycle
        fields = [
            "id",
            "year",
            "month",
            "cycle_start_date",
            "cycle_end_date",
            "scoring_deadline",
            "status",
            "trigger_source",
            "created_at",
            "created_by",
        ]
        read_only_fields = ["status", "trigger_source", "created_at", "created_by"]


class ExpertScoreSerializer(serializers.ModelSerializer):
    """专家打分。"""

    expert_username = serializers.CharField(source="expert.username", read_only=True)

    class Meta:
        model = ExpertScore
        fields = [
            "id",
            "cycle",
            "expert",
            "expert_username",
            "joint_student",
            "score",
            "comment",
            "submitted_at",
            "is_locked",
        ]
        read_only_fields = ["expert", "submitted_at", "is_locked"]


class StipendRecordSerializer(serializers.ModelSerializer):
    """补助记录。"""

    student_name = serializers.CharField(source="joint_student.personnel.name", read_only=True)
    student_id = serializers.CharField(source="joint_student.student_id", read_only=True)
    student_type = serializers.CharField(source="joint_student.student_type", read_only=True)
    grade_display = serializers.CharField(source="get_grade_display", read_only=True)

    class Meta:
        model = StipendRecord
        fields = [
            "id",
            "cycle",
            "joint_student",
            "student_name",
            "student_id",
            "student_type",
            "average_score",
            "rank_in_cycle",
            "grade",
            "grade_display",
            "base_amount",
            "grade_coefficient",
            "attendance_ratio",
            "final_amount",
            "status",
            "locked_at",
            "locked_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "cycle",
            "joint_student",
            "average_score",
            "rank_in_cycle",
            "grade",
            "base_amount",
            "grade_coefficient",
            "attendance_ratio",
            "final_amount",
            "status",
            "locked_at",
            "locked_by",
            "created_at",
            "updated_at",
        ]
