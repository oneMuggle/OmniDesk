# 实施计划：三层级外部项目集成

## 背景与目标

OmniDesk 平台目前已独立集成 Dify、RagFlow 等 AI 服务，但每个集成都是独立的 Django app + 前端页面，缺乏统一的管理和扩展机制。本项目旨在建立三层级外部集成体系：

1. **第一层：外链集成** — 内网工具的统一导航入口（GitLab、Jenkins 等），支持分类、图标、描述、SSO 跳转
2. **第二层：功能调用集成** — 带 API 调用的内网服务（RAGFlow、Dify 等），支持配置管理、iframe 嵌入、API 代理
3. **第三层：热插拔插件系统** — 用户上传自定义插件，提供统一接口模板，沙箱执行，版本管理

**核心目标：** 将现有的 Dify/RagFlow 等集成迁移到统一框架下，为未来扩展提供标准化路径。

## 涉及文件与模块

### 后端新增
| 文件路径 | 说明 |
|---------|------|
| `omni_desk_backend/external_integration/__init__.py` | Django app 入口 |
| `omni_desk_backend/external_integration/models.py` | 三层集成的数据模型 |
| `omni_desk_backend/external_integration/serializers.py` | API 序列化器 |
| `omni_desk_backend/external_integration/views.py` | ViewSet + 自定义 action |
| `omni_desk_backend/external_integration/urls.py` | 路由注册 |
| `omni_desk_backend/external_integration/permissions.py` | 插件执行权限控制 |
| `omni_desk_backend/external_integration/plugin_loader.py` | 插件加载器（第三层核心） |
| `omni_desk_backend/external_integration/plugin_sandbox.py` | 插件沙箱执行环境 |
| `omni_desk_backend/external_integration/admin.py` | Django Admin 注册 |
| `omni_desk_backend/external_integration/apps.py` | App 配置 |
| `omni_desk_backend/external_integration/migrations/0001_initial.py` | 数据库迁移 |
| `omni_desk_backend/external_integration/tests/test_models.py` | 模型测试 |
| `omni_desk_backend/external_integration/tests/test_api.py` | API 测试 |
| `omni_desk_backend/external_integration/tests/test_plugin_loader.py` | 插件加载器测试 |

### 后端修改
| 文件路径 | 说明 |
|---------|------|
| `omni_desk_backend/omni_desk_backend/settings/base.py` | 注册 `external_integration` app，添加插件目录配置 |
| `omni_desk_backend/omni_desk_backend/urls.py` | 注册新的 API 路由 |
| `omni_desk_backend/omni_desk_backend/settings/production.py` | 添加插件沙箱安全配置 |

### 前端新增
| 文件路径 | 说明 |
|---------|------|
| `omni_desk_frontend/src/features/external-links/pages/ExternalLinksPage.jsx` | 第一层：外链展示页 |
| `omni_desk_frontend/src/features/external-links/pages/ExternalLinkManagementPage.jsx` | 第一层：外链管理页 |
| `omni_desk_frontend/src/features/external-links/api/externalLinksApi.js` | 第一层：API 封装 |
| `omni_desk_frontend/src/features/integration-hub/pages/IntegrationHubPage.jsx` | 第二层：集成中心展示页 |
| `omni_desk_frontend/src/features/integration-hub/pages/IntegrationManagementPage.jsx` | 第二层：集成管理页 |
| `omni_desk_frontend/src/features/integration-hub/components/IntegrationCard.jsx` | 集成卡片组件 |
| `omni_desk_frontend/src/features/integration-hub/components/IntegrationIframeViewer.jsx` | iframe 嵌入查看器 |
| `omni_desk_frontend/src/features/integration-hub/api/integrationApi.js` | 第二层：API 封装 |
| `omni_desk_frontend/src/features/plugin-market/pages/PluginMarketPage.jsx` | 第三层：插件市场页 |
| `omni_desk_frontend/src/features/plugin-market/pages/PluginManagementPage.jsx` | 第三层：插件管理页 |
| `omni_desk_frontend/src/features/plugin-market/components/PluginCard.jsx` | 插件卡片组件 |
| `omni_desk_frontend/src/features/plugin-market/components/PluginUploadModal.jsx` | 插件上传弹窗 |
| `omni_desk_frontend/src/features/plugin-market/components/PluginDetailModal.jsx` | 插件详情弹窗 |
| `omni_desk_frontend/src/features/plugin-market/api/pluginApi.js` | 第三层：API 封装 |
| `omni_desk_frontend/src/features/plugin-market/utils/pluginValidator.js` | 插件格式验证工具 |

### 前端修改
| 文件路径 | 说明 |
|---------|------|
| `omni_desk_frontend/src/routes/index.js` | 新增三层集成的路由 |
| `omni_desk_frontend/src/shared/config/menuConfig.js` | 新增菜单项（外链、集成中心、插件市场） |

## 技术方案

### 数据库模型设计

#### 第一层模型：ExternalLink（外链）

```python
class ExternalLink(models.Model):
    name = CharField(max_length=255, verbose_name="名称")
    url = URLField(max_length=500, verbose_name="链接地址")
    icon = CharField(max_length=50, null=True, verbose_name="图标类名")  # Ant Design icon name
    description = TextField(blank=True, verbose_name="描述")
    category = CharField(max_length=100, db_index=True, verbose_name="分类")  # 如: 开发工具, CI/CD, 文档管理
    sso_enabled = BooleanField(default=False, verbose_name="是否启用 SSO")
    sso_token_endpoint = URLField(max_length=500, null=True, blank=True, verbose_name="SSO Token 端点")
    sort_order = IntegerField(default=0, verbose_name="排序")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

#### 第二层模型：IntegrationService（集成服务）

```python
class IntegrationService(models.Model):
    INTEGRATION_TYPES = [
        ('iframe', 'iframe 嵌入'),
        ('api', 'API 代理调用'),
        ('widget', '组件嵌入'),
    ]
    name = CharField(max_length=255, unique=True, verbose_name="服务名称")
    slug = SlugField(unique=True, verbose_name="标识符")  # 用于 URL 和前端识别
    description = TextField(blank=True, verbose_name="描述")
    integration_type = CharField(choices=INTEGRATION_TYPES, max_length=20, verbose_name="集成类型")
    endpoint_url = URLField(max_length=500, verbose_name="服务端点")
    api_key = CharField(max_length=255, blank=True, null=True, verbose_name="API 密钥")  # 加密存储
    embed_path = CharField(max_length=500, blank=True, null=True, verbose_name="嵌入路径/模板")
    config_schema = JSONField(default=dict, verbose_name="配置 Schema")  # JSON Schema 定义额外配置
    metadata = JSONField(default=dict, verbose_name="元数据")  # 图标、颜色、特性标签等
    is_active = BooleanField(default=True, verbose_name="是否激活")
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

#### 第三层模型：Plugin + PluginVersion（插件及版本）

```python
class Plugin(models.Model):
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending_review', '待审核'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('disabled', '已禁用'),
    ]
    name = CharField(max_length=255, unique=True, verbose_name="插件名称")
    slug = SlugField(unique=True, verbose_name="标识符")
    description = TextField(blank=True, verbose_name="描述")
    author = ForeignKey(CustomUser, on_delete=SET_NULL, null=True, verbose_name="作者")
    category = CharField(max_length=100, db_index=True, verbose_name="分类")
    icon = CharField(max_length=50, null=True, verbose_name="图标")
    status = CharField(choices=STATUS_CHOICES, default='draft', max_length=20, verbose_name="状态")
    interface_version = CharField(max_length=20, default='v1', verbose_name="接口版本")
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class PluginVersion(models.Model):
    plugin = ForeignKey(Plugin, on_delete=CASCADE, related_name='versions', verbose_name="所属插件")
    version = CharField(max_length=20, verbose_name="版本号")  # SemVer
    upload_file = FileField(upload_to='plugins/', verbose_name="插件文件")  # .zip 或 .py
    file_hash = CharField(max_length=64, verbose_name="文件哈希")  # SHA-256
    manifest = JSONField(default=dict, verbose_name="插件清单")
    is_active = BooleanField(default=False, verbose_name="是否激活")
    uploaded_by = ForeignKey(CustomUser, on_delete=SET_NULL, null=True, verbose_name="上传人")
    uploaded_at = DateTimeField(auto_now_add=True)
    review_notes = TextField(blank=True, null=True, verbose_name="审核备注")

class PluginCallLog(models.Model):
    """插件调用审计日志"""
    plugin_version = ForeignKey(PluginVersion, on_delete=SET_NULL, null=True, verbose_name="插件版本")
    user = ForeignKey(CustomUser, on_delete=SET_NULL, null=True, verbose_name="调用用户")
    method = CharField(max_length=20, verbose_name="调用方法")
    args_summary = CharField(max_length=500, blank=True, verbose_name="参数摘要")
    status = CharField(max_length=20, verbose_name="执行状态")
    execution_time_ms = IntegerField(null=True, verbose_name="执行耗时(ms)")
    error_message = TextField(blank=True, null=True, verbose_name="错误信息")
    created_at = DateTimeField(auto_now_add=True)
```

### API 端点设计

#### 第一层：外链 API
| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/external-links/` | GET | 获取外链列表（按分类分组） |
| `POST /api/external-links/` | POST | 创建外链（admin） |
| `PUT /api/external-links/:id/` | PUT | 更新外链（admin） |
| `DELETE /api/external-links/:id/` | DELETE | 删除外链（admin） |
| `POST /api/external-links/:id/sso-token/` | POST | 获取 SSO 跳转 token |

#### 第二层：集成服务 API
| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/integrations/` | GET | 获取集成服务列表 |
| `POST /api/integrations/` | POST | 创建集成服务（admin） |
| `PUT /api/integrations/:id/` | PUT | 更新集成服务（admin） |
| `DELETE /api/integrations/:id/` | DELETE | 删除集成服务（admin） |
| `GET /api/integrations/:slug/embed/` | GET | 获取嵌入 URL（代理） |
| `POST /api/integrations/:slug/proxy/` | POST | API 代理调用 |

#### 第三层：插件 API
| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/plugins/` | GET | 获取插件列表 |
| `POST /api/plugins/` | POST | 上传插件（需要上传权限） |
| `GET /api/plugins/:id/` | GET | 获取插件详情（含版本列表） |
| `POST /api/plugins/:id/versions/:version/activate/` | POST | 激活指定版本（admin） |
| `POST /api/plugins/:id/review/` | POST | 审核插件（admin） |
| `POST /api/plugins/:id/execute/` | POST | 执行插件功能 |
| `GET /api/plugins/:id/logs/` | GET | 查看调用日志（admin） |
| `GET /api/plugins/template/` | GET | 下载插件开发模板 |

### 第三层插件安全设计

#### 多语言支持设计

第三层插件系统采用 **"协议化"** 而非 **"类继承"** 的架构，支持 C、C++、Fortran、Python、Go、Rust 等任意语言编写的程序。

**核心理念：CLI 标准输入输出协议**

插件不依赖特定语言，只需实现标准输入输出协议：
```
stdin:  JSON 格式输入 {"action": "run", "params": {...}}
stdout: JSON 格式输出 {"status": "success", "result": {...}}
exit code: 0=成功, 非0=失败
```

后端通过 `subprocess` 调用编译后的可执行文件，天然实现进程隔离沙箱。

#### 插件打包规范

用户上传 `.zip` 包，内含：
```
my-plugin/
├── manifest.json       # 插件描述与运行时信息
├── executable          # 编译后的可执行文件（Linux ELF）
├── config_schema.json  # 配置界面定义（可选）
└── README.md           # 使用说明
```

#### 插件清单（manifest.json）

```json
{
  "name": "my-fortran-calculator",
  "version": "1.0.0",
  "runtime": "native",
  "language": "fortran",
  "entry_point": "./executable",
  "protocol": "stdio",
  "timeout_seconds": 30,
  "memory_limit_mb": 256,
  "system_dependencies": ["libgfortran5"],
  "permissions": ["stdio"]
}
```

#### 多语言 SDK 模板

为降低用户接入成本，项目为不同语言提供 SDK 模板：

| 语言 | SDK 文件 | 说明 |
|------|----------|------|
| **C** | `plugin_sdk.h` + `main.c` | 头文件提供 JSON 输入输出封装 |
| **C++** | `plugin_sdk.hpp` + `main.cpp` | 封装类提供类型安全的接口 |
| **Fortran** | `plugin_sdk.f90` + `main.f90` | 模块提供 ISO_C_BINDING 适配 |
| **Python** | `plugin_sdk.py` + `main.py` | 可直接用 `BasePlugin` 类或 CLI 模式 |
| **Go** | `sdk/go.mod` + `main.go` | Go module 提供便捷封装 |
| **Rust** | `sdk/Cargo.toml` + `main.rs` | Rust crate 提供类型安全接口 |

**Python 双模式支持：**
- **CLI 模式**（推荐）：读写 stdin/stdout，与多语言统一
- **类模式**（保留）：继承 `BasePlugin`，适合简单 Python 脚本快速集成

#### 沙箱执行机制

采用 **子进程隔离** 作为核心沙箱方案：
- 所有插件（无论语言）在独立子进程中执行
- 设置资源限制：30 秒超时、256MB 内存上限
- 使用 Linux `prlimit` / `cgroups` 限制系统资源
- 禁用网络访问（除非插件申请 `network` 权限并审核通过）
- 临时目录隔离，插件无法访问宿主文件系统

#### 插件接口规范（SDK 示例）

```c
/* plugin_sdk.h — C 语言 SDK */
#ifndef PLUGIN_SDK_H
#define PLUGIN_SDK_H

/* 读取 JSON 输入 */
char* plugin_read_input(void);

/* 输出 JSON 结果 */
void plugin_output(const char* json_result);

/* 输出错误 */
void plugin_error(const char* message, int exit_code);

#endif
```

```fortran
! plugin_sdk.f90 — Fortran SDK
module plugin_sdk
  use iso_c_binding
  implicit none
contains
  subroutine read_input(json_string)
    character(len=:), allocatable, intent(out) :: json_string
    ! 从 stdin 读取 JSON
  end subroutine

  subroutine write_output(json_result)
    character(len=*), intent(in) :: json_result
    ! 写入 stdout
  end subroutine
end module
```

### 数据流与架构

```
前端 (React)                        后端 (Django)
┌───────────────────────┐          ┌────────────────────────────┐
│ ExternalLinksPage     │ ─GET──→  │ ExternalLinkViewSet        │
│ (分类展示外链)          │          │ (CRUD + SSO token)         │
├───────────────────────┤          ├────────────────────────────┤
│ IntegrationHubPage    │ ─GET──→  │ IntegrationServiceViewSet  │
│ (集成服务展示)          │ ─POST─→ │ /proxy/ action → 转发请求  │
│ (iframe/API 调用)      │          │ → 外部服务 → 返回结果       │
├───────────────────────┤          ├────────────────────────────┤
│ PluginMarketPage      │ ─POST──→│ PluginViewSet              │
│ (浏览/上传/执行插件)    │ ─POST─→ │ /execute/ action           │
│                       │          │ → PluginLoader             │
│                       │          │   → SandboxExecutor        │
│                       │          │     → 隔离执行插件代码      │
│                       │          │   → 返回结果                │
│                       │          │ → PluginCallLog 记录审计    │
└───────────────────────┘          └────────────────────────────┘
```

## 实施步骤

### 第一阶段：基础架构与第一层外链集成（1-2 天）

- [x] **步骤 1：创建 Django app**
  - 文件：`omni_desk_backend/external_integration/`（整个目录）
  - 创建 app 结构：`models.py`, `views.py`, `serializers.py`, `urls.py`, `admin.py`, `apps.py`
  - 在 `settings/base.py` 注册 app
  - 在 `urls.py` 注册 API 路由
  - 风险：低

- [x] **步骤 2：实现 ExternalLink 模型和 API**
  - 文件：`omni_desk_backend/external_integration/models.py`
  - 文件：`omni_desk_backend/external_integration/serializers.py`
  - 文件：`omni_desk_backend/external_integration/views.py`
  - 实现 CRUD + SSO token 生成端点
  - 编写数据库迁移
  - 风险：低

- [x] **步骤 3：前端外链展示页面**
  - 文件：`omni_desk_frontend/src/features/external-links/pages/ExternalLinksPage.jsx`
  - 文件：`omni_desk_frontend/src/features/external-links/pages/ExternalLinkManagementPage.jsx`
  - 文件：`omni_desk_frontend/src/features/external-links/api/externalLinksApi.js`
  - 按分类分组展示，支持 SSO 跳转
  - 风险：低

- [x] **步骤 4：路由和菜单集成**
  - 文件：`omni_desk_frontend/src/routes/index.js`
  - 文件：`omni_desk_frontend/src/shared/config/menuConfig.js`
  - 添加外链菜单项（首页下或独立导航）
  - 风险：低

- [x] **步骤 5：编写测试**
  - 文件：`omni_desk_backend/external_integration/tests/test_models.py`
  - 文件：`omni_desk_backend/external_integration/tests/test_api.py`
  - 模型测试 + API CRUD 测试
  - 风险：低

### 第二阶段：第二层功能调用集成（2-3 天）

- [ ] **步骤 6：实现 IntegrationService 模型和 API**
  - 文件：`omni_desk_backend/external_integration/models.py`（追加）
  - 文件：`omni_desk_backend/external_integration/serializers.py`（追加）
  - 文件：`omni_desk_backend/external_integration/views.py`（追加）
  - 实现嵌入 URL 获取 + API 代理端点
  - API 密钥加密存储（使用 Django `cryptography` 或 Fernet）
  - 风险：中 — API 代理需要处理超时、错误转发

- [ ] **步骤 7：前端集成中心页面**
  - 文件：`omni_desk_frontend/src/features/integration-hub/pages/IntegrationHubPage.jsx`
  - 文件：`omni_desk_frontend/src/features/integration-hub/pages/IntegrationManagementPage.jsx`
  - 文件：`omni_desk_frontend/src/features/integration-hub/components/IntegrationCard.jsx`
  - 文件：`omni_desk_frontend/src/features/integration-hub/components/IntegrationIframeViewer.jsx`
  - 文件：`omni_desk_frontend/src/features/integration-hub/api/integrationApi.js`
  - 支持 iframe 嵌入视图 + API 调用面板
  - 风险：中 — iframe CSP 策略可能需要额外配置

- [ ] **步骤 8：迁移现有 Dify/RagFlow 到统一框架**
  - 将 `dify_apps` 数据迁移到 `IntegrationService` 模型
  - 创建数据迁移脚本
  - 保留旧端点兼容（标记 deprecated），新前端指向新端点
  - 风险：中 — 需要保证迁移期间不影响现有功能

- [ ] **步骤 9：编写测试**
  - 文件：`omni_desk_backend/external_integration/tests/test_models.py`（追加）
  - 文件：`omni_desk_backend/external_integration/tests/test_api.py`（追加）
  - API 代理测试 + iframe 安全测试
  - 风险：低

### 第三阶段：第三层热插拔插件系统（4-5 天）

- [ ] **步骤 10：实现 Plugin 模型和 API（基础 CRUD）**
  - 文件：`omni_desk_backend/external_integration/models.py`（追加）
  - 文件：`omni_desk_backend/external_integration/serializers.py`（追加）
  - 文件：`omni_desk_backend/external_integration/views.py`（追加）
  - 实现 Plugin + PluginVersion + PluginCallLog 模型
  - 实现插件上传、版本管理、审核流程 API
  - 风险：中 — 文件上传安全需要额外注意

- [ ] **步骤 11：实现插件加载器和沙箱**
  - 文件：`omni_desk_backend/external_integration/plugin_loader.py`
  - 文件：`omni_desk_backend/external_integration/plugin_sandbox.py`
  - 文件：`omni_desk_backend/external_integration/permissions.py`
  - 实现插件解压、manifest 解析、子进程沙箱执行
  - 使用 `subprocess` + `prlimit` 设置超时（30 秒）和内存限制（256MB）
  - 实现 stdin/stdout JSON 协议通信
  - 实现临时目录隔离，禁用网络访问（默认）
  - 风险：高 — 子进程逃逸是核心安全风险，需全面测试

- [ ] **步骤 12：多语言 SDK 模板和开发指南**
  - 文件：`omni_desk_backend/external_integration/templates/plugin_manifest.json`
  - 文件：`omni_desk_backend/external_integration/templates/sdk/c/main.c` + `plugin_sdk.h`
  - 文件：`omni_desk_backend/external_integration/templates/sdk/cpp/main.cpp` + `plugin_sdk.hpp`
  - 文件：`omni_desk_backend/external_integration/templates/sdk/fortran/main.f90` + `plugin_sdk.f90`
  - 文件：`omni_desk_backend/external_integration/templates/sdk/python/main.py` + `plugin_sdk.py`
  - 文件：`omni_desk_backend/external_integration/templates/sdk/go/main.go` + `go.mod`
  - 文件：`docs/technical/plugin-development-guide.md`（归档目录）
  - 提供 6 种语言的 SDK 模板 + 示例插件（每种语言一个 Hello World 示例）
  - 风险：低

- [ ] **步骤 13：前端插件市场页面**
  - 文件：`omni_desk_frontend/src/features/plugin-market/pages/PluginMarketPage.jsx`
  - 文件：`omni_desk_frontend/src/features/plugin-market/pages/PluginManagementPage.jsx`
  - 文件：`omni_desk_frontend/src/features/plugin-market/components/PluginCard.jsx`
  - 文件：`omni_desk_frontend/src/features/plugin-market/components/PluginUploadModal.jsx`
  - 文件：`omni_desk_frontend/src/features/plugin-market/components/PluginDetailModal.jsx`
  - 文件：`omni_desk_frontend/src/features/plugin-market/api/pluginApi.js`
  - 文件：`omni_desk_frontend/src/features/plugin-market/utils/pluginValidator.js`
  - 支持浏览、上传、查看、执行插件
  - 风险：中 — 上传验证需要在前端和后端都做

- [ ] **步骤 14：编写测试**
  - 文件：`omni_desk_backend/external_integration/tests/test_plugin_loader.py`
  - 子进程隔离测试：验证插件无法访问宿主文件系统
  - 恶意代码测试：验证 `rm -rf /`, `curl external_url` 等被拦截
  - 超时测试：验证无限循环插件被强制终止
  - 内存测试：验证内存超限被强制终止
  - 多语言测试：分别用 C/C++/Fortran/Python 编译的插件验证执行流程
  - 风险：高 — 安全测试必须全面

### 第四阶段：集成、优化和文档（2-3 天）

- [ ] **步骤 15：菜单和路由全面集成**
  - 更新 `menuConfig.js`，将三层功能加入导航
  - 建议菜单结构：
    ```
    外部集成（submenu）
    ├── 快捷外链（第一层）
    ├── 集成中心（第二层）
    └── 插件市场（第三层，admin）
    ```
  - 风险：低

- [ ] **步骤 16：安全加固**
  - 配置 X-Frame-Options 允许受信任域名 iframe 嵌入
  - 添加插件执行速率限制
  - 添加 API 密钥加密存储（使用 `django-cryptography` 或 `cryptography.fernet`）
  - 添加插件文件类型白名单（.zip, .py）
  - 添加文件大小限制（默认 10MB）
  - 风险：中

- [ ] **步骤 17：编写完整测试和覆盖率报告**
  - 确保整体覆盖率 >= 80%
  - 添加集成测试：完整的上传 -> 审核 -> 激活 -> 执行流程
  - 风险：中

- [ ] **步骤 18：文档更新**
  - 文件：`docs/technical/external-integration-architecture.md`
  - 文件：`docs/technical/plugin-development-guide.md`
  - 文件：`docs/technical/api-reference.md`
  - 更新 `CLAUDE.md` 添加新模块说明
  - 风险：低

## 风险评估与依赖

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|----------|
| 插件子进程逃逸 | **高** | 恶意插件可访问服务器文件系统或执行系统命令 | 1. 子进程隔离 + prlimit 资源限制 2. 禁用网络（默认）3. 临时目录隔离 4. 插件审核流程 5. 调用审计日志 |
| 多语言依赖缺失 | **中** | Fortran/C++ 等插件因缺少运行时库无法执行 | 1. manifest 声明 system_dependencies 2. 构建阶段预装常见运行时 3. 上传时验证可执行文件合法性 |
| API 代理被滥用 | **中** | 攻击者可能通过代理端点发起 SSRF 攻击 | 1. 限制允许代理的目标域名（白名单）2. 添加速率限制 3. 验证 redirect 不跳出白名单 |
| iframe CSP 冲突 | **中** | 部分外部服务可能拒绝在 iframe 中嵌入 | 1. 提前验证目标服务 CSP 2. 对于不支持 iframe 的服务降级为链接跳转 |
| 数据迁移影响现有功能 | **中** | Dify/RagFlow 现有用户可能受影响 | 1. 保留旧 API 端点兼容 2. 分阶段迁移 3. 充分测试 |
| 内网离线环境依赖 | **中** | SDK 模板等需要在构建时打包 | 1. SDK 模板随代码一起打包 2. 确保构建机器可联网，目标服务器离线可用 |
| 插件版本兼容性 | **低** | 插件接口变更可能导致旧插件失效 | 1. 插件接口版本化（protocol 字段）2. 向后兼容策略 |

## 依赖关系

- **第一阶段** 无外部依赖，可独立开始
- **第二阶段** 依赖第一阶段的 app 结构和 API 路由注册
- **第三阶段** 依赖前两阶段的基础，特别是模型和权限框架
- **第四阶段** 依赖前三阶段的实现完成

每阶段可独立合并到主分支，不阻塞其他阶段。

## 成功标准

- [ ] 外链管理：用户可添加/分类/查看外链，支持 SSO 跳转
- [ ] 集成服务：用户可通过 iframe 或 API 调用方式与 Dify/RagFlow 等服务交互
- [ ] 现有 Dify/RagFlow 数据成功迁移到新模型，旧端点保持兼容
- [ ] 插件系统：用户可上传、审核、激活、执行自定义插件
- [ ] 插件沙箱（子进程隔离）能拦截文件系统越权访问、网络外连、资源超限等恶意操作
- [ ] 多语言 SDK 模板覆盖 C、C++、Fortran、Python、Go、Rust
- [ ] 测试覆盖率 >= 80%
- [ ] 所有 API 端点通过认证和权限保护
- [ ] 内网离线环境下所有依赖可用
