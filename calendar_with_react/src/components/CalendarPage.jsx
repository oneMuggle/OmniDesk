import React from 'react';
import CalendarControls from './Calendar/CalendarControls';
import TrialCalendarContainer from './Calendar/TrialCalendarContainer';
import ScheduleCalendarContainer from './Calendar/ScheduleCalendarContainer';
import './CalendarPage.css';

const CalendarPage = ({ calendarType }) => {
  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls />
        {calendarType === 'trial' && <TrialCalendarContainer />}
        {calendarType === 'shift' && <ScheduleCalendarContainer />}
      </div>
    </div>
  );
};

export default CalendarPage;
