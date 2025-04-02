import axios from 'axios';
import { handleError } from './responseHandler';

// 创建专属日历API实例
const calendarClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

export const calendarApi = {
  // 获取试验日历事件
  fetchTrialEvents: async () => {
    try {
      console.debug(calendarClient.baseURL);
      
      const response = await calendarClient.get('/api/events/trials/');
      return response.data.flatMap(trial => {
        // 将时间段转换为日历事件
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
        
        // 自动计算主事件时间范围
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

  // 创建试验
  createTrial: async (trialData) => {
    try {
      const response = await calendarClient.post('/events/trials/', {
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
      handleError(error);
      throw error;
    }
  },

  // 更新试验
  updateTrial: async (trialId, trialData) => {
    try {
      const response = await calendarClient.patch(`/events/trials/${trialId}/`, {
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

  // 其他保留接口
  fetchCalendarEvents: () => calendarClient.get('/events/'),
  updateCalendarEvent: (id, eventData) => calendarClient.put(`/events/${id}/`, eventData),
  deleteCalendarEvent: (id) => calendarClient.delete(`/events/${id}/`)
};
