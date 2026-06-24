"""人员信息 Seeder：岗位、人员、合同、教育、工作经历、资质、家庭成员"""

import random
from datetime import date, timedelta
from personnel.models import (
    Position,
    Personnel,
    Contract,
    Education,
    WorkExperience,
    ProfessionalQualification,
    FamilyMember,
)
from events.management.seeders.base import BaseSeeder

FIRST_NAMES = [
    "张伟",
    "李娜",
    "王芳",
    "刘洋",
    "陈静",
    "杨帆",
    "赵磊",
    "黄丽",
    "周涛",
    "吴敏",
    "徐强",
    "孙鹏",
    "马超",
    "朱琳",
    "胡斌",
    "郭艳",
    "何勇",
    "林峰",
    "高远",
    "罗军",
    "梁博",
    "宋佳",
    "谢宇",
    "韩雪",
    "唐亮",
    "许文",
    "邓辉",
    "萧然",
    "冯程",
    "曹杰",
]
DEPARTMENTS = [
    "研发部",
    "测试部",
    "质量部",
    "生产部",
    "工艺部",
    "设备部",
    "安全部",
    "综合管理部",
]
POSITIONS = [
    "研究员",
    "高级工程师",
    "工程师",
    "技师",
    "助理工程师",
    "项目经理",
    "质量工程师",
    "试验员",
]


def _random_date(start_year=2018, end_year=2025):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


class PersonnelSeeder(BaseSeeder):
    name = "人员管理"
    order = 10
    models = [Position, Personnel, Contract, Education, WorkExperience, ProfessionalQualification, FamilyMember]

    def seed(self):
        count = self.context.get("personnel_count", 15)

        # 岗位
        positions = {}
        for name in POSITIONS:
            obj, _ = self.safe_get_or_create(Position, name=name)
            positions[name] = obj

        # 人员及详细信息
        created_personnel = []
        for i in range(count):
            name = FIRST_NAMES[i % len(FIRST_NAMES)]
            existing = Personnel.objects.filter(name=name).count()
            if existing > 0:
                name = f"{name}{existing + 1}"

            dept = random.choice(DEPARTMENTS)
            pos = random.choice(list(positions.values()))
            hire = _random_date(2019, 2025)
            birth = hire - timedelta(days=random.randint(365 * 22, 365 * 45))

            personnel, _ = self.safe_get_or_create(
                Personnel,
                name=name,
                defaults={
                    # 18 字符真实身份证 — model 字段已改为 max_length=64,密文能放下
                    "id_card_number": f"110101{random.randint(19800101, 19991231):08d}{random.randint(1000, 9999):04d}",
                    "date_of_birth": birth,
                    "phone_number": f"1{random.choice([3, 5, 7, 8, 9])}{random.randint(100000000, 999999999):09d}",
                    "address": f"北京市{random.choice(['朝阳区', '海淀区', '西城区', '东城区', '丰台区'])}某某街道{random.randint(1, 200)}号",
                    "hire_date": hire,
                    "department": dept,
                    "position": pos,
                    "status": "active",
                },
            )
            created_personnel.append(personnel)

            # 合同
            for j in range(random.choice([1, 1, 2])):
                if j == 0:
                    c_start = hire
                else:
                    prev = Contract.objects.filter(personnel=personnel).latest("end_date")
                    c_start = prev.end_date + timedelta(days=1)
                c_end = c_start + timedelta(days=random.choice([365, 365 * 2, 365 * 3]))

                self.safe_get_or_create(
                    Contract,
                    personnel=personnel,
                    contract_number=f"CTR-{hire.year}-{personnel.id:04d}-{j + 1}",
                    defaults={
                        "start_date": c_start,
                        "end_date": c_end,
                        "contract_type": random.choice(["permanent", "fixed-term"]),
                    },
                )

            # 教育背景
            schools = [
                "清华大学",
                "北京大学",
                "北京航空航天大学",
                "北京理工大学",
                "中国科学院大学",
                "浙江大学",
                "上海交通大学",
                "复旦大学",
            ]
            majors = ["计算机科学", "电子工程", "机械工程", "材料科学", "化学工程", "自动化", "物理学", "通信工程"]
            degrees = ["本科", "硕士", "博士"]

            for _ in range(random.choice([1, 1, 2])):
                edu_start = _random_date(2000, 2018)
                edu_end = edu_start + timedelta(days=random.choice([365 * 3, 365 * 4, 365 * 5, 365 * 6]))
                self.safe_get_or_create(
                    Education,
                    personnel=personnel,
                    school=random.choice(schools),
                    defaults={
                        "degree": random.choice(degrees),
                        "major": random.choice(majors),
                        "start_date": edu_start,
                        "end_date": edu_end,
                    },
                )

            # 工作经历
            companies = [
                "华为技术有限公司",
                "中兴通讯",
                "中国电子科技集团",
                "航天科技集团",
                "中芯国际",
                "京东方",
                "比亚迪",
                "宁德时代",
            ]
            for _ in range(random.choice([0, 1, 1, 2])):
                w_start = _random_date(2015, 2023)
                w_end = w_start + timedelta(days=random.randint(365, 365 * 5))
                self.safe_get_or_create(
                    WorkExperience,
                    personnel=personnel,
                    company=random.choice(companies),
                    start_date=w_start,
                    end_date=w_end,
                    defaults={
                        "position": random.choice(POSITIONS),
                        "description": f"负责{random.choice(['产品研发', '质量控制', '项目管理', '工艺优化', '设备维护'])}相关工作",
                    },
                )

            # 职业资质
            if random.random() < 0.3:
                quals = ["ISO9001内审员", "六西格玛绿带", "项目管理师", "注册安全工程师", "电气工程师资格证"]
                issue = _random_date(2020, 2025)
                self.safe_get_or_create(
                    ProfessionalQualification,
                    personnel=personnel,
                    qualification_name=random.choice(quals),
                    defaults={
                        "issue_date": issue,
                        "expiry_date": issue + timedelta(days=365 * 3),
                        "certificate_id": f"QUAL-{random.randint(10000, 99999)}",
                    },
                )

            # 家庭成员
            if random.random() < 0.5:
                relationships = ["配偶", "父亲", "母亲", "子女", "兄弟", "姐妹"]
                used = set()
                for _ in range(random.choice([1, 2])):
                    rel = random.choice(relationships)
                    while rel in used:
                        rel = random.choice(relationships)
                    used.add(rel)
                    self.safe_get_or_create(
                        FamilyMember,
                        personnel=personnel,
                        name=random.choice(FIRST_NAMES),
                        defaults={
                            "relationship": rel,
                            "id_card_number": f"110101{random.randint(19600101, 20001231):08d}{random.randint(1000, 9999):04d}",
                            "contact_number": f"1{random.choice([3, 5, 7, 8, 9])}{random.randint(100000000, 999999999):09d}",
                        },
                    )

        # 写入上下文供后续 seeder 使用
        self.context["positions"] = positions
        self.context["personnel"] = created_personnel

        return [
            ("岗位", len(positions)),
            ("人员", len(created_personnel)),
            ("合同", Contract.objects.count()),
            ("教育", Education.objects.count()),
            ("工作经历", WorkExperience.objects.count()),
            ("资质", ProfessionalQualification.objects.count()),
            ("家庭成员", FamilyMember.objects.count()),
        ]
