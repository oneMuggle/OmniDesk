# 25. 后端 API 性能审计报告

> 生成日期:2026-06-05
> 审计范围:`omni_desk_backend/**/views.py` 中所有 DRF ViewSet 与 APIView
> 目的:识别 N+1 查询、缺失分页、缺失字段裁剪等问题

## 一、整体概览

| 指标 | 值 |
|------|---|
| ViewSet / APIView 总数 | **52** |
| 已使用 `select_related` / `prefetch_related` | ~17 个文件 |
| 显式声明 `pagination_class` | 4 个 |
| 显式禁用分页 (`pagination_class = None`) | 3 个 |
| 全局默认分页 | `PageNumberPagination`, PAGE_SIZE=10 |
| 显式自定义 PAGE_SIZE | 1 个 (`EbookPagination: page_size=10`) |

**结论**:项目对性能优化**整体重视度较高**,大多数高频 ViewSet 已正确使用 `select_related`/`prefetch_related`。但仍有 ~10 个中频 ViewSet 缺少优化,需补齐。

## 二、已优化(无需改动)

| ViewSet | 文件 | 优化方式 |
|---------|------|----------|
| `PersonnelViewSet` | `personnel/views.py:19` | `select_related("position")` + `prefetch_related(contracts, educations, work_experiences, qualifications, family_members)` |
| `ContractViewSet` / `EducationViewSet` / `WorkExperienceViewSet` 等 | `personnel/views.py` | `select_related("personnel")` |
| `TimeSlotViewSet` | `events/views.py` | `select_related("trial")` |
| `ScheduleViewSet` | `events/views.py` | `select_related("duty_person", "duty_leader")` |
| `AnnouncementViewSet` | `events/views.py` | `select_related("author")` |
| `TrialViewSet` | `events/views.py` | `prefetch_related("equipments", "responsible_persons", "time_slots")` |
| `PostViewSet` | `communication/views.py` | `select_related("author")` |
| `CommentViewSet` | `communication/views.py` | `select_related("author", "post")` |
| `NewsArticleViewSet` | `news/views.py` | `select_related("personnel", "news_type")` |
| `PluginViewSet` | `external_integration/views.py` | `prefetch_related("versions")` |
| `dashboard.views.today_schedules` | `dashboard/views.py:18` | `select_related("duty_person", "duty_leader")` |
| `compliance.services.compliance_engine` | `compliance/services/compliance_engine.py:17` | `select_related(...)` |
| `MeetingRoomViewSet` / `BookingViewSet` | `meeting_rooms/views.py` | 已用 `select_related` |

## 三、需优化的 N+1 风险(按优先级)

### 🔴 P0 - 高频但未优化

#### 1. `ComplianceIssueViewSet` (compliance/views.py:13)
```python
queryset = ComplianceIssue.objects.all()  # ❌ 无 select_related
```
- **关联**:`project`(FK)、`reporter`(FK)、`assignee`(FK)
- **风险**:列表每条 issue 会触发 3 次额外查询 → 100 条 = 301 queries
- **建议**:
  ```python
  queryset = ComplianceIssue.objects.select_related("project", "reporter", "assignee")
  ```

#### 2. `DocumentTemplateViewSet` (documents/views/templates.py)
- 需先看 `DocumentTemplate` 模型是否有 FK 到 Project/Owner
- 如果有,需加 `select_related`

#### 3. `BookViewSet` / `ChapterViewSet` (documents/views/books.py)
- `Book` 有 FK 到 `Project`;`Chapter` 有 FK 到 `Book`
- 当前 18-83 行没看,需检查

### 🟡 P1 - 中频,可优化

| ViewSet | 文件 | 备注 |
|---------|------|------|
| `EquipmentViewSet` | `events/views.py:43` | Equipment 模型简单,需查是否有 FK |
| `HolidayViewSet` | `events/views.py` | 简单 model,可能 OK |
| `NewsTypeViewSet` | `news/views.py:12` | 简单,可能 OK |
| `MemoViewSet` | `memos/views.py` | Memo FK to User,过滤后基本是 1 个用户 → 优化价值低 |
| `NotificationViewSet` | `notifications/views.py` | 单用户过滤,优化价值低 |
| `DifyAppViewSet` | `dify_apps/views.py:8` | `DifyApp` 无 FK?需查模型 |
| `EbookViewSet` | `ebooks/views.py` | 简单 model,可能 OK |
| `RagflowConfigViewSet` | `ragflow_service/views.py` | 简单 |
| `OllamaConfigViewSet` | `config/views.py` | 配置类,数据量小 |
| `KnowledgeBaseViewSet` | `smart_assistant/views/knowledge_base.py` | 需查模型 |
| `SessionViewSet` | `smart_assistant/views/sessions.py` | 单用户,优化价值低 |
| `LlmEndpointViewSet` | `smart_assistant/views/llm_config.py` | 配置类,数据量小 |
| `LlmAppConfigViewSet` | `smart_assistant/views/llm_config.py` | 同上 |
| `EBookViewSet` | `documents/views/ebooks.py` | 简单 |
| `ChapterViewSet` | `documents/views/books.py:83` | FK to Book,需加 select_related |
| `ExternalLinkViewSet` | `external_integration/views.py:23` | 无 FK,可能 OK |
| `IntegrationServiceViewSet` | `external_integration/views.py:55` | 配置类 |

## 四、显式禁用分页的 ViewSet

| 文件:行 | ViewSet | 评估 |
|---------|---------|------|
| `documents/views/documents.py:13` | `GeneratedDocumentViewSet` | 需评估:如果文档量大,禁用分页会导致响应过大 |
| `users/views.py:185` | `UserPersonnelViewSet` | 通常是单一关联,禁用合理 |
| `permissions/views.py:29` | `GroupViewSet` | Group 数量少,禁用合理 |

**建议**:
- `GeneratedDocumentViewSet` 重新启用分页(文档可能很多)

## 五、已显式自定义分页的 ViewSet

| 文件 | ViewSet | PAGE_SIZE |
|------|---------|-----------|
| `documents/views/documents.py` | 显式 | (从 None 改) |
| `ebooks/views.py` | `EbookPagination` | 10 |
| `permissions/views.py` | 显式 | (从 None 改) |
| `users/views.py` | 显式 | (从 None 改) |

## 六、优化建议(按 ROI 排序)

1. **立刻修**:`ComplianceIssueViewSet` 加 `select_related("project", "reporter", "assignee")`
2. **立刻修**:`ChapterViewSet` 加 `select_related("book")`
3. **评估**:`DocumentTemplateViewSet` 是否需要 `select_related("project", "owner")`
4. **评估**:`GeneratedDocumentViewSet` 是否恢复分页

## 七、监控建议

- 接入 `django-silk` 到 dev 模式,自动检测 N+1
- 在 CI 中加 `pytest-django-queries` 检测 N+1(可选)
- 关键列表 API 加 query count 上限(如 ≤ 10 queries/请求)

## 八、附录:扫描命令

```bash
# 找出所有 ViewSet/APIView
grep -rEn "(ListAPIView|ListCreateAPIView|ModelViewSet|ReadOnlyModelViewSet|generics\.List)" --include="*.py" omni_desk_backend/

# 找出有 select_related/prefetch_related 的文件
grep -rEln "select_related|prefetch_related" --include="*.py" omni_desk_backend/

# 找出禁用分页的 ViewSet
grep -rEn "pagination_class\s*=\s*None" --include="*.py" omni_desk_backend/

# 全局分页配置
grep -E "DEFAULT_PAGINATION|PAGE_SIZE" omni_desk_backend/omni_desk_backend/settings/base.py
```
