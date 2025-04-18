import { message } from 'antd';
import { calendarApi } from '../api/calendar';
import { extractSlotId } from '../utils/calendarUtils';

export const useEventService = (queryClient) => {
  const handleEventSubmit = async (values, currentEvent, selectedTrial) => {
    try {
      const slotId = currentEvent?.id ? extractSlotId(currentEvent.id) : null;
      const isUpdate = !!slotId;

      // 验证 time_slots 数组
      if (!values.time_slots || values.time_slots.length === 0) {
        throw new Error('至少需要一个有效时间段');
      }

      // 处理多个时间段
      const responses = await Promise.all(
        values.time_slots.map(async (slot) => {
          if (!slot.start_time || !slot.end_time) {
            throw new Error('所有时间段必须包含开始和结束时间');
          }

          const payload = {
            trial_id: selectedTrial?.id,
            start_time: slot.start_time,
            end_time: slot.end_time,
            description: values.description,
            responsible_persons: values.responsiblePersons
          };

          return slot.id 
            ? calendarApi.updateTimeSlot(slot.id, payload)
            : calendarApi.createTimeSlot(payload);
        })
      );

      message.success(`成功处理${responses.length}个时间段`);
      const response = responses[0]; // 返回第一个结果保持兼容

      queryClient.invalidateQueries(['schedules']);
      return response.data;
    } catch (error) {
      console.error('提交事件失败:', error);
      message.error(`操作失败: ${error.response?.data?.message || error.message}`);
      throw error;
    }
  };

  const handleDeleteEvent = async (eventId) => {
    try {
      const slotId = extractSlotId(eventId);
      await calendarApi.deleteTimeSlot(slotId);
      message.success('时间段删除成功');
      queryClient.invalidateQueries(['schedules']);
    } catch (error) {
      console.error('删除事件失败:', error);
      message.error(`删除失败: ${error.response?.data?.message || error.message}`);
      throw error;
    }
  };

  return {
    handleEventSubmit,
    handleDeleteEvent
  };
};
