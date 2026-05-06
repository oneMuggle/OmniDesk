import apiClient from '../../../shared/api/apiClient';
import { handleError } from '../../../shared/api/responseHandler';

export const scheduleApi = {
  checkScheduleDate: async (date) => {
    try {
      const response = await apiClient.get('events/schedules/', {
        params: { duty_date: date }
      });
      return (response.data.results || []).length > 0;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  fetchSchedules: async () => {
    try {
      return await scheduleApi.getSchedules();
    } catch (error) {
      handleError(error);
      return [];
    }
  },

  fetchSchedulesByDateRange: async (startDate, endDate) => {
    try {
      const response = await apiClient.get('events/schedules/by-date-range/', {
        params: { start_date: startDate, end_date: endDate }
      });
      const raw = response.data;
      const results = Array.isArray(raw) ? raw : (Array.isArray(raw.results) ? raw.results : []);
      return results.map(schedule => {
        const dutyPerson = schedule.duty_person || {};
        const dutyLeader = schedule.duty_leader || {};
        return {
          id: schedule.id,
          duty_date: schedule.duty_date,
          duty_person: dutyPerson,
          duty_leader: dutyLeader,
        };
      });
    } catch (error) {
      handleError(error);
      return [];
    }
  },

  getSchedules: async () => {
    try {
      let allSchedules = [];
      let url = 'events/schedules/';
      
      while (url) {
        const response = await apiClient.get(url);

        if (!response?.data) {
          break;
        }

        const results = Array.isArray(response.data.results) ? response.data.results : [];
        allSchedules = allSchedules.concat(results);
        
        url = response.data.next;
      }

      return allSchedules.map(schedule => {
        const dutyPerson = schedule.duty_person || {};
        const dutyLeader = schedule.duty_leader || {};
        return {
          id: schedule.id,
          duty_date: schedule.duty_date,
          duty_person: dutyPerson,
          duty_leader: dutyLeader,
        };
      });
    } catch (error) {
      handleError(error);
      return [];
    }
  },

  createSchedule: async (scheduleData) => {
    try {
      const response = await apiClient.post('events/schedules/', {
        duty_date: scheduleData.date,
        duty_person_id: scheduleData.duty_person_id, // 修改为 duty_person_id
        duty_leader_id: scheduleData.duty_leader_id  // 修改为 duty_leader_id
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateSchedule: async (scheduleId, scheduleData) => {
    try {
      const response = await apiClient.patch(`events/schedules/${scheduleId}/`, {
        duty_date: scheduleData.date,
        duty_person_id: scheduleData.duty_person_id, // 修改为 duty_person_id
        duty_leader_id: scheduleData.duty_leader_id  // 修改为 duty_leader_id
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateScheduleDate: async (scheduleId, newDate) => {
    try {
      const response = await apiClient.patch(`events/schedules/${scheduleId}/`, {
        duty_date: newDate,
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  upsertSchedule: async (scheduleData) => {
    try {
      const { id, override, ...data } = scheduleData;
      const endpoint = id ? `events/schedules/${id}/` : 'events/schedules/';
      const method = id ? 'patch' : 'post';
      
      const response = await apiClient[method](endpoint, {
        duty_date: data.date,
        duty_person: data.staff,
        duty_leader: data.leader,
        override: override || false
      });
      
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  deleteSchedule: async (scheduleId) => {
    try {
      await apiClient.delete(`events/schedules/${scheduleId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  bulkDeleteSchedules: async (ids) => {
    try {
      const response = await apiClient.post('events/schedules/bulk_destroy/', { ids });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  swapScheduleDates: async (scheduleId1, scheduleId2) => {
    try {
      const response = await apiClient.post('events/schedules/swap-dates/', {
        schedule_id_1: scheduleId1,
        schedule_id_2: scheduleId2
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  swapWeeklyLeaders: async (data) => {
    try {
      const response = await apiClient.post('events/schedules/swap-weekly-leaders/', data);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  fetchEquipment: async () => {
    try {
      const response = await apiClient.get('events/equipments/');
      return response.data.results || [];
    } catch (error) {
      handleError(error);
      return [];
    }
  },

  getPersonnel: async () => {
    try {
      const response = await apiClient.get('personnel/personnel/');
      return response.data.results || [];
    } catch (error) {
      handleError(error);
      return [];
    }
  },

  generateSchedules: async (data) => {
    try {
      const response = await apiClient.post('events/schedules/generate-schedules/', data);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  createPersonnel: async (personnelData) => {
    try {
      const response = await apiClient.post('personnel/personnel/', personnelData);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updatePersonnel: async (personnelId, personnelData) => {
    try {
      const response = await apiClient.patch(`personnel/personnel/${personnelId}/`, personnelData);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  deletePersonnel: async (personnelId) => {
    try {
      await apiClient.delete(`personnel/personnel/${personnelId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  }
};
