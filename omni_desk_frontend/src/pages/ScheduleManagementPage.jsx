import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Calendar as AntdCalendar } from 'antd';
import { scheduleApi } from '../api/scheduleApi';
import { getPersonnelSequences, getLeaderSequences } from '../api/sequenceApi';
import moment from 'moment';

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

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          ...values,
          start_date: values.start_date ? values.start_date.format('YYYY-MM-DD') : null,
          personnel_sequence_id: values.personnel_sequence_id,
          leader_sequence_id: values.leader_sequence_id,
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
      title="生成排班"
      visible={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="start_date"
          label="起始日期"
          rules={[{ required: true, message: '请选择起始日期!' }]}
        >
          <DatePicker style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          name="personnel_sequence_id"
          label="人员顺序"
          rules={[{ required: true, message: '请选择人员顺序!' }]}
        >
          <Select placeholder="选择人员顺序">
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id}>
                {seq.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="leader_sequence_id"
          label="领导顺序"
          rules={[{ required: true, message: '请选择领导顺序!' }]}
        >
          <Select placeholder="选择领导顺序">
            {Array.isArray(leaderSequences) && leaderSequences.map(seq => (
              <Option key={seq.id} value={seq.id}>
                {seq.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="duration_days"
          label="生成天数"
          initialValue={30}
          rules={[{ required: true, message: '请输入生成天数!' }]}
        >
          <Input type="number" />
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
      const data = await scheduleApi.getPersonnel();
      setPersonnelList(data);
    } catch (error) {
      message.error('获取人员列表失败');
    }
  };

  const fetchSequences = async () => {
    try {
      const personnelRes = await getPersonnelSequences();
      setPersonnelSequences(personnelRes.data);
      const leaderRes = await getLeaderSequences();
      setLeaderSequences(leaderRes.data);
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
      await scheduleApi.generateSchedules({
        start_date: values.start_date,
        personnel_sequence_id: values.personnel_sequence_id,
        leader_sequence_id: values.leader_sequence_id,
        duration_days: values.duration_days,
      });
      message.success('排班生成成功');
      setIsGenerateModalVisible(false);
      fetchData();
    } catch (error) {
      message.error('生成排班失败');
    }
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

  const cellRender = (value) => {
    const date = value.format('YYYY-MM-DD');
    const daySchedules = schedules.filter(s => moment(s.duty_date).format('YYYY-MM-DD') === date);

    return (
      <ul className="events">
        {daySchedules.map(item => (
          <li key={item.id}>
            <p>值班人员: {getPersonnelName(item.duty_person)}</p>
            <p>值班领导: {getPersonnelName(item.duty_leader)}</p>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <Card title="排班管理" extra={
      <Space>
        <Button type="primary" onClick={handleAdd}>新增排班</Button>
        <Button type="default" onClick={() => setIsGenerateModalVisible(true)}>生成排班</Button>
      </Space>
    }>
      <div style={{ marginBottom: 20 }}>
        <AntdCalendar cellRender={cellRender} />
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