# Dify 应用创建失败问题修复计划

## 问题描述
在 Dify 应用管理页面添加新的 Dify 应用时，前端提示 "Failed to save Dify application."，控制台显示 `POST http://localhost:8000/api/dify-apps/ 400 (Bad Request)` 错误。

## 问题分析
1.  **前端数据发送**: 前端组件 [`omni_desk_frontend/src/components/DifyApps/DifyAppManagementPage.jsx`](omni_desk_frontend/src/components/DifyApps/DifyAppManagementPage.jsx) 在创建新应用时，通过 `handleSubmit` 函数向 `/api/dify-apps/` 发送 `POST` 请求，请求体为 `formData`。该 `formData` 包含 `name`, `description`, `embed_url` 字段。
2.  **后端 API 期望**: 后端 `omni_desk_backend/dify_apps/` 模块的 `DifyAppViewSet` (位于 [`omni_desk_backend/dify_apps/views.py`](omni_desk_backend/dify_apps/views.py)) 使用 `DifyAppSerializer` (位于 [`omni_desk_backend/dify_apps/serializers.py`](omni_desk_backend/dify_apps/serializers.py)) 处理数据。`DifyAppSerializer` 映射到 `DifyApp` 模型 (位于 [`omni_desk_backend/dify_apps/models.py`](omni_desk_backend/dify_apps/models.py))。
3.  **模型字段**: `DifyApp` 模型定义了以下字段：
    *   `name`: `CharField(max_length=255, unique=True, verbose_name="应用名称")` - 必填，唯一。
    *   `description`: `TextField(blank=True, null=True, verbose_name="应用描述")` - 可选。
    *   `embed_url`: `URLField(max_length=500, verbose_name="嵌入式 URL")` - 必填，URL 格式。
    *   `is_active`: `BooleanField(default=True, verbose_name="是否激活")` - **可选，默认为 `True`**。
4.  **不一致之处**: 前端 `formData` 缺少 `is_active` 字段。尽管 `is_active` 在模型中定义了默认值 `True`，但如果 `DifyAppSerializer` 没有明确将 `is_active` 标记为非必需，序列化器可能会因为缺少该字段而引发验证错误，导致 `400 Bad Request`。

## 解决方案

最推荐的解决方案是修改后端 `DifyAppSerializer`，明确将 `is_active` 字段设置为非必需。这样，即使前端不发送 `is_active` 字段，后端也会使用模型中定义的默认值 `True`。

### 具体修改步骤

**文件**: [`omni_desk_backend/dify_apps/serializers.py`](omni_desk_backend/dify_apps/serializers.py)

**修改内容**:
在 `DifyAppSerializer` 的 `Meta` 类中，添加或修改 `extra_kwargs` 来将 `is_active` 字段设置为 `required=False`。

```python
# omni_desk_backend/dify_apps/serializers.py

from rest_framework import serializers
from .models import DifyApp

class DifyAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = DifyApp
        fields = ['id', 'name', 'description', 'embed_url', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        # 添加 extra_kwargs 来设置 is_active 为非必需
        extra_kwargs = {
            'is_active': {'required': False}
        }

```

### 实施计划

1.  **切换模式**: 请求用户切换到 `code` 模式。
2.  **执行修改**: 在 `code` 模式下，使用 `apply_diff` 工具修改 [`omni_desk_backend/dify_apps/serializers.py`](omni_desk_backend/dify_apps/serializers.py)。
3.  **验证**: 指导用户重新测试 Dify 应用的创建功能，确认 `400 Bad Request` 错误是否已解决。
