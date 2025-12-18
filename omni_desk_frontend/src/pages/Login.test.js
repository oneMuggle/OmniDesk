import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
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
    renderWithRouter(<Login />);
    fireEvent.click(screen.getByRole('button', { name: /登 录/i }));
    expect(await screen.findByText('请输入用户名和密码')).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('should handle successful login and navigation', async () => {
    mockLogin.mockResolvedValue({ success: true, redirectTo: '/dashboard' });
    renderWithRouter(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password' } });
    fireEvent.click(screen.getByRole('button', { name: /登 录/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /登录中.../i })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'password', false);
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('should handle failed login and display error message', async () => {
    const error = '用户名或密码错误';
    mockLogin.mockRejectedValue(new Error(error));
    renderWithRouter(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'wronguser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'wrongpassword' } });
    fireEvent.click(screen.getByRole('button', { name: /登 录/i }));

    expect(await screen.findByText(error)).toBeInTheDocument();
    expect(mockLogin).toHaveBeenCalledWith('wronguser', 'wrongpassword', false);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('should pass rememberMe flag correctly when checked', async () => {
    mockLogin.mockResolvedValue({ success: true });
    renderWithRouter(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password' } });
    fireEvent.click(screen.getByLabelText('记住我'));
    fireEvent.click(screen.getByRole('button', { name: /登 录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'password', true);
    });
  });

  it('should handle guest login successfully', async () => {
    mockLoginAsGuest.mockResolvedValue({ success: true });
    renderWithRouter(<Login />);

    fireEvent.click(screen.getByRole('button', { name: /以游客身份访问/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /正在进入.../i })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(mockLoginAsGuest).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('should handle failed guest login', async () => {
    const error = '游客登录失败';
    mockLoginAsGuest.mockResolvedValue({ success: false, error });
    renderWithRouter(<Login />);

    fireEvent.click(screen.getByRole('button', { name: /以游客身份访问/i }));

    expect(await screen.findByText(error)).toBeInTheDocument();
    expect(mockLoginAsGuest).toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});