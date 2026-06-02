from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from events.management.seeders import discover_seeders, SEEDER_REGISTRY

User = get_user_model()


class Command(BaseCommand):
    help = "批量插入测试数据：人员、试验、排班、会议室、传感器、项目等"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="指定关联的用户名（默认使用第一个用户或超级用户）",
        )
        parser.add_argument(
            "--personnel-count",
            type=int,
            default=15,
            help="创建的人员数量（默认15）",
        )
        parser.add_argument(
            "--seed",
            type=str,
            default=None,
            help="只运行指定 seeder（如 --seed PersonnelSeeder）",
        )
        parser.add_argument(
            "--list-seeders",
            action="store_true",
            help="列出所有可用的 seeder",
        )

    def handle(self, *args, **options):
        # --list-seeders: 列出可用 seeder
        if options["list_seeders"]:
            self.stdout.write("可用的 Seeder：")
            for module_path, class_name, default_enabled in SEEDER_REGISTRY:
                status = "启用" if default_enabled else "禁用"
                self.stdout.write(f"  {class_name:<30} [{status}]")
            return

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("开始批量插入测试数据"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        # 获取或创建关联用户
        username = options.get("user")
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stdout.write(self.style.WARNING(f"用户 '{username}' 不存在，尝试使用第一个用户"))
                user = User.objects.first()
        else:
            user = User.objects.first()

        if not user:
            self.stdout.write(self.style.WARNING("未找到任何用户，跳过需要用户关联的数据"))

        # 构建共享上下文
        context = {
            "user": user,
            "personnel_count": options["personnel_count"],
        }

        # 动态加载 seeder
        enabled_name = options.get("seed")
        seeders = discover_seeders(context, enabled_names=[enabled_name] if enabled_name else None)

        if not seeders:
            self.stdout.write(self.style.WARNING(f"未找到可用的 seeder（filter: {enabled_name}）"))
            return

        # 按顺序执行
        for i, seeder in enumerate(seeders, 1):
            self.stdout.write(f"\n[{i}/{len(seeders)}] {seeder.name}...")
            try:
                results = seeder.seed()
                for label, count in results:
                    self.stdout.write(f"  {label}: {count} 条")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  失败: {e}"))

        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("测试数据插入完成！"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
