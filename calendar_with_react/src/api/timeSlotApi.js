import apiClient from './apiClient';
import { handleError } from './responseHandler';
import { fromServerFormat } from '../utils/dateUtils';

export const timeSlotApi = {
  fetchTimeSlotsByTrial: async (trialId) => {
    try {
      const response = await apiClient.get(`/events/time-slots/?trial=${trialId}`);
      
      // 处理分页响应和非分页响应
      const slots = Array.isArray(response.data)
        ? response.data  // 非分页响应
        : response.data?.results || [];  // 分页响应
      
      if (!Array.isArray(slots)) {
        console.error('无效的时间段数据格式:', response.data);
        return [];
      }

      return slots.map(slot => {
        if (!slot || !slot.start_time || !slot.end_time) {
          console.warn('无效的时间段数据:', slot);
          return null;
        }
        
        return {
          id: slot.id,
          start: fromServerFormat(slot.start_time),
          end: fromServerFormat(slot.end_time),
          description: slot.description || '',
          trialId: slot.trial_id
        };
      }).filter(Boolean);  // 过滤掉无效项
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  createTimeSlot: async (trialId, slotData) => {
    try {
      const response = await apiClient.post(`/events/trials/${trialId}/time-slots/`, {
        start_time: slotData.start_time,
        end_time: slotData.end_time,
        description: slotData.description || ''
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateTimeSlot: async (slotId, slotData) => {
    try {
      console.log('更新时间段请求数据:', slotData);
      const response = await apiClient.patch(`/events/time-slots/${slotId}/`, {
        start_time: slotData.start_time,
        end_time: slotData.end_time,
        description: slotData.description || ''
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  deleteTimeSlot: async (slotId) => {
    try {
      await apiClient.delete(`/events/time-slots/${slotId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateTimeSlotByIndex: async (trialId, slotIndex, slotData) => {
    try {
      const response = await apiClient.patch(`/events/trials/${trialId}/time-slots/${slotIndex}/`, {
        start_time: slotData.start_time,
        end_time: slotData.end_time,
        description: slotData.description || ''
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  bulkUpdateTimeSlots: async (trialId, slots) => {
    try {
      const response = await apiClient.put(`/events/trials/${trialId}/time-slots/bulk/`, {
        time_slots: slots.map(slot => ({
          id: slot.id,
          start_time: slot.start_time,
          end_time: slot.end_time,
          description: slot.description || ''
        }))
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  bulkCreateTimeSlots: async (trialId, slots) => {
    try {
      const response = await apiClient.post(`/events/trials/${trialId}/time-slots/bulk/`, {
        time_slots: slots.map(slot => ({
          start_time: slot.start_time,
          end_time: slot.end_time,
          description: slot.description || ''
        }))
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  }
};
