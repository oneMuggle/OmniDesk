// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Playwright E2E 测试配置
 * 用于 paperless-ngx 集成的端到端测试
 *
 * 运行测试:
 *   npx playwright test
 *
 * 运行特定测试文件:
 *   npx playwright test paperless-integration
 *
 * 查看测试报告:
 *   npx playwright show-report
 */
module.exports = defineConfig({
  testDir: './e2e',
  /* 最大并行数 */
  fullyParallel: true,
  /* CI 环境下禁止 test.only */
  forbidOnly: !!process.env.CI,
  /* 失败重试次数 */
  retries: process.env.CI ? 2 : 0,
  /* 并发工作进程数 */
  workers: process.env.CI ? 1 : undefined,
  /* 测试报告器 */
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  /* 全局配置 */
  use: {
    /* 基础 URL */
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    /* 收集失败测试的 trace */
    trace: 'on-first-retry',
    /* 截图策略 */
    screenshot: 'only-on-failure',
    /* 视频录制 */
    video: 'retain-on-failure',
  },
  /* 项目配置 */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  /* Web 服务器配置(可选) */
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm start',
        url: 'http://localhost:3000',
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
      },
});
