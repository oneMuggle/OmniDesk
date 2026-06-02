import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Button, Table, Modal, Form, Input, InputNumber, Checkbox, Space, Tag, message } from 'antd';
import { CheckOutlined } from '@ant-design/icons';
import {
  addEndpoint,
  updateEndpoint,
  deleteEndpoint,
  fetchEndpointModels,
  testEndpoint as apiTestEndpoint,
} from '../../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../../shared/utils/logger';

const EndpointManagement = ({ endpoints, loadEndpoints, loadAppConfigs }) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();
  const [testingId, setTestingId] = useState(null);
  const [testResult, setTestResult] = useState(null);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, priority: 1, is_fallback: false });
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditing(record);
    form.setFieldsValue({
      name: record.name,
      api_endpoint: record.api_endpoint,
      is_active: record.is_active,
      priority: record.priority || 1,
      is_fallback: record.is_fallback || false,
      model_capabilities: record.model_capabilities || [],
      cost_per_1k_tokens: record.cost_per_1k_tokens,
    });
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
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

  const handleSave = async (values) => {
    try {
      if (editing) {
        await updateEndpoint(editing.id, values);
        message.success('端点更新成功。');
      } else {
        await addEndpoint(values);
        message.success('端点添加成功。');
      }
      setModalVisible(false);
      loadEndpoints();
    } catch (error) {
      message.error(`保存端点失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存端点失败:', error);
    }
  };

  const handleTest = async (endpointId) => {
    setTestingId(endpointId);
    setTestResult(null);
    try {
      const response = await apiTestEndpoint(endpointId);
      const result = response.data;
      setTestResult({ id: endpointId, status: result.status, message: result.message });
      if (result.status === 'ok') {
        message.success(result.message);
      } else {
        message.warning(result.message);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.message || error.message || '测试请求失败';
      setTestResult({ id: endpointId, status: 'error', message: errorMsg });
      message.error(errorMsg);
      logger.error('测试端点失败:', error);
    } finally {
      setTestingId(null);
    }
  };

  const columns = [
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
        const isTesting = testingId === record.id;
        const result = testResult?.id === record.id ? testResult : null;
        return (
          <Space size="middle">
            <Button
              size="small"
              type="default"
              icon={isTesting ? undefined : <CheckOutlined />}
              loading={isTesting}
              onClick={() => handleTest(record.id)}
            >
              测试
            </Button>
            {result && result.status === 'ok' && <Tag color="green">正常</Tag>}
            {result && result.status !== 'ok' && (
              <Tag color="red">{result.message?.slice(0, 20)}...</Tag>
            )}
            <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
            <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
          </Space>
        );
      },
    },
  ];

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={handleAdd}>添加 API 端点</Button>
      </div>
      <Table columns={columns} dataSource={endpoints} rowKey="id" pagination={false} />

      <Modal
        title={editing ? '编辑 API 端点' : '添加 API 端点'}
        open={modalVisible}
        onCancel={() => { setModalVisible(false); setEditing(null); form.resetFields(); }}
        footer={null}
        width={520}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}
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
          <Form.Item label="API 密钥" name="api_key" rules={[{ required: !editing, message: '请输入 API 密钥!' }]}>
            <Input.Password placeholder={editing ? '留空则不修改' : ''} />
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
              <Button onClick={() => { setModalVisible(false); setEditing(null); form.resetFields(); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

EndpointManagement.propTypes = {
  endpoints: PropTypes.array.isRequired,
  loadEndpoints: PropTypes.func.isRequired,
  loadAppConfigs: PropTypes.func.isRequired,
};

export default EndpointManagement;
