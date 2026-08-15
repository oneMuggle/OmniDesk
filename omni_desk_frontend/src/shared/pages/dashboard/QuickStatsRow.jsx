import { Card, Col, Row, Statistic, Typography } from 'antd';
import {
  ExperimentOutlined,
  CalendarOutlined,
  VideoCameraOutlined,
  BellOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import { quickActions } from './dashboardData';

const { Text } = Typography;

const QuickStatsRow = ({ weeklyTrials, weeklySchedules, weeklyBookings }) => {
  return (
    <Row gutter={[16, 16]} className="stat-cards-row">
      {/* 本周试验 */}
      <Col xs={24} sm={12} lg={6}>
        <Card className="stat-card" hoverable>
          <Statistic
            title="本周试验"
            value={weeklyTrials.length}
            prefix={<ExperimentOutlined />}
            valueStyle={{ color: '#f59e0b' }}
          />
        </Card>
      </Col>

      {/* 本周排班 */}
      <Col xs={24} sm={12} lg={6}>
        <Card className="stat-card" hoverable>
          <Statistic
            title="本周排班"
            value={weeklySchedules.length}
            prefix={<CalendarOutlined />}
            valueStyle={{ color: '#3b82f6' }}
          />
        </Card>
      </Col>

      {/* 会议室预约 */}
      <Col xs={24} sm={12} lg={6}>
        <Card className="stat-card" hoverable>
          <Statistic
            title="会议室预约"
            value={weeklyBookings.length}
            prefix={<VideoCameraOutlined />}
            valueStyle={{ color: '#10b981' }}
          />
        </Card>
      </Col>

      {/* 快捷操作 */}
      <Col xs={24} sm={12} lg={6}>
        <Card className="stat-card quick-action-card" hoverable>
          <div className="quick-action-header">
            <BellOutlined className="quick-action-icon" />
            <span>快捷操作</span>
          </div>
          <div className="quick-action-grid">
            {quickActions.map(action => (
              <Link key={action.to} to={action.to} className="quick-action-item">
                <div className="quick-action-icon-btn" style={{ color: action.color }}>
                  {action.icon}
                </div>
                <Text className="quick-action-label">{action.title}</Text>
              </Link>
            ))}
          </div>
        </Card>
      </Col>
    </Row>
  );
};

QuickStatsRow.propTypes = {
  weeklyTrials: PropTypes.array.isRequired,
  weeklySchedules: PropTypes.array.isRequired,
  weeklyBookings: PropTypes.array.isRequired,
};

export default QuickStatsRow;
