import apiClient from './apiClient';
import { handleError } from './responseHandler';

export const trialApi = {
  fetchTrialEvents: async () => {
    try {
      const response = await apiClient.get('/events/trials/');
      return response.data.flatMap(trial => {
        const timeSlots = trial.time_slots?.map(slot => ({
          id: `slot_${slot.id}`,
          title: trial.title,
          start: new Date(slot.start_time),
          end: new Date(slot.end_time),
          extendedProps: {
            trialId: trial.id,
            description: slot.description,
            equipment: trial.equipments,
            personnel: trial.responsible_persons
          }
        })) || [];
        
        const startDates = timeSlots.map(p => p.start);
        const endDates = timeSlots.map(p => p.end);
        
        return [{
          id: trial.id,
          title: trial.title,
          start: new Date(Math.min(...startDates)),
          end: new Date(Math.max(...endDates)),
          extendedProps: {
            isMainEvent: true,
            timeSlots: timeSlots
          }
        }, ...timeSlots];
      });
    } catch (error) {
      console.error('Failed to fetch trial events:', error);
      return [];
    }
  },

  createTrial: async (trialData) => {
    try {
      const response = await apiClient.post('/events/trials/', {
        ...trialData,
        equipment_ids: trialData.equipmentIds || [],
        responsible_person_ids: trialData.responsiblePersonIds || [],
        time_slots: trialData.timeSlots?.map(slot => ({
          start_time: slot.start,
          end_time: slot.end,
          description: slot.description || ''
        })) || []
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'calendar-view'
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
      const response = await apiClient.patch(`/events/trials/${trialId}/`, {
        ...trialData,
        equipment_ids: trialData.equipmentIds,
        responsible_person_ids: trialData.responsiblePersonIds,
        time_slots: trialData.timeSlots?.map(slot => ({
          id: slot.id || null,
          start_time: slot.start,
          end_time: slot.end,
          description: slot.description || ''
        })) || []
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'calendar-view'
        }
      });
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  fetchCalendarEvents: () => apiClient.get('/events/trials/'),
  updateCalendarEvent: (id, eventData) => apiClient.put(`/events/trials/${id}/`, eventData),
  deleteCalendarEvent: (id) => apiClient.delete(`/events/trials/${id}/`),
  
  getTrialDetails: async (trialId) => {
    try {
      const response = await apiClient.get(`/events/trials/${trialId}/`);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  }
};
