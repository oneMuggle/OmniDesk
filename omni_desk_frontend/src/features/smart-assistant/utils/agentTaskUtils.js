/**
 * AgentTaskPanel 纯函数工具
 *
 * 多 Agent 任务面板的模块级纯函数,由 AgentTaskPanel.jsx 拆分而来,
 * 无 React 依赖,可独立单测。
 */

export const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled'];

/** 事件类型 → 时间线节点颜色 */
export const eventColor = (type) => {
  if (type.endsWith('.failed')) return 'red';
  if (type.endsWith('.completed')) return 'green';
  if (type.startsWith('task.')) return 'blue';
  if (type.startsWith('supervisor.') || type.startsWith('user.')) return 'purple';
  if (type === 'hook.triggered') return 'orange';
  return 'gray';
};

export const formatTime = (iso) => (iso ? String(iso).replace('T', ' ').slice(0, 19) : '');

export const formatPayload = (payload) => {
  if (!payload || typeof payload !== 'object' || Object.keys(payload).length === 0) {
    return null;
  }
  const text = JSON.stringify(payload);
  return text.length > 140 ? `${text.slice(0, 140)}…` : text;
};

/** 历史事件(AgentEventSerializer: sequence/event_type/subtask/payload/created_at) → 统一结构 */
export const normalizeHistoryEvent = (event) => ({
  key: `h-${event.sequence}`,
  sequence: event.sequence,
  type: event.event_type,
  subtaskRef: event.subtask ? `#${event.subtask}` : null,
  payload: event.payload,
  time: event.created_at,
});

/** SSE 事件({type, sequence, subtask_id, payload, timestamp}) → 统一结构 */
export const normalizeStreamEvent = (event) => ({
  key: `s-${event.sequence}`,
  sequence: event.sequence,
  type: event.type,
  subtaskRef: event.subtask_id || null,
  payload: event.payload,
  time: event.timestamp,
});

export const statusInfoOf = (status, map) => map[status] || { label: status, color: 'default' };
