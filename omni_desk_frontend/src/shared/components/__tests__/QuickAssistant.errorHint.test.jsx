/**
 * QuickAssistant 失败辅助提示测试(后端输出契约 format_version:1)。
 *
 * 验证:
 * 1. done 事件携带 kind → 消息气泡下方渲染映射文案
 * 2. done 事件携带 hint → 优先显示 hint
 * 3. 旧版事件(无 kind/error 字段) → 无辅助提示行,行为与旧版一致
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import QuickAssistant from '../QuickAssistant';
import { ERROR_KIND_MESSAGES } from '../../../features/smart-assistant/api/smartAssistantApi';

// ── API Mock ──
// requireActual 保留 resolveErrorHint / ERROR_KIND_MESSAGES 等纯函数导出
jest.mock('../../../features/smart-assistant/api/smartAssistantApi', () => ({
  ...jest.requireActual('../../../features/smart-assistant/api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'qa-session' } }),
}));

beforeAll(() => {
  // jsdom 未实现 scrollIntoView,Mock 为空函数
  Element.prototype.scrollIntoView = jest.fn();
});

const renderQuickAssistant = () => render(
  <MemoryRouter>
    <ConfigProvider>
      <QuickAssistant />
    </ConfigProvider>
  </MemoryRouter>
);

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

/** 打开抽屉、发送一条问题并等待回复正文出现 */
const openAndSend = async (events, answer) => {
  const { sendSmartChatStream } = require('../../../features/smart-assistant/api/smartAssistantApi');
  sendSmartChatStream.mockReturnValue({
    bodyPromise: Promise.resolve(createMockStream(events)),
    abort: jest.fn(),
  });

  renderQuickAssistant();

  // 抽屉关闭时 FloatButton 是唯一按钮;点击打开抽屉
  fireEvent.click(screen.getByRole('button'));

  const input = await screen.findByPlaceholderText('问我任何问题...');
  fireEvent.change(input, { target: { value: '测试问题' } });
  // Enter 提交(不带 Shift)
  fireEvent.keyDown(input, { key: 'Enter' });

  await waitFor(() => {
    expect(screen.getByText(answer)).toBeInTheDocument();
  }, { timeout: 3000 });
};

describe('QuickAssistant 失败辅助提示', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('done 携带 kind=llm_unavailable → 渲染映射文案', async () => {
    await openAndSend([
      { type: 'chunk', content: '回答生成失败', format_version: 1 },
      { type: 'done', error: true, kind: 'llm_unavailable', format_version: 1 },
    ], '回答生成失败');

    const hint = await screen.findByTestId('qa-error-hint');
    expect(hint).toHaveTextContent(ERROR_KIND_MESSAGES.llm_unavailable);
  });

  it('done 携带 hint → 优先显示 hint', async () => {
    await openAndSend([
      { type: 'chunk', content: '回答生成失败' },
      { type: 'done', error: true, kind: 'internal_error', hint: '模型服务维护中' },
    ], '回答生成失败');

    const hint = await screen.findByTestId('qa-error-hint');
    expect(hint).toHaveTextContent('模型服务维护中');
    expect(hint).not.toHaveTextContent(ERROR_KIND_MESSAGES.internal_error);
  });

  it('旧版事件(无 kind/error 字段) → 无辅助提示行', async () => {
    await openAndSend([
      { type: 'chunk', content: '正常回答' },
      { type: 'done' },
    ], '正常回答');

    expect(screen.queryByTestId('qa-error-hint')).not.toBeInTheDocument();
  });
});
