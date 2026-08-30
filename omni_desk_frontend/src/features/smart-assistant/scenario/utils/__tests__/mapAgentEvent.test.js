import mapAgentEvent from '../mapAgentEvent';

describe('mapAgentEvent', () => {
  test.each([
    ['subtask.started', 'thinking'],
    ['subtask.progress', 'thinking'],
    ['subtask.completed', 'thinking'],
  ])('将 %s 映射为 %s', (eventType, type) => {
    expect(mapAgentEvent({
      type: eventType,
      sequence: 7,
      payload: { agent: 'planner', content: '处理中' },
      timestamp: '2026-08-30T10:00:00Z',
    })).toMatchObject({
      id: 7,
      sequence: 7,
      eventType,
      type,
      agent: 'planner',
      content: '处理中',
      ts: '2026-08-30T10:00:00Z',
    });
  });

  test.each(['tool_call', 'tool_result'])('映射 %s 并保留工具字段', (eventType) => {
    const event = mapAgentEvent({
      type: eventType,
      sequence: 8,
      payload: {
        agent: 'researcher',
        tool: 'search_docs',
        input: { query: '离线部署' },
        output: { hits: 2 },
      },
      timestamp: 1700000000000,
    });

    expect(event).toMatchObject({
      id: 8,
      sequence: 8,
      eventType,
      type: eventType,
      agent: 'researcher',
      tool: 'search_docs',
      input: { query: '离线部署' },
      output: { hits: 2 },
      ts: 1700000000000,
    });
  });

  test('task.completed 映射为最终答复并从历史事件字段提取数据', () => {
    expect(mapAgentEvent({
      event_type: 'task.completed',
      sequence: 9,
      payload: {
        agent: 'coordinator',
        content: '任务已完成',
        output: { answer: '完成' },
      },
      created_at: '2026-08-30T10:01:00Z',
    })).toMatchObject({
      id: 9,
      sequence: 9,
      eventType: 'task.completed',
      type: 'final_answer',
      agent: 'coordinator',
      content: '任务已完成',
      output: { answer: '完成' },
      ts: '2026-08-30T10:01:00Z',
    });
  });

  test.each(['subtask.skipped', 'subtask.failed', 'task.failed', 'task.aborted'])(
    '%s 映射为 error',
    (eventType) => {
      expect(mapAgentEvent({
        type: eventType,
        sequence: 10,
        payload: { error: '执行失败' },
      })).toMatchObject({
        id: 10,
        sequence: 10,
        eventType,
        type: 'error',
      });
    }
  );

  test('未知事件返回明确兜底且不抛异常', () => {
    expect(() => mapAgentEvent(null)).not.toThrow();
    expect(mapAgentEvent({ type: 'unknown.event', sequence: 11 })).toMatchObject({
      id: 11,
      sequence: 11,
      eventType: 'unknown.event',
      type: 'thinking',
      content: '未知事件类型: unknown.event',
    });
  });

  test('畸形 payload 不抛异常并使用安全默认值', () => {
    expect(mapAgentEvent({ type: 'subtask.progress', sequence: 12, payload: null })).toEqual({
      id: 12,
      sequence: 12,
      eventType: 'subtask.progress',
      type: 'thinking',
    });
  });
});
