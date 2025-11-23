import { scheduleApi } from './scheduleApi';
import apiClient from './apiClient';

jest.mock('./apiClient');

describe('scheduleApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should handle bulk delete schedules successfully', async () => {
    const ids = [1, 2, 3];
    const response = { data: {} };
    apiClient.post.mockResolvedValue(response);

    const result = await scheduleApi.bulkDeleteSchedules(ids);

    expect(apiClient.post).toHaveBeenCalledWith('/events/schedules/bulk_destroy/', { ids });
    expect(result).toEqual(response.data);
  });

  it('should handle bulk delete schedules failure', async () => {
    const ids = [1, 2, 3];
    const error = new Error('Network Error');
    apiClient.post.mockRejectedValue(error);

    await expect(scheduleApi.bulkDeleteSchedules(ids)).rejects.toThrow('Network Error');
    expect(apiClient.post).toHaveBeenCalledWith('/events/schedules/bulk_destroy/', { ids });
  });
});