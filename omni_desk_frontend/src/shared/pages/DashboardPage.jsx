import { useState, useEffect } from 'react';
import { Typography, Card, Row, Col, List, Empty, Statistic, Tag, Skeleton } from 'antd';
import {
  ExperimentOutlined,
  CalendarOutlined,
  VideoCameraOutlined,
  BellOutlined,
  FileTextOutlined,
  ProjectOutlined,
  RightOutlined,
  ClockCircleOutlined,
  NotificationOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');
import apiClient from '../api/apiClient';
import SkeletonList from '../components/SkeletonList';
import './DashboardPage.css';
import { logger } from '../utils/logger';

const { Title, Text } = Typography;

const DATE_FORMAT = 'YYYY-MM-DD';

const quickActions = [
  { to: '/announcements', icon: <BellOutlined />, title: '查看公告', color: '#6366f1' },
  { to: '/meeting-rooms', icon: <VideoCameraOutlined />, title: '预约会议室', color: '#10b981' },
  { to: '/trial-schedule', icon: <ExperimentOutlined />, title: '试验日程', color: '#f59e0b' },
  { to: '/shift-schedule', icon: <CalendarOutlined />, title: '排班日程', color: '#3b82f6' },
  { to: '/memos', icon: <FileTextOutlined />, title: '备忘录', color: '#8b5cf6' },
  { to: '/projects', icon: <ProjectOutlined />, title: '项目管理', color: '#ec4899' },
];

const DashboardPage = () => {
  const [loading, setLoading] = useState(true);
  const [weeklyTrials, setWeeklyTrials] = useState([]);
  const [weeklySchedules, setWeeklySchedules] = useState([]);
  const [weeklyBookings, setWeeklyBookings] = useState([]);
  const [errors, setErrors] = useState({});

  // 新增：仪表盘聚合数据
  const [dashboardStats, setDashboardStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    const fetchWeeklyData = async () => {
      setLoading(true);

      const results = await Promise.allSettled([
        apiClient.get('events/trials/this-week/'),
        (async () => {
          const today = new Date();
          const startOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1)));
          const endOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + 7));
          return apiClient.get('events/schedules/by-date-range/', {
            params: {
              start_date: startOfWeek.toISOString().split('T')[0],
              end_date: endOfWeek.toISOString().split('T')[0]
            }
          });
        })(),
        apiClient.get('meeting-rooms/meeting-room-bookings/this-week/'),
      ]);

      const [trialsResult, schedulesResult, bookingsResult] = results;

      if (trialsResult.status === 'fulfilled') {
        setWeeklyTrials(trialsResult.value.data);
      } else {
        logger.error('Error fetching weekly trials:', trialsResult.reason);
        setErrors(prev => ({ ...prev, trials: true }));
      }

      if (schedulesResult.status === 'fulfilled') {
        setWeeklySchedules(schedulesResult.value.data);
      } else {
        logger.error('Error fetching weekly schedules:', schedulesResult.reason);
        setErrors(prev => ({ ...prev, schedules: true }));
      }

      if (bookingsResult.status === 'fulfilled') {
        setWeeklyBookings(bookingsResult.value.data);
      } else {
        logger.error('Error fetching weekly bookings:', bookingsResult.reason);
        setErrors(prev => ({ ...prev, bookings: true }));
      }

      setLoading(false);
    };

    fetchWeeklyData();
  }, []);

  // 获取仪表盘聚合数据
  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        const response = await apiClient.get('dashboard/stats/');
        setDashboardStats(response.data);
      } catch (err) {
        logger.error('Error fetching dashboard stats:', err);
      } finally {
        setStatsLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

  return (
    <div className="dashboard-page-container">
      <div className="dashboard-header">
        <Title level={2} className="dashboard-title">欢迎来到智能办公桌面管理系统</Title>
        <Text type="secondary">这里是您的智能办公中心，高效管理您的日常工作。</Text>
      </div>

      {/* 通知 + 今日排班 + 待办行 */}
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

      {/* 待办事项 + 最新公告 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
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

      {/* 统计卡片行 */}
      <Row gutter={[16, 16]} className="stat-cards-row">
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

      {/* 本周概览 */}
      <div className="welcome-page-overview">
        <Title level={4} className="section-title">本周概览</Title>
        <Row gutter={[16, 16]}>
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

      <div className="welcome-page-footer">
        <Text type="secondary">如有任何疑问，请联系管理员。</Text>
      </div>
    </div>
  );
};

export default DashboardPage;
