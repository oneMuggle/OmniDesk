import { useState, useEffect, useCallback } from 'react';
import { Card, Typography, Tabs, message } from 'antd';
import { CloudServerOutlined, AppstoreOutlined, ApiOutlined, DatabaseOutlined } from '@ant-design/icons';
import {
  getEndpoints,
  getAppConfigs,
  getDifyApps,
  getRagflowConfigs,
} from '../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../shared/utils/logger';
import EndpointManagement from '../components/ai-apps/EndpointManagement';
import AppConfigManagement from '../components/ai-apps/AppConfigManagement';
import DifyAppManagement from '../components/ai-apps/DifyAppManagement';
import RagflowConfigManagement from '../components/ai-apps/RagflowConfigManagement';

const { Title } = Typography;

const AiAppManagementPage = () => {
  const [endpoints, setEndpoints] = useState([]);
  const [appConfigs, setAppConfigs] = useState([]);
  const [difyApps, setDifyApps] = useState([]);
  const [ragflowConfigs, setRagflowConfigs] = useState([]);

  const loadEndpoints = useCallback(async () => {
    try {
      const response = await getEndpoints();
      setEndpoints(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载端点配置失败。');
      logger.error('加载端点配置失败:', error);
    }
  }, []);

  const loadAppConfigs = useCallback(async () => {
    try {
      const response = await getAppConfigs();
      setAppConfigs(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载应用配置失败。');
      logger.error('加载应用配置失败:', error);
    }
  }, []);

  const loadDifyApps = useCallback(async () => {
    try {
      const response = await getDifyApps();
      setDifyApps(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载 Dify 应用失败。');
      logger.error('加载 Dify 应用失败:', error);
    }
  }, []);

  const loadRagflowConfigs = useCallback(async () => {
    try {
      const response = await getRagflowConfigs();
      setRagflowConfigs(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载 Ragflow 配置失败。');
      logger.error('加载 Ragflow 配置失败:', error);
    }
  }, []);

  useEffect(() => {
    loadEndpoints();
    loadAppConfigs();
    loadDifyApps();
    loadRagflowConfigs();
  }, [loadEndpoints, loadAppConfigs, loadDifyApps, loadRagflowConfigs]);

  const tabItems = [
    {
      key: 'endpoints',
      label: <span><CloudServerOutlined /> API 端点管理</span>,
      children: (
        <EndpointManagement
          endpoints={endpoints}
          loadEndpoints={loadEndpoints}
          loadAppConfigs={loadAppConfigs}
        />
      ),
    },
    {
      key: 'appConfigs',
      label: <span><AppstoreOutlined /> LLM 应用配置</span>,
      children: (
        <AppConfigManagement
          appConfigs={appConfigs}
          endpoints={endpoints}
          loadAppConfigs={loadAppConfigs}
        />
      ),
    },
    {
      key: 'dify',
      label: <span><ApiOutlined /> Dify 应用管理</span>,
      children: <DifyAppManagement difyApps={difyApps} loadDifyApps={loadDifyApps} />,
    },
    {
      key: 'ragflow',
      label: <span><DatabaseOutlined /> Ragflow 配置管理</span>,
      children: (
        <RagflowConfigManagement
          ragflowConfigs={ragflowConfigs}
          loadRagflowConfigs={loadRagflowConfigs}
        />
      ),
    },
  ];

  return (
    <Card title={<Title level={2}>AI 应用管理</Title>} style={{ margin: '20px' }}>
      <Tabs defaultActiveKey="endpoints" items={tabItems} />
    </Card>
  );
};

export default AiAppManagementPage;
