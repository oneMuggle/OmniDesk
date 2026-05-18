import { useState, useEffect } from 'react';
import { Card, Statistic, Row, Col, Table, Spin } from 'antd';
import { getStatsOverview, getStatsDaily } from '../api/smartAssistantApi';
import './StatsPage.css';

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
    { title: '问题', dataIndex: 'user_query', key: 'user_query', ellipsis: true },
    { title: '次数', dataIndex: 'count', key: 'count', width: 80, sorter: (a, b) => a.count - b.count },
  ];

  const dailyColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '对话数', dataIndex: 'conversations', key: 'conversations', width: 100 },
    { title: '工具调用', dataIndex: 'tool_calls', key: 'tool_calls', width: 100 },
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

          <Row gutter={16}>
            <Col span={12}>
              <Card title="意图分布" size="small">
                <Table
                  columns={intentColumns}
                  dataSource={intentData}
                  size="small"
                  pagination={false}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="工具调用" size="small">
                <Table
                  columns={toolColumns}
                  dataSource={toolData}
                  size="small"
                  pagination={false}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={12}>
              <Card title="热门问题 Top 10" size="small">
                <Table
                  columns={questionColumns}
                  dataSource={overview?.top_questions || []}
                  size="small"
                  pagination={false}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="每日趋势" size="small">
                <Table
                  columns={dailyColumns}
                  dataSource={dailyStats}
                  size="small"
                  pagination={false}
                  scroll={{ y: 300 }}
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
