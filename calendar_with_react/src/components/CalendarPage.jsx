import React, { useState } from 'react';
import { Modal, Form } from 'antd';
import { calendarApi } from '../api/calendar';
import { trialApi } from '../api/trialApi';
import { getStatusConfig } from '../utils/calendarUtils';
import { useAuth } from '../context/AuthContext';
import { fromServerFormat } from '../utils/dateUtils';
import { useCalendarData } from '../hooks/useCalendarData';
import { useEventService } from '../services/eventService';
import CalendarControls from './Calendar/CalendarControls';
import EventModal from './Calendar/EventModal/EventModal';
import ScheduleModal from './Calendar/ScheduleModal';
import TrialCalendar from './Calendar/TrialCalendar';
import ScheduleCalendar from './Calendar/ScheduleCalendar';
import './CalendarPage.css';

const CalendarPage = () => {
  const [form] = Form.useForm();
  const { isGuest } = useAuth();
  const [modalType, setModalType] = useState('new');
  const [scheduleModalVisible, setScheduleModalVisible] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit');
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState(null);

  // 使用自定义hook获取数据
  const {
    trials,
    schedules,
    personnel,
    defaultEvents,
    darkMode,
    toggleDarkMode,
    calendarType,
    setCalendarType,
    currentEvent,
    setCurrentEvent,
    queryClient
  } = useCalendarData();

  // 使用事件服务
  const { handleEventSubmit } = useEventService(queryClient);

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
    setScheduleModalVisible(true);
  };

  // 处理事件拖放
  const handleEventDrop = async (info) => {
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
  };

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls 
          darkMode={darkMode}
          setDarkMode={toggleDarkMode}
          calendarType={calendarType}
          setCalendarType={setCalendarType}
        />

        {calendarType === 'trial' ? (
          <TrialCalendar
            trials={trials}
            defaultEvents={defaultEvents}
            isGuest={isGuest}
            onTrialDateClick={handleTrialDateClick}
            onTrialSelect={handleTrialSelect}
            onTrialEventClick={async (clickInfo) => {
              const eventObj = clickInfo.event.toPlainObject();
              const trialId = eventObj.extendedProps?.trialId;
              
              try {
                if (trialId) {
                  const trialDetails = await trialApi.getTrialDetails(trialId);
                  setSelectedTrial(trialDetails);
                  
                  setCurrentEvent({
                    ...eventObj,
                    start: fromServerFormat(eventObj.start)?.toDate(),
                    end: fromServerFormat(eventObj.end)?.toDate(),
                    extendedProps: {
                      ...eventObj.extendedProps,
                      statusConfig: getStatusConfig(eventObj.extendedProps.status),
                      trialDetails: trialDetails // 添加试验详情到事件对象
                    }
                  });
                } else {
                  setCurrentEvent({
                    ...eventObj,
                    start: fromServerFormat(eventObj.start)?.toDate(),
                    end: fromServerFormat(eventObj.end)?.toDate(),
                    extendedProps: {
                      ...eventObj.extendedProps,
                      statusConfig: getStatusConfig(eventObj.extendedProps.status)
                    }
                  });
                }
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
            defaultEvents={defaultEvents}
            isGuest={isGuest}
            onScheduleDateClick={handleScheduleDateClick}
            onScheduleEventClick={(clickInfo) => {
              const eventObj = clickInfo.event.toPlainObject();
              const schedule = schedules.find(s => s.id === eventObj.id);
              if (schedule) {
                setCurrentSchedule(schedule);
                setScheduleModalMode('view');
                setScheduleModalVisible(true);
                
                // 同时设置currentEvent以显示EventModal
                setCurrentEvent({
                  ...eventObj,
                  extendedProps: {
                    ...eventObj.extendedProps,
                    scheduleDetails: schedule
                  }
                });
                setModalType('view');
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
            select={() => {}}
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
