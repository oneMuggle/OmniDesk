import React from 'react';
import { Form } from 'antd';
import PropTypes from 'prop-types';
import CalendarEventModal from './CalendarEventModal';
import { scheduleApi } from '../api/schedule'; // 引入 scheduleApi
import { trialApi } from '../api/trialApi'; // 引入 trialApi
import { toServerFormat } from '../utils/dateUtils';
import { useQueryClient } from '@tanstack/react-query'; // 引入 useQueryClient

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

  const handleSave = async (values) => {
    if (!currentEvent) return;

    if (currentEvent.type === 'SCHEDULE') {
      try {
        const payload = {
          date: toServerFormat(values.duty_date),
          duty_person: values.duty_person,
          duty_leader: values.duty_leader,
        };
        if (currentEvent.id && currentEvent.id.startsWith('schedule-')) {
          await scheduleApi.updateSchedule(currentEvent.id.replace('schedule-', ''), payload);
        } else {
          await scheduleApi.createSchedule(payload);
        }
        queryClient.invalidateQueries(['schedules']); // 使排班缓存失效
        handleCancel();
      } catch (error) {
        console.error('提交排班失败:', error);
        // TODO: Add error notification
      }
    } else if (currentEvent.type === 'TRIAL') {
      await handleEventSubmit(values);
      queryClient.invalidateQueries(['trials']); // 使试验缓存失效
      handleCancel();
    }
  };

  const handleDelete = async (id) => {
    if (!currentEvent) return;

    if (currentEvent.type === 'SCHEDULE') {
      try {
        await scheduleApi.deleteSchedule(id.replace('schedule-', ''));
        queryClient.invalidateQueries(['schedules']);
        handleCancel();
      } catch (error) {
        console.error('删除排班失败:', error);
        // TODO: Add error notification
      }
    } else if (currentEvent.type === 'TRIAL') {
      try {
        await trialApi.deleteTimeSlot(id.replace('slot_', ''));
        queryClient.invalidateQueries(['trials']);
        handleCancel();
      } catch (error) {
        console.error('删除试验时间段失败:', error);
        // TODO: Add error notification
      }
    }
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