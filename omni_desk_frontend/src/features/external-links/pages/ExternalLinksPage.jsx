import { useState, useEffect } from 'react';
import { Card, Typography, Spin, message, Row, Col, Tag } from 'antd';
import {
  LinkOutlined,
  CodeOutlined,
  ToolOutlined,
  FileTextOutlined,
  CloudOutlined,
} from '@ant-design/icons';
import { fetchExternalLinks, getSsoToken } from '../api/externalLinksApi';

const { Title, Text } = Typography;

// 分类图标映射
const CATEGORY_ICONS = {
  '开发工具': CodeOutlined,
  'CI/CD': ToolOutlined,
  '文档管理': FileTextOutlined,
  '云服务': CloudOutlined,
};
const DEFAULT_ICON = LinkOutlined;

const ExternalLinksPage = () => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadLinks();
  }, []);

  const loadLinks = async () => {
    try {
      setLoading(true);
      const data = await fetchExternalLinks();
      setGroups(data);
    } catch {
      message.error('加载外链列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleLinkClick = async (link) => {
    if (link.sso_enabled) {
      try {
        const result = await getSsoToken(link.id);
        window.open(result.redirect_url, '_blank');
      } catch {
        message.error('获取 SSO 令牌失败');
      }
    } else {
      window.open(link.url, '_blank');
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />;
  }

  if (groups.length === 0) {
    return (
      <div style={{ padding: '24px' }}>
        <Title level={4}>快捷外链</Title>
        <Text type="secondary">暂无外链，请在管理中心添加</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Title level={4}>快捷外链</Title>
      <Row gutter={[24, 24]}>
        {groups.map((group) => (
          <Col xs={24} sm={24} md={12} lg={8} key={group.category}>
            <Card
              title={group.category}
              size="small"
              style={{ height: '100%' }}
            >
              {group.links.map((link) => {
                const IconComponent = CATEGORY_ICONS[link.category] || DEFAULT_ICON;
                return (
                  <div
                    key={link.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '8px 0',
                      cursor: 'pointer',
                      borderBottom: '1px solid #f0f0f0',
                    }}
                    onClick={() => handleLinkClick(link)}
                  >
                    <IconComponent style={{ marginRight: 8, color: '#1890ff' }} />
                    <Text strong>{link.name}</Text>
                    {link.sso_enabled && (
                      <Tag color="green" style={{ marginLeft: 8 }}>
                        SSO
                      </Tag>
                    )}
                  </div>
                );
              })}
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
};

export default ExternalLinksPage;
