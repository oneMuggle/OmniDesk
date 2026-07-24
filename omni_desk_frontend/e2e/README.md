# Paperless-ngx 集成端到端测试

本目录包含 Paperless-ngx 集成的端到端(E2E)测试,使用 Playwright 框架。

## 测试场景

1. **上传文档 → 同步 → 检索**: 验证完整的文档上传、同步和搜索流程
2. **Paperless 宕机时上传仍成功**: 验证在 Paperless 服务不可用时,本地上传仍然成功(状态为"待同步")
3. **文档库页面加载**: 验证文档库页面正常加载
4. **统一搜索包含 paperless 文档**: 验证搜索功能包含 Paperless 文档
5. **文档下载功能**: 验证文档下载功能正常工作

## 前置条件

运行测试前,确保以下服务已启动:

- **Django 后端**: `http://localhost:8000`
- **React 前端**: `http://localhost:3000`
- **Paperless-ngx 服务**: (可选,用于同步测试)

测试用户: `admin` / `admin`

## 运行测试

### 运行所有 E2E 测试

```bash
npm run test:e2e
```

### 运行特定测试文件

```bash
npx playwright test paperless-integration
```

### 使用 UI 模式运行(调试)

```bash
npm run test:e2e:ui
```

### 查看测试报告

```bash
npm run test:e2e:report
```

## 测试文件

- `paperless-integration.spec.js` - Paperless 集成测试场景

## 测试固件

- `e2e-fixtures/test.pdf` - 用于上传测试的示例 PDF 文件

## 配置

Playwright 配置文件: `playwright.config.js`

主要配置项:
- `baseURL`: 前端 URL,默认 `http://localhost:3000`,可通过环境变量 `BASE_URL` 覆盖
- `testDir`: 测试文件目录 `./e2e`
- `retries`: CI 环境下失败重试 2 次,本地不重试
- `workers`: CI 环境下单进程,本地自动

## CI 集成

在 CI 环境中运行测试时,需要:

1. 启动 Django 后端服务
2. 启动 React 前端服务
3. (可选)启动 Paperless-ngx 服务

如果服务不可用,测试可能会失败。可以通过以下方式跳过特定测试:

```javascript
test.skip('test name', async ({ page }) => {
  // 测试代码
});
```

## 注意事项

- E2E 测试依赖真实的服务运行,不适合在每次提交时运行
- 建议在重大功能完成后运行完整 E2E 测试
- 单元测试( Jest)应该覆盖大部分功能,E2E 测试只覆盖关键用户流程
- 测试截图和视频仅在失败时保留

## 故障排查

### 测试失败:无法连接到前端

确保前端服务已启动:
```bash
npm start
```

### 测试失败:无法连接到后端

确保后端服务已启动:
```bash
cd ../
python manage.py runserver
```

### 测试失败:元素未找到

- 检查 `data-testid` 属性是否正确
- 使用 `npx playwright test --ui` 进行交互式调试
- 查看失败截图: `playwright-report/` 目录

### 浏览器安装失败

重新安装 Playwright 浏览器:
```bash
npx playwright install chromium
```

## 相关文档

- [Playwright 文档](https://playwright.dev/)
- [Paperless 集成计划](../../docs/plans/)
- [测试规范](../../CLAUDE.md#testing)
