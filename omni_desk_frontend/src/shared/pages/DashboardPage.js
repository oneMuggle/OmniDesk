import { useEffect, useState } from 'react';
import { Typography, Card, Row, Col, List, message, Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import apiClient from '../api/apiClient';

const { Title, Text } = Typography;


const DashboardPage = () => {
  const [loadingTrials, setLoadingTrials] = useState(true);
  const [loadingSchedules, setLoadingSchedules] = useState(true);
  const [loadingBookings, setLoadingBookings] = useState(true);
  const [weeklyTrials, setWeeklyTrials] = useState([]);
  const [weeklySchedules, setWeeklySchedules] = useState([]);
  const [weeklyBookings, setWeeklyBookings] = useState([]);

  useEffect(() => {
    const fetchWeeklyData = async () => {
      // Fetch weekly trials
      try {
        const trialsResponse = await apiClient.get('/events/trials/this-week/');
        setWeeklyTrials(trialsResponse.data);
      } catch (error) {
        message.error('获取本周试验日程失败！');
        console.error('Error fetching weekly trials:', error);
      } finally {
        setLoadingTrials(false);
      }

      // Fetch weekly schedules
      try {
        const today = new Date();
        const startOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1))); // Monday
        const endOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + 7)); // Sunday
        
        const schedulesResponse = await apiClient.get('/events/schedules/by-date-range/', {
          params: {
            start_date: startOfWeek.toISOString().split('T')[0],
            end_date: endOfWeek.toISOString().split('T')[0]
          }
        });
        setWeeklySchedules(schedulesResponse.data);
      } catch (error) {
        message.error('获取本周排班日程失败！');
        console.error('Error fetching weekly schedules:', error);
      } finally {
        setLoadingSchedules(false);
      }

      // Fetch weekly meeting room bookings
      try {
        const bookingsResponse = await apiClient.get('/meeting-rooms/meeting-room-bookings/this-week/');
        setWeeklyBookings(bookingsResponse.data);
      } catch (error) {
        message.error('获取本周会议室预约失败！');
        console.error('Error fetching weekly bookings:', error);
      } finally {
        setLoadingBookings(false);
      }
    };

    fetchWeeklyData();
  }, []);

  const antIcon = <LoadingOutlined className="welcome-page-loading-spinner" spin />;

  return (
    <div className="welcome-page-container">
      <Title level={2}>欢迎来到智能办公桌面管理系统！</Title>
      <Text>这里是您的智能办公中心，高效管理您的日常工作。</Text>

      <div className="welcome-page-overview">
        <Title level={3}>本周概览</Title>
        <Row gutter={[16, 16]}>
          {/* 本周试验日程 */}
          <Col xs={24} sm={24} md={8}>
            <Card title="本周试验日程" bordered={false}>
              {loadingTrials ? (
                <div className="welcome-page-loading-container">
                  <Spin indicator={antIcon} />
                </div>
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
                            <Text type="secondary">负责人: {item.responsible_persons.map(p => p.name).join(', ')}</Text>
                          </>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Col>

          {/* 本周排班日程 */}
          <Col xs={24} sm={24} md={8}>
            <Card title="本周排班日程" bordered={false}>
              {loadingSchedules ? (
                <div className="welcome-page-loading-container">
                  <Spin indicator={antIcon} />
                </div>
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

          {/* 本周会议室预约 */}
          <Col xs={24} sm={24} md={8}>
            <Card title="本周会议室预约" bordered={false}>
              {loadingBookings ? (
                <div className="welcome-page-loading-container">
                  <Spin indicator={antIcon} />
                </div>
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