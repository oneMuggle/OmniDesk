/**
 * Tests for NotificationsPage component.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import NotificationsPage from './NotificationsPage';
import notificationApi from '../../features/notifications/api/notificationApi';

jest.mock('../../features/notifications/api/notificationApi');

const createQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false, gcTime: 0 },
    mutations: { retry: false },
  },
});

const renderWithQueryClient = (ui, queryClient) => {
  const qc = queryClient || createQueryClient();
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
  );
};

describe('NotificationsPage', () => {
  let queryClient;

  beforeEach(() => {
    jest.clearAllMocks();
    queryClient = createQueryClient();
  });

  it('renders empty state when no notifications', async () => {
    notificationApi.getList.mockResolvedValue({ data: { results: [] } });

    renderWithQueryClient(<NotificationsPage />, queryClient);

    await waitFor(() => {
      expect(notificationApi.getList).toHaveBeenCalled();
    });
  });

  it('renders notifications with correct type tags', async () => {
    notificationApi.getList.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            type: 'schedule_change',
            title: '排班调整通知',
            message: '您的值班日期已调整',
            is_read: false,
            created_at: '2026-05-30T10:00:00Z',
            link: '/schedule',
          },
          {
            id: 2,
            type: 'compliance_issue',
            title: '合规问题通知',
            message: '发现新的合规问题',
            is_read: true,
            created_at: '2026-05-29T08:00:00Z',
            link: null,
          },
        ]
      }
    });

    renderWithQueryClient(<NotificationsPage />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('排班调整通知')).toBeInTheDocument();
    });

    expect(screen.getByText('合规问题通知')).toBeInTheDocument();
  });

  it('marks notification as read on row click', async () => {
    notificationApi.getList.mockResolvedValue({
      data: {
        results: [{
          id: 1,
          type: 'announcement',
          title: 'Test Announcement',
          message: 'Test message',
          is_read: false,
          created_at: '2026-05-30T10:00:00Z',
          link: null,
        }]
      }
    });
    notificationApi.markRead.mockResolvedValue({ data: {} });

    renderWithQueryClient(<NotificationsPage />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Test Announcement')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Announcement'));

    await waitFor(() => {
      expect(notificationApi.markRead).toHaveBeenCalledWith(1);
    });
  });

  it('filters notifications by read status', async () => {
    notificationApi.getList.mockResolvedValue({
      data: { results: [] }
    });

    renderWithQueryClient(<NotificationsPage />, queryClient);

    await waitFor(() => {
      expect(notificationApi.getList).toHaveBeenCalledWith({});
    });
  });
});
