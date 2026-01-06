import apiClient from './apiClient';
import { handleError } from './responseHandler';
import { toServerFormat } from '../utils/dateUtils';

export const trialApi = {
  fetchTrialEvents: async () => {
    try {
      const response = await apiClient.get('events/trials/');
      // 确保返回的是包含试验事件的数组
      return response.data.results || [];
    } catch (error) {
      console.error('Failed to fetch trial events:', error);
      handleError(error);
      throw error;
    }
  },

  createTrial: async (trialData) => {
    try {
      const response = await apiClient.post('events/trials/', {
        ...trialData,
        equipment_ids: trialData.equipmentIds || [],
        responsible_person_ids: trialData.responsiblePersonIds || [],
        time_periods: trialData.time_slots?.map(slot => ({
          start_time: toServerFormat(slot.start_time),
          end_time: toServerFormat(slot.end_time),
          description: slot.description || ''
        })) || []
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'schedule-view'
        }
      });
      return response.data;
    } catch (error) {
      handleError({
        ...error,
        message: `创建试验失败: ${error.message}`,
        details: {
          start: trialData.start,
          end: trialData.end
        }
      });
      throw new Error(`事件创建失败: ${error.message}`);
    }
  },

  updateTrial: async (trialId, trialData) => {
    try {
      const response = await apiClient.patch(`events/trials/${trialId}/`, {
        ...trialData,
        equipment_ids: trialData.equipmentIds,
        responsible_person_ids: trialData.responsiblePersonIds,
        time_slots_data: trialData.time_slots_data || []
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'schedule-view'
        }
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  fetchCalendarEvents: () => apiClient.get('events/trials/'),
  updateCalendarEvent: (id, eventData) => apiClient.put(`events/trials/${id}/`, eventData),
  deleteCalendarEvent: (id) => apiClient.delete(`events/trials/${id}/`),

  getTrialDetails: async (trialId) => {
    try {
      const response = await apiClient.get(`events/trials/${trialId}/`);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  fetchTimeSlotsByTrial: async (trialId) => {
    try {
      const response = await apiClient.get(`events/time-slots/?trial=${trialId}`);
      return response.data.results || [];
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  bulkCreateTimeSlots: async (trialId, timeSlots) => {
    try {
      const response = await apiClient.post('events/time-slots/bulk-create/', {
        trial: trialId,
        time_slots: timeSlots.map(slot => ({
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

};
