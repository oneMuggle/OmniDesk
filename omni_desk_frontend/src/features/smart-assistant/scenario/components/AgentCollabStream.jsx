// 中栏协作流容器：把 events 序列按 type 派发到对应子组件渲染
import { Empty, Typography } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';

import AgentCard from './AgentCard';
import ToolCallCard from './ToolCallCard';
import FinalAnswerCard from './FinalAnswerCard';

const { Title, Paragraph } = Typography;

/**
 * @param {{
 *   events: Array<{
 *     id:string, type:string, agent?:string, tool?:string,
 *     content?:string, input?:object, output?:unknown,
 *     payloadKind?:string, payload?:object
 *   }>,
 *   isRunning: boolean,
 *   isCompleted: boolean,
 *   status: string,
 * }} props
 */
export default function AgentCollabStream({ events, isRunning, isCompleted, status }) {
  if (events.length === 0) {
    return (
      <div className="collab-stream empty">
        <Empty
          image={<ThunderboltOutlined style={{ fontSize: 64, color: '#bfbfbf' }} />}
          description={
            <div>
              <Title level={5} style={{ marginTop: 16 }}>等待任务开始</Title>
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                从左侧选择一个业务场景,或用自然语言描述需求,智能体将协同完成任务
              </Paragraph>
            </div>
          }
        />
      </div>
    );
  }

  // 把 tool_call 和它紧接着的 tool_result 配对展示
  // 规则：拿当前 events,逐个看；如果当前是 tool_call,看下一个事件是不是 tool_result
  // (剧本设计里 tool_call 后紧跟的就是 tool_result)
  const pairedList = [];
  for (let i = 0; i < events.length; i += 1) {
    const cur = events[i];
    if (cur.type === 'tool_call') {
      const next = events[i + 1];
      if (next && next.type === 'tool_result') {
        pairedList.push({
          key: cur.id,
          kind: 'tool_pair',
          toolCall: cur,
          toolResult: next,
        });
        // eslint-disable-next-line no-param-reassign
        i += 1;
        continue;
      }
    }
    if (cur.type === 'tool_result') {
      // 单独出现的 tool_result(无对应 tool_call)— 跳过避免重复
      continue;
    }
    pairedList.push({ key: cur.id, kind: cur.type, event: cur });
  }

  return (
    <div className="collab-stream">
      <div className="collab-stream-meta">
        <span className="collab-stream-status">
          状态:{status === 'running' ? '运行中' : status === 'paused' ? '已暂停' : status === 'completed' ? '已完成' : status === 'partial' ? '部分完成' : status === 'failed' ? '已失败' : '空闲'}
        </span>
        <span className="collab-stream-count">事件:{events.length}</span>
        {isRunning && <span className="collab-stream-pulse" />}
      </div>
      {pairedList.map((node) => {
        if (node.kind === 'tool_pair') {
          const tc = node.toolCall;
          return (
            <ToolCallCard
              key={node.key}
              agent={tc.agent}
              tool={tc.tool}
              input={tc.input}
              output={node.toolResult.output}
            />
          );
        }
        if (node.kind === 'thinking') {
          return (
            <AgentCard
              key={node.key}
              agent={node.event.agent}
              content={node.event.content}
              variant="thinking"
            />
          );
        }
        if (node.kind === 'error') {
          return (
            <AgentCard
              key={node.key}
              agent={node.event.agent || 'system'}
              content={node.event.content || '任务执行失败'}
              payload={node.event.payload}
              variant="thinking"
            />
          );
        }
        if (node.kind === 'final_answer') {
          return (
            <FinalAnswerCard
              key={node.key}
              agent={node.event.agent}
              payloadKind={node.event.payloadKind}
              payload={node.event.payload}
              finalOutput={node.event.finalOutput}
            />
          );
        }
        return null;
      })}
      {isCompleted && (
        <div className="collab-stream-footer">
          <span>— 任务已完成,可导出审计日志 —</span>
        </div>
      )}
    </div>
  );
}
