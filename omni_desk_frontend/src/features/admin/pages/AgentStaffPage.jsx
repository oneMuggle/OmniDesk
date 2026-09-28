import { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Card, Drawer, Empty, InputNumber, List, Space, Switch, Table, Tag, Typography, message,
} from 'antd';
import { ReloadOutlined, TeamOutlined } from '@ant-design/icons';
import {
  getAgentProfileRuns,
  listAgentProfiles,
  runAgentProfile,
  updateAgentProfile,
} from '../../smart-assistant/api/smartAssistantApi';
import { extractResults } from '../../../shared/api/responseHandler';
import { logger } from '../../../shared/utils/logger';

const { Title, Text, Paragraph } = Typography;

export const RUN_STATUS = {
  running: { color: 'blue', label: '运行中' },
  succeeded: { color: 'green', label: '成功' },
  degraded: { color: 'orange', label: '已降级' },
  failed: { color: 'red', label: '失败' },
  skipped: { color: 'default', label: '已跳过' },
};

export const EVENT_LABELS = {
  'run.started': '运行开始',
  'run.completed': '运行完成',
  'run.failed': '运行失败',
  'run.skipped': '运行跳过',
  'llm.call': '调用 LLM',
  'llm.fallback': 'LLM 降级为模板',
  'notify.sent': '发送通知',
  'proposal.created': '创建待确认事项',
  'proposal.approved': '待确认事项已确认',
  'proposal.rejected': '待确认事项已取消',
  'proposal.expired': '待确认事项已过期',
  'proposal.failed': '待确认事项执行失败',
  'quota.exceeded': '超出配额',
  'config.changed': '配置变更',
};

const SKIP_REASONS = { disabled: '角色未启用', already_running: '上一次运行尚未结束', no_runner: '未实现' };

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
}

function errorText(error, fallback) {
  return error?.response?.data?.detail || fallback;
}

function RunStatusTag({ status }) {
  const meta = RUN_STATUS[status] || { color: 'default', label: status || '—' };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

RunStatusTag.propTypes = { status: PropTypes.string };

function eventSummary(event) {
  const payload = event.payload || {};
  const parts = [];
  if (event.user_name) parts.push(`对象：${event.user_name}`);
  if (payload.title) parts.push(payload.title);
  if (payload.kind && event.event_type === 'quota.exceeded') {
    parts.push(`${payload.kind === 'llm' ? 'LLM' : '动作'}配额 ${payload.quota}`);
  } else if (payload.kind) {
    parts.push(`类型：${payload.kind}`);
  }
  if (payload.purpose) parts.push(`用途：${payload.purpose}`);
  if (payload.reason) parts.push(SKIP_REASONS[payload.reason] || payload.reason);
  if (payload.changes) parts.push(`修改：${Object.keys(payload.changes).join('、')}`);
  return parts.join('；');
}

/**
 * 控制台「AI 管理 → 数字员工」（S4-1）。
 *
 * 每个角色可单独启停、单独设置每日 LLM 配额与动作配额；可立即运行一次，
 * 并查看最近的运行记录与审计事件。数字员工只能发起并请求确认。
 */
const AgentStaffPage = () => {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState('');
  const [runsFor, setRunsFor] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await listAgentProfiles();
      const data = extractResults(response.data) || response.data;
      setProfiles(Array.isArray(data) ? data : []);
    } catch (error) {
      message.error('加载数字员工失败');
      logger.error('加载数字员工失败:', error);
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

  const patch = async (key, data, successText) => {
    setSaving(key);
    try {
      const { data: updated } = await updateAgentProfile(key, data);
      setProfiles((prev) => prev.map((p) => (p.key === key ? { ...p, ...updated } : p)));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      message.success(successText);
    } catch (error) {
      message.error(errorText(error, '保存失败'));
    } finally {
      setSaving('');
    }
  };

  const setDraft = (key, field, value) => {
    setDrafts((prev) => ({ ...prev, [key]: { ...prev[key], [field]: value } }));
  };

  const runNow = async (key) => {
    try {
      await runAgentProfile(key);
      message.success('已提交运行，稍后刷新查看结果');
    } catch (error) {
      message.error(errorText(error, '提交失败'));
    }
  };

  const openRuns = async (profile) => {
    setRunsFor(profile);
    setRuns([]);
    setRunsLoading(true);
    try {
      const { data } = await getAgentProfileRuns(profile.key);
      setRuns(Array.isArray(data) ? data : []);
    } catch (error) {
      message.error('加载运行记录失败');
      logger.error('加载运行记录失败:', error);
    } finally {
      setRunsLoading(false);
    }
  };

  const columns = [
    {
      title: '角色',
      key: 'name',
      render: (_, p) => (
        <div style={{ maxWidth: 320 }}>
          <Text strong>{p.name}</Text>
          <Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }}>{p.description}</Paragraph>
        </div>
      ),
    },
    { title: '定时', dataIndex: 'schedule_label', key: 'schedule', render: (v) => v || '—' },
    {
      title: '启用',
      key: 'enabled',
      render: (_, p) => (
        <Switch
          checked={p.enabled}
          loading={saving === p.key}
          aria-label={`启用${p.name}`}
          onChange={(checked) => patch(p.key, { enabled: checked }, checked ? `已启用${p.name}` : `已停用${p.name}`)}
        />
      ),
    },
    {
      title: '每日配额',
      key: 'quota',
      render: (_, p) => {
        const draft = drafts[p.key] || {};
        const llm = draft.daily_llm_quota ?? p.daily_llm_quota;
        const actions = draft.daily_action_quota ?? p.daily_action_quota;
        const dirty = llm !== p.daily_llm_quota || actions !== p.daily_action_quota;
        return (
          <Space direction="vertical" size={4}>
            <Space size={4}>
              <Text type="secondary">动作</Text>
              <InputNumber
                size="small"
                min={0}
                max={100000}
                value={actions}
                aria-label={`${p.name}动作配额`}
                onChange={(v) => setDraft(p.key, 'daily_action_quota', v ?? 0)}
              />
            </Space>
            <Space size={4}>
              <Text type="secondary">LLM</Text>
              <InputNumber
                size="small"
                min={0}
                max={100000}
                value={llm}
                aria-label={`${p.name}LLM配额`}
                onChange={(v) => setDraft(p.key, 'daily_llm_quota', v ?? 0)}
              />
            </Space>
            {dirty && (
              <Button
                size="small"
                type="primary"
                loading={saving === p.key}
                onClick={() => patch(p.key, { daily_llm_quota: llm, daily_action_quota: actions }, '配额已保存')}
              >
                保存配额
              </Button>
            )}
          </Space>
        );
      },
    },
    {
      title: '今日用量',
      key: 'usage',
      render: (_, p) => (
        <Space direction="vertical" size={0}>
          <Text>动作 {p.usage_today?.actions ?? 0} / {p.daily_action_quota}</Text>
          <Text type="secondary">LLM {p.usage_today?.llm_calls ?? 0} / {p.daily_llm_quota}</Text>
        </Space>
      ),
    },
    {
      title: '最近运行',
      key: 'last_run',
      render: (_, p) => (p.last_run ? (
        <Space direction="vertical" size={0}>
          <RunStatusTag status={p.last_run.status} />
          <Text type="secondary" style={{ fontSize: 12 }}>{formatTime(p.last_run.started_at)}</Text>
        </Space>
      ) : <Text type="secondary">尚未运行</Text>),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, p) => (
        <Space direction="vertical" size={4}>
          <Button size="small" disabled={!p.enabled} onClick={() => runNow(p.key)}>立即运行</Button>
          <Button size="small" type="link" onClick={() => openRuns(p)}>运行记录</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }} wrap>
        <Title level={4} style={{ margin: 0 }}>
          <TeamOutlined /> 数字员工
        </Title>
        <Button icon={<ReloadOutlined />} onClick={refresh}>刷新</Button>
      </Space>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="数字员工只能发起并请求确认：需要修改数据的操作会发给当事人，由本人在智能助手里确认。每个动作都记录审计；超出配额时跳过后续动作或改用模板内容。"
      />
      <Table rowKey="key" columns={columns} dataSource={profiles} loading={loading} pagination={false} />

      <Drawer
        title={runsFor ? `${runsFor.name} · 最近运行` : '最近运行'}
        open={Boolean(runsFor)}
        width={560}
        onClose={() => setRunsFor(null)}
      >
        {!runsLoading && runs.length === 0 && <Empty description="暂无运行记录" />}
        <List
          loading={runsLoading}
          dataSource={runs}
          renderItem={(run) => (
            <List.Item key={run.id} style={{ display: 'block' }}>
              <Space wrap>
                <RunStatusTag status={run.status} />
                <Text>{formatTime(run.started_at)}</Text>
                <Text type="secondary">{run.trigger === 'manual' ? '手动' : '定时'}</Text>
              </Space>
              {run.error && <div><Text type="danger">{run.error}</Text></div>}
              <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                {(run.events || []).map((event) => (
                  <li key={event.id}>
                    <Text>{EVENT_LABELS[event.event_type] || event.event_type}</Text>
                    {eventSummary(event) && <Text type="secondary">：{eventSummary(event)}</Text>}
                  </li>
                ))}
              </ul>
            </List.Item>
          )}
        />
      </Drawer>
    </Card>
  );
};

export default AgentStaffPage;
