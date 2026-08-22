import { render, screen, waitFor } from '../../../../test-utils/test-utils';
import StudentListPage from './StudentListPage';
import { listStudents } from '../../api/students';

jest.mock('../../api/students');

describe('StudentListPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('渲染列表并展示学号', async () => {
    listStudents.mockResolvedValue({
      data: {
        results: [
          { id: 1, student_id: '2026001', student_type: 'master', personnel_name: '张三', mentor_name: '李四', enrollment_date: '2026-09-01', is_active: true },
          { id: 2, student_id: '2026002', student_type: 'phd', personnel_name: '', mentor_name: '', enrollment_date: '2026-09-01', is_active: false },
        ],
      },
    });
    render(<StudentListPage />);
    await waitFor(() => {
      expect(screen.getByText('2026001')).toBeInTheDocument();
      expect(screen.getByText('2026002')).toBeInTheDocument();
    });
    expect(screen.getByText('联培生列表')).toBeInTheDocument();
  });

  it('空数据时表头仍可见', async () => {
    listStudents.mockResolvedValue({ data: { results: [] } });
    render(<StudentListPage />);
    await waitFor(() => {
      expect(screen.getByText('联培生列表')).toBeInTheDocument();
    });
    expect(screen.getByText('学号')).toBeInTheDocument();
  });
});
