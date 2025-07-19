import { Modal } from 'antd';
import { calendarApi } from '../api/calendar';

export const useCalendarEventDrop = (calendarType, schedules, scheduleQueryClient) => {
  const handleEventDrop = async (info) => {
    if (calendarType === 'schedule') {
      const { event, oldEvent } = info;
      const scheduleId = event.id;
      const newDate = event.startStr;
      const oldDate = oldEvent.startStr;
      
      try {
        const loading = Modal.info({
          title: '正在更新排班',
          content: '请稍候...',
          maskClosable: false
        });
        
        const targetSchedule = schedules.find(s => s.date === newDate);
        if (targetSchedule) {
          await calendarApi.swapScheduleDates(scheduleId, targetSchedule.id);
        } else {
          await calendarApi.updateScheduleDate(scheduleId, newDate);
        }
        
        await scheduleQueryClient.invalidateQueries(['schedules']);
        
        loading.update({
          type: 'success',
          title: '更新成功',
          content: targetSchedule ? '排班日期已交换' : '排班日期已更新',
          okButtonProps: { type: 'primary' }
        });
      } catch (error) {
        console.error('更新排班日期失败:', error);
        info.revert();
        Modal.error({
          title: '更新失败',
          content: `无法更新排班日期: ${error.message}`,
        });
      }
    }
  };

  return { handleEventDrop };
};