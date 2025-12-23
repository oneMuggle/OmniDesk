import React from 'react';
import { Form } from 'antd';
import PropTypes from 'prop-types';
import CalendarEventModal from './CalendarEventModal';
import { scheduleApi } from '../api/schedule'; // 引入 scheduleApi
import { trialApi } from '../api/trialApi'; // 引入 trialApi
import { toServerFormat } from '../utils/dateUtils';
import { useQueryClient, useMutation } from '@tanstack/react-query';

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
      console.error('提交排班失败:', error);
      // TODO: Add error notification
    },
  });

  const { mutate: deleteEvent, isPending: isDeleting } = useMutation({
    mutationFn: (id) => {
      if (currentEvent.type === 'SCHEDULE') {
        return scheduleApi.deleteSchedule(id.replace('schedule-', ''));
      }
      if (currentEvent.type === 'TRIAL') {
        return trialApi.deleteTimeSlot(id.replace('slot_', ''));
      }
      return Promise.reject(new Error('Unknown event type for deletion'));
    },
    onSuccess: () => {
      const queryKey = currentEvent.type === 'SCHEDULE' ? ['schedules'] : ['trials'];
      queryClient.invalidateQueries({ queryKey });
      handleCancel();
    },
    onError: (error) => {
      console.error(`删除 ${currentEvent.type} 事件失败:`, error);
      // TODO: Add error notification
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
    // TODO: Implement swap logic for both SCHEDULE and TRIAL
    console.log('Swap functionality not yet implemented.');
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