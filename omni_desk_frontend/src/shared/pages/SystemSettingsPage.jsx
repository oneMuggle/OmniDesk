import React, { useState, useEffect } from 'react';
import { getOllamaConfigs, addOllamaConfig, updateOllamaConfig, deleteOllamaConfig, getOllamaModelsFromEndpoint } from '../api/ollama';
import { Card, Button, Table, Modal, Form, Input, InputNumber, Checkbox, Select, Space, Typography, message } from 'antd';
import { logger } from '../utils/logger';

const { Title } = Typography;
const { Option } = Select;

const SystemSettingsPage = () => {
  const [configs, setConfigs] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [form] = Form.useForm();

  const loadConfigs = React.useCallback(async () => {
    try {
      const response = await getOllamaConfigs();
      setConfigs(response.data.results || []);
    } catch (error) {
      message.error('加载配置失败。');
      logger.error("加载 Ollama 配置失败:", error);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadConfigs();
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
    setAvailableModels([]);
    setIsModalVisible(true);
    form.resetFields();
  };

  const handleEdit = (config) => {
    setEditingConfig({ ...config });
    form.setFieldsValue({ ...config });
    setIsModalVisible(true);
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
      logger.error("Failed to fetch models:", error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteOllamaConfig(id);
      message.success('配置删除成功。');
      loadConfigs();
    } catch (error) {
      message.error('删除配置失败。');
      logger.error("删除 Ollama 配置失败:", error);
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
      logger.error("保存 Ollama 配置失败:", error);
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
        logger.error("Failed to fetch models:", error);
      }
    } else {
      message.warning('请输入 API 地址。');
    }
  };

  const columns = [
    { title: '别名', dataIndex: 'alias', key: 'alias' },
    { title: 'API 地址', dataIndex: 'api_endpoint', key: 'api_endpoint' },
    { title: '模型', dataIndex: 'model', key: 'model' },
    {
      title: '默认', dataIndex: 'is_default', key: 'is_default',
      render: (text) => (text ? '是' : '否'),
    },
    {
      title: '操作', key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card title={<Title level={2}>Ollama 配置</Title>} style={{ margin: '20px' }}>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={handleAddNew}>添加新的配置</Button>
      </div>
      <Table columns={columns} dataSource={configs} rowKey="id" pagination={false} />

      {isModalVisible && (
        <Modal
          title={editingConfig && editingConfig.id ? '编辑配置' : '添加配置'}
          open={isModalVisible}
          onCancel={handleCancel}
          footer={null}
        >
          <Form form={form} layout="vertical" onFinish={handleSave} initialValues={editingConfig}>
            <Form.Item label="别名" name="alias" rules={[{ required: true, message: '请输入别名!' }]}>
              <Input />
            </Form.Item>
            <Form.Item label="API 地址" name="api_endpoint" rules={[
              { required: true, message: '请输入 API 地址!' },
              { type: 'url', message: '请输入有效的 URL 地址!' },
            ]}>
              <Space.Compact>
                <Input />
                <Button type="primary" onClick={handleFetchModels}>获取模型</Button>
              </Space.Compact>
            </Form.Item>
            <Form.Item label="模型" name="model" rules={[{ required: true, message: '请选择一个模型!' }]}>
              <Select placeholder="请选择模型">
                {availableModels.map(model => (
                  <Option key={model} value={model}>{model}</Option>
                ))}
              </Select>
            </Form.Item>
            <Form.Item label="Temperature" name="temperature">
              <InputNumber step={0.1} min={0} max={1} />
            </Form.Item>
            <Form.Item label="Top P" name="top_p">
              <InputNumber step={0.1} min={0} max={1} />
            </Form.Item>
            <Form.Item name="is_default" valuePropName="checked">
              <Checkbox>设为默认</Checkbox>
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">保存</Button>
                <Button onClick={handleCancel}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>
      )}
    </Card>
  );
};

export default SystemSettingsPage;
