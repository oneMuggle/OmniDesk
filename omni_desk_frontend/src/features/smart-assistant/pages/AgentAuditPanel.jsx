import { useState, useEffect } from 'react';
import { Card, Table, Tag, Button, Space, Modal, Descriptions, Input, DatePicker, Select } from 'antd';
import { EyeOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import apiClient from '../../../shared/api/apiClient';
import './AgentAuditPanel.css';

const { RangePicker } = DatePicker;
const { Search } = Input;

const INTENT_OPTIONS = [
  { label: '排班查询', value: 'schedule_query' },
  { label: '人员查询', value: 'personnel_query' },
  { label: '知识库问答', value: 'knowledge_qa' },
  { label: '通用对话', value: 'general_chat' },
];

const AgentAuditPanel = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedLog, setSelectedLog] = useState(null);
  const [filters, setFilters] = useState({
    keyword: '',
    intent: undefined,
    dateRange: null,
  });

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page, page_size: 20 });
      if (filters.keyword) params.set('keyword', filters.keyword);
      if (filters.intent) params.set('intent', filters.intent);
      if (filters.dateRange) {
        params.set('start_time', filters.dateRange[0].format('YYYY-MM-DD'));
        params.set('end_time', filters.dateRange[1].format('YYYY-MM-DD'));
      }
      const response = await apiClient.get(`/smart-assistant/agent-logs/?${params}`);
      setLogs(response.data.results || response.data || []);
      setTotal(response.data.count || 0);
    } catch {
      // 静默失败
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page]);

  const handleSearch = () => {
    setPage(1);
    fetchLogs();
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val) => val ? new Date(val).toLocaleString('zh-CN') : '-',
    },
    {
      title: '用户问题',
      dataIndex: 'user_query',
      key: 'user_query',
      ellipsis: true,
    },
    {
      title: '意图',
      dataIndex: 'intent',
      key: 'intent',
      width: 120,
      render: (intent) => {
        const labels = {
          schedule_query: '排班查询',
          personnel_query: '人员查询',
          knowledge_qa: '知识库问答',
          general_chat: '通用对话',
        };
        return <Tag color="blue">{labels[intent] || intent}</Tag>;
      },
    },
    {
      title: '工具',
      dataIndex: 'tool_used',
      key: 'tool_used',
      width: 120,
      render: (tool) => tool ? <Tag color="green">{tool}</Tag> : <Tag>无</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_, record) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          size="small"
          onClick={() => setSelectedLog(record)}
        >
          详情
        </Button>
      ),
    },
  ];

  return (
    <div className="agent-audit-panel">
      <h3>Agent 审计面板</h3>
      <Card className="audit-filters">
        <Space wrap>
          <Search
            placeholder="搜索问题或回答"
            value={filters.keyword}
            onChange={(e) => setFilters(f => ({ ...f, keyword: e.target.value }))}
            onSearch={handleSearch}
            style={{ width: 240 }}
          />
          <Select
            placeholder="意图类型"
            allowClear
            value={filters.intent}
            onChange={(val) => setFilters(f => ({ ...f, intent: val }))}
            style={{ width: 160 }}
            options={INTENT_OPTIONS}
          />
          <RangePicker
            value={filters.dateRange}
            onChange={(dates) => setFilters(f => ({ ...f, dateRange: dates }))}
          />
          <Button icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchLogs} loading={loading}>
            刷新
          </Button>
        </Space>
      </Card>
      <Card className="audit-table">
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize: 20,
            total,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 条`,
          }}
          locale={{ emptyText: '暂无审计记录' }}
        />
      </Card>

      <Modal
        title="日志详情"
        open={!!selectedLog}
        onCancel={() => setSelectedLog(null)}
        footer={null}
        width={700}
      >
        {selectedLog && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="时间">
              {new Date(selectedLog.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="用户问题">
              {selectedLog.user_query}
            </Descriptions.Item>
            <Descriptions.Item label="意图">{selectedLog.intent}</Descriptions.Item>
            <Descriptions.Item label="使用工具">{selectedLog.tool_used || '无'}</Descriptions.Item>
            <Descriptions.Item label="工具输入">
              <pre>{JSON.stringify(selectedLog.tool_input, null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="工具输出">
              <pre>{JSON.stringify(selectedLog.tool_output, null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="LLM 回答">
              {selectedLog.llm_response}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default AgentAuditPanel;
