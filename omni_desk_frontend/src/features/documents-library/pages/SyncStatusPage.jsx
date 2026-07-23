/**
 * 同步状态页 (paperless-ngx 集成)
 *
 * 列出当前用户的所有 outbox 项,按状态分组显示。
 * 后端接口:`/api/paperless/outbox/`
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Table, Tabs, Button, Space, Tag, message, Tooltip, Popconfirm, Empty, Spin, Typography,
} from 'antd';
import {
  ReloadOutlined, RedoOutlined, DeleteOutlined,
} from '@ant-design/icons';
import axiosInstance from '../../../shared/api/axiosConfig';
import PaperlessHealthBanner from '../components/PaperlessHealthBanner';
import SyncStatusBadge from '../components/SyncStatusBadge';

const { Text } = Typography;

const fetchOutbox = async (params) => {
  const { data } = await axiosInstance.get('/paperless/outbox/', { params });
  if (Array.isArray(data)) return { results: data, count: data.length };
  if (data?.results) return data;
  return { results: [], count: 0 };
};

const retryOutboxItem = async (id) => {
  const { data } = await axiosInstance.post(`/paperless/outbox/${id}/retry/`);
  return data;
};

const deleteOutboxItem = async (id) => {
  await axiosInstance.delete(`/paperless/outbox/${id}/`);
};

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待同步' },
  { key: 'syncing', label: '同步中' },
  { key: 'failed', label: '失败' },
  { key: 'dead', label: '需重试' },
  { key: 'synced', label: '已同步' },
];

export default function SyncStatusPage() {
  const [activeTab, setActiveTab] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const queryClient = useQueryClient();

  const params = {
    page,
    page_size: pageSize,
    ...(activeTab !== 'all' ? { status: activeTab } : {}),
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['paperless-outbox', activeTab, page, pageSize],
    queryFn: () => fetchOutbox(params),
    refetchInterval: 15000, // 每 15 秒自动刷新
    keepPreviousData: true,
  });

  const retryMutation = useMutation({
    mutationFn: retryOutboxItem,
    onSuccess: () => {
      message.success('已重新加入同步队列');
      queryClient.invalidateQueries({ queryKey: ['paperless-outbox'] });
    },
    onError: (error) => {
      message.error(error.response?.data?.detail || '重试失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteOutboxItem,
    onSuccess: () => {
      message.success('已删除');
      queryClient.invalidateQueries({ queryKey: ['paperless-outbox'] });
    },
    onError: (error) => {
      message.error(error.response?.data?.detail || '删除失败');
    },
  });

  const items = data?.results || [];
  const total = data?.count || 0;

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      ellipsis: true,
      render: (text) => <Text strong>{text || '—'}</Text>,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text) => text || '—',
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (val) => <SyncStatusBadge status={val || 'pending'} />,
    },
    {
      title: '重试次数',
      dataIndex: 'retry_count',
      key: 'retry_count',
      width: 100,
      render: (val) => (
        <Tag color={val > 3 ? 'red' : val > 0 ? 'orange' : 'default'}>
          {val ?? 0}
        </Tag>
      ),
    },
    {
      title: '错误信息',
      dataIndex: 'last_error',
      key: 'last_error',
      ellipsis: true,
      render: (val) => val
        ? (
          <Tooltip title={val}>
            <Text type="danger">{val.slice(0, 60)}{val.length > 60 ? '...' : ''}</Text>
          </Tooltip>
        )
        : '—',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val) => (val ? new Date(val).toLocaleString('zh-CN') : '—'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          {(record.status === 'failed' || record.status === 'dead') && (
            <Tooltip title="重试同步">
              <Button
                size="small"
                type="text"
                icon={<RedoOutlined />}
                loading={retryMutation.isPending}
                onClick={() => retryMutation.mutate(record.id)}
              />
            </Tooltip>
          )}
          <Popconfirm
            title="确认删除此同步记录?"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} align="center">
        <h2 style={{ margin: 0 }}>同步状态</h2>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
      </Space>

      <PaperlessHealthBanner />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key);
          setPage(1);
        }}
        items={STATUS_TABS}
        style={{ marginBottom: 16 }}
      />

      <Spin spinning={isLoading}>
        {items.length === 0 && !isLoading ? (
          <Empty description="暂无同步记录" />
        ) : (
          <Table
            rowKey="id"
            columns={columns}
            dataSource={items}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
              onChange: (p, ps) => {
                if (ps !== pageSize) {
                  setPage(1);
                } else {
                  setPage(p);
                }
                setPageSize(ps);
              },
            }}
          />
        )}
      </Spin>
    </div>
  );
}
