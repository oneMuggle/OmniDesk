import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Space, notification } from 'antd';
import { Link } from 'react-router-dom';
import apiClient from '../api/axiosConfig';
import SensorForm from '../components/sensor/SensorForm';

const SensorManagementPage = () => {
  const [sensors, setSensors] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingSensor, setEditingSensor] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchSensors();
  }, []);

  const fetchSensors = async () => {
    try {
      const data = await apiClient.get('sensor-management/sensors/');
      if (data && Array.isArray(data.results)) {
        setSensors(data.results);
      } else {
        setSensors([]);
      }
    } catch (error) {
      message.error('获取传感器列表失败');
    }
  };

  const handleAdd = () => {
    setEditingSensor(null);
    setIsModalVisible(true);
  };

  const handleEdit = (sensor) => {
    setEditingSensor(sensor);
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingSensor(null);
    form.resetFields();
  };

  const handleFormSubmit = (values) => {
    const processedValues = {
      ...values,
      room_temperature: values.room_temperature === '' || values.room_temperature === undefined ? null : values.room_temperature,
      relative_humidity: values.relative_humidity === '' || values.relative_humidity === undefined ? null : values.relative_humidity,
      calibration_accuracy: values.calibration_accuracy === '' ? null : values.calibration_accuracy,
      manufacturer: values.manufacturer === '' ? null : values.manufacturer,
      serial_number: values.serial_number === '' ? null : values.serial_number,
    };

    const request = editingSensor
      ? apiClient.put(`sensor-management/sensors/${editingSensor.id}/`, processedValues)
      : apiClient.post('sensor-management/sensors/', processedValues);

    request
      .then(response => {
        notification.success({
          message: '保存成功',
        });
        setIsModalVisible(false);
        setEditingSensor(null); // 清空编辑状态
        fetchSensors(); // <--- 添加这一行来刷新列表
      })
      .catch(error => {
        if (error.response && error.response.data) {
          // 打印详细的后端错误到控制台，这对于调试至关重要
          console.error('保存失败，后端验证错误:', error.response.data);

          const errorData = error.response.data;
          // 遍历后端返回的错误对象，为每个出错的字段显示一个通知
          Object.keys(errorData).forEach(field => {
            const messages = Array.isArray(errorData[field]) ? errorData[field].join(' ') : errorData[field];
            notification.error({
              message: `字段 "${field}" 无效`,
              description: messages,
            });
          });
        } else {
          // 处理网络错误或其他未知错误
          console.error('保存传感器失败:', error);
          notification.error({
            message: '保存传感器失败',
            description: '发生未知错误，请检查网络连接或联系管理员。',
          });
        }
      });
  };

  const columns = [
    { title: '传感器名称', dataIndex: 'name', key: 'name' },
    { title: '室温 (°C)', dataIndex: 'room_temperature', key: 'room_temperature' },
    { title: '相对湿度 (%)', dataIndex: 'relative_humidity', key: 'relative_humidity' },
    { title: '传感器编号', dataIndex: 'sensor_number', key: 'sensor_number' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button onClick={() => handleEdit(record)}>编辑</Button>
          <Link to={`/sensor-management/sensors/${record.id}`}>
            <Button>查看详情</Button>
          </Link>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Button type="primary" onClick={handleAdd} style={{ marginBottom: 16 }}>
        添加新传感器
      </Button>
      <Table dataSource={sensors} columns={columns} rowKey="id" />
      <Modal
        title={editingSensor ? '编辑传感器' : '添加新传感器'}
        visible={isModalVisible}
        onCancel={handleCancel}
        footer={null}
      >
        <SensorForm
          form={form}
          initialValues={editingSensor}
          onSubmit={handleFormSubmit}
        />
      </Modal>
    </div>
  );
};

export default SensorManagementPage;
