import React from 'react';
import { render, screen } from '@testing-library/react';
import AnnouncementsPage from './AnnouncementsPage';

import apiClient from '../api/apiClient';

// Mocking the API client to prevent actual network requests during tests
jest.mock('../api/apiClient');

describe('AnnouncementsPage', () => {
  test('renders the announcements page title', () => {
    apiClient.get.mockResolvedValue({ data: [] });
    render(<AnnouncementsPage />);
    
    // 查找标题元素
    const titleElement = screen.getByRole('heading', { name: /系统公告/i });
    
    // 断言标题元素存在于文档中
    expect(titleElement).toBeInTheDocument();
  });

  test('displays "No announcements" message when there are no announcements', async () => {
    apiClient.get.mockResolvedValue({ data: [] });
    render(<AnnouncementsPage />);
    
    // 等待并查找“没有公告”的消息
    const noAnnouncementsMessage = await screen.findByText(/没有公告/i);
    
    // 断言消息存在于文档中
    expect(noAnnouncementsMessage).toBeInTheDocument();
  });
});