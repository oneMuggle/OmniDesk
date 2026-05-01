import { getEquipment, createEquipment, updateEquipment, deleteEquipment } from './equipment';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
}));

describe('equipmentApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getEquipment', () => {
    it('should get equipment without params', async () => {
      apiClient.get.mockResolvedValue({
        data: { results: [], count: 0, current_page: 1, page_size: 10 },
      });
      const result = await getEquipment();
      expect(apiClient.get).toHaveBeenCalledWith('events/equipments/', {
        params: { page: undefined, pageSize: undefined },
      });
      expect(result.data).toEqual([]);
    });

    it('should get equipment with pagination', async () => {
      apiClient.get.mockResolvedValue({
        data: { results: [{ id: 1 }], count: 5, current_page: 2, page_size: 2 },
      });
      const result = await getEquipment({ page: 2, pageSize: 2 });
      expect(apiClient.get).toHaveBeenCalledWith('events/equipments/', {
        params: { page: 2, page_size: 2 },
      });
      expect(result.pagination.total).toBe(5);
    });
  });

  describe('createEquipment', () => {
    it('should create equipment', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, name: 'Device A' } });
      const result = await createEquipment({ name: 'Device A' });
      expect(apiClient.post).toHaveBeenCalledWith('events/equipments/', { name: 'Device A' });
      expect(result.name).toBe('Device A');
    });
  });

  describe('updateEquipment', () => {
    it('should partial update equipment', async () => {
      apiClient.patch.mockResolvedValue({ data: { id: 1, name: 'Updated' } });
      const result = await updateEquipment(1, { name: 'Updated' });
      expect(apiClient.patch).toHaveBeenCalledWith('events/equipments/1/', { name: 'Updated' });
      expect(result.name).toBe('Updated');
    });
  });

  describe('deleteEquipment', () => {
    it('should delete equipment', async () => {
      apiClient.delete.mockResolvedValue({});
      const result = await deleteEquipment(1);
      expect(apiClient.delete).toHaveBeenCalledWith('events/equipments/1/');
      expect(result.success).toBe(true);
    });
  });
});
