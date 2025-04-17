import { apiClient } from '../context/AuthContext';
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
      const response = await apiClient.get('/events/schedules/');
      
      if (!response?.data) {
        console.error('无效的API响应格式: 缺少data字段', response);
        return [];
      }

      const results = Array.isArray(response.data.results) 
        ? response.data.results 
        : [];

      return results.map(schedule => ({
        id: schedule.id,
        date: schedule.duty_date,  // 修正字段映射
        staff: schedule.duty_person,  // 修正字段映射
        leader: schedule.duty_leader  // 修正字段映射
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
        duty_person: scheduleData.staff,
        duty_leader: scheduleData.leader
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
        duty_person: scheduleData.staff,
        duty_leader: scheduleData.leader
      });
      console.log('更新排班响应:', response.data);
      return response.data;
    } catch (error) {
      console.error('更新排班失败:', error.response?.data || error.message);
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
  }
};
