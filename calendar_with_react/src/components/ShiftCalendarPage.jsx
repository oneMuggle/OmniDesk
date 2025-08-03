import React from 'react';
import CalendarPage from './CalendarPage'; // 假设CalendarPage是基础日历组件

const ShiftCalendarPage = () => {
  return (
    <div>
      <h1>排班日历</h1>
      {/* 这里可以添加排班日历特有的逻辑或组件 */}
      <CalendarPage calendarType="shift" />
    </div>
  );
};

export default ShiftCalendarPage;