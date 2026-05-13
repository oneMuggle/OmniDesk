import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import PostDetail from './PostDetail';

jest.mock('../../features/communication/api/communicationApi', () => ({
  getPost: jest.fn(),
  createComment: jest.fn(),
}));

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => jest.fn(),
  useParams: () => ({ postId: '1' }),
}));

const renderWithRouter = (ui, { initialEntries = ['/communication/1'] } = {}) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {ui}
    </MemoryRouter>
  );
};

describe('PostDetail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows loading spinner initially', () => {
    const { getPost } = require('../../features/communication/api/communicationApi');
    getPost.mockReturnValue(new Promise(() => {}));
    renderWithRouter(<PostDetail />);
    expect(document.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('renders post content when loaded', async () => {
    const { getPost } = require('../../features/communication/api/communicationApi');
    getPost.mockResolvedValue({
      data: {
        id: 1,
        title: 'Test Post',
        content: '<p>Hello world</p>',
        author: 'Admin',
        created_at: '2024-01-01T00:00:00',
        tags: ['tag1'],
        comments: [],
      },
    });
    renderWithRouter(<PostDetail />);
    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('tag1')).toBeInTheDocument();
  });

  it('shows error alert when fetch fails', async () => {
    const { getPost } = require('../../features/communication/api/communicationApi');
    getPost.mockRejectedValue(new Error('Failed'));
    renderWithRouter(<PostDetail />);
    await waitFor(() => {
      expect(screen.getByText('错误')).toBeInTheDocument();
    });
    expect(screen.getByText('获取帖子失败，请稍后重试。')).toBeInTheDocument();
  });

  it('shows error alert when post data is null', async () => {
    const { getPost } = require('../../features/communication/api/communicationApi');
    getPost.mockResolvedValue({ data: null });
    renderWithRouter(<PostDetail />);
    await waitFor(() => {
      expect(document.querySelector('.post-detail-error')).toBeInTheDocument();
    });
  });

  it('renders comments when present', async () => {
    const { getPost } = require('../../features/communication/api/communicationApi');
    getPost.mockResolvedValue({
      data: {
        id: 1,
        title: 'Post',
        content: '<p>Content</p>',
        author: 'Author',
        created_at: '2024-01-01',
        comments: [
          { id: 1, content: 'Nice!', author: 'User1', created_at: '2024-01-02' },
        ],
      },
    });
    renderWithRouter(<PostDetail />);
    await waitFor(() => {
      expect(screen.getByText('Nice!')).toBeInTheDocument();
    });
    expect(screen.getByText('User1')).toBeInTheDocument();
  });

  it('shows no comments message when comments empty', async () => {
    const { getPost } = require('../../features/communication/api/communicationApi');
    getPost.mockResolvedValue({
      data: {
        id: 1,
        title: 'Post',
        content: '<p>Content</p>',
        author: 'Author',
        created_at: '2024-01-01',
        comments: [],
      },
    });
    renderWithRouter(<PostDetail />);
    await waitFor(() => {
      expect(screen.getByText('暂无评论，快来抢沙发吧！')).toBeInTheDocument();
    });
  });
});
