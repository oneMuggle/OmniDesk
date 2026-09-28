import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Empty, Space, Table, Tag, Typography, message } from 'antd';
import { DatabaseOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import {
  getKnowledgeIngestSummary,
  reconcileKnowledgeSources,
  retryKnowledgeSource,
} from '../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../shared/utils/logger';

const { Title, Paragraph } = Typography;

export const STATUS_COLORS = {
  pending: 'blue',
  ingested: 'green',
  failed: 'red',
  removed: 'default',
};

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
}

function errorText(error, fallback) {
  return error?.response?.data?.detail || fallback;
}

/**
 * 控制台「AI 管理 → 知识入库」（S4-2）。
 *
 * 已发布公告、文档库（Paperless）文档会自动写入 RAGFlow；检索时按用户能否看到原对象过滤。
 * 这里查看是否已配置、各状态数量和失败记录，可立即对账或逐条重试。
 */
const KnowledgeIngestPage = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    try {
      const { data } = await getKnowledgeIngestSummary();
      setSummary(data);
    } catch (error) {
      message.error('加载知识入库概况失败');
      logger.error('加载知识入库概况失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = () => {
    setLoading(true);
    load();
  };

  const reconcile = async () => {
    setBusy('reconcile');
    try {
      await reconcileKnowledgeSources();
      message.success('已提交对账，稍后刷新查看结果');
    } catch (error) {
      message.error(errorText(error, '提交对账失败'));
    } finally {
      setBusy('');
    }
  };

  const retry = async (record) => {
    setBusy(`retry-${record.id}`);
    try {
      await retryKnowledgeSource(record.id);
      message.success('已重新提交入库');
    } catch (error) {
      message.error(errorText(error, '重试失败'));
    } finally {
      setBusy('');
    }
  };

  const statuses = summary?.statuses || [];
  const countRows = (summary?.source_types || []).map((type) => ({
    key: type.value,
    label: type.label,
    ...(summary?.counts?.[type.value] || {}),
  }));
  const countColumns = [
    { title: '来源', dataIndex: 'label', key: 'label' },
    ...statuses.map((s) => ({
      title: <Tag color={STATUS_COLORS[s.value] || 'default'}>{s.label}</Tag>,
      dataIndex: s.value,
      key: s.value,
      render: (value) => value ?? 0,
    })),
  ];
  const failureColumns = [
    { title: '来源', dataIndex: 'source_type_display', key: 'source' },
    { title: '标题', key: 'title', render: (_, r) => r.title || `#${r.source_id}` },
    { title: '错误', dataIndex: 'last_error', key: 'error' },
    { title: '失败次数', dataIndex: 'attempts', key: 'attempts' },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated', render: formatTime },
    {
      title: '操作',
      key: 'actions',
      render: (_, r) => (
        <Button size="small" loading={busy === `retry-${r.id}`} disabled={!summary?.enabled} onClick={() => retry(r)}>
          重试
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', marginBottom: 8 }}>
        <Title level={4} style={{ margin: 0 }}>
          <DatabaseOutlined /> 知识入库
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<SyncOutlined />}
            onClick={reconcile}
            loading={busy === 'reconcile'}
            disabled={!summary?.enabled}
          >
            立即对账
          </Button>
        </Space>
      </Space>
      <Paragraph type="secondary">
        已发布的公告和文档库中的文档会自动写入知识库，删除或撤回后同步移除；每 30 分钟自动对账一次。
        智能助手检索时，只返回提问人自己能看到的公告和文档。
      </Paragraph>

      {summary && !summary.enabled && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="自动入库未启用"
          description={
            summary.dataset_configured
              ? '已设置入库数据集，但没有启用的 RAGFlow 配置。请先在 RAGFlow 配置中启用一项。'
              : '请在部署环境中设置 SMART_ASSISTANT_INGEST_DATASET_ID（单独的 RAGFlow 数据集，不要挂到 RAGFlow 聊天助手上）。'
          }
        />
      )}

      <Card title="入库概况" size="small" style={{ marginBottom: 16 }}>
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          loading={loading}
          columns={countColumns}
          dataSource={countRows}
        />
      </Card>

      <Card title="最近失败" size="small">
        {summary?.failures?.length ? (
          <Table rowKey="id" size="small" pagination={false} columns={failureColumns} dataSource={summary.failures} />
        ) : (
          <Empty description="没有失败记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>
    </div>
  );
};

export default KnowledgeIngestPage;
