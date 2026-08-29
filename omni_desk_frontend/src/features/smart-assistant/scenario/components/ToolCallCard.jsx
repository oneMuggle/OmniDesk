// 工具调用卡片：展示 tool_call + tool_result
import { Avatar, Card, Empty, Tag, Typography, theme } from 'antd';
import {
  ApiOutlined,
} from '@ant-design/icons';
import { getAgent, getAgentIcon } from '../data/agents';
import { getTool, getToolIcon } from '../data/tools';

const { Text } = Typography;
const { useToken } = theme;

/**
 * @param {{
 *   agent: string,
 *   tool: string,
 *   input?: Record<string, unknown>,
 *   output?: unknown,
 * }} props
 */
export default function ToolCallCard({ agent, tool, input, output }) {
  const agentMeta = getAgent(agent);
  const toolMeta = getTool(tool);
  const AgentIcon = getAgentIcon(agent);
  const ToolIcon = getToolIcon(tool);
  const color = agentMeta?.avatarColor || '#1677ff';
  const { token } = useToken();

  return (
    <div className="tool-call-card" data-tool={tool}>
      <div className="tool-call-rail">
        <Avatar size={32} style={{ backgroundColor: color }} icon={<AgentIcon />} />
        <div className="tool-call-rail-line" />
        <Avatar size={28} style={{ backgroundColor: token.colorPrimary }} icon={<ToolIcon />} />
      </div>
      <div className="tool-call-body">
        <div className="tool-call-header">
          <Tag color={color} bordered={false}>{agentMeta?.name || agent}</Tag>
          <ApiOutlined style={{ margin: '0 8px', color: token.colorTextTertiary }} />
          <Tag icon={<ToolIcon />} bordered={false} color="processing">{toolMeta?.name || tool}</Tag>
        </div>

        <Card size="small" className="tool-call-section" title="调用参数" styles={{ body: { padding: 12 } }}>
          {input && Object.keys(input).length > 0 ? (
            <pre className="tool-call-json">{JSON.stringify(input, null, 2)}</pre>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无参数" />
          )}
        </Card>

        <Card size="small" className="tool-call-section" title="返回结果" styles={{ body: { padding: 12 } }}>
          {output ? <ToolResultView output={output} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="等待返回…" />}
        </Card>
      </div>
    </div>
  );
}

function ToolResultView({ output }) {
  if (output === null || output === undefined) {
    return <Text type="secondary">—</Text>;
  }
  if (typeof output === 'string' || typeof output === 'number' || typeof output === 'boolean') {
    return <Text>{String(output)}</Text>;
  }
  if (Array.isArray(output)) {
    return (
      <div className="tool-call-list">
        {output.map((item, idx) => (
          <Card
            key={idx}
            size="small"
            style={{ marginBottom: 8 }}
            styles={{ body: { padding: 8 } }}
          >
            <pre className="tool-call-json">{JSON.stringify(item, null, 2)}</pre>
          </Card>
        ))}
      </div>
    );
  }
  if (typeof output === 'object') {
    const o = /** @type {Record<string, unknown>} */ (output);
    const entries = Object.entries(o);
    return (
      <div className="tool-call-object">
        {entries.map(([k, v]) => {
          if (Array.isArray(v)) {
            return (
              <div key={k} className="tool-call-object-row">
                <Text type="secondary" strong style={{ marginRight: 8 }}>{k}:</Text>
                <div className="tool-call-list">
                  {v.map((item, idx) => (
                    <pre key={idx} className="tool-call-json small">{JSON.stringify(item, null, 2)}</pre>
                  ))}
                </div>
              </div>
            );
          }
          return (
            <div key={k} className="tool-call-object-row">
              <Text type="secondary" strong style={{ marginRight: 8 }}>{k}:</Text>
              <span>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
            </div>
          );
        })}
      </div>
    );
  }
  return <Text>{String(output)}</Text>;
}
