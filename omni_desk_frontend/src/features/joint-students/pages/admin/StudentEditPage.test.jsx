import { render, screen, waitFor } from '../../../../test-utils';
import StudentEditPage from './StudentEditPage';
import * as api from '../../api/students';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => jest.fn(),
  useParams: () => ({ id: undefined }),
}));

jest.mock('../../api/students');

describe('StudentEditPage (新建)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.listPersonnelPool.mockResolvedValue({
      data: [{ id: 10, name: '人员A', department: '研发', has_joint_student: false }],
    });
  });

  it('加载 Personnel 池选项', async () => {
    render(<StudentEditPage />);
    await waitFor(() => {
      expect(screen.getByText('新增联培生')).toBeInTheDocument();
    });
    expect(api.listPersonnelPool).toHaveBeenCalled();
  });

  it('提交表单调用 createStudent', async () => {
    api.createStudent.mockResolvedValue({ data: { id: 1 } });
    render(<StudentEditPage />);
    await waitFor(() => {
      expect(screen.getByText('新增联培生')).toBeInTheDocument();
    });
    const buttons = await screen.findAllByRole('button');
    const normalized = buttons.map((b) => b.textContent.replace(/\s/g, ''));
    expect(normalized.some((n) => n.includes('保存'))).toBe(true);
    expect(normalized.some((n) => n.includes('取消'))).toBe(true);
  });
});
