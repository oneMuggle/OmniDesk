import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const calendarEventApi = {
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
        
        // 处理Date对象
        if (date instanceof Date) {
          return isNaN(date.getTime()) ? null : date.toISOString();
        }
        
        // 处理moment对象
        if (date._isAMomentObject) {
          return date.isValid?.() ? date.toISOString() : null;
        }
        
        // 处理字符串或其他格式
        try {
          const d = new Date(date);
          return isNaN(d.getTime()) ? null : d.toISOString();
        } catch {
          return null;
        }
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
      
      const response = await apiClient.post('/events/trials/', {
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
  }
};
