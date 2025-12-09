import React from 'react';
import ScheduleControls from '../components/ScheduleControls';
import TrialScheduleContainer from '../components/TrialScheduleContainer';
import ShiftScheduleContainer from '../components/ShiftScheduleContainer';
import '../components/CalendarPage.css';

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