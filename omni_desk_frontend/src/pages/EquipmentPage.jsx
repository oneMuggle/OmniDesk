import React, { useState, useEffect } from 'react';
import { Button, Table, Modal, Form, Input, message } from 'antd';
import { 
  getEquipment,
  createEquipment,
  updateEquipment,
  deleteEquipment
} from '../api/equipment';
import './EquipmentPage.css';

const EquipmentPage = () => {
  const [equipmentList, setEquipmentList] = useState([]);
  const [form] = Form.useForm();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingEquipment, setEditingEquipment] = useState(null);

  const loadEquipment = React.useCallback(async () => {
    try {
      const response = await getEquipment();
      setEquipmentList(response.data);
    } catch (error) {
      message.error(error.message || '获取设备列表失败');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadEquipment();
  }, [loadEquipment]);

  const handleSubmit = async (values) => {
    try {
      if (editingEquipment) {
        await updateEquipment(editingEquipment.id, values);
        message.success('设备更新成功');
      } else {
        await createEquipment(values);
        message.success('设备添加成功');
      }
      setModalVisible(false);
      loadEquipment();
    } catch (error) {
      message.error(editingEquipment ? '更新设备失败' : '添加设备失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteEquipment(id);
      message.success('设备删除成功');
      loadEquipment();
    } catch (error) {
      message.error('设备删除失败');
    }
  };

  const columns = [
    {
      title: '设备名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '设备简介',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <>
          <Button type="link" onClick={() => {
            setEditingEquipment(record);
            form.setFieldsValue(record);
            setModalVisible(true);
          }}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </>
      ),
    },
  ];

  return (
    <div className="equipment-page">
      <div className="page-header">
        <h2>试验设备管理</h2>
        <Button type="primary" onClick={() => {
          setEditingEquipment(null);
          form.resetFields();
          setModalVisible(true);
        }}>
          添加设备
        </Button>
      </div>

      <Table 
        dataSource={equipmentList} 
        columns={columns} 
        rowKey="id"
        bordered
        pagination={{ pageSize: 8 }}
      />

      <Modal
        title={editingEquipment ? '编辑设备' : '新增设备'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ remember: true }}
        >
          <Form.Item
            label="设备名称"
            name="name"
            rules={[{ required: true, message: '请输入设备名称' }]}
          >
            <Input placeholder="请输入设备名称" />
          </Form.Item>

          <Form.Item
            label="设备简介"
            name="description"
            rules={[{ required: true, message: '请输入设备简介' }]}
          >
            <Input.TextArea rows={4} placeholder="请输入设备简介" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit">
              {editingEquipment ? '保存修改' : '确认添加'}
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default EquipmentPage;
