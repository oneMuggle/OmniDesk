import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message } from 'antd';
import { 
  getPersonnel, 
  createPerson, 
  updatePerson, 
  deletePerson 
} from '../api/personnel';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';

const PersonnelPage = () => {
  const [form] = Form.useForm();
  const [data, setData] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const columns = [
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '职位',
      dataIndex: 'position',
      key: 'position',
    },
    {
      title: '联系电话',
      dataIndex: 'phone',
      key: 'phone',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <div className='space-x-2'>
          <Button 
            type="primary" 
            icon={<EditOutlined />}
            onClick={() => showEditModal(record)}
          >
            编辑
          </Button>
          <Button 
            danger 
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </div>
      ),
    },
  ];

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const result = await getPersonnel();
      setData(result);
    } catch (error) {
      message.error('获取人员数据失败');
    }
  };

  const showCreateModal = () => {
    form.resetFields();
    setEditingId(null);
    setIsModalVisible(true);
  };

  const showEditModal = (record) => {
    form.setFieldsValue(record);
    setEditingId(record.id);
    setIsModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingId) {
        await updatePerson(editingId, values);
        message.success('更新成功');
      } else {
        await createPerson(values);
        message.success('创建成功');
      }
      setIsModalVisible(false);
      fetchData();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleDelete = async (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该人员信息吗？',
      onOk: async () => {
        try {
          await deletePerson(id);
          message.success('删除成功');
          fetchData();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  return (
    <div className='p-4'>
      <div className='mb-4 flex justify-between'>
        <h2 className='text-xl font-bold'>人员管理系统</h2>
        <Button 
          type="primary" 
          icon={<PlusOutlined />}
          onClick={showCreateModal}
        >
          新增人员
        </Button>
      </div>

      <Table 
        columns={columns} 
        dataSource={data} 
        rowKey="id"
        bordered
        pagination={{ pageSize: 8 }}
      />

      <Modal
        title={editingId ? '编辑人员' : '新增人员'}
        visible={isModalVisible}
        onOk={handleSubmit}
        onCancel={() => setIsModalVisible(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="姓名"
            name="name"
            rules={[{ required: true, message: '请输入姓名' }]}
          >
            <Input placeholder="请输入姓名" />
          </Form.Item>

          <Form.Item
            label="职位"
            name="position"
            rules={[{ required: true, message: '请输入职位' }]}
          >
            <Input placeholder="请输入职位" />
          </Form.Item>

          <Form.Item
            label="联系电话"
            name="phone"
            rules={[
              { required: true, message: '请输入联系电话' },
              { pattern: /^1[3-9]\d{9}$/, message: '请输入有效的手机号码' }
            ]}
          >
            <Input placeholder="请输入联系电话" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PersonnelPage;
