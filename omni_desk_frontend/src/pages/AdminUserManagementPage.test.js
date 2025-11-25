import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AdminUserManagementPage from './AdminUserManagementPage';
import userManagementApi from '../api/userManagementApi';
import pageConfigApi from '../api/pageConfigApi';
import { useAuth } from '../context/AuthContext';

jest.mock('../api/userManagementApi');
jest.mock('../api/pageConfigApi');
jest.mock('../context/AuthContext');

const mockUsers = {
  data: {
    results: [
      { id: 1, username: 'admin', email: 'admin@example.com', role: 'admin', date_joined: '2023-01-01T00:00:00Z' },
      { id: 2, username: 'testuser', email: 'test@example.com', role: 'user', date_joined: '2023-01-02T00:00:00Z' },
    ],
  },
};

const mockPageConfigs = {
  data: {
    results: [
      { page_name: 'Home', page_path: '/', is_hidden_for_non_admin: false },
      { page_name: 'Admin', page_path: '/admin', is_hidden_for_non_admin: true },
    ],
  },
};

const mockCurrentUser = {
  id: 1,
  username: 'admin',
  role: 'admin',
};

describe('AdminUserManagementPage', () => {
  beforeEach(() => {
    useAuth.mockReturnValue({ user: mockCurrentUser });
    userManagementApi.getAllUsers.mockResolvedValue(mockUsers);
    pageConfigApi.getAllPageConfigs.mockResolvedValue(mockPageConfigs);
    userManagementApi.updateUserRole.mockResolvedValue({});
    pageConfigApi.updatePageConfig.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders user and page config tables with data', async () => {
    render(<AdminUserManagementPage />);

    await waitFor(() => {
      expect(screen.getByText('管理员面板')).toBeInTheDocument();
    });

    expect(await screen.findByText('admin')).toBeInTheDocument();
    expect(await screen.findByText('testuser')).toBeInTheDocument();
    expect(await screen.findByText('Home')).toBeInTheDocument();
    expect(await screen.findByText('Admin')).toBeInTheDocument();
  });

  test('handles user role change', async () => {
    render(<AdminUserManagementPage />);

    await waitFor(() => {
        expect(screen.getByText('testuser')).toBeInTheDocument();
    });

    const roleSelect = screen.getAllByRole('combobox')[0];
    fireEvent.mouseDown(roleSelect);
    const option = await screen.findByText('经理');
    fireEvent.click(option);

    await waitFor(() => {
      expect(userManagementApi.updateUserRole).toHaveBeenCalledWith(2, 'manager');
    });
  });

  test('handles page visibility change', async () => {
    render(<AdminUserManagementPage />);

    await waitFor(() => {
        expect(screen.getByText('Home')).toBeInTheDocument();
    });

    const visibilitySwitch = screen.getAllByRole('switch')[0];
    fireEvent.click(visibilitySwitch);

    await waitFor(() => {
      expect(pageConfigApi.updatePageConfig).toHaveBeenCalledWith('/', { is_hidden_for_non_admin: true });
    });
  });

  test('disables role change for current user', async () => {
    render(<AdminUserManagementPage />);

    await waitFor(() => {
        expect(screen.getByText('admin')).toBeInTheDocument();
    });
    
    const adminRoleSelect = screen.getAllByRole('combobox')[1];
    expect(adminRoleSelect.hasAttribute('disabled')).toBe(true);
  });
});