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
        params: { trial: trialId, ...params }
      });
      
      // 验证响应数据格式
      if (!response.data) {
        console.warn('API返回空数据:', { trialId, response });
        return [];
      }
      
      // 处理数组或对象格式的响应
      let slotsData;
      if (Array.isArray(response.data)) {
        slotsData = response.data;
      } else if (response.data && typeof response.data === 'object') {
        slotsData = response.data.results || response.data.items || [];
      } else {
        console.error('无法解析时间段数据:', { 
          trialId,
          responseData: response.data
        });
        return [];
      }
      
      // 确保最终是数组
      if (!Array.isArray(slotsData)) {
        console.error('最终数据不是数组:', { 
          trialId,
          slotsData
        });
        return [];
      }

      // 确保数据有map方法
      if (typeof slotsData.map !== 'function') {
        console.error('响应数据没有map方法:', {
          trialId,
          slotsDataType: typeof slotsData,
          slotsData
        });
        return [];
      }

      // 转换数据格式
      try {
        return slotsData.map(slot => {
          if (!slot || !slot.start_time || !slot.end_time) {
            console.warn('跳过无效时间段数据:', slot);
            return null;
          }
          
          try {
            return {
              id: slot.id,
              start: new Date(slot.start_time),
              end: new Date(slot.end_time),
              description: slot.description || '',
              trialId: slot.trial || trialId,
              trialTitle: slot.trial_title || ''
            };
          } catch (error) {
            console.error('处理单个时间段失败:', {
              error,
              slotData: slot
            });
            return null;
          }
        }).filter(Boolean);
      } catch (error) {
        console.error('映射时间段数据失败:', {
          error,
          slotsData
        });
        return [];
      }
    } catch (error) {
      const errorDetails = {
        trialId,
        apiUrl: '/api/events/time-slots/',
        params: { trial: trialId, ...params },
        response: error.response?.data,
        error: error.message,
        stack: error.stack
      };
      console.error('获取时间段API调用失败:', errorDetails);
      
      handleError({
        ...error,
        message: `获取时间段失败: ${error.response?.data?.message || error.message}`,
        details: {
          ...errorDetails,
          // 添加更多调试信息
          requestConfig: error.config,
          isAxiosError: error.isAxiosError
        }
      });
      
      // 返回空数组确保前端不会崩溃
      return [];
    }
  },

  createTimeSlot: async (slotData) => {
    try {
      console.error('[API Request] createTimeSlot:', slotData);
      const response = await apiClient.post('/api/events/time-slots/', {
        trial_id: slotData.trial,
        start_time: slotData.start_time,
        end_time: slotData.end_time,
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
          trialId:slotData.trialId,
          start: slotData.start_time,
          end: slotData.end_time
        }
      });
      throw error;
    }
  },

  updateTimeSlot: async (slotId, slotData) => {
    // 验证必填字段
    if (!slotData.start_time || !slotData.end_time) {
      throw new Error('必须提供start_time和end_time字段');
    }

    try {
      // 转换ID格式
      let finalSlotId = slotId;
      if (typeof slotId === 'string' && slotId.startsWith('slot_')) {
        finalSlotId = `${slotData.trial_id || slotData.trial}-${slotId.replace('slot_', '')}`;
      }

      console.log(`[API] 开始更新时间段 ID: ${finalSlotId}`, {
        提交数据: slotData,
        请求URL: `/api/events/time-slots/${slotId}/`
      });
      
      const response = await apiClient.patch(`/api/events/time-slots/${finalSlotId}/`, {
        start_time: slotData.start_time,
        end_time: slotData.end_time,
        description: slotData.description || '',
        trial_id: slotData.trial,
        // 确保发送所有必填字段
        start: slotData.start_time,
        end: slotData.end_time
      }, {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-Source': 'calendar-view'
        }
      });
      
      console.log(`[API] 时间段更新成功 ID: ${slotId}`, {
        响应数据: response.data
      });
      
      return {
        ...response.data,
        start: new Date(response.data.start_time),
        end: new Date(response.data.end_time)
      };
    } catch (error) {
      console.error(`[API] 时间段更新失败 ID: ${slotId}`, {
        错误: error,
        状态码: error.response?.status,
        响应数据: error.response?.data
      });
      
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
      // 特殊处理404错误 - 时间段可能已被删除
      if (error.response?.status === 404) {
        console.warn(`时间段 ${slotId} 可能已被删除`, error);
        return { success: false, id: slotId, message: '时间段不存在或已被删除' };
      }
      handleError({
        ...error,
        message: `删除时间段失败: ${error.message}`,
        details: { slotId }
      });
      throw error;
    }
  },

  // 通过trialId和slotIndex更新时间段
  updateTimeSlotByIndex: async (trialId, slotIndex, slotData) => {
    try {
      console.log(`[API] 开始通过索引更新时间段 trialId: ${trialId}, slotIndex: ${slotIndex}`, {
        提交数据: slotData,
        请求URL: `/api/events/trials/${trialId}/update-time-slot/${slotIndex}/`
      });
      
      const response = await apiClient.patch(
        `/api/events/trials/${trialId}/update-time-slot/${slotIndex}/`,
        {
          start_time: slotData.start_time,
          end_time: slotData.end_time,
          description: slotData.description || '',
          trial_id: slotData.trial
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Request-Source': 'calendar-view'
          }
        }
      );
      
      console.log(`[API] 通过索引更新时间段成功 trialId: ${trialId}, slotIndex: ${slotIndex}`, {
        响应数据: response.data
      });
      
      return {
        ...response.data,
        start: new Date(response.data.start_time),
        end: new Date(response.data.end_time)
      };
    } catch (error) {
      console.error(`[API] 通过索引更新时间段失败 trialId: ${trialId}, slotIndex: ${slotIndex}`, {
        错误: error,
        状态码: error.response?.status,
        响应数据: error.response?.data
      });
      
      handleError({
        ...error,
        message: `通过索引更新时间段失败: ${error.message}`,
        details: {
          trialId,
          slotIndex,
          start: slotData.start_time,
          end: slotData.end_time
        }
      });
      throw error;
    }
  },

  // 批量更新时间段
  bulkUpdateTimeSlots: async (slotsData) => {
    try {
      const validatedSlots = slotsData.map(slot => {
        if (!slot.id) {
          throw new Error('缺少时间段ID');
        }
        
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
          id: slot.id,
          start_time: startISO,
          end_time: endISO,
          description: slot.description || ''
        };
      });

      const response = await apiClient.patch(
        '/api/events/time-slots/bulk-update/',
        validatedSlots,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Request-Source': 'calendar-view'
          }
        }
      );
      
      return response.data.map(slot => ({
        ...slot,
        start: new Date(slot.start_time),
        end: new Date(slot.end_time)
      }));
    } catch (error) {
      // 特殊处理404错误 - 时间段可能已被删除
      if (error.response?.status === 404) {
        const notFoundSlots = slotsData.filter(slot => 
          error.response.data?.not_found?.includes(slot.id)
        );
        console.warn('部分时间段不存在:', notFoundSlots);
        return {
          success: false,
          notFound: notFoundSlots,
          message: '部分时间段不存在或已被删除'
        };
      }
      
      handleError({
        ...error,
        message: `批量更新时间段失败: ${error.message}`
      });
      throw error;
    }
  },

  // 批量创建时间段
  bulkCreateTimeSlots: async (trialId, slotsData) => {
    try {
      console.log('[API] 批量创建时间段请求数据:', {
        trialId,
        slotsData
      });

      const validatedSlots = slotsData.map(slot => {
        const startISO = slot.start;
        const endISO = slot.end;
        
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

      const response = await apiClient.post(
        '/api/events/time-slots/bulk-create/',
        {
          trial: trialId,
          time_slots: validatedSlots
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Request-Source': 'calendar-view'
          }
        }
      );

      // 验证响应数据
      if (!response.data || !Array.isArray(response.data)) {
        console.error('API返回无效数据:', response.data);
        throw new Error('API返回无效的时间段数据');
      }

      const createdSlots = response.data.map(slot => {
        if (!slot.id || !slot.start_time || !slot.end_time) {
          console.error('无效的时间段数据:', slot);
          throw new Error('API返回的时间段数据不完整');
        }
        return {
          ...slot,
          start: new Date(slot.start_time),
          end: new Date(slot.end_time)
        };
      });

      console.log('[API] 批量创建时间段成功:', createdSlots);
      return createdSlots;
    } catch (error) {
      handleError({
        ...error,
        message: `批量创建时间段失败: ${error.message}`
      });
      throw error;
    }
  },

  // 其他保留接口
  fetchCalendarEvents: () => apiClient.get('/api/events/trials/'),
  updateCalendarEvent: (id, eventData) => apiClient.put(`/api/events/trials/${id}/`, eventData),
  deleteCalendarEvent: (id) => apiClient.delete(`/api/events/trials/${id}/`)
};
