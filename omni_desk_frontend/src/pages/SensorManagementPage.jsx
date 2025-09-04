import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import moment from 'moment';
import apiClient from '../api/apiClient'; // 假设你有一个apiClient用于后端请求

const { Option } = Select;
const { confirm } = Modal;

const SensorFormModal = ({ visible, onCancel, onOk, initialData }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (visible) {
      form.setFieldsValue({
        ...initialData,
        production_date: initialData.production_date ? moment(initialData.production_date) : null,
        purchase_date: initialData.purchase_date ? moment(initialData.purchase_date) : null,
        last_calibration_date: initialData.last_calibration_date ? moment(initialData.last_calibration_date) : null,
      });
    }
  }, [visible, initialData, form]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          ...values,
          production_date: values.production_date ? values.production_date.format('YYYY-MM-DD') : null,
          purchase_date: values.purchase_date ? values.purchase_date.format('YYYY-MM-DD') : null,
          last_calibration_date: values.last_calibration_date ? values.last_calibration_date.format('YYYY-MM-DD') : null,
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
      title={initialData.id ? "编辑传感器" : "新增传感器"}
      visible={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item name="serial_number" label="序列号" rules={[{ required: true, message: '请输入序列号!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="model_name" label="型号名称" rules={[{ required: true, message: '请输入型号名称!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="manufacturer" label="制造商" rules={[{ required: true, message: '请输入制造商!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="calibration_accuracy" label="校准精度" rules={[{ required: true, message: '请输入校准精度!' }]}>
          <Input type="number" step="0.01" />
        </Form.Item>
        <Form.Item name="production_date" label="生产日期">
          <DatePicker style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="purchase_date" label="购买日期">
          <DatePicker style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="last_calibration_date" label="上次校准日期">
          <DatePicker style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="calibration_interval_days" label="校准周期（天）" rules={[{ required: true, message: '请输入校准周期!' }]}>
          <Input type="number" />
        </Form.Item>
        <Form.Item name="status" label="状态" rules={[{ required: true, message: '请选择状态!' }]}>
          <Select>
            <Option value="in_stock">库存中</Option>
            <Option value="in_use">使用中</Option>
            <Option value="under_calibration">校准中</Option>
            <Option value="retired">已报废</Option>
          </Select>
        </Form.Item>
        <Form.Item name="location" label="存放位置">
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
};

const SensorManagementPage = () => {
  const [sensors, setSensors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentSensor, setCurrentSensor] = useState(null);

  useEffect(() => {
    fetchSensors();
  }, []);

  const fetchSensors = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/api/sensor-management/sensors/');
      setSensors(response.data);
    } catch (error) {
      message.error('获取传感器列表失败!');
      console.error('Error fetching sensors:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setCurrentSensor(null);
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setCurrentSensor(record);
    setIsModalVisible(true);
  };

  const handleDelete = (id) => {
    confirm({
      title: '确定要删除此传感器吗?',
      icon: <ExclamationCircleOutlined />,
      content: '删除后将无法恢复。',
      onOk: async () => {
        try {
          await apiClient.delete(`/api/sensor-management/sensors/${id}/`);
          message.success('传感器删除成功!');
          fetchSensors();
        } catch (error) {
          message.error('删除传感器失败!');
          console.error('Error deleting sensor:', error);
        }
      },
    });
  };

  const handleModalOk = async (values) => {
    try {
      if (currentSensor) {
        await apiClient.put(`/api/sensor-management/sensors/${currentSensor.id}/`, values);
        message.success('传感器更新成功!');
      } else {
        await apiClient.post('/api/sensor-management/sensors/', values);
        message.success('传感器新增成功!');
      }
      setIsModalVisible(false);
      fetchSensors();
    } catch (error) {
      message.error('保存传感器失败!');
      console.error('Error saving sensor:', error);
    }
  };

  const getStatusTag = (status) => {
    switch (status) {
      case 'in_stock':
        return <Tag color="blue">库存中</Tag>;
      case 'in_use':
        return <Tag color="green">使用中</Tag>;
      case 'under_calibration':
        return <Tag color="orange">校准中</Tag>;
      case 'retired':
        return <Tag color="red">已报废</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const columns = [
    {
      title: '序列号',
      dataIndex: 'serial_number',
      key: 'serial_number',
      sorter: (a, b) => a.serial_number.localeCompare(b.serial_number),
    },
    {
      title: '型号名称',
      dataIndex: 'model_name',
      key: 'model_name',
    },
    {
      title: '制造商',
      dataIndex: 'manufacturer',
      key: 'manufacturer',
    },
    {
      title: '校准精度',
      dataIndex: 'calibration_accuracy',
      key: 'calibration_accuracy',
    },
    {
      title: '上次校准日期',
      dataIndex: 'last_calibration_date',
      key: 'last_calibration_date',
      render: (text) => text ? moment(text).format('YYYY-MM-DD') : 'N/A',
      sorter: (a, b) => moment(a.last_calibration_date || '1900-01-01').unix() - moment(b.last_calibration_date || '1900-01-01').unix(),
    },
    {
      title: '下次校准日期',
      dataIndex: 'next_calibration_date',
      key: 'next_calibration_date',
      render: (text) => text ? moment(text).format('YYYY-MM-DD') : 'N/A',
      sorter: (a, b) => moment(a.next_calibration_date || '1900-01-01').unix() - moment(b.next_calibration_date || '1900-01-01').unix(),
    },
    {
      title: '校准周期（天）',
      dataIndex: 'calibration_interval_days',
      key: 'calibration_interval_days',
      sorter: (a, b) => a.calibration_interval_days - b.calibration_interval_days,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => getStatusTag(status),
      filters: [
        { text: '库存中', value: 'in_stock' },
        { text: '使用中', value: 'in_use' },
        { text: '校准中', value: 'under_calibration' },
        { text: '已报废', value: 'retired' },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: '存放位置',
      dataIndex: 'location',
      key: 'location',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="传感器管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增传感器
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={sensors}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />
      <SensorFormModal
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleModalOk}
        initialData={currentSensor || {}}
      />
    </Card>
  );
};

export default SensorManagementPage;