import React from 'react';
import './styles/BaseCalendar.css';
import './styles/Controls.css';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';

const BaseCalendar = ({
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
  console.log('BaseCalendar received events:', events); // Add this line
  return (
    <FullCalendar
      plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
      initialView="dayGridMonth"
      initialDate="2025-04-01"
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
      eventClick={onEventClick}
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
    />
  );
};

export default BaseCalendar;
