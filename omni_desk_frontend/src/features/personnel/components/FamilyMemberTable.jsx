import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { getFamilyMembers, createFamilyMember, updateFamilyMember, deleteFamilyMember } from '../api/personnelApi';
import { Button, Table, Modal, Form, Input } from 'antd';

const FamilyMemberTable = ({ personnelId }) => {
  const [familyMembers, setFamilyMembers] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingFamilyMember, setEditingFamilyMember] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => {
    const fetchFamilyMembersData = async () => {
      if (!personnelId) return;
      try {
        const response = await getFamilyMembers(personnelId);
        setFamilyMembers(response.data || []);
      } catch (error) {
        setFamilyMembers([]);
      }
    };

    fetchFamilyMembersData();
  }, [personnelId]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingFamilyMember) {
        await updateFamilyMember(editingFamilyMember.id, { ...values, personnel: personnelId });
      } else {
        await createFamilyMember({ ...values, personnel: personnelId });
      }
      // Re-fetch data after modal is closed
      const fetch = async () => {
        if (!personnelId) return;
        try {
          const response = await getFamilyMembers(personnelId);
          setFamilyMembers(response.data || []);
        } catch (error) {
          console.error('Error re-fetching family members:', error);
        }
      };
      fetch();
      setIsModalVisible(false);
      setEditingFamilyMember(null);
    } catch (error) {
      console.error('Failed to save family member:', error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteFamilyMember(id);
      // Re-fetch data after deletion
      const fetch = async () => {
        if (!personnelId) return;
        try {
          const response = await getFamilyMembers(personnelId);
          setFamilyMembers(response.data || []);
        } catch (error) {
          console.error('Error re-fetching family members after delete:', error);
        }
      };
      fetch();
    } catch (error) {
      console.error('Failed to delete family member:', error);
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
      <Table dataSource={Array.isArray(familyMembers) ? familyMembers : []} columns={columns} rowKey="id" />
      <Modal
        title={editingFamilyMember ? '编辑家庭成员' : '添加家庭成员'}
        open={isModalVisible}
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

FamilyMemberTable.propTypes = {
  personnelId: PropTypes.number.isRequired,
};

export default FamilyMemberTable;