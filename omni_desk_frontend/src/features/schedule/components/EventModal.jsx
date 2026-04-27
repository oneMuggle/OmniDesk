import React from 'react';
import { Form } from 'antd';
import PropTypes from 'prop-types';
import CalendarEventModal from './CalendarEventModal';
import { scheduleApi } from '../api/schedule';
import { trialApi } from '../../../shared/api/trialApi';
import { toServerFormat } from '../utils/dateUtils';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { logger } from '../../../shared/utils/logger';

const EventModal = ({
  form,
  currentEvent,
  trials,
  isGuest,
  isEditing,
  modifiedSlots,
  selectedTrial,
  handleEventSubmit,
  setCurrentEvent,
  setIsEditing,
  setModifiedSlots,
  setSelectedTrial,
}) => {
  const queryClient = useQueryClient();

  const handleCancel = () => setCurrentEvent(null);

  const { mutate: saveSchedule, isPending: isSaving } = useMutation({
    mutationFn: (values) => {
      const payload = {
        date: toServerFormat(values.duty_date),
        duty_person: values.duty_person,
        duty_leader: values.duty_leader,
      };
      if (currentEvent.id && currentEvent.id.startsWith('schedule-')) {
        return scheduleApi.updateSchedule(currentEvent.id.replace('schedule-', ''), payload);
      }
      return scheduleApi.createSchedule(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      handleCancel();
    },
    onError: (error) => {
      logger.error('提交排班失败:', error);
    },
  });

  const { mutate: deleteEvent, isPending: isDeleting } = useMutation({
    mutationFn: (id) => {
      if (currentEvent.type === 'SCHEDULE') {
        return scheduleApi.deleteSchedule(id.replace('schedule-', ''));
      }
      if (currentEvent.type === 'TRIAL') {
        // 删除整个试验，而不是单个时间槽
        return trialApi.deleteTrial(id.replace('trial_', ''));
      }
      return Promise.reject(new Error('Unknown event type for deletion'));
    },
    onSuccess: () => {
      const queryKey = currentEvent.type === 'SCHEDULE' ? ['schedules'] : ['trials'];
      queryClient.invalidateQueries({ queryKey });
      handleCancel();
    },
    onError: (error) => {
      logger.error(`删除 ${currentEvent.type} 事件失败:`, error);
    },
  });

  const handleSave = async (values) => {
    if (!currentEvent) return;

    if (currentEvent.type === 'SCHEDULE') {
      saveSchedule(values);
    } else if (currentEvent.type === 'TRIAL') {
      await handleEventSubmit(values);
      queryClient.invalidateQueries({ queryKey: ['trials'] });
      handleCancel();
    }
  };

  const handleDelete = (id) => {
    if (!currentEvent) return;
    deleteEvent(id);
  };

  const handleSwap = async (id) => {
    if (!currentEvent) return;

    if (currentEvent.type === 'SCHEDULE') {
      const targetDate = prompt('请输入要调换的目标日期 (YYYY-MM-DD):');
      if (!targetDate) return;

      const schedules = queryClient.getQueryData(['schedules']) || [];
      const targetSchedule = schedules.find(s => s.duty_date === targetDate || s.start === targetDate);
      if (targetSchedule) {
        try {
          await scheduleApi.swapScheduleDates(id.replace('schedule-', ''), targetSchedule.id);
          queryClient.invalidateQueries({ queryKey: ['schedules'] });
          handleCancel();
        } catch (error) {
          logger.error('调换排班日期失败:', error);
        }
      } else {
        logger.warn(`未找到日期为 ${targetDate} 的排班记录`);
      }
    } else if (currentEvent.type === 'TRIAL') {
      logger.warn('试验日程调换功能暂未实现');
    }
  };

  return (
    <CalendarEventModal
      isVisible={currentEvent !== null}
      currentEvent={currentEvent}
      onCancel={handleCancel}
      onSave={handleSave}
      onDelete={handleDelete}
      onSwap={handleSwap}
      form={form}
      isEditing={isEditing}
      setIsEditing={setIsEditing}
      selectedTrial={selectedTrial}
      isProcessing={isSaving || isDeleting}
    />
  );
};

EventModal.propTypes = {
  form: PropTypes.object.isRequired,
  currentEvent: PropTypes.object,
  trials: PropTypes.array,
  isGuest: PropTypes.bool,
  isEditing: PropTypes.bool.isRequired,
  modifiedSlots: PropTypes.array.isRequired,
  selectedTrial: PropTypes.object,
  handleEventSubmit: PropTypes.func.isRequired,
  setCurrentEvent: PropTypes.func.isRequired,
  setIsEditing: PropTypes.func.isRequired,
  setModifiedSlots: PropTypes.func.isRequired,
  setSelectedTrial: PropTypes.func.isRequired,
};

export default EventModal;