import { Card, Tag, Typography, Button } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

const STATUS_MAP = {
  approved: { color: 'green', text: '已批准' },
  draft: { color: 'default', text: '草稿' },
  pending_review: { color: 'orange', text: '待审核' },
  disabled: { color: 'gray', text: '已禁用' },
};

const PluginCard = ({ plugin, onDetail, onExecute }) => {
  const status = STATUS_MAP[plugin.status] || STATUS_MAP.draft;
  const activeVersion = plugin.versions?.find((v) => v.is_active);

  return (
    <Card
      hoverable
      title={
        <span>
          {plugin.icon || '📦'} {plugin.name}
        </span>
      }
      extra={<Tag color={status.color}>{status.text}</Tag>}
      style={{ height: '100%' }}
    >
      <Text type="secondary">{plugin.description || '暂无描述'}</Text>
      {activeVersion && (
        <div style={{ marginTop: 8 }}>
          <Tag>版本 {activeVersion.version}</Tag>
        </div>
      )}
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <Button size="small" onClick={() => onDetail(plugin)}>
          详情
        </Button>
        <Button
          size="small"
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={() => onExecute(plugin)}
          disabled={plugin.status !== 'approved'}
        >
          执行
        </Button>
      </div>
    </Card>
  );
};

export default PluginCard;
