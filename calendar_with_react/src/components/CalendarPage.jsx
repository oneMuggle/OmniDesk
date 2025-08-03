import React from 'react';
import CalendarControls from './Calendar/CalendarControls';
import TrialCalendarContainer from './Calendar/TrialCalendarContainer';
import './CalendarPage.css';

const CalendarPage = () => {
  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls />
        <TrialCalendarContainer />
      </div>
    </div>
  );
};

export default CalendarPage;
