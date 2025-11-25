import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Radio, InputNumber, Slider, Switch, Popconfirm } from 'antd';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { scheduleApi } from '../api/scheduleApi';
import { getAllPersonnel, getPositions } from '../api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../api/sequenceApi';
import moment from 'moment';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import PersonnelSequenceModal from '../components/Schedule/PersonnelSequenceModal';

const { Option } = Select;

const ScheduleFormModal = ({ open, onCancel, onOk, initialData, personnelList, positions }) => {
  const [form] = Form.useForm();
  const [filteredDutyPersonList, setFilteredDutyPersonList] = useState(personnelList);
  const [filteredDutyLeaderList, setFilteredDutyLeaderList] = useState(personnelList);
  const [selectedPersonPositionId, setSelectedPersonPositionId] = useState(null);
  const [selectedLeaderPositionId, setSelectedLeaderPositionId] = useState(null);

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        ...initialData,
        date: initialData.duty_date ? moment(initialData.duty_date) : null,
        duty_person: initialData.duty_person ? initialData.duty_person.id : null,
        duty_leader: initialData.duty_leader ? initialData.duty_leader.id : null,
      });
      // console.log("ScheduleFormModal - initialData:", initialData);
      // console.log("ScheduleFormModal - duty_person (from initialData):", initialData.duty_person);
      // console.log("ScheduleFormModal - duty_leader (from initialData):", initialData.duty_leader);
      // console.log("ScheduleFormModal - duty_person phone_numbers:", initialData.duty_person?.phone_numbers);
      // console.log("ScheduleFormModal - duty_leader phone_numbers:", initialData.duty_leader?.phone_numbers);
      // console.log("ScheduleFormModal - form fields after setFieldsValue:", form.getFieldsValue());
      // Reset filters and lists when modal opens
      setFilteredDutyPersonList(personnelList);
      setFilteredDutyLeaderList(personnelList);
      setSelectedPersonPositionId(null);
      setSelectedLeaderPositionId(null);
    }
  }, [open, initialData, form, personnelList]);


  useEffect(() => {
    if (selectedPersonPositionId) {
      setFilteredDutyPersonList(personnelList.filter(p => p.position === selectedPersonPositionId));
    } else {
      setFilteredDutyPersonList(personnelList);
    }
    form.setFieldsValue({ duty_person: null }); // Clear selected person
  }, [selectedPersonPositionId, personnelList, form]);

  useEffect(() => {
    if (selectedLeaderPositionId) {
      setFilteredDutyLeaderList(personnelList.filter(p => p.position === selectedLeaderPositionId));
    } else {
      setFilteredDutyLeaderList(personnelList);
    }
    form.setFieldsValue({ duty_leader: null }); // Clear selected leader
  }, [selectedLeaderPositionId, personnelList, form]);

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
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  return (
    <Modal
      title={initialData.id ? "编辑排班" : "新增排班"}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
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
      <Form form={form} layout="vertical">
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
            onChange={(value) => setSelectedPersonPositionId(value)}
            value={selectedPersonPositionId}
            getPopupContainer={(triggerNode) => triggerNode.parentNode}
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
            filterOption={(input, option) =>
              option.children[0].toLowerCase().indexOf(input.toLowerCase()) >= 0 // option.children is array: [name, ' (', position_name, ')']
            }
            getPopupContainer={(triggerNode) => triggerNode.parentNode}
          >
            {filteredDutyPersonList.map(person => (
              <Option key={person.id} value={person.id}>
                {person.name} ({person.position_name})
              </Option>
            ))}
          </Select>
        </Form.Item>
        {initialData.duty_person && initialData.duty_person.phone_numbers && initialData.duty_person.phone_numbers.length > 0 && (
          <Form.Item label="值班人员电话">
            <Input value={initialData.duty_person.phone_numbers.map(p => p.number).join(', ')} readOnly data-testid="schedule-modal-duty-person-phone" />
          </Form.Item>
        )}
        <Form.Item
          name="leader_position_filter"
          label="值班领导职务筛选"
        >
          <Select
            placeholder="按职务筛选值班领导"
            allowClear
            onChange={(value) => setSelectedLeaderPositionId(value)}
            value={selectedLeaderPositionId}
            getPopupContainer={(triggerNode) => triggerNode.parentNode}
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
            filterOption={(input, option) =>
              option.children[0].toLowerCase().indexOf(input.toLowerCase()) >= 0
            }
            getPopupContainer={(triggerNode) => triggerNode.parentNode}
          >
            {filteredDutyLeaderList.map(person => (
              <Option key={person.id} value={person.id}>
                {person.name} ({person.position_name})
              </Option>
            ))}
          </Select>
        </Form.Item>
        {initialData.duty_leader && initialData.duty_leader.phone_numbers && initialData.duty_leader.phone_numbers.length > 0 && (
          <Form.Item label="值班领导电话">
            <Input value={initialData.duty_leader.phone_numbers.map(p => p.number).join(', ')} readOnly data-testid="schedule-modal-duty-leader-phone" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
};


const GenerateScheduleModal = ({ open, onCancel, onOk, personnelSequences, leaderSequences }) => {
  const [form] = Form.useForm();
  const [generationMode, setGenerationMode] = useState('days');
  const [selectedPersonnel, setSelectedPersonnel] = useState([]);
  const [selectedLeaders, setSelectedLeaders] = useState([]);
console.log('GenerateScheduleModal - personnelSequences:', personnelSequences);
console.log('GenerateScheduleModal - leaderSequences:', leaderSequences);

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
        setSelectedLeaders([]);
      })
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  const handleSequenceChange = (type, sequenceId) => {
    if (type === 'personnel') {
      const sequence = personnelSequences.find(s => s.id === sequenceId);
      console.log('handleSequenceChange - selectedPersonnel:', sequence ? sequence.personnel_details : []);
      setSelectedPersonnel(sequence ? sequence.personnel_details : []);
      console.log('handleSequenceChange - selectedPersonnel:', sequence ? sequence.personnel_details : []);
      form.setFieldsValue({ start_personnel_id: null });
      console.log('handleSequenceChange - selectedPersonnel:', sequence ? sequence.personnel_details : []);
    } else if (type === 'leader') {
      const sequence = leaderSequences.find(s => s.id === sequenceId);
      console.log('handleSequenceChange - selectedLeaders:', sequence ? sequence.personnel_details : []);
      console.log('handleSequenceChange - selectedLeaders:', sequence ? sequence.personnel_details : []);
      setSelectedLeaders(sequence ? sequence.personnel_details : []);
      console.log('handleSequenceChange - selectedLeaders:', sequence ? sequence.personnel_details : []);
      form.setFieldsValue({ start_leader_id: null });
      console.log('handleSequenceChange - selectedLeaders:', sequence ? sequence.personnel_details : []);
    }
  };

  return (
    <Modal title="生成排班" open={open} onOk={handleOk} onCancel={onCancel} destroyOnClose data-testid="generate-schedule-modal">
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
            <DatePicker.MonthPicker style={{ width: '100%' }} data-testid="generate-schedule-target-month" />
          </Form.Item>
        )}

        <Form.Item name="personnel_sequence_id" label="人员顺序" rules={[{ required: true, message: '请选择人员顺序!' }]}>
          <Select placeholder="选择人员顺序" onChange={(value) => handleSequenceChange('personnel', value)} data-testid="generate-schedule-personnel-sequence" getPopupContainer={(triggerNode) => triggerNode.parentNode}>
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id}>
                {seq.name} ({seq.personnel_details.map(p => p.name).join(', ')})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_personnel_id" label="起始人员">
          <Select placeholder="选择起始人员" allowClear data-testid="generate-schedule-start-personnel" getPopupContainer={(triggerNode) => triggerNode.parentNode}>
            {selectedPersonnel.map(p => {
              console.log('Rendering personnel option:', p);
              return <Option key={p.id} value={p.id}>{p.name}</Option>
            })}
          </Select>
        </Form.Item>

        <Form.Item name="leader_sequence_id" label="领导顺序" rules={[{ required: true, message: '请选择领导顺序!' }]}>
          <Select placeholder="选择领导顺序" onChange={(value) => handleSequenceChange('leader', value)} data-testid="generate-schedule-leader-sequence" getPopupContainer={(triggerNode) => triggerNode.parentNode}>
            {Array.isArray(leaderSequences) && leaderSequences.map(seq => (
              <Option key={seq.id} value={seq.id}>
                {seq.name} ({seq.personnel_details.map(p => p.name).join(', ')})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_leader_id" label="起始领导">
          <Select placeholder="选择起始领导" allowClear data-testid="generate-schedule-start-leader" getPopupContainer={(triggerNode) => triggerNode.parentNode}>
            {selectedLeaders.map(p => {
              console.log('Rendering leader option:', p);
              return <Option key={p.id} value={p.id}>{p.name}</Option>
            })}
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
};

const ScheduleManagementPage = () => {
  const [schedules, setSchedules] = useState([]);
  const [personnelList, setPersonnelList] = useState([]);
  const [personnelSequences, setPersonnelSequences] = useState([]);
  const [leaderSequences, setLeaderSequences] = useState([]);
  const [positions, setPositions] = useState([]); // 新增职务状态
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [isPersonnelSequenceModalVisible, setIsPersonnelSequenceModalVisible] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const calendarRef = useRef(null);
  const calendarContainerRef = useRef(null); // 新增ref用于日历容器
  const originalCalendarContainerStyle = useRef({}); // 存储日历容器的原始样式
  const [selectedSchedules, setSelectedSchedules] = useState([]);
  const [isAllSelected, setIsAllSelected] = useState(false);
  const [isCalendarFilterEnabled, setIsCalendarFilterEnabled] = useState(false);
  const [calendarViewInfo, setCalendarViewInfo] = useState(null);

  useEffect(() => {
    // 组件挂载时保存日历容器的原始样式
    if (calendarContainerRef.current) {
      originalCalendarContainerStyle.current = {
        width: calendarContainerRef.current.style.width,
        height: calendarContainerRef.current.style.height,
        // 可以添加其他需要保存的样式属性
      };
    }
  }, []);

  useEffect(() => {
    const initData = async () => {
      await fetchPersonnel(); // 确保人员列表先加载
      await fetchPositions(); // 确保职务列表先加载
      await fetchSequences(); // 确保顺序列表先加载
      fetchData(); // 最后加载排班数据
    };
    initData();
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await scheduleApi.getSchedules();
      // 遍历排班数据，duty_person和duty_leader已经是完整对象，无需额外查找
      const formattedData = data.map(schedule => ({
        ...schedule,
        // duty_person 和 duty_leader 已经包含完整信息，直接使用
      }));
      setSchedules(formattedData);
    } catch (error) {
      message.error('获取排班数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPersonnel = async () => {
    try {
      const data = await getAllPersonnel();
      setPersonnelList(data);
    } catch (error) {
      message.error('获取人员列表失败');
    }
  };

  const fetchPositions = async () => {
    try {
      const data = await getPositions();
      setPositions(data.results); // 假设API返回的数据在results字段
    } catch (error) {
      message.error('获取职务列表失败');
    }
  };

  const fetchSequences = async () => {
    try {
      const personnelRes = await getPersonnelSequences();
      setPersonnelSequences(personnelRes.data.results);
      const leaderRes = await getLeaderSequences();
      setLeaderSequences(leaderRes.data.results);
    } catch (error) {
      message.error('获取顺序列表失败');
    }
  };

  const getPersonnelName = (id) => {
    const person = personnelList.find(p => p.id === id);
    return person ? person.name : '未知';
  };

  const handleAdd = () => {
    setCurrentSchedule(null);
    setIsModalVisible(true);
  };

  const handleEdit = useCallback((record) => {
    setCurrentSchedule(record);
    setIsModalVisible(true);
  }, []);

  const handleDelete = useCallback(async (id) => {
    try {
      await scheduleApi.deleteSchedule(id);
      message.success('排班删除成功');
      fetchData();
    } catch (error) {
      message.error('删除排班失败');
    }
  }, [fetchData]);

  const handleBulkDelete = async () => {
    if (selectedSchedules.length === 0) {
      message.info('请先选择要删除的排班');
      return;
    }
    try {
      await scheduleApi.bulkDeleteSchedules(selectedSchedules);
      message.success('批量删除成功');
      setSchedules(schedules.filter(s => !selectedSchedules.includes(s.id)));
      setSelectedSchedules([]);
    } catch (error) {
      message.error('批量删除失败');
    }
  };

  const handleModalOk = async (values) => {
    try {
      if (currentSchedule) {
        await scheduleApi.updateSchedule(currentSchedule.id, values);
        message.success('排班更新成功');
      } else {
        await scheduleApi.createSchedule(values);
        message.success('排班创建成功');
      }
      setIsModalVisible(false);
      fetchData();
    } catch (error) {
      message.error('保存排班失败');
    }
  };

  const handlePersonnelSequenceModalOk = () => {
    // The modal now handles its own API call. We just need to close it and refetch.
    setIsPersonnelSequenceModalVisible(false);
    fetchSequences(); // Refetch sequences to update the list
    message.success('人员顺序已成功保存');
  };

  const handlePersonnelSequenceModalCancel = () => {
    setIsPersonnelSequenceModalVisible(false);
  };
 
   const handleGenerateModalOk = async (values) => {
     try {
       await scheduleApi.generateSchedules(values);
      message.success('排班生成成功');
      setIsGenerateModalVisible(false);
      fetchData();
    } catch (error) {
      const errorMsg = error.response?.data?.error || '生成排班失败';
      message.error(errorMsg);
    }
  };

  const handleEventDrop = async (info) => {
    const { event: draggedEvent, oldEvent, revert } = info;
    const newDate = moment(draggedEvent.start).format('YYYY-MM-DD');

    const targetEvent = schedules.find(s =>
      moment(s.duty_date).format('YYYY-MM-DD') === newDate && String(s.id) !== draggedEvent.id
    );

    try {
      const draggedId = parseInt(draggedEvent.id, 10);
      if (targetEvent) {
        // 目标日期已有排班，交换
        const targetId = parseInt(targetEvent.id, 10);
        await scheduleApi.swapScheduleDates(draggedId, targetId);
        message.success('排班交换成功');
      } else {
        // 目标日期无排班，更新
        const scheduleData = {
          date: newDate,
          duty_person: draggedEvent.extendedProps.duty_person,
          duty_leader: draggedEvent.extendedProps.duty_leader,
        };
        await scheduleApi.updateSchedule(draggedId, scheduleData);
        message.success('排班日期更新成功');
      }
      fetchData(); // 重新获取数据刷新日历
    } catch (error) {
      message.error('更新排班失败');
      revert(); // 如果失败，则将事件还原
    }
  };
  const handleEventClick = (info) => {
    // 提取事件的原始数据，这些数据在 extendedProps 中
    const clickedSchedule = {
      id: parseInt(info.event.id, 10), // FullCalendar 的事件ID可能是字符串，需要转回数字
      duty_date: info.event.startStr,
      duty_person: info.event.extendedProps.duty_person,
      duty_leader: info.event.extendedProps.duty_leader,
    };
    handleEdit(clickedSchedule);
  };

  const handleDatesSet = (viewInfo) => {
    setCalendarViewInfo(viewInfo);
  };

  const calendarEvents = useMemo(() => {
    return schedules.map(schedule => ({
      id: schedule.id.toString(),
      title: `${schedule.duty_person.name} (值班), ${schedule.duty_leader.name} (领导)`,
      start: schedule.duty_date,
      allDay: true,
      extendedProps: {
        duty_person: schedule.duty_person,
        duty_leader: schedule.duty_leader,
      }
    }));
  }, [schedules]);

  const filteredSchedules = useMemo(() => {
    if (!isCalendarFilterEnabled || !calendarViewInfo) {
      return schedules;
    }
    const viewStart = moment(calendarViewInfo.start).startOf('day');
    const viewEnd = moment(calendarViewInfo.end).endOf('day');
    return schedules.filter(schedule => {
      const dutyDate = moment(schedule.duty_date);
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
    // 确保在导出前，日历已经渲染了所有需要的数据
    await new Promise(resolve => setTimeout(resolve, 500));

    const calendarEl = calendarContainerRef.current;
    if (!calendarEl) {
      message.error('无法找到日历元素');
      setIsExporting(false);
      return;
    }

    // 暂时移除日历容器的固定尺寸，以便html2canvas能捕获完整内容
    const originalWidth = calendarEl.style.width;
    const originalHeight = calendarEl.style.height;
    calendarEl.style.width = 'auto';
    calendarEl.style.height = 'auto';

    try {
      const canvas = await html2canvas(calendarEl, {
        scale: 2, // 提高分辨率
        useCORS: true,
      });
      const pdf = new jsPDF({
        orientation: 'landscape',
        unit: 'px',
        format: [canvas.width, canvas.height],
      });
      pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, canvas.width, canvas.height);
      pdf.save('schedule.pdf');
    } catch (error) {
      console.error("导出PDF时出错:", error);
      message.error('导出PDF失败');
    } finally {
      // 恢复原始样式
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
      sorter: (a, b) => moment(a.duty_date).unix() - moment(b.duty_date).unix(),
      sortOrder: 'ascend',
    },
    {
      title: '值班人员',
      dataIndex: ['duty_person', 'name'],
      key: 'duty_person',
    },
    {
      title: '值班人员电话',
      dataIndex: ['duty_person', 'phone_numbers'],
      key: 'duty_person_phone',
      render: (phone_numbers) => phone_numbers?.map(p => p.number).join(', ') || 'N/A',
    },
    {
      title: '值班领导',
      dataIndex: ['duty_leader', 'name'],
      key: 'duty_leader',
    },
    {
      title: '值班领导电话',
      dataIndex: ['duty_leader', 'phone_numbers'],
      key: 'duty_leader_phone',
      render: (phone_numbers) => phone_numbers?.map(p => p.number).join(', ') || 'N/A',
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
      <Card>
        <div className="flex justify-between items-center mb-4">
          <Space>
            <Button type="primary" onClick={handleAdd} data-testid="add-schedule-button">新增排班</Button>
            <Button type="default" onClick={() => setIsGenerateModalVisible(true)} data-testid="generate-schedule-button">生成排班</Button>
            <Button type="default" onClick={() => setIsPersonnelSequenceModalVisible(true)} data-testid="set-sequence-button">设置顺序</Button>
            <Button danger onClick={handleBulkDelete} disabled={selectedSchedules.length === 0} data-testid="bulk-delete-button">批量删除</Button>
          </Space>
          <Space>
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
        <div ref={calendarContainerRef}>
          <FullCalendar
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
            datesSet={handleDatesSet}
            locale="zh-cn"
            data-testid="schedule-calendar"
          />
        </div>
        <div className="mt-4">
          <Space className="mb-2">
            <Button onClick={handleSelectAll} data-testid="select-all-button">全选</Button>
            <Button onClick={handleInvertSelection} data-testid="invert-selection-button">反选</Button>
          </Space>
          <Table
            columns={columns}
            dataSource={filteredSchedules}
            rowKey="id"
            loading={loading}
            rowSelection={rowSelection}
            pagination={{ pageSize: 10 }}
            data-testid="schedule-table"
          />
        </div>
      </Card>
      {isModalVisible && (
        <ScheduleFormModal
          open={isModalVisible}
          onCancel={() => setIsModalVisible(false)}
          onOk={handleModalOk}
          initialData={currentSchedule || {}}
          personnelList={personnelList}
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
          personnelList={personnelList}
        />
      )}
    </div>
  );
};

export default ScheduleManagementPage;