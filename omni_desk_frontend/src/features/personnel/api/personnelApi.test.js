import {
  getPersonnel,
  getAllPersonnel,
  getPersonnelDetails,
  createPersonnel,
  updatePersonnel,
  deletePersonnel,
  getPositions,
  createPosition,
  updatePosition,
  deletePosition,
  getMyPersonnel,
  updateMyPersonnel,
} from './personnelApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient');

describe('personnelApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getPersonnel', () => {
    it('should fetch personnel with given params', async () => {
      const params = { page: 1 };
      const response = { data: { results: [{ id: 1, name: 'John Doe' }], count: 1, current_page: 1, page_size: 10 } };
      apiClient.get.mockResolvedValue(response);

      const result = await getPersonnel(params);

      expect(apiClient.get).toHaveBeenCalledWith('personnel/personnel/', { params });
      // 验证数据转换
      expect(result.data).toEqual(response.data.results);
      expect(result.pagination.total).toBe(response.data.count);
      expect(result.pagination.current).toBe(response.data.current_page);
      expect(result.pagination.pageSize).toBe(response.data.page_size);
    });
  });

  describe('getAllPersonnel', () => {
    it('should fetch all personnel', async () => {
      const response = { data: { results: [{ id: 1, name: 'John Doe' }] } };
      apiClient.get.mockResolvedValue(response);

      const result = await getAllPersonnel();

      expect(apiClient.get).toHaveBeenCalledWith('personnel/personnel/', { params: { page_size: 1000 } });
      expect(result).toEqual(response);
    });
  });

  describe('getPersonnelDetails', () => {
    it('should fetch personnel details by id', async () => {
      const id = 1;
      const response = { data: { id: 1, name: 'John Doe' } };
      apiClient.get.mockResolvedValue(response);

      await getPersonnelDetails(id);

      expect(apiClient.get).toHaveBeenCalledWith(`personnel/personnel/${id}/`);
    });
  });

  describe('createPersonnel', () => {
    it('should create new personnel', async () => {
      const data = { name: 'John Doe' };
      const response = { data: { id: 1, ...data } };
      apiClient.post.mockResolvedValue(response);

      await createPersonnel(data);

      expect(apiClient.post).toHaveBeenCalledWith('personnel/personnel/', data);
    });
  });

  describe('updatePersonnel', () => {
    it('should update personnel by id', async () => {
      const id = 1;
      const data = { name: 'John Doe' };
      const response = { data: { id: 1, ...data } };
      apiClient.put.mockResolvedValue(response);

      await updatePersonnel(id, data);

      expect(apiClient.put).toHaveBeenCalledWith(`personnel/personnel/${id}/`, data);
    });
  });

  describe('deletePersonnel', () => {
    it('should delete personnel by id', async () => {
      const id = 1;
      apiClient.delete.mockResolvedValue({});

      await deletePersonnel(id);

      expect(apiClient.delete).toHaveBeenCalledWith(`personnel/personnel/${id}/`);
    });
  });

  describe('getPositions', () => {
    it('should fetch all positions', async () => {
      const response = { data: { results: [{ id: 1, name: 'Manager' }], count: 1, current_page: 1, page_size: 10 } };
      apiClient.get.mockResolvedValue(response);

      const result = await getPositions();

      expect(apiClient.get).toHaveBeenCalledWith('personnel/positions/', { "params": {} });
      expect(result).toEqual(response);
    });
  });

  describe('createPosition', () => {
    it('should create a new position', async () => {
      const data = { name: 'Manager' };
      const response = { data: { id: 1, ...data } };
      apiClient.post.mockResolvedValue(response);

      await createPosition(data);

      expect(apiClient.post).toHaveBeenCalledWith('personnel/positions/', data);
    });
  });

  describe('updatePosition', () => {
    it('should update a position by id', async () => {
      const id = 1;
      const data = { name: 'Manager' };
      const response = { data: { id: 1, ...data } };
      apiClient.put.mockResolvedValue(response);

      await updatePosition(id, data);

      expect(apiClient.put).toHaveBeenCalledWith(`personnel/positions/${id}/`, data);
    });
  });

  describe('deletePosition', () => {
    it('should delete a position by id', async () => {
      const id = 1;
      apiClient.delete.mockResolvedValue({});

      await deletePosition(id);

      expect(apiClient.delete).toHaveBeenCalledWith(`personnel/positions/${id}/`);
    });
  });

  // P2-3: P4-1 新增 getMyPersonnel / updateMyPersonnel 测试
  describe('getMyPersonnel', () => {
    it('should fetch current user personnel', async () => {
      const response = {
        data: { id: 1, name: '测试人员', phone_number: '13800000000' },
      };
      apiClient.get.mockResolvedValue(response);

      const result = await getMyPersonnel();

      expect(apiClient.get).toHaveBeenCalledWith('users/me/personnel/');
      expect(result).toEqual(response.data);
    });

    it('should throw network error when request fails', async () => {
      apiClient.get.mockRejectedValue(new Error('Network error'));
      await expect(getMyPersonnel()).rejects.toMatchObject({ message: /网络/ });
    });
  });

  describe('updateMyPersonnel', () => {
    it('should patch allowed fields', async () => {
      const payload = { phone_number: '13911111111' };
      const response = { data: { id: 1, ...payload } };
      apiClient.patch.mockResolvedValue(response);

      const result = await updateMyPersonnel(payload);

      expect(apiClient.patch).toHaveBeenCalledWith('users/me/personnel/', payload);
      expect(result).toEqual(response.data);
    });
  });
});