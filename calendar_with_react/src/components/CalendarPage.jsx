import React, { useState, useEffect } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import { Modal, Input, Button } from 'antd';
import './CalendarPage.css';

const CalendarPage = () => {
  const [events, setEvents] = useState([
    { title: 'Meeting', start: new Date() }
  ]);
  const [darkMode, setDarkMode] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);
  const [modalType, setModalType] = useState('new'); // 'view' | 'edit' | 'new'
  const [currentEvent, setCurrentEvent] = useState(null);

  useEffect(() => {
    document.body.classList.toggle('dark-mode', darkMode);
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  const handleDateClick = (arg) => {
    const clickedDate = arg.date;
    const existingEvent = events.find(event => 
      new Date(event.start).toDateString() === clickedDate.toDateString()
    );

    setSelectedDate(clickedDate);
    if (existingEvent) {
      setCurrentEvent(existingEvent);
      setModalType('view');
    } else {
      setCurrentEvent({
        title: '',
        start: clickedDate,
        allDay: arg.allDay
      });
      setModalType('new');
    }
  };

  const handleEventSubmit = (newEvent) => {
    if (modalType === 'new') {
      setEvents([...events, newEvent]);
    } else {
      setEvents(events.map(event => 
        event.start === currentEvent.start ? newEvent : event
      ));
    }
    setCurrentEvent(null);
  };

  const handleDeleteEvent = () => {
    setEvents(events.filter(event => event.start !== currentEvent.start));
    setCurrentEvent(null);
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

      <Modal
        title={modalType === 'view' ? '查看事件' : modalType === 'edit' ? '编辑事件' : '新建事件'}
        open={!!currentEvent}
        onCancel={() => setCurrentEvent(null)}
        footer={[
          modalType === 'view' && (
            <Button key="edit" type="primary" onClick={() => setModalType('edit')}>
              编辑
            </Button>
          ),
          modalType === 'edit' && (
            <Button key="delete" danger onClick={handleDeleteEvent}>
              删除
            </Button>
          ),
          <Button 
            key="submit" 
            type="primary" 
            onClick={() => handleEventSubmit(currentEvent)}
            disabled={modalType === 'view'}
          >
            {modalType === 'view' ? '关闭' : '保存'}
          </Button>
        ]}
      >
        <Input
          placeholder="事件标题"
          value={currentEvent?.title || ''}
          onChange={(e) => setCurrentEvent({...currentEvent, title: e.target.value})}
          disabled={modalType === 'view'}
          style={{ marginBottom: 16 }}
        />
        <p>日期：{currentEvent?.start.toLocaleDateString()}</p>
        {modalType !== 'new' && <p>创建时间：{currentEvent?.start.toLocaleString()}</p>}
      </Modal>
    </div>
  );
};

export default CalendarPage;
