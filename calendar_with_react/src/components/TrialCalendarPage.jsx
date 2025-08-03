import React from 'react';
import CalendarPage from './CalendarPage'; // 假设CalendarPage是基础日历组件

const TrialCalendarPage = () => {
  return (
    <div>
      <h1>试验日历</h1>
      {/* 这里可以添加试验日历特有的逻辑或组件 */}
      <CalendarPage calendarType="trial" />
    </div>
  );
};

export default TrialCalendarPage;