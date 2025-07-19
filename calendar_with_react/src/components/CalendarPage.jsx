import React, { useState } from 'react';
import { Modal, Form } from 'antd';
import { calendarApi } from '../api/calendar';
import { formatDate } from '../utils/dateUtils';
import { trialApi } from '../api/trialApi';
import { getStatusConfig } from '../utils/calendarUtils';
import { useAuth } from '../context/AuthContext';
import { fromServerFormat } from '../utils/dateUtils';
import { useTrialCalendarData } from '../hooks/useTrialCalendarData';
import { useScheduleCalendarData } from '../hooks/useScheduleCalendarData';
import CalendarControls from './Calendar/CalendarControls';
import { useCalendarEventDrop } from '../hooks/useCalendarEventDrop';
import EventModal from './Calendar/EventModal/EventModal';
import PersonnelScheduleModal from './Calendar/ScheduleModal';
import TrialCalendar from './Calendar/TrialCalendar';
import ScheduleCalendar from './Calendar/ScheduleCalendar';
import './CalendarPage.css';

const CalendarPage = () => {
  const [form] = Form.useForm();
  const { isGuest } = useAuth();
  const [modalType, setModalType] = useState('new');
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit');
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState(null);
  const [calendarType, setCalendarType] = useState('trial');
  const [currentEvent, setCurrentEvent] = useState(null);
  const [darkMode, setDarkMode] = useState(false);

  // 使用独立的数据hooks
  const {
    trials,
    trialEvents,
    queryClient: trialQueryClient
  } = useTrialCalendarData();

  const {
    schedules,
    personnel,
    queryClient: scheduleQueryClient
  } = useScheduleCalendarData();

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  // 处理事件提交
  const handleEventSubmit = async (values, isNewEvent) => {
    try {
      if (calendarType === 'trial') {
        // 试验事件处理
        if (isNewEvent) {
          await calendarApi.createTrialEvent(values);
        } else {
          await calendarApi.updateTrialEvent(currentEvent.id, values);
        }
        trialQueryClient.invalidateQueries(['trials']);
      } else {
        // 排班事件处理 (如果需要)
        // 目前排班事件没有独立的创建/更新流程，而是通过拖放或模态框处理
      }
      setCurrentEvent(null); // 关闭模态框
      Modal.success({
        title: '操作成功',
        content: `事件已${isNewEvent ? '创建' : '更新'}！`,
      });
    } catch (error) {
      console.error('事件提交失败:', error);
      Modal.error({
        title: '操作失败',
        content: `提交事件时发生错误: ${error.message}`,
      });
    }
  };

  // 处理试验日历选择
  const handleTrialSelect = (selectInfo) => {
    const newEvent = {
      title: '',
      start: selectInfo.start,
      end: selectInfo.end,
      allDay: selectInfo.allDay,
      type: 'TRIAL'
    };
    setCurrentEvent(newEvent);
    setModalType('new');
  };

  // 处理试验日历日期点击
  const handleTrialDateClick = (arg) => {
    const newEvent = {
      title: '',
      start: arg.date,
      allDay: arg.allDay,
      type: 'TRIAL'
    };
    setCurrentEvent(newEvent);
    setModalType('new');
  };

  // 处理排班日历日期点击
  const handleScheduleDateClick = (arg) => {
    setCurrentSchedule({
      date: arg.dateStr,
      staff: null,
      leader: null,
      staffPhone: '',
      leaderPhone: ''
    });
    setScheduleModalMode('edit');
    setScheduleModalOpen(true);
  };

  const { handleEventDrop } = useCalendarEventDrop(calendarType, schedules, scheduleQueryClient);

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls 
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          toggleDarkMode={toggleDarkMode}
          calendarType={calendarType}
          setCalendarType={setCalendarType}
        />

        {calendarType === 'trial' ? (
          <TrialCalendar
            trials={trials}
            trialEvents={trialEvents}
            isGuest={isGuest}
            onTrialDateClick={handleTrialDateClick}
            onTrialSelect={handleTrialSelect}
            onTrialEventClick={async (clickInfo) => {
              const eventObj = clickInfo.event.toPlainObject();
              const trialId = eventObj.extendedProps?.trialId;

              try {
                let trialDetails = null;
                if (trialId) {
                  trialDetails = await trialApi.getTrialDetails(trialId);
                  setSelectedTrial(trialDetails);
                }

                setCurrentEvent({
                  ...eventObj,
                  start: fromServerFormat(eventObj.start),
                  end: fromServerFormat(eventObj.end),
                  extendedProps: {
                    ...eventObj.extendedProps,
                    statusConfig: getStatusConfig(eventObj.extendedProps.status),
                    trialDetails: trialDetails
                  }
                });
                setModalType('view');
              } catch (error) {
                console.error('获取试验详情失败:', error);
                Modal.error({
                  title: '加载失败',
                  content: '无法加载试验详情，请稍后再试'
                });
              }
            }}
          />
        ) : (
          <ScheduleCalendar
            personnel={personnel}
            schedules={schedules}
            isGuest={isGuest}
            onScheduleDateClick={handleScheduleDateClick}
            onScheduleEventClick={(clickInfo) => {
              const eventObj = clickInfo.event.toPlainObject();
              const scheduleId = parseInt(eventObj.id.replace('schedule-', ''));
              const schedule = schedules.find(s => s.id === scheduleId);
              if (schedule) {
                setCurrentSchedule({
                  id: schedule.id,
                  date: schedule.date,
                  staff: schedule.staff,
                  leader: schedule.leader,
                  staffPhone: schedule.staffPhone,
                  leaderPhone: schedule.leaderPhone
                });
                setScheduleModalMode('view');
                setScheduleModalOpen(true);
              }
            }}
            onEventDrop={handleEventDrop}
            onEventDragStart={(info) => {
              info.el.style.opacity = '0.8';
              info.el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
            }}
            onEventDragStop={(info) => {
              info.el.style.opacity = '1';
              info.el.style.boxShadow = 'none';
            }}
          />
        )}
      </div>

      {currentEvent && (
        <EventModal
          form={form}
          currentEvent={currentEvent}
          modalType={modalType}
          trials={trials}
          isGuest={isGuest}
          isEditing={isEditing}
          modifiedSlots={modifiedSlots}
          selectedTrial={selectedTrial}
          handleEventSubmit={handleEventSubmit}
          setCurrentEvent={setCurrentEvent}
          setIsEditing={setIsEditing}
          setModifiedSlots={setModifiedSlots}
          setSelectedTrial={setSelectedTrial}
          calendarApi={calendarApi} // Add this line
        />
      )}

      <PersonnelScheduleModal
        open={scheduleModalOpen}
        onCancel={() => setScheduleModalOpen(false)}
        scheduleData={currentSchedule}
        mode={scheduleModalMode}
        personnelList={personnel}
        onSave={(mode) => {
          if (mode === 'edit') {
            setScheduleModalMode('edit');
          }
          scheduleQueryClient.invalidateQueries(['schedules']);
        }}
        onDelete={() => scheduleQueryClient.invalidateQueries(['schedules'])}
      />
    </div>
  );
};

export default CalendarPage;
