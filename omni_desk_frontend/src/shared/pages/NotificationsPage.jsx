import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Tag, Typography, Button, Space } from 'antd';
import dayjs from 'dayjs';
import { CheckOutlined } from '@ant-design/icons';
import notificationApi from '../../features/notifications/api/notificationApi';

const { Title } = Typography;

const TYPE_TAG = {
  schedule_change: { color: 'blue', label: '排班变更' },
  announcement: { color: 'green', label: '公告发布' },
  memo_due: { color: 'orange', label: '备忘录到期' },
  calibration_reminder: { color: 'purple', label: '校准提醒' },
  project_update: { color: 'cyan', label: '项目更新' },
  compliance_issue: { color: 'red', label: '合规问题' },
  system: { color: 'default', label: '系统通知' },
};

const NotificationsPage = () => {
  const [filter, setFilter] = useState('all');
  const queryClient = useQueryClient();

  const notificationsQuery = useQuery({
    queryKey: ['notifications', filter],
    queryFn: () => {
      const params = filter !== 'all' ? { is_read: filter === 'read' ? 'true' : 'false' } : {};
      return notificationApi.getList(params);
    },
    select: (res) => res.data.results || res.data || [],
  });

  const markReadMutation = useMutation({
    mutationFn: (id) => notificationApi.markRead(id),
    onSuccess: () => queryClient.invalidateQueries(['notifications']),
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationApi.markAllRead(),
    onSuccess: () => queryClient.invalidateQueries(['notifications']),
  });

  const handleRowClick = (record) => {
    if (!record.is_read) {
      markReadMutation.mutate(record.id);
    }
    if (record.link) {
      window.location.hash = record.link;
    }
  };

  const columns = [
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type) => {
        const info = TYPE_TAG[type] || TYPE_TAG.system;
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (text, record) => (
        <Space>
          {!record.is_read && <Tag color="red" style={{ marginRight: 0 }}>未读</Tag>}
          {text}
        </Space>
      ),
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date) => dayjs(date).format('YYYY-MM-DD HH:mm'),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={2} style={{ margin: 0 }}>通知中心</Title>
        <Space>
          <Button
            type={filter === 'all' ? 'primary' : 'default'}
            onClick={() => setFilter('all')}
          >
            全部
          </Button>
          <Button
            type={filter === 'unread' ? 'primary' : 'default'}
            onClick={() => setFilter('unread')}
          >
            未读
          </Button>
          <Button
            type={filter === 'read' ? 'primary' : 'default'}
            onClick={() => setFilter('read')}
          >
            已读
          </Button>
          <Button
            icon={<CheckOutlined />}
            onClick={() => markAllReadMutation.mutate()}
            loading={markAllReadMutation.isPending}
          >
            全部标记已读
          </Button>
        </Space>
      </div>
      <Table
        columns={columns}
        dataSource={notificationsQuery.data?.map(n => ({ ...n, key: n.id })) || []}
        loading={notificationsQuery.isLoading}
        pagination={{ pageSize: 10 }}
        rowClassName={(record) => record.is_read ? '' : 'notification-unread'}
        onRow={(record) => ({ onClick: () => handleRowClick(record) })}
      />
    </div>
  );
};

export default NotificationsPage;
