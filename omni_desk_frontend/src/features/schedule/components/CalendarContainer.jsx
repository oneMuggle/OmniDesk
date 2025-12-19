import React, { useState } from 'react';
import PropTypes from 'prop-types';
import TrialScheduleContainer from '~/features/schedule/components/TrialScheduleContainer';
import ScheduleCalendar from './ScheduleCalendar';
import ScheduleControls from './ScheduleControls';
import './styles/CalendarContainer.css';

const CalendarContainer = ({
  trialData,
  scheduleData,
  isGuest,
  onTrialDateClick,
  onTrialEventClick,
  onTrialSelect,
  onScheduleDateClick,
  onScheduleEventClick,
  onScheduleSelect
}) => {
  const [scheduleType, setScheduleType] = useState('schedule');
  const [darkMode, setDarkMode] = useState(false);

  return (
    <div className={`schedule-container ${darkMode ? 'dark' : ''} ${scheduleType}`}>
      <ScheduleControls
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        scheduleType={scheduleType}
        setScheduleType={setScheduleType}
      />

      {scheduleType === 'trial' ? (
        <TrialScheduleContainer
          trials={trialData}
          isGuest={isGuest}
          onTrialDateClick={onTrialDateClick}
          onTrialEventClick={onTrialEventClick}
          onTrialSelect={onTrialSelect}
        />
      ) : (
        <ScheduleCalendar
          schedules={scheduleData}
          isGuest={isGuest}
          onDateClick={onScheduleDateClick}
          onEventClick={onScheduleEventClick}
          onScheduleSelect={onScheduleSelect}
        />
      )}
    </div>
  );
};

CalendarContainer.propTypes = {
  trialData: PropTypes.array,
  scheduleData: PropTypes.array,
  isGuest: PropTypes.bool,
  onTrialDateClick: PropTypes.func,
  onTrialEventClick: PropTypes.func,
  onTrialSelect: PropTypes.func,
  onScheduleDateClick: PropTypes.func,
  onScheduleEventClick: PropTypes.func,
  onScheduleSelect: PropTypes.func
};

export default CalendarContainer;
