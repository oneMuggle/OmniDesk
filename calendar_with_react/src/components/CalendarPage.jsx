import React, { useState, useEffect } from 'react';
import { Select } from 'antd';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import { Modal, Input, Button } from 'antd';
import './CalendarPage.css';

const CalendarPage = () => {
  // 不同类型日历的事件数据
  const [defaultEvents, setDefaultEvents] = useState([
    { title: 'Meeting', start: new Date() }
  ]);
  const [workEvents, setWorkEvents] = useState([
    { title: '项目会议', start: new Date(), type: 'work' }
  ]);
  const [holidayEvents, setHolidayEvents] = useState([
    { title: '公共假期', start: new Date(), type: 'holiday' }
  ]);
  const [darkMode, setDarkMode] = useState(false);
  const [calendarType, setCalendarType] = useState('default'); // 新增日历类型状态
  
  // 日历类型选项
  const calendarOptions = [
    { value: 'default', label: '默认日历' },
    { value: 'work', label: '工作日程' },
    { value: 'holiday', label: '节假日历' },
  ];
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
    const currentEvents = calendarType === 'work' ? workEvents : 
                         calendarType === 'holiday' ? holidayEvents : 
                         defaultEvents;
    const existingEvent = currentEvents.find(event => 
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
    const eventWithType = { ...newEvent, type: calendarType };
    switch(calendarType) {
      case 'work':
        if (modalType === 'new') {
          setWorkEvents([...workEvents, eventWithType]);
        } else {
          setWorkEvents(workEvents.map(event => 
            event.start === currentEvent.start ? eventWithType : event
          ));
        }
        break;
      case 'holiday':
        if (modalType === 'new') {
          setHolidayEvents([...holidayEvents, eventWithType]);
        } else {
          setHolidayEvents(holidayEvents.map(event => 
            event.start === currentEvent.start ? eventWithType : event
          ));
        }
        break;
      default:
        if (modalType === 'new') {
          setDefaultEvents([...defaultEvents, eventWithType]);
        } else {
          setDefaultEvents(defaultEvents.map(event => 
            event.start === currentEvent.start ? eventWithType : event
          ));
        }
    }
    setCurrentEvent(null);
  };

  const handleDeleteEvent = () => {
    switch(calendarType) {
      case 'work':
        setWorkEvents(workEvents.filter(event => event.start !== currentEvent.start));
        break;
      case 'holiday':
        setHolidayEvents(holidayEvents.filter(event => event.start !== currentEvent.start));
        break;
      default:
        setDefaultEvents(defaultEvents.filter(event => event.start !== currentEvent.start));
    }
    setCurrentEvent(null);
  };

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <div className="calendar-controls">
          <Select
            defaultValue="default"
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
        </div>
        
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
          events={
            calendarType === 'work' ? workEvents : 
            calendarType === 'holiday' ? holidayEvents : 
            defaultEvents
          }
          dateClick={(arg) => {
            setCurrentEvent({
              title: '',
              start: arg.date,
              allDay: arg.allDay
            });
            setModalType('new');
          }}
          eventClick={(clickInfo) => {
            setCurrentEvent({
              ...clickInfo.event.toPlainObject(),
              start: new Date(clickInfo.event.start)
            });
            setModalType('view');
          }}
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
