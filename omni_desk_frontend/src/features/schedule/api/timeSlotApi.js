import apiClient from '../../../shared/api/apiClient';
import { handleError } from '../../../shared/api/responseHandler';

export const timeSlotApi = {
  fetchTimeSlotsByTrial: async (trialId) => {
    try {
      const response = await apiClient.get(`/api/events/time-slots/?trial=${trialId}`);
      
      const slots = Array.isArray(response.data)
        ? response.data
        : response.data?.results || [];

      if (!Array.isArray(slots)) {
        console.error('Invalid time slot data format:', response.data);
        return [];
      }

      return slots.map(slot => {
        if (!slot || !slot.start_time || !slot.end_time) {
          console.warn('Invalid time slot data:', slot);
          return null;
        }
        
        return {
          id: slot.id,
          // Convert server ISO strings to Date objects directly
          start: new Date(slot.start_time),
          end: new Date(slot.end_time),
          description: slot.description || '',
          trialId: slot.trial_id
        };
      }).filter(Boolean);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  createTimeSlot: async (trialId, slotData) => {
    try {
      const response = await apiClient.post(`/api/events/trials/${trialId}/time-slots/`, {
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
      const response = await apiClient.patch(`/api/events/time-slots/${slotId}/`, {
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
      await apiClient.delete(`/api/events/time-slots/${slotId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateTimeSlotByIndex: async (trialId, slotIndex, slotData) => {
    try {
      const response = await apiClient.patch(`/api/events/trials/${trialId}/time-slots/${slotIndex}/`, {
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
      const response = await apiClient.put(`/api/events/trials/${trialId}/time-slots/bulk/`, {
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
      const response = await apiClient.post(`/api/events/trials/${trialId}/time-slots/bulk/`, {
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
