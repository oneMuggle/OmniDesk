"""项目与文档 Seeder：项目、标签、文档模板、书籍/章节"""

import random
from datetime import date, timedelta
from projects.models import Project
from documents.models import DocumentTemplate, Tag, Book, Chapter
from events.management.seeders.base import BaseSeeder


class ProjectSeeder(BaseSeeder):
    name = "项目与文档"
    order = 50
    models = [Project, Tag, DocumentTemplate, Book, Chapter]

    def seed(self):
        user = self.context.get("user")

        project_defs = [
            ("新一代传感器研发项目", "研发高精度、低功耗的新一代温度传感器，预计2026年底完成样机测试", "进行中", 60),
            ("质量管理体系升级", "按照ISO9001:2015标准升级质量管理体系，完善文档和流程", "进行中", 30),
            ("试验设备智能化改造", "对现有试验设备进行智能化改造，实现远程监控和数据自动采集", "进行中", 45),
            ("安全生产标准化建设", "建立安全生产标准化体系，通过第三方认证", "已完成", 90),
            ("人才梯队建设计划", "建立技术人才梯队，培养后备技术骨干", "进行中", 120),
        ]

        projects = []
        for name, desc, status, duration in project_defs:
            start = date(2025, 1, 1) + timedelta(days=random.randint(0, 180))
            end = start + timedelta(days=duration)
            obj, _ = self.safe_get_or_create(
                Project,
                name=name,
                defaults={"description": desc, "status": status, "start_date": start, "end_date": end, "manager": user},
            )
            projects.append(obj)

        # 标签
        tags = ["试验", "传感器", "质量", "安全", "研发", "标准", "培训", "管理"]
        tag_objs = []
        for name in tags:
            obj, _ = Tag.objects.get_or_create(name=name)
            tag_objs.append(obj)

        # 文档模板
        if projects:
            doc_defs = [
                ("试验报告模板", "tech_design", "本模板用于编写试验报告，包含试验目的、方法、结果和结论等部分。"),
                ("项目进度报告", "progress_report", "项目进度月度报告模板，包含里程碑完成情况和下月计划。"),
                ("会议纪要模板", "meeting_minutes", "各类会议的纪要模板，包含议题、决议和责任人。"),
            ]
            for name, doc_type, content in doc_defs:
                self.safe_get_or_create(
                    DocumentTemplate,
                    name=name,
                    defaults={"template_type": doc_type, "content": content, "project": projects[0], "owner": user},
                )

        # 书籍/章节
        if projects:
            book, _ = self.safe_get_or_create(
                Book,
                title="传感器技术手册",
                defaults={"author": "技术部", "description": "传感器相关技术知识的汇总手册", "project": projects[0]},
            )
            book.tags.set(tag_objs[:3])

            chapters = [
                ("传感器概述", "传感器是一种将物理量转换为电信号的装置..."),
                ("温度传感器原理", "温度传感器利用材料的热电效应、电阻温度特性等原理..."),
                ("压力传感器分类", "压力传感器按工作原理可分为应变式、压阻式、电容式等..."),
                ("传感器选型指南", "选择传感器时需考虑测量范围、精度、响应时间等参数..."),
            ]
            for i, (title, content) in enumerate(chapters):
                Chapter.objects.get_or_create(
                    book=book,
                    title=title,
                    defaults={"content_md": content, "content_html": f"<p>{content}</p>", "order": i + 1},
                )

        self.context["projects"] = projects
        return [
            ("项目", len(projects)),
            ("标签", len(tag_objs)),
            ("文档模板", 3),
            ("书籍章节", 4),
        ]
