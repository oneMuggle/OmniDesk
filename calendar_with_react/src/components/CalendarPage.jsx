import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Select } from 'antd';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import { Modal, Input, Button, DatePicker } from 'antd';
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

  const handleEventSubmit = async (newEvent) => {
    try {
      const eventData = {
        ...newEvent,
        start_time: newEvent.start.toISOString(),
        end_time: newEvent.end_time.toISOString(),
        experiment_info: newEvent.experiment_info,
        responsible_person: newEvent.responsible_person,
        train_count: newEvent.train_count
      };

      const response = await axios.post('/api/events/', eventData, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.status === 201) {
        const eventWithType = { ...newEvent, type: calendarType };
        switch(calendarType) {
          case 'work':
            setWorkEvents(prev => [...prev, eventWithType]);
            break;
          case 'holiday':
            setHolidayEvents(prev => [...prev, eventWithType]);
            break;
          default:
            setDefaultEvents(prev => [...prev, eventWithType]);
        }
      }
    } catch (error) {
      console.error('保存事件失败:', error);
      alert('保存事件失败，请检查网络连接或联系管理员');
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Input
            placeholder="事件标题"
            value={currentEvent?.title || ''}
            onChange={(e) => setCurrentEvent({...currentEvent, title: e.target.value})}
            disabled={modalType === 'view'}
          />

          <Input.TextArea
            placeholder="事件描述"
            value={currentEvent?.description || ''}
            onChange={(e) => setCurrentEvent({...currentEvent, description: e.target.value})}
            disabled={modalType === 'view'}
            rows={3}
          />

          <Input.TextArea
            placeholder="试验信息"
            value={currentEvent?.experiment_info || ''}
            onChange={(e) => setCurrentEvent({...currentEvent, experiment_info: e.target.value})}
            disabled={modalType === 'view'}
            rows={3}
          />

          <Input
            placeholder="负责人"
            value={currentEvent?.responsible_person || ''}
            onChange={(e) => setCurrentEvent({...currentEvent, responsible_person: e.target.value})}
            disabled={modalType === 'view'}
          />

          <Input
            type="number"
            placeholder="车次数量"
            value={currentEvent?.train_count || 0}
            onChange={(e) => setCurrentEvent({...currentEvent, train_count: parseInt(e.target.value) || 0})}
            disabled={modalType === 'view'}
            min={0}
          />

          <DatePicker
            showTime
            format="YYYY-MM-DD HH:mm"
            placeholder="开始时间"
            value={currentEvent?.start_time}
            onChange={(date) => setCurrentEvent({...currentEvent, start_time: date})}
            disabled={modalType === 'view'}
          />

          <DatePicker
            showTime
            format="YYYY-MM-DD HH:mm"
            placeholder="结束时间"
            value={currentEvent?.end_time}
            onChange={(date) => setCurrentEvent({...currentEvent, end_time: date})}
            disabled={modalType === 'view'}
          />

          <p>创建时间：{currentEvent?.start.toLocaleString()}</p>
        </div>
      </Modal>
    </div>
  );
};

export default CalendarPage;
