import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Card, Table, Button, Modal, Form, Input, message, Space } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import apiClient from '../api/apiClient';

const { confirm } = Modal;

const SensorCategoryFormModal = ({ visible, onCancel, onOk, initialData }) => {
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
      title={initialData.id ? "编辑传感器类别" : "新增传感器类别"}
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="类别名称" rules={[{ required: true, message: '请输入类别名称!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea />
        </Form.Item>
      </Form>
    </Modal>
  );
};

SensorCategoryFormModal.propTypes = {
  visible: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  initialData: PropTypes.object,
};

SensorCategoryFormModal.defaultProps = {
  initialData: null,
};

const SensorCategoryManagementPage = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentCategory, setCurrentCategory] = useState(null);

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/sensor-management/sensor-categories/');
      setCategories(Array.isArray(response.data.results) ? response.data.results : []);
    } catch (error) {
      message.error('获取传感器类别列表失败!');
      console.error('Error fetching sensor categories:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setCurrentCategory(null);
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setCurrentCategory(record);
    setIsModalVisible(true);
  };

  const handleDelete = (id) => {
    confirm({
      title: '确定要删除此传感器类别吗?',
      icon: <ExclamationCircleOutlined />,
      content: '删除后将无法恢复。',
      onOk: async () => {
        try {
          await apiClient.delete(`/sensor-management/sensor-categories/${id}/`);
          message.success('传感器类别删除成功!');
          fetchCategories();
        } catch (error) {
          message.error('删除传感器类别失败!');
          console.error('Error deleting sensor category:', error);
        }
      },
    });
  };

  const handleModalOk = async (values) => {
    try {
      if (currentCategory) {
        await apiClient.put(`/sensor-management/sensor-categories/${currentCategory.id}/`, values);
        message.success('传感器类别更新成功!');
      } else {
        await apiClient.post('/sensor-management/sensor-categories/', values);
        message.success('传感器类别新增成功!');
      }
      setIsModalVisible(false);
      fetchCategories();
    } catch (error) {
      message.error('保存传感器类别失败!');
      console.error('Error saving sensor category:', error);
    }
  };

  const columns = [
    {
      title: '类别名称',
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
      title="传感器类别管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增类别
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={categories}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />
      <SensorCategoryFormModal
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleModalOk}
        initialData={currentCategory || {}}
      />
    </Card>
  );
};

export default SensorCategoryManagementPage;