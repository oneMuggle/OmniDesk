const EVENT_TYPE_MAP = {
  'task.started': 'thinking',
  'task.paused': 'thinking',
  'task.resumed': 'thinking',
  'task.completed': 'final_answer',
  'task.cancelled': 'error',
  'subtask.started': 'thinking',
  'subtask.progress': 'thinking',
  'subtask.tool_call': 'tool_call',
  'subtask.tool_result': 'tool_result',
  'subtask.quality_gate': 'thinking',
  'subtask.completed': 'thinking',
  'subtask.skipped': 'error',
  'subtask.failed': 'error',
  'task.failed': 'error',
  'task.aborted': 'error',
  'supervisor.decision': 'thinking',
  'supervisor.intervention': 'thinking',
  'user.intervention': 'thinking',
  'hook.triggered': 'thinking',
  started: 'thinking',
  progress: 'thinking',
  tool_call: 'tool_call',
  tool_result: 'tool_result',
  completed: 'thinking',
};

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

const firstDefined = (...values) => values.find((value) => value !== undefined && value !== null);

/**
 * 将 SSE 或历史 AgentEvent 转换为场景组件使用的统一事件结构。
 * @param {unknown} event 原始 SSE/历史事件
 * @returns {object} 统一场景事件；未知或畸形事件也会返回可渲染的 error 事件
 */
export function mapAgentEvent(event) {
  const source = isObject(event) ? event : {};
  const payload = isObject(source.payload) ? source.payload : {};
  const eventType = firstDefined(source.type, source.event_type, 'unknown');
  const mappedType = EVENT_TYPE_MAP[eventType] || 'thinking';
  const result = {
    id: source.sequence,
    sequence: source.sequence,
    eventType,
    type: mappedType,
  };

  const agent = firstDefined(source.agent, payload.agent, source.role, payload.role);
  const tool = firstDefined(source.tool, payload.tool);
  const input = firstDefined(source.input, payload.input, payload.arguments);
  const output = firstDefined(source.output, payload.output, payload.result);
  const finalOutput = firstDefined(source.final_output, payload.final_output);
  const payloadKind = firstDefined(source.payloadKind, payload.payloadKind);
  const content = firstDefined(
    source.content,
    payload.content,
    payload.message,
    payload.error,
    source.error
  );
  const ts = firstDefined(source.ts, source.timestamp, source.created_at, payload.ts);

  if (agent !== undefined) result.agent = agent;
  if (tool !== undefined) result.tool = tool;
  if (input !== undefined) result.input = input;
  if (output !== undefined) result.output = output;
  if (finalOutput !== undefined) result.finalOutput = finalOutput;
  if (payloadKind !== undefined) result.payloadKind = payloadKind;
  if (content !== undefined) {
    result.content = content;
  } else if (mappedType === 'error' || !EVENT_TYPE_MAP[eventType]) {
    result.content = `未知事件类型: ${eventType}`;
  }
  if (ts !== undefined) result.ts = ts;

  return result;
}

export default mapAgentEvent;
