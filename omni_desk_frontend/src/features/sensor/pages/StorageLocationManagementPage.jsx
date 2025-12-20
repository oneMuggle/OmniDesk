import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Card, Table, Button, Modal, Form, Input, message, Space } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import apiClient from '../api/apiClient';

const { confirm } = Modal;

const StorageLocationFormModal = ({ visible, onCancel, onOk, initialData = null }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (visible) {
      form.setFieldsValue(initialData);
    }
  }, [visible, initialData, form]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        onOk(values);
        form.resetFields();
      })
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  return (
    <Modal
      title={initialData.id ? "编辑存放位置" : "新增存放位置"}
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="位置名称" rules={[{ required: true, message: '请输入位置名称!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea />
        </Form.Item>
      </Form>
    </Modal>
  );
};

StorageLocationFormModal.propTypes = {
  visible: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  initialData: PropTypes.object,
};


const StorageLocationManagementPage = () => {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(null);

  useEffect(() => {
    fetchLocations();
  }, []);

  const fetchLocations = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/sensor-management/storage-locations/');
      setLocations(Array.isArray(response.data.results) ? response.data.results : []);
    } catch (error) {
      message.error('获取存放位置列表失败!');
      console.error('Error fetching storage locations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setCurrentLocation(null);
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setCurrentLocation(record);
    setIsModalVisible(true);
  };

  const handleDelete = (id) => {
    confirm({
      title: '确定要删除此存放位置吗?',
      icon: <ExclamationCircleOutlined />,
      content: '删除后将无法恢复。',
      onOk: async () => {
        try {
          await apiClient.delete(`/sensor-management/storage-locations/${id}/`);
          message.success('存放位置删除成功!');
          fetchLocations();
        } catch (error) {
          message.error('删除存放位置失败!');
          console.error('Error deleting storage location:', error);
        }
      },
    });
  };

  const handleModalOk = async (values) => {
    try {
      if (currentLocation) {
        await apiClient.put(`/sensor-management/storage-locations/${currentLocation.id}/`, values);
        message.success('存放位置更新成功!');
      } else {
        await apiClient.post('/sensor-management/storage-locations/', values);
        message.success('存放位置新增成功!');
      }
      setIsModalVisible(false);
      fetchLocations();
    } catch (error) {
      message.error('保存存放位置失败!');
      console.error('Error saving storage location:', error);
    }
  };

  const columns = [
    {
      title: '位置名称',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
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
      title="存放位置管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增位置
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={locations}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />
      <StorageLocationFormModal
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleModalOk}
        initialData={currentLocation || {}}
      />
    </Card>
  );
};

export default StorageLocationManagementPage;