import React, { useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import moment from 'moment';
import CalendarControls from './Calendar/CalendarControls';
import EventModal from './Calendar/EventModal/EventModal';
import ScheduleModal from './Calendar/ScheduleModal';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import tippy from 'tippy.js';
import 'tippy.js/dist/tippy.css';
import { Tooltip } from 'react-tooltip';
import { Modal, Button, DatePicker, Form } from 'antd';
import { fromServerFormat, toServerFormat } from '../utils/dateUtils';
import { calendarApi } from '../api/calendar';
import { getTrials, getTrialById } from '../api/trials';
import { getStatusConfig, getTrialColor } from '../utils/calendarUtils';
import { useCalendarData } from '../hooks/useCalendarData';
import { useEventService } from '../services/eventService';
import './CalendarPage.css';

const CalendarPage = () => {
  const { isGuest } = useAuth();
  const [form] = Form.useForm();
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);
  const [scheduleModalVisible, setScheduleModalVisible] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit');
  const [modalType, setModalType] = useState('new');

  // 使用自定义hook获取数据
  const {
    trials,
    isTrialsLoading,
    schedules,
    isSchedulesLoading,
    personnel,
    isPersonnelLoading,
    defaultEvents,
    setDefaultEvents,
    darkMode,
    toggleDarkMode,
    calendarType,
    setCalendarType,
    currentEvent,
    setCurrentEvent,
    selectedTrial,
    setSelectedTrial,
    queryClient
  } = useCalendarData();

  console.log('当前日历类型:', calendarType);
  console.log('排班数据:', schedules);
  console.log('人员数据:', personnel);

  // 使用事件服务
  const { handleEventSubmit } = useEventService(queryClient);

  // 日历类型选项
  const calendarOptions = [
    { value: 'trial', label: '试验日历' },
    { value: 'schedule', label: '排班日历' },
  ];

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls 
          darkMode={darkMode}
          setDarkMode={toggleDarkMode}
          calendarType={calendarType}
          setCalendarType={setCalendarType}
        />

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
          events={useMemo(() => {
            if (calendarType === 'trial') {
              const trialEvents = (Array.isArray(trials) ? trials : []).flatMap(trial =>
                (Array.isArray(trial?.time_slots) ? trial.time_slots : []).map((slot, index) => ({
                  id: `trial-${trial.id}-${index}`,
                  title: `${trial.title} (ID: ${trial.id})`,
                  start: fromServerFormat(trial.start_date)?.toDate(),
                  end: fromServerFormat(trial.end_date)?.toDate(),
                  extendedProps: {
                    type: 'TRIAL',
                    status: trial.status,
                    client: trial.client,
                    equipment: trial.equipment,
                    personnel: trial.responsible_persons,
                    description: trial.description,
                    trialId: trial.id
                  },
                  color: getTrialColor(trial.id),
                  borderColor: getStatusConfig(trial.status).color,
                  allDay: false,
                  editable: false,
                  tooltip: {
                    title: `${trial.title}`,
                    description: `
                      状态: ${getStatusConfig(trial.status).text}
                      负责人: ${trial.responsible_persons?.join(', ') || '无'}
                      设备: ${trial.equipment || '无'}
                      描述: ${trial.description || '无'}
                    `
                  }
                }))
              );
              return [...defaultEvents, ...trialEvents];
            } else {
              return schedules.map(schedule => {
                const staffPerson = personnel.find(p => p.id === schedule.staff);
                const leaderPerson = personnel.find(p => p.id === schedule.leader);
                console.log('staffPerson:', staffPerson);
                console.log('leaderPerson:', leaderPerson);
                console.log('schedule:', schedule);
                return {
                  id: schedule.id,
                  title: `${staffPerson?.name || schedule.staff} (${leaderPerson?.name || schedule.leader})`,
                  start: schedule.date,
                  allDay: true,
                  extendedProps: {
                    type: 'SCHEDULE',
                    staff: schedule.staff,
                    leader: schedule.leader,
                    staffPhone: staffPerson?.phone || '无',
                    leaderPhone: leaderPerson?.phone || '无'
                  },
                  color: '#4CAF50',
                  display: 'background',
                  textColor: '#ffffff',
                  editable: !isGuest,
                  tooltip: {
                    title: `${staffPerson?.name || schedule.staff} 值班`,
                    description: `
                      日期: ${schedule.duty_date}
                      值班人: ${staffPerson?.name || schedule.staff} (${staffPerson?.phone || '无'})
                      值班领导: ${leaderPerson?.name || schedule.leader} (${leaderPerson?.phone || '无'})
                    `,
                    backgroundColor: '#4CAF50'
                  }
                };
              });
            }
          }, [calendarType, defaultEvents, trials])}
          dateClick={(arg) => {
            if (calendarType === 'trial') {
              const newEvent = {
                title: '',
                start: arg.date,
                allDay: arg.allDay,
                type: 'TRIAL'
              };
              setCurrentEvent(newEvent);
              setModalType('new');
            } else {
              setCurrentSchedule({
                date: arg.dateStr,
                staff: null,
                leader: null,
                staffPhone: '',
                leaderPhone: ''
              });
              setScheduleModalMode('edit');
              setScheduleModalVisible(true);
            }
          }}
          eventClick={async (clickInfo) => {
            const eventObj = clickInfo.event.toPlainObject();
            try {
              if (calendarType === 'trial') {
                const { data } = await getTrialById(eventObj.extendedProps.trialId);
                setCurrentEvent({
                  ...eventObj,
                  start: fromServerFormat(eventObj.start)?.toDate(),
                  end: fromServerFormat(eventObj.end)?.toDate(),
                  extendedProps: {
                    ...eventObj.extendedProps,
                    statusConfig: getStatusConfig(eventObj.extendedProps.status),
                    description: data.description,
                    client: data.client,
                    equipment: data.related_equipment,
                    personnel: data.responsible_persons,
                    timeSlots: data.time_slots
                  }
                });
                form.setFieldsValue({
                  trial: eventObj.extendedProps.trialId,
                  time_slots: data.time_slots?.map(slot => ({
                    start: fromServerFormat(slot.start_time)?.toDate(),
                    end: fromServerFormat(slot.end_time)?.toDate(),
                    description: slot.description,
                    id: slot.id
                  })) || []
                });
              } else if (calendarType === 'schedule') {
                const schedule = schedules.find(s => s.id === eventObj.id);
                if (schedule) {
                  setCurrentSchedule(schedule);
                  setScheduleModalMode('view');
                  setScheduleModalVisible(true);
                }
              }
              setModalType('view');
            } catch (error) {
              console.error('获取排班详情失败:', error);
              Modal.error({
                title: '加载失败',
                content: '无法加载排班详情信息',
              });
            }
          }}
          editable={!isGuest}
          selectable={!isGuest}
          eventStartEditable={!isGuest}
          eventDurationEditable={!isGuest}
          height="auto"
          firstDay={1}
          eventDrop={async (info) => {
            if (calendarType === 'schedule') {
              const { event, oldEvent } = info;
              const scheduleId = event.id;
              const newDate = event.startStr;
              const oldDate = oldEvent.startStr;
              
              try {
                const loading = Modal.info({
                  title: '正在更新排班',
                  content: '请稍候...',
                  maskClosable: false
                });
                
                const targetSchedule = schedules.find(s => s.date === newDate);
                if (targetSchedule) {
                  await calendarApi.swapScheduleDates(scheduleId, targetSchedule.id);
                } else {
                  await calendarApi.updateScheduleDate(scheduleId, newDate);
                }
                
                await queryClient.invalidateQueries(['schedules']);
                
                loading.update({
                  type: 'success',
                  title: '更新成功',
                  content: targetSchedule ? '排班日期已交换' : '排班日期已更新',
                  okButtonProps: { type: 'primary' }
                });
              } catch (error) {
                console.error('更新排班日期失败:', error);
                info.revert();
                Modal.error({
                  title: '更新失败',
                  content: `无法更新排班日期: ${error.message}`,
                });
              }
            }
          }}
          eventDragStop={(info) => {
            info.el.style.opacity = '1';
            info.el.style.boxShadow = 'none';
          }}
          eventDragStart={(info) => {
            info.el.style.opacity = '0.8';
            info.el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
          }}
        />
      </div>

      {currentEvent && (
        <EventModal
          currentEvent={currentEvent}
          modalType={modalType}
          form={form}
          trials={trials}
          isTrialsLoading={isTrialsLoading}
          selectedTrial={selectedTrial}
          isEditing={isEditing}
          modifiedSlots={modifiedSlots}
          handleEventSubmit={handleEventSubmit}
          setCurrentEvent={setCurrentEvent}
          setIsEditing={setIsEditing}
          setModifiedSlots={setModifiedSlots}
          setSelectedTrial={setSelectedTrial}
          calendarApi={calendarApi}
        />
      )}

      <ScheduleModal
        visible={scheduleModalVisible}
        onCancel={() => setScheduleModalVisible(false)}
        scheduleData={currentSchedule}
        mode={scheduleModalMode}
        personnelList={personnel}
        onSave={() => queryClient.invalidateQueries(['schedules'])}
        onDelete={() => queryClient.invalidateQueries(['schedules'])}
      />
    </div>
  );
};

export default CalendarPage;
