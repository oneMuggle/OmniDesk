import { useState, useEffect, useCallback } from 'react';
import { Card, Button, Table, Modal, Form, Input, InputNumber, Checkbox, Space, Typography, message } from 'antd';
import {
  getLlmConfigs,
  addLlmConfig,
  updateLlmConfig,
  deleteLlmConfig,
} from '../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../shared/utils/logger';

const { Title } = Typography;

const AiAppManagementPage = () => {
  const [configs, setConfigs] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [form] = Form.useForm();

  const loadConfigs = useCallback(async () => {
    try {
      const response = await getLlmConfigs();
      setConfigs(response.data.results || []);
    } catch (error) {
      message.error('加载配置失败。');
      logger.error('加载 LLM 配置失败:', error);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadConfigs();
  }, [loadConfigs]);

  const handleAdd = () => {
    setEditingConfig(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, temperature: 0.7, top_p: 0.9 });
    setIsModalVisible(true);
  };

  const handleEdit = (config) => {
    setEditingConfig(config);
    form.setFieldsValue({
      ...config,
    });
    setIsModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await deleteLlmConfig(id);
      message.success('配置删除成功。');
      loadConfigs();
    } catch (error) {
      message.error('删除配置失败。');
      logger.error('删除 LLM 配置失败:', error);
    }
  };

  const handleSave = async (values) => {
    try {
      if (editingConfig) {
        await updateLlmConfig(editingConfig.id, values);
        message.success('配置更新成功。');
      } else {
        await addLlmConfig(values);
        message.success('配置添加成功。');
      }
      setIsModalVisible(false);
      loadConfigs();
    } catch (error) {
      message.error(`保存配置失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存 LLM 配置失败:', error);
    }
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingConfig(null);
    form.resetFields();
  };

  const columns = [
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
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
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
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card title={<Title level={2}>AI 应用管理</Title>} style={{ margin: '20px' }}>
        <div style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={handleAdd}>
            添加新的 LLM 配置
          </Button>
        </div>
        <Table columns={columns} dataSource={configs} rowKey="id" pagination={false} />

        <Modal
          title={editingConfig ? '编辑 LLM 配置' : '添加 LLM 配置'}
          open={isModalVisible}
          onCancel={handleCancel}
          footer={null}
        >
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
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
              rules={[
                { required: true, message: '请输入 API 端点!' },
                { type: 'url', message: '请输入有效的 URL 地址!' },
              ]}
            >
              <Input placeholder="https://gcli.ggchan.dev" />
            </Form.Item>
            <Form.Item
              label="API 密钥"
              name="api_key"
              rules={[{ required: !editingConfig, message: '请输入 API 密钥!' }]}
            >
              <Input.Password placeholder={editingConfig ? '留空则不修改' : ''} />
            </Form.Item>
            <Form.Item
              label="模型名称"
              name="model_name"
              rules={[{ required: true, message: '请输入模型名称!' }]}
            >
              <Input placeholder="gemini-2.5-pro" />
            </Form.Item>
            <Form.Item
              label="Temperature"
              name="temperature"
            >
              <InputNumber step={0.1} min={0} max={2} />
            </Form.Item>
            <Form.Item
              label="Top P"
              name="top_p"
            >
              <InputNumber step={0.1} min={0} max={1} />
            </Form.Item>
            <Form.Item
              name="is_active"
              valuePropName="checked"
            >
              <Checkbox>设为激活（同时只允许一个配置激活）</Checkbox>
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
      </Card>
    </>
  );
};

export default AiAppManagementPage;
