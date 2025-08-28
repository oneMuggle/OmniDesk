import React, { useState, useEffect } from 'react';
import { Form } from 'antd';
import { trialApi } from '../api/trialApi';
import { useAuth } from '../context/AuthContext';
import { useTrialScheduleData } from '../hooks/useTrialScheduleData';
import CalendarEventModal from './CalendarEventModal'; // 使用新的通用模态框
import TrialSchedule from './TrialSchedule';

const TrialScheduleContainer = () => {
  const [form] = Form.useForm();
  const { isGuest } = useAuth();
  const [currentEvent, setCurrentEvent] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState(null);

  const {
    trials,
    trialEvents,
    isTrialsLoading,
    queryClient: trialQueryClient
  } = useTrialScheduleData();

  useEffect(() => {
    if (!isTrialsLoading) {
      trialQueryClient.invalidateQueries(['trials']);
    }
  }, [isTrialsLoading, trialQueryClient]);

  const handleSaveTrial = async (values) => {
    const trialId = values.trial || selectedTrial?.id;
    if (!trialId) {
      // If it's a new trial, trialId might not exist yet.
      // In this case, 'values' should contain all necessary data for creation.
      // If it's an update, trialId must exist.
      if (!values.id) { // Assuming new trials won't have an ID yet
        console.error('无法确定要更新或创建的试验项目。');
        return;
      }
    }
    try {
      if (values.id) { // Existing trial, update
        await trialApi.updateTrial(values.id, values);
      } else { // New trial, create
        await trialApi.createTrial(values); // Assuming createTrial expects a full trial object
      }
      trialQueryClient.invalidateQueries(['trials']);
      setCurrentEvent(null);
    } catch (error) {
      console.error('保存试验失败:', error);
    }
  };

  const handleEventClick = async (clickInfo) => {
    const eventObj = clickInfo.event.toPlainObject();
    const trialId = eventObj.extendedProps?.trialId;

    let trialDetails = null;
    if (trialId) {
      trialDetails = await trialApi.getTrialDetails(trialId);
      setSelectedTrial(trialDetails);
    }

    const updatedCurrentEvent = {
      ...eventObj,
      extendedProps: {
        ...eventObj.extendedProps,
        trialDetails: trialDetails,
        time_ranges: eventObj.extendedProps?.time_ranges || [{
          start_time: eventObj.start,
          end_time: eventObj.end
        }],
      },
    };
    console.log('TrialScheduleContainer - handleEventClick: updatedCurrentEvent', updatedCurrentEvent);
    setCurrentEvent(updatedCurrentEvent);
  };

  const handleDateSelect = (selectInfo) => {
    setCurrentEvent({
      title: '',
      time_ranges: [{
        start_time: selectInfo.start,
        end_time: selectInfo.end,
      }],
      allDay: selectInfo.allDay,
      extendedProps: { // 将 type 移动到 extendedProps
        type: 'TRIAL'
      }
    });
  };

  if (isTrialsLoading) {
    return <div>正在加载试验日程...</div>;
  }

  return (
    <>
      <TrialSchedule
        trials={trials}
        trialEvents={trialEvents}
        isGuest={isGuest}
        onDateClick={handleDateSelect}
        select={handleDateSelect}
        onEventClick={handleEventClick}
      />

      {currentEvent && (
        <CalendarEventModal
          isVisible={!!currentEvent}
          form={form}
          currentEvent={currentEvent}
          trials={trials}
          isGuest={isGuest}
          isEditing={isEditing}
          setIsEditing={setIsEditing}
          selectedTrial={selectedTrial}
          onSave={handleSaveTrial} // 将试验保存逻辑传递给 CalendarEventModal
          onCancel={() => setCurrentEvent(null)}
          onDelete={() => console.log('onDelete called')} // 临时空函数
          onSwap={() => console.log('onSwap called')}     // 临时空函数
        />
      )}

    </>
  );
};

export default TrialScheduleContainer;