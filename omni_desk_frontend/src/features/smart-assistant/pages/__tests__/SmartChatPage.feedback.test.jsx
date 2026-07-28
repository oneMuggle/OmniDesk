/**
 * 智能助手赞踩反馈 API 接入测试(P1)。
 *
 * 验证:
 * 1. SSE done 事件携带的 log_id 被记录到 assistant 消息
 * 2. 点击赞/踩调用 submitFeedback(logId, type)
 * 3. API 失败 → message.error 提示 + 回滚本地状态
 * 4. 防重复提交(同值不重复调用),允许 up/down 改选
 * 5. 旧版事件(无 log_id)→ 仅本地状态,不调用 API
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigProvider, message } from 'antd';
import { ReadableStream } from 'stream/web';
import SmartChatPage from '../SmartChatPage';

// ── API Mock ──
jest.mock('../../api/smartAssistantApi', () => ({
  sendSmartChatStream: jest.fn(),
  sendSmartChat: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'test-session' } }),
  deleteSession: jest.fn().mockResolvedValue({}),
  submitFeedback: jest.fn(),
}));

// ── 浏览器 API Mock ──
// jsdom 不提供 requestAnimationFrame / scrollIntoView;与 ux 测试保持一致:
// requestAnimationFrame 返回 0(假值)使 finally 中 flushTypewriter 直接显示全文
beforeAll(() => {
  window.requestAnimationFrame = () => 0;
  window.cancelAnimationFrame = jest.fn();
  Element.prototype.scrollIntoView = jest.fn();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockResolvedValue(undefined) },
    writable: true,
    configurable: true,
  });
});

const renderWithProviders = (component) => render(<ConfigProvider>{component}</ConfigProvider>);

/** 构造按顺序产出 SSE 事件的模拟 ReadableStream */
const createMockStream = (events) => {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index >= events.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(events[index])}\n\n`));
      index++;
    },
  });
};

/** 模拟一次完整的流式回答;logId 为 undefined 时 done 事件不携带 log_id(旧版事件) */
const mockStreamAnswer = (content, logId) => {
  const { sendSmartChatStream } = require('../../api/smartAssistantApi');
  const doneEvent = logId !== undefined ? { type: 'done', log_id: logId } : { type: 'done' };
  sendSmartChatStream.mockReturnValue({
    bodyPromise: Promise.resolve(createMockStream([
      { type: 'meta', intent: 'general' },
      { type: 'chunk', content },
      doneEvent,
    ])),
    abort: jest.fn(),
  });
};

/** 发送一条问题并等待 assistant 回复出现 */
const sendQuestion = async (question, answer, logId) => {
  mockStreamAnswer(answer, logId);
  renderWithProviders(<SmartChatPage />);
  const input = screen.getByPlaceholderText(/问我任何问题/);
  fireEvent.change(input, { target: { value: question } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));
  await waitFor(() => {
    expect(screen.getByText(answer)).toBeInTheDocument();
  }, { timeout: 3000 });
};

// antd 图标按钮的无障碍名来自图标 aria-label(赞: like / 踩: dislike)
const getLikeButton = () => screen.getByRole('button', { name: 'like' });
const getDislikeButton = () => screen.getByRole('button', { name: 'dislike' });

describe('SmartChatPage 赞踩反馈', () => {
  let messageErrorSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    messageErrorSpy = jest.spyOn(message, 'error').mockImplementation(() => ({}));
  });

  afterEach(() => {
    messageErrorSpy.mockRestore();
  });

  it('点击赞调用 submitFeedback 并进入已反馈态', async () => {
    const { submitFeedback } = require('../../api/smartAssistantApi');
    submitFeedback.mockResolvedValue({ data: { feedback: 'up' } });

    await sendQuestion('今天有什么安排', '今日安排如下', 42);

    fireEvent.click(getLikeButton());

    await waitFor(() => {
      expect(submitFeedback).toHaveBeenCalledWith(42, 'up');
    });
    // 已反馈态:赞按钮 active,踩按钮未激活
    await waitFor(() => {
      expect(getLikeButton()).toHaveClass('active');
    });
    expect(getDislikeButton()).not.toHaveClass('active');
  });

  it('点击踩调用 submitFeedback(logId, "down")', async () => {
    const { submitFeedback } = require('../../api/smartAssistantApi');
    submitFeedback.mockResolvedValue({ data: { feedback: 'down' } });

    await sendQuestion('测试问题', '测试回答', 7);

    fireEvent.click(getDislikeButton());

    await waitFor(() => {
      expect(submitFeedback).toHaveBeenCalledWith(7, 'down');
    });
    await waitFor(() => {
      expect(getDislikeButton()).toHaveClass('active');
    });
  });

  it('API 失败时提示错误并回滚本地状态', async () => {
    const { submitFeedback } = require('../../api/smartAssistantApi');
    submitFeedback.mockRejectedValue(new Error('server error'));

    await sendQuestion('测试问题', '测试回答', 42);

    fireEvent.click(getLikeButton());

    // 等待失败处理完成:错误提示
    await waitFor(() => {
      expect(messageErrorSpy).toHaveBeenCalledWith('反馈提交失败,请稍后重试');
    });
    // 本地状态回滚:赞按钮不再 active
    await waitFor(() => {
      expect(getLikeButton()).not.toHaveClass('active');
    });
  });

  it('相同反馈防重复提交;允许改选另一种反馈', async () => {
    const { submitFeedback } = require('../../api/smartAssistantApi');
    submitFeedback.mockResolvedValue({ data: { feedback: 'up' } });

    await sendQuestion('测试问题', '测试回答', 42);

    // 第一次点赞
    fireEvent.click(getLikeButton());
    // 等待提交完成(active 已置位且 loading 结束、按钮可用)
    await waitFor(() => {
      expect(getLikeButton()).toBeEnabled();
    });
    expect(submitFeedback).toHaveBeenCalledTimes(1);

    // 再次点赞同值 → 不重复调用
    fireEvent.click(getLikeButton());
    expect(submitFeedback).toHaveBeenCalledTimes(1);

    // 改选踩 → 允许,触发新请求
    fireEvent.click(getDislikeButton());
    await waitFor(() => {
      expect(submitFeedback).toHaveBeenLastCalledWith(42, 'down');
    });
    expect(submitFeedback).toHaveBeenCalledTimes(2);
  });

  it('旧版事件无 log_id 时仅本地标记,不调用 API', async () => {
    const { submitFeedback } = require('../../api/smartAssistantApi');

    await sendQuestion('旧版问题', '旧版回答', undefined);

    fireEvent.click(getLikeButton());

    // 本地进入已反馈态,但不触发 API
    await waitFor(() => {
      expect(getLikeButton()).toHaveClass('active');
    });
    expect(submitFeedback).not.toHaveBeenCalled();
  });
});
