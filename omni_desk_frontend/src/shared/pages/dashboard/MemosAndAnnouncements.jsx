import { Card, Col, Row, List, Empty, Tag, Typography } from 'antd';
import { ClockCircleOutlined, BellOutlined, RightOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import dayjs from 'dayjs';
import PropTypes from 'prop-types';
import SkeletonList from '../../components/SkeletonList';

const { Text } = Typography;

const MemosAndAnnouncements = ({ dashboardStats, statsLoading }) => {
  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
      {/* 待办事项 */}
      <Col xs={24} md={12}>
        <Card title={
          <span><ClockCircleOutlined style={{ marginRight: 8 }} />待办事项</span>
        } extra={<Link to="/memos" style={{ fontSize: 12 }}>查看全部 <RightOutlined /></Link>}>
          {statsLoading ? (
            <SkeletonList count={3} />
          ) : dashboardStats?.memos_due?.length > 0 ? (
            <List
              size="small"
              dataSource={dashboardStats.memos_due}
              renderItem={item => (
                <List.Item>
                  <List.Item.Meta
                    title={<Text strong>{item.title}</Text>}
                    description={
                      <Text type="secondary">
                        {item.reminder_time ? `截止：${dayjs(item.reminder_time).format('YYYY-MM-DD HH:mm')}` : '无截止时间'}
                      </Text>
                    }
                  />
                  <Tag color={item.is_completed ? 'green' : 'orange'}>
                    {item.is_completed ? '已完成' : '进行中'}
                  </Tag>
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无待办事项" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      </Col>

      {/* 最新公告 */}
      <Col xs={24} md={12}>
        <Card title={
          <span><BellOutlined style={{ marginRight: 8 }} />最新公告</span>
        } extra={<Link to="/announcements" style={{ fontSize: 12 }}>查看全部 <RightOutlined /></Link>}>
          {statsLoading ? (
            <SkeletonList count={3} />
          ) : dashboardStats?.recent_announcements?.length > 0 ? (
            <List
              size="small"
              dataSource={dashboardStats.recent_announcements}
              renderItem={item => (
                <List.Item>
                  <List.Item.Meta
                    title={<Text strong>{item.title}</Text>}
                    description={
                      <Text type="secondary">
                        {item.author__username ? `发布人：${item.author__username}` : ''}
                        {item.created_at ? ` · ${dayjs(item.created_at).fromNow()}` : ''}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无公告" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      </Col>
    </Row>
  );
};

MemosAndAnnouncements.propTypes = {
  dashboardStats: PropTypes.object,
  statsLoading: PropTypes.bool.isRequired,
};

export default MemosAndAnnouncements;
