import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Badge, Popover, List, Button, Spin, Empty, message } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import notificationApi from '../api/notificationApi';

const NotificationBell = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // 未读数轮询(5s 一次,详见 plan §6.3)
  const { data: unreadData } = useQuery({
    queryKey: ['unreadCount'],
    queryFn: () => notificationApi.getUnreadCount().then((r) => r.data),
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
  });
  const unreadCount = unreadData?.unread_count || 0;

  // 拉取最近 5 条
  const { data: listData, isLoading } = useQuery({
    queryKey: ['recentNotifications'],
    queryFn: () =>
      notificationApi.getList({ page: 1, page_size: 5 }).then((r) => r.data),
    refetchInterval: 10000,
  });
  const recent = listData?.results || [];

  const markRead = useMutation({
    mutationFn: (id) => notificationApi.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unreadCount'] });
      queryClient.invalidateQueries({ queryKey: ['recentNotifications'] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationApi.markAllRead(),
    onSuccess: () => {
      message.success('已全部标记为已读');
      queryClient.invalidateQueries({ queryKey: ['unreadCount'] });
      queryClient.invalidateQueries({ queryKey: ['recentNotifications'] });
    },
  });

  const content = (
    <div style={{ width: 360, maxHeight: 480, overflow: 'auto' }}>
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : recent.length === 0 ? (
        <Empty description="暂无通知" />
      ) : (
        <>
          <List
            dataSource={recent}
            renderItem={(item) => (
              <List.Item
                key={item.id}
                style={{
                  background: item.is_read ? 'transparent' : '#f0f5ff',
                  padding: '8px 12px',
                }}
                actions={
                  !item.is_read
                    ? [
                        <Button
                          key="read"
                          type="link"
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
                  }
                  description={
                    <>
                      <div style={{ fontSize: 12 }}>{item.content}</div>
                      <small style={{ color: '#999' }}>
                        {item.type_display}
                      </small>
                    </>
                  }
                />
              </List.Item>
            )}
          />
          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <Button
              type="link"
              onClick={() => navigate('/notifications')}
            >
              查看全部
            </Button>
            {unreadCount > 0 && (
              <Button
                type="link"
                onClick={() => markAllRead.mutate()}
                loading={markAllRead.isPending}
              >
                全部已读
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );

  return (
    <Popover
      content={content}
      trigger="click"
      placement="bottomRight"
      overlayStyle={{ zIndex: 1050 }}
    >
      <Badge count={unreadCount} size="small" offset={[-4, 4]}>
        <Button
          type="text"
          icon={<BellOutlined style={{ fontSize: 18 }} />}
          aria-label="通知"
        />
      </Badge>
    </Popover>
  );
};

export default NotificationBell;
