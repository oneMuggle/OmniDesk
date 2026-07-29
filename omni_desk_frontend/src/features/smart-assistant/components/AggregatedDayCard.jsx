import { useMemo } from 'react';
import { Card, Tag, Typography, Empty, Skeleton, Alert, List, Space } from 'antd';
import PropTypes from 'prop-types';

const { Text, Title } = Typography;

/**
 * AggregatedDayCard - 跨模块汇总查询结果聚合卡片
 *
 * 接收 ResultSynthesizer 输出(扁平结构):
 * - items: 按 sort_key 排序后的所有项
 * - moduleCounts: {模块名: 数量}
 * - summary: 人类可读汇总文本
 *
 * 按模块自动分组渲染,使用 Ant Design Card + Tag
 */
const AggregatedDayCard = ({ items = [], moduleCounts = {}, summary = '', isLoading, error }) => {
  // 注意:useMemo 必须无条件调用(rules of hooks),先于任何 early return
  const grouped = useMemo(() => {
    const map = {};
    for (const item of items) {
      if (!map[item.module]) map[item.module] = [];
      map[item.module].push(item);
    }
    return map;
  }, [items]);

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

AggregatedDayCard.propTypes = {
  items: PropTypes.arrayOf(PropTypes.shape({
    type: PropTypes.string,
    module: PropTypes.string,
    data: PropTypes.object,
    sort_key: PropTypes.string,
  })),
  moduleCounts: PropTypes.object,
  summary: PropTypes.string,
  isLoading: PropTypes.bool,
  error: PropTypes.string,
};

export default AggregatedDayCard;
