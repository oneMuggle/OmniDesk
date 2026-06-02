import { useState, useEffect, useCallback } from 'react';
import { Card, Button, Table, Modal, Form, Input, InputNumber, Checkbox, Space, Typography, message, Select, Tabs, Tag } from 'antd';
import { CloudServerOutlined, AppstoreOutlined, ApiOutlined, DatabaseOutlined, CheckOutlined } from '@ant-design/icons';
import {
  getEndpoints,
  addEndpoint,
  updateEndpoint,
  deleteEndpoint,
  fetchEndpointModels,
  testEndpoint as apiTestEndpoint,
  getAppConfigs,
  addAppConfig,
  updateAppConfig,
  deleteAppConfig,
  getDifyApps,
  addDifyApp,
  updateDifyApp,
  deleteDifyApp,
  getRagflowConfigs,
  addRagflowConfig,
  updateRagflowConfig,
  deleteRagflowConfig,
} from '../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../shared/utils/logger';

const { Title } = Typography;

const AiAppManagementPage = () => {
  // ===== LLM 端点 & 应用配置 =====
  const [endpoints, setEndpoints] = useState([]);
  const [appConfigs, setAppConfigs] = useState([]);
  const [endpointModalVisible, setEndpointModalVisible] = useState(false);
  const [appConfigModalVisible, setAppConfigModalVisible] = useState(false);
  const [editingEndpoint, setEditingEndpoint] = useState(null);
  const [editingAppConfig, setEditingAppConfig] = useState(null);
  const [endpointForm] = Form.useForm();
  const [appConfigForm] = Form.useForm();
  const [modelOptions, setModelOptions] = useState([]);
  // 应用配置模态框中当前选中的端点 ID（用于联动获取模型列表）
  const [selectedEndpointId, setSelectedEndpointId] = useState(null);
  const [fetchingModels, setFetchingModels] = useState(false);
  // 端点测试状态：记录正在测试或测试结果的端点 ID
  const [testingEndpointId, setTestingEndpointId] = useState(null);
  const [endpointTestResult, setEndpointTestResult] = useState(null);

  // ===== Dify 应用 =====
  const [difyApps, setDifyApps] = useState([]);
  const [difyModalVisible, setDifyModalVisible] = useState(false);
  const [editingDifyApp, setEditingDifyApp] = useState(null);
  const [difyForm] = Form.useForm();

  // ===== Ragflow 配置 =====
  const [ragflowConfigs, setRagflowConfigs] = useState([]);
  const [ragflowModalVisible, setRagflowModalVisible] = useState(false);
  const [editingRagflowConfig, setEditingRagflowConfig] = useState(null);
  const [ragflowForm] = Form.useForm();

  // 加载 LLM 端点
  const loadEndpoints = useCallback(async () => {
    try {
      const response = await getEndpoints();
      setEndpoints(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载端点配置失败。');
      logger.error('加载端点配置失败:', error);
    }
  }, []);

  // 加载 LLM 应用配置
  const loadAppConfigs = useCallback(async () => {
    try {
      const response = await getAppConfigs();
      setAppConfigs(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载应用配置失败。');
      logger.error('加载应用配置失败:', error);
    }
  }, []);

  // 加载 Dify 应用
  const loadDifyApps = useCallback(async () => {
    try {
      const response = await getDifyApps();
      setDifyApps(response.data.results || response.data || []);
    } catch (error) {
      message.error('加载 Dify 应用失败。');
      logger.error('加载 Dify 应用失败:', error);
    }
  }, []);

  // 加载 Ragflow 配置
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

  // ===== LLM 端点管理 =====
  const handleAddEndpoint = () => {
    setEditingEndpoint(null);
    endpointForm.resetFields();
    endpointForm.setFieldsValue({ is_active: true, priority: 1, is_fallback: false });
    setEndpointModalVisible(true);
  };

  const handleEditEndpoint = (record) => {
    setEditingEndpoint(record);
    endpointForm.setFieldsValue({
      name: record.name,
      api_endpoint: record.api_endpoint,
      is_active: record.is_active,
      priority: record.priority || 1,
      is_fallback: record.is_fallback || false,
      model_capabilities: record.model_capabilities || [],
      cost_per_1k_tokens: record.cost_per_1k_tokens,
    });
    setEndpointModalVisible(true);
  };

  const handleDeleteEndpoint = async (id) => {
    try {
      await deleteEndpoint(id);
      message.success('端点删除成功。');
      loadEndpoints();
      loadAppConfigs();
    } catch (error) {
      message.error('删除端点失败。');
      logger.error('删除端点失败:', error);
    }
  };

  const handleSaveEndpoint = async (values) => {
    try {
      if (editingEndpoint) {
        await updateEndpoint(editingEndpoint.id, values);
        message.success('端点更新成功。');
      } else {
        await addEndpoint(values);
        message.success('端点添加成功。');
      }
      setEndpointModalVisible(false);
      loadEndpoints();
    } catch (error) {
      message.error(`保存端点失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存端点失败:', error);
    }
  };

  // 应用配置模态框中：选择端点后自动获取模型列表
  const handleEndpointChange = async (endpointId, preserveModelName = false) => {
    setSelectedEndpointId(endpointId);
    if (!preserveModelName) {
      appConfigForm.setFieldValue('model_name', undefined); // 清空已选模型
    }
    if (!endpointId) {
      setModelOptions([]);
      return;
    }
    setFetchingModels(true);
    try {
      const response = await fetchEndpointModels(endpointId);
      const models = response.data?.models || [];
      if (models.length > 0) {
        setModelOptions(models);
        message.success(`获取到 ${models.length} 个可用模型`);
      } else {
        message.warning('未获取到任何模型，请检查端点和密钥是否正确');
        setModelOptions([]);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.error || error.message || '获取模型列表失败';
      message.error(errorMsg);
      logger.error('获取模型列表失败:', error);
      setModelOptions([]);
    } finally {
      setFetchingModels(false);
    }
  };

  // 测试端点连通性
  const handleTestEndpoint = async (endpointId) => {
    setTestingEndpointId(endpointId);
    setEndpointTestResult(null);
    try {
      const response = await apiTestEndpoint(endpointId);
      const result = response.data;
      setEndpointTestResult({ id: endpointId, status: result.status, message: result.message });
      if (result.status === 'ok') {
        message.success(result.message);
      } else {
        message.warning(result.message);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.message || error.message || '测试请求失败';
      setEndpointTestResult({ id: endpointId, status: 'error', message: errorMsg });
      message.error(errorMsg);
      logger.error('测试端点失败:', error);
    } finally {
      setTestingEndpointId(null);
    }
  };

  const endpointColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: 'API 端点', dataIndex: 'api_endpoint', key: 'api_endpoint' },
    {
      title: '优先级', dataIndex: 'priority', key: 'priority',
      render: (val) => val ?? 1,
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (text) => (text ? <Tag color="green">激活</Tag> : <Tag color="default">未激活</Tag>),
    },
    {
      title: '备用', dataIndex: 'is_fallback', key: 'is_fallback',
      render: (text) => (text ? <Tag color="orange">备用</Tag> : <span style={{ color: '#999' }}>—</span>),
    },
    {
      title: '操作', key: 'action',
      render: (_, record) => {
        const isTesting = testingEndpointId === record.id;
        const testResult = endpointTestResult?.id === record.id ? endpointTestResult : null;
        return (
          <Space size="middle">
            <Button
              size="small"
              type="default"
              icon={isTesting ? undefined : <CheckOutlined />}
              loading={isTesting}
              onClick={() => handleTestEndpoint(record.id)}
            >
              测试
            </Button>
            {testResult && testResult.status === 'ok' && (
              <Tag color="green">正常</Tag>
            )}
            {testResult && testResult.status !== 'ok' && (
              <Tag color="red">{testResult.message?.slice(0, 20)}...</Tag>
            )}
            <Button type="link" onClick={() => handleEditEndpoint(record)}>编辑</Button>
            <Button type="link" danger onClick={() => handleDeleteEndpoint(record.id)}>删除</Button>
          </Space>
        );
      },
    },
  ];

  // ===== LLM 应用配置管理 =====
  const handleAddAppConfig = () => {
    setEditingAppConfig(null);
    appConfigForm.resetFields();
    appConfigForm.setFieldsValue({ is_active: true, temperature: 0.7, top_p: 0.9 });
    setModelOptions([]);
    setSelectedEndpointId(null);
    setFetchingModels(false);
    setAppConfigModalVisible(true);
  };

  const handleEditAppConfig = (record) => {
    setEditingAppConfig(record);
    appConfigForm.setFieldsValue({
      app_name: record.app_name,
      endpoint: record.endpoint,
      model_name: record.model_name,
      temperature: record.temperature,
      top_p: record.top_p,
      is_active: record.is_active,
    });
    // 预取当前关联端点的模型列表（编辑模式保留已选模型）
    const endpointId = record.endpoint?.id ?? record.endpoint;
    setSelectedEndpointId(endpointId);
    if (endpointId) {
      handleEndpointChange(endpointId, true);
    }
    setAppConfigModalVisible(true);
  };

  const handleDeleteAppConfig = async (id) => {
    try {
      await deleteAppConfig(id);
      message.success('应用配置删除成功。');
      loadAppConfigs();
    } catch (error) {
      message.error('删除应用配置失败。');
      logger.error('删除应用配置失败:', error);
    }
  };

  const handleSaveAppConfig = async (values) => {
    try {
      if (editingAppConfig) {
        await updateAppConfig(editingAppConfig.id, values);
        message.success('应用配置更新成功。');
      } else {
        await addAppConfig(values);
        message.success('应用配置添加成功。');
      }
      setAppConfigModalVisible(false);
      loadAppConfigs();
    } catch (error) {
      message.error(`保存应用配置失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存应用配置失败:', error);
    }
  };

  const appConfigColumns = [
    { title: '应用', dataIndex: 'app_name', key: 'app_name', render: (text) => {
      const map = { smart_assistant: '智能助手' };
      return map[text] || text;
    }},
    { title: '关联端点', dataIndex: 'endpoint_name', key: 'endpoint_name' },
    { title: '模型', dataIndex: 'model_name', key: 'model_name' },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (text) => (text ? <Tag color="green">激活</Tag> : <Tag color="default">未激活</Tag>),
    },
    {
      title: '操作', key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEditAppConfig(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDeleteAppConfig(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  // ===== Dify 应用管理 =====
  const handleAddDifyApp = () => {
    setEditingDifyApp(null);
    difyForm.resetFields();
    setDifyModalVisible(true);
  };

  const handleEditDifyApp = (record) => {
    setEditingDifyApp(record);
    difyForm.setFieldsValue({
      name: record.name,
      description: record.description,
      embed_url: record.embed_url,
      is_active: record.is_active,
    });
    setDifyModalVisible(true);
  };

  const handleDeleteDifyApp = async (id) => {
    try {
      await deleteDifyApp(id);
      message.success('Dify 应用删除成功。');
      loadDifyApps();
    } catch (error) {
      message.error('删除 Dify 应用失败。');
      logger.error('删除 Dify 应用失败:', error);
    }
  };

  const handleSaveDifyApp = async (values) => {
    try {
      if (editingDifyApp) {
        await updateDifyApp(editingDifyApp.id, values);
        message.success('Dify 应用更新成功。');
      } else {
        await addDifyApp(values);
        message.success('Dify 应用添加成功。');
      }
      setDifyModalVisible(false);
      loadDifyApps();
    } catch (error) {
      message.error(`保存 Dify 应用失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存 Dify 应用失败:', error);
    }
  };

  const difyColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '嵌入 URL', dataIndex: 'embed_url', key: 'embed_url', ellipsis: true, render: (url) => <a href={url} target="_blank" rel="noopener noreferrer">{url}</a> },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (text) => (text ? <Tag color="green">激活</Tag> : <Tag color="default">未激活</Tag>),
    },
    {
      title: '操作', key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEditDifyApp(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDeleteDifyApp(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  // ===== Ragflow 配置管理 =====
  const handleAddRagflowConfig = () => {
    setEditingRagflowConfig(null);
    ragflowForm.resetFields();
    ragflowForm.setFieldsValue({ is_active: true });
    setRagflowModalVisible(true);
  };

  const handleEditRagflowConfig = (record) => {
    setEditingRagflowConfig(record);
    ragflowForm.setFieldsValue({
      name: record.name,
      api_endpoint: record.api_endpoint,
      api_key: '',
      is_active: record.is_active,
    });
    setRagflowModalVisible(true);
  };

  const handleDeleteRagflowConfig = async (id) => {
    try {
      await deleteRagflowConfig(id);
      message.success('Ragflow 配置删除成功。');
      loadRagflowConfigs();
    } catch (error) {
      message.error('删除 Ragflow 配置失败。');
      logger.error('删除 Ragflow 配置失败:', error);
    }
  };

  const handleSaveRagflowConfig = async (values) => {
    try {
      // 编辑时如果 api_key 为空，不传该字段
      if (editingRagflowConfig && !values.api_key) {
        delete values.api_key;
      }
      if (editingRagflowConfig) {
        await updateRagflowConfig(editingRagflowConfig.id, values);
        message.success('Ragflow 配置更新成功。');
      } else {
        await addRagflowConfig(values);
        message.success('Ragflow 配置添加成功。');
      }
      setRagflowModalVisible(false);
      loadRagflowConfigs();
    } catch (error) {
      message.error(`保存 Ragflow 配置失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存 Ragflow 配置失败:', error);
    }
  };

  const ragflowColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: 'API 端点', dataIndex: 'api_endpoint', key: 'api_endpoint' },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (text) => (text ? <Tag color="green">激活</Tag> : <Tag color="default">未激活</Tag>),
    },
    {
      title: '操作', key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEditRagflowConfig(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDeleteRagflowConfig(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'endpoints',
      label: <span><CloudServerOutlined /> API 端点管理</span>,
      children: (
        <>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={handleAddEndpoint}>添加 API 端点</Button>
          </div>
          <Table columns={endpointColumns} dataSource={endpoints} rowKey="id" pagination={false} />
        </>
      ),
    },
    {
      key: 'appConfigs',
      label: <span><AppstoreOutlined /> LLM 应用配置</span>,
      children: (
        <>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={handleAddAppConfig}>添加应用配置</Button>
          </div>
          <Table columns={appConfigColumns} dataSource={appConfigs} rowKey="id" pagination={false} />
        </>
      ),
    },
    {
      key: 'dify',
      label: <span><ApiOutlined /> Dify 应用管理</span>,
      children: (
        <>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={handleAddDifyApp}>添加 Dify 应用</Button>
          </div>
          <Table columns={difyColumns} dataSource={difyApps} rowKey="id" pagination={false} />
        </>
      ),
    },
    {
      key: 'ragflow',
      label: <span><DatabaseOutlined /> Ragflow 配置管理</span>,
      children: (
        <>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={handleAddRagflowConfig}>添加 Ragflow 配置</Button>
          </div>
          <Table columns={ragflowColumns} dataSource={ragflowConfigs} rowKey="id" pagination={false} />
        </>
      ),
    },
  ];

  return (
    <Card title={<Title level={2}>AI 应用管理</Title>} style={{ margin: '20px' }}>
      <Tabs defaultActiveKey="endpoints" items={tabItems} />

      {/* 端点编辑模态框 */}
      <Modal
        title={editingEndpoint ? '编辑 API 端点' : '添加 API 端点'}
        open={endpointModalVisible}
        onCancel={() => { setEndpointModalVisible(false); setEditingEndpoint(null); endpointForm.resetFields(); }}
        footer={null}
        width={520}
      >
        <Form form={endpointForm} layout="vertical" onFinish={handleSaveEndpoint}
          initialValues={{ is_active: true, priority: 1, is_fallback: false }}>
          <Form.Item label="配置名称" name="name" rules={[{ required: true, message: '请输入配置名称!' }]}>
            <Input placeholder="如：gcli网关" />
          </Form.Item>
          <Form.Item label="API 端点" name="api_endpoint" rules={[
            { required: true, message: '请输入 API 端点!' },
            { type: 'url', message: '请输入有效的 URL 地址!' },
          ]}>
            <Input placeholder="https://gcli.ggchan.dev" />
          </Form.Item>
          <Form.Item label="API 密钥" name="api_key" rules={[{ required: !editingEndpoint, message: '请输入 API 密钥!' }]}>
            <Input.Password placeholder={editingEndpoint ? '留空则不修改' : ''} />
          </Form.Item>
          <Form.Item label="优先级" name="priority"
            tooltip="数字越小优先级越高，主端点设为 1，备用端点设为更大的数字">
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" valuePropName="checked">
            <Checkbox>设为激活（同时只允许一个端点激活）</Checkbox>
          </Form.Item>
          <Form.Item name="is_fallback" valuePropName="checked">
            <Checkbox>设为备用端点（主端点不可用时自动降级到此）</Checkbox>
          </Form.Item>
          <Form.Item label="每千 Token 费用（元）" name="cost_per_1k_tokens"
            tooltip="用于成本核算，可选">
            <InputNumber step={0.001} min={0} style={{ width: '100%' }} placeholder="如：0.01" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setEndpointModalVisible(false); setEditingEndpoint(null); endpointForm.resetFields(); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 应用配置编辑模态框 */}
      <Modal
        title={editingAppConfig ? '编辑应用配置' : '添加应用配置'}
        open={appConfigModalVisible}
        onCancel={() => { setAppConfigModalVisible(false); setEditingAppConfig(null); appConfigForm.resetFields(); setModelOptions([]); setSelectedEndpointId(null); setFetchingModels(false); }}
        footer={null}
      >
        <Form form={appConfigForm} layout="vertical" onFinish={handleSaveAppConfig}>
          <Form.Item label="应用" name="app_name" rules={[{ required: true, message: '请选择应用!' }]}>
            <Select options={[{ label: '智能助手', value: 'smart_assistant' }]} />
          </Form.Item>
          <Form.Item label="关联端点" name="endpoint" rules={[{ required: true, message: '请选择 API 端点!' }]}>
            <Select
              options={endpoints.filter(e => e.is_active).map(e => ({ label: `${e.name} (${e.api_endpoint})`, value: e.id }))}
              placeholder="请选择已配置的 API 端点"
              onChange={handleEndpointChange}
            />
          </Form.Item>
          <Form.Item label="模型名称" name="model_name" rules={[{ required: true, message: '请输入或选择模型名称!' }]}>
            <Select
              showSearch
              placeholder={fetchingModels ? '正在获取模型列表...' : '选择端点后自动获取模型列表'}
              loading={fetchingModels}
              options={modelOptions.map(m => ({ label: m, value: m }))}
              notFoundContent={fetchingModels ? '加载中...' : (selectedEndpointId ? '该端点无可用模型' : '请先选择关联端点')}
              allowClear
            />
          </Form.Item>
          <Form.Item label="Temperature" name="temperature">
            <InputNumber step={0.1} min={0} max={2} />
          </Form.Item>
          <Form.Item label="Top P" name="top_p">
            <InputNumber step={0.1} min={0} max={1} />
          </Form.Item>
          <Form.Item name="is_active" valuePropName="checked">
            <Checkbox>设为激活（同一应用同时只允许一个配置激活）</Checkbox>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setAppConfigModalVisible(false); setEditingAppConfig(null); appConfigForm.resetFields(); setModelOptions([]); setSelectedEndpointId(null); setFetchingModels(false); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Dify 应用编辑模态框 */}
      <Modal
        title={editingDifyApp ? '编辑 Dify 应用' : '添加 Dify 应用'}
        open={difyModalVisible}
        onCancel={() => { setDifyModalVisible(false); setEditingDifyApp(null); difyForm.resetFields(); }}
        footer={null}
      >
        <Form form={difyForm} layout="vertical" onFinish={handleSaveDifyApp}>
          <Form.Item label="应用名称" name="name" rules={[{ required: true, message: '请输入应用名称!' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item label="嵌入 URL" name="embed_url" rules={[
            { required: true, message: '请输入嵌入 URL!' },
            { type: 'url', message: '请输入有效的 URL 地址!' },
          ]}>
            <Input />
          </Form.Item>
          <Form.Item name="is_active" valuePropName="checked">
            <Checkbox>设为激活</Checkbox>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setDifyModalVisible(false); setEditingDifyApp(null); difyForm.resetFields(); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Ragflow 配置编辑模态框 */}
      <Modal
        title={editingRagflowConfig ? '编辑 Ragflow 配置' : '添加 Ragflow 配置'}
        open={ragflowModalVisible}
        onCancel={() => { setRagflowModalVisible(false); setEditingRagflowConfig(null); ragflowForm.resetFields(); }}
        footer={null}
      >
        <Form form={ragflowForm} layout="vertical" onFinish={handleSaveRagflowConfig}>
          <Form.Item label="配置名称" name="name" rules={[{ required: true, message: '请输入配置名称!' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="API 端点" name="api_endpoint" rules={[
            { required: true, message: '请输入 API 端点!' },
            { type: 'url', message: '请输入有效的 URL 地址!' },
          ]}>
            <Input />
          </Form.Item>
          <Form.Item label="API 密钥" name="api_key" rules={[{ required: !editingRagflowConfig, message: '请输入 API 密钥!' }]}>
            <Input.Password placeholder={editingRagflowConfig ? '留空则不修改' : ''} />
          </Form.Item>
          <Form.Item name="is_active" valuePropName="checked">
            <Checkbox>设为激活</Checkbox>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setRagflowModalVisible(false); setEditingRagflowConfig(null); ragflowForm.resetFields(); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default AiAppManagementPage;
