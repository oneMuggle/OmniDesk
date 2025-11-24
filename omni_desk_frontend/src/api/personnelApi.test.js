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
} from './personnelApi';
import apiClient from './apiClient';

jest.mock('./apiClient');

describe('personnelApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getPersonnel', () => {
    it('should fetch personnel with given params', async () => {
      const params = { page: 1 };
      const response = { data: { results: [{ id: 1, name: 'John Doe' }] } };
      apiClient.get.mockResolvedValue(response);

      const result = await getPersonnel(params);

      expect(apiClient.get).toHaveBeenCalledWith('/events/personnel/', { params });
      expect(result).toEqual(response.data);
    });
  });

  describe('getAllPersonnel', () => {
    it('should fetch all personnel', async () => {
      const response = { data: [{ id: 1, name: 'John Doe' }] };
      apiClient.get.mockResolvedValue(response);

      const result = await getAllPersonnel();

      expect(apiClient.get).toHaveBeenCalledWith('/events/personnel/all/');
      expect(result).toEqual(response.data);
    });
  });

  describe('getPersonnelDetails', () => {
    it('should fetch personnel details by id', async () => {
      const id = 1;
      const response = { data: { id: 1, name: 'John Doe' } };
      apiClient.get.mockResolvedValue(response);

      await getPersonnelDetails(id);

      expect(apiClient.get).toHaveBeenCalledWith(`/events/personnel/${id}/`);
    });
  });

  describe('createPersonnel', () => {
    it('should create new personnel', async () => {
      const data = { name: 'John Doe' };
      const response = { data: { id: 1, ...data } };
      apiClient.post.mockResolvedValue(response);

      await createPersonnel(data);

      expect(apiClient.post).toHaveBeenCalledWith('/events/personnel/', data);
    });
  });

  describe('updatePersonnel', () => {
    it('should update personnel by id', async () => {
      const id = 1;
      const data = { name: 'John Doe' };
      const response = { data: { id: 1, ...data } };
      apiClient.put.mockResolvedValue(response);

      await updatePersonnel(id, data);

      expect(apiClient.put).toHaveBeenCalledWith(`/events/personnel/${id}/`, data);
    });
  });

  describe('deletePersonnel', () => {
    it('should delete personnel by id', async () => {
      const id = 1;
      apiClient.delete.mockResolvedValue({});

      await deletePersonnel(id);

      expect(apiClient.delete).toHaveBeenCalledWith(`/events/personnel/${id}/`);
    });
  });

  describe('getPositions', () => {
    it('should fetch all positions', async () => {
      const response = { data: [{ id: 1, name: 'Manager' }] };
      apiClient.get.mockResolvedValue(response);

      const result = await getPositions();

      expect(apiClient.get).toHaveBeenCalledWith('/events/positions/');
      expect(result).toEqual(response.data);
    });
  });

  describe('createPosition', () => {
    it('should create a new position', async () => {
      const data = { name: 'Manager' };
      const response = { data: { id: 1, ...data } };
      apiClient.post.mockResolvedValue(response);

      await createPosition(data);

      expect(apiClient.post).toHaveBeenCalledWith('/events/positions/', data);
    });
  });

  describe('updatePosition', () => {
    it('should update a position by id', async () => {
      const id = 1;
      const data = { name: 'Manager' };
      const response = { data: { id: 1, ...data } };
      apiClient.put.mockResolvedValue(response);

      await updatePosition(id, data);

      expect(apiClient.put).toHaveBeenCalledWith(`/events/positions/${id}/`, data);
    });
  });

  describe('deletePosition', () => {
    it('should delete a position by id', async () => {
      const id = 1;
      apiClient.delete.mockResolvedValue({});

      await deletePosition(id);

      expect(apiClient.delete).toHaveBeenCalledWith(`/events/positions/${id}/`);
    });
  });
});