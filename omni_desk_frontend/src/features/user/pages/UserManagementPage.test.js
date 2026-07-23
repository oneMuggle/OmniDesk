import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UserManagementPage from './UserManagementPage';
import userManagementApi from '../api/userManagementApi';
import { getAllPersonnel } from '../../personnel/api/personnelApi';
import { permissionsApi } from '../../../shared/api/permissionsApi';
import { AuthContext } from '../../auth/context/AuthContext';

// Mock the logger — component uses logger.warn for edit/delete
jest.mock('../../../shared/utils/logger', () => ({
  logger: { warn: jest.fn(), error: jest.fn(), info: jest.fn() },
}));
import { logger } from '../../../shared/utils/logger';

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
      { id: 1, username: 'user.one', email: 'user.one@example.com', groups: [], permissions: { can_change: true, can_delete: true } },
      { id: 2, username: 'user.two', email: 'user.two@example.com', groups: [], permissions: { can_change: true, can_delete: true } },
    ];

    mockGroups = [
      { id: 101, name: 'Admin' },
      { id: 102, name: 'Editor' },
    ];
  });

  const setupMocks = () => {
    mockedGetAllUsers.mockResolvedValue({ data: { results: mockUsers } });
    mockedGetAllPersonnel.mockResolvedValue({ data: { results: [] } });
    mockedGetGroups.mockResolvedValue({ data: { results: mockGroups } });
    mockedCreateUser.mockImplementation(newUser =>
      Promise.resolve({ data: { id: Date.now(), ...newUser, groups: [] } })
    );
    mockedUpdateUser.mockImplementation((id, updatedUser) =>
      Promise.resolve({ data: { id, ...updatedUser } })
    );
    mockedDeleteUser.mockResolvedValue({ status: 204 });
  };

  it('should render the initial list of users', async () => {
    setupMocks();
    renderPage();
    await screen.findByText('user.one');
    expect(screen.getByText('user.two')).toBeInTheDocument();
  });


  it('should call the edit user logger when the edit button is clicked', async () => {
    setupMocks();
    renderPage();
    await screen.findByText('user.one');
    const user = userEvent.setup();

    const editButtons = screen.getAllByTestId('edit-user-button');
    await user.click(editButtons[0]);

    expect(logger.warn).toHaveBeenCalledWith('Edit user handler not implemented', 1);
  });

  it('should call the delete user logger when the delete button is clicked', async () => {
    setupMocks();
    renderPage();
    await screen.findByText('user.one');
    const user = userEvent.setup();

    const deleteButtons = screen.getAllByTestId('delete-user-button');
    await user.click(deleteButtons[0]);

    expect(logger.warn).toHaveBeenCalledWith('Delete user handler not implemented', 1);
  });

});