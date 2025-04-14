import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const scheduleApi = {
  getSchedules: async () => {
    try {
      const response = await apiClient.get('/api/events/schedules/');
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  fetchSchedules: async () => {
    try {
      const response = await apiClient.get('/api/events/schedules/');
      return response.data.map(schedule => ({
        id: schedule.id,
        title: schedule.title,
        start: new Date(schedule.start_time),
        end: new Date(schedule.end_time),
        extendedProps: {
          description: schedule.description,
          personnel: schedule.responsible_persons,
          equipment: schedule.equipments
        }
      }));
    } catch (error) {
      console.error('Failed to fetch schedules:', error);
      return [];
    }
  },

  createSchedule: async (scheduleData) => {
    try {
      const response = await apiClient.post('/api/events/schedules/', {
        title: scheduleData.title,
        start_time: scheduleData.start,
        end_time: scheduleData.end,
        description: scheduleData.description || '',
        equipment_ids: scheduleData.equipmentIds || [],
        responsible_person_ids: scheduleData.responsiblePersonIds || []
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
        title: scheduleData.title,
        start_time: scheduleData.start,
        end_time: scheduleData.end,
        description: scheduleData.description || '',
        equipment_ids: scheduleData.equipmentIds || [],
        responsible_person_ids: scheduleData.responsiblePersonIds || []
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
