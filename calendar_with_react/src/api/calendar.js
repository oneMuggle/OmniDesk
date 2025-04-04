import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const calendarApi = {
  // 获取试验日历事件
  fetchTrialEvents: async () => {
    try {
      // 自动携带认证令牌
      
      const response = await apiClient.get('/api/events/trials/');
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
      const response = await apiClient.post('/api/events/trials/', {
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

  // 创建通用日历事件
  createCalendarEvent: async (eventData) => {
    try {
      console.error('[API Request] createCalendarEvent:', eventData);
      console.log('[API Request] createCalendarEvent payload:', JSON.stringify({
        ...eventData,
        time_slots: eventData.time_slots?.map(s => ({ 
          start: s.start?.toISOString(), 
          end: s.end?.toISOString() 
        }))
      }, null, 2));
      
      // 统一时间格式处理函数
      const normalizeDate = (date) => {
        if (!date) return null;
        // 处理moment对象
        if (date._isAMomentObject) {
          return date.isValid() ? date.toISOString() : null;
        }
        // 处理字符串或Date对象
        const d = date instanceof Date ? date : new Date(date);
        return isNaN(d.getTime()) ? null : d.toISOString();
      };

      // 验证并规范化时间段
      if (!eventData.time_slots || eventData.time_slots.length === 0) {
        throw new Error('必须提供至少一个有效时间段');
      }

      const validatedSlots = eventData.time_slots.map(slot => {
        const startISO = normalizeDate(slot.start_time || slot.start);
        const endISO = normalizeDate(slot.end_time || slot.end);
        
        if (!startISO || !endISO) {
          throw new Error(`无效的时间段参数: ${JSON.stringify(slot)}`);
        }

        const startDate = new Date(startISO);
        const endDate = new Date(endISO);
        
        if (startDate >= endDate) {
          throw new Error(`结束时间(${endISO})必须晚于开始时间(${startISO})`);
        }
        
        if (endDate - startDate < 30*60*1000) {
          throw new Error(`每个时间段至少需要30分钟，当前为${(endDate - startDate)/60000}分钟`);
        }

        return {
          start_time: startISO,
          end_time: endISO
        };
      });
      
      const response = await apiClient.post('/api/events/trials/', {
        title: eventData.title,
        // 使用已验证的时间段
        time_slots: validatedSlots,
        description: eventData.description || '',
        status: eventData.status || 'planned',
        related_equipment: eventData.related_equipment || [],
        responsible_persons: eventData.responsible_persons || []
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
      const response = await apiClient.patch(`/api/events/trials/${trialId}/`, {
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

  // 时间段相关接口
  // 时间段管理API
  fetchTimeSlotsByTrial: async (trialId, params = {}) => {
    try {
      const response = await apiClient.get('/api/events/time-slots/', {
        params: {
          trial: trialId,
          ...params
        }
      });
      return response.data.map(slot => ({
        id: slot.id,
        start: new Date(slot.start_time),
        end: new Date(slot.end_time),
        description: slot.description,
        trialId: slot.trial,
        trialTitle: slot.trial_title
      }));
    } catch (error) {
      handleError({
        ...error,
        message: `获取时间段失败: ${error.message}`,
        details: { trialId }
      });
      throw error;
    }
  },

  createTimeSlot: async (trialId, slotData) => {
    try {
      const response = await apiClient.post('/api/events/time-slots/', {
        trial: trialId,
        start_time: slotData.start?.toISOString(),
        end_time: slotData.end?.toISOString(),
        description: slotData.description || ''
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'calendar-view'
        }
      });
      return {
        ...response.data,
        start: new Date(response.data.start_time),
        end: new Date(response.data.end_time)
      };
    } catch (error) {
      handleError({
        ...error,
        message: `创建时间段失败: ${error.message}`,
        details: {
          trialId,
          start: slotData.start,
          end: slotData.end
        }
      });
      throw error;
    }
  },

  updateTimeSlot: async (slotId, slotData) => {
    try {
      const response = await apiClient.patch(`/api/events/time-slots/${slotId}/`, {
        start_time: slotData.start?.toISOString(),
        end_time: slotData.end?.toISOString(),
        description: slotData.description || ''
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'calendar-view'
        }
      });
      return {
        ...response.data,
        start: new Date(response.data.start_time),
        end: new Date(response.data.end_time)
      };
    } catch (error) {
      handleError({
        ...error,
        message: `更新时间段失败: ${error.message}`,
        details: {
          slotId,
          start: slotData.start,
          end: slotData.end
        }
      });
      throw error;
    }
  },

  deleteTimeSlot: async (slotId) => {
    try {
      await apiClient.delete(`/api/events/time-slots/${slotId}/`, {
        headers: {
          'X-Request-Source': 'calendar-view'
        }
      });
      return { success: true, id: slotId };
    } catch (error) {
      handleError({
        ...error,
        message: `删除时间段失败: ${error.message}`,
        details: { slotId }
      });
      throw error;
    }
  },

  // 批量创建时间段
  bulkCreateTimeSlots: async (trialId, slotsData) => {
    try {
      const validatedSlots = slotsData.map(slot => {
        const startISO = slot.start?.toISOString();
        const endISO = slot.end?.toISOString();
        
        if (!startISO || !endISO) {
          throw new Error(`无效的时间段参数: ${JSON.stringify(slot)}`);
        }

        const startDate = new Date(startISO);
        const endDate = new Date(endISO);
        
        if (startDate >= endDate) {
          throw new Error(`结束时间必须晚于开始时间`);
        }
        
        if (endDate - startDate < 30*60*1000) {
          throw new Error(`每个时间段至少需要30分钟`);
        }

        return {
          start_time: startISO,
          end_time: endISO,
          description: slot.description || ''
        };
      });

      const response = await apiClient.post('/api/events/time-slots/bulk/', {
        trial_id: trialId,
        time_slots: validatedSlots
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'calendar-view'
        }
      });
      
      return response.data.map(slot => ({
        ...slot,
        start: new Date(slot.start_time),
        end: new Date(slot.end_time)
      }));
    } catch (error) {
      handleError({
        ...error,
        message: `批量创建时间段失败: ${error.message}`,
        details: {
          trialId,
          slotsCount: slotsData.length
        }
      });
      throw error;
    }
  },

  // 其他保留接口
  fetchCalendarEvents: () => apiClient.get('/api/events/trials/'),
  updateCalendarEvent: (id, eventData) => apiClient.put(`/api/events/trials/${id}/`, eventData),
  deleteCalendarEvent: (id) => apiClient.delete(`/api/events/trials/${id}/`)
};
