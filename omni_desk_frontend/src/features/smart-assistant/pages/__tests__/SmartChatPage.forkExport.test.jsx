/**
 * 智能助手会话 fork / Markdown 导出前端接入测试。
 *
 * 验证:
 * 1. 会话操作菜单点击「创建副本」→ 调用 forkSession 并切入副本会话
 * 2. 点击「导出 Markdown」→ 调用 exportSessionMarkdown(id, title) 并提示成功
 * 3. fork 失败 → message.error 提示
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigProvider, message } from 'antd';
import SmartChatPage from '../SmartChatPage';

const SOURCE_SESSION = {
  id: 1,
  title: '测试会话',
  messages: [
    { role: 'user', content: '你好' },
    { role: 'assistant', content: '你好呀' },
  ],
};

// ── API Mock ──
// 共享 API 层:requireActual 保留纯函数导出,getSessions 返回一条会话
jest.mock('../../api/smartAssistantApi', () => ({
  ...jest.requireActual('../../api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  sendSmartChat: jest.fn(),
  getSessions: jest.fn(),
  createSession: jest.fn(),
  deleteSession: jest.fn(),
  submitFeedback: jest.fn(),
}));

// fork / 导出 API(页面同目录独立模块)
jest.mock('../sessionForkExportApi', () => ({
  forkSession: jest.fn(),
  exportSessionMarkdown: jest.fn(),
}));

// ── 浏览器 API Mock ──
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

/** 渲染页面并打开会话列表面板,返回可点击的「会话操作」菜单按钮 */
const openSessionMenu = async () => {
  const { getSessions } = require('../../api/smartAssistantApi');
  getSessions.mockResolvedValue({ data: { results: [SOURCE_SESSION] } });

  renderWithProviders(<SmartChatPage />);

  // 打开会话列表面板,等待会话项渲染(列表加载完成)
  fireEvent.click(screen.getByRole('button', { name: '会话' }));
  await waitFor(() => {
    expect(screen.getByText('测试会话')).toBeInTheDocument();
  });

  // 点击会话项的操作菜单(⋯)并等待菜单展开
  const menuBtn = await screen.findByRole('button', { name: '会话操作' });
  fireEvent.click(menuBtn);
  await screen.findByText('创建副本');
};

describe('SmartChatPage 会话 fork / 导出', () => {
  let messageSuccessSpy;
  let messageErrorSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    messageSuccessSpy = jest.spyOn(message, 'success').mockImplementation(() => ({}));
    messageErrorSpy = jest.spyOn(message, 'error').mockImplementation(() => ({}));
  });

  afterEach(() => {
    messageSuccessSpy.mockRestore();
    messageErrorSpy.mockRestore();
  });

  it('点击「创建副本」调用 forkSession 并切入副本会话', async () => {
    const { forkSession } = require('../sessionForkExportApi');
    forkSession.mockResolvedValue({
      data: {
        id: 99,
        title: '测试会话（副本）',
        messages: [
          { role: 'user', content: '副本问题' },
          { role: 'assistant', content: '副本回答' },
        ],
      },
    });

    await openSessionMenu();
    fireEvent.click(screen.getByText('创建副本'));

    // 以源会话 ID 调用 fork API
    await waitFor(() => {
      expect(forkSession).toHaveBeenCalledWith(1);
    });

    // 成功后切入副本会话:副本消息渲染到聊天区
    await waitFor(() => {
      expect(screen.getByText('副本回答')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(messageSuccessSpy).toHaveBeenCalledWith('已创建会话副本');
    });
  });

  it('点击「导出 Markdown」调用 exportSessionMarkdown(id, title) 并提示成功', async () => {
    const { exportSessionMarkdown } = require('../sessionForkExportApi');
    exportSessionMarkdown.mockResolvedValue(undefined);

    await openSessionMenu();
    fireEvent.click(screen.getByText('导出 Markdown'));

    await waitFor(() => {
      expect(exportSessionMarkdown).toHaveBeenCalledWith(1, '测试会话');
    });
    await waitFor(() => {
      expect(messageSuccessSpy).toHaveBeenCalledWith('导出成功');
    });
  });

  it('fork 失败时提示错误且不切换会话', async () => {
    const { forkSession } = require('../sessionForkExportApi');
    forkSession.mockRejectedValue(new Error('server error'));

    await openSessionMenu();
    fireEvent.click(screen.getByText('创建副本'));

    await waitFor(() => {
      expect(messageErrorSpy).toHaveBeenCalledWith('创建副本失败，请稍后重试');
    });
    // 失败时不产生新会话消息
    expect(screen.queryByText('副本回答')).not.toBeInTheDocument();
  });

  it('导出失败时提示错误', async () => {
    const { exportSessionMarkdown } = require('../sessionForkExportApi');
    exportSessionMarkdown.mockRejectedValue(new Error('network error'));

    await openSessionMenu();
    fireEvent.click(screen.getByText('导出 Markdown'));

    await waitFor(() => {
      expect(messageErrorSpy).toHaveBeenCalledWith('导出失败，请稍后重试');
    });
  });
});
