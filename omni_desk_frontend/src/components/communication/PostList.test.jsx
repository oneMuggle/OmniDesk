import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import PostList from './PostList';

jest.mock('../../features/communication/api/communicationApi', () => ({
  getPosts: jest.fn(),
}));

jest.mock('../../shared/context/RefreshContext', () => {
  const { createContext } = require('react');
  return { RefreshContext: createContext({ refreshKey: 0 }) };
});

const renderWithRouter = (ui, { initialEntries = ['/communication'] } = {}) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {ui}
    </MemoryRouter>
  );
};

describe('PostList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows loading spinner initially', () => {
    const { getPosts } = require('../../features/communication/api/communicationApi');
    getPosts.mockReturnValue(new Promise(() => {}));
    renderWithRouter(<PostList />);
    expect(document.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('renders posts when loaded', async () => {
    const { getPosts } = require('../../features/communication/api/communicationApi');
    getPosts.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            title: 'Post 1',
            content: '<p>Content 1</p>',
            author: 'Admin',
            created_at: '2024-01-01',
          },
        ],
      },
    });
    renderWithRouter(<PostList />);
    await waitFor(() => {
      expect(screen.getByText('Post 1')).toBeInTheDocument();
    });
    expect(screen.getByText('作者:')).toBeInTheDocument();
  });

  it('shows empty list when no posts', async () => {
    const { getPosts } = require('../../features/communication/api/communicationApi');
    getPosts.mockResolvedValue({ data: { results: [] } });
    renderWithRouter(<PostList />);
    await waitFor(() => {
      expect(screen.getByText('帖子列表')).toBeInTheDocument();
    });
  });

  it('shows empty posts array on fetch error', async () => {
    const { getPosts } = require('../../features/communication/api/communicationApi');
    getPosts.mockRejectedValue(new Error('Failed'));
    renderWithRouter(<PostList />);
    await waitFor(() => {
      expect(screen.getByText('帖子列表')).toBeInTheDocument();
    });
  });
});
