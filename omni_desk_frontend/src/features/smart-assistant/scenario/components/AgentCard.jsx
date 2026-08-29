// 单个智能体卡片：用于 thinking / final_answer 步骤
import { Avatar, Card, Tag, Typography } from 'antd';
import { getAgent, getAgentIcon } from '../data/agents';

const { Text } = Typography;

/**
 * @param {{
 *   agent: string,
 *   content?: string,
 *   payload?: Record<string, unknown>,
 *   variant?: 'thinking' | 'final'
 * }} props
 */
export default function AgentCard({ agent, content, payload, variant = 'thinking' }) {
  const meta = getAgent(agent);
  const Icon = getAgentIcon(agent);
  const color = meta?.avatarColor || '#1677ff';
  return (
    <div className="agent-card" data-variant={variant}>
      <Avatar
        size={36}
        style={{ backgroundColor: color, flexShrink: 0 }}
        icon={<Icon />}
      />
      <div className="agent-card-body">
        <div className="agent-card-header">
          <Text strong>{meta?.name || agent}</Text>
          <Tag color={color} bordered={false} style={{ marginLeft: 8 }}>
            {meta?.role || '智能体'}
          </Tag>
          <Tag bordered={false} color={variant === 'final' ? 'gold' : 'default'}>
            {variant === 'final' ? '最终答复' : '思考'}
          </Tag>
        </div>
        {content && <div className="agent-card-content">{content}</div>}
        {payload && (
          <Card size="small" className="agent-card-payload" styles={{ body: { padding: 12 } }}>
            {Object.entries(payload).map(([k, v]) => (
              <div key={k} className="agent-card-payload-row">
                <Text type="secondary" style={{ marginRight: 8 }}>{k}:</Text>
                <span>{typeof v === 'string' ? v : JSON.stringify(v)}</span>
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}
