import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import AnnouncementsPage from './AnnouncementsPage';

import apiClient from '../../../shared/api/apiClient';

// Mocking the API client to prevent actual network requests during tests
jest.mock('../../../shared/api/apiClient');

describe('AnnouncementsPage', () => {
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

    await waitFor(() => {
      expect(screen.getAllByText('First Announcement').length).toBeGreaterThan(0);
    });
    
    expect(screen.getAllByText('Second Announcement').length).toBeGreaterThan(0);
  });
});