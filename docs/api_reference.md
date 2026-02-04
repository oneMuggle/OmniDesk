# OmniDesk API 参考

本文档为 OmniDesk 系统中所有可用的 API 端点提供了全面的参考。

---

### 1. 认证与用户 (`/api/auth/`, `/api/users/`)

-   **`POST /api/auth/registration/`**
    *   **视图:** `UserRegistrationView`
    *   **方法:** `POST`
    *   **描述:** 用户注册。允许任何人创建新帐户。
-   **`POST /api/auth/login/`**
    *   **视图:** `UserLoginView`
    *   **方法:** `POST`
    *   **描述:** 用户登录。成功后返回JWT访问和刷新令牌以及用户权限。
-   **`POST /api/auth/token/refresh/`**
    *   **视图:** `TokenRefreshView` (来自 `rest_framework_simplejwt`)
    *   **方法:** `POST`
    *   **描述:** 使用刷新令牌获取新的访问令牌。
-   **`GET /api/users/me/`**
    *   **视图:** `CurrentUserView`
    *   **方法:** `GET`
    *   **描述:** 获取当前已认证用户的详细信息。
-   **`GET, PUT, PATCH /api/users/me/profile/`**
    *   **视图:** `UserProfileUpdateView`
    *   **方法:** `GET`, `PUT`, `PATCH`
    *   **描述:** 获取并更新当前已认证用户的个人资料。
-   **`PUT /api/users/me/change-password/`**
    *   **视图:** `ChangePasswordView`
    *   **方法:** `PUT`
    *   **描述:** 更改当前已认证用户的密码。
-   **`GET, POST /api/users/`**
    *   **视图:** `UserPersonnelViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** (管理员/经理) 列出或创建用户与人事信息之间的关联。
-   **`GET, PATCH /api/users/{id}/`**
    *   **视图:** `UserPersonnelViewSet`
    *   **方法:** `GET`, `PATCH`
    *   **描述:** (管理员/经理) 检索或更新特定用户的人事信息关联。
-   **`GET /api/users/control-panel/`**
    *   **视图:** `UserAdminListView`
    *   **方法:** `GET`
    *   **描述:** (管理员) 列出所有系统用户以进行管理。
-   **`GET, PUT, PATCH /api/users/control-panel/{id}/`**
    *   **视图:** `UserAdminDetailView`
    *   **方法:** `GET`, `PUT`, `PATCH`
    *   **描述:** (管理员) 检索或更新特定用户的管理信息。

---

### 2. 用户交流 (`/api/communication/`)

-   **`GET, POST /api/communication/posts/`**
    *   **视图:** `PostViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取帖子列表或创建新帖子。
-   **`GET, PUT, PATCH, DELETE /api/communication/posts/{id}/`**
    *   **视图:** `PostViewSet`
    *   **方法:** `GET`, `PUT`, `PATCH`, `DELETE`
    *   **描述:** 检索、更新或删除单个帖子。
-   **`GET, POST /api/communication/posts/{post_pk}/comments/`**
    *   **视图:** `CommentViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取帖子的评论列表或向帖子添加新评论。
-   **`GET, PUT, PATCH, DELETE /api/communication/posts/{post_pk}/comments/{id}/`**
    *   **视图:** `CommentViewSet`
    *   **方法:** `GET`, `PUT`, `PATCH`, `DELETE`
    *   **描述:** 检索、更新或删除单条评论。

---

### 3. 合规管理 (`/api/compliance/`)

-   **`GET, POST /api/compliance/`**
    *   **视图:** `ComplianceIssueViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取合规性问题列表或创建新问题。
-   **`GET, PUT, PATCH, DELETE /api/compliance/{id}/`**
    *   **视图:** `ComplianceIssueViewSet`
    *   **方法:** `GET`, `PUT`, `PATCH`, `DELETE`
    *   **描述:** 检索、更新或删除单个合规性问题。
-   **`GET /api/compliance/unread_count/`**
    *   **视图:** `ComplianceIssueViewSet`
    *   **方法:** `GET`
    *   **描述:** 获取当前用户未读（待处理/进行中）的合规性问题数量。

---

### 4. 系统配置 (`/api/config/`, `/api/ollama/`)

-   **`GET /api/config/`**
    *   **视图:** `get_ollama_config`
    *   **方法:** `GET`
    *   **描述:** 获取 Ollama 的基础端点 URL。
-   **`GET, POST /api/config/page-visibility/`**
    *   **视图:** `PageVisibilityViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取或设置不同用户组的页面可见性。
-   **`GET, POST /api/config/ollama-configs/`**
    *   **视图:** `OllamaConfigViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取 Ollama 配置列表或创建新配置。
-   **`GET, PUT, PATCH, DELETE /api/config/ollama-configs/{id}/`**
    *   **视图:** `OllamaConfigViewSet`
    *   **方法:** `GET`, `PUT`, `PATCH`, `DELETE`
    *   **描述:** 检索、更新或删除单个 Ollama 配置。
-   **`GET /api/ollama/configs/`**
    *   **视图:** `ollama_configs_view`
    *   **方法:** `GET`
    *   **描述:** 一个简单的健康检查端点，返回 `{'status': 'ok'}`。

---

### 5. Dify应用 (`/api/dify-apps/`)

-   **`GET, POST /api/dify-apps/`**
    *   **视图:** `DifyAppViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取 Dify 应用列表或创建新应用。
-   **`GET, PUT, PATCH, DELETE /api/dify-apps/{id}/`**
    *   **视图:** `DifyAppViewSet`
    *   **方法:** `GET`, `PUT`, `PATCH`, `DELETE`
    *   **描述:** 检索、更新或删除单个 Dify 应用。

---

### 6. 文档管理 (`/api/documents/`)

-   **`GET, POST /api/documents/templates/`**
    *   **视图:** `DocumentTemplateViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取或创建文档模板。
-   **`POST /api/documents/templates/upload/`**
    *   **视图:** `DocumentTemplateViewSet`
    *   **方法:** `POST`
    *   **描述:** 上传文档模板文件。
-   **`POST /api/documents/templates/{id}/analyze/`**
    *   **视图:** `DocumentTemplateViewSet`
    *   **方法:** `POST`
    *   **描述:** 分析文档模板是否存在合规性问题。
-   **`GET, POST /api/documents/books/`**
    *   **视图:** `BookViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取或创建书籍。
-   **`GET /api/documents/books/{id}/export_markdown/`**
    *   **视图:** `BookViewSet`
    *   **方法:** `GET`
    *   **描述:** 将书籍导出为 Markdown 文件。
-   **`POST /api/documents/import_book/`**
    *   **视图:** `BookImportView`
    *   **方法:** `POST`
    *   **描述:** 从 Markdown 或 Zip 文件导入书籍。
-   **`GET /api/documents/chapters/{id}/`**
    *   **视图:** `ChapterViewSet`
    *   **方法:** `GET`
    *   **描述:** 获取章节详细信息。
-   **`PUT /api/documents/chapters/{id}/update_content/`**
    *   **视图:** `ChapterViewSet`
    *   **方法:** `PUT`
    *   **描述:** 更新章节的 Markdown 内容。
-   ... 以及 `DocumentTemplate`, `GeneratedDocument`, `Book`, `Chapter`, 和 `EBook` 的其他标准CRUD端点。

---

### 7. 事件与排班 (`/api/events/`)

-   **`GET, POST /api/events/schedules/`**
    *   **视图:** `ScheduleViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 获取或创建排班记录。
-   **`POST /api/events/schedules/generate-schedules/`**
    *   **视图:** `ScheduleViewSet`
    *   **方法:** `POST`
    *   **描述:** 自动生成排班表。
-   **`POST /api/events/schedules/swap-dates/`**
    *   **视图:** `ScheduleViewSet`
    *   **方法:** `POST`
    *   **描述:** 交换两个日期的排班人员。
-   **`POST /api/events/schedules/swap-weekly-leaders/`**
    *   **视图:** `ScheduleViewSet`
    *   **方法:** `POST`
    *   **描述:** 交换两周的值班领导。
-   **`GET, POST /api/events/personnel-sequences/`**
    *   **视图:** `PersonnelSequenceViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理人员排班顺序。
-   **`GET, POST /api/events/leader-sequences/`**
    *   **视图:** `LeaderSequenceViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理领导排班顺序。
-   ... 以及 `Trial`, `TimeSlot`, `Holiday`, `Position`, `Equipment`, 和 `Announcement` 的其他标准CRUD端点。

---

### 8. 会议室预定 (`/api/meeting-rooms/`)

-   **`GET, POST /api/meeting-rooms/meeting-rooms/`**
    *   **视图:** `MeetingRoomViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理会议室。
-   **`GET, POST /api/meeting-rooms/meeting-room-bookings/`**
    *   **视图:** `MeetingRoomBookingViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理会议室预订。
-   **`GET /api/meeting-rooms/meeting-room-bookings/this-week/`**
    *   **视图:** `MeetingRoomBookingViewSet`
    *   **方法:** `GET`
    *   **描述:** 获取本周的会议室预订情况。
-   **`GET /api/meeting-rooms/meeting-room-stats/`**
    *   **视图:** `MeetingRoomStatsAPIView`
    *   **方法:** `GET`
    *   **描述:** 获取会议室使用情况的统计数据。
-   ... 以及 `MeetingRoomMaintenance` 的其他标准CRUD端点。

---

### 9. 备忘录 (`/api/memos/`)

-   **`GET, POST /api/memos/`**
    *   **视图:** `MemoViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 为当前用户获取或创建备忘录。
-   **`GET, PUT, PATCH, DELETE /api/memos/{id}/`**
    *   **视图:** `MemoViewSet`
    *   **方法:** `GET`, `PUT`, `PATCH`, `DELETE`
    *   **描述:** 检索、更新或删除单个备忘录。

---

### 10. 新闻中心 (`/api/`)

-   **`GET, POST /api/news-types/`**
    *   **视图:** `NewsTypeViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理新闻类型。
-   **`GET, POST /api/news-articles/`**
    *   **视图:** `NewsArticleViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理新闻文章。
-   **`GET /api/news-stats/`**
    *   **视图:** `NewsStatsView`
    *   **方法:** `GET`
    *   **描述:** 获取新闻发布统计数据。

---

### 11. 办公助手 (`/api/office_assistant/`)

-   **`POST /api/office_assistant/process/`**
    *   **视图:** `OfficeAssistantProcessView`
    *   **方法:** `POST`
    *   **描述:** 处理输入文本（校对、翻译、润色）。
-   **`POST /api/office_assistant/process-document/`**
    *   **视图:** `ProcessDocumentView`
    *   **方法:** `POST`
    *   **描述:** 处理上传的文档文件。

---

### 12. 权限管理 (`/api/permissions/`)

-   **`GET, POST /api/permissions/groups/`**
    *   **视图:** `GroupViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理用户组。
-   **`GET, PUT /api/permissions/groups/{group_id}/permissions/`**
    *   **视图:** `GroupPermissionView`
    *   **方法:** `GET`, `PUT`
    *   **描述:** 获取或设置指定用户组的权限。
-   **`GET /api/permissions/users/me/permissions/`**
    *   **视图:** `UserPermissionView`
    *   **方法:** `GET`
    *   **描述:** 获取当前用户的页面路由权限。
-   **`GET /api/permissions/permissions/grouped/`**
    *   **视图:** `GroupedPermissionsView`
    *   **方法:** `GET`
    *   **描述:** 获取所有可用权限，按模型分组。

---

### 13. 人事管理 (`/api/personnel/`)

-   **`GET, POST /api/personnel/personnel/`**
    *   **视图:** `PersonnelViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理基本人事信息。
-   ... 以及 `Contract`, `Education`, `WorkExperience`, `ProfessionalQualification`, `FamilyMember`, 和 `Position` 的其他标准CRUD端点。

---

### 14. 项目管理 (`/api/projects/`)

-   **`GET, POST /api/projects/`**
    *   **视图:** `ProjectViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理项目信息。

---

### 15. RAGflow服务 (`/api/ragflow-service/`)

-   **`GET, POST /api/ragflow-service/configs/`**
    *   **视图:** `RagflowConfigViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理 RAGflow 服务配置。
-   **`POST /api/ragflow-service/configs/{id}/query/`**
    *   **视图:** `RagflowConfigViewSet`
    *   **方法:** `POST`
    *   **描述:** 使用指定的配置向 RAGflow 服务发送查询。

---

### 16. 传感器管理 (`/api/sensor-management/`)

-   **`GET, POST /api/sensor-management/sensors/`**
    *   **视图:** `SensorViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理传感器信息。
-   **`GET, POST /api/sensor-management/sensor-movements/`**
    *   **视图:** `SensorMovementViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** 管理传感器签入/签出记录。
-   **`POST /api/sensor-management/calibration-reminders/{id}/mark-as-sent/`**
    *   **视图:** `CalibrationReminderViewSet`
    *   **方法:** `POST`
    *   **描述:** 将校准提醒标记为已发送。
-   ... 以及 `SensorCategory`, `StorageLocation`, `SensorCalibration`, 和 `CalibrationReminder` 的其他标准CRUD端点。

---

### 17. 传感器（旧版） (`/api/sensors/`)

-   **`GET, POST /api/sensors/sensors/`**
    *   **视图:** `SensorViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** (可能已弃用) 管理传感器。功能与 `sensor_management` 应用重叠。
-   **`GET, POST /api/sensors/calibration-records/`**
    *   **视图:** `CalibrationRecordViewSet`
    *   **方法:** `GET`, `POST`
    *   **描述:** (可能已弃用) 管理校准记录。功能与 `sensor_management` 应用重叠。

---

### **特别说明**

`sensors` 应用程序似乎是 `sensor_management` 应用程序的旧版本或功能重叠版本。建议进行审查，以确定是否可以合并或删除以避免冗余。