/**
 * agentTaskApi 契约测试
 *
 * REST 部分: 校验与后端 AgentTaskViewSet 一致的端点 URL 与载荷
 * SSE 部分: subscribeTaskStream 的事件解析、终态事件、认证失败、abort 断开
 */
import { ReadableStream } from 'stream/web';
import { waitFor } from '@testing-library/react';
import {
  createAgentTask,
  executeAgentTask,
  getAgentTaskTimeline,
  getAgentTasks,
  interveneAgentTask,
  subscribeTaskStream,
} from '../agentTaskApi';
import apiClient from '../../../../shared/api/apiClient';

jest.mock('../../../../shared/api/apiClient', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    defaults: { baseURL: '/api/' },
  },
}));

const encoder = new TextEncoder();

/** 构造按序产出 `data: <json>\n\n` chunk 的模拟 ReadableStream */
const createMockStream = (events) => {
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index >= events.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(events[index])}\n\n`));
      index += 1;
    },
  });
};

const mockFetchResponse = (body, { status = 200 } = {}) => {
  globalThis.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    body,
  });
};

const createCallbacks = () => ({
  onEvent: jest.fn(),
  onDone: jest.fn(),
  onTimeout: jest.fn(),
  onError: jest.fn(),
});

describe('agentTaskApi REST 端点', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('getAgentTasks GET 任务列表端点', async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    await getAgentTasks();

    expect(apiClient.get).toHaveBeenCalledTimes(1);
    expect(apiClient.get).toHaveBeenCalledWith('smart-assistant/tasks/');
  });

  it('getAgentTaskTimeline GET 时间线端点', async () => {
    apiClient.get.mockResolvedValue({ data: {} });

    await getAgentTaskTimeline('t-1');

    expect(apiClient.get).toHaveBeenCalledWith('smart-assistant/tasks/t-1/timeline/');
  });

  it('createAgentTask POST create 端点并携带 query / user_context', async () => {
    apiClient.post.mockResolvedValue({ data: { task_id: 't-1' } });

    await createAgentTask('写一份报告', { scope: 'tech' });

    expect(apiClient.post).toHaveBeenCalledWith('smart-assistant/tasks/create/', {
      query: '写一份报告',
      user_context: { scope: 'tech' },
    });
  });

  it('createAgentTask userContext 缺省为空对象', async () => {
    apiClient.post.mockResolvedValue({ data: {} });

    await createAgentTask('调研任务');

    expect(apiClient.post).toHaveBeenCalledWith('smart-assistant/tasks/create/', {
      query: '调研任务',
      user_context: {},
    });
  });

  it('executeAgentTask POST execute 端点', async () => {
    apiClient.post.mockResolvedValue({ data: {} });

    await executeAgentTask('t-1');

    expect(apiClient.post).toHaveBeenCalledWith('smart-assistant/tasks/t-1/execute/');
  });

  it('interveneAgentTask POST intervene 端点并携带 action', async () => {
    apiClient.post.mockResolvedValue({ data: { status: 'paused' } });

    await interveneAgentTask('t-1', 'pause');

    expect(apiClient.post).toHaveBeenCalledWith('smart-assistant/tasks/t-1/intervene/', {
      action: 'pause',
    });
  });

  it('API 错误向上抛出供调用方处理', async () => {
    apiClient.post.mockRejectedValue(new Error('network'));

    await expect(createAgentTask('q')).rejects.toThrow('network');
  });
});

describe('subscribeTaskStream SSE 订阅', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.setItem('authTokens', JSON.stringify({ access: 'test-token' }));
  });

  afterEach(() => {
    delete globalThis.fetch;
    localStorage.clear();
  });

  it('GET 流端点携带 last_seq，并在回调处理后继续派发同一批事件', async () => {
    mockFetchResponse(createMockStream([
      { type: 'task.started', sequence: 5 },
      { type: 'subtask.started', sequence: 6 },
    ]));
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks, { lastSeq: 4 });

    await waitFor(() => expect(callbacks.onDone).toHaveBeenCalled());
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/smart-assistant/tasks/t-1/stream/?last_seq=4',
      expect.any(Object)
    );
    expect(callbacks.onEvent).toHaveBeenCalledTimes(2);
    expect(callbacks.onDone).toHaveBeenCalledWith(undefined, 6);
  });

  it('GET 流端点并携带 Bearer token', async () => {
    mockFetchResponse(createMockStream([]));
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() => expect(callbacks.onDone).toHaveBeenCalled());
    const request = globalThis.fetch.mock.calls[0][1];
    expect(request.method).toBe('GET');
    expect(new Headers(request.headers).get('Authorization')).toBe('Bearer test-token');
  });

  it('按序派发进度事件,done 事件触发 onDone 且不进 onEvent', async () => {
    mockFetchResponse(
      createMockStream([
        { type: 'task.started', sequence: 1, payload: {}, timestamp: '2026-07-01T10:00:00' },
        { type: 'subtask.started', sequence: 2, subtask_id: 'st-1', payload: {}, timestamp: '2026-07-01T10:00:01' },
        { type: 'done', task_id: 't-1' },
      ])
    );
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() => expect(callbacks.onDone).toHaveBeenCalled());
    expect(callbacks.onEvent).toHaveBeenCalledTimes(2);
    expect(callbacks.onEvent.mock.calls[0][0]).toMatchObject({ type: 'task.started', sequence: 1 });
    expect(callbacks.onEvent.mock.calls[1][0]).toMatchObject({
      type: 'subtask.started',
      subtask_id: 'st-1',
    });
    expect(callbacks.onError).not.toHaveBeenCalled();
    expect(callbacks.onTimeout).not.toHaveBeenCalled();
  });

  it('服务端正常关流(无显式 done)也触发 onDone', async () => {
    mockFetchResponse(createMockStream([]));
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() => expect(callbacks.onDone).toHaveBeenCalled());
    expect(callbacks.onError).not.toHaveBeenCalled();
  });

  it('timeout 事件触发 onTimeout 且不进 onEvent', async () => {
    mockFetchResponse(
      createMockStream([{ type: 'task.started', sequence: 1, payload: {} }, { type: 'timeout' }])
    );
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() => expect(callbacks.onTimeout).toHaveBeenCalled());
    expect(callbacks.onEvent).toHaveBeenCalledTimes(1);
    expect(callbacks.onDone).not.toHaveBeenCalled();
  });

  it('401 响应触发认证错误', async () => {
    mockFetchResponse(null, { status: 401 });
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() =>
      expect(callbacks.onError).toHaveBeenCalledWith(
        expect.objectContaining({ message: '认证已过期，请重新登录' })
      )
    );
  });

  it('非 2xx 响应触发连接失败错误', async () => {
    mockFetchResponse(null, { status: 500 });
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() =>
      expect(callbacks.onError).toHaveBeenCalledWith(
        expect.objectContaining({ message: '任务进度流连接失败' })
      )
    );
  });

  it('畸形 JSON 数据行被跳过,不影响后续事件', async () => {
    // 手工构造含坏行的流:坏行 + 正常事件 + done
    const chunks = [
      'data: {这不是合法JSON\n\n',
      `data: ${JSON.stringify({ type: 'task.started', sequence: 1, payload: {} })}\n\n`,
      `data: ${JSON.stringify({ type: 'done', task_id: 't-1' })}\n\n`,
    ];
    let index = 0;
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream({
        pull(controller) {
          if (index >= chunks.length) {
            controller.close();
            return;
          }
          controller.enqueue(encoder.encode(chunks[index]));
          index += 1;
        },
      }),
    });
    const callbacks = createCallbacks();

    subscribeTaskStream('t-1', callbacks);

    await waitFor(() => expect(callbacks.onError).toHaveBeenCalledWith(expect.objectContaining({ message: '任务进度数据格式错误' })));
    expect(callbacks.onEvent).toHaveBeenCalledTimes(0);
    expect(callbacks.onDone).not.toHaveBeenCalled();
  });

  it('abort 断开连接后不触发 onError', async () => {
    globalThis.fetch = jest.fn(
      (url, options) =>
        new Promise((resolve, reject) => {
          options.signal.addEventListener('abort', () => {
            const error = new Error('Aborted');
            error.name = 'AbortError';
            reject(error);
          });
        })
    );
    const callbacks = createCallbacks();

    const { abort } = subscribeTaskStream('t-1', callbacks);
    abort();

    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(callbacks.onError).not.toHaveBeenCalled();
    expect(callbacks.onDone).not.toHaveBeenCalled();
  });

  describe('无 ReadableStream 时的 timeline 降级', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('轮询 timeline 并仅派发 sequence 大于 lastSeq 的事件，终态带最终 sequence', async () => {
      globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, body: {} });
      apiClient.get
        .mockResolvedValueOnce({
          data: {
            task: { status: 'running' },
            timeline: [
              { type: 'task.started', sequence: 1 },
              { type: 'subtask.progress', sequence: 2 },
            ],
          },
        })
        .mockResolvedValueOnce({
          data: {
            task: { status: 'completed' },
            timeline: [
              { type: 'task.started', sequence: 1 },
              { type: 'subtask.progress', sequence: 2 },
              { type: 'task.completed', sequence: 3 },
            ],
          },
        });
      const callbacks = createCallbacks();

      subscribeTaskStream('t-1', callbacks);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      expect(callbacks.onEvent).toHaveBeenCalledTimes(2);
      await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith(
        'smart-assistant/tasks/t-1/timeline/',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      ));

      jest.advanceTimersByTime(2000);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();

      expect(callbacks.onEvent).toHaveBeenCalledTimes(3);
      expect(callbacks.onEvent).toHaveBeenLastCalledWith(expect.objectContaining({ sequence: 3 }));
      expect(callbacks.onDone).toHaveBeenCalledWith(expect.objectContaining({ sequence: 3 }));
      expect(callbacks.onError).not.toHaveBeenCalled();
    });

    it('缺少 AbortController 时仍能轮询并在 abort 后停止后续回调', async () => {
      const originalAbortController = globalThis.AbortController;
      globalThis.AbortController = undefined;
      globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, body: {} });
      apiClient.get.mockResolvedValue({
        data: {
          task: { status: 'completed' },
          timeline: [{ type: 'task.completed', sequence: 1 }],
        },
      });
      const callbacks = createCallbacks();

      const subscription = subscribeTaskStream('t-1', callbacks);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
      subscription.abort();

      expect(callbacks.onEvent).toHaveBeenCalledTimes(1);
      expect(callbacks.onDone).toHaveBeenCalledWith(expect.objectContaining({ sequence: 1 }));
      globalThis.AbortController = originalAbortController;
    });

    it('abort 会清理轮询 timer 并取消进行中的 timeline 请求', async () => {
      globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, body: {} });
      apiClient.get.mockImplementation(
        (url, options) =>
          new Promise((resolve, reject) => {
            options.signal.addEventListener('abort', () => {
              const error = new Error('Aborted');
              error.name = 'AbortError';
              reject(error);
            });
          })
      );
      const callbacks = createCallbacks();
      const subscription = subscribeTaskStream('t-1', callbacks);

      await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
      subscription.abort();
      jest.advanceTimersByTime(10000);
      await Promise.resolve();

      expect(apiClient.get).toHaveBeenCalledTimes(1);
      expect(callbacks.onDone).not.toHaveBeenCalled();
      expect(callbacks.onError).not.toHaveBeenCalled();
    });
  });
});
