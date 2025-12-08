import React from 'react';
import ScheduleControls from './ScheduleControls';
import TrialScheduleContainer from './TrialScheduleContainer';
import ShiftScheduleContainer from './ShiftScheduleContainer';
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