import React, { useState, useRef } from 'react';
import { useAuth } from '../../auth/context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData';
import { useScheduleEventDrop } from '../hooks/useScheduleEventDrop';
import PersonnelScheduleModal from './PersonnelScheduleModal';
import ShiftSchedule from './ShiftSchedule';
import WeeklyLeaderDisplay from '../../../shared/components/Schedule/WeeklyLeaderDisplay';
import MonthlyLeaderSidebar from '../../../shared/components/Schedule/MonthlyLeaderSidebar';
import moment from 'moment';
import { DragDropContext } from 'react-beautiful-dnd';
import { scheduleApi } from '../api/schedule';

const ShiftScheduleContainer = () => {
  const { isGuest } = useAuth();
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit');
  const calendarRef = useRef(null);
  const [currentView, setCurrentView] = useState('dayGridMonth');
  const [calendarViewInfo, setCalendarViewInfo] = useState(null);

  const {
    schedules,
    personnel,
    queryClient: scheduleQueryClient
  } = useScheduleData();

  const weeklyLeaders = React.useMemo(() => {
    if (!calendarViewInfo || !schedules || schedules.length === 0) {
      return [];
    }

    const start = moment(calendarViewInfo.start);
    const end = moment(calendarViewInfo.end);
    const leadersByWeek = {};

    schedules.forEach(schedule => {
      const scheduleDate = moment(schedule.duty_date);
      if (scheduleDate.isBetween(start, end, 'day', '[]')) {
        const week = scheduleDate.week();
        if (!leadersByWeek[week]) {
          leadersByWeek[week] = {
            id: week,
            start: scheduleDate.clone().startOf('week').format('YYYY-MM-DD'),
            leaders: [],
            schedules: []
          };
        }
        if (schedule.duty_leader && !leadersByWeek[week].leaders.some(l => l.id === schedule.duty_leader.id)) {
          leadersByWeek[week].leaders.push(schedule.duty_leader);
        }
        leadersByWeek[week].schedules.push(schedule);
      }
    });

    return Object.values(leadersByWeek).sort((a, b) => a.id - b.id);
  }, [schedules, calendarViewInfo]);

  const handleScheduleDateClick = (arg) => {
    console.log("Date clicked:", arg.dateStr);
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
    (error) => { console.error('排班事件拖放失败:', error); }
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
              personnel={personnel}
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