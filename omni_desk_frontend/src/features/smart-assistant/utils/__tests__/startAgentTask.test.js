import { startAgentTask } from '../startAgentTask';

jest.mock('../../api/agentTaskApi', () => ({
  createAgentTask: jest.fn(),
  executeAgentTask: jest.fn(),
}));

const api = () => require('../../api/agentTaskApi');

describe('startAgentTask', () => {
  beforeEach(() => jest.clearAllMocks());

  it('创建 → 回调卡片 → 执行,返回协作卡片消息', async () => {
    api().createAgentTask.mockResolvedValue({ data: { task_id: 'abc', plan: { objective: '规划后的目标' } } });
    api().executeAgentTask.mockResolvedValue({});
    const order = [];
    api().executeAgentTask.mockImplementation(async () => { order.push('execute'); });

    const card = await startAgentTask('写报告', {
      conversationId: 7,
      onCreated: () => order.push('created'),
    });

    expect(api().createAgentTask).toHaveBeenCalledWith('写报告', { conversation_id: 7 });
    expect(order).toEqual(['created', 'execute']);
    expect(card).toMatchObject({
      id: 'agent-abc',
      role: 'assistant',
      type: 'collab_card',
      taskId: 'abc',
      userInput: '写报告',
      objective: '规划后的目标',
    });
  });

  it('没有 task_id 时抛错且不执行', async () => {
    api().createAgentTask.mockResolvedValue({ data: {} });
    await expect(startAgentTask('写报告')).rejects.toThrow('任务创建失败');
    expect(api().executeAgentTask).not.toHaveBeenCalled();
  });
});
