// e2e/helpers/api-fixtures.js — Task 7 共享 fixtures
//
// 提供:
//   - getCredentials():从 E2E_USERNAME/PASSWORD 或 E2E_USER_USERNAME/PASSWORD
//     或 guest fixture(E2E_GUEST_USERNAME/PASSWORD)取"普通用户"凭据(优先级从高到低)
//   - getUserCredentials():从 E2E_USER_USERNAME/PASSWORD 或 guest fixture
//     取"普通用户"凭据(用于需要显式普通用户的断言,如 J6)
//   - requireCredentials():无凭据时 fail 而非 skip(部署验收要求)
//   - performLogin(page, creds):走真实 /api/auth/login flow,不 mock Axios
//
// 注意:不写入 logs / screenshots / traces 中敏感字段;Authorization header
// 由 Playwright 内部上下文管理,不进 trace。所有凭据必须从 secrets 注入,
// 禁止硬编码。

/**
 * @typedef {Object} Credentials
 * @property {string} username
 * @property {string} password
 */

/**
 * 读取"普通用户"凭据。优先级:
 *   1. E2E_USERNAME/PASSWORD(传统 env,所有测试通用)
 *   2. E2E_USER_USERNAME/PASSWORD(Task 8 引入的显式普通用户变量)
 *   3. E2E_GUEST_USERNAME/PASSWORD(deployment 注入的 guest 凭据,
 *      仅当 E2E_AUTH_MODE=guest 时启用;两变量均须存在,缺一即拒)
 * @returns {Credentials|null} null 表示无凭据可用
 */
function getCredentials() {
  if (process.env.E2E_USERNAME && process.env.E2E_PASSWORD) {
    return {
      username: process.env.E2E_USERNAME,
      password: process.env.E2E_PASSWORD,
    };
  }
  if (process.env.E2E_USER_USERNAME && process.env.E2E_USER_PASSWORD) {
    return {
      username: process.env.E2E_USER_USERNAME,
      password: process.env.E2E_USER_PASSWORD,
    };
  }
  if (process.env.E2E_AUTH_MODE === 'guest') {
    return _getGuestCredentialsOrNull('getCredentials');
  }
  return null;
}

/**
 * 读取"普通用户"凭据的专用版本。仅从 E2E_USER_USERNAME/PASSWORD 或
 * guest fixture 解析,不接受传统 E2E_USERNAME/PASSWORD。
 *
 * 用途:J6 等需要"明确是普通用户"断言的场景。禁止再用
 * username.includes('admin') 之类的关键字做 skip 判定。
 *
 * @returns {Credentials|null}
 */
function getUserCredentials() {
  if (process.env.E2E_USER_USERNAME && process.env.E2E_USER_PASSWORD) {
    return {
      username: process.env.E2E_USER_USERNAME,
      password: process.env.E2E_USER_PASSWORD,
    };
  }
  if (process.env.E2E_AUTH_MODE === 'guest') {
    return _getGuestCredentialsOrNull('getUserCredentials');
  }
  return null;
}

/**
 * Guest 凭据必须来自 secrets(E2E_GUEST_USERNAME/E2E_GUEST_PASSWORD),
 * 两变量同时存在才返回凭据;任一缺失即抛错而非返回弱口令占位。
 * @param {string} source 供错误信息定位调用方
 * @returns {Credentials}
 */
function _getGuestCredentialsOrNull(source) {
  const u = process.env.E2E_GUEST_USERNAME;
  const p = process.env.E2E_GUEST_PASSWORD;
  if (u && p) {
    return { username: u, password: p };
  }
  throw new Error(
    `[${source}] E2E_AUTH_MODE=guest 但 E2E_GUEST_USERNAME/E2E_GUEST_PASSWORD 未注入 — 禁止硬编码弱口令`,
  );
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
      `[${testName}] 需要 E2E_USERNAME/E2E_PASSWORD、E2E_USER_USERNAME/E2E_USER_PASSWORD 或 E2E_AUTH_MODE=guest(且 E2E_GUEST_USERNAME/E2E_GUEST_PASSWORD 已注入) — 无凭据不可部署验收`,
    );
  }
  return creds;
}

/**
 * 强制要求"普通用户"凭据存在。无凭据时抛错。
 * @param {string} testName
 * @returns {Credentials}
 */
function requireUserCredentials(testName) {
  const creds = getUserCredentials();
  if (!creds) {
    throw new Error(
      `[${testName}] 需要 E2E_USER_USERNAME/E2E_USER_PASSWORD 或 E2E_AUTH_MODE=guest(且 E2E_GUEST_USERNAME/E2E_GUEST_PASSWORD 已注入) — 无显式普通用户凭据不可做角色化断言`,
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
  const response = await page.request.post('/api/auth/login/', {
    data: { username: creds.username, password: creds.password },
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok()) {
    return false;
  }

  const data = await response.json();
  if (typeof data.access !== 'string' || typeof data.refresh !== 'string') {
    return false;
  }

  const authTokens = JSON.stringify({
    access: data.access,
    refresh: data.refresh,
  });
  await page.addInitScript((tokens) => {
    window.sessionStorage.setItem('authTokens', tokens);
  }, authTokens);
  return true;
}

module.exports = {
  getCredentials,
  getUserCredentials,
  requireCredentials,
  requireUserCredentials,
  performLogin,
};