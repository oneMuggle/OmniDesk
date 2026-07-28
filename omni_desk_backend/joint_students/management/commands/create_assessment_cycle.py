"""手动创建本月 (或指定年月) 的考核批次。"""
from datetime import date

from django.core.management.base import BaseCommand

from joint_students.models import AssessmentCycle
from joint_students.services.cycle import create_cycle


class Command(BaseCommand):
    help = "手动创建本月 (或指定年月) 的考核批次"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="年份 (默认今年)")
        parser.add_argument("--month", type=int, help="月份 (默认本月)")
        parser.add_argument(
            "--source", type=str, default="manual",
            choices=[AssessmentCycle.TRIGGER_AUTO, AssessmentCycle.TRIGGER_MANUAL],
            help="触发来源 (默认 manual)",
        )

    def handle(self, *args, **opts):
        year = opts.get("year") or date.today().year
        month = opts.get("month") or date.today().month
        cycle = create_cycle(
            year, month, trigger_source=opts["source"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"批次 {year}-{month:02d} 创建成功: id={cycle.id} status={cycle.status}"
        ))
