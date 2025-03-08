import React, { useState, useEffect } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import './CalendarPage.css';

const CalendarPage = () => {
  const [events, setEvents] = useState([
    { title: 'Meeting', start: new Date() }
  ]);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    document.body.classList.toggle('dark-mode', darkMode);
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  const handleDateClick = (arg) => {
    const title = prompt('请输入事件标题：');
    if (title) {
      setEvents([...events, {
        title: title,
        start: arg.date,
        allDay: arg.allDay
      }]);
    }
  };

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <button 
          className="theme-toggle"
          onClick={toggleDarkMode}
          data-tooltip-id="theme-tooltip"
          data-tooltip-content={darkMode ? '切换到亮色模式' : '切换到暗黑模式'}
        >
          {darkMode ? '🌙' : '☀️'}
        </button>
        
        <Tooltip id="theme-tooltip" />
        
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
          }}
          locale={zhCnLocale}
          buttonText={{
            today: '今天',
            month: '月视图',
            week: '周视图',
            day: '日视图'
          }}
          events={events}
          dateClick={handleDateClick}
          editable={true}
          selectable={true}
          height="auto"
          firstDay={1}
        />
      </div>
    </div>
  );
};

export default CalendarPage;
