/**
 * S3-1:完整智能助手页的写操作确认卡。
 */
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import SmartChatPage from '../SmartChatPage';

jest.mock('../../api/smartAssistantApi', () => ({
  ...jest.requireActual('../../api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  sendSmartChat: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'test-session' } }),
  deleteSession: jest.fn().mockResolvedValue({}),
  submitFeedback: jest.fn(),
  approveConfirmation: jest.fn(),
  rejectConfirmation: jest.fn(),
  revertWriteLog: jest.fn(),
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

const CONFIRM_EVENTS = [
  { type: 'meta', intent: 'tool_call', tool_used: 'notification_mark_read', tool_result: { draft: {} } },
  {
    type: 'confirmation',
    awaiting_confirmation: true,
    confirmation_token: 'page-token',
    answer: '待确认：标记通知已读',
    draft: {
      summary: '待确认：标记通知已读 · 3 条通知',
      fields: {},
      preview: {
        action: '标记通知已读',
        target: { type: '通知', label: '3 条通知' },
        changes: [{ field: 'is_read', label: '状态', before: '未读', after: '已读' }],
        affected_count: 3,
        items: ['会议提醒', '报销审批', '系统公告'],
        reversible: true,
        risk: 'write',
      },
    },
  },
  { type: 'done', error: false, awaiting_confirmation: true },
];

const ANSWER_EVENTS = [
  { type: 'meta', intent: 'general_chat' },
  { type: 'chunk', content: '好的' },
  { type: 'done', finish_reason: 'stop', error: false },
];

const mockStreamOnce = (events) => {
  api().sendSmartChatStream.mockReturnValueOnce({
    bodyPromise: Promise.resolve(createMockStream(events)),
    abort: jest.fn(),
  });
};

const send = async (text) => {
  fireEvent.change(screen.getByPlaceholderText(/问我任何问题/), { target: { value: text } });
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
  });
};

describe('SmartChatPage 写操作确认卡', () => {
  beforeEach(() => jest.clearAllMocks());

  it('显示预览卡片而不是弹窗;在对话里说“确认”不会执行', async () => {
    mockStreamOnce(CONFIRM_EVENTS);
    mockStreamOnce(ANSWER_EVENTS);
    render(<ConfigProvider><SmartChatPage /></ConfigProvider>);

    await send('把未读通知都标为已读');
    const card = await screen.findByTestId('write-confirm-card', {}, { timeout: 4000 });
    expect(card).toHaveTextContent('影响范围：共 3 项');
    expect(card).toHaveTextContent('报销审批');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await send('确认');
    await screen.findByText('好的', {}, { timeout: 4000 });
    expect(api().approveConfirmation).not.toHaveBeenCalled();
    expect(api().sendSmartChat).not.toHaveBeenCalled();
    // 第二次请求不带 confirm token
    expect(api().sendSmartChatStream.mock.calls[1][3]).toBeNull();
    expect(screen.getByRole('button', { name: '确认执行' })).toBeInTheDocument();
  });

  it('点取消调用取消接口', async () => {
    mockStreamOnce(CONFIRM_EVENTS);
    api().rejectConfirmation.mockResolvedValue({ data: { rejected: true } });
    render(<ConfigProvider><SmartChatPage /></ConfigProvider>);

    await send('把未读通知都标为已读');
    await screen.findByTestId('write-confirm-card', {}, { timeout: 4000 });
    fireEvent.click(screen.getByRole('button', { name: /取\s*消/ }));
    expect(await screen.findByTestId('write-confirm-status')).toHaveTextContent('已取消');
    expect(api().rejectConfirmation).toHaveBeenCalledWith('page-token');
  });
});
