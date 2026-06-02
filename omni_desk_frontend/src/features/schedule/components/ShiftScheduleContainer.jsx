import React, { useState, useRef } from 'react';
import dayjs from 'dayjs';
import { useAuth } from '../../auth/context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData';
import { useScheduleEventDrop } from '../hooks/useScheduleEventDrop';
import PersonnelScheduleModal from './PersonnelScheduleModal';
import ShiftSchedule from './ShiftSchedule';
import WeeklyLeaderDisplay from '../../../shared/components/Schedule/WeeklyLeaderDisplay';
import MonthlyLeaderSidebar from '../../../shared/components/Schedule/MonthlyLeaderSidebar';
import { scheduleApi } from '../api/schedule';
import { logger } from '../../../shared/utils/logger';
import { Spin } from 'antd';
import { DragDropContext } from '@hello-pangea/dnd';
import { computeWeeklyLeaders } from '../utils/computeWeeklyLeaders';
import '../../../shared/components/styles/CalendarPageLayout.css';

const ShiftScheduleContainer = () => {
  const { isGuest } = useAuth();
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const calendarRef = useRef(null);
  const [currentView, setCurrentView] = useState('dayGridMonth');
  const [calendarViewInfo, setCalendarViewInfo] = useState(null);

  const dateRange = calendarViewInfo
    ? { start: dayjs(calendarViewInfo.start).format('YYYY-MM-DD'), end: dayjs(calendarViewInfo.end).format('YYYY-MM-DD') }
    : null;

  const {
    schedules,
    isSchedulesLoading,
    queryClient: scheduleQueryClient
  } = useScheduleData(dateRange);

  const weeklyLeaders = React.useMemo(() => {
    return computeWeeklyLeaders(schedules, calendarViewInfo);
  }, [schedules, calendarViewInfo]);

  const handleLeaderDragEnd = (result) => {
    if (!result.destination) return;

    const sourceWeek = weeklyLeaders[result.source.index];
    const destinationWeek = weeklyLeaders[result.destination.index];
    if (!sourceWeek || !destinationWeek) return;

    scheduleApi.swapWeeklyLeaders({
      source_week_start_date: sourceWeek.start,
      destination_week_start_date: destinationWeek.start,
    }).then(() => {
      scheduleQueryClient.invalidateQueries({ queryKey: ['schedules'] });
    }).catch(() => {
      logger.error('值班领导顺序交换失败');
    });
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

  if (isSchedulesLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0' }}>
        <Spin size="large" tip="正在加载排班数据..." />
      </div>
    );
  }

  const handleDatesSet = (viewInfo) => {
    setCalendarViewInfo(viewInfo);
    setCurrentView(viewInfo.view.type);
  };

  return (
    <div className="calendar-page-container">
      <div className="calendar-page-header">
        <h1>排班日程</h1>
      </div>
      <div className="calendar-page-content">
      <DragDropContext onDragEnd={handleLeaderDragEnd}>
        <div style={{ display: 'flex' }}>
          <div style={{ flex: 1 }}>
            {currentView === 'timeGridWeek' && <WeeklyLeaderDisplay leaders={weeklyLeaders.length > 0 ? weeklyLeaders[0].leaders : []} />}
            <ShiftSchedule
              calendarRef={calendarRef}
              schedules={schedules}
              isGuest={isGuest}
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
            isDragDisabled={false}
          />
        )}
      </div>
    </DragDropContext>

      <PersonnelScheduleModal
        open={scheduleModalOpen}
        onCancel={() => setScheduleModalOpen(false)}
        scheduleData={currentSchedule}
      />
      </div>
    </div>
  );
};

export default ShiftScheduleContainer;