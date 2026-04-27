import { Modal } from 'antd';
import { logger } from '../../../shared/utils/logger';

export const useScheduleEventDrop = (updateEventApi, queryClient, onDropSuccess, onDropError) => {
  const handleEventDrop = async (info) => {
    const { event, oldEvent } = info;
    const eventId = event.id;
    const newStart = event.startStr;
    const oldStart = oldEvent.startStr;

    try {
      const loading = Modal.info({
        title: '正在更新事件',
        content: '请稍候...',
        maskClosable: false
      });

      await updateEventApi(eventId, newStart, oldStart);

      loading.destroy();
      await queryClient.invalidateQueries();

      Modal.success({
        title: '更新成功',
        content: '事件日期已更新',
      });
      if (onDropSuccess) {
        onDropSuccess();
      }
    } catch (error) {
      logger.error('更新事件日期失败:', error);
      info.revert();
      Modal.error({
        title: '更新失败',
        content: `无法更新事件日期: ${error.message}`,
      });
      if (onDropError) {
        onDropError(error);
      }
    }
  };

  return { handleEventDrop };
};