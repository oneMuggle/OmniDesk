"""link_user_personnel — 将 CustomUser 关联到 Personnel 记录。

用法:
    # 默认策略:按 username == Personnel.name 匹配
    python manage.py link_user_personnel

    # 预览,不实际写库
    python manage.py link_user_personnel --dry-run

    # 指定批次号(便于回滚)
    python manage.py link_user_personnel --batch=2026-06-05-001

    # 解绑(将 CustomUser.personnel 置 None)
    python manage.py link_user_personnel --unlink

    # 按 batch_id 回滚
    python manage.py link_user_personnel --rollback --batch=2026-06-05-001

设计目标:
- 可回滚:每次写操作都落 AuditLogEntry,按 batch_id 可回滚
- 绑定后发 ACCOUNT_LINKED 通知给用户
- 默认 --dry-run 友好(必须显式 --batch 才正式生效的策略可选,此处保留 dry-run 显式开关)
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from personnel.models import Personnel
from users.models import AuditLogEntry

User = get_user_model()


STRATEGY_USERNAME_TO_NAME = "username_to_name"


def _default_batch_id() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")


class Command(BaseCommand):
    help = "将 CustomUser 关联到(或解绑)Personnel 记录,支持按批次回滚"

    def add_arguments(self, parser):
        parser.add_argument(
            "--strategy",
            default=STRATEGY_USERNAME_TO_NAME,
            choices=[STRATEGY_USERNAME_TO_NAME],
            help="匹配策略(目前仅支持 username_to_name)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="预览将进行的变更,不实际写入数据库",
        )
        parser.add_argument(
            "--unlink",
            action="store_true",
            help="解绑模式:将所有 CustomUser.personnel 置 None",
        )
        parser.add_argument(
            "--batch",
            default=None,
            help="批次 ID(用于审计与回滚),默认自动生成",
        )
        parser.add_argument(
            "--rollback",
            action="store_true",
            help="回滚模式:按 --batch 指定的批次 ID 还原",
        )

    # ---- 主入口 ----
    def handle(self, *args, **options):
        if options["rollback"]:
            self._rollback(options)
            return
        if options["unlink"]:
            self._unlink(options)
            return
        self._link(options)

    # ---- Link 模式 ----
    def _link(self, options):
        dry_run = options["dry_run"]
        batch_id = options["batch"] or _default_batch_id()

        if dry_run:
            self.stdout.write(self.style.WARNING("[Dry Run] 预览模式,不会写入数据库"))

        matched = skipped_linked = skipped_no_match = 0
        for user in User.objects.select_related("personnel").all():
            if user.personnel_id is not None:
                skipped_linked += 1
                continue
            personnel = Personnel.objects.filter(name=user.username).first()
            if personnel is None:
                skipped_no_match += 1
                self._write_audit(
                    user=user,
                    action=AuditLogEntry.ACTION_LINK_SKIPPED,
                    old_pid=None,
                    new_pid=None,
                    batch_id=batch_id,
                    metadata={"reason": "no_matching_personnel", "username": user.username},
                    dry_run=dry_run,
                )
                continue

            self.stdout.write(f"[Link] {user.username} -> {personnel.name} (id={personnel.id})")
            self._write_audit(
                user=user,
                action=AuditLogEntry.ACTION_LINK,
                old_pid=None,
                new_pid=personnel.id,
                batch_id=batch_id,
                metadata={"strategy": options["strategy"]},
                dry_run=dry_run,
            )
            if not dry_run:
                with transaction.atomic():
                    user.personnel = personnel
                    user.save(update_fields=["personnel"])
                # 发 ACCOUNT_LINKED 通知
                self._send_account_linked_notification(user, personnel)
            matched += 1

        self._print_summary(matched, skipped_linked, skipped_no_match, dry_run, batch_id)

    # ---- Unlink 模式 ----
    def _unlink(self, options):
        dry_run = options["dry_run"]
        batch_id = options["batch"] or _default_batch_id()

        if dry_run:
            self.stdout.write(self.style.WARNING("[Dry Run] 预览模式,不会写入数据库"))

        unlinked = skipped_no_link = 0
        for user in User.objects.select_related("personnel").filter(personnel__isnull=False):
            old_pid = user.personnel_id
            self.stdout.write(f"[Unlink] {user.username} <- personnel_id={old_pid}")
            self._write_audit(
                user=user,
                action=AuditLogEntry.ACTION_UNLINK,
                old_pid=old_pid,
                new_pid=None,
                batch_id=batch_id,
                metadata={},
                dry_run=dry_run,
            )
            if not dry_run:
                with transaction.atomic():
                    user.personnel = None
                    user.save(update_fields=["personnel"])
            unlinked += 1
        # 统计没绑定的用户(写 skipped 日志,便于审计)
        for user in User.objects.filter(personnel__isnull=True):
            self._write_audit(
                user=user,
                action=AuditLogEntry.ACTION_UNLINK_SKIPPED,
                old_pid=None,
                new_pid=None,
                batch_id=batch_id,
                metadata={"reason": "no_personnel"},
                dry_run=dry_run,
            )
            skipped_no_link += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"[Unlink] 完成 — 实际解绑: {unlinked}, 跳过(无关联): {skipped_no_link} (batch={batch_id})"
            )
        )

    # ---- Rollback 模式 ----
    def _rollback(self, options):
        batch_id = options["batch"]
        if not batch_id:
            raise CommandError("--rollback 必须配合 --batch=BATCH_ID")

        entries = AuditLogEntry.objects.filter(batch_id=batch_id).order_by("created_at")
        if not entries.exists():
            raise CommandError(f"批次 {batch_id} 不存在或无日志")

        restored = 0
        for entry in entries:
            user = entry.target_user
            if entry.action == AuditLogEntry.ACTION_LINK:
                # 回滚 link:将 user.personnel 置回 None(因为 link 前是 None)
                with transaction.atomic():
                    user.personnel = None
                    user.save(update_fields=["personnel"])
                restored += 1
            elif entry.action == AuditLogEntry.ACTION_UNLINK:
                # 回滚 unlink:把 user.personnel 恢复为 old_personnel_id
                if entry.old_personnel_id is None:
                    continue
                with transaction.atomic():
                    user.personnel_id = entry.old_personnel_id
                    user.save(update_fields=["personnel"])
                restored += 1
            # ACTION_LINK_SKIPPED / ACTION_UNLINK_SKIPPED 不需要回滚

        self.stdout.write(
            self.style.SUCCESS(f"[Rollback] 批次 {batch_id} 已回滚,共恢复 {restored} 条 user.personnel 状态")
        )

    # ---- 内部工具 ----
    def _write_audit(self, *, user, action, old_pid, new_pid, batch_id, metadata, dry_run):
        if dry_run:
            return
        AuditLogEntry.objects.create(
            batch_id=batch_id,
            actor=f"cli:{_default_batch_id()}",  # CLI 操作者
            action=action,
            target_user=user,
            old_personnel_id=old_pid,
            new_personnel_id=new_pid,
            metadata=metadata,
        )

    def _send_account_linked_notification(self, user, personnel):
        try:
            from notifications.service import NotificationService

            NotificationService.create(
                user=user,
                type="account_linked",
                title="账号已关联人员档案",
                content=(
                    f"您的账号 {user.username} 已成功关联到人员档案"
                    f"「{personnel.name}」,此后您可使用个人中心查看/维护自己的信息,"
                    f"并在值班/岗位变动时收到系统通知。"
                ),
                link="/me/profile",
            )
        except Exception as exc:
            # 通知发送失败不应阻塞主流程
            self.stderr.write(
                self.style.WARNING(f"[Notification] 发送 ACCOUNT_LINKED 失败(忽略): user={user.username}, err={exc}")
            )

    def _print_summary(self, matched, skipped_linked, skipped_no_match, dry_run, batch_id):
        prefix = "[Dry Run] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Link 完成 — 匹配绑定: {matched}, 跳过(已绑定): {skipped_linked}, "
                f"跳过(无匹配): {skipped_no_match} (batch={batch_id})"
            )
        )
        self.stdout.write(self.style.SUCCESS("=" * 60))
