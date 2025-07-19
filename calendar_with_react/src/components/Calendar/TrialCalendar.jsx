import React from 'react';
import PropTypes from 'prop-types';
import BaseCalendar from './BaseCalendar';

const TrialCalendar = ({
  trialEvents = [],
  isGuest,
  onDateClick,
  onEventClick,
  select = () => {}
}) => {
  return (
    <BaseCalendar
      events={trialEvents}
      onDateClick={onDateClick}
      onEventClick={onEventClick}
      editable={!isGuest}
      selectable={!isGuest}
      select={select}
    />
  );
};

TrialCalendar.propTypes = {
  trialEvents: PropTypes.arrayOf(
    PropTypes.shape({
      extendedProps: PropTypes.shape({
        type: PropTypes.oneOf(['TRIAL'])
      })
    })
  ),
  isGuest: PropTypes.bool,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  select: PropTypes.func
};

export default TrialCalendar;
