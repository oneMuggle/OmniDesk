import React, { useState, useRef } from 'react';
import { useAuth } from '../../auth/context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData';
import { useScheduleEventDrop } from '../hooks/useScheduleEventDrop';
import PersonnelScheduleModal from './PersonnelScheduleModal';
import ShiftSchedule from './ShiftSchedule';
import WeeklyLeaderDisplay from '../../../shared/components/Schedule/WeeklyLeaderDisplay';
import MonthlyLeaderSidebar from '../../../shared/components/Schedule/MonthlyLeaderSidebar';
import { scheduleApi } from '../api/schedule';
import { logger } from '../../../shared/utils/logger';
import { DragDropContext } from '@hello-pangea/dnd';
import { computeWeeklyLeaders } from '../utils/computeWeeklyLeaders';

const ShiftScheduleContainer = () => {
  const { isGuest } = useAuth();
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const calendarRef = useRef(null);
  const [currentView, setCurrentView] = useState('dayGridMonth');
  const [calendarViewInfo, setCalendarViewInfo] = useState(null);

  const {
    schedules,
    queryClient: scheduleQueryClient
  } = useScheduleData();

  const weeklyLeaders = React.useMemo(() => {
    return computeWeeklyLeaders(schedules, calendarViewInfo);
  }, [schedules, calendarViewInfo]);

  const handleScheduleDateClick = () => {
    // Date click handler - reserved for future use
  };

  const updateScheduleEvent = async (scheduleId, newDate) => {
    const targetSchedule = schedules.find(s => s.date === newDate);
    if (targetSchedule) {
      await scheduleApi.swapScheduleDates(scheduleId, targetSchedule.id);
    } else {
      await scheduleApi.updateScheduleDate(scheduleId, newDate);
    }
  };

  const { handleEventDrop } = useScheduleEventDrop(
    updateScheduleEvent,
    scheduleQueryClient,
    () => { /* onDropSuccess callback */ },
    (error) => { logger.error('排班事件拖放失败:', error); }
  );

  const handleDatesSet = (viewInfo) => {
    setCalendarViewInfo(viewInfo);
    setCurrentView(viewInfo.view.type);
  };

  return (
    <>
      <DragDropContext onDragEnd={() => {}}>
        <div style={{ display: 'flex' }}>
          <div style={{ flex: 1 }}>
            {currentView === 'timeGridWeek' && <WeeklyLeaderDisplay leaders={weeklyLeaders.length > 0 ? weeklyLeaders[0].leaders : []} />}
            <ShiftSchedule
              calendarRef={calendarRef}
              schedules={schedules}
              isGuest={isGuest}
              onDateClick={handleScheduleDateClick}
              onDatesSet={handleDatesSet}
              onEventClick={(clickInfo) => {
                const { event } = clickInfo;
                const { extendedProps } = event;
                if (extendedProps && extendedProps.scheduleDetails) {
                  setCurrentSchedule({
                    id: parseInt(event.id.replace('schedule-', '')),
                    date: event.startStr,
                    staff: extendedProps.scheduleDetails.duty_person?.id,
                    leader: extendedProps.scheduleDetails.duty_leader?.id,
                    staffName: extendedProps.scheduleDetails.duty_person?.name || '未知人员',
                    leaderName: extendedProps.scheduleDetails.duty_leader?.name || '未知人员',
                    staffPhone: extendedProps.scheduleDetails.duty_person?.phone_numbers?.map(p => p.number).join(', ') || '',
                    leaderPhone: extendedProps.scheduleDetails.duty_leader?.phone_numbers?.map(p => p.number).join(', ') || ''
                  });
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
        </div>
        {currentView === 'dayGridMonth' && (
          <MonthlyLeaderSidebar
            weeklyLeaders={weeklyLeaders}
            calendarRef={calendarRef}
            isDragDisabled={true}
          />
        )}
      </div>
    </DragDropContext>

      <PersonnelScheduleModal
        open={scheduleModalOpen}
        onCancel={() => setScheduleModalOpen(false)}
        scheduleData={currentSchedule}
      />
    </>
  );
};

export default ShiftScheduleContainer;