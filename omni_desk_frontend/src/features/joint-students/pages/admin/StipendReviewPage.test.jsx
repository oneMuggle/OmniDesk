import { render, screen, waitFor } from '../../../../test-utils';
import StipendReviewPage from './StipendReviewPage';
import { listStipends } from '../../api/stipends';
import { listCycles } from '../../api/cycles';

jest.mock('../../api/stipends');
jest.mock('../../api/cycles');

describe('StipendReviewPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('加载批次 + 补助列表', async () => {
    listCycles.mockResolvedValue({ data: { results: [
      { id: 1, year: 2026, month: 8, status: 'finalized' },
    ]}});
    listStipends.mockResolvedValue({ data: { results: [
      {
        id: 9,
        student_name: '张三',
        student_id: 'S1',
        rank_in_cycle: 1,
        grade: 'A',
        attendance_ratio: '1.00',
        final_amount: '6000.00',
        status: 'pending',
      },
    ]}});

    render(<StipendReviewPage />);
    await waitFor(() => {
      expect(screen.getByText('补助复核')).toBeInTheDocument();
    });
    expect(await screen.findAllByText('张三')).not.toHaveLength(0);
    expect(await screen.findAllByText('A 档')).not.toHaveLength(0);
    expect(await screen.findAllByText('100%')).not.toHaveLength(0);
    expect(await screen.findAllByText('6000.00 元')).not.toHaveLength(0);
    expect(screen.getByRole('button', { name: /复核通过/ })).toBeInTheDocument();
  });

  it('已锁定不显示复核按钮', async () => {
    listCycles.mockResolvedValue({ data: { results: [] } });
    listStipends.mockResolvedValue({ data: { results: [
      { id: 10, student_name: '李四', student_id: 'S2', rank_in_cycle: 2, grade: 'B', attendance_ratio: '0.50', final_amount: '2400.00', status: 'locked' },
    ]}});
    render(<StipendReviewPage />);
    await waitFor(() => {
      expect(screen.getAllByText('李四').length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole('button', { name: /复核通过/ })).toBeNull();
  });
});
