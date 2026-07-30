# 技术文档：用户与权限管理

## 1. 概述

本系统采用一种混合权限模型，将后端API的访问控制与前端页面的可见性分离开来，以实现灵活而安全的用户权限管理。

- **后端API授权**: 基于在 `CustomUser` 模型中定义的静态角色（`role`），例如“管理员”、“经理”和“普通用户”。
- **前端页面可见性**: 一个完全动态的、由数据库驱动的系统，它允许管理员通过界面将特定的前端路由（页面）授权给不同的用户组。

---

## 2. 后端实现

### 2.1. API 访问控制 (基于角色)

API的访问权限主要由 `users` 应用负责。

- **核心模型**: [`omni_desk_backend/users/models.py`](omni_desk_backend/users/models.py:4)
  - `CustomUser` 模型包含一个 `role` 字段，用于定义用户的基本角色。

- **权限控制**: [`omni_desk_backend/users/permissions.py`](omni_desk_backend/users/permissions.py)
  - 定义了一系列权限类，如 `IsAdmin`、`IsManager` 和 `IsAdminOrManager`。
  - 这些类检查请求用户的 `role` 属性，以确定其是否有权访问特定的API端点。
  - 例如，一个视图如果设置了 `permission_classes = [IsAdmin]`，那么只有 `role` 为 `admin` 的用户才能访问。

### 2.2. 前端页面可见性 (基于用户组)

前端页面的可见性由一个独立的 `permissions` 应用管理。

- **核心模型**: [`omni_desk_backend/permissions/models.py`](omni_desk_backend/permissions/models.py)
  - `PageRoute`: 将每个前端路由（如 `/dashboard`, `/settings`）抽象为数据库中的一个条目。
  - `Group` (Django内置): 代表用户组（如“财务部”、“研发部”）。
  - `GroupPagePermission`: 一个中间表，用于建立 `Group` 和 `PageRoute` 之间的多对多关系，从而定义哪个用户组可以查看哪个页面。

- **核心API视图**: [`omni_desk_backend/permissions/views.py`](omni_desk_backend/permissions/views.py)
  - `GroupViewSet`: 提供对用户组的完整CRUD（创建、读取、更新、删除）操作。
  - `PageRouteViewSet`: 提供一个只读的API，用于获取所有已定义的页面路由，通常以树状结构返回。
  - `GroupPermissionView`: 核心视图，处理特定用户组的权限读取和更新。
    - `GET`: 获取一个用户组被授权的所有 `PageRoute` ID。
    - `PUT`: 批量更新一个用户组的页面权限。
  - `UserPermissionView`: 获取当前登录用户有权访问的所有页面路由。前端通常在登录后调用此接口来动态生成导航菜单。

---

## 3. 前端实现

前端的权限管理界面由 `GroupPermissionManager` 组件实现。

- **核心组件**: [`omni_desk_frontend/src/components/Admin/GroupPermissionManager.jsx`](omni_desk_frontend/src/components/Admin/GroupPermissionManager.jsx)
  - 该组件提供了一个完整的管理界面，允许管理员：
    1.  创建、编辑和删除用户组。
    2.  选择一个用户组。
    3.  在页面树中勾选该用户组可以访问的页面。
    4.  保存更改，通过调用后端的 `GroupPermissionView` 来更新权限。

- **API客户端**: [`omni_desk_frontend/src/api/permissionsApi.js`](omni_desk_frontend/src/api/permissionsApi.js)
  - 这是一个专门的API客户端，封装了所有与后端 `permissions` 应用交互的HTTP请求。

---

## 4. 用户-人员关联

系统还支持将一个用户账户（`CustomUser`）与一个“人员”实体（`events.Personnel`）进行一对一绑定。

- **后端**:
  - `CustomUser` 模型中有一个 `personnel` 字段，它是一个到 `events.Personnel` 的 `OneToOneField`。
  - [`omni_desk_backend/users/views.py`](omni_desk_backend/users/views.py) 中的 `UserPersonnelViewSet` 提供了API，允许管理员将用户账户指派给一个人员。
- **前端**:
  - 相关的管理界面允许管理员在用户列表中为每个用户选择并关联一个“人员”。

---

## 5. 行级权限 / 作者隔离 / 权限体系清理（2026-07 P0 批次）

> 本节对应审计批次 [41-p0-security-data-safety-batch-2026-07.md §1-3](41-p0-security-data-safety-batch-2026-07.md)。覆盖 P0-A / P0-C / P0-D / P0-E 四个修复点。

### 5.1 `IsOwnerOrManagerOrReadOnly`（personnel 行级权限,P0-A）

[`omni_desk_backend/personnel/permissions.py`](omni_desk_backend/personnel/permissions.py) 新增的权限类,用于 personnel 子模型的行级访问控制(Contract / Education / WorkExperience / Qualification / FamilyMember 共 5 个 ViewSet)。

**判定逻辑(双层防御):**

1. **L1 `has_permission`:** 仅要求登录(`request.user.is_authenticated`)。
2. **L3 `has_object_permission`:**
   - `SAFE_METHODS` → 放行(由 `get_queryset` 行级过滤兜底,见下)
   - `request.user.is_privileged_user()` → 放行(Admin / Manager 组 + superuser)
   - 反向查找 `obj.personnel.user_account_id == request.user.id` → 放行
   - 其他 → 拒

**ViewSet 接入示例(ContractViewSet):**

```python
class ContractViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrManagerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_privileged_user():
            return Contract.objects.all()
        return Contract.objects.filter(personnel__user_account=self.request.user)
```

> **注意:** 项目原本无 `CustomUser.role` 字段(只在 `Personnel.role`);行级权限统一走 `is_privileged_user()`(内部封装"Admin / Manager 组 + superuser"判定)。其余四个 ViewSet 接入模式同上,详见 [41-p0-security-data-safety-batch-2026-07.md §1.1](41-p0-security-data-safety-batch-2026-07.md)。

**测试位置:** `omni_desk_backend/personnel/tests/test_permissions.py`(owner 可读本人 / 其他用户看不到他人)。

### 5.2 `IsAuthorOrReadOnly`(communication 作者隔离,P0-D)

[`omni_desk_backend/communication/views.py`](omni_desk_backend/communication/views.py) 新增的权限类,适用于 `Post` / `Comment` 等"作者本人可控"模型。

**判定逻辑:**

- `SAFE_METHODS` → 放行
- `obj.author_id == request.user.id` → 放行
- 其他 → 403

**接入:**

```python
class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]

    def get_queryset(self):
        return Post.objects.all()  # 安全方法内可看所有,写入由 IsAuthorOrReadOnly 控制
```

**测试位置:** `omni_desk_backend/communication/tests/test_author_isolation.py`(Bob 不能 DELETE Alice 的帖子)。

### 5.3 权限体系清理(P0-C, P0-E)

- **去重 `IsAdminOrManagerOrReadOnly`:** [`users/permissions.py`](omni_desk_backend/users/permissions.py) 历史上存在两份重复定义(行 70-89 与 158-176),`2026-07` 批次已合并为唯一一份并加注释。
- **删除不可达 return:** `IsTargetPersonnel.has_object_permission` 历史上在 `if request.user.role in ('admin', 'hr'): return True` 分支后留有 `return IsAdmin().has_permission(...)` 的死代码(line 210),已删除。
- **`UserAdminDetailView` 删 `instance.phone_number` 死引用:** [`users/views.py`](omni_desk_backend/users/views.py) 第 233 行原写 `instance.phone_number = personnel.phone_numbers.first().number`,但 `instance` 不是 Personnel,实际从未生效;已删除该行,改为提示用户走 `PhoneNumber` 关联模型 `update_or_create`(详见 [26-personnel-user-association.md](26-personnel-user-association.md) §3.2)。

**测试位置:** `omni_desk_backend/users/tests/test_permissions_cleanup.py`(`inspect` 静态断言同名类仅一份 / 无死代码)。