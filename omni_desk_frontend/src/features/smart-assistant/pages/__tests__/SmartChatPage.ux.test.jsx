/**
 * 智能助手 UX 验证测试 — 取消按钮、Think 分离。
 *
 * Task 5 of feat/sa-perf-ux: 前端体验收尾。
 * 验证 Task 4.5 实现的两个关键 UX 改进:
 * 1. 流式响应中显示停止(取消)按钮
 * 2. <thinking> 标签内容在 Collapse 中与正文分离渲染
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import SmartChatPage from '../SmartChatPage';

// ── API Mock ──
jest.mock('../../api/smartAssistantApi', () => ({
  sendSmartChatStream: jest.fn(),
  sendSmartChat: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'test-session' } }),
  deleteSession: jest.fn().mockResolvedValue({}),
}));

// ── 浏览器 API Mock ──
// jsdom 不提供 requestAnimationFrame / scrollIntoView / ReadableStream / performance.now
beforeAll(() => {
  // requestAnimationFrame 返回 0(假值),使 flushTypewriter 在 finally 块中被调用
  // (!rafRef.current → !0 → true),打字机回调不会被触发
  window.requestAnimationFrame = () => 0;
  window.cancelAnimationFrame = jest.fn();
  // jsdom 未实现 scrollIntoView,Mock 为空函数
  Element.prototype.scrollIntoView = jest.fn();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockResolvedValue(undefined) },
    writable: true,
    configurable: true,
  });
});

const renderWithProviders = (component) => {
  return render(<ConfigProvider>{component}</ConfigProvider>);
};

/**
 * 构造模拟 ReadableStream,按顺序产出 SSE 事件。
 * 每个 chunk 编码为 `data: <json>\n\n` 格式。
 */
const createMockStream = (events, delayMs = 0) => {
  const encoder = new TextEncoder();
  let index = 0;

  return new ReadableStream({
    async pull(controller) {
      if (index >= events.length) {
        controller.close();
        return;
      }
      if (delayMs > 0) {
        await new Promise((r) => setTimeout(r, delayMs));
      }
      const sseData = `data: ${JSON.stringify(events[index])}\n\n`;
      controller.enqueue(encoder.encode(sseData));
      index++;
    },
  });
};

describe('SmartChatPage UX', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows stop button(取消)while streaming', async () => {
    const { sendSmartChatStream } = require('../../api/smartAssistantApi');

    // 流永不完成 → isLoading 保持 true → 取消按钮持续显示
    sendSmartChatStream.mockReturnValue({
      bodyPromise: new Promise(() => {}),
      abort: jest.fn(),
    });

    renderWithProviders(<SmartChatPage />);

    const input = screen.getByPlaceholderText(/问我任何问题/);
    fireEvent.change(input, { target: { value: '测试问题' } });
    fireEvent.submit(input.closest('form'));

    // 验证取消按钮出现(isLoading=true 时渲染)
    await waitFor(() => {
      expect(screen.getByText('取消')).toBeInTheDocument();
    });
  });

  it('renders think content separately from main content', async () => {
    const { sendSmartChatStream } = require('../../api/smartAssistantApi');

    // 模拟包含 <thinking> 标签的流式响应
    sendSmartChatStream.mockReturnValue({
      bodyPromise: Promise.resolve(
        createMockStream([
          { type: 'meta', intent: 'general' },
          { type: 'chunk', content: '<thinking>分析中</thinking>最终答案' },
          { type: 'done' },
        ])
      ),
      abort: jest.fn(),
    });

    renderWithProviders(<SmartChatPage />);

    const input = screen.getByPlaceholderText(/问我任何问题/);
    fireEvent.change(input, { target: { value: 'think 测试' } });
    fireEvent.submit(input.closest('form'));

    // 验证正文("最终答案")首先渲染,think 折叠区存在(header "思考过程")
    await waitFor(
      () => {
        expect(screen.getByText('最终答案')).toBeInTheDocument();
        // think 折叠区 header 始终可见
        expect(screen.getByText('思考过程')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // 点击折叠区 header 展开 think 内容
    const collapseHeader = screen.getByRole('button', { name: /思考过程/i });
    fireEvent.click(collapseHeader);

    // 验证展开后 think 内容("分析中")可见
    await waitFor(() => {
      expect(screen.getByText('分析中')).toBeInTheDocument();
    });
  });
});
