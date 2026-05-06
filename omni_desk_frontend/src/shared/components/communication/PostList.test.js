import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PostList from './PostList';

jest.mock('../../context/RefreshContext', () => {
  const { createContext } = require('react');
  return { RefreshContext: createContext({ refreshKey: 0 }) };
});

jest.mock('../../api/communicationApi', () => ({
  getPosts: jest.fn(),
}));

import { getPosts } from '../../api/communicationApi';

const mockGetPosts = getPosts;

const renderWithRouter = (ui, { initialEntries } = {}) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="*" element={ui} />
      </Routes>
    </MemoryRouter>
  );
};

describe('PostList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows loading spinner while fetching', () => {
    mockGetPosts.mockReturnValue(new Promise(() => {}));
    renderWithRouter(<PostList />);
    expect(document.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('renders posts after fetching', async () => {
    mockGetPosts.mockResolvedValue({
      data: {
        results: [
          { id: 1, title: 'First Post', content: '<p>Hello world</p>', author: 'Alice', created_at: '2026-01-01T00:00:00Z' },
          { id: 2, title: 'Second Post', content: '<p>Testing is great</p>', author: 'Bob', created_at: '2026-02-01T00:00:00Z' },
        ],
      },
    });
    renderWithRouter(<PostList />);

    await waitFor(() => {
      expect(screen.getByText('First Post')).toBeInTheDocument();
      expect(screen.getByText('Second Post')).toBeInTheDocument();
    });
  });

  it('renders empty list when no posts', async () => {
    mockGetPosts.mockResolvedValue({ data: { results: [] } });
    renderWithRouter(<PostList />);

    await waitFor(() => {
      expect(screen.getByText('帖子列表')).toBeInTheDocument();
    });
  });

  it('renders empty list on fetch error', async () => {
    mockGetPosts.mockRejectedValue(new Error('Network error'));
    renderWithRouter(<PostList />);

    await waitFor(() => {
      expect(screen.getByText('帖子列表')).toBeInTheDocument();
    });
  });

  it('strips HTML tags from content preview', async () => {
    mockGetPosts.mockResolvedValue({
      data: {
        results: [
          { id: 1, title: 'HTML Post', content: '<strong>Bold</strong> text', author: 'Dev', created_at: '2026-01-01' },
        ],
      },
    });
    renderWithRouter(<PostList />);

    await waitFor(() => {
      expect(screen.getByText(/Bold text/)).toBeInTheDocument();
    });
  });
});
