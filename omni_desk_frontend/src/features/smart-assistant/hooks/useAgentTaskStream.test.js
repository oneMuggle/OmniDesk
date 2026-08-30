import { renderHook, act } from '@testing-library/react';
import { subscribeTaskStream } from '../api/agentTaskApi';
import useAgentTaskStream from './useAgentTaskStream';
import mapAgentEvent from '../scenario/utils/mapAgentEvent';

jest.mock('../api/agentTaskApi', () => ({
  subscribeTaskStream: jest.fn(),
  interveneAgentTask: jest.fn().mockResolvedValue({ data: { status: 'paused' } }),
}));
jest.mock('../scenario/utils/mapAgentEvent', () => jest.fn((event) => ({ ...event, type: 'thinking' })));

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
    expect(result.current.events).toEqual([{ type: 'thinking', sequence: 3 }]);
    expect(result.current.lastSeq).toBe(3);
    expect(result.current.status).toBe('completed');
  });

  it('超时按 lastSeq 自动重连而非进入暂停态', () => {
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      subscriptions.push({ callbacks, options, abort: jest.fn() });
      return { abort: subscriptions[subscriptions.length - 1].abort };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-2'));
    act(() => subscriptions[0].callbacks.onEvent({ type: 'progress', sequence: 8 }));
    act(() => subscriptions[0].callbacks.onTimeout());
    expect(subscriptions[0].abort).toHaveBeenCalled();
    expect(subscriptions[1].options).toEqual({ lastSeq: 8 });
    expect(result.current.status).toBe('running');
  });

  it('连接错误最多退避三次后才标记失败', () => {
    jest.useFakeTimers();
    const subscriptions = [];
    subscribeTaskStream.mockImplementation((taskId, callbacks, options) => {
      subscriptions.push({ callbacks, options, abort: jest.fn() });
      return { abort: subscriptions[subscriptions.length - 1].abort };
    });
    const { result } = renderHook(() => useAgentTaskStream('task-3'));
    act(() => subscriptions[0].callbacks.onError(new Error('断开')));
    expect(result.current.status).toBe('running');
    act(() => jest.advanceTimersByTime(1000));
    act(() => subscriptions[1].callbacks.onError(new Error('断开')));
    act(() => jest.advanceTimersByTime(2000));
    act(() => subscriptions[2].callbacks.onError(new Error('断开')));
    act(() => jest.advanceTimersByTime(4000));
    expect(result.current.status).toBe('failed');
    jest.useRealTimers();
  });


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
