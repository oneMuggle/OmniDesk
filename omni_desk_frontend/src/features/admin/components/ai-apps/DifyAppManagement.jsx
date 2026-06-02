import { useState } from 'react';
import PropTypes from 'prop-types';
import { Button, Table, Modal, Form, Input, Checkbox, Space, Tag, message } from 'antd';
import { addDifyApp, updateDifyApp, deleteDifyApp } from '../../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../../shared/utils/logger';

const DifyAppManagement = ({ difyApps, loadDifyApps }) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();

  const handleAdd = () => { setEditing(null); form.resetFields(); setModalVisible(true); };

  const handleEdit = (record) => {
    setEditing(record);
    form.setFieldsValue({ name: record.name, description: record.description, embed_url: record.embed_url, is_active: record.is_active });
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
    try { await deleteDifyApp(id); message.success('Dify 应用删除成功。'); loadDifyApps(); }
    catch (error) { message.error('删除 Dify 应用失败。'); logger.error('删除 Dify 应用失败:', error); }
  };

  const handleSave = async (values) => {
    try {
      if (editing) { await updateDifyApp(editing.id, values); message.success('Dify 应用更新成功。'); }
      else { await addDifyApp(values); message.success('Dify 应用添加成功。'); }
      setModalVisible(false); loadDifyApps();
    } catch (error) { message.error(`保存 Dify 应用失败: ${error.response?.data?.detail || error.message}`); logger.error('保存 Dify 应用失败:', error); }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '嵌入 URL', dataIndex: 'embed_url', key: 'embed_url', ellipsis: true, render: (url) => <a href={url} target="_blank" rel="noopener noreferrer">{url}</a> },
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
      <div style={{ marginBottom: 16 }}><Button type="primary" onClick={handleAdd}>添加 Dify 应用</Button></div>
      <Table columns={columns} dataSource={difyApps} rowKey="id" pagination={false} />
      <Modal title={editing ? '编辑 Dify 应用' : '添加 Dify 应用'} open={modalVisible} onCancel={() => { setModalVisible(false); setEditing(null); form.resetFields(); }} footer={null}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item label="应用名称" name="name" rules={[{ required: true, message: '请输入应用名称!' }]}><Input /></Form.Item>
          <Form.Item label="描述" name="description"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item label="嵌入 URL" name="embed_url" rules={[{ required: true, message: '请输入嵌入 URL!' }, { type: 'url', message: '请输入有效的 URL 地址!' }]}><Input /></Form.Item>
          <Form.Item name="is_active" valuePropName="checked"><Checkbox>设为激活</Checkbox></Form.Item>
          <Form.Item><Space><Button type="primary" htmlType="submit">保存</Button><Button onClick={() => { setModalVisible(false); setEditing(null); form.resetFields(); }}>取消</Button></Space></Form.Item>
        </Form>
      </Modal>
    </>
  );
};

DifyAppManagement.propTypes = { difyApps: PropTypes.array.isRequired, loadDifyApps: PropTypes.func.isRequired };
export default DifyAppManagement;
