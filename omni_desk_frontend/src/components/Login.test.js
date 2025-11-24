import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter as Router } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import Login from './Login';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const mockLogin = jest.fn();
const mockLoginAsGuest = jest.fn();

const renderWithAuth = (ui, { providerProps, ...renderOptions }) => {
  return render(
    <AuthContext.Provider value={providerProps}>
      <Router>{ui}</Router>
    </AuthContext.Provider>,
    renderOptions
  );
};

describe('Login Component', () => {
  let providerProps;

  beforeEach(() => {
    providerProps = {
      login: mockLogin,
      loginAsGuest: mockLoginAsGuest,
    };
    mockLogin.mockClear();
    mockLoginAsGuest.mockClear();
    mockNavigate.mockClear();
  });

  test('renders login form correctly', () => {
    renderWithAuth(<Login />, { providerProps });
    expect(screen.getByRole('heading', { name: /登录/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /记住我/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /以游客身份访问/i })).toBeInTheDocument();
    expect(screen.getByText(/没有账号？/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /立即注册/i })).toBeInTheDocument();
  });

  test('allows user to enter username and password', () => {
    renderWithAuth(<Login />, { providerProps });
    const usernameInput = screen.getByPlaceholderText('用户名');
    const passwordInput = screen.getByLabelText('密码');

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    expect(usernameInput.value).toBe('testuser');
    expect(passwordInput.value).toBe('password123');
  });

  test('allows user to check "remember me"', () => {
    renderWithAuth(<Login />, { providerProps });
    const rememberMeCheckbox = screen.getByRole('checkbox', { name: /记住我/i });

    fireEvent.click(rememberMeCheckbox);
    expect(rememberMeCheckbox.checked).toBe(true);
  });

  test('shows error message if username or password is not provided', async () => {
    renderWithAuth(<Login />, { providerProps });
    const loginButton = screen.getByRole('button', { name: /登录/i });

    fireEvent.click(loginButton);

    expect(await screen.findByText('请输入用户名和密码')).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  test('calls login function on form submission and redirects on success', async () => {
    mockLogin.mockResolvedValue({ success: true, redirectTo: '/dashboard' });
    renderWithAuth(<Login />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'password123', false);
    });
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  test('shows error message on login failure', async () => {
    mockLogin.mockResolvedValue({ success: false, error: '无效的凭证' });
    renderWithAuth(<Login />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'wronguser' } });
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'wrongpass' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    expect(await screen.findByText('无效的凭证')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('calls loginAsGuest and redirects on success', async () => {
    mockLoginAsGuest.mockResolvedValue({ success: true });
    renderWithAuth(<Login />, { providerProps });

    const guestButton = screen.getByRole('button', { name: /以游客身份访问/i });
    fireEvent.click(guestButton);

    await waitFor(() => {
      expect(mockLoginAsGuest).toHaveBeenCalled();
    });
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  test('shows error message on guest login failure', async () => {
    mockLoginAsGuest.mockResolvedValue({ success: false, error: '游客登录已禁用' });
    renderWithAuth(<Login />, { providerProps });

    const guestButton = screen.getByRole('button', { name: /以游客身份访问/i });
    fireEvent.click(guestButton);

    expect(await screen.findByText('游客登录已禁用')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('navigates to register page when "立即注册" link is clicked', () => {
    renderWithAuth(<Login />, { providerProps });
    const registerLink = screen.getByRole('link', { name: /立即注册/i });
    expect(registerLink).toHaveAttribute('href', '/register');
  });
});