import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import PropTypes from 'prop-types';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Login from './Login';
import { useAuth } from '../context/AuthContext';

// Mock the AuthContext
jest.mock('../context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const mockLogin = jest.fn();
const mockLoginAsGuest = jest.fn();
const mockNavigate = jest.fn();

// Mock useNavigate
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

// Wrapper to provide future flags context from React Router
const MemoryRouterWrapper = ({ children }) => (
  <MemoryRouter>
    <Routes>
      <Route path="*" element={children} />
    </Routes>
  </MemoryRouter>
);

MemoryRouterWrapper.propTypes = {
  children: PropTypes.node.isRequired,
};

const renderWithRouter = (ui) => {
  return render(ui, { wrapper: MemoryRouterWrapper });
};

describe('Login Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuth.mockReturnValue({
      login: mockLogin,
      loginAsGuest: mockLoginAsGuest,
    });
  });

  it('should render login form correctly', () => {
    renderWithRouter(<Login />);
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登 录/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /以游客身份访问/i })).toBeInTheDocument();
  });

  it('should display an error if login is attempted with empty credentials', async () => {
    const user = userEvent.setup();
    renderWithRouter(<Login />);
    await user.click(screen.getByRole('button', { name: /登 录/i }));
    // Ant Design Form shows individual field validation errors
    await waitFor(() => {
      expect(screen.getByText('请输入用户名')).toBeInTheDocument();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('should handle successful login and navigation', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue({ success: true, redirectTo: '/dashboard' });
    renderWithRouter(<Login />);

    await user.type(screen.getByPlaceholderText('用户名'), 'testuser');
    await user.type(screen.getByPlaceholderText('密码'), 'password');
    await user.click(screen.getByRole('button', { name: /登 录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'password', undefined);
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('should handle failed login and display error message', async () => {
    const user = userEvent.setup();
    const error = '用户名或密码错误';
    mockLogin.mockRejectedValue(new Error(error));
    renderWithRouter(<Login />);

    await user.type(screen.getByPlaceholderText('用户名'), 'wronguser');
    await user.type(screen.getByPlaceholderText('密码'), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /登 录/i }));

    await waitFor(() => {
      expect(screen.getByText(error)).toBeInTheDocument();
    });
    expect(mockLogin).toHaveBeenCalledWith('wronguser', 'wrongpassword', undefined);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('should pass rememberMe flag correctly when checked', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue({ success: true });
    renderWithRouter(<Login />);

    await user.type(screen.getByPlaceholderText('用户名'), 'testuser');
    await user.type(screen.getByPlaceholderText('密码'), 'password');
    await user.click(screen.getByLabelText('记住我'));
    await user.click(screen.getByRole('button', { name: /登 录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'password', true);
    });
  });

  it('should handle guest login successfully', async () => {
    const user = userEvent.setup();
    mockLoginAsGuest.mockResolvedValue({ success: true });
    renderWithRouter(<Login />);

    await user.click(screen.getByRole('button', { name: /以游客身份访问/i }));

    await waitFor(() => {
      expect(mockLoginAsGuest).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('should handle failed guest login', async () => {
    const user = userEvent.setup();
    const error = '游客登录失败';
    mockLoginAsGuest.mockResolvedValue({ success: false, error });
    renderWithRouter(<Login />);

    await user.click(screen.getByRole('button', { name: /以游客身份访问/i }));

    await waitFor(() => {
      expect(screen.getByText(error)).toBeInTheDocument();
    });
    expect(mockLoginAsGuest).toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});