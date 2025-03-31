import React, { useState, useEffect, useMemo } from 'react';
import { 
  useQuery, 
  QueryClient, 
  QueryClientProvider 
} from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import { Modal, Button, DatePicker, Form, Select, Descriptions, Badge, Space } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { calendarApi } from '../api/calendar';
import { getTrials } from '../api/trials';
import './CalendarPage.css';

// 状态配置对象
const trialStatusConfig = {
  planned: {
    color: '#1890ff',
    text: '已计划',
    icon: '🗓️',
    badgeStyle: { backgroundColor: '#1890ff' }
  },
  in_progress: {
    color: '#52c41a', 
    text: '进行中',
    icon: '🔄',
    badgeStyle: { backgroundColor: '#52c41a' }
  },
  completed: {
    color: '#888',
    text: '已完成', 
    icon: '✅',
    badgeStyle: { backgroundColor: '#888' }
  },
  cancelled: {
    color: '#ff4d4f',
    text: '已取消',
    icon: '❌',
    badgeStyle: { backgroundColor: '#ff4d4f' }
  }
};

const CalendarPage = () => {
  const { 
    data: trials = [], 
    isLoading: isTrialsLoading 
  } = useQuery({
    queryKey: ['trials'],
    queryFn: () => getTrials().then(res => res.results || []), 
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
      if (!selectedTrial) {
        alert('请先选择试验项目');
        return;
      }

      const payload = {
        title: selectedTrial.title,
        description: selectedTrial.description,
        client: selectedTrial.client,
        trial_id: selectedTrial.id,
        time_slots: newEvent.time_slots?.map(slot => ({
          start_time: slot.start.toISOString(),
          end_time: slot.end.toISOString()
        })),
        status: selectedTrial.status,
        related_equipment: selectedTrial.related_equipment.map(e => e.id),
        responsible_persons: selectedTrial.responsible_persons.map(p => p.id)
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
            // 转换试验数据为日历事件
            const trialEvents = trials.map(trial => ({
              id: `trial-${trial.id}`,
              title: trial.title,
              start: new Date(trial.start_date),
              end: new Date(trial.end_date),
              extendedProps: {
                type: 'TRIAL',
                status: trial.status,
                client: trial.client,
                equipment: trial.related_equipment,
                persons: trial.responsible_persons,
                description: trial.description
              },
              color: getStatusConfig(trial.status).color,
              allDay: true,
              editable: false
            }));

            // 合并已有事件和试验事件
            return [...defaultEvents, ...trialEvents].filter(event => 
              calendarType === 'trial' ? 
              event.extendedProps?.type === 'TRIAL' : 
              event.extendedProps?.type === 'SCHEDULE'
            );
          }, [calendarType, defaultEvents, trials])}
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
            const eventObj = clickInfo.event.toPlainObject();
            if (eventObj.extendedProps?.type === 'TRIAL') {
              setCurrentEvent({
                ...eventObj,
                start: new Date(eventObj.start),
                end: new Date(eventObj.end),
                extendedProps: {
                  ...eventObj.extendedProps,
                  statusConfig: getStatusConfig(eventObj.extendedProps.status)
                }
              });
              setModalType('view');
            } else {
              setCurrentEvent({
                ...eventObj,
                start: new Date(eventObj.start),
                end: new Date(eventObj.end)
              });
              setModalType('view');
            }
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
                filterOption={(input, option) =>
                  `${option.label} ${option.value}`.toLowerCase().includes(input.toLowerCase())
                }
                options={trials.map(trial => ({
                  value: trial.id,
                  label: `${trial.title} (${trial.client})`,
                  trialData: trial
                }))}
                optionFilterProp="label"
                onSearch={value => {
                  // 触发API搜索
                  getTrials({ search: value });
                }}
                loading={isTrialsLoading}
                onChange={(value, option) => {
                  if (!option) {
                    setSelectedTrial(null);
                    return;
                  }
                  setSelectedTrial(option.trialData);
                }}
              />
            </Form.Item>

            {selectedTrial && (
              <>
                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="客户单位">{selectedTrial.client}</Descriptions.Item>
                  <Descriptions.Item label="试验描述">{selectedTrial.description}</Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Badge 
                      status={getStatusConfig(selectedTrial.status).badgeStyle.backgroundColor}
                      text={trialStatusConfig[selectedTrial.status]?.text || '未知状态'}
                    />
                  </Descriptions.Item>
                </Descriptions>

                {selectedTrial?.related_equipment?.length > 0 && (
                  <Descriptions 
                    title="相关设备" 
                    bordered 
                    size="small" 
                    column={1}
                    style={{ marginTop: 16 }}
                  >
                    {selectedTrial.related_equipment.map((equip, index) => (
                      <Descriptions.Item 
                        key={equip.id} 
                        label={`设备 ${index + 1}`}
                      >
                        <div>
                          <div>名称：{equip.name}</div>
                          <div>描述：{equip.description || '暂无描述'}</div>
                        </div>
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                )}

                {selectedTrial?.related_equipment?.length === 0 && (
                  <div style={{ marginTop: 16, color: '#999' }}>
                    暂无相关设备信息
                  </div>
                )}
              </>
            )}
          </Form>
          <Form layout="vertical">
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
}

const queryClient = new QueryClient();

export default function CalendarWrapper() {
  return (
    <QueryClientProvider client={queryClient}>
      <CalendarPage />
      <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
    </QueryClientProvider>
  );
}
