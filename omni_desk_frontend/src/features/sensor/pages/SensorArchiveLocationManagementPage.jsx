import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm } from 'antd';
import { getStorageLocations, createStorageLocation, updateStorageLocation, deleteStorageLocation } from '../api/sensorApi';

const SensorArchiveLocationManagementPage = () => {
  const [locations, setLocations] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingLocation, setEditingLocation] = useState(null);
  const [form] = Form.useForm();

  const fetchLocations = async () => {
    try {
      const response = await getStorageLocations();
      setLocations(response.data.results);
    } catch (error) {
      message.error('获取存档位置失败');
    }
  };

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const response = await getStorageLocations();
        if (isMounted) {
          setLocations(response.data.results);
        }
      } catch (error) {
        message.error('获取存档位置失败');
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

  const showModal = (location = null) => {
    setEditingLocation(location);
    form.setFieldsValue(location ? { name: location.name, description: location.description } : { name: '', description: '' });
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingLocation(null);
    form.resetFields();
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
      fetchLocations();
      handleCancel();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteStorageLocation(id);
      message.success('删除成功');
      fetchLocations();
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
        添加存档位置
      </Button>
      <Table columns={columns} dataSource={locations} rowKey="id" />
      <Modal
        title={editingLocation ? '编辑存档位置' : '添加存档位置'}
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

export default SensorArchiveLocationManagementPage;