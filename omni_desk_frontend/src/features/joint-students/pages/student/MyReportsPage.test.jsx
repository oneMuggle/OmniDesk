import { render, screen, waitFor } from '../../../../test-utils/test-utils';
import MyReportsPage from './MyReportsPage';
import { listReports } from '../../api/reports';

jest.mock('../../api/reports');

describe('MyReportsPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('默认加载报告列表', async () => {
    listReports.mockResolvedValue({ data: { results: [] } });
    render(<MyReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('我的月度报告')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /新建月度报告/ })).toBeInTheDocument();
  });

  it('已通过本月报告时显示禁用按钮', async () => {
    const now = new Date();
    listReports.mockResolvedValue({
      data: { results: [
        {
          id: 1,
          year: now.getFullYear(),
          month: now.getMonth() + 1,
          attendance_days_actual: 22,
          attendance_days_expected: 22,
          status: 'approved',
          reviewer_comment: '',
        },
      ]},
    });
    render(<MyReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('本月已提交')).toBeInTheDocument();
    });
  });
});
