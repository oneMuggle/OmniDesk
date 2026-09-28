import { useState, useEffect } from 'react';
import { Card, Statistic, Row, Col, Spin } from 'antd';
import { getStatsOverview, getStatsDaily } from '../api/smartAssistantApi';
import './StatsPage.css';
import DataTable from '../../../shared/components/DataTable';

// 比例为空（窗口内没有数据）时显示「—」，不显示 0%
const formatRate = (value) => (value === null || value === undefined ? '—' : `${value}%`);

const StatsPage = () => {
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState(null);
  const [dailyStats, setDailyStats] = useState([]);
  const [days, setDays] = useState(30);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [overviewRes, dailyRes] = await Promise.all([
          getStatsOverview(days),
          getStatsDaily(days),
        ]);
        setOverview(overviewRes.data);
        setDailyStats(dailyRes.data.daily_stats || []);
      } catch {
        // 静默失败
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [days]);

  const intentColumns = [
    { title: '意图', dataIndex: 'key', key: 'key' },
    { title: '次数', dataIndex: 'count', key: 'count', sorter: (a, b) => a.count - b.count },
  ];

  const toolColumns = [
    { title: '工具', dataIndex: 'key', key: 'key' },
    { title: '调用次数', dataIndex: 'count', key: 'count', sorter: (a, b) => a.count - b.count },
  ];

  const questionColumns = [
    { title: '热门意图', dataIndex: 'intent', key: 'intent' },
    { title: '次数', dataIndex: 'count', key: 'count', width: 80, sorter: (a, b) => a.count - b.count },
  ];

  const dailyColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '对话数', dataIndex: 'conversations', key: 'conversations', width: 90 },
    { title: '工具调用', dataIndex: 'tool_calls', key: 'tool_calls', width: 90 },
    {
      title: '回答成功率',
      dataIndex: 'answer_success_rate',
      key: 'answer_success_rate',
      width: 100,
      render: formatRate,
    },
    {
      title: 'P95',
      dataIndex: 'p95_response_time_ms',
      key: 'p95_response_time_ms',
      width: 90,
      render: (value) => `${value || 0} ms`,
    },
  ];

  const modelColumns = [
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: '对话数', dataIndex: 'conversations', key: 'conversations', width: 90 },
    {
      title: '回答成功率',
      dataIndex: 'answer_success_rate',
      key: 'answer_success_rate',
      width: 110,
      render: formatRate,
    },
    {
      title: '平均响应',
      dataIndex: 'avg_response_time_ms',
      key: 'avg_response_time_ms',
      width: 100,
      render: (value) => `${value || 0} ms`,
    },
    {
      title: 'P95',
      dataIndex: 'p95_response_time_ms',
      key: 'p95_response_time_ms',
      width: 90,
      render: (value) => `${value || 0} ms`,
    },
    { title: 'Token', dataIndex: 'total_tokens', key: 'total_tokens', width: 100 },
  ];

  const intentData = overview?.intent_breakdown
    ? Object.entries(overview.intent_breakdown).map(([key, count]) => ({ key, count }))
    : [];

  const toolData = overview?.tool_breakdown
    ? Object.entries(overview.tool_breakdown).map(([key, count]) => ({ key, count }))
    : [];

  return (
    <div className="stats-page">
      <h2>智能助手统计</h2>
      <div className="stats-filters">
        <label>时间范围：</label>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>近 7 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      </div>

      {loading ? (
        <Spin size="large" />
      ) : (
        <>
          <Row gutter={16} className="stats-summary-row">
            <Col span={6}>
              <Card>
                <Statistic title="对话总数" value={overview?.total_conversations || 0} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="活跃用户" value={overview?.active_users || 0} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="未识别问题" value={overview?.unrecognized || 0} valueStyle={{ color: '#ff4d4f' }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="统计天数" value={overview?.period_days || days} suffix="天" />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} className="stats-summary-row">
            <Col span={6}>
              <Card>
                <Statistic
                  title="回答成功率"
                  value={formatRate(overview?.answer_success_rate)}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="LLM 调用成功率"
                  value={formatRate(overview?.llm_call_success_rate)}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="响应时间 P50" value={overview?.p50_response_time_ms || 0} suffix="ms" />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="响应时间 P95" value={overview?.p95_response_time_ms || 0} suffix="ms" />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} className="stats-summary-row">
            <Col span={24}>
              <Card title="按模型" size="small">
                <DataTable
                  columns={modelColumns}
                  dataSource={overview?.by_model || []}
                  rowKey="model"
                  size="small"
                  pagination={false}
                  showActions={false}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="意图分布" size="small">
                <DataTable
                  columns={intentColumns}
                  dataSource={intentData}
                  size="small"
                  pagination={false}                  showActions={false}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="工具调用" size="small">
                <DataTable
                  columns={toolColumns}
                  dataSource={toolData}
                  size="small"
                  pagination={false}                  showActions={false}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={12}>
              <Card title="热门问题 Top 10" size="small">
                <DataTable
                  columns={questionColumns}
                  dataSource={overview?.top_questions || []}
                  size="small"
                  pagination={false}                  showActions={false}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="每日趋势" size="small">
                <DataTable
                  columns={dailyColumns}
                  dataSource={dailyStats}
                  size="small"
                  pagination={false}
                  scroll={{ y: 300 }}                  showActions={false}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
};

export default StatsPage;
