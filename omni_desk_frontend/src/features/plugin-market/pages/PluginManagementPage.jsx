import { useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Tag, message, Popconfirm, Space, Typography,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPlugins, createPlugin, updatePlugin, deletePlugin,
} from '../api/pluginApi';
import PluginUploadModal from '../components/PluginUploadModal';

const { Title } = Typography;

const STATUS_MAP = {
  draft: { color: 'default', text: '草稿' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已批准' },
  rejected: { color: 'red', text: '已拒绝' },
  disabled: { color: 'gray', text: '已禁用' },
};

const CATEGORIES = ['数据处理', '计算分析', '文件转换', '自动化脚本', '其他'];

const PluginManagementPage = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPlugin, setEditingPlugin] = useState(null);
  const [uploadPlugin, setUploadPlugin] = useState(null);
  const [form] = Form.useForm();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['plugins-admin'],
    queryFn: () => fetchPlugins(),
  });

  const openCreateModal = () => {
    setEditingPlugin(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingPlugin(record);
    form.setFieldsValue(record);
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingPlugin) {
        await updatePlugin(editingPlugin.id, values);
        message.success('更新成功');
      } else {
        await createPlugin(values);
        message.success('创建成功');
      }
      setIsModalOpen(false);
      refetch();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deletePlugin(id);
      message.success('删除成功');
      refetch();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '标识符', dataIndex: 'slug', key: 'slug' },
    { title: '分类', dataIndex: 'category', key: 'category', render: (v) => <Tag>{v}</Tag> },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v) => <Tag color={STATUS_MAP[v]?.color}>{STATUS_MAP[v]?.text}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Button
            size="small"
            icon={<UploadOutlined />}
            onClick={() => setUploadPlugin(record)}
          />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const plugins = data?.results || data || [];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>插件管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          创建插件
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={plugins}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 10 }}
      />
      <Modal
        title={editingPlugin ? '编辑插件' : '创建插件'}
        open={isModalOpen}
        onOk={handleSave}
        onCancel={() => setIsModalOpen(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="slug" label="标识符" rules={[{ required: true }]}>
            <Input placeholder="英文短横线分隔，如 data-processor" />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}>
            <Select options={CATEGORIES.map((c) => ({ label: c, value: c }))} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="icon" label="图标">
            <Input placeholder="如 emoji 或图标类名" />
          </Form.Item>
        </Form>
      </Modal>

      {uploadPlugin && (
        <PluginUploadModal
          plugin={uploadPlugin}
          onClose={() => setUploadPlugin(null)}
          onSuccess={() => refetch()}
        />
      )}
    </div>
  );
};

export default PluginManagementPage;
