# Omni-Desk 测试计划

## 1. 概述

本文档旨在为 `omni_desk_backend` 和 `omni_desk_frontend` 项目制定一个全面的测试策略，目标是将测试覆盖率提高到90%，以确保应用的稳定性、可靠性和可维护性。

## 2. 当前测试覆盖率评估

目前，项目的具体测试覆盖率尚不明确。首要任务是生成一份基准覆盖率报告，以评估现有测试的广度和深度。

*   **后端 (Django):** 尽管存在 `pytest` 和 `coverage` 库，但现有测试的覆盖范围需要通过实际运行来确定。
*   **前端 (React):** 项目使用 Jest 和 React Testing Library，但同样需要生成初始报告来评估覆盖率。

## 3. 达到90%测试覆盖率的策略

为了系统性地达到90%的覆盖率目标，我们将采用以下分层测试策略：

### 3.1. 后端 (`omni_desk_backend`)

1.  **单元测试 (Unit Tests):**
    *   **Models:** 为模型的自定义方法、属性和元数据选项编写测试。
    *   **Serializers:** 验证序列化器的字段验证、数据转换以及 `create()` 和 `update()` 方法。
    *   **Permissions:** 针对自定义权限类 `permissions.py` 编写测试，确保它们能正确授予或拒绝访问。
    *   **Tasks & Services:** 为 Celery 异步任务和任何独立的服务模块编写单元测试，以验证其业务逻辑。

2.  **集成测试 (Integration Tests):**
    *   **API Endpoints (Views):** 为每个 API 视图编写集成测试，覆盖 CRUD 操作、认证/授权逻辑、过滤、分页和错误处理。使用 `APIClient` 模拟 HTTP 请求。

3.  **工具和实践:**
    *   使用 `pytest` 作为测试运行器。
    *   使用 `coverage.py` 持续监控测试覆盖率。
    *   在 CI/CD 流程中集成测试和覆盖率检查，防止未充分测试的代码合并到主分支。

### 3.2. 前端 (`omni_desk_frontend`)

1.  **单元测试 (Unit Tests):**
    *   **Utils/Hooks:** 为独立的工具函数 (`utils`) 和自定义 Hooks 编写测试，确保其逻辑正确。
    *   **API Clients:** 模拟 `axios` 或其他API请求库，验证 API 调用函数是否以正确的参数和格式发送请求。

2.  **组件测试 (Component Tests):**
    *   使用 React Testing Library (`@testing-library/react`) 为每个UI组件编写测试。
    *   测试组件的渲染、用户交互（点击、输入等）以及在不同 `props` 下的行为。
    *   优先测试原子组件和分子组件，确保UI构建块的可靠性。

3.  **集成测试 (Integration Tests):**
    *   测试涉及多个组件协同工作的用户流程，例如：
        *   用户登录和注册流程。
        *   涉及表单提交和API交互的页面（如用户管理、新闻发布）。
        *   跨页面导航。

4.  **工具和实践:**
    *   使用 `Jest` 作为测试框架。
    *   使用 `npm test -- --coverage` 生成覆盖率报告。
    *   利用 Mock Service Worker (`msw`) 拦截和模拟API请求，使前端测试独立于后端。

## 4. 优先测试的关键模块

为了最大化投入产出比，以下模块应被优先测试：

### 后端模块:
*   **`users`:** 认证、授权、用户管理。
*   **`permissions`:** 权限模型和自定义权限逻辑。
*   **`news`:** 新闻内容的创建、发布和管理。
*   **`events`:** 日程和事件管理的核心逻辑。
*   **`communication`:** 内部通信功能。

### 前端组件/页面:
*   **认证流程:** `LoginPage`, `RegisterPage`, `useAuth` hook。
*   **用户管理:** `AdminUserManagementPage`, `UserManagementPage`。
*   **核心布局:** `App.js`, `Sidebar`, `Navbar`。
*   **新闻模块:** `NewsListPage`, `NewsDetailPage`, `NewsEditor`。
*   **日历/排班:** `ScheduleCalendar`, `BookingComponent`。

## 5. 如何运行测试和生成报告

### 5.1. 后端 (`omni_desk_backend`)

1.  **安装依赖:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **运行测试:**
    进入 `omni_desk_backend` 目录，执行以下命令：
    ```bash
    pytest
    ```

3.  **生成覆盖率报告:**
    ```bash
    # 运行测试并收集覆盖率数据
    coverage run -m pytest

    # 在终端查看简要报告
    coverage report

    # 生成详细的 HTML 报告 (推荐)
    coverage html
    ```
    HTML 报告将创建在 `htmlcov/` 目录下，可以在浏览器中打开 `index.html` 查看。

### 5.2. 前端 (`omni_desk_frontend`)

1.  **安装依赖:**
    进入 `omni_desk_frontend` 目录，执行：
    ```bash
    npm install
    ```

2.  **运行测试:**
    ```bash
    # 运行所有测试
    npm test

    # 运行特定文件的测试
    npm test -- src/pages/UserManagementPage.test.js
    ```

3.  **生成覆盖率报告:**
    ```bash
    npm test -- --coverage --watchAll=false
    ```
    该命令会运行所有测试并生成一个覆盖率报告，显示在终端中。同时，会在 `coverage/` 目录下生成一个LCOV报告，可用于更详细的分析。