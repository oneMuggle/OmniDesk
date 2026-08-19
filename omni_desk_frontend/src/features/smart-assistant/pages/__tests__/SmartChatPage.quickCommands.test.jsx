/**
 * P0-3:QuickCommands 接入 SmartChatPage 验证。
 *
 * 此前 QuickCommands 组件已建好但未挂载到聊天页(孤儿代码)。本测试验证:
 * 1. 快捷指令按钮在聊天页渲染可见
 * 2. 点击快捷指令会以对应 query 触发流式发送(sendSmartChatStream)
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import SmartChatPage from '../SmartChatPage';

// ── API Mock(保留纯函数导出)──
jest.mock('../../api/smartAssistantApi', () => ({
  ...jest.requireActual('../../api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  sendSmartChat: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'test-session' } }),
  deleteSession: jest.fn().mockResolvedValue({}),
}));

// ── 浏览器 API Mock(jsdom 缺失)──
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

describe('SmartChatPage 快捷指令接入(P0-3)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('渲染快捷指令按钮', async () => {
    const { sendSmartChatStream } = require('../../api/smartAssistantApi');
    sendSmartChatStream.mockReturnValue({ bodyPromise: new Promise(() => {}), abort: jest.fn() });

    renderWithProviders(<SmartChatPage />);

    // 快捷指令区标签 + 代表性按钮可见
    expect(await screen.findByText('快捷指令')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /明天谁值班/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '我的本周' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '我今天' })).toBeInTheDocument();
  });

  it('点击普通快捷指令以对应 query 发送', async () => {
    const { sendSmartChatStream } = require('../../api/smartAssistantApi');
    sendSmartChatStream.mockReturnValue({ bodyPromise: new Promise(() => {}), abort: jest.fn() });

    renderWithProviders(<SmartChatPage />);

    fireEvent.click(await screen.findByRole('button', { name: /明天谁值班/ }));

    await waitFor(() => {
      expect(sendSmartChatStream).toHaveBeenCalled();
    });
    // 第一个参数为快捷指令对应的 query
    expect(sendSmartChatStream.mock.calls[0][0]).toBe('明天谁值班？');
  });

  it('点击"我的本周"个人总结指令翻译为自然语言 query', async () => {
    const { sendSmartChatStream } = require('../../api/smartAssistantApi');
    sendSmartChatStream.mockReturnValue({ bodyPromise: new Promise(() => {}), abort: jest.fn() });

    renderWithProviders(<SmartChatPage />);

    fireEvent.click(await screen.findByRole('button', { name: '我的本周' }));

    await waitFor(() => {
      expect(sendSmartChatStream).toHaveBeenCalled();
    });
    // personal_summary + scope=week → 翻译为"这周我有哪些事"
    expect(sendSmartChatStream.mock.calls[0][0]).toBe('这周我有哪些事');
  });
});
