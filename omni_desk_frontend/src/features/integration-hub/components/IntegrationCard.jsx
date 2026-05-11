import { Card, Tag, Typography, Button } from 'antd';
import { RocketOutlined, ApiOutlined } from '@ant-design/icons';

const { Text } = Typography;

const TYPE_CONFIG = {
  iframe: { color: 'blue', icon: <RocketOutlined />, label: 'iframe 嵌入' },
  api: { color: 'green', icon: <ApiOutlined />, label: 'API 代理' },
  widget: { color: 'orange', icon: <RocketOutlined />, label: '组件嵌入' },
};

const IntegrationCard = ({ service, onView, onExecute }) => {
  const config = TYPE_CONFIG[service.integration_type] || TYPE_CONFIG.iframe;

  return (
    <Card
      hoverable
      title={
        <span>
          {config.icon} {service.name}
        </span>
      }
      extra={<Tag color={config.color}>{config.label}</Tag>}
      style={{ height: '100%' }}
    >
      <Text type="secondary">{service.description || '暂无描述'}</Text>
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        {service.integration_type === 'iframe' && (
          <Button size="small" onClick={() => onView(service)}>
            打开
          </Button>
        )}
        {service.integration_type === 'api' && (
          <Button size="small" type="primary" onClick={() => onExecute(service)}>
            调用
          </Button>
        )}
      </div>
    </Card>
  );
};

export default IntegrationCard;
