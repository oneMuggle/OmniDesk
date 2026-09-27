/**
 * QuickAssistant S3-1:抽屉里的写操作确认卡。
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import QuickAssistant from '../QuickAssistant';

jest.mock('../../../features/smart-assistant/api/smartAssistantApi', () => ({
  ...jest.requireActual('../../../features/smart-assistant/api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'qa-session' } }),
  getAssistantContext: jest.fn().mockResolvedValue({ data: { page_context: null, quick_prompts: [] } }),
  approveConfirmation: jest.fn(),
  rejectConfirmation: jest.fn(),
  revertWriteLog: jest.fn(),
}));

const api = () => require('../../../features/smart-assistant/api/smartAssistantApi');

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
  { type: 'meta', intent: 'tool_call', tool_used: 'meeting_room_book', tool_result: { draft: { summary: 's' } } },
  {
    type: 'confirmation',
    awaiting_confirmation: true,
    confirmation_token: 'qa-token',
    answer: '待确认：预约会议室',
    draft: {
      summary: '待确认：预约会议室 · 三楼大会议室',
      fields: {},
      preview: {
        action: '预约会议室',
        target: { type: '会议室预约', label: '三楼大会议室 · 10-08 14:00–15:00' },
        changes: [],
        reversible: true,
        risk: 'write',
      },
    },
  },
  { type: 'done', error: false, awaiting_confirmation: true },
];

describe('QuickAssistant 写操作确认', () => {
  beforeEach(() => jest.clearAllMocks());

  it('confirmation 事件显示确认卡,点确认调用确认接口', async () => {
    api().sendSmartChatStream.mockReturnValueOnce({
      bodyPromise: Promise.resolve(createMockStream(CONFIRM_EVENTS)),
      abort: jest.fn(),
    });
    api().approveConfirmation.mockResolvedValue({
      data: { answer: '已预约 三楼大会议室', reversible: true, write_log_id: 5 },
    });
    render(
      <MemoryRouter initialEntries={['/meeting-rooms']}>
        <ConfigProvider>
          <QuickAssistant />
        </ConfigProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button'));
    const input = await screen.findByPlaceholderText('问我任何问题...');
    fireEvent.change(input, { target: { value: '帮我订明天下午两点的三楼会议室' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    const card = await screen.findByTestId('write-confirm-card', {}, { timeout: 4000 });
    expect(card).toHaveTextContent('三楼大会议室 · 10-08 14:00–15:00');
    expect(api().approveConfirmation).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(await screen.findByTestId('write-confirm-result')).toHaveTextContent('已预约 三楼大会议室');
    expect(api().approveConfirmation).toHaveBeenCalledWith('qa-token');
  });
});
