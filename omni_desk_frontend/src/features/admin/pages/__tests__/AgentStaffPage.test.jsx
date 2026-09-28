/**
 * S4-1:控制台「AI 管理 → 数字员工」。
 */
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import AgentStaffPage from '../AgentStaffPage';

jest.mock('../../../smart-assistant/api/smartAssistantApi', () => ({
  listAgentProfiles: jest.fn(),
  updateAgentProfile: jest.fn(),
  runAgentProfile: jest.fn(),
  getAgentProfileRuns: jest.fn(),
}));

const api = () => require('../../../smart-assistant/api/smartAssistantApi');

const PROFILES = [
  {
    key: 'secretary',
    name: '个人秘书',
    description: '工作日早上推送晨报',
    schedule_label: '工作日 08:30',
    enabled: true,
    daily_llm_quota: 0,
    daily_action_quota: 500,
    usage_today: { actions: 12, llm_calls: 0 },
    last_run: { id: 1, status: 'degraded', started_at: '2026-09-28T00:30:00Z' },
  },
  {
    key: 'scheduler',
    name: '排班管理员',
    description: '巡检排班冲突',
    schedule_label: '工作日 16:00',
    enabled: false,
    daily_llm_quota: 0,
    daily_action_quota: 50,
    usage_today: { actions: 0, llm_calls: 0 },
    last_run: null,
  },
];

const rowOf = (name) => screen.getAllByRole('row').find((row) => within(row).queryByText(name));

beforeEach(() => {
  jest.clearAllMocks();
  api().listAgentProfiles.mockResolvedValue({ data: PROFILES });
});

describe('AgentStaffPage', () => {
  it('列出角色、定时、用量与最近运行', async () => {
    render(<AgentStaffPage />);
    expect(await screen.findByText('个人秘书', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText('工作日 08:30')).toBeInTheDocument();
    expect(screen.getByText('动作 12 / 500')).toBeInTheDocument();
    expect(screen.getByText('已降级')).toBeInTheDocument();
    expect(screen.getByText('尚未运行')).toBeInTheDocument();
  });

  it('启停开关调用接口并更新', async () => {
    api().updateAgentProfile.mockResolvedValue({ data: { ...PROFILES[1], enabled: true } });
    render(<AgentStaffPage />);
    const toggle = await screen.findByRole('switch', { name: '启用排班管理员' }, { timeout: 4000 });
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    expect(api().updateAgentProfile).toHaveBeenCalledWith('scheduler', { enabled: true });
    expect(await screen.findByRole('switch', { name: '启用排班管理员', checked: true })).toBeInTheDocument();
  });

  it('修改配额后出现保存按钮并提交', async () => {
    api().updateAgentProfile.mockResolvedValue({ data: { ...PROFILES[1], daily_action_quota: 80 } });
    render(<AgentStaffPage />);
    const input = await screen.findByRole('spinbutton', { name: '排班管理员动作配额' }, { timeout: 4000 });
    expect(screen.queryByRole('button', { name: '保存配额' })).not.toBeInTheDocument();
    fireEvent.change(input, { target: { value: '80' } });
    fireEvent.click(await screen.findByRole('button', { name: '保存配额' }));
    expect(api().updateAgentProfile).toHaveBeenCalledWith('scheduler', { daily_llm_quota: 0, daily_action_quota: 80 });
  });

  it('未启用的角色不能立即运行,启用的可以', async () => {
    api().runAgentProfile.mockResolvedValue({ data: {} });
    render(<AgentStaffPage />);
    await screen.findByText('排班管理员', {}, { timeout: 4000 });
    expect(within(rowOf('排班管理员')).getByRole('button', { name: '立即运行' })).toBeDisabled();
    fireEvent.click(within(rowOf('个人秘书')).getByRole('button', { name: '立即运行' }));
    expect(api().runAgentProfile).toHaveBeenCalledWith('secretary');
  });

  it('运行记录抽屉显示审计事件', async () => {
    api().getAgentProfileRuns.mockResolvedValue({
      data: [
        {
          id: 3,
          trigger: 'manual',
          status: 'degraded',
          started_at: '2026-09-28T01:00:00Z',
          error: '',
          events: [
            { id: 1, event_type: 'run.started', payload: {}, user_name: null },
            { id: 2, event_type: 'quota.exceeded', payload: { kind: 'action', quota: 2 }, user_name: null },
            { id: 3, event_type: 'notify.sent', payload: { title: '晨报' }, user_name: 'alice' },
          ],
        },
      ],
    });
    render(<AgentStaffPage />);
    await screen.findByText('个人秘书', {}, { timeout: 4000 });
    fireEvent.click(within(rowOf('个人秘书')).getByRole('button', { name: '运行记录' }));
    expect(await screen.findByText('个人秘书 · 最近运行', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(await screen.findByText('超出配额')).toBeInTheDocument();
    expect(screen.getByText('：动作配额 2')).toBeInTheDocument();
    expect(screen.getByText('：对象：alice；晨报')).toBeInTheDocument();
    expect(screen.getByText('手动')).toBeInTheDocument();
    expect(api().getAgentProfileRuns).toHaveBeenCalledWith('secretary');
  });
});
