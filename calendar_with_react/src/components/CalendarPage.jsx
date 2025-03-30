import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { calendarApi } from '../api/calendar';
import { getTrials } from '../api/trials';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import { Modal, Button, DatePicker, Form, Select, Descriptions, Badge, Space } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import './CalendarPage.css';

const CalendarPage = () => {
  const { 
    data: trials = [], 
    isLoading: isTrialsLoading 
  } = useQuery({
    queryKey: ['trials'],
    queryFn: () => getTrials().then(res => res.data || []),
    gcTime: 600000,
    staleTime: 300000
  });

  // 不同类型日历的事件数据
  const [defaultEvents, setDefaultEvents] = useState([
    { title: 'Meeting', start: new Date() }
  ]);
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
  
  const statusColors = {
    '进行中': 'processing',
    '已计划': 'success',
    '已取消': 'error',
    '已完成': 'default'
  };

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await calendarApi.fetchCalendarEvents();
        const events = response.data.map(event => ({
          ...event,
          start: new Date(event.start_time),
          end: new Date(event.end_time)
        }));
        setDefaultEvents(events);
      } catch (error) {
        console.error('加载日历事件失败:', error);
      }
    };
    
    document.body.classList.toggle('dark-mode', darkMode);
    fetchEvents();
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  const handleEventSubmit = async (newEvent) => {
    try {
      const payload = {
        title: newEvent.title,
        description: newEvent.description,
        experiment_info: newEvent.experiment_info,
        responsible_person: newEvent.responsible_person,
        train_count: newEvent.train_count || 0,
        trial_id: selectedTrial?.id,
        time_slots: newEvent.time_slots?.map(slot => ({
          start_time: slot.start.toISOString(),
          end_time: slot.end.toISOString()
        }))
      };

      let response;
      if (newEvent.id) {
        response = await calendarApi.updateCalendarEvent(newEvent.id, payload);
      } else {
        response = await calendarApi.createCalendarEvent(payload);
      }

        if (response.status === 200 || response.status === 201) {
          const createdEvent = {
            ...response.data,
            start: new Date(response.data.start_time),
            end: new Date(response.data.end_time),
            type: calendarType
          };
          
          // 统一保存到defaultEvents并根据类型过滤
          setDefaultEvents(prev => [...prev, {
            ...createdEvent,
            type: calendarType === 'trial' ? 'TRIAL' : 'SCHEDULE'
          }]);
        }
    } catch (error) {
      console.error('保存事件失败:', error);
      alert('保存事件失败，请检查网络连接或联系管理员');
    }
    setCurrentEvent(null);
  };

  const handleTrialSelect = async (trialId) => {
    try {
      const { data } = await getTrials({ id: trialId });
      setSelectedTrial(data);
    } catch (error) {
      console.error('获取试验详情失败:', error);
      alert('无法加载试验详情');
    }
  };

  return (
    <div className="calendar-page">
      <div className="calendar-container">
        <div className="calendar-controls">
          <Select
            defaultValue="trial"
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
          events={useMemo(() => {
            return defaultEvents.filter(event => 
              calendarType === 'trial' ? 
              event.type === 'TRIAL' : 
              event.type === 'SCHEDULE'
            );
          }, [calendarType, defaultEvents])}
          dateClick={(arg) => {
            const newEvent = {
              title: '',
              start: arg.date,
              allDay: arg.allDay,
              type: calendarType === 'trial' ? 'TRIAL' : 'SCHEDULE'
            };
            setCurrentEvent(newEvent);
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
        title={modalType === 'view' ? '查看试验排班' : '新建试验排班'}
        open={!!currentEvent}
        onCancel={() => setCurrentEvent(null)}
        footer={[
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
          <Form layout="vertical">
            <Form.Item label="试验项目" required>
              <Select
                showSearch
                placeholder="搜索试验项目"
                options={trials.map(trial => ({
                  value: trial.id,
                  label: `${trial.code} - ${trial.title}`,
                  trial: trial
                }))}
                loading={isTrialsLoading}
                filterOption={(input, option) =>
                  option.label.toLowerCase().includes(input.toLowerCase())
                }
                onChange={(value, option) => {
                  handleTrialSelect(value);
                  setSelectedTrial(option.trial);
                }}
              />
            </Form.Item>

            {selectedTrial && (
              <Descriptions bordered size="small" column={1}>
                <Descriptions.Item label="试验编号">{selectedTrial.code}</Descriptions.Item>
                <Descriptions.Item label="负责人">{selectedTrial.manager}</Descriptions.Item>
                <Descriptions.Item label="当前阶段">{selectedTrial.phase}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Badge status={statusColors[selectedTrial.status]} text={selectedTrial.status} />
                </Descriptions.Item>
              </Descriptions>
            )}

            <Form.List name="time_slots">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item
                        {...restField}
                        name={[name, 'start']}
                        label="开始时间"
                        rules={[{ required: true, message: '请选择开始时间' }]}
                      >
                        <DatePicker showTime format="YYYY-MM-DD HH:mm" />
                      </Form.Item>
                      <Form.Item
                        {...restField}
                        name={[name, 'end']}
                        label="结束时间"
                        rules={[
                          { required: true, message: '请选择结束时间' },
                          ({ getFieldValue }) => ({
                            validator(_, value) {
                              const start = getFieldValue(['time_slots', name, 'start']);
                              if (start && value && value.isBefore(start)) {
                                return Promise.reject(new Error('结束时间不能早于开始时间'));
                              }
                              return Promise.resolve();
                            },
                          }),
                        ]}
                      >
                        <DatePicker showTime format="YYYY-MM-DD HH:mm" />
                      </Form.Item>
                      <MinusCircleOutlined onClick={() => remove(name)} />
                    </Space>
                  ))}
                  <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                    添加时间段
                  </Button>
                </>
              )}
            </Form.List>
          </Form>
        </div>
      </Modal>
    </div>
  );
};

const queryClient = new QueryClient();

export default function CalendarWrapper() {
  return (
    <QueryClientProvider client={queryClient}>
      <CalendarPage />
      <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
    </QueryClientProvider>
  );
}
