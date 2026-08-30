// 工具调用卡片：展示 tool_call + tool_result
import { createElement } from 'react';
import { Avatar, Card, Empty, Tag, Typography, theme } from 'antd';
import {
  ApiOutlined,
} from '@ant-design/icons';
import { getAgent, getAgentIcon } from '../data/agents';
import { getTool, getToolIcon } from '../data/tools';

const { Text } = Typography;
const SENSITIVE_KEYS = /token|password|secret|credential|authorization|cookie|prompt|args|argument|api[_-]?key|access[_-]?key|private[_-]?key|session/i;
const MAX_DISPLAY_LENGTH = 2000;

function safeDisplay(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value !== 'object') return String(value).slice(0, MAX_DISPLAY_LENGTH);
  if (Array.isArray(value)) return `${value.length} 项结果`;
  return Object.keys(value).filter((key) => !SENSITIVE_KEYS.test(key)).slice(0, 20).map((key) => `${key}: ${safeDisplay(value[key])}`).join('\n').slice(0, MAX_DISPLAY_LENGTH);
}

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
        <Avatar size={32} style={{ backgroundColor: color }} icon={createElement(AgentIcon)} />
        <div className="tool-call-rail-line" />
        <Avatar size={28} style={{ backgroundColor: token.colorPrimary }} icon={createElement(ToolIcon)} />
      </div>
      <div className="tool-call-body">
        <div className="tool-call-header">
          <Tag color={color} bordered={false}>{agentMeta?.name || agent}</Tag>
          <ApiOutlined style={{ margin: '0 8px', color: token.colorTextTertiary }} />
          <Tag icon={createElement(ToolIcon)} bordered={false} color="processing">{toolMeta?.name || tool}</Tag>
        </div>

        <Card size="small" className="tool-call-section" title="调用参数" styles={{ body: { padding: 12 } }}>
          {input && Object.keys(input).length > 0 ? (
            <Text className="tool-call-json">{safeDisplay(input)}</Text>
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
  if (typeof output !== 'object') {
    return <Text>{safeDisplay(output)}</Text>;
  }
  if (Array.isArray(output)) {
    return (
      <div className="tool-call-list">
        {output.slice(0, 20).map((item, index) => (
          <Card key={index} size="small" style={{ marginBottom: 8 }} styles={{ body: { padding: 8 } }}>
            <Text className="tool-call-json">{safeDisplay(item)}</Text>
          </Card>
        ))}
      </div>
    );
  }
  return (
    <div className="tool-call-object">
      {Object.keys(output).filter((key) => !SENSITIVE_KEYS.test(key)).slice(0, 20).map((key) => (
        <div key={key} className="tool-call-object-row">
          <Text type="secondary" strong style={{ marginRight: 8 }}>{key}:</Text>
          <span>{safeDisplay(output[key])}</span>
        </div>
      ))}
    </div>
  );
}
