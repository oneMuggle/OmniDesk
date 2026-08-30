import mapAgentEvent from '../mapAgentEvent';

describe('mapAgentEvent', () => {
  it('顶层字段优先于 payload，并保留 task/subtask/status', () => {
    const mapped = mapAgentEvent({
      type: 'subtask.progress', sequence: 7, task_id: 'task-top', subtask_id: 'sub-top', status: 'running',
      payload: { task_id: 'task-payload', subtask_id: 'sub-payload', status: 'paused', content: '进度' },
    });

    expect(mapped).toMatchObject({
      type: 'thinking', eventType: 'subtask.progress', sequence: 7,
      task_id: 'task-top', subtask_id: 'sub-top', status: 'running', content: '进度',
    });
  });

  it('顶层缺失时从 payload fallback 事件字段', () => {
    const mapped = mapAgentEvent({
      event_type: 'subtask.tool_result', sequence: 8,
      payload: { task_id: 'task-payload', subtask_id: 'sub-payload', tool: 'search', result: { ok: true }, status: 'completed' },
    });

    expect(mapped).toMatchObject({
      type: 'tool_result', eventType: 'subtask.tool_result', sequence: 8,
      task_id: 'task-payload', subtask_id: 'sub-payload', tool: 'search', output: { ok: true }, status: 'completed',
    });
  });


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
      id: 'evt-7',
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
      id: 'evt-8',
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
      id: 'evt-9',
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
      id: 'evt-10',
        sequence: 10,
        eventType,
        type: 'error',
      });
    }
  );

  test('未知事件返回明确兜底且不抛异常', () => {
    expect(() => mapAgentEvent(null)).not.toThrow();
    expect(mapAgentEvent({ type: 'unknown.event', sequence: 11 })).toMatchObject({
      id: 'evt-11',
      sequence: 11,
      eventType: 'unknown.event',
      type: 'thinking',
      content: '未知事件类型: unknown.event',
    });
  });

  test('缺失、负数和小数 sequence 使用稳定且不冲突的 id', () => {
    const missing = mapAgentEvent({ type: 'subtask.progress', payload: { content: 'a' } });
    const negative = mapAgentEvent({ type: 'subtask.progress', sequence: -1, payload: { content: 'b' } });
    const decimal = mapAgentEvent({ type: 'subtask.progress', sequence: 1.5, payload: { content: 'c' } });

    expect(missing.id).toMatch(/^evt-invalid-/);
    expect(negative.id).toMatch(/^evt-invalid-/);
    expect(decimal.id).toMatch(/^evt-invalid-/);
    expect(new Set([missing.id, negative.id, decimal.id]).size).toBe(3);
    expect(missing.sequence).toBeNull();
  });

  test('畸形 payload 不抛异常并使用安全默认值', () => {
    expect(mapAgentEvent({ type: 'subtask.progress', sequence: 12, payload: null })).toEqual({
      id: 'evt-12',
      sequence: 12,
      eventType: 'subtask.progress',
      type: 'thinking',
    });
  });
});
