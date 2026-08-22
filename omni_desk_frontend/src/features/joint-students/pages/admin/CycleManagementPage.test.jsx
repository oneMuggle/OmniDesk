import { render, screen, waitFor } from '../../../../test-utils/test-utils';
import CycleManagementPage from './CycleManagementPage';
import { listCycles } from '../../api/cycles';

jest.mock('../../api/cycles');

describe('CycleManagementPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('加载批次列表', async () => {
    listCycles.mockResolvedValue({
      data: { results: [
        { id: 1, year: 2026, month: 8, cycle_end_date: '2026-08-25', scoring_deadline: '2026-08-28', status: 'collecting', trigger_source: 'manual' },
      ]},
    });
    render(<CycleManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('考核批次管理')).toBeInTheDocument();
    });
    expect(await screen.findAllByText('2026-08-25')).not.toHaveLength(0);
    expect(await screen.findAllByText('收集中')).not.toHaveLength(0);
    expect(await screen.findAllByText('手动')).not.toHaveLength(0);
    expect(screen.getAllByRole('button', { name: /强制截止/ }).length).toBeGreaterThan(0);
  });

  it('已截止批次不显示强制截止按钮', async () => {
    listCycles.mockResolvedValue({
      data: { results: [
        { id: 1, year: 2026, month: 7, cycle_end_date: '2026-07-25', scoring_deadline: '2026-07-28', status: 'closed', trigger_source: 'auto' },
      ]},
    });
    render(<CycleManagementPage />);
    await waitFor(async () => {
      expect(await screen.findAllByText('已截止')).not.toHaveLength(0);
    });
    expect(screen.queryByRole('button', { name: /强制截止/ })).toBeNull();
  });
});
