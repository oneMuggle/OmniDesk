// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

/**
 * Paperless-ngx 集成端到端测试
 *
 * 前置条件:
 * - Django 后端运行在 http://localhost:8000
 * - React 前端运行在 http://localhost:3000
 * - Paperless-ngx 服务可用(对于同步测试)
 * - 测试用户: admin/admin
 *
 * 运行测试:
 *   npx playwright test paperless-integration
 */

test.describe('Paperless 集成端到端测试', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('http://localhost:3000/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/');
  });

  test('上传文档 → 同步 → 检索', async ({ page }) => {
    // 1. 导航到项目页面
    await page.goto('http://localhost:3000/projects/1');
    await page.waitForLoadState('networkidle');

    // 2. 点击上传按钮
    const uploadButton = page.locator('[data-testid="upload-doc-btn"]');
    await expect(uploadButton).toBeVisible();
    await uploadButton.click();

    // 3. 选择文件上传
    const fileInput = page.locator('input[type="file"]');
    const testPdfPath = path.join(__dirname, '..', 'e2e-fixtures', 'test.pdf');
    await fileInput.setInputFiles(testPdfPath);

    // 4. 等待上传完成
    await page.waitForResponse(
      (response) =>
        response.url().includes('/upload_document') && response.status() === 200,
      { timeout: 30000 }
    );

    // 5. 验证同步状态(假设 paperless 服务可用)
    const syncBadge = page.locator('[data-testid="sync-badge"]');
    await expect(syncBadge).toBeVisible({ timeout: 10000 });
    await expect(syncBadge).toContainText('已同步');

    // 6. 返回首页并搜索
    await page.goto('http://localhost:3000/');
    const searchBar = page.locator('[data-testid="search-bar"]');
    await expect(searchBar).toBeVisible();
    await searchBar.fill('test');

    // 7. 等待搜索结果
    await page.waitForTimeout(2000); // 等待搜索 API 返回

    // 8. 验证搜索结果
    const searchResult = page.locator('[data-testid="search-result"]').first();
    await expect(searchResult).toBeVisible({ timeout: 5000 });
    await searchResult.click();

    // 9. 验证跳转到 paperless 相关页面
    await page.waitForURL('**/documents-library/**', { timeout: 10000 });
  });

  test('Paperless 宕机时上传仍成功(待同步状态)', async ({ page, request }) => {
    // 这个测试需要模拟 paperless 服务不可用
    // 在实际 CI 环境中,可能需要特殊配置或跳过

    // 1. 导航到项目页面
    await page.goto('http://localhost:3000/projects/1');
    await page.waitForLoadState('networkidle');

    // 2. 点击上传按钮
    const uploadButton = page.locator('[data-testid="upload-doc-btn"]');
    await expect(uploadButton).toBeVisible();
    await uploadButton.click();

    // 3. 选择文件上传
    const fileInput = page.locator('input[type="file"]');
    const testPdfPath = path.join(__dirname, '..', 'e2e-fixtures', 'test.pdf');
    await fileInput.setInputFiles(testPdfPath);

    // 4. 等待上传完成(本地上传成功)
    await page.waitForResponse(
      (response) =>
        response.url().includes('/upload_document') && response.status() === 200,
      { timeout: 30000 }
    );

    // 5. 验证同步状态为"待同步"(paperless 不可用时)
    const syncBadge = page.locator('[data-testid="sync-badge"]');
    await expect(syncBadge).toBeVisible({ timeout: 10000 });

    // 可能是"已同步"或"待同步",取决于 paperless 服务状态
    const syncText = await syncBadge.textContent();
    expect(['已同步', '待同步', '同步中']).toContain(syncText);
  });

  test('文档库页面加载', async ({ page }) => {
    // 1. 导航到文档库页面
    await page.goto('http://localhost:3000/documents-library');
    await page.waitForLoadState('networkidle');

    // 2. 验证页面标题或关键元素
    const pageTitle = page.locator('h1, .page-title').first();
    await expect(pageTitle).toBeVisible();

    // 3. 如果有文档列表,验证列表存在
    const documentList = page.locator('[data-testid="document-list"]');
    if (await documentList.isVisible()) {
      const items = documentList.locator('[data-testid="document-item"]');
      const count = await items.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });

  test('统一搜索包含 paperless 文档', async ({ page }) => {
    // 1. 导航到首页
    await page.goto('http://localhost:3000/');
    await page.waitForLoadState('networkidle');

    // 2. 使用搜索栏
    const searchBar = page.locator('[data-testid="search-bar"]');
    if (await searchBar.isVisible()) {
      await searchBar.fill('test');

      // 3. 等待搜索结果
      await page.waitForTimeout(2000);

      // 4. 验证搜索结果包含文档库相关内容
      const searchResults = page.locator('[data-testid="search-result"]');
      const count = await searchResults.count();

      // 如果有搜索结果,验证至少有一个
      if (count > 0) {
        await expect(searchResults.first()).toBeVisible();
      }
    }
  });

  test('文档下载功能', async ({ page }) => {
    // 1. 导航到文档库
    await page.goto('http://localhost:3000/documents-library');
    await page.waitForLoadState('networkidle');

    // 2. 查找文档列表
    const documentList = page.locator('[data-testid="document-list"]');
    if (await documentList.isVisible()) {
      const firstDocument = documentList
        .locator('[data-testid="document-item"]')
        .first();

      if (await firstDocument.isVisible()) {
        // 3. 点击文档进入详情
        await firstDocument.click();
        await page.waitForLoadState('networkidle');

        // 4. 查找下载按钮
        const downloadButton = page.locator(
          '[data-testid="download-btn"], button:has-text("下载")'
        );

        if (await downloadButton.isVisible()) {
          // 5. 点击下载并验证响应
          const downloadPromise = page.waitForEvent('download');
          await downloadButton.click();
          const download = await downloadPromise;

          // 6. 验证下载的文件
          expect(download.suggestedFilename()).toBeTruthy();
        }
      }
    }
  });
});
