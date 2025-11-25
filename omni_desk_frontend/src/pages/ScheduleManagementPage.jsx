import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Radio, InputNumber, Slider, Switch } from 'antd';
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
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="date"
          label="值班日期"
          rules={[{ required: true, message: '请选择值班日期!' }]}
        >
          <DatePicker style={{ width: '100%' }} />
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
            filterOption={(input, option) =>
              option.children[0].toLowerCase().indexOf(input.toLowerCase()) >= 0 // option.children is array: [name, ' (', position_name, ')']
            }
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
            <Input value={initialData.duty_person.phone_numbers.map(p => p.number).join(', ')} readOnly />
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
            filterOption={(input, option) =>
              option.children[0].toLowerCase().indexOf(input.toLowerCase()) >= 0
            }
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
            <Input value={initialData.duty_leader.phone_numbers.map(p => p.number).join(', ')} readOnly />
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
    <Modal title="生成排班" open={open} onOk={handleOk} onCancel={onCancel} destroyOnClose>
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
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="duration_days" label="生成天数" initialValue={30} rules={[{ required: true, message: '请输入生成天数!' }]}>
              <Input type="number" />
            </Form.Item>
          </>
        ) : (
          <Form.Item name="target_month" label="选择月份" rules={[{ required: true, message: '请选择月份!' }]}>
            <DatePicker.MonthPicker style={{ width: '100%' }} />
          </Form.Item>
        )}

        <Form.Item name="personnel_sequence_id" label="人员顺序" rules={[{ required: true, message: '请选择人员顺序!' }]}>
          <Select placeholder="选择人员顺序" onChange={(value) => handleSequenceChange('personnel', value)}>
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id}>
                {seq.name} ({seq.personnel_details.map(p => p.name).join(', ')})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_personnel_id" label="起始人员">
          <Select placeholder="选择起始人员" allowClear>
            {selectedPersonnel.map(p => {
              console.log('Rendering personnel option:', p);
              return <Option key={p.id} value={p.id}>{p.name}</Option>
            })}
          </Select>
        </Form.Item>

        <Form.Item name="leader_sequence_id" label="领导顺序" rules={[{ required: true, message: '请选择领导顺序!' }]}>
          <Select placeholder="选择领导顺序" onChange={(value) => handleSequenceChange('leader', value)}>
            {Array.isArray(leaderSequences) && leaderSequences.map(seq => (
              <Option key={seq.id} value={seq.id}>
                {seq.name} ({seq.personnel_details.map(p => p.name).join(', ')})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_leader_id" label="起始领导">
          <Select placeholder="选择起始领导" allowClear>
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
    setCurrentSchedule(clickedSchedule);
    setIsModalVisible(true);
  };

  const calendarEvents = useMemo(() => {
    return schedules.map(schedule => ({
      id: String(schedule.id),
      start: schedule.duty_date,
      allDay: true,
      extendedProps: {
        duty_person: schedule.duty_person,
        duty_leader: schedule.duty_leader,
        duty_person_name: schedule.duty_person?.name || '未知',
        duty_leader_name: schedule.duty_leader?.name || '未知',
      }
    }));
  }, [schedules]);

  const filteredSchedules = useMemo(() => {
    if (!isCalendarFilterEnabled || !calendarViewInfo) {
      return schedules;
    }

    const { start, end } = calendarViewInfo;
    const viewStart = moment(start).startOf('day');
    const viewEnd = moment(end).endOf('day');

    return schedules.filter(schedule => {
      const dutyDate = moment(schedule.duty_date);
      return dutyDate.isBetween(viewStart, viewEnd, undefined, '[]');
    });
  }, [schedules, isCalendarFilterEnabled, calendarViewInfo]);

  const exportToPdf = async () => {
    setIsExporting(true);
    const calendarEl = calendarRef.current.getApi().el;
    const originalStyle = {
      width: calendarEl.style.width,
      height: calendarEl.style.height,
    };
    calendarEl.style.width = '100%';
    calendarEl.style.height = 'auto';

    await new Promise(resolve => setTimeout(resolve, 500));

    html2canvas(calendarEl, {
      scale: 2,
      useCORS: true,
      logging: true,
    }).then(canvas => {
      const pdf = new jsPDF({
        orientation: 'landscape',
        unit: 'px',
        format: [canvas.width, canvas.height]
      });
      pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, canvas.width, canvas.height);
      pdf.save('schedule.pdf');
      calendarEl.style.width = originalStyle.width;
      calendarEl.style.height = originalStyle.height;
      setIsExporting(false);
    }).catch(err => {
      console.error("Error exporting to PDF:", err);
      message.error('导出PDF失败');
      calendarEl.style.width = originalStyle.width;
      calendarEl.style.height = originalStyle.height;
      setIsExporting(false);
    });
  };

  const columns = [
    { title: '日期', dataIndex: 'duty_date', key: 'date' },
    { title: '值班人员', dataIndex: ['duty_person', 'name'], key: 'duty_person' },
    { title: '值班领导', dataIndex: ['duty_leader', 'name'], key: 'duty_leader' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  const handleSelectAll = () => {
    const allScheduleIds = filteredSchedules.map(s => s.id);
    setSelectedSchedules(allScheduleIds);
    setIsAllSelected(true);
  };

  const handleInvertSelection = () => {
    const allScheduleIds = filteredSchedules.map(s => s.id);
    const unselectedSchedules = allScheduleIds.filter(id => !selectedSchedules.includes(id));
    setSelectedSchedules(unselectedSchedules);
    setIsAllSelected(false);
  };

  const rowSelection = {
    selectedRowKeys: selectedSchedules,
    onChange: (selectedRowKeys) => {
      setSelectedSchedules(selectedRowKeys);
      setIsAllSelected(selectedRowKeys.length === filteredSchedules.length && filteredSchedules.length > 0);
    },
  };

  return (
    <>
      <Card
        title="排班管理"
        extra={
          <Space>
            <Button type="primary" onClick={handleAdd}>新增排班</Button>
            <Button onClick={() => setIsGenerateModalVisible(true)}>生成排班</Button>
            <Button onClick={exportToPdf} loading={isExporting}>导出为PDF</Button>
            <Space align="center" style={{ marginLeft: 16 }}>
              <span>日历过滤</span>
              <Switch
                checked={isCalendarFilterEnabled}
                onChange={setIsCalendarFilterEnabled}
              />
            </Space>
          </Space>
        }
      >
        <div ref={calendarContainerRef}>
          <FullCalendar
            plugins={[dayGridPlugin, interactionPlugin]}
            initialView="dayGridMonth"
            weekends={true}
            events={calendarEvents}
            editable={true}
            droppable={true}
            eventDrop={handleEventDrop}
            eventClick={handleEventClick}
            locale="zh-cn"
            eventContent={(eventInfo) => (
              <div style={{ textAlign: 'center' }}>
                <div>{eventInfo.event.extendedProps.duty_person_name}</div>
                <div>{eventInfo.event.extendedProps.duty_leader_name}</div>
              </div>
            )}
            datesSet={(view) => setCalendarViewInfo(view)}
            headerToolbar={
              isExporting
                ? { left: '', center: 'title', right: '' }
                : { left: 'prev,next today', center: 'title', right: 'dayGridMonth,dayGridWeek' }
            }
            ref={calendarRef}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button onClick={handleSelectAll}>全选</Button>
            <Button onClick={handleInvertSelection}>反选</Button>
            <Button danger onClick={handleBulkDelete}>批量删除</Button>
          </Space>
        </div>
        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={filteredSchedules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
        <ScheduleFormModal
          open={isModalVisible}
          onCancel={() => setIsModalVisible(false)}
          onOk={handleModalOk}
          initialData={currentSchedule || {}}
          personnelList={personnelList}
          positions={positions} // 传递职务列表
        />
        {isGenerateModalVisible && (
          <GenerateScheduleModal
            visible={isGenerateModalVisible}
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
          />
        )}
      </Card>
    </>
  );
};

export default ScheduleManagementPage;