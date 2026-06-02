import { useState } from 'react';
import { Card, Row, Col, Input, Select, Tag, Button, message, Empty, Spin } from 'antd';
import { SearchOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { fetchPlugins, executePlugin } from '../api/pluginApi';
import PluginDetailModal from '../components/PluginDetailModal';
import { logger } from '../../shared/utils/logger';

const { Search } = Input;

const STATUS_MAP = {
  approved: { color: 'green', text: '已批准' },
  draft: { color: 'default', text: '草稿' },
  pending_review: { color: 'orange', text: '待审核' },
  rejected: { color: 'red', text: '已拒绝' },
  disabled: { color: 'gray', text: '已禁用' },
};

const CATEGORY_OPTIONS = [
  { value: '', label: '全部分类' },
  { value: '数据处理', label: '数据处理' },
  { value: '计算分析', label: '计算分析' },
  { value: '文件转换', label: '文件转换' },
  { value: '自动化脚本', label: '自动化脚本' },
  { value: '其他', label: '其他' },
];

export default function PluginMarketPage() {
  const [searchText, setSearchText] = useState('');
  const [category, setCategory] = useState('');
  const [selectedPlugin, setSelectedPlugin] = useState(null);
  const [detailVisible, setDetailVisible] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['plugins', searchText, category],
    queryFn: () => fetchPlugins({ search: searchText, category }),
  });

  const handleExecute = async (pluginId) => {
    try {
      const result = await executePlugin(pluginId);
      message.success('插件执行成功');
      logger.debug('Plugin result:', result);
    } catch (error) {
      message.error('插件执行失败');
    }
  };

  const handleCardClick = (plugin) => {
    setSelectedPlugin(plugin);
    setDetailVisible(true);
  };

  const plugins = data?.results || data || [];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 24 }}>插件市场</h2>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Search
            placeholder="搜索插件名称或描述"
            prefix={<SearchOutlined />}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
        </Col>
        <Col span={6}>
          <Select
            style={{ width: '100%' }}
            options={CATEGORY_OPTIONS}
            value={category}
            onChange={setCategory}
          />
        </Col>
      </Row>

      <Spin spinning={isLoading}>
        {plugins.length === 0 ? (
          <Empty description="暂无插件" />
        ) : (
          <Row gutter={[16, 16]}>
            {plugins.map((plugin) => {
              const status = STATUS_MAP[plugin.status] || STATUS_MAP.draft;
              return (
                <Col key={plugin.id} xs={24} sm={12} md={8} lg={6}>
                  <Card
                    hoverable
                    onClick={() => handleCardClick(plugin)}
                    cover={
                      plugin.icon ? (
                        <div style={{ height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48 }}>
                          {plugin.icon}
                        </div>
                      ) : null
                    }
                    extra={
                      <Button
                        type="link"
                        icon={<PlayCircleOutlined />}
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExecute(plugin.id);
                        }}
                      />
                    }
                  >
                    <Card.Meta
                      title={
                        <span>
                          {plugin.name}
                          <Tag color={status.color} style={{ marginLeft: 8 }}>
                            {status.text}
                          </Tag>
                        </span>
                      }
                      description={plugin.description?.slice(0, 60) || '暂无描述'}
                    />
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Spin>

      <PluginDetailModal
        visible={detailVisible}
        plugin={selectedPlugin}
        onClose={() => {
          setDetailVisible(false);
          setSelectedPlugin(null);
        }}
      />
    </div>
  );
}
