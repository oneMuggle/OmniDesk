import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm } from 'antd';
import {
  getStorageLocations,
  createStorageLocation,
  updateStorageLocation,
  deleteStorageLocation,
} from '../../api/sensorApi';

const StorageLocationManagementPage = () => {
  const [locations, setLocations] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingLocation, setEditingLocation] = useState(null);
  const [form] = Form.useForm();

  const fetchLocations = async () => {
    try {
      const response = await getStorageLocations();
      setLocations(response.data);
    } catch (error) {
      message.error('获取存放地点列表失败');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      await fetchLocations();
    };
    loadData();
  }, []);

  const handleAdd = () => {
    setEditingLocation(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingLocation(record);
    form.setFieldsValue(record);
    setIsModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await deleteStorageLocation(id);
      message.success('删除成功');
      await fetchLocations();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingLocation) {
        await updateStorageLocation(editingLocation.id, values);
        message.success('更新成功');
      } else {
        await createStorageLocation(values);
        message.success('添加成功');
      }
      setIsModalVisible(false);
      await fetchLocations();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleCancel = () => {
    setIsModalVisible(false);
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
          <Button type="link" onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确定删除吗?"
            onConfirm={() => handleDelete(record.id)}
            okText="是"
            cancelText="否"
          >
            <Button type="link" danger>
              删除
            </Button>
          </Popconfirm>
        </span>
      ),
    },
  ];

  return (
    <div>
      <Button type="primary" onClick={handleAdd} style={{ marginBottom: 16 }}>
        添加存放地点
      </Button>
      <Table columns={columns} dataSource={locations} rowKey="id" />
      <Modal
        title={editingLocation ? '编辑存放地点' : '添加存放地点'}
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
          <Form.Item name="description" label="描述">
            <Input.TextArea />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default StorageLocationManagementPage;