import React from 'react';
import PropTypes from 'prop-types';

const ScheduleControls = ({ darkMode, setDarkMode, scheduleType, setScheduleType }) => {
  return (
    <div className="schedule-controls">
      <div className="schedule-type-toggle">
        <label>
          <input
            type="radio"
            value="schedule"
            checked={scheduleType === 'schedule'}
            onChange={() => setScheduleType('schedule')}
          />
          排班日历
        </label>
        <label>
          <input
            type="radio"
            value="trial"
            checked={scheduleType === 'trial'}
            onChange={() => setScheduleType('trial')}
          />
          试用日历
        </label>
      </div>
      <button onClick={() => setDarkMode(!darkMode)}>
        切换 {darkMode ? '亮色' : '暗色'} 模式
      </button>
    </div>
  );
};

ScheduleControls.propTypes = {
  darkMode: PropTypes.bool.isRequired,
  setDarkMode: PropTypes.func.isRequired,
  scheduleType: PropTypes.string.isRequired,
  setScheduleType: PropTypes.func.isRequired,
};

export default ScheduleControls;