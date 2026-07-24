import React, { useState } from 'react';
import { Card, Statistic, Row, Col, Input, Button, List, Typography, Space } from 'antd';
import { BarChartOutlined, SearchOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Text, Title } = Typography;

/**
 * AI 数据摘要与自然语言查询组件
 *
 * 展示 AI 分析结果（Sheet 数量、总行数、每列统计信息），
 * 并提供自然语言查询入口，支持 Ctrl+Enter 快捷键。
 *
 * @param {object}   props.summary  AI 分析摘要数据
 * @param {function} props.onQuery  查询回调，参数为问题文本，返回答案
 */
const AIAnalysisSection = ({ summary, onQuery }) => {
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);

  const handleQuery = async () => {
    if (!queryText.trim()) return;

    setQueryLoading(true);
    try {
      const answer = await onQuery(queryText);
      setQueryResult(answer);
    } catch (err) {
      console.error('Query failed:', err);
    } finally {
      setQueryLoading(false);
    }
  };

  return (
    <div className="ai-analysis-section">
      {/* 数据摘要 */}
      {summary && (
        <div style={{ marginBottom: 24 }}>
          <Title level={5}>
            <BarChartOutlined /> 数据摘要
          </Title>

          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="Sheet 数量" value={summary.sheet_count} />
            </Col>
            <Col span={8}>
              <Statistic title="总行数" value={summary.total_rows} />
            </Col>
          </Row>

          {/* 每个 Sheet 的详细统计 */}
          {summary.summaries && summary.summaries.map((sheetSummary, index) => (
            <Card
              key={index}
              size="small"
              title={sheetSummary.sheet_name}
              style={{ marginTop: 16 }}
            >
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic title="行数" value={sheetSummary.row_count} />
                </Col>
                <Col span={8}>
                  <Statistic title="列数" value={sheetSummary.column_count} />
                </Col>
              </Row>

              {/* 列统计 */}
              {sheetSummary.columns && (
                <div style={{ marginTop: 16 }}>
                  <Text strong>列详情：</Text>
                  <List
                    size="small"
                    dataSource={sheetSummary.columns}
                    renderItem={(col) => (
                      <List.Item>
                        <Text>{col.name}</Text>
                        <Text type="secondary">
                          ({col.type}, {col.null_count} 空值, {col.unique_count} 唯一值)
                        </Text>
                        {col.mean !== undefined && col.mean !== null && (
                          <Text type="secondary">
                            ，最小: {col.min?.toFixed(2)}, 最大: {col.max?.toFixed(2)}
                            ，平均: {col.mean.toFixed(2)}, 总和: {col.sum?.toFixed(2)}
                          </Text>
                        )}
                      </List.Item>
                    )}
                  />
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* 自然语言查询 */}
      <div>
        <Title level={5}>
          <SearchOutlined /> 自然语言查询
        </Title>

        <Space direction="vertical" style={{ width: '100%' }}>
          <TextArea
            rows={3}
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder="输入您的问题，例如：哪个月份的销售额最高？"
            onPressEnter={(e) => e.ctrlKey && handleQuery()}
          />

          <Button
            type="primary"
            icon={<SearchOutlined />}
            loading={queryLoading}
            onClick={handleQuery}
          >
            查询 (Ctrl+Enter)
          </Button>

          {queryResult && (
            <Card size="small" title="查询结果">
              <Text>{queryResult}</Text>
            </Card>
          )}
        </Space>
      </div>
    </div>
  );
};

export default AIAnalysisSection;
