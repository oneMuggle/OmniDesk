import { holidayApi } from './holidayApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient');

describe('holidayApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getHolidays', () => {
    it('should fetch all holidays', async () => {
      const mockHolidays = {
        results: [
          { id: 1, name: '元旦', start_date: '2024-01-01', end_date: '2024-01-01' },
          { id: 2, name: '春节', start_date: '2024-02-10', end_date: '2024-02-17' },
        ],
      };
      apiClient.get.mockResolvedValueOnce({ data: mockHolidays });

      const result = await holidayApi.getHolidays();

      expect(apiClient.get).toHaveBeenCalledWith('events/holidays/', { params: {} });
      expect(result).toEqual(mockHolidays.results);
    });

    it('should filter holidays by year', async () => {
      const mockHolidays = {
        results: [
          { id: 1, name: '元旦', start_date: '2025-01-01', end_date: '2025-01-01' },
        ],
      };
      apiClient.get.mockResolvedValueOnce({ data: mockHolidays });

      const result = await holidayApi.getHolidays(2025);

      expect(apiClient.get).toHaveBeenCalledWith('events/holidays/', { params: { year: 2025 } });
      expect(result).toEqual(mockHolidays.results);
    });

    it('should return empty array when no results', async () => {
      apiClient.get.mockResolvedValueOnce({ data: {} });

      const result = await holidayApi.getHolidays();

      expect(result).toEqual([]);
    });
  });

  describe('createHoliday', () => {
    it('should create a holiday', async () => {
      const holidayData = { name: '中秋节', start_date: '2024-09-17', end_date: '2024-09-19' };
      const mockResponse = { data: { id: 3, ...holidayData } };
      apiClient.post.mockResolvedValueOnce(mockResponse);

      const result = await holidayApi.createHoliday(holidayData);

      expect(apiClient.post).toHaveBeenCalledWith('events/holidays/', holidayData);
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('updateHoliday', () => {
    it('should update a holiday', async () => {
      const holidayId = 1;
      const updateData = { name: '元旦(更新)' };
      const mockResponse = { data: { id: holidayId, name: '元旦(更新)' } };
      apiClient.patch.mockResolvedValueOnce(mockResponse);

      const result = await holidayApi.updateHoliday(holidayId, updateData);

      expect(apiClient.patch).toHaveBeenCalledWith(`events/holidays/${holidayId}/`, updateData);
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('deleteHoliday', () => {
    it('should delete a holiday', async () => {
      const holidayId = 1;
      apiClient.delete.mockResolvedValueOnce({});

      await holidayApi.deleteHoliday(holidayId);

      expect(apiClient.delete).toHaveBeenCalledWith(`events/holidays/${holidayId}/`);
    });
  });
});
