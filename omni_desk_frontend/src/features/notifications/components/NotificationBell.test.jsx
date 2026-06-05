/**
 * P5-2:NotificationBell 组件最小化测试
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import NotificationBell from './NotificationBell';
import notificationApi from '../api/notificationApi';

jest.mock('../api/notificationApi');

const unreadResponse = { data: { unread_count: 3 } };
const listResponse = {
  data: { results: [{ id: 1, title: '测试通知', content: '内容', type_display: '系统', is_read: false }] },
};

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NotificationBell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe('NotificationBell', () => {
  it('renders bell button', () => {
    notificationApi.getUnreadCount.mockResolvedValue(unreadResponse);
    notificationApi.getList.mockResolvedValue(listResponse);
    renderWithProviders();
    expect(screen.getByLabelText('通知')).toBeInTheDocument();
  });

  it('shows unread badge count', async () => {
    notificationApi.getUnreadCount.mockResolvedValue(unreadResponse);
    notificationApi.getList.mockResolvedValue(listResponse);
    renderWithProviders();
    // 用 findByText 等待异步 useQuery 解析
    expect(await screen.findByText('3')).toBeInTheDocument();
  });
});
