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

  it('synthetic done 不推进 lastSeq，后续真实 sequence 仍可继续派发', () => {
    jest.useFakeTimers();
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      const subscription = { callbacks, options, abort: jest.fn() };
      subscriptions.push(subscription);
      if (subscriptions.length === 1) {
        callbacks.onEvent({ type: 'progress', sequence: 4 });
        callbacks.onDone({ type: 'done', sequence: 5, synthetic: true }, 4);
      }
      return { abort: subscription.abort };
    });

    const { result } = renderHook(() => useAgentTaskStream('task-synthetic'));
    expect(result.current.lastSeq).toBe(4);
    act(() => result.current.retry());
    expect(subscriptions[1].options).toEqual({ lastSeq: 4 });
    act(() => subscriptions[1].callbacks.onEvent({ type: 'progress', sequence: 5 }));
    expect(result.current.lastSeq).toBe(5);
  });


  it('SSE done paused 时保持 paused，不误判为 completed', () => {
    subscribeTaskStream.mockImplementation((taskId, callbacks) => {
      callbacks.onDone({ type: 'done', status: 'paused', sequence: 4 }, 4);
      return { abort: jest.fn() };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-paused'));

    expect(result.current.status).toBe('paused');
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

  it('resume 在 manuallyPaused 状态仍订阅并等待 task.resumed 事件', async () => {
    jest.useFakeTimers();
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      const subscription = { callbacks, options, abort: jest.fn() };
      subscriptions.push(subscription);
      return subscription;
    });
    const { result } = renderHook(() => useAgentTaskStream('task-resume'));

    await act(async () => { await result.current.pause(); });
    expect(result.current.status).toBe('pausing');
    await act(async () => { await result.current.resume(); });

    expect(result.current.status).toBe('resuming');
    expect(subscriptions.length).toBeGreaterThan(1);
    act(() => subscriptions[subscriptions.length - 1].callbacks.onEvent({ type: 'task.resumed', sequence: 2 }));
    expect(result.current.status).toBe('running');
    expect(result.current.error).toBeNull();
  });

  it('pause 未收到确认事件时五秒后回滚并报告错误', async () => {
    jest.useFakeTimers();
    subscribeTaskStream.mockImplementation(() => ({ abort: jest.fn() }));
    const { result } = renderHook(() => useAgentTaskStream('task-pause-timeout'));

    await act(async () => { await result.current.pause(); });
    expect(result.current.status).toBe('pausing');
    act(() => jest.advanceTimersByTime(5000));
    expect(result.current.status).toBe('running');
    expect(result.current.error).toEqual(expect.objectContaining({ message: '暂停确认超时' }));
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
