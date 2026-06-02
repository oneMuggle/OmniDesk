/* eslint-env node, jest */
import { permissionsApi } from './permissionsApi';
import apiClient from './apiClient';

jest.mock('./apiClient', () => ({
  get: jest.fn(),
}));

describe('permissionsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  describe('getGroups', () => {
    it('should get all groups via apiClient', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });
      await permissionsApi.getGroups();
      expect(apiClient.get).toHaveBeenCalledWith('/permissions/groups/');
    });
  });

  describe('getPermissions', () => {
    it('should get current user permissions', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ permissions: [] }),
          status: 200,
        })
      );
      await permissionsApi.getMyPermissions();
      expect(fetch).toHaveBeenCalledWith('/api/permissions/users/me/permissions/', expect.any(Object));
    });
  });

  describe('getPageTree', () => {
    it('should get permission tree', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ tree: [] }),
          status: 200,
        })
      );
      await permissionsApi.getPageTree();
      expect(fetch).toHaveBeenCalledWith('/api/permissions/pages/', expect.any(Object));
    });
  });

  describe('createGroup', () => {
    it('should create a group', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 1, name: 'New Group' }),
          status: 201,
        })
      );
      const result = await permissionsApi.createGroup({ name: 'New Group' });
      expect(fetch).toHaveBeenCalledWith('/api/permissions/groups/', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'New Group' }),
      }));
      expect(result.name).toBe('New Group');
    });
  });

  describe('updateGroup', () => {
    it('should update a group', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 1, name: 'Updated' }),
          status: 200,
        })
      );
      const result = await permissionsApi.updateGroup(1, { name: 'Updated' });
      expect(fetch).toHaveBeenCalledWith('/api/permissions/groups/1/', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ name: 'Updated' }),
      }));
      expect(result.name).toBe('Updated');
    });
  });

  describe('deleteGroup', () => {
    it('should delete a group with 204 response', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 204,
        })
      );
      const result = await permissionsApi.deleteGroup(1);
      expect(fetch).toHaveBeenCalledWith('/api/permissions/groups/1/', expect.objectContaining({
        method: 'DELETE',
      }));
      expect(result).toBeNull();
    });
  });

  describe('getGroupPermissions', () => {
    it('should get group permissions', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ permissions: [1, 2] }),
          status: 200,
        })
      );
      const result = await permissionsApi.getGroupPermissions(1);
      expect(fetch).toHaveBeenCalledWith('/api/permissions/groups/1/permissions/', expect.any(Object));
      expect(result.permissions).toEqual([1, 2]);
    });
  });

  describe('updateGroupPermissions', () => {
    it('should update group permissions', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
          status: 200,
        })
      );
      await permissionsApi.updateGroupPermissions(1, [1, 2, 3]);
      expect(fetch).toHaveBeenCalledWith('/api/permissions/groups/1/permissions/', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ permissions: [1, 2, 3] }),
      }));
    });
  });
});
