// 审计时间线：右侧栏
// 把播放器 events 序列化为可追溯的审计日志
import { Empty, Tag, Timeline, Tooltip, Typography, theme } from 'antd';
import {
  BulbOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';
import { getAgent } from '../data/agents';
import { getTool } from '../data/tools';
import dayjs from 'dayjs';

const { Text } = Typography;
const { useToken } = theme;

const TYPE_META = {
  thinking: { color: 'blue', icon: BulbOutlined, label: '思考' },
  tool_call: { color: 'orange', icon: ApiOutlined, label: '调用工具' },
  tool_result: { color: 'cyan', icon: FileSearchOutlined, label: '工具返回' },
  final_answer: { color: 'green', icon: CheckCircleOutlined, label: '最终答复' },
};

/**
 * @param {{
 *   events: Array<{ id:string, ts:number, type:string, agent?:string, tool?:string, content?:string }>,
 *   activeScenarioId?: string|null,
 * }} props
 */
export default function AuditTimeline({ events, activeScenarioId }) {
  const { token } = useToken();
  return (
    <div className="audit-timeline">
      <div className="audit-timeline-header">
        <Text type="secondary" strong>审计时间线</Text>
        {activeScenarioId && <Tag bordered={false} color="blue">{activeScenarioId}</Tag>}
      </div>
      {events.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无审计记录" />
      ) : (
        <Timeline
          items={events.map((e) => {
            const meta = TYPE_META[e.type] || TYPE_META.thinking;
            const Icon = meta.icon;
            const ts = dayjs(e.ts).format('HH:mm:ss.SSS');
            const agentName = e.agent ? getAgent(e.agent)?.name : undefined;
            const toolName = e.tool ? getTool(e.tool)?.name : undefined;
            const title = (
              <span>
                <Icon style={{ marginRight: 6, color: token[meta.color] || token.colorPrimary }} />
                <Text strong style={{ marginRight: 6 }}>{meta.label}</Text>
                {agentName && <Tag color="blue" bordered={false}>{agentName}</Tag>}
                {toolName && <Tag color="orange" bordered={false}>{toolName}</Tag>}
              </span>
            );
            const tooltipText = JSON.stringify({ ...e, id: undefined, ts: undefined }, null, 2);
            return {
              color: meta.color,
              dot: <Icon style={{ color: token[meta.color] || token.colorPrimary }} />,
              children: (
                <Tooltip title={<pre style={{ margin: 0 }}>{tooltipText}</pre>} placement="left">
                  <div className="audit-timeline-row">
                    <div>{title}</div>
                    {e.content && <div className="audit-timeline-content">{e.content}</div>}
                    <Text type="secondary" className="audit-timeline-ts">{ts}</Text>
                  </div>
                </Tooltip>
              ),
            };
          })}
        />
      )}
    </div>
  );
}
