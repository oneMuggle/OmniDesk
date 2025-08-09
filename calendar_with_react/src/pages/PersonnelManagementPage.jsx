import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, message, Space } from 'antd';
import { scheduleApi } from '../api/scheduleApi'; // 假设人员API也在scheduleApi中

const PersonnelFormModal = ({ visible, onCancel, onOk, initialData }) => {
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
      title={initialData.id ? "编辑人员" : "新增人员"}
      visible={visible}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label="姓名"
          rules={[{ required: true, message: '请输入姓名!' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="department"
          label="部门"
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="phone"
          label="电话"
        >
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
};

const PersonnelManagementPage = () => {
  const [personnel, setPersonnel] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentPersonnel, setCurrentPersonnel] = useState(null);

  useEffect(() => {
    fetchPersonnel();
  }, []);

  const fetchPersonnel = async () => {
    setLoading(true);
    try {
      const data = await scheduleApi.getPersonnel(); // 假设getPersonnel能获取所有人员
      setPersonnel(data);
    } catch (error) {
      message.error('获取人员列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setCurrentPersonnel(null);
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setCurrentPersonnel(record);
    setIsModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      // 假设scheduleApi中提供了deletePersonnel方法
      // 如果没有，需要修改scheduleApi.js或DRFForVue/events/views.py
      await scheduleApi.deletePersonnel(id); 
      message.success('人员删除成功');
      fetchPersonnel();
    } catch (error) {
      message.error('删除人员失败');
    }
  };

  const handleModalOk = async (values) => {
    try {
      if (currentPersonnel) {
        // 假设scheduleApi中提供了updatePersonnel方法
        await scheduleApi.updatePersonnel(currentPersonnel.id, values);
        message.success('人员更新成功');
      } else {
        // 假设scheduleApi中提供了createPersonnel方法
        await scheduleApi.createPersonnel(values);
        message.success('人员创建成功');
      }
      setIsModalVisible(false);
      fetchPersonnel();
    } catch (error) {
      message.error('保存人员失败');
    }
  };

  const columns = [
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '部门',
      dataIndex: 'department',
      key: 'department',
    },
    {
      title: '电话',
      dataIndex: 'phone',
      key: 'phone',
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

  return (
    <Card title="人员管理" extra={<Button type="primary" onClick={handleAdd}>新增人员</Button>}>
      <Table
        columns={columns}
        dataSource={personnel}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />
      <PersonnelFormModal
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleModalOk}
        initialData={currentPersonnel || {}}
      />
    </Card>
  );
};

export default PersonnelManagementPage;