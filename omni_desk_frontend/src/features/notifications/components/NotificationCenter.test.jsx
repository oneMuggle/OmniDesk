/**
 * P5-2:NotificationCenter 组件最小化测试
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import NotificationCenter from './NotificationCenter';
import notificationApi from '../api/notificationApi';

jest.mock('../api/notificationApi');

const listResponse = {
  data: {
    results: [
      { id: 1, title: '排班通知', content: '明天值班', type_display: '排班变更', priority: 2, is_read: false, created_at: '2026-06-05T10:00:00Z' },
    ],
    count: 1,
  },
};

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NotificationCenter />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe('NotificationCenter', () => {
  it('renders title and filter controls', () => {
    notificationApi.getList.mockResolvedValue(listResponse);
    renderWithProviders();
    expect(screen.getByText('通知中心')).toBeInTheDocument();
    expect(screen.getByText('全部已读')).toBeInTheDocument();
  });

  it('renders notification items from API', async () => {
    notificationApi.getList.mockResolvedValue(listResponse);
    renderWithProviders();
    const titleEl = await screen.findByText('排班通知');
    expect(titleEl).toBeInTheDocument();
  });
});
