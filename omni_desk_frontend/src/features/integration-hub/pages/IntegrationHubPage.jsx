import { useState, useEffect } from 'react';
import { Typography, Spin, Row, Col, message } from 'antd';
import { fetchIntegrations } from '../api/integrationApi';
import IntegrationCard from '../components/IntegrationCard';
import IntegrationIframeViewer from '../components/IntegrationIframeViewer';

const { Title } = Typography;

const IntegrationHubPage = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [currentService, setCurrentService] = useState(null);

  useEffect(() => { loadServices(); }, []);

  const loadServices = async () => {
    try {
      setLoading(true);
      const data = await fetchIntegrations();
      setServices(data);
    } catch {
      message.error('加载集成服务失败');
    } finally {
      setLoading(false);
    }
  };

  const handleView = (service) => {
    setCurrentService(service);
    setViewerOpen(true);
  };

  const handleExecute = async (service) => {
    message.info(`${service.name} 调用面板（开发中）`);
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />;
  }

  return (
    <div style={{ padding: '24px' }}>
      <Title level={4}>集成中心</Title>
      {services.length === 0 ? (
        <Typography.Text type="secondary">暂无集成服务，请在管理中心添加</Typography.Text>
      ) : (
        <Row gutter={[24, 24]}>
          {services.map((service) => (
            <Col xs={24} sm={12} md={8} lg={6} key={service.id}>
              <IntegrationCard
                service={service}
                onView={handleView}
                onExecute={handleExecute}
              />
            </Col>
          ))}
        </Row>
      )}
      <IntegrationIframeViewer
        service={currentService}
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
      />
    </div>
  );
};

export default IntegrationHubPage;
