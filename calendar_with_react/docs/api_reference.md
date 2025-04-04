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
