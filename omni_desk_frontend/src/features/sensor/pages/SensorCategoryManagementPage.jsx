import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm } from 'antd';
import { getSensorCategories, createSensorCategory, updateSensorCategory, deleteSensorCategory } from '../api/sensorApi';

const SensorCategoryManagementPage = () => {
  const [categories, setCategories] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [form] = Form.useForm();

  const fetchCategories = async () => {
    try {
      const response = await getSensorCategories();
      setCategories(response.data.results);
    } catch (error) {
      message.error('获取传感器类别失败');
    }
  };

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const response = await getSensorCategories();
        if (isMounted) {
          setCategories(response.data.results);
        }
      } catch (error) {
        message.error('获取传感器类别失败');
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

  const showModal = (category = null) => {
    setEditingCategory(category);
    form.setFieldsValue(category ? { name: category.name, description: category.description } : { name: '', description: '' });
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingCategory(null);
    form.resetFields();
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingCategory) {
        await updateSensorCategory(editingCategory.id, values);
        message.success('更新成功');
      } else {
        await createSensorCategory(values);
        message.success('添加成功');
      }
      fetchCategories();
      handleCancel();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteSensorCategory(id);
      message.success('删除成功');
      fetchCategories();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
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
        <span>
          <Button type="link" onClick={() => showModal(record)}>编辑</Button>
          <Popconfirm
            title="确定删除吗?"
            onConfirm={() => handleDelete(record.id)}
            okText="是"
            cancelText="否"
          >
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </span>
      ),
    },
  ];

  return (
    <div>
      <Button type="primary" onClick={() => showModal()} style={{ marginBottom: 16 }}>
        添加传感器类别
      </Button>
      <Table columns={columns} dataSource={categories} rowKey="id" />
      <Modal
        title={editingCategory ? '编辑传感器类别' : '添加传感器类别'}
        visible={isModalVisible}
        onOk={handleOk}
        onCancel={handleCancel}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SensorCategoryManagementPage;