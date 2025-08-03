import { Modal } from 'antd';

export const useCalendarEventDrop = (updateEventApi, queryClient, onDropSuccess, onDropError) => {
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

      // 调用传入的API更新事件
      await updateEventApi(eventId, newStart, oldStart);

      await queryClient.invalidateQueries(); // 使相关查询失效

      loading.update({
        type: 'success',
        title: '更新成功',
        content: '事件日期已更新',
        okButtonProps: { type: 'primary' }
      });
      if (onDropSuccess) {
        onDropSuccess();
      }
    } catch (error) {
      console.error('更新事件日期失败:', error);
      info.revert(); // 回滚事件到原位置
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