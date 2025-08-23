# Ollama 多配置功能开发计划

## 1. 目标

在系统中实现对多个 Ollama 配置的支持，允许用户通过别名保存和管理不同的 Ollama API 和模型配置，并在智能问答页面动态切换。

## 2. 后端开发 (Django)

### 2.1. 数据模型 (`config/models.py`)

创建一个新的数据模型 `OllamaConfig` 用于存储 Ollama 的配置信息。

```python
from django.db import models
from django.utils.translation import gettext_lazy as _

class OllamaConfig(models.Model):
    alias = models.CharField(_('配置别名'), max_length=100, unique=True)
    api_endpoint = models.URLField(_('API 地址'))
    model = models.CharField(_('模型名称'), max_length=100)
    temperature = models.FloatField(_('Temperature'), default=0.8, null=True, blank=True)
    top_p = models.FloatField(_('Top P'), default=0.9, null=True, blank=True)
    is_default = models.BooleanField(_('是否为默认'), default=False)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('Ollama 配置')
        verbose_name_plural = _('Ollama 配置')

    def __str__(self):
        return self.alias

    def save(self, *args, **kwargs):
        if self.is_default:
            # 将其他所有配置的 is_default 设置为 False
            OllamaConfig.objects.filter(is_default=True).update(is_default=False)
        super(OllamaConfig, self).save(*args, **kwargs)
```

### 2.2. 数据库迁移

```bash
python manage.py makemigrations config
python manage.py migrate
```

### 2.3. Serializer (`config/serializers.py`)

为 `OllamaConfig` 模型创建一个 Serializer。

```python
from rest_framework import serializers
from .models import OllamaConfig

class OllamaConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = OllamaConfig
        fields = '__all__'
```

### 2.4. View (`config/views.py`)

创建一个 `ViewSet` 来处理 `OllamaConfig` 的增删改查操作。

```python
from rest_framework import viewsets
from .models import OllamaConfig
from .serializers import OllamaConfigSerializer

class OllamaConfigViewSet(viewsets.ModelViewSet):
    queryset = OllamaConfig.objects.all()
    serializer_class = OllamaConfigSerializer
```

### 2.5. URL (`config/urls.py`)

将新的 `ViewSet` 注册到 Django REST Framework 的路由器中。

```python
from rest_framework.routers import DefaultRouter
from .views import OllamaConfigViewSet

router = DefaultRouter()
router.register(r'ollama-configs', OllamaConfigViewSet, basename='ollamaconfig')

# urlpatterns... (将其包含在现有 urlpatterns 中)
```

## 3. 前端开发 (React)

### 3.1. 创建设置页面

-   创建一个新组件 `src/pages/SettingsPage.jsx`。
-   在 `src/routes/index.js` 中添加路由 `/settings`。
-   在 `src/components/Sidebar.jsx` 中添加入口链接。

### 3.2. 实现 Ollama 配置 UI (`SettingsPage.jsx`)

-   从后端获取所有 Ollama 配置并以列表形式展示。
-   提供表单用于添加、编辑和删除配置。
-   表单字段应包括：`别名`, `API 地址`, `模型`, `Temperature`, `Top P`, 以及一个 `设为默认` 的复选框。

### 3.3. 更新 API (`api/ollama.js`)

-   创建新的 API 调用函数来与后端的 `ollama-configs` 端点交互。
-   修改 `chatCompletion` 函数，使其接受一个完整的配置对象，而不是依赖全局配置。

```javascript
// 新增 API 函数
export const getOllamaConfigs = () => apiClient.get('/config/ollama-configs/');
export const addOllamaConfig = (config) => apiClient.post('/config/ollama-configs/', config);
export const updateOllamaConfig = (id, config) => apiClient.put(`/config/ollama-configs/${id}/`, config);
export const deleteOllamaConfig = (id) => apiClient.delete(`/config/ollama-configs/${id}/`);

// 修改 chatCompletion
export const chatCompletion = async (config, messages) => {
  const ollamaClient = axios.create({
    baseURL: config.api_endpoint,
    headers: { 'Content-Type': 'application/json' }
  });

  // ... (其余逻辑)
};
```

### 3.4. 更新智能问答页面 (`IntelligentChatPage.jsx`)

-   在页面顶部添加一个下拉菜单（`<select>`），用于显示和选择可用的 Ollama 配置别名。
-   从 `ApiContext` 或组件 state 中管理当前选中的配置。
-   页面加载时，获取所有配置，并将默认配置设为当前选中项。
-   `handleSubmit` 函数现在需要传递当前选中的完整配置对象给 `chatCompletion` 函数。

## 4. 实施流程

1.  **后端**: 从 `models.py` 开始，按照上述步骤完成后端开发。
2.  **前端**: 创建设置页面并实现配置管理功能。
3.  **整合**: 将智能问答页面与新的配置系统集成。
4.  **测试**: 全面测试新功能的各个方面。

这个计划涵盖了从后端数据模型到前端用户交互的所有必要步骤。