import { renderHook, act } from '@testing-library/react';
import { subscribeTaskStream } from '../api/agentTaskApi';
import useAgentTaskStream from './useAgentTaskStream';

jest.mock('../api/agentTaskApi', () => ({
  subscribeTaskStream: jest.fn(),
  interveneAgentTask: jest.fn().mockResolvedValue({ data: { status: 'paused' } }),
}));
jest.mock('../scenario/utils/mapAgentEvent', () => jest.fn((event) => ({ ...event, type: 'thinking' })));

describe('useAgentTaskStream', () => {
  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllMocks();
  });

  it('订阅真实 taskId 并从 lastSeq 继续，按 sequence 去重事件', () => {
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      callbacks.onEvent({ type: 'task.started', sequence: 3 });
      callbacks.onDone({ type: 'done' }, options.lastSeq);
      return { abort: jest.fn() };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-9', { lastSeq: 2 }));

    expect(subscribeTaskStream).toHaveBeenCalledWith('task-9', expect.any(Object), { lastSeq: 2 });
    expect(result.current.events).toEqual([{ type: 'thinking', sequence: 3 }]);
    expect(result.current.lastSeq).toBe(3);
    expect(result.current.status).toBe('completed');
  });

  it('超时按 lastSeq 自动重连而非进入暂停态', () => {
    jest.useFakeTimers();
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      const subscription = { callbacks, options, abort: jest.fn() };
      subscriptions.push(subscription);
      return { abort: subscription.abort };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-2'));
    act(() => subscriptions[0].callbacks.onEvent({ type: 'progress', sequence: 8 }));
    act(() => subscriptions[0].callbacks.onTimeout());
    act(() => jest.runOnlyPendingTimers());

    expect(subscriptions[0].abort).toHaveBeenCalled();
    expect(subscriptions[1].options).toEqual({ lastSeq: 8 });
    expect(result.current.status).toBe('running');
  });

  it('连接错误最多退避三次后才标记失败', () => {
    jest.useFakeTimers();
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      const subscription = { callbacks, options, abort: jest.fn() };
      subscriptions.push(subscription);
      return { abort: subscription.abort };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-3'));

    act(() => subscriptions[0].callbacks.onError(new Error('断开')));
    expect(result.current.status).toBe('running');
    act(() => jest.advanceTimersByTime(1000));
    act(() => subscriptions[1].callbacks.onError(new Error('断开')));
    act(() => jest.advanceTimersByTime(2000));
    act(() => subscriptions[2].callbacks.onError(new Error('断开')));
    act(() => jest.advanceTimersByTime(4000));
    act(() => subscriptions[3].callbacks.onError(new Error('断开')));
    expect(result.current.status).toBe('failed');
  });
});
