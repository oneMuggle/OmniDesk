import React from 'react';
import SchedulePage from './SchedulePage';

const TrialCalendarPage = () => {
  return (
    <div>
      <h1>试验日历</h1>
      {/* 这里可以添加试验日历特有的逻辑或组件 */}
      <SchedulePage scheduleType="trial" />
    </div>
  );
};

export default TrialCalendarPage;