import { useState } from 'react';
import { Button, Table, Modal, Form, message, Space } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSensors, createSensor, updateSensor, deleteSensor } from '../api/sensorApi';
import SensorForm from '../components/SensorForm';
import { Link } from 'react-router-dom';

const SensorManagementPage = () => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingSensor, setEditingSensor] = useState(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: rawData, isLoading } = useQuery(['sensors'], getSensors);
  const sensors = rawData?.results || [];

  const createMutation = useMutation(createSensor, {
    onSuccess: () => {
      queryClient.invalidateQueries('sensors');
      message.success('传感器创建成功');
      setIsModalVisible(false);
      form.resetFields();
    },
    onError: () => {
      message.error('传感器创建失败');
    },
  });

  const updateMutation = useMutation(({ id, data }) => updateSensor(id, data), {
    onSuccess: () => {
      queryClient.invalidateQueries('sensors');
      message.success('传感器更新成功');
      setIsModalVisible(false);
      setEditingSensor(null);
      form.resetFields();
    },
    onError: () => {
      message.error('传感器更新失败');
    },
  });

  const deleteMutation = useMutation(deleteSensor, {
    onSuccess: () => {
      queryClient.invalidateQueries('sensors');
      message.success('传感器删除成功');
    },
    onError: () => {
      message.error('传感器删除失败');
    },
  });

  const handleAdd = () => {
    setEditingSensor(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingSensor(record);
    form.setFieldsValue({
      ...record,
      category: record.category.id,
      storage_location: record.storage_location.id,
    });
    setIsModalVisible(true);
  };

  const handleDelete = (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '你确定要删除这个传感器吗？',
      onOk: () => {
        deleteMutation.mutate(id);
      },
    });
  };

  const handleOk = () => {
    form.validateFields().then((values) => {
      if (editingSensor) {
        updateMutation.mutate({ id: editingSensor.id, data: values });
      } else {
        createMutation.mutate(values);
      }
    });
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingSensor(null);
    form.resetFields();
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类别', dataIndex: ['category', 'name'], key: 'category' },
    { title: '存放地点', dataIndex: ['storage_location', 'name'], key: 'storage_location' },
    { title: '状态', dataIndex: 'status', key: 'status' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Link to={`/control-panel/sensor/sensors/${record.id}`} >查看详情</Link>
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <h1>传感器管理</h1>
      <Button type="primary" onClick={handleAdd} style={{ marginBottom: 16 }}>
        新增传感器
      </Button>
      <Table
        columns={columns}
        dataSource={sensors}
        loading={isLoading}
        rowKey="id"
      />
      <Modal
        title={editingSensor ? '编辑传感器' : '新增传感器'}
        visible={isModalVisible}
        onOk={handleOk}
        onCancel={handleCancel}
        confirmLoading={createMutation.isLoading || updateMutation.isLoading}
      >
        <SensorForm form={form} initialValues={editingSensor} />
      </Modal>
    </div>
  );
};

export default SensorManagementPage;