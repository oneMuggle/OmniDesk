import PropTypes from 'prop-types';
import '../../../shared/components/styles/Schedule.css'; // 导入日历美化样式
import '../../../shared/components/styles/Controls.css';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';

const BaseSchedule = ({ // Changed BaseCalendar to BaseSchedule
  events,
  onDateClick = () => {},
  onEventClick = () => {},
  editable = false,
  selectable = false,
  select = () => {},
  onEventDrop = () => {},
  onEventDragStart = () => {},
  onEventDragStop = () => {},
  calendarRef = null,
  onDatesSet = () => {},
  slotMinTime,
  slotMaxTime,
}) => {
  return (
    <FullCalendar
      ref={calendarRef}
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
        onEventClick(clickInfo);
      }}
      datesSet={onDatesSet}
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
      slotMinTime={slotMinTime}
      slotMaxTime={slotMaxTime}
      eventContent={(eventInfo) => {
        const { extendedProps, allDay } = eventInfo.event;
        const details = extendedProps?.scheduleDetails;

        if (details) {
          return (
            <div className="calendar-event-card">
              <div className="event-card-row">
                <span className="event-card-name">{details.duty_person?.name || details.staff?.name || ''}</span>
              </div>
              <div className="event-card-row event-card-muted">
                <span>{details.duty_leader?.name || details.leader?.name || ''}</span>
              </div>
            </div>
          );
        }

        if (allDay) {
          return (
            <div className="calendar-event-card">
              <div className="event-card-title">{eventInfo.event.title}</div>
            </div>
          );
        }

        const startTime = eventInfo.timeText;
        return (
          <div className="calendar-event-card calendar-event-card--with-time">
            {startTime && <span className="event-card-time">{startTime}</span>}
            <span className="event-card-title">{eventInfo.event.title}</span>
          </div>
        );
      }}
    />
  );
};

BaseSchedule.propTypes = {
  events: PropTypes.array.isRequired,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  editable: PropTypes.bool,
  selectable: PropTypes.bool,
  select: PropTypes.func,
  onEventDrop: PropTypes.func,
  onEventDragStart: PropTypes.func,
  onEventDragStop: PropTypes.func,
  calendarRef: PropTypes.object,
  onDatesSet: PropTypes.func,
  slotMinTime: PropTypes.string,
  slotMaxTime: PropTypes.string,
};


export default BaseSchedule; // Changed BaseCalendar to BaseSchedule