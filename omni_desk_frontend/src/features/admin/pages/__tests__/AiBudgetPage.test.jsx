/**
 * 方案 5.6:控制台「AI 管理 → 预算与用量」。
 */
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AiBudgetPage from '../AiBudgetPage';

jest.mock('../../../smart-assistant/api/smartAssistantApi', () => ({
  getBudgetUsage: jest.fn(),
  listBudgetPolicies: jest.fn(),
  createBudgetPolicy: jest.fn(),
  updateBudgetPolicy: jest.fn(),
  deleteBudgetPolicy: jest.fn(),
  searchBudgetUsers: jest.fn(),
}));

const api = () => require('../../../smart-assistant/api/smartAssistantApi');

const USAGE = {
  date: '2026-09-28',
  days: 7,
  soft_percent: 80,
  has_limits: false,
  totals: { tokens: 123456, calls: 321, failed_calls: 2, estimated_calls: 32, cost: 1.5, estimated_ratio: 0.1, unattributed_tokens: 0 },
  apps: [
    {
      app_name: 'smart_assistant',
      app_label: '智能助手',
      tokens: 100000,
      calls: 300,
      failed_calls: 2,
      estimated_calls: 30,
      cost: 1.2,
      state: 'ok',
      percent: null,
      limits: { tokens: 0, calls: 0, source: '未设置' },
    },
    {
      app_name: 'office_assistant',
      app_label: '办公助手',
      tokens: 23456,
      calls: 21,
      failed_calls: 0,
      estimated_calls: 2,
      cost: 0.3,
      state: 'readonly',
      percent: 85,
      limits: { tokens: 0, calls: 25, source: '应用：办公助手' },
    },
  ],
  daily: [
    { date: '2026-09-27', tokens: 1000, calls: 10, estimated_calls: 1, cost: 0 },
    { date: '2026-09-28', tokens: 123456, calls: 321, estimated_calls: 32, cost: 1.5 },
  ],
  top_users: [
    {
      user_id: 5,
      user_display: '张三（zhangsan）',
      state: 'blocked',
      percent: 100,
      usage: { tokens: 50000, calls: 120 },
      limits: { tokens: 50000, calls: 0, source: '用户组：研发' },
    },
  ],
  staff: [{ staff_key: 'secretary', name: '行政秘书', tokens: 800, calls: 4 }],
  groups: [
    { id: 1, name: 'Admin' },
    { id: 2, name: '研发' },
  ],
  app_choices: [
    { value: 'smart_assistant', label: '智能助手' },
    { value: 'office_assistant', label: '办公助手' },
  ],
};

const POLICIES = [
  {
    id: 1,
    scope: 'default',
    scope_display: '全员默认',
    group: null,
    group_name: '',
    user: null,
    user_display: '',
    app_name: '',
    app_label: '',
    daily_token_limit: 0,
    daily_call_limit: 0,
    soft_limit_percent: 80,
    note: '全员默认',
    updated_by_name: '',
  },
  {
    id: 2,
    scope: 'group',
    scope_display: '用户组',
    group: 2,
    group_name: '研发',
    user: null,
    user_display: '',
    app_name: '',
    app_label: '',
    daily_token_limit: 50000,
    daily_call_limit: 0,
    soft_limit_percent: 80,
    note: '',
    updated_by_name: 'admin',
  },
];

const rowOf = (...texts) =>
  screen.getAllByRole('row').find((row) => texts.every((text) => row.textContent.includes(text)));
// 上限配置表的行都带「同全员默认」或只读阈值列
const policyRow = (text) => rowOf(text, '同全员默认');

describe('AiBudgetPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api().getBudgetUsage.mockResolvedValue({ data: USAGE });
    api().listBudgetPolicies.mockResolvedValue({ data: POLICIES });
    api().updateBudgetPolicy.mockResolvedValue({ data: {} });
    api().createBudgetPolicy.mockResolvedValue({ data: {} });
    api().deleteBudgetPolicy.mockResolvedValue({});
  });

  it('展示今日概况、按应用、用户排行、数字员工与上限配置', async () => {
    render(<AiBudgetPage />);
    expect(await screen.findByText('当前只统计、不限制')).toBeInTheDocument();
    expect(screen.getAllByText('123,456').length).toBeGreaterThan(0);
    expect(api().getBudgetUsage).toHaveBeenCalledWith(7);

    const office = rowOf('办公助手');
    expect(within(office).getByText('只读 85%')).toBeInTheDocument();
    expect(within(office).getByText('25 次')).toBeInTheDocument();

    const user = rowOf('张三（zhangsan）');
    expect(within(user).getByText('已停用 100%')).toBeInTheDocument();
    expect(within(user).getByText('用户组：研发')).toBeInTheDocument();

    expect(screen.getByText('行政秘书')).toBeInTheDocument();

    const defaultRow = rowOf('所有人（未单独设置的用户）');
    expect(within(defaultRow).getByText('80%')).toBeInTheDocument();
    expect(within(defaultRow).queryByRole('button', { name: /删\s*除/ })).not.toBeInTheDocument();
    expect(within(policyRow('研发')).getByText('50,000')).toBeInTheDocument();
  });

  it('切换天数重新加载', async () => {
    render(<AiBudgetPage />);
    await screen.findByText('当前只统计、不限制');
    fireEvent.click(screen.getByText('近 30 天'));
    await waitFor(() => expect(api().getBudgetUsage).toHaveBeenCalledWith(30));
  });

  it('修改全员默认:可改只读阈值,提交 PATCH', async () => {
    render(<AiBudgetPage />);
    await screen.findByText('当前只统计、不限制');
    fireEvent.click(within(rowOf('所有人（未单独设置的用户）')).getByRole('button', { name: /修\s*改/ }));

    const dialog = await screen.findByRole('dialog', {}, { timeout: 4000 });
    const tokenInput = within(dialog).getByLabelText('每日 token 上限');
    fireEvent.change(tokenInput, { target: { value: '200000' } });
    const softInput = within(dialog).getByLabelText('只读阈值（%）');
    fireEvent.change(softInput, { target: { value: '70' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /保\s*存/ }));

    await waitFor(() =>
      expect(api().updateBudgetPolicy).toHaveBeenCalledWith(1, {
        daily_token_limit: 200000,
        daily_call_limit: 0,
        note: '全员默认',
        soft_limit_percent: 70,
      }),
    );
  });

  it('新增用户组上限', async () => {
    render(<AiBudgetPage />);
    await screen.findByText('当前只统计、不限制');
    fireEvent.click(screen.getByRole('button', { name: /新增上限/ }));
    const dialog = await screen.findByRole('dialog', {}, { timeout: 4000 });
    expect(within(dialog).queryByLabelText('只读阈值（%）')).not.toBeInTheDocument();

    fireEvent.mouseDown(within(dialog).getByRole('combobox'));
    fireEvent.click(await screen.findByTitle('Admin'));
    fireEvent.change(within(dialog).getByLabelText('每日调用次数上限'), { target: { value: '500' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /保\s*存/ }));

    await waitFor(() =>
      expect(api().createBudgetPolicy).toHaveBeenCalledWith(
        expect.objectContaining({ scope: 'group', group: 1, daily_call_limit: 500, daily_token_limit: 0 }),
      ),
    );
  });

  it('删除非默认上限', async () => {
    render(<AiBudgetPage />);
    await screen.findByText('当前只统计、不限制');
    fireEvent.click(within(policyRow('研发')).getByRole('button', { name: /删\s*除/ }));
    await screen.findByText('删除后按上一级上限执行，确定删除？');
    // 气泡确认框渲染在 body 末尾,最后一个「删除」按钮即确认按钮
    const buttons = screen.getAllByRole('button', { name: /删\s*除/ });
    fireEvent.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(api().deleteBudgetPolicy).toHaveBeenCalledWith(2));
  });
});
