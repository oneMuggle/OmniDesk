# 技术文档：联培生管理模块

## 1. 概述

联培生（联合培养硕博研究生）管理是 OmniDesk 独立的子模块,与 `personnel` 主表 1:1 关联但业务独立。**前端 19 个文件计划在后续独立 PR 实施**;本章描述当前已落地的后端能力,前端页面可在 Django admin / API 临时调试。

### 核心业务诉求

| 维度 | 联培生 | 与正式员工差异 |
|---|---|---|
| 合同形式 | 联合培养协议(非劳动合同) | 独立 |
| 报酬 | 补助(非工资) | 独立 |
| 月度流程 | 月度报告 + 月末考核 | 独立 |
| 考核机制 | 专家组打分 + 出勤考核 + A/B 档 | 独立 |
| 行政归属 | 联培生管理员 Group | 与 HR(人员模块)互不重叠 |

### 补助计算公式

```
月补助 = 基本额度 × 考核系数 × 出勤比
       = (硕士 3000 / 博士 6000)
       × (A 档 1.0 / B 档 0.6)
       × (实际出勤天数 / 应出勤天数)
```

**A 档名额硬性限制 ≤ 40%**,不足余向下取整;同分时按工号稳定排序。

### 非目标(明确范围外)

- ❌ 考勤系统(打卡/排班):项目里没有,也不引入
- ❌ 论文/科研成果管理
- ❌ 财务系统对接:补助仅生成记录,不与外部银行/工资系统打通
- ❌ 通知渠道扩展:仅复用站内 `Notification`,不引入邮件/短信/微信

---

## 2. 后端实现 (`joint_students` 应用)

[`omni_desk_backend/joint_students/`](../../omni_desk_backend/joint_students/) 是单 Django app,提供 5 张模型 + 3 个服务 + DRF + Celery + 权限 + Django admin。

### 2.1 数据模型(5 张表)

| 模型 | 字段摘要 | 备注 |
|---|---|---|
| `JointStudent` | `personnel` (1:1 Personnel) + `student_id` + `degree_level` (MASTER/PHD) + `mentor` + `enrollment_date` | 联培生档案 |
| `MonthlyReport` | `student` + `cycle` + `work_progress` + `highlights` + `attendance_days` + `expected_days` | 月度报告 |
| `AssessmentCycle` | `month` + `status` (OPEN/CLOSED) + `deadline` + `created_at` | 月末考核批次 |
| `ExpertScore` | `cycle` + `student` + `expert` + `score` (Decimal) + `submitted_at` | 专家组打分,每人独立打分 |
| `StipendRecord` | `student` + `cycle` + `base_amount` + `grade_coefficient` + `attendance_ratio` + `final_amount` | 补助记录 |

外键约束: 5 张表全部与 `personnel.Personnel` 强耦合(联培生 1:1 关联在职档案),Django 设计上**不动 `personnel.models.py`**。

### 2.2 服务层(`services/`)

[`omni_desk_backend/joint_students/services/`](../../omni_desk_backend/joint_students/services/) 三个独立模块:

- **`grading.py` — `assign_grades(cycle)`**: A 档 40% 名额优先算法。
  - 计算专家组均分 → 降序排序 → 前 40% 标 A 档 → 余下 B 档
  - 同分时按 `personnel__employee_id` 字典序稳定排序
  - 边界: 0 名学生 → 返回空列表;1-2 名学生 → 至多 1 个 A 档(向下取整)

- **`stipend.py` — `compute_attendance_ratio(actual, expected)` + `compute_stipend_amount(...)`**: 补助计算。
  - 出勤比: `actual / expected`,上限 1.0(防御超额)
  - 应出勤 0 → 视为完全出勤(防御除零)
  - 用 `Decimal` 类型,不用 float

- **`cycle.py` — `create_cycle(...)` / `close_cycle(cycle)` / `notify_experts(...)` / `notify_managers_to_review_stipends(...)`**: 批次生命周期。
  - `create_cycle`: 月初调用,创建 `AssessmentCycle` + 通知专家组
  - `close_cycle`: 月末截止,得分已交齐后触发补助计算
  - 通知复用 `notifications.Notification`,不新增渠道

### 2.3 API 视图

[`omni_desk_backend/joint_students/views.py`](../../omni_desk_backend/joint_students/views.py) 提供 DRF ViewSets:

- `/api/joint-students/students/` — 联培生档案 CRUD
- `/api/joint-students/reports/` — 月度报告 CRUD
- `/api/joint-students/cycles/` — 考核批次管理
- `/api/joint-students/scores/` — 专家组打分
- `/api/joint-students/stipends/` — 补助记录 CRUD

权限类位于 [`omni_desk_backend/joint_students/permissions.py`](../../omni_desk_backend/joint_students/permissions.py),基于 `permissions.GroupPagePermission` 扩展;联培生管理员独立 Group,与 HR 互不重叠。

### 2.4 Celery 任务

[`omni_desk_backend/joint_students/tasks.py`](../../omni_desk_backend/joint_students/tasks.py) 单个 scheduler 任务:

```python
@shared_task(name="joint_students.check_and_create_assessment_cycle")
def check_and_create_assessment_cycle(trigger_source: str = "auto") -> None:
    """月初检查当前月是否已创建批次,未创建则创建并通知专家组。"""
```

Beat 调度(`omni_desk_backend/omni_desk_backend/celery.py`):

```python
app.conf.beat_schedule.update({
    "create-monthly-assessment-cycle": {
        "task": "joint_students.check_and_create_assessment_cycle",
        "cron": f"0 2 {settings.JOINT_STUDENT_CYCLE_DAY} * *",
        "kwargs": {"trigger_source": "auto"},
    },
})
```

- 默认每月 25 号 02:00 触发(可由 `JOINT_STUDENT_CYCLE_DAY` 环境变量覆盖)
- 与 `memos.tasks.send_due_memo_reminders` 不冲突(cron 表达式不同)
- 兼容 2026-08 main 上的 `RequestIdTask` 传播层: 用 `update()` 而非赋值,保留其他模块追加的条目

手动触发: `python manage.py create_assessment_cycle --month 2026-08`(用于把当月批次提前创建)。

### 2.5 数据迁移

3 个迁移文件:

- `0001_initial.py` — 5 张模型建表
- `0002_seed_groups.py` — 创建 `联培生管理员` / `考核专家组` / `联培生` 3 个 Group
- `0003_seed_page_routes.py` — 12 个 PageRoute(用于前端 ProtectedRoute 权限控制)

> 注: `0003_seed_page_routes` 在测试 DB 也会执行,会污染部分单元测试的 `PageRoute` 计数假设。受影响的测试文件已用 `isolated_page_routes` fixture 隔离,详见 PR #391。

### 2.6 关键配置

`omni_desk_backend/omni_desk_backend/settings/base.py`:

```python
INSTALLED_APPS = [
    ...,
    "joint_students.apps.JointStudentsConfig",  # 2026-08-19 恢复
]

# 每月几号 02:00 触发考核批次自动创建任务 (Celery Beat cron)
JOINT_STUDENT_CYCLE_DAY = int(os.environ.get("JOINT_STUDENT_CYCLE_DAY", "25"))
```

---

## 3. 前端实现

**⚠️ 前端 19 个文件暂未实现,计划在后续独立 PR 实施。**

设计文档规划的文件清单(摘自 `docs/superpowers/specs/2026-07-28-联培生管理模块-design.md`):

```
omni_desk_frontend/src/features/joint-students/
├── api/{client.js, students.js, reports.js, cycles.js, scores.js, stipends.js}
└── pages/
    ├── admin/{StudentListPage, StudentEditPage, ReportReviewPage,
    │          CycleManagementPage, StipendReviewPage}.jsx
    ├── expert/{ExpertScoringPage}.jsx
    ├── student/{MyReportsPage, ReportSubmitPage, MyStipendsPage}.jsx
    └── mentor/{MentorOverviewPage}.jsx
```

按 4 类角色分页面:管理员 / 专家 / 联培生 / 导师。后端 API 已就绪,前端可通过 `curl` / Django admin 临时调试。

---

## 4. 测试

[`omni_desk_backend/joint_students/tests/`](../../omni_desk_backend/joint_students/tests/) 5 个测试文件,**52 个测试全部通过**:

- `test_models.py` — 5 张模型的字段约束、外键关系
- `test_grading.py` — A 档名额算法 + 边界 case(0/1/2/10/41/100 学生)
- `test_stipend.py` — 补助计算公式 + 出勤上限 + 应出勤 0 防御
- `test_cycle.py` — 批次生命周期 + 通知触发
- `test_api.py` — API 权限 + 4 类角色隔离
- `test_tasks.py` — Celery 任务触发
- `factories.py` — 测试工厂(命名空间隔离,不与全局 factories 冲突)

运行:

```bash
pytest --ds=omni_desk_backend.settings.test omni_desk_backend/joint_students/ -v
```

---

## 5. 部署与运维

### 5.1 增量迁移

生产首次部署 PR #391 时,在 `migrate` 之前必须先确保:

- `permissions.PageRoute` 表已存在(依赖 `permissions.0001_initial`)
- `personnel.Personnel` 主表已存在(联培生 1:1 关联)

部署脚本 `deployment/docker/upgrade.sh` 已自动处理依赖顺序,无需手动干预。

### 5.2 Celery Beat

PR #391 修改了 `omni_desk_backend/celery.py`,生产部署后**必须重启 Celery worker 和 beat 进程**才能生效新调度。Beat 不会热加载配置。

### 5.3 已知风险

- **Django 4.2 EOL**: Django 4.2 已于 2026-04 EOL,本模块运行在含多个已知 CVE 的版本上。已在 CI 中通过 `pip-audit --ignore-vuln` 包含 `PYSEC-2026-3717` 等白名单临时绕过。Django 4.2 → 5.x 升级专项需在 `docs/superpowers/specs/` 立项后单独处理。
- **归档分支回溯**: 完整实现历史(2026-07-28, 10 个 commit)保留在 `origin/archive/joint-students-module` 分支,主实施见证是 PR #391。

---

## 6. 后续工作

- ⏭ 前端 19 个文件实现(独立 PR)
- ⏭ 用户手册章节(后端稳定后再写)
- ⏭ Django 4.2 EOL 升级专项
