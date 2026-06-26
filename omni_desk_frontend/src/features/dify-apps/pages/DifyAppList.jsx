import './DifyApps.css';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Tag, Spin } from 'antd';
import { RobotOutlined, MessageOutlined, FileSearchOutlined, SafetyOutlined } from '@ant-design/icons';
import apiClient from '../../../shared/api/apiClient';
import { logger } from '../../../shared/utils/logger';

const { Title, Paragraph, Text } = Typography;

const DifyAppList = () => {
    const [difyApps, setDifyApps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchDifyApps = async () => {
            try {
                const response = await apiClient.get('/api/dify-apps/');
                setDifyApps(response.data.results || []);
            } catch (err) {
                setError('Failed to fetch Dify applications.');
                logger.error('Error fetching Dify apps:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchDifyApps();
    }, []);

    const handleAppClick = (appId) => {
        navigate(`/dify-apps/${appId}`);
    };

    const getAppIcon = (appName) => {
        const name = appName.toLowerCase();
        if (name.includes('客服') || name.includes('智能问答')) {
            return <MessageOutlined style={{ fontSize: '48px', color: '#1890ff' }} />;
        } else if (name.includes('合同') || name.includes('审查')) {
            return <FileSearchOutlined style={{ fontSize: '48px', color: '#52c41a' }} />;
        } else if (name.includes('员工') || name.includes('手册')) {
            return <SafetyOutlined style={{ fontSize: '48px', color: '#722ed1' }} />;
        } else {
            return <RobotOutlined style={{ fontSize: '48px', color: '#fa8c16' }} />;
        }
    };

    const getAppTag = (appName) => {
        const name = appName.toLowerCase();
        if (name.includes('客服')) {
            return <Tag color="blue">客户服务</Tag>;
        } else if (name.includes('合同')) {
            return <Tag color="green">法务工具</Tag>;
        } else if (name.includes('员工')) {
            return <Tag color="purple">人力资源</Tag>;
        }
        return <Tag color="orange">AI 助手</Tag>;
    };

    if (loading) {
        return (
            <div className="dify-app-list-container">
                <div style={{ textAlign: 'center', padding: '100px 0' }}>
                    <Spin size="large" tip="加载应用中..." />
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="dify-app-list-container">
                <div className="error-message" style={{ textAlign: 'center', padding: '50px', color: '#ff4d4f' }}>
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div className="dify-app-list-container">
            <div className="page-header">
                <Title level={2}>Dify 智能应用</Title>
                <Paragraph type="secondary">
                    基于 Dify 平台构建的企业级 AI 应用，提供智能问答、文档分析等能力
                </Paragraph>
            </div>

            <Row gutter={[24, 24]}>
                {difyApps.length === 0 ? (
                    <Col span={24}>
                        <div style={{ textAlign: 'center', padding: '50px', color: '#999' }}>
                            暂无可用的 Dify 应用
                        </div>
                    </Col>
                ) : (
                    difyApps.map(app => (
                        <Col key={app.id} xs={24} sm={12} lg={8} xl={6}>
                            <Card
                                hoverable
                                className="dify-app-card"
                                onClick={() => handleAppClick(app.id)}
                            >
                                <div className="card-icon">
                                    {getAppIcon(app.name)}
                                </div>
                                <div className="card-content">
                                    <div className="card-header">
                                        <Title level={4} className="card-title">{app.name}</Title>
                                        {getAppTag(app.name)}
                                    </div>
                                    <Paragraph className="card-description" ellipsis={{ rows: 3 }}>
                                        {app.description}
                                    </Paragraph>
                                    <div className="card-footer">
                                        <Text type="secondary" style={{ fontSize: '12px' }}>
                                            点击开始使用 →
                                        </Text>
                                    </div>
                                </div>
                            </Card>
                        </Col>
                    ))
                )}
            </Row>
        </div>
    );
};

export default DifyAppList;
