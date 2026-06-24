import base64
import hashlib
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

logger = logging.getLogger(__name__)


def _encrypt_field(value, key):
    """Simple XOR-based encryption for sensitive fields using SECRET_KEY."""
    if not value:
        return value
    key_bytes = hashlib.sha256(key.encode()).digest()
    value_bytes = value.encode("utf-8")
    encrypted = bytes(v ^ key_bytes[i % len(key_bytes)] for i, v in enumerate(value_bytes))
    return base64.b64encode(encrypted).decode("utf-8")


def _decrypt_field(encoded_value, key):
    """Decrypt a field encrypted by _encrypt_field."""
    if not encoded_value:
        return encoded_value
    try:
        key_bytes = hashlib.sha256(key.encode()).digest()
        encrypted = base64.b64decode(encoded_value.encode("utf-8"))
        decrypted = bytes(e ^ key_bytes[i % len(key_bytes)] for i, e in enumerate(encrypted))
        return decrypted.decode("utf-8")
    except Exception:
        # Data may be corrupted (e.g., encrypted with a different key).
        # Return the raw value instead of crashing.
        logger.debug("字段解密失败，返回原始值（可能数据已损坏或使用不同密钥加密）")
        return encoded_value


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts values using Django's SECRET_KEY."""

    def from_db_value(self, value, expression, connection):
        return _decrypt_field(value, settings.SECRET_KEY)

    def get_prep_value(self, value):
        if value is None:
            return None
        return _encrypt_field(value, settings.SECRET_KEY)


class Position(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="职位名称")

    class Meta:
        verbose_name = "职位"
        verbose_name_plural = "职位管理"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Personnel(models.Model):
    """
    核心人员信息模型
    """

    # Basic Info
    name = models.CharField(max_length=100, verbose_name="姓名", db_index=True)
    id_card_number = EncryptedCharField(max_length=64, unique=True, null=True, blank=True, verbose_name="身份证号")
    # max_length 调整为 64:18 字符明文 XOR+base64 加密后变 24 字符密文,18 长度不够
    date_of_birth = models.DateField(verbose_name="出生年月", null=True, blank=True)
    phone_number = models.CharField(max_length=20, verbose_name="联系电话", blank=True)
    address = models.TextField(verbose_name="家庭住址", blank=True)

    # Employment Info
    hire_date = models.DateField(verbose_name="入职日期", null=True, blank=True)
    department = models.CharField(max_length=100, verbose_name="部门", blank=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="职位")

    STATUS_CHOICES = [
        ("active", "在职"),
        ("inactive", "离职"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", verbose_name="员工状态")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    def clean(self):
        """L3 数据完整性防护(P2-4):仅校验数据本身,不依赖用户上下文。"""
        super().clean()
        errors = {}
        if not self.name or not self.name.strip():
            errors["name"] = "姓名不能为空"
        valid_statuses = {code for code, _ in self.STATUS_CHOICES}
        if self.status not in valid_statuses:
            errors["status"] = f"status 必须是 {valid_statuses} 之一"
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "人员信息"
        verbose_name_plural = verbose_name
        ordering = ["-hire_date"]


class Contract(models.Model):
    """
    合同信息模型
    """

    personnel = models.ForeignKey(
        Personnel, on_delete=models.CASCADE, related_name="contracts", verbose_name="关联人员"
    )
    contract_number = models.CharField(max_length=100, verbose_name="合同编号")
    start_date = models.DateField(verbose_name="合同开始日期")
    end_date = models.DateField(verbose_name="合同结束日期")

    CONTRACT_TYPE_CHOICES = [
        ("permanent", "长期合同"),
        ("fixed-term", "固定期限合同"),
    ]
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, verbose_name="合同类型")

    def __str__(self):
        return f"{self.personnel.name} - {self.contract_number}"

    class Meta:
        verbose_name = "合同信息"
        verbose_name_plural = verbose_name


class Education(models.Model):
    """
    教育背景模型
    """

    personnel = models.ForeignKey(
        Personnel, on_delete=models.CASCADE, related_name="educations", verbose_name="关联人员"
    )
    school = models.CharField(max_length=200, verbose_name="毕业院校")
    degree = models.CharField(max_length=100, verbose_name="学历")
    major = models.CharField(max_length=100, verbose_name="专业")
    start_date = models.DateField(verbose_name="开始日期")
    end_date = models.DateField(verbose_name="结束日期")

    def __str__(self):
        return f"{self.personnel.name} - {self.school}"

    class Meta:
        verbose_name = "教育背景"
        verbose_name_plural = verbose_name


class WorkExperience(models.Model):
    """
    工作经历模型
    """

    personnel = models.ForeignKey(
        Personnel, on_delete=models.CASCADE, related_name="work_experiences", verbose_name="关联人员"
    )
    company = models.CharField(max_length=200, verbose_name="公司名称")
    position = models.CharField(max_length=100, verbose_name="职位")
    start_date = models.DateField(verbose_name="开始日期")
    end_date = models.DateField(verbose_name="结束日期")
    description = models.TextField(verbose_name="工作描述", blank=True)

    def __str__(self):
        return f"{self.personnel.name} @ {self.company}"

    class Meta:
        verbose_name = "工作经历"
        verbose_name_plural = verbose_name


class ProfessionalQualification(models.Model):
    """
    职业资质模型
    """

    personnel = models.ForeignKey(
        Personnel, on_delete=models.CASCADE, related_name="qualifications", verbose_name="关联人员"
    )
    qualification_name = models.CharField(max_length=200, verbose_name="资质名称")
    issue_date = models.DateField(verbose_name="生效日期")
    expiry_date = models.DateField(verbose_name="失效日期", null=True, blank=True)
    certificate_id = models.CharField(max_length=100, verbose_name="证件编号", blank=True)

    def __str__(self):
        return f"{self.personnel.name} - {self.qualification_name}"

    class Meta:
        verbose_name = "职业资质"
        verbose_name_plural = verbose_name
        ordering = ["id"]


class FamilyMember(models.Model):
    """
    家庭成员模型
    """

    personnel = models.ForeignKey(
        Personnel, on_delete=models.CASCADE, related_name="family_members", verbose_name="关联人员"
    )
    name = models.CharField(max_length=100, verbose_name="姓名")
    relationship = models.CharField(max_length=50, verbose_name="与本人关系")
    id_card_number = EncryptedCharField(max_length=64, verbose_name="身份证号", blank=True)
    # max_length 调整为 64:18 字符明文 XOR+base64 加密后变 24 字符密文,18 长度不够
    contact_number = models.CharField(max_length=20, verbose_name="联系电话", blank=True)

    def __str__(self):
        return f"{self.personnel.name} - {self.name} ({self.relationship})"

    class Meta:
        verbose_name = "家庭成员"
        verbose_name_plural = verbose_name
        ordering = ["id"]
