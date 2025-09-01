import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Radio } from 'antd';
import { scheduleApi } from '../api/scheduleApi';
import { getAllPersonnel } from '../api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../api/sequenceApi';
import moment from 'moment';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

const { Option } = Select;

const ScheduleFormModal = ({ visible, onCancel, onOk, initialData, personnelList }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (visible) {
      form.setFieldsValue({
        ...initialData,
        date: initialData.duty_date ? moment(initialData.duty_date) : null,
      });
    }
  }, [visible, initialData, form]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          ...values,
          date: values.date ? values.date.format('YYYY-MM-DD') : null,
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
      visible={visible}
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
          name="duty_person"
          label="值班人员"
          rules={[{ required: true, message: '请选择值班人员!' }]}
        >
          <Select
            placeholder="选择值班人员"
            showSearch
            filterOption={(input, option) =>
              option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
            }
          >
            {personnelList.map(person => (
              <Option key={person.id} value={person.id}>
                {person.name}
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
              option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
            }
          >
            {personnelList.map(person => (
              <Option key={person.id} value={person.id}>
                {person.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
};

const GenerateScheduleModal = ({ visible, onCancel, onOk, personnelSequences, leaderSequences }) => {
  const [form] = Form.useForm();
  const [generationMode, setGenerationMode] = useState('days');
  const [selectedPersonnel, setSelectedPersonnel] = useState([]);
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
        setSelectedLeaders([]);
      })
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  const handleSequenceChange = (type, sequenceId) => {
    if (type === 'personnel') {
      const sequence = personnelSequences.find(s => s.id === sequenceId);
      setSelectedPersonnel(sequence ? sequence.personnel_details : []);
      form.setFieldsValue({ start_personnel_id: null });
    } else if (type === 'leader') {
      const sequence = leaderSequences.find(s => s.id === sequenceId);
      setSelectedLeaders(sequence ? sequence.personnel_details : []);
      form.setFieldsValue({ start_leader_id: null });
    }
  };

  return (
    <Modal title="生成排班" visible={visible} onOk={handleOk} onCancel={onCancel} destroyOnClose>
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
            {selectedPersonnel.map(p => <Option key={p.id} value={p.id}>{p.name}</Option>)}
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
            {selectedLeaders.map(p => <Option key={p.id} value={p.id}>{p.name}</Option>)}
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
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);

  useEffect(() => {
    fetchData();
    fetchPersonnel();
    fetchSequences();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await scheduleApi.getSchedules();
      setSchedules(data);
    } catch (error) {
      message.error('获取排班数据失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchPersonnel = async () => {
    try {
      const data = await getAllPersonnel();
      setPersonnelList(data);
    } catch (error) {
      message.error('获取人员列表失败');
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

  const handleEdit = (record) => {
    setCurrentSchedule(record);
    setIsModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await scheduleApi.deleteSchedule(id);
      message.success('排班删除成功');
      fetchData();
    } catch (error) {
      message.error('删除排班失败');
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

  const formatCalendarEvents = () => {
    return schedules.map(schedule => ({
      id: String(schedule.id),
      title: `${getPersonnelName(schedule.duty_person)} / ${getPersonnelName(schedule.duty_leader)}`,
      start: schedule.duty_date,
      allDay: true,
      extendedProps: {
        duty_person: schedule.duty_person,
        duty_leader: schedule.duty_leader,
      }
    }));
  };

  const columns = [
    {
      title: '值班日期',
      dataIndex: 'duty_date',
      key: 'duty_date',
      render: (text) => moment(text).format('YYYY-MM-DD'),
      sorter: (a, b) => moment(a.duty_date).unix() - moment(b.duty_date).unix(),
    },
    {
      title: '值班人员',
      dataIndex: 'duty_person',
      key: 'duty_person',
      render: (id) => getPersonnelName(id),
    },
    {
      title: '值班领导',
      dataIndex: 'duty_leader',
      key: 'duty_leader',
      render: (id) => getPersonnelName(id),
    },
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

  return (
    <Card title="排班管理" extra={
      <Space>
        <Button type="primary" onClick={handleAdd}>新增排班</Button>
        <Button type="default" onClick={() => setIsGenerateModalVisible(true)}>生成排班</Button>
      </Space>
    }>
      <div style={{ marginBottom: 20 }}>
        <FullCalendar
          plugins={[dayGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          events={formatCalendarEvents()}
          editable={true}
          droppable={true}
          eventDrop={handleEventDrop}
          locale="zh-cn"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,dayGridWeek'
          }}
        />
      </div>
      <Table
        columns={columns}
        dataSource={schedules}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />
      <ScheduleFormModal
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleModalOk}
        initialData={currentSchedule || {}}
        personnelList={personnelList}
      />
      <GenerateScheduleModal
        visible={isGenerateModalVisible}
        onCancel={() => setIsGenerateModalVisible(false)}
        onOk={handleGenerateModalOk}
        personnelSequences={personnelSequences}
        leaderSequences={leaderSequences}
      />
    </Card>
  );
};

export default ScheduleManagementPage;