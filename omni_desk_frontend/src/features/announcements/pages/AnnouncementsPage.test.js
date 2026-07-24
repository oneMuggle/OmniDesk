import { render, screen } from '@testing-library/react';
import AnnouncementsPage from './AnnouncementsPage';

import apiClient from '../../../shared/api/apiClient';

// Mocking the API client to prevent actual network requests during tests
jest.mock('../../../shared/api/apiClient');

describe('AnnouncementsPage', () => {
  beforeEach(() => {
    // 在每个测试用例运行前重置 mock
    apiClient.get.mockReset();
  });

  test('renders the announcements page title', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    render(<AnnouncementsPage />);
    
    // 查找标题元素
    const titleElement = await screen.findByRole('heading', { name: /系统公告/i });
    
    // 断言标题元素存在于文档中
    expect(titleElement).toBeInTheDocument();
  });

  test('displays "No announcements" message when there are no announcements', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    render(<AnnouncementsPage />);
    
    // 等待并查找“没有公告”的消息
    const noAnnouncementsMessage = await screen.findByText(/没有公告/i);
    
    // 断言消息存在于文档中
    expect(noAnnouncementsMessage).toBeInTheDocument();
  });

  test('displays announcements when API call is successful', async () => {
    const mockAnnouncements = {
      data: {
        results: [
          { id: 1, title: 'First Announcement', content: 'Content of the first announcement.', created_at: '2025-12-19T10:00:00Z', author: { username: 'admin' } },
          { id: 2, title: 'Second Announcement', content: 'Content of the second announcement.', created_at: '2025-12-19T11:00:00Z', author: { username: 'admin' } },
        ]
      }
    };
    apiClient.get.mockResolvedValue(mockAnnouncements);
    render(<AnnouncementsPage />);

    // react-slick 可能会渲染幻灯片的多个实例，因此我们使用 findAllByText
    // 并断言文本至少出现一次，以确保测试的健壮性。
    expect((await screen.findAllByText('First Announcement'))[0]).toBeInTheDocument();
    expect((await screen.findAllByText('Second Announcement'))[0]).toBeInTheDocument();
  });
});