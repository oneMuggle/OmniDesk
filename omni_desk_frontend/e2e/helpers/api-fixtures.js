// e2e/helpers/api-fixtures.js — Task 7 共享 fixtures
//
// 提供:
//   - getCredentials():从 E2E_USERNAME/PASSWORD 或 guest fixture 取凭据
//   - requireCredentials():无凭据时 fail 而非 skip(部署验收要求)
//   - performLogin(page, creds):走真实 /api/auth/login flow,不 mock Axios
//
// 注意:不写入 logs / screenshots / traces 中敏感字段;Authorization header
// 由 Playwright 内部上下文管理,不进 trace。

/**
 * @typedef {Object} Credentials
 * @property {string} username
 * @property {string} password
 */

/**
 * 读取凭据。优先级:E2E_USERNAME/PASSWORD env > guest fixture(测试用)。
 * @returns {Credentials|null} null 表示无凭据可用
 */
function getCredentials() {
  if (process.env.E2E_USERNAME && process.env.E2E_PASSWORD) {
    return {
      username: process.env.E2E_USERNAME,
      password: process.env.E2E_PASSWORD,
    };
  }
  // guest fixture(部署测试机预置的弱口令账号,用于部署 smoke)
  if (process.env.E2E_AUTH_MODE === 'guest') {
    return { username: 'smoketest', password: 'smoketest-pass-2026' };
  }
  return null;
}

/**
 * 强制要求凭据存在。无凭据时抛错使测试 fail(部署验收要求不允许 skip)。
 * @param {string} testName
 * @returns {Credentials}
 */
function requireCredentials(testName) {
  const creds = getCredentials();
  if (!creds) {
    throw new Error(
      `[${testName}] 需要 E2E_USERNAME/E2E_PASSWORD 或 E2E_AUTH_MODE=guest — 无凭据不可部署验收`,
    );
  }
  return creds;
}

/**
 * 走真实登录流程。失败时返回 false 而非抛错(让测试选择处理方式)。
 * @param {import('@playwright/test').Page} page
 * @param {Credentials} creds
 * @returns {Promise<boolean>}
 */
async function performLogin(page, creds) {
  // 后端登录端点:返回 access + refresh JWT
  const response = await page.request.post('/api/auth/login/', {
    data: { username: creds.username, password: creds.password },
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok()) {
    return false;
  }
  // 后端会通过 Set-Cookie 下发 access + refresh;
  // Playwright request context 自动维护 cookie,page.goto 后续请求自动带上。
  return true;
}

module.exports = {
  getCredentials,
  requireCredentials,
  performLogin,
};