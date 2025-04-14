import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import moment from 'moment';
import CalendarControls from './Calendar/CalendarControls';
import EventModal from './Calendar/EventModal/EventModal';
import {
  useQuery,
  useQueryClient
} from '@tanstack/react-query';
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
import './CalendarPage.css';

// 基于trialId生成HSL颜色 (改进版)
const getTrialColor = (trialId) => {
  // djb2哈希算法
  let hash = 5381;
  for (let i = 0; i < String(trialId).length; i++) {
    hash = (hash * 33) ^ String(trialId).charCodeAt(i);
  }
  
  // 使用黄金角度分布色相 (137.5°)
  const hue = (hash * 137.5) % 360;
  // 使用正常饱和度和亮度
  const saturation = 85; // 正常饱和度
  const lightness = 55; // 正常亮度
  
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

// 状态配置对象
const trialStatusConfig = {
  planned: {
    color: '#1890ff', // 蓝色
    text: '已计划', 
    icon: '🗓️',
    badgeStyle: { backgroundColor: '#1890ff' }
  },
  in_progress: {
    color: '#52c41a', // 绿色
    text: '进行中',
    icon: '🔄',
    badgeStyle: { backgroundColor: '#52c41a' }
  },
  completed: {
    color: '#888', // 灰色
    text: '已完成',
    icon: '✅',
    badgeStyle: { backgroundColor: '#888' }
  },
  cancelled: {
    color: '#ff4d4f', // 红色
    text: '已取消',
    icon: '❌',
    badgeStyle: { backgroundColor: '#ff4d4f' }
  }
};

const CalendarPage = () => {
  const { isGuest } = useAuth();
  const queryClient = useQueryClient();
  const {
    data: trials = [],
    isLoading: isTrialsLoading
  } = useQuery({
    queryKey: ['trials'],
    queryFn: () => getTrials().then(res => Array.isArray(res?.results) ? res.results : []),
    gcTime: 600000,
    staleTime: 300000
  });

  const {
    data: schedules = [],
    isLoading: isSchedulesLoading
  } = useQuery({
    queryKey: ['schedules'],
    queryFn: () => calendarApi.getSchedules(),
    gcTime: 600000,
    staleTime: 300000
  });

  const {
    data: personnel = [],
    isLoading: isPersonnelLoading
  } = useQuery({
    queryKey: ['personnel'],
    queryFn: () => calendarApi.getPersonnel(),
    gcTime: 600000,
    staleTime: 300000
  });

  const [scheduleModalVisible, setScheduleModalVisible] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleModalMode, setScheduleModalMode] = useState('edit'); // 'view' | 'edit'

  // 不同类型日历的事件数据
  const [defaultEvents, setDefaultEvents] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [calendarType, setCalendarType] = useState('trial'); // 初始设为试验日历

  // 日历类型选项
  const calendarOptions = [
    { value: 'trial', label: '试验日历' },
    { value: 'schedule', label: '排班日历' },
  ];
  const [modalType, setModalType] = useState('new'); // 'view' | 'edit' | 'new'
  const [currentEvent, setCurrentEvent] = useState(null);
  const [selectedTrial, setSelectedTrial] = useState(null);
  const [form] = Form.useForm();
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);

  const getStatusConfig = (status) =>
    trialStatusConfig[status] || {
      color: '#d3d3d3',
      text: '未知状态',
      icon: '❓',
      badgeStyle: { backgroundColor: '#d3d3d3' }
    };

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await calendarApi.fetchTimeSlotsByTrial();
        const events = response.data.map(trial => ({
          title: trial.trial_name,
          start: fromServerFormat(trial.start_date)?.toDate(),
          end: fromServerFormat(trial.end_date)?.toDate(),
          extendedProps: {
            status: trial.status,
            responsible: trial.responsible_persons,
            trialId: trial.id
          }
        }));
        setDefaultEvents(events);
      } catch (error) {
        console.error('加载试验日历失败:', error);
      }
    };

    document.body.classList.toggle('dark-mode', darkMode);
    fetchEvents();
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  const extractSlotId = (compositeId) => {
    console.log('[DEBUG] 正在解析ID:', compositeId);
    
    // 处理 'trial-1-0' 格式 (提取 slotId)
    if (typeof compositeId === 'string' && compositeId.startsWith('trial-')) {
      const match = compositeId.match(/trial-(\d+)-(\d+)/);
      if (match) {
        const trialId = parseInt(match[1]);
        const slotIndex = parseInt(match[2]);
        console.log('[DEBUG] 从 trial-id 格式提取出 trialId:', trialId, 'slotIndex:', slotIndex);
        return { trialId, slotIndex };
      }
      return null;
    }
    
    // 处理 'slot_1' 格式 (提取 slotId)
    if (typeof compositeId === 'string' && compositeId.startsWith('slot_')) {
      const id = parseInt(compositeId.replace('slot_', ''));
      console.log('[DEBUG] 从 slot_id 格式提取出:', id);
      return { slotId: id };
    }
    
    // 处理 '1-0' 格式 (提取 trialId 和 slotIndex)
    if (typeof compositeId === 'string' && /^\d+-\d+$/.test(compositeId)) {
      const [trialId, slotIndex] = compositeId.split('-').map(Number);
      console.log('[DEBUG] 从 1-0 格式提取出 trialId:', trialId, 'slotIndex:', slotIndex);
      return { trialId, slotIndex };
    }
    
    // 处理直接数字ID
    if (!isNaN(parseInt(compositeId))) {
      const id = parseInt(compositeId);
      console.log('[DEBUG] 直接解析数字ID:', id);
      return { slotId: id };
    }
    
    console.error('[ERROR] 无法解析ID:', compositeId);
    throw new Error(`无效的时间段ID格式: ${compositeId}`);
  };

  const handleEventSubmit = async (newEvent) => {
    try {
      const trialId = form.getFieldValue('trial');
      if (!trialId) {
        alert('请先选择试验项目');
        return;
      }

      // 获取选中的试验项目数据
      const selectedTrialData = trials.find(t => t.id === trialId);
      if (!selectedTrialData) {
        alert('无效的试验项目');
        return;
      }

      // 确保time_slots存在且为数组，添加防御性检查
      const timeSlots = (Array.isArray(newEvent.time_slots) ? newEvent.time_slots : [])
        .filter(slot => slot?.start && slot?.end) // 过滤无效时间段
        .map(slot => ({
          start: fromServerFormat(slot.start)?.toDate(),
          end: fromServerFormat(slot.end)?.toDate(),
          description: slot.description || ''
        }));

      // 添加调试日志
      console.log('Time slots data:', timeSlots);

      let response;
      if (newEvent.id && timeSlots.length > 0) {
        // 统一使用批量更新接口
        const slotInfo = extractSlotId(newEvent.id);
        if (!slotInfo) {
          console.error('[DEBUG] 无法从ID提取有效的slot信息:', newEvent.id);
          throw new Error('无效的时间段ID格式');
        }
        
        console.log('[DEBUG] 解析出的slot信息:', slotInfo);
        
        // 构造批量更新数据
        const updateData = [{
          id: slotInfo.slotId || `${slotInfo.trialId}-${slotInfo.slotIndex}`,
          start: timeSlots[0].start,
          end: timeSlots[0].end,
          description: timeSlots[0].description
        }];
        
        console.log('[DEBUG] 准备批量更新时间段数据:', updateData);
        response = await calendarApi.bulkUpdateTimeSlots(updateData);
      } else if (timeSlots.length > 0) {
        // 创建时间段
        if (timeSlots.length > 1) {
          console.log('[DEBUG] 批量创建多个时间段:', timeSlots.length);
          response = await calendarApi.bulkCreateTimeSlots(trialId, timeSlots);
        } else {
          console.log('[DEBUG] 创建单个新时间段');
          console.log('时间段:', timeSlots);
          console.log('start_time:', toServerFormat(timeSlots[0].start));
          console.log('end_time:', toServerFormat(timeSlots[0].end));
          
          response = await calendarApi.createTimeSlot({
            trial: trialId,
            start_time: toServerFormat(timeSlots[0].start),
            end_time: toServerFormat(timeSlots[0].end),
            description: timeSlots[0].description
          });
        }
      } else {
        // 没有时间段要更新
        console.log('[DEBUG] 没有时间段需要更新');
        // 这里可以添加提示或其他处理逻辑
        response = { success: true };
      }

      // 处理响应
      const eventsToAdd = Array.isArray(response) ?
        response.map(slot => ({
          id: `slot_${slot.id}`,
          title: selectedTrialData.title,
          start: fromServerFormat(slot.start_time)?.toDate(),
          end: fromServerFormat(slot.end_time)?.toDate(),
          extendedProps: {
            trialId: trialId,
            description: slot.description
          }
        })) :
        [{
          id: `slot_${response.id}`,
          title: selectedTrialData.title,
          start: fromServerFormat(response.start_time)?.toDate(),
          end: fromServerFormat(response.end_time)?.toDate(),
          extendedProps: {
            trialId: trialId,
            description: response.description
          }
        }];

      // 更新本地状态
      if (newEvent.id) {
        // 更新现有事件
        setDefaultEvents(prev => 
          prev.map(event => 
            event.id === newEvent.id ? 
              eventsToAdd[0] : 
              event
          )
        );
      } else {
        // 添加新事件
        setDefaultEvents(prev => [...prev, ...eventsToAdd]);
      }
      
      // 重新获取数据
      queryClient.invalidateQueries(['trials']);
      const freshTrials = await getTrials();
      setSelectedTrial(freshTrials.results.find(t => t.id === trialId));
    } catch (error) {
      console.error('保存时间段失败:', error);
      alert(`保存时间段失败: ${error.message}`);
    }
    setCurrentEvent(null);
  };

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <CalendarControls 
          darkMode={darkMode}
          setDarkMode={setDarkMode}
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
              // 转换试验数据为日历事件（使用实际时间段）
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
              // 转换排班数据为日历事件
              return schedules.map(schedule => ({
                id: schedule.id,
                title: `${schedule.staff} (${schedule.leader})`,
                start: schedule.date,
                allDay: true,
                extendedProps: {
                  type: 'SCHEDULE',
                  staff: schedule.staff,
                  leader: schedule.leader,
                  staffPhone: personnel.find(p => p.id === schedule.staff)?.phone || '无',
                  leaderPhone: personnel.find(p => p.id === schedule.leader)?.phone || '无'
                },
                color: '#4CAF50',
                display: 'background',
                textColor: '#ffffff',
                editable: !isGuest,
                tooltip: {
                  title: `${schedule.staff} 值班`,
                  description: `
                    日期: ${schedule.date}
                    值班人: ${schedule.staff} (${schedule.staffPhone})
                    值班领导: ${schedule.leader} (${schedule.leaderPhone})
                  `,
                  backgroundColor: '#4CAF50'
                }
              }));
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
                // 获取试验详情
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
                
                // 检查目标日期是否已有排班
                const targetSchedule = schedules.find(s => s.date === newDate);
                if (targetSchedule) {
                  // 交换两个排班的日期
                  await calendarApi.swapScheduleDates(scheduleId, targetSchedule.id);
                } else {
                  // 仅更新当前排班的日期
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
            // 添加拖拽结束时的视觉反馈
            info.el.style.opacity = '1';
            info.el.style.boxShadow = 'none';
          }}
          eventDragStart={(info) => {
            // 添加拖拽开始时的视觉反馈
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
