from rest_framework import serializers

from .models import Contract, Education, FamilyMember, Personnel, Position, ProfessionalQualification, WorkExperience


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name"]


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ["id", "personnel", "contract_number", "contract_type", "start_date", "end_date"]


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ["id", "personnel", "school", "degree", "major", "start_date", "end_date"]


class WorkExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkExperience
        fields = ["id", "personnel", "company", "position", "start_date", "end_date", "description"]


class ProfessionalQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalQualification
        # R3-B1: certificate_id(证件编号)仅允许写入,读响应不返回;与 api_key write_only 决策一致
        fields = ["id", "personnel", "qualification_name", "issue_date", "expiry_date", "certificate_id"]
        extra_kwargs = {"certificate_id": {"write_only": True}}


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        # R3-B1: id_card_number(身份证,Fernet 加密)仅允许写入,读响应不返回明文;
        # 保留写能力避免 HR 经 API 录入身份证被静默丢弃
        fields = ["id", "personnel", "name", "relationship", "contact_number", "id_card_number"]
        extra_kwargs = {"id_card_number": {"write_only": True}}


class PersonnelSerializer(serializers.ModelSerializer):
    """
    用于人员列表的核心序列化器 (不包含详细的关联信息)
    """

    id_card_number = serializers.CharField(
        allow_null=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Personnel
        fields = [
            "id",
            "name",
            "id_card_number",
            "date_of_birth",
            "phone_number",
            "address",
            "hire_date",
            "department",
            "position",
            "status",
        ]
        extra_kwargs = {
            "date_of_birth": {"required": False, "allow_null": True},
            "phone_number": {"required": False, "allow_null": True},
            "address": {"required": False, "allow_null": True},
            "hire_date": {"required": False, "allow_null": True},
            "department": {"required": False, "allow_null": True},
            "status": {"required": False, "allow_null": True},
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.position:
            representation["position"] = PositionSerializer(instance.position).data
        return representation


class PersonnelDetailSerializer(serializers.ModelSerializer):
    """
    用于人员详情的序列化器 (包含所有关联信息)
    """

    contracts = ContractSerializer(many=True, read_only=True)
    educations = EducationSerializer(many=True, read_only=True)
    work_experiences = WorkExperienceSerializer(many=True, read_only=True)
    qualifications = ProfessionalQualificationSerializer(many=True, read_only=True)
    family_members = FamilyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Personnel
        fields = [
            "id",
            "name",
            "id_card_number",
            "date_of_birth",
            "phone_number",
            "address",
            "hire_date",
            "department",
            "position",
            "status",
            "contracts",
            "educations",
            "work_experiences",
            "qualifications",
            "family_members",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.position:
            representation["position"] = PositionSerializer(instance.position).data
        return representation


class PersonnelSelfSerializer(serializers.ModelSerializer):
    """用户自助查看/编辑自己人员信息的序列化器(白名单字段)。

    P2-1 引入。L1 防护层(详见 plan 文档 §4.2):
    - 可写字段:date_of_birth, phone_number, address
    - 只读字段:id, name, hire_date, department, position, status
    - 隐藏字段:id_card_number(隐私,不出现在 schema 中)
    - 嵌套子表(只读展示):educations, work_experiences, family_members
    """

    educations = EducationSerializer(many=True, read_only=True)
    work_experiences = WorkExperienceSerializer(many=True, read_only=True)
    family_members = FamilyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Personnel
        fields = [
            "id",
            "name",
            "date_of_birth",
            "phone_number",
            "address",
            "hire_date",
            "department",
            "position",
            "status",
            "educations",
            "work_experiences",
            "family_members",
        ]
        read_only_fields = [
            "id",
            "name",
            "hire_date",
            "department",
            "position",
            "status",
        ]
        extra_kwargs = {
            "date_of_birth": {"required": False, "allow_null": True},
            "phone_number": {"required": False, "allow_null": True},
            "address": {"required": False, "allow_null": True},
        }
