import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, notification, Space } from 'antd';
import { Link } from 'react-router-dom';
import { getSensors, createSensor } from '../api/sensorApi';

const SensorManagementPage = () => {
  const [sensors, setSensors] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchSensors();
  }, []);

  const fetchSensors = async () => {
    try {
      const response = await getSensors();
      if (response.data && Array.isArray(response.data.results)) {
        setSensors(response.data.results);
      } else if (Array.isArray(response.data)) {
        setSensors(response.data);
      } else {
        setSensors([]);
      }
    } catch (error) {
      message.error('获取传感器列表失败');
      console.error('获取传感器列表失败:', error);
    }
  };

  const showAddModal = () => {
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    form.resetFields();
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createSensor(values);
      notification.success({
        message: '添加成功',
        description: '新的传感器已成功添加。',
      });
      setIsModalVisible(false);
      form.resetFields();
      fetchSensors(); // Refresh the list
    } catch (error) {
      notification.error({
        message: '添加失败',
        description: '无法添加传感器，请检查您输入的数据。',
      });
      console.error('创建传感器失败:', error);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '序列号',
      dataIndex: 'serial_number',
      key: 'serial_number',
    },
    {
      title: '校准范围',
      dataIndex: 'calibration_range',
      key: 'calibration_range',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Link to={`/sensor-management/history/${record.id}`}>校准历史</Link>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={showAddModal}>
          添加传感器
        </Button>
        <Link to="/sensor-management/add-record">
          <Button type="primary">
            添加校准记录
          </Button>
        </Link>
      </Space>
      <Table columns={columns} dataSource={sensors} rowKey="id" />
      <Modal
        title="添加新传感器"
        visible={isModalVisible}
        onOk={handleCreate}
        onCancel={handleCancel}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" name="sensor_form">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入传感器名称!' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="serial_number"
            label="序列号"
            rules={[{ required: true, message: '请输入序列号!' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="calibration_range"
            label="校准范围"
            rules={[{ required: true, message: '请输入校准范围!' }]}
          >
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SensorManagementPage;
