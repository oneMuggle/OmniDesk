# 值班排班换班(ScheduleSwapRequest) — 规划阶段

> **状态:等待用户确认**
> 本文为 `/plan` 阶段产出,未经确认严禁进入编码阶段。
> 实施前所有代码片段仅表达设计意图。

---

## 1. 背景与目标

### 1.1 业务诉求
v0.4.0 已完成"用户自助管理自己"的字段级防护(`/api/users/me/personnel/`)。但**排班**仍停留在"HR 在管理后台拖拽改":
- 用户只能被动查询排班,无法知道未来自己哪天值班
- 想换班只能线下喊,无线上留痕
- 接收方无知情权,HR 审批无审计

### 1.2 与 v0.4.0 的衔接
本功能是 v0.4.0 的**自然延伸**:

| v0.4.0 已交付 | v0.5.0 本设计补齐 |
|---|---|
| 用户改自己档案 | 用户查/换自己排班 |
| Personnel 变更通知 | Schedule 换班 6 种通知 |
| 三层防护 | 同模式应用到 SwapRequest |
| `IsHR` 权限类 | 审批直接复用 |
| `NotificationService` + `AuditLogEntry` | 新增 6 个 TYPE + `ScheduleSwapAuditLog` |

### 1.3 成功标准
- [ ] 登录用户在 `/me/schedule` 看自己未来 N 天所有值班
- [ ] 申请换班 → 接收方 → HR 三方均 5s 内收到通知
- [ ] HR 批准后 Schedule 字段自动同步,通知双方
- [ ] 超 48h 未处理自动 `expired`
- [ ] 状态流转可在 `ScheduleSwapAuditLog` 查询
- [ ] 字段级权限 L1+L2+L3 三层防护
- [ ] 整体覆盖率 ≥ 80%

---

## 2. 现状分析

### 2.1 现有 Schedule 模型可扩展性 ✅
**源文件**:`omni_desk_backend/events/models.py:135-163`
- `duty_date` 已有 `unique=True` + UniqueConstraint → **不能通过改 duty_date 实现换班**
- 必须**交换 `duty_person` / `duty_leader` 字段值**,日期不动(沿用 `ScheduleViewSet.swap_dates` 已有做法)

**结论**:**不修改任何 Schedule 字段**(满足用户硬性约束);新增 `ScheduleSwapRequest` 模型

### 2.2 通知机制复用点 ✅
- `NotificationService.create(user, type, title, content, link, priority, dedupe_key)` 24h 去重
- `notifications/signals.py` 已有 `Schedule.post_save` 监听
- `Notification.TYPE_CHOICES` 追加 6 个 type 即可

### 2.3 权限体系复用点 ✅
- `IsHR` 审批用
- 自定义 `IsRequester` / `IsTargetPersonnel`(对象级)

---

## 3. 数据模型设计

### 3.1 `ScheduleSwapRequest`(新建)

**位置**:`omni_desk_backend/events/models.py` 末尾追加

```python
class ScheduleSwapRequest(models.Model):
    """值班换班申请(状态机:pending → accepted_by_target → approved)。"""
    
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted_by_target"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected_by_target"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [...]
    
    SCOPE_DUTY_PERSON = "duty_person"
    SCOPE_DUTY_LEADER = "duty_leader"
    SCOPE_CHOICES = [...]
    
    requester = models.ForeignKey("personnel.Personnel", PROTECT, related_name="initiated_swap_requests")
    original_schedule = models.ForeignKey(Schedule, CASCADE, related_name="outgoing_swap_requests")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_DUTY_PERSON)
    target_personnel = models.ForeignKey("personnel.Personnel", PROTECT, related_name="incoming_swap_requests")
    target_schedule = models.ForeignKey(Schedule, SET_NULL, null=True, blank=True, related_name="incoming_swap_requests",
                                       help_text="若为空=单方面替班,若有值=对调")
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    
    target_decided_at = models.DateTimeField(null=True, blank=True)
    target_decision_note = models.CharField(max_length=500, blank=True)
    
    approver = models.ForeignKey("users.CustomUser", SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.CharField(max_length=500, blank=True)
    
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="swap_status_expires_idx"),
            models.Index(fields=["requester", "status"], name="swap_requester_status_idx"),
            models.Index(fields=["target_personnel", "status"], name="swap_target_status_idx"),
        ]
        constraints = [
            # 同一原排班同时只能有一个 active 申请
            models.UniqueConstraint(
                fields=["original_schedule"],
                condition=models.Q(status__in=["pending", "accepted_by_target"]),
                name="uniq_active_swap_per_schedule",
            ),
        ]
    
    def clean(self):
        """L3 数据完整性防护。"""
        super().clean()
        errors = {}
        if self.requester_id == self.target_personnel_id:
            errors["target_personnel"] = "不能把班换给自己"
        if self.scope == self.SCOPE_DUTY_PERSON:
            if self.original_schedule.duty_person_id != self.requester_id:
                errors["requester"] = "您不是该日的值班人员,无权发起换班"
        else:
            if self.original_schedule.duty_leader_id != self.requester_id:
                errors["requester"] = "您不是该日的值班领导,无权发起换班"
        if self.original_schedule.duty_date < timezone.now().date():
            errors["original_schedule"] = "无法对已过去的排班发起换班申请"
        if self.expires_at and self.expires_at <= timezone.now():
            errors["expires_at"] = "失效时间必须晚于当前时间"
        if errors:
            raise ValidationError(errors)
```

### 3.2 `ScheduleSwapAuditLog`(新建)
不复用 `AuditLogEntry`(语义不同),独立模型记录每次状态变更:

```python
class ScheduleSwapAuditLog(models.Model):
    swap_request = models.ForeignKey(ScheduleSwapRequest, CASCADE, related_name="audit_logs")
    actor = models.ForeignKey("users.CustomUser", SET_NULL, null=True, blank=True)
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    note = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 3.3 不修改 Schedule 模型 ✅
**用户硬性约束**:不动任何 Schedule 字段。所有换班语义在 SwapRequest;Schedule 的 `duty_person`/`duty_leader` 只在 `approve()` 那一刻原子性交换。

---

## 4. 换班工作流(状态机)

> **用户已确认决策**:两人互认即生效(决策 1C),状态机简化如下。
> **HR 不参与审批**,仅知情(所有状态变更都发通知给 HR 组)。

```
┌─────────┐  接收方accept(自动生效)  ┌──────────┐
│ pending │────────────────────────►│ approved │
└────┬────┘                           └──────────┘
     │ 接收方reject / 申请方cancel / 系统超时
     ▼
┌──────────────────────────────────────────┐
│ rejected_by_target / cancelled / expired │
└──────────────────────────────────────────┘
```

### 4.1 状态转换矩阵(简化后)

| 当前状态 | 触发者 | 触发动作 | 新状态 | Schedule 操作 | 通知 |
|---|---|---|---|---|---|
| `pending` | 接收方 | `accept` | `approved` | **直接调 `apply_swap()`** | 申请方 + 接收方 + **HR 组(知情)** |
| `pending` | 接收方 | `reject` | `rejected_by_target` | 无 | 申请方 + **HR 组(知情)** |
| `pending` | 申请方 | `cancel` | `cancelled` | 无 | 接收方 + **HR 组(知情)** |
| `pending` | 系统 | (超时 48h) | `expired` | 无 | 申请方 + 接收方 + **HR 组(知情)** |

> **状态数从 6 缩为 5**:`pending / approved / rejected_by_target / cancelled / expired`(去 `accepted_by_target` 中间态)
> **HR 角色从"审批者"变"知情者"**:任何状态变更都发通知给 HR 组,但 HR 不参与审批流

### 4.2 Accept 自动生效(关键变更)

`accept` action 不再是"等 HR 审批",而是**直接执行 `apply_swap()`**:

```python
@action(detail=True, methods=["post"])
def accept(self, request, pk=None):
    swap = self.get_object()
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise ValidationError("该申请不在 pending 状态,无法 accept")
    with transaction.atomic():
        old_status = swap.status
        swap.apply_swap(approver=swap.target_personnel.user_account)  # 记录目标方同意
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap, actor=request.user,
            from_status=old_status, to_status=swap.status,
            note=request.data.get("target_decision_note", "接收方同意"),
        )
    return Response(SwapRequestDetailSerializer(swap).data)
```

注:`apply_swap` 中 `approver` 字段填**接收方**(或**双方都填**,记录审计时 actor 与 approver 区分)。

### 4.2 Approve 时的原子操作

```python
@transaction.atomic
def apply_swap(self, approver):
    """执行 Schedule 字段交换。仅在 approved 时被调用。"""
    original = Schedule.objects.select_for_update().get(pk=self.original_schedule_id)
    target = (Schedule.objects.select_for_update().get(pk=self.target_schedule_id)
              if self.target_schedule_id else None)
    
    field = "duty_person" if self.scope == self.SCOPE_DUTY_PERSON else "duty_leader"
    
    if target is None:
        # 单方面替班
        setattr(original, field, self.target_personnel)
        original.save(update_fields=[field])
    else:
        # 双向对调
        original_val, target_val = getattr(original, field), getattr(target, field)
        setattr(original, field, target_val)
        setattr(target, field, original_val)
        original.save(update_fields=[field])
        target.save(update_fields=[field])
    
    self.status = self.STATUS_APPROVED
    self.approver = approver
    self.approved_at = timezone.now()
    self.save(update_fields=["status", "approver", "approved_at", "updated_at"])
```

### 4.3 时效控制
- `expires_at` 在 `perform_create` 时由 ViewSet 自动计算:`now + SWAP_REQUEST_TTL_HOURS`(默认 48h)
- Celery 定时任务 `cleanup_expired_swap_requests` 每小时跑一次,批量把超时 pending/accepted 改为 `expired` 并通知

---

## 5. API 设计

**前缀**:`/api/events/swap-requests/`(沿用 events 应用)

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| `GET` | `/api/events/swap-requests/?role=requester\|target\|approver` | `IsAuthenticated` | 三视角列表 |
| `GET` | `/api/events/swap-requests/{id}/` | `IsAuthenticated` + 行级 | 详情(仅当事三方) |
| `POST` | `/api/events/swap-requests/` | `IsAuthenticated` | 发起 |
| `POST` | `/api/events/swap-requests/{id}/accept/` | `IsTargetPersonnel` | 接收方同意 |
| `POST` | `/api/events/swap-requests/{id}/reject/` | `IsTargetPersonnel` OR `IsHR` | 接收方拒绝 / HR 驳回 |
| `POST` | `/api/events/swap-requests/{id}/approve/` | `IsHR` | HR 终批 |
| `POST` | `/api/events/swap-requests/{id}/cancel/` | `IsRequester` | 申请方撤销 |
| `GET` | `/api/events/me/schedule/?days=60` | `IsAuthenticated` | **当前用户排班自助入口** |
| `GET` | `/api/events/swap-requests/{id}/audit-logs/` | `IsAuthenticated` + 行级 | 审计日志 |

### 5.1 序列化器分层(5 套)

| Serializer | 场景 | 可写字段 |
|---|---|---|
| `SwapRequestCreateSerializer` | `POST /swap-requests/` | `original_schedule`, `scope`, `target_personnel`, `target_schedule`, `reason` |
| `SwapRequestListSerializer` | `GET /swap-requests/` | (空,只读) |
| `SwapRequestDetailSerializer` | `GET /{id}/` | (空,只读,含嵌套 schedule + audit_logs) |
| `SwapRequestApprovalSerializer` | `/approve|reject/` (HR) | `approval_note` |
| `SwapRequestTargetActionSerializer` | `/accept|reject/` (接收方) | `target_decision_note` |

### 5.2 字段级三层防护

**L1 序列化器**:SwapRequestCreateSerializer 不暴露 `requester` / `expires_at` / `status` 字段,客户端无法传

**L2 ViewSet**:强制注入
```python
def perform_create(self, serializer):
    requester = self.request.user.personnel
    if requester is None:
        raise PermissionDenied("当前用户尚未关联人员档案,请联系 HR")
    ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
    serializer.save(
        requester=requester,
        expires_at=timezone.now() + timedelta(hours=ttl),
        status=ScheduleSwapRequest.STATUS_PENDING,
    )
```

**L3 Model.clean()**:见 §3.1

### 5.3 行级权限 `get_queryset()`

```python
def get_queryset(self):
    user = self.request.user
    personnel = getattr(user, "personnel", None)
    role = self.request.query_params.get("role", "all")
    base = ScheduleSwapRequest.objects.select_related(
        "requester", "target_personnel", "original_schedule", "target_schedule", "approver"
    )
    if role == "approver":
        if not IsHR().has_permission(self.request, self):
            return base.none()
        return base.filter(status=ScheduleSwapRequest.STATUS_ACCEPTED)
    if personnel is None:
        return base.none()
    if role == "requester":
        return base.filter(requester=personnel)
    if role == "target":
        return base.filter(target_personnel=personnel)
    return base.filter(
        Q(requester=personnel) | Q(target_personnel=personnel) | Q(approver=user)
    )
```

---

## 6. 通知机制

### 6.1 新增 TYPE_CHOICES(6 项)

```python
TYPE_CHOICES = [
    # ... 已有 ...
    ("schedule_swap_requested", "换班申请已发起"),
    ("schedule_swap_accepted",  "换班申请被接受"),
    ("schedule_swap_rejected",  "换班申请被拒绝"),
    ("schedule_swap_approved",  "换班申请已通过"),
    ("schedule_swap_cancelled", "换班申请已撤销"),
    ("schedule_swap_expired",   "换班申请已超时"),
]
```

### 6.2 触发表(谁发→谁收)

| 事件 | type | priority | dedupe_key |
|---|---|---|---|
| 创建 → 接收方 | `schedule_swap_requested` | HIGH | `swap:{id}:to_target` |
| 创建 → HR 组 | `schedule_swap_requested` | NORMAL | `swap:{id}:to_hr` |
| 接收方 accept → 申请方 | `schedule_swap_accepted` | HIGH | — |
| 接收方 accept → HR 组 | `schedule_swap_accepted` | HIGH | `swap:{id}:to_hr_accepted` |
| 接收方 reject → 申请方 | `schedule_swap_rejected` | HIGH | — |
| HR approve → 双方 | `schedule_swap_approved` | URGENT | — |
| HR reject → 双方 | `schedule_swap_rejected` | HIGH | — |
| 申请方 cancel → 接收方(+HR) | `schedule_swap_cancelled` | NORMAL | — |
| 系统 expire → 三方 | `schedule_swap_expired` | NORMAL | — |

### 6.3 实现位置 — 新建 `events/signals.py`

**新文件**:`omni_desk_backend/events/signals.py`

- `pre_save` 捕获旧 status
- `post_save` 根据 status 迁移触发不同通知
- 复用 `NotificationService.create()`(无需自建服务)

### 6.4 注册 — 修改 `events/apps.py`

```python
class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"
    def ready(self):
        import events.signals  # noqa: F401
```

---

## 7. 前端设计

### 7.1 目录结构(新增 7 个组件 + 1 API + 1 hook + 2 pages)

```
omni_desk_frontend/src/features/schedule/
├── api/swapRequestApi.js          # 新增
├── hooks/useSwapRequests.js        # 新增
├── components/
│   ├── MyScheduleView.jsx          # 新增:我的未来 N 天值班
│   ├── SwapRequestForm.jsx         # 新增:发起换班模态
│   ├── SwapRequestList.jsx         # 新增:三视角列表
│   └── SwapRequestDetailDrawer.jsx # 新增:详情抽屉
└── pages/
    ├── MySchedulePage.jsx          # 新增:Tab(我的排班/我发起/我收到)
    └── SwapApprovalPage.jsx        # 新增:HR 审批中心
```

### 7.2 路由

```jsx
// /me/schedule — 主应用路由(职工自助入口)
{
  path: "me/schedule",
  element: (
    <ProtectedRoute pagePath="/me/schedule" pageName="我的排班">
      <LazyComponent component={MySchedulePage} />
    </ProtectedRoute>
  ),
},

// /schedule/swap-approvals — 管理面板(HR 审批)
{ path: "schedule/swap-approvals", element: <LazyComponent component={SwapApprovalPage} /> }
```

### 7.3 关键交互

- **发起换班**:`MyScheduleView` 点某天排班 → `SwapRequestForm` 弹出 → 选 scope / target_personnel / 目标日期 / reason → submit
- **接收方**:`NotificationBell` 跳详情 → `SwapRequestDetailDrawer` 显示原排班+理由 → Accept/Reject + note
- **HR 审批**:`SwapApprovalPage` 表格 + 操作列(批准/驳回)

### 7.4 与 NotificationBell 集成
已有铃铛 5s 轮询未读数,新增 6 个 type 后**无需任何前端改动** — `item.link` 直接跳详情抽屉。

---

## 8. 风险与依赖

| 风险 | 等级 | 缓解 |
|---|---|---|
| **并发改 Schedule**:两个换班同时 approve,UNIQUE 约束撞车 | HIGH | `apply_swap` 用 `select_for_update()` 锁原/目标排班;DB 唯一约束 `uniq_active_swap_per_schedule` |
| **状态机非法迁移**:直调 `/approve/` 时 status 不对 | HIGH | ViewSet 每个 action 第一步 status 守卫;非法→409 |
| **通知失败阻塞主流程** | MEDIUM | signal 内 `try/except` 全包裹,失败仅 log |
| **Celery 挂掉导致 expire 不触发** | MEDIUM | `MyScheduleView` 实时计算"已超时但未标记";`/api/health/` 检查 worker 数 |
| **跨日期换班冲突**:接收方那天已有班/节假日 | MEDIUM | L3 `clean()` 校验 `target_schedule` 日期合法 + 不与现有排班冲突 |
| **同一 Schedule 被多人同时申请** | HIGH | `perform_create` 用 `select_for_update()` 锁原排班;DB 唯一约束 |
| **personnel 关联缺失** | LOW | `perform_create` 检查 `request.user.personnel`,无则 403 |
| **数据迁移可回滚** | MEDIUM | 新增 model 走标准 migration;CHANGELOG 标注 |
| **审计日志膨胀** | LOW | 索引+长期归档任务 |
| **Notification 重复** | LOW | 已有 `dedupe_key` 24h 合并 |

---

## 9. 实施步骤(分阶段、可勾选)

### Phase 1:数据模型 + 迁移
- [ ] `events/models.py` 末尾追加 `ScheduleSwapRequest` + `ScheduleSwapAuditLog`
- [ ] `notifications/models.py:6` `TYPE_CHOICES` 追加 6 个 swap 相关 type
- [ ] `python manage.py makemigrations events notifications`
- [ ] `python manage.py check_migrations`(无破坏性变更)
- [ ] `events/admin.py` 注册 2 个新 model
- [ ] 单元测试:`events/tests/test_swap_request_model.py`(clean() 全部 ValidationError 分支)
- 验证:`pytest events/tests/test_swap_request_model.py` 100% 通过

### Phase 2:API + 权限 + 序列化器
- [ ] `events/serializers.py` 末尾追加 5 个 SwapRequest serializers
- [ ] `events/views.py` 新增 `SwapRequestViewSet`(5 action) + `MyScheduleView`
- [ ] `users/permissions.py` 末尾追加 `IsRequester` / `IsTargetPersonnel`
- [ ] `events/urls.py` router 注册 + path 加 `me/schedule/`
- [ ] 集成测试:`events/tests/test_swap_request_api.py`(三层防护 + 状态机所有 transition)
- 验证:覆盖率 ≥ 80%

### Phase 3:Signal + 通知 + 审计
- [ ] 新建 `events/signals.py`
- [ ] `events/apps.py` 增加 `ready()` 注册
- [ ] Signal 单元测试:`events/tests/test_swap_signals.py`
- [ ] 审计日志测试:`events/tests/test_swap_audit_log.py`
- 验证:`pytest events/tests/test_swap_signals.py test_swap_audit_log.py` 全绿

### Phase 4:Celery 定时任务
- [ ] 新建 `events/tasks.py` `cleanup_expired_swap_requests`
- [ ] `settings/base.py` `CELERY_BEAT_SCHEDULE` 注册
- [ ] 任务测试:`events/tests/test_swap_tasks.py`

### Phase 5:前端
- [ ] `swapRequestApi.js` + `useSwapRequests.js`
- [ ] `MyScheduleView` / `SwapRequestForm` / `SwapRequestList` / `SwapRequestDetailDrawer` 组件
- [ ] `MySchedulePage` / `SwapApprovalPage` 容器页
- [ ] `routes/index.jsx` 新增 2 路由 + `App.jsx` 侧边栏加入口
- [ ] Jest 测试:每个组件 ≥ 1 happy + 1 error path

### Phase 6:测试、文档、发版
- [ ] Playwright E2E:`swap-request.spec.js`
- [ ] 技术文档:`docs/technical/14-schedule-swap-request.md`
- [ ] 用户手册:`docs/user-manual/0X-schedule-swap-request.md`
- [ ] `VERSION` → `v0.5.0`,`CHANGELOG.md` 追加 v0.5.0 条目
- [ ] `python manage.py check_migrations` 无 destructive
- [ ] PR 标题:`feat(events): schedule swap request workflow with three-party notification`

---

## 10. 不确定项与建议(等待用户拍板)

> 下列决策直接影响实施,**需用户明确**。每项给出推荐。

### 10.1 是否采用"双签机制"(接收方 + HR)?

- **A 推荐**:双签(接收方同意 → HR 终批)
- B:单 HR(直接 pending → HR 审批)
- C:仅接收方(两人互认即生效)

### 10.2 是否允许"跨日期换班"?

- **A**:仅双向对调(`target_schedule_id` 必填)
- B:仅单方面替班(`target_schedule_id` 为空)
- **C 推荐**:两者皆可(更灵活)

### 10.3 时效(`SWAP_REQUEST_TTL_HOURS`)默认值?

- A:24h
- **B 推荐**:48h
- C:72h
- D:可配置(每次自选)

### 10.4 是否支持"链式换班"(A→B→C)?

- **A 推荐**:不支持,首版仅两人换班(沿用 YAGNI)
- B:支持,新增 `ScheduleSwapChain` 模型

### 10.5 首版是否仅支持 `duty_person`,`duty_leader` 留后续?

- **A 推荐**:先只支持 duty_person(简化测试矩阵,领导换班需部门负责人额外签字)
- B:第一版就支持 duty_leader

---

## 文档状态

> ⏸️ **等待用户确认**
>
> 请逐条确认 §10 的 5 个不确定项后回复"通过"或"修改:xxx"。
> 用户明确说"继续"或"通过"之前,**严禁进入实施阶段**。
>
> 确认后我会:
> 1. 按 §9 Phase 1 起步,**每完成一个 Phase 单独 commit + 自评**
> 2. 全部完成后按 CLAUDE.md "Document Organization" 移入 `docs/technical/14-schedule-swap-request.md` 与 `docs/user-manual/0X-schedule-swap-request.md`,删除本 plan 文件

---

## 关键文件路径速查

### 后端新建
- `omni_desk_backend/events/signals.py` ⭐
- `omni_desk_backend/events/tasks.py`
- `omni_desk_backend/events/tests/test_swap_request_model.py`
- `omni_desk_backend/events/tests/test_swap_request_api.py`
- `omni_desk_backend/events/tests/test_swap_signals.py`
- `omni_desk_backend/events/tests/test_swap_audit_log.py`
- `omni_desk_backend/events/tests/test_swap_tasks.py`

### 后端修改
- `omni_desk_backend/events/models.py`(追加 2 model)
- `omni_desk_backend/events/serializers.py`(追加 5 serializer)
- `omni_desk_backend/events/views.py`(新增 2 View)
- `omni_desk_backend/events/urls.py`(router + path)
- `omni_desk_backend/events/apps.py`(`ready()`)
- `omni_desk_backend/events/admin.py`
- `omni_desk_backend/notifications/models.py:6-20`(扩 TYPE_CHOICES)
- `omni_desk_backend/users/permissions.py`(追加 2 权限)
- `omni_desk_backend/settings/base.py`(`CELERY_BEAT_SCHEDULE`)

### 前端新建
- `omni_desk_frontend/src/features/schedule/api/swapRequestApi.js`
- `omni_desk_frontend/src/features/schedule/hooks/useSwapRequests.js`
- `omni_desk_frontend/src/features/schedule/components/MyScheduleView.jsx`
- `omni_desk_frontend/src/features/schedule/components/SwapRequestForm.jsx`
- `omni_desk_frontend/src/features/schedule/components/SwapRequestList.jsx`
- `omni_desk_frontend/src/features/schedule/components/SwapRequestDetailDrawer.jsx`
- `omni_desk_frontend/src/features/schedule/pages/MySchedulePage.jsx`
- `omni_desk_frontend/src/features/schedule/pages/SwapApprovalPage.jsx`

### 前端修改
- `omni_desk_frontend/src/routes/index.jsx`(2 路由 + 4 lazy import)
- `omni_desk_frontend/src/App.jsx`(侧边栏菜单)

### 文档
- `deployment/docker/VERSION` → `v0.5.0`
- `deployment/docker/CHANGELOG.md`(v0.5.0 条目)
- `docs/technical/README.md`(加章节 14)
- `docs/user-manual/README.md`(加章节)
- `docs/technical/14-schedule-swap-request.md`(实施完成后归档)
- `docs/user-manual/0X-schedule-swap-request.md`(实施完成后归档)
