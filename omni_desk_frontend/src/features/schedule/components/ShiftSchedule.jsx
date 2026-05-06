import React from 'react';
import PropTypes from 'prop-types';
import BaseSchedule from './BaseSchedule';
import { transformScheduleToEvents } from '../utils/eventTransformers';

const ShiftSchedule = ({
  schedules,
  onDateClick,
  onEventClick,
  onScheduleSelect = () => {},
  calendarRef,
  onDatesSet,
}) => {
  const events = React.useMemo(() => {
    return transformScheduleToEvents(schedules);
  }, [schedules]);

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
      slotMinTime="08:00:00"
      slotMaxTime="22:00:00"
    />
  );
};

ShiftSchedule.propTypes = {
  schedules: PropTypes.array,
  isGuest: PropTypes.bool,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  onScheduleSelect: PropTypes.func,
  calendarRef: PropTypes.object.isRequired,
  onDatesSet: PropTypes.func.isRequired,
};

export default ShiftSchedule;
