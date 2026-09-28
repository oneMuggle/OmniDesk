import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { FundOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  createBudgetPolicy,
  deleteBudgetPolicy,
  getBudgetUsage,
  listBudgetPolicies,
  searchBudgetUsers,
  updateBudgetPolicy,
} from '../../smart-assistant/api/smartAssistantApi';
import { logger } from '../../../shared/utils/logger';

const { Title, Paragraph, Text } = Typography;

export const STATE_TAGS = {
  ok: { color: 'green', label: '正常' },
  readonly: { color: 'orange', label: '只读' },
  blocked: { color: 'red', label: '已停用' },
};

const SCOPE_OPTIONS = [
  { value: 'group', label: '用户组' },
  { value: 'user', label: '个人' },
  { value: 'app', label: '应用' },
];

const DAY_OPTIONS = [
  { value: 7, label: '近 7 天' },
  { value: 14, label: '近 14 天' },
  { value: 30, label: '近 30 天' },
];

const fmt = (n) => (n ?? 0).toLocaleString('zh-CN');

function limitText(limits) {
  if (!limits) return '不限';
  const parts = [];
  if (limits.tokens) parts.push(`${fmt(limits.tokens)} token`);
  if (limits.calls) parts.push(`${fmt(limits.calls)} 次`);
  return parts.length ? parts.join(' / ') : '不限';
}

function StateTag({ state, percent }) {
  const tag = STATE_TAGS[state] || STATE_TAGS.ok;
  return (
    <Tag color={tag.color}>
      {tag.label}
      {percent != null ? ` ${percent}%` : ''}
    </Tag>
  );
}

function errorText(error, fallback) {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  const first = Object.values(data).flat().find((v) => typeof v === 'string');
  return first || fallback;
}

function policyTarget(policy) {
  if (policy.scope === 'default') return '所有人（未单独设置的用户）';
  if (policy.scope === 'group') return policy.group_name;
  if (policy.scope === 'user') return policy.user_display;
  return policy.app_label;
}

/** 新增 / 编辑上限配置的弹窗。 */
function PolicyModal({ open, policy, groups, appChoices, onCancel, onSaved }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [userOptions, setUserOptions] = useState([]);
  const scope = Form.useWatch('scope', form);
  const editing = Boolean(policy);
  const isDefault = policy?.scope === 'default';

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    if (policy) {
      form.setFieldsValue({
        scope: policy.scope,
        group: policy.group,
        user: policy.user,
        app_name: policy.app_name,
        daily_token_limit: policy.daily_token_limit,
        daily_call_limit: policy.daily_call_limit,
        soft_limit_percent: policy.soft_limit_percent,
        note: policy.note,
      });
    } else {
      form.setFieldsValue({ scope: 'group', daily_token_limit: 0, daily_call_limit: 0 });
    }
  }, [open, policy, form]);

  const searchUsers = async (q) => {
    try {
      const { data } = await searchBudgetUsers(q);
      setUserOptions((data || []).map((u) => ({ value: u.id, label: u.label })));
    } catch (error) {
      logger.warn('搜索用户失败:', error);
    }
  };

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        const payload = {
          daily_token_limit: values.daily_token_limit ?? 0,
          daily_call_limit: values.daily_call_limit ?? 0,
          note: values.note || '',
        };
        if (isDefault) payload.soft_limit_percent = values.soft_limit_percent;
        await updateBudgetPolicy(policy.id, payload);
      } else {
        await createBudgetPolicy({
          ...values,
          daily_token_limit: values.daily_token_limit ?? 0,
          daily_call_limit: values.daily_call_limit ?? 0,
          note: values.note || '',
        });
      }
      message.success('已保存');
      onSaved();
    } catch (error) {
      message.error(errorText(error, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  const userInitial = policy?.user ? [{ value: policy.user, label: policy.user_display }] : [];

  return (
    <Modal
      open={open}
      title={editing ? `修改上限：${policy.scope_display} · ${policyTarget(policy)}` : '新增上限'}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      onOk={submit}
      onCancel={onCancel}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        {!editing && (
          <>
            <Form.Item name="scope" label="作用范围" rules={[{ required: true }]}>
              <Segmented options={SCOPE_OPTIONS} />
            </Form.Item>
            {scope === 'group' && (
              <Form.Item name="group" label="用户组" rules={[{ required: true, message: '请选择用户组' }]}>
                <Select
                  placeholder="选择用户组"
                  options={groups.map((g) => ({ value: g.id, label: g.name }))}
                  showSearch
                  optionFilterProp="label"
                />
              </Form.Item>
            )}
            {scope === 'user' && (
              <Form.Item name="user" label="用户" rules={[{ required: true, message: '请选择用户' }]}>
                <Select
                  placeholder="输入用户名或姓名搜索"
                  showSearch
                  filterOption={false}
                  onSearch={searchUsers}
                  onFocus={() => searchUsers('')}
                  options={userOptions.length ? userOptions : userInitial}
                />
              </Form.Item>
            )}
            {scope === 'app' && (
              <Form.Item name="app_name" label="应用" rules={[{ required: true, message: '请选择应用' }]}>
                <Select placeholder="选择应用" options={appChoices} />
              </Form.Item>
            )}
          </>
        )}
        <Form.Item name="daily_token_limit" label="每日 token 上限" extra="0 表示不限">
          <InputNumber min={0} step={10000} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="daily_call_limit" label="每日调用次数上限" extra="0 表示不限；一次对话通常包含多次调用">
          <InputNumber min={0} step={50} style={{ width: '100%' }} />
        </Form.Item>
        {isDefault && (
          <Form.Item
            name="soft_limit_percent"
            label="只读阈值（%）"
            extra="对所有上限生效：用量达到该比例后暂停写操作、多步任务和办公文档生成"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
        )}
        <Form.Item name="note" label="备注">
          <Input maxLength={200} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

/**
 * 控制台「AI 管理 → 预算与用量」（方案 5.6）。
 *
 * 所有 LLM 调用按用户 / 应用 / 数字员工每日计量。默认只统计不限制；管理员可设全员默认、
 * 用户组、个人与应用的每日上限。到只读阈值暂停写操作、多步任务和办公文档生成，到上限当天停用 AI。
 */
const AiBudgetPage = () => {
  const [days, setDays] = useState(7);
  const [usage, setUsage] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null 关闭;{} 新增;policy 编辑

  const load = useCallback(async (range) => {
    try {
      const [usageResp, policyResp] = await Promise.all([getBudgetUsage(range), listBudgetPolicies()]);
      setUsage(usageResp.data);
      setPolicies(Array.isArray(policyResp.data) ? policyResp.data : []);
    } catch (error) {
      message.error('加载预算与用量失败');
      logger.error('加载预算与用量失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(days);
  }, [load, days]);

  const refresh = () => {
    setLoading(true);
    load(days);
  };

  const changeDays = (value) => {
    setLoading(true);
    setDays(value);
  };

  const remove = async (policy) => {
    try {
      await deleteBudgetPolicy(policy.id);
      message.success('已删除');
      refresh();
    } catch (error) {
      message.error(errorText(error, '删除失败'));
    }
  };

  const totals = usage?.totals;
  const maxDaily = useMemo(() => Math.max(1, ...(usage?.daily || []).map((d) => d.tokens)), [usage]);

  const appColumns = [
    { title: '应用', dataIndex: 'app_label', key: 'app' },
    { title: 'token', dataIndex: 'tokens', key: 'tokens', render: fmt },
    { title: '调用', dataIndex: 'calls', key: 'calls', render: fmt },
    { title: '失败', dataIndex: 'failed_calls', key: 'failed', render: fmt },
    { title: '每日上限', key: 'limits', render: (_, r) => limitText(r.limits) },
    { title: '状态', key: 'state', render: (_, r) => <StateTag state={r.state} percent={r.percent} /> },
  ];
  const dailyColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: 'token',
      dataIndex: 'tokens',
      key: 'tokens',
      render: (value) => (
        <Space>
          <span
            aria-hidden
            style={{
              display: 'inline-block',
              height: 8,
              width: Math.round((value / maxDaily) * 160),
              background: '#1677ff',
              borderRadius: 4,
            }}
          />
          {fmt(value)}
        </Space>
      ),
    },
    { title: '调用', dataIndex: 'calls', key: 'calls', render: fmt },
    { title: '估算调用', dataIndex: 'estimated_calls', key: 'estimated', render: fmt },
  ];
  const userColumns = [
    { title: '用户', dataIndex: 'user_display', key: 'user' },
    { title: 'token', key: 'tokens', render: (_, r) => fmt(r.usage?.tokens) },
    { title: '调用', key: 'calls', render: (_, r) => fmt(r.usage?.calls) },
    { title: '每日上限', key: 'limits', render: (_, r) => limitText(r.limits) },
    { title: '上限来源', key: 'source', render: (_, r) => r.limits?.source || '—' },
    { title: '状态', key: 'state', render: (_, r) => <StateTag state={r.state} percent={r.percent} /> },
  ];
  const staffColumns = [
    { title: '数字员工', dataIndex: 'name', key: 'name' },
    { title: 'token', dataIndex: 'tokens', key: 'tokens', render: fmt },
    { title: '调用', dataIndex: 'calls', key: 'calls', render: fmt },
  ];
  const policyColumns = [
    { title: '范围', dataIndex: 'scope_display', key: 'scope' },
    { title: '对象', key: 'target', render: (_, r) => policyTarget(r) },
    { title: '每日 token 上限', dataIndex: 'daily_token_limit', key: 'tokens', render: (v) => (v ? fmt(v) : '不限') },
    { title: '每日调用上限', dataIndex: 'daily_call_limit', key: 'calls', render: (v) => (v ? fmt(v) : '不限') },
    {
      title: '只读阈值',
      key: 'soft',
      render: (_, r) => (r.scope === 'default' ? `${r.soft_limit_percent}%` : '同全员默认'),
    },
    { title: '备注', dataIndex: 'note', key: 'note', render: (v) => v || '—' },
    { title: '修改人', dataIndex: 'updated_by_name', key: 'by', render: (v) => v || '—' },
    {
      title: '操作',
      key: 'actions',
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => setEditing(r)}>
            修改
          </Button>
          {r.scope !== 'default' && (
            <Popconfirm title="删除后按上一级上限执行，确定删除？" okText="删除" cancelText="取消" onConfirm={() => remove(r)}>
              <Button size="small" danger>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', marginBottom: 8 }}>
        <Title level={4} style={{ margin: 0 }}>
          <FundOutlined /> 预算与用量
        </Title>
        <Space>
          <Segmented options={DAY_OPTIONS} value={days} onChange={changeDays} />
          <Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
            刷新
          </Button>
        </Space>
      </Space>
      <Paragraph type="secondary">
        所有 AI 调用按用户、应用和数字员工每日计量（0 点重置）。用量达到只读阈值后，写操作、多步任务和办公文档生成暂停，
        普通查询照常；达到上限后当天停用 AI，页面其他功能不受影响。用户上限按「个人 → 用户组（多个组取最宽松）→
        全员默认」确定，应用上限对所有人（含数字员工）合计生效。数字员工的调用次数在「数字员工」页单独设置。
      </Paragraph>

      {usage && !usage.has_limits && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前只统计、不限制"
          description="所有上限都是 0（不限）。建议先观察一段时间的实际用量，再在下方「上限配置」里设置。"
        />
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="今日 token" value={totals?.tokens ?? 0} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="今日调用次数" value={totals?.calls ?? 0} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="今日预估费用（元）" value={totals?.cost ?? 0} precision={2} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="按字数估算的调用占比"
              value={Math.round((totals?.estimated_ratio ?? 0) * 100)}
              suffix="%"
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              端点未返回用量时按字数估算
            </Text>
          </Card>
        </Col>
      </Row>

      <Card title="今日按应用" size="small" style={{ marginBottom: 16 }}>
        <Table rowKey="app_name" size="small" pagination={false} loading={loading} columns={appColumns} dataSource={usage?.apps || []} />
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title={`近 ${usage?.days ?? days} 天趋势`} size="small" style={{ marginBottom: 16 }}>
            <Table rowKey="date" size="small" pagination={false} columns={dailyColumns} dataSource={usage?.daily || []} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="今日数字员工" size="small" style={{ marginBottom: 16 }}>
            {usage?.staff?.length ? (
              <Table rowKey="staff_key" size="small" pagination={false} columns={staffColumns} dataSource={usage.staff} />
            ) : (
              <Empty description="今天数字员工还没有调用 AI" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="今日用户排行（前 20）" size="small" style={{ marginBottom: 16 }}>
        {usage?.top_users?.length ? (
          <Table rowKey="user_id" size="small" pagination={false} columns={userColumns} dataSource={usage.top_users} />
        ) : (
          <Empty description="今天还没有用户调用 AI" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card
        title="上限配置"
        size="small"
        extra={
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setEditing({})}>
            新增上限
          </Button>
        }
      >
        <Table rowKey="id" size="small" pagination={false} columns={policyColumns} dataSource={policies} />
      </Card>

      <PolicyModal
        open={editing !== null}
        policy={editing && editing.id ? editing : null}
        groups={usage?.groups || []}
        appChoices={usage?.app_choices || []}
        onCancel={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          refresh();
        }}
      />
    </div>
  );
};

export default AiBudgetPage;
