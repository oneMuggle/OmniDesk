import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  List,
  Button,
  Spin,
  Empty,
  Pagination,
  Select,
  Space,
  Card,
  message,
  Tag,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import notificationApi from '../api/notificationApi';

const TYPE_FILTER_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'schedule_change', label: '排班变更' },
  { value: 'announcement', label: '公告' },
  { value: 'system', label: '系统' },
  { value: 'position_changed', label: '岗位变动' },
  { value: 'emergency_contact', label: '紧急联系人' },
  { value: 'account_linked', label: '账号关联' },
];

const NotificationCenter = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [typeFilter, setTypeFilter] = useState('');
  const [isReadFilter, setIsReadFilter] = useState('');

  const params = { page, page_size: pageSize };
  if (typeFilter) params.type = typeFilter;
  if (isReadFilter !== '') params.is_read = isReadFilter;

  const { data, isLoading } = useQuery({
    queryKey: ['notifications', params],
    queryFn: () => notificationApi.getList(params).then((r) => r.data),
    refetchOnWindowFocus: false,
  });
  const list = data?.results || [];
  const total = data?.count || 0;

  const markRead = useMutation({
    mutationFn: (id) => notificationApi.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['unreadCount'] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationApi.markAllRead(),
    onSuccess: () => {
      message.success('已全部标记为已读');
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['unreadCount'] });
    },
  });

  return (
    <Card
      title="通知中心"
      extra={
        <Button
          type="primary"
          onClick={() => markAllRead.mutate()}
          loading={markAllRead.isPending}
        >
          全部已读
        </Button>
      }
    >
      <Space style={{ marginBottom: 16 }}>
        <span>类型:</span>
        <Select
          value={typeFilter}
          onChange={setTypeFilter}
          options={TYPE_FILTER_OPTIONS}
          style={{ width: 160 }}
        />
        <span>已读状态:</span>
        <Select
          value={isReadFilter}
          onChange={setIsReadFilter}
          options={[
            { value: '', label: '全部' },
            { value: 'false', label: '未读' },
            { value: 'true', label: '已读' },
          ]}
          style={{ width: 120 }}
        />
      </Space>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : list.length === 0 ? (
        <Empty description="暂无通知" />
      ) : (
        <List
          dataSource={list}
          renderItem={(item) => (
            <List.Item
              key={item.id}
              style={{
                background: item.is_read ? 'transparent' : '#f0f5ff',
                padding: '12px 16px',
                borderRadius: 4,
                marginBottom: 4,
              }}
              actions={
                !item.is_read
                  ? [
                      <Button
                        key="read"
                        size="small"
                        onClick={() => markRead.mutate(item.id)}
                      >
                        标记已读
                      </Button>,
                    ]
                  : []
              }
            >
              <List.Item.Meta
                title={
                  <Space>
                    <a
                      href={item.link || '#'}
                      onClick={(e) => {
                        e.preventDefault();
                        if (item.link) navigate(item.link);
                        if (!item.is_read) markRead.mutate(item.id);
                      }}
                    >
                      {item.title}
                    </a>
                    <Tag>{item.type_display}</Tag>
                    {item.priority >= 3 && (
                      <Tag color="red">紧急</Tag>
                    )}
                  </Space>
                }
                description={
                  <>
                    <div>{item.content}</div>
                    <small style={{ color: '#999' }}>
                      {new Date(item.created_at).toLocaleString('zh-CN')}
                    </small>
                  </>
                }
              />
            </List.Item>
          )}
        />
      )}

      {total > pageSize && (
        <Pagination
          current={page}
          total={total}
          pageSize={pageSize}
          onChange={setPage}
          style={{ textAlign: 'center', marginTop: 16 }}
        />
      )}
    </Card>
  );
};

export default NotificationCenter;
