"""create_smoke_user — 创建/更新部署冒烟测试专用账号(P0-5)。

依据 docs/plans/2026-08-17_pre-deploy-hardening.md §6.3 决策项 3:
smoke 阶段 12 需真实账密登录覆盖 argon2 hasher(production 与 test 的 MD5 差异),
不能用管理员账号(凭据混入 .env / CI secrets 风险大)。

此命令幂等:已存在则只更新密码 + 锁定属性;不存在则创建。

用法:
    # 从 .env 读取 SMOKE_TEST_USER/PASSWORD(默认)
    python manage.py create_smoke_user

    # 显式传参(覆盖环境变量)
    python manage.py create_smoke_user --username=smoke-test-bot --password=...

    # 预览(只读,不实际写入)
    python manage.py create_smoke_user --dry-run

    # 重置(强制更新密码)
    python manage.py create_smoke_user --reset

    # 止血:禁用账号
    python manage.py create_smoke_user --disable

安全约束:
- is_staff=False is_superuser=False:进不了 Django admin
- 不加任何 Group/permission:默认只能调用 /api/auth/login/ 拿到 JWT
- email 字段置空(防止恢复攻击面)
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()

DEFAULT_USERNAME = "smoke-test-bot"


class Command(BaseCommand):
    help = "创建或更新部署冒烟测试专用账号(无管理权限)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            # 变量存在但为空(如示例文件占位行 SMOKE_TEST_USER=)时必须 fallback 到默认名,
            # 不能直接 .get(key, default) — 那只在变量"未设置"时才返回 default,空值会传空串。
            default=os.environ.get("SMOKE_TEST_USER") or DEFAULT_USERNAME,
            help=f"smoke 账号用户名(默认读 $SMOKE_TEST_USER,未设置/为空时 fallback {DEFAULT_USERNAME!r})",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("SMOKE_TEST_PASSWORD", ""),
            help="smoke 账号密码(默认读 $SMOKE_TEST_PASSWORD;为空则要求显式传参)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只读,不实际写入数据库",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="强制更新密码(默认仅在用户不存在时设密码)",
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help="禁用账号(active=False),用于事故止血",
        )

    def handle(self, *args, **options):
        username: str = options["username"]
        password: str = options["password"]
        dry_run: bool = options["dry_run"]
        reset: bool = options["reset"]
        disable: bool = options["disable"]

        if not username:
            raise CommandError("username 不能为空(传 --username 或设 $SMOKE_TEST_USER)")

        if disable:
            self._set_active(username, active=False, dry_run=dry_run)
            return

        if not password:
            raise CommandError("password 不能为空(传 --password 或设 $SMOKE_TEST_PASSWORD);若要禁用账号请用 --disable")

        user, created = User.objects.get_or_create(username=username)
        action = "create" if created else "update"

        if dry_run:
            self.stdout.write(
                f"[DRY-RUN] 将 {action} smoke 账号: {username} (is_staff=False, is_superuser=False, email=None)"
            )
            # dry-run 路径如果触发了 create,需要回滚避免污染测试
            if created:
                user.delete()
            return

        # 锁定属性:无论 update 还是 create,都强制为非管理员
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.email = None  # 邮箱强制置空(防恢复攻击;user.email or None 在已有 email 时不退化)
        if created or reset:
            user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ smoke 账号 {action} 成功: {username} "
                f"(is_staff={user.is_staff}, is_superuser={user.is_superuser}, "
                f"is_active={user.is_active}, password_set={created or reset})"
            )
        )

    def _set_active(self, username: str, *, active: bool, dry_run: bool) -> None:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"账号 {username!r} 不存在,无法 disable") from exc

        if dry_run:
            self.stdout.write(f"[DRY-RUN] 将 active={active} → {username}")
            return

        user.is_active = active
        user.save(update_fields=["is_active"])
        status = "已禁用" if not active else "已启用"
        self.stdout.write(self.style.WARNING(f"⚠️ 账号 {username} {status}"))
