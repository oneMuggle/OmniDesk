import { render, screen, waitFor } from '@testing-library/react';
import { AuthContext } from '../../features/auth/context/AuthContext';
import EventsPage from './EventsPage';
import apiClient from '../api/apiClient';

jest.mock('../api/apiClient');

// R4-B5: canManageEvents 改由 hasPermission 提供,测试 mock 补齐
const renderPage = (authValue = { user: { role: 'user' }, hasPermission: () => false }) =>
  render(
    <AuthContext.Provider value={authValue}>
      <EventsPage />
    </AuthContext.Provider>
  );

describe('EventsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('挂载时调用 apiClient.get("events/") 并渲染返回数据', async () => {
    apiClient.get.mockResolvedValue({
      data: {
        results: [
          { id: 1, title: '年度会议' },
          { id: 2, title: '安全培训' },
        ],
      },
      status: 200,
    });

    renderPage();

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('events/');
    });

    expect(await screen.findByText('年度会议')).toBeInTheDocument();
    expect(screen.getByText('安全培训')).toBeInTheDocument();
  });

  it('兼容纯数组响应', async () => {
    apiClient.get.mockResolvedValue({
      data: [{ id: 9, title: '数组事件' }],
      status: 200,
    });

    renderPage();

    expect(await screen.findByText('数组事件')).toBeInTheDocument();
  });

  it('请求失败时展示错误信息', async () => {
    apiClient.get.mockRejectedValue(new Error('网络异常'));

    renderPage();

    expect(await screen.findByText(/加载失败: 网络异常/)).toBeInTheDocument();
  });
});
