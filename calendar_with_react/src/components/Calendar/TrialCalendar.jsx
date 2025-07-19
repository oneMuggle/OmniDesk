import React from 'react';
import PropTypes from 'prop-types';
import './styles/TrialCalendar.css';
import BaseCalendar from './BaseCalendar';

const TrialCalendar = ({
  trialEvents = [],
  isGuest,
  onTrialDateClick,
  onTrialEventClick,
  onTrialSelect = () => {}
}) => {
  return (
    <BaseCalendar
      events={trialEvents}
      onDateClick={onTrialDateClick}
      onEventClick={onTrialEventClick}
      editable={!isGuest}
      selectable={!isGuest}
      select={onTrialSelect}
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
  onTrialDateClick: PropTypes.func,
  onTrialEventClick: PropTypes.func,
  onTrialSelect: PropTypes.func
};

export default TrialCalendar;
