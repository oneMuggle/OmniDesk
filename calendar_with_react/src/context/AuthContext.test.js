import { render, screen, act } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import { MemoryRouter } from 'react-router-dom';

// 测试组件用来消费上下文
const TestComponent = () => {
  const { user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="user">{user?.username}</span>
      <button onClick={() => login('testuser', 'password')}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test('初始状态应为未登录', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </MemoryRouter>
    );
    
    expect(screen.getByTestId('user').textContent).toBe('');
  });

  test('成功登录应更新用户状态', async () => {
    const mockResponse = {
      access: 'mock-token',
      user: { username: 'testuser', email: 'test@example.com' }
    };
    
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </MemoryRouter>
    );

    await act(async () => {
      screen.getByText('Login').click();
    });

    expect(screen.getByTestId('user').textContent).toBe('testuser');
    expect(localStorage.getItem('token')).toBe('mock-token');
  });

  test('登录失败应保持未登录状态', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </MemoryRouter>
    );

    await act(async () => {
      screen.getByText('Login').click();
    });

    expect(screen.getByTestId('user').textContent).toBe('');
    expect(localStorage.getItem('token')).toBeNull();
  });

  test('登出应清除用户状态', async () => {
    localStorage.setItem('token', 'mock-token');
    
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </MemoryRouter>
    );

    await act(async () => {
      screen.getByText('Logout').click();
    });

    expect(screen.getByTestId('user').textContent).toBe('');
    expect(localStorage.getItem('token')).toBeNull();
  });
});
