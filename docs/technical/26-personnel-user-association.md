# 人员-用户关联方案

> **章节版本**:v0.4.0(2026-06-05)
> **状态**:✅ 已完成实施
> **关联章节**:`07-user-permissions.md`(用户与权限)、`08-schedule-trial.md`(排班)

## 概述

OmniDesk 中"人员"(`Personnel`)与"用户"(`CustomUser`)是**两个独立但可关联**的概念:

- **人员(Personnel)**:详细电子化人事档案(姓名、工号、岗位、家庭、教育、合同、绩效、奖惩、紧急联系人等)
- **用户(CustomUser)**:系统登录账号(username、密码、JWT 令牌、所属组)

**关联的核心价值**:
1. 人员变动(岗位/部门/值班)能精确推送到对应用户的通知中心
2. 登录用户能自助维护自己的人员信息(电话/地址/紧急联系人)
3. 离职/调岗有清晰的人员-账号联动工作流

## 核心设计

### 数据模型

```python
# users/models.py
class CustomUser(AbstractUser):
    personnel = models.OneToOneField(
        "personnel.Personnel",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="user_account",
        verbose_name="关联人员",
    )
```

- 1:1 严格约束(`OneToOneField` DB 层唯一)
- 反向访问:`personnel.user_account`
- 删除 User 时 `SET_NULL`,人员档案永留

### 字段级权限矩阵(详见 plan §4.1)

| Personnel 字段 | 用户本人 | HR (Manager 组) | Admin |
|---|---|---|---|
| `name`、`id_card_number`、`hire_date`、`department`、`position`、`status` | ❌ 只读 | ✅ | ✅ |
| `phone_number`、`address`、`date_of_birth` | ✅ 可改 | ✅ | ✅ |
| `family_members`、`educations` 等子表 | ✅ 可改 | ❌ 只读(部分) | ✅ |

### 三层防护

| 层 | 实现 |
|---|---|
| **L1 Serializer** | `PersonnelSelfSerializer`(`personnel/serializers.py`)字段白名单 |
| **L2 ViewSet** | `MyPersonnelView.perform_update`(`users/views.py`)服务端白名单二次过滤 |
| **L3 Model** | `Personnel.clean()`(`personnel/models.py`)数据完整性校验 |

## API 端点

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/api/users/me/personnel/` | GET | IsAuthenticated | 当前用户的人员信息(无 → 404) |
| `/api/users/me/personnel/` | PATCH | IsAuthenticated | 改白名单字段 + 自动发"信息更新"通知 |
| `/api/notifications/` | GET | IsAuthenticated | 我的通知列表(分页 + 类型/已读过滤) |
| `/api/notifications/{id}/mark_read/` | PATCH | IsAuthenticated(本人) | 标记已读(同步 `read_at`) |
| `/api/notifications/mark_all_read/` | POST | IsAuthenticated | 全部已读(同步 `read_at`) |
| `/api/notifications/unread_count/` | GET | IsAuthenticated | 未读数(前端 5s 轮询) |
| `/api/personnel/link/` | POST | IsAdmin | Admin 绑定/解绑 User ↔ Personnel |

## 通知触发矩阵

| 业务事件 | Signal | 通知类型 | 收件人 |
|---|---|---|---|
| Schedule 创建 | `Schedule.post_save` | `schedule_change` | duty_person/duty_leader 关联 user |
| Announcement 创建 | `Announcement.post_save` | `announcement` | 全部用户(除作者) |
| **Personnel 岗位/部门变更** | `Personnel.pre/post_save` | `position_changed` | personnel 关联 user |
| **FamilyMember 增/改** | `FamilyMember.post_save` | `emergency_contact` | personnel 关联 user |
| ComplianceIssue 创建 | `ComplianceIssue.post_save` | `compliance_issue` | project.manager |
| Memo 创建 | `Memo.post_save` | `memo_due` | memo.user |

## 通知去重 / 聚合

- `dedupe_key` 字段(24h 窗口 + 同 user + 同 key + 未读 → 合并,body 追加 `[追加] ...`)
- 优先级:LOW/NORMAL/HIGH/URGENT(1-4)
- 免打扰:未来 `NotificationPreference` 支持(P1-2 模型已就位)
- 渠道:站内信必发,邮件/短信待 Phase 5+

## 管理命令

```bash
# 预览绑定(不写库)
python manage.py link_user_personnel --dry-run

# 正式绑定
python manage.py link_user_personnel --batch=2026-06-05-001

# 解绑
python manage.py link_user_personnel --unlink --batch=2026-06-05-002

# 按批次回滚
python manage.py link_user_personnel --rollback --batch=2026-06-05-001
```

所有写操作都写 `users.AuditLogEntry`(含 `batch_id` 用于回滚)。

## 前端集成

| 路径 | 组件 | 说明 |
|---|---|---|
| `/me/personnel` | `MyPersonnelInfo.jsx` | 我的信息自助维护 |
| `/notifications` | `NotificationCenter.jsx` | 通知中心(分页 + 过滤) |
| Header(可选) | `NotificationBell.jsx` | 铃铛 + 5s 轮询未读数 |

**字段级权限在 UI 中的体现**:只读字段用 `<Input disabled />` + `<Tooltip title="由 HR 维护">` 提示。

## 关键文件清单

**后端**:
- `omni_desk_backend/notifications/models.py`(扩展 Notification + 新增 NotificationPreference)
- `omni_desk_backend/notifications/service.py`(NotificationService 扩展 priority/dedupe_key)
- `omni_desk_backend/notifications/signals.py`(Personnel/FamilyMember signals)
- `omni_desk_backend/notifications/views.py`(同步 read_at)
- `omni_desk_backend/personnel/serializers.py`(PersonnelSelfSerializer)
- `omni_desk_backend/personnel/models.py`(Personnel.clean())
- `omni_desk_backend/personnel/views.py`(权限调整 IsAdminOrManagerOrReadOnly)
- `omni_desk_backend/users/permissions.py`(IsHR + IsAdminOrManagerOrReadOnly)
- `omni_desk_backend/users/views.py`(MyPersonnelView)
- `omni_desk_backend/users/models.py`(AuditLogEntry)
- `omni_desk_backend/users/management/commands/link_user_personnel.py`
- 2 个新 migration:`notifications/0003_*`、`users/0002_auditlogentry`

**前端**:
- `omni_desk_frontend/src/features/personnel/api/personnelApi.js`(getMyPersonnel / updateMyPersonnel)
- `omni_desk_frontend/src/features/personnel/components/MyPersonnelInfo.jsx`
- `omni_desk_frontend/src/features/notifications/components/NotificationBell.jsx`
- `omni_desk_frontend/src/features/notifications/components/NotificationCenter.jsx`
- `omni_desk_frontend/src/routes/index.jsx`(注册 `/me/personnel`、`/notifications`)

## 已知风险与限制

1. **PersonnelViewSet 权限放宽**:从 `IsAdminOrReadOnly` 改为 `IsAdminOrManagerOrReadOnly`(HR 可写)— 见 CHANGELOG [0.4.0]
2. **邮件/短信渠道**:本次未实现(站内信必发;邮件待 SMTP 配置后接入)
3. **批量排班通知风暴**:`bulk_create` 时通过 `NotificationService` 聚合到单条"本月值班已生成"(留作 P5 收尾优化)
4. **审计日志**:`actor` 字段简化为字符串(`cli:<timestamp>`),未关联到具体 User,留作后续优化

## 实施记录

- **计划文档**:`docs/plans/2026-06-05_personnel-user-association.md`(实施完成后已删除)
- **测试统计**:后端 648 passed + 1 skipped + 2 xfailed,整体覆盖率 80.57%
- **TDD 工作流**:全 Phase 严格 RED → GREEN → IMPROVE
