/**
 * S2:完整智能助手页的任务计划卡(intent=complex_task)。
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
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
}));

jest.mock('../../api/agentTaskApi', () => ({
  ...jest.requireActual('../../api/agentTaskApi'),
  createAgentTask: jest.fn(),
  executeAgentTask: jest.fn(),
}));

jest.mock('../../scenario/components/ScenarioCollabCard', () => ({
  __esModule: true,
  default: ({ taskId }) => <div data-testid="collab-card">协作任务 {taskId}</div>,
}));

beforeAll(() => {
  jest.useFakeTimers();
  Element.prototype.scrollIntoView = jest.fn();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockResolvedValue(undefined) },
    writable: true,
    configurable: true,
  });
});

afterAll(() => {
  jest.useRealTimers();
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

const PROPOSAL_EVENTS = [
  { type: 'meta', intent: 'complex_task', task_proposal: { objective: '调研校准方法并写报告', mode: 'agent_task' } },
  { type: 'chunk', content: '需要多个步骤协作完成' },
  { type: 'done', finish_reason: 'stop', error: false },
];

const sendProposal = async () => {
  const { sendSmartChatStream } = require('../../api/smartAssistantApi');
  sendSmartChatStream.mockReturnValueOnce({
    bodyPromise: Promise.resolve(createMockStream(PROPOSAL_EVENTS)),
    abort: jest.fn(),
  });
  render(<ConfigProvider><SmartChatPage /></ConfigProvider>);
  fireEvent.change(screen.getByPlaceholderText(/问我任何问题/), { target: { value: '调研校准方法并写报告' } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));
  await act(async () => {
    jest.advanceTimersByTime(500);
  });
  return waitFor(() => expect(screen.getByTestId('task-proposal-card')).toBeInTheDocument(), { timeout: 3000 });
};

describe('SmartChatPage 任务计划卡', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('创建协作任务:调用任务接口并插入协作卡片', async () => {
    const taskApi = require('../../api/agentTaskApi');
    taskApi.createAgentTask.mockResolvedValue({ data: { task_id: 'task-9' } });
    taskApi.executeAgentTask.mockResolvedValue({});

    await sendProposal();
    fireEvent.click(screen.getByRole('button', { name: '创建协作任务' }));

    await waitFor(() => expect(screen.getByTestId('collab-card')).toHaveTextContent('task-9'));
    expect(taskApi.createAgentTask).toHaveBeenCalledWith('调研校准方法并写报告', { conversation_id: null });
    expect(taskApi.executeAgentTask).toHaveBeenCalledWith('task-9');
    expect(screen.getByRole('button', { name: '创建协作任务' })).toBeDisabled();
  });

  it('直接回答:带 skipTaskProposal 重发原问题', async () => {
    const { sendSmartChatStream } = require('../../api/smartAssistantApi');
    await sendProposal();
    sendSmartChatStream.mockReturnValueOnce({ bodyPromise: new Promise(() => {}), abort: jest.fn() });

    fireEvent.click(screen.getByRole('button', { name: '直接回答' }));

    await waitFor(() => expect(sendSmartChatStream).toHaveBeenCalledTimes(2));
    const second = sendSmartChatStream.mock.calls[1];
    expect(second[0]).toBe('调研校准方法并写报告');
    expect(second[4]).toEqual({ skipTaskProposal: true });
    expect(sendSmartChatStream.mock.calls[0][4]).toEqual({ skipTaskProposal: false });
  });
});
