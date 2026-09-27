# 46 AI 能力目录

> **本文件由代码自动生成，请勿手工编辑。**
> 生成命令：`cd omni_desk_backend && python manage.py ai_capabilities --write`
> 数据来源：各 app 的 `ai_tools.py`（`smart_assistant/capabilities`）。测试会校验本文件与代码一致。

## 概览

共 17 个工具集、28 个工具：只读 21 个，写入 6 个，删除 1 个。

| 工具集 | 所属 app | 工具（intent） |
| --- | --- | --- |
| 人员（`personnel`） | `personnel` | `personnel_query` |
| 排班与日程（`schedule`） | `events` | `schedule_query`、`event_query`、`swap_request_query`、`swap_request_create`、`swap_request_decide` |
| 公文与模板（`documents`） | `documents` | `document_search` |
| 备忘录（`memos`） | `memos` | `memo_query`、`memo_create`、`memo_update`、`memo_delete` |
| 项目（`projects`） | `projects` | `project_status` |
| 合规（`compliance`） | `compliance` | `compliance_query` |
| 会议室（`meeting_rooms`） | `meeting_rooms` | `meeting_room_query` |
| 传感器（`sensors`） | `sensor_management` | `sensor_query` |
| 交流与公告（`communication`） | `communication` | `announcement_query`、`communication_thread_query` |
| 新闻（`news`） | `news` | `news_search` |
| 知识库（`knowledge`） | `smart_assistant` | `knowledge_qa` |
| 办公文件（`office`） | `smart_assistant` | `office_read`、`spreadsheet_qa`、`office_generate` |
| 通知（`notifications`） | `notifications` | `notification_query`、`agent_notify` |
| 内网外链（`external_links`） | `external_integration` | `external_link_query` |
| 文档库（`document_library`） | `paperless_proxy` | `document_library_query` |
| 跨模块检索（`search`） | `search_federation` | `global_search` |
| 联培生（`joint_students`） | `joint_students` | `joint_student_query` |

## 工具明细

### 人员（`personnel`）

声明位置：`personnel/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `personnel_query` | 查询人员 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询人员信息（姓名、部门、职位、状态） |

### 排班与日程（`schedule`）

声明位置：`events/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `schedule_query` | 查询排班 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询排班、值班安排 |
| `event_query` | 查询日程与节假日 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询事件/日程/排班/节假日 |
| `swap_request_query` | 查询换班申请 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询换班申请状态(我发起的 / 我收到的) |
| `swap_request_create` | 发起换班申请 | 写入 | 登录即可 | 三级 scope | 本人确认 | — | 基于自然语言发起换班/替班申请(接收方决策后生效) |
| `swap_request_decide` | 处理换班申请 | 写入 | 登录即可 | 三级 scope | 本人确认 | — | 对收到的换班申请做出决策(accept/reject/cancel) |

### 公文与模板（`documents`）

声明位置：`documents/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `document_search` | 搜索公文 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 搜索公文/文档（按标题/类型/状态） |

### 备忘录（`memos`）

声明位置：`memos/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `memo_query` | 查询备忘录 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询备忘录/便签 |
| `memo_create` | 创建备忘录 | 写入 | 登录即可 | 三级 scope | 本人确认 | — | 基于自然语言创建一条备忘录/便签(支持设置提醒时间) |
| `memo_update` | 修改备忘录 | 写入 | 登录即可 | 三级 scope | 本人确认 | — | 基于自然语言修改一条已有备忘录/便签(支持改标题、内容、提醒时间) |
| `memo_delete` | 删除备忘录 | 删除 | 登录即可 | 三级 scope | 本人确认 | — | 基于自然语言删除一条已有备忘录/便签(破坏性操作,需二次确认) |

### 项目（`projects`）

声明位置：`projects/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `project_status` | 查询项目状态 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询项目进度/状态/负责人 |

### 合规（`compliance`）

声明位置：`compliance/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `compliance_query` | 查询合规问题 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询合规问题/待整改项(compliance.ComplianceIssue) |

### 会议室（`meeting_rooms`）

声明位置：`meeting_rooms/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `meeting_room_query` | 查询会议室 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询会议室可用性和预订 |

### 传感器（`sensors`）

声明位置：`sensor_management/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sensor_query` | 查询传感器 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询传感器数据和告警 |

### 交流与公告（`communication`）

声明位置：`communication/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `announcement_query` | 查询公告 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询公司公告/通知(communication.Post) |
| `communication_thread_query` | 查询交流帖子 | 只读 | 登录即可 | 同模块接口 | — | 幂等 | 查询交流区帖子及最近评论（可按关键词、只看我发的帖子筛选） |

### 新闻（`news`）

声明位置：`news/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `news_search` | 搜索新闻 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 搜索新闻/通知 |

### 知识库（`knowledge`）

声明位置：`smart_assistant/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `knowledge_qa` | 知识库问答 | 只读 | 登录即可 | 知识库 | — | 幂等、访问外部系统 | 从知识库查询业务知识 |

### 办公文件（`office`）

声明位置：`smart_assistant/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `office_read` | 读取附件内容 | 只读 | 登录即可 | 仅本次附件 | — | 幂等 | 读取用户上传 Office 附件的指定内容切片（当附件较长、需要更多内容时调用） |
| `spreadsheet_qa` | 表格问答 | 只读 | 登录即可 | 仅本次附件 | — | 幂等 | 对用户上传的 Excel 表格做数据统计（总行数/列名）与自然语言问答 |
| `office_generate` | 生成 Word 文档 | 写入 | 登录即可 | 仅本人 | 本人确认 | — | 根据用户描述的结构和变量生成 .docx 文档下载 |

### 通知（`notifications`）

声明位置：`notifications/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `notification_query` | 查询我的通知 | 只读 | 登录即可 | 仅本人 | — | 幂等 | 查询我的站内通知（未读数、最近通知，可按类型、关键词筛选） |
| `agent_notify` | 发送站内通知 | 写入 | 登录即可 | 按 scope 限定收件人 | 本人确认 | — | 向一个或多个用户发送站内通知(写操作,需要用户确认)。 |

### 内网外链（`external_links`）

声明位置：`external_integration/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `external_link_query` | 查询内网外链 | 只读 | 登录即可 | 三级 scope | — | 幂等 | 查询公司内网外链(VPN/Jira 等,external_integration.ExternalLink) |

### 文档库（`document_library`）

声明位置：`paperless_proxy/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `document_library_query` | 检索文档库 | 只读 | 登录即可 | 同模块接口 | — | 幂等 | 按标题检索文档库（Paperless）中我能看到的文档，返回类型、上传人和同步状态 |

### 跨模块检索（`search`）

声明位置：`search_federation/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `global_search` | 跨模块检索 | 只读 | 登录即可 | 委托其他工具 | — | 幂等 | 跨模块检索项目、备忘录、人员、合规问题、公文模板（按当前用户权限范围） |

### 联培生（`joint_students`）

声明位置：`joint_students/ai_tools.py`

| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `joint_student_query` | 查询联培生 | 只读 | 登录即可 | 同模块接口 | — | 幂等 | 查询联培生（姓名、学号、导师、在读状态、最近一次月报状态），按联培生模块的可见范围返回 |

## 页面上下文

用户在下列详情页打开 AI 抽屉时，前端只传当前路径；后端按路由解析记录 ID，再用该用户的权限重新读取记录，作为参考资料注入对话（看不到的记录不注入）。

| record_type | 名称 | 工具集 | 路由 | 读取函数 |
| --- | --- | --- | --- | --- |
| `personnel` | 人员 | `personnel` | `^/control-panel/personnel/(?P<record_id>\d+)(/edit)?/?$` | `personnel.ai_tools.load_personnel_context` |
| `sensor` | 传感器 | `sensors` | `^/control-panel/sensors/(?P<record_id>\d+)(/calibration/[a-z]+)?/?$` | `sensor_management.ai_tools.load_sensor_context` |
| `communication_post` | 交流帖子 | `communication` | `^/communication/(?P<record_id>\d+)/?$` | `communication.ai_tools.load_post_context` |
| `joint_student` | 联培生 | `joint_students` | `^/joint-students/admin/students/(?P<record_id>\d+)(/edit)?/?$` | `joint_students.ai_tools.load_joint_student_context` |

## 快捷问题

按路由匹配（`re.search`），只有用户能调用所属工具集中至少一个工具时才展示，每页最多 6 条。`^/$` 为 Dashboard。

| 工具集 | 按钮 | 发送的问题 | 路由 |
| --- | --- | --- | --- |
| `personnel` | 我的信息 | 查一下我的人员信息 | `^/control-panel/personnel`、`^/me/personnel` |
| `schedule` | 今天安排 | 我今天有什么安排？ | `^/$` |
| `schedule` | 明天谁值班 | 明天谁值班？ | `^/schedule`、`^/shift-schedule`、`^/trial-schedule`、`^/events`、`^/control-panel/schedule` |
| `schedule` | 本周节假日 | 这周有哪些节假日或调休？ | `^/schedule`、`^/shift-schedule`、`^/trial-schedule`、`^/events`、`^/control-panel/schedule` |
| `schedule` | 换班申请 | 我收到的换班申请有哪些？ | `^/schedule`、`^/shift-schedule`、`^/trial-schedule`、`^/events`、`^/control-panel/schedule` |
| `memos` | 我的备忘录 | 我最近的备忘录有哪些？ | `^/$`、`^/memos` |
| `memos` | 即将提醒 | 接下来三天有哪些备忘录提醒？ | `^/memos` |
| `projects` | 项目进度 | 当前各项目的进度如何？ | `^/control-panel/projects` |
| `projects` | 延期项目 | 有哪些项目进度落后或已延期？ | `^/control-panel/projects` |
| `compliance` | 合规待办 | 我有哪些待处理的合规问题？ | `^/$`、`^/control-panel/compliance` |
| `compliance` | 逾期整改 | 有哪些已经逾期的整改项？ | `^/control-panel/compliance` |
| `meeting_rooms` | 空闲会议室 | 今天下午有哪些空闲的会议室？ | `^/meeting-rooms`、`^/control-panel/meeting-rooms` |
| `meeting_rooms` | 我的预约 | 我这周预约了哪些会议室？ | `^/$`、`^/meeting-rooms` |
| `sensors` | 待校准 | 哪些传感器快到校准日期了？ | `^/control-panel/sensors` |
| `sensors` | 校准记录 | 这个传感器的校准记录是什么？ | `^/control-panel/sensors/\d+` |
| `communication` | 最新公告 | 最近有哪些公告？ | `^/$`、`^/announcements`、`^/communication$` |
| `communication` | 总结讨论 | 总结一下这个帖子的讨论和主要观点 | `^/communication/\d+` |
| `communication` | 我的帖子 | 我发的帖子有人回复吗？ | `^/communication` |
| `notifications` | 未读通知 | 我有几条未读通知？都是什么？ | `^/$`、`^/notifications` |
| `document_library` | 最近文档 | 文档库里最近上传了哪些文档？ | `^/documents-library` |
| `joint_students` | 联培生概况 | 列出我可以查看的联培生及最近月报状态 | `^/joint-students` |
| `joint_students` | 月报情况 | 这个联培生最近的月报情况怎么样？ | `^/joint-students/admin/students/\d+` |

## 字段说明

- **类型**：由工具类的 `risk_level` 推导；对外导出为 MCP ToolAnnotations（`readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint`）。
- **权限**：`登录即可` 表示已登录用户都能调用，实际能看到的数据由"数据范围"限制；填写权限码时，还需 `user.has_perm()` 通过（superuser 天然通过）。
- **数据范围**：
  - 三级 scope（`scope`）：按 SELF / DEPARTMENT / GLOBAL 三级 scope 过滤（`smart_assistant/scope.py`）
  - 仅本人（`owner`）：只返回当前用户本人的数据，任何 scope 都不扩大
  - 同模块接口（`module`）：与该模块 HTTP 接口共用同一段可见性逻辑
  - 委托其他工具（`delegated`）：不直接查询模型，调用其他工具的 `scoped_queryset()`
  - 仅本次附件（`attachment`）：只读取本次请求携带的附件
  - 知识库（`knowledge`）：检索知识库或公共资料，不涉及用户私有数据
  - 按 scope 限定收件人（`recipient`）：向他人写入（如发通知）时，按发起人的 scope 限定可选收件人
- **确认**：写入和删除类工具必须经发起人本人确认后才执行（confirm-replay）。
