import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UserManagementPage from './UserManagementPage';
import userManagementApi from '../api/userManagementApi';
import { getAllPersonnel } from '../../personnel/api/personnelApi';
import { permissionsApi } from '../../../shared/api/permissionsApi';
import { AuthContext } from '../../auth/context/AuthContext';

// 1. 在文件顶部 Mock 整个 API 模块
jest.mock('../api/userManagementApi');
jest.mock('../../personnel/api/personnelApi');
jest.mock('../../../shared/api/permissionsApi');

// 2. 将 Mock 函数转换为 jest.Mock 类型
const mockedGetAllUsers = jest.mocked(userManagementApi.getAllUsers);
const mockedCreateUser = jest.mocked(userManagementApi.createUser);
const mockedUpdateUser = jest.mocked(userManagementApi.updateUser);
const mockedDeleteUser = jest.mocked(userManagementApi.deleteUser);
const mockedGetAllPersonnel = jest.mocked(getAllPersonnel);
const mockedGetGroups = jest.mocked(permissionsApi.getGroups);

const mockUser = { id: 1, username: 'test-admin', is_superuser: true };

const renderPage = () => {
  return render(
    <AuthContext.Provider value={{ user: mockUser, isAuthenticated: true, isGuest: false, hasPermission: () => true }}>
      <UserManagementPage />
    </AuthContext.Provider>
  );
};

describe('UserManagementPage', () => {
  let mockUsers;
  let mockGroups;

  // 3. 使用 beforeEach 处理公共设置
  beforeEach(() => {
    // 重置所有 mock
    jest.clearAllMocks();

    mockUsers = [
      { id: 1, username: 'user.one', email: 'user.one@example.com', groups: [] },
      { id: 2, username: 'user.two', email: 'user.two@example.com', groups: [] },
    ];

    mockGroups = [
      { id: 101, name: 'Admin' },
      { id: 102, name: 'Editor' },
    ];

    // 为 API 提供默认的成功解析值
    mockedGetAllUsers.mockResolvedValue({ data: { results: mockUsers } });
    mockedGetAllPersonnel.mockResolvedValue([]);
    mockedGetGroups.mockResolvedValue({ results: mockGroups });
    mockedCreateUser.mockImplementation(newUser => 
      Promise.resolve({ data: { id: Date.now(), ...newUser, groups: [] } })
    );
    mockedUpdateUser.mockImplementation((id, updatedUser) =>
      Promise.resolve({ data: { id, ...updatedUser } })
    );
    mockedDeleteUser.mockResolvedValue({ status: 204 });
  });

  it('should render the initial list of users', async () => {
    renderPage();
    expect(await screen.findByText('user.one')).toBeInTheDocument();
    expect(await screen.findByText('user.two')).toBeInTheDocument();
  });

  it('should allow creating a new user', async () => {
    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /create user/i }));

    await user.type(screen.getByLabelText(/username/i), 'new.user');
    await user.type(screen.getByLabelText(/email/i), 'new.user@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');

    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(mockedCreateUser).toHaveBeenCalledWith(expect.objectContaining({
        username: 'new.user',
        email: 'new.user@example.com',
      }));
    });

    expect(await screen.findByText('new.user')).toBeInTheDocument();
  });

  it('should allow editing an existing user', async () => {
    renderPage();
    const user = userEvent.setup();

    // 等待初始用户列表加载完成
    await screen.findByText('user.one');

    const editButtons = await screen.findAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    const emailInput = screen.getByLabelText(/email/i);
    await user.clear(emailInput);
    await user.type(emailInput, 'user.one.updated@example.com');

    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(mockedUpdateUser).toHaveBeenCalledWith(1, expect.objectContaining({
        email: 'user.one.updated@example.com',
      }));
    });
    
    // 重新获取以确保UI已更新
    mockedGetAllUsers.mockResolvedValue({ data: { results: [
      { id: 1, username: 'user.one', email: 'user.one.updated@example.com', groups: [] },
      ...mockUsers.slice(1)
    ]}});
    
    // 触发重新获取的逻辑，例如关闭模态框后
    // 在实际应用中，这通常由组件的内部状态管理触发
    // 这里我们直接验证更新后的文本是否出现
    expect(await screen.findByText('user.one.updated@example.com')).toBeInTheDocument();
  });

  it('should allow deleting a user', async () => {
    window.confirm = jest.fn(() => true); // Mock confirm dialog
    renderPage();
    const user = userEvent.setup();

    await screen.findByText('user.one');

    const deleteButtons = await screen.findAllByRole('button', { name: /delete/i });
    await user.click(deleteButtons[0]);

    expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to delete this user?');
    
    await waitFor(() => {
      expect(mockedDeleteUser).toHaveBeenCalledWith(1);
    });

    await waitFor(() => {
      expect(screen.queryByText('user.one')).not.toBeInTheDocument();
    });
  });

  it('should filter the user list based on search input', async () => {
    renderPage();
    const user = userEvent.setup();

    await screen.findByText('user.one');

    const searchInput = screen.getByPlaceholderText(/search users/i);
    await user.type(searchInput, 'user.two');

    expect(screen.queryByText('user.one')).not.toBeInTheDocument();
    expect(screen.getByText('user.two')).toBeInTheDocument();
  });

  it('should allow assigning permissions when editing a user', async () => {
    renderPage();
    const user = userEvent.setup();

    await screen.findByText('user.one');

    const editButtons = await screen.findAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    // 假设权限是以复选框的形式存在的
    await user.click(screen.getByLabelText(/editor/i));

    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(mockedUpdateUser).toHaveBeenCalledWith(1, expect.objectContaining({
        groups: [102], // 'Editor' group ID
      }));
    });
  });
});