import { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Switch, Select, message, Popconfirm,
  Typography, Space, Tag,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  fetchIntegrations, createIntegration, updateIntegration, deleteIntegration,
} from '../api/integrationApi';

const { Title } = Typography;

const INTEGRATION_TYPES = [
  { label: 'iframe 嵌入', value: 'iframe' },
  { label: 'API 代理调用', value: 'api' },
  { label: '组件嵌入', value: 'widget' },
];

const IntegrationManagementPage = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingService, setEditingService] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => { loadServices(); }, []);

  const loadServices = async () => {
    setLoading(true);
    try {
      const data = await fetchIntegrations();
      setServices(data);
    } catch {
      message.error('加载集成服务失败');
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingService(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true });
    setIsModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingService(record);
    form.setFieldsValue(record);
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingService) {
        await updateIntegration(editingService.slug, values);
        message.success('更新成功');
      } else {
        await createIntegration(values);
        message.success('创建成功');
      }
      setIsModalOpen(false);
      loadServices();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (slug) => {
    try {
      await deleteIntegration(slug);
      message.success('删除成功');
      loadServices();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '标识符', dataIndex: 'slug', key: 'slug' },
    {
      title: '类型', dataIndex: 'integration_type', key: 'integration_type',
      render: (v) => {
        const typeMap = { iframe: 'blue', api: 'green', widget: 'orange' };
        return <Tag color={typeMap[v]}>{v}</Tag>;
      },
    },
    { title: '端点', dataIndex: 'endpoint_url', key: 'endpoint_url', ellipsis: true },
    { title: '激活', dataIndex: 'is_active', key: 'is_active', render: (v) => v ? '是' : '否', width: 60 },
    {
      title: '操作', key: 'action', width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.slug)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>集成服务管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          添加服务
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={services}
        rowKey="slug"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />
      <Modal
        title={editingService ? '编辑集成服务' : '添加集成服务'}
        open={isModalOpen}
        onOk={handleSave}
        onCancel={() => setIsModalOpen(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="服务名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="slug" label="标识符" rules={[{ required: true, pattern: /^[a-z0-9-]+$/ }]}>
            <Input placeholder="如: difai-chat" />
          </Form.Item>
          <Form.Item name="integration_type" label="集成类型" rules={[{ required: true }]}>
            <Select options={INTEGRATION_TYPES} />
          </Form.Item>
          <Form.Item name="endpoint_url" label="服务端点" rules={[{ required: true, type: 'url' }]}>
            <Input placeholder="http://..." />
          </Form.Item>
          <Form.Item name="embed_path" label="嵌入路径">
            <Input placeholder="iframe 嵌入时的路径" />
          </Form.Item>
          <Form.Item name="api_key" label="API 密钥">
            <Input.Password />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="is_active" label="激活" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default IntegrationManagementPage;
