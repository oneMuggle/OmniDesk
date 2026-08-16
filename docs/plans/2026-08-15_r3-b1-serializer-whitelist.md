# R3-B1: Serializer `__all__` 白名单化(后端 API 安全)

> 日期:2026-08-15 | 状态:实施中(PR-1 完成,待 merge)
> 来源:`docs/plans/2026-08-14_project-optimization-round3.md` §R3-B1
> 关联:round3 本体 plan;前端字段依赖分析已由 Explore agent 完成

## 1. 背景与目标

当前 11 个 app 的 serializer 中共 **34 处** `fields = "__all__"`,导致:

- **模型全部字段经 API 直暴露**,含敏感字段(身份证号、API 密钥、证件编号、LLM 日志内部数据等)
- 无法精确控制"哪些字段可读 / 可写",为越权与数据泄露埋雷

**目标**:逐 app 白名单化,每个 serializer 显式声明字段,同时剔除敏感字段,并配套 serializer 单测锁定白名单(防回归)。白名单化后前端消费字段不受影响(已通过前端字段依赖分析验证)。

## 2. 现状与发现(调研结论)

### 2.1 高危敏感字段(本 plan 必须处理)

| 严重级别 | 位置 | 问题 | 修复 |
|---|---|---|---|
| 🔴 CRITICAL | `external_integration/serializers.py:98` IntegrationServiceSerializer | `api_key` 用 `EncryptedCharField` 加密存储,但 `__all__` 读取时**解密后明文暴露**。任何能访问 `/api/external/integrations/` 的登录用户可读全部集成服务密钥。前端未消费此字段(已 grep 确认)。 | `api_key` 设 `write_only=True`(保留写入能力,读取不返回) |
| 🔴 HIGH | `personnel/serializers.py:39` FamilyMemberSerializer | 模型含 `id_card_number`(Fernet 加密存储,读取时解密)。`__all__` 在人员详情接口返回明文身份证。前端不消费该字段。 | 白名单剔除 `id_card_number` |
| 🟠 MEDIUM | `personnel/serializers.py:33` ProfessionalQualificationSerializer | `certificate_id`(证件编号)随 `__all__` 暴露,前端未消费。 | 白名单剔除 `certificate_id` |
| 🟠 MEDIUM | `smart_assistant/serializers.py:94` AgentLogSerializer | `__all__` 暴露 `session` FK、token/费用、`tool_calls_meta`、`tool_call_path`、`user_feedback` 等内部审计数据。**注意**:视图层已有 IDOR 归属隔离(普通用户仅能看自己的日志,staff 才能跨用户),本项为字段收敛而非越权修复。 | 白名单收敛为前端消费字段 |

### 2.2 附带发现(本轮不强制,仅标注)

- `meeting_rooms/serializers.py:20` MeetingRoomBookingSerializer 嵌套 `UserDetailSerializer`,其 `user` 嵌套含 `phone_numbers`(联系电话)。前端 `MeetingRoomBookingPage.jsx` 展示 `user.phone_numbers[0].number`。嵌套字段非 `__all__` 本身,本轮保留现状,作为后续"最小化用户信息暴露"评估项。
- 前端存在多处"幻字段"(访问后端不存在的字段名,当前恒 undefined,白名单化不会恶化):`ProfessionalQualification.name/issuing_authority`、`UploadedImage.url`、`Announcement.author.username/real_name`、`documents.DocumentTemplate.updatedAt` 等。不纳入本轮范围。
- `users/serializers.py:96` PositionSerializer 为**死代码**(全库无 view 引用;`personnel/views.py` 用的是 `personnel.serializers.PositionSerializer`),直接删除。

## 3. 技术方案

### 3.1 白名单原则

1. **保留前端消费字段**(依赖分析已核实,见各 serializer 对照表)
2. **剔除敏感字段**:`api_key`(write_only)、`id_card_number`、`certificate_id`
3. **保留嵌套字段**:`TrialSerializer.time_slots/responsible_persons/equipments`、`ScheduleSerializer.duty_person/duty_leader`、`MeetingRoomBookingSerializer.user/meeting_room_name`、`TagSerializer` 嵌套等前端深度消费项
4. **保留时间戳**:`created_at`/`updated_at` 一律保留(前端列表展示常用)
5. 显式声明 `read_only_fields` 保持原有写保护不变

### 3.2 分 PR 与字段对照表

按 app 相关性与风险分 **4 个 PR**,每 PR 独立可合并、独立回归。

---

#### PR-1 (P0 安全)external_integration + smart_assistant

**`external_integration/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| ExternalLinkSerializer (L91) | `("id","name","url","icon","description","category","sso_enabled","sso_token_endpoint","sort_order","is_active","created_at","updated_at")` | 前端全消费,`sso_token_endpoint` 为内部端点 URL,前端必读保留 |
| IntegrationServiceSerializer (L98) | `("id","name","slug","description","integration_type","endpoint_url","api_key","embed_path","config_schema","metadata","is_active","created_at","updated_at")` + `extra_kwargs={"api_key":{"write_only":True}}` | 🔴 `api_key` 改 write_only,读响应不再返回明文密钥 |
| PluginSerializer (L118) | `("id","name","slug","description","author","category","icon","status","interface_version","versions","created_at","updated_at")` | 前端消费字段 + versions 嵌套(PluginVersionSerializer 已白名单) |

**`smart_assistant/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| AgentLogSerializer (L94) | `("id","user_query","intent","tool_used","tool_input","tool_output","llm_response","created_at")` | 收敛为 AgentAuditPanel 消费字段;剔除 session/token/费用/tool_call_path/tool_calls_meta/user_feedback/model_name/response_time_ms/tool_success |

---

#### PR-2 (P0 安全)personnel

**`personnel/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| PositionSerializer (L9) | `("id","name")` | 下拉/表格消费 |
| ContractSerializer (L15) | `("id","personnel","contract_number","contract_type","start_date","end_date")` | 前端详情/编辑消费 + 写回 personnel |
| EducationSerializer (L21) | `("id","personnel","school","degree","major","start_date","end_date")` | 全消费 |
| WorkExperienceSerializer (L27) | `("id","personnel","company","position","start_date","end_date","description")` | 全消费 |
| ProfessionalQualificationSerializer (L33) | `("id","personnel","qualification_name","issue_date","expiry_date")` + `certificate_id` write_only | 🟠 `certificate_id`(证件编号)改 write_only,读响应不返回 |
| FamilyMemberSerializer (L39) | `("id","personnel","name","relationship","contact_number")` + `id_card_number` write_only | 🔴 `id_card_number`(身份证)改 write_only,读响应不返回明文 |

---

#### PR-3 (P1)events + meeting_rooms

**`events/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| TimeSlotSerializer (L25) | `("id","trial","start_time","end_time","description")` | 前端全消费 |
| TrialSerializer (L42) | `("id","title","version","client","description","start_date","end_date","equipments","responsible_persons","status","created_at","updated_at","time_slots_data","time_slots")` | `time_slots_data` 为 write_only 自定义字段保留;嵌套 `time_slots` 前端深度消费(eventTransformers.jsx/TrialDetails.jsx),必须保留(表格补全) |
| DocumentTemplateSerializer (L67) | `("id","name","experiment_type","template_file","created_at","owner")` | 后端无 API 出口(仅 admin),白名单化收敛 |
| ScheduleSerializer (L76) | `("id","duty_date","duty_person","duty_leader")` | 嵌套保留 |
| AnnouncementSerializer (L82) | `("id","title","content","author","created_at","updated_at")` | 前端消费 |
| UploadedImageSerializer (L88) | `("id","image","uploaded_at")` | 前端读幻字段 `url`,保留 `image` |
| HolidaySerializer (L233) | `("id","name","start_date","end_date")` | 前端全消费 |

**`meeting_rooms/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| MeetingRoomSerializer (L11) | `("id","name","description","capacity","location")` | 前端全消费 |
| MeetingRoomBookingSerializer (L20) | `("id","meeting_room","user","start_time","end_time","title","participants","description","created_at","updated_at","meeting_room_name")` | `user` 嵌套(UserDetailSerializer)前端深度消费,保留 |
| MeetingRoomMaintenanceSerializer (L29) | `("id","meeting_room","start_time","end_time","reason","created_at","updated_at","meeting_room_name")` | 前端全消费 |

---

#### PR-4 (P2)documents + config + users + news + projects + sensor_management

**`documents/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| DocumentTemplateSerializer (L15) | `("id","project","name","template_type","content","extracted_text","created_at","updated_at","owner","project_name")` | 前端消费 id/name/project_name/project;content 保留(模板业务数据) |
| GeneratedDocumentSerializer (L26) | `("id","template","content","generated_by","generated_at","is_final","content_preview")` | 前端无消费,白名单收敛 |
| TagSerializer (L39) | `("id","name")` | 嵌套于 BookSerializer |
| EBookSerializer (L104) | `("id","title","author","content","created_at")` | 前端无消费(前端打 `/api/ebooks/` 属另一 app) |

**`config/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| PageSerializer (L24) | `("id","name","path")` | 前端消费 id/name |
| PageVisibilitySerializer (L37) | `("id","page","group","is_visible")` | 后端未使用(裸 ViewSet 手工组装),收敛即可 |

**`users/serializers.py`**

| Serializer | 处理 | 说明 |
|---|---|---|
| PositionSerializer (L96) | **删除** | 死代码,全库无 view 引用;`personnel/views.py` 用 personnel 自己的 PositionSerializer |

**`news/serializers.py`** / **`projects/serializers.py`** / **`sensor_management/serializers.py`**

| Serializer | 白名单 fields | 说明 |
|---|---|---|
| news.NewsTypeSerializer (L11) | `("id","name")` | 嵌套于 NewsArticleSerializer |
| projects.ProjectSerializer (L9) | `("id","name","description","start_date","end_date","status","manager","created_at","updated_at")` + `extra_kwargs={"manager":{"write_only":True}}` | 读响应收敛 manager(前端未消费);写路径保留——`projects/views.py` perform_create 要求 Admin 创建项目必须指定 manager |
| sensor.SensorCategorySerializer (L17) | `("id","name","description","created_at","updated_at")` | 前端消费 |
| sensor.StorageLocationSerializer (L24) | `("id","name","description","created_at","updated_at")` | 前端消费 |
| sensor.CalibrationDataPointSerializer (L31) | `("id","sensor_calibration","pressure_value","positive_trip_voltage_1","positive_trip_voltage_2","positive_trip_voltage_3","negative_trip_voltage_1","negative_trip_voltage_2","negative_trip_voltage_3")` | 嵌套于 SensorCalibrationSerializer |
| sensor.SensorMovementSerializer (L127) | `("id","sensor","movement_type","movement_date","operator","quantity","reason","destination_source")` | 前端无消费,收敛 |
| sensor.CalibrationReminderSerializer (L136) | `("id","sensor","remind_date","is_sent","sent_date","notes","reminded_users","created_at","updated_at")` | 前端无消费,收敛 |

## 4. 实施步骤

> 每 PR 独立走 feature 分支 → PR → CI 绿 → AI 检阅 → merge。每个 PR 内先写/改 serializer 单测(RED),再改 serializer(GREEN)。

### PR-1: external_integration + smart_assistant(P0)

- [x] 分支 `refactor/r3-b1-serializer-whitelist-ext-integ`
- [x] 写 `external_integration/tests/` serializer 测试:断言读响应**不含** `api_key`、写入接受 `api_key`
- [x] 白名单化 ExternalLinkSerializer / IntegrationServiceSerializer / PluginSerializer
- [x] 写 `smart_assistant/tests/` AgentLogSerializer 测试:断言字段白名单
- [x] 白名单化 AgentLogSerializer
- [x] 后端全量 pytest(2490 passed)+ 前端 build 冒烟(✓ built in 23.82s)
- [x] AI 检阅(PR #271)修复:① ragflow_service.RagflowConfigSerializer 同类 CRITICAL(api_key write_only,IsAdminOrReadOnly 下任意登录用户可读明文密钥)② 前端 IntegrationManagementPage 编辑表单回归(openEditModal 先 resetFields + 编辑时空 api_key 不提交,防残留密钥覆盖)③ 补 API 层契约测试(GET 不含 api_key / PUT 不带 api_key 保留原密钥)。修复后全量 2495 passed,前端 build ✓

### PR-2: personnel(P0)

- [x] 分支 `refactor/r3-b1-serializer-whitelist-personnel`
- [x] 写 `personnel/tests/` serializer 测试:FamilyMember 读响应**不含** `id_card_number`、ProfessionalQualification 不含 `certificate_id`
- [x] 白名单化 6 个 serializer
- [x] 后端全量 pytest(2503 passed)+ 前端 build 冒烟 + 人员详情页字段消费安全网确认(前端仅消费 Personnel 主表 id_card_number,FamilyMember 嵌套零消费)
- [x] AI 检阅(PR #274)修复:`id_card_number`/`certificate_id` 由「剔除」改为 **write_only**(保留写能力,读响应不返回;与 api_key 决策一致,避免 API 写路径静默丢弃);补 2 个写路径测试

### PR-3: events + meeting_rooms(P1)

- [x] 分支 `refactor/r3-b1-serializer-whitelist-events`
- [x] 写 events / meeting_rooms serializer 测试(15 个:7 serializer 字段集契约 + Trial 嵌套/写路径 + meeting_rooms 嵌套)
- [x] 白名单化 events 7 处 + meeting_rooms 3 处(发现:TrialSerializer 表格原漏 `time_slots` 嵌套,§3.1 原则保留,已修正表格)
- [x] 后端全量 pytest(2520 passed)+ 前端 build 冒烟(✓ built in 22.48s)
- [x] AI 检阅(PR #277)修复:无 CRITICAL/HIGH;补 7 个写路径契约测试(Booking/Maintenance/MeetingRoom/Holiday/Announcement/Schedule/DocumentTemplate 写接受,防未来误删可写字段)。修复后全量 2527 passed

### PR-4: documents + config + users + news + projects + sensor_management(P2)

- [x] 分支 `refactor/r3-b1-serializer-whitelist-misc`
- [x] 写各 app serializer 测试(5 个测试文件,20 个用例:字段集契约 + write-path + 嵌套保留)
- [x] 白名单化 13 处 + 删除 users.PositionSerializer
- [x] 后端全量 pytest(2547 passed)+ 前端 build 冒烟
- [x] AI 检阅修复:① `projects.ProjectSerializer.manager` 由「剔除」改为 **write_only**——发现 `projects/views.py` perform_create 契约:Admin 创建项目**必须**经请求体指定 manager,剔除会破坏该功能且使既有测试 `test_create_project_with_specified_manager` 失败;改为 write_only 后读响应收敛(前端零消费)写路径保留,与 api_key/id_card_number 决策一致。补 1 个 write-path 测试(test_write_accepts_manager)

### 收尾

- [ ] 全部 PR merge 后,更新 round3 plan 的 R3-B1 状态为 ✅
- [ ] 按 round3 §9 验收:`pytest --cov-fail-under=80` 全绿
- [ ] 归档:本 plan 完成后删除,内容并入 round3 验收

## 5. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| 白名单化后前端缺字段报错 | 每 serializer 白名单基于前端依赖分析(Agent 已核实消费字段);每 PR 后前端冒烟验证 |
| `api_key` write_only 后管理页无法回显密钥 | 前端已 grep 确认**无** api_key 消费;write_only 仍允许写入。若发现遗漏消费点,在 PR-1 阶段同步修复 |
| 嵌套 serializer 依赖(如 TrialSerializer 引用 personnel serializer) | personnel 白名单在 PR-2,若 PR-1 先行需确认无交叉影响;实际 PR-1 不依赖 personnel 嵌套字段,顺序安全 |
| 删除 users.PositionSerializer 破坏外部引用 | 已 grep 确认全库无引用,删除安全 |
| DRF 校验:write_only 字段必须出现在 fields 中 | IntegrationServiceSerializer 的 `api_key` 保留在 fields + extra_kwargs write_only,符合 DRF 契约 |

## 6. 依赖

- 前端字段依赖分析(本 plan §3.2 对照表)由 Explore agent 完成,已核实
- 无阻塞性依赖;PR 间字段无交叉(各 serializer 独立)
