import React from 'react';
import { Typography, Card, Space, Row, Col } from 'antd';
import { UserOutlined, CalendarOutlined, BookOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const WelcomePage = () => {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>欢迎来到日历管理系统！</Title>
      <Text>这里是您的个性化中心，您可以轻松管理日程、查看活动、学习知识等。</Text>

      <div style={{ marginTop: '48px' }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={8}>
            <Card
              hoverable
              actions={[
                <Space>
                  <UserOutlined />
                  <Text>个人信息</Text>
                </Space>,
              ]}
            >
              <Card.Meta
                title="个人中心"
                description="管理您的个人资料和设置。"
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card
              hoverable
              actions={[
                <Space>
                  <CalendarOutlined />
                  <Text>我的日程</Text>
                </Space>,
              ]}
            >
              <Card.Meta
                title="日历视图"
                description="查看和安排您的活动和事件。"
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card
              hoverable
              actions={[
                <Space>
                  <BookOutlined />
                  <Text>知识库</Text>
                </Space>,
              ]}
            >
              <Card.Meta
                title="学习资料"
                description="探索丰富的书籍和文档资源。"
              />
            </Card>
          </Col>
        </Row>
      </div>

      <div style={{ marginTop: '48px', textAlign: 'center' }}>
        <Text type="secondary">
          如有任何疑问，请联系管理员。
        </Text>
      </div>
    </div>
  );
};

export default WelcomePage;