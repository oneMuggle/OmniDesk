import React from 'react';
import ScheduleControls from './Calendar/CalendarControls'; // Assuming this will be renamed to ScheduleControls
import TrialScheduleContainer from './Calendar/TrialCalendarContainer'; // Assuming this will be renamed to TrialScheduleContainer
import ShiftScheduleContainer from './Calendar/ScheduleCalendarContainer'; // Assuming this will be renamed to ShiftScheduleContainer
import './CalendarPage.css'; // Assuming this will be renamed to SchedulePage.css

const SchedulePage = ({ scheduleType }) => {
  return (
    <div className="schedule-page">
      <div className="schedule-container">
        <ScheduleControls />
        {scheduleType === 'trial' && <TrialScheduleContainer />}
        {scheduleType === 'shift' && <ShiftScheduleContainer />}
      </div>
    </div>
  );
};

export default SchedulePage;