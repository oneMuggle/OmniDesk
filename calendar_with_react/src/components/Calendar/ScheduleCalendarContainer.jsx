import React, { useState } from 'react';
import { Form } from 'antd';
import { useAuth } from '../../context/AuthContext';
import { useScheduleCalendarData } from '../../hooks/useScheduleCalendarData';
import { useCalendarEventDrop } from '../../hooks/useCalendarEventDrop';
import PersonnelScheduleModal from './ScheduleModal';
import ScheduleCalendar from './ScheduleCalendar';
import { calendarApi } from '../../api/calendar'; // Import calendarApi

const ScheduleCalendarContainer = () => {
  const { isGuest } = useAuth();
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit');

  const {
    schedules,
    personnel,
    queryClient: scheduleQueryClient
  } = useScheduleCalendarData();

  const handleScheduleDateClick = (arg) => {
    setCurrentSchedule({
      date: arg.dateStr,
      staff: null,
      leader: null,
      staffPhone: '',
      leaderPhone: ''
    });
    setScheduleModalMode('edit');
    setScheduleModalOpen(true);
  };

  // 定义排班事件的更新函数
  const updateScheduleEvent = async (scheduleId, newDate) => {
    const targetSchedule = schedules.find(s => s.date === newDate);
    if (targetSchedule) {
      await calendarApi.swapScheduleDates(scheduleId, targetSchedule.id);
    } else {
      await calendarApi.updateScheduleDate(scheduleId, newDate);
    }
  };

  const { handleEventDrop } = useCalendarEventDrop(
    updateScheduleEvent,
    scheduleQueryClient,
    () => { /* onDropSuccess callback */ },
    (error) => { console.error('排班事件拖放失败:', error); }
  );

  return (
    <>
      <ScheduleCalendar
        personnel={personnel}
        schedules={schedules}
        isGuest={isGuest}
        onDateClick={handleScheduleDateClick}
        onEventClick={(clickInfo) => {
          const { event } = clickInfo;
          const { extendedProps } = event;
          if (extendedProps && extendedProps.scheduleDetails) {
            setCurrentSchedule({
              id: parseInt(event.id.replace('schedule-', '')),
              date: event.startStr,
              staff: extendedProps.duty_person_id,
              leader: extendedProps.duty_leader_id,
              staffPhone: extendedProps.scheduleDetails.staff.contact,
              leaderPhone: extendedProps.scheduleDetails.leader.contact
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

export default ScheduleCalendarContainer;