from rest_framework import serializers

from .models import Contract, Education, FamilyMember, Personnel, Position, ProfessionalQualification, WorkExperience


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'

class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = '__all__'

class WorkExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkExperience
        fields = '__all__'

class ProfessionalQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalQualification
        fields = '__all__'

class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = '__all__'

class PersonnelSerializer(serializers.ModelSerializer):
    """
    用于人员列表的核心序列化器 (不包含详细的关联信息)
    """
    id_card_number = serializers.CharField(
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Personnel
        fields = [
            'id', 'name', 'id_card_number', 'date_of_birth', 'phone_number',
            'address', 'hire_date', 'department', 'position', 'status'
        ]
        extra_kwargs = {
            'date_of_birth': {'required': False, 'allow_null': True},
            'phone_number': {'required': False, 'allow_null': True},
            'address': {'required': False, 'allow_null': True},
            'hire_date': {'required': False, 'allow_null': True},
            'department': {'required': False, 'allow_null': True},
            'status': {'required': False, 'allow_null': True},
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.position:
            representation['position'] = PositionSerializer(instance.position).data
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
            'id', 'name', 'id_card_number', 'date_of_birth', 'phone_number',
            'address', 'hire_date', 'department', 'position', 'status',
            'contracts', 'educations', 'work_experiences', 'qualifications', 'family_members'
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.position:
            representation['position'] = PositionSerializer(instance.position).data
        return representation
