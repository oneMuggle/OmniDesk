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
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.getByLabelText('确认密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /注册/i })).toBeInTheDocument();
    expect(screen.getByText(/已有账号？/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /立即登录/i })).toBeInTheDocument();
  });

  test('allows user to enter registration details', () => {
    renderWithAuth(<Register />, { providerProps });
    const usernameInput = screen.getByPlaceholderText('用户名');
    const passwordInput = screen.getByLabelText('密码');
    const confirmPasswordInput = screen.getByLabelText('确认密码');

    fireEvent.change(usernameInput, { target: { value: 'newuser' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'password123' } });

    expect(usernameInput.value).toBe('newuser');
    expect(passwordInput.value).toBe('password123');
    expect(confirmPasswordInput.value).toBe('password123');
  });

  test('shows error message if passwords do not match', async () => {
    renderWithAuth(<Register />, { providerProps });
    const passwordInput = screen.getByLabelText('密码');
    const confirmPasswordInput = screen.getByLabelText('确认密码');
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
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'password123' } });
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
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    expect(await screen.findByText('用户名已存在')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('navigates to login page when "立即登录" link is clicked', () => {
    renderWithAuth(<Register />, { providerProps });
    const loginLink = screen.getByRole('link', { name: /立即登录/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });
});