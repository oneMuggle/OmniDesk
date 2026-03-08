# 前端测试指南 (Frontend Testing Guidelines)

本文档旨在统一前端团队的测试实践，确保测试代码的质量、可读性和可维护性。

## 1. 核心原则 (Core Principles)

- **以用户为中心 (User-Centric)**: 测试应尽可能模拟真实用户的交互行为。编写测试时，应思考用户如何与界面交互，而不是关心内部实现细节。
- **独立性 (Independence)**: 每个测试用例都应该是独立的，不依赖于其他测试用例的执行顺序或状态。使用 `beforeEach` 或 `afterEach` 来清理状态。
- **可维护性 (Maintainability)**: 测试代码应与业务代码一样被重视。保持其整洁、清晰，并随着功能的迭代而更新。避免因实现细节的微小变更导致大量测试失败。

## 2. 工具链 (Toolchain)

我们统一使用以下工具作为标准的测试技术栈：

- **[Jest](https://jestjs.io/)**: 一个功能强大的 JavaScript 测试框架，提供了测试运行器、断言库和 Mock 功能。
- **[@testing-library/react](https://testing-library.com/docs/react-testing-library/intro/)**: 提供了一套以用户为中心查询和交互的工具函数，鼓励编写更健壮的测试。
- **[@testing-library/user-event](https://testing-library.com/docs/user-event/intro)**: 模拟真实的用户浏览器事件，比 `fireEvent` 更贴近实际用户操作。

## 3. 选择器优先级 (Selector Priority)

为了编写与实现细节解耦的测试，请严格遵循以下选择器优先级顺序。目标是使用用户能够看到或交互的属性来查找元素。

1.  **`getByRole`**: 查找具有特定 ARIA 角色的元素，这是最具语义化的方式。例如，按钮 (`role="button"`)、链接 (`role="link"`)。
2.  **`getByLabelText`**: 查找与表单标签 (`<label>`) 关联的元素，非常适合表单输入。
3.  **`getByPlaceholderText`**: 查找具有特定占位符文本的元素。
4.  **`getByText`**: 查找包含特定文本内容的元素。
5.  **`getByDisplayValue`**: 查找表单元素当前显示的 `value`。

**应避免使用以下选择器：**

- **`getByTestId`**: 仅作为最后的备选方案。过度使用 `data-testid` 会使测试与实现细节紧密耦合，并且对用户没有任何实际价值。
- **CSS 选择器 (类名、ID)**: 这是最脆弱的选择方式，任何样式或结构的调整都可能破坏测试。

## 4. API Mocking 策略 (API Mocking Strategy)

统一的 API Mocking 是确保测试稳定性和可预测性的关键。

- **在最高层级 Mock (Mock at the Highest Level)**: 我们应该在测试文件的顶部，直接 Mock 整个封装好的 API 模块，而不是在每个测试用例中单独 Mock `fetch` 或 `axios`。

- **示例**:
  假设我们有一个 API 模块 `userManagementApi`，它封装了所有与用户管理相关的请求。

  ```javascript
  // src/features/user/api/userManagementApi.js
  import { api } from '@/shared/api/base';

  export const fetchUsers = () => api.get('/users');
  export const createUser = (newUser) => api.post('/users', newUser);
  ```

  在测试文件中，我们应该这样做：

  ```javascript
  // src/features/user/components/UserList.test.js
  import { render, screen, waitFor } from '@testing-library/react';
  import { userEvent } from '@testing-library/user-event';
  import { fetchUsers, createUser } from '@/features/user/api/userManagementApi';
  import UserList from './UserList';

  // 在文件顶部 Mock 整个模块
  jest.mock('@/features/user/api/userManagementApi');

  // 将 Mock 后的函数转换为 jest.Mock 类型，以便在测试中使用
  const mockedFetchUsers = jest.mocked(fetchUsers);
  const mockedCreateUser = jest.mocked(createUser);

  describe('UserList Component', () => {
    beforeEach(() => {
      // 在每个测试开始前重置 Mock
      mockedFetchUsers.mockClear();
      mockedCreateUser.mockClear();
    });

    it('should display users after fetching', async () => {
      const mockUsers = [{ id: 1, name: 'John Doe' }];
      // 为本次测试提供一个解析后的值
      mockedFetchUsers.mockResolvedValue(mockUsers);

      render(<UserList />);

      expect(await screen.findByText('John Doe')).toBeInTheDocument();
    });
  });
  ```

## 5. 测试结构 (Test Structure)

- **使用 `describe` 组织测试**: 将相关的测试用例组织在 `describe` 块中，以提高可读性。可以嵌套 `describe` 来组织更复杂的场景。
- **使用 `beforeEach` 处理公共设置**: 将组件渲染、API 模拟等重复性的设置代码放入 `beforeEach` 中，保持测试用例的简洁和专注。

```javascript
describe('MyComponent', () => {
  beforeEach(() => {
    // 在这里渲染组件或设置 Mock
    render(<MyComponent />);
  });

  it('should do something', () => {
    // 测试逻辑
  });

  it('should do something else', () => {
    // 测试逻辑
  });
});
```

## 6. 异步操作 (Asynchronous Operations)

现代前端应用充满了异步操作（如 API 请求、定时器）。处理不当会导致测试不稳定（"flaky tests"）。

- **总是使用 `async/await`**: 任何涉及异步行为的测试都必须是 `async` 函数。
- **使用 `findBy*` 查询**: 当你需要等待一个元素出现时，使用 `findBy*` 系列查询。它会等待一段时间直到元素出现或超时。
  ```javascript
  // 错误的方式
  // const element = getByText('Loaded'); // 可能会在数据加载完成前执行

  // 正确的方式
  const element = await screen.findByText('Loaded');
  ```
- **使用 `waitFor` 处理复杂场景**: 当你需要等待多个事件发生，或者等待某个断言变为真时，使用 `waitFor`。
  ```javascript
  await waitFor(() => {
    expect(screen.getByText('Status: Completed')).toBeInTheDocument();
  });