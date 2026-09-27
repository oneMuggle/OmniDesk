/**
 * QuickAssistant S2 能力:页面上下文、快捷问题、全局唤起、任务计划卡。
 */
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import { ReadableStream } from 'stream/web';
import QuickAssistant from '../QuickAssistant';
import { openAIDrawer } from '../../utils/aiDrawer';

jest.mock('../../../features/smart-assistant/api/smartAssistantApi', () => ({
  ...jest.requireActual('../../../features/smart-assistant/api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  createSession: jest.fn().mockResolvedValue({ data: { id: 'qa-session' } }),
  getAssistantContext: jest.fn(),
}));

jest.mock('../../../features/smart-assistant/api/agentTaskApi', () => ({
  createAgentTask: jest.fn(),
  executeAgentTask: jest.fn(),
}));

jest.mock('../../../features/smart-assistant/scenario/components/ScenarioCollabCard', () => ({
  __esModule: true,
  default: ({ taskId }) => <div data-testid="collab-card">协作任务 {taskId}</div>,
}));

const api = () => require('../../../features/smart-assistant/api/smartAssistantApi');
const taskApi = () => require('../../../features/smart-assistant/api/agentTaskApi');

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

const mockStreamOnce = (events) => {
  api().sendSmartChatStream.mockReturnValueOnce({
    bodyPromise: Promise.resolve(createMockStream(events)),
    abort: jest.fn(),
  });
};

const renderAt = (route) => render(
  <MemoryRouter initialEntries={[route]}>
    <ConfigProvider>
      <QuickAssistant />
    </ConfigProvider>
  </MemoryRouter>
);

const ANSWER_EVENTS = [
  { type: 'meta', intent: 'general_chat' },
  { type: 'chunk', content: '这是回答' },
  { type: 'done', finish_reason: 'stop', error: false },
];

const PROPOSAL_EVENTS = [
  { type: 'meta', intent: 'complex_task', task_proposal: { objective: '调研传感器校准方法', mode: 'agent_task' } },
  { type: 'chunk', content: '这个问题需要多个步骤协作完成' },
  { type: 'done', finish_reason: 'stop', error: false },
];

describe('QuickAssistant S2', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api().getAssistantContext.mockResolvedValue({
      data: {
        page_context: { record_type: 'communication_post', title: '交流帖子', label: '食堂意见' },
        quick_prompts: [{ label: '总结讨论', query: '总结一下这个帖子的讨论', toolset: 'communication' }],
      },
    });
  });

  it('打开后按当前路由展示页面上下文与快捷问题,点击快捷问题带 page_route 发送', async () => {
    mockStreamOnce(ANSWER_EVENTS);
    renderAt('/communication/12');

    fireEvent.click(screen.getByRole('button'));

    expect(await screen.findByTestId('qa-page-context')).toHaveTextContent('交流帖子 · 食堂意见');
    expect(api().getAssistantContext).toHaveBeenCalledWith('/communication/12');

    fireEvent.click(screen.getByRole('button', { name: '总结讨论' }));

    await screen.findByText('这是回答');
    const call = api().sendSmartChatStream.mock.calls[0];
    expect(call[0]).toBe('总结一下这个帖子的讨论');
    expect(call[4]).toEqual({ pageRoute: '/communication/12', skipTaskProposal: false });
  });

  it('上下文接口失败时不显示标签和快捷问题,仍可正常对话', async () => {
    api().getAssistantContext.mockRejectedValue(new Error('boom'));
    mockStreamOnce(ANSWER_EVENTS);
    renderAt('/memos');

    fireEvent.click(screen.getByRole('button'));
    const input = await screen.findByPlaceholderText('问我任何问题...');
    await waitFor(() => expect(api().getAssistantContext).toHaveBeenCalled());
    expect(screen.queryByTestId('qa-page-context')).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: '你好' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await screen.findByText('这是回答');
    expect(api().sendSmartChatStream.mock.calls[0][4].pageRoute).toBe('/memos');
  });

  it('openAIDrawer({ query }) 打开抽屉并自动发送', async () => {
    mockStreamOnce(ANSWER_EVENTS);
    renderAt('/');

    act(() => {
      openAIDrawer({ query: '我今天有什么安排？' });
    });

    await screen.findByText('这是回答');
    expect(api().sendSmartChatStream).toHaveBeenCalledTimes(1);
    expect(api().sendSmartChatStream.mock.calls[0][0]).toBe('我今天有什么安排？');
  });

  it('openAIDrawer() 不带问题时只打开抽屉', async () => {
    renderAt('/');
    act(() => {
      openAIDrawer();
    });
    expect(await screen.findByPlaceholderText('问我任何问题...')).toBeInTheDocument();
    expect(api().sendSmartChatStream).not.toHaveBeenCalled();
  });

  it('完整智能助手页不显示悬浮助手', () => {
    renderAt('/smart-assistant');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('任务计划卡:创建协作任务后插入协作卡片', async () => {
    mockStreamOnce(PROPOSAL_EVENTS);
    taskApi().createAgentTask.mockResolvedValue({ data: { task_id: 't-1', plan: { objective: '调研传感器校准方法' } } });
    taskApi().executeAgentTask.mockResolvedValue({});
    renderAt('/');

    act(() => {
      openAIDrawer({ query: '调研传感器校准方法' });
    });

    expect(await screen.findByTestId('task-proposal-card', {}, { timeout: 4000 })).toHaveTextContent('调研传感器校准方法');
    fireEvent.click(screen.getByRole('button', { name: '创建协作任务' }));

    expect(await screen.findByTestId('collab-card')).toHaveTextContent('t-1');
    expect(taskApi().createAgentTask).toHaveBeenCalledWith('调研传感器校准方法', { conversation_id: 'qa-session' });
    expect(taskApi().executeAgentTask).toHaveBeenCalledWith('t-1');
    await waitFor(() => {
      expect(screen.getByTestId('task-proposal-status')).toHaveTextContent('已创建协作任务');
    });
  });

  it('任务计划卡:创建失败显示错误,可再次尝试', async () => {
    mockStreamOnce(PROPOSAL_EVENTS);
    taskApi().createAgentTask.mockRejectedValue(new Error('down'));
    renderAt('/');

    act(() => {
      openAIDrawer({ query: '调研传感器校准方法' });
    });
    await screen.findByTestId('task-proposal-card', {}, { timeout: 4000 });
    fireEvent.click(screen.getByRole('button', { name: '创建协作任务' }));

    await waitFor(() => {
      expect(screen.getByTestId('task-proposal-status')).toHaveTextContent('任务创建失败');
    }, { timeout: 4000 });
    expect(screen.getByRole('button', { name: '创建协作任务' })).not.toBeDisabled();
  });

  it('任务计划卡:直接回答时带 skipTaskProposal 重发', async () => {
    mockStreamOnce(PROPOSAL_EVENTS);
    mockStreamOnce(ANSWER_EVENTS);
    renderAt('/');

    act(() => {
      openAIDrawer({ query: '调研传感器校准方法' });
    });
    await screen.findByTestId('task-proposal-card', {}, { timeout: 4000 });
    fireEvent.click(screen.getByRole('button', { name: '直接回答' }));

    await screen.findByText('这是回答', {}, { timeout: 4000 });
    const second = api().sendSmartChatStream.mock.calls[1];
    expect(second[0]).toBe('调研传感器校准方法');
    expect(second[4].skipTaskProposal).toBe(true);
    expect(taskApi().createAgentTask).not.toHaveBeenCalled();
  });
});
