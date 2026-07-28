/**
 * AgentTaskPanel 多 Agent 任务面板测试
 *
 * 覆盖:
 * - 创建表单渲染与创建并执行流程(create → execute → 自动选中)
 * - 任务列表渲染 / 空态 / 错误态
 * - 选中任务后订阅 SSE,事件增量渲染进时间线(mock subscribeTaskStream 回调)
 * - 介入按钮触发 intervene 接口
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import AgentTaskPanel from '../AgentTaskPanel';
import {
  createAgentTask,
  executeAgentTask,
  getAgentTasks,
  getAgentTaskTimeline,
  interveneAgentTask,
  subscribeTaskStream,
} from '../../api/agentTaskApi';

jest.mock('../../api/agentTaskApi', () => ({
  ...jest.requireActual('../../api/agentTaskApi'),
  getAgentTasks: jest.fn(),
  createAgentTask: jest.fn(),
  executeAgentTask: jest.fn(),
  interveneAgentTask: jest.fn(),
  getAgentTaskTimeline: jest.fn(),
  subscribeTaskStream: jest.fn(),
}));

const RUNNING_TASK = {
  task_id: 't-1',
  objective: '调研 RAG 技术',
  status: 'running',
  execution_mode: 'pipeline',
  created_at: '2026-07-01T10:00:00Z',
  subtasks: [],
};

const timelineResponse = (overrides = {}) => ({
  data: {
    task: RUNNING_TASK,
    subtasks: [],
    timeline: [],
    ...overrides,
  },
});

const renderPanel = () =>
  render(
    <ConfigProvider>
      <AgentTaskPanel />
    </ConfigProvider>
  );

describe('AgentTaskPanel', () => {
  let streamCallbacks;
  let abortMock;

  beforeEach(() => {
    jest.clearAllMocks();
    streamCallbacks = null;
    abortMock = jest.fn();
    getAgentTasks.mockResolvedValue({ data: [] });
    subscribeTaskStream.mockImplementation((taskId, callbacks) => {
      streamCallbacks = callbacks;
      return { abort: abortMock };
    });
  });

  it('渲染目标输入框与创建并执行按钮', () => {
    renderPanel();

    expect(screen.getByPlaceholderText(/任务目标/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /创建并执行/ })).toBeInTheDocument();
  });

  it('加载并展示任务列表与状态标签', async () => {
    getAgentTasks.mockResolvedValue({ data: [RUNNING_TASK] });

    renderPanel();

    expect(await screen.findByText('调研 RAG 技术')).toBeInTheDocument();
    expect(screen.getByText('执行中')).toBeInTheDocument();
    expect(getAgentTasks).toHaveBeenCalledTimes(1);
  });

  it('任务列表为空时展示空态', async () => {
    renderPanel();

    expect(await screen.findByText('暂无任务')).toBeInTheDocument();
  });

  it('任务列表加载失败时展示错误提示', async () => {
    getAgentTasks.mockRejectedValue(new Error('network'));

    renderPanel();

    expect(await screen.findByText(/任务列表加载失败/)).toBeInTheDocument();
  });

  it('创建并执行:依次调用 create 与 execute 接口并拉取新任务时间线', async () => {
    createAgentTask.mockResolvedValue({
      data: { task_id: 't-new', status: 'pending', plan: {} },
    });
    executeAgentTask.mockResolvedValue({ data: { status: 'started', task_id: 't-new' } });
    getAgentTaskTimeline.mockResolvedValue(
      timelineResponse({ task: { ...RUNNING_TASK, task_id: 't-new', objective: '写一份调研报告' } })
    );

    renderPanel();

    fireEvent.change(screen.getByPlaceholderText(/任务目标/), {
      target: { value: '写一份调研报告' },
    });
    fireEvent.click(screen.getByRole('button', { name: /创建并执行/ }));

    await waitFor(() => {
      expect(createAgentTask).toHaveBeenCalledWith('写一份调研报告');
      expect(executeAgentTask).toHaveBeenCalledWith('t-new');
    });
    // 创建后自动选中并拉取时间线详情
    await waitFor(() => expect(getAgentTaskTimeline).toHaveBeenCalledWith('t-new'));
    // 新任务出现在列表与详情中(列表项 + 详情头至少各一处)
    await waitFor(() => {
      expect(screen.getAllByText('写一份调研报告').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('创建失败时展示后端错误信息', async () => {
    createAgentTask.mockRejectedValue({
      response: { data: { error: 'Supervisor 无法生成任务计划: 无可用 LLM' } },
    });

    renderPanel();

    fireEvent.change(screen.getByPlaceholderText(/任务目标/), { target: { value: '任意目标' } });
    fireEvent.click(screen.getByRole('button', { name: /创建并执行/ }));

    expect(await screen.findByText(/Supervisor 无法生成任务计划/)).toBeInTheDocument();
    expect(executeAgentTask).not.toHaveBeenCalled();
  });

  it('选中运行中任务后订阅 SSE,事件增量渲染进时间线', async () => {
    getAgentTasks.mockResolvedValue({ data: [RUNNING_TASK] });
    getAgentTaskTimeline.mockResolvedValue(timelineResponse());

    renderPanel();

    fireEvent.click(await screen.findByText('调研 RAG 技术'));

    await waitFor(() =>
      expect(subscribeTaskStream).toHaveBeenCalledWith('t-1', expect.any(Object))
    );

    // 模拟 SSE 推送两条事件
    act(() => {
      streamCallbacks.onEvent({
        type: 'task.started',
        sequence: 1,
        payload: {},
        timestamp: '2026-07-01T10:00:01Z',
      });
      streamCallbacks.onEvent({
        type: 'subtask.tool_call',
        sequence: 2,
        subtask_id: 'st-1',
        payload: { tool: 'search' },
        timestamp: '2026-07-01T10:00:02Z',
      });
    });

    expect(screen.getByText('任务开始')).toBeInTheDocument();
    expect(screen.getByText('子任务工具调用')).toBeInTheDocument();
    expect(screen.getByText('st-1')).toBeInTheDocument();
    expect(screen.getByText(/"tool":"search"/)).toBeInTheDocument();
  });

  it('SSE 重连回放事件按 sequence 去重', async () => {
    getAgentTasks.mockResolvedValue({ data: [RUNNING_TASK] });
    // 历史时间线已含 sequence=1 的事件(模拟重连前先拉取时间线)
    getAgentTaskTimeline.mockResolvedValue(
      timelineResponse({
        timeline: [
          {
            sequence: 1,
            event_type: 'task.started',
            subtask: null,
            payload: {},
            created_at: '2026-07-01T10:00:01Z',
          },
        ],
      })
    );

    renderPanel();
    fireEvent.click(await screen.findByText('调研 RAG 技术'));
    await waitFor(() => expect(subscribeTaskStream).toHaveBeenCalled());

    // 重连流回放 sequence=1,不应产生重复节点
    act(() => {
      streamCallbacks.onEvent({
        type: 'task.started',
        sequence: 1,
        payload: {},
        timestamp: '2026-07-01T10:00:01Z',
      });
    });

    expect(screen.getAllByText('任务开始')).toHaveLength(1);
  });

  it('时间线加载历史事件并渲染中文标签', async () => {
    getAgentTasks.mockResolvedValue({
      data: [{ ...RUNNING_TASK, status: 'completed' }],
    });
    getAgentTaskTimeline.mockResolvedValue(
      timelineResponse({
        task: { ...RUNNING_TASK, status: 'completed' },
        timeline: [
          {
            sequence: 1,
            event_type: 'task.started',
            subtask: null,
            payload: {},
            created_at: '2026-07-01T10:00:01Z',
          },
          {
            sequence: 2,
            event_type: 'task.completed',
            subtask: null,
            payload: {},
            created_at: '2026-07-01T10:05:00Z',
          },
        ],
      })
    );

    renderPanel();
    fireEvent.click(await screen.findByText('调研 RAG 技术'));

    expect(await screen.findByText('任务开始')).toBeInTheDocument();
    expect(screen.getByText('任务完成')).toBeInTheDocument();
    // 终态任务不订阅 SSE
    expect(subscribeTaskStream).not.toHaveBeenCalled();
  });

  it('介入:运行中任务点击暂停触发 intervene 接口', async () => {
    getAgentTasks.mockResolvedValue({ data: [RUNNING_TASK] });
    getAgentTaskTimeline.mockResolvedValue(timelineResponse());
    interveneAgentTask.mockResolvedValue({ data: { status: 'paused' } });

    renderPanel();

    fireEvent.click(await screen.findByText('调研 RAG 技术'));
    await waitFor(() => expect(getAgentTaskTimeline).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /暂停/ }));

    await waitFor(() => expect(interveneAgentTask).toHaveBeenCalledWith('t-1', 'pause'));
  });

  it('介入:终态任务的暂停/恢复/终止按钮均禁用', async () => {
    getAgentTasks.mockResolvedValue({
      data: [{ ...RUNNING_TASK, status: 'completed' }],
    });
    getAgentTaskTimeline.mockResolvedValue(
      timelineResponse({ task: { ...RUNNING_TASK, status: 'completed' } })
    );

    renderPanel();
    fireEvent.click(await screen.findByText('调研 RAG 技术'));

    // 列表与详情各有一个「已完成」标签
    await waitFor(() => {
      expect(screen.getAllByText('已完成').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByRole('button', { name: /暂停/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /恢复/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /终止/ })).toBeDisabled();
  });

  it('组件卸载时通过 abort 断开 SSE', async () => {
    getAgentTasks.mockResolvedValue({ data: [RUNNING_TASK] });
    getAgentTaskTimeline.mockResolvedValue(timelineResponse());

    const { unmount } = renderPanel();
    fireEvent.click(await screen.findByText('调研 RAG 技术'));
    await waitFor(() => expect(subscribeTaskStream).toHaveBeenCalled());

    unmount();

    expect(abortMock).toHaveBeenCalled();
  });
});
