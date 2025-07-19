import React, { useState } from 'react';
import CalendarControls from './Calendar/CalendarControls';
import TrialCalendarContainer from './Calendar/TrialCalendarContainer';
import ScheduleCalendarContainer from './Calendar/ScheduleCalendarContainer';
import './CalendarPage.css';

const CalendarPage = () => {
  const [calendarType, setCalendarType] = useState('trial');
  const [darkMode, setDarkMode] = useState(false);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          toggleDarkMode={toggleDarkMode}
          calendarType={calendarType}
          setCalendarType={setCalendarType}
        />

        {calendarType === 'trial' ? (
          <TrialCalendarContainer />
        ) : (
          <ScheduleCalendarContainer />
        )}
      </div>
    </div>
  );
};

export default CalendarPage;
