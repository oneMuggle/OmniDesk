/**
 * VersionInfo 最小单测(R4-D3)。
 *
 * mock axiosInstance + RQ QueryClient,覆盖:版本数据渲染 / DEV tag 分支 / 加载失败分支。
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import axiosInstance from '../../../shared/api/axiosConfig';
import VersionInfo from '../VersionInfo';

jest.mock('../../../shared/api/axiosConfig', () => ({
  get: jest.fn(),
}));

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <VersionInfo />
    </QueryClientProvider>
  );
};

describe('VersionInfo', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('展示版本号、构建时间与 Django 版本', async () => {
    axiosInstance.get.mockResolvedValue({
      data: {
        version: '0.7.0-alpha.2',
        build_time: '2026-08-16T10:00:00Z',
        django_version: '4.2.16',
      },
    });

    renderPage();

    expect(await screen.findByText('0.7.0-alpha.2')).toBeInTheDocument();
    expect(screen.getByText('2026-08-16T10:00:00Z')).toBeInTheDocument();
    expect(screen.getByText('4.2.16')).toBeInTheDocument();
    expect(axiosInstance.get).toHaveBeenCalledWith('system/version/');
  });

  it('版本号含 dev → 渲染 DEV 标签', async () => {
    axiosInstance.get.mockResolvedValue({
      data: { version: '0.8.0dev', build_time: '', django_version: '4.2.16' },
    });

    renderPage();

    expect(await screen.findByText('0.8.0dev')).toBeInTheDocument();
    expect(screen.getByText('DEV')).toBeInTheDocument();
  });

  it('版本号不含 dev → 不渲染 DEV 标签', async () => {
    axiosInstance.get.mockResolvedValue({
      data: { version: '0.7.0', build_time: '', django_version: '4.2.16' },
    });

    renderPage();

    await screen.findByText('0.7.0');
    expect(screen.queryByText('DEV')).not.toBeInTheDocument();
  });

  it('加载失败 → 展示错误提示', async () => {
    axiosInstance.get.mockRejectedValue(new Error('network down'));

    renderPage();

    expect(await screen.findByText('Unable to load version information.')).toBeInTheDocument();
  });
});