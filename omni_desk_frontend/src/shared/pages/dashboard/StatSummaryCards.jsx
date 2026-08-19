import { Card, Col, Row, Statistic, Tag, Skeleton, Typography } from 'antd';
import { CalendarOutlined, NotificationOutlined, ProjectOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';

const { Text } = Typography;

const StatSummaryCards = ({ dashboardStats, statsLoading }) => {
  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
      {/* 未读通知 */}
      <Col xs={24} sm={12} lg={6}>
        <Card className="stat-card" hoverable>
          <Statistic
            title="未读通知"
            value={statsLoading ? undefined : dashboardStats?.unread_notifications ?? 0}
            prefix={<NotificationOutlined />}
            valueStyle={{ color: '#ef4444' }}
          />
          {statsLoading ? <Skeleton.Button active style={{ marginTop: 8, width: 80 }} /> : null}
        </Card>
      </Col>

      {/* 进行中项目 */}
      <Col xs={24} sm={12} lg={6}>
        <Card className="stat-card" hoverable>
          <Statistic
            title="进行中项目"
            value={statsLoading ? undefined : dashboardStats?.projects?.active_count ?? 0}
            prefix={<ProjectOutlined />}
            valueStyle={{ color: '#ec4899' }}
          />
        </Card>
      </Col>

      {/* 今日值班 */}
      <Col xs={24} sm={24} lg={12}>
        <Card className="stat-card" title={
          <span><CalendarOutlined style={{ marginRight: 8 }} />今日值班</span>
        }>
          {statsLoading ? (
            <Skeleton paragraph={{ rows: 1 }} active />
          ) : dashboardStats?.today_schedule?.length > 0 ? (
            <div style={{ display: 'flex', gap: 24 }}>
              {dashboardStats.today_schedule.map((s, i) => (
                <span key={i}>
                  {s.duty_person && <Tag color="blue">值班：{s.duty_person}</Tag>}
                  {s.duty_leader && <Tag color="orange">领导：{s.duty_leader}</Tag>}
                </span>
              ))}
            </div>
          ) : (
            <Text type="secondary">今日暂无排班</Text>
          )}
        </Card>
      </Col>
    </Row>
  );
};

StatSummaryCards.propTypes = {
  dashboardStats: PropTypes.object,
  statsLoading: PropTypes.bool.isRequired,
};

export default StatSummaryCards;
