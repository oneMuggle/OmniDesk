import { Card, Col, List, Row, Typography, Empty } from 'antd';
import {
  ExperimentOutlined,
  CalendarOutlined,
  VideoCameraOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import dayjs from 'dayjs';
import PropTypes from 'prop-types';
import SkeletonList from '../../components/SkeletonList';

const { Title, Text } = Typography;

const DATE_FORMAT = 'YYYY-MM-DD';

const WeeklyOverview = ({ weeklyTrials, weeklySchedules, weeklyBookings, loading, errors }) => {
  return (
    <div className="welcome-page-overview">
      <Title level={4} className="section-title">本周概览</Title>
      <Row gutter={[16, 16]}>
        {/* 试验日程 */}
        <Col xs={24} sm={24} md={8}>
          <Card
            className="dashboard-list-card"
            title={
              <div className="card-title-bar">
                <ExperimentOutlined style={{ color: '#f59e0b' }} />
                <span>试验日程</span>
              </div>
            }
            extra={
              <Link to="/trial-schedule" className="card-extra-link">
                查看全部 <RightOutlined />
              </Link>
            }
          >
            {loading ? (
              <SkeletonList count={3} />
            ) : errors.trials ? (
              <Empty description="加载失败" />
            ) : weeklyTrials.length === 0 ? (
              <Empty description="本周暂无试验日程" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                itemLayout="horizontal"
                dataSource={weeklyTrials}
                renderItem={item => (
                  <List.Item className="dashboard-list-item">
                    <List.Item.Meta
                      title={<Text strong>{item.title}</Text>}
                      description={
                        <div className="list-item-description">
                          <Text type="secondary">
                            {item.start_date ? dayjs(item.start_date).format(DATE_FORMAT) : 'N/A'}
                            {item.end_date ? ` - ${dayjs(item.end_date).format(DATE_FORMAT)}` : ''}
                          </Text>
                          <Text type="secondary">负责人: {item.responsible_persons?.map(p => p.name).join(', ') || 'N/A'}</Text>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* 排班日程 */}
        <Col xs={24} sm={24} md={8}>
          <Card
            className="dashboard-list-card"
            title={
              <div className="card-title-bar">
                <CalendarOutlined style={{ color: '#3b82f6' }} />
                <span>排班日程</span>
              </div>
            }
            extra={
              <Link to="/shift-schedule" className="card-extra-link">
                查看全部 <RightOutlined />
              </Link>
            }
          >
            {loading ? (
              <SkeletonList count={3} />
            ) : errors.schedules ? (
              <Empty description="加载失败" />
            ) : weeklySchedules.length === 0 ? (
              <Empty description="本周暂无排班日程" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                itemLayout="horizontal"
                dataSource={weeklySchedules}
                renderItem={item => (
                  <List.Item className="dashboard-list-item">
                    <List.Item.Meta
                      title={<Text strong>{dayjs(item.duty_date).format(DATE_FORMAT)}</Text>}
                      description={
                        <div className="list-item-description">
                          <Text type="secondary">值班人员: {item.duty_person ? item.duty_person.name : 'N/A'}</Text>
                          <Text type="secondary">值班领导: {item.duty_leader ? item.duty_leader.name : 'N/A'}</Text>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* 会议室预约 */}
        <Col xs={24} sm={24} md={8}>
          <Card
            className="dashboard-list-card"
            title={
              <div className="card-title-bar">
                <VideoCameraOutlined style={{ color: '#10b981' }} />
                <span>会议室预约</span>
              </div>
            }
            extra={
              <Link to="/meeting-rooms" className="card-extra-link">
                查看全部 <RightOutlined />
              </Link>
            }
          >
            {loading ? (
              <SkeletonList count={3} />
            ) : errors.bookings ? (
              <Empty description="加载失败" />
            ) : weeklyBookings.length === 0 ? (
              <Empty description="本周暂无会议室预约" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                itemLayout="horizontal"
                dataSource={weeklyBookings}
                renderItem={item => (
                  <List.Item className="dashboard-list-item">
                    <List.Item.Meta
                      title={<Text strong>{item.title}</Text>}
                      description={
                        <div className="list-item-description">
                          <Text type="secondary">
                            {new Date(item.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            {' - '}
                            {new Date(item.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </Text>
                          <Text type="secondary">会议室: {item.meeting_room_name}</Text>
                          <Text type="secondary">预约人: {item.user ? item.user.username : 'N/A'}</Text>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

WeeklyOverview.propTypes = {
  weeklyTrials: PropTypes.array.isRequired,
  weeklySchedules: PropTypes.array.isRequired,
  weeklyBookings: PropTypes.array.isRequired,
  loading: PropTypes.bool.isRequired,
  errors: PropTypes.shape({
    trials: PropTypes.bool,
    schedules: PropTypes.bool,
    bookings: PropTypes.bool,
  }).isRequired,
};

export default WeeklyOverview;
