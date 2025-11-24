import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter as Router } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import Register from './Register';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const mockRegister = jest.fn();

const renderWithAuth = (ui, { providerProps, ...renderOptions }) => {
  return render(
    <AuthContext.Provider value={providerProps}>
      <Router>{ui}</Router>
    </AuthContext.Provider>,
    renderOptions
  );
};

describe('Register Component', () => {
  let providerProps;

  beforeEach(() => {
    providerProps = {
      register: mockRegister,
    };
    mockRegister.mockClear();
    mockNavigate.mockClear();
  });

  test('renders register form correctly', () => {
    renderWithAuth(<Register />, { providerProps });
    expect(screen.getByRole('heading', { name: /注册/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('确认密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /注册/i })).toBeInTheDocument();
    expect(screen.getByText(/已有账号？/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /立即登录/i })).toBeInTheDocument();
  });

  test('allows user to enter registration details', () => {
    renderWithAuth(<Register />, { providerProps });
    const usernameInput = screen.getByPlaceholderText('用户名');
    const passwordInput = screen.getByPlaceholderText('密码');
    const confirmPasswordInput = screen.getByPlaceholderText('确认密码');

    fireEvent.change(usernameInput, { target: { value: 'newuser' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'password123' } });

    expect(usernameInput.value).toBe('newuser');
    expect(passwordInput.value).toBe('password123');
    expect(confirmPasswordInput.value).toBe('password123');
  });

  test('shows error message if passwords do not match', async () => {
    renderWithAuth(<Register />, { providerProps });
    const passwordInput = screen.getByPlaceholderText('密码');
    const confirmPasswordInput = screen.getByPlaceholderText('确认密码');
    const registerButton = screen.getByRole('button', { name: /注册/i });

    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'password456' } });
    fireEvent.click(registerButton);

    expect(await screen.findByText('密码和确认密码不一致')).toBeInTheDocument();
    expect(mockRegister).not.toHaveBeenCalled();
  });

  test('calls register function on form submission and redirects on success', async () => {
    mockRegister.mockResolvedValue({ success: true });
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith('newuser', 'password123', 'password123');
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login', {
        state: { registeredUsername: 'newuser' },
      });
    });
  });

  test('shows error message on registration failure', async () => {
    mockRegister.mockResolvedValue({ success: false, errors: { username: ['用户名已存在'] } });
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'existinguser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    expect(await screen.findByText('用户名已存在')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('navigates to login page when "立即登录" link is clicked', () => {
    renderWithAuth(<Register />, { providerProps });
    const loginLink = screen.getByRole('link', { name: /立即登录/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  test('trims whitespace from username and password before registration', async () => {
    mockRegister.mockResolvedValue({ success: true });
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: '  newuser  ' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: '  password123  ' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: '  password123  ' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith('newuser', 'password123', 'password123');
    });
  });

  test('disables button and shows loading text during registration', async () => {
    // Use a promise that doesn't resolve immediately to check the loading state
    const promise = new Promise(resolve => {});
    mockRegister.mockReturnValue(promise);
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /注册中.../i })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /注册中.../i })).toBeDisabled();
  });

  test('shows non_field_errors on registration failure', async () => {
    mockRegister.mockResolvedValue({ success: false, errors: { non_field_errors: ['Invalid data provided.'] } });
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    expect(await screen.findByText('Invalid data provided.')).toBeInTheDocument();
  });

  test('shows detail error on registration failure', async () => {
    mockRegister.mockResolvedValue({ success: false, errors: { detail: 'Authentication credentials were not provided.' } });
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    expect(await screen.findByText('Authentication credentials were not provided.')).toBeInTheDocument();
  });

  test('shows default error message on registration failure with unknown error format', async () => {
    mockRegister.mockResolvedValue({ success: false, errors: {} });
    renderWithAuth(<Register />, { providerProps });

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    expect(await screen.findByText('注册失败')).toBeInTheDocument();
  });
});