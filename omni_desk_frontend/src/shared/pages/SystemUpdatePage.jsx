import { useState, useEffect } from 'react';
import { Card, Tabs, Spin, Tag, Descriptions, Table, Alert, Typography, Button } from 'antd';
import { DownloadOutlined, WindowsOutlined } from '@ant-design/icons';
import axiosInstanceInstance from '../api/axiosInstanceConfig';
import ReactMarkdown from 'react-markdown';

const { Title } = Typography;

function SystemUpdatePage() {
  const [versionData, setVersionData] = useState(null);
  const [changelog, setChangelog] = useState('');
  const [migrationData, setMigrationData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [versionRes, changelogRes, migrationRes] = await Promise.all([
          axiosInstance.get('/api/system/version/'),
          axiosInstance.get('/api/system/changelog/'),
          axiosInstance.get('/api/system/migrations/'),
        ]);
        setVersionData(versionRes.data);
        setChangelog(changelogRes.data.changelog);
        setMigrationData(migrationRes.data);
      } catch (error) {
        console.error('Failed to load system update info:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  if (loading) {
    return <Spin />;
  }

  const isDev = versionData?.version?.includes('dev');

  const pendingColumns = [
    { title: '应用', dataIndex: 'app', key: 'app', width: 180 },
    { title: '迁移文件', dataIndex: 'name', key: 'name' },
    {
      title: '操作',
      dataIndex: 'operations',
      key: 'operations',
      render: (ops) => ops.map((op, i) => {
        const isDestructive = op.destructive;
        const text = op.type === 'DeleteModel'
          ? `删除模型 ${op.model}`
          : op.type === 'RemoveField'
            ? `删除字段 ${op.model}.${op.field}`
            : op.type === 'CreateModel'
              ? `创建模型 ${op.model}`
              : op.type === 'AddField'
                ? `添加字段 ${op.model}.${op.field}`
                : op.type === 'AlterField'
                  ? `修改字段 ${op.model}.${op.field}`
                  : op.type;
        return isDestructive
          ? <Tag key={i} color="red">{text}</Tag>
          : <Tag key={i} color="blue">{text}</Tag>;
      }),
    },
  ];

  const appliedColumns = [
    { title: '应用', dataIndex: 'app', key: 'app', width: 200 },
    { title: '迁移文件', dataIndex: 'name', key: 'name' },
  ];

  const items = [
    {
      key: 'version',
      label: '版本信息',
      children: (
        <Card>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="应用版本">
              {versionData?.version || '未知'}
              {isDev && <Tag color="orange" style={{ marginLeft: 8 }}>开发版</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="构建时间">{versionData?.build_time || '未知'}</Descriptions.Item>
            <Descriptions.Item label="Django 版本">{versionData?.django_version || '未知'}</Descriptions.Item>
          </Descriptions>
        </Card>
      ),
    },
    {
      key: 'desktop',
      label: '桌面客户端',
      children: (
        <Card>
          <div style={{ textAlign: 'center', padding: '24px' }}>
            <WindowsOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
            <Title level={4}>OmniDesk 桌面助手</Title>
            <p style={{ color: '#8c8c8c', marginBottom: 24 }}>
              Win7 兼容 · 消息提醒 · 快速访问 · 离线缓存
            </p>
            <Button
              type="primary"
              size="large"
              icon={<DownloadOutlined />}
              href="/static/downloads/OmniDeskNotifier.exe"
            >
              下载桌面客户端
            </Button>
            <div style={{ marginTop: 16, fontSize: 12, color: '#999' }}>
              <p>版本: {versionData?.version || '未知'}</p>
              <p>适用系统: Windows 7 / 8 / 10 / 11</p>
            </div>
          </div>
        </Card>
      ),
    },
    {
      key: 'changelog',
      label: '更新日志',
      children: (
        <Card>
          <div style={{ maxHeight: '600px', overflowY: 'auto', padding: '16px', background: '#fafafa', borderRadius: 4 }}>
            <ReactMarkdown>{changelog}</ReactMarkdown>
          </div>
        </Card>
      ),
    },
    {
      key: 'migrations',
      label: '迁移状态',
      children: (
        <>
          {migrationData?.has_destructive && (
            <Alert
              message="警告：检测到破坏性变更（删除表/字段）"
              description="执行迁移前请务必备份数据库，确认变更影响后再继续。"
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}
          <Card title={`待执行迁移 (${migrationData?.pending_count || 0})`} style={{ marginBottom: 16 }}>
            {migrationData?.pending_count === 0 ? (
              <p style={{ color: '#8c8c8c' }}>无待执行迁移。</p>
            ) : (
              <Table
                columns={pendingColumns}
                dataSource={migrationData?.pending || []}
                rowKey={(r) => `${r.app}_${r.name}`}
                pagination={false}
                size="small"
              />
            )}
          </Card>
          <Card title={`已应用迁移 (${migrationData?.applied_count || 0})`}>
            <Table
              columns={appliedColumns}
              dataSource={migrationData?.applied || []}
              rowKey={(r) => `${r.app}_${r.name}`}
              pagination={{ pageSize: 10 }}
              size="small"
            />
          </Card>
        </>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>系统更新管理</Title>
      <Tabs defaultActiveKey="version" items={items} />
    </div>
  );
}

export default SystemUpdatePage;
