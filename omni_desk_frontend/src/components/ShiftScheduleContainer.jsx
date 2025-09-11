import React, { useState } from 'react';
import { Form } from 'antd';
import { useAuth } from '../context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData'; // Changed useScheduleCalendarData to useScheduleData
import { useScheduleEventDrop } from '../hooks/useScheduleEventDrop'; // Changed useCalendarEventDrop to useScheduleEventDrop
import PersonnelScheduleModal from './PersonnelScheduleModal';
import ShiftSchedule from './ShiftSchedule'; // Changed ScheduleCalendar to ShiftSchedule
import { scheduleApi } from '../api/schedule';

const ShiftScheduleContainer = () => {
  const { isGuest } = useAuth();
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit');

  const {
    schedules,
    personnel,
    queryClient: scheduleQueryClient
  } = useScheduleData(); // Changed useScheduleCalendarData to useScheduleData

  const handleScheduleDateClick = (arg) => {
    // 点击空白处时不应该显示模态框，如果需要新增排班功能，应通过其他方式触发
    console.log("Date clicked:", arg.dateStr);
    // 这里不再打开模态框
  };

  // 定义排班事件的更新函数
  const updateScheduleEvent = async (scheduleId, newDate) => {
    const targetSchedule = schedules.find(s => s.date === newDate);
    if (targetSchedule) {
      await scheduleApi.swapScheduleDates(scheduleId, targetSchedule.id);
    } else {
      await scheduleApi.updateScheduleDate(scheduleId, newDate);
    }
  };

  const { handleEventDrop } = useScheduleEventDrop( // Changed useCalendarEventDrop to useScheduleEventDrop
    updateScheduleEvent,
    scheduleQueryClient,
    () => { /* onDropSuccess callback */ },
    (error) => { console.error('排班事件拖放失败:', error); }
  );

  return (
    <>
      <ShiftSchedule // Changed ScheduleCalendar to ShiftSchedule
        personnel={personnel}
        schedules={schedules}
        isGuest={isGuest}
        onDateClick={handleScheduleDateClick}
        onEventClick={(clickInfo) => {
          const { event } = clickInfo;
          const { extendedProps } = event;
          console.log("ShiftScheduleContainer - extendedProps.scheduleDetails:", extendedProps.scheduleDetails);
          console.log("ShiftScheduleContainer - extendedProps.scheduleDetails.duty_person:", extendedProps.scheduleDetails.duty_person);
          console.log("ShiftScheduleContainer - extendedProps.scheduleDetails.duty_leader:", extendedProps.scheduleDetails.duty_leader);
          if (extendedProps && extendedProps.scheduleDetails) {
            setCurrentSchedule({
              id: parseInt(event.id.replace('schedule-', '')),
              date: event.startStr,
              staff: extendedProps.scheduleDetails.duty_person?.id,
              leader: extendedProps.scheduleDetails.duty_leader?.id,
              staffPhone: extendedProps.scheduleDetails.duty_person?.phone_numbers?.map(p => p.number).join(', ') || '',
              leaderPhone: extendedProps.scheduleDetails.duty_leader?.phone_numbers?.map(p => p.number).join(', ') || ''
            });
            setScheduleModalMode('view');
            setScheduleModalOpen(true);
          }
        }}
        onEventDrop={handleEventDrop}
        onEventDragStart={(info) => {
          info.el.style.opacity = '0.8';
          info.el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
        }}
        onEventDragStop={(info) => {
          info.el.style.opacity = '1';
          info.el.style.boxShadow = 'none';
        }}
      />

      <PersonnelScheduleModal
        open={scheduleModalOpen}
        onCancel={() => setScheduleModalOpen(false)}
        scheduleData={currentSchedule}
        mode={scheduleModalMode}
        personnelList={personnel}
        onSave={(mode) => {
          if (mode === 'edit') {
            setScheduleModalMode('edit');
          }
          scheduleQueryClient.invalidateQueries(['schedules']);
        }}
        onDelete={() => scheduleQueryClient.invalidateQueries(['schedules'])}
      />
    </>
  );
};

export default ShiftScheduleContainer;