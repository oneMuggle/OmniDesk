"""清理测试数据管理命令

按 seeder 反向依赖顺序删除测试数据，避免外键约束冲突。
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from events.management.seeders import discover_seeders

User = get_user_model()


class Command(BaseCommand):
    help = "清理 seed_data 插入的测试数据（按反向依赖顺序删除）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            "-y",
            action="store_true",
            help="跳过确认提示",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="预览将被删除的数据，不实际执行",
        )
        parser.add_argument(
            "--seed",
            type=str,
            default=None,
            help="只清理指定 seeder 的数据（如 --seed 人员管理）",
        )

    def handle(self, *args, **options):
        seeders = discover_seeders({})

        # Filter to a specific seeder if requested
        target_name = options.get("seed")
        if target_name:
            seeders = [s for s in seeders if s.name == target_name or s.__class__.__name__ == target_name]
            if not seeders:
                self.stdout.write(self.style.ERROR(f"未找到名为 '{target_name}' 的 seeder"))
                available = [f"{s.name} ({s.__class__.__name__})" for s in discover_seeders({})]
                self.stdout.write(f"可用的 seeder: {', '.join(available)}")
                return

        # Reverse order: delete dependents first
        seeders = list(reversed(seeders))

        # Collect deletion info
        deletion_plan = []
        for seeder in seeders:
            model_counts = []
            for model in getattr(seeder, "models", []):
                if model is not None:
                    count = model.objects.count()
                    if count > 0:
                        model_counts.append((model, count))
            if model_counts:
                deletion_plan.append((seeder, model_counts))

        if not deletion_plan:
            self.stdout.write(self.style.SUCCESS("没有测试数据需要清理"))
            return

        # Display plan
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(self.style.WARNING("测试数据清理计划"))
        self.stdout.write(self.style.WARNING("=" * 60))

        total_rows = 0
        for seeder, model_counts in deletion_plan:
            self.stdout.write(f"\n[{seeder.name}] ({seeder.__class__.__name__})")
            for model, count in model_counts:
                self.stdout.write(f"  {model.__name__:30s} {count} 条")
                total_rows += count

        self.stdout.write(f"\n总计: 约 {total_rows} 条记录将被删除")

        if options.get("dry_run"):
            self.stdout.write(self.style.WARNING("\n[Dry Run] 以上为预览，未实际执行"))
            return

        if not options.get("force"):
            self.stdout.write(self.style.WARNING("\n此操作不可恢复！"))
            confirm = input("确认执行？输入 yes 继续: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("已取消"))
                return

        # Execute deletions
        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("开始清理测试数据"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        total_deleted = 0
        for seeder, model_counts in deletion_plan:
            self.stdout.write(f"\n[{seeder.name}]...")
            for model, count in model_counts:
                try:
                    model.objects.all().delete()
                    self.stdout.write(f"  {model.__name__:30s} 删除 {count} 条")
                    total_deleted += count
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  {model.__name__:30s} 失败: {e}"))

        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"清理完成！共删除 {total_deleted} 条记录"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
