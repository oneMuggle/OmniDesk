/**
 * agentTaskUtils 纯函数单测
 *
 * 覆盖 AgentTaskPanel 拆分出的全部工具函数各分支,
 * 保证拆分后行为逐字一致。
 */
import {
  TERMINAL_STATUSES,
  eventColor,
  formatPayload,
  formatTime,
  normalizeHistoryEvent,
  normalizeStreamEvent,
  statusInfoOf,
} from '../agentTaskUtils';

describe('TERMINAL_STATUSES', () => {
  it('包含 completed/failed/cancelled', () => {
    expect(TERMINAL_STATUSES).toEqual(['completed', 'failed', 'partial', 'cancelled', 'paused']);
  });
});

describe('eventColor', () => {
  it('.failed 后缀 → red', () => {
    expect(eventColor('subtask.tool_call.failed')).toBe('red');
  });
  it('.completed 后缀 → green', () => {
    expect(eventColor('task.completed')).toBe('green');
  });
  it('task. 前缀 → blue', () => {
    expect(eventColor('task.started')).toBe('blue');
  });
  it('supervisor./user. 前缀 → purple', () => {
    expect(eventColor('supervisor.plan_created')).toBe('purple');
    expect(eventColor('user.confirmation')).toBe('purple');
  });
  it('hook.triggered → orange', () => {
    expect(eventColor('hook.triggered')).toBe('orange');
  });
  it('未知类型 → gray', () => {
    expect(eventColor('unknown.event')).toBe('gray');
  });
});

describe('formatTime', () => {
  it('ISO 时间格式化为可读时间', () => {
    expect(formatTime('2026-07-01T10:00:00Z')).toBe('2026-07-01 10:00:00');
  });
  it('空值返回空字符串', () => {
    expect(formatTime(null)).toBe('');
    expect(formatTime(undefined)).toBe('');
  });
});

describe('formatPayload', () => {
  it('空对象返回 null', () => {
    expect(formatPayload({})).toBeNull();
  });
  it('非对象返回 null', () => {
    expect(formatPayload(null)).toBeNull();
    expect(formatPayload(undefined)).toBeNull();
    expect(formatPayload('string')).toBeNull();
  });
  it('短 payload 原样序列化', () => {
    expect(formatPayload({ tool: 'search' })).toBe('{"tool":"search"}');
  });
  it('超长 payload 截断到 140 字符', () => {
    const long = { text: 'x'.repeat(300) };
    const text = JSON.stringify(long);
    expect(formatPayload(long)).toBe(`${text.slice(0, 140)}…`);
  });
});

describe('normalizeHistoryEvent', () => {
  it('映射序列号/类型/时间并标记历史来源 key', () => {
    const event = {
      sequence: 2,
      event_type: 'task.started',
      subtask: 'st-1',
      payload: {},
      created_at: '2026-07-01T10:00:01Z',
    };
    expect(normalizeHistoryEvent(event)).toEqual({
      key: 'h-2',
      sequence: 2,
      type: 'task.started',
      subtaskRef: '#st-1',
      payload: {},
      time: '2026-07-01T10:00:01Z',
    });
  });
  it('无 subtask 时 subtaskRef 为 null', () => {
    const event = { sequence: 1, event_type: 'task.started', subtask: null, payload: {}, created_at: null };
    expect(normalizeHistoryEvent(event).subtaskRef).toBeNull();
  });
});

describe('normalizeStreamEvent', () => {
  it('映射 type/sequence/subtask_id/timestamp 并标记流来源 key', () => {
    const event = {
      type: 'subtask.tool_call',
      sequence: 2,
      subtask_id: 'st-1',
      payload: { tool: 'search' },
      timestamp: '2026-07-01T10:00:02Z',
    };
    expect(normalizeStreamEvent(event)).toEqual({
      key: 's-2',
      sequence: 2,
      type: 'subtask.tool_call',
      subtaskRef: 'st-1', // 既有实现无 # 前缀(与历史事件 normalizeHistoryEvent 不同)
      payload: { tool: 'search' },
      time: '2026-07-01T10:00:02Z',
    });
  });
  it('无 subtask_id 时 subtaskRef 为 null', () => {
    const event = { type: 'task.started', sequence: 1, subtask_id: null, payload: {}, timestamp: null };
    expect(normalizeStreamEvent(event).subtaskRef).toBeNull();
  });
});

describe('statusInfoOf', () => {
  const map = { running: { label: '执行中', color: 'processing' } };
  it('命中映射返回对应信息', () => {
    expect(statusInfoOf('running', map)).toEqual({ label: '执行中', color: 'processing' });
  });
  it('未命中时回退为原状态标签 + default 颜色', () => {
    expect(statusInfoOf('unknown', map)).toEqual({ label: 'unknown', color: 'default' });
  });
});
