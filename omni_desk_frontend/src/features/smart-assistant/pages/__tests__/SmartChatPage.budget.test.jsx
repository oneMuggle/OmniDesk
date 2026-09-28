/**
 * 方案 5.6:智能助手页的今日 AI 额度提示条。
 * 1. 进入页面时查 budget/me,只读 → 显示提示条;
 * 2. 回答的 session 事件带 budget → 提示条随之更新;budget 为 null → 隐藏。
 */
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import SmartChatPage from '../SmartChatPage';

jest.mock('../../api/smartAssistantApi', () => ({
  ...jest.requireActual('../../api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'test-session' } }),
  deleteSession: jest.fn().mockResolvedValue({}),
  submitFeedback: jest.fn(),
  getMyBudget: jest.fn(),
}));

const api = () => require('../../api/smartAssistantApi');

beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

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

const renderPage = () => render(<ConfigProvider><SmartChatPage /></ConfigProvider>);

const send = async (events) => {
  api().sendSmartChatStream.mockReturnValue({
    bodyPromise: Promise.resolve(createMockStream(events)),
    abort: jest.fn(),
  });
  fireEvent.change(screen.getByPlaceholderText(/问我任何问题/), { target: { value: '你好' } });
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
  });
};

describe('SmartChatPage 额度提示条', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('进入页面时只读 → 显示提示条', async () => {
    api().getMyBudget.mockResolvedValue({
      data: { state: 'readonly', message: '你今天的 AI 额度已用 85%，写操作、多步任务和办公文档生成暂停，普通查询不受影响。' },
    });
    renderPage();
    const notice = await screen.findByTestId('budget-notice');
    expect(notice).toHaveTextContent('已用 85%');
  });

  it('正常时不显示;回答的 session 事件带 blocked → 显示', async () => {
    api().getMyBudget.mockResolvedValue({ data: { state: 'ok', message: '' } });
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId('budget-notice')).not.toBeInTheDocument();

    await send([
      { type: 'chunk', content: '今天的 AI 额度已用完' },
      { type: 'done', error: true, kind: 'budget_exceeded' },
      { type: 'session', conversation_id: 1, log_id: 1, error: true, budget: { state: 'blocked', message: '你今天的 AI 额度已用完，明天 0 点自动恢复' } },
    ]);
    expect(await screen.findByTestId('budget-notice', {}, { timeout: 4000 })).toHaveTextContent('明天 0 点自动恢复');
  });

  it('session 事件 budget 为 null → 隐藏提示条', async () => {
    api().getMyBudget.mockResolvedValue({ data: { state: 'readonly', message: '已用 85%' } });
    renderPage();
    await screen.findByTestId('budget-notice');

    await send([
      { type: 'chunk', content: '好的' },
      { type: 'done' },
      { type: 'session', conversation_id: 1, log_id: 2, error: false, budget: null },
    ]);
    await waitFor(() => expect(screen.queryByTestId('budget-notice')).not.toBeInTheDocument(), { timeout: 4000 });
  });

  it('查询额度失败时静默', async () => {
    api().getMyBudget.mockRejectedValue(new Error('network'));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId('budget-notice')).not.toBeInTheDocument();
  });
});
