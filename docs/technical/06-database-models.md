# 数据库模型总览

> 本文档汇总 OmniDesk 所有 Django 模型及其关系。

## 1. 核心模型

### CustomUser (`users/models.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `username` | CharField | 用户名（唯一） |
| `role` | CharField | 角色（admin / manager / user / guest） |
| `permissions` | JSONField | 页面级权限配置 |
| `is_active` | BooleanField | 是否活跃 |
| `last_login` | DateTimeField | 最后登录时间 |

> 自定义用户模型：`AUTH_USER_MODEL = 'users.CustomUser'`

## 2. 功能模块模型

### 2.1 排班与试验

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Schedule` | date, shift, duty_person, duty_leader | 排班计划 |
| `Trial` | name, start_date, end_date, status | 试验记录 |

### 2.2 会议室

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `MeetingRoom` | name, capacity, location, equipment | 会议室信息 |
| `MeetingBooking` | room, user, start_time, end_time, purpose | 预约记录 |

### 2.3 传感器管理

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Sensor` | name, type, location, status | 传感器设备 |
| `SensorCalibration` | sensor, calibration_date, result, operator | 校准记录 |

### 2.4 备忘录

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Memo` | title, content, author, reminder_time, is_completed | 备忘录条目 |
| `MemoCategory` | name, color | 备忘录分类 |

### 2.5 公告

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Announcement` | title, content(HTML), author | 公告（含富文本） |
| `UploadedImage` | image, uploaded_at | 富文本图片 |

### 2.6 新闻

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `NewsArticle` | title, content, author, publish_date | 新闻文章 |

### 2.7 项目与合规

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Project` | name, manager, status, start_date, end_date | 项目 |
| `ComplianceIssue` | project, title, status, due_date | 合规问题 |

### 2.8 人员

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Personnel` | name, department, position, contact | 人员信息 |

### 2.9 通知

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Notification` | user, type, content, is_read | 系统通知 |
| type 值 | | schedule_change, announcement, memo_due, calibration_reminder, project_update, compliance_issue, system |

### 2.10 智能助手

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `AgentLog` | user, query, response, tool_used, tool_output | 助手调用日志 |

### 2.11 权限

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `GroupPagePermission` | group, page_route, can_access | 组级页面权限 |

## 3. 关系图

```
CustomUser (role: admin/manager/user/guest)
    ├──→ Announcement (author FK)
    ├──→ NewsArticle (author FK)
    ├──→ Project (manager FK)
    ├──→ Memo (author FK)
    ├──→ Notification (user FK)
    ├──→ AgentLog (user FK)
    └──→ MeetingBooking (user FK)

MeetingRoom ←──→ MeetingBooking (room FK)
Sensor ←──→ SensorCalibration (sensor FK)
Project ←──→ ComplianceIssue (project FK)

GroupPagePermission → Django Group → CustomUser
```

> **注意**: 以上为主要模型概览。详细字段定义请参考各模块技术文档。`sensors/` 和 `documents/EBook` 已标记为弃用。
