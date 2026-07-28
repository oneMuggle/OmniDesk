/**
 * 智能助手失败辅助提示测试(后端输出契约 format_version:1)。
 *
 * 验证:
 * 1. done 事件携带 kind=no_llm_endpoint → 气泡下方渲染配置指引文案
 * 2. done 事件携带 hint → hint 优先于 kind 映射
 * 3. 旧版事件(无 kind/error 字段) → 无辅助提示行,行为与旧版一致
 * 4. 失败且流未产出正文 → 兜底失败气泡 + 辅助提示行
 * 5. format_version 字段被忽略(不渲染、不报错)
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import SmartChatPage from '../SmartChatPage';
import { ERROR_KIND_MESSAGES } from '../../api/smartAssistantApi';

// ── API Mock ──
// requireActual 保留 resolveErrorHint / ERROR_KIND_MESSAGES 等纯函数导出
jest.mock('../../api/smartAssistantApi', () => ({
  ...jest.requireActual('../../api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  sendSmartChat: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'test-session' } }),
  deleteSession: jest.fn().mockResolvedValue({}),
  submitFeedback: jest.fn(),
}));

// ── 浏览器 API Mock ──
// 与其他 SmartChatPage 测试一致:requestAnimationFrame 返回 0(假值),
// 使 finally 中 flushTypewriter 直接显示全文
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

/** 发送一条问题并等待 assistant 回复(气泡正文)出现 */
const sendAndWait = async (events, answer) => {
  const { sendSmartChatStream } = require('../../api/smartAssistantApi');
  sendSmartChatStream.mockReturnValue({
    bodyPromise: Promise.resolve(createMockStream(events)),
    abort: jest.fn(),
  });

  renderWithProviders(<SmartChatPage />);
  const input = screen.getByPlaceholderText(/问我任何问题/);
  fireEvent.change(input, { target: { value: '测试问题' } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));

  await waitFor(() => {
    expect(screen.getByText(answer)).toBeInTheDocument();
  }, { timeout: 3000 });
};

describe('SmartChatPage 失败辅助提示', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('done 携带 kind=no_llm_endpoint → 渲染配置指引文案', async () => {
    await sendAndWait([
      { type: 'meta', intent: 'general', format_version: 1 },
      { type: 'chunk', content: '回答生成失败: LLM 端点未配置', format_version: 1 },
      { type: 'done', error: true, kind: 'no_llm_endpoint', format_version: 1 },
    ], '回答生成失败: LLM 端点未配置');

    // 气泡下方出现辅助提示行(映射兜底文案)
    const hint = await screen.findByTestId('message-error-hint');
    expect(hint).toHaveTextContent(ERROR_KIND_MESSAGES.no_llm_endpoint);
    expect(hint).toHaveTextContent('管理后台 → AI 应用');
  });

  it('done 携带 hint → 优先显示 hint 而非 kind 映射', async () => {
    await sendAndWait([
      { type: 'chunk', content: '回答生成失败' },
      { type: 'done', error: true, kind: 'rate_limited', hint: '当前并发过高，请 30 秒后重试' },
    ], '回答生成失败');

    const hint = await screen.findByTestId('message-error-hint');
    expect(hint).toHaveTextContent('当前并发过高，请 30 秒后重试');
    // kind 映射文案不应出现
    expect(hint).not.toHaveTextContent(ERROR_KIND_MESSAGES.rate_limited);
  });

  it('旧版事件(无 kind/error 字段) → 无辅助提示行且不崩溃', async () => {
    await sendAndWait([
      { type: 'meta', intent: 'general' },
      { type: 'chunk', content: '正常回答内容' },
      { type: 'done' },
    ], '正常回答内容');

    // 流结束后仍不应出现提示行
    expect(screen.queryByTestId('message-error-hint')).not.toBeInTheDocument();
  });

  it('失败且流未产出正文 → 兜底失败气泡 + 辅助提示行', async () => {
    await sendAndWait([
      { type: 'done', error: true, kind: 'llm_unavailable' },
    ], '回答生成失败');

    const hint = await screen.findByTestId('message-error-hint');
    expect(hint).toHaveTextContent(ERROR_KIND_MESSAGES.llm_unavailable);
  });

  it('失败消息(带 errorHint)不渲染赞踩按钮', async () => {
    // 失败消息无归属 AgentLog(无主日志),feedback 提交必然 404,
    // 故不展示赞踩入口,避免体验不一致
    await sendAndWait([
      { type: 'chunk', content: '回答生成失败' },
      { type: 'done', error: true, kind: 'no_llm_endpoint' },
    ], '回答生成失败');

    // 等待流结束(errorHint 已渲染即最终态)
    await screen.findByTestId('message-error-hint');

    // antd 图标按钮的无障碍名来自图标 aria-label(赞: like / 踩: dislike)
    expect(screen.queryByRole('button', { name: 'like' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'dislike' })).not.toBeInTheDocument();
  });
});
