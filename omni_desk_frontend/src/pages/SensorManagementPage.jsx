import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, Select, message, Space, Tag, InputNumber } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import moment from 'moment';
import apiClient from '../api/apiClient';
import { useNavigate } from 'react-router-dom';

const { Option } = Select;
const { confirm } = Modal;

const SensorFormModal = ({ visible, onCancel, onOk, initialData }) => {
  const [form] = Form.useForm();
  const [sensorCategories, setSensorCategories] = useState([]);
  const [storageLocations, setStorageLocations] = useState([]);

  useEffect(() => {
    if (visible) {
      form.setFieldsValue({
        ...initialData,
        production_date: initialData.production_date ? moment(initialData.production_date) : null,
        purchase_date: initialData.purchase_date ? moment(initialData.purchase_date) : null,
        last_calibration_date: initialData.last_calibration_date ? moment(initialData.last_calibration_date) : null,
        sensor_category: initialData.sensor_category || undefined, // 确保初始值为 undefined 以便 Select 组件正确显示 Placeholder
        location: initialData.location || undefined,
      });
      fetchSensorCategories();
      fetchStorageLocations();
    }
  }, [visible, initialData, form]);

  const fetchSensorCategories = async () => {
    try {
      const response = await apiClient.get('/sensor-management/sensor-categories/');
      setSensorCategories(response.data.results || []);
    } catch (error) {
      message.error('获取传感器类别失败!');
      console.error('Error fetching sensor categories:', error);
    }
  };

  const fetchStorageLocations = async () => {
    try {
      const response = await apiClient.get('/sensor-management/storage-locations/');
      setStorageLocations(response.data.results || []);
    } catch (error) {
      message.error('获取存放位置失败!');
      console.error('Error fetching storage locations:', error);
    }
  };

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
        <Form.Item name="sensor_name" label="传感器名称" rules={[{ required: true, message: '请输入传感器名称!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="sensor_number" label="传感器编号" rules={[{ required: true, message: '请输入传感器编号!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="serial_number" label="序列号" rules={[{ required: true, message: '请输入序列号!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="sensor_category" label="传感器类别" rules={[{ required: true, message: '请选择传感器类别!' }]}>
          <Select placeholder="请选择传感器类别">
            {sensorCategories.map(category => (
              <Option key={category.id} value={category.id}>{category.name}</Option>
            ))}
          </Select>
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
          <Select placeholder="请选择存放位置">
            {storageLocations.map(location => (
              <Option key={location.id} value={location.id}>{location.name}</Option>
            ))}
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
};

const InboundFormModal = ({ visible, onCancel, onOk, initialData }) => {
  const [form] = Form.useForm();
  const [storageLocations, setStorageLocations] = useState([]);

  useEffect(() => {
    if (visible) {
      form.setFieldsValue({
        sensor: initialData.id,
        quantity: 1,
        movement_date: moment(),
        movement_type: 'in',
        destination_source: initialData.location || undefined, // 默认使用传感器当前位置
      });
      fetchStorageLocations();
    }
  }, [visible, initialData, form]);

  const fetchStorageLocations = async () => {
    try {
      const response = await apiClient.get('/sensor-management/storage-locations/');
      setStorageLocations(response.data.results || []);
    } catch (error) {
      message.error('获取存放位置失败!');
      console.error('Error fetching storage locations:', error);
    }
  };

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          ...values,
          movement_date: values.movement_date ? values.movement_date.format('YYYY-MM-DDTHH:mm:ss') : null,
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
      title={`传感器入库: ${initialData.serial_number}`}
      visible={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item name="sensor" label="传感器ID" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="movement_type" label="操作类型" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="quantity" label="数量" rules={[{ required: true, message: '请输入数量!' }, { type: 'number', min: 1, message: '数量必须大于0' }]}>
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="movement_date" label="入库时间" rules={[{ required: true, message: '请选择入库时间!' }]}>
          <DatePicker showTime style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="destination_source" label="存放位置" rules={[{ required: true, message: '请选择存放位置!' }]}>
          <Select placeholder="请选择存放位置">
            {storageLocations.map(location => (
              <Option key={location.id} value={location.id}>{location.name}</Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="reason" label="备注">
          <Input.TextArea />
        </Form.Item>
      </Form>
    </Modal>
  );
};

const OutboundFormModal = ({ visible, onCancel, onOk, initialData }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (visible) {
      form.setFieldsValue({
        sensor: initialData.id,
        quantity: 1,
        movement_date: moment(),
        movement_type: 'out',
        destination_source: '',
      });
    }
  }, [visible, initialData, form]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          ...values,
          movement_date: values.movement_date ? values.movement_date.format('YYYY-MM-DDTHH:mm:ss') : null,
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
      title={`传感器出库: ${initialData.serial_number}`}
      visible={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item name="sensor" label="传感器ID" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="movement_type" label="操作类型" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="quantity" label="数量" rules={[{ required: true, message: '请输入数量!' }, { type: 'number', min: 1, max: initialData.current_quantity, message: `数量不能大于当前库存: ${initialData.current_quantity}` }]}>
          <InputNumber min={1} max={initialData.current_quantity} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="movement_date" label="出库时间" rules={[{ required: true, message: '请选择出库时间!' }]}>
          <DatePicker showTime style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="destination_source" label="使用地点" rules={[{ required: true, message: '请输入使用地点!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="reason" label="备注">
          <Input.TextArea />
        </Form.Item>
      </Form>
    </Modal>
  );
};

const SensorManagementPage = () => {
  const [sensors, setSensors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isInboundModalVisible, setIsInboundModalVisible] = useState(false);
  const [isOutboundModalVisible, setIsOutboundModalVisible] = useState(false);
  const [currentSensor, setCurrentSensor] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchSensors();
  }, []);

  const fetchSensors = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/sensor-management/sensors/');
      setSensors(Array.isArray(response.data.results) ? response.data.results : []);
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
          await apiClient.delete(`/sensor-management/sensors/${id}/`);
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
        await apiClient.put(`/sensor-management/sensors/${currentSensor.id}/`, values);
        message.success('传感器更新成功!');
      } else {
        await apiClient.post('/sensor-management/sensors/', values);
        message.success('传感器新增成功!');
      }
      setIsModalVisible(false);
      fetchSensors();
    } catch (error) {
      message.error('保存传感器失败!');
      console.error('Error saving sensor:', error);
    }
  };

  const handleInbound = (record) => {
    setCurrentSensor(record);
    setIsInboundModalVisible(true);
  };

  const handleOutbound = (record) => {
    setCurrentSensor(record);
    setIsOutboundModalVisible(true);
  };

  const handleMovementOk = async (values) => {
    try {
      await apiClient.post('/sensor-management/sensor-movements/', values);
      message.success('出入库操作成功!');
      setIsInboundModalVisible(false);
      setIsOutboundModalVisible(false);
      fetchSensors(); // Refresh sensor list to show updated quantity and status
    } catch (error) {
      message.error('出入库操作失败!');
      console.error('Error saving sensor movement:', error);
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
      title: '传感器名称',
      dataIndex: 'sensor_name',
      key: 'sensor_name',
      sorter: (a, b) => a.sensor_name.localeCompare(b.sensor_name),
    },
    {
      title: '传感器类别',
      dataIndex: 'sensor_category_name',
      key: 'sensor_category_name',
    },
    {
      title: '传感器编号',
      dataIndex: 'sensor_number',
      key: 'sensor_number',
      sorter: (a, b) => a.sensor_number.localeCompare(b.sensor_number),
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
      title: '室温',
      dataIndex: 'room_temperature',
      key: 'room_temperature',
      render: (text) => text ? `${text}°C` : 'N/A',
      sorter: (a, b) => (a.room_temperature || 0) - (b.room_temperature || 0),
    },
    {
      title: '相对湿度',
      dataIndex: 'relative_humidity',
      key: 'relative_humidity',
      render: (text) => text ? `${text}%` : 'N/A',
      sorter: (a, b) => (a.relative_humidity || 0) - (b.relative_humidity || 0),
    },
    {
      title: '当前数量',
      dataIndex: 'current_quantity',
      key: 'current_quantity',
      sorter: (a, b) => a.current_quantity - b.current_quantity,
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
      dataIndex: 'location_name',
      key: 'location_name',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" onClick={() => handleInbound(record)}>入库</Button>
          <Button type="link" onClick={() => handleOutbound(record)}>出库</Button>
          <Button type="link" onClick={() => navigate(`/sensor-calibration/${record.id}`)}>校准数据</Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="传感器管理"
      extra={
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增传感器
          </Button>
          <Button onClick={() => navigate('/sensor-categories')}>管理类别</Button>
          <Button onClick={() => navigate('/storage-locations')}>管理位置</Button>
        </Space>
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
      <InboundFormModal
        visible={isInboundModalVisible}
        onCancel={() => setIsInboundModalVisible(false)}
        onOk={handleMovementOk}
        initialData={currentSensor || {}}
      />
      <OutboundFormModal
        visible={isOutboundModalVisible}
        onCancel={() => setIsOutboundModalVisible(false)}
        onOk={handleMovementOk}
        initialData={currentSensor || {}}
      />
    </Card>
  );
};

export default SensorManagementPage;
