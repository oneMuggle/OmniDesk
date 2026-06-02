import { useState } from 'react';
import PropTypes from 'prop-types';
import { Button, Table, Modal, Form, Input, Checkbox, Space, Tag, message } from 'antd';
import { addRagflowConfig, updateRagflowConfig, deleteRagflowConfig } from '../../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../../shared/utils/logger';

const RagflowConfigManagement = ({ ragflowConfigs, loadRagflowConfigs }) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();

  const handleAdd = () => { setEditing(null); form.resetFields(); form.setFieldsValue({ is_active: true }); setModalVisible(true); };

  const handleEdit = (record) => {
    setEditing(record);
    form.setFieldsValue({ name: record.name, api_endpoint: record.api_endpoint, api_key: '', is_active: record.is_active });
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
    try { await deleteRagflowConfig(id); message.success('Ragflow 配置删除成功。'); loadRagflowConfigs(); }
    catch (error) { message.error('删除 Ragflow 配置失败。'); logger.error('删除 Ragflow 配置失败:', error); }
  };

  const handleSave = async (values) => {
    try {
      const payload = { ...values };
      if (editing && !payload.api_key) { delete payload.api_key; }
      if (editing) { await updateRagflowConfig(editing.id, payload); message.success('Ragflow 配置更新成功。'); }
      else { await addRagflowConfig(payload); message.success('Ragflow 配置添加成功。'); }
      setModalVisible(false); loadRagflowConfigs();
    } catch (error) { message.error(`保存 Ragflow 配置失败: ${error.response?.data?.detail || error.message}`); logger.error('保存 Ragflow 配置失败:', error); }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: 'API 端点', dataIndex: 'api_endpoint', key: 'api_endpoint' },
    { title: '状态', dataIndex: 'is_active', key: 'is_active', render: (text) => (text ? <Tag color="green">激活</Tag> : <Tag color="default">未激活</Tag>) },
    { title: '操作', key: 'action', render: (_, record) => (
      <Space size="middle">
        <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
        <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
      </Space>
    )},
  ];

  return (
    <>
      <div style={{ marginBottom: 16 }}><Button type="primary" onClick={handleAdd}>添加 Ragflow 配置</Button></div>
      <Table columns={columns} dataSource={ragflowConfigs} rowKey="id" pagination={false} />
      <Modal title={editing ? '编辑 Ragflow 配置' : '添加 Ragflow 配置'} open={modalVisible} onCancel={() => { setModalVisible(false); setEditing(null); form.resetFields(); }} footer={null}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item label="配置名称" name="name" rules={[{ required: true, message: '请输入配置名称!' }]}><Input /></Form.Item>
          <Form.Item label="API 端点" name="api_endpoint" rules={[{ required: true, message: '请输入 API 端点!' }, { type: 'url', message: '请输入有效的 URL 地址!' }]}><Input /></Form.Item>
          <Form.Item label="API 密钥" name="api_key" rules={[{ required: !editing, message: '请输入 API 密钥!' }]}><Input.Password placeholder={editing ? '留空则不修改' : ''} /></Form.Item>
          <Form.Item name="is_active" valuePropName="checked"><Checkbox>设为激活</Checkbox></Form.Item>
          <Form.Item><Space><Button type="primary" htmlType="submit">保存</Button><Button onClick={() => { setModalVisible(false); setEditing(null); form.resetFields(); }}>取消</Button></Space></Form.Item>
        </Form>
      </Modal>
    </>
  );
};

RagflowConfigManagement.propTypes = { ragflowConfigs: PropTypes.array.isRequired, loadRagflowConfigs: PropTypes.func.isRequired };
export default RagflowConfigManagement;
