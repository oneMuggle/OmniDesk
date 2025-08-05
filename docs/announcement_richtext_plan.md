# 富文本公告功能改造计划

## 1. 目标

将现有的纯文本公告系统升级为支持富文本格式的系统，允许管理员使用格式化文本、列表、链接等功能来创建和编辑公告。

## 2. 技术选型

*   **富文本编辑器**: `react-quill` - 一个强大且易于集成的 React 富文本编辑器组件。
*   **后端**: 保持现有的 Django + DRF 结构，`TextField` 足以存储 HTML 内容。
*   **前端**: React

## 3. 改造步骤

```mermaid
graph TD
    A[开始] --> B{1. 安装依赖};
    B --> C{2. 修改公告表单};
    C --> D{3. 修改公告展示页面};
    D --> E[完成];

    subgraph 后端 (无需修改)
        direction LR
        F[模型: Announcement]
        G[序列化器: AnnouncementSerializer]
    end

    subgraph 前端修改
        direction TB
        C --> C1[a. 导入 ReactQuill];
        C --> C2[b. 替换 textarea];
        C --> C3[c. 更新 state 和 onChange];
        
        D --> D1[a. 获取公告内容];
        D --> D2[b. 使用 dangerouslySetInnerHTML 渲染];
    end
```

**详细步骤解释**:

1.  **安装依赖**:
    *   使用 `npm` 来安装 `react-quill` 库及其必要的 CSS 文件。

2.  **修改公告表单 (`AnnouncementForm.jsx`)**:
    *   将当前的 `<textarea>` 替换为 `<ReactQuill>` 组件。
    *   修改 `content` 状态的更新逻辑，以处理 `react-quill` 生成的 HTML 字符串。

3.  **修改公告展示页面 (`AnnouncementsPage.jsx`)**:
    *   为了正确显示富文本内容，需要找到渲染公告内容的部分。
    *   使用 React 的 `dangerouslySetInnerHTML` 属性来将存储的 HTML 字符串渲染为实际的 DOM 元素。这是展示富文本内容的标准做法。

## 4. 风险与对策

*   **XSS 攻击风险**: 由于我们会直接渲染用户（管理员）输入的 HTML，存在跨站脚本（XSS）攻击的风险。
*   **对策**: 在这个项目中，我们假设发布公告的管理员是可信的。在更广泛的应用中，我们会引入 HTML 清理库（如 `dompurify`）来过滤掉恶意的脚本标签，确保安全。对于当前任务，我们将暂时不实现清理，但会在计划中注明。