import { useState, useEffect, useRef, useMemo } from 'react';
import { useQueryClient, useQuery, useMutation } from '@tanstack/react-query';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Radio, Switch, Popconfirm } from 'antd';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { scheduleApi } from '../api/scheduleApi';
import { getPositions } from '../../personnel/api/personnelApi';
import axiosInstance from '../../../shared/api/axiosConfig';
import { getPersonnelSequences, getLeaderSequences } from '../../../shared/api/sequenceApi';
import '../../../shared/components/styles/Schedule.css';
import dayjs from 'dayjs';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import PersonnelSequenceModal from '../../../shared/components/Schedule/PersonnelSequenceModal';
import WeeklyLeaderDisplay from '../../../shared/components/Schedule/WeeklyLeaderDisplay';
import MonthlyLeaderSidebar from '../../../shared/components/Schedule/MonthlyLeaderSidebar';
import { DragDropContext } from '@hello-pangea/dnd';
import { logger } from '../../../shared/utils/logger';
import { computeWeeklyLeaders } from '../utils/computeWeeklyLeaders';

const { Option } = Select;

import PropTypes from 'prop-types';

const ScheduleFormModal = ({ open, onCancel, onOk, initialValues, personnelList, positions }) => {
  const [form] = Form.useForm();
  const selectedPersonPositionId = Form.useWatch('person_position_filter', form);
  const selectedLeaderPositionId = Form.useWatch('leader_position_filter', form);

  // Use initialValues as fallback when Form.useWatch hasn't picked up the value yet
  const effectivePersonPositionId = selectedPersonPositionId ?? initialValues?.person_position_filter;
  const effectiveLeaderPositionId = selectedLeaderPositionId ?? initialValues?.leader_position_filter;

  // Get currently selected person/leader IDs to ensure they're always in the options
  const selectedPersonId = Form.useWatch('duty_person', form);
  const selectedLeaderId = Form.useWatch('duty_leader', form);

  const filteredDutyPersonList = useMemo(() => {
    if (!effectivePersonPositionId) return personnelList;
    const filteredPersonnel = personnelList.filter(p => {
      // Always include the currently selected person
      if (selectedPersonId != null && Number(p.id) === Number(selectedPersonId)) return true;
      return Number(p.position?.id) === Number(effectivePersonPositionId);
    });
    return filteredPersonnel;
  }, [personnelList, effectivePersonPositionId, selectedPersonId]);

  const filteredDutyLeaderList = useMemo(() => {
    if (!effectiveLeaderPositionId) return personnelList;
    const filteredLeaders = personnelList.filter(p => {
      // Always include the currently selected leader
      if (selectedLeaderId != null && Number(p.id) === Number(selectedLeaderId)) return true;
      return Number(p.position?.id) === Number(effectiveLeaderPositionId);
    });
    return filteredLeaders;
  }, [personnelList, effectiveLeaderPositionId, selectedLeaderId]);

  // Sync form values when modal opens with new initialValues
  useEffect(() => {
    if (open) {
      // Set form values explicitly
      form.setFieldsValue(initialValues || {});
    } else {
      form.resetFields();
    }
  }, [open]);


  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          date: values.date ? values.date.format('YYYY-MM-DD') : null,
          duty_person_id: values.duty_person, // 映射到后端期望的字段名
          duty_leader_id: values.duty_leader, // 映射到后端期望的字段名
          // 移除 person_position_filter 和 leader_position_filter，它们只用于前端筛选
        };
        onOk(submitData);
        form.resetFields();
      })
      .catch(() => {
      });
  };

  return (
    <Modal
      title={initialValues.id ? "编辑排班" : "新增排班"}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnHidden
      data-testid="schedule-modal"
      footer={[
        <Button key="back" onClick={onCancel}>
          取消
        </Button>,
        <Button key="submit" type="primary" onClick={handleOk} data-testid="schedule-modal-ok-button">
          确定
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        key={initialValues.id || 'new'}
        initialValues={initialValues}
      >
        <Form.Item
          name="date"
          label="值班日期"
          rules={[{ required: true, message: '请选择值班日期!' }]}
        >
          <DatePicker style={{ width: '100%' }} data-testid="schedule-modal-date-picker" />
        </Form.Item>
        <Form.Item
          name="person_position_filter"
          label="值班人员职务筛选"
        >
          <Select
            placeholder="按职务筛选值班人员"
            allowClear
          >
            {positions.map(position => (
              <Option key={position.id} value={position.id}>
                {position.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="duty_person"
          label="值班人员"
          rules={[{ required: true, message: '请选择值班人员!' }]}
        >
          <Select
            placeholder="选择值班人员"
            showSearch
            data-testid="schedule-modal-duty-person-select"
            classNames={{ popup: { root: 'duty-person-select-dropdown' } }}
            filterOption={(input, option) =>
              (option?.children ?? []).join('').toLowerCase().includes(input.toLowerCase())
            }
          >
            {filteredDutyPersonList.map(user => (
              <Select.Option key={user.id} value={user.id} data-testid={`duty-person-option-${user.id}`}>
                {user.position?.name ? `${user.name} (${user.position.name})` : user.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        {initialValues?.duty_person_phone && (
          <Form.Item label="值班人员电话">
            <Input value={initialValues.duty_person_phone} readOnly data-testid="schedule-modal-duty-person-phone" />
          </Form.Item>
        )}
        <Form.Item
          name="leader_position_filter"
          label="值班领导职务筛选"
        >
          <Select
            placeholder="按职务筛选值班领导"
            allowClear
          >
            {positions.map(position => (
              <Option key={position.id} value={position.id}>
                {position.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="duty_leader"
          label="值班领导"
          rules={[{ required: true, message: '请选择值班领导!' }]}
        >
          <Select
            placeholder="选择值班领导"
            showSearch
            data-testid="schedule-modal-duty-leader-select"
            classNames={{ popup: { root: 'duty-leader-select-dropdown' } }}
            filterOption={(input, option) =>
              (option?.children ?? []).join('').toLowerCase().includes(input.toLowerCase())
            }
          >
            {filteredDutyLeaderList.map(user => (
              <Select.Option key={user.id} value={user.id} data-testid={`duty-leader-option-${user.id}`}>
                {user.position?.name ? `${user.name} (${user.position.name})` : user.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        {initialValues?.duty_leader_phone && (
          <Form.Item label="值班领导电话">
            <Input value={initialValues.duty_leader_phone} readOnly data-testid="schedule-modal-duty-leader-phone" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
};

ScheduleFormModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  initialValues: PropTypes.object,
  personnelList: PropTypes.array.isRequired,
  positions: PropTypes.array.isRequired,
};

ScheduleFormModal.defaultProps = {
  initialValues: {},
};



const GenerateScheduleModal = ({ open, onCancel, onOk, personnelSequences, leaderSequences }) => {
  const [form] = Form.useForm();
  const [generationMode, setGenerationMode] = useState('days');
  const [selectedPersonnel, setSelectedPersonnel] = useState([]);
  const [selectedHolidayPersonnel, setSelectedHolidayPersonnel] = useState([]);
  const [selectedLeaders, setSelectedLeaders] = useState([]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = { ...values };
        if (values.start_date) {
          submitData.start_date = values.start_date.format('YYYY-MM-DD');
        }
        if (values.target_month) {
          submitData.target_month = values.target_month.format('YYYY-MM');
        }
        onOk(submitData);
        form.resetFields();
        setSelectedPersonnel([]);
        setSelectedHolidayPersonnel([]);
        setSelectedLeaders([]);
      })
      .catch(() => {
      });
  };

  const handleSequenceChange = (type, sequenceId) => {
    if (type === 'workday') {
      const sequence = personnelSequences.find(s => s.id === sequenceId);
      const personnelDetails = sequence?.personnel_details;
      setSelectedPersonnel(personnelDetails || []);
      form.setFieldsValue({ start_personnel_id: null });
    } else if (type === 'holiday') {
      const sequence = personnelSequences.find(s => s.id === sequenceId);
      setSelectedHolidayPersonnel(sequence?.personnel_details || []);
      form.setFieldsValue({ start_holiday_personnel_id: null });
    } else if (type === 'leader') {
      const sequence = leaderSequences.find(s => s.id === sequenceId);
      setSelectedLeaders(sequence?.personnel_details || []);
      form.setFieldsValue({ start_leader_id: null });
    }
  };

  return (
    <Modal title="生成排班" open={open} onOk={handleOk} onCancel={onCancel} destroyOnHidden data-testid="generate-schedule-modal">
      <Form form={form} layout="vertical" initialValues={{ generationMode: 'days' }}>
        <Form.Item name="generationMode" label="生成方式">
          <Radio.Group onChange={(e) => setGenerationMode(e.target.value)}>
            <Radio value="days">按天数</Radio>
            <Radio value="month">按月份</Radio>
          </Radio.Group>
        </Form.Item>

        {generationMode === 'days' ? (
          <>
            <Form.Item name="start_date" label="起始日期" rules={[{ required: true, message: '请选择起始日期!' }]}>
              <DatePicker style={{ width: '100%' }} data-testid="generate-schedule-start-date" />
            </Form.Item>
            <Form.Item name="duration_days" label="生成天数" initialValue={30} rules={[{ required: true, message: '请输入生成天数!' }]}>
              <Input type="number" data-testid="generate-schedule-duration-days" />
            </Form.Item>
          </>
        ) : (
          <Form.Item name="target_month" label="选择月份" rules={[{ required: true, message: '请选择月份!' }]}>
            <DatePicker picker="month" style={{ width: '100%' }} data-testid="generate-schedule-target-month" />
          </Form.Item>
        )}

        <Form.Item name="workday_personnel_sequence_id" label="人员顺序 (工作日)" rules={[{ required: true, message: '请选择工作日人员顺序!' }]}>
          <Select placeholder="选择工作日人员顺序" onChange={(value) => handleSequenceChange('workday', value)} data-testid="generate-schedule-workday-personnel-sequence" classNames={{ popup: { root: 'workday-sequence-select-dropdown' } }}>
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id} data-testid={`workday-sequence-option-${seq.id}`}>
                {seq.name} (工作日: {Array.isArray(seq.personnel_details) ? seq.personnel_details.map(p => p.name).join(', ') : ''})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_personnel_id" label="起始人员 (工作日)">
          <Select placeholder="选择工作日起始人员" allowClear data-testid="generate-schedule-start-personnel" classNames={{ popup: { root: 'start-personnel-select-dropdown' } }}>
            {
              (() => {
                if (!Array.isArray(selectedPersonnel)) {
                  return null;
                }
                const filteredPersonnel = selectedPersonnel.filter(p => p && p.id != null);
                
                const weekdayPersonnelOptions = filteredPersonnel.map(p => (
                  <Option key={p.id} value={p.id} data-testid={`start-personnel-option-${p.id}`}>{p.name}</Option>
                ));
                
                return weekdayPersonnelOptions;
              })()
            }
          </Select>
        </Form.Item>

        <Form.Item name="holiday_personnel_sequence_id" label="人员顺序 (节假日)" rules={[{ required: true, message: '请选择节假日人员顺序!' }]}>
          <Select placeholder="选择节假日人员顺序" onChange={(value) => handleSequenceChange('holiday', value)} data-testid="generate-schedule-holiday-personnel-sequence" classNames={{ popup: { root: 'holiday-sequence-select-dropdown' } }}>
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id} data-testid={`holiday-sequence-option-${seq.id}`}>
                {seq.name} (节假日: {Array.isArray(seq.personnel_details) ? seq.personnel_details.map(p => p.name).join(', ') : ''})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_holiday_personnel_id" label="起始人员 (节假日)">
          <Select placeholder="选择节假日起始人员" allowClear data-testid="generate-schedule-start-holiday-personnel" classNames={{ popup: { root: 'start-holiday-personnel-select-dropdown' } }}>
            {selectedHolidayPersonnel.filter(p => p && p.id != null).map(p => (
              <Option key={p.id} value={p.id} data-testid={`start-holiday-personnel-option-${p.id}`}>{p.name}</Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="leader_sequence_id" label="领导顺序" rules={[{ required: true, message: '请选择领导顺序!' }]}>
          <Select placeholder="选择领导顺序" onChange={(value) => handleSequenceChange('leader', value)} data-testid="generate-schedule-leader-sequence" classNames={{ popup: { root: 'leader-sequence-select-dropdown' } }}>
            {Array.isArray(leaderSequences) && leaderSequences.map(seq => (
              <Option key={seq.id} value={seq.id} data-testid={`leader-sequence-option-${seq.id}`}>
                {seq.name} ({Array.isArray(seq.personnel_details) ? seq.personnel_details.map(p => p.name).join(', ') : ''})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_leader_id" label="起始领导">
          <Select placeholder="选择起始领导" allowClear data-testid="generate-schedule-start-leader" classNames={{ popup: { root: 'start-leader-select-dropdown' } }}>
            {selectedLeaders.map(p => (
              <Option key={p.id} value={p.id}>{p.name}</Option>
            ))}
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
};

GenerateScheduleModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  personnelSequences: PropTypes.array.isRequired,
  leaderSequences: PropTypes.array.isRequired,
};

const ScheduleManagementPage = () => {
  const queryClient = useQueryClient();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [isPersonnelSequenceModalVisible, setIsPersonnelSequenceModalVisible] = useState(false);
  const [currentSequence, setCurrentSequence] = useState(null);
  const [formInitialValues, setFormInitialValues] = useState({});
  const [isExporting, setIsExporting] = useState(false);
  const calendarRef = useRef(null);
  const calendarContainerRef = useRef(null);
  const originalCalendarContainerStyle = useRef({});
  const [selectedSchedules, setSelectedSchedules] = useState([]);
  const [isAllSelected, setIsAllSelected] = useState(false);
  const [isCalendarFilterEnabled, setIsCalendarFilterEnabled] = useState(false);
  const [calendarViewInfo, setCalendarViewInfo] = useState(null);
  const [currentView, setCurrentView] = useState('dayGridMonth');
  const [viewMode, setViewMode] = useState('calendar');
  const [weeklyLeaders, setWeeklyLeaders] = useState([]);

  const schedulesQuery = useQuery({
    queryKey: ['schedules'],
    queryFn: scheduleApi.fetchSchedules,
  });


  const personnelQuery = useQuery({
    queryKey: ['personnel'],
    queryFn: async () => {
      // Load all personnel by fetching all pages
      let allResults = [];
      let page = 1;
      let hasMore = true;
      while (hasMore) {
        const res = await axiosInstance.get('personnel/personnel/', { params: { page, page_size: 1000 } });
        allResults = allResults.concat(res.data.results || []);
        hasMore = !!res.data.next;
        if (!hasMore || res.data.results?.length < 1000) break;
      }
      return allResults;
    }
  });

  const positionsQuery = useQuery({
    queryKey: ['positions'],
    queryFn: () => getPositions().then(res => res.data.results),
  });

  const personnelSequencesQuery = useQuery({
    queryKey: ['personnelSequences'],
    queryFn: () => getPersonnelSequences().then(res => res.data.results),
  });

  const leaderSequencesQuery = useQuery({
    queryKey: ['leaderSequences'],
    queryFn: () => getLeaderSequences().then(res => res.data.results),
  });

  const schedules = useMemo(() => schedulesQuery.data || [], [schedulesQuery.data]);
  const personnel = personnelQuery.data || [];
  const positions = positionsQuery.data || [];
  const personnelSequences = personnelSequencesQuery.data || [];
  const leaderSequences = leaderSequencesQuery.data || [];

  const isDataPending =
    schedulesQuery.isPending ||
    personnelQuery.isPending ||
    positionsQuery.isPending ||
    personnelSequencesQuery.isPending ||
    leaderSequencesQuery.isPending;

  const invalidateSchedules = () => {
    queryClient.invalidateQueries({ queryKey: ['schedules'] });
  };

  const createOrUpdateMutation = useMutation({
    mutationFn: (values) =>
      formInitialValues.id
        ? scheduleApi.updateSchedule(formInitialValues.id, values)
        : scheduleApi.createSchedule(values),
    onSuccess: () => {
      message.success(formInitialValues.id ? '排班更新成功' : '排班创建成功');
      invalidateSchedules();
      setIsModalVisible(false);
    },
    onError: () => {
      message.error('保存排班失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => scheduleApi.deleteSchedule(id),
    onSuccess: () => {
      message.success('排班删除成功');
      invalidateSchedules();
    },
    onError: () => {
      message.error('删除排班失败');
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids) => scheduleApi.bulkDeleteSchedules(ids),
    onSuccess: () => {
      message.success('批量删除成功');
      invalidateSchedules();
      setSelectedSchedules([]);
    },
    onError: () => {
      message.error('批量删除失败');
    },
  });

  const generateMutation = useMutation({
    mutationFn: (values) => scheduleApi.generateSchedules(values),
    onSuccess: () => {
      message.success('排班生成成功');
      invalidateSchedules();
      setIsGenerateModalVisible(false);
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.error || '生成排班失败';
      message.error(errorMsg);
    },
  });

  const swapDatesMutation = useMutation({
    mutationFn: ({ draggedId, targetId }) => scheduleApi.swapScheduleDates(draggedId, targetId),
    onSuccess: () => {
      message.success('排班交换成功');
      invalidateSchedules();
    },
    onError: (_error, _variables, context) => {
      message.error('更新排班失败');
      context?.revert?.();
    },
  });

  const updateDateMutation = useMutation({
    mutationFn: ({ id, data }) => scheduleApi.updateSchedule(id, data),
    onSuccess: () => {
      message.success('排班日期更新成功');
      invalidateSchedules();
    },
    onError: (_error, _variables, context) => {
      message.error('更新排班失败');
      context?.revert?.();
    },
  });

  const swapLeadersMutation = useMutation({
    mutationFn: (data) => scheduleApi.swapWeeklyLeaders(data),
    onSuccess: () => {
      message.success('值班领导顺序更新成功');
      invalidateSchedules();
    },
    onError: (_error, _variables, context) => {
      message.error('更新值班领导顺序失败');
      setWeeklyLeaders(context?.previousWeeklyLeaders ?? weeklyLeaders);
    },
  });

  useEffect(() => {
    if (calendarContainerRef.current) {
      originalCalendarContainerStyle.current = {
        width: calendarContainerRef.current.style.width,
        height: calendarContainerRef.current.style.height,
      };
    }
  }, []);

  const handleAdd = () => {
    setFormInitialValues({ id: null });
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    const initialValues = {
      id: record.id,
      date: record.duty_date ? dayjs(record.duty_date) : null,
      duty_person: record.duty_person?.id,
      duty_leader: record.duty_leader?.id,
      person_position_filter: record.duty_person?.position?.id,
      leader_position_filter: record.duty_leader?.position?.id,
      duty_person_phone: record.duty_person?.phone_numbers?.map(p => p.number).join(', ') || '',
      duty_leader_phone: record.duty_leader?.phone_numbers?.map(p => p.number).join(', ') || '',
    };
    setFormInitialValues(initialValues);
    setIsModalVisible(true);
  };

  const handleDelete = (id) => {
    deleteMutation.mutate(id);
  };

  const handleBulkDelete = () => {
    if (selectedSchedules.length === 0) {
      message.info('请先选择要删除的排班');
      return;
    }
    bulkDeleteMutation.mutate(selectedSchedules);
  };

  const handleModalOk = (values) => {
    createOrUpdateMutation.mutate(values);
  };

  const handlePersonnelSequenceModalOk = () => {
    setIsPersonnelSequenceModalVisible(false);
    setCurrentSequence(null);
    queryClient.invalidateQueries({ queryKey: ['personnelSequences', 'leaderSequences'] });
    message.success('人员顺序已成功保存');
  };

  const handlePersonnelSequenceModalCancel = () => {
    setIsPersonnelSequenceModalVisible(false);
    setCurrentSequence(null);
  };

  const handleGenerateModalOk = (values) => {
    generateMutation.mutate(values);
  };

  const handleEventDrop = (info) => {
    const { event: draggedEvent, revert } = info;
    const newDate = dayjs(draggedEvent.start).format('YYYY-MM-DD');
    const targetEvent = schedules.find(s =>
      dayjs(s.duty_date).format('YYYY-MM-DD') === newDate && String(s.id) !== draggedEvent.id
    );
    const draggedId = parseInt(draggedEvent.id, 10);

    if (targetEvent) {
      const targetId = parseInt(targetEvent.id, 10);
      swapDatesMutation.mutate({ draggedId, targetId }, { context: { revert } });
    } else {
      const scheduleData = {
        date: newDate,
        duty_person_id: draggedEvent.extendedProps.duty_person.id,
        duty_leader_id: draggedEvent.extendedProps.duty_leader.id,
      };
      updateDateMutation.mutate({ id: draggedId, data: scheduleData }, { context: { revert } });
    }
  };

  const handleEventClick = (info) => {
    const scheduleId = parseInt(info.event.id, 10);
    const clickedSchedule = schedules.find(s => s.id === scheduleId);
    if (clickedSchedule) {
      handleEdit(clickedSchedule);
    } else {
      message.error('未找到对应的排班数据');
    }
  };

  useEffect(() => {
    const leaders = computeWeeklyLeaders(schedules, calendarViewInfo);
    setWeeklyLeaders(leaders);
  }, [schedules, calendarViewInfo]);

  const handleDatesSet = (viewInfo) => {
    setCalendarViewInfo(viewInfo);
    setCurrentView(viewInfo.view.type);
  };

  const handleLeaderDragEnd = async (result) => {
    if (!result.destination) return;

    const previousWeeklyLeaders = weeklyLeaders;
    const newWeeklyLeaders = Array.from(weeklyLeaders);
    const [reorderedItem] = newWeeklyLeaders.splice(result.source.index, 1);
    newWeeklyLeaders.splice(result.destination.index, 0, reorderedItem);
    setWeeklyLeaders(newWeeklyLeaders);

    const sourceWeek = weeklyLeaders[result.source.index];
    const destinationWeek = weeklyLeaders[result.destination.index];

    swapLeadersMutation.mutate({
      source_week_start_date: sourceWeek.start,
      destination_week_start_date: destinationWeek.start,
    }, { context: { previousWeeklyLeaders } });
  };

  const calendarEvents = useMemo(() => {
    return schedules.map(schedule => {
      const dutyPerson = schedule.duty_person;
      const dutyLeader = schedule.duty_leader;
      return {
        id: String(schedule.id),
        start: schedule.duty_date,
        allDay: true,
        extendedProps: {
          duty_person: {
            ...dutyPerson,
            name: dutyPerson?.username || dutyPerson?.name,
          },
          duty_leader: {
            ...dutyLeader,
            name: dutyLeader?.username || dutyLeader?.name,
          },
        }
      };
    });
  }, [schedules]);

  const renderEventContent = (eventInfo) => {
    const { duty_person, duty_leader } = eventInfo.event.extendedProps;
    return (
      <div className="calendar-event-card">
        <div className="event-card-row">
          <span className="event-card-name">{duty_person?.name || ''}</span>
        </div>
        <div className="event-card-row event-card-muted">
          <span>{duty_leader?.name || ''}</span>
        </div>
      </div>
    );
  };

  const filteredSchedules = useMemo(() => {
    if (!isCalendarFilterEnabled || !calendarViewInfo) {
      return schedules;
    }
    const viewStart = dayjs(calendarViewInfo.start).startOf('day');
    const viewEnd = dayjs(calendarViewInfo.end).endOf('day');
    return schedules.filter(schedule => {
      const dutyDate = dayjs(schedule.duty_date);
      return dutyDate.isBetween(viewStart, viewEnd, null, '[]');
    });
  }, [schedules, isCalendarFilterEnabled, calendarViewInfo]);

  const handleSelectAll = () => {
    if (isAllSelected) {
      setSelectedSchedules([]);
    } else {
      setSelectedSchedules(filteredSchedules.map(s => s.id));
    }
    setIsAllSelected(!isAllSelected);
  };

  const handleInvertSelection = () => {
    const allIds = filteredSchedules.map(s => s.id);
    const newSelectedIds = allIds.filter(id => !selectedSchedules.includes(id));
    setSelectedSchedules(newSelectedIds);
    setIsAllSelected(newSelectedIds.length === allIds.length && allIds.length > 0);
  };

  const rowSelection = {
    selectedRowKeys: selectedSchedules,
    onChange: (keys) => {
      setSelectedSchedules(keys);
      setIsAllSelected(keys.length === filteredSchedules.length && filteredSchedules.length > 0);
    },
  };

  const exportToPDF = async () => {
    setIsExporting(true);
    await new Promise(resolve => setTimeout(resolve, 500));
    const calendarEl = calendarContainerRef.current;
    if (!calendarEl) {
      message.error('无法找到日历元素');
      setIsExporting(false);
      return;
    }
    const originalWidth = calendarEl.style.width;
    const originalHeight = calendarEl.style.height;
    calendarEl.style.width = 'auto';
    calendarEl.style.height = 'auto';
    try {
      const canvas = await html2canvas(calendarEl, { scale: 2, useCORS: true });
      const pdf = new jsPDF({ orientation: 'landscape', unit: 'px', format: [canvas.width, canvas.height] });
      pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, canvas.width, canvas.height);
      pdf.save('schedule.pdf');
    } catch (error) {
      logger.error("导出PDF时出错:", error);
      message.error('导出PDF失败');
    } finally {
      calendarEl.style.width = originalWidth;
      calendarEl.style.height = originalHeight;
      setIsExporting(false);
    }
  };

  const columns = [
    {
      title: '值班日期',
      dataIndex: 'duty_date',
      key: 'duty_date',
      sorter: (a, b) => dayjs(a.duty_date).unix() - dayjs(b.duty_date).unix(),
      sortOrder: 'ascend',
    },
    {
      title: '值班人员',
      dataIndex: ['duty_person', 'name'],
      key: 'duty_person',
    },
    {
      title: '值班人员电话',
      dataIndex: ['duty_person', 'phone_number'],
      key: 'duty_person_phone',
      render: (phone_number) => phone_number || 'N/A',
    },
    {
      title: '值班领导',
      dataIndex: ['duty_leader', 'name'],
      key: 'duty_leader',
    },
    {
      title: '值班领导电话',
      dataIndex: ['duty_leader', 'phone_number'],
      key: 'duty_leader_phone',
      render: (phone_number) => phone_number || 'N/A',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="primary" onClick={() => handleEdit(record)} data-testid={`edit-schedule-button-${record.id}`}>编辑</Button>
          <Popconfirm title="确定删除吗?" onConfirm={() => handleDelete(record.id)}>
            <Button danger data-testid={`delete-schedule-button-${record.id}`}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-4" data-testid="schedule-management-page">
      <h1 className="text-2xl font-bold mb-4">排班管理</h1>
      <Card loading={isDataPending}>
        <div className="flex justify-between items-center mb-4">
          <Space>
            <Button type="primary" onClick={handleAdd} data-testid="add-schedule-button">新增排班</Button>
            <Button type="default" onClick={() => setIsGenerateModalVisible(true)} data-testid="generate-schedule-button">生成排班</Button>
            <Button type="default" onClick={() => setIsPersonnelSequenceModalVisible(true)} data-testid="manage-personnel-sequence-button">管理人员顺序</Button>
          </Space>
          <Space>
           <Radio.Group value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
             <Radio.Button value="calendar">日历</Radio.Button>
             <Radio.Button value="list">列表</Radio.Button>
           </Radio.Group>
            <Switch
              checkedChildren="日历筛选已开启"
              unCheckedChildren="日历筛选已关闭"
              checked={isCalendarFilterEnabled}
              onChange={setIsCalendarFilterEnabled}
              data-testid="calendar-filter-switch"
            />
            <Button onClick={exportToPDF} loading={isExporting} data-testid="export-pdf-button">导出为PDF</Button>
          </Space>
        </div>

       {viewMode === 'calendar' && (
         <DragDropContext onDragEnd={handleLeaderDragEnd}>
           <div style={{ display: 'flex' }}>
             <div ref={calendarContainerRef} style={{ flex: 1 }}>
               {currentView === 'dayGridWeek' && <WeeklyLeaderDisplay leaders={weeklyLeaders.length > 0 ? weeklyLeaders[0].leaders : []} />}
               <FullCalendar
                 data-testid="full-calendar"
                 ref={calendarRef}
                 plugins={[dayGridPlugin, interactionPlugin]}
                 initialView="dayGridMonth"
                 headerToolbar={{
                   left: 'prev,next today',
                   center: 'title',
                   right: 'dayGridMonth,dayGridWeek'
                 }}
                 events={calendarEvents}
                 editable={true}
                 droppable={true}
                 eventDrop={handleEventDrop}
                 eventClick={handleEventClick}
                 eventContent={renderEventContent}
                 datesSet={handleDatesSet}
                 locale="zh-cn"
                 firstDay={1}
                 slotMinTime="08:00:00"
                 slotMaxTime="23:00:00"
               />
             </div>
             {currentView === 'dayGridMonth' && (
               <MonthlyLeaderSidebar
                 weeklyLeaders={weeklyLeaders}
                 calendarRef={calendarRef}
                 isDragDisabled={swapLeadersMutation.isPending}
               />
             )}
           </div>
         </DragDropContext>
       )}

       {viewMode === 'list' && (
         <div className="mt-4">
           <Space className="mb-2">
             <Button onClick={handleSelectAll} data-testid="select-all-button">全选</Button>
             <Button onClick={handleInvertSelection} data-testid="invert-selection-button">反选</Button>
             <Button danger onClick={handleBulkDelete} disabled={selectedSchedules.length === 0 || bulkDeleteMutation.isPending} data-testid="bulk-delete-button">批量删除</Button>
           </Space>
           <Table
             columns={columns}
             dataSource={filteredSchedules}
             rowKey="id"
             loading={isDataPending}
             rowSelection={rowSelection}
             pagination={{ pageSize: 10 }}
             data-testid="schedule-table"
           />
         </div>
       )}
      </Card>
      {isModalVisible && (
        <ScheduleFormModal
          key={formInitialValues.id || 'new-schedule'}
          open={isModalVisible}
          onCancel={() => {
            setIsModalVisible(false);
            setFormInitialValues({});
          }}
          onOk={handleModalOk}
          initialValues={formInitialValues}
          personnelList={personnel}
          positions={positions}
        />
      )}
      {isGenerateModalVisible && (
        <GenerateScheduleModal
          open={isGenerateModalVisible}
          onCancel={() => setIsGenerateModalVisible(false)}
          onOk={handleGenerateModalOk}
          personnelSequences={personnelSequences}
          leaderSequences={leaderSequences}
        />
      )}
      {isPersonnelSequenceModalVisible && (
        <PersonnelSequenceModal
          open={isPersonnelSequenceModalVisible}
          onOk={handlePersonnelSequenceModalOk}
          onCancel={handlePersonnelSequenceModalCancel}
          personnelList={personnel}
          sequence={currentSequence}
          positions={positions}
        />
      )}
    </div>
  );
};

export default ScheduleManagementPage;