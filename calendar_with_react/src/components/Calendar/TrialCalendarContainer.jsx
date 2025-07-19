import React, { useState } from 'react';
import { Modal, Form } from 'antd';
import { calendarApi } from '../../api/calendar';
import { trialApi } from '../../api/trialApi';
import { getStatusConfig } from '../../utils/calendarUtils';
import { useAuth } from '../../context/AuthContext';
import { fromServerFormat } from '../../utils/dateUtils';
import { useTrialCalendarData } from '../../hooks/useTrialCalendarData';
import EventModal from './EventModal/EventModal';
import TrialCalendar from './TrialCalendar';

const TrialCalendarContainer = () => {
  const [form] = Form.useForm();
  const { isGuest } = useAuth();
  const [currentEvent, setCurrentEvent] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState(null);

  const {
    trials,
    trialEvents,
    queryClient: trialQueryClient
  } = useTrialCalendarData();

  const handleEventSubmit = async (values, isNewEvent) => {
    try {
      if (isNewEvent) {
        await calendarApi.createTrialEvent(values);
      } else {
        await calendarApi.updateTrialEvent(currentEvent.id, values);
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

  return (
    <>
      <TrialCalendar
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
                trialDetails: trialDetails
              }
            });
          } catch (error) {
            console.error('获取试验详情失败:', error);
            Modal.error({
              title: '加载失败',
              content: '无法加载试验详情，请稍后再试'
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
          calendarApi={calendarApi}
        />
      )}
    </>
  );
};

export default TrialCalendarContainer;