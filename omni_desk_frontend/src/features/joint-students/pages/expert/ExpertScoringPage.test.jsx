import { render, screen, waitFor } from '../../../../test-utils';
import ExpertScoringPage from './ExpertScoringPage';
import { listReports } from '../../api/reports';
import { listCycles } from '../../api/cycles';
import { listScores } from '../../api/scores';

jest.mock('../../api/reports');
jest.mock('../../api/cycles');
jest.mock('../../api/scores');

describe('ExpertScoringPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('加载批次并展示报告列表', async () => {
    listCycles.mockResolvedValue({ data: { results: [
      { id: 1, year: 2026, month: 8, status: 'collecting' },
    ]}});
    listReports.mockResolvedValue({ data: { results: [
      { id: 7, joint_student: 11, student_name: '张三', student_id: 'S1', year: 2026, month: 8, attendance_days_actual: 22, attendance_days_expected: 22, status: 'approved' },
    ]}});
    listScores.mockResolvedValue({ data: { results: [] } });

    render(<ExpertScoringPage />);
    await waitFor(() => {
      expect(screen.getByText('专家打分')).toBeInTheDocument();
    });
    expect(await screen.findAllByText('张三')).not.toHaveLength(0);
    expect(await screen.findAllByText('未打分')).not.toHaveLength(0);
    const buttons = await screen.findAllByRole('button');
    const normalized = buttons.map((b) => b.textContent.replace(/\s/g, ''));
    expect(normalized.some((n) => n.includes('打分'))).toBe(true);
  });

  it('已打分显示当前分数', async () => {
    listCycles.mockResolvedValue({ data: { results: [
      { id: 1, year: 2026, month: 8, status: 'collecting' },
    ]}});
    listReports.mockResolvedValue({ data: { results: [
      { id: 7, joint_student: 11, student_name: '张三', student_id: 'S1', year: 2026, month: 8, attendance_days_actual: 22, attendance_days_expected: 22, status: 'approved' },
    ]}});
    listScores.mockResolvedValue({ data: { results: [
      { id: 50, joint_student: 11, score: 92, comment: 'good' },
    ]}});

    render(<ExpertScoringPage />);
    await waitFor(() => {
      expect(screen.getAllByText('92').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('已锁定').length).toBeGreaterThan(0);
  });
});
