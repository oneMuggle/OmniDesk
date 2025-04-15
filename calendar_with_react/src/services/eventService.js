import { message } from 'antd';
import { calendarApi } from '../api/calendar';
import { extractSlotId } from '../utils/calendarUtils';

export const useEventService = (queryClient) => {
  const handleEventSubmit = async (values, currentEvent, selectedTrial) => {
    try {
      const slotId = currentEvent?.id ? extractSlotId(currentEvent.id) : null;
      const isUpdate = !!slotId;

      const payload = {
        trial_id: selectedTrial?.id,
        start_time: values.startTime.format('YYYY-MM-DD HH:mm:ss'),
        end_time: values.endTime.format('YYYY-MM-DD HH:mm:ss'),
        description: values.description,
        responsible_persons: values.responsiblePersons
      };

      let response;
      if (isUpdate) {
        response = await calendarApi.updateTimeSlot(slotId, payload);
        message.success('时间段更新成功');
      } else {
        response = await calendarApi.createTimeSlot(payload);
        message.success('时间段创建成功');
      }

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
