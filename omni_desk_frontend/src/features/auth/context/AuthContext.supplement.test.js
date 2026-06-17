/* eslint-disable react-hooks/set-state-in-effect */
/**
 * AuthContext 补充测试：login、logout、register、loginAsGuest、pageConfigs 等。
 */

import React, { useContext, useEffect, useState } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider, AuthContext } from './AuthContext';

// --- Mocks ---

jest.mock('../../../shared/api/axiosConfig.js', () => ({
  post: jest.fn(),
  get: jest.fn(),
  defaults: { baseURL: '/api/' },
}));

jest.mock('../../../shared/api/pageConfigApi', () => ({
  getAllPageConfigs: jest.fn(),
}));

jest.mock('../../../shared/utils/logger', () => ({
  logger: { error: jest.fn() },
}));

import apiClient from '../../../shared/api/axiosConfig';
import pageConfigApi from '../../../shared/api/pageConfigApi';

const apiClientMock = apiClient;
const pageConfigApiMock = pageConfigApi;

// --- Helper Components ---

const AuthActionTrigger = ({ action }) => {
  const ctx = useContext(AuthContext);
  const [result, setResult] = useState(null);

  useEffect(() => {
    const run = async () => {
      const res = await action(ctx);
      setResult(JSON.stringify(res));
    };
    run();
  }, [action, ctx]);

  return result ? <div data-testid="result">{result}</div> : <div>loading</div>;
};

const ContextConsumer = ({ capture }) => {
  const ctx = useContext(AuthContext);
  useEffect(() => { capture(ctx); }, [ctx, capture]);
  return null;
};

const SetUserAndCheck = ({ user, permission, testId }) => {
  const { setUser, hasPermission } = useContext(AuthContext);
  const [result, setResult] = useState(null);
  useEffect(() => {
    setUser(user);
    setResult(hasPermission(permission) ? 'Allowed' : 'Denied');
  }, [setUser, hasPermission, user, permission]);
  return result ? <div data-testid={testId}>{result}</div> : null;
};

const renderWithContext = (ui) => {
  return render(<AuthProvider>{ui}</AuthProvider>);
};

// --- Tests ---

describe('AuthProvider - login', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('login 成功时应设置用户和 tokens', async () => {
    apiClientMock.post.mockImplementation((url) => {
      if (url === 'auth/login/') {
        return Promise.resolve({
          data: {
            access: 'new-access',
            refresh: 'new-refresh',
            permissions: ['admin'],
          },
        });
      }
      if (url === 'users/me/') {
        return Promise.resolve({ data: { username: 'testuser', is_superuser: false } });
      }
      return Promise.reject(new Error('unknown'));
    });
    pageConfigApiMock.getAllPageConfigs.mockResolvedValue({ data: [] });

    const action = async (ctx) => ctx.login('testuser', 'pass123', true);

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      expect(screen.getByTestId('result')).toHaveTextContent('success');
    });

    expect(localStorage.getItem('authTokens')).toContain('new-access');
  });

  it('login 失败应返回 success: false', async () => {
    apiClientMock.post.mockRejectedValue({
      response: { data: { detail: '用户名或密码错误' } },
    });

    const action = async (ctx) => ctx.login('wronguser', 'wrongpass');

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      const result = JSON.parse(screen.getByTestId('result').textContent);
      expect(result.success).toBe(false);
    });
  });
});

describe('AuthProvider - logout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    delete window.location;
    window.location = { href: '' };
  });

  it('logout 应清除所有存储', async () => {
    localStorage.setItem('authTokens', JSON.stringify({ access: 'token' }));
    localStorage.setItem('userPermissions', JSON.stringify(['admin']));

    let logoutFn;
    renderWithContext(
      <ContextConsumer capture={(ctx) => { logoutFn = ctx.logout; }} />
    );

    await act(async () => {
      logoutFn();
    });

    expect(localStorage.getItem('authTokens')).toBeNull();
    expect(localStorage.getItem('userPermissions')).toBeNull();
    expect(sessionStorage.getItem('authTokens')).toBeNull();
  });
});

describe('AuthProvider - loginAsGuest', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('guest 登录成功应设置 isGuest', async () => {
    apiClientMock.post.mockImplementation((url) => {
      if (url === 'auth/guest-login/') {
        return Promise.resolve({
          data: { access: 'guest-access', refresh: 'guest-refresh' },
        });
      }
      return Promise.reject(new Error('unknown'));
    });
    apiClientMock.get.mockResolvedValue({
      data: { username: 'guest_abc123', is_superuser: false },
    });
    pageConfigApiMock.getAllPageConfigs.mockResolvedValue({ data: [] });

    const action = async (ctx) => ctx.loginAsGuest();

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      expect(sessionStorage.getItem('authTokens')).toContain('guest-access');
    });
  });

  it('guest 登录失败应返回 success: false', async () => {
    apiClientMock.post.mockRejectedValue(new Error('network error'));

    const action = async (ctx) => ctx.loginAsGuest();

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      const result = JSON.parse(screen.getByTestId('result').textContent);
      expect(result.success).toBe(false);
    });
  });
});

describe('AuthProvider - register', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('注册成功应返回 success: true', async () => {
    apiClientMock.post.mockResolvedValue({
      status: 201,
      data: { username: 'newuser' },
    });

    const action = async (ctx) => ctx.register({
      username: 'newuser',
      password: 'Pass123',
      password_confirmation: 'Pass123',
    });

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      const result = JSON.parse(screen.getByTestId('result').textContent);
      expect(result.success).toBe(true);
    });
  });

  it('注册失败应返回错误信息', async () => {
    apiClientMock.post.mockRejectedValue({
      response: { data: { username: ['用户名已存在'] } },
    });

    const action = async (ctx) => ctx.register({
      username: 'existing',
      password: 'Pass123',
      password_confirmation: 'Pass123',
    });

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      const result = JSON.parse(screen.getByTestId('result').textContent);
      expect(result.success).toBe(false);
    });
  });
});

describe('AuthProvider - pageConfigs', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('登录成功后应获取 pageConfigs', async () => {
    apiClientMock.post.mockResolvedValue({
      data: { access: 'tok', refresh: 'ref', permissions: [] },
    });
    apiClientMock.get.mockResolvedValue({
      data: { username: 'testuser', is_superuser: false },
    });
    pageConfigApiMock.getAllPageConfigs.mockResolvedValue({
      data: [{ path: '/dashboard', visible: true }],
    });

    const action = async (ctx) => ctx.login('testuser', 'pass', true);

    renderWithContext(<AuthActionTrigger action={action} />);

    await waitFor(() => {
      expect(pageConfigApiMock.getAllPageConfigs).toHaveBeenCalled();
    });
  });
});

describe('AuthProvider - hasPermission edge cases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('guest 用户应可通过 group 权限访问页面', () => {
    renderWithContext(
      <SetUserAndCheck
        user={{ username: 'guest_abc', is_superuser: false, permissions: ['guest_page'] }}
        permission="guest_page"
        testId="guest-perm"
      />
    );

    expect(screen.getByTestId('guest-perm').textContent).toBe('Allowed');
  });
});
