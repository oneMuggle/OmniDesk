import { Modal, Descriptions, Tag, Table, Button, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { executePlugin } from '../api/pluginApi';

const STATUS_MAP = {
  draft: { color: 'default', text: '草稿' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已批准' },
  rejected: { color: 'red', text: '已拒绝' },
  disabled: { color: 'gray', text: '已禁用' },
};

const PluginDetailModal = ({ visible, plugin, onClose }) => {
  const [executing, setExecuting] = useState(false);
  const [execResult, setExecResult] = useState(null);

  if (!plugin) return null;

  const status = STATUS_MAP[plugin.status] || STATUS_MAP.draft;

  const versionColumns = [
    { title: '版本', dataIndex: 'version', key: 'version' },
    { title: '哈希', dataIndex: 'file_hash', key: 'file_hash', ellipsis: true },
    {
      title: '状态',
      key: 'is_active',
      render: (v) => (v.is_active ? <Tag color="green">激活</Tag> : <Tag>未激活</Tag>),
    },
    { title: '上传时间', dataIndex: 'uploaded_at', key: 'uploaded_at' },
  ];

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const result = await executePlugin(plugin.id);
      setExecResult(result);
      message.success('执行成功');
    } catch {
      message.error('执行失败');
    } finally {
      setExecuting(false);
    }
  };

  return (
    <Modal
      title={plugin.name}
      open={visible}
      onCancel={onClose}
      footer={
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Button onClick={onClose}>关闭</Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={executing}
            onClick={handleExecute}
            disabled={plugin.status !== 'approved'}
          >
            执行
          </Button>
        </div>
      }
      width={700}
    >
      <Descriptions column={2} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="标识符">{plugin.slug}</Descriptions.Item>
        <Descriptions.Item label="分类">{plugin.category}</Descriptions.Item>
        <Descriptions.Item label="状态"><Tag color={status.color}>{status.text}</Tag></Descriptions.Item>
        <Descriptions.Item label="接口版本">{plugin.interface_version || 'v1'}</Descriptions.Item>
      </Descriptions>
      {plugin.description && (
        <div style={{ marginBottom: 16 }}>
          <strong>描述：</strong>{plugin.description}
        </div>
      )}
      {plugin.versions && plugin.versions.length > 0 && (
        <Table
          columns={versionColumns}
          dataSource={plugin.versions}
          rowKey="id"
          size="small"
          pagination={false}
        />
      )}
      {execResult && (
        <div style={{ marginTop: 16, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
          <strong>执行结果：</strong>
          <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(execResult, null, 2)}
          </pre>
        </div>
      )}
    </Modal>
  );
};

export default PluginDetailModal;
