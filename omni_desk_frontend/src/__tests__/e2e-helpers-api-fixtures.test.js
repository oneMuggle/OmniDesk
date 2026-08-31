/* eslint-env node */
// src/__tests__/e2e-helpers-api-fixtures.test.js
//
// 单元测试 e2e/helpers/api-fixtures.js
//
// 覆盖:
//   - getCredentials():优先级与 fallback
//   - requireCredentials():fail-closed 行为(无凭据抛错)
//   - performLogin():成功路径 + 各类失败路径 + addInitScript 调用语义
//
// 注意:jest.config.js 的 testPathIgnorePatterns 排除 /e2e/ 目录,
// 所以测试文件必须放在 src/__tests__/ 下,import 走 ../../e2e/...

const {
  getCredentials,
  getUserCredentials,
  requireCredentials,
  requireUserCredentials,
  performLogin,
} = require('../../e2e/helpers/api-fixtures');

// 隔离 env,避免其它测试残留影响
const ORIGINAL_ENV = { ...process.env };
afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
  jest.restoreAllMocks();
});

describe('getCredentials', () => {
  test('E2E_USERNAME/PASSWORD 优先于 guest fixture', () => {
    process.env.E2E_USERNAME = 'real_user';
    process.env.E2E_PASSWORD = 'real_pass';
    process.env.E2E_AUTH_MODE = 'guest';
    expect(getCredentials()).toEqual({ username: 'real_user', password: 'real_pass' });
  });

  test('无 env 凭据且 E2E_AUTH_MODE=guest + 注入 guest 凭据时返回 guest 凭据', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    process.env.E2E_AUTH_MODE = 'guest';
    process.env.E2E_GUEST_USERNAME = 'guest_user';
    process.env.E2E_GUEST_PASSWORD = 'guest_pass';
    expect(getCredentials()).toEqual({
      username: 'guest_user',
      password: 'guest_pass',
    });
  });

  test('E2E_AUTH_MODE=guest 但 E2E_GUEST_USERNAME 缺失时抛错(禁止硬编码弱口令)', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    process.env.E2E_AUTH_MODE = 'guest';
    delete process.env.E2E_GUEST_USERNAME;
    process.env.E2E_GUEST_PASSWORD = 'guest_pass';
    expect(() => getCredentials()).toThrow(/E2E_GUEST_USERNAME.*E2E_GUEST_PASSWORD/);
  });

  test('E2E_AUTH_MODE=guest 但 E2E_GUEST_PASSWORD 缺失时抛错', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    process.env.E2E_AUTH_MODE = 'guest';
    process.env.E2E_GUEST_USERNAME = 'guest_user';
    delete process.env.E2E_GUEST_PASSWORD;
    expect(() => getCredentials()).toThrow(/E2E_GUEST_USERNAME.*E2E_GUEST_PASSWORD/);
  });

  test('无 env 凭据且无 guest 时返回 null', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    delete process.env.E2E_AUTH_MODE;
    expect(getCredentials()).toBeNull();
  });

  test('E2E_PASSWORD 为空时仍视为无 env 凭据(回到 guest / null)', () => {
    process.env.E2E_USERNAME = 'partial_user';
    process.env.E2E_PASSWORD = '';
    delete process.env.E2E_AUTH_MODE;
    expect(getCredentials()).toBeNull();
  });

  test('E2E_USER_USERNAME/PASSWORD 是次优先级(传统 E2E_USERNAME/PASSWORD 缺失时)', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    process.env.E2E_USER_USERNAME = 'explicit_user';
    process.env.E2E_USER_PASSWORD = 'explicit_pass';
    expect(getCredentials()).toEqual({
      username: 'explicit_user',
      password: 'explicit_pass',
    });
  });
});

describe('getUserCredentials', () => {
  test('E2E_USER_USERNAME/PASSWORD 优先', () => {
    process.env.E2E_USER_USERNAME = 'role_user';
    process.env.E2E_USER_PASSWORD = 'role_pass';
    process.env.E2E_AUTH_MODE = 'guest';
    expect(getUserCredentials()).toEqual({ username: 'role_user', password: 'role_pass' });
  });

  test('E2E_AUTH_MODE=guest 且注入 guest 凭据时返回 guest 凭据', () => {
    delete process.env.E2E_USER_USERNAME;
    delete process.env.E2E_USER_PASSWORD;
    process.env.E2E_AUTH_MODE = 'guest';
    process.env.E2E_GUEST_USERNAME = 'guest_user';
    process.env.E2E_GUEST_PASSWORD = 'guest_pass';
    expect(getUserCredentials()).toEqual({
      username: 'guest_user',
      password: 'guest_pass',
    });
  });

  test('E2E_AUTH_MODE=guest 但 E2E_GUEST_* 缺失时抛错', () => {
    delete process.env.E2E_USER_USERNAME;
    delete process.env.E2E_USER_PASSWORD;
    process.env.E2E_AUTH_MODE = 'guest';
    delete process.env.E2E_GUEST_USERNAME;
    delete process.env.E2E_GUEST_PASSWORD;
    expect(() => getUserCredentials()).toThrow(/E2E_GUEST_USERNAME.*E2E_GUEST_PASSWORD/);
  });

  test('忽略传统 E2E_USERNAME/PASSWORD(防止 admin 凭据污染普通用户断言)', () => {
    process.env.E2E_USERNAME = 'admin_user';
    process.env.E2E_PASSWORD = 'admin_pass';
    delete process.env.E2E_USER_USERNAME;
    delete process.env.E2E_USER_PASSWORD;
    delete process.env.E2E_AUTH_MODE;
    expect(getUserCredentials()).toBeNull();
  });

  test('无任何凭据返回 null', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    delete process.env.E2E_USER_USERNAME;
    delete process.env.E2E_USER_PASSWORD;
    delete process.env.E2E_AUTH_MODE;
    expect(getUserCredentials()).toBeNull();
  });
});

describe('requireCredentials', () => {
  test('凭据存在时透传 getCredentials 结果', () => {
    process.env.E2E_USERNAME = 'real_user';
    process.env.E2E_PASSWORD = 'real_pass';
    expect(requireCredentials('test-name')).toEqual({
      username: 'real_user',
      password: 'real_pass',
    });
  });

  test('凭据缺失时抛 Error 并包含 testName(部署验收 fail-closed)', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    delete process.env.E2E_AUTH_MODE;
    expect(() => requireCredentials('J2-valid-login')).toThrow(/J2-valid-login/);
  });
});

describe('requireUserCredentials', () => {
  test('E2E_USER_* 存在时透传', () => {
    process.env.E2E_USER_USERNAME = 'role_user';
    process.env.E2E_USER_PASSWORD = 'role_pass';
    expect(requireUserCredentials('J6-role')).toEqual({
      username: 'role_user',
      password: 'role_pass',
    });
  });

  test('凭据缺失且无 guest 时抛 Error 并包含 testName', () => {
    delete process.env.E2E_USERNAME;
    delete process.env.E2E_PASSWORD;
    delete process.env.E2E_USER_USERNAME;
    delete process.env.E2E_USER_PASSWORD;
    delete process.env.E2E_AUTH_MODE;
    expect(() => requireUserCredentials('J6-role')).toThrow(/J6-role/);
  });
});

describe('performLogin', () => {
  // 通用 mock page:支持 request.post + addInitScript
  function makePage({ response }) {
    return {
      request: {
        post: jest.fn().mockResolvedValue(response),
      },
      addInitScript: jest.fn().mockResolvedValue(undefined),
    };
  }

  function okResponse(json) {
    return {
      ok: () => true,
      json: () => Promise.resolve(json),
    };
  }

  function failResponse() {
    return {
      ok: () => false,
      json: () => Promise.resolve({ detail: 'unauthorized' }),
    };
  }

  test('2xx + 合法 access/refresh → 返回 true 并注册 addInitScript 写入 sessionStorage.authTokens', async () => {
    const page = makePage({
      response: okResponse({ access: 'a-token', refresh: 'r-token' }),
    });
    // 隔离 jsdom sessionStorage,避免与其它测试相互污染
    window.sessionStorage.clear();
    const result = await performLogin(page, { username: 'u', password: 'p' });

    expect(result).toBe(true);
    expect(page.request.post).toHaveBeenCalledWith('/api/auth/login/', {
      data: { username: 'u', password: 'p' },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(page.addInitScript).toHaveBeenCalledTimes(1);
    const [scriptFn, payload] = page.addInitScript.mock.calls[0];
    expect(typeof scriptFn).toBe('function');
    expect(typeof payload).toBe('string');
    const parsed = JSON.parse(payload);
    expect(parsed).toEqual({ access: 'a-token', refresh: 'r-token' });
    // 关键:script body 应把 tokens 写入 sessionStorage.authTokens,
    // 与 AuthContext 的读取位置(sessionStorage / localStorage)对齐。
    // arrow function 内部用 window 词法引用,jest 的 jsdom 环境提供全局 window,
    // 直接调用 scriptFn 即可验证实际写入行为。
    scriptFn(payload);
    expect(window.sessionStorage.getItem('authTokens')).toBe(payload);
  });

  test('非 2xx → 返回 false 且不调用 addInitScript', async () => {
    const page = makePage({ response: failResponse() });
    const result = await performLogin(page, { username: 'u', password: 'p' });

    expect(result).toBe(false);
    expect(page.addInitScript).not.toHaveBeenCalled();
  });

  test('2xx 但响应体缺 access → 返回 false', async () => {
    const page = makePage({ response: okResponse({ refresh: 'r-only' }) });
    const result = await performLogin(page, { username: 'u', password: 'p' });

    expect(result).toBe(false);
    expect(page.addInitScript).not.toHaveBeenCalled();
  });

  test('2xx 但响应体缺 refresh → 返回 false', async () => {
    const page = makePage({ response: okResponse({ access: 'a-only' }) });
    const result = await performLogin(page, { username: 'u', password: 'p' });

    expect(result).toBe(false);
    expect(page.addInitScript).not.toHaveBeenCalled();
  });

  test('2xx 但 access 非字符串(例如 null) → 返回 false', async () => {
    const page = makePage({ response: okResponse({ access: null, refresh: 'r' }) });
    const result = await performLogin(page, { username: 'u', password: 'p' });

    expect(result).toBe(false);
    expect(page.addInitScript).not.toHaveBeenCalled();
  });

  test('request.post 抛出(网络错误) → 异常向外传播(调用方决定处理方式)', async () => {
    const page = {
      request: { post: jest.fn().mockRejectedValue(new Error('ECONNREFUSED')) },
      addInitScript: jest.fn(),
    };
    await expect(performLogin(page, { username: 'u', password: 'p' })).rejects.toThrow(
      /ECONNREFUSED/,
    );
    expect(page.addInitScript).not.toHaveBeenCalled();
  });
});