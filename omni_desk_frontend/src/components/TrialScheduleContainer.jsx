import React, { useState, useEffect } from 'react';
import { Modal, Form } from 'antd';
import { scheduleApi } from '../api/schedule';
import { trialApi } from '../api/trialApi';
import { getStatusConfig } from '../utils/scheduleUtils'; // Changed calendarUtils to scheduleUtils
import { useAuth } from '../context/AuthContext';
import { fromServerFormat } from '../utils/dateUtils';
import { useTrialScheduleData } from '../hooks/useTrialScheduleData'; // Changed useTrialCalendarData to useTrialScheduleData
import EventModal from './EventModal';
import TrialSchedule from './TrialSchedule'; // Changed TrialCalendar to TrialSchedule

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

  const handleEventSubmit = async (values, isNewEvent) => {
    try {
      if (isNewEvent) {
        await scheduleApi.createTrialEvent(values);
      } else {
        await scheduleApi.updateTrialEvent(currentEvent.id, values);
      }
      trialQueryClient.invalidateQueries(['trials']);
      setCurrentEvent(null);
      Modal.success({
        title: '操作成功',
        content: `事件已${isNewEvent ? '创建' : '更新'}！`,
      });
    } catch (error) {
      console.error('事件提交失败:', error);
      Modal.error({
        title: '操作失败',
        content: `提交事件时发生错误: ${error.message}`,
      });
    }
  };

  const handleTrialSelect = (selectInfo) => {
    console.log('[DEBUG] handleTrialSelect triggered:', selectInfo);
    const newEvent = {
      title: '',
      start: selectInfo.start,
      end: selectInfo.end,
      allDay: selectInfo.allDay,
      type: 'TRIAL'
    };
    console.log('[DEBUG] New event created in handleTrialSelect:', newEvent);
    setCurrentEvent(newEvent);
  };

  const handleTrialDateClick = (arg) => {
    console.log('[DEBUG] handleTrialDateClick triggered:', arg);
    const newEvent = {
      title: '',
      start: arg.date,
      allDay: arg.allDay,
      type: 'TRIAL'
    };
    console.log('[DEBUG] New event created in handleTrialDateClick:', newEvent);
    setCurrentEvent(newEvent);
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
        onDateClick={handleTrialDateClick}
        select={handleTrialSelect}
        onEventClick={async (clickInfo) => {
          const eventObj = clickInfo.event.toPlainObject();
          const trialId = eventObj.extendedProps?.trialId;

          try {
            let trialDetails = null;
            if (trialId) {
              trialDetails = await trialApi.getTrialDetails(trialId);
              setSelectedTrial(trialDetails);
            }

            setCurrentEvent({
              ...eventObj,
              start: fromServerFormat(eventObj.start),
              end: fromServerFormat(eventObj.end),
              extendedProps: {
                ...eventObj.extendedProps,
                statusConfig: getStatusConfig(eventObj.extendedProps.status),
                trialDetails: trialDetails,
              },
            });
          } catch (error) {
            console.error('获取试验详情失败:', error);
            Modal.error({
              title: '加载失败',
              content: '无法加载试验详情，请稍后再试',
            });
          }
        }}
      />

      {currentEvent && (
        <EventModal
          form={form}
          currentEvent={currentEvent}
          trials={trials}
          isGuest={isGuest}
          isEditing={isEditing}
          modifiedSlots={modifiedSlots}
          selectedTrial={selectedTrial}
          handleEventSubmit={handleEventSubmit}
          setCurrentEvent={setCurrentEvent}
          setIsEditing={setIsEditing}
          setModifiedSlots={setModifiedSlots}
          setSelectedTrial={setSelectedTrial}
          scheduleApi={scheduleApi}
        />
      )}
    </>
  );
};

export default TrialScheduleContainer;