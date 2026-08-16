/**
 * SyncStatusPage 最小渲染测试(R4-D1)。
 *
 * mock axiosInstance 与 PaperlessHealthBanner,断言:
 * outbox 列表数据渲染、空态文案。
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import axiosInstance from '../../../../shared/api/axiosConfig';
import SyncStatusPage from '../SyncStatusPage';

jest.mock('../../../../shared/api/axiosConfig', () => ({
  get: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
}));

jest.mock('../../components/PaperlessHealthBanner', () => function MockBanner() {
  return null;
});

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SyncStatusPage />
    </QueryClientProvider>
  );
};

describe('SyncStatusPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockOutbox = (results, count) => {
    axiosInstance.get.mockImplementation((url) => {
      if (url === '/paperless/outbox/') {
        return Promise.resolve({ data: { results, count } });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });
  };

  it('渲染 outbox 列表数据(文件名/标题/来源)', async () => {
    mockOutbox(
      [{
        id: 1,
        filename: '财务报告.pdf',
        title: 'Q3 财务报告',
        source_type: 'compliance_report',
        status: 'synced',
        retry_count: 0,
        created_at: '2026-08-01T10:00:00+08:00',
      }],
      1,
    );

    renderPage();

    expect(await screen.findByText('财务报告.pdf')).toBeInTheDocument();
    expect(screen.getByText('Q3 财务报告')).toBeInTheDocument();
    expect(screen.getByText('compliance_report')).toBeInTheDocument();
  });

  it('空列表展示占位文案', async () => {
    mockOutbox([], 0);

    renderPage();

    expect(await screen.findByText('暂无同步记录')).toBeInTheDocument();
  });
});