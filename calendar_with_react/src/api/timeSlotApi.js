import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const timeSlotApi = {
  fetchTimeSlotsByTrial: async (trialId) => {
    try {
      const response = await apiClient.get(`/api/events/time-slots/?trial=${trialId}`);
      // 确保从results字段获取数据，并处理可能的undefined情况
      const slots = response.data?.results || [];
      
      return slots.map(slot => ({
        id: slot.id,
        start: new Date(slot.start_time),
        end: new Date(slot.end_time),
        description: slot.description || '',
        trialId: slot.trial_id  // 注意API返回的是trial_id字段
      }));
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  createTimeSlot: async (trialId, slotData) => {
    try {
      const response = await apiClient.post(`/api/events/trials/${trialId}/time-slots/`, {
        start_time: slotData.start,
        end_time: slotData.end,
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
      const response = await apiClient.patch(`/api/events/time-slots/${slotId}/`, {
        start_time: slotData.start,
        end_time: slotData.end,
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
      await apiClient.delete(`/api/events/time-slots/${slotId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateTimeSlotByIndex: async (trialId, slotIndex, slotData) => {
    try {
      const response = await apiClient.patch(`/api/events/trials/${trialId}/time-slots/${slotIndex}/`, {
        start_time: slotData.start,
        end_time: slotData.end,
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
      const response = await apiClient.put(`/api/events/trials/${trialId}/time-slots/bulk/`, {
        time_slots: slots.map(slot => ({
          id: slot.id,
          start_time: slot.start,
          end_time: slot.end,
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
      const response = await apiClient.post(`/api/events/trials/${trialId}/time-slots/bulk/`, {
        time_slots: slots.map(slot => ({
          start_time: slot.start,
          end_time: slot.end,
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
