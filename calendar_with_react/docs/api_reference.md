# API 参考手册

## 认证 API

### 用户注册
- **端点**: `POST /api/auth/register/`
- **权限**: 允许匿名访问
- **请求体**:
  ```json
  {
    "username": "string",
    "password": "string",
    "email": "string"
  }
  ```
- **成功响应**:
  ```json
  {
    "success": true,
    "message": "注册成功，请登录",
    "username": "string"
  }
  ```

### 用户登录
- **端点**: `POST /api/auth/login/`
- **权限**: 允许匿名访问
- **请求体**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **成功响应**:
  ```json
  {
    "success": true,
    "access": "JWT令牌",
    "refresh": "刷新令牌",
    "user": {
      "id": 1,
      "username": "string"
    }
  }
  ```

## 用户管理 API

### 获取当前用户信息
- **端点**: `GET /api/users/me/`
- **权限**: 需要认证
- **响应**:
  ```json
  {
    "id": 1,
    "username": "string",
    "email": "string@example.com"
  }
  ```

## 试验管理 API

### 获取试验列表
- **端点**: `GET /api/events/trials/`
- **权限**: 需要认证
- **过滤参数**:
  - `status`: 试验状态
  - `equipments`: 关联设备ID
  - `start_date`: 开始日期
  - `end_date`: 结束日期
- **排序参数**:
  - `start_date`: 按开始日期排序
  - `time_slots__start_time`: 按时间段排序

### 创建试验
- **端点**: `POST /api/events/trials/`
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "name": "试验名称",
    "description": "试验描述",
    "equipment_ids": [1, 2],
    "responsible_person_ids": [3, 4],
    "time_periods": [
      {
        "start_time": "2023-01-01T09:00:00",
        "end_time": "2023-01-01T17:00:00"
      }
    ]
  }
  ```

## 时间段管理 API

### 获取时间段
- **端点**: `GET /api/events/time-slots/`
- **权限**: 需要认证
- **查询参数**:
  - `trial`: 关联试验ID (可选)
  - `start_time__gte`: 开始时间大于等于 (ISO8601格式)
  - `end_time__lte`: 结束时间小于等于 (ISO8601格式)
- **响应**:
  ```json
  [
    {
      "id": 1,
      "start_time": "2023-01-01T09:00:00Z",
      "end_time": "2023-01-01T10:00:00Z",
      "description": "时间段描述",
      "trial": 1,
      "trial_title": "试验名称"
    }
  ]
  ```

### 创建时间段
- **端点**: `POST /api/events/time-slots/`
- **权限**: 需要认证
- **请求头**:
  - `X-Request-Source`: calendar-view (可选)
- **请求体**:
  ```json
  {
    "trial": 1,
    "start_time": "2023-01-01T09:00:00Z",
    "end_time": "2023-01-01T10:00:00Z",
    "description": "时间段描述"
  }
  ```
- **验证规则**:
  - 时间段长度至少30分钟
  - 不能与现有时间段重叠
  - 必须关联有效试验
- **成功响应**:
  ```json
  {
    "id": 1,
    "start_time": "2023-01-01T09:00:00Z",
    "end_time": "2023-01-01T10:00:00Z",
    "description": "时间段描述",
    "trial": 1
  }
  ```

### 更新时间段
- **端点**: `PATCH /api/events/time-slots/{id}/`
- **权限**: 需要认证
- **请求头**:
  - `X-Request-Source`: calendar-view (可选)
- **请求体**:
  ```json
  {
    "start_time": "2023-01-01T10:00:00Z",
    "end_time": "2023-01-01T11:00:00Z",
    "description": "更新后的描述"
  }
  ```
- **验证规则**:
  - 如果更新时间，需保持end_time > start_time
  - 更新后不能与其他时间段重叠
- **成功响应**:
  ```json
  {
    "id": 1,
    "start_time": "2023-01-01T10:00:00Z",
    "end_time": "2023-01-01T11:00:00Z",
    "description": "更新后的描述",
    "trial": 1
  }
  ```

### 删除时间段
- **端点**: `DELETE /api/events/time-slots/{id}/`
- **权限**: 需要认证
- **请求头**:
  - `X-Request-Source`: calendar-view (可选)
- **成功响应**: HTTP 204 No Content
- **错误响应**:
  - 404: 时间段不存在
  - 403: 无删除权限

### 批量创建时间段
- **端点**: `POST /api/events/time-slots/bulk/`
- **权限**: 需要认证
- **请求头**:
  - `X-Request-Source`: calendar-view (可选)
- **请求体**:
  ```json
  {
    "trial_id": 1,
    "time_slots": [
      {
        "start_time": "2023-01-01T09:00:00Z",
        "end_time": "2023-01-01T10:00:00Z",
        "description": "时间段1描述"
      },
      {
        "start_time": "2023-01-01T11:00:00Z",
        "end_time": "2023-01-01T12:00:00Z",
        "description": "时间段2描述"
      }
    ]
  }
  ```
- **验证规则**:
  - 每个时间段长度至少30分钟
  - 时间段之间不能重叠
  - 所有时间段必须关联同一试验
  - 最多允许批量创建50个时间段
- **成功响应**:
  ```json
  [
    {
      "id": 1,
      "start_time": "2023-01-01T09:00:00Z",
      "end_time": "2023-01-01T10:00:00Z",
      "description": "时间段1描述",
      "trial": 1
    },
    {
      "id": 2,
      "start_time": "2023-01-01T11:00:00Z",
      "end_time": "2023-01-01T12:00:00Z",
      "description": "时间段2描述",
      "trial": 1
    }
  ]
  ```
- **错误响应**:
  - 400: 验证失败(包含错误详情)
  - 403: 无创建权限
  - 404: 关联试验不存在

## 文档管理 API

### 上传文档模板
- **端点**: `POST /api/documents/templates/upload/`
- **权限**: 需要认证
- **请求格式**: multipart/form-data
- **参数**:
  - `template`: 文件字段

### 生成文档
- **端点**: `POST /api/documents/{template_id}/generate/`
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "parameters": {
      "title": "文档标题"
    }
  }
