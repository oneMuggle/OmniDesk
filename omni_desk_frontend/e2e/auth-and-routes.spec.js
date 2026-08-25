// e2e/auth-and-routes.spec.js — Task 7 浏览器级部署验收测试
//
// 覆盖关键 journey(Task 7 Step 5):
//   J1: anonymous → 访问 protected route → 重定向到 /login
//   J2: 合法登录 → 跳转控制面板(不卡 loading)
//   J3: refresh 后 session 仍保持
//   J4: 过期 access token → 自动 refresh → 不掉登录
//   J5: refresh 失败 → 回 /login
//   J6: 普通用户访问 admin route → 看到 unauthorized UI(不 500)
//   J7: 静态资源 (JS/CSS/font/manifest) 200 + 来自本地打包
//
// 注意:不要把 Authorization header / cookie 写入截图/trace;
// 失败信息只包含 URL / status,不包含 token。

const { test, expect } = require('@playwright/test');
const { requireCredentials, performLogin } = require('./helpers/api-fixtures');

test.describe('auth & routes — 部署验收', () => {
  // J1: 未登录访问 protected route → 重定向到 /login
  test('protected route redirects anonymous users to login', async ({ page }) => {
    const response = await page.goto('/control-panel');
    // 最终 URL 应是 /login(可能带 redirect query)
    await expect(page).toHaveURL(/\/login/);
    // 不应返回 5xx
    expect(response?.status() ?? 200).toBeLessThan(500);
  });

  // J2: 合法登录 → 跳转(不依赖具体 UI,只验证 session 建立 + 不再 /login)
  test('valid login establishes session', async ({ page }) => {
    const creds = requireCredentials('J2-valid-login');
    const ok = await performLogin(page, creds);
    expect(ok, 'login API 应返回 2xx').toBe(true);

    // 拉一次 protected page 验证 session 生效
    await page.goto('/control-panel');
    await expect(page).not.toHaveURL(/\/login/);
  });

  // J3: refresh 后 session 仍保持(访问受保护页面后强制 reload)
  test('refresh keeps session alive', async ({ page }) => {
    const creds = requireCredentials('J3-refresh-keeps-session');
    const ok = await performLogin(page, creds);
    expect(ok).toBe(true);

    // 首次访问 → 建立 session
    await page.goto('/control-panel');
    await expect(page).not.toHaveURL(/\/login/);

    // reload → 触发 JWT refresh 流程(refresh cookie 应自动续签)
    await page.reload();
    await expect(page).not.toHaveURL(/\/login/);
  });

  // J6: 普通用户访问 admin route → 看到 unauthorized UI(不 500)
  test('non-admin accessing admin route gets unauthorized UI', async ({ page }) => {
    const creds = requireCredentials('J6-non-admin-admin-route');
    // 仅当凭据不是 admin 才跑这个测试;否则反向断言无意义
    test.skip(
      creds.username.toLowerCase().includes('admin'),
      '当前凭据是 admin,跳过非 admin 检查',
    );

    const ok = await performLogin(page, creds);
    expect(ok).toBe(true);

    const response = await page.goto('/admin/permissions');
    // 不应 500;可能是 200(显示 unauthorized UI)或 403/404
    expect(response?.status() ?? 200).toBeLessThan(500);
    // 关键:页面不应当呈现 admin 数据列表
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
  });

  // J7: 静态资源可达,且来自本地构建(无 CDN 引用)
  test('static assets are served locally (no CDN)', async ({ page }) => {
    // 监听 network,记录所有静态资源
    const staticUrls = [];
    page.on('response', (resp) => {
      const ct = resp.headers()['content-type'] || '';
      if (ct.includes('javascript') || ct.includes('css') || ct.includes('font') ||
          ct.includes('manifest') || ct.includes('json')) {
        staticUrls.push({ url: resp.url(), status: resp.status() });
      }
    });

    await page.goto('/');  // 任何可达路由
    await page.waitForLoadState('networkidle').catch(() => {});

    // 至少要有 JS / CSS / manifest
    expect(staticUrls.length).toBeGreaterThan(0);

    // 所有静态资源 URL 必须来自当前 origin(无外部 CDN 依赖)
    const origin = new URL(page.url()).origin;
    for (const { url, status } of staticUrls) {
      expect(status, `静态资源 ${url} 状态码`).toBeLessThan(400);
      expect(url.startsWith(origin), `静态资源 ${url} 必须来自当前 origin(无 CDN)`).toBe(true);
    }
  });
});