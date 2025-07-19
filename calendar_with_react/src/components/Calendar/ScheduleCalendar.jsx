import React from 'react';
import PropTypes from 'prop-types';
import BaseCalendar from './BaseCalendar';
import { fromServerFormat } from '../../utils/dateUtils';

const ScheduleCalendar = ({
  schedules,
  isGuest,
  onDateClick,
  onEventClick,
  onScheduleSelect = () => {}
}) => {
  console.log('ScheduleCalendar接收到的排班数据:', schedules); // 添加调试日志
  
  const events = React.useMemo(() => {
    return (Array.isArray(schedules) ? schedules : [])
      .map(schedule => ({
        type: 'SCHEDULE',
        id: schedule.id,
        title: schedule.title,
        start: fromServerFormat(schedule.start_time)?.toDate(),
        end: fromServerFormat(schedule.end_time)?.toDate(),
        extendedProps: {
          type: 'SCHEDULE',
          status: schedule.status,
          personnel: schedule.personnel,
          description: schedule.description
        },
        allDay: false,
        editable: !isGuest
      }));
  }, [schedules, isGuest]);

  return (
    <BaseCalendar
      events={events}
      onDateClick={onDateClick}
      onEventClick={onEventClick}
      editable={!isGuest}
      selectable={!isGuest}
      select={onScheduleSelect}
    />
  );
};

ScheduleCalendar.propTypes = {
  schedules: PropTypes.array,
  isGuest: PropTypes.bool,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  onScheduleSelect: PropTypes.func
};

export default ScheduleCalendar;
