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
    const error = {
      isAxiosError: true,
      response: { data: { detail: 'Bulk delete failed' }, status: 500 },
      message: 'Network Error'
    };
    apiClient.post.mockRejectedValue(error);

    // We spy on handleError to ensure it's called, but prevent its output in tests
    const handleError = jest.spyOn(require('./responseHandler'), 'handleError').mockImplementation(() => {});

    await expect(scheduleApi.bulkDeleteSchedules(ids)).rejects.toEqual(error);
    expect(apiClient.post).toHaveBeenCalledWith('/events/schedules/bulk_destroy/', { ids });
    expect(handleError).toHaveBeenCalledWith(error);

    handleError.mockRestore();
  });

  describe('getSchedules', () => {
    it('should fetch and format schedules correctly, handling pagination', async () => {
      const mockSchedulesPage1 = {
        results: [
          { id: 1, duty_date: '2023-10-01', duty_person: 'Alice', duty_leader: 'Bob' },
        ],
        next: '/events/schedules/?page=2',
      };
      const mockSchedulesPage2 = {
        results: [
          { id: 2, duty_date: '2023-10-02', duty_person: 'Charlie', duty_leader: 'Dave' },
        ],
        next: null,
      };

      apiClient.get
        .mockResolvedValueOnce({ data: mockSchedulesPage1 })
        .mockResolvedValueOnce({ data: mockSchedulesPage2 });

      const result = await scheduleApi.getSchedules();

      expect(apiClient.get).toHaveBeenCalledWith('/events/schedules/');
      expect(apiClient.get).toHaveBeenCalledWith('/events/schedules/?page=2');
      expect(result).toEqual([
        { id: 1, duty_date: '2023-10-01', duty_person: 'Alice', duty_leader: 'Bob', type: 'SCHEDULE' },
        { id: 2, duty_date: '2023-10-02', duty_person: 'Charlie', duty_leader: 'Dave', type: 'SCHEDULE' },
      ]);
    });
  });

  describe('createSchedule', () => {
    it('should create a new schedule', async () => {
      const newSchedule = { date: '2023-10-01', duty_person_id: 1, duty_leader_id: 2 };
      const response = { data: { id: 1, ...newSchedule } };
      apiClient.post.mockResolvedValue(response);

      const result = await scheduleApi.createSchedule(newSchedule);

      expect(apiClient.post).toHaveBeenCalledWith('/events/schedules/', {
        duty_date: newSchedule.date,
        duty_person_id: newSchedule.duty_person_id,
        duty_leader_id: newSchedule.duty_leader_id,
      });
      expect(result).toEqual(response.data);
    });
  });

  describe('updateSchedule', () => {
    it('should update an existing schedule', async () => {
      const scheduleId = 1;
      const updatedSchedule = { date: '2023-10-01', duty_person_id: 1, duty_leader_id: 2 };
      const response = { data: { id: scheduleId, ...updatedSchedule } };
      apiClient.patch.mockResolvedValue(response);

      const result = await scheduleApi.updateSchedule(scheduleId, updatedSchedule);

      expect(apiClient.patch).toHaveBeenCalledWith(`/events/schedules/${scheduleId}/`, {
        duty_date: updatedSchedule.date,
        duty_person_id: updatedSchedule.duty_person_id,
        duty_leader_id: updatedSchedule.duty_leader_id,
      });
      expect(result).toEqual(response.data);
    });
  });

  describe('deleteSchedule', () => {
    it('should delete a schedule', async () => {
      const scheduleId = 1;
      apiClient.delete.mockResolvedValue({});

      await scheduleApi.deleteSchedule(scheduleId);

      expect(apiClient.delete).toHaveBeenCalledWith(`/events/schedules/${scheduleId}/`);
    });
  });
});