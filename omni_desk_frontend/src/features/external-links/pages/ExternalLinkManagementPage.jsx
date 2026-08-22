import { useState } from 'react';
import {
  Button, Modal, Form, Input, Switch, InputNumber, Select,
  message, Popconfirm, Typography, Space, Tag,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import {
  fetchExternalLinks, createExternalLink, updateExternalLink, deleteExternalLink,
} from '../api/externalLinksApi';
import { useCrudQuery } from '../../../shared/hooks/useCrudQuery';
import DataTable from '../../../shared/components/DataTable';

const { Title } = Typography;

const CATEGORIES = ['开发工具', 'CI/CD', '文档管理', '云服务', '其他'];

const EXTERNAL_LINKS_QUERY_KEY = ['external-links'];

const ExternalLinkManagementPage = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLink, setEditingLink] = useState(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  // fetchExternalLinks 返回分组数组,扁平化在 queryFn 内完成
  const linksQuery = useCrudQuery(
    EXTERNAL_LINKS_QUERY_KEY,
    async () => {
      const data = await fetchExternalLinks();
      return data.flatMap((g) => g.links);
    },
    { errorMessage: '加载外链列表失败' }
  );
  const links = linksQuery.data ?? [];
  const loading = linksQuery.isLoading;

  // 增删改后刷新列表(等价原手动 loadLinks)
  const loadLinks = () => queryClient.invalidateQueries({ queryKey: EXTERNAL_LINKS_QUERY_KEY });

  const openCreateModal = () => {
    setEditingLink(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingLink(record);
    form.setFieldsValue(record);
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingLink) {
        await updateExternalLink(editingLink.id, values);
        message.success('更新成功');
      } else {
        await createExternalLink(values);
        message.success('创建成功');
      }
      setIsModalOpen(false);
      loadLinks();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteExternalLink(id);
      message.success('删除成功');
      loadLinks();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category', render: (v) => <Tag>{v}</Tag> },
    { title: '链接', dataIndex: 'url', key: 'url', ellipsis: true },
    { title: 'SSO', dataIndex: 'sso_enabled', key: 'sso_enabled', render: (v) => v ? '是' : '否' },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    {
      title: '操作', key: 'action', width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} aria-label="编辑" onClick={() => openEditModal(record)} />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} aria-label="删除" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>外链管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          添加外链
        </Button>
      </div>
      <DataTable
        columns={columns}
        dataSource={links}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        showActions={false}
      />
      <Modal
        title={editingLink ? '编辑外链' : '添加外链'}
        open={isModalOpen}
        onOk={handleSave}
        onCancel={() => setIsModalOpen(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="链接地址" rules={[{ required: true, type: 'url' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}>
            <Select options={CATEGORIES.map((c) => ({ label: c, value: c }))} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="icon" label="图标类名">
            <Input placeholder="如: CodeOutlined" />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="激活" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="sso_enabled" label="启用 SSO" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="sso_token_endpoint" label="SSO Token 端点">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ExternalLinkManagementPage;
