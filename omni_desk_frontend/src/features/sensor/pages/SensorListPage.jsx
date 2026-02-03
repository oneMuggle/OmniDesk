import { useState, useEffect } from 'react';
import { Button, Table, Modal, Form, message, Space } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSensors, createSensor, updateSensor, deleteSensor } from '../api/sensorApi';
import SensorForm from '../components/SensorForm';
import { Link } from 'react-router-dom';

const SensorListPage = () => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingSensor, setEditingSensor] = useState(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const sensorsQuery = useQuery({ queryKey: ['sensors'], queryFn: getSensors });
  const sensors = sensorsQuery.data?.data?.results || [];

  const createMutation = useMutation({
    mutationFn: createSensor,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sensors'] });
      message.success('传感器创建成功');
      setIsModalVisible(false);
    },
    onError: () => {
      message.error('传感器创建失败');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateSensor(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sensors'] });
      message.success('传感器更新成功');
      setIsModalVisible(false);
      setEditingSensor(null);
    },
    onError: () => {
      message.error('传感器更新失败');
    },
  });

  const deleteMutation = useMutation({ mutationFn: deleteSensor,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sensors'] });
      message.success('传感器删除成功');
    },
    onError: () => {
      message.error('传感器删除失败');
    },
  });

  const handleAdd = () => {
    setEditingSensor(null);
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingSensor({
      ...record,
      category_id: record.sensor_category_name,
      storage_location_id: record.location_name,
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
  };

  const statusMap = {
    in_stock: '在库',
    in_use: '使用中',
    retired: '已报废',
    // 根据需要添加其他状态
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类别', dataIndex: 'sensor_category_name', key: 'category' },
    { title: '存放地点', dataIndex: 'location_name', key: 'storage_location' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => statusMap[status] || status
    },
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
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={handleAdd}>
          新增传感器
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={sensors}
        loading={sensorsQuery.isLoading}
        rowKey="id"
      />
      <Modal
        title={editingSensor ? '编辑传感器' : '新增传感器'}
        open={isModalVisible}
        onOk={handleOk}
        onCancel={handleCancel}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        destroyOnClose
      >
        <SensorForm form={form} initialValues={editingSensor} />
      </Modal>
    </div>
  );
};

export default SensorListPage;