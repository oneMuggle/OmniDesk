import React, { useState, useEffect } from 'react';
import { getFamilyMembers, createFamilyMember, updateFamilyMember, deleteFamilyMember } from '../../api/personnelApi';
import { Button, Table, Modal, Form, Input } from 'antd';

const FamilyMemberTable = ({ personnelId }) => {
  const [familyMembers, setFamilyMembers] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingFamilyMember, setEditingFamilyMember] = useState(null);
  const [form] = Form.useForm();

  const fetchFamilyMembers = React.useCallback(async () => {
    if (!personnelId) return;
    try {
      const response = await getFamilyMembers(personnelId);
      setFamilyMembers(response.data);
    } catch (error) {
      console.error('Failed to fetch family members', error);
    }
  }, [personnelId]);

  useEffect(() => {
    fetchFamilyMembers();
  }, [fetchFamilyMembers]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingFamilyMember) {
        await updateFamilyMember(editingFamilyMember.id, { ...values, personnel: personnelId });
      } else {
        await createFamilyMember({ ...values, personnel: personnelId });
      }
      fetchFamilyMembers();
      setIsModalVisible(false);
      setEditingFamilyMember(null);
    } catch (error) {
      console.error('Failed to save family member', error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteFamilyMember(id);
      fetchFamilyMembers();
    } catch (error) {
      console.error('Failed to delete family member', error);
    }
  };

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name' },
    { title: '关系', dataIndex: 'relationship', key: 'relationship' },
    { title: '联系电话', dataIndex: 'contact_number', key: 'contact_number' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <span>
          <Button type="link" onClick={() => { setEditingFamilyMember(record); setIsModalVisible(true); form.setFieldsValue(record); }}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </span>
      ),
    },
  ];

  return (
    <div>
      <Button type="primary" onClick={() => { setEditingFamilyMember(null); setIsModalVisible(true); form.resetFields(); }} style={{ marginBottom: 16 }}>
        添加家庭成员
      </Button>
      <Table dataSource={familyMembers} columns={columns} rowKey="id" />
      <Modal
        title={editingFamilyMember ? '编辑家庭成员' : '添加家庭成员'}
        visible={isModalVisible}
        onOk={handleOk}
        onCancel={() => { setIsModalVisible(false); setEditingFamilyMember(null); }}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="relationship" label="关系" rules={[{ required: true, message: '请输入关系' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="contact_number" label="联系电话" rules={[{ required: true, message: '请输入联系电话' }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default FamilyMemberTable;