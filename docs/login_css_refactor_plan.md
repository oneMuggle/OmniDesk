# **计划：将全局 `button` 样式限定在登录和注册组件中**

**目标**：将 `Login.css` 中的全局 `button` 样式修改为 `.login-button`，并更新 `Login.jsx` 和 `Register.jsx` 以使用这个新类，从而避免影响其他组件。

**步骤**：

1.  **修改 `Login.css`**：
    *   将 `button` 选择器重命名为 `.login-button`。
    *   将 `button:hover` 选择器重命名为 `.login-button:hover`。
    *   将 `button:disabled` 选择器重命名为 `.login-button:disabled`。
    *   将 `button::after` 选择器重命名为 `.login-button::after`。

2.  **修改 `Login.jsx`**：
    *   在 `Login.jsx` 中，为登录按钮添加 `className="login-button"`。

3.  **修改 `Register.jsx`**：
    *   在 `Register.jsx` 中，为注册按钮添加 `className="login-button"`。

**预期结果**：
*   登录和注册页面的按钮样式保持不变。
*   其他页面的按钮将不再受 `Login.css` 中定义的样式影响。

**Mermaid 序列图**:

```mermaid
sequenceDiagram
    participant A as Architect
    participant B as User
    participant C as CodeMode

    A->>B: 提出修改计划
    B-->>A: 同意计划
    A->>C: 请求切换到代码模式
    C->>C: 修改 Login.css
    C->>C: 修改 Login.jsx
    C->>C: 修改 Register.jsx
    C-->>B: 完成修改