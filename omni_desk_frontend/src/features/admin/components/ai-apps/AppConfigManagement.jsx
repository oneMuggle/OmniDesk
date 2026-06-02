import { useState } from 'react';
import PropTypes from 'prop-types';
import { Button, Table, Modal, Form, Input, InputNumber, Checkbox, Space, Select, Tag, message } from 'antd';
import {
  addAppConfig,
  updateAppConfig,
  deleteAppConfig,
  fetchEndpointModels,
} from '../../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../../shared/utils/logger';

const AppConfigManagement = ({ appConfigs, endpoints, loadAppConfigs }) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();
  const [modelOptions, setModelOptions] = useState([]);
  const [selectedEndpointId, setSelectedEndpointId] = useState(null);
  const [fetchingModels, setFetchingModels] = useState(false);

  const handleEndpointChange = async (endpointId, preserveModelName = false) => {
    setSelectedEndpointId(endpointId);
    if (!preserveModelName) {
      form.setFieldValue('model_name', undefined);
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

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, temperature: 0.7, top_p: 0.9 });
    setModelOptions([]);
    setSelectedEndpointId(null);
    setFetchingModels(false);
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditing(record);
    form.setFieldsValue({
      app_name: record.app_name,
      endpoint: record.endpoint,
      model_name: record.model_name,
      temperature: record.temperature,
      top_p: record.top_p,
      is_active: record.is_active,
    });
    const endpointId = record.endpoint?.id ?? record.endpoint;
    setSelectedEndpointId(endpointId);
    if (endpointId) {
      handleEndpointChange(endpointId, true);
    }
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await deleteAppConfig(id);
      message.success('应用配置删除成功。');
      loadAppConfigs();
    } catch (error) {
      message.error('删除应用配置失败。');
      logger.error('删除应用配置失败:', error);
    }
  };

  const handleSave = async (values) => {
    try {
      if (editing) {
        await updateAppConfig(editing.id, values);
        message.success('应用配置更新成功。');
      } else {
        await addAppConfig(values);
        message.success('应用配置添加成功。');
      }
      setModalVisible(false);
      loadAppConfigs();
    } catch (error) {
      message.error(`保存应用配置失败: ${error.response?.data?.detail || error.message}`);
      logger.error('保存应用配置失败:', error);
    }
  };

  const columns = [
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
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={handleAdd}>添加应用配置</Button>
      </div>
      <Table columns={columns} dataSource={appConfigs} rowKey="id" pagination={false} />

      <Modal
        title={editing ? '编辑应用配置' : '添加应用配置'}
        open={modalVisible}
        onCancel={() => { setModalVisible(false); setEditing(null); form.resetFields(); setModelOptions([]); setSelectedEndpointId(null); setFetchingModels(false); }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
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
              <Button onClick={() => { setModalVisible(false); setEditing(null); form.resetFields(); setModelOptions([]); setSelectedEndpointId(null); setFetchingModels(false); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

AppConfigManagement.propTypes = {
  appConfigs: PropTypes.array.isRequired,
  endpoints: PropTypes.array.isRequired,
  loadAppConfigs: PropTypes.func.isRequired,
};

export default AppConfigManagement;
