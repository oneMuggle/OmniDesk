import { render, screen, waitFor } from '../../../../test-utils';
import MyStipendsPage from './MyStipendsPage';
import { listStipends } from '../../api/stipends';

jest.mock('../../api/stipends');

describe('MyStipendsPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('加载已锁定补助列表', async () => {
    listStipends.mockResolvedValue({
      data: { results: [
        {
          id: 1,
          cycle: { year: 2026, month: 8 },
          grade: 'A',
          attendance_ratio: '1.00',
          final_amount: '6000.00',
          locked_at: '2026-08-30T10:00:00Z',
        },
      ]},
    });
    render(<MyStipendsPage />);
    await waitFor(() => {
      expect(screen.getByText('我的补助')).toBeInTheDocument();
    });
    expect(await screen.findAllByText('A 档')).not.toHaveLength(0);
    expect(await screen.findAllByText('100%')).not.toHaveLength(0);
    expect(await screen.findAllByText('6000.00 元')).not.toHaveLength(0);
    expect(screen.getByText('本年累计')).toBeInTheDocument();
  });

  it('空数据展示空统计', async () => {
    listStipends.mockResolvedValue({ data: { results: [] } });
    render(<MyStipendsPage />);
    await waitFor(() => {
      expect(screen.getByText('我的补助')).toBeInTheDocument();
    });
    expect(screen.getByText(/记录数/)).toBeInTheDocument();
  });
});
