// playwright.config.js — Task 7:浏览器级部署验收测试配置
//
// 目的:在真实 Nginx 端点上跑浏览器 E2E(不是 Vite dev server),
//      验证离线部署的 frontend 可访问性、auth 流、refresh、admin 权限。
//
// 环境变量:
//   E2E_BASE_URL   目标 URL(默认 http://localhost,生产环境传 nginx URL)
//   E2E_USERNAME   登录用户名
//   E2E_PASSWORD   登录密码
//   E2E_AUTH_MODE  'env'(默认,使用 E2E_USERNAME/PASSWORD) | 'guest'(测试 fixture 凭据)
//
// 输出路径:
//   所有 trace / screenshot / video → ../test-artifacts/screenshots/
//   (顶层路径,符合 OmniDesk 统一截图目录规范)

const path = require('path');

const ARTIFACT_ROOT = path.resolve(__dirname, '../test-artifacts/screenshots');

module.exports = {
  testDir: './e2e',
  // 默认 30s 超时,refresh/admin 检查给 60s
  timeout: 60_000,
  expect: { timeout: 10_000 },

  // 单 worker 串行(部署验收,无并发需求)
  workers: process.env.CI ? 1 : undefined,
  // CI 模式:重试 2 次以容忍偶发网络/启动延迟
  retries: process.env.CI ? 2 : 0,

  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(ARTIFACT_ROOT, 'html'), open: 'never' }],
    ['json', { outputFile: path.join(ARTIFACT_ROOT, 'results.json') }],
  ],

  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // 离线部署环境可能有自签证书/反向代理,容忍常见 SSL 错
    ignoreHTTPSErrors: true,
    // 不要在 trace/screenshot 中暴露 Authorization header / cookies
    // (默认就是不存,但显式声明)
  },

  // 不主动下载浏览器二进制(部署机可能已预装);缺失时报错而不是 silent skip
  // CI 模式下强制要求浏览器可用,验收不通过
  projects: [
    {
      name: 'chromium',
      use: {
        // 浏览器 binary 路径由部署机预装;Playwright 默认自动检测
      },
    },
  ],
};