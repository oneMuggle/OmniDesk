import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import Login from './Login';
import { login } from '../api/userManagementApi';
import { AuthProvider } from '../context/AuthContext';

jest.mock('../api/userManagementApi', () => ({
  login: jest.fn(),
}));

const renderWithAuthProvider = (component) => {
  return render(
    <MemoryRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </MemoryRouter>
  );
};

describe('Login Component', () => {
  beforeEach(() => {
    login.mockClear();
  });

  it('should render login form', () => {
    renderWithAuthProvider(<Login />);
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登 录/i })).toBeInTheDocument();
  });

  it('should show error message on failed login', async () => {
    login.mockResolvedValue({ success: false, error: 'Invalid credentials' });
    renderWithAuthProvider(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'wronguser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'wrongpassword' } });
    fireEvent.click(screen.getByRole('button', { name: /登 录/i }));

    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument();
  });

  it('should not show error when login is successful', async () => {
    login.mockResolvedValue({ success: true });
    renderWithAuthProvider(<Login />);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password' } });
    fireEvent.click(screen.getByRole('button', { name: /登 录/i }));

    await waitFor(() => {
      expect(login).toHaveBeenCalled();
      expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument();
    });
  });
});