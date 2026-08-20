import { render, screen, waitFor } from '../../../../test-utils';
import MentorOverviewPage from './MentorOverviewPage';
import { listStudents } from '../../api/students';
import { listReports } from '../../api/reports';

jest.mock('../../api/students');
jest.mock('../../api/reports');

describe('MentorOverviewPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('加载名下联培生与本月报告状态', async () => {
    listStudents.mockResolvedValue({
      data: { results: [
        { id: 11, student_id: 'S1', student_type: 'master', personnel_name: '张三' },
        { id: 12, student_id: 'S2', student_type: 'phd', personnel_name: '李四' },
      ]},
    });
    listReports.mockResolvedValue({
      data: { results: [
        {
          id: 100,
          joint_student: 11,
          year: new Date().getFullYear(),
          month: new Date().getMonth() + 1,
          attendance_days_actual: 22,
          attendance_days_expected: 22,
          status: 'approved',
        },
      ]},
    });
    render(<MentorOverviewPage />);
    await waitFor(() => {
      expect(screen.getByText('我的联培生')).toBeInTheDocument();
    });
    expect(await screen.findAllByText('张三')).not.toHaveLength(0);
    expect(await screen.findAllByText('李四')).not.toHaveLength(0);
    expect(await screen.findAllByText('已通过')).not.toHaveLength(0);
    expect(await screen.findAllByText('未提交')).not.toHaveLength(0);
  });

  it('空数据提示', async () => {
    listStudents.mockResolvedValue({ data: { results: [] } });
    listReports.mockResolvedValue({ data: { results: [] } });
    render(<MentorOverviewPage />);
    await waitFor(() => {
      expect(screen.getByText(/未关联导师身份或名下无联培生/)).toBeInTheDocument();
    });
  });
});
