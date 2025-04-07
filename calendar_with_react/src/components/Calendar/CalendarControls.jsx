import React from 'react';
import { Select } from 'antd';
import { Tooltip } from 'react-tooltip';

const CalendarControls = ({ 
  darkMode, 
  setDarkMode,
  calendarType,
  setCalendarType 
}) => {
  const calendarOptions = [
    { value: 'trial', label: '试验日历' },
    { value: 'schedule', label: '排班日历' },
  ];

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  return (
    <div className="calendar-controls">
      <Select
        value={calendarType}
        style={{ width: 200, marginRight: 16 }}
        onChange={(value) => setCalendarType(value)}
        options={calendarOptions}
      />
      <button
        className="theme-toggle"
        onClick={toggleDarkMode}
        data-tooltip-id="theme-tooltip"
        data-tooltip-content={darkMode ? '切换到亮色模式' : '切换到暗黑模式'}
      >
        {darkMode ? '🌙' : '☀️'}
      </button>
      <Tooltip id="theme-tooltip" />
    </div>
  );
};

export default CalendarControls;
