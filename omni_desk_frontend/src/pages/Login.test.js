import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import Login from './Login';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const mockLogin = jest.fn();
const mockLoginAsGuest = jest.fn();

describe('Login Component', () => {
  beforeEach(() => {
    mockLogin.mockClear();
    mockLoginAsGuest.mockClear();
    useAuth.mockReturnValue({
      login: mockLogin,
      loginAsGuest: mockLoginAsGuest,
    });
  });

  const renderInRouter = (component) => render(<MemoryRouter>{component}</MemoryRouter>);

  it('should render login form', () => {
    renderInRouter(<Login />);
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('should show error message on failed login', async () => {
    mockLogin.mockRejectedValue(new Error('登录失败'));
    renderInRouter(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'wronguser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'wrongpassword' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    expect(await screen.findByText('登录失败')).toBeInTheDocument();
    expect(mockLogin).toHaveBeenCalledWith('wronguser', 'wrongpassword', false);
  });

  it('should not show error when login is successful', async () => {
    mockLogin.mockResolvedValue({ success: true });
    renderInRouter(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'password', false);
    });

    expect(screen.queryByText(/登录失败/)).not.toBeInTheDocument();
  });
});