import { render, screen, waitFor } from '../../../../test-utils/test-utils';
import ReportReviewPage from './ReportReviewPage';
import { listReports } from '../../api/reports';

jest.mock('../../api/reports');

describe('ReportReviewPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('默认拉取 submitted 报告', async () => {
    listReports.mockResolvedValue({ data: { results: [] } });
    render(<ReportReviewPage />);
    await waitFor(() => {
      expect(screen.getByText('月度报告审核')).toBeInTheDocument();
    });
    expect(listReports).toHaveBeenCalledWith({ status: 'submitted' });
  });

  it('展示状态文案', async () => {
    listReports.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            student_name: '张三',
            student_id: 'S1',
            year: 2026,
            month: 8,
            attendance_days_actual: 22,
            attendance_days_expected: 22,
            status: 'submitted',
          },
        ],
      },
    });
    render(<ReportReviewPage />);
    await waitFor(() => {
      expect(screen.getByText('张三')).toBeInTheDocument();
    });
    expect(await screen.findAllByText('待审核')).not.toHaveLength(0);
    const buttons = await screen.findAllByRole('button');
    const normalized = buttons.map((b) => b.textContent.replace(/\s/g, ''));
    expect(normalized.some((n) => n.includes('通过'))).toBe(true);
    expect(normalized.some((n) => n.includes('驳回'))).toBe(true);
  });
});
