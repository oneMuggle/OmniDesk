import React, { useState } from 'react';
import PropTypes from 'prop-types';
import TrialCalendar from './TrialCalendar';
import ScheduleCalendar from './ScheduleCalendar';
import CalendarControls from './CalendarControls';
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
  const [calendarType, setCalendarType] = useState('schedule');
  const [darkMode, setDarkMode] = useState(false);

  return (
    <div className={`calendar-container ${darkMode ? 'dark' : ''}`}>
      <CalendarControls 
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        calendarType={calendarType}
        setCalendarType={setCalendarType}
      />

      {calendarType === 'trial' ? (
        <TrialCalendar
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
