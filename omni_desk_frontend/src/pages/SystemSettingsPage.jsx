import React, { useState, useEffect } from 'react';
import { getOllamaConfigs, addOllamaConfig, updateOllamaConfig, deleteOllamaConfig, getOllamaModelsFromEndpoint } from '../api/ollama';
import { Card, Button, Table, Modal, Form, Input, InputNumber, Checkbox, Select, Space, Typography, message } from 'antd';
import apiClient from '../api/apiClient'; // 导入 apiClient

const { Title } = Typography;
const { Option } = Select;

const SystemSettingsPage = () => {
  const [configs, setConfigs] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [form] = Form.useForm();

  // Ragflow 相关的状态
  const [ragflowConfigs, setRagflowConfigs] = useState([]);
  const [selectedRagflowConfig, setSelectedRagflowConfig] = useState(null);
  const [isRagflowModalVisible, setIsRagflowModalVisible] = useState(false); // 新增状态
  const [ragflowForm] = Form.useForm(); // 为 Ragflow 配置管理创建新的 Form 实例

  const loadConfigs = React.useCallback(async () => {
    try {
      const response = await getOllamaConfigs();
      setConfigs(response.data.results || []);
    } catch (error) {
      message.error('加载配置失败。');
      console.error("加载 Ollama 配置失败:", error);
    }
  }, []);

  useEffect(() => {
    loadConfigs();
    // 加载 Ragflow 配置
    const fetchRagflowConfigs = async () => {
      try {
        const response = await apiClient.get('/ragflow-service/configs/');
        setRagflowConfigs(response.data.results || []);
      } catch (error) {
        message.error('加载 Ragflow 配置失败。');
        console.error('Error fetching Ragflow configs:', error);
      }
    };
    fetchRagflowConfigs();
  }, [loadConfigs]);

  const handleAddNew = () => {
    setEditingConfig({
      alias: '',
      api_endpoint: '',
      model: '',
      temperature: 0.8,
      top_p: 0.9,
      is_default: false,
    });
    setAvailableModels([]); // Clear available models when adding new config
    setIsModalVisible(true);
    form.resetFields();
  };

  const handleEdit = (config) => {
    setEditingConfig({ ...config });
    form.setFieldsValue({ ...config });
    setIsModalVisible(true);
    // Fetch models if api_endpoint is available for the config being edited
    if (config.api_endpoint) {
      fetchModelsForEditing(config.api_endpoint);
    } else {
      setAvailableModels([]);
    }
  };

  const fetchModelsForEditing = async (apiEndpoint) => {
    try {
      const response = await getOllamaModelsFromEndpoint(apiEndpoint);
      const models = response.data.map(model => model.id);
      setAvailableModels(models);
    } catch (error) {
      message.error('获取模型列表失败，请检查 API 地址是否正确。');
      console.error("Failed to fetch models:", error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteOllamaConfig(id);
      message.success('配置删除成功。');
      loadConfigs();
    } catch (error) {
      message.error('删除配置失败。');
      console.error("删除 Ollama 配置失败:", error);
    }
  };

  const handleSave = async (values) => {
    const payload = {
      ...values,
      is_default: values.is_default || false,
      temperature: values.temperature === undefined ? null : values.temperature,
      top_p: values.top_p === undefined ? null : values.top_p,
    };

    try {
      if (editingConfig.id) {
        await updateOllamaConfig(editingConfig.id, payload);
        message.success('配置更新成功。');
      } else {
        const aliasExists = configs.some(config => config.alias === payload.alias);
        if (aliasExists) {
          message.error("别名已存在，请选择一个不同的别名。");
          return;
        }
        await addOllamaConfig(payload);
        message.success('配置添加成功。');
      }
      setIsModalVisible(false);
      loadConfigs();
    } catch (error) {
      message.error('保存配置失败。');
      console.error("保存 Ollama 配置失败:", error);
    }
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingConfig(null);
    setAvailableModels([]);
    form.resetFields();
  };

  const handleFetchModels = async () => {
    const apiEndpoint = form.getFieldValue('api_endpoint');
    if (apiEndpoint) {
      try {
        const response = await getOllamaModelsFromEndpoint(apiEndpoint);
        const models = response.data.map(model => model.id);
        setAvailableModels(models);
        if (models.length > 0 && !form.getFieldValue('model')) {
          form.setFieldsValue({ model: models[0] });
        }
        message.success('模型列表获取成功。');
      } catch (error) {
        message.error('获取模型列表失败，请检查 API 地址是否正确。');
        console.error("Failed to fetch models:", error);
      }
    } else {
      message.warning('请输入 API 地址。');
    }
  };

  const columns = [
    {
      title: '别名',
      dataIndex: 'alias',
      key: 'alias',
    },
    {
      title: 'API 地址',
      dataIndex: 'api_endpoint',
      key: 'api_endpoint',
    },
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
    },
    {
      title: '默认',
      dataIndex: 'is_default',
      key: 'is_default',
      render: (text) => (text ? '是' : '否'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  const handleAddRagflowConfig = () => {
    setSelectedRagflowConfig(null);
    ragflowForm.resetFields();
    ragflowForm.setFieldsValue({ is_active: true });
    setIsRagflowModalVisible(true); // 显示 Modal
  };

  const handleEditRagflowConfig = (config) => {
    setSelectedRagflowConfig(config);
    ragflowForm.setFieldsValue(config);
  };

  const handleDeleteRagflowConfig = async (id) => {
    try {
      await apiClient.delete(`/ragflow-service/configs/${id}/`);
      message.success('Ragflow 配置删除成功。');
      const response = await apiClient.get('/ragflow-service/configs/');
      setRagflowConfigs(response.data.results || []);
      setSelectedRagflowConfig(null);
      ragflowForm.resetFields();
      ragflowForm.setFieldsValue({ is_active: true });
    } catch (error) {
      message.error('删除 Ragflow 配置失败。');
      console.error('删除 Ragflow 配置失败:', error);
    }
  };

  const handleSaveRagflowConfig = async (values) => {
    try {
      if (selectedRagflowConfig) {
        await apiClient.put(`/ragflow-service/configs/${selectedRagflowConfig.id}/`, values);
        message.success('Ragflow 配置更新成功。');
      } else {
        await apiClient.post('/ragflow-service/configs/', values);
        message.success('Ragflow 配置新增成功。');
      }
      const response = await apiClient.get('/ragflow-service/configs/');
      setRagflowConfigs(response.data.results || []);
      setSelectedRagflowConfig(null);
      ragflowForm.resetFields();
      ragflowForm.setFieldsValue({ is_active: true });
    } catch (error) {
      message.error(`保存 Ragflow 配置失败: ${error.response?.data?.detail || error.message}`);
      console.error('保存 Ragflow 配置失败:', error);
    }
  };

  const ragflowColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'API 端点',
      dataIndex: 'api_endpoint',
      key: 'api_endpoint',
    },
    {
      title: '是否激活',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (text) => (text ? '是' : '否'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEditRagflowConfig(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDeleteRagflowConfig(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card title={<Title level={2}>Ollama 配置</Title>} style={{ margin: '20px' }}>
        <div style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={handleAddNew}>
            添加新的配置
          </Button>
        </div>
        <Table columns={columns} dataSource={configs} rowKey="id" pagination={false} />

        {isModalVisible && (
          <Modal
            title={editingConfig && editingConfig.id ? '编辑配置' : '添加配置'}
            visible={isModalVisible}
            onCancel={handleCancel}
            footer={null}
          >
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
              initialValues={editingConfig}
            >
              <Form.Item
                label="别名"
                name="alias"
                rules={[{ required: true, message: '请输入别名!' }]}
              >
                <Input />
              </Form.Item>
              <Form.Item
                label="API 地址"
                name="api_endpoint"
                rules={[{ required: true, message: '请输入 API 地址!' }, { type: 'url', message: '请输入有效的 URL 地址!' }]}
              >
                <Input
                  addonAfter={
                    <Button type="link" onClick={handleFetchModels} style={{ padding: 0 }}>
                      获取模型
                    </Button>
                  }
                />
              </Form.Item>
              <Form.Item
                label="模型"
                name="model"
                rules={[{ required: true, message: '请选择一个模型!' }]}
              >
                <Select placeholder="请选择模型">
                  {availableModels.map(model => (
                    <Option key={model} value={model}>{model}</Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                label="Temperature"
                name="temperature"
              >
                <InputNumber step={0.1} min={0} max={1} />
              </Form.Item>
              <Form.Item
                label="Top P"
                name="top_p"
              >
                <InputNumber step={0.1} min={0} max={1} />
              </Form.Item>
              <Form.Item
                name="is_default"
                valuePropName="checked"
              >
                <Checkbox>设为默认</Checkbox>
              </Form.Item>
              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit">
                    保存
                  </Button>
                  <Button onClick={handleCancel}>
                    取消
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Modal>
        )}
      </Card>

      <Card title={<Title level={2}>Ragflow 配置</Title>} style={{ margin: '20px' }}>
        <div style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={handleAddRagflowConfig}>
            添加新的 Ragflow 配置
          </Button>
        </div>
        <Table columns={ragflowColumns} dataSource={ragflowConfigs} rowKey="id" pagination={false} />

        {isRagflowModalVisible && ( // 使用新的状态控制 Modal 的显示
          <Modal
            title={selectedRagflowConfig ? '编辑 Ragflow 配置' : '添加 Ragflow 配置'}
            visible={isRagflowModalVisible}
            onCancel={() => {
              setSelectedRagflowConfig(null);
              ragflowForm.resetFields();
              ragflowForm.setFieldsValue({ is_active: true });
              setIsRagflowModalVisible(false); // 关闭 Modal
            }}
            footer={null}
          >
            <Form
              form={ragflowForm}
              layout="vertical"
              onFinish={handleSaveRagflowConfig}
              initialValues={selectedRagflowConfig || { is_active: true }}
            >
              <Form.Item
                label="配置名称"
                name="name"
                rules={[{ required: true, message: '请输入配置名称!' }]}
              >
                <Input />
              </Form.Item>
              <Form.Item
                label="API 端点"
                name="api_endpoint"
                rules={[{ required: true, message: '请输入 API 端点!' }]}
              >
                <Input />
              </Form.Item>
              <Form.Item
                label="API 密钥"
                name="api_key"
              >
                <Input />
              </Form.Item>
              <Form.Item
                name="is_active"
                valuePropName="checked"
              >
                <Checkbox>是否激活</Checkbox>
              </Form.Item>
              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit">
                    {selectedRagflowConfig ? '更新配置' : '新增配置'}
                  </Button>
                  <Button onClick={() => {
                    setSelectedRagflowConfig(null);
                    ragflowForm.resetFields();
                    ragflowForm.setFieldsValue({ is_active: true });
                  }}>
                    取消
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Modal>
        )}
      </Card>
    </>
  );
};

export default SystemSettingsPage;