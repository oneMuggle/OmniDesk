import React from 'react';
import PropTypes from 'prop-types';
import BaseSchedule from './BaseSchedule';
import { transformScheduleToEvents } from '../utils/eventTransformers';

const ShiftSchedule = ({
  schedules,
  onDateClick,
  onEventClick,
  onScheduleSelect = () => {},
  personnel, // 接收 personnel prop
  calendarRef,
  onDatesSet,
}) => {
  // console.log('ScheduleCalendar接收到的排班数据:', schedules); // 添加调试日志
  // console.log('ScheduleCalendar接收到的人员数据:', personnel); // 添加调试日志

  const events = React.useMemo(() => {
    return transformScheduleToEvents(schedules, personnel);
  }, [schedules, personnel]);

  return (
    <BaseSchedule
      calendarRef={calendarRef}
      events={events}
      onDateClick={onDateClick}
      onEventClick={onEventClick}
      onDatesSet={onDatesSet}
      editable={false} // 排班在主页面不可编辑
      selectable={false} // 排班在主页面不可选择
      select={onScheduleSelect}
    />
  );
};

ShiftSchedule.propTypes = {
  schedules: PropTypes.array,
  isGuest: PropTypes.bool,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  onScheduleSelect: PropTypes.func,
  personnel: PropTypes.array.isRequired,
  calendarRef: PropTypes.object.isRequired,
  onDatesSet: PropTypes.func.isRequired,
};

export default ShiftSchedule;
