# Dify 应用集成计划

**目标：** 在现有项目中集成 Dify 应用管理功能，允许用户在管理面板中定义 Dify 应用的名称、嵌入式 URL 等信息，并在前端以列表形式展示这些应用，点击后进入具体应用。

**流程图：**

```mermaid
graph TD
    A[用户定义Dify应用元数据] --> B(后端管理面板);
    B --> C{保存到数据库};
    C --> D[前端Dify应用列表页面];
    D --> E[用户点击应用卡片];
    E --> F[Dify应用详情页面];
    F --> G[iFrame嵌入Dify应用];

    subgraph 后端 (DRFForVue)
        B --> B1(创建DifyApp模型);
        B1 --> B2(创建DifyApp序列化器);
        B2 --> B3(创建DifyApp视图集);
        B3 --> B4(配置DifyApp路由);
        B4 --> B5(注册到Admin面板);
    end

    subgraph 前端 (calendar_with_react)
        D --> D1(创建DifyAppList组件);
        D1 --> D2(通过API获取Dify应用列表);
        D2 --> D3(渲染应用卡片);
        E --> F1(创建DifyAppViewer组件);
        F1 --> G;
        F1 --> F2(配置React路由);
        F2 --> F3(更新侧边栏导航);
    end
```

**详细步骤：**

1.  **后端开发 (DRFForVue)**
    *   **创建 DifyApp 模型**: 在 `DRFForVue` 项目中创建一个新的 Django App (例如 `dify_apps`)。在此 App 中定义 `DifyApp` 模型，包含字段如 `name` (应用名称), `description` (应用描述), `embed_url` (嵌入式 URL), `is_active` (是否激活) 等。
    *   **创建 DifyApp 序列化器**: 为 `DifyApp` 模型创建 Django REST Framework 序列化器。
    *   **创建 DifyApp 视图集**: 创建一个视图集 (ViewSet)，提供 `DifyApp` 的 CRUD (创建、读取、更新、删除) API 接口。
    *   **配置 DifyApp 路由**: 在 `DRFForVue/DRFForVue/urls.py` 或新的 App 的 `urls.py` 中配置 `DifyApp` 视图集的路由。
    *   **注册到 Django Admin 面板**: 将 `DifyApp` 模型注册到 Django Admin，以便管理员可以通过后台管理界面添加、编辑和删除 Dify 应用信息。

2.  **前端开发 (calendar_with_react)**
    *   **创建 DifyApps 目录**: 在 [`calendar_with_react/src/components/`](calendar_with_react/src/components/) 下创建新目录 [`DifyApps/`](calendar_with_react/src/components/DifyApps/)。
    *   **创建 DifyAppList 组件**: 在 [`DifyApps/`](calendar_with_react/src/components/DifyApps/) 下创建 [`DifyAppList.jsx`](calendar_with_react/src/components/DifyApps/DifyAppList.jsx) 组件。
        *   此组件将通过 API 请求后端获取 `DifyApp` 列表数据。
        *   以卡片或列表形式展示每个 Dify 应用的名称和描述。
        *   点击应用卡片后，导航到具体的 Dify 应用展示页面 (`/dify-apps/:appId`)。
    *   **创建 DifyAppViewer 组件**: 在 [`DifyApps/`](calendar_with_react/src/components/DifyApps/) 下创建 [`DifyAppViewer.jsx`](calendar_with_react/src/components/DifyApps/DifyAppViewer.jsx) 组件。
        *   此组件将从路由参数中获取 `appId`。
        *   根据 `appId` 请求后端获取对应的 `embed_url`。
        *   在一个 `iframe` 中加载并显示 `embed_url` 指向的 Dify 应用。
    *   **配置 React 路由**: 修改 [`calendar_with_react/src/routes/index.js`](calendar_with_react/src/routes/index.js)，添加以下路由：
        *   `/dify-apps`：映射到 [`DifyAppList.jsx`](calendar_with_react/src/components/DifyApps/DifyAppList.jsx)。
        *   `/dify-apps/:appId`：映射到 [`DifyAppViewer.jsx`](calendar_with_react/src/components/DifyApps/DifyAppViewer.jsx)。
    *   **更新侧边栏导航**: 修改 [`calendar_with_react/src/components/Sidebar.jsx`](calendar_with_react/src/components/Sidebar.jsx)，在侧边栏中添加一个导航链接，指向 `/dify-apps` 页面。
    *   **样式和布局**: 为 [`DifyAppList.jsx`](calendar_with_react/src/components/DifyApps/DifyAppList.jsx) 和 [`DifyAppViewer.jsx`](calendar_with_react/src/components/DifyApps/DifyAppViewer.jsx) 创建相应的 CSS 文件，确保页面布局美观且与现有项目风格一致。