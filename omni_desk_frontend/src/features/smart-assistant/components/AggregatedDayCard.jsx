import React, { useMemo } from 'react';
import { Card, Tag, Typography, Empty, Skeleton, Alert, List, Space } from 'antd';

const { Text, Title } = Typography;

/**
 * AggregatedDayCard - 跨模块汇总查询结果聚合卡片
 *
 * 接收 ResultSynthesizer 输出:
 * - items: 按 sort_key 排序后的所有项
 * - moduleCounts: {模块名: 数量}
 * - summary: 人类可读汇总文本
 *
 * 按模块自动分组渲染,使用 Ant Design Card + Tag
 */
const AggregatedDayCard = ({ items = [], moduleCounts = {}, summary = '', isLoading, error }) => {
  if (isLoading) {
    return <Card><Skeleton active /></Card>;
  }

  if (error) {
    return <Alert type="error" message={error} />;
  }

  if (!items.length) {
    return (
      <Card>
        <Empty description={summary || '未找到相关信息'} />
      </Card>
    );
  }

  const grouped = useMemo(() => {
    const map = {};
    for (const item of items) {
      if (!map[item.module]) map[item.module] = [];
      map[item.module].push(item);
    }
    return map;
  }, [items]);

  return (
    <Card
      data-testid="aggregated-day-card"
      title={<Title level={5}>{summary}</Title>}
      extra={
        <Space>
          {Object.entries(moduleCounts).map(([mod, n]) => (
            <Tag key={mod} color="blue">{mod} {n}</Tag>
          ))}
        </Space>
      }
    >
      {Object.entries(grouped).map(([module, moduleItems]) => (
        <div key={module} data-testid="module-group" style={{ marginBottom: 16 }}>
          <Text strong>{module}</Text>
          <List
            size="small"
            dataSource={moduleItems}
            renderItem={(item) => (
              <List.Item>
                <Text type="secondary" style={{ marginRight: 8 }}>
                  {item.sort_key !== '9999' ? item.sort_key : ''}
                </Text>
                <Text>{JSON.stringify(item.data)}</Text>
              </List.Item>
            )}
          />
        </div>
      ))}
    </Card>
  );
};

export default AggregatedDayCard;