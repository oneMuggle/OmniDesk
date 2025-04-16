import React, { useMemo } from 'react';
import './styles/ScheduleCalendar.css';
import { fromServerFormat } from '../../utils/dateUtils';
import BaseCalendar from './BaseCalendar';

const ScheduleCalendar = ({
  personnel = [],
  schedules,
  defaultEvents,
  isGuest,
  onScheduleDateClick,
  onScheduleEventClick,
  onEventDrop,
  onEventDragStart,
  onEventDragStop,
  select = () => {}
}) => {
  const events = useMemo(() => {
    console.log('ScheduleCalendar events', schedules, defaultEvents);
    console.log('ScheduleCalendar personnel events', personnel);
    const getNameById = (id) => {
      const person = personnel.find(p => p.id === id);
      return person ? person.name : `未知(${id})`;
    };

    const scheduleEvents = (Array.isArray(schedules) ? schedules : []).map(schedule => ({
      id: `schedule-${schedule.id}`,
      title: `${getNameById(schedule.staff)} (${getNameById(schedule.leader)})`,
      start: fromServerFormat(schedule.date)?.toDate(),
      end: fromServerFormat(schedule.date)?.toDate(),
      extendedProps: {
        type: 'SCHEDULE',
        personnelId: schedule.personnel_id,
        position: schedule.position,
        department: schedule.department,
        scheduleId: schedule.id
      },
      color: '#4CAF50',
      allDay: false,
      editable: !isGuest,
      tooltip: {
        title: `${getNameById(schedule.staff)}`,
        description: `
          职位: ${schedule.position}
          部门: ${schedule.department}
          时间: ${schedule.start_time} - ${schedule.end_time}
          人员ID: ${schedule.staff}
        `
      }
    }));
    return [...defaultEvents, ...scheduleEvents];
  }, [schedules, defaultEvents]);

  return (
    <BaseCalendar
      events={events}
      onDateClick={onScheduleDateClick}
      onEventClick={onScheduleEventClick}
      editable={!isGuest}
      selectable={!isGuest}
      onEventDrop={onEventDrop}
      onEventDragStart={onEventDragStart}
      onEventDragStop={onEventDragStop}
      select={select}
    />
  );
};

export default ScheduleCalendar;
