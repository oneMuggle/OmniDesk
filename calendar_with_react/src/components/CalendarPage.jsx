import React, { useState, useEffect, useMemo } from 'react';
import {
  useQuery,
  useQueryClient
} from '@tanstack/react-query';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import zhCnLocale from '@fullcalendar/core/locales/zh-cn';
import { Tooltip } from 'react-tooltip';
import { Modal, Button, DatePicker, Form, Select, Descriptions, Badge, Space, Input } from 'antd';
import { fromServerFormat, toServerFormat } from '../utils/dateUtils';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { calendarApi } from '../api/calendar';
import { getTrials, getTrialById } from '../api/trials';
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
  const queryClient = useQueryClient();
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
  const [form] = Form.useForm();

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

  const handleEventSubmit = async (newEvent) => {
    try {
      if (!selectedTrial) {
        alert('请先选择试验项目');
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
      if (timeSlots.length > 1) {
        // 批量创建时间段
        response = await calendarApi.bulkCreateTimeSlots(selectedTrial.id, timeSlots);
      } else if (newEvent.id) {
        // 更新单个时间段
        response = await calendarApi.updateTimeSlot(newEvent.id, {
          trial: selectedTrial.id,
          start_time: toServerFormat(timeSlots[0].start),
          end_time: toServerFormat(timeSlots[0].end),
          description: timeSlots[0].description
        });
      } else {
        console.error('时间段:', timeSlots);
        console.error('start_time:', toServerFormat(timeSlots[0].start));
        console.error('end_time:', toServerFormat(timeSlots[0].end));
        // 创建单个时间段
        response = await calendarApi.createTimeSlot({
          trial: selectedTrial.id,
          start_time: toServerFormat(timeSlots[0].start),
          end_time: toServerFormat(timeSlots[0].end),
          description: timeSlots[0].description
        });
      }

      // 处理响应
      const eventsToAdd = Array.isArray(response) ?
        response.map(slot => ({
          id: `slot_${slot.id}`,
          title: selectedTrial.title,
          start: fromServerFormat(slot.start_time)?.toDate(),
          end: fromServerFormat(slot.end_time)?.toDate(),
          extendedProps: {
            trialId: selectedTrial.id,
            description: slot.description
          }
        })) :
        [{
          id: `slot_${response.id}`,
          title: selectedTrial.title,
          start: fromServerFormat(response.start_time)?.toDate(),
          end: fromServerFormat(response.end_time)?.toDate(),
          extendedProps: {
            trialId: selectedTrial.id,
            description: response.description
          }
        }];

      setDefaultEvents(prev => [...prev, ...eventsToAdd]);
      queryClient.invalidateQueries(['trials']);
    } catch (error) {
      console.error('保存时间段失败:', error);
      alert(`保存时间段失败: ${error.message}`);
    }
    setCurrentEvent(null);
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
            // 转换试验数据为日历事件（使用实际时间段）
            const trialEvents = trials.flatMap(trial =>
              (trial.time_slots || []).map((slot, index) => ({
                id: `trial-${trial.id}-${index}`,
                title: trial.title,
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
                color: getStatusConfig(trial.status).color,
                allDay: false,
                editable: false
              }))
            );

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
          eventClick={async (clickInfo) => {
            const eventObj = clickInfo.event.toPlainObject();
            try {
              if (eventObj.extendedProps?.type === 'TRIAL') {
                // 获取试验详情
                console.error('Trial event clicked:', eventObj);
                console.error('trialId:', eventObj.extendedProps.trialId);
                const { data } = await getTrialById(eventObj.extendedProps.trialId);
                console.log('Trial API response:', data);
                console.error('Trial API response:', {
                  data: data,
                  equipment: data?.equipments,
                  persons: data?.responsible_persons,
                  time_slots: data?.time_slots
                });
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
              } else {
                // 获取排班详情
                const response = await calendarApi.fetchTimeSlotsByTrial(eventObj.extendedProps?.trialId);
                const slotDetails = response.find(slot => slot.id === eventObj.id.replace('slot_', ''));
                setCurrentEvent({
                  ...eventObj,
                  start: fromServerFormat(eventObj.start)?.toDate(),
                  end: fromServerFormat(eventObj.end)?.toDate(),
                  extendedProps: {
                    ...eventObj.extendedProps,
                    description: slotDetails?.description,
                    trialTitle: slotDetails?.trialTitle
                  }
                });
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
          editable={true}
          selectable={true}
          height="auto"
          firstDay={1}
        />
      </div>

      {currentEvent && (
        <Modal
          title={modalType === 'view' ? '查看试验排班' : '新建试验排班'}
          open={!!currentEvent}
          onCancel={() => setCurrentEvent(null)}
          width={800}
          footer={[
            ...(modalType === 'view' ? [
              <Button
                key="edit"
                type="primary"
                onClick={() => {
                  setModalType('edit');
                  form.setFieldsValue({
                    trial: currentEvent.extendedProps.trialId,
                    time_slots: currentEvent.extendedProps.timeSlots?.map(slot => ({
                      start: fromServerFormat(slot.start_time)?.toDate(),
                      end: fromServerFormat(slot.end_time)?.toDate(),
                      description: slot.description,
                      id: slot.id
                    })) || []
                  });
                }}
              >
                编辑
              </Button>,
              <Button
                key="delete"
                danger
                onClick={async () => {
                  Modal.confirm({
                    title: '确认删除',
                    content: currentEvent.extendedProps?.type === 'TRIAL' ?
                      '确定要删除这个试验及其所有排班吗？' :
                      '确定要删除这个排班吗？',
                    okText: '确认',
                    cancelText: '取消',
                    onOk: async () => {
                      try {
                        if (currentEvent.extendedProps?.type === 'TRIAL') {
                          await calendarApi.deleteCalendarEvent(currentEvent.extendedProps.trialId);
                        } else {
                          await calendarApi.deleteTimeSlot(currentEvent.id.replace('slot_', ''));
                        }
                        setDefaultEvents(prev =>
                          prev.filter(e => e.id !== currentEvent.id)
                        );
                        setCurrentEvent(null);
                        queryClient.invalidateQueries(['trials']);
                      } catch (error) {
                        console.error('删除失败:', error);
                        Modal.error({
                          title: '删除失败',
                          content: error.message,
                        });
                      }
                    }
                  });
                }}
              >
                删除
              </Button>
            ] : []),
            <Button
              key="submit"
              type="primary"
              onClick={() => {
                if (modalType === 'view') {
                  setCurrentEvent(null);
                  return;
                }

                // 增强的时间段验证逻辑
                const formValues = form.getFieldsValue(true);
                console.log('原始表单数据:', formValues);

                // 验证time_slots数据结构
                const timeSlots = formValues.time_slots || [];
                if (!Array.isArray(timeSlots)) {
                  console.error('time_slots字段不是数组:', formValues);
                  alert('表单数据异常: 时间段数据格式不正确');
                  return;
                }

                // 检查每个时间段的有效性
                const invalidSlots = [];
                const validSlots = timeSlots.map((slot, index) => {
                  if (!slot?.start || !slot?.end) {
                    invalidSlots.push(`时间段 ${index + 1}: 缺少开始或结束时间`);
                    return null;
                  }

                  try {
                    const start = fromServerFormat(slot.start);
                    const end = fromServerFormat(slot.end);

                    if (!start || !end) {
                      invalidSlots.push(`时间段 ${index + 1}: 时间格式无效`);
                      return null;
                    }

                    const startDate = start.toDate();
                    const endDate = end.toDate();

                    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
                      invalidSlots.push(`时间段 ${index + 1}: 时间格式无效`);
                      return null;
                    }

                    if (endDate <= startDate) {
                      invalidSlots.push(`时间段 ${index + 1}: 结束时间必须晚于开始时间`);
                      return null;
                    }

                    return {
                      start,
                      end,
                      ...(slot.id && { id: slot.id })
                    };
                  } catch (error) {
                    invalidSlots.push(`时间段 ${index + 1}: ${error.message}`);
                    return null;
                  }
                }).filter(Boolean);

                // 如果有无效时间段，显示详细错误
                if (invalidSlots.length > 0 || validSlots.length === 0) {
                  const errorMessage = [
                    '请修正以下问题:',
                    ...invalidSlots,
                    validSlots.length === 0 ? '至少需要一个有效时间段' : ''
                  ].join('\n');

                  console.error('时间段验证失败:', {
                    formValues,
                    invalidSlots,
                    validSlots
                  });

                  alert(errorMessage);
                  return;
                }

                const formData = {
                  ...currentEvent,
                  ...formValues,
                  time_slots: validSlots
                };
                console.log('验证后的表单数据:', {
                  ...formData,
                  time_slots: formData.time_slots.map(slot => ({
                    start: toServerFormat(slot.start),
                    end: toServerFormat(slot.end),
                    duration: slot.end - slot.start
                  }))
                });
                handleEventSubmit(formData);
              }}
            >
              {modalType === 'view' ? '关闭' : '保存'}
            </Button>
          ]}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Form
              layout="vertical"
              form={form}
              initialValues={{ time_slots: [] }}
            >
              <Form.Item label="试验项目" required name="trial">
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
                          getValueProps={(value) => ({ value: value ? fromServerFormat(value) : null })}
                        >
                          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" />
                        </Form.Item>
                        <Form.Item
                          {...restField}
                          name={[name, 'end']}
                          label="结束时间"
                          rules={[{ required: true, message: '请选择结束时间' }]}
                          getValueProps={(value) => ({ value: value ? fromServerFormat(value) : null })}
                        >
                          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" />
                        </Form.Item>
                        <Form.Item
                          {...restField}
                          name={[name, 'description']}
                          label="描述"
                        >
                          <Input.TextArea rows={1} />
                        </Form.Item>
                        <MinusCircleOutlined onClick={() => remove(name)} />
                      </Space>
                    ))}
                    <Form.Item>
                      <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                        添加时间段
                      </Button>
                    </Form.Item>
                  </>
                )}
              </Form.List>
            </Form>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default CalendarPage;
