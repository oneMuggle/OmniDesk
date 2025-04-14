import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const scheduleApi = {
  getSchedules: async () => {
    try {
      const response = await apiClient.get('/api/events/schedules/');
      return response.data.map(schedule => ({
        id: schedule.id,
        date: schedule.date,
        staff: schedule.staff,
        leader: schedule.leader
      }));
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  createSchedule: async (scheduleData) => {
    try {
      const response = await apiClient.post('/api/events/schedules/', {
        date: scheduleData.date,
        staff: scheduleData.staff,
        leader: scheduleData.leader
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateSchedule: async (scheduleId, scheduleData) => {
    try {
      const response = await apiClient.patch(`/api/events/schedules/${scheduleId}/`, {
        date: scheduleData.date,
        staff: scheduleData.staff,
        leader: scheduleData.leader
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  deleteSchedule: async (scheduleId) => {
    try {
      await apiClient.delete(`/api/events/schedules/${scheduleId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  swapScheduleDates: async (scheduleId1, scheduleId2) => {
    try {
      const response = await apiClient.post('/api/events/schedules/swap-dates/', {
        schedule_id_1: scheduleId1,
        schedule_id_2: scheduleId2
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  }
};
