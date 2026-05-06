from django.db import models


class Position(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="职位名称")

    class Meta:
        verbose_name = "职位"
        verbose_name_plural = "职位管理"
        ordering = ['name']

    def __str__(self):
        return self.name

class Personnel(models.Model):
    """
    核心人员信息模型
    """
    # Basic Info
    name = models.CharField(max_length=100, verbose_name="姓名")
    id_card_number = models.CharField(max_length=18, unique=True, null=True, blank=True, verbose_name='身份证号')
    date_of_birth = models.DateField(verbose_name="出生年月", null=True, blank=True)
    phone_number = models.CharField(max_length=20, verbose_name="联系电话", blank=True)
    address = models.TextField(verbose_name="家庭住址", blank=True)

    # Employment Info
    hire_date = models.DateField(verbose_name="入职日期", null=True, blank=True)
    department = models.CharField(max_length=100, verbose_name="部门", blank=True)
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="职位"
    )

    STATUS_CHOICES = [
        ('active', '在职'),
        ('inactive', '离职'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name="员工状态")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "人员信息"
        verbose_name_plural = verbose_name
        ordering = ['-hire_date']

class Contract(models.Model):
    """
    合同信息模型
    """
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name='contracts', verbose_name="关联人员")
    contract_number = models.CharField(max_length=100, verbose_name="合同编号")
    start_date = models.DateField(verbose_name="合同开始日期")
    end_date = models.DateField(verbose_name="合同结束日期")

    CONTRACT_TYPE_CHOICES = [
        ('permanent', '长期合同'),
        ('fixed-term', '固定期限合同'),
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
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name='educations', verbose_name="关联人员")
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
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name='work_experiences', verbose_name="关联人员")
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
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name='qualifications', verbose_name="关联人员")
    qualification_name = models.CharField(max_length=200, verbose_name="资质名称")
    issue_date = models.DateField(verbose_name="生效日期")
    expiry_date = models.DateField(verbose_name="失效日期", null=True, blank=True)
    certificate_id = models.CharField(max_length=100, verbose_name="证件编号", blank=True)

    def __str__(self):
        return f"{self.personnel.name} - {self.qualification_name}"

    class Meta:
        verbose_name = "职业资质"
        verbose_name_plural = verbose_name
        ordering = ['id']

class FamilyMember(models.Model):
    """
    家庭成员模型
    """
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name='family_members', verbose_name="关联人员")
    name = models.CharField(max_length=100, verbose_name="姓名")
    relationship = models.CharField(max_length=50, verbose_name="与本人关系")
    id_card_number = models.CharField(max_length=18, verbose_name="身份证号", blank=True)
    contact_number = models.CharField(max_length=20, verbose_name="联系电话", blank=True)

    def __str__(self):
        return f"{self.personnel.name} - {self.name} ({self.relationship})"

    class Meta:
        verbose_name = "家庭成员"
        verbose_name_plural = verbose_name
        ordering = ['id']
