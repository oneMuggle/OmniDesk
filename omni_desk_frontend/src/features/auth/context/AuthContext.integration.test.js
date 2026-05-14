/**
 * AuthContext integration tests — full auth flows with mocked HTTP layer.
 *
 * Unlike Login.test.js / Register.test.js (which mock useAuth), these tests
 * exercise the real AuthContext logic while intercepting axios calls.
 */
import { useContext } from 'react';
import { render, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PropTypes from 'prop-types';

// ── Mock axios module ──────────────────────────────────────────────────────
const mockPost = jest.fn();
const mockGet = jest.fn();

jest.mock('../../../shared/api/axiosConfig.js', () => ({
  post: (...args) => mockPost(...args),
  get: (...args) => mockGet(...args),
  defaults: { baseURL: 'http://127.0.0.1:8000/api/' },
  interceptors: {
    request: { use: jest.fn(), eject: jest.fn() },
    response: { use: jest.fn(), eject: jest.fn() },
  },
}));

jest.mock('../../../shared/api/pageConfigApi', () => ({
  getAllPageConfigs: jest.fn().mockResolvedValue({ data: [] }),
}));

jest.mock('../../../shared/utils/logger', () => ({
  logger: { error: jest.fn(), info: jest.fn() },
}));

// Import after mocking
import { AuthProvider, AuthContext } from './AuthContext';

// ── Test helper ────────────────────────────────────────────────────────────
const ContextConsumer = ({ onContext }) => {
  const value = useContext(AuthContext);
  onContext(value);
  return null;
};
ContextConsumer.propTypes = { onContext: PropTypes.func.isRequired };

const renderWithProvider = async () => {
  let ctx;
  await act(async () => {
    render(
      <AuthProvider>
        <ContextConsumer onContext={(v) => { ctx = v; }} />
      </AuthProvider>,
    );
  });
  return {
    getContext: () => ctx,
  };
};

// ── Tests ──────────────────────────────────────────────────────────────────
describe('AuthContext Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('full login flow: credentials → tokens → user profile (sessionStorage)', async () => {
    mockPost.mockResolvedValueOnce({
      data: { access: 'jwt-abc', refresh: 'jwt-refresh-abc' },
    });
    mockGet.mockResolvedValueOnce({
      data: { username: 'testuser', email: 't@t.com', permissions: [] },
    });

    const { getContext } = await renderWithProvider();
    const result = await getContext().login('testuser', 'password');

    expect(result.success).toBe(true);
    expect(result.redirectTo).toBe('/');
    expect(sessionStorage.getItem('authTokens')).toContain('jwt-abc');
    expect(localStorage.getItem('authTokens')).toBeNull();

    await waitFor(() => {
      expect(getContext().user?.username).toBe('testuser');
    });
  });

  it('login with rememberMe stores in localStorage', async () => {
    mockPost.mockResolvedValueOnce({
      data: { access: 'jwt-abc', refresh: 'jwt-refresh-abc' },
    });
    mockGet.mockResolvedValueOnce({
      data: { username: 'testuser', email: 't@t.com', permissions: [] },
    });

    const { getContext } = await renderWithProvider();
    await getContext().login('testuser', 'password', true);

    await waitFor(() => {
      expect(getContext().user).not.toBeNull();
    });
    expect(localStorage.getItem('authTokens')).toContain('jwt-abc');
    expect(sessionStorage.getItem('authTokens')).toBeNull();
  });

  it('login failure returns error object', async () => {
    mockPost.mockRejectedValueOnce({
      response: { data: { detail: '用户名或密码错误' } },
    });

    const { getContext } = await renderWithProvider();
    const result = await getContext().login('wrong', 'wrong');

    expect(result.success).toBe(false);
    expect(result.error).toBe('用户名或密码错误');
  });

  it('registration success returns redirect message', async () => {
    mockPost.mockResolvedValueOnce({
      status: 201,
      data: { username: 'newuser', user: { id: 1 } },
    });

    const { getContext } = await renderWithProvider();
    const result = await getContext().register({
      username: 'newuser',
      password: 'pass123',
      password_confirmation: 'pass123',
    });

    expect(result.success).toBe(true);
    expect(result.message).toBe('注册成功，请登录');
  });

  it('registration failure returns validation errors', async () => {
    mockPost.mockRejectedValueOnce({
      response: {
        data: { validation_errors: { username: ['A user with that username already exists.'] } },
      },
    });

    const { getContext } = await renderWithProvider();
    const result = await getContext().register({
      username: 'existing',
      password: 'pass123',
      password_confirmation: 'pass123',
    });

    expect(result.success).toBe(false);
    expect(result.errors).toHaveProperty('validation_errors');
  });

  it('guest login flow: creates guest → gets tokens → sets isGuest', async () => {
    mockPost.mockResolvedValueOnce({
      data: { access: 'guest-jwt', refresh: 'guest-refresh', is_guest: true },
    });
    mockGet.mockResolvedValueOnce({
      data: { username: 'guest_abc123', email: '', permissions: [] },
    });

    const { getContext } = await renderWithProvider();
    const result = await getContext().loginAsGuest();

    expect(result.success).toBe(true);
    expect(sessionStorage.getItem('authTokens')).toContain('guest-jwt');

    await waitFor(() => {
      expect(getContext().user?.username).toBe('guest_abc123');
      expect(getContext().isGuest).toBe(true);
    });
  });

  it('logout clears all storage and resets state', async () => {
    mockPost.mockResolvedValueOnce({
      data: { access: 'jwt-abc', refresh: 'jwt-refresh-abc' },
    });
    mockGet.mockResolvedValueOnce({
      data: { username: 'testuser', email: 't@t.com', permissions: [] },
    });

    const { getContext } = await renderWithProvider();
    await getContext().login('testuser', 'password');

    await waitFor(() => {
      expect(getContext().user).not.toBeNull();
    });
    expect(sessionStorage.getItem('authTokens')).toBeTruthy();

    act(() => { getContext().logout(); });

    expect(localStorage.getItem('authTokens')).toBeNull();
    expect(sessionStorage.getItem('authTokens')).toBeNull();
    expect(localStorage.getItem('userPermissions')).toBeNull();
    expect(sessionStorage.getItem('userPermissions')).toBeNull();
  });

  it('initialization from stored tokens on mount', async () => {
    sessionStorage.setItem(
      'authTokens',
      JSON.stringify({ access: 'stored-jwt', refresh: 'stored-refresh' }),
    );
    mockGet.mockResolvedValueOnce({
      data: { username: 'storeduser', email: 's@t.com', permissions: ['read'] },
    });

    const { getContext } = await renderWithProvider();

    await waitFor(() => {
      expect(getContext().user?.username).toBe('storeduser');
    });
    expect(getContext().isAuthenticated).toBe(true);
  });

  it('clears tokens when stored token returns 401 on init', async () => {
    sessionStorage.setItem(
      'authTokens',
      JSON.stringify({ access: 'expired-jwt', refresh: 'expired-refresh' }),
    );
    mockGet.mockRejectedValueOnce({ response: { status: 401 } });

    const { getContext } = await renderWithProvider();

    await waitFor(() => {
      expect(getContext().user).toBeNull();
    });
    expect(sessionStorage.getItem('authTokens')).toBeNull();
    expect(localStorage.getItem('authTokens')).toBeNull();
  });
});
