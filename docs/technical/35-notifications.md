# 35. 通知中心 (notifications app)

> 适用版本:OmniDesk v0.7+
> 关联:通知双轨轮询统一(R4-B1,前端)、39-observability.md(日志)、27-logging-standards.md

## 一、概述

`notifications` 应用是站内通知中心:各业务模块通过信号(signals.py)或 `NotificationService` 创建通知落库,前端通过 REST API 轮询拉取未读列表与数量。当前**仅实现站内通知**(DB 落库 + REST 轮询);邮件 / SMS 渠道仅在 `NotificationPreference.channel_settings` 中预留设计,未实现实际发送。

## 二、架构

```
业务事件(Schedule / Announcement / ComplianceIssue / Memo /
        Personnel 岗位变动 / FamilyMember 紧急联系人 / …)
  └── post_save/pre_save 信号  ──▶ NotificationService.create()
        │                           └── dedupe_key 命中? 24h 内同 key 未读 → 追加合并
        ▼
Notification 落库(user 维度)
  └── 前端轮询 /api/notifications/
        ├── GET ?type=&is_read=      列表(按 -created_at)
        ├── GET unread_count/        未读数
        └── PATCH mark_read / mark_all_read
```

## 三、数据模型

### 3.1 Notification(通知)

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | FK → CustomUser | 接收用户(related_name=`notifications`) |
| `type` | CharField(30) | 通知类型(见下表),db_index |
| `priority` | PositiveSmallIntegerField | 1 低 / 2 普通 / 3 高 / 4 紧急,默认普通 |
| `title` / `content` | CharField / TextField | 标题 / 内容 |
| `link` | CharField(500) | 跳转链接(可空) |
| `is_read` / `read_at` | Boolean / DateTime | 已读状态与时间 |
| `dedupe_key` | CharField(128) | 去重键,db_index |
| `is_system` | Boolean | 系统通知标记 |
| `created_at` / `updated_at` | DateTime | 自动时间戳 |

索引:`notif_user_read_idx`(`user`, `is_read`, `-created_at`)支撑未读列表查询;`notif_dedupe_idx`(`dedupe_key`, `created_at`)支撑去重查找。

### 3.2 NotificationPreference(用户通知偏好)

- `user`:OneToOne → CustomUser。
- `quiet_hours_start` / `quiet_hours_end`:免打扰时段(可空)。
- `channel_settings`:JSONField,示例 `{"email": {"schedule_change": true, "announcement": false}, "sms": {...}}`;未在 JSON 中列出的 type 默认全渠道发送。**当前仅数据结构预留,渠道发送逻辑未实现。**

### 3.3 通知类型(TYPE_CHOICES,部分)

排班:`schedule_change`、`schedule_swap_requested/approved/rejected/cancelled/expired`;公告:`announcement`;备忘录:`memo_due`;校准:`calibration_reminder`;项目:`project_update`;合规:`compliance_issue`、`compliance_due`;人员:`position_changed`、`account_linked`、`emergency_contact`、`training_assigned`、`reward_punishment`;系统:`system`、`paperless_down`、`paperless_recovered`。

## 四、API 端点

路由:`/api/notifications/`(DefaultRouter 注册 `NotificationViewSet`),全部要求登录,`get_queryset()` 只返回当前用户通知。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/notifications/` | GET | 当前用户通知列表(可 `?type=`、`?is_read=` 过滤) |
| `/api/notifications/{id}/` | GET / PATCH / DELETE | 单条通知(读 / 标已读 / 删) |
| `/api/notifications/unread_count/` | GET | 未读数 `{"unread_count": N}` |
| `/api/notifications/{id}/mark_read/` | PATCH | 单条标已读(写 `is_read` + `read_at`) |
| `/api/notifications/mark_all_read/` | POST | 全部标已读(批量 update) |

序列化输出含 `type_display`(类型中文名)。

## 五、去重机制(NotificationService)

`NotificationService.create(user, type, title, content, link="", priority, dedupe_key="")`:

- 传 `dedupe_key` 时,先查「24h 窗口(`DEDUPE_WINDOW = timedelta(hours=24)`) + 同 user + 同 key + 未读」的原通知;命中则把新 content 以 `\n[追加]` 合并进原通知(`update_fields=["content", "updated_at"]`),返回原通知。
- 未命中或未传 key,`transaction.atomic()` 内新建。

典型用法:公告 fan-out 用 `dedupe_key=f"announcement:{公告id}:{用户id}"`,便于事后按公告/用户定位与清理。

## 六、信号触发源(signals.py)

| 信号 | 通知类型 | 说明 |
|------|----------|------|
| `Schedule` post_save(created) | `schedule_change` | 通知值班人员/值班领导 |
| `Announcement` post_save(created) | `announcement` | **fan-out**:`bulk_create(batch_size=500)` 批量落库,排除作者本人,每条携带 dedupe_key |
| `ComplianceIssue` post_save(created) | `compliance_issue` | 通知项目负责人 |
| `Memo` post_save(created, 有 reminder_time) | `memo_due` | 通知备忘录属主 |
| `Personnel` pre_save + post_save | `position_changed` | 岗位/部门变更(对比 pre_save 快照)通知本人 |
| `FamilyMember` post_save | `emergency_contact` | 紧急联系人新增/更新通知 personnel 关联 user |

## 七、测试

`notifications/tests/` 覆盖模型、去重合并、viewset 过滤与已读操作、信号触发。
