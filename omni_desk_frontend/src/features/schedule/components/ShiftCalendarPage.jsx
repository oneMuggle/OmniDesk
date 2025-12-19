import React from 'react';
import SchedulePage from './SchedulePage';

const ShiftCalendarPage = () => {
  return (
    <div>
      <h1>排班日历</h1>
      {/* 这里可以添加排班日历特有的逻辑或组件 */}
      <SchedulePage scheduleType="shift" />
    </div>
  );
};

export default ShiftCalendarPage;