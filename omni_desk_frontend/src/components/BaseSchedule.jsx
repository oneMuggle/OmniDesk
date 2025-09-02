import React from 'react';
import './styles/Schedule.css'; // 导入日历美化样式
import './styles/Controls.css';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';

const BaseSchedule = ({ // Changed BaseCalendar to BaseSchedule
  events,
  onDateClick,
  onEventClick,
  editable,
  selectable,
  select,
  onEventDrop,
  onEventDragStart,
  onEventDragStop
}) => {
  console.log('BaseSchedule received events:', events); // Add this line
  return (
    <FullCalendar
      plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
      initialView="dayGridMonth"
      headerToolbar={{
        left: 'prevYear,prev,next,nextYear today',
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
      dateClick={onDateClick}
      eventClick={(clickInfo) => {
        console.log('BaseSchedule - onEventClick:', clickInfo);
        onEventClick(clickInfo);
      }}
      editable={editable}
      selectable={selectable}
      eventStartEditable={editable}
      eventDurationEditable={editable}
      height="auto"
      firstDay={1}
      eventDrop={onEventDrop}
      eventDragStop={onEventDragStop}
      eventDragStart={onEventDragStart}
      select={select || (() => {})}
      eventContent={(eventInfo) => {
        if (eventInfo.event.extendedProps.type === 'SCHEDULE') {
          return (
            <div style={{ textAlign: 'center' }}>
              <div>{eventInfo.event.extendedProps.duty_person_name}</div>
              <div>{eventInfo.event.extendedProps.duty_leader_name}</div>
            </div>
          );
        }
        return (
          <div style={{ textAlign: 'center' }}>
            <div>{eventInfo.event.title}</div>
          </div>
        );
      }}
    />
  );
};

export default BaseSchedule; // Changed BaseCalendar to BaseSchedule