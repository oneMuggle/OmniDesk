# 用户与人员关联管理功能开发计划

## 任务概述
添加一个新页面，允许管理员和经理将用户与人员关联，并将该页面添加到管理面板的导航栏中。
“人员”是指 `CustomUser` 模型中的用户，并且希望实现一个“人员”只能被一个用户指定的关联关系。

## 计划阶段

### 第一阶段：后端开发

#### 1. 修改 `CustomUser` 模型
- **文件路径**：`omni_desk_backend/users/models.py`
- **修改内容**：在 `CustomUser` 模型中添加一个 `assigned_by` 字段，该字段是一个指向 `CustomUser` 自身的外键，允许为空（表示该人员未被任何用户指定）。
  ```python
  # omni_desk_backend/users/models.py
  from django.db import models
  from django.contrib.auth.models import AbstractUser

  class CustomUser(AbstractUser):
      # ... 现有字段 ...
      assigned_by = models.ForeignKey(
          'self',
          on_delete=models.SET_NULL,
          null=True,
          blank=True,
          related_name='assigned_personnel',
          verbose_name='指派人'
      )
      # ... 其他字段和方法 ...
  ```
- **后续操作**：运行 Django 迁移命令来更新数据库。

#### 2. 修改 `User` 序列化器
- **文件路径**：`omni_desk_backend/users/serializers.py`
- **修改内容**：修改 `CustomUserSerializer`，使其能够处理 `assigned_by` 字段的读写。
  ```python
  # omni_desk_backend/users/serializers.py
  from rest_framework import serializers
  from .models import CustomUser

  class CustomUserSerializer(serializers.ModelSerializer):
      # ... 现有字段 ...
      assigned_by = serializers.PrimaryKeyRelatedField(
          queryset=CustomUser.objects.all(),
          allow_null=True,
          required=False
      )
      assigned_by_username = serializers.CharField(source='assigned_by.username', read_only=True)

      class Meta:
          model = CustomUser
          fields = [
              'id', 'username', 'email', 'phone', 'avatar', 'role', 'assigned_by', 'assigned_by_username'
              # ... 其他现有字段 ...
          ]
          read_only_fields = ['username', 'email', 'role'] # 根据实际需求调整

  ```

#### 3. 添加 API 视图
- **文件路径**：`omni_desk_backend/users/views.py`
- **修改内容**：添加一个新的视图集 `UserPersonnelViewSet`，用于列出所有用户（作为人员），并允许管理员/经理更新某个用户的 `assigned_by` 字段。
  ```python
  # omni_desk_backend/users/views.py
  from rest_framework import viewsets, permissions
  from .models import CustomUser
  from .serializers import CustomUserSerializer
  from .permissions import IsAdminOrManager

  class UserPersonnelViewSet(viewsets.ModelViewSet):
      queryset = CustomUser.objects.all().order_by('username')
      serializer_class = CustomUserSerializer
      permission_classes = [IsAdminOrManager] # 确保只有管理员和经理可以访问

      def get_queryset(self):
          # 允许管理员和经理查看所有用户，普通用户只能查看自己
          if self.request.user.is_authenticated and (self.request.user.role == 'admin' or self.request.user.role == 'manager'):
              return CustomUser.objects.all().order_by('username')
          return CustomUser.objects.filter(id=self.request.user.id) # 假设普通用户只能看到自己
  ```

#### 4. 添加 API 路由
- **文件路径**：`omni_desk_backend/users/urls.py`
- **修改内容**：为 `UserPersonnelViewSet` 添加 URL 模式。
  ```python
  # omni_desk_backend/users/urls.py
  from django.urls import path, include
  from rest_framework.routers import DefaultRouter
  from .views import CustomUserViewSet, UserPersonnelViewSet # 导入UserPersonnelViewSet

  router = DefaultRouter()
  router.register(r'users', CustomUserViewSet)
  router.register(r'personnel', UserPersonnelViewSet) # 为UserPersonnelViewSet注册路由

  urlpatterns = [
      path('', include(router.urls)),
      # ... 其他现有URL模式 ...
  ]
  ```

### 第二阶段：前端开发

#### 1. 创建 `UserPersonnelManagementPage.jsx`
- **文件路径**：`omni_desk_frontend/src/pages/UserPersonnelManagementPage.jsx`
- **文件内容**：创建一个 React 组件，用于显示和管理用户与人员的关联。
  ```jsx
  // omni_desk_frontend/src/pages/UserPersonnelManagementPage.jsx
  import React, { useState, useEffect } from 'react';
  import axios from 'axios';
  import { toast } from 'react-toastify';
  import { useAuth } from '../context/AuthContext'; // 假设有 AuthContext 用于获取 token

  const UserPersonnelManagementPage = () => {
      const [users, setUsers] = useState([]);
      const [personnel, setPersonnel] = useState([]);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState(null);
      const { authToken } = useAuth(); // 从 AuthContext 获取认证 token

      useEffect(() => {
          const fetchData = async () => {
              try {
                  const headers = authToken ? { Authorization: `Token ${authToken}` } : {};
                  const [usersResponse, personnelResponse] = await Promise.all([
                      axios.get('/api/users/', { headers }), // 获取所有用户，用于指派人下拉列表
                      axios.get('/api/personnel/', { headers }) // 获取所有人员，即所有CustomUser
                  ]);
                  setUsers(usersResponse.data);
                  setPersonnel(personnelResponse.data);
              } catch (err) {
                  setError('加载数据失败。请稍后重试。');
                  toast.error('加载数据失败。');
                  console.error('Error fetching data:', err);
              } finally {
                  setLoading(false);
              }
          };

          fetchData();
      }, [authToken]);

      const handleAssignedByChange = async (personnelId, newAssignedById) => {
          try {
              const headers = authToken ? { Authorization: `Token ${authToken}` } : {};
              await axios.patch(`/api/personnel/${personnelId}/`, { assigned_by: newAssignedById || null }, { headers });
              setPersonnel(prevPersonnel =>
                  prevPersonnel.map(p =>
                      p.id === personnelId ? { ...p, assigned_by: newAssignedById, assigned_by_username: users.find(u => u.id === newAssignedById)?.username || null } : p
                  )
              );
              toast.success('关联更新成功！');
          } catch (err) {
              toast.error('更新关联失败。');
              console.error('Error updating assignment:', err);
          }
      };

      if (loading) return <div>加载中...</div>;
      if (error) return <div>{error}</div>;

      return (
          <div className="user-personnel-management-page">
              <h1>用户人员关联管理</h1>
              <table>
                  <thead>
                      <tr>
                          <th>用户名</th>
                          <th>角色</th>
                          <th>当前指派人</th>
                          <th>操作</th>
                      </tr>
                  </thead>
                  <tbody>
                      {personnel.map(p => (
                          <tr key={p.id}>
                              <td>{p.username}</td>
                              <td>{p.role}</td>
                              <td>{p.assigned_by_username || '未指派'}</td>
                              <td>
                                  <select
                                      value={p.assigned_by || ''}
                                      onChange={(e) => handleAssignedByChange(p.id, e.target.value ? parseInt(e.target.value) : null)}
                                  >
                                      <option value="">-- 选择指派人 --</option>
                                      {users.map(u => (
                                          <option key={u.id} value={u.id}>
                                              {u.username} ({u.role})
                                          </option>
                                      ))}
                                  </select>
                              </td>
                          </tr>
                      ))}
                  </tbody>
              </table>
          </div>
      );
  };

  export default UserPersonnelManagementPage;
  ```

#### 2. 更新 `index.js` 路由
- **文件路径**：`omni_desk_frontend/src/routes/index.js`
- **修改内容**：导入 `UserPersonnelManagementPage` 并添加新的路由。
  ```javascript
  // omni_desk_frontend/src/routes/index.js
  // ... 现有导入 ...
  import UserPersonnelManagementPage from './pages/UserPersonnelManagementPage'; // 导入新页面

  const router = createBrowserRouter([
    // ... 现有路由 ...
    {
      path: "/admin",
      element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin"><AdminLayout /></ProtectedRoute>,
      children: [
        // ... 现有子路由 ...
        {
          path: "user-personnel-management",
          element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/user-personnel-management"><UserPersonnelManagementPage /></ProtectedRoute>
        },
        // ... 其他现有子路由 ...
      ]
    },
    // ... 其他现有路由 ...
  ]);
  ```

#### 3. 更新 `Sidebar.jsx` 导航
- **文件路径**：`omni_desk_frontend/src/components/Sidebar.jsx`
- **修改内容**：在 `menuItems` 数组中，找到 `管理中心` 的子菜单，并添加一个新的菜单项。
  ```javascript
  // omni_desk_frontend/src/components/Sidebar.jsx
  // ... 现有导入和定义 ...

  const Sidebar = ({ isMobileMenuOpen, toggleMobileMenu }) => {
    // ... 现有状态和上下文 ...

    const menuItems = [
      // ... 现有菜单项 ...
      { to: "/admin", icon: faCog, text: "管理中心", permission: ["admin", "manager"] },
      {
        type: 'submenu',
        text: '管理中心', // 假设管理中心是一个子菜单
        icon: faCog,
        permission: ["admin", "manager"],
        subItems: [
          // ... 现有管理子菜单项 ...
          { to: "/admin/user-personnel-management", text: "用户人员关联管理", permission: ["admin", "manager"] },
          // ... 其他现有管理子菜单项 ...
        ]
      },
      { type: 'button', icon: faSignOutAlt, text: '退出登录', action: logout, permission: 'authenticated' }
    ];

    // ... 现有 renderMenuItem 函数 ...
  };
  ```

### 第三阶段：测试与部署

1.  **后端测试**：
    *   在本地运行 Django 开发服务器，使用 Postman 或类似的工具测试新的 API 接口。
    *   确保用户和人员的关联关系能够正确地创建、读取、更新。

2.  **前端测试**：
    *   运行前端开发服务器，访问新的“用户人员关联管理”页面。
    *   测试页面功能，包括显示列表、修改关联、保存更改等。
    *   测试权限控制，确保只有管理员和经理能够访问该页面。

3.  **集成测试**：
    *   确保前端和后端能够正常通信。

4.  **部署**：
    *   将所有更改部署到开发或生产环境。

## Mermaid 图

```mermaid
graph TD
    A[用户任务] --> B{分析需求};
    B --> C[收集信息];
    C --> D[澄清问题];
    D --> E[制定计划];

    E --> F[后端开发];
    F --> F1[修改CustomUser模型];
    F1 --> F2[运行Django迁移];
    F2 --> F3[修改User序列化器];
    F3 --> F4[添加API视图];
    F4 --> F5[添加API路由];

    E --> G[前端开发];
    G --> G1[创建UserPersonnelManagementPage.jsx];
    G1 --> G2[更新routes/index.js];
    G2 --> G3[更新Sidebar.jsx];
    G3 --> G4[实现API调用];

    F --> H[测试与部署];
    G --> H;
    H --> H1[后端测试];
    H1 --> H2[前端测试];
    H2 --> H3[集成测试];
    H3 --> H4[部署];