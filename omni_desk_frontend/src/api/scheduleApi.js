import apiClient from './apiClient';
import { handleError } from './responseHandler';

export const scheduleApi = {
  checkScheduleDate: async (date) => {
    try {
      const response = await apiClient.get('/events/schedules/', {
        params: { duty_date: date }
      });
      return (response.data.results || []).length > 0;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  getSchedules: async () => {
    try {
      let allSchedules = [];
      let url = '/events/schedules/';
      
      while (url) {
        const response = await apiClient.get(url);
        console.log(`API原始响应数据 (${url}):`, response.data);

        if (!response?.data) {
          console.error('无效的API响应格式: 缺少data字段', response);
          break;
        }

        const results = Array.isArray(response.data.results) ? response.data.results : [];
        allSchedules = allSchedules.concat(results);
        
        url = response.data.next;
      }

      console.log('转换前所有排班数据:', allSchedules);

      return allSchedules.map(schedule => ({
        id: schedule.id,
        duty_date: schedule.duty_date,
        duty_person: schedule.duty_person,
        duty_leader: schedule.duty_leader,
        type: 'SCHEDULE'
      }));
    } catch (error) {
      console.error('获取排班数据失败:', error);
      handleError(error);
      return [];
    }
  },

  createSchedule: async (scheduleData) => {
    try {
      console.log('创建排班请求数据:', scheduleData);
      const response = await apiClient.post('/events/schedules/', {
        duty_date: scheduleData.date,
        duty_person_id: scheduleData.duty_person_id, // 修改为 duty_person_id
        duty_leader_id: scheduleData.duty_leader_id  // 修改为 duty_leader_id
      });
      console.log('创建排班响应:', response.data);
      return response.data;
    } catch (error) {
      console.error('创建排班失败:', error.response?.data || error.message);
      handleError(error);
      throw error;
    }
  },

  updateSchedule: async (scheduleId, scheduleData) => {
    try {
      console.log('更新排班请求数据:', {scheduleId, ...scheduleData});
      const response = await apiClient.patch(`/events/schedules/${scheduleId}/`, {
        duty_date: scheduleData.date,
        duty_person_id: scheduleData.duty_person_id, // 修改为 duty_person_id
        duty_leader_id: scheduleData.duty_leader_id  // 修改为 duty_leader_id
      });
      console.log('更新排班响应:', response.data);
      return response.data;
    } catch (error) {
      console.error('更新排班失败:', error.response?.data || error.message);
      handleError(error);
      throw error;
    }
  },

  upsertSchedule: async (scheduleData) => {
    try {
      const { id, override, ...data } = scheduleData;
      const endpoint = id ? `/events/schedules/${id}/` : '/events/schedules/';
      const method = id ? 'patch' : 'post';
      
      const response = await apiClient[method](endpoint, {
        duty_date: data.date,
        duty_person: data.staff,
        duty_leader: data.leader,
        override: override || false
      });
      
      return response.data;
    } catch (error) {
      console.error('保存排班失败:', error.response?.data || error.message);
      handleError(error);
      throw error;
    }
  },

  deleteSchedule: async (scheduleId) => {
    try {
      await apiClient.delete(`/events/schedules/${scheduleId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  bulkDeleteSchedules: async (ids) => {
    try {
      const response = await apiClient.post('/events/schedules/bulk_destroy/', { ids });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  swapScheduleDates: async (scheduleId1, scheduleId2) => {
    try {
      const response = await apiClient.post('/events/schedules/swap-dates/', {
        schedule_id_1: scheduleId1,
        schedule_id_2: scheduleId2
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  getPersonnel: async () => {
    try {
      const response = await apiClient.get('/events/personnel/');
      return response.data.results || [];
    } catch (error) {
      console.error('获取人员数据失败:', error);
      handleError(error);
      return [];
    }
  },

  generateSchedules: async (data) => {
    try {
      const response = await apiClient.post('/events/schedules/generate-schedules/', data);
      return response.data;
    } catch (error) {
      console.error('生成排班失败:', error.response?.data || error.message);
      handleError(error);
      throw error;
    }
  },

  createPersonnel: async (personnelData) => {
    try {
      const response = await apiClient.post('/events/personnel/', personnelData);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updatePersonnel: async (personnelId, personnelData) => {
    try {
      const response = await apiClient.patch(`/events/personnel/${personnelId}/`, personnelData);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  deletePersonnel: async (personnelId) => {
    try {
      await apiClient.delete(`/events/personnel/${personnelId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  }
};
