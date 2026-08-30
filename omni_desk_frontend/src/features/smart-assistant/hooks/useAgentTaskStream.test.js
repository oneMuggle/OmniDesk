import { renderHook, act } from '@testing-library/react';
import { subscribeTaskStream } from '../api/agentTaskApi';
import useAgentTaskStream from './useAgentTaskStream';

jest.mock('../api/agentTaskApi', () => ({
  subscribeTaskStream: jest.fn(),
}));

describe('useAgentTaskStream', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      callbacks.onEvent({ type: 'task.started', sequence: 3 });
      callbacks.onDone({ type: 'done' }, options.lastSeq);
      return { abort: jest.fn() };
    });
  });

  it('订阅真实 taskId 并从 lastSeq 继续，按 sequence 去重事件', () => {
    const { result } = renderHook(() => useAgentTaskStream('task-9', { lastSeq: 2 }));

    expect(subscribeTaskStream).toHaveBeenCalledWith(
      'task-9',
      expect.any(Object),
      { lastSeq: 2 },
    );
    expect(result.current.events).toEqual([{ type: 'task.started', sequence: 3 }]);
    expect(result.current.lastSeq).toBe(3);
    expect(result.current.status).toBe('completed');
  });

  it('重连时使用最新 sequence 并支持暂停恢复取消重试动作', () => {
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      const subscription = { callbacks, options, abort: jest.fn() };
      subscriptions.push(subscription);
      return { abort: subscription.abort };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-1'));

    act(() => result.current.onEvent({ type: 'subtask.progress', sequence: 7 }));
    act(() => result.current.pause());
    act(() => result.current.resume());
    act(() => result.current.cancel());
    act(() => result.current.retry());

    expect(subscriptions[0].abort).toHaveBeenCalled();
    expect(subscriptions[1].options).toEqual({ lastSeq: 7 });
    expect(result.current.status).toBe('running');
  });
});
