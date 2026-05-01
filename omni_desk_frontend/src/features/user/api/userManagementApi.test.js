import userManagementApi from './userManagementApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  patch: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

describe('userManagementApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should get all users', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    await userManagementApi.getAllUsers();
    expect(apiClient.get).toHaveBeenCalledWith('users/control-panel/');
  });

  it('should associate user with personnel', async () => {
    apiClient.patch.mockResolvedValue({ data: { id: 1 } });
    await userManagementApi.associateUserWithPersonnel(1, 2);
    expect(apiClient.patch).toHaveBeenCalledWith('users/control-panel/1/', { personnel_id: 2 });
  });

  it('should create a user', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
    await userManagementApi.createUser({ username: 'test' });
    expect(apiClient.post).toHaveBeenCalledWith('users/control-panel/', { username: 'test' });
  });

  it('should update a user', async () => {
    apiClient.patch.mockResolvedValue({ data: { id: 1 } });
    await userManagementApi.updateUser(1, { real_name: 'Updated' });
    expect(apiClient.patch).toHaveBeenCalledWith('users/control-panel/1/', { real_name: 'Updated' });
  });

  it('should update user groups', async () => {
    apiClient.patch.mockResolvedValue({ data: { id: 1 } });
    await userManagementApi.updateUserGroups(1, [1, 2]);
    expect(apiClient.patch).toHaveBeenCalledWith('users/control-panel/1/', { groups: [1, 2] });
  });

  it('should delete a user', async () => {
    apiClient.delete.mockResolvedValue({});
    await userManagementApi.deleteUser(1);
    expect(apiClient.delete).toHaveBeenCalledWith('users/control-panel/1/');
  });

  it('should get groups', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    await userManagementApi.getGroups();
    expect(apiClient.get).toHaveBeenCalledWith('permissions/groups/');
  });

  it('should get grouped permissions', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    await userManagementApi.getGroupedPermissions();
    expect(apiClient.get).toHaveBeenCalledWith('permissions/permissions/grouped/');
  });

  it('should get group permissions', async () => {
    apiClient.get.mockResolvedValue({ data: { permissions: [] } });
    await userManagementApi.getGroupPermissions(1);
    expect(apiClient.get).toHaveBeenCalledWith('permissions/groups/1/permissions/');
  });

  it('should update group permissions', async () => {
    apiClient.put.mockResolvedValue({ data: { permissions: [] } });
    await userManagementApi.updateGroupPermissions(1, ['read', 'write']);
    expect(apiClient.put).toHaveBeenCalledWith('permissions/groups/1/permissions/', { permissions: ['read', 'write'] });
  });
});
