import React, { useState } from 'react';
import { createQualification, updateQualification, deleteQualification } from '../../api/personnelApi';
import { Button, Table, Modal, Form, Input } from 'antd';

const ProfessionalQualificationTable = ({ qualifications, personnelId, fetchQualifications }) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingQualification, setEditingQualification] = useState(null);
  const [form] = Form.useForm();

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingQualification) {
        await updateQualification(editingQualification.id, { ...values, personnel: personnelId });
      } else {
        await createQualification({ ...values, personnel: personnelId });
      }
      fetchQualifications();
      setIsModalVisible(false);
      setEditingQualification(null);
    } catch (error) {
      console.error('Failed to save qualification', error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteQualification(id);
      fetchQualifications();
    } catch (error) {
      console.error('Failed to delete qualification', error);
    }
  };

  const columns = [
    { title: '证书名称', dataIndex: 'name', key: 'name' },
    { title: '颁发机构', dataIndex: 'issuing_authority', key: 'issuing_authority' },
    { title: '颁发日期', dataIndex: 'issue_date', key: 'issue_date' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <span>
          <Button type="link" onClick={() => { setEditingQualification(record); setIsModalVisible(true); form.setFieldsValue(record); }}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </span>
      ),
    },
  ];

  return (
    <div>
      <Button type="primary" onClick={() => { setEditingQualification(null); setIsModalVisible(true); form.resetFields(); }} style={{ marginBottom: 16 }}>
        添加职业资质
      </Button>
      <Table dataSource={qualifications || []} columns={columns} rowKey="id" />
      <Modal
        title={editingQualification ? '编辑职业资质' : '添加职业资质'}
        visible={isModalVisible}
        onOk={handleOk}
        onCancel={() => { setIsModalVisible(false); setEditingQualification(null); }}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="证书名称" rules={[{ required: true, message: '请输入证书名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="issuing_authority" label="颁发机构" rules={[{ required: true, message: '请输入颁发机构' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="issue_date" label="颁发日期" rules={[{ required: true, message: '请输入颁发日期' }]}>
            <Input type="date" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProfessionalQualificationTable;