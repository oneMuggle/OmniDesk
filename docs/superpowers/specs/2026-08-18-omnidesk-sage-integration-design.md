# OmniDesk ↔ S agent 互通设计稿

- **日期**:2026-08-18
- **作者**:Claude(经与用户多轮澄清后定稿)
- **状态**:待用户复审
- **关联项目**:OmniDesk(`/home/fz/project/OmniDesk`)、Sage(`/home/fz/project/sage`)

---

## 1. 背景与目标

### 1.1 现状

| 项目 | 角色 | 用户范围 | 能力特征 |
|---|---|---|---|
| **OmniDesk** | 组织级业务系统 | 内网全员(多用户集中部署) | 16 个 Django app,覆盖人员/排班/审批/会议室/传感器/合规等 |
| **Sage** | 个人级 AI 工作台 | 单机单用户(Electron 桌面端) | 本地对话 + 三层记忆 + ChromaDB + Skill + MCP |

两个项目目前完全独立,用户群体和能力集无重叠。

### 1.2 业务动机

- OmniDesk 用户希望从 AI 助手获得业务相关回答(排班、人员、审批等)
- Sage 用户希望助手能感知真实业务,而不是停留在 demo 阶段
- Win7 LTS 桌面端用户在内网中也需要 AI 助手能力,但 Python 3.8 锁版
- 两个项目应保持**独立运行**是常态,**能力增强**是可选

### 1.3 设计目标

1. **OmniDesk 与 Sage 各自独立运行是默认行为,互通是可选能力增强**
2. **OmniDesk 用户 = Sage 用户**(身份绑定,无独立 Sage 账号)
3. **双向能力互通**:Sage 能查 OmniDesk 业务;OmniDesk 能派任务给 Sage 执行本地操作
4. **Sage 能力天花板高于 OmniDesk**(能力扩展在 Sage 端);OmniDesk 守住"治理 + 业务数据"层
5. **MVP 在 1-2 个月内可演示**,覆盖最核心两个场景(查排班 + 本地文件扫描)

---

## 2. 设计原则(写进 spec 顶部,任何后续决策不得违反)

1. **独立优先**:任何一侧缺失,另一侧完整可用
2. **可选增强**:所有互通功能默认关闭,需用户主动启用
3. **配置驱动**:互通通过环境变量 / 设置项启用,不引入新的强一致组件
4. **降级完备**:超时 / 不可达 / 配置缺失,业务功能降级到原有路径,**永远不阻塞**
5. **不反向依赖**:OmniDesk 不依赖 Sage 服务端;Sage 不强依赖 OmniDesk API
6. **身份共享 ≠ 数据共享**:身份互通仅用于"能查什么",对话内容默认不共享

---

## 3. 非目标(明确不做)

为避免后续团队提"我们也加个 AI Agent"导致重复建设,**以下条目在本设计稿范围内明确不做**:

- ❌ OmniDesk 不自建记忆 / Agent / Skill 体系(避免与 Sage 重复建设)
- ❌ OmniDesk 不集成本地 LLM(继续走现有 Ollama / 直连 LLM 路径作为离线降级)
- ❌ OmniDesk 不提供 AI 能力扩展接口(能力扩展统一在 Sage 端)
- ❌ Sage 不引入"独立用户体系"(身份统一来自 OmniDesk)
- ❌ MVP 不做记忆双向同步(留中期)
- ❌ MVP 不做 Skill 双向互通(留中期)
- ❌ MVP 不做事件主动推送(留中期)
- ❌ MVP 不做组织级 Skill 审核流程(留长期)

---

## 4. 角色与能力归属

| 维度 | OmniDesk(组织级) | S agent(个人级) |
|---|---|---|
| **核心资产** | 业务数据 + 流程 + 治理 | AI 能力 + 本机资源 + 个人记忆 |
| **能力扩展点** | 业务 API 后端开发 | 本地工具 / Skill / ChromaDB |
| **扩展自由度** | 受 Django 后端开发节奏约束 | 无外部依赖,可独立扩展 |
| **能力天花板** | 组织采购了什么业务系统 | **用户整台电脑能做什么** |
| **演进趋势** | 守住"治理 + 业务数据"层 | **越来越强**(本地能力扩展不需要 OmniDesk 配合) |
| **AI 体验层** | 提供 OmniDesk Web 入口(走通道 A/B 拉 Sage 能力) | 终端用户体验层 |

**结论**:Sage 的 AI 应用能力会越来越强,OmniDesk 的 AI 应用能力相对弱化。**这是产品定位的合理分工,不是威胁**。OmniDesk 通过"AI 使用审计 / 权限边界 / 数据脱敏 / 组织级 Skill 审核"守住治理层。

---

## 5. 架构总览

### 5.1 部署拓扑

```
┌─────────────────────── 组织内网 ───────────────────────────┐
│                                                              │
│  ┌──────────────── OmniDesk (Django 4.2) ─────────────────┐ │
│  │  16 业务 app + Sage 集成层 (新增)                  │ │
│  │                                                        │ │
│  │  • CustomUser 扩展模型(OneToOne,见 6.1.1)              │ │
│  │    - sage_user_id / sage_last_sync_at                  │ │
│  │    - sage_local_features_enabled / sage_omnidesk_url   │ │
│  │  • 新增 app: sage_integration/                         │ │
│  │    - /api/sage/auth/        账号绑定                 │ │
│  │    - /api/sage/proxy/...    业务查询代理 (通道 A)     │ │
│  │    - /api/sage/tasks/...    任务派发与回写 (通道 B)   │ │
│  │    - /api/sage/local-files/ 本地文件元数据 (通道 B)   │ │
│  └────────────────────────────────────────────────────────┘ │
│                            ▲                                  │
│                            │ Sage 主动(通道 A 查询 + │
│                            │ 通道 B 自派+立即认领)   │
│  ┌──────────────── Sage 桌面端 (Electron) ────────────────┐ │
│  │  本地对话 + 记忆 + ChromaDB + Skill + MCP            │ │
│  │                                                        │ │
│  │  • 默认: 完全独立运行(无 OmniDesk 配置)              │ │
│  │  • 用户主动启用 OmniDesk 集成后:                       │ │
│  │    - 通道 A worker: 业务查询工具调用                  │ │
│  │    - 通道 B worker: 任务轮询 + 本地工具执行           │ │
│  │  • 本地能力边界:                                      │ │
│  │    - 文件系统 (用户配白名单)                          │ │
│  │    - 本地 ChromaDB 知识库                            │ │
│  │    - 本地 Skill 集                                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 双向通道定义

| 通道 | 名称 | 方向 | 触发 | 默认状态 |
|---|---|---|---|---|
| **通道 A** | 业务查询 | Sage → OmniDesk | Sage Agent 主动调 | 关闭(需配 OmniDesk URL + 凭证) |
| **通道 B** | 本地任务 | OmniDesk → Sage | Sage 桌面端自派 → OmniDesk 留痕 | 关闭(需用户在 Sage 设置里开启"接收 OmniDesk 任务") |

**通道 B 触发约束**:为避免 OmniDesk 自建 AI 能力(违反非目标),通道 B 任务**仅由 Sage 桌面端发起**,OmniDesk 仅作"任务留痕 + 审计 + 限流"。

---

## 6. 详细设计

### 6.1 身份与账号绑定

#### 6.1.1 OmniDesk 端数据模型变更

新建独立模型(`OneToOne` 关联 `CustomUser`),而非直接加字段到 `CustomUser`,原因:

- 避免污染用户主表
- 后续若回滚 Sage 集成,可整体删除该 app 不影响 `users/`
- 与现有"附属模型"惯例一致(如 `PhoneNumber`)

**新建 migration**:`sage_integration/migrations/0001_initial.py`

```python
class SageIntegrationFields(models.Model):
    """OmniDesk CustomUser 的 Sage 集成扩展字段。

    Why: Sage 不引入独立账号体系,身份统一来自 OmniDesk CustomUser。
    How to apply: OneToOne 扩展模型而非直接加字段,便于整体回滚。
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sage_integration',
        primary_key=True,
    )
    sage_user_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text='Sage 桌面端生成的稳定 UUID,标识 OmniDesk 用户',
    )
    sage_last_sync_at = models.DateTimeField(
        null=True, blank=True,
        help_text='最后一次通道 A/B 调用成功的时间戳',
    )
    sage_local_features_enabled = models.BooleanField(
        default=False,
        help_text='用户主动开启"接收 OmniDesk 任务"后的通道 B 开关',
    )
    sage_omnidesk_url = models.URLField(
        null=True, blank=True,
        help_text='Sage 上报的 OmniDesk 服务地址(冗余校验,防中间人)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### 6.1.2 绑定流程

```
Sage 桌面端                     OmniDesk
    │                              │
    │ 用户在设置页输入 OmniDesk URL │
    │ + username + password        │
    │                              │
    │──── POST /api/sage/auth/bind/ ▶│
    │     {username, password,      │
    │      sage_user_id (本机生成)} │
    │                              │
    │                              │ 验证 Django 用户密码
    │                              │ 校验 sage_user_id 唯一性
    │                              │ 生成 JWT (含 sage_user_id claim)
    │                              │
    │◀─── 200 {access, refresh, ────│
    │       user_profile}          │
    │                              │
    │ 本地加密存储 JWT              │
    │ (MVP: Electron safeStorage)  │
    │                              │
    │─── GET /api/sage/auth/whoami/ ▶│  (后续每次启动调用,验 token)
    │◀─── 200 {username, ...} ─────│
    │                              │
    │ 用户点"启用接收 OmniDesk 任务" │
    │                              │
    │─── POST /api/sage/local-feat/enable/ ▶│
    │◀─── 200 {ok} ────────────────│
```

#### 6.1.3 JWT 扩展

OmniDesk 现有 JWT 用 `djangorestframework-simplejwt`,**新增 claim**:
- `sage_user_id`:UUID,绑定时由 Sage 生成并写入用户档案
- `sage_local_features`:bool,通道 B 开关状态

不新增 token 类型,沿用现有 30min access + 7day refresh。

#### 6.1.4 凭证本地存储

- **不存明文密码**:绑定完成后 OmniDesk 仅下发 JWT,Sage 本机不保留密码
- **JWT 加密存储**:
 - **MVP**:Electron `safeStorage` API(跨平台 OK,数据用 OS 密钥加密)
  - **后续**:迁移到 OS 原生 keystore(Windows wincred / macOS Keychain / Linux Secret Service)
- **失败处理**:`safeStorage` 不可用 → 降级到 `localStorage` + 提示用户"加密存储不可用,token 明文存储"

### 6.2 通道 A:Sage → OmniDesk 业务查询

#### 6.2.1 OmniDesk 端新增 API

新建 app `sage_integration/`,结构:

```
sage_integration/
├── apps.py
├── models.py            # SageIntegrationFields, SageTask
├── auth_views.py        # /api/sage/auth/ 绑定 + 验证
├── proxy_views.py       # /api/sage/proxy/* 业务查询代理
├── task_views.py        # /api/sage/tasks/* 通道 B 任务派发
├── permissions.py       # IsSageAuthenticated 权限类
├── throttles.py         # SageProxyThrottle (按用户限流)
├── urls.py
├── serializers.py
├── migrations/
└── tests/
    ├── test_auth.py
    ├── test_proxy.py
    └── test_tasks.py
```

**API 列表**(MVP 阶段):

| Endpoint | 方法 | 用途 | 内部对应 OmniDesk API |
|---|---|---|---|
| `/api/sage/auth/bind/` | POST | 账号绑定(用户名密码 + sage_user_id) | 自有 |
| `/api/sage/auth/whoami/` | GET | JWT 校验 + 返回用户档案 | 自有 |
| `/api/sage/proxy/schedule/` | GET | 查询当前用户排班 | `events.views.schedule_*` |
| `/api/sage/proxy/personnel/` | GET | 查询人员信息(按姓名/部门) | `personnel.views.*` |

**代理实现要点**:
- **不是简单的透传代理** — 在代理层做权限收口、脱敏、字段裁剪
- 例:`personnel/` 返回字段裁剪到 `{id, name, department, position, phone}`,不返回身份证 / 银行账号等敏感字段
- 例:`schedule/` 仅返回 `request.user` 自己的排班,不返回他人排班

#### 6.2.2 Sage 端新增工具

在 Sage `backend/tools/` 下新增 `omnidesk_tools.py`:

```python
class OmniDeskScheduleTool(Tool):
    """查询当前登录用户在 OmniDesk 的排班。"""
    name = "omnidesk_query_schedule"
    description = "查询当前用户在 OmniDesk 的排班..."
    requires_user_auth = True  # 必须先完成 OmniDesk 绑定

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        token = ctx.user_session.omnidesk_jwt
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{ctx.user_session.omnidesk_url}/api/sage/proxy/schedule/",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
        if r.status_code != 200:
            return ToolResult(error=f"OmniDesk 排班查询失败: {r.status_code}")
        return ToolResult(data=r.json())


class OmniDeskPersonnelTool(Tool):
    """查询 OmniDesk 人员信息。"""
    name = "omnidesk_query_personnel"
    # ... 同上模式,内部调 /api/sage/proxy/personnel/
```

**注册位置**:Sage 现有 ToolRegistry,**按用户配置动态注册**(绑定了 OmniDesk 才注册,未绑定则该工具不存在,Agent 自然不会调用)。

#### 6.2.3 Sage 设置 UI

新增"连接到 OmniDesk"设置页:
- 输入 OmniDesk 服务 URL
- 输入 OmniDesk 用户名 / 密码(仅用于绑定一次)
- 状态显示:未绑定 / 已绑定(显示 username) / 凭证过期
- "解除绑定"按钮
- "启用接收 OmniDesk 任务"开关(通道 B 开关)

位置:`src/pages/settings/` 或 `src/features/settings/`,沿用现有设置 UI 模式。

#### 6.2.4 降级策略

```
Sage 发起业务查询
  │
  ├─ 未配置 OmniDesk URL? → Tool 直接返回 "未连接 OmniDesk,无法查询业务数据"
  │
  ├─ Token 失效 (401)?
  │    → 自动刷新一次 → 失败则提示用户"请重新连接 OmniDesk"
  │
  ├─ OmniDesk 不可达 / 超时 (5s)?
  │    → Tool 返回 "OmniDesk 当前不可达,请稍后重试"
  │    → Sage 用本地知识兜底回答(若有相关记忆)
  │
  └─ 成功 → 返回结构化数据给 Agent
```

**关键**:任何降级路径下,Sage 对话本身**永远不报错给用户**(只是工具调用失败,Agent 回答"我暂时无法查询,你可以...")。

### 6.3 通道 B:OmniDesk → Sage 本地任务

#### 6.3.1 任务模型

**OmniDesk 端** `sage_integration/models.py`:

```python
class SageTask(models.Model):
    """Sage 桌面端发起、OmniDesk 留痕的本地任务。

    Why: 不让 OmniDesk 自建 AI 触发能力(违反非目标),仅作审计/留痕/限流。
    """

    TASK_KIND_CHOICES = [
        ('local_file_scan', '本地文件扫描'),
        ('local_kb_search', '本地知识库查询'),
    ]
    STATUS_CHOICES = [
        ('pending', '等待 Sage 认领'),
        ('claimed', 'Sage 已认领,执行中'),
        ('done', '完成'),
        ('failed', '失败'),
        ('timeout', '超时'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sage_tasks',
        help_text='任务归属用户(只能本人发起/查询)',
    )
    kind = models.CharField(max_length=64, choices=TASK_KIND_CHOICES)
    params = models.JSONField(default=dict, help_text='任务参数')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    result = models.JSONField(null=True, blank=True, help_text='执行结果')
    error = models.TextField(blank=True, help_text='失败原因')
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text='任务过期时间,默认 1 小时后')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
        ]
```

#### 6.3.2 OmniDesk API(通道 B)

| Endpoint | 方法 | 用途 | 权限 |
|---|---|---|---|
| `/api/sage/tasks/` | POST | Sage 桌面端发起任务(只能给自己派) | `IsAuthenticated` + `sage_local_features_enabled=True` |
| `/api/sage/tasks/pending/` | GET | Sage 桌面端查询当前用户未认领任务 | JWT + `sage_local_features_enabled=True` |
| `/api/sage/tasks/<uuid:id>/claim/` | POST | Sage 认领任务(防止多端重复) | 同上 |
| `/api/sage/tasks/<uuid:id>/result/` | POST | Sage 回写执行结果 | 同上 |
| `/api/sage/tasks/<uuid:id>/` | GET | 查询单个任务状态 | `IsAuthenticated` (仅本人) |

**轮询间隔**:MVP 固定 30 秒一次;中期可改长轮询 / Server-Sent Events。

**任务过期**:`expires_at = created_at + 1h`,过期任务 Sage 不再 claim,OmniDesk 后台 cleanup 标记为 `timeout`。

#### 6.3.3 Sage 端实现

新增 `backend/integrations/omnidesk_reverse/`(Sage 桌面端的后台 worker):

```python
class OmniDeskReverseWorker:
    """Sage 后台 worker:发起本地任务到 OmniDesk 留痕 + 在本机执行。"""

    POLL_INTERVAL_SECONDS = 30

    def __init__(self, user_session: UserSession):
        self.user_session = user_session
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._poll_once()
            except Exception as e:
                logger.exception("OmniDesk 反向通道轮询异常: %s", e)
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _poll_once(self) -> None:
        if not self.user_session.omnidesk_local_features_enabled:
            return  # 用户没开启,完全 no-op

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{self.user_session.omnidesk_url}/api/sage/tasks/pending/",
                headers={"Authorization": f"Bearer {self.user_session.omnidesk_jwt}"},
            )
        if r.status_code != 200:
            return  # 静默降级,不打扰用户

        tasks = r.json()["tasks"]
        for task_summary in tasks:
            await self._execute_task(task_summary)

    async def _execute_task(self, task_summary: dict) -> None:
        # 1. claim
        # 2. 根据 task['kind'] 路由到对应本地工具
        # 3. 执行
        # 4. 回写结果
        pass
```

**通道 B 完整流程**(Sage 自派 + OmniDesk 留痕):

```
Sage 桌面端 (Electron)            OmniDesk
    │                              │
    │ 用户说"扫描我的合同文件夹"   │
    │                              │
    │ S agent 解析意图 → 决定执行 │
    │ local_file_scan              │
    │                              │
    │─── POST /api/sage/tasks/ ────▶│  (1) 留痕
    │     {kind: "local_file_scan",│
    │      params: {directory,     │
    │               pattern}}      │
    │                              │
    │◀─── 201 {task_id} ───────────│
    │                              │
    │─── POST .../claim/ ──────────▶│  (2) 立即认领(Sage 既是发起者又是执行者)
    │◀─── 200 ────────────────────│
    │                              │
    │ (3) 在本机执行文件扫描       │
    │     (路径白名单校验)         │
    │                              │
    │─── POST .../result/ ─────────▶│  (4) 回写结果
    │     {status: "done",         │
    │      result: {...}}          │
    │◀─── 200 ────────────────────│
    │                              │
    │ (5) S agent 拿到结果,在对话 │
    │     中展示给用户              │
```

**任务执行器**(MVP 两个):
- `local_file_scan(directory, pattern)` → 文件元数据采集 + 路径白名单校验
- `local_kb_search(query)` → 调 Sage `ChromaDB` 客户端

#### 6.3.4 安全边界

- **路径白名单**:用户在 Sage 设置里配置"允许 OmniDesk 任务访问的目录白名单",S agent 端校验
- **文件大小限制**:单个扫描任务最多返回 1000 个文件,单个文件元数据不含内容
- **执行超时**:单任务 60s 超时,失败标记 `timeout`
- **结果脱敏**:文件路径在 OmniDesk 端持久化前去除用户主目录前缀(`/home/user/...` → `/...`)

### 6.4 复用 vs 新建

| 能力 | 是否复用现有 | 说明 |
|---|---|---|
| JWT 颁发与校验 | ✅ 复用 `djangorestframework-simplejwt` | 仅扩展 claim |
| 用户模型 | ✅ 复用 `CustomUser` | 新字段通过 OneToOne 扩展模型 |
| Throttle | ✅ 复用 `core.throttles.*` | 通道 A 单独配 `SageProxyThrottle` |
| 测试模式 | ✅ 复用 `settings.test` | Sage 集成测试用 in-memory SQLite |
| DRF ViewSet | ✅ 复用 DRF 风格 | 不引入新框架 |
| Sage 现有 ToolRegistry | ✅ 复用 | 通道 A 工具按用户配置动态注册 |
| Sage 现有 ChromaDB | ✅ 复用 | 通道 B `local_kb_search` 直接调 |
| Sage 现有调度循环 | ✅ 复用 | 通道 B worker 作为新 asyncio task |
| OmniDesk `core/observability_logger` | ✅ 复用 | 复用现有指标基础设施 |

### 6.5 安全设计

| 风险 | 缓解 |
|---|---|
| Sage 拿到 JWT 后滥用 | JWT 含 `sage_user_id` claim,OmniDesk 后端所有 `sage_integration` 接口强校验一致性 |
| 通道 B 文件越权访问 | 用户在 Sage 设置里配置"允许 OmniDesk 任务访问的目录白名单";Sage 端校验 |
| 中间人攻击 | OmniDesk 内网部署 + JWT 短有效期(30min);Sage 本地存 `omnidesk_url` 与首次绑定 URL 校验 |
| 业务敏感数据泄露 | 代理层字段裁剪(见 6.2.1);`personnel` 不返回身份证 / 银行账号 |
| 任务队列被恶意填充 | `SageTask` 限流:每用户每小时最多 20 个任务 |
| Sage 桌面端被冒充 | JWT 绑定 + Sage 上报本机指纹(`sage_user_id` 在首次绑定时生成) |
| 凭证泄露 | 不存明文密码;JWT 用 OS keystore 加密;MVP 用 Electron `safeStorage` |

### 6.6 性能与可用性

| 指标 | MVP 目标 |
|---|---|
| 通道 A 响应时间 | P95 < 2s(本地网络 + JWT 校验 + 业务查询) |
| 通道 B 任务平均延迟 | < 30s(轮询间隔 + 执行时间) |
| 通道 B 任务超时 | 1h(OmniDesk 端 `expires_at`) |
| 通道 A 不可达降级 | 自动,用户无感 |
| 通道 B 不可达降级 | Sage 静默重试,不打扰用户 |
| Token 刷新 | 复用 simplejwt 现有 7day refresh |

### 6.7 测试策略

**OmniDesk 端**(沿用 pytest + DRF APIClient):
- `test_auth.py`:绑定 / 解绑 / JWT 校验 / claim 一致性
- `test_proxy.py`:业务查询代理字段裁剪 / 权限校验 / 限流
- `test_tasks.py`:任务创建 / 轮询 / 认领 / 结果回写 / 超时

**Sage 端**(沿用现有 pytest):
- `test_omnidesk_auth.py`:绑定流程 / JWT 存储
- `test_omnidesk_reverse_worker.py`:轮询 / 任务路由 / 结果回写 / 异常降级
- `test_omnidesk_tools.py`:通道 A 工具调用 / 错误处理

**集成测试**(可选,MVP 不强制):
- 用 OmniDesk test settings 起服务,Sage 端 e2e 测试绑定 → 业务查询 → 本地任务全链路

**测试覆盖目标**:核心路径 ≥ 80%(沿用现有规则)。

### 6.8 部署与发布

**OmniDesk 端**:
- 新 app `sage_integration/` + migration
- 不需要新的环境变量(默认不通)
- 启用条件:管理员在 `settings.py` 加 `SAGE_INTEGRATION_ENABLED = True`(默认 False,**全功能开关**,彻底关闭互通)

**Sage 桌面端**:
- 新增设置页 + 后台 worker
- 默认不启用,需用户主动配 OmniDesk URL + 凭证
- Win7 LTS 客户端:**完全支持**(Python 3.8 + 标准 httpx / json 都 OK,Electron `safeStorage` 在 Win7 上需 Step 4.4 验证)
- 主线 Win10+ / macOS / Linux:**完全支持**

**发布顺序**:
1. OmniDesk 端先发(后端先行,前端不动)— 单独 PR
2. Sage 桌面端跟随发 — 单独 PR
3. 任一先发都不破坏另一侧运行(独立原则)

### 6.9 监控与可观测性

- 复用 OmniDesk 现有 `core/observability_logger.py`(已有)
- 新增 metrics:
 - `sage_auth_bind_total`(counter,按 success/failure)
 - `sage_proxy_request_total`(counter,按 endpoint / status)
 - `sage_task_dispatch_total`(counter,按 kind / status)
 - `sage_task_duration_seconds`(histogram)
- 复用 Sage 现有 `prometheus` adapter
- 不引入新的监控系统

---

## 7. 实施步骤(MVP 边界)

按依赖顺序排列,**每步独立可验证**:

### 阶段 1:OmniDesk 后端基础(预计 1 周)

- [ ] **Step 1.1**:新建 `sage_integration` app + Django settings 注册
- [ ] **Step 1.2**:`SageIntegrationFields` 模型 + migration
- [ ] **Step 1.3**:`IsSageAuthenticated` 权限类 + `SageProxyThrottle` 限流
- [ ] **Step 1.4**:`/api/sage/auth/bind/` + `/api/sage/auth/whoami/` 实现 + 测试
- [ ] **Step 1.5**:`settings.SAGE_INTEGRATION_ENABLED` 全局开关
- [ ] **Step 1.6**:OmniDesk 端单元测试覆盖(目标 ≥ 80%)

### 阶段 2:OmniDesk 通道 A 业务代理(预计 1 周)

- [ ] **Step 2.1**:`/api/sage/proxy/schedule/` — 调 `events.views.schedule_*`,字段裁剪到本人排班
- [ ] **Step 2.2**:`/api/sage/proxy/personnel/` — 调 `personnel.views.*`,字段裁剪敏感项
- [ ] **Step 2.3**:两个 endpoint 单元测试 + 集成测试
- [ ] **Step 2.4**:`SageIntegrationFields` 中 `sage_last_sync_at` 字段在通道 A 调用成功时更新

### 阶段 3:OmniDesk 通道 B 任务模型与 API(预计 1 周)

- [ ] **Step 3.1**:`SageTask` 模型 + migration
- [ ] **Step 3.2**:`/api/sage/tasks/` POST + GET(单任务查询)+ `/pending/` GET
- [ ] **Step 3.3**:`/claim/` + `/result/` POST 实现 + 状态机校验
- [ ] **Step 3.4**:任务限流(每用户每小时 20 个)+ 超时 cleanup 命令
- [ ] **Step 3.5**:单元测试 + 集成测试

### 阶段 4:Sage 设置 UI(预计 0.5 周)

- [ ] **Step 4.1**:Sage 设置页新增"连接到 OmniDesk"区块
- [ ] **Step 4.2**:绑定表单 + 状态显示 + 解除绑定
- [ ] **Step 4.3**:`safeStorage` 存 JWT + 启动时 whoami 校验
- [ ] **Step 4.4**:Win7 LTS 验证(`safeStorage` 在 Electron 21 上的兼容性)

### 阶段 5:Sage 通道 A 工具(预计 1 周)

- [ ] **Step 5.1**:`backend/tools/omnidesk_tools.py` — `OmniDeskScheduleTool` + `OmniDeskPersonnelTool`
- [ ] **Step 5.2**:ToolRegistry 按用户配置动态注册(未绑定不注册)
- [ ] **Step 5.3**:HTTP 客户端 + 超时 + 401 自动刷新
- [ ] **Step 5.4**:降级路径 + 单元测试

### 阶段 6:Sage 通道 B 反向 worker(预计 1 周)

- [ ] **Step 6.1**:`OmniDeskReverseWorker` 异步任务 + 启动 / 停止生命周期
- [ ] **Step 6.2**:`local_file_scan` 执行器 — 路径白名单校验 + 文件元数据采集
- [ ] **Step 6.3**:`local_kb_search` 执行器 — 复用现有 ChromaDB 客户端
- [ ] **Step 6.4**:结果回写 + 异常处理
- [ ] **Step 6.5**:单元测试 + 端到端冒烟测试

### 阶段 7:文档与发布(预计 0.5 周)

- [ ] **Step 7.1**:`docs/technical/40-omnidesk-sage-integration.md` — 架构 / API / 部署 / 故障排查
- [ ] **Step 7.2**:更新 `docs/user-manual/40-sage-integration.md`(用户视角)
- [ ] **Step 7.3**:更新 `docs/technical/README.md` 章节目录
- [ ] **Step 7.4**:OmniDesk 端 CHANGELOG.md 增条目
- [ ] **Step 7.5**:Sage 端 CHANGELOG 增条目

**总周期估算**:6 周(留 buffer 后约 7-8 周)。

---

## 8. 中期 / 长期路线(非 MVP)

### 中期(3-6 个月)

- 通道 A 业务查询工具扩展:`approvals` / `meeting_rooms` / `sensors` / ...
- Sage 记忆定时同步到 OmniDesk(管理员可审计 AI 使用情况)
- OmniDesk 用户档案页加"Sage 同步状态"显示
- 通道 B 工具扩展:`local_file_read` / `local_skill_invoke`
- 任务轮询升级为长轮询 / Server-Sent Events

### 长期(6-12 个月)

- OmniDesk 业务事件主动推送给 Sage(审批通过 → Sage 整理相关文件)
- Sage Skill 经过 OmniDesk 审核后组织级发布
- 统一 RAG 检索:Sage 长期记忆 + OmniDesk RAGFlow 文档检索合并

---

## 9. 风险与决策记录

### 9.1 已识别风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| Sage 本地记忆组织可见引发隐私争议 | 中 | 同步前明示 + 颗粒度可选 + 用户可关闭(MVP 不做同步,中期引入时设计) |
| OmniDesk 单点故障影响 Sage | 中 | Sage 断网降级到本地模式(无业务数据但能用) |
| JWT 泄露 | 中 | 短有效期 + OS keystore 加密 + 仅本人通道校验 |
| 业务敏感数据泄露 | 中 | 代理层字段裁剪白名单 |
| 任务队列被恶意填充 | 中 | 每用户每小时限流 20 个 |
| Sage 桌面端被冒充 | 中 | `sage_user_id` 指纹绑定 |
| Win7 LTS `safeStorage` 兼容性 | 低 | Electron 21 `safeStorage` 在 Windows 7 上需 Step 4.4 验证 |
| 互通代码污染 OmniDesk 主代码 | 中 | 新建独立 `sage_integration` app,不修改 16 个业务 app 的代码 |
| 用户配置错误导致死循环 | 低 | 轮询超时 + 异常吞掉,不阻塞 Sage 主循环 |

### 9.2 关键决策记录

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 身份体系 | A: Sage 独立账号 / B: 复用 OmniDesk | **B** | 单一身份源,降低管理成本 |
| 部署形态 | A: Sage 服务端 / B: 桌面端为主 | **B** | 桌面端是 Sage 唯一形态;互通层全在桌面端,Win7 LTS 友好 |
| 互通方向 | A: 单向 / B: 双向 | **B**(MVP 两通道) | 用户明确要求"互相能调" |
| 互通强度 | A: 强依赖 / B: 弱耦合可选 | **B** | 用户明确要求"独立使用是常态,增强是可选" |
| 触发通道 B | A: OmniDesk 主动派发 / B: Sage 自派 | **B** | 避免 OmniDesk 自建 AI 能力,符合"OmniDesk 不做 AI"非目标 |
| JWT 存储 | A: localStorage / B: Electron safeStorage | **B**(MVP) | 跨平台基本可用;后续迁移到 OS 原生 keystore |
| 字段裁剪层位置 | A: OmniDesk 业务 API 自带 / B: sage_integration 代理层 | **B** | 不污染 16 个业务 app,sage_integration 独立可禁用 |
| 轮询 vs 反向 HTTP | A: HTTP 反向回调 / B: 主动轮询 | **B** | NAT 后用户电脑无法接收外部连接,轮询最稳 |

---

## 10. 验收标准(MVP 完成判定)

- [ ] OmniDesk 端 `sage_integration` app 单元测试覆盖率 ≥ 80%
- [ ] Sage 端通道 A/B 代码单元测试覆盖率 ≥ 80%
- [ ] 集成测试:OmniDesk test settings + Sage 端,绑定 → 业务查询 → 本地任务全链路通过
- [ ] Win7 LTS 客户端可正常绑定 OmniDesk + 调用业务查询
- [ ] 任何一侧缺失 / 不可达,另一侧功能不受影响(独立原则验证)
- [ ] 关闭 `settings.SAGE_INTEGRATION_ENABLED` 后,OmniDesk 端 sage_integration 接口全部不可用
- [ ] Sage 不配 OmniDesk 时,完全等价于当前版本(回归验证)
- [ ] 文档齐备:`docs/technical/40-omnidesk-sage-integration.md` + `docs/user-manual/40-sage-integration.md`
- [ ] CHANGELOG 双端更新
- [ ] OmniDesk CI + Sage CI 全绿

---

## 11. 开放问题(留待实施时确认)

1. **OmniDesk 排班 API 现有形态**:需在 Step 2.1 实施时确认 `events.views.schedule_*` 的具体 endpoint 与权限模型,确认字段裁剪边界
2. **OmniDesk 人员 API 现有形态**:同上,Step 2.2 需核对 `personnel.views.*`
3. **Sage 现有 ChromaDB 客户端 API**:Step 6.3 实施时确认
4. **Electron safeStorage 在 Windows 7 上的行为**:Step 4.4 验证,失败则改用 DPAPI 替代
5. **OmniDesk 现有 JWT 是否需要额外 revoke 机制**(MVP 阶段如发现需要,单独处理)

---

**Spec 状态**:待用户复审后进入 writing-plans 阶段。