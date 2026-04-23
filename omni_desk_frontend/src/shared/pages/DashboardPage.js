import { useEffect, useState } from 'react';
import { Typography, Card, Row, Col, List, Empty } from 'antd';
import apiClient from '../api/apiClient';
import SkeletonList from '../components/SkeletonList';

const { Title, Text } = Typography;

const DashboardPage = () => {
  const [loading, setLoading] = useState(true);
  const [weeklyTrials, setWeeklyTrials] = useState([]);
  const [weeklySchedules, setWeeklySchedules] = useState([]);
  const [weeklyBookings, setWeeklyBookings] = useState([]);
  const [errors, setErrors] = useState({});

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
        console.error('Error fetching weekly trials:', trialsResult.reason);
        setErrors(prev => ({ ...prev, trials: true }));
      }

      if (schedulesResult.status === 'fulfilled') {
        setWeeklySchedules(schedulesResult.value.data);
      } else {
        console.error('Error fetching weekly schedules:', schedulesResult.reason);
        setErrors(prev => ({ ...prev, schedules: true }));
      }

      if (bookingsResult.status === 'fulfilled') {
        setWeeklyBookings(bookingsResult.value.data);
      } else {
        console.error('Error fetching weekly bookings:', bookingsResult.reason);
        setErrors(prev => ({ ...prev, bookings: true }));
      }

      setLoading(false);
    };

    fetchWeeklyData();
  }, []);

  return (
    <div className="welcome-page-container">
      <Title level={2}>欢迎来到智能办公桌面管理系统！</Title>
      <Text>这里是您的智能办公中心，高效管理您的日常工作。</Text>

      <div className="welcome-page-overview">
        <Title level={3}>本周概览</Title>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={24} md={8}>
            <Card title="本周试验日程" variant="borderless">
              {loading ? (
                <SkeletonList count={3} />
              ) : errors.trials ? (
                <Empty description="加载失败" />
              ) : (
                <List
                  itemLayout="horizontal"
                  dataSource={weeklyTrials}
                  locale={{ emptyText: '本周暂无试验日程' }}
                  renderItem={item => (
                    <List.Item>
                      <List.Item.Meta
                        title={<Text>{item.title}</Text>}
                        description={
                          <>
                            <Text type="secondary">{item.start_date ? new Date(item.start_date).toLocaleString() : 'N/A'} - {item.end_date ? new Date(item.end_date).toLocaleString() : 'N/A'}</Text><br />
                            <Text type="secondary">负责人: {item.responsible_persons?.map(p => p.name).join(', ') || 'N/A'}</Text>
                          </>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Col>

          <Col xs={24} sm={24} md={8}>
            <Card title="本周排班日程" variant="borderless">
              {loading ? (
                <SkeletonList count={3} />
              ) : errors.schedules ? (
                <Empty description="加载失败" />
              ) : (
                <List
                  itemLayout="horizontal"
                  dataSource={weeklySchedules}
                  locale={{ emptyText: '本周暂无排班日程' }}
                  renderItem={item => (
                    <List.Item>
                      <List.Item.Meta
                        title={<Text>{item.duty_date}</Text>}
                        description={
                          <>
                            <Text type="secondary">值班人员: {item.duty_person ? item.duty_person.name : 'N/A'}</Text><br />
                            <Text type="secondary">值班领导: {item.duty_leader ? item.duty_leader.name : 'N/A'}</Text>
                          </>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Col>

          <Col xs={24} sm={24} md={8}>
            <Card title="本周会议室预约" variant="borderless">
              {loading ? (
                <SkeletonList count={3} />
              ) : errors.bookings ? (
                <Empty description="加载失败" />
              ) : (
                <List
                  itemLayout="horizontal"
                  dataSource={weeklyBookings}
                  locale={{ emptyText: '本周暂无会议室预约' }}
                  renderItem={item => (
                    <List.Item>
                      <List.Item.Meta
                        title={<Text>{item.title}</Text>}
                        description={
                          <>
                            <Text type="secondary">{new Date(item.start_time).toLocaleString()} - {new Date(item.end_time).toLocaleString()}</Text><br />
                            <Text type="secondary">会议室: {item.meeting_room_name}</Text><br />
                            <Text type="secondary">预约人: {item.user ? item.user.username : 'N/A'}</Text>
                          </>
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
        <Text type="secondary">
          如有任何疑问，请联系管理员。
        </Text>
      </div>
    </div>
  );
};

export default DashboardPage;