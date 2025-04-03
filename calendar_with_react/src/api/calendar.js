import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const calendarApi = {
  // 获取试验日历事件
  fetchTrialEvents: async () => {
    try {
      // 自动携带认证令牌
      
      const response = await apiClient.get('/events/trials/');
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

  // 创建通用日历事件
  createCalendarEvent: async (eventData) => {
    try {
      console.log('[API Request] createCalendarEvent payload:', JSON.stringify({
        ...eventData,
        time_slots: eventData.time_slots?.map(s => ({ 
          start: s.start?.toISOString(), 
          end: s.end?.toISOString() 
        }))
      }, null, 2));
      
      // 添加防御性检查并规范化时间格式
      // 增强日期校验逻辑
      const normalizeDate = (date) => {
        if (!date) return null;
        // 处理moment对象
        if (date._isAMomentObject) {
          return date.isValid() ? date.toISOString() : null;
        }
        const d = date instanceof Date ? date : new Date(date);
        return isNaN(d) ? null : d.toISOString();
      };

      // 获取并规范化时间
      const startISO = normalizeDate(eventData.start);
      const endISO = normalizeDate(eventData.end);
      
      // 增强校验规则
      if (!startISO || !endISO) {
        throw new Error('事件必须包含有效的开始和结束时间');
      }
      
      const startDate = new Date(startISO);
      const endDate = new Date(endISO);
      
      if (startDate >= endDate) {
        throw new Error('结束时间必须晚于开始时间');
      }
      
      if (endDate - startDate < 30*60*1000) { // 30分钟
        throw new Error('事件持续时间至少需要30分钟');
      }

      const response = await apiClient.post('/events/', {
        title: eventData.title,
        start_time: startISO,
        end_time: endISO,
        // 规范化时间段数据
        time_slots: (eventData.time_slots || []).map(slot => ({
          start_time: normalizeDate(slot.start),
          end_time: normalizeDate(slot.end)
        })).filter(slot => slot.start_time && slot.end_time),
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

  // 其他保留接口
  fetchCalendarEvents: () => apiClient.get('/events/'),
  updateCalendarEvent: (id, eventData) => apiClient.put(`/events/${id}/`, eventData),
  deleteCalendarEvent: (id) => apiClient.delete(`/events/${id}/`)
};
